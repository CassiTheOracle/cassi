/**
 * HelixConductor tests — brain-integrated session lifecycle.
 *
 * Uses in-memory SQLite for journal + session store and a mock GlobalWorkspace
 * to verify the conductor wires posture modules + journaling + snapshots.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HelixConductor } from '../src/helix-conductor.js'
import { HelixJournal } from '../src/helix-journal.js'
import { HelixSessionStore } from '../src/helix-session-store.js'
import { HelixTelemetry } from '../src/helix-telemetry.js'
import type { CognitiveSignal } from '../src/vendor/core/intelligence/workspace/index.js'
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


function createMockWorkspace() {
  const handlers: Array<(signals: CognitiveSignal[]) => void> = []
  const submit = vi.fn((signal: CognitiveSignal) => {
    signal.luminance = { novelty: 1, urgency: 1, relevance: 1, sourceCredibility: 1, composite: 1 }
    return true
  })
  return {
    submit,
    onBroadcast(h: (s: CognitiveSignal[]) => void) {
      handlers.push(h)
      return () => {
        const idx = handlers.indexOf(h)
        if (idx >= 0) handlers.splice(idx, 1)
      }
    },
    emit(signals: CognitiveSignal[]) {
      for (const h of handlers) h(signals)
    },
    getSnapshot() {
      return { threshold: 0.25, slots: [] }
    },
    onRadiance: vi.fn(() => () => { /* noop */ }),
  }
}


