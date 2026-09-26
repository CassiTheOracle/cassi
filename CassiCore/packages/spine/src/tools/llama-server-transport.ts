import type { MindCompleteTransport } from './mind-complete.js'

const DEFAULT_BASE_URL = 'http://127.0.0.1:8080'
const DEFAULT_WORLD_MODE_URL = 'http://127.0.0.1:8082'
const DEFAULT_TIMEOUT_MS = 120_000
const MAX_ERROR_BODY_LENGTH = 512

export interface LlamaServerTransportConfig {
  baseUrl?: string
  worldModeUrl?: string
  apiToken?: string
  timeoutMs?: number
  fetch?: typeof globalThis.fetch
}

interface ChatCompletionResponse {
  choices?: Array<{
    message?: {
      content?: unknown
    }
  }>
  usage?: unknown
}

function endpoint(baseUrl: string): string {
  return `${baseUrl.replace(/\/+$/, '')}/v1/chat/completions`
}

function errorBodyExcerpt(body: string): string {
  return body.length <= MAX_ERROR_BODY_LENGTH
    ? body
    : `${body.slice(0, MAX_ERROR_BODY_LENGTH)}…`
}

/**
 * Build the raw-completion transport for an already-running OpenAI-compatible
 * llama-server. The retained spine uses this adapter by default for `mind_complete`;
 * an embedding host can still inject another `MindCompleteTransport` explicitly.
 * Ordinary agent sessions continue to use ohmypi's built-in provider path.
 */
export function createLlamaServerTransport(
  config: LlamaServerTransportConfig = {},
): MindCompleteTransport {
  const baseUrl = config.baseUrl ?? DEFAULT_BASE_URL
  const worldModeUrl = config.worldModeUrl ?? DEFAULT_WORLD_MODE_URL
  const timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const fetchImpl = config.fetch ?? globalThis.fetch

  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error('llama-server timeoutMs must be a positive finite number')
  }
  if (typeof fetchImpl !== 'function') {
    throw new Error('llama-server transport requires a fetch implementation')
  }

  return async (resolved, messages, opts) => {
    if (opts.cassi_world_mode !== undefined && opts.cassi_world_mode !== 'closed_loop') {
      throw new Error(`unsupported cassi_world_mode: ${String(opts.cassi_world_mode)}`)
    }

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    const headers: Record<string, string> = {
      'content-type': 'application/json',
    }
    if (config.apiToken) {
      headers.authorization = `Bearer ${config.apiToken}`
    }

    const body: Record<string, unknown> = {
      model: resolved.id,
      messages,
      stream: false,
    }
    if (opts.cassi_world_mode === 'closed_loop') {
      body.cassi_world_mode = 'closed_loop'
    }
    if (typeof opts.temperature === 'number' && Number.isFinite(opts.temperature)) {
      body.temperature = opts.temperature
    }

    try {
      const response = await fetchImpl(
        endpoint(opts.cassi_world_mode === 'closed_loop' ? worldModeUrl : baseUrl),
        {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
          signal: controller.signal,
        },
      )

      const responseText = await response.text()
      if (!response.ok) {
        throw new Error(
          `llama-server returned HTTP ${response.status}: ${errorBodyExcerpt(responseText)}`,
        )
      }

      let payload: ChatCompletionResponse
      try {
        payload = JSON.parse(responseText) as ChatCompletionResponse
      } catch (error) {
        throw new Error(
          `llama-server returned malformed JSON: ${error instanceof Error ? error.message : String(error)}`,
        )
      }

      const content = payload.choices?.[0]?.message?.content
      if (typeof content !== 'string') {
        throw new Error('llama-server response is missing string completion content')
      }

      return {
        content,
        usage: payload.usage,
      }
    } catch (error) {
      if (controller.signal.aborted) {
        throw new Error(`llama-server request timed out after ${timeoutMs}ms`)
      }
      if (error instanceof Error && error.message.startsWith('llama-server ')) {
        throw error
      }
      throw new Error(
        `llama-server request failed: ${error instanceof Error ? error.message : String(error)}`,
      )
    } finally {
      clearTimeout(timer)
    }
  }
}
