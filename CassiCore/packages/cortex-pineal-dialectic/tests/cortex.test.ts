import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { CorticalField, CortexSession, Commissure, signalToEngram, createConsolidationBridge } from '../src/cortex/index.js'
import { Region } from '../src/cortex/region.js'
import { TractEngine } from '../src/cortex/tract.js'
import { oscillate } from '../src/cortex/dynamics.js'
import {
  createSignal, computeActivation, attendSignal,
  transitionState, meetsConsolidationCriteria, deriveSignal,
} from '../src/cortex/signal.js'
import { ACTIVATION_DEFAULTS, CONSOLIDATION_DEFAULTS, SYSTEM_REGIONS } from '../src/cortex/types.js'
import type { CorticalSignal, SignalInput } from '../src/cortex/types.js'
import { AffectRegister } from '@cassicore/mnemic-field'
import { mockLogger } from './helpers.ts'

function input(overrides?: Partial<SignalInput>): SignalInput {
  return {
    type: 'perception',
    content: 'test signal',
    author: 'test',
    ...overrides,
  }
}

describe('Signal Lifecycle', () => {
  it('creates a signal with defaults', () => {
    const sig = createSignal('sensory', input(), 0.1)
    expect(sig.id).toBeTruthy()
    expect(sig.region).toBe('sensory')
    expect(sig.type).toBe('perception')
    expect(sig.activation).toBe(ACTIVATION_DEFAULTS.defaultSalience)
    expect(sig.salience).toBe(ACTIVATION_DEFAULTS.defaultSalience)
    expect(sig.state).toBe('active')
    expect(sig.bindings).toEqual([])
    expect(sig.sourceSignals).toEqual([])
  })

  it('creates a signal with explicit salience', () => {
    const sig = createSignal('limbic', input({ salience: 0.9 }), 0.1)
    expect(sig.salience).toBe(0.9)
    expect(sig.activation).toBe(0.9)
  })

  it('computes exponential activation decay', () => {
    const sig = createSignal('sensory', input({ salience: 1.0 }), 0.1)
    const baseTime = sig.lastAttended

    const a1 = computeActivation(sig, baseTime + 60_000)
    expect(a1).toBeCloseTo(Math.exp(-0.1), 5)

    const a5 = computeActivation(sig, baseTime + 300_000)
    expect(a5).toBeCloseTo(Math.exp(-0.5), 5)
  })

  it('returns current activation when no time has passed', () => {
    const sig = createSignal('sensory', input({ salience: 0.8 }), 0.1)
    expect(computeActivation(sig, sig.lastAttended)).toBe(0.8)
  })

  it('boosts activation on attention', () => {
    const sig = createSignal('sensory', input({ salience: 0.4 }), 0.1)
    attendSignal(sig)
    expect(sig.activation).toBeCloseTo(0.4 + ACTIVATION_DEFAULTS.attentionBoost, 5)
  })

  it('caps activation at 1.0 on attention', () => {
    const sig = createSignal('sensory', input({ salience: 0.95 }), 0.1)
    attendSignal(sig)
    expect(sig.activation).toBe(1.0)
  })

  it('transitions active → fading → decayed', () => {
    const sig = createSignal('sensory', input({ salience: 0.5, decayRate: 1.0 }), 1.0)
    const base = sig.lastAttended

    transitionState(sig, base + 60_000)
    expect(sig.state).toBe('fading')

    transitionState(sig, base + 300_000)
    expect(sig.state).toBe('decayed')
  })

  it('does not re-transition consolidated signals', () => {
    const sig = createSignal('sensory', input(), 0.1)
    sig.state = 'consolidated'
    transitionState(sig, Date.now() + 999_999_999)
    expect(sig.state).toBe('consolidated')
  })
})

describe('Consolidation Criteria', () => {
  it('consolidates high-salience signals', () => {
    const sig = createSignal('sensory', input({ salience: 0.6 }), 0.1)
    expect(meetsConsolidationCriteria(sig)).toBe(true)
  })

  it('consolidates signals with many source references', () => {
    const sig = createSignal('sensory', input({ salience: 0.2 }), 0.1)
    sig.sourceSignals = ['a', 'b', 'c']
    expect(meetsConsolidationCriteria(sig)).toBe(true)
  })

  it('consolidates signals with bindings', () => {
    const sig = createSignal('sensory', input({ salience: 0.2 }), 0.1)
    sig.bindings = ['x', 'y']
    expect(meetsConsolidationCriteria(sig)).toBe(true)
  })

  it('does not consolidate low-importance signals', () => {
    const sig = createSignal('sensory', input({ salience: 0.2 }), 0.1)
    expect(meetsConsolidationCriteria(sig)).toBe(false)
  })
})

