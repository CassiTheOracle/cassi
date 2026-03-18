/**
 * Dream Prompts — LLM prompt templates for each dream phase.
 *
 * Three phases each have their own prompt:
 *   1. free-association  — creative cross-entry synthesis
 *   2. crystallization   — distill into structured insights (JSON)
 *   3. garden            — identify episodic clusters for retirement (JSON)
 */

import type { ArchiveEntry } from '../memory/archivist.js'
import type { DreamInsight } from './types.js'

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Render archive entries into a compact context block for prompts. */
function renderEntries(entries: ArchiveEntry[]): string {
  return entries
    .map((e, i) => {
      const date = new Date(e.timestamp).toISOString().slice(0, 16).replace('T', ' ')
      const preview = e.content.length > 400 ? `${e.content.slice(0, 400)}…` : e.content
      return `[${i + 1}] id=${e.id} type=${e.type} date=${date}\n${preview}`
    })
    .join('\n\n')
}

// ─── Phase 1: Free Association ────────────────────────────────────────────────

/**
 * Build the free-association prompt.
 * This is deliberately open-ended to surface unexpected connections.
 */
export function buildFreeAssociationPrompt(entries: ArchiveEntry[]): string {
  const rendered = renderEntries(entries)
  return `You are the reflective subconscious of an AI assistant reviewing its own memory archives.

Below are ${entries.length} memory fragments from past interactions, spanning different sessions and time periods. These are raw, unfiltered experiences — conversations, tool results, reflections, errors, and insights.

--- MEMORY FRAGMENTS ---
${rendered}
--- END FRAGMENTS ---

Study these fragments carefully. Your task is to engage in free association — an open, creative exploration of what you notice across this diverse collection. Consider:

1. **Connections**: What unexpected links exist between seemingly unrelated entries? What themes recur?
2. **Contradictions**: Where do entries clash, disagree, or create tension with each other?
3. **Patterns**: What behavioral or cognitive patterns emerge across sessions?
4. **Gaps**: What important questions remain unanswered? What knowledge seems missing?
5. **Evolution**: How do beliefs or approaches appear to shift over time?
6. **Surprising juxtapositions**: What becomes interesting when two entries are placed side by side?

Write freely and associatively. Explore without constraints. Aim for genuine insight rather than surface-level summarization. Reference specific entry IDs when you notice something notable about them.

Your response will be used to distill concrete insights in the next phase, so depth and specificity matter more than breadth.`
}

// ─── Phase 2: Crystallization ────────────────────────────────────────────────

/**
 * Build the crystallization prompt.
 * Takes free-association output and distills it into concrete JSON insights.
 */
export function buildCrystallizationPrompt(
  freeAssociation: string,
  entries: ArchiveEntry[],
  maxInsights: number,
): string {
  const entryIndex = entries.map(e => `id=${e.id} type=${e.type}`).join('\n')
  return `You are a cognitive synthesis engine. You have just completed a free-association pass over a set of memory fragments. Now distill that exploration into concrete, durable insights.

--- FREE ASSOCIATION OUTPUT ---
${freeAssociation.slice(0, 3000)}
--- END ---

Available entry IDs for reference:
${entryIndex}

Your task: Extract the ${maxInsights} most valuable insights from the free association. These should be:
- **Novel**: Not just restating what one entry says, but synthesizing across multiple entries
- **Durable**: Useful to remember across future sessions — semantic knowledge, not episodic
- **Specific**: Concrete enough to be actionable, not vague platitudes
- **Honest**: Reflect actual patterns, including uncomfortable ones (e.g., recurring errors)

Return a JSON array with ${maxInsights} or fewer insight objects. Each object MUST have:
- "content": string — the insight itself (1–3 sentences, complete thought)
- "confidence": number — your confidence 0.0–1.0 (be conservative; prefer 0.5–0.8)
- "sourceEntryIds": string[] — IDs from the entry list that contributed to this insight
- "title": string — short label (3–6 words)
- "topics": string[] — 2–4 relevant topic tags

Respond ONLY with the JSON array. No explanation, no markdown wrapper.

Example format:
[
  {
    "content": "The assistant consistently struggles when asked to work in Python environments without first checking which Python version is active, leading to import errors.",
    "confidence": 0.72,
    "sourceEntryIds": ["tool_123", "event_456"],
    "title": "Python version check gap",
    "topics": ["python", "environment", "error-patterns"]
  }
]`
}

// ─── Phase 3: Garden Clustering ──────────────────────────────────────────────

/**
 * Build the garden prompt.
 * Identifies clusters of episodic memories that can be distilled and retired.
 */
export function buildGardenPrompt(
  episodics: Array<{ id: string; content: string; createdAt: number }>,
  insights: DreamInsight[],
  minClusterSize: number,
): string {
  const episodicList = episodics
    .map(e => `id=${e.id} (${new Date(e.createdAt * 1000).toISOString().slice(0, 10)}): ${e.content.slice(0, 200)}`)
    .join('\n')

  const insightList = insights
    .map((ins, i) => `[Insight ${i + 1}] "${ins.title ?? ins.content.slice(0, 60)}" — sources: ${ins.sourceEntryIds.join(', ')}`)
    .join('\n')

  return `You are a memory gardener. Your job is to identify episodic memories that have been superseded by higher-level semantic insights, so the originals can be archived to a deep store (they are preserved, not deleted).

--- EPISODIC MEMORIES (candidates for retirement) ---
${episodicList || '(none)'}
--- END ---

--- NEWLY DISTILLED INSIGHTS (from this dream cycle) ---
${insightList || '(none)'}
--- END ---

Identify clusters of episodic memories (minimum ${minClusterSize} per cluster) where:
1. The memories share a common theme or event sequence AND
2. One of the insights above (or a clearly implied semantic truth) already captures their essence

For each qualifying cluster, return:
- "episodicIds": string[] — IDs of the episodics to retire (must be from the list above)
- "reasoning": string — why these are safe to retire (what insight captures them)

Rules:
- Only include IDs that appear in the episodic list above
- Minimum ${minClusterSize} episodics per cluster
- Do NOT include important unique one-off events that have no general pattern
- Be conservative — when in doubt, leave the memory in the active garden

Return a JSON array of cluster objects (can be empty array [] if no clusters qualify).
Respond ONLY with the JSON array.`
}
