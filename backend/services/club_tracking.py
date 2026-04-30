from math import atan2, degrees, sqrt
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np


Point = Dict[str, object]
TrackingFrame = Dict[str, object]

WRIST_NAMES = ('LEFT_WRIST', 'RIGHT_WRIST')
MIN_CLUB_CONFIDENCE_FOR_SUMMARY = 0.2
MAX_CLUB_DETECTION_IMAGE_SIDE = 720


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _landmark_map(pose_frame: Dict[str, object]) -> Dict[str, Dict[str, float]]:
    return {
        str(landmark.get('name')): landmark
        for landmark in pose_frame.get('landmarks', [])
        if isinstance(landmark, dict) and landmark.get('name')
    }


def _point_from_landmark(landmark: Optional[Dict[str, float]]) -> Optional[Point]:
    if not landmark:
        return None

    raw_visibility = landmark.get('visibility')
    visibility = _clamp(float(raw_visibility) if raw_visibility is not None else 1.0, 0, 1)
    return {
        'x': _clamp(float(landmark.get('x') or 0), 0, 1),
        'y': _clamp(float(landmark.get('y') or 0), 0, 1),
        'z': float(landmark['z']) if landmark.get('z') is not None else None,
        'confidence': visibility,
        'source': 'pose_landmark',
    }


def _midpoint(a: Point, b: Point) -> Point:
    return {
        'x': (float(a['x']) + float(b['x'])) / 2,
        'y': (float(a['y']) + float(b['y'])) / 2,
        'z': ((float(a['z']) + float(b['z'])) / 2) if a.get('z') is not None and b.get('z') is not None else None,
        'confidence': min(float(a.get('confidence') or 0), float(b.get('confidence') or 0)),
        'source': 'pose_midpoint',
    }


def _normalized_to_pixel(point: Point, width: int, height: int) -> Tuple[float, float]:
    return float(point['x']) * width, float(point['y']) * height


def _resize_for_club_detection(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    max_side = max(width, height)
    if max_side <= MAX_CLUB_DETECTION_IMAGE_SIDE:
        return frame

    scale = MAX_CLUB_DETECTION_IMAGE_SIDE / max_side
    return cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)


def _pixel_point(x: float, y: float, width: int, height: int, confidence: float, source: str) -> Point:
    return {
        'x': round(_clamp(x / max(width, 1), 0, 1), 5),
        'y': round(_clamp(y / max(height, 1), 0, 1), 5),
        'confidence': round(_clamp(confidence, 0, 1), 3),
        'source': source,
    }


def _distance_to_segment(
    point: Tuple[float, float],
    start: Tuple[float, float],
    end: Tuple[float, float],
) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return sqrt((px - sx) ** 2 + (py - sy) ** 2)

    projection = _clamp(((px - sx) * dx + (py - sy) * dy) / length_sq, 0, 1)
    closest_x = sx + projection * dx
    closest_y = sy + projection * dy
    return sqrt((px - closest_x) ** 2 + (py - closest_y) ** 2)


def _line_angle_degrees(start: Point, end: Point, width: int, height: int) -> float:
    sx, sy = _normalized_to_pixel(start, width, height)
    ex, ey = _normalized_to_pixel(end, width, height)
    return degrees(atan2(ey - sy, ex - sx))


def _line_length_px(start: Point, end: Point, width: int, height: int) -> float:
    sx, sy = _normalized_to_pixel(start, width, height)
    ex, ey = _normalized_to_pixel(end, width, height)
    return sqrt((ex - sx) ** 2 + (ey - sy) ** 2)


def _build_shaft_line(start: Point, end: Point, width: int, height: int, confidence: float, source: str) -> Dict[str, object]:
    return {
        'start': start,
        'end': end,
        'confidence': round(_clamp(confidence, 0, 1), 3),
        'angleDegrees': round(_line_angle_degrees(start, end, width, height), 2),
        'lengthPx': round(_line_length_px(start, end, width, height), 2),
        'source': source,
    }


