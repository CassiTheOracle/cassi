/**
 * Phase 3+ types: Providers, Channels, Sessions, Turn pipeline, Tool execution
 */


export type ContentBlock =
  | { type: 'text'; text: string }
  | { type: 'tool_use'; id: string; name: string; input: Record<string, unknown> }
  | { type: 'tool_result'; tool_use_id: string; content: string; is_error?: boolean }


export type ImageMediaType = 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp'

export interface ImageAttachment {
  /** Base64-encoded image bytes */
  data: string
  mediaType: ImageMediaType
  /** Human-readable label (e.g. filename or Telegram file_id) */
  label?: string
}


export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string | ContentBlock[];
  name?: string;
}

export type ThinkingLevel = 'none' | 'low' | 'medium' | 'high';

export interface CompletionOpts {
  model: string;
  maxTokens?: number;
  temperature?: number;
  thinking?: ThinkingLevel;
  systemPrompt?: string;
  stream?: boolean;
  /** Tool schemas to pass to the model. Anthropic format — providers convert as needed. */
  tools?: Array<{
    name: string;
    description: string;
    input_schema: Record<string, unknown>;
  }>
  /**
   * Bypass per-session dedup to allow concurrent requests for the same logical session.
   * Use cautiously.
   */
  allowConcurrent?: boolean;
  /** Explicitly disable deduplication for this call */
  dedupe?: boolean;
  /** AbortSignal for cancellation */
  signal?: AbortSignal;
  /**
   * Which module/component initiated this request.
   * E.g. 'turn-pipeline', 'thinker', 'subconscious', 'macro-dialectic:yang', 'dialectic'.
   * Emitted in provider:request_* events for observability.
   */
  source?: string;
  /**
   * What caused this LLM call — e.g. 'turn', 'tools', 'timer', 'thinker'.
   * Combined with `source` for provenance: `trigger > source`.
   * For deeper chains: `trigger: 'tools > thinker'`.
   */
  trigger?: string;
  /**
   * Called immediately after the provider assigns a request ID.
   * Enables correlating outcome events with the exact provider request.
   *
   * Usage:
   * ```ts
   * let requestId: string | undefined
   * await this.infer(prompt, { onMeta: (m) => { requestId = m.requestId } })
   * this.bus.emit({ type: 'thinker:insight', ..., requestId })
   * ```
   */
  onMeta?: (meta: { requestId: string }) => void;
  /**
   * Session ID for prompt logging.
   * Nullable — background intelligence calls may not have one.
   */
  sessionId?: string;
  /**
   * Keeps the SDK session alive across successive complete() calls.
   * All iterations within the same warm session are part of a single premium request.
   *
   * The key identifies the logical session — e.g. `lumen:session123:yang`.
   * Falls back to create-and-destroy pattern when not set.
   */
  warmSessionKey?: string;
}

export interface CompletionChunk {
  type: 'token' | 'thinking' | 'done' | 'error' | 'tool_use';
  text?: string;
  tokensUsed?: number;
  /** Token usage breakdown (available on 'done' chunks) */
  tokenBreakdown?: {
    input: number;
    output: number;
    cacheRead: number;
    cacheWrite: number;
  };
  model?: string;
  error?: string;
  /** Present when type === 'tool_use' */
  toolCall?: {
    id: string;
    name: string;
    input: Record<string, unknown>;
  }
}


export interface IProvider {
  readonly id: string;
  readonly models: string[];

  /** Stream a completion */
  complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk>;

  /** Count tokens for a message array */
  countTokens(messages: Message[]): Promise<number>;

  /** Health check */
  ping(): Promise<boolean>;
}


export interface InboundMessage {
  id: string;
  sessionId: string;
  channelId: string;
  senderId: string;
  senderName?: string;
  content: string;
  replyToId?: string;
  timestamp: Date;
  /** Attached images (e.g. Telegram photos) */
  attachments?: ImageAttachment[];
  metadata?: Record<string, unknown>;
}

export interface OutboundMessage {
  sessionId: string;
  channelId: string;
  content: string;
  replyToId?: string;
  metadata?: Record<string, unknown>;
}

export interface IChannel {
  readonly id: string;
  send(message: OutboundMessage): Promise<void>;
  onMessage(handler: (msg: InboundMessage) => void): void;
  start(): Promise<void>;
  stop(): Promise<void>;
}


export interface SessionConfig {
  model: string;
  /** Explicit provider ID (e.g. 'pi', 'kimi-coding') */
  providerId?: string;
  /** Model name without provider prefix (e.g. 'gpt-5-mini') */
  providerModel?: string;
  systemPrompt?: string;
  thinking?: ThinkingLevel;
  maxContextTokens?: number;
  /**
   * Session is never pruned by idle-time expiry or LRU eviction.
   * Used for persistent module sessions that survive daemon restarts.
   */
  permanent?: boolean;
}

export interface Session {
  id: string;
  channelId: string;
  senderId: string;
  history: Message[];
  config: SessionConfig;
  createdAt: Date;
  lastActiveAt: Date;
  tokenCount: number;
}

export interface ISessionManager {
  getOrCreate(channelId: string, senderId: string, config?: Partial<SessionConfig>): Session;
  getOrCreateById(stableId: string, channelId: string, senderId: string, config?: Partial<SessionConfig>): Session;
  get(sessionId: string): Session | undefined;
  addTurn(sessionId: string, message: Message): void;
  clear(sessionId: string): void;
  delete(sessionId: string): void;
  list(): Session[];
}


export interface TurnContext {
  session: Session;
  inbound: InboundMessage;
  messages: Message[];
  opts: CompletionOpts;
}

export interface TurnResult {
  response: string;
  tokensUsed: number;
  model: string;
  durationMs: number;
  thinkerInjection?: string;
  toolCalls?: Array<{ name: string; durationMs: number }>
  tool_outputs?: Array<{
    tool_name: string;
    tool_call_id: string;
    output: string;
    is_error: boolean;
    timestamp: Date;
  }>
}
