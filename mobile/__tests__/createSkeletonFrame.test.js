import {
  createSkeletonFrameFromNamedPoseLandmarks,
  createSkeletonFrameFromPoseLandmarks,
} from '../services/model/createSkeletonFrame';

const makeLandmarks = () =>
  Array.from({ length: 33 }, (_, index) => ({
    x: index,
    y: index + 100,
    z: index + 200,
    visibility: 0.9,
  }));

describe('createSkeletonFrameFromPoseLandmarks', () => {
  it('creates a pelvis-normalized skeleton frame from MediaPipe pose landmarks', () => {
    const landmarks = makeLandmarks();
    landmarks[0] = { x: 5, y: 10, z: 15, visibility: 0.8 };
    landmarks[11] = { x: 2, y: 20, z: 3, visibility: 0.7 };
    landmarks[12] = { x: 6, y: 24, z: 7, visibility: 0.9 };
    landmarks[23] = { x: 10, y: 40, z: 20, visibility: 0.6 };
    landmarks[24] = { x: 14, y: 40, z: 22, visibility: 0.8 };

    const frame = createSkeletonFrameFromPoseLandmarks(landmarks, 12, 400);

    expect(frame.frameIndex).toBe(12);
    expect(frame.timestampMs).toBe(400);
    expect(frame.joints.pelvis_center.position).toEqual({ x: 0, y: 0, z: 0 });
    expect(frame.joints.chest_center.position).toEqual({ x: -8, y: -18, z: -16 });
    expect(frame.joints.head.position).toEqual({ x: -7, y: -30, z: -6 });
    expect(frame.joints.left_hip.position).toEqual({ x: -2, y: 0, z: -1 });
    expect(frame.joints.right_hip.position).toEqual({ x: 2, y: 0, z: 1 });
    expect(frame.joints.pelvis_center.visibility).toBeCloseTo(0.7);
    expect(frame.joints.chest_center.visibility).toBeCloseTo(0.8);
  });

  it('throws when required MediaPipe landmarks are missing', () => {
    expect(() => createSkeletonFrameFromPoseLandmarks([])).toThrow(
      'Expected at least 29 MediaPipe pose landmarks'
    );
  });

  it('creates a skeleton frame from named app pose landmarks', () => {
    const landmarks = [
      ['NOSE', 5, 10, 15],
      ['LEFT_SHOULDER', 2, 20, 3],
      ['RIGHT_SHOULDER', 6, 24, 7],
      ['LEFT_ELBOW', 1, 30, 4],
      ['RIGHT_ELBOW', 7, 30, 8],
      ['LEFT_WRIST', 0, 36, 4],
      ['RIGHT_WRIST', 8, 36, 8],
      ['LEFT_HIP', 10, 40, 20],
      ['RIGHT_HIP', 14, 40, 22],
      ['LEFT_KNEE', 10, 50, 20],
      ['RIGHT_KNEE', 14, 50, 22],
      ['LEFT_ANKLE', 10, 60, 20],
      ['RIGHT_ANKLE', 14, 60, 22],
    ].map(([name, x, y, z]) => ({ name, x, y, z, visibility: 0.9 }));

    const frame = createSkeletonFrameFromNamedPoseLandmarks(landmarks, 2, 120);

    expect(frame.frameIndex).toBe(2);
    expect(frame.timestampMs).toBe(120);
    expect(frame.joints.pelvis_center.position).toEqual({ x: 0, y: 0, z: 0 });
    expect(frame.joints.chest_center.position).toEqual({ x: -8, y: -18, z: -16 });
    expect(frame.joints.left_wrist.position).toEqual({ x: -12, y: -4, z: -17 });
  });
});
