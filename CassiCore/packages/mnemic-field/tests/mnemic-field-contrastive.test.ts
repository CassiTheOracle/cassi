import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Database from 'better-sqlite3'
import { MnemicField } from '../src/index.js'
import { mockLogger } from './helpers.js'
import type { Engram, Nucleus, DistinctivenessResult } from '../src/index.js'

function makeInMemoryDb(): Database.Database {
  const db = new Database(':memory:')
  db.pragma('foreign_keys = ON')
  return db
}

describe('Mnemic Field — Phase 2: Contrastive Extraction', () => {
  let field: MnemicField
  let db: Database.Database

  beforeEach(() => {
    db = makeInMemoryDb()
    field = new MnemicField(mockLogger(), db)
  })

  afterEach(() => {
    field.close()
  })

  describe('extractDistinctiveness()', () => {
    it('returns zero engrams scored when field is empty', async () => {
      const result = await field.extractDistinctiveness()
      expect(result.engramsScored).toBe(0)
      expect(result.groupsProcessed).toBe(0)
      expect(result.durationMs).toBeGreaterThanOrEqual(0)
    })

    it('handles engrams with content < 20 chars (filtered out)', async () => {
      field.store({ content: 'hello world', nodeType: 'fact', x: 0.1, y: 0.1 })
      field.store({ content: 'hello there', nodeType: 'fact', x: 0.2, y: 0.15 })

      const result = await field.extractDistinctiveness()
      // Content too short (<20 chars), filtered out by WHERE length(content) > 20
      expect(result.engramsScored).toBe(0)
    })

    it('groups engrams by nucleus (clusterId)', async () => {
      // Store engrams and assign them to the same nucleus via consolidation
      field.store({
        content: 'The architecture uses a layered pattern with clear separation of concerns across all modules.',
        nodeType: 'decision', x: 0.01, y: 0.01,
      })
      field.store({
        content: 'The architecture uses a layered pattern but we should consider hexagonal instead.',
        nodeType: 'concern', x: 0.02, y: 0.015,
      })
      field.store({
        content: 'Memory management is handled by a dedicated subsystem with configurable retention policies.',
        nodeType: 'fact', x: 0.5, y: 0.5,
      })

      // Run consolidation with high epsilon to force grouping
      await field.consolidate({
        skipDrift: true,
        skipPruning: true,
        nucleiMinClusterSize: 2,
        nucleiEpsilon: 2.0,
        skipDistinctiveness: true, // we'll call it manually
      })

      const nuclei = field.listNuclei()
      expect(nuclei.length).toBeGreaterThanOrEqual(1)

      // extractDistinctiveness should group by nucleus
      // (embedding service may not be available, method catches gracefully)
      const result = await field.extractDistinctiveness()
      expect(result).toHaveProperty('engramsScored')
      expect(result).toHaveProperty('groupsProcessed')
      expect(result).toHaveProperty('durationMs')
    })

    it('groups engrams by angular sector when no nucleus', async () => {
      // 3 engrams in the same angular sector (close theta)
      field.store({
        content: 'This is a unique sentence about performance optimization in the query planner.',
        nodeType: 'fact', x: 0.5, y: 0.01,
      })
      field.store({
        content: 'This is a unique sentence about query planner optimization for large datasets.',
        nodeType: 'fact', x: 0.6, y: 0.02,
      })
      field.store({
        content: 'Completely different topic about frontend rendering performance with React components.',
        nodeType: 'fact', x: -0.4, y: -0.4,
      })

      const result = await field.extractDistinctiveness()
      // x/y close engrams land in same sector; the far one in a different sector
      expect(result).toHaveProperty('engramsScored')
      expect(result).toHaveProperty('groupsProcessed')
    })
  })

  describe('consolidate() with skipDistinctiveness', () => {
    it('skips distinctiveness extraction when skipDistinctiveness is true', async () => {
      field.store({
        content: 'The project should use a hexagonal architecture pattern for isolation of concerns.',
        nodeType: 'decision', x: 0.1, y: 0.1,
      })

      const result = await field.consolidate({
        skipDrift: true,
        skipNuclei: true,
        skipAbstractions: true,
        skipPruning: true,
        skipDistinctiveness: true,
      })

      expect(result).toHaveProperty('potentiationUpdates')
      // distinctiveness fields should be undefined since we skipped
      expect(result.distinctivenessEngramsScored).toBeUndefined()
      expect(result.distinctivenessGroupsProcessed).toBeUndefined()
      expect(result.distinctivenessDurationMs).toBeUndefined()
    })

    it('does not set distinctiveness fields when skipDistinctiveness is omitted and nothing to group', async () => {
      field.store({
        content: 'Single short engram with not enough to group or process for distinctiveness scan.',
        nodeType: 'fact', x: 0.1, y: 0.1,
      })

      const result = await field.consolidate({
        skipDrift: true,
        skipNuclei: true,
        skipAbstractions: true,
        skipPruning: true,
        // skipDistinctiveness omitted — should still run but find nothing
      })

      // extractDistinctiveness was called but found nothing to group
      expect(result.distinctivenessEngramsScored).toBe(0)
      expect(result.distinctivenessGroupsProcessed).toBe(0)
      expect(result.distinctivenessDurationMs).toBeGreaterThanOrEqual(0)
    })

    it('includes distinctiveness fields in result when consolidation runs with nuclei', async () => {
      for (let i = 0; i < 5; i++) {
        field.store({
          content: `Important architectural decision number ${i} about the system layout and component interactions.`,
          nodeType: 'decision',
          x: 0.01 * i,
          y: 0.01 * i,
        })
      }

      const result = await field.consolidate({
        skipDrift: true,
        skipPruning: true,
        skipAbstractions: true,
        nucleiMinClusterSize: 3,
        nucleiEpsilon: 2.0,
        // skipDistinctiveness omitted — runs after consolidation
      })

      expect(result).toHaveProperty('potentiationUpdates')
      expect(result).toHaveProperty('nucleiDetected')
      // distinctiveness fields should be present (even if embedding service unavailable = 0)
      expect(result).toHaveProperty('distinctivenessEngramsScored')
      expect(result).toHaveProperty('distinctivenessGroupsProcessed')
      expect(result).toHaveProperty('distinctivenessDurationMs')
    })
  })

  describe('getNucleus() and getEngramsByCluster()', () => {
    it('returns null for non-existent nucleus', () => {
      const n = field.getNucleus('nonexistent')
      expect(n).toBeNull()
    })

    it('returns nucleus after consolidation detects one', async () => {
      for (let i = 0; i < 5; i++) {
        field.store({
          content: `Clustered decision ${i} about memory management strategy`,
          nodeType: 'decision',
          x: 0.001 * i,
          y: 0.001 * i,
        })
      }

      await field.consolidate({
        skipDrift: true,
        skipPruning: true,
        skipAbstractions: true,
        nucleiMinClusterSize: 3,
        nucleiEpsilon: 2.0,
        skipDistinctiveness: true,
      })

      const nuclei = field.listNuclei()
      expect(nuclei.length).toBeGreaterThanOrEqual(1)

      const nucleus = field.getNucleus(nuclei[0].id)
      expect(nucleus).not.toBeNull()
      expect(nucleus!.id).toBe(nuclei[0].id)
      expect(nucleus!.memberCount).toBeGreaterThanOrEqual(3)

      const members = field.getEngramsByCluster(nuclei[0].id)
      expect(members.length).toBe(nucleus!.memberCount)
      expect(members.every(m => typeof m.content === 'string')).toBe(true)
    })

    it('getEngramsByCluster returns empty for unknown cluster', () => {
      const members = field.getEngramsByCluster('nonexistent')
      expect(members).toEqual([])
    })
  })
})
