# Safety and Privacy Configuration

The project uses the existing `mobile/.env` file as the local source of safety configuration. Existing values are preserved; new keys should be appended only when missing. `mobile/.env.example` lists every expected key with safe defaults.

## Safe Defaults

- `PROCESS_ON_DEVICE=true` keeps swing analysis mobile-first.
- `ALLOW_VIDEO_UPLOAD=false` blocks raw video uploads by default.
- `STORE_RAW_VIDEO=false` prevents persistent raw video storage.
- `REQUIRE_USER_VIDEO_UPLOAD_CONSENT=true` requires explicit consent before server fallback.
- `DELETE_RAW_VIDEO_AFTER_ANALYSIS=true` removes temporary video files after processing.
- `SAVE_POSE_DATA_ONLY=true` keeps structured pose/metrics separate from raw media.
- `LOG_SENSITIVE_DATA=false` avoids logging pose arrays, frame data, secrets, and raw video paths.
- `SEND_VIDEO_TO_LLM=false` blocks raw video from AI/LLM requests.
- `SEND_POSE_DATA_TO_LLM=false` blocks full pose arrays from AI/LLM requests.
- `SEND_ONLY_SUMMARIZED_METRICS_TO_LLM=true` allows only summarized metrics by default.
- `ENABLE_LLM_SWING_COACHING=false` prevents automatic coaching calls until you explicitly enable them.

## Development

Use:

```env
APP_ENV=development
DEBUG=false
ALLOW_VIDEO_UPLOAD=false
STORE_RAW_VIDEO=false
```

For local backend fallback testing, temporarily set:

```env
ALLOW_VIDEO_UPLOAD=true
REQUIRE_USER_VIDEO_UPLOAD_CONSENT=true
STORE_RAW_VIDEO=false
DELETE_RAW_VIDEO_AFTER_ANALYSIS=true
```

This allows upload for analysis but still deletes the temporary raw video after processing.

## Production

Production validation fails unless:

- `DEBUG=false`
- `ENABLE_PUBLIC_TUNNEL=false`
- `LOG_SENSITIVE_DATA=false`
- `OPENAI_API_KEY`, `DATABASE_URL`, `STORAGE_BUCKET`, and `JWT_SECRET` are set

Secrets are never printed in the startup summary.

## Backend Network Safety

When `ALLOW_EXTERNAL_CONNECTIONS=false`, CORS is limited to localhost origins. Set it to `true` only when the backend is intentionally reachable by devices on your network or by a deployed client.

`ENABLE_PUBLIC_TUNNEL=false` is required in production. Public tunnels are useful for short-lived development testing only.

## Video Handling

The server-side upload route still exists for fallback and debugging, but it is wrapped by safety checks:

- upload is blocked when `ALLOW_VIDEO_UPLOAD=false`
- upload requires consent when `REQUIRE_USER_VIDEO_UPLOAD_CONSENT=true`
- raw video is only retained when `STORE_RAW_VIDEO=true`
- temporary video files are deleted when `DELETE_RAW_VIDEO_AFTER_ANALYSIS=true` or storage is disabled

Structured pose and metric JSON can be submitted to `POST /swings/analysis` without uploading video.

## Logging and AI Use

Logging helpers redact keys such as API keys, tokens, secrets, passwords, and database URLs. Pose/frame data is excluded unless sensitive logging is explicitly enabled.

LLM payload helpers block raw video and exclude full pose arrays by default. The intended AI-safe payload contains summarized metadata, phases, biomechanics, tracking summaries, ball-flight summaries, and estimates only.

When `ENABLE_LLM_SWING_COACHING=true`, the backend sends summarized swing evidence to the configured coaching model and stores the structured coaching response as `swingCoaching`. The mobile app can display those pain points on the video timeline without sending raw video to the coaching LLM.
