import base64
import json
import urllib.error
import urllib.request
from datetime import datetime
from math import sqrt
from statistics import median
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from config import Settings, settings


VALID_BALL_CONFIDENCE = 0.45
MIN_POINT_CONFIDENCE = 0.2
LLM_CONFIDENCE_TRIGGER = 0.72

IMPACT_VISION_PROMPT = (
    'You are reviewing only the strike/impact area of a golf swing video. '
    'Use the provided impact-frame crops and the structured tracking evidence. '
    'Do not infer full ball flight or invent measurements. If the ball, club face, '
    'or contact point is not clearly visible, return unknown. Classify strike location '
    'only as center, thin, fat, heel, toe, or unknown.'
)


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


def _clamp(value: float, minimum: float = 0, maximum: float = 1) -> float:
    return min(max(value, minimum), maximum)


def _point_to_pixel(point: Dict[str, object], width: int, height: int) -> Tuple[float, float]:
    return float(point['x']) * width, float(point['y']) * height


def _has_valid_ball(ball_flight_summary: Dict[str, object]) -> bool:
    return (
        ball_flight_summary.get('status') == 'tracked'
        and (_safe_float(ball_flight_summary.get('confidence')) or 0) >= VALID_BALL_CONFIDENCE
    )


def _visible_samples(
    frames: List[Dict[str, object]],
    point_key: str,
    min_confidence: float = MIN_POINT_CONFIDENCE,
) -> List[Dict[str, object]]:
    samples: List[Dict[str, object]] = []
    for frame_data in frames:
        point = frame_data.get(point_key)
        timestamp_ms = _safe_int(frame_data.get('timestampMs'))
        confidence = _safe_float(point.get('confidence')) if isinstance(point, dict) else None
        if not isinstance(point, dict) or timestamp_ms is None or confidence is None or confidence < min_confidence:
            continue
        samples.append({
            'frameIndex': _safe_int(frame_data.get('frameIndex')),
            'timestampMs': timestamp_ms,
            'point': point,
            'confidence': confidence,
        })
    return sorted(samples, key=lambda sample: int(sample['timestampMs']))


def _nearest_sample(samples: List[Dict[str, object]], timestamp_ms: Optional[int]) -> Optional[Dict[str, object]]:
    if not samples:
        return None
    if timestamp_ms is None:
        return samples[0]
    return min(samples, key=lambda sample: abs(int(sample['timestampMs']) - timestamp_ms))


def _impact_timestamp_ms(
    phases: Dict[str, object],
    tracking_summary: Dict[str, object],
    ball_flight_summary: Dict[str, object],
) -> Optional[int]:
    for candidate in (
        phases.get('impact'),
        tracking_summary.get('estimatedImpactMs'),
        ball_flight_summary.get('firstBallMs'),
    ):
        timestamp = _safe_int(candidate)
        if timestamp is not None:
            return timestamp
    return None


def _ball_diameter_px(ball_samples: List[Dict[str, object]], metadata: Dict[str, object]) -> Optional[float]:
    values: List[float] = []
    for sample in ball_samples:
        point = sample.get('point')
        if not isinstance(point, dict):
            continue
        diameter = _safe_float(point.get('diameterPx'))
        radius = _safe_float(point.get('radiusPx'))
        if diameter is None and radius is not None:
            diameter = radius * 2
        if diameter is not None and diameter >= 2:
            values.append(diameter)
    if values:
        return median(values)

    width = _safe_float(metadata.get('width')) or 0
    height = _safe_float(metadata.get('height')) or 0
    if width > 0 and height > 0:
        return max(min(width, height) * 0.012, 4)
    return None


def _point_payload(sample: Optional[Dict[str, object]], width: int, height: int, source: str) -> Optional[Dict[str, object]]:
    if not sample:
        return None
    point = sample.get('point')
    if not isinstance(point, dict):
        return None
    x_px, y_px = _point_to_pixel(point, width, height)
    return {
        'x': point.get('x'),
        'y': point.get('y'),
        'xPx': round(x_px, 2),
        'yPx': round(y_px, 2),
        'confidence': _safe_round(_safe_float(point.get('confidence')) or sample.get('confidence'), 3),
        'source': point.get('source') or source,
        'frameIndex': sample.get('frameIndex'),
        'timestampMs': sample.get('timestampMs'),
    }


