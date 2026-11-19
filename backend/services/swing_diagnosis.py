from typing import Dict, List, Optional


SEVERITY_RANK = {'high': 0, 'medium': 1, 'low': 2}
MAX_PRIORITIES = 6
DEFAULT_WINDOWS_MS = {
    'address': 450,
    'takeaway': 500,
    'topOfBackswing': 450,
    'downswing': 650,
    'impact': 450,
    'finish': 650,
    'ballFlight': 900,
    'overall': 900,
}


def _safe_float(value: object) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, minimum: float = 0, maximum: float = 1) -> float:
    return min(max(value, minimum), maximum)


def _phase_time(phases: Dict[str, object], phase: str, fallback: Optional[int] = None) -> int:
    timestamp = _safe_int(phases.get(phase))
    if timestamp is not None:
        return timestamp
    return fallback if fallback is not None else 0


def _metric(metrics: Dict[str, object], key: str) -> Optional[float]:
    return _safe_float(metrics.get(key))


def _window_end(phase: str, timestamp_ms: int) -> int:
    return timestamp_ms + DEFAULT_WINDOWS_MS.get(phase, DEFAULT_WINDOWS_MS['overall'])


def _priority(
    priorities: List[Dict[str, object]],
    *,
    priority_id: str,
    category: str,
    severity: str,
    phase: str,
    timestamp_ms: int,
    title: str,
    evidence: str,
    video_cue: str,
    likely_effect: str,
    recommendation: str,
    drill: str,
    related_metrics: List[str],
    confidence: float,
    source: str,
    end_timestamp_ms: Optional[int] = None,
) -> None:
    priorities.append({
        'id': priority_id,
        'source': source,
        'category': category,
        'severity': severity,
        'phase': phase,
        'timestampMs': timestamp_ms,
        'endTimestampMs': end_timestamp_ms if end_timestamp_ms is not None and end_timestamp_ms >= timestamp_ms else _window_end(phase, timestamp_ms),
        'title': title,
        'evidence': evidence,
        'videoCue': video_cue,
        'likelyEffect': likely_effect,
        'recommendation': recommendation,
        'drill': drill,
        'relatedMetrics': related_metrics,
        'confidence': round(_clamp(confidence), 3),
        'llmInstruction': 'The LLM may simplify wording, but should not change this deterministic diagnosis.',
    })


def _quality_priority(
    priorities: List[Dict[str, object]],
    tracking_summary: Dict[str, object],
    phases: Dict[str, object],
) -> None:
    quality = tracking_summary.get('quality') if isinstance(tracking_summary.get('quality'), dict) else {}
    confidence = _safe_float(quality.get('overallTrackingConfidence')) or 0
    needs_retake = bool(quality.get('needsRetake'))
    if confidence >= 0.55 and not needs_retake:
        return

    reasons = quality.get('retakeReasons') if isinstance(quality.get('retakeReasons'), list) else []
    evidence = ' '.join(str(reason) for reason in reasons) or f'Overall tracking confidence is {round(confidence, 2)}.'
    _priority(
        priorities,
        priority_id='tracking-quality',
        category='tracking_quality',
        severity='high' if needs_retake or confidence < 0.35 else 'medium',
        phase='overall',
        timestamp_ms=_phase_time(phases, 'address', _safe_int(tracking_summary.get('estimatedImpactMs')) or 0),
        title='Retake quality limits swing diagnosis',
        evidence=evidence,
        video_cue='Check whether the body, hands, club head, and impact area stay visible through the swing.',
        likely_effect='Noisy tracking can make club, wrist, face/path, and head feedback less reliable.',
        recommendation='Retake from a stable down-the-line angle with the full body, ball area, and entire club visible.',
        drill='Record one slow rehearsal first and confirm the overlay follows wrists and club head through impact.',
        related_metrics=['trackingSummary.quality.overallTrackingConfidence', 'trackingSummary.quality.retakeReasons'],
        confidence=max(0.35, 1 - confidence),
        source='tracking_quality_gate',
    )


