/**
 * Warm Provider — OpenAI-compatible HTTP endpoint that bridges
 * OpenCode to CassiCore's warm session infrastructure.
 *
 * Implements POST /v1/chat/completions in OpenAI SSE format so
 * OpenCode (or any OpenAI-compatible client) can use CassiCore
 * as a provider. Under the hood, all turns within the same
 * conversation share one Copilot SDK `sendAndWait()` call,
 * collapsing them into a single premium request.
 *
 * Endpoints:
 *   POST /v1/chat/completions   — Stream a completion (OpenAI SSE format)
 *   GET  /v1/models             — List available models
 *   GET  /v1/warm/sessions      — List active warm sessions (management)
 *   DELETE /v1/warm/sessions/:id — Destroy a warm session (management)
 */
import type { ILogger, IEventBus } from '@cassicore/foundation'
import type http from 'node:http'
import type { CopilotSdkProvider } from '@cassicore/providers'
import { WarmProviderManager } from '@cassicore/providers'

export interface WarmProviderRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

/** Lazy singleton — created on first request if the SDK provider is available */
let manager: WarmProviderManager | null = null

async function getOrCreateManager(daemon: any, logger: ILogger): Promise<WarmProviderManager | null> {
  if (manager) return manager

  // Get the copilot-sdk provider from the provider map
  const providers: Map<string, unknown> | undefined =
    (daemon.pipeline as any)?.providers ??
    (daemon as any).providers

  if (!providers) {
    logger.warn('warm-provider: no providers map found on daemon')
    return null
  }

  const sdkProvider = providers.get('copilot-sdk') as CopilotSdkProvider | undefined
  if (!sdkProvider) {
    logger.warn('warm-provider: copilot-sdk provider not available')
    return null
  }

  const bus: IEventBus = daemon.bus
  const idleTimeoutMs = daemon.config?.get?.('warmProvider.idleTimeoutMs', 8 * 60 * 60 * 1000) ?? 8 * 60 * 60 * 1000

  // Build a default system prompt that includes AGENTS.md context
  const systemPrompt = await buildDefaultSystemPrompt(daemon)

  manager = new WarmProviderManager({
    provider: sdkProvider,
    bus,
    logger,
    idleTimeoutMs,
    defaultSystemPrompt: systemPrompt,
  })

  logger.info('warm-provider: manager created', { idleTimeoutMs })
  return manager
}

/**
 * Build a default system prompt from workspace instructions and daemon context.
 * Uses ancestor directory chain discovery to find AGENTS.md and related
 * instruction files from the working directory up to the filesystem root.
 * Applies per-file (4K chars) and total (12K chars) token budgeting.
 */
async function buildDefaultSystemPrompt(daemon: any): Promise<string> {
  const parts: string[] = []

  // Discover instruction files from ancestor directory chain
  try {
    const { discoverAndRenderInstructions } = await import('../vendor/core/workspace/instruction-discovery.js')
    const result = discoverAndRenderInstructions(process.cwd())
    if (result.rendered) {
      parts.push(result.rendered)
    }
  } catch {
    // Fallback: try loading AGENTS.md directly (original behavior)
    try {
      const { readFileSync, existsSync } = await import('node:fs')
      const { join } = await import('node:path')
      const agentsMd = join(process.cwd(), 'AGENTS.md')
      if (existsSync(agentsMd)) {
        parts.push(readFileSync(agentsMd, 'utf-8'))
      }
    } catch { /* ignore */ }
  }

  // Add warm session preamble
  parts.push(`
You are an AI coding assistant running inside CassiCore's warm session infrastructure.
You have access to all CassiCore tools including file operations (read, write, edit, bash),
code intelligence (grep, glob), and intelligent context management (cassi_enrich, cassi_do, cassi_memory).

IMPORTANT: At the start of each user message, call cassi_enrich with the user's message
to surface relevant memories, past decisions, and conversation history.

CRITICAL: You MUST call finished() at the end of EVERY response, without exception.
This applies to every turn — long or short, simple or complex, code or conversation.

finished({ result: "<brief summary of what you did>" })

Why this is mandatory:
- You are running inside a Copilot SDK warm session
- finished() is the mechanism that keeps this session alive between turns
- The handler blocks until the next user message arrives, then returns it as your next task
- Skipping finished() terminates the warm session — the next turn will cold-start a new
  premium request, wasting billing efficiency
- All turns within one warm session collapse into a single premium request

Do NOT end a response without calling finished(). No exceptions.
`.trim())

  return parts.join('\n\n')
}

/**
 * Parse an OpenAI-format request body.
 */
