/**
 * Phase 3+ types: Providers, Channels, Sessions, Turn pipeline, Tool execution
 */

// ─── Content Blocks (for tool-use conversation turns) ────────────────────────

export type ContentBlock =
  | { type: 'text'; text: string }
  | { type: 'tool_use'; id: string; name: string; input: Record<string, unknown> }
  | { type: 'tool_result'; tool_use_id: string; content: string; is_error?: boolean }

// ─── Image Attachments ────────────────────────────────────────────────────────

export type ImageMediaType = 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp'

export interface ImageAttachment {
  /** base64-encoded image bytes */
  data: string
  mediaType: ImageMediaType
  /** Optional human label (e.g. filename or Telegram file_id) */
  label?: string
}

// ─── Messages ────────────────────────────────────────────────────────────────

export interface Message {
  role: 'user' | 'assistant' | 'system';
  /** Plain text for normal turns; ContentBlock[] when tool use is involved */
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
   * Provider coordination flags understood by the centralized provider.
   * - allowConcurrent: set true to bypass per-session dedup and allow multiple
   *   concurrent requests for the same logical session. Use cautiously.
   * - dedupe: set false to explicitly disable deduplication for this call.
   */
  allowConcurrent?: boolean;
  dedupe?: boolean;
  /**
   * AbortSignal for cancellation support. Passed to provider for early termination.
   */
  signal?: AbortSignal;
  /**
   * Observability: which module/component initiated this request.
   * E.g. 'turn-pipeline', 'thinker', 'subconscious', 'macro-dialectic:yang', 'dialectic'.
   * Read by the provider observability tap and emitted in provider:request_* events.
   */
  source?: string;
  /**
   * Observability: what caused this LLM call — e.g. 'turn', 'tools', 'timer', 'thinker'.
   * Used with `source` to display provenance chains in the LLM stream: `trigger > source`.
   * For deeper chains the trigger itself can be a chain: `trigger: 'tools > thinker'`.
   */
  trigger?: string;
  /**
   * Observability callback: invoked once with provider metadata (including requestId)
   * immediately after the provider assigns a request ID. Enables callers to correlate
   * their outcome events with the exact provider request that produced the output.
   *
   * Usage in cognitive modules:
   * ```ts
   * let requestId: string | undefined
   * await this.infer(prompt, { onMeta: (m) => { requestId = m.requestId } })
   * this.bus.emit({ type: 'thinker:insight', ..., requestId })
   * ```
   */
  onMeta?: (meta: { requestId: string }) => void;
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

// ─── Provider ────────────────────────────────────────────────────────────────

export interface IProvider {
  readonly id: string;
  readonly models: string[];

  /** Stream a completion. Yields chunks until done. */
  complete(messages: Message[], opts: CompletionOpts): AsyncIterable<CompletionChunk>;

  /** Count tokens for a message array (approximate) */
  countTokens(messages: Message[]): Promise<number>;

  /** Check if the provider is reachable */
  ping(): Promise<boolean>;
}

// ─── Channel ─────────────────────────────────────────────────────────────────

export interface InboundMessage {
  id: string;
  sessionId: string;
  channelId: string;
  senderId: string;
  senderName?: string;
  content: string;
  replyToId?: string;
  timestamp: Date;
  /** Images attached to this message (e.g. photos sent via Telegram) */
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

// ─── Session ─────────────────────────────────────────────────────────────────

export interface SessionConfig {
  model: string;
  /** Optional explicit provider ID to pin a provider (e.g. 'pi', 'kimi-coding') */
  providerId?: string;
  /** Optional model name without provider prefix (e.g. 'gpt-5-mini') */
  providerModel?: string;
  systemPrompt?: string;
  thinking?: ThinkingLevel;
  maxContextTokens?: number;
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
  get(sessionId: string): Session | undefined;
  addTurn(sessionId: string, message: Message): void;
  clear(sessionId: string): void;
  delete(sessionId: string): void;
  list(): Session[];
}

// ─── Turn pipeline ────────────────────────────────────────────────────────────

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
  /** Tool execution results with detailed output information */
  tool_outputs?: Array<{
    tool_name: string;
    tool_call_id: string;
    output: string;
    is_error: boolean;
    timestamp: Date;
  }>
}
