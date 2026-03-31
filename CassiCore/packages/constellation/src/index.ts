/**
 * Constellation — Self-organizing, recursively composable multi-agent system.
 *
 * Exports: types, FlexPosture system, templates, Corpus tree, and Corpus organizer.
 */

// ── Types ──────────────────────────────────────────────────────────────────

export type {
  FlexPosture,
  ToolAccessLevel,
  WorkStreamMode,
  ConstellationTemplate,
  ConstellationHelixConfig,
  ConstellationNode,
  ConstellationNodeStatus,
  ConstellationPostureResult,
  SpawnRequest,
  SpawnRequestStatus,
  ConstellationResult,
  ConstellationProjectOpts,
  BlackboardBridgeConfig,
  ConstellationEventType,
} from './types.js'

export {
  constellationSessionId,
  helixSessionId,
  postureSessionId,
} from './types.js'


// ── FlexPosture System ─────────────────────────────────────────────────────

export {
  validatePosture,
  validatePostureSet,
  applyDefaults,
  composeConstellationPrompt,
  resolveSlotName,
  createPosture,
  createPostureSet,
} from './flex-posture.js'

export type { PostureValidationResult } from './flex-posture.js'


// ── Templates ──────────────────────────────────────────────────────────────

export {
  getTemplatePostures,
  listTemplates,
  describeTemplate,
  resolvePostures,
} from './templates.js'


// ── Corpus Types ───────────────────────────────────────────────────────────

export type {
  ICorpusTree,
  CorpusBranch,
  CorpusBranchStatus,
  CorpusStep,
  CorpusTreeSnapshot,
  CorpusBranchSnapshot,
  CorpusProcessedState,
  BranchAssessment,
  BranchHealthStatus,
  CrossHelixPattern,
  CrossHelixPatternType,
  CorpusDirective,
  CorpusDirectiveType,
  SpawnDecision,
  CorpusConfig,
  CorpusCadence,
  CorpusDeps,
  CorpusLLM,
  CorpusBlackboard,
  CorpusResult,
  CorpusIntervention,
  // Shared Thought Tree types
  BranchDigest,
  BranchApproach,
  TopicNode,
  TopicContribution,
  SelfOrgAdjustment,
  SelfOrgAdjustmentType,
  StrategyRetrospective,
  RetrospectiveTrigger,
  ElevatedPattern,
  EffectivenessRecord,
} from './corpus-types.js'

export {
  DEFAULT_CORPUS_CONFIG,
  createInitialProcessedState,
} from './corpus-types.js'


// ── Corpus Tree ────────────────────────────────────────────────────────────

export { CorpusTree } from './corpus-tree.js'


// ── Corpus Organizer ───────────────────────────────────────────────────────

export { Corpus, createCorpus } from './corpus.js'


// ── Constellation Pipeline ─────────────────────────────────────────────────

export { runConstellationPipeline, serializeConstellationResult } from './constellation-pipeline.js'
export type { ConstellationPipelineOpts } from './constellation-pipeline.js'


// ── Blackboard Bridge ──────────────────────────────────────────────────────

export { BlackboardBridge, createBridge } from './blackboard-bridge.js'


// ── Cross-Helix Dialectic ─────────────────────────────────────────────────

export { CrossHelixDialectic } from './cross-helix-dialectic.js'
export type {
  CrossHelixMessage,
  CrossHelixConvergencePoint,
  CrossHelixTension,
  CrossHelixDialecticSnapshot,
  CrossHelixDialecticConfig,
} from './cross-helix-dialectic.js'


// ── Corpus Tools (Tool-based analysis) ────────────────────────────────────

export {
  getCorpusToolDefinitions,
  executeCorpusTool,
  buildCorpusSystemPrompt,
  createCorpusMiniHelixTools,
} from './corpus-tools.js'
export type { CorpusToolDefinition, CorpusToolContext, ToolCallResult } from './corpus-tools.js'


// ── Corpus Mini-Helix ─────────────────────────────────────────────────────

export { CorpusMiniHelix } from './corpus-mini-helix.js'
export type { CorpusMiniHelixConfig } from './corpus-mini-helix.js'


// ── Constellation Injection Source ─────────────────────────────────────────

export { ConstellationRegistry, ConstellationInjectionSource } from './constellation-injection.js'
export type { ConstellationLiveState } from './constellation-injection.js'


// ── Constellation Orchestrator ─────────────────────────────────────────────

export { createConstellationOrchestrator } from './constellation-orchestrator.js'
export type { ConstellationOrchestrator } from './constellation-orchestrator.js'
