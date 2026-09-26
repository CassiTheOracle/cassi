/**
 * VENDOR TYPE STUB — `core/intelligence/thought-observer.ts`.
 *
 * Type-placeholder for the cognitive-signal observer surface consumed by the
 * tools (cognitive-tools.ts, collect-thoughts.ts). Tools hold it as a typed
 * dep (`deps.thoughtObserver?.extractSignalsFromText/storeSignals`) and tests
 * mock it. Owned by the P5 brain package; re-pointed when it lands (Open-6).
 */

/** A cognitive signal extracted from the LLM's thinking stream. */
export interface CognitiveSignal {
  kind: SignalKind
  text: string
  confidence: number
}

/** The kinds of cognitive signals that can be extracted. */
export type SignalKind =
  | 'edge_case'
  | 'assumption'
  | 'tension'
  | 'gap'
  | 'convergence'
  | 'insight'
  | 'memory_note'
  | 'search_intent'
  | 'code_intent'
  | 'memory_intent'
  | 'context_intent'

/** Observer configuration. */
export interface ThoughtObserverOpts {
  realtimeEnabled?: boolean
  postTurnEnabled?: boolean
  minConfidence?: number
  maxSignalsPerTurn?: number
  maxBufferChars?: number
}

/** Observer diagnostics. */
export interface ThoughtObserverStats {
  totalSignalsExtracted: number
  signalsByKind: Record<string, number>
  sessionsTracked: number
}

/**
 * Cognitive-signal observer wired to the event bus and the cognitive bridge.
 * Tools consume only `extractSignalsFromText` + `storeSignals` (rest structural).
 */
export interface ThoughtObserver {
  name: string
  priority: number
  onEventBus(bus: unknown): void
  setContextManager(cm: unknown): void
  setCognitiveBridge(bridge: unknown): void
  peekSignals(sessionId: string): CognitiveSignal[]
  consumeSignals(sessionId: string): CognitiveSignal[]
  getRecentSignals(sessionId: string): unknown[]
  storeSignals(sessionId: string, signals: CognitiveSignal[]): Promise<void>
  extractSignalsFromText(text: string): CognitiveSignal[]
  getStats(): ThoughtObserverStats
  cleanup(): void
}
