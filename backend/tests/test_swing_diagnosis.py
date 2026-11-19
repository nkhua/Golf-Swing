import unittest

from services.swing_diagnosis import build_swing_diagnosis


class SwingDiagnosisTests(unittest.TestCase):
    def test_builds_ball_strike_diagnosis_before_llm_wording(self):
        diagnosis = build_swing_diagnosis(
            {'headMovementPx': 22, 'swayPx': 18, 'confidence': 0.64},
            {
                'estimatedImpactMs': 1420,
                'golfMetrics': {
                    'shaftLeanAtImpactDegrees': -18,
                },
                'quality': {'overallTrackingConfidence': 0.84, 'needsRetake': False},
            },
            {
                'status': 'tracked',
                'firstBallMs': 1460,
                'launchDirection': 'right',
                'actualShotShape': 'fade',
                'trajectoryAngleDegrees': 18.5,
                'confidence': 0.76,
            },
            {
                'metrics': {
                    'clubPathProxy': 'in_to_out',
                    'clubPathDegrees': 10,
                    'faceToTarget': 'open',
                    'faceToPath': 'closed',
                    'faceToPathDegrees': -8,
                    'smashFactor': 1.28,
                },
                'dataQuality': {'confidence': 0.52},
            },
            {'status': 'not_dry_swing'},
            {'address': 250, 'topOfBackswing': 1050, 'impact': 1420, 'finish': 2100},
            impact_analysis={
                'status': 'generated',
                'contactQuality': {
                    'classification': 'thin',
                    'confidence': 0.66,
                    'evidence': ['Club-head vertical offset from ball is -18 px.'],
                },
                'dataQuality': {'confidence': 0.58, 'ballFlightAvailable': True},
            },
        )

        self.assertEqual(diagnosis['status'], 'generated')
        self.assertEqual(diagnosis['analysisMode'], 'ball_strike')
        self.assertEqual(diagnosis['llmRole'], 'wording_only')
        self.assertEqual(diagnosis['actualBallFlight']['status'], 'measured_from_validated_ball_track')
        self.assertEqual(diagnosis['expectedActualComparison']['expectedOutcome']['startDirection'], 'right')
        self.assertEqual(diagnosis['expectedActualComparison']['expectedOutcome']['curve'], 'draw')
        self.assertEqual(diagnosis['expectedActualComparison']['actualOutcome']['curve'], 'fade')
        self.assertEqual(diagnosis['expectedActualComparison']['agreement']['curve'], 'mismatch')
        self.assertEqual(diagnosis['expectedActualComparison']['trainingSignal'], 'tracking_or_strike_uncertainty')
        priority_ids = {priority['id'] for priority in diagnosis['priorities']}
        self.assertIn('impact-handle-trails', priority_ids)
        self.assertIn('impact-face-path-control', priority_ids)
        self.assertIn('actual-start-curve-pattern', priority_ids)
        self.assertIn('impact-strike-quality-thin', priority_ids)
        self.assertIn('expected-actual-outcome-mismatch', priority_ids)
        self.assertEqual(diagnosis['dataQuality']['impactAnalysisConfidence'], 0.58)
        self.assertEqual(diagnosis['sourceFlow'], [
            'vision_tracking',
            'deterministic_swing_diagnosis',
            'llm_wording_only',
        ])

    def test_uses_dry_swing_findings_when_no_ball_is_available(self):
        diagnosis = build_swing_diagnosis(
            {'confidence': 0.44},
            {'quality': {'overallTrackingConfidence': 0.82}},
            {'status': 'no_ball_detected', 'confidence': 0},
            {'metrics': {}, 'dataQuality': {'confidence': 0.1}},
            {
                'status': 'generated',
                'predictedBallFlight': {
                    'status': 'predicted_from_dry_swing',
                    'startDirection': 'right',
                    'curve': 'draw',
                    'confidence': 0.44,
                },
                'biomechanicalFindings': [
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
                        'likelyEffect': 'Weak contact risk.',
                        'fix': 'Move the handle ahead.',
                        'drill': 'Punch swings.',
                        'relatedMetrics': ['shaftLeanAtImpactDegrees'],
                        'confidence': 0.72,
                    },
                ],
            },
            {'impact': 1420},
        )

        self.assertEqual(diagnosis['analysisMode'], 'dry_swing')
        self.assertEqual(diagnosis['priorities'][0]['id'], 'impact-handle-trails')
        self.assertEqual(diagnosis['priorities'][0]['recommendation'], 'Move the handle ahead.')
        self.assertEqual(diagnosis['predictedBallFlight']['curve'], 'draw')
        self.assertEqual(diagnosis['actualBallFlight']['status'], 'not_available')
        self.assertEqual(diagnosis['expectedActualComparison']['status'], 'no_actual_ball')


if __name__ == '__main__':
    unittest.main()
