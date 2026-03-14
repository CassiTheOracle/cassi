import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join, dirname } from 'node:path'

import { signalPromise } from '../utils/abort.js'

import { BaseProvider } from './base.js'

import type { Message, ContentBlock, CompletionOpts, CompletionChunk, ImageAttachment } from '../../types/runtime.js'

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

function credentialsCachePath(profileId?: string) {
  if (profileId) return join(homedir(), '.cassicore', 'credentials', `github-copilot.token.${profileId}.json`)
  return join(homedir(), '.cassicore', 'credentials', 'github-copilot.token.json')
}

/**
 * Exchange an OAuth token for a Copilot API session token via
 * https://api.github.com/copilot_internal/v2/token
 *
 * The session token is cached to disk so it survives daemon restarts
 * and is refreshed when it expires.
 */
async function exchangeOAuthForCopilotToken(oauthToken: string, profileId?: string): Promise<string> {
  const CREDENTIALS_CACHE_PATH = credentialsCachePath(profileId)
  // Check disk cache first
  try {
    const cache = JSON.parse(readFileSync(CREDENTIALS_CACHE_PATH, 'utf8')) as { token: string; expiresAt: number }
    if (cache.token && cache.expiresAt > Date.now() + 60_000) {
      return cache.token
    }
  } catch { /* fall through */ }

  // Exchange OAuth token for Copilot session token
  const res = await fetch('https://api.github.com/copilot_internal/v2/token', {
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${oauthToken}`,
      'User-Agent': 'GitHubCopilotChat/0.35.0',
      'Editor-Version': 'vscode/1.107.0',
      'Editor-Plugin-Version': 'copilot-chat/0.35.0',
      'Copilot-Integration-Id': 'vscode-chat',
    },
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Copilot token exchange failed (${res.status}): ${text}`)
  }

  const data = await res.json() as { token: string; expires_at: number }
  if (!data.token || !data.expires_at) {
    throw new Error('Invalid Copilot token response')
  }

  const expiresAt = data.expires_at * 1000 - 5 * 60 * 1000 // 5min buffer

  // Cache to disk
  try {
    mkdirSync(dirname(CREDENTIALS_CACHE_PATH), { recursive: true })
    writeFileSync(CREDENTIALS_CACHE_PATH, JSON.stringify({ token: data.token, expiresAt }))
  } catch { /* non-fatal */ }

  return data.token
}

/**
 * Resolve the live Copilot API token from the CassiCore credentials cache.
 * Synchronous fallback — used when the async exchange hasn't happened yet.
 */
function resolveCopilotApiToken(oauthToken: string, profileId?: string): string {
  const CREDENTIALS_CACHE_PATH = credentialsCachePath(profileId)
  try {
    const cache = JSON.parse(readFileSync(CREDENTIALS_CACHE_PATH, 'utf8')) as { token: string; expiresAt: number }
    if (cache.token && cache.expiresAt > Date.now() + 60_000) {
      return cache.token
    }
  } catch { /* fall through */ }
  return oauthToken
}

// ── Message format helpers ────────────────────────────────────────────────────

/**
 * Convert Message.content + optional image attachments to Anthropic API format.
 *
 * Anthropic multimodal content is an array of blocks:
 *   [{ type: 'image', source: { type: 'base64', media_type, data } }, ..., { type: 'text', text }]
 *
 * Images are prepended before the text block so the model sees them first.
 */
function toAnthropicContent(
  msg: Message,
  attachments?: ImageAttachment[],
): string | Array<Record<string, unknown>> {
  const imageBlocks: Array<Record<string, unknown>> = (attachments ?? []).map(att => ({
    type: 'image',
    source: {
      type: 'base64',
      media_type: att.mediaType,
      data: att.data,
    },
  }))

  if (typeof msg.content === 'string') {
    if (imageBlocks.length === 0) return msg.content
    const contentParts: Array<Record<string, unknown>> = [...imageBlocks]
    if (msg.content) contentParts.push({ type: 'text', text: msg.content })
    return contentParts
  }

  // ContentBlock[] — convert to Anthropic format
  const contentBlocks = (msg.content as ContentBlock[]).map(b => {
    if (b.type === 'text') return { type: 'text', text: b.text }
    if (b.type === 'tool_use') return { type: 'tool_use', id: b.id, name: b.name, input: b.input }
    if (b.type === 'tool_result') return { type: 'tool_result', tool_use_id: b.tool_use_id, content: b.content, is_error: b.is_error }
    return b as Record<string, unknown>
  })

  return imageBlocks.length > 0 ? [...imageBlocks, ...contentBlocks] : contentBlocks
}

/**
 * Convert Message[] to OpenAI format.
 * Images are injected as image_url content parts (base64 data URIs).
 * tool_use blocks → tool_calls array on assistant messages.
 * tool_result blocks → role: 'tool' messages with tool_call_id.
 */
