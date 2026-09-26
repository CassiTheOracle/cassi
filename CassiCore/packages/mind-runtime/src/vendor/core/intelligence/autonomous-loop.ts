/**
 * AutonomousAgentLoop — Core execution engine for autonomous agents.
 *
 * Drives an agent through repeated pipeline.process() iterations, where each
 * iteration is a full LLM call with tool access, intelligence context, and
 * sibling awareness.  The agent decides what to do next by emitting structured
 * JSON decisions at the end of each turn.
 *
 * Modelled on the dialectic swarm loop pattern:
 * - setTimeout-based scheduling (never setInterval) to prevent overlapping ticks
 * - busy flag guard
 * - iteration counting with configurable max
 * - history persistence via memory.kv_set()
 * - event emission for monitoring
 * - error handling with busy=false in finally block
 *
 * Decision schema (validated by AJV, same as MultiAgentCoordinator.autonomyValidator):
 *   { action: 'continue' | 'complete' | 'delegate' | 'blocked',
 *     result?: string, reason?: string, delegateTo?: string, delegateTask?: string }
 */

import Ajv from 'ajv'

import type { SessionDigestStore, SessionMessage } from './session-digest.js'
import type { IDialecticSystem, YangContext } from '@cassicore/foundation'
import type { IExecutionBackend } from '@cassicore/foundation'
import type { IMemory } from '@cassicore/foundation'
import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { InboundMessage, TurnResult, ISessionManager, SessionConfig } from '@cassicore/foundation'
// REMOVED: TurnPipeline import deleted — execution backend is always used
import type { ValidateFunction } from 'ajv'


export type AgentDecision =
  | { action: 'continue'; reason?: string }
  | { action: 'complete'; result: string; reason?: string }
  | { action: 'delegate'; delegateTo: string; delegateTask: string; reason?: string }
  | { action: 'blocked'; reason: string }

export interface AutonomousLoopOpts {
  /** Delay between iterations in ms (default: 2000) */
  intervalMs?: number
  /** Maximum iterations before forced stop (default: 250) */
  maxIterations?: number
  /** Maximum total tokens across all iterations (default: 2500000) */
  maxTokens?: number
  /** Timeout in ms from start (default: 4 hours) */
  timeoutMs?: number
  /** Whether the agent may perform destructive operations */
  allowDestructive?: boolean
  /** Initial task description for the first iteration */
  initialTask?: string
  /**
   * Provider configuration for this agent's LLM calls.
   * Applied to the session config before the first iteration so that the
   * pipeline resolves the correct provider/model instead of using daemon defaults.
   */
  provider?: { model?: string; providerId?: string; thinking?: string }
  /** Custom system prompt override for this agent */
  systemPrompt?: string
  /** Parent session ID (for hierarchy tracking in execution backends) */
  parentSessionId?: string
  /**
   * Force use of the CassiCore-native TurnPipeline even when an execution
   * backend (e.g. OpenCode) is globally wired.  Use this for internal
   * CassiCore agents (team coordinators, sub-agents) that should run turns
   * directly through the pipeline rather than via an external relay.
   */
  forceNativePipeline?: boolean
  /** Callback when the agent emits a 'delegate' decision */
  onDelegate?: (agentId: string, delegateTo: string, delegateTask: string) => Promise<void> | void
  /** Callback when the agent emits a 'blocked' decision */
  onBlocked?: (agentId: string, reason: string) => Promise<void> | void
}

interface LoopState {
  agentId: string
  sessionId: string
  timer?: ReturnType<typeof setTimeout>
  iterations: number
  totalTokensUsed: number
  busy: boolean
  paused: boolean
  stopped: boolean
  startedAt: number
  opts: Required<Pick<AutonomousLoopOpts, 'intervalMs' | 'maxIterations' | 'maxTokens' | 'timeoutMs' | 'allowDestructive'>> & {
    initialTask?: string
    forceNativePipeline?: boolean
    onDelegate?: AutonomousLoopOpts['onDelegate']
    onBlocked?: AutonomousLoopOpts['onBlocked']
  }
  /** Text summary of previous iteration's result, fed as context into the next */
  lastResult?: string
  history: Array<{
    iteration: number
    timestamp: number
    decision?: AgentDecision
    tokensUsed: number
    durationMs: number
    error?: string
  }>
}


const DECISION_SCHEMA = {
  type: 'object',
  properties: {
    action: { type: 'string', enum: ['continue', 'complete', 'delegate', 'blocked'] },
    result: { type: 'string' },
    reason: { type: 'string' },
    delegateTo: { type: 'string' },
    delegateTask: { type: 'string' },
  },
  required: ['action'],
  additionalProperties: true,
  allOf: [
    { if: { properties: { action: { const: 'complete' } } }, then: { required: ['result'] } },
    { if: { properties: { action: { const: 'delegate' } } }, then: { required: ['delegateTo', 'delegateTask'] } },
    { if: { properties: { action: { const: 'blocked' } } }, then: { required: ['reason'] } },
  ],
} as const


