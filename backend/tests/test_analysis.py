import unittest
from unittest.mock import Mock, patch

from services import analysis


class DummyCapture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return True

    def get(self, _prop):
        return 0

    def release(self):
        self.released = True


class AnalysisTests(unittest.TestCase):
    def test_pose_landmarker_uses_installed_running_mode_enum(self):
        options = object()
        landmarker = object()

        with patch.object(analysis, '_download_model_asset'), \
            patch.object(analysis.base_options, 'BaseOptions', return_value=object()), \
            patch.object(analysis.vision, 'PoseLandmarkerOptions', return_value=options) as pose_options, \
            patch.object(analysis.vision.PoseLandmarker, 'create_from_options', return_value=landmarker):
            result = analysis._create_pose_landmarker()

        self.assertIs(result, landmarker)
        self.assertIs(
            pose_options.call_args.kwargs['running_mode'],
            analysis.VisionTaskRunningMode.IMAGE,
        )

    def test_extract_pose_landmarks_releases_video_when_landmarker_creation_fails(self):
        capture = DummyCapture()

        with patch.object(analysis.cv2, 'VideoCapture', return_value=capture), \
            patch.object(analysis, '_create_pose_landmarker', side_effect=RuntimeError('model failed')):
            with self.assertRaises(RuntimeError):
                analysis.extract_pose_landmarks('swing.mp4')

        self.assertTrue(capture.released)


if __name__ == '__main__':
    unittest.main()
