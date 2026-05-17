/**
 * ReverieModule — ambient in-flight memory curator.
 *
 * Wakeful counterpart to Meditation: cheap, frequent, runs while the
 * primary is still active. Curates Lamina blocks and promotes engrams.
 *
 * See project_reverie_design.md for the full architectural rationale.
 */

import { MODEL_DEFAULTS } from '../../config/system-settings.js'
import { BaseCognitiveModule } from '../base/cognitive-module.js'

import { buildReveriePrompt } from './prompt.js'
import { ReverieTriggerController } from './trigger.js'
import { ToolFilterRegistry, DEFAULT_TOOL_FILTER } from './tool-filter.js'
import {
  DEFAULT_REVERIE_CONFIG,
  type ReverieConfig,
  type ReverieDecision,
  type ReverieEdit,
  type ReverieRecord,
  type ReverieTrigger,
} from './types.js'

interface ToolRoundEntry {
  round: number
  toolCalls: Array<{ name: string; id: string }>
  results: Array<{ toolCallId: string; isError: boolean; contentPreview: string }>
  at: number
}

import type { ILogger } from '../../../types/interfaces.js'
import type { LaminaField } from '../lamina/index.js'
import type { MnemicField } from '../mnemic-field/index.js'
import type { Engram } from '../mnemic-field/types.js'
import type { AuditStore } from '../../runtime/audit/index.js'
import { withStep } from '../../runtime/audit/index.js'

let counter = 0
function rid(): string {
  return `rev_${Date.now().toString(36)}${(counter++).toString(36)}`
}

const DECISION_FALLBACK: ReverieDecision = { silence: true, edits: [], notes: ['parse-failed'] }

function safeParse(text: string): ReverieDecision {
  try {
    const obj = JSON.parse(text)
    if (typeof obj !== 'object' || obj == null) return DECISION_FALLBACK
    const edits: ReverieEdit[] = Array.isArray(obj.edits) ? obj.edits.filter((e: any) =>
      typeof e?.action === 'string' && typeof e?.content === 'string' && typeof e?.reason === 'string') : []
    return {
      silence: !!obj.silence,
      edits,
      notes: Array.isArray(obj.notes) ? obj.notes.map(String) : [],
    }
  } catch {
    return DECISION_FALLBACK
  }
}

export class ReverieModule extends BaseCognitiveModule {
  readonly name = 'reverie'
  readonly priority = 14

  private cfg: ReverieConfig = { ...DEFAULT_REVERIE_CONFIG }
  private trigger = new ReverieTriggerController(this.cfg)
  private filter: ToolFilterRegistry = DEFAULT_TOOL_FILTER
  private lamina?: LaminaField
  private audit?: AuditStore
  private mnemic?: MnemicField
  /** Recent decisions for /reverie/recent admin endpoint. */
  private recent: ReverieRecord[] = []
  /** Best-effort recent exchange tracker per session. */
  private exchanges = new Map<string, { lastUser?: string; lastAssistant?: string }>()
  /** Sliding window of recent tool rounds — what the primary actually did. */
  private toolRoundLog = new Map<string, ToolRoundEntry[]>()
  private summaryTimers = new Map<string, NodeJS.Timeout>()
  /** Max tool rounds to retain in the sliding window. Generous — input tokens are cheap. */
  private readonly maxToolRounds = 24
  /** Pending <note for="reverie"> messages from Thalamus thought-commands, per session. */
  private pendingNotes = new Map<string, Array<{ message: string; at: number }>>()
  /** Cap on buffered notes per session — drop oldest beyond this. */
  private readonly maxPendingNotes = 20
  /**
   * Trigger for Thalamus's background distillation queue. Set by the daemon
   * so Reverie owns the WHEN (turn-end) while Thalamus owns the HOW (queue +
   * storage). The design specifies Reverie as owner of stateful background
   * work; this is the minimal coupling that delivers that without moving
   * queue state across modules.
   */
  private distillationTrigger: ((sessionId: string) => void) | null = null

