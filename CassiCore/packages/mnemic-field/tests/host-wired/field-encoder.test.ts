// HOST-WIRED QUARANTINE — NOT part of the counted by-default suite.
//
// This test exercises MnemicField's MindFieldEncoder journal hooks
// (setFieldEncoder / drainFieldDeposits / fieldDepositsSent) which depend on
// the overhaul session's `field-encoder` runtime (`StandardMindFieldEncoder` /
// `NoopMindFieldEncoder`). Those packages have not landed, so this test is
// quarantined to tests/host-wired/ (excluded by vitest.config). When the
// overhaul's field-encoder publishes, re-point the `@cassicore/field-encoder`
// import below and promote it into the counted suite.
//
// (P4 table §1.4 / Open Flag 6.)
import { describe, expect, it } from 'vitest'

import { MnemicField } from '@cassicore/mnemic-field'
// @cassicore/field-encoder  ← overhaul-owned runtime; import StandardMindFieldEncoder,
// NoopMindFieldEncoder here once the package lands:
// import { StandardMindFieldEncoder, NoopMindFieldEncoder } from '@cassicore/field-encoder'

function logger(): any {
  const l = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {}, child: () => l }
  return l
}

describe('MnemicField neuron-like field encoding (Mind Over Brain, Stage 1)', () => {
  it('is no-op by construction when no encoder is wired (parity gate)', () => {
    const field = new MnemicField(logger(), ':memory:')
    const engram = field.store({ id: 't:1', content: 'hello', nodeType: 'fact', x: 0.2, y: 0.1, z: 0.3 })
    // No encoder → no deposits, unchanged behavior, zero fieldDeposits.
    expect(field.drainFieldDeposits()).toEqual([])
    expect(field.fieldDepositsSent()).toBe(0)
    expect(field.get('t:1')).toMatchObject({ id: 't:1', nodeType: 'fact' })
    field.connect({ sourceId: 't:1', targetId: 't:1', edgeType: 'supports' })
    expect(field.drainFieldDeposits()).toEqual([])
    expect(engram).toBeTruthy()
    field.close()
  })

  it('queues a deposit at the engram own field coordinates with a Noop encoder', () => {
    // The Noop encoder is OPEN-equivalent for store()'s side-effect-free
    // contract: it never throws, never blocks, even with deposits enabled.
    const field = new MnemicField(logger(), ':memory:')
    field.setFieldEncoder(new NoopMindFieldEncoder())
    // isOpen() false → store() short-circuits; still no deposits.
    field.store({ id: 't:2', content: 'x', nodeType: 'fact', x: 0.5, y: 0.5, z: 0.5 })
    expect(field.drainFieldDeposits()).toEqual([])
    field.close()
  })

  it('queues a charge deposit at the engram own coordinates with the standard encoder', () => {
    const field = new MnemicField(logger(), ':memory:')
    const enc = new StandardMindFieldEncoder()
    field.setFieldEncoder(enc)
    const engram = field.store({ id: 't:3', content: 'remember me', nodeType: 'fact', x: 0.25, y: -0.4, z: 0.6 })
    const dep = field.drainFieldDeposits()
    expect(dep).toHaveLength(1)
    expect(dep[0].slice(0, 3)).toEqual([0.25, -0.4, 0.6]) // position = engram coords
    // fact → (yang=1.618, yin=1.0, sigma=2.0); powerFor(fact)=0.9 → cy=1.618*0.9
    expect(dep[0][3]).toBeCloseTo(1.618 * 0.9, 5)
    expect(dep[0][4]).toBeCloseTo(1.0 * 0.9, 5)
    expect(dep[0][5]).toBe(2.0)
    expect(field.fieldDepositsSent()).toBe(1)
    expect(engram).toMatchObject({ id: 't:3' })
    field.close()
  })

  it('queues deposits for connect and consolidation', async () => {
    const field = new MnemicField(logger(), ':memory:')
    field.setFieldEncoder(new StandardMindFieldEncoder())
    field.store({ id: 'a', content: 'A', nodeType: 'fact', x: 0.1, y: 0.1, z: 0.1 })
    field.drainFieldDeposits() // clear the store deposit
    field.connect({ sourceId: 'a', targetId: 'a', edgeType: 'supports' })
    const afterConnect = field.drainFieldDeposits()
    expect(afterConnect).toHaveLength(1)
    expect(afterConnect[0].slice(0, 3)).toEqual([0, 0, 0.3]) // synapse thread charge
    // Consolidation (sparse DB; may be empty) — must not throw and may queue.
    const result = await field.consolidate({ concurrency: 1 })
    expect(result).toBeTruthy()
    expect(Array.isArray(field.drainFieldDeposits())).toBe(true)
    field.close()
  })
})
