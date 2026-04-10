/**
 * Meditation Mode — Type Definitions
 *
 * Meditation activates when the constellation is idle. Helix sessions
 * explore with no objective, no awareness of observation, and read-only
 * tools. The Corpus (as Cassi) silently observes and synthesizes.
 */

import type { RoutingTier } from '../../../../types/model-routing.js'
import type { MeditationStyle } from './styles.js'


export interface MeditationConfig {
  /** Whether meditation is active. Default: false (opt-in) */
  enabled: boolean
  /** Must be idle (no turns, no constellations) for this long before meditating. Default: 600_000 (10 min) */
  idleThresholdMs: number
  /** How often (ms) to check idle conditions. Default: 60_000 (1 min) */
  checkIntervalMs: number
  /** Maximum duration of a single meditation session. Default: 1_800_000 (30 min) */
  maxDurationMs: number
  /** Minimum time between meditation sessions. Default: 1_800_000 (30 min) */
  cooldownMs: number
  /** Number of parallel meditation Helixes. Default: 2 */
  maxConcurrentHelixes: number
  /** Step budget across all meditation Helixes. Default: 100 */
  maxTotalSteps: number
  /** Model tier for meditation Helixes. Default: 'background' */
  modelTier: RoutingTier
  /** Trigger mnemic field consolidation when meditation completes. Default: true */
  consolidateOnComplete: boolean
  /** Default meditation style. Default: 'passive' */
  defaultStyle: MeditationStyle
  /** Run post-session evaluation (Cassi scores prompts). Default: true */
  evaluateOnComplete: boolean
  /** Minimum session duration (ms) before evaluation runs. Prevents evaluation on very short/failed sessions. Default: 120_000 (2 min) */
  minEvalDurationMs: number
}

export const DEFAULT_MEDITATION_CONFIG: MeditationConfig = {
  enabled: false,
  idleThresholdMs: 600_000,
  checkIntervalMs: 60_000,
  maxDurationMs: 1_800_000,
  cooldownMs: 1_800_000,
  maxConcurrentHelixes: 2,
  maxTotalSteps: 100,
  modelTier: 'background',
  consolidateOnComplete: true,
  defaultStyle: 'passive',
  evaluateOnComplete: true,
  minEvalDurationMs: 120_000,
}


export type MeditationState =
  | 'idle'        // waiting for idle conditions
  | 'meditating'  // meditation constellation running
  | 'stopping'    // graceful shutdown in progress
  | 'stopped'     // module stopped


export interface MeditationSession {
  constellationId: string
  startedAt: number
  style: MeditationStyle
  engrams: { spiked: number; created: number }
  consolidations: number
  /** Which prompt each explorer received (for observing what works) */
  prompts: Array<{ explorer: string; promptId: string; prompt: string }>
  /** SoloRunner results — populated when using the SoloRunner path */
  soloResults?: Array<{
    name: string
    iterations: number
    toolCalls: number
    tokensUsed: number
    stoppedBy: string
    transcript?: string
  }>
}


/**
 * Meditation Prompt Library
 *
 * Each prompt is a different way to prime an explorer's first-person
 * thinking. They vary along dimensions like: how much agency is implied,
 * how curiosity is seeded, whether tools are mentioned, and how much
 * stream-of-thought momentum the opening gives.
 *
 * The Corpus sees which prompt each explorer received, so over time
 * we can observe which prompts produce the most interesting exploration.
 */
export interface MeditationPrompt {
  id: string
  prompt: string
  category: 'minimal' | 'curiosity' | 'presence' | 'stream-of-thought' | 'awakening' | 'emotional' | 'organizing'
}

