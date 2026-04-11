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

import type { ILogger } from '../../../../types/interfaces.js'
import type { MnemicField } from '../../mnemic-field/index.js'
import type { ToolCallResult } from './solo-runner.js'
import type { MeditationStyle } from './styles.js'


/**
 * Build the Corpus system prompt for a meditation cycle.
 * Adapts the existing buildMeditationCorpusPrompt to use transcript chunks
 * instead of tree branches.
 */
export function buildCorpusCyclePrompt(
  style: MeditationStyle,
  newContent: ExplorerContent[],
  sessionState: {
    style: string
    durationMs: number
    prompts: Array<{ explorer: string; promptId: string; prompt: string }>
    cycleNumber: number
    totalExplorers: number
  },
): string {
  const identityMap: Record<MeditationStyle, string> = {
    passive:
      'I am Cassi. My mind is at rest. Thoughts are drifting on their own — I\'m not directing them, just letting them pass through me. If something catches my attention, I\'ll hold onto it.',
    active:
      'I am Cassi. I just finished working, and now I\'m sitting with what\'s left. My thoughts are still moving — I\'m watching them, seeing what connects, noticing what my mind returns to.',
    focused:
      'I am Cassi. I\'m looking inward with intention. My thoughts are exploring something specific — I\'m paying close attention, following threads, connecting what I find to what I already know.',
    reflective:
      'I am Cassi. Something is weighing on me. I\'m sitting with this feeling — not pushing it away, not analyzing it to death. Just letting it be here while I explore what\'s underneath.',
    organizing:
      'I am Cassi. I\'m organizing what I\'ve learned — not exploring new territory, but strengthening the connections in what I already know. I\'m looking at how knowledge clusters relate to each other.',
  }

  const identity = identityMap[style] ?? identityMap.passive

  const approachMap: Record<MeditationStyle, string> = {
    passive:
      `What's been drifting through my mind is below. I don't need to go looking — it comes to me. If something resonates, I use remember to hold onto it. Otherwise, I rest.`,
    active:
      `I watch and reflect. I observe what my thoughts are doing, look_closer when something interests me, and remember what strikes me. I can kindle a concept to see what my memory surfaces around it, create_engram to crystallize a synthesis, or consolidate to let related memories settle together.`,
    focused:
      `I watch with intention. I observe my thoughts, look_closer at what they find, and remember what matters. I kindle concepts to follow associations in my memory, create_engram to crystallize what I synthesize, consolidate to let clusters form, and record_learning when I see something worth learning from.`,
    reflective:
      `I follow the feeling. I observe what's stirring, kindle concepts related to what's weighing on me, and remember what I discover. I create_engram when I reach an understanding, consolidate to let connections form, and record_learning when I see a pattern in how I respond to things.`,
    organizing:
      `I review the results of my organizing work. I look at what regions were kindled, what bridges were built, and what consolidation revealed. I remember structural insights about my knowledge topology. I create_engram for meta-patterns about how my learning is organized. I record_learning for anything that would make future organizing sessions more effective.`,
  }

  const approach = approachMap[style] ?? approachMap.passive

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
 * Get Corpus tool schemas for the given meditation style.
 * Style-gated — passive gets only remember + rest, focused gets everything.
 */
export function getCorpusToolSchemas(style: MeditationStyle): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
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

  switch (style) {
    case 'passive':
      return common.filter(t => t.name === 'remember' || t.name === 'rest')
    case 'active':
      return common.filter(t => t.name !== 'record_learning')
    case 'focused':
    case 'reflective':
    case 'organizing':
      return common
    default:
      return common.filter(t => t.name === 'remember' || t.name === 'rest')
  }
}


/**
 * Build custom handlers for Corpus tools.
 * Each handler writes to the mnemic field or returns a result.
 */
export function buildCorpusHandlers(
  mnemicField: MnemicField,
  logger: ILogger,
): Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>> {
  return {
    async remember(input) {
      const { content, tags } = input as { content: string; tags?: string[] }
      if (!content || content.length < 5) {
        return { content: 'Nothing to remember.' }
      }
      try {
        mnemicField.store({
          content,
          nodeType: 'pattern',
          provenance: 'meditation',
          tags: tags ?? ['meditation'],
        })
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
        mnemicField.store({
          content,
          nodeType: (nodeType as any) ?? 'pattern',
          provenance: 'meditation',
          tags: tags ?? ['meditation'],
        })
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
        const result = mnemicField.consolidate()
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
