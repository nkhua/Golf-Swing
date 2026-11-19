import React, { useMemo } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import Skeleton3DViewer from '../components/Skeleton3DViewer';
import SwingVideoSkeletonOverlay from '../components/SwingVideoSkeletonOverlay';
import { createSkeletonFrameFromNamedPoseLandmarks } from '../services/model/createSkeletonFrame';
import { smoothSkeletonFrames } from '../services/model/smoothSkeletonFrames';

const formatMs = (value) => (typeof value === 'number' ? `${value} ms` : 'Unavailable');
const formatNumber = (value, suffix = '') => (typeof value === 'number' ? `${value}${suffix}` : 'Unavailable');
const formatRange = (value, suffix = '') =>
  Array.isArray(value) && value.length === 2 ? `${value[0]}-${value[1]}${suffix}` : 'Unavailable';
const formatLabel = (value) =>
  typeof value === 'string'
    ? value
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase())
    : 'Unavailable';
const objectMetric = (value) =>
  value && typeof value === 'object' && !Array.isArray(value) ? value : {};

export default function ResultsScreen({ route }) {
  const { analysis } = route.params || {};
  const biomechanics = analysis?.biomechanics || {};
  const estimates = analysis?.ballFlightEstimates || {};
  const privacy = analysis?.privacy || {};
  const swingWindow = analysis?.swingWindow;
  const trackingSummary = analysis?.trackingSummary || {};
  const trackingGolfMetrics = trackingSummary.golfMetrics || {};
  const clubFaceEstimate = objectMetric(trackingGolfMetrics.clubFaceEstimate);
  const trackingQuality = trackingSummary.quality || {};
  const ballFlightSummary = analysis?.ballFlightSummary || {};
  const ballFlightQuality = ballFlightSummary.quality || {};
  const launchMonitor = analysis?.launchMonitor || {};
  const launchMonitorMetrics = launchMonitor.metrics || {};
  const launchMonitorQuality = launchMonitor.dataQuality || {};
  const launchMonitorCalibration = launchMonitor.calibration || {};
  const launchMonitorInterpretation = Array.isArray(launchMonitor.interpretation) ? launchMonitor.interpretation : [];
  const impactAnalysis = analysis?.impactAnalysis || {};
  const impactContact = impactAnalysis.contactQuality || {};
  const impactLowPoint = impactAnalysis.estimatedLowPoint || {};
  const impactFacePath = impactAnalysis.facePathProxy || {};
  const impactVisual = impactAnalysis.visualImpactInference || {};
  const impactQuality = impactAnalysis.dataQuality || {};
  const drySwing = analysis?.drySwing || {};
  const drySwingFlight = drySwing.predictedBallFlight || {};
  const drySwingQuality = drySwing.dataQuality || {};
  const drySwingFindings = Array.isArray(drySwing.biomechanicalFindings) ? drySwing.biomechanicalFindings : [];
  const drySwingPracticePlan = Array.isArray(drySwing.practicePlan) ? drySwing.practicePlan : [];
  const swingDiagnosis = analysis?.swingDiagnosis || {};
  const diagnosisPriorities = Array.isArray(swingDiagnosis.priorities) ? swingDiagnosis.priorities : [];
  const diagnosisQuality = swingDiagnosis.dataQuality || {};
  const diagnosisActualFlight = swingDiagnosis.actualBallFlight || {};
  const diagnosisPredictedFlight = swingDiagnosis.predictedBallFlight || {};
  const expectedActual = swingDiagnosis.expectedActualComparison || {};
  const expectedOutcome = expectedActual.expectedOutcome || {};
  const actualOutcome = expectedActual.actualOutcome || {};
  const outcomeAgreement = expectedActual.agreement || {};
  const uncertaintyFlags = Array.isArray(expectedActual.uncertaintyFlags) ? expectedActual.uncertaintyFlags : [];
  const diagnosisPainPoints = diagnosisPriorities.map((priority, index) => ({
    id: priority.id || `diagnosis-${index + 1}`,
    category: priority.category || 'tracking_quality',
    severity: priority.severity || 'medium',
    phase: priority.phase || 'overall',
    title: priority.title || 'Swing diagnosis priority',
    evidence: priority.evidence || 'Deterministic diagnosis evidence was limited.',
    videoCue: priority.videoCue || priority.likelyEffect || 'Compare this timestamp with the overlay.',
    timestampMs: typeof priority.timestampMs === 'number' ? priority.timestampMs : 0,
    endTimestampMs:
      typeof priority.endTimestampMs === 'number'
        ? priority.endTimestampMs
        : typeof priority.timestampMs === 'number'
          ? priority.timestampMs
          : 0,
    recommendation: priority.recommendation || 'Retake with clearer framing.',
    drill: priority.drill || 'Record one slow rehearsal and compare the same phase.',
    relatedMetrics: Array.isArray(priority.relatedMetrics) ? priority.relatedMetrics : [],
    confidence: typeof priority.confidence === 'number' ? priority.confidence : 0,
  }));
  const drySwingPainPoints = drySwingFindings.map((finding, index) => ({
    id: finding.id || `dry-swing-${index + 1}`,
    category: finding.category || 'tracking_quality',
    severity: finding.severity || 'medium',
    phase: finding.phase || 'overall',
    title: finding.title || 'Dry swing finding',
    evidence: finding.evidence || 'Measured dry-swing evidence was limited.',
    videoCue: finding.videoCue || finding.likelyEffect || 'Compare this timestamp with the overlay.',
    timestampMs: typeof finding.timestampMs === 'number' ? finding.timestampMs : 0,
    endTimestampMs:
      typeof finding.endTimestampMs === 'number'
        ? finding.endTimestampMs
        : typeof finding.timestampMs === 'number'
          ? finding.timestampMs
          : 0,
    recommendation: finding.fix || 'Retake with clearer framing.',
    drill: finding.drill || 'Record one slow rehearsal and compare the same phase.',
    relatedMetrics: Array.isArray(finding.relatedMetrics) ? finding.relatedMetrics : [],
    confidence: typeof finding.confidence === 'number' ? finding.confidence : 0,
  }));
  const swingCoaching = analysis?.swingCoaching || {};
  const coachingPainPoints = Array.isArray(swingCoaching.painPoints) ? swingCoaching.painPoints : [];
  const videoPainPoints = coachingPainPoints.length ? coachingPainPoints : diagnosisPainPoints.length ? diagnosisPainPoints : drySwingPainPoints;
  const skeletonBuild = useMemo(() => {
    if (!analysis?.poseFrames?.length) {
      return { frames: [], error: null };
    }

    try {
      const frames = smoothSkeletonFrames(
        analysis.poseFrames.map((poseFrame) =>
          createSkeletonFrameFromNamedPoseLandmarks(
            poseFrame.landmarks || [],
            poseFrame.frameIndex,
            poseFrame.timestampMs
          )
        )
      );
      return { frames, error: null };
    } catch {
      return { frames: [], error: 'Pose frames were received, but required body landmarks were missing.' };
    }
  }, [analysis?.poseFrames]);
  const skeletonFrames = skeletonBuild.frames;
  const poseSource =
    analysis?.source === 'server' && privacy.rawVideoUploaded
      ? 'Real video processed by backend MediaPipe'
      : analysis?.source === 'on_device'
        ? 'On-device or mock pose frames'
        : 'Unavailable';

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Swing Analysis</Text>
      {analysis ? (
        <View style={styles.content}>
          {analysis.localVideoUri && analysis.poseFrames?.length ? (
            <View style={styles.card}>
              <Text style={styles.subheading}>Video Skeleton Overlay</Text>
              <SwingVideoSkeletonOverlay
                videoUri={analysis.localVideoUri}
                poseFrames={analysis.poseFrames}
                trackingFrames={analysis.trackingFrames}
                ballTrackingFrames={analysis.ballTrackingFrames}
                coachingPainPoints={videoPainPoints}
                trackingSummary={trackingSummary}
                videoMetadata={analysis.videoMetadata}
                swingWindow={swingWindow}
              />
              <Text style={styles.note}>
                Overlay uses MediaPipe pose landmarks plus tracked wrist, grip, club-head, shaft, and post-impact ball points.
              </Text>
            </View>
          ) : null}

          <View style={styles.card}>
            <Text style={styles.subheading}>Source</Text>
            <Text style={styles.metric}>Analyzer: {analysis.source === 'on_device' ? 'On device' : 'Server fallback'}</Text>
            <Text style={styles.metric}>Raw video uploaded: {privacy.rawVideoUploaded ? 'Yes' : 'No'}</Text>
            <Text style={styles.metric}>Upload consent: {privacy.userConsentedToUpload ? 'Yes' : 'No'}</Text>
            <Text style={styles.metric}>Frames sent to LLM: {privacy.videoFramesSentToLlm ? 'Yes' : 'No'}</Text>
            <Text style={styles.metric}>Impact frames sent to LLM: {privacy.impactFramesSentToLlm ? 'Yes' : 'No'}</Text>
            <Text style={styles.metric}>Swing metrics sent to LLM: {privacy.swingMetricsSentToLlm ? 'Yes' : 'No'}</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.subheading}>LLM Swing Coach</Text>
            <Text style={styles.metric}>Status: {swingCoaching.status || 'Unavailable'}</Text>
            <Text style={styles.metric}>Model: {swingCoaching.model || 'Unavailable'}</Text>
            <Text style={styles.metric}>Role: {swingDiagnosis.llmRole ? formatLabel(swingDiagnosis.llmRole) : 'Wording Only'}</Text>
            <Text style={styles.metric}>Confidence: {formatNumber(swingCoaching.confidence)}</Text>
            {swingCoaching.summary ? <Text style={styles.coachingSummary}>{swingCoaching.summary}</Text> : null}
            {coachingPainPoints.length ? (
              <View style={styles.painPointList}>
                {coachingPainPoints.map((painPoint, index) => (
                  <View key={painPoint.id || `${painPoint.title}-${index}`} style={styles.painPointRow}>
                    <Text style={styles.painPointMeta}>
                      {painPoint.severity || 'medium'} | {painPoint.phase || 'overall'} | {formatMs(painPoint.timestampMs)}
                    </Text>
                    <Text style={styles.painPointTitle}>{painPoint.title}</Text>
                    <Text style={styles.painPointText}>{painPoint.evidence}</Text>
                    <Text style={styles.painPointCue}>Video cue: {painPoint.videoCue}</Text>
                    <Text style={styles.painPointText}>Fix: {painPoint.recommendation}</Text>
                    <Text style={styles.painPointText}>Drill: {painPoint.drill}</Text>
                  </View>
                ))}
              </View>
            ) : null}
            {swingCoaching.notes ? <Text style={styles.note}>{swingCoaching.notes}</Text> : null}
          </View>

          {swingDiagnosis.status ? (
            <View style={styles.card}>
              <Text style={styles.subheading}>Deterministic Swing Diagnosis</Text>
              <Text style={styles.metric}>Status: {formatLabel(swingDiagnosis.status)}</Text>
              <Text style={styles.metric}>Mode: {formatLabel(swingDiagnosis.analysisMode)}</Text>
              <Text style={styles.metric}>LLM role: {formatLabel(swingDiagnosis.llmRole)}</Text>
              <Text style={styles.metric}>Confidence: {formatNumber(diagnosisQuality.confidence)}</Text>
              <Text style={styles.metric}>Actual ball flight: {formatLabel(diagnosisActualFlight.status)}</Text>
              <Text style={styles.metric}>Actual shot shape: {formatLabel(diagnosisActualFlight.actualShotShape)}</Text>
              {diagnosisPredictedFlight?.status ? (
                <Text style={styles.metric}>Predicted flight: {formatLabel(diagnosisPredictedFlight.startDirection)} / {formatLabel(diagnosisPredictedFlight.curve)}</Text>
              ) : null}
              {swingDiagnosis.summary ? <Text style={styles.coachingSummary}>{swingDiagnosis.summary}</Text> : null}
              {diagnosisPriorities.length ? (
                <View style={styles.painPointList}>
                  {diagnosisPriorities.map((priority, index) => (
                    <View key={priority.id || `${priority.title}-${index}`} style={styles.painPointRow}>
                      <Text style={styles.painPointMeta}>
                        {priority.severity || 'medium'} | {priority.phase || 'overall'} | {formatMs(priority.timestampMs)}
                      </Text>
                      <Text style={styles.painPointTitle}>{priority.title}</Text>
                      <Text style={styles.painPointText}>{priority.evidence}</Text>
                      {priority.likelyEffect ? <Text style={styles.painPointText}>Likely effect: {priority.likelyEffect}</Text> : null}
                      <Text style={styles.painPointCue}>Video cue: {priority.videoCue}</Text>
                      <Text style={styles.painPointText}>Fix: {priority.recommendation}</Text>
                      <Text style={styles.painPointText}>Drill: {priority.drill}</Text>
                    </View>
                  ))}
                </View>
              ) : null}
              {swingDiagnosis.notes ? <Text style={styles.note}>{swingDiagnosis.notes}</Text> : null}
            </View>
          ) : null}

          {expectedActual.status ? (
            <View style={styles.card}>
              <Text style={styles.subheading}>Expected vs Actual</Text>
              <Text style={styles.metric}>Training signal: {formatLabel(expectedActual.trainingSignal)}</Text>
              <Text style={styles.metric}>Expected start: {formatLabel(expectedOutcome.startDirection)}</Text>
              <Text style={styles.metric}>Expected curve: {formatLabel(expectedOutcome.curve)}</Text>
              <Text style={styles.metric}>Expected face/path: {formatLabel(expectedOutcome.faceToTarget)} / {formatLabel(expectedOutcome.faceToPath)}</Text>
              <Text style={styles.metric}>Actual start: {formatLabel(actualOutcome.startDirection)}</Text>
              <Text style={styles.metric}>Actual curve: {formatLabel(actualOutcome.curve)}</Text>
              <Text style={styles.metric}>Start agreement: {formatLabel(outcomeAgreement.startDirection)}</Text>
              <Text style={styles.metric}>Curve agreement: {formatLabel(outcomeAgreement.curve)}</Text>
              <Text style={styles.metric}>Overall agreement: {formatLabel(outcomeAgreement.overall)}</Text>
              <Text style={styles.metric}>Comparison confidence: {formatNumber(expectedActual.confidence)}</Text>
              {expectedActual.coachingInstruction ? <Text style={styles.note}>{expectedActual.coachingInstruction}</Text> : null}
              {uncertaintyFlags.length ? (
                <View style={styles.launchMonitorNotes}>
                  {uncertaintyFlags.map((flag) => (
                    <Text key={flag} style={styles.note}>
                      {formatLabel(flag)}
                    </Text>
                  ))}
                </View>
              ) : null}
            </View>
          ) : null}

          {swingWindow ? (
            <View style={styles.card}>
              <Text style={styles.subheading}>Swing Cut</Text>
              <Text style={styles.metric}>Playback start: {formatMs(swingWindow.startMs)}</Text>
              <Text style={styles.metric}>Detected swing start: {formatMs(swingWindow.detectedStartMs)}</Text>
              <Text style={styles.metric}>Pre-roll: {formatMs(swingWindow.preRollMs)}</Text>
              <Text style={styles.metric}>Detected swing finish: {formatMs(swingWindow.detectedEndMs)}</Text>
              <Text style={styles.metric}>Ball-flight post-roll: {formatMs(swingWindow.postRollMs)}</Text>
              <Text style={styles.metric}>Playback end: {formatMs(swingWindow.endMs)}</Text>
              <Text style={styles.metric}>Method: {swingWindow.method === 'llm_vision' ? 'LLM vision' : swingWindow.method}</Text>
              <Text style={styles.metric}>Confidence: {formatNumber(swingWindow.confidence)}</Text>
              {swingWindow.notes ? <Text style={styles.note}>{swingWindow.notes}</Text> : null}
            </View>
          ) : null}

          <View style={styles.card}>
            <Text style={styles.subheading}>Measured from Pose</Text>
            <Text style={styles.metric}>Tempo ratio: {formatNumber(biomechanics.tempoRatio)}</Text>
            <Text style={styles.metric}>Backswing time: {formatMs(biomechanics.backswingTimeMs)}</Text>
            <Text style={styles.metric}>Downswing time: {formatMs(biomechanics.downswingTimeMs)}</Text>
            <Text style={styles.metric}>Spine angle at address: {formatNumber(biomechanics.spineAngleAtAddress, ' deg')}</Text>
            <Text style={styles.metric}>Shoulder turn at top: {formatNumber(biomechanics.shoulderTurnAtTop, ' deg')}</Text>
            <Text style={styles.metric}>Hip turn at top: {formatNumber(biomechanics.hipTurnAtTop, ' deg')}</Text>
            <Text style={styles.metric}>Head movement: {formatNumber(biomechanics.headMovementPx, ' px')}</Text>
            <Text style={styles.metric}>Sway: {formatNumber(biomechanics.swayPx, ' px')}</Text>
            <Text style={styles.note}>
              Pose values are early measurements from video landmarks, not final coaching truth.
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.subheading}>Body, Wrist, Eye, and Club Tracking</Text>
            <Text style={styles.metric}>Tracking frames: {trackingSummary.framesTracked || analysis.trackingFrames?.length || 0}</Text>
            <Text style={styles.metric}>Body frames: {trackingSummary.bodyFrameCount || 0}</Text>
            <Text style={styles.metric}>Wrist frames: {trackingSummary.wristFrameCount || 0}</Text>
            <Text style={styles.metric}>Hand-detail frames: {trackingSummary.handFrameCount || 0}</Text>
            <Text style={styles.metric}>Head/eye frames: {trackingSummary.headFrameCount || trackingSummary.faceFrameCount || 0}</Text>
            <Text style={styles.metric}>Club frames: {trackingSummary.clubFrameCount || 0}</Text>
            <Text style={styles.metric}>Club confidence: {formatNumber(trackingSummary.averageClubConfidence)}</Text>
            <Text style={styles.metric}>Overall tracking confidence: {formatNumber(trackingQuality.overallTrackingConfidence)}</Text>
            <Text style={styles.metric}>Avg left wrist angle: {formatNumber(trackingGolfMetrics.averageLeftWristAngleDegrees, ' deg')}</Text>
            <Text style={styles.metric}>Avg right wrist angle: {formatNumber(trackingGolfMetrics.averageRightWristAngleDegrees, ' deg')}</Text>
            <Text style={styles.metric}>Impact shaft lean: {formatNumber(trackingGolfMetrics.shaftLeanAtImpactDegrees, ' deg')}</Text>
            <Text style={styles.metric}>Eye line at address: {formatNumber(trackingGolfMetrics.eyeLineAngleAtAddress, ' deg')}</Text>
            <Text style={styles.metric}>Head turn at impact: {formatNumber(trackingGolfMetrics.headTurnAtImpact)}</Text>
            <Text style={styles.metric}>Club face proxy: {formatLabel(clubFaceEstimate.status)}</Text>
            <Text style={styles.metric}>Face to target: {formatLabel(clubFaceEstimate.faceToTarget)}</Text>
            <Text style={styles.metric}>Face to path: {formatLabel(clubFaceEstimate.faceToPath)}</Text>
            <Text style={styles.metric}>Club path proxy: {formatLabel(clubFaceEstimate.clubPathProxy)}</Text>
            <Text style={styles.metric}>Face estimate confidence: {formatNumber(clubFaceEstimate.confidence)}</Text>
            <Text style={styles.metric}>Face degrees to target: {formatNumber(clubFaceEstimate.estimatedDegreesToTarget, ' deg')}</Text>
            <Text style={styles.metric}>Face degrees to path: {formatNumber(clubFaceEstimate.estimatedDegreesToPath, ' deg')}</Text>
            <Text style={styles.metric}>Grip path: {formatNumber(trackingSummary.gripPathLengthPx, ' px')}</Text>
            <Text style={styles.metric}>Club-head path: {formatNumber(trackingSummary.clubHeadPathLengthPx, ' px')}</Text>
            <Text style={styles.metric}>Max club speed: {formatNumber(trackingSummary.maxClubHeadSpeedPxPerSec, ' px/s')}</Text>
            <Text style={styles.metric}>Estimated impact: {formatMs(trackingSummary.estimatedImpactMs)}</Text>
            {trackingQuality.needsRetake && Array.isArray(trackingQuality.retakeReasons) ? (
              <Text style={styles.note}>{trackingQuality.retakeReasons.join(' ')}</Text>
            ) : null}
            {trackingSummary.notes ? <Text style={styles.note}>{trackingSummary.notes}</Text> : null}
          </View>

          <View style={styles.card}>
            <Text style={styles.subheading}>Launch Monitor Proxy</Text>
            <Text style={styles.metric}>Status: {formatLabel(launchMonitor.status)}</Text>
            <Text style={styles.metric}>Calibration: {formatLabel(launchMonitorCalibration.status)}</Text>
            <Text style={styles.metric}>Overall confidence: {formatNumber(launchMonitorQuality.confidence)}</Text>
            <Text style={styles.metric}>Club speed: {formatNumber(launchMonitorMetrics.clubSpeedMph, ' mph')}</Text>
            <Text style={styles.metric}>Club speed proxy: {formatNumber(launchMonitorMetrics.clubSpeedPxPerSec, ' px/s')}</Text>
            <Text style={styles.metric}>Ball speed: {formatNumber(launchMonitorMetrics.ballSpeedMph, ' mph')}</Text>
            <Text style={styles.metric}>Ball speed proxy: {formatNumber(launchMonitorMetrics.ballSpeedPxPerSec, ' px/s')}</Text>
            <Text style={styles.metric}>Smash factor: {formatNumber(launchMonitorMetrics.smashFactor)}</Text>
            <Text style={styles.metric}>Launch angle: {formatNumber(launchMonitorMetrics.launchAngleDegrees, ' deg')}</Text>
            <Text style={styles.metric}>Launch direction: {formatLabel(launchMonitorMetrics.launchDirection)}</Text>
            <Text style={styles.metric}>Attack angle: {formatNumber(launchMonitorMetrics.attackAngleDegrees, ' deg')}</Text>
            <Text style={styles.metric}>Face angle: {formatNumber(launchMonitorMetrics.faceAngleDegrees, ' deg')}</Text>
            <Text style={styles.metric}>Face to path: {formatNumber(launchMonitorMetrics.faceToPathDegrees, ' deg')}</Text>
            <Text style={styles.metric}>Spin rate: {formatNumber(launchMonitorMetrics.spinRateRpm, ' rpm')}</Text>
            <Text style={styles.metric}>Visible carry: {formatNumber(launchMonitorMetrics.visibleCarryYards, ' yd')}</Text>
            <Text style={styles.metric}>True carry: {formatNumber(launchMonitorMetrics.carryYards, ' yd')}</Text>
            {launchMonitorInterpretation.length ? (
              <View style={styles.launchMonitorNotes}>
                {launchMonitorInterpretation.map((item) => (
                  <Text key={item.id || item.text} style={styles.note}>
                    {item.text}
                  </Text>
                ))}
              </View>
            ) : null}
            {launchMonitor.notes ? <Text style={styles.note}>{launchMonitor.notes}</Text> : null}
          </View>

          {impactAnalysis.status ? (
            <View style={styles.card}>
              <Text style={styles.subheading}>Strike Point / Impact</Text>
              <Text style={styles.metric}>Status: {formatLabel(impactAnalysis.status)}</Text>
              <Text style={styles.metric}>Impact frame: {formatMs(impactAnalysis.impactTimestampMs)}</Text>
              <Text style={styles.metric}>Club-ball proximity: {formatNumber(impactAnalysis.clubBallProximityPx, ' px')}</Text>
              <Text style={styles.metric}>Contact estimate: {formatLabel(impactContact.classification)}</Text>
              <Text style={styles.metric}>Vertical strike: {formatLabel(impactContact.verticalStrike)}</Text>
              <Text style={styles.metric}>Horizontal strike: {formatLabel(impactContact.horizontalStrike)}</Text>
              <Text style={styles.metric}>Estimated low point: {formatLabel(impactLowPoint.classification)}</Text>
              <Text style={styles.metric}>Low point timing: {formatMs(impactLowPoint.relativeToImpactMs)}</Text>
              <Text style={styles.metric}>Impact shaft lean: {formatNumber(impactAnalysis.shaftLeanAtImpactDegrees, ' deg')}</Text>
              <Text style={styles.metric}>Face/path proxy: {formatLabel(impactFacePath.faceToTarget)} / {formatLabel(impactFacePath.faceToPath)}</Text>
              <Text style={styles.metric}>Visual impact LLM: {formatLabel(impactVisual.status)}</Text>
              <Text style={styles.metric}>Visual frames sent: {formatNumber(impactVisual.framesSent)}</Text>
              <Text style={styles.metric}>Impact confidence: {formatNumber(impactQuality.confidence)}</Text>
              {Array.isArray(impactContact.evidence) && impactContact.evidence.length ? (
                <View style={styles.launchMonitorNotes}>
                  {impactContact.evidence.map((item) => (
                    <Text key={item} style={styles.note}>
                      {item}
                    </Text>
                  ))}
                </View>
              ) : null}
              {impactAnalysis.notes ? <Text style={styles.note}>{impactAnalysis.notes}</Text> : null}
            </View>
          ) : null}

          {drySwing.status === 'generated' ? (
            <View style={styles.card}>
              <Text style={styles.subheading}>Dry Swing Mode</Text>
              <Text style={styles.metric}>Status: {formatLabel(drySwing.status)}</Text>
              <Text style={styles.metric}>Overall confidence: {formatNumber(drySwingQuality.confidence)}</Text>
              <Text style={styles.metric}>Ball flight source: Predicted from biomechanics and club delivery</Text>
              <Text style={styles.metric}>Predicted start: {formatLabel(drySwingFlight.startDirection)}</Text>
              <Text style={styles.metric}>Predicted curve: {formatLabel(drySwingFlight.curve)}</Text>
              <Text style={styles.metric}>Contact risk: {formatLabel(drySwingFlight.contactRisk)}</Text>
              <Text style={styles.metric}>Trajectory: {formatLabel(drySwingFlight.trajectory)}</Text>
              <Text style={styles.metric}>Prediction confidence: {formatNumber(drySwingFlight.confidence)}</Text>
              {Array.isArray(drySwingFlight.evidence) && drySwingFlight.evidence.length ? (
                <View style={styles.launchMonitorNotes}>
                  {drySwingFlight.evidence.map((item) => (
                    <Text key={item} style={styles.note}>
                      {item}
                    </Text>
                  ))}
                </View>
              ) : null}
              {drySwingFindings.length ? (
                <View style={styles.painPointList}>
                  {drySwingFindings.map((finding, index) => (
                    <View key={finding.id || `${finding.title}-${index}`} style={styles.painPointRow}>
                      <Text style={styles.painPointMeta}>
                        {finding.severity || 'medium'} | {finding.phase || 'overall'} | {formatMs(finding.timestampMs)}
                      </Text>
                      <Text style={styles.painPointTitle}>{finding.title}</Text>
                      <Text style={styles.painPointText}>{finding.evidence}</Text>
                      {finding.likelyEffect ? <Text style={styles.painPointText}>Likely effect: {finding.likelyEffect}</Text> : null}
                      {finding.videoCue ? <Text style={styles.painPointCue}>Video cue: {finding.videoCue}</Text> : null}
                      <Text style={styles.painPointText}>Fix: {finding.fix}</Text>
                      <Text style={styles.painPointText}>Drill: {finding.drill}</Text>
                    </View>
                  ))}
                </View>
              ) : null}
              {drySwingPracticePlan.length ? (
                <View style={styles.launchMonitorNotes}>
                  {drySwingPracticePlan.map((item) => (
                    <Text key={`${item.priority}-${item.title}`} style={styles.note}>
                      {item.priority}. {item.drill}
                    </Text>
                  ))}
                </View>
              ) : null}
              {drySwing.notes ? <Text style={styles.note}>{drySwing.notes}</Text> : null}
            </View>
          ) : null}

          <View style={styles.card}>
            <Text style={styles.subheading}>Estimated Ball Flight</Text>
            <Text style={styles.metric}>Ball tracking frames: {ballFlightSummary.framesTracked || analysis.ballTrackingFrames?.length || 0}</Text>
            <Text style={styles.metric}>Visible ball frames: {ballFlightSummary.ballFrameCount || 0}</Text>
            <Text style={styles.metric}>Tracked ball window: {formatMs(ballFlightSummary.trackingStartMs)}-{formatMs(ballFlightSummary.trackingEndMs)}</Text>
            <Text style={styles.metric}>Launch angle: {formatRange(estimates.launchAngleRange, ' deg')}</Text>
            <Text style={styles.metric}>Launch direction: {estimates.launchDirection || 'Unavailable'}</Text>
            <Text style={styles.metric}>Trajectory angle: {formatNumber(ballFlightSummary.trajectoryAngleDegrees, ' deg')}</Text>
            <Text style={styles.metric}>Actual shot shape: {estimates.actualShotShape || 'Unknown'}</Text>
            <Text style={styles.metric}>Ball path: {formatNumber(ballFlightSummary.ballPathLengthPx, ' px')}</Text>
            <Text style={styles.metric}>Max ball speed: {formatNumber(ballFlightSummary.maxBallSpeedPxPerSec, ' px/s')}</Text>
            <Text style={styles.metric}>Carry: {formatRange(estimates.carryRangeYards, ' yd')}</Text>
            <Text style={styles.metric}>Spin tendency: {estimates.spinTendency || 'Unknown'}</Text>
            <Text style={styles.metric}>Confidence: {formatNumber(estimates.confidence)}</Text>
            {ballFlightQuality.needsRetake && Array.isArray(ballFlightQuality.retakeReasons) ? (
              <Text style={styles.note}>{ballFlightQuality.retakeReasons.join(' ')}</Text>
            ) : null}
            <Text style={styles.note}>
              Ball-flight fields come from post-impact video tracking when visible and still require future launch-monitor calibration.
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.subheading}>Pose Data</Text>
            <Text style={styles.metric}>Pose source: {poseSource}</Text>
            <Text style={styles.metric}>Frames with landmarks: {analysis.poseFrames?.length || 0}</Text>
            <Text style={styles.metric}>Frames with point tracking: {analysis.trackingFrames?.length || 0}</Text>
            <Text style={styles.metric}>Skeleton frames built: {skeletonFrames.length}</Text>
            <Text style={styles.metric}>Joints per skeleton frame: {skeletonFrames[0] ? Object.keys(skeletonFrames[0].joints).length : 0}</Text>
            <Text style={styles.metric}>Camera angle: {analysis.videoMetadata?.cameraAngle || 'unknown'}</Text>
            <Text style={styles.metric}>Camera facing: {analysis.videoMetadata?.cameraFacing || 'unknown'}</Text>
            {skeletonBuild.error ? <Text style={styles.note}>{skeletonBuild.error}</Text> : null}
          </View>

          {skeletonFrames.length > 0 ? (
            <View style={styles.card}>
              <Text style={styles.subheading}>3D Skeleton</Text>
              <Skeleton3DViewer frames={skeletonFrames} fps={analysis.videoMetadata?.fps} />
            </View>
          ) : null}
        </View>
      ) : (
        <Text style={styles.empty}>No analysis available yet. Record a swing first.</Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    backgroundColor: '#f4f4f8',
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 16,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 18,
    marginBottom: 14,
    elevation: 3,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
  },
  content: {
    width: '100%',
  },
  metric: {
    fontSize: 16,
    marginBottom: 8,
  },
  subheading: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 10,
  },
  note: {
    marginTop: 8,
    fontSize: 13,
    lineHeight: 18,
    color: '#555',
  },
  coachingSummary: {
    marginBottom: 10,
    fontSize: 15,
    lineHeight: 21,
    color: '#333',
  },
  painPointList: {
    borderTopWidth: 1,
    borderTopColor: '#e5e5ea',
  },
  painPointRow: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e5ea',
  },
  painPointMeta: {
    marginBottom: 5,
    color: '#6b7280',
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  painPointTitle: {
    marginBottom: 6,
    color: '#111214',
    fontSize: 16,
    fontWeight: '800',
  },
  painPointText: {
    marginBottom: 5,
    color: '#333',
    fontSize: 14,
    lineHeight: 20,
  },
  painPointCue: {
    marginBottom: 5,
    color: '#7a4a00',
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 20,
  },
  launchMonitorNotes: {
    marginTop: 4,
  },
  tip: {
    marginTop: 8,
    fontSize: 15,
    lineHeight: 22,
    color: '#333',
  },
  empty: {
    fontSize: 16,
    color: '#666',
  },
});
