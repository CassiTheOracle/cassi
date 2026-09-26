/**
 * code-analysis-context — Port over CassiCore's `code-analysis/context-assembler.js` (prepareContext).
 *
 * The real implementation imports `code-analysis/gitnexus-bridge.js`, which spawns `git`
 * subprocesses and runs background index/symbol refreshes — deep CassiCore code-analysis
 * integration. Constellation (fast-decomposer) calls `prepareContext(...)` to build
 * `PreparedContext` for task decomposition. Vendoring it would drag the git-nexus machinery
 * into the standalone package, so it is a port: the type surface + a `not connected` default.
 *
 * Self-contained: depends only on local port types.
 */

/** Mirror of `code-analysis/types.js` prepared-context surface used by constellation. */
export interface PreparedContextFile {
  filePath: string
  relevance: number
  reason: string
  keySymbols: string[]
  excerpt?: string
  [key: string]: unknown
}

/** Mirror of `code-analysis/types.js` prepared-context surface used by constellation. */
export interface PreparedContext {
  /** The (possibly truncated) assembled context text. */
  text?: string
  /** Structured context blocks, when available. */
  blocks?: unknown[]
  /** Relevant files surfaced by the code index. */
  files: PreparedContextFile[]
  /** Extracted keyword hints from the goal/task. */
  extractedKeywords: string[]
  summary?: string
  estimatedTokens?: number
  /** Whether context assembly reached the repository codebase. */
  usedCodebaseIndex?: boolean
  /** Disposition flags the caller may inspect. */
  reachedCharBudget?: boolean
  packageName?: string
  fileName?: string
  languages?: string[]
  symbols?: Array<{ name: string; kind?: string; file?: string }>
  error?: string
  [key: string]: unknown
}

/** Mirror of the `PrepareContextOptions` used by fast-decomposer. */
export interface PrepareContextOptions {
  repoPath?: string
  goal?: string
  taskDescription?: string
  task?: string
  tokenBudget?: number
  includeContent?: boolean
  includeSymbols?: boolean
  includeFileList?: boolean
  maxChars?: number
  maxTokens?: number
  [key: string]: unknown
}

/**
 * Build a codebase context snapshot for a task. Real implementation requires
 * the host's git-nexus code-analysis integration. The host's `routeTool` is passed
 * through so a wired implementation can dispatch git/read tools at runtime.
 */
export function prepareContext(
  _routeTool: (tool: string, args: unknown) => Promise<unknown>,
  _opts: PrepareContextOptions,
  _log?: unknown,
): Promise<PreparedContext> {
  return Promise.reject(
    new Error(
      '[constellation] code-analysis-context not connected — wire prepareContext in the host',
    ),
  )
}
