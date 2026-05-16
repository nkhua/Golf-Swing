import React, { useMemo, useState } from 'react';
import { useEvent, useEventListener } from 'expo';
import { useVideoPlayer, VideoView } from 'expo-video';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { LayoutChangeEvent } from 'react-native';
import type {
  FrameBallTrackingData,
  FramePoseData,
  FrameTrackingData,
  SwingCoachingPainPoint,
  SwingTrimWindow,
  SwingVideoMetadata,
  TrackedPoint,
} from '../types/swingAnalysis';
import { normalizePlaybackFps } from '../services/model/skeletonPlayback';

type SwingVideoSkeletonOverlayProps = {
  videoUri: string;
  poseFrames: FramePoseData[];
  trackingFrames?: FrameTrackingData[];
  ballTrackingFrames?: FrameBallTrackingData[];
  coachingPainPoints?: SwingCoachingPainPoint[];
  videoMetadata?: Partial<SwingVideoMetadata>;
  swingWindow?: Partial<SwingTrimWindow>;
};

type OverlaySize = {
  width: number;
  height: number;
};

type LandmarkPoint = {
  name: string;
  x: number;
  y: number;
  visibility?: number;
};

const BONES: Array<[string, string]> = [
  ['NOSE', 'LEFT_SHOULDER'],
  ['NOSE', 'RIGHT_SHOULDER'],
  ['LEFT_SHOULDER', 'RIGHT_SHOULDER'],
  ['LEFT_SHOULDER', 'LEFT_ELBOW'],
  ['LEFT_ELBOW', 'LEFT_WRIST'],
  ['RIGHT_SHOULDER', 'RIGHT_ELBOW'],
  ['RIGHT_ELBOW', 'RIGHT_WRIST'],
  ['LEFT_SHOULDER', 'LEFT_HIP'],
  ['RIGHT_SHOULDER', 'RIGHT_HIP'],
  ['LEFT_HIP', 'RIGHT_HIP'],
  ['LEFT_HIP', 'LEFT_KNEE'],
  ['LEFT_KNEE', 'LEFT_ANKLE'],
  ['RIGHT_HIP', 'RIGHT_KNEE'],
  ['RIGHT_KNEE', 'RIGHT_ANKLE'],
];

const SKELETON_LANDMARK_NAMES = new Set(BONES.flat());

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const normalizeName = (name: string) => name.trim().toUpperCase();

export const getNearestPoseFrameIndex = (poseFrames: FramePoseData[], currentTimeMs: number) => {
  if (!poseFrames.length) {
    return 0;
  }

  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;

  for (let index = 0; index < poseFrames.length; index += 1) {
    const distance = Math.abs((poseFrames[index].timestampMs || 0) - currentTimeMs);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  }

  return nearestIndex;
};

export const getNearestTrackingFrameIndex = (trackingFrames: FrameTrackingData[], currentTimeMs: number) => {
  if (!trackingFrames.length) {
    return 0;
  }

  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;

  for (let index = 0; index < trackingFrames.length; index += 1) {
    const distance = Math.abs((trackingFrames[index].timestampMs || 0) - currentTimeMs);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  }

  return nearestIndex;
};

export const getNearestBallTrackingFrameIndex = (ballTrackingFrames: FrameBallTrackingData[], currentTimeMs: number) => {
  if (!ballTrackingFrames.length) {
    return 0;
  }

  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;

  for (let index = 0; index < ballTrackingFrames.length; index += 1) {
    const distance = Math.abs((ballTrackingFrames[index].timestampMs || 0) - currentTimeMs);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  }

  return nearestIndex;
};

export const getActiveCoachingPainPoint = (
  painPoints: SwingCoachingPainPoint[],
  currentTimeMs: number
) => {
  return painPoints.find((painPoint) => {
    const startMs = Number(painPoint.timestampMs || 0) - 250;
    const endMs = Math.max(Number(painPoint.endTimestampMs || painPoint.timestampMs || 0), startMs + 900);
    return currentTimeMs >= startMs && currentTimeMs <= endMs + 250;
  });
};

export const getVideoAspectRatio = (metadata?: Partial<SwingVideoMetadata>) => {
  const width = Number(metadata?.width || 0);
  const height = Number(metadata?.height || 0);

  if (width > 0 && height > 0) {
    return width / height;
  }

  return 9 / 16;
};

