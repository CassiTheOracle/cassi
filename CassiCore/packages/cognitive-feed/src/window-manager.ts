import type { ILogger } from '../../../types/interfaces.js'
import type { MessageFormatter } from './message-formatter.js'
import { fmtDuration as fmtDur, fmtTokens as fmtTok } from './message-formatter.js'
import type { RateLimiter } from './rate-limiter.js'
import type { TelegramClient } from './telegram-client.js'
import type { CuratedEvent } from './event-curator.js'
import * as fs from 'node:fs'
import * as path from 'node:path'

export interface BranchState {
  helixId: string
  goal: string
  status: 'active' | 'completed' | 'degraded' | 'failed'
  depth?: number
  score?: number
  steps?: number
  annotation?: string
  pattern?: string
  strategy?: string
  tokensUsed?: number
  tokensUnity?: number
  tokensYang?: number
  tokensYin?: number
  tokensMentor?: number
  modelUnity?: string
  modelProviderUnity?: string
  modelYang?: string
  modelProviderYang?: string
  modelYin?: string
  modelProviderYin?: string
  tierUnity?: string
  tierYang?: string
  tierYin?: string
  liveStreamSnippet?: string
  blockers?: string[]
  confidence?: number
  confidenceTrend?: string
  workUnits?: number
  iterations?: number
  durationMs?: number
  postureStatuses?: { energy: string; status: string; toolCalls?: number }[]
  brainstemAnnotations?: { type: string; score: number; description: string }[]
  recentOutputs?: string[]
  discoveries?: number
  directives?: number
  escalations?: number
  sweepCount?: number
  stagnationLevel?: number
  forceKillAt?: number
  unityConclusion?: string
  filesModified?: string[]
}

export interface ConstellationState {
  id: string
  goal: string
  template: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  durationMs: number
  totalTokens: number
  totalBranches: number
  completedBranches: number
  failedBranches: number
  outcome?: string
  outcomeReason?: string
  error?: string
  branches: Map<string, BranchState>
  sweepCount?: number
  stagnationLevel?: number
  errors?: string[]
  firstSeenAt: number
}

export interface HelixState {
  helixId: string
  goal: string
  constellationId?: string
  status: 'active' | 'completed' | 'failed' | 'degraded'
  iterations?: number
  durationMs?: number
  tokensUsed?: number
  tokensUnity?: number
  tokensYang?: number
  tokensYin?: number
  tokensMentor?: number
  score?: number
  confidence?: number
  confidenceTrend?: string
  strategy?: string
  inProgress?: boolean
  progress?: number
  liveStreamSnippet?: string
  unityConclusion?: string
  filesModified?: string[]
  blockers?: string[]
  postureStatuses?: { energy: string; status: string; tier?: string; model?: string; provider?: string; toolCalls?: number }[]
  brainstemAnnotations?: { type: string; score: number; description: string }[]
  recentOutputs?: string[]
  workUnits?: number
}

export interface ActivityEntry {
  timestamp: number
  icon: string
  title: string
  description: string
  details: string[]
  constellationId?: string
  helixId?: string
}

export interface CorpusEntry {
  timestamp: number
  icon: string
  type: string
  title: string
  details: string[]
  constellationId?: string
}

export interface WindowManagerConfig {
  formatter: MessageFormatter
  rateLimiter: RateLimiter
  client: TelegramClient
  chatId: number
  logger: ILogger
  persistencePath?: string
}

const WINDOW_INTERVALS = {
  dashboard: 30_000,
  activity: 3_000,
  helix: 5_000,
  corpus: 3_000,
}

export class WindowManager {
  private constellations = new Map<string, ConstellationState>()
  private helixes = new Map<string, HelixState>()
  private activityLog: ActivityEntry[] = []
  private corpusLog: CorpusEntry[] = []

  private dirty: Record<string, boolean> = { dashboard: false, activity: false, helix: false, corpus: false }
  private lastFlush: Record<string, number> = { dashboard: 0, activity: 0, helix: 0, corpus: 0 }
  private lastRendered: Record<string, string> = {}
  private messageIds: Record<string, number | undefined> = {}

  private formatter: MessageFormatter
  private rateLimiter: RateLimiter
  private client: TelegramClient
  private chatId: number
  private logger: ILogger
  private persistencePath: string
  private initPromise: Promise<void> | null = null

