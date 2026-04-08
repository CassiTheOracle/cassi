/**
 * Meditation Events — Lifecycle events emitted to the EventBus.
 *
 * Events follow the `meditation:*` namespace. The Cognitive Feed module
 * routes these to the meditation Telegram topic for real-time observation.
 *
 * Event types:
 *   meditation:started             — session began
 *   meditation:stopped             — session ended
 *   meditation:evaluation-complete — Cassi finished scoring prompts
 *   meditation:prompt-created      — Cassi authored a new prompt
 *   meditation:prompt-retired      — a prompt was retired
 *   meditation:style-selected      — meditation style was chosen
 *   meditation:evolution-adjusted  — mutation temperature changed
 *   meditation:focused-seeding     — focused mode kindled the mnemic field
 */

import type { IEventBus } from '../../../../types/interfaces.js'
import type { MeditationStyle } from './styles.js'


export interface MeditationStartedEvent {
  type: 'meditation:started'
  constellationId: string
  style: MeditationStyle
  prompts: Array<{ explorer: string; promptId: string; prompt: string }>
  timestamp: number
}

export interface MeditationStoppedEvent {
  type: 'meditation:stopped'
  constellationId: string
  style: MeditationStyle
  reason: string
  durationMs: number
  engrams: { spiked: number; created: number }
  consolidations: number
  timestamp: number
}

export interface MeditationEvaluationCompleteEvent {
  type: 'meditation:evaluation-complete'
  constellationId: string
  style: MeditationStyle
  scores: Array<{ promptId: string; explorerName: string; overallScore: number }>
  summary: string
  evalDurationMs: number
  evalTokensUsed: number
  timestamp: number
}

export interface MeditationPromptCreatedEvent {
  type: 'meditation:prompt-created'
  promptId: string
  parentId: string
  content: string
  category: string
  rationale: string
  timestamp: number
}

export interface MeditationPromptRetiredEvent {
  type: 'meditation:prompt-retired'
  promptId: string
  reason: string
  avgScore: number
  timesUsed: number
  timestamp: number
}

export interface MeditationStyleSelectedEvent {
  type: 'meditation:style-selected'
  style: MeditationStyle
  reason: string
  idleMs: number
  timestamp: number
}

export interface MeditationEvolutionAdjustedEvent {
  type: 'meditation:evolution-adjusted'
  oldTemperature: number
  newTemperature: number
  recentMutationAvg: number
  recentLibraryAvg: number
  direction: 'warmer' | 'cooler' | 'stable'
  timestamp: number
}

export interface MeditationFocusedSeedingEvent {
  type: 'meditation:focused-seeding'
  constellationId: string
  focusTopics: string[]
  engramsKindled: number
  seedingDurationMs: number
  timestamp: number
}

export interface MeditationSelfAwarenessEvent {
  type: 'meditation:self-awareness'
  helixId: string
  stepIndex: number
  confidence: number
  fileTrigger?: { path: string; category: string; weight: number }
  reasoningMatch?: { label: string; weight: number; excerpt: string }
  excerpt: string
  timestamp: number
}

export type MeditationEvent =
  | MeditationStartedEvent
  | MeditationStoppedEvent
  | MeditationEvaluationCompleteEvent
  | MeditationPromptCreatedEvent
  | MeditationPromptRetiredEvent
  | MeditationStyleSelectedEvent
  | MeditationEvolutionAdjustedEvent
  | MeditationFocusedSeedingEvent
  | MeditationSelfAwarenessEvent


/**
 * Emit a meditation event to the event bus.
 * Casts through `any` because the RuntimeEvent union may not include
 * meditation types yet — the event bus dispatches on string type regardless.
 */
export function emitMeditationEvent(eventBus: IEventBus | undefined, event: MeditationEvent): void {
  if (!eventBus) return
  void (eventBus as any).emit(event)
}