  constructor(logger: ILogger, config?: Partial<ReverieConfig>) {
    super(logger, {
      providerId: MODEL_DEFAULTS.background?.provider ?? MODEL_DEFAULTS.reasoning.provider,
      model: MODEL_DEFAULTS.background?.model ?? MODEL_DEFAULTS.reasoning.model,
    })
    this.cfg = { ...this.cfg, ...config }
    this.trigger.setConfig(this.cfg)
  }

  setLamina(lamina: LaminaField): void { this.lamina = lamina }
  setAudit(audit: AuditStore): void { this.audit = audit }
  setMnemicField(mnemic: MnemicField): void { this.mnemic = mnemic }
  setToolFilter(filter: ToolFilterRegistry): void { this.filter = filter }

  /**
   * Wire the distillation trigger callback. The daemon connects this to
   * Thalamus.queueBackgroundDistillations so Reverie's onTurnEnd hook can
   * fire the queue at a consistent point in the turn lifecycle.
   */
  setDistillationTrigger(fn: (sessionId: string) => void): void {
    this.distillationTrigger = fn
  }

  /**
   * Receive a <note for="reverie"> thought-command from Thalamus. Cassi uses
   * these to hint upcoming distillation goal-context, suppress false-positive
   * loop flags, or leave intent for the next ambient curation pass. The note
   * is buffered and consumed on the next runOnce.
   */
  receiveNote(sessionId: string, recipient: string, message: string): void {
    if (recipient !== 'reverie' && recipient !== '*') return
    const arr = this.pendingNotes.get(sessionId) ?? []
    arr.push({ message, at: Date.now() })
    this.pendingNotes.set(sessionId, arr.slice(-this.maxPendingNotes))
  }

  override async stop(): Promise<void> {
    for (const timer of this.summaryTimers.values()) clearTimeout(timer)
    this.summaryTimers.clear()
    await super.stop()
  }

  protected async onTurnStart(sessionId: string, message: string): Promise<void> {
    const e = this.exchanges.get(sessionId) ?? {}
    e.lastUser = message
    this.exchanges.set(sessionId, e)
    this.markSessionSummaryStale(sessionId, 'turn-start')
  }

  protected async onTurnEnd(sessionId: string, response: string): Promise<void> {
    const e = this.exchanges.get(sessionId) ?? {}
    e.lastAssistant = response
    this.exchanges.set(sessionId, e)
    // Fire the Thalamus distillation queue if wired. Non-blocking — the
    // queueBackgroundDistillations method spawns its own promise. We do
    // this BEFORE runOnce so distillation LLM calls can run in parallel
    // with Reverie's own ambient inference.
    if (this.distillationTrigger) {
      try { this.distillationTrigger(sessionId) } catch (err) {
        this.logger.debug('[reverie] distillation trigger threw', { error: String(err) })
      }
    }
    // Schedule a step credit for the primary's turn-end so Reverie can fire.
    const trig = this.trigger.recordStep(sessionId, 'primary')
    if (trig) await this.runOnce(sessionId, trig)
    this.scheduleSessionSummary(sessionId)
  }

  protected async onToolRound(
    sessionId: string,
    round: number,
    toolCalls: Array<{ name: string; id: string }>,
    results: Array<{ toolCallId: string; isError: boolean; contentPreview: string }>,
  ): Promise<void> {
    // Capture the tool round in the sliding window
    const log = this.toolRoundLog.get(sessionId) ?? []
    log.push({ round, toolCalls, results, at: Date.now() })
    if (log.length > this.maxToolRounds) log.shift()
    this.toolRoundLog.set(sessionId, log)

    const trig = this.trigger.recordStep(sessionId, 'primary')
    if (trig) await this.runOnce(sessionId, trig)
    this.markSessionSummaryStale(sessionId, 'tool-round')
    this.scheduleSessionSummary(sessionId)
  }

