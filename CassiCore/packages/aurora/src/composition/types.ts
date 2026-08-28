/**
 * B1 Concept Arithmetic — types for the composition AST and store records.
 *
 * Compositions are named, composable steering primitives. They parse from a
 * mini-DSL into an AST, serialize to JSON for storage in `aurora_compositions`,
 * and (when A2 lands) resolve into per-layer Float32Array projections that
 * inject into the model's residual stream.
 *
 * This slice covers the AST surface for the full Section 3 grammar, plus
 * runtime records for invocation tracking. The `modulated` AST kind is
 * present for forward compatibility — Phase B1.2 wires the parser path that
 * produces it; B1.1a accepts and stores AST shapes that don't include it.
 *
 * See: docs/design/aurora-concept-arithmetic.md
 */

import type { AffectLabel } from '@cassicore/mnemic-field'

export type CompositionAst =
  | { kind: 'gate'; label: string }
  | { kind: 'affect'; label: AffectLabel }
  | { kind: 'reference'; name: string }
  | { kind: 'live'; selector: string }
  | { kind: 'scaled'; operand: CompositionAst; factor: number }
  | { kind: 'sum'; operands: CompositionAst[] }
  | { kind: 'layered'; operand: CompositionAst; layers: LayerSpec }
  | { kind: 'modulated'; operand: CompositionAst; predicate: AffectPredicate }
  | { kind: 'scaledModulated'; operand: CompositionAst; expression: AffectExpr }

export type LayerSpec =
  | { all: true }
  | { range: [number, number] }
  | { layer: number }

export type AffectPredicate =
  | { kind: 'valence'; op: '<' | '>' | '~'; threshold: number }
  | { kind: 'arousal'; op: '<' | '>' | '~'; threshold: number }
  | { kind: 'label'; equals: AffectLabel }
  | { kind: 'and'; preds: AffectPredicate[] }
  | { kind: 'or'; preds: AffectPredicate[] }

/**
 * Tiny linear expression over affect dimensions, used by `| scaled_by(...)`.
 * Resolves to a scalar in `[0, 1]` (clamped) that scales composition strength.
 * Grammar mirrors the same +/- linear form as the main DSL but with the
 * variable set restricted to {valence, arousal} and constants.
 */
export type AffectExpr =
  | { kind: 'number'; value: number }
  | { kind: 'var'; name: 'valence' | 'arousal' }
  | { kind: 'add'; left: AffectExpr; right: AffectExpr }
  | { kind: 'sub'; left: AffectExpr; right: AffectExpr }

/**
 * Tolerance band for the `~` (approximately equal) operator. A predicate like
 * `valence ~ 0.5` is true when the dimension is within +/- this band of the
 * threshold. Set on the predicate via `kind === '~'`.
 */
export const AFFECT_APPROX_BAND = 0.1

/**
 * The set of affect-state labels whose subtraction triggers the suppressive
 * welfare guard (Section 10.2 #2). Subtracting these dampens an internal
 * affective signal — Anthropic's emotion-concepts research flags this as
 * higher risk than additive composition; we require explicit opt-in.
 */
export const SUPPRESSIVE_AFFECT_LABELS = new Set<AffectLabel>([
  'frustrated',
  'fatigued',
  'uneasy',
  'melancholy',
  'alarmed',
])

/**
 * B1.3 — invocation rule. Binds a composition to a topical-context
 * trigger so the composition activates automatically when at least one
 * of `topicKeywords` appears in the current active-concept set.
 *
 * Edge-triggered: the rule fires when the trigger flips false→true,
 * not on every evaluation tick. The evaluator tracks each rule's
 * `lastSatisfiedAt` to suppress repeat-firings while the trigger
 * stays satisfied.
 *
 * Match policy is case-insensitive substring against active concept
 * labels — same heuristic the N2 detector uses for meditation seed
 * topic matching. A rule with `topicKeywords: ['review', 'feedback']`
 * fires when any active concept contains "review" or "feedback".
 */
