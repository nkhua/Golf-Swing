import { MockOnDeviceSwingAnalyzer, MockServerSwingAnalyzer } from '../services/analyzers/MockSwingAnalyzers';

describe('mock swing analyzers', () => {
  it('return the same normalized payload shape for on-device and server sources', async () => {
    const onDeviceResult = await new MockOnDeviceSwingAnalyzer().analyzeVideo();
    const serverResult = await new MockServerSwingAnalyzer().analyzeVideo();

    for (const result of [onDeviceResult, serverResult]) {
      expect(result.swingId).toBeTruthy();
      expect(result.videoMetadata.cameraAngle).toBe('down_the_line');
      expect(Array.isArray(result.poseFrames)).toBe(true);
      expect(result.biomechanics).toHaveProperty('tempoRatio');
      expect(result.privacy).toHaveProperty('rawVideoUploaded');
      expect(result.privacy).toHaveProperty('userConsentedToUpload');
    }

    expect(onDeviceResult.source).toBe('on_device');
    expect(onDeviceResult.privacy.rawVideoUploaded).toBe(false);
    expect(serverResult.source).toBe('server');
    expect(serverResult.privacy.rawVideoUploaded).toBe(true);
  });
});