  /** Public hook — manual ping (e.g. from another module or admin endpoint). */
  ping(sessionId: string, reason: string): void {
    this.trigger.ping(sessionId, reason)
  }

  async summarizeSessionNow(sessionId: string): Promise<Engram | null> {
    if (!this.mnemic || !this.provider) return null
    const events = this.mnemic
      .replaySession(sessionId, { limit: this.cfg.summaryMaxEvents })
      .filter(e => e.kind !== 'session_summary')
    if (events.length === 0) return null

    const compactEvents = events.map(e => ({
      id: e.id,
      kind: e.kind,
      timestamp: e.timestamp,
      content: e.content.slice(0, 800),
      metadata: e.metadata,
    }))
    const prompt = [
      'Summarize this CassiCore replay event stream into a concise session summary.',
      'Return plain text only. Include goal, completed work, current state, blockers, and next actions when available.',
      JSON.stringify(compactEvents),
    ].join('\n\n')

    const summary = await this.infer([
      { role: 'system', content: 'You summarize CassiCore session replay events faithfully and concisely.' },
      { role: 'user', content: prompt },
    ], { maxTokens: 1200, temperature: 0.2 })

    const rootId = sessionId.startsWith('session:') ? sessionId : `session:${sessionId}`
    const summaryId = `session_summary:${rootId.slice('session:'.length)}`
    const existing = this.mnemic.get(summaryId)
    const content = JSON.stringify({ summary, eventCount: events.length, generatedAt: new Date().toISOString() })
    if (existing) {
      return this.mnemic.update(summaryId, {
        content,
        nodeType: 'abstraction',
        tags: ['session-replay', 'session-summary', 'reverie'],
        metadata: { sessionId: rootId, stale: false, generatedAt: Date.now(), eventCount: events.length },
      })
    }
    const engram = this.mnemic.store({
      id: summaryId,
      content,
      nodeType: 'abstraction',
      tags: ['session-replay', 'session-summary', 'reverie'],
      provenance: 'reverie',
      metadata: { sessionId: rootId, stale: false, generatedAt: Date.now(), eventCount: events.length },
    })
    if (this.mnemic.get(rootId)) this.mnemic.connect({ sourceId: summaryId, targetId: rootId, edgeType: 'part_of' })
    return engram
  }

  private scheduleSessionSummary(sessionId: string): void {
    if (!this.mnemic || !this.provider || this.cfg.summaryInactivityMs <= 0) return
    const existing = this.summaryTimers.get(sessionId)
    if (existing) clearTimeout(existing)
    const timer = setTimeout(() => {
      this.summaryTimers.delete(sessionId)
      this.summarizeSessionNow(sessionId).catch(err => {
        this.logger.warn('[reverie] session summary failed', { sessionId, error: String(err) })
      })
    }, this.cfg.summaryInactivityMs)
    timer.unref?.()
    this.summaryTimers.set(sessionId, timer)
  }

  private markSessionSummaryStale(sessionId: string, reason: string): void {
    if (!this.mnemic) return
    const summaryId = `session_summary:${sessionId.startsWith('session:') ? sessionId.slice('session:'.length) : sessionId}`
    const existing = this.mnemic.get(summaryId)
    if (!existing) return
    this.mnemic.update(summaryId, {
      metadata: { ...existing.metadata, stale: true, staleReason: reason, staleAt: Date.now() },
      tags: Array.from(new Set([...existing.tags, 'stale'])),
    })
  }

