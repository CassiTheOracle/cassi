/**
 * VENDORED — faithful type surface of `core/intelligence/module-session-registry.ts`.
 * Consumed by helix (index.ts) as `ModuleSessionRegistry`.
 *
 * Self-contained stub: imports only shared types from `@cassicore/foundation`.
 */
import type { ILogger, Session } from '@cassicore/foundation'

/** Compaction policy for a module session. */
export interface CompactionPolicy {
  hotWindowTurns: number
  compactionThreshold: number
  maxSummaryEras: number
  archiveCompacted: boolean
  importanceKeywords: string[]
}

/** Local surface of the session compactor injected after construction. */
export interface ModuleSessionCompactor {
  compact(sessionId: string, registration: ModuleRegistration): Promise<void>
}

/** Local surface of the session manager used by the registry. */
export interface SessionManager {
  getOrCreateById(
    stableId: string,
    channelId: string,
    senderId: string,
    config?: Partial<Session['config']> & { permanent?: boolean },
  ): Session
  get(sessionId: string): Session | undefined
  store?: { save(session: Session): unknown }
}

export interface ModuleRegistration {
  /** Stable key used in session IDs, e.g. 'thinker', 'lumen', 'subconscious.observer' */
  moduleKey: string
  /** Human-readable label shown in Telegram and admin API */
  displayName: string
  /** Which cognitive-feed topic this module posts to */
  topicKey: string
  /** Stable session ID: `module:{moduleKey}` */
  sessionId: string
  /** Smart compaction policy for this module */
  compactionPolicy: CompactionPolicy
}

