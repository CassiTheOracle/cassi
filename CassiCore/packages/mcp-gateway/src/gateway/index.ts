#!/usr/bin/env node
/**
 * CassiCore MCP Gateway Module Exports
 * Re-exports all domain modules for the gateway
 */

// Helpers
export {
  GATEWAY_VERSION,
  DEFAULT_FETCH_TIMEOUT_MS,
  createLogger,
  fetchWithTimeout,
  fetchIntelligence,
  resolveSessionId,
  formatError,
  formatJsonResponse,
  formatTextResponse,
  SAFE_CONFIG_KEYS,
  isConfigKeySafe,
} from './helpers.js';

// Core Tools
export {
  CORE_TOOLS,
  executeCassiCoreTool,
  isCoreTool,
  getCoreTools,
} from './tool-management.js';

// Session Tools
export {
  SESSION_TOOLS,
  SESSION_TOOL_NAMES,
  executeSessionTool,
  getSessionTools,
} from './session-tools.js';

// Memory Tools
export {
  MEMORY_TOOLS,
  MEMORY_TOOL_NAMES,
  executeMemoryTool,
  getMemoryTools,
} from './memory-tools.js';

// Config/Admin Tools
export {
  CONFIG_ADMIN_TOOLS,
  CONFIG_ADMIN_TOOL_NAMES,
  executeConfigAdminTool,
  getConfigAdminTools,
} from './config-admin-tools.js';

// Flux Tools (NEW - Unified Team Orchestration)
// NOTE: These exports come BEFORE legacy team-tools to establish flux-tools as canonical
export {
  FLUX_TOOLS,
  FLUX_TOOL_NAMES,
  executeFluxTeamTool,
  executeFluxRun,
  executeFluxInspect,
  executeFluxWatch,
  type CheckpointPolicy,
  type FluxRunConfig,
} from './flux-tools.js';

// Team Tools — DEPRECATED (Phase 1)
// ⚠️ Deprecated in favor of flux-tools.js. Legacy wrappers log warnings and delegate to flux_*.
export {
  TEAM_TOOLS,
  TEAM_AGENT_TOOLS,
  ACTION_TOOLS,
  TEAM_TOOL_NAMES,
  TEAM_AGENT_TOOL_NAMES,
  ACTION_TOOL_NAMES,
  executeTeamTool,
  executeTeamAgentTool,
  executeActionTool,
  getTeamTools,
  getTeamAgentTools,
  getActionTools,
} from './team-tools.js';

// Composite Tools — DEPRECATED for team tools (Phase 1)
// ⚠️ cassi_team_inspect and cassi_team_watch deprecated in favor of flux_inspect and flux_watch.
export {
  COMPOSITE_TOOLS,
  COMPOSITE_TOOL_NAMES,
  executeCompositeTool,
  getCompositeTools,
} from './composite-tools.js';

// Admin API Tools (NEW - Phase 3)
export {
  ADMIN_API_TOOLS,
  ADMIN_API_TOOL_NAMES,
  executeAdminApiTool,
  getAdminApiTools,
} from './admin-api-tools.js';

// Dialectic Tools
export {
  DIALECTIC_TOOLS,
  DIALECTIC_TOOL_NAMES,
  executeDialecticTool,
  getDialecticTools,
} from './dialectic-tools.js';

// Intelligence Tools
export {
  INTELLIGENCE_TOOLS,
  INTELLIGENCE_TOOL_NAMES,
  executeIntelligenceTool,
  getIntelligenceTools,
} from './intelligence-tools.js';

// Lumen Tools
export {
  LUMEN_TOOLS,
  LUMEN_TOOL_NAMES,
  executeLumenTool,
  getLumenTools,
} from './lumen-tools.js';

// Model Directive Tools
export {
  MODEL_DIRECTIVE_TOOLS,
  MODEL_DIRECTIVE_TOOL_NAMES,
  executeModelDirectiveTool,
  getModelDirectiveTools,
} from './model-directive-tools.js';

// Do Tool (meta-wrapper with context enrichment) + Enrich Tool (context-only)
export {
  DO_TOOLS,
  DO_TOOL_NAMES,
  ENRICH_TOOLS,
  ENRICH_TOOL_NAMES,
  executeDoTool,
  executeEnrichTool,
  getDoTools,
  normalizeToolName,
} from './do-tool.js';
export type { ToolRouter } from './do-tool.js';

// Context Enrichment (shared module)
export {
  fetchAndFormatContext,
  type ContextLimits,
  type ContextEnrichmentResult,
} from './context-enrichment.js';

// Resources Module (NEW - MCP Resources Design)
export {
  readResource,
  getStaticResources,
  getResourceTemplates,
  invalidateResourceCache,
  parseResourceUri,
} from './resources.js';
