from typing import Dict, Optional

from schemas import StoredAnalysisResult, StoredSwing, SwingAnalysisPayload, dump_model


class SwingRepository:
    """In-memory storage boundary matching the intended database split."""

    def __init__(self) -> None:
        self.swings: Dict[str, StoredSwing] = {}
        self.analysis_results: Dict[str, StoredAnalysisResult] = {}

    def save_payload(self, payload: SwingAnalysisPayload, video_url: Optional[str] = None) -> SwingAnalysisPayload:
        self.swings[payload.swingId] = StoredSwing(
            swingId=payload.swingId,
            status='processed',
            source=payload.source,
            videoMetadata=payload.videoMetadata,
            privacy=payload.privacy,
            videoUrl=video_url,
        )
        self.analysis_results[payload.swingId] = StoredAnalysisResult(
            swingId=payload.swingId,
            phases=dump_model(payload.phases),
            metricsJson=dump_model(payload.biomechanics, exclude_none=True),
            poseJson=[dump_model(frame, exclude_none=True) for frame in payload.poseFrames],
            trackingJson=[dump_model(frame, exclude_none=True) for frame in payload.trackingFrames],
            trackingSummaryJson=dump_model(payload.trackingSummary, exclude_none=True),
            estimatesJson=dump_model(payload.ballFlightEstimates, exclude_none=True)
            if payload.ballFlightEstimates
            else None,
        )
        return payload


repository = SwingRepository()
