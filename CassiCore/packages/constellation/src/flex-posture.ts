/**
 * FlexPosture — Dynamic posture creation, validation, and system prompt composition.
 *
 * In Constellation, postures are the atomic unit of agency. This module handles:
 *
 *   1. Validation  — Ensure posture configs are well-formed and consistent
 *   2. Composition — Build system prompts from energy identity + constellation context + custom instruction
 *   3. Defaults    — Fill in sensible defaults for optional fields
 *   4. Slot naming — Generate stable model routing slot names
 *
 * The composition model is layered:
 *   Layer 1 (optional): Base energetic identity from posture-store (yang/yin/unity)
 *   Layer 2: Constellation agent-type context (how to use tools, channels, communication)
 *   Layer 3: Custom instruction (the posture's specific behavioral guidance)
 *
 * Postures without an energy direction skip Layers 1-2 and use only Layer 3
 * with a minimal operational preamble.
 */

import type {
  FlexPosture,
  ToolAccessLevel,
  ConstellationTemplate,
} from './types.js'
import { getBaseIdentity } from '../shared/posture-store.js'
import type { PostureName } from '../shared/posture-store.js'


// Validation

/** Validation result. */
export interface PostureValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

/** Reserved posture names that have well-known behavior. */
const RESERVED_NAMES = new Set(['unity', 'yang', 'yin', 'mentor'])

/** Maximum postures per Helix — prevents runaway resource usage. */
const MAX_POSTURES_PER_HELIX = 12

/** Maximum instruction length in characters. */
const MAX_INSTRUCTION_LENGTH = 4000

/**
 * Validate a single FlexPosture definition.
 * @dep callers: validatePostureSet (core/intelligence/constellation/flex-posture.ts), createPosture (core/intelligence/constellation/flex-posture.ts)
 * @dep calls: test
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function validatePosture(posture: FlexPosture): PostureValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  // Name
  if (!posture.name || posture.name.trim().length === 0) {
    errors.push('Posture name is required')
  } else if (!/^[a-z][a-z0-9_-]*$/.test(posture.name)) {
    errors.push(`Posture name must be lowercase alphanumeric with hyphens/underscores, got: "${posture.name}"`)
  }

  // Instruction
  if (!posture.instruction || posture.instruction.trim().length === 0) {
    errors.push('Posture instruction is required')
  } else if (posture.instruction.length > MAX_INSTRUCTION_LENGTH) {
    warnings.push(`Instruction is ${posture.instruction.length} chars — consider trimming for token efficiency`)
  }

  // Energy direction
  if (posture.energy && !['yang', 'yin', 'unity'].includes(posture.energy)) {
    errors.push(`Invalid energy direction: "${posture.energy}". Must be yang, yin, or unity`)
  }

  // Tool access
  const validToolAccess: ToolAccessLevel[] = ['full', 'read-only', 'read-only+memory', 'none']
  if (!validToolAccess.includes(posture.toolAccess)) {
    errors.push(`Invalid toolAccess: "${posture.toolAccess}". Must be one of: ${validToolAccess.join(', ')}`)
  }

  // Channel consistency
  if (posture.channels.workStream === 'producer' && posture.toolAccess === 'none') {
    warnings.push('WorkStream producer with no tool access — will not be able to create artifacts')
  }
  if (posture.channels.workStream === 'producer' && posture.toolAccess === 'read-only') {
    warnings.push('WorkStream producer with read-only tools — limited implementation capability')
  }

  // Spawn capability checks
  if (posture.canSpawnHelix && posture.toolAccess === 'none') {
    warnings.push('Posture can spawn Helix but has no tool access — spawned children will work without parent tool context')
  }

  // Max iterations
  if (posture.maxIterations !== undefined && posture.maxIterations < 1) {
    errors.push('maxIterations must be ≥ 1')
  }
  if (posture.maxIterations !== undefined && posture.maxIterations > 1000) {
    warnings.push(`maxIterations is ${posture.maxIterations} — very high, consider whether this is intentional`)
  }

  // Temperature
  if (posture.temperature !== undefined && (posture.temperature < 0 || posture.temperature > 2)) {
    errors.push('temperature must be between 0 and 2')
  }

  return { valid: errors.length === 0, errors, warnings }
}

/**
 * Validate a set of postures for a Helix.
 */
