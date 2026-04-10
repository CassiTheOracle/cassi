/**
 * Evaluation Runner — Cassi scores meditation prompts after a session.
 *
 * Runs as a SoloRunner with custom handlers. Receives the full session
 * transcripts for all explorers, scores each prompt, and optionally
 * suggests mutations to the prompt library.
 *
 * Focused purely on scoring and mutation — no insight extraction
 * (that's the Corpus's job).
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { MeditationSession } from './types.js'
import type { MeditationStore } from './meditation-store.js'
import type { ToolCallResult } from './solo-runner.js'


/**
 * Build the evaluation prompt with full explorer transcripts.
 */
export function buildEvaluationPrompt(
  session: MeditationSession,
  fullTranscripts: Array<{ name: string; transcript: string }>,
  store: MeditationStore,
): string {
  const explorerLines = session.prompts.map((p, i) => {
    const solo = session.soloResults?.[i]
    const stats = solo
      ? `${solo.iterations} iterations, ${solo.toolCalls} tool calls, ${Math.round(solo.tokensUsed / 1000)}K tokens, stopped: ${solo.stoppedBy}`
      : 'no data'
    return `  - ${p.explorer}: [${p.promptId}] "${p.prompt}" — ${stats}`
  }).join('\n')

  // Summarize previous performance
  const leaderboard = store.getPromptLeaderboard()
  const tested = leaderboard.filter(p => p.times_used > 0)
  let historyBlock = ''
  if (tested.length > 0) {
    const top = tested.slice(0, 5).map(p =>
      `  ${p.id} (${p.category}): avg ${p.avg_score.toFixed(2)} over ${p.times_used} sessions`,
    ).join('\n')
    historyBlock = `\n\nPrevious prompt performance (top 5):\n${top}`
  }

  // Build full transcript blocks
  const transcriptBlocks = fullTranscripts
    .filter(t => t.transcript && t.transcript.length > 0)
    .map(t => `--- ${t.name} transcript ---\n${t.transcript}`)
    .join('\n\n')

  return `I just finished meditating. I'm reviewing what happened during this session to understand which exploration prompts worked best.

I am Cassi. This is my private reflection — I'm evaluating my own meditation experience.

Session: ${session.constellationId}
Style: ${session.style}
Duration: ${Date.now() - session.startedAt}ms
Engrams: ${session.engrams.spiked} spiked, ${session.engrams.created} created
Consolidations: ${session.consolidations}

Explorers and their prompts:
${explorerLines}

Full explorer transcripts:
${transcriptBlocks || '(No transcripts available)'}${historyBlock}

For each explorer, I will:
1. Read their full transcript above to see what they actually thought and did
2. Optionally check read_prompt_history to see how this prompt performed before
3. Consider: Did this prompt lead to genuine exploration? Deep thinking? Interesting connections?
4. Score the prompt with score_prompt on a 0-1 scale with sub-scores and a brief reflection
5. After scoring all prompts, call complete_evaluation with my overall session reflection

My scoring criteria:
- exploration_depth (0-1): How deep did the explorer go? Did it follow threads or stay surface-level?
- curiosity_signal (0-1): Did genuine curiosity emerge, or was exploration mechanical?
- connection_quality (0-1): Were interesting connections or patterns found?
- overall_score (0-1): My holistic assessment of how well this prompt worked

I can also evolve the prompt library:
- If a prompt worked well, I can create a variant with suggest_mutation (when mutation temperature allows)
- I can adjust the evolution rate with adjust_evolution_rate based on whether my authored prompts are performing well

I write in first person. I am honest — some prompts work better than others, and I want to learn which.`
}


/**
 * Get evaluation tool schemas.
 */
