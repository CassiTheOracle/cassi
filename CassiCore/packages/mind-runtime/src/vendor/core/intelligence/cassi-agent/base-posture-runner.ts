/**
 * BasePostureRunner — Abstract base class for posture execution threads.
 *
 * A PostureRunner is NOT an agent — it is a behavioral execution thread within
 * a CassiAgent (Helix, Lumen, or Dyad). Postures (Yang, Yin, Unity) are
 * energetic directions that compose the agent, not standalone entities.
 *
 * Extracts the ~95% infrastructure duplication between LumenPostureRunner and
 * DyadPostureRunner into a single shared implementation. All systems extend
 * this base and add their own:
 *   - Channel injection (DialecticChannel for Lumen, WorkStream for Dyad)
 *   - Meta-tool routing (dialectic tools vs dyad pipeline tools)
 *   - Run methods (unified run() vs role-specific runAs*())
 *   - Initial message construction
 *
 * Shared infrastructure extracted here:
 *   - streamInference() — streaming token loop with activity heartbeat
 *   - refreshHandleIfChanged() — hot model swap via ModelDirective
 *   - manageContextPressure() — 3-pass context window management
 *   - extractToolCalls() — content block → ParsedToolCall extraction
 *   - truncateToolResult() — character-limited result truncation
 *   - estimateMessageChars() — context size estimation
 *   - executeRealTools() — parallel tool execution with persistence
 *   - processBlackboardCalls() — blackboard meta-tool handling
 *   - processPlanCalls() — plan meta-tool handling
 *   - processBlockedCalls() — access-denied tool responses
 *   - cancel() — cooperative cancellation
 *   - isReadOnlyTool() — tool access filtering
 *
 * Design: Composition over inheritance where possible. Subclasses override
 * abstract methods for label generation (getAgentLabel, getSourceLabel,
 * getTriggerLabel) and hook into model-change events (onModelChanged).
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { Message, ContentBlock, CompletionOpts } from '@cassicore/foundation'
import type { ModelHandle, ModelCompletionOpts } from '@cassicore/model-pool'
import type { IModelDirective, ModelConfig } from '@cassicore/foundation'
import type { ToolExecutor } from '@cassicore/tools'
import type { ToolRegistry } from '@cassicore/tools'
import type { PlanHandler } from '@cassicore/flux-team'
import type { Blackboard } from '@cassicore/flux-team'
import type {
  BasePosture,
  InferenceResult,
  ParsedToolCall,
  IAgentStore,
} from '@cassicore/foundation'
import {
  handleBlackboardToolCall,
  isBlackboardMetaTool,
  getBlackboardToolSchemas,
} from '@cassicore/flux-team'
import type { ContextBudgetCoordinator } from './context-budget-coordinator.js'
import { CHARS_PER_TOKEN as _CHARS_PER_TOKEN } from '../shared/token-estimation.js'
export const CHARS_PER_TOKEN = _CHARS_PER_TOKEN

/**
 * Fraction of model context window to use for actual content.
 * WHY: Reserve 15% headroom for token estimation variance and system overhead.
 * This prevents hard cutoffs during inference.
 */
export const CONTEXT_BUDGET_FRACTION = 0.85
export const MAX_TOOL_RESULT_CHARS = 256_000



/**
 * Check if a tool is read-only using the tool registry.
 * Falls back to pattern matching for tools not in registry.
 */
