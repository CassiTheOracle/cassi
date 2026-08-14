/**
 * mnemic-writeback-target.ts — Bridges ContextRepo manual file edits back
 * into the Mnemic Field.
 *
 * entities/*.md → engram update
 * skills/*.md → skill upsert (best-effort)
 * system/*.md → flag for Pineal review
 */

import type { MnemicField } from '@cassicore/mnemic-field'
import type { WritebackTarget } from '../context-repo/writeback.js'
import type { ILogger } from '@cassicore/foundation'

export class MnemicWritebackTarget implements WritebackTarget {
  constructor(
    private mnemic: MnemicField,
    private logger: ILogger,
  ) {}

  updateEngram(id: string, content: string): void {
    try {
      const engram = this.mnemic.get(id)
      if (!engram) {
        this.logger.debug?.('[writeback] engram not found, creating', { id })
        this.mnemic.store({
          nodeType: 'fact',
          content,
          metadata: { source: 'context-repo-writeback', originalId: id },
        })
        return
      }
      this.mnemic.update(id, { content })
      this.logger.info?.('[writeback] engram updated from file edit', { id })
    } catch (err) {
      this.logger.warn?.('[writeback] engram update failed', { id, error: String(err) })
    }
  }

  upsertSkill(id: string, content: string): void {
    try {
      this.mnemic.store({
        nodeType: 'pattern',
        content,
        metadata: { source: 'context-repo-writeback', skillId: id },
      })
      this.logger.info?.('[writeback] skill stored from file edit', { id })
    } catch (err) {
      this.logger.warn?.('[writeback] skill store failed', { id, error: String(err) })
    }
  }

  flagSystemEdit(file: string, content: string): void {
    // Store as a low-potentiation engram flagged for Pineal review
    try {
      this.mnemic.store({
        nodeType: 'fact',
        content: `File: ${file}\n\n${content.slice(0, 2000)}`,
        metadata: { source: 'context-repo-writeback', file, flagged: true },
      })
      this.logger.info?.('[writeback] system edit flagged for Pineal review', { file })
    } catch (err) {
      this.logger.warn?.('[writeback] system edit flag failed', { file, error: String(err) })
    }
  }
}
