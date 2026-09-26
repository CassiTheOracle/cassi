import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Database from 'better-sqlite3'
import { MnemicField } from '../src/index.js'
import { ENGRAM_TYPES } from '../src/types.js'
import { mockLogger } from './helpers.js'

function makeInMemoryDb(): Database.Database {
  const db = new Database(':memory:')
  db.pragma('foreign_keys = ON')
  return db
}

describe('Mnemic Field — Engram Types & Initial Potentiation', () => {
  let field: MnemicField
  let db: Database.Database

  beforeEach(() => {
    db = makeInMemoryDb()
    field = new MnemicField(mockLogger(), db)
  })

  afterEach(() => {
    field.close()
  })

  describe('engram types', () => {
    it('includes concern type for risk/issue tracking', () => {
      expect(ENGRAM_TYPES).toContain('concern')
    })

    it('includes anomaly type for bug/defect tracking', () => {
      expect(ENGRAM_TYPES).toContain('anomaly')
    })

    it('does not include board-entry (replaced by native types)', () => {
      expect(ENGRAM_TYPES).not.toContain('board-entry')
    })

    it('stores a concern engram', () => {
      const e = field.store({
        content: 'API rate limits may cause cascading failures',
        nodeType: 'concern',
        tags: ['topic:api-redesign'],
      })
      expect(e.nodeType).toBe('concern')
      expect(e.tags).toContain('topic:api-redesign')
    })

    it('stores an anomaly engram', () => {
      const e = field.store({
        content: 'NullPointerException in request handler',
        nodeType: 'anomaly',
        tags: ['topic:bugs', 'severity:critical'],
      })
      expect(e.nodeType).toBe('anomaly')
    })

    it('stores a decision engram with topic tag', () => {
      const e = field.store({
        content: 'Use Cortex for working memory, Mnemic Field for persistence',
        nodeType: 'decision',
        tags: ['topic:architecture'],
      })
      expect(e.nodeType).toBe('decision')
      expect(e.tags).toContain('topic:architecture')
    })
  })

  describe('initialPotentiation', () => {
    it('defaults to 0', () => {
      const e = field.store({ content: 'normal memory', nodeType: 'fact' })
      expect(e.potentiation).toBe(0)
    })

    it('accepts custom initial potentiation', () => {
      const e = field.store({
        content: 'important memory',
        nodeType: 'fact',
        initialPotentiation: 0.8,
      })
      expect(e.potentiation).toBe(0.8)
    })

    it('pins coordination data with high potentiation', () => {
      const e = field.store({
        content: 'Critical decision: migrate to Cortex',
        nodeType: 'decision',
        initialPotentiation: 1.0,
        tags: ['topic:wave7'],
      })
      expect(e.potentiation).toBe(1.0)
    })
  })

  describe('topic-based coordination via native store/search', () => {
    it('stores and retrieves by topic using searchText', () => {
      field.store({
        content: 'Found: blackboard has 15 consumer files',
        nodeType: 'episode',
        tags: ['topic:blackboard-removal'],
        initialPotentiation: 1.0,
      })
      field.store({
        content: 'Decided: use Cortex for per-session memory',
        nodeType: 'decision',
        tags: ['topic:blackboard-removal'],
        initialPotentiation: 1.0,
      })
      field.store({
        content: 'Unrelated fact about weather',
        nodeType: 'fact',
      })

      const results = field.searchText('blackboard')
      expect(results.length).toBeGreaterThanOrEqual(2)
      expect(results.every(r => r.engram.content.includes('blackboard') || r.engram.tags.some(t => t.includes('blackboard')))).toBe(true)
    })

    it('uses nodeType to distinguish coordination categories', () => {
      field.store({ content: 'observation about API', nodeType: 'episode', tags: ['topic:api'] })
      field.store({ content: 'risk about API rate limits', nodeType: 'concern', tags: ['topic:api'] })
      field.store({ content: 'chose REST over GraphQL', nodeType: 'decision', tags: ['topic:api'] })

      const all = field.list(100, 'decision')
      expect(all.length).toBeGreaterThanOrEqual(1)
      expect(all[0].nodeType).toBe('decision')
    })
  })
})
