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
- Body geometry is tracked as posture lines and frame metrics: shoulders, hips, spine, forearms, and shoulder/hip separation.
- Wrist points are tracked from pose landmarks, and optional MediaPipe hand landmarks add palm/MCP points plus wrist-angle measurements. Without hand landmarks, wrist angles fall back to lower-confidence club/forearm proxies.
- Head and eye direction are tracked from pose facial landmarks by default. This is an eye-line/head-direction proxy, not calibrated gaze.
- The club shaft/head are detected with OpenCV line candidates near the grip, then temporally repaired and smoothed so brief motion blur does not make the overlay flicker.
- If `SEND_VIDEO_TO_LLM=true` and `OPENAI_API_KEY` is set, the backend sends a small set of sampled JPEG frames to the configured vision model to refine `startMs` and `endMs`.
- Raw video is not sent to the LLM by default. Keep `SEND_VIDEO_TO_LLM=false` for local-only trimming.
- Tune the optional model with `LLM_SWING_TRIM_MODEL` and cap sampled frames with `LLM_SWING_TRIM_MAX_FRAMES`.

The response includes `swingWindow`, `phases`, trimmed `poseFrames`, rich `trackingFrames`, `trackingSummary.golfMetrics`, `trackingSummary.quality`, and `privacy.videoFramesSentToLlm` so the mobile app can loop the overlay and 3D skeleton on the detected swing instead of the full recording.

`safety.build_llm_payload` always includes the summarized tracking metrics and includes full `trackingFrames` alongside `poseFrames` when `SEND_POSE_DATA_TO_LLM=true` and summarized-only mode is disabled.

## Endpoints

- `GET /health` - health check
- `POST /swings/analysis` - store mobile-produced analysis JSON without uploading video
- `POST /swings/upload` - fallback/debug path that uploads a video file as `video`
- `POST /upload-swing` - legacy alias for the upload path

## Persistence Shape

`schema.sql` documents the target database split:

- `swings` stores metadata, status, source, privacy flags, and a nullable video URL.
- `analysis_results` stores metrics JSON, pose JSON, tracking JSON, phase JSON, and estimated ball-flight JSON separately from raw video.

The current prototype uses `storage.py` as an in-memory repository with the same boundaries.