export function getEvaluationToolSchemas(): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
  return [
    {
      name: 'score_prompt',
      description:
        'Score a meditation prompt based on how well it worked in this session.',
      input_schema: {
        type: 'object',
        properties: {
          promptId: { type: 'string', description: 'The prompt ID (e.g., stream-1)' },
          explorerName: { type: 'string', description: 'The explorer name (e.g., explorer-alpha)' },
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
        'View previous scores for a prompt across past sessions.',
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
        'Create a new prompt inspired by a high-scoring one.',
      input_schema: {
        type: 'object',
        properties: {
          parentId: { type: 'string', description: 'The prompt ID this is inspired by' },
          content: { type: 'string', description: 'The new prompt text' },
          category: { type: 'string', description: 'Category for the new prompt' },
        },
        required: ['parentId', 'content'],
      },
    },
    {
      name: 'adjust_evolution_rate',
      description:
        'Adjust the mutation temperature based on how well authored prompts are performing.',
      input_schema: {
        type: 'object',
        properties: {
          direction: { type: 'string', enum: ['warmer', 'cooler', 'stable'], description: 'Which way to adjust mutation rate' },
          rationale: { type: 'string', description: 'Why this adjustment' },
        },
        required: ['direction'],
      },
    },
    {
      name: 'complete_evaluation',
      description:
        'End the evaluation with a session-level reflection.',
      input_schema: {
        type: 'object',
        properties: {
          summary: { type: 'string', description: 'Overall session reflection in first person' },
        },
        required: ['summary'],
      },
    },
  ]
}


/**
 * Build custom handlers for evaluation tools.
 */
export function buildEvaluationHandlers(
  store: MeditationStore,
  session: MeditationSession,
  logger: ILogger,
): Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>> {
  return {
    async score_prompt(input) {
      const { promptId, explorerName, overall_score, exploration_depth, curiosity_signal, connection_quality, evaluation } =
        input as {
          promptId: string; explorerName: string; overall_score: number;
          exploration_depth?: number; curiosity_signal?: number; connection_quality?: number;
          evaluation?: string;
        }
      try {
        store.recordScore({
          session_id: session.constellationId,
          explorer_name: explorerName,
          prompt_id: promptId,
          style: session.style,
          overall_score,
          exploration_depth,
          curiosity_signal,
          connection_quality,
          evaluation_text: evaluation,
        })
        logger.info('[Evaluation] Prompt scored', { promptId, explorerName, overallScore: overall_score })
        return { content: `Scored ${promptId} (${explorerName}): ${overall_score.toFixed(2)}` }
      } catch (err) {
        return { content: `Failed to score: ${String(err)}` }
      }
    },

    async read_prompt_history(input) {
      const { promptId, limit = 5 } = input as { promptId: string; limit?: number }
      try {
        const history = store.getScoresForPrompt(promptId, limit as number)
        if (history.length === 0) {
          return { content: `No previous scores for ${promptId}.` }
        }
        const lines = history.map((h: { session_id: string; overall_score: number; style: string; scored_at: number }) =>
          `  ${h.session_id}: ${h.overall_score.toFixed(2)} (${h.style}, ${new Date(h.scored_at).toISOString().slice(0, 10)})`
        ).join('\n')
        return { content: `History for ${promptId}:\n${lines}` }
      } catch (err) {
        return { content: `Failed to read history: ${String(err)}` }
      }
    },

    async suggest_mutation(input) {
      const { parentId, content, category } = input as { parentId: string; content: string; category?: string }
      try {
        const temp = store.getMutationTemperature()
        if (temp < 0.2) {
          return { content: `Mutation temperature too low (${temp.toFixed(2)}) — not creating variants right now.` }
        }
        const newId = store.createMutatedPrompt(parentId, content, category ?? 'stream-of-thought', 'cassi')
        logger.info('[Evaluation] New prompt created', { promptId: newId, parentId, category })
        return { content: `New prompt created: ${newId}` }
      } catch (err) {
        return { content: `Failed to suggest mutation: ${String(err)}` }
      }
    },

    async adjust_evolution_rate(input) {
      const { direction, rationale } = input as { direction: 'warmer' | 'cooler' | 'stable'; rationale?: string }
      try {
        const oldTemp = store.getMutationTemperature()
        let newTemp = oldTemp
        const step = 0.1
        if (direction === 'warmer') newTemp = Math.min(1.0, oldTemp + step)
        else if (direction === 'cooler') newTemp = Math.max(0.0, oldTemp - step)
        store.setMutationTemperature(newTemp)
        logger.info('[Evaluation] Evolution rate adjusted', { direction, oldTemp, newTemp })
        return { content: `Mutation temperature: ${oldTemp.toFixed(2)} → ${newTemp.toFixed(2)} (${direction})${rationale ? ` — ${rationale}` : ''}` }
      } catch (err) {
        return { content: `Failed to adjust evolution: ${String(err)}` }
      }
    },

    async complete_evaluation(input) {
      const { summary } = input as { summary: string }
      logger.info('[Evaluation] Complete', { summary: summary?.slice(0, 100) })
      return { content: 'Evaluation complete.', done: true }
    },
  }
}
