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
  private constellationEngramId: string | undefined
  private branchEngramIds = new Map<string, string>()

  constructor(field: MnemicField, logger: ILogger) {
    this.field = field
    this.logger = logger.child('mnemic-locus-memory')
  }

  setConstellationEngramId(id: string): void {
    this.constellationEngramId = id
  }

  setBranchEngramIds(ids: Map<string, string>): void {
    this.branchEngramIds = new Map(ids)
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
      const existing = this.field.get(entry.id)
      if (existing) {
        this.updateMemory(entry)
      } else {
        this.field.store({
          id: entry.id,
          nodeType: MEMORY_NODE_TYPE,
          content: entry.content,
          tags: [MEMORY_TAG, `phase:${entry.phase}`],
          provenance: `constellation:${entry.originSessionId}`,
          metadata: entryToMetadata(entry),
        })
      }

      // Connect memory to parent constellation and source branch via edges
      // so it's reachable via graph propagation from related engrams.
      this.connectMemoryEdges(entry)
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

  private connectMemoryEdges(entry: LocusMemoryEntry): void {
    if (!this.constellationEngramId && this.branchEngramIds.size === 0) return

    try {
      if (this.constellationEngramId) {
        this.field.connect({
          sourceId: entry.id,
          targetId: this.constellationEngramId,
          edgeType: 'spawned_from',
          weight: 0.6,
          metadata: { provenance: 'locus-memory' },
        })
      }
      const branchId = this.branchEngramIds.get(entry.sourceHelixId)
      if (branchId) {
        this.field.connect({
          sourceId: entry.id,
          targetId: branchId,
          edgeType: 'part_of',
          weight: 0.6,
          metadata: { provenance: 'locus-memory' },
        })
      }

      this.logger.info('Connected memory via edges', {
        memoryId: entry.id,
        constellationEdge: Boolean(this.constellationEngramId),
        branchEdge: Boolean(branchId),
      })
    } catch (err) {
      this.logger.debug('Failed to connect memory edges', {
        memoryId: entry.id,
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