  constructor(config: WindowManagerConfig) {
    this.formatter = config.formatter
    this.rateLimiter = config.rateLimiter
    this.client = config.client
    this.chatId = config.chatId
    this.logger = config.logger
    this.persistencePath = config.persistencePath ?? path.join(process.env.HOME ?? '/tmp', '.cassicore', 'data', 'cognitive-feed-windows.json')
  }

  async init(): Promise<void> {
    if (this.initPromise) return this.initPromise
    this.initPromise = this.initializeWindows()
    return this.initPromise
  }

  private async initializeWindows(): Promise<void> {
    this.restore()
    for (const id of ['dashboard', 'activity', 'helix', 'corpus'] as const) {
      const msgId = this.messageIds[id]
      if (msgId) {
        try {
          await this.client.editMessage(this.chatId, msgId, `⏳ Rebooting ${id} window...`)
          this.logger.info('[window-manager] Restored window message', { id, msgId })
        } catch {
          this.logger.info('[window-manager] Window message lost, will create new', { id })
          this.messageIds[id] = undefined
        }
      }
    }
    const missing = Object.entries(this.messageIds).filter(([, v]) => !v).map(([k]) => k)
    if (missing.length > 0) {
      await this.createWindows(missing)
    }
  }

  private async createWindows(ids: string[]): Promise<void> {
    for (const id of ids) {
      let text = ''
      switch (id) {
        case 'dashboard': text = '📊 Constellation Dashboard\n\nNo active constellations yet. Waiting for activity...'; break
        case 'activity': text = '📌 Activity Timeline\n\nWaiting for events...'; break
        case 'helix': text = '🔬 Helix Activity\n\nWaiting for branches...'; break
        case 'corpus': text = '🎯 Corpus Coordination\n\nWaiting for decisions...'; break
      }
      try {
        const msgId = await this.client.sendMessage(this.chatId, text)
        if (msgId) {
          this.messageIds[id] = msgId
          this.logger.info('[window-manager] Created window message', { id, msgId })
        }
      } catch (err) {
        this.logger.warn('[window-manager] Failed to create window', { id, error: String(err) })
      }
    }
    this.persist()
  }

  accept(curated: CuratedEvent): void {
    const { event } = curated
    const e = event as any
    const type = event.type as string

    this.updateConstellationState(type, e)
    this.updateHelixState(type, e)
    this.addActivityEntry(type, e)
    this.addCorpusEntry(type, e)
  }

