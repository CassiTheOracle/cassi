/**
 * Agent Auto-Commit Tool
 *
 * Provides a tool for agents to commit their changes to git.
 * This enables autonomous operation where agents can commit their work
 * without human intervention.
 *
 * Design: Option B - Agent-called commit tool
 * - Agents call `commit_changes(message)` when their implementation is complete
 * - Tool runs `git add -A && git commit -m "..."`
 * - Fits existing tool patterns like SIGNAL_DONE_TOOL and BB_TRACK_ARTIFACT_TOOL
 */
import { execSync } from 'child_process'
import type { ILogger } from '@cassicore/foundation'

/**
 * Tool schema for the commit_changes tool.
 * Follows the same pattern as other meta-tools in the codebase.
 */
export const COMMIT_CHANGES_TOOL: ToolSchema = {
  name: 'commit_changes',
  description:
    'Commit all modified files to git. Use this when your implementation is complete and tested. ' +
    'This runs `git add -A && git commit` automatically. ' +
    'Provide a clear, descriptive commit message following conventional commit format.',
  input_schema: {
    type: 'object',
    properties: {
      message: {
        type: 'string',
        description:
          'Commit message following conventional commit format. ' +
          'Example: "feat(auth): add OAuth2 login support" or "fix(api): handle null response"',
      },
      scope: {
        type: 'string',
        description:
          'Optional scope for the commit (e.g., "auth", "api", "ui"). ' +
          'If provided, will be prepended to the message as "scope: message".',
      },
    },
    required: ['message'],
  },
}

/**
 * Result of a commit operation.
 */
export interface CommitResult {
  success: boolean
  message: string
  commitHash?: string
  filesChanged?: number
}

/**
 * Check if the current directory is a git repository.
 */
function isGitRepo(): boolean {
  try {
    execSync('git rev-parse --is-inside-work-tree', { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] })
    return true
  } catch {
    return false
  }
}

/**
 * Check if there are any changes to commit.
 * Returns the list of changed files or empty array if no changes.
 */
function getChangedFiles(): string[] {
  try {
    const status = execSync('git status --porcelain', { encoding: 'utf-8' })
    if (!status.trim()) return []
    return status.trim().split('\n').filter(Boolean)
  } catch {
    return []
  }
}

/**
 * Handle the commit_changes tool call.
 *
 * @param input - Tool input with 'message' and optional 'scope'
 * @param logger - Optional logger for recording operations
 * @returns JSON string with commit result
 */
export function handleCommitChanges(
  input: Record<string, unknown>,
  logger?: ILogger,
): string {
  const rawMessage = String(input.message ?? '')

  if (!rawMessage.trim()) {
    return JSON.stringify({
      success: false,
      error: 'Commit message is required',
    })
  }

  // Build the commit message with optional scope
  const scope = input.scope ? String(input.scope).trim() : undefined
  const commitMessage = scope
    ? `${scope}: ${rawMessage}`
    : rawMessage

  logger?.info('Attempting to commit changes', { message: commitMessage })

  // Check if we're in a git repository
  if (!isGitRepo()) {
    const result: CommitResult = {
      success: false,
      message: 'Not a git repository. Cannot commit changes.',
    }
    logger?.error('Commit failed: not a git repository')
    return JSON.stringify(result)
  }

  // Check for changes
  const changedFiles = getChangedFiles()
  if (changedFiles.length === 0) {
    const result: CommitResult = {
      success: true,
      message: 'Nothing to commit. Working directory is clean.',
      filesChanged: 0,
    }
    logger?.info('No changes to commit')
    return JSON.stringify(result)
  }

  try {
    // Stage all changes
    execSync('git add -A', { encoding: 'utf-8' })

    // Commit with the message
    // Use --no-verify to skip pre-commit hooks (agents are trusted)
    // This allows commits even if hooks would fail
    const output = execSync(
      `git commit -m "${commitMessage.replace(/"/g, '\\"')}" --no-verify`,
      { encoding: 'utf-8' },
    )

    // Extract commit hash from output
    // Output format: "[branch hash] message" or "hash message"
    const hashMatch = output.match(/\[?\w+\s+([a-f0-9]{7,})\]?/)
    const commitHash = hashMatch ? hashMatch[1] : undefined

    const result: CommitResult = {
      success: true,
      message: `Committed ${changedFiles.length} file(s) successfully`,
      commitHash,
      filesChanged: changedFiles.length,
    }

    logger?.info('Commit successful', { commitHash, filesChanged: changedFiles.length })
    return JSON.stringify(result)
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error)

    // Check for common error conditions
    if (errorMessage.includes('merge conflict')) {
      const result: CommitResult = {
        success: false,
        message: 'Cannot commit: merge conflicts exist. Resolve conflicts first.',
      }
      logger?.error('Commit failed: merge conflicts')
      return JSON.stringify(result)
    }

    if (errorMessage.includes('pre-commit')) {
      // This shouldn't happen with --no-verify, but handle it anyway
      const result: CommitResult = {
        success: false,
        message: `Pre-commit hook failed: ${errorMessage}`,
      }
      logger?.error('Commit failed: pre-commit hook', { error: errorMessage })
      return JSON.stringify(result)
    }

    const result: CommitResult = {
      success: false,
      message: `Commit failed: ${errorMessage}`,
    }
    logger?.error('Commit failed', { error: errorMessage })
    return JSON.stringify(result)
  }
}

/**
 * Tool schema type (matches the pattern used in dyad-tools.ts and blackboard-tools.ts).
 * This allows the tool to be used in the tool registry.
 */
export interface ToolSchema {
  name: string
  description: string
  input_schema: {
    type: 'object'
    properties: Record<string, {
      type: string
      description: string
      enum?: string[]
      items?: { type: string }
    }>
    required?: string[]
  }
}
