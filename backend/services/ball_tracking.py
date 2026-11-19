from math import atan2, degrees, sqrt
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


BallFrame = Dict[str, object]
Point = Dict[str, object]

MAX_BALL_TRACKING_FRAMES = 90
BALL_FLIGHT_TRACK_MS = 3500
MIN_BALL_CONTOUR_AREA = 6
MAX_BALL_CONTOUR_AREA_RATIO = 0.0025
MIN_VALID_BALL_FRAMES = 4
MIN_POST_IMPACT_BALL_FRAMES = 3
MIN_AVERAGE_BALL_CONFIDENCE = 0.38
BALL_NEAR_IMPACT_WINDOW_MS = 650
BALL_VALIDATION_WINDOW_MS = 1100


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _pixel_point(x: float, y: float, width: int, height: int, confidence: float, source: str) -> Point:
    return {
        'x': round(_clamp(x / max(width, 1), 0, 1), 5),
        'y': round(_clamp(y / max(height, 1), 0, 1), 5),
        'confidence': round(_clamp(confidence, 0, 1), 3),
        'source': source,
    }


def _normalized_to_pixel(point: Point, width: int, height: int) -> Tuple[float, float]:
    return float(point['x']) * width, float(point['y']) * height


def _point_distance_px(a: Point, b: Point, width: int, height: int) -> float:
    ax, ay = _normalized_to_pixel(a, width, height)
    bx, by = _normalized_to_pixel(b, width, height)
    return sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def _candidate_mask(frame: np.ndarray, previous_frame: Optional[np.ndarray]) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    bright = cv2.inRange(gray, 185, 255)
    white = cv2.inRange(saturation, 0, 90) & cv2.inRange(value, 135, 255)
    mask = cv2.bitwise_or(bright, white)

    if previous_frame is not None and previous_frame.shape == frame.shape:
        previous_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
        motion = cv2.absdiff(gray, previous_gray)
        motion_mask = cv2.threshold(motion, 18, 255, cv2.THRESH_BINARY)[1]
        mask = cv2.bitwise_and(mask, cv2.dilate(motion_mask, np.ones((3, 3), dtype=np.uint8), iterations=1))

    mask = cv2.medianBlur(mask, 3)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8))


def _detect_ball_candidate(
    frame: np.ndarray,
    previous_frame: Optional[np.ndarray],
    previous_ball: Optional[Point],
) -> Optional[Point]:
    if frame.size == 0:
        return None

    height, width = frame.shape[:2]
    mask = _candidate_mask(frame, previous_frame)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    max_area = max(MIN_BALL_CONTOUR_AREA + 1, width * height * MAX_BALL_CONTOUR_AREA_RATIO)
    best: Optional[Point] = None
    best_score = 0.0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_BALL_CONTOUR_AREA or area > max_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        aspect = w / max(h, 1)
        if aspect < 0.35 or aspect > 3.2:
            continue

        moments = cv2.moments(contour)
        if not moments['m00']:
            continue

        cx = moments['m10'] / moments['m00']
        cy = moments['m01'] / moments['m00']
        radius = sqrt(area / np.pi)
        fill_ratio = area / max(w * h, 1)
        compactness = _clamp(fill_ratio, 0, 1)
        size_score = 1 - _clamp(abs(radius - 4.5) / 12, 0, 1)
        lower_frame_prior = 1 - _clamp((height * 0.18 - cy) / max(height * 0.18, 1), 0, 1)
        continuity_score = 0.5

        if previous_ball:
            px, py = _normalized_to_pixel(previous_ball, width, height)
            distance = sqrt((cx - px) ** 2 + (cy - py) ** 2)
            continuity_score = 1 - _clamp(distance / max(width, height) * 2.2, 0, 1)

        score = 0.28 * compactness + 0.22 * size_score + 0.18 * lower_frame_prior + 0.32 * continuity_score
        if score <= best_score:
            continue

        best_score = score
        best = _pixel_point(cx, cy, width, height, 0.2 + score * 0.75, 'vision_motion')
        best['radiusPx'] = round(radius, 2)
        best['diameterPx'] = round(radius * 2, 2)
        best['areaPx'] = round(area, 2)
        best['aspectRatio'] = round(aspect, 3)
        best['fillRatio'] = round(fill_ratio, 3)
        best['compactness'] = round(compactness, 3)
        best['detectionScore'] = round(score, 3)

    return best


