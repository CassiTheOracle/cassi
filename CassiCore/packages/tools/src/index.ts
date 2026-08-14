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
