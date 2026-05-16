import unittest

import cv2
import numpy as np

from services.club_tracking import summarize_tracking_frames, track_swing_points_for_frame


def landmark(name, x, y, visibility=0.95):
    return {'name': name, 'x': x, 'y': y, 'z': 0, 'visibility': visibility}


class ClubTrackingTests(unittest.TestCase):
    def test_tracks_wrists_grip_and_visible_club_line(self):
        frame = np.zeros((240, 240, 3), dtype=np.uint8)
        cv2.line(frame, (120, 156), (190, 70), (255, 255, 255), 4)
        pose_frame = {
            'frameIndex': 12,
            'timestampMs': 400,
            'landmarks': [
                landmark('LEFT_WRIST', 0.46, 0.66),
                landmark('RIGHT_WRIST', 0.54, 0.64),
            ],
        }

        tracking = track_swing_points_for_frame(frame, pose_frame, {'width': 240, 'height': 240})

        self.assertEqual(tracking['frameIndex'], 12)
        self.assertIsNotNone(tracking['leftWrist'])
        self.assertIsNotNone(tracking['rightWrist'])
        self.assertAlmostEqual(tracking['grip']['x'], 0.5, places=2)
        self.assertIsNotNone(tracking['clubHead'])
        self.assertGreater(tracking['clubHead']['confidence'], 0.35)
        self.assertEqual(tracking['clubHead']['source'], 'vision_line')
        self.assertIsNotNone(tracking['clubShaft'])
        self.assertGreater(tracking['clubShaft']['lengthPx'], 70)

    def test_builds_golf_body_head_and_wrist_metrics_without_hand_model(self):
        frame = np.zeros((240, 240, 3), dtype=np.uint8)
        cv2.line(frame, (120, 156), (190, 70), (255, 255, 255), 4)
        pose_frame = {
            'frameIndex': 12,
            'timestampMs': 400,
            'landmarks': [
                landmark('NOSE', 0.5, 0.2),
                landmark('LEFT_EYE', 0.47, 0.18),
                landmark('RIGHT_EYE', 0.53, 0.18),
                landmark('LEFT_SHOULDER', 0.42, 0.34),
                landmark('RIGHT_SHOULDER', 0.58, 0.34),
                landmark('LEFT_ELBOW', 0.42, 0.5),
                landmark('RIGHT_ELBOW', 0.58, 0.5),
                landmark('LEFT_WRIST', 0.46, 0.66),
                landmark('RIGHT_WRIST', 0.54, 0.64),
                landmark('LEFT_HIP', 0.44, 0.58),
                landmark('RIGHT_HIP', 0.56, 0.58),
            ],
        }

        tracking = track_swing_points_for_frame(frame, pose_frame, {'width': 240, 'height': 240})

        self.assertIsNotNone(tracking['spineLine'])
        self.assertIsNotNone(tracking['eyeLine'])
        self.assertEqual(tracking['headMetrics']['source'], 'pose_estimate')
        self.assertEqual(tracking['handMetrics']['source'], 'club_proxy')
        self.assertIsInstance(tracking['handMetrics']['leftWristAngleDegrees'], float)
        self.assertTrue(tracking['quality']['headPoseEstimated'])

    def test_summarizes_tracking_paths_for_llm_metrics(self):
        frames = [
            {
                'frameIndex': 0,
                'timestampMs': 0,
                'leftWrist': {'x': 0.45, 'y': 0.65, 'confidence': 0.9, 'source': 'pose_landmark'},
                'rightWrist': {'x': 0.55, 'y': 0.65, 'confidence': 0.9, 'source': 'pose_landmark'},
                'grip': {'x': 0.5, 'y': 0.65, 'confidence': 0.9, 'source': 'pose_midpoint'},
                'clubHead': {'x': 0.58, 'y': 0.55, 'confidence': 0.7, 'source': 'vision_line'},
                'handMetrics': {'leftWristAngleDegrees': 145, 'rightWristAngleDegrees': 140},
                'headMetrics': {'eyeLineAngleDegrees': 2, 'headTurnProxy': 0.1},
                'clubMetrics': {'shaftAngleDegrees': -52, 'shaftLeanFromVerticalDegrees': 38},
                'bodyMetrics': {'spineAngleDegrees': 88},
                'quality': {
                    'bodyDetected': True,
                    'handsDetected': True,
                    'headPoseEstimated': True,
                    'clubDetected': True,
                },
            },
            {
                'frameIndex': 1,
                'timestampMs': 100,
                'leftWrist': {'x': 0.48, 'y': 0.62, 'confidence': 0.9, 'source': 'pose_landmark'},
                'rightWrist': {'x': 0.58, 'y': 0.62, 'confidence': 0.9, 'source': 'pose_landmark'},
                'grip': {'x': 0.53, 'y': 0.62, 'confidence': 0.9, 'source': 'pose_midpoint'},
                'clubHead': {'x': 0.75, 'y': 0.4, 'confidence': 0.8, 'source': 'vision_line'},
                'handMetrics': {'leftWristAngleDegrees': 135, 'rightWristAngleDegrees': 132},
                'headMetrics': {'eyeLineAngleDegrees': 1, 'headTurnProxy': 0.05},
                'clubMetrics': {'shaftAngleDegrees': -45, 'shaftLeanFromVerticalDegrees': 45},
                'bodyMetrics': {'spineAngleDegrees': 86},
                'quality': {
                    'bodyDetected': True,
                    'handsDetected': True,
                    'headPoseEstimated': True,
                    'clubDetected': True,
                },
            },
        ]

        summary = summarize_tracking_frames(
            frames,
            {'width': 1000, 'height': 1000},
            {'address': 0, 'impact': 100, 'topOfBackswing': 100},
        )

        self.assertEqual(summary['framesTracked'], 2)
        self.assertEqual(summary['wristFrameCount'], 2)
        self.assertEqual(summary['clubFrameCount'], 2)
        self.assertEqual(summary['handFrameCount'], 2)
        self.assertEqual(summary['faceFrameCount'], 0)
        self.assertEqual(summary['headFrameCount'], 2)
        self.assertGreater(summary['clubHeadPathLengthPx'], 200)
        self.assertEqual(summary['estimatedImpactMs'], 100)
        self.assertEqual(summary['golfMetrics']['leftWristAngleAtImpact'], 135)
        self.assertEqual(summary['golfMetrics']['shaftLeanAtImpactDegrees'], 45)
        self.assertGreater(summary['quality']['overallTrackingConfidence'], 0.8)


if __name__ == '__main__':
    unittest.main()