def _low_point_estimate(
    tracking_samples: List[Dict[str, object]],
    impact_ms: Optional[int],
    ball_sample: Optional[Dict[str, object]],
    width: int,
    height: int,
) -> Dict[str, object]:
    if not tracking_samples:
        return {
            'status': 'unavailable',
            'timestampMs': None,
            'frameIndex': None,
            'clubHeadYpx': None,
            'relativeToImpactMs': None,
            'relativeToBallYPx': None,
            'classification': 'unknown',
            'confidence': 0,
        }

    candidates = tracking_samples
    if impact_ms is not None:
        near = [
            sample
            for sample in tracking_samples
            if abs(int(sample['timestampMs']) - impact_ms) <= 650
        ]
        if near:
            candidates = near

    low_sample = max(candidates, key=lambda sample: _point_to_pixel(sample['point'], width, height)[1])
    _, low_y = _point_to_pixel(low_sample['point'], width, height)
    ball_y = None
    if ball_sample:
        _, ball_y = _point_to_pixel(ball_sample['point'], width, height)
    relative_ms = int(low_sample['timestampMs']) - impact_ms if impact_ms is not None else None
    relative_to_ball_y = low_y - ball_y if ball_y is not None else None
    confidence = _clamp(float(low_sample.get('confidence') or 0) * (0.85 if impact_ms is not None else 0.55), 0, 0.8)

    classification = 'unknown'
    if relative_ms is not None:
        if relative_ms < -90:
            classification = 'before_ball_fat_risk'
        elif relative_ms > 220:
            classification = 'after_ball_ball_first_bias'
        else:
            classification = 'near_impact'

    return {
        'status': 'estimated',
        'timestampMs': int(low_sample['timestampMs']),
        'frameIndex': low_sample.get('frameIndex'),
        'clubHeadYpx': round(low_y, 2),
        'relativeToImpactMs': relative_ms,
        'relativeToBallYPx': _safe_round(relative_to_ball_y),
        'classification': classification,
        'confidence': round(confidence, 3),
        'notes': 'Low point is the lowest screen-space club-head sample near impact, not a calibrated 3D turf-contact point.',
    }


def _contact_classification(
    proximity_px: Optional[float],
    vertical_delta_px: Optional[float],
    ball_diameter_px: Optional[float],
    low_point: Dict[str, object],
) -> Dict[str, object]:
    if proximity_px is None or ball_diameter_px is None:
        return {
            'classification': 'unknown',
            'verticalStrike': 'unknown',
            'horizontalStrike': 'unknown',
            'confidence': 0,
            'evidence': ['Club-head/ball proximity was unavailable at impact.'],
        }

    close_threshold = max(ball_diameter_px * 3.25, 28)
    near_threshold = max(ball_diameter_px * 4.75, 42)
    evidence = [
        f'Club-ball proximity is {round(proximity_px, 1)} px.',
        f'Estimated ball diameter is {round(ball_diameter_px, 1)} px.',
    ]
    low_point_classification = str(low_point.get('classification') or 'unknown')
    if low_point_classification != 'unknown':
        evidence.append(f'Low-point proxy is {low_point_classification}.')

    if proximity_px > near_threshold:
        return {
            'classification': 'unknown',
            'verticalStrike': 'unknown',
            'horizontalStrike': 'unknown',
            'confidence': 0.18,
            'evidence': [*evidence, 'Club head was not close enough to the ball point for a reliable strike-location claim.'],
        }

    vertical_strike = 'center_or_unknown'
    classification = 'likely_centered'
    if vertical_delta_px is not None:
        # Positive means the club-head point is lower in the image than the ball.
        if vertical_delta_px < -ball_diameter_px * 1.35:
            vertical_strike = 'thin'
            classification = 'thin'
        elif vertical_delta_px > ball_diameter_px * 2.1:
            vertical_strike = 'fat'
            classification = 'fat'
        else:
            vertical_strike = 'centered_window'
        evidence.append(f'Club-head vertical offset from ball is {round(vertical_delta_px, 1)} px.')

    if classification == 'likely_centered' and low_point_classification == 'before_ball_fat_risk':
        classification = 'fat'
        vertical_strike = 'fat_low_point_before_ball'

    proximity_score = 1 - _clamp(proximity_px / near_threshold, 0, 1)
    vertical_score = (
        1 - _clamp(abs(vertical_delta_px or 0) / max(ball_diameter_px * 3.0, 1), 0, 1)
        if vertical_delta_px is not None
        else 0.35
    )
    confidence = _clamp(0.24 + proximity_score * 0.34 + vertical_score * 0.22 + float(low_point.get('confidence') or 0) * 0.2, 0, 0.76)
    if proximity_px > close_threshold and classification == 'likely_centered':
        classification = 'off_center_unknown'
        confidence = min(confidence, 0.48)

    return {
        'classification': classification,
        'verticalStrike': vertical_strike,
        'horizontalStrike': 'unknown_without_face_visibility',
        'confidence': round(confidence, 3),
        'evidence': evidence,
    }