function PoseOverlay({
  frame,
  trackingFrame,
  ballTrackingFrame,
  ballTrailFrames,
  overlaySize,
}: {
  frame?: FramePoseData;
  trackingFrame?: FrameTrackingData;
  ballTrackingFrame?: FrameBallTrackingData;
  ballTrailFrames: FrameBallTrackingData[];
  overlaySize: OverlaySize;
}) {
  const landmarksByName = useMemo(() => {
    const map = new Map<string, LandmarkPoint>();
    for (const landmark of frame?.landmarks || []) {
      const normalizedName = landmark.name ? normalizeName(landmark.name) : '';
      if (SKELETON_LANDMARK_NAMES.has(normalizedName)) {
        map.set(normalizedName, { ...landmark, name: normalizedName });
      }
    }
    return map;
  }, [frame]);

  if (!frame || overlaySize.width <= 1 || overlaySize.height <= 1) {
    return null;
  }

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill} testID="pose-overlay-layer">
      {BONES.map(([fromName, toName]) => {
        const from = landmarksByName.get(fromName);
        const to = landmarksByName.get(toName);
        if (!from || !to) {
          return null;
        }

        const fromX = from.x * overlaySize.width;
        const fromY = from.y * overlaySize.height;
        const toX = to.x * overlaySize.width;
        const toY = to.y * overlaySize.height;
        const dx = toX - fromX;
        const dy = toY - fromY;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);
        const opacity = clamp(((from.visibility ?? 1) + (to.visibility ?? 1)) / 2, 0.2, 1);

        return (
          <View
            key={`${fromName}-${toName}`}
            testID="pose-overlay-bone"
            style={[
              styles.overlayBone,
              {
                left: fromX + dx / 2 - length / 2,
                top: fromY + dy / 2 - 2,
                width: length,
                opacity,
                transform: [{ rotateZ: `${angle}rad` }],
              },
            ]}
          />
        );
      })}

      {Array.from(landmarksByName.values()).map((landmark) => (
        <View
          key={landmark.name}
          testID="pose-overlay-joint"
          style={[
            styles.overlayJoint,
            {
              left: landmark.x * overlaySize.width - 4,
              top: landmark.y * overlaySize.height - 4,
              opacity: clamp(landmark.visibility ?? 1, 0.25, 1),
            },
          ]}
        />
      ))}
      <TrackingOverlay frame={trackingFrame} overlaySize={overlaySize} />
      <BallTrackingOverlay frame={ballTrackingFrame} trailFrames={ballTrailFrames} overlaySize={overlaySize} />
    </View>
  );
}

function TrackingOverlay({
  frame,
  overlaySize,
}: {
  frame?: FrameTrackingData;
  overlaySize: OverlaySize;
}) {
  if (!frame || overlaySize.width <= 1 || overlaySize.height <= 1) {
    return null;
  }

  const shaftStart = frame.clubShaft?.start || frame.grip;
  const shaftEnd = frame.clubShaft?.end || frame.clubHead;

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill} testID="tracking-overlay-layer">
      {frame.eyeLine?.start && frame.eyeLine?.end ? (
        <TrackingLine
          from={frame.eyeLine.start}
          to={frame.eyeLine.end}
          overlaySize={overlaySize}
          variant="eyeLine"
          testID="tracking-overlay-eye-line"
        />
      ) : null}
      {frame.headDirection?.start && frame.headDirection?.end ? (
        <TrackingLine
          from={frame.headDirection.start}
          to={frame.headDirection.end}
          overlaySize={overlaySize}
          variant="headDirection"
          testID="tracking-overlay-head-direction"
        />
      ) : null}
      {shaftStart && shaftEnd ? (
        <TrackingLine
          from={shaftStart}
          to={shaftEnd}
          overlaySize={overlaySize}
          variant="clubShaft"
          testID="tracking-overlay-club-shaft"
        />
      ) : null}
      <TrackingPoint point={frame.leftWrist} overlaySize={overlaySize} variant="wrist" testID="tracking-overlay-wrist" />
      <TrackingPoint point={frame.rightWrist} overlaySize={overlaySize} variant="wrist" testID="tracking-overlay-wrist" />
      <TrackingPoint point={frame.leftMiddleMcp} overlaySize={overlaySize} variant="hand" testID="tracking-overlay-hand" />
      <TrackingPoint point={frame.rightMiddleMcp} overlaySize={overlaySize} variant="hand" testID="tracking-overlay-hand" />
      <TrackingPoint point={frame.leftEye} overlaySize={overlaySize} variant="eye" testID="tracking-overlay-eye" />
      <TrackingPoint point={frame.rightEye} overlaySize={overlaySize} variant="eye" testID="tracking-overlay-eye" />
      <TrackingPoint point={frame.grip} overlaySize={overlaySize} variant="grip" testID="tracking-overlay-grip" />
      <TrackingPoint point={frame.clubHead} overlaySize={overlaySize} variant="clubHead" testID="tracking-overlay-club-head" />
    </View>
  );
}

