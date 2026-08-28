import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import Database from 'better-sqlite3'
import { MnemicField } from '../src/index.js'
import { mockLogger } from './helpers.js'

// Hoisted mock for reranker service — must be at top level for ESM
vi.mock('../src/vendor/core/intelligence/embeddings/reranker-service.js', () => ({
  getRerankerService: vi.fn(),
}))

import { getRerankerService } from '../src/vendor/core/intelligence/embeddings/reranker-service.js'

function makeInMemoryDb(): Database.Database {
  const db = new Database(':memory:')
  db.pragma('foreign_keys = ON')
  return db
}

function makeEmbedding(primary: number, dim = 8): number[] {
  const v = new Array(dim).fill(0)
  v[primary % dim] = 1.0
  return v
}

describe('MnemicField — Reranker Mode', () => {
  let field: MnemicField
  let db: Database.Database

  beforeEach(() => {
    db = makeInMemoryDb()
    field = new MnemicField(mockLogger(), db)
    vi.clearAllMocks()
  })

  afterEach(() => {
    field.close()
  })

  function buildSmallNetwork() {
    const a = field.store({ id: 'a', content: 'architecture patterns for distributed systems', nodeType: 'fact', embedding: makeEmbedding(0), x: 0, y: 0 })
    const b = field.store({ id: 'b', content: 'memory design with spreading activation', nodeType: 'fact', embedding: makeEmbedding(1), x: 1, y: 0 })
    const c = field.store({ id: 'c', content: 'activation spreading across neural fields', nodeType: 'fact', embedding: makeEmbedding(2), x: 2, y: 0 })
    const d = field.store({ id: 'd', content: 'unrelated island topic', nodeType: 'fact', embedding: makeEmbedding(3), x: 100, y: 100 })
    field.connect({ sourceId: 'a', targetId: 'b', edgeType: 'similar_to', weight: 0.8 })
    field.connect({ sourceId: 'b', targetId: 'c', edgeType: 'caused_by', weight: 0.9 })
    return { a, b, c, d }
  }

  it('setRerankerMode stores the mode', () => {
    field.setRerankerMode('local')
    field.setRerankerMode('off')
    field.setRerankerMode('llm')
  })

  it('retrieve falls back to kindling when local reranker is unavailable', async () => {
    buildSmallNetwork()
    field.setRerankerMode('local')

    // Mock reranker as unavailable
    vi.mocked(getRerankerService).mockReturnValue({
      available: false,
      rerank: vi.fn(),
    } as any)

    const hits = await field.retrieve('architecture', { limit: 3 })
    expect(hits.length).toBeGreaterThan(0)
    expect(hits[0].id).toBeTruthy()
    expect(hits[0].content).toBeTruthy()
    expect(hits[0].score).toBeGreaterThanOrEqual(0)
  })

  it('retrieve falls back to kindling when mode is off', async () => {
    buildSmallNetwork()
    field.setRerankerMode('off')

    const hits = await field.retrieve('architecture', { limit: 3 })
    expect(hits.length).toBeGreaterThan(0)
  })

  it('retrieve with local reranker scores via mock reranker', async () => {
    // Mock reranker to return specific scores
    // Note: kindling may filter to fewer candidates than stored documents,
    // so we use a dynamic mock that matches the actual candidate indices.
    vi.mocked(getRerankerService).mockReturnValue({
      available: true,
      rerank: vi.fn().mockImplementation((_query: string, documents: string[]) => {
        // Document c (about birds) should be most relevant
        const results = documents.map((doc, i) => ({
          index: i,
          relevanceScore: doc.includes('birds') ? 0.95 : 0.3,
        }))
        return Promise.resolve(results)
      }),
    } as any)

    const freshField = new MnemicField(mockLogger(), makeInMemoryDb())
    freshField.store({ id: 'a', content: 'alpha document about cats', nodeType: 'fact', embedding: makeEmbedding(0), x: 0, y: 0 })
    freshField.store({ id: 'b', content: 'beta document about dogs', nodeType: 'fact', embedding: makeEmbedding(1), x: 1, y: 0 })
    freshField.store({ id: 'c', content: 'gamma document about birds', nodeType: 'fact', embedding: makeEmbedding(2), x: 2, y: 0 })
    freshField.connect({ sourceId: 'a', targetId: 'b', edgeType: 'similar_to', weight: 0.8 })
    freshField.setRerankerMode('local')

    const hits = await freshField.retrieve('birds', { limit: 3 })
    expect(hits.length).toBeGreaterThan(0)
    expect(hits[0].id).toBe('c')
    expect(hits[0].score).toBeCloseTo(0.95, 2)

    freshField.close()
  })
})
