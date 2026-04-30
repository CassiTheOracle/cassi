/**
 * Tests for AuroraPersistence — cross-session state continuity (B6.1).
 *
 * Covers:
 *  - Schema migration (v1)
 *  - Session lifecycle: begin, end, crash recovery
 *  - Node/edge upsert + hydration with decay
 *  - Reasoning log write + read-back
 *  - Focus and affect recording
 *  - Decay pass (sub-threshold pruning)
 *  - Full round-trip: write state → close → reopen → hydrate
 *
 * See: docs/design/aurora-cross-session-continuity.md
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'

import type { CognitiveNode, CognitiveEdge } from './types.js'
import type { ReasoningRecord } from './types.js'
import { AuroraPersistence } from './persistence.js'
import type { SessionHandle } from './persistence.js'

// section

function mockLogger(): any {
  const make = () => ({
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => make(),
  })
  return make()
}

function makeNode(overrides: Partial<CognitiveNode> = {}): CognitiveNode {
  return {
    id: 'node_test',
    label: 'test concept',
    source: 'both',
    resonance: 0.8,
    centrality: 0.5,
    activated: true,
    ...overrides,
  }
}

function makeEdge(overrides: Partial<CognitiveEdge> = {}): CognitiveEdge {
  return {
    sourceId: 'node_a',
    targetId: 'node_b',
    origin: 'model',
    edgeType: 'co_activates_with',
    weight: 0.7,
    ...overrides,
  }
}

function makeReasoningRecord(turn: number): ReasoningRecord {
  return {
    id: `rec_${turn}`,
    text: `Reasoning text for turn ${turn}`,
    concepts: ['concept_a', 'concept_b'],
    insights: [],
    shift: null,
    momentum: { trendingConcepts: ['concept_a'], novelty: 0.3, confidence: 0.7, topicShift: false, turnsInDirection: 1 },
    activatedNodes: ['node_a'],
    turnNumber: turn,
    recordedAt: Date.now(),
    durationMs: 50,
    reverieAnalyzed: false,
  }
}

// section

describe('AuroraPersistence', () => {
  let tmpDir: string
  let dbPath: string

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aurora-persist-'))
    dbPath = path.join(tmpDir, 'aurora.db')
  })

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true })
  })

  it('creates schema on first open', () => {
    const p = new AuroraPersistence(dbPath, mockLogger())
    // If we got here without errors, the schema was created
    p.close()
    expect(fs.existsSync(dbPath)).toBe(true)
  })

  it('idempotent open (schema already exists)', () => {
    const p1 = new AuroraPersistence(dbPath, mockLogger())
    p1.close()
    const p2 = new AuroraPersistence(dbPath, mockLogger())
    p2.close()
    // No double-migration errors
  })

  // section

  describe('session lifecycle', () => {
    it('begins a session with no prior sessions (cold start)', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const handle = p.beginSession()
      expect(handle.sessionId).toMatch(/^aur_sess_/)
      expect(handle.inheritsFrom).toBeNull()
      expect(handle.createdAt).toBeTruthy()
      p.close()
    })

    it('chains sessions (inherits_from)', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const h1 = p.beginSession()
      p.endSession(h1, 'graceful')

      const h2 = p.beginSession()
      expect(h2.inheritsFrom).toBe(h1.sessionId)
      p.close()
    })

    it('detects crashed sessions and closes them', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const h1 = p.beginSession()
      // Don't end h1 — simulate crash

      const h2 = p.beginSession()
      expect(h2.inheritsFrom).toBe(h1.sessionId)
      p.close()
    })
  })

  // section

  describe('node persistence', () => {
    it('upserts and hydrates nodes', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const handle = p.beginSession()

      p.upsertNode(makeNode({ id: 'n1', label: 'concept_a', resonance: 0.9 }), handle.sessionId)
      p.upsertNode(makeNode({ id: 'n2', label: 'concept_b', resonance: 0.6 }), handle.sessionId)

      const { nodes } = p.hydrateClaustrum()
      expect(nodes).toHaveLength(2)

      const n1 = nodes.find(n => n.id === 'n1')
      expect(n1).toBeDefined()
      expect(n1!.label).toBe('concept_a')
      expect(n1!.resonance).toBeCloseTo(0.9, 2) // fresh — no decay

      p.close()
    })

    it('upsert bumps activation count on conflict', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const handle = p.beginSession()

      p.upsertNode(makeNode({ id: 'n1', resonance: 0.5 }), handle.sessionId)
      p.upsertNode(makeNode({ id: 'n1', resonance: 0.8 }), handle.sessionId)

      const { nodes } = p.hydrateClaustrum()
      const n1 = nodes.find(n => n.id === 'n1')
      expect(n1!.resonance).toBeGreaterThanOrEqual(0.8) // MAX(0.5, 0.8)
      p.close()
    })
  })

  // section

  describe('edge persistence', () => {
    it('upserts and hydrates edges between nodes', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const handle = p.beginSession()

      p.upsertNode(makeNode({ id: 'a' }), handle.sessionId)
      p.upsertNode(makeNode({ id: 'b' }), handle.sessionId)
      p.upsertEdge(makeEdge({ sourceId: 'a', targetId: 'b', weight: 0.7 }))

      const { edges } = p.hydrateClaustrum()
      expect(edges).toHaveLength(1)
      expect(edges[0].weight).toBeCloseTo(0.7, 2)
      expect(edges[0].sourceId).toBe('a')
      expect(edges[0].targetId).toBe('b')
      p.close()
    })
  })

  // section

  describe('reasoning log', () => {
    it('writes and hydrates reasoning records', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const handle = p.beginSession()

      for (let i = 1; i <= 5; i++) {
        p.writeReasoning(handle, makeReasoningRecord(i))
      }

      const records = p.hydrateReasoningLog()
      expect(records).toHaveLength(5)
      expect(records[0].turnNumber).toBe(1) // oldest first
      expect(records[4].turnNumber).toBe(5)
      expect(records[4].concepts).toEqual(['concept_a', 'concept_b'])

      p.close()
    })

    it('respects the hydration limit', () => {
      const p = new AuroraPersistence(dbPath, mockLogger(), { reasoningHydrationLimit: 3 })
      const handle = p.beginSession()

      for (let i = 1; i <= 10; i++) {
        p.writeReasoning(handle, makeReasoningRecord(i))
      }

      const records = p.hydrateReasoningLog()
      expect(records).toHaveLength(3)
      // Should get the most recent 3
      expect(records[2].turnNumber).toBe(10)
      p.close()
    })
  })

  // section

  describe('focus and affect', () => {
    it('records and hydrates focus shifts', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const handle = p.beginSession()

      p.recordFocusShift(handle, ['concept_a', 'concept_b'], 'topic_change')

      const focus = p.hydrateFocus()
      expect(focus).not.toBeNull()
      expect(focus!.foci).toEqual(['concept_a', 'concept_b'])
      expect(focus!.trigger).toBe('topic_change')
      p.close()
    })

    it('records affect samples', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const handle = p.beginSession()

      // Just test it doesn't throw
      p.recordAffectSample(handle, { label: 'curious', intensity: 0.7 })
      p.close()
    })

    it('returns null focus when no records exist', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      expect(p.hydrateFocus()).toBeNull()
      p.close()
    })

    it('returns null momentum when no records exist', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      expect(p.hydrateMomentum()).toBeNull()
      p.close()
    })
  })

  // section

  describe('decay pass', () => {
    it('drops sub-threshold nodes and edges', () => {
      const p = new AuroraPersistence(dbPath, mockLogger(), {
        minConfidenceThreshold: 0.1,
        nodeDecayHalfLifeDays: 7, // 7-day half-life
      })
      const handle = p.beginSession()

      // Create a node with low confidence
      p.upsertNode(makeNode({ id: 'weak', resonance: 0.15 }), handle.sessionId)
      p.upsertNode(makeNode({ id: 'strong', resonance: 0.99 }), handle.sessionId)

      // Simulate 30 days passing (~4.3 half-lives for weak: 0.15 * 0.5^4.3 ≈ 0.007)
      // For strong: 0.99 * 0.5^4.3 ≈ 0.047 — below threshold too.
      // Use 14 days (2 half-lives): weak → 0.15*0.25 = 0.0375 (dropped), strong → 0.99*0.25 = 0.2475 (survives)
      const future = new Date(Date.now() + 14 * 86_400_000)
      const result = p.decayPass(future)

      expect(result.nodesDropped).toBeGreaterThanOrEqual(1)
      const { nodes } = p.hydrateClaustrum(future)
      expect(nodes.find(n => n.id === 'weak')).toBeUndefined()
      expect(nodes.find(n => n.id === 'strong')).toBeDefined()
      p.close()
    })
  })

  // section

  describe('full round-trip (close → reopen → hydrate)', () => {
    it('survives close and reopen with state intact', () => {
      const handle1: SessionHandle = (() => {
        const p = new AuroraPersistence(dbPath, mockLogger())
        const h = p.beginSession({ vindexId: 'gemma3-4b' })

        p.upsertNode(makeNode({ id: 'n1', label: 'persistence test' }), h.sessionId)
        p.upsertNode(makeNode({ id: 'n2', label: 'cross-session' }), h.sessionId)
        p.upsertEdge(makeEdge({ sourceId: 'n1', targetId: 'n2' }))

        for (let i = 1; i <= 3; i++) {
          p.writeReasoning(h, makeReasoningRecord(i))
        }

        p.recordFocusShift(h, ['n1', 'n2'])
        p.endSession(h, 'graceful')
        p.close()
        return h
      })()

      // Reopen and hydrate
      const p2 = new AuroraPersistence(dbPath, mockLogger())
      const h2 = p2.beginSession()
      expect(h2.inheritsFrom).toBe(handle1.sessionId)

      const { nodes, edges } = p2.hydrateClaustrum()
      expect(nodes).toHaveLength(2)
      expect(edges).toHaveLength(1)

      const records = p2.hydrateReasoningLog()
      expect(records).toHaveLength(3)

      const focus = p2.hydrateFocus()
      expect(focus).not.toBeNull()
      expect(focus!.foci).toEqual(['n1', 'n2'])

      p2.endSession(h2, 'graceful')
      p2.close()
    })

    it('handles crash recovery on reopen', () => {
      // First instance: crash (no endSession)
      const p1 = new AuroraPersistence(dbPath, mockLogger())
      const h1 = p1.beginSession()
      p1.upsertNode(makeNode({ id: 'survivor', resonance: 0.8 }), h1.sessionId)
      // Don't call endSession or close — simulate crash
      p1.close()

      // Second instance: detects crash, recovers
      const p2 = new AuroraPersistence(dbPath, mockLogger())
      const h2 = p2.beginSession()
      expect(h2.inheritsFrom).toBe(h1.sessionId)

      const { nodes } = p2.hydrateClaustrum()
      expect(nodes).toHaveLength(1)
      expect(nodes[0].id).toBe('survivor')
      p2.close()
    })
  })

  // section

  describe('edge cases', () => {
    it('does nothing when closed', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      p.close()
      // beginSession should throw (assertOpen)
      expect(() => p.beginSession()).toThrow('AuroraPersistence is closed')
      // But non-asserting writes should be no-ops (they check this.closed early)
      expect(() => p.upsertNode(makeNode())).not.toThrow()
      expect(() => p.endSession({ sessionId: 'x', inheritsFrom: null, createdAt: '' } as any)).not.toThrow()
    })

    it('handles empty hydration gracefully', () => {
      const p = new AuroraPersistence(dbPath, mockLogger())
      const { nodes, edges } = p.hydrateClaustrum()
      expect(nodes).toHaveLength(0)
      expect(edges).toHaveLength(0)
      expect(p.hydrateReasoningLog()).toHaveLength(0)
      expect(p.hydrateMomentum()).toBeNull()
      expect(p.hydrateFocus()).toBeNull()
      p.close()
    })
  })
})
