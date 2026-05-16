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
    const leftElbow = poseFrame.landmarks.find((landmark) => landmark.name === 'LEFT_ELBOW');
    const rightElbow = poseFrame.landmarks.find((landmark) => landmark.name === 'RIGHT_ELBOW');
    const leftEye = poseFrame.landmarks.find((landmark) => landmark.name === 'NOSE');
    const rightEye = poseFrame.landmarks.find((landmark) => landmark.name === 'NOSE');
    const nose = poseFrame.landmarks.find((landmark) => landmark.name === 'NOSE');
    const trackedPoint = (landmark, source = 'pose_landmark', confidence = 0.92) => ({
      x: landmark.x,
      y: landmark.y,
      z: landmark.z,
      confidence,
      source,
    });
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
    const leftMiddleMcp = {
      x: leftWrist.x + 0.025,
      y: leftWrist.y - 0.025,
      z: leftWrist.z,
      confidence: 0.68,
      source: 'hand_landmark',
    };
    const rightMiddleMcp = {
      x: rightWrist.x - 0.025,
      y: rightWrist.y - 0.025,
      z: rightWrist.z,
      confidence: 0.68,
      source: 'hand_landmark',
    };
    const mockLeftEye = {
      x: nose.x - 0.035,
      y: nose.y + 0.005,
      z: nose.z,
      confidence: 0.7,
      source: 'pose_estimate',
    };
    const mockRightEye = {
      x: nose.x + 0.035,
      y: nose.y + 0.005,
      z: nose.z,
      confidence: 0.7,
      source: 'pose_estimate',
    };
    const headCenter = {
      x: (mockLeftEye.x + mockRightEye.x) / 2,
      y: (mockLeftEye.y + mockRightEye.y) / 2,
      z: nose.z,
      confidence: 0.7,
      source: 'pose_estimate',
    };
    const dx = clubHead.x - grip.x;
    const dy = clubHead.y - grip.y;
    const line = (start, end, source = end.source) => ({
      start,
      end,
      confidence: Math.min(start.confidence, end.confidence),
      angleDegrees: Math.atan2(end.y - start.y, end.x - start.x) * (180 / Math.PI),
      lengthPx: Math.sqrt((end.x - start.x) ** 2 + (end.y - start.y) ** 2) * 1080,
      source,
    });

    return {
      frameIndex: poseFrame.frameIndex,
      timestampMs: poseFrame.timestampMs,
      leftWrist: trackedPoint(leftWrist),
      rightWrist: trackedPoint(rightWrist),
      leftElbow: trackedPoint(leftElbow),
      rightElbow: trackedPoint(rightElbow),
      leftHandWrist: trackedPoint(leftWrist, 'hand_landmark', 0.68),
      rightHandWrist: trackedPoint(rightWrist, 'hand_landmark', 0.68),
      leftMiddleMcp,
      rightMiddleMcp,
      leftEye: mockLeftEye,
      rightEye: mockRightEye,
      nose: trackedPoint(nose, 'pose_estimate', 0.7),
      headCenter,
      grip,
      clubHead,
      clubShaft: line(grip, clubHead),
      leftForearmLine: line(trackedPoint(leftElbow), trackedPoint(leftWrist), 'pose_landmark'),
      rightForearmLine: line(trackedPoint(rightElbow), trackedPoint(rightWrist), 'pose_landmark'),
      eyeLine: line(mockLeftEye, mockRightEye, 'pose_estimate'),
      headDirection: line(headCenter, trackedPoint(nose, 'pose_estimate', 0.7), 'pose_estimate'),
      bodyMetrics: {
        spineAngleDegrees: 86,
        shoulderLineAngleDegrees: 2,
        hipLineAngleDegrees: 1,
      },
      handMetrics: {
        source: 'hand_landmark',
        leftWristAngleDegrees: 148 - index * 2,
        rightWristAngleDegrees: 143 - index * 2,
        handLandmarksDetected: true,
      },
      headMetrics: {
        source: 'pose_estimate',
        eyeLineAngleDegrees: 0,
        headDirectionAngleDegrees: 90,
        headTurnProxy: 0.02,
        eyesDownProxy: 0.2,
      },
      clubMetrics: {
        shaftAngleDegrees: Math.atan2(dy, dx) * (180 / Math.PI),
        shaftLeanFromVerticalDegrees: Math.atan2(dy, dx) * (180 / Math.PI) + 90,
        clubHeadConfidence: clubHead.confidence,
        clubDetectionSource: clubHead.source,
      },
      quality: {
        bodyDetected: true,
        handsDetected: true,
        faceDetected: false,
        headPoseEstimated: true,
        clubDetected: true,
      },
    };
  });
