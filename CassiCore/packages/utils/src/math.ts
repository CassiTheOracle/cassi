/**
 * Clamp a number between min and max inclusive.
 * If min > max the bounds are swapped to be robust.
 * If any argument is NaN the result is NaN.
 *
 * @param x - value to clamp
 * @param a - lower bound
 * @param b - upper bound
 * @returns clamped value or NaN if any input is NaN
 * @dep callers: fallbackParseResponse (core/intelligence/dialectic/serenity.ts), parseResponse (core/intelligence/dialectic/serenity.ts), parseDualResponse (core/intelligence/dialectic/serenity.ts), parseResponse (core/intelligence/dialectic/yang.ts), parseResponse (core/intelligence/dialectic/yin.ts) [+2]
 * @dep module: Dialectic
 * @dep risk: HIGH | 7 callers, 0 flows, 1 module
 */
export function clamp(x: number, a: number, b: number): number {
  if (Number.isNaN(x) || Number.isNaN(a) || Number.isNaN(b)) return NaN
  let min = a
  let max = b
  if (min > max) {
    const t = min
    min = max
    max = t
  }
  if (x <= min) return min
  if (x >= max) return max
  return x
}

/**
 * Linear interpolation between a and b using parameter t.
 * Computes a + (b - a) * t.
 * If any argument is NaN the result is NaN.
 * t may be outside [0,1] for extrapolation.
 *
 * @param a - start value
 * @param b - end value
 * @param t - interpolation parameter (0..1)
 * @returns interpolated value or NaN if any input is NaN
 */
export function lerp(a: number, b: number, t: number): number {
  if (Number.isNaN(a) || Number.isNaN(b) || Number.isNaN(t)) return NaN
  return a + (b - a) * t
}

/**
 * Remap a numeric value from one range to another.
 * Formula: outMin + ((value - inMin) * (outMax - outMin)) / (inMax - inMin)
 *
 * Behavior notes:
 * - If any numeric input is NaN, returns NaN.
 * - If inMin === inMax the source range has zero length and the function returns NaN
 *   (to explicitly flag invalid input rather than silently returning Infinity or an
 *   arbitrary number).
 * - Reversed input or output ranges are supported (no special handling required).
 * - If clampResult is true the remapped value is clamped to the output range (handles
 *   reversed output ranges by internally swapping bounds in clamp()).
 *
 * @param value - value in the input range
 * @param inMin - input range start
 * @param inMax - input range end
 * @param outMin - output range start
 * @param outMax - output range end
 * @param clampResult - whether to clamp the result to the output range (default false)
 * @returns remapped value, or NaN for invalid inputs (NaN inputs or zero-length in-range)
 */
export function remap(
  value: number,
  inMin: number,
  inMax: number,
  outMin: number,
  outMax: number,
  clampResult = false
): number {
  if (
    Number.isNaN(value) ||
    Number.isNaN(inMin) ||
    Number.isNaN(inMax) ||
    Number.isNaN(outMin) ||
    Number.isNaN(outMax)
  ) {
    return NaN
  }

  const denom = inMax - inMin
  if (denom === 0) return NaN

  const t = (value - inMin) / denom
  const out = outMin + t * (outMax - outMin)
  if (!clampResult) return out
  return clamp(out, outMin, outMax)
}
