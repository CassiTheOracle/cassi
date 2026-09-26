/**
 * Shared math utilities used across the mnemic field subsystems.
 *
 * These were duplicated in field-generator.ts, visual-ingestor.ts, and
 * spatial-index.ts. Centralized here for single-source-of-truth.
 */

/** Cosine similarity between two float arrays. */
export function cosineSimilarity(a: Float32Array | number[], b: Float32Array | number[]): number {
  const dim = Math.min(a.length, b.length);
  let dot = 0, magA = 0, magB = 0;
  for (let i = 0; i < dim; i++) {
    dot += (a[i] ?? 0) * (b[i] ?? 0);
    magA += (a[i] ?? 0) * (a[i] ?? 0);
    magB += (b[i] ?? 0) * (b[i] ?? 0);
  }
  const denom = Math.sqrt(magA) * Math.sqrt(magB);
  return denom < 1e-8 ? 0 : dot / denom;
}

/** Node types excluded from cross-modal linking (structural/operational). */
export const STRUCTURAL_NODE_TYPES: ReadonlySet<string> = new Set([
  'message', 'tool_invocation', 'tool', 'bridge',
  'session', 'file', 'file_version', 'file_read',
  'changeset', 'replay_segment', 'thought_command',
  'attractor', 'generation',
]);

/** Simple deterministic hash for dedup detection. */
export function simpleHash(input: string): string {
  let h = 0;
  for (let i = 0; i < input.length; i++) {
    h = ((h << 5) - h + input.charCodeAt(i)) | 0;
  }
  return Math.abs(h).toString(16).padStart(8, '0');
}