const DECISION_SUFFIX = `

When you have finished your work for this iteration, output a JSON decision block wrapped in <decision> tags:

<decision>
{"action": "continue", "reason": "need to finish implementing the remaining tests"}
</decision>

Valid actions:
- "continue" — you have more work to do; include "reason" explaining what's next
- "complete" — you have finished the assigned task; include "result" with a summary of what was accomplished
- "delegate" — you need another specialist; include "delegateTo" (role name) and "delegateTask" (task description)
- "blocked" — you cannot proceed; include "reason" explaining why

If you do not emit a <decision> block, the loop will assume "continue".`


export class AutonomousAgentLoop {
  private logger: ILogger
  private loops = new Map<string, LoopState>()
  private decisionValidator?: ValidateFunction

  // External dependencies (wired after construction)
  // REMOVED: pipeline property deleted — execution backend is always wired
  private backend?: IExecutionBackend
  private memory?: IMemory
  private eventBus?: IEventBus
  private digestStore?: SessionDigestStore
  private sessions?: ISessionManager
  private dialectic?: IDialecticSystem

  constructor(logger: ILogger) {
    this.logger = logger.child?.('autonomous-loop') ?? logger

    // Build AJV validator
    try {
      const ajv = new (Ajv as any)({ allErrors: true, strict: false })
      this.decisionValidator = (ajv as any).compile(DECISION_SCHEMA as any)
    } catch (e) {
      this.logger.debug('AutonomousAgentLoop: failed to initialise AJV validator', { error: String(e) })
    }
  }


  // REMOVED: setPipeline() deleted — use setBackend() with CassiCoreExecutionBackend instead

  /**
   * Set the execution backend. Required for autonomous loop execution.
   * Use CassiCoreExecutionBackend wrapping SessionPipeline.
   */
  setBackend(backend: IExecutionBackend): void {
    this.backend = backend
    this.logger.info('AutonomousLoop: execution backend set', { backend: backend.name })
  }

  /** Get the active execution backend name (for diagnostics) */
  getBackendName(): string {
    return this.backend?.name ?? 'none'
  }

  setMemory(memory: IMemory): void {
    this.memory = memory
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus
  }

  setDigestStore(store: SessionDigestStore): void {
    this.digestStore = store
  }

  setSessions(sessions: ISessionManager): void {
    this.sessions = sessions
  }

  setDialectic(dialectic: IDialecticSystem): void {
    this.dialectic = dialectic
  }


  /**
   * Start an autonomous iteration loop for the given agent.
   * The agent must already exist in the MultiAgentCoordinator.
   */
  async start(agentId: string, sessionId: string, opts: AutonomousLoopOpts = {}): Promise<void> {
    if (this.loops.has(agentId)) {
      throw new Error(`Autonomous loop already running for agent ${agentId}`)
    }
    if (!this.backend) {
      throw new Error('AutonomousAgentLoop: no execution backend wired — call setBackend() first')
    }

    // If a provider config was supplied, apply it to the session so the pipeline
    // resolves the correct provider/model instead of falling back to daemon defaults.
    if (opts.provider && this.sessions) {
      this.configureSessionProvider(sessionId, opts.provider)
    }

    // Determine which execution path this agent will use.
    // forceNativePipeline bypasses the globally-wired backend (e.g. OpenCode)
    // and runs turns directly through TurnPipeline — required for internal
    // CassiCore agents (team coordinators, sub-agents) so they don't loop
    // through the IDE as a relay.
    const useBackend = this.backend && !opts.forceNativePipeline

    // If using an execution backend, await session initialization before
    // scheduling the first iteration.  Previously this was fire-and-forget,
    // causing iteration 1 to always fail with "no OpenCode session".
    if (useBackend) {
      try {
        await this.backend!.initAgentSession(agentId, sessionId, {
          initialTask: opts.initialTask,
          provider: opts.provider,
          systemPrompt: opts.systemPrompt,
          parentSessionId: opts.parentSessionId,
        })
      } catch (err) {
        this.logger.error('AutonomousLoop: backend initAgentSession failed', { agentId, error: String(err) })
        // Non-fatal: iteration 1 will fail but may retry after backoff
      }
    }

    const state: LoopState = {
      agentId,
      sessionId,
      iterations: 0,
      totalTokensUsed: 0,
      busy: false,
      paused: false,
      stopped: false,
      startedAt: Date.now(),
      opts: {
        intervalMs: opts.intervalMs ?? 2000,
        maxIterations: opts.maxIterations ?? 250,
        maxTokens: opts.maxTokens ?? 2_500_000,
        timeoutMs: opts.timeoutMs ?? 4 * 60 * 60 * 1000,
        allowDestructive: opts.allowDestructive ?? false,
        initialTask: opts.initialTask,
        forceNativePipeline: opts.forceNativePipeline ?? false,
        onDelegate: opts.onDelegate,
        onBlocked: opts.onBlocked,
      },
      history: [],
    }

    this.loops.set(agentId, state)

    this.logger.info('AutonomousLoop: started', {
      agentId,
      sessionId,
      intervalMs: state.opts.intervalMs,
      maxIterations: state.opts.maxIterations,
      maxTokens: state.opts.maxTokens,
      timeoutMs: state.opts.timeoutMs,
      forceNativePipeline: state.opts.forceNativePipeline,
    })

    this.emitEvent('autonomy:loop_started', { agentId, sessionId, opts: state.opts })

    // Schedule first iteration immediately
    state.timer = setTimeout(() => void this.runIteration(agentId).catch(() => {}), 0)
    try { (state.timer as any).unref?.() } catch {}
  }

