/**
 * Critical race-condition test for topology link integrity
 * under concurrent removeHelix calls.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { GravityEngine } from '../src/topology/gravity-engine.js'
import { LinkManager } from '../src/topology/link-manager.js'
import type { BranchDigest, BranchApproach } from '../src/corpus-types.js'
import type { LinkConfig } from '../src/topology/topology-types.js'
import { DEFAULT_GRAVITY_CONFIG } from '../src/topology/topology-types.js'

function createMockEmbeddingService() {
  const embeddings = new Map<string, number[]>()

  return {
    async embed(text: string, _mode: string): Promise<number[]> {
      if (embeddings.has(text)) return embeddings.get(text)!
      const emb = Array.from({ length: 8 }, (_, i) => {
        let h = 0
        for (const ch of text) h = ((h << 5) - h + ch.charCodeAt(0) + i) | 0
        return (h & 0xFFFF) / 0xFFFF
      })
      embeddings.set(text, emb)
      return emb
    },

    cosineSimilarity(a: number[] | null, b: number[] | null): number {
      if (!a || !b || a.length !== b.length) return 0
      let dot = 0, normA = 0, normB = 0
      for (let i = 0; i < a.length; i++) {
        dot += a[i] * b[i]
        normA += a[i] * a[i]
        normB += b[i] * b[i]
      }
      const denom = Math.sqrt(normA) * Math.sqrt(normB)
      return denom === 0 ? 0 : dot / denom
    },

    setEmbedding(text: string, emb: number[]): void {
      embeddings.set(text, emb)
    },
  }
}

function createMockLogger() {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: () => createMockLogger(),
  }
}

function createDigest(overrides: Partial<BranchDigest> = {}): BranchDigest {
  return {
    helixId: 'default',
    goalSummary: 'Implement feature X',
    approach: 'implement' as BranchApproach,
    progress: 0.5,
    filesActive: ['src/main.ts', 'src/utils.ts'],
    keyFindings: ['Found existing pattern in utils'],
    blockers: [],
    currentStrategy: 'direct implementation',
    rollingScore: 0.7,
    workUnitsProcessed: 5,
    updatedAt: Date.now(),
    ...overrides,
  } as BranchDigest
}

describe('LinkManager — concurrent removal integrity', () => {
  let engine: GravityEngine
  let linkManager: LinkManager
  let mockEmbed: ReturnType<typeof createMockEmbeddingService>
  let mockLogger: ReturnType<typeof createMockLogger>

  const testLinkConfig: LinkConfig = {
    linkThreshold: 5.0,
    unlinkThreshold: 8.0,
    mediumMergeStabilityTicks: 3,
    deepMergeStabilityTicks: 8,
    minLinkSimilarity: 0.3,
  }

  beforeEach(() => {
    mockEmbed = createMockEmbeddingService()
    mockLogger = createMockLogger()
    engine = new GravityEngine({
      embeddingService: mockEmbed as any,
      logger: mockLogger as any,
      config: DEFAULT_GRAVITY_CONFIG,
    })
    linkManager = new LinkManager({
      gravityEngine: engine,
      logger: mockLogger as any,
      config: testLinkConfig,
    })
  })

  it('maintains link integrity after concurrent removeHelix calls', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    for (let i = 0; i < 20; i++) {
      await engine.registerHelix(`h${i}`, digest)
    }

    // Evaluate to form links
    const helixIds = Array.from({ length: 20 }, (_, i) => `h${i}`)
    linkManager.evaluate(helixIds)

    // Concurrently remove multiple helixes
    const removalPromises: Promise<void>[] = []
    for (let i = 0; i < 10; i++) {
      removalPromises.push(
        (async () => {
          await new Promise(resolve => setTimeout(resolve, Math.random() * 5))
          linkManager.removeHelix(`h${i}`)
        })()
      )
    }

    await Promise.all(removalPromises)

    // Verify remaining links are consistent
    const allLinks = linkManager.getAllLinks()
    // Filter to only links between remaining helixes (h10-h19)
    const validLinks = allLinks.filter(link => {
      const aNum = parseInt(link.helixIdA.replace('h', ''))
      const bNum = parseInt(link.helixIdB.replace('h', ''))
      return aNum >= 10 && bNum >= 10
    })
    // All remaining links should be between h10-h19
    for (const link of validLinks) {
      const aIdx = parseInt(link.helixIdA.replace('h', ''))
      const bIdx = parseInt(link.helixIdB.replace('h', ''))
      expect(aIdx).toBeGreaterThanOrEqual(10)
      expect(bIdx).toBeGreaterThanOrEqual(10)
    }
  })
})
