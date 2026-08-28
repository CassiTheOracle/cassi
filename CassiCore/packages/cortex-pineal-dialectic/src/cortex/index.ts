import type { ILogger } from '@cassicore/foundation'
import type {
  CorticalSignal, SignalInput, SignalType, SignalState,
  RegionConfig, RegionInfo, RegionSnapshot,
  Tract, TractConfig,
  CorticalFieldConfig, CorticalFieldSnapshot,
  OscillationResult, ConsolidationCallback,
  CortexSessionConfig, CortexSessionSnapshot,
} from './types.js'
import {
  SYSTEM_REGIONS, SYSTEM_REGION_NAMES, SYSTEM_TRACTS,
  ACTIVATION_DEFAULTS,
} from './types.js'
import { Region } from './region.js'
import { TractEngine } from './tract.js'
import { oscillate } from './dynamics.js'
import { computeActivation } from './signal.js'
import { CortexSession } from './session.js'
import type { AffectRegister } from '@cassicore/mnemic-field'
import { SIGNAL_TYPE_PHRASES } from '@cassicore/foundation'
import type { MnemicField } from '@cassicore/mnemic-field'

const MAX_OSCILLATION_HISTORY = 100

export interface OscillationHistoryEntry extends OscillationResult {
  timestamp: number
}

export interface CortexStats {
  regions: {
    count: number
    totalSignals: number
    totalActive: number
    totalFading: number
    totalConsolidated: number
    capacityUtilization: number
    perRegion: Array<{
      name: string
      signals: number
      active: number
      fading: number
      consolidated: number
      capacity: number
      utilization: number
    }>
  }
  tracts: {
    count: number
  }
  sessions: {
    count: number
    totalWorkingMemory: number
  }
  oscillation: {
    isRunning: boolean
    intervalMs: number
    totalTicks: number
    avgDurationMs: number
    totalDecayed: number
    totalPruned: number
    totalConsolidated: number
    totalBound: number
  }
  signalsByType: Record<string, number>
  signalsByState: Record<string, number>
}

export interface SignalSearchOpts {
  region?: string
  type?: SignalType
  state?: SignalState
  author?: string
  tags?: string[]
  sessionId?: string
  content?: string
  limit?: number
}

export class CorticalField {
  readonly sensory: Region
  readonly association: Region
  readonly executive: Region
  readonly motor: Region
  readonly limbic: Region
  readonly monitor: Region

  private regions = new Map<string, Region>()
  private tractEngine = new TractEngine()
  private logger: ILogger
  private tickInterval: ReturnType<typeof setInterval> | null = null
  private tickIntervalMs: number
  private onConsolidate?: ConsolidationCallback
  private affectRegister?: AffectRegister
  private sessions = new Map<string, CortexSession>()
  private oscillationHistory: OscillationHistoryEntry[] = []
  private cumulativeOscillation = { ticks: 0, decayed: 0, pruned: 0, consolidated: 0, bound: 0, totalDurationMs: 0 }
  private mnemicField?: MnemicField

  constructor(logger: ILogger, config?: CorticalFieldConfig) {
    this.logger = logger.child('cortex')
    this.tickIntervalMs = config?.tickIntervalMs ?? ACTIVATION_DEFAULTS.tickIntervalMs
    this.onConsolidate = config?.onConsolidate

    this.sensory = this.initRegion('sensory', SYSTEM_REGIONS.sensory)
    this.association = this.initRegion('association', SYSTEM_REGIONS.association)
    this.executive = this.initRegion('executive', SYSTEM_REGIONS.executive)
    this.motor = this.initRegion('motor', SYSTEM_REGIONS.motor)
    this.limbic = this.initRegion('limbic', SYSTEM_REGIONS.limbic)
    this.monitor = this.initRegion('monitor', SYSTEM_REGIONS.monitor)

    for (const def of SYSTEM_TRACTS) {
      this.tractEngine.connect(def.from, def.to, def.config)
    }

    this.logger.info('CorticalField initialized', {
      regions: this.regions.size,
      tracts: this.tractEngine.list().length,
    })
  }

  private initRegion(name: string, config: RegionConfig): Region {
    const region = new Region(name, config)
    this.regions.set(name, region)
    return region
  }