  /** Stop the loop. Clears timer and marks the agent as stopped. */
  stop(agentId: string, reason = 'stopped'): void {
    const state = this.loops.get(agentId)
    if (!state) return

    state.stopped = true
    if (state.timer) {
      clearTimeout(state.timer)
      state.timer = undefined
    }
    this.loops.delete(agentId)

    this.logger.info('AutonomousLoop: stopped', { agentId, reason, iterations: state.iterations, totalTokens: state.totalTokensUsed })
    this.emitEvent('autonomy:loop_stopped', { agentId, reason, iterations: state.iterations, totalTokensUsed: state.totalTokensUsed })

    // Clean up backend session (fire-and-forget)
    if (this.backend) {
      this.backend.destroyAgentSession(agentId).catch(err => {
        this.logger.warn('AutonomousLoop: backend destroyAgentSession failed', { agentId, error: String(err) })
      })
    }

    // Emit agent:error for failure conditions so listeners (TeamOrchestrator, MultiAgentCoordinator) can react
    const nonFailureReasons = new Set(['completed', 'stopped'])
    if (!nonFailureReasons.has(reason)) {
      this.emitEvent('agent:error', { agentId, error: `Autonomous loop stopped: ${reason}`, reason })
    }

    // Persist final history
    void this.persistHistory(agentId, state).catch(() => {})
  }

  /** Pause the loop. The current iteration (if running) will finish, then no more ticks. */
  pause(agentId: string): void {
    const state = this.loops.get(agentId)
    if (!state) return
    state.paused = true
    if (state.timer) {
      clearTimeout(state.timer)
      state.timer = undefined
    }
    this.logger.info('AutonomousLoop: paused', { agentId })
    this.emitEvent('autonomy:loop_paused', { agentId })
  }

  /** Resume a paused loop. Schedules the next iteration immediately. */
  resume(agentId: string): void {
    const state = this.loops.get(agentId)
    if (!state) return
    if (!state.paused) return
    state.paused = false
    this.logger.info('AutonomousLoop: resumed', { agentId })
    this.emitEvent('autonomy:loop_resumed', { agentId })

    // Schedule next tick immediately
    state.timer = setTimeout(() => void this.runIteration(agentId).catch(() => {}), 0)
    try { (state.timer as any).unref?.() } catch {}
  }

  /** Check if an agent has a running loop. */
  isRunning(agentId: string): boolean {
    const state = this.loops.get(agentId)
    return state != null && !state.stopped
  }

  /** Check if an agent's loop is paused. */
  isPaused(agentId: string): boolean {
    return this.loops.get(agentId)?.paused ?? false
  }

  /** Get loop status for monitoring. */
  getStatus(agentId: string): { iterations: number; totalTokensUsed: number; paused: boolean; elapsedMs: number; history: LoopState['history'] } | undefined {
    const state = this.loops.get(agentId)
    if (!state) return undefined
    return {
      iterations: state.iterations,
      totalTokensUsed: state.totalTokensUsed,
      paused: state.paused,
      elapsedMs: Date.now() - state.startedAt,
      history: state.history,
    }
  }

  /** List all active loops. */
  listActive(): Array<{ agentId: string; sessionId: string; iterations: number; paused: boolean }> {
    return Array.from(this.loops.entries()).map(([agentId, s]) => ({
      agentId,
      sessionId: s.sessionId,
      iterations: s.iterations,
      paused: s.paused,
    }))
  }

  /** Stop all running loops (used during daemon shutdown). */
  stopAll(reason = 'shutdown'): void {
    const isDaemonRestart = reason === 'daemon-restart'
    const agentIds = Array.from(this.loops.keys())

    // Write manifest of active agents before stopping (for restart recovery)
    if (isDaemonRestart && this.memory && agentIds.length > 0) {
      void this.memory.kv_set('autonomous:loop:restart_manifest', agentIds).catch(err => {
        this.logger.warn('Failed to persist restart manifest', { error: String(err) })
      })
    }

    for (const agentId of agentIds) {
      // Persist full loop state before stopping when restarting
      if (isDaemonRestart) {
        const state = this.loops.get(agentId)
        if (state) {
          void this.persistLoopState(agentId, state).catch(err => {
            this.logger.warn('Failed to persist loop state during restart', { agentId, error: String(err) })
          })
        }
      }
      this.stop(agentId, reason)
    }
    if (isDaemonRestart) {
      this.logger.info('AutonomousLoop: all loops stopped for daemon restart — state persisted')
    }
  }

