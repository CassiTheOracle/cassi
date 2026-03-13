/**
 * CassiCore Event System
 *
 * Central event bus and streaming API for CassiCore daemon.
 * Enables deep integration between CLI, daemon, and Cassandra.
 */

// Event Bus — re-exported from core for convenience
import { bus } from '../event-bus.js';
export type { EventBus } from '../event-bus.js';

/**
 * Get the shared EventBus singleton.
 * This is the same instance as `bus` in core/event-bus.ts.
 */
export function getEventBus() { return bus; }

/**
 * Clear all event history from the shared bus.
 */
export function resetEventBus(): void {
  bus.clear();
}

// Event Types (CLI ↔ daemon protocol types)
export type {
  BaseEvent,
  CassiCoreEvent,
  CassiCoreEventHandler,
  SessionStartEvent,
  SessionShutdownEvent,
  AgentStartEvent,
  AgentEndEvent,
  TurnStartEvent,
  TurnEndEvent,
  StreamingStartEvent,
  StreamingTokenEvent,
  StreamingEndEvent,
  UserMessageEvent,
  AssistantMessageEvent,
  ToolExecutionStartEvent,
  ToolExecutionUpdateEvent,
  ToolExecutionEndEvent,
  ModelSelectEvent,
  SystemPromptUpdateEvent,
  ContextUsageEvent,
  CompactionStartEvent,
  CompactionEndEvent,
  ErrorEvent,
} from './event-types.js';

// Event API
export {
  EventAPI,
  SSEConnectionManager,
} from './event-api.js';

export type {
  IngestRequest,
  IngestResponse,
  HistoryRequest,
  HistoryResponse,
  StateSnapshotRequest,
  StateSnapshot,
} from './event-api.js';

// Cassandra Event Client
export {
  CassandraEventClient,
  createEventClient,
} from './cassandra-event-client.js';

export type {
  CassandraEventClientOptions,
  CassandraState,
  ActiveToolCall,
  EventType,
} from './cassandra-event-client.js';

// Context Window Debugging
export {
  ContextWindowDebugger,
  initContextWindowDebugger,
  getContextWindowDebugger,
  resetContextWindowDebugger,
} from './context-window-debug.js';

export type {
  ContextWindowSnapshot,
  ContextWindowDiff,
} from './context-window-debug.js';
