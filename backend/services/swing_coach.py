import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import Settings, settings


SWING_COACH_PROMPT = (
    'You are a careful golf swing coach using measured app evidence. '
    'Identify the highest-leverage pain points visible in the swing data. '
    'Do not invent measurements or claim certainty beyond the evidence. '
    'Every pain point must point to a concrete video moment using timestampMs, '
    'a visible cue the player can look for in the video overlay, and one actionable fix.'
)

PHASE_ORDER = (
    'address',
    'takeaway',
    'topOfBackswing',
    'downswing',
    'impact',
    'finish',
    'ballFlight',
    'overall',
)


def _extract_response_text(response_body: Dict[str, object]) -> str:
    output_text = response_body.get('output_text')
    if isinstance(output_text, str):
        return output_text

    fragments: List[str] = []
    output = response_body.get('output')
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get('content')
            if not isinstance(content, list):
                continue
            for fragment in content:
                if isinstance(fragment, dict) and fragment.get('type') in {'output_text', 'text'}:
                    text = fragment.get('text')
                    if isinstance(text, str):
                        fragments.append(text)
    return '\n'.join(fragments)


def _safe_int(value: object) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _phase_markers(phases: Dict[str, object], swing_window: Dict[str, object]) -> Dict[str, int]:
    markers = {
        key: timestamp
        for key in ('address', 'takeaway', 'topOfBackswing', 'impact', 'finish')
        if (timestamp := _safe_int(phases.get(key))) is not None
    }

    start_ms = _safe_int(swing_window.get('detectedStartMs') or swing_window.get('startMs'))
    end_ms = _safe_int(swing_window.get('detectedEndMs') or swing_window.get('endMs'))
    playback_end_ms = _safe_int(swing_window.get('endMs'))
    if start_ms is not None:
        markers.setdefault('address', start_ms)
    if end_ms is not None:
        markers.setdefault('finish', end_ms)
    if playback_end_ms is not None:
        markers.setdefault('ballFlight', playback_end_ms)

    if 'topOfBackswing' in markers and 'impact' in markers:
        markers.setdefault('downswing', (markers['topOfBackswing'] + markers['impact']) // 2)

    if markers:
        markers.setdefault('overall', min(markers.values()))
    return markers


def _nearest_phase_timestamp(phase: str, phase_markers: Dict[str, int]) -> int:
    if phase in phase_markers:
        return phase_markers[phase]
    if phase == 'ballFlight' and 'impact' in phase_markers:
        return phase_markers['impact']
    return phase_markers.get('overall', 0)


def _clamp_timestamp(timestamp_ms: int, swing_window: Dict[str, object]) -> int:
    start_ms = _safe_int(swing_window.get('startMs')) or 0
    end_ms = _safe_int(swing_window.get('endMs')) or max(timestamp_ms, start_ms)
    return min(max(timestamp_ms, start_ms), max(end_ms, start_ms))


def _coaching_status(
    status: str,
    model: str,
    summary: str,
    note: str,
    confidence: float = 0,
) -> Dict[str, object]:
    return {
        'status': status,
        'model': model,
        'generatedAt': datetime.utcnow().isoformat() + 'Z',
        'summary': summary,
        'painPoints': [],
        'confidence': confidence,
        'notes': note,
    }


def build_swing_coach_evidence(analysis_payload: Dict[str, object]) -> Dict[str, object]:
    swing_window = analysis_payload.get('swingWindow') if isinstance(analysis_payload.get('swingWindow'), dict) else {}
    phases = analysis_payload.get('phases') if isinstance(analysis_payload.get('phases'), dict) else {}
    tracking_summary = (
        analysis_payload.get('trackingSummary') if isinstance(analysis_payload.get('trackingSummary'), dict) else {}
    )
    ball_flight_summary = (
        analysis_payload.get('ballFlightSummary') if isinstance(analysis_payload.get('ballFlightSummary'), dict) else {}
    )
    biomechanics = analysis_payload.get('biomechanics') if isinstance(analysis_payload.get('biomechanics'), dict) else {}
    ball_flight_estimates = (
        analysis_payload.get('ballFlightEstimates')
        if isinstance(analysis_payload.get('ballFlightEstimates'), dict)
        else {}
    )

    return {
        'videoMetadata': analysis_payload.get('videoMetadata') or {},
        'swingWindow': swing_window,
        'phaseMarkersMs': _phase_markers(phases, swing_window),
        'trackingSummary': {
            'framesTracked': tracking_summary.get('framesTracked'),
            'bodyFrameCount': tracking_summary.get('bodyFrameCount'),
            'wristFrameCount': tracking_summary.get('wristFrameCount'),
            'handFrameCount': tracking_summary.get('handFrameCount'),
            'headFrameCount': tracking_summary.get('headFrameCount'),
            'clubFrameCount': tracking_summary.get('clubFrameCount'),
            'averageClubConfidence': tracking_summary.get('averageClubConfidence'),
            'estimatedImpactMs': tracking_summary.get('estimatedImpactMs'),
            'gripPathLengthPx': tracking_summary.get('gripPathLengthPx'),
            'clubHeadPathLengthPx': tracking_summary.get('clubHeadPathLengthPx'),
            'maxClubHeadSpeedPxPerSec': tracking_summary.get('maxClubHeadSpeedPxPerSec'),
            'golfMetrics': tracking_summary.get('golfMetrics') or {},
            'quality': tracking_summary.get('quality') or {},
        },
        'ballFlightSummary': ball_flight_summary,
        'biomechanics': biomechanics,
        'ballFlightEstimates': ball_flight_estimates,
    }


def _coaching_json_schema(max_points: int) -> Dict[str, object]:
    return {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'summary': {
                'type': 'string',
                'description': 'One concise paragraph summarizing the swing pattern and evidence quality.',
            },
            'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
            'notes': {'type': 'string'},
            'painPoints': {
                'type': 'array',
                'minItems': 0,
                'maxItems': max_points,
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'id': {'type': 'string'},
                        'category': {
                            'type': 'string',
                            'enum': [
                                'setup',
                                'backswing',
                                'downswing',
                                'impact',
                                'follow_through',
                                'ball_flight',
                                'tracking_quality',
                            ],
                        },
                        'severity': {'type': 'string', 'enum': ['high', 'medium', 'low']},
                        'phase': {'type': 'string', 'enum': list(PHASE_ORDER)},
                        'title': {'type': 'string'},
                        'evidence': {'type': 'string'},
                        'videoCue': {'type': 'string'},
                        'timestampMs': {'type': 'integer', 'minimum': 0},
                        'endTimestampMs': {'type': 'integer', 'minimum': 0},
                        'recommendation': {'type': 'string'},
                        'drill': {'type': 'string'},
                        'relatedMetrics': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'maxItems': 6,
                        },
                        'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    },
                    'required': [
                        'id',
                        'category',
                        'severity',
                        'phase',
                        'title',
                        'evidence',
                        'videoCue',
                        'timestampMs',
                        'endTimestampMs',
                        'recommendation',
                        'drill',
                        'relatedMetrics',
                        'confidence',
                    ],
                },
            },
        },
        'required': ['summary', 'confidence', 'notes', 'painPoints'],
    }


