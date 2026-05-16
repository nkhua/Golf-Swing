from datetime import datetime
from math import atan2, degrees
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional, Tuple
import urllib.request
from uuid import uuid4

import cv2
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options
from mediapipe.tasks.python.vision.core import image as mp_image
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode

from config import settings
from services.club_tracking import extract_swing_tracking
from services.swing_trim import apply_swing_window, estimate_swing_window_from_pose, refine_swing_window_with_llm

MODEL_URL = 'https://storage.googleapis.com/mediapipe-tasks/pose_landmarker/pose_landmarker_full.task'
MODEL_PATH = Path(__file__).resolve().parent.parent / 'models' / 'pose_landmarker_full.task'
MODEL_PATH.parent.mkdir(exist_ok=True)
MAX_FRAMES_TO_ANALYZE = 90
MAX_POSE_IMAGE_SIDE = 720


def _download_model_asset() -> None:
    if MODEL_PATH.exists():
        return

    with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
        content = response.read()

    MODEL_PATH.write_bytes(content)


def _create_pose_landmarker() -> vision.PoseLandmarker:
    _download_model_asset()
    options = vision.PoseLandmarkerOptions(
        base_options=base_options.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=VisionTaskRunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return vision.PoseLandmarker.create_from_options(options)


def _resize_for_pose(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    max_side = max(width, height)
    if max_side <= MAX_POSE_IMAGE_SIDE:
        return frame

    scale = MAX_POSE_IMAGE_SIDE / max_side
    return cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)


def _log_stage(stage: str, duration_seconds: float) -> None:
    print(f'Swing analysis stage "{stage}" completed in {duration_seconds:.2f}s')


def _angle_between_points(a: Dict[str, float], b: Dict[str, float]) -> float:
    dx = b['x'] - a['x']
    dy = b['y'] - a['y']
    return degrees(atan2(dy, dx))


def _get_landmark(frame: List[Dict[str, float]], landmark: vision.PoseLandmark) -> Dict[str, float]:
    point = frame[landmark.value]
    if point['name'] != landmark.name:
        raise ValueError(f'Landmark index mismatch: expected {landmark.name}, got {point["name"]}')
    return point


def get_video_metadata(video_path: str) -> Dict[str, object]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f'Unable to open video: {video_path}')

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()

    duration_ms = int((frame_count / fps) * 1000) if fps else 0
    return {
        'fps': fps,
        'durationMs': duration_ms,
        'width': width,
        'height': height,
        'cameraAngle': 'down_the_line',
    }