  private updateConstellationState(type: string, e: any): void {
    const cid = e.constellationId

    if (type === 'constellation:started' && cid) {
      this.constellations.set(cid, {
        id: cid,
        goal: e.goal ?? '',
        template: e.template ?? 'standard',
        status: 'running',
        durationMs: 0,
        totalTokens: 0,
        totalBranches: e.maxHelixes ?? 1,
        completedBranches: 0,
        failedBranches: 0,
        branches: new Map(),
        firstSeenAt: Date.now(),
      })
      this.dirty.dashboard = true
      return
    }

    const c = cid ? this.constellations.get(cid) : undefined
    if (!c) return

    if (type === 'constellation:completed') {
      c.status = 'completed'
      c.outcome = e.outcome
      c.outcomeReason = e.outcomeReason
      c.durationMs = e.durationMs ?? c.durationMs
      c.totalTokens = e.totalTokens ?? c.totalTokens
      c.completedBranches = e.completedBranches ?? c.completedBranches
      c.failedBranches = e.failedBranches ?? c.failedBranches
      this.dirty.dashboard = true
    }

    if (type === 'constellation:failed') {
      c.status = 'failed'
      c.error = e.error
      c.durationMs = e.durationMs ?? c.durationMs
      this.dirty.dashboard = true
    }

    if (type === 'constellation:cancelled') {
      c.status = 'cancelled'
      c.error = e.reason
      c.durationMs = e.durationMs ?? c.durationMs
      this.dirty.dashboard = true
    }

    if (type === 'constellation:checkpoint') {
      c.totalTokens = e.tokensUsed ?? c.totalTokens
      c.sweepCount = e.sweepCount ?? c.sweepCount
      c.completedBranches = e.completedBranches ?? c.completedBranches
      c.failedBranches = e.failedBranches ?? c.failedBranches
      c.totalBranches = e.totalBranches ?? c.totalBranches
      c.durationMs = e.durationMs ?? c.durationMs
      this.dirty.dashboard = true
    }

    if (type === 'constellation:stagnation') {
      c.stagnationLevel = e.level
      this.dirty.dashboard = true
    }

    if (type === 'constellation:branch:created' && e.helixId) {
      if (!c.branches.has(e.helixId)) {
        c.branches.set(e.helixId, {
          helixId: e.helixId,
          goal: e.goal ?? '',
          status: 'active',
          depth: e.depth,
        })
      }
      this.dirty.dashboard = true
    }

    if (type === 'constellation:branch:launched' && e.helixId) {
      let b = c.branches.get(e.helixId)
      if (!b) {
        b = { helixId: e.helixId, goal: '', status: 'active' }
        c.branches.set(e.helixId, b)
      }
      const launchPostures: any[] = e.postures ?? []
      for (const p of launchPostures) {
        switch (p.energy) {
          case 'unity': b.tierUnity = p.tier; b.modelUnity = p.model; b.modelProviderUnity = p.provider; break
          case 'yang': b.tierYang = p.tier; b.modelYang = p.model; b.modelProviderYang = p.provider; break
          case 'yin': b.tierYin = p.tier; b.modelYin = p.model; b.modelProviderYin = p.provider; break
        }
      }
      this.dirty.dashboard = true
      this.dirty.helix = true
    }

    if (type === 'constellation:branch:completed' && e.helixId) {
      const b = c.branches.get(e.helixId)
      if (b) {
        b.status = 'completed'
        b.tokensUsed = e.tokensUsed ?? b.tokensUsed
        b.tokensUnity = (e.tokensByPosture as any)?.unity ?? b.tokensUnity
        b.tokensYang = (e.tokensByPosture as any)?.yang ?? b.tokensYang
        b.tokensYin = (e.tokensByPosture as any)?.yin ?? b.tokensYin
        b.tokensMentor = (e.tokensByPosture as any)?.mentor ?? b.tokensMentor
        b.durationMs = e.durationMs ?? b.durationMs
        b.unityConclusion = e.unityConclusion
        b.score = e.score ?? b.score
      }
      this.dirty.dashboard = true
    }

    if (type === 'constellation:branch:degraded' && e.helixId) {
      const b = c.branches.get(e.helixId)
      if (b) {
        b.status = 'degraded'
        b.tokensUsed = e.tokensUsed ?? b.tokensUsed
        b.durationMs = e.durationMs ?? b.durationMs
      }
      this.dirty.dashboard = true
    }

    if (type === 'constellation:branch:failed' && e.helixId) {
      const b = c.branches.get(e.helixId)
      if (b) {
        b.status = 'failed'
        b.tokensUsed = e.partialTokens ?? b.tokensUsed
        b.durationMs = e.durationMs ?? b.durationMs
      }
      this.dirty.dashboard = true
    }
  }

  private updateHelixState(type: string, e: any): void {
    const hid = e.helixId ?? e.sessionId
    if (!hid) return

    if (type === 'helix:started') {
      this.helixes.set(hid, {
        helixId: hid,
        goal: e.goal ?? '',
        constellationId: e.constellationId,
        status: 'active',
        iterations: 0,
        postureStatuses: [],
        brainstemAnnotations: [],
      })
      this.dirty.helix = true
      return
    }

    const h = this.helixes.get(hid)
    if (!h) return

    if (type === 'helix:completed') {
      h.status = 'completed'
      h.durationMs = e.durationMs ?? h.durationMs
      h.tokensUsed = (e.tokensUsed as any)?.unity ?? 0
      h.tokensUnity = (e.tokensUsed as any)?.unity ?? 0
      h.tokensYang = (e.tokensUsed as any)?.yang ?? 0
      h.tokensYin = (e.tokensUsed as any)?.yin ?? 0
      h.tokensMentor = (e.tokensUsed as any)?.mentor ?? 0
      h.unityConclusion = e.unityConclusion
      this.dirty.helix = true
    }

    if (type === 'helix:failed') {
      h.status = 'failed'
      h.durationMs = e.durationMs ?? h.durationMs
      this.dirty.helix = true
    }

    if (type === 'helix:iteration:complete') {
      h.iterations = e.iteration ?? (h.iterations ?? 0) + 1
      this.dirty.helix = true
    }

    if (type === 'constellation:branch:launched' && hid) {
      h.postureStatuses = (e.postures as any[])?.map((p: any) => ({
        energy: p.energy,
        status: 'active',
        tier: p.tier,
        model: p.model,
        provider: p.provider,
      }))
      h.goal = e.goal ?? h.goal
      h.constellationId = e.constellationId ?? h.constellationId
      this.dirty.helix = true
    }

    if (type === 'constellation:branch:completed') {
      h.status = 'completed'
      h.durationMs = e.durationMs ?? h.durationMs
      h.tokensUsed = e.tokensUsed ?? h.tokensUsed
      h.tokensUnity = (e.tokensByPosture as any)?.unity ?? h.tokensUnity
      h.tokensYang = (e.tokensByPosture as any)?.yang ?? h.tokensYang
      h.tokensYin = (e.tokensByPosture as any)?.yin ?? h.tokensYin
      h.unityConclusion = e.unityConclusion
      h.score = e.score ?? h.score
      h.filesModified = e.filesModified
      this.dirty.helix = true
    }

    if (type === 'brainstem:annotation') {
      h.brainstemAnnotations = h.brainstemAnnotations ?? []
      h.brainstemAnnotations.push({
        type: e.annotationType ?? 'observation',
        score: e.score ?? 0.5,
        description: e.description ?? '',
      })
      if (h.brainstemAnnotations.length > 5) h.brainstemAnnotations = h.brainstemAnnotations.slice(-5)
      h.score = e.score ?? h.score
      this.dirty.helix = true
    }

    if (type === 'helix:synapse:broadcast') {
      h.liveStreamSnippet = (e.preview ?? '').slice(0, 200)
      this.dirty.helix = true
    }
  }