  /**
   * Persist full loop state for restart recovery.
   * Saved to memory.kv_set so it survives daemon restart.
   */
  private async persistLoopState(agentId: string, state: LoopState): Promise<void> {
    if (!this.memory) return
    try {
      await this.memory.kv_set(`autonomous:loop:${agentId}:restart_state`, {
        agentId: state.agentId,
        sessionId: state.sessionId,
        iterations: state.iterations,
        totalTokensUsed: state.totalTokensUsed,
        startedAt: state.startedAt,
        stoppedAt: Date.now(),
        opts: {
          intervalMs: state.opts.intervalMs,
          maxIterations: state.opts.maxIterations,
          maxTokens: state.opts.maxTokens,
          timeoutMs: state.opts.timeoutMs,
          allowDestructive: state.opts.allowDestructive,
          initialTask: state.opts.initialTask,
          forceNativePipeline: state.opts.forceNativePipeline,
        },
        lastResult: state.lastResult,
      })
    } catch (err) {
      this.logger.debug('AutonomousLoop: failed to persist loop state', { agentId, error: String(err) })
    }
  }

  /** Max downtime (ms) for auto-resuming loops after daemon restart */
  static readonly RESUME_MAX_DOWNTIME_MS = 60_000

  /**
   * Restore loops that were interrupted by a daemon restart.
   * Only resumes loops that were stopped < 60s ago.
   * @returns Number of loops restored
   */
  async restoreLoops(): Promise<number> {
    if (!this.memory) return 0

    const now = Date.now()
    let restored = 0

    try {
      // Scan for persisted restart states
      // The kv store doesn't support prefix listing, so we track active agents
      // via a dedicated key that stopAll writes
      const manifest = await this.memory.kv_get<string[]>('autonomous:loop:restart_manifest')
      if (!manifest || manifest.length === 0) return 0

      for (const agentId of manifest) {
        try {
          const saved = await this.memory.kv_get<{
            agentId: string
            sessionId: string
            iterations: number
            totalTokensUsed: number
            startedAt: number
            stoppedAt: number
            opts: {
              intervalMs: number
              maxIterations: number
              maxTokens: number
              timeoutMs: number
              allowDestructive: boolean
              initialTask?: string
              forceNativePipeline?: boolean
            }
            lastResult?: string
          }>(`autonomous:loop:${agentId}:restart_state`)

          if (!saved) continue

          // Enforce 60s downtime policy
          const downtimeMs = now - saved.stoppedAt
          if (downtimeMs > AutonomousAgentLoop.RESUME_MAX_DOWNTIME_MS) {
            this.logger.info('AutonomousLoop: skipping restore — too long since shutdown', {
              agentId,
              downtimeMs,
              maxMs: AutonomousAgentLoop.RESUME_MAX_DOWNTIME_MS,
            })
            // Clean up stale state
            await this.memory.kv_set(`autonomous:loop:${agentId}:restart_state`, undefined)
            continue
          }

          // Budget tracking on restore — warn but don't skip
          if (saved.iterations >= saved.opts.maxIterations || saved.totalTokensUsed >= saved.opts.maxTokens) {
            this.logger.warn('AutonomousLoop: restoring loop with budget exceeded (tracking only)', { agentId })
          }

          // Resume the loop with remaining budget
          this.logger.info('AutonomousLoop: restoring loop after daemon restart', {
            agentId,
            sessionId: saved.sessionId,
            iterations: saved.iterations,
            downtimeMs,
          })

          this.start(agentId, saved.sessionId, {
            intervalMs: saved.opts.intervalMs,
            maxIterations: saved.opts.maxIterations,
            maxTokens: saved.opts.maxTokens,
            timeoutMs: saved.opts.timeoutMs,
            allowDestructive: saved.opts.allowDestructive,
            initialTask: saved.lastResult
              ? `[RESUMED after daemon restart — ${downtimeMs}ms downtime] Continue from where you left off. Previous context: ${saved.lastResult}`
              : saved.opts.initialTask,
            forceNativePipeline: saved.opts.forceNativePipeline,
          })

          // Carry forward iteration count and token usage
          const restoredState = this.loops.get(agentId)
          if (restoredState) {
            restoredState.iterations = saved.iterations
            restoredState.totalTokensUsed = saved.totalTokensUsed
          }

          // Clean up persisted state
          await this.memory.kv_set(`autonomous:loop:${agentId}:restart_state`, undefined)
          restored++
        } catch (err) {
          this.logger.warn('AutonomousLoop: failed to restore loop', { agentId, error: String(err) })
        }
      }

      // Clean up manifest
      await this.memory.kv_set('autonomous:loop:restart_manifest', undefined)
    } catch (err) {
      this.logger.warn('AutonomousLoop: restoreLoops failed', { error: String(err) })
    }

    if (restored > 0) {
      this.logger.info(`AutonomousLoop: restored ${restored} loop(s) after daemon restart`)
    }
    return restored
  }


