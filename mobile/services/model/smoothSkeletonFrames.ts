import type {
  SkeletonFrame,
  SkeletonJoint,
  SkeletonJointName,
  SkeletonPoint3D,
} from './createSkeletonFrame';

const WINDOW_RADIUS = 1;
const RAPID_MOTION_THRESHOLD = 0.15;
const RAPID_MOTION_BLEND = 0.35;

const distance = (a: SkeletonPoint3D, b: SkeletonPoint3D): number => {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  const dz = a.z - b.z;
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
};

const averagePoints = (points: SkeletonPoint3D[]): SkeletonPoint3D => {
  const total = points.reduce(
    (sum, point) => ({
      x: sum.x + point.x,
      y: sum.y + point.y,
      z: sum.z + point.z,
    }),
    { x: 0, y: 0, z: 0 }
  );

  return {
    x: total.x / points.length,
    y: total.y / points.length,
    z: total.z / points.length,
  };
};

const blendPoints = (
  current: SkeletonPoint3D,
  target: SkeletonPoint3D,
  blend: number
): SkeletonPoint3D => ({
  x: current.x + (target.x - current.x) * blend,
  y: current.y + (target.y - current.y) * blend,
  z: current.z + (target.z - current.z) * blend,
});

const averageVisibility = (joints: SkeletonJoint[]): number | undefined => {
  const values = joints
    .map((joint) => joint.visibility)
    .filter((value): value is number => typeof value === 'number');

  if (!values.length) {
    return undefined;
  }

  return values.reduce((sum, value) => sum + value, 0) / values.length;
};

const isRapidMotion = (
  previous: SkeletonJoint | undefined,
  current: SkeletonJoint,
  next: SkeletonJoint | undefined
): boolean => {
  const previousDelta = previous ? distance(previous.position, current.position) : 0;
  const nextDelta = next ? distance(current.position, next.position) : 0;
  return previousDelta > RAPID_MOTION_THRESHOLD || nextDelta > RAPID_MOTION_THRESHOLD;
};

export function smoothSkeletonFrames(frames: SkeletonFrame[]): SkeletonFrame[] {
  return frames.map((frame, frameIndex) => {
    const smoothedJoints = { ...frame.joints };
    const jointNames = Object.keys(frame.joints) as SkeletonJointName[];

    for (const jointName of jointNames) {
      const currentJoint = frame.joints[jointName];
      if (!currentJoint) {
        continue;
      }

      const neighboringJoints: SkeletonJoint[] = [];

      for (let offset = -WINDOW_RADIUS; offset <= WINDOW_RADIUS; offset += 1) {
        const neighborFrame = frames[frameIndex + offset];
        const neighborJoint = neighborFrame?.joints?.[jointName];
        if (neighborJoint) {
          neighboringJoints.push(neighborJoint);
        }
      }

      if (neighboringJoints.length <= 1) {
        continue;
      }

      const averagedPosition = averagePoints(neighboringJoints.map((joint) => joint.position));
      const previousJoint = frames[frameIndex - 1]?.joints?.[jointName];
      const nextJoint = frames[frameIndex + 1]?.joints?.[jointName];
      const blend = isRapidMotion(previousJoint, currentJoint, nextJoint)
        ? RAPID_MOTION_BLEND
        : 1;

      const visibility = averageVisibility(neighboringJoints);
      smoothedJoints[jointName] = {
        ...currentJoint,
        position: blendPoints(currentJoint.position, averagedPosition, blend),
        ...(typeof visibility === 'number' ? { visibility } : {}),
      };
    }

    return {
      ...frame,
      timestampMs: frame.timestampMs,
      joints: smoothedJoints,
    };
  });
}
