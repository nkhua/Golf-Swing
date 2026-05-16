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

    return best


def _path_metrics(
    frames: List[BallFrame],
    width: int,
    height: int,
) -> Dict[str, object]:
    visible = [
        frame_data
        for frame_data in frames
        if isinstance(frame_data.get('ball'), dict)
        and float(frame_data['ball'].get('confidence') or 0) >= 0.22
    ]
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

    shot_shape = 'unknown'
    if abs(curvature_px) > width * 0.025:
        shot_shape = 'fade' if curvature_px > 0 else 'draw'
    elif len(visible) >= 3:
        shot_shape = 'straight'

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
        'shotShape': shot_shape,
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
            'framesTracked': 0,
            'ballFrameCount': 0,
            'averageBallConfidence': 0,
            'confidence': 0,
            'quality': {
                'ballFrameRatio': 0,
                'needsLongerVideo': True,
                'needsRetake': True,
                'retakeReasons': ['No ball tracking frames were available.'],
            },
            'notes': 'No ball tracking frames were available.',
        }

    metrics = _path_metrics(frames, width, height)
    ball_count = int(metrics.get('ballFrameCount') or 0)
    ball_ratio = ball_count / len(frames)
    tracking_start_ms = int(frames[0].get('timestampMs') or 0)
    tracking_end_ms = int(frames[-1].get('timestampMs') or tracking_start_ms)
    impact_ms = int(phases.get('impact') or tracking_start_ms) if phases else tracking_start_ms
    needs_longer_video = tracking_end_ms - impact_ms < BALL_FLIGHT_TRACK_MS - 250
    retake_reasons: List[str] = []
    if ball_count < 2:
        retake_reasons.append('The ball was not visible long enough after impact to estimate flight.')
    if needs_longer_video:
        retake_reasons.append('Keep recording longer after impact so the ball flight can be tracked.')

    confidence = float(metrics.get('confidence') or 0)
    return {
        'framesTracked': len(frames),
        **metrics,
        'trackingStartMs': tracking_start_ms,
        'trackingEndMs': tracking_end_ms,
        'trackingMethod': 'bright_motion_contours_after_impact',
        'quality': {
            'ballFrameRatio': round(ball_ratio, 3),
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
    launch_direction = summary.get('launchDirection') if confidence >= 0.45 else None
    return {
        'launchDirection': launch_direction,
        'shotShape': summary.get('shotShape') or 'unknown',
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
