/**
 * code-extractor.ts — Extracts source_file engrams from mnemic-field.db
 * to a staging directory for building.
 *
 * Runs in the supervisor context (before daemon fork) or as a standalone CLI.
 * Opens the DB read-only — no daemon required.
 */

import Database from 'better-sqlite3'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { execSync } from 'node:child_process'

export interface ExtractionResult {
  success: boolean
  filesExtracted: number
  stagingDir: string
  buildOutput?: string
  error?: string
  durationMs: number
}

interface SourceFileRow {
  id: string
  content: string
  metadata: string
}

interface SourceFileMetadataParsed {
  filePath: string
  language?: string
  checksum?: string
  sizeBytes?: number
  buildable?: boolean
}

const DATA_DIR = path.join(os.homedir(), '.cassicore', 'data')
const DB_PATH = path.join(DATA_DIR, 'mnemic-field.db')
const STAGING_BASE = path.join(os.homedir(), '.cassicore', 'staging')

/**
 * Check if the code in the DB is newer than what's on disk.
 * Returns the latest committed_at timestamp, or null if no changesets exist.
 */
export function checkForUpdates(dbPath = DB_PATH): { needsExtraction: boolean; latestCommit: string | null } {
  if (!fs.existsSync(dbPath)) {
    return { needsExtraction: false, latestCommit: null }
  }

  let db: Database.Database | null = null
  try {
    db = new Database(dbPath, { readonly: true })
    db.pragma('busy_timeout = 3000')

    const hasTable = db.prepare(
      `SELECT 1 FROM sqlite_master WHERE type='table' AND name='changesets'`
    ).get()

    if (!hasTable) {
      return { needsExtraction: false, latestCommit: null }
    }

    const row = db.prepare(
      `SELECT MAX(committed_at) as latest FROM changesets WHERE status IN ('committed', 'verified')`
    ).get() as { latest: string | null } | undefined

    const latestCommit = row?.latest ?? null
    if (!latestCommit) {
      return { needsExtraction: false, latestCommit: null }
    }

    return { needsExtraction: true, latestCommit }
  } catch {
    return { needsExtraction: false, latestCommit: null }
  } finally {
    try { db?.close() } catch { /* ignore */ }
  }
}

/**
 * Extract all source_file engrams from the DB to a staging directory.
 */
export function extractToStaging(
  repoRoot: string,
  dbPath = DB_PATH,
  stagingDir?: string,
): ExtractionResult {
  const start = Date.now()
  const staging = stagingDir ?? path.join(STAGING_BASE, `extract-${Date.now()}`)

  if (!fs.existsSync(dbPath)) {
    return {
      success: false,
      filesExtracted: 0,
      stagingDir: staging,
      error: `Database not found: ${dbPath}`,
      durationMs: Date.now() - start,
    }
  }

  let db: Database.Database | null = null
  try {
    db = new Database(dbPath, { readonly: true })
    db.pragma('busy_timeout = 5000')

    const rows = db.prepare(`
      SELECT id, content, metadata FROM engrams WHERE node_type = 'source_file'
    `).all() as SourceFileRow[]

    if (rows.length === 0) {
      return {
        success: false,
        filesExtracted: 0,
        stagingDir: staging,
        error: 'No source_file engrams found in database',
        durationMs: Date.now() - start,
      }
    }

    fs.mkdirSync(staging, { recursive: true })

    let filesExtracted = 0
    for (const row of rows) {
      let meta: SourceFileMetadataParsed
      try {
        meta = JSON.parse(row.metadata) as SourceFileMetadataParsed
      } catch {
        continue
      }

      if (!meta.filePath) continue

      const targetPath = path.join(staging, meta.filePath)
      const targetDir = path.dirname(targetPath)
      if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir, { recursive: true })
      }

      fs.writeFileSync(targetPath, row.content, 'utf8')
      filesExtracted++
    }

    // Copy non-code config files from the repo root that the build needs
    const configFiles = [
      'package.json', 'package-lock.json', 'tsconfig.json',
      '.npmrc',
    ]
    for (const cf of configFiles) {
      const src = path.join(repoRoot, cf)
      if (fs.existsSync(src)) {
        fs.copyFileSync(src, path.join(staging, cf))
      }
    }

    // Symlink node_modules to avoid reinstalling
    const nodeModulesSrc = path.join(repoRoot, 'node_modules')
    const nodeModulesDst = path.join(staging, 'node_modules')
    if (fs.existsSync(nodeModulesSrc) && !fs.existsSync(nodeModulesDst)) {
      fs.symlinkSync(nodeModulesSrc, nodeModulesDst, 'dir')
    }

    return {
      success: true,
      filesExtracted,
      stagingDir: staging,
      durationMs: Date.now() - start,
    }
  } catch (err) {
    return {
      success: false,
      filesExtracted: 0,
      stagingDir: staging,
      error: String(err),
      durationMs: Date.now() - start,
    }
  } finally {
    try { db?.close() } catch { /* ignore */ }
  }
}

/**
 * Run tsc type-check against a staging directory.
 */
