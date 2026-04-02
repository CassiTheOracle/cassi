/*
 * Constellation Templates — Preset Helix configurations.
 *
 * Templates are factory functions that produce a set of FlexPostures
 * for common Helix patterns. They're a convenience layer — users can
 * always define custom postures directly.
 *
 * Note: Mentor posture was removed from all templates. The Brainstem
 * handles per-Helix tactical organization (scoring, pattern detection,
 * guidance), and the Corpus handles Constellation-level strategic
 * coordination (cross-Helix patterns, spawn evaluation, synthesis).
 *
 * Available templates:
 *   - standard:       Unity + Yang + Yin (classic Helix, 3 postures)
 *   - research:       Unity + Yang + Yin + 2 Researchers (5 postures)
 *   - implementation: 2 Unities + Yang + Yin (parallel build, 4 postures)
 *   - review:         Unity + 2 Yangs + 2 Yins (heavy review, 5 postures)
 *   - minimal:        Unity + single Reviewer (lightweight, 2 postures)
 */

import type { FlexPosture, ConstellationTemplate } from './types.js'
import { createPostureSet } from './flex-posture.js'


// Standard Template — Classic Helix (3 postures)

const STANDARD_POSTURES: FlexPosture[] = [
  {
    name: 'unity',
    instruction: 'Implement the goal. You are the primary worker — create artifacts, write code, make changes. Move forward with confidence.',
    energy: 'unity',
    toolAccess: 'full',
    channels: { workStream: 'producer', constellationBoard: true },
    canSpawnDrones: true,
    maxIterations: 500,
  },
  {
    name: 'yang',
    instruction: 'Review work assertively. Advocate for strengths, challenge weak criticism, find genuine opportunities. Debate with the contractive reviewer.',
    energy: 'yang',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 100,
  },
  {
    name: 'yin',
    instruction: 'Review work cautiously. Find risks, stress-test assumptions, identify failure modes. Debate with the expansive reviewer.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 100,
  },
]


// Research Template — Extra researchers for investigation-heavy work

const RESEARCH_POSTURES: FlexPosture[] = [
  ...STANDARD_POSTURES,
  {
    name: 'researcher-alpha',
    instruction: 'Investigate the codebase architecture and execution flows relevant to the goal. Share findings proactively. Focus on structural understanding — how components connect, what calls what, where data flows.',
    energy: 'yang',
    toolAccess: 'read-only+memory',
    channels: { dialectic: true, constellationBoard: true },
    canSpawnDrones: true,
    maxIterations: 80,
  },
  {
    name: 'researcher-beta',
    instruction: 'Investigate edge cases, failure modes, and integration boundaries relevant to the goal. Share findings proactively. Focus on operational understanding — what breaks under load, where errors propagate, what assumptions are fragile.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { dialectic: true, constellationBoard: true },
    canSpawnDrones: true,
    maxIterations: 80,
  },
]


// Implementation Template — Two workers for parallel building (4 postures)

const IMPLEMENTATION_POSTURES: FlexPosture[] = [
  {
    name: 'unity-primary',
    instruction: 'Implement the core functionality of the goal. You are the primary builder — focus on the main deliverable. Coordinate with the secondary builder through the blackboard.',
    energy: 'unity',
    toolAccess: 'full',
    channels: { workStream: 'producer', constellationBoard: true },
    canSpawnDrones: true,
    maxIterations: 500,
  },
  {
    name: 'unity-secondary',
    instruction: 'Implement supporting functionality — tests, documentation, configuration, and integration glue. Coordinate with the primary builder through the blackboard to avoid conflicts.',
    energy: 'unity',
    toolAccess: 'full',
    channels: { workStream: 'producer', constellationBoard: true },
    maxIterations: 300,
  },
  {
    name: 'yang',
    instruction: 'Review work from both builders assertively. Advocate for strengths, challenge weak criticism, ensure the two builders are producing coherent output.',
    energy: 'yang',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 100,
  },
  {
    name: 'yin',
    instruction: 'Review work from both builders cautiously. Find integration risks between the two work streams, stress-test assumptions, identify conflicts.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 100,
  },
]


// Review Template — Extra reviewers for quality-critical work (5 postures)

const REVIEW_POSTURES: FlexPosture[] = [
  {
    name: 'unity',
    instruction: 'Implement the goal. You are the primary worker — create artifacts, write code, make changes. Expect thorough review from four reviewers.',
    energy: 'unity',
    toolAccess: 'full',
    channels: { workStream: 'producer', constellationBoard: true },
    canSpawnDrones: true,
    maxIterations: 500,
  },
  {
    name: 'yang-correctness',
    instruction: 'Review for correctness. Does the implementation do what it should? Find genuine strengths in the approach. Challenge risk assessments that are overly pessimistic.',
    energy: 'yang',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 80,
  },
  {
    name: 'yang-design',
    instruction: 'Review for design quality. Is the architecture sound? Are patterns consistent? Advocate for the design choices that are genuinely good. Challenge aesthetic objections that lack substance.',
    energy: 'yang',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 80,
  },
  {
    name: 'yin-safety',
    instruction: 'Review for safety and regression risk. What could break? What edge cases are missed? What assumptions are fragile? Find the failure modes that would hurt most.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 80,
  },
  {
    name: 'yin-integration',
    instruction: 'Review for integration impact. What existing code is affected? What callers break? What tests need updating? Find the blast radius the builder might miss.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 80,
  },
]

/**
 * @dep callers: resolvePostures (core/intelligence/constellation/templates.ts), resolvePostures (core/intelligence/constellation/constellation-pipeline.ts)
 * @dep calls: createPostureSet
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function getTemplatePostures(template: ConstellationTemplate): FlexPosture[] {
  switch (template) {
    case 'standard':
      return createPostureSet(STANDARD_POSTURES)
    case 'research':
      return createPostureSet(RESEARCH_POSTURES)
    case 'implementation':
      return createPostureSet(IMPLEMENTATION_POSTURES)
    case 'review':
      return createPostureSet(REVIEW_POSTURES)
    case 'minimal':
      return createPostureSet([
        { name: 'unity', instruction: 'Implement the goal. You are the primary worker — create artifacts and move forward.', energy: 'unity', toolAccess: 'full', channels: { workStream: 'producer', constellationBoard: true }, maxIterations: 200 },
        { name: 'reviewer', instruction: 'Provide short, focused review cycles — surface major issues quickly.', energy: 'yin', toolAccess: 'read-only+memory', channels: { workStream: 'consumer', dialectic: true, constellationBoard: true }, maxIterations: 80 },
      ])
  }
}

export function listTemplates(): ConstellationTemplate[] {
  return ['standard', 'research', 'implementation', 'review', 'minimal']
}

export function describeTemplate(template: ConstellationTemplate): string {
  switch (template) {
    case 'standard':
      return 'Unity + Yang + Yin — balanced build + review (Brainstem organizes)'
    case 'research':
      return 'Standard plus two researchers — good for exploratory tasks'
    case 'implementation':
      return 'Two builders + reviewers — parallel implementation (Brainstem organizes)'
    case 'review':
      return 'One builder + four reviewers — high-quality review (Brainstem organizes)'
    case 'minimal':
      return 'One builder + one reviewer — fast, lightweight'
  }
}

export function resolvePostures(opts?: { postures?: FlexPosture[]; template?: ConstellationTemplate }): FlexPosture[] {
  const postures = opts?.postures
  if (postures && postures.length > 0) return createPostureSet(postures)
  const template = opts?.template ?? 'standard'
  return getTemplatePostures(template)
}
