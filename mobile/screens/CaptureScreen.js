import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Camera, CameraView } from 'expo-camera';
import { OnDeviceSwingAnalyzer } from '../services/analyzers/OnDeviceSwingAnalyzer';
import { ServerSwingAnalyzer, getConfiguredBackendUrl } from '../services/analyzers/ServerSwingAnalyzer';

const ANALYSIS_MODE = (process.env.EXPO_PUBLIC_ANALYSIS_MODE || 'server').toLowerCase();
const BALL_FLIGHT_CAPTURE_DURATION_SECONDS = 16;
const CAMERA_FACING_LABELS = {
  back: 'Back camera',
  front: 'Front camera',
};

const shouldUseServerFirst = () => ANALYSIS_MODE === 'server';

const getAnalysisModeLabel = () => {
  if (ANALYSIS_MODE === 'server') {
    return 'Real video: local MediaPipe backend';
  }

  if (ANALYSIS_MODE === 'mock') {
    return 'Mock on-device skeleton';
  }

  return 'Auto: on-device first, backend fallback';
};

export default function CaptureScreen({ navigation }) {
  const [hasPermission, setHasPermission] = useState(null);
  const [cameraFacing, setCameraFacing] = useState('back');
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [pendingVideoUri, setPendingVideoUri] = useState(null);
  const [fallbackMessage, setFallbackMessage] = useState(null);
  const [backendStatus, setBackendStatus] = useState(null);
  const cameraRef = useRef(null);
  const onDeviceAnalyzerRef = useRef(new OnDeviceSwingAnalyzer());
  const serverAnalyzerRef = useRef(new ServerSwingAnalyzer());
  const backendUrl = getConfiguredBackendUrl();
  const currentCameraLabel = CAMERA_FACING_LABELS[cameraFacing];
  const nextCameraFacing = cameraFacing === 'back' ? 'front' : 'back';
  const nextCameraLabel = CAMERA_FACING_LABELS[nextCameraFacing];
  const cameraControlsDisabled = isRecording || isAnalyzing;

  const buildCaptureMetadata = () => ({
    cameraAngle: 'down_the_line',
    cameraFacing,
  });

  useEffect(() => {
    Camera.requestCameraPermissionsAsync().then(({ status }) => {
      setHasPermission(status === 'granted');
    });
  }, []);

  const toggleCameraFacing = () => {
    if (cameraControlsDisabled) {
      return;
    }

    setCameraFacing((currentFacing) => (currentFacing === 'back' ? 'front' : 'back'));
  };

  const startRecording = async () => {
    if (cameraRef.current && !isRecording) {
      try {
        setIsRecording(true);
        const video = await cameraRef.current.recordAsync({ maxDuration: BALL_FLIGHT_CAPTURE_DURATION_SECONDS });
        setIsRecording(false);
        await analyzeOnDeviceFirst(video.uri);
      } catch (error) {
        setIsRecording(false);
        Alert.alert('Recording error', error.message);
      }
    }
  };

  const stopRecording = async () => {
    if (cameraRef.current && isRecording) {
      await cameraRef.current.stopRecording();
    }
  };

  const analyzeOnDeviceFirst = async (uri) => {
    setPendingVideoUri(null);
    setFallbackMessage(null);
    setIsAnalyzing(true);

    try {
      if (shouldUseServerFirst()) {
        if (!backendUrl) {
          setPendingVideoUri(uri);
          setFallbackMessage('Backend URL is not configured. Set EXPO_PUBLIC_BACKEND_URL in mobile/.env, restart Expo, then upload this swing.');
          return;
        }

        setPendingVideoUri(uri);
        setFallbackMessage('Real swing video is ready. Upload it to your local backend to build MediaPipe pose frames and the 3D skeleton.');
        return;
      }

      const onDeviceAnalyzer = onDeviceAnalyzerRef.current;
      const isAvailable = await onDeviceAnalyzer.isAvailable();

      if (!isAvailable) {
        setPendingVideoUri(uri);
        setFallbackMessage(
          'On-device pose analysis is not available in this build yet. You can opt in to upload this swing for server processing.'
        );
        return;
      }

      const result = await onDeviceAnalyzer.analyzeVideo({
        uri,
        metadata: buildCaptureMetadata(),
      });
      navigation.navigate('Results', { analysis: { ...result, localVideoUri: uri } });
    } catch (error) {
      setPendingVideoUri(uri);
      setFallbackMessage(error.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const checkBackendHealth = async () => {
    setBackendStatus('Checking backend...');

    try {
      await serverAnalyzerRef.current.checkHealth();
      setBackendStatus('Backend reachable');
    } catch (error) {
      setBackendStatus(error.message);
    }
  };

  const processOnServerWithConsent = async () => {
    if (!pendingVideoUri) {
      return;
    }

    setIsAnalyzing(true);
    setFallbackMessage(null);

    try {
      await serverAnalyzerRef.current.checkHealth();
      const result = await serverAnalyzerRef.current.analyzeVideo({
        uri: pendingVideoUri,
        metadata: buildCaptureMetadata(),
        userConsentedToUpload: true,
      });
      const localVideoUri = pendingVideoUri;
      setPendingVideoUri(null);
      navigation.navigate('Results', { analysis: { ...result, localVideoUri } });
    } catch (error) {
      Alert.alert('Server analysis failed', error.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (hasPermission === null) {
    return <View style={styles.container}><Text>Requesting camera permission...</Text></View>;
  }

  if (hasPermission === false) {
    return <View style={styles.container}><Text>No access to camera</Text></View>;
  }

  return (
    <View style={styles.container}>
      <CameraView
        key={cameraFacing}
        style={styles.camera}
        facing={cameraFacing}
        mode="video"
        mute={true}
        mirror={false}
        ref={cameraRef}
      />
      <View style={styles.instructions}>
        <Text style={styles.heading}>Swing capture</Text>
        <Text style={styles.text}>Position the camera directly behind the player and keep the full body visible.</Text>
        <Text style={styles.text}>Keep recording through impact and the first few seconds of ball flight.</Text>
        <View style={styles.statusPanel}>
          <Text style={styles.statusText}>Analysis: {getAnalysisModeLabel()}</Text>
          <Text style={styles.statusText}>Camera: {currentCameraLabel}</Text>
          <Text style={styles.statusText}>Backend: {backendUrl || 'Not configured'}</Text>
          {backendStatus ? <Text style={styles.statusText}>Status: {backendStatus}</Text> : null}
          <TouchableOpacity
            style={styles.statusButton}
            onPress={checkBackendHealth}
            disabled={isAnalyzing || !backendUrl}
          >
            <Text style={styles.statusButtonText}>Check Backend</Text>
          </TouchableOpacity>
        </View>
      </View>
      <View style={styles.controls}>
        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel={`Flip to ${nextCameraLabel.toLowerCase()}`}
          style={[styles.flipButton, cameraControlsDisabled && styles.buttonDisabled]}
          onPress={toggleCameraFacing}
          disabled={cameraControlsDisabled}
        >
          <Text style={styles.flipButtonText}>Flip to {nextCameraLabel}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.button, isRecording && styles.buttonStop]}
          onPress={isRecording ? stopRecording : startRecording}
          disabled={isAnalyzing}
        >
          <Text style={styles.buttonText}>{isRecording ? 'Stop' : 'Record'}</Text>
        </TouchableOpacity>
        {/* TODO: Add an import-video path with expo-image-picker or the platform media picker. */}
        {fallbackMessage && (
          <View style={styles.fallbackPanel}>
            <Text style={styles.fallbackText}>{fallbackMessage}</Text>
            <TouchableOpacity
              style={[styles.button, styles.serverButton]}
              onPress={processOnServerWithConsent}
              disabled={isAnalyzing}
            >
              <Text style={styles.buttonText}>Upload and Process</Text>
            </TouchableOpacity>
          </View>
        )}
        {isAnalyzing && <ActivityIndicator size="large" color="#007AFF" />}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  camera: {
    flex: 1,
  },
  instructions: {
    padding: 16,
    backgroundColor: '#fff',
  },
  heading: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 8,
  },
  text: {
    fontSize: 14,
    color: '#333',
  },
  statusPanel: {
    marginTop: 12,
    padding: 12,
    borderRadius: 8,
    backgroundColor: '#eef2f7',
  },
  statusText: {
    marginBottom: 6,
    fontSize: 13,
    color: '#253044',
  },
  statusButton: {
    minHeight: 34,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    backgroundColor: '#253044',
  },
  statusButtonText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '700',
  },
  controls: {
    padding: 20,
    backgroundColor: '#111',
    alignItems: 'center',
  },
  button: {
    width: 220,
    paddingVertical: 14,
    borderRadius: 30,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    marginBottom: 12,
  },
  flipButton: {
    width: 220,
    minHeight: 44,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 22,
    borderWidth: 1,
    borderColor: '#8ec5ff',
    marginBottom: 12,
  },
  flipButtonText: {
    color: '#8ec5ff',
    fontSize: 15,
    fontWeight: '700',
  },
  buttonDisabled: {
    opacity: 0.42,
  },
  buttonStop: {
    backgroundColor: '#FF3B30',
  },
  serverButton: {
    width: 240,
    backgroundColor: '#5856D6',
    marginTop: 12,
    marginBottom: 0,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  fallbackPanel: {
    width: '100%',
    maxWidth: 340,
    marginTop: 8,
    padding: 14,
    borderRadius: 8,
    backgroundColor: '#1c1c1e',
    alignItems: 'center',
  },
  fallbackText: {
    color: '#f2f2f7',
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
  },
});
