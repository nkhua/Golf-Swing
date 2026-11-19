import { MockOnDeviceSwingAnalyzer, MockServerSwingAnalyzer } from '../services/analyzers/MockSwingAnalyzers';

describe('mock swing analyzers', () => {
  it('return the same normalized payload shape for on-device and server sources', async () => {
    const onDeviceResult = await new MockOnDeviceSwingAnalyzer().analyzeVideo();
    const serverResult = await new MockServerSwingAnalyzer().analyzeVideo();

    for (const result of [onDeviceResult, serverResult]) {
      expect(result.swingId).toBeTruthy();
      expect(result.videoMetadata.cameraAngle).toBe('down_the_line');
      expect(Array.isArray(result.poseFrames)).toBe(true);
      expect(Array.isArray(result.trackingFrames)).toBe(true);
      expect(Array.isArray(result.ballTrackingFrames)).toBe(true);
      expect(result.trackingFrames[0]).toHaveProperty('clubHead');
      expect(result.trackingFrames[0]).toHaveProperty('handMetrics');
      expect(result.trackingFrames[0]).toHaveProperty('headMetrics');
      expect(result.trackingSummary).toHaveProperty('clubFrameCount');
      expect(result.trackingSummary.golfMetrics).toHaveProperty('averageLeftWristAngleDegrees');
      expect(result.trackingSummary.quality.overallTrackingConfidence).toBeGreaterThan(0.8);
      expect(result.ballTrackingFrames[0]).toHaveProperty('ball');
      expect(result.ballFlightSummary).toHaveProperty('ballFrameCount');
      expect(result.ballFlightSummary.quality.needsRetake).toBe(false);
      expect(result.launchMonitor).toHaveProperty('status', 'estimated');
      expect(result.launchMonitor.metrics).toHaveProperty('clubSpeedMph');
      expect(result.launchMonitor.dataQuality.missingMetrics).toContain('spinRateRpm');
      expect(result.impactAnalysis).toHaveProperty('status', 'generated');
      expect(result.impactAnalysis.contactQuality).toHaveProperty('classification', 'likely_centered');
      expect(result.drySwing).toHaveProperty('status', 'not_dry_swing');
      expect(result.swingDiagnosis).toHaveProperty('llmRole', 'wording_only');
      expect(result.swingDiagnosis.expectedActualComparison).toHaveProperty('trainingSignal', 'tracking_or_strike_uncertainty');
      expect(result.swingDiagnosis.priorities[0]).toHaveProperty('id', 'impact-handle-trails');
      expect(result.swingCoaching).toHaveProperty('status', 'generated');
      expect(result.swingCoaching.painPoints[0]).toHaveProperty('timestampMs', 1420);
      expect(result.biomechanics).toHaveProperty('tempoRatio');
      expect(result.swingWindow).toMatchObject({
        startMs: 250,
        detectedEndMs: 2100,
        endMs: 5200,
        postRollMs: 3100,
        method: 'pose_motion',
      });
      expect(result.privacy).toHaveProperty('rawVideoUploaded');
      expect(result.privacy).toHaveProperty('userConsentedToUpload');
      expect(result.privacy).toHaveProperty('videoFramesSentToLlm');
      expect(result.privacy).toHaveProperty('impactFramesSentToLlm');
      expect(result.privacy).toHaveProperty('swingMetricsSentToLlm');
    }

    expect(onDeviceResult.source).toBe('on_device');
    expect(onDeviceResult.privacy.rawVideoUploaded).toBe(false);
    expect(serverResult.source).toBe('server');
    expect(serverResult.privacy.rawVideoUploaded).toBe(true);
  });
});
