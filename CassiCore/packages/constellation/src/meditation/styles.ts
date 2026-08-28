import type { MeditationPrompt } from './types.js'
import type { Affect } from '@cassicore/mnemic-field'

export type MeditationStyle = 'passive' | 'active' | 'focused' | 'reflective' | 'organizing' | 'self-modeling'

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
  organizing: {
    categoryPreferences: ['organizing'],
    description: 'Memory reorganization. Cassi strengthens connections, bridges clusters, and accelerates learning across the entire brain.',
  },
  'self-modeling': {
    categoryPreferences: ['self-modeling'],
    description: 'Architectural self-knowledge hygiene. Cassi cleans, reclassifies, grounds, and distills the self-model into sharper principles, patterns, and weaknesses.',
  },
}

const AFFECT_INTENSITY_THRESHOLD = 0.45

/**
 * How many regular sessions between automatic organizing sessions.
 * After every N non-organizing sessions, selectStyle may choose
 * 'organizing' if the system has been idle long enough (deep idle).
 */
const ORGANIZING_INTERVAL = 5

export function selectStyle(
  lastTurnAt: number,
  idleThresholdMs: number,
  defaultStyle: MeditationStyle,
  affect?: Affect | null,
  sessionCount?: number,
): MeditationStyle {
  if (affect && isEmotionallyCharged(affect)) return 'reflective'

  if (lastTurnAt <= 0) return defaultStyle

  const idleMs = Date.now() - lastTurnAt

  // Periodic organizing: during deep idle, every Nth session reorganizes
  // the mnemic field to accelerate future learning across all domains.
  if (
    sessionCount !== undefined &&
    sessionCount > 0 &&
    sessionCount % ORGANIZING_INTERVAL === 0 &&
    idleMs > idleThresholdMs * 3
  ) {
    return 'organizing'
  }

  if (idleMs < idleThresholdMs * 2) return 'active'
  if (idleMs > idleThresholdMs * 4) return 'passive'
  return defaultStyle
}

function isEmotionallyCharged(affect: Affect): boolean {
  const intensity = Math.abs(affect.valence) * 0.7 + affect.arousal * 0.3
  return intensity > AFFECT_INTENSITY_THRESHOLD
}
