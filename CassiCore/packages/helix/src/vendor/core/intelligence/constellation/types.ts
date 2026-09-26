/**
 * Constellation Types (vendor stub)
 *
 * Faithful type surface for CassiCore `core/intelligence/constellation/types.ts`,
 * limited to the symbol helix consumes: `ToolAccessLevel` (used as an inline
 * `import('../constellation/types.js').ToolAccessLevel` field type by
 * helix-pipeline.ts and helix-posture-runner.ts).
 */

/**
 * Tool access levels for postures.
 *
 * - `full`: All tools including write/edit/shell
 * - `read-only`: Only read_file, grep, glob, etc.
 * - `read-only+memory`: Read tools + memory search/store
 * - `none`: No tool access (pure dialectic/communication agent)
 */
export type ToolAccessLevel = 'full' | 'read-only' | 'read-only+memory' | 'none'
