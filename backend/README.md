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
- The ball is tracked after impact with bright/motion contour candidates. This produces `ballTrackingFrames`, `ballFlightSummary`, and rough `ballFlightEstimates`; it is useful evidence for later coaching LLMs but still needs launch-monitor calibration before being treated as ground truth.
- If `SEND_VIDEO_TO_LLM=true` and `OPENAI_API_KEY` is set, the backend sends a small set of sampled JPEG frames to the configured vision model to refine `startMs` and `endMs`.
- Raw video is not sent to the LLM by default. Keep `SEND_VIDEO_TO_LLM=false` for local-only trimming.
- Tune the optional model with `LLM_SWING_TRIM_MODEL` and cap sampled frames with `LLM_SWING_TRIM_MAX_FRAMES`.
- If `ENABLE_LLM_SWING_COACHING=true` and `OPENAI_API_KEY` is set, the backend sends summarized pose, club, and ball-flight evidence to `LLM_SWING_COACH_MODEL` and returns `swingCoaching.painPoints`. Each pain point includes a phase, timestamp, video cue, evidence, recommendation, and drill so the app can show it directly on the playback.
- Keep `SEND_POSE_DATA_TO_LLM=false` and `SEND_ONLY_SUMMARIZED_METRICS_TO_LLM=true` unless you deliberately want full pose/tracking points in future LLM workflows.

The response includes `swingWindow`, `phases`, trimmed `poseFrames`, rich `trackingFrames`, `trackingSummary.golfMetrics`, `trackingSummary.quality`, `ballTrackingFrames`, `ballFlightSummary`, `swingCoaching`, and `privacy.videoFramesSentToLlm` so the mobile app can loop the overlay on the useful swing-and-ball-flight section instead of the full recording.

`safety.build_llm_payload` always includes the summarized body/club and ball-flight metrics, and includes full `trackingFrames` plus `ballTrackingFrames` alongside `poseFrames` when `SEND_POSE_DATA_TO_LLM=true` and summarized-only mode is disabled.

## Endpoints

- `GET /health` - health check
- `POST /swings/analysis` - store mobile-produced analysis JSON without uploading video
- `POST /swings/upload` - fallback/debug path that uploads a video file as `video`
- `POST /upload-swing` - legacy alias for the upload path

## Persistence Shape

`schema.sql` documents the target database split:

- `swings` stores metadata, status, source, privacy flags, and a nullable video URL.
- `analysis_results` stores metrics JSON, pose JSON, tracking JSON, ball tracking JSON, coaching JSON, phase JSON, and estimated ball-flight JSON separately from raw video.

The current prototype uses `storage.py` as an in-memory repository with the same boundaries.
