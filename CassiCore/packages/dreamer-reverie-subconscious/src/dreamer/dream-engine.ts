/**
 * Dream Engine — Core dream cycle state machine.
 *
 * Receives injected inference functions and the MemoryModule so it can
 * be tested in isolation without a running daemon or real LLM.
 */

import type { ILogger } from '@cassicore/foundation'
// REMOVED: MemoryModule import — deleted. DreamEngine now uses IMemory with optional methods.
import type { IMemory } from '@cassicore/foundation'

/** Minimal ArchiveEntry shape for dream engine */
interface ArchiveEntry {
  id: string
  content: string
  type: string
  createdAt: number
  metadata?: Record<string, unknown>
}
import type { ReasoningBank } from '../../vendor/core/intelligence/reasoning-bank/index.js'
import type { SearchResult } from '../../vendor/core/intelligence/reasoning-bank/types.js'
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
    private readonly memory: IMemory & { sampleForDream?(opts: any): any[]; archiveDream?(content: string, metadata: any): void },
    private readonly logger: ILogger,
    private readonly reasoningBank?: ReasoningBank,
  ) {}

  /**
   * Run a complete dream cycle.
   * Returns a DreamRecord describing everything that was created/retired.
   */
  async runCycle(config: DreamerConfig): Promise<DreamRecord> {
    const startedAt = Date.now()
    const dreamId = `dream_${startedAt}_${Math.random().toString(36).slice(2, 6)}`

    this.logger.info('[DreamEngine] Starting dream cycle', { dreamId })

    // REMOVED: MemoryModule methods — cast to any for backward compat. MemoryShim skips dream cycles.
    const memoryAny = this.memory as any
    const entries = memoryAny.sampleForDream({
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
        const memId = await memoryAny.store({
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

    // Phase 4: Reasoning Synthesis — cross-pollinate dream insights with reasoning traces
    let reasoningSynthesesCount = 0
    if (this.reasoningBank && insights.length > 0) {
      try {
        reasoningSynthesesCount = await this.synthesizeWithReasoningBank(dreamId, insights)
      } catch (err) {
        this.logger.warn('[DreamEngine] Reasoning synthesis phase failed (non-fatal)', { error: String(err) })
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

    memoryAny.markArchiveEntriesDreamed(entries.map((e: any) => e.id))

    const completedAt = Date.now()
    const topInsight = insights.sort((a, b) => b.confidence - a.confidence)[0]
    const record: DreamRecord = {
      id: dreamId,
      startedAt,
      completedAt,
      durationMs: completedAt - startedAt,
      archiveEntriesProcessed: entries.map((e: any) => e.id),
      insightsCreated: insightMemoryIds,
      episodicsRetired,
      linksCreated,
      reasoningSyntheses: reasoningSynthesesCount,
      rawAnalysis: freeAssociation.slice(0, 2000),
      topInsightContent: topInsight?.content,
    }

    this.logger.info('[DreamEngine] Dream cycle complete', {
      dreamId,
      durationMs: record.durationMs,
      insightsCreated: insightMemoryIds.length,
      episodicsRetired: episodicsRetired.length,
      linksCreated,
      reasoningSyntheses: reasoningSynthesesCount,
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
   * Phase 4: Reasoning Synthesis — find reasoning traces related to dream insights,
   * synthesize cross-session meta-reasoning, and store it back into the Reasoning Bank.
   *
   * HOW: For each dream insight, search the Reasoning Bank for traces with overlapping
   * goals or files. When multiple traces relate to the same insight, synthesize a
   * meta-observation about what approach patterns tend to succeed. This creates
   * 'dream-synthesis' traces that capture cross-session wisdom.
   */
  private async synthesizeWithReasoningBank(
    dreamId: string,
    insights: DreamInsight[],
  ): Promise<number> {
    if (!this.reasoningBank) return 0

    // Collect relevant reasoning traces for each insight
    const insightTraces: Array<{ insight: DreamInsight; traces: SearchResult[] }> = []

    for (const insight of insights) {
      // Search by insight topics and content keywords
      const searchTerms = [
        ...(insight.topics ?? []),
        ...(insight.title ? [insight.title] : []),
      ].filter(Boolean).join(' ')

      if (!searchTerms) continue

      const traces = this.reasoningBank.search({
        query: searchTerms,
        minQuality: 0.6,
        successOnly: true,
        limit: 5,
      })

      if (traces.length >= 2) {
        insightTraces.push({ insight, traces })
      }
    }

    if (insightTraces.length === 0) {
      this.logger.debug('[DreamEngine] No reasoning traces found for synthesis')
      return 0
    }

    // Synthesize meta-reasoning from traces that overlap with dream insights
    let stored = 0
    for (const { insight, traces } of insightTraces) {
      const tracesSummary = traces.map(t =>
        `[${t.trace.approach}] goal: "${t.trace.goal.slice(0, 100)}" — quality: ${t.trace.qualityScore.toFixed(2)}, ` +
        `files: ${t.trace.relevantFiles.slice(0, 3).join(', ')}`
      ).join('\n')

      const prompt = `You are an AI analyzing patterns across multiple coding sessions.

A dream insight was formed:
"${insight.content}"
${insight.title ? `Title: "${insight.title}"` : ''}
${insight.topics?.length ? `Topics: ${insight.topics.join(', ')}` : ''}

Related successful reasoning traces from past sessions:
${tracesSummary}

Synthesize a concise meta-observation (2-3 sentences) about what approach patterns tend to succeed for this type of work. Focus on actionable guidance that would help a future session.

Return JSON: { "synthesis": "...", "approach_pattern": "...", "applicable_context": "..." }`

      try {
        const result = await this.inferJSONFn<{
          synthesis?: string
          approach_pattern?: string
          applicable_context?: string
        }>(prompt)

        if (result?.synthesis && result.synthesis.length > 20) {
          this.reasoningBank.store({
            sourceHelixId: `dream-${dreamId}`,
            goal: insight.title ?? insight.content.slice(0, 100),
            approach: result.approach_pattern ?? 'dream-synthesis',
            content: result.synthesis,
            qualityScore: Math.min(insight.confidence + 0.1, 1.0),
            succeeded: true,
            relevantFiles: traces.flatMap(t => t.trace.relevantFiles).filter((v, i, a) => a.indexOf(v) === i).slice(0, 10),
            taskType: 'general',
          })
          stored++
          this.logger.debug('[DreamEngine] Stored reasoning synthesis', {
            dreamId,
            approach: result.approach_pattern,
            traceCount: traces.length,
          })
        }
      } catch (err) {
        this.logger.debug('[DreamEngine] Reasoning synthesis LLM call failed', { error: String(err) })
      }
    }

    return stored
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
    const memAny = this.memory as any
    const episodics = memAny.getEpisodicMemoriesByIds
      ? memAny.getEpisodicMemoriesByIds(candidateIds)
      : []

    if (episodics.length < minClusterSize) return []

    const prompt = buildGardenPrompt(
      episodics.map((e: any) => ({ id: e.id, content: e.content, createdAt: e.createdAt })),
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
      const validIds = ids.filter((id: string) => episodics.some((e: any) => e.id === id))
      if (validIds.length >= minClusterSize) {
        const reasoning = typeof cluster.reasoning === 'string' ? cluster.reasoning : 'distilled by dreamer'
        memAny.archiveDeep(validIds, reasoning)
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
