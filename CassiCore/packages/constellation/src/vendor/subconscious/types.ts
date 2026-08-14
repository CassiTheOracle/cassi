/** VENDORED TYPE STUB — mirrors `subconscious/types.js`. Surface: Observation, Anomaly. */
export interface Observation {
  patterns: string[]
  summary: string
  confidence: number
  relatedEventTypes: string[]
  timestamp: number
  sessionId?: string
  [key: string]: unknown
}

export interface Anomaly {
  description: string
  severity?: string
  suggestedAction?: string
  eventTypes: string[]
  timestamp: number
  sessionId?: string
  [key: string]: unknown
}
