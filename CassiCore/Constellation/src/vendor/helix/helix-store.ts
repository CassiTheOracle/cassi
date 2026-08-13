/**
 * VENDORED TYPE STUB — mirrors `helix/helix-store.js`. Surface: HelixStore + the getSession
 * session-record shape the constellation pipeline reads for token accounting.
 */
export interface HelixSessionRecord {
  sessionId: string
  tokensUnity?: number
  tokensYang?: number
  tokensYin?: number
  tokensMentor?: number
  [key: string]: unknown
}

export interface HelixStore {
  getSession(sessionId: string): HelixSessionRecord | undefined
  [key: string]: unknown
}