  /**
   * Public inference interface — allows external modules (like Aurora's
   * ReverieReasoningObserver) to use Reverie as an inference provider.
   * Implements ReverieInferenceProvider.
   *
   * NOTE: This shadows BaseCognitiveModule.infer() with a different signature.
   * We use a different method name to avoid the type conflict.
   */
  async inferForObserver(
    messages: Array<{ role: string; content: string }>,
    options: { maxTokens: number; temperature: number; signal?: AbortSignal },
  ): Promise<string> {
    if (!this.provider) {
      throw new Error('[reverie] No provider configured — cannot infer')
    }
    const ctrl = new AbortController()
    const timeout = options.signal
      ? undefined
      : setTimeout(() => ctrl.abort(), 15_000)
    const signal = options.signal ?? ctrl.signal

    // Cast messages to the Message type from runtime types — shape is compatible at runtime
    const castMessages = messages as import('../../../types/runtime.js').Message[]

    try {
      const result = await super.infer(castMessages, {
        maxTokens: options.maxTokens,
        temperature: options.temperature,
        signal,
      })
      if (timeout) clearTimeout(timeout)
      return result
    } catch (err) {
      if (timeout) clearTimeout(timeout)
      throw err
    }
  }

  /** Run a single Reverie cycle. Safe to call directly (manual trigger). */
  async runOnce(sessionId: string, trigger: ReverieTrigger): Promise<ReverieRecord> {
    const startedAt = new Date()
    const start = Date.now()
    if (!this.lamina) {
      const r: ReverieRecord = this.makeRecord(sessionId, trigger, DECISION_FALLBACK, 0, 0, 'failed', startedAt, null)
      this.appendRecent(r); return r
    }
    const sup = this.trigger.shouldSuppress(sessionId)
    if (sup.suppress) {
      const r: ReverieRecord = this.makeRecord(sessionId, trigger, { silence: true, edits: [], notes: [sup.reason ?? 'suppressed'] }, 0, 0, 'suppressed', startedAt, null)
      this.appendRecent(r)
      this.trigger.recordRun(sessionId, { tokens: 0, durationMs: 0, suppressed: true })
      return r
    }

    // Auto-detect loops before LLM call — cheap, no inference needed
    const autoLoop = this.detectAutoLoops(sessionId)
    if (autoLoop && this.lamina) {
      try {
        this.lamina.append('open-hypotheses',
          { content: `[auto-detect] ${autoLoop}`, reason: 'reverie-auto-loop' }, 'reverie')
      } catch { /* best-effort */ }
    }

    // Build prompt with sliding window of recent activity
    const laminae = this.lamina.list({ matchScope: { kind: 'session', sessionId }, limit: 30 })
    const ex = this.exchanges.get(sessionId) ?? {}
    const recentExchange = `User: ${ex.lastUser ?? '(n/a)'}
Assistant: ${ex.lastAssistant ?? '(n/a)'}`
    const toolRounds = this.toolRoundLog.get(sessionId) ?? []
    const cassiNotes = (this.pendingNotes.get(sessionId) ?? []).map(n => n.message)
    if (cassiNotes.length > 0) this.pendingNotes.delete(sessionId)
    const prompt = buildReveriePrompt({
      sessionId,
      triggerReason: trigger.reason,
      laminae,
      recentSignals: autoLoop ? [autoLoop] : [],
      recentExchange,
      recentToolRounds: toolRounds,
      budgetTokensRemaining: this.cfg.sessionTokenBudget,
      cassiNotes,
    })

    let raw = ''
    try {
      const ctrl = new AbortController()
      const timeout = setTimeout(() => ctrl.abort(), 15_000)
      raw = await this.infer([
        { role: 'system', content: prompt.system },
        { role: 'user', content: prompt.user },
      ], { maxTokens: 2048, temperature: 0.3, signal: ctrl.signal })
      clearTimeout(timeout)
    } catch (err) {
      this.logger.warn(`[reverie] inference failed`, { error: String(err) })
      const r = this.makeRecord(sessionId, trigger, DECISION_FALLBACK, Date.now() - start, 0, 'failed', startedAt, null)
      this.appendRecent(r)
      this.trigger.recordRun(sessionId, { tokens: 0, durationMs: Date.now() - start, suppressed: false })
      return r
    }

    const decision = safeParse(raw)
    const tokensApprox = Math.ceil((prompt.system.length + prompt.user.length + raw.length) / 4)

    // Apply edits within an audit step
    let provenance = null
    if (!decision.silence && decision.edits.length > 0 && this.audit) {
      const run = this.audit.startRun({ kind: 'reverie', agentId: 'reverie', sessionId, goal: trigger.reason })
      const step = this.audit.startStep({ runId: run.id, slot: 'reverie', reason: trigger.kind })
      provenance = { runId: run.id, stepId: step.id, agentId: 'reverie', reason: trigger.reason }
      try {
        withStep(provenance, () => this.applyEdits(sessionId, decision.edits))
      } finally {
        this.audit.finishStep(step.id, { status: 'completed', toolCallCount: decision.edits.length })
        this.audit.finishRun(run.id, 'completed')
      }
    }

    const durationMs = Date.now() - start
    this.trigger.recordRun(sessionId, { tokens: tokensApprox, durationMs, suppressed: false })
    const record = this.makeRecord(sessionId, trigger, decision, durationMs, tokensApprox, 'completed', startedAt, provenance)
    this.appendRecent(record)
    return record
  }