describe('Region', () => {
  let region: Region

  beforeEach(() => {
    region = new Region('sensory', SYSTEM_REGIONS.sensory)
  })

  it('posts and retrieves signals', () => {
    const sig = region.post(input())
    expect(region.size()).toBe(1)
    expect(region.get(sig.id)).toBe(sig)
  })

  it('reads active signals sorted by activation', () => {
    region.post(input({ salience: 0.35, content: 'low' }))
    region.post(input({ salience: 0.9, content: 'high' }))
    region.post(input({ salience: 0.6, content: 'mid' }))

    const active = region.readActive()
    expect(active.length).toBe(3)
    expect(active[0].content).toBe('high')
    expect(active[1].content).toBe('mid')
    expect(active[2].content).toBe('low')
  })

  it('filters out low-activation signals from readActive', () => {
    const sig = region.post(input({ salience: 0.5, decayRate: 2.0 }))
    const future = Date.now() + 300_000
    const active = region.readActive(future)
    expect(active.length).toBe(0)
  })

  it('attends to a signal and boosts activation', () => {
    const sig = region.post(input({ salience: 0.4 }))
    const attended = region.attend(sig.id)
    expect(attended).toBeDefined()
    expect(attended!.activation).toBeGreaterThan(0.4)
  })

  it('removes a signal', () => {
    const sig = region.post(input())
    expect(region.remove(sig.id)).toBe(true)
    expect(region.size()).toBe(0)
  })

  it('enforces capacity by evicting lowest activation', () => {
    const smallRegion = new Region('test', { capacity: 3, defaultDecayRate: 0.1 })
    smallRegion.post(input({ salience: 0.9, content: 'keep1' }))
    smallRegion.post(input({ salience: 0.8, content: 'keep2' }))
    smallRegion.post(input({ salience: 0.7, content: 'keep3' }))

    const evicted = smallRegion.post(input({ salience: 0.3, content: 'newcomer' }))
    expect(smallRegion.size()).toBe(3)

    const all = smallRegion.readAll()
    const contents = all.map(s => s.content)
    expect(contents).toContain('keep1')
    expect(contents).toContain('keep2')
  })

  it('snapshots and restores', () => {
    region.post(input({ content: 'a' }))
    region.post(input({ content: 'b' }))
    const snap = region.snapshot()
    expect(snap.length).toBe(2)

    region.clear()
    expect(region.size()).toBe(0)

    region.restore(snap)
    expect(region.size()).toBe(2)
  })
})

describe('TractEngine', () => {
  let engine: TractEngine
  let regions: Map<string, Region>

  beforeEach(() => {
    engine = new TractEngine()
    regions = new Map()
    regions.set('sensory', new Region('sensory', SYSTEM_REGIONS.sensory))
    regions.set('association', new Region('association', SYSTEM_REGIONS.association))
    regions.set('limbic', new Region('limbic', SYSTEM_REGIONS.limbic))
  })

  it('connects and lists tracts', () => {
    engine.connect('sensory', 'association', { strength: 0.8 })
    expect(engine.list().length).toBe(1)
    expect(engine.list()[0].from).toBe('sensory')
    expect(engine.list()[0].to).toBe('association')
  })

  it('disconnects a tract', () => {
    const tract = engine.connect('sensory', 'association')
    expect(engine.disconnect(tract.id)).toBe(true)
    expect(engine.list().length).toBe(0)
  })

  it('propagates signals through tracts', () => {
    engine.connect('sensory', 'association', { strength: 0.8 })

    const sig = createSignal('sensory', input({ salience: 0.6 }), 0.3)
    regions.get('sensory')!.insert(sig)

    const derived = engine.propagate(sig, regions)
    expect(derived.length).toBe(1)
    expect(derived[0].region).toBe('association')
    expect(derived[0].sourceSignals).toContain(sig.id)
    expect(derived[0].activation).toBeCloseTo(0.6 * 0.8, 5)
  })

  it('filters by signal type', () => {
    engine.connect('sensory', 'association', {
      filter: { types: ['anomaly'] },
    })

    const perception = createSignal('sensory', input({ type: 'perception' }), 0.1)
    regions.get('sensory')!.insert(perception)
    expect(engine.propagate(perception, regions).length).toBe(0)

    const anomaly = createSignal('sensory', input({ type: 'anomaly' }), 0.1)
    regions.get('sensory')!.insert(anomaly)
    expect(engine.propagate(anomaly, regions).length).toBe(1)
  })

  it('filters by minimum salience', () => {
    engine.connect('sensory', 'association', {
      filter: { minSalience: 0.5 },
    })

    const low = createSignal('sensory', input({ salience: 0.3 }), 0.1)
    regions.get('sensory')!.insert(low)
    expect(engine.propagate(low, regions).length).toBe(0)

    const high = createSignal('sensory', input({ salience: 0.7 }), 0.1)
    regions.get('sensory')!.insert(high)
    expect(engine.propagate(high, regions).length).toBe(1)
  })

  it('respects refractory period', () => {
    const tract = engine.connect('sensory', 'association', {
      refractory: 5000,
    })

    const sig1 = createSignal('sensory', input(), 0.1)
    regions.get('sensory')!.insert(sig1)
    const now = Date.now()

    expect(engine.propagate(sig1, regions, now).length).toBe(1)

    const sig2 = createSignal('sensory', input(), 0.1)
    regions.get('sensory')!.insert(sig2)
    expect(engine.propagate(sig2, regions, now + 1000).length).toBe(0)
    expect(engine.propagate(sig2, regions, now + 6000).length).toBe(1)
  })

  it('transforms type during propagation', () => {
    engine.connect('association', 'limbic', {
      transform: { typeOverride: 'concern' },
    })

    const sig = createSignal('association', input({ type: 'association' }), 0.1)
    regions.get('association')!.insert(sig)

    const derived = engine.propagate(sig, regions)
    expect(derived[0].type).toBe('concern')
  })

  it('adds tags during propagation', () => {
    engine.connect('sensory', 'association', {
      transform: { addTags: ['propagated', 'auto'] },
    })

    const sig = createSignal('sensory', input({ tags: ['original'] }), 0.1)
    regions.get('sensory')!.insert(sig)

    const derived = engine.propagate(sig, regions)
    expect(derived[0].tags).toContain('original')
    expect(derived[0].tags).toContain('propagated')
    expect(derived[0].tags).toContain('auto')
  })
})

