import unittest

from services.dry_swing import analyze_dry_swing


class DrySwingTests(unittest.TestCase):
    def test_generates_dry_swing_prediction_and_biomechanics_findings_without_ball(self):
        dry_swing = analyze_dry_swing(
            {
                'tempoRatio': 1.8,
                'shoulderTurnAtTop': 48,
                'hipTurnAtTop': 36,
                'headMovementPx': 92,
                'swayPx': 82,
                'confidence': 0.66,
            },
            {
                'estimatedImpactMs': 1420,
                'averageClubConfidence': 0.74,
                'golfMetrics': {
                    'shaftLeanAtImpactDegrees': -16,
                    'headTurnAtImpact': 0.22,
                    'eyeLineAngleAtAddress': 0,
                    'eyeLineAngleAtImpact': 12,
                    'clubFaceEstimate': {
                        'status': 'estimated',
                        'faceToTarget': 'open',
                        'faceToPath': 'closed',
                        'clubPathProxy': 'in_to_out',
                        'estimatedDegreesToTarget': 6,
                        'estimatedDegreesToPath': -7,
                        'clubPathDegrees': 11,
                        'confidence': 0.68,
                    },
                },
                'quality': {
                    'overallTrackingConfidence': 0.82,
                    'needsRetake': False,
                    'retakeReasons': [],
                },
            },
            {
                'status': 'partial',
                'metrics': {
                    'clubSpeedPxPerSec': 1550,
                    'attackAngleDegrees': -3.5,
                    'clubPathProxy': 'in_to_out',
                    'clubPathDegrees': 11,
                    'faceToTarget': 'open',
                    'faceToPath': 'closed',
                    'faceAngleDegrees': 6,
                    'faceToPathDegrees': -7,
                },
                'dataQuality': {
                    'confidence': 0.38,
                    'attackAngleConfidence': 0.3,
                },
            },
            {
                'status': 'no_ball_detected',
                'ballFrameCount': 0,
                'ballCandidateFrameCount': 2,
                'launchDirection': None,
                'actualShotShape': 'unknown',
                'confidence': 0,
            },
            {
                'address': 250,
                'topOfBackswing': 1050,
                'downswing': 1220,
                'impact': 1420,
                'finish': 2100,
            },
        )

        self.assertEqual(dry_swing['status'], 'generated')
        self.assertFalse(dry_swing['actualBallFlightAvailable'])
        self.assertEqual(dry_swing['predictedBallFlight']['status'], 'predicted_from_dry_swing')
        self.assertEqual(dry_swing['predictedBallFlight']['startDirection'], 'right')
        self.assertEqual(dry_swing['predictedBallFlight']['curve'], 'draw')
        self.assertEqual(dry_swing['predictedBallFlight']['contactRisk'], 'scoop_or_thin_contact_risk')
        self.assertGreater(dry_swing['predictedBallFlight']['confidence'], 0.2)
        finding_ids = {finding['id'] for finding in dry_swing['biomechanicalFindings']}
        self.assertIn('impact-handle-trails', finding_ids)
        self.assertIn('predicted-face-path-ball-flight', finding_ids)
        self.assertIn('excess-head-movement', finding_ids)
        self.assertTrue(dry_swing['practicePlan'])
        self.assertIn('validatedBallFlight', dry_swing['dataQuality']['missingEvidence'])

    def test_skips_dry_mode_when_validated_ball_flight_exists(self):
        dry_swing = analyze_dry_swing(
            {'confidence': 0.7},
            {'quality': {'overallTrackingConfidence': 0.8}},
            {'metrics': {'clubSpeedPxPerSec': 1200}},
            {'status': 'tracked', 'confidence': 0.74, 'actualShotShape': 'fade'},
        )

        self.assertEqual(dry_swing['status'], 'not_dry_swing')
        self.assertTrue(dry_swing['actualBallFlightAvailable'])
        self.assertEqual(dry_swing['predictedBallFlight']['status'], 'not_applicable')

    def test_prioritizes_tracking_quality_when_motion_evidence_is_weak(self):
        dry_swing = analyze_dry_swing(
            {'confidence': 0.18},
            {
                'estimatedImpactMs': 900,
                'golfMetrics': {},
                'quality': {
                    'overallTrackingConfidence': 0.22,
                    'needsRetake': True,
                    'retakeReasons': ['Club shaft/head was visible in fewer than 35% of tracked frames.'],
                },
            },
            {'metrics': {}, 'dataQuality': {'confidence': 0.05}},
            {'status': 'no_ball_detected', 'confidence': 0},
            {'address': 100, 'impact': 900},
        )

        self.assertEqual(dry_swing['status'], 'generated')
        self.assertEqual(dry_swing['biomechanicalFindings'][0]['id'], 'tracking-quality')
        self.assertEqual(dry_swing['biomechanicalFindings'][0]['category'], 'tracking_quality')
        self.assertEqual(dry_swing['predictedBallFlight']['status'], 'insufficient_evidence')


if __name__ == '__main__':
    unittest.main()