const MODULE_DEFINITIONS: Array<Omit<ModuleRegistration, 'sessionId'>> = [
  { moduleKey: 'thinker', displayName: 'Thinker', topicKey: 'intelligence', compactionPolicy: { hotWindowTurns: 80, compactionThreshold: 150, maxSummaryEras: 10, archiveCompacted: true, importanceKeywords: ['insight', 'pattern', 'error', 'strategy', 'warning', 'critical', 'decision'] } },
  { moduleKey: 'subconscious.observer', displayName: 'Subconscious Observer', topicKey: 'intelligence', compactionPolicy: { hotWindowTurns: 30, compactionThreshold: 60, maxSummaryEras: 8, archiveCompacted: true, importanceKeywords: ['anomaly', 'alert', 'critical', 'error', 'pattern', 'observation'] } },
  { moduleKey: 'dialectic', displayName: 'Dialectic', topicKey: 'intelligence', compactionPolicy: { hotWindowTurns: 50, compactionThreshold: 100, maxSummaryEras: 8, archiveCompacted: true, importanceKeywords: ['conclusion', 'tension', 'synthesis', 'decision', 'error', 'agreement', 'disagreement'] } },
  { moduleKey: 'dialectic.guide', displayName: 'Dialectic Guide', topicKey: 'intelligence', compactionPolicy: { hotWindowTurns: 40, compactionThreshold: 80, maxSummaryEras: 6, archiveCompacted: true, importanceKeywords: ['guide', 'synthesis', 'recommendation', 'error'] } },
  { moduleKey: 'dreamer', displayName: 'Dreamer', topicKey: 'memory', compactionPolicy: { hotWindowTurns: 40, compactionThreshold: 80, maxSummaryEras: 8, archiveCompacted: true, importanceKeywords: ['insight', 'pattern', 'link', 'synthesis', 'error'] } },
  { moduleKey: 'memory.archiver', displayName: 'Memory Archiver', topicKey: 'memory', compactionPolicy: { hotWindowTurns: 30, compactionThreshold: 60, maxSummaryEras: 6, archiveCompacted: false, importanceKeywords: ['high', 'priority', 'error', 'decision'] } },
  { moduleKey: 'memory.search', displayName: 'Memory Search', topicKey: 'memory', compactionPolicy: { hotWindowTurns: 30, compactionThreshold: 60, maxSummaryEras: 6, archiveCompacted: false, importanceKeywords: ['found', 'high relevance', 'error', 'synthesis'] } },
  { moduleKey: 'context-distiller', displayName: 'Context Distiller', topicKey: 'system', compactionPolicy: { hotWindowTurns: 20, compactionThreshold: 40, maxSummaryEras: 4, archiveCompacted: false, importanceKeywords: ['error', 'failed'] } },
  { moduleKey: 'scout', displayName: 'Scout', topicKey: 'system', compactionPolicy: { hotWindowTurns: 20, compactionThreshold: 40, maxSummaryEras: 4, archiveCompacted: false, importanceKeywords: ['error', 'tool', 'result', 'context'] } },
  { moduleKey: 'drone-swarm', displayName: 'Drone Swarm', topicKey: 'constellation', compactionPolicy: { hotWindowTurns: 40, compactionThreshold: 80, maxSummaryEras: 6, archiveCompacted: true, importanceKeywords: ['error', 'result', 'complete', 'failed', 'mission'] } },
  { moduleKey: 'lumen', displayName: 'Lumen', topicKey: 'constellation', compactionPolicy: { hotWindowTurns: 60, compactionThreshold: 120, maxSummaryEras: 10, archiveCompacted: true, importanceKeywords: ['decision', 'recommendation', 'error', 'conclusion', 'synthesis', 'goal'] } },
  { moduleKey: 'dyad', displayName: 'Dyad', topicKey: 'constellation', compactionPolicy: { hotWindowTurns: 60, compactionThreshold: 120, maxSummaryEras: 10, archiveCompacted: true, importanceKeywords: ['error', 'complete', 'refinement', 'apex', 'result', 'goal'] } },
  { moduleKey: 'triad', displayName: 'Triad Team', topicKey: 'constellation', compactionPolicy: { hotWindowTurns: 60, compactionThreshold: 120, maxSummaryEras: 10, archiveCompacted: true, importanceKeywords: ['error', 'conclusion', 'critique', 'proposal', 'execution'] } },
  { moduleKey: 'triad-team', displayName: 'Triad Team Orchestrator', topicKey: 'constellation', compactionPolicy: { hotWindowTurns: 60, compactionThreshold: 120, maxSummaryEras: 10, archiveCompacted: true, importanceKeywords: ['error', 'conclusion', 'team', 'cell', 'checkpoint', 'planning'] } },
  { moduleKey: 'helix', displayName: 'Helix', topicKey: 'constellation', compactionPolicy: { hotWindowTurns: 60, compactionThreshold: 120, maxSummaryEras: 10, archiveCompacted: true, importanceKeywords: ['error', 'review', 'refinement', 'yang', 'yin', 'synthesis', 'goal'] } },
]

export class ModuleSessionRegistry {
  private readonly logger: ILogger
  private readonly sessionManager: SessionManager
  private readonly registrations = new Map<string, ModuleRegistration>()
  private readonly sessionToKey = new Map<string, string>()
  private readonly topicModules = new Map<string, string[]>()
  private compactor: ModuleSessionCompactor | undefined

  constructor(sessionManager: SessionManager, logger: ILogger) {
    this.sessionManager = sessionManager
    this.logger = logger.child?.('module-session-registry') ?? logger

    for (const def of MODULE_DEFINITIONS) {
      const sessionId = `module:${def.moduleKey}`
      const reg: ModuleRegistration = { ...def, sessionId }
      this.registrations.set(def.moduleKey, reg)
      this.sessionToKey.set(sessionId, def.moduleKey)
      const existing = this.topicModules.get(def.topicKey) ?? []
      existing.push(def.moduleKey)
      this.topicModules.set(def.topicKey, existing)
    }
  }

  setCompactor(compactor: ModuleSessionCompactor): void {
    this.compactor = compactor
  }

  async compactNow(moduleKey: string): Promise<boolean> {
    const reg = this.registrations.get(moduleKey)
    if (!reg || !this.compactor) return false
    await this.compactor.compact(reg.sessionId, reg)
    return true
  }

