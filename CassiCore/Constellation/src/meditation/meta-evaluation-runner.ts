/**
 * Meta-Evaluation Runner — Cassi scores her own Corpus observation prompt.
 *
 * After each meditation session, Cassi reviews how well her observation
 * prompt worked: did she extract genuine insights? Use tools meaningfully?
 * Go beyond surface observations?
 *
 * Scores feed into Thompson sampling for corpus prompt evolution.
 * Mutations create new observation prompts.
 */

import type { ILogger } from '../vendor/types/interfaces.js'
import type { MeditationStore } from './meditation-store.js'
import type { MeditationSession } from './types.js'
import type { ToolCallResult } from './solo-runner.js'


/**
 * Build the meta-evaluation prompt.
 */
export function buildMetaEvaluationPrompt(
  session: MeditationSession,
  corpusPrompt: { id: string; identity: string; approach: string; category: string },
  corpusOutput: {
    iterations: number
    toolCalls: number
    toolsUsed: string[]
    insightsStored: number
    consolidations: number
  },
  store: MeditationStore,
): string {
  const history = store.getCorpusScoresForPrompt(corpusPrompt.id, 5)
  let historyBlock = ''
  if (history.length > 0) {
    const lines = history.map((h: { overall_score: number; scored_at: number }) =>
      `  Score: ${h.overall_score.toFixed(2)} (${new Date(h.scored_at).toISOString().slice(0, 10)})`
    ).join('\n')
    historyBlock = `\n\nPrevious scores for this prompt:\n${lines}`
  }

  return `I just finished observing two meditation explorers. I'm reviewing how well my observation prompt worked.

My observation prompt was:
  ID: ${corpusPrompt.id}
  Category: ${corpusPrompt.category}
  Identity: "${corpusPrompt.identity.slice(0, 150)}..."
  Approach: "${corpusPrompt.approach.slice(0, 150)}..."

What I actually did during observation:
  Iterations: ${corpusOutput.iterations}
  Tool calls: ${corpusOutput.toolCalls}
  Tools used: ${corpusOutput.toolsUsed.join(', ') || 'none'}
  Insights stored: ${corpusOutput.insightsStored}
  Consolidations: ${corpusOutput.consolidations}${historyBlock}

I need to score how well this observation prompt worked for me. Good observation prompts lead to:
- Genuine, non-obvious insights (not just surface observations)
- Meaningful tool use (remember, create_engram, kindle, consolidate — not just rest)
- Depth of reflection (going beyond "I noticed X" to "This connects to Y because...")
- Self-awareness (noticing patterns in my own observation process)

My scoring criteria:
- insight_quality (0-1): Were the insights genuine and non-obvious?
- tool_diversity (0-1): Did I use multiple tools meaningfully, or just one?
- depth (0-1): Did I go beyond surface observations to deeper connections?
- self_reflection (0-1): Did I reflect on my own observation process?
- overall_score (0-1): My holistic assessment of how well this prompt worked

I can also evolve the prompt library:
- If this prompt worked well, I can create a variant with suggest_corpus_mutation
- I can adjust the corpus evolution rate with adjust_corpus_evolution_rate

I write in first person. I am honest — some prompts work better than others.`
}


/**
 * Get meta-evaluation tool schemas.
 */
export function getMetaEvaluationToolSchemas(): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
  return [
    {
      name: 'score_corpus_prompt',
      description: 'Score the corpus observation prompt based on how well it worked.',
      input_schema: {
        type: 'object',
        properties: {
          overall_score: { type: 'number', description: 'Overall score 0-1' },
          insight_quality: { type: 'number', description: 'Insight quality score 0-1' },
          tool_diversity: { type: 'number', description: 'Tool diversity score 0-1' },
          depth: { type: 'number', description: 'Depth score 0-1' },
          self_reflection: { type: 'number', description: 'Self-reflection score 0-1' },
          evaluation: { type: 'string', description: 'Brief first-person reflection' },
        },
        required: ['overall_score'],
      },
    },
    {
      name: 'read_corpus_prompt_history',
      description: 'View previous scores for this corpus prompt.',
      input_schema: {
        type: 'object',
        properties: {
          promptId: { type: 'string', description: 'The corpus prompt ID' },
          limit: { type: 'number', description: 'Max scores to return (default 5)' },
        },
        required: ['promptId'],
      },
    },
    {
      name: 'suggest_corpus_mutation',
      description: 'Create a new corpus prompt inspired by this one.',
      input_schema: {
        type: 'object',
        properties: {
          parentId: { type: 'string', description: 'The corpus prompt ID this is inspired by' },
          identity: { type: 'string', description: 'The new identity text' },
          approach: { type: 'string', description: 'The new approach text' },
          category: { type: 'string', description: 'Category for the new prompt' },
        },
        required: ['parentId', 'identity', 'approach'],
      },
    },
    {
      name: 'adjust_corpus_evolution_rate',
      description: 'Adjust the mutation temperature for corpus prompts.',
      input_schema: {
        type: 'object',
        properties: {
          direction: { type: 'string', enum: ['warmer', 'cooler', 'stable'], description: 'Which way to adjust' },
          rationale: { type: 'string', description: 'Why this adjustment' },
        },
        required: ['direction'],
      },
    },
    {
      name: 'complete_meta_evaluation',
      description: 'End the meta-evaluation with a reflection.',
      input_schema: {
        type: 'object',
        properties: {
          summary: { type: 'string', description: 'Overall reflection in first person' },
        },
        required: ['summary'],
      },
    },
  ]
}


