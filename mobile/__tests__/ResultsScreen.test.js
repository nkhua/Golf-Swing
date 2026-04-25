import React from 'react';
import { render } from '@testing-library/react-native';
import ResultsScreen from '../screens/ResultsScreen';
import { createMockSwingAnalysisPayload } from '../services/analyzers/MockSwingAnalyzers';

describe('ResultsScreen', () => {
  it('renders on-device and server analysis payloads', () => {
    const onDevice = render(
      <ResultsScreen route={{ params: { analysis: createMockSwingAnalysisPayload('on_device') } }} />
    );
    expect(onDevice.getByText('Analyzer: On device')).toBeTruthy();
    expect(onDevice.getByText('Raw video uploaded: No')).toBeTruthy();

    const server = render(
      <ResultsScreen route={{ params: { analysis: createMockSwingAnalysisPayload('server') } }} />
    );
    expect(server.getByText('Analyzer: Server fallback')).toBeTruthy();
    expect(server.getByText('Raw video uploaded: Yes')).toBeTruthy();
  });
});
