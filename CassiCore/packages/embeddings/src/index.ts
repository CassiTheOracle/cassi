/**
 * @cassicore/embeddings — package barrel (PACKAGER-WRITTEN, Open Flag 7).
 *
 * The source `core/intelligence/embeddings/` dir has no `index.ts`, so this
 * barrel is freshly authored to expose the canonical home symbols consumed by
 * helix + constellation re-points: `getEmbeddingService`, `getRerankerService`,
 * `SqliteVectorIndex`/`getVectorIndex`, the embeddings/types surface, and the
 * shared posture / token-estimation composables. History-preserved import
 * splice from cassicore's core/intelligence/{embeddings,shared}.
 */

export { EmbeddingService, getEmbeddingService, resetEmbeddingService } from './embeddings/embedding-service.js'
export type { EmbeddingMode, EmbeddingServiceConfig } from './embeddings/embedding-service.js'
export { RerankerService, getRerankerService, resetRerankerService } from './embeddings/reranker-service.js'
export type { RerankResult } from './embeddings/reranker-service.js'
export { SqliteVectorIndex, getVectorIndex, resetVectorIndex } from './embeddings/sqlite-index.js'
export type { VectorHit, VectorIndexStats } from './embeddings/sqlite-index.js'
export type { RerankerMode } from './embeddings/types.js'
export { BackgroundEmbeddingWorker, getBackgroundEmbeddingWorker, resetBackgroundEmbeddingWorker } from './embeddings/background-worker.js'
export type { BackgroundWorkerStats } from './embeddings/background-worker.js'
export { composeSystemPrompt, getBaseIdentity, hasContext } from './shared/posture-store.js'
export type { PostureName, AgentType } from './shared/posture-store.js'
export { CHARS_PER_TOKEN, estimateTokens, estimateChars } from './shared/token-estimation.js'
