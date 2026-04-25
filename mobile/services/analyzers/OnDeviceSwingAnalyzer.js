import { Platform } from 'react-native';
import { SwingAnalyzer, createFallbackVideoMetadata, normalizeSwingPayload } from './SwingAnalyzer';

const ENABLE_MOCK_ON_DEVICE_ANALYSIS = process.env.EXPO_PUBLIC_ENABLE_MOCK_ON_DEVICE_ANALYSIS === 'true';

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
        poseFrames: [
          {
            frameIndex: 0,
            timestampMs: 0,
            landmarks: [
              { name: 'LEFT_SHOULDER', x: 0.42, y: 0.32, z: -0.02, visibility: 0.92 },
              { name: 'RIGHT_SHOULDER', x: 0.58, y: 0.33, z: -0.01, visibility: 0.92 },
              { name: 'LEFT_HIP', x: 0.44, y: 0.55, z: 0, visibility: 0.9 },
              { name: 'RIGHT_HIP', x: 0.56, y: 0.55, z: 0, visibility: 0.9 },
            ],
          },
        ],
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
