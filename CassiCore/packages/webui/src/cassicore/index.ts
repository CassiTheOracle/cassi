/**
 * CassiCore WebUI Integration
 *
 * Tightly integrated web interface for CassiCore daemon
 */

// Admin API Client
export {
  CassiCoreAdminClient,
  getAdminClient,
  setAdminClient,
} from './admin-client.js';

// CassiCore-specific components
export { DialecticPanel } from './dialectic-panel.js';
export { MemoryExplorer } from './memory-explorer.js';

// Re-export core components with CassiCore adaptations
export { CassiCoreChatPanel } from './cassicore-chat-panel.js';

// Types
export type {
  HealthStatus,
  HealthCheck,
  Session,
  SessionConfig,
  Message,
  ToolCall,
  ToolResult,
  DialecticState,
  DialecticUpdate,
  MemoryResult,
  SearchOptions,
  Subagent,
  SubagentConfig,
  Provider,
} from './admin-client.js';
