/**
 * CassiCore Plugin System — Contract Types
 *
 * Defines the interface between CassiCore and external clients (OpenCode,
 * Claude Code, Cursor, web apps, etc.). Designed as progressive layers:
 *
 *   Layer 0 — Transport: how the client connects (worker, unix socket, HTTP, WebSocket)
 *   Layer 1 — Session: session lifecycle, turn tracking, basic event forwarding
 *   Layer 2 — Context: system prompt enrichment, pressure monitoring, chunk management
 *   Layer 3 — Deep: custom tools, self-learning profiles, thinker directives, intelligence
 *
 * Layers are opt-in. A minimal plugin only needs Layer 0 + 1.
 * The OpenCode integration uses all four layers.
 */


// Plugin manifest

/**
 * What a plugin declares about itself when registering with CassiCore.
 * This is the first message a plugin sends after connecting.
 */
export interface PluginManifest {
  /** Unique plugin identifier (e.g., "opencode", "claude-code", "cursor") */
  id: string
  /** Human-readable name */
  name: string
  /** Semver version string */
  version: string
  /** Which capabilities this plugin needs from CassiCore */
  capabilities: PluginCapability[]
  /** How this plugin connects to the daemon */
  transport: TransportType
  /** Session ID prefix for this plugin (e.g., "oc:" for OpenCode, "cc:" for Claude Code) */
  sessionPrefix?: string
  /** Plugin-specific metadata */
  meta?: Record<string, unknown>
}

/** Capabilities a plugin can request — each unlocks a set of API methods */
export type PluginCapability =
  | 'session'        // Session lifecycle management (Layer 1)
  | 'events'         // Real-time event streaming (Layer 1)
  | 'context'        // System prompt / context injection (Layer 2)
  | 'pressure'       // Context pressure reporting and PCPM (Layer 2)
  | 'chunks'         // Chunk manifest and modification (Layer 2)
  | 'memory'         // Memory store, search, KV access (Layer 2)
  | 'tools'          // Custom tool registration (Layer 3)
  | 'intelligence'   // Cognitive context, thinker, dialectic (Layer 3)
  | 'training'       // Training data pipeline access (Layer 3)

/** How the plugin connects to the CassiCore daemon */
export type TransportType =
  | 'worker'         // In-process worker thread (current channel workers)
  | 'unix-socket'    // Local Unix domain socket (fast IPC, admin.sock)
  | 'http'           // HTTP + SSE (local or remote)
  | 'websocket'      // WebSocket (real-time bidirectional)

/** Runtime state of a registered plugin */
export type PluginStatus = 'registered' | 'connected' | 'disconnected' | 'error'


// Plugin registration

export interface PluginRegistration {
  manifest: PluginManifest
  status: PluginStatus
  connectedAt: number | null
  lastHeartbeat: number | null
  /** Capabilities that were granted (may differ from requested if some are unavailable) */
  grantedCapabilities: PluginCapability[]
  /** API key for authenticating subsequent requests (returned on registration) */
  apiKey: string
}


// Plugin protocol messages
// These define the wire protocol for plugin ↔ CassiCore communication.
// HTTP plugins use these as JSON request/response bodies.
// WebSocket/worker plugins use these as message frames.

/** Base envelope for all plugin protocol messages */
export interface PluginMessage {
  type: string
  pluginId: string
  /** Monotonic request ID for correlating request/response pairs */
  requestId?: string
  timestamp: number
}


// Layer 1: Session

export interface SessionCreateRequest extends PluginMessage {
  type: 'session.create'
  parentSessionId?: string
  meta?: Record<string, unknown>
}

export interface SessionCreateResponse {
  sessionId: string
  created: boolean
}

export interface SessionDestroyRequest extends PluginMessage {
  type: 'session.destroy'
  sessionId: string
}

/**
 * Forward a complete turn (user message + assistant response) from
 * the external client to CassiCore for intelligence processing.
 * This is the primary data ingestion path for observer-mode plugins
 * (plugins that observe an external agent's conversation).
 */
export interface TurnCompleteEvent extends PluginMessage {
  type: 'turn.complete'
  sessionId: string
  userMessage: string
  assistantResponse: string
  model?: string
  tokens?: TokenUsage
}

export interface TokenUsage {
  input?: number
  output?: number
  reasoning?: number
  cache?: { read?: number; write?: number }
}

/**
 * Forward a reasoning/thinking block from the external agent.
 * CassiCore's ThoughtObserver uses these to detect patterns.
 */
