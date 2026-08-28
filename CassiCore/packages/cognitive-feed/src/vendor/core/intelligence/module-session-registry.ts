/**
 * VENDORED — faithful type surface of `core/intelligence/module-session-registry.ts`.
 * Consumed by @cassicore/cognitive-feed module-chat-handler.ts as
 * `ModuleSessionRegistry`, `ModuleRegistration` (type-only).
 *
 * Self-contained stub: declares the module registration surface and the registry
 * class type used by the consumer. The class is a structural SUPERSET of the
 * `ModuleSessionRegistry` vendored by `@cassicore/foundation` (which declares
 * `getOrCreate` / `getSessionId` for `BaseCognitiveModule.setModuleRegistry`),
 * so cognitive-feed's registry type unifies with the base-module field.
 *
 * Re-point to `@cassicore/workspace` when that package lands (P5 repoint log).
 */

/** A persistent debug session (matches foundation's vendored type shape). */
export interface ModuleSession {
  key: string
}

export interface CompactionPolicy {
  /** Number of most-recent turns to always keep verbatim */
  hotWindowTurns: number
  /** Total turn count that triggers compaction */
  compactionThreshold: number
  /** Maximum era summary messages to retain */
  maxSummaryEras: number
  /** Whether to archive compacted turns to the memory archive */
  archiveCompacted: boolean
  /** Keywords that raise a turn's importance classification */
  importanceKeywords: string[]
}

export interface ModuleRegistration {
  /** Stable key used in session IDs, e.g. 'thinker', 'lumen' */
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

/** Registry of module → session mappings (type surface). */
export declare class ModuleSessionRegistry {
  /** Create/load the session for a module key (persisted to disk). */
  getOrCreate(moduleKey: string): ModuleSession
  /** Get the session id for a module key, if one is registered. */
  getSessionId(moduleKey: string): string | undefined
  /** Get a module's registration, or undefined. */
  getRegistration(moduleKey: string): ModuleRegistration | undefined
  /** Module keys registered to a topic key. */
  getModulesForTopic(topicKey: string): string[]
  /** The most recently active module key for a topic, if any. */
  getMostRecentModuleForTopic(topicKey: string): string | undefined
}
