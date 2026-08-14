/**
 * Tests for HelixCoordinator — native coordination layer for Helix.
 *
 * Covers: broadcast work units, per-reviewer cursors, termination consensus,
 * dialectic mesh with Unity, and HelixCoordinator integration.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  HelixWorkStream,
  HelixDialecticMesh,
  HelixCoordinator,
} from '../src/helix-coordinator.js'

function makeLogger(): any {
  return {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    child: () => makeLogger(),
  }
}

function makeWorkUnit(id: string, content = 'test content'): any {
  return {
    id,
    iteration: 1,
    reasoning: content,
    toolCalls: [],
    toolResults: [],
    filesModified: [],
    timestamp: Date.now(),
  }
}


describe('HelixWorkStream broadcast', () => {
  let ws: HelixWorkStream

  beforeEach(() => {
    ws = new HelixWorkStream()
  })

  it('should give the same work unit to both reviewers', async () => {
    ws.postWorkUnit(makeWorkUnit('wu-1'))

    const yangWU = await ws.nextWorkUnitForReviewer('yang', 100)
    const yinWU = await ws.nextWorkUnitForReviewer('yin', 100)

    expect(yangWU?.id).toBe('wu-1')
    expect(yinWU?.id).toBe('wu-1')
  })

  it('should maintain independent cursors per reviewer', async () => {
    ws.postWorkUnit(makeWorkUnit('wu-1', 'first'))
    ws.postWorkUnit(makeWorkUnit('wu-2', 'second'))

    // Yang reads both
    const y1 = await ws.nextWorkUnitForReviewer('yang', 100)
    const y2 = await ws.nextWorkUnitForReviewer('yang', 100)
    expect(y1?.id).toBe('wu-1')
    expect(y2?.id).toBe('wu-2')

    // Yin reads both independently
    const i1 = await ws.nextWorkUnitForReviewer('yin', 100)
    const i2 = await ws.nextWorkUnitForReviewer('yin', 100)
    expect(i1?.id).toBe('wu-1')
    expect(i2?.id).toBe('wu-2')
  })

  it('should return null on timeout when no work units available', async () => {
    const result = await ws.nextWorkUnitForReviewer('yang', 50)
    expect(result).toBeNull()
  })

  it('should return null when Unity is done and all work seen', async () => {
    ws.postWorkUnit(makeWorkUnit('wu-1'))
    await ws.nextWorkUnitForReviewer('yang', 100)
    ws.signalWorkerDone()

    const result = await ws.nextWorkUnitForReviewer('yang', 100)
    expect(result).toBeNull()
  })

  it('should notify waiting reviewers when work unit is posted', async () => {
    const promise = ws.nextWorkUnitForReviewer('yang', 5000)

    // Post after a short delay
    setTimeout(() => ws.postWorkUnit(makeWorkUnit('wu-1')), 50)

    const result = await promise
    expect(result?.id).toBe('wu-1')
  })

  it('should unblock all waiters when Unity signals done', async () => {
    const yangPromise = ws.nextWorkUnitForReviewer('yang', 5000)
    const yinPromise = ws.nextWorkUnitForReviewer('yin', 5000)

    setTimeout(() => ws.signalWorkerDone(), 50)

    const [yangResult, yinResult] = await Promise.all([yangPromise, yinPromise])
    expect(yangResult).toBeNull()
    expect(yinResult).toBeNull()
  })
})


describe('HelixWorkStream termination', () => {
  let ws: HelixWorkStream

  beforeEach(() => {
    ws = new HelixWorkStream()
  })

  it('should track whether a reviewer has seen all work units', async () => {
    ws.postWorkUnit(makeWorkUnit('wu-1'))

    expect(ws.hasReviewerSeenAll('yang')).toBe(false)

    await ws.nextWorkUnitForReviewer('yang', 100)
    expect(ws.hasReviewerSeenAll('yang')).toBe(true)
    // Yin hasn't seen it yet
    expect(ws.hasReviewerSeenAll('yin')).toBe(false)
  })

  it('should reach termination consensus when Unity done and all reviewers ready', async () => {
    ws.postWorkUnit(makeWorkUnit('wu-1'))

    await ws.nextWorkUnitForReviewer('yang', 100)
    await ws.nextWorkUnitForReviewer('yin', 100)
    ws.signalWorkerDone()
    ws.signalReviewerReady('yang')
    ws.signalReviewerReady('yin')

    expect(ws.isTerminationConsensus(['yang', 'yin'])).toBe(true)
  })

  it('should not reach consensus if a reviewer has not seen all work', async () => {
    ws.postWorkUnit(makeWorkUnit('wu-1'))

    await ws.nextWorkUnitForReviewer('yang', 100)
    ws.signalWorkerDone()
    ws.signalReviewerReady('yang')
    // Yin hasn't seen wu-1

    expect(ws.isTerminationConsensus(['yang', 'yin'])).toBe(false)
  })

  it('should report reviewer progress', async () => {
    ws.postWorkUnit(makeWorkUnit('wu-1'))
    ws.postWorkUnit(makeWorkUnit('wu-2'))

    await ws.nextWorkUnitForReviewer('yang', 100)

    const progress = ws.getReviewerProgress('yang')
    expect(progress.cursor).toBe(1)
    expect(progress.total).toBe(2)
    expect(progress.ready).toBe(false)
  })
})


describe('HelixDialecticMesh', () => {
  it('should let Unity drain all dialectic messages', () => {
    const mesh = new HelixDialecticMesh()

    mesh.postFinding('yang', 'Code looks clean', 'reviewed main.ts')
    mesh.postFinding('yin', 'Missing error handling', 'no try-catch in handler')

    const unityView = mesh.drainForUnity()
    expect(unityView).toHaveLength(2)
    expect(unityView[0].type).toBe('finding')
  })

  it('should track Unity cursor and only return new messages', () => {
    const mesh = new HelixDialecticMesh()

    mesh.postFinding('yang', 'First finding')
    mesh.drainForUnity() // Reads 1 message

    mesh.postFinding('yin', 'Second finding')
    const newMessages = mesh.drainForUnity()
    expect(newMessages).toHaveLength(1)
    expect(newMessages[0].type).toBe('finding')
  })

  it('should allow Unity to post findings via postUnityFinding', () => {
    const mesh = new HelixDialecticMesh()
    const id = mesh.postUnityFinding('Unity observation', 'evidence from tool output')
    expect(typeof id).toBe('string')
  })
})


describe('HelixCoordinator', () => {
  it('should create with HelixWorkStream and HelixDialecticMesh', () => {
    const coord = new HelixCoordinator({
      sessionId: 'test-session',
      logger: makeLogger(),
    })

    expect(coord.workStream).toBeInstanceOf(HelixWorkStream)
    expect(coord.dialecticMesh).toBeInstanceOf(HelixDialecticMesh)
  })

  it('should report progress for all reviewers', async () => {
    const coord = new HelixCoordinator({
      sessionId: 'test-session',
      logger: makeLogger(),
    })

    coord.workStream.postWorkUnit(makeWorkUnit('wu-1'))
    await coord.workStream.nextWorkUnitForReviewer('yang', 100)

    const progress = coord.getProgress()
    expect(progress.yang.cursor).toBe(1)
    expect(progress.yang.total).toBe(1)
    expect(progress.yin.cursor).toBe(0)
    expect(progress.yin.total).toBe(1)
  })

  it('should provide Unity view of dialectic activity', () => {
    const coord = new HelixCoordinator({
      sessionId: 'test-session',
      logger: makeLogger(),
    })

    coord.dialecticMesh.postFinding('yang', 'Good architecture')
    coord.dialecticMesh.postFinding('yin', 'Missing tests')

    const view = coord.getUnityView()
    expect(view).toHaveLength(2)
    expect(view[0]).toContain('yang')
    expect(view[1]).toContain('yin')
  })

  it('should track metrics: work units auto-increment on postWorkUnit', () => {
    const coord = new HelixCoordinator({
      sessionId: 'test-session',
      logger: makeLogger(),
    })

    const snapshot1 = coord.getMetricsSnapshot()
    expect(snapshot1.workUnitsProduced).toBe(0)
    expect(snapshot1.nudgesSent).toBe(0)
    expect(snapshot1.sessionDurationMs).toBeGreaterThanOrEqual(0)

    // Post work units — should auto-increment via HelixWorkStream override
    coord.workStream.postWorkUnit(makeWorkUnit('wu-1'))
    coord.workStream.postWorkUnit(makeWorkUnit('wu-2'))
    coord.workStream.postWorkUnit(makeWorkUnit('wu-3'))

    const snapshot2 = coord.getMetricsSnapshot()
    expect(snapshot2.workUnitsProduced).toBe(3)
  })

  it('should track metrics: nudges auto-increment on postNudge', () => {
    const coord = new HelixCoordinator({
      sessionId: 'test-session',
      logger: makeLogger(),
    })

    // Post a nudge through the work stream
    coord.workStream.postNudge({
      id: 'nudge-1',
      from: 'yang',
      to: 'unity',
      severity: 'low',
      content: 'Consider better error handling',
      timestamp: Date.now(),
      acknowledged: false,
    } as any, 1)

    const snapshot = coord.getMetricsSnapshot()
    expect(snapshot.nudgesSent).toBe(1)
  })

  it('should track metrics: reviewer iterations via recordReviewerIteration', () => {
    const coord = new HelixCoordinator({
      sessionId: 'test-session',
      logger: makeLogger(),
    })

    coord.recordReviewerIteration('yang')
    coord.recordReviewerIteration('yang')
    coord.recordReviewerIteration('yin')

    const snapshot = coord.getMetricsSnapshot()
    expect(snapshot.reviewerIterations.yang).toBe(2)
    expect(snapshot.reviewerIterations.yin).toBe(1)
  })

  it('should track session duration in metrics', async () => {
    const coord = new HelixCoordinator({
      sessionId: 'test-session',
      logger: makeLogger(),
    })

    // Wait a small amount to get a non-zero duration
    await new Promise(r => setTimeout(r, 10))

    const snapshot = coord.getMetricsSnapshot()
    expect(snapshot.sessionDurationMs).toBeGreaterThan(0)
  })
})
