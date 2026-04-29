from pathlib import Path
from typing import Any, Dict, Optional
import time
import warnings

from config import SECRET_KEYS, Settings, settings
from schemas import SwingAnalysisPayload, dump_model


REDACTED = '[REDACTED]'
SENSITIVE_NAME_PARTS = ('secret', 'token', 'password', 'api_key', 'authorization', 'database_url')


def redact_value(key: str, value: Any) -> Any:
    normalized = key.lower()
    if key.upper() in SECRET_KEYS or any(part in normalized for part in SENSITIVE_NAME_PARTS):
        return REDACTED
    return value


def redact_mapping(data: Dict[str, Any]) -> Dict[str, Any]:
    redacted: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        else:
            redacted[key] = redact_value(key, value)
    return redacted


def sanitize_log_payload(payload: SwingAnalysisPayload, active_settings: Settings = settings) -> Dict[str, Any]:
    data = {
        'swingId': payload.swingId,
        'source': payload.source,
        'privacy': dump_model(payload.privacy),
        'videoMetadata': dump_model(payload.videoMetadata, exclude_none=True),
    }

    if active_settings.log_sensitive_data:
        data['biomechanics'] = dump_model(payload.biomechanics, exclude_none=True)

    if active_settings.log_sensitive_data and not active_settings.save_pose_data_only:
        data['poseFrames'] = [dump_model(frame, exclude_none=True) for frame in payload.poseFrames]

    return redact_mapping(data)


def assert_video_upload_allowed(user_consented: bool, active_settings: Settings = settings) -> None:
    if not active_settings.allow_video_upload:
        raise PermissionError('Video upload is disabled by ALLOW_VIDEO_UPLOAD=false.')

    if active_settings.require_user_video_upload_consent and not user_consented:
        raise PermissionError('Video upload requires explicit user consent.')


def should_store_raw_video(active_settings: Settings = settings) -> bool:
    return active_settings.allow_video_upload and active_settings.store_raw_video


def maybe_delete_raw_video(path: Optional[Path], active_settings: Settings = settings) -> bool:
    if not path or not path.exists():
        return False

    if active_settings.delete_raw_video_after_analysis or not should_store_raw_video(active_settings):
        for attempt in range(3):
            try:
                path.unlink(missing_ok=True)
                return True
            except PermissionError:
                if attempt == 2:
                    warnings.warn(
                        f'Could not delete temporary raw video because it is still locked: {path}',
                        RuntimeWarning,
                    )
                    return False
                time.sleep(0.2)

    return False


def build_llm_payload(payload: SwingAnalysisPayload, active_settings: Settings = settings) -> Dict[str, Any]:
    if active_settings.send_video_to_llm:
        raise PermissionError('Raw video LLM payloads are blocked by safety policy.')

    llm_payload: Dict[str, Any] = {
        'swingId': payload.swingId,
        'source': payload.source,
        'videoMetadata': dump_model(payload.videoMetadata, exclude_none=True),
        'phases': dump_model(payload.phases, exclude_none=True),
        'biomechanics': dump_model(payload.biomechanics, exclude_none=True),
        'ballFlightEstimates': dump_model(payload.ballFlightEstimates, exclude_none=True)
        if payload.ballFlightEstimates
        else None,
    }

    if active_settings.send_pose_data_to_llm:
        llm_payload['poseFrames'] = [dump_model(frame, exclude_none=True) for frame in payload.poseFrames]

    if active_settings.send_only_summarized_metrics_to_llm:
        llm_payload.pop('poseFrames', None)

    return {key: value for key, value in llm_payload.items() if value is not None}