def _normalize_coaching_response(
    parsed: Dict[str, object],
    evidence: Dict[str, object],
    active_settings: Settings,
) -> Dict[str, object]:
    swing_window = evidence.get('swingWindow') if isinstance(evidence.get('swingWindow'), dict) else {}
    phase_markers = evidence.get('phaseMarkersMs') if isinstance(evidence.get('phaseMarkersMs'), dict) else {}
    normalized_points: List[Dict[str, object]] = []

    pain_points = parsed.get('painPoints')
    if isinstance(pain_points, list):
        for index, pain_point in enumerate(pain_points[:active_settings.llm_swing_coach_max_points]):
            if not isinstance(pain_point, dict):
                continue

            phase = str(pain_point.get('phase') or 'overall')
            timestamp_ms = _safe_int(pain_point.get('timestampMs'))
            if timestamp_ms is None:
                timestamp_ms = _nearest_phase_timestamp(phase, phase_markers)
            timestamp_ms = _clamp_timestamp(timestamp_ms, swing_window)

            end_timestamp_ms = _safe_int(pain_point.get('endTimestampMs'))
            if end_timestamp_ms is None or end_timestamp_ms < timestamp_ms:
                end_timestamp_ms = timestamp_ms
            end_timestamp_ms = _clamp_timestamp(end_timestamp_ms, swing_window)

            related_metrics = pain_point.get('relatedMetrics')
            normalized_points.append({
                'id': str(pain_point.get('id') or f'pain-point-{index + 1}'),
                'category': pain_point.get('category') or 'tracking_quality',
                'severity': pain_point.get('severity') or 'medium',
                'phase': phase if phase in PHASE_ORDER else 'overall',
                'title': str(pain_point.get('title') or 'Review this swing moment.'),
                'evidence': str(pain_point.get('evidence') or 'Evidence was limited.'),
                'videoCue': str(pain_point.get('videoCue') or 'Compare this moment with the overlay.'),
                'timestampMs': timestamp_ms,
                'endTimestampMs': end_timestamp_ms,
                'recommendation': str(pain_point.get('recommendation') or 'Retake with clearer framing.'),
                'drill': str(pain_point.get('drill') or 'Record one slow rehearsal and compare the same phase.'),
                'relatedMetrics': related_metrics if isinstance(related_metrics, list) else [],
                'confidence': max(0, min(float(pain_point.get('confidence') or 0), 1)),
            })

    return {
        'status': 'generated',
        'model': active_settings.llm_swing_coach_model,
        'generatedAt': datetime.utcnow().isoformat() + 'Z',
        'summary': str(parsed.get('summary') or 'Swing coaching generated from measured tracking evidence.'),
        'painPoints': normalized_points,
        'confidence': max(0, min(float(parsed.get('confidence') or 0), 1)),
        'notes': str(parsed.get('notes') or 'Generated from summarized pose, club, and ball-flight evidence.'),
    }


