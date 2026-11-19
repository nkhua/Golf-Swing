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
  SwingTrackingSummary,
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
  trackingSummary?: SwingTrackingSummary;
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
const OVERLAY_SMOOTHING_RADIUS = 2;
const TRACKING_SMOOTHING_RADIUS = 1;
const POSE_SMOOTHING_MAX_DISTANCE_MS = 180;
const TRACKING_SMOOTHING_MAX_DISTANCE_MS = 160;
const BALL_SMOOTHING_MAX_DISTANCE_MS = 180;
const POSE_INTERPOLATION_MAX_GAP_MS = 900;
const TRACKING_INTERPOLATION_MAX_GAP_MS = 700;
const BALL_INTERPOLATION_MAX_GAP_MS = 450;

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const normalizeName = (name: string) => name.trim().toUpperCase();

const objectMetric = (value: unknown) =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};

const toFiniteNumber = (value: unknown) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : undefined;
};

const interpolateNumber = (from: number | undefined, to: number | undefined, progress: number) => {
  if (typeof from !== 'number') {
    return to;
  }
  if (typeof to !== 'number') {
    return from;
  }
  return from + (to - from) * progress;
};

const frameTime = (frame?: { timestampMs?: number }) => Number(frame?.timestampMs || 0);

const interpolationPair = <T extends { timestampMs: number }>(
  frames: T[],
  currentTimeMs: number,
  maxGapMs: number
) => {
  if (!frames.length) {
    return undefined;
  }

  const sortedFrames = [...frames].sort((a, b) => frameTime(a) - frameTime(b));
  if (currentTimeMs <= frameTime(sortedFrames[0])) {
    return { previous: sortedFrames[0], next: sortedFrames[0], progress: 0 };
  }

  const last = sortedFrames[sortedFrames.length - 1];
  if (currentTimeMs >= frameTime(last)) {
    return { previous: last, next: last, progress: 0 };
  }

  for (let index = 1; index < sortedFrames.length; index += 1) {
    const next = sortedFrames[index];
    const previous = sortedFrames[index - 1];
    const previousTime = frameTime(previous);
    const nextTime = frameTime(next);
    if (previousTime <= currentTimeMs && currentTimeMs <= nextTime) {
      const gapMs = nextTime - previousTime;
      if (gapMs <= 0 || gapMs > maxGapMs) {
        return undefined;
      }
      return {
        previous,
        next,
        progress: clamp((currentTimeMs - previousTime) / gapMs, 0, 1),
      };
    }
  }

  return undefined;
};

const nearestFrameWithin = <T extends { timestampMs: number }>(
  frames: T[],
  currentTimeMs: number,
  maxDistanceMs: number
) => {
  if (!frames.length) {
    return undefined;
  }
  const nearest = frames.reduce((best, frame) => {
    const bestDistance = Math.abs(frameTime(best) - currentTimeMs);
    const distance = Math.abs(frameTime(frame) - currentTimeMs);
    return distance < bestDistance ? frame : best;
  }, frames[0]);
  return Math.abs(frameTime(nearest) - currentTimeMs) <= maxDistanceMs ? nearest : undefined;
};

const smoothLandmarkCoordinate = (
  frames: FramePoseData[],
  frameIndex: number,
  name: string,
  key: 'x' | 'y' | 'z' | 'visibility',
  radius: number
) => {
  let weightedTotal = 0;
  let totalWeight = 0;
  const normalizedName = normalizeName(name);

  for (let index = Math.max(0, frameIndex - radius); index <= Math.min(frames.length - 1, frameIndex + radius); index += 1) {
    if (Math.abs(frameTime(frames[index]) - frameTime(frames[frameIndex])) > POSE_SMOOTHING_MAX_DISTANCE_MS) {
      continue;
    }
    const landmark = frames[index].landmarks.find((candidate) => normalizeName(candidate.name || '') === normalizedName);
    const value = landmark ? toFiniteNumber(landmark[key]) : undefined;
    if (value === undefined) {
      continue;
    }
    const distance = Math.abs(index - frameIndex);
    const visibility = key === 'visibility' ? 1 : clamp(Number(landmark?.visibility ?? 1), 0.15, 1);
    const weight = (radius + 1 - distance) * visibility;
    weightedTotal += value * weight;
    totalWeight += weight;
  }

  return totalWeight > 0 ? weightedTotal / totalWeight : undefined;
};

