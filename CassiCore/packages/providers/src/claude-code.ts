import { spawn } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import readline from 'node:readline'

import { BaseProvider } from './base.js'
import { signalPromise } from '../utils/abort.js'

import type { ILogger } from '../../types/interfaces.js'
import type { CompletionChunk, CompletionOpts, IProvider, ImageAttachment, Message } from '../../types/runtime.js'

const DEFAULT_MODELS = [
  'claude-sonnet-4-6',
  'claude-opus-4-6',
  'claude-haiku-4-5',
] as const

const MODEL_INFO: Record<string, {
  name: string
  reasoning: boolean
  contextWindow: number
  maxTokens: number
}> = {
  'claude-sonnet-4-6': {
    name: 'Claude Sonnet 4.6 (Claude Code CLI)',
    reasoning: true,
    contextWindow: 200000,
    maxTokens: 32000,
  },
  'claude-opus-4-6': {
    name: 'Claude Opus 4.6 (Claude Code CLI)',
    reasoning: true,
    contextWindow: 1000000,
    maxTokens: 64000,
  },
  'claude-haiku-4-5': {
    name: 'Claude Haiku 4.5 (Claude Code CLI)',
    reasoning: false,
    contextWindow: 200000,
    maxTokens: 32000,
  },
}

const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000
const CASSICORE_MCP_CONFIG = JSON.stringify({
  mcpServers: {
    cassicore: {
      command: 'npx',
      args: ['tsx', '/home/valerie/workspaces/cassicore/mcp/cassicore-gateway.ts'],
    },
  },
})
const EPHEMERAL_SERVER_NAME = 'cassicore_ephemeral'
const ONE_TOOL_PER_TURN_NOTE = [
  'Tool-calling discipline:',
  '- Call at most one tool per turn.',
  '- Wait for the tool result before making another tool call.',
  '- Do not batch multiple tool calls in a single response.',
].join('\n')
const EPHEMERAL_SERVER_SCRIPT = '/home/valerie/workspaces/cassicore/core/providers/claude-code-bridge/ephemeral-mcp-server.mjs'
const EPHEMERAL_HOOK_SCRIPT = '/home/valerie/workspaces/cassicore/core/providers/claude-code-bridge/defer-tool-hook.mjs'

export interface ClaudeCodeProviderOptions {
  cliPath?: string
  workingDirectory?: string
  defaultModel?: string
  logger: ILogger
}

interface ClaudeResultUsage {
  input_tokens?: number
  output_tokens?: number
  cache_read_input_tokens?: number
  cache_creation_input_tokens?: number
}

interface ClaudeJsonLine {
  type?: string
  subtype?: string
  result?: string
  is_error?: boolean
  error?: unknown
  usage?: ClaudeResultUsage
  message?: {
    content?: Array<{ type?: string; text?: string; thinking?: string }>
  }
  event?: {
    type?: string
    index?: number
    content_block?: {
      type?: string
      id?: string
      name?: string
      input?: Record<string, unknown>
    }
    delta?: {
      type?: string
      text?: string
      thinking?: string
      partial_json?: string
    }
    usage?: ClaudeResultUsage
  }
}

interface PendingToolUse {
  id: string
  name: string
  inputJson: string
  inputFallback: Record<string, unknown>
  sawInputDelta: boolean
}

interface ToolBridgePaths {
  mcpConfigPath: string
  settingsPath: string
  toolsPath: string
  resultsPath: string
}

interface DeferredSessionState {
  key: string
  claudeSessionId: string
  deferredToolUse: {
    id: string
    name: string
    input: Record<string, unknown>
  }
  bridge: ToolBridgePaths
  model: string
}

export class ClaudeCodeProvider extends BaseProvider implements IProvider {
  readonly id = 'claude-code'
  readonly models: string[] = [...DEFAULT_MODELS]

  private readonly cliPath: string
  private readonly workingDirectory: string
  private readonly defaultModel: string
  private readonly logger: ILogger
  private readonly deferredSessions = new Map<string, DeferredSessionState>()

