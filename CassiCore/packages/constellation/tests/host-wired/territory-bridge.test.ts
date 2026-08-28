// HOST-WIRED: requires CassiCore daemon runtime; excluded from default vitest run.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { GlobalWorkspace } from '../../core/intelligence/workspace/global-workspace.js'
import {
  BridgeDedupe,
  computeConceptOverlap,
  computeFileOverlap,
  computeTerritorialOverlap,
  emitBridgePair,
  handleWorkspaceBroadcastForTerritory,
  parseSiblingGoalEntry,
  renderBridgeContent,
  type SiblingGoalEntry,
} from '../../core/intelligence/constellation/territory-bridge.js'
import { extractKeywords } from '../../core/intelligence/workspace/luminance.js'
import { publishHelixGoalSignal } from '../../core/intelligence/constellation/helix-goal-lamina.js'

import type { CognitiveSignal } from '../../core/intelligence/workspace/cognitive-signal.js'
import type { GoalSubTask } from '../../core/intelligence/constellation/corpus-types.js'
import type { ILogger } from '../../types/interfaces.js'

function silentLogger(): ILogger {
  const make = () => () => undefined as unknown as void
  const l: ILogger = { debug: make(), info: make(), warn: make(), error: make(), child: () => l }
  return l
}

function makeEntry(overrides: Partial<SiblingGoalEntry> = {}): SiblingGoalEntry {
  const goalText = overrides.goalText ?? 'Add rate limiting to admin API endpoints'
  return {
    helixId: 'helix-default',
    goalText,
    relevantFiles: ['core/admin-api/index.ts', 'core/admin-api/middleware.ts'],
    keywords: overrides.keywords ?? extractKeywords(goalText),
    budgetSteps: 30,
    receivedAt: 1000,
    ...overrides,
  }
}

function makeSubTask(overrides: Partial<GoalSubTask> = {}): GoalSubTask {
  return {
    goal: 'Add rate limiting to admin API',
    relevantFiles: ['core/admin-api/index.ts'],
    budgetSteps: 30,
    priority: 1,
    ...overrides,
  }
}

