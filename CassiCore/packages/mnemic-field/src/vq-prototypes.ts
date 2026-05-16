/**
 * VQ Sector Prototypes — Vector Quantization codebook for automatic domain
 * discovery beyond the 4 Pineal domains.
 *
 * Maintains K learnable prototype vectors (1024-dim). New engrams get θ from
 * their nearest prototype. Consolidation updates prototypes via EMA.
 */

/**
 * Cosine similarity between two vectors (both as ArrayLike<number>).
 * Returns a value in [-1, 1] where 1 = identical direction.
 */
export function cosineSimilarity(a: ArrayLike<number>, b: ArrayLike<number>): number {
  if (a.length !== b.length || a.length === 0) return 0
  let dot = 0
  let normA = 0
  let normB = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    normA += a[i] * a[i]
    normB += b[i] * b[i]
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB)
  return denom > 0 ? dot / denom : 0
}

/** Cosine distance: 1 - cosineSimilarity. Range [0, 2]. */
export function cosineDistance(a: ArrayLike<number>, b: ArrayLike<number>): number {
  return 1 - cosineSimilarity(a, b)
}

export interface AssignResult {
  prototypeIdx: number
  distance: number
}

/**
 * Pineal domain anchor labels mapped to their angular positions (radians).
 * Identity = 0°, Wisdom = 90°, Philosophy = 180°, Praxis = 270°.
 */
const PINEAL_ANCHOR_ANGLES: Record<string, number> = {
  identity: 0,
  wisdom: Math.PI / 2,
  philosophy: Math.PI,
  praxis: (3 * Math.PI) / 2,
}

/** Default threshold for creating a new prototype (cosine distance). */
const DEFAULT_CREATE_THRESHOLD = 0.6

/** Default EMA alpha for prototype updates. */
const DEFAULT_EMA_ALPHA = 0.01

export class VQSectorPrototypes {
  /** Learnable prototype vectors, each of length `dim`. */
  readonly codebook: Float32Array[] = []

  /** Human-readable labels for each prototype (e.g., "identity", "domain-5"). */
  readonly domainLabels: string[] = []

  /** Incrementing counter for auto-labeling new domains. */
  private nextDomainId = 1

  /** Embedding dimension (typically 1024). */
  readonly dim: number

  /**
   * Whether initFromAnchors has been called. assign() will lazy-init
   * if the codebook is empty on first use.
   */
  private anchorsInitialized = false

  constructor(dim: number) {
    this.dim = dim
  }

  /**
   * Seed the codebook with 4 prototypes at Pineal domain angles.
   * Each anchor must be a Float32Array of length `this.dim`.
   * Only anchors present in the map are seeded; missing ones are skipped.
   */
  initFromAnchors(anchors: Map<string, Float32Array>): void {
    if (this.anchorsInitialized) return
    this.anchorsInitialized = true

    // Seed in a fixed order so prototypeIdx is predictable
    const orderedLabels = ['identity', 'wisdom', 'philosophy', 'praxis']
    for (const label of orderedLabels) {
      const embedding = anchors.get(label)
      if (embedding && embedding.length === this.dim) {
        this.codebook.push(new Float32Array(embedding))
        this.domainLabels.push(label)
      }
    }

    // If no anchors were provided, leave codebook empty for lazy init
    if (this.codebook.length === 0) {
      this.anchorsInitialized = false
    }
  }

  /**
   * Find the nearest prototype by cosine distance.
   * If the codebook is empty, lazy-initializes with a single prototype
   * copied from the input embedding and labeled "domain-1".
   */
  assign(embedding: Float32Array): AssignResult {
    if (this.codebook.length === 0) {
      this._lazyInit(embedding)
    }

    let bestIdx = 0
    let bestDist = Infinity

    for (let i = 0; i < this.codebook.length; i++) {
      const dist = cosineDistance(embedding, this.codebook[i])
      if (dist < bestDist) {
        bestDist = dist
        bestIdx = i
      }
    }

    return { prototypeIdx: bestIdx, distance: bestDist }
  }

  /**
   * Create a new prototype if the embedding is far from all existing
   * prototypes (cosine distance > threshold for every prototype).
   * Returns the index of either the newly created prototype or the
   * nearest existing one.
   *
   * New prototypes are assigned even angular spacing automatically
   * via prototypeAngle().
   */
  maybeCreatePrototype(
    embedding: Float32Array,
    threshold: number = DEFAULT_CREATE_THRESHOLD,
  ): number {
    if (this.codebook.length === 0) {
      this._lazyInit(embedding)
      return 0
    }

    // Check distance to all existing prototypes
    let minDist = Infinity
    for (let i = 0; i < this.codebook.length; i++) {
      const dist = cosineDistance(embedding, this.codebook[i])
      if (dist < minDist) minDist = dist
    }

    // If close to an existing prototype, return its index
    if (minDist <= threshold) {
      let bestIdx = 0
      let bestDist = Infinity
      for (let i = 0; i < this.codebook.length; i++) {
        const dist = cosineDistance(embedding, this.codebook[i])
        if (dist < bestDist) {
          bestDist = dist
          bestIdx = i
        }
      }
      return bestIdx
    }

    // Far from all existing — create a new prototype
    const newIdx = this.codebook.length
    this.codebook.push(new Float32Array(embedding))
    this.domainLabels.push(`domain-${this.nextDomainId++}`)
    return newIdx
  }

  /**
   * Update a prototype via exponential moving average (EMA):
   *   prototype = (1 - alpha) * prototype + alpha * embedding
   */
  updatePrototype(
    idx: number,
    embedding: Float32Array,
    alpha: number = DEFAULT_EMA_ALPHA,
  ): void {
    if (idx < 0 || idx >= this.codebook.length) return
    const proto = this.codebook[idx]
    for (let i = 0; i < this.dim; i++) {
      proto[i] = (1 - alpha) * proto[i] + alpha * embedding[i]
    }
  }

  /**
   * Return the angular position (θ in radians) for a prototype.
   * Angles are evenly distributed around the circle: 2π * idx / count.
   *
   * For the 4 Pineal domains seeded with initFromAnchors, indices 0-3
   * correspond to: identity=0°, wisdom=90°, philosophy=180°, praxis=270°.
   */
  prototypeAngle(idx: number): number {
    if (this.codebook.length === 0) return 0
    return (2 * Math.PI * idx) / this.codebook.length
  }

  /** Number of prototypes in the codebook. */
  getPrototypeCount(): number {
    return this.codebook.length
  }

  /**
   * Lazy initialization: seed with a single prototype copied from
   * the first embedding seen. This ensures assign() and
   * maybeCreatePrototype() work even before initFromAnchors() is called.
   */
  private _lazyInit(embedding: Float32Array): void {
    this.codebook.push(new Float32Array(embedding))
    this.domainLabels.push(`domain-${this.nextDomainId++}`)
  }
}
