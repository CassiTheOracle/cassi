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

// Team Tools
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

// Composite Tools (NEW - Phase 2)
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

// Resources Module (NEW - MCP Resources Design)
export {
  readResource,
  getStaticResources,
  getResourceTemplates,
  invalidateResourceCache,
  parseResourceUri,
} from './resources.js';