describe('HelixConductor', () => {
  let logger: ILogger
  let journal: HelixJournal
  let sessionStore: HelixSessionStore
  let telemetry: HelixTelemetry

  beforeEach(() => {
    logger = createMockLogger()
    journal = new HelixJournal({ logger, inMemory: true })
    sessionStore = new HelixSessionStore({ logger, inMemory: true })
    telemetry = new HelixTelemetry(logger)
  })

  afterEach(() => {
    journal.close()
    sessionStore.close()
    telemetry.shutdown()
  })

  it('journals session.start + posture.lifecycle on start, terminate on stop', async () => {
    const ws = createMockWorkspace()
    const conductor = new HelixConductor({
      sessionId: 'sess-a',
      goal: 'test goal',
      logger,
      globalWorkspace: ws as any,
      journal,
      sessionStore,
      telemetry,
      snapshotIntervalMs: 0,
    })

    await conductor.start()
    await conductor.stop('ok')

    const events = journal.readSession('sess-a')
    const types = events.map(e => e.eventType)

    expect(types[0]).toBe('session.start')
    expect(types.filter(t => t === 'posture.lifecycle').length).toBe(6) // 3 starts + 3 stops
    expect(types.includes('session.terminate')).toBe(true)
    expect(types.includes('snapshot.taken')).toBe(true)
  })

  it('exposes three PostureModules keyed by role', async () => {
    const ws = createMockWorkspace()
    const conductor = new HelixConductor({
      sessionId: 's',
      goal: 'g',
      logger,
      globalWorkspace: ws as any,
      journal,
      sessionStore,
      telemetry,
      snapshotIntervalMs: 0,
    })
    await conductor.start()

    const modules = conductor.getPostureModules()
    expect(Object.keys(modules).sort()).toEqual(['unity', 'yang', 'yin'])
    expect(modules['unity']?.role).toBe('unity')
    expect(modules['yang']?.role).toBe('yang')
    expect(modules['yin']?.role).toBe('yin')

    await conductor.stop()
  })

  it('journals workspace.broadcast entries for session-scoped signals', async () => {
    const ws = createMockWorkspace()
    const conductor = new HelixConductor({
      sessionId: 's',
      goal: 'g',
      logger,
      globalWorkspace: ws as any,
      journal,
      sessionStore,
      telemetry,
      snapshotIntervalMs: 0,
    })
    await conductor.start()

    const matching: CognitiveSignal = {
      signalId: 'sig-1',
      source: 'helix-yang-x',
      sessionId: 's',
      type: 'observation',
      content: 'hi',
      luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, composite: 0.5 },
      createdAt: Date.now(),
      metadata: { correlation: 'c-1' },
    }
    const otherSession: CognitiveSignal = { ...matching, signalId: 'sig-2', sessionId: 'other' }

    ws.emit([matching, otherSession])

    const broadcasts = journal.readSession('s').filter(e => e.eventType === 'workspace.broadcast')
    expect(broadcasts.length).toBe(1)
    expect((broadcasts[0]!.payload as any).signals.length).toBe(1)
    expect((broadcasts[0]!.payload as any).signals[0].signalId).toBe('sig-1')

    await conductor.stop()
  })

  it('journals signal.submit via telemetry when a PostureModule publishes', async () => {
    const ws = createMockWorkspace()
    const conductor = new HelixConductor({
      sessionId: 's',
      goal: 'g',
      logger,
      globalWorkspace: ws as any,
      journal,
      sessionStore,
      telemetry,
      snapshotIntervalMs: 0,
    })
    await conductor.start()

    const unity = conductor.getPostureModules()['unity']!
    unity.publish('observation', 'work unit', {
      kind: 'work-unit',
      correlation: 'work-1',
    })
    // Emulate the runner's telemetry hook — this is how the posture-runner
    // signals the conductor's journal in production.
    telemetry.recordSignalSubmit({
      sessionId: 's',
      posture: 'unity',
      signalType: 'observation',
      correlation: 'work-1',
      kind: 'work-unit',
      ignited: true,
    })

    const submits = journal.readSession('s').filter(e => e.eventType === 'signal.submit')
    expect(submits.length).toBe(1)
    expect(submits[0]!.correlationId).toBe('work-1')
    expect(submits[0]!.postureId).toBe('helix-unity')

    await conductor.stop()
  })

  it('takeSnapshot persists a HelixSnapshot readable via the session store', async () => {
    const ws = createMockWorkspace()
    const conductor = new HelixConductor({
      sessionId: 's',
      goal: 'g',
      logger,
      globalWorkspace: ws as any,
      journal,
      sessionStore,
      telemetry,
      snapshotIntervalMs: 0,
    })
    await conductor.start()
    conductor.takeSnapshot()

    const loaded = sessionStore.loadSnapshot('s')
    expect(loaded?.state.postures.length).toBe(3)
    expect(loaded?.state.conductor.status).toBe('running')

    await conductor.stop()
  })

  it('feeds session broadcasts through HelixLocus and journals kindle.spark', async () => {
    const ws = createMockWorkspace()
    const conductor = new HelixConductor({
      sessionId: 's',
      goal: 'g',
      logger,
      globalWorkspace: ws as any,
      journal,
      sessionStore,
      telemetry,
      snapshotIntervalMs: 0,
    })
    await conductor.start()

    const yangChallenge: CognitiveSignal = {
      signalId: 'sig-c',
      source: 'helix-yang-x',
      sessionId: 's',
      type: 'tension',
      content: 'edge case X',
      luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, composite: 0.9 },
      createdAt: Date.now(),
      metadata: { kind: 'challenge', posture: 'yang', correlation: 'f-1' },
    }
    ws.emit([yangChallenge])

    const kindleSparkEntries = journal.readSession('s').filter(e => e.eventType === 'kindle.spark')
    expect(kindleSparkEntries.length).toBe(1)
    expect((kindleSparkEntries[0]!.payload as any).kind).toBe('challenge')

    await conductor.stop()

    const radiateEntries = journal.readSession('s').filter(e => e.eventType === 'kindle.radiate')
    expect(radiateEntries.length).toBeGreaterThanOrEqual(1)
    expect((radiateEntries[0]!.payload as any).reason).toBe('session-end')
  })

  it('unregisters postures from telemetry on stop', async () => {
    const ws = createMockWorkspace()
    const conductor = new HelixConductor({
      sessionId: 's',
      goal: 'g',
      logger,
      globalWorkspace: ws as any,
      journal,
      sessionStore,
      telemetry,
      snapshotIntervalMs: 0,
    })
    await conductor.start()
    await conductor.stop()

    const stopLifecycleEntries = journal
      .readSession('s')
      .filter(e => e.eventType === 'posture.lifecycle' && (e.payload as any).phase === 'stopped')
    expect(stopLifecycleEntries.length).toBe(3)
  })
})
