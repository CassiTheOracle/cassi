/**
 * Phase C integration test — cross-posture round-trip via GlobalWorkspace.
 *
 * Validates the end-to-end brain-integration flow without running a full
 * Helix pipeline (no model handles needed). Wires:
 *
 *   - A real GlobalWorkspace (with luminance scoring + ignition).
 *   - A real HelixJournal (in-memory SQLite).
 *   - A real HelixTelemetry bridged to the journal.
 *   - Three PostureModules (unity / yang / yin) subscribed to the workspace.
 *
 * Asserts:
 *   - Yang publishes a `finding` (observation with correlation) → journal
 *     records signal.submit, workspace broadcasts to Yin + Unity.
 *   - Yin sees the finding, publishes a `challenge` (tension, same correlation).
 *   - Unity sees the challenge, publishes a `concession` (insight, same correlation).
 *   - Journal.readByCorrelation returns all three in temporal order.
 *   - Signal metadata carries posture, recipient, kind, correlation intact.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { EventEmitter } from 'events'

import { GlobalWorkspace } from '../src/vendor/core/intelligence/workspace/index.js'
import { HelixJournal } from '../src/helix-journal.js'
import { HelixTelemetry } from '../src/helix-telemetry.js'
import { PostureModule } from '../src/posture-module.js'
import { UNITY_POSTURE, YANG_POSTURE, YIN_POSTURE } from '../src/helix-postures.js'
import type { ILogger, IEventBus } from '@cassicore/foundation'


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


function createEventBus(): IEventBus {
  const emitter = new EventEmitter()
  emitter.setMaxListeners(50)
  const bus: IEventBus = {
    emit: vi.fn(async (evt: any) => {
      emitter.emit(String(evt.type), evt)
    }),
    on: (type: any, handler: (e: any) => void) => {
      const key = String(type)
      emitter.on(key, handler)
      return () => emitter.off(key, handler)
    },
  } as any
  return bus
}


describe('Phase C — cross-posture round-trip via GlobalWorkspace', () => {
  let logger: ILogger
  let bus: IEventBus
  let workspace: GlobalWorkspace
  let journal: HelixJournal
  let telemetry: HelixTelemetry
  let unity: PostureModule
  let yang: PostureModule
  let yin: PostureModule

  const sessionId = 'test-session'
  const roleId = 'rt'

  beforeEach(() => {
    logger = createMockLogger()
    bus = createEventBus()
    workspace = new GlobalWorkspace(logger, { ignitionThreshold: 0 })
    workspace.setEventBus(bus)

    journal = new HelixJournal({ logger, inMemory: true })
    telemetry = new HelixTelemetry(logger)
    telemetry.setJournal(journal)
    telemetry.setEventBus(bus)
    telemetry.startSession(sessionId, { goal: 'round-trip-test', roleId })

    const make = (posture: typeof UNITY_POSTURE) => {
      const mod = new PostureModule(logger, { posture, sessionId, roleId })
      mod.setEventBus(bus)
      mod.setGlobalWorkspace(workspace)
      telemetry.registerPostureSession(mod.name, sessionId)
      return mod
    }

    unity = make(UNITY_POSTURE)
    yang = make(YANG_POSTURE)
    yin = make(YIN_POSTURE)
  })

  afterEach(async () => {
    await unity.stop()
    await yang.stop()
    await yin.stop()
    telemetry.shutdown()
    journal.close()
  })

  function publishAndRecord(
    mod: PostureModule,
    type: 'observation' | 'tension' | 'insight',
    content: string,
    opts: { correlation?: string; recipient?: string; kind?: string } = {},
  ): boolean {
    const ignited = mod.publish(type, content, opts)
    telemetry.recordSignalSubmit({
      sessionId,
      posture: mod.role,
      signalType: type,
      correlation: opts.correlation,
      recipient: opts.recipient,
      kind: opts.kind,
      ignited,
    })
    return ignited
  }

  it('finding → challenge → concession threads through correlation', () => {
    const correlation = 'finding-1'

    // Yang finds something.
    const yangIgnited = publishAndRecord(yang, 'observation', 'The pagination helper is fragile under empty input.', {
      correlation,
      kind: 'finding',
    })
    expect(yangIgnited).toBe(true)

    // Broadcast the workspace so the other PostureModules pick up the signal.
    workspace.broadcast()
    const yinQueued = yin.drainBroadcasts()
    const unityQueued = unity.drainBroadcasts()
    expect(yinQueued.map(s => s.signalId)).toHaveLength(1)
    expect(yinQueued[0]!.metadata).toMatchObject({
      posture: 'yang',
      kind: 'finding',
      correlation,
    })
    expect(unityQueued.map(s => s.signalId)).toHaveLength(1)

    // Yin challenges it.
    const yinIgnited = publishAndRecord(yin, 'tension', 'Counter: the caller guards against empty already.', {
      correlation,
      kind: 'challenge',
    })
    expect(yinIgnited).toBe(true)

    workspace.broadcast()
    const yangQueued = yang.drainBroadcasts()
    const unityQueued2 = unity.drainBroadcasts()
    expect(yangQueued.find(s => s.metadata?.kind === 'challenge')).toBeTruthy()
    expect(unityQueued2.find(s => s.metadata?.kind === 'challenge')).toBeTruthy()

    // Unity concedes.
    const unityIgnited = publishAndRecord(unity, 'insight', 'Conceded: the guard covers it.', {
      correlation,
      kind: 'concession',
    })
    expect(unityIgnited).toBe(true)

    workspace.broadcast()

    // Journal must thread the whole exchange under the same correlation.
    const thread = journal.readByCorrelation(correlation)
    const submitEntries = thread.filter(e => e.eventType === 'signal.submit')
    expect(submitEntries.length).toBe(3)
    const kinds = submitEntries.map(e => (e.payload as any).kind)
    expect(kinds).toEqual(['finding', 'challenge', 'concession'])
    const postures = submitEntries.map(e => e.postureId)
    expect(postures).toEqual(['helix-yang', 'helix-yin', 'helix-unity'])
  })

  it('recipient-targeted nudge reaches Unity only', () => {
    const ignited = publishAndRecord(yang, 'observation', 'Try pattern X next iteration.', {
      kind: 'nudge',
      recipient: 'unity',
    })
    expect(ignited).toBe(true)
    workspace.broadcast()

    const yinQueued = yin.drainBroadcasts()
    const unityQueued = unity.drainBroadcasts()

    expect(yinQueued.length).toBe(0)
    expect(unityQueued.length).toBe(1)
    expect(unityQueued[0]!.metadata?.kind).toBe('nudge')
  })

  it('ignition events are journaled with session id via posture registration', async () => {
    publishAndRecord(yang, 'observation', 'A finding.', { kind: 'finding', correlation: 'f-2' })

    // Ignition journaling happens synchronously after submit inside the
    // telemetry EventBus subscriber — wait a microtask so it flushes.
    await new Promise(r => setImmediate(r))

    const igniteEntries = journal
      .readSession(sessionId)
      .filter(e => e.eventType === 'signal.ignite')
    expect(igniteEntries.length).toBeGreaterThanOrEqual(1)
    expect(igniteEntries[0]!.postureId).toBe(yang.name)
    expect((igniteEntries[0]!.payload as any).signalType).toBe('observation')
  })

  it('stats counters track submissions + ignitions per posture', () => {
    publishAndRecord(yang, 'observation', 'a', { kind: 'finding' })
    publishAndRecord(yang, 'observation', 'b', { kind: 'finding' })
    publishAndRecord(yin, 'tension', 'c', { kind: 'challenge' })

    const metrics = telemetry.getMetricsSnapshot()
    expect(metrics.signalsSubmitted['helix-yang']).toBe(2)
    expect(metrics.signalsSubmitted['helix-yin']).toBe(1)
    expect(yang.getStats().submitted).toBe(2)
    expect(yin.getStats().submitted).toBe(1)
  })
})
