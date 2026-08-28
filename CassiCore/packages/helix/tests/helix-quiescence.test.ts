/**
 * HelixQuiescenceDetector tests — idle detection + hard cutoff.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HelixQuiescenceDetector } from '../src/helix-quiescence.js'
import { HelixJournal } from '../src/helix-journal.js'
import { HelixLocus } from '../src/helix-locus.js'
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


describe('HelixQuiescenceDetector', () => {
  let logger: ILogger
  let journal: HelixJournal

  beforeEach(() => {
    logger = createMockLogger()
    journal = new HelixJournal({ logger, inMemory: true })
  })

  afterEach(() => {
    journal.close()
  })

  it('does not fire while session is younger than minSessionAgeMs', () => {
    const detector = new HelixQuiescenceDetector({
      sessionId: 's',
      logger,
      journal,
      config: { minSessionAgeMs: 60_000, idleWindowMs: 0 },
    })
    const report = detector.check()
    expect(report).toBeNull()
  })

  it('fires with `idle` reason when no activity events are present', () => {
    const detector = new HelixQuiescenceDetector({
      sessionId: 's',
      logger,
      journal,
      config: { minSessionAgeMs: 0, idleWindowMs: 0 },
    })
    const report = detector.check()
    expect(report).not.toBeNull()
    expect(report!.reason).toBe('idle')
  })

  it('holds off while recent activity journal entries exist', () => {
    journal.append({ sessionId: 's', eventType: 'signal.submit' })
    const detector = new HelixQuiescenceDetector({
      sessionId: 's',
      logger,
      journal,
      config: { minSessionAgeMs: 0, idleWindowMs: 60_000 },
    })
    const report = detector.check()
    expect(report).toBeNull()
  })

  it('fires when live kindles drop to zero and idle window has elapsed', () => {
    const locus = new HelixLocus({ sessionId: 's', logger })
    const detector = new HelixQuiescenceDetector({
      sessionId: 's',
      logger,
      journal,
      locus,
      config: { minSessionAgeMs: 0, idleWindowMs: 0 },
    })
    // No kindles, no activity → fires.
    expect(detector.check()).not.toBeNull()
  })

  it('hard-cutoff fires regardless of activity', async () => {
    journal.append({ sessionId: 's', eventType: 'signal.submit' })
    const detector = new HelixQuiescenceDetector({
      sessionId: 's',
      logger,
      journal,
      config: { minSessionAgeMs: 60_000, idleWindowMs: 60_000, hardCutoffMs: 10 },
    })
    await new Promise(r => setTimeout(r, 25))
    const report = detector.check()
    expect(report).not.toBeNull()
    expect(report!.reason).toBe('hard-cutoff')
  })

  it('only fires once; subsequent checks return null', () => {
    const detector = new HelixQuiescenceDetector({
      sessionId: 's',
      logger,
      journal,
      config: { minSessionAgeMs: 0, idleWindowMs: 0 },
    })
    expect(detector.check()).not.toBeNull()
    expect(detector.check()).toBeNull()
    expect(detector.check()).toBeNull()
  })

  it('delivers reports to registered listeners', () => {
    const received: any[] = []
    const detector = new HelixQuiescenceDetector({
      sessionId: 's',
      logger,
      journal,
      config: { minSessionAgeMs: 0, idleWindowMs: 0 },
    })
    detector.onQuiescence(r => received.push(r))
    detector.check()
    expect(received.length).toBe(1)
    expect(received[0].sessionId).toBe('s')
  })
})