def generate_swing_coaching(
    analysis_payload: Dict[str, object],
    active_settings: Settings = settings,
) -> Tuple[Dict[str, object], bool]:
    if not active_settings.enable_llm_swing_coaching:
        return _coaching_status(
            'disabled',
            active_settings.llm_swing_coach_model,
            'LLM swing coaching is disabled.',
            'Set ENABLE_LLM_SWING_COACHING=true and provide OPENAI_API_KEY to generate video-linked coaching.',
        ), False

    if not active_settings.openai_api_key:
        return _coaching_status(
            'missing_api_key',
            active_settings.llm_swing_coach_model,
            'LLM swing coaching could not run because OPENAI_API_KEY is missing.',
            'The backend keeps the analysis payload usable without LLM coaching.',
        ), False

    evidence = build_swing_coach_evidence(analysis_payload)
    content = [{
        'type': 'input_text',
        'text': (
            f'{SWING_COACH_PROMPT}\n'
            f'Return at most {active_settings.llm_swing_coach_max_points} pain points. '
            'Use the phaseMarkersMs timestamps for videoCue timing. '
            'If evidence quality is weak, make tracking_quality the top pain point instead of inventing mechanics.\n'
            'JSON evidence:\n'
            + json.dumps(evidence, separators=(',', ':'), sort_keys=True)
        ),
    }]

    request_body = json.dumps({
        'model': active_settings.llm_swing_coach_model,
        'input': [{'role': 'user', 'content': content}],
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'swing_coaching_analysis',
                'strict': True,
                'schema': _coaching_json_schema(active_settings.llm_swing_coach_max_points),
            },
        },
    }).encode('utf-8')

    request = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=request_body,
        headers={
            'Authorization': f'Bearer {active_settings.openai_api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response_body = json.loads(response.read().decode('utf-8'))
        parsed = json.loads(_extract_response_text(response_body))
        if not isinstance(parsed, dict):
            raise ValueError('Structured coaching response was not an object.')
        return _normalize_coaching_response(parsed, evidence, active_settings), True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return _coaching_status(
            'failed',
            active_settings.llm_swing_coach_model,
            'LLM swing coaching failed, but the measured swing analysis is still available.',
            str(exc)[:220],
        ), True