describe('Oscillation Dynamics', () => {
  let regions: Map<string, Region>

  beforeEach(() => {
    regions = new Map()
    regions.set('sensory', new Region('sensory', { capacity: 100, defaultDecayRate: 0.3 }))
    regions.set('association', new Region('association', { capacity: 50, defaultDecayRate: 0.1 }))
  })

  it('prunes decayed signals', () => {
    const region = regions.get('sensory')!
    const sig = region.post(input({ salience: 0.5, decayRate: 5.0 }))

    sig.lastAttended = Date.now() - 600_000

    const result = oscillate(regions)
    expect(result.decayed).toBeGreaterThanOrEqual(1)
    expect(result.pruned).toBeGreaterThanOrEqual(1)
    expect(region.size()).toBe(0)
  })

  it('consolidates important fading signals', () => {
    const region = regions.get('sensory')!
    const sig = region.post(input({ salience: 0.7, decayRate: 0.5 }))
    sig.lastAttended = Date.now() - 120_000

    const consolidated: CorticalSignal[] = []
    const result = oscillate(regions, (s) => consolidated.push(s))
    expect(result.consolidated).toBe(1)
    expect(consolidated[0].id).toBe(sig.id)
    expect(sig.state).toBe('consolidated')
  })

  it('does not consolidate unimportant fading signals', () => {
    const region = regions.get('sensory')!
    const sig = region.post(input({ salience: 0.2, decayRate: 0.5 }))
    sig.lastAttended = Date.now() - 120_000

    const result = oscillate(regions)
    expect(result.consolidated).toBe(0)
  })

  it('binds signals with shared tags', () => {
    const r1 = regions.get('sensory')!
    const r2 = regions.get('association')!

    const s1 = r1.post(input({ tags: ['auth'], salience: 0.8 }))
    const s2 = r2.post(input({ tags: ['auth'], salience: 0.8 }))

    const result = oscillate(regions)
    expect(result.bound).toBeGreaterThanOrEqual(1)
    expect(s1.bindings).toContain(s2.id)
    expect(s2.bindings).toContain(s1.id)
  })

  it('binds signals with shared sessions', () => {
    const r1 = regions.get('sensory')!
    const r2 = regions.get('association')!

    const s1 = r1.post(input({ sessionId: 'sess-1', salience: 0.8 }))
    const s2 = r2.post(input({ sessionId: 'sess-1', salience: 0.8 }))

    const result = oscillate(regions)
    expect(result.bound).toBeGreaterThanOrEqual(1)
    expect(s1.bindings).toContain(s2.id)
  })

  it('does not duplicate existing bindings', () => {
    const r1 = regions.get('sensory')!
    const r2 = regions.get('association')!

    const s1 = r1.post(input({ tags: ['x'], salience: 0.8 }))
    const s2 = r2.post(input({ tags: ['x'], salience: 0.8 }))

    oscillate(regions)
    const bindCountBefore = s1.bindings.length

    oscillate(regions)
    expect(s1.bindings.length).toBe(bindCountBefore)
  })
})