  private addActivityEntry(type: string, e: any): void {
    const entry = this.buildActivityEntry(type, e)
    if (!entry) return

    this.activityLog.unshift(entry)
    if (this.activityLog.length > 15) this.activityLog.pop()
    this.dirty.activity = true
  }

  private buildActivityEntry(type: string, e: any): ActivityEntry | null {
    const ts = Date.now()
    const cid = e.constellationId
    const hid = e.helixId ?? e.sessionId

    if (type === 'constellation:started') {
      return { timestamp: ts, icon: '🌌', title: 'Constellation started', description: (e.goal ?? '').slice(0, 150), details: [`Template: ${e.template ?? 'standard'}`, `Max branches: ${e.maxHelixes ?? 1}`], constellationId: cid }
    }
    if (type === 'constellation:completed') {
      const icon = e.outcome === 'success' ? '✅' : e.outcome === 'degraded' ? '⚠️' : '❌'
      const d = e.durationMs ? `in ${fmtDur(e.durationMs)}` : ''
      return { timestamp: ts, icon, title: `Constellation ${e.outcome ?? 'completed'} ${d}`, description: e.outcomeReason ?? '', details: [`${e.totalTokens ? fmtTok(e.totalTokens) : '?'} tokens`, `Branches: ${e.completedBranches ?? 0}/${e.totalBranches ?? 0}`], constellationId: cid }
    }
    if (type === 'constellation:failed') {
      return { timestamp: ts, icon: '❌', title: 'Constellation failed', description: (e.error ?? '').slice(0, 150), details: [], constellationId: cid }
    }
    if (type === 'constellation:branch:completed') {
      const d = e.durationMs ? `in ${fmtDur(e.durationMs)}` : ''
      const tp = e.tokensByPosture ? `U:${fmtTok(((e.tokensByPosture as any).unity ?? 0))} Y:${fmtTok(((e.tokensByPosture as any).yang ?? 0))} I:${fmtTok(((e.tokensByPosture as any).yin ?? 0))}` : ''
      return { timestamp: ts, icon: '✅', title: `Branch completed ${d}`, description: `Helix: ${hid ?? '?'}`, details: [tp, `${fmtTok(e.tokensUsed)} total`].filter(Boolean), constellationId: cid, helixId: hid }
    }
    if (type === 'constellation:branch:degraded') {
      return { timestamp: ts, icon: '⚠️', title: 'Branch degraded', description: `Helix: ${hid ?? '?'}`, details: [`${fmtDur(e.durationMs)}`], constellationId: cid, helixId: hid }
    }
    if (type === 'constellation:branch:failed') {
      return { timestamp: ts, icon: '❌', title: 'Branch failed', description: `Helix: ${hid ?? '?'}`, details: [(e.error ?? '').slice(0, 200)], constellationId: cid, helixId: hid }
    }
    if (type === 'constellation:stagnation') {
      return { timestamp: ts, icon: '⚠️', title: `Stagnation level ${e.level}`, description: `${e.activeBranches ?? '?'} branches flat, ${fmtTok(e.tokensUsed)} tokens`, details: [`${fmtDur(e.durationMs)} elapsed`], constellationId: cid }
    }
    if (type === 'helix:completed') {
      return { timestamp: ts, icon: '🔬', title: 'Helix completed', description: (e.unityConclusion ?? '').slice(0, 150), details: [`${fmtDur(e.durationMs)}`], constellationId: e.constellationId, helixId: hid }
    }
    if (type === 'corpus:intervention') {
      return { timestamp: ts, icon: '🎯', title: `Corpus → ${e.targetHelixId ?? '?'}  ${e.directiveType ?? '?'}`, description: (e.reason ?? '').slice(0, 150), details: [`Urgency: ${e.urgency ?? '?'}`], constellationId: cid }
    }
    if (type === 'corpus:spawn-decision') {
      const icon = e.approved ? '✅' : '❌'
      return { timestamp: ts, icon, title: `Spawn ${e.approved ? 'approved' : 'rejected'}`, description: (e.reason ?? '').slice(0, 150), details: [`Request: ${e.requestId ?? '?'}`], constellationId: cid }
    }
    if (type === 'corpus:discovery') {
      return { timestamp: ts, icon: '💡', title: `Discovery #${e.discoveryId ?? '?'}`, description: (e.content ?? '').slice(0, 150), details: [`Source: ${e.sourceHelixId ?? '?'}`, `Type: ${e.type ?? '?'}`], constellationId: cid }
    }
    if (type === 'corpus:synthesis') {
      return { timestamp: ts, icon: '📝', title: 'Cross-branch synthesis', description: (e.synthesis ?? '').slice(0, 150), details: [`Confidence: ${e.confidence ?? '?'}`], constellationId: cid }
    }
    if (type === 'corpus:escalation') {
      return { timestamp: ts, icon: '🚨', title: 'Escalation', description: (e.reason ?? '').slice(0, 150), details: [`Level: ${e.escalationLevel ?? '?'}`], constellationId: cid }
    }
    if (type === 'corpus:redecomposition') {
      return { timestamp: ts, icon: '🔄', title: 'Redecomposition', description: (e.reason ?? '').slice(0, 150), details: [`Original: ${(e.originalGoal ?? '').slice(0, 80)}`], constellationId: cid }
    }
    if (type === 'corpus:external-assumed') {
      return { timestamp: ts, icon: '🤖', title: 'External agent assumed control', description: `Agent: ${e.agentId ?? '?'}`, details: [], constellationId: cid }
    }
    if (type === 'corpus:external-released') {
      return { timestamp: ts, icon: '🤖', title: 'External control released', description: (e.reason ?? '').slice(0, 150), details: [], constellationId: cid }
    }
    if (type === 'corpus:external-directive') {
      return { timestamp: ts, icon: '🤖', title: `External directive: ${e.directiveType ?? '?'}`, description: (e.content ?? '').slice(0, 150), details: [`Urgency: ${e.urgency ?? '?'}`], constellationId: cid }
    }
    if (type === 'corpus:pattern') {
      return { timestamp: ts, icon: '🔍', title: `Pattern: ${e.patternType ?? '?'} [${e.severity ?? '?'}]`, description: (e.description ?? '').slice(0, 150), details: [`Affected: ${(e.affectedHelixes ?? []).join(', ')}`], constellationId: cid }
    }

    return null
  }