export function isReadOnlyTool(name: string, registry?: ToolRegistry): boolean {
  const def = registry?.getDefinition(name)
  if (def?.readOnly !== undefined) return def.readOnly

  const readOnlyPatterns = [
    'read', 'glob', 'grep', 'list', 'search', 'find', 'get', 'show',
    'cat', 'head', 'tail', 'which', 'type', 'file', 'stat',
    'code', 'web',
    'serena_list_dir', 'serena_find_file', 'serena_search_for_pattern',
    'serena_get_symbols_overview', 'serena_find_symbol', 'serena_find_referencing_symbols',
    'serena_check_onboarding_performed', 'serena_onboarding', 'serena_initial_instructions',
    'serena_open_dashboard',
    'serena__list_dir', 'serena__find_file', 'serena__search_for_pattern',
    'serena__get_symbols_overview', 'serena__find_symbol', 'serena__find_referencing_symbols',
    'serena__read_file', 'serena__execute_shell_command',
    'gitnexus_query', 'gitnexus_context', 'gitnexus_impact',
    'gitnexus_cypher', 'gitnexus_detect_changes', 'gitnexus_list_repos',
    'gitnexus__query', 'gitnexus__context', 'gitnexus__impact',
    'gitnexus__cypher', 'gitnexus__detect_changes', 'gitnexus__list_repos',
  ]
  return readOnlyPatterns.some(p => name.startsWith(p) || name === p)
}


/**
 * Check if a tool is a memory tool (allowed for read-only+memory access).
 */
export function isMemoryTool(name: string): boolean {
  return name.startsWith('memory_') || name.startsWith('cassi_memory_')
    || name.startsWith('archive_') || name.startsWith('cassi_archive_')
    || name === 'cassi_enrich' || name === 'cassi_universal_search'
    || name === 'cassi_browse'
}


/**
 * Array.findLastIndex polyfill for older Node.js versions.
 * @dep callers: injectDialecticMessages (core/intelligence/lumen/lumen-posture-runner.ts), injectWorkStreamMessages (core/intelligence/dyad/dyad-posture-runner.ts)
 * @dep module: Lumen
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function findLastIndex<T>(arr: T[], predicate: (item: T) => boolean): number {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (predicate(arr[i])) return i
  }
  return -1
}



/**
 * Abstract base for both LumenPostureRunner and DyadPostureRunner.
 *
 * Subclasses provide:
 *   - getAgentLabel()  → 'yang' | 'yin' | 'executive' | 'apex'
 *   - getSourceLabel() → 'lumen:yang' | 'dyad:yang' etc.
 *   - getTriggerLabel() → 'dialectic' | 'dyad'
 *   - onModelChanged(prev, next) → optional hook for event emission
 */
export abstract class BasePostureRunner<
  TPosture extends BasePosture = BasePosture,
