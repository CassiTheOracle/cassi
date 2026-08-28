/**
 * Phase 1a predictors. Both run in parallel on every observation; their
 * predictions for the *next* query are scored against that next query's
 * actual embedding when it arrives. Logged as raw cosine — threshold τ
 * is an offline knob.
 */

export interface Predictor {
  readonly id: string
  /** Score the predictor's last prediction against the current observation's embedding. */
  scoreAgainst(actual: Float32Array): number | null
  /** Update internal state with the latest observation, then refresh the prediction. */
  update(embedding: Float32Array): void
  /** Reset all state. */
  reset(): void
}

export function cosineSim(a: Float32Array, b: Float32Array): number {
  if (a.length !== b.length) return 0
  let dot = 0, ma = 0, mb = 0
  for (let i = 0; i < a.length; i++) { dot += a[i] * b[i]; ma += a[i] * a[i]; mb += b[i] * b[i] }
  if (ma === 0 || mb === 0) return 0
  return dot / (Math.sqrt(ma) * Math.sqrt(mb))
}

/** Predict next query embedding as the mean of the last N observed embeddings. */
export class NBackCentroid implements Predictor {
  readonly id = 'nback-centroid'
  private buf: Float32Array[] = []
  private prediction: Float32Array | null = null

  constructor(private readonly n: number = 4) {}

  scoreAgainst(actual: Float32Array): number | null {
    return this.prediction ? cosineSim(this.prediction, actual) : null
  }

  update(embedding: Float32Array): void {
    this.buf.push(embedding)
    if (this.buf.length > this.n) this.buf.shift()
    const dim = embedding.length
    const acc = new Float32Array(dim)
    for (const v of this.buf) for (let i = 0; i < dim; i++) acc[i] += v[i]
    for (let i = 0; i < dim; i++) acc[i] /= this.buf.length
    this.prediction = acc
  }

  reset(): void { this.buf = []; this.prediction = null }
}

/** RETRIEVE_CACHE-style baseline: predict next query == previous query. */
export class LastQueryBaseline implements Predictor {
  readonly id = 'last-query'
  private prediction: Float32Array | null = null

  scoreAgainst(actual: Float32Array): number | null {
    return this.prediction ? cosineSim(this.prediction, actual) : null
  }

  update(embedding: Float32Array): void { this.prediction = embedding }

  reset(): void { this.prediction = null }
}
