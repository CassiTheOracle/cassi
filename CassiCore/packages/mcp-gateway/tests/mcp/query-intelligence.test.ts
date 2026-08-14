import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  normalizeQuery,
  extractKeyTerms,
  extractEntities,
  buildQueryVariants,
  mergeAndRank,
  recoverFromEmpty,
  formatTopRelevantEntry,
  searchMultiVariant,
  MIN_TOP_RELEVANT_SCORE,
  MIN_SOURCE_DISPLAY_SCORE,
  type RankedSearchResult,
} from '../../src/gateway/query-intelligence.js'


function makeMemoryResult(id: string, content: string, score = 0.8, sessionId = 'sess-1'): unknown {
  return { entry: { id, type: 'fact', content, createdAt: Date.now(), sessionId }, score }
}

function makeArchiveResult(id: string, content: string, score = 0.75, sessionId = 'sess-2'): unknown {
  return {
    entry: { id, type: 'conversation', content, timestamp: Date.now(), sessionId },
    score,
  }
}

function makeIndexResult(ref: string, content: string, rank = 0.7): unknown {
  return { entry: { ref, role: 'assistant', blockType: 'text', content, timestamp: Date.now() }, rank }
}


describe('normalizeQuery', () => {
  it('collapses multiple spaces', () => {
    expect(normalizeQuery('hello   world')).toBe('hello   world'.replace(/\s{2,}/g, ' '))
  })

  it('removes newlines', () => {
    const q = 'line one\nline two\r\nline three'
    expect(normalizeQuery(q)).not.toMatch(/[\r\n]/)
  })

  it('strips smart quotes', () => {
    expect(normalizeQuery('\u201chello\u201d')).not.toMatch(/[\u201c\u201d]/)
  })

  it('preserves underscores, hyphens, slashes', () => {
    const q = 'cassi_do core/intelligence/memory.ts github-copilot'
    const n = normalizeQuery(q)
    expect(n).toContain('cassi_do')
    expect(n).toContain('core/intelligence/memory.ts')
    expect(n).toContain('github-copilot')
  })
})


describe('extractKeyTerms', () => {
  it('filters stop words', () => {
    const terms = extractKeyTerms('the quick brown fox and the lazy dog')
    expect(terms).not.toContain('the')
    expect(terms).not.toContain('and')
    expect(terms).toContain('quick')
    expect(terms).toContain('brown')
  })

  it('filters words shorter than 3 chars', () => {
    const terms = extractKeyTerms('do it now')
    expect(terms).not.toContain('do')
    expect(terms).not.toContain('it')
  })

  it('returns at most 8 terms', () => {
    const q = 'alpha beta gamma delta epsilon zeta eta theta iota kappa'
    expect(extractKeyTerms(q).length).toBeLessThanOrEqual(8)
  })

  it('lowercases terms', () => {
    const terms = extractKeyTerms('CassiCore Intelligence Memory')
    expect(terms).toContain('cassicore')
  })
})


describe('extractEntities', () => {
  it('extracts session refs', () => {
    const e = extractEntities('See S0#M3.B1.P2 and also S1')
    expect(e.sessionRefs).toContain('S0#M3.B1.P2')
    expect(e.sessionRefs).toContain('S1')
  })

  it('extracts cassi_ tool names', () => {
    const e = extractEntities('I called cassi_agent and cassi_do yesterday')
    expect(e.toolNames).toContain('cassi_agent')
    expect(e.toolNames).toContain('cassi_do')
  })

  it('extracts gitnexus_ and serena_ tools', () => {
    const e = extractEntities('used gitnexus_query and serena_find_symbol')
    expect(e.toolNames).toContain('gitnexus_query')
    expect(e.toolNames).toContain('serena_find_symbol')
  })

  it('extracts core primitives: bash, read, grep', () => {
    const e = extractEntities('ran bash and grep on the file with read')
    expect(e.toolNames).toContain('bash')
    expect(e.toolNames).toContain('grep')
    expect(e.toolNames).toContain('read')
  })

  it('extracts file paths', () => {
    const e = extractEntities('look at core/intelligence/memory/index.ts and mcp/gateway/do-tool.ts')
    expect(e.filePaths.some(p => p.includes('core/intelligence'))).toBe(true)
    expect(e.filePaths.some(p => p.includes('mcp/gateway'))).toBe(true)
  })

  it('extracts known providers', () => {
    const e = extractEntities('switched from anthropic to github-copilot')
    expect(e.providers).toContain('anthropic')
    expect(e.providers).toContain('github-copilot')
  })

  it('returns empty arrays when nothing matches', () => {
    const e = extractEntities('some generic query with no patterns')
    expect(e.sessionRefs).toHaveLength(0)
    expect(e.toolNames).toHaveLength(0)
    expect(e.providers).toHaveLength(0)
  })

  it('deduplicates tool names', () => {
    const e = extractEntities('cassi_do cassi_do cassi_do')
    expect(e.toolNames.filter(t => t === 'cassi_do')).toHaveLength(1)
  })
})