describe('CorticalField', () => {
  let field: CorticalField

  beforeEach(() => {
    field = new CorticalField(mockLogger())
  })

  afterEach(() => {
    field.close()
  })

  it('initializes with 6 system regions', () => {
    const regions = field.listRegions()
    expect(regions.length).toBe(6)
    const names = regions.map(r => r.name).sort()
    expect(names).toEqual(['association', 'executive', 'limbic', 'monitor', 'motor', 'sensory'])
    expect(regions.every(r => r.isSystem)).toBe(true)
  })

  it('initializes with system tracts', () => {
    const tracts = field.listTracts()
    expect(tracts.length).toBe(7)
  })

  it('posts a signal to a region', () => {
    const sig = field.signal('sensory', input({ content: 'user typed hello' }))
    expect(sig.region).toBe('sensory')
    expect(sig.content).toBe('user typed hello')
    expect(sig.state).toBe('active')
  })

  it('throws on unknown region', () => {
    expect(() => field.signal('nonexistent', input())).toThrow('Unknown region')
  })

  it('reads active signals across regions', () => {
    field.signal('sensory', input({ content: 'a', salience: 0.8 }))
    field.signal('association', input({ content: 'b', salience: 0.7 }))
    field.signal('executive', input({ content: 'c', salience: 0.9 }))

    const active = field.readActive()
    expect(active.length).toBeGreaterThanOrEqual(3)
    expect(active[0].salience).toBeGreaterThanOrEqual(active[1].salience)
  })

  it('filters readActive by region', () => {
    field.signal('sensory', input({ content: 'a' }))
    field.signal('association', input({ content: 'b' }))

    const sensoryOnly = field.readActive({ regions: ['sensory'] })
    expect(sensoryOnly.every(s => s.region === 'sensory')).toBe(true)
  })

  it('filters readActive by type', () => {
    field.signal('sensory', input({ type: 'perception' }))
    field.signal('sensory', input({ type: 'anomaly' }))

    const anomalies = field.readActive({ types: ['anomaly'] })
    expect(anomalies.every(s => s.type === 'anomaly')).toBe(true)
  })

  it('filters readActive by sessionId', () => {
    field.signal('sensory', input({ sessionId: 'A' }))
    field.signal('sensory', input({ sessionId: 'B' }))

    const sessionA = field.readActive({ sessionId: 'A' })
    expect(sessionA.every(s => s.sessionId === 'A')).toBe(true)
  })

  it('attends to a signal across regions', () => {
    const sig = field.signal('sensory', input({ salience: 0.4 }))
    const attended = field.attend(sig.id)
    expect(attended).toBeDefined()
    expect(attended!.activation).toBeGreaterThan(0.4)
  })

  it('propagates signals through system tracts', () => {
    const sig = field.signal('sensory', input({ salience: 0.5 }))

    const assocSignals = field.getRegion('association')!.readAll()
    expect(assocSignals.length).toBeGreaterThanOrEqual(1)
    expect(assocSignals[0].sourceSignals).toContain(sig.id)
  })

  it('creates and deletes custom regions', () => {
    const region = field.createRegion('project:auth', { capacity: 25 })
    expect(region.config.capacity).toBe(25)
    expect(field.getRegion('project:auth')).toBe(region)

    expect(field.deleteRegion('project:auth')).toBe(true)
    expect(field.getRegion('project:auth')).toBeUndefined()
  })

  it('prevents deletion of system regions', () => {
    expect(() => field.deleteRegion('sensory')).toThrow('Cannot delete system region')
  })

  it('prevents duplicate region creation', () => {
    expect(() => field.createRegion('sensory')).toThrow('Region already exists')
  })

  it('connects and disconnects custom tracts', () => {
    const tract = field.connect('monitor', 'executive', { strength: 0.5 })
    expect(field.listTracts().length).toBe(8)

    field.disconnect(tract.id)
    expect(field.listTracts().length).toBe(7)
  })

  it('throws on connecting unknown regions', () => {
    expect(() => field.connect('nonexistent', 'sensory')).toThrow('Unknown source region')
    expect(() => field.connect('sensory', 'nonexistent')).toThrow('Unknown target region')
  })

  it('runs oscillation tick', () => {
    field.signal('sensory', input({ salience: 0.8 }))
    const result = field.tick()
    expect(result).toHaveProperty('decayed')
    expect(result).toHaveProperty('pruned')
    expect(result).toHaveProperty('consolidated')
    expect(result).toHaveProperty('bound')
    expect(result).toHaveProperty('durationMs')
  })

  it('snapshots and restores', () => {
    field.signal('sensory', input({ content: 'persistent' }))
    field.signal('association', input({ content: 'also persistent' }))

    const snap = field.snapshot()
    field.close()

    const restored = new CorticalField(mockLogger())
    restored.restore(snap)

    const active = restored.readActive({ regions: ['sensory'] })
    expect(active.some(s => s.content === 'persistent')).toBe(true)

    restored.close()
  })
})

