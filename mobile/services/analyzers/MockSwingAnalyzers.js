import { normalizeSwingPayload } from './SwingAnalyzer';
import { createMockPoseFrames, createMockTrackingFrames } from '../model/mockPoseFrames';

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
    swingWindow: {
      startMs: 250,
      detectedStartMs: 250,
      endMs: 2100,
      startFrameIndex: 0,
      endFrameIndex: 3,
      preRollMs: 0,
      method: 'pose_motion',
      confidence: 0.78,
      notes: 'Detected from mock pose motion.',
    },
    phases: {
      address: 250,
      takeaway: 420,
      topOfBackswing: 1050,
      impact: 1420,
      finish: 2100,
    },
    poseFrames: createMockPoseFrames(),
    trackingFrames: createMockTrackingFrames(),
    trackingSummary: {
      framesTracked: 4,
      wristFrameCount: 4,
      clubFrameCount: 4,
      handFrameCount: 4,
      faceFrameCount: 0,
      headFrameCount: 4,
      bodyFrameCount: 4,
      averageClubConfidence: 0.72,
      leftWristPathLengthPx: 78,
      rightWristPathLengthPx: 78,
      gripPathLengthPx: 78,
      clubHeadPathLengthPx: 242,
      maxGripSpeedPxPerSec: 160,
      maxClubHeadSpeedPxPerSec: 640,
      estimatedImpactMs: 1420,
      clubDetectionMethod: 'pose_hands_face_plus_hough_line_temporal',
      golfMetrics: {
        averageLeftWristAngleDegrees: 145,
        averageRightWristAngleDegrees: 140,
        leftWristAngleAtAddress: 148,
        rightWristAngleAtAddress: 143,
        leftWristAngleAtImpact: 142,
        rightWristAngleAtImpact: 137,
        shaftLeanAtImpactDegrees: -28,
        eyeLineAngleAtAddress: 0,
        eyeLineAngleAtImpact: 0,
        averageHeadTurnProxy: 0.02,
      },
      quality: {
        bodyFrameRatio: 1,
        handFrameRatio: 1,
        faceFrameRatio: 0,
        headFrameRatio: 1,
        clubFrameRatio: 1,
        overallTrackingConfidence: 0.86,
        needsRetake: false,
        retakeReasons: [],
      },
      trackedFeatureSet: [
        'pose_body_landmarks',
        'hand_landmark_wrist_angles',
        'face_or_pose_eye_line',
        'hough_club_shaft_near_grip',
        'temporal_prediction_and_smoothing',
      ],
      notes: 'Mock wrist, grip, shaft, and club-head tracks.',
    },
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
      videoFramesSentToLlm: false,
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