  constructor(options: ClaudeCodeProviderOptions) {
    super()
    this.cliPath = options.cliPath || process.env.CLAUDE_CODE_CLI_PATH || 'claude'
    this.defaultModel = this.normalizeModel(options.defaultModel || DEFAULT_MODELS[0])
    this.workingDirectory = options.workingDirectory || this.ensureSandboxDir()
    this.logger = options.logger.child('claude-code-provider')
  }

  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    const model = this.normalizeModel(opts.model || this.defaultModel)
    const externalToolMode = Array.isArray(opts.tools) && opts.tools.length > 0
    const deferredKey = opts.warmSessionKey || opts.sessionId || undefined
    const deferredState = deferredKey ? this.deferredSessions.get(deferredKey) : undefined
    const resumedToolResult = deferredState ? this.findDeferredToolResult(messages, deferredState.deferredToolUse.id) : null
    const systemPrompt = this.extractSystemPrompt(messages, opts.systemPrompt, externalToolMode)
    const prompt = this.formatMessagesAsPrompt(messages, attachments)
    const effort = this.mapThinkingToEffort(opts.thinking)
    const toolBridge = externalToolMode
      ? (deferredState?.bridge ?? this.prepareEphemeralToolBridge(opts.tools ?? []))
      : null
    const commandArgs = [
      '-p',
      '--output-format',
      'stream-json',
      '--include-partial-messages',
      '--verbose',
      '--tools',
      '',
      '--permission-mode',
      'dontAsk',
      '--model',
      model,
      '--setting-sources',
      'user',
    ]

    if (deferredState && resumedToolResult) {
      this.writeDeferredToolResult(toolBridge, deferredState.deferredToolUse.id, resumedToolResult)
      commandArgs.push('--resume', deferredState.claudeSessionId)
    } else {
      commandArgs.splice(1, 0, prompt)
      if (!externalToolMode) {
        commandArgs.push('--no-session-persistence')
      }
    }

    if (externalToolMode && toolBridge) {
      commandArgs.push(
        '--allowedTools',
        `mcp__${EPHEMERAL_SERVER_NAME}__*`,
        '--disallowedTools',
        'Bash,Read,Edit,Write,Glob,Grep,WebFetch,WebSearch,Task,TodoWrite,ToolSearch,ReadMcpResourceTool,ListMcpResourcesTool,mcp__cassicore__*',
        '--strict-mcp-config',
        '--mcp-config',
        toolBridge.mcpConfigPath,
        '--settings',
        toolBridge.settingsPath,
      )
    } else {
      commandArgs.push(
        '--allowedTools',
        'mcp__cassicore__*',
        '--disallowedTools',
        'Bash,Read,Edit,Write,Glob,Grep,WebFetch,WebSearch,Task,TodoWrite,ToolSearch,ReadMcpResourceTool,ListMcpResourcesTool',
        '--strict-mcp-config',
        '--mcp-config',
        CASSICORE_MCP_CONFIG,
      )
    }

    if (systemPrompt) {
      commandArgs.push('--append-system-prompt', systemPrompt)
    }
    if (effort) {
      commandArgs.push('--effort', effort)
    }

    const env = { ...process.env }
    delete env.ANTHROPIC_BASE_URL

