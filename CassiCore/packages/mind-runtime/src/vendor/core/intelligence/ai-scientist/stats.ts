/**
 * AI Scientist — Statistical Utilities
 *
 * Implements the quantitative primitives used by the experiment engine:
 * Welch's t-test, Cohen's d effect size, Wilson score intervals, and
 * Bayesian beta posterior estimation.
 *
 * All functions are pure and deterministic.
 */


/** Arithmetic mean of an array. Returns 0 for empty input. */
/**
 * @dep callers: cohensD (core/intelligence/ai-scientist/stats.ts), welchTTest (core/intelligence/ai-scientist/stats.ts), describeStats (core/intelligence/ai-scientist/stats.ts), variance (core/intelligence/ai-scientist/stats.ts)
 * @dep flows: OnTurnEnd → Mean (7/7), Analyse → Mean (4/4)
 * @dep module: Ai-scientist
 * @dep risk: MEDIUM | 4 callers, 2 flows, 1 module
 */

export function mean(xs: number[]): number {
  if (xs.length === 0) return 0
  return xs.reduce((s, x) => s + x, 0) / xs.length
}

/** Sample variance (Bessel's correction). Returns 0 for n < 2. */
/**
 * @dep callers: cohensD (core/intelligence/ai-scientist/stats.ts), welchTTest (core/intelligence/ai-scientist/stats.ts), describeStats (core/intelligence/ai-scientist/stats.ts)
 * @dep calls: mean
 * @dep flows: OnTurnEnd → Mean (6/7), Analyse → Mean (3/4)
 * @dep module: Ai-scientist
 * @dep risk: LOW | 3 callers, 2 flows, 1 module
 */

export function variance(xs: number[]): number {
  if (xs.length < 2) return 0
  const m = mean(xs)
  return xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1)
}

export interface DescriptiveStats {
  count: number
  mean: number
  stdDev: number
  min: number
  max: number
  p50: number
  p95: number
  p99: number
}

/** Full descriptive statistics for a numeric sample. */
/**
 * @dep callers: analyse (core/intelligence/ai-scientist/aging-analyzer.ts), analyse (core/intelligence/ai-scientist/experiment-engine.ts)
 * @dep calls: mean, variance
 * @dep flows: Analyse → Mean (2/4)
 * @dep module: Ai-scientist
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */

export function describeStats(xs: number[]): DescriptiveStats {
  if (xs.length === 0) {
    return { count: 0, mean: 0, stdDev: 0, min: 0, max: 0, p50: 0, p95: 0, p99: 0 }
  }
  const sorted = [...xs].sort((a, b) => a - b)
  const m = mean(xs)
  return {
    count: xs.length,
    mean: m,
    stdDev: Math.sqrt(variance(xs)),
    min: sorted[0],
    max: sorted[sorted.length - 1],
    p50: sorted[Math.floor(sorted.length * 0.5)],
    p95: sorted[Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1)],
    p99: sorted[Math.min(Math.floor(sorted.length * 0.99), sorted.length - 1)],
  }
}


export interface TTestResult {
  tStat: number
  df: number
  /** Two-tailed p-value */
  pValue: number
}

/**
 * Welch's t-test for two independent samples with possibly unequal variances.
 * Returns a two-tailed p-value using the Welch–Satterthwaite approximation.
 * @dep callers: analyse (core/intelligence/ai-scientist/aging-analyzer.ts), analyse (core/intelligence/ai-scientist/experiment-engine.ts)
 * @dep calls: mean, variance, twoTailedPValue
 * @dep flows: Analyse → LogGamma (2/5)
 * @dep module: Ai-scientist
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */
export function welchTTest(a: number[], b: number[]): TTestResult {
  if (a.length < 2 || b.length < 2) return { tStat: 0, df: 0, pValue: 1 }

  const na = a.length, nb = b.length
  const va = variance(a), vb = variance(b)
  const se = Math.sqrt(va / na + vb / nb)

  if (se === 0) return { tStat: 0, df: 0, pValue: mean(a) === mean(b) ? 1 : 0 }

  const tStat = (mean(a) - mean(b)) / se
  const vaOnN = va / na, vbOnN = vb / nb
  const df = (vaOnN + vbOnN) ** 2 / (vaOnN ** 2 / (na - 1) + vbOnN ** 2 / (nb - 1))
  const pValue = twoTailedPValue(Math.abs(tStat), df)

  return { tStat, df, pValue }
}