export function validatePostureSet(postures: FlexPosture[]): PostureValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  if (postures.length === 0) {
    errors.push('At least one posture is required')
    return { valid: false, errors, warnings }
  }

  if (postures.length > MAX_POSTURES_PER_HELIX) {
    errors.push(`Too many postures: ${postures.length} (max ${MAX_POSTURES_PER_HELIX})`)
  }

  // Check for duplicate names
  const names = new Set<string>()
  for (const p of postures) {
    if (names.has(p.name)) {
      errors.push(`Duplicate posture name: "${p.name}"`)
    }
    names.add(p.name)
  }

  // Validate each posture
  for (const p of postures) {
    const result = validatePosture(p)
    errors.push(...result.errors.map(e => `[${p.name}] ${e}`))
    warnings.push(...result.warnings.map(w => `[${p.name}] ${w}`))
  }

  // Check for at least one producer if any consumers exist
  const hasProducer = postures.some(p => p.channels.workStream === 'producer' || p.channels.workStream === 'both')
  const hasConsumer = postures.some(p => p.channels.workStream === 'consumer' || p.channels.workStream === 'both')
  if (hasConsumer && !hasProducer) {
    warnings.push('WorkStream consumers exist but no producer — consumers will have no work to review')
  }

  // Check for dialectic balance
  const dialecticPostures = postures.filter(p => p.channels.dialectic)
  if (dialecticPostures.length === 1) {
    warnings.push('Only one dialectic participant — dialectic requires at least two postures for meaningful debate')
  }

  return { valid: errors.length === 0, errors, warnings }
}


// Defaults

/**
 * Apply sensible defaults to a FlexPosture, filling in optional fields.
 */
export function applyDefaults(posture: FlexPosture): FlexPosture {
  return {
    ...posture,
    channels: {
      constellationBoard: true,  // Default: everyone can see the team board
      ...posture.channels,
    },
    maxIterations: posture.maxIterations ?? defaultMaxIterations(posture),
    temperature: posture.temperature ?? defaultTemperature(posture),
    canSpawnHelix: posture.canSpawnHelix ?? false,
    canSpawnDrones: posture.canSpawnDrones ?? false,
    canReadParentBoard: posture.canReadParentBoard ?? false,
  }
}

function defaultMaxIterations(posture: FlexPosture): number {
  // Producers (implementers) get more iterations
  if (posture.channels.workStream === 'producer' || posture.channels.workStream === 'both') return 500
  // Consumers (reviewers) and dialectic get moderate
  if (posture.channels.workStream === 'consumer' || posture.channels.dialectic) return 100
  // Spawn-capable (coordinators/mentors) get slightly more
  if (posture.canSpawnHelix) return 120
  // Everyone else
  return 100
}

function defaultTemperature(posture: FlexPosture): number {
  if (posture.energy === 'yin') return 0.35
  if (posture.energy === 'yang') return 0.7
  if (posture.energy === 'unity') return 0.5
  return 0.7
}


// System Prompt Composition

/**
 * Compose a complete system prompt for a FlexPosture.
 *
 * Layered composition:
 *   1. Base energetic identity (if energy direction specified)
 *   2. Constellation operational context (channel usage, tools, communication)
 *   3. Custom instruction
 *   4. Optional appendix (Phase Zero briefing, parent context, etc.)
 *
 * Postures without an energy direction get a neutral operational preamble
 * plus their custom instruction.
 */
export function composeConstellationPrompt(
  posture: FlexPosture,
  opts?: {
    /** Extra context to append (Phase Zero, parent context, etc.) */
    appendix?: string
    /** The goal of this Helix instance. */
    helixGoal?: string
    /** Whether this Helix is a child (has a parent). */
    isChild?: boolean
    /** The Constellation-level goal (if different from Helix goal). */
    constellationGoal?: string
  },
): string {
  const sections: string[] = []

  // Layer 1: Base energetic identity (optional)
  if (posture.energy) {
    try {
      sections.push(getBaseIdentity(posture.energy as PostureName))
    } catch {
      // Graceful fallback — shouldn't happen but don't crash prompt composition
    }
  }

  // Layer 2: Constellation operational context
  sections.push(buildOperationalContext(posture, opts))

  // Layer 3: Custom instruction
  sections.push(`## My Specific Role\n\n${posture.instruction}`)

  // Layer 4: Optional appendix
  if (opts?.appendix) {
    sections.push(opts.appendix)
  }

  return sections.join('\n\n---\n\n')
}

