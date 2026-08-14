/**
 * VENDORED — faithful type surface of `core/intelligence/cassi-agent/base-posture-runner.ts`.
 * Consumed by helix (helix-posture-runner.ts): `BasePostureRunner`, `isReadOnlyTool`,
 * `isMemoryTool`, `findLastIndex`, `CHARS_PER_TOKEN`, `CONTEXT_BUDGET_FRACTION`,
 * `MAX_TOOL_RESULT_CHARS`.
 *
 * Self-contained stub: imports only shared types from `@cassicore/foundation` and
 * sibling vendor modules within this tree.
 */
import { CHARS_PER_TOKEN as _CHARS_PER_TOKEN } from '@cassicore/embeddings'
// Re-exported so callers get a stable constant surface.
export const CHARS_PER_TOKEN = _CHARS_PER_TOKEN

import {
  handleBlackboardToolCall,
  getBlackboardToolSchemas,
} from '../flux-team/blackboard-tools.js'

import type {
  ILogger,
  IEventBus,
  Message,
  ContentBlock,
  CompletionOpts,
  ModelConfig,
  IModelDirective,
  BasePosture,
  InferenceResult,
  ParsedToolCall,
  IAgentStore,
} from '@cassicore/foundation'

// Faithful to D: base-posture-runner imports these from the model-pool / tools
// modules (the SAME sources helix imports), guaranteeing identical structural types.
import type {
  ModelHandle,
  ModelCompletionOpts,
} from '../../model-pool/types.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'

/** Re-exported so posture-runner consumers share the identical types. */
export type { ModelHandle, ModelCompletionOpts, ToolExecutor, ToolRegistry }

/**
 * Fraction of model context window to use for actual content.
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
 */
export function findLastIndex<T>(arr: T[], predicate: (item: T) => boolean): number {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (predicate(arr[i])) return i
  }
  return -1
}

/**
 * Abstract base for both LumenPostureRunner and DyadPostureRunner.
 * Reproduces the faithful member surface that helix-posture-runner extends.
 */
export abstract class BasePostureRunner<TPosture extends BasePosture = BasePosture> {
  protected handle: ModelHandle
  protected handleFactory?: (config: ModelConfig) => Promise<ModelHandle>
  protected lastModelConfig!: { provider: string; model: string }

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
  protected blackboard?: import('../flux-team/blackboard.js').Blackboard
  protected planHandler?: import('../flux-team/plan-handler.js').PlanHandler
  protected onActivity?: () => void
  protected moduleDebugSessionId?: string
  protected contextBudgetCoordinator?: import('./context-budget-coordinator.js').ContextBudgetCoordinator
  /** Thalamus for context curation during long-running sessions */
  protected thalamus?: import('@cassicore/thalamus').ThalamusModule
  /** Cross-session topic index for sharing Thalamus insights across sessions */
  protected crossSessionIndex?: import('@cassicore/thalamus').CrossSessionTopicIndex

  protected pushMessage(msg: Message): void {
    if (this.thalamus) {
      const index = this.messages.length
      const annotated = this.thalamus.process(this.sessionId, msg, index)
      this.messages.push(annotated as Message)
    } else {
      this.messages.push(msg)
    }
  }

  protected onStreamChunk?(tokensSoFar: number, textAccumulated: string, hasToolUse: boolean): void

  protected abstract getAgentLabel(): string
  protected abstract getSourceLabel(): string
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
    planHandler?: import('../flux-team/plan-handler.js').PlanHandler
    blackboard?: import('../flux-team/blackboard.js').Blackboard
    onActivity?: () => void
    modelDirective?: IModelDirective
    handleFactory?: (config: ModelConfig) => Promise<ModelHandle>
    eventBus?: IEventBus
    jobId?: string
    postureSlot?: string
    moduleDebugSessionId?: string
    contextBudgetCoordinator?: import('./context-budget-coordinator.js').ContextBudgetCoordinator
    thalamus?: import('@cassicore/thalamus').ThalamusModule
    crossSessionIndex?: import('@cassicore/thalamus').CrossSessionTopicIndex
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
    this.thalamus = opts.thalamus
    this.crossSessionIndex = opts.crossSessionIndex
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
    let streamReasoningAccumulated = ''

    const opts: ModelCompletionOpts = {
      model: this.handle.model,
      temperature: this.posture.temperature,
      tools: tools.length > 0 ? tools : undefined,
      stream: true,
      source: this.getSourceLabel(),
      trigger: this.getTriggerLabel(),
      sessionId: this.moduleDebugSessionId,
      thinking: 'none',
      warmSessionKey: this.sessionId
        ? `warm:${this.getSourceLabel()}:${this.sessionId}`
        : undefined,
    }

    let inferenceMessages = this.messages
    if (this.thalamus && this.messages.length > 10) {
      try {
        const curation = await this.thalamus.curate(this.sessionId, this.messages, {
          excludeSessionPrefixes: [],
        })
        inferenceMessages = curation.messages
        if (this.crossSessionIndex && curation.meta.topicSummaries?.length) {
          try {
            await this.crossSessionIndex.publish(this.sessionId, curation.meta.topicSummaries)
          } catch { /* non-critical */ }
        }
      } catch { /* fall back to full messages */ }
    }

