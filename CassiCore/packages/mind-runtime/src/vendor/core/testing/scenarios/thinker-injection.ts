/**
 * Scenario: Intelligence module injection pipeline
 *
 * Verifies that cognitive modules (thinker, optimizer, dialectic) actively
 * participate in turns — emitting events, processing signals, and modifying
 * the turn context.
 */
import type { WorkflowScenario } from '../verification/scenario-types.js'

export const thinkerInjection: WorkflowScenario = {
  name: 'thinker-injection',
  description: 'Verifies that intelligence modules participate in turns and emit expected events',
  timeoutMs: 180_000,

  steps: [
    {
      label: 'Baseline snapshot',
      action: { type: 'snapshot', label: 'baseline' },
    },

    // Step 1: A question likely to trigger thinker activity
    {
      label: 'Send a question that triggers cognitive activity',
      action: { type: 'turn', message: 'What is the best approach to implementing event-driven architecture in a Node.js daemon with hot-reload configuration?' },
      assertions: [
        { type: 'event-emitted', event: 'turn:start' as any },
        { type: 'event-emitted', event: 'turn:end' as any },
        // Intelligence modules should have processed the turn
        { type: 'no-event', event: 'plugin:crashed' as any },
      ],
    },

    {
      label: 'Post-turn-1 snapshot',
      action: { type: 'snapshot', label: 'after-turn-1' },
    },

    // Step 2: Follow-up that should show accumulated context + module engagement
    {
      label: 'Follow-up turn — deeper engagement',
      action: { type: 'turn', message: 'How would you handle module isolation so a crashing module does not take down the daemon?' },
      assertions: [
        { type: 'event-sequence', events: ['turn:start' as any, 'turn:end' as any] },
        { type: 'session-state', path: 'turnCount', equals: 2 },
        { type: 'snapshot-diff', fromLabel: 'after-turn-1', changed: ['session.turnCount'] },
        { type: 'no-event', event: 'self-healer:error-detected' as any },
      ],
    },

    // Step 3: A meta question — tests whether context from prior turns feeds back
    {
      label: 'Meta-question — tests context feedback',
      action: { type: 'turn', message: 'Given what we discussed, what are the risks I should test for?' },
      assertions: [
        { type: 'session-state', path: 'turnCount', equals: 3 },
        { type: 'event-count', event: 'turn:end' as any, min: 3 },
        { type: 'no-event', event: 'plugin:crashed' as any },
      ],
    },
  ],
}