/**
 * Approximate two-tailed p-value from a t-distribution using the regularised
 * incomplete beta function. Accurate to ~3 decimal places for df > 5.
 * @dep callers: welchTTest (core/intelligence/ai-scientist/stats.ts)
 * @dep calls: regularisedIncompleteBeta
 * @dep flows: Analyse → LogGamma (3/5)
 * @dep module: Ai-scientist
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
function twoTailedPValue(t: number, df: number): number {
  // x = df / (df + t^2) maps to the beta CDF
  const x = df / (df + t * t)
  return Math.min(1, Math.max(0, regularisedIncompleteBeta(df / 2, 0.5, x)))
}

/** Regularised incomplete beta I_x(a,b) via Lentz continued fraction. */
/**
 * @dep callers: twoTailedPValue (core/intelligence/ai-scientist/stats.ts)
 * @dep calls: logGamma
 * @dep flows: Analyse → LogGamma (4/5)
 * @dep module: Ai-scientist
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

function regularisedIncompleteBeta(a: number, b: number, x: number): number {
  if (x <= 0) return 0
  if (x >= 1) return 1

  const lbeta = logGamma(a) + logGamma(b) - logGamma(a + b)
  const front = (Math.exp(Math.log(x) * a + Math.log(1 - x) * b - lbeta)) / a

  const EPS = 3e-7, MAXIT = 100
  let c = 1, d = 1 - (a + b) * x / (a + 1)
  if (Math.abs(d) < 1e-30) d = 1e-30
  d = 1 / d
  let cf = d

  for (let m = 1; m <= MAXIT; m++) {
    const m2 = 2 * m
    // Even step
    let num = m * (b - m) * x / ((a + m2 - 1) * (a + m2))
    d = 1 + num * d; if (Math.abs(d) < 1e-30) d = 1e-30
    c = 1 + num / c; if (Math.abs(c) < 1e-30) c = 1e-30
    d = 1 / d; cf *= c * d
    // Odd step
    num = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1))
    d = 1 + num * d; if (Math.abs(d) < 1e-30) d = 1e-30
    c = 1 + num / c; if (Math.abs(c) < 1e-30) c = 1e-30
    d = 1 / d; const delta = c * d; cf *= delta
    if (Math.abs(delta - 1) < EPS) break
  }
  return front * cf
}

/** Lanczos approximation for log-Gamma. */
/**
 * @dep callers: logGamma (core/intelligence/ai-scientist/stats.ts), regularisedIncompleteBeta (core/intelligence/ai-scientist/stats.ts)
 * @dep calls: logGamma
 * @dep flows: Analyse → LogGamma (5/5)
 * @dep module: Ai-scientist
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */

function logGamma(z: number): number {
  const g = 7
  const c = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ]
  if (z < 0.5) return Math.log(Math.PI) - Math.log(Math.sin(Math.PI * z)) - logGamma(1 - z)
  z -= 1
  let x = c[0]
  for (let i = 1; i < g + 2; i++) x += c[i] / (z + i)
  const t = z + g + 0.5
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x)
}


/**
 * Cohen's d pooled-SD effect size.
 * |d| < 0.2 small, 0.2–0.5 medium, > 0.8 large.
 * @dep callers: analyse (core/intelligence/ai-scientist/experiment-engine.ts)
 * @dep calls: mean, variance
 * @dep flows: OnTurnEnd → Mean (5/7)
 * @dep module: Ai-scientist
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export function cohensD(a: number[], b: number[]): number {
  if (a.length < 2 || b.length < 2) return 0
  const pooledSD = Math.sqrt(
    ((a.length - 1) * variance(a) + (b.length - 1) * variance(b)) /
    (a.length + b.length - 2)
  )
  return pooledSD === 0 ? 0 : (mean(a) - mean(b)) / pooledSD
}


/**
 * Bayesian beta posterior mean for a binary-outcome metric.
 * Uses a uniform Beta(1,1) prior by default.
 * @dep callers: analyse (core/intelligence/ai-scientist/experiment-engine.ts)
 * @dep flows: OnTurnEnd → BetaPosteriorMean (5/5)
 * @dep module: Ai-scientist
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export function betaPosteriorMean(
  successes: number,
  total: number,
  alphaPrior = 1,
  betaPrior = 1,
): number {
  const failures = Math.max(0, total - successes)
  return (alphaPrior + successes) / (alphaPrior + betaPrior + successes + failures)
}

/**
 * Wilson score 95 % confidence interval for a proportion.
 */
export function wilsonInterval(n: number, p: number, z = 1.96): [number, number] {
  if (n === 0) return [0, 1]
  const denom = 1 + (z * z) / n
  const centre = (p + (z * z) / (2 * n)) / denom
  const margin = (z * Math.sqrt(p * (1 - p) / n + (z * z) / (4 * n * n))) / denom
  return [Math.max(0, centre - margin), Math.min(1, centre + margin)]
}