describe('buildQueryVariants', () => {
  it('always includes the exact variant', () => {
    const variants = buildQueryVariants('test query', { sessionRefs: [], toolNames: [], filePaths: [], providers: [] }, null)
    expect(variants[0].label).toBe('exact')
    expect(variants[0].query).toBe('test query')
    expect(variants[0].weight).toBe(1.0)
  })

  it('adds entity variant when entities found', () => {
    const entities = { sessionRefs: [], toolNames: ['cassi_do', 'bash'], filePaths: [], providers: [] }
    const variants = buildQueryVariants('run cassi_do and bash', entities, null)
    const entityVariant = variants.find(v => v.label === 'entity')
    expect(entityVariant).toBeDefined()
    expect(entityVariant!.query).toContain('cassi_do')
    expect(entityVariant!.weight).toBe(0.8)
  })

  it('adds expanded variant when metadata has related terms', () => {
    const metadata = {
      tags:     [{ name: 'mem', count: 5 }, { name: 'archive', count: 3 }],
      entities: [{ name: 'search', count: 2 }],
      topics:   [{ name: 'context enrichment', count: 4 }],
      fetchedAt: Date.now(),
    }
    const entities = { sessionRefs: [], toolNames: [], filePaths: [], providers: [] }
    // 'memory' contains 'mem', 'search' is an exact entity match
    const variants = buildQueryVariants('memory search', entities, metadata)
    const expandedVariant = variants.find(v => v.label === 'expanded')
    expect(expandedVariant).toBeDefined()
    expect(expandedVariant!.weight).toBe(0.7)
  })

  it('returns only exact variant when no entities and no metadata', () => {
    const entities = { sessionRefs: [], toolNames: [], filePaths: [], providers: [] }
    const variants = buildQueryVariants('generic query', entities, null)
    expect(variants).toHaveLength(1)
    expect(variants[0].label).toBe('exact')
  })

  it('caps expanded terms at 6', () => {
    const metadata = {
      tags:     Array.from({ length: 10 }, (_, i) => ({ name: `query-tag-${i}`, count: 5 })),
      entities: [],
      topics:   [],
      fetchedAt: Date.now(),
    }
    const entities = { sessionRefs: [], toolNames: [], filePaths: [], providers: [] }
    const variants = buildQueryVariants('query', entities, metadata)
    const expanded = variants.find(v => v.label === 'expanded')
    if (expanded) {
      // Expanded query shouldn't have more than 6 extra terms
      const extraTerms = expanded.query.replace('query', '').trim().split(' ').filter(Boolean)
      expect(extraTerms.length).toBeLessThanOrEqual(6)
    }
  })
})


describe('mergeAndRank', () => {
  const makeRanked = (source: 'memory' | 'archive' | 'index', score: number, sessionId = 's1'): RankedSearchResult => ({
    raw: { entry: { id: `${source}-${score}`, content: 'x', sessionId, timestamp: Date.now() }, score },
    source,
    rawScore: score,
    baseScore: score,
    finalScore: 0,
    variantLabel: 'exact',
  })

  it('returns top N results sorted by finalScore', () => {
    const results = [
      makeRanked('memory',  0.9, 's1'),
      makeRanked('archive', 0.5, 's2'),
      makeRanked('index',   0.7, 's3'),
    ]
    const ranked = mergeAndRank(results, 'query', 2)
    expect(ranked).toHaveLength(2)
    expect(ranked[0].finalScore).toBeGreaterThanOrEqual(ranked[1].finalScore)
  })

  it('assigns higher finalScore to recent entries', () => {
    const old = { ...makeRanked('memory', 0.8, 's1') }
    ;(old.raw as any).entry.timestamp = Date.now() - 30 * 24 * 3600 * 1000 // 30 days ago
    const fresh = makeRanked('archive', 0.8, 's2')

    const ranked = mergeAndRank([old, fresh], 'query', 2)
    expect(ranked[0].source).toBe('archive') // fresh wins on recency
  })

  it('boosts recency weight for "recent" queries', () => {
    const old   = { ...makeRanked('memory',  0.95, 's1') }
    const fresh = { ...makeRanked('archive', 0.6,  's2') }
    ;(old.raw as any).entry.timestamp = Date.now() - 30 * 24 * 3600 * 1000

    const ranked = mergeAndRank([old, fresh], 'show me recent changes', 2)
    // With recency boosted, the fresh lower-score result should beat the stale high-score one
    expect(ranked[0].source).toBe('archive')
  })

  it('applies diversity bonus — results from different sessions rank higher', () => {
    // Three results from same session vs one from a different session
    const same1 = makeRanked('memory',  0.85, 'sess-A')
    const same2 = makeRanked('archive', 0.84, 'sess-A')
    const same3 = makeRanked('index',   0.83, 'sess-A')
    const diff  = makeRanked('memory',  0.70, 'sess-B')

    const ranked = mergeAndRank([same1, same2, same3, diff], 'query', 4)
    // The diff session result should have higher finalScore than its baseScore suggests
    const diffRanked = ranked.find(r => (r.raw as any).entry.sessionId === 'sess-B')
    expect(diffRanked).toBeDefined()
    expect(diffRanked!.finalScore).toBeGreaterThan(0.70 * 0.7) // got diversity bonus
  })

  it('returns empty array for empty input', () => {
    expect(mergeAndRank([], 'query', 5)).toEqual([])
  })
})


