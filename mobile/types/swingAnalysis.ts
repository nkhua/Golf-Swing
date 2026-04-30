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

export type TrackingPointSource = 'pose_landmark' | 'pose_midpoint' | 'vision_line' | 'temporal_prediction';

export type TrackedPoint = {
  x: number;
  y: number;
  z?: number;
  confidence: number;
  source: TrackingPointSource;
};

export type TrackedLine = {
  start: TrackedPoint;
  end: TrackedPoint;
  confidence: number;
  angleDegrees?: number;
  lengthPx?: number;
  source: TrackingPointSource;
};

export type FrameTrackingData = {
  frameIndex: number;
  timestampMs: number;
  leftWrist?: TrackedPoint;
  rightWrist?: TrackedPoint;
  grip?: TrackedPoint;
  clubHead?: TrackedPoint;
  clubShaft?: TrackedLine;
};

export type SwingTrackingSummary = {
  framesTracked: number;
  wristFrameCount: number;
  clubFrameCount: number;
  averageClubConfidence: number;
  leftWristPathLengthPx?: number;
  rightWristPathLengthPx?: number;
  gripPathLengthPx?: number;
  clubHeadPathLengthPx?: number;
  maxGripSpeedPxPerSec?: number;
  maxClubHeadSpeedPxPerSec?: number;
  estimatedImpactMs?: number;
  clubDetectionMethod?: string;
  notes?: string;
};

export type SwingPhaseTimestamps = {
  address?: number;
  takeaway?: number;
  topOfBackswing?: number;
  impact?: number;
  finish?: number;
};

export type SwingTrimWindow = {
  startMs: number;
  endMs: number;
  startFrameIndex: number;
  endFrameIndex: number;
  method: 'pose_motion' | 'pose_motion_short_clip' | 'llm_vision' | 'fallback_full_video';
  confidence: number;
  notes?: string;
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
  localVideoUri?: string;
  videoMetadata: SwingVideoMetadata;
  swingWindow?: SwingTrimWindow;
  phases: SwingPhaseTimestamps;
  poseFrames: FramePoseData[];
  trackingFrames: FrameTrackingData[];
  trackingSummary?: SwingTrackingSummary;
  biomechanics: SwingBiomechanicsMetrics;
  ballFlightEstimates?: BallFlightEstimates;
  privacy: {
    rawVideoUploaded: boolean;
    userConsentedToUpload: boolean;
    videoFramesSentToLlm?: boolean;
  };
};
