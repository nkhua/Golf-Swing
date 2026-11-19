import React from 'react';
import { act, fireEvent, render } from '@testing-library/react-native';
import SwingVideoSkeletonOverlay, {
  getActiveCoachingPainPoint,
  getCoachingMarkerPositionPercent,
  getClubPathTrailFrames,
  getNearestBallTrackingFrameIndex,
  getNearestPoseFrameIndex,
  getNearestTrackingFrameIndex,
  getVideoAspectRatio,
  interpolatePoseFrame,
  interpolateTrackingFrame,
  smoothPoseFramesForOverlay,
  smoothTrackingFramesForOverlay,
} from '../components/SwingVideoSkeletonOverlay';
import { createMockBallTrackingFrames, createMockPoseFrames, createMockTrackingFrames } from '../services/model/mockPoseFrames';

let mockLastPlayer;
const mockUseVideoPlayer = jest.fn((source, setup) => {
  mockLastPlayer = {
    source,
    loop: false,
    muted: false,
    timeUpdateEventInterval: 0,
    playing: false,
    currentTime: 0,
    play: jest.fn(),
    pause: jest.fn(),
  };
  setup?.(mockLastPlayer);
  return mockLastPlayer;
});
const mockUseEvent = jest.fn((_player, _eventName, initialValue) => initialValue);
const mockUseEventListener = jest.fn();

const mockCoachingPainPoints = [
  {
    id: 'impact-shaft-lean',
    category: 'impact',
    severity: 'high',
    phase: 'impact',
    title: 'Handle trails at impact',
    evidence: 'Shaft lean is behind the ball.',
    videoCue: 'Watch the grip point behind the club head at impact.',
    timestampMs: 1420,
    endTimestampMs: 1750,
    recommendation: 'Move the handle ahead through impact.',
    drill: 'Half-swing punch shots.',
    relatedMetrics: ['shaftLeanAtImpactDegrees'],
    confidence: 0.79,
  },
];

jest.mock('expo', () => ({
  useEvent: (...args) => mockUseEvent(...args),
  useEventListener: (...args) => mockUseEventListener(...args),
}));

jest.mock('expo-video', () => {
  const React = require('react');
  const { View } = require('react-native');

  return {
    useVideoPlayer: (...args) => mockUseVideoPlayer(...args),
    VideoView: ({ player: _player, ...props }) => <View {...props} />,
  };
});

