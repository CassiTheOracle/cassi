import { BaseProvider } from './base.js'
import type { Message, ContentBlock, CompletionOpts, CompletionChunk } from '../../types/runtime.js'
import { readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const BASE_URL = 'https://api.individual.githubcopilot.com'

const COPILOT_HEADERS = {
  'User-Agent': 'GitHubCopilotChat/0.35.0',
  'Editor-Version': 'vscode/1.107.0',
  'Editor-Plugin-Version': 'copilot-chat/0.35.0',
  'Copilot-Integration-Id': 'vscode-chat',
  'Content-Type': 'application/json',
}

/** Models that use Anthropic Messages API format */
const ANTHROPIC_MODELS = new Set(['claude-sonnet-4.6', 'claude-sonnet-4.5', 'claude-opus-4.6', 'claude-haiku-4.5'])

/**
 * Resolve the live Copilot API token from the OpenClaw credentials cache.
 * The oauth token (ghu_) must first be exchanged for a session token.
 * TODO: implement full token exchange flow for standalone ClaraCore operation.
 */
function resolveCopilotApiToken(oauthToken: string): string {
  try {
    const cachePath = join(homedir(), '.openclaw', 'credentials', 'github-copilot.token.json')
    const cache = JSON.parse(readFileSync(cachePath, 'utf8')) as { token: string; expiresAt: number }
    if (cache.token && cache.expiresAt > Date.now() + 60_000) {
      return cache.token
    }
  } catch { /* fall through */ }
  return oauthToken
}

// ── Message format helpers ────────────────────────────────────────────────────

/**
 * Convert Message.content to Anthropic API format.
 * ContentBlock[] → passed through directly.
 * string → wrapped as [{ type: 'text', text }] for consistency.
 */
function toAnthropicContent(
  msg: Message,
): string | Array<Record<string, unknown>> {
  if (typeof msg.content === 'string') return msg.content
  // ContentBlock[] — convert to Anthropic format
  return (msg.content as ContentBlock[]).map(b => {
    if (b.type === 'text') return { type: 'text', text: b.text }
    if (b.type === 'tool_use') return { type: 'tool_use', id: b.id, name: b.name, input: b.input }
    if (b.type === 'tool_result') return { type: 'tool_result', tool_use_id: b.tool_use_id, content: b.content, is_error: b.is_error }
    return b as Record<string, unknown>
  })
}

/**
 * Convert Message[] to OpenAI format.
 * tool_result blocks → role: 'tool' messages.
 */
function toOpenAIMessages(messages: Message[]): Array<Record<string, unknown>> {
  const out: Array<Record<string, unknown>> = []
  for (const msg of messages) {
    if (typeof msg.content === 'string') {
      out.push({ role: msg.role, content: msg.content })
      continue
    }
    const blocks = msg.content as ContentBlock[]
    // Separate tool_result blocks (become role:'tool' messages) from the rest
    const textBlocks = blocks.filter(b => b.type !== 'tool_result')
    const toolResults = blocks.filter((b): b is Extract<ContentBlock, { type: 'tool_result' }> => b.type === 'tool_result')

    if (textBlocks.length > 0) {
      const text = textBlocks
        .map(b => (b.type === 'text' ? b.text : b.type === 'tool_use' ? `[tool_use:${b.name}]` : ''))
        .join('')
      out.push({ role: msg.role, content: text })
    }
    for (const r of toolResults) {
      out.push({ role: 'tool', tool_call_id: r.tool_use_id, content: r.content })
    }
  }
  return out
}

export class GitHubCopilotProvider extends BaseProvider {
  readonly id = 'github-copilot'
  readonly models = ['claude-sonnet-4.6', 'claude-sonnet-4.5', 'gpt-5-mini', 'claude-opus-4.6']

  constructor(private oauthToken: string) { super() }

  private get token(): string {
    return resolveCopilotApiToken(this.oauthToken)
  }

  async *complete(messages: Message[], opts: CompletionOpts): AsyncIterable<CompletionChunk> {
    const model = opts.model || this.models[0]
    if (ANTHROPIC_MODELS.has(model)) {
      yield* this.completeAnthropic(messages, opts, model)
    } else {
      yield* this.completeOpenAI(messages, opts, model)
    }
  }

  /** Anthropic Messages API format (for Claude models) */
  private async *completeAnthropic(
    messages: Message[],
    opts: CompletionOpts,
    model: string,
  ): AsyncIterable<CompletionChunk> {
    const system = opts.systemPrompt || (
      typeof messages.find(m => m.role === 'system')?.content === 'string'
        ? messages.find(m => m.role === 'system')?.content as string
        : undefined
    )
    const filtered = messages.filter(m => m.role !== 'system')

    const body: Record<string, unknown> = {
      model,
      max_tokens: opts.maxTokens ?? 8192,
      stream: true,
      messages: filtered.map(m => ({ role: m.role, content: toAnthropicContent(m) })),
    }
    if (system) body['system'] = system
    if (opts.thinking === 'high') {
      body['thinking'] = { type: 'enabled', budget_tokens: 8000 }
      body['max_tokens'] = Math.max((opts.maxTokens ?? 16000), 16000)
    } else if (opts.thinking === 'medium') {
      body['thinking'] = { type: 'enabled', budget_tokens: 4000 }
      body['max_tokens'] = Math.max((opts.maxTokens ?? 8192), 8192)
    }
    // Attach tools if provided
    if (opts.tools?.length) {
      body['tools'] = opts.tools
    }

    let res: Response
    try {
      res = await fetch(`${BASE_URL}/v1/messages`, {
        method: 'POST',
        headers: { ...COPILOT_HEADERS, Authorization: `Bearer ${this.token}` },
        body: JSON.stringify(body),
      })
    } catch (err) {
      yield { type: 'error', error: `network error: ${String(err)}` }
      return
    }

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      yield { type: 'error', error: `http ${res.status}: ${text}` }
      return
    }

    const reader = res.body?.getReader()
    if (!reader) { yield { type: 'error', error: 'no response body' }; return }

    const decoder = new TextDecoder()
    let buf = ''
    let totalTokens = 0
    // Track tool use block being accumulated
    let currentTool: { id: string; name: string; inputJson: string } | null = null

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') continue
          try {
            const evt = JSON.parse(data) as Record<string, unknown>
            const evtType = evt['type'] as string

            if (evtType === 'content_block_start') {
              const block = evt['content_block'] as Record<string, unknown>
              if (block?.['type'] === 'tool_use') {
                currentTool = {
                  id: block['id'] as string,
                  name: block['name'] as string,
                  inputJson: '',
                }
              }
            } else if (evtType === 'content_block_delta') {
              const delta = evt['delta'] as Record<string, unknown>
              if (delta?.['type'] === 'text_delta') {
                yield { type: 'token', text: delta['text'] as string }
              } else if (delta?.['type'] === 'thinking_delta') {
                yield { type: 'thinking', text: delta['thinking'] as string }
              } else if (delta?.['type'] === 'input_json_delta' && currentTool) {
                currentTool.inputJson += (delta['partial_json'] as string) ?? ''
              }
            } else if (evtType === 'content_block_stop') {
              if (currentTool) {
                let parsed: Record<string, unknown> = {}
                try { parsed = JSON.parse(currentTool.inputJson) } catch { /* empty input */ }
                yield {
                  type: 'tool_use',
                  toolCall: { id: currentTool.id, name: currentTool.name, input: parsed },
                }
                currentTool = null
              }
            } else if (evtType === 'message_delta') {
              const usage = evt['usage'] as Record<string, unknown>
              if (usage?.['output_tokens']) totalTokens = usage['output_tokens'] as number
            } else if (evtType === 'message_stop') {
              yield { type: 'done', tokensUsed: totalTokens, model }
            }
          } catch { /* skip malformed events */ }
        }
      }
    } finally {
      reader.releaseLock()
    }
  }

  /** OpenAI Chat Completions format (for GPT models) */
  private async *completeOpenAI(
    messages: Message[],
    opts: CompletionOpts,
    model: string,
  ): AsyncIterable<CompletionChunk> {
    const body: Record<string, unknown> = {
      model,
      messages: toOpenAIMessages(messages),
      stream: true,
      max_tokens: opts.maxTokens ?? 4096,
    }
    if (opts.tools?.length) {
      body['tools'] = opts.tools.map(t => ({
        type: 'function',
        function: { name: t.name, description: t.description, parameters: t.input_schema },
      }))
      body['tool_choice'] = 'auto'
    }

    let res: Response
    try {
      res = await fetch(`${BASE_URL}/chat/completions`, {
        method: 'POST',
        headers: { ...COPILOT_HEADERS, Authorization: `Bearer ${this.token}` },
        body: JSON.stringify(body),
      })
    } catch (err) {
      yield { type: 'error', error: `network error: ${String(err)}` }
      return
    }

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      yield { type: 'error', error: `http ${res.status}: ${text}` }
      return
    }

    const reader = res.body?.getReader()
    if (!reader) { yield { type: 'error', error: 'no response body' }; return }

    const decoder = new TextDecoder()
    let buf = ''
    // Accumulate tool_calls across streaming chunks
    const toolCallAccum: Map<number, { id: string; name: string; argsJson: string }> = new Map()

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') {
            // Flush accumulated tool calls
            for (const tc of toolCallAccum.values()) {
              let parsed: Record<string, unknown> = {}
              try { parsed = JSON.parse(tc.argsJson) } catch { /* empty */ }
              yield { type: 'tool_use', toolCall: { id: tc.id, name: tc.name, input: parsed } }
            }
            toolCallAccum.clear()
            yield { type: 'done', model }
            continue
          }
          try {
            const evt = JSON.parse(data) as Record<string, unknown>
            const choices = evt['choices'] as Array<Record<string, unknown>>
            const delta = choices?.[0]?.['delta'] as Record<string, unknown>
            if (!delta) continue

            if (delta['content']) {
              yield { type: 'token', text: delta['content'] as string }
            }
            if (delta['tool_calls']) {
              const tcs = delta['tool_calls'] as Array<Record<string, unknown>>
              for (const tc of tcs) {
                const idx = tc['index'] as number
                const fn = tc['function'] as Record<string, unknown> | undefined
                if (!toolCallAccum.has(idx)) {
                  toolCallAccum.set(idx, {
                    id: (tc['id'] as string) ?? `call_${idx}`,
                    name: (fn?.['name'] as string) ?? '',
                    argsJson: '',
                  })
                }
                const acc = toolCallAccum.get(idx)!
                if (fn?.['name']) acc.name = fn['name'] as string
                if (fn?.['arguments']) acc.argsJson += fn['arguments'] as string
                if (tc['id']) acc.id = tc['id'] as string
              }
            }
          } catch { /* skip malformed */ }
        }
      }
    } finally {
      reader.releaseLock()
    }
  }

  async countTokens(messages: Message[]): Promise<number> {
    return this.estimateTokens(messages)
  }

  async ping(): Promise<boolean> {
    try {
      const res = await fetch(`${BASE_URL}/v1/models`, {
        headers: { ...COPILOT_HEADERS, Authorization: `Bearer ${this.token}` },
      })
      return res.ok
    } catch { return false }
  }
}
