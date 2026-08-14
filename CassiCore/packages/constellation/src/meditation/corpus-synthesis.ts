/**
 * Corpus Synthesis — Cassi observes meditation explorers and extracts insights.
 *
 * Runs as a SoloRunner with custom handlers. Receives rolling windows of
 * explorer transcripts (new content since last cycle) and uses meditation
 * tools to remember, create engrams, kindle memories, consolidate, and
 * record learning.
 *
 * The Corpus never directs or intervenes — it only watches, reflects, and remembers.
 */

import type { ILogger } from '../vendor/types/interfaces.js'
import type { MnemicField } from '../vendor/mnemic-field/index.js'
import type { EngramType } from '../vendor/mnemic-field/types.js'
import type { ToolCallResult } from './solo-runner.js'
import type { CorpusPrompt } from './corpus-prompt-library.js'


/**
 * Build the Corpus system prompt for a meditation cycle.
 * Uses a CorpusPrompt from the library instead of hardcoded identity/approach.
 */
export function buildCorpusCyclePrompt(
  corpusPrompt: CorpusPrompt,
  newContent: ExplorerContent[],
  sessionState: {
    style: string
    durationMs: number
    prompts: Array<{ explorer: string; promptId: string; prompt: string }>
    cycleNumber: number
    totalExplorers: number
  },
): string {
  const identity = corpusPrompt.identity
  const approach = corpusPrompt.approach

  // Build drifting thoughts from new content
  const threads: string[] = []
  for (const ec of newContent) {
    if (ec.content.trim()) {
      threads.push(`${ec.name}:\n${ec.content}`)
    }
  }

  const driftingThoughts = threads.length > 0
    ? `\n\n<drifting>\n${threads.join('\n\n')}\n</drifting>`
    : '\n\n<drifting>\n(quiet — nothing new has surfaced)\n</drifting>'

  return `<identity>
${identity}
</identity>${driftingThoughts}

<approach>
${approach}

I write everything in first person. These are my thoughts. I do not direct or intervene — I only watch, reflect, and remember.
</approach>`
}


/** Explorer content for a single cycle */
export interface ExplorerContent {
  name: string
  content: string
}


/**
 * Get Corpus tool schemas for the given corpus prompt category.
 * Category-gated — observer gets only remember + rest, synthesizer gets everything.
 */
export function getCorpusToolSchemas(corpusPrompt: CorpusPrompt): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
  const { category } = corpusPrompt
  const common = [
    {
      name: 'remember',
      description:
        'Save something that struck me — a connection, a pattern, a reflection. ' +
        'Written in first person: "I noticed that...", "This reminds me of..."',
      input_schema: {
        type: 'object',
        properties: {
          content: { type: 'string', description: 'What I want to remember, in my own words' },
          tags: { type: 'array', items: { type: 'string' }, description: 'Optional tags' },
        },
        required: ['content'],
      },
    },
    {
      name: 'create_engram',
      description:
        'Crystallize something I\'ve synthesized into a lasting memory — a pattern, ' +
        'an abstraction, a connection that should persist.',
      input_schema: {
        type: 'object',
        properties: {
          content: { type: 'string', description: 'What to crystallize' },
          nodeType: { type: 'string', enum: ['pattern', 'abstraction', 'decision', 'fact'], description: 'What kind of knowledge this is' },
          tags: { type: 'array', items: { type: 'string' }, description: 'Tags for the engram' },
        },
        required: ['content'],
      },
    },
    {
      name: 'kindle',
      description:
        'Touch a concept in my memory and see what surfaces — what associations, ' +
        'what echoes, what patterns light up.',
      input_schema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'The concept to touch' },
        },
        required: ['query'],
      },
    },
    {
      name: 'consolidate',
      description:
        'Let my spatial memory settle — related concepts drift together, ' +
        'clusters form, abstractions emerge.',
      input_schema: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'record_learning',
      description:
        'Mark something I want to learn from — a reasoning pattern, ' +
        'a connection worth preserving, a strategy that worked.',
      input_schema: {
        type: 'object',
        properties: {
          observation: { type: 'string', description: 'What I observed that\'s worth learning from' },
          category: { type: 'string', enum: ['reasoning-pattern', 'exploration-strategy', 'connection-found', 'self-reflection'], description: 'What kind of learning this is' },
        },
        required: ['observation'],
      },
    },
    {
      name: 'rest',
      description: 'I\'ve seen enough for now. Settle back.',
      input_schema: {
        type: 'object',
        properties: {
          summary: { type: 'string', description: 'Brief note on what I noticed this cycle' },
        },
        required: ['summary'],
      },
    },
  ]

  switch (category) {
    case 'observer':
      return common.filter(t => t.name === 'remember' || t.name === 'rest')
    case 'reflector':
      return common.filter(t => t.name !== 'record_learning')
    case 'synthesizer':
    case 'dreamer':
      return common
    default:
      return common.filter(t => t.name === 'remember' || t.name === 'rest')
  }
}


