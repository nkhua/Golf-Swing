import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PanResponder, Pressable, StyleSheet, Text, View } from 'react-native';
import type {
  SkeletonFrame,
  SkeletonJoint,
  SkeletonJointName,
  SkeletonPoint3D,
} from '../services/model/createSkeletonFrame';
import {
  advanceFrameIndex,
  getFrameIndexFromProgress,
  getTimelineProgress,
  normalizePlaybackFps,
} from '../services/model/skeletonPlayback';

type Skeleton3DViewerProps = {
  frames?: SkeletonFrame[];
  fps?: number;
  loop?: boolean;
  frame?: SkeletonFrame | null;
};

type OrbitState = {
  yaw: number;
  pitch: number;
};

type CanvasSize = {
  width: number;
  height: number;
};

type ProjectedJoint = SkeletonJoint & {
  screenX: number;
  screenY: number;
  depth: number;
};

type ProjectionBounds = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
};

const BONES: Array<[SkeletonJointName, SkeletonJointName]> = [
  ['head', 'chest_center'],
  ['chest_center', 'pelvis_center'],
  ['left_shoulder', 'right_shoulder'],
  ['left_shoulder', 'left_elbow'],
  ['left_elbow', 'left_wrist'],
  ['right_shoulder', 'right_elbow'],
  ['right_elbow', 'right_wrist'],
  ['left_shoulder', 'left_hip'],
  ['right_shoulder', 'right_hip'],
  ['left_hip', 'right_hip'],
  ['left_hip', 'left_knee'],
  ['left_knee', 'left_ankle'],
  ['right_hip', 'right_knee'],
  ['right_knee', 'right_ankle'],
];

const JOINT_SIZE = 10;
const MIN_VIEW_SIZE = 1;
const MIN_POSE_SPAN = 0.28;
const PROJECTION_PADDING_RATIO = 0.16;
const MIN_BOUND_SAMPLE_COUNT = 6;

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const rotatePoint = (position: SkeletonPoint3D, orbit: OrbitState): SkeletonPoint3D => {
  const cosYaw = Math.cos(orbit.yaw);
  const sinYaw = Math.sin(orbit.yaw);
  const cosPitch = Math.cos(orbit.pitch);
  const sinPitch = Math.sin(orbit.pitch);
  const x = position.x * cosYaw - position.z * sinYaw;
  const z = position.x * sinYaw + position.z * cosYaw;
  const y = -position.y * cosPitch - z * sinPitch;

  return {
    x,
    y,
    z: -position.y * sinPitch + z * cosPitch,
  };
};

const percentile = (values: number[], ratio: number) => {
  if (!values.length) {
    return 0;
  }

  const sorted = [...values].sort((a, b) => a - b);
  const index = clamp(Math.round((sorted.length - 1) * ratio), 0, sorted.length - 1);
  return sorted[index];
};

const expandBounds = (bounds: ProjectionBounds): ProjectionBounds => {
  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerY = (bounds.minY + bounds.maxY) / 2;
  const width = Math.max(bounds.maxX - bounds.minX, MIN_POSE_SPAN);
  const height = Math.max(bounds.maxY - bounds.minY, MIN_POSE_SPAN);
  const padding = Math.max(width, height) * PROJECTION_PADDING_RATIO;

  return {
    minX: centerX - width / 2 - padding,
    maxX: centerX + width / 2 + padding,
    minY: centerY - height / 2 - padding,
    maxY: centerY + height / 2 + padding,
  };
};