describe('recoverFromEmpty', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('returns suggested terms from metadata when results are empty', async () => {
    ;(globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => [],
    })

    const metadata = {
      tags:     [{ name: 'cassi-do-redesign', count: 3 }],
      entities: [{ name: 'query intelligence', count: 2 }],
      topics:   [{ name: 'context enrichment', count: 4 }],
      fetchedAt: Date.now(),
    }

    const result = await recoverFromEmpty(
      'http://localhost:7433',
      'enrich improvements',
      ['enrich', 'improvements', 'context'],
      metadata,
    )

    expect(result.suggestedTerms.length).toBeGreaterThan(0)
  })

  it('returns broad results when archive search returns relevant entries', async () => {
    const fakeResults = [
      { entry: { id: '1', type: 'conversation', content: 'related content' }, score: 0.4 },
      { entry: { id: '2', type: 'insight',      content: 'relevant insight'  }, score: 0.3 },
      { entry: { id: '3', type: 'event',        content: 'low score event'   }, score: 0.1 }, // below threshold
    ]
    ;(globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => fakeResults,
    })

    const result = await recoverFromEmpty('http://localhost:7433', 'test query', ['test', 'query'], null)

    // Only entries with score >= 0.25 should be included
    expect(result.usedBroad).toBe(true)
    expect(result.results.length).toBe(2) // score 0.4 and 0.3 pass; 0.1 filtered
  })

  it('degrades gracefully when fetch fails', async () => {
    ;(globalThis.fetch as any).mockRejectedValue(new Error('network error'))

    const result = await recoverFromEmpty('http://localhost:7433', 'query', ['query'], null)

    expect(result.results).toEqual([])
    expect(result.suggestedTerms).toEqual([])
  }, 15_000)
})


