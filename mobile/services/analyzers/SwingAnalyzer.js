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

const normalizeActualShotShape = (value) => {
  if (!value || typeof value !== 'object') {
    return value;
  }

  return {
    ...value,
    actualShotShape: value.actualShotShape,
  };
};

export const normalizeSwingPayload = (payload, defaults = {}) => ({
  swingId: payload?.swingId || defaults.swingId || `swing-${Date.now()}`,
  source: payload?.source || defaults.source || 'server',
  localVideoUri: payload?.localVideoUri || defaults.localVideoUri,
  videoMetadata: {
    ...createFallbackVideoMetadata(defaults.videoMetadata),
    ...(payload?.videoMetadata || {}),
  },
  swingWindow: payload?.swingWindow || defaults.swingWindow,
  phases: payload?.phases || {},
  poseFrames: payload?.poseFrames || [],
  trackingFrames: payload?.trackingFrames || [],
  trackingSummary: payload?.trackingSummary || defaults.trackingSummary,
  ballTrackingFrames: payload?.ballTrackingFrames || defaults.ballTrackingFrames || [],
  ballFlightSummary: normalizeActualShotShape(payload?.ballFlightSummary || defaults.ballFlightSummary),
  launchMonitor: payload?.launchMonitor || defaults.launchMonitor,
  impactAnalysis: payload?.impactAnalysis || defaults.impactAnalysis,
  drySwing: payload?.drySwing || defaults.drySwing,
  swingDiagnosis: payload?.swingDiagnosis || defaults.swingDiagnosis,
  swingCoaching: payload?.swingCoaching || defaults.swingCoaching,
  biomechanics: payload?.biomechanics || {},
  ballFlightEstimates: normalizeActualShotShape(payload?.ballFlightEstimates),
  privacy: {
    rawVideoUploaded: Boolean(payload?.privacy?.rawVideoUploaded),
    userConsentedToUpload: Boolean(payload?.privacy?.userConsentedToUpload),
    ...(defaults.privacy || {}),
    ...(payload?.privacy || {}),
  },
});