def extract_pose_landmarks(video_path: str) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    started_at = perf_counter()
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f'Unable to open video: {video_path}')

    pose_landmarker = None
    frames: List[Dict[str, object]] = []
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_interval = max(1, frame_count // MAX_FRAMES_TO_ANALYZE) if frame_count else 1
    frame_index = 0

    try:
        pose_landmarker = _create_pose_landmarker()

        while True:
            has_frame, frame = cap.read()
            if not has_frame:
                break

            if frame_index % frame_interval != 0:
                frame_index += 1
                continue

            pose_frame = _resize_for_pose(frame)
            rgb_frame = cv2.cvtColor(pose_frame, cv2.COLOR_BGR2RGB)
            input_image = mp_image.Image(mp_image.ImageFormat.SRGB, np.asarray(rgb_frame))
            results = pose_landmarker.detect(input_image)

            if results.pose_landmarks:
                frame_landmarks: List[Dict[str, float]] = []
                pose_landmarks = results.pose_landmarks[0]
                for idx, landmark in enumerate(pose_landmarks):
                    frame_landmarks.append({
                        'name': vision.PoseLandmark(idx).name,
                        'x': float(landmark.x),
                        'y': float(landmark.y),
                        'z': float(landmark.z),
                        'visibility': float(getattr(landmark, 'visibility', 1.0)),
                    })
                timestamp_ms = int((frame_index / fps) * 1000) if fps else 0
                frames.append({
                    'frameIndex': frame_index,
                    'timestampMs': timestamp_ms,
                    'landmarks': frame_landmarks,
                })

            frame_index += 1
    finally:
        if pose_landmarker is not None:
            pose_landmarker.close()
        cap.release()
        _log_stage('pose_landmarks', perf_counter() - started_at)

    metadata = {
        'fps': fps,
        'durationMs': int((frame_count / fps) * 1000) if fps else 0,
        'width': width,
        'height': height,
        'cameraAngle': 'down_the_line',
    }
    return frames, metadata


def _legacy_tip(balance_score: int, hip_turn: Optional[float]) -> str:
    if balance_score < 50:
        return 'Your stance appears unstable. Keep your weight centered and ground your feet evenly.'
    if hip_turn is None:
        return 'Pose data was limited. Retake the swing with the full body visible for stronger feedback.'
    return 'Good back-view stability. Treat these early pose metrics as directional until calibrated.'


def compute_swing_metrics(frames: List[Dict[str, object]], metadata: Dict[str, object]) -> Dict[str, object]:
    shoulder_angles = []
    hip_angles = []
    balance_scores = []
    head_x_values = []
    hip_center_x_values = []

    for frame_data in frames:
        frame = frame_data.get('landmarks', [])
        try:
            left_shoulder = _get_landmark(frame, vision.PoseLandmark.LEFT_SHOULDER)
            right_shoulder = _get_landmark(frame, vision.PoseLandmark.RIGHT_SHOULDER)
            left_hip = _get_landmark(frame, vision.PoseLandmark.LEFT_HIP)
            right_hip = _get_landmark(frame, vision.PoseLandmark.RIGHT_HIP)
            left_ankle = _get_landmark(frame, vision.PoseLandmark.LEFT_ANKLE)
            right_ankle = _get_landmark(frame, vision.PoseLandmark.RIGHT_ANKLE)
            nose = _get_landmark(frame, vision.PoseLandmark.NOSE)
        except (IndexError, ValueError):
            continue

        shoulders_angle = abs(_angle_between_points(left_shoulder, right_shoulder))
        hips_angle = abs(_angle_between_points(left_hip, right_hip))
        shoulder_angles.append(min(shoulders_angle, 180 - shoulders_angle))
        hip_angles.append(min(hips_angle, 180 - hips_angle))

        shoulder_center_x = (left_shoulder['x'] + right_shoulder['x']) / 2
        hip_center_x = (left_hip['x'] + right_hip['x']) / 2
        ankle_center_x = (left_ankle['x'] + right_ankle['x']) / 2
        balance_offset = abs((shoulder_center_x + hip_center_x) / 2 - ankle_center_x)
        balance_scores.append(max(0, 100 - balance_offset * 300))
        head_x_values.append(nose['x'])
        hip_center_x_values.append(hip_center_x)

    if not shoulder_angles or not hip_angles:
        return {
            'biomechanics': {
                'confidence': 0,
            },
            'ballFlightEstimates': {
                'shotShape': 'unknown',
                'spinTendency': 'unknown',
                'confidence': 0,
            },
            'legacySummary': {
                'club_path': 'unknown',
                'spine_angle': 'undetected',
                'shoulder_rotation': 'undetected',
                'hip_rotation': 'undetected',
                'balance_score': 0,
                'tip': 'Unable to detect a full body pose. Please retake the swing with better back-view framing.',
            },
        }

    average_shoulder_angle = sum(shoulder_angles) / len(shoulder_angles)
    average_hip_angle = sum(hip_angles) / len(hip_angles)
    average_balance = sum(balance_scores) / len(balance_scores)
    width = float(metadata.get('width') or 0)
    head_movement_px = (max(head_x_values) - min(head_x_values)) * width if head_x_values else None
    sway_px = (max(hip_center_x_values) - min(hip_center_x_values)) * width if hip_center_x_values else None
    balance_score = int(min(max(average_balance, 0), 100))

    return {
        'biomechanics': {
            # These values are measured from the sampled video landmarks. They should be
            # calibrated against ground-truth motion capture before being treated as final.
            'spineAngleAtAddress': round(average_shoulder_angle, 2),
            'shoulderTurnAtTop': round(max(shoulder_angles), 2),
            'hipTurnAtTop': round(max(hip_angles), 2),
            'headMovementPx': round(head_movement_px, 2) if head_movement_px is not None else None,
            'swayPx': round(sway_px, 2) if sway_px is not None else None,
            'confidence': round(min(len(frames) / 30, 1), 2),
        },
        'ballFlightEstimates': {
            # Pose-only ball flight is a rough estimate and needs launch-monitor calibration.
            'shotShape': 'unknown',
            'spinTendency': 'unknown',
            'confidence': 0.05,
        },
        'legacySummary': {
            'club_path': 'back-view estimate',
            'spine_angle': 'measured from pose',
            'shoulder_rotation': 'measured from pose',
            'hip_rotation': 'measured from pose',
            'balance_score': balance_score,
            'tip': _legacy_tip(balance_score, max(hip_angles) if hip_angles else None),
        },
    }


def analyze_swing(video_path: str) -> dict:
    started_at = perf_counter()
    frames, metadata = extract_pose_landmarks(video_path)
    pose_done_at = perf_counter()
    swing_window, phases = estimate_swing_window_from_pose(frames, metadata)
    llm_window = refine_swing_window_with_llm(video_path, swing_window, metadata)
    trim_done_at = perf_counter()
    if llm_window:
        swing_window = {**swing_window, **llm_window}
        if frames:
            start_frame = next((frame for frame in frames if frame['timestampMs'] >= swing_window['startMs']), frames[0])
            end_frame = next((frame for frame in reversed(frames) if frame['timestampMs'] <= swing_window['endMs']), frames[-1])
            swing_window['startFrameIndex'] = start_frame['frameIndex']
            swing_window['endFrameIndex'] = end_frame['frameIndex']
            phases = {
                **phases,
                'address': swing_window.get('detectedStartMs', swing_window['startMs']),
                'finish': swing_window['endMs'],
            }

    trimmed_frames = apply_swing_window(frames, swing_window)
    tracking_frames, tracking_summary = extract_swing_tracking(video_path, trimmed_frames, metadata, phases)
    tracking_done_at = perf_counter()
    analysis = compute_swing_metrics(trimmed_frames, metadata)
    metrics_done_at = perf_counter()
    legacy_summary = analysis.get('legacySummary', {})
    video_frames_sent_to_llm = bool(settings.send_video_to_llm and settings.openai_api_key)
    payload = {
        'swingId': uuid4().hex,
        'source': 'server',
        'videoMetadata': metadata,
        'swingWindow': swing_window,
        'phases': phases,
        'poseFrames': trimmed_frames,
        'trackingFrames': tracking_frames,
        'trackingSummary': tracking_summary,
        'biomechanics': analysis['biomechanics'],
        'ballFlightEstimates': analysis.get('ballFlightEstimates'),
        'privacy': {
            'rawVideoUploaded': True,
            'userConsentedToUpload': True,
            'videoFramesSentToLlm': video_frames_sent_to_llm,
        },
        'analysisTime': datetime.utcnow().isoformat() + 'Z',
        'framesAnalyzed': len(trimmed_frames),
        **legacy_summary,
    }
    _log_stage('swing_window_and_llm_refinement', trim_done_at - pose_done_at)
    _log_stage('wrist_and_club_tracking', tracking_done_at - trim_done_at)
    _log_stage('metrics', metrics_done_at - tracking_done_at)
    _log_stage('total', perf_counter() - started_at)
    return payload
