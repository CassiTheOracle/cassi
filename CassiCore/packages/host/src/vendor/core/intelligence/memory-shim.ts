/**
 * MemoryShim — Lightweight IMemory stub for backward compatibility
 *
 * REMOVED: The full MemoryModule (core/intelligence/memory/) is deleted.
 * This shim implements the IMemory interface with in-memory storage,
 * allowing existing callers to compile and run while they migrate to MnemicField.
 *
 * Migration path (Phase 5):
 *   - memory.search(query) → mnemicField.retrieve(query)
 *   - memory.store(entry) → mnemicField.spike() + engram creation
 *   - memory.kv_get/kv_set → Use LaminaField or MnemicField directly
 *   - memory.archive* → Use Archivist directly
 *
 * @deprecated Migrate callers to MnemicField/LaminaField directly. This shim will be removed.
 */

import type { IMemory, MemoryEntry, SearchOpts, SearchResult, SmartRecallOpts, SmartRecallResult } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
import type { Message } from '@cassicore/foundation'
import type { IndexEntry, IndexSearchResult } from '@cassicore/foundation'

export class MemoryShim implements IMemory {
  private readonly kvStore = new Map<string, unknown>()
  private readonly entries: MemoryEntry[] = []
  private nextId = 1
  private readonly logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child('memory-shim')
  }

  /** In-memory store — returns generated id */
  async store(entry: Omit<MemoryEntry, 'id' | 'createdAt'>): Promise<string> {
    const id = `shim-${this.nextId++}`
    const newEntry: MemoryEntry = {
      ...entry,
      id,
      createdAt: new Date(),
    } as MemoryEntry
    this.entries.push(newEntry)
    return id
  }

  /** In-memory search — basic substring match */
  async search(query: string, opts?: SearchOpts): Promise<SearchResult[]> {
    const limit = opts?.limit ?? 10
    const q = query.toLowerCase()
    const results = this.entries
      .filter(e => e.content?.toLowerCase()?.includes(q))
      .slice(0, limit)
      .map(e => ({
        entry: e,
        score: 0.5,
        confidence: 'moderate' as const,
      }))
    return results
  }

  /** Smart recall — not implemented */
  async smartRecall(): Promise<SmartRecallResult[]> {
    return []
  }

  /** In-memory KV store */
  async kv_get<T>(key: string): Promise<T | undefined> {
    return this.kvStore.get(key) as T | undefined
  }

  async kv_set(key: string, value: unknown): Promise<void> {
    this.kvStore.set(key, value)
  }

  async kv_del(key: string): Promise<void> {
    this.kvStore.delete(key)
  }

  async delete(): Promise<boolean> {
    return false
  }

  async pin(): Promise<boolean> {
    return false
  }

  async unpin(): Promise<boolean> {
    return false
  }

  /** Basic stats */
  async stats(): Promise<Record<string, number>> {
    return {
      totalEntries: this.entries.length,
      totalSearches: 0,
    }
  }

  // --- Archivist stubs (use Archivist directly) ---

  async archiveConversation(): Promise<{ id: string; analysis: any }> {
    return { id: 'shim', analysis: {} }
  }
  async archiveDialectic(): Promise<{ id: string; analysis: any }> {
    return { id: 'shim', analysis: {} }
  }
  async archiveInsight(): Promise<{ id: string; analysis: any }> {
    return { id: 'shim', analysis: {} }
  }
  async archivePattern(): Promise<{ id: string; analysis: any }> {
    return { id: 'shim', analysis: {} }
  }
  async archiveEvent(): Promise<{ id: string; analysis: any }> {
    return { id: 'shim', analysis: {} }
  }
  async archiveToolCall(): Promise<{ id: string; analysis: any }> {
    return { id: 'shim', analysis: {} }
  }
  async archiveDocument(): Promise<{ id: string; analysis: any }> {
    return { id: 'shim', analysis: {} }
  }

  getDb(): any {
    return undefined
  }

  // --- Session indexing stubs ---

  indexSession(): string {
    return 'shim'
  }
  indexIncremental(): string {
    return 'shim'
  }
  resolveRef(): IndexEntry[] {
    return []
  }
  searchIndex(query: string, opts?: { label?: string; sessionId?: string; limit?: number }): IndexSearchResult[] {
    return []
  }

  // --- Dreamer archive stub ---
  async archiveDream(): Promise<{ id: string; analysis: any }> {
    return { id: 'shim', analysis: {} }
  }

  // --- Turn history stubs (continuity adapter) ---

  async saveTurn(): Promise<string> {
    return 'shim'
  }

  async getRecentTurns(): Promise<any[]> {
    return []
  }

  async searchTurnHistory(): Promise<any[]> {
    return []
  }

  async pruneConversations(): Promise<void> {
    // no-op
  }

  // REMOVED: getArchivist — MemoryModule archivist deleted.
  getArchivist(): undefined {
    return undefined
  }
}

/** Create a MemoryShim instance */
export function createMemoryShim(logger: ILogger): MemoryShim {
  return new MemoryShim(logger)
}