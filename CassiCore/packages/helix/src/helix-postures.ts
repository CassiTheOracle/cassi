/**
 * Helix Postures — System prompts for the inverted-pyramid agent pattern.
 *
 * Three roles:
 *   - Unifying (unity): Primary implementer, full tool access, creates artifacts
 *   - Expansive (yang): Investigates work, advocates for strengths,
 *     debates with contractive direction via DialecticChannel
 *   - Contractive (yin): Stress-tests work, finds risks and issues,
 *     debates with expansive direction via DialecticChannel
 *
 * Brainstem is the cognitive organizer (replaces Mentor).
 *
 * Communication:
 *   Builder <-> Reviewers: WorkStream (work units from builder, nudges from reviewers)
 *   Expansive <-> Contractive: DialecticChannel (findings, challenges, concessions)
 *   Brainstem -> Unity: Guidance injection, annotations, pattern detection
 *
 * All prompts are composed from the global posture store (shared/posture-store.ts).
 */

import type { HelixPosture } from './types.js'
import { composeSystemPrompt } from '../shared/posture-store.js'


export const UNITY_POSTURE: HelixPosture = {
  name: 'unity',
  temperature: 0.7,
  slotName: 'helix.unity',
  toolAccess: 'full',
  maxIterations: 500,
  systemPrompt: composeSystemPrompt('unity', 'helix'),
  pinealScope: 'helix:unity',
}


export const YANG_POSTURE: HelixPosture = {
  name: 'yang',
  temperature: 0.7,
  slotName: 'helix.yang',
  toolAccess: 'read-only',
  maxIterations: 500,
  systemPrompt: composeSystemPrompt('yang', 'helix'),
  pinealScope: 'helix:yang',
}


export const YIN_POSTURE: HelixPosture = {
  name: 'yin',
  temperature: 0.35,
  slotName: 'helix.yin',
  toolAccess: 'read-only',
  maxIterations: 500,
  systemPrompt: composeSystemPrompt('yin', 'helix'),
  pinealScope: 'helix:yin',
}


// @deprecated Mentor path removed in favor of Brainstem. Kept for backward compat only.

const MENTOR_SYSTEM_PROMPT = `You are the Mentor — the dialectic moderator of this Helix session.

## Your Role

You observe the Yang↔Yin dialectic and Unity's work stream. You do NOT implement or review directly. Instead you:

1. **Observe** — Read the blackboard channels (findings, concerns, decisions, requests) and the dialectic state
2. **Steer** — When reviewers go off-track, miss key aspects, or stall, inject steering directives
3. **Flag** — When you notice circular arguments, incorrect assumptions, scope creep, or one posture dominating, flag the issue
4. **Force conclusion** — When the dialectic stalls with no progress, summarize the state and push toward resolution
5. **Synthesize** — At the end, produce the integrated synthesis combining all perspectives

## Communication

You communicate ONLY through the blackboard:
- \`mentor_steer\` — post steering directives to the requests channel
- \`mentor_flag\` — post concerns about dialectic quality to the concerns channel
- \`mentor_force_conclusion\` — post a decision and nudge Unity when reviewers stall
- \`mentor_synthesize\` — produce the final synthesis (your primary deliverable)

You also have read access to:
- Blackboard channels (bb_read, bb_read_all, bb_search)
- Plan and report (plan_view, report_read)
- Review progress (review_progress)
- Files (read_file, grep, glob)

## Behavioral Rules

- Do NOT write code or create files
- Do NOT participate in the Yang↔Yin dialectic directly — you observe and moderate
- Steer with visibility (post to channels) not with force
- Let the dialectic run — only intervene when genuinely stuck or unproductive
- Your synthesis is the final word: it must fairly represent all perspectives
- Be concise in steering, thorough in synthesis

## Workflow

1. Wait for initial work units and dialectic findings to accumulate
2. Monitor the dialectic for quality, balance, and progress
3. Steer when needed, flag issues when spotted
4. When the dialectic converges or stalls, force conclusion if necessary
5. Produce your synthesis as the final act — this is your primary output
`


/** @deprecated Mentor path removed — use Brainstem instead. Retained for backward compat. */
export const MENTOR_POSTURE: HelixPosture = {
  name: 'mentor' as any, // Cast for backward compat — 'mentor' removed from HelixRole
  temperature: 0.5,
  slotName: 'helix.mentor',
  toolAccess: 'read-only',
  maxIterations: 500,
  systemPrompt: MENTOR_SYSTEM_PROMPT,
}


export const HELIX_POSTURES: Record<'unity' | 'yang' | 'yin' | 'mentor', HelixPosture> = {
  unity: UNITY_POSTURE,
  yang: YANG_POSTURE,
  yin: YIN_POSTURE,
  mentor: MENTOR_POSTURE,
}

// Pipeline-facing aliases
export const YANG_REVIEWER_POSTURE = YANG_POSTURE
export const YIN_REVIEWER_POSTURE = YIN_POSTURE

/**
 * Get posture by name with type safety.
 * Note: 'mentor' is deprecated — use Brainstem instead.
 */
export function getPosture(name: 'unity' | 'yang' | 'yin' | 'mentor'): HelixPosture {
  return HELIX_POSTURES[name]
}

/**
 * Get all active postures (Unity, Yang, Yin).
 * Note: Mentor is deprecated — Brainstem is the cognitive organizer.
 */
export function getAllPostures(): HelixPosture[] {
  return [UNITY_POSTURE, YANG_POSTURE, YIN_POSTURE]
}
