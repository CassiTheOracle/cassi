/**
 * Territory bridge — overlap detection and bridge-signal emission for cross-Helix
 * territory awareness. Consumes the goal-signal contract established by
 * `helix-goal-lamina.ts:publishHelixGoalSignal` (PR-1 of the territory-awareness
 * spec at docs/design/cassi-proposed/pending/2026-05-06-cross-helix-territory-awareness.md).
 *
 * Goal-signal metadata contract this module reads:
 *   { constellationId, helixId, relevantFiles, budgetSteps, kind }
 *
 * Any change to that contract must update parseSiblingGoalEntry below.
 */

import type { CognitiveSignal } from '../workspace/cognitive-signal.js'
import type { GlobalWorkspace } from '../workspace/global-workspace.js'
import { extractKeywords, keywordOverlap } from '../workspace/luminance.js'

const MIN_CONCEPT_OVERLAP = 0.25
const MIN_SHARED_KEYWORDS = 3

/**
 * Pair-keyed exact-match dedupe with TTL — purpose-built for bridge emission.
 *
 * BroadcastDedupe (used by HelixSynapse for prose) does Jaccard on tokens, which
 * collapses our structured fingerprints (file lists separated by punctuation)
 * into near-identical token sets. Exact match on a canonical fingerprint string
 * is the right semantic for "same overlap shape between the same pair."
 */
export class BridgeDedupe {
  private history: Map<string, { fingerprint: string; at: number }> = new Map()
  constructor(private readonly ttlMs: number = 30_000) {}

  check(key: string, fingerprint: string): boolean {
    const now = Date.now()
    this.prune(now)
    const prev = this.history.get(key)
    return Boolean(prev && prev.fingerprint === fingerprint)
  }

  remember(key: string, fingerprint: string): void {
    this.history.set(key, { fingerprint, at: Date.now() })
  }

  private prune(now: number): void {
    for (const [k, v] of this.history) {
      if (now - v.at > this.ttlMs) this.history.delete(k)
    }
  }
}

export interface SiblingGoalEntry {
  helixId: string
  goalText: string
  relevantFiles: string[]
  keywords: Set<string>
  budgetSteps?: number
  receivedAt: number
}

export interface OverlapResult {
  hasOverlap: boolean
  sharedFiles: string[]
  sharedKeywords: string[]
}

export function parseSiblingGoalEntry(signal: CognitiveSignal): SiblingGoalEntry | null {
  if (signal.type !== 'goal') return null
  const md = signal.metadata as Record<string, unknown> | undefined
  if (!md) return null
  const helixId = typeof md.helixId === 'string' ? md.helixId : signal.sessionId
  const relevantFiles = Array.isArray(md.relevantFiles)
    ? md.relevantFiles.filter((f): f is string => typeof f === 'string')
    : []
  return {
    helixId,
    goalText: signal.content,
    relevantFiles,
    keywords: extractKeywords(signal.content),
    budgetSteps: typeof md.budgetSteps === 'number' ? md.budgetSteps : undefined,
    receivedAt: signal.createdAt,
  }
}

export function computeFileOverlap(a: SiblingGoalEntry, b: SiblingGoalEntry): string[] {
  if (!a.relevantFiles.length || !b.relevantFiles.length) return []
  const setB = new Set(b.relevantFiles)
  return a.relevantFiles.filter(f => setB.has(f))
}

export function computeConceptOverlap(a: SiblingGoalEntry, b: SiblingGoalEntry): string[] {
  if (!a.keywords.size || !b.keywords.size) return []
  const overlap = keywordOverlap(a.keywords, b.keywords)
  if (overlap < MIN_CONCEPT_OVERLAP) return []
  const shared: string[] = []
  for (const k of a.keywords) if (b.keywords.has(k)) shared.push(k)
  return shared.length >= MIN_SHARED_KEYWORDS ? shared : []
}

export function computeTerritorialOverlap(a: SiblingGoalEntry, b: SiblingGoalEntry): OverlapResult {
  const sharedFiles = computeFileOverlap(a, b)
  const sharedKeywords = computeConceptOverlap(a, b)
  return {
    hasOverlap: sharedFiles.length > 0 || sharedKeywords.length > 0,
    sharedFiles,
    sharedKeywords,
  }
}