def _deterministic_impact_analysis(
    metadata: Dict[str, object],
    tracking_frames: List[Dict[str, object]],
    tracking_summary: Dict[str, object],
    ball_tracking_frames: List[Dict[str, object]],
    ball_flight_summary: Dict[str, object],
    phases: Dict[str, object],
    launch_monitor: Dict[str, object],
    club_face_estimate: Dict[str, object],
) -> Dict[str, object]:
    width = int(metadata.get('width') or 0)
    height = int(metadata.get('height') or 0)
    impact_ms = _impact_timestamp_ms(phases, tracking_summary, ball_flight_summary)
    tracking_samples = _visible_samples(tracking_frames, 'clubHead')
    ball_samples = _visible_samples(ball_tracking_frames, 'ball', min_confidence=0.22)
    club_sample = _nearest_sample(tracking_samples, impact_ms)
    ball_sample = _nearest_sample(ball_samples, impact_ms)
    ball_diameter = _ball_diameter_px(ball_samples, metadata)
    club_point = club_sample.get('point') if club_sample else None
    ball_point = ball_sample.get('point') if ball_sample else None

    proximity_px = None
    vertical_delta_px = None
    horizontal_delta_px = None
    if isinstance(club_point, dict) and isinstance(ball_point, dict) and width > 0 and height > 0:
        club_x, club_y = _point_to_pixel(club_point, width, height)
        ball_x, ball_y = _point_to_pixel(ball_point, width, height)
        horizontal_delta_px = club_x - ball_x
        vertical_delta_px = club_y - ball_y
        proximity_px = sqrt(horizontal_delta_px * horizontal_delta_px + vertical_delta_px * vertical_delta_px)

    low_point = _low_point_estimate(tracking_samples, impact_ms, ball_sample, width, height)
    contact_quality = _contact_classification(proximity_px, vertical_delta_px, ball_diameter, low_point)
    golf_metrics = tracking_summary.get('golfMetrics') if isinstance(tracking_summary.get('golfMetrics'), dict) else {}
    launch_metrics = launch_monitor.get('metrics') if isinstance(launch_monitor.get('metrics'), dict) else {}
    quality_confidence = _safe_float((tracking_summary.get('quality') or {}).get('overallTrackingConfidence')) if isinstance(tracking_summary.get('quality'), dict) else None
    confidence = _clamp(
        (float(contact_quality.get('confidence') or 0) * 0.44)
        + ((_safe_float(ball_flight_summary.get('confidence')) or 0) * 0.22)
        + (float(low_point.get('confidence') or 0) * 0.14)
        + ((_safe_float(club_face_estimate.get('confidence')) or 0) * 0.12)
        + ((quality_confidence or 0) * 0.08),
        0,
        0.82,
    )

    return {
        'status': 'generated',
        'modelVersion': 'impact-strike-v1',
        'analysisMode': 'ball_strike',
        'measurementSystem': 'single_camera_video_proxy',
        'impactTimestampMs': impact_ms,
        'impactFrame': {
            'frameIndex': club_sample.get('frameIndex') if club_sample else ball_sample.get('frameIndex') if ball_sample else None,
            'timestampMs': impact_ms,
            'clubTrackingFrameTimestampMs': club_sample.get('timestampMs') if club_sample else None,
            'ballTrackingFrameTimestampMs': ball_sample.get('timestampMs') if ball_sample else None,
        },
        'clubHeadAtImpact': _point_payload(club_sample, width, height, 'vision_line') if width > 0 and height > 0 else None,
        'ballPositionBeforeImpact': _point_payload(ball_sample, width, height, 'vision_motion') if width > 0 and height > 0 else None,
        'clubBallProximityPx': _safe_round(proximity_px),
        'clubBallHorizontalOffsetPx': _safe_round(horizontal_delta_px),
        'clubBallVerticalOffsetPx': _safe_round(vertical_delta_px),
        'estimatedBallDiameterPx': _safe_round(ball_diameter),
        'estimatedLowPoint': low_point,
        'shaftLeanAtImpactDegrees': golf_metrics.get('shaftLeanAtImpactDegrees'),
        'facePathProxy': {
            'faceToTarget': club_face_estimate.get('faceToTarget') or launch_metrics.get('faceToTarget') or 'unknown',
            'faceToPath': club_face_estimate.get('faceToPath') or launch_metrics.get('faceToPath') or 'unknown',
            'faceAngleDegrees': club_face_estimate.get('estimatedDegreesToTarget') or launch_metrics.get('faceAngleDegrees'),
            'faceToPathDegrees': club_face_estimate.get('estimatedDegreesToPath') or launch_metrics.get('faceToPathDegrees'),
            'clubPathProxy': club_face_estimate.get('clubPathProxy') or launch_metrics.get('clubPathProxy') or 'unknown',
            'clubPathDegrees': club_face_estimate.get('clubPathDegrees') or launch_metrics.get('clubPathDegrees'),
            'confidence': club_face_estimate.get('confidence') or 0,
            'measurementType': 'video_proxy_not_launch_monitor',
        },
        'contactQuality': contact_quality,
        'visualImpactInference': {
            'status': 'not_requested',
            'framesSent': 0,
            'reason': 'Deterministic impact evidence was sufficient or LLM impact analysis was disabled.',
        },
        'dataQuality': {
            'confidence': round(confidence, 3),
            'ballFlightConfidence': _safe_round(_safe_float(ball_flight_summary.get('confidence')), 3),
            'trackingConfidence': _safe_round(quality_confidence, 3),
            'clubFaceProxyConfidence': _safe_round(_safe_float(club_face_estimate.get('confidence')), 3),
            'ballFlightAvailable': True,
            'limitations': [
                'Strike point is inferred from single-camera club-head and ball positions.',
                'Heel/toe contact requires visible club-face detail; deterministic tracking keeps it unknown unless vision refinement can see it.',
                'Club-face angle is a video proxy and should not be treated as radar-grade face angle.',
            ],
        },
        'notes': 'Impact analysis is emitted only for validated real-ball swings. Dry swings do not get strike-location claims.',
    }


