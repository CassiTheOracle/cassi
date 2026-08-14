/** VENDORED TYPE STUB — mirrors `workspace/cognitive-signal.js`. Surface: CognitiveSignal, SignalType. */
export type SignalType =
  | 'anomaly'
  | 'insight'
  | 'concern'
  | 'decision'
  | 'finding'
  | string

export interface CognitiveSignal {
  signalId: string
  source: string
  sessionId: string
  type: SignalType
  content: string
  luminance?: Record<string, number>
  createdAt: number
  urgencyHint?: number
  metadata?: Record<string, unknown>
  [key: string]: unknown
}