function BallTrackingOverlay({
  frame,
  trailFrames,
  overlaySize,
}: {
  frame?: FrameBallTrackingData;
  trailFrames: FrameBallTrackingData[];
  overlaySize: OverlaySize;
}) {
  if (overlaySize.width <= 1 || overlaySize.height <= 1) {
    return null;
  }

  const visibleTrail = trailFrames.filter((trailFrame) => trailFrame.ball);
  const ball = frame?.ball;

  if (!ball && visibleTrail.length < 2) {
    return null;
  }

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill} testID="ball-tracking-overlay-layer">
      {visibleTrail.slice(1).map((trailFrame, index) => {
        const previous = visibleTrail[index];
        if (!previous.ball || !trailFrame.ball) {
          return null;
        }

        return (
          <TrackingLine
            key={`${previous.frameIndex}-${trailFrame.frameIndex}`}
            from={previous.ball}
            to={trailFrame.ball}
            overlaySize={overlaySize}
            variant="ballTrail"
            testID="ball-tracking-overlay-trail"
          />
        );
      })}
      <TrackingPoint point={ball} overlaySize={overlaySize} variant="ball" testID="ball-tracking-overlay-point" />
    </View>
  );
}

function TrackingLine({
  from,
  to,
  overlaySize,
  variant = 'clubShaft',
  testID,
}: {
  from: TrackedPoint;
  to: TrackedPoint;
  overlaySize: OverlaySize;
  variant?: 'clubShaft' | 'eyeLine' | 'headDirection' | 'ballTrail';
  testID: string;
}) {
  const fromX = from.x * overlaySize.width;
  const fromY = from.y * overlaySize.height;
  const toX = to.x * overlaySize.width;
  const toY = to.y * overlaySize.height;
  const dx = toX - fromX;
  const dy = toY - fromY;
  const length = Math.sqrt(dx * dx + dy * dy);
  const angle = Math.atan2(dy, dx);
  const opacity = clamp(Math.min(from.confidence ?? 0, to.confidence ?? 0), 0.2, 0.95);
  const lineStyle =
    variant === 'eyeLine'
      ? styles.trackingEyeLine
      : variant === 'headDirection'
        ? styles.trackingHeadDirection
        : variant === 'ballTrail'
          ? styles.trackingBallTrail
        : styles.trackingClubShaft;

  return (
    <View
      testID={testID}
      style={[
        lineStyle,
        {
          left: fromX + dx / 2 - length / 2,
          top: fromY + dy / 2 - 1.5,
          width: length,
          opacity,
          transform: [{ rotateZ: `${angle}rad` }],
        },
      ]}
    />
  );
}

function TrackingPoint({
  point,
  overlaySize,
  variant,
  testID,
}: {
  point?: TrackedPoint;
  overlaySize: OverlaySize;
  variant: 'wrist' | 'hand' | 'eye' | 'grip' | 'clubHead' | 'ball';
  testID: string;
}) {
  if (!point) {
    return null;
  }

  const size = variant === 'clubHead' ? 12 : variant === 'ball' ? 11 : variant === 'grip' ? 9 : variant === 'eye' ? 7 : 10;
  const style =
    variant === 'clubHead'
      ? styles.trackingClubHead
      : variant === 'ball'
        ? styles.trackingBall
      : variant === 'hand'
        ? styles.trackingHand
        : variant === 'eye'
          ? styles.trackingEye
      : variant === 'grip'
        ? styles.trackingGrip
        : styles.trackingWrist;

  return (
    <View
      testID={testID}
      style={[
        styles.trackingPoint,
        style,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          left: point.x * overlaySize.width - size / 2,
          top: point.y * overlaySize.height - size / 2,
          opacity: clamp(point.confidence ?? 0, 0.25, 1),
        },
      ]}
    />
  );
}

