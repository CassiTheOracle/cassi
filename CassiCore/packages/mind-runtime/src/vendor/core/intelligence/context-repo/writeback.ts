/**
 * Pull-based file-watcher for the context repo: manual edits in entities/ and
 * skills/ propagate back to Mnemic; edits in system/ are flagged for Pineal
 * review. Callers invoke scan() periodically instead of keeping an inotify fd.
 */

import fs from 'node:fs'
import path from 'node:path'

import type { ILogger } from '@cassicore/foundation'
import type { ContextRepoFs } from './fs.js'
import { parseEntity } from './fs.js'

export interface WritebackTarget {
  /** Update an engram by id with new content. */
  updateEngram?: (id: string, content: string) => void
  /** Add or update a skill. */
  upsertSkill?: (id: string, content: string) => void
  /** Flag a system/* manual edit for Pineal review. */
  flagSystemEdit?: (file: string, content: string) => void
}

export class Writeback {
  /** Last-seen mtime per file, so we only emit on actual changes. */
  private mtimes = new Map<string, number>()

  constructor(
    private readonly repo: ContextRepoFs,
    private readonly target: WritebackTarget,
    private readonly logger: ILogger,
  ) {}

  /** Scan watched dirs and emit writebacks. Returns counts of events fired. */
  scan(): { engrams: number; skills: number; system: number } {
    let engrams = 0
    let skills = 0
    let system = 0

    engrams += this.scanDir('entities', (file, raw) => {
      const ent = parseEntity(file, raw)
      if (ent && ent.frontmatter.kind === 'engram' && this.target.updateEngram) {
        this.target.updateEngram(ent.frontmatter.id, ent.body)
        return true
      }
      return false
    })
    skills += this.scanDir('skills', (file, raw) => {
      const ent = parseEntity(file, raw)
      if (ent && this.target.upsertSkill) {
        this.target.upsertSkill(ent.frontmatter.id, ent.body)
        return true
      }
      return false
    })
    system += this.scanDir('system', (file, raw) => {
      if (this.target.flagSystemEdit) {
        this.target.flagSystemEdit(file, raw)
        return true
      }
      return false
    })

    return { engrams, skills, system }
  }

  private scanDir(prefix: string, handle: (file: string, raw: string) => boolean): number {
    const dir = path.join(this.repo.identity.repoDir, prefix)
    if (!fs.existsSync(dir)) return 0
    let count = 0
    const seen = new Set<string>()
    for (const name of fs.readdirSync(dir)) {
      if (!name.endsWith('.md')) continue
      const full = path.join(dir, name)
      seen.add(full)
      let stat: fs.Stats
      try { stat = fs.statSync(full) } catch { continue }
      const last = this.mtimes.get(full)
      if (last !== undefined && stat.mtimeMs <= last) continue
      const raw = fs.readFileSync(full, 'utf8')
      try {
        if (handle(`${prefix}/${name}`, raw)) count++
      } catch (err) {
        this.logger.warn?.('[context-repo] writeback handler failed', { file: name, error: String(err) })
      }
      this.mtimes.set(full, stat.mtimeMs)
    }
    // Prune entries for files that were deleted. Otherwise mtimes grows
    // unbounded across sessions and risks false-negative diffs if a deleted
    // path is later re-created with an older mtime than the stale entry.
    const dirPrefix = dir + path.sep
    for (const key of this.mtimes.keys()) {
      if (key.startsWith(dirPrefix) && !seen.has(key)) this.mtimes.delete(key)
    }
    return count
  }

  /** Reset known mtimes — used after a projection pass to avoid echo. */
  resetMtimes(): void { this.mtimes.clear() }
}
