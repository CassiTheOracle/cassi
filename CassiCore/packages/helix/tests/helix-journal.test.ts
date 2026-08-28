/**
 * HelixJournal tests — append-only SQLite log for brain-integrated Helix.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HelixJournal } from '../src/helix-journal.js'
import type { ILogger } from '@cassicore/foundation'


function createMockLogger(): ILogger {
  const logger: ILogger = {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    child: () => logger,
  } as any
  return logger
}


describe('HelixJournal', () => {
  let journal: HelixJournal

  beforeEach(() => {
    journal = new HelixJournal({ logger: createMockLogger(), inMemory: true })
  })

  afterEach(() => {
    journal.close()
  })

  it('assigns monotonic per-session sequence numbers', () => {
    const a1 = journal.append({ sessionId: 's-a', eventType: 'signal.submit' })
    const a2 = journal.append({ sessionId: 's-a', eventType: 'signal.submit' })
    const b1 = journal.append({ sessionId: 's-b', eventType: 'signal.submit' })
    const a3 = journal.append({ sessionId: 's-a', eventType: 'signal.submit' })

    expect(a1.seq).toBe(1)
    expect(a2.seq).toBe(2)
    expect(a3.seq).toBe(3)
    expect(b1.seq).toBe(1)
  })

  it('readSession returns entries in seq order with sinceSeq filter', () => {
    for (let i = 0; i < 5; i++) {
      journal.append({ sessionId: 's', eventType: 'signal.submit', payload: { i } })
    }
    const tail = journal.readSession('s', { sinceSeq: 2 })
    expect(tail.map(e => e.seq)).toEqual([3, 4, 5])
  })

  it('readByCorrelation groups entries across event types', () => {
    journal.append({ sessionId: 's', eventType: 'signal.submit', correlationId: 'f-1' })
    journal.append({ sessionId: 's', eventType: 'signal.ignite', correlationId: 'f-1' })
    journal.append({ sessionId: 's', eventType: 'signal.submit', correlationId: 'f-2' })
    journal.append({ sessionId: 's', eventType: 'signal.submit', correlationId: 'f-1' })

    const f1 = journal.readByCorrelation('f-1')
    expect(f1.length).toBe(3)
    expect(f1.map(e => e.eventType)).toEqual(['signal.submit', 'signal.ignite', 'signal.submit'])
  })

  it('subscribe delivers entries in real time', () => {
    const received: any[] = []
    const unsub = journal.subscribe(e => received.push(e))

    journal.append({ sessionId: 's', eventType: 'signal.submit', payload: { a: 1 } })
    journal.append({ sessionId: 's', eventType: 'workspace.broadcast' })

    unsub()
    journal.append({ sessionId: 's', eventType: 'session.terminate' })

    expect(received.length).toBe(2)
    expect(received[0].eventType).toBe('signal.submit')
    expect(received[0].payload).toEqual({ a: 1 })
    expect(received[1].eventType).toBe('workspace.broadcast')
  })

  it('listSessions returns most-recent-first with counts', () => {
    journal.append({ sessionId: 's-old', eventType: 'session.start' })
    journal.append({ sessionId: 's-old', eventType: 'signal.submit' })
    journal.append({ sessionId: 's-new', eventType: 'session.start' })

    const list = journal.listSessions()
    expect(list.length).toBe(2)
    expect(list[0].sessionId).toBe('s-new')
    expect(list[1].sessionId).toBe('s-old')
    expect(list[1].eventCount).toBe(2)
  })

  it('deleteSession removes all entries for a session', () => {
    journal.append({ sessionId: 's-x', eventType: 'session.start' })
    journal.append({ sessionId: 's-x', eventType: 'signal.submit' })
    journal.append({ sessionId: 's-y', eventType: 'session.start' })

    const removed = journal.deleteSession('s-x')
    expect(removed).toBe(2)
    expect(journal.readSession('s-x').length).toBe(0)
    expect(journal.readSession('s-y').length).toBe(1)
  })

  it('persists payload JSON round-trip', () => {
    journal.append({
      sessionId: 's',
      eventType: 'signal.submit',
      payload: { complex: { a: [1, 2], b: 'hi' }, n: 42 },
    })
    const [entry] = journal.readSession('s')
    expect(entry!.payload).toEqual({ complex: { a: [1, 2], b: 'hi' }, n: 42 })
  })
})
