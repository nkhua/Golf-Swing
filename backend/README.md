# Backend Service

This backend supports privacy-first swing analysis. It accepts structured pose/metric JSON from the mobile app when on-device analysis is available, and it still accepts raw video uploads for fallback or debugging.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The first server-side video analysis run will download the MediaPipe pose-landmarker model asset into `backend/models` if it is not already present. The enhanced hand landmark model is optional and disabled by default for local performance; set `ENABLE_DETAILED_HAND_TRACKING=true` to use it on key swing frames for more accurate wrist-angle measurements. If that optional download fails, analysis falls back to pose/club proxies instead of blocking the upload.

## Swing Window Detection

Server video analysis now detects the actual swing window before building metrics, tracking points, and 3D playback data:

- The default path uses MediaPipe pose motion from wrists, elbows, shoulders, and hips.
- `swingWindow.startMs` includes up to 2 seconds of pre-swing lead-in for user playback; `swingWindow.detectedStartMs` and `phases.address` preserve the actual detected swing start.
- `swingWindow.endMs` includes up to 3.5 seconds of post-finish playback for ball flight; `swingWindow.detectedEndMs` and `phases.finish` preserve the actual swing finish.
- Body geometry is tracked as posture lines and frame metrics: shoulders, hips, spine, forearms, and shoulder/hip separation.
- Wrist points are tracked from pose landmarks, and optional MediaPipe hand landmarks add palm/MCP points plus wrist-angle measurements. Without hand landmarks, wrist angles fall back to lower-confidence club/forearm proxies.
- Head and eye direction are tracked from pose facial landmarks by default. This is an eye-line/head-direction proxy, not calibrated gaze.
- The club shaft/head are detected with OpenCV line candidates near the grip, then temporally repaired and smoothed so brief motion blur does not make the overlay flicker.
- The mobile overlay renders the club-head path as an amber swing trail and renders a compact club-face marker at the current club head. This is shown separately from the red post-impact ball-flight trail so dry-swing path and actual ball flight do not get mixed together.
- The ball is tracked after impact with bright/motion contour candidates plus a ball-presence gate. This produces `ballTrackingFrames`, `ballFlightSummary`, and rough `ballFlightEstimates` only when a small, continuous, near-impact ball track is validated. Dry swings return `ballFlightSummary.status=no_ball_detected`, `launchDirection=null`, and `actualShotShape=unknown` instead of simulated shot outcomes.
- `trackingSummary.golfMetrics.clubFaceEstimate` combines ball start direction with screen-space club-head path around impact to produce confidence-scored face-to-target and face-to-path buckets. This is a video proxy for LLM reasoning, not a measured launch-monitor club-face angle.
- `launchMonitor` converts the measured club, ball, and face/path proxies into a TrackMan-style output shape: club speed, ball speed, smash factor, launch angle, launch direction, attack angle, club path, face angle, face-to-path, spin placeholders, carry placeholders, visible travel, data quality, definitions, and interpretation. Metrics that cannot be measured from the current single-camera pipeline remain null and are listed in `launchMonitor.dataQuality.missingMetrics`.
- `impactAnalysis` runs only when `ballFlightSummary.status=tracked` with validated confidence. It records club-head position at impact, ball position near impact, club-ball proximity, estimated low point, shaft lean, face/path proxy, and contact-quality classification (`likely_centered`, `thin`, `fat`, `heel`, `toe`, `off_center_unknown`, or `unknown`). No-ball and dry swings return `status=not_available_no_validated_ball` and do not record strike-quality claims.
- `drySwing` runs only when no validated ball flight exists. It scores biomechanics and delivery proxies, returns `biomechanicalFindings` with timestamps/fixes/drills, and provides `predictedBallFlight` as a clearly labeled hypothesis for start direction, curve, trajectory, and contact risk. It never writes to `actualShotShape`.
- `swingDiagnosis` is the deterministic coaching boundary for every swing. It consumes tracking, impact analysis, launch-monitor proxies, validated ball flight, and dry-swing findings, then emits authoritative `priorities` with IDs, timestamps, evidence, likely effects, recommendations, and drills. It also emits `expectedActualComparison`: expected start/curve from biomechanics and face/path proxies versus actual start/curve from validated ball flight. When those disagree, the training signal becomes `tracking_or_strike_uncertainty` so coaching checks strike/tracking before prescribing a face/path fix. The LLM is a wording layer on top of these priorities, not the source of swing faults.
- If `SEND_VIDEO_TO_LLM=true` and `OPENAI_API_KEY` is set, the backend sends a small set of sampled JPEG frames to the configured vision model to refine `startMs` and `endMs`.
- If `ENABLE_LLM_IMPACT_ANALYSIS=true`, `SEND_VIDEO_TO_LLM=true`, and `OPENAI_API_KEY` is set, the backend can send up to `LLM_IMPACT_ANALYSIS_MAX_FRAMES` impact-area JPEG crops to `LLM_IMPACT_ANALYSIS_MODEL` only for validated real-ball swings when deterministic strike evidence is weak. This can refine visible club-face angle and heel/toe/thin/fat/center strike labels without sending the whole video.
- Raw video is not sent to the LLM by default. Keep `SEND_VIDEO_TO_LLM=false` for local-only trimming.
- Tune the optional model with `LLM_SWING_TRIM_MODEL` and cap sampled frames with `LLM_SWING_TRIM_MAX_FRAMES`.
- If `ENABLE_LLM_SWING_COACHING=true` and `OPENAI_API_KEY` is set, the backend sends summarized pose, club, ball-flight evidence, and `swingDiagnosis.priorities` to `LLM_SWING_COACH_MODEL` and returns `swingCoaching.painPoints`. The model must preserve deterministic priority IDs; invented IDs are ignored and the backend falls back to deterministic wording. Returned timestamps are snapped back to measured phase markers when the model labels a phase such as impact, top, address, or finish, preventing feedback from landing on the wrong part of the video.
- Keep `SEND_POSE_DATA_TO_LLM=false` and `SEND_ONLY_SUMMARIZED_METRICS_TO_LLM=true` unless you deliberately want full pose/tracking points in future LLM workflows.

