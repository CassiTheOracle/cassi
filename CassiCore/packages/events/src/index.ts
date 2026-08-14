/**
 * CassiCore Event System
 *
 * Central event bus and streaming API for CassiCore daemon.
 * Enables deep integration between CLI, daemon, and Cassandra.
 */

// Event Bus — re-exported from core for convenience
import { bus } from './event-bus.js';
export { bus } from './event-bus.js';
export { Logger, rootLogger } from './logger.js';
export type { EventBus } from './event-bus.js';

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

// Event History
export { EventHistory, getEventHistory, setEventHistory } from './event-history.js';

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
} from './events/event-types.js';

// Event API
export {
  EventAPI,
  SSEConnectionManager,
} from './events/event-api.js';

export type {
  IngestRequest,
  IngestResponse,
  HistoryRequest,
  HistoryResponse,
  StateSnapshotRequest,
  StateSnapshot,
} from './events/event-api.js';

// Cassandra Event Client
export {
  CassandraEventClient,
  createEventClient,
} from './events/cassandra-event-client.js';

export type {
  CassandraEventClientOptions,
  CassandraState,
  ActiveToolCall,
  EventType,
} from './events/cassandra-event-client.js';

// Context Window Debugging
export {
  ContextWindowDebugger,
  initContextWindowDebugger,
  getContextWindowDebugger,
  resetContextWindowDebugger,
} from './events/context-window-debug.js';

export type {
  ContextWindowSnapshot,
  ContextWindowDiff,
} from './events/context-window-debug.js';
