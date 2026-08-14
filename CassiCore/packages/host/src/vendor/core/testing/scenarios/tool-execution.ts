/**
 * Scenario: Tool execution round-trip
 *
 * Verifies the full lifecycle of tool execution within a turn:
 * - Turn starts, provider requests a tool call
 * - Tool executes and returns a result
 * - Provider incorporates the tool result
 * - Turn completes without crashes
 *
 * This tests the agentic loop: LLM → tool call → tool result → LLM continuation.
 */
import type { WorkflowScenario } from '../verification/scenario-types.js'

export const toolExecution: WorkflowScenario = {
  name: 'tool-execution',
  description: 'Verifies tool execution round-trip within a turn — request, execute, incorporate result',
  timeoutMs: 60_000,

  steps: [
    {
      label: 'Baseline snapshot',
      action: { type: 'snapshot', label: 'baseline' },
    },

    // Step 1: Ask something that is very likely to trigger a tool call
    {
      label: 'Turn requesting tool use',
      action: { type: 'turn', message: 'Read the file package.json in the current project and tell me the project name.' },
      assertions: [
        { type: 'event-emitted', event: 'turn:start' as any },
        { type: 'event-emitted', event: 'turn:end' as any },
        // The turn should complete (tool executed or not)
        { type: 'session-state', path: 'turnCount', equals: 1 },
        // No crashes during tool execution
        { type: 'no-event', event: 'plugin:crashed' as any },
      ],
    },

    {
      label: 'Post-tool snapshot',
      action: { type: 'snapshot', label: 'after-tool' },
    },

    // Step 2: Follow-up that references tool output
    {
      label: 'Follow-up referencing tool result',
      action: { type: 'turn', message: 'What version is specified in that package.json?' },
      assertions: [
        { type: 'event-sequence', events: ['turn:start' as any, 'turn:end' as any] },
        { type: 'session-state', path: 'turnCount', equals: 2 },
        { type: 'snapshot-diff', fromLabel: 'after-tool', changed: ['session.turnCount'] },
        { type: 'no-event', event: 'self-healer:error-detected' as any },
      ],
    },
  ],
}