export const smoothPoseFramesForOverlay = (
  frames: FramePoseData[],
  radius = OVERLAY_SMOOTHING_RADIUS
): FramePoseData[] => {
  if (frames.length <= 2 || radius <= 0) {
    return frames;
  }

  return frames.map((frame, frameIndex) => ({
    ...frame,
    landmarks: frame.landmarks.map((landmark) => ({
      ...landmark,
      x: smoothLandmarkCoordinate(frames, frameIndex, landmark.name, 'x', radius) ?? landmark.x,
      y: smoothLandmarkCoordinate(frames, frameIndex, landmark.name, 'y', radius) ?? landmark.y,
      z: smoothLandmarkCoordinate(frames, frameIndex, landmark.name, 'z', radius) ?? landmark.z,
      visibility:
        smoothLandmarkCoordinate(frames, frameIndex, landmark.name, 'visibility', radius) ?? landmark.visibility,
    })),
  }));
};

const TRACKED_POINT_KEYS = [
  'leftWrist',
  'rightWrist',
  'leftElbow',
  'rightElbow',
  'leftShoulder',
  'rightShoulder',
  'leftHip',
  'rightHip',
  'leftHandWrist',
  'rightHandWrist',
  'leftIndexMcp',
  'rightIndexMcp',
  'leftMiddleMcp',
  'rightMiddleMcp',
  'leftPalmCenter',
  'rightPalmCenter',
  'leftEye',
  'rightEye',
  'nose',
  'chin',
  'headCenter',
  'grip',
  'clubHead',
] as const;

const TRACKED_LINE_KEYS = [
  'clubShaft',
  'shoulderLine',
  'hipLine',
  'spineLine',
  'leftForearmLine',
  'rightForearmLine',
  'eyeLine',
  'headDirection',
] as const;

const pointFromFrame = (frame: FrameTrackingData, key: string) =>
  (frame as unknown as Record<string, TrackedPoint | undefined>)[key];

const lineFromFrame = (frame: FrameTrackingData, key: string) =>
  (frame as unknown as Record<string, { start?: TrackedPoint; end?: TrackedPoint; confidence?: number } | undefined>)[key];

const smoothTrackedPoint = (
  frames: FrameTrackingData[],
  frameIndex: number,
  key: string,
  radius: number
): TrackedPoint | undefined => {
  const center = pointFromFrame(frames[frameIndex], key);
  if (!center) {
    return undefined;
  }

  let totalWeight = 0;
  let x = 0;
  let y = 0;
  let z = 0;
  let confidence = 0;
  let zWeight = 0;
  for (let index = Math.max(0, frameIndex - radius); index <= Math.min(frames.length - 1, frameIndex + radius); index += 1) {
    if (Math.abs(frameTime(frames[index]) - frameTime(frames[frameIndex])) > TRACKING_SMOOTHING_MAX_DISTANCE_MS) {
      continue;
    }
    const point = pointFromFrame(frames[index], key);
    if (!point) {
      continue;
    }
    const distance = Math.abs(index - frameIndex);
    const pointConfidence = clamp(Number(point.confidence ?? 0.5), 0.1, 1);
    const weight = (radius + 1 - distance) * pointConfidence;
    x += point.x * weight;
    y += point.y * weight;
    confidence += pointConfidence * weight;
    totalWeight += weight;
    if (typeof point.z === 'number') {
      z += point.z * weight;
      zWeight += weight;
    }
  }

  if (!totalWeight) {
    return center;
  }

  return {
    ...center,
    x: x / totalWeight,
    y: y / totalWeight,
    z: zWeight > 0 ? z / zWeight : center.z,
    confidence: clamp(confidence / totalWeight, 0, 1),
  };
};

