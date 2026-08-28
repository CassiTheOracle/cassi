/**
 * Blackboard Search & Pagination Tests
 *
 * Tests regex-based search and cursor-based pagination across all 6 board types:
 * channels, scratchpad, tool log, artifacts, plan steps, and report sections.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { Blackboard } from '../src/blackboard.js'
import type { ILogger } from '@cassicore/foundation'
import {
  encodeCursor,
  decodeCursor,
  validatePattern,
  encodeCompositeCursor,
  decodeCompositeCursor,
} from '../src/blackboard-search.js'

const createMockLogger = () => ({
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  debug: vi.fn(),
  child: vi.fn().mockReturnThis(),
})

describe('Blackboard Search & Pagination', () => {
  let bb: Blackboard
  let logger: ReturnType<typeof createMockLogger>

  beforeEach(() => {
    logger = createMockLogger()
    bb = new Blackboard(logger as unknown as ILogger, 'test-cell')
  })


  describe('cursor encoding', () => {
    it('should encode and decode a cursor round-trip', () => {
      const cursor = { ts: 1700000000000, id: 'abc-123' }
      const encoded = encodeCursor(cursor)
      expect(typeof encoded).toBe('string')
      expect(encoded.length).toBeGreaterThan(0)

      const decoded = decodeCursor(encoded)
      expect(decoded).toEqual(cursor)
    })

    it('should encode and decode a cursor with sortValue', () => {
      const cursor = { ts: 1700000000000, id: 'abc', sortValue: 5 }
      const decoded = decodeCursor(encodeCursor(cursor))
      expect(decoded).toEqual(cursor)
    })

    it('should return null for invalid cursor strings', () => {
      expect(decodeCursor('')).toBeNull()
      expect(decodeCursor('not-valid-base64!!!')).toBeNull()
      expect(decodeCursor(Buffer.from('{"foo":"bar"}').toString('base64url'))).toBeNull()
    })

    it('should encode and decode composite cursors', () => {
      const cursors = { channel: 'abc123', report: 'def456' }
      const encoded = encodeCompositeCursor(cursors)
      const decoded = decodeCompositeCursor(encoded)
      expect(decoded).toEqual(cursors)
    })

    it('should return null for invalid composite cursors', () => {
      expect(decodeCompositeCursor('')).toBeNull()
      expect(decodeCompositeCursor('garbage')).toBeNull()
    })
  })


  describe('pattern validation', () => {
    it('should accept valid patterns', () => {
      expect(validatePattern('hello')).toBeNull()
      expect(validatePattern('foo.*bar')).toBeNull()
      expect(validatePattern('[a-z]+')).toBeNull()
    })

    it('should reject patterns that are too long', () => {
      const longPattern = 'a'.repeat(201)
      expect(validatePattern(longPattern)).toContain('too long')
    })

    it('should reject invalid regex syntax', () => {
      expect(validatePattern('[')).toContain('Invalid regex')
      expect(validatePattern('(?P<name>')).toContain('Invalid regex')
    })
  })


  describe('searchChannel', () => {
    beforeEach(() => {
      // Post test data
      bb.post('findings', { author: 'yang', content: 'Found a bug in auth module', priority: 5, tags: ['bug', 'auth'] })
      bb.post('findings', { author: 'yin', content: 'Auth logic looks correct to me', priority: 3, tags: ['auth'] })
      bb.post('concerns', { author: 'yang', content: 'Performance concern in database layer', priority: 4, tags: ['performance'] })
      bb.post('decisions', { author: 'executive', content: 'Decided to refactor the auth module', priority: 2, tags: ['auth', 'refactor'] })
    })

    it('should return all entries when no filters are applied', () => {
      const result = bb.searchChannel()
      expect(result.total).toBe(4)
      expect(result.items).toHaveLength(4)
      expect(result.hasMore).toBe(false)
    })

    it('should filter by channel', () => {
      const result = bb.searchChannel({ channel: 'findings' })
      expect(result.total).toBe(2)
      expect(result.items.every(e => e.channel === 'findings')).toBe(true)
    })

    it('should search by regex pattern', () => {
      const result = bb.searchChannel({ pattern: 'auth' })
      expect(result.total).toBe(3) // all 3 entries mentioning auth
    })

    it('should search by regex with special characters', () => {
      const result = bb.searchChannel({ pattern: 'bug.*auth' })
      expect(result.total).toBe(1)
      expect(result.items[0].content).toContain('bug in auth')
    })

    it('should filter by author', () => {
      const result = bb.searchChannel({ author: 'yang' })
      expect(result.total).toBe(2)
      expect(result.items.every(e => e.author === 'yang')).toBe(true)
    })

    it('should filter by tags (AND logic)', () => {
      const result = bb.searchChannel({ tags: ['auth', 'refactor'] })
      expect(result.total).toBe(1)
      expect(result.items[0].content).toContain('refactor')
    })

    it('should filter by minimum priority', () => {
      const result = bb.searchChannel({ minPriority: 4 })
      expect(result.total).toBe(2) // priorities 5 and 4
      expect(result.items.every(e => e.priority >= 4)).toBe(true)
    })

    it('should sort by priority DESC, timestamp DESC', () => {
      const result = bb.searchChannel()
      for (let i = 1; i < result.items.length; i++) {
        const prev = result.items[i - 1]
        const curr = result.items[i]
        if (prev.priority === curr.priority) {
          expect(prev.timestamp).toBeGreaterThanOrEqual(curr.timestamp)
        } else {
          expect(prev.priority).toBeGreaterThan(curr.priority)
        }
      }
    })

    it('should return empty result for non-matching pattern', () => {
      const result = bb.searchChannel({ pattern: 'nonexistent_xyz_42' })
      expect(result.total).toBe(0)
      expect(result.items).toHaveLength(0)
      expect(result.hasMore).toBe(false)
    })

    it('should throw on invalid regex', () => {
      expect(() => bb.searchChannel({ pattern: '[' })).toThrow('Invalid regex')
    })

    it('should paginate with cursor', () => {
      // Post enough entries for pagination
      for (let i = 0; i < 10; i++) {
        bb.post('findings', { author: 'yang', content: `Entry number ${i}`, priority: i, tags: [] })
      }

      const page1 = bb.searchChannel({ channel: 'findings', limit: 5 })
      expect(page1.items).toHaveLength(5)
      expect(page1.hasMore).toBe(true)
      expect(page1.cursor).toBeDefined()
      expect(page1.total).toBe(12) // 2 from beforeEach + 10 new

      const page2 = bb.searchChannel({ channel: 'findings', limit: 5, cursor: page1.cursor })
      expect(page2.items).toHaveLength(5)
      expect(page2.hasMore).toBe(true)

      const page3 = bb.searchChannel({ channel: 'findings', limit: 5, cursor: page2.cursor })
      expect(page3.items).toHaveLength(2) // remaining 2
      expect(page3.hasMore).toBe(false)

      // All items should be unique across pages
      const allIds = [...page1.items, ...page2.items, ...page3.items].map(e => e.id)
      expect(new Set(allIds).size).toBe(12)
    })

    it('should combine search pattern with pagination', () => {
      for (let i = 0; i < 10; i++) {
        bb.post('findings', { author: 'yang', content: `Auth related item ${i}`, priority: 1, tags: [] })
      }

      const page1 = bb.searchChannel({ pattern: 'auth', limit: 5 })
      expect(page1.total).toBe(13) // 3 from beforeEach + 10 new
      expect(page1.hasMore).toBe(true)

      const page2 = bb.searchChannel({ pattern: 'auth', limit: 5, cursor: page1.cursor })
      expect(page2.items.length).toBeGreaterThan(0)
    })

    it('should filter by since/until timestamps', () => {
      const before = Date.now()
      bb.post('findings', { author: 'test', content: 'Recent entry', priority: 1, tags: [] })

      const result = bb.searchChannel({ since: before })
      expect(result.items.some(e => e.content === 'Recent entry')).toBe(true)
    })
  })


  describe('searchScratchpad', () => {
    beforeEach(() => {
      bb.setScratchpad('config.database', 'postgresql://localhost:5432/mydb', 'yang')
      bb.setScratchpad('config.cache', 'redis://localhost:6379', 'yin')
      bb.setScratchpad('notes.summary', 'This is a summary of findings', 'executive')
    })

    it('should return all non-expired entries', () => {
      const result = bb.searchScratchpad()
      expect(result.total).toBe(3)
    })

    it('should search by key pattern', () => {
      const result = bb.searchScratchpad({ pattern: 'config' })
      expect(result.total).toBe(2)
    })

    it('should search by value pattern', () => {
      const result = bb.searchScratchpad({ pattern: 'redis' })
      expect(result.total).toBe(1)
      expect(result.items[0].key).toBe('config.cache')
    })

    it('should filter by author', () => {
      const result = bb.searchScratchpad({ author: 'yang' })
      expect(result.total).toBe(1)
    })

    it('should paginate correctly', () => {
      const page1 = bb.searchScratchpad({ limit: 2 })
      expect(page1.items).toHaveLength(2)
      expect(page1.hasMore).toBe(true)

      const page2 = bb.searchScratchpad({ limit: 2, cursor: page1.cursor })
      expect(page2.items).toHaveLength(1)
      expect(page2.hasMore).toBe(false)
    })
  })


  describe('searchToolLog', () => {
    beforeEach(() => {
      bb.addToolRecord({ tool: 'read_file', nodeId: 'node-1', durationMs: 100, isError: false, params: {}, result: 'ok' })
      bb.addToolRecord({ tool: 'bash', nodeId: 'node-1', durationMs: 5000, isError: true, params: {}, result: 'failed' })
      bb.addToolRecord({ tool: 'read_file', nodeId: 'node-2', durationMs: 50, isError: false, params: {}, result: 'ok' })
      bb.addToolRecord({ tool: 'write_file', nodeId: 'node-1', durationMs: 200, isError: false, params: {}, result: 'ok' })
    })

    it('should return all records', () => {
      const result = bb.searchToolLog()
      expect(result.total).toBe(4)
    })

    it('should search by tool name pattern', () => {
      const result = bb.searchToolLog({ pattern: 'read' })
      expect(result.total).toBe(2)
    })

    it('should search by nodeId pattern', () => {
      const result = bb.searchToolLog({ pattern: 'node-2' })
      expect(result.total).toBe(1)
    })

    it('should filter by exact tool name', () => {
      const result = bb.searchToolLog({ tool: 'read_file' })
      expect(result.total).toBe(2)
    })

    it('should filter by error status', () => {
      const result = bb.searchToolLog({ isError: true })
      expect(result.total).toBe(1)
      expect(result.items[0].tool).toBe('bash')
    })

    it('should sort newest first', () => {
      const result = bb.searchToolLog()
      for (let i = 1; i < result.items.length; i++) {
        expect(result.items[i - 1].timestamp).toBeGreaterThanOrEqual(result.items[i].timestamp)
      }
    })

    it('should paginate correctly', () => {
      const page1 = bb.searchToolLog({ limit: 2 })
      expect(page1.items).toHaveLength(2)
      expect(page1.hasMore).toBe(true)

      const page2 = bb.searchToolLog({ limit: 2, cursor: page1.cursor })
      expect(page2.items).toHaveLength(2)
      expect(page2.hasMore).toBe(false)
    })
  })


  describe('searchArtifacts', () => {
    beforeEach(() => {
      bb.addArtifact({ path: 'src/auth/login.ts', operation: 'modified', author: 'yang' })
      bb.addArtifact({ path: 'src/db/query.ts', operation: 'created', author: 'yin' })
      bb.addArtifact({ path: 'tests/auth.test.ts', operation: 'modified', author: 'yang' })
    })

    it('should return all artifacts', () => {
      const result = bb.searchArtifacts()
      expect(result.total).toBe(3)
    })

    it('should search by path pattern', () => {
      const result = bb.searchArtifacts({ pattern: 'auth' })
      expect(result.total).toBe(2)
    })

    it('should filter by operation', () => {
      const result = bb.searchArtifacts({ operation: 'created' })
      expect(result.total).toBe(1)
      expect(result.items[0].path).toBe('src/db/query.ts')
    })

    it('should filter by author', () => {
      const result = bb.searchArtifacts({ author: 'yang' })
      expect(result.total).toBe(2)
    })

    it('should paginate correctly', () => {
      const page1 = bb.searchArtifacts({ limit: 2 })
      expect(page1.items).toHaveLength(2)
      expect(page1.hasMore).toBe(true)

      const page2 = bb.searchArtifacts({ limit: 2, cursor: page1.cursor })
      expect(page2.items).toHaveLength(1)
      expect(page2.hasMore).toBe(false)
    })
  })


  describe('searchPlan', () => {
    beforeEach(() => {
      bb.initPlan('Refactor Auth Module')
      bb.submitPlanStep({
        title: 'Analyze auth flow', description: 'Understand the current auth implementation',
        author: 'executive', order: 1, tags: ['auth', 'analysis'],
        dependencies: [], priority: 'medium',
      })
      bb.submitPlanStep({
        title: 'Refactor login endpoint', description: 'Clean up the login handler',
        author: 'executive', order: 2, assignee: 'yang',
        tags: ['auth', 'refactor'], priority: 'high', dependencies: [],
      })
      bb.submitPlanStep({
        title: 'Update tests', description: 'Write new test cases for auth',
        author: 'executive', order: 3,
        tags: ['test'], priority: 'low', dependencies: [],
      })
    })

    it('should return all steps', () => {
      const result = bb.searchPlan()
      expect(result.total).toBe(3)
    })

    it('should search by title pattern', () => {
      const result = bb.searchPlan({ pattern: 'auth' })
      expect(result.total).toBe(3) // all 3 steps mention 'auth' in tags, title, or description
    })

    it('should filter by status', () => {
      const result = bb.searchPlan({ status: 'proposed' })
      expect(result.total).toBe(3) // all steps start as proposed
    })

    it('should filter by assignee', () => {
      // Approve then claim step 2 by yang
      const plan = bb.getPlan()!
      const step2 = plan.steps.find(s => s.title === 'Refactor login endpoint')!
      bb.updatePlanStep(step2.id, { status: 'approved' })
      bb.claimPlanStep(step2.id, 'yang')

      const result = bb.searchPlan({ assignee: 'yang' })
      expect(result.total).toBe(1)
      expect(result.items[0].title).toBe('Refactor login endpoint')
    })

    it('should sort by order ASC', () => {
      const result = bb.searchPlan()
      for (let i = 1; i < result.items.length; i++) {
        expect(result.items[i].order).toBeGreaterThan(result.items[i - 1].order)
      }
    })

    it('should return empty when no plan exists', () => {
      const emptyBb = new Blackboard(logger as unknown as ILogger, 'empty')
      const result = emptyBb.searchPlan()
      expect(result.total).toBe(0)
      expect(result.items).toHaveLength(0)
    })

    it('should paginate correctly', () => {
      const page1 = bb.searchPlan({ limit: 2 })
      expect(page1.items).toHaveLength(2)
      expect(page1.hasMore).toBe(true)
      expect(page1.items[0].order).toBe(1)

      const page2 = bb.searchPlan({ limit: 2, cursor: page1.cursor })
      expect(page2.items).toHaveLength(1)
      expect(page2.hasMore).toBe(false)
      expect(page2.items[0].order).toBe(3)
    })
  })


  describe('searchReport', () => {
    beforeEach(() => {
      bb.addReportSection({
        type: 'finding',
        title: 'Auth vulnerability discovered',
        content: 'The auth module has a bypass vulnerability in the token validation logic.',
        author: 'yang',
      })
      bb.addReportSection({
        type: 'recommendation',
        title: 'Use JWT instead of custom tokens',
        content: 'Switching to JWT would eliminate the token validation bypass.',
        author: 'yin',
      })
      bb.addReportSection({
        type: 'concern',
        title: 'Migration risk',
        content: 'Changing auth tokens could break existing sessions.',
        author: 'executive',
      })
    })

    it('should return all sections', () => {
      const result = bb.searchReport()
      expect(result.total).toBe(3)
    })

    it('should search by content pattern', () => {
      const result = bb.searchReport({ pattern: 'token' })
      expect(result.total).toBe(3) // all three mention tokens/token
    })

    it('should search by title pattern', () => {
      const result = bb.searchReport({ pattern: 'JWT' })
      expect(result.total).toBe(1)
    })

    it('should filter by section type', () => {
      const result = bb.searchReport({ type: 'finding' })
      expect(result.total).toBe(1)
      expect(result.items[0].title).toContain('Auth vulnerability')
    })

    it('should filter by author', () => {
      const result = bb.searchReport({ author: 'yin' })
      expect(result.total).toBe(1)
    })

    it('should return empty when no report exists', () => {
      const emptyBb = new Blackboard(logger as unknown as ILogger, 'empty')
      const result = emptyBb.searchReport()
      expect(result.total).toBe(0)
    })

    it('should paginate correctly', () => {
      const page1 = bb.searchReport({ limit: 2 })
      expect(page1.items).toHaveLength(2)
      expect(page1.hasMore).toBe(true)

      const page2 = bb.searchReport({ limit: 2, cursor: page1.cursor })
      expect(page2.items).toHaveLength(1)
      expect(page2.hasMore).toBe(false)

      // No overlap
      const ids1 = new Set(page1.items.map(s => s.id))
      const ids2 = new Set(page2.items.map(s => s.id))
      for (const id of ids2) {
        expect(ids1.has(id)).toBe(false)
      }
    })
  })


  describe('searchAll', () => {
    beforeEach(() => {
      // Populate multiple boards with 'auth'-related content
      bb.post('findings', { author: 'yang', content: 'Auth bug found', priority: 5, tags: ['auth'] })
      bb.post('concerns', { author: 'yin', content: 'Auth migration risk', priority: 3, tags: ['auth'] })
      bb.setScratchpad('auth.config', 'jwt-secret-key', 'yang')
      bb.addArtifact({ path: 'src/auth/handler.ts', operation: 'modified', author: 'yang' })
      bb.addReportSection({ type: 'finding', title: 'Auth security review', content: 'Auth needs review', author: 'yang' })
    })

    it('should search across all boards', () => {
      const result = bb.searchAll({ pattern: 'auth' })
      expect(result.totalMatches).toBeGreaterThan(0)
      expect(result.rankedBoards.length).toBeGreaterThan(0)
    })

    it('should return results grouped by board', () => {
      const result = bb.searchAll({ pattern: 'auth' })
      expect(result.boards.channel).toBeDefined()
      expect(result.boards.channel?.total).toBe(2)
      expect(result.boards.scratchpad).toBeDefined()
      expect(result.boards.artifact).toBeDefined()
      expect(result.boards.report).toBeDefined()
    })

    it('should rank boards by match count', () => {
      const result = bb.searchAll({ pattern: 'auth' })
      for (let i = 1; i < result.rankedBoards.length; i++) {
        expect(result.rankedBoards[i - 1].count).toBeGreaterThanOrEqual(result.rankedBoards[i].count)
      }
    })

    it('should filter by specific boards', () => {
      const result = bb.searchAll({ pattern: 'auth', boards: ['channel', 'report'] })
      expect(result.boards.channel).toBeDefined()
      expect(result.boards.report).toBeDefined()
      expect(result.boards.scratchpad).toBeUndefined()
      expect(result.boards.artifact).toBeUndefined()
    })

    it('should include composite cursor when results overflow', () => {
      // Add enough entries to trigger pagination
      for (let i = 0; i < 60; i++) {
        bb.post('findings', { author: 'yang', content: `Auth item ${i}`, priority: 1, tags: [] })
      }

      const result = bb.searchAll({ pattern: 'auth', limitPerBoard: 10 })
      expect(result.boards.channel?.hasMore).toBe(true)
      expect(result.cursor).toBeDefined()
    })

    it('should return empty for non-matching pattern', () => {
      const result = bb.searchAll({ pattern: 'nonexistent_xyz_42' })
      expect(result.totalMatches).toBe(0)
      expect(result.rankedBoards).toHaveLength(0)
    })

    it('should filter by author across boards', () => {
      const result = bb.searchAll({ pattern: 'auth', author: 'yin' })
      // Only yin's entries should match
      if (result.boards.channel) {
        expect(result.boards.channel.items.every(i => i.item.author === 'yin')).toBe(true)
      }
    })
  })


  describe('edge cases', () => {
    it('should handle case-insensitive regex', () => {
      bb.post('findings', { author: 'yang', content: 'IMPORTANT BUG', priority: 1, tags: [] })
      const result = bb.searchChannel({ pattern: 'important bug' })
      expect(result.total).toBe(1)
    })

    it('should handle regex special characters in content (not in pattern)', () => {
      bb.post('findings', { author: 'yang', content: 'Error in file (src/auth.ts): line 42', priority: 1, tags: [] })
      // Escaped parens in pattern
      const result = bb.searchChannel({ pattern: '\\(src/auth\\.ts\\)' })
      expect(result.total).toBe(1)
    })

    it('should handle limit=0 by using default', () => {
      bb.post('findings', { author: 'yang', content: 'test', priority: 1, tags: [] })
      const result = bb.searchChannel({ limit: 0 })
      expect(result.items).toHaveLength(1) // uses default limit, not 0
    })

    it('should clamp limit to MAX_SEARCH_LIMIT', () => {
      for (let i = 0; i < 10; i++) {
        bb.post('findings', { author: 'yang', content: `item ${i}`, priority: 1, tags: [] })
      }
      const result = bb.searchChannel({ limit: 9999 })
      expect(result.items).toHaveLength(10) // total is only 10, so all returned
    })

    it('should handle cursor stability when items are added between pages', () => {
      for (let i = 0; i < 5; i++) {
        bb.post('findings', { author: 'yang', content: `item ${i}`, priority: i, tags: [] })
      }

      const page1 = bb.searchChannel({ channel: 'findings', limit: 3 })
      expect(page1.items).toHaveLength(3)
      expect(page1.hasMore).toBe(true)

      // Add a new high-priority entry between pages
      bb.post('findings', { author: 'yin', content: 'new high priority', priority: 10, tags: [] })

      // Page 2 should still return items after the cursor position
      const page2 = bb.searchChannel({ channel: 'findings', limit: 3, cursor: page1.cursor })
      expect(page2.items.length).toBeGreaterThan(0)

      // The new item should not appear in page 2 (it has higher priority, so it's before the cursor)
      // But it WILL affect the total count
      expect(page2.total).toBe(6)
    })

    it('should handle empty boards gracefully', () => {
      const channelResult = bb.searchChannel({ pattern: 'anything' })
      expect(channelResult.total).toBe(0)

      const scratchpadResult = bb.searchScratchpad({ pattern: 'anything' })
      expect(scratchpadResult.total).toBe(0)

      const toolLogResult = bb.searchToolLog({ pattern: 'anything' })
      expect(toolLogResult.total).toBe(0)

      const artifactResult = bb.searchArtifacts({ pattern: 'anything' })
      expect(artifactResult.total).toBe(0)
    })
  })
})
