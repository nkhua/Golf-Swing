import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from config import Settings
from services.impact_analysis import analyze_impact_strike


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
        'ENABLE_DETAILED_HAND_TRACKING': 'false',
        'ANONYMIZE_USER_DATA': 'true',
        'SEND_VIDEO_TO_LLM': 'false',
        'SEND_POSE_DATA_TO_LLM': 'false',
        'SEND_ONLY_SUMMARIZED_METRICS_TO_LLM': 'true',
        'ENABLE_LLM_SWING_COACHING': 'false',
        'ENABLE_LLM_IMPACT_ANALYSIS': 'false',
        'LLM_SWING_TRIM_MODEL': 'gpt-4.1-mini',
        'LLM_SWING_TRIM_MAX_FRAMES': '12',
        'LLM_SWING_COACH_MODEL': 'gpt-4.1-mini',
        'LLM_SWING_COACH_MAX_POINTS': '3',
        'LLM_IMPACT_ANALYSIS_MODEL': 'gpt-4.1-mini',
        'LLM_IMPACT_ANALYSIS_MAX_FRAMES': '3',
        'OPENAI_API_KEY': '',
        'DATABASE_URL': '',
        'STORAGE_BUCKET': '',
        'JWT_SECRET': '',
    }
    values.update(overrides)
    return Settings.from_env(values)


def make_tracking_frames():
    return [
        {
            'frameIndex': 58,
            'timestampMs': 960,
            'clubHead': {'x': 0.48, 'y': 0.58, 'confidence': 0.76, 'source': 'vision_line'},
        },
        {
            'frameIndex': 60,
            'timestampMs': 1000,
            'clubHead': {'x': 0.51, 'y': 0.62, 'confidence': 0.8, 'source': 'vision_line'},
        },
        {
            'frameIndex': 64,
            'timestampMs': 1066,
            'clubHead': {'x': 0.55, 'y': 0.64, 'confidence': 0.77, 'source': 'vision_line'},
        },
    ]


def make_ball_frames():
    return [
        {
            'frameIndex': 60,
            'timestampMs': 1000,
            'ball': {
                'x': 0.515,
                'y': 0.62,
                'confidence': 0.74,
                'source': 'vision_motion',
                'radiusPx': 5,
                'diameterPx': 10,
            },
        },
        {
            'frameIndex': 66,
            'timestampMs': 1100,
            'ball': {
                'x': 0.62,
                'y': 0.58,
                'confidence': 0.76,
                'source': 'vision_motion',
                'radiusPx': 4.8,
                'diameterPx': 9.6,
            },
        },
    ]


