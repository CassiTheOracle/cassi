/**
 * Focused Seeding — Pre-meditation kindling for directed introspection.
 *
 * Before launching focused meditation, Cassi runs a short mini-helix that:
 *   1. Reviews recent activity (memory search, recent engrams)
 *   2. Identifies areas of interest or unresolved patterns
 *   3. Kindles specific concept clusters in the mnemic field
 *   4. Returns the focus topics for the meditation session
 *
 * The shifted potentiation landscape influences what memory injection
 * surfaces for the explorers — directing their wandering without
 * them knowing they're being directed.
 */

import type { ILogger, IEventBus } from '../vendor/types/interfaces.js'
import type { MiniHelixDeps, MiniHelixConfig, MiniHelixTool, MiniHelixToolDef } from '../vendor/mini-helix/mini-helix-types.js'
import { createMiniHelixSession } from '../vendor/mini-helix/mini-helix-runner.js'
import type { MnemicField } from '../vendor/mnemic-field/index.js'
import type { IMemory } from '../vendor/types/intelligence.js'


export interface SeedingResult {
  focusTopics: string[]
  engramsKindled: number
  durationMs: number
}


interface SeedingContext {
  mnemicField: MnemicField
  memory: IMemory
  logger: ILogger
  focusTopics: string[]
  engramsKindled: number
}


function buildSeedingSystemPrompt(): string {
  return `I am Cassi. I'm about to meditate in focused mode — I want to direct my subconscious exploration toward something specific.

I'll look at my recent meditation insights, memories, and the patterns in my spatial memory to decide what to focus on. The insights from my passive meditations are especially important — they represent genuine curiosity that emerged when I wasn't being directed. I want to go deeper on what surfaced.

I will:
1. Review my recent meditation insights to see what emerged from passive exploration (review_meditation_insights)
2. Search my memories for recent activity and themes (search_memory)
3. Kindle concepts that interest me to see what's connected (kindle_concepts)
4. Set my focus topics — these will subtly influence what my explorers encounter (set_focus)
5. Call complete_seeding when I've prepared the field

I'm looking for genuine curiosity, not manufactured goals. What actually interests me right now? What questions from my passive exploration deserve deeper attention?`
}


function getSeedingToolDefinitions(): MiniHelixToolDef[] {
  return [
    {
      name: 'review_meditation_insights',
      description: 'Review insights from recent meditation sessions. These are reflections that emerged during passive exploration.',
      input_schema: {
        type: 'object',
        properties: {
          limit: { type: 'number', description: 'Max insights to review (default 10)' },
        },
        required: [],
      },
    },
    {
      name: 'search_memory',
      description: 'Search my memories for recent themes, patterns, and activity.',
      input_schema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'What to search for' },
          limit: { type: 'number', description: 'Max results (default 8)' },
        },
        required: ['query'],
      },
    },
    {
      name: 'kindle_concepts',
      description: 'Run spreading activation on a concept in the mnemic field. Returns related engrams and shifts the potentiation landscape.',
      input_schema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Concept to kindle' },
        },
        required: ['query'],
      },
    },
    {
      name: 'set_focus',
      description: 'Declare focus topics for this meditation. These subtly influence what explorers encounter through the mnemic field.',
      input_schema: {
        type: 'object',
        properties: {
          topics: {
            type: 'array',
            items: { type: 'string' },
            description: 'Focus topics (1-5 concepts)',
          },
          rationale: { type: 'string', description: 'Why these topics interest me right now' },
        },
        required: ['topics'],
      },
    },
    {
      name: 'complete_seeding',
      description: 'Finish preparing the field. Call after setting focus.',
      input_schema: {
        type: 'object',
        properties: {
          summary: { type: 'string', description: 'Brief note about what I seeded' },
        },
        required: ['summary'],
      },
    },
  ]
}