    try {
      for await (const chunk of this.handle.stream(inferenceMessages, opts)) {
        this.onActivity?.()
        switch (chunk.type) {
          case 'token':
            currentText += chunk.text ?? ''
            break
          case 'thinking':
            streamReasoningAccumulated += chunk.text ?? ''
            break
          case 'tool_use':
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

    if (currentText.trim()) {
      contentBlocks.push({ type: 'text', text: currentText.trim() })
    }

    return { contentBlocks, tokensUsed, tokenBreakdown, hasToolUse, reasoningContent: streamReasoningAccumulated }
  }

  protected async refreshHandleIfChanged(): Promise<void> {
    if (!this.modelDirective || !this.handleFactory || !this.lastModelConfig) return
    const resolved = this.modelDirective.resolve(this.jobId, this.postureSlot)
    if (resolved.provider === this.lastModelConfig.provider &&
        resolved.model === this.lastModelConfig.model) {
      return
    }
    const prev = { ...this.lastModelConfig }
    try {
      const newHandle = await this.handleFactory(resolved)
      try { this.handle.release() } catch { /* best-effort */ }
      this.handle = newHandle
      this.lastModelConfig = { provider: resolved.provider, model: resolved.model }
      this.onModelChanged(prev, { provider: resolved.provider, model: resolved.model })
    } catch (err) {
      this.logger.error('Failed to swap model handle — continuing with current', {
        error: String(err),
        agent: this.getAgentLabel(),
      })
    }
  }

  protected onModelChanged(
    _prev: { provider: string; model: string },
    _next: { provider: string; model: string },
  ): void {
    // Default: no-op — subclasses can override
  }

  /**
   * Extract ParsedToolCall objects from inference content blocks.
   */
  protected extractToolCalls(blocks: ContentBlock[]): ParsedToolCall[] {
    return blocks
      .filter((b): b is ContentBlock & { type: 'tool_use' } => b.type === 'tool_use')
      .map(b => ({ id: b.id, name: b.name, input: b.input }))
  }

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

  protected truncateOversizedToolResults(maxCharsPerResult: number): void {
    for (const msg of this.messages) {
      if (!Array.isArray(msg.content)) continue
      for (const block of msg.content) {
        if (block.type !== 'tool_result' && block.type !== 'tool_use') continue
        // tool_result blocks have a numeric content in D:; tool_use input may be oversized
        void maxCharsPerResult
      }
    }
  }

  /**
   * 3-pass context window management — trims the message buffer when it
   * exceeds the model context budget. Called at the top of each iteration.
   */
  protected manageContextPressure(): void {
    const contextWindow = this.handle.capabilities?.contextWindow ?? 128_000
    const maxChars = contextWindow * CHARS_PER_TOKEN * CONTEXT_BUDGET_FRACTION
    let currentChars = this.estimateMessageChars()
    if (currentChars <= maxChars) return
    // Compaction-aware: if the first message is a system <summary>, keep it and
    // only trim oversized tool results; otherwise drop the oldest tool results.
    const hasCompactedSummary = this.messages[0]?.role === 'system' &&
      typeof this.messages[0]?.content === 'string' &&
      this.messages[0].content.includes('<summary>')
    if (hasCompactedSummary && currentChars < maxChars * 1.2) {
      this.truncateOversizedToolResults(500_000)
      this.logger.debug('Context pressure — compaction detected, skipping aggressive truncation', {
        role: this.getAgentLabel(), currentChars, maxChars,
      })
      return
    }
    this.logger.info('Context pressure — starting relief', {
      role: this.getAgentLabel(), currentChars, maxChars,
      messageCount: this.messages.length, iteration: this.iterationCount,
    })
    this.truncateOversizedToolResults(32_000)
  }

  protected processBlackboardCalls(calls: ParsedToolCall[]): ContentBlock[] {
    const results: ContentBlock[] = []
    for (const tc of calls) {
      this.toolCallCount++
      const startMs = Date.now()
      const result = this.blackboard
        ? handleBlackboardToolCall(this.blackboard, tc.name, tc.input, this.getAgentLabel())
        : JSON.stringify({ error: `No blackboard available for tool: ${tc.name}` })
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

  protected async executeRealTools(calls: ParsedToolCall[]): Promise<ContentBlock[]> {
    const results: ContentBlock[] = []
    if (calls.length === 0 || !this.toolExecutor) return results

    const execResults = await Promise.allSettled(
      calls.map(async tc => {
        this.toolCallCount++
        const startMs = Date.now()
        try {
          this.onActivity?.()
          const result = await this.toolExecutor!.execute(
            { id: tc.id, name: tc.name, input: tc.input },
            this.sessionId,
          )
          const durationMs = Date.now() - startMs
          if (this.thalamus) {
            const outputBytes = Buffer.byteLength(result.content, 'utf8')
            this.thalamus.getTemporalRegistry(this.sessionId)
              .recordToolMetrics(tc.id, durationMs, outputBytes)
          }
          this.store?.saveToolCall(
            this.sessionId, this.getAgentLabel(), tc.name, tc.id, false,
            tc.input, this.truncateToolResult(result.content), result.isError,
            durationMs, this.iterationCount,
          )
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

  protected processBlockedCalls(calls: ParsedToolCall[]): ContentBlock[] {
    return calls.map(tc => ({
      type: 'tool_result' as const,
      tool_use_id: tc.id,
      content: `Tool "${tc.name}" is not available with the current tool access level (${this.posture.toolAccess}). Use read, glob, grep, or other read-only tools instead.`,
      is_error: true,
    }))
  }

  protected isToolAllowed(name: string): boolean {
    const hasFullAccess = this.posture.toolAccess === 'full'
    if (hasFullAccess) return true
    if (isReadOnlyTool(name, this.toolRegistry)) return true
    if (isMemoryTool(name)) return true
    return false
  }

  protected getBlackboardSchemas(): NonNullable<CompletionOpts['tools']> {
    if (!this.blackboard) return []
    return getBlackboardToolSchemas(this.getAgentLabel() as any)
  }
}