def _detect_club_line(frame: np.ndarray, grip: Optional[Point]) -> Optional[Dict[str, object]]:
    if grip is None or frame.size == 0:
        return None

    frame = _resize_for_club_detection(frame)
    height, width = frame.shape[:2]
    grip_px = _normalized_to_pixel(grip, width, height)
    min_dimension = max(min(width, height), 1)
    max_grip_distance = max(28.0, min_dimension * 0.065)
    min_line_length = max(26, int(min_dimension * 0.09))
    max_line_gap = max(8, int(min_dimension * 0.025))

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 45, 145)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=max(18, int(min_dimension * 0.045)),
        minLineLength=min_line_length,
        maxLineGap=max_line_gap,
    )
    if lines is None:
        return None

    best_candidate: Optional[Dict[str, object]] = None
    best_score = 0.0
    grip_confidence = float(grip.get('confidence') or 0)

    for raw_line in lines[:, 0]:
        x1, y1, x2, y2 = [float(value) for value in raw_line]
        start_px = (x1, y1)
        end_px = (x2, y2)
        line_length = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if line_length < min_line_length:
            continue

        distance_to_grip = _distance_to_segment(grip_px, start_px, end_px)
        if distance_to_grip > max_grip_distance:
            continue

        start_distance = sqrt((x1 - grip_px[0]) ** 2 + (y1 - grip_px[1]) ** 2)
        end_distance = sqrt((x2 - grip_px[0]) ** 2 + (y2 - grip_px[1]) ** 2)
        head_px = start_px if start_distance >= end_distance else end_px
        shaft_start_px = end_px if start_distance >= end_distance else start_px
        far_distance = max(start_distance, end_distance)
        extension_factor = _clamp(far_distance / (min_dimension * 0.32), 0, 1)
        proximity_factor = 1 - _clamp(distance_to_grip / max_grip_distance, 0, 1)
        length_factor = _clamp(line_length / (min_dimension * 0.35), 0, 1)
        score = (0.42 * proximity_factor) + (0.36 * length_factor) + (0.22 * extension_factor)

        if score <= best_score:
            continue

        confidence = _clamp((0.15 + score * 0.85) * _clamp(grip_confidence, 0.25, 1), 0, 1)
        shaft_start = _pixel_point(shaft_start_px[0], shaft_start_px[1], width, height, confidence, 'vision_line')
        club_head = _pixel_point(head_px[0], head_px[1], width, height, confidence, 'vision_line')
        best_candidate = {
            'clubHead': club_head,
            'clubShaft': _build_shaft_line(shaft_start, club_head, width, height, confidence, 'vision_line'),
        }
        best_score = score

    return best_candidate


def _weighted_smooth_point(center_point: Optional[Point], points: Sequence[Optional[Point]]) -> Optional[Point]:
    if center_point is None:
        return None

    visible = [point for point in points if point is not None]
    if not visible:
        return None

    source = str(center_point.get('source') or visible[-1].get('source') or 'unknown')
    weights = [max(float(point.get('confidence') or 0), 0.05) for point in visible]
    total_weight = sum(weights) or 1
    smoothed = {
        'x': round(sum(float(point['x']) * weight for point, weight in zip(visible, weights)) / total_weight, 5),
        'y': round(sum(float(point['y']) * weight for point, weight in zip(visible, weights)) / total_weight, 5),
        'confidence': round(min(max(float(center_point.get('confidence') or 0), 0), 1), 3),
        'source': source,
    }
    z_values = [
        (float(point['z']), weight)
        for point, weight in zip(visible, weights)
        if point.get('z') is not None
    ]
    if z_values:
        smoothed['z'] = round(sum(z * weight for z, weight in z_values) / sum(weight for _, weight in z_values), 5)
    return smoothed