describe('territory-bridge — pure helpers', () => {
  describe('parseSiblingGoalEntry', () => {
    it('returns a SiblingGoalEntry for a well-formed goal signal', () => {
      const sig: CognitiveSignal = {
        signalId: 's1',
        source: 'helix',
        sessionId: 'helix-1',
        type: 'goal',
        content: 'Working on: Add rate limiting',
        createdAt: 5000,
        luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, cognitiveResonance: 0, strategicImportance: 0, composite: 0 },
        metadata: {
          constellationId: 'c-1',
          helixId: 'helix-1',
          relevantFiles: ['a.ts', 'b.ts'],
          budgetSteps: 25,
          kind: 'seed',
        },
      }
      const entry = parseSiblingGoalEntry(sig)
      expect(entry).not.toBeNull()
      expect(entry?.helixId).toBe('helix-1')
      expect(entry?.goalText).toBe('Working on: Add rate limiting')
      expect(entry?.relevantFiles).toEqual(['a.ts', 'b.ts'])
      expect(entry?.budgetSteps).toBe(25)
      expect(entry?.receivedAt).toBe(5000)
    })

    it('returns null for non-goal signals', () => {
      const sig: CognitiveSignal = {
        signalId: 's2',
        source: 'corpus',
        sessionId: 'helix-1',
        type: 'warning',
        content: 'Something',
        createdAt: 0,
        luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, cognitiveResonance: 0, strategicImportance: 0, composite: 0 },
        metadata: {},
      }
      expect(parseSiblingGoalEntry(sig)).toBeNull()
    })

    it('falls back to sessionId when metadata.helixId missing', () => {
      const sig: CognitiveSignal = {
        signalId: 's3', source: 'helix', sessionId: 'helix-fallback', type: 'goal', content: 'x', createdAt: 0,
        luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, cognitiveResonance: 0, strategicImportance: 0, composite: 0 },
        metadata: { constellationId: 'c-1' },
      }
      expect(parseSiblingGoalEntry(sig)?.helixId).toBe('helix-fallback')
    })
  })

  describe('computeFileOverlap', () => {
    it('returns intersection of relevantFiles', () => {
      const a = makeEntry({ relevantFiles: ['a.ts', 'b.ts', 'c.ts'] })
      const b = makeEntry({ relevantFiles: ['b.ts', 'c.ts', 'd.ts'] })
      expect(computeFileOverlap(a, b)).toEqual(['b.ts', 'c.ts'])
    })

    it('returns empty when neither has files', () => {
      const a = makeEntry({ relevantFiles: [] })
      const b = makeEntry({ relevantFiles: [] })
      expect(computeFileOverlap(a, b)).toEqual([])
    })

    it('returns empty when no intersection', () => {
      const a = makeEntry({ relevantFiles: ['a.ts'] })
      const b = makeEntry({ relevantFiles: ['b.ts'] })
      expect(computeFileOverlap(a, b)).toEqual([])
    })
  })

  describe('computeConceptOverlap', () => {
    it('returns shared keywords when Jaccard >= 0.25 AND shared count >= 3', () => {
      const a = makeEntry({ goalText: 'Add rate limiting to admin API endpoints', keywords: extractKeywords('Add rate limiting to admin API endpoints') })
      const b = makeEntry({ goalText: 'Refactor rate limiting on admin API middleware', keywords: extractKeywords('Refactor rate limiting on admin API middleware') })
      const shared = computeConceptOverlap(a, b)
      expect(shared.length).toBeGreaterThanOrEqual(3)
    })

    it('returns empty when keyword overlap is too small', () => {
      const a = makeEntry({ goalText: 'Add caching layer to database', keywords: extractKeywords('Add caching layer to database') })
      const b = makeEntry({ goalText: 'Refactor authentication middleware', keywords: extractKeywords('Refactor authentication middleware') })
      expect(computeConceptOverlap(a, b)).toEqual([])
    })

    it('returns empty when either set is empty', () => {
      const a = makeEntry({ keywords: new Set() })
      const b = makeEntry()
      expect(computeConceptOverlap(a, b)).toEqual([])
    })
  })

  describe('computeTerritorialOverlap', () => {
    it('hasOverlap when files overlap even if concepts do not', () => {
      const a = makeEntry({ relevantFiles: ['x.ts'], goalText: 'Add caching', keywords: extractKeywords('Add caching') })
      const b = makeEntry({ relevantFiles: ['x.ts'], goalText: 'Refactor authentication', keywords: extractKeywords('Refactor authentication') })
      const overlap = computeTerritorialOverlap(a, b)
      expect(overlap.hasOverlap).toBe(true)
      expect(overlap.sharedFiles).toEqual(['x.ts'])
      expect(overlap.sharedKeywords).toEqual([])
    })

    it('hasOverlap when concepts overlap even if files do not', () => {
      const t = 'Add rate limiting to admin API endpoints'
      const a = makeEntry({ relevantFiles: ['a.ts'], goalText: t, keywords: extractKeywords(t) })
      const b = makeEntry({ relevantFiles: ['b.ts'], goalText: 'Refactor rate limiting on admin API middleware', keywords: extractKeywords('Refactor rate limiting on admin API middleware') })
      const overlap = computeTerritorialOverlap(a, b)
      expect(overlap.hasOverlap).toBe(true)
      expect(overlap.sharedFiles).toEqual([])
      expect(overlap.sharedKeywords.length).toBeGreaterThanOrEqual(3)
    })

    it('hasOverlap is false when neither files nor concepts match', () => {
      const a = makeEntry({ relevantFiles: ['a.ts'], goalText: 'Add caching', keywords: extractKeywords('Add caching') })
      const b = makeEntry({ relevantFiles: ['b.ts'], goalText: 'Refactor authentication', keywords: extractKeywords('Refactor authentication') })
      expect(computeTerritorialOverlap(a, b).hasOverlap).toBe(false)
    })
  })

  describe('renderBridgeContent', () => {
    it('includes peer goal preview, shared files, shared concepts', () => {
      const peer = makeEntry({ helixId: 'helix-peer-12345678', goalText: 'Working on: Add rate limiting' })
      const overlap = { hasOverlap: true, sharedFiles: ['x.ts'], sharedKeywords: ['rate', 'limiting', 'admin'] }
      const content = renderBridgeContent(peer, overlap)
      expect(content).toContain('Helix helix-pe is also working')
      expect(content).toContain('Their goal: Working on: Add rate limiting')
      expect(content).toContain('Shared files: x.ts')
      expect(content).toContain('Shared concepts: rate, limiting, admin')
    })

    it('omits the files line when no shared files', () => {
      const peer = makeEntry()
      const overlap = { hasOverlap: true, sharedFiles: [], sharedKeywords: ['k1', 'k2', 'k3'] }
      const content = renderBridgeContent(peer, overlap)
      expect(content).not.toContain('Shared files:')
      expect(content).toContain('Shared concepts:')
    })
  })
})

