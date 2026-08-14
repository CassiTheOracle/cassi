/**
 * Clamp a number between min and max inclusive.
 * If min > max the bounds are swapped to be robust.
 * If any argument is NaN the result is NaN.
 *
 * @param x - value to clamp
 * @param a - lower bound
 * @param b - upper bound
 * @returns clamped value or NaN if any input is NaN
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
 */
export function lerp(a: number, b: number, t: number): number {
  if (Number.isNaN(a) || Number.isNaN(b) || Number.isNaN(t)) return NaN
  return a + (b - a) * t
}

/**
 * Remap a numeric value from one range to another.
 * Formula: outMin + ((value - inMin) * (outMax - outMin)) / (inMax - inMin)
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
