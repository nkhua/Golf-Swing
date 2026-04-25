import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import CaptureScreen from './screens/CaptureScreen';
import ResultsScreen from './screens/ResultsScreen';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Capture">
        <Stack.Screen name="Capture" component={CaptureScreen} options={{ title: 'Capture Swing' }} />
        <Stack.Screen name="Results" component={ResultsScreen} options={{ title: 'Analysis Results' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
