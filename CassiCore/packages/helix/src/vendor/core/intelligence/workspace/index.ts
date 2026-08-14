/**
 * VENDORED TYPE STUB — `core/intelligence/workspace/index.ts`
 *
 * Faithful type surface for helix consumers: `GlobalWorkspace`, `CognitiveSignal`,
 * `SignalType`, `TraitVector`, `SystemLuminanceScore`, `WorkspaceResponse`.
 * The shared signal types (`SignalType`, `CognitiveSignal`, `SystemLuminanceScore`,
 * `GlobalWorkspace`) are aligned byte-for-byte with `@cassicore/foundation`'s
 * canonical vendored `core/intelligence/workspace/index.ts` so PostureModule's
 * `BaseCognitiveModule` override and `setGlobalWorkspace` wiring type-check.
 * Helix additionally publishes via the legacy `broadcast(...)` and reads
 * `getRecentSignals(...)` (kept on the interface).
 * Self-contained; only builtin types. Re-pointed to `@cassicore/lamina` at P5.
 */
import type { IEventBus } from '@cassicore/foundation'

/** Functional category of a cognitive signal. */
export type SignalType =
  | 'insight'
  | 'observation'
  | 'warning'
  | 'memory'
  | 'tension'
  | 'convergence'
  | 'suggestion'
  | 'context'
  | 'enrichment'
  | 'goal'
  | 'bridge'

/** Trait vector of a signal's publisher. */
export interface TraitVector {
  [trait: string]: number
}

/** System-level luminance score — four-plus dimensions of salience. */
export interface SystemLuminanceScore {
  /** 0-1: Is this information new relative to what's already in the workspace? */
  novelty: number
  /** 0-1: How time-sensitive? */
  urgency: number
  /** 0-1: How many active sessions / processing contexts benefit? */
  relevance: number
  /** 0-1: Track record of this source producing useful signals. */
  sourceCredibility: number
  /** 0-1: Alignment with current cognitive state. */
  cognitiveResonance: number
  /** 0-1: Enduring significance. */
  strategicImportance: number
  /** Weighted composite — the actual competition score. */
  composite: number
}

/** The unit of competition in the Global Workspace. */
export interface CognitiveSignal {
  /** Unique identifier for this signal */
  signalId: string
  /** Module that produced this signal (e.g. 'thinker', 'subconscious') */
  source: string
  /** Session this signal applies to (or '*' for global signals) */
  sessionId: string
  /** Functional category */
  type: SignalType
  /** The actual payload — what the module wants to communicate */
  content: string
  /** Luminance score (set by the workspace's luminance scorer) */
  luminance: SystemLuminanceScore
  /** Coalition IDs this signal has joined (populated by workspace) */
  coalitionIds?: string[]
  /** When this signal was created */
  createdAt: number
  /** Optional urgency hint from the module */
  urgencyHint?: number
  /** Module-specific metadata for downstream tracing */
  metadata?: Record<string, unknown>
  /** Trait vector of the signal's publisher */
  publisherTraitVector?: TraitVector
}

/** A slot in the workspace holding a current signal (or empty). */
export interface WorkspaceSlot {
  signal: CognitiveSignal | null
}

/** How a module's response relates to a broadcast. */
export type ResponseDisposition =
  | 'convergent'
  | 'divergent'
  | 'lateral'
  | 'silent'

/** A module's response to a workspace broadcast. */
export interface WorkspaceResponse {
  /** Which module produced this response */
  source: string
  /** How the module's context relates to the broadcast */
  disposition: ResponseDisposition
  /** The relevant context the module wants to surface */
  content: string
  /** Confidence in the response's relevance (0-1) */
  confidence: number
  /** Signal type of the returned context */
  type: SignalType
  /** When this response was produced */
  respondedAt: number
  /** Optional metadata for downstream tracing */
  metadata?: Record<string, unknown>
}

/** Handler invoked with the broadcast signals; returns a module response (may be null). */
export type WorkspaceResponseHandler = (
  broadcastSignals: CognitiveSignal[],
) => Promise<WorkspaceResponse | null> | WorkspaceResponse | null

