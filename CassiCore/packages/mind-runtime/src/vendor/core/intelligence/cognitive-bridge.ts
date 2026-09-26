/**
 * CognitiveBridge — links sessions into a shared cognitive space.
 *
 * Instead of discrete messages between peers, the bridge creates a continuous
 * bidirectional flow of cognitive signals between linked sessions. When Session
 * A's ThoughtObserver extracts an edge case, it automatically appears in Session
 * B's context injections — as if B thought of it itself.
 *
 * Three linking modes:
 *   1. Auto-link by project — sessions sharing projectPath are linked on creation
 *   2. Spawn-linked — parent and child sessions auto-link on subagent:spawned
 *   3. Tool-initiated — _link_brain tool establishes explicit link
 *
 * The bridge also performs resonance detection: when two linked sessions
 * independently identify similar patterns, their confidence is amplified.
 * Opposing signals surface as tensions for conscious resolution.
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
// REMOVED: InjectionAggregator import — deprecated.
import type { CognitiveSignal, SignalKind } from './thought-observer.js'


export type LinkMode = 'auto-project' | 'spawn-linked' | 'tool-initiated'

export interface SessionLink {
  sessionA: string
  sessionB: string
  mode: LinkMode
  linkedAt: number
}

export interface ResonancePattern {
  kind: 'resonance' | 'tension'
  signalA: { sessionId: string; signal: CognitiveSignal }
  signalB: { sessionId: string; signal: CognitiveSignal }
  similarity: number
  amplifiedConfidence: number
  detectedAt: number
}

export interface CognitiveBridgeStats {
  totalLinks: number
  totalSignalsRouted: number
  totalResonancesDetected: number
  totalTensionsDetected: number
  activeSessionCount: number
}


const MAX_LINKS_PER_SESSION = 8
const MAX_FUSED_SIGNALS_PER_SESSION = 20
const MAX_RESONANCE_PATTERNS_PER_SESSION = 10
const RESONANCE_TTL_MS = 10 * 60 * 1000  // 10 minutes
const SIGNAL_ROUTE_DEBOUNCE_MS = 500
const RESONANCE_SIMILARITY_THRESHOLD = 0.55
const RESONANCE_CONFIDENCE_BOOST = 0.15


const STOP_WORDS = new Set([
  'the', 'this', 'that', 'with', 'from', 'have', 'has', 'had', 'been', 'being',
  'will', 'would', 'could', 'should', 'might', 'must', 'shall', 'can', 'may',
  'not', 'but', 'and', 'for', 'are', 'was', 'were', 'its', 'also', 'into',
  'more', 'some', 'than', 'then', 'them', 'they', 'their', 'there', 'here',
  'when', 'where', 'which', 'what', 'about', 'does', 'each', 'other',
  'very', 'just', 'need', 'needs', 'like', 'well',
])


function extractKeywords(text: string): Set<string> {
  const words = text.toLowerCase().replace(/[^a-z0-9\s_-]/g, ' ').split(/\s+/)
  const keywords = new Set<string>()
  for (const w of words) {
    if (w.length >= 3 && !STOP_WORDS.has(w)) {
      keywords.add(w)
    }
  }
  return keywords
}

function jaccardSimilarity(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 0
  let intersection = 0
  for (const word of a) {
    if (b.has(word)) intersection++
  }
  const union = a.size + b.size - intersection
  return union === 0 ? 0 : intersection / union
}

/** Signal kinds considered "opposing" for tension detection */
const OPPOSING_KINDS: Array<[SignalKind, SignalKind]> = [
  ['edge_case', 'convergence'],
  ['gap', 'convergence'],
  ['tension', 'convergence'],
  ['assumption', 'insight'],
]

function areOpposingKinds(a: SignalKind, b: SignalKind): boolean {
  return OPPOSING_KINDS.some(
    ([x, y]) => (a === x && b === y) || (a === y && b === x)
  )
}


export interface CognitiveBridge {
  name: string
  priority: number

  linkSessions(sessionA: string, sessionB: string, mode: LinkMode): boolean
  unlinkSessions(sessionA: string, sessionB: string): boolean
  isLinked(sessionA: string, sessionB: string): boolean
  getLinkedPeers(sessionId: string): Array<{ peerId: string; mode: LinkMode; linkedAt: number }>

  routeSignals(sourceSessionId: string, signals: CognitiveSignal[]): void

