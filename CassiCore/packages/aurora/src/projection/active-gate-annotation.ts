/**
 * A2.4 active-gate annotation — text rendering of a vector projection.
 *
 * For runtimes we can't inject into (remote APIs: Anthropic, OpenAI, …),
 * the projection becomes a structured text block describing which gates
 * are currently composing the residual-stream bias. The model reads this
 * as steering metadata. Per spec §3 / §A2.4:
 *
 *   "Active-gate annotation: surface the names of currently-injected gate
 *    vectors as 'this is what your residual would be biased toward' —
 *    the model interprets this as steering metadata. Better than pure
 *    description, weaker than real injection."
 *
 * The block is intentionally compact — it costs context tokens even when
 * it can't drive activation injection, so the renderer surfaces only the
 * top-N gates by salience and uses a tight per-line format.
 */

import type { GateContribution, VectorProjection } from '../types.js'

export interface AnnotationOptions {
  /** Top-N contributions to surface (default 8). */
  maxGates?: number
  /** Drop gates whose weight is below this floor (default 0.02). */
  minWeight?: number
}

const DEFAULT_MAX_GATES = 8
const DEFAULT_MIN_WEIGHT = 0.02

/**
 * Render the projection as an active-gate annotation block. Returns the
 * empty string when the projection is null, has no contributions, or has
 * no contributions clearing the weight floor — callers can splice the
 * result into the broader serialization without conditional logic.
 */
export function renderActiveGateAnnotation(
  projection: VectorProjection | null,
  options: AnnotationOptions = {},
): string {
  if (!projection || projection.contributions.length === 0) return ''
  const maxGates = options.maxGates ?? DEFAULT_MAX_GATES
  const minWeight = options.minWeight ?? DEFAULT_MIN_WEIGHT

  const surfaced = projection.contributions
    .filter(c => c.weight >= minWeight)
    .slice(0, maxGates)
  if (surfaced.length === 0) return ''

  const lines: string[] = ['[Active steering — gate composition biasing residual]']
  for (const c of surfaced) {
    lines.push(formatContribution(c))
  }
  const skipped = projection.contributions.length - surfaced.length
  if (skipped > 0) {
    lines.push(`  (+${skipped} more gates below display threshold)`)
  }
  return lines.join('\n')
}

function formatContribution(c: GateContribution): string {
  const layerSpan = formatLayers(c.layers)
  const weightPct = (c.weight * 100).toFixed(1)
  return `  • ${c.label} (w=${weightPct}% @ ${layerSpan})`
}

function formatLayers(layers: number[]): string {
  if (layers.length === 0) return 'no layers'
  if (layers.length === 1) return `L${layers[0]}`
  // Detect a contiguous range and render as L<lo>..L<hi>
  const sorted = [...layers].sort((a, b) => a - b)
  const isContiguous = sorted.every((v, i) => i === 0 || v === sorted[i - 1] + 1)
  if (isContiguous) return `L${sorted[0]}..L${sorted[sorted.length - 1]}`
  return sorted.map(l => `L${l}`).join(',')
}
