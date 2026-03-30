/**
 * Mini-Helix Runner — Lightweight tool-calling loop for infrastructure agents
 *
 * A stripped-down agent loop optimized for Corpus and Brainstem:
 *   - Single LLM with purpose-built tools (no posture multiplexing)
 *   - No Phase Zero distillation, no dialectic, no work stream
 *   - Supports LLM-driven pause (pause_until_trigger) and external pause
 *   - Shares parent's ModelPool via handleFactory
 *   - Conversation history maintained across cycles for Corpus continuity
 *
 * Uses handle.stream() for native tool-call support (ContentBlock-based),
 * matching the same streaming pattern as BasePostureRunner.streamInference().
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { ModelHandle, ModelCompletionOpts } from '../../model-pool/types.js'
import type { Message, ContentBlock, CompletionChunk, CompletionOpts } from '../../../types/runtime.js'
import type {
  MiniHelixConfig,
  MiniHelixDeps,
  MiniHelixTool,
  MiniHelixToolResult,
  MiniHelixSession,
  MiniHelixStatus,
  MiniHelixProgress,
  MiniHelixResult,
} from './mini-helix-types.js'
import { MINI_HELIX_DEFAULTS } from './mini-helix-types.js'


// ═══════════════════════════════════════════════════════════════════
// Factory
// ═══════════════════════════════════════════════════════════════════

/**
 * Create a mini-Helix session with the given tools and configuration.
 *
 * @param tools - Purpose-built tool set (Corpus: ~18 tools, Brainstem: 8 tools)
 * @param config - Session configuration (merged with consumer defaults)
 * @param deps - Dependencies (logger, eventBus, handleFactory)
 */
export function createMiniHelixSession(
  tools: MiniHelixTool[],
  config: MiniHelixConfig,
  deps: MiniHelixDeps,
): MiniHelixSession {
  return new MiniHelixRunner(tools, config, deps)
}


// ═══════════════════════════════════════════════════════════════════
// Implementation
// ═══════════════════════════════════════════════════════════════════

class MiniHelixRunner implements MiniHelixSession {
  private tools: Map<string, MiniHelixTool>
  private config: Required<MiniHelixConfig>
  private deps: MiniHelixDeps
  private logger: ILogger

  // State
  private status: MiniHelixStatus = 'idle'
  private messages: Message[] = []
  private handle: ModelHandle | null = null

  // Counters
  private totalToolCalls = 0
  private totalLLMCalls = 0
  private totalInputTokens = 0
  private totalOutputTokens = 0
  private completedCycles = 0
  private startTime = 0
  private cycleStartTime = 0
  private currentIteration = 0

  // Cancellation / pause
  private cancelled = false
  private pauseRequested = false

  constructor(tools: MiniHelixTool[], config: MiniHelixConfig, deps: MiniHelixDeps) {
    // Merge consumer defaults UNDER explicit config (config wins)
    const defaults = MINI_HELIX_DEFAULTS[config.consumer]
    this.config = {
      maxIterationsPerCycle: config.maxIterationsPerCycle ?? defaults.maxIterationsPerCycle ?? 50,
      maxTokens: config.maxTokens ?? defaults.maxTokens ?? 2048,
      cycleTimeoutMs: config.cycleTimeoutMs ?? defaults.cycleTimeoutMs ?? 120_000,
      modelTier: config.modelTier ?? defaults.modelTier ?? 'balanced',
      consumer: config.consumer,
      systemPrompt: config.systemPrompt,
      sessionId: config.sessionId,
      constellationId: config.constellationId,
      modelName: config.modelName,
    } as Required<MiniHelixConfig>

    this.deps = deps
    this.logger = deps.logger.child(`mini-helix:${config.consumer}`)

    // Register tools
    this.tools = new Map()
    for (const tool of tools) {
      this.tools.set(tool.def.name, tool)
    }

    this.logger.info('Mini-Helix session created', {
      sessionId: config.sessionId,
      consumer: config.consumer,
      toolCount: tools.length,
      tools: tools.map((t) => t.def.name),
    })
  }


  // ─── Public Interface ──────────────────────────────────────────────

  async run(userMessage?: string): Promise<MiniHelixResult> {
    if (this.cancelled) {
      return this.buildResult('cancelled')
    }

    if (this.status === 'running') {
      throw new Error('Mini-Helix session already running')
    }

    this.status = 'running'
    this.cycleStartTime = Date.now()
    this.currentIteration = 0

    if (this.startTime === 0) {
      this.startTime = Date.now()
    }

    this.logger.info('Mini-Helix cycle starting', {
      sessionId: this.config.sessionId,
      cycle: this.completedCycles + 1,
      userMessage: userMessage?.slice(0, 100),
    })

    this.deps.eventBus?.emit({
      type: 'mini-helix:cycle:started' as any,
      sessionId: this.config.sessionId,
      consumer: this.config.consumer,
      cycle: this.completedCycles + 1,
    } as any)

    // Inject user message if provided
    if (userMessage) {
      this.messages.push({ role: 'user', content: userMessage })
    } else if (this.messages.length === 0) {
      // First cycle — seed with initial prompt
      this.messages.push({ role: 'user', content: 'Begin your analysis.' })
    }

    try {
      // Acquire model handle if we don't have one
      if (!this.handle) {
        this.handle = await this.deps.handleFactory({
          tier: this.config.modelTier,
          purpose: `mini-helix:${this.config.consumer}`,
          sessionId: this.config.sessionId,
        })
        this.logger.info('Model handle acquired', {
          provider: this.handle.provider,
          model: this.handle.model,
        })
      }

      // Run the tool-calling loop
      return await this.runLoop()
    } catch (err) {
      this.status = 'error'
      this.logger.error('Mini-Helix cycle failed', {
        sessionId: this.config.sessionId,
        error: String(err),
        iteration: this.currentIteration,
      })
      return this.buildResult('error')
    }
  }