  setAffectRegister(register: AffectRegister): void {
    this.affectRegister = register
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }

  setConsolidationCallback(cb: ConsolidationCallback): void {
    this.onConsolidate = cb
  }

  getAffectState(): import('./types.js').Affect | undefined {
    const state = this.affectRegister?.getState()
    if (!state) return undefined
    return { valence: state.valence, arousal: state.arousal }
  }

  private cascadePropagate(signal: CorticalSignal, maxDepth = 3): void {
    const visited = new Set<string>()
    const queue: Array<{ signal: CorticalSignal; depth: number }> = [{ signal, depth: 0 }]

    while (queue.length > 0) {
      const { signal: current, depth } = queue.shift()!
      if (depth >= maxDepth || visited.has(current.id)) continue
      visited.add(current.id)

      const derived = this.tractEngine.propagate(current, this.regions)
      for (const d of derived) {
        queue.push({ signal: d, depth: depth + 1 })
      }
    }

    const total = visited.size - 1
    if (total > 0) {
      this.logger.debug('Tract propagation', {
        source: signal.region,
        signalId: signal.id,
        totalDerived: total,
      })
    }
  }

  signal(regionName: string, input: SignalInput): CorticalSignal {
    const region = this.regions.get(regionName)
    if (!region) throw new Error(`Unknown region: ${regionName}`)

    const sig = region.post(input)

    if (regionName === 'limbic' && this.affectRegister) {
      this.affectRegister.absorbSignal({
        valence: sig.valence,
        arousal: sig.salience,
      })
    }

    this.cascadePropagate(sig)

    if (this.mnemicField && sig.content) {
      this.mnemicField.classifyPhrase(sig.content, SIGNAL_TYPE_PHRASES).then(result => {
        if (result?.label && result.label !== sig.type && result.score > 0.45) {
          this.logger.warn('signal type mismatch', {
            declared: sig.type,
            classified: result.label,
            score: result.score.toFixed(2),
          })
        }
      }).catch(() => {})
    }

    return sig
  }

  readActive(opts?: {
    regions?: string[]
    types?: SignalType[]
    limit?: number
    sessionId?: string
  }): CorticalSignal[] {
    const now = Date.now()
    const regionNames = opts?.regions ?? [...this.regions.keys()]
    let result: CorticalSignal[] = []

    for (const name of regionNames) {
      const region = this.regions.get(name)
      if (!region) continue
      result.push(...region.getActive(now))
    }

    if (opts?.types) {
      result = result.filter(s => opts.types!.includes(s.type))
    }

    if (opts?.sessionId) {
      result = result.filter(s => s.sessionId === opts.sessionId)
    }

    result.sort((a, b) => computeActivation(b, now) - computeActivation(a, now))

    if (opts?.limit) {
      result = result.slice(0, opts.limit)
    }

    return result
  }

  attend(signalId: string): CorticalSignal | undefined {
    for (const region of this.regions.values()) {
      const signal = region.attend(signalId)
      if (signal) return signal
    }
    return undefined
  }

  getSignal(signalId: string): CorticalSignal | undefined {
    for (const region of this.regions.values()) {
      const signal = region.get(signalId)
      if (signal) return signal
    }
    return undefined
  }

  getRegion(name: string): Region | undefined {
    return this.regions.get(name)
  }

  createRegion(name: string, config?: Partial<RegionConfig>): Region {
    if (this.regions.has(name)) throw new Error(`Region already exists: ${name}`)
    const full: RegionConfig = {
      capacity: config?.capacity ?? 50,
      defaultDecayRate: config?.defaultDecayRate ?? ACTIVATION_DEFAULTS.defaultDecayRate,
      description: config?.description,
    }
    const region = new Region(name, full)
    this.regions.set(name, region)
    this.logger.info('Region created', { name, capacity: full.capacity })
    return region
  }

  deleteRegion(name: string): boolean {
    if (SYSTEM_REGION_NAMES.includes(name)) {
      throw new Error(`Cannot delete system region: ${name}`)
    }
    const deleted = this.regions.delete(name)
    if (deleted) this.logger.info('Region deleted', { name })
    return deleted
  }