> {

  protected handle: ModelHandle
  protected handleFactory?: (config: ModelConfig) => Promise<ModelHandle>
  protected lastModelConfig: { provider: string; model: string }

  protected messages: Message[] = []
  protected posture: TPosture
  protected maxIterations: number

  protected tokensUsed = 0
  protected toolCallCount = 0
  protected iterationCount = 0
  protected cancelled = false
  protected concluded = false

  protected logger: ILogger
  protected eventBus?: IEventBus
  protected store?: IAgentStore
  protected toolExecutor?: ToolExecutor
  protected toolRegistry?: ToolRegistry
  protected modelDirective?: IModelDirective
  protected sessionId: string
  protected jobId?: string
  protected postureSlot?: string
  protected blackboard?: Blackboard
  protected planHandler?: PlanHandler
  protected onActivity?: () => void
  protected moduleDebugSessionId?: string
  /** Optional intelligent context management coordinator */
  protected contextBudgetCoordinator?: ContextBudgetCoordinator

  /** Append one message to the canonical conversation. */
  protected pushMessage(msg: Message): void {
    this.messages.push(msg)
  }

  /**
   * Hook for subclasses to receive real-time streaming token events.
   * Called every ~50 tokens during inference for Brainstem/Corpus visibility.
   */
  protected onStreamChunk?(tokensSoFar: number, textAccumulated: string, hasToolUse: boolean): void



  /** Return the agent's label for logging and store persistence (e.g., 'yang', 'yin') */
  protected abstract getAgentLabel(): string

  /** Return the source label for inference opts (e.g., 'lumen:yang', 'dyad:yang') */
  protected abstract getSourceLabel(): string

  /** Return the trigger label for inference opts (e.g., 'dialectic', 'dyad') */
  protected abstract getTriggerLabel(): string



  constructor(opts: {
    posture: TPosture
    handle: ModelHandle
    logger: ILogger
    sessionId?: string
    defaultSessionId?: string
    toolExecutor?: ToolExecutor
    toolRegistry?: ToolRegistry
    store?: IAgentStore
    planHandler?: PlanHandler
    blackboard?: Blackboard
    onActivity?: () => void
    modelDirective?: IModelDirective
    handleFactory?: (config: ModelConfig) => Promise<ModelHandle>
    eventBus?: IEventBus
    jobId?: string
    postureSlot?: string
    moduleDebugSessionId?: string
    contextBudgetCoordinator?: ContextBudgetCoordinator
  }) {
    this.posture = opts.posture
    this.handle = opts.handle
    this.maxIterations = opts.posture.maxIterations
    this.logger = opts.logger
    this.sessionId = opts.sessionId ?? opts.defaultSessionId ?? 'agent-session'
    this.toolExecutor = opts.toolExecutor
    this.toolRegistry = opts.toolRegistry
    this.store = opts.store
    this.planHandler = opts.planHandler
    this.blackboard = opts.blackboard
    this.onActivity = opts.onActivity
    this.modelDirective = opts.modelDirective
    this.handleFactory = opts.handleFactory
    this.eventBus = opts.eventBus
    this.jobId = opts.jobId
    this.postureSlot = opts.postureSlot
    this.moduleDebugSessionId = opts.moduleDebugSessionId
    this.contextBudgetCoordinator = opts.contextBudgetCoordinator
    this.lastModelConfig = { provider: opts.handle.provider, model: opts.handle.model }
  }



  getIterationCount(): number { return this.iterationCount }
  getTokensUsed(): number { return this.tokensUsed }
  getToolCallCount(): number { return this.toolCallCount }

  cancel(): void {
    this.cancelled = true
  }



  /**
   * Stream inference from the model, collecting content blocks.
   * Signals activity on every chunk to keep the watchdog happy.
   */
  protected async streamInference(
    tools: NonNullable<CompletionOpts['tools']>,
  ): Promise<InferenceResult> {
    await this.refreshHandleIfChanged()

    const contentBlocks: ContentBlock[] = []
    let currentText = ''
    let tokensUsed = 0
    let hasToolUse = false
    let tokenBreakdown: InferenceResult['tokenBreakdown'] | undefined

    const opts: ModelCompletionOpts = {
      model: this.handle.model,
      temperature: this.posture.temperature,
      tools: tools.length > 0 ? tools : undefined,
      stream: true,
      source: this.getSourceLabel(),
      trigger: this.getTriggerLabel(),
      sessionId: this.moduleDebugSessionId,
      thinking: 'none',  // disable thinking mode — DeepSeek requires reasoning_content 
                         // pass-through which the centralized provider adapter strips
      // Warm session: keep copilot-sdk sessions alive across iterations.
      // Key = source label + session ID (e.g. "lumen:yang:session123").
      warmSessionKey: this.sessionId
        ? `warm:${this.getSourceLabel()}:${this.sessionId}`
        : undefined,
    }

    let streamTokenCount = 0
    let streamTextAccumulated = ''
    let streamReasoningAccumulated = ''

    const inferenceMessages = this.messages

    try {
      for await (const chunk of this.handle.stream(inferenceMessages, opts)) {
        // Heartbeat: signal activity on every streaming chunk so the
        // inactivity watchdog doesn't kill us during long inferences.
        this.onActivity?.()

        switch (chunk.type) {
          case 'token':
            currentText += chunk.text ?? ''
            streamTokenCount++
            streamTextAccumulated += chunk.text ?? ''
            // Emit stream activity every 50 tokens for real-time visibility
            if (streamTokenCount % 50 === 0) {
              this.onStreamChunk?.(streamTokenCount, streamTextAccumulated, hasToolUse)
            }
            break

          case 'thinking':
            // Accumulate reasoning tokens — DeepSeek requires them passed back
            streamReasoningAccumulated += chunk.text ?? ''
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
            if (chunk.tokenBreakdown) tokenBreakdown = chunk.tokenBreakdown
            break

          case 'error':
            throw new Error(`Inference error: ${chunk.error ?? 'unknown'}`)
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      throw new Error(
        `${this.getAgentLabel()} inference failed at iteration ${this.iterationCount}: ${msg}`,
      )
    }

    // Flush any remaining text
    if (currentText.trim()) {
      contentBlocks.push({ type: 'text', text: currentText.trim() })
    }

    return { contentBlocks, tokensUsed, tokenBreakdown, hasToolUse, reasoningContent: streamReasoningAccumulated }
  }


  /**
   * Check for mid-run model directive changes and swap the handle if needed.
   * Subclasses can override onModelChanged() to emit system-specific events.
   */
  protected async refreshHandleIfChanged(): Promise<void> {
    if (!this.modelDirective || !this.handleFactory || !this.lastModelConfig) return

    const resolved = this.modelDirective.resolve(this.jobId, this.postureSlot)

    // Same model — nothing to do
    if (resolved.provider === this.lastModelConfig.provider &&
        resolved.model === this.lastModelConfig.model) {
      return
    }

    const prev = { ...this.lastModelConfig }
    this.logger.info('Model directive changed — swapping handle', {
      agent: this.getAgentLabel(),
      prev: `${prev.provider}/${prev.model}`,
      next: `${resolved.provider}/${resolved.model}`,
      sessionId: this.sessionId,
      iteration: this.iterationCount,
    })

    try {
      const newHandle = await this.handleFactory(resolved)

      // Release old handle
      try { this.handle.release() } catch { /* best-effort */ }

      this.handle = newHandle
      this.lastModelConfig = { provider: resolved.provider, model: resolved.model }

      // Let subclasses emit system-specific events
      this.onModelChanged(prev, { provider: resolved.provider, model: resolved.model })
    } catch (err) {
      this.logger.error('Failed to swap model handle — continuing with current', {
        error: String(err),
        agent: this.getAgentLabel(),
        attempted: `${resolved.provider}/${resolved.model}`,
      })
    }
  }

  /**
   * Hook for subclasses to emit events when the model changes.
   * Default: no-op. Lumen overrides to emit lumen:model:changed events.
   */
  protected onModelChanged(
    _prev: { provider: string; model: string },
    _next: { provider: string; model: string },
  ): void {
    // Default: no-op — subclasses can override
  }


  /**
   * Three-pass context pressure management.
   * Pass 1: Truncate tool results in older messages
   * Pass 2: Drop oldest non-protected messages
   * Pass 3: Aggressive truncation of remaining content
   *
   * When a ContextBudgetCoordinator is available, uses ICW scoring
   * (recency + keyword relevance) to make intelligent retention decisions
   * instead of blind oldest-first dropping.
   *
   * Coordination with layered compaction:
   * - If layered compaction already ran (detected by <summary> in system message),
   *   skip aggressive truncation and only do light tool result truncation.
   * - Compaction preserves the most important content in structured form.
   */
  protected manageContextPressure(): void {
    const contextWindow = this.handle.capabilities?.contextWindow ?? 128_000
    const maxChars = contextWindow * CHARS_PER_TOKEN * CONTEXT_BUDGET_FRACTION

    let currentChars = this.estimateMessageChars()
    if (currentChars <= maxChars) return

    const role = this.getAgentLabel()

    // Coordination: If layered compaction already ran, skip aggressive truncation
    // Compaction produces a structured summary that preserves important context
    const hasCompactedSummary = this.messages[0]?.role === 'system' &&
      typeof this.messages[0]?.content === 'string' &&
      this.messages[0].content.includes('<summary>')

    if (hasCompactedSummary && currentChars < maxChars * 1.2) {
      // Compaction handled it — only do light truncation of tool results
      this.truncateOversizedToolResults(500_000)
      this.logger.debug('Context pressure — compaction detected, skipping aggressive truncation', {
        role,
        currentChars,
        maxChars,
      })
      return
    }

    this.logger.info('Context pressure — starting relief', {
      role,
      currentChars,
      maxChars,
      messageCount: this.messages.length,
      iteration: this.iterationCount,
      hasCoordinator: !!this.contextBudgetCoordinator,
    })

    if (this.contextBudgetCoordinator) {
      const icw = this.contextBudgetCoordinator.getICW()
      const config = this.contextBudgetCoordinator.getPostureConfig(role)

      // Use the initial goal/system message as the relevance query
      const goalMsg = this.messages.find(m => m.role === 'system')
      const query = typeof goalMsg?.content === 'string'
        ? goalMsg.content.slice(0, 500)
        : ''

      // Pass 1: Truncate oversized tool results before scoring
      this.truncateOversizedToolResults(config.maxToolResultChars)

      // Pass 2: Use ICW scoreAndSelect to choose which messages to keep
      const result = icw.scoreAndSelect(
        this.messages,
        query,
        Math.round(maxChars),
        {
          anchorTurns: config.anchorTurns ?? 2,
          tailAnchorTurns: config.tailAnchorTurns ?? 3,
          weights: config.weights,
        },
      )

      const omitted = this.messages.length - result.messages.length
      if (omitted > 0) {
        this.messages = result.messages
        this.logger.info('Context pressure — ICW scored and selected', {
          role,
          omitted,
          kept: result.messages.length,
          stats: result.stats,
        })
      }
      return
    }

    const protectedHead = 2
    const protectedTail = 4

    // Pass 1: Truncate tool results in older messages
    if (this.messages.length > protectedHead + protectedTail) {
      const truncatable = this.messages.slice(protectedHead, -protectedTail)
      for (const msg of truncatable) {
        if (Array.isArray(msg.content)) {
          msg.content = msg.content.map(block => {
            if (block.type === 'tool_result' && block.content.length > 500) {
              return { ...block, content: block.content.slice(0, 500) + '\n[... truncated ...]' }
            }
            return block
          })
        }
      }
    }

    currentChars = this.estimateMessageChars()
    if (currentChars <= maxChars) return

    // Pass 2: Drop oldest non-protected messages
    let droppedCount = 0
    while (currentChars > maxChars && this.messages.length > protectedHead + protectedTail + 1) {
      this.messages.splice(protectedHead, 1)
      currentChars = this.estimateMessageChars()
      droppedCount++
    }

    if (droppedCount > 0) {
      this.logger.info('Context pressure — dropped old messages', {
        droppedCount,
        currentChars,
        maxChars,
        messageCount: this.messages.length,
      })
    }

    if (currentChars <= maxChars) return

    // Pass 3: Aggressive truncation
    for (const msg of this.messages.slice(protectedHead)) {
      if (Array.isArray(msg.content)) {
        msg.content = msg.content.map(block => {
          if (block.type === 'tool_result' && block.content.length > 200) {
            return { ...block, content: block.content.slice(0, 200) + '\n[... aggressively truncated ...]' }
          }
          if (block.type === 'text' && block.text.length > 500) {
            return { ...block, text: block.text.slice(0, 500) + '\n[... truncated ...]' }
          }
          return block
        })
      } else if (typeof msg.content === 'string' && msg.content.length > 1000 && msg.role !== 'system') {
        msg.content = msg.content.slice(0, 1000) + '\n[... truncated for context pressure ...]'
      }
    }

    this.logger.warn('Context pressure — aggressive truncation applied', {
      currentChars: this.estimateMessageChars(),
      maxChars,
      messageCount: this.messages.length,
    })
  }

  /**
   * Truncate all tool result blocks exceeding maxChars in the message history.
   * Used by the ICW path before scoring to ensure individual results are bounded.
   */
  private truncateOversizedToolResults(maxChars: number): void {
    for (const msg of this.messages) {
      if (Array.isArray(msg.content)) {
        msg.content = msg.content.map(block => {
           if (block.type === 'tool_result' && block.content.length > maxChars) {
            const omitted = block.content.length - maxChars
            return {
              ...block,
              content: block.content.slice(0, maxChars) +
                `\n\n[tool result truncated at ${maxChars.toLocaleString()} of ${block.content.length.toLocaleString()} chars — ${omitted.toLocaleString()} chars omitted]`,
            }
           }
          return block
        })
      }
    }
  }


  /**
   * Extract ParsedToolCall objects from inference content blocks.
   */
  protected extractToolCalls(blocks: ContentBlock[]): ParsedToolCall[] {
    return blocks
      .filter((b): b is ContentBlock & { type: 'tool_use' } => b.type === 'tool_use')
      .map(b => ({ id: b.id, name: b.name, input: b.input }))
  }


  /**
   * Truncate tool result content to a budget-aware limit.
   * When a ContextBudgetCoordinator is available, uses its effective max
   * (which shrinks as the posture's total tool output budget fills up).
   */
  protected truncateToolResult(content: string): string {
    const role = this.getAgentLabel()
    let maxChars = MAX_TOOL_RESULT_CHARS

    if (this.contextBudgetCoordinator) {
      maxChars = this.contextBudgetCoordinator.getEffectiveMaxToolResultChars(role)
      this.contextBudgetCoordinator.recordToolOutput(role, Math.min(content.length, maxChars))
    }

    if (content.length <= maxChars) return content
    const omitted = content.length - maxChars
    return content.slice(0, maxChars) +
      `\n\n[tool result truncated at ${maxChars.toLocaleString()} of ${content.length.toLocaleString()} chars — ${omitted.toLocaleString()} chars omitted. ` +
      `If this is a file read, re-call with offset: ${maxChars} to get the next section.]`
  }


  /**
   * Estimate the total character count of all messages in the context window.
   */
  protected estimateMessageChars(): number {
    let total = 0
    for (const msg of this.messages) {
      if (typeof msg.content === 'string') {
        total += msg.content.length
      } else if (Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (block.type === 'text') total += block.text.length
          else if (block.type === 'tool_result') total += block.content.length
          else if (block.type === 'tool_use') total += JSON.stringify(block.input).length + 50
        }
      }
    }
    return total
  }



  /**
   * Process blackboard meta-tool calls.
   * Shared by both Lumen and Dyad — identical implementation.
   */
  protected processBlackboardCalls(calls: ParsedToolCall[]): ContentBlock[] {
    const results: ContentBlock[] = []
    for (const tc of calls) {
      this.toolCallCount++
      const startMs = Date.now()
      const result = handleBlackboardToolCall(this.blackboard!, tc.name, tc.input, this.getAgentLabel())
      this.blackboard?.addToolRecord({
        tool: tc.name,
        nodeId: this.getAgentLabel(),
        params: tc.input,
        result,
        isError: result.includes('"error"'),
        durationMs: Date.now() - startMs,
      })
      results.push({
        type: 'tool_result',
        tool_use_id: tc.id,
        content: result,
      })
      this.store?.saveToolCall(
        this.sessionId, this.getAgentLabel(), tc.name, tc.id, true,
        tc.input, result, false, Date.now() - startMs, this.iterationCount,
      )
    }
    return results
  }


  /**
   * Process plan meta-tool calls via PlanHandler.
   * Shared by both Lumen and Dyad — identical implementation.
   */
  protected processPlanCalls(calls: ParsedToolCall[]): ContentBlock[] {
    const results: ContentBlock[] = []
    for (const tc of calls) {
      this.toolCallCount++
      const startMs = Date.now()
      const planResult = this.planHandler!.handleToolCall(tc.name, tc.input, this.getAgentLabel() as any)
      results.push({
        type: 'tool_result',
        tool_use_id: tc.id,
        content: planResult,
      })
      this.store?.saveToolCall(
        this.sessionId, this.getAgentLabel(), tc.name, tc.id, true,
        tc.input, planResult, false, Date.now() - startMs, this.iterationCount,
      )
    }
    return results
  }


  /**
   * Execute real (non-meta) tools in parallel via ToolExecutor.
   * Shared by both Lumen and Dyad — identical implementation.
   */
  protected async executeRealTools(calls: ParsedToolCall[]): Promise<ContentBlock[]> {
    const results: ContentBlock[] = []
    if (calls.length === 0 || !this.toolExecutor) return results

    const execResults = await Promise.allSettled(
      calls.map(async tc => {
        this.toolCallCount++
        const startMs = Date.now()
        try {
          // Heartbeat during tool execution — long-running tools can take 30s+
          this.onActivity?.()
          const result = await this.toolExecutor!.execute(
            { id: tc.id, name: tc.name, input: tc.input },
            this.sessionId,
          )
          this.logger.debug('Tool executed', {
            tool: tc.name,
            durationMs: Date.now() - startMs,
            isError: result.isError,
            contentLength: result.content.length,
          })
          const durationMs = Date.now() - startMs


          this.store?.saveToolCall(
            this.sessionId, this.getAgentLabel(), tc.name, tc.id, false,
            tc.input, this.truncateToolResult(result.content), result.isError,
            durationMs, this.iterationCount,
          )
          this.blackboard?.addToolRecord({
            tool: tc.name,
            nodeId: this.getAgentLabel(),
            params: tc.input,
            result: this.truncateToolResult(result.content),
            isError: result.isError,
            durationMs,
          })
          return {
            id: tc.id,
            content: this.truncateToolResult(result.content),
            isError: result.isError,
          }
        } catch (err) {
          return {
            id: tc.id,
            content: `Tool execution failed: ${err instanceof Error ? err.message : String(err)}`,
            isError: true,
          }
        }
      }),
    )

    for (const settled of execResults) {
      if (settled.status === 'fulfilled') {
        results.push({
          type: 'tool_result',
          tool_use_id: settled.value.id,
          content: settled.value.content,
          is_error: settled.value.isError,
        })
      } else {
        results.push({
          type: 'tool_result',
          tool_use_id: 'unknown',
          content: `Tool execution rejected: ${settled.reason}`,
          is_error: true,
        })
      }
    }

    return results
  }


  /**
   * Generate error responses for tools blocked by access level.
   * Shared by both Lumen and Dyad — identical implementation.
   */
  protected processBlockedCalls(calls: ParsedToolCall[]): ContentBlock[] {
    return calls.map(tc => ({
      type: 'tool_result' as const,
      tool_use_id: tc.id,
      content: `Tool "${tc.name}" is not available with the current tool access level (${this.posture.toolAccess}). Use read, glob, grep, or other read-only tools instead.`,
      is_error: true,
    }))
  }


  /**
   * Classify a tool call for access filtering.
   * Returns true if the tool should be allowed based on posture access level.
   */
  protected isToolAllowed(name: string): boolean {
    const hasFullAccess = this.posture.toolAccess === 'full'
    if (hasFullAccess) return true
    if (isReadOnlyTool(name, this.toolRegistry)) return true
    if (isMemoryTool(name)) return true
    return false
  }


  /**
   * Build blackboard tool schemas if a blackboard is wired.
   * Shared helper used by both systems' buildToolSchemas() methods.
   */
  protected getBlackboardSchemas(): NonNullable<CompletionOpts['tools']> {
    if (!this.blackboard) return []
    return getBlackboardToolSchemas(this.getAgentLabel() as any)
  }
}
