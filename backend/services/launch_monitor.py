from math import atan2, degrees, sqrt
from statistics import median
from typing import Dict, List, Optional, Tuple


BALL_DIAMETER_INCHES = 1.68
YARDS_PER_SECOND_TO_MPH = 3600 / 1760
MIN_POINT_CONFIDENCE = 0.2


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _safe_float(value: object) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_round(value: Optional[float], digits: int = 2) -> Optional[float]:
    return round(value, digits) if value is not None else None


def _point_to_pixel(point: Dict[str, object], width: int, height: int) -> Tuple[float, float]:
    return float(point['x']) * width, float(point['y']) * height


def _visible_samples(
    frames: List[Dict[str, object]],
    point_key: str,
    min_confidence: float = MIN_POINT_CONFIDENCE,
) -> List[Tuple[int, Dict[str, object]]]:
    samples: List[Tuple[int, Dict[str, object]]] = []
    for frame_data in frames:
        point = frame_data.get(point_key)
        timestamp_ms = _safe_int(frame_data.get('timestampMs'))
        confidence = _safe_float(point.get('confidence')) if isinstance(point, dict) else None
        if not isinstance(point, dict) or timestamp_ms is None or confidence is None or confidence < min_confidence:
            continue
        samples.append((timestamp_ms, point))
    return sorted(samples, key=lambda sample: sample[0])