/**
 * Build the operational context section for a Constellation posture.
 * This describes how to use available tools, channels, and communication.
 */
function buildOperationalContext(
  posture: FlexPosture,
  opts?: {
    helixGoal?: string
    isChild?: boolean
    constellationGoal?: string
  },
): string {
  const parts: string[] = []

  parts.push(`I am the "${posture.name}" posture in a Constellation Helix session.`)

  if (opts?.helixGoal) {
    parts.push(`\nMy Helix's goal: ${opts.helixGoal}`)
  }
  if (opts?.constellationGoal && opts.constellationGoal !== opts?.helixGoal) {
    parts.push(`The overall Constellation goal: ${opts.constellationGoal}`)
  }
  if (opts?.isChild) {
    parts.push(`This is a child Helix — spawned by a parent Helix to handle a sub-goal.`)
  }

  // Tool access description
  parts.push(buildToolAccessDescription(posture.toolAccess))

  // Channel descriptions
  if (posture.channels.workStream) {
    parts.push(buildWorkStreamDescription(posture.channels.workStream))
  }

  if (posture.channels.dialectic) {
    parts.push(buildDialecticDescription())
  }

  // Blackboard description (always available)
  parts.push(buildBlackboardDescription(posture))

  // Spawn capabilities
  if (posture.canSpawnHelix) {
    parts.push(buildSpawnDescription())
  }

  if (posture.canSpawnDrones) {
    parts.push(buildDroneDescription())
  }

  // Pacing guidance
  parts.push(buildPacingGuidance(posture))

  return parts.join('\n\n')
}

function buildToolAccessDescription(level: ToolAccessLevel): string {
  switch (level) {
    case 'full':
      return `## My Tools

I have full tool access — read, write, edit, shell commands, everything. I'm a primary builder in this session.`
    case 'read-only':
      return `## My Tools

I have read-only tool access — I can investigate the codebase (read_file, grep, glob) but I can't modify files. My influence comes through communication channels.`
    case 'read-only+memory':
      return `## My Tools

I have read-only tool access plus memory tools — I can investigate the codebase and search/store memories, but I can't modify files.`
    case 'none':
      return `## My Tools

I have no direct tool access. I work entirely through communication channels — dialectic, blackboard, and work stream.`
  }
}

function buildWorkStreamDescription(mode: 'producer' | 'consumer' | 'both'): string {
  if (mode === 'producer') {
    return `## Work Stream (I produce work)

My work is automatically captured as work units after each iteration. Other postures (reviewers, observers) see my reasoning, tool calls, and results.

- signal_done(summary, key_points?) — I signal that I've completed my work.
- acknowledge_nudge(nudge_id, response?) — I acknowledge nudges from reviewers. High-severity nudges block me until acknowledged.

Nudges from reviewers appear in my tool results. Low-severity is advisory; high-severity blocks until acknowledged.`
  }

  if (mode === 'consumer') {
    return `## Work Stream (I review work)

Work units from producers arrive automatically — I see their reasoning, tool calls, results, and files modified.

- send_nudge(severity, content, work_unit_id?) — I send feedback to producers. Low-severity is advisory; high-severity blocks until acknowledged.
- review_progress() — I get a live view of all work and dialectic state.`
  }

  return `## Work Stream (I produce and review)

I have dual work stream access — I can produce work units AND review others' work.

- signal_done(summary, key_points?) — I signal my work is complete.
- acknowledge_nudge(nudge_id, response?) — I acknowledge reviewer feedback.
- send_nudge(severity, content, work_unit_id?) — I send feedback to others.
- review_progress() — I get a live view of all work and dialectic state.`
}

function buildDialecticDescription(): string {
  return `## Dialectic Channel (I debate)

I participate in a live dialectic with other postures. My dialectic tools:

- share_finding(finding, evidence?, tags[]) — I share discoveries backed by evidence.
- challenge(finding_id, counterargument, evidence?) — I challenge a finding when I have counter-evidence.
- concede(challenge_id, reason?) — I acknowledge when a challenge was valid.
- signal_conclusion(conclusion, confidence, key_points) — I signal my final assessment. Blocked if I have unresolved challenges.

Messages from other dialectic postures appear in my tool results. I must engage with challenges — either conceding or countering. Unresolved challenges block my conclusion.`
}