  cancel(): void {
    this.cancelled = true
    this.status = 'cancelled'
    this.logger.info('Mini-Helix cancelled', {
      sessionId: this.config.sessionId,
    })
  }

  pause(): void {
    if (this.status === 'running') {
      this.pauseRequested = true
      this.logger.info('Mini-Helix pause requested', {
        sessionId: this.config.sessionId,
      })
    } else {
      this.status = 'paused'
    }
  }

  resume(): void {
    if (this.status === 'paused') {
      this.status = 'idle' // Will transition to 'running' on next run()
      this.logger.info('Mini-Helix resumed', {
        sessionId: this.config.sessionId,
      })
    }
  }

  async shutdown(): Promise<void> {
    this.cancelled = true
    this.status = 'completed'

    if (this.handle) {
      try {
        this.handle.release()
      } catch (err) {
        this.logger.warn('Error releasing model handle during shutdown', {
          error: String(err),
        })
      }
      this.handle = null
    }

    this.logger.info('Mini-Helix shutdown complete', {
      sessionId: this.config.sessionId,
      totalToolCalls: this.totalToolCalls,
      totalLLMCalls: this.totalLLMCalls,
      cycles: this.completedCycles,
    })
  }

  getProgress(): MiniHelixProgress {
    return {
      status: this.status,
      consumer: this.config.consumer,
      sessionId: this.config.sessionId,
      iteration: this.currentIteration,
      totalToolCalls: this.totalToolCalls,
      totalLLMCalls: this.totalLLMCalls,
      totalTokens: this.totalInputTokens + this.totalOutputTokens,
      completedCycles: this.completedCycles,
      currentCycleDurationMs: this.cycleStartTime > 0 ? Date.now() - this.cycleStartTime : 0,
      totalDurationMs: this.startTime > 0 ? Date.now() - this.startTime : 0,
    }
  }

  getStatus(): MiniHelixStatus {
    return this.status
  }

  updateSystemPrompt(prompt: string): void {
    this.config.systemPrompt = prompt
  }

  injectMessage(message: Message): void {
    this.messages.push(message)
  }


  // ─── Streaming Inference ───────────────────────────────────────────

  /**
   * Stream inference from the model, collecting ContentBlocks.
   * Matches BasePostureRunner.streamInference() pattern.
   */
  private async streamInference(): Promise<{
    contentBlocks: ContentBlock[]
    tokensUsed: number
    hasToolUse: boolean
  }> {
    if (!this.handle) throw new Error('No model handle')

    this.totalLLMCalls++
    const contentBlocks: ContentBlock[] = []
    let currentText = ''
    let tokensUsed = 0
    let hasToolUse = false

    const toolDefs = Array.from(this.tools.values()).map((t) => t.def)

    const opts: ModelCompletionOpts = {
      model: this.config.modelName || this.handle.model,
      maxTokens: this.config.maxTokens,
      tools: toolDefs.length > 0 ? toolDefs : undefined,
      stream: true,
      source: `mini-helix:${this.config.consumer}`,
      sessionId: this.config.sessionId,
      systemPrompt: this.config.systemPrompt,
      warmSessionKey: `warm:mini-helix:${this.config.consumer}:${this.config.sessionId}`,
    }

    for await (const chunk of this.handle.stream(this.messages, opts)) {
      switch (chunk.type) {
        case 'token':
          currentText += chunk.text ?? ''
          break

        case 'thinking':
          // Discard thinking tokens
          break

        case 'tool_use':
          // Flush accumulated text as a text block
          if (currentText.trim()) {
            contentBlocks.push({ type: 'text', text: currentText.trim() })
            currentText = ''
          }
          if (chunk.toolCall) {
            contentBlocks.push({
              type: 'tool_use',
              id: chunk.toolCall.id,
              name: chunk.toolCall.name,
              input: chunk.toolCall.input,
            })
            hasToolUse = true
          }
          break

        case 'done':
          if (chunk.tokensUsed) tokensUsed = chunk.tokensUsed
          if (chunk.tokenBreakdown) {
            this.totalInputTokens += chunk.tokenBreakdown.input
            this.totalOutputTokens += chunk.tokenBreakdown.output
          }
          break

        case 'error':
          throw new Error(`Inference error: ${chunk.error ?? 'unknown'}`)
      }
    }

    // Flush remaining text
    if (currentText.trim()) {
      contentBlocks.push({ type: 'text', text: currentText.trim() })
    }

    return { contentBlocks, tokensUsed, hasToolUse }
  }