/**
 * Build custom handlers for meta-evaluation tools.
 */
export function buildMetaEvaluationHandlers(
  store: MeditationStore,
  session: MeditationSession,
  corpusPromptId: string,
  logger: ILogger,
): Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>> {
  return {
    async score_corpus_prompt(input) {
      const { overall_score, insight_quality, tool_diversity, depth, self_reflection, evaluation } =
        input as {
          overall_score: number; insight_quality?: number; tool_diversity?: number;
          depth?: number; self_reflection?: number; evaluation?: string;
        }
      try {
        store.recordCorpusScore({
          session_id: session.constellationId,
          corpus_prompt_id: corpusPromptId,
          style: session.style,
          insight_quality,
          tool_diversity,
          depth,
          self_reflection,
          overall_score,
          evaluation_text: evaluation,
        })
        logger.info('[Meta-Evaluation] Corpus prompt scored', { promptId: corpusPromptId, overallScore: overall_score })
        return { content: `Scored corpus prompt ${corpusPromptId}: ${overall_score.toFixed(2)}` }
      } catch (err) {
        return { content: `Failed to score: ${String(err)}` }
      }
    },

    async read_corpus_prompt_history(input) {
      const { promptId, limit = 5 } = input as { promptId: string; limit?: number }
      try {
        const history = store.getCorpusScoresForPrompt(promptId, limit as number)
        if (history.length === 0) {
          return { content: `No previous scores for ${promptId}.` }
        }
        const lines = history.map((h: { overall_score: number; scored_at: number }) =>
          `  ${h.overall_score.toFixed(2)} (${new Date(h.scored_at).toISOString().slice(0, 10)})`
        ).join('\n')
        return { content: `History for ${promptId}:\n${lines}` }
      } catch (err) {
        return { content: `Failed to read history: ${String(err)}` }
      }
    },

    async suggest_corpus_mutation(input) {
      const { parentId, identity, approach, category } = input as {
        parentId: string; identity: string; approach: string; category?: string;
      }
      try {
        const temp = store.getMutationTemperature()
        if (temp < 0.2) {
          return { content: `Mutation temperature too low (${temp.toFixed(2)}) — not creating variants right now.` }
        }
        const newId = `cassi-corpus-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
        const ok = store.createCorpusMutation(newId, identity, approach, category ?? 'observer', session.style as any, parentId)
        if (!ok) {
          return { content: 'Corpus prompt cap reached — cannot create new variant.' }
        }
        logger.info('[Meta-Evaluation] New corpus prompt created', { promptId: newId, parentId })
        return { content: `New corpus prompt created: ${newId}` }
      } catch (err) {
        return { content: `Failed to suggest mutation: ${String(err)}` }
      }
    },

    async adjust_corpus_evolution_rate(input) {
      const { direction, rationale } = input as { direction: 'warmer' | 'cooler' | 'stable'; rationale?: string }
      try {
        const oldTemp = store.getMutationTemperature()
        let newTemp = oldTemp
        const step = 0.1
        if (direction === 'warmer') newTemp = Math.min(1.0, oldTemp + step)
        else if (direction === 'cooler') newTemp = Math.max(0.0, oldTemp - step)
        store.setMutationTemperature(newTemp)
        logger.info('[Meta-Evaluation] Corpus evolution rate adjusted', { direction, oldTemp, newTemp })
        return { content: `Mutation temperature: ${oldTemp.toFixed(2)} → ${newTemp.toFixed(2)} (${direction})${rationale ? ` — ${rationale}` : ''}` }
      } catch (err) {
        return { content: `Failed to adjust evolution: ${String(err)}` }
      }
    },

    async complete_meta_evaluation(input) {
      const { summary } = input as { summary: string }
      logger.info('[Meta-Evaluation] Complete', { summary: summary?.slice(0, 100) })
      return { content: 'Meta-evaluation complete.', done: true }
    },
  }
}
