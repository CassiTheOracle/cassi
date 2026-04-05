/**
 * Constellation — Self-organizing, recursively composable multi-agent system.
 *
 * Exports: types, FlexPosture system, templates, Corpus tree, and Corpus organizer.
 */


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



export {
  getTemplatePostures,
  listTemplates,
  describeTemplate,
  resolvePostures,
} from './templates.js'



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
  // External Corpus Protocol types
  ExternalCorpusState,
  ExternalCorpusSnapshot,
  PendingExternalSpawnRequest,
} from './corpus-types.js'

export {
  DEFAULT_CORPUS_CONFIG,
  createInitialProcessedState,
  createInitialExternalCorpusState,
  DEFAULT_EXTERNAL_CORPUS_HEARTBEAT_MS,
} from './corpus-types.js'



export { CorpusTree } from './corpus-tree.js'



export { Corpus, createCorpus } from './corpus.js'



export { runConstellationPipeline, serializeConstellationResult } from './constellation-pipeline.js'
export type { ConstellationPipelineOpts } from './constellation-pipeline.js'



export { BlackboardBridge, createBridge } from './blackboard-bridge.js'

export { ConstellationWorktreeIsolation } from './worktree-isolation.js'
export type { ConstellationIsolation, WorktreeChanges, WorktreeMergeResult } from './worktree-isolation.js'



export { CrossHelixDialectic } from './cross-helix-dialectic.js'
export type {
  CrossHelixMessage,
  CrossHelixConvergencePoint,
  CrossHelixTension,
  CrossHelixDialecticSnapshot,
  CrossHelixDialecticConfig,
} from './cross-helix-dialectic.js'



export {
  getCorpusToolDefinitions,
  executeCorpusTool,
  buildCorpusSystemPrompt,
  createCorpusMiniHelixTools,
} from './corpus-tools.js'
export type { CorpusToolDefinition, CorpusToolContext, ToolCallResult } from './corpus-tools.js'



export { CorpusMiniHelix } from './corpus-mini-helix.js'
export type { CorpusMiniHelixConfig } from './corpus-mini-helix.js'



export { ConstellationRegistry, ConstellationInjectionSource } from './constellation-injection.js'
export type { ConstellationLiveState } from './constellation-injection.js'



export { createConstellationOrchestrator } from './constellation-orchestrator.js'
export type { ConstellationOrchestrator } from './constellation-orchestrator.js'

export { createConstellationGuidanceProvider, ConstellationGuidanceRegistry } from './guidance-provider.js'
export type { ConstellationGuidanceProviderOpts } from './guidance-provider.js'



export { DecompositionTracker } from './decomposition-tracker.js'
export type {
  TrackedTask,
  TaskStatus,
  DecompositionSnapshot,
} from './decomposition-tracker.js'


// Fast Decomposer — Direct LLM-based goal decomposition

export { fastDecompose, shouldDecompose } from './fast-decomposer.js'
export type { FastDecomposerOpts, DecompositionMode, DecompositionDecision } from './fast-decomposer.js'


// Template Capabilities — Machine-readable template metadata

export { getTemplateCapabilities, listTemplateCapabilities } from './templates.js'
export type { PostureCapabilities, TemplateCapabilities } from './types.js'


// Audit Trail — Event-driven decision logging

export { createConstellationAuditTrail } from './constellation-audit-trail.js'
export type {
  ConstellationAuditTrail,
  AuditDecision,
  AuditPlan,
  AuditSummary,
} from './constellation-audit-trail.js'
