import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from services.ball_tracking import (
    estimates_from_ball_summary,
    extract_ball_tracking,
    summarize_ball_tracking,
)


def write_synthetic_ball_video(path: Path, fps: int = 30, frame_count: int = 150) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*'MJPG'),
        fps,
        (240, 240),
    )

    if not writer.isOpened():
        raise RuntimeError('Could not create synthetic test video.')

    try:
        for frame_index in range(frame_count):
            frame = np.zeros((240, 240, 3), dtype=np.uint8)
            if frame_index >= 30:
                progress = min((frame_index - 30) / 48, 1)
                center = (int(88 + progress * 82), int(152 - progress * 46 + (progress ** 2) * 22))
                cv2.circle(frame, center, 5, (255, 255, 255), -1)
            writer.write(frame)
    finally:
        writer.release()


class BallTrackingTests(unittest.TestCase):
    def test_extracts_post_impact_ball_path_from_video(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / 'ball-flight.avi'
            write_synthetic_ball_video(video_path)

            frames, summary = extract_ball_tracking(
                str(video_path),
                {
                    'fps': 30,
                    'durationMs': 5000,
                    'width': 240,
                    'height': 240,
                },
                {'impact': 1000},
                {'endMs': 4500, 'detectedEndMs': 1900},
            )

        self.assertGreaterEqual(len(frames), 60)
        self.assertGreaterEqual(summary['ballFrameCount'], 8)
        self.assertEqual(summary['launchDirection'], 'right')
        self.assertIn(summary['shotShape'], {'straight', 'fade'})
        self.assertGreater(summary['maxBallSpeedPxPerSec'], 0)
        self.assertFalse(summary['quality']['needsRetake'])
        self.assertFalse(summary['quality']['needsLongerVideo'])
        self.assertEqual(frames[0]['timestampMs'], 833)

    def test_summarizes_missing_or_too_short_ball_tracking_as_retake(self):
        empty_summary = summarize_ball_tracking([], {'width': 240, 'height': 240}, {'impact': 1000})
        self.assertEqual(empty_summary['confidence'], 0)
        self.assertTrue(empty_summary['quality']['needsRetake'])

        short_summary = summarize_ball_tracking(
            [
                {
                    'frameIndex': 30,
                    'timestampMs': 1000,
                    'ball': {'x': 0.45, 'y': 0.65, 'confidence': 0.7, 'source': 'vision_motion'},
                },
                {
                    'frameIndex': 32,
                    'timestampMs': 1066,
                    'ball': {'x': 0.48, 'y': 0.62, 'confidence': 0.7, 'source': 'vision_motion'},
                },
            ],
            {'width': 240, 'height': 240},
            {'impact': 1000},
        )

        self.assertTrue(short_summary['quality']['needsLongerVideo'])
        self.assertIn('Keep recording longer after impact so the ball flight can be tracked.', short_summary['quality']['retakeReasons'])

    def test_estimates_do_not_claim_direction_when_confidence_is_low(self):
        estimates = estimates_from_ball_summary({
            'launchDirection': 'right',
            'shotShape': 'fade',
            'confidence': 0.2,
        })

        self.assertIsNone(estimates['launchDirection'])
        self.assertEqual(estimates['shotShape'], 'fade')


if __name__ == '__main__':
    unittest.main()
