import json
import unittest
from unittest.mock import patch

from config import Settings
from services.swing_coach import build_swing_coach_evidence, generate_swing_coaching


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
        'LLM_SWING_TRIM_MODEL': 'gpt-4.1-mini',
        'LLM_SWING_TRIM_MAX_FRAMES': '12',
        'LLM_SWING_COACH_MODEL': 'gpt-4.1-mini',
        'LLM_SWING_COACH_MAX_POINTS': '3',
        'OPENAI_API_KEY': '',
        'DATABASE_URL': '',
        'STORAGE_BUCKET': '',
        'JWT_SECRET': '',
    }
    values.update(overrides)
    return Settings.from_env(values)


def make_analysis_payload():
    return {
        'videoMetadata': {'fps': 60, 'durationMs': 5600, 'width': 1080, 'height': 1920},
        'swingWindow': {'startMs': 250, 'detectedStartMs': 250, 'detectedEndMs': 2100, 'endMs': 5200},
        'phases': {'address': 250, 'takeaway': 420, 'topOfBackswing': 1050, 'impact': 1420, 'finish': 2100},
        'trackingSummary': {
            'framesTracked': 8,
            'clubFrameCount': 8,
            'averageClubConfidence': 0.76,
            'estimatedImpactMs': 1420,
            'golfMetrics': {
                'shaftLeanAtImpactDegrees': -28,
                'headTurnAtImpact': 0.18,
                'eyeLineAngleAtImpact': 4,
            },
            'quality': {'overallTrackingConfidence': 0.82, 'needsRetake': False},
        },
        'ballFlightSummary': {
            'ballFrameCount': 6,
            'launchDirection': 'right',
            'shotShape': 'fade',
            'confidence': 0.78,
        },
        'biomechanics': {'spineAngleAtAddress': 7, 'confidence': 0.7},
        'ballFlightEstimates': {'launchDirection': 'right', 'shotShape': 'fade', 'confidence': 0.78},
    }


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self):
        return json.dumps(self.body).encode('utf-8')


class SwingCoachTests(unittest.TestCase):
    def test_builds_summarized_evidence_without_raw_frames(self):
        payload = make_analysis_payload()
        payload['poseFrames'] = [{'frameIndex': 0, 'landmarks': []}]
        payload['trackingFrames'] = [{'frameIndex': 0}]

        evidence = build_swing_coach_evidence(payload)

        self.assertIn('phaseMarkersMs', evidence)
        self.assertEqual(evidence['phaseMarkersMs']['impact'], 1420)
        self.assertNotIn('poseFrames', evidence)
        self.assertNotIn('trackingFrames', evidence)

    def test_returns_disabled_or_missing_key_without_network_call(self):
        disabled, metrics_sent = generate_swing_coaching(make_analysis_payload(), make_settings())
        self.assertEqual(disabled['status'], 'disabled')
        self.assertFalse(metrics_sent)

        missing_key, metrics_sent = generate_swing_coaching(
            make_analysis_payload(),
            make_settings(ENABLE_LLM_SWING_COACHING='true'),
        )
        self.assertEqual(missing_key['status'], 'missing_api_key')
        self.assertFalse(metrics_sent)

    def test_generates_timestamped_pain_points_from_structured_output(self):
        response_payload = {
            'output_text': json.dumps({
                'summary': 'Impact is the priority.',
                'confidence': 0.81,
                'notes': 'Generated from metrics.',
                'painPoints': [
                    {
                        'id': 'impact-shaft-lean',
                        'category': 'impact',
                        'severity': 'high',
                        'phase': 'impact',
                        'title': 'Handle trails at impact',
                        'evidence': 'Shaft lean is -28 deg at impact.',
                        'videoCue': 'Watch the grip point behind the club head at impact.',
                        'timestampMs': 1420,
                        'endTimestampMs': 1750,
                        'recommendation': 'Move the handle ahead through impact.',
                        'drill': 'Half-swing punch shots with a held finish.',
                        'relatedMetrics': ['shaftLeanAtImpactDegrees'],
                        'confidence': 0.79,
                    }
                ],
            }),
        }

        with patch('services.swing_coach.urllib.request.urlopen', return_value=FakeResponse(response_payload)) as urlopen:
            coaching, metrics_sent = generate_swing_coaching(
                make_analysis_payload(),
                make_settings(ENABLE_LLM_SWING_COACHING='true', OPENAI_API_KEY='sk-test'),
            )

        request_body = json.loads(urlopen.call_args.args[0].data.decode('utf-8'))
        self.assertEqual(request_body['model'], 'gpt-4.1-mini')
        self.assertEqual(request_body['text']['format']['type'], 'json_schema')
        self.assertEqual(coaching['status'], 'generated')
        self.assertTrue(metrics_sent)
        self.assertEqual(coaching['painPoints'][0]['timestampMs'], 1420)
        self.assertEqual(coaching['painPoints'][0]['phase'], 'impact')


if __name__ == '__main__':
    unittest.main()