function buildBlackboardDescription(posture: FlexPosture): string {
  const parts = [`## Blackboard (shared workspace)

I have access to the Helix's shared Blackboard with five channels:

- **findings** — Discoveries and results from investigation
- **concerns** — Risks, issues, and worries
- **decisions** — Resolved questions and commitments
- **artifacts** — Files, outputs, and deliverables
- **requests** — Work requests and steering directives

My blackboard tools: bb_post, bb_read, bb_read_all, bb_search`]

  if (posture.channels.constellationBoard !== false) {
    parts.push(`I also have access to the **Constellation-wide Blackboard** — a team-level board visible to ALL Helix instances in this Constellation. I use it for cross-team communication and visibility.`)
  }

  if (posture.canReadParentBoard) {
    parts.push(`I can read the **parent Helix's Blackboard** — this gives me context about the broader task my Helix was spawned to support.`)
  }

  return parts.join('\n\n')
}

function buildSpawnDescription(): string {
  return `## Spawning New Helixes

I can spawn new child Helix instances to handle sub-goals:

- spawn_helix(goal, context?, template?, postures?) — Create a new Helix with its own team of postures.
- observe_child(child_helix_id) — Read a child Helix's Blackboard state.
- steer_child(child_helix_id, directive) — Send a steering directive to a child.

Child findings auto-forward to my Helix's Blackboard. I can steer children or let them work autonomously.

Spawning rules:
- Children at depth ≤ 1 are auto-approved.
- Deeper children need approval from the parent's coordinator.
- Each child gets its own Blackboard, linked to mine via a bridge.`
}

function buildDroneDescription(): string {
  return `## Research Drones

I can dispatch drone swarms for parallel research:

- dispatch_research(query, priority?) — Spawn a drone swarm to investigate a question.

Drone results are posted to my Helix's Blackboard findings channel. Drones have read-only tool access and work in parallel — they're fast but lightweight.`
}

function buildPacingGuidance(posture: FlexPosture): string {
  const max = posture.maxIterations ?? 100
  const earlyPhase = Math.min(5, Math.floor(max * 0.1))
  const midPhase = Math.floor(max * 0.6)
  const wrapPhase = Math.floor(max * 0.8)

  return `## My Pacing

I have ${max} iterations maximum. I should:
- Iterations 1–${earlyPhase}: Orient, investigate, build context.
- Iterations ${earlyPhase + 1}–${midPhase}: Peak activity — my main work phase.
- Iterations ${midPhase + 1}–${wrapPhase}: Begin forming conclusions, wrap up.
- After iteration ${wrapPhase}: I should be concluding. Don't let the session timeout.

A good result delivered on time is worth more than a perfect result that never finishes.`
}


// Model Slot Naming

/**
 * Generate a stable model routing slot name for a posture.
 *
 * If the posture has a custom slotName, use it.
 * Otherwise, generate from the constellation/helix/posture hierarchy.
 */
export function resolveSlotName(
  posture: FlexPosture,
  constellationId: string,
  helixIndex: number,
): string {
  if (posture.slotName) return posture.slotName

  // Use the posture's energy direction for routing when available,
  // otherwise fall back to the posture name
  const roleHint = posture.energy ?? posture.name
  return `constellation.${constellationId}.h${helixIndex}.${roleHint}`
}


// Factory Helpers

/**
 * Create a FlexPosture with validation and defaults applied.
 * Throws if the posture is invalid.
 */
export function createPosture(partial: FlexPosture): FlexPosture {
  const posture = applyDefaults(partial)
  const validation = validatePosture(posture)
  if (!validation.valid) {
    throw new Error(`Invalid posture "${partial.name}": ${validation.errors.join('; ')}`)
  }
  return posture
}

/**
 * Create a set of postures with validation.
 * Throws if any posture is invalid or the set has issues.
 * @dep callers: getTemplatePostures (core/intelligence/constellation/templates.ts), resolvePostures (core/intelligence/constellation/templates.ts)
 * @dep calls: validatePostureSet
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function createPostureSet(postures: FlexPosture[]): FlexPosture[] {
  const withDefaults = postures.map(applyDefaults)
  const validation = validatePostureSet(withDefaults)
  if (!validation.valid) {
    throw new Error(`Invalid posture set: ${validation.errors.join('; ')}`)
  }
  return withDefaults
}
