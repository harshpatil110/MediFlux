/**
 * Deterministic replay helpers for animated CascadeTimeline execution (Task M8.2).
 */

import { CascadeStep } from './CascadeTimeline';

export type ReplaySpeed = '1x' | '2x' | '4x';

/**
 * Returns interval in milliseconds between tier steps for a given replay speed multiplier.
 * 1x: 1200ms
 * 2x: 600ms
 * 4x: 300ms
 */
export function getReplayIntervalMs(speed: ReplaySpeed): number {
  switch (speed) {
    case '4x':
      return 300;
    case '2x':
      return 600;
    case '1x':
    default:
      return 1200;
  }
}

/**
 * Computes visual display steps during replay based on active step index.
 * - idx < activeReplayIndex: Completed with recorded final state & reasoning
 * - idx === activeReplayIndex: Currently running state
 * - idx > activeReplayIndex: Pending / awaiting state
 * When not replaying, returns original stored steps unmodified.
 */
export function computeReplayDisplaySteps(
  storedSteps: CascadeStep[],
  activeReplayIndex: number,
  isReplaying: boolean
): CascadeStep[] {
  if (!storedSteps || storedSteps.length === 0) {
    return [];
  }

  if (!isReplaying) {
    return storedSteps;
  }

  return storedSteps.map((step, idx) => {
    if (idx < activeReplayIndex) {
      // Step already executed in replay: show recorded outcome
      const recordedState = step.state || (step.status === 'succeeded' ? 'completed' : (step.status as any)) || 'completed';
      return {
        ...step,
        state: recordedState,
        status: step.status || 'succeeded',
      };
    } else if (idx === activeReplayIndex) {
      // Current active step in replay: show running state
      return {
        ...step,
        state: 'running',
        status: 'running',
      };
    } else {
      // Future step in replay: show pending state
      return {
        ...step,
        state: 'pending',
        status: 'pending',
        reasoning: 'Awaiting upstream stage completion...',
        duration_ms: 0,
        total_tokens: 0,
      };
    }
  });
}
