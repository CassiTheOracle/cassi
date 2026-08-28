/**
 * Smart Rules Recovery Module
 *
 * Detects dead-end turns (empty responses, deflections, tool failure loops)
 * and triggers recovery strategies to get conversations back on track.
 *
 * Priority: 65 (runs after most intelligence modules)
 *
 * @example
 * ```typescript
 * // Config keys (under intelligence.smartRules):
 * // - enabled: boolean (default: true)
 * // - maxRetries: number (default: 2)
 * // - minResponseLength: number (default: 20)
 * // - loopDetectionWindow: number (default: 5)
 * // - confidenceThreshold: number (default: 0.7)
 * ```
 */

import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { detectDeadEnd, type DeadEndDetection } from './detectors.js'
import { getRecoveryStrategy, type RecoveryAction } from './strategies.js'

import type { ILogger } from '@cassicore/foundation'
import type { ModuleModelConfig } from '../base/cognitive-module.js'

export interface SmartRulesConfig {
  /** Enable/disable the module */
  enabled: boolean
  /** Maximum recovery attempts per session before giving up */
  maxRetries: number
  /** Minimum acceptable response length in characters */
  minResponseLength: number
  /** Number of recent turns to check for loop detection */
  loopDetectionWindow: number
  /** Minimum confidence threshold to trigger recovery */
  confidenceThreshold: number
}

const DEFAULT_CONFIG: SmartRulesConfig = {
  enabled: true,
  maxRetries: 2,
  minResponseLength: 20,
  loopDetectionWindow: 5,
  confidenceThreshold: 0.7,
}

/**
 * SmartRulesModule — Dead-end detection and recovery
 *
 * Monitors turn responses for patterns indicating the conversation is stuck:
 * - Empty responses with no tool calls
 * - Deflection language without attempted alternatives
 * - Repeated tool failures (tool loops)
 * - Repeated message patterns (stuck loops)
 *
 * When detected, emits recovery signals to help get back on track.
 */
export class SmartRulesModule extends BaseCognitiveModule {
  readonly name = 'smart-rules'
  readonly priority = 65

  private configValue: SmartRulesConfig = { ...DEFAULT_CONFIG }
  private sessionRetryCounts: Map<string, number> = new Map()

  constructor(logger: ILogger, modelConfig?: Partial<ModuleModelConfig>) {
    super(logger.child('smart-rules'), modelConfig)
    this.logger = logger.child('smart-rules')
  }

  async init(): Promise<void> {
    await super.init()

    // Load config from IConfig if available
    if (this.config) {
      try {
        const enabled = this.config.get<boolean>('intelligence.smartRules.enabled', DEFAULT_CONFIG.enabled)
        const maxRetries = this.config.get<number>('intelligence.smartRules.maxRetries', DEFAULT_CONFIG.maxRetries)
        const minResponseLength = this.config.get<number>('intelligence.smartRules.minResponseLength', DEFAULT_CONFIG.minResponseLength)
        const loopDetectionWindow = this.config.get<number>('intelligence.smartRules.loopDetectionWindow', DEFAULT_CONFIG.loopDetectionWindow)
        const confidenceThreshold = this.config.get<number>('intelligence.smartRules.confidenceThreshold', DEFAULT_CONFIG.confidenceThreshold)

        this.configValue = {
          enabled,
          maxRetries,
          minResponseLength,
          loopDetectionWindow,
          confidenceThreshold,
        }
      } catch (err) {
        this.logger.warn('Failed to load smart-rules config, using defaults', { error: String(err) })
      }
    }

    this.logger.info('SmartRules module initialized', {
      config: this.configValue,
    })
  }

  async start(): Promise<void> {
    await super.start()
    this.logger.info('SmartRules module started')
  }

  async stop(): Promise<void> {
    this.sessionRetryCounts.clear()
    await super.stop()
    this.logger.info('SmartRules module stopped')
  }

  /**
   * Get current configuration
   */
  getConfig(): Readonly<SmartRulesConfig> {
    return { ...this.configValue }
  }