  listRegions(): RegionInfo[] {
    const now = Date.now()
    return [...this.regions.entries()].map(([name, region]) => ({
      name,
      isSystem: SYSTEM_REGION_NAMES.includes(name),
      config: region.config,
      signalCount: region.size(),
      activeCount: region.countActive(now),
    }))
  }

  connect(from: string, to: string, config?: TractConfig): Tract {
    if (!this.regions.has(from)) throw new Error(`Unknown source region: ${from}`)
    if (!this.regions.has(to)) throw new Error(`Unknown target region: ${to}`)
    const tract = this.tractEngine.connect(from, to, config)
    this.logger.debug('Tract connected', { from, to, strength: tract.strength })
    return tract
  }

  disconnect(tractId: string): boolean {
    return this.tractEngine.disconnect(tractId)
  }

  listTracts(): Tract[] {
    return this.tractEngine.list()
  }

  createSession(sessionId: string, config?: CortexSessionConfig): CortexSession {
    if (this.sessions.has(sessionId)) {
      return this.sessions.get(sessionId)!
    }
    const session = new CortexSession(this, sessionId, config)
    this.sessions.set(sessionId, session)
    this.logger.debug('Session created', { sessionId: sessionId.slice(-8) })
    return session
  }

  getSession(sessionId: string): CortexSession | undefined {
    return this.sessions.get(sessionId)
  }

  endSession(sessionId: string): CortexSessionSnapshot | undefined {
    const session = this.sessions.get(sessionId)
    if (!session) return undefined
    const snapshot = session.snapshot()
    session.close()
    this.sessions.delete(sessionId)
    this.logger.debug('Session ended', { sessionId: sessionId.slice(-8) })
    return snapshot
  }

  listSessions(): Array<{ sessionId: string; workingMemorySize: number }> {
    return [...this.sessions.entries()].map(([id, session]) => ({
      sessionId: id,
      workingMemorySize: session.getWorkingMemorySize(),
    }))
  }

  tick(): OscillationResult {
    const result = oscillate(this.regions, this.onConsolidate)

    this.oscillationHistory.push({ ...result, timestamp: Date.now() })
    if (this.oscillationHistory.length > MAX_OSCILLATION_HISTORY) {
      this.oscillationHistory.shift()
    }
    this.cumulativeOscillation.ticks++
    this.cumulativeOscillation.decayed += result.decayed
    this.cumulativeOscillation.pruned += result.pruned
    this.cumulativeOscillation.consolidated += result.consolidated
    this.cumulativeOscillation.bound += result.bound
    this.cumulativeOscillation.totalDurationMs += result.durationMs

    if (result.pruned > 0 || result.consolidated > 0 || result.bound > 0) {
      this.logger.debug('Oscillation tick', { ...result })
    }
    return result
  }

  startOscillation(): void {
    if (this.tickInterval) return
    this.tickInterval = setInterval(() => this.tick(), this.tickIntervalMs)
    this.logger.info('Oscillation started', { intervalMs: this.tickIntervalMs })
  }

  stopOscillation(): void {
    if (!this.tickInterval) return
    clearInterval(this.tickInterval)
    this.tickInterval = null
    this.logger.info('Oscillation stopped')
  }

  snapshot(): CorticalFieldSnapshot {
    const regionSnapshots: RegionSnapshot[] = []
    for (const [name, region] of this.regions) {
      regionSnapshots.push({
        name,
        config: region.config,
        signals: region.snapshot(),
      })
    }
    return {
      regions: regionSnapshots,
      tracts: this.tractEngine.snapshot(),
      timestamp: Date.now(),
    }
  }

  restore(snap: CorticalFieldSnapshot): void {
    for (const rs of snap.regions) {
      let region = this.regions.get(rs.name)
      if (!region) {
        region = new Region(rs.name, rs.config)
        this.regions.set(rs.name, region)
      }
      region.restore(rs.signals)
    }
    this.tractEngine.restore(snap.tracts)
    this.logger.info('CorticalField restored', {
      regions: snap.regions.length,
      tracts: snap.tracts.length,
    })
  }