function toOpenAIMessages(
  messages: Message[],
  attachmentsByIndex?: Map<number, ImageAttachment[]>,
): Array<Record<string, unknown>> {
  const out: Array<Record<string, unknown>> = []

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i]
    const attachments = attachmentsByIndex?.get(i) ?? []

    if (typeof msg.content === 'string') {
      if (attachments.length === 0) {
        out.push({ role: msg.role, content: msg.content })
      } else {
        // Multimodal: mix image_url parts + text part
        const parts: Array<Record<string, unknown>> = attachments.map(att => ({
          type: 'image_url',
          image_url: { url: `data:${att.mediaType};base64,${att.data}` },
        }))
        if (msg.content) parts.push({ type: 'text', text: msg.content })
        out.push({ role: msg.role, content: parts })
      }
      continue
    }

    const blocks = msg.content as ContentBlock[]
    const toolUseBlocks = blocks.filter(
      (b): b is Extract<ContentBlock, { type: 'tool_use' }> => b.type === 'tool_use'
    )
    const toolResults = blocks.filter(
      (b): b is Extract<ContentBlock, { type: 'tool_result' }> => b.type === 'tool_result'
    )
    const textBlocks = blocks.filter(b => b.type === 'text')

    // Assistant messages with tool_use blocks → OpenAI tool_calls format
    if (toolUseBlocks.length > 0) {
      const textContent = textBlocks
        .map(b => b.type === 'text' ? b.text : '')
        .join('')

      const toolCalls = toolUseBlocks.map(b => ({
        id: b.id,
        type: 'function',
        function: {
          name: b.name,
          arguments: JSON.stringify(b.input ?? {}),
        },
      }))

      const assistantMsg: Record<string, unknown> = {
        role: 'assistant',
        tool_calls: toolCalls,
      }
      // OpenAI allows content to be null/empty when tool_calls are present
      if (textContent) assistantMsg.content = textContent
      else assistantMsg.content = null

      if (attachments.length > 0) {
        const parts: Array<Record<string, unknown>> = attachments.map(att => ({
          type: 'image_url',
          image_url: { url: `data:${att.mediaType};base64,${att.data}` },
        }))
        if (textContent) parts.push({ type: 'text', text: textContent })
        assistantMsg.content = parts
      }

      out.push(assistantMsg)
    } else if (textBlocks.length > 0 && toolResults.length === 0) {
      // Pure text message (no tool blocks)
      const textContent = textBlocks
        .map(b => b.type === 'text' ? b.text : '')
        .join('')

      if (attachments.length > 0) {
        const parts: Array<Record<string, unknown>> = attachments.map(att => ({
          type: 'image_url',
          image_url: { url: `data:${att.mediaType};base64,${att.data}` },
        }))
        if (textContent) parts.push({ type: 'text', text: textContent })
        out.push({ role: msg.role, content: parts })
      } else {
        out.push({ role: msg.role, content: textContent })
      }
    }

    // tool_result blocks → OpenAI role: 'tool' messages with tool_call_id
    for (const r of toolResults) {
      out.push({ role: 'tool', tool_call_id: r.tool_use_id, content: r.content })
    }
  }

  return out
}

export class GitHubCopilotProvider extends BaseProvider {
  readonly id = 'github-copilot'
  readonly models = ['gpt-4o', 'gpt-4o-mini', 'gemini-3-flash-preview', 'gemini-3-pro-preview', 'claude-sonnet-4.6', 'claude-sonnet-4.5', 'claude-opus-4.6', 'claude-haiku-4.5', 'gpt-5-mini']

  // Caching for ping() — prevents health-check spam
  private lastPingTime = 0
  private lastPingResult = false
  private readonly PING_CACHE_MS = 60000  // 60 second cache

  // Caching for token — prevents file read on every request
  private cachedToken: string | null = null
  private tokenExpiresAt = 0
  private readonly TOKEN_REFRESH_BUFFER_MS = 60000  // Refresh 60s before expiry
  private tokenExchangePromise: Promise<void> | null = null

  constructor(private oauthToken: string, private profileId?: string) {
    super()
    // Kick off async token exchange immediately — subsequent calls wait on this
    this.tokenExchangePromise = this.refreshCopilotToken().catch(() => {})
  }

  /** Exchange OAuth token for a Copilot session token (async, cached to disk) */
  private async refreshCopilotToken(): Promise<void> {
    try {
      const token = await exchangeOAuthForCopilotToken(this.oauthToken, this.profileId)
      this.cachedToken = token
      try {
        const cache = JSON.parse(readFileSync(credentialsCachePath(this.profileId), 'utf8')) as { expiresAt: number }
        this.tokenExpiresAt = cache.expiresAt
      } catch {
        this.tokenExpiresAt = Date.now() + 25 * 60 * 1000
      }
    } catch {
      // Fall back to synchronous resolution
    }
  }