describe('emitBridgePair', () => {
  let workspace: GlobalWorkspace
  let dedupe: BridgeDedupe

  beforeEach(() => {
    workspace = new GlobalWorkspace(silentLogger())
    dedupe = new BridgeDedupe(30_000)
  })

  it('submits two bridge signals on first emit, one targeted at each member', () => {
    const a = makeEntry({ helixId: 'helix-a' })
    const b = makeEntry({ helixId: 'helix-b' })
    const overlap = { hasOverlap: true, sharedFiles: ['x.ts'], sharedKeywords: [] }

    const emitted = emitBridgePair(workspace, dedupe, 'c-1', a, b, overlap)
    expect(emitted).toBe(true)

    const foci = workspace.getCurrentFoci()
    const bridges = foci.filter(s => s.type === 'bridge')
    expect(bridges.length).toBe(2)
    const sessionIds = new Set(bridges.map(b => b.sessionId))
    expect(sessionIds).toEqual(new Set(['helix-a', 'helix-b']))
  })

  it('is a no-op on the second emit with same overlap (within dedupe ttl)', () => {
    const a = makeEntry({ helixId: 'helix-a' })
    const b = makeEntry({ helixId: 'helix-b' })
    const overlap = { hasOverlap: true, sharedFiles: ['x.ts'], sharedKeywords: [] }

    expect(emitBridgePair(workspace, dedupe, 'c-1', a, b, overlap)).toBe(true)
    expect(emitBridgePair(workspace, dedupe, 'c-1', a, b, overlap)).toBe(false)
  })

  it('re-emits when the overlap shape changes (different files)', () => {
    const a = makeEntry({ helixId: 'helix-a' })
    const b = makeEntry({ helixId: 'helix-b' })

    expect(emitBridgePair(workspace, dedupe, 'c-1', a, b, { hasOverlap: true, sharedFiles: ['x.ts'], sharedKeywords: [] })).toBe(true)
    expect(emitBridgePair(workspace, dedupe, 'c-1', a, b, { hasOverlap: true, sharedFiles: ['x.ts', 'y.ts'], sharedKeywords: [] })).toBe(true)
  })

  it('re-emits after the dedupe TTL expires', () => {
    vi.useFakeTimers()
    try {
      const a = makeEntry({ helixId: 'helix-a' })
      const b = makeEntry({ helixId: 'helix-b' })
      const overlap = { hasOverlap: true, sharedFiles: ['x.ts'], sharedKeywords: [] }

      expect(emitBridgePair(workspace, dedupe, 'c-1', a, b, overlap)).toBe(true)
      vi.advanceTimersByTime(31_000)
      expect(emitBridgePair(workspace, dedupe, 'c-1', a, b, overlap)).toBe(true)
    } finally {
      vi.useRealTimers()
    }
  })

  it('uses canonical pair ordering for stable dedupe (a→b vs b→a are the same key)', () => {
    const a = makeEntry({ helixId: 'helix-a' })
    const b = makeEntry({ helixId: 'helix-b' })
    const overlap = { hasOverlap: true, sharedFiles: ['x.ts'], sharedKeywords: [] }

    expect(emitBridgePair(workspace, dedupe, 'c-1', a, b, overlap)).toBe(true)
    expect(emitBridgePair(workspace, dedupe, 'c-1', b, a, overlap)).toBe(false)
  })
})

