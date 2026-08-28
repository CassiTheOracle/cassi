/**
 * ReflexModule — Fast-path routing for deterministic/recurring patterns.
 *
 * Intercepts incoming messages and routes matching patterns directly to tool
 * execution, bypassing the LLM for common operations. This reduces latency
 * and token usage for routine tasks.
 *
 * Module characteristics:
 * - Name: 'reflex'
 * - Priority: 95 (runs before almost everything)
 * - Confidence thresholds:
 *   - > 0.9: Signal for direct tool execution (bypass LLM)
 *   - 0.7-0.9: Attach as suggestion (LLM still processes)
 *   - < 0.7: Pass through (no action)
 *
 * The module does NOT execute tools itself. It annotates the turn context
 * so the turn pipeline can decide whether to skip LLM inference.
 *
 * @example
 * ```typescript
 * const reflex = createReflex(logger)
 * reflex.wire({ eventBus, toolExecutor, config })
 * await reflex.init()
 * await reflex.start()
 * ```
 */

import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { PatternRegistry } from './pattern-registry.js'
import { PatternLearner } from './pattern-learner.js'
import type { ILogger } from '@cassicore/foundation'
import type { RuntimeEvent } from '@cassicore/foundation'

export interface ReflexModuleConfig {
  /** Enable pattern learning from successful interactions (default: true) */
  enableLearning?: boolean
  /** Minimum confidence to trigger reflex (default: 0.7) */
  minConfidence?: number
  /** Confidence threshold for direct execution (default: 0.9) */
  directExecutionThreshold?: number
  /** Pattern decay interval in hours (default: 24) */
  decayIntervalHours?: number
}

interface ReflexTurnContext {
  sessionId: string
  message: string
  matchedPattern?: {
    patternId: string
    toolName: string
    toolParams: Record<string, unknown>
    confidence: number
    captures: string[]
  }
}

export class ReflexModule extends BaseCognitiveModule {
  readonly name = 'reflex'
  readonly priority = 95

  private registry: PatternRegistry
  private learner?: PatternLearner
  private reflexConfig: ReflexModuleConfig
  private decayTimer?: NodeJS.Timeout
  private turnContexts: Map<string, ReflexTurnContext> = new Map()

  constructor(
    logger: ILogger,
    config?: ReflexModuleConfig,
  ) {
    super(logger.child('reflex'))
    this.reflexConfig = {
      enableLearning: true,
      minConfidence: 0.7,
      directExecutionThreshold: 0.9,
      decayIntervalHours: 24,
      ...config,
    }
    this.registry = new PatternRegistry(this.logger)
    this.registerBuiltInPatterns()
  }

  /**
   * Initialize the reflex module.
   * Registers built-in patterns and starts background processes.
   */
  async init(): Promise<void> {
    await super.init()

    // Initialize pattern learner if enabled
    if (this.reflexConfig.enableLearning && this.eventBus) {
      this.learner = new PatternLearner(this.logger, this.registry)

      // Listen for tool execution events to learn from successful interactions
      this.subscribe('tool:round-complete' as any, (event: any) => {
        this.handleToolRoundComplete(event)
      })
    }

    // Start pattern decay timer
    this.startDecayTimer()

    this.logger.info('Reflex module initialized', {
      enableLearning: this.reflexConfig.enableLearning,
      minConfidence: this.reflexConfig.minConfidence,
      directExecutionThreshold: this.reflexConfig.directExecutionThreshold,
      patternCount: this.registry.count(),
    })
  }

  /**
   * Start the reflex module.
   */
  async start(): Promise<void> {
    await super.start()
    this.logger.info('Reflex module started')
  }

  /**
   * Stop the reflex module.
   * Cleans up timers and pending patterns.
   */
  async stop(): Promise<void> {
    if (this.decayTimer) {
      clearInterval(this.decayTimer)
      this.decayTimer = undefined
    }

    this.learner?.clear()
    this.turnContexts.clear()

    await super.stop()
    this.logger.info('Reflex module stopped')
  }

  /**
   * Handle incoming turn start events.
   * Checks the message against pattern registry and emits reflex signals.
   */
  protected async onTurnStart(sessionId: string, message: string): Promise<void> {
    const match = this.registry.match(message)

    if (!match) {
      this.logger.debug('No reflex pattern matched', { sessionId, message })
      return
    }

    const { pattern, captures } = match

    // Record the hit for pattern statistics
    this.registry.recordHit(pattern.id)

    // Build tool parameters from template
    // Future enhancement: support capture group substitution ($1, $2, etc.)
    const toolParams = this.buildToolParams(pattern.paramTemplate, captures)

    // Store turn context for later retrieval
    this.turnContexts.set(sessionId, {
      sessionId,
      message,
      matchedPattern: {
        patternId: pattern.id,
        toolName: pattern.toolName,
        toolParams,
        confidence: pattern.confidence,
        captures,
      },
    })

    // Emit reflex match event
    this.eventBus?.emit({
      type: 'reflex:match' as any,
      patternId: pattern.id,
      toolName: pattern.toolName,
      confidence: pattern.confidence,
      sessionId,
      timestamp: new Date(),
    })

    // Determine action based on confidence
    if (pattern.confidence >= this.reflexConfig.directExecutionThreshold!) {
      this.logger.info('High-confidence reflex match - candidate for direct execution', {
        sessionId,
        patternId: pattern.id,
        toolName: pattern.toolName,
        confidence: pattern.confidence,
      })
    } else if (pattern.confidence >= this.reflexConfig.minConfidence!) {
      this.logger.debug('Medium-confidence reflex match - suggestion mode', {
        sessionId,
        patternId: pattern.id,
        toolName: pattern.toolName,
        confidence: pattern.confidence,
      })
    }
  }

