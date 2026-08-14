/**
 * ThoughtObserver — extracts cognitive signals from the LLM's thinking stream.
 *
 * The thinking stream is generated as part of the free tool loop (zero additional
 * requests on request-based billing). This module passively observes thinking
 * chunks in real-time and performs deeper batch analysis post-turn, routing
 * extracted signals to the InjectionAggregator and Context Manager.
 *
 * Signal types extracted:
 * - edge_case:    corner cases, boundary conditions, failure modes
 * - assumption:   implicit assumptions in reasoning
 * - tension:      conflicting requirements or contradictions
 * - gap:          missing handling, overlooked scenarios
 * - convergence:  independent agreement, confirmed patterns
 * - insight:      key realizations, root cause identifications
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
// REMOVED: InjectionAggregator import — deprecated.
import type { CognitiveBridge } from './cognitive-bridge.js'


export interface CognitiveSignal {
  kind: SignalKind
  text: string
  confidence: number
}

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

// Each rule maps a regex pattern to a signal kind + base confidence.
// Patterns are applied to individual sentences extracted from the thinking stream.

interface PatternRule {
  /** Regex tested against normalized (lowercased, trimmed) sentences */
  pattern: RegExp
  kind: SignalKind
  /** Base confidence before modifiers (0.0–1.0) */
  baseConfidence: number
}