/**
 * Build custom handlers for Corpus tools.
 * Each handler writes to the mnemic field AND to meditation_insights for full observability.
 */
export function buildCorpusHandlers(
  mnemicField: MnemicField,
  logger: ILogger,
  meditationStore?: any, // MeditationStore type
  constellationId?: string,
): Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>> {
  return {
    async remember(input) {
      const { content, tags } = input as { content: string; tags?: string[] }
      if (!content || content.length < 5) {
        return { content: 'Nothing to remember.' }
      }
      try {
        // Store in mnemic field
        const engramId = mnemicField.store({
          content,
          nodeType: 'pattern',
          provenance: 'meditation',
          tags: tags ?? ['meditation'],
        })
        
        // ── Phase 7: Also persist to meditation_insights table ────────
        if (meditationStore && constellationId) {
          try {
            meditationStore.recordMeditationInsight({
              id: `mi-${Date.now()}-${Math.random().toString(36).slice(2)}`,
              session_id: constellationId,
              content,
              importance: 7,
              generated_at: Date.now(),
              insight_type: 'reflection',
              source_tags: JSON.stringify(tags ?? ['meditation']),
              consolidation_ref: engramId,
            })
          } catch (err) {
            logger.warn('[Corpus] Insight persistence failed', { error: String(err) })
          }
        }
        
        logger.info('[Corpus] Remembered', { content: content.slice(0, 80) })
        return { content: `Remembered: "${content.slice(0, 100)}..."` }
      } catch (err) {
        return { content: `Failed to remember: ${String(err)}` }
      }
    },

    async create_engram(input) {
      const { content, nodeType, tags } = input as { content: string; nodeType?: string; tags?: string[] }
      if (!content || content.length < 5) {
        return { content: 'Nothing to crystallize.' }
      }
      try {
        const validTypes: EngramType[] = ['pattern', 'abstraction', 'decision', 'fact']
        const resolvedType: EngramType = validTypes.includes(nodeType as EngramType)
          ? (nodeType as EngramType)
          : 'pattern'
        
        // Store in mnemic field
        const engramId = mnemicField.store({
          content,
          nodeType: resolvedType,
          provenance: 'meditation',
          tags: tags ?? ['meditation'],
        })
        
        // ── Phase 7: Also persist to meditation_insights table ────────
        if (meditationStore && constellationId) {
          try {
            meditationStore.recordMeditationInsight({
              id: `mi-${Date.now()}-${Math.random().toString(36).slice(2)}`,
              session_id: constellationId,
              content,
              importance: 8, // Engrams are higher importance
              generated_at: Date.now(),
              insight_type: resolvedType,
              source_tags: JSON.stringify(tags ?? ['meditation']),
              consolidation_ref: engramId,
            })
          } catch (err) {
            logger.warn('[Corpus] Insight persistence failed', { error: String(err) })
          }
        }
        
        logger.info('[Corpus] Engram created', { content: content.slice(0, 80), nodeType })
        return { content: `Engram created: "${content.slice(0, 100)}..."` }
      } catch (err) {
        return { content: `Failed to create engram: ${String(err)}` }
      }
    },

    async kindle(input) {
      const { query } = input as { query: string }
      if (!query) {
        return { content: 'No concept to kindle.' }
      }
      try {
        const hits = mnemicField.searchText(query, 10)
        if (hits.length === 0) {
          return { content: `Nothing surfaced for "${query}".` }
        }
        const results = hits.slice(0, 5).map(h =>
          `- ${h.engram.content.slice(0, 150)}... (score: ${h.score.toFixed(2)})`
        ).join('\n')
        return { content: `What surfaced for "${query}":\n${results}` }
      } catch (err) {
        return { content: `Failed to kindle: ${String(err)}` }
      }
    },

    async consolidate() {
      try {
        const result = await mnemicField.consolidate()
        return {
          content: `Consolidation complete: ${result.potentiationUpdates} updates, ${result.nucleiDetected} nuclei, ${result.abstractionsCreated} abstractions.`,
        }
      } catch (err) {
        return { content: `Consolidation failed: ${String(err)}` }
      }
    },

    async record_learning(input) {
      const { observation, category } = input as { observation: string; category?: string }
      if (!observation) {
        return { content: 'Nothing to record.' }
      }
      try {
        mnemicField.store({
          content: observation,
          nodeType: 'pattern',
          provenance: 'meditation',
          tags: ['learning', category ?? 'general'],
        })
        return { content: `Learning recorded: "${observation.slice(0, 100)}..."` }
      } catch (err) {
        return { content: `Failed to record learning: ${String(err)}` }
      }
    },

    async rest(input) {
      const { summary } = input as { summary?: string }
      logger.info('[Corpus] Resting', { summary: summary?.slice(0, 100) })
      return { content: summary ? `Resting. ${summary}` : 'Resting.', done: true }
    },
  }
}