def _speed_segments(
    frames: List[Dict[str, object]],
    point_key: str,
    width: int,
    height: int,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> List[Dict[str, object]]:
    samples = _visible_samples(frames, point_key)
    segments: List[Dict[str, object]] = []
    previous: Optional[Tuple[int, Dict[str, object]]] = None

    for current in samples:
        current_ms, current_point = current
        if previous is not None:
            previous_ms, previous_point = previous
            if current_ms > previous_ms:
                if start_ms is not None and current_ms < start_ms:
                    previous = current
                    continue
                if end_ms is not None and previous_ms > end_ms:
                    previous = current
                    continue

                previous_x, previous_y = _point_to_pixel(previous_point, width, height)
                current_x, current_y = _point_to_pixel(current_point, width, height)
                dx_px = current_x - previous_x
                dy_px = current_y - previous_y
                distance_px = sqrt(dx_px * dx_px + dy_px * dy_px)
                delta_seconds = (current_ms - previous_ms) / 1000
                confidence = min(
                    float(previous_point.get('confidence') or 0),
                    float(current_point.get('confidence') or 0),
                )
                segments.append({
                    'timestampMs': current_ms,
                    'startTimestampMs': previous_ms,
                    'endTimestampMs': current_ms,
                    'speedPxPerSec': distance_px / delta_seconds,
                    'distancePx': distance_px,
                    'deltaXPx': dx_px,
                    'deltaYPx': dy_px,
                    'confidence': confidence,
                })
        previous = current

    return segments


def _max_speed_segment(
    frames: List[Dict[str, object]],
    point_key: str,
    width: int,
    height: int,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> Optional[Dict[str, object]]:
    segments = _speed_segments(frames, point_key, width, height, start_ms, end_ms)
    if not segments:
        return None
    return max(segments, key=lambda segment: float(segment['speedPxPerSec']))


def _calibration_from_metadata(metadata: Dict[str, object]) -> Optional[Dict[str, object]]:
    calibration = metadata.get('calibration') if isinstance(metadata.get('calibration'), dict) else {}
    candidates = (
        metadata.get('yardsPerPixel'),
        calibration.get('yardsPerPixel'),
        metadata.get('metersPerPixel'),
        calibration.get('metersPerPixel'),
    )
    for index, candidate in enumerate(candidates):
        value = _safe_float(candidate)
        if value is None or value <= 0:
            continue
        yards_per_pixel = value * 1.09361 if index >= 2 else value
        return {
            'status': 'calibrated',
            'method': 'provided_yards_per_pixel' if index < 2 else 'provided_meters_per_pixel',
            'yardsPerPixel': yards_per_pixel,
            'confidence': 0.82,
            'notes': 'Physical speed and distance estimates use caller-provided scene calibration.',
        }
    return None


def _calibration_from_ball_size(ball_frames: List[Dict[str, object]]) -> Dict[str, object]:
    diameters_px: List[float] = []
    for _timestamp_ms, point in _visible_samples(ball_frames, 'ball', min_confidence=0.22)[:8]:
        diameter_px = _safe_float(point.get('diameterPx'))
        radius_px = _safe_float(point.get('radiusPx'))
        if diameter_px is None and radius_px is not None:
            diameter_px = radius_px * 2
        if diameter_px is not None and diameter_px >= 2:
            diameters_px.append(diameter_px)

    if not diameters_px:
        return {
            'status': 'pixel_only',
            'method': 'none',
            'yardsPerPixel': None,
            'confidence': 0,
            'notes': 'No physical calibration was available, so mph, yards, spin rate, and true carry stay unavailable.',
        }

    median_diameter_px = median(diameters_px)
    yards_per_pixel = (BALL_DIAMETER_INCHES / 36) / median_diameter_px
    confidence = _clamp(0.16 + min(len(diameters_px) / 10, 0.2) + min(median_diameter_px / 40, 0.18), 0, 0.48)
    return {
        'status': 'estimated',
        'method': 'detected_golf_ball_diameter',
        'yardsPerPixel': round(yards_per_pixel, 7),
        'ballDiameterPx': round(median_diameter_px, 2),
        'confidence': round(confidence, 3),
        'notes': 'Scale is inferred from detected ball size. Perspective, blur, and compression make this lower confidence.',
    }


def _calibration(
    metadata: Dict[str, object],
    ball_frames: List[Dict[str, object]],
    allow_ball_size_estimate: bool,
) -> Dict[str, object]:
    metadata_calibration = _calibration_from_metadata(metadata)
    if metadata_calibration:
        return metadata_calibration
    if allow_ball_size_estimate:
        return _calibration_from_ball_size(ball_frames)
    return {
        'status': 'pixel_only',
        'method': 'none',
        'yardsPerPixel': None,
        'confidence': 0,
        'notes': 'No validated ball flight or physical scene calibration was available, so mph and yards stay unavailable.',
    }


def _mph_from_px_per_second(speed_px_per_second: Optional[float], yards_per_pixel: Optional[float]) -> Optional[float]:
    if speed_px_per_second is None or yards_per_pixel is None:
        return None
    return speed_px_per_second * yards_per_pixel * YARDS_PER_SECOND_TO_MPH


def _distance_yards(distance_px: object, yards_per_pixel: Optional[float]) -> Optional[float]:
    value = _safe_float(distance_px)
    if value is None or yards_per_pixel is None:
        return None
    return value * yards_per_pixel


def _direction_degrees(launch_direction: object) -> Optional[float]:
    if launch_direction == 'right':
        return 6.0
    if launch_direction == 'left':
        return -6.0
    if launch_direction == 'straight':
        return 0.0
    return None


def _actual_shot_shape_spin_axis_proxy(actual_shot_shape: object) -> str:
    if actual_shot_shape == 'fade':
        return 'right_tilt_proxy'
    if actual_shot_shape == 'draw':
        return 'left_tilt_proxy'
    if actual_shot_shape == 'straight':
        return 'neutral_proxy'
    return 'unknown'


def _attack_angle_proxy(
    tracking_frames: List[Dict[str, object]],
    metadata: Dict[str, object],
    impact_ms: Optional[int],
) -> Dict[str, object]:
    width = int(metadata.get('width') or 0)
    height = int(metadata.get('height') or 0)
    if width <= 0 or height <= 0:
        return {'attackAngleDegrees': None, 'attackDirection': 'unknown', 'confidence': 0}

    start_ms = impact_ms - 420 if impact_ms is not None else None
    end_ms = impact_ms + 120 if impact_ms is not None else None
    segments = _speed_segments(tracking_frames, 'clubHead', width, height, start_ms, end_ms)
    if not segments:
        return {'attackAngleDegrees': None, 'attackDirection': 'unknown', 'confidence': 0}

    segment = max(segments, key=lambda item: float(item['speedPxPerSec']))
    dx_px = abs(float(segment['deltaXPx']))
    dy_px = float(segment['deltaYPx'])
    horizontal_scale = max(dx_px, width * 0.08, 1)
    # Positive means the club head is moving upward on the image at impact.
    attack_angle = _clamp(degrees(atan2(-dy_px, horizontal_scale)), -12, 12)
    if attack_angle > 2:
        direction = 'up'
    elif attack_angle < -2:
        direction = 'down'
    else:
        direction = 'level'

    return {
        'attackAngleDegrees': round(attack_angle, 2),
        'attackDirection': direction,
        'confidence': round(_clamp(float(segment['confidence']) * 0.45, 0, 0.42), 3),
        'evidence': {
            'startTimestampMs': segment['startTimestampMs'],
            'endTimestampMs': segment['endTimestampMs'],
            'deltaXPx': round(float(segment['deltaXPx']), 2),
            'deltaYPx': round(float(segment['deltaYPx']), 2),
        },
    }


def _interpretation(
    metrics: Dict[str, object],
    data_quality: Dict[str, object],
    ball_flight_summary: Dict[str, object],
) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    if data_quality.get('requiresCalibration'):
        items.append({
            'id': 'calibration-required',
            'severity': 'medium',
            'text': 'Use pixel-speed proxies for comparison only until a real-world scale calibration is available.',
        })

    smash_factor = _safe_float(metrics.get('smashFactor') or metrics.get('smashFactorProxy'))
    if smash_factor is not None:
        if smash_factor >= 1.45:
            text = 'Energy transfer looks strong from the available speed proxy.'
            severity = 'low'
        elif smash_factor >= 1.33:
            text = 'Energy transfer is workable, but center contact and delivered loft are worth checking.'
            severity = 'medium'
        else:
            text = 'Energy transfer looks weak; prioritize strike location, delivered loft, and face/path control.'
            severity = 'high'
        items.append({'id': 'smash-factor', 'severity': severity, 'text': text})

    launch_direction = ball_flight_summary.get('launchDirection')
    actual_shot_shape = ball_flight_summary.get('actualShotShape')
    if launch_direction and actual_shot_shape and actual_shot_shape != 'unknown':
        items.append({
            'id': 'start-and-curve',
            'severity': 'medium' if actual_shot_shape != 'straight' or launch_direction != 'straight' else 'low',
            'text': f'Ball starts {launch_direction} with an actual {actual_shot_shape} curve; interpret this together with face-to-path and club-path proxies.',
        })

    missing_metrics = data_quality.get('missingMetrics')
    if isinstance(missing_metrics, list) and missing_metrics:
        items.append({
            'id': 'not-measured',
            'severity': 'low',
            'text': 'Spin rate, true carry, total distance, and landing angle need radar, calibrated multi-camera capture, or full-flight tracking.',
        })

    return items


def estimate_launch_monitor_metrics(
    metadata: Dict[str, object],
    tracking_frames: List[Dict[str, object]],
    tracking_summary: Dict[str, object],
    ball_tracking_frames: List[Dict[str, object]],
    ball_flight_summary: Dict[str, object],
    phases: Optional[Dict[str, object]] = None,
    club_face_estimate: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    width = int(metadata.get('width') or 0)
    height = int(metadata.get('height') or 0)
    phases = phases or {}
    club_face_estimate = club_face_estimate or {}
    impact_ms = _safe_int(phases.get('impact') or tracking_summary.get('estimatedImpactMs'))
    has_valid_ball_flight = ball_flight_summary.get('status') == 'tracked' and float(ball_flight_summary.get('confidence') or 0) >= 0.45
    calibration = _calibration(metadata, ball_tracking_frames, has_valid_ball_flight)
    yards_per_pixel = _safe_float(calibration.get('yardsPerPixel'))
    calibration_confidence = float(calibration.get('confidence') or 0)

    club_segment = _max_speed_segment(
        tracking_frames,
        'clubHead',
        width,
        height,
        impact_ms - 650 if impact_ms is not None else None,
        impact_ms + 120 if impact_ms is not None else None,
    ) if width > 0 and height > 0 else None
    ball_segment = _max_speed_segment(
        ball_tracking_frames,
        'ball',
        width,
        height,
        impact_ms if impact_ms is not None else None,
        impact_ms + 900 if impact_ms is not None else None,
    ) if has_valid_ball_flight and width > 0 and height > 0 else None

    club_speed_px = (
        float(club_segment['speedPxPerSec'])
        if club_segment
        else _safe_float(tracking_summary.get('maxClubHeadSpeedPxPerSec'))
    )
    ball_speed_px = (
        float(ball_segment['speedPxPerSec'])
        if ball_segment
        else (_safe_float(ball_flight_summary.get('maxBallSpeedPxPerSec')) if has_valid_ball_flight else None)
    )
    club_speed_mph = _mph_from_px_per_second(club_speed_px, yards_per_pixel)
    ball_speed_mph = _mph_from_px_per_second(ball_speed_px, yards_per_pixel)
    smash_factor = (
        ball_speed_mph / club_speed_mph
        if ball_speed_mph is not None and club_speed_mph is not None and club_speed_mph > 0
        else None
    )
    smash_factor_proxy = (
        ball_speed_px / club_speed_px
        if ball_speed_px is not None and club_speed_px is not None and club_speed_px > 0
        else None
    )
    attack = _attack_angle_proxy(tracking_frames, metadata, impact_ms)
    launch_angle = _safe_float(ball_flight_summary.get('trajectoryAngleDegrees'))
    launch_direction = ball_flight_summary.get('launchDirection') if has_valid_ball_flight else None
    actual_shot_shape = ball_flight_summary.get('actualShotShape') if has_valid_ball_flight else 'unknown'

    metrics = {
        'clubSpeedMph': _safe_round(club_speed_mph, 1),
        'clubSpeedPxPerSec': _safe_round(club_speed_px),
        'ballSpeedMph': _safe_round(ball_speed_mph, 1),
        'ballSpeedPxPerSec': _safe_round(ball_speed_px),
        'smashFactor': _safe_round(smash_factor, 2),
        'smashFactorProxy': _safe_round(smash_factor_proxy, 2),
        'launchAngleDegrees': _safe_round(launch_angle),
        'launchDirection': launch_direction or 'unknown',
        'launchDirectionDegrees': _safe_round(_direction_degrees(launch_direction)),
        'attackAngleDegrees': attack.get('attackAngleDegrees'),
        'attackDirection': attack.get('attackDirection'),
        'clubPathDegrees': club_face_estimate.get('clubPathDegrees'),
        'clubPathProxy': club_face_estimate.get('clubPathProxy') or 'unknown',
        'faceAngleDegrees': club_face_estimate.get('estimatedDegreesToTarget'),
        'faceToPathDegrees': club_face_estimate.get('estimatedDegreesToPath'),
        'faceToTarget': club_face_estimate.get('faceToTarget') or 'unknown',
        'faceToPath': club_face_estimate.get('faceToPath') or 'unknown',
        'actualShotShape': actual_shot_shape,
        'spinRateRpm': None,
        'spinAxisDegrees': None,
        'spinAxisProxy': _actual_shot_shape_spin_axis_proxy(actual_shot_shape),
        'carryYards': None,
        'visibleBallTravelYards': _safe_round(
            _distance_yards(ball_flight_summary.get('ballPathLengthPx') if has_valid_ball_flight else None, yards_per_pixel),
            1,
        ),
        'visibleCarryYards': _safe_round(
            _distance_yards(ball_flight_summary.get('carryDistancePx') if has_valid_ball_flight else None, yards_per_pixel),
            1,
        ),
        'apexHeightYards': _safe_round(
            _distance_yards(ball_flight_summary.get('apexHeightPx') if has_valid_ball_flight else None, yards_per_pixel),
            1,
        ),
        'curveYards': _safe_round(
            _distance_yards(ball_flight_summary.get('curvaturePx') if has_valid_ball_flight else None, yards_per_pixel),
            1,
        ),
        'landingAngleDegrees': None,
        'totalDistanceYards': None,
    }

    club_speed_confidence = (
        _clamp(float(club_segment.get('confidence') or 0) * max(calibration_confidence, 0.2), 0, 0.72)
        if club_segment
        else 0
    )
    ball_speed_confidence = (
        _clamp(float(ball_segment.get('confidence') or 0) * max(calibration_confidence, 0.2), 0, 0.72)
        if ball_segment
        else 0
    )
    ball_summary_confidence = _clamp(float(ball_flight_summary.get('confidence') or 0), 0, 1) if has_valid_ball_flight else 0
    overall_confidence = _clamp(
        club_speed_confidence * 0.28
        + ball_speed_confidence * 0.28
        + ball_summary_confidence * 0.24
        + calibration_confidence * 0.12
        + float(attack.get('confidence') or 0) * 0.08,
        0,
        0.82,
    )
    missing_metrics = [
        'spinRateRpm',
        'spinAxisDegrees',
        'carryYards',
        'landingAngleDegrees',
        'totalDistanceYards',
    ]
    if club_speed_mph is None:
        missing_metrics.append('clubSpeedMph')
    if ball_speed_mph is None:
        missing_metrics.append('ballSpeedMph')
    if not has_valid_ball_flight:
        missing_metrics.extend([
            'launchDirection',
            'actualShotShape',
            'ballSpeedPxPerSec',
            'smashFactor',
            'smashFactorProxy',
            'visibleBallTravelYards',
            'visibleCarryYards',
            'apexHeightYards',
            'curveYards',
        ])
    missing_metrics = list(dict.fromkeys(missing_metrics))

    if club_speed_px and ball_speed_px:
        status = 'estimated' if overall_confidence >= 0.32 else 'partial'
    elif club_speed_px or ball_speed_px:
        status = 'partial'
    else:
        status = 'insufficient_evidence'

    data_quality = {
        'confidence': round(overall_confidence, 3),
        'clubSpeedConfidence': round(club_speed_confidence, 3),
        'ballSpeedConfidence': round(ball_speed_confidence, 3),
        'launchConfidence': round(ball_summary_confidence, 3),
        'attackAngleConfidence': attack.get('confidence') or 0,
        'calibrationConfidence': round(calibration_confidence, 3),
        'requiresCalibration': yards_per_pixel is None or calibration.get('status') != 'calibrated',
        'missingMetrics': missing_metrics,
        'clubSpeedEvidence': club_segment,
        'ballSpeedEvidence': ball_segment,
        'attackAngleEvidence': attack.get('evidence'),
    }

    return {
        'status': status,
        'measurementSystem': 'video_proxy_not_launch_monitor',
        'modelVersion': 'launch-monitor-proxy-v1',
        'calibration': calibration,
        'metrics': metrics,
        'dataQuality': data_quality,
        'interpretation': _interpretation(metrics, data_quality, ball_flight_summary),
        'definitions': {
            'clubSpeed': 'Club-head speed near impact. Video proxy uses club-head pixel motion near impact.',
            'ballSpeed': 'Initial ball speed after separation. Video proxy uses early post-impact ball motion.',
            'smashFactor': 'Ball speed divided by club speed; useful as strike-efficiency evidence when speeds share calibration.',
            'launchAngle': 'Vertical start angle of the ball. Current value is projected video trajectory angle.',
            'launchDirection': 'Horizontal start direction bucket from the post-impact ball trace.',
            'attackAngle': 'Up/down club-head movement at impact. Current value is a screen-space proxy.',
            'spinRate': 'Not measurable from the current single-camera video pipeline.',
            'carry': 'Not true full carry unless future capture sees and calibrates the full flight.',
        },
        'notes': (
            'This layer mirrors launch-monitor fields for coaching context, but radar-grade TrackMan metrics '
            'require calibrated 3D club/ball tracking. The app should treat mph and yards as estimated unless '
            'calibration.status is calibrated and confidence is high.'
        ),
    }
