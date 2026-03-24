/**
 * Helix Postures — System prompts for the inverted-pyramid agent pattern.
 *
 * Three concurrent postures:
 *   - Unity (Worker): Primary implementer, full tool access, creates artifacts
 *   - Yang (Assertive Reviewer): Investigates Unity's work, advocates for strengths,
 *     debates with Yin via DialecticChannel
 *   - Yin (Cautious Reviewer): Stress-tests Unity's work, finds risks and issues,
 *     debates with Yang via DialecticChannel
 *
 * Communication:
 *   Unity <-> Reviewers: WorkStream (work units from Unity, nudges from reviewers)
 *   Yang  <-> Yin:       DialecticChannel (findings, challenges, concessions)
 *
 * Prompts are composed from the global posture store (shared/posture-store.ts).
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
}


export const YANG_POSTURE: HelixPosture = {
  name: 'yang',
  temperature: 0.7,
  slotName: 'helix.yang',
  toolAccess: 'read-only',
  maxIterations: 100,
  systemPrompt: composeSystemPrompt('yang', 'helix'),
}


export const YIN_POSTURE: HelixPosture = {
  name: 'yin',
  temperature: 0.35,
  slotName: 'helix.yin',
  toolAccess: 'read-only',
  maxIterations: 100,
  systemPrompt: composeSystemPrompt('yin', 'helix'),
}


export const HELIX_POSTURES: Record<'unity' | 'yang' | 'yin', HelixPosture> = {
  unity: UNITY_POSTURE,
  yang: YANG_POSTURE,
  yin: YIN_POSTURE,
}

// Pipeline-facing aliases
export const YANG_REVIEWER_POSTURE = YANG_POSTURE
export const YIN_REVIEWER_POSTURE = YIN_POSTURE

/**
 * Get posture by name with type safety.
 */
export function getPosture(name: 'unity' | 'yang' | 'yin'): HelixPosture {
  return HELIX_POSTURES[name]
}

/**
 * Get all postures for concurrent execution.
 */
export function getAllPostures(): HelixPosture[] {
  return [UNITY_POSTURE, YANG_POSTURE, YIN_POSTURE]
}
