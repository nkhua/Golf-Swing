from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


CameraAngle = Literal['down_the_line', 'face_on', 'unknown']
AnalysisSource = Literal['on_device', 'server']
TrackingPointSource = Literal['pose_landmark', 'pose_midpoint', 'vision_line', 'temporal_prediction']


def dump_model(model: BaseModel, **kwargs) -> Dict:
    if hasattr(model, 'model_dump'):
        return model.model_dump(**kwargs)
    return model.dict(**kwargs)


class SwingVideoMetadata(BaseModel):
    fps: float = 0
    durationMs: int = 0
    width: int = 0
    height: int = 0
    cameraAngle: CameraAngle = 'unknown'
    clubType: Optional[str] = None


class PoseLandmark(BaseModel):
    name: str
    x: float
    y: float
    z: Optional[float] = None
    visibility: Optional[float] = None


class FramePoseData(BaseModel):
    frameIndex: int
    timestampMs: int
    landmarks: List[PoseLandmark] = Field(default_factory=list)


class TrackedPoint(BaseModel):
    x: float
    y: float
    z: Optional[float] = None
    confidence: float = 0
    source: TrackingPointSource


class TrackedLine(BaseModel):
    start: TrackedPoint
    end: TrackedPoint
    confidence: float = 0
    angleDegrees: Optional[float] = None
    lengthPx: Optional[float] = None
    source: TrackingPointSource


class FrameTrackingData(BaseModel):
    frameIndex: int
    timestampMs: int
    leftWrist: Optional[TrackedPoint] = None
    rightWrist: Optional[TrackedPoint] = None
    grip: Optional[TrackedPoint] = None
    clubHead: Optional[TrackedPoint] = None
    clubShaft: Optional[TrackedLine] = None


class SwingTrackingSummary(BaseModel):
    framesTracked: int = 0
    wristFrameCount: int = 0
    clubFrameCount: int = 0
    averageClubConfidence: float = 0
    leftWristPathLengthPx: Optional[float] = None
    rightWristPathLengthPx: Optional[float] = None
    gripPathLengthPx: Optional[float] = None
    clubHeadPathLengthPx: Optional[float] = None
    maxGripSpeedPxPerSec: Optional[float] = None
    maxClubHeadSpeedPxPerSec: Optional[float] = None
    estimatedImpactMs: Optional[int] = None
    clubDetectionMethod: str = 'hough_line_near_hands'
    notes: Optional[str] = None


class SwingPhaseTimestamps(BaseModel):
    address: Optional[int] = None
    takeaway: Optional[int] = None
    topOfBackswing: Optional[int] = None
    impact: Optional[int] = None
    finish: Optional[int] = None


class SwingTrimWindow(BaseModel):
    startMs: int = 0
    endMs: int = 0
    startFrameIndex: int = 0
    endFrameIndex: int = 0
    method: Literal['pose_motion', 'pose_motion_short_clip', 'llm_vision', 'fallback_full_video'] = 'fallback_full_video'
    confidence: float = 0
    notes: Optional[str] = None


class SwingBiomechanicsMetrics(BaseModel):
    # Measured from video landmarks when pose quality allows it.
    tempoRatio: Optional[float] = None
    backswingTimeMs: Optional[int] = None
    downswingTimeMs: Optional[int] = None
    spineAngleAtAddress: Optional[float] = None
    shoulderTurnAtTop: Optional[float] = None
    hipTurnAtTop: Optional[float] = None
    headMovementPx: Optional[float] = None
    swayPx: Optional[float] = None
    confidence: Optional[float] = None


class BallFlightEstimates(BaseModel):
    # Estimated from pose/video only. Future launch-monitor calibration is required
    # before these can be interpreted as ground truth.
    launchAngleRange: Optional[Tuple[float, float]] = None
    launchDirection: Optional[Literal['left', 'straight', 'right']] = None
    shotShape: Optional[Literal['draw', 'fade', 'straight', 'unknown']] = None
    carryRangeYards: Optional[Tuple[float, float]] = None
    spinTendency: Optional[Literal['low', 'medium', 'high', 'unknown']] = None
    confidence: Optional[float] = None


class SwingPrivacyFlags(BaseModel):
    rawVideoUploaded: bool = False
    userConsentedToUpload: bool = False
    videoFramesSentToLlm: bool = False


class SwingAnalysisPayload(BaseModel):
    swingId: str
    source: AnalysisSource
    videoMetadata: SwingVideoMetadata = Field(default_factory=SwingVideoMetadata)
    swingWindow: Optional[SwingTrimWindow] = None
    phases: SwingPhaseTimestamps = Field(default_factory=SwingPhaseTimestamps)
    poseFrames: List[FramePoseData] = Field(default_factory=list)
    trackingFrames: List[FrameTrackingData] = Field(default_factory=list)
    trackingSummary: SwingTrackingSummary = Field(default_factory=SwingTrackingSummary)
    biomechanics: SwingBiomechanicsMetrics = Field(default_factory=SwingBiomechanicsMetrics)
    ballFlightEstimates: Optional[BallFlightEstimates] = None
    privacy: SwingPrivacyFlags = Field(default_factory=SwingPrivacyFlags)


class StoredSwing(BaseModel):
    swingId: str
    status: Literal['received', 'processed', 'failed'] = 'received'
    source: AnalysisSource
    videoMetadata: SwingVideoMetadata
    privacy: SwingPrivacyFlags
    videoUrl: Optional[str] = None


class StoredAnalysisResult(BaseModel):
    swingId: str
    phases: Dict
    metricsJson: Dict
    poseJson: List[Dict]
    trackingJson: List[Dict] = Field(default_factory=list)
    trackingSummaryJson: Dict = Field(default_factory=dict)
    estimatesJson: Optional[Dict] = None
