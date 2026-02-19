/**
 * Phase 3 types: Providers, Channels, Sessions, Turn pipeline
 */

// ─── Messages ────────────────────────────────────────────────────────────────

export interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  name?: string;
}

export type ThinkingLevel = "none" | "low" | "medium" | "high";

export interface CompletionOpts {
  model: string;
  maxTokens?: number;
  temperature?: number;
  thinking?: ThinkingLevel;
  systemPrompt?: string;
  stream?: boolean;
}

export interface CompletionChunk {
  type: "token" | "thinking" | "done" | "error";
  text?: string;
  tokensUsed?: number;
  model?: string;
  error?: string;
}

// ─── Provider ────────────────────────────────────────────────────────────────

export interface IProvider {
  readonly id: string;
  readonly models: string[];

  /** Stream a completion. Yields chunks until done. */
  complete(
    messages: Message[],
    opts: CompletionOpts
  ): AsyncIterable<CompletionChunk>;

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

  /** Send a message to the channel */
  send(message: OutboundMessage): Promise<void>;

  /** Register handler for incoming messages */
  onMessage(handler: (msg: InboundMessage) => void): void;

  /** Start listening */
  start(): Promise<void>;

  /** Stop listening */
  stop(): Promise<void>;
}

// ─── Session ─────────────────────────────────────────────────────────────────

export interface SessionConfig {
  model: string;
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
  /** Get or create session for a sender+channel combo */
  getOrCreate(channelId: string, senderId: string, config?: Partial<SessionConfig>): Session;

  /** Get session by id */
  get(sessionId: string): Session | undefined;

  /** Update session history */
  addTurn(sessionId: string, message: Message): void;

  /** Clear session history (but keep session) */
  clear(sessionId: string): void;

  /** Delete session entirely */
  delete(sessionId: string): void;

  /** List all active sessions */
  list(): Session[];
}

// ─── Turn pipeline ────────────────────────────────────────────────────────────

export interface TurnContext {
  session: Session;
  inbound: InboundMessage;
  messages: Message[];   // full history + current message
  opts: CompletionOpts;
}

export interface TurnResult {
  response: string;
  tokensUsed: number;
  model: string;
  durationMs: number;
  thinkerInjection?: string;  // pre-turn context from Thinker
}
