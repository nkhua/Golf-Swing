import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Camera, CameraView } from 'expo-camera';
import { OnDeviceSwingAnalyzer } from '../services/analyzers/OnDeviceSwingAnalyzer';
import { ServerSwingAnalyzer } from '../services/analyzers/ServerSwingAnalyzer';

export default function CaptureScreen({ navigation }) {
  const [hasPermission, setHasPermission] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [pendingVideoUri, setPendingVideoUri] = useState(null);
  const [fallbackMessage, setFallbackMessage] = useState(null);
  const cameraRef = useRef(null);
  const onDeviceAnalyzerRef = useRef(new OnDeviceSwingAnalyzer());
  const serverAnalyzerRef = useRef(new ServerSwingAnalyzer());

  useEffect(() => {
    Camera.requestCameraPermissionsAsync().then(({ status }) => {
      setHasPermission(status === 'granted');
    });
  }, []);

  const startRecording = async () => {
    if (cameraRef.current && !isRecording) {
      try {
        setIsRecording(true);
        const video = await cameraRef.current.recordAsync({ maxDuration: 10 });
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
        metadata: {
          cameraAngle: 'down_the_line',
        },
      });
      navigation.navigate('Results', { analysis: result });
    } catch (error) {
      setPendingVideoUri(uri);
      setFallbackMessage(error.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const processOnServerWithConsent = async () => {
    if (!pendingVideoUri) {
      return;
    }

    setIsAnalyzing(true);
    setFallbackMessage(null);

    try {
      const result = await serverAnalyzerRef.current.analyzeVideo({
        uri: pendingVideoUri,
        metadata: {
          cameraAngle: 'down_the_line',
        },
        userConsentedToUpload: true,
      });
      setPendingVideoUri(null);
      navigation.navigate('Results', { analysis: result });
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
        style={styles.camera}
        facing="back"
        mode="video"
        mute={true}
        ref={cameraRef}
      />
      <View style={styles.instructions}>
        <Text style={styles.heading}>Back-view swing capture</Text>
        <Text style={styles.text}>Position the camera directly behind the player and keep the full body visible.</Text>
      </View>
      <View style={styles.controls}>
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
