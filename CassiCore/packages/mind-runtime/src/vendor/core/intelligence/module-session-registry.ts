/**
 * ModuleSessionRegistry
 *
 * Creates and manages stable, persistent CassiCore sessions for every LLM-calling
 * intelligence module. These sessions survive daemon restarts, accumulate history,
 * and are exposed as interactive Telegram topics for debugging.
 *
 * Session ID convention: `module:{key}`
 * Example: `module:thinker`, `module:subconscious.observer`, `module:lumen`
 */

import type { ILogger } from '@cassicore/foundation'
import type { Session } from '@cassicore/foundation'
import type { SessionManager } from '../session-manager.js'
import type { ModuleSessionCompactor, CompactionPolicy } from './module-session-compactor.js'


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

// Module → topic mapping and compaction policies
// Modules sharing a topic are distinguished by [ModuleName] prefix in Telegram posts

const MODULE_DEFINITIONS: Array<Omit<ModuleRegistration, 'sessionId'>> = [
  // Thinker — high-value insights, keep more history
  {
    moduleKey: 'thinker',
    displayName: 'Thinker',
    topicKey: 'intelligence',
    compactionPolicy: {
      hotWindowTurns: 80,
      compactionThreshold: 150,
      maxSummaryEras: 10,
      archiveCompacted: true,
      importanceKeywords: ['insight', 'pattern', 'error', 'strategy', 'warning', 'critical', 'decision'],
    },
  },

  // Subconscious Observer — mostly routine scans, compact aggressively
  {
    moduleKey: 'subconscious.observer',
    displayName: 'Subconscious Observer',
    topicKey: 'intelligence',
    compactionPolicy: {
      hotWindowTurns: 30,
      compactionThreshold: 60,
      maxSummaryEras: 8,
      archiveCompacted: true,
      importanceKeywords: ['anomaly', 'alert', 'critical', 'error', 'pattern', 'observation'],
    },
  },

  // Dialectic — standard threshold, valuable reasoning chains
  {
    moduleKey: 'dialectic',
    displayName: 'Dialectic',
    topicKey: 'intelligence',
    compactionPolicy: {
      hotWindowTurns: 50,
      compactionThreshold: 100,
      maxSummaryEras: 8,
      archiveCompacted: true,
      importanceKeywords: ['conclusion', 'tension', 'synthesis', 'decision', 'error', 'agreement', 'disagreement'],
    },
  },

  // Dialectic guide processor
  {
    moduleKey: 'dialectic.guide',
    displayName: 'Dialectic Guide',
    topicKey: 'intelligence',
    compactionPolicy: {
      hotWindowTurns: 40,
      compactionThreshold: 80,
      maxSummaryEras: 6,
      archiveCompacted: true,
      importanceKeywords: ['guide', 'synthesis', 'recommendation', 'error'],
    },
  },

  // Dreamer — dream cycles are self-summarizing
  {
    moduleKey: 'dreamer',
    displayName: 'Dreamer',
    topicKey: 'memory',
    compactionPolicy: {
      hotWindowTurns: 40,
      compactionThreshold: 80,
      maxSummaryEras: 8,
      archiveCompacted: true,
      importanceKeywords: ['insight', 'pattern', 'link', 'synthesis', 'error'],
    },
  },

  // Archive analyzer — routine analysis
  {
    moduleKey: 'memory.archiver',
    displayName: 'Memory Archiver',
    topicKey: 'memory',
    compactionPolicy: {
      hotWindowTurns: 30,
      compactionThreshold: 60,
      maxSummaryEras: 6,
      archiveCompacted: false,
      importanceKeywords: ['high', 'priority', 'error', 'decision'],
    },
  },

  // Continuous search — mostly routine
  {
    moduleKey: 'memory.search',
    displayName: 'Memory Search',
    topicKey: 'memory',
    compactionPolicy: {
      hotWindowTurns: 30,
      compactionThreshold: 60,
      maxSummaryEras: 6,
      archiveCompacted: false,
      importanceKeywords: ['found', 'high relevance', 'error', 'synthesis'],
    },
  },

  // Context distiller — very routine, compact aggressively
  {
    moduleKey: 'context-distiller',
    displayName: 'Context Distiller',
    topicKey: 'system',
    compactionPolicy: {
      hotWindowTurns: 20,
      compactionThreshold: 40,
      maxSummaryEras: 4,
      archiveCompacted: false,
      importanceKeywords: ['error', 'failed'],
    },
  },

  // Scout
  {
    moduleKey: 'scout',
    displayName: 'Scout',
    topicKey: 'system',
    compactionPolicy: {
      hotWindowTurns: 20,
      compactionThreshold: 40,
      maxSummaryEras: 4,
      archiveCompacted: false,
      importanceKeywords: ['error', 'tool', 'result', 'context'],
    },
  },

  // Drone swarm
  {
    moduleKey: 'drone-swarm',
    displayName: 'Drone Swarm',
    topicKey: 'constellation',
    compactionPolicy: {
      hotWindowTurns: 40,
      compactionThreshold: 80,
      maxSummaryEras: 6,
      archiveCompacted: true,
      importanceKeywords: ['error', 'result', 'complete', 'failed', 'mission'],
    },
  },

  // Orchestrators — keep more history, valuable for debugging runs
  {
    moduleKey: 'lumen',
    displayName: 'Lumen',
    topicKey: 'constellation',
    compactionPolicy: {
      hotWindowTurns: 60,
      compactionThreshold: 120,
      maxSummaryEras: 10,
      archiveCompacted: true,
      importanceKeywords: ['decision', 'recommendation', 'error', 'conclusion', 'synthesis', 'goal'],
    },
  },

  {
    moduleKey: 'dyad',
    displayName: 'Dyad',
    topicKey: 'constellation',
    compactionPolicy: {
      hotWindowTurns: 60,
      compactionThreshold: 120,
      maxSummaryEras: 10,
      archiveCompacted: true,
      importanceKeywords: ['error', 'complete', 'refinement', 'apex', 'result', 'goal'],
    },
  },

  {
    moduleKey: 'triad',
    displayName: 'Triad Team',
    topicKey: 'constellation',
    compactionPolicy: {
      hotWindowTurns: 60,
      compactionThreshold: 120,
      maxSummaryEras: 10,
      archiveCompacted: true,
      importanceKeywords: ['error', 'conclusion', 'critique', 'proposal', 'execution'],
    },
  },

  // triad-team module (TriadTeamOrchestrator.name = 'triad-team')
  // Distinct from 'triad' which is used by member/executor sessions.
  {
    moduleKey: 'triad-team',
    displayName: 'Triad Team Orchestrator',
    topicKey: 'constellation',
    compactionPolicy: {
      hotWindowTurns: 60,
      compactionThreshold: 120,
      maxSummaryEras: 10,
      archiveCompacted: true,
      importanceKeywords: ['error', 'conclusion', 'team', 'cell', 'checkpoint', 'planning'],
    },
  },

  // Helix orchestrator (HelixOrchestrator.name = 'helix')
  {
    moduleKey: 'helix',
    displayName: 'Helix',
    topicKey: 'constellation',
    compactionPolicy: {
      hotWindowTurns: 60,
      compactionThreshold: 120,
      maxSummaryEras: 10,
      archiveCompacted: true,
      importanceKeywords: ['error', 'review', 'refinement', 'yang', 'yin', 'synthesis', 'goal'],
    },
  },
]