describe('Affect Integration', () => {
  let field: CorticalField
  let register: AffectRegister

  beforeEach(() => {
    register = new AffectRegister()
    field = new CorticalField(mockLogger())
    field.setAffectRegister(register)
  })

  afterEach(() => {
    field.close()
  })

  it('feeds limbic signals to affect register', () => {
    const before = register.getState()

    field.signal('limbic', input({
      type: 'concern',
      content: 'security vulnerability detected',
      salience: 0.8,
      valence: -0.6,
    }))

    const after = register.getState()
    expect(after.valence).toBeLessThan(before.valence)
    expect(after.arousal).toBeGreaterThan(before.arousal)
  })

  it('does not feed non-limbic signals to affect register', () => {
    const before = register.getState()

    field.signal('sensory', input({
      salience: 0.9,
      valence: -0.9,
    }))

    const after = register.getState()
    expect(after.valence).toBeCloseTo(before.valence, 1)
  })

  it('positive limbic signals shift valence up', () => {
    const before = register.getState()

    field.signal('limbic', input({
      type: 'insight',
      content: 'all tests passing',
      salience: 0.7,
      valence: 0.8,
    }))

    const after = register.getState()
    expect(after.valence).toBeGreaterThan(before.valence)
  })
})

describe('End-to-End: Cognitive Cycle', () => {
  let field: CorticalField

  beforeEach(() => {
    field = new CorticalField(mockLogger())
  })

  afterEach(() => {
    field.close()
  })

  it('signal flows from sensory through association to executive', () => {
    const sensoryInput = field.signal('sensory', input({
      type: 'perception',
      content: 'user requested auth refactor',
      salience: 0.7,
      tags: ['auth'],
    }))

    const assocSignals = field.getRegion('association')!.readAll()
    expect(assocSignals.length).toBeGreaterThanOrEqual(1)

    const propagated = assocSignals.find(s => s.sourceSignals.includes(sensoryInput.id))
    expect(propagated).toBeDefined()

    if (propagated && propagated.salience >= 0.5) {
      const execSignals = field.getRegion('executive')!.readAll()
      expect(execSignals.length).toBeGreaterThanOrEqual(1)
    }
  })

  it('high-salience concern flows from association to limbic', () => {
    field.signal('association', input({
      type: 'concern',
      content: 'potential SQL injection in query builder',
      salience: 0.8,
    }))

    const limbicSignals = field.getRegion('limbic')!.readAll()
    expect(limbicSignals.length).toBeGreaterThanOrEqual(1)
    expect(limbicSignals[0].type).toBe('concern')
  })

  it('anomaly in monitor escalates to limbic', () => {
    field.signal('monitor', input({
      type: 'anomaly',
      content: 'memory usage spike detected',
      salience: 0.6,
    }))

    const limbicSignals = field.getRegion('limbic')!.readAll()
    expect(limbicSignals.length).toBeGreaterThanOrEqual(1)
  })

  it('decision in executive propagates to motor', () => {
    field.signal('executive', input({
      type: 'decision',
      content: 'apply migration strategy B',
      salience: 0.8,
    }))

    const motorSignals = field.getRegion('motor')!.readAll()
    expect(motorSignals.length).toBeGreaterThanOrEqual(1)
  })

  it('consolidation callback fires for important fading signals', () => {
    const consolidated: CorticalSignal[] = []
    const fieldWithCallback = new CorticalField(mockLogger(), {
      onConsolidate: (s) => consolidated.push(s),
    })

    const sig = fieldWithCallback.signal('executive', input({
      salience: 0.7,
      decayRate: 0.5,
      content: 'important decision to remember',
    }))
    sig.lastAttended = Date.now() - 120_000

    fieldWithCallback.tick()
    expect(consolidated.length).toBe(1)
    expect(consolidated[0].content).toBe('important decision to remember')

    fieldWithCallback.close()
  })
})

