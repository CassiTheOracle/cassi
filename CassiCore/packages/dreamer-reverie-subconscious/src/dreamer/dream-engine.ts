/**
 * Dream Engine — Core dream cycle state machine.
 *
 * Receives injected inference functions and the MemoryModule so it can
 * be tested in isolation without a running daemon or real LLM.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { ArchiveEntry } from '../memory/archivist.js'
import type { MemoryModule } from '../memory/index.js'
import {
  buildFreeAssociationPrompt,
  buildCrystallizationPrompt,
  buildGardenPrompt,
} from './dream-prompt.js'
import type { DreamInsight, DreamRecord, DreamerConfig } from './types.js'


export type InferFn = (prompt: string) => Promise<string>
export type InferJSONFn = <T>(prompt: string) => Promise<T | null>


interface RawInsight {
  content?: unknown
  confidence?: unknown
  sourceEntryIds?: unknown
  title?: unknown
  topics?: unknown
}

interface RawCluster {
  episodicIds?: unknown
  reasoning?: unknown
}


export class DreamCycleEngine {
  constructor(
    private readonly inferFn: InferFn,
    private readonly inferJSONFn: InferJSONFn,
    private readonly memory: MemoryModule,
    private readonly logger: ILogger,
  ) {}

  /**
   * Run a complete dream cycle.
   * Returns a DreamRecord describing everything that was created/retired.
   */
  async runCycle(config: DreamerConfig): Promise<DreamRecord> {
    const startedAt = Date.now()
    const dreamId = `dream_${startedAt}_${Math.random().toString(36).slice(2, 6)}`

    this.logger.info('[DreamEngine] Starting dream cycle', { dreamId })

    const entries = this.memory.sampleForDream({
      sampleSize: config.archiveSampleSize,
      recentWindowHours: config.recentWindowHours,
      lookbackDays: config.archiveLookbackDays,
    })

    if (entries.length === 0) {
      this.logger.info('[DreamEngine] No archive entries to dream about — skipping', { dreamId })
      return this.emptyRecord(dreamId, startedAt, entries)
    }

    this.logger.debug('[DreamEngine] Sampled archive entries', { count: entries.length })

    const freeAssociation = await this.freeAssociate(entries)

    const insights = await this.crystallize(freeAssociation, entries, config.maxInsightsPerDream)

    const insightMemoryIds: string[] = []
    for (const insight of insights) {
      try {
        const memId = await this.memory.store({
          type: 'insight',
          content: insight.content,
          metadata: {
            source: 'dreamer',
            dreamId,
            title: insight.title,
            confidence: insight.confidence,
            topics: insight.topics,
            sourceEntryIds: insight.sourceEntryIds,
          },
        })
        insightMemoryIds.push(memId)
        this.logger.debug('[DreamEngine] Stored dream insight', { memId, title: insight.title })
      } catch (err) {
        this.logger.warn('[DreamEngine] Failed to store insight', { error: String(err) })
      }
    }

    const episodicsRetired: string[] = []
    if (config.enableGardening && insights.length > 0) {
      try {
        episodicsRetired.push(...await this.garden(insights, config.minClusterSizeForGarden))
      } catch (err) {
        this.logger.warn('[DreamEngine] Gardening phase failed (non-fatal)', { error: String(err) })
      }
    }

    let linksCreated = 0
    if (config.enableLinking) {
      try {
        linksCreated = this.createLinks(entries, insights)
      } catch (err) {
        this.logger.warn('[DreamEngine] Linking phase failed (non-fatal)', { error: String(err) })
      }
    }

    this.memory.markArchiveEntriesDreamed(entries.map(e => e.id))

    const completedAt = Date.now()
    const topInsight = insights.sort((a, b) => b.confidence - a.confidence)[0]
    const record: DreamRecord = {
      id: dreamId,
      startedAt,
      completedAt,
      durationMs: completedAt - startedAt,
      archiveEntriesProcessed: entries.map(e => e.id),
      insightsCreated: insightMemoryIds,
      episodicsRetired,
      linksCreated,
      rawAnalysis: freeAssociation.slice(0, 2000),
      topInsightContent: topInsight?.content,
    }

    this.logger.info('[DreamEngine] Dream cycle complete', {
      dreamId,
      durationMs: record.durationMs,
      insightsCreated: insightMemoryIds.length,
      episodicsRetired: episodicsRetired.length,
      linksCreated,
    })

    return record
  }


  /**
   * Phase 2: Free association — asks LLM to find connections across sampled entries.
   */
  async freeAssociate(entries: ArchiveEntry[]): Promise<string> {
    const prompt = buildFreeAssociationPrompt(entries)
    try {
      return await this.inferFn(prompt)
    } catch (err) {
      this.logger.warn('[DreamEngine] Free association LLM call failed', { error: String(err) })
      return `[Dream analysis unavailable: ${String(err)}]`
    }
  }

  /**
   * Phase 3: Crystallization — distill free-association into structured insights.
   */
  async crystallize(
    freeAssociation: string,
    entries: ArchiveEntry[],
    maxInsights: number,
  ): Promise<DreamInsight[]> {
    const prompt = buildCrystallizationPrompt(freeAssociation, entries, maxInsights)
    try {
      const raw = await this.inferJSONFn<RawInsight[]>(prompt)
      if (!Array.isArray(raw)) return []
      return raw
        .filter(r => typeof r?.content === 'string' && r.content.length > 10)
        .slice(0, maxInsights)
        .map(r => ({
          content: String(r.content),
          confidence: typeof r.confidence === 'number' ? Math.min(1, Math.max(0, r.confidence)) : 0.5,
          sourceEntryIds: Array.isArray(r.sourceEntryIds) ? r.sourceEntryIds.map(String) : [],
          title: typeof r.title === 'string' ? r.title : undefined,
          topics: Array.isArray(r.topics) ? r.topics.map(String) : [],
        }))
    } catch (err) {
      this.logger.warn('[DreamEngine] Crystallization LLM call failed', { error: String(err) })
      return []
    }
  }

  /**
   * Phase 5: Gardening — find episodic memory clusters safe to retire.
   * Returns the memory IDs of retired episodics.
   */
  private async garden(insights: DreamInsight[], minClusterSize: number): Promise<string[]> {
    // Collect all candidate memory IDs mentioned in insight source references
    // and look up their episodic memories in the active garden
    const candidateIds = [...new Set(insights.flatMap(i => i.sourceEntryIds))]

    // sourceEntryIds are archive entry IDs, not memory IDs — we need episodic
    // memory entries that are thematically similar. Query recent episodic memories.
    const episodics = this.memory.getEpisodicMemoriesByIds
      ? this.memory.getEpisodicMemoriesByIds(candidateIds)
      : []

    if (episodics.length < minClusterSize) return []

    const prompt = buildGardenPrompt(
      episodics.map(e => ({ id: e.id, content: e.content, createdAt: e.createdAt })),
      insights,
      minClusterSize,
    )

    const raw = await this.inferJSONFn<RawCluster[]>(prompt)
    if (!Array.isArray(raw)) return []

    const allRetiredIds: string[] = []
    for (const cluster of raw) {
      const ids = Array.isArray(cluster?.episodicIds) ? cluster.episodicIds.map(String) : []
      if (ids.length < minClusterSize) continue
      // Verify all IDs exist in our episodic list (guard against hallucination)
      const validIds = ids.filter(id => episodics.some(e => e.id === id))
      if (validIds.length >= minClusterSize) {
        const reasoning = typeof cluster.reasoning === 'string' ? cluster.reasoning : 'distilled by dreamer'
        this.memory.archiveDeep(validIds, reasoning)
        allRetiredIds.push(...validIds)
      }
    }

    return allRetiredIds
  }

  /**
   * Phase 6: Create conceptual links between archive entries.
   * Returns the number of links created.
   */
  private createLinks(entries: ArchiveEntry[], insights: DreamInsight[]): number {
    // Create links between entries that were co-cited in the same insight
    let created = 0
    for (const insight of insights) {
      const ids = insight.sourceEntryIds
      if (ids.length < 2) continue
      // Link each pair of co-cited entries
      for (let i = 0; i < ids.length - 1; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          try {
            const sourceId = ids[i]
            const targetId = ids[j]
            // Use the archivist's link method if available
            const archivist = (this.memory as any).archivist
            if (archivist?.linkEntries) {
              archivist.linkEntries(sourceId, targetId, 'related', insight.confidence)
              created++
            }
          } catch { /* best effort */ }
        }
      }
    }
    return created
  }


  private emptyRecord(id: string, startedAt: number, entries: ArchiveEntry[]): DreamRecord {
    const completedAt = Date.now()
    return {
      id,
      startedAt,
      completedAt,
      durationMs: completedAt - startedAt,
      archiveEntriesProcessed: entries.map(e => e.id),
      insightsCreated: [],
      episodicsRetired: [],
      linksCreated: 0,
    }
  }
}