    const child = spawn(this.cliPath, commandArgs, {
      cwd: this.workingDirectory,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    let stderr = ''
    let done = false
    let finalError: string | null = null
    let finalUsage: ClaudeResultUsage | undefined
    let finalResultText = ''
    let streamedAnyText = false
    const chunkQueue: CompletionChunk[] = []
    const pendingToolUses = new Map<number, PendingToolUse>()
    let resolveWait: (() => void) | null = null

    const wake = () => resolveWait?.()

    const stdoutRl = readline.createInterface({ input: child.stdout })
    stdoutRl.on('line', (line) => {
      const trimmed = line.trim()
      if (!trimmed) return

      let parsed: ClaudeJsonLine
      try {
        parsed = JSON.parse(trimmed) as ClaudeJsonLine
      } catch {
        return
      }

      if (parsed.type === 'stream_event') {
        const event = parsed.event
        if (event?.type === 'content_block_start') {
          const block = event.content_block
          if (block?.type === 'tool_use' && typeof event.index === 'number' && block.id && block.name) {
            pendingToolUses.set(event.index, {
              id: block.id,
              name: block.name,
              inputJson: '',
              inputFallback: block.input && typeof block.input === 'object' ? block.input : {},
              sawInputDelta: false,
            })
          }
        } else if (event?.type === 'content_block_delta') {
          const delta = event.delta
          if (delta?.type === 'text_delta' && delta.text) {
            streamedAnyText = true
            chunkQueue.push({ type: 'token', text: delta.text })
            wake()
          } else if (delta?.type === 'thinking_delta') {
            const thinking = delta.thinking || delta.text
            if (thinking) {
              chunkQueue.push({ type: 'thinking', text: thinking })
              wake()
            }
          } else if (delta?.type === 'input_json_delta' && typeof event.index === 'number') {
            const pending = pendingToolUses.get(event.index)
            if (pending && delta.partial_json) {
              pending.sawInputDelta = true
              pending.inputJson += delta.partial_json
            }
          }
        } else if (event?.type === 'content_block_stop' && typeof event.index === 'number') {
          const pending = pendingToolUses.get(event.index)
          if (pending) {
            let input: Record<string, unknown> = pending.inputFallback
            if (pending.sawInputDelta) {
              try {
                input = pending.inputJson ? JSON.parse(pending.inputJson) : {}
              } catch {
                input = pending.inputFallback
              }
            }
            chunkQueue.push({
              type: 'tool_use',
              toolCall: {
                id: pending.id,
                name: this.normalizeToolName(pending.name),
                input,
              },
            })
            pendingToolUses.delete(event.index)
            wake()
          }
        } else if (event?.type === 'message_delta' && event.usage) {
          finalUsage = event.usage
        }
        return
      }

      if (parsed.type === 'assistant' && Array.isArray(parsed.message?.content)) {
        finalResultText = parsed.message.content
          .map((part) => part.text || part.thinking || '')
          .join('')
      }

      if (parsed.type === 'result') {
        finalUsage = parsed.usage || finalUsage
        finalResultText = parsed.result || finalResultText
        const stopReason = typeof (parsed as any).stop_reason === 'string' ? (parsed as any).stop_reason : ''
        const sessionId = typeof (parsed as any).session_id === 'string' ? (parsed as any).session_id : ''
        const deferredToolUse = (parsed as any).deferred_tool_use
        if (stopReason === 'tool_deferred' && deferredKey && sessionId && deferredToolUse?.id && deferredToolUse?.name) {
          this.deferredSessions.set(deferredKey, {
            key: deferredKey,
            claudeSessionId: sessionId,
            deferredToolUse: {
              id: deferredToolUse.id,
              name: this.normalizeToolName(deferredToolUse.name),
              input: deferredToolUse.input && typeof deferredToolUse.input === 'object' ? deferredToolUse.input : {},
            },
            bridge: toolBridge!,
            model,
          })
        } else if (deferredKey && resumedToolResult) {
          this.deferredSessions.delete(deferredKey)
          if (toolBridge) this.clearDeferredToolResults(toolBridge)
        }
        if (parsed.is_error) {
          finalError = typeof parsed.error === 'string'
            ? parsed.error
            : parsed.result || 'Claude Code request failed'
        }
        done = true
        wake()
      }
    })

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8')
    })

    const exitPromise = new Promise<number | null>((resolve) => {
      child.on('close', (code) => {
        done = true
        wake()
        resolve(code)
      })
    })

    const abortHandler = () => {
      try { child.kill('SIGTERM') } catch {}
      setTimeout(() => {
        try { child.kill('SIGKILL') } catch {}
      }, 2000).unref?.()
    }

    if (signal) {
      if (signal.aborted) abortHandler()
      else signal.addEventListener('abort', abortHandler, { once: true })
    }

    const timeoutPromise = new Promise<void>((_, reject) => {
      const timeout = setTimeout(() => reject(new Error(`Claude Code request timed out after ${DEFAULT_TIMEOUT_MS}ms`)), DEFAULT_TIMEOUT_MS)
      timeout.unref?.()
      if (signal) {
        signalPromise(signal).then(() => clearTimeout(timeout)).catch(() => {})
      }
    })

