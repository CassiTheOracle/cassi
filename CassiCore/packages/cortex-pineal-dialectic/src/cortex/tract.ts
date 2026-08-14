import { randomUUID } from 'node:crypto'
import type { CorticalSignal, Tract, TractConfig, TractFilter } from './types.js'
import { ACTIVATION_DEFAULTS } from './types.js'
import { computeActivation, deriveSignal } from './signal.js'
import type { Region } from './region.js'

export class TractEngine {
  private tracts = new Map<string, Tract>()

  connect(from: string, to: string, config?: TractConfig): Tract {
    const tract: Tract = {
      id: randomUUID(),
      from,
      to,
      strength: config?.strength ?? 0.5,
      filter: config?.filter,
      transform: config?.transform,
      refractory: config?.refractory ?? ACTIVATION_DEFAULTS.defaultRefractory,
      lastFired: 0,
    }
    this.tracts.set(tract.id, tract)
    return tract
  }

  disconnect(id: string): boolean {
    return this.tracts.delete(id)
  }

  get(id: string): Tract | undefined {
    return this.tracts.get(id)
  }

  list(): Tract[] {
    return [...this.tracts.values()]
  }

  getOutgoing(regionName: string): Tract[] {
    const result: Tract[] = []
    for (const tract of this.tracts.values()) {
      if (tract.from === regionName) result.push(tract)
    }
    return result
  }

  propagate(
    signal: CorticalSignal,
    regions: Map<string, Region>,
    now?: number,
  ): CorticalSignal[] {
    const t = now ?? Date.now()
    const outgoing = this.getOutgoing(signal.region)
    const derived: CorticalSignal[] = []

    for (const tract of outgoing) {
      if (!this.canFire(tract, t)) continue
      if (!this.passesFilter(signal, tract.filter, t)) continue

      const targetRegion = regions.get(tract.to)
      if (!targetRegion) continue

      const child = deriveSignal(signal, tract, tract.to, targetRegion.config.defaultDecayRate)
      targetRegion.insert(child)
      tract.lastFired = t
      derived.push(child)
    }

    return derived
  }

  private canFire(tract: Tract, now: number): boolean {
    return (now - tract.lastFired) >= tract.refractory
  }

  private passesFilter(signal: CorticalSignal, filter: TractFilter | undefined, now: number): boolean {
    if (!filter) return true

    if (filter.types && !filter.types.includes(signal.type)) return false

    if (filter.minSalience !== undefined && signal.salience < filter.minSalience) return false

    if (filter.minActivation !== undefined) {
      const a = computeActivation(signal, now)
      if (a < filter.minActivation) return false
    }

    if (filter.tags && filter.tags.length > 0) {
      const hasMatchingTag = filter.tags.some(t => signal.tags.includes(t))
      if (!hasMatchingTag) return false
    }

    return true
  }

  clear(): void {
    this.tracts.clear()
  }

  snapshot(): Tract[] {
    return [...this.tracts.values()]
  }

  restore(tracts: Tract[]): void {
    this.tracts.clear()
    for (const t of tracts) {
      this.tracts.set(t.id, t)
    }
  }
}