def _not_available_no_ball(ball_flight_summary: Dict[str, object]) -> Dict[str, object]:
    return {
        'status': 'not_available_no_validated_ball',
        'modelVersion': 'impact-strike-v1',
        'analysisMode': 'dry_swing_or_no_validated_ball',
        'measurementSystem': 'not_recorded_without_validated_ball',
        'impactTimestampMs': None,
        'impactFrame': None,
        'clubHeadAtImpact': None,
        'ballPositionBeforeImpact': None,
        'clubBallProximityPx': None,
        'estimatedLowPoint': None,
        'shaftLeanAtImpactDegrees': None,
        'facePathProxy': None,
        'contactQuality': {
            'classification': 'not_recorded_no_ball',
            'verticalStrike': 'not_recorded_no_ball',
            'horizontalStrike': 'not_recorded_no_ball',
            'confidence': 0,
            'evidence': ['No validated ball track exists, so strike quality was intentionally not recorded.'],
        },
        'visualImpactInference': {
            'status': 'skipped_no_validated_ball',
            'framesSent': 0,
        },
        'dataQuality': {
            'confidence': 0,
            'ballFlightAvailable': False,
            'ballFlightStatus': ball_flight_summary.get('status') or 'no_ball_detected',
            'limitations': ['Actual strike point and contact quality require a validated ball at impact.'],
        },
        'notes': 'Dry/no-ball swings can still have biomechanical contact-risk predictions, but no actual strike-location measurement.',
    }