describe('SwingVideoSkeletonOverlay', () => {
  beforeEach(() => {
    mockUseVideoPlayer.mockClear();
    mockUseEvent.mockClear();
    mockUseEventListener.mockClear();
    mockLastPlayer = undefined;
  });

  it('maps video time and metadata to the closest pose frame', () => {
    const frames = createMockPoseFrames();

    expect(getNearestPoseFrameIndex(frames, 0)).toBe(0);
    expect(getNearestPoseFrameIndex(frames, 900)).toBe(2);
    expect(getNearestPoseFrameIndex(frames, 1400)).toBe(3);
    expect(getNearestPoseFrameIndex([], 1400)).toBe(0);
    expect(getNearestTrackingFrameIndex(createMockTrackingFrames(), 900)).toBe(2);
    expect(getNearestTrackingFrameIndex([], 900)).toBe(0);
    expect(getNearestBallTrackingFrameIndex(createMockBallTrackingFrames(), 1750)).toBe(2);
    expect(getNearestBallTrackingFrameIndex([], 1750)).toBe(0);
    expect(getClubPathTrailFrames(createMockTrackingFrames(), 1100, 0)).toHaveLength(3);
    expect(getActiveCoachingPainPoint(mockCoachingPainPoints, 1500)?.id).toBe('impact-shaft-lean');
    expect(getActiveCoachingPainPoint(mockCoachingPainPoints, 2500)).toBeUndefined();
    expect(getCoachingMarkerPositionPercent(mockCoachingPainPoints[0], 250, 5200)).toBeCloseTo(23.64);
    expect(getVideoAspectRatio({ width: 1080, height: 1920 })).toBeCloseTo(9 / 16);
    expect(getVideoAspectRatio({ width: 0, height: 0 })).toBeCloseTo(9 / 16);
  });

  it('smooths and interpolates overlay frames to reduce point jitter', () => {
    const jitteryPoseFrames = [
      {
        frameIndex: 0,
        timestampMs: 0,
        landmarks: [{ name: 'LEFT_WRIST', x: 0.4, y: 0.5, z: 0, visibility: 0.9 }],
      },
      {
        frameIndex: 1,
        timestampMs: 33,
        landmarks: [{ name: 'LEFT_WRIST', x: 0.8, y: 0.5, z: 0, visibility: 0.9 }],
      },
      {
        frameIndex: 2,
        timestampMs: 66,
        landmarks: [{ name: 'LEFT_WRIST', x: 0.42, y: 0.5, z: 0, visibility: 0.9 }],
      },
    ];
    const smoothedPoseFrames = smoothPoseFramesForOverlay(jitteryPoseFrames);
    const middleWrist = smoothedPoseFrames[1].landmarks.find((landmark) => landmark.name === 'LEFT_WRIST');
    expect(middleWrist.x).toBeLessThan(0.7);

    const interpolatedPose = interpolatePoseFrame(smoothedPoseFrames, 16);
    const wristAtHalfTime = interpolatedPose.landmarks.find((landmark) => landmark.name === 'LEFT_WRIST');
    expect(wristAtHalfTime.x).toBeGreaterThan(smoothedPoseFrames[0].landmarks[0].x);
    expect(wristAtHalfTime.x).toBeLessThan(smoothedPoseFrames[1].landmarks[0].x);

    const trackingFrames = [
      {
        frameIndex: 0,
        timestampMs: 0,
        clubHead: { x: 0.3, y: 0.7, confidence: 0.7, source: 'vision_line' },
      },
      {
        frameIndex: 1,
        timestampMs: 33,
        clubHead: { x: 0.9, y: 0.2, confidence: 0.7, source: 'vision_line' },
      },
      {
        frameIndex: 2,
        timestampMs: 66,
        clubHead: { x: 0.34, y: 0.68, confidence: 0.7, source: 'vision_line' },
      },
    ];
    const smoothedTrackingFrames = smoothTrackingFramesForOverlay(trackingFrames);
    expect(smoothedTrackingFrames[1].clubHead.x).toBeLessThan(0.76);
    expect(interpolateTrackingFrame(smoothedTrackingFrames, 16).clubHead.x).toBeGreaterThan(0.3);
  });

  it('renders video with a pose overlay and playback controls', () => {
    const screen = render(
      <SwingVideoSkeletonOverlay
        videoUri="file:///local-swing.mp4"
        poseFrames={createMockPoseFrames()}
        trackingFrames={createMockTrackingFrames()}
        ballTrackingFrames={createMockBallTrackingFrames()}
        coachingPainPoints={mockCoachingPainPoints}
        videoMetadata={{ fps: 60, width: 1080, height: 1920 }}
      />
    );

    fireEvent(screen.getByTestId('swing-video-overlay-stage'), 'layout', {
      nativeEvent: { layout: { width: 360, height: 640 } },
    });

    expect(screen.getByTestId('swing-video-view')).toBeTruthy();
    expect(screen.getByTestId('pose-overlay-layer')).toBeTruthy();
    expect(screen.getAllByTestId('pose-overlay-bone').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('pose-overlay-joint')).toHaveLength(13);
    expect(screen.getByTestId('tracking-overlay-layer')).toBeTruthy();
    expect(screen.getAllByTestId('tracking-overlay-wrist')).toHaveLength(2);
    expect(screen.getAllByTestId('tracking-overlay-hand')).toHaveLength(2);
    expect(screen.getAllByTestId('tracking-overlay-eye')).toHaveLength(2);
    expect(screen.getByTestId('tracking-overlay-eye-line')).toBeTruthy();
    expect(screen.getByTestId('tracking-overlay-head-direction')).toBeTruthy();
    expect(screen.getByTestId('tracking-overlay-grip')).toBeTruthy();
    expect(screen.getByTestId('tracking-overlay-club-head')).toBeTruthy();
    expect(screen.getByTestId('tracking-overlay-club-shaft')).toBeTruthy();
    expect(screen.getByTestId('club-face-overlay-marker')).toBeTruthy();

    const timeUpdate = mockUseEventListener.mock.calls.find((call) => call[1] === 'timeUpdate')[2];
    act(() => {
      timeUpdate({ currentTime: 1.6 });
    });
    expect(screen.getByTestId('club-path-overlay-layer')).toBeTruthy();
    expect(screen.getAllByTestId('club-path-overlay-trail').length).toBeGreaterThan(0);
    expect(screen.getByTestId('ball-tracking-overlay-layer')).toBeTruthy();
    expect(screen.getByTestId('ball-tracking-overlay-point')).toBeTruthy();
    expect(screen.getAllByTestId('ball-tracking-overlay-trail').length).toBeGreaterThan(0);
    expect(screen.getByTestId('coaching-video-cue')).toBeTruthy();
    expect(screen.getByText('Handle trails at impact')).toBeTruthy();
    expect(screen.getByTestId('coaching-timeline')).toBeTruthy();
    expect(screen.getAllByTestId('coaching-timeline-marker')).toHaveLength(1);
    expect(screen.getAllByTestId('coaching-moment-chip')).toHaveLength(1);

    expect(mockLastPlayer.source).toEqual({ uri: 'file:///local-swing.mp4' });
    expect(mockLastPlayer.loop).toBe(true);
    expect(mockLastPlayer.muted).toBe(true);
    expect(mockLastPlayer.timeUpdateEventInterval).toBeCloseTo(1 / 60);
    expect(mockUseEventListener).toHaveBeenCalledWith(
      mockLastPlayer,
      'timeUpdate',
      expect.any(Function)
    );

    fireEvent.press(screen.getByText('Play'));
    expect(mockLastPlayer.play).toHaveBeenCalledTimes(1);

    mockLastPlayer.currentTime = 1.2;
    fireEvent.press(screen.getByText('Restart'));
    expect(mockLastPlayer.currentTime).toBe(0);

    const playerBeforeSeek = mockLastPlayer;
    act(() => {
      fireEvent.press(screen.getByText('1. 1.4s'));
    });
    expect(playerBeforeSeek.currentTime).toBeCloseTo(1.42);
  });

  it('starts, restarts, and loops inside the detected swing window', () => {
    render(
      <SwingVideoSkeletonOverlay
        videoUri="file:///local-swing.mp4"
        poseFrames={createMockPoseFrames()}
        trackingFrames={createMockTrackingFrames()}
        videoMetadata={{ fps: 60, width: 1080, height: 1920, durationMs: 2200 }}
        swingWindow={{ startMs: 250, endMs: 1500 }}
      />
    );

    expect(mockLastPlayer.currentTime).toBeCloseTo(0.25);

    const timeUpdate = mockUseEventListener.mock.calls.find((call) => call[1] === 'timeUpdate')[2];
    act(() => {
      timeUpdate({ currentTime: 1.6 });
    });
    expect(mockLastPlayer.currentTime).toBeCloseTo(0.25);
  });
});
