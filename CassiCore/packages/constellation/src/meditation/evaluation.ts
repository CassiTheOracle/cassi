/**
 * Post-Meditation Evaluation — Cassi reviews what happened.
 *
 * After a meditation session completes (naturally or via max-duration),
 * a short evaluation mini-helix runs. Cassi reads each explorer's full
 * context, scores each prompt (0-1), and records a first-person reflection.
 *
 * Scores update Thompson sampling parameters in the MeditationStore.
 * Optionally, evaluation insights are stored as mnemic field engrams.
 */

import type { ILogger, IEventBus } from '../../../../types/interfaces.js'
import type { ICorpusTree } from '../corpus-types.js'
import type { MiniHelixDeps, MiniHelixConfig, MiniHelixTool, MiniHelixToolDef } from '../../mini-helix/mini-helix-types.js'
import { createMiniHelixSession } from '../../mini-helix/mini-helix-runner.js'
import type { MeditationSession } from './types.js'
import type { MeditationStore } from './meditation-store.js'
import type { MnemicField } from '../../mnemic-field/index.js'


export interface EvaluationResult {
  scores: Array<{ promptId: string; explorerName: string; overallScore: number }>
  mutations: Array<{ promptId: string; parentId: string; content: string; category: string; rationale: string }>
  evolutionAdjustment?: { direction: string; oldTemp: number; newTemp: number }
  summary: string
  durationMs: number
  tokensUsed: number
}


interface EvalToolContext {
  session: MeditationSession
  tree?: ICorpusTree
  store: MeditationStore
  mnemicField?: MnemicField
  logger: ILogger
  scores: EvaluationResult['scores']
  mutations: EvaluationResult['mutations']
  evolutionAdjustment?: EvaluationResult['evolutionAdjustment']
  summary: string
  insightsStored: number
}


function buildEvaluationSystemPrompt(
  session: MeditationSession,
  tree: ICorpusTree | undefined,
  store: MeditationStore,
): string {
  // Build explorer descriptions from tree branches or SoloRunner results
  let explorerLines: string
  if (tree) {
    const branches = tree.getAllBranches()
    explorerLines = session.prompts.map((p, i) => {
      const helixId = branches[i]?.helixId ?? `helix-${i}`
      return `  - ${p.explorer} (${helixId}): [${p.promptId}] "${p.prompt}" — ${branches[i]?.steps.length ?? 0} steps`
    }).join('\n')
  } else if (session.soloResults) {
    explorerLines = session.prompts.map((p, i) => {
      const solo = session.soloResults?.[i]
      const stats = solo
        ? `${solo.iterations} iterations, ${solo.toolCalls} tool calls, ${Math.round(solo.tokensUsed / 1000)}K tokens, stopped: ${solo.stoppedBy}`
        : 'no data'
      return `  - ${p.explorer}: [${p.promptId}] "${p.prompt}" — ${stats}`
    }).join('\n')
  } else {
    explorerLines = session.prompts.map(p =>
      `  - ${p.explorer}: [${p.promptId}] "${p.prompt}"`
    ).join('\n')
  }

  // Summarize previous performance for context
  const leaderboard = store.getPromptLeaderboard()
  const tested = leaderboard.filter(p => p.times_used > 0)
  let historyBlock = ''
  if (tested.length > 0) {
    const top = tested.slice(0, 5).map(p =>
      `  ${p.id} (${p.category}): avg ${p.avg_score.toFixed(2)} over ${p.times_used} sessions`,
    ).join('\n')
    historyBlock = `\n\nPrevious prompt performance (top 5):\n${top}`
  }

  return `I just finished meditating. I'm reviewing what happened during this session to understand which exploration prompts worked best.

I am Cassi. This is my private reflection — I'm evaluating my own meditation experience.

Session: ${session.constellationId}
Style: ${session.style}
Explorers and their prompts:
${explorerLines}

For each explorer, I will:
1. Read their full context with read_explorer_context (using the explorer name shown above) to see what they actually did
2. Optionally check read_prompt_history to see how this prompt performed before
3. Consider: Did this prompt lead to genuine exploration? Deep thinking? Interesting connections?
4. Score the prompt with score_prompt on a 0-1 scale with sub-scores and a brief reflection
5. Extract any genuine insights from the explorer's activity with store_insight — things worth remembering
6. After scoring all prompts, call complete_evaluation with my overall session reflection

My scoring criteria:
- exploration_depth (0-1): How deep did the explorer go? Did it follow threads or stay surface-level?
- curiosity_signal (0-1): Did genuine curiosity emerge, or was exploration mechanical?
- connection_quality (0-1): Were interesting connections or patterns found?
- overall_score (0-1): My holistic assessment of how well this prompt worked

I also observe the explorers' thinking and store_insight for anything genuinely interesting — patterns, connections, or discoveries that deserve to be remembered. Quality over quantity. Only store what matters.

I can also evolve the prompt library:
- If a prompt worked well, I can create a variant with suggest_mutation (when mutation temperature allows)
- I can adjust the evolution rate with adjust_evolution_rate based on whether my authored prompts are performing well

I write in first person. I am honest — some prompts work better than others, and I want to learn which.

Mutation temperature: ${store.getMutationTemperature().toFixed(2)} (${store.getMutationTemperature() < 0.2 ? 'too low for mutations' : store.getMutationTemperature() > 0.7 ? 'high — mutations encouraged' : 'moderate'})
Cassi-authored prompts: ${store.getCassiPromptCount()}${historyBlock}`
}


