/**
 * CassiCore Version — canonical version source for ALL consumers.
 * 
 * Computes version from git tags at module load time. Falls back to
 * package.json when git is unavailable (e.g., systemd service from
 * a built artifact without .git/).
 * 
 * This replaces the old core/build-id.ts pattern — all version
 * consumers should import from here.
 * 
 * Consumers:
 *   - core/daemon.ts         → CASSICORE_VERSION, CASSICORE_BUILD_STRING
 *   - mcp/gateway/helpers.ts → GATEWAY_VERSION
 *   - core/tools/hermes-mcp-client.ts → clientInfo
 *   - core/admin-api/health.ts       → health endpoint
 */

import { execSync } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const CURRENT_DIR = dirname(fileURLToPath(import.meta.url))
const GIT_TIMEOUT_MS = 5000

// WHY: At runtime this file may live in dist/core/ (compiled from core/).
// Walk up until we find package.json to locate the true repo root.
function findRepoRoot(startDir: string): string {
  let dir = startDir
  for (let i = 0; i < 5; i++) {
    if (existsSync(resolve(dir, 'package.json'))) return dir
    const parent = dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  return resolve(startDir, '..')
}

const REPO_ROOT = findRepoRoot(CURRENT_DIR)

// ── Git helpers ─────────────────────────────────────────────────

function git(cmd: string): string | null {
  const gitDir = resolve(REPO_ROOT, '.git')
  if (!existsSync(gitDir)) return null
  
  try {
    return execSync(`git ${cmd}`, {
      cwd: REPO_ROOT,
      encoding: 'utf-8',
      timeout: GIT_TIMEOUT_MS,
      stdio: ['pipe', 'pipe', 'pipe'],
    }).trim()
  } catch {
    return null
  }
}

// ── Version computation ─────────────────────────────────────────

interface ParsedDescribe {
  releaseVersion: string
  commitsSinceTag: number
  gitHash: string
  dirty: boolean
  hasTags: boolean
}

/**
 * Parse git describe --tags --long --dirty --always output.
 * 
 * Examples:
 *   v0.4.0-0-gfff05189        → release=0.4.0, count=0, hash=fff05189
 *   v0.4.0-3-g1a2b3c4-dirty  → release=0.4.0, count=3, hash=1a2b3c4, dirty
 *   1a2b3c4                   → no tags, hash only
 */
function parseGitDescribe(raw: string): ParsedDescribe | null {
  const taggedRegex = /^v?(\d+\.\d+\.\d+(?:-[a-zA-Z\d.]+)?)-(\d+)-g([0-9a-f]+)(-dirty)?$/
  const taggedMatch = raw.match(taggedRegex)
  if (taggedMatch) {
    return {
      releaseVersion: taggedMatch[1],
      commitsSinceTag: parseInt(taggedMatch[2], 10),
      gitHash: taggedMatch[3],
      dirty: taggedMatch[4] === '-dirty',
      hasTags: true,
    }
  }

  const untaggedRegex = /^([0-9a-f]+)(-dirty)?$/
  const untaggedMatch = raw.match(untaggedRegex)
  if (untaggedMatch) {
    return {
      releaseVersion: '0.0.0',
      commitsSinceTag: 0,
      gitHash: untaggedMatch[1],
      dirty: untaggedMatch[2] === '-dirty',
      hasTags: false,
    }
  }

  return null
}

/**
 * Compute the next semver bump from conventional commits since last tag.
 */
function computeNextBump(commitsSinceTag: number): 'major' | 'minor' | 'patch' | 'none' {
  if (commitsSinceTag === 0) return 'none'

  const log = git(`log --format="%s" HEAD~${commitsSinceTag}..HEAD`)
  if (!log) return 'none'

  const subjects = log.split('\n').filter(Boolean)
  let bump: 'major' | 'minor' | 'patch' | 'none' = 'none'

  for (const subject of subjects) {
    if (
      subject.includes('BREAKING CHANGE') ||
      subject.includes('BREAKING-CHANGE') ||
      /!:\s/.test(subject)
    ) {
      return 'major'
    }
    if (/^feat(\([^)]*\))?!?:\s/.test(subject)) {
      bump = 'minor'
    }
    if (/^fix(\([^)]*\))?!?:\s/.test(subject) && bump === 'none') {
      bump = 'patch'
    }
  }

  return bump
}

interface VersionInfo {
  releaseVersion: string
  buildVersion: string
  buildDirty: boolean
  nextBump: 'major' | 'minor' | 'patch' | 'none'
  gitRef: string
  hasGit: boolean
}

function computeVersion(): VersionInfo {
  const describe = git('describe --tags --long --dirty --always')
  
  if (describe) {
    const parsed = parseGitDescribe(describe)
    if (parsed) {
      const nextBump = parsed.hasTags
        ? computeNextBump(parsed.commitsSinceTag)
        : 'none'

      const buildVersion = `${parsed.releaseVersion}-${parsed.commitsSinceTag}-g${parsed.gitHash}${parsed.dirty ? '-dirty' : ''}`

      return {
        releaseVersion: parsed.releaseVersion,
        buildVersion,
        buildDirty: parsed.dirty,
        nextBump,
        gitRef: parsed.gitHash,
        hasGit: true,
      }
    }
  }

  // Fallback: read package.json version
  try {
    const pkgPath = resolve(REPO_ROOT, 'package.json')
    const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'))
    const ver = pkg.version || '0.0.0'
    return {
      releaseVersion: ver,
      buildVersion: ver,
      buildDirty: false,
      nextBump: 'none',
      gitRef: 'unknown',
      hasGit: false,
    }
  } catch {
    return {
      releaseVersion: '0.0.0',
      buildVersion: '0.0.0',
      buildDirty: false,
      nextBump: 'none',
      gitRef: 'unknown',
      hasGit: false,
    }
  }
}

// ── Compute once at module load ─────────────────────────────────

const _VERSION = computeVersion()

// ── Public exports ──────────────────────────────────────────────

/** Clean semver release version (e.g. "0.5.0") */
export const CASSICORE_VERSION: string = _VERSION.releaseVersion

/** Full build version with git metadata (e.g. "0.5.0-3-g1a2b3c4") */
export const CASSICORE_BUILD: string = _VERSION.buildVersion

/** Human-readable build string */
export const CASSICORE_BUILD_STRING: string = _VERSION.buildVersion

/** Suggested next semver bump based on commits since last tag */
export const NEXT_BUMP: 'major' | 'minor' | 'patch' | 'none' = _VERSION.nextBump

/** Abbreviated git commit hash (or "unknown") */
export const GIT_REF: string = _VERSION.gitRef

/** Whether git was available for version computation */
export const HAS_GIT: boolean = _VERSION.hasGit

/** Whether the working tree was dirty at load time */
export const BUILD_DIRTY: boolean = _VERSION.buildDirty

// ── Gateway version (MCP protocol uses clean semver) ───────────

export const GATEWAY_VERSION: string = CASSICORE_VERSION

// ── Legacy compatibility with old build-id.ts ───────────────────

export interface BuildIdentifier {
  version: string
  gitRef?: string
}

export function getBuildIdentifier(): BuildIdentifier {
  return {
    version: CASSICORE_VERSION,
    gitRef: GIT_REF !== 'unknown' ? GIT_REF : undefined,
  }
}

export function formatBuildId(id?: BuildIdentifier): string {
  const build = id ?? getBuildIdentifier()
  if (build.gitRef) {
    return `${build.version}+${build.gitRef}`
  }
  return build.version
}

/** Repository root directory (for consumers that need it) */
export function getRepoRoot(): string {
  return REPO_ROOT
}
