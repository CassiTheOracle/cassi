/**
 * CassiCore Runtime Types (local copy for tight integration)
 * 
 * These types mirror the CassiCore runtime types to avoid cross-module imports.
 */

// Content blocks for tool-use conversation turns
export type ContentBlock =
  | { type: 'text'; text: string }
  | { type: 'tool_use'; id: string; name: string; input: Record<string, unknown> }
  | { type: 'tool_result'; tool_use_id: string; content: string; is_error?: boolean };

// Image attachments
export type ImageMediaType = 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp';

export interface ImageAttachment {
  data: string;
  mediaType: ImageMediaType;
  label?: string;
}

// Messages
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
  tools?: Array<{
    name: string;
    description: string;
    input_schema: Record<string, unknown>;
  }>;
  allowConcurrent?: boolean;
  dedupe?: boolean;
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
  toolCall?: {
    id: string;
    name: string;
    input: Record<string, unknown>;
  };
}

// Provider interface
export interface IProvider {
  readonly id: string;
  readonly models: string[];
  complete(messages: Message[], opts: CompletionOpts, attachments?: ImageAttachment[], signal?: AbortSignal): AsyncIterable<CompletionChunk>;
  countTokens(messages: Message[]): Promise<number>;
  ping(signal?: AbortSignal): Promise<boolean>;
}