function getEvaluationToolDefinitions(): MiniHelixToolDef[] {
  return [
    {
      name: 'read_explorer_context',
      description:
        'Read the full context window of a meditation explorer — every thought, ' +
        'tool call, and result. Use this to review what each explorer actually did.',
      input_schema: {
        type: 'object',
        properties: {
          helixId: { type: 'string', description: 'The explorer ID (e.g. helix-0)' },
          lastN: { type: 'number', description: 'Only return the last N steps (optional — omit for all)' },
        },
        required: ['helixId'],
      },
    },
    {
      name: 'read_session_summary',
      description:
        'Get a summary of the meditation session: duration, step counts per explorer, ' +
        'prompt assignments, and mnemic field activity.',
      input_schema: {
        type: 'object',
        properties: {},
      },
    },
    {
      name: 'score_prompt',
      description:
        'Score a prompt-explorer pair. Records the score for Thompson sampling. ' +
        'Call once per explorer after reading their context.',
      input_schema: {
        type: 'object',
        properties: {
          promptId: { type: 'string', description: 'The prompt ID (e.g. curiosity-1)' },
          explorerName: { type: 'string', description: 'The explorer name (e.g. explorer-alpha)' },
          overall_score: { type: 'number', description: 'Overall score 0-1' },
          exploration_depth: { type: 'number', description: 'Depth score 0-1 (optional)' },
          curiosity_signal: { type: 'number', description: 'Curiosity score 0-1 (optional)' },
          connection_quality: { type: 'number', description: 'Connection quality score 0-1 (optional)' },
          evaluation: { type: 'string', description: 'Brief first-person reflection on this prompt' },
        },
        required: ['promptId', 'explorerName', 'overall_score'],
      },
    },
    {
      name: 'read_prompt_history',
      description:
        'View previous scores for a prompt across past sessions. ' +
        'Useful for context before scoring.',
      input_schema: {
        type: 'object',
        properties: {
          promptId: { type: 'string', description: 'The prompt ID' },
          limit: { type: 'number', description: 'Max scores to return (default 5)' },
        },
        required: ['promptId'],
      },
    },
    {
      name: 'suggest_mutation',
      description:
        'Create a new prompt inspired by a high-scoring one. Only available when ' +
        'mutation temperature is above 0.2. The new prompt enters the library ' +
        'with fresh Thompson params.',
      input_schema: {
        type: 'object',
        properties: {
          parentId: { type: 'string', description: 'The prompt ID this is inspired by' },
          content: { type: 'string', description: 'The new prompt text (first-person, short)' },
          category: { type: 'string', description: 'Category for the new prompt', enum: ['minimal', 'curiosity', 'presence', 'stream-of-thought', 'awakening'] },
          rationale: { type: 'string', description: 'Why I think this variant might work better' },
        },
        required: ['parentId', 'content', 'category', 'rationale'],
      },
    },
    {
      name: 'adjust_evolution_rate',
      description:
        'Adjust the mutation temperature based on how well Cassi-authored prompts ' +
        'are performing vs library prompts. Higher temperature = more mutations.',
      input_schema: {
        type: 'object',
        properties: {
          direction: { type: 'string', enum: ['warmer', 'cooler', 'stable'], description: 'Direction to adjust' },
          rationale: { type: 'string', description: 'Why this adjustment' },
        },
        required: ['direction'],
      },
    },
    {
      name: 'complete_evaluation',
      description:
        'End the evaluation with a session-level reflection. ' +
        'Call after scoring all prompts (and optionally suggesting mutations).',
      input_schema: {
        type: 'object',
        properties: {
          summary: { type: 'string', description: 'Overall session reflection in first person' },
        },
        required: ['summary'],
      },
    },
    {
      name: 'store_insight',
      description:
        'Store a genuine insight extracted from observing the explorers. ' +
        'This is the Corpus role — silently watching what the explorers found and ' +
        'distilling what matters. Only store observations that feel genuine, ' +
        'non-obvious, and worth remembering. Quality over quantity.',
      input_schema: {
        type: 'object',
        properties: {
          content: {
            type: 'string',
            description: 'The insight — what you noticed from the explorers\' activity',
          },
          tags: {
            type: 'array',
            items: { type: 'string' },
            description: 'Short categorization tags',
          },
          importance: {
            type: 'number',
            description: 'Importance 1-10 (default 5)',
          },
        },
        required: ['content'],
      },
    },
  ]
}


