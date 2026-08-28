/**
 * VENDOR TYPE STUB — `core/intelligence/workspace/index.ts`
 *
 * Type-only placeholder for the Global Workspace surface consumed by the P1 live-set
 * (`base/cognitive-module.ts`): `GlobalWorkspace`, `CognitiveSignal`, `SignalType`,
 * `WorkspaceResponse`. Self-contained; builtin types only; no runtime.
 * KEPT LOCAL (not re-pointed to @cassicore/workspace): foundation is the P1 shared
 * substrate and must not declare an upward dependency on the P5 workspace package
 * (substrate-inversion rule — see DreamerConfig fix 6694b52 / PhrasePrototypeSet 18d105c).
 * Downstream consumers (helix/constellation) re-point to the real @cassicore/workspace.
 */

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

/**
 * Trait vector of a signal's publisher.
 * Shape matches @cassicore/workspace's cognitive-signal.ts TraitVector (C-POLY-1);
 * aligned so downstream consumers that mix real-workspace types with foundation's
 * BaseCognitiveModule boundary types stay structurally compatible.
 */
export interface TraitVector {
  /** Structural: emphasis on organization, architecture, modularity */
  structural: number
  /** Pragmatic: emphasis on code that works, tests pass, ship it */
  pragmatic: number
  /** Generative: emphasis on exploration, alternatives, creativity */
  generative: number
  /** Analytical: emphasis on rigor, correctness, edge cases */
  analytical: number
  /** Collaborative: emphasis on Yang/Yin dialectic, synthesis */
  collaborative: number
  /** Adaptive: emphasis on flexibility, iteration, learning */
  adaptive: number
  /** Decisive: emphasis on choosing, committing, forward progress */
  decisive: number
  /** Focused: emphasis on depth, thoroughness, completeness */
  focused: number
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
export class GlobalWorkspace {
  /** Submit a signal for competition. Returns true if it ignited. */
  submit(signal: CognitiveSignal): boolean {
    throw new Error('vendor stub: no runtime implementation')
  }

  /** Subscribe to broadcasts. */
  onBroadcast(handler: (signals: CognitiveSignal[]) => void): Unsubscribe {
    throw new Error('vendor stub: no runtime implementation')
  }

  /** Register a radiance response handler for a source. */
  onRadiance(source: string, handler: WorkspaceResponseHandler): Unsubscribe {
    throw new Error('vendor stub: no runtime implementation')
  }

  /** Snapshot the workspace's current state. */
  getSnapshot(): GlobalWorkspaceSnapshot {
    throw new Error('vendor stub: no runtime implementation')
  }
}
