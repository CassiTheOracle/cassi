/**
 * Tests for Aurora Event Journal (AEJ).
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'

import { EventJournal, createEventJournal, type AuroraEventInput } from './event-journal.js'
import type { ILogger } from '../../../types/interfaces.js'


describe('EventJournal', () => {
  let journal: EventJournal
  let testDbPath: string

  const mockLogger: ILogger = {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => mockLogger,
  } as any

  beforeEach(async () => {
    testDbPath = `/tmp/test-aej-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
    // Ensure clean state
    const fs = await import('node:fs/promises')
    await fs.unlink(testDbPath).catch(() => {})
    journal = createEventJournal(mockLogger, testDbPath)
  })

  afterEach(async () => {
    journal.close()
    const fs = await import('node:fs/promises')
    await fs.unlink(testDbPath).catch(() => {})
  })

  describe('emit', () => {
    it('should emit an event and return an ID', () => {
      const input: AuroraEventInput = {
        source: 'B1',
        category: 'composition',
        text: 'Test event',
      }

      const id = journal.emit(input)

      expect(id).toMatch(/^evt_\d+_[a-z0-9]+$/)
    })

    it('should store event with all fields', () => {
      const input: AuroraEventInput = {
        source: 'B1',
        category: 'composition',
        text: 'Test event with references',
        references: [{ spec: 'B1', recordId: 'inv-123' }],
        tags: ['test', 'composition'],
        sessionId: 'sess-456',
        metadata: { key: 'value' },
      }

      const id = journal.emit(input)
      const events = journal.bySource('B1')

      expect(events).toHaveLength(1)
      expect(events[0].id).toBe(id)
      expect(events[0].source).toBe('B1')
      expect(events[0].category).toBe('composition')
      expect(events[0].text).toBe('Test event with references')
      expect(events[0].references).toEqual([{ spec: 'B1', recordId: 'inv-123' }])
      expect(events[0].tags).toEqual(['test', 'composition'])
      expect(events[0].sessionId).toBe('sess-456')
      expect(events[0].metadata).toEqual({ key: 'value' })
    })

    it('should use provided timestamp when given', () => {
      const customTime = '2026-05-01T12:00:00.000Z'
      const input: AuroraEventInput = {
        source: 'B1',
        category: 'composition',
        text: 'Test event',
        occurredAt: customTime,
      }

      journal.emit(input)
      const events = journal.bySource('B1')

      expect(events[0].timestamp).toBe(customTime)
    })
  })

  describe('byTimeRange', () => {
    it('should query events in time range', () => {
      journal.emit({
        source: 'B1',
        category: 'composition',
        text: 'Early event',
        occurredAt: '2026-05-01T10:00:00.000Z',
      })

      journal.emit({
        source: 'B1',
        category: 'composition',
        text: 'Middle event',
        occurredAt: '2026-05-01T12:00:00.000Z',
      })

      journal.emit({
        source: 'B1',
        category: 'composition',
        text: 'Late event',
        occurredAt: '2026-05-01T14:00:00.000Z',
      })

      const events = journal.byTimeRange('2026-05-01T11:00:00.000Z', '2026-05-01T13:00:00.000Z')

      expect(events).toHaveLength(1)
      expect(events[0].text).toBe('Middle event')
    })

    it('should respect limit parameter', () => {
      for (let i = 0; i < 10; i++) {
        journal.emit({
          source: 'B1',
          category: 'composition',
          text: `Event ${i}`,
          occurredAt: `2026-05-01T${10 + i}:00:00.000Z`,
        })
      }

      const events = journal.byTimeRange('2026-05-01T10:00:00.000Z', '2026-05-01T20:00:00.000Z', 3)

      expect(events).toHaveLength(3)
    })
  })

  describe('bySource', () => {
    it('should query events by source', () => {
      journal.emit({ source: 'B1', category: 'composition', text: 'B1 event' })
      journal.emit({ source: 'C1', category: 'gap_detection', text: 'C1 event' })
      journal.emit({ source: 'B1', category: 'composition', text: 'Another B1 event' })

      const b1Events = journal.bySource('B1')
      const c1Events = journal.bySource('C1')

      expect(b1Events).toHaveLength(2)
      expect(c1Events).toHaveLength(1)
      expect(b1Events[0].text).toBe('Another B1 event')
      expect(b1Events[1].text).toBe('B1 event')
    })

    it('should return empty array for unknown source', () => {
      const events = journal.bySource('UNKNOWN')
      expect(events).toEqual([])
    })
  })

  describe('bySessionId', () => {
    it('should query events by session ID', () => {
      journal.emit({ source: 'B1', category: 'composition', text: 'Session 1 event', sessionId: 'sess-1' })
      journal.emit({ source: 'C1', category: 'gap_detection', text: 'Session 2 event', sessionId: 'sess-2' })
      journal.emit({ source: 'B1', category: 'composition', text: 'Another session 1 event', sessionId: 'sess-1' })

      const sess1Events = journal.bySessionId('sess-1')
      const sess2Events = journal.bySessionId('sess-2')

      expect(sess1Events).toHaveLength(2)
      expect(sess2Events).toHaveLength(1)
    })

    it('should return empty array for unknown session', () => {
      const events = journal.bySessionId('unknown-session')
      expect(events).toEqual([])
    })
  })

  describe('withTag', () => {
    it('should query events by tag', () => {
      journal.emit({
        source: 'B1',
        category: 'composition',
        text: 'Event 1',
        tags: ['welfare-flag', 'composition'],
      })

      journal.emit({
        source: 'C1',
        category: 'gap_detection',
        text: 'Event 2',
        tags: ['gap-detected'],
      })

      journal.emit({
        source: 'B1',
        category: 'composition',
        text: 'Event 3',
        tags: ['welfare-flag', 'test'],
      })

      const welfareEvents = journal.withTag('welfare-flag')
      const gapEvents = journal.withTag('gap-detected')

      expect(welfareEvents).toHaveLength(2)
      expect(gapEvents).toHaveLength(1)
    })

    it('should handle partial tag matches correctly', () => {
      journal.emit({
        source: 'B1',
        category: 'composition',
        text: 'Event',
        tags: ['test-tag'],
      })

      const exactMatch = journal.withTag('test-tag')
      const partialMatch = journal.withTag('test')

      expect(exactMatch).toHaveLength(1)
      expect(partialMatch).toHaveLength(0)
    })
  })

  describe('composite', () => {
    beforeEach(() => {
      journal.emit({
        source: 'B1',
        category: 'composition',
        text: 'B1 composition 1',
        tags: ['composition', 'welfare-flag'],
        sessionId: 'sess-1',
        occurredAt: '2026-05-01T10:00:00.000Z',
      })

      journal.emit({
        source: 'B1',
        category: 'gap_detection',
        text: 'B1 gap 1',
        tags: ['gap-detected'],
        sessionId: 'sess-1',
        occurredAt: '2026-05-01T11:00:00.000Z',
      })

      journal.emit({
        source: 'C1',
        category: 'composition',
        text: 'C1 composition 1',
        tags: ['composition'],
        sessionId: 'sess-2',
        occurredAt: '2026-05-01T12:00:00.000Z',
      })

      journal.emit({
        source: 'C1',
        category: 'welfare_flag',
        text: 'C1 welfare flag',
        tags: ['welfare-flag'],
        sessionId: 'sess-2',
        occurredAt: '2026-05-01T13:00:00.000Z',
      })
    })

    it('should filter by sources', () => {
      const events = journal.composite({ sources: ['B1'] })
      expect(events).toHaveLength(2)
      expect(events.every(e => e.source === 'B1')).toBe(true)
    })

    it('should filter by categories', () => {
      const events = journal.composite({ categories: ['composition'] })
      expect(events).toHaveLength(2)
      expect(events.every(e => e.category === 'composition')).toBe(true)
    })

    it('should filter by tags', () => {
      const events = journal.composite({ tags: ['welfare-flag'] })
      expect(events).toHaveLength(2)
      expect(events.every(e => e.tags.includes('welfare-flag'))).toBe(true)
    })

    it('should filter by session IDs', () => {
      const events = journal.composite({ sessionIds: ['sess-1'] })
      expect(events).toHaveLength(2)
      expect(events.every(e => e.sessionId === 'sess-1')).toBe(true)
    })

    it('should filter by time range', () => {
      const events = journal.composite({
        timeRange: { start: '2026-05-01T10:30:00.000Z', end: '2026-05-01T12:30:00.000Z' },
      })
      expect(events).toHaveLength(2)
    })

    it('should apply multiple filters together', () => {
      const events = journal.composite({
        sources: ['B1'],
        tags: ['composition'],
      })
      expect(events).toHaveLength(1)
      expect(events[0].source).toBe('B1')
      expect(events[0].tags.includes('composition')).toBe(true)
    })

    it('should support pagination', () => {
      const firstPage = journal.composite({ limit: 2, offset: 0 })
      const secondPage = journal.composite({ limit: 2, offset: 2 })

      expect(firstPage).toHaveLength(2)
      expect(secondPage).toHaveLength(2)
      expect(firstPage[0].timestamp > firstPage[1].timestamp).toBe(true)
    })
  })

  describe('query', () => {
    it('should be alias for composite', () => {
      journal.emit({ source: 'B1', category: 'composition', text: 'Test' })
      const events = journal.query({ sources: ['B1'] })
      expect(events).toHaveLength(1)
    })
  })

  describe('recent', () => {
    it('should return most recent events', () => {
      for (let i = 0; i < 10; i++) {
        journal.emit({ source: 'B1', category: 'composition', text: `Event ${i}` })
      }

      const recent = journal.recent(5)

      expect(recent).toHaveLength(5)
      expect(recent[0].text).toBe('Event 9')
      expect(recent[4].text).toBe('Event 5')
    })

    it('should use default limit of 50', () => {
      for (let i = 0; i < 60; i++) {
        journal.emit({ source: 'B1', category: 'composition', text: `Event ${i}` })
      }

      const recent = journal.recent()

      expect(recent).toHaveLength(50)
    })
  })

  describe('getStatistics', () => {
    it('should return journal statistics', () => {
      journal.emit({ source: 'B1', category: 'composition', text: 'Event 1' })
      journal.emit({ source: 'B1', category: 'gap_detection', text: 'Event 2' })
      journal.emit({ source: 'C1', category: 'composition', text: 'Event 3' })
      journal.emit({ source: 'C1', category: 'welfare_flag', text: 'Event 4' })

      const stats = journal.getStatistics()

      expect(stats.totalEvents).toBe(4)
      expect(stats.bySource.B1).toBe(2)
      expect(stats.bySource.C1).toBe(2)
      expect(stats.byCategory.composition).toBe(2)
      expect(stats.byCategory.gap_detection).toBe(1)
      expect(stats.byCategory.welfare_flag).toBe(1)
      expect(stats.oldestEvent).toBeTruthy()
      expect(stats.newestEvent).toBeTruthy()
    })

    it('should return empty stats for new journal', () => {
      const stats = journal.getStatistics()

      expect(stats.totalEvents).toBe(0)
      expect(stats.bySource).toEqual({})
      expect(stats.byCategory).toEqual({})
      expect(stats.oldestEvent).toBeNull()
      expect(stats.newestEvent).toBeNull()
    })
  })

  describe('backfill', () => {
    it('should backfill events from async function', async () => {
      const backfillFn = async (): Promise<AuroraEventInput[]> => [
        { source: 'B1', category: 'composition', text: 'Backfilled 1' },
        { source: 'C1', category: 'gap_detection', text: 'Backfilled 2' },
      ]

      const count = await journal.backfill(backfillFn)

      expect(count).toBe(2)

      const allEvents = journal.recent()
      expect(allEvents).toHaveLength(2)
      expect(allEvents[0].text).toBe('Backfilled 2')
      expect(allEvents[1].text).toBe('Backfilled 1')
    })

    it('should handle empty backfill', async () => {
      const backfillFn = async (): Promise<AuroraEventInput[]> => []

      const count = await journal.backfill(backfillFn)

      expect(count).toBe(0)
    })
  })

  describe('close', () => {
    it('should close database connection', () => {
      const testJournal = createEventJournal(mockLogger, testDbPath)
      testJournal.emit({ source: 'B1', category: 'composition', text: 'Test' })

      expect(() => testJournal.close()).not.toThrow()
    })
  })
})