def _smooth_tracking_frames(frames: List[TrackingFrame], metadata: Dict[str, object]) -> List[TrackingFrame]:
    width = int(metadata.get('width') or 0)
    height = int(metadata.get('height') or 0)
    if not frames or width <= 0 or height <= 0:
        return frames

    smoothed: List[TrackingFrame] = []
    for index, frame_data in enumerate(frames):
        window = frames[max(0, index - 1):min(len(frames), index + 2)]
        next_frame = {**frame_data}
        for key in ('leftWrist', 'rightWrist', 'grip', 'clubHead'):
            next_frame[key] = _weighted_smooth_point(
                frame_data.get(key),
                [candidate.get(key) for candidate in window],
            )

        grip = next_frame.get('grip')
        club_head = next_frame.get('clubHead')
        if grip and club_head:
            shaft_confidence = min(float(grip.get('confidence') or 0), float(club_head.get('confidence') or 0))
            next_frame['clubShaft'] = _build_shaft_line(grip, club_head, width, height, shaft_confidence, str(club_head.get('source') or 'vision_line'))
        else:
            next_frame['clubShaft'] = None

        smoothed.append(next_frame)

    return smoothed


def _predict_missing_club_points(frames: List[TrackingFrame], metadata: Dict[str, object]) -> List[TrackingFrame]:
    width = int(metadata.get('width') or 0)
    height = int(metadata.get('height') or 0)
    if width <= 0 or height <= 0:
        return frames

    previous_grip: Optional[Point] = None
    previous_head: Optional[Point] = None
    previous_confidence = 0.0

    for frame_data in frames:
        grip = frame_data.get('grip')
        club_head = frame_data.get('clubHead')
        if grip and club_head and float(club_head.get('confidence') or 0) >= MIN_CLUB_CONFIDENCE_FOR_SUMMARY:
            previous_grip = grip
            previous_head = club_head
            previous_confidence = float(club_head.get('confidence') or 0)
            continue

        if not grip or not previous_grip or not previous_head or previous_confidence < 0.35:
            continue

        vector_x = float(previous_head['x']) - float(previous_grip['x'])
        vector_y = float(previous_head['y']) - float(previous_grip['y'])
        predicted_head = {
            'x': round(_clamp(float(grip['x']) + vector_x, 0, 1), 5),
            'y': round(_clamp(float(grip['y']) + vector_y, 0, 1), 5),
            'confidence': round(previous_confidence * 0.55, 3),
            'source': 'temporal_prediction',
        }
        frame_data['clubHead'] = predicted_head
        frame_data['clubShaft'] = _build_shaft_line(
            grip,
            predicted_head,
            width,
            height,
            min(float(grip.get('confidence') or 0), float(predicted_head['confidence'])),
            'temporal_prediction',
        )

    return frames


def track_swing_points_for_frame(
    frame: np.ndarray,
    pose_frame: Dict[str, object],
    metadata: Dict[str, object],
) -> TrackingFrame:
    height, width = frame.shape[:2] if frame.size else (int(metadata.get('height') or 0), int(metadata.get('width') or 0))
    landmarks = _landmark_map(pose_frame)
    left_wrist = _point_from_landmark(landmarks.get('LEFT_WRIST'))
    right_wrist = _point_from_landmark(landmarks.get('RIGHT_WRIST'))
    grip = _midpoint(left_wrist, right_wrist) if left_wrist and right_wrist else left_wrist or right_wrist

    tracking_frame: TrackingFrame = {
        'frameIndex': int(pose_frame.get('frameIndex') or 0),
        'timestampMs': int(pose_frame.get('timestampMs') or 0),
        'leftWrist': left_wrist,
        'rightWrist': right_wrist,
        'grip': grip,
        'clubHead': None,
        'clubShaft': None,
    }

    if width > 0 and height > 0:
        detected = _detect_club_line(frame, grip)
        if detected:
            tracking_frame.update(detected)

    return tracking_frame


def _point_distance_px(a: Point, b: Point, width: int, height: int) -> float:
    ax, ay = _normalized_to_pixel(a, width, height)
    bx, by = _normalized_to_pixel(b, width, height)
    return sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def _path_metrics(
    frames: List[TrackingFrame],
    key: str,
    width: int,
    height: int,
    min_confidence: float = 0.0,
) -> Tuple[float, float, Optional[int], int]:
    previous_point: Optional[Point] = None
    previous_time: Optional[int] = None
    path_length = 0.0
    max_speed = 0.0
    max_speed_time: Optional[int] = None
    count = 0

    for frame_data in frames:
        point = frame_data.get(key)
        confidence = float(point.get('confidence') or 0) if isinstance(point, dict) else 0
        if not isinstance(point, dict) or confidence < min_confidence:
            continue

        current_time = int(frame_data.get('timestampMs') or 0)
        count += 1
        if previous_point is not None and previous_time is not None and current_time > previous_time:
            distance = _point_distance_px(previous_point, point, width, height)
            path_length += distance
            speed = distance / ((current_time - previous_time) / 1000)
            if speed > max_speed:
                max_speed = speed
                max_speed_time = current_time

        previous_point = point
        previous_time = current_time

    return path_length, max_speed, max_speed_time, count


