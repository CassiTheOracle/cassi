/**
 * Context Repository types.
 *
 * A Context Repository is a per-project git repo at
 * `~/.cassicore/context-repos/<projectHash>/` that projects select Mnemic
 * engrams + Laminae + skills into inspectable markdown files. It is the
 * "human-readable mirror" of Cassi's working memory.
 *
 * Mnemic remains the source of truth — the context repo is a projection
 * that is always safely rebuildable.
 */

export type ContextEntityKind =
  | 'identity'
  | 'lamina'
  | 'engram'
  | 'skill'
  | 'principle'
  | 'decision'
  | 'weakness'
  | 'note'

export interface ContextFrontmatter {
  /** Stable id; for engrams it's the engram id, for laminae it's the label. */
  id: string
  kind: ContextEntityKind
  /** What produced this projection — 'lamina', 'mnemic', 'pineal', 'manual'. */
  source: string
  priority: number
  pinned: boolean
  potentiation?: number
  tags?: string[]
  /** Block projection for sensitive engrams (frontmatter flag). */
  sensitive?: boolean
  /** Last sync timestamp. */
  syncedAt: string
}

export interface ContextEntity {
  frontmatter: ContextFrontmatter
  body: string
  /** Relative path within the repo, e.g. 'entities/engram-abc.md'. */
  relPath: string
}

export interface ContextRepoConfig {
  enabled: boolean
  /** Override the default ~/.cassicore/context-repos/<hash>/ root. */
  rootDir?: string
  /** Cap on entity files projected per Meditation pass. */
  entityCap: number
  /** Minimum potentiation for engram projection. */
  potentiationThreshold: number
  /** Worktrees older than this are pruned by gc(). */
  worktreeMaxAgeDays: number
}

export const DEFAULT_CONTEXT_REPO_CONFIG: ContextRepoConfig = {
  enabled: true, // Enabled by default — human-readable memory projection
  entityCap: 200,
  potentiationThreshold: 0.6,
  worktreeMaxAgeDays: 30,
}

export interface RepoIdentity {
  /** Project root path (or 'global'). */
  projectPath: string
  /** Hash of projectPath, used as the dir name. */
  projectHash: string
  /** Resolved repo root. */
  repoDir: string
}

export interface RepoStats {
  totalFiles: number
  totalCommits: number
  pinnedEntities: number
  worktrees: number
  diskBytes: number
}
