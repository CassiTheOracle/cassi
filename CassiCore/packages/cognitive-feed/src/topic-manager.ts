/**
 * TopicManager — Creates and tracks Telegram Forum Topics for each cognitive module.
 *
 * On startup, ensures all configured topics exist in the supergroup.
 * Persists topic IDs to avoid re-creation on restart.
 *
 * Topic colors follow a semantic scheme:
 *  - Violet (13338331): Dialectic/reasoning systems (Lumen, Dialectic, Thinker)
 *  - Blue   (7322096):  Work/pipeline systems (Dyad, MultiAgent, LLM Calls)
 *  - Green  (9367192):  Growth/memory systems (FluxTeam, Memory, Blackboard)
 *  - Yellow (16766590): Planning/adaptive systems (TriadTeam, Adaptive)
 *  - Rose   (16749490): Parallel/heartbeat systems (DroneSwarm, Heart)
 *  - Red    (16478047): Alerting/system (Consciousness, System)
 */

import { homedir } from 'node:os'
import { join } from 'node:path'
import { readFile, writeFile, mkdir } from 'node:fs/promises'

import type { TelegramClient, ForumTopic } from './telegram-client.js'
import type { ILogger } from '../../../types/interfaces.js'

// Topic Color Constants

export const TOPIC_COLORS = {
  BLUE:   7322096,   // 0x6FB9F0
  YELLOW: 16766590,  // 0xFFD67E
  VIOLET: 13338331,  // 0xCB86DB
  GREEN:  9367192,   // 0x8EEE98
  ROSE:   16749490,  // 0xFF93B2
  RED:    16478047,  // 0xFB6F5F
} as const

// Topic Definitions

/** Audience category for topic grouping and naming conventions */
export type TopicCategory = 'ops' | 'intel' | 'team' | 'user'

export interface TopicDefinition {
  key: string
  displayName: string
  color: number
  description: string
  /** Audience category — groups topics by intended consumer */
  category: TopicCategory
}

/**
 * All available topic definitions.
 * Order determines creation order in the supergroup.
 */
export const TOPIC_DEFINITIONS: TopicDefinition[] = [
  // Team / orchestration systems
  { key: 'dyad',        displayName: 'Dyad',           color: TOPIC_COLORS.BLUE,   description: 'Yang/Yin/Apex pipeline',                category: 'team' },
  { key: 'lumen',       displayName: 'Lumen',          color: TOPIC_COLORS.VIOLET, description: 'Yang/Yin/Executive dialectic',           category: 'team' },
  { key: 'fluxTeam',    displayName: 'FluxTeam',       color: TOPIC_COLORS.GREEN,  description: 'Graph-based team execution',             category: 'team' },
  { key: 'triadTeam',   displayName: 'Triad Team',     color: TOPIC_COLORS.YELLOW, description: 'Proposer/Critic/Executor hierarchy',     category: 'team' },
  { key: 'droneSwarm',  displayName: 'Drone Swarm',    color: TOPIC_COLORS.ROSE,   description: 'Parallel agent fan-out',                 category: 'team' },
  { key: 'multiAgent',  displayName: 'Multi-Agent',    color: TOPIC_COLORS.BLUE,   description: 'Agent spawning & coordination',          category: 'team' },

  // Intelligence modules
  { key: 'thinker',       displayName: 'Thinker',        color: TOPIC_COLORS.VIOLET, description: 'Autonomous background thinking',       category: 'intel' },
  { key: 'dialectic',     displayName: 'Dialectic',      color: TOPIC_COLORS.VIOLET, description: 'Inline Yang/Yin/Serenity reasoning',   category: 'intel' },
  { key: 'constellation', displayName: 'Constellation',  color: TOPIC_COLORS.RED,    description: 'Constellation reasoning tree & Helix activity', category: 'intel' },
  { key: 'consciousness', displayName: 'Consciousness',  color: TOPIC_COLORS.RED,    description: 'Subconscious observations & anomalies', category: 'intel' },
  { key: 'memoryDreams',  displayName: 'Memory & Dreams', color: TOPIC_COLORS.GREEN, description: 'Memory queries, archive, dream cycles', category: 'intel' },
  { key: 'adaptive',      displayName: 'Adaptive',       color: TOPIC_COLORS.YELLOW, description: 'Optimizer, reflex, smart rules, improvement', category: 'intel' },
  { key: 'heart',         displayName: 'Heart',          color: TOPIC_COLORS.ROSE,   description: 'Heartbeat & delivery',                 category: 'intel' },

  // Operational / system
  { key: 'system',     displayName: 'System',         color: TOPIC_COLORS.RED,    description: 'Errors, self-healing, trust, permissions', category: 'ops' },
  { key: 'budget',     displayName: 'Budget',         color: TOPIC_COLORS.RED,    description: 'Provider & team budget alerts',            category: 'ops' },
  { key: 'tools',      displayName: 'Tools',          color: TOPIC_COLORS.BLUE,   description: 'Tool registration & execution lifecycle', category: 'ops' },

  // Raw feeds
  { key: 'llmCalls',   displayName: 'LLM Calls',     color: TOPIC_COLORS.BLUE,   description: 'Raw provider request feed',               category: 'ops' },

  // Shared workspaces
  { key: 'blackboard', displayName: 'Blackboard',     color: TOPIC_COLORS.GREEN,  description: 'Global & session blackboard updates',     category: 'ops' },

  // Timeline
  { key: 'timeStore',  displayName: 'TimeStore',      color: TOPIC_COLORS.BLUE,   description: 'Timeline store ingestion & retention',     category: 'ops' },

  // User-facing
  { key: 'sessions',   displayName: 'Sessions',       color: TOPIC_COLORS.YELLOW, description: 'User session lifecycle events',           category: 'user' },
]

