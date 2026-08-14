/**
 * VENDOR TYPE STUB — `core/intelligence/cognitive-bridge.ts`.
 *
 * Type-placeholder for the cross-session cognitive bridge surface consumed by
 * the tools (cognitive-tools.ts, collect-thoughts.ts, peer-coordination.ts).
 * Tools hold it as a typed dep and call `getFusedSignals`/`getResonancePatterns`/
 * `routeSignals`/`getLinkedPeers`/`isLinked`/`linkSessions`; tests mock it.
 * Owned by the P5 brain package; re-pointed when it lands (Open-6).
 */

import type { CognitiveSignal } from './thought-observer.js'

/** How sessions become linked. */
export type LinkMode = 'auto-project' | 'spawn-linked' | 'tool-initiated'

/** A link between two sessions. */
export interface SessionLink {
  sessionIdA: string
  sessionIdB: string
  mode: LinkMode
  projectedAt: number
}

/** Shape of a cognitive signal as referenced by a resonance pattern. */
export interface CognitiveSignalRef {
  kind: string
  text: string
  confidence: number
}

/** A cross-session resonance pattern between two cognitive signals. */
export interface ResonancePattern {
  kind: 'resonance' | 'tension'
  signalA: { sessionId: string; signal: CognitiveSignalRef }
  signalB: { sessionId: string; signal: CognitiveSignalRef }
  similarity: number
  amplifiedConfidence: number
  detectedAt: number
}

/** Bridge diagnostics. */
export interface CognitiveBridgeStats {
  trackedSessionPairs: number
  activeResonances: number
  signalRouteCount: number
}

/**
 * Cross-session cognitive bridge: fuses/shares cognitive signals and tracks
 * resonance patterns across linked sessions.
 */
export interface CognitiveBridge {
  getFusedSignals(sessionId: string): CognitiveSignal[]
  getResonancePatterns(sessionId: string): ResonancePattern[]
  routeSignals(sessionId: string, signals: CognitiveSignal[]): void
  getLinkedPeers(sessionId: string): string[]
  isLinked(sessionIdA: string, sessionIdB: string): boolean
  linkSessions(sessionIdA: string, sessionIdB: string, mode?: LinkMode): void
  getStats(): CognitiveBridgeStats
}
