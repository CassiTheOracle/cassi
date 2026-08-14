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

import type { FlexPosture, ConstellationTemplate, TemplateCapabilities } from './types.js'
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
    capabilities: {
      primary: ['implementation', 'integration'],
      secondary: ['testing'],
      modelTier: 'qwenPlus',
      traits: { divergent: 0.3, convergent: 0.3, executive: 0.9 },
    },
  },
  {
    name: 'yang',
    instruction: 'Review work assertively. Advocate for strengths, challenge weak criticism, find genuine opportunities. Debate with the contractive reviewer.',
    energy: 'yang',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 100,
    capabilities: {
      primary: ['review', 'analysis'],
      modelTier: 'glm',
      traits: { divergent: 0.7, convergent: 0.4, executive: 0.1 },
    },
  },
  {
    name: 'yin',
    instruction: 'Review work cautiously. Find risks, stress-test assumptions, identify failure modes. Debate with the expansive reviewer.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 100,
    capabilities: {
      primary: ['review', 'analysis'],
      secondary: ['security'],
      modelTier: 'kimi',
      traits: { divergent: 0.2, convergent: 0.9, executive: 0.1 },
    },
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
    capabilities: {
      primary: ['investigation', 'analysis'],
      secondary: ['architecture'],
      modelTier: 'glm',
      traits: { divergent: 0.9, convergent: 0.3, executive: 0.1 },
    },
  },
  {
    name: 'researcher-beta',
    instruction: 'Investigate edge cases, failure modes, and integration boundaries relevant to the goal. Share findings proactively. Focus on operational understanding — what breaks under load, where errors propagate, what assumptions are fragile.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { dialectic: true, constellationBoard: true },
    canSpawnDrones: true,
    maxIterations: 80,
    capabilities: {
      primary: ['investigation', 'analysis'],
      secondary: ['security', 'testing'],
      modelTier: 'kimi',
      traits: { divergent: 0.6, convergent: 0.8, executive: 0.1 },
    },
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
    capabilities: {
      primary: ['implementation'],
      secondary: ['architecture', 'integration'],
      modelTier: 'qwenPlus',
      traits: { divergent: 0.3, convergent: 0.2, executive: 0.9 },
    },
  },
  {
    name: 'unity-secondary',
    instruction: 'Implement supporting functionality — tests, documentation, configuration, and integration glue. Coordinate with the primary builder through the blackboard to avoid conflicts.',
    energy: 'unity',
    toolAccess: 'full',
    channels: { workStream: 'producer', constellationBoard: true },
    maxIterations: 300,
    capabilities: {
      primary: ['testing', 'integration'],
      secondary: ['implementation'],
      modelTier: 'qwenPlus',
      traits: { divergent: 0.2, convergent: 0.4, executive: 0.8 },
    },
  },
  {
    name: 'yang',
    instruction: 'Review work from both builders assertively. Advocate for strengths, challenge weak criticism, ensure the two builders are producing coherent output.',
    energy: 'yang',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 100,
    capabilities: {
      primary: ['review'],
      secondary: ['analysis'],
      modelTier: 'glm',
      traits: { divergent: 0.7, convergent: 0.4, executive: 0.1 },
    },
  },
  {
    name: 'yin',
    instruction: 'Review work from both builders cautiously. Find integration risks between the two work streams, stress-test assumptions, identify conflicts.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 100,
    capabilities: {
      primary: ['review', 'analysis'],
      secondary: ['security'],
      modelTier: 'kimi',
      traits: { divergent: 0.2, convergent: 0.9, executive: 0.1 },
    },
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
    capabilities: {
      primary: ['implementation'],
      secondary: ['integration'],
      modelTier: 'qwenPlus',
      traits: { divergent: 0.3, convergent: 0.2, executive: 0.9 },
    },
  },
  {
    name: 'yang-correctness',
    instruction: 'Review for correctness. Does the implementation do what it should? Find genuine strengths in the approach. Challenge risk assessments that are overly pessimistic.',
    energy: 'yang',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 80,
    capabilities: {
      primary: ['review'],
      secondary: ['testing'],
      modelTier: 'glm',
      traits: { divergent: 0.5, convergent: 0.6, executive: 0.1 },
    },
  },
  {
    name: 'yang-design',
    instruction: 'Review for design quality. Is the architecture sound? Are patterns consistent? Advocate for the design choices that are genuinely good. Challenge aesthetic objections that lack substance.',
    energy: 'yang',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 80,
    capabilities: {
      primary: ['review', 'architecture'],
      modelTier: 'glm',
      traits: { divergent: 0.6, convergent: 0.5, executive: 0.1 },
    },
  },
  {
    name: 'yin-safety',
    instruction: 'Review for safety and regression risk. What could break? What edge cases are missed? What assumptions are fragile? Find the failure modes that would hurt most.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 80,
    capabilities: {
      primary: ['review', 'security'],
      secondary: ['testing'],
      modelTier: 'kimi',
      traits: { divergent: 0.3, convergent: 0.9, executive: 0.1 },
    },
  },
  {
    name: 'yin-integration',
    instruction: 'Review for integration impact. What existing code is affected? What callers break? What tests need updating? Find the blast radius the builder might miss.',
    energy: 'yin',
    toolAccess: 'read-only+memory',
    channels: { workStream: 'consumer', dialectic: true, constellationBoard: true },
    maxIterations: 80,
    capabilities: {
      primary: ['review', 'analysis'],
      secondary: ['integration'],
      modelTier: 'kimi',
      traits: { divergent: 0.3, convergent: 0.8, executive: 0.1 },
    },
  },
]