def write_test_video(path: Path):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 60, (120, 120))
    for index in range(80):
        frame = np.zeros((120, 120, 3), dtype=np.uint8)
        cv2.circle(frame, (62, 74), 4, (255, 255, 255), -1)
        cv2.line(frame, (48 + index // 8, 80), (65 + index // 8, 72), (210, 210, 210), 2)
        writer.write(frame)
    writer.release()


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self):
        return json.dumps(self.body).encode('utf-8')


class ImpactAnalysisTests(unittest.TestCase):
    def test_no_ball_does_not_record_strike_claims_or_send_frames(self):
        analysis, frames_sent = analyze_impact_strike(
            'unused.mp4',
            {'width': 1000, 'height': 1000, 'fps': 60},
            make_tracking_frames(),
            {'estimatedImpactMs': 1000},
            [],
            {'status': 'no_ball_detected', 'confidence': 0},
            {'impact': 1000},
            {},
            {},
            active_settings=make_settings(SEND_VIDEO_TO_LLM='true', ENABLE_LLM_IMPACT_ANALYSIS='true', OPENAI_API_KEY='sk-test'),
        )

        self.assertFalse(frames_sent)
        self.assertEqual(analysis['status'], 'not_available_no_validated_ball')
        self.assertEqual(analysis['contactQuality']['classification'], 'not_recorded_no_ball')
        self.assertIsNone(analysis['clubBallProximityPx'])
        self.assertEqual(analysis['visualImpactInference']['status'], 'skipped_no_validated_ball')

    def test_estimates_strike_metrics_for_valid_ball_without_llm(self):
        analysis, frames_sent = analyze_impact_strike(
            'unused.mp4',
            {'width': 1000, 'height': 1000, 'fps': 60},
            make_tracking_frames(),
            {
                'estimatedImpactMs': 1000,
                'golfMetrics': {'shaftLeanAtImpactDegrees': -12},
                'quality': {'overallTrackingConfidence': 0.82},
            },
            make_ball_frames(),
            {
                'status': 'tracked',
                'firstBallMs': 1000,
                'launchDirection': 'right',
                'actualShotShape': 'fade',
                'confidence': 0.74,
            },
            {'impact': 1000},
            {'metrics': {'smashFactorProxy': 1.35}},
            {
                'faceToTarget': 'open',
                'faceToPath': 'closed',
                'estimatedDegreesToTarget': 6,
                'estimatedDegreesToPath': -8,
                'clubPathProxy': 'in_to_out',
                'clubPathDegrees': 12,
                'confidence': 0.62,
            },
            active_settings=make_settings(),
        )

        self.assertFalse(frames_sent)
        self.assertEqual(analysis['status'], 'generated')
        self.assertEqual(analysis['analysisMode'], 'ball_strike')
        self.assertLess(analysis['clubBallProximityPx'], 20)
        self.assertEqual(analysis['shaftLeanAtImpactDegrees'], -12)
        self.assertEqual(analysis['facePathProxy']['faceToPath'], 'closed')
        self.assertIn(analysis['contactQuality']['classification'], {'likely_centered', 'fat', 'thin'})
        self.assertEqual(analysis['visualImpactInference']['framesSent'], 0)

    def test_optional_llm_refines_impact_frame_when_enabled_and_needed(self):
        response_payload = {
            'output_text': json.dumps({
                'contactLikely': True,
                'strikeLocation': 'toe',
                'clubFaceAngle': 'open',
                'clubFaceVisible': True,
                'ballVisible': True,
                'impactFrameQuality': 'clear',
                'confidence': 0.66,
                'evidence': ['Ball and toe-side face contact are visible in the crop.'],
                'limitations': ['Single-frame blur still limits precision.'],
            })
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / 'impact.mp4'
            write_test_video(video_path)

            with patch('urllib.request.urlopen', return_value=FakeResponse(response_payload)):
                analysis, frames_sent = analyze_impact_strike(
                    str(video_path),
                    {'width': 120, 'height': 120, 'fps': 60},
                    make_tracking_frames(),
                    {
                        'estimatedImpactMs': 1000,
                        'golfMetrics': {'shaftLeanAtImpactDegrees': -12},
                        'quality': {'overallTrackingConfidence': 0.62},
                    },
                    make_ball_frames(),
                    {
                        'status': 'tracked',
                        'firstBallMs': 1000,
                        'launchDirection': 'right',
                        'actualShotShape': 'fade',
                        'confidence': 0.74,
                    },
                    {'impact': 1000},
                    {'metrics': {'smashFactorProxy': 1.1}},
                    {'faceToTarget': 'unknown', 'faceToPath': 'unknown', 'confidence': 0.1},
                    active_settings=make_settings(
                        SEND_VIDEO_TO_LLM='true',
                        ENABLE_LLM_IMPACT_ANALYSIS='true',
                        OPENAI_API_KEY='sk-test',
                    ),
                )

        self.assertTrue(frames_sent)
        self.assertEqual(analysis['visualImpactInference']['status'], 'generated')
        self.assertEqual(analysis['contactQuality']['classification'], 'toe')
        self.assertEqual(analysis['contactQuality']['horizontalStrike'], 'toe')
        self.assertEqual(analysis['facePathProxy']['visualFaceAngle'], 'open')


if __name__ == '__main__':
    unittest.main()
