/**
 * PostureModule tests — Phase A scaffold.
 *
 * Verifies that Helix postures wrapped in a PostureModule publish
 * CognitiveSignals with the right metadata, filter incoming broadcasts by
 * session / sender / recipient, and clean up on stop.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { CognitiveSignal } from '@cassicore/workspace'
import { PostureModule } from '../src/posture-module.js'
import { UNITY_POSTURE, YANG_POSTURE } from '../src/helix-postures.js'
import type { ILogger } from '@cassicore/foundation'


function createMockLogger(): ILogger {
  const make = () => vi.fn()
  const logger: ILogger = {
    debug: make(),
    info: make(),
    warn: make(),
    error: make(),
    child: () => logger,
  } as any
  return logger
}


interface CapturedWorkspace {
  submit: ReturnType<typeof vi.fn>
  onBroadcast: (handler: (signals: CognitiveSignal[]) => void) => () => void
  emit: (signals: CognitiveSignal[]) => void
  getSnapshot: () => { threshold: number; slots: Array<{ signal: CognitiveSignal | null }> }
  onRadiance: ReturnType<typeof vi.fn>
}

function createMockWorkspace(shouldIgnite = true): CapturedWorkspace {
  const handlers: Array<(signals: CognitiveSignal[]) => void> = []
  const submit = vi.fn((signal: CognitiveSignal) => {
    signal.luminance = { novelty: 1, urgency: 1, relevance: 1, sourceCredibility: 1, composite: 1 }
    return shouldIgnite
  })
  return {
    submit,
    onBroadcast(handler) {
      handlers.push(handler)
      return () => {
        const idx = handlers.indexOf(handler)
        if (idx >= 0) handlers.splice(idx, 1)
      }
    },
    emit(signals) {
      for (const h of handlers) h(signals)
    },
    getSnapshot() {
      return { threshold: 0.25, slots: [] }
    },
    onRadiance: vi.fn(() => () => { /* no-op */ }),
  }
}


function makeSignal(partial: Partial<CognitiveSignal>): CognitiveSignal {
  return {
    signalId: partial.signalId ?? 'sig-1',
    source: partial.source ?? 'other',
    sessionId: partial.sessionId ?? 'session-a',
    type: partial.type ?? 'observation',
    content: partial.content ?? 'hello',
    luminance: partial.luminance ?? { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, composite: 0 },
    createdAt: partial.createdAt ?? Date.now(),
    metadata: partial.metadata,
  }
}