  getOrCreate(moduleKey: string): Session {
    let reg = this.registrations.get(moduleKey)
    if (!reg) {
      this.logger.warn(`ModuleSessionRegistry: unknown module key '${moduleKey}' — creating ad-hoc`)
      const sessionId = `module:${moduleKey}`
      const adHoc: ModuleRegistration = {
        moduleKey,
        displayName: moduleKey,
        topicKey: 'system',
        sessionId,
        compactionPolicy: {
          hotWindowTurns: 40,
          compactionThreshold: 80,
          maxSummaryEras: 6,
          archiveCompacted: false,
          importanceKeywords: ['error'],
        },
      }
      this.registrations.set(moduleKey, adHoc)
      this.sessionToKey.set(sessionId, moduleKey)
      reg = adHoc
    }

    const { sessionId, displayName } = reg
    return this.sessionManager.getOrCreateById(
      sessionId,
      'channel:module',
      `module:${moduleKey}`,
      { permanent: true } as any,
    )
  }

  getSessionId(moduleKey: string): string | undefined {
    return this.registrations.get(moduleKey)?.sessionId
  }

  getModuleKey(sessionId: string): string | undefined {
    return this.sessionToKey.get(sessionId)
  }

  getRegistration(moduleKey: string): ModuleRegistration | undefined {
    return this.registrations.get(moduleKey)
  }

  getModulesForTopic(topicKey: string): string[] {
    return this.topicModules.get(topicKey) ?? []
  }

  getMostRecentModuleForTopic(topicKey: string): string | undefined {
    const keys = this.topicModules.get(topicKey) ?? []
    if (keys.length === 0) return undefined
    if (keys.length === 1) return keys[0]
    let bestKey: string | undefined
    let bestTime = 0
    for (const key of keys) {
      const reg = this.registrations.get(key)
      if (!reg) continue
      const session = this.sessionManager.get(reg.sessionId)
      const t = session?.lastActiveAt?.getTime() ?? 0
      if (t > bestTime) {
        bestTime = t
        bestKey = key
      }
    }
    return bestKey ?? keys[0]
  }

  appendTurn(moduleKey: string, role: 'user' | 'assistant', content: string): void {
    const reg = this.registrations.get(moduleKey)
    if (!reg) return
    const session = this.sessionManager.get(reg.sessionId)
    if (!session) return
    session.history.push({ role, text: content, timestamp: new Date() } as any)
    session.lastActiveAt = new Date()
    try {
      ;(this.sessionManager as any).store?.save(session)
    } catch { /* best-effort */ }
    if (this.compactor && session.history.length > reg.compactionPolicy.compactionThreshold) {
      void this.compactor.compact(reg.sessionId, reg).catch((err: unknown) => {
        this.logger.warn(`ModuleSessionRegistry: compaction failed for ${moduleKey}`, { error: String(err) })
      })
    }
  }

  listAll(): Array<{
    moduleKey: string
    displayName: string
    topicKey: string
    sessionId: string
    lastActiveAt: Date | undefined
    turnCount: number
  }> {
    return Array.from(this.registrations.values()).map(reg => {
      const session = this.sessionManager.get(reg.sessionId)
      return {
        moduleKey: reg.moduleKey,
        displayName: reg.displayName,
        topicKey: reg.topicKey,
        sessionId: reg.sessionId,
        lastActiveAt: session?.lastActiveAt,
        turnCount: session?.history?.length ?? 0,
      }
    })
  }

  async warmAll(): Promise<void> {
    for (const reg of this.registrations.values()) {
      try {
        this.getOrCreate(reg.moduleKey)
      } catch (err) {
        this.logger.warn(`ModuleSessionRegistry: failed to warm session for ${reg.moduleKey}`, {
          error: String(err),
        })
      }
    }
    this.logger.info(`ModuleSessionRegistry: warmed ${this.registrations.size} module sessions`)
  }
}