  private applyEdits(sessionId: string, edits: ReverieEdit[]): void {
    if (!this.lamina) return
    for (const edit of edits) {
      try {
        if (edit.action === 'note') continue
        if (edit.action === 'task-tree.rethink') {
          // Rethink active-task as a structured task tree
          const denial = this.filter.checkLamina('reverie', 'rethink', 'active-task')
          if (denial) { this.logger.info('[reverie] task-tree rethink denied', { denial }); continue }
          this.lamina.rethink('active-task', { content: edit.content, reason: edit.reason }, 'reverie')
          continue
        }
        if (edit.action === 'contradiction.flag') {
          // Append contradiction note to session-decisions
          this.lamina.append('session-decisions',
            { content: `[contradiction] ${edit.content}`, reason: edit.reason }, 'reverie')
          continue
        }
        if (edit.action === 'mnemic.label_retrieval') {
          if (!this.mnemic || !edit.labels || edit.labels.length === 0) continue
          const persisted = this.mnemic.recordIndexerTrainingRequests(edit.labels)
          this.logger.info?.('[reverie] retrieval labels persisted', {
            count: persisted,
            sessionId,
          })
          continue
        }
        if (edit.action === 'loop.detect') {
          // Append loop detection to open-hypotheses
          this.lamina.append('open-hypotheses',
            { content: `[loop] ${edit.content}`, reason: edit.reason }, 'reverie')
          continue
        }
        if (edit.action.startsWith('lamina.') && edit.label) {
          const denial = this.filter.checkLamina('reverie', edit.action.split('.')[1] as any, edit.label)
          if (denial) { this.logger.info('[reverie] edit denied by tool-filter', { denial, label: edit.label }); continue }
          if (edit.action === 'lamina.append') {
            this.lamina.append(edit.label, { content: edit.content, reason: edit.reason }, 'reverie',
              { kind: 'session', sessionId })
          } else if (edit.action === 'lamina.replace') {
            // Best-effort: re-read for current hash if model didn't supply one
            const current = this.lamina.read(edit.label, { kind: 'session', sessionId }) ?? this.lamina.read(edit.label)
            const expected = edit.expectedHash ?? current?.contentHash ?? null
            this.lamina.replace(edit.label, { expectedHash: expected, content: edit.content, reason: edit.reason }, 'reverie',
              current?.scope ?? { kind: 'global' })
          } else if (edit.action === 'lamina.rethink') {
            this.lamina.rethink(edit.label, { content: edit.content, reason: edit.reason }, 'reverie',
              { kind: 'session', sessionId })
          }
        } else if (edit.action === 'mnemic.promote') {
          // Best-effort: emit an event the memory module can subscribe to
          this.eventBus?.emit({
            type: 'reverie:promote' as any,
            sessionId,
            engramId: edit.engramId,
            reason: edit.reason,
            timestamp: new Date(),
          } as any)
        }
      } catch (err) {
        this.logger.warn?.('[reverie] edit failed — silently dropped', { error: String(err), edit: { action: edit.action, label: edit.label } })
      }
    }
  }

