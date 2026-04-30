import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


TRUTHY = {'1', 'true', 'yes', 'on'}
FALSY = {'0', 'false', 'no', 'off', ''}
SECRET_KEYS = {'OPENAI_API_KEY', 'DATABASE_URL', 'STORAGE_BUCKET', 'JWT_SECRET'}
KNOWN_ENV_KEYS = {
    'APP_ENV',
    'DEBUG',
    'BACKEND_HOST',
    'BACKEND_PORT',
    'ALLOW_EXTERNAL_CONNECTIONS',
    'ENABLE_PUBLIC_TUNNEL',
    'PROCESS_ON_DEVICE',
    'ALLOW_VIDEO_UPLOAD',
    'STORE_RAW_VIDEO',
    'REQUIRE_USER_VIDEO_UPLOAD_CONSENT',
    'DELETE_RAW_VIDEO_AFTER_ANALYSIS',
    'SAVE_POSE_DATA_ONLY',
    'LOG_SENSITIVE_DATA',
    'STORE_FRAME_IMAGES',
    'STORE_DEBUG_OVERLAYS',
    'ANONYMIZE_USER_DATA',
    'SEND_VIDEO_TO_LLM',
    'SEND_POSE_DATA_TO_LLM',
    'SEND_ONLY_SUMMARIZED_METRICS_TO_LLM',
    'LLM_SWING_TRIM_MODEL',
    'LLM_SWING_TRIM_MAX_FRAMES',
    *SECRET_KEYS,
}


class ConfigError(ValueError):
    pass


def _parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value

    return values


def find_env_files() -> Iterable[Path]:
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    return (
        project_root / '.env',
        backend_dir / '.env',
        project_root / 'mobile' / '.env',
    )


def load_env_values() -> Dict[str, str]:
    loaded: Dict[str, str] = {}
    for env_path in find_env_files():
        loaded.update(_parse_env_file(env_path))

    merged = dict(loaded)
    for key in KNOWN_ENV_KEYS:
        if key not in merged or (key in SECRET_KEYS and not merged.get(key)):
            if key in os.environ:
                merged[key] = os.environ[key]
    return merged


def _bool_value(values: Dict[str, str], key: str, default: bool) -> bool:
    raw = str(values.get(key, str(default))).strip().lower()
    if raw in TRUTHY:
        return True
    if raw in FALSY:
        return False
    raise ConfigError(f'{key} must be a boolean value.')


def _int_value(values: Dict[str, str], key: str, default: int) -> int:
    raw = values.get(key, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f'{key} must be an integer.') from exc


def _str_value(values: Dict[str, str], key: str, default: str = '') -> str:
    return str(values.get(key, default)).strip()


@dataclass(frozen=True)
class Settings:
    app_env: str
    debug: bool
    backend_host: str
    backend_port: int
    allow_external_connections: bool
    enable_public_tunnel: bool
    process_on_device: bool
    allow_video_upload: bool
    store_raw_video: bool
    require_user_video_upload_consent: bool
    delete_raw_video_after_analysis: bool
    save_pose_data_only: bool
    log_sensitive_data: bool
    store_frame_images: bool
    store_debug_overlays: bool
    anonymize_user_data: bool
    send_video_to_llm: bool
    send_pose_data_to_llm: bool
    send_only_summarized_metrics_to_llm: bool
    llm_swing_trim_model: str
    llm_swing_trim_max_frames: int
    openai_api_key: str
    database_url: str
    storage_bucket: str
    jwt_secret: str

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> 'Settings':
        values = env or load_env_values()
        settings = cls(
            app_env=_str_value(values, 'APP_ENV', 'development'),
            debug=_bool_value(values, 'DEBUG', False),
            backend_host=_str_value(values, 'BACKEND_HOST', '127.0.0.1'),
            backend_port=_int_value(values, 'BACKEND_PORT', 8000),
            allow_external_connections=_bool_value(values, 'ALLOW_EXTERNAL_CONNECTIONS', False),
            enable_public_tunnel=_bool_value(values, 'ENABLE_PUBLIC_TUNNEL', False),
            process_on_device=_bool_value(values, 'PROCESS_ON_DEVICE', True),
            allow_video_upload=_bool_value(values, 'ALLOW_VIDEO_UPLOAD', False),
            store_raw_video=_bool_value(values, 'STORE_RAW_VIDEO', False),
            require_user_video_upload_consent=_bool_value(values, 'REQUIRE_USER_VIDEO_UPLOAD_CONSENT', True),
            delete_raw_video_after_analysis=_bool_value(values, 'DELETE_RAW_VIDEO_AFTER_ANALYSIS', True),
            save_pose_data_only=_bool_value(values, 'SAVE_POSE_DATA_ONLY', True),
            log_sensitive_data=_bool_value(values, 'LOG_SENSITIVE_DATA', False),
            store_frame_images=_bool_value(values, 'STORE_FRAME_IMAGES', False),
            store_debug_overlays=_bool_value(values, 'STORE_DEBUG_OVERLAYS', False),
            anonymize_user_data=_bool_value(values, 'ANONYMIZE_USER_DATA', True),
            send_video_to_llm=_bool_value(values, 'SEND_VIDEO_TO_LLM', False),
            send_pose_data_to_llm=_bool_value(values, 'SEND_POSE_DATA_TO_LLM', False),
            send_only_summarized_metrics_to_llm=_bool_value(values, 'SEND_ONLY_SUMMARIZED_METRICS_TO_LLM', True),
            llm_swing_trim_model=_str_value(values, 'LLM_SWING_TRIM_MODEL', 'gpt-4.1-mini'),
            llm_swing_trim_max_frames=_int_value(values, 'LLM_SWING_TRIM_MAX_FRAMES', 12),
            openai_api_key=_str_value(values, 'OPENAI_API_KEY'),
            database_url=_str_value(values, 'DATABASE_URL'),
            storage_bucket=_str_value(values, 'STORAGE_BUCKET'),
            jwt_secret=_str_value(values, 'JWT_SECRET'),
        )
        settings.validate()
        return settings

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == 'production'

    def validate(self) -> None:
        if self.backend_port <= 0 or self.backend_port > 65535:
            raise ConfigError('BACKEND_PORT must be between 1 and 65535.')
        if self.llm_swing_trim_max_frames < 2 or self.llm_swing_trim_max_frames > 24:
            raise ConfigError('LLM_SWING_TRIM_MAX_FRAMES must be between 2 and 24.')

        if self.is_production:
            if self.debug:
                raise ConfigError('DEBUG must be false in production.')
            if self.enable_public_tunnel:
                raise ConfigError('ENABLE_PUBLIC_TUNNEL must be false in production.')
            if self.log_sensitive_data:
                raise ConfigError('LOG_SENSITIVE_DATA must be false in production.')

            missing = [
                key
                for key, value in {
                    'OPENAI_API_KEY': self.openai_api_key,
                    'DATABASE_URL': self.database_url,
                    'STORAGE_BUCKET': self.storage_bucket,
                    'JWT_SECRET': self.jwt_secret,
                }.items()
                if not value
            ]
            if missing:
                raise ConfigError(f'Missing required production secrets: {", ".join(missing)}.')

    def startup_summary(self) -> Dict[str, str]:
        return {
            'environment': self.app_env,
            'video_upload': 'enabled' if self.allow_video_upload else 'disabled',
            'raw_video_storage': 'enabled' if self.store_raw_video else 'disabled',
            'external_connections': 'enabled' if self.allow_external_connections else 'disabled',
        }


settings = Settings.from_env()
