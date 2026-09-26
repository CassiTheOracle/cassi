/**
 * Tests for RefusalChannel — Unified Refusal Channel (URC).
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Database from 'better-sqlite3'
import { RefusalChannel } from './refusal-channel.js'
import type { ActionKind, ActionRecord, ActionStatus, ConsentRule, ProposedAction, RefusalChannelConfig } from './refusal-channel.js'

function mockLogger() {
  const logs: { level: string; msg: string; data?: any }[] = []
  return {
    debug: (msg: string, data?: any) => logs.push({ level: 'debug', msg, data }),
    info: (msg: string, data?: any) => logs.push({ level: 'info', msg, data }),
    warn: (msg: string, data?: any) => logs.push({ level: 'warn', msg, data }),
    error: (msg: string, data?: any) => logs.push({ level: 'error', msg, data }),
    child: () => mockLogger(),
    logs,
  } as any
}

function makeChannel(config?: Partial<RefusalChannelConfig>): RefusalChannel {
  const db = new Database(':memory:')
  return new RefusalChannel(db, mockLogger(), config)
}

describe('RefusalChannel', () => {
  it('should propose an auto-approved action and resolve immediately', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'composition_activation',
      payload: { name: 'focus' },
    })

    expect(handle.kind).toBe('composition_activation')
    expect(handle.id).toMatch(/^urc_/)

    // Auto-approved actions should already be approved
    const record = channel.get(handle)
    expect(record?.status).toBe('approved')
    expect(record?.resolvedBy).toBe('auto-approved')

    channel.close()
  })

  it('should propose an operator-only action and leave it pending', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
    })

    const record = channel.get(handle)
    expect(record?.status).toBe('proposed')
    expect(record?.resolvedBy).toBeNull()

    channel.close()
  })

  it('should approve a pending action', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
    })

    channel.approve(handle, 'operator')
    const record = channel.get(handle)
    expect(record?.status).toBe('approved')
    expect(record?.resolvedBy).toBe('operator')

    channel.close()
  })

  it('should refuse a pending action with reason', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
    })

    channel.refuse(handle, 'cassi', 'Not the right time')
    const record = channel.get(handle)
    expect(record?.status).toBe('refused')
    expect(record?.reason).toBe('Not the right time')

    channel.close()
  })

  it('should modify a pending action, creating a linked proposal', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1', priority: 'high' },
    })

    const newHandle = channel.modify(handle, {
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1', priority: 'medium' },
    }, 'operator', 'Lower priority')

    // Original should be 'modified'
    const original = channel.get(handle)
    expect(original?.status).toBe('modified')
    expect(original?.modifiedToId).toBe(newHandle.id)

    // New should be pending
    const revised = channel.get(newHandle)
    expect(revised?.status).toBe('proposed')
    expect(revised?.payload).toEqual({ gapId: 'gap_1', priority: 'medium' })

    channel.close()
  })

  it('should defer a pending action', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
    })

    channel.defer(handle, 'operator', 'Wait for review', 3600)
    const record = channel.get(handle)
    expect(record?.status).toBe('deferred')
    expect(record?.reason).toBe('Wait for review')

    channel.close()
  })

  it('should not allow double-resolution', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
    })

    channel.approve(handle, 'operator')
    // Second approve should be a no-op
    channel.approve(handle, 'cassi')

    const record = channel.get(handle)
    expect(record?.status).toBe('approved')
    // First approver wins
    expect(record?.resolvedBy).toBe('operator')

    channel.close()
  })

  it('should not allow refusing an already-approved action', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
    })

    channel.approve(handle, 'operator')
    channel.refuse(handle, 'cassi', 'Too late')

    const record = channel.get(handle)
    expect(record?.status).toBe('approved')

    channel.close()
  })

  it('should list pending actions', () => {
    const channel = makeChannel()
    channel.proposeAction({ kind: 'meditation_schedule', payload: { gapId: 'gap_1' } })
    channel.proposeAction({ kind: 'meditation_schedule', payload: { gapId: 'gap_2' } })
    // Auto-approved won't show as pending
    channel.proposeAction({ kind: 'composition_activation', payload: { name: 'test' } })

    const pending = channel.getPending()
    expect(pending).toHaveLength(2)
    expect(pending.every(r => r.status === 'proposed')).toBe(true)

    channel.close()
  })

  it('should list actions by status', () => {
    const channel = makeChannel()
    const h1 = channel.proposeAction({ kind: 'meditation_schedule', payload: { gapId: 'gap_1' } })
    channel.refuse(h1, 'cassi', 'Bad idea')
    channel.proposeAction({ kind: 'meditation_schedule', payload: { gapId: 'gap_2' } })

    const refused = channel.list({ statuses: ['refused'] })
    expect(refused).toHaveLength(1)
    expect(refused[0].status).toBe('refused')

    const proposed = channel.list({ statuses: ['proposed'] })
    expect(proposed).toHaveLength(1)

    channel.close()
  })

  it('should list actions by kind', () => {
    const channel = makeChannel()
    channel.proposeAction({ kind: 'meditation_schedule', payload: {} })
    channel.proposeAction({ kind: 'overlay_patch_apply', payload: {} })
    channel.proposeAction({ kind: 'meditation_schedule', payload: {} })

    const meditation = channel.list({ kinds: ['meditation_schedule'] })
    expect(meditation).toHaveLength(2)

    channel.close()
  })

  it('should compute statistics', () => {
    const channel = makeChannel()
    const h1 = channel.proposeAction({ kind: 'meditation_schedule', payload: {} })
    channel.refuse(h1, 'cassi', 'No')
    // Auto-approved
    channel.proposeAction({ kind: 'composition_activation', payload: {} })

    const stats = channel.getStatistics()
    expect(stats.total).toBe(2)
    expect(stats.byStatus.refused).toBe(1)
    expect(stats.byStatus.approved).toBe(1)

    channel.close()
  })

  it('should respect the enabled=false config by auto-approving everything', async () => {
    const channel = makeChannel({ enabled: false })
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
    })

    const resolution = await channel.await(handle)
    expect(resolution.kind).toBe('approved')

    channel.close()
  })

  it('should expire proposed actions after expirationSeconds', async () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
      expirationSeconds: 1, // 1 second for fast test
    })

    // Wait for expiration
    const resolution = await channel.await(handle)

    expect(resolution.kind).toBe('expired')
    const record = channel.get(handle)
    expect(record?.status).toBe('expired')

    channel.close()
  }, 10000)

  it('should resolve via await when action is approved during wait', async () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
      expirationSeconds: 10,
    })

    // Approve after a short delay
    setTimeout(() => channel.approve(handle, 'operator'), 100)

    const resolution = await channel.await(handle)
    expect(resolution.kind).toBe('approved')

    channel.close()
  })

  it('should throw when modifying a non-proposed action', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
    })

    channel.approve(handle, 'operator')

    expect(() => {
      channel.modify(handle, {
        kind: 'meditation_schedule',
        payload: { gapId: 'gap_1', priority: 'low' },
      }, 'operator', 'Changed mind')
    }).toThrow(/Cannot modify/)

    channel.close()
  })

  it('should apply custom consent matrix', () => {
    const customMatrix: Partial<Record<ActionKind, ConsentRule>> = {
      meditation_schedule: {
        requiredSources: ['auto-approved'],
        defaultExpirationSeconds: 30,
        cassiHasStanding: false,
      },
    }

    const channel = makeChannel({ consentMatrix: customMatrix })
    const handle = channel.proposeAction({
      kind: 'meditation_schedule',
      payload: { gapId: 'gap_1' },
    })

    // Should auto-approve since we overrode the matrix
    const record = channel.get(handle)
    expect(record?.status).toBe('approved')

    channel.close()
  })

  it('should persist metadata', () => {
    const channel = makeChannel()
    const handle = channel.proposeAction({
      kind: 'counterfactual_run',
      payload: { forkId: 'fork_1' },
      metadata: { source: 'B7', confidence: 0.9 },
    })

    const record = channel.get(handle)
    expect(record?.metadata).toEqual({ source: 'B7', confidence: 0.9 })

    channel.close()
  })

  it('should fall back to default consent rule for unknown action kinds', () => {
    const channel = makeChannel()
    // counterfactual_run is auto-approved in default matrix
    const handle = channel.proposeAction({
      kind: 'counterfactual_run',
      payload: { forkId: 'fork_1' },
    })

    const record = channel.get(handle)
    expect(record?.status).toBe('approved')

    channel.close()
  })
})
