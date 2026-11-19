import React from 'react';
import { act } from 'react-test-renderer';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
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
    const { getByTestId, getByText, queryByText } = render(<CaptureScreen navigation={navigation} />);

    await act(async () => {
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(getByText('Swing capture')).toBeTruthy();
    });

    expect(getByTestId('mock-camera').props.facing).toBe('back');
    expect(getByTestId('mock-camera').props.mirror).toBe(false);
    expect(getByText('Record')).toBeTruthy();
    expect(getByText('Camera: Back camera')).toBeTruthy();
    expect(getByText('Flip to Front camera')).toBeTruthy();
    expect(getByText('Keep recording through impact and the first few seconds of ball flight.')).toBeTruthy();
    expect(queryByText('Requesting camera permission...')).toBeNull();
  });

  it('flips between back and front camera without mirroring the recorded video', async () => {
    const navigation = { navigate: jest.fn() };
    const { getByTestId, getByText } = render(<CaptureScreen navigation={navigation} />);

    await act(async () => {
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(getByText('Camera: Back camera')).toBeTruthy();
    });

    fireEvent.press(getByText('Flip to Front camera'));

    expect(getByTestId('mock-camera').props.facing).toBe('front');
    expect(getByTestId('mock-camera').props.mirror).toBe(false);
    expect(getByText('Camera: Front camera')).toBeTruthy();
    expect(getByText('Flip to Back camera')).toBeTruthy();

    fireEvent.press(getByText('Flip to Back camera'));

    expect(getByTestId('mock-camera').props.facing).toBe('back');
    expect(getByTestId('mock-camera').props.mirror).toBe(false);
    expect(getByText('Camera: Back camera')).toBeTruthy();
  });
});