  /**
   * Handle turn end events.
   * Cleans up turn context.
   */
  protected async onTurnEnd(sessionId: string): Promise<void> {
    this.turnContexts.delete(sessionId)
  }

  /**
   * Register built-in patterns for common operations.
   */
  private registerBuiltInPatterns(): void {
    const builtInPatterns = [
      {
        pattern: '^/status$',
        toolName: 'bash',
        paramTemplate: { command: 'echo "System operational"' },
        confidence: 0.95,
      },
      {
        pattern: '^run\\s+(?:the\\s+)?tests?$',
        toolName: 'bash',
        paramTemplate: { command: 'npm test' },
        confidence: 0.95,
      },
      {
        pattern: '^build$',
        toolName: 'bash',
        paramTemplate: { command: 'npm run build' },
        confidence: 0.95,
      },
      {
        pattern: '^(?:git\\s+)?status$',
        toolName: 'bash',
        paramTemplate: { command: 'git status' },
        confidence: 0.95,
      },
      {
        pattern: '^(?:git\\s+)?diff$',
        toolName: 'bash',
        paramTemplate: { command: 'git diff' },
        confidence: 0.95,
      },
      {
        pattern: '^(?:git\\s+)?log$',
        toolName: 'bash',
        paramTemplate: { command: 'git log --oneline -20' },
        confidence: 0.95,
      },
    ]

    for (const p of builtInPatterns) {
      this.registry.register({
        ...p,
        source: 'builtin',
      })
    }

    this.logger.info('Registered built-in reflex patterns', {
      count: builtInPatterns.length,
    })
  }

  /**
   * Build tool parameters from a template and capture groups.
   *
   * @param template - Parameter template
   * @param captures - Capture groups from regex match
   * @returns Built parameters
   */
  private buildToolParams(
    template: Record<string, unknown>,
    captures: string[],
  ): Record<string, unknown> {
    // Simple implementation: return template as-is
    // Future enhancement: support $1, $2, etc. substitution in string values

    const result: Record<string, unknown> = {}

    for (const [key, value] of Object.entries(template)) {
      if (typeof value === 'string') {
        // Replace capture group references
        result[key] = value.replace(/\$(\d+)/g, (_, index) => {
          const captureIndex = parseInt(index, 10) - 1
          return captures[captureIndex] ?? ''
        })
      } else {
        result[key] = value
      }
    }

    return result
  }

  /**
   * Start the pattern decay timer.
   * Periodically removes unused learned patterns.
   */
  private startDecayTimer(): void {
    const intervalHours = this.reflexConfig.decayIntervalHours ?? 24
    const intervalMs = intervalHours * 60 * 60 * 1000

    this.decayTimer = setInterval(() => {
      const removed = this.registry.decayUnused(intervalHours)
      if (removed > 0) {
        this.logger.info('Pattern decay cycle complete', { removed })
      }
    }, intervalMs)

    this.logger.debug('Started pattern decay timer', { intervalHours })
  }

  /**
   * Handle tool round complete events for pattern learning.
   * Records successful interactions for potential pattern promotion.
   */
  private handleToolRoundComplete(event: any): void {
    if (!this.learner || !this.reflexConfig.enableLearning) return

    const sessionId = event.sessionId
    const turnContext = this.turnContexts.get(sessionId)

    // Only learn from turns that had a reflex match
    if (!turnContext?.matchedPattern) return

    const toolCalls = event.toolCalls || []
    const results = event.results || []

    for (const toolCall of toolCalls) {
      const result = results.find((r: any) => r.toolCallId === toolCall.id)
      const success = result && !result.isError

      if (success) {
        this.learner.record({
          userMessage: turnContext.message,
          toolName: toolCall.name,
          toolParams: toolCall.input || {},
          success: true,
        })
      }
    }

    // Check for patterns ready to be promoted
    this.learner.checkPromotions()
  }

  /**
   * Get the matched pattern context for a session.
   * Used by the turn pipeline to determine if LLM can be skipped.
   *
   * @param sessionId - Session ID
   * @returns Match context or undefined
   */
  getMatchContext(sessionId: string): ReflexTurnContext | undefined {
    return this.turnContexts.get(sessionId)
  }

  /**
   * Get pattern registry statistics.
   *
   * @returns Registry stats
   */
  getStats(): {
    totalPatterns: number
    builtinPatterns: number
    learnedPatterns: number
    pendingLearnedPatterns: number
  } {
    const patterns = this.registry.list()
    const builtin = patterns.filter((p) => p.source === 'builtin').length
    const learned = patterns.filter((p) => p.source === 'learned').length

    return {
      totalPatterns: patterns.length,
      builtinPatterns: builtin,
      learnedPatterns: learned,
      pendingLearnedPatterns: this.learner?.getPendingCount() ?? 0,
    }
  }
}

/**
 * Factory function to create a ReflexModule instance.
 *
 * @param logger - Logger instance
 * @param config - Optional configuration
 * @returns Configured ReflexModule instance
 */
export function createReflex(
  logger: ILogger,
  config?: ReflexModuleConfig,
): ReflexModule {
  return new ReflexModule(logger, config)
}
