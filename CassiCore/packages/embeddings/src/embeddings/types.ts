/**
 * Shared types for the reranker/embeddings subsystem.
 *
 * RerankerMode lives here so both consumers (MnemicField retrieval and the
 * Thalamus RerankerCompressor) reference the same identity. Without a shared
 * home, the type was defined inside mnemic-field/types.ts and tacit-imported
 * by other modules — which makes any future widening (e.g. adding a 'hybrid'
 * mode) require parallel changes in two unrelated files.
 *
 * Modes:
 *   - 'local' — use the local cross-encoder reranker (zerank-server / vLLM).
 *               Fast, cheap, narrow window of relevance.
 *   - 'llm'   — use a cloud LLM as the reranker. Slower, costlier, deeper
 *               relevance judgment. Currently only MnemicField has an LLM
 *               reranker wired (`LLMReranker` in mnemic-field/llm-reranker.ts);
 *               Thalamus's RerankerCompressor still only honors 'local'/'off'.
 *   - 'off'   — skip reranking entirely. Falls back to whatever scoring the
 *               consumer was using before reranker integration.
 */
export type RerankerMode = 'local' | 'llm' | 'off'