  private async runIteration(agentId: string): Promise<void> {
    const state = this.loops.get(agentId)
    if (!state || state.stopped || state.paused || state.busy) return

    // Check stop conditions before running (warnings only — never stop on budget)
    if (state.iterations >= state.opts.maxIterations) {
      this.logger.warn('AutonomousLoop: maxIterations reached — continuing (tracking only)', {
        agentId,
        iterations: state.iterations,
        maxIterations: state.opts.maxIterations,
      })
    }
    if (state.totalTokensUsed >= state.opts.maxTokens) {
      this.logger.warn('AutonomousLoop: maxTokens reached — continuing (tracking only)', {
        agentId,
        totalTokensUsed: state.totalTokensUsed,
        maxTokens: state.opts.maxTokens,
      })
    }
    if (Date.now() - state.startedAt >= state.opts.timeoutMs) {
      this.logger.warn('AutonomousLoop: timeout reached — continuing (tracking only)', {
        agentId,
        elapsedMs: Date.now() - state.startedAt,
        timeoutMs: state.opts.timeoutMs,
      })
    }

    state.busy = true
    state.iterations += 1
    const iteration = state.iterations
    const iterStart = Date.now()

    try {
      // 1. Build inbound message for this iteration
      const inbound = this.buildInboundMessage(agentId, state)

      // 2. Execute iteration — via backend (required)
      // REMOVED: forceNativePipeline fallback deleted — backend is always used
      const result: TurnResult = await this.backend!.execute(inbound)

      // 3. Track token usage
      state.totalTokensUsed += result.tokensUsed || 0

      // 3b. Emit tool:round-complete for cognitive modules (Reverie, Reflex, etc.)
      // This bridges the OpenCode execution path into the CassiCore event system.
      if (result.toolCalls && result.toolCalls.length > 0) {
        this.emitEvent('tool:round-complete', {
          sessionId: inbound.sessionId,
          round: iteration,
          toolCalls: result.toolCalls.map((tc, idx) => ({ name: tc.name, id: `auto-${idx}` })),
          results: (result.tool_outputs ?? []).map(r => ({
            toolCallId: r.tool_call_id ?? 'unknown',
            isError: r.is_error,
            contentPreview: typeof r.output === 'string' ? r.output : String(r.output ?? ''),
          })),
          timestamp: new Date(),
        })
      }

      // 4. Parse decision from response
      const decision = this.parseDecision(result.response)

      // 5. Record iteration history
      const entry = {
        iteration,
        timestamp: Date.now(),
        decision,
        tokensUsed: result.tokensUsed || 0,
        durationMs: Date.now() - iterStart,
      }
      state.history.push(entry)

      // Trim history for safety (keep last 500 entries)
      if (state.history.length > 500) {
        state.history = state.history.slice(-500)
      }

      // 6. Store last result for context continuity
      state.lastResult = result.response

      // 7. Emit iteration event
      this.emitEvent('autonomy:iteration', {
        agentId,
        iteration,
        decision,
        tokensUsed: result.tokensUsed,
        totalTokensUsed: state.totalTokensUsed,
        durationMs: entry.durationMs,
        toolCalls: result.toolCalls?.length ?? 0,
      })

      // 8. Persist history periodically (every 5 iterations)
      if (iteration % 5 === 0) {
        void this.persistHistory(agentId, state).catch(() => {})
      }

      // 8b. Fire continuous dialectic analysis of this iteration's work product.
      // Signals are queued in pendingDialecticSignals and injected by the pipeline
      // at the start of a subsequent iteration — no blocking, no modification to
      // the existing injection mechanism.
      this.fireIterationDialectic(agentId, state, result, decision)

      // 9. Act on decision
      const nextDelayMs = await this.handleDecision(agentId, state, decision, result)

      // 10. Schedule next iteration (if not stopped by decision handler)
      if (!state.stopped && !state.paused && this.loops.has(agentId)) {
        state.timer = setTimeout(
          () => void this.runIteration(agentId).catch(() => {}),
          nextDelayMs,
        )
        try { (state.timer as any).unref?.() } catch {}
      }

    } catch (err) {
      const errStr = String(err)
      this.logger.warn('AutonomousLoop: iteration error', { agentId, iteration, error: errStr })

      state.history.push({
        iteration,
        timestamp: Date.now(),
        tokensUsed: 0,
        durationMs: Date.now() - iterStart,
        error: errStr,
      })

      this.emitEvent('autonomy:iteration_error', { agentId, iteration, error: errStr })

      // Fail fast on provider configuration errors — retrying won't help
      if (errStr.includes('Provider') && (errStr.includes('not loaded') || errStr.includes('not available'))) {
        this.logger.error('AutonomousLoop: provider not available — stopping loop to avoid wasting iterations', { agentId, error: errStr })
        this.stop(agentId, 'provider_unavailable')
        return
      }

      // On error, schedule retry with exponential backoff (capped at 30s)
      const backoffMs = Math.min(state.opts.intervalMs * Math.pow(2, Math.min(state.history.filter(h => h.error).length, 5)), 30_000)
      if (!state.stopped && !state.paused && this.loops.has(agentId)) {
        state.timer = setTimeout(
          () => void this.runIteration(agentId).catch(() => {}),
          backoffMs,
        )
        try { (state.timer as any).unref?.() } catch {}
      }
    } finally {
      state.busy = false
    }
  }


