import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import Settings, settings


SWING_COACH_PROMPT = (
    'You are a careful golf swing coach using measured app evidence. '
    'The deterministic swingDiagnosis object is authoritative. '
    'Rewrite its highest-priority issues into clear player-facing coaching, but do not invent new faults or change priority IDs. '
    'Do not invent measurements or claim certainty beyond the evidence. '
    'Treat trackingSummary.golfMetrics.clubFaceEstimate as a low-confidence video proxy unless its confidence is high. '
    'Use impactAnalysis for strike-point and contact-quality wording only when impactAnalysis.status is generated; never claim strike quality from dry swings. '
    'Use swingDiagnosis.expectedActualComparison as the training loop: when expected delivery and actual ball flight disagree, explain the uncertainty instead of forcing a face/path fix. '
    'Use ballFlightSummary.actualShotShape only when ballFlightSummary.status is tracked and confidence passes the app validation gate; otherwise treat the swing as a dry/no-ball swing. '
    'When swingDiagnosis.analysisMode is dry_swing, label predicted ball flight as predicted rather than actual. '
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

PHASE_TIMESTAMP_SNAP_TOLERANCE_MS = 450
PHASE_DEFAULT_WINDOWS_MS = {
    'address': 450,
    'takeaway': 500,
    'topOfBackswing': 450,
    'downswing': 650,
    'impact': 450,
    'finish': 650,
    'ballFlight': 900,
    'overall': 900,
}


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


def _safe_float(value: object) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
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


def _phase_accurate_timestamp(
    phase: str,
    requested_timestamp_ms: Optional[int],
    phase_markers: Dict[str, int],
    swing_window: Dict[str, object],
) -> int:
    phase_timestamp = _nearest_phase_timestamp(phase, phase_markers)
    if requested_timestamp_ms is None:
        return phase_timestamp

    if phase in phase_markers and phase not in {'overall', 'ballFlight'}:
        if abs(requested_timestamp_ms - phase_timestamp) > PHASE_TIMESTAMP_SNAP_TOLERANCE_MS:
            return phase_timestamp
        return phase_timestamp if phase in {'address', 'topOfBackswing', 'impact', 'finish'} else requested_timestamp_ms

    return _clamp_timestamp(requested_timestamp_ms, swing_window)


def _phase_default_end_timestamp(phase: str, timestamp_ms: int, phase_markers: Dict[str, int]) -> int:
    if phase == 'downswing' and (impact_ms := phase_markers.get('impact')) is not None:
        return max(timestamp_ms, impact_ms)
    if phase == 'topOfBackswing' and (impact_ms := phase_markers.get('impact')) is not None:
        return min(max(timestamp_ms + 250, timestamp_ms), impact_ms)
    if phase == 'address' and (takeaway_ms := phase_markers.get('takeaway')) is not None:
        return max(timestamp_ms, takeaway_ms)
    return timestamp_ms + PHASE_DEFAULT_WINDOWS_MS.get(phase, PHASE_DEFAULT_WINDOWS_MS['overall'])


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
    launch_monitor = (
        analysis_payload.get('launchMonitor') if isinstance(analysis_payload.get('launchMonitor'), dict) else {}
    )
    impact_analysis = (
        analysis_payload.get('impactAnalysis') if isinstance(analysis_payload.get('impactAnalysis'), dict) else {}
    )
    dry_swing = (
        analysis_payload.get('drySwing') if isinstance(analysis_payload.get('drySwing'), dict) else {}
    )
    swing_diagnosis = (
        analysis_payload.get('swingDiagnosis') if isinstance(analysis_payload.get('swingDiagnosis'), dict) else {}
    )
    ball_flight_confidence = _safe_float(ball_flight_summary.get('confidence')) or 0
    has_valid_ball_flight = (
        ball_flight_summary.get('status') == 'tracked'
        and ball_flight_confidence >= 0.45
    )

    return {
        'videoMetadata': analysis_payload.get('videoMetadata') or {},
        'analysisMode': 'ball_strike' if has_valid_ball_flight else 'dry_swing_or_no_validated_ball',
        'ballFlightAvailable': has_valid_ball_flight,
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
        'launchMonitor': launch_monitor,
        'impactAnalysis': impact_analysis,
        'drySwing': dry_swing,
        'swingDiagnosis': swing_diagnosis,
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


def _schema_category(category: object) -> str:
    category_text = str(category or 'tracking_quality')
    if category_text in {'head', 'wrist', 'tempo'}:
        return 'downswing'
    if category_text in {'ball_flight', 'impact', 'setup', 'backswing', 'downswing', 'follow_through', 'tracking_quality'}:
        return category_text
    return 'tracking_quality'


def _diagnosis_priorities(evidence: Dict[str, object]) -> List[Dict[str, object]]:
    diagnosis = evidence.get('swingDiagnosis') if isinstance(evidence.get('swingDiagnosis'), dict) else {}
    priorities = diagnosis.get('priorities') if isinstance(diagnosis.get('priorities'), list) else []
    return [priority for priority in priorities if isinstance(priority, dict) and priority.get('id')]


def _fallback_point_from_priority(
    priority: Dict[str, object],
    swing_window: Dict[str, object],
    phase_markers: Dict[str, int],
) -> Dict[str, object]:
    phase = str(priority.get('phase') or 'overall')
    timestamp_ms = _phase_accurate_timestamp(phase, _safe_int(priority.get('timestampMs')), phase_markers, swing_window)
    timestamp_ms = _clamp_timestamp(timestamp_ms, swing_window)
    end_timestamp_ms = _safe_int(priority.get('endTimestampMs'))
    if end_timestamp_ms is None or end_timestamp_ms < timestamp_ms:
        end_timestamp_ms = _phase_default_end_timestamp(phase, timestamp_ms, phase_markers)
    end_timestamp_ms = _clamp_timestamp(end_timestamp_ms, swing_window)

    related_metrics = priority.get('relatedMetrics')
    return {
        'id': str(priority.get('id')),
        'category': _schema_category(priority.get('category')),
        'severity': priority.get('severity') if priority.get('severity') in {'high', 'medium', 'low'} else 'medium',
        'phase': phase if phase in PHASE_ORDER else 'overall',
        'title': str(priority.get('title') or 'Review this swing priority.'),
        'evidence': str(priority.get('evidence') or 'Deterministic diagnosis found this priority.'),
        'videoCue': str(priority.get('videoCue') or 'Compare this moment with the overlay.'),
        'timestampMs': timestamp_ms,
        'endTimestampMs': end_timestamp_ms,
        'recommendation': str(priority.get('recommendation') or 'Retake with clearer framing.'),
        'drill': str(priority.get('drill') or 'Record one slow rehearsal and compare the same phase.'),
        'relatedMetrics': related_metrics if isinstance(related_metrics, list) else [],
        'confidence': max(0, min(float(priority.get('confidence') or 0), 1)),
    }


def _normalize_coaching_response(
    parsed: Dict[str, object],
    evidence: Dict[str, object],
    active_settings: Settings,
) -> Dict[str, object]:
    swing_window = evidence.get('swingWindow') if isinstance(evidence.get('swingWindow'), dict) else {}
    phase_markers = evidence.get('phaseMarkersMs') if isinstance(evidence.get('phaseMarkersMs'), dict) else {}
    diagnosis_priorities = _diagnosis_priorities(evidence)
    priority_by_id = {str(priority.get('id')): priority for priority in diagnosis_priorities}
    normalized_points: List[Dict[str, object]] = []

    pain_points = parsed.get('painPoints')
    if isinstance(pain_points, list):
        for index, pain_point in enumerate(pain_points[:active_settings.llm_swing_coach_max_points]):
            if not isinstance(pain_point, dict):
                continue

            priority = priority_by_id.get(str(pain_point.get('id'))) if priority_by_id else None
            if priority_by_id and priority is None:
                continue

            phase = str((priority or {}).get('phase') or pain_point.get('phase') or 'overall')
            timestamp_ms = _phase_accurate_timestamp(
                phase,
                _safe_int((priority or {}).get('timestampMs') or pain_point.get('timestampMs')),
                phase_markers,
                swing_window,
            )
            timestamp_ms = _clamp_timestamp(timestamp_ms, swing_window)

            end_timestamp_ms = _safe_int((priority or {}).get('endTimestampMs') or pain_point.get('endTimestampMs'))
            phase_end_timestamp_ms = _phase_default_end_timestamp(phase, timestamp_ms, phase_markers)
            if (
                end_timestamp_ms is None
                or end_timestamp_ms < timestamp_ms
                or end_timestamp_ms - timestamp_ms > 1600
                or (
                    phase in phase_markers
                    and phase not in {'overall', 'ballFlight'}
                    and abs((end_timestamp_ms or phase_end_timestamp_ms) - phase_end_timestamp_ms) > 900
                )
            ):
                end_timestamp_ms = phase_end_timestamp_ms
            end_timestamp_ms = _clamp_timestamp(end_timestamp_ms, swing_window)

            related_metrics = (priority or {}).get('relatedMetrics') or pain_point.get('relatedMetrics')
            normalized_points.append({
                'id': str((priority or {}).get('id') or pain_point.get('id') or f'pain-point-{index + 1}'),
                'category': _schema_category((priority or {}).get('category') or pain_point.get('category')),
                'severity': (priority or {}).get('severity') or pain_point.get('severity') or 'medium',
                'phase': phase if phase in PHASE_ORDER else 'overall',
                'title': str(pain_point.get('title') or (priority or {}).get('title') or 'Review this swing moment.'),
                'evidence': str(pain_point.get('evidence') or (priority or {}).get('evidence') or 'Evidence was limited.'),
                'videoCue': str(pain_point.get('videoCue') or (priority or {}).get('videoCue') or 'Compare this moment with the overlay.'),
                'timestampMs': timestamp_ms,
                'endTimestampMs': end_timestamp_ms,
                'recommendation': str(pain_point.get('recommendation') or (priority or {}).get('recommendation') or 'Retake with clearer framing.'),
                'drill': str(pain_point.get('drill') or (priority or {}).get('drill') or 'Record one slow rehearsal and compare the same phase.'),
                'relatedMetrics': related_metrics if isinstance(related_metrics, list) else [],
                'confidence': max(0, min(float((priority or {}).get('confidence') or pain_point.get('confidence') or 0), 1)),
            })

    if priority_by_id and not normalized_points:
        normalized_points = [
            _fallback_point_from_priority(priority, swing_window, phase_markers)
            for priority in diagnosis_priorities[:active_settings.llm_swing_coach_max_points]
        ]

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
            'Use swingDiagnosis.priorities as the allowed issue list and preserve each priority id. '
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