const smoothTrackedLine = (
  frames: FrameTrackingData[],
  frameIndex: number,
  key: string,
  radius: number
) => {
  const line = lineFromFrame(frames[frameIndex], key);
  if (!line?.start || !line?.end) {
    return line;
  }

  const startSamples = frames.map((frame) => ({ ...frame, [key]: lineFromFrame(frame, key)?.start }));
  const endSamples = frames.map((frame) => ({ ...frame, [key]: lineFromFrame(frame, key)?.end }));
  const start = smoothTrackedPoint(startSamples as FrameTrackingData[], frameIndex, key, radius);
  const end = smoothTrackedPoint(endSamples as FrameTrackingData[], frameIndex, key, radius);
  return start && end
    ? {
        ...line,
        start,
        end,
        confidence: Math.min(start.confidence ?? 0, end.confidence ?? 0),
      }
    : line;
};

export const smoothTrackingFramesForOverlay = (
  frames: FrameTrackingData[],
  radius = TRACKING_SMOOTHING_RADIUS
): FrameTrackingData[] => {
  if (frames.length <= 2 || radius <= 0) {
    return frames;
  }

  return frames.map((frame, frameIndex) => {
    const nextFrame = { ...frame } as unknown as Record<string, unknown>;
    for (const key of TRACKED_POINT_KEYS) {
      nextFrame[key] = smoothTrackedPoint(frames, frameIndex, key, radius);
    }
    for (const key of TRACKED_LINE_KEYS) {
      nextFrame[key] = smoothTrackedLine(frames, frameIndex, key, radius);
    }
    return nextFrame as FrameTrackingData;
  });
};

const smoothBallPoint = (
  frames: FrameBallTrackingData[],
  frameIndex: number,
  radius: number
): TrackedPoint | undefined => {
  const center = frames[frameIndex].ball;
  if (!center) {
    return undefined;
  }

  let totalWeight = 0;
  let x = 0;
  let y = 0;
  let confidence = 0;
  for (let index = Math.max(0, frameIndex - radius); index <= Math.min(frames.length - 1, frameIndex + radius); index += 1) {
    if (Math.abs(frameTime(frames[index]) - frameTime(frames[frameIndex])) > BALL_SMOOTHING_MAX_DISTANCE_MS) {
      continue;
    }
    const point = frames[index].ball;
    if (!point) {
      continue;
    }
    const distance = Math.abs(index - frameIndex);
    const pointConfidence = clamp(Number(point.confidence ?? 0.5), 0.1, 1);
    const weight = (radius + 1 - distance) * pointConfidence;
    x += point.x * weight;
    y += point.y * weight;
    confidence += pointConfidence * weight;
    totalWeight += weight;
  }

  if (!totalWeight) {
    return center;
  }

  return {
    ...center,
    x: x / totalWeight,
    y: y / totalWeight,
    confidence: clamp(confidence / totalWeight, 0, 1),
  };
};

export const smoothBallTrackingFramesForOverlay = (
  frames: FrameBallTrackingData[],
  radius = 1
): FrameBallTrackingData[] => {
  if (frames.length <= 2 || radius <= 0) {
    return frames;
  }
  return frames.map((frame, frameIndex) => ({
    ...frame,
    ball: smoothBallPoint(frames, frameIndex, radius),
  }));
};

const interpolateTrackedPoint = (
  previous?: TrackedPoint,
  next?: TrackedPoint,
  progress = 0
): TrackedPoint | undefined => {
  if (!previous && !next) {
    return undefined;
  }
  if (!previous) {
    return next;
  }
  if (!next) {
    return previous;
  }

  return {
    ...next,
    x: interpolateNumber(previous.x, next.x, progress) ?? next.x,
    y: interpolateNumber(previous.y, next.y, progress) ?? next.y,
    z: interpolateNumber(previous.z, next.z, progress),
    confidence: interpolateNumber(previous.confidence, next.confidence, progress) ?? next.confidence,
  };
};

