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

import type { ILogger, IEventBus } from '../../../../types/interfaces.js'
import type { MiniHelixDeps, MiniHelixConfig, MiniHelixTool, MiniHelixToolDef } from '../../mini-helix/mini-helix-types.js'
import { createMiniHelixSession } from '../../mini-helix/mini-helix-runner.js'
import type { MnemicField } from '../../mnemic-field/index.js'
import type { IMemory } from '../../../../types/intelligence.js'


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

I'll look at my recent memories and the patterns in my spatial memory to decide what to focus on. Maybe there's an unresolved pattern I noticed, a question that keeps surfacing, or an area of the codebase I haven't explored deeply.

I will:
1. Search my memories for recent activity and themes (search_memory)
2. Kindle concepts that interest me to see what's connected (kindle_concepts)
3. Set my focus topics — these will subtly influence what my explorers encounter (set_focus)
4. Call complete_seeding when I've prepared the field

I'm looking for genuine curiosity, not manufactured goals. What actually interests me right now?`
}


function getSeedingToolDefinitions(): MiniHelixToolDef[] {
  return [
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

  handlers.set('kindle_concepts', (args) => {
    const { query } = args as { query: string }
    try {
      const hits = ctx.mnemicField.retrieve(query, { limit: 10 })
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

  handlers.set('set_focus', (args) => {
    const { topics, rationale } = args as { topics: string[]; rationale?: string }
    ctx.focusTopics = topics.slice(0, 5)

    // Kindle each focus topic to shift the potentiation landscape
    for (const topic of ctx.focusTopics) {
      try {
        const hits = ctx.mnemicField.retrieve(topic, { limit: 5 })
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
 */
export async function runFocusedSeeding(opts: {
  mnemicField: MnemicField
  memory: IMemory
  handleFactory: MiniHelixDeps['handleFactory']
  logger: ILogger
  eventBus?: IEventBus
}): Promise<SeedingResult> {
  const { mnemicField, memory, handleFactory, logger, eventBus } = opts
  const startTime = Date.now()

  const ctx: SeedingContext = {
    mnemicField,
    memory,
    logger,
    focusTopics: [],
    engramsKindled: 0,
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
