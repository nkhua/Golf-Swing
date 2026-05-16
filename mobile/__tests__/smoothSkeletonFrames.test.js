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
    expect(smoothed[0].joints.pelvis_center.position.x).toBeCloseTo(0.0123);
    expect(smoothed[2].joints.pelvis_center.position.x).toBeCloseTo(0.0477);
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

  it('repairs isolated temporal spikes instead of rendering broken limbs', () => {
    const frames = [makeFrame(0, 0, 0), makeFrame(1, 16, 1), makeFrame(2, 32, 0)];

    const smoothed = smoothSkeletonFrames(frames);

    expect(smoothed[1].joints.pelvis_center.position.x).toBeLessThan(0.2);
  });

  it('preserves directional motion while still damping jitter', () => {
    const frames = [makeFrame(0, 0, 0), makeFrame(1, 16, 0.5), makeFrame(2, 32, 1)];

    const smoothed = smoothSkeletonFrames(frames);

    expect(smoothed[1].joints.pelvis_center.position.x).toBeCloseTo(0.5);
  });

  it('leans harder on neighbors when a landmark confidence drops', () => {
    const frames = [
      makeFrame(0, 0, 0),
      {
        frameIndex: 1,
        timestampMs: 16,
        joints: {
          pelvis_center: makeJoint('pelvis_center', 0.3, 0.2),
        },
      },
      makeFrame(2, 32, 0),
    ];

    const smoothed = smoothSkeletonFrames(frames);

    expect(smoothed[1].joints.pelvis_center.position.x).toBeLessThan(0.08);
  });
});