  private addCorpusEntry(type: string, e: any): void {
    const entry = this.buildCorpusEntry(type, e)
    if (!entry) return

    this.corpusLog.unshift(entry)
    if (this.corpusLog.length > 10) this.corpusLog.pop()
    this.dirty.corpus = true
  }

  private buildCorpusEntry(type: string, e: any): CorpusEntry | null {
    const ts = Date.now()
    const cid = e.constellationId

    if (type === 'corpus:intervention') {
      return { timestamp: ts, icon: '🎯', type: 'intervention', title: `Corpus → ${e.targetHelixId ?? '?'}  ${e.directiveType ?? '?'} (${e.urgency ?? '?'})`, details: [`Reason: ${(e.reason ?? '').slice(0, 300)}`, `Sweep: #${e.sweepCount ?? '?'}`.trim()].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:spawn-decision') {
      const icon = e.approved ? '✅' : '❌'
      return { timestamp: ts, icon, type: 'spawn-decision', title: `Spawn ${e.approved ? 'approved' : 'rejected'}`, details: [`Request: ${e.requestId ?? '?'}`, `Reason: ${(e.reason ?? '').slice(0, 300)}`, e.modifiedGoal ? `Modified: ${(e.modifiedGoal ?? '').slice(0, 200)}` : ''].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:auto-spawn') {
      return { timestamp: ts, icon: '🔄', type: 'auto-spawn', title: `Auto-spawn: ${e.helixId ?? '?'}`, details: [`Goal: ${(e.goal ?? '').slice(0, 200)}`, `Reason: ${(e.reason ?? '').slice(0, 200)}`].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:discovery') {
      return { timestamp: ts, icon: '💡', type: 'discovery', title: `Discovery #${e.discoveryId ?? '?'}`, details: [`Source: ${e.sourceHelixId ?? '?'}`, `Type: ${e.type ?? '?'}`, `Content: ${(e.content ?? '').slice(0, 300)}`].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:pattern') {
      return { timestamp: ts, icon: '🔍', type: 'pattern', title: `Pattern: ${e.patternType ?? '?'} [${e.severity ?? '?'}]`, details: [`Affected: ${(e.affectedHelixes ?? []).join(', ')}`, (e.description ?? '').slice(0, 300)].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:synthesis') {
      return { timestamp: ts, icon: '📝', type: 'synthesis', title: `Cross-branch synthesis`, details: [`Confidence: ${e.confidence ?? '?'}`, (e.synthesis ?? '').slice(0, 300)].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:escalation') {
      return { timestamp: ts, icon: '🚨', type: 'escalation', title: `Escalation: ${e.helixId ?? '?'}`, details: [`Level: ${e.escalationLevel ?? '?'}`, (e.reason ?? '').slice(0, 300)].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:redecomposition') {
      return { timestamp: ts, icon: '🔄', type: 'redecomposition', title: 'Redecomposition', details: [`Reason: ${(e.reason ?? '').slice(0, 200)}`, `New strategies: ${e.newGoals?.length ?? 0}`].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:degraded') {
      return { timestamp: ts, icon: '⚠️', type: 'health', title: 'Corpus degraded', details: [`Reason: ${(e.reason ?? '').slice(0, 200)}`], constellationId: cid }
    }
    if (type === 'corpus:unhealthy') {
      return { timestamp: ts, icon: '🔴', type: 'health', title: 'Corpus unhealthy', details: [`Reason: ${(e.reason ?? '').slice(0, 200)}`], constellationId: cid }
    }
    if (type === 'corpus:healthy') {
      return { timestamp: ts, icon: '🟢', type: 'health', title: 'Corpus recovered', details: [`Previous: ${e.previousState ?? '?'}`], constellationId: cid }
    }
    if (type === 'corpus:parallel-split') {
      return { timestamp: ts, icon: '🔀', type: 'split', title: `Parallel split: ${e.parentHelixId ?? '?'}`, details: [`Children: ${(e.childHelixIds ?? []).join(', ')}`, (e.goals ?? []).map((g: string) => g.slice(0, 100)).join(', ')].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:external-assumed') {
      return { timestamp: ts, icon: '🤖', type: 'external', title: `External assumed: ${e.agentId ?? '?'}`, details: [], constellationId: cid }
    }
    if (type === 'corpus:external-released') {
      return { timestamp: ts, icon: '🤖', type: 'external', title: 'External released', details: [(e.reason ?? '').slice(0, 200)], constellationId: cid }
    }
    if (type === 'corpus:external-directive') {
      return { timestamp: ts, icon: '🤖', type: 'external', title: `External directive: ${e.directiveType ?? '?'}`, details: [`Urgency: ${e.urgency ?? '?'}`, (e.content ?? '').slice(0, 300)].filter(Boolean), constellationId: cid }
    }
    if (type === 'corpus:external-spawn-decision') {
      return { timestamp: ts, icon: '🤖', type: 'external', title: `External spawn ${e.approved ? 'approved' : 'rejected'}`, details: [`Request: ${e.requestId ?? '?'}`, (e.reason ?? '').slice(0, 200)].filter(Boolean), constellationId: cid }
    }

    return null
  }

  async flush(): Promise<void> {
    await this.init()
    const now = Date.now()

    if (this.dirty.dashboard && now - this.lastFlush.dashboard >= WINDOW_INTERVALS.dashboard) {
      let text = this.formatter.formatDashboard(this.constellations)
      if (text.length > 4096) text = text.slice(0, 4000) + '\n\n...truncated'
      this.dirty.dashboard = false
      this.lastFlush.dashboard = now
      await this.createOrEdit('dashboard', text)
    }

    if (this.dirty.activity && now - this.lastFlush.activity >= WINDOW_INTERVALS.activity) {
      let text = this.formatter.formatActivity(this.activityLog)
      if (text.length > 4096) text = text.slice(0, 4000) + '\n\n...truncated'
      this.dirty.activity = false
      this.lastFlush.activity = now
      await this.createOrEdit('activity', text)
    }

    if (this.dirty.helix && now - this.lastFlush.helix >= WINDOW_INTERVALS.helix) {
      let text = this.formatter.formatHelix(this.helixes)
      if (text.length > 4096) text = text.slice(0, 4000) + '\n\n...truncated'
      this.dirty.helix = false
      this.lastFlush.helix = now
      await this.createOrEdit('helix', text)
    }

    if (this.dirty.corpus && now - this.lastFlush.corpus >= WINDOW_INTERVALS.corpus) {
      let text = this.formatter.formatCorpus(this.corpusLog)
      if (text.length > 4096) text = text.slice(0, 4000) + '\n\n...truncated'
      this.dirty.corpus = false
      this.lastFlush.corpus = now
      await this.createOrEdit('corpus', text)
    }

    this.pruneStaleState(now)
  }

  private pruneStaleState(now: number): void {
    const maxAgeMs = 30 * 60 * 1000
    for (const [cid, c] of this.constellations) {
      if (c.status !== 'running' && now - c.firstSeenAt > maxAgeMs) {
        this.constellations.delete(cid)
      }
    }
    for (const [hid, h] of this.helixes) {
      const cid = h.constellationId
      if (cid && !this.constellations.has(cid)) {
        this.helixes.delete(hid)
      }
    }
  }

  private async createOrEdit(windowId: string, text: string): Promise<void> {
    if (text === this.lastRendered[windowId]) return
    this.lastRendered[windowId] = text
    const msgId = this.messageIds[windowId]
    if (msgId) {
      this.rateLimiter.enqueue({
        id: `window-${windowId}-${Date.now()}`,
        text,
        chatId: this.chatId,
        editMessageId: msgId,
        priority: 'medium',
        timestamp: Date.now(),
      })
    }
  }

  async shutdown(): Promise<void> {
    this.persist()

    for (const id of ['dashboard', 'activity', 'helix', 'corpus'] as const) {
      const msgId = this.messageIds[id]
      if (msgId) {
        try {
          await this.client.editMessage(this.chatId, msgId, `${this.windowTitle(id)} — off`)
        } catch {
          // best-effort
        }
      }
    }
  }

  private windowTitle(id: string): string {
    switch (id) {
      case 'dashboard': return '📊 Constellation Dashboard'
      case 'activity': return '📌 Activity Timeline'
      case 'helix': return '🔬 Helix Activity'
      case 'corpus': return '🎯 Corpus Coordination'
      default: return ''
    }
  }

  getMessageIds(): Record<string, number | undefined> {
    return { ...this.messageIds }
  }

  private persist(): void {
    try {
      const dir = path.dirname(this.persistencePath)
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      fs.writeFileSync(this.persistencePath, JSON.stringify({
        chatId: this.chatId,
        windows: this.messageIds,
        savedAt: new Date().toISOString(),
      }, null, 2), 'utf-8')
    } catch (err) {
      this.logger.warn('[window-manager] Failed to persist window state', { error: String(err) })
    }
  }

  private restore(): void {
    try {
      if (!fs.existsSync(this.persistencePath)) return
      const raw = fs.readFileSync(this.persistencePath, 'utf-8')
      const data = JSON.parse(raw)
      if (data.chatId === this.chatId && data.windows) {
        for (const [id, msgId] of Object.entries(data.windows)) {
          if (typeof msgId === 'number') {
            this.messageIds[id] = msgId
          }
        }
      }
    } catch (err) {
      this.logger.warn('[window-manager] Failed to restore window state', { error: String(err) })
    }
  }
}