describe('PostureModule', () => {
  let logger: ILogger

  beforeEach(() => {
    logger = createMockLogger()
  })

  it('derives a unique name from role + roleId', () => {
    const mod = new PostureModule(logger, {
      posture: UNITY_POSTURE,
      sessionId: 'session-abc',
      roleId: 'abc',
    })
    expect(mod.name).toBe('helix-unity-abc')
    expect(mod.role).toBe('unity')
    expect(mod.sessionId).toBe('session-abc')
  })

  it('publish() no-ops when no GlobalWorkspace is wired', () => {
    const mod = new PostureModule(logger, {
      posture: UNITY_POSTURE,
      sessionId: 'session-a',
      roleId: 'a',
    })
    const ignited = mod.publish('observation', 'work unit')
    expect(ignited).toBe(false)
    expect(mod.getStats().submitted).toBe(0)
  })

  it('publish() submits with helix metadata (posture, roleId, correlation, recipient, kind)', () => {
    const ws = createMockWorkspace(true)
    const mod = new PostureModule(logger, {
      posture: YANG_POSTURE,
      sessionId: 'session-x',
      roleId: 'xyz',
    })
    mod.setGlobalWorkspace(ws as any)

    const ignited = mod.publish('tension', 'this might break', {
      correlation: 'finding-42',
      recipient: 'helix-unity-xyz',
      kind: 'challenge',
      extra: { severity: 'high' },
    })

    expect(ignited).toBe(true)
    expect(ws.submit).toHaveBeenCalledTimes(1)
    const signal = ws.submit.mock.calls[0][0] as CognitiveSignal
    expect(signal.source).toBe('helix-yang-xyz')
    expect(signal.sessionId).toBe('session-x')
    expect(signal.type).toBe('tension')
    expect(signal.content).toBe('this might break')
    expect(signal.metadata).toMatchObject({
      helix: true,
      sessionId: 'session-x',
      posture: 'yang',
      roleId: 'xyz',
      correlation: 'finding-42',
      recipient: 'helix-unity-xyz',
      kind: 'challenge',
      severity: 'high',
    })

    expect(mod.getStats().submitted).toBe(1)
    expect(mod.getStats().ignited).toBe(1)
  })

  it('tracks submitted vs ignited separately when signals fail to ignite', () => {
    const ws = createMockWorkspace(false)
    const mod = new PostureModule(logger, {
      posture: YANG_POSTURE,
      sessionId: 's',
      roleId: '1',
    })
    mod.setGlobalWorkspace(ws as any)

    mod.publish('observation', 'noise')
    mod.publish('observation', 'more noise')

    expect(mod.getStats().submitted).toBe(2)
    expect(mod.getStats().ignited).toBe(0)
  })

  it('onWorkspaceBroadcast queues only session-relevant, non-self signals', () => {
    const ws = createMockWorkspace()
    const mod = new PostureModule(logger, {
      posture: UNITY_POSTURE,
      sessionId: 'session-a',
      roleId: 'a',
    })
    mod.setGlobalWorkspace(ws as any)

    const mine = makeSignal({ signalId: 's1', source: mod.name, sessionId: 'session-a' })
    const otherSession = makeSignal({ signalId: 's2', source: 'helix-yang-other', sessionId: 'session-b' })
    const relevant = makeSignal({ signalId: 's3', source: 'helix-yang-a', sessionId: 'session-a' })
    const global = makeSignal({ signalId: 's4', source: 'thinker', sessionId: '*' })

    ws.emit([mine, otherSession, relevant, global])
    const drained = mod.drainBroadcasts()

    expect(drained.map(s => s.signalId)).toEqual(['s3', 's4'])
  })

  it('filters broadcasts by recipient when one is specified', () => {
    const ws = createMockWorkspace()
    const unity = new PostureModule(logger, { posture: UNITY_POSTURE, sessionId: 's', roleId: 'a' })
    const yang = new PostureModule(logger, { posture: YANG_POSTURE, sessionId: 's', roleId: 'a' })
    unity.setGlobalWorkspace(ws as any)
    yang.setGlobalWorkspace(ws as any)

    const nudgeToUnityByName = makeSignal({
      signalId: 'n1',
      source: yang.name,
      sessionId: 's',
      metadata: { recipient: unity.name },
    })
    const nudgeToUnityByRole = makeSignal({
      signalId: 'n2',
      source: yang.name,
      sessionId: 's',
      metadata: { recipient: 'unity' },
    })
    const unrecipiented = makeSignal({
      signalId: 'n3',
      source: yang.name,
      sessionId: 's',
    })

    ws.emit([nudgeToUnityByName, nudgeToUnityByRole, unrecipiented])

    const unitySeen = unity.drainBroadcasts().map(s => s.signalId).sort()
    const yangSeen = yang.drainBroadcasts().map(s => s.signalId).sort()

    expect(unitySeen).toEqual(['n1', 'n2', 'n3'])
    expect(yangSeen).toEqual([])
  })

  it('awaitBroadcast resolves on next emission', async () => {
    const ws = createMockWorkspace()
    const mod = new PostureModule(logger, { posture: UNITY_POSTURE, sessionId: 's', roleId: 'a' })
    mod.setGlobalWorkspace(ws as any)

    const waitPromise = mod.awaitBroadcast(500)
    ws.emit([makeSignal({ signalId: 's1', source: 'helix-yang-a', sessionId: 's' })])
    const signals = await waitPromise
    expect(signals.map(s => s.signalId)).toEqual(['s1'])
  })

  it('awaitBroadcast returns [] on timeout when no relevant signals arrive', async () => {
    const ws = createMockWorkspace()
    const mod = new PostureModule(logger, { posture: UNITY_POSTURE, sessionId: 's', roleId: 'a' })
    mod.setGlobalWorkspace(ws as any)

    const start = Date.now()
    const signals = await mod.awaitBroadcast(50)
    expect(signals).toEqual([])
    expect(Date.now() - start).toBeGreaterThanOrEqual(45)
  })

  it('stop() stops accepting new signals and clears queued ones', async () => {
    const ws = createMockWorkspace()
    const mod = new PostureModule(logger, { posture: UNITY_POSTURE, sessionId: 's', roleId: 'a' })
    mod.setGlobalWorkspace(ws as any)

    ws.emit([makeSignal({ signalId: 's1', source: 'helix-yang-a', sessionId: 's' })])
    expect(mod.getStats().queued).toBe(1)

    await mod.stop()

    expect(mod.getStats().queued).toBe(0)
    const ignited = mod.publish('observation', 'after stop')
    expect(ignited).toBe(false)
    expect(mod.getStats().submitted).toBe(0)
  })
})