describe('formatTopRelevantEntry', () => {
  it('formats a memory result with source label and score', () => {
    const r: RankedSearchResult = {
      raw: { entry: { id: '1', type: 'fact', content: 'some memory content', createdAt: Date.now() }, score: 0.9 },
      source: 'memory',
      rawScore: 0.9,
      baseScore: 0.9,
      finalScore: 0.87,
      variantLabel: 'exact',
    }
    const formatted = formatTopRelevantEntry(r, 0)
    expect(formatted).toMatch(/\[Memory\/fact\]/)
    expect(formatted).toMatch(/87%/)
    expect(formatted).toContain('some memory content')
  })

  it('formats an archive result with analysis summary when available', () => {
    const r: RankedSearchResult = {
      raw: {
        entry: {
          id: '2',
          type: 'conversation',
          content: 'long conversation content',
          analysis: { summary: 'brief summary of the conversation' },
          timestamp: Date.now(),
        },
        score: 0.8,
      },
      source: 'archive',
      rawScore: 0.8,
      baseScore: 0.8,
      finalScore: 0.76,
      variantLabel: 'exact',
    }
    const formatted = formatTopRelevantEntry(r, 1)
    expect(formatted).toMatch(/\[Archive\/conversation\]/)
    expect(formatted).toContain('brief summary') // prefers analysis.summary
    expect(formatted).not.toContain('long conversation content')
  })

  it('formats an index result with session ref', () => {
    const r: RankedSearchResult = {
      raw: {
        entry: { ref: 'S0#M3.B0.P1', role: 'assistant', blockType: 'text', content: 'relevant paragraph', timestamp: Date.now() },
        rank: 0.65,
      },
      source: 'index',
      rawScore: 0.65,
      baseScore: 0.65,
      finalScore: 0.60,
      variantLabel: 'exact',
    }
    const formatted = formatTopRelevantEntry(r, 2)
    expect(formatted).toMatch(/\[Session\/S0#M3\.B0\.P1\]/)
    expect(formatted).toMatch(/60%/)
    expect(formatted).toContain('relevant paragraph')
  })

  it('includes an age label for recent entries', () => {
    const r: RankedSearchResult = {
      raw: { entry: { id: '3', type: 'fact', content: 'recent memory', createdAt: Date.now() - 2 * 3600_000 }, score: 0.7 },
      source: 'memory',
      rawScore: 0.7,
      baseScore: 0.7,
      finalScore: 0.65,
      variantLabel: 'exact',
    }
    const formatted = formatTopRelevantEntry(r, 0)
    expect(formatted).toMatch(/\d+h ago/)
  })
})


describe('searchMultiVariant', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('deduplicates results with the same id across variants', async () => {
    const sharedEntry = { id: 'shared-1', type: 'fact', content: 'shared', createdAt: Date.now() }
    ;(globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => [{ entry: sharedEntry, score: 0.8 }],
    })

    const variants = [
      { query: 'original query', weight: 1.0, label: 'exact' as const },
      { query: 'expanded query',  weight: 0.7, label: 'expanded' as const },
    ]

    const results = await searchMultiVariant('memory', 'http://localhost:7433', variants, 5)
    // Despite two variants both returning the same entry, it should appear once
    const ids = results.map(r => ((r.raw as any)?.entry ?? r.raw as any)?.id)
    expect(ids.filter(id => id === 'shared-1')).toHaveLength(1)
  })

  it('scales baseScore by variant weight', async () => {
    ;(globalThis.fetch as any)
      .mockResolvedValueOnce({ ok: true, json: async () => [{ entry: { id: 'a', content: 'x' }, score: 1.0 }] })
      .mockResolvedValueOnce({ ok: true, json: async () => [{ entry: { id: 'b', content: 'y' }, score: 1.0 }] })

    const variants = [
      { query: 'q1', weight: 1.0, label: 'exact' as const },
      { query: 'q2', weight: 0.7, label: 'expanded' as const },
    ]

    const results = await searchMultiVariant('archive', 'http://localhost:7433', variants, 5)
    const exactResult    = results.find(r => ((r.raw as any)?.entry?.id) === 'a')
    const expandedResult = results.find(r => ((r.raw as any)?.entry?.id) === 'b')

    expect(exactResult?.baseScore).toBeCloseTo(1.0)
    expect(expandedResult?.baseScore).toBeCloseTo(0.7)
  })

  it('returns empty array when all variants fail', async () => {
    ;(globalThis.fetch as any).mockRejectedValue(new Error('network error'))

    const variants = [{ query: 'q', weight: 1.0, label: 'exact' as const }]
    const results = await searchMultiVariant('memory', 'http://localhost:7433', variants, 5)
    expect(results).toEqual([])
  }, 15_000)

  it('stores rawScore on each result', async () => {
    ;(globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => [{ entry: { id: 'r1', content: 'x' }, score: 0.85 }],
    })

    const variants = [{ query: 'q', weight: 0.8, label: 'entity' as const }]
    const results = await searchMultiVariant('memory', 'http://localhost:7433', variants, 5)
    expect(results[0].rawScore).toBeCloseTo(0.85)
    expect(results[0].baseScore).toBeCloseTo(0.68) // 0.85 * 0.8
  })
})


describe('threshold constants', () => {
  it('MIN_TOP_RELEVANT_SCORE is in a reasonable range', () => {
    expect(MIN_TOP_RELEVANT_SCORE).toBeGreaterThanOrEqual(0.5)
    expect(MIN_TOP_RELEVANT_SCORE).toBeLessThanOrEqual(0.9)
  })

  it('MIN_SOURCE_DISPLAY_SCORE is lower than MIN_TOP_RELEVANT_SCORE', () => {
    expect(MIN_SOURCE_DISPLAY_SCORE).toBeLessThan(MIN_TOP_RELEVANT_SCORE)
  })

  it('MIN_SOURCE_DISPLAY_SCORE is in a reasonable range', () => {
    expect(MIN_SOURCE_DISPLAY_SCORE).toBeGreaterThanOrEqual(0.3)
    expect(MIN_SOURCE_DISPLAY_SCORE).toBeLessThanOrEqual(0.7)
  })
})
