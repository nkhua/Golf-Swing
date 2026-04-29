import {
  advanceFrameIndex,
  getFrameIndexFromProgress,
  getTimelineProgress,
  normalizePlaybackFps,
} from '../services/model/skeletonPlayback';

describe('skeleton playback helpers', () => {
  it('normalizes fps to a safe range', () => {
    expect(normalizePlaybackFps()).toBe(30);
    expect(normalizePlaybackFps(0)).toBe(1);
    expect(normalizePlaybackFps(240)).toBe(120);
    expect(normalizePlaybackFps(60)).toBe(60);
  });

  it('maps timeline progress to frame indexes', () => {
    expect(getFrameIndexFromProgress(0, 5)).toBe(0);
    expect(getFrameIndexFromProgress(0.5, 5)).toBe(2);
    expect(getFrameIndexFromProgress(1, 5)).toBe(4);
    expect(getFrameIndexFromProgress(2, 5)).toBe(4);
  });

  it('advances frame indexes with loop playback', () => {
    expect(advanceFrameIndex(3, 2, 5, true)).toBe(0);
    expect(advanceFrameIndex(3, 2, 5, false)).toBe(4);
  });

  it('calculates timeline progress', () => {
    expect(getTimelineProgress(2, 5)).toBe(0.5);
    expect(getTimelineProgress(2, 1)).toBe(0);
  });
});
