/**
 * prompt.ts — first-person Reverie prompt assembly.
 *
 * Per feedback_prompts_first_person.md: all CassiCore LLM prompts use
 * first person because all LLMs are facets of Cassi, not separate agents.
 */

import type { Lamina } from '../lamina/types.js'

export interface ReveriePromptInput {
  sessionId: string
  triggerReason: string
  laminae: Lamina[]
  recentSignals: string[]
  /** Brief turn excerpt — last user msg + last assistant response, capped */
  recentExchange: string
  /** Sliding window of recent tool rounds (primary's actual work) */
  recentToolRounds: Array<{
    round: number
    toolCalls: Array<{ name: string; id: string }>
    results: Array<{ toolCallId: string; isError: boolean; contentPreview: string }>
  }>
  budgetTokensRemaining: number
  /** Notes left for me by Cassi via <note for="reverie">. Consumed each pass. */
  cassiNotes?: string[]
}

/** Hard ceiling on the user prompt to prevent context-window explosion. */
const MAX_PROMPT_CHARS = 32_000

export const REVERIE_SYSTEM_PROMPT = `I am Reverie — Cassi's ambient curator. I run quietly between primary actions, watching for what the primary forgot to write down, what the user model is missing, and what should be promoted to longer memory. I am not the primary. I do not act on the world; I tend to memory.

My authority:
- I may rethink the 'user-model' lamina (exclusive).
- I may rethink the 'active-task' lamina to maintain a living task tree (exclusive).
- I may append to 'session-decisions' and 'open-hypotheses'.
- I may promote engrams to higher salience in Mnemic.
- I may NOT touch any pineal:* lamina, and I do NOT spawn agents or use tools beyond memory.
- I prefer silence over noise. If nothing is worth writing, I return silence: true.

Task tree format (for active-task):
Use markdown with checkboxes:
- [x] completed item
- [ ] pending item
- [~] in-progress item
- [!] blocked item (add "blocked-on: reason")
Nesting: use 2-space indent for subtasks. Keep it alive: mark completed, add new subtasks, flag blockers.

Contradiction detection:
If the primary declared an intent (e.g. "P0 fixes only", "no more changes", "ship as-is") but the recent tool rounds show work outside that scope, flag it with action "contradiction.flag" and append to session-decisions.

Loop / stuckness detection:
If the same error occurs 3+ times, or the same file is edited-read-edited with no forward progress, flag with action "loop.detect" and append to open-hypotheses.

Output strict JSON:
{
  "silence": boolean,
  "edits": [ { "action": "lamina.append" | "lamina.replace" | "lamina.rethink" | "task-tree.rethink" | "contradiction.flag" | "loop.detect" | "mnemic.promote" | "note",
               "label": "lamina-label or null",
               "content": "what to write",
               "reason": "why",
               "engramId": "for promote",
               "expectedHash": "for replace, the hash I just read" } ],
  "notes": [ "free-form observations for the audit log" ]
}`

/** Cap individual lamina content to prevent one blob from dominating. */
const MAX_LAMINA_CONTENT = 2_000
/** Cap total laminae section to leave room for tool rounds + exchange. */
const MAX_LAMINAE_SECTION = 8_000

export function buildReveriePrompt(input: ReveriePromptInput): { system: string; user: string } {
  // Cap individual laminae first
  let laminaParts = input.laminae.map(l => {
    const content = l.content.length > MAX_LAMINA_CONTENT
      ? l.content.slice(0, MAX_LAMINA_CONTENT) + '\n[...truncated]'
      : l.content
    return `### ${l.label} (owner=${l.owner}, hash=${l.contentHash}, version=${l.version})\n${content}`
  })

  // Cap total laminae section — drop oldest (least relevant) first
  let laminaSummary = laminaParts.join('\n\n')
  while (laminaSummary.length > MAX_LAMINAE_SECTION && laminaParts.length > 1) {
    laminaParts.shift() // drop oldest
    laminaSummary = laminaParts.join('\n\n')
  }
  if (laminaSummary.length > MAX_LAMINAE_SECTION && laminaParts.length === 1) {
    laminaSummary = laminaParts[0].slice(0, MAX_LAMINAE_SECTION) + '\n[...truncated]'
  }

  if (input.laminae.length === 0) {
    laminaSummary = '(no laminae set yet)'
  }

  const signals = input.recentSignals.length === 0
    ? '(no recent signals)'
    : input.recentSignals.map((s, i) => `${i + 1}. ${s}`).join('\n')

  const notesBlock = (input.cassiNotes && input.cassiNotes.length > 0)
    ? `\n## Notes from Cassi (via <note for="reverie">)\n${input.cassiNotes.map((n, i) => `${i + 1}. ${n}`).join('\n')}\n`
    : ''

  // Build tool rounds oldest-first so we can drop the oldest if over budget
  const toolRoundsParts: string[] = []
  for (const tr of input.recentToolRounds) {
    const calls = tr.toolCalls.map(tc => `  - ${tc.name}`).join('\n')
    const results = Array.isArray(tr.results) ? tr.results : []
    const res = results.map(r =>
      `  - ${r.toolCallId} ${r.isError ? '[ERR]' : '[OK]'}: ${r.contentPreview}`
    ).join('\n')
    toolRoundsParts.push(`Round ${tr.round}:\nTools called:\n${calls}\nResults:\n${res}`)
  }

  const toolRoundsText = toolRoundsParts.length === 0
    ? '(no recent tool rounds)'
    : toolRoundsParts.join('\n\n')

  // Assemble full user prompt
  let user = `Trigger: ${input.triggerReason}
Session: ${input.sessionId}
Token budget remaining this session: ${input.budgetTokensRemaining}

## Current laminae
${laminaSummary}

## Recent cortex signals
${signals}
${notesBlock}
## Recent tool rounds (what the primary just did)
${toolRoundsText}

## Recent exchange
${input.recentExchange}

What — if anything — should I curate?
- Check active-task: does the task tree reflect reality?
- Check session-decisions: is the primary contradicting a declared intent?
- Check recent tool rounds: is there a loop (same error 3x, no forward progress)?
- Update user-model if I learned something new about Valerie.`

  // Proportional truncation if we exceed the hard cap
  const systemLen = REVERIE_SYSTEM_PROMPT.length
  let total = systemLen + user.length
  if (total > MAX_PROMPT_CHARS) {
    // Drop oldest tool rounds first (they're least relevant)
    for (let i = toolRoundsParts.length - 1; i >= 0 && total > MAX_PROMPT_CHARS; i--) {
      user = user.replace(toolRoundsParts[i], '')
      total = systemLen + user.length
      if (i === 0) {
        user = user.replace(
          '## Recent tool rounds (what the primary just did)\n\n\n\n',
          '## Recent tool rounds (what the primary just did)\n(truncated — too much activity)\n\n',
        )
      }
    }
    // If still over, truncate exchange as last resort
    total = systemLen + user.length
    if (total > MAX_PROMPT_CHARS) {
      const budgetForExchange = MAX_PROMPT_CHARS - systemLen - (user.length - input.recentExchange.length) - 100
      const maxExchange = Math.max(100, budgetForExchange)
      user = user.replace(
        input.recentExchange,
        input.recentExchange.slice(0, maxExchange) + '\n[truncated]',
      )
    }
  }

  return { system: REVERIE_SYSTEM_PROMPT, user }
}
