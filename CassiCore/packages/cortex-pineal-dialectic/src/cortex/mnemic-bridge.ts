import type { CorticalSignal, ConsolidationCallback, SignalType } from './types.js'
import type { EngramCreate, EngramType } from '@cassicore/mnemic-field'

const SIGNAL_TO_ENGRAM_TYPE: Record<SignalType, EngramType> = {
  perception: 'episode',
  association: 'pattern',
  concern: 'episode',
  decision: 'decision',
  action: 'episode',
  request: 'episode',
  anomaly: 'episode',
  insight: 'abstraction',
}

export interface ConsolidationTarget {
  store(input: EngramCreate): { id: string }
}

export function signalToEngram(signal: CorticalSignal): EngramCreate {
  return {
    content: signal.content,
    nodeType: SIGNAL_TO_ENGRAM_TYPE[signal.type],
    tags: [
      ...signal.tags,
      `cortex:${signal.region}`,
      `signal:${signal.type}`,
    ],
    provenance: `cortex/${signal.author}`,
    metadata: {
      cortexSignalId: signal.id,
      region: signal.region,
      signalType: signal.type,
      salience: signal.salience,
      valence: signal.valence,
      confidence: signal.confidence,
      sessionId: signal.sessionId,
      sourceSignals: [...signal.sourceSignals],
      bindings: [...signal.bindings],
      consolidatedAt: signal.consolidatedAt,
    },
  }
}

export function createConsolidationBridge(
  target: ConsolidationTarget,
  logger?: { warn(msg: string, meta?: Record<string, unknown>): void; debug(msg: string, meta?: Record<string, unknown>): void },
): ConsolidationCallback {
  return (signal: CorticalSignal) => {
    try {
      const engram = signalToEngram(signal)
      const result = target.store(engram)
      logger?.debug('Cortex signal consolidated to mnemic field', {
        signalId: signal.id,
        engramId: result.id,
        region: signal.region,
        type: signal.type,
      })
    } catch (err) {
      logger?.warn('Consolidation bridge failed', { signalId: signal.id, error: String(err) })
    }
  }
}
