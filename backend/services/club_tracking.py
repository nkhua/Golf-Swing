from math import atan2, degrees, sqrt
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import urllib.request

import cv2
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options
from mediapipe.tasks.python.vision.core import image as mp_image
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode

from config import settings


Point = Dict[str, object]
TrackingFrame = Dict[str, object]

WRIST_NAMES = ('LEFT_WRIST', 'RIGHT_WRIST')
MIN_CLUB_CONFIDENCE_FOR_SUMMARY = 0.2
MAX_CLUB_DETECTION_IMAGE_SIDE = 720
MAX_HAND_LANDMARK_FRAMES = 6
MODEL_DIR = Path(__file__).resolve().parent.parent / 'models'
HAND_MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
FACE_MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
HAND_MODEL_PATH = MODEL_DIR / 'hand_landmarker.task'
FACE_MODEL_PATH = MODEL_DIR / 'face_landmarker.task'
FAILED_OPTIONAL_MODEL_DOWNLOADS = set()

HAND_LANDMARK_WRIST = 0
HAND_LANDMARK_INDEX_MCP = 5
HAND_LANDMARK_MIDDLE_MCP = 9
HAND_LANDMARK_PINKY_MCP = 17

FACE_LEFT_EYE_OUTER = 33
FACE_LEFT_EYE_INNER = 133
FACE_RIGHT_EYE_INNER = 362
FACE_RIGHT_EYE_OUTER = 263
FACE_NOSE_TIP = 1
FACE_CHIN = 152


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _download_model_asset(url: str, path: Path) -> bool:
    if path.exists():
        return True
    if path in FAILED_OPTIONAL_MODEL_DOWNLOADS:
        return False

    path.parent.mkdir(exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            path.write_bytes(response.read())
        return True
    except Exception:
        FAILED_OPTIONAL_MODEL_DOWNLOADS.add(path)
        return False


def _create_hand_landmarker() -> Optional[vision.HandLandmarker]:
    if not _download_model_asset(HAND_MODEL_URL, HAND_MODEL_PATH):
        return None

    options = vision.HandLandmarkerOptions(
        base_options=base_options.BaseOptions(model_asset_path=str(HAND_MODEL_PATH)),
        running_mode=VisionTaskRunningMode.IMAGE,
        num_hands=2,
        min_hand_detection_confidence=0.45,
        min_hand_presence_confidence=0.45,
        min_tracking_confidence=0.45,
    )
    try:
        return vision.HandLandmarker.create_from_options(options)
    except Exception:
        return None


def _create_face_landmarker() -> Optional[vision.FaceLandmarker]:
    if not _download_model_asset(FACE_MODEL_URL, FACE_MODEL_PATH):
        return None

    options = vision.FaceLandmarkerOptions(
        base_options=base_options.BaseOptions(model_asset_path=str(FACE_MODEL_PATH)),
        running_mode=VisionTaskRunningMode.IMAGE,
        num_faces=1,
        min_face_detection_confidence=0.45,
        min_face_presence_confidence=0.45,
        min_tracking_confidence=0.45,
        output_facial_transformation_matrixes=True,
    )
    try:
        return vision.FaceLandmarker.create_from_options(options)
    except Exception:
        return None


def _create_mp_image(frame: np.ndarray) -> Optional[mp_image.Image]:
    if frame.size == 0:
        return None

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return mp_image.Image(mp_image.ImageFormat.SRGB, np.asarray(rgb_frame))


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


def _point_from_task_landmark(landmark, confidence: float, source: str) -> Point:
    return {
        'x': round(_clamp(float(getattr(landmark, 'x', 0)), 0, 1), 5),
        'y': round(_clamp(float(getattr(landmark, 'y', 0)), 0, 1), 5),
        'z': round(float(getattr(landmark, 'z')), 5) if getattr(landmark, 'z', None) is not None else None,
        'confidence': round(_clamp(confidence, 0, 1), 3),
        'source': source,
    }


def _midpoint(a: Point, b: Point) -> Point:
    return {
        'x': (float(a['x']) + float(b['x'])) / 2,
        'y': (float(a['y']) + float(b['y'])) / 2,
        'z': ((float(a['z']) + float(b['z'])) / 2) if a.get('z') is not None and b.get('z') is not None else None,
        'confidence': min(float(a.get('confidence') or 0), float(b.get('confidence') or 0)),
        'source': 'pose_midpoint',
    }


def _midpoint_with_source(a: Point, b: Point, source: str) -> Point:
    point = _midpoint(a, b)
    point['source'] = source
    return point


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


def _angle_between_vectors_degrees(
    vertex: Point,
    first: Point,
    second: Point,
    width: int,
    height: int,
) -> Optional[float]:
    vx, vy = _normalized_to_pixel(vertex, width, height)
    ax, ay = _normalized_to_pixel(first, width, height)
    bx, by = _normalized_to_pixel(second, width, height)
    vector_a = (ax - vx, ay - vy)
    vector_b = (bx - vx, by - vy)
    mag_a = sqrt(vector_a[0] ** 2 + vector_a[1] ** 2)
    mag_b = sqrt(vector_b[0] ** 2 + vector_b[1] ** 2)
    if mag_a == 0 or mag_b == 0:
        return None

    dot = vector_a[0] * vector_b[0] + vector_a[1] * vector_b[1]
    cross = vector_a[0] * vector_b[1] - vector_a[1] * vector_b[0]
    return degrees(atan2(cross, dot))


def _absolute_joint_angle_degrees(
    vertex: Point,
    first: Point,
    second: Point,
    width: int,
    height: int,
) -> Optional[float]:
    angle = _angle_between_vectors_degrees(vertex, first, second, width, height)
    return round(abs(angle), 2) if angle is not None else None


def _safe_round(value: Optional[float], digits: int = 2) -> Optional[float]:
    return round(value, digits) if value is not None else None


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


def _nearest_pose_wrist_side(
    hand_wrist: Point,
    left_wrist: Optional[Point],
    right_wrist: Optional[Point],
    width: int,
    height: int,
) -> Optional[str]:
    distances: List[Tuple[str, float]] = []
    if left_wrist:
        distances.append(('left', _point_distance_px(hand_wrist, left_wrist, width, height)))
    if right_wrist:
        distances.append(('right', _point_distance_px(hand_wrist, right_wrist, width, height)))
    if not distances:
        return None
    return min(distances, key=lambda item: item[1])[0]


def _hand_detection_score(results, hand_index: int) -> float:
    handedness = getattr(results, 'handedness', None) or []
    try:
        categories = handedness[hand_index]
        if categories:
            return float(getattr(categories[0], 'score', 0.75) or 0.75)
    except (IndexError, TypeError):
        pass
    return 0.75


def _extract_hand_points(
    frame: np.ndarray,
    input_image: Optional[mp_image.Image],
    hand_landmarker: Optional[vision.HandLandmarker],
    left_wrist: Optional[Point],
    right_wrist: Optional[Point],
    width: int,
    height: int,
) -> Dict[str, Point]:
    if input_image is None or hand_landmarker is None:
        return {}

    try:
        results = hand_landmarker.detect(input_image)
    except Exception:
        return {}

    hand_landmarks = getattr(results, 'hand_landmarks', None) or []
    points: Dict[str, Point] = {}
    for hand_index, landmarks in enumerate(hand_landmarks):
        if len(landmarks) <= HAND_LANDMARK_PINKY_MCP:
            continue

        score = _hand_detection_score(results, hand_index)
        hand_wrist = _point_from_task_landmark(landmarks[HAND_LANDMARK_WRIST], score, 'hand_landmark')
        side = _nearest_pose_wrist_side(hand_wrist, left_wrist, right_wrist, width, height)
        if not side:
            continue

        index_mcp = _point_from_task_landmark(landmarks[HAND_LANDMARK_INDEX_MCP], score, 'hand_landmark')
        middle_mcp = _point_from_task_landmark(landmarks[HAND_LANDMARK_MIDDLE_MCP], score, 'hand_landmark')
        pinky_mcp = _point_from_task_landmark(landmarks[HAND_LANDMARK_PINKY_MCP], score, 'hand_landmark')
        points[f'{side}HandWrist'] = hand_wrist
        points[f'{side}IndexMcp'] = index_mcp
        points[f'{side}MiddleMcp'] = middle_mcp
        points[f'{side}PinkyMcp'] = pinky_mcp
        points[f'{side}PalmCenter'] = _midpoint_with_source(index_mcp, pinky_mcp, 'hand_landmark')

    return points


def _face_point_from_landmarks(landmarks, index: int, confidence: float, source: str) -> Optional[Point]:
    if len(landmarks) <= index:
        return None
    return _point_from_task_landmark(landmarks[index], confidence, source)


def _extract_face_points(
    input_image: Optional[mp_image.Image],
    face_landmarker: Optional[vision.FaceLandmarker],
    landmarks: Dict[str, Dict[str, float]],
) -> Dict[str, object]:
    if input_image is not None and face_landmarker is not None:
        try:
            results = face_landmarker.detect(input_image)
        except Exception:
            results = None

        face_landmarks = getattr(results, 'face_landmarks', None) if results is not None else None
        if face_landmarks:
            face = face_landmarks[0]
            confidence = 0.82
            left_outer = _face_point_from_landmarks(face, FACE_LEFT_EYE_OUTER, confidence, 'face_landmark')
            left_inner = _face_point_from_landmarks(face, FACE_LEFT_EYE_INNER, confidence, 'face_landmark')
            right_inner = _face_point_from_landmarks(face, FACE_RIGHT_EYE_INNER, confidence, 'face_landmark')
            right_outer = _face_point_from_landmarks(face, FACE_RIGHT_EYE_OUTER, confidence, 'face_landmark')
            nose = _face_point_from_landmarks(face, FACE_NOSE_TIP, confidence, 'face_landmark')
            chin = _face_point_from_landmarks(face, FACE_CHIN, confidence, 'face_landmark')
            if left_outer and left_inner and right_inner and right_outer and nose:
                left_eye = _midpoint_with_source(left_outer, left_inner, 'face_landmark')
                right_eye = _midpoint_with_source(right_inner, right_outer, 'face_landmark')
                head_center = _midpoint_with_source(left_eye, right_eye, 'face_landmark')
                return {
                    'leftEye': left_eye,
                    'rightEye': right_eye,
                    'nose': nose,
                    'chin': chin,
                    'headCenter': head_center,
                    'source': 'face_landmark',
                }

    left_eye = _point_from_landmark(landmarks.get('LEFT_EYE'))
    right_eye = _point_from_landmark(landmarks.get('RIGHT_EYE'))
    nose = _point_from_landmark(landmarks.get('NOSE'))
    if not left_eye or not right_eye or not nose:
        return {}

    left_eye['source'] = 'pose_estimate'
    right_eye['source'] = 'pose_estimate'
    nose['source'] = 'pose_estimate'
    return {
        'leftEye': left_eye,
        'rightEye': right_eye,
        'nose': nose,
        'chin': None,
        'headCenter': _midpoint_with_source(left_eye, right_eye, 'pose_estimate'),
        'source': 'pose_estimate',
    }


def _build_line_if_points(
    start: Optional[Point],
    end: Optional[Point],
    width: int,
    height: int,
    source: str,
) -> Optional[Dict[str, object]]:
    if not start or not end:
        return None
    return _build_shaft_line(
        start,
        end,
        width,
        height,
        min(float(start.get('confidence') or 0), float(end.get('confidence') or 0)),
        source,
    )


def _build_body_tracking(
    landmarks: Dict[str, Dict[str, float]],
    width: int,
    height: int,
) -> Dict[str, object]:
    left_shoulder = _point_from_landmark(landmarks.get('LEFT_SHOULDER'))
    right_shoulder = _point_from_landmark(landmarks.get('RIGHT_SHOULDER'))
    left_hip = _point_from_landmark(landmarks.get('LEFT_HIP'))
    right_hip = _point_from_landmark(landmarks.get('RIGHT_HIP'))
    left_elbow = _point_from_landmark(landmarks.get('LEFT_ELBOW'))
    right_elbow = _point_from_landmark(landmarks.get('RIGHT_ELBOW'))
    left_wrist = _point_from_landmark(landmarks.get('LEFT_WRIST'))
    right_wrist = _point_from_landmark(landmarks.get('RIGHT_WRIST'))

    shoulder_center = _midpoint_with_source(left_shoulder, right_shoulder, 'pose_midpoint') if left_shoulder and right_shoulder else None
    hip_center = _midpoint_with_source(left_hip, right_hip, 'pose_midpoint') if left_hip and right_hip else None
    shoulder_line = _build_line_if_points(left_shoulder, right_shoulder, width, height, 'pose_landmark')
    hip_line = _build_line_if_points(left_hip, right_hip, width, height, 'pose_landmark')
    spine_line = _build_line_if_points(hip_center, shoulder_center, width, height, 'pose_midpoint')
    left_arm_line = _build_line_if_points(left_elbow, left_wrist, width, height, 'pose_landmark')
    right_arm_line = _build_line_if_points(right_elbow, right_wrist, width, height, 'pose_landmark')
    spine_angle = spine_line.get('angleDegrees') if spine_line else None

    return {
        'leftElbow': left_elbow,
        'rightElbow': right_elbow,
        'leftShoulder': left_shoulder,
        'rightShoulder': right_shoulder,
        'leftHip': left_hip,
        'rightHip': right_hip,
        'shoulderLine': shoulder_line,
        'hipLine': hip_line,
        'spineLine': spine_line,
        'leftForearmLine': left_arm_line,
        'rightForearmLine': right_arm_line,
        'bodyMetrics': {
            'spineAngleDegrees': _safe_round(spine_angle),
            'shoulderLineAngleDegrees': shoulder_line.get('angleDegrees') if shoulder_line else None,
            'hipLineAngleDegrees': hip_line.get('angleDegrees') if hip_line else None,
            'shoulderHipSeparationDegrees': _safe_round(
                abs((shoulder_line.get('angleDegrees') if shoulder_line else 0) - (hip_line.get('angleDegrees') if hip_line else 0))
            ) if shoulder_line and hip_line else None,
        },
    }


def _build_head_metrics(
    face_points: Dict[str, object],
    width: int,
    height: int,
) -> Dict[str, object]:
    left_eye = face_points.get('leftEye')
    right_eye = face_points.get('rightEye')
    nose = face_points.get('nose')
    head_center = face_points.get('headCenter')
    source = str(face_points.get('source') or 'pose_estimate')
    eye_line = _build_line_if_points(left_eye, right_eye, width, height, source)
    head_direction = _build_line_if_points(head_center, nose, width, height, source)

    turn_proxy = None
    down_proxy = None
    if left_eye and right_eye and nose and head_center:
        eye_width = max(_line_length_px(left_eye, right_eye, width, height), 1)
        nose_x, nose_y = _normalized_to_pixel(nose, width, height)
        center_x, center_y = _normalized_to_pixel(head_center, width, height)
        turn_proxy = _clamp((nose_x - center_x) / eye_width, -1, 1)
        down_proxy = _clamp((nose_y - center_y) / eye_width, -1, 1)

    return {
        'eyeLine': eye_line,
        'headDirection': head_direction,
        'headMetrics': {
            'source': source,
            'eyeLineAngleDegrees': eye_line.get('angleDegrees') if eye_line else None,
            'headDirectionAngleDegrees': head_direction.get('angleDegrees') if head_direction else None,
            'headTurnProxy': _safe_round(turn_proxy, 3),
            'eyesDownProxy': _safe_round(down_proxy, 3),
        },
    }


def _build_hand_metrics(
    body: Dict[str, object],
    hand_points: Dict[str, Point],
    club_head: Optional[Point],
    width: int,
    height: int,
) -> Dict[str, object]:
    left_elbow = body.get('leftElbow')
    right_elbow = body.get('rightElbow')
    left_forearm = body.get('leftForearmLine') or {}
    right_forearm = body.get('rightForearmLine') or {}
    left_wrist = hand_points.get('leftHandWrist') or left_forearm.get('end')
    right_wrist = hand_points.get('rightHandWrist') or right_forearm.get('end')
    left_hand_axis = hand_points.get('leftMiddleMcp') or club_head
    right_hand_axis = hand_points.get('rightMiddleMcp') or club_head

    left_angle = (
        _absolute_joint_angle_degrees(left_wrist, left_elbow, left_hand_axis, width, height)
        if left_wrist and left_elbow and left_hand_axis
        else None
    )
    right_angle = (
        _absolute_joint_angle_degrees(right_wrist, right_elbow, right_hand_axis, width, height)
        if right_wrist and right_elbow and right_hand_axis
        else None
    )
    source = 'hand_landmark' if hand_points else 'club_proxy'
    return {
        'leftHandWrist': hand_points.get('leftHandWrist'),
        'rightHandWrist': hand_points.get('rightHandWrist'),
        'leftIndexMcp': hand_points.get('leftIndexMcp'),
        'rightIndexMcp': hand_points.get('rightIndexMcp'),
        'leftMiddleMcp': hand_points.get('leftMiddleMcp'),
        'rightMiddleMcp': hand_points.get('rightMiddleMcp'),
        'leftPalmCenter': hand_points.get('leftPalmCenter'),
        'rightPalmCenter': hand_points.get('rightPalmCenter'),
        'handMetrics': {
            'source': source,
            'leftWristAngleDegrees': left_angle,
            'rightWristAngleDegrees': right_angle,
            'handLandmarksDetected': bool(hand_points),
        },
    }


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
    point_keys = (
        'leftWrist',
        'rightWrist',
        'grip',
        'clubHead',
        'leftHandWrist',
        'rightHandWrist',
        'leftIndexMcp',
        'rightIndexMcp',
        'leftMiddleMcp',
        'rightMiddleMcp',
        'leftPalmCenter',
        'rightPalmCenter',
        'leftEye',
        'rightEye',
        'nose',
        'chin',
        'headCenter',
        'leftElbow',
        'rightElbow',
        'leftShoulder',
        'rightShoulder',
        'leftHip',
        'rightHip',
    )
    for index, frame_data in enumerate(frames):
        window = frames[max(0, index - 1):min(len(frames), index + 2)]
        next_frame = {**frame_data}
        for key in point_keys:
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
        next_frame['eyeLine'] = _build_line_if_points(next_frame.get('leftEye'), next_frame.get('rightEye'), width, height, str((next_frame.get('leftEye') or {}).get('source') or 'pose_estimate'))
        next_frame['headDirection'] = _build_line_if_points(next_frame.get('headCenter'), next_frame.get('nose'), width, height, str((next_frame.get('nose') or {}).get('source') or 'pose_estimate'))
        shoulder_center = _midpoint_with_source(next_frame['leftShoulder'], next_frame['rightShoulder'], 'pose_midpoint') if next_frame.get('leftShoulder') and next_frame.get('rightShoulder') else None
        hip_center = _midpoint_with_source(next_frame['leftHip'], next_frame['rightHip'], 'pose_midpoint') if next_frame.get('leftHip') and next_frame.get('rightHip') else None
        next_frame['shoulderLine'] = _build_line_if_points(next_frame.get('leftShoulder'), next_frame.get('rightShoulder'), width, height, 'pose_landmark')
        next_frame['hipLine'] = _build_line_if_points(next_frame.get('leftHip'), next_frame.get('rightHip'), width, height, 'pose_landmark')
        next_frame['spineLine'] = _build_line_if_points(hip_center, shoulder_center, width, height, 'pose_midpoint')
        next_frame['leftForearmLine'] = _build_line_if_points(next_frame.get('leftElbow'), next_frame.get('leftWrist'), width, height, 'pose_landmark')
        next_frame['rightForearmLine'] = _build_line_if_points(next_frame.get('rightElbow'), next_frame.get('rightWrist'), width, height, 'pose_landmark')
        hand_points = {
            key: next_frame.get(key)
            for key in (
                'leftHandWrist',
                'rightHandWrist',
                'leftIndexMcp',
                'rightIndexMcp',
                'leftMiddleMcp',
                'rightMiddleMcp',
                'leftPalmCenter',
                'rightPalmCenter',
            )
            if next_frame.get(key)
        }
        next_frame.update(_build_hand_metrics(next_frame, hand_points, club_head, width, height))
        shaft_angle = next_frame['clubShaft'].get('angleDegrees') if isinstance(next_frame.get('clubShaft'), dict) else None
        next_frame['clubMetrics'] = {
            'shaftAngleDegrees': shaft_angle,
            'shaftLeanFromVerticalDegrees': _safe_round(shaft_angle + 90) if isinstance(shaft_angle, (int, float)) else None,
            'clubHeadConfidence': float(club_head.get('confidence') or 0) if isinstance(club_head, dict) else 0,
            'clubDetectionSource': str(club_head.get('source') or 'unavailable') if isinstance(club_head, dict) else 'unavailable',
        }
        next_frame['headMetrics'] = _build_head_metrics(next_frame, width, height).get('headMetrics', {})
        shoulder_line = next_frame.get('shoulderLine')
        hip_line = next_frame.get('hipLine')
        next_frame['bodyMetrics'] = {
            'spineAngleDegrees': next_frame.get('spineLine', {}).get('angleDegrees') if isinstance(next_frame.get('spineLine'), dict) else None,
            'shoulderLineAngleDegrees': shoulder_line.get('angleDegrees') if isinstance(shoulder_line, dict) else None,
            'hipLineAngleDegrees': hip_line.get('angleDegrees') if isinstance(hip_line, dict) else None,
            'shoulderHipSeparationDegrees': _safe_round(
                abs((shoulder_line.get('angleDegrees') if isinstance(shoulder_line, dict) else 0) - (hip_line.get('angleDegrees') if isinstance(hip_line, dict) else 0))
            ) if isinstance(shoulder_line, dict) and isinstance(hip_line, dict) else None,
        }
        next_frame['quality'] = {
            'bodyDetected': bool(next_frame.get('leftWrist') or next_frame.get('rightWrist')),
            'handsDetected': bool(hand_points),
            'faceDetected': str((next_frame.get('headMetrics') or {}).get('source')) == 'face_landmark',
            'headPoseEstimated': bool(next_frame.get('headDirection')),
            'clubDetected': isinstance(club_head, dict) and float(club_head.get('confidence') or 0) >= MIN_CLUB_CONFIDENCE_FOR_SUMMARY,
        }

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
    hand_landmarker: Optional[vision.HandLandmarker] = None,
    face_landmarker: Optional[vision.FaceLandmarker] = None,
) -> TrackingFrame:
    height, width = frame.shape[:2] if frame.size else (int(metadata.get('height') or 0), int(metadata.get('width') or 0))
    landmarks = _landmark_map(pose_frame)
    left_wrist = _point_from_landmark(landmarks.get('LEFT_WRIST'))
    right_wrist = _point_from_landmark(landmarks.get('RIGHT_WRIST'))
    grip = _midpoint(left_wrist, right_wrist) if left_wrist and right_wrist else left_wrist or right_wrist
    input_image = _create_mp_image(frame) if frame.size and (hand_landmarker or face_landmarker) else None
    body_tracking = _build_body_tracking(landmarks, width, height)
    face_points = _extract_face_points(input_image, face_landmarker, landmarks)
    head_tracking = _build_head_metrics(face_points, width, height) if face_points else {'headMetrics': {'source': 'unavailable'}}

    tracking_frame: TrackingFrame = {
        'frameIndex': int(pose_frame.get('frameIndex') or 0),
        'timestampMs': int(pose_frame.get('timestampMs') or 0),
        'leftWrist': left_wrist,
        'rightWrist': right_wrist,
        'grip': grip,
        'clubHead': None,
        'clubShaft': None,
        **body_tracking,
        **{key: value for key, value in face_points.items() if key != 'source'},
        **head_tracking,
    }

    if width > 0 and height > 0:
        detected = _detect_club_line(frame, grip)
        if detected:
            tracking_frame.update(detected)

    club_head = tracking_frame.get('clubHead')
    club_shaft = tracking_frame.get('clubShaft')
    hand_points = _extract_hand_points(frame, input_image, hand_landmarker, left_wrist, right_wrist, width, height)
    tracking_frame.update(_build_hand_metrics(body_tracking, hand_points, club_head, width, height))
    shaft_angle = club_shaft.get('angleDegrees') if isinstance(club_shaft, dict) else None
    tracking_frame['clubMetrics'] = {
        'shaftAngleDegrees': shaft_angle,
        'shaftLeanFromVerticalDegrees': _safe_round(shaft_angle + 90) if isinstance(shaft_angle, (int, float)) else None,
        'clubHeadConfidence': float(club_head.get('confidence') or 0) if isinstance(club_head, dict) else 0,
        'clubDetectionSource': str(club_head.get('source') or 'unavailable') if isinstance(club_head, dict) else 'unavailable',
    }
    tracking_frame['quality'] = {
        'bodyDetected': bool(left_wrist or right_wrist),
        'handsDetected': bool(hand_points),
        'faceDetected': bool(face_points and face_points.get('source') == 'face_landmark'),
        'headPoseEstimated': bool(head_tracking.get('headDirection')),
        'clubDetected': isinstance(club_head, dict) and float(club_head.get('confidence') or 0) >= MIN_CLUB_CONFIDENCE_FOR_SUMMARY,
    }

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