describe('CortexSession', () => {
  let field: CorticalField
  let session: CortexSession

  beforeEach(() => {
    field = new CorticalField(mockLogger())
    session = field.createSession('sess-1')
  })

  afterEach(() => {
    field.close()
  })

  it('creates a session with sessionId', () => {
    expect(session.sessionId).toBe('sess-1')
    expect(field.getSession('sess-1')).toBe(session)
  })

  it('returns existing session on duplicate create', () => {
    const same = field.createSession('sess-1')
    expect(same).toBe(session)
  })

  it('posts signals with auto-tagged sessionId', () => {
    const sig = session.signal('sensory', input({ content: 'session observation' }))
    expect(sig.sessionId).toBe('sess-1')
    expect(sig.region).toBe('sensory')
  })

  it('reads only session-scoped signals', () => {
    session.signal('sensory', input({ content: 'mine', salience: 0.8 }))
    field.signal('sensory', input({ content: 'global', salience: 0.8, sessionId: 'other' }))

    const results = session.read('sensory')
    expect(results.every(s => s.sessionId === 'sess-1')).toBe(true)
    expect(results.some(s => s.content === 'mine')).toBe(true)
  })

  it('focuses a signal into working memory', () => {
    const sig = session.signal('executive', input({ content: 'important goal', salience: 0.8 }))
    expect(session.focus(sig.id)).toBe(true)
    expect(session.isInWorkingMemory(sig.id)).toBe(true)
    expect(session.getWorkingMemorySize()).toBe(1)
  })

  it('rejects focusing signals from other sessions', () => {
    const otherSig = field.signal('sensory', input({ sessionId: 'other-sess' }))
    expect(session.focus(otherSig.id)).toBe(false)
  })

  it('defocuses a signal from working memory', () => {
    const sig = session.signal('executive', input({ salience: 0.8 }))
    session.focus(sig.id)
    expect(session.defocus(sig.id)).toBe(true)
    expect(session.isInWorkingMemory(sig.id)).toBe(false)
  })

  it('enforces working memory capacity', () => {
    const small = field.createSession('small-wm', { workingMemoryCapacity: 3 })
    const ids: string[] = []

    for (let i = 0; i < 5; i++) {
      const sig = small.signal('executive', input({ salience: 0.5 + i * 0.1, content: `item-${i}` }))
      small.focus(sig.id)
      ids.push(sig.id)
    }

    expect(small.getWorkingMemorySize()).toBe(3)
    const wm = small.getWorkingMemory()
    expect(wm.length).toBe(3)
  })

  it('returns working memory sorted by activation', () => {
    const low = session.signal('executive', input({ salience: 0.4, content: 'low' }))
    const high = session.signal('executive', input({ salience: 0.9, content: 'high' }))
    const mid = session.signal('executive', input({ salience: 0.6, content: 'mid' }))

    session.focus(low.id)
    session.focus(high.id)
    session.focus(mid.id)

    const wm = session.getWorkingMemory()
    expect(wm[0].content).toBe('high')
    expect(wm[1].content).toBe('mid')
    expect(wm[2].content).toBe('low')
  })

  it('cleans up decayed signals from working memory', () => {
    const sig = session.signal('executive', input({ salience: 0.5, decayRate: 5.0 }))
    session.focus(sig.id)
    sig.lastAttended = Date.now() - 600_000
    sig.state = 'decayed'

    const wm = session.getWorkingMemory()
    expect(wm.length).toBe(0)
    expect(session.getWorkingMemorySize()).toBe(0)
  })

  it('snapshots and restores working memory', () => {
    const sig1 = session.signal('executive', input({ salience: 0.8 }))
    const sig2 = session.signal('association', input({ salience: 0.7 }))
    session.focus(sig1.id)
    session.focus(sig2.id)

    const snap = session.snapshot()
    expect(snap.workingMemory.length).toBe(2)
    expect(snap.sessionId).toBe('sess-1')

    session.close()
    expect(session.getWorkingMemorySize()).toBe(0)

    session.restore(snap)
    expect(session.getWorkingMemorySize()).toBe(2)
  })

  it('ends session and returns snapshot', () => {
    session.signal('sensory', input({ salience: 0.8 }))
    const snap = field.endSession('sess-1')
    expect(snap).toBeDefined()
    expect(snap!.sessionId).toBe('sess-1')
    expect(field.getSession('sess-1')).toBeUndefined()
  })

  it('lists active sessions', () => {
    field.createSession('sess-2')
    const list = field.listSessions()
    expect(list.length).toBe(2)
    expect(list.map(s => s.sessionId).sort()).toEqual(['sess-1', 'sess-2'])
  })
})

