import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { ThinkerSession, type ThinkerSdkProvider } from './thinker-session.js'
import { ConcreteThinkerToolProvider } from './thinker-tool-provider.js'

import type { IMemory, IThinker, ThinkerStats } from '@cassicore/foundation'
import type { ILogger, ThinkerDeferredWiring } from '@cassicore/foundation'
import type { CorticalField } from '@cassicore/cortex-pineal-dialectic'
import type { IProvider } from '@cassicore/foundation'

export interface ThinkerConfig {
  enabled: boolean
  ponderInterval: number
  thinkInterval: number
  ponderModel: string
  thinkModel: string
  enableSwarm?: boolean
  enableAdaptation?: boolean
  enableDialecticHandoff?: boolean
}

interface ThinkerFeedbackEntry {
  insight: string
  level: 'ponder' | 'think'
  timestamp: number
  helpful?: boolean
  usedInResponse?: boolean
}

const DEFAULT_CONFIG: ThinkerConfig = {
  enabled: false,
  ponderInterval: 30,
  thinkInterval: 150,
  ponderModel: 'copilot-sdk/gpt-5-mini',
  thinkModel: 'copilot-sdk/gpt-5-mini',
  enableSwarm: false,
  enableAdaptation: true,
  enableDialecticHandoff: false,
}

export class ThinkerModule extends BaseCognitiveModule implements IThinker {
  __awaitingWiring?: ThinkerDeferredWiring
  readonly name = 'thinker'
  readonly priority = 30

  private readonly thinkerConfig: ThinkerConfig
  private thinkerSessions = new Map<string, {
    session: ThinkerSession
    hostSessionId: string
    lastActivityAt: number
  }>()
  private providerInstance?: IProvider
  private insightCount = 0
  private insightHistory: ThinkerFeedbackEntry[] = []
  private lastPonderAt?: Date
  private lastThinkAt?: Date
  private totalTurns = 0
  private totalToolCalls = 0
  private toolProvider?: ConcreteThinkerToolProvider
  private cortex?: CorticalField
  private static readonly HOST_ACTIVITY_TTL_MS = 60_000

  constructor(logger: ILogger, config?: Partial<ThinkerConfig>, memory?: IMemory) {
    super(logger)
    this.thinkerConfig = { ...DEFAULT_CONFIG, ...config }
    this.memory = memory

    if (this.thinkerConfig.enabled) {
      this.logger.info('Thinker: enabled (ThinkerSession facade)', {
        model: this.thinkerConfig.thinkModel,
      })
    } else {
      this.logger.info('Thinker: disabled (opt-in via config.enabled)')
    }
  }

  override async init(): Promise<void> {
    await super.init()
    await this.loadPersistedState()
  }

  override async start(): Promise<void> {
    await super.start()
    if (!this.thinkerConfig.enabled) return
  }

  override async stop(): Promise<void> {
    for (const entry of this.thinkerSessions.values()) {
      await entry.session.stop()
    }
    this.thinkerSessions.clear()
    await super.stop()
  }

  override setMemory(memory: IMemory): void {
    super.setMemory(memory)
    this.ensureToolProvider()
    void this.loadPersistedState()
  }

  override setProvider(provider: IProvider): void {
    super.setProvider(provider)
    this.providerInstance = provider
  }

  setCortex(cortex: CorticalField): void {
    this.cortex = cortex
  }

  setIntrospectionSources(_sources: Record<string, unknown>): void {
    // Fast-delete path: the old thinker introspection engine is intentionally dropped.
  }

  getThinkerSession(hostSessionId: string): ThinkerSession | undefined {
    if (!this.thinkerConfig.enabled) return undefined
    this.touchHostSession(hostSessionId)
    const existing = this.thinkerSessions.get(hostSessionId)
    if (existing) return existing.session
    const session = this.createThinkerSession(hostSessionId)
    this.thinkerSessions.set(hostSessionId, {
      session,
      hostSessionId,
      lastActivityAt: Date.now(),
    })
    void session.start()
    return session
  }