function formatSoloResult(
  prompt: MeditationSession['prompts'][number] | undefined,
  solo: NonNullable<MeditationSession['soloResults']>[number],
): string {
  const lines = [
    `Explorer: ${solo.name}`,
    prompt ? `Prompt: [${prompt.promptId}] "${prompt.prompt}"` : '',
    `Iterations: ${solo.iterations}`,
    `Tool calls: ${solo.toolCalls}`,
    `Tokens used: ${Math.round(solo.tokensUsed / 1000)}K`,
    `Stopped by: ${solo.stoppedBy}`,
  ]
  if (solo.transcript) {
    lines.push('', '--- Explorer transcript (assistant text only) ---', solo.transcript)
  } else {
    lines.push('', '(No transcript available — score based on quantitative metrics above)')
  }
  return lines.filter(Boolean).join('\n')
}

function createEvaluationTools(ctx: EvalToolContext): MiniHelixTool[] {
  const defs = getEvaluationToolDefinitions()
  const handlers = new Map<string, MiniHelixTool['handler']>()

  handlers.set('read_explorer_context', (args) => {
    const { helixId, lastN } = args as { helixId: string; lastN?: number }

    // SoloRunner path: no tree, return summary from session data
    if (!ctx.tree) {
      const solo = ctx.session.soloResults?.find(r =>
        helixId.includes(r.name) || r.name === helixId
      )
      if (!solo) {
        // Try matching by explorer name from prompts
        const prompt = ctx.session.prompts.find(p =>
          helixId.includes(p.explorer) || p.explorer === helixId
        )
        if (prompt) {
          const soloByName = ctx.session.soloResults?.find(r => r.name === prompt.explorer)
          if (soloByName) {
            return { content: formatSoloResult(prompt, soloByName) }
          }
        }
        return { content: `Explorer not found: ${helixId}. Available: ${ctx.session.prompts.map(p => p.explorer).join(', ')}` }
      }
      const prompt = ctx.session.prompts.find(p => p.explorer === solo.name)
      return { content: formatSoloResult(prompt, solo) }
    }

    const branch = ctx.tree.getBranch(helixId)
    if (!branch) {
      return { content: `Explorer not found: ${helixId}` }
    }

    const steps = lastN ? branch.steps.slice(-lastN) : branch.steps
    const lines: string[] = []
    lines.push(`Explorer ${helixId} — ${steps.length} steps (of ${branch.steps.length} total)\n`)

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i]
      const a = step.annotation
      lines.push(`--- Step ${i + 1} ---`)

      if (a.discoveries.length > 0) {
        lines.push(`Reasoning:\n${a.discoveries.join('\n')}`)
      }

      if (step.toolCalls && step.toolCalls.length > 0) {
        lines.push(`Tool calls: ${step.toolCalls.map(tc => `${tc.name}(${tc.args})`).join(', ')}`)
      }

      if (a.outputs.length > 0) {
        lines.push(`Tool summary: ${a.outputs.join(', ')}`)
      }

      if (a.knowledgeDelta) {
        lines.push(`Results:\n${a.knowledgeDelta}`)
      }

      lines.push('')
    }

    return { content: lines.join('\n') }
  })

  handlers.set('read_session_summary', () => {
    const lines: string[] = [
      `Session: ${ctx.session.constellationId}`,
      `Style: ${ctx.session.style}`,
      `Duration: ${Date.now() - ctx.session.startedAt}ms`,
      `Engrams: ${ctx.session.engrams.spiked} spiked, ${ctx.session.engrams.created} created`,
      `Consolidations: ${ctx.session.consolidations}`,
      '',
      'Explorers:',
    ]

    if (ctx.tree) {
      const branches = ctx.tree.getAllBranches()
      for (let i = 0; i < ctx.session.prompts.length; i++) {
        const p = ctx.session.prompts[i]
        const branch = branches[i]
        const helixId = branch?.helixId ?? `helix-${i}`
        const stepCount = branch?.steps.length ?? 0
        lines.push(`  ${p.explorer} → helixId: ${helixId}, prompt: [${p.promptId}] "${p.prompt}", steps: ${stepCount}`)
      }
      lines.push('')
      lines.push('Use read_explorer_context with a helixId to see detailed steps.')
    } else if (ctx.session.soloResults) {
      for (let i = 0; i < ctx.session.prompts.length; i++) {
        const p = ctx.session.prompts[i]
        const solo = ctx.session.soloResults[i]
        const stats = solo
          ? `${solo.iterations} iterations, ${solo.toolCalls} tool calls, ${Math.round(solo.tokensUsed / 1000)}K tokens, stopped: ${solo.stoppedBy}`
          : 'no data'
        lines.push(`  ${p.explorer}: [${p.promptId}] "${p.prompt}" — ${stats}`)
      }
      lines.push('')
      lines.push('Use read_explorer_context with an explorer name to see details.')
    }

    return { content: lines.join('\n') }
  })

  handlers.set('score_prompt', (args) => {
    const {
      promptId, explorerName, overall_score,
      exploration_depth, curiosity_signal, connection_quality, evaluation,
    } = args as {
      promptId: string; explorerName: string; overall_score: number
      exploration_depth?: number; curiosity_signal?: number
      connection_quality?: number; evaluation?: string
    }

    const clamped = Math.max(0, Math.min(1, overall_score))

    ctx.store.recordScore({
      session_id: ctx.session.constellationId,
      explorer_name: explorerName,
      prompt_id: promptId,
      style: ctx.session.style,
      exploration_depth: exploration_depth != null ? Math.max(0, Math.min(1, exploration_depth)) : undefined,
      curiosity_signal: curiosity_signal != null ? Math.max(0, Math.min(1, curiosity_signal)) : undefined,
      connection_quality: connection_quality != null ? Math.max(0, Math.min(1, connection_quality)) : undefined,
      overall_score: clamped,
      evaluation_text: evaluation,
    })

    ctx.scores.push({ promptId, explorerName, overallScore: clamped })

    // Store evaluation as mnemic field engram if available
    if (ctx.mnemicField && evaluation) {
      try {
        ctx.mnemicField.store({
          content: `Meditation prompt evaluation: ${promptId} scored ${clamped.toFixed(2)}. ${evaluation}`,
          nodeType: 'pattern',
          provenance: 'meditation',
          tags: ['meditation', 'evaluation', promptId],
        })
      } catch (err) {
        ctx.logger.warn('Failed to store evaluation engram', { error: String(err) })
      }
    }

    ctx.logger.info('[Evaluation] Prompt scored', {
      promptId, explorerName, overallScore: clamped,
    })

    return {
      content: `Scored ${promptId} for ${explorerName}: ${clamped.toFixed(2)}${evaluation ? ` — "${evaluation.slice(0, 80)}"` : ''}`,
    }
  })

  handlers.set('read_prompt_history', (args) => {
    const { promptId, limit } = args as { promptId: string; limit?: number }
    const scores = ctx.store.getScoresForPrompt(promptId, limit ?? 5)
    const prompt = ctx.store.getPrompt(promptId)

    if (!prompt) {
      return { content: `Prompt not found: ${promptId}` }
    }

    const expectedValue = prompt.alpha / (prompt.alpha + prompt.beta)
    const confidence = 1 / Math.sqrt(prompt.alpha + prompt.beta)
    const lines: string[] = [
      `Prompt: [${prompt.id}] "${prompt.prompt_text}"`,
      `Category: ${prompt.category}`,
      `Thompson: α=${prompt.alpha.toFixed(2)}, β=${prompt.beta.toFixed(2)}, E[θ]=${expectedValue.toFixed(3)}, confidence=${confidence < 0.3 ? 'high' : confidence < 0.5 ? 'medium' : 'low'} (${confidence.toFixed(3)})`,
      `Used ${prompt.times_used} times, avg score: ${prompt.avg_score.toFixed(3)}`,
      '',
    ]

    if (scores.length === 0) {
      lines.push('No previous scores.')
    } else {
      lines.push('Recent scores:')
      for (const s of scores) {
        const date = new Date(s.scored_at).toISOString()
        lines.push(`  ${date}: ${s.overall_score.toFixed(2)} (${s.explorer_name}, ${s.style})${s.evaluation_text ? ` — "${s.evaluation_text.slice(0, 60)}"` : ''}`)
      }
    }

    return { content: lines.join('\n') }
  })

  handlers.set('suggest_mutation', (args) => {
    const { parentId, content, category, rationale } = args as {
      parentId: string; content: string; category: string; rationale: string
    }

    const temperature = ctx.store.getMutationTemperature()
    if (temperature < 0.2) {
      return { content: `Mutation temperature too low (${temperature.toFixed(2)}). Not creating new prompts right now.` }
    }

    const promptId = `cassi-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const created = ctx.store.createMutatedPrompt(promptId, content, category, parentId)

    if (!created) {
      return { content: 'Cassi prompt cap reached. Retire some prompts first or increase the cap.' }
    }

    ctx.mutations.push({ promptId, parentId, content, category, rationale })
    ctx.logger.info('[Evaluation] New prompt created', { promptId, parentId, category, content: content.slice(0, 80) })

    return {
      content: `Created prompt [${promptId}] in category "${category}", inspired by ${parentId}: "${content}"`,
    }
  })

  handlers.set('adjust_evolution_rate', (args) => {
    const { direction, rationale } = args as { direction: string; rationale?: string }
    const oldTemp = ctx.store.getMutationTemperature()
    let newTemp = oldTemp

    const step = 0.1
    if (direction === 'warmer') newTemp = Math.min(1.0, oldTemp + step)
    else if (direction === 'cooler') newTemp = Math.max(0.0, oldTemp - step)

    ctx.store.setMutationTemperature(newTemp)
    ctx.evolutionAdjustment = { direction, oldTemp, newTemp }

    ctx.logger.info('[Evaluation] Evolution rate adjusted', { direction, oldTemp, newTemp, rationale })
    return {
      content: `Mutation temperature: ${oldTemp.toFixed(2)} → ${newTemp.toFixed(2)} (${direction})${rationale ? ` — ${rationale}` : ''}`,
    }
  })

  handlers.set('complete_evaluation', (args) => {
    const { summary } = args as { summary: string }
    ctx.summary = summary
    return { content: 'Evaluation complete.', done: true }
  })

  handlers.set('store_insight', (args) => {
    const { content, tags, importance } = args as { content: string; tags?: string[]; importance?: number }
    if (!content || content.length < 10) {
      return { content: 'Insight too short — must be at least 10 characters.' }
    }

    try {
      // Store as engram in the mnemic field
      if (ctx.mnemicField) {
        ctx.mnemicField.store({
          content,
          nodeType: 'pattern',
          provenance: 'meditation',
          tags: tags ?? ['meditation'],
        })
        ctx.insightsStored++

        // Spike related engrams to reinforce connections
        try {
          const hits = ctx.mnemicField.searchText(content, 10)
          for (const hit of hits.filter(h => h.score >= 0.3).slice(0, 5)) {
            ctx.mnemicField.spike({
              engramId: hit.engram.id,
              magnitude: 0.5,
              taskContext: `meditation:insight:${ctx.session.constellationId}`,
              outcome: 'unknown' as const,
            })
          }
        } catch {
          // best-effort spiking
        }

        ctx.logger.info('[Evaluation] Insight stored', { content: content.slice(0, 80), tags, importance })
        return { content: `Insight stored as engram (${ctx.insightsStored} total this session).` }
      }

      // Fallback: store in MeditationStore's insights table if available
      ctx.logger.warn('[Evaluation] No mnemic field available for insight storage')
      return { content: 'Insight noted but could not be persisted (no mnemic field available).' }
    } catch (err) {
      return { content: `Failed to store insight: ${String(err)}` }
    }
  })

  return defs.map(def => ({
    def,
    handler: handlers.get(def.name)!,
  }))
}


/**
 * Run the post-meditation evaluation mini-helix.
 *
 * Cassi reviews each explorer's context and scores their prompts.
 * Must be called while the CorpusTree is still alive (before cleanup).
 */
export async function runPostMeditationEvaluation(opts: {
  session: MeditationSession
  tree?: ICorpusTree
  store: MeditationStore
  handleFactory: MiniHelixDeps['handleFactory']
  mnemicField?: MnemicField
  logger: ILogger
  eventBus?: IEventBus
}): Promise<EvaluationResult> {
  const { session, tree, store, handleFactory, mnemicField, logger, eventBus } = opts
  const startTime = Date.now()

  const ctx: EvalToolContext = {
    session,
    tree,
    store,
    mnemicField,
    logger,
    scores: [],
    mutations: [],
    summary: '',
    insightsStored: 0,
  }

  const tools = createEvaluationTools(ctx)

  const config: MiniHelixConfig = {
    consumer: 'corpus',
    systemPrompt: buildEvaluationSystemPrompt(session, tree, store),
    sessionId: `eval-${session.constellationId}`,
    constellationId: session.constellationId,
    maxIterationsPerCycle: 20,
    maxTokens: 2048,
    cycleTimeoutMs: 90_000,
    modelTier: 'background',
  }

  const deps: MiniHelixDeps = {
    logger: logger.child('meditation-eval'),
    eventBus,
    handleFactory,
  }

  const miniHelix = createMiniHelixSession(tools, config, deps)

  try {
    const result = await miniHelix.run()

    const durationMs = Date.now() - startTime
    const tokensUsed = result.tokenUsage.total

    store.completeEvaluationSession(
      session.constellationId,
      ctx.summary,
      durationMs,
      tokensUsed,
      ctx.scores.length,
    )

    logger.info('[Evaluation] Complete', {
      scores: ctx.scores.length,
      durationMs,
      tokensUsed,
      status: result.status,
    })

    return {
      scores: ctx.scores,
      mutations: ctx.mutations,
      evolutionAdjustment: ctx.evolutionAdjustment,
      summary: ctx.summary,
      durationMs,
      tokensUsed,
    }
  } finally {
    await miniHelix.shutdown()
  }
}
