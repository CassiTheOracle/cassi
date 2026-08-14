export interface HermesSessionRow {
  id: string
  source: string
  user_id: string | null
  model: string | null
  started_at: number
  ended_at: number | null
  end_reason: string | null
  message_count: number
  tool_call_count: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  reasoning_tokens: number
  estimated_cost_usd: number | null
  actual_cost_usd: number | null
  title: string | null
  api_call_count: number
  parent_session_id: string | null
}

export interface HermesMessageRow {
  id: number
  session_id: string
  role: string
  content: string | null
  tool_call_id: string | null
  tool_calls: string | null
  tool_name: string | null
  timestamp: number
  token_count: number | null
  finish_reason: string | null
  reasoning: string | null
}

export interface HermesSessionDetail extends HermesSessionRow {
  messages: HermesMessageRow[]
  child_sessions: Array<{ id: string; title: string | null; message_count: number; started_at: number }>
}

export interface ToolDefinition {
  name: string
  description: string
  inputSchema: {
    type: 'object'
    properties: Record<string, unknown>
    required?: string[]
  }
}

export interface SearchResult {
  session_id: string
  role: string
  content_preview: string
  timestamp: number
  match_type: string
}

export type ToolHandler = (
  adminUrl: string,
  toolName: string,
  args: any,
  hermesDbPath: string,
  logger: any,
) => Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: boolean }>
