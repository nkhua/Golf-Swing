export type SwingAnalysisSource = 'on_device' | 'server';

export type CameraAngle = 'down_the_line' | 'face_on' | 'unknown';

export type SwingVideoMetadata = {
  fps: number;
  durationMs: number;
  width: number;
  height: number;
  cameraAngle: CameraAngle;
  clubType?: string;
};

export type PoseLandmark = {
  name: string;
  x: number;
  y: number;
  z?: number;
  visibility?: number;
};

export type FramePoseData = {
  frameIndex: number;
  timestampMs: number;
  landmarks: PoseLandmark[];
};

export type SwingPhaseTimestamps = {
  address?: number;
  takeaway?: number;
  topOfBackswing?: number;
  impact?: number;
  finish?: number;
};

export type SwingBiomechanicsMetrics = {
  // Measured from pose/video geometry when landmarks are available.
  tempoRatio?: number;
  backswingTimeMs?: number;
  downswingTimeMs?: number;
  spineAngleAtAddress?: number;
  shoulderTurnAtTop?: number;
  hipTurnAtTop?: number;
  headMovementPx?: number;
  swayPx?: number;
  // Derived confidence for pose-only biomechanics. Future calibration should compare
  // these values with launch-monitor or lab ground-truth before treating them as final.
  confidence?: number;
};

export type BallFlightEstimates = {
  // Estimated from body/club motion only. These require launch-monitor calibration before
  // being used as ground-truth ball flight metrics.
  launchAngleRange?: [number, number];
  launchDirection?: 'left' | 'straight' | 'right';
  shotShape?: 'draw' | 'fade' | 'straight' | 'unknown';
  carryRangeYards?: [number, number];
  spinTendency?: 'low' | 'medium' | 'high' | 'unknown';
  confidence?: number;
};

export type SwingAnalysisPayload = {
  swingId: string;
  source: SwingAnalysisSource;
  videoMetadata: SwingVideoMetadata;
  phases: SwingPhaseTimestamps;
  poseFrames: FramePoseData[];
  biomechanics: SwingBiomechanicsMetrics;
  ballFlightEstimates?: BallFlightEstimates;
  privacy: {
    rawVideoUploaded: boolean;
    userConsentedToUpload: boolean;
  };
};