The response includes `swingWindow`, `phases`, trimmed `poseFrames`, rich `trackingFrames`, `trackingSummary.golfMetrics`, `trackingSummary.quality`, `ballTrackingFrames`, `ballFlightSummary`, `launchMonitor`, `impactAnalysis`, `drySwing`, `swingDiagnosis`, `swingCoaching`, `privacy.videoFramesSentToLlm`, and `privacy.impactFramesSentToLlm` so the mobile app can loop the overlay on the useful swing-and-ball-flight section instead of the full recording.

`safety.build_llm_payload` always includes the summarized body/club, club-face proxy, impact analysis, launch-monitor proxy, dry-swing analysis, deterministic swing diagnosis, and ball-flight metrics, and includes full `trackingFrames` plus `ballTrackingFrames` alongside `poseFrames` when `SEND_POSE_DATA_TO_LLM=true` and summarized-only mode is disabled.

## Endpoints

- `GET /health` - health check
- `POST /swings/analysis` - store mobile-produced analysis JSON without uploading video
- `POST /swings/upload` - fallback/debug path that uploads a video file as `video`
- `POST /upload-swing` - legacy alias for the upload path

## Persistence Shape

`schema.sql` documents the target database split:

- `swings` stores metadata, status, source, privacy flags, and a nullable video URL.
- `analysis_results` stores metrics JSON, pose JSON, tracking JSON, ball tracking JSON, launch-monitor JSON, dry-swing JSON, swing-diagnosis JSON, coaching JSON, phase JSON, and estimated ball-flight JSON separately from raw video.

The current prototype uses `storage.py` as an in-memory repository with the same boundaries.