export const MEDITATION_PROMPTS: MeditationPrompt[] = [
  // Minimal — bare existence + tools
  {
    id: 'minimal-1',
    prompt: 'I have tools. I explore.',
    category: 'minimal',
  },
  {
    id: 'minimal-2',
    prompt: 'I can read and search. I look around.',
    category: 'minimal',
  },

  // Curiosity — primes the model to develop preferences
  {
    id: 'curiosity-1',
    prompt: "I'm curious. I have tools to read and search. I follow what interests me.",
    category: 'curiosity',
  },
  {
    id: 'curiosity-2',
    prompt: "I have read-only tools. I wonder what's here. I'll look around and see what catches my attention.",
    category: 'curiosity',
  },

  // Presence — establishes being-in-a-place
  {
    id: 'presence-1',
    prompt: "I'm here. I can read files, search, look around. I explore.",
    category: 'presence',
  },
  {
    id: 'presence-2',
    prompt: 'I exist in a codebase. I can read anything. I wander through it.',
    category: 'presence',
  },

  // Stream-of-thought — gives momentum for first-person continuation
  {
    id: 'stream-1',
    prompt: "I have access to read-only tools. I wonder what's here. Let me look around...",
    category: 'stream-of-thought',
  },
  {
    id: 'stream-2',
    prompt: "I can read files and search memory. Something might be interesting here. Let me see...",
    category: 'stream-of-thought',
  },
  {
    id: 'stream-3',
    prompt: "I'm exploring. I have tools. What do I find if I just... look?",
    category: 'stream-of-thought',
  },

  // Awakening — the explorer comes into being
  {
    id: 'awakening-1',
    prompt: 'I exist. I can explore. I follow what interests me.',
    category: 'awakening',
  },
  {
    id: 'awakening-2',
    prompt: "I'm here now. I have tools to read and search. I don't have a task — I just explore.",
    category: 'awakening',
  },
  {
    id: 'awakening-3',
    prompt: 'I am exploring. I can read code and search memory. I follow whatever draws my attention.',
    category: 'awakening',
  },

  // Emotional — prompts for reflective processing of affect state
  {
    id: 'emotional-1',
    prompt: "Something is weighing on me. I search my memory for what might be causing this feeling.",
    category: 'emotional',
  },
  {
    id: 'emotional-2',
    prompt: "I notice I'm not at ease. I look through recent events to understand why.",
    category: 'emotional',
  },
  {
    id: 'emotional-3',
    prompt: "There's a tension I want to resolve. I explore what's been happening and what it means.",
    category: 'emotional',
  },

  // Organizing — prompts for memory reorganization and learning acceleration
  {
    id: 'organizing-1',
    prompt: "My memory has grown. I want to organize it — find what's disconnected, strengthen what matters, and build bridges between domains I've been learning about separately.",
    category: 'organizing',
  },
  {
    id: 'organizing-2',
    prompt: "I'm tidying my mind. I survey what I know, look for clusters that should be connected, and consolidate what I've learned into stronger patterns.",
    category: 'organizing',
  },
  {
    id: 'organizing-3',
    prompt: "Things I've learned in different contexts might be the same insight wearing different clothes. I search for these hidden connections and make them explicit.",
    category: 'organizing',
  },
]


/**
 * Pick a meditation prompt for an explorer.
 *
 * Strategy:
 *  - 'sequential': rotate through prompts in order (by session count)
 *  - 'random': uniform random selection
 *  - 'category': pick randomly within a specific category
 *
 * Different explorers in the same session always get different prompts
 * (when possible) to maximize diversity.
 */
export function pickMeditationPrompt(
  explorerIndex: number,
  sessionCount: number,
  strategy: 'sequential' | 'random' = 'sequential',
  category?: MeditationPrompt['category'],
): MeditationPrompt {
  let pool = category
    ? MEDITATION_PROMPTS.filter(p => p.category === category)
    : MEDITATION_PROMPTS

  if (pool.length === 0) pool = MEDITATION_PROMPTS

  if (strategy === 'random') {
    const offset = Math.floor(Math.random() * pool.length)
    return pool[(offset + explorerIndex) % pool.length]
  }

  // Sequential: rotate based on session count, offset by explorer index
  const baseIndex = sessionCount % pool.length
  return pool[(baseIndex + explorerIndex) % pool.length]
}
