export class SwingAnalyzer {
  async isAvailable() {
    return false;
  }

  async analyzeVideo(_input) {
    throw new Error('SwingAnalyzer.analyzeVideo must be implemented by a concrete analyzer.');
  }

  async analyzeLiveFrames(_input) {
    throw new Error('Live frame analysis is not implemented for this analyzer.');
  }
}

export const createFallbackVideoMetadata = (overrides = {}) => ({
  fps: 0,
  durationMs: 0,
  width: 0,
  height: 0,
  cameraAngle: 'down_the_line',
  ...overrides,
});

export const normalizeSwingPayload = (payload, defaults = {}) => ({
  swingId: payload?.swingId || defaults.swingId || `swing-${Date.now()}`,
  source: payload?.source || defaults.source || 'server',
  localVideoUri: payload?.localVideoUri || defaults.localVideoUri,
  videoMetadata: {
    ...createFallbackVideoMetadata(defaults.videoMetadata),
    ...(payload?.videoMetadata || {}),
  },
  phases: payload?.phases || {},
  poseFrames: payload?.poseFrames || [],
  biomechanics: payload?.biomechanics || {},
  ballFlightEstimates: payload?.ballFlightEstimates,
  privacy: {
    rawVideoUploaded: Boolean(payload?.privacy?.rawVideoUploaded),
    userConsentedToUpload: Boolean(payload?.privacy?.userConsentedToUpload),
    ...(defaults.privacy || {}),
    ...(payload?.privacy || {}),
  },
});
