import { smoothSkeletonFrames } from '../services/model/smoothSkeletonFrames';

const makeJoint = (name, x, visibility = 0.9) => ({
  name,
  position: { x, y: 0, z: 0 },
  visibility,
});

const makeFrame = (frameIndex, timestampMs, x) => ({
  frameIndex,
  timestampMs,
  joints: {
    pelvis_center: makeJoint('pelvis_center', x),
  },
});

describe('smoothSkeletonFrames', () => {
  it('applies a window-3 moving average and preserves timestamps', () => {
    const frames = [makeFrame(0, 0, 0), makeFrame(1, 16, 0.03), makeFrame(2, 32, 0.06)];

    const smoothed = smoothSkeletonFrames(frames);

    expect(smoothed.map((frame) => frame.timestampMs)).toEqual([0, 16, 32]);
    expect(smoothed[1].joints.pelvis_center.position.x).toBeCloseTo(0.03);
    expect(smoothed[0].joints.pelvis_center.position.x).toBeCloseTo(0.015);
    expect(smoothed[2].joints.pelvis_center.position.x).toBeCloseTo(0.045);
  });

  it('handles missing joints safely', () => {
    const frames = [
      makeFrame(0, 0, 0),
      { frameIndex: 1, timestampMs: 16, joints: {} },
      makeFrame(2, 32, 0.06),
    ];

    const smoothed = smoothSkeletonFrames(frames);

    expect(smoothed[1].joints.pelvis_center).toBeUndefined();
    expect(smoothed[0].joints.pelvis_center.position.x).toBe(0);
    expect(smoothed[2].joints.pelvis_center.position.x).toBe(0.06);
  });

  it('reduces smoothing on rapid motion', () => {
    const frames = [makeFrame(0, 0, 0), makeFrame(1, 16, 1), makeFrame(2, 32, 0)];

    const smoothed = smoothSkeletonFrames(frames);

    expect(smoothed[1].joints.pelvis_center.position.x).toBeGreaterThan(0.65);
    expect(smoothed[1].joints.pelvis_center.position.x).toBeLessThan(1);
  });
});
