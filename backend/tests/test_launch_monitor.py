import unittest

from services.launch_monitor import estimate_launch_monitor_metrics


class LaunchMonitorTests(unittest.TestCase):
    def test_estimates_trackman_like_proxy_metrics_from_video_tracking(self):
        tracking_frames = [
            {
                'timestampMs': 900,
                'clubHead': {'x': 0.46, 'y': 0.72, 'confidence': 0.8, 'source': 'vision_line'},
            },
            {
                'timestampMs': 1000,
                'clubHead': {'x': 0.58, 'y': 0.62, 'confidence': 0.82, 'source': 'vision_line'},
            },
            {
                'timestampMs': 1100,
                'clubHead': {'x': 0.72, 'y': 0.56, 'confidence': 0.78, 'source': 'vision_line'},
            },
        ]
        ball_frames = [
            {
                'timestampMs': 1020,
                'ball': {
                    'x': 0.58,
                    'y': 0.58,
                    'confidence': 0.74,
                    'source': 'vision_motion',
                    'radiusPx': 5,
                    'diameterPx': 10,
                },
            },
            {
                'timestampMs': 1120,
                'ball': {
                    'x': 0.76,
                    'y': 0.52,
                    'confidence': 0.77,
                    'source': 'vision_motion',
                    'radiusPx': 4.8,
                    'diameterPx': 9.6,
                },
            },
            {
                'timestampMs': 1220,
                'ball': {
                    'x': 0.86,
                    'y': 0.50,
                    'confidence': 0.72,
                    'source': 'vision_motion',
                    'radiusPx': 4.6,
                    'diameterPx': 9.2,
                },
            },
        ]

        launch_monitor = estimate_launch_monitor_metrics(
            {'width': 1000, 'height': 1000, 'cameraAngle': 'down_the_line'},
            tracking_frames,
            {
                'maxClubHeadSpeedPxPerSec': 1600,
                'estimatedImpactMs': 1000,
                'quality': {'overallTrackingConfidence': 0.78},
            },
            ball_frames,
            {
                'status': 'tracked',
                'launchDirection': 'right',
                'trajectoryAngleDegrees': 18.5,
                'actualShotShape': 'fade',
                'ballPathLengthPx': 360,
                'carryDistancePx': 280,
                'apexHeightPx': 80,
                'curvaturePx': 18,
                'maxBallSpeedPxPerSec': 1900,
                'confidence': 0.74,
            },
            {'impact': 1000},
            {
                'clubPathDegrees': 8,
                'clubPathProxy': 'in_to_out',
                'estimatedDegreesToTarget': 6,
                'estimatedDegreesToPath': -2,
                'faceToTarget': 'open',
                'faceToPath': 'square',
            },
        )

        self.assertEqual(launch_monitor['measurementSystem'], 'video_proxy_not_launch_monitor')
        self.assertEqual(launch_monitor['status'], 'estimated')
        self.assertEqual(launch_monitor['calibration']['status'], 'estimated')
        self.assertGreater(launch_monitor['metrics']['clubSpeedPxPerSec'], 0)
        self.assertGreater(launch_monitor['metrics']['ballSpeedPxPerSec'], 0)
        self.assertIsNotNone(launch_monitor['metrics']['clubSpeedMph'])
        self.assertIsNotNone(launch_monitor['metrics']['ballSpeedMph'])
        self.assertIsNotNone(launch_monitor['metrics']['smashFactor'])
        self.assertEqual(launch_monitor['metrics']['launchDirection'], 'right')
        self.assertEqual(launch_monitor['metrics']['actualShotShape'], 'fade')
        self.assertEqual(launch_monitor['metrics']['spinRateRpm'], None)
        self.assertIn('spinRateRpm', launch_monitor['dataQuality']['missingMetrics'])
        self.assertTrue(launch_monitor['dataQuality']['requiresCalibration'])
        self.assertTrue(launch_monitor['interpretation'])

    def test_marks_insufficient_evidence_without_speed_segments(self):
        launch_monitor = estimate_launch_monitor_metrics(
            {'width': 1000, 'height': 1000},
            [],
            {},
            [],
            {},
        )

        self.assertEqual(launch_monitor['status'], 'insufficient_evidence')
        self.assertEqual(launch_monitor['metrics']['clubSpeedPxPerSec'], None)
        self.assertEqual(launch_monitor['metrics']['ballSpeedPxPerSec'], None)
        self.assertIn('clubSpeedMph', launch_monitor['dataQuality']['missingMetrics'])

    def test_does_not_use_ball_candidates_when_ball_flight_is_not_validated(self):
        launch_monitor = estimate_launch_monitor_metrics(
            {'width': 1000, 'height': 1000},
            [
                {
                    'timestampMs': 900,
                    'clubHead': {'x': 0.45, 'y': 0.72, 'confidence': 0.8, 'source': 'vision_line'},
                },
                {
                    'timestampMs': 1000,
                    'clubHead': {'x': 0.62, 'y': 0.58, 'confidence': 0.82, 'source': 'vision_line'},
                },
            ],
            {'estimatedImpactMs': 1000, 'maxClubHeadSpeedPxPerSec': 1700},
            [
                {
                    'timestampMs': 1030,
                    'ball': {'x': 0.5, 'y': 0.5, 'confidence': 0.8, 'source': 'vision_motion'},
                },
                {
                    'timestampMs': 1130,
                    'ball': {'x': 0.8, 'y': 0.45, 'confidence': 0.8, 'source': 'vision_motion'},
                },
            ],
            {
                'status': 'no_ball_detected',
                'launchDirection': None,
                'actualShotShape': 'unknown',
                'maxBallSpeedPxPerSec': None,
                'confidence': 0,
            },
            {'impact': 1000},
        )

        self.assertEqual(launch_monitor['status'], 'partial')
        self.assertIsNone(launch_monitor['metrics']['ballSpeedPxPerSec'])
        self.assertIsNone(launch_monitor['metrics']['smashFactorProxy'])
        self.assertEqual(launch_monitor['metrics']['launchDirection'], 'unknown')
        self.assertIn('actualShotShape', launch_monitor['dataQuality']['missingMetrics'])


if __name__ == '__main__':
    unittest.main()