export const interpolatePoseFrame = (
  frames: FramePoseData[],
  currentTimeMs: number,
  maxGapMs = POSE_INTERPOLATION_MAX_GAP_MS
): FramePoseData | undefined => {
  const pair = interpolationPair(frames, currentTimeMs, maxGapMs);
  if (!pair) {
    return nearestFrameWithin(frames, currentTimeMs, maxGapMs / 2);
  }
  const { previous, next, progress } = pair;
  if (previous === next) {
    return previous;
  }

  const previousByName = new Map(previous.landmarks.map((landmark) => [normalizeName(landmark.name), landmark]));
  const nextByName = new Map(next.landmarks.map((landmark) => [normalizeName(landmark.name), landmark]));
  const names = new Set([...previousByName.keys(), ...nextByName.keys()]);
  const landmarks = Array.from(names).map((name) => {
    const from = previousByName.get(name);
    const to = nextByName.get(name);
    const source = to || from;
    if (!source) {
      return undefined;
    }
    return {
      ...source,
      name,
      x: interpolateNumber(from?.x, to?.x, progress) ?? source.x,
      y: interpolateNumber(from?.y, to?.y, progress) ?? source.y,
      z: interpolateNumber(from?.z, to?.z, progress),
      visibility: interpolateNumber(from?.visibility, to?.visibility, progress) ?? source.visibility,
    };
  }).filter(Boolean) as FramePoseData['landmarks'];

  return {
    ...next,
    frameIndex: progress < 0.5 ? previous.frameIndex : next.frameIndex,
    timestampMs: currentTimeMs,
    landmarks,
  };
};

export const interpolateTrackingFrame = (
  frames: FrameTrackingData[],
  currentTimeMs: number,
  maxGapMs = TRACKING_INTERPOLATION_MAX_GAP_MS
): FrameTrackingData | undefined => {
  const pair = interpolationPair(frames, currentTimeMs, maxGapMs);
  if (!pair) {
    return nearestFrameWithin(frames, currentTimeMs, maxGapMs / 2);
  }
  const { previous, next, progress } = pair;
  if (previous === next) {
    return previous;
  }

  const interpolated = {
    ...next,
    frameIndex: progress < 0.5 ? previous.frameIndex : next.frameIndex,
    timestampMs: currentTimeMs,
  } as unknown as Record<string, unknown>;
  for (const key of TRACKED_POINT_KEYS) {
    interpolated[key] = interpolateTrackedPoint(pointFromFrame(previous, key), pointFromFrame(next, key), progress);
  }
  for (const key of TRACKED_LINE_KEYS) {
    const previousLine = lineFromFrame(previous, key);
    const nextLine = lineFromFrame(next, key);
    const source = nextLine || previousLine;
    interpolated[key] = source
      ? {
          ...source,
          start: interpolateTrackedPoint(previousLine?.start, nextLine?.start, progress),
          end: interpolateTrackedPoint(previousLine?.end, nextLine?.end, progress),
          confidence: interpolateNumber(previousLine?.confidence, nextLine?.confidence, progress) ?? source.confidence,
        }
      : undefined;
  }
  return interpolated as FrameTrackingData;
};

export const interpolateBallTrackingFrame = (
  frames: FrameBallTrackingData[],
  currentTimeMs: number,
  maxGapMs = BALL_INTERPOLATION_MAX_GAP_MS
): FrameBallTrackingData | undefined => {
  const pair = interpolationPair(frames, currentTimeMs, maxGapMs);
  if (!pair) {
    return nearestFrameWithin(frames, currentTimeMs, maxGapMs / 2);
  }
  const { previous, next, progress } = pair;
  if (previous === next) {
    return previous;
  }
  return {
    ...next,
    frameIndex: progress < 0.5 ? previous.frameIndex : next.frameIndex,
    timestampMs: currentTimeMs,
    ball: interpolateTrackedPoint(previous.ball, next.ball, progress),
  };
};

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

export const getClubPathTrailFrames = (
  trackingFrames: FrameTrackingData[],
  currentTimeMs: number,
  trimStartMs = 0,
  maxFrames = 18
) =>
  trackingFrames
    .filter((frame) => {
      const timestampMs = Number(frame.timestampMs || 0);
      return timestampMs >= trimStartMs && timestampMs <= currentTimeMs + 140 && Boolean(frame.clubHead);
    })
    .slice(-maxFrames);

