import type { MnemicField, Engram } from '../../mnemic-field/index.js'
import type { ILogger } from '../../../../types/interfaces.js'
import type { LocusMemoryPersistence } from './constellation-memory.js'
import type { LocusMemoryEntry } from './memory-types.js'

const MEMORY_PREFIX = 'lmem-'
const MEMORY_NODE_TYPE = 'pattern'
const MEMORY_TAG = 'locus-memory'

export class MnemicLocusMemoryPersistence implements LocusMemoryPersistence {
  private field: MnemicField
  private logger: ILogger

  constructor(field: MnemicField, logger: ILogger) {
    this.field = field
    this.logger = logger.child('mnemic-locus-memory')
  }

  loadMemories(): LocusMemoryEntry[] {
    try {
      const engrams = this.field.getEngramsByIdPrefix(MEMORY_PREFIX)
      const entries: LocusMemoryEntry[] = []
      for (const e of engrams) {
        const entry = engramToMemory(e)
        if (entry) entries.push(entry)
      }
      this.logger.debug('Loaded locus memories from MnemicField', { count: entries.length })
      return entries
    } catch (err) {
      this.logger.warn('Failed to load locus memories from MnemicField', { error: String(err) })
      return []
    }
  }

  saveMemory(entry: LocusMemoryEntry): void {
    try {
      this.field.store({
        id: entry.id,
        nodeType: MEMORY_NODE_TYPE,
        content: entry.content,
        tags: [MEMORY_TAG, `phase:${entry.phase}`],
        provenance: `constellation:${entry.originSessionId}`,
        metadata: entryToMetadata(entry),
      })
      this.logger.debug('Saved locus memory to MnemicField', {
        memoryId: entry.id,
        phase: entry.phase,
      })
    } catch (err) {
      this.logger.warn('Failed to save locus memory to MnemicField', {
        memoryId: entry.id,
        error: String(err),
      })
    }
  }

  updateMemory(entry: LocusMemoryEntry): void {
    try {
      this.field.update(entry.id, {
        content: entry.content,
        tags: [MEMORY_TAG, `phase:${entry.phase}`],
        metadata: entryToMetadata(entry),
      })
      this.logger.debug('Updated locus memory in MnemicField', {
        memoryId: entry.id,
        phase: entry.phase,
        confidence: entry.confidence.toFixed(3),
      })
    } catch (err) {
      this.logger.warn('Failed to update locus memory in MnemicField', {
        memoryId: entry.id,
        error: String(err),
      })
    }
  }

  deleteMemory(id: string): void {
    try {
      this.field.delete(id)
      this.logger.debug('Deleted locus memory from MnemicField', { memoryId: id })
    } catch (err) {
      this.logger.warn('Failed to delete locus memory from MnemicField', {
        memoryId: id,
        error: String(err),
      })
    }
  }
}

function entryToMetadata(entry: LocusMemoryEntry): Record<string, unknown> {
  return {
    memoryType: entry.memoryType,
    confidence: entry.confidence,
    luminance: entry.luminance,
    phase: entry.phase,
    originSessionId: entry.originSessionId,
    sourceHelixId: entry.sourceHelixId,
    sourceGoal: entry.sourceGoal,
    relevantFiles: entry.relevantFiles,
    confirmations: entry.confirmations,
    contradictions: entry.contradictions,
    recallCount: entry.recallCount,
    createdAt: entry.createdAt,
    lastRecalledAt: entry.lastRecalledAt,
    lastUpdatedAt: entry.lastUpdatedAt,
  }
}

function engramToMemory(engram: Engram): LocusMemoryEntry | null {
  const m = engram.metadata as Record<string, unknown> | undefined
  if (!m || typeof m.confidence !== 'number') return null

  return {
    id: engram.id,
    content: engram.content,
    memoryType: (m.memoryType as LocusMemoryEntry['memoryType']) ?? 'observation',
    confidence: m.confidence as number,
    luminance: (m.luminance as number) ?? 0,
    phase: (m.phase as LocusMemoryEntry['phase']) ?? 'provisional',
    originSessionId: (m.originSessionId as string) ?? '',
    sourceHelixId: (m.sourceHelixId as string) ?? '',
    sourceGoal: (m.sourceGoal as string) ?? '',
    relevantFiles: (m.relevantFiles as string[]) ?? [],
    confirmations: (m.confirmations as number) ?? 0,
    contradictions: (m.contradictions as number) ?? 0,
    recallCount: (m.recallCount as number) ?? 0,
    createdAt: (m.createdAt as number) ?? Date.now(),
    lastRecalledAt: (m.lastRecalledAt as number | null) ?? null,
    lastUpdatedAt: (m.lastUpdatedAt as number) ?? Date.now(),
  }
}