export class ModuleSessionRegistry {
  private readonly logger: ILogger
  private readonly sessionManager: SessionManager
  private readonly registrations = new Map<string, ModuleRegistration>()
  /** Reverse map: sessionId → moduleKey */
  private readonly sessionToKey = new Map<string, string>()
  /** topic key → list of module keys registered to that topic */
  private readonly topicModules = new Map<string, string[]>()
  private compactor: ModuleSessionCompactor | undefined

  constructor(sessionManager: SessionManager, logger: ILogger) {
    this.sessionManager = sessionManager
    this.logger = logger.child?.('module-session-registry') ?? logger

    // Pre-register all known modules at construction time.
    // Sessions are created lazily on first getSessionId() / getOrCreate() call.
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

  /** Wire in the compactor (injected after construction to avoid circular dep). */
  setCompactor(compactor: ModuleSessionCompactor): void {
    this.compactor = compactor
  }

  async compactNow(moduleKey: string): Promise<boolean> {
    const reg = this.registrations.get(moduleKey)
    if (!reg || !this.compactor) return false
    await this.compactor.compact(reg.sessionId, reg)
    return true
  }

  /**
   * Get or create the persistent session for a module.
   * Creates the session via SessionManager.getOrCreateById() so it is persisted to disk.
   */
  getOrCreate(moduleKey: string): Session {
    const reg = this.registrations.get(moduleKey)
    if (!reg) {
      this.logger.warn(`ModuleSessionRegistry: unknown module key '${moduleKey}' — creating ad-hoc`)
      // Register ad-hoc so repeated calls don't re-warn
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
    }

    const { sessionId, displayName } = this.registrations.get(moduleKey)!

    return this.sessionManager.getOrCreateById(
      sessionId,
      'channel:module',
      `module:${moduleKey}`,
      { permanent: true } as any,
    )
  }

  /**
   * Get the stable session ID for a module key.
   * Returns undefined if the module key is not registered.
   */
  getSessionId(moduleKey: string): string | undefined {
    return this.registrations.get(moduleKey)?.sessionId
  }

  /**
   * Resolve a session ID back to its module key.
   * Returns undefined if the session ID does not belong to a module session.
   */
  getModuleKey(sessionId: string): string | undefined {
    return this.sessionToKey.get(sessionId)
  }

  /**
   * Get the registration for a module key.
   */
  getRegistration(moduleKey: string): ModuleRegistration | undefined {
    return this.registrations.get(moduleKey)
  }

  /**
   * Get all module keys registered for a Telegram topic key.
   * Multiple modules may share a topic (e.g. 'memoryDreams' has dreamer, archiver, search).
   */
  getModulesForTopic(topicKey: string): string[] {
    return this.topicModules.get(topicKey) ?? []
  }

  /**
   * Get the most recently active module session on a topic.
   * Used to route plain-text Telegram messages in topic to the right session.
   */
  getMostRecentModuleForTopic(topicKey: string): string | undefined {
    const keys = this.topicModules.get(topicKey) ?? []
    if (keys.length === 0) return undefined
    if (keys.length === 1) return keys[0]

    // Pick the one whose session was most recently active
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

  /**
   * Append a turn to a module's session history.
   * Triggers smart compaction asynchronously if the threshold is exceeded.
   */
  appendTurn(moduleKey: string, role: 'user' | 'assistant', content: string): void {
    const reg = this.registrations.get(moduleKey)
    if (!reg) return

    const session = this.sessionManager.get(reg.sessionId)
    if (!session) return

    // Append to history
    session.history.push({ role, text: content, timestamp: new Date() } as any)
    session.lastActiveAt = new Date()

    // Persist the updated session
    try {
      ;(this.sessionManager as any).store?.save(session)
    } catch { /* best-effort */ }

    // Trigger compaction asynchronously if threshold exceeded
    if (
      this.compactor &&
      session.history.length > reg.compactionPolicy.compactionThreshold
    ) {
      void this.compactor.compact(reg.sessionId, reg).catch((err: unknown) => {
        this.logger.warn(`ModuleSessionRegistry: compaction failed for ${moduleKey}`, { error: String(err) })
      })
    }
  }

  /**
   * List all registered module sessions with their metadata.
   */
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

  /**
   * Pre-warm all module sessions: ensures every session is loaded from disk
   * (or created fresh) so they are ready before the first LLM call.
   */
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