def _numeric_values(frames: List[TrackingFrame], group_key: str, metric_key: str) -> List[float]:
    values: List[float] = []
    for frame_data in frames:
        group = frame_data.get(group_key)
        if isinstance(group, dict) and isinstance(group.get(metric_key), (int, float)):
            values.append(float(group[metric_key]))
    return values


def _average(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _nearest_frame(frames: List[TrackingFrame], timestamp_ms: Optional[int]) -> Optional[TrackingFrame]:
    if timestamp_ms is None or not frames:
        return None
    return min(frames, key=lambda frame: abs(int(frame.get('timestampMs') or 0) - timestamp_ms))


def _select_hand_landmark_frame_indices(
    pose_frames: List[Dict[str, object]],
    phases: Optional[Dict[str, object]],
) -> set:
    if not pose_frames:
        return set()

    selected = set()
    phase_keys = ('address', 'takeaway', 'topOfBackswing', 'impact', 'finish')
    for phase_key in phase_keys:
        if phases and phases.get(phase_key) is not None:
            target = int(phases[phase_key])
            nearest = min(pose_frames, key=lambda frame: abs(int(frame.get('timestampMs') or 0) - target))
            selected.add(int(nearest.get('frameIndex') or 0))

    if len(selected) < MAX_HAND_LANDMARK_FRAMES:
        step = max(1, len(pose_frames) // MAX_HAND_LANDMARK_FRAMES)
        for pose_frame in pose_frames[::step]:
            selected.add(int(pose_frame.get('frameIndex') or 0))
            if len(selected) >= MAX_HAND_LANDMARK_FRAMES:
                break

    return selected


def _phase_metric(
    frames: List[TrackingFrame],
    phases: Optional[Dict[str, object]],
    phase_key: str,
    group_key: str,
    metric_key: str,
) -> Optional[float]:
    if not phases:
        return None
    frame_data = _nearest_frame(frames, int(phases[phase_key])) if phases.get(phase_key) is not None else None
    group = frame_data.get(group_key) if frame_data else None
    if isinstance(group, dict) and isinstance(group.get(metric_key), (int, float)):
        return round(float(group[metric_key]), 2)
    return None


def _confidence(value: object) -> float:
    try:
        return _clamp(float(value or 0), 0, 1)
    except (TypeError, ValueError):
        return 0


def _face_bucket_from_degrees(angle_degrees: Optional[float], confidence: float) -> str:
    if angle_degrees is None or confidence < 0.2:
        return 'unknown'
    if abs(angle_degrees) <= 2:
        return 'square'
    return 'open' if angle_degrees > 0 else 'closed'


def _path_bucket_from_degrees(path_degrees: Optional[float], confidence: float) -> str:
    if path_degrees is None or confidence < 0.2:
        return 'unknown'
    if abs(path_degrees) <= 3:
        return 'neutral'
    return 'in_to_out' if path_degrees > 0 else 'out_to_in'


def _launch_direction_face_degrees(ball_flight_summary: Dict[str, object]) -> Tuple[Optional[float], str, float]:
    ball_confidence = _confidence(ball_flight_summary.get('confidence'))
    launch_direction = ball_flight_summary.get('launchDirection')
    if (
        ball_confidence < 0.35
        or not isinstance(launch_direction, str)
        or launch_direction not in {'left', 'straight', 'right'}
    ):
        return None, 'unknown', ball_confidence

    # The ball tracker currently returns direction buckets, not calibrated horizontal
    # launch degrees. These degree values are bucket midpoints for LLM context only.
    degrees_by_direction = {
        'left': -6.0,
        'straight': 0.0,
        'right': 6.0,
    }
    estimated_degrees = degrees_by_direction[str(launch_direction)]
    return estimated_degrees, _face_bucket_from_degrees(estimated_degrees, ball_confidence), ball_confidence


def _impact_timestamp_ms(
    frames: List[TrackingFrame],
    phases: Optional[Dict[str, object]],
    tracking_summary: Optional[Dict[str, object]],
) -> Optional[int]:
    for candidate in (
        phases.get('impact') if phases else None,
        tracking_summary.get('estimatedImpactMs') if tracking_summary else None,
    ):
        try:
            if candidate is not None:
                return int(candidate)
        except (TypeError, ValueError):
            continue

    timestamps = [
        int(frame_data.get('timestampMs') or 0)
        for frame_data in frames
        if frame_data.get('timestampMs') is not None
    ]
    if not timestamps:
        return None
    return timestamps[len(timestamps) // 2]


def _club_path_proxy_around_impact(
    frames: List[TrackingFrame],
    metadata: Dict[str, object],
    impact_ms: Optional[int],
) -> Dict[str, object]:
    width = int(metadata.get('width') or 0)
    height = int(metadata.get('height') or 0)
    if not frames or width <= 0 or height <= 0:
        return {
            'clubPathProxy': 'unknown',
            'clubPathDegrees': None,
            'confidence': 0,
            'sampleCount': 0,
        }

    valid_samples = [
        frame_data
        for frame_data in frames
        if isinstance(frame_data.get('clubHead'), dict)
        and float(frame_data['clubHead'].get('confidence') or 0) >= MIN_CLUB_CONFIDENCE_FOR_SUMMARY
    ]
    if impact_ms is not None:
        impact_window = [
            frame_data
            for frame_data in valid_samples
            if abs(int(frame_data.get('timestampMs') or 0) - impact_ms) <= 450
        ]
        if len(impact_window) >= 2:
            valid_samples = impact_window

    valid_samples = sorted(valid_samples, key=lambda frame_data: int(frame_data.get('timestampMs') or 0))
    if len(valid_samples) < 2:
        return {
            'clubPathProxy': 'unknown',
            'clubPathDegrees': None,
            'confidence': 0,
            'sampleCount': len(valid_samples),
        }

    first = valid_samples[0]
    last = valid_samples[-1]
    first_point = first['clubHead']
    last_point = last['clubHead']
    first_x, first_y = _normalized_to_pixel(first_point, width, height)
    last_x, last_y = _normalized_to_pixel(last_point, width, height)
    dx_px = last_x - first_x
    dy_px = last_y - first_y
    distance_px = sqrt(dx_px * dx_px + dy_px * dy_px)
    vertical_scale = max(abs(dy_px), height * 0.08, 1)
    path_degrees = round(_clamp(degrees(atan2(dx_px, vertical_scale)), -14, 14), 2)
    average_confidence = (
        float(first_point.get('confidence') or 0) + float(last_point.get('confidence') or 0)
    ) / 2
    sample_factor = _clamp(len(valid_samples) / 5, 0.35, 1)
    motion_factor = _clamp(distance_px / max(width * 0.08, 1), 0.25, 1)
    confidence = _clamp(average_confidence * sample_factor * motion_factor, 0, 0.88)

    return {
        'clubPathProxy': _path_bucket_from_degrees(path_degrees, confidence),
        'clubPathDegrees': path_degrees,
        'confidence': round(confidence, 3),
        'sampleCount': len(valid_samples),
        'impactWindowMs': 450 if impact_ms is not None else None,
        'deltaXPx': round(dx_px, 2),
        'deltaYPx': round(dy_px, 2),
        'distancePx': round(distance_px, 2),
        'startTimestampMs': int(first.get('timestampMs') or 0),
        'endTimestampMs': int(last.get('timestampMs') or 0),
    }


def estimate_club_face_proxy(
    frames: List[TrackingFrame],
    metadata: Dict[str, object],
    phases: Optional[Dict[str, object]],
    ball_flight_summary: Optional[Dict[str, object]],
    tracking_summary: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Estimate impact delivery features useful to the LLM.

    This is intentionally a proxy. Normal phone video does not expose the true
    club-face plane at impact, so the estimate combines ball start direction and
    screen-space club-head path with confidence and limitations.
    """
    ball_flight_summary = ball_flight_summary or {}
    tracking_summary = tracking_summary or {}
    impact_ms = _impact_timestamp_ms(frames, phases, tracking_summary)
    estimated_face_degrees, face_to_target, ball_confidence = _launch_direction_face_degrees(ball_flight_summary)
    club_path = _club_path_proxy_around_impact(frames, metadata, impact_ms)
    path_degrees = club_path.get('clubPathDegrees') if isinstance(club_path.get('clubPathDegrees'), (int, float)) else None
    path_confidence = _confidence(club_path.get('confidence'))
    quality = tracking_summary.get('quality') if isinstance(tracking_summary.get('quality'), dict) else {}
    tracking_confidence = _confidence(quality.get('overallTrackingConfidence'))

    estimated_face_to_path = None
    if estimated_face_degrees is not None and path_degrees is not None and path_confidence >= 0.2:
        estimated_face_to_path = round(estimated_face_degrees - float(path_degrees), 2)

    face_to_path = _face_bucket_from_degrees(
        estimated_face_to_path,
        min(ball_confidence, path_confidence) if estimated_face_to_path is not None else 0,
    )
    confidence_parts = []
    if estimated_face_degrees is not None:
        confidence_parts.append(ball_confidence * 0.62)
    if path_degrees is not None:
        confidence_parts.append(path_confidence * 0.28)
    if tracking_confidence:
        confidence_parts.append(tracking_confidence * 0.10)
    confidence = _clamp(sum(confidence_parts), 0, 0.82)

    if face_to_target != 'unknown' and face_to_path != 'unknown':
        status = 'estimated'
    elif face_to_target != 'unknown' or club_path.get('clubPathProxy') != 'unknown':
        status = 'partial'
    else:
        status = 'insufficient_evidence'

    evidence = [
        f"Ball launch direction bucket: {ball_flight_summary.get('launchDirection') or 'unknown'}",
        f"Ball tracking confidence: {round(ball_confidence, 3)}",
        f"Club path proxy: {club_path.get('clubPathProxy')}",
        f"Club path proxy confidence: {club_path.get('confidence')}",
        f"Impact timestamp used: {impact_ms if impact_ms is not None else 'unknown'} ms",
    ]

    return {
        'status': status,
        'measurementType': 'video_proxy_not_launch_monitor',
        'faceToTarget': face_to_target,
        'faceToPath': face_to_path,
        'clubPathProxy': club_path.get('clubPathProxy'),
        'ballStartDirection': ball_flight_summary.get('launchDirection') or 'unknown',
        'estimatedDegreesToTarget': _safe_round(estimated_face_degrees),
        'estimatedDegreesToPath': _safe_round(estimated_face_to_path),
        'clubPathDegrees': _safe_round(path_degrees),
        'confidence': round(confidence, 3),
        'impactTimestampMs': impact_ms,
        'clubPathEvidence': club_path,
        'evidence': evidence,
        'assumptions': [
            'Positive/right bucket is treated as open to target for a right-handed down-the-line view.',
            'Club path is inferred from screen-space club-head motion near impact.',
        ],
        'limitations': [
            'This is not a measured club-face angle; it needs launch-monitor or calibrated multi-camera validation.',
            'Off-center strike, camera alignment, handedness, and motion blur can change the true face/path relationship.',
        ],
    }


def summarize_tracking_frames(
    frames: List[TrackingFrame],
    metadata: Dict[str, object],
    phases: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    width = int(metadata.get('width') or 0)
    height = int(metadata.get('height') or 0)
    if not frames or width <= 0 or height <= 0:
        return {
            'framesTracked': 0,
            'wristFrameCount': 0,
            'clubFrameCount': 0,
            'averageClubConfidence': 0,
            'handFrameCount': 0,
            'faceFrameCount': 0,
            'headFrameCount': 0,
            'bodyFrameCount': 0,
            'clubDetectionMethod': 'hough_line_near_hands',
            'golfMetrics': {},
            'quality': {
                'overallTrackingConfidence': 0,
                'needsRetake': True,
                'retakeReasons': ['No tracking frames were available.'],
            },
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
    hand_count = sum(1 for frame_data in frames if (frame_data.get('quality') or {}).get('handsDetected'))
    face_count = sum(1 for frame_data in frames if (frame_data.get('quality') or {}).get('faceDetected'))
    head_count = sum(1 for frame_data in frames if (frame_data.get('quality') or {}).get('headPoseEstimated'))
    body_count = sum(1 for frame_data in frames if (frame_data.get('quality') or {}).get('bodyDetected'))
    body_ratio = body_count / len(frames)
    hand_ratio = hand_count / len(frames)
    face_ratio = face_count / len(frames)
    head_ratio = head_count / len(frames)
    club_ratio = club_count / len(frames)
    left_wrist_angles = _numeric_values(frames, 'handMetrics', 'leftWristAngleDegrees')
    right_wrist_angles = _numeric_values(frames, 'handMetrics', 'rightWristAngleDegrees')
    shaft_angles = _numeric_values(frames, 'clubMetrics', 'shaftAngleDegrees')
    shaft_lean_values = _numeric_values(frames, 'clubMetrics', 'shaftLeanFromVerticalDegrees')
    eye_line_values = _numeric_values(frames, 'headMetrics', 'eyeLineAngleDegrees')
    head_turn_values = _numeric_values(frames, 'headMetrics', 'headTurnProxy')
    spine_values = _numeric_values(frames, 'bodyMetrics', 'spineAngleDegrees')
    overall_confidence = _clamp(
        0.34 * body_ratio
        + 0.24 * club_ratio
        + 0.18 * hand_ratio
        + 0.14 * head_ratio
        + 0.10 * (sum(club_confidences) / len(club_confidences) if club_confidences else 0),
        0,
        1,
    )
    critical_retake_reasons: List[str] = []
    advisory_reasons: List[str] = []
    if club_ratio < 0.35:
        critical_retake_reasons.append('Club shaft/head was visible in fewer than 35% of tracked frames.')
    if body_ratio < 0.75:
        critical_retake_reasons.append('Full body landmarks were missing too often for reliable posture analysis.')
    if hand_ratio < 0.25:
        advisory_reasons.append('Detailed hand landmarks were limited, so wrist angles use lower-confidence proxies.')
    if head_ratio < 0.45:
        advisory_reasons.append('Head/eye direction was not consistently visible.')
    retake_reasons = [*critical_retake_reasons, *advisory_reasons]

    return {
        'framesTracked': len(frames),
        'wristFrameCount': min(left_count, right_count) if left_count and right_count else max(left_count, right_count),
        'clubFrameCount': club_count,
        'handFrameCount': hand_count,
        'faceFrameCount': face_count,
        'headFrameCount': head_count,
        'bodyFrameCount': body_count,
        'averageClubConfidence': round(sum(club_confidences) / len(club_confidences), 3) if club_confidences else 0,
        'leftWristPathLengthPx': round(left_path, 2),
        'rightWristPathLengthPx': round(right_path, 2),
        'gripPathLengthPx': round(grip_path, 2),
        'clubHeadPathLengthPx': round(club_path, 2),
        'maxGripSpeedPxPerSec': round(grip_speed, 2),
        'maxClubHeadSpeedPxPerSec': round(club_speed, 2),
        'estimatedImpactMs': impact_ms,
        'clubDetectionMethod': 'pose_hands_face_plus_hough_line_temporal',
        'golfMetrics': {
            'averageLeftWristAngleDegrees': _safe_round(_average(left_wrist_angles)),
            'averageRightWristAngleDegrees': _safe_round(_average(right_wrist_angles)),
            'leftWristAngleAtAddress': _phase_metric(frames, phases, 'address', 'handMetrics', 'leftWristAngleDegrees'),
            'rightWristAngleAtAddress': _phase_metric(frames, phases, 'address', 'handMetrics', 'rightWristAngleDegrees'),
            'leftWristAngleAtTop': _phase_metric(frames, phases, 'topOfBackswing', 'handMetrics', 'leftWristAngleDegrees'),
            'rightWristAngleAtTop': _phase_metric(frames, phases, 'topOfBackswing', 'handMetrics', 'rightWristAngleDegrees'),
            'leftWristAngleAtImpact': _phase_metric(frames, phases, 'impact', 'handMetrics', 'leftWristAngleDegrees'),
            'rightWristAngleAtImpact': _phase_metric(frames, phases, 'impact', 'handMetrics', 'rightWristAngleDegrees'),
            'averageShaftAngleDegrees': _safe_round(_average(shaft_angles)),
            'shaftAngleAtAddress': _phase_metric(frames, phases, 'address', 'clubMetrics', 'shaftAngleDegrees'),
            'shaftAngleAtTop': _phase_metric(frames, phases, 'topOfBackswing', 'clubMetrics', 'shaftAngleDegrees'),
            'shaftAngleAtImpact': _phase_metric(frames, phases, 'impact', 'clubMetrics', 'shaftAngleDegrees'),
            'shaftLeanAtImpactDegrees': _phase_metric(frames, phases, 'impact', 'clubMetrics', 'shaftLeanFromVerticalDegrees'),
            'averageEyeLineAngleDegrees': _safe_round(_average(eye_line_values)),
            'eyeLineAngleAtAddress': _phase_metric(frames, phases, 'address', 'headMetrics', 'eyeLineAngleDegrees'),
            'eyeLineAngleAtImpact': _phase_metric(frames, phases, 'impact', 'headMetrics', 'eyeLineAngleDegrees'),
            'averageHeadTurnProxy': _safe_round(_average(head_turn_values), 3),
            'headTurnAtAddress': _phase_metric(frames, phases, 'address', 'headMetrics', 'headTurnProxy'),
            'headTurnAtImpact': _phase_metric(frames, phases, 'impact', 'headMetrics', 'headTurnProxy'),
            'averageSpineAngleDegrees': _safe_round(_average(spine_values)),
        },
        'quality': {
            'bodyFrameRatio': round(body_ratio, 3),
            'handFrameRatio': round(hand_ratio, 3),
            'faceFrameRatio': round(face_ratio, 3),
            'headFrameRatio': round(head_ratio, 3),
            'clubFrameRatio': round(club_ratio, 3),
            'overallTrackingConfidence': round(overall_confidence, 3),
            'needsRetake': overall_confidence < 0.55 or bool(critical_retake_reasons),
            'retakeReasons': retake_reasons,
        },
        'trackedFeatureSet': [
            'pose_body_landmarks',
            'hand_landmark_wrist_angles',
            'face_or_pose_eye_line',
            'hough_club_shaft_near_grip',
            'temporal_prediction_and_smoothing',
        ],
        'notes': (
            'Tracking frames combine pose body landmarks, optional MediaPipe hand and face landmarks, '
            'OpenCV shaft candidates near the grip, temporal repair, and confidence gates. Eye direction '
            'is a head/eye-line proxy, not a calibrated gaze vector.'
        ),
    }


def extract_swing_tracking(
    video_path: str,
    pose_frames: List[Dict[str, object]],
    metadata: Dict[str, object],
    phases: Optional[Dict[str, object]] = None,
) -> Tuple[List[TrackingFrame], Dict[str, object]]:
    if not pose_frames:
        return [], summarize_tracking_frames([], metadata, phases)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        tracking_frames = [
            track_swing_points_for_frame(np.empty((0, 0, 3), dtype=np.uint8), pose_frame, metadata)
            for pose_frame in pose_frames
        ]
        tracking_frames = _smooth_tracking_frames(_predict_missing_club_points(tracking_frames, metadata), metadata)
        return tracking_frames, summarize_tracking_frames(tracking_frames, metadata, phases)

    tracking_frames: List[TrackingFrame] = []
    hand_landmarker = _create_hand_landmarker() if settings.enable_detailed_hand_tracking else None
    # Pose already exposes nose/eye landmarks on the full-body frames. Running FaceLandmarker
    # on every golf frame is too slow for local testing, so face tracking stays as a pose proxy
    # unless a future calibrated gaze module needs dense face landmarks.
    face_landmarker = None
    hand_frame_indices = _select_hand_landmark_frame_indices(pose_frames, phases)
    hand_miss_count = 0
    try:
        for pose_frame in pose_frames:
            frame_index = int(pose_frame.get('frameIndex') or 0)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                frame = np.empty((0, 0, 3), dtype=np.uint8)
            use_hand_landmarker = (
                hand_landmarker
                if frame_index in hand_frame_indices and hand_miss_count < 3
                else None
            )
            tracking = track_swing_points_for_frame(frame, pose_frame, metadata, use_hand_landmarker, face_landmarker)
            if use_hand_landmarker and not (tracking.get('quality') or {}).get('handsDetected'):
                hand_miss_count += 1
            tracking_frames.append(tracking)
    finally:
        if hand_landmarker is not None:
            hand_landmarker.close()
        if face_landmarker is not None:
            face_landmarker.close()
        cap.release()

    tracking_frames = _predict_missing_club_points(tracking_frames, metadata)
    tracking_frames = _smooth_tracking_frames(tracking_frames, metadata)
    return tracking_frames, summarize_tracking_frames(tracking_frames, metadata, phases)
