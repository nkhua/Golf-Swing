import React from 'react';
import { render } from '@testing-library/react-native';
import Skeleton3DViewer from '../components/Skeleton3DViewer';
import { createSkeletonFrameFromNamedPoseLandmarks } from '../services/model/createSkeletonFrame';

const makeLandmarks = () =>
  [
    ['NOSE', 0.5, 0.18, -0.05],
    ['LEFT_SHOULDER', 0.42, 0.34, -0.02],
    ['RIGHT_SHOULDER', 0.58, 0.34, -0.02],
    ['LEFT_ELBOW', 0.36, 0.46, -0.02],
    ['RIGHT_ELBOW', 0.64, 0.46, -0.02],
    ['LEFT_WRIST', 0.32, 0.58, -0.02],
    ['RIGHT_WRIST', 0.68, 0.58, -0.02],
    ['LEFT_HIP', 0.45, 0.58, 0],
    ['RIGHT_HIP', 0.55, 0.58, 0],
    ['LEFT_KNEE', 0.44, 0.76, 0.02],
    ['RIGHT_KNEE', 0.56, 0.76, 0.02],
    ['LEFT_ANKLE', 0.43, 0.94, 0.02],
    ['RIGHT_ANKLE', 0.57, 0.94, 0.02],
  ].map(([name, x, y, z]) => ({ name, x, y, z, visibility: 0.9 }));

describe('Skeleton3DViewer', () => {
  it('renders skeleton playback controls without native GL dependencies', () => {
    const frame = createSkeletonFrameFromNamedPoseLandmarks(makeLandmarks(), 0, 0);
    const screen = render(<Skeleton3DViewer frames={[frame]} fps={30} />);

    expect(screen.getByText('Play')).toBeTruthy();
    expect(screen.getByText('1/1')).toBeTruthy();
  });
});
