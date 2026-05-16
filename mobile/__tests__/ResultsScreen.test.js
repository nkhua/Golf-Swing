import React from 'react';
import { render } from '@testing-library/react-native';
import ResultsScreen from '../screens/ResultsScreen';
import { createMockSwingAnalysisPayload } from '../services/analyzers/MockSwingAnalyzers';

jest.mock('../components/Skeleton3DViewer', () => {
  const { Text } = require('react-native');
  return function MockSkeleton3DViewer() {
    return <Text>Mock 3D skeleton viewer</Text>;
  };
});

jest.mock('../components/SwingVideoSkeletonOverlay', () => {
  const { Text } = require('react-native');
  return function MockSwingVideoSkeletonOverlay() {
    return <Text>Mock video skeleton overlay</Text>;
  };
});

describe('ResultsScreen', () => {
  it('renders on-device and server analysis payloads', () => {
    const onDevice = render(
      <ResultsScreen route={{ params: { analysis: createMockSwingAnalysisPayload('on_device') } }} />
    );
    expect(onDevice.getByText('Analyzer: On device')).toBeTruthy();
    expect(onDevice.getByText('Raw video uploaded: No')).toBeTruthy();
    expect(onDevice.getByText('Frames sent to LLM: No')).toBeTruthy();
    expect(onDevice.getByText('Swing metrics sent to LLM: No')).toBeTruthy();
    expect(onDevice.getByText('LLM Swing Coach')).toBeTruthy();
    expect(onDevice.getByText('Handle is arriving behind the club head')).toBeTruthy();
    expect(onDevice.getByText('Swing Cut')).toBeTruthy();
    expect(onDevice.getByText('Body, Wrist, Eye, and Club Tracking')).toBeTruthy();
    expect(onDevice.getByText('Club frames: 4')).toBeTruthy();
    expect(onDevice.getByText('Avg left wrist angle: 145 deg')).toBeTruthy();
    expect(onDevice.getByText('Estimated Ball Flight')).toBeTruthy();
    expect(onDevice.getByText('Visible ball frames: 6')).toBeTruthy();
    expect(onDevice.getByText('Max ball speed: 1410 px/s')).toBeTruthy();

    const server = render(
      <ResultsScreen route={{ params: { analysis: createMockSwingAnalysisPayload('server') } }} />
    );
    expect(server.getByText('Analyzer: Server fallback')).toBeTruthy();
    expect(server.getByText('Raw video uploaded: Yes')).toBeTruthy();
  });

  it('renders the skeleton viewer when pose landmarks can build a skeleton', () => {
    const screen = render(
      <ResultsScreen route={{ params: { analysis: createMockSwingAnalysisPayload('on_device') } }} />
    );

    expect(screen.getByText('3D Skeleton')).toBeTruthy();
    expect(screen.getByText('Mock 3D skeleton viewer')).toBeTruthy();
  });

  it('renders a video overlay when a captured local video uri is available', () => {
    const analysis = {
      ...createMockSwingAnalysisPayload('server'),
      localVideoUri: 'file:///local-swing.mp4',
    };
    const screen = render(<ResultsScreen route={{ params: { analysis } }} />);

    expect(screen.getByText('Video Skeleton Overlay')).toBeTruthy();
    expect(screen.getByText('Mock video skeleton overlay')).toBeTruthy();
  });
});