def _copy_dry_swing_priorities(dry_swing: Dict[str, object]) -> List[Dict[str, object]]:
    findings = dry_swing.get('biomechanicalFindings') if isinstance(dry_swing.get('biomechanicalFindings'), list) else []
    priorities: List[Dict[str, object]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        timestamp_ms = _safe_int(finding.get('timestampMs')) or 0
        priorities.append({
            'id': str(finding.get('id') or f'dry-swing-{len(priorities) + 1}'),
            'source': 'deterministic_dry_swing',
            'category': str(finding.get('category') or 'tracking_quality'),
            'severity': str(finding.get('severity') or 'medium'),
            'phase': str(finding.get('phase') or 'overall'),
            'timestampMs': timestamp_ms,
            'endTimestampMs': _safe_int(finding.get('endTimestampMs')) or _window_end(str(finding.get('phase') or 'overall'), timestamp_ms),
            'title': str(finding.get('title') or 'Dry swing finding'),
            'evidence': str(finding.get('evidence') or 'Deterministic dry-swing evidence was limited.'),
            'videoCue': str(finding.get('videoCue') or 'Compare this moment with the overlay.'),
            'likelyEffect': str(finding.get('likelyEffect') or 'This movement pattern can affect strike and ball flight.'),
            'recommendation': str(finding.get('fix') or finding.get('recommendation') or 'Retake with clearer framing.'),
            'drill': str(finding.get('drill') or 'Record one slow rehearsal and compare the same phase.'),
            'relatedMetrics': finding.get('relatedMetrics') if isinstance(finding.get('relatedMetrics'), list) else [],
            'confidence': _clamp(_safe_float(finding.get('confidence')) or 0),
            'llmInstruction': 'The LLM may simplify wording, but should not change this deterministic diagnosis.',
        })
    return priorities


def _actual_ball_flight(ball_flight_summary: Dict[str, object], launch_metrics: Dict[str, object]) -> Dict[str, object]:
    has_valid_ball = ball_flight_summary.get('status') == 'tracked' and (_safe_float(ball_flight_summary.get('confidence')) or 0) >= 0.45
    if not has_valid_ball:
        return {
            'status': 'not_available',
            'source': 'none',
            'launchDirection': None,
            'actualShotShape': 'unknown',
            'confidence': 0,
        }

    return {
        'status': 'measured_from_validated_ball_track',
        'source': 'ballFlightSummary',
        'launchDirection': ball_flight_summary.get('launchDirection') or launch_metrics.get('launchDirection') or 'unknown',
        'actualShotShape': ball_flight_summary.get('actualShotShape') or launch_metrics.get('actualShotShape') or 'unknown',
        'trajectoryAngleDegrees': ball_flight_summary.get('trajectoryAngleDegrees'),
        'maxBallSpeedPxPerSec': ball_flight_summary.get('maxBallSpeedPxPerSec'),
        'confidence': round(_clamp(_safe_float(ball_flight_summary.get('confidence')) or 0), 3),
        'notes': 'This is actual observed ball-flight evidence from the validated ball tracker.',
    }


def _expected_start_from_face(face_to_target: object) -> str:
    if face_to_target == 'open':
        return 'right'
    if face_to_target == 'closed':
        return 'left'
    if face_to_target == 'square':
        return 'straight'
    return 'unknown'


def _expected_curve_from_face_path(face_to_path: object) -> str:
    if face_to_path == 'open':
        return 'fade'
    if face_to_path == 'closed':
        return 'draw'
    if face_to_path == 'square':
        return 'straight'
    return 'unknown'


def _agreement(expected: str, actual: object) -> str:
    if expected == 'unknown' or actual in {None, 'unknown'}:
        return 'unknown'
    return 'match' if expected == actual else 'mismatch'


def _expected_actual_comparison(
    tracking_summary: Dict[str, object],
    ball_flight_summary: Dict[str, object],
    launch_metrics: Dict[str, object],
    impact_analysis: Dict[str, object],
    actual_ball_flight: Dict[str, object],
) -> Dict[str, object]:
    if actual_ball_flight.get('status') != 'measured_from_validated_ball_track':
        return {
            'status': 'no_actual_ball',
            'trainingSignal': 'prediction_only',
            'expectedOutcome': {
                'startDirection': 'unknown',
                'curve': 'unknown',
                'source': 'not_available_without_ball',
            },
            'actualOutcome': {
                'startDirection': None,
                'curve': 'unknown',
                'source': 'not_available',
            },
            'agreement': {
                'startDirection': 'unknown',
                'curve': 'unknown',
                'overall': 'unknown',
            },
            'uncertaintyFlags': ['no_validated_ball_flight'],
            'coachingInstruction': 'Use dry-swing biomechanics as a prediction only; do not claim the ball-flight result.',
            'confidence': 0,
        }

    golf_metrics = tracking_summary.get('golfMetrics') if isinstance(tracking_summary.get('golfMetrics'), dict) else {}
    face_proxy = golf_metrics.get('clubFaceEstimate') if isinstance(golf_metrics.get('clubFaceEstimate'), dict) else {}
    impact_face_proxy = impact_analysis.get('facePathProxy') if isinstance(impact_analysis.get('facePathProxy'), dict) else {}
    contact_quality = impact_analysis.get('contactQuality') if isinstance(impact_analysis.get('contactQuality'), dict) else {}
    face_to_target = (
        impact_face_proxy.get('faceToTarget')
        or face_proxy.get('faceToTarget')
        or launch_metrics.get('faceToTarget')
        or 'unknown'
    )
    face_to_path = (
        impact_face_proxy.get('faceToPath')
        or face_proxy.get('faceToPath')
        or launch_metrics.get('faceToPath')
        or 'unknown'
    )
    club_path = (
        impact_face_proxy.get('clubPathProxy')
        or face_proxy.get('clubPathProxy')
        or launch_metrics.get('clubPathProxy')
        or 'unknown'
    )
    expected_start = _expected_start_from_face(face_to_target)
    expected_curve = _expected_curve_from_face_path(face_to_path)
    actual_start = actual_ball_flight.get('launchDirection') or ball_flight_summary.get('launchDirection')
    actual_curve = actual_ball_flight.get('actualShotShape') or ball_flight_summary.get('actualShotShape') or 'unknown'
    start_agreement = _agreement(expected_start, actual_start)
    curve_agreement = _agreement(expected_curve, actual_curve)
    known_agreements = [value for value in (start_agreement, curve_agreement) if value != 'unknown']
    if not known_agreements:
        overall = 'unknown'
    elif all(value == 'match' for value in known_agreements):
        overall = 'match'
    elif any(value == 'mismatch' for value in known_agreements):
        overall = 'mismatch'
    else:
        overall = 'partial'

    uncertainty_flags: List[str] = []
    if start_agreement == 'mismatch':
        uncertainty_flags.append('expected_start_direction_disagrees_with_actual_start')
    if curve_agreement == 'mismatch':
        uncertainty_flags.append('expected_curve_disagrees_with_actual_shape')

    contact_classification = str(contact_quality.get('classification') or 'unknown')
    if contact_classification in {'thin', 'fat', 'heel', 'toe', 'off_center_unknown', 'unknown'}:
        uncertainty_flags.append(f'impact_contact_{contact_classification}')
    if (_safe_float(contact_quality.get('confidence')) or 0) < 0.45:
        uncertainty_flags.append('strike_quality_low_confidence')

    face_confidence = (
        _safe_float(impact_face_proxy.get('confidence'))
        or _safe_float(face_proxy.get('confidence'))
        or _safe_float(launch_metrics.get('faceConfidence'))
        or 0
    )
    ball_confidence = _safe_float(ball_flight_summary.get('confidence')) or 0
    if face_confidence < 0.45:
        uncertainty_flags.append('face_path_proxy_low_confidence')
    if ball_confidence < 0.6:
        uncertainty_flags.append('ball_flight_low_confidence')

    if overall == 'match' and not uncertainty_flags:
        training_signal = 'delivery_prediction_confirmed'
        coaching_instruction = 'Use the expected face/path delivery as the primary training target.'
    elif overall == 'match':
        training_signal = 'prediction_matches_with_uncertainty'
        coaching_instruction = 'Delivery prediction matches the ball result, but resolve listed uncertainty before over-weighting it.'
    elif overall == 'mismatch':
        training_signal = 'tracking_or_strike_uncertainty'
        coaching_instruction = 'Do not over-coach face/path from this swing until strike quality and tracking confidence are checked.'
    else:
        training_signal = 'insufficient_comparison_evidence'
        coaching_instruction = 'Use the comparison as low-confidence context only.'

    confidence = _clamp(ball_confidence * 0.38 + face_confidence * 0.32 + (_safe_float(contact_quality.get('confidence')) or 0) * 0.18 + (0.12 if known_agreements else 0))
    return {
        'status': 'generated',
        'trainingSignal': training_signal,
        'expectedOutcome': {
            'startDirection': expected_start,
            'curve': expected_curve,
            'clubPathProxy': club_path,
            'faceToTarget': face_to_target,
            'faceToPath': face_to_path,
            'source': 'biomechanics_face_path_proxy',
        },
        'actualOutcome': {
            'startDirection': actual_start or 'unknown',
            'curve': actual_curve,
            'source': 'validated_ball_flight',
        },
        'agreement': {
            'startDirection': start_agreement,
            'curve': curve_agreement,
            'overall': overall,
        },
        'uncertaintyFlags': list(dict.fromkeys(uncertainty_flags)),
        'coachingInstruction': coaching_instruction,
        'confidence': round(confidence, 3),
        'notes': (
            'Expected outcome comes from deterministic club delivery proxies. Actual outcome comes from validated '
            'ball tracking. A mismatch means the app should check strike quality/tracking before making strong coaching claims.'
        ),
    }


def _comparison_priority(
    priorities: List[Dict[str, object]],
    comparison: Dict[str, object],
    phases: Dict[str, object],
    tracking_summary: Dict[str, object],
) -> None:
    if comparison.get('trainingSignal') != 'tracking_or_strike_uncertainty':
        return

    expected = comparison.get('expectedOutcome') if isinstance(comparison.get('expectedOutcome'), dict) else {}
    actual = comparison.get('actualOutcome') if isinstance(comparison.get('actualOutcome'), dict) else {}
    agreement = comparison.get('agreement') if isinstance(comparison.get('agreement'), dict) else {}
    flags = comparison.get('uncertaintyFlags') if isinstance(comparison.get('uncertaintyFlags'), list) else []
    impact_ms = _phase_time(phases, 'impact', _safe_int(tracking_summary.get('estimatedImpactMs')) or 0)
    _priority(
        priorities,
        priority_id='expected-actual-outcome-mismatch',
        category='tracking_quality',
        severity='high',
        phase='impact',
        timestamp_ms=impact_ms,
        title='Expected delivery and actual ball flight disagree',
        evidence=(
            f'Expected start {expected.get("startDirection", "unknown")} with {expected.get("curve", "unknown")} curve; '
            f'actual ball started {actual.get("startDirection", "unknown")} with {actual.get("curve", "unknown")} shape. '
            f'Agreement: start={agreement.get("startDirection", "unknown")}, curve={agreement.get("curve", "unknown")}.'
        ),
        video_cue='Review impact and the first ball-flight frames together: amber club path/face cue, strike point, then red ball tracer.',
        likely_effect='The swing fault may be strike quality, tracking quality, or face/path estimate error rather than the visible delivery alone.',
        recommendation='Treat this swing as uncertainty evidence: confirm centered contact and clean tracking before prescribing a face/path fix.',
        drill='Use impact spray or tape for five balls, then compare the same expected-vs-actual readout only on centered strikes.',
        related_metrics=[
            'swingDiagnosis.expectedActualComparison',
            'impactAnalysis.contactQuality',
            'trackingSummary.golfMetrics.clubFaceEstimate',
            'ballFlightSummary.actualShotShape',
        ],
        confidence=_safe_float(comparison.get('confidence')) or 0.45,
        source='expected_vs_actual_training_loop',
    )


def _body_and_delivery_priorities(
    biomechanics: Dict[str, object],
    tracking_summary: Dict[str, object],
    launch_metrics: Dict[str, object],
    ball_flight_summary: Dict[str, object],
    impact_analysis: Dict[str, object],
    expected_actual_comparison: Dict[str, object],
    phases: Dict[str, object],
) -> List[Dict[str, object]]:
    priorities: List[Dict[str, object]] = []
    golf_metrics = tracking_summary.get('golfMetrics') if isinstance(tracking_summary.get('golfMetrics'), dict) else {}
    impact_ms = _phase_time(phases, 'impact', _safe_int(tracking_summary.get('estimatedImpactMs')) or 0)
    top_ms = _phase_time(phases, 'topOfBackswing', impact_ms)
    downswing_ms = _phase_time(phases, 'downswing', (top_ms + impact_ms) // 2 if impact_ms else top_ms)
    ball_flight_ms = _phase_time(phases, 'ballFlight', _safe_int(ball_flight_summary.get('firstBallMs')) or impact_ms)

    _quality_priority(priorities, tracking_summary, phases)
    _comparison_priority(priorities, expected_actual_comparison, phases, tracking_summary)

    launch_direction = ball_flight_summary.get('launchDirection') or launch_metrics.get('launchDirection')
    actual_shape = ball_flight_summary.get('actualShotShape') or launch_metrics.get('actualShotShape')
    face_to_path = launch_metrics.get('faceToPath')
    face_to_target = launch_metrics.get('faceToTarget')
    face_to_path_degrees = _metric(launch_metrics, 'faceToPathDegrees')
    if (
        ball_flight_summary.get('status') == 'tracked'
        and (launch_direction not in {None, 'straight', 'unknown'} or actual_shape not in {None, 'straight', 'unknown'})
    ):
        _priority(
            priorities,
            priority_id='actual-start-curve-pattern',
            category='ball_flight',
            severity='medium' if actual_shape != 'straight' or launch_direction != 'straight' else 'low',
            phase='ballFlight',
            timestamp_ms=ball_flight_ms,
            title='Actual ball flight shows a start-and-curve pattern',
            evidence=f'Validated ball track starts {launch_direction or "unknown"} with actual {actual_shape or "unknown"} shape.',
            video_cue='Watch the red ball tracer immediately after impact and compare it with the amber club path.',
            likely_effect='Start direction is mostly face-to-target; curve is mostly face-to-path.',
            recommendation='Use the face/path and impact cues as the movement fix instead of guessing from shot shape alone.',
            drill='Hit half-speed shots with an intermediate start-line target and review whether the red tracer starts on that line.',
            related_metrics=['ballFlightSummary.launchDirection', 'ballFlightSummary.actualShotShape'],
            confidence=_safe_float(ball_flight_summary.get('confidence')) or 0.45,
            source='validated_ball_flight',
        )

    if face_to_path not in {None, 'square', 'unknown'} or (face_to_path_degrees is not None and abs(face_to_path_degrees) >= 4):
        _priority(
            priorities,
            priority_id='impact-face-path-control',
            category='impact',
            severity='high' if face_to_path_degrees is not None and abs(face_to_path_degrees) >= 8 else 'medium',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Face-to-path is driving curve risk',
            evidence=(
                f'Face-to-target is {face_to_target or "unknown"} and face-to-path is {face_to_path or "unknown"}'
                + (f' ({round(face_to_path_degrees, 1)} deg).' if face_to_path_degrees is not None else '.')
            ),
            video_cue='At impact, look at the club-face marker relative to the amber club path.',
            likely_effect='A face that is not matched to path will curve the ball even when contact is solid.',
            recommendation='Rehearse the face matching your intended start line at waist-high impact.',
            drill='Make split-hand waist-high swings, stopping at impact with the face square to a small intermediate target.',
            related_metrics=['launchMonitor.metrics.faceToPath', 'launchMonitor.metrics.faceToPathDegrees'],
            confidence=0.6,
            source='club_face_path_proxy',
        )

    club_path_proxy = launch_metrics.get('clubPathProxy')
    club_path_degrees = _metric(launch_metrics, 'clubPathDegrees')
    if club_path_proxy in {'in_to_out', 'out_to_in'} and (club_path_degrees is None or abs(club_path_degrees) >= 7):
        if club_path_proxy == 'out_to_in':
            title = 'Club path is cutting across the ball'
            effect = 'This can produce pull starts, fades, slices, and glancing contact.'
            recommendation = 'Keep the trail shoulder back longer while the club exits around the body.'
            drill = 'Place a soft headcover outside the target line behind the ball and make half swings missing it.'
        else:
            title = 'Club path is working strongly from the inside'
            effect = 'This can produce push starts or hooks when the face closes relative to path.'
            recommendation = 'Keep the chest turning so the club does not get trapped behind the hands.'
            drill = 'Make pump rehearsals where the hands return in front of the trail thigh before rotating through.'
        _priority(
            priorities,
            priority_id=f'club-path-{club_path_proxy}',
            category='downswing',
            severity='medium',
            phase='downswing',
            timestamp_ms=downswing_ms,
            title=title,
            evidence=f'Club path proxy is {club_path_proxy}' + (f' at {round(club_path_degrees, 1)} deg.' if club_path_degrees is not None else '.'),
            video_cue='Use the amber club-head trail to see how the club approaches the strike point.',
            likely_effect=effect,
            recommendation=recommendation,
            drill=drill,
            related_metrics=['launchMonitor.metrics.clubPathProxy', 'launchMonitor.metrics.clubPathDegrees'],
            confidence=0.56,
            source='club_path_proxy',
        )

    shaft_lean = _metric(golf_metrics, 'shaftLeanAtImpactDegrees')
    if shaft_lean is not None and shaft_lean <= -10:
        _priority(
            priorities,
            priority_id='impact-handle-trails',
            category='impact',
            severity='high',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Handle is trailing the club head at impact',
            evidence=f'Impact shaft lean proxy is {round(shaft_lean, 1)} deg.',
            video_cue='At impact, compare the grip point with the club head; the grip should not arrive behind the head.',
            likely_effect='Adds loft, moves low point backward, and raises thin or weak-contact risk.',
            recommendation='Rehearse a flatter lead wrist and a handle that reaches the strike point slightly before the club head.',
            drill='Hit waist-high punch swings and freeze just after impact with the grip ahead of the club head.',
            related_metrics=['trackingSummary.golfMetrics.shaftLeanAtImpactDegrees'],
            confidence=0.72,
            source='impact_shaft_lean_proxy',
        )

    head_movement_px = _metric(biomechanics, 'headMovementPx')
    if head_movement_px is not None and head_movement_px >= 70:
        _priority(
            priorities,
            priority_id='excess-head-movement',
            category='head',
            severity='medium' if head_movement_px < 110 else 'high',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Head movement is adding contact variability',
            evidence=f'Head movement is {round(head_movement_px, 1)} px.',
            video_cue='Track the head marker from address into impact; it should stay quiet relative to the strike point.',
            likely_effect='Large head drift changes low point and strike location.',
            recommendation='Let pressure shift under you while the head stays quieter relative to the ball.',
            drill='Make slow swings with a wall or alignment stick just outside the lead side of your head.',
            related_metrics=['biomechanics.headMovementPx'],
            confidence=0.58,
            source='pose_biomechanics',
        )

    sway_px = _metric(biomechanics, 'swayPx')
    if sway_px is not None and sway_px >= 65:
        _priority(
            priorities,
            priority_id='excess-lateral-sway',
            category='downswing',
            severity='medium' if sway_px < 105 else 'high',
            phase='downswing',
            timestamp_ms=downswing_ms,
            title='Lateral sway is adding low-point risk',
            evidence=f'Hip-center sway is {round(sway_px, 1)} px.',
            video_cue='Watch the hip-center marker; it should rotate and pressure-shift without sliding past the trail side.',
            likely_effect='Too much slide moves the bottom of the arc and can cause fat or thin strikes.',
            recommendation='Turn the trail hip behind you going back, then rotate into the lead side instead of sliding.',
            drill='Put an alignment stick beside the trail hip and rehearse turns without bumping into it.',
            related_metrics=['biomechanics.swayPx'],
            confidence=0.6,
            source='pose_biomechanics',
        )

    smash_factor = _metric(launch_metrics, 'smashFactor') or _metric(launch_metrics, 'smashFactorProxy')
    if smash_factor is not None and smash_factor < 1.33:
        _priority(
            priorities,
            priority_id='low-energy-transfer',
            category='impact',
            severity='high' if smash_factor < 1.22 else 'medium',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Energy transfer looks inefficient',
            evidence=f'Smash-factor proxy is {round(smash_factor, 2)}.',
            video_cue='Check impact: face/path, handle position, and strike point should line up at the same moment.',
            likely_effect='Low energy transfer usually points to off-center contact, delivered-loft issues, or face/path mismatch.',
            recommendation='Prioritize center contact and stable delivered loft before chasing more speed.',
            drill='Hit ten half-speed shots trying to center the strike before increasing speed.',
            related_metrics=['launchMonitor.metrics.smashFactor', 'launchMonitor.metrics.smashFactorProxy'],
            confidence=0.5,
            source='launch_monitor_proxy',
        )

    contact_quality = impact_analysis.get('contactQuality') if isinstance(impact_analysis.get('contactQuality'), dict) else {}
    contact_classification = str(contact_quality.get('classification') or 'unknown')
    if contact_classification in {'thin', 'fat', 'heel', 'toe', 'off_center_unknown'}:
        title_by_classification = {
            'thin': 'Strike point suggests thin contact',
            'fat': 'Low point suggests fat-contact risk',
            'heel': 'Strike point appears toward the heel',
            'toe': 'Strike point appears toward the toe',
            'off_center_unknown': 'Strike point looks off-center but direction is unclear',
        }
        effect_by_classification = {
            'thin': 'Thin contact lowers energy transfer and can launch weak or low.',
            'fat': 'A low point behind the ball loses speed before impact and can produce heavy contact.',
            'heel': 'Heel contact can leak ball speed and influence gear-effect curve.',
            'toe': 'Toe contact can leak ball speed and influence gear-effect curve.',
            'off_center_unknown': 'Off-center contact usually lowers ball speed and makes face/path feedback harder to interpret.',
        }
        drill_by_classification = {
            'thin': 'Place a towel 4 inches behind the ball and brush the turf after the ball with half swings.',
            'fat': 'Make low-point line drills: draw a line, put the ball just ahead of it, and brush the line after contact.',
            'heel': 'Use foot-spray feedback and rehearse impact with the club exiting slightly more around you.',
            'toe': 'Use foot-spray feedback and rehearse staying in posture through the strike.',
            'off_center_unknown': 'Use foot-spray or impact tape and hit ten waist-high shots before full swings.',
        }
        _priority(
            priorities,
            priority_id=f'impact-strike-quality-{contact_classification}',
            category='impact',
            severity='high' if contact_classification in {'thin', 'fat'} else 'medium',
            phase='impact',
            timestamp_ms=impact_ms,
            title=title_by_classification[contact_classification],
            evidence=' '.join(str(item) for item in contact_quality.get('evidence', [])[:3])
            or f'Impact contact-quality proxy is {contact_classification}.',
            video_cue='Pause at impact and compare the club-head point, ball point, and low-point marker in the strike area.',
            likely_effect=effect_by_classification[contact_classification],
            recommendation='Prioritize strike-point control before interpreting curve as only a face/path issue.',
            drill=drill_by_classification[contact_classification],
            related_metrics=[
                'impactAnalysis.contactQuality.classification',
                'impactAnalysis.clubBallProximityPx',
                'impactAnalysis.estimatedLowPoint',
            ],
            confidence=_safe_float(contact_quality.get('confidence')) or 0.45,
            source='impact_strike_analysis',
        )

    return priorities


def _practice_plan(priorities: List[Dict[str, object]]) -> List[Dict[str, object]]:
    return [
        {
            'priority': index,
            'title': priority.get('title'),
            'phase': priority.get('phase'),
            'drill': priority.get('drill'),
            'checkpoint': priority.get('videoCue'),
        }
        for index, priority in enumerate(priorities[:3], start=1)
    ]


def _summary(analysis_mode: str, priorities: List[Dict[str, object]], actual_ball_flight: Dict[str, object]) -> str:
    if not priorities:
        return 'Deterministic diagnosis did not find a high-confidence swing priority from the available tracking.'
    top = priorities[0]
    if analysis_mode == 'ball_strike':
        flight = actual_ball_flight.get('actualShotShape') or 'unknown'
        direction = actual_ball_flight.get('launchDirection') or 'unknown'
        comparison = next((priority for priority in priorities if priority.get('id') == 'expected-actual-outcome-mismatch'), None)
        if comparison:
            return f'Top deterministic priority is {top["title"]}. Actual ball flight starts {direction} with {flight} shape, but expected delivery and actual result disagree.'
        return f'Top deterministic priority is {top["title"]}. Actual ball flight starts {direction} with {flight} shape.'
    return f'Top deterministic dry-swing priority is {top["title"]}. Predicted flight is a hypothesis until a ball is tracked.'


def build_swing_diagnosis(
    biomechanics: Dict[str, object],
    tracking_summary: Dict[str, object],
    ball_flight_summary: Dict[str, object],
    launch_monitor: Dict[str, object],
    dry_swing: Dict[str, object],
    phases: Optional[Dict[str, object]] = None,
    impact_analysis: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    phases = phases or {}
    biomechanics = biomechanics or {}
    tracking_summary = tracking_summary or {}
    ball_flight_summary = ball_flight_summary or {}
    launch_monitor = launch_monitor or {}
    dry_swing = dry_swing or {}
    impact_analysis = impact_analysis or {}
    launch_metrics = launch_monitor.get('metrics') if isinstance(launch_monitor.get('metrics'), dict) else {}
    launch_quality = launch_monitor.get('dataQuality') if isinstance(launch_monitor.get('dataQuality'), dict) else {}

    actual_ball_flight = _actual_ball_flight(ball_flight_summary, launch_metrics)
    has_actual_ball_flight = actual_ball_flight.get('status') == 'measured_from_validated_ball_track'
    expected_actual_comparison = _expected_actual_comparison(
        tracking_summary,
        ball_flight_summary,
        launch_metrics,
        impact_analysis,
        actual_ball_flight,
    )
    analysis_mode = 'ball_strike' if has_actual_ball_flight else 'dry_swing'
    priorities = (
        _body_and_delivery_priorities(
            biomechanics,
            tracking_summary,
            launch_metrics,
            ball_flight_summary,
            impact_analysis,
            expected_actual_comparison,
            phases,
        )
        if has_actual_ball_flight
        else _copy_dry_swing_priorities(dry_swing)
    )
    if not priorities:
        _quality_priority(priorities, tracking_summary, phases)

    priorities.sort(
        key=lambda item: (
            SEVERITY_RANK.get(str(item.get('severity')), 1),
            -float(item.get('confidence') or 0),
            int(item.get('timestampMs') or 0),
            str(item.get('id') or ''),
        )
    )
    priorities = priorities[:MAX_PRIORITIES]
    confidence_values = [
        _safe_float(priority.get('confidence'))
        for priority in priorities
        if _safe_float(priority.get('confidence')) is not None
    ]
    tracking_quality = tracking_summary.get('quality') if isinstance(tracking_summary.get('quality'), dict) else {}
    base_confidence = _safe_float(tracking_quality.get('overallTrackingConfidence')) or _safe_float(biomechanics.get('confidence')) or 0
    priority_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0
    confidence = _clamp(priority_confidence * 0.72 + base_confidence * 0.28)

    return {
        'status': 'generated' if priorities else 'insufficient_evidence',
        'modelVersion': 'deterministic-swing-diagnosis-v1',
        'analysisMode': analysis_mode,
        'llmRole': 'wording_only',
        'summary': _summary(analysis_mode, priorities, actual_ball_flight),
        'priorities': priorities,
        'practicePlan': _practice_plan(priorities),
        'actualBallFlight': actual_ball_flight,
        'expectedActualComparison': expected_actual_comparison,
        'predictedBallFlight': dry_swing.get('predictedBallFlight') if analysis_mode == 'dry_swing' else None,
        'dataQuality': {
            'confidence': round(confidence, 3),
            'trackingConfidence': _safe_float(tracking_quality.get('overallTrackingConfidence')),
            'launchMonitorConfidence': _safe_float(launch_quality.get('confidence')),
            'impactAnalysisConfidence': _safe_float((impact_analysis.get('dataQuality') or {}).get('confidence'))
            if isinstance(impact_analysis.get('dataQuality'), dict)
            else None,
            'ballFlightAvailable': has_actual_ball_flight,
            'priorityCount': len(priorities),
            'limitations': [
                'Diagnosis is deterministic and based on current video-tracking proxies.',
                'The LLM should only rewrite these priorities for clarity, not create new swing faults.',
                'Single-camera face/path, attack angle, and speed fields are not radar-grade measurements.',
            ],
        },
        'sourceFlow': [
            'vision_tracking',
            'deterministic_swing_diagnosis',
            'llm_wording_only',
        ],
        'notes': 'This object is the authoritative swing diagnosis. LLM coaching should preserve these priority IDs and timestamps.',
    }
