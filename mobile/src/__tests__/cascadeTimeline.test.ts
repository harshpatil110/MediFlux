import {
  CascadeStep,
  CascadeTrace,
} from '../features/cascade/CascadeTimeline';
import {
  getReplayIntervalMs,
  computeReplayDisplaySteps,
  ReplaySpeed,
} from '../features/cascade/replayHelpers';

describe('CascadeTimeline State Modeling & Replay Mechanics', () => {
  const sampleSteps: CascadeStep[] = [
    {
      stage: 'supervisor',
      state: 'completed',
      status: 'succeeded',
      tier_label: 'CTRL',
      reasoning: 'Evaluated single-strip retail demand signal. Routing replenishment cascade.',
      duration_ms: 120,
      total_tokens: 340,
      structured_output: { routing_action: 'CASCADE_PROPAGATE' },
    },
    {
      stage: 'pharmacy',
      state: 'completed',
      status: 'succeeded',
      tier_label: 'T1',
      reasoning: 'Stock decremented to 14 strips. Reorder threshold 15 triggered.',
      duration_ms: 210,
      total_tokens: 420,
      structured_output: { reorder_needed: true, order_qty_strips: 10 },
    },
    {
      stage: 'stockist',
      state: 'waiting_approval',
      status: 'waiting_approval',
      tier_label: 'T2',
      reasoning: 'Cross-border stockist allocation requires human supervisor sign-off.',
      hitl_task_id: 'task-hitl-001',
      duration_ms: 0,
      total_tokens: 150,
    },
    {
      stage: 'distributor',
      state: 'skipped',
      status: 'skipped',
      tier_label: 'T3',
      skip_reason: 'Stockist fulfilled demand directly from local buffer stock.',
      reasoning: 'Upstream distributor bypassed per multi-echelon optimization.',
    },
    {
      stage: 'manufacturer',
      state: 'failed',
      status: 'failed',
      tier_label: 'T4',
      reasoning: 'API quota exceeded during production run dispatch.',
    },
  ];

  const sampleTrace: CascadeTrace = {
    correlation_id: 'corr-cascade-test-123',
    started_at: '2026-11-17T00:00:00Z',
    total_duration_ms: 480,
    total_tokens: 910,
    status: 'paused',
    steps: sampleSteps,
  };

  test('validates step states and attributes (done, waiting_approval, skipped, failed)', () => {
    // 1. Done step has reasoning, duration, tokens, and structured output
    const doneStep = sampleTrace.steps[0];
    expect(doneStep.state).toBe('completed');
    expect(doneStep.reasoning).toBeTruthy();
    expect(doneStep.duration_ms).toBeGreaterThan(0);
    expect(doneStep.total_tokens).toBeGreaterThan(0);
    expect(doneStep.structured_output).toEqual({ routing_action: 'CASCADE_PROPAGATE' });

    // 2. Waiting approval step has hitl_task_id for deep linking
    const waitingStep = sampleTrace.steps[2];
    expect(waitingStep.state).toBe('waiting_approval');
    expect(waitingStep.hitl_task_id).toBe('task-hitl-001');

    // 3. Skipped step contains supervisor skip_reason
    const skippedStep = sampleTrace.steps[3];
    expect(skippedStep.state).toBe('skipped');
    expect(skippedStep.skip_reason).toContain('buffer stock');

    // 4. Failed step records failure reasoning
    const failedStep = sampleTrace.steps[4];
    expect(failedStep.state).toBe('failed');
    expect(failedStep.reasoning).toContain('API quota exceeded');
  });

  test('getReplayIntervalMs calculates accurate delays for 1x, 2x, and 4x speeds', () => {
    expect(getReplayIntervalMs('1x')).toBe(1200);
    expect(getReplayIntervalMs('2x')).toBe(600);
    expect(getReplayIntervalMs('4x')).toBe(300);
    expect(getReplayIntervalMs('unknown' as ReplaySpeed)).toBe(1200);
  });

  test('computeReplayDisplaySteps progression accurately partitions executed, running, and pending steps', () => {
    // When isReplaying is false, returns original stored steps
    const staticSteps = computeReplayDisplaySteps(sampleSteps, 2, false);
    expect(staticSteps).toEqual(sampleSteps);

    // When isReplaying is true and activeReplayIndex is 1:
    // Index 0: executed (completed)
    // Index 1: active (running)
    // Index 2+: future (pending with placeholder text)
    const replaySteps = computeReplayDisplaySteps(sampleSteps, 1, true);
    expect(replaySteps.length).toBe(sampleSteps.length);

    expect(replaySteps[0].state).toBe('completed');
    expect(replaySteps[1].state).toBe('running');
    expect(replaySteps[1].status).toBe('running');

    expect(replaySteps[2].state).toBe('pending');
    expect(replaySteps[2].reasoning).toBe('Awaiting upstream stage completion...');
    expect(replaySteps[2].duration_ms).toBe(0);

    expect(replaySteps[3].state).toBe('pending');
    expect(replaySteps[4].state).toBe('pending');
  });

  test('computeReplayDisplaySteps handles edge cases (empty steps, index beyond length)', () => {
    expect(computeReplayDisplaySteps([], 0, true)).toEqual([]);

    // When replay reaches past final step, all steps are displayed with final recorded state
    const allCompleted = computeReplayDisplaySteps(sampleSteps, 10, true);
    expect(allCompleted.every((s) => s.state !== 'pending' && s.state !== 'running')).toBe(true);
  });
});