def _visible_candidates(frames: List[BallFrame], min_confidence: float = 0.22) -> List[BallFrame]:
    return [
        frame_data
        for frame_data in frames
        if isinstance(frame_data.get('ball'), dict)
        and float(frame_data['ball'].get('confidence') or 0) >= min_confidence
    ]


def _ball_diameter_values(visible: List[BallFrame]) -> List[float]:
    values = []
    for frame_data in visible:
        ball = frame_data.get('ball')
        if not isinstance(ball, dict):
            continue
        diameter = ball.get('diameterPx')
        radius = ball.get('radiusPx')
        try:
            if diameter is None and radius is not None:
                diameter = float(radius) * 2
            if diameter is not None:
                values.append(float(diameter))
        except (TypeError, ValueError):
            continue
    return values


def _average_confidence(visible: List[BallFrame]) -> float:
    if not visible:
        return 0
    return sum(float(frame_data['ball'].get('confidence') or 0) for frame_data in visible) / len(visible)


def _net_displacement_px(visible: List[BallFrame], width: int, height: int) -> float:
    if len(visible) < 2:
        return 0
    first_x, first_y = _normalized_to_pixel(visible[0]['ball'], width, height)
    last_x, last_y = _normalized_to_pixel(visible[-1]['ball'], width, height)
    return sqrt((last_x - first_x) ** 2 + (last_y - first_y) ** 2)


def _step_distances_px(visible: List[BallFrame], width: int, height: int) -> List[float]:
    distances = []
    previous = None
    for frame_data in visible:
        if previous is not None:
            distances.append(_point_distance_px(previous['ball'], frame_data['ball'], width, height))
        previous = frame_data
    return distances


