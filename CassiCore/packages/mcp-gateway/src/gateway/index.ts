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
  watchViaSSE,
  type CollectedEvent,
  type WatchViaSSEOptions,
} from './helpers.js';

// Core Tools
export {
  CORE_TOOLS,
  VYBIT_TOOL,
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

// Flux Tools — Unified Team Orchestration (replaces deprecated cassi_team_* tools)
export {
  FLUX_TOOLS,
  FLUX_TOOL_NAMES,
  executeFluxTeamTool,
  executeFluxRun,
  executeFluxInspect,
  executeFluxWatch,
  getFluxTools,
  type CheckpointPolicy,
  type FluxRunConfig,
} from './flux-tools.js';

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
  DYAD_TOOLS,
  DYAD_TOOL_NAMES,
  executeDyadTool,
  getDyadTools,
} from './dyad-tools.js';
export {
  LUMEN_TOOLS,
  LUMEN_TOOL_NAMES,
  executeLumenTool,
  getLumenTools,
} from './lumen-tools.js';

// Helix Tools
export {
  HELIX_TOOLS,
  HELIX_TOOL_NAMES,
  executeHelixTool,
  getHelixTools,
} from './helix-tools.js';

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

// Blackboard Tools (Global boards + session snapshots)
export {
  BLACKBOARD_TOOLS,
  BLACKBOARD_TOOL_NAMES,
  getBlackboardMcpTools,
  executeBlackboardTool,
} from './blackboard-tools.js';

// File Artifact Tools (Agent file sharing)
export {
  FILE_ARTIFACT_TOOLS,
  FILE_ARTIFACT_TOOL_NAMES,
  getFileArtifactMcpTools,
  executeFileArtifactTool,
} from './file-artifact-tools.js';

// Training Warehouse Tools
export {
  TRAINING_TOOLS,
  TRAINING_TOOL_NAMES,
  executeTrainingTool,
  getTrainingTools,
} from './training-tools.js';

// Consolidated Tools (NEW - Phase 2+)
export {
  AGENT_TOOL,
  AGENT_TOOL_NAME,
  executeAgentTool,
  getAgentTool,
} from './agent-tools.js';

export {
  MEMORY_CONSOLIDATED_TOOL,
  MEMORY_CONSOLIDATED_TOOL_NAME,
  executeMemoryConsolidatedTool,
  getMemoryConsolidatedTool,
} from './consolidated-memory-tools.js';

export {
  SESSION_CONSOLIDATED_TOOL,
  SESSION_CONSOLIDATED_TOOL_NAME,
  executeSessionConsolidatedTool,
  getSessionConsolidatedTool,
} from './consolidated-session-tools.js';

export {
  INTELLIGENCE_CONSOLIDATED_TOOL,
  INTELLIGENCE_CONSOLIDATED_TOOL_NAME,
  executeIntelligenceConsolidatedTool,
  getIntelligenceConsolidatedTool,
} from './consolidated-intelligence-tools.js';

export {
  ARTIFACT_CONSOLIDATED_TOOL,
  ARTIFACT_CONSOLIDATED_TOOL_NAME,
  executeArtifactConsolidatedTool,
  getArtifactConsolidatedTool,
} from './consolidated-file-tools.js';

export {
  WEB_CONSOLIDATED_TOOL,
  WEB_CONSOLIDATED_TOOL_NAME,
  executeWebConsolidatedTool,
  getWebConsolidatedTool,
} from './consolidated-web-tools.js';

export {
  CONFIG_CONSOLIDATED_TOOL,
  CONFIG_CONSOLIDATED_TOOL_NAME,
  executeConfigConsolidatedTool,
  getConfigConsolidatedTool,
} from './consolidated-config-tools.js';

export {
  MODEL_CONSOLIDATED_TOOL,
  MODEL_CONSOLIDATED_TOOL_NAME,
  executeModelConsolidatedTool,
  getModelConsolidatedTool,
} from './consolidated-model-tools.js';

export {
  BLACKBOARD_CONSOLIDATED_TOOL,
  BLACKBOARD_CONSOLIDATED_TOOL_NAME,
  executeBlackboardConsolidatedTool,
  getBlackboardConsolidatedTool,
} from './consolidated-blackboard-tools.js';

export {
  TRAINING_CONSOLIDATED_TOOL,
  TRAINING_CONSOLIDATED_TOOL_NAME,
  executeTrainingConsolidatedTool,
  getTrainingConsolidatedTool,
} from './consolidated-training-tools.js';

// Serena Auto-Onboarding
export {
  SerenaAutoOnboarding,
  createSerenaOnboarding,
} from './serena-onboarding.js';
export type { ToolRouter as SerenaToolRouter } from './serena-onboarding.js';

// Consolidated Code Tools (GitNexus + Serena code intelligence)
export {
  CODE_CONSOLIDATED_TOOL,
  CODE_CONSOLIDATED_TOOL_NAME,
  executeCodeConsolidatedTool,
  getCodeConsolidatedTool,
  getCodeConsolidatedToolSchema,
} from './consolidated-code-tools.js';

// Consolidated Filesystem Tools (Serena file operations)
export {
  FILESYSTEM_CONSOLIDATED_TOOL,
  FILESYSTEM_CONSOLIDATED_TOOL_NAME,
  executeFilesystemConsolidatedTool,
  getFilesystemConsolidatedTool,
  getFilesystemConsolidatedToolSchema,
} from './consolidated-filesystem-tools.js';

// Consolidated Browser Tools (Playwright)
export {
  BROWSER_CONSOLIDATED_TOOL,
  BROWSER_CONSOLIDATED_TOOL_NAME,
  executeBrowserConsolidatedTool,
  getBrowserConsolidatedTool,
} from './consolidated-browser-tools.js';

// Tool Alias System
export {
  TOOL_ALIASES,
  CANONICAL_TOOL_NAMES,
  resolveToolAlias,
  stripKnownPrefix,
  unknownToolError,
  suggestToolName,
  levenshteinSimilarity,
  findBestFuzzyMatch,
  allKnownToolNames,
} from './tool-aliases.js';
export type { AliasEntry, AliasTable } from './tool-aliases.js';
