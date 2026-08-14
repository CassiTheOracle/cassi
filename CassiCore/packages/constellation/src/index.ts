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



export { ConstellationRegistry } from './constellation-injection.js'
export type { ConstellationLiveState } from './constellation-injection.js'



export { createConstellationOrchestrator } from './constellation-orchestrator.js'
export type { ConstellationOrchestrator } from './constellation-orchestrator.js'

export { createConstellationGuidanceProvider, ConstellationGuidanceRegistry } from './guidance-provider.js'
export type { ConstellationGuidanceProviderOpts } from './guidance-provider.js'

// Observer-memory bridge — insight sink / observer insight types consumed by
// @cassicore/aurora's Claustrum (re-point target for the former sibling import).
export { ObserverMemoryBridge, extractConceptHints, priorityToConfidence } from './observer-memory-bridge.js'
export type {
  ObserverInsight,
  ClaustrumInsightSink,
  ObserverMemoryHit,
  ObserverMemorySource,
  ObserverMemoryBridgeOpts,
} from './observer-memory-bridge.js'

// Meditation style selection — affect-integrated style selection (consumed by
// @cassicore/cortex-pineal-dialectic's cortex tests).
export { selectStyle, STYLE_CONFIGS } from './meditation/styles.js'
export type { MeditationStyle, StyleConfig } from './meditation/styles.js'



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


// REMOVED: Constellation Audit Trail — wrote to FileArtifactStore which is gone.

// =============================================================================
// HOST WIRING PORTS
// -----------------------------------------------------------------------------
// Constellation is standalone: every deep CassiCore host integration (helix
// pipeline, code-analysis context assembly, model-pool, filesystem paths,
// gaming-mode flagging, luminance keyword helpers, and the consolidated code/
// filesystem/web tool surfaces) is exposed through a typed PORT instead of a
// runtime import. Each port ships a default `not connected` implementation so
// the package loads and type-checks on its own; a host wires the functions it
// needs before running a constellation pipeline. See src/ports/*.ts.
// =============================================================================

// Helix pipeline + BrainstemMiniHelix (deep daemon integration)
export { runHelixPipeline, BrainstemMiniHelix } from './ports/helix-pipeline.js'
export type {
  HelixResult,
  HelixPipelineOpts,
  HelixToolProfile,
  BrainstemMiniHelixOpts,
  BrainstemMiniHelixDeps,
} from './ports/helix-pipeline.js'

// Code-analysis context assembly (prepareContext — git-nexus backed in the host)
export { prepareContext } from './ports/code-analysis-context.js'
export type { PreparedContext, PreparedContextFile, PrepareContextOptions } from './ports/code-analysis-context.js'

// Filesystem/data-directory helpers
export { getCassiCoreHome, getDataDir, setDataDirRoot } from './ports/paths.js'

// Gaming-mode flag (host-provided mode detection)
export { isGamingMode, setGamingMode, isGamingModeAutoManaged } from './ports/gaming-mode.js'

// Workspace luminance / keyword helpers
export { extractKeywords, keywordOverlap } from './ports/workspace-luminance.js'

// Consolidated code / filesystem / web tool surfaces
export {
  getCodeConsolidatedToolSchema,
  getFilesystemConsolidatedToolSchema,
  WEB_CONSOLIDATED_TOOL,
  executeCodeConsolidatedTool,
  executeFilesystemConsolidatedTool,
  executeWebConsolidatedTool,
} from './ports/mcp-consolidated-tools.js'
export type { ToolSchema, RouteTool, ConsolidatedToolResult } from './ports/mcp-consolidated-tools.js'
// P7 admin-api: constellation-store row/progress types
export type { ConstellationSessionRow, ProgressSnapshot } from './constellation-store.js'
export { ConstellationStore } from './constellation-store.js'
export { analyzeConstellation } from './constellation-analyzer.js'

export { createMeditationController } from './meditation/index.js'
export type { MeditationController } from './meditation/index.js'
export { BroadcastDedupe } from './observer-broadcast-dedupe.js'

export { runSoloExplorer } from './meditation/solo-runner.js'