const PATTERN_RULES: PatternRule[] = [
  { pattern: /\bedge\s+case\b/i,                  kind: 'edge_case',   baseConfidence: 0.85 },
  { pattern: /\bcorner\s+case\b/i,                kind: 'edge_case',   baseConfidence: 0.85 },
  { pattern: /\bwhat\s+if\b.*\b(fail|break|crash|overflow|empty|null|undefined|missing)\b/i, kind: 'edge_case', baseConfidence: 0.75 },
  { pattern: /\bwhat\s+about\b.*\b(empty|null|zero|negative|large|concurrent)\b/i, kind: 'edge_case', baseConfidence: 0.70 },
  { pattern: /\bmight\s+(fail|break|crash)\s+when\b/i, kind: 'edge_case', baseConfidence: 0.80 },
  { pattern: /\bbreaks?\s+if\b/i,                 kind: 'edge_case',   baseConfidence: 0.75 },
  { pattern: /\bdoesn'?t\s+handle\s+(the\s+case|when|if)\b/i, kind: 'edge_case', baseConfidence: 0.80 },
  { pattern: /\bboundary\s+(condition|case|value)\b/i, kind: 'edge_case', baseConfidence: 0.80 },
  { pattern: /\boff[- ]by[- ]one\b/i,             kind: 'edge_case',   baseConfidence: 0.85 },
  { pattern: /\brace\s+condition\b/i,              kind: 'edge_case',   baseConfidence: 0.85 },

  { pattern: /\bi('m| am)\s+assuming\b/i,          kind: 'assumption',  baseConfidence: 0.80 },
  { pattern: /\bthis\s+assumes?\b/i,               kind: 'assumption',  baseConfidence: 0.80 },
  { pattern: /\bpresum(es?|ing|ably)\b/i,          kind: 'assumption',  baseConfidence: 0.70 },
  { pattern: /\bpresuppos(es?|ing)\b/i,            kind: 'assumption',  baseConfidence: 0.75 },
  { pattern: /\brelies?\s+on\s+the\s+assumption\b/i, kind: 'assumption', baseConfidence: 0.80 },
  { pattern: /\bassum(e|ing)\s+(that|here|single|no)\b/i, kind: 'assumption', baseConfidence: 0.75 },
  { pattern: /\bimplicitly\s+(assum|expect|requir)/i, kind: 'assumption', baseConfidence: 0.80 },

  { pattern: /\bcontradicts?\b/i,                  kind: 'tension',     baseConfidence: 0.80 },
  { pattern: /\btension\s+between\b/i,             kind: 'tension',     baseConfidence: 0.85 },
  { pattern: /\bon\s+the\s+other\s+hand\b/i,       kind: 'tension',     baseConfidence: 0.65 },
  { pattern: /\bhowever\b.*\bbut\b/i,              kind: 'tension',     baseConfidence: 0.60 },
  { pattern: /\bconflicting\s+(requirements?|goals?|needs?)\b/i, kind: 'tension', baseConfidence: 0.80 },
  { pattern: /\btrade-?off\s+between\b/i,          kind: 'tension',     baseConfidence: 0.75 },
  { pattern: /\bmutually\s+exclusive\b/i,          kind: 'tension',     baseConfidence: 0.85 },

  { pattern: /\bdoesn'?t\s+handle\b/i,             kind: 'gap',         baseConfidence: 0.75 },
  { pattern: /\bno\s+(coverage|handling|validation)\s+(for|of)\b/i, kind: 'gap', baseConfidence: 0.80 },
  { pattern: /\boverlooked\b/i,                    kind: 'gap',         baseConfidence: 0.70 },
  { pattern: /\bmissing\b.*\b(handling|check|validation|error|case)\b/i, kind: 'gap', baseConfidence: 0.75 },
  { pattern: /\bforgot\s+to\b/i,                   kind: 'gap',         baseConfidence: 0.80 },
  { pattern: /\bnot\s+(yet\s+)?(implemented|handled|covered)\b/i, kind: 'gap', baseConfidence: 0.70 },

  { pattern: /\bconfirms?\s+(that|my|the|this)\b/i, kind: 'convergence', baseConfidence: 0.70 },
  { pattern: /\baligns?\s+with\b/i,                kind: 'convergence', baseConfidence: 0.70 },
  { pattern: /\bconsistent\s+with\b/i,             kind: 'convergence', baseConfidence: 0.70 },
  { pattern: /\breinforces?\s+(the|my|this)\b/i,   kind: 'convergence', baseConfidence: 0.70 },
  { pattern: /\bindependent(ly)?\s+(confirms?|agrees?|validates?)\b/i, kind: 'convergence', baseConfidence: 0.80 },

  { pattern: /\bthe\s+(real|root|underlying|actual)\s+(issue|cause|problem)\s+(is|here)\b/i, kind: 'insight', baseConfidence: 0.80 },
  { pattern: /\bkey\s+(insight|observation|realization)\b/i, kind: 'insight', baseConfidence: 0.80 },
  { pattern: /\binteresting\s+pattern\b/i,         kind: 'insight',     baseConfidence: 0.70 },
  { pattern: /\bthis\s+(means|implies|suggests)\s+that\b/i, kind: 'insight', baseConfidence: 0.60 },
  { pattern: /\bfundamental(ly)?\b.*\b(wrong|flawed|broken|misunderst)/i, kind: 'insight', baseConfidence: 0.80 },

  // Intent detection patterns
  { pattern: /\b(i need to|let me|i should|i want to)\s+(find|check|look at|search|read|understand|examine)\b/i, kind: 'search_intent', baseConfidence: 0.80 },
  { pattern: /\b(before\s+(calling\s+)?enrich|before\s+i\s+(search|look|check))\b/i, kind: 'context_intent', baseConfidence: 0.90 },
  { pattern: /\b(what|who|where|how)\s+(calls|uses|imports|extends|implements|references)\b/i, kind: 'code_intent', baseConfidence: 0.85 },
  { pattern: /\b(callers?\s+of|callees?\s+of|dependencies?\s+of|dependents?\s+of)\b/i, kind: 'code_intent', baseConfidence: 0.85 },
  { pattern: /\b(past|previous|earlier|before|last\s+time)\s+(decision|conversation|approach|discussion|session)\b/i, kind: 'memory_intent', baseConfidence: 0.80 },
  { pattern: /\b(i\s+recall|i\s+remember|didn't\s+we|wasn't\s+there)\b/i, kind: 'memory_intent', baseConfidence: 0.75 },
  { pattern: /\b(architecture|execution\s+flow|call\s+chain|blast\s+radius)\s+(of|for)\b/i, kind: 'code_intent', baseConfidence: 0.85 },
  { pattern: /\b(relevant\s+(files?|modules?|functions?|classes?))\b/i, kind: 'search_intent', baseConfidence: 0.75 },
  { pattern: /\b(implementation\s+of|source\s+(code\s+)?(of|for))\b/i, kind: 'code_intent', baseConfidence: 0.80 },
]

// Applied after pattern matching to adjust confidence based on emphasis signals.

function applyConfidenceModifiers(text: string, baseConfidence: number): number {
  let confidence = baseConfidence

  // Exclamation marks → slight boost (emphasis)
  if (/!/.test(text)) confidence = Math.min(1.0, confidence + 0.05)

  // ALL CAPS words (3+ chars) → emphasis boost
  if (/\b[A-Z]{3,}\b/.test(text)) confidence = Math.min(1.0, confidence + 0.05)

  // Hedging language → reduce confidence
  if (/\b(maybe|perhaps|possibly|might|could be)\b/i.test(text)) confidence = Math.max(0.3, confidence - 0.15)

  // Questioning form → reduce confidence (speculative)
  if (/\?$/.test(text.trim())) confidence = Math.max(0.3, confidence - 0.10)

  return Math.round(confidence * 100) / 100
}

// Splits a text block into sentences for individual analysis.

function splitSentences(text: string): string[] {
  // Split on sentence boundaries, keeping reasonable chunks
  return text
    .split(/(?<=[.!?])\s+|(?:\r?\n){2,}/)
    .map(s => s.trim())
    .filter(s => s.length > 15 && s.length < 500) // Skip trivially short/long fragments
}


export interface ThoughtObserverOpts {
  /** Enable real-time stream processing (default: true) */
  realtimeEnabled?: boolean
  /** Enable post-turn batch analysis (default: true) */
  postTurnEnabled?: boolean
  /** Minimum confidence to emit a signal (default: 0.6) */
  minConfidence?: number
  /** Maximum signals per turn to prevent noise (default: 8) */
  maxSignalsPerTurn?: number
  /** Maximum chars of thinking to buffer per session (default: 50000) */
  maxBufferChars?: number
}

export interface ThoughtObserver {
  name: string
  priority: number
  /** Wire the event bus for listening to thinking/turn events */
  onEventBus(bus: IEventBus): void
  /** REMOVED: setInjectionAggregator — InjectionAggregator deleted. */
  /** Wire the context manager for global context enrichment */
  setContextManager(cm: { mergeCognitiveSignals(sessionId: string, signals: Array<{ kind: string; text: string; confidence: number; extractedAt?: number }>): Promise<void> }): void
  /** Wire the cognitive bridge for cross-session signal routing */
  setCognitiveBridge(bridge: CognitiveBridge): void
  /** Get signals extracted in the current/last turn for a session (non-destructive) */
  peekSignals(sessionId: string): CognitiveSignal[]
  /** Get and clear signals for a session */
  consumeSignals(sessionId: string): CognitiveSignal[]
  /** Get recent signals for trace population (returns TraceCognitiveSignal format) */
  getRecentSignals(sessionId: string): import('@cassicore/foundation').TraceCognitiveSignal[]
  /**
   * Store previously extracted signals for a session and route them through the
   * cognitive pipeline.
   */
  storeSignals(sessionId: string, signals: CognitiveSignal[]): Promise<void>
  /**
   * Extract cognitive signals from arbitrary text (not just thinking stream).
   * Used by drone swarm to extract signals from drone outputs, and by
   * cognitive probes to analyze investigation results. Pure extraction —
   * does NOT route signals or update session state.
   */
  extractSignalsFromText(text: string): CognitiveSignal[]
  /** Get stats for diagnostics */
  getStats(): ThoughtObserverStats
  /** Clean up resources */
  cleanup(): void
}

export interface ThoughtObserverStats {
  totalSignalsExtracted: number
  signalsByKind: Record<string, number>
  sessionsTracked: number
  totalCharsProcessed: number
}

/**
 * @dep callers: cognitive-drones.test.ts (tests/cognitive-drones.test.ts), think-stream.test.ts (tests/think-stream.test.ts), thought-observer.test.ts (tests/thought-observer.test.ts), createIntelligence (core/intelligence/index.ts)
 * @dep module: Intelligence
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

export function createThoughtObserver(logger: ILogger, opts?: ThoughtObserverOpts): ThoughtObserver {
  const name = 'thought-observer'
  const priority = 82  // Between Context Manager (85) and Trust Ledger (80)

  const config = {
    realtimeEnabled: opts?.realtimeEnabled ?? true,
    postTurnEnabled: opts?.postTurnEnabled ?? true,
    minConfidence: opts?.minConfidence ?? 0.6,
    maxSignalsPerTurn: opts?.maxSignalsPerTurn ?? 8,
    maxBufferChars: opts?.maxBufferChars ?? 50_000,
  }

  let _bus: IEventBus | undefined
  // REMOVED: _injectionAggregator — InjectionAggregator deleted.
  let _contextManager: { mergeCognitiveSignals(sessionId: string, signals: Array<{ kind: string; text: string; confidence: number; extractedAt?: number }>): Promise<void> } | undefined
  let _cognitiveBridge: CognitiveBridge | undefined
  const _unsubscribers: Array<() => void> = []


  /** Accumulated thinking text per session (buffered for post-turn analysis) */
  const _thinkingBuffers = new Map<string, string>()

  /** Signals extracted per session (current turn) */
  const _signalStore = new Map<string, CognitiveSignal[]>()

  /** Dedup set per session to avoid emitting identical signals within a turn */
  const _dedupKeys = new Map<string, Set<string>>()

  let _totalSignals = 0
  let _totalChars = 0
  const _kindCounts: Record<string, number> = {}


  function dedupKey(signal: CognitiveSignal): string {
    // Normalize: kind + first 80 chars of text lowercased
    return `${signal.kind}::${signal.text.toLowerCase().slice(0, 80)}`
  }

  function isDuplicate(sessionId: string, signal: CognitiveSignal): boolean {
    const key = dedupKey(signal)
    const existing = _dedupKeys.get(sessionId)
    if (existing?.has(key)) return true
    if (!existing) _dedupKeys.set(sessionId, new Set())
    _dedupKeys.get(sessionId)!.add(key)
    return false
  }


  function extractSignals(text: string): CognitiveSignal[] {
    const signals: CognitiveSignal[] = []
    const sentences = splitSentences(text)

    for (const sentence of sentences) {
      for (const rule of PATTERN_RULES) {
        if (rule.pattern.test(sentence)) {
          const confidence = applyConfidenceModifiers(sentence, rule.baseConfidence)
          if (confidence >= config.minConfidence) {
            signals.push({
              kind: rule.kind,
              text: sentence.slice(0, 200), // Cap text length
              confidence,
            })
            break // One signal per sentence (highest-priority rule wins)
          }
        }
      }
    }

    return signals
  }


  function routeSignals(sessionId: string, signals: CognitiveSignal[], source: 'realtime' | 'post-turn' | 'manual'): CognitiveSignal[] {
    if (signals.length === 0) return []

    // Dedup and cap
    const currentCount = _signalStore.get(sessionId)?.length ?? 0
    const budget = config.maxSignalsPerTurn - currentCount
    if (budget <= 0) return []

    const novel = signals.filter(s => !isDuplicate(sessionId, s)).slice(0, budget)
    if (novel.length === 0) return []

    // Store for peek/consume access
    if (!_signalStore.has(sessionId)) _signalStore.set(sessionId, [])
    _signalStore.get(sessionId)!.push(...novel)

    // REMOVED: injectionAggregator routing — InjectionAggregator deleted.

    // Route through CognitiveBridge for cross-session signal sharing.
    // If this session is linked to peers, signals flow to them automatically.
    if (_cognitiveBridge) {
      _cognitiveBridge.routeSignals(sessionId, novel)
    }

    // Update stats
    _totalSignals += novel.length
    for (const s of novel) {
      _kindCounts[s.kind] = (_kindCounts[s.kind] ?? 0) + 1
    }

    // Emit event
    _bus?.emit?.({
      type: 'thinking:signal-extracted',
      sessionId,
      signals: novel.map(s => ({ kind: s.kind, text: s.text, confidence: s.confidence })),
      source,
      thinkingCharsProcessed: _thinkingBuffers.get(sessionId)?.length ?? 0,
      timestamp: new Date(),
    } as any)

    // Emit intent-detected events for intent signals
    for (const signal of novel) {
      if (signal.kind.endsWith('_intent')) {
        _bus?.emit?.({
          type: 'worker:message',
          pluginId: 'thought-observer',
          payload: {
            type: 'thinking:intent-detected',
            sessionId,
            intent: {
              kind: signal.kind,
              text: signal.text,
              confidence: signal.confidence,
              detectedAt: Date.now(),
            },
          },
        } as any)

        // Structured observability logging
        logger.info('intent-detected', {
          sessionId,
          kind: signal.kind,
          confidence: signal.confidence,
          patternIndex: PATTERN_RULES.findIndex(r => r.kind === signal.kind && r.pattern.test(signal.text)),
          sentenceLength: signal.text.length,
          label: `intent:${signal.kind}`,
        })
      }
    }

    logger.info(`Extracted ${novel.length} signal(s) from ${source}`, {
      sessionId: sessionId.slice(-8),
      kinds: novel.map(s => s.kind).join(', '),
    })

    return novel
  }

  // Processes thinking chunks as they arrive via worker:message events.

  function onThinkingChunk(sessionId: string, text: string): void {
    if (!config.realtimeEnabled) return
    if (!text || text.length < 20) return // Skip trivially small chunks

    // Accumulate in buffer (capped)
    const existing = _thinkingBuffers.get(sessionId) ?? ''
    const combined = existing + text
    _thinkingBuffers.set(sessionId, combined.length > config.maxBufferChars
      ? combined.slice(-config.maxBufferChars)
      : combined)

    _totalChars += text.length

    // Extract from the new chunk (not the entire buffer, to avoid re-processing)
    const signals = extractSignals(text)
    if (signals.length > 0) {
      routeSignals(sessionId, signals, 'realtime')
    }
  }

  // On turn:end, analyze the full thinking buffer for patterns that span
  // multiple sentences (cross-reference, repeated themes).

  function onTurnEnd(sessionId: string): void {
    if (!config.postTurnEnabled) return

    const buffer = _thinkingBuffers.get(sessionId)
    if (!buffer || buffer.length < 100) {
      clearTurnState(sessionId)
      return
    }

    // Run full extraction on the complete buffer.
    // The dedup set ensures we don't re-emit signals already found in real-time.
    const signals = extractSignals(buffer)
    if (signals.length > 0) {
      routeSignals(sessionId, signals, 'post-turn')
    }

    // Persist high-confidence signals to context manager's global context
    const highConfidence = (_signalStore.get(sessionId) ?? []).filter(s => s.confidence >= 0.7)
    if (highConfidence.length > 0 && _contextManager) {
      void persistToContextManager(sessionId, highConfidence).catch(err => {
        logger.debug('Failed to persist signals to context manager', {
          error: String(err),
        })
      })
    }

    // Clear turn-scoped state (buffer + dedup). Signal store persists until consumed.
    clearTurnState(sessionId)
  }

  async function persistToContextManager(sessionId: string, signals: CognitiveSignal[]): Promise<void> {
    if (!_contextManager) return

    try {
      const MAX_PERSISTED_SIGNALS = 12
      const formatted = signals.slice(0, MAX_PERSISTED_SIGNALS).map(s => ({
        kind: s.kind,
        text: s.text.slice(0, 150),
        confidence: s.confidence,
        extractedAt: Date.now(),
      }))

      await _contextManager.mergeCognitiveSignals(sessionId, formatted)
    } catch (err) {
      logger.debug('persistToContextManager failed', { error: String(err) })
    }
  }

  async function storeSignals(sessionId: string, signals: CognitiveSignal[]): Promise<void> {
    if (!sessionId || signals.length === 0) return

    const stored = routeSignals(sessionId, signals, 'manual')
    if (stored.length === 0) return

    const highConfidence = stored.filter(signal => signal.confidence >= 0.7)
    if (highConfidence.length > 0 && _contextManager) {
      await persistToContextManager(sessionId, highConfidence)
    }
  }

  function clearTurnState(sessionId: string): void {
    _thinkingBuffers.delete(sessionId)
    _dedupKeys.delete(sessionId)
  }


  function onEventBus(bus: IEventBus): void {
    _bus = bus

    // Listen for thinking chunks via worker:message
    const unsub1 = bus.on('worker:message' as any, (e: any) => {
      try {
        const payload = e?.payload
        if (!payload) return
        if (payload.type !== 'turn:thinking') return
        const sessionId = payload.sessionId ?? e?.pluginId
        const text = payload.content ?? payload.text ?? payload.token ?? ''
        if (sessionId && text) {
          onThinkingChunk(sessionId, text)
        }
      } catch (err) {
        logger.debug('worker:message handler error', { error: String(err) })
      }
    })
    if (unsub1) _unsubscribers.push(unsub1)

    // Listen for turn:end to trigger post-turn batch analysis
    const unsub2 = bus.on('turn:end', (e: any) => {
      try {
        const sessionId = (e as any)?.sessionId
        if (sessionId) onTurnEnd(sessionId)
      } catch (err) {
        logger.debug('turn:end handler error', { error: String(err) })
      }
    })
    if (unsub2) _unsubscribers.push(unsub2)

    // Clean up on session end
    const unsub3 = bus.on('session:ended' as any, (e: any) => {
      const sid = (e as any)?.sessionId
      if (sid) {
        clearTurnState(sid)
        _signalStore.delete(sid)
      }
    })
    if (unsub3) _unsubscribers.push(unsub3)

    logger.info('Wired to event bus')
  }

  // REMOVED: setInjectionAggregator — InjectionAggregator deleted.

  function setContextManager(cm: { mergeCognitiveSignals(sessionId: string, signals: Array<{ kind: string; text: string; confidence: number; extractedAt?: number }>): Promise<void> }): void {
    _contextManager = cm
    logger.info('Wired to context manager')
  }

  function setCognitiveBridge(bridge: CognitiveBridge): void {
    _cognitiveBridge = bridge
    logger.info('Wired to cognitive bridge')
  }

  function peekSignals(sessionId: string): CognitiveSignal[] {
    return [...(_signalStore.get(sessionId) ?? [])]
  }

  function consumeSignals(sessionId: string): CognitiveSignal[] {
    const signals = _signalStore.get(sessionId) ?? []
    _signalStore.delete(sessionId)
    return signals
  }

  function getRecentSignals(sessionId: string): import('@cassicore/foundation').TraceCognitiveSignal[] {
    const signals = _signalStore.get(sessionId) ?? []
    // Return in TraceCognitiveSignal format (includes source field)
    return signals.map(s => ({
      source: 'thought-observer',
      kind: s.kind,
      confidence: s.confidence,
      text: s.text,
    }))
  }

  function getStats(): ThoughtObserverStats {
    return {
      totalSignalsExtracted: _totalSignals,
      signalsByKind: { ..._kindCounts },
      sessionsTracked: _signalStore.size,
      totalCharsProcessed: _totalChars,
    }
  }

  function cleanup(): void {
    for (const unsub of _unsubscribers) {
      try { unsub() } catch { /* best-effort */ }
    }
    _unsubscribers.length = 0
    _thinkingBuffers.clear()
    _signalStore.clear()
    _dedupKeys.clear()
    logger.info('Cleaned up')
  }

  return {
    name,
    priority,
    onEventBus,
    setContextManager,
    setCognitiveBridge,
    peekSignals,
    consumeSignals,
    getRecentSignals,
    storeSignals,
    extractSignalsFromText: extractSignals,
    getStats,
    cleanup,
  }
}