export interface ReasoningEvent extends PluginMessage {
  type: 'reasoning'
  sessionId: string
  text: string
  model?: string
}

/**
 * Forward streaming tokens for real-time observation.
 * Used by the focus tracker and session health monitor.
 */
export interface TokenStreamEvent extends PluginMessage {
  type: 'token.stream'
  sessionId: string
  delta: string
  kind: 'token' | 'thinking'
}

/**
 * Forward tool invocation/result events from the external agent.
 */
export interface ToolEvent extends PluginMessage {
  type: 'tool.call' | 'tool.result'
  sessionId: string
  toolName: string
  /** For tool.call: the arguments. For tool.result: { isError: boolean } */
  data?: Record<string, unknown>
}


// Layer 1: Events

/** Subscribe to CassiCore events (SSE stream) */
export interface EventSubscribeRequest extends PluginMessage {
  type: 'events.subscribe'
  /** Event type patterns to subscribe to (glob-style). Default: all events. */
  filter?: string[]
}

/** A CassiCore event forwarded to the plugin */
export interface DaemonEvent {
  type: string
  data: Record<string, unknown>
  timestamp: number
}


// Layer 2: Context

/**
 * Request enriched system context for injection into the model's system prompt.
 * CassiCore assembles SOUL.md, cognitive signals, thinker insights, dialectic
 * state, team status, cross-session patterns, etc.
 */
export interface ContextRequest extends PluginMessage {
  type: 'context.get'
  sessionId: string
  /** Model's context window size (tokens) */
  contextLimit?: number
  /** Current tokens used in the context window */
  tokensUsed?: number
  /** Whether to include full context or slim version */
  slim?: boolean
}

export interface ContextResponse {
  /** Structured daemon context payload (focus states, teams, thinker state, etc.) */
  context: unknown
  /** Ready-to-inject cognitive prompt parts for the target session */
  cognitive: string[]
  /** Live system snapshot useful for adaptive clients */
  cognitiveStatus: unknown
}

/**
 * Report context pressure from the client.
 * CassiCore uses this for PCPM decisions and thinker directives.
 */
export interface PressureReportEvent extends PluginMessage {
  type: 'pressure.report'
  sessionId: string
  /** Context pressure ratio (0-1): tokensUsed / contextLimit */
  pressure: number
  contextLimit: number
  /** Estimated active tokens in the context window */
  activeTokens?: number
}

/**
 * Request the current thinker context directive (if any).
 * Thinker writes directives after analyzing the working state.
 */
export interface DirectiveRequest extends PluginMessage {
  type: 'directive.get'
  sessionId: string
}

export interface DirectiveResponse {
  /** Chunks to collapse (IDs) */
  collapse: string[]
  /** Chunks to remove (IDs) */
  remove: string[]
  /** Chunks to pin (IDs) */
  pin: string[]
  /** Reason for the directive */
  reason: string
  /** When the directive was created */
  timestamp: number
}


// Layer 2: Memory / KV

export interface KVGetRequest extends PluginMessage {
  type: 'kv.get'
  key: string
}

export interface KVSetRequest extends PluginMessage {
  type: 'kv.set'
  key: string
  value: unknown
  ttl?: number
}

export interface MemorySearchRequest extends PluginMessage {
  type: 'memory.search'
  query: string
  limit?: number
}

export interface MemoryStoreRequest extends PluginMessage {
  type: 'memory.store'
  content: string
  tags?: string[]
}


// Layer 2: Chunks

/**
 * Store collapsed/removed chunk content for later retrieval.
 * The client collapses chunks locally and stores the original content
 * in CassiCore so it can be restored on demand.
 */
export interface ChunkStoreRequest extends PluginMessage {
  type: 'chunk.store'
  sessionId: string
  chunks: StoredChunk[]
}

export interface StoredChunk {
  id: string
  content: string
  role: string
  type: string
  toolName?: string
  tokens: number
  preview: string
}

/**
 * Retrieve stored chunk content (for _chunk_open equivalent).
 */
export interface ChunkExpandRequest extends PluginMessage {
  type: 'chunk.expand'
  sessionId: string
  chunkIds: string[]
}


// Layer 3: Tools

/**
 * Register custom tools that the model can invoke through the plugin.
 * The plugin is responsible for executing the tool and returning results.
 */
export interface ToolRegisterRequest extends PluginMessage {
  type: 'tool.register'
  tools: ToolDefinition[]
}