    try {
      while (!done || chunkQueue.length > 0) {
        while (chunkQueue.length > 0) {
          yield chunkQueue.shift()!
        }

        if (done) break

        await Promise.race([
          timeoutPromise,
          exitPromise,
          new Promise<void>((resolve) => {
            resolveWait = resolve
            setTimeout(resolve, 2000).unref?.()
          }),
        ])
      }

      const exitCode = await exitPromise
      if (signal) {
        try { signal.removeEventListener('abort', abortHandler) } catch {}
      }
      try { stdoutRl.close() } catch {}

      if (signal?.aborted) {
        yield { type: 'error', error: 'cancelled' }
        return
      }

      if (!finalError && exitCode !== 0 && exitCode !== null) {
        finalError = stderr.trim() || `Claude Code exited with status ${exitCode}`
      }

      if (finalError) {
        yield { type: 'error', error: finalError }
        return
      }

      if (!streamedAnyText && finalResultText) {
        yield { type: 'token', text: finalResultText }
      }

      const input = finalUsage?.input_tokens ?? 0
      const output = finalUsage?.output_tokens ?? 0
      const cacheRead = finalUsage?.cache_read_input_tokens ?? 0
      const cacheWrite = finalUsage?.cache_creation_input_tokens ?? 0
      const totalTokens = input + output + cacheRead + cacheWrite

      yield {
        type: 'done',
        tokensUsed: totalTokens || undefined,
        tokenBreakdown: totalTokens ? {
          input,
          output,
          cacheRead,
          cacheWrite,
        } : undefined,
        model,
      }
    } catch (err) {
      abortHandler()
      yield { type: 'error', error: String(err) }
    } finally {
      if (toolBridge && (!deferredKey || !this.deferredSessions.has(deferredKey))) {
        this.cleanupToolBridge(toolBridge)
      }
    }
  }

  async countTokens(messages: Message[]): Promise<number> {
    return this.estimateTokens(messages)
  }

  async ping(_signal?: AbortSignal): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      const child = spawn(this.cliPath, ['auth', 'status'], {
        cwd: this.workingDirectory,
        env: process.env,
        stdio: ['ignore', 'pipe', 'pipe'],
      })

      let stdout = ''
      child.stdout.on('data', (chunk) => { stdout += chunk.toString('utf8') })
      child.on('close', (code) => {
        if (code !== 0) {
          resolve(false)
          return
        }
        try {
          const parsed = JSON.parse(stdout)
          resolve(parsed?.loggedIn === true)
        } catch {
          resolve(false)
        }
      })
      child.on('error', () => resolve(false))
    })
  }

  describeModel(model?: string): {
    name: string
    api: string
    reasoning: boolean
    input: string[]
    cost: { input: number; output: number; cacheRead: number; cacheWrite: number }
    contextWindow: number
    maxTokens: number
  } {
    const normalized = this.normalizeModel(model || this.defaultModel)
    const info = MODEL_INFO[normalized] || MODEL_INFO[this.defaultModel]
    return {
      name: info.name,
      api: 'anthropic-messages',
      reasoning: info.reasoning,
      input: ['text'],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: info.contextWindow,
      maxTokens: info.maxTokens,
    }
  }

  private ensureSandboxDir(): string {
    const dir = path.join(os.homedir(), '.cassicore', 'claude-code-provider')
    fs.mkdirSync(dir, { recursive: true })
    return dir
  }

  private normalizeModel(model: string): string {
    const trimmed = model.replace(/^claude-code\//, '')
    if (trimmed === 'sonnet') return 'claude-sonnet-4-6'
    if (trimmed === 'opus') return 'claude-opus-4-6'
    if (trimmed === 'haiku') return 'claude-haiku-4-5'
    return trimmed
  }

  private normalizeToolName(name: string): string {
    const prefix = `mcp__${EPHEMERAL_SERVER_NAME}__`
    return name.startsWith(prefix) ? name.slice(prefix.length) : name
  }

  private mapThinkingToEffort(thinking?: CompletionOpts['thinking']): 'low' | 'medium' | 'high' | 'max' | null {
    switch (thinking) {
      case 'none':
        return 'low'
      case 'low':
        return 'low'
      case 'medium':
        return 'medium'
      case 'high':
        return 'high'
      default:
        return null
    }
  }

  private extractSystemPrompt(messages: Message[], override?: string, externalToolMode = false): string {
    const base = override
      ? override
      : (() => {
          const system = messages.find((message) => message.role === 'system')
          if (!system) return ''
          return typeof system.content === 'string' ? system.content : JSON.stringify(system.content)
        })()

    if (!externalToolMode) return base

    return base
      ? `${base}\n\n${ONE_TOOL_PER_TURN_NOTE}`
      : ONE_TOOL_PER_TURN_NOTE
  }

  private prepareEphemeralToolBridge(tools: NonNullable<CompletionOpts['tools']>): ToolBridgePaths {
    const bridgeDir = path.join(this.workingDirectory, 'tool-bridge')
    fs.mkdirSync(bridgeDir, { recursive: true })
    const bridgeId = `bridge-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const toolsPath = path.join(bridgeDir, `${bridgeId}-tools.json`)
    const mcpConfigPath = path.join(bridgeDir, `${bridgeId}.mcp.json`)
    const settingsPath = path.join(bridgeDir, `${bridgeId}.settings.json`)
    const resultsPath = path.join(bridgeDir, `${bridgeId}-results.json`)

    fs.writeFileSync(toolsPath, JSON.stringify({ tools }, null, 2), 'utf8')
    fs.writeFileSync(resultsPath, '{}', 'utf8')
    fs.writeFileSync(mcpConfigPath, JSON.stringify({
      mcpServers: {
        [EPHEMERAL_SERVER_NAME]: {
          command: 'node',
          args: [EPHEMERAL_SERVER_SCRIPT, toolsPath, resultsPath],
        },
      },
    }, null, 2), 'utf8')
    fs.writeFileSync(settingsPath, JSON.stringify({
      hooks: {
        PreToolUse: [{
          matcher: `mcp__${EPHEMERAL_SERVER_NAME}__.*`,
          hooks: [{
            type: 'command',
            command: `node ${JSON.stringify(EPHEMERAL_HOOK_SCRIPT)} ${JSON.stringify(resultsPath)}`,
            timeout: 10,
          }],
        }],
      },
    }, null, 2), 'utf8')

    return { mcpConfigPath, settingsPath, toolsPath, resultsPath }
  }

  private cleanupToolBridge(paths: ToolBridgePaths): void {
    for (const filePath of [paths.toolsPath, paths.mcpConfigPath, paths.settingsPath, paths.resultsPath]) {
      try {
        fs.unlinkSync(filePath)
      } catch {
        // best effort
      }
    }
  }

  private findDeferredToolResult(messages: Message[], toolUseId: string): { content: string; isError: boolean } | null {
    for (let i = messages.length - 1; i >= 0; i--) {
      const message = messages[i]
      if (!Array.isArray(message.content)) continue
      for (const block of message.content) {
        if (block.type === 'tool_result' && block.tool_use_id === toolUseId) {
          return {
            content: block.content,
            isError: block.is_error === true,
          }
        }
      }
    }
    return null
  }

  private writeDeferredToolResult(
    paths: ToolBridgePaths | null,
    toolUseId: string,
    result: { content: string; isError: boolean },
  ): void {
    if (!paths) return
    const current = this.readDeferredToolResults(paths)
    current[toolUseId] = result
    fs.writeFileSync(paths.resultsPath, JSON.stringify(current, null, 2), 'utf8')
  }

  private readDeferredToolResults(paths: ToolBridgePaths): Record<string, { content: string; isError: boolean }> {
    try {
      return JSON.parse(fs.readFileSync(paths.resultsPath, 'utf8'))
    } catch {
      return {}
    }
  }

  private clearDeferredToolResults(paths: ToolBridgePaths): void {
    try {
      fs.writeFileSync(paths.resultsPath, '{}', 'utf8')
    } catch {
      // best effort
    }
  }

  private formatMessagesAsPrompt(messages: Message[], attachments?: ImageAttachment[]): string {
    const parts: string[] = []

    for (const message of messages) {
      if (message.role === 'system') continue
      const content = typeof message.content === 'string'
        ? message.content
        : JSON.stringify(message.content)
      if (!content.trim()) continue
      parts.push(`[${message.role}]\n${content}`)
    }

    if (attachments?.length) {
      parts.push(`[attachments]\n${attachments.length} image attachment(s) were omitted because the Claude Code runtime provider currently supports text-only input.`)
    }

    return parts.join('\n\n')
  }
}