  getOscillationHistory(limit?: number): OscillationHistoryEntry[] {
    const entries = this.oscillationHistory
    if (limit && limit < entries.length) {
      return entries.slice(-limit)
    }
    return [...entries]
  }

  getStats(): CortexStats {
    const now = Date.now()
    const perRegion: CortexStats['regions']['perRegion'] = []
    let totalSignals = 0
    let totalActive = 0
    let totalFading = 0
    let totalConsolidated = 0
    let totalCapacity = 0
    const byType: Record<string, number> = {}
    const byState: Record<string, number> = {}

    for (const [name, region] of this.regions) {
      const signals = region.snapshot()
      let active = 0, fading = 0, consolidated = 0

      for (const s of signals) {
        const a = computeActivation(s, now)
        if (s.state === 'consolidated') {
          consolidated++
        } else if (a > ACTIVATION_DEFAULTS.activeThreshold) {
          active++
        } else if (a > ACTIVATION_DEFAULTS.fadingThreshold) {
          fading++
        }
        byType[s.type] = (byType[s.type] ?? 0) + 1
        byState[s.state] = (byState[s.state] ?? 0) + 1
      }

      const capacity = region.config.capacity
      totalSignals += signals.length
      totalActive += active
      totalFading += fading
      totalConsolidated += consolidated
      totalCapacity += capacity

      perRegion.push({
        name,
        signals: signals.length,
        active,
        fading,
        consolidated,
        capacity,
        utilization: capacity > 0 ? signals.length / capacity : 0,
      })
    }

    const cum = this.cumulativeOscillation
    return {
      regions: {
        count: this.regions.size,
        totalSignals,
        totalActive,
        totalFading,
        totalConsolidated,
        capacityUtilization: totalCapacity > 0 ? totalSignals / totalCapacity : 0,
        perRegion,
      },
      tracts: { count: this.tractEngine.list().length },
      sessions: {
        count: this.sessions.size,
        totalWorkingMemory: [...this.sessions.values()]
          .reduce((sum, s) => sum + s.getWorkingMemorySize(), 0),
      },
      oscillation: {
        isRunning: this.tickInterval !== null,
        intervalMs: this.tickIntervalMs,
        totalTicks: cum.ticks,
        avgDurationMs: cum.ticks > 0 ? cum.totalDurationMs / cum.ticks : 0,
        totalDecayed: cum.decayed,
        totalPruned: cum.pruned,
        totalConsolidated: cum.consolidated,
        totalBound: cum.bound,
      },
      signalsByType: byType,
      signalsByState: byState,
    }
  }

  searchSignals(opts: SignalSearchOpts): CorticalSignal[] {
    const now = Date.now()
    let results: CorticalSignal[] = []
    const regionNames = opts.region ? [opts.region] : [...this.regions.keys()]

    for (const name of regionNames) {
      const region = this.regions.get(name)
      if (!region) continue
      results.push(...region.snapshot())
    }

    if (opts.type) {
      results = results.filter(s => s.type === opts.type)
    }
    if (opts.state) {
      results = results.filter(s => s.state === opts.state)
    }
    if (opts.author) {
      results = results.filter(s => s.author === opts.author)
    }
    if (opts.sessionId) {
      results = results.filter(s => s.sessionId === opts.sessionId)
    }
    if (opts.tags && opts.tags.length > 0) {
      results = results.filter(s => opts.tags!.some(t => s.tags.includes(t)))
    }
    if (opts.content) {
      const lower = opts.content.toLowerCase()
      results = results.filter(s => s.content.toLowerCase().includes(lower))
    }

    results.sort((a, b) => computeActivation(b, now) - computeActivation(a, now))

    if (opts.limit) {
      results = results.slice(0, opts.limit)
    }
    return results
  }

  getConsolidated(limit = 20): CorticalSignal[] {
    const consolidated: CorticalSignal[] = []
    for (const region of this.regions.values()) {
      for (const s of region.snapshot()) {
        if (s.state === 'consolidated') consolidated.push(s)
      }
    }
    consolidated.sort((a, b) => (b.consolidatedAt ?? 0) - (a.consolidatedAt ?? 0))
    return consolidated.slice(0, limit)
  }