export function typeCheck(stagingDir: string): { success: boolean; output: string } {
  try {
    const output = execSync('npx tsc --noEmit', {
      cwd: stagingDir,
      encoding: 'utf8',
      timeout: 120_000,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    return { success: true, output: output || '' }
  } catch (err: unknown) {
    const output = (err as { stdout?: string; stderr?: string }).stdout
      ?? (err as { stderr?: string }).stderr
      ?? String(err)
    return { success: false, output }
  }
}

/**
 * Run full tsc build against a staging directory.
 */
export function build(stagingDir: string): { success: boolean; output: string; distDir: string } {
  const distDir = path.join(stagingDir, 'dist')
  try {
    const output = execSync('npx tsc', {
      cwd: stagingDir,
      encoding: 'utf8',
      timeout: 120_000,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    return { success: true, output: output || '', distDir }
  } catch (err: unknown) {
    const output = (err as { stdout?: string; stderr?: string }).stdout
      ?? (err as { stderr?: string }).stderr
      ?? String(err)
    return { success: false, output, distDir }
  }
}

/**
 * Mark a changeset as verified in the DB (build succeeded).
 */
export function markVerified(changesetId: string, dbPath = DB_PATH): void {
  const db = new Database(dbPath)
  try {
    db.pragma('busy_timeout = 5000')
    db.prepare(`UPDATE changesets SET status = 'verified', build_verified = 1 WHERE id = ?`).run(changesetId)
  } finally {
    db.close()
  }
}

/**
 * Mark a changeset as failed in the DB.
 */
export function markFailed(changesetId: string, dbPath = DB_PATH): void {
  const db = new Database(dbPath)
  try {
    db.pragma('busy_timeout = 5000')
    db.prepare(`UPDATE changesets SET status = 'failed' WHERE id = ?`).run(changesetId)
  } finally {
    db.close()
  }
}

/**
 * Full extraction + build pipeline. Used by the supervisor before daemon fork.
 *
 * 1. Extract source_file engrams to staging
 * 2. Type-check (tsc --noEmit)
 * 3. If type-check passes, full build (tsc)
 * 4. If build passes, swap staging dist/ into production dist/
 * 5. Clean up staging
 */
export function extractAndBuild(
  repoRoot: string,
  dbPath = DB_PATH,
): ExtractionResult {
  const start = Date.now()

  const extraction = extractToStaging(repoRoot, dbPath)
  if (!extraction.success) return extraction

  const check = typeCheck(extraction.stagingDir)
  if (!check.success) {
    cleanupStaging(extraction.stagingDir)
    return {
      success: false,
      filesExtracted: extraction.filesExtracted,
      stagingDir: extraction.stagingDir,
      buildOutput: check.output,
      error: 'Type check failed',
      durationMs: Date.now() - start,
    }
  }

  const buildResult = build(extraction.stagingDir)
  if (!buildResult.success) {
    cleanupStaging(extraction.stagingDir)
    return {
      success: false,
      filesExtracted: extraction.filesExtracted,
      stagingDir: extraction.stagingDir,
      buildOutput: buildResult.output,
      error: 'Build failed',
      durationMs: Date.now() - start,
    }
  }

  // Swap dist/ — move current dist to backup, move staging dist to production
  const prodDist = path.join(repoRoot, 'dist')
  const backupDist = path.join(repoRoot, 'dist.bak')

  try {
    if (fs.existsSync(backupDist)) {
      fs.rmSync(backupDist, { recursive: true, force: true })
    }
    if (fs.existsSync(prodDist)) {
      fs.renameSync(prodDist, backupDist)
    }
    fs.renameSync(buildResult.distDir, prodDist)

    // Also copy source files to repo root (for tsx dev mode and git)
    copySourceToRepo(extraction.stagingDir, repoRoot)

    // Clean up backup and staging
    if (fs.existsSync(backupDist)) {
      fs.rmSync(backupDist, { recursive: true, force: true })
    }
  } catch (err) {
    // Restore backup if swap failed
    if (fs.existsSync(backupDist) && !fs.existsSync(prodDist)) {
      try { fs.renameSync(backupDist, prodDist) } catch { /* best effort */ }
    }
    cleanupStaging(extraction.stagingDir)
    return {
      success: false,
      filesExtracted: extraction.filesExtracted,
      stagingDir: extraction.stagingDir,
      error: `Dist swap failed: ${String(err)}`,
      durationMs: Date.now() - start,
    }
  }

  cleanupStaging(extraction.stagingDir)

  return {
    success: true,
    filesExtracted: extraction.filesExtracted,
    stagingDir: extraction.stagingDir,
    buildOutput: buildResult.output,
    durationMs: Date.now() - start,
  }
}

/**
 * Copy extracted source files back to the repo root (excluding config/node_modules).
 */
function copySourceToRepo(stagingDir: string, repoRoot: string): void {
  const skip = new Set(['node_modules', 'dist', 'package.json', 'package-lock.json', 'tsconfig.json', '.npmrc'])

  const copyRecursive = (src: string, dest: string) => {
    const entries = fs.readdirSync(src, { withFileTypes: true })
    for (const entry of entries) {
      if (skip.has(entry.name)) continue
      const srcPath = path.join(src, entry.name)
      const destPath = path.join(dest, entry.name)
      if (entry.isDirectory()) {
        fs.mkdirSync(destPath, { recursive: true })
        copyRecursive(srcPath, destPath)
      } else {
        fs.copyFileSync(srcPath, destPath)
      }
    }
  }

  copyRecursive(stagingDir, repoRoot)
}

function cleanupStaging(stagingDir: string): void {
  try {
    if (fs.existsSync(stagingDir)) {
      fs.rmSync(stagingDir, { recursive: true, force: true })
    }
  } catch { /* best effort cleanup */ }
}
