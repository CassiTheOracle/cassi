/**
 * VENDORED TYPE STUB — mirrors `types/intelligence.js` (CassiCore).
 * Surface used by constellation: IMemory, SearchResult.
 */

export interface MemoryEntry {
  id?: string
  type?: string
  content: string
  metadata?: Record<string, unknown>
  timestamp?: number
  createdAt?: Date
  importance?: number
  tags?: string[]
  sessionId?: string
  pinned?: boolean
  [key: string]: unknown
}

/** A stored memory returned by `IMemory.search`/`getRecent` — createdAt is always present. */
export interface StoredMemoryEntry {
  id: string
  type: string
  content: string
  metadata?: Record<string, unknown>
  timestamp?: number
  createdAt: Date
  importance?: number
  tags?: string[]
  sessionId?: string
  pinned?: boolean
  [key: string]: unknown
}

export interface SearchResult {
  id?: string
  content: string
  score: number
  entry: StoredMemoryEntry
  metadata?: Record<string, unknown>
  [key: string]: unknown
}

export interface IMemory {
  store(entry: MemoryEntry): Promise<string | undefined>
  search(query: string, opts?: { limit?: number; [key: string]: unknown }): Promise<SearchResult[]>
  [key: string]: unknown
}
