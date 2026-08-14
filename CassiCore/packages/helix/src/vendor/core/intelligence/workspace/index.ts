/**
 * VENDORED TYPE STUB — mirrors `workspace/index.js` surface: GlobalWorkspace,
 * CognitiveSignal, SignalType (the unit of competition for Global Workspace
 * Theory). Helix publishes CognitiveSignals into the GlobalWorkspace and
 * subscribes to broadcasts. Self-contained: single file.
 */

export type SignalType =
  | 'observation'
  | 'tension'
  | 'insight'
  | 'suggestion'
  | 'warning'
  | 'bridge'
  | 'work-unit'
  | 'finding'
  | 'challenge'
  | 'concern'
  | 'anomaly'
  | 'decision'
  | string

/** The unit of competition for the capacity-limited broadcast medium. */
export interface CognitiveSignal {
  signalId: string
  /** Semantic kind inside the SignalType (e.g. 'work-unit', 'finding'). */
  type: SignalType
  /** Human-readable content. */
  content: string
  /** Origin module / posture id. */
  source: string
  /** Session scope ('*' broadcasts to all sessions). */
  sessionId: string
  /** Luminance score — composite drives ignition. */
  luminance?: { composite?: number; [key: string]: unknown }
  /** Extra urgency beyond the SignalType baseline (0-1). */
  urgencyHint?: number
  /** Creation timestamp. */
  createdAt: number
  /** Additional metadata merged into the published signal. */
  metadata?: Record<string, unknown>
  [key: string]: unknown
}

/** A signal submitted/accepted into a workspace slot. */
export type WorkspaceSlot = CognitiveSignal | null

export interface GlobalWorkspaceConfig {
  capacity?: number
  urgencyDecayBase?: number
  [key: string]: unknown
}

export interface WorkspaceResponse {
  content: string
  [key: string]: unknown
}

/**
 * Global Workspace — the broadcast engine (Global Workspace Theory) Helix
 * postures publish into and subscribe to.
 */
export interface GlobalWorkspace {
  /** Submit a signal for ignition; true if it entered the workspace. */
  submit(signal: CognitiveSignal): boolean
  /** Subscribe to broadcasts; returns an unsubscribe function. */
  onBroadcast(handler: (signals: CognitiveSignal[]) => void): () => void
  /** Subscribe to a named radiance/observer stream. */
  onRadiance(name: string, handler: (signals: CognitiveSignal[]) => unknown): () => void
  /** Broadcast a signal directly (author + salience form). */
  broadcast(signal: { type: string; content: string; author: string; salience: number }): void
  /** Return the most recent signals, capped at `limit`. */
  getRecentSignals(limit?: number): Array<{ type: string; content: string; author: string; timestamp: number }>
  /** Snapshot the workspace threshold and occupied slots. */
  getSnapshot(): { threshold: number; slots: WorkspaceSlot[] }
  [key: string]: unknown
}
