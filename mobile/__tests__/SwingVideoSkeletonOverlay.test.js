import React from 'react';
import { act, fireEvent, render } from '@testing-library/react-native';
import SwingVideoSkeletonOverlay, {
  getNearestPoseFrameIndex,
  getNearestTrackingFrameIndex,
  getVideoAspectRatio,
} from '../components/SwingVideoSkeletonOverlay';
import { createMockPoseFrames, createMockTrackingFrames } from '../services/model/mockPoseFrames';

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
    expect(getVideoAspectRatio({ width: 1080, height: 1920 })).toBeCloseTo(9 / 16);
    expect(getVideoAspectRatio({ width: 0, height: 0 })).toBeCloseTo(9 / 16);
  });

  it('renders video with a pose overlay and playback controls', () => {
    const screen = render(
      <SwingVideoSkeletonOverlay
        videoUri="file:///local-swing.mp4"
        poseFrames={createMockPoseFrames()}
        trackingFrames={createMockTrackingFrames()}
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
    expect(screen.getByTestId('tracking-overlay-grip')).toBeTruthy();
    expect(screen.getByTestId('tracking-overlay-club-head')).toBeTruthy();
    expect(screen.getByTestId('tracking-overlay-club-shaft')).toBeTruthy();
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
