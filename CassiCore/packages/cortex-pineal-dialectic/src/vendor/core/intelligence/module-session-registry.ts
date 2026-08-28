/**
 * VENDORED — faithful type surface of `core/intelligence/module-session-registry.ts`.
 * Consumed by @cassicore/cortex-pineal-dialectic (dialectic/*) as
 * `ModuleSessionRegistry` (type-only).
 *
 * Self-contained stub. The class is a structural SUPERSET of the
 * `ModuleSessionRegistry` vendored by `@cassicore/foundation` (declaring
 * `getOrCreate`/`getSessionId` for `BaseCognitiveModule.setModuleRegistry`), so
 * it unifies with base-module typing where a dialectic class extends it.
 * Re-point to `@cassicore/workspace` when that package lands (P5 repoint log).
 */

/** A persistent debug session (matches foundation's vendored type shape). */
export interface ModuleSession {
  key: string
}

export interface CompactionPolicy {
  hotWindowTurns: number
  compactionThreshold: number
  maxSummaryEras: number
  archiveCompacted: boolean
  importanceKeywords: string[]
}

export interface ModuleRegistration {
  moduleKey: string
  displayName: string
  topicKey: string
  sessionId: string
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
