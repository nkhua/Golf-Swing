import { normalizeSwingPayload } from './SwingAnalyzer';
import { createMockBallTrackingFrames, createMockPoseFrames, createMockTrackingFrames } from '../model/mockPoseFrames';

export const createMockSwingAnalysisPayload = (source = 'on_device') =>
  normalizeSwingPayload({
    swingId: `${source}-mock-swing`,
    source,
    videoMetadata: {
      fps: 60,
      durationMs: 5600,
      width: 1080,
      height: 1920,
      cameraAngle: 'down_the_line',
      clubType: '7 iron',
    },
    swingWindow: {
      startMs: 250,
      detectedStartMs: 250,
      detectedEndMs: 2100,
      endMs: 5200,
      startFrameIndex: 0,
      endFrameIndex: 312,
      preRollMs: 0,
      postRollMs: 3100,
      method: 'pose_motion',
      confidence: 0.78,
      notes: 'Detected from mock pose motion with post-impact ball-flight playback.',
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
    ballTrackingFrames: createMockBallTrackingFrames(),
    ballFlightSummary: {
      framesTracked: 6,
      ballFrameCount: 6,
      firstBallMs: 1420,
      lastBallMs: 2800,
      trackingStartMs: 1420,
      trackingEndMs: 2800,
      averageBallConfidence: 0.72,
      launchDirection: 'right',
      trajectoryAngleDegrees: 18.5,
      apexHeightPx: 365,
      carryDistancePx: 367,
      ballPathLengthPx: 502,
      maxBallSpeedPxPerSec: 1410,
      curvaturePx: 24,
      shotShape: 'fade',
      trackingMethod: 'bright_motion_contours_after_impact',
      confidence: 0.78,
      quality: {
        ballFrameRatio: 1,
        needsLongerVideo: false,
        needsRetake: false,
        retakeReasons: [],
      },
      notes: 'Mock post-impact ball track.',
    },
    swingCoaching: {
      status: 'generated',
      model: 'mock-golf-coach',
      generatedAt: '2026-05-15T00:00:00Z',
      summary: 'The strongest pattern is a late impact cue: the shaft is leaning back while the ball starts right, so the first fix is improving handle position through impact.',
      painPoints: [
        {
          id: 'impact-shaft-lean',
          category: 'impact',
          severity: 'high',
          phase: 'impact',
          title: 'Handle is arriving behind the club head',
          evidence: 'Impact shaft lean is measured at -28 deg with a right-starting ball trace.',
          videoCue: 'At impact, compare the grip point to the club head; the handle should not trail the head.',
          timestampMs: 1420,
          endTimestampMs: 1700,
          recommendation: 'Feel the lead wrist flatter and the handle slightly ahead of the ball through impact.',
          drill: 'Make half-speed punch swings stopping just after impact with the handle ahead of the club head.',
          relatedMetrics: ['shaftLeanAtImpactDegrees', 'launchDirection', 'shotShape'],
          confidence: 0.78,
        },
        {
          id: 'head-turn-impact',
          category: 'downswing',
          severity: 'medium',
          phase: 'impact',
          title: 'Head and eye line leave the ball early',
          evidence: 'The tracked head-turn proxy changes near impact while the eye-line cue is available.',
          videoCue: 'Watch the head marker at impact; it should stay quiet until after the strike.',
          timestampMs: 1420,
          endTimestampMs: 1900,
          recommendation: 'Keep your chest rotating while your eyes stay on the strike point a fraction longer.',
          drill: 'Hit slow chips while holding your finish and naming the exact spot where the ball sat.',
          relatedMetrics: ['headTurnAtImpact', 'eyeLineAngleAtImpact'],
          confidence: 0.68,
        },
      ],
      confidence: 0.75,
      notes: 'Mock coaching generated from structured swing metrics.',
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
      launchDirection: 'right',
      shotShape: 'fade',
      spinTendency: 'unknown',
      confidence: 0.78,
    },
    privacy: {
      rawVideoUploaded: source === 'server',
      userConsentedToUpload: source === 'server',
      videoFramesSentToLlm: false,
      swingMetricsSentToLlm: false,
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
