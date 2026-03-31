/**
 * Corpus Mini-Helix — Self-driving analysis loop for the Constellation coordinator
 *
 * Wraps the existing Corpus's state management and pattern detection with a
 * mini-Helix session. The LLM drives its own analysis loop:
 *
 *   1. Starts at constellation boot
 *   2. Reads branch state, digests, topics, patterns
 *   3. Sends directives, mediates tensions, elevates patterns
 *   4. Calls pause_until_trigger when the state is stable
 *   5. Resumes on safety-net triggers (cascades, stuck branches, escalations)
 *   6. Repeats until constellation completes
 *
 * The Corpus retains its existing class for state management (Corpus.ts),
 * but LLM analysis is delegated to the mini-Helix session instead of
 * the legacy runToolBasedAnalysis / runLegacyLLMAnalysis paths.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type {
  ICorpusTree,
  CorpusConfig,
  CorpusDeps,
  CorpusProcessedState,
  CrossHelixPattern,
  CorpusDirective,
} from './corpus-types.js'
import { createInitialProcessedState, DEFAULT_CORPUS_CONFIG } from './corpus-types.js'
import {
  buildCorpusSystemPrompt,
  createCorpusMiniHelixTools,
} from './corpus-tools.js'
import type { CorpusToolContext } from './corpus-tools.js'
import type { CrossHelixDialectic } from './cross-helix-dialectic.js'
import { createMiniHelixSession } from '../mini-helix/mini-helix-runner.js'
import type { MiniHelixSession, MiniHelixDeps, MiniHelixConfig } from '../mini-helix/mini-helix-types.js'

/**
 * Minimal interface for child Brainstems to avoid circular imports.
 */
interface MinimalBrainstem {
  onCorpusDirective?: (directive: CorpusDirective) => void
}

/**
 * Configuration specific to the Corpus mini-Helix mode.
 */
export interface CorpusMiniHelixConfig {
  /** Model tier for the Corpus mini-Helix. Default: 'qwenMax' */
  modelTier?: string
  /** Model name override (e.g., 'qwen3-max'). Optional. */
  modelName?: string
  /** Max tool-call iterations per analysis cycle. Default: 50 */
  maxIterationsPerCycle?: number
  /** Timeout per cycle in ms. Default: 120_000 */
  cycleTimeoutMs?: number
}

/**
 * CorpusMiniHelix — Manages the Corpus's mini-Helix session lifecycle.
 *
 * Owns the mini-Helix session, state, and trigger mechanism.
 * The existing Corpus class continues to own the tree, state, and pattern detection.
 */
export class CorpusMiniHelix {
  private session: MiniHelixSession | null = null
  private tree: ICorpusTree
  private deps: CorpusDeps
  private corpusConfig: CorpusConfig
  private miniHelixConfig: CorpusMiniHelixConfig
  private state: CorpusProcessedState
  private logger: ILogger

  // Child Brainstems
  private childBrainstems: Map<string, MinimalBrainstem> = new Map()

  // Lifecycle
  private running = false
  private shutdownRequested = false

  // Cross-Helix dialectic (optional)
  private crossHelixDialectic?: CrossHelixDialectic

  // Pattern state for the system prompt
  private crossPatterns: CrossHelixPattern[] = []

  // Escalation queue
  private escalationQueue: Array<{ reason: string; context: Record<string, unknown> }> = []

  // Mini-Helix deps
  private miniHelixDeps: MiniHelixDeps

  // Available tools in the worker Helixes (for system prompt awareness)
  private availableToolNames: string[]

  constructor(
    tree: ICorpusTree,
    deps: CorpusDeps,
    miniHelixDeps: MiniHelixDeps,
    config?: {
      corpus?: Partial<CorpusConfig>
      miniHelix?: CorpusMiniHelixConfig
    },
    availableToolNames?: string[],
  ) {
    this.tree = tree
    this.deps = deps
    this.miniHelixDeps = miniHelixDeps
    this.availableToolNames = availableToolNames ?? []
    this.corpusConfig = { ...DEFAULT_CORPUS_CONFIG, ...config?.corpus }
    this.miniHelixConfig = config?.miniHelix ?? {}
    this.state = createInitialProcessedState()
    this.logger = deps.logger.child('corpus-mini-helix')
    this.crossHelixDialectic = deps.crossHelixDialectic as CrossHelixDialectic | undefined
  }

  // ─── Public API ────────────────────────────────────────────────

  /** Register a child Brainstem for directive delivery */
  registerBrainstem(helixId: string, brainstem: MinimalBrainstem): void {
    this.childBrainstems.set(helixId, brainstem)
  }

  /** Unregister a Brainstem when its Helix completes */
  unregisterBrainstem(helixId: string): void {
    this.childBrainstems.delete(helixId)
  }

  /** Receive an escalation from a Brainstem */
  receiveEscalation(reason: string, context: Record<string, unknown>): void {
    this.escalationQueue.push({ reason, context })
    this.logger.info('Escalation received', { reason, context })

    // If paused, trigger resume
    if (this.session?.getStatus() === 'paused') {
      this.triggerResume(`Escalation: ${reason}`)
    }
  }

