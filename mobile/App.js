import React, { useState } from 'react';
import { StatusBar, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import CaptureScreen from './screens/CaptureScreen';
import ResultsScreen from './screens/ResultsScreen';

export default function App() {
  const [screen, setScreen] = useState('Capture');
  const [analysis, setAnalysis] = useState(null);

  const navigation = {
    navigate: (screenName, params = {}) => {
      if (screenName === 'Results') {
        setAnalysis(params.analysis ?? null);
        setScreen('Results');
      }

      if (screenName === 'Capture') {
        setScreen('Capture');
      }
    },
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.safeArea}>
        <StatusBar barStyle="light-content" />
        <View style={styles.header}>
          {screen === 'Results' ? (
            <TouchableOpacity
              accessibilityRole="button"
              accessibilityLabel="Back to camera"
              onPress={() => setScreen('Capture')}
              style={styles.backButton}
            >
              <Text style={styles.backButtonText}>Back</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.headerSpacer} />
          )}
          <Text style={styles.headerTitle}>{screen === 'Results' ? 'Analysis Results' : 'Capture Swing'}</Text>
          <View style={styles.headerSpacer} />
        </View>

        <View style={styles.content}>
          {screen === 'Results' ? (
            <ResultsScreen route={{ params: { analysis } }} />
          ) : (
            <CaptureScreen navigation={navigation} />
          )}
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#111',
  },
  header: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    backgroundColor: '#111',
  },
  headerTitle: {
    flex: 1,
    color: '#fff',
    fontSize: 17,
    fontWeight: '700',
    textAlign: 'center',
  },
  headerSpacer: {
    width: 64,
  },
  backButton: {
    width: 64,
    minHeight: 36,
    justifyContent: 'center',
  },
  backButtonText: {
    color: '#8ec5ff',
    fontSize: 16,
    fontWeight: '600',
  },
  content: {
    flex: 1,
  },
});