export interface ToolDefinition {
  /** Tool name (must be unique within the plugin's namespace) */
  name: string
  /** Human-readable description */
  description: string
  /** JSON Schema for the tool's parameters */
  parameters: Record<string, unknown>
}

/**
 * CassiCore invokes a registered tool — plugin must execute and respond.
 */
export interface ToolInvokeRequest {
  type: 'tool.invoke'
  toolName: string
  args: Record<string, unknown>
  /** Correlation ID — plugin must include this in the response */
  callId: string
  sessionId: string
}

export interface ToolInvokeResponse extends PluginMessage {
  type: 'tool.invoke.result'
  callId: string
  result: unknown
  isError?: boolean
}


// Layer 3: Intelligence

export interface IntelligenceStatusRequest extends PluginMessage {
  type: 'intelligence.status'
}

export interface EnrichRequest extends PluginMessage {
  type: 'intelligence.enrich'
  query: string
  sessionId?: string
}

/**
 * Ingest events into the intelligence layer for processing by
 * the thinker, focus tracker, session health monitor, etc.
 */
export interface IngestRequest extends PluginMessage {
  type: 'intelligence.ingest'
  sessionId: string
  events: IntelligenceEvent[]
}

export interface IntelligenceEvent {
  type: string
  sessionId?: string
  timestamp: number
  [key: string]: unknown
}

/**
 * Post the current working state for thinker analysis.
 * The thinker reads this to understand what the agent is working on
 * and what chunks are most/least important.
 */
export interface WorkingStateEvent extends PluginMessage {
  type: 'working-state.post'
  sessionId: string
  state: WorkingState
}

export interface WorkingState {
  turnCount: number
  pressure: number
  contextLimit: number
  tier: string
  mode: string
  focusTopic: string
  activeFiles: string[]
  topConsumers?: string[]
  collapseCandidates?: Array<{ id: string; tool: string; tokens: number; age: number }>
  chunkCount?: number
  activeTokens?: number
}


// Session archiving

/**
 * Archive conversation messages for long-term storage and retrieval.
 * Used during compaction to preserve conversation history.
 */
export interface ArchiveRequest extends PluginMessage {
  type: 'session.archive'
  sessionId: string
  messages: ArchiveMessage[]
}

export interface ArchiveMessage {
  role: string
  content: string | Array<{ type: string; text?: string }>
}

/**
 * Request CassiCore to generate a compaction summary.
 * CassiCore uses its own model to summarize the conversation,
 * incorporating memory and cognitive context.
 */
export interface CompactRequest extends PluginMessage {
  type: 'session.compact'
  sessionId: string
  messages: ArchiveMessage[]
}

export interface CompactResponse {
  summary: string
  model: string
  tokensUsed: number
  hasMemory: boolean
  hasCognitive: boolean
}


// Session index

/**
 * Index conversation messages for paragraph-level full-text search.
 * Enables cassi_resolve_ref and session index_search.
 */
export interface IndexRequest extends PluginMessage {
  type: 'session.index'
  sessionId: string
  messages: Array<{
    role: 'user' | 'assistant' | 'system' | 'tool'
    content: string
  }>
}

export interface IndexSearchRequest extends PluginMessage {
  type: 'session.index.search'
  query: string
}

export interface ResolveRefRequest extends PluginMessage {
  type: 'session.resolve_ref'
  ref: string
}


// Discriminated union

/** All possible plugin → CassiCore messages */
export type PluginToCore =
  | SessionCreateRequest
  | SessionDestroyRequest
  | TurnCompleteEvent
  | ReasoningEvent
  | TokenStreamEvent
  | ToolEvent
  | EventSubscribeRequest
  | ContextRequest
  | PressureReportEvent
  | DirectiveRequest
  | KVGetRequest
  | KVSetRequest
  | MemorySearchRequest
  | MemoryStoreRequest
  | ChunkStoreRequest
  | ChunkExpandRequest
  | ToolRegisterRequest
  | ToolInvokeResponse
  | IntelligenceStatusRequest
  | EnrichRequest
  | IngestRequest
  | WorkingStateEvent
  | ArchiveRequest
  | CompactRequest
  | IndexRequest
  | IndexSearchRequest
  | ResolveRefRequest

/** All possible CassiCore → plugin messages */
export type CoreToPlugin =
  | DaemonEvent
  | ToolInvokeRequest
  | { type: 'heartbeat'; timestamp: number }
  | { type: 'error'; message: string; requestId?: string }