export function renderBridgeContent(peer: SiblingGoalEntry, overlap: OverlapResult): string {
  const lines = [
    `Helix ${peer.helixId.slice(0, 8)} is also working on overlapping territory.`,
    `  Their goal: ${peer.goalText.split('\n')[0].slice(0, 200)}`,
  ]
  if (overlap.sharedFiles.length) lines.push(`  Shared files: ${overlap.sharedFiles.join(', ')}`)
  if (overlap.sharedKeywords.length) lines.push(`  Shared concepts: ${overlap.sharedKeywords.join(', ')}`)
  return lines.join('\n')
}

export interface TerritoryHandlerState {
  siblingGoalIndex: Map<string, SiblingGoalEntry>
  isMember: (helixId: string) => boolean
}

/**
 * Handle a batch of workspace broadcast signals — filter for goal signals from
 * sibling Helixes, maintain the goal index, and emit bridge signals on overlap.
 * Idempotent across repeat calls (dedupe handles re-broadcasts of the same goal).
 *
 * Pure-ish: the only side effects are mutating `state.siblingGoalIndex`,
 * `dedupe`'s memory, and submitting bridge signals to `workspace`. No timers,
 * no logger, no global state. Called by Corpus.onWorkspaceBroadcast.
 */
export function handleWorkspaceBroadcastForTerritory(
  signals: CognitiveSignal[],
  state: TerritoryHandlerState,
  workspace: GlobalWorkspace,
  dedupe: BridgeDedupe,
  constellationId: string,
): void {
  for (const sig of signals) {
    if (sig.type !== 'goal') continue
    if (!state.isMember(sig.sessionId)) continue

    const entry = parseSiblingGoalEntry(sig)
    if (!entry) continue

    const md = sig.metadata as Record<string, unknown> | undefined
    const kind = md?.kind
    if (kind === 'completed' || kind === 'failed') {
      state.siblingGoalIndex.delete(entry.helixId)
      continue
    }

    state.siblingGoalIndex.set(entry.helixId, entry)

    for (const [peerId, peer] of state.siblingGoalIndex) {
      if (peerId === entry.helixId) continue
      const overlap = computeTerritorialOverlap(entry, peer)
      if (overlap.hasOverlap) {
        emitBridgePair(workspace, dedupe, constellationId, entry, peer, overlap)
      }
    }
  }
}

export function emitBridgePair(
  workspace: GlobalWorkspace,
  dedupe: BridgeDedupe,
  constellationId: string,
  a: SiblingGoalEntry,
  b: SiblingGoalEntry,
  overlap: OverlapResult,
): boolean {
  const [first, second] = a.helixId < b.helixId ? [a, b] : [b, a]
  const dedupeKey = `bridge:${first.helixId}:${second.helixId}`
  const fingerprint = `${overlap.sharedFiles.slice().sort().join(',')}|${overlap.sharedKeywords.slice().sort().join(',')}`
  if (dedupe.check(dedupeKey, fingerprint)) return false
  dedupe.remember(dedupeKey, fingerprint)

  for (const [target, peer] of [[a, b], [b, a]] as const) {
    const signal: CognitiveSignal = {
      signalId: `bridge-${target.helixId}-${Date.now()}`,
      source: 'corpus',
      sessionId: target.helixId,
      type: 'bridge',
      content: renderBridgeContent(peer, overlap),
      createdAt: Date.now(),
      urgencyHint: 0,
      luminance: {
        novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0,
        cognitiveResonance: 0, strategicImportance: 0, composite: 0,
      },
      metadata: {
        constellationId,
        peerHelixId: peer.helixId,
        sharedFiles: overlap.sharedFiles,
        sharedKeywords: overlap.sharedKeywords,
      },
    }
    try {
      workspace.submit(signal)
    } catch {
      // Non-fatal — the second emission may still succeed; receiver gets one of the pair.
    }
  }
  return true
}
