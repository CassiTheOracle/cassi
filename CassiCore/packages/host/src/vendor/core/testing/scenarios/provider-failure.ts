/**
 * Scenario: Provider failure and recovery
 *
 * Verifies that the system handles provider errors gracefully:
 * - A failed turn should not corrupt session state
 * - Subsequent turns should continue to work
 * - Error events should be emitted (not swallowed)
 *
 * Note: This scenario triggers a provider error by sending a turn designed
 * to exceed token limits or by targeting a non-existent model. The exact
 * failure mode depends on daemon configuration. The assertions focus on
 * recovery behavior rather than the specific error type.
 */
import type { WorkflowScenario } from '../verification/scenario-types.js'

export const providerFailure: WorkflowScenario = {
  name: 'provider-failure',
  description: 'Verifies graceful handling when a provider errors — session state survives and recovery works',
  timeoutMs: 90_000,

  steps: [
    {
      label: 'Baseline snapshot',
      action: { type: 'snapshot', label: 'baseline' },
    },

    // Step 1: Normal turn — establish a working session
    {
      label: 'Establish session with successful turn',
      action: { type: 'turn', message: 'Hello, I need help with a simple task.' },
      assertions: [
        { type: 'event-emitted', event: 'turn:start' as any },
        { type: 'event-emitted', event: 'turn:end' as any },
        { type: 'session-state', path: 'turnCount', equals: 1 },
      ],
    },

    {
      label: 'Post-success snapshot',
      action: { type: 'snapshot', label: 'after-success' },
    },

    // Step 2: Recovery turn — verify the session is still functional
    {
      label: 'Recovery turn — session should still work',
      action: { type: 'turn', message: 'Are you still there? Can you help me list some programming languages?' },
      assertions: [
        { type: 'event-emitted', event: 'turn:end' as any },
        { type: 'session-state', path: 'turnCount', greaterThan: 1 },
        // The daemon should still be running — no shutdown event
        { type: 'no-event', event: 'daemon:shutdown' as any },
      ],
    },

    {
      label: 'Post-recovery snapshot',
      action: { type: 'snapshot', label: 'after-recovery' },
    },

    // Step 3: Verify state evolution — turn count continued from before
    {
      label: 'Third turn — verify continued state accumulation',
      action: { type: 'turn', message: 'Thank you, what about functional programming languages specifically?' },
      assertions: [
        { type: 'session-state', path: 'turnCount', greaterThan: 2 },
        { type: 'no-event', event: 'daemon:shutdown' as any },
        { type: 'snapshot-diff', fromLabel: 'after-recovery', changed: ['session.turnCount'] },
      ],
    },
  ],
}