def _needs_visual_refinement(impact_analysis: Dict[str, object]) -> bool:
    contact = impact_analysis.get('contactQuality') if isinstance(impact_analysis.get('contactQuality'), dict) else {}
    face = impact_analysis.get('facePathProxy') if isinstance(impact_analysis.get('facePathProxy'), dict) else {}
    confidence = _safe_float((impact_analysis.get('dataQuality') or {}).get('confidence')) if isinstance(impact_analysis.get('dataQuality'), dict) else 0
    return (
        (confidence or 0) < LLM_CONFIDENCE_TRIGGER
        or contact.get('classification') in {'unknown', 'off_center_unknown'}
        or contact.get('horizontalStrike') == 'unknown_without_face_visibility'
        or face.get('faceToTarget') == 'unknown'
    )


def _crop_impact_region(
    frame: np.ndarray,
    center_points: List[Tuple[float, float]],
) -> np.ndarray:
    if frame.size == 0 or not center_points:
        return frame
    height, width = frame.shape[:2]
    min_x = min(point[0] for point in center_points)
    max_x = max(point[0] for point in center_points)
    min_y = min(point[1] for point in center_points)
    max_y = max(point[1] for point in center_points)
    pad = max(96, int(min(width, height) * 0.12))
    x1 = max(0, int(min_x - pad))
    y1 = max(0, int(min_y - pad))
    x2 = min(width, int(max_x + pad))
    y2 = min(height, int(max_y + pad))
    if x2 <= x1 or y2 <= y1:
        return frame
    return frame[y1:y2, x1:x2]


def _jpeg_data_url(frame: np.ndarray) -> Optional[str]:
    ok, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        return None
    return 'data:image/jpeg;base64,' + base64.b64encode(encoded.tobytes()).decode('ascii')


def _sample_impact_frames(
    video_path: str,
    metadata: Dict[str, object],
    impact_analysis: Dict[str, object],
    max_frames: int,
) -> List[Dict[str, object]]:
    impact_ms = _safe_int(impact_analysis.get('impactTimestampMs'))
    fps = _safe_float(metadata.get('fps'))
    if impact_ms is None or fps is None or fps <= 0 or max_frames <= 0:
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    club = impact_analysis.get('clubHeadAtImpact') if isinstance(impact_analysis.get('clubHeadAtImpact'), dict) else {}
    ball = impact_analysis.get('ballPositionBeforeImpact') if isinstance(impact_analysis.get('ballPositionBeforeImpact'), dict) else {}
    center_points = []
    for point in (club, ball):
        x_px = _safe_float(point.get('xPx'))
        y_px = _safe_float(point.get('yPx'))
        if x_px is not None and y_px is not None:
            center_points.append((x_px, y_px))

    offsets = [0, -70, 70, -120, 120][:max_frames]
    samples: List[Dict[str, object]] = []
    try:
        for offset_ms in offsets:
            timestamp_ms = max(0, impact_ms + offset_ms)
            frame_index = max(0, int((timestamp_ms / 1000) * fps))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                continue
            crop = _crop_impact_region(frame, center_points)
            data_url = _jpeg_data_url(crop)
            if not data_url:
                continue
            samples.append({
                'frameIndex': frame_index,
                'timestampMs': timestamp_ms,
                'dataUrl': data_url,
                'crop': 'impact_area',
            })
    finally:
        cap.release()
    return samples


def _extract_response_text(response_body: Dict[str, object]) -> str:
    output_text = response_body.get('output_text')
    if isinstance(output_text, str):
        return output_text

    fragments: List[str] = []
    output = response_body.get('output')
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get('content')
            if not isinstance(content, list):
                continue
            for fragment in content:
                if isinstance(fragment, dict) and fragment.get('type') in {'output_text', 'text'}:
                    text = fragment.get('text')
                    if isinstance(text, str):
                        fragments.append(text)
    return '\n'.join(fragments)


