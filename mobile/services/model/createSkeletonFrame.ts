export type MediaPipePoseLandmark = {
  name?: string;
  x: number;
  y: number;
  z?: number;
  visibility?: number;
};

export type SkeletonJointName =
  | 'pelvis_center'
  | 'chest_center'
  | 'head'
  | 'left_shoulder'
  | 'right_shoulder'
  | 'left_elbow'
  | 'right_elbow'
  | 'left_wrist'
  | 'right_wrist'
  | 'left_hip'
  | 'right_hip'
  | 'left_knee'
  | 'right_knee'
  | 'left_ankle'
  | 'right_ankle';

export type SkeletonPoint3D = {
  x: number;
  y: number;
  z: number;
};

export type SkeletonJoint = {
  name: SkeletonJointName;
  position: SkeletonPoint3D;
  visibility?: number;
};

export type SkeletonFrame = {
  frameIndex: number;
  timestampMs: number;
  joints: Record<SkeletonJointName, SkeletonJoint>;
};

const POSE_LANDMARK_INDEX = {
  NOSE: 0,
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
  LEFT_ELBOW: 13,
  RIGHT_ELBOW: 14,
  LEFT_WRIST: 15,
  RIGHT_WRIST: 16,
  LEFT_HIP: 23,
  RIGHT_HIP: 24,
  LEFT_KNEE: 25,
  RIGHT_KNEE: 26,
  LEFT_ANKLE: 27,
  RIGHT_ANKLE: 28,
} as const;

const REQUIRED_LANDMARK_COUNT = POSE_LANDMARK_INDEX.RIGHT_ANKLE + 1;

const toPoint = (landmark: MediaPipePoseLandmark): SkeletonPoint3D => ({
  x: landmark.x,
  y: landmark.y,
  z: landmark.z ?? 0,
});

const midpoint = (a: SkeletonPoint3D, b: SkeletonPoint3D): SkeletonPoint3D => ({
  x: (a.x + b.x) / 2,
  y: (a.y + b.y) / 2,
  z: (a.z + b.z) / 2,
});

const subtract = (point: SkeletonPoint3D, origin: SkeletonPoint3D): SkeletonPoint3D => ({
  x: point.x - origin.x,
  y: point.y - origin.y,
  z: point.z - origin.z,
});

const averageVisibility = (
  a?: number,
  b?: number
): number | undefined => {
  if (typeof a === 'number' && typeof b === 'number') {
    return (a + b) / 2;
  }

  return typeof a === 'number' ? a : b;
};

const createJoint = (
  name: SkeletonJointName,
  point: SkeletonPoint3D,
  origin: SkeletonPoint3D,
  visibility?: number
): SkeletonJoint => ({
  name,
  position: subtract(point, origin),
  ...(typeof visibility === 'number' ? { visibility } : {}),
});

const getLandmark = (
  landmarks: MediaPipePoseLandmark[],
  index: number
): MediaPipePoseLandmark => {
  const landmark = landmarks[index];
  if (!landmark) {
    throw new Error(`Missing MediaPipe pose landmark at index ${index}.`);
  }

  return landmark;
};

