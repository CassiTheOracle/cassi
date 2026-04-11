/**
 * External Client Integration Layer
 *
 * Provides shared infrastructure for external coding agents (OpenCode,
 * Claude Code, Cursor, Windsurf, etc.) to use CassiCore's cognitive
 * services — thalamus context curation, cortex signals, mnemic field,
 * and locus-bridge assembly.
 *
 * The external client curator works in "index-only" mode: it scores
 * lightweight message digests and returns which indices to keep, so
 * the caller can apply decisions to its own AI SDK message array
 * without losing type fidelity.
 */

export { ExternalClientCurator } from './curator.js'
export type {
  ExternalCurateRequest,
  ExternalCurationResult,
  ExternalMessageDigest,
  CurationGap,
} from './types.js'
