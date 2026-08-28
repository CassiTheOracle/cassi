/**
 * CassiCore Event Types
 *
 * Type definitions for the CLI ↔ daemon event protocol.
 * These types describe the specific event shapes exchanged between
 * the CassiCLI and the CassiCore daemon via HTTP/SSE.
 */

// Base Event

export interface BaseEvent {
  type: string;
  sessionId: string;
  timestamp: number;
  eventId: string;
}

// Session Lifecycle

export interface SessionStartEvent extends BaseEvent {
  type: 'session_start';
  cwd: string;
}

export interface SessionShutdownEvent extends BaseEvent {
  type: 'session_shutdown';
  durationMs: number;
}

// Agent Loop

export interface AgentStartEvent extends BaseEvent {
  type: 'agent_start';
  turnIndex: number;
  model: string;
}

export interface AgentEndEvent extends BaseEvent {
  type: 'agent_end';
  turnIndex: number;
  messageCount: number;
}

export interface TurnStartEvent extends BaseEvent {
  type: 'turn_start';
  turnIndex: number;
  promptPreview: string;
}

export interface TurnEndEvent extends BaseEvent {
  type: 'turn_end';
  turnIndex: number;
}

// Streaming

export interface StreamingStartEvent extends BaseEvent {
  type: 'streaming_start';
  model: string;
}

export interface StreamingTokenEvent extends BaseEvent {
  type: 'streaming_token';
  token: string;
}

export interface StreamingEndEvent extends BaseEvent {
  type: 'streaming_end';
  fullMessageLength: number;
}

// Messages

export interface UserMessageEvent extends BaseEvent {
  type: 'user_message';
  content: string;
  hasImages: boolean;
}

export interface AssistantMessageEvent extends BaseEvent {
  type: 'assistant_message';
  content: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens?: number;
  cacheWriteTokens?: number;
}

// Tools

export interface ToolExecutionStartEvent extends BaseEvent {
  type: 'tool_execution_start';
  toolCallId: string;
  toolName: string;
  args: unknown;
}

export interface ToolExecutionUpdateEvent extends BaseEvent {
  type: 'tool_execution_update';
  toolCallId: string;
  toolName: string;
  partialResult: unknown;
}

export interface ToolExecutionEndEvent extends BaseEvent {
  type: 'tool_execution_end';
  toolCallId: string;
  toolName: string;
  result: unknown;
  isError: boolean;
  durationMs: number;
}

// Model

export interface ModelSelectEvent extends BaseEvent {
  type: 'model_select';
  model: string;
  previousModel?: string;
  source: 'user' | 'cycle' | 'restore';
}

// System

export interface SystemPromptUpdateEvent extends BaseEvent {
  type: 'system_prompt_update';
  promptHash: string;
  promptLength: number;
}

export interface ContextUsageEvent extends BaseEvent {
  type: 'context_usage';
  tokens: number;
  contextWindow: number;
  percent: number;
}

// Compaction

export interface CompactionStartEvent extends BaseEvent {
  type: 'compaction_start';
  reason: 'threshold' | 'overflow' | 'manual';
}

export interface CompactionEndEvent extends BaseEvent {
  type: 'compaction_end';
  summaryLength: number;
  entriesRemoved: number;
}

// Errors

export interface ErrorEvent extends BaseEvent {
  type: 'error';
  error: string;
  context?: string;
  recoverable: boolean;
}

// Union Type

export type CassiCoreEvent =
  | SessionStartEvent
  | SessionShutdownEvent
  | AgentStartEvent
  | AgentEndEvent
  | TurnStartEvent
  | TurnEndEvent
  | StreamingStartEvent
  | StreamingTokenEvent
  | StreamingEndEvent
  | UserMessageEvent
  | AssistantMessageEvent
  | ToolExecutionStartEvent
  | ToolExecutionUpdateEvent
  | ToolExecutionEndEvent
  | ModelSelectEvent
  | SystemPromptUpdateEvent
  | ContextUsageEvent
  | CompactionStartEvent
  | CompactionEndEvent
  | ErrorEvent;

export type CassiCoreEventHandler<T extends CassiCoreEvent> = (event: T) => void | Promise<void>;