/** Map of topic key → definition for fast lookup */
export const TOPIC_MAP = new Map(TOPIC_DEFINITIONS.map(t => [t.key, t]))

// TopicManager

export class TopicManager {
  private readonly client: TelegramClient
  private readonly chatId: number
  private readonly logger: ILogger
  private readonly persistPath: string

  /** topic key → thread_id */
  private readonly topicIds = new Map<string, number>()

  constructor(client: TelegramClient, chatId: number, logger: ILogger) {
    this.client = client
    this.chatId = chatId
    this.logger = logger
    this.persistPath = join(homedir(), '.cassicore', 'data', 'cognitive-feed-topics.json')
  }

  /**
   * Ensure all enabled topics exist in the supergroup.
   * Loads persisted IDs from config, creates missing topics.
   */
  async ensureTopics(enabledTopics: Record<string, boolean>): Promise<void> {
    // Load persisted topic IDs from file
    await this.loadPersistedIds()

    for (const def of TOPIC_DEFINITIONS) {
      if (!enabledTopics[def.key]) continue

      // Skip if we already have a valid ID
      if (this.topicIds.has(def.key)) {
        this.logger.debug(`[topic-manager] Topic '${def.displayName}' already tracked (threadId=${this.topicIds.get(def.key)})`)
        continue
      }

      // Create the topic
      const topic = await this.client.createForumTopic(this.chatId, def.displayName, def.color)
      if (topic) {
        this.topicIds.set(def.key, topic.message_thread_id)
        this.logger.info(`[topic-manager] Created topic '${def.displayName}' (threadId=${topic.message_thread_id})`)
      } else {
        this.logger.warn(`[topic-manager] Failed to create topic '${def.displayName}'`)
      }
    }

    // Persist IDs to file for next restart
    await this.persistIds()

    this.logger.info(`[topic-manager] Topics ready: ${this.topicIds.size} active`)
  }

  /**
   * Get the thread_id for a topic key.
   * Returns undefined if the topic doesn't exist or isn't enabled.
   */
  getThreadId(topicKey: string): number | undefined {
    return this.topicIds.get(topicKey)
  }

  /**
   * Get all active topic key → threadId mappings.
   */
  getAllTopicIds(): ReadonlyMap<string, number> {
    return this.topicIds
  }

  /**
   * Resolve a thread_id back to its topic key.
   */
  getTopicKeyByThreadId(threadId: number): string | undefined {
    for (const [key, id] of this.topicIds) {
      if (id === threadId) return key
    }
    return undefined
  }

  /**
   * Get the topic definition for a key.
   */
  getDefinition(topicKey: string): TopicDefinition | undefined {
    return TOPIC_MAP.get(topicKey)
  }


  private async loadPersistedIds(): Promise<void> {
    try {
      const raw = await readFile(this.persistPath, 'utf-8')
      const stored = JSON.parse(raw) as Record<string, number>
      if (stored && typeof stored === 'object') {
        for (const [key, id] of Object.entries(stored)) {
          if (typeof id === 'number' && id > 0) {
            this.topicIds.set(key, id)
          }
        }
        this.logger.debug(`[topic-manager] Loaded ${this.topicIds.size} persisted topic IDs`)
      }
    } catch {
      // File doesn't exist yet — that's fine on first run
    }
  }

  private async persistIds(): Promise<void> {
    try {
      const ids: Record<string, number> = {}
      for (const [key, id] of this.topicIds) {
        ids[key] = id
      }
      // Ensure data directory exists
      await mkdir(join(homedir(), '.cassicore', 'data'), { recursive: true })
      await writeFile(this.persistPath, JSON.stringify(ids, null, 2), 'utf-8')
      this.logger.debug(`[topic-manager] Persisted ${Object.keys(ids).length} topic IDs`)
    } catch (err) {
      this.logger.warn(`[topic-manager] Failed to persist topic IDs: ${String(err)}`)
    }
  }
}