  /**
   * Process turn:end events to detect dead-ends
   */
  protected override async onTurnEnd(sessionId: string, response: string, durationMs: number): Promise<void> {
    if (!this.configValue.enabled) {
      return
    }

    try {
      // Check if we've exceeded max retries for this session
      const retryCount = this.sessionRetryCounts.get(sessionId) ?? 0
      if (retryCount >= this.configValue.maxRetries) {
        this.logger.debug('Max retries exceeded for session', { sessionId, retryCount })
        return
      }

      // Get recent history for loop detection
      const recentHistory = await this.getRecentHistory(sessionId)

      // For now, we don't have direct access to tool call results in onTurnEnd
      // We'll pass empty array and rely on response text analysis
      // HOW: Wire toolExecutor to get actual tool call results
      const toolCalls: Array<{ name: string; success: boolean }> = []

      // Detect dead-end
      const detection = detectDeadEnd(response, toolCalls, recentHistory)

      if (detection && detection.confidence >= this.configValue.confidenceThreshold) {
        this.logger.info('Dead-end detected', {
          sessionId,
          type: detection.type,
          confidence: detection.confidence,
          details: detection.details,
        })

        // Get recovery strategy
        const recoveryAction = getRecoveryStrategy(detection)

        // Emit recovery signal
        this.emitRecoverySignal(sessionId, detection, recoveryAction)

        // Increment retry count
        this.sessionRetryCounts.set(sessionId, retryCount + 1)
      }
    } catch (err) {
      this.logger.error('Error in onTurnEnd', {
        sessionId,
        error: String(err),
      })
    }
  }

  /**
   * Get recent conversation history for loop detection
   */
  private async getRecentHistory(
    sessionId: string,
  ): Promise<Array<{ role: string; content: string; toolCalls?: Array<{ name: string }> }>> {
    if (!this.memory) {
      return []
    }

    try {
      // Type assertion: MemoryModule has getRecentTurns but IMemory interface doesn't declare it
      const memoryWithTurns = this.memory as any
      const recent: Array<{ role: string; content: string; toolCalls?: Array<{ name: string }> }> = await memoryWithTurns.getRecentTurns?.(sessionId, this.configValue.loopDetectionWindow) ?? []

      return recent.map((turn: any) => ({
        role: turn.role,
        content: turn.content,
        toolCalls: turn.toolCalls?.map((tc: any) => ({ name: tc.name })),
      }))
    } catch (err) {
      this.logger.debug('Failed to get recent history', {
        sessionId,
        error: String(err),
      })
      return []
    }
  }

  /**
   * Emit a recovery signal event
   */
  private emitRecoverySignal(
    sessionId: string,
    detection: DeadEndDetection,
    action: RecoveryAction,
  ): void {
    // Emit typed event for recovery signal
    this.eventBus?.emit({
      type: 'smart-rules:recovery' as any,
      sessionId,
      detection: {
        type: detection.type,
        confidence: detection.confidence,
        details: detection.details,
      },
      recoveryAction: {
        type: action.type,
        content: action.content,
      },
      timestamp: new Date(),
    })

    this.logger.debug('Recovery signal emitted', {
      sessionId,
      detectionType: detection.type,
      actionType: action.type,
    })
  }

  /**
   * Register event subscriptions
   */
  protected override registerSubscriptions(): void {
    // Subscribe to tool:round-complete to track tool failures
    this.subscribe('tool:round-complete' as any, async (event: any) => {
      if (!this.configValue.enabled) return

      const { sessionId, round, toolCalls, results } = event

      // Track tool failures for loop detection
      const failedTools = results
        .filter((r: any) => r.isError)
        .map((r: any) => r.toolCallId)

      if (failedTools.length > 0) {
        this.logger.debug('Tool failures detected', {
          sessionId,
          round,
          failedCount: failedTools.length,
        })
      }
    })

    this.logger.debug('SmartRules registered event subscriptions')
  }
}

/**
 * Factory function for creating SmartRulesModule instances
 */
export function createSmartRulesModule(
  logger: ILogger,
  modelConfig?: Partial<ModuleModelConfig>,
): SmartRulesModule {
  return new SmartRulesModule(logger, modelConfig)
}
