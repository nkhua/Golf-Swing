# Golf Swing Analyzer

A cross-platform mobile golf swing analyzer moving toward privacy-first, mobile-first pose processing. The app records a swing, attempts local/on-device analysis, and only uploads raw video when local analysis is unavailable and the user opts in to server fallback.

## Structure

- `mobile/` - Expo React Native mobile app prototype
- `backend/` - FastAPI backend with structured analysis and video fallback endpoints

## Architecture Direction

- Mobile capture records or, in a future media-picker path, imports a local swing video.
- `OnDeviceSwingAnalyzer` is the default analyzer boundary for native MediaPipe Pose Landmarker integration.
- `ServerSwingAnalyzer` is the fallback/debug path and requires explicit upload consent.
- Result display consumes the shared `SwingAnalysisPayload` shape regardless of analyzer source.
- Backend stores structured analysis separately from nullable raw video references.
- Safety flags in `mobile/.env` control upload, storage, logging, networking, and AI payload behavior. See `SECURITY.md`.

## Getting Started

### Automated Setup

1. From the repository root, run the script for your platform:
   - Windows PowerShell: `./setup.ps1`
   - macOS/Linux: `./setup.sh`
2. This creates the backend virtual environment, installs backend dependencies, and installs mobile dependencies.

### Mobile App

1. Open `mobile/`
2. Create `mobile/.env` from `mobile/.env.example` and set your backend URL:
   - `EXPO_PUBLIC_BACKEND_URL=http://YOUR_COMPUTER_LAN_IP:8000`
   - This keeps your local IP out of committed source code. Restart Expo after changing it.
3. Start the app: `npm start`
4. Run on a device or emulator with Expo Go

Expo Go cannot load custom native MediaPipe modules directly. The code includes TODO stubs for an Expo development build/native module path, iOS and Android MediaPipe Pose Landmarker bindings, and a possible React Native Vision Camera frame processor.

### Testing Real Skeletons With Expo Go

The Expo app can record real user video today, but real pose extraction happens through the local backend. The on-device analyzer is currently a mock/stub unless a future native MediaPipe module is added.

1. Copy `mobile/.env.expo-real-video.example` to `mobile/.env`, then replace `YOUR_COMPUTER_LAN_IP` with your computer's IPv4 address.
2. In `mobile/.env`, confirm:
   - `EXPO_PUBLIC_ANALYSIS_MODE=server`
   - `EXPO_PUBLIC_ENABLE_MOCK_ON_DEVICE_ANALYSIS=false`
   - `EXPO_PUBLIC_BACKEND_URL=http://YOUR_COMPUTER_LAN_IP:8000`
   - `ALLOW_VIDEO_UPLOAD=true`
   - `DELETE_RAW_VIDEO_AFTER_ANALYSIS=true`
3. Start the backend with `uvicorn main:app --reload --host 0.0.0.0 --port 8000`.
4. Confirm your phone can open `http://YOUR_COMPUTER_LAN_IP:8000/health`.
5. Start Expo with `npm run start:lan` from `mobile/`.
6. Record a swing with either the back or front camera, then tap `Upload and Process`. The flip control is disabled while recording so the camera session cannot switch mid-swing, and front-camera capture is kept unmirrored for left/right analysis consistency.
7. Keep recording through impact and the first few seconds of ball flight. The app allows a longer 16 second capture window so the backend has post-impact frames to track.
8. The results screen should show `Pose source: Real video processed by backend MediaPipe`, a detected `Swing Cut`, non-zero pose/tracking frames, a skeleton overlay with body, wrist, hand, eye-line, grip, club-head, shaft, and ball points on the captured swing segment, and a standalone 3D skeleton.

Backend uploads now trim analysis to the detected swing window. Playback includes up to 2 seconds before the detected swing start and up to 3.5 seconds after the detected swing finish for ball flight, while `swingWindow.detectedStartMs`, `swingWindow.detectedEndMs`, `phases.address`, and `phases.finish` preserve the actual swing timestamps. By default this is local pose-motion segmentation. Body, wrist, eye-line, grip, club-head, and shaft tracking are returned as structured `trackingFrames` plus compact `trackingSummary.golfMetrics` and `trackingSummary.quality`. The video overlay shows the club head swing path as an amber trail, the current shaft/head, and a small club-face marker at the head; post-impact ball flight stays a separate red trail. Post-impact ball candidates are returned as `ballTrackingFrames`, `ballFlightSummary`, and calibrated-later `ballFlightEstimates`; the ball-flight summary now has a strict presence gate and reports `status=no_ball_detected` instead of inventing launch direction or `actualShotShape` during dry swings. When no validated ball is found, `drySwing` predicts likely ball flight as `predictedBallFlight` and keeps that prediction separate from actual shot results. When a validated ball is found, `impactAnalysis` records strike-point evidence: club-head position at impact, ball position near impact, club-ball proximity, estimated low point, shaft lean, face/path proxy, and a contact-quality estimate. Dry/no-ball swings intentionally return `not_available_no_validated_ball` so the app does not claim centered, thin, fat, heel, or toe contact without a real ball. The new `swingDiagnosis` layer is the deterministic coaching boundary for every swing: vision/tracking, impact analysis, and launch-monitor proxies feed deterministic priorities, and `expectedActualComparison` compares predicted start/curve from delivery against actual start/curve from the ball tracer. If expected and actual disagree, the training signal becomes `tracking_or_strike_uncertainty` instead of blindly coaching the predicted fault. The LLM only rewrites those priority IDs into clearer wording. The backend also adds `trackingSummary.golfMetrics.clubFaceEstimate`, a confidence-scored video proxy that combines ball start direction with club-head path around impact so the deterministic diagnosis can reason about face-to-target and face-to-path without pretending it has launch-monitor truth. `launchMonitor` mirrors launch-monitor fields such as club speed, ball speed, smash factor, launch angle, attack angle, face/path, spin, carry, and total distance; fields that need radar, a validated ball, or calibration stay null with `dataQuality.missingMetrics` instead of being invented. Set `ENABLE_LLM_SWING_COACHING=true` with `OPENAI_API_KEY` to generate `swingCoaching.painPoints`, which the app snaps to measured phase timestamps and shows as video cues with actionable fixes. LLM payloads include the tracking, club-face proxy, impact analysis, launch-monitor proxy, dry-swing summary, deterministic swing diagnosis, and ball summaries by default and can include full tracking points with `SEND_POSE_DATA_TO_LLM=true` and `SEND_ONLY_SUMMARIZED_METRICS_TO_LLM=false`. To let a vision LLM refine the cut, set `SEND_VIDEO_TO_LLM=true`; to let a vision LLM inspect only impact crops when deterministic strike evidence is weak, also set `ENABLE_LLM_IMPACT_ANALYSIS=true`. The backend sends sampled JPEG frames/crops, not the whole video file, and reports `privacy.videoFramesSentToLlm` plus `privacy.impactFramesSentToLlm`.

### Backend

1. Open `backend/`
2. Create or activate the virtual environment:
   - Windows: `python -m venv venv && venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv venv && source venv/bin/activate`
3. Install Python dependencies: `pip install -r requirements.txt`
4. Start the API: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`

## Next Steps

- Replace the mock on-device analyzer path with native MediaPipe Pose Landmarker.
- Add video import with a platform media picker.
- Calibrate pose-only metrics and ball-flight estimates against launch-monitor or other ground-truth data.