export interface InvocationRule {
  /** Unique rule id. Used for upsert + audit. */
  id: string
  /** Substring keywords matched (case-insensitive) against active concept labels. */
  topicKeywords: string[]
  /** Composition name to invoke when the rule fires. Must already be in the store. */
  composition: string
  /** TTL passed to invokeComposition. Default 5. */
  ttlTurns?: number
  /** magnitudeScale passed to invokeComposition. Default 1.0. */
  magnitudeScale?: number
  /** Free-form description for operator audit. */
  description?: string
  /** ISO timestamp the rule was last upserted. */
  updatedAt: string
}

export interface InvocationRuleEvaluation {
  /** Rule ids that fired this tick (false→true edge). */
  fired: string[]
  /** Rule ids whose trigger is now false (true→false edge). */
  unfired: string[]
  /** Rule ids whose trigger remained satisfied (suppressed re-fire). */
  stillSatisfied: string[]
}

/**
 * B1.4 — composition proposal authored by Cassi (or operator on her behalf).
 *
 * Stays in `pending` until reviewed; `approve` promotes it to a
 * proper CompositionRecord via the regular upsertComposition path,
 * `reject` discards it with a reason. Provenance is preserved via
 * `proposer` and `rationale`.
 */
export type CompositionProposalStatus = 'pending' | 'approved' | 'rejected' | 'withdrawn'

export interface CompositionProposal {
  id: string
  /** The DSL string to be parsed when approved. */
  dsl: string
  /** Composition name; must be present in the DSL (`name = ...`). */
  proposedName: string
  /** Why Cassi/operator proposed this composition. */
  rationale: string
  /** Who proposed: 'cassi' (in-conversation) or 'operator'. */
  proposer: 'cassi' | 'operator'
  status: CompositionProposalStatus
  proposedAt: string
  reviewedAt?: string
  reviewedBy?: 'cassi' | 'operator'
  reviewComment?: string
  /** Optional metadata payload (links to the conversation, observation, etc.). */
  metadata: Record<string, unknown>
}

/**
 * B2 retrieval-policy spec attached to a composition (parse form).
 *
 * The DSL `with retrieval(<mode>[, <strength>])` lands here. `directed`
 * mode requires a vector and isn't parser-expressible at this phase —
 * inline directed policies are a runtime concern set programmatically
 * by callers, not via the DSL. The DSL only exposes `consonant` and
 * `complementary`, which resolve at runtime against current affect.
 */
export interface RetrievalPolicySpec {
  mode: 'consonant' | 'complementary'
  /** Strength in [0,1]. Default 0.3 if omitted in the DSL. */
  strength: number
}

export interface CompositionRecord {
  name: string
  dsl: string
  ast: CompositionAst
  layerPolicy: string
  affectModulated: boolean
  suppressive: boolean
  vindexId: string
  description: string | null
  createdAt: string
  updatedAt: string
  metadata: Record<string, unknown>
  /** B2.2: optional affect-conditioned retrieval policy applied while this composition is active. */
  retrievalPolicy: RetrievalPolicySpec | null
}

export interface ActiveComposition {
  name: string
  ast: CompositionAst
  invokedAt: string
  ttlTurns: number
  remainingTurns: number
  magnitudeScale: number
  trigger: InvocationTrigger
  /** B2.2: retrieval policy attached at definition time, carried into the active window. */
  retrievalPolicy?: RetrievalPolicySpec | null
}

export type InvocationTrigger = 'manual' | 'affect_predicate' | `rule:${string}`

export interface InvocationRecord {
  id: number
  name: string
  invokedAt: string
  sessionId: string | null
  trigger: InvocationTrigger
  resolvedNorm: number | null
  metadata: Record<string, unknown>
}

export interface DefineCompositionOptions {
  description?: string | null
  vindexId?: string
  metadata?: Record<string, unknown>
  /**
   * Welfare guard: suppressive compositions are refused unless the operator
   * explicitly opts in. See Section 10.2 #2 of the B1 spec.
   */
  allowSuppressive?: boolean
}

export interface InvokeCompositionOptions {
  ttlTurns?: number
  magnitudeScale?: number
  sessionId?: string | null
  trigger?: InvocationTrigger
}

export const DEFAULT_TTL_TURNS = 5
export const DEFAULT_MAGNITUDE_SCALE = 1.0
export const DEFAULT_VINDEX_ID = 'default'
