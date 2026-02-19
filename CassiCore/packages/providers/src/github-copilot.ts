import { BaseProvider } from './base.js'
import type { Message, CompletionOpts, CompletionChunk } from '../../types/runtime.js'
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
  // Try to read from OpenClaw's cached token (works while OpenClaw is running)
  try {
    const cachePath = join(homedir(), '.openclaw', 'credentials', 'github-copilot.token.json')
    const cache = JSON.parse(readFileSync(cachePath, 'utf8')) as { token: string; expiresAt: number }
    if (cache.token && cache.expiresAt > Date.now() + 60_000) {
      return cache.token
    }
  } catch { /* fall through */ }
  // Fall back to oauth token directly (may work for some endpoints)
  return oauthToken
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
    model: string
  ): AsyncIterable<CompletionChunk> {
    const system = opts.systemPrompt || messages.find(m => m.role === 'system')?.content
    const filtered = messages.filter(m => m.role !== 'system')

    const body: Record<string, unknown> = {
      model,
      max_tokens: opts.maxTokens ?? 8192,
      stream: true,
      messages: filtered.map(m => ({ role: m.role, content: m.content })),
    }
    if (system) body['system'] = system
    if (opts.thinking === 'high') {
      body['thinking'] = { type: 'enabled', budget_tokens: 8000 }
      body['max_tokens'] = Math.max((opts.maxTokens ?? 16000), 16000)
    } else if (opts.thinking === 'medium') {
      body['thinking'] = { type: 'enabled', budget_tokens: 4000 }
      body['max_tokens'] = Math.max((opts.maxTokens ?? 8192), 8192)
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
            const type = evt['type'] as string
            if (type === 'content_block_delta') {
              const delta = evt['delta'] as Record<string, unknown>
              if (delta?.['type'] === 'text_delta') {
                yield { type: 'token', text: delta['text'] as string }
              }
            } else if (type === 'message_delta') {
              const usage = (evt['usage'] as Record<string, unknown>)
              if (usage?.['output_tokens']) totalTokens = usage['output_tokens'] as number
            } else if (type === 'message_stop') {
              yield { type: 'done', tokensUsed: totalTokens, model }
            }
          } catch { /* skip malformed */ }
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
    model: string
  ): AsyncIterable<CompletionChunk> {
    const body: Record<string, unknown> = {
      model,
      messages: messages.map(m => ({ role: m.role, content: m.content })),
      stream: true,
      max_tokens: opts.maxTokens ?? 4096,
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
          if (data === '[DONE]') { yield { type: 'done', model }; continue }
          try {
            const evt = JSON.parse(data) as Record<string, unknown>
            const choices = evt['choices'] as Array<Record<string, unknown>>
            const delta = choices?.[0]?.['delta'] as Record<string, unknown>
            if (delta?.['content']) yield { type: 'token', text: delta['content'] as string }
          } catch { /* skip */ }
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