  /** Trigger a safety-net resume (cascade failure, stuck branch, tension, etc.) */
  triggerResume(reason: string): void {
    if (!this.session || this.shutdownRequested) return

    const status = this.session.getStatus()
    if (status === 'paused') {
      this.logger.info('Triggering Corpus resume', { reason })

      // Update system prompt with fresh state
      const prompt = this.buildSystemPrompt()
      this.session.updateSystemPrompt(prompt)

      // Inject trigger context
      const triggerMsg = this.buildTriggerMessage(reason)
      this.session.injectMessage({ role: 'user', content: triggerMsg })

      // Resume the session
      this.session.resume()

      // Run a new cycle
      this.runCycle().catch((err) => {
        this.logger.error('Triggered cycle failed', { error: String(err) })
      })
    }
  }

  /** Start the Corpus mini-Helix */
  async start(): Promise<void> {
    if (this.running) return
    this.running = true
    this.shutdownRequested = false

    this.logger.info('Corpus mini-Helix starting')

    // Build tool context
    const toolCtx = this.buildToolContext()

    // Create tools
    const tools = createCorpusMiniHelixTools(toolCtx)

    // Create session
    const config: MiniHelixConfig = {
      consumer: 'corpus',
      systemPrompt: this.buildSystemPrompt(),
      sessionId: `corpus-${this.deps.constellationId}`,
      constellationId: this.deps.constellationId,
      maxIterationsPerCycle: this.miniHelixConfig.maxIterationsPerCycle ?? 50,
      maxTokens: this.corpusConfig.maxTokens,
      cycleTimeoutMs: this.miniHelixConfig.cycleTimeoutMs ?? 120_000,
      modelTier: this.miniHelixConfig.modelTier ?? 'qwenMax',
      modelName: this.miniHelixConfig.modelName,
    }

    this.session = createMiniHelixSession(tools, config, this.miniHelixDeps)

    // Run initial cycle
    await this.runCycle()
  }

  /** Stop the Corpus mini-Helix */
  async stop(): Promise<void> {
    this.shutdownRequested = true
    this.running = false

    if (this.session) {
      this.session.cancel()
      await this.session.shutdown()
      this.session = null
    }

    this.logger.info('Corpus mini-Helix stopped')
  }

  /** Get current progress */
  getProgress() {
    return this.session?.getProgress() ?? null
  }

  /** Get state for the existing Corpus result interface */
  getState(): CorpusProcessedState {
    return this.state
  }


  // ─── Internal ──────────────────────────────────────────────────

  private async runCycle(): Promise<void> {
    if (!this.session || this.shutdownRequested) return

    try {
      // Build user message with any pending escalations
      let userMessage: string | undefined

      if (this.escalationQueue.length > 0) {
        const escalations = this.escalationQueue.splice(0)
        userMessage = `I've been woken by ${escalations.length} escalation(s):\n` +
          escalations.map((e, i) => `${i + 1}. ${e.reason} (context: ${JSON.stringify(e.context)})`).join('\n') +
          '\n\nAnalyze the current state and take appropriate action.'
      }

      // Update system prompt with fresh state
      this.session.updateSystemPrompt(this.buildSystemPrompt())

      const result = await this.session.run(userMessage)

      this.logger.info('Corpus cycle completed', {
        status: result.status,
        toolCalls: result.toolCalls,
        llmCalls: result.llmCalls,
      })

      // If the session completed (signal_done), keep running in a loop
      if (result.status === 'completed' && !this.shutdownRequested) {
        // Small delay before next cycle
        await new Promise((resolve) => setTimeout(resolve, this.corpusConfig.idlePollMs))
        await this.runCycle()
      }

      // If paused (pause_until_trigger), we wait for triggerResume()
      // Nothing to do here — the session is paused
    } catch (err) {
      this.logger.error('Corpus cycle error', { error: String(err) })
    }
  }

  private buildSystemPrompt(): string {
    return buildCorpusSystemPrompt(
      this.deps.goal,
      this.state,
      this.tree,
      this.crossPatterns,
      this.availableToolNames,
    )
  }

  private buildTriggerMessage(reason: string): string {
    return `I've been woken because: ${reason}\n\n` +
      'Analyze the current state and determine what action is needed.'
  }

  private buildToolContext(): CorpusToolContext {
    return {
      tree: this.tree,
      state: this.state,
      deps: this.deps,
      config: this.corpusConfig,
      logger: this.logger,
      crossHelixDialectic: this.crossHelixDialectic,
      sendDirective: (directive) => {
        const brainstem = this.childBrainstems.get(directive.targetHelixId)
        if (brainstem?.onCorpusDirective) {
          brainstem.onCorpusDirective(directive)
          this.logger.info('Directive sent', {
            target: directive.targetHelixId,
            type: directive.type,
          })
        } else {
          this.logger.warn('No Brainstem registered for directive target', {
            target: directive.targetHelixId,
          })
        }
      },
      requestSpawn: (request) => {
        if (this.deps.onSpawnRequest) {
          this.deps.onSpawnRequest(request)
        }
      },
    }
  }
}
