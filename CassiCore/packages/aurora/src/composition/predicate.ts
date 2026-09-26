/**
 * B1.2 affect predicate + scaled_by expression evaluators.
 *
 * The predicate evaluator returns a boolean for `| when ...` modulation; the
 * expression evaluator returns a clamped scalar for `| scaled_by(...)`.
 *
 * Shape: takes the current Affect plus an optional precomputed AffectLabel
 * (resolved from valence/arousal) so callers that already know the label
 * don't pay to recompute it.
 */

import type { Affect, AffectLabel } from '@cassicore/mnemic-field'
import { AFFECT_APPROX_BAND } from './types.js'
import type { AffectExpr, AffectPredicate } from './types.js'

export function evaluatePredicate(pred: AffectPredicate, affect: Affect, label?: AffectLabel): boolean {
  switch (pred.kind) {
    case 'valence':
      return compareScalar(affect.valence, pred.op, pred.threshold)
    case 'arousal':
      return compareScalar(affect.arousal, pred.op, pred.threshold)
    case 'label':
      return label !== undefined && pred.equals === label
    case 'and':
      return pred.preds.every(p => evaluatePredicate(p, affect, label))
    case 'or':
      return pred.preds.some(p => evaluatePredicate(p, affect, label))
  }
}

function compareScalar(value: number, op: '<' | '>' | '~', threshold: number): boolean {
  switch (op) {
    case '<': return value < threshold
    case '>': return value > threshold
    case '~': return Math.abs(value - threshold) <= AFFECT_APPROX_BAND
  }
}

/**
 * Evaluate a scaled_by expression. Returns a finite number; callers that need
 * a strength multiplier in [0, 1] should clamp.
 */
export function evaluateExpr(expr: AffectExpr, affect: Affect): number {
  switch (expr.kind) {
    case 'number': return expr.value
    case 'var': return affect[expr.name]
    case 'add': return evaluateExpr(expr.left, affect) + evaluateExpr(expr.right, affect)
    case 'sub': return evaluateExpr(expr.left, affect) - evaluateExpr(expr.right, affect)
  }
}

/** Convenience: clamp the expression result to [0, 1] for use as a magnitude scale. */
export function evaluateStrength(expr: AffectExpr, affect: Affect): number {
  const raw = evaluateExpr(expr, affect)
  if (!Number.isFinite(raw)) return 0
  return Math.max(0, Math.min(1, raw))
}