  private get token(): string {
    // Use cached token if still valid (with buffer)
    if (this.cachedToken && this.tokenExpiresAt > Date.now() + this.TOKEN_REFRESH_BUFFER_MS) {
      return this.cachedToken
    }

    const resolved = resolveCopilotApiToken(this.oauthToken, this.profileId)
    this.cachedToken = resolved

    // Try to parse expiry from the token cache file
    try {
      const cachePath = credentialsCachePath(this.profileId)
      const cache = JSON.parse(readFileSync(cachePath, 'utf8')) as { expiresAt: number }
      this.tokenExpiresAt = cache.expiresAt
    } catch {
      this.tokenExpiresAt = Date.now() + 25 * 60 * 1000  // Default 25min
    }

    return resolved
  }

  /** Fetch with timeout and optional external abort signal */
  private async fetchWithTimeout(
    url: string,
    options: RequestInit,
    timeoutMs = 30000,
    externalSignal?: AbortSignal,
  ): Promise<Response> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    try {
      if (externalSignal) {
        if (externalSignal.aborted) try { controller.abort() } catch {}
        else signalPromise(externalSignal).then(() => { try { controller.abort() } catch {} }).catch(() => {})
      }

      const res = await fetch(url, { ...options, signal: controller.signal })
      return res
    } finally {
      clearTimeout(timeoutId)
    }
  }

  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    // Ensure the initial token exchange has completed before first request
    if (this.tokenExchangePromise) {
      await this.tokenExchangePromise
      this.tokenExchangePromise = null
    }
    // Re-exchange if token is near expiry
    if (this.tokenExpiresAt > 0 && this.tokenExpiresAt < Date.now() + this.TOKEN_REFRESH_BUFFER_MS) {
      await this.refreshCopilotToken()
    }
    const model = opts.model || this.models[0]
    if (ANTHROPIC_MODELS.has(model)) {
      yield* this.completeAnthropic(messages, opts, model, attachments, signal)
    } else {
      yield* this.completeOpenAI(messages, opts, model, attachments, signal)
    }
  }

  /** Anthropic Messages API format (for Claude models) */
  private async *completeAnthropic(
    messages: Message[],
    opts: CompletionOpts,
    model: string,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    const system = opts.systemPrompt || (
      typeof messages.find(m => m.role === 'system')?.content === 'string'
        ? messages.find(m => m.role === 'system')?.content as string
        : undefined
    )
    const filtered = messages.filter(m => m.role !== 'system')

    // Attachments belong to the last user message
    const lastUserIdx = filtered.map(m => m.role).lastIndexOf('user')

    const body: Record<string, unknown> = {
      model,
      max_tokens: opts.maxTokens ?? 8192,
      stream: true,
      messages: filtered.map((m, i) => ({
        role: m.role,
        content: toAnthropicContent(
          m,
          i === lastUserIdx ? attachments : undefined,
        ),
      })),
    }
    if (system) body['system'] = system
    if (opts.thinking === 'high') {
      body['thinking'] = { type: 'enabled', budget_tokens: 8000 }
      body['max_tokens'] = Math.max((opts.maxTokens ?? 16000), 16000)
    } else if (opts.thinking === 'medium') {
      body['thinking'] = { type: 'enabled', budget_tokens: 4000 }
      body['max_tokens'] = Math.max((opts.maxTokens ?? 8192), 8192)
    }
    if (opts.tools?.length) {
      body['tools'] = opts.tools
    }

    let res: Response
    try {
      res = await this.fetchWithTimeout(
        `${BASE_URL}/v1/messages`,
        {
          method: 'POST',
          headers: { ...COPILOT_HEADERS, Authorization: `Bearer ${this.token}` },
          body: JSON.stringify(body),
        },
        60000, // 60s timeout for completions
        signal,
      )
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        yield { type: 'error', error: signal?.aborted ? 'cancelled' : 'request timeout after 60s' }
      } else {
        yield { type: 'error', error: `network error: ${String(err)}` }
      }
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
    let inputTokens = 0
    let outputTokens = 0
    let currentTool: { id: string; name: string; inputJson: string } | null = null

    // STREAM STALL DETECTION: Track last chunk received time
    const CHUNK_TIMEOUT_MS = 30000  // 30s without data = stall
    let lastChunkTime = Date.now()

    try {
      while (true) {
        // Check for external cancellation
        if (signal?.aborted) {
          try { await reader.cancel() } catch {}
          yield { type: 'error', error: 'cancelled' }
          return
        }

        // Race the read against a timeout — reader.read() can hang forever
        const timeoutPromise = new Promise<{ done: true; value: undefined }>((resolve) => {
          setTimeout(() => resolve({ done: true, value: undefined }), CHUNK_TIMEOUT_MS)
        })
        const readResult = await Promise.race([reader.read(), timeoutPromise])

        if (readResult.done && !readResult.value && Date.now() - lastChunkTime > CHUNK_TIMEOUT_MS - 1000) {
          reader.releaseLock()
          yield { type: 'error', error: `stream stalled - no data received for ${CHUNK_TIMEOUT_MS / 1000}s` }
          return
        }

        const { done, value } = readResult
        if (done) break
        lastChunkTime = Date.now()  // Reset stall timer on data
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
            } else if (evtType === 'message_start') {
              // Anthropic format: message_start contains input token count
              const message = evt['message'] as Record<string, unknown>
              const usage = message?.['usage'] as Record<string, unknown>
              if (usage?.['input_tokens']) inputTokens = usage['input_tokens'] as number
            } else if (evtType === 'message_delta') {
              const usage = evt['usage'] as Record<string, unknown>
              if (usage?.['output_tokens']) outputTokens = usage['output_tokens'] as number
            } else if (evtType === 'message_stop') {
              yield { type: 'done', tokensUsed: inputTokens + outputTokens, model }
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
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    // Build attachment map: last user message index → attachments
    const attachmentMap = new Map<number, ImageAttachment[]>()
    if (attachments?.length) {
      const lastUserIdx = messages.map(m => m.role).lastIndexOf('user')
      if (lastUserIdx >= 0) attachmentMap.set(lastUserIdx, attachments)
    }

    const body: Record<string, unknown> = {
      model,
      messages: toOpenAIMessages(messages, attachmentMap),
      stream: true,
      stream_options: { include_usage: true },
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
      res = await this.fetchWithTimeout(
        `${BASE_URL}/chat/completions`,
        {
          method: 'POST',
          headers: { ...COPILOT_HEADERS, Authorization: `Bearer ${this.token}` },
          body: JSON.stringify(body),
        },
        60000, // 60s timeout for completions
        signal,
      )
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        yield { type: 'error', error: 'request timeout after 60s' }
      } else {
        yield { type: 'error', error: `network error: ${String(err)}` }
      }
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
    const toolCallAccum: Map<number, { id: string; name: string; argsJson: string }> = new Map()

    // STREAM STALL DETECTION: Track last chunk received time
    const CHUNK_TIMEOUT_MS = 30000  // 30s without data = stall
    let lastChunkTime = Date.now()

    try {
      while (true) {
        // Race the read against a timeout — reader.read() can hang forever
        // if the server stops sending data mid-stream
        const timeoutPromise = new Promise<{ done: true; value: undefined }>((resolve) => {
          setTimeout(() => resolve({ done: true, value: undefined }), CHUNK_TIMEOUT_MS)
        })
        const readResult = await Promise.race([reader.read(), timeoutPromise])

        if (readResult.done && !readResult.value && Date.now() - lastChunkTime > CHUNK_TIMEOUT_MS - 1000) {
          // Timeout won the race — stream stalled
          reader.releaseLock()
          yield { type: 'error', error: `stream stalled - no data received for ${CHUNK_TIMEOUT_MS / 1000}s` }
          return
        }

        const { done, value } = readResult
        if (done) break
        lastChunkTime = Date.now()  // Reset stall timer on data
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') {
            for (const tc of toolCallAccum.values()) {
              let parsed: Record<string, unknown> = {}
              try { parsed = JSON.parse(tc.argsJson) } catch { /* empty */ }
              yield { type: 'tool_use', toolCall: { id: tc.id, name: tc.name, input: parsed } }
            }
            toolCallAccum.clear()
            yield { type: 'done', tokensUsed: totalTokens, model }
            continue
          }
          try {
            const evt = JSON.parse(data) as Record<string, unknown>

            // OpenAI includes usage on the final chunk when stream_options.include_usage is true
            const usage = evt['usage'] as Record<string, unknown> | undefined
            if (usage) {
              totalTokens = (usage['total_tokens'] as number) || 0
            }

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

  async ping(signal?: AbortSignal): Promise<boolean> {
    // CACHE: Return cached result if within TTL
    const now = Date.now()
    if (now - this.lastPingTime < this.PING_CACHE_MS) {
      return this.lastPingResult
    }

    try {
      const res = await this.fetchWithTimeout(
        `${BASE_URL}/v1/models`,
        { headers: { ...COPILOT_HEADERS, Authorization: `Bearer ${this.token}` } },
        10000, // 10s timeout for health check
        signal,
      )
      this.lastPingResult = res.ok
      this.lastPingTime = now
      return res.ok
    } catch {
      this.lastPingResult = false
      this.lastPingTime = now
      return false
    }
  }
}