  // ─── Tool-Calling Loop ─────────────────────────────────────────────

  private async runLoop(): Promise<MiniHelixResult> {
    const deadline = Date.now() + this.config.cycleTimeoutMs

    while (
      this.currentIteration < this.config.maxIterationsPerCycle &&
      !this.cancelled &&
      !this.pauseRequested &&
      Date.now() < deadline
    ) {
      this.currentIteration++

      // Stream inference
      const { contentBlocks, tokensUsed, hasToolUse } = await this.streamInference()

      if (!hasToolUse) {
        // Pure text response — no tool calls
        this.messages.push({ role: 'assistant', content: contentBlocks })

        this.logger.debug('LLM returned text without tool calls', {
          iteration: this.currentIteration,
        })

        // Nudge to use tools
        this.messages.push({
          role: 'user',
          content: 'Use your tools to take action, or call signal_done if your work is complete.',
        })
        continue
      }

      // Extract tool calls from content blocks
      const toolCalls: Array<{ id: string; name: string; input: Record<string, unknown> }> = []
      for (const block of contentBlocks) {
        if (block.type === 'tool_use') {
          toolCalls.push({ id: block.id, name: block.name, input: block.input })
        }
      }

      // Add assistant message to history
      this.messages.push({ role: 'assistant', content: contentBlocks })

      // Execute tool calls
      const toolResults: ContentBlock[] = []
      let shouldStop = false
      let shouldPause = false

      for (const call of toolCalls) {
        const tool = this.tools.get(call.name)
        if (!tool) {
          toolResults.push({
            type: 'tool_result',
            tool_use_id: call.id,
            content: `Error: Unknown tool "${call.name}". Available tools: ${Array.from(this.tools.keys()).join(', ')}`,
            is_error: true,
          })
          continue
        }

        this.totalToolCalls++

        try {
          const result = await Promise.resolve(tool.handler(call.input))

          toolResults.push({
            type: 'tool_result',
            tool_use_id: call.id,
            content: result.content,
          })

          if (result.done) {
            shouldStop = true
            this.logger.info('Tool signaled done', {
              tool: call.name,
              iteration: this.currentIteration,
            })
          }

          if (result.pause) {
            shouldPause = true
            this.logger.info('Tool requested pause', {
              tool: call.name,
              iteration: this.currentIteration,
            })
          }
        } catch (err) {
          toolResults.push({
            type: 'tool_result',
            tool_use_id: call.id,
            content: `Error executing tool "${call.name}": ${String(err)}`,
            is_error: true,
          })
          this.logger.warn('Tool execution error', {
            tool: call.name,
            error: String(err),
            iteration: this.currentIteration,
          })
        }
      }

      // Add tool results to history
      this.messages.push({ role: 'user', content: toolResults })

      if (shouldStop) {
        this.completedCycles++
        this.status = 'completed'
        this.emitCycleEvent('completed')
        return this.buildResult('completed')
      }

      if (shouldPause) {
        this.completedCycles++
        this.status = 'paused'
        this.emitCycleEvent('paused')
        return this.buildResult('paused')
      }
    }

    // Loop ended — determine why
    if (this.cancelled) {
      this.status = 'cancelled'
      this.emitCycleEvent('cancelled')
      return this.buildResult('cancelled')
    }

    if (this.pauseRequested) {
      this.pauseRequested = false
      this.completedCycles++
      this.status = 'paused'
      this.emitCycleEvent('paused')
      return this.buildResult('paused')
    }

    if (Date.now() >= deadline) {
      this.logger.warn('Mini-Helix cycle timed out', {
        sessionId: this.config.sessionId,
        iteration: this.currentIteration,
        timeoutMs: this.config.cycleTimeoutMs,
      })
    }

    // Max iterations reached — treat as completed
    this.completedCycles++
    this.status = 'completed'
    this.emitCycleEvent('completed')
    return this.buildResult('completed')
  }


  // ─── Helpers ───────────────────────────────────────────────────────

  private buildResult(status: MiniHelixStatus): MiniHelixResult {
    return {
      summary: `Mini-Helix ${this.config.consumer} ${status} after ${this.currentIteration} iterations, ${this.totalToolCalls} tool calls`,
      status,
      toolCalls: this.totalToolCalls,
      llmCalls: this.totalLLMCalls,
      tokenUsage: {
        input: this.totalInputTokens,
        output: this.totalOutputTokens,
        total: this.totalInputTokens + this.totalOutputTokens,
      },
      cycles: this.completedCycles,
      durationMs: this.startTime > 0 ? Date.now() - this.startTime : 0,
    }
  }

  private emitCycleEvent(event: string): void {
    this.deps.eventBus?.emit({
      type: `mini-helix:cycle:${event}` as any,
      sessionId: this.config.sessionId,
      consumer: this.config.consumer,
      cycle: this.completedCycles,
      iteration: this.currentIteration,
      toolCalls: this.totalToolCalls,
    } as any)
  }
}