def summarize_tracking_frames(
    frames: List[TrackingFrame],
    metadata: Dict[str, object],
) -> Dict[str, object]:
    width = int(metadata.get('width') or 0)
    height = int(metadata.get('height') or 0)
    if not frames or width <= 0 or height <= 0:
        return {
            'framesTracked': 0,
            'wristFrameCount': 0,
            'clubFrameCount': 0,
            'averageClubConfidence': 0,
            'clubDetectionMethod': 'hough_line_near_hands',
            'notes': 'No tracking frames were available.',
        }

    left_path, left_speed, _, left_count = _path_metrics(frames, 'leftWrist', width, height)
    right_path, right_speed, _, right_count = _path_metrics(frames, 'rightWrist', width, height)
    grip_path, grip_speed, _, grip_count = _path_metrics(frames, 'grip', width, height)
    club_path, club_speed, impact_ms, club_count = _path_metrics(
        frames,
        'clubHead',
        width,
        height,
        MIN_CLUB_CONFIDENCE_FOR_SUMMARY,
    )
    club_confidences = [
        float(frame_data['clubHead'].get('confidence') or 0)
        for frame_data in frames
        if isinstance(frame_data.get('clubHead'), dict)
        and float(frame_data['clubHead'].get('confidence') or 0) >= MIN_CLUB_CONFIDENCE_FOR_SUMMARY
    ]

    return {
        'framesTracked': len(frames),
        'wristFrameCount': min(left_count, right_count) if left_count and right_count else max(left_count, right_count),
        'clubFrameCount': club_count,
        'averageClubConfidence': round(sum(club_confidences) / len(club_confidences), 3) if club_confidences else 0,
        'leftWristPathLengthPx': round(left_path, 2),
        'rightWristPathLengthPx': round(right_path, 2),
        'gripPathLengthPx': round(grip_path, 2),
        'clubHeadPathLengthPx': round(club_path, 2),
        'maxGripSpeedPxPerSec': round(grip_speed, 2),
        'maxClubHeadSpeedPxPerSec': round(club_speed, 2),
        'estimatedImpactMs': impact_ms,
        'clubDetectionMethod': 'hough_line_near_hands',
        'notes': (
            'Wrists and grip are tracked from MediaPipe pose landmarks; club head and shaft are '
            'detected from OpenCV line candidates near the hands and temporally smoothed.'
        ),
    }


def extract_swing_tracking(
    video_path: str,
    pose_frames: List[Dict[str, object]],
    metadata: Dict[str, object],
) -> Tuple[List[TrackingFrame], Dict[str, object]]:
    if not pose_frames:
        return [], summarize_tracking_frames([], metadata)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        tracking_frames = [
            track_swing_points_for_frame(np.empty((0, 0, 3), dtype=np.uint8), pose_frame, metadata)
            for pose_frame in pose_frames
        ]
        tracking_frames = _smooth_tracking_frames(_predict_missing_club_points(tracking_frames, metadata), metadata)
        return tracking_frames, summarize_tracking_frames(tracking_frames, metadata)

    tracking_frames: List[TrackingFrame] = []
    try:
        for pose_frame in pose_frames:
            frame_index = int(pose_frame.get('frameIndex') or 0)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                frame = np.empty((0, 0, 3), dtype=np.uint8)
            tracking_frames.append(track_swing_points_for_frame(frame, pose_frame, metadata))
    finally:
        cap.release()

    tracking_frames = _predict_missing_club_points(tracking_frames, metadata)
    tracking_frames = _smooth_tracking_frames(tracking_frames, metadata)
    return tracking_frames, summarize_tracking_frames(tracking_frames, metadata)
