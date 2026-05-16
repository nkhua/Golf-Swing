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

export default function ResultsScreen({ route }) {
  const { analysis } = route.params || {};
  const biomechanics = analysis?.biomechanics || {};
  const estimates = analysis?.ballFlightEstimates || {};
  const privacy = analysis?.privacy || {};
  const swingWindow = analysis?.swingWindow;
  const trackingSummary = analysis?.trackingSummary || {};
  const trackingGolfMetrics = trackingSummary.golfMetrics || {};
  const trackingQuality = trackingSummary.quality || {};
  const ballFlightSummary = analysis?.ballFlightSummary || {};
  const ballFlightQuality = ballFlightSummary.quality || {};
  const swingCoaching = analysis?.swingCoaching || {};
  const coachingPainPoints = Array.isArray(swingCoaching.painPoints) ? swingCoaching.painPoints : [];
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
                coachingPainPoints={coachingPainPoints}
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
            <Text style={styles.metric}>Swing metrics sent to LLM: {privacy.swingMetricsSentToLlm ? 'Yes' : 'No'}</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.subheading}>LLM Swing Coach</Text>
            <Text style={styles.metric}>Status: {swingCoaching.status || 'Unavailable'}</Text>
            <Text style={styles.metric}>Model: {swingCoaching.model || 'Unavailable'}</Text>
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
            <Text style={styles.subheading}>Estimated Ball Flight</Text>
            <Text style={styles.metric}>Ball tracking frames: {ballFlightSummary.framesTracked || analysis.ballTrackingFrames?.length || 0}</Text>
            <Text style={styles.metric}>Visible ball frames: {ballFlightSummary.ballFrameCount || 0}</Text>
            <Text style={styles.metric}>Tracked ball window: {formatMs(ballFlightSummary.trackingStartMs)}-{formatMs(ballFlightSummary.trackingEndMs)}</Text>
            <Text style={styles.metric}>Launch angle: {formatRange(estimates.launchAngleRange, ' deg')}</Text>
            <Text style={styles.metric}>Launch direction: {estimates.launchDirection || 'Unavailable'}</Text>
            <Text style={styles.metric}>Trajectory angle: {formatNumber(ballFlightSummary.trajectoryAngleDegrees, ' deg')}</Text>
            <Text style={styles.metric}>Shot shape: {estimates.shotShape || 'Unknown'}</Text>
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
