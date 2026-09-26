/**
 * CassiAgent — Shared base for posture runners across all agent systems.
 *
 * Postures (Yang, Yin, Unity) are NOT agents — they are behavioral modes
 * that compose a single CassiAgent (Helix, Lumen, Dyad). The PostureRunner
 * is the execution thread for a posture within an agent, not an agent itself.
 *
 * Re-exports from this module:
 * - BasePostureRunner: Abstract base class with shared tool-loop infrastructure
 * - Shared constants: CHARS_PER_TOKEN, CONTEXT_BUDGET_FRACTION, MAX_TOOL_RESULT_CHARS
 * - Shared utilities: isReadOnlyTool, isMemoryTool, findLastIndex
 */

export {
  BasePostureRunner,
  CHARS_PER_TOKEN,
  CONTEXT_BUDGET_FRACTION,
  MAX_TOOL_RESULT_CHARS,
  isReadOnlyTool,
  isMemoryTool,
  findLastIndex,
} from './base-posture-runner.js'

