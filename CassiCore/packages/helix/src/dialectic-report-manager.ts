/**
 * DialecticReportManager — Standalone report management extracted from DialecticChannel.
 *
 * Refactoring #3 from c-27 review: separates report logic (init, add, revise,
 * promote, discard, metrics) from dialectic messaging so each concern can evolve
 * independently.
 *
 * The Brainstem auto-generates report sections in focused profiles, but the
 * manual report tools (report_add_section, etc.) still exist in the 'full'
 * profile for backward compatibility.
 */

import type { Report, ReportSection, ReportSectionType, ReportSectionStatus, ReportQualityMetrics } from '@cassicore/foundation'

export class DialecticReportManager {
  private report: Report | null = null
  private sectionCounter = 0
  private readonly sessionId?: string

  constructor(sessionId?: string) {
    this.sessionId = sessionId
  }

  initReport(goal: string): Report {
    const now = Date.now()
    this.report = {
      id: `report-${now}`,
      goal,
      sections: [],
      createdAt: now,
      updatedAt: now,
    }
    return this.report
  }

  addSection(section: {
    type: ReportSectionType
    status?: ReportSectionStatus
    title: string
    content: string
    author: string
    confidence?: number
    references?: string[]
    threadId?: string
    respondsTo?: string
    challenges?: string
    supports?: string
  }): ReportSection {
    if (!this.report) this.initReport('')
    const now = Date.now()
    const id = `rs-${++this.sectionCounter}`
    const newSection: ReportSection = {
      id,
      type: section.type,
      status: section.status ?? 'active',
      title: section.title,
      content: section.content,
      author: section.author,
      confidence: section.confidence,
      references: section.references,
      threadId: section.threadId,
      respondsTo: section.respondsTo,
      challenges: section.challenges,
      supports: section.supports,
      createdAt: now,
      updatedAt: now,
    }
    this.report!.sections.push(newSection)
    this.report!.updatedAt = now
    return newSection
  }

  autoDraftFromFinding(posture: string, findingId: string, text: string, evidence?: string[]): void {
    if (!this.report) this.initReport('')
    this.addSection({
      type: 'finding',
      status: 'draft',
      title: text.slice(0, 80),
      content: text,
      author: posture,
      references: evidence,
      threadId: findingId,
    })
  }

  autoDraftFromChallenge(posture: string, challengeId: string, text: string, targetFindingId: string): void {
    if (!this.report) this.initReport('')
    this.addSection({
      type: 'concern',
      status: 'draft',
      title: text.slice(0, 80),
      content: text,
      author: posture,
      threadId: targetFindingId,
      challenges: targetFindingId,
    })
  }

  autoDraftFromConcession(posture: string, concessionId: string, text: string, challengeId: string): void {
    if (!this.report) this.initReport('')
    this.addSection({
      type: 'decision',
      status: 'draft',
      title: text.slice(0, 80),
      content: text,
      author: posture,
      threadId: challengeId,
      respondsTo: challengeId,
    })
  }

  reviseSection(sectionId: string, content: string, _reason?: string): ReportSection | null {
    if (!this.report) return null
    const original = this.report.sections.find(s => s.id === sectionId)
    if (!original) return null

    original.superseded = true
    original.status = 'superseded'
    original.updatedAt = Date.now()

    return this.addSection({
      type: original.type,
      title: original.title,
      content,
      author: original.author,
      confidence: original.confidence,
      references: original.references,
      threadId: original.threadId,
    })
  }

  promoteSection(sectionId: string): boolean {
    if (!this.report) return false
    const section = this.report.sections.find(s => s.id === sectionId && s.status === 'draft')
    if (!section) return false
    section.status = 'active'
    section.updatedAt = Date.now()
    this.report.updatedAt = Date.now()
    return true
  }

  discardSection(sectionId: string): boolean {
    if (!this.report) return false
    const idx = this.report.sections.findIndex(s => s.id === sectionId && s.status === 'draft')
    if (idx === -1) return false
    this.report.sections.splice(idx, 1)

    // Cascading cleanup
    for (const s of this.report.sections) {
      if (s.respondsTo === sectionId) s.respondsTo = undefined
      if (s.challenges === sectionId) s.challenges = undefined
      if (s.supports === sectionId) s.supports = undefined
      if (s.supersedes === sectionId) s.supersedes = undefined
    }

    this.report.updatedAt = Date.now()
    return true
  }