  getThinkerSessionId(hostSessionId: string): string | undefined {
    return this.getThinkerSession(hostSessionId)?.getStats().sessionId
  }

  async recordInsightFeedback(insightId: string, helpful: boolean, usedInResponse: boolean = false): Promise<void> {
    const now = Date.now()
    const existing = this.insightHistory.find((entry) => entry.insight === insightId)
    if (existing) {
      existing.helpful = helpful
      existing.usedInResponse = existing.usedInResponse || usedInResponse
      existing.timestamp = now
    } else {
      this.insightHistory.push({
        insight: insightId,
        level: 'ponder',
        timestamp: now,
        helpful,
        usedInResponse,
      })
    }
    this.insightHistory = this.insightHistory.slice(-50)
    await this.persistFeedbackState()
  }

  async markInsightUsed(insightId: string): Promise<void> {
    const now = Date.now()
    const existing = this.insightHistory.find((entry) => entry.insight === insightId)
    if (existing) {
      existing.usedInResponse = true
      existing.timestamp = now
    } else {
      this.insightHistory.push({
        insight: insightId,
        level: 'ponder',
        timestamp: now,
        usedInResponse: true,
      })
    }
    this.insightHistory = this.insightHistory.slice(-50)
    await this.persistFeedbackState()
  }

  override onEventBus(bus: any): void {
    super.onEventBus(bus)

    this.subscribe('turn:end' as any, async () => {
      this.totalTurns += 1
      if (this.memory && this.totalTurns % 10 === 0) {
        try {
          await this.memory.kv_set('thinker:turnCount', this.totalTurns)
        } catch {
          // best-effort
        }
      }
    })

    this.subscribe('turn:start' as any, async (e: any) => {
      if (e?.sessionId) {
        this.touchHostSession(String(e.sessionId))
        await this.cleanupInactiveSessions()
      }
    })

    this.subscribe('tool:executed' as any, async () => {
      this.totalToolCalls += 1
      if (this.memory && this.totalToolCalls % 10 === 0) {
        try {
          await this.memory.kv_set('thinker:toolCallCount', this.totalToolCalls)
        } catch {
          // best-effort
        }
      }
    })

    this.subscribe('turn:tool_call' as any, async (e: any) => {
      if (e?.sessionId) {
        this.touchHostSession(String(e.sessionId))
        await this.cleanupInactiveSessions()
      }
    })

    this.subscribe('turn:tool_result' as any, async (e: any) => {
      if (e?.sessionId) {
        this.touchHostSession(String(e.sessionId))
        await this.cleanupInactiveSessions()
      }
    })

    this.subscribe('turn:thinking' as any, async (e: any) => {
      if (e?.sessionId) {
        this.touchHostSession(String(e.sessionId))
        await this.cleanupInactiveSessions()
      }
    })

    this.subscribe('session_idle' as any, async (e: any) => {
      if (e?.sessionId) {
        const hostSessionId = String(e.sessionId)
        const entry = this.thinkerSessions.get(hostSessionId)
        if (entry && !this.isHostSessionActive(hostSessionId)) {
          await entry.session.stop()
          this.thinkerSessions.delete(hostSessionId)
        }
      }
    })

    this.subscribe('thinker:insight-applied' as any, async (e: any) => {
      const insight = e?.insight ?? e?.payload?.insight
      if (insight) await this.markInsightUsed(String(insight))
    })

    this.subscribe('thinker:feedback' as any, async (e: any) => {
      const body = e?.payload ? e.payload : e
      const insight = body?.insight
      const helpful = body?.helpful
      const usedInResponse = body?.usedInResponse ?? false
      if (insight && typeof helpful === 'boolean') {
        await this.recordInsightFeedback(String(insight), Boolean(helpful), Boolean(usedInResponse))
      }
    })

    this.subscribe('thinker:repair-request' as any, async (e: any) => {
      if (!this.eventBus || !e?.id || !e?.prompt) return
      const hostSessionId = String(e.sessionId ?? 'repair')
      const text = await this.requestInsight(hostSessionId, String(e.prompt), 'ponder', 30_000)
      this.eventBus.emit({ type: 'thinker:repair-response', id: e.id, text })
    })
  }

