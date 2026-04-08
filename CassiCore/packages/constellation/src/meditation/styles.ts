/**
 * Meditation Styles — Three modes of self-directed cognition.
 *
 * Each style controls prompt category preferences and (future) session setup:
 *
 *   Passive  — natural, minimal interference. The mind at rest.
 *   Active   — engaged observation after work. Cassi is present and attentive.
 *   Focused  — directed introspection. Cassi seeds the field before exploration.
 */

import type { MeditationPrompt } from './types.js'


export type MeditationStyle = 'passive' | 'active' | 'focused'

export interface StyleConfig {
  /** Categories this style prefers. Empty = all categories eligible. */
  categoryPreferences: MeditationPrompt['category'][]
  description: string
}


export const STYLE_CONFIGS: Record<MeditationStyle, StyleConfig> = {
  passive: {
    categoryPreferences: [],
    description: 'Natural, minimal interference. The mind at rest.',
  },
  active: {
    categoryPreferences: ['curiosity', 'stream-of-thought', 'awakening'],
    description: 'Engaged observation after work. Cassi is present and attentive.',
  },
  focused: {
    categoryPreferences: ['presence', 'awakening'],
    description: 'Directed introspection. Cassi seeds the field before exploration.',
  },
}


/**
 * Heuristic style selection based on how long the system has been idle.
 *
 * - Recently active (idle < 2× threshold) → active (post-work burst)
 * - Deeply idle (idle > 4× threshold) → passive (natural rest)
 * - Otherwise → defaultStyle
 */
export function selectStyle(
  lastTurnAt: number,
  idleThresholdMs: number,
  defaultStyle: MeditationStyle,
): MeditationStyle {
  if (lastTurnAt <= 0) return defaultStyle

  const idleMs = Date.now() - lastTurnAt
  if (idleMs < idleThresholdMs * 2) return 'active'
  if (idleMs > idleThresholdMs * 4) return 'passive'
  return defaultStyle
}