export const getStableProjectionBounds = (
  frames: SkeletonFrame[],
  orbit: OrbitState
): ProjectionBounds | null => {
  const rotatedPoints = frames.flatMap((sourceFrame) =>
    (Object.values(sourceFrame.joints).filter(Boolean) as SkeletonJoint[])
      .filter((joint) => typeof joint.visibility !== 'number' || joint.visibility >= 0.25)
      .map((joint) => rotatePoint(joint.position, orbit))
  );

  if (rotatedPoints.length < MIN_BOUND_SAMPLE_COUNT) {
    return null;
  }

  const xs = rotatedPoints.map((point) => point.x);
  const ys = rotatedPoints.map((point) => point.y);
  return expandBounds({
    minX: percentile(xs, 0.04),
    maxX: percentile(xs, 0.96),
    minY: percentile(ys, 0.04),
    maxY: percentile(ys, 0.96),
  });
};

export const projectJoints = (
  frame: SkeletonFrame,
  orbit: OrbitState,
  canvasSize: CanvasSize,
  stableBounds?: ProjectionBounds | null
): ProjectedJoint[] => {
  const rotated = (Object.values(frame.joints).filter(Boolean) as SkeletonJoint[]).map((joint) => ({
    ...joint,
    rotated: rotatePoint(joint.position, orbit),
  }));

  if (!rotated.length) {
    return [];
  }

  const fallbackBounds = expandBounds({
    minX: Math.min(...rotated.map((joint) => joint.rotated.x)),
    maxX: Math.max(...rotated.map((joint) => joint.rotated.x)),
    minY: Math.min(...rotated.map((joint) => joint.rotated.y)),
    maxY: Math.max(...rotated.map((joint) => joint.rotated.y)),
  });
  const bounds = stableBounds || fallbackBounds;
  const poseWidth = Math.max(bounds.maxX - bounds.minX, 0.001);
  const poseHeight = Math.max(bounds.maxY - bounds.minY, 0.001);
  const usableWidth = Math.max(canvasSize.width - 48, MIN_VIEW_SIZE);
  const usableHeight = Math.max(canvasSize.height - 48, MIN_VIEW_SIZE);
  const scale = Math.min(usableWidth / poseWidth, usableHeight / poseHeight);
  const centerX = canvasSize.width / 2;
  const centerY = canvasSize.height / 2;
  const poseCenterX = (bounds.minX + bounds.maxX) / 2;
  const poseCenterY = (bounds.minY + bounds.maxY) / 2;

  return rotated.map((joint) => ({
    ...joint,
    screenX: centerX + (joint.rotated.x - poseCenterX) * scale,
    screenY: centerY + (joint.rotated.y - poseCenterY) * scale,
    depth: joint.rotated.z,
  }));
};

function SkeletonProjection({
  frame,
  orbit,
  canvasSize,
  stableBounds,
}: {
  frame: SkeletonFrame | null;
  orbit: OrbitState;
  canvasSize: CanvasSize;
  stableBounds?: ProjectionBounds | null;
}) {
  const projectedJoints = useMemo(() => {
    if (!frame) {
      return [];
    }

    return projectJoints(frame, orbit, canvasSize, stableBounds);
  }, [canvasSize, frame, orbit, stableBounds]);

  const jointsByName = useMemo(() => {
    const map = new Map<SkeletonJointName, ProjectedJoint>();
    for (const joint of projectedJoints) {
      map.set(joint.name, joint);
    }
    return map;
  }, [projectedJoints]);

  if (!frame) {
    return <Text style={styles.emptyText}>No skeleton frames</Text>;
  }

  return (
    <View style={StyleSheet.absoluteFill}>
      {BONES.map(([fromName, toName]) => {
        const from = jointsByName.get(fromName);
        const to = jointsByName.get(toName);
        if (!from || !to) {
          return null;
        }

        const dx = to.screenX - from.screenX;
        const dy = to.screenY - from.screenY;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);
        const opacity = clamp(((from.visibility ?? 1) + (to.visibility ?? 1)) / 2, 0.25, 1);

        return (
          <View
            key={`${fromName}-${toName}`}
            style={[
              styles.bone,
              {
                left: from.screenX + dx / 2 - length / 2,
                top: from.screenY + dy / 2 - 2,
                width: length,
                opacity,
                transform: [{ rotateZ: `${angle}rad` }],
              },
            ]}
          />
        );
      })}

      {projectedJoints.map((joint) => (
        <View
          key={joint.name}
          style={[
            styles.joint,
            {
              left: joint.screenX - JOINT_SIZE / 2,
              top: joint.screenY - JOINT_SIZE / 2,
              opacity: clamp(joint.visibility ?? 1, 0.3, 1),
            },
          ]}
        />
      ))}
    </View>
  );
}

