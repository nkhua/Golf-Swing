import React from 'react';
import { act } from 'react-test-renderer';
import { render, waitFor } from '@testing-library/react-native';
import CaptureScreen from '../screens/CaptureScreen';

jest.mock('expo-camera', () => {
  const React = require('react');
  const { View } = require('react-native');

  const CameraViewMock = React.forwardRef((props, ref) => <View {...props} ref={ref} testID="mock-camera" />);
  const CameraMock = {
    requestCameraPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
  };

  return {
    Camera: CameraMock,
    CameraView: CameraViewMock,
  };
});

describe('CaptureScreen', () => {
  it('renders instructions and record button after permission is granted', async () => {
    const navigation = { navigate: jest.fn() };
    const { getByText, queryByText } = render(<CaptureScreen navigation={navigation} />);

    await act(async () => {
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(getByText('Back-view swing capture')).toBeTruthy();
    });

    expect(getByText('Record')).toBeTruthy();
    expect(getByText('Keep recording through impact and the first few seconds of ball flight.')).toBeTruthy();
    expect(queryByText('Requesting camera permission...')).toBeNull();
  });
});