export const getCoachingMarkerPositionPercent = (
  painPoint: SwingCoachingPainPoint,
  trimStartMs: number,
  trimEndMs: number
) => {
  const durationMs = Math.max(trimEndMs - trimStartMs, 1);
  return clamp(((Number(painPoint.timestampMs || 0) - trimStartMs) / durationMs) * 100, 0, 100);
};

const formatCueTime = (timestampMs?: number) => {
  if (typeof timestampMs !== 'number') {
    return '0.0s';
  }

  return `${(timestampMs / 1000).toFixed(1)}s`;
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
  clubTrailFrames,
  ballTrackingFrame,
  ballTrailFrames,
  clubFaceEstimate,
  overlaySize,
}: {
  frame?: FramePoseData;
  trackingFrame?: FrameTrackingData;
  clubTrailFrames: FrameTrackingData[];
  ballTrackingFrame?: FrameBallTrackingData;
  ballTrailFrames: FrameBallTrackingData[];
  clubFaceEstimate?: Record<string, unknown>;
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
      <ClubPathOverlay trailFrames={clubTrailFrames} overlaySize={overlaySize} />
      <TrackingOverlay frame={trackingFrame} clubFaceEstimate={clubFaceEstimate} overlaySize={overlaySize} />
      <BallTrackingOverlay frame={ballTrackingFrame} trailFrames={ballTrailFrames} overlaySize={overlaySize} />
    </View>
  );
}