  getReport(): Report | null {
    return this.report
  }

  getView(opts?: {
    filterType?: string
    filterAuthor?: string
    filterStatus?: string
    since?: number
  }): ReportSection[] {
    if (!this.report) return []
    let sections = this.report.sections
    if (opts?.filterType) sections = sections.filter(s => s.type === opts.filterType)
    if (opts?.filterAuthor) sections = sections.filter(s => s.author === opts.filterAuthor)
    if (opts?.filterStatus) sections = sections.filter(s => s.status === opts.filterStatus)
    if (opts?.since) sections = sections.filter(s => s.updatedAt > opts.since!)
    return sections
  }

  getMetrics(): ReportQualityMetrics {
    if (!this.report) {
      return {
        totalSections: 0, activeSections: 0, draftSections: 0,
        byType: {}, byAuthor: {}, avgConfidence: 0,
        threadCount: 0, unresolvedConcerns: 0, coverageScore: 0,
      }
    }

    const sections = this.report.sections
    const active = sections.filter(s => s.status === 'active')
    const drafts = sections.filter(s => s.status === 'draft')

    const byType: Partial<Record<string, number>> = {}
    for (const s of active) {
      byType[s.type] = (byType[s.type] || 0) + 1
    }

    const byAuthor: Record<string, number> = {}
    for (const s of active) {
      byAuthor[s.author] = (byAuthor[s.author] || 0) + 1
    }

    const withConf = active.filter(s => s.confidence != null)
    const avgConfidence = withConf.length > 0
      ? withConf.reduce((sum, s) => sum + (s.confidence ?? 0), 0) / withConf.length
      : 0

    const threads = new Set(active.filter(s => s.threadId).map(s => s.threadId))
    const decisionThreads = new Set(
      active.filter(s => s.type === 'decision').map(s => s.threadId).filter(Boolean)
    )
    const unresolvedConcerns = active.filter(
      s => s.type === 'concern' && (!s.threadId || !decisionThreads.has(s.threadId))
    ).length

    const typesUsed = new Set(Object.keys(byType))
    const idealTypes = ['finding', 'concern', 'recommendation']
    const coverageScore = idealTypes.filter(t => typesUsed.has(t)).length / idealTypes.length

    return {
      totalSections: sections.length,
      activeSections: active.length,
      draftSections: drafts.length,
      byType,
      byAuthor,
      avgConfidence: Math.round(avgConfidence * 100) / 100,
      threadCount: threads.size,
      unresolvedConcerns,
      coverageScore: Math.round(coverageScore * 100) / 100,
    }
  }

  formatForContext(): string {
    if (!this.report || this.report.sections.length === 0) return ''

    const active = this.report.sections.filter(s => s.status === 'active')
    const drafts = this.report.sections.filter(s => s.status === 'draft')

    if (active.length === 0 && drafts.length === 0) return ''

    const parts: string[] = ['## Incremental Report']

    const byType = new Map<string, typeof active>()
    for (const s of active) {
      if (!byType.has(s.type)) byType.set(s.type, [])
      byType.get(s.type)!.push(s)
    }

    for (const [type, sections] of byType) {
      parts.push(`\n### ${type.charAt(0).toUpperCase() + type.slice(1)}s`)
      for (const s of sections) {
        const conf = s.confidence != null ? ` (confidence: ${s.confidence})` : ''
        const refs = s.references?.length ? `\n  References: ${s.references.join(', ')}` : ''
        const thread = s.threadId ? ` [thread: ${s.threadId}]` : ''
        parts.push(`- **${s.title}** — by ${s.author}${conf}${thread}\n  ${s.content}${refs}`)
      }
    }

    if (drafts.length > 0) {
      parts.push(`\n### Drafts (${drafts.length} pending review)`)
      for (const s of drafts) {
        parts.push(`- [DRAFT] **${s.title}** — ${s.type} by ${s.author}`)
      }
    }

    return parts.join('\n')
  }
}