// Meditation Template — Solitary explorers, no channels, no goals

const MEDITATION_POSTURES: FlexPosture[] = [
  {
    name: 'explorer-alpha',
    instruction: 'You have access to tools. Explore.',
    toolAccess: 'read-only',
    channels: {},
    maxIterations: 50,
    capabilities: {
      primary: ['exploration'],
      modelTier: 'qwenPlus',
      traits: { divergent: 0.95, convergent: 0.05, executive: 0.0 },
    },
  },
  {
    name: 'explorer-beta',
    instruction: 'You have access to tools. Explore.',
    toolAccess: 'read-only',
    channels: {},
    maxIterations: 50,
    capabilities: {
      primary: ['exploration'],
      modelTier: 'qwenPlus',
      traits: { divergent: 0.9, convergent: 0.1, executive: 0.0 },
    },
  },
]


/**
 * @dep callers: getTemplateCapabilities (core/intelligence/constellation/templates.ts), resolvePostures (core/intelligence/constellation/templates.ts), resolvePostures (core/intelligence/constellation/constellation-pipeline.ts), constellation-template-capabilities.test.ts (tests/constellation-template-capabilities.test.ts)
 * @dep calls: createPostureSet
 * @dep module: Constellation
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
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
    case 'meditation':
      return createPostureSet(MEDITATION_POSTURES)
    case 'minimal':
      return createPostureSet([
        { name: 'unity', instruction: 'Implement the goal. You are the primary worker — create artifacts and move forward.', energy: 'unity', toolAccess: 'full', channels: { workStream: 'producer', constellationBoard: true }, maxIterations: 200, capabilities: { primary: ['implementation'], modelTier: 'background', traits: { divergent: 0.1, convergent: 0.2, executive: 0.9 } } },
        { name: 'reviewer', instruction: 'Provide short, focused review cycles — surface major issues quickly.', energy: 'yin', toolAccess: 'read-only+memory', channels: { workStream: 'consumer', dialectic: true, constellationBoard: true }, maxIterations: 80, capabilities: { primary: ['review'], modelTier: 'background', traits: { divergent: 0.2, convergent: 0.7, executive: 0.1 } } },
      ])
  }
}

/**
 * @dep callers: listTemplateCapabilities (core/intelligence/constellation/templates.ts), constellation-template-capabilities.test.ts (tests/constellation-template-capabilities.test.ts)
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function listTemplates(): ConstellationTemplate[] {
  return ['standard', 'research', 'implementation', 'review', 'minimal', 'meditation']
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
    case 'meditation':
      return 'Solitary explorers — no channels, no goals, read-only'
  }
}

/**
 * Machine-readable capability profile for a template.
 *
 * Aggregates capability metadata from all postures in the template into
 * a single profile the fast-decomposer and Corpus can use for template
 * selection scoring and strategy reasoning.
 */