def _parse_visual_response(text: str) -> Optional[Dict[str, object]]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    strike_location = parsed.get('strikeLocation')
    if strike_location not in {'center', 'thin', 'fat', 'heel', 'toe', 'unknown'}:
        parsed['strikeLocation'] = 'unknown'
    face_angle = parsed.get('clubFaceAngle')
    if face_angle not in {'open', 'square', 'closed', 'unknown'}:
        parsed['clubFaceAngle'] = 'unknown'
    confidence = _clamp(_safe_float(parsed.get('confidence')) or 0, 0, 1)
    parsed['confidence'] = round(confidence, 3)
    parsed['evidence'] = parsed.get('evidence') if isinstance(parsed.get('evidence'), list) else []
    parsed['limitations'] = parsed.get('limitations') if isinstance(parsed.get('limitations'), list) else []
    return parsed


def _request_visual_refinement(
    impact_analysis: Dict[str, object],
    samples: List[Dict[str, object]],
    active_settings: Settings,
) -> Optional[Dict[str, object]]:
    content = [{
        'type': 'input_text',
        'text': (
            f'{IMPACT_VISION_PROMPT}\n'
            f'Structured impact evidence: {json.dumps({key: value for key, value in impact_analysis.items() if key != "visualImpactInference"})}'
        ),
    }]
    for sample in samples:
        content.append({
            'type': 'input_text',
            'text': f'Impact crop frame {sample["frameIndex"]}, timestamp {sample["timestampMs"]} ms.',
        })
        content.append({
            'type': 'input_image',
            'image_url': sample['dataUrl'],
            'detail': 'high',
        })

    request_body = json.dumps({
        'model': active_settings.llm_impact_analysis_model,
        'input': [{'role': 'user', 'content': content}],
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'impact_visual_refinement',
                'strict': True,
                'schema': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'contactLikely': {'type': 'boolean'},
                        'strikeLocation': {
                            'type': 'string',
                            'enum': ['center', 'thin', 'fat', 'heel', 'toe', 'unknown'],
                        },
                        'clubFaceAngle': {
                            'type': 'string',
                            'enum': ['open', 'square', 'closed', 'unknown'],
                        },
                        'clubFaceVisible': {'type': 'boolean'},
                        'ballVisible': {'type': 'boolean'},
                        'impactFrameQuality': {
                            'type': 'string',
                            'enum': ['clear', 'motion_blur', 'occluded', 'unknown'],
                        },
                        'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                        'evidence': {'type': 'array', 'items': {'type': 'string'}},
                        'limitations': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': [
                        'contactLikely',
                        'strikeLocation',
                        'clubFaceAngle',
                        'clubFaceVisible',
                        'ballVisible',
                        'impactFrameQuality',
                        'confidence',
                        'evidence',
                        'limitations',
                    ],
                },
            },
        },
    }).encode('utf-8')
    request = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=request_body,
        headers={
            'Authorization': f'Bearer {active_settings.openai_api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response_body = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    return _parse_visual_response(_extract_response_text(response_body))


def _merge_visual_refinement(
    impact_analysis: Dict[str, object],
    visual: Dict[str, object],
    frame_count: int,
    model: str,
) -> Dict[str, object]:
    contact = impact_analysis.get('contactQuality') if isinstance(impact_analysis.get('contactQuality'), dict) else {}
    visual_confidence = _safe_float(visual.get('confidence')) or 0
    strike_location = str(visual.get('strikeLocation') or 'unknown')
    llm_classification = 'likely_centered' if strike_location == 'center' else strike_location
    if strike_location != 'unknown' and visual_confidence >= 0.35:
        contact = {
            **contact,
            'classification': llm_classification,
            'llmClassification': llm_classification,
            'confidence': round(_clamp(float(contact.get('confidence') or 0) * 0.45 + visual_confidence * 0.55, 0, 0.9), 3),
            'evidence': [
                *(contact.get('evidence') if isinstance(contact.get('evidence'), list) else []),
                *[str(item) for item in visual.get('evidence', [])[:4]],
            ],
        }
        if strike_location in {'heel', 'toe'}:
            contact['horizontalStrike'] = strike_location
        elif strike_location in {'thin', 'fat'}:
            contact['verticalStrike'] = strike_location

    face = impact_analysis.get('facePathProxy') if isinstance(impact_analysis.get('facePathProxy'), dict) else {}
    if visual.get('clubFaceAngle') in {'open', 'square', 'closed'} and visual_confidence >= 0.35:
        face = {
            **face,
            'visualFaceAngle': visual.get('clubFaceAngle'),
            'visualFaceConfidence': visual_confidence,
        }

    data_quality = impact_analysis.get('dataQuality') if isinstance(impact_analysis.get('dataQuality'), dict) else {}
    impact_confidence = _clamp(float(data_quality.get('confidence') or 0) * 0.58 + visual_confidence * 0.42, 0, 0.9)
    return {
        **impact_analysis,
        'contactQuality': contact,
        'facePathProxy': face,
        'visualImpactInference': {
            'status': 'generated',
            'model': model,
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
            'framesSent': frame_count,
            **visual,
        },
        'dataQuality': {
            **data_quality,
            'confidence': round(impact_confidence, 3),
            'visualRefinementConfidence': visual_confidence,
        },
    }


def analyze_impact_strike(
    video_path: str,
    metadata: Dict[str, object],
    tracking_frames: List[Dict[str, object]],
    tracking_summary: Dict[str, object],
    ball_tracking_frames: List[Dict[str, object]],
    ball_flight_summary: Dict[str, object],
    phases: Optional[Dict[str, object]],
    launch_monitor: Optional[Dict[str, object]],
    club_face_estimate: Optional[Dict[str, object]],
    active_settings: Settings = settings,
) -> Tuple[Dict[str, object], bool]:
    phases = phases or {}
    launch_monitor = launch_monitor or {}
    club_face_estimate = club_face_estimate or {}
    if not _has_valid_ball(ball_flight_summary or {}):
        return _not_available_no_ball(ball_flight_summary or {}), False

    impact_analysis = _deterministic_impact_analysis(
        metadata or {},
        tracking_frames or [],
        tracking_summary or {},
        ball_tracking_frames or [],
        ball_flight_summary or {},
        phases,
        launch_monitor,
        club_face_estimate,
    )

    should_call_llm = (
        active_settings.enable_llm_impact_analysis
        and active_settings.send_video_to_llm
        and bool(active_settings.openai_api_key)
        and _needs_visual_refinement(impact_analysis)
    )
    if not should_call_llm:
        reason = 'disabled_or_not_needed'
        if not active_settings.enable_llm_impact_analysis:
            reason = 'ENABLE_LLM_IMPACT_ANALYSIS is false'
        elif not active_settings.send_video_to_llm:
            reason = 'SEND_VIDEO_TO_LLM is false'
        elif not active_settings.openai_api_key:
            reason = 'OPENAI_API_KEY is missing'
        elif not _needs_visual_refinement(impact_analysis):
            reason = 'deterministic impact evidence is sufficient'
        impact_analysis['visualImpactInference'] = {
            'status': 'not_requested',
            'framesSent': 0,
            'reason': reason,
        }
        return impact_analysis, False

    samples = _sample_impact_frames(
        video_path,
        metadata or {},
        impact_analysis,
        max(1, min(active_settings.llm_impact_analysis_max_frames, 4)),
    )
    if not samples:
        impact_analysis['visualImpactInference'] = {
            'status': 'failed',
            'framesSent': 0,
            'reason': 'Impact frame crops could not be extracted.',
        }
        return impact_analysis, False

    visual = _request_visual_refinement(impact_analysis, samples, active_settings)
    if not visual:
        impact_analysis['visualImpactInference'] = {
            'status': 'failed',
            'model': active_settings.llm_impact_analysis_model,
            'framesSent': len(samples),
            'reason': 'LLM impact vision request failed or returned invalid JSON.',
        }
        return impact_analysis, True

    return _merge_visual_refinement(
        impact_analysis,
        visual,
        len(samples),
        active_settings.llm_impact_analysis_model,
    ), True