  /** Automatic loop detection — cheap, runs without LLM. */
  private detectAutoLoops(sessionId: string): string | null {
    const log = this.toolRoundLog.get(sessionId) ?? []
    if (log.length < 3) return null

    // Count errors per tool
    const errorCounts = new Map<string, number>()
    for (const tr of log) {
      if (!Array.isArray(tr.results)) continue
      for (const r of tr.results) {
        if (r.isError) {
          const toolCalls = Array.isArray(tr.toolCalls) ? tr.toolCalls : []
          const key = `${toolCalls.find(tc => tc.id === r.toolCallId)?.name ?? 'unknown'}:${r.contentPreview.slice(0, 60)}`
          errorCounts.set(key, (errorCounts.get(key) ?? 0) + 1)
        }
      }
    }
    for (const [key, count] of errorCounts) {
      if (count >= 3) return `Same error repeated ${count} times: ${key}`
    }

    // Detect circular file edits (file A read → file A written → file A read again)
    const fileOps: Array<{ file: string; op: 'read' | 'write' }> = []
    for (const tr of log) {
      const results = Array.isArray(tr.results) ? tr.results : []
      const toolCalls = Array.isArray(tr.toolCalls) ? tr.toolCalls : []
      for (const tc of toolCalls) {
        if (tc.name === 'read' || tc.name === 'cassi_read') {
          const m = results.find(r => r.toolCallId === tc.id)?.contentPreview.match(/path["']?\s*:\s*["']([^"']+)/)
          if (m) fileOps.push({ file: m[1], op: 'read' })
        }
        if (tc.name === 'write' || tc.name === 'cassi_write') {
          const m = results.find(r => r.toolCallId === tc.id)?.contentPreview.match(/path["']?\s*:\s*["']([^"']+)/)
          if (m) fileOps.push({ file: m[1], op: 'write' })
        }
      }
    }
    // Look for read-write-read pattern on same file
    for (let i = 0; i < fileOps.length - 2; i++) {
      if (fileOps[i].op === 'read' && fileOps[i + 1].op === 'write' && fileOps[i + 2].op === 'read' &&
          fileOps[i].file === fileOps[i + 2].file) {
        return `Circular edit pattern on ${fileOps[i].file}: read → write → re-read without forward progress`
      }
    }

    return null
  }

  private makeRecord(
    sessionId: string,
    trigger: ReverieTrigger,
    decision: ReverieDecision,
    durationMs: number,
    budgetTokens: number,
    status: ReverieRecord['status'],
    startedAt: Date,
    provenance: ReverieRecord['provenance'],
  ): ReverieRecord {
    return {
      id: rid(),
      sessionId,
      trigger,
      decision,
      durationMs,
      budgetTokens,
      startedAt: startedAt.toISOString(),
      finishedAt: new Date().toISOString(),
      status,
      provenance,
    }
  }

  private appendRecent(record: ReverieRecord): void {
    this.recent.push(record)
    if (this.recent.length > 50) this.recent.splice(0, this.recent.length - 50)
  }

  // Diagnostics
  getRecent(limit = 20): ReverieRecord[] {
    return this.recent.slice(-limit).reverse()
  }

  reverieMetrics() {
    const total = this.recent.length
    const silent = this.recent.filter(r => r.decision.silence).length
    const suppressed = this.recent.filter(r => r.status === 'suppressed').length
    const useful = this.recent.filter(r => !r.decision.silence && r.decision.edits.length > 0).length
    return {
      invocations: total,
      silenceRatio: total === 0 ? 0 : silent / total,
      suppressedRatio: total === 0 ? 0 : suppressed / total,
      editsUsefulRatio: total === 0 ? 0 : useful / total,
    }
  }
}

export type { ReverieConfig, ReverieRecord, ReverieDecision, ReverieEdit, ReverieTrigger } from './types.js'
export { ToolFilterRegistry, DEFAULT_TOOL_FILTER } from './tool-filter.js'
