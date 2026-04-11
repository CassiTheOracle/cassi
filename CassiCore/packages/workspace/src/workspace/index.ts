/**
 * Global Workspace — System-level attention and broadcasting.
 *
 * Implements Global Workspace Theory (Baars, 1988) for CassiCore:
 * specialist cognitive modules compete for access to a capacity-limited
 * broadcast medium. Only the brightest signals enter consciousness.
 *
 * The Radiance Loop completes the GWT cycle: after broadcast, modules
 * respond with relevant context, an LLM observer reads the pattern,
 * and its observations re-enter the workspace as signals.
 *
 * Public API:
 *   GlobalWorkspace   — the workspace engine
 *   CognitiveSignal   — the unit of competition
 *   AttentionSchema   — metacognitive self-model
 *   ExpectationModel  — learned baseline for surprise detection
 *   WorkspaceObserver — LLM-based metacognitive observer
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

export type {
  WorkspaceResponse,
  WorkspaceResponseHandler,
  ResponsePattern,
  ResponseDisposition,
  ModuleExpectation,
  SurpriseAssessment,
  ObservationSignal,
  ObservationType,
  RadianceLoopConfig,
} from './radiance-types.js'
export { DEFAULT_RADIANCE_LOOP_CONFIG } from './radiance-types.js'

export { ExpectationModel } from './expectation-model.js'

export { RadianceLoop } from './radiance-loop.js'
export type { RadianceCycleResult, ObserverRunner } from './radiance-loop.js'

export {
  buildObserverPrompt,
  getObserverToolSchemas,
  buildObserverHandlers,
} from './workspace-observer.js'
