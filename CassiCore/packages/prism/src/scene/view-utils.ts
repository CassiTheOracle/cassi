import type { ViewMode } from '../store.js'
import type { ViewModeTransform } from '../views/types.js'
import { temporalDepth } from '../views/temporal-depth.js'
import { potentiationLandscape } from '../views/potentiation.js'
import { flatField } from '../views/flat-field.js'

export const ENGRAM_TYPES = [
  'fact', 'episode', 'decision', 'pattern',
  'abstraction', 'goal', 'file', 'tool', 'session', 'outcome',
  'source_file', 'changeset', 'artifact',
]

const VIEW_MODES: Record<ViewMode, ViewModeTransform> = {
  'temporal-depth': temporalDepth,
  'potentiation-landscape': potentiationLandscape,
  'flat-field': flatField,
}

export function getViewMode(id: ViewMode): ViewModeTransform {
  return VIEW_MODES[id]
}

export function getAllViewModes(): ViewModeTransform[] {
  return Object.values(VIEW_MODES)
}
