import type { MeditationPrompt } from './types.js'
import type { Affect } from '../../mnemic-field/types.js'

export type MeditationStyle = 'passive' | 'active' | 'focused' | 'reflective'

export interface StyleConfig {
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
  reflective: {
    categoryPreferences: ['emotional', 'presence'],
    description: 'Emotional processing. Cassi explores what she is feeling and why.',
  },
}

const AFFECT_INTENSITY_THRESHOLD = 0.45

export function selectStyle(
  lastTurnAt: number,
  idleThresholdMs: number,
  defaultStyle: MeditationStyle,
  affect?: Affect | null,
): MeditationStyle {
  if (affect && isEmotionallyCharged(affect)) return 'reflective'

  if (lastTurnAt <= 0) return defaultStyle

  const idleMs = Date.now() - lastTurnAt
  if (idleMs < idleThresholdMs * 2) return 'active'
  if (idleMs > idleThresholdMs * 4) return 'passive'
  return defaultStyle
}

function isEmotionallyCharged(affect: Affect): boolean {
  const intensity = Math.abs(affect.valence) * 0.7 + affect.arousal * 0.3
  return intensity > AFFECT_INTENSITY_THRESHOLD
}
