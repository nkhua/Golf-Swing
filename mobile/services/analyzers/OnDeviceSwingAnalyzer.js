import { Platform } from 'react-native';
import { SwingAnalyzer, createFallbackVideoMetadata, normalizeSwingPayload } from './SwingAnalyzer';
import { createMockPoseFrames } from '../model/mockPoseFrames';

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
          shotShape: 'unknown',
          spinTendency: 'unknown',
          confidence: 0.05,
        },
        privacy: {
          rawVideoUploaded: false,
          userConsentedToUpload: false,
        },
      },
      { videoMetadata: metadata }
    );
  }

  async analyzeLiveFrames({ frames, metadata = {} }) {
    return this.analyzeVideo({ uri: 'live-camera-stream', frames, metadata });
  }
}
