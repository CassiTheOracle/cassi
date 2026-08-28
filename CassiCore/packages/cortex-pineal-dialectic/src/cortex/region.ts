import type { CorticalSignal, RegionConfig, SignalInput } from './types.js'
import { ACTIVATION_DEFAULTS } from './types.js'
import { createSignal, computeActivation, attendSignal, transitionState } from './signal.js'

export class Region {
  readonly name: string
  readonly config: RegionConfig
  private signals = new Map<string, CorticalSignal>()

  constructor(name: string, config: RegionConfig) {
    this.name = name
    this.config = config
  }

  post(input: SignalInput): CorticalSignal {
    const signal = createSignal(this.name, input, this.config.defaultDecayRate)
    this.signals.set(signal.id, signal)
    this.enforceCapacity()
    return signal
  }

  insert(signal: CorticalSignal): void {
    this.signals.set(signal.id, signal)
    this.enforceCapacity()
  }

  get(id: string): CorticalSignal | undefined {
    return this.signals.get(id)
  }

  remove(id: string): boolean {
    return this.signals.delete(id)
  }

  attend(id: string): CorticalSignal | undefined {
    const signal = this.signals.get(id)
    if (!signal) return undefined
    attendSignal(signal)
    return signal
  }

  getActive(now?: number): CorticalSignal[] {
    const t = now ?? Date.now()
    const active: CorticalSignal[] = []
    for (const signal of this.signals.values()) {
      if (computeActivation(signal, t) > ACTIVATION_DEFAULTS.activeThreshold) {
        active.push(signal)
      }
    }
    return active
  }

  readActive(now?: number): CorticalSignal[] {
    const t = now ?? Date.now()
    return this.getActive(t).sort((a, b) => computeActivation(b, t) - computeActivation(a, t))
  }

  countActive(now?: number): number {
    const t = now ?? Date.now()
    let count = 0
    for (const signal of this.signals.values()) {
      if (computeActivation(signal, t) > ACTIVATION_DEFAULTS.activeThreshold) {
        count++
      }
    }
    return count
  }

  readFading(now?: number): CorticalSignal[] {
    const t = now ?? Date.now()
    const fading: CorticalSignal[] = []
    for (const signal of this.signals.values()) {
      if (signal.state === 'consolidated') continue
      const a = computeActivation(signal, t)
      if (a > ACTIVATION_DEFAULTS.fadingThreshold && a <= ACTIVATION_DEFAULTS.activeThreshold) {
        fading.push(signal)
      }
    }
    return fading
  }

  readAll(now?: number): CorticalSignal[] {
    const t = now ?? Date.now()
    const result: CorticalSignal[] = []
    for (const signal of this.signals.values()) {
      if (signal.state === 'consolidated') continue
      if (computeActivation(signal, t) > ACTIVATION_DEFAULTS.fadingThreshold) {
        result.push(signal)
      }
    }
    return result.sort((a, b) => computeActivation(b, t) - computeActivation(a, t))
  }

  enforceCapacity(): CorticalSignal[] {
    if (this.signals.size <= this.config.capacity) return []

    const now = Date.now()
    const ranked = [...this.signals.values()]
      .map(s => ({ signal: s, activation: computeActivation(s, now) }))
      .sort((a, b) => a.activation - b.activation)

    const evictCount = this.signals.size - this.config.capacity
    const evicted: CorticalSignal[] = []

    for (let i = 0; i < evictCount; i++) {
      const { signal } = ranked[i]
      this.signals.delete(signal.id)
      evicted.push(signal)
    }

    return evicted
  }

  updateStates(now?: number): { decayed: string[]; fading: string[] } {
    const t = now ?? Date.now()
    const decayed: string[] = []
    const fading: string[] = []

    for (const signal of this.signals.values()) {
      const prevState = signal.state
      transitionState(signal, t)
      if (signal.state === 'decayed' && prevState !== 'decayed') {
        decayed.push(signal.id)
      } else if (signal.state === 'fading' && prevState === 'active') {
        fading.push(signal.id)
      }
    }

    return { decayed, fading }
  }

  prune(): number {
    let pruned = 0
    for (const [id, signal] of this.signals) {
      if (signal.state === 'decayed') {
        this.signals.delete(id)
        pruned++
      }
    }
    return pruned
  }

  size(): number {
    return this.signals.size
  }

  clear(): void {
    this.signals.clear()
  }

  snapshot(): CorticalSignal[] {
    return [...this.signals.values()]
  }

  restore(signals: CorticalSignal[]): void {
    this.signals.clear()
    for (const s of signals) {
      this.signals.set(s.id, s)
    }
  }
}