  private buildInboundMessage(agentId: string, state: LoopState): InboundMessage {
    const iteration = state.iterations
    let content: string

    if (iteration === 1) {
      // First iteration: provide the initial task
      content = this.buildFirstIterationPrompt(agentId, state)
    } else {
      // Subsequent iterations: continuation with previous result summary + budget
      content = this.buildContinuationPrompt(agentId, state)
    }

    return {
      id: `autonomous-${agentId}-iter-${iteration}`,
      sessionId: state.sessionId,
      channelId: 'autonomous',
      senderId: 'autonomous-loop',
      senderName: 'Autonomous Agent Loop',
      content,
      timestamp: new Date(),
      metadata: {
        autonomous: true,
        agentId,
        iteration,
        totalTokensUsed: state.totalTokensUsed,
        budgetRemaining: state.opts.maxTokens - state.totalTokensUsed,
      },
    }
  }

  private buildFirstIterationPrompt(agentId: string, state: LoopState): string {
    const taskDescription = state.opts.initialTask || 'No specific task assigned. Await instructions.'

    // Check for unread mailbox messages
    const mailbox = this.getMailboxMessages(state.sessionId)
    const mailboxSection = mailbox.length > 0
      ? `\n\n## Unread Messages\n${mailbox.map(m => `- From ${m.fromTopic} (${m.fromSessionId}): ${m.content}`).join('\n')}`
      : ''

    return `# Autonomous Agent Task

You are an autonomous agent operating in a team. You have full tool access and will work iteratively until your task is complete.

## Your Task
${taskDescription}

## Budget
- Iterations: 1/${state.opts.maxIterations}
- Tokens: 0/${state.opts.maxTokens.toLocaleString()} used
- Time limit: ${Math.round(state.opts.timeoutMs / 60000)} minutes
${state.opts.allowDestructive ? '- Destructive operations: ALLOWED' : '- Destructive operations: NOT ALLOWED — do not perform destructive edits'}
${mailboxSection}
${DECISION_SUFFIX}`
  }

  private buildContinuationPrompt(agentId: string, state: LoopState): string {
    const budgetPct = Math.round((state.totalTokensUsed / state.opts.maxTokens) * 100)
    const elapsedMin = Math.round((Date.now() - state.startedAt) / 60000)
    const timeRemainingMin = Math.max(0, Math.round((state.opts.timeoutMs - (Date.now() - state.startedAt)) / 60000))

    // Check for unread mailbox messages
    const mailbox = this.getMailboxMessages(state.sessionId)
    const mailboxSection = mailbox.length > 0
      ? `\n\n## New Messages\n${mailbox.map(m => `- From ${m.fromTopic} (${m.fromSessionId}): ${m.content}`).join('\n')}`
      : ''

    // Previous iteration summary (truncated)
    const prevSummary = state.lastResult
      ? state.lastResult.slice(0, 2000)
      : '(no previous output)'

    return `# Continuation — Iteration ${state.iterations}

## Budget Status
- Iterations: ${state.iterations}/${state.opts.maxIterations}
- Tokens: ${state.totalTokensUsed.toLocaleString()}/${state.opts.maxTokens.toLocaleString()} (${budgetPct}% used)
- Elapsed: ${elapsedMin}min | Remaining: ${timeRemainingMin}min

## Previous Iteration Summary
${prevSummary}
${mailboxSection}

Continue working on your assigned task. Use tools as needed, then emit your decision.
${DECISION_SUFFIX}`
  }


