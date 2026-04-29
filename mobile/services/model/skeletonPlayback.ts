export const DEFAULT_PLAYBACK_FPS = 30;
const MIN_PLAYBACK_FPS = 1;
const MAX_PLAYBACK_FPS = 120;

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

export function normalizePlaybackFps(fps?: number): number {
  if (typeof fps !== 'number' || !Number.isFinite(fps)) {
    return DEFAULT_PLAYBACK_FPS;
  }

  return clamp(fps, MIN_PLAYBACK_FPS, MAX_PLAYBACK_FPS);
}

export function getTimelineProgress(frameIndex: number, frameCount: number): number {
  if (frameCount <= 1) {
    return 0;
  }

  return clamp(frameIndex / (frameCount - 1), 0, 1);
}

export function getFrameIndexFromProgress(progress: number, frameCount: number): number {
  if (frameCount <= 1) {
    return 0;
  }

  return Math.round(clamp(progress, 0, 1) * (frameCount - 1));
}

export function advanceFrameIndex(
  currentFrameIndex: number,
  stepCount: number,
  frameCount: number,
  loop = true
): number {
  if (frameCount <= 1) {
    return 0;
  }

  const nextFrameIndex = currentFrameIndex + Math.max(0, stepCount);

  if (!loop) {
    return Math.min(nextFrameIndex, frameCount - 1);
  }

  return nextFrameIndex % frameCount;
}
