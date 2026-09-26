import type { CorticalSignal, ConsolidationCallback, OscillationResult } from './types.js'
import { ACTIVATION_DEFAULTS } from './types.js'
import { meetsConsolidationCriteria } from './signal.js'
import type { Region } from './region.js'

const MAX_BINDINGS_PER_SIGNAL = 20

export function oscillate(
  regions: Map<string, Region>,
  onConsolidate?: ConsolidationCallback,
): OscillationResult {
  const start = Date.now()
  let decayed = 0
  let pruned = 0
  let consolidated = 0

  for (const region of regions.values()) {
    const stateChanges = region.updateStates(start)
    decayed += stateChanges.decayed.length

    const fadingSignals = region.readFading(start)
    for (const signal of fadingSignals) {
      if (meetsConsolidationCriteria(signal)) {
        signal.state = 'consolidated'
        signal.consolidatedAt = start
        consolidated++
        onConsolidate?.(signal)
      }
    }

    pruned += region.prune()
  }

  const activeSignals = collectActive(regions, start)
  let bound = 0
  bound += bindByKey(activeSignals, s => s.tags)
  bound += bindByKey(activeSignals, s => s.sessionId ? [s.sessionId] : [])

  return {
    decayed,
    pruned,
    consolidated,
    bound,
    durationMs: Date.now() - start,
  }
}

function collectActive(regions: Map<string, Region>, now: number): CorticalSignal[] {
  const result: CorticalSignal[] = []
  for (const region of regions.values()) {
    for (const signal of region.getActive(now)) {
      result.push(signal)
    }
  }
  return result
}

function bindByKey(
  signals: CorticalSignal[],
  extractKeys: (signal: CorticalSignal) => string[],
): number {
  const index = new Map<string, CorticalSignal[]>()

  for (const signal of signals) {
    for (const key of extractKeys(signal)) {
      let group = index.get(key)
      if (!group) {
        group = []
        index.set(key, group)
      }
      group.push(signal)
    }
  }

  let bound = 0
  for (const group of index.values()) {
    if (group.length < 2) continue
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        if (addBinding(group[i], group[j])) bound++
      }
    }
  }
  return bound
}

function addBinding(a: CorticalSignal, b: CorticalSignal): boolean {
  if (a.bindings.length >= MAX_BINDINGS_PER_SIGNAL || b.bindings.length >= MAX_BINDINGS_PER_SIGNAL) return false
  if (a.bindings.includes(b.id) || b.bindings.includes(a.id)) return false
  a.bindings.push(b.id)
  b.bindings.push(a.id)
  return true
}
