/**
 * Scenario: Multi-turn context persistence
 *
 * Verifies that session state accumulates correctly across multiple turns
 * and that no crash events are emitted during normal operation.
 */
import type { WorkflowScenario } from '../verification/scenario-types.js'

export const multiTurnContext: WorkflowScenario = {
  name: 'multi-turn-context',
  description: 'Verifies context persistence and session state accumulation across multiple turns',
  timeoutMs: 60_000,

  steps: [
    // Step 0: Take a baseline snapshot
    {
      label: 'Baseline snapshot',
      action: { type: 'snapshot', label: 'baseline' },
    },

    // Step 1: First turn — establish context
    {
      label: 'First turn — establish context',
      action: { type: 'turn', message: 'I am working on a TypeScript project called CassiCore. It uses ES modules and vitest for testing.' },
      assertions: [
        { type: 'event-emitted', event: 'turn:start' as any },
        { type: 'event-emitted', event: 'turn:end' as any },
        { type: 'session-state', path: 'turnCount', equals: 1 },
        { type: 'no-event', event: 'plugin:crashed' as any },
      ],
    },

    // Step 2: Take a post-first-turn snapshot
    {
      label: 'Post-turn-1 snapshot',
      action: { type: 'snapshot', label: 'after-turn-1' },
    },

    // Step 3: Second turn — reference prior context
    {
      label: 'Second turn — reference prior context',
      action: { type: 'turn', message: 'What testing framework does my project use?' },
      assertions: [
        { type: 'event-sequence', events: ['turn:start' as any, 'turn:end' as any] },
        { type: 'session-state', path: 'turnCount', equals: 2 },
        { type: 'session-state', path: 'messageCount', greaterThan: 2 },
        { type: 'snapshot-diff', fromLabel: 'after-turn-1', changed: ['session.turnCount', 'session.messageCount'] },
      ],
    },

    // Step 4: Third turn — continued conversation
    {
      label: 'Third turn — continued conversation',
      action: { type: 'turn', message: 'Summarize what we have discussed so far.' },
      assertions: [
        { type: 'session-state', path: 'turnCount', equals: 3 },
        { type: 'no-event', event: 'plugin:crashed' as any },
        { type: 'no-event', event: 'self-healer:error-detected' as any },
        { type: 'event-count', event: 'turn:start' as any, min: 3 },
        { type: 'event-count', event: 'turn:end' as any, min: 3 },
      ],
    },
  ],
}