  private parseDecision(response: string): AgentDecision {
    // Look for <decision>...</decision> block
    const match = response.match(/<decision>\s*([\s\S]*?)\s*<\/decision>/i)
    if (!match) {
      // No decision block — default to continue
      return { action: 'continue', reason: 'no explicit decision emitted' }
    }

    try {
      const parsed = JSON.parse(match[1])

      // Validate with AJV if available
      if (this.decisionValidator) {
        const valid = this.decisionValidator(parsed)
        if (!valid) {
          const errors = (this.decisionValidator.errors || []).map((e: any) => `${e.instancePath || ''} ${e.message || ''}`).join('; ')
          this.logger.debug('AutonomousLoop: decision validation failed, defaulting to continue', { errors })
          return { action: 'continue', reason: `invalid decision schema: ${errors}` }
        }
      }

      return parsed as AgentDecision
    } catch (err) {
      this.logger.debug('AutonomousLoop: failed to parse decision JSON', { error: String(err) })
      return { action: 'continue', reason: 'failed to parse decision JSON' }
    }
  }


  /**
   * Act on the agent's decision. Returns the delay (ms) before the next iteration.
   */
  private async handleDecision(
    agentId: string,
    state: LoopState,
    decision: AgentDecision,
    turnResult: TurnResult,
  ): Promise<number> {
    switch (decision.action) {
      case 'continue':
        return state.opts.intervalMs

      case 'complete': {
        // Agent declares task complete — stop loop
        this.logger.info('AutonomousLoop: agent completed task', { agentId, resultLength: decision.result.length })

        this.stop(agentId, 'completed')
        return 0
      }

      case 'delegate': {
        // Agent wants to delegate to another specialist
        this.logger.info('AutonomousLoop: agent requesting delegation', {
          agentId,
          delegateTo: decision.delegateTo,
          delegateTask: decision.delegateTask,
        })
        this.emitEvent('autonomy:delegation_requested', {
          agentId,
          delegateTo: decision.delegateTo,
          delegateTask: decision.delegateTask,
        })

        if (state.opts.onDelegate) {
          try {
            await Promise.resolve(state.opts.onDelegate(agentId, decision.delegateTo, decision.delegateTask))
          } catch (err) {
            this.logger.warn('AutonomousLoop: onDelegate callback failed', { agentId, error: String(err) })
          }
        }

        // Continue after delegation (coordinator may assign sub-tasks)
        return state.opts.intervalMs
      }

      case 'blocked': {
        // Agent is blocked — notify and apply backoff
        this.logger.warn('AutonomousLoop: agent blocked', { agentId, reason: decision.reason })
        this.emitEvent('autonomy:blocked', { agentId, reason: decision.reason })

        // Send mailbox message to coordinator session if digest store is available
        if (this.digestStore) {
          try {
            this.digestStore.sendMessage(state.sessionId, state.sessionId, `Agent ${agentId} blocked: ${decision.reason}`)
          } catch (err) {
            this.logger.debug('AutonomousLoop: failed to send blocked message to digest', { error: String(err) })
          }
        }

        if (state.opts.onBlocked) {
          try {
            await Promise.resolve(state.opts.onBlocked(agentId, decision.reason))
          } catch (err) {
            this.logger.warn('AutonomousLoop: onBlocked callback failed', { agentId, error: String(err) })
          }
        }

        // Exponential backoff on blocked: 2x, 4x, 8x... capped at 60s
        const blockedCount = state.history.filter(h => h.decision?.action === 'blocked').length
        const backoffMs = Math.min(state.opts.intervalMs * Math.pow(2, Math.min(blockedCount, 5)), 60_000)
        return backoffMs
      }

      default:
        return state.opts.intervalMs
    }
  }


  /**
   * Fire dialectic analysis of an iteration's work product (fire-and-forget).
   *
   * The dialectic runs Yang (expansion) + Yin (critique) + Serenity (synthesis)
   * against a structured summary of what the agent just did.  Any urgent signals
   * are emitted via `dialectic:signal` on the event bus and automatically
   * queued in the pipeline's `pendingDialecticSignals` map, where they get
   * injected at the top of a subsequent iteration as `[DIALECTIC ANALYSIS]`
   * system messages.
   *
   * Cache is explicitly skipped because autonomous continuation prompts share
   * boilerplate structure that would trigger false Jaccard cache hits.
   */
  private fireIterationDialectic(
    agentId: string,
    state: LoopState,
    result: TurnResult,
    decision: AgentDecision,
  ): void {
    if (!this.dialectic) return

    const iteration = state.iterations
    const content = this.buildDialecticInput(agentId, state, result, decision)

    // Compose autonomous-aware context
    const context: YangContext = {
      recentMemories: [],
      availableTools: result.toolCalls?.map(tc => tc.name) ?? [],
      sessionHistory: [],   // Session history is already in the pipeline; keep lightweight
      toolOutputs: result.tool_outputs?.map(
        to => `${to.tool_name}${to.is_error ? ' [ERROR]' : ''}: ${to.output.slice(0, 500)}`,
      ) ?? [],
      agentDecision: decision.action,
      iterationNumber: iteration,
    }

    // Fire-and-forget — signals land in pendingDialecticSignals for next iteration
    this.dialectic.processTurn(
      state.sessionId,
      `autonomous-${agentId}-iter-${iteration}`,
      content,
      context,
      { skipCache: true },
    ).catch(err => {
      this.logger.debug('AutonomousLoop: dialectic analysis failed (non-fatal)', {
        agentId,
        iteration,
        error: String(err),
      })
    })
  }