export default function Skeleton3DViewer({
  frames,
  fps = 30,
  loop = true,
  frame,
}: Skeleton3DViewerProps) {
  const [orbit, setOrbit] = useState<OrbitState>({ yaw: 0.55, pitch: 0.25 });
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [trackWidth, setTrackWidth] = useState(1);
  const [canvasSize, setCanvasSize] = useState<CanvasSize>({ width: 1, height: 1 });
  const orbitOnGestureStart = useRef(orbit);
  const lastTickMs = useRef<number | null>(null);
  const accumulatedMs = useRef(0);

  const playbackFrames = useMemo(() => {
    if (frames?.length) {
      return frames;
    }

    return frame ? [frame] : [];
  }, [frame, frames]);

  const frameCount = playbackFrames.length;
  const safeFps = normalizePlaybackFps(fps);
  const frameIntervalMs = 1000 / safeFps;
  const stableBounds = useMemo(
    () => getStableProjectionBounds(playbackFrames, orbit),
    [orbit, playbackFrames]
  );
  const currentFrame = playbackFrames[currentFrameIndex] ?? playbackFrames[0] ?? null;
  const timelineProgress = getTimelineProgress(currentFrameIndex, frameCount);

  useEffect(() => {
    setCurrentFrameIndex((index) => Math.min(index, Math.max(frameCount - 1, 0)));
    if (frameCount <= 1) {
      setIsPlaying(false);
    }
  }, [frameCount]);

  useEffect(() => {
    if (!isPlaying || frameCount <= 1) {
      lastTickMs.current = null;
      accumulatedMs.current = 0;
      return undefined;
    }

    let animationFrameId = 0;

    const tick = (nowMs: number) => {
      if (lastTickMs.current === null) {
        lastTickMs.current = nowMs;
      }

      accumulatedMs.current += nowMs - lastTickMs.current;
      lastTickMs.current = nowMs;

      if (accumulatedMs.current >= frameIntervalMs) {
        const stepCount = Math.floor(accumulatedMs.current / frameIntervalMs);
        accumulatedMs.current %= frameIntervalMs;

        setCurrentFrameIndex((index) => {
          const nextIndex = advanceFrameIndex(index, stepCount, frameCount, loop);
          if (!loop && nextIndex === frameCount - 1) {
            setIsPlaying(false);
          }
          return nextIndex;
        });
      }

      animationFrameId = requestAnimationFrame(tick);
    };

    animationFrameId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [frameCount, frameIntervalMs, isPlaying, loop]);

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: () => {
          orbitOnGestureStart.current = orbit;
        },
        onPanResponderMove: (_event, gesture) => {
          setOrbit({
            yaw: orbitOnGestureStart.current.yaw + gesture.dx * 0.01,
            pitch: clamp(orbitOnGestureStart.current.pitch + gesture.dy * 0.01, -1.1, 1.1),
          });
        },
      }),
    [orbit]
  );

  const scrubToLocation = useCallback((locationX: number) => {
    const progress = clamp(locationX / trackWidth, 0, 1);
    setCurrentFrameIndex(getFrameIndexFromProgress(progress, frameCount));
  }, [frameCount, trackWidth]);

  const scrubberPanResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => frameCount > 1,
        onMoveShouldSetPanResponder: () => frameCount > 1,
        onPanResponderGrant: (event) => {
          setIsPlaying(false);
          scrubToLocation((event as any).nativeEvent.locationX);
        },
        onPanResponderMove: (event) => {
          scrubToLocation((event as any).nativeEvent.locationX);
        },
      }),
    [frameCount, scrubToLocation]
  );

  const handleCanvasLayout = (event: any) => {
    const { width, height } = event.nativeEvent.layout;
    setCanvasSize({
      width: Math.max(width, MIN_VIEW_SIZE),
      height: Math.max(height, MIN_VIEW_SIZE),
    });
  };

  const togglePlayback = () => {
    if (frameCount <= 1) {
      return;
    }

    if (!loop && currentFrameIndex === frameCount - 1) {
      setCurrentFrameIndex(0);
    }

    setIsPlaying((playing) => !playing);
  };

  return (
    <View style={styles.container}>
      <View style={styles.canvasContainer} onLayout={handleCanvasLayout} {...panResponder.panHandlers}>
        <View style={styles.gridLineHorizontal} />
        <View style={styles.gridLineVertical} />
        <SkeletonProjection
          frame={currentFrame}
          orbit={orbit}
          canvasSize={canvasSize}
          stableBounds={stableBounds}
        />
      </View>

      <View style={styles.controls}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isPlaying ? 'Pause skeleton playback' : 'Play skeleton playback'}
          disabled={frameCount <= 1}
          onPress={togglePlayback}
          style={[styles.playButton, frameCount <= 1 && styles.disabledButton]}
        >
          <Text style={styles.playButtonText}>{isPlaying ? 'Pause' : 'Play'}</Text>
        </Pressable>

        <View
          style={styles.scrubber}
          onLayout={(event) => setTrackWidth(Math.max(event.nativeEvent.layout.width, 1))}
          {...scrubberPanResponder.panHandlers}
        >
          <View style={styles.scrubberTrack} />
          <View style={[styles.scrubberFill, { width: `${timelineProgress * 100}%` }]} />
          <View style={[styles.scrubberThumb, { left: `${timelineProgress * 100}%` }]} />
        </View>

        <Text style={styles.frameLabel}>
          {frameCount ? currentFrameIndex + 1 : 0}/{frameCount}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    backgroundColor: '#111214',
  },
  canvasContainer: {
    width: '100%',
    aspectRatio: 1,
    overflow: 'hidden',
    backgroundColor: '#111214',
  },
  gridLineHorizontal: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: '50%',
    height: 1,
    backgroundColor: '#24262b',
  },
  gridLineVertical: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: '50%',
    width: 1,
    backgroundColor: '#24262b',
  },
  emptyText: {
    marginTop: 24,
    color: '#c7c7cc',
    fontSize: 14,
    textAlign: 'center',
  },
  bone: {
    position: 'absolute',
    height: 4,
    borderRadius: 2,
    backgroundColor: '#f2f2f7',
  },
  joint: {
    position: 'absolute',
    width: JOINT_SIZE,
    height: JOINT_SIZE,
    borderRadius: JOINT_SIZE / 2,
    backgroundColor: '#34c759',
    borderWidth: 1,
    borderColor: '#d8ffe0',
  },
  controls: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#1c1c1e',
  },
  playButton: {
    minWidth: 64,
    minHeight: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    backgroundColor: '#34c759',
  },
  disabledButton: {
    opacity: 0.45,
  },
  playButtonText: {
    color: '#071108',
    fontSize: 14,
    fontWeight: '700',
  },
  scrubber: {
    flex: 1,
    height: 28,
    justifyContent: 'center',
  },
  scrubberTrack: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 12,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#3a3a3c',
  },
  scrubberFill: {
    height: 4,
    borderRadius: 2,
    backgroundColor: '#34c759',
  },
  scrubberThumb: {
    position: 'absolute',
    width: 14,
    height: 14,
    marginLeft: -7,
    borderRadius: 7,
    backgroundColor: '#f2f2f7',
  },
  frameLabel: {
    minWidth: 48,
    color: '#f2f2f7',
    fontSize: 12,
    textAlign: 'right',
  },
});