def _validate_ball_presence(
    frames: List[BallFrame],
    width: int,
    height: int,
    impact_ms: int,
) -> Dict[str, object]:
    visible = _visible_candidates(frames)
    candidate_count = len(visible)
    reasons: List[str] = []

    if candidate_count < MIN_VALID_BALL_FRAMES:
        reasons.append('No validated golf ball track was found near impact.')

    near_impact = [
        frame_data
        for frame_data in visible
        if impact_ms - 180 <= int(frame_data.get('timestampMs') or 0) <= impact_ms + BALL_NEAR_IMPACT_WINDOW_MS
    ]
    if len(near_impact) < 1:
        reasons.append('A ball candidate was not visible near the strike window.')

    post_impact = [
        frame_data
        for frame_data in visible
        if impact_ms <= int(frame_data.get('timestampMs') or 0) <= impact_ms + BALL_VALIDATION_WINDOW_MS
    ]
    if len(post_impact) < MIN_POST_IMPACT_BALL_FRAMES:
        reasons.append('Post-impact ball motion was not continuous enough to estimate flight.')

    average_confidence = _average_confidence(visible)
    if average_confidence < MIN_AVERAGE_BALL_CONFIDENCE:
        reasons.append('Ball candidate confidence was too low for actual ball-flight metrics.')

    first_ball = visible[0]['ball'] if visible else None
    if isinstance(first_ball, dict):
        first_x, first_y = _normalized_to_pixel(first_ball, width, height)
        if first_x < width * 0.04 or first_x > width * 0.96 or first_y < height * 0.12 or first_y > height * 0.96:
            reasons.append('The first ball candidate was outside the expected strike-zone area.')

    diameters = _ball_diameter_values(visible)
    median_diameter = None
    diameter_consistency = None
    if diameters:
        ordered = sorted(diameters)
        median_diameter = ordered[len(ordered) // 2]
        min_diameter = min(diameters)
        max_diameter = max(diameters)
        diameter_consistency = max_diameter / max(min_diameter, 1)
        if median_diameter < 2 or median_diameter > min(width, height) * 0.09:
            reasons.append('Ball candidate size was outside the expected golf-ball range.')
        if diameter_consistency > 3.0:
            reasons.append('Ball candidate size changed too much across frames.')
    else:
        reasons.append('Ball candidate size was not available for validation.')

    net_displacement = _net_displacement_px(visible, width, height)
    if net_displacement < max(width, height) * 0.035:
        reasons.append('Ball candidate did not move far enough after impact.')

    step_distances = _step_distances_px(visible, width, height)
    if step_distances:
        outlier_steps = [distance for distance in step_distances if distance > max(width, height) * 0.42]
        if len(outlier_steps) > max(1, len(step_distances) // 3):
            reasons.append('Ball candidate path had large discontinuities.')

    confidence = _clamp(
        0.24 * min(candidate_count / 8, 1)
        + 0.24 * min(len(post_impact) / 5, 1)
        + 0.26 * _clamp(average_confidence, 0, 1)
        + 0.14 * min(net_displacement / max(width * 0.16, 1), 1)
        + (0.12 if diameters else 0),
        0,
        0.92,
    )

    is_valid = not reasons
    return {
        'isValid': is_valid,
        'status': 'tracked' if is_valid else 'no_ball_detected',
        'visibleFrames': visible if is_valid else [],
        'candidateFrameCount': candidate_count,
        'nearImpactFrameCount': len(near_impact),
        'postImpactFrameCount': len(post_impact),
        'averageCandidateConfidence': round(average_confidence, 3),
        'presenceConfidence': round(confidence if is_valid else 0, 3),
        'netDisplacementPx': round(net_displacement, 2),
        'medianDiameterPx': round(median_diameter, 2) if median_diameter is not None else None,
        'diameterConsistencyRatio': round(diameter_consistency, 3) if diameter_consistency is not None else None,
        'reasons': reasons,
    }


def _path_metrics(
    frames: List[BallFrame],
    width: int,
    height: int,
) -> Dict[str, object]:
    visible = _visible_candidates(frames)
    if len(visible) < 2:
        return {
            'ballFrameCount': len(visible),
            'averageBallConfidence': round(
                sum(float(frame_data['ball'].get('confidence') or 0) for frame_data in visible) / len(visible),
                3,
            ) if visible else 0,
        }

    first = visible[0]
    last = visible[-1]
    first_point = first['ball']
    last_point = last['ball']
    first_x, first_y = _normalized_to_pixel(first_point, width, height)
    last_x, last_y = _normalized_to_pixel(last_point, width, height)
    dx = last_x - first_x
    dy = last_y - first_y
    trajectory_angle = degrees(atan2(-dy, dx))
    launch_direction = 'straight'
    if dx > width * 0.035:
        launch_direction = 'right'
    elif dx < -width * 0.035:
        launch_direction = 'left'

    path_length = 0.0
    max_speed = 0.0
    previous = None
    for frame_data in visible:
        if previous is not None:
            delta_ms = int(frame_data['timestampMs']) - int(previous['timestampMs'])
            if delta_ms > 0:
                distance = _point_distance_px(previous['ball'], frame_data['ball'], width, height)
                path_length += distance
                max_speed = max(max_speed, distance / (delta_ms / 1000))
        previous = frame_data

    y_values = [_normalized_to_pixel(frame_data['ball'], width, height)[1] for frame_data in visible]
    x_values = [_normalized_to_pixel(frame_data['ball'], width, height)[0] for frame_data in visible]
    curvature_px = 0.0
    if len(visible) >= 3:
        midpoint = visible[len(visible) // 2]['ball']
        mid_x, _ = _normalized_to_pixel(midpoint, width, height)
        expected_mid_x = (first_x + last_x) / 2
        curvature_px = mid_x - expected_mid_x

    actual_shot_shape = 'unknown'
    if abs(curvature_px) > width * 0.025:
        actual_shot_shape = 'fade' if curvature_px > 0 else 'draw'
    elif len(visible) >= 3:
        actual_shot_shape = 'straight'

    average_confidence = sum(float(frame_data['ball'].get('confidence') or 0) for frame_data in visible) / len(visible)
    confidence = _clamp(0.25 + min(len(visible) / 12, 0.4) + average_confidence * 0.35, 0, 0.92)

    return {
        'ballFrameCount': len(visible),
        'firstBallMs': int(first['timestampMs']),
        'lastBallMs': int(last['timestampMs']),
        'averageBallConfidence': round(average_confidence, 3),
        'launchDirection': launch_direction,
        'trajectoryAngleDegrees': round(trajectory_angle, 2),
        'apexHeightPx': round(max(y_values) - min(y_values), 2),
        'carryDistancePx': round(max(x_values) - min(x_values), 2),
        'ballPathLengthPx': round(path_length, 2),
        'maxBallSpeedPxPerSec': round(max_speed, 2),
        'curvaturePx': round(curvature_px, 2),
        'actualShotShape': actual_shot_shape,
        'confidence': round(confidence, 3),
    }


def summarize_ball_tracking(
    frames: List[BallFrame],
    metadata: Dict[str, object],
    phases: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    width = int(metadata.get('width') or 0)
    height = int(metadata.get('height') or 0)
    if not frames or width <= 0 or height <= 0:
        return {
            'status': 'no_ball_detected',
            'framesTracked': 0,
            'ballFrameCount': 0,
            'ballCandidateFrameCount': 0,
            'averageBallConfidence': 0,
            'ballPresenceConfidence': 0,
            'launchDirection': None,
            'actualShotShape': 'unknown',
            'confidence': 0,
            'quality': {
                'ballFrameRatio': 0,
                'candidateFrameRatio': 0,
                'noBallDetected': True,
                'needsLongerVideo': True,
                'needsRetake': True,
                'retakeReasons': ['No ball tracking frames were available.'],
            },
            'notes': 'No ball tracking frames were available.',
        }

    tracking_start_ms = int(frames[0].get('timestampMs') or 0)
    tracking_end_ms = int(frames[-1].get('timestampMs') or tracking_start_ms)
    impact_ms = int(phases.get('impact') or tracking_start_ms) if phases else tracking_start_ms
    validation = _validate_ball_presence(frames, width, height, impact_ms)
    if not validation['isValid']:
        retake_reasons = list(validation.get('reasons') or ['No validated golf ball track was found near impact.'])
        needs_longer_video = tracking_end_ms - impact_ms < BALL_FLIGHT_TRACK_MS - 250
        if needs_longer_video:
            retake_reasons.append('Keep recording longer after impact so the ball flight can be tracked.')
        return {
            'status': 'no_ball_detected',
            'framesTracked': len(frames),
            'ballFrameCount': 0,
            'ballCandidateFrameCount': int(validation.get('candidateFrameCount') or 0),
            'nearImpactBallFrameCount': int(validation.get('nearImpactFrameCount') or 0),
            'postImpactBallFrameCount': int(validation.get('postImpactFrameCount') or 0),
            'averageBallConfidence': 0,
            'averageCandidateBallConfidence': validation.get('averageCandidateConfidence') or 0,
            'ballPresenceConfidence': 0,
            'launchDirection': None,
            'trajectoryAngleDegrees': None,
            'apexHeightPx': None,
            'carryDistancePx': None,
            'ballPathLengthPx': None,
            'maxBallSpeedPxPerSec': None,
            'curvaturePx': None,
            'actualShotShape': 'unknown',
            'confidence': 0,
            'trackingStartMs': tracking_start_ms,
            'trackingEndMs': tracking_end_ms,
            'trackingMethod': 'bright_motion_contours_after_impact_with_ball_presence_gate',
            'validation': {key: value for key, value in validation.items() if key != 'visibleFrames'},
            'quality': {
                'ballFrameRatio': 0,
                'candidateFrameRatio': round((int(validation.get('candidateFrameCount') or 0)) / len(frames), 3),
                'noBallDetected': True,
                'needsLongerVideo': needs_longer_video,
                'needsRetake': True,
                'retakeReasons': retake_reasons,
            },
            'notes': (
                'No validated golf ball was detected, so actual ball flight, launch direction, and actual shot shape '
                'were intentionally left unavailable.'
            ),
        }

    validated_frames = validation['visibleFrames']
    metrics = _path_metrics(validated_frames, width, height)
    ball_count = int(metrics.get('ballFrameCount') or 0)
    ball_ratio = ball_count / len(frames)
    needs_longer_video = tracking_end_ms - impact_ms < BALL_FLIGHT_TRACK_MS - 250
    retake_reasons: List[str] = []
    if ball_count < 2:
        retake_reasons.append('The ball was not visible long enough after impact to estimate flight.')
    if needs_longer_video:
        retake_reasons.append('Keep recording longer after impact so the ball flight can be tracked.')

    confidence = float(metrics.get('confidence') or 0)
    return {
        'status': 'tracked',
        'framesTracked': len(frames),
        **metrics,
        'ballCandidateFrameCount': int(validation.get('candidateFrameCount') or 0),
        'nearImpactBallFrameCount': int(validation.get('nearImpactFrameCount') or 0),
        'postImpactBallFrameCount': int(validation.get('postImpactFrameCount') or 0),
        'ballPresenceConfidence': validation.get('presenceConfidence') or 0,
        'trackingStartMs': tracking_start_ms,
        'trackingEndMs': tracking_end_ms,
        'trackingMethod': 'bright_motion_contours_after_impact_with_ball_presence_gate',
        'validation': {key: value for key, value in validation.items() if key != 'visibleFrames'},
        'quality': {
            'ballFrameRatio': round(ball_ratio, 3),
            'candidateFrameRatio': round((int(validation.get('candidateFrameCount') or 0)) / len(frames), 3),
            'noBallDetected': False,
            'needsLongerVideo': needs_longer_video,
            'needsRetake': confidence < 0.45 or ball_count < 2,
            'retakeReasons': retake_reasons,
        },
        'notes': (
            'Ball tracking uses bright/motion contour candidates after impact. It is evidence for '
            'launch direction and rough trajectory only; launch-monitor calibration is still required.'
        ),
    }


def estimates_from_ball_summary(summary: Dict[str, object]) -> Dict[str, object]:
    confidence = float(summary.get('confidence') or 0)
    has_valid_ball = summary.get('status') == 'tracked' and confidence >= 0.45
    launch_direction = summary.get('launchDirection') if has_valid_ball else None
    return {
        'launchDirection': launch_direction,
        'actualShotShape': summary.get('actualShotShape') if has_valid_ball else 'unknown',
        'spinTendency': 'unknown',
        'confidence': round(confidence, 3),
    }


def extract_ball_tracking(
    video_path: str,
    metadata: Dict[str, object],
    phases: Optional[Dict[str, object]] = None,
    window: Optional[Dict[str, object]] = None,
) -> Tuple[List[BallFrame], Dict[str, object]]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], summarize_ball_tracking([], metadata, phases)

    frames: List[BallFrame] = []
    phases = phases or {}
    window = window or {}
    previous_frame = None
    previous_ball = None

    try:
        fps = float(metadata.get('fps') or cap.get(cv2.CAP_PROP_FPS) or 0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if not fps or not frame_count:
            return [], summarize_ball_tracking([], metadata, phases)

        duration_ms = int(metadata.get('durationMs') or ((frame_count / fps) * 1000))
        impact_ms = int(phases.get('impact') or window.get('detectedEndMs') or window.get('endMs') or 0)
        start_ms = max(0, impact_ms - 150)
        end_ms = min(duration_ms, max(int(window.get('endMs') or 0), impact_ms + BALL_FLIGHT_TRACK_MS))
        start_frame = max(0, int(start_ms / 1000 * fps))
        end_frame = min(frame_count - 1, int(end_ms / 1000 * fps))
        step = max(1, int((end_frame - start_frame + 1) / MAX_BALL_TRACKING_FRAMES))

        for frame_index in range(start_frame, end_frame + 1, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                continue

            timestamp_ms = int((frame_index / fps) * 1000)
            ball = _detect_ball_candidate(frame, previous_frame, previous_ball)
            if ball:
                previous_ball = ball
            previous_frame = frame
            frames.append({
                'frameIndex': frame_index,
                'timestampMs': timestamp_ms,
                'ball': ball,
            })
    finally:
        cap.release()

    return frames, summarize_ball_tracking(frames, metadata, phases)
