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

The first server-side video analysis run will download the MediaPipe pose-landmarker model asset into `backend/models` if it is not already present.

## Endpoints

- `GET /health` - health check
- `POST /swings/analysis` - store mobile-produced analysis JSON without uploading video
- `POST /swings/upload` - fallback/debug path that uploads a video file as `video`
- `POST /upload-swing` - legacy alias for the upload path

## Persistence Shape

`schema.sql` documents the target database split:

- `swings` stores metadata, status, source, privacy flags, and a nullable video URL.
- `analysis_results` stores metrics JSON, pose JSON, phase JSON, and estimated ball-flight JSON separately from raw video.

The current prototype uses `storage.py` as an in-memory repository with the same boundaries.
