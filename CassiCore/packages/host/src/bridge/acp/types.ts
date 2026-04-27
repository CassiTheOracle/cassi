import type {
  CancelNotification,
  ContentBlock,
  InitializeRequest,
  InitializeResponse,
  NewSessionRequest,
  NewSessionResponse,
  PromptRequest,
  PromptResponse,
  SessionNotification,
} from '@zed-industries/agent-client-protocol'

export type ChatStreamEvent =
  | { type: 'token'; token: string }
  | { type: 'response'; text: string; model?: string; tokensUsed?: number; durationMs?: number }
  | { type: 'tool_call'; toolCallId?: string; tool: string; input: unknown }
  | { type: 'tool_result'; toolCallId?: string; tool?: string; isError?: boolean; content?: unknown }
  | { type: 'error'; error: string }

export type StopReason =
  | 'end_turn'
  | 'max_tokens'
  | 'max_turn_requests'
  | 'refusal'
  | 'cancelled'

export type {
  CancelNotification,
  ContentBlock,
  InitializeRequest,
  InitializeResponse,
  NewSessionRequest,
  NewSessionResponse,
  PromptRequest,
  PromptResponse,
  SessionNotification,
}
