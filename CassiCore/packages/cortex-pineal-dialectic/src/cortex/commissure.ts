import type { CorticalSignal, SignalType, CommissureConfig } from './types.js'
import { COMMISSURE_DEFAULTS } from './types.js'
import type { CorticalField } from './index.js'
import type { CortexSession } from './session.js'
import { computeActivation } from './signal.js'

const MAX_DEDUP_SIZE = 2000

export class Commissure {
  private parent: CorticalField
  private child: CortexSession
  private dedup = new Set<string>()
  private lastAscending = 0
  private lastDescending = 0
  private minIntervalMs: number
  private ascendingFilters: CommissureTractConfig[]
  private descendingFilters: CommissureTractConfig[]

  constructor(
    parent: CorticalField,
    child: CortexSession,
    config?: CommissureConfig,
  ) {
    this.parent = parent
    this.child = child
    this.minIntervalMs = 1000 / (config?.maxPropagationsPerSecond ?? COMMISSURE_DEFAULTS.maxPropagationsPerSecond)

    this.ascendingFilters = [
      { fromRegion: 'association', toRegion: 'association', minSalience: 0.5 },
      { fromRegion: 'limbic', toRegion: 'limbic', minSalience: 0.4 },
      { fromRegion: 'executive', toRegion: 'executive', minSalience: 0.6 },
    ]

    this.descendingFilters = [
      { fromRegion: 'executive', toRegion: 'executive', minSalience: 0.5, types: ['decision'] },
    ]
  }

  propagateAscending(): CorticalSignal[] {
    const now = Date.now()
    if (now - this.lastAscending < this.minIntervalMs) return []

    const propagated: CorticalSignal[] = []

    for (const filter of this.ascendingFilters) {
      const signals = this.child.read(filter.fromRegion, { types: filter.types })

      for (const signal of signals) {
        if (this.isDuplicate(signal)) continue
        if (computeActivation(signal, now) < (filter.minSalience ?? 0)) continue

        const derived = this.parent.signal(filter.toRegion, {
          type: signal.type,
          content: signal.content,
          author: signal.author,
          source: signal.id,
          sessionId: this.child.sessionId,
          salience: signal.salience * 0.8,
          valence: signal.valence,
          confidence: signal.confidence,
          tags: [...signal.tags, `from:${this.child.sessionId.slice(-8)}`],
          sourceSignals: [signal.id],
        })

        this.dedup.add(signal.id)
        this.dedup.add(derived.id)
        propagated.push(derived)
      }
    }

    if (propagated.length > 0) this.lastAscending = now
    this.pruneDedup()
    return propagated
  }

  propagateDescending(): CorticalSignal[] {
    const now = Date.now()
    if (now - this.lastDescending < this.minIntervalMs) return []

    const propagated: CorticalSignal[] = []

    for (const filter of this.descendingFilters) {
      const parentRegion = this.parent.getRegion(filter.fromRegion)
      if (!parentRegion) continue

      const signals = parentRegion.getActive(now)

      for (const signal of signals) {
        if (this.isDuplicate(signal)) continue
        if (signal.sessionId === this.child.sessionId) continue
        if (filter.types && !filter.types.includes(signal.type)) continue
        if (computeActivation(signal, now) < (filter.minSalience ?? 0)) continue

        const derived = this.child.signal(filter.toRegion, {
          type: signal.type,
          content: signal.content,
          author: signal.author,
          source: signal.id,
          salience: signal.salience * 0.7,
          valence: signal.valence,
          confidence: signal.confidence,
          tags: [...signal.tags, 'guidance'],
          sourceSignals: [signal.id],
        })

        this.dedup.add(signal.id)
        this.dedup.add(derived.id)
        propagated.push(derived)
      }
    }

    if (propagated.length > 0) this.lastDescending = now
    this.pruneDedup()
    return propagated
  }

  propagate(): { ascending: CorticalSignal[]; descending: CorticalSignal[] } {
    return {
      ascending: this.propagateAscending(),
      descending: this.propagateDescending(),
    }
  }

  private isDuplicate(signal: CorticalSignal): boolean {
    if (this.dedup.has(signal.id)) return true
    if (signal.source && this.dedup.has(signal.source)) return true
    return false
  }

  private pruneDedup(): void {
    if (this.dedup.size > MAX_DEDUP_SIZE) {
      this.dedup.clear()
    }
  }

  clearDedup(): void {
    this.dedup.clear()
  }

  get dedupSize(): number {
    return this.dedup.size
  }
}

interface CommissureTractConfig {
  fromRegion: string
  toRegion: string
  minSalience?: number
  types?: SignalType[]
}
