from typing import Dict, List, Optional


FACE_TO_DIRECTION = {
    'open': 'right',
    'square': 'straight',
    'closed': 'left',
}

FACE_TO_CURVE = {
    'open': 'fade',
    'square': 'straight',
    'closed': 'draw',
}

PATH_TO_BIAS = {
    'in_to_out': 'right',
    'neutral': 'straight',
    'out_to_in': 'left',
}

SEVERITY_RANK = {'high': 0, 'medium': 1, 'low': 2}
MAX_FINDINGS = 8
FINDING_WINDOW_MS = {
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


def _safe_round(value: Optional[float], digits: int = 2) -> Optional[float]:
    return round(value, digits) if value is not None else None


def _clamp(value: float, minimum: float = 0, maximum: float = 1) -> float:
    return min(max(value, minimum), maximum)


def _metric(metrics: Dict[str, object], key: str) -> Optional[float]:
    return _safe_float(metrics.get(key))


def _phase_time(phases: Dict[str, object], phase: str, fallback: Optional[int] = None) -> int:
    timestamp = _safe_int(phases.get(phase))
    if timestamp is not None:
        return timestamp
    return fallback if fallback is not None else 0


def _bucket_from_degrees(value: Optional[float], negative_label: str, positive_label: str, neutral_label: str) -> str:
    if value is None:
        return 'unknown'
    if value <= -2.5:
        return negative_label
    if value >= 2.5:
        return positive_label
    return neutral_label


def _issue(
    findings: List[Dict[str, object]],
    *,
    issue_id: str,
    category: str,
    severity: str,
    phase: str,
    timestamp_ms: int,
    title: str,
    evidence: str,
    video_cue: str,
    likely_effect: str,
    fix: str,
    drill: str,
    related_metrics: List[str],
    confidence: float,
    end_timestamp_ms: Optional[int] = None,
) -> None:
    normalized_end_ms = end_timestamp_ms
    if normalized_end_ms is None or normalized_end_ms < timestamp_ms:
        normalized_end_ms = timestamp_ms + FINDING_WINDOW_MS.get(phase, FINDING_WINDOW_MS['overall'])

    findings.append({
        'id': issue_id,
        'category': category,
        'severity': severity,
        'phase': phase,
        'timestampMs': timestamp_ms,
        'endTimestampMs': normalized_end_ms,
        'title': title,
        'evidence': evidence,
        'videoCue': video_cue,
        'likelyEffect': likely_effect,
        'fix': fix,
        'drill': drill,
        'relatedMetrics': related_metrics,
        'confidence': round(_clamp(confidence), 3),
    })


def _start_direction(face_to_target: object, face_angle_degrees: Optional[float], club_path_proxy: object) -> str:
    if face_to_target in FACE_TO_DIRECTION:
        return FACE_TO_DIRECTION[str(face_to_target)]

    from_degrees = _bucket_from_degrees(face_angle_degrees, 'left', 'right', 'straight')
    if from_degrees != 'unknown':
        return from_degrees

    if club_path_proxy in PATH_TO_BIAS:
        return PATH_TO_BIAS[str(club_path_proxy)]
    return 'unknown'


def _curve(face_to_path: object, face_to_path_degrees: Optional[float], club_path_proxy: object) -> str:
    if face_to_path in FACE_TO_CURVE:
        return FACE_TO_CURVE[str(face_to_path)]

    from_degrees = _bucket_from_degrees(face_to_path_degrees, 'draw', 'fade', 'straight')
    if from_degrees != 'unknown':
        return from_degrees

    if club_path_proxy == 'out_to_in':
        return 'fade'
    if club_path_proxy == 'in_to_out':
        return 'draw'
    return 'unknown'


def _contact_risk(
    shaft_lean: Optional[float],
    attack_angle: Optional[float],
    head_movement_px: Optional[float],
    sway_px: Optional[float],
) -> str:
    if shaft_lean is not None and shaft_lean <= -10:
        return 'scoop_or_thin_contact_risk'
    if attack_angle is not None and attack_angle <= -8:
        return 'steep_or_fat_contact_risk'
    if attack_angle is not None and attack_angle >= 8:
        return 'upward_or_thin_contact_risk'
    if (head_movement_px is not None and head_movement_px >= 75) or (sway_px is not None and sway_px >= 70):
        return 'low_point_control_risk'
    return 'center_contact_unknown'


def _trajectory(
    shaft_lean: Optional[float],
    attack_angle: Optional[float],
) -> str:
    if shaft_lean is not None and shaft_lean <= -10:
        return 'high_or_weak'
    if shaft_lean is not None and shaft_lean >= 18 and attack_angle is not None and attack_angle <= -4:
        return 'low_or_de_lofted'
    if attack_angle is not None and attack_angle >= 6:
        return 'higher'
    if attack_angle is not None and attack_angle <= -6:
        return 'lower'
    return 'mid_or_unknown'


def _prediction_confidence(
    club_face: Dict[str, object],
    launch_quality: Dict[str, object],
    tracking_quality: Dict[str, object],
    biomechanics: Dict[str, object],
) -> float:
    evidence = [
        _safe_float(club_face.get('confidence')),
        _safe_float(launch_quality.get('attackAngleConfidence')),
        _safe_float(tracking_quality.get('overallTrackingConfidence')),
        _safe_float(biomechanics.get('confidence')),
    ]
    values = [value for value in evidence if value is not None]
    if not values:
        return 0
    return _clamp(sum(values) / len(values) * 0.82, 0, 0.72)


def _predict_ball_flight(
    biomechanics: Dict[str, object],
    golf_metrics: Dict[str, object],
    launch_metrics: Dict[str, object],
    launch_quality: Dict[str, object],
    tracking_quality: Dict[str, object],
) -> Dict[str, object]:
    club_face = golf_metrics.get('clubFaceEstimate') if isinstance(golf_metrics.get('clubFaceEstimate'), dict) else {}
    face_to_target = launch_metrics.get('faceToTarget') or club_face.get('faceToTarget')
    face_to_path = launch_metrics.get('faceToPath') or club_face.get('faceToPath')
    club_path_proxy = launch_metrics.get('clubPathProxy') or club_face.get('clubPathProxy')
    face_angle_degrees = _metric(launch_metrics, 'faceAngleDegrees')
    if face_angle_degrees is None:
        face_angle_degrees = _safe_float(club_face.get('estimatedDegreesToTarget'))
    face_to_path_degrees = _metric(launch_metrics, 'faceToPathDegrees')
    if face_to_path_degrees is None:
        face_to_path_degrees = _safe_float(club_face.get('estimatedDegreesToPath'))

    shaft_lean = _metric(golf_metrics, 'shaftLeanAtImpactDegrees')
    attack_angle = _metric(launch_metrics, 'attackAngleDegrees')
    head_movement_px = _metric(biomechanics, 'headMovementPx')
    sway_px = _metric(biomechanics, 'swayPx')

    start_direction = _start_direction(face_to_target, face_angle_degrees, club_path_proxy)
    curve = _curve(face_to_path, face_to_path_degrees, club_path_proxy)
    confidence = _prediction_confidence(club_face, launch_quality, tracking_quality, biomechanics)
    evidence: List[str] = []
    if face_to_target and face_to_target != 'unknown':
        evidence.append(f'face-to-target proxy is {face_to_target}')
    if face_to_path and face_to_path != 'unknown':
        evidence.append(f'face-to-path proxy is {face_to_path}')
    if club_path_proxy and club_path_proxy != 'unknown':
        evidence.append(f'club-path proxy is {club_path_proxy}')
    if attack_angle is not None:
        evidence.append(f'attack-angle proxy is {round(attack_angle, 2)} deg')
    if shaft_lean is not None:
        evidence.append(f'impact shaft lean is {round(shaft_lean, 2)} deg')

    status = 'predicted_from_dry_swing' if confidence >= 0.18 and evidence else 'insufficient_evidence'
    return {
        'status': status,
        'startDirection': start_direction,
        'curve': curve,
        'contactRisk': _contact_risk(shaft_lean, attack_angle, head_movement_px, sway_px),
        'trajectory': _trajectory(shaft_lean, attack_angle),
        'confidence': round(confidence, 3),
        'evidence': evidence,
        'notes': (
            'Predicted from dry-swing biomechanics and club-delivery proxies. This is not an actual shot result.'
            if status == 'predicted_from_dry_swing'
            else 'Not enough club-delivery evidence to predict ball flight from this dry swing.'
        ),
    }


def _tracking_quality_finding(
    findings: List[Dict[str, object]],
    tracking_summary: Dict[str, object],
    tracking_quality: Dict[str, object],
    phases: Dict[str, object],
) -> None:
    confidence = _safe_float(tracking_quality.get('overallTrackingConfidence')) or 0
    needs_retake = bool(tracking_quality.get('needsRetake'))
    reasons = tracking_quality.get('retakeReasons') if isinstance(tracking_quality.get('retakeReasons'), list) else []
    if confidence >= 0.55 and not needs_retake:
        return

    evidence = ' '.join(str(reason) for reason in reasons) or f'Overall tracking confidence is {round(confidence, 2)}.'
    severity = 'high' if confidence < 0.35 or needs_retake else 'medium'
    _issue(
        findings,
        issue_id='tracking-quality',
        category='tracking_quality',
        severity=severity,
        phase='overall',
        timestamp_ms=_phase_time(phases, 'address', _safe_int(tracking_summary.get('estimatedImpactMs')) or 0),
        title='Retake quality limits swing diagnosis',
        evidence=evidence,
        video_cue='Check whether the full body, hands, club head, and impact area stay in frame.',
        likely_effect='The analyzer may over-weight noisy club, wrist, or head measurements.',
        fix='Retake from a stable down-the-line angle with the full body, ball area, and entire club visible.',
        drill='Record one slow rehearsal first, then confirm the overlay tracks wrists and club head through impact.',
        related_metrics=['trackingSummary.quality.overallTrackingConfidence', 'trackingSummary.quality.retakeReasons'],
        confidence=max(0.35, 1 - confidence),
    )


def _biomechanics_findings(
    biomechanics: Dict[str, object],
    tracking_summary: Dict[str, object],
    golf_metrics: Dict[str, object],
    launch_metrics: Dict[str, object],
    prediction: Dict[str, object],
    phases: Dict[str, object],
) -> List[Dict[str, object]]:
    findings: List[Dict[str, object]] = []
    tracking_quality = tracking_summary.get('quality') if isinstance(tracking_summary.get('quality'), dict) else {}
    impact_ms = _phase_time(phases, 'impact', _safe_int(tracking_summary.get('estimatedImpactMs')) or 0)
    top_ms = _phase_time(phases, 'topOfBackswing', impact_ms)
    downswing_ms = _phase_time(phases, 'downswing', (top_ms + impact_ms) // 2 if impact_ms else top_ms)
    address_ms = _phase_time(phases, 'address', 0)

    _tracking_quality_finding(findings, tracking_summary, tracking_quality, phases)

    shaft_lean = _metric(golf_metrics, 'shaftLeanAtImpactDegrees')
    if shaft_lean is not None and shaft_lean <= -10:
        _issue(
            findings,
            issue_id='impact-handle-trails',
            category='impact',
            severity='high',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Handle is trailing the club head at impact',
            evidence=f'Impact shaft lean proxy is {round(shaft_lean, 1)} deg.',
            video_cue='At impact, compare the grip point to the club head; the grip should not arrive behind the head.',
            likely_effect='Adds loft, moves the low point backward, and raises thin or weak-contact risk.',
            fix='Rehearse a flatter lead wrist and a handle that reaches the strike point slightly before the club head.',
            drill='Hit waist-high punch swings and freeze just after impact with the grip ahead of the club head.',
            related_metrics=['trackingSummary.golfMetrics.shaftLeanAtImpactDegrees'],
            confidence=0.72,
        )
    elif shaft_lean is not None and shaft_lean < 4:
        _issue(
            findings,
            issue_id='impact-neutral-handle',
            category='impact',
            severity='medium',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Impact handle position is not clearly forward',
            evidence=f'Impact shaft lean proxy is {round(shaft_lean, 1)} deg.',
            video_cue='Pause at impact and check whether the hands are slightly ahead of the club head.',
            likely_effect='Can reduce compression and make strike quality depend heavily on timing.',
            fix='Move pressure into the lead side earlier and keep the handle moving through the strike.',
            drill='Make slow 9-to-3 swings with a tee just ahead of the ball and brush the tee after impact.',
            related_metrics=['trackingSummary.golfMetrics.shaftLeanAtImpactDegrees'],
            confidence=0.58,
        )
    elif shaft_lean is not None and shaft_lean >= 24:
        _issue(
            findings,
            issue_id='impact-excess-forward-lean',
            category='impact',
            severity='medium',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Impact may be over-de-lofted',
            evidence=f'Impact shaft lean proxy is {round(shaft_lean, 1)} deg.',
            video_cue='At impact, check whether the handle is far ahead and the club head is dragging too long.',
            likely_effect='Can lower launch and make the club approach too steep if the body stalls.',
            fix='Keep rotating through impact so forward shaft lean comes from body turn, not a hand shove.',
            drill='Make three-quarter swings feeling chest, hands, and club exiting together.',
            related_metrics=['trackingSummary.golfMetrics.shaftLeanAtImpactDegrees'],
            confidence=0.5,
        )

    face_to_target = launch_metrics.get('faceToTarget')
    face_to_path = launch_metrics.get('faceToPath')
    club_path_proxy = launch_metrics.get('clubPathProxy')
    club_path_degrees = _metric(launch_metrics, 'clubPathDegrees')
    if prediction.get('status') == 'predicted_from_dry_swing' and (
        prediction.get('startDirection') not in {'straight', 'unknown'}
        or prediction.get('curve') not in {'straight', 'unknown'}
    ):
        _issue(
            findings,
            issue_id='predicted-face-path-ball-flight',
            category='impact',
            severity='medium',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Face and path predict a curved ball flight',
            evidence=(
                f"Dry swing prediction is start {prediction.get('startDirection')} with "
                f"{prediction.get('curve')} curve from face/path proxies."
            ),
            video_cue='Pause at impact and compare the face/path readout with the club-head path through the ball.',
            likely_effect='Face angle tends to control start direction; face-to-path tends to control curve.',
            fix='Use a small intermediate target and rehearse the club face matching that line at waist-high impact.',
            drill='Make slow split-hand swings, stopping at impact with the face square to the intended start line.',
            related_metrics=['launchMonitor.metrics.faceToTarget', 'launchMonitor.metrics.faceToPath'],
            confidence=_safe_float(prediction.get('confidence')) or 0.45,
        )

    if club_path_proxy in {'in_to_out', 'out_to_in'} and (club_path_degrees is None or abs(club_path_degrees) >= 7):
        if club_path_proxy == 'out_to_in':
            title = 'Club path is working across the ball'
            effect = 'Often pairs with pull starts, fades, slices, and glancing contact when the face is open to path.'
            fix = 'Feel the trail shoulder staying back longer while the club exits more around the body after impact.'
            drill = 'Place a soft headcover outside the target line behind the ball and make half swings missing it.'
        else:
            title = 'Club path is working strongly from the inside'
            effect = 'Can create push starts or hooks when the face closes relative to the path.'
            fix = 'Let the chest keep turning so the club does not get trapped behind the hands through impact.'
            drill = 'Make pump rehearsals where the hands return in front of the trail thigh before rotating through.'
        _issue(
            findings,
            issue_id=f'club-path-{club_path_proxy}',
            category='downswing',
            severity='medium',
            phase='downswing',
            timestamp_ms=downswing_ms,
            title=title,
            evidence=f'Club path proxy is {club_path_proxy}' + (f' at {round(club_path_degrees, 1)} deg.' if club_path_degrees is not None else '.'),
            video_cue='Watch the club-head trace from the top into impact and compare it with the target line.',
            likely_effect=effect,
            fix=fix,
            drill=drill,
            related_metrics=['launchMonitor.metrics.clubPathProxy', 'launchMonitor.metrics.clubPathDegrees'],
            confidence=0.56,
        )

    tempo_ratio = _metric(biomechanics, 'tempoRatio')
    if tempo_ratio is not None and tempo_ratio < 2.1:
        _issue(
            findings,
            issue_id='rushed-transition',
            category='tempo',
            severity='medium',
            phase='topOfBackswing',
            timestamp_ms=top_ms,
            title='Transition is rushed',
            evidence=f'Tempo ratio is {round(tempo_ratio, 2)}.',
            video_cue='Watch the change of direction at the top; the downswing begins almost immediately.',
            likely_effect='A rushed transition can steepen the shaft and make face timing inconsistent.',
            fix='Let the backswing finish before the lower body starts the downswing.',
            drill='Use a count of one-two to the top and three through impact for ten slow rehearsals.',
            related_metrics=['biomechanics.tempoRatio', 'biomechanics.backswingTimeMs', 'biomechanics.downswingTimeMs'],
            confidence=0.55,
        )
    elif tempo_ratio is not None and tempo_ratio > 4.0:
        _issue(
            findings,
            issue_id='disconnected-tempo',
            category='tempo',
            severity='low',
            phase='topOfBackswing',
            timestamp_ms=top_ms,
            title='Tempo may be disconnected',
            evidence=f'Tempo ratio is {round(tempo_ratio, 2)}.',
            video_cue='Compare the length of the backswing with the speed of the downswing transition.',
            likely_effect='A very long backswing relative to the downswing can make sequencing harder to repeat.',
            fix='Shorten the rehearsal to a controlled three-quarter backswing while keeping speed through impact.',
            drill='Hit ten three-quarter swings while holding the finish for two seconds.',
            related_metrics=['biomechanics.tempoRatio'],
            confidence=0.42,
        )

    shoulder_turn = _metric(biomechanics, 'shoulderTurnAtTop')
    hip_turn = _metric(biomechanics, 'hipTurnAtTop')
    if shoulder_turn is not None and shoulder_turn < 55:
        _issue(
            findings,
            issue_id='limited-shoulder-turn',
            category='backswing',
            severity='medium',
            phase='topOfBackswing',
            timestamp_ms=top_ms,
            title='Backswing turn is limited',
            evidence=f'Shoulder turn at the top is {round(shoulder_turn, 1)} deg.',
            video_cue='At the top, check whether the lead shoulder has moved fully under the chin line.',
            likely_effect='Limited turn can force arms-only speed and make low point timing harder.',
            fix='Turn the ribcage around a steady spine angle instead of only lifting the arms.',
            drill='Make cross-arm turns to the top, then repeat with the club while keeping the head centered.',
            related_metrics=['biomechanics.shoulderTurnAtTop'],
            confidence=0.52,
        )
    if shoulder_turn is not None and hip_turn is not None and shoulder_turn - hip_turn < 18 and shoulder_turn >= 60:
        _issue(
            findings,
            issue_id='low-shoulder-hip-separation',
            category='backswing',
            severity='low',
            phase='topOfBackswing',
            timestamp_ms=top_ms,
            title='Shoulder and hip turn are not separating much',
            evidence=f'Shoulder turn is {round(shoulder_turn, 1)} deg and hip turn is {round(hip_turn, 1)} deg.',
            video_cue='At the top, compare shoulder rotation with hip rotation in the body overlay.',
            likely_effect='Less separation can reduce stored rotation and make the downswing more arms-driven.',
            fix='Keep trail-hip depth while turning the chest a little more against a stable lower body.',
            drill='Do step-through rehearsals: turn to the top, pause, then step and rotate through.',
            related_metrics=['biomechanics.shoulderTurnAtTop', 'biomechanics.hipTurnAtTop'],
            confidence=0.4,
        )

    head_movement_px = _metric(biomechanics, 'headMovementPx')
    if head_movement_px is not None and head_movement_px >= 70:
        _issue(
            findings,
            issue_id='excess-head-movement',
            category='head',
            severity='medium' if head_movement_px < 110 else 'high',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Head is moving too much for stable contact',
            evidence=f'Head movement is {round(head_movement_px, 1)} px.',
            video_cue='Track the head marker from address into impact; it should not drift across the strike area.',
            likely_effect='Large head drift changes the low point and makes strike location harder to repeat.',
            fix='Let pressure shift under you while the head stays quieter relative to the ball.',
            drill='Make slow swings with a wall or alignment stick just outside the lead side of your head.',
            related_metrics=['biomechanics.headMovementPx'],
            confidence=0.58,
        )

    sway_px = _metric(biomechanics, 'swayPx')
    if sway_px is not None and sway_px >= 65:
        _issue(
            findings,
            issue_id='excess-lateral-sway',
            category='downswing',
            severity='medium' if sway_px < 105 else 'high',
            phase='downswing',
            timestamp_ms=downswing_ms,
            title='Lateral sway is adding low-point risk',
            evidence=f'Hip-center sway is {round(sway_px, 1)} px.',
            video_cue='Watch the hip-center marker; it should rotate and pressure-shift without sliding past the trail side.',
            likely_effect='Too much slide moves the bottom of the arc and can cause fat or thin strikes.',
            fix='Turn the trail hip behind you going back, then rotate into the lead side instead of sliding.',
            drill='Put an alignment stick beside the trail hip and rehearse turns without bumping into it.',
            related_metrics=['biomechanics.swayPx'],
            confidence=0.6,
        )

    head_turn = _metric(golf_metrics, 'headTurnAtImpact')
    eye_line_address = _metric(golf_metrics, 'eyeLineAngleAtAddress')
    eye_line_impact = _metric(golf_metrics, 'eyeLineAngleAtImpact')
    eye_line_change = abs(eye_line_impact - eye_line_address) if eye_line_address is not None and eye_line_impact is not None else None
    if (head_turn is not None and abs(head_turn) >= 0.16) or (eye_line_change is not None and eye_line_change >= 8):
        evidence_parts = []
        if head_turn is not None:
            evidence_parts.append(f'head-turn proxy at impact is {round(head_turn, 3)}')
        if eye_line_change is not None:
            evidence_parts.append(f'eye-line changed {round(eye_line_change, 1)} deg')
        _issue(
            findings,
            issue_id='early-head-eye-release',
            category='head',
            severity='medium',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Head and eye line release early',
            evidence='; '.join(evidence_parts) + '.',
            video_cue='At impact, watch whether the head and eye-line overlay leave the strike point before the club arrives.',
            likely_effect='Early visual release can pull posture open and move contact around the face.',
            fix='Keep the chest rotating while the eyes stay on the strike point until just after impact.',
            drill='Hit slow chips and call out the exact spot where the ball was after the club passes.',
            related_metrics=['trackingSummary.golfMetrics.headTurnAtImpact', 'trackingSummary.golfMetrics.eyeLineAngleAtImpact'],
            confidence=0.54,
        )

    attack_angle = _metric(launch_metrics, 'attackAngleDegrees')
    if attack_angle is not None and attack_angle <= -8:
        _issue(
            findings,
            issue_id='steep-attack-angle',
            category='impact',
            severity='medium',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Attack angle proxy is steep',
            evidence=f'Attack-angle proxy is {round(attack_angle, 1)} deg down.',
            video_cue='Watch the club-head trace immediately before impact; it is dropping sharply into the strike.',
            likely_effect='Raises fat-contact and high-spin/low-launch risk, especially without enough body rotation.',
            fix='Shallow the club earlier and rotate through instead of chopping down late.',
            drill='Make split-grip pump swings where the club shallows behind you before turning through.',
            related_metrics=['launchMonitor.metrics.attackAngleDegrees'],
            confidence=0.5,
        )
    elif attack_angle is not None and attack_angle >= 8:
        _issue(
            findings,
            issue_id='upward-attack-angle',
            category='impact',
            severity='low',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Attack angle proxy is very upward',
            evidence=f'Attack-angle proxy is {round(attack_angle, 1)} deg up.',
            video_cue='Watch whether the club is already rising before it reaches the strike point.',
            likely_effect='Can work with driver, but with irons it can raise thin-contact and low-compression risk.',
            fix='Match ball position and low point to the club; irons need the low point ahead of the ball.',
            drill='Brush the turf after the ball line for five slow iron rehearsals.',
            related_metrics=['launchMonitor.metrics.attackAngleDegrees'],
            confidence=0.43,
        )

    left_wrist_impact = _metric(golf_metrics, 'leftWristAngleAtImpact')
    right_wrist_impact = _metric(golf_metrics, 'rightWristAngleAtImpact')
    wrist_values = [value for value in (left_wrist_impact, right_wrist_impact) if value is not None]
    if wrist_values and (min(wrist_values) < 115 or max(wrist_values) > 172):
        _issue(
            findings,
            issue_id='wrist-condition-impact',
            category='wrist',
            severity='medium',
            phase='impact',
            timestamp_ms=impact_ms,
            title='Impact wrist condition looks extreme',
            evidence='; '.join(f'{name} is {round(value, 1)} deg' for name, value in (
                ('left wrist angle', left_wrist_impact),
                ('right wrist angle', right_wrist_impact),
            ) if value is not None) + '.',
            video_cue='At impact, compare both wrist markers with the forearm lines; look for a flip or locked-out shape.',
            likely_effect='Extreme wrist angles can change delivered loft and face control late.',
            fix='Rehearse a stable lead wrist and passive trail wrist through a waist-high impact position.',
            drill='Use lead-hand-only half swings, stopping at impact to check the wrist angle in the overlay.',
            related_metrics=[
                'trackingSummary.golfMetrics.leftWristAngleAtImpact',
                'trackingSummary.golfMetrics.rightWristAngleAtImpact',
            ],
            confidence=0.48,
        )

    findings.sort(key=lambda item: (SEVERITY_RANK.get(str(item.get('severity')), 1), int(item.get('timestampMs') or 0), str(item.get('id'))))
    return findings[:MAX_FINDINGS]


def _practice_plan(findings: List[Dict[str, object]]) -> List[Dict[str, object]]:
    plan: List[Dict[str, object]] = []
    for index, finding in enumerate(findings[:3], start=1):
        plan.append({
            'priority': index,
            'title': finding.get('title'),
            'phase': finding.get('phase'),
            'drill': finding.get('drill'),
            'checkpoint': finding.get('videoCue'),
        })
    return plan


def _overall_confidence(
    biomechanics: Dict[str, object],
    tracking_summary: Dict[str, object],
    launch_monitor: Dict[str, object],
    prediction: Dict[str, object],
) -> float:
    tracking_quality = tracking_summary.get('quality') if isinstance(tracking_summary.get('quality'), dict) else {}
    launch_quality = launch_monitor.get('dataQuality') if isinstance(launch_monitor.get('dataQuality'), dict) else {}
    values = [
        _safe_float(biomechanics.get('confidence')),
        _safe_float(tracking_quality.get('overallTrackingConfidence')),
        _safe_float(launch_quality.get('confidence')),
        _safe_float(prediction.get('confidence')),
    ]
    usable = [value for value in values if value is not None]
    if not usable:
        return 0
    return _clamp(sum(usable) / len(usable))


def analyze_dry_swing(
    biomechanics: Dict[str, object],
    tracking_summary: Dict[str, object],
    launch_monitor: Dict[str, object],
    ball_flight_summary: Dict[str, object],
    phases: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Build a deterministic dry-swing analysis without inventing actual ball flight."""
    phases = phases or {}
    biomechanics = biomechanics or {}
    tracking_summary = tracking_summary or {}
    launch_monitor = launch_monitor or {}
    ball_flight_summary = ball_flight_summary or {}

    has_valid_ball_flight = (
        ball_flight_summary.get('status') == 'tracked'
        and (_safe_float(ball_flight_summary.get('confidence')) or 0) >= 0.45
    )
    if has_valid_ball_flight:
        return {
            'status': 'not_dry_swing',
            'mode': 'ball_strike',
            'actualBallFlightAvailable': True,
            'predictedBallFlight': {
                'status': 'not_applicable',
                'startDirection': 'unknown',
                'curve': 'unknown',
                'contactRisk': 'actual_ball_flight_available',
                'trajectory': 'actual_ball_flight_available',
                'confidence': 0,
                'evidence': [],
            },
            'biomechanicalFindings': [],
            'practicePlan': [],
            'dataQuality': {
                'confidence': 0,
                'ballFlightStatus': ball_flight_summary.get('status'),
                'limitations': ['Validated ball flight is available; use ballFlightSummary and launchMonitor actual-shot fields.'],
            },
            'notes': 'Dry swing mode is skipped when validated ball flight exists.',
        }

    golf_metrics = tracking_summary.get('golfMetrics') if isinstance(tracking_summary.get('golfMetrics'), dict) else {}
    launch_metrics = launch_monitor.get('metrics') if isinstance(launch_monitor.get('metrics'), dict) else {}
    launch_quality = launch_monitor.get('dataQuality') if isinstance(launch_monitor.get('dataQuality'), dict) else {}
    tracking_quality = tracking_summary.get('quality') if isinstance(tracking_summary.get('quality'), dict) else {}
    prediction = _predict_ball_flight(biomechanics, golf_metrics, launch_metrics, launch_quality, tracking_quality)
    findings = _biomechanics_findings(biomechanics, tracking_summary, golf_metrics, launch_metrics, prediction, phases)
    confidence = _overall_confidence(biomechanics, tracking_summary, launch_monitor, prediction)
    has_evidence = bool(findings) or prediction.get('status') == 'predicted_from_dry_swing'
    has_tracking_quality_finding = any(finding.get('id') == 'tracking-quality' for finding in findings)
    status = 'generated' if has_evidence and (confidence >= 0.18 or has_tracking_quality_finding) else 'insufficient_evidence'

    return {
        'status': status,
        'mode': 'dry_swing',
        'modelVersion': 'dry-swing-biomechanics-v1',
        'actualBallFlightAvailable': False,
        'predictedBallFlight': prediction,
        'biomechanicalFindings': findings,
        'practicePlan': _practice_plan(findings),
        'dataQuality': {
            'confidence': round(confidence, 3),
            'biomechanicsConfidence': _safe_round(_safe_float(biomechanics.get('confidence')), 3),
            'trackingConfidence': _safe_round(_safe_float(tracking_quality.get('overallTrackingConfidence')), 3),
            'clubSpeedAvailable': _safe_float(launch_metrics.get('clubSpeedPxPerSec')) is not None,
            'clubFaceProxyAvailable': isinstance(golf_metrics.get('clubFaceEstimate'), dict),
            'ballFlightStatus': ball_flight_summary.get('status') or 'no_ball_detected',
            'ballCandidateFrameCount': _safe_int(ball_flight_summary.get('ballCandidateFrameCount')) or 0,
            'missingEvidence': [
                key
                for key, available in {
                    'validatedBallFlight': False,
                    'clubFaceProxy': isinstance(golf_metrics.get('clubFaceEstimate'), dict),
                    'impactShaftLean': _metric(golf_metrics, 'shaftLeanAtImpactDegrees') is not None,
                    'tempoRatio': _metric(biomechanics, 'tempoRatio') is not None,
                    'headMovement': _metric(biomechanics, 'headMovementPx') is not None,
                }.items()
                if not available
            ],
            'limitations': [
                'No validated ball flight was detected, so predictedBallFlight is a hypothesis, not the actual shot.',
                'Single-camera club face, club path, attack angle, and wrist metrics are screen-space proxies.',
                'Use this mode to coach movement patterns; confirm final ball flight with a real ball or launch monitor.',
            ],
        },
        'notes': (
            'Dry swing mode analyzes body, wrist, head/eye, club delivery, and launch-monitor proxy fields while '
            'keeping predicted ball flight separate from actual shot-shape evidence.'
        ),
    }