export default function SwingVideoSkeletonOverlay({
  videoUri,
  poseFrames,
  trackingFrames = [],
  ballTrackingFrames = [],
  coachingPainPoints = [],
  videoMetadata,
  swingWindow,
}: SwingVideoSkeletonOverlayProps) {
  const [overlaySize, setOverlaySize] = useState<OverlaySize>({ width: 1, height: 1 });
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const safeFps = normalizePlaybackFps(videoMetadata?.fps);
  const aspectRatio = getVideoAspectRatio(videoMetadata);
  const trimStartMs = Math.max(0, Number(swingWindow?.startMs || 0));
  const trimEndMs = Math.max(trimStartMs, Number(swingWindow?.endMs || videoMetadata?.durationMs || 0));
  const hasTrimWindow = trimEndMs > trimStartMs;
  const currentFrameIndex = getNearestPoseFrameIndex(poseFrames, currentTimeMs);
  const currentTrackingFrameIndex = getNearestTrackingFrameIndex(trackingFrames, currentTimeMs);
  const currentBallTrackingFrameIndex = getNearestBallTrackingFrameIndex(ballTrackingFrames, currentTimeMs);
  const currentFrame = poseFrames[currentFrameIndex];
  const currentTrackingFrame = trackingFrames[currentTrackingFrameIndex];
  const currentBallTrackingFrame = ballTrackingFrames[currentBallTrackingFrameIndex];
  const visibleBallTrackingFrame =
    currentBallTrackingFrame && Math.abs((currentBallTrackingFrame.timestampMs || 0) - currentTimeMs) <= 300
      ? currentBallTrackingFrame
      : undefined;
  const ballTrailFrames = ballTrackingFrames
    .filter((frame) => frame.timestampMs <= currentTimeMs && frame.ball)
    .slice(-10);
  const activeCoachingPainPoint = getActiveCoachingPainPoint(coachingPainPoints, currentTimeMs);
  const frameCount = poseFrames.length;
  const player = useVideoPlayer({ uri: videoUri }, (videoPlayer) => {
    videoPlayer.loop = true;
    videoPlayer.muted = true;
    videoPlayer.timeUpdateEventInterval = 1 / safeFps;
    if (hasTrimWindow) {
      videoPlayer.currentTime = trimStartMs / 1000;
    }
  });
  const { isPlaying } = useEvent(player, 'playingChange', { isPlaying: player.playing });

  useEventListener(player, 'timeUpdate', ({ currentTime }) => {
    const nextTimeMs = currentTime * 1000;
    if (hasTrimWindow && nextTimeMs >= trimEndMs) {
      player.currentTime = trimStartMs / 1000;
      setCurrentTimeMs(trimStartMs);
      return;
    }

    setCurrentTimeMs(nextTimeMs);
  });

  const handleOverlayLayout = (event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    setOverlaySize({
      width: Math.max(width, 1),
      height: Math.max(height, 1),
    });
  };

  const togglePlayback = () => {
    if (isPlaying) {
      player.pause();
      return;
    }

    if (hasTrimWindow && (currentTimeMs < trimStartMs || currentTimeMs >= trimEndMs)) {
      player.currentTime = trimStartMs / 1000;
      setCurrentTimeMs(trimStartMs);
    }
    player.play();
  };

  const restart = () => {
    player.currentTime = hasTrimWindow ? trimStartMs / 1000 : 0;
    setCurrentTimeMs(hasTrimWindow ? trimStartMs : 0);
  };

  return (
    <View style={styles.container} testID="swing-video-skeleton-overlay">
      <View
        style={[styles.videoStage, { aspectRatio }]}
        onLayout={handleOverlayLayout}
        testID="swing-video-overlay-stage"
      >
        <VideoView
          testID="swing-video-view"
          player={player}
          nativeControls={false}
          contentFit="fill"
          allowsFullscreen={false}
          allowsPictureInPicture={false}
          surfaceType="textureView"
          style={StyleSheet.absoluteFill}
        />
        <PoseOverlay
          frame={currentFrame}
          trackingFrame={currentTrackingFrame}
          ballTrackingFrame={visibleBallTrackingFrame}
          ballTrailFrames={ballTrailFrames}
          overlaySize={overlaySize}
        />
        <View pointerEvents="none" style={styles.frameBadge}>
          <Text style={styles.frameBadgeText}>
            {frameCount ? currentFrameIndex + 1 : 0}/{frameCount}
          </Text>
        </View>
        {activeCoachingPainPoint ? (
          <View pointerEvents="none" style={styles.coachingCue} testID="coaching-video-cue">
            <Text style={styles.coachingCuePhase}>{activeCoachingPainPoint.phase}</Text>
            <Text style={styles.coachingCueTitle}>{activeCoachingPainPoint.title}</Text>
            <Text style={styles.coachingCueText}>{activeCoachingPainPoint.videoCue}</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.controls}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isPlaying ? 'Pause overlaid swing video' : 'Play overlaid swing video'}
          onPress={togglePlayback}
          style={styles.controlButton}
        >
          <Text style={styles.controlButtonText}>{isPlaying ? 'Pause' : 'Play'}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Restart overlaid swing video"
          onPress={restart}
          style={[styles.controlButton, styles.secondaryButton]}
        >
          <Text style={styles.secondaryButtonText}>Restart</Text>
        </Pressable>
        <Text style={styles.timeLabel}>
          {Math.round(currentTimeMs)} ms{hasTrimWindow ? ` / ${Math.round(trimStartMs)}-${Math.round(trimEndMs)} ms` : ''}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    overflow: 'hidden',
    borderRadius: 8,
    backgroundColor: '#111214',
  },
  videoStage: {
    width: '100%',
    overflow: 'hidden',
    backgroundColor: '#000',
  },
  overlayBone: {
    position: 'absolute',
    height: 4,
    borderRadius: 2,
    backgroundColor: '#34c759',
  },
  overlayJoint: {
    position: 'absolute',
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#f2f2f7',
    borderWidth: 1,
    borderColor: '#34c759',
  },
  trackingClubShaft: {
    position: 'absolute',
    height: 3,
    borderRadius: 2,
    backgroundColor: '#ffd60a',
  },
  trackingEyeLine: {
    position: 'absolute',
    height: 2,
    borderRadius: 1,
    backgroundColor: '#64d2ff',
  },
  trackingHeadDirection: {
    position: 'absolute',
    height: 2,
    borderRadius: 1,
    backgroundColor: '#bf5af2',
  },
  trackingBallTrail: {
    position: 'absolute',
    height: 2,
    borderRadius: 1,
    backgroundColor: '#ff453a',
  },
  trackingPoint: {
    position: 'absolute',
    borderWidth: 2,
  },
  trackingWrist: {
    backgroundColor: 'rgba(10, 132, 255, 0.82)',
    borderColor: '#f2f2f7',
  },
  trackingGrip: {
    backgroundColor: '#ff375f',
    borderColor: '#fff',
  },
  trackingHand: {
    backgroundColor: '#ff9f0a',
    borderColor: '#fff',
  },
  trackingEye: {
    backgroundColor: '#64d2ff',
    borderColor: '#001f2d',
  },
  trackingClubHead: {
    backgroundColor: '#ffd60a',
    borderColor: '#1c1c1e',
  },
  trackingBall: {
    backgroundColor: '#fff',
    borderColor: '#ff453a',
  },
  frameBadge: {
    position: 'absolute',
    right: 10,
    top: 10,
    minWidth: 52,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 5,
    backgroundColor: 'rgba(0, 0, 0, 0.62)',
  },
  frameBadgeText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '700',
    textAlign: 'center',
  },
  coachingCue: {
    position: 'absolute',
    left: 10,
    right: 10,
    bottom: 10,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 9,
    backgroundColor: 'rgba(0, 0, 0, 0.72)',
    borderWidth: 1,
    borderColor: 'rgba(255, 214, 10, 0.75)',
  },
  coachingCuePhase: {
    color: '#ffd60a',
    fontSize: 11,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  coachingCueTitle: {
    marginTop: 3,
    color: '#fff',
    fontSize: 14,
    fontWeight: '800',
  },
  coachingCueText: {
    marginTop: 3,
    color: '#f2f2f7',
    fontSize: 12,
    lineHeight: 16,
  },
  controls: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#1c1c1e',
  },
  controlButton: {
    minWidth: 72,
    minHeight: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    backgroundColor: '#34c759',
  },
  secondaryButton: {
    backgroundColor: '#2c2c2e',
  },
  controlButtonText: {
    color: '#071108',
    fontSize: 14,
    fontWeight: '700',
  },
  secondaryButtonText: {
    color: '#f2f2f7',
    fontSize: 14,
    fontWeight: '700',
  },
  timeLabel: {
    flex: 1,
    color: '#f2f2f7',
    fontSize: 12,
    textAlign: 'right',
  },
});