function TrackingOverlay({
  frame,
  clubFaceEstimate,
  overlaySize,
}: {
  frame?: FrameTrackingData;
  clubFaceEstimate?: Record<string, unknown>;
  overlaySize: OverlaySize;
}) {
  if (!frame || overlaySize.width <= 1 || overlaySize.height <= 1) {
    return null;
  }

  const shaftStart = frame.clubShaft?.start || frame.grip;
  const shaftEnd = frame.clubShaft?.end || frame.clubHead;
  const faceAngleDegrees = toFiniteNumber(clubFaceEstimate?.estimatedDegreesToTarget);

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
        <>
          <TrackingLine
            from={shaftStart}
            to={shaftEnd}
            overlaySize={overlaySize}
            variant="clubShaft"
            testID="tracking-overlay-club-shaft"
          />
          <ClubFaceMarker
            shaftStart={shaftStart}
            shaftEnd={shaftEnd}
            faceAngleDegrees={faceAngleDegrees}
            faceToTarget={String(clubFaceEstimate?.faceToTarget || 'unknown')}
            overlaySize={overlaySize}
          />
        </>
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

function ClubPathOverlay({
  trailFrames,
  overlaySize,
}: {
  trailFrames: FrameTrackingData[];
  overlaySize: OverlaySize;
}) {
  if (overlaySize.width <= 1 || overlaySize.height <= 1) {
    return null;
  }

  const visibleTrail = trailFrames.filter((trailFrame) => trailFrame.clubHead);
  if (visibleTrail.length < 2) {
    return null;
  }

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill} testID="club-path-overlay-layer">
      {visibleTrail.slice(1).map((trailFrame, index) => {
        const previous = visibleTrail[index];
        if (!previous.clubHead || !trailFrame.clubHead) {
          return null;
        }

        return (
          <TrackingLine
            key={`${previous.frameIndex}-${trailFrame.frameIndex}`}
            from={previous.clubHead}
            to={trailFrame.clubHead}
            overlaySize={overlaySize}
            variant="clubTrail"
            testID="club-path-overlay-trail"
          />
        );
      })}
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
  variant?: 'clubShaft' | 'eyeLine' | 'headDirection' | 'ballTrail' | 'clubTrail';
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
        : variant === 'clubTrail'
          ? styles.trackingClubTrail
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

function ClubFaceMarker({
  shaftStart,
  shaftEnd,
  faceAngleDegrees,
  faceToTarget,
  overlaySize,
}: {
  shaftStart: TrackedPoint;
  shaftEnd: TrackedPoint;
  faceAngleDegrees?: number;
  faceToTarget: string;
  overlaySize: OverlaySize;
}) {
  const centerX = shaftEnd.x * overlaySize.width;
  const centerY = shaftEnd.y * overlaySize.height;
  const shaftDx = shaftEnd.x * overlaySize.width - shaftStart.x * overlaySize.width;
  const shaftDy = shaftEnd.y * overlaySize.height - shaftStart.y * overlaySize.height;
  const shaftAngle = Math.atan2(shaftDy, shaftDx);
  const estimatedFaceOffset = clamp(faceAngleDegrees || 0, -14, 14) * (Math.PI / 180);
  const markerAngle = shaftAngle + Math.PI / 2 + estimatedFaceOffset;
  const length = clamp(Math.sqrt(shaftDx * shaftDx + shaftDy * shaftDy) * 0.28, 18, 44);
  const faceStyle =
    faceToTarget === 'open'
      ? styles.trackingClubFaceOpen
      : faceToTarget === 'closed'
        ? styles.trackingClubFaceClosed
        : styles.trackingClubFaceSquare;

  return (
    <View
      pointerEvents="none"
      testID="club-face-overlay-marker"
      style={[
        styles.trackingClubFaceMarker,
        faceStyle,
        {
          left: centerX - length / 2,
          top: centerY - 2,
          width: length,
          opacity: clamp(shaftEnd.confidence ?? 0, 0.3, 0.95),
          transform: [{ rotateZ: `${markerAngle}rad` }],
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
  trackingSummary,
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
  const smoothedPoseFrames = useMemo(() => smoothPoseFramesForOverlay(poseFrames), [poseFrames]);
  const smoothedTrackingFrames = useMemo(() => smoothTrackingFramesForOverlay(trackingFrames), [trackingFrames]);
  const smoothedBallTrackingFrames = useMemo(
    () => smoothBallTrackingFramesForOverlay(ballTrackingFrames),
    [ballTrackingFrames]
  );
  const currentFrameIndex = getNearestPoseFrameIndex(smoothedPoseFrames, currentTimeMs);
  const currentFrame = interpolatePoseFrame(smoothedPoseFrames, currentTimeMs);
  const visibleTrackingFrame = interpolateTrackingFrame(smoothedTrackingFrames, currentTimeMs);
  const visibleBallTrackingFrame = interpolateBallTrackingFrame(smoothedBallTrackingFrames, currentTimeMs);
  const ballTrailFrames = smoothedBallTrackingFrames
    .filter((frame) => frame.timestampMs <= currentTimeMs && frame.ball)
    .slice(-10);
  const clubTrailFrames = getClubPathTrailFrames(smoothedTrackingFrames, currentTimeMs, trimStartMs);
  const clubFaceEstimate = objectMetric(trackingSummary?.golfMetrics?.clubFaceEstimate);
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

  const seekToTimestamp = (timestampMs: number) => {
    const targetMs = clamp(timestampMs, trimStartMs, trimEndMs || timestampMs);
    player.currentTime = targetMs / 1000;
    setCurrentTimeMs(targetMs);
  };

  const timelineProgress = hasTrimWindow
    ? clamp(((currentTimeMs - trimStartMs) / Math.max(trimEndMs - trimStartMs, 1)) * 100, 0, 100)
    : 0;
  const sortedCoachingPainPoints = [...coachingPainPoints]
    .filter((painPoint) => typeof painPoint.timestampMs === 'number')
    .sort((a, b) => a.timestampMs - b.timestampMs);

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
          trackingFrame={visibleTrackingFrame}
          clubTrailFrames={clubTrailFrames}
          ballTrackingFrame={visibleBallTrackingFrame}
          ballTrailFrames={ballTrailFrames}
          clubFaceEstimate={clubFaceEstimate}
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
        <View style={styles.playbackRow}>
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

        {sortedCoachingPainPoints.length ? (
          <View style={styles.coachingTimeline} testID="coaching-timeline">
            <View style={styles.timelineTrack}>
              <View style={styles.timelineTrackBase} />
              <View style={[styles.timelineFill, { width: `${timelineProgress}%` }]} />
              {sortedCoachingPainPoints.map((painPoint, index) => {
                const isActive = activeCoachingPainPoint?.id === painPoint.id;
                const left = `${getCoachingMarkerPositionPercent(painPoint, trimStartMs, trimEndMs)}%` as `${number}%`;
                return (
                  <Pressable
                    key={painPoint.id || `${painPoint.title}-${index}`}
                    accessibilityRole="button"
                    accessibilityLabel={`Jump to ${painPoint.title} at ${formatCueTime(painPoint.timestampMs)}`}
                    onPress={() => seekToTimestamp(painPoint.timestampMs)}
                    style={[styles.timelineMarkerHitbox, { left }]}
                    testID="coaching-timeline-marker"
                  >
                    <View style={[styles.timelineMarker, isActive && styles.timelineMarkerActive]}>
                      <Text style={[styles.timelineMarkerText, isActive && styles.timelineMarkerTextActive]}>
                        {index + 1}
                      </Text>
                    </View>
                  </Pressable>
                );
              })}
            </View>
            <View style={styles.coachingMomentChips}>
              {sortedCoachingPainPoints.map((painPoint, index) => {
                const isActive = activeCoachingPainPoint?.id === painPoint.id;
                return (
                  <Pressable
                    key={`${painPoint.id || painPoint.title}-chip`}
                    accessibilityRole="button"
                    accessibilityLabel={`Show ${painPoint.title} at ${formatCueTime(painPoint.timestampMs)}`}
                    onPress={() => seekToTimestamp(painPoint.timestampMs)}
                    style={[styles.coachingMomentChip, isActive && styles.coachingMomentChipActive]}
                    testID="coaching-moment-chip"
                  >
                    <Text style={[styles.coachingMomentChipText, isActive && styles.coachingMomentChipTextActive]}>
                      {index + 1}. {formatCueTime(painPoint.timestampMs)}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
        ) : null}
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
    gap: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#1c1c1e',
  },
  playbackRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
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
  coachingTimeline: {
    gap: 9,
  },
  timelineTrack: {
    height: 28,
    justifyContent: 'center',
  },
  timelineTrackBase: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 12,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#3a3a3c',
  },
  timelineFill: {
    position: 'absolute',
    left: 0,
    top: 12,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#ffd60a',
  },
  trackingClubTrail: {
    position: 'absolute',
    height: 3,
    borderRadius: 2,
    backgroundColor: '#ff9f0a',
  },
  trackingClubFaceMarker: {
    position: 'absolute',
    height: 4,
    borderRadius: 2,
    borderWidth: 1,
  },
  trackingClubFaceOpen: {
    backgroundColor: '#64d2ff',
    borderColor: '#001f2d',
  },
  trackingClubFaceSquare: {
    backgroundColor: '#30d158',
    borderColor: '#04270c',
  },
  trackingClubFaceClosed: {
    backgroundColor: '#ff375f',
    borderColor: '#2d0009',
  },
  timelineMarkerHitbox: {
    position: 'absolute',
    top: 1,
    width: 28,
    height: 26,
    marginLeft: -14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  timelineMarker: {
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#3a3a3c',
    borderWidth: 2,
    borderColor: '#ffd60a',
  },
  timelineMarkerActive: {
    backgroundColor: '#ffd60a',
    borderColor: '#fff',
  },
  timelineMarkerText: {
    color: '#f2f2f7',
    fontSize: 11,
    fontWeight: '900',
  },
  timelineMarkerTextActive: {
    color: '#111214',
  },
  coachingMomentChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  coachingMomentChip: {
    minHeight: 30,
    justifyContent: 'center',
    borderRadius: 8,
    paddingHorizontal: 10,
    backgroundColor: '#2c2c2e',
    borderWidth: 1,
    borderColor: '#48484a',
  },
  coachingMomentChipActive: {
    backgroundColor: '#ffd60a',
    borderColor: '#fff',
  },
  coachingMomentChipText: {
    color: '#f2f2f7',
    fontSize: 12,
    fontWeight: '800',
  },
  coachingMomentChipTextActive: {
    color: '#111214',
  },
});
