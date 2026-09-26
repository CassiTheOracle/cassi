/**
 * VENDORED — faithful type surface of `core/intelligence/embeddings/embedding-service.ts`.
 * Consumed by @cassicore/thalamus cross-session-index.ts as `EmbeddingService` (type-only).
 *
 * Self-contained stub: declares the `EmbeddingService` class type with the shape used
 * by the consumer. No runtime dependency on the embedding server. Re-point to
 * `@cassicore/embeddings` when that package lands (P5 repoint log).
 */

/** Embedding mode — determines the system prompt for asymmetric search */
export type EmbeddingMode = 'query' | 'document'

/**
 * Shared embedding service — wraps vLLM /v1/embeddings with caching,
 * circuit breaker, and batching (type surface).
 */
export declare class EmbeddingService {
  /** Embed a single text. Returns null if server unavailable. */
  embed(text: string, mode?: EmbeddingMode): Promise<number[] | null>
  /** Embed multiple texts in a single batch. Returns parallel array (null for failures). */
  embedBatch(texts: string[], mode?: EmbeddingMode): Promise<Array<number[] | null>>
  /** Cosine similarity between two vectors. Returns 0 on null/mismatched input. */
  cosineSimilarity(a: number[] | null, b: number[] | null): number
  /** Check if any embedding server instance is available. */
  readonly available: boolean
  /** Model tag used for cache key differentiation. */
  readonly model: string
  /** Number of cached embeddings. */
  readonly cacheSize: number
}