export function createSkeletonFrameFromPoseLandmarks(
  landmarks: MediaPipePoseLandmark[],
  frameIndex = 0,
  timestampMs = 0
): SkeletonFrame {
  if (landmarks.length < REQUIRED_LANDMARK_COUNT) {
    throw new Error(
      `Expected at least ${REQUIRED_LANDMARK_COUNT} MediaPipe pose landmarks, received ${landmarks.length}.`
    );
  }

  const nose = getLandmark(landmarks, POSE_LANDMARK_INDEX.NOSE);
  const leftShoulder = getLandmark(landmarks, POSE_LANDMARK_INDEX.LEFT_SHOULDER);
  const rightShoulder = getLandmark(landmarks, POSE_LANDMARK_INDEX.RIGHT_SHOULDER);
  const leftElbow = getLandmark(landmarks, POSE_LANDMARK_INDEX.LEFT_ELBOW);
  const rightElbow = getLandmark(landmarks, POSE_LANDMARK_INDEX.RIGHT_ELBOW);
  const leftWrist = getLandmark(landmarks, POSE_LANDMARK_INDEX.LEFT_WRIST);
  const rightWrist = getLandmark(landmarks, POSE_LANDMARK_INDEX.RIGHT_WRIST);
  const leftHip = getLandmark(landmarks, POSE_LANDMARK_INDEX.LEFT_HIP);
  const rightHip = getLandmark(landmarks, POSE_LANDMARK_INDEX.RIGHT_HIP);
  const leftKnee = getLandmark(landmarks, POSE_LANDMARK_INDEX.LEFT_KNEE);
  const rightKnee = getLandmark(landmarks, POSE_LANDMARK_INDEX.RIGHT_KNEE);
  const leftAnkle = getLandmark(landmarks, POSE_LANDMARK_INDEX.LEFT_ANKLE);
  const rightAnkle = getLandmark(landmarks, POSE_LANDMARK_INDEX.RIGHT_ANKLE);

  const leftHipPoint = toPoint(leftHip);
  const rightHipPoint = toPoint(rightHip);
  const leftShoulderPoint = toPoint(leftShoulder);
  const rightShoulderPoint = toPoint(rightShoulder);
  const pelvisCenter = midpoint(leftHipPoint, rightHipPoint);
  const chestCenter = midpoint(leftShoulderPoint, rightShoulderPoint);

  return {
    frameIndex,
    timestampMs,
    joints: {
      pelvis_center: createJoint(
        'pelvis_center',
        pelvisCenter,
        pelvisCenter,
        averageVisibility(leftHip.visibility, rightHip.visibility)
      ),
      chest_center: createJoint(
        'chest_center',
        chestCenter,
        pelvisCenter,
        averageVisibility(leftShoulder.visibility, rightShoulder.visibility)
      ),
      head: createJoint('head', toPoint(nose), pelvisCenter, nose.visibility),
      left_shoulder: createJoint('left_shoulder', leftShoulderPoint, pelvisCenter, leftShoulder.visibility),
      right_shoulder: createJoint('right_shoulder', rightShoulderPoint, pelvisCenter, rightShoulder.visibility),
      left_elbow: createJoint('left_elbow', toPoint(leftElbow), pelvisCenter, leftElbow.visibility),
      right_elbow: createJoint('right_elbow', toPoint(rightElbow), pelvisCenter, rightElbow.visibility),
      left_wrist: createJoint('left_wrist', toPoint(leftWrist), pelvisCenter, leftWrist.visibility),
      right_wrist: createJoint('right_wrist', toPoint(rightWrist), pelvisCenter, rightWrist.visibility),
      left_hip: createJoint('left_hip', leftHipPoint, pelvisCenter, leftHip.visibility),
      right_hip: createJoint('right_hip', rightHipPoint, pelvisCenter, rightHip.visibility),
      left_knee: createJoint('left_knee', toPoint(leftKnee), pelvisCenter, leftKnee.visibility),
      right_knee: createJoint('right_knee', toPoint(rightKnee), pelvisCenter, rightKnee.visibility),
      left_ankle: createJoint('left_ankle', toPoint(leftAnkle), pelvisCenter, leftAnkle.visibility),
      right_ankle: createJoint('right_ankle', toPoint(rightAnkle), pelvisCenter, rightAnkle.visibility),
    },
  };
}

const SKELETON_TO_NAMED_POSE_LANDMARK: Record<SkeletonJointName, string | [string, string]> = {
  pelvis_center: ['LEFT_HIP', 'RIGHT_HIP'],
  chest_center: ['LEFT_SHOULDER', 'RIGHT_SHOULDER'],
  head: 'NOSE',
  left_shoulder: 'LEFT_SHOULDER',
  right_shoulder: 'RIGHT_SHOULDER',
  left_elbow: 'LEFT_ELBOW',
  right_elbow: 'RIGHT_ELBOW',
  left_wrist: 'LEFT_WRIST',
  right_wrist: 'RIGHT_WRIST',
  left_hip: 'LEFT_HIP',
  right_hip: 'RIGHT_HIP',
  left_knee: 'LEFT_KNEE',
  right_knee: 'RIGHT_KNEE',
  left_ankle: 'LEFT_ANKLE',
  right_ankle: 'RIGHT_ANKLE',
};

const normalizeLandmarkName = (name: string) => name.trim().toUpperCase();

const getNamedLandmark = (
  landmarksByName: Map<string, MediaPipePoseLandmark>,
  name: string
): MediaPipePoseLandmark => {
  const landmark = landmarksByName.get(normalizeLandmarkName(name));
  if (!landmark) {
    throw new Error(`Missing named pose landmark ${name}.`);
  }

  return landmark;
};

export function createSkeletonFrameFromNamedPoseLandmarks(
  landmarks: MediaPipePoseLandmark[],
  frameIndex = 0,
  timestampMs = 0
): SkeletonFrame {
  const landmarksByName = new Map<string, MediaPipePoseLandmark>();

  for (const landmark of landmarks) {
    if (landmark.name) {
      landmarksByName.set(normalizeLandmarkName(landmark.name), landmark);
    }
  }

  const leftHip = getNamedLandmark(landmarksByName, 'LEFT_HIP');
  const rightHip = getNamedLandmark(landmarksByName, 'RIGHT_HIP');
  const pelvisCenter = midpoint(toPoint(leftHip), toPoint(rightHip));

  const joints = {} as Record<SkeletonJointName, SkeletonJoint>;

  for (const [jointName, poseName] of Object.entries(SKELETON_TO_NAMED_POSE_LANDMARK) as Array<
    [SkeletonJointName, string | [string, string]]
  >) {
    if (Array.isArray(poseName)) {
      const first = getNamedLandmark(landmarksByName, poseName[0]);
      const second = getNamedLandmark(landmarksByName, poseName[1]);
      joints[jointName] = createJoint(
        jointName,
        midpoint(toPoint(first), toPoint(second)),
        pelvisCenter,
        averageVisibility(first.visibility, second.visibility)
      );
      continue;
    }

    const landmark = getNamedLandmark(landmarksByName, poseName);
    joints[jointName] = createJoint(jointName, toPoint(landmark), pelvisCenter, landmark.visibility);
  }

  return {
    frameIndex,
    timestampMs,
    joints,
  };
}
