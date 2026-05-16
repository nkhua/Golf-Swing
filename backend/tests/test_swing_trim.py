import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.swing_trim import (
    _parse_llm_window,
    apply_swing_window,
    estimate_swing_window_from_pose,
    refine_swing_window_with_llm,
)


def landmark(name, x, y):
    return {'name': name, 'x': x, 'y': y, 'z': 0, 'visibility': 0.95}


def pose_frame(index, timestamp_ms, wrist_x):
    return {
        'frameIndex': index,
        'timestampMs': timestamp_ms,
        'landmarks': [
            landmark('LEFT_WRIST', wrist_x, 0.45),
            landmark('RIGHT_WRIST', wrist_x + 0.1, 0.45),
            landmark('LEFT_ELBOW', wrist_x + 0.02, 0.38),
            landmark('RIGHT_ELBOW', wrist_x + 0.08, 0.38),
            landmark('LEFT_SHOULDER', 0.42, 0.32),
            landmark('RIGHT_SHOULDER', 0.58, 0.32),
            landmark('LEFT_HIP', 0.44, 0.56),
            landmark('RIGHT_HIP', 0.56, 0.56),
        ],
    }


class SwingTrimTests(unittest.TestCase):
    def test_estimates_motion_window_and_phases(self):
        frames = [
            pose_frame(0, 0, 0.35),
            pose_frame(1, 400, 0.35),
            pose_frame(2, 800, 0.48),
            pose_frame(3, 1200, 0.68),
            pose_frame(4, 1600, 0.52),
            pose_frame(5, 2000, 0.5),
        ]

        window, phases = estimate_swing_window_from_pose(frames, {'durationMs': 2400})

        self.assertEqual(window['method'], 'pose_motion')
        self.assertGreaterEqual(window['endMs'], window['startMs'] + 900)
        self.assertGreater(window['confidence'], 0.45)
        self.assertEqual(phases['address'], window['detectedStartMs'])
        self.assertEqual(phases['finish'], window['endMs'])
        self.assertGreaterEqual(phases['impact'], phases['topOfBackswing'])

    def test_motion_window_includes_two_second_preroll_before_detected_start(self):
        frames = [
            pose_frame(0, 0, 0.35),
            pose_frame(1, 1000, 0.35),
            pose_frame(2, 2000, 0.35),
            pose_frame(3, 3000, 0.35),
            pose_frame(4, 4000, 0.35),
            pose_frame(5, 5000, 0.48),
            pose_frame(6, 6000, 0.68),
            pose_frame(7, 7000, 0.52),
        ]

        window, phases = estimate_swing_window_from_pose(frames, {'durationMs': 7600})

        self.assertEqual(window['detectedStartMs'], 3000)
        self.assertEqual(window['startMs'], 1000)
        self.assertEqual(window['preRollMs'], 2000)
        self.assertEqual(phases['address'], 3000)

    def test_llm_window_includes_two_second_preroll_before_detected_start(self):
        window = _parse_llm_window(
            '{"startMs": 4500, "endMs": 7200, "confidence": 0.8, "notes": "Clean swing."}',
            9000,
        )

        self.assertIsNotNone(window)
        self.assertEqual(window['detectedStartMs'], 4500)
        self.assertEqual(window['startMs'], 2500)
        self.assertEqual(window['preRollMs'], 2000)

    def test_applies_window_to_pose_frames_without_emptying_data(self):
        frames = [
            pose_frame(0, 0, 0.35),
            pose_frame(1, 500, 0.48),
            pose_frame(2, 1000, 0.68),
            pose_frame(3, 1500, 0.52),
        ]

        trimmed = apply_swing_window(frames, {'startMs': 450, 'endMs': 1200})
        fallback = apply_swing_window(frames, {'startMs': 3000, 'endMs': 4000})

        self.assertEqual([frame['frameIndex'] for frame in trimmed], [1, 2])
        self.assertEqual(fallback, frames)

    def test_llm_refinement_is_privacy_gated(self):
        disabled_settings = SimpleNamespace(send_video_to_llm=False, openai_api_key='secret')
        with patch('services.swing_trim.settings', disabled_settings):
            result = refine_swing_window_with_llm(
                'swing.mp4',
                {'startMs': 0, 'endMs': 1000},
                {'durationMs': 1500},
            )

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
