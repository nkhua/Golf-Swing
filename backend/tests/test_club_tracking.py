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

    def test_summarizes_tracking_paths_for_llm_metrics(self):
        frames = [
            {
                'frameIndex': 0,
                'timestampMs': 0,
                'leftWrist': {'x': 0.45, 'y': 0.65, 'confidence': 0.9, 'source': 'pose_landmark'},
                'rightWrist': {'x': 0.55, 'y': 0.65, 'confidence': 0.9, 'source': 'pose_landmark'},
                'grip': {'x': 0.5, 'y': 0.65, 'confidence': 0.9, 'source': 'pose_midpoint'},
                'clubHead': {'x': 0.58, 'y': 0.55, 'confidence': 0.7, 'source': 'vision_line'},
            },
            {
                'frameIndex': 1,
                'timestampMs': 100,
                'leftWrist': {'x': 0.48, 'y': 0.62, 'confidence': 0.9, 'source': 'pose_landmark'},
                'rightWrist': {'x': 0.58, 'y': 0.62, 'confidence': 0.9, 'source': 'pose_landmark'},
                'grip': {'x': 0.53, 'y': 0.62, 'confidence': 0.9, 'source': 'pose_midpoint'},
                'clubHead': {'x': 0.75, 'y': 0.4, 'confidence': 0.8, 'source': 'vision_line'},
            },
        ]

        summary = summarize_tracking_frames(frames, {'width': 1000, 'height': 1000})

        self.assertEqual(summary['framesTracked'], 2)
        self.assertEqual(summary['wristFrameCount'], 2)
        self.assertEqual(summary['clubFrameCount'], 2)
        self.assertGreater(summary['clubHeadPathLengthPx'], 200)
        self.assertEqual(summary['estimatedImpactMs'], 100)


if __name__ == '__main__':
    unittest.main()
