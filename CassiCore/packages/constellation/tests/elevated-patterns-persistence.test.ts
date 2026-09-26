/**
 * Tests for Elevated Patterns persistence in ConstellationStore.
 *
 * Validates:
 * - Schema v3 migration creates the elevated_patterns table
 * - saveElevatedPattern persists patterns to SQLite
 * - getElevatedPatterns retrieves patterns with filtering
 * - incrementPatternReferenceCount updates counts
 * - pruneElevatedPatterns respects reference counts
 * - CorpusTree onPatternElevated callback fires on new patterns
 * - Pipeline seeding loads historical patterns into the tree
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { ConstellationStore } from '../src/constellation-store.js'
import { CorpusTree } from '../src/corpus-tree.js'
import type { ElevatedPattern } from '../src/corpus-types.js'

// Minimal logger for tests
const noopLogger = {
  info: () => {},
  warn: () => {},
  error: () => {},
  debug: () => {},
  child: () => noopLogger,
} as any

function makePattern(overrides: Partial<ElevatedPattern> = {}): ElevatedPattern {
  return {
    id: `pattern-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    sourceHelixId: 'helix-test-1',
    approach: 'implementation',
    description: 'Test pattern that worked well',
    applicableContext: 'When solving complex bugs',
    achievedScore: 0.85,
    relevantFiles: ['core/foo.ts', 'core/bar.ts'],
    supportingRetrospectives: ['pivot from brute-force to implementation: better coverage'],
    elevatedAt: Date.now(),
    referenceCount: 0,
    ...overrides,
  }
}


describe('Elevated Patterns Persistence', () => {
  let tmpDir: string
  let store: ConstellationStore

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cassi-elevated-test-'))
    store = ConstellationStore.open(noopLogger, tmpDir, 365)
  })

  afterEach(() => {
    store.close()
    fs.rmSync(tmpDir, { recursive: true, force: true })
  })


  describe('ConstellationStore elevated patterns', () => {
    it('saves and retrieves elevated patterns', () => {
      const pattern = makePattern({ achievedScore: 0.9 })
      store.saveElevatedPattern(pattern, 'session-1')

      const loaded = store.getElevatedPatterns()
      expect(loaded).toHaveLength(1)
      expect(loaded[0].id).toBe(pattern.id)
      expect(loaded[0].sourceHelixId).toBe('helix-test-1')
      expect(loaded[0].approach).toBe('implementation')
      expect(loaded[0].achievedScore).toBe(0.9)
      expect(loaded[0].relevantFiles).toEqual(['core/foo.ts', 'core/bar.ts'])
      expect(loaded[0].supportingRetrospectives).toHaveLength(1)
      expect(loaded[0].referenceCount).toBe(0)
    })

    it('filters by approach', () => {
      store.saveElevatedPattern(makePattern({ id: 'p1', approach: 'implementation' }))
      store.saveElevatedPattern(makePattern({ id: 'p2', approach: 'exploration' }))
      store.saveElevatedPattern(makePattern({ id: 'p3', approach: 'implementation' }))

      const implementation = store.getElevatedPatterns({ approach: 'implementation' })
      expect(implementation).toHaveLength(2)
      expect(implementation.every(p => p.approach === 'implementation')).toBe(true)

      const exploration = store.getElevatedPatterns({ approach: 'exploration' })
      expect(exploration).toHaveLength(1)
    })

    it('filters by minimum score', () => {
      store.saveElevatedPattern(makePattern({ id: 'low', achievedScore: 0.5 }))
      store.saveElevatedPattern(makePattern({ id: 'mid', achievedScore: 0.7 }))
      store.saveElevatedPattern(makePattern({ id: 'high', achievedScore: 0.9 }))

      const highOnly = store.getElevatedPatterns({ minScore: 0.8 })
      expect(highOnly).toHaveLength(1)
      expect(highOnly[0].id).toBe('high')

      const midAndUp = store.getElevatedPatterns({ minScore: 0.6 })
      expect(midAndUp).toHaveLength(2)
    })

    it('respects limit', () => {
      for (let i = 0; i < 10; i++) {
        store.saveElevatedPattern(makePattern({
          id: `p-${i}`,
          achievedScore: 0.5 + (i * 0.05),
        }))
      }

      const limited = store.getElevatedPatterns({ limit: 3 })
      expect(limited).toHaveLength(3)
      // Should be ordered by score descending
      expect(limited[0].achievedScore).toBeGreaterThanOrEqual(limited[1].achievedScore)
    })

    it('increments reference count', () => {
      const pattern = makePattern({ id: 'reftest' })
      store.saveElevatedPattern(pattern)

      store.incrementPatternReferenceCount('reftest')
      store.incrementPatternReferenceCount('reftest')
      store.incrementPatternReferenceCount('reftest')

      const loaded = store.getElevatedPatterns()
      expect(loaded[0].referenceCount).toBe(3)
    })

    it('prunes unreferenced old patterns but keeps referenced ones', () => {
      const oldTime = Date.now() - 400 * 24 * 60 * 60 * 1000 // 400 days ago
      const recentTime = Date.now() - 10 * 24 * 60 * 60 * 1000 // 10 days ago

      // Old unreferenced — should be pruned
      store.saveElevatedPattern(makePattern({
        id: 'old-unreferenced',
        elevatedAt: oldTime,
        referenceCount: 0,
      }))

      // Old referenced — should survive
      store.saveElevatedPattern(makePattern({
        id: 'old-referenced',
        elevatedAt: oldTime,
        referenceCount: 5,
      }))

      // Recent unreferenced — should survive
      store.saveElevatedPattern(makePattern({
        id: 'recent-unreferenced',
        elevatedAt: recentTime,
        referenceCount: 0,
      }))

      const pruned = store.pruneElevatedPatterns(180)
      expect(pruned).toBe(1) // Only old-unreferenced

      const remaining = store.getElevatedPatterns()
      expect(remaining).toHaveLength(2)
      expect(remaining.map(p => p.id).sort()).toEqual(['old-referenced', 'recent-unreferenced'])
    })

    it('uses INSERT OR REPLACE for idempotent saves', () => {
      const pattern = makePattern({ id: 'upsert-test', achievedScore: 0.7 })
      store.saveElevatedPattern(pattern)

      // Re-save with updated score
      store.saveElevatedPattern({ ...pattern, achievedScore: 0.95 })

      const loaded = store.getElevatedPatterns()
      expect(loaded).toHaveLength(1)
      expect(loaded[0].achievedScore).toBe(0.95)
    })
  })


  describe('CorpusTree onPatternElevated callback', () => {
    it('fires callback when a new pattern is elevated', () => {
      const tree = new CorpusTree(noopLogger)
      const elevated: ElevatedPattern[] = []

      tree.onPatternElevated = (pattern) => {
        elevated.push(pattern)
      }

      const pattern = makePattern()
      tree.elevatePattern(pattern)

      expect(elevated).toHaveLength(1)
      expect(elevated[0].id).toBe(pattern.id)
    })

    it('does not fire callback when callback is not set', () => {
      const tree = new CorpusTree(noopLogger)
      // Should not throw
      tree.elevatePattern(makePattern())
      expect(tree.getElevatedPatterns()).toHaveLength(1)
    })

    it('persists patterns through store via callback', () => {
      const tree = new CorpusTree(noopLogger)

      tree.onPatternElevated = (pattern) => {
        store.saveElevatedPattern(pattern, 'test-session')
      }

      tree.elevatePattern(makePattern({ id: 'callback-persist-1' }))
      tree.elevatePattern(makePattern({ id: 'callback-persist-2' }))

      // Verify both in-memory and persisted
      expect(tree.getElevatedPatterns()).toHaveLength(2)
      const stored = store.getElevatedPatterns()
      expect(stored).toHaveLength(2)
      expect(stored.map(p => p.id).sort()).toEqual(['callback-persist-1', 'callback-persist-2'])
    })
  })


  describe('Pipeline seeding behavior', () => {
    it('historical patterns can be loaded and seeded into a new tree', () => {
      // Simulate a previous Constellation that elevated patterns
      store.saveElevatedPattern(makePattern({ id: 'hist-1', achievedScore: 0.9 }))
      store.saveElevatedPattern(makePattern({ id: 'hist-2', achievedScore: 0.8 }))
      store.saveElevatedPattern(makePattern({ id: 'hist-3', achievedScore: 0.5 })) // Below 0.6 threshold

      // Simulate new Constellation loading historical patterns
      const tree = new CorpusTree(noopLogger)
      const historical = store.getElevatedPatterns({ minScore: 0.6, limit: 50 })
      for (const pattern of historical) {
        tree.elevatePattern(pattern)
      }

      expect(tree.getElevatedPatterns()).toHaveLength(2)
      expect(tree.getElevatedPatterns().map(p => p.id).sort()).toEqual(['hist-1', 'hist-2'])
    })

    it('seeding does not re-persist patterns when callback is set after seeding', () => {
      store.saveElevatedPattern(makePattern({ id: 'existing-1', achievedScore: 0.85 }))

      const tree = new CorpusTree(noopLogger)
      const persistedIds: string[] = []

      // Load historical patterns BEFORE setting callback (mirrors pipeline behavior)
      const historical = store.getElevatedPatterns({ minScore: 0.6, limit: 50 })
      for (const pattern of historical) {
        tree.elevatePattern(pattern)
      }

      // Set callback AFTER seeding
      tree.onPatternElevated = (pattern) => {
        persistedIds.push(pattern.id)
      }

      // New pattern should trigger the callback
      tree.elevatePattern(makePattern({ id: 'new-pattern' }))

      expect(persistedIds).toEqual(['new-pattern'])
      expect(tree.getElevatedPatterns()).toHaveLength(2)
    })
  })


  describe('Schema migration', () => {
    it('v2 to v3 migration creates elevated_patterns table', () => {
      // The store is already created with v3 schema. Verify the table exists
      // by checking we can save and load without errors.
      store.saveElevatedPattern(makePattern())
      const patterns = store.getElevatedPatterns()
      expect(patterns).toHaveLength(1)
    })
  })
})
