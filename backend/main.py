from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from config import settings
from safety import assert_video_upload_allowed, maybe_delete_raw_video, should_store_raw_video
from schemas import SwingAnalysisPayload, dump_model
from services.analysis import analyze_swing
from storage import repository

app = FastAPI(title='Golf Swing Analyzer API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'] if settings.allow_external_connections else ['http://127.0.0.1', 'http://localhost'],
    allow_methods=['*'],
    allow_headers=['*'],
)

UPLOAD_DIR = Path(__file__).resolve().parent / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


@app.on_event('startup')
async def print_startup_safety_summary():
    summary = settings.startup_summary()
    print(
        'Safety summary: '
        f'environment={summary["environment"]}, '
        f'video_upload={summary["video_upload"]}, '
        f'raw_video_storage={summary["raw_video_storage"]}, '
        f'external_connections={summary["external_connections"]}'
    )


@app.get('/health')
def health():
    return {'status': 'ok'}


async def _process_uploaded_swing(video: UploadFile, user_consented_to_upload: bool = False):
    try:
        assert_video_upload_allowed(user_consented_to_upload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not video.content_type or not video.content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail='Upload must be a video file.')

    file_id = uuid4().hex
    video_path = UPLOAD_DIR / f'{file_id}.mp4'
    bytes_written = 0

    try:
        with video_path.open('wb') as out_file:
            while chunk := await video.read(CHUNK_SIZE):
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_BYTES:
                    video_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail='Video file is too large. Limit uploads to 50 MB.')
                out_file.write(chunk)

        try:
            analysis = await run_in_threadpool(analyze_swing, str(video_path))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f'Swing analysis failed: {exc}') from exc

        payload = SwingAnalysisPayload(**analysis)
        payload.privacy.rawVideoUploaded = True
        payload.privacy.userConsentedToUpload = user_consented_to_upload
        video_url = str(video_path) if should_store_raw_video() else None
        repository.save_payload(payload, video_url=video_url)
        return JSONResponse(content=dump_model(payload, exclude_none=True))
    finally:
        maybe_delete_raw_video(video_path)


@app.post('/swings/analysis')
async def submit_swing_analysis(payload: SwingAnalysisPayload):
    if payload.privacy.rawVideoUploaded:
        raise HTTPException(status_code=400, detail='Use /swings/upload when raw video is uploaded.')

    stored_payload = repository.save_payload(payload, video_url=None)
    return JSONResponse(content=dump_model(stored_payload, exclude_none=True))


@app.post('/swings/upload')
async def upload_swing(
    video: UploadFile = File(...),
    user_consented_to_upload: bool = Form(False),
):
    return await _process_uploaded_swing(video, user_consented_to_upload=user_consented_to_upload)


@app.post('/upload-swing')
async def upload_swing_legacy(
    video: UploadFile = File(...),
    user_consented_to_upload: bool = Form(False),
):
    return await _process_uploaded_swing(video, user_consented_to_upload=user_consented_to_upload)
