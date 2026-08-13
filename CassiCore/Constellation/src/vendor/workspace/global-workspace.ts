/** VENDORED TYPE STUB — mirrors `workspace/global-workspace.js`. Surface: GlobalWorkspace, CognitiveSignal, SignalType, WorkspaceResponse. */
import type { CognitiveSignal, SignalType } from './cognitive-signal.js'
export type { CognitiveSignal, SignalType }

export interface GlobalWorkspace {
  submit(signal: CognitiveSignal): boolean
  onBroadcast(handler: (signals: CognitiveSignal[]) => void): () => void
  onRadiance(name: string, handler: (signals: CognitiveSignal[]) => unknown): () => void
  getSnapshot(): { threshold: number; slots: Array<{ signal: CognitiveSignal | null }> }
  [key: string]: unknown
}

export interface WorkspaceResponse {
  content: string
  [key: string]: unknown
}
