/**
 * Session Management
 * 
 * Simplified session management exports
 */

// Types
export type {
  SessionState,
  Message,
  ToolCall,
  ToolResult,
  TurnRequest,
  TurnResult,
  TurnMetadata,
  ToolExecution,
  SessionFilter,
  TurnData,
  ProcessorResult,
  IntelligenceContext,
  ISessionStore,
  ILogger,
  IToolExecutor,
  ToolContext,
  StreamEventType,
  StreamEventCallback
} from './types.js';

// Errors
export {
  SessionError,
  SessionNotFoundError,
  StoreError,
  TurnProcessingError,
  ProviderNotFoundError
} from './types.js';

// Session Manager
export { SessionManager, createSessionManager } from './SessionManager.js';
export type { GetOrCreateOptions } from './SessionManager.js';

// Stores
export { SQLiteSessionStore, createDefaultSQLiteStore } from './stores/SQLiteStore.js';
export type { SQLiteStoreOptions } from './stores/SQLiteStore.js';

export { MemorySessionStore, createTestStore } from './stores/MemoryStore.js';
export type { MemoryStoreOptions } from './stores/MemoryStore.js';
