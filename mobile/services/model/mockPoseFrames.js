const BASE_LANDMARKS = {
  NOSE: { x: 0.5, y: 0.19, z: -0.08 },
  LEFT_SHOULDER: { x: 0.42, y: 0.32, z: -0.03 },
  RIGHT_SHOULDER: { x: 0.58, y: 0.32, z: -0.02 },
  LEFT_ELBOW: { x: 0.36, y: 0.43, z: -0.04 },
  RIGHT_ELBOW: { x: 0.64, y: 0.43, z: -0.03 },
  LEFT_WRIST: { x: 0.31, y: 0.54, z: -0.04 },
  RIGHT_WRIST: { x: 0.69, y: 0.54, z: -0.03 },
  LEFT_HIP: { x: 0.44, y: 0.56, z: 0 },
  RIGHT_HIP: { x: 0.56, y: 0.56, z: 0.01 },
  LEFT_KNEE: { x: 0.42, y: 0.73, z: 0.02 },
  RIGHT_KNEE: { x: 0.58, y: 0.73, z: 0.03 },
  LEFT_ANKLE: { x: 0.41, y: 0.91, z: 0.04 },
  RIGHT_ANKLE: { x: 0.59, y: 0.91, z: 0.04 },
};

const toLandmarks = (offset) =>
  Object.entries(BASE_LANDMARKS).map(([name, landmark]) => ({
    name,
    x: landmark.x + offset.x,
    y: landmark.y + offset.y,
    z: landmark.z + offset.z,
    visibility: 0.92,
  }));

export const createMockPoseFrames = () => [
  {
    frameIndex: 0,
    timestampMs: 0,
    landmarks: toLandmarks({ x: 0, y: 0, z: 0 }),
  },
  {
    frameIndex: 1,
    timestampMs: 550,
    landmarks: toLandmarks({ x: -0.015, y: -0.025, z: 0.02 }),
  },
  {
    frameIndex: 2,
    timestampMs: 1050,
    landmarks: toLandmarks({ x: 0.02, y: -0.015, z: -0.015 }),
  },
  {
    frameIndex: 3,
    timestampMs: 1420,
    landmarks: toLandmarks({ x: 0.01, y: 0.018, z: 0.01 }),
  },
];

export const createMockTrackingFrames = () =>
  createMockPoseFrames().map((poseFrame, index) => {
    const leftWrist = poseFrame.landmarks.find((landmark) => landmark.name === 'LEFT_WRIST');
    const rightWrist = poseFrame.landmarks.find((landmark) => landmark.name === 'RIGHT_WRIST');
    const grip = {
      x: (leftWrist.x + rightWrist.x) / 2,
      y: (leftWrist.y + rightWrist.y) / 2,
      z: (leftWrist.z + rightWrist.z) / 2,
      confidence: 0.92,
      source: 'pose_midpoint',
    };
    const clubHead = {
      x: Math.min(0.96, grip.x + 0.14 + index * 0.035),
      y: Math.max(0.05, grip.y - 0.18 - index * 0.025),
      confidence: 0.72,
      source: index === 2 ? 'temporal_prediction' : 'vision_line',
    };
    const dx = clubHead.x - grip.x;
    const dy = clubHead.y - grip.y;

    return {
      frameIndex: poseFrame.frameIndex,
      timestampMs: poseFrame.timestampMs,
      leftWrist: {
        x: leftWrist.x,
        y: leftWrist.y,
        z: leftWrist.z,
        confidence: 0.92,
        source: 'pose_landmark',
      },
      rightWrist: {
        x: rightWrist.x,
        y: rightWrist.y,
        z: rightWrist.z,
        confidence: 0.92,
        source: 'pose_landmark',
      },
      grip,
      clubHead,
      clubShaft: {
        start: grip,
        end: clubHead,
        confidence: Math.min(grip.confidence, clubHead.confidence),
        angleDegrees: Math.atan2(dy, dx) * (180 / Math.PI),
        lengthPx: Math.sqrt(dx * dx + dy * dy) * 1080,
        source: clubHead.source,
      },
    };
  });
