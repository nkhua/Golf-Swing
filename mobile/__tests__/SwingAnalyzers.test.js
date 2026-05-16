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
      expect(result.trackingFrames[0]).toHaveProperty('clubHead');
      expect(result.trackingFrames[0]).toHaveProperty('handMetrics');
      expect(result.trackingFrames[0]).toHaveProperty('headMetrics');
      expect(result.trackingSummary).toHaveProperty('clubFrameCount');
      expect(result.trackingSummary.golfMetrics).toHaveProperty('averageLeftWristAngleDegrees');
      expect(result.trackingSummary.quality.overallTrackingConfidence).toBeGreaterThan(0.8);
      expect(result.biomechanics).toHaveProperty('tempoRatio');
      expect(result.swingWindow).toMatchObject({
        startMs: 250,
        endMs: 2100,
        method: 'pose_motion',
      });
      expect(result.privacy).toHaveProperty('rawVideoUploaded');
      expect(result.privacy).toHaveProperty('userConsentedToUpload');
      expect(result.privacy).toHaveProperty('videoFramesSentToLlm');
    }

    expect(onDeviceResult.source).toBe('on_device');
    expect(onDeviceResult.privacy.rawVideoUploaded).toBe(false);
    expect(serverResult.source).toBe('server');
    expect(serverResult.privacy.rawVideoUploaded).toBe(true);
  });
});