describe('handleWorkspaceBroadcastForTerritory — integration', () => {
  let workspace: GlobalWorkspace
  let dedupe: BridgeDedupe
  let goalIndex: Map<string, SiblingGoalEntry>
  let members: Set<string>

  beforeEach(() => {
    workspace = new GlobalWorkspace(silentLogger())
    dedupe = new BridgeDedupe(30_000)
    goalIndex = new Map()
    members = new Set(['helix-1', 'helix-2'])
  })

  function publish(helixId: string, subTask: GoalSubTask, kind: 'seed' | 'completed' | 'failed' = 'seed', outcome?: string): void {
    publishHelixGoalSignal(workspace, 'c-1', helixId, subTask, kind, outcome)
  }

  function process(): void {
    handleWorkspaceBroadcastForTerritory(
      workspace.getCurrentFoci(),
      { siblingGoalIndex: goalIndex, isMember: id => members.has(id) },
      workspace, dedupe, 'c-1',
    )
  }

  it('emits bridges when two siblings have overlapping files', () => {
    publish('helix-1', makeSubTask({ relevantFiles: ['x.ts', 'y.ts'] }))
    publish('helix-2', makeSubTask({ relevantFiles: ['y.ts', 'z.ts'] }))
    process()

    const bridges = workspace.getCurrentFoci().filter(s => s.type === 'bridge')
    expect(bridges.length).toBe(2)
    expect(new Set(bridges.map(b => b.sessionId))).toEqual(new Set(['helix-1', 'helix-2']))
  })

  it('does not emit when goals do not overlap', () => {
    publish('helix-1', makeSubTask({ goal: 'Caching layer', relevantFiles: ['cache.ts'] }))
    publish('helix-2', makeSubTask({ goal: 'Auth middleware', relevantFiles: ['auth.ts'] }))
    process()

    expect(workspace.getCurrentFoci().filter(s => s.type === 'bridge').length).toBe(0)
  })

  it('ignores goals from non-sibling sessionIds', () => {
    publish('helix-1', makeSubTask({ relevantFiles: ['x.ts'] }))
    publish('helix-stranger', makeSubTask({ relevantFiles: ['x.ts'] }))
    process()

    expect(workspace.getCurrentFoci().filter(s => s.type === 'bridge').length).toBe(0)
    expect(goalIndex.has('helix-stranger')).toBe(false)
    expect(goalIndex.has('helix-1')).toBe(true)
  })

  it('removes a helixId from the index on terminal kind', () => {
    publish('helix-1', makeSubTask({ relevantFiles: ['x.ts'] }))
    process()
    expect(goalIndex.has('helix-1')).toBe(true)

    publish('helix-1', makeSubTask({ relevantFiles: ['x.ts'] }), 'completed', 'shipped')
    process()
    expect(goalIndex.has('helix-1')).toBe(false)
  })

  it('skips bridge signals when re-processing (no feedback loop)', () => {
    publish('helix-1', makeSubTask({ relevantFiles: ['x.ts'] }))
    publish('helix-2', makeSubTask({ relevantFiles: ['x.ts'] }))
    process()

    const initialBridges = workspace.getCurrentFoci().filter(s => s.type === 'bridge').length
    expect(initialBridges).toBe(2)

    // Re-process — bridges still in slots, must not trigger more bridges
    process()
    expect(workspace.getCurrentFoci().filter(s => s.type === 'bridge').length).toBe(initialBridges)
  })
})
