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
                'clubFaceEstimate': {
                    'status': 'estimated',
                    'measurementType': 'video_proxy_not_launch_monitor',
                    'faceToTarget': 'open',
                    'faceToPath': 'closed',
                    'clubPathProxy': 'in_to_out',
                    'ballStartDirection': 'right',
                    'estimatedDegreesToTarget': 6,
                    'estimatedDegreesToPath': -8,
                    'clubPathDegrees': 14,
                    'confidence': 0.68,
                    'evidence': ['Ball launch direction bucket: right'],
                },
            },
            'quality': {'overallTrackingConfidence': 0.82, 'needsRetake': False},
        },
        'ballFlightSummary': {
            'status': 'tracked',
            'ballFrameCount': 6,
            'launchDirection': 'right',
            'actualShotShape': 'fade',
            'confidence': 0.78,
        },
        'launchMonitor': {
            'status': 'estimated',
            'measurementSystem': 'video_proxy_not_launch_monitor',
            'metrics': {
                'clubSpeedMph': 82.4,
                'ballSpeedMph': 119.1,
                'smashFactor': 1.45,
                'launchAngleDegrees': 18.5,
                'spinRateRpm': None,
            },
            'dataQuality': {
                'confidence': 0.52,
                'missingMetrics': ['spinRateRpm', 'carryYards'],
            },
        },
        'impactAnalysis': {
            'status': 'generated',
            'analysisMode': 'ball_strike',
            'impactTimestampMs': 1420,
            'clubBallProximityPx': 14,
            'shaftLeanAtImpactDegrees': -28,
            'contactQuality': {
                'classification': 'likely_centered',
                'confidence': 0.64,
                'evidence': ['Club-ball proximity is 14 px.'],
            },
            'visualImpactInference': {'status': 'not_requested', 'framesSent': 0},
            'dataQuality': {'confidence': 0.61, 'ballFlightAvailable': True},
        },
        'drySwing': {
            'status': 'not_dry_swing',
            'mode': 'ball_strike',
            'actualBallFlightAvailable': True,
            'predictedBallFlight': {'status': 'not_applicable', 'confidence': 0},
            'biomechanicalFindings': [],
            'practicePlan': [],
            'dataQuality': {'confidence': 0, 'ballFlightStatus': 'tracked'},
        },
        'swingDiagnosis': {
            'status': 'generated',
            'analysisMode': 'ball_strike',
            'llmRole': 'wording_only',
            'summary': 'Top deterministic priority is Handle trails at impact.',
            'priorities': [
                {
                    'id': 'impact-shaft-lean',
                    'category': 'impact',
                    'severity': 'high',
                    'phase': 'impact',
                    'timestampMs': 1420,
                    'endTimestampMs': 1870,
                    'title': 'Handle trails at impact',
                    'evidence': 'Impact shaft lean is -28 deg.',
                    'videoCue': 'Watch the grip point behind the club head at impact.',
                    'recommendation': 'Move the handle ahead through impact.',
                    'drill': 'Half-swing punch shots.',
                    'relatedMetrics': ['shaftLeanAtImpactDegrees'],
                    'confidence': 0.79,
                }
            ],
            'practicePlan': [],
            'dataQuality': {'confidence': 0.72},
        },
        'biomechanics': {'spineAngleAtAddress': 7, 'confidence': 0.7},
        'ballFlightEstimates': {'launchDirection': 'right', 'actualShotShape': 'fade', 'confidence': 0.78},
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

        self.assertEqual(evidence['analysisMode'], 'ball_strike')
        self.assertTrue(evidence['ballFlightAvailable'])
        self.assertIn('phaseMarkersMs', evidence)
        self.assertEqual(evidence['phaseMarkersMs']['impact'], 1420)
        self.assertNotIn('poseFrames', evidence)
        self.assertNotIn('trackingFrames', evidence)
        self.assertEqual(
            evidence['trackingSummary']['golfMetrics']['clubFaceEstimate']['faceToTarget'],
            'open',
        )
        self.assertEqual(evidence['launchMonitor']['metrics']['smashFactor'], 1.45)
        self.assertEqual(evidence['impactAnalysis']['status'], 'generated')
        self.assertEqual(evidence['drySwing']['status'], 'not_dry_swing')
        self.assertEqual(evidence['swingDiagnosis']['llmRole'], 'wording_only')

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

    def test_marks_no_validated_ball_as_dry_swing_evidence(self):
        payload = make_analysis_payload()
        payload['ballFlightSummary'] = {
            'status': 'no_ball_detected',
            'ballFrameCount': 0,
            'ballCandidateFrameCount': 0,
            'launchDirection': None,
            'actualShotShape': 'unknown',
            'confidence': 0,
        }
        payload['ballFlightEstimates'] = {
            'launchDirection': None,
            'actualShotShape': 'unknown',
            'confidence': 0,
        }
        payload['drySwing'] = {
            'status': 'generated',
            'mode': 'dry_swing',
            'actualBallFlightAvailable': False,
            'predictedBallFlight': {
                'status': 'predicted_from_dry_swing',
                'startDirection': 'right',
                'curve': 'draw',
                'confidence': 0.44,
            },
            'biomechanicalFindings': [
                {
                    'id': 'impact-handle-trails',
                    'phase': 'impact',
                    'timestampMs': 1420,
                    'title': 'Handle is trailing the club head at impact',
                }
            ],
            'dataQuality': {'confidence': 0.44, 'ballFlightStatus': 'no_ball_detected'},
        }
        payload['swingDiagnosis'] = {
            'status': 'generated',
            'analysisMode': 'dry_swing',
            'llmRole': 'wording_only',
            'priorities': [
                {
                    'id': 'impact-handle-trails',
                    'category': 'impact',
                    'severity': 'high',
                    'phase': 'impact',
                    'timestampMs': 1420,
                    'endTimestampMs': 1870,
                    'title': 'Handle is trailing the club head at impact',
                    'evidence': 'Impact shaft lean proxy is -16 deg.',
                    'videoCue': 'Pause at impact.',
                    'recommendation': 'Move the handle ahead.',
                    'drill': 'Punch swings.',
                    'relatedMetrics': ['shaftLeanAtImpactDegrees'],
                    'confidence': 0.72,
                }
            ],
        }

        evidence = build_swing_coach_evidence(payload)

        self.assertEqual(evidence['analysisMode'], 'dry_swing_or_no_validated_ball')
        self.assertFalse(evidence['ballFlightAvailable'])
        self.assertIsNone(evidence['ballFlightSummary']['launchDirection'])
        self.assertEqual(evidence['drySwing']['status'], 'generated')
        self.assertEqual(evidence['drySwing']['predictedBallFlight']['curve'], 'draw')
        self.assertEqual(evidence['swingDiagnosis']['analysisMode'], 'dry_swing')

    def test_low_confidence_tracked_ball_stays_dry_swing_evidence(self):
        payload = make_analysis_payload()
        payload['ballFlightSummary'] = {
            'status': 'tracked',
            'ballFrameCount': 2,
            'ballCandidateFrameCount': 2,
            'launchDirection': 'right',
            'actualShotShape': 'fade',
            'confidence': 0.2,
        }

        evidence = build_swing_coach_evidence(payload)

        self.assertEqual(evidence['analysisMode'], 'dry_swing_or_no_validated_ball')
        self.assertFalse(evidence['ballFlightAvailable'])

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

    def test_llm_wording_cannot_add_faults_outside_deterministic_diagnosis(self):
        response_payload = {
            'output_text': json.dumps({
                'summary': 'Stick to deterministic priorities.',
                'confidence': 0.81,
                'notes': 'Generated from diagnosis.',
                'painPoints': [
                    {
                        'id': 'invented-overswing',
                        'category': 'backswing',
                        'severity': 'high',
                        'phase': 'topOfBackswing',
                        'title': 'Invented backswing issue',
                        'evidence': 'This was not in deterministic diagnosis.',
                        'videoCue': 'Ignore this.',
                        'timestampMs': 1050,
                        'endTimestampMs': 1300,
                        'recommendation': 'Do something unrelated.',
                        'drill': 'Unrelated drill.',
                        'relatedMetrics': [],
                        'confidence': 0.9,
                    }
                ],
            }),
        }

        with patch('services.swing_coach.urllib.request.urlopen', return_value=FakeResponse(response_payload)):
            coaching, metrics_sent = generate_swing_coaching(
                make_analysis_payload(),
                make_settings(ENABLE_LLM_SWING_COACHING='true', OPENAI_API_KEY='sk-test'),
            )

        self.assertTrue(metrics_sent)
        self.assertEqual(coaching['painPoints'][0]['id'], 'impact-shaft-lean')
        self.assertEqual(coaching['painPoints'][0]['title'], 'Handle trails at impact')
        self.assertEqual(coaching['painPoints'][0]['timestampMs'], 1420)

    def test_snaps_llm_timestamps_to_measured_phase_markers(self):
        response_payload = {
            'output_text': json.dumps({
                'summary': 'The cue is impact, even if the model guessed the wrong second.',
                'confidence': 0.74,
                'notes': 'Generated from metrics.',
                'painPoints': [
                    {
                        'id': 'impact-face-path',
                        'category': 'impact',
                        'severity': 'medium',
                        'phase': 'impact',
                        'title': 'Face and path need matching',
                        'evidence': 'Face/path evidence is around impact.',
                        'videoCue': 'Pause exactly at impact.',
                        'timestampMs': 2600,
                        'endTimestampMs': 4200,
                        'recommendation': 'Match the face to the start line.',
                        'drill': 'Slow impact freezes.',
                        'relatedMetrics': ['faceToPathDegrees'],
                        'confidence': 0.7,
                    }
                ],
            }),
        }

        with patch('services.swing_coach.urllib.request.urlopen', return_value=FakeResponse(response_payload)):
            coaching, _metrics_sent = generate_swing_coaching(
                make_analysis_payload(),
                make_settings(ENABLE_LLM_SWING_COACHING='true', OPENAI_API_KEY='sk-test'),
            )

        self.assertEqual(coaching['painPoints'][0]['timestampMs'], 1420)
        self.assertEqual(coaching['painPoints'][0]['endTimestampMs'], 1870)


if __name__ == '__main__':
    unittest.main()
