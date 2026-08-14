/**
 * Session Types for CassiCore
 * 
 * Flattened, cleaner interfaces for session management
 */

import type { ImageAttachment, ContentBlock, IProvider } from '@cassicore/foundation';

// Core Session Types

/**
 * Simplified session state - flattened from complex Session interface
 */
export interface SessionState {
  // Identity
  id: string;
  channelId: string;
  senderId: string;
  
  // Conversation data
  messages: Message[];
  
  // Configuration (flattened)
  model: string;              // Format: "provider/model"
  systemPrompt: string;
  maxTokens: number;
  temperature: number;
  thinking?: 'none' | 'low' | 'medium' | 'high';
  
  // Metadata
  createdAt: number;
  lastActiveAt: number;
  turnCount: number;
  
  // Optional: Context from intelligence layer
  context?: IntelligenceContext;
}

/**
 * Simplified message type
 */
export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string | ContentBlock[];
  timestamp: number;
  
  // Optional tool-related data
  toolCalls?: ToolCall[];
  toolResults?: ToolResult[];
}

/**
 * Tool call from assistant
 */
export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
}

/**
 * Tool execution result
 */
export interface ToolResult {
  toolCallId: string;
  toolName: string;
  content: string;
  isError: boolean;
}

/**
 * Context injected by intelligence layer
 */
export interface IntelligenceContext {
  recentMemories?: string[];
  dialecticInsights?: string[];
  thinkerNotes?: string[];
  subconsciousSignals?: string[];
  /** Injections from InjectionAggregator (Corpus, SessionDigest, Optimizer, Dreamer, etc.) */
  injections?: string[];
  /** Pre-formatted `<observers>` block from the Default Mode Network (DMN). */
  observersBlock?: string;

  // Timestamps for freshness
  updatedAt?: number;
}

// Streaming Types

/**
 * Event types emitted during per-token streaming
 */
export type StreamEventType = 'token' | 'thinking' | 'tool_call' | 'tool_result';

/**
 * Callback invoked for each streaming event during turn processing.
 * Threads from ToolLoop → TurnHandler → SessionPipeline → SSE handler.
 */
export type StreamEventCallback = (
  type: StreamEventType,
  data: {
    token?: string;
    toolCall?: ToolCall;
    toolResult?: ToolExecution;
  }
) => void;

// Request/Response Types

/**
 * Incoming turn request
 */
export interface TurnRequest {
  sessionId?: string;         // Optional - will be generated if not provided
  channelId: string;
  senderId: string;
  content: string;
  attachments?: ImageAttachment[];
  metadata?: Record<string, unknown>;
  signal?: AbortSignal;       // For cancellation
}

/**
 * Turn processing result
 */
export interface TurnResult {
  response: string;
  tokensUsed: number;
  model: string;
  durationMs: number;
  toolCalls?: ToolExecution[];
  thinkingBlocks?: string[];
}

/**
 * Tool execution record
 */
export interface ToolExecution {
  toolCallId: string;
  toolName: string;
  content: string;
  isError: boolean;
  durationMs: number;
}

// Store Types

/**
 * Filter options for listing sessions
 */
export interface SessionFilter {
  channelId?: string;
  senderId?: string;
  olderThan?: number;
  newerThan?: number;
  limit?: number;
  offset?: number;
}

/**
 * Metadata for turn operations
 */
export interface TurnMetadata {
  tokensUsed?: number;
  toolCalls?: ToolExecution[];
  model?: string;
  durationMs?: number;
}

// Intelligence Types

/**
 * Data passed to intelligence processors
 */
export interface TurnData {
  userMessage: string;
  assistantResponse: string;
  toolCalls?: ToolExecution[];
  sessionHistory: Message[];
  availableTools: string[];
  thinkingBlocks?: string[];
  timestamp: number;
}

/**
 * Result from intelligence processor
 */
export interface ProcessorResult {
  type: 'memories' | 'dialecticInsights' | 'thinkerNotes' | 'subconsciousSignals' | string;
  data: unknown;
}

// Utility Types

/**
 * Options for SessionManager
 */
export interface SessionManagerOptions {
  store: ISessionStore;
  defaultModel: string;
  defaultSystemPrompt: string;
  logger: ILogger;
  cacheSize?: number;
}

/**
 * Options for TurnHandler
 */
export interface TurnHandlerOptions {
  providers: Map<string, IProvider>;
  toolExecutor: IToolExecutor;
  logger: ILogger;
  maxToolRounds?: number;
  contextWindowTokens?: number;
  toolTimeoutMs?: number;
  /** Tool schemas to pass to LLM providers (Anthropic format).
   *  Accepts a getter function for live registry updates, or a static array. */
  toolSchemas?: (() => Array<{ name: string; description: string; input_schema: Record<string, unknown> }>) | Array<{ name: string; description: string; input_schema: Record<string, unknown> }>;
}

/**
 * Simplified logger interface
 */
export interface ILogger {
  debug(msg: string, meta?: Record<string, unknown>): void;
  info(msg: string, meta?: Record<string, unknown>): void;
  warn(msg: string, meta?: Record<string, unknown>): void;
  error(msg: string, meta?: Record<string, unknown>): void;
  child(component: string): ILogger;
}

/**
 * Tool executor interface
 */
export interface IToolExecutor {
  execute(name: string, input: unknown, context: ToolContext): Promise<ToolResult>;
  isAvailable(name: string): boolean;
}

/**
 * Context passed to tools
 */
export interface ToolContext {
  sessionId: string;
  toolCallId: string;
  signal?: AbortSignal;
}

// Store Interface

/**
 * Session store interface - unified persistence layer
 */
export interface ISessionStore {
  /**
   * Load session by ID
   */
  load(sessionId: string): Promise<SessionState | null>;
  
  /**
   * Save session
   */
  save(session: SessionState): Promise<void>;
  
  /**
   * Delete session
   */
  delete(sessionId: string): Promise<void>;
  
  /**
   * List sessions with optional filter
   */
  list(filter?: SessionFilter): Promise<SessionState[]>;
  
  /**
   * Initialize store (create tables, etc.)
   */
  initialize?(): Promise<void>;
  
  /**
   * Close store connection
   */
  close?(): Promise<void>;
  
  /**
   * Clear all sessions
   */
  clear?(): Promise<void>;
}

// Error Types

/**
 * Base error for session system
 */
export class SessionError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message);
    this.name = 'SessionError';
    this.cause = options?.cause;
  }
}

export class SessionNotFoundError extends SessionError {
  constructor(sessionId: string) {
    super(`Session not found: ${sessionId}`);
    this.name = 'SessionNotFoundError';
  }
}

export class StoreError extends SessionError {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = 'StoreError';
  }
}

export class TurnProcessingError extends SessionError {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = 'TurnProcessingError';
  }
}

export class ProviderNotFoundError extends SessionError {
  constructor(providerId: string) {
    super(`Provider not found: ${providerId}`);
    this.name = 'ProviderNotFoundError';
  }
}
