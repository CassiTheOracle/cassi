const DEFAULT_BASE_URL = 'http://127.0.0.1:8080'
const DEFAULT_TIMEOUT_MS = 120_000

function normalizeBaseUrl(baseUrl) {
  return baseUrl.replace(/\/+$/, '')
}

function finitePositive(value) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
}

function requestError(label, error) {
  return new Error(`${label}: ${error instanceof Error ? error.message : String(error)}`)
}

/**
 * Bounded loopback client for an already-running llama-server.
 * It supervises request readiness and receipts; it never launches, retries,
 * or exposes the model process, and it never alters field behavior.
 */
export function createCassiQwenClient({
  baseUrl = DEFAULT_BASE_URL,
  expectedModel,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  fetch: fetchImpl = globalThis.fetch,
} = {}) {
  if (typeof expectedModel !== 'string' || expectedModel.length === 0) {
    throw new Error('CassiQwen client requires a non-empty expectedModel')
  }
  if (!finitePositive(timeoutMs)) throw new Error('CassiQwen client timeoutMs must be positive and finite')
  if (typeof fetchImpl !== 'function') throw new Error('CassiQwen client requires fetch')
  const root = normalizeBaseUrl(baseUrl)

  async function requestJson(path, init = undefined, timeout = timeoutMs) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)
    try {
      const response = await fetchImpl(`${root}${path}`, { ...init, signal: controller.signal })
      const raw = await response.text()
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${raw}`)
      try {
        return JSON.parse(raw)
      } catch (error) {
        throw new Error(`malformed JSON: ${error instanceof Error ? error.message : String(error)}`)
      }
    } catch (error) {
      if (controller.signal.aborted) throw new Error(`timed out after ${timeout}ms`)
      throw error
    } finally {
      clearTimeout(timer)
    }
  }

  return {
    async readiness() {
      try {
        const health = await requestJson('/health')
        if (health?.status !== 'ok') return { ready: false, reason: 'health status was not ok' }
        const models = await requestJson('/v1/models')
        const model = models?.data?.[0]?.id
        if (model !== expectedModel) return { ready: false, reason: `expected model ${expectedModel}, received ${String(model)}` }
        return { ready: true, model }
      } catch (error) {
        return { ready: false, reason: requestError('readiness failed', error).message }
      }
    },

    async complete({ prompt, mode = 'fast', maxTokens, timeoutMs: requestTimeoutMs } = {}) {
      if (typeof prompt !== 'string' || prompt.length === 0) throw new Error('completion requires a non-empty prompt')
      if (mode !== 'fast' && mode !== 'deliberate') throw new Error('completion mode must be fast or deliberate')
      if (!Number.isInteger(maxTokens) || maxTokens < 1) throw new Error('completion maxTokens must be a positive integer')
      const effectiveTimeout = requestTimeoutMs ?? timeoutMs
      if (!finitePositive(effectiveTimeout)) throw new Error('completion timeoutMs must be positive and finite')
      const ready = await this.readiness()
      if (!ready.ready) throw new Error(`CassiQwen is not ready: ${ready.reason}`)

      const startedAt = performance.now()
      let payload
      try {
        payload = await requestJson('/v1/chat/completions', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            model: expectedModel,
            messages: [{ role: 'user', content: prompt }],
            temperature: 0,
            max_tokens: maxTokens,
            stream: false,
            chat_template_kwargs: { enable_thinking: mode === 'deliberate' },
          }),
        }, effectiveTimeout)
      } catch (error) {
        throw requestError('completion failed', error)
      }
      const message = payload?.choices?.[0]?.message
      if (typeof message?.content !== 'string') throw new Error('completion failed: response did not include final string content')
      return {
        content: message.content,
        reasoningContent: typeof message.reasoning_content === 'string' ? message.reasoning_content : null,
        receipt: {
          model: expectedModel,
          mode,
          maxTokens,
          wallTimeMs: performance.now() - startedAt,
          usage: payload.usage ?? null,
          timings: payload.timings ?? null,
          finishReason: payload?.choices?.[0]?.finish_reason ?? null,
          fieldMode: 'off',
        },
      }
    },
  }
}
