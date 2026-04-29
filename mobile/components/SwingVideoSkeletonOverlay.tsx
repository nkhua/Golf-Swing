import React, { useMemo, useState } from 'react';
import { useEvent, useEventListener } from 'expo';
import { useVideoPlayer, VideoView } from 'expo-video';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { LayoutChangeEvent } from 'react-native';
import type { FramePoseData, SwingVideoMetadata } from '../types/swingAnalysis';
import { normalizePlaybackFps } from '../services/model/skeletonPlayback';

type SwingVideoSkeletonOverlayProps = {
  videoUri: string;
  poseFrames: FramePoseData[];
  videoMetadata?: Partial<SwingVideoMetadata>;
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
  overlaySize,
}: {
  frame?: FramePoseData;
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
    </View>
  );
}

export default function SwingVideoSkeletonOverlay({
  videoUri,
  poseFrames,
  videoMetadata,
}: SwingVideoSkeletonOverlayProps) {
  const [overlaySize, setOverlaySize] = useState<OverlaySize>({ width: 1, height: 1 });
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const safeFps = normalizePlaybackFps(videoMetadata?.fps);
  const aspectRatio = getVideoAspectRatio(videoMetadata);
  const currentFrameIndex = getNearestPoseFrameIndex(poseFrames, currentTimeMs);
  const currentFrame = poseFrames[currentFrameIndex];
  const frameCount = poseFrames.length;
  const player = useVideoPlayer({ uri: videoUri }, (videoPlayer) => {
    videoPlayer.loop = true;
    videoPlayer.muted = true;
    videoPlayer.timeUpdateEventInterval = 1 / safeFps;
  });
  const { isPlaying } = useEvent(player, 'playingChange', { isPlaying: player.playing });

  useEventListener(player, 'timeUpdate', ({ currentTime }) => {
    setCurrentTimeMs(currentTime * 1000);
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

    player.play();
  };

  const restart = () => {
    player.currentTime = 0;
    setCurrentTimeMs(0);
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
        <PoseOverlay frame={currentFrame} overlaySize={overlaySize} />
        <View pointerEvents="none" style={styles.frameBadge}>
          <Text style={styles.frameBadgeText}>
            {frameCount ? currentFrameIndex + 1 : 0}/{frameCount}
          </Text>
        </View>
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
        <Text style={styles.timeLabel}>{Math.round(currentTimeMs)} ms</Text>
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
