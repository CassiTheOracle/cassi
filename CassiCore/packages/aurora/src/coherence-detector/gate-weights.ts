/**
 * AST → gate-weight map.
 *
 * Walks a composition AST and produces `Map<gateLabel, signedWeight>` — the
 * effective steering vector each gate contributes once scalar multipliers
 * have been folded in. Used by the pairwise cancellation/contradiction
 * detectors to find overlapping gates with opposite signs across active
 * compositions.
 *
 * Limitations (intentional for this slice):
 * - `reference` nodes are not resolved (would require composition-store
 *   lookups that introduce cycles); their contribution is omitted, which
 *   means a reference-heavy composition gets undercounted. Improvement
 *   ticket: resolve references through the store passed by the caller.
 * - `live` selectors are similarly skipped; their contribution depends on
 *   runtime claustrum state.
 * - `modulated` and `scaledModulated` are folded transparently — the
 *   modulation predicate/strength has already been evaluated to determine
 *   that the composition is *active*; the weight calculation treats the
 *   active composition as if at full strength.
 */

import type { CompositionAst } from '../composition/types.js'

export type GateWeights = Map<string, number>

export function gateWeights(ast: CompositionAst, factor = 1): GateWeights {
  const out: GateWeights = new Map()
  fold(ast, factor, out)
  return out
}

function fold(ast: CompositionAst, factor: number, out: GateWeights): void {
  switch (ast.kind) {
    case 'gate':
      out.set(ast.label, (out.get(ast.label) ?? 0) + factor)
      return
    case 'affect':
      out.set(ast.label, (out.get(ast.label) ?? 0) + factor)
      return
    case 'reference':
    case 'live':
      return
    case 'scaled':
      fold(ast.operand, factor * ast.factor, out)
      return
    case 'sum':
      for (const op of ast.operands) fold(op, factor, out)
      return
    case 'layered':
    case 'modulated':
    case 'scaledModulated':
      fold(ast.operand, factor, out)
      return
  }
}

/** L1 norm of a gate-weight map (sum of absolute weights). */
export function l1Norm(w: GateWeights): number {
  let s = 0
  for (const v of w.values()) s += Math.abs(v)
  return s
}

/**
 * Pairwise cancellation analysis: for two gate-weight maps, find labels
 * that appear in both with OPPOSITE signs. Returns:
 *   - overlap: total L1 magnitude of opposite-sign overlap (the "wasted" steering)
 *   - conflictingGates: labels where signs disagree
 */
export function cancellationOverlap(a: GateWeights, b: GateWeights): {
  overlap: number
  conflictingGates: string[]
} {
  let overlap = 0
  const conflictingGates: string[] = []
  for (const [label, va] of a) {
    const vb = b.get(label)
    if (vb === undefined || vb === 0 || va === 0) continue
    if (Math.sign(va) !== Math.sign(vb)) {
      const minMag = Math.min(Math.abs(va), Math.abs(vb))
      overlap += minMag
      conflictingGates.push(label)
    }
  }
  return { overlap, conflictingGates }
}

/**
 * Subtraction-only weights — the gates a composition explicitly suppresses
 * (negative weight). Used to detect composition-meditation suppression.
 */
export function suppressedLabels(ast: CompositionAst): Set<string> {
  const w = gateWeights(ast)
  const out = new Set<string>()
  for (const [label, weight] of w) {
    if (weight < 0) out.add(label)
  }
  return out
}