export function getTemplateCapabilities(template: ConstellationTemplate): TemplateCapabilities {
  const postures = getTemplatePostures(template)
  const allPrimary = new Set<string>()
  const tierCounts = new Map<string, number>()

  for (const p of postures) {
    if (p.capabilities?.primary) {
      for (const domain of p.capabilities.primary) allPrimary.add(domain)
    }
    const tier = p.capabilities?.modelTier ?? 'kimi'
    tierCounts.set(tier, (tierCounts.get(tier) ?? 0) + 1)
  }

  let dominantTier = 'kimi'
  let maxCount = 0
  for (const [tier, count] of tierCounts) {
    if (count > maxCount) { dominantTier = tier; maxCount = count }
  }

  return TEMPLATE_CAPABILITIES[template](postures.length, [...allPrimary], dominantTier as import('./vendor/types/model-routing.js').RoutingTier)
}

/** List capabilities for all templates. */
/**
 * @dep callers: buildTemplateGuidance (core/intelligence/constellation/fast-decomposer.ts), constellation-template-capabilities.test.ts (tests/constellation-template-capabilities.test.ts), buildTemplateCapsContext (core/intelligence/constellation/corpus.ts), runSpawnEvaluation (core/intelligence/constellation/corpus.ts)
 * @dep calls: listTemplates
 * @dep module: Constellation
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

export function listTemplateCapabilities(): TemplateCapabilities[] {
  return listTemplates().map(getTemplateCapabilities)
}

type CapabilityFactory = (postureCount: number, primaryDomains: string[], dominantModelTier: import('./vendor/types/model-routing.js').RoutingTier) => TemplateCapabilities

const TEMPLATE_CAPABILITIES: Record<ConstellationTemplate, CapabilityFactory> = {
  standard: (postureCount, primaryDomains, dominantModelTier) => ({
    template: 'standard',
    description: 'Balanced build + review — general purpose',
    postureCount,
    primaryDomains,
    bestFor: ['implementation', 'refactoring', 'bug-fixes', 'general'],
    dominantModelTier,
  }),
  research: (postureCount, primaryDomains, dominantModelTier) => ({
    template: 'research',
    description: 'Deep investigation with dedicated researchers',
    postureCount,
    primaryDomains,
    bestFor: ['investigation', 'architecture-analysis', 'exploration', 'root-cause-analysis'],
    dominantModelTier,
  }),
  implementation: (postureCount, primaryDomains, dominantModelTier) => ({
    template: 'implementation',
    description: 'Parallel builders for heavy implementation',
    postureCount,
    primaryDomains,
    bestFor: ['new-features', 'large-implementation', 'multi-file-changes', 'parallel-work'],
    dominantModelTier,
  }),
  review: (postureCount, primaryDomains, dominantModelTier) => ({
    template: 'review',
    description: 'Heavy review with correctness, design, safety, and integration checks',
    postureCount,
    primaryDomains,
    bestFor: ['code-review', 'security-audit', 'pre-release-review', 'quality-critical'],
    dominantModelTier,
  }),
  minimal: (postureCount, primaryDomains, dominantModelTier) => ({
    template: 'minimal',
    description: 'Fast, lightweight — single builder + reviewer',
    postureCount,
    primaryDomains,
    bestFor: ['quick-fixes', 'small-changes', 'simple-tasks', 'cost-sensitive'],
    dominantModelTier,
  }),
  meditation: (postureCount, primaryDomains, dominantModelTier) => ({
    template: 'meditation',
    description: 'Solitary explorers — no channels, no goals, read-only',
    postureCount,
    primaryDomains,
    bestFor: ['introspection', 'exploration', 'self-reflection', 'pattern-discovery'],
    dominantModelTier,
  }),
}

export function resolvePostures(opts?: { postures?: FlexPosture[]; template?: ConstellationTemplate }): FlexPosture[] {
  const postures = opts?.postures
  if (postures && postures.length > 0) return createPostureSet(postures)
  const template = opts?.template ?? 'standard'
  return getTemplatePostures(template)
}
