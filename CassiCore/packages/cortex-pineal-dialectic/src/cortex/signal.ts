import { randomUUID } from 'node:crypto'
import type { CorticalSignal, SignalInput, Tract } from './types.js'
import { ACTIVATION_DEFAULTS, CONSOLIDATION_DEFAULTS } from './types.js'

export function createSignal(region: string, input: SignalInput, defaultDecayRate: number): CorticalSignal {
  const now = Date.now()
  const salience = input.salience ?? ACTIVATION_DEFAULTS.defaultSalience
  return {
    id: randomUUID(),
    region,
    type: input.type,
    content: input.content,
    structured: input.structured,
    author: input.author,
    source: input.source,
    sessionId: input.sessionId,
    salience,
    activation: salience,
    valence: input.valence ?? 0,
    confidence: input.confidence ?? ACTIVATION_DEFAULTS.defaultConfidence,
    tags: input.tags ?? [],
    bindings: [],
    sourceSignals: input.sourceSignals ?? [],
    createdAt: now,
    lastAttended: now,
    decayRate: input.decayRate ?? defaultDecayRate,
    state: 'active',
  }
}

/**
 * Lazy exponential decay: activation decays toward 0 based on time since last attended.
 * activation(t) = activation_at_lastAttended * e^(-decayRate * elapsed_minutes)
 */
export function computeActivation(signal: CorticalSignal, now?: number): number {
  const t = now ?? Date.now()
  const elapsedMinutes = (t - signal.lastAttended) / 60_000
  if (elapsedMinutes <= 0) return signal.activation
  return signal.activation * Math.exp(-signal.decayRate * elapsedMinutes)
}

export function attendSignal(signal: CorticalSignal): void {
  signal.activation = computeActivation(signal)
  signal.activation = Math.min(1.0, signal.activation + ACTIVATION_DEFAULTS.attentionBoost)
  signal.lastAttended = Date.now()
}

export function transitionState(signal: CorticalSignal, now?: number): void {
  const currentActivation = computeActivation(signal, now)

  if (signal.state === 'consolidated' || signal.state === 'decayed') return

  if (currentActivation > ACTIVATION_DEFAULTS.activeThreshold) {
    signal.state = 'active'
  } else if (currentActivation > ACTIVATION_DEFAULTS.fadingThreshold) {
    signal.state = 'fading'
  } else {
    signal.state = 'decayed'
  }
}

export function meetsConsolidationCriteria(signal: CorticalSignal): boolean {
  if (signal.salience >= CONSOLIDATION_DEFAULTS.salienceMin) return true

  const referenceCount = signal.sourceSignals.length
  if (referenceCount >= CONSOLIDATION_DEFAULTS.referenceCountMin) return true

  if (signal.bindings.length >= CONSOLIDATION_DEFAULTS.bindingCountMin) return true

  return false
}

export function deriveSignal(
  original: CorticalSignal,
  tract: Tract,
  targetRegion: string,
  defaultDecayRate: number,
): CorticalSignal {
  const now = Date.now()
  const activationScale = tract.transform?.activationScale ?? tract.strength
  const activation = computeActivation(original) * activationScale

  const tags = [...original.tags]
  if (tract.transform?.addTags) {
    for (const tag of tract.transform.addTags) {
      if (!tags.includes(tag)) tags.push(tag)
    }
  }

  return {
    id: randomUUID(),
    region: targetRegion,
    type: tract.transform?.typeOverride ?? original.type,
    content: original.content,
    structured: original.structured,
    author: original.author,
    source: original.id,
    sessionId: original.sessionId,
    salience: original.salience * activationScale,
    activation,
    valence: original.valence,
    confidence: original.confidence,
    tags,
    bindings: [],
    sourceSignals: [original.id],
    createdAt: now,
    lastAttended: now,
    decayRate: defaultDecayRate,
    state: activation > ACTIVATION_DEFAULTS.activeThreshold ? 'active' : 'fading',
  }
}