  getFading(limit = 20): CorticalSignal[] {
    const now = Date.now()
    const fading: CorticalSignal[] = []
    for (const region of this.regions.values()) {
      fading.push(...region.readFading(now))
    }
    fading.sort((a, b) => computeActivation(b, now) - computeActivation(a, now))
    return fading.slice(0, limit)
  }

  getRegionDetail(name: string): {
    name: string
    config: RegionConfig
    signals: Array<CorticalSignal & { computedActivation: number }>
    stateDistribution: Record<string, number>
    capacityUtilization: number
  } | undefined {
    const region = this.regions.get(name)
    if (!region) return undefined
    const now = Date.now()
    const signals = region.snapshot()
    const stateDistribution: Record<string, number> = {}

    const enriched = signals.map(s => {
      stateDistribution[s.state] = (stateDistribution[s.state] ?? 0) + 1
      return { ...s, computedActivation: computeActivation(s, now) }
    })
    enriched.sort((a, b) => b.computedActivation - a.computedActivation)

    return {
      name,
      config: region.config,
      signals: enriched,
      stateDistribution,
      capacityUtilization: region.config.capacity > 0 ? signals.length / region.config.capacity : 0,
    }
  }

  getSignalDetail(signalId: string): (CorticalSignal & { computedActivation: number; boundSignals: Array<{ id: string; content: string; region: string }> }) | undefined {
    const signal = this.getSignal(signalId)
    if (!signal) return undefined
    const now = Date.now()
    const boundSignals = signal.bindings
      .map(id => {
        const bound = this.getSignal(id)
        return bound ? { id: bound.id, content: bound.content, region: bound.region } : null
      })
      .filter((b): b is NonNullable<typeof b> => b !== null)

    return {
      ...signal,
      computedActivation: computeActivation(signal, now),
      boundSignals,
    }
  }

  getSessionDetail(sessionId: string): {
    sessionId: string
    workingMemoryCapacity: number
    workingMemory: Array<CorticalSignal & { computedActivation: number }>
    allSessionSignals: number
  } | undefined {
    const session = this.sessions.get(sessionId)
    if (!session) return undefined
    const now = Date.now()
    const wmSignals = session.getWorkingMemory().map(s => ({
      ...s,
      computedActivation: computeActivation(s, now),
    }))

    let allCount = 0
    for (const region of this.regions.values()) {
      for (const s of region.snapshot()) {
        if (s.sessionId === sessionId) allCount++
      }
    }

    return {
      sessionId,
      workingMemoryCapacity: session.workingMemoryCapacity,
      workingMemory: wmSignals,
      allSessionSignals: allCount,
    }
  }

  getTract(tractId: string): Tract | undefined {
    return this.tractEngine.get(tractId)
  }

  close(): void {
    this.stopOscillation()
    for (const session of this.sessions.values()) {
      session.close()
    }
    this.sessions.clear()
    for (const region of this.regions.values()) {
      region.clear()
    }
    this.tractEngine.clear()
    this.logger.info('CorticalField closed')
  }
}

export { Region } from './region.js'
export { TractEngine } from './tract.js'
export { CortexSession } from './session.js'
export { Commissure } from './commissure.js'
export { createConsolidationBridge, signalToEngram } from './mnemic-bridge.js'
export type { ConsolidationTarget } from './mnemic-bridge.js'
export { oscillate } from './dynamics.js'
export {
  createSignal, computeActivation, attendSignal,
  transitionState, meetsConsolidationCriteria, deriveSignal,
} from './signal.js'
export type {
  CorticalSignal, SignalInput, SignalType, SignalState,
  RegionConfig, RegionInfo,
  Tract, TractConfig, TractFilter, TractTransform,
  CorticalFieldConfig, CorticalFieldSnapshot,
  CortexSessionConfig, CortexSessionSnapshot,
  CommissureConfig,
  OscillationResult, ConsolidationCallback,
} from './types.js'
export {
  SYSTEM_REGIONS, SYSTEM_TRACTS, ACTIVATION_DEFAULTS,
  CONSOLIDATION_DEFAULTS, SESSION_DEFAULTS, COMMISSURE_DEFAULTS,
} from './types.js'
