/**
 * VENDORED TYPE STUB — mirrors `core/intelligence/module-session-registry.js`
 * `ModuleSessionRegistry` surface consumed by subconscious (`getSessionId`,
 * `appendTurn` on an injected registry). Re-point to its owning package at
 * P7 (§P5b table §A2.2 / Open Flag 3). Type-only — no runtime impl reproduced.
 */

/**
 * Faithful `ModuleSessionRegistry` surface — the methods subconscious calls on
 * an injected instance, plus an open index signature for the broader class.
 */
export interface ModuleSessionRegistry {
  getSessionId(moduleKey: string): string | undefined
  getOrCreate(moduleKey: string): { sessionId: string; [key: string]: unknown }
  appendTurn(moduleKey: string, role: 'user' | 'assistant', content: string): void
  [key: string]: unknown
}
