/**
 * VENDORED TYPE STUB — mirrors `mnemic-field/self-model/inter-field-bridge.js` (CassiCore).
 * Surface used by meditation/self-modeling-synthesis.
 */
export interface PortalStatsEntry {
  concept: string
  episodicConnections: number
  selfModelConnections: number
}

export interface InterFieldBridge {
  seedEpisodicLinks(limit?: number): number
  getPortalStats(): PortalStatsEntry[]
  [key: string]: unknown
}
