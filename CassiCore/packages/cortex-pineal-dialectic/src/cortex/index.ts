import type { ILogger } from '../../../types/interfaces.js'
import type {
  CorticalSignal, SignalInput, SignalType,
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
import type { AffectRegister } from '../mnemic-field/affect.js'

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
