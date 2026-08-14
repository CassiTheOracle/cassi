/**
 * CassiCore Bridge - OpenAI-compatible API over Unix socket
 * 
 * Provides a lightweight OpenAI-compatible API endpoint that OpenClaw
 * can use to communicate with CassiCore providers.
 */
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'

import type { ILogger } from '../../types/interfaces.js'
import type { IProvider, Message, CompletionOpts, CompletionChunk } from '../../types/runtime.js'

interface BridgeOptions {
  socketPath?: string
  port?: number
  host?: string
}

export function createBridge(
  providers: Map<string, IProvider>,
  logger: ILogger,
  options: BridgeOptions = {}
) {
  const socketPath = options.socketPath || path.join(os.homedir(), '.cassicore', 'bridge.sock')
  const port = options.port
  const host = options.host || '127.0.0.1'

  let server: http.Server | null = null

  function sendJSON(res: http.ServerResponse, code: number, obj: unknown) {
    const s = JSON.stringify(obj)
    res.writeHead(code, { 'Content-Type': 'application/json' })
    res.end(s)
  }

  function parseBody(req: http.IncomingMessage): Promise<any> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = []
      req.on('data', (c) => chunks.push(Buffer.from(c)))
      req.on('end', () => {
        if (chunks.length === 0) return resolve(undefined)
        try {
          const s = Buffer.concat(chunks).toString('utf8')
          resolve(JSON.parse(s))
        } catch (err) {
          reject(err)
        }
      })
      req.on('error', reject)
    })
  }

  function getProviderForModel(model: string): IProvider | null {
    // Handle provider/model format (e.g., "kimi-coding/k2p5")
    if (model.includes('/')) {
      const [providerId] = model.split('/')
      return providers.get(providerId) || null
    }
    // Fallback to default provider
    return providers.values().next().value || null
  }

  function convertMessages(body: any): Message[] {
    const messages: Message[] = []
    if (body.messages && Array.isArray(body.messages)) {
      for (const m of body.messages) {
        if (m.role && m.content) {
          messages.push({
            role: m.role,
            content: m.content,
          })
        }
      }
    }
    return messages
  }

  async function handleChatCompletions(req: http.IncomingMessage, res: http.ServerResponse) {
    if (req.method !== 'POST') {
      return sendJSON(res, 405, { error: 'method not allowed' })
    }

    try {
      const body = await parseBody(req)
      
      if (!body || !body.model) {
        return sendJSON(res, 400, { error: 'missing model' })
      }

      const provider = getProviderForModel(body.model)
      if (!provider) {
        return sendJSON(res, 404, { error: `provider not found for model: ${body.model}` })
      }

      const modelId = body.model.includes('/') ? body.model.split('/')[1] : body.model
      const messages = convertMessages(body)
      
      const opts: CompletionOpts = {
        model: modelId,
        maxTokens: body.max_tokens,
        temperature: body.temperature,
        thinking: body.thinking || 'high',
        stream: body.stream === true,
      }

      // Handle streaming
      if (body.stream) {
        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        })

        try {
          const stream = provider.complete(messages, opts)
          let id = 0

          for await (const chunk of stream) {
            if (chunk.type === 'token' && chunk.text) {
              const data = JSON.stringify({
                id: `chatcmpl-${id++}`,
                object: 'chat.completion.chunk',
                created: Math.floor(Date.now() / 1000),
                model: body.model,
                choices: [{
                  index: 0,
                  delta: { content: chunk.text },
                  finish_reason: null,
                }],
              })
              res.write(`data: ${data}\n\n`)
            } else if (chunk.type === 'done') {
              const data = JSON.stringify({
                id: `chatcmpl-${id++}`,
                object: 'chat.completion.chunk',
                created: Math.floor(Date.now() / 1000),
                model: body.model,
                choices: [{
                  index: 0,
                  delta: {},
                  finish_reason: 'stop',
                }],
              })
              res.write(`data: ${data}\n\n`)
            }
          }

          res.write('data: [DONE]\n\n')
          res.end()
        } catch (err) {
          logger.warn(`streaming error: ${String(err)}`)
          res.write(`data: ${JSON.stringify({ error: String(err) })}\n\n`)
          res.end()
        }
      } else {
        // Non-streaming
        let fullText = ''
        let tokensUsed = 0
        
        try {
          const stream = provider.complete(messages, opts)
          for await (const chunk of stream) {
            if (chunk.type === 'error' && chunk.error) {
              // Provider returned an error chunk
              throw new Error(chunk.error)
            }
            if (chunk.type === 'token' && chunk.text) {
              fullText += chunk.text
            }
            if (chunk.tokensUsed) {
              tokensUsed = chunk.tokensUsed
            }
          }

          const response = {
            id: `chatcmpl-${Date.now()}`,
            object: 'chat.completion',
            created: Math.floor(Date.now() / 1000),
            model: body.model,
            choices: [{
              index: 0,
              message: {
                role: 'assistant',
                content: fullText,
              },
              finish_reason: 'stop',
            }],
            usage: {
              prompt_tokens: 0,
              completion_tokens: tokensUsed,
              total_tokens: tokensUsed,
            },
          }

          return sendJSON(res, 200, response)
        } catch (err: any) {
          // Check for specific error types
          const errMsg = String(err?.message || err)
          let statusCode = 500
          let errorCode = 'internal_error'
          
          if (errMsg.includes('quota') || errMsg.includes('429')) {
            statusCode = 429
            errorCode = 'insufficient_quota'
          } else if (errMsg.includes('auth') || errMsg.includes('token') || errMsg.includes('401')) {
            statusCode = 401
            errorCode = 'invalid_auth'
          } else if (errMsg.includes('not found') || errMsg.includes('404')) {
            statusCode = 404
            errorCode = 'not_found'
          }
          
          logger.warn(`completion error: ${errMsg}`)
          return sendJSON(res, statusCode, {
            error: {
              message: errMsg,
              type: errorCode,
              code: errorCode,
            }
          })
        }
      }
    } catch (err) {
      logger.warn(`chat completions error: ${String(err)}`)
      return sendJSON(res, 500, { error: String(err) })
    }
  }

  async function handleModels(req: http.IncomingMessage, res: http.ServerResponse) {
    if (req.method !== 'GET') {
      return sendJSON(res, 405, { error: 'method not allowed' })
    }

    const models: Array<{ id: string; object: string; created: number; owned_by: string }> = []
    
    for (const [providerId, provider] of providers) {
      const providerModels = provider.models || []
      for (const modelId of providerModels) {
        models.push({
          id: `${providerId}/${modelId}`,
          object: 'model',
          created: Math.floor(Date.now() / 1000),
          owned_by: providerId,
        })
      }
    }

    return sendJSON(res, 200, {
      object: 'list',
      data: models,
    })
  }

  async function handler(req: http.IncomingMessage, res: http.ServerResponse) {
    const url = new URL(req.url || '/', `http://${host}:${port || 0}`)

    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*')
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    if (req.method === 'OPTIONS') {
      res.writeHead(200)
      res.end()
      return
    }

    try {
      if (url.pathname === '/v1/chat/completions') {
        await handleChatCompletions(req, res)
      } else if (url.pathname === '/v1/models') {
        await handleModels(req, res)
      } else if (url.pathname === '/health') {
        sendJSON(res, 200, { status: 'ok', providers: Array.from(providers.keys()) })
      } else {
        sendJSON(res, 404, { error: 'not_found', path: url.pathname })
      }
    } catch (err) {
      logger.warn(`handler error: ${String(err)}`)
      sendJSON(res, 500, { error: 'internal_error', message: String(err) })
    }
  }

  async function start(): Promise<{ socketPath: string; port?: number }> {
    // Remove old socket if exists
    try {
      if (fs.existsSync(socketPath)) {
        fs.unlinkSync(socketPath)
      }
    } catch (err) {
      logger.warn(`failed to remove old socket: ${String(err)}`)
    }

    server = http.createServer(handler)

    // Listen on Unix socket
    await new Promise<void>((resolve, reject) => {
      server!.listen(socketPath, () => {
        // Set permissions so OpenClaw can connect
        try {
          fs.chmodSync(socketPath, 0o666)
        } catch (err) {
          logger.warn(`failed to set socket permissions: ${String(err)}`)
        }
        resolve()
      })
      server!.on('error', reject)
    })

    logger.info(`listening on unix:${socketPath}`)

    // Also listen on TCP if port specified
    if (port) {
      await new Promise<void>((resolve, reject) => {
        server!.listen(port, host, () => {
          resolve()
        })
        server!.on('error', reject)
      })
      logger.info(`listening on http://${host}:${port}`)
      return { socketPath, port }
    }

    return { socketPath }
  }

  async function stop(): Promise<void> {
    if (server) {
      await new Promise<void>((resolve) => {
        server!.close(() => resolve())
      })
      server = null
    }
    // Clean up socket file
    try {
      if (fs.existsSync(socketPath)) {
        fs.unlinkSync(socketPath)
      }
    } catch (err) {
      // ignore cleanup errors
    }
  }

  return { start, stop }
}
