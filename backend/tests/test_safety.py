import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        trackingFrames=[
            {
                'frameIndex': 0,
                'timestampMs': 0,
                'leftWrist': {'x': 0.45, 'y': 0.62, 'confidence': 0.9, 'source': 'pose_landmark'},
                'rightWrist': {'x': 0.55, 'y': 0.62, 'confidence': 0.9, 'source': 'pose_landmark'},
                'grip': {'x': 0.5, 'y': 0.62, 'confidence': 0.9, 'source': 'pose_midpoint'},
                'clubHead': {'x': 0.72, 'y': 0.44, 'confidence': 0.7, 'source': 'vision_line'},
            }
        ],
        trackingSummary={
            'framesTracked': 1,
            'wristFrameCount': 1,
            'clubFrameCount': 1,
            'averageClubConfidence': 0.7,
        },
        ballTrackingFrames=[
            {
                'frameIndex': 42,
                'timestampMs': 1400,
                'ball': {'x': 0.62, 'y': 0.48, 'confidence': 0.72, 'source': 'vision_motion'},
            }
        ],
        ballFlightSummary={
            'status': 'tracked',
            'framesTracked': 1,
            'ballFrameCount': 1,
            'averageBallConfidence': 0.72,
            'launchDirection': 'right',
            'actualShotShape': 'fade',
            'confidence': 0.55,
        },
        launchMonitor={
            'status': 'partial',
            'measurementSystem': 'video_proxy_not_launch_monitor',
            'metrics': {'clubSpeedPxPerSec': 640, 'ballSpeedPxPerSec': 1410},
            'dataQuality': {'confidence': 0.4, 'missingMetrics': ['spinRateRpm']},
        },
        impactAnalysis={
            'status': 'generated',
            'analysisMode': 'ball_strike',
            'impactTimestampMs': 1200,
            'clubBallProximityPx': 12,
            'contactQuality': {
                'classification': 'likely_centered',
                'confidence': 0.62,
                'evidence': ['Club-ball proximity is 12 px.'],
            },
            'visualImpactInference': {'status': 'not_requested', 'framesSent': 0},
            'dataQuality': {'confidence': 0.58, 'ballFlightAvailable': True},
        },
        drySwing={
            'status': 'not_dry_swing',
            'mode': 'ball_strike',
            'actualBallFlightAvailable': True,
            'predictedBallFlight': {'status': 'not_applicable', 'confidence': 0},
            'biomechanicalFindings': [],
            'practicePlan': [],
            'dataQuality': {'confidence': 0, 'ballFlightStatus': 'tracked'},
        },
        swingDiagnosis={
            'status': 'generated',
            'analysisMode': 'ball_strike',
            'llmRole': 'wording_only',
            'priorities': [
                {
                    'id': 'impact-handle-trails',
                    'category': 'impact',
                    'severity': 'high',
                    'phase': 'impact',
                    'timestampMs': 1200,
                    'endTimestampMs': 1650,
                    'title': 'Handle trails at impact',
                    'evidence': 'Impact shaft lean is behind.',
                    'videoCue': 'Watch impact.',
                    'recommendation': 'Move handle forward.',
                    'drill': 'Punch shots.',
                    'relatedMetrics': ['shaftLeanAtImpactDegrees'],
                    'confidence': 0.72,
                }
            ],
            'dataQuality': {'confidence': 0.72},
        },
        biomechanics={'tempoRatio': 2.7, 'confidence': 0.5},
        privacy={'rawVideoUploaded': False, 'userConsentedToUpload': False, 'impactFramesSentToLlm': False},
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

    def test_locked_raw_video_cleanup_does_not_mask_original_error(self):
        settings = make_settings(ALLOW_VIDEO_UPLOAD='true')
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'swing.mp4'
            path.write_bytes(b'video')

            with patch.object(Path, 'unlink', side_effect=PermissionError('locked')):
                with self.assertWarns(RuntimeWarning):
                    deleted = maybe_delete_raw_video(path, active_settings=settings)

            self.assertFalse(deleted)

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
        self.assertNotIn('trackingFrames', payload)
        self.assertNotIn('ballTrackingFrames', payload)
        self.assertIn('trackingSummary', payload)
        self.assertIn('ballFlightSummary', payload)
        self.assertIn('launchMonitor', payload)
        self.assertIn('impactAnalysis', payload)
        self.assertIn('drySwing', payload)
        self.assertIn('swingDiagnosis', payload)
        self.assertIn('biomechanics', payload)
        self.assertIn('videoMetadata', payload)

    def test_llm_payload_can_include_pose_and_tracking_points_when_enabled(self):
        settings = make_settings(
            SEND_POSE_DATA_TO_LLM='true',
            SEND_ONLY_SUMMARIZED_METRICS_TO_LLM='false',
        )

        payload = build_llm_payload(make_payload(), active_settings=settings)

        self.assertIn('poseFrames', payload)
        self.assertIn('trackingFrames', payload)
        self.assertIn('ballTrackingFrames', payload)
        self.assertEqual(payload['trackingFrames'][0]['clubHead']['source'], 'vision_line')
        self.assertEqual(payload['ballTrackingFrames'][0]['ball']['source'], 'vision_motion')


if __name__ == '__main__':
    unittest.main()