  async stats(): Promise<ThinkerStats> {
    return {
      totalInsights: this.insightCount,
      totalTurns: this.totalTurns,
      totalToolCalls: this.totalToolCalls,
      toolCallsUntilPonder: 0,
      ponderInterval: this.thinkerConfig.ponderInterval,
      thinkInterval: this.thinkerConfig.thinkInterval,
      ponderUnit: 'tool-calls',
      insightCount: this.insightCount,
      recentToolActivity: Math.min(this.totalToolCalls, 50),
      lastPonderAt: this.lastPonderAt,
      lastThinkAt: this.lastThinkAt,
    }
  }

  async think(depth: 'Ponder' | 'Think', _signal?: AbortSignal): Promise<string> {
    if (!this.thinkerConfig.enabled) {
      return '[Thinker: disabled]'
    }

    const internalDepth = depth === 'Think' ? 'think' : 'ponder'
    const prompt = internalDepth === 'think'
      ? 'Perform a deep strategic reflection on the current context. Return the single most useful observation.'
      : 'Perform a quick tactical reflection on the current context. Return the single most useful observation.'

    const hostSessionId = 'manual'
    const content = await this.requestInsight(hostSessionId, prompt, internalDepth, internalDepth === 'think' ? 10_000 : 5_000)
    if (internalDepth === 'think') this.lastThinkAt = new Date()
    else this.lastPonderAt = new Date()

    if (this.isQualityInsight(content)) {
      this.insightCount += 1
      await this.persistInsight(content, internalDepth)
      if (this.eventBus) {
        this.eventBus.emit({
          type: 'thinker:inject-insight',
          sessionId: hostSessionId,
          insight: `[Thinker Insight] ${content}`,
          level: internalDepth === 'think' ? 'Think' : 'Ponder',
        })
      }
      if (this.cortex) {
        try {
          this.cortex.signal('monitor', {
            type: 'insight',
            content,
            author: 'thinker',
            sessionId: hostSessionId,
            salience: internalDepth === 'think' ? 0.7 : 0.5,
            valence: 0.2,
            tags: [internalDepth],
          })
        } catch { /* cortex signal is fire-and-forget */ }
      }
    }

    return content
  }

  private async requestInsight(hostSessionId: string, prompt: string, depth: 'ponder' | 'think', timeoutMs: number): Promise<string> {
    const session = this.getThinkerSession(hostSessionId)
    if (!session) return '[Thinker: session unavailable]'

    const requestId = session.enqueueThought(prompt, {
      step: 1,
      estimatedSteps: 1,
      isRevision: false,
      branchId: depth,
    })

    const hasResponse = await session.waitForResponse(timeoutMs)
    if (!hasResponse) {
      return '[Thinker: no response available]'
    }

    const buffered = session.drainBuffer()
    const response = buffered.find((item) => item.requestId === requestId) ?? buffered[buffered.length - 1]
    return response?.content ?? '[Thinker: empty response]'
  }

  private ensureToolProvider(): void {
    if (this.toolProvider || !this.memory) return
    this.toolProvider = new ConcreteThinkerToolProvider({
      workspaceRoot: process.cwd(),
      logger: this.logger,
      memory: this.memory,
      blackboardRegistry: this.globalBlackboardRegistry,
    })
  }