describe('Commissure', () => {
  let parentField: CorticalField
  let childSession: CortexSession
  let commissure: Commissure

  beforeEach(() => {
    parentField = new CorticalField(mockLogger())
    childSession = parentField.createSession('child-1')
    commissure = new Commissure(parentField, childSession)
  })

  afterEach(() => {
    parentField.close()
  })

  it('propagates high-salience child association signals to parent', () => {
    childSession.signal('association', input({
      type: 'association',
      content: 'discovered pattern in auth module',
      salience: 0.7,
    }))

    const result = commissure.propagateAscending()
    expect(result.length).toBeGreaterThanOrEqual(1)
    expect(result[0].content).toBe('discovered pattern in auth module')
    expect(result[0].tags).toContain(`from:${childSession.sessionId.slice(-8)}`)
  })

  it('does not propagate low-salience child signals', () => {
    childSession.signal('association', input({
      type: 'association',
      content: 'minor observation',
      salience: 0.2,
    }))

    const result = commissure.propagateAscending()
    expect(result.length).toBe(0)
  })

  it('propagates child limbic concerns to parent', () => {
    childSession.signal('limbic', input({
      type: 'concern',
      content: 'security vulnerability found',
      salience: 0.8,
      valence: -0.5,
    }))

    const result = commissure.propagateAscending()
    expect(result.some(s => s.content === 'security vulnerability found')).toBe(true)
  })

  it('deduplicates — same signal not propagated twice', () => {
    childSession.signal('association', input({
      type: 'association',
      content: 'unique finding',
      salience: 0.7,
    }))

    const first = commissure.propagateAscending()
    expect(first.length).toBeGreaterThanOrEqual(1)

    commissure['lastAscending'] = 0
    const second = commissure.propagateAscending()
    expect(second.length).toBe(0)
  })

  it('propagates parent decisions down to child', () => {
    parentField.signal('executive', input({
      type: 'decision',
      content: 'use strategy B for migration',
      salience: 0.8,
      sessionId: 'corpus',
    }))

    const result = commissure.propagateDescending()
    expect(result.length).toBeGreaterThanOrEqual(1)
    expect(result[0].content).toBe('use strategy B for migration')
    expect(result[0].tags).toContain('guidance')
  })

  it('does not propagate child own signals back down', () => {
    childSession.signal('executive', input({
      type: 'decision',
      content: 'local decision',
      salience: 0.8,
    }))

    const result = commissure.propagateDescending()
    const loopback = result.filter(s => s.content === 'local decision')
    expect(loopback.length).toBe(0)
  })

  it('propagate() runs both directions', () => {
    childSession.signal('association', input({
      type: 'association',
      content: 'child finding',
      salience: 0.7,
    }))
    parentField.signal('executive', input({
      type: 'decision',
      content: 'parent directive',
      salience: 0.8,
      sessionId: 'corpus',
    }))

    const result = commissure.propagate()
    expect(result.ascending.length).toBeGreaterThanOrEqual(1)
    expect(result.descending.length).toBeGreaterThanOrEqual(1)
  })

  it('clearDedup resets deduplication state', () => {
    childSession.signal('association', input({
      type: 'association',
      content: 'finding',
      salience: 0.7,
    }))

    commissure.propagateAscending()
    expect(commissure.dedupSize).toBeGreaterThan(0)

    commissure.clearDedup()
    expect(commissure.dedupSize).toBe(0)
  })
})