/** A snapshot of the workspace's current state. */
export interface GlobalWorkspaceSnapshot {
  slots: WorkspaceSlot[]
  pendingCount: number
  totalSubmitted: number
  totalIgnited: number
  ignitionRate: number
  threshold: number
  tickCount: number
}

/** Unsubscribe handle returned by event subscription methods. */
export type Unsubscribe = () => void

/** The Global Workspace engine — capacity-limited attention + broadcast. */
export interface GlobalWorkspaceConfig {
  ignitionThreshold?: number
  capacity?: number
  urgencyDecayBase?: number
  [key: string]: unknown
}

/**
 * The Global Workspace engine — capacity-limited attention + broadcast.
 *
 * Faithful minimal runtime for helix's PostureModule seam: signals submitted
 * via `submit()` are ignition-scored against the threshold and queued; an
 * explicit `broadcast()` flushes the pending set to every `onBroadcast`
 * subscriber (each module filters for relevance in its overridden
 * `onWorkspaceBroadcast`). No luminance/coalition machinery — re-pointed to
 * `@cassicore/lamina` (workspace) at P5.
 */
export class GlobalWorkspace {
  private threshold: number
  private listeners: Array<(signals: CognitiveSignal[]) => void> = []
  private radiance: Array<{ source: string; handler: WorkspaceResponseHandler }> = []
  private pending: CognitiveSignal[] = []
  private slots: WorkspaceSlot[] = []
  private eventBus?: IEventBus
  private readonly signalIds = new Set<string>()
  private readonly logger?: unknown

  constructor(logger?: unknown, config: GlobalWorkspaceConfig = {}) {
    this.logger = logger
    this.threshold = config.ignitionThreshold ?? 0.5
    this.capacity = config.capacity ?? 8
    for (let i = 0; i < this.capacity; i++) this.slots.push({ signal: null })
  }

  private capacity: number

  /** Wire an event bus for telemetry (stored; no emissions in this stub). */
  setEventBus(bus: IEventBus): void {
    this.eventBus = bus
  }

  /** Submit a signal for competition. Returns true if it ignited. */
  submit(signal: CognitiveSignal): boolean {
    if (this.signalIds.has(signal.signalId)) return false
    this.signalIds.add(signal.signalId)
    const score = signal.luminance?.composite ?? 0
    const ignited = score >= this.threshold
    if (ignited) {
      this.pending.push(signal)
      // Emit the ignition to the event bus so telemetry can journal it.
      try {
        this.eventBus?.emit({
          type: 'workspace:ignition',
          source: signal.source,
          signalType: signal.type,
          signalId: signal.signalId,
          luminance: signal.luminance,
        } as any)
      } catch { /* best-effort */ }
    }
    return ignited
  }

  /** Flush pending signals to all broadcast subscribers. */
  broadcast(): void {
    const batch = this.pending
    this.pending = []
    if (batch.length === 0) return
    for (const cb of this.listeners) {
      try { cb(batch) } catch { /* best-effort */ }
    }
  }

  /** Subscribe to broadcasts. */
  onBroadcast(handler: (signals: CognitiveSignal[]) => void): Unsubscribe {
    this.listeners.push(handler)
    return () => {
      this.listeners = this.listeners.filter((h) => h !== handler)
    }
  }

  /** Register a radiance response handler for a source. */
  onRadiance(source: string, handler: WorkspaceResponseHandler): Unsubscribe {
    this.radiance.push({ source, handler })
    return () => {
      this.radiance = this.radiance.filter((r) => r.source !== source || r.handler !== handler)
    }
  }

  /** Snapshot the workspace's current state. */
  getSnapshot(): GlobalWorkspaceSnapshot {
    return {
      slots: [...this.slots],
      pendingCount: this.pending.length,
      totalSubmitted: 0,
      totalIgnited: 0,
      ignitionRate: 0,
      threshold: this.threshold,
      tickCount: 0,
    }
  }

  /** Return the most recently submitted signals, capped at `limit`. */
  getRecentSignals(limit: number): CognitiveSignal[] {
    return [...this.pending].slice(-limit)
  }
}