  private createThinkerSession(hostSessionId: string): ThinkerSession {
    this.ensureToolProvider()
    return new ThinkerSession({
      logger: this.logger,
      bus: this.eventBus,
      sessionKey: `thinker:${hostSessionId}`,
      hostSessionId,
      getProvider: () => {
        const sdkProvider = this.providerResolver?.('copilot-sdk') as ThinkerSdkProvider | undefined
        if (sdkProvider?.executeSdkTurn || sdkProvider?.executeScopedTurn || sdkProvider?.executePersistentScopedTurn) return sdkProvider
        const direct = this.providerInstance as ThinkerSdkProvider | undefined
        if (direct?.executeSdkTurn || direct?.executeScopedTurn || direct?.executePersistentScopedTurn) return direct
        return undefined
      },
      toolProvider: this.toolProvider,
      config: {
        enabled: this.thinkerConfig.enabled,
        model: this.thinkerConfig.thinkModel,
      },
    })
  }

  private touchHostSession(hostSessionId: string): void {
    const now = Date.now()
    const entry = this.thinkerSessions.get(hostSessionId)
    if (entry) {
      entry.lastActivityAt = now
      return
    }
  }

  private isHostSessionActive(hostSessionId: string): boolean {
    const entry = this.thinkerSessions.get(hostSessionId)
    if (!entry) return false
    return (Date.now() - entry.lastActivityAt) < ThinkerModule.HOST_ACTIVITY_TTL_MS
  }

  private async cleanupInactiveSessions(): Promise<void> {
    const stale: string[] = []
    for (const [hostSessionId, entry] of this.thinkerSessions.entries()) {
      if ((Date.now() - entry.lastActivityAt) >= ThinkerModule.HOST_ACTIVITY_TTL_MS) {
        stale.push(hostSessionId)
      }
    }

    for (const hostSessionId of stale) {
      const entry = this.thinkerSessions.get(hostSessionId)
      if (!entry) continue
      await entry.session.stop()
      this.thinkerSessions.delete(hostSessionId)
    }
  }

  private async loadPersistedState(): Promise<void> {
    if (!this.memory) return

    try {
      const history = await this.memory.kv_get<ThinkerFeedbackEntry[]>('thinker:insight-history')
      if (Array.isArray(history)) this.insightHistory = history.slice(-50)
    } catch {
      // best-effort
    }

    try {
      const insightCount = await this.memory.kv_get<number>('thinker:insightCount')
      if (typeof insightCount === 'number') this.insightCount = insightCount
    } catch {
      // best-effort
    }

    try {
      const turns = await this.memory.kv_get<number>('thinker:turnCount')
      if (typeof turns === 'number') this.totalTurns = turns
    } catch {
      // best-effort
    }

    try {
      const toolCalls = await this.memory.kv_get<number>('thinker:toolCallCount')
      if (typeof toolCalls === 'number') this.totalToolCalls = toolCalls
    } catch {
      // best-effort
    }
  }

  private async persistFeedbackState(): Promise<void> {
    if (!this.memory) return
    try {
      await this.memory.kv_set('thinker:insight-history', this.insightHistory)
    } catch {
      // best-effort
    }
  }

  private async persistInsight(insight: string, level: 'ponder' | 'think'): Promise<void> {
    if (!this.memory) return
    try {
      await this.memory.kv_set('thinker:insightCount', this.insightCount)
      await this.memory.store({
        type: 'insight',
        content: insight,
        metadata: { source: 'thinker-session-facade', level },
      })
    } catch {
      // best-effort
    }
  }

  private isQualityInsight(insight: string): boolean {
    if (insight.length < 20) return false

    const conversationMarkers = /^(user|assistant|human|system)\s*:/im
    const markerCount = (insight.match(new RegExp(conversationMarkers.source, 'gim')) || []).length
    if (markerCount >= 3) return false

    const lowerInsight = insight.toLowerCase()
    const capabilityDisclaimers = [
      'cannot execute local shell commands',
      'cannot access the filesystem',
      'cannot read your repo',
      'lack filesystem access',
      'ask the user to provide the file contents',
    ]
    if (capabilityDisclaimers.some((phrase) => lowerInsight.includes(phrase))) return false

    return true
  }
}

export const createThinker = (logger: ILogger, config?: Partial<ThinkerConfig>, memory?: IMemory): ThinkerModule =>
  new ThinkerModule(logger, config, memory)

export const MODULE_CLASS = ThinkerModule
