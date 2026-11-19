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
    expect(onDevice.getByText('Impact frames sent to LLM: No')).toBeTruthy();
    expect(onDevice.getByText('Swing metrics sent to LLM: No')).toBeTruthy();
    expect(onDevice.getByText('LLM Swing Coach')).toBeTruthy();
    expect(onDevice.getAllByText('Handle is arriving behind the club head').length).toBeGreaterThan(0);
    expect(onDevice.getByText('Deterministic Swing Diagnosis')).toBeTruthy();
    expect(onDevice.getByText('LLM role: Wording Only')).toBeTruthy();
    expect(onDevice.getByText('Face-to-path is driving curve risk')).toBeTruthy();
    expect(onDevice.getByText('Expected vs Actual')).toBeTruthy();
    expect(onDevice.getByText('Training signal: Tracking Or Strike Uncertainty')).toBeTruthy();
    expect(onDevice.getByText('Expected curve: Draw')).toBeTruthy();
    expect(onDevice.getByText('Actual curve: Fade')).toBeTruthy();
    expect(onDevice.getByText('Curve agreement: Mismatch')).toBeTruthy();
    expect(onDevice.getByText('Swing Cut')).toBeTruthy();
    expect(onDevice.getByText('Body, Wrist, Eye, and Club Tracking')).toBeTruthy();
    expect(onDevice.getByText('Club frames: 4')).toBeTruthy();
    expect(onDevice.getByText('Avg left wrist angle: 145 deg')).toBeTruthy();
    expect(onDevice.getByText('Club face proxy: Estimated')).toBeTruthy();
    expect(onDevice.getByText('Face to target: Open')).toBeTruthy();
    expect(onDevice.getByText('Face to path: Closed')).toBeTruthy();
    expect(onDevice.getByText('Club path proxy: In To Out')).toBeTruthy();
    expect(onDevice.getByText('Launch Monitor Proxy')).toBeTruthy();
    expect(onDevice.getByText('Club speed: 73.4 mph')).toBeTruthy();
    expect(onDevice.getByText('Ball speed: 161.7 mph')).toBeTruthy();
    expect(onDevice.getByText('Spin rate: Unavailable')).toBeTruthy();
    expect(onDevice.getByText('Strike Point / Impact')).toBeTruthy();
    expect(onDevice.getByText('Club-ball proximity: 22.8 px')).toBeTruthy();
    expect(onDevice.getByText('Contact estimate: Likely Centered')).toBeTruthy();
    expect(onDevice.getByText('Visual impact LLM: Not Requested')).toBeTruthy();
    expect(onDevice.getByText('Estimated Ball Flight')).toBeTruthy();
    expect(onDevice.getByText('Visible ball frames: 6')).toBeTruthy();
    expect(onDevice.getByText('Actual shot shape: fade')).toBeTruthy();
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

  it('renders dry swing predictions and biomechanical fixes when no ball is validated', () => {
    const analysis = {
      ...createMockSwingAnalysisPayload('server'),
      ballFlightSummary: {
        status: 'no_ball_detected',
        framesTracked: 6,
        ballFrameCount: 0,
        ballCandidateFrameCount: 2,
        averageBallConfidence: 0,
        launchDirection: undefined,
        actualShotShape: 'unknown',
        confidence: 0,
        quality: {
          noBallDetected: true,
          needsRetake: false,
          retakeReasons: [],
        },
      },
      drySwing: {
        status: 'generated',
        mode: 'dry_swing',
        actualBallFlightAvailable: false,
        predictedBallFlight: {
          status: 'predicted_from_dry_swing',
          startDirection: 'right',
          curve: 'draw',
          contactRisk: 'scoop_or_thin_contact_risk',
          trajectory: 'high_or_weak',
          confidence: 0.46,
          evidence: ['face-to-target proxy is open', 'face-to-path proxy is closed'],
        },
        biomechanicalFindings: [
          {
            id: 'impact-handle-trails',
            category: 'impact',
            severity: 'high',
            phase: 'impact',
            timestampMs: 1420,
            endTimestampMs: 1420,
            title: 'Handle is trailing the club head at impact',
            evidence: 'Impact shaft lean proxy is -16 deg.',
            videoCue: 'At impact, compare the grip point to the club head.',
            likelyEffect: 'Adds loft and raises thin or weak-contact risk.',
            fix: 'Rehearse a flatter lead wrist and a handle that reaches the strike point first.',
            drill: 'Hit waist-high punch swings and freeze just after impact.',
            relatedMetrics: ['trackingSummary.golfMetrics.shaftLeanAtImpactDegrees'],
            confidence: 0.72,
          },
        ],
        practicePlan: [
          {
            priority: 1,
            title: 'Handle is trailing the club head at impact',
            phase: 'impact',
            drill: 'Hit waist-high punch swings and freeze just after impact.',
            checkpoint: 'At impact, compare the grip point to the club head.',
          },
        ],
        dataQuality: {
          confidence: 0.51,
          ballFlightStatus: 'no_ball_detected',
        },
        notes: 'Dry swing mode keeps predicted flight separate from actual shot-shape evidence.',
      },
      swingDiagnosis: {
        status: 'generated',
        analysisMode: 'dry_swing',
        llmRole: 'wording_only',
        summary: 'Top deterministic dry-swing priority is Handle is trailing the club head at impact.',
        priorities: [
          {
            id: 'impact-handle-trails',
            category: 'impact',
            severity: 'high',
            phase: 'impact',
            timestampMs: 1420,
            endTimestampMs: 1870,
            title: 'Handle is trailing the club head at impact',
            evidence: 'Impact shaft lean proxy is -16 deg.',
            videoCue: 'At impact, compare the grip point to the club head.',
            likelyEffect: 'Adds loft and raises thin or weak-contact risk.',
            recommendation: 'Rehearse a flatter lead wrist and a handle that reaches the strike point first.',
            drill: 'Hit waist-high punch swings and freeze just after impact.',
            relatedMetrics: ['trackingSummary.golfMetrics.shaftLeanAtImpactDegrees'],
            confidence: 0.72,
          },
        ],
        expectedActualComparison: {
          status: 'no_actual_ball',
          trainingSignal: 'prediction_only',
          expectedOutcome: {
            startDirection: 'unknown',
            curve: 'unknown',
            source: 'not_available_without_ball',
          },
          actualOutcome: {
            startDirection: null,
            curve: 'unknown',
            source: 'not_available',
          },
          agreement: {
            startDirection: 'unknown',
            curve: 'unknown',
            overall: 'unknown',
          },
          uncertaintyFlags: ['no_validated_ball_flight'],
          coachingInstruction: 'Use dry-swing biomechanics as a prediction only; do not claim the ball-flight result.',
          confidence: 0,
        },
        actualBallFlight: {
          status: 'not_available',
          launchDirection: null,
          actualShotShape: 'unknown',
          confidence: 0,
        },
        predictedBallFlight: {
          status: 'predicted_from_dry_swing',
          startDirection: 'right',
          curve: 'draw',
          confidence: 0.46,
        },
        dataQuality: {
          confidence: 0.51,
          ballFlightAvailable: false,
          priorityCount: 1,
        },
      },
      impactAnalysis: {
        status: 'not_available_no_validated_ball',
        modelVersion: 'impact-strike-v1',
        analysisMode: 'dry_swing_or_no_validated_ball',
        measurementSystem: 'not_recorded_without_validated_ball',
        impactTimestampMs: null,
        impactFrame: null,
        clubHeadAtImpact: null,
        ballPositionBeforeImpact: null,
        clubBallProximityPx: null,
        estimatedLowPoint: null,
        shaftLeanAtImpactDegrees: null,
        facePathProxy: null,
        contactQuality: {
          classification: 'not_recorded_no_ball',
          verticalStrike: 'not_recorded_no_ball',
          horizontalStrike: 'not_recorded_no_ball',
          confidence: 0,
          evidence: ['No validated ball track exists, so strike quality was intentionally not recorded.'],
        },
        visualImpactInference: {
          status: 'skipped_no_validated_ball',
          framesSent: 0,
        },
        dataQuality: {
          confidence: 0,
          ballFlightAvailable: false,
          ballFlightStatus: 'no_ball_detected',
        },
      },
    };

    const screen = render(<ResultsScreen route={{ params: { analysis } }} />);

    expect(screen.getByText('Deterministic Swing Diagnosis')).toBeTruthy();
    expect(screen.getByText('Mode: Dry Swing')).toBeTruthy();
    expect(screen.getByText('Dry Swing Mode')).toBeTruthy();
    expect(screen.getByText('Ball flight source: Predicted from biomechanics and club delivery')).toBeTruthy();
    expect(screen.getByText('Predicted start: Right')).toBeTruthy();
    expect(screen.getByText('Predicted curve: Draw')).toBeTruthy();
    expect(screen.getByText('Contact risk: Scoop Or Thin Contact Risk')).toBeTruthy();
    expect(screen.getByText('Contact estimate: Not Recorded No Ball')).toBeTruthy();
    expect(screen.getByText('Visual impact LLM: Skipped No Validated Ball')).toBeTruthy();
    expect(screen.getByText('Training signal: Prediction Only')).toBeTruthy();
    expect(screen.getAllByText('Handle is trailing the club head at impact').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Fix: Rehearse a flatter lead wrist and a handle that reaches the strike point first.').length).toBeGreaterThan(0);
  });
});
