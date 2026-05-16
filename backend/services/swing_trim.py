import base64
import json
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

import cv2

from config import settings


SWING_TRIM_PROMPT = (
    'You are selecting the actual golf swing window from sampled video frames. '
    'Return strict JSON with startMs, endMs, confidence, and notes. '
    'startMs should be the address/start of takeaway, and endMs should be the balanced finish. '
    'Prefer the full swing over cutting off the takeaway, impact, or finish.'
)
PRE_SWING_PREROLL_MS = 2000
POST_SWING_PAD_MS = 250
BALL_FLIGHT_POSTROLL_MS = 3500


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _start_with_preroll(detected_start_ms: int) -> int:
    return max(0, int(detected_start_ms) - PRE_SWING_PREROLL_MS)


def _preroll_included_ms(detected_start_ms: int, window_start_ms: int) -> int:
    return max(0, int(detected_start_ms) - int(window_start_ms))


def _landmark_map(frame_data: Dict[str, object]) -> Dict[str, Dict[str, float]]:
    return {
        str(landmark.get('name')): landmark
        for landmark in frame_data.get('landmarks', [])
        if isinstance(landmark, dict) and landmark.get('name')
    }


def _point_distance(a: Optional[Dict[str, float]], b: Optional[Dict[str, float]]) -> float:
    if not a or not b:
        return 0.0

    ax = float(a.get('x') or 0)
    ay = float(a.get('y') or 0)
    bx = float(b.get('x') or 0)
    by = float(b.get('y') or 0)
    visibility = min(float(a.get('visibility') or 1), float(b.get('visibility') or 1))
    return (((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5) * _clamp(visibility, 0.15, 1)


def _frame_motion(previous: Dict[str, object], current: Dict[str, object]) -> float:
    previous_points = _landmark_map(previous)
    current_points = _landmark_map(current)
    tracked_names = (
        'LEFT_WRIST',
        'RIGHT_WRIST',
        'LEFT_ELBOW',
        'RIGHT_ELBOW',
        'LEFT_SHOULDER',
        'RIGHT_SHOULDER',
        'LEFT_HIP',
        'RIGHT_HIP',
    )
    distances = [
        _point_distance(previous_points.get(name), current_points.get(name))
        for name in tracked_names
        if previous_points.get(name) and current_points.get(name)
    ]
    return sum(distances) / len(distances) if distances else 0.0


def _wrist_height(frame_data: Dict[str, object]) -> float:
    points = _landmark_map(frame_data)
    wrists = [
        points.get('LEFT_WRIST'),
        points.get('RIGHT_WRIST'),
    ]
    visible_wrists = [wrist for wrist in wrists if wrist]
    if not visible_wrists:
        return 1.0
    return sum(float(wrist.get('y') or 1.0) for wrist in visible_wrists) / len(visible_wrists)


def _median(values: List[float]) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _frame_at_or_after(frames: List[Dict[str, object]], timestamp_ms: int) -> Dict[str, object]:
    for frame_data in frames:
        if int(frame_data.get('timestampMs') or 0) >= timestamp_ms:
            return frame_data
    return frames[-1]


def _frame_at_or_before(frames: List[Dict[str, object]], timestamp_ms: int) -> Dict[str, object]:
    for frame_data in reversed(frames):
        if int(frame_data.get('timestampMs') or 0) <= timestamp_ms:
            return frame_data
    return frames[0]


def estimate_swing_window_from_pose(
    frames: List[Dict[str, object]],
    metadata: Dict[str, object],
) -> Tuple[Dict[str, object], Dict[str, Optional[int]]]:
    duration_ms = int(metadata.get('durationMs') or 0)
    if not frames:
        end_ms = duration_ms if duration_ms > 0 else 0
        return {
            'startMs': 0,
            'detectedStartMs': 0,
            'detectedEndMs': end_ms,
            'endMs': end_ms,
            'startFrameIndex': 0,
            'endFrameIndex': 0,
            'preRollMs': 0,
            'postRollMs': 0,
            'method': 'fallback_full_video',
            'confidence': 0,
            'notes': 'No pose frames were available, so the full video was kept.',
        }, {'address': 0, 'finish': end_ms}

    if len(frames) < 4:
        detected_start_ms = int(frames[0].get('timestampMs') or 0)
        start_ms = _start_with_preroll(detected_start_ms)
        detected_end_ms = int(frames[-1].get('timestampMs') or duration_ms or start_ms)
        end_ceiling = duration_ms if duration_ms > 0 else detected_end_ms
        end_ms = min(end_ceiling, detected_end_ms + BALL_FLIGHT_POSTROLL_MS)
        return {
            'startMs': start_ms,
            'detectedStartMs': detected_start_ms,
            'detectedEndMs': detected_end_ms,
            'endMs': end_ms,
            'startFrameIndex': int(frames[0].get('frameIndex') or 0),
            'endFrameIndex': int(frames[-1].get('frameIndex') or 0),
            'preRollMs': _preroll_included_ms(detected_start_ms, start_ms),
            'postRollMs': max(0, end_ms - detected_end_ms),
            'method': 'pose_motion_short_clip',
            'confidence': 0.35,
            'notes': 'Few pose frames were available, so the detected pose span was kept.',
        }, {'address': detected_start_ms, 'finish': detected_end_ms}

    motions = [_frame_motion(frames[index - 1], frames[index]) for index in range(1, len(frames))]
    peak_motion = max(motions) if motions else 0
    median_motion = _median(motions)
    threshold = median_motion + (peak_motion - median_motion) * 0.28
    active_indices = [index + 1 for index, motion in enumerate(motions) if motion >= threshold and motion > 0.002]

    if not active_indices:
        active_indices = list(range(len(frames)))

    first_active = max(min(active_indices) - 2, 0)
    last_active = min(max(active_indices) + 2, len(frames) - 1)
    detected_start_ms = int(frames[first_active].get('timestampMs') or 0)
    raw_end_ms = int(frames[last_active].get('timestampMs') or detected_start_ms)
    start_ms = _start_with_preroll(detected_start_ms)
    end_ceiling = duration_ms if duration_ms > 0 else int(frames[-1].get('timestampMs') or raw_end_ms)
    detected_end_ms = min(end_ceiling, raw_end_ms + POST_SWING_PAD_MS)
    end_ms = min(end_ceiling, detected_end_ms + BALL_FLIGHT_POSTROLL_MS)

    if end_ms - start_ms < 900:
        midpoint = (start_ms + end_ms) // 2
        start_ms = max(0, midpoint - 450)
        end_ms = min(end_ceiling, midpoint + 450)

    start_frame = _frame_at_or_after(frames, start_ms)
    end_frame = _frame_at_or_before(frames, end_ms)
    window_indices = list(range(first_active, last_active + 1))
    top_index = min(window_indices, key=lambda index: _wrist_height(frames[index]))
    downswing_motion_indices = [index for index in range(max(top_index + 1, 1), last_active + 1)]
    if downswing_motion_indices:
        impact_index = max(downswing_motion_indices, key=lambda index: motions[index - 1] if index > 0 else 0)
    else:
        impact_index = min(last_active, top_index + max((last_active - top_index) // 2, 1))
    top_ms = int(frames[top_index].get('timestampMs') or start_ms)
    impact_ms = int(frames[min(impact_index, len(frames) - 1)].get('timestampMs') or end_ms)
    confidence = _clamp(0.45 + min(peak_motion * 3.5, 0.4) + min(len(frames) / 180, 0.15), 0, 0.92)

    return {
        'startMs': int(start_ms),
        'detectedStartMs': int(detected_start_ms),
        'detectedEndMs': int(detected_end_ms),
        'endMs': int(end_ms),
        'startFrameIndex': int(start_frame.get('frameIndex') or 0),
        'endFrameIndex': int(end_frame.get('frameIndex') or 0),
        'preRollMs': _preroll_included_ms(detected_start_ms, start_ms),
        'postRollMs': max(0, int(end_ms) - int(detected_end_ms)),
        'method': 'pose_motion',
        'confidence': round(confidence, 2),
        'notes': 'Detected from wrist, elbow, shoulder, and hip motion in MediaPipe pose frames. Playback includes up to 2 seconds before the swing and up to 3.5 seconds after finish for ball flight.',
    }, {
        'address': int(detected_start_ms),
        'takeaway': int(max(detected_start_ms, top_ms - max((top_ms - detected_start_ms) // 2, 1))),
        'topOfBackswing': int(top_ms),
        'impact': int(impact_ms),
        'finish': int(detected_end_ms),
    }


def _sample_video_frames(video_path: str, max_frames: int) -> List[Dict[str, object]]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if not fps or not frame_count:
            return []

        samples: List[Dict[str, object]] = []
        step = max(frame_count // max_frames, 1)
        for frame_index in range(0, frame_count, step):
            if len(samples) >= max_frames:
                break

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                continue

            height, width = frame.shape[:2]
            max_side = max(width, height)
            if max_side > 768:
                scale = 768 / max_side
                frame = cv2.resize(frame, (int(width * scale), int(height * scale)))

            ok, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
            if not ok:
                continue

            samples.append({
                'frameIndex': frame_index,
                'timestampMs': int((frame_index / fps) * 1000),
                'dataUrl': 'data:image/jpeg;base64,' + base64.b64encode(encoded.tobytes()).decode('ascii'),
            })
        return samples
    finally:
        cap.release()


def _extract_response_text(response_body: Dict[str, object]) -> str:
    output_text = response_body.get('output_text')
    if isinstance(output_text, str):
        return output_text

    fragments: List[str] = []
    for output in response_body.get('output', []) if isinstance(response_body.get('output'), list) else []:
        for content in output.get('content', []) if isinstance(output, dict) else []:
            if isinstance(content, dict) and content.get('type') in {'output_text', 'text'}:
                text = content.get('text')
                if isinstance(text, str):
                    fragments.append(text)
    return '\n'.join(fragments)


def _parse_llm_window(text: str, duration_ms: int) -> Optional[Dict[str, object]]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None

    try:
        detected_start_ms = int(parsed['startMs'])
        detected_end_ms = int(parsed['endMs'])
    except (KeyError, TypeError, ValueError):
        return None

    if duration_ms > 0:
        detected_start_ms = int(_clamp(detected_start_ms, 0, duration_ms))
        detected_end_ms = int(_clamp(detected_end_ms, detected_start_ms, duration_ms))

    if detected_end_ms <= detected_start_ms:
        return None

    start_ms = _start_with_preroll(detected_start_ms)
    end_ms = min(duration_ms if duration_ms > 0 else detected_end_ms, detected_end_ms + BALL_FLIGHT_POSTROLL_MS)
    confidence = _clamp(float(parsed.get('confidence') or 0.6), 0, 1)
    notes = str(parsed.get('notes') or 'Refined from sampled video frames by the configured LLM.')
    return {
        'startMs': start_ms,
        'detectedStartMs': detected_start_ms,
        'detectedEndMs': detected_end_ms,
        'endMs': end_ms,
        'preRollMs': _preroll_included_ms(detected_start_ms, start_ms),
        'postRollMs': max(0, end_ms - detected_end_ms),
        'method': 'llm_vision',
        'confidence': round(confidence, 2),
        'notes': f'{notes[:180]} Playback includes lead-in before the swing and extra time after finish for ball flight.',
    }


def refine_swing_window_with_llm(
    video_path: str,
    proposed_window: Dict[str, object],
    metadata: Dict[str, object],
) -> Optional[Dict[str, object]]:
    if not settings.send_video_to_llm or not settings.openai_api_key:
        return None

    samples = _sample_video_frames(video_path, settings.llm_swing_trim_max_frames)
    if len(samples) < 2:
        return None

    content = [{
        'type': 'input_text',
        'text': (
            f'{SWING_TRIM_PROMPT}\n'
            f'Video duration: {metadata.get("durationMs", 0)} ms. '
            f'Heuristic proposal for the actual swing: start '
            f'{proposed_window.get("detectedStartMs", proposed_window.get("startMs"))} ms, '
            f'end {proposed_window.get("detectedEndMs", proposed_window.get("endMs"))} ms. '
            'Each image is a sampled frame; its timestamp is included immediately before the image.'
        ),
    }]
    for sample in samples:
        content.append({
            'type': 'input_text',
            'text': f'Frame {sample["frameIndex"]}, timestamp {sample["timestampMs"]} ms',
        })
        content.append({
            'type': 'input_image',
            'image_url': sample['dataUrl'],
            'detail': 'low',
        })

    request_body = json.dumps({
        'model': settings.llm_swing_trim_model,
        'input': [{'role': 'user', 'content': content}],
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'swing_trim_window',
                'strict': True,
                'schema': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'startMs': {'type': 'integer', 'minimum': 0},
                        'endMs': {'type': 'integer', 'minimum': 0},
                        'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                        'notes': {'type': 'string'},
                    },
                    'required': ['startMs', 'endMs', 'confidence', 'notes'],
                },
            },
        },
    }).encode('utf-8')
    request = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=request_body,
        headers={
            'Authorization': f'Bearer {settings.openai_api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response_body = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    return _parse_llm_window(_extract_response_text(response_body), int(metadata.get('durationMs') or 0))


def apply_swing_window(
    frames: List[Dict[str, object]],
    window: Dict[str, object],
) -> List[Dict[str, object]]:
    start_ms = int(window.get('startMs') or 0)
    end_ms = int(window.get('endMs') or start_ms)
    trimmed = [
        frame_data
        for frame_data in frames
        if start_ms <= int(frame_data.get('timestampMs') or 0) <= end_ms
    ]
    return trimmed or frames
