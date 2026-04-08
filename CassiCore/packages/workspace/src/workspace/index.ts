/**
 * Global Workspace — System-level attention and broadcasting.
 *
 * Implements Global Workspace Theory (Baars, 1988) for CassiCore:
 * specialist cognitive modules compete for access to a capacity-limited
 * broadcast medium. Only the brightest signals enter consciousness.
 *
 * Public API:
 *   GlobalWorkspace  — the workspace engine
 *   CognitiveSignal  — the unit of competition
 *   AttentionSchema  — metacognitive self-model
 */

export { GlobalWorkspace } from './global-workspace.js'

export type {
  CognitiveSignal,
  SignalType,
  SystemLuminanceScore,
  SystemLuminanceWeights,
  WorkspaceSlot,
  GlobalWorkspaceConfig,
} from './cognitive-signal.js'
export { DEFAULT_WORKSPACE_CONFIG, DEFAULT_LUMINANCE_WEIGHTS, BASE_URGENCY } from './cognitive-signal.js'

export type { AttentionSchema } from './attention-schema.js'
export { buildAttentionSchema, formatAttentionSchema } from './attention-schema.js'

export type { Coalition } from './coalition.js'
export type { FeedbackResult } from './feedback-tracker.js'
export type { CredibilityRecord, FeedbackOutcome } from './workspace-memory.js'
