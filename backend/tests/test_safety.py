import tempfile
import unittest
from pathlib import Path

from config import ConfigError, Settings
from safety import assert_video_upload_allowed, build_llm_payload, maybe_delete_raw_video, redact_mapping
from schemas import SwingAnalysisPayload


def make_settings(**overrides):
    values = {
        'APP_ENV': 'development',
        'DEBUG': 'false',
        'BACKEND_HOST': '127.0.0.1',
        'BACKEND_PORT': '8000',
        'ALLOW_EXTERNAL_CONNECTIONS': 'false',
        'ENABLE_PUBLIC_TUNNEL': 'false',
        'PROCESS_ON_DEVICE': 'true',
        'ALLOW_VIDEO_UPLOAD': 'false',
        'STORE_RAW_VIDEO': 'false',
        'REQUIRE_USER_VIDEO_UPLOAD_CONSENT': 'true',
        'DELETE_RAW_VIDEO_AFTER_ANALYSIS': 'true',
        'SAVE_POSE_DATA_ONLY': 'true',
        'LOG_SENSITIVE_DATA': 'false',
        'STORE_FRAME_IMAGES': 'false',
        'STORE_DEBUG_OVERLAYS': 'false',
        'ANONYMIZE_USER_DATA': 'true',
        'SEND_VIDEO_TO_LLM': 'false',
        'SEND_POSE_DATA_TO_LLM': 'false',
        'SEND_ONLY_SUMMARIZED_METRICS_TO_LLM': 'true',
        'OPENAI_API_KEY': '',
        'DATABASE_URL': '',
        'STORAGE_BUCKET': '',
        'JWT_SECRET': '',
    }
    values.update(overrides)
    return Settings.from_env(values)


def make_payload():
    return SwingAnalysisPayload(
        swingId='test-swing',
        source='on_device',
        videoMetadata={
            'fps': 60,
            'durationMs': 1800,
            'width': 1080,
            'height': 1920,
            'cameraAngle': 'down_the_line',
        },
        phases={'address': 0, 'impact': 1200},
        poseFrames=[
            {
                'frameIndex': 0,
                'timestampMs': 0,
                'landmarks': [{'name': 'LEFT_SHOULDER', 'x': 0.4, 'y': 0.3}],
            }
        ],
        biomechanics={'tempoRatio': 2.7, 'confidence': 0.5},
        privacy={'rawVideoUploaded': False, 'userConsentedToUpload': False},
    )


class SafetyTests(unittest.TestCase):
    def test_upload_blocked_when_video_upload_disabled(self):
        settings = make_settings(ALLOW_VIDEO_UPLOAD='false')
        with self.assertRaises(PermissionError):
            assert_video_upload_allowed(user_consented=True, active_settings=settings)

    def test_raw_video_not_stored_when_storage_disabled(self):
        settings = make_settings(
            ALLOW_VIDEO_UPLOAD='true',
            STORE_RAW_VIDEO='false',
            DELETE_RAW_VIDEO_AFTER_ANALYSIS='false',
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'swing.mp4'
            path.write_bytes(b'video')
            maybe_delete_raw_video(path, active_settings=settings)
            self.assertFalse(path.exists())

    def test_production_fails_with_unsafe_config(self):
        with self.assertRaises(ConfigError):
            make_settings(APP_ENV='production', DEBUG='true')

        with self.assertRaises(ConfigError):
            make_settings(
                APP_ENV='production',
                OPENAI_API_KEY='sk-test',
                DATABASE_URL='postgres://example',
                STORAGE_BUCKET='bucket',
                JWT_SECRET='secret',
                ENABLE_PUBLIC_TUNNEL='true',
            )

    def test_logs_redact_secrets(self):
        redacted = redact_mapping({
            'OPENAI_API_KEY': 'sk-secret',
            'Authorization': 'Bearer token',
            'safe': 'ok',
        })
        self.assertEqual(redacted['OPENAI_API_KEY'], '[REDACTED]')
        self.assertEqual(redacted['Authorization'], '[REDACTED]')
        self.assertEqual(redacted['safe'], 'ok')

    def test_llm_payload_excludes_sensitive_data_by_default(self):
        settings = make_settings()
        payload = build_llm_payload(make_payload(), active_settings=settings)
        self.assertNotIn('poseFrames', payload)
        self.assertIn('biomechanics', payload)
        self.assertIn('videoMetadata', payload)


if __name__ == '__main__':
    unittest.main()
