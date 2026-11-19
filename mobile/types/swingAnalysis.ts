export type SwingAnalysisSource = 'on_device' | 'server';

export type CameraAngle = 'down_the_line' | 'face_on' | 'unknown';
export type CameraFacing = 'front' | 'back';

export type SwingVideoMetadata = {
  fps: number;
  durationMs: number;
  width: number;
  height: number;
  cameraAngle: CameraAngle;
  cameraFacing?: CameraFacing;
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

export type TrackingPointSource =
  | 'pose_landmark'
  | 'pose_midpoint'
  | 'pose_estimate'
  | 'hand_landmark'
  | 'face_landmark'
  | 'vision_line'
  | 'vision_motion'
  | 'temporal_prediction'
  | 'club_proxy';

export type TrackedPoint = {
  x: number;
  y: number;
  z?: number;
  confidence: number;
  source: TrackingPointSource;
  radiusPx?: number;
  diameterPx?: number;
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
  leftElbow?: TrackedPoint;
  rightElbow?: TrackedPoint;
  leftShoulder?: TrackedPoint;
  rightShoulder?: TrackedPoint;
  leftHip?: TrackedPoint;
  rightHip?: TrackedPoint;
  leftHandWrist?: TrackedPoint;
  rightHandWrist?: TrackedPoint;
  leftIndexMcp?: TrackedPoint;
  rightIndexMcp?: TrackedPoint;
  leftMiddleMcp?: TrackedPoint;
  rightMiddleMcp?: TrackedPoint;
  leftPalmCenter?: TrackedPoint;
  rightPalmCenter?: TrackedPoint;
  leftEye?: TrackedPoint;
  rightEye?: TrackedPoint;
  nose?: TrackedPoint;
  chin?: TrackedPoint;
  headCenter?: TrackedPoint;
  grip?: TrackedPoint;
  clubHead?: TrackedPoint;
  clubShaft?: TrackedLine;
  shoulderLine?: TrackedLine;
  hipLine?: TrackedLine;
  spineLine?: TrackedLine;
  leftForearmLine?: TrackedLine;
  rightForearmLine?: TrackedLine;
  eyeLine?: TrackedLine;
  headDirection?: TrackedLine;
  bodyMetrics?: Record<string, number | string | boolean | null | undefined>;
  handMetrics?: Record<string, number | string | boolean | null | undefined>;
  headMetrics?: Record<string, number | string | boolean | null | undefined>;
  clubMetrics?: Record<string, number | string | boolean | null | undefined>;
  quality?: Record<string, number | string | boolean | null | undefined>;
};

export type FrameBallTrackingData = {
  frameIndex: number;
  timestampMs: number;
  ball?: TrackedPoint;
};

export type ClubFaceEstimate = {
  status: 'estimated' | 'partial' | 'insufficient_evidence';
  measurementType: 'video_proxy_not_launch_monitor';
  faceToTarget: 'open' | 'square' | 'closed' | 'unknown';
  faceToPath: 'open' | 'square' | 'closed' | 'unknown';
  clubPathProxy: 'in_to_out' | 'neutral' | 'out_to_in' | 'unknown';
  ballStartDirection: 'left' | 'straight' | 'right' | 'unknown';
  estimatedDegreesToTarget?: number | null;
  estimatedDegreesToPath?: number | null;
  clubPathDegrees?: number | null;
  confidence: number;
  impactTimestampMs?: number | null;
  clubPathEvidence?: Record<string, number | string | boolean | null | undefined>;
  evidence?: string[];
  assumptions?: string[];
  limitations?: string[];
};

export type GolfMetricValue =
  | number
  | string
  | boolean
  | null
  | undefined
  | string[]
  | ClubFaceEstimate
  | Record<string, unknown>;

export type SwingTrackingSummary = {
  framesTracked: number;
  wristFrameCount: number;
  clubFrameCount: number;
  handFrameCount?: number;
  faceFrameCount?: number;
  headFrameCount?: number;
  bodyFrameCount?: number;
  averageClubConfidence: number;
  leftWristPathLengthPx?: number;
  rightWristPathLengthPx?: number;
  gripPathLengthPx?: number;
  clubHeadPathLengthPx?: number;
  maxGripSpeedPxPerSec?: number;
  maxClubHeadSpeedPxPerSec?: number;
  estimatedImpactMs?: number;
  clubDetectionMethod?: string;
  golfMetrics?: Record<string, GolfMetricValue>;
  quality?: {
    bodyFrameRatio?: number;
    handFrameRatio?: number;
    faceFrameRatio?: number;
    headFrameRatio?: number;
    clubFrameRatio?: number;
    overallTrackingConfidence?: number;
    needsRetake?: boolean;
    retakeReasons?: string[];
  };
  trackedFeatureSet?: string[];
  notes?: string;
};

export type BallFlightTrackingSummary = {
  status?: 'tracked' | 'no_ball_detected';
  framesTracked: number;
  ballFrameCount: number;
  ballCandidateFrameCount?: number;
  nearImpactBallFrameCount?: number;
  postImpactBallFrameCount?: number;
  firstBallMs?: number;
  lastBallMs?: number;
  trackingStartMs?: number;
  trackingEndMs?: number;
  averageBallConfidence: number;
  averageCandidateBallConfidence?: number;
  ballPresenceConfidence?: number;
  launchDirection?: 'left' | 'straight' | 'right';
  trajectoryAngleDegrees?: number;
  apexHeightPx?: number;
  carryDistancePx?: number;
  ballPathLengthPx?: number;
  maxBallSpeedPxPerSec?: number;
  curvaturePx?: number;
  actualShotShape?: 'draw' | 'fade' | 'straight' | 'unknown';
  trackingMethod?: string;
  validation?: Record<string, unknown>;
  confidence: number;
  quality?: {
    ballFrameRatio?: number;
    candidateFrameRatio?: number;
    noBallDetected?: boolean;
    needsLongerVideo?: boolean;
    needsRetake?: boolean;
    retakeReasons?: string[];
  };
  notes?: string;
};

export type SwingCoachingPainPoint = {
  id: string;
  category:
    | 'setup'
    | 'backswing'
    | 'downswing'
    | 'impact'
    | 'follow_through'
    | 'ball_flight'
    | 'tracking_quality';
  severity: 'high' | 'medium' | 'low';
  phase:
    | 'address'
    | 'takeaway'
    | 'topOfBackswing'
    | 'downswing'
    | 'impact'
    | 'finish'
    | 'ballFlight'
    | 'overall';
  title: string;
  evidence: string;
  videoCue: string;
  timestampMs: number;
  endTimestampMs: number;
  recommendation: string;
  drill: string;
  relatedMetrics: string[];
  confidence: number;
};

export type SwingCoachingAnalysis = {
  status: 'generated' | 'disabled' | 'missing_api_key' | 'failed' | 'insufficient_evidence';
  model?: string;
  generatedAt?: string;
  summary?: string;
  painPoints: SwingCoachingPainPoint[];
  confidence: number;
  notes?: string;
};

export type LaunchMonitorMetrics = {
  status?: 'estimated' | 'partial' | 'insufficient_evidence';
  measurementSystem?: 'video_proxy_not_launch_monitor';
  modelVersion?: string;
  calibration?: {
    status?: 'calibrated' | 'estimated' | 'pixel_only';
    method?: string;
    yardsPerPixel?: number | null;
    ballDiameterPx?: number;
    confidence?: number;
    notes?: string;
  };
  metrics?: {
    clubSpeedMph?: number | null;
    clubSpeedPxPerSec?: number | null;
    ballSpeedMph?: number | null;
    ballSpeedPxPerSec?: number | null;
    smashFactor?: number | null;
    smashFactorProxy?: number | null;
    launchAngleDegrees?: number | null;
    launchDirection?: 'left' | 'straight' | 'right' | 'unknown';
    launchDirectionDegrees?: number | null;
    attackAngleDegrees?: number | null;
    attackDirection?: 'up' | 'level' | 'down' | 'unknown';
    clubPathDegrees?: number | null;
    clubPathProxy?: 'in_to_out' | 'neutral' | 'out_to_in' | 'unknown';
    faceAngleDegrees?: number | null;
    faceToPathDegrees?: number | null;
    faceToTarget?: 'open' | 'square' | 'closed' | 'unknown';
    faceToPath?: 'open' | 'square' | 'closed' | 'unknown';
    actualShotShape?: 'draw' | 'fade' | 'straight' | 'unknown';
    spinRateRpm?: number | null;
    spinAxisDegrees?: number | null;
    spinAxisProxy?: string;
    carryYards?: number | null;
    visibleBallTravelYards?: number | null;
    visibleCarryYards?: number | null;
    apexHeightYards?: number | null;
    curveYards?: number | null;
    landingAngleDegrees?: number | null;
    totalDistanceYards?: number | null;
  };
  dataQuality?: {
    confidence?: number;
    clubSpeedConfidence?: number;
    ballSpeedConfidence?: number;
    launchConfidence?: number;
    attackAngleConfidence?: number;
    calibrationConfidence?: number;
    requiresCalibration?: boolean;
    missingMetrics?: string[];
  };
  interpretation?: Array<{
    id: string;
    severity: 'high' | 'medium' | 'low';
    text: string;
  }>;
  definitions?: Record<string, string>;
  notes?: string;
};

export type ImpactAnalysis = {
  status?: 'generated' | 'not_available_no_validated_ball' | 'insufficient_evidence';
  modelVersion?: string;
  analysisMode?: 'ball_strike' | 'dry_swing_or_no_validated_ball';
  measurementSystem?: 'single_camera_video_proxy' | 'not_recorded_without_validated_ball';
  impactTimestampMs?: number | null;
  impactFrame?: {
    frameIndex?: number | null;
    timestampMs?: number | null;
    clubTrackingFrameTimestampMs?: number | null;
    ballTrackingFrameTimestampMs?: number | null;
  } | null;
  clubHeadAtImpact?: Record<string, unknown> | null;
  ballPositionBeforeImpact?: Record<string, unknown> | null;
  clubBallProximityPx?: number | null;
  clubBallHorizontalOffsetPx?: number | null;
  clubBallVerticalOffsetPx?: number | null;
  estimatedBallDiameterPx?: number | null;
  estimatedLowPoint?: {
    status?: 'estimated' | 'unavailable';
    timestampMs?: number | null;
    frameIndex?: number | null;
    clubHeadYpx?: number | null;
    relativeToImpactMs?: number | null;
    relativeToBallYPx?: number | null;
    classification?: string;
    confidence?: number;
    notes?: string;
  } | null;
  shaftLeanAtImpactDegrees?: number | null;
  facePathProxy?: {
    faceToTarget?: 'open' | 'square' | 'closed' | 'unknown';
    faceToPath?: 'open' | 'square' | 'closed' | 'unknown';
    faceAngleDegrees?: number | null;
    faceToPathDegrees?: number | null;
    clubPathProxy?: 'in_to_out' | 'neutral' | 'out_to_in' | 'unknown';
    clubPathDegrees?: number | null;
    confidence?: number;
    visualFaceAngle?: 'open' | 'square' | 'closed' | 'unknown';
    visualFaceConfidence?: number;
    measurementType?: string;
  } | null;
  contactQuality?: {
    classification?: 'likely_centered' | 'thin' | 'fat' | 'heel' | 'toe' | 'off_center_unknown' | 'unknown' | 'not_recorded_no_ball';
    verticalStrike?: string;
    horizontalStrike?: string;
    llmClassification?: string;
    confidence?: number;
    evidence?: string[];
  };
  visualImpactInference?: {
    status?: 'generated' | 'not_requested' | 'skipped_no_validated_ball' | 'failed';
    model?: string;
    generatedAt?: string;
    framesSent?: number;
    reason?: string;
    contactLikely?: boolean;
    strikeLocation?: 'center' | 'thin' | 'fat' | 'heel' | 'toe' | 'unknown';
    clubFaceAngle?: 'open' | 'square' | 'closed' | 'unknown';
    clubFaceVisible?: boolean;
    ballVisible?: boolean;
    impactFrameQuality?: 'clear' | 'motion_blur' | 'occluded' | 'unknown';
    confidence?: number;
    evidence?: string[];
    limitations?: string[];
  };
  dataQuality?: {
    confidence?: number;
    ballFlightConfidence?: number | null;
    trackingConfidence?: number | null;
    clubFaceProxyConfidence?: number | null;
    visualRefinementConfidence?: number | null;
    ballFlightAvailable?: boolean;
    ballFlightStatus?: string;
    limitations?: string[];
  };
  notes?: string;
};

export type DrySwingPredictedBallFlight = {
  status?: 'predicted_from_dry_swing' | 'insufficient_evidence' | 'not_applicable';
  startDirection?: 'left' | 'straight' | 'right' | 'unknown';
  curve?: 'draw' | 'fade' | 'straight' | 'unknown';
  contactRisk?: string;
  trajectory?: string;
  confidence?: number;
  evidence?: string[];
  notes?: string;
};

export type DrySwingBiomechanicalFinding = {
  id: string;
  category:
    | 'setup'
    | 'backswing'
    | 'downswing'
    | 'impact'
    | 'follow_through'
    | 'ball_flight'
    | 'tracking_quality'
    | 'tempo'
    | 'head'
    | 'wrist';
  severity: 'high' | 'medium' | 'low';
  phase:
    | 'address'
    | 'takeaway'
    | 'topOfBackswing'
    | 'downswing'
    | 'impact'
    | 'finish'
    | 'ballFlight'
    | 'overall';
  timestampMs: number;
  endTimestampMs?: number;
  title: string;
  evidence: string;
  videoCue?: string;
  likelyEffect?: string;
  fix: string;
  drill: string;
  relatedMetrics?: string[];
  confidence?: number;
};

export type DrySwingPracticePlanItem = {
  priority: number;
  title?: string;
  phase?: string;
  drill?: string;
  checkpoint?: string;
};

export type DrySwingAnalysis = {
  status?: 'generated' | 'not_dry_swing' | 'insufficient_evidence';
  mode?: 'dry_swing' | 'ball_strike';
  modelVersion?: string;
  actualBallFlightAvailable?: boolean;
  predictedBallFlight?: DrySwingPredictedBallFlight;
  biomechanicalFindings?: DrySwingBiomechanicalFinding[];
  practicePlan?: DrySwingPracticePlanItem[];
  dataQuality?: {
    confidence?: number;
    biomechanicsConfidence?: number | null;
    trackingConfidence?: number | null;
    clubSpeedAvailable?: boolean;
    clubFaceProxyAvailable?: boolean;
    ballFlightStatus?: string;
    ballCandidateFrameCount?: number;
    missingEvidence?: string[];
    limitations?: string[];
  };
  notes?: string;
};

export type SwingDiagnosisPriority = {
  id: string;
  source?: string;
  category:
    | 'setup'
    | 'backswing'
    | 'downswing'
    | 'impact'
    | 'follow_through'
    | 'ball_flight'
    | 'tracking_quality'
    | 'tempo'
    | 'head'
    | 'wrist';
  severity: 'high' | 'medium' | 'low';
  phase:
    | 'address'
    | 'takeaway'
    | 'topOfBackswing'
    | 'downswing'
    | 'impact'
    | 'finish'
    | 'ballFlight'
    | 'overall';
  timestampMs: number;
  endTimestampMs: number;
  title: string;
  evidence: string;
  videoCue: string;
  likelyEffect?: string;
  recommendation: string;
  drill: string;
  relatedMetrics?: string[];
  confidence?: number;
  llmInstruction?: string;
};

export type SwingDiagnosis = {
  status?: 'generated' | 'insufficient_evidence';
  modelVersion?: string;
  analysisMode?: 'ball_strike' | 'dry_swing';
  llmRole?: 'wording_only';
  summary?: string;
  priorities?: SwingDiagnosisPriority[];
  practicePlan?: DrySwingPracticePlanItem[];
  expectedActualComparison?: {
    status?: 'generated' | 'no_actual_ball';
    trainingSignal?:
      | 'delivery_prediction_confirmed'
      | 'prediction_matches_with_uncertainty'
      | 'tracking_or_strike_uncertainty'
      | 'insufficient_comparison_evidence'
      | 'prediction_only';
    expectedOutcome?: {
      startDirection?: 'left' | 'straight' | 'right' | 'unknown';
      curve?: 'draw' | 'fade' | 'straight' | 'unknown';
      clubPathProxy?: 'in_to_out' | 'neutral' | 'out_to_in' | 'unknown';
      faceToTarget?: 'open' | 'square' | 'closed' | 'unknown';
      faceToPath?: 'open' | 'square' | 'closed' | 'unknown';
      source?: string;
    };
    actualOutcome?: {
      startDirection?: 'left' | 'straight' | 'right' | 'unknown' | null;
      curve?: 'draw' | 'fade' | 'straight' | 'unknown';
      source?: string;
    };
    agreement?: {
      startDirection?: 'match' | 'mismatch' | 'unknown';
      curve?: 'match' | 'mismatch' | 'unknown';
      overall?: 'match' | 'mismatch' | 'partial' | 'unknown';
    };
    uncertaintyFlags?: string[];
    coachingInstruction?: string;
    confidence?: number;
    notes?: string;
  };
  actualBallFlight?: {
    status?: 'measured_from_validated_ball_track' | 'not_available';
    source?: string;
    launchDirection?: 'left' | 'straight' | 'right' | 'unknown' | null;
    actualShotShape?: 'draw' | 'fade' | 'straight' | 'unknown';
    trajectoryAngleDegrees?: number | null;
    maxBallSpeedPxPerSec?: number | null;
    confidence?: number;
    notes?: string;
  };
  predictedBallFlight?: DrySwingPredictedBallFlight | null;
  dataQuality?: {
    confidence?: number;
    trackingConfidence?: number | null;
    launchMonitorConfidence?: number | null;
    ballFlightAvailable?: boolean;
    priorityCount?: number;
    limitations?: string[];
  };
  sourceFlow?: string[];
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
  detectedStartMs?: number;
  detectedEndMs?: number;
  endMs: number;
  startFrameIndex: number;
  endFrameIndex: number;
  preRollMs?: number;
  postRollMs?: number;
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
  actualShotShape?: 'draw' | 'fade' | 'straight' | 'unknown';
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
  ballTrackingFrames?: FrameBallTrackingData[];
  ballFlightSummary?: BallFlightTrackingSummary;
  launchMonitor?: LaunchMonitorMetrics;
  impactAnalysis?: ImpactAnalysis;
  drySwing?: DrySwingAnalysis;
  swingDiagnosis?: SwingDiagnosis;
  swingCoaching?: SwingCoachingAnalysis;
  biomechanics: SwingBiomechanicsMetrics;
  ballFlightEstimates?: BallFlightEstimates;
  privacy: {
    rawVideoUploaded: boolean;
    userConsentedToUpload: boolean;
    videoFramesSentToLlm?: boolean;
    impactFramesSentToLlm?: boolean;
    swingMetricsSentToLlm?: boolean;
  };
};
