import type { CorticalSignal, SignalInput, SignalType, CortexSessionConfig, CortexSessionSnapshot } from './types.js'
import { SESSION_DEFAULTS } from './types.js'
import { computeActivation, attendSignal } from './signal.js'
import type { CorticalField } from './index.js'

export class CortexSession {
  readonly sessionId: string
  readonly workingMemoryCapacity: number

  private cortex: CorticalField
  private workingMemory = new Set<string>()

  constructor(cortex: CorticalField, sessionId: string, config?: CortexSessionConfig) {
    this.cortex = cortex
    this.sessionId = sessionId
    this.workingMemoryCapacity = config?.workingMemoryCapacity ?? SESSION_DEFAULTS.workingMemoryCapacity
  }

  signal(region: string, input: Omit<SignalInput, 'sessionId'>): CorticalSignal {
    return this.cortex.signal(region, { ...input, sessionId: this.sessionId })
  }

  read(region?: string, opts?: { types?: SignalType[]; limit?: number }): CorticalSignal[] {
    return this.cortex.readActive({
      regions: region ? [region] : undefined,
      types: opts?.types,
      limit: opts?.limit,
      sessionId: this.sessionId,
    })
  }

  focus(signalId: string): boolean {
    const signal = this.cortex.getSignal(signalId)
    if (!signal) return false
    if (signal.sessionId !== this.sessionId) return false

    attendSignal(signal)
    this.workingMemory.add(signalId)

    if (this.workingMemory.size > this.workingMemoryCapacity) {
      this.evictWeakest()
    }
    return true
  }

  defocus(signalId: string): boolean {
    return this.workingMemory.delete(signalId)
  }

  getWorkingMemory(): CorticalSignal[] {
    const now = Date.now()
    const signals: CorticalSignal[] = []

    for (const id of this.workingMemory) {
      const signal = this.cortex.getSignal(id)
      if (!signal || signal.state === 'decayed') {
        this.workingMemory.delete(id)
        continue
      }
      signals.push(signal)
    }

    return signals.sort((a, b) => computeActivation(b, now) - computeActivation(a, now))
  }

  getWorkingMemorySize(): number {
    this.pruneDecayed()
    return this.workingMemory.size
  }

  isInWorkingMemory(signalId: string): boolean {
    if (!this.workingMemory.has(signalId)) return false
    const signal = this.cortex.getSignal(signalId)
    if (!signal || signal.state === 'decayed') {
      this.workingMemory.delete(signalId)
      return false
    }
    return true
  }

  private pruneDecayed(): void {
    for (const id of this.workingMemory) {
      const signal = this.cortex.getSignal(id)
      if (!signal || signal.state === 'decayed') {
        this.workingMemory.delete(id)
      }
    }
  }

  private evictWeakest(): void {
    const now = Date.now()
    let weakestId: string | null = null
    let weakestActivation = Infinity

    for (const id of this.workingMemory) {
      const signal = this.cortex.getSignal(id)
      if (!signal) {
        this.workingMemory.delete(id)
        return
      }
      const a = computeActivation(signal, now)
      if (a < weakestActivation) {
        weakestActivation = a
        weakestId = id
      }
    }

    if (weakestId) this.workingMemory.delete(weakestId)
  }

  snapshot(): CortexSessionSnapshot {
    return {
      sessionId: this.sessionId,
      workingMemory: [...this.workingMemory],
      timestamp: Date.now(),
    }
  }

  restore(snap: CortexSessionSnapshot): void {
    this.workingMemory.clear()
    for (const id of snap.workingMemory) {
      if (this.cortex.getSignal(id)) {
        this.workingMemory.add(id)
      }
    }
  }

  close(): void {
    this.workingMemory.clear()
  }
}