describe('Consolidation Bridge', () => {
  it('maps signal types to engram types', () => {
    const perception = createSignal('sensory', input({ type: 'perception' }), 0.1)
    expect(signalToEngram(perception).nodeType).toBe('episode')

    const assoc = createSignal('association', input({ type: 'association' }), 0.1)
    expect(signalToEngram(assoc).nodeType).toBe('pattern')

    const decision = createSignal('executive', input({ type: 'decision' }), 0.1)
    expect(signalToEngram(decision).nodeType).toBe('decision')

    const insight = createSignal('monitor', input({ type: 'insight' }), 0.1)
    expect(signalToEngram(insight).nodeType).toBe('abstraction')
  })

  it('preserves content and tags', () => {
    const sig = createSignal('association', input({
      type: 'association',
      content: 'auth pattern detected',
      tags: ['auth', 'security'],
    }), 0.1)

    const engram = signalToEngram(sig)
    expect(engram.content).toBe('auth pattern detected')
    expect(engram.tags).toContain('auth')
    expect(engram.tags).toContain('security')
    expect(engram.tags).toContain('cortex:association')
    expect(engram.tags).toContain('signal:association')
  })

  it('includes cortex metadata', () => {
    const sig = createSignal('limbic', input({
      type: 'concern',
      salience: 0.8,
      valence: -0.4,
      confidence: 0.9,
      sessionId: 'sess-x',
    }), 0.1)

    const engram = signalToEngram(sig)
    expect(engram.metadata).toMatchObject({
      cortexSignalId: sig.id,
      region: 'limbic',
      signalType: 'concern',
      salience: 0.8,
      valence: -0.4,
      confidence: 0.9,
      sessionId: 'sess-x',
    })
  })

  it('sets provenance from author', () => {
    const sig = createSignal('sensory', input({ author: 'dialectic' }), 0.1)
    expect(signalToEngram(sig).provenance).toBe('cortex/dialectic')
  })

  it('createConsolidationBridge calls store on consolidation', () => {
    const stored: any[] = []
    const mockTarget = {
      store(input: any) {
        stored.push(input)
        return { id: 'engram-1' }
      },
    }

    const field = new CorticalField(mockLogger(), {
      onConsolidate: createConsolidationBridge(mockTarget),
    })

    const sig = field.signal('executive', input({
      type: 'decision',
      content: 'migrate to strategy B',
      salience: 0.7,
      decayRate: 0.5,
    }))

    sig.lastAttended = Date.now() - 120_000
    field.tick()

    expect(stored.length).toBe(1)
    expect(stored[0].content).toBe('migrate to strategy B')
    expect(stored[0].nodeType).toBe('decision')
    expect(stored[0].provenance).toBe('cortex/test')

    field.close()
  })

  it('bridge handles store errors gracefully', () => {
    const mockTarget = {
      store() { throw new Error('DB full') },
    }

    const field = new CorticalField(mockLogger(), {
      onConsolidate: createConsolidationBridge(mockTarget),
    })

    const sig = field.signal('sensory', input({ salience: 0.7, decayRate: 0.5 }))
    sig.lastAttended = Date.now() - 120_000

    expect(() => field.tick()).not.toThrow()
    field.close()
  })

  it('setConsolidationCallback allows late wiring', () => {
    const stored: any[] = []
    const mockTarget = {
      store(input: any) { stored.push(input); return { id: 'e-1' } },
    }

    const field = new CorticalField(mockLogger())
    field.setConsolidationCallback(createConsolidationBridge(mockTarget))

    const sig = field.signal('monitor', input({
      type: 'insight',
      content: 'system is healthy',
      salience: 0.6,
      decayRate: 0.5,
    }))
    sig.lastAttended = Date.now() - 120_000

    field.tick()
    expect(stored.length).toBe(1)
    expect(stored[0].nodeType).toBe('abstraction')

    field.close()
  })
})

describe('Emotional Meditation (Wave 5)', () => {
  // Test selectStyle with affect integration
  let selectStyleFn: typeof import('@cassicore/constellation').selectStyle
  let styleConfigs: typeof import('@cassicore/constellation').STYLE_CONFIGS

  beforeEach(async () => {
    const styles = await import('@cassicore/constellation')
    selectStyleFn = styles.selectStyle
    styleConfigs = styles.STYLE_CONFIGS
  })

  it('defines a self-modeling meditation style', () => {
    expect(styleConfigs['self-modeling']).toBeDefined()
    expect(styleConfigs['self-modeling'].description).toContain('self-model')
  })

  it('selects reflective style when affect is emotionally charged', () => {
    const charged = { valence: -0.6, arousal: 0.5 }
    const style = selectStyleFn(Date.now() - 300_000, 600_000, 'passive', charged)
    expect(style).toBe('reflective')
  })

  it('selects reflective for high positive valence too', () => {
    const elated = { valence: 0.7, arousal: 0.3 }
    const style = selectStyleFn(Date.now() - 300_000, 600_000, 'passive', elated)
    expect(style).toBe('reflective')
  })

  it('does not select reflective for neutral affect', () => {
    const neutral = { valence: 0.05, arousal: 0.1 }
    const style = selectStyleFn(Date.now() - 300_000, 600_000, 'passive', neutral)
    expect(style).not.toBe('reflective')
  })

  it('falls through to idle-based selection when no affect', () => {
    const style = selectStyleFn(Date.now() - 100_000, 600_000, 'passive')
    expect(style).toBe('active')
  })

  it('falls through to idle-based selection with null affect', () => {
    const style = selectStyleFn(Date.now() - 3_000_000, 600_000, 'passive', null)
    expect(style).toBe('passive')
  })

  it('CorticalField exposes affect state via getAffectState', () => {
    const field = new CorticalField(mockLogger())
    expect(field.getAffectState()).toBeUndefined()

    const register = new AffectRegister()
    field.setAffectRegister(register)

    for (let i = 0; i < 5; i++) register.absorbSignal({ valence: -0.8, arousal: 0.7 })
    const state = field.getAffectState()
    expect(state).toBeDefined()
    expect(state!.valence).toBeLessThan(0)
    expect(state!.arousal).toBeGreaterThan(0)

    field.close()
  })
})