  /**
   * Build a structured text summary of the iteration for dialectic analysis.
   * This is what Yang/Yin/Serenity actually analyze — the agent's work product,
   * not the boilerplate continuation prompt.
   */
  private buildDialecticInput(
    agentId: string,
    state: LoopState,
    result: TurnResult,
    decision: AgentDecision,
  ): string {
    const iteration = state.iterations
    const budgetPct = Math.round((state.totalTokensUsed / state.opts.maxTokens) * 100)

    // Summarize tool calls
    const toolSection = result.toolCalls?.length
      ? `Tools used: ${result.toolCalls.map(tc => tc.name).join(', ')}`
      : 'No tools used'

    // Summarize tool outputs (truncated for token efficiency)
    const outputSection = result.tool_outputs?.length
      ? result.tool_outputs.map(to =>
          `${to.tool_name}${to.is_error ? ' [ERROR]' : ''}: ${to.output.slice(0, 300)}`
        ).join('\n')
      : ''

    // Agent's response (truncated — the dialectic doesn't need the full text)
    const responseSummary = result.response.slice(0, 1500)

    // Decision context
    const decisionStr = decision.action === 'complete'
      ? `complete — "${(decision as any).result?.slice(0, 200) ?? ''}"`
      : decision.action === 'blocked'
        ? `blocked — "${(decision as any).reason ?? ''}"`
        : decision.action === 'delegate'
          ? `delegate to ${(decision as any).delegateTo} — "${(decision as any).delegateTask?.slice(0, 200) ?? ''}"`
          : `continue${(decision as any).reason ? ` — "${(decision as any).reason}"` : ''}`

    return `[Autonomous agent ${agentId} — iteration ${iteration}/${state.opts.maxIterations}, ${budgetPct}% budget used]

Decision: ${decisionStr}
${toolSection}

${outputSection ? `## Tool Outputs\n${outputSection}\n` : ''}
## Agent Response
${responseSummary}`
  }


  /**
   * Apply agent-specific provider config to a session before the first iteration.
   * This bridges the gap between TeamOrchestrator's per-agent provider resolution
   * and the pipeline's session-based model lookup (`session.config.model`).
   */
  private configureSessionProvider(
    sessionId: string,
    provider: NonNullable<AutonomousLoopOpts['provider']>,
  ): void {
    if (!this.sessions) return

    // Get or pre-create the session so we can patch its config before the
    // pipeline's first `process()` call. We use getOrCreate with the autonomous
    // channel so the session exists with a stable ID.
    let session = this.sessions.get(sessionId)
    if (!session) {
      // Pre-create the session so the pipeline finds it with the correct config.
      // The pipeline uses getOrCreateById internally, but that path creates with
      // defaults. By creating here first, sessions.get() will return it.
      session = (this.sessions as any).getOrCreateById?.(sessionId, 'autonomous', 'autonomous-agent')
        ?? this.sessions.getOrCreate('autonomous', sessionId)
    }
    if (!session) {
      this.logger.warn('AutonomousLoop: could not obtain session for provider config', { sessionId })
      return
    }

    // Apply provider config to session
    const updates: Partial<SessionConfig> = {}
    if (provider.providerId && provider.model) {
      updates.model = `${provider.providerId}/${provider.model}`
    } else if (provider.model) {
      updates.model = provider.model
    }
    if (provider.providerId) {
      updates.providerId = provider.providerId
    }
    if (provider.model) {
      updates.providerModel = provider.model
    }
    if (provider.thinking) {
      updates.thinking = provider.thinking as SessionConfig['thinking']
    }

    Object.assign(session.config, updates)
    this.logger.debug('AutonomousLoop: configured session provider', {
      sessionId,
      model: session.config.model,
      providerId: session.config.providerId,
      thinking: session.config.thinking,
    })
  }

  private getMailboxMessages(sessionId: string): SessionMessage[] {
    if (!this.digestStore) return []
    try {
      return this.digestStore.readMailbox(sessionId) || []
    } catch {
      return []
    }
  }

  private async persistHistory(agentId: string, state: LoopState): Promise<void> {
    if (!this.memory) return
    try {
      await this.memory.kv_set(`autonomous:loop:${agentId}:history`, state.history)
    } catch (err) {
      this.logger.debug('AutonomousLoop: failed to persist history', { agentId, error: String(err) })
    }
  }

  private emitEvent(type: string, data: Record<string, unknown>): void {
    if (!this.eventBus) return
    try {
      (this.eventBus as any).emit?.({ type, ...data })
    } catch (err) {
      this.logger.debug('AutonomousLoop: failed to emit event', { type, error: String(err) })
    }
  }
}
