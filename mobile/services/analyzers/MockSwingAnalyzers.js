import { normalizeSwingPayload } from './SwingAnalyzer';

export const createMockSwingAnalysisPayload = (source = 'on_device') =>
  normalizeSwingPayload({
    swingId: `${source}-mock-swing`,
    source,
    videoMetadata: {
      fps: 60,
      durationMs: 2200,
      width: 1080,
      height: 1920,
      cameraAngle: 'down_the_line',
      clubType: '7 iron',
    },
    phases: {
      address: 0,
      takeaway: 420,
      topOfBackswing: 1050,
      impact: 1420,
      finish: 2100,
    },
    poseFrames: [
      {
        frameIndex: 0,
        timestampMs: 0,
        landmarks: [
          { name: 'LEFT_SHOULDER', x: 0.44, y: 0.31, z: -0.03, visibility: 0.95 },
          { name: 'RIGHT_SHOULDER', x: 0.57, y: 0.32, z: -0.02, visibility: 0.95 },
        ],
      },
    ],
    biomechanics: {
      tempoRatio: 2.84,
      backswingTimeMs: 1050,
      downswingTimeMs: 370,
      spineAngleAtAddress: 7,
      shoulderTurnAtTop: 82,
      hipTurnAtTop: 39,
      headMovementPx: 14,
      swayPx: 21,
      confidence: source === 'on_device' ? 0.45 : 0.55,
    },
    ballFlightEstimates: {
      launchDirection: 'straight',
      shotShape: 'unknown',
      spinTendency: 'unknown',
      confidence: 0.1,
    },
    privacy: {
      rawVideoUploaded: source === 'server',
      userConsentedToUpload: source === 'server',
    },
  });

export class MockOnDeviceSwingAnalyzer {
  async isAvailable() {
    return true;
  }

  async analyzeVideo() {
    return createMockSwingAnalysisPayload('on_device');
  }
}

export class MockServerSwingAnalyzer {
  async isAvailable() {
    return true;
  }

  async analyzeVideo() {
    return createMockSwingAnalysisPayload('server');
  }
}