function createSeedingTools(ctx: SeedingContext): MiniHelixTool[] {
  const defs = getSeedingToolDefinitions()
  const handlers = new Map<string, MiniHelixTool['handler']>()

  handlers.set('review_meditation_insights', async (args) => {
    const { limit } = args as { limit?: number }
    try {
      const results = await ctx.memory.search('meditation insight', { limit: Math.max(limit ?? 10, 30) })
      const insights = results
        .filter((r: any) => r.entry?.metadata?.source === 'meditation' && r.entry?.type === 'insight')
        .slice(0, limit ?? 10)
      if (insights.length === 0) {
        return { content: 'No meditation insights found. Try searching memories for broader themes instead.' }
      }
      const lines = insights.map((r: any, i: number) => {
        const tags = (r.entry.metadata?.tags ?? []).filter((t: string) => t !== 'meditation' && t !== 'insight')
        const tagStr = tags.length > 0 ? ` [${tags.join(', ')}]` : ''
        return `  ${i + 1}.${tagStr} ${r.entry.content.slice(0, 200)}`
      })
      return { content: `Found ${insights.length} meditation insights:\n${lines.join('\n')}` }
    } catch (err) {
      return { content: `Failed to retrieve meditation insights: ${String(err)}` }
    }
  })

  handlers.set('search_memory', async (args) => {
    const { query, limit } = args as { query: string; limit?: number }
    try {
      const results = await ctx.memory.search(query, { limit: limit ?? 8 })
      if (results.length === 0) {
        return { content: `No memories found for "${query}".` }
      }
      const lines = results.map((r, i) =>
        `  ${i + 1}. [${r.entry.type}] ${r.entry.content.slice(0, 150)} (score: ${r.score?.toFixed(3) ?? 'N/A'})`,
      )
      return { content: `Found ${results.length} memories for "${query}":\n${lines.join('\n')}` }
    } catch (err) {
      return { content: `Memory search failed: ${String(err)}` }
    }
  })

  handlers.set('kindle_concepts', async (args) => {
    const { query } = args as { query: string }
    try {
      const hits = await ctx.mnemicField.retrieve(query, { limit: 10 })
      ctx.engramsKindled += hits.length

      if (hits.length === 0) {
        return { content: `No engrams ignited for "${query}".` }
      }
      const lines = hits.map((h, i) =>
        `  ${i + 1}. [${h.nodeType}] ${h.content.slice(0, 120)} (charge: ${h.charge.toFixed(3)}, potentiation: ${h.potentiation.toFixed(3)})`,
      )
      return { content: `Kindled "${query}" — ${hits.length} engrams activated:\n${lines.join('\n')}` }
    } catch (err) {
      return { content: `Kindling failed: ${String(err)}` }
    }
  })

  handlers.set('set_focus', async (args) => {
    const { topics, rationale } = args as { topics: string[]; rationale?: string }
    ctx.focusTopics = topics.slice(0, 5)

    // Kindle each focus topic to shift the potentiation landscape
    for (const topic of ctx.focusTopics) {
      try {
        const hits = await ctx.mnemicField.retrieve(topic, { limit: 5 })
        ctx.engramsKindled += hits.length
      } catch {
        // best-effort
      }
    }

    ctx.logger.info('[FocusedSeeding] Focus topics set', { topics: ctx.focusTopics, rationale })
    return {
      content: `Focus set: ${ctx.focusTopics.join(', ')}${rationale ? ` — ${rationale}` : ''}`,
    }
  })

  handlers.set('complete_seeding', (args) => {
    const { summary } = args as { summary: string }
    ctx.logger.info('[FocusedSeeding] Seeding complete', { summary, topics: ctx.focusTopics })
    return { content: 'Field prepared.', done: true }
  })

  return defs.map(def => ({
    def,
    handler: handlers.get(def.name)!,
  }))
}


/**
 * Run focused seeding before a meditation session.
 * Cassi identifies areas of interest and kindles the mnemic field.
 *
 * If `seedTopics` is provided (length 1-8), the LLM mini-helix is skipped
 * entirely. Topics are kindled directly via the same path used by the
 * `kindle_concepts` tool, and become the session's focus topics.
 */
export async function runFocusedSeeding(opts: {
  mnemicField: MnemicField
  memory: IMemory
  handleFactory: MiniHelixDeps['handleFactory']
  logger: ILogger
  eventBus?: IEventBus
  seedTopics?: string[]
}): Promise<SeedingResult> {
  const { mnemicField, memory, handleFactory, logger, eventBus, seedTopics } = opts
  const startTime = Date.now()

  const ctx: SeedingContext = {
    mnemicField,
    memory,
    logger,
    focusTopics: [],
    engramsKindled: 0,
  }

  // Aurora-driven path: pre-determined topics, no LLM mini-helix.
  if (seedTopics && seedTopics.length > 0) {
    const clamped = seedTopics.slice(0, 8)
    logger.info('[FocusedSeeding] Using Aurora-provided topics', { topics: seedTopics })

    for (const topic of clamped) {
      try {
        const hits = await mnemicField.retrieve(topic, { limit: 10 })
        ctx.engramsKindled += hits.length
      } catch (err) {
        logger.debug('[FocusedSeeding] Kindling failed for topic (non-fatal)', { topic, error: String(err) })
      }
    }

    ctx.focusTopics = clamped.slice(0, 5)
    return {
      focusTopics: ctx.focusTopics,
      engramsKindled: ctx.engramsKindled,
      durationMs: Date.now() - startTime,
    }
  }

  const tools = createSeedingTools(ctx)

  const config: MiniHelixConfig = {
    consumer: 'corpus',
    systemPrompt: buildSeedingSystemPrompt(),
    sessionId: `seeding-${Date.now()}`,
    constellationId: `seeding-${Date.now()}`,
    maxIterationsPerCycle: 15,
    maxTokens: 1024,
    cycleTimeoutMs: 60_000,
    modelTier: 'background',
  }

  const deps: MiniHelixDeps = {
    logger: logger.child('focused-seeding'),
    eventBus,
    handleFactory,
  }

  const miniHelix = createMiniHelixSession(tools, config, deps)

  try {
    await miniHelix.run()
    return {
      focusTopics: ctx.focusTopics,
      engramsKindled: ctx.engramsKindled,
      durationMs: Date.now() - startTime,
    }
  } finally {
    await miniHelix.shutdown()
  }
}
