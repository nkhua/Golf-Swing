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
                videoMetadata={analysis.videoMetadata}
              />
              <Text style={styles.note}>
                Overlay uses MediaPipe image landmarks from the analyzed frames.
              </Text>
            </View>
          ) : null}

          <View style={styles.card}>
            <Text style={styles.subheading}>Source</Text>
            <Text style={styles.metric}>Analyzer: {analysis.source === 'on_device' ? 'On device' : 'Server fallback'}</Text>
            <Text style={styles.metric}>Raw video uploaded: {privacy.rawVideoUploaded ? 'Yes' : 'No'}</Text>
            <Text style={styles.metric}>Upload consent: {privacy.userConsentedToUpload ? 'Yes' : 'No'}</Text>
          </View>

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
            <Text style={styles.subheading}>Estimated Ball Flight</Text>
            <Text style={styles.metric}>Launch angle: {formatRange(estimates.launchAngleRange, ' deg')}</Text>
            <Text style={styles.metric}>Launch direction: {estimates.launchDirection || 'Unavailable'}</Text>
            <Text style={styles.metric}>Shot shape: {estimates.shotShape || 'Unknown'}</Text>
            <Text style={styles.metric}>Carry: {formatRange(estimates.carryRangeYards, ' yd')}</Text>
            <Text style={styles.metric}>Spin tendency: {estimates.spinTendency || 'Unknown'}</Text>
            <Text style={styles.metric}>Confidence: {formatNumber(estimates.confidence)}</Text>
            <Text style={styles.note}>
              Ball-flight fields are estimates and require future launch-monitor calibration.
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.subheading}>Pose Data</Text>
            <Text style={styles.metric}>Pose source: {poseSource}</Text>
            <Text style={styles.metric}>Frames with landmarks: {analysis.poseFrames?.length || 0}</Text>
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
