/**
 * @cassicore/tools — packager barrel.
 *
 * The source `core/tools/` dir has NO `index.ts`; the packager writes this
 * barrel to expose the public registry/executor surface, the tool type system,
 * and the 30+ core tool implementations via `registerCoreTools` and the
 * individual definition/handler exports consumers rely on.
 *
 * The `registerCoreTools(registry, deps)` seam contract (plan §3e.4/§5-P6) is
 * re-exported verbatim so P5-Packages/P7 admin-api/mcp can register the core
 * toolset against any `ToolRegistry`.
 */

// ── Registry / executor / tool type system ────────────────────────────────
export type {
  ToolParamProperty,
  ToolParamSchema,
  ToolCategory,
  ToolDefinition,
  ToolCall,
  ToolResult,
  ToolHandler,
  ToolExecutionContext,
} from './types.js'
export { ToolRegistry } from './registry.js'
export type { ToolListOptions } from './registry.js'
export { ToolExecutor } from './executor.js'

// ── Safety / reliability / presentation / scout / hermes / interactive ────
export {
  validateToolInput,
  validateToolOutput,
  executeWithTimeout,
  executeToolSafe,
  createSafeToolExecutor,
} from './safety.js'
export type { ValidationResult, SafeResult, ToolGuardrails } from './safety.js'
export { ToolReliabilityTracker } from './reliability.js'
export type {
  CircuitState,
  ToolReliabilityMetrics,
  ReliabilityConfig,
} from './reliability.js'
export { presentForLLM } from './presentation.js'
export type { PresentationOptions } from './presentation.js'
export { Scout, getScout } from './scout.js'
export type {
  ScoutInvestigation,
  ScoutFindings,
  SessionContextProvider,
  ScoutOptions,
} from './scout.js'
export { HermesMcpClient, getHermesMcpClient, shutdownHermesMcpClient } from './hermes-mcp-client.js'
export { HERMES_TOOL_DEFINITIONS, registerHermesTools } from './hermes-tools.js'
export type { HermesToolName } from './hermes-tools.js'
export {
  InteractiveToolSession,
  isPrompt,
  extractText,
  splitForTelegram,
} from './interactive-tool-session.js'
export type {
  ParamSchema,
  PromptResult,
  ExecutionResult,
  SessionResult,
} from './interactive-tool-session.js'

// ── Hooks ─────────────────────────────────────────────────────────────────
export { ExternalHookRunner, mergeHookFeedback, EMPTY_HOOK_CONFIG } from './hooks/external-hook-runner.js'
export type { HookEvent, HookRunResult, ExternalHookConfig } from './hooks/external-hook-runner.js'

// ── registerCoreTools ─────────────────────────────────────────────────────
export {
  registerCoreTools,
} from './implementations/index.js'
export type {
  CoreToolDeps,
} from './implementations/index.js'

// ── registerMindTools (P3 retained mind slice) ────────────────────────────
// The P3 spine/runtime seam: registers ONLY the retained mind tools (plan §4.2
// + the P5-deletion seam tools) against a ToolRegistry, with retained handler
// deps injected via CoreToolDeps. `registerCoreTools` above is untouched.
export {
  registerMindTools,
} from './implementations/index.js'

// ── Impl tool definitions / surfaces consumed by inbound packages ─────────
// graph-discover (constellation-pipeline re-points setGraphDiscoverDeps runtime)
export {
  setGraphDiscoverDeps,
  graphDiscoverDefinition,
  graphDiscoverHandler,
} from './implementations/graph-discover.js'
export type { GraphDiscoverDeps } from './implementations/graph-discover.js'
// collect-thoughts (constellation guidance-provider re-points the type)
export type { ConstellationGuidanceProvider } from './implementations/collect-thoughts.js'
// Retained mind-tool definitions (P3 spine schema surface)
// _reflect / _remember / remember / memory_search were P5-deleted (merge into
// ohmypi memory built-ins over the shared field, CASSICORE-FOCUS §3.3 / §7.5).
export {
  collectThoughtsDefinition,
  coordinateDefinition,
  checkPeersDefinition,
  listSubagentsDefinition,
  getSubagentStatusDefinition,
  getSubagentResultDefinition,
  systemHealthDefinition,
  debugSessionDefinition,
  universalSearchDefinition,
  cassandraQueryEventsDef,
  cassandraContextInspectDef,
  queryEventsDefinition,
} from './implementations/mind-definitions.js'
