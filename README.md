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