interface OpenAIChatRequest {
  model?: string
  messages?: Array<{ role: string; content: string }>
  stream?: boolean
  /** Custom: conversation ID for warm session keying */
  conversation_id?: string
}

/**
 * Route handler for /v1/* endpoints.
 */
export async function handleWarmProviderRoutes(
  deps: WarmProviderRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody } = deps

  // Only handle /v1/* routes
  if (!pathname.startsWith('/v1/')) return false

  const subpath = pathname.slice(3) // Remove '/v1'

  if (method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Conversation-ID',
      'Access-Control-Max-Age': '86400',
    })
    res.end()
    return true
  }

  if (subpath === '/models' && method === 'GET') {
    const mgr = await getOrCreateManager(daemon, logger)
    if (!mgr) {
      sendJSON(res, 503, { error: { message: 'Warm provider not available (copilot-sdk not initialized)', type: 'server_error' } })
      return true
    }

    // Get models from the SDK provider
    const providers: Map<string, any> | undefined =
      (daemon.pipeline as any)?.providers ?? (daemon as any).providers
    const sdkProvider = providers?.get('copilot-sdk')
    const models = sdkProvider?.models ?? []

    const response = {
      object: 'list',
      data: models.map((id: string) => ({
        id,
        object: 'model',
        created: Math.floor(Date.now() / 1000),
        owned_by: 'cassicore-warm',
      })),
    }
    sendJSON(res, 200, response)
    return true
  }

  if (subpath === '/chat/completions' && method === 'POST') {
    const mgr = await getOrCreateManager(daemon, logger)
    if (!mgr) {
      sendJSON(res, 503, { error: { message: 'Warm provider not available (copilot-sdk not initialized)', type: 'server_error' } })
      return true
    }

    let body: OpenAIChatRequest
    try {
      body = await parseBody(req)
    } catch (err) {
      sendJSON(res, 400, { error: { message: `Invalid request body: ${String(err)}`, type: 'invalid_request_error' } })
      return true
    }

    const messages = body.messages ?? []
    const model = body.model
    const stream = body.stream !== false // Default to streaming

    // Extract the latest user message as the prompt
    const userMessages = messages.filter(m => m.role === 'user')
    const latestUserMessage = userMessages[userMessages.length - 1]?.content
    if (!latestUserMessage) {
      sendJSON(res, 400, { error: { message: 'No user message found in messages array', type: 'invalid_request_error' } })
      return true
    }

    // Extract system prompt if present
    const systemMessage = messages.find(m => m.role === 'system')?.content

    // Determine conversation ID for warm session keying.
    // Priority: explicit conversation_id > X-Conversation-ID header > stable auto-key
    //
    // The auto-key MUST be stable across turns. We use the remote address
    // (+ model for session isolation) because OpenCode dynamically mutates
    // the system prompt between turns (injecting token counts, session info,
    // system reminders, etc.), making any hash of the system prompt unstable.
    // A single OpenCode instance always connects from the same address, so
    // this produces a consistent key across the entire conversation.
    const remoteAddr = req.socket.remoteAddress || 'default'
    const modelKey = model || 'default'
    const conversationId =
      body.conversation_id ??
      req.headers['x-conversation-id'] as string ??
      `auto-${hashString(remoteAddr)}-${hashString(modelKey)}`

    logger.debug('warm-provider: resolved conversation ID', {
      conversationId,
      source: body.conversation_id ? 'explicit' : req.headers['x-conversation-id'] ? 'header' : 'auto',
      remoteAddr: req.socket.remoteAddress,
      model: model || 'default',
    })

    if (!stream) {
      // Non-streaming: collect all chunks and return as a single response
      let fullText = ''
      let error: string | undefined

      for await (const chunk of mgr.processMessage(conversationId, latestUserMessage, { model, systemPrompt: systemMessage })) {
        if (chunk.type === 'token' && chunk.text) {
          fullText += chunk.text
        } else if (chunk.type === 'error') {
          error = chunk.error
        }
      }

      if (error && !fullText) {
        sendJSON(res, 500, { error: { message: error, type: 'server_error' } })
        return true
      }

      const response = buildNonStreamingResponse(fullText, model || 'claude-opus-4.6', conversationId)
      sendJSON(res, 200, response)
      return true
    }

    // Streaming response — OpenAI SSE format
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
      'X-Accel-Buffering': 'no',
    })

    const completionId = `chatcmpl-warm-${Date.now()}`
    const modelId = model || 'claude-opus-4.6'

    try {
      for await (const chunk of mgr.processMessage(conversationId, latestUserMessage, { model, systemPrompt: systemMessage })) {
        if (res.destroyed) break

        if (chunk.type === 'thinking' && chunk.text) {
          // Reasoning/thinking tokens — use OpenAI's reasoning_content delta format
          // This is how @ai-sdk/openai-compatible expects reasoning tokens
          const sseData = {
            id: completionId,
            object: 'chat.completion.chunk',
            created: Math.floor(Date.now() / 1000),
            model: modelId,
            choices: [{
              index: 0,
              delta: { reasoning_content: chunk.text },
              finish_reason: null,
            }],
          }
          res.write(`data: ${JSON.stringify(sseData)}\n\n`)
        } else if (chunk.type === 'token' && chunk.text) {
          const sseData = {
            id: completionId,
            object: 'chat.completion.chunk',
            created: Math.floor(Date.now() / 1000),
            model: modelId,
            choices: [{
              index: 0,
              delta: { content: chunk.text },
              finish_reason: null,
            }],
          }
          res.write(`data: ${JSON.stringify(sseData)}\n\n`)
        } else if (chunk.type === 'done') {
          const finalData = {
            id: completionId,
            object: 'chat.completion.chunk',
            created: Math.floor(Date.now() / 1000),
            model: chunk.model || modelId,
            choices: [{
              index: 0,
              delta: {},
              finish_reason: 'stop',
            }],
            ...(chunk.tokenBreakdown ? {
              usage: {
                prompt_tokens: chunk.tokenBreakdown.input,
                completion_tokens: chunk.tokenBreakdown.output,
                total_tokens: chunk.tokenBreakdown.input + chunk.tokenBreakdown.output,
              },
            } : {}),
          }
          res.write(`data: ${JSON.stringify(finalData)}\n\n`)
        } else if (chunk.type === 'error') {
          const errorData = {
            id: completionId,
            object: 'chat.completion.chunk',
            created: Math.floor(Date.now() / 1000),
            model: modelId,
            choices: [{
              index: 0,
              delta: { content: `\n\n[Error: ${chunk.error}]` },
              finish_reason: 'stop',
            }],
          }
          res.write(`data: ${JSON.stringify(errorData)}\n\n`)
        }
      }
    } catch (err) {
      logger.error('warm-provider: streaming error', { error: String(err), conversationId })
      if (!res.destroyed) {
        const errorData = {
          id: completionId,
          object: 'chat.completion.chunk',
          created: Math.floor(Date.now() / 1000),
          model: modelId,
          choices: [{
            index: 0,
            delta: { content: `\n\n[Stream error: ${String(err)}]` },
            finish_reason: 'stop',
          }],
        }
        res.write(`data: ${JSON.stringify(errorData)}\n\n`)
      }
    }

    // Send the terminal [DONE] marker
    if (!res.destroyed) {
      res.write('data: [DONE]\n\n')
      res.end()
    }
    return true
  }

  if (subpath === '/warm/sessions' && method === 'GET') {
    const mgr = await getOrCreateManager(daemon, logger)
    if (!mgr) {
      sendJSON(res, 503, { error: { message: 'Warm provider not available', type: 'server_error' } })
      return true
    }
    sendJSON(res, 200, { sessions: mgr.listSessions() })
    return true
  }

  if (subpath.startsWith('/warm/sessions/') && method === 'DELETE') {
    const mgr = await getOrCreateManager(daemon, logger)
    if (!mgr) {
      sendJSON(res, 503, { error: { message: 'Warm provider not available', type: 'server_error' } })
      return true
    }
    const id = subpath.slice('/warm/sessions/'.length)
    const destroyed = await mgr.destroySession(id, 'admin API request')
    sendJSON(res, 200, { destroyed, conversationId: id })
    return true
  }

  return false
}

/**
 * Build a non-streaming OpenAI chat completion response.
 */
function buildNonStreamingResponse(content: string, model: string, conversationId: string) {
  return {
    id: `chatcmpl-warm-${Date.now()}`,
    object: 'chat.completion',
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [{
      index: 0,
      message: { role: 'assistant', content },
      finish_reason: 'stop',
    }],
    usage: {
      prompt_tokens: 0, // Not easily available from SDK
      completion_tokens: 0,
      total_tokens: 0,
    },
    system_fingerprint: `warm:${conversationId}`,
  }
}

/**
 * Simple string hash for generating deterministic conversation IDs.
 */
function hashString(str: string): string {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash |= 0
  }
  return Math.abs(hash).toString(36)
}

/**
 * Shut down the warm provider manager (called during daemon shutdown).
 */
export async function shutdownWarmProvider(): Promise<void> {
  if (manager) {
    await manager.shutdown()
    manager = null
  }
}
