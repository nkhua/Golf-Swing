import { Platform } from 'react-native';
import { SwingAnalyzer, createFallbackVideoMetadata, normalizeSwingPayload } from './SwingAnalyzer';
import { createMockPoseFrames, createMockTrackingFrames } from '../model/mockPoseFrames';

const ANALYSIS_MODE = (process.env.EXPO_PUBLIC_ANALYSIS_MODE || '').toLowerCase();
const ENABLE_MOCK_ON_DEVICE_ANALYSIS =
  process.env.EXPO_PUBLIC_ENABLE_MOCK_ON_DEVICE_ANALYSIS === 'true' || ANALYSIS_MODE === 'mock';

export class OnDeviceSwingAnalyzer extends SwingAnalyzer {
  async isAvailable() {
    // TODO: Expo development build/native module setup.
    // Expo Go cannot load custom native MediaPipe Pose Landmarker modules directly.
    // This returns false until an iOS/Android native module or Vision Camera frame
    // processor is added, while keeping the app architecture on-device-first.
    return ENABLE_MOCK_ON_DEVICE_ANALYSIS;
  }

  async analyzeVideo({ uri, metadata = {} }) {
    const available = await this.isAvailable();
    if (!available) {
      throw new Error(`On-device pose analysis is not available in this ${Platform.OS} build.`);
    }

    // TODO: iOS MediaPipe Pose Landmarker integration.
    // TODO: Android MediaPipe Pose Landmarker integration.
    // TODO: React Native Vision Camera frame processor integration for live frames.
    // Native implementation should return image-coordinate landmarks and, when
    // available, MediaPipe world coordinates without uploading the raw video.
    return normalizeSwingPayload(
      {
        swingId: `local-${Date.now()}`,
        source: 'on_device',
        videoMetadata: createFallbackVideoMetadata(metadata),
        phases: {
          address: 0,
          topOfBackswing: 900,
          impact: 1250,
          finish: 1800,
        },
        poseFrames: createMockPoseFrames(),
        trackingFrames: createMockTrackingFrames(),
        trackingSummary: {
          framesTracked: 4,
          wristFrameCount: 4,
          clubFrameCount: 4,
          averageClubConfidence: 0.72,
          clubDetectionMethod: 'hough_line_near_hands',
        },
        biomechanics: {
          backswingTimeMs: 900,
          downswingTimeMs: 350,
          tempoRatio: 2.57,
          spineAngleAtAddress: 6,
          headMovementPx: 12,
          swayPx: 18,
          confidence: 0.35,
        },
        ballFlightEstimates: {
          actualShotShape: 'unknown',
          spinTendency: 'unknown',
          confidence: 0.05,
        },
        launchMonitor: {
          status: 'insufficient_evidence',
          measurementSystem: 'video_proxy_not_launch_monitor',
          metrics: {},
          dataQuality: {
            confidence: 0,
            requiresCalibration: true,
            missingMetrics: ['clubSpeedMph', 'ballSpeedMph', 'spinRateRpm', 'carryYards'],
          },
        },
        impactAnalysis: {
          status: 'not_available_no_validated_ball',
          modelVersion: 'impact-strike-v1',
          analysisMode: 'dry_swing_or_no_validated_ball',
          measurementSystem: 'not_recorded_without_validated_ball',
          impactTimestampMs: null,
          impactFrame: null,
          clubHeadAtImpact: null,
          ballPositionBeforeImpact: null,
          clubBallProximityPx: null,
          estimatedLowPoint: null,
          shaftLeanAtImpactDegrees: null,
          facePathProxy: null,
          contactQuality: {
            classification: 'not_recorded_no_ball',
            verticalStrike: 'not_recorded_no_ball',
            horizontalStrike: 'not_recorded_no_ball',
            confidence: 0,
            evidence: ['No validated ball track exists, so strike quality was intentionally not recorded.'],
          },
          visualImpactInference: {
            status: 'skipped_no_validated_ball',
            framesSent: 0,
          },
          dataQuality: {
            confidence: 0,
            ballFlightAvailable: false,
            ballFlightStatus: 'no_ball_detected',
          },
        },
        drySwing: {
          status: 'insufficient_evidence',
          mode: 'dry_swing',
          actualBallFlightAvailable: false,
          predictedBallFlight: {
            status: 'insufficient_evidence',
            startDirection: 'unknown',
            curve: 'unknown',
            contactRisk: 'center_contact_unknown',
            trajectory: 'mid_or_unknown',
            confidence: 0,
            evidence: [],
          },
          biomechanicalFindings: [],
          practicePlan: [],
          dataQuality: {
            confidence: 0,
            ballFlightStatus: 'no_ball_detected',
            missingEvidence: ['clubFaceProxy', 'impactShaftLean'],
          },
          notes: 'Dry swing mode needs backend club/head/hand tracking for useful movement feedback.',
        },
        swingDiagnosis: {
          status: 'insufficient_evidence',
          analysisMode: 'dry_swing',
          llmRole: 'wording_only',
          summary: 'On-device mock analysis does not have enough club-delivery evidence for deterministic diagnosis.',
          priorities: [],
          practicePlan: [],
          expectedActualComparison: {
            status: 'no_actual_ball',
            trainingSignal: 'prediction_only',
            expectedOutcome: {
              startDirection: 'unknown',
              curve: 'unknown',
              source: 'not_available_without_ball',
            },
            actualOutcome: {
              startDirection: null,
              curve: 'unknown',
              source: 'not_available',
            },
            agreement: {
              startDirection: 'unknown',
              curve: 'unknown',
              overall: 'unknown',
            },
            uncertaintyFlags: ['no_validated_ball_flight'],
            coachingInstruction: 'Use dry-swing biomechanics as a prediction only; do not claim the ball-flight result.',
            confidence: 0,
          },
          actualBallFlight: {
            status: 'not_available',
            launchDirection: null,
            actualShotShape: 'unknown',
            confidence: 0,
          },
          predictedBallFlight: {
            status: 'insufficient_evidence',
            startDirection: 'unknown',
            curve: 'unknown',
            confidence: 0,
          },
          dataQuality: {
            confidence: 0,
            ballFlightAvailable: false,
            priorityCount: 0,
          },
          sourceFlow: ['vision_tracking', 'deterministic_swing_diagnosis', 'llm_wording_only'],
        },
        privacy: {
          rawVideoUploaded: false,
          userConsentedToUpload: false,
          impactFramesSentToLlm: false,
        },
      },
      { videoMetadata: metadata }
    );
  }

  async analyzeLiveFrames({ frames, metadata = {} }) {
    return this.analyzeVideo({ uri: 'live-camera-stream', frames, metadata });
  }
}
