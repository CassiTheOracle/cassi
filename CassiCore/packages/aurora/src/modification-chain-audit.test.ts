/**
 * Tests for Substrate Modification Compounding Audit (SMCA).
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { unlinkSync, existsSync, mkdirSync } from 'node:fs'
import { randomBytes } from 'node:crypto'
import * as path from 'node:path'

import { SubstrateModificationAudit } from './modification-chain-audit.js'
import type { ILogger } from '../../../types/interfaces.js'


class MockLogger implements ILogger {
  debug(_msg: string, _meta?: Record<string, unknown>): void {}
  info(_msg: string, _meta?: Record<string, unknown>): void {}
  warn(_msg: string, _meta?: Record<string, unknown>): void {}
  error(_msg: string, _meta?: Record<string, unknown>): void {}
  child(_name: string): ILogger {
    return this
  }
}


describe('SubstrateModificationAudit', () => {
  let smca: SubstrateModificationAudit
  let testDbPath: string

  const mockLogger = new MockLogger()

  beforeEach(() => {
    const testDir = path.join(process.env.TMPDIR || '/tmp', 'cassi-smca-tests')
    if (!existsSync(testDir)) {
      mkdirSync(testDir, { recursive: true })
    }
    const uniqueId = randomBytes(8).toString('hex')
    testDbPath = path.join(testDir, `aurora-smca-${uniqueId}.db`)
    smca = new SubstrateModificationAudit({ logger: mockLogger, dbPath: testDbPath })
  })

  afterEach(() => {
    smca.close()
    if (existsSync(testDbPath)) {
      unlinkSync(testDbPath)
    }
  })

  describe('Chain lifecycle', () => {
    it('should start a new chain', () => {
      const chainId = smca.startChain('C1', 'gap-123', 'Test gap detection')
      expect(chainId).toMatch(/^chain-\d+-[a-z0-9]+$/)

      const chains = smca.queryChains()
      expect(chains).toHaveLength(1)
      expect(chains[0].id).toBe(chainId)
      expect(chains[0].originSpec).toBe('C1')
      expect(chains[0].originIdentifier).toBe('gap-123')
      expect(chains[0].status).toBe('active')
    })

    it('should add links to a chain', () => {
      const chainId = smca.startChain('C1', 'gap-123', 'Test chain')

      smca.addLink(chainId, 'gap_detected', 'C1', 'gap-123', 'Initial detection')
      smca.addLink(chainId, 'meditation_seeded', 'C1', 'meditation-456', 'Meditation started')

      const links = smca.getLinks(chainId)
      expect(links).toHaveLength(2)
      expect(links[0].type).toBe('gap_detected')
      expect(links[1].type).toBe('meditation_seeded')

      const chains = smca.queryChains({ limit: 10 })
      expect(chains[0].linkCount).toBe(2)
    })

    it('should complete a chain', () => {
      const chainId = smca.startChain('C1', 'gap-123', 'Test chain')
      smca.completeChain(chainId)

      const chains = smca.queryChains()
      const chain = chains.find(c => c.id === chainId)
      expect(chain?.status).toBe('completed')
      expect(chain?.completedAt).not.toBeNull()
    })

    it('should abandon a chain with reason', () => {
      const chainId = smca.startChain('C1', 'gap-123', 'Test chain')
      smca.abandonChain(chainId, 'Gap resolved naturally')

      const chains = smca.queryChains()
      const chain = chains.find(c => c.id === chainId)
      expect(chain?.status).toBe('abandoned')
      expect(chain?.description).toContain('abandoned')
      expect(chain?.description).toContain('Gap resolved naturally')
    })

    it('should not update completed chains', () => {
      const chainId = smca.startChain('C1', 'gap-123', 'Test chain')
      smca.completeChain(chainId)

      const chainsBefore = smca.queryChains().length
      smca.completeChain(chainId)
      const chainsAfter = smca.queryChains().length

      expect(chainsBefore).toBe(chainsAfter)
    })
  })

  describe('Querying', () => {
    beforeEach(() => {
      smca.startChain('C1', 'gap-1', 'Gap 1', 'high', true)
      smca.startChain('C3', 'overlay-2', 'Overlay 2', 'medium', false)
      smca.startChain('B1', 'composition-3', 'Composition 3', 'low', true)
    })

    it('should query by status', () => {
      const activeChains = smca.queryChains({ status: 'active' })
      expect(activeChains).toHaveLength(3)

      smca.completeChain(smca.queryChains()[0].id)
      const stillActive = smca.queryChains({ status: 'active' })
      expect(stillActive).toHaveLength(2)

      const completed = smca.queryChains({ status: 'completed' })
      expect(completed).toHaveLength(1)
    })

    it('should query by origin spec', () => {
      const c1Chains = smca.queryChains({ originSpec: 'C1' })
      expect(c1Chains).toHaveLength(1)
      expect(c1Chains[0].originSpec).toBe('C1')

      const multiSpec = smca.queryChains({ originSpec: ['C1', 'C3'] })
      expect(multiSpec).toHaveLength(2)
    })

    it('should query by welfare relevance', () => {
      const welfareRelevant = smca.queryChains({ welfareRelevant: true })
      expect(welfareRelevant).toHaveLength(2)
      expect(welfareRelevant.every(c => c.welfareRelevant)).toBe(true)
    })

    it('should query with limit', () => {
      const limited = smca.queryChains({ limit: 2 })
      expect(limited).toHaveLength(2)
    })

    it('should query with since filter', () => {
      const cutoff = new Date(Date.now() + 10000).toISOString()
      const futureChains = smca.queryChains({ since: cutoff })
      expect(futureChains).toHaveLength(0)
    })
  })

  describe('Statistics and monitoring', () => {
    beforeEach(() => {
      const chain1 = smca.startChain('C1', 'gap-1', 'Gap 1', 'high', true)
      const chain2 = smca.startChain('C3', 'overlay-2', 'Overlay 2', 'medium', false)
      const chain3 = smca.startChain('B1', 'composition-3', 'Composition 3', 'low', true)

      smca.addLink(chain1, 'gap_detected', 'C1', 'gap-1', 'Detection')
      smca.addLink(chain1, 'meditation_seeded', 'C1', 'med-1', 'Meditation')
      smca.completeChain(chain1)

      smca.addLink(chain2, 'candidate_proposed', 'C3', 'cand-2', 'Proposal')

      smca.abandonChain(chain3, 'Cancelled')
    })

    it('should compute statistics', () => {
      const stats = smca.getStatistics()

      expect(stats.total).toBe(3)
      expect(stats.active).toBe(1)
      expect(stats.completed).toBe(1)
      expect(stats.abandoned).toBe(1)
      expect(stats.welfareRelevant).toBe(2)
      expect(stats.byOriginSpec['C1']).toBe(1)
      expect(stats.byOriginSpec['C3']).toBe(1)
      expect(stats.byOriginSpec['B1']).toBe(1)
    })

    it('should identify stalled chains', () => {
      const chainId = smca.startChain('C1', 'stalled-1', 'Stalled chain')

      const stalled = smca.getStalledChains(0)
      expect(stalled).toContainEqual(
        expect.objectContaining({
          id: chainId,
          status: 'active',
        })
      )
    })

    it('should prune old chains', () => {
      const pruned = smca.prune(0)
      expect(pruned).toBe(2)

      const stats = smca.getStatistics()
      expect(stats.total).toBe(1)
      expect(stats.active).toBe(1)
    })
  })

  describe('Get chain with links', () => {
    it('should return null for non-existent chain', () => {
      const result = smca.getChainWithLinks('non-existent')
      expect(result).toBeNull()
    })

    it('should return chain with all links', () => {
      const chainId = smca.startChain('C1', 'gap-123', 'Test chain')

      smca.addLink(chainId, 'gap_detected', 'C1', 'gap-123', 'Detection')
      smca.addLink(chainId, 'meditation_seeded', 'C1', 'med-456', 'Meditation')
      smca.addLink(chainId, 'engram_created', 'C1', 'engram-789', 'Engram')

      const result = smca.getChainWithLinks(chainId)

      expect(result).not.toBeNull()
      expect(result?.chain.id).toBe(chainId)
      expect(result?.links).toHaveLength(3)
      expect(result?.links[0].type).toBe('gap_detected')
      expect(result?.links[2].type).toBe('engram_created')
    })
  })

  describe('Metadata handling', () => {
    it('should store and retrieve link metadata', () => {
      const chainId = smca.startChain('C1', 'gap-1', 'Test chain')

      const metadata = { layer: 42, confidence: 0.95, features: ['a', 'b'] }
      smca.addLink(chainId, 'gap_detected', 'C1', 'gap-1', 'Detection', metadata)

      const links = smca.getLinks(chainId)
      expect(links[0].metadata).toEqual(metadata)
    })
  })

  describe('Priority handling', () => {
    it('should store chain priority', () => {
      const highPriorityId = smca.startChain('C1', 'gap-1', 'Urgent gap', 'high')
      const lowPriorityId = smca.startChain('C1', 'gap-2', 'Minor gap', 'low')

      const chains = smca.queryChains()
      const highPriority = chains.find(c => c.id === highPriorityId)
      const lowPriority = chains.find(c => c.id === lowPriorityId)

      expect(highPriority?.priority).toBe('high')
      expect(lowPriority?.priority).toBe('low')
    })
  })

  describe('Multiple chains', () => {
    it('should handle concurrent chains', () => {
      const chainIds = Array.from({ length: 10 }, (_, i) =>
        smca.startChain(`C${(i % 3) + 1}`, `id-${i}`, `Chain ${i}`)
      )

      expect(chainIds).toHaveLength(10)
      expect(new Set(chainIds).size).toBe(10)

      const allChains = smca.queryChains()
      expect(allChains).toHaveLength(10)
    })
  })
})