  getFusedSignals(sessionId: string): CognitiveSignal[]
  getResonancePatterns(sessionId: string): ResonancePattern[]

  onEventBus(bus: IEventBus): void
  // REMOVED: setInjectionAggregator — InjectionAggregator deleted.
  setSessionManager(sm: { get(id: string): any | undefined }): void

  getStats(): CognitiveBridgeStats
  cleanup(): void
}

/**
 * @dep callers: cognitive-bridge.test.ts (tests/cognitive-bridge.test.ts), cognitive-drones.test.ts (tests/cognitive-drones.test.ts), think-stream.test.ts (tests/think-stream.test.ts), createIntelligence (core/intelligence/index.ts)
 * @dep module: Intelligence
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

export function createCognitiveBridge(logger: ILogger): CognitiveBridge {
  const name = 'cognitive-bridge'
  const priority = 81  // Just below ThoughtObserver (82)

  let _bus: IEventBus | undefined
  // REMOVED: _injectionAggregator — InjectionAggregator deleted.
  let _sessionManager: { get(id: string): any | undefined } | undefined
  const _unsubscribers: Array<() => void> = []


  /** Bidirectional links: sessionId → Set of linked peer sessionIds */
  const _links = new Map<string, Map<string, { mode: LinkMode; linkedAt: number }>>()

  /** Fused signals: sessionId → signals received FROM peers (not own signals) */
  const _peerSignals = new Map<string, CognitiveSignal[]>()

  /** Resonance patterns: sessionId → detected cross-session convergences */
  const _resonance = new Map<string, ResonancePattern[]>()

  /** Recent signals per session (for resonance detection). sessionId → recent signals */
  const _recentSignals = new Map<string, Array<{ signal: CognitiveSignal; timestamp: number }>>()

  /** Debounce timers for signal routing */
  const _routeTimers = new Map<string, ReturnType<typeof setTimeout>>()
  const _routeQueues = new Map<string, CognitiveSignal[]>()

  let _totalRouted = 0
  let _totalResonances = 0
  let _totalTensions = 0


  function linkSessions(sessionA: string, sessionB: string, mode: LinkMode): boolean {
    if (sessionA === sessionB) return false

    // Check limits
    const aLinks = _links.get(sessionA)
    const bLinks = _links.get(sessionB)
    if ((aLinks?.size ?? 0) >= MAX_LINKS_PER_SESSION) {
      logger.warn('Max links reached for session', { sessionId: sessionA.slice(-8) })
      return false
    }
    if ((bLinks?.size ?? 0) >= MAX_LINKS_PER_SESSION) {
      logger.warn('Max links reached for session', { sessionId: sessionB.slice(-8) })
      return false
    }

    // Already linked?
    if (aLinks?.has(sessionB)) return true

    const now = Date.now()
    const linkInfo = { mode, linkedAt: now }

    // Bidirectional
    if (!_links.has(sessionA)) _links.set(sessionA, new Map())
    if (!_links.has(sessionB)) _links.set(sessionB, new Map())
    _links.get(sessionA)!.set(sessionB, linkInfo)
    _links.get(sessionB)!.set(sessionA, linkInfo)

    _bus?.emit?.({
      type: 'cognitive-bridge:linked' as any,
      sessionA,
      sessionB,
      mode,
      timestamp: new Date(),
    })

    logger.info('Sessions linked', {
      sessionA: sessionA.slice(-8),
      sessionB: sessionB.slice(-8),
      mode,
    })

    return true
  }

  function unlinkSessions(sessionA: string, sessionB: string): boolean {
    const aLinks = _links.get(sessionA)
    const bLinks = _links.get(sessionB)
    if (!aLinks?.has(sessionB)) return false

    aLinks.delete(sessionB)
    bLinks?.delete(sessionA)

    // Clean up empty maps
    if (aLinks.size === 0) _links.delete(sessionA)
    if (bLinks && bLinks.size === 0) _links.delete(sessionB)

    logger.info('Sessions unlinked', {
      sessionA: sessionA.slice(-8),
      sessionB: sessionB.slice(-8),
    })

    return true
  }

  function isLinked(sessionA: string, sessionB: string): boolean {
    return _links.get(sessionA)?.has(sessionB) ?? false
  }

  function getLinkedPeers(sessionId: string): Array<{ peerId: string; mode: LinkMode; linkedAt: number }> {
    const links = _links.get(sessionId)
    if (!links) return []
    return Array.from(links.entries()).map(([peerId, info]) => ({
      peerId,
      mode: info.mode,
      linkedAt: info.linkedAt,
    }))
  }


  function routeSignals(sourceSessionId: string, signals: CognitiveSignal[]): void {
    if (signals.length === 0) return
    const peers = _links.get(sourceSessionId)
    if (!peers || peers.size === 0) return

    // Accumulate in queue
    if (!_routeQueues.has(sourceSessionId)) _routeQueues.set(sourceSessionId, [])
    _routeQueues.get(sourceSessionId)!.push(...signals)

    // Debounce: batch route after 500ms of quiet
    if (_routeTimers.has(sourceSessionId)) {
      clearTimeout(_routeTimers.get(sourceSessionId)!)
    }

    _routeTimers.set(sourceSessionId, setTimeout(() => {
      flushRouteQueue(sourceSessionId)
      _routeTimers.delete(sourceSessionId)
    }, SIGNAL_ROUTE_DEBOUNCE_MS))
  }

  function flushRouteQueue(sourceSessionId: string): void {
    const queue = _routeQueues.get(sourceSessionId)
    if (!queue || queue.length === 0) return
    _routeQueues.delete(sourceSessionId)

    const peers = _links.get(sourceSessionId)
    if (!peers || peers.size === 0) return

    // Store in source's recent signals (for resonance detection by peers)
    storeRecentSignals(sourceSessionId, queue)

    for (const [peerId] of peers) {
      // Add to peer's fused signal store
      if (!_peerSignals.has(peerId)) _peerSignals.set(peerId, [])
      const peerStore = _peerSignals.get(peerId)!

      for (const signal of queue) {
        // Annotate with source
        const annotated: CognitiveSignal = {
          ...signal,
          text: signal.text, // Keep original text; source is tracked via fused store context
        }

        peerStore.push(annotated)
        _totalRouted++

        // REMOVED: injectionAggregator.queueDialecticSignal — InjectionAggregator deleted.

        // Check for resonance
        detectResonance(sourceSessionId, peerId, signal)
      }

      // Cap fused signals
      if (peerStore.length > MAX_FUSED_SIGNALS_PER_SESSION) {
        peerStore.splice(0, peerStore.length - MAX_FUSED_SIGNALS_PER_SESSION)
      }
    }

    logger.debug?.('Routed signals', {
      source: sourceSessionId.slice(-8),
      signalCount: queue.length,
      peerCount: peers.size,
    })
  }

  function storeRecentSignals(sessionId: string, signals: CognitiveSignal[]): void {
    if (!_recentSignals.has(sessionId)) _recentSignals.set(sessionId, [])
    const store = _recentSignals.get(sessionId)!
    const now = Date.now()

    for (const s of signals) {
      store.push({ signal: s, timestamp: now })
    }

    // Evict old signals
    const cutoff = now - RESONANCE_TTL_MS
    const fresh = store.filter(e => e.timestamp > cutoff)
    _recentSignals.set(sessionId, fresh.slice(-30)) // Keep last 30
  }


  function detectResonance(
    sourceSessionId: string,
    peerId: string,
    incomingSignal: CognitiveSignal,
  ): void {
    const peerRecent = _recentSignals.get(peerId)
    if (!peerRecent || peerRecent.length === 0) return

    const incomingKeywords = extractKeywords(incomingSignal.text)
    if (incomingKeywords.size === 0) return

    const now = Date.now()

    for (const entry of peerRecent) {
      const peerKeywords = extractKeywords(entry.signal.text)
      if (peerKeywords.size === 0) continue

      const similarity = jaccardSimilarity(incomingKeywords, peerKeywords)

      if (similarity >= RESONANCE_SIMILARITY_THRESHOLD) {
        const isOpposing = areOpposingKinds(incomingSignal.kind, entry.signal.kind)

        const pattern: ResonancePattern = {
          kind: isOpposing ? 'tension' : 'resonance',
          signalA: { sessionId: sourceSessionId, signal: incomingSignal },
          signalB: { sessionId: peerId, signal: entry.signal },
          similarity,
          amplifiedConfidence: isOpposing
            ? Math.max(incomingSignal.confidence, entry.signal.confidence)
            : Math.min(1.0, Math.max(incomingSignal.confidence, entry.signal.confidence) + RESONANCE_CONFIDENCE_BOOST),
          detectedAt: now,
        }

        // Store for both sessions
        storeResonance(sourceSessionId, pattern)
        storeResonance(peerId, pattern)

        if (isOpposing) {
          _totalTensions++
          logger.info('Tension detected', {
            source: sourceSessionId.slice(-8),
            peer: peerId.slice(-8),
            similarity: similarity.toFixed(2),
            kindA: incomingSignal.kind,
            kindB: entry.signal.kind,
          })
        } else {
          _totalResonances++
          logger.info('Resonance detected', {
            source: sourceSessionId.slice(-8),
            peer: peerId.slice(-8),
            similarity: similarity.toFixed(2),
            amplified: pattern.amplifiedConfidence.toFixed(2),
          })
        }

        // REMOVED: injectionAggregator resonance injection — InjectionAggregator deleted.

        // Only one resonance per incoming signal (highest similarity)
        break
      }
    }
  }

  function storeResonance(sessionId: string, pattern: ResonancePattern): void {
    if (!_resonance.has(sessionId)) _resonance.set(sessionId, [])
    const store = _resonance.get(sessionId)!
    store.push(pattern)

    // Evict old + cap
    const cutoff = Date.now() - RESONANCE_TTL_MS
    const fresh = store.filter(p => p.detectedAt > cutoff)
    _resonance.set(sessionId, fresh.slice(-MAX_RESONANCE_PATTERNS_PER_SESSION))
  }


  function getFusedSignals(sessionId: string): CognitiveSignal[] {
    return [...(_peerSignals.get(sessionId) ?? [])]
  }

  function getResonancePatterns(sessionId: string): ResonancePattern[] {
    const now = Date.now()
    const patterns = _resonance.get(sessionId) ?? []
    // Return only non-expired
    return patterns.filter(p => (now - p.detectedAt) < RESONANCE_TTL_MS)
  }


  function tryAutoLinkByProject(newSessionId: string): void {
    if (!_sessionManager) return

    const newSession = _sessionManager.get(newSessionId)
    if (!newSession) return

    const newProjectPath = (newSession.config as any)?.projectPath
    if (!newProjectPath) return

    // Check all existing sessions with links or digests
    // We need to iterate existing sessions — use the link map + check session manager
    const checkedIds = new Set<string>()

    // Check sessions that already have links (they're active)
    for (const [existingId] of _links) {
      if (existingId === newSessionId || checkedIds.has(existingId)) continue
      checkedIds.add(existingId)

      const existing = _sessionManager.get(existingId)
      if (!existing) continue

      const existingPath = (existing.config as any)?.projectPath
      if (existingPath && existingPath === newProjectPath) {
        linkSessions(newSessionId, existingId, 'auto-project')
      }
    }
  }

  function tryAutoLinkSpawn(parentSessionId: string, childSessionId: string): void {
    linkSessions(parentSessionId, childSessionId, 'spawn-linked')
  }


  function onEventBus(bus: IEventBus): void {
    _bus = bus

    // Auto-link on session creation (by project)
    const unsub1 = bus.on('session:created' as any, (e: any) => {
      try {
        const sessionId = e?.sessionId
        if (sessionId) {
          // Delay slightly to let the session's config be fully populated
          setTimeout(() => tryAutoLinkByProject(sessionId), 500)
        }
      } catch (err) {
        logger.debug('session:created handler error', { error: String(err) })
      }
    })
    if (unsub1) _unsubscribers.push(unsub1)

    // Auto-link on subagent spawn
    const unsub2 = bus.on('subagent:spawned' as any, (e: any) => {
      try {
        const parentId = e?.parentSessionId
        const childId = e?.childSessionId
        if (parentId && childId) {
          tryAutoLinkSpawn(parentId, childId)
        }
      } catch (err) {
        logger.debug('subagent:spawned handler error', { error: String(err) })
      }
    })
    if (unsub2) _unsubscribers.push(unsub2)

    // When MultiAgentCoordinator spawns a team agent, link it to the parent
    // session AND to all existing team siblings. Agent thinking streams then
    // route through ThoughtObserver → CognitiveBridge → peer sessions.
    const unsub4 = bus.on('agent:spawned' as any, (e: any) => {
      try {
        const agentId = e?.agentId
        const parentSessionId = e?.parentSessionId
        const role = e?.role

        if (!agentId) return

        const agentSessionId = `agent:${agentId}`

        // Link to parent session if provided
        if (parentSessionId) {
          tryAutoLinkSpawn(parentSessionId, agentSessionId)
          logger.info('Team agent linked to parent', {
            agentId: agentId.slice?.(-8) ?? agentId,
            parent: parentSessionId.slice(-8),
            role,
          })

          // Link to existing team siblings (other agents linked to the same parent)
          const parentPeers = getLinkedPeers(parentSessionId)
          for (const peer of parentPeers) {
            // Link to other agents (not the parent itself, and not itself)
            if (peer.peerId.startsWith('agent:') && peer.peerId !== agentSessionId) {
              linkSessions(agentSessionId, peer.peerId, 'spawn-linked')
              logger.debug('Sibling agents linked', {
                agentA: agentSessionId.slice(-8),
                agentB: peer.peerId.slice(-8),
              })
            }
          }
        }
      } catch (err) {
        logger.debug('agent:spawned handler error', { error: String(err) })
      }
    })
    if (unsub4) _unsubscribers.push(unsub4)

    // Clean up agent links on completion/error
    const handleAgentEnd = (e: any) => {
      try {
        const agentId = e?.agentId
        if (agentId) {
          cleanupSession(`agent:${agentId}`)
          logger.debug('Agent session cleaned up', {
            agentId: agentId.slice?.(-8) ?? agentId,
          })
        }
      } catch (err) {
        logger.debug('agent end handler error', { error: String(err) })
      }
    }

    const unsub5 = bus.on('agent:completed' as any, handleAgentEnd)
    if (unsub5) _unsubscribers.push(unsub5)
    const unsub6 = bus.on('agent:error' as any, handleAgentEnd)
    if (unsub6) _unsubscribers.push(unsub6)

    // Clean up on session end
    const unsub3 = bus.on('session:ended' as any, (e: any) => {
      try {
        const sessionId = (e as any)?.sessionId
        if (sessionId) cleanupSession(sessionId)
      } catch (err) {
        logger.debug('session:ended handler error', { error: String(err) })
      }
    })
    if (unsub3) _unsubscribers.push(unsub3)

    logger.info('Wired to event bus')
  }

  // REMOVED: setInjectionAggregator — InjectionAggregator deleted.

  function setSessionManager(sm: { get(id: string): any | undefined }): void {
    _sessionManager = sm
  }


  function cleanupSession(sessionId: string): void {
    // Unlink from all peers
    const peers = _links.get(sessionId)
    if (peers) {
      for (const [peerId] of peers) {
        const peerLinks = _links.get(peerId)
        peerLinks?.delete(sessionId)
        if (peerLinks && peerLinks.size === 0) _links.delete(peerId)
      }
      _links.delete(sessionId)
    }

    _peerSignals.delete(sessionId)
    _resonance.delete(sessionId)
    _recentSignals.delete(sessionId)

    // Cancel debounce timer
    const timer = _routeTimers.get(sessionId)
    if (timer) {
      clearTimeout(timer)
      _routeTimers.delete(sessionId)
    }
    _routeQueues.delete(sessionId)
  }

  function cleanup(): void {
    for (const unsub of _unsubscribers) {
      try { unsub() } catch { /* best-effort */ }
    }
    _unsubscribers.length = 0

    // Cancel all debounce timers
    for (const [, timer] of _routeTimers) clearTimeout(timer)

    _links.clear()
    _peerSignals.clear()
    _resonance.clear()
    _recentSignals.clear()
    _routeTimers.clear()
    _routeQueues.clear()

    logger.info('Cleaned up')
  }

  function getStats(): CognitiveBridgeStats {
    let totalLinks = 0
    for (const [, peers] of _links) totalLinks += peers.size
    totalLinks = Math.floor(totalLinks / 2) // Each link counted twice (bidirectional)

    return {
      totalLinks,
      totalSignalsRouted: _totalRouted,
      totalResonancesDetected: _totalResonances,
      totalTensionsDetected: _totalTensions,
      activeSessionCount: _links.size,
    }
  }

  return {
    name,
    priority,
    linkSessions,
    unlinkSessions,
    isLinked,
    getLinkedPeers,
    routeSignals,
    getFusedSignals,
    getResonancePatterns,
    onEventBus,
    setSessionManager,
    getStats,
    cleanup,
  }
}
