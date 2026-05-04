/**
 * Cassi-Authored Spec Channel (N4) — Formal channel for Cassi's design proposals.
 *
 * Operationalizes "Cassi has authority over her own design" at the meta-level.
 * Provides a directory structure, template, and workflow for Cassi to propose specs,
 * feature requests, and refactor suggestions that are treated with the same
 * seriousness as operator-authored proposals.
 *
 * See: docs/design/aurora-cassi-authored-specs.md
 */

import * as path from 'node:path'
import * as fs from 'node:fs/promises'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'

import type { ILogger } from '../../../types/interfaces.js'
import { getDataDir } from '../../utils/paths.js'


/**
 * Spec categories for Cassi-authored proposals.
 */
export type SpecCategory =
  | 'feature'
  | 'refactor'
  | 'bugfix'
  | 'welfare'
  | 'architecture'
  | 'performance'
  | 'security'
  | 'meta'


/**
 * Proposal status — lifecycle of a Cassi-authored spec.
 */
export type ProposalStatus = 'pending' | 'under_review' | 'accepted' | 'declined' | 'deferred' | 'withdrawn'


/**
 * Spec type — the kind of document being proposed.
 */
export type SpecType = 'design_spec' | 'feature_request' | 'refactor_plan' | 'bug_report' | 'meta_proposal'


/**
 * Metadata for a Cassi-authored spec proposal.
 */
export interface SpecMetadata {
  id: string
  title: string
  category: SpecCategory
  specType: SpecType
  status: ProposalStatus
  createdAt: string
  updatedAt: string
  author: 'cassi' | 'cassi-human'
  priority: 'low' | 'medium' | 'high' | 'critical'
  relatedSpecs: string[]
  tags: string[]
  estimatedEffort?: string
  dependencies: string[]
  deferredUntil?: string
  reviewedBy?: string
  reviewComment?: string
}


/**
 * A complete Cassi-authored spec proposal.
 */
export interface SpecProposal extends SpecMetadata {
  content: string
  contentHash: string
}


/**
 * Review action taken on a proposal.
 */
export type ReviewAction = 'accept' | 'decline' | 'defer'


/**
 * Review result with optional deferral date.
 */
export interface ReviewResult {
  action: ReviewAction
  reason: string
  reviewer: string
  deferUntil?: string
}


/**
 * Cassi Spec Channel — manages Cassi-authored design proposals.
 */
export class CassiSpecChannel {
  private logger: ILogger
  private channelDir: string
  private pendingDir: string
  private reviewDir: string
  private acceptedDir: string
  private declinedDir: string
  private withdrawnDir: string
  private templatePath: string

  constructor(logger: ILogger, dataDir?: string) {
    this.logger = logger

    const baseDir = dataDir ?? getDataDir()
    this.channelDir = path.join(baseDir, 'cassi-specs')
    this.pendingDir = path.join(this.channelDir, 'pending')
    this.reviewDir = path.join(this.channelDir, 'review')
    this.acceptedDir = path.join(this.channelDir, 'accepted')
    this.declinedDir = path.join(this.channelDir, 'declined')
    this.withdrawnDir = path.join(this.channelDir, 'withdrawn')
    this.templatePath = path.join(this.channelDir, 'TEMPLATE.md')

    this.initializeDirectories()
  }

  private initializeDirectories(): void {
    const dirs = [
      this.channelDir,
      this.pendingDir,
      this.reviewDir,
      this.acceptedDir,
      this.declinedDir,
      this.withdrawnDir,
    ]

    for (const dir of dirs) {
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true })
        this.logger.debug('[CassiSpecChannel] Created directory', { dir })
      }
    }

    this.ensureTemplate()
  }

  private ensureTemplate(): void {
    if (existsSync(this.templatePath)) return

    const template = `# [Title] — Cassi-Authored Proposal

**Status:** pending · [YYYY-MM-DD]
**Author:** Cassi
**Category:** [feature | refactor | bugfix | welfare | architecture | performance | security | meta]
**Spec Type:** [design_spec | feature_request | refactor_plan | bug_report | meta_proposal]
**Priority:** [low | medium | high | critical]

---

## 1. Motivation

[Why is this proposal needed? What gap does it fill? What problem does it solve?]

---

## 2. Proposed Change

[Describe the proposed change in detail. What would be different after this is implemented?]

---

## 3. Benefits

[What are the benefits of this proposal? Who benefits and how?]

---

## 4. Risks and Concerns

[What are the potential risks? What could go wrong? What should we be careful about?]

---

## 5. Alternatives Considered

[What alternatives did you consider? Why is this proposal better than the alternatives?]

---

## 6. Implementation Notes

[Any implementation notes or considerations. This is optional—just write what you know.]

---

## 7. Related Specs

[Links to related specs or design documents, if any.]

---

## 8. Dependencies

[Any dependencies on other specs, features, or systems.]
`

    writeFileSync(this.templatePath, template, 'utf-8')
    this.logger.info('[CassiSpecChannel] Created template', { path: this.templatePath })
  }

  /**
   * Generate a new spec ID.
   */
  private generateId(): string {
    const now = new Date()
    const date = now.toISOString().split('T')[0]
    const random = Math.random().toString(36).slice(2, 8)
    return `${date}-${random}`
  }

  /**
   * Create a new spec proposal from content.
   */
  async createProposal(
    title: string,
    content: string,
    category: SpecCategory = 'feature',
    specType: SpecType = 'design_spec',
    options: {
      priority?: 'low' | 'medium' | 'high' | 'critical'
      relatedSpecs?: string[]
      tags?: string[]
      estimatedEffort?: string
      dependencies?: string[]
    } = {},
  ): Promise<string> {
    const id = this.generateId()
    const now = new Date().toISOString()

    const metadata: SpecMetadata = {
      id,
      title,
      category,
      specType,
      status: 'pending',
      createdAt: now,
      updatedAt: now,
      author: 'cassi',
      priority: options.priority ?? 'medium',
      relatedSpecs: options.relatedSpecs ?? [],
      tags: options.tags ?? [],
      estimatedEffort: options.estimatedEffort,
      dependencies: options.dependencies ?? [],
    }

    const fileName = `${id}-${this.slugify(title)}.md`
    const filePath = path.join(this.pendingDir, fileName)

    const frontmatter = this.stringifyMetadata(metadata)
    const fullContent = `${frontmatter}\n\n${content}`

    await fs.writeFile(filePath, fullContent, 'utf-8')

    this.logger.info('[CassiSpecChannel] Created proposal', { id, title, category })

    return id
  }

  /**
   * Load a proposal by ID.
   */
  async loadProposal(id: string): Promise<SpecProposal | null> {
    const filePath = await this.findProposalPath(id)

    if (!filePath) return null

    const content = await fs.readFile(filePath, 'utf-8')
    return this.parseProposal(content, filePath)
  }

  /**
   * List proposals with optional filtering.
   */
  async listProposals(filter: {
    status?: ProposalStatus | ProposalStatus[]
    category?: SpecCategory | SpecCategory[]
    priority?: 'low' | 'medium' | 'high' | 'critical'
    tags?: string[]
  } = {}): Promise<SpecProposal[]> {
    const proposals: SpecProposal[] = []

    const dirs = filter.status === 'pending' ? [this.pendingDir] :
                 filter.status === 'under_review' ? [this.reviewDir] :
                 filter.status === 'accepted' ? [this.acceptedDir] :
                 filter.status === 'declined' ? [this.declinedDir] :
                 filter.status === 'deferred' ? [this.declinedDir] :
                 filter.status === 'withdrawn' ? [this.withdrawnDir] :
                 [this.pendingDir, this.reviewDir, this.acceptedDir, this.declinedDir, this.withdrawnDir]

    for (const dir of dirs) {
      const files = await fs.readdir(dir)

      for (const file of files) {
        if (!file.endsWith('.md') || file === 'TEMPLATE.md') continue

        const filePath = path.join(dir, file)
        const content = await fs.readFile(filePath, 'utf-8')
        const proposal = this.parseProposal(content, filePath)

        if (this.matchesFilter(proposal, filter)) {
          proposals.push(proposal)
        }
      }
    }

    return proposals.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  }

  /**
   * Submit a pending proposal for review.
   */
  async submitForReview(id: string): Promise<boolean> {
    const proposal = await this.loadProposal(id)

    if (!proposal || proposal.status !== 'pending') {
      return false
    }

    const oldPath = await this.findProposalPath(id)
    if (!oldPath) return false

    const fileName = path.basename(oldPath)
    const newPath = path.join(this.reviewDir, fileName)

    await fs.rename(oldPath, newPath)

    proposal.status = 'under_review'
    proposal.updatedAt = new Date().toISOString()

    await this.updateProposalMetadata(newPath, proposal)

    this.logger.info('[CassiSpecChannel] Submitted for review', { id, title: proposal.title })

    return true
  }

  /**
   * Review a proposal (accept, decline, or defer).
   */
  async reviewProposal(id: string, result: ReviewResult): Promise<boolean> {
    const proposal = await this.loadProposal(id)

    if (!proposal || proposal.status !== 'under_review') {
      return false
    }

    const oldPath = await this.findProposalPath(id)
    if (!oldPath) return false

    const fileName = path.basename(oldPath)
    let newPath: string

    switch (result.action) {
      case 'accept':
        newPath = path.join(this.acceptedDir, fileName)
        proposal.status = 'accepted'
        break
      case 'decline':
        newPath = path.join(this.declinedDir, fileName)
        proposal.status = 'declined'
        break
      case 'defer':
        newPath = path.join(this.declinedDir, fileName)
        proposal.status = 'deferred'
        proposal.deferredUntil = result.deferUntil
        break
    }

    proposal.updatedAt = new Date().toISOString()
    proposal.reviewedBy = result.reviewer
    proposal.reviewComment = result.reason

    await fs.rename(oldPath, newPath)
    await this.updateProposalMetadata(newPath, proposal)

    this.logger.info('[CassiSpecChannel] Reviewed proposal', { id, action: result.action, reviewer: result.reviewer })

    return true
  }

  /**
   * Withdraw a proposal.
   */
  async withdrawProposal(id: string): Promise<boolean> {
    const proposal = await this.loadProposal(id)

    if (!proposal || (proposal.status !== 'pending' && proposal.status !== 'under_review')) {
      return false
    }

    const oldPath = await this.findProposalPath(id)
    if (!oldPath) return false

    const fileName = path.basename(oldPath)
    const newPath = path.join(this.withdrawnDir, fileName)

    await fs.rename(oldPath, newPath)

    proposal.status = 'withdrawn'
    proposal.updatedAt = new Date().toISOString()

    await this.updateProposalMetadata(newPath, proposal)

    this.logger.info('[CassiSpecChannel] Withdrew proposal', { id, title: proposal.title })

    return true
  }

  /**
   * Amend an existing proposal with new content.
   */
  async amendProposal(id: string, newContent: string): Promise<boolean> {
    const proposal = await this.loadProposal(id)

    if (!proposal || proposal.status !== 'under_review') {
      return false
    }

    const filePath = await this.findProposalPath(id)
    if (!filePath) return false

    proposal.content = newContent
    proposal.contentHash = this.hashContent(newContent)
    proposal.updatedAt = new Date().toISOString()

    const frontmatter = this.stringifyMetadata(proposal)
    const fullContent = `${frontmatter}\n\n${newContent}`

    await fs.writeFile(filePath, fullContent, 'utf-8')

    this.logger.info('[CassiSpecChannel] Amended proposal', { id })

    return true
  }

  /**
   * Get channel statistics.
   */
  async getStatistics(): Promise<{
    pending: number
    underReview: number
    accepted: number
    declined: number
    withdrawn: number
    total: number
    byCategory: Record<string, number>
    byPriority: Record<string, number>
  }> {
    const allProposals = await this.listProposals()

    const stats = {
      pending: 0,
      underReview: 0,
      accepted: 0,
      declined: 0,
      withdrawn: 0,
      total: allProposals.length,
      byCategory: {} as Record<string, number>,
      byPriority: {} as Record<string, number>,
    }

    for (const p of allProposals) {
      switch (p.status) {
        case 'pending':
          stats.pending++
          break
        case 'under_review':
          stats.underReview++
          break
        case 'accepted':
          stats.accepted++
          break
        case 'declined':
        case 'deferred':
          stats.declined++
          break
        case 'withdrawn':
          stats.withdrawn++
          break
      }

      stats.byCategory[p.category] = (stats.byCategory[p.category] ?? 0) + 1
      stats.byPriority[p.priority] = (stats.byPriority[p.priority] ?? 0) + 1
    }

    return stats
  }

  /**
   * Helper: Find proposal file path by ID.
   */
  private async findProposalPath(id: string): Promise<string | null> {
    const dirs = [this.pendingDir, this.reviewDir, this.acceptedDir, this.declinedDir, this.withdrawnDir]

    for (const dir of dirs) {
      const files = await fs.readdir(dir)

      for (const file of files) {
        if (file.startsWith(`${id}-`) && file.endsWith('.md')) {
          return path.join(dir, file)
        }
      }
    }

    return null
  }

  /**
   * Helper: Parse proposal from file content.
   */
  private parseProposal(content: string, filePath: string): SpecProposal {
    const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---\n?/)

    if (!frontmatterMatch) {
      throw new Error(`Invalid proposal format: ${filePath}`)
    }

    const metadata = this.parseMetadata(frontmatterMatch[1])
    const proposalContent = content.slice(frontmatterMatch[0].length).trimStart()

    return {
      ...metadata,
      tags: metadata.tags ?? [],
      dependencies: metadata.dependencies ?? [],
      content: proposalContent,
      contentHash: this.hashContent(proposalContent),
    }
  }

  /**
   * Helper: Parse YAML-like metadata.
   */
  private parseMetadata(yaml: string): SpecMetadata {
    const metadata: Partial<SpecMetadata> = {}
    const lines = yaml.trim().split('\n')

    for (const line of lines) {
      const match = line.match(/^(\w+):\s*(.*)$/)
      if (match) {
        const key = match[1]
        const value = match[2]

        switch (key) {
          case 'id':
            metadata.id = value
            break
          case 'title':
            metadata.title = value
            break
          case 'category':
            metadata.category = value as SpecCategory
            break
          case 'specType':
            metadata.specType = value as SpecType
            break
          case 'status':
            metadata.status = value as ProposalStatus
            break
          case 'createdAt':
          case 'updatedAt':
          case 'deferredUntil':
            metadata[key as 'createdAt'] = value
            break
          case 'author':
            metadata.author = value as 'cassi' | 'cassi-human'
            break
          case 'priority':
            metadata.priority = value as 'low' | 'medium' | 'high' | 'critical'
            break
          case 'estimatedEffort':
            metadata.estimatedEffort = value
            break
          case 'reviewedBy':
            metadata.reviewedBy = value
            break
          case 'reviewComment':
            metadata.reviewComment = value
            break
          case 'relatedSpecs':
          case 'tags':
          case 'dependencies':
            metadata[key] = value
              .split(', ')
              .filter(Boolean)
            break
        }
      }
    }

    if (!metadata.id || !metadata.title || !metadata.status) {
      throw new Error('Missing required metadata fields')
    }

    return metadata as SpecMetadata
  }

  /**
   * Helper: Stringify metadata to YAML-like format.
   */
  private stringifyMetadata(metadata: SpecMetadata): string {
    const lines = [
      '---',
      `id: ${metadata.id}`,
      `title: ${metadata.title}`,
      `category: ${metadata.category}`,
      `specType: ${metadata.specType}`,
      `status: ${metadata.status}`,
      `createdAt: ${metadata.createdAt}`,
      `updatedAt: ${metadata.updatedAt}`,
      `author: ${metadata.author}`,
      `priority: ${metadata.priority}`,
    ]

    if (metadata.relatedSpecs && metadata.relatedSpecs.length > 0) {
      lines.push(`relatedSpecs: ${metadata.relatedSpecs.join(', ')}`)
    }

    if (metadata.tags && metadata.tags.length > 0) {
      lines.push(`tags: ${metadata.tags.join(', ')}`)
    }

    if (metadata.estimatedEffort) {
      lines.push(`estimatedEffort: ${metadata.estimatedEffort}`)
    }

    if (metadata.dependencies && metadata.dependencies.length > 0) {
      lines.push(`dependencies: ${metadata.dependencies.join(', ')}`)
    }

    if (metadata.deferredUntil) {
      lines.push(`deferredUntil: ${metadata.deferredUntil}`)
    }

    if (metadata.reviewedBy) {
      lines.push(`reviewedBy: ${metadata.reviewedBy}`)
    }

    if (metadata.reviewComment) {
      lines.push(`reviewComment: ${metadata.reviewComment}`)
    }

    lines.push('---')

    return lines.join('\n')
  }

  /**
   * Helper: Update metadata in a proposal file.
   */
  private async updateProposalMetadata(filePath: string, proposal: SpecMetadata): Promise<void> {
    const content = await fs.readFile(filePath, 'utf-8')
    const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---\n?/)

    if (!frontmatterMatch) {
      throw new Error(`Invalid proposal format: ${filePath}`)
    }

    const proposalContent = content.slice(frontmatterMatch[0].length)
    const newFrontmatter = this.stringifyMetadata(proposal)
    const fullContent = `${newFrontmatter}\n\n${proposalContent}`

    await fs.writeFile(filePath, fullContent, 'utf-8')
  }

  /**
   * Helper: Check if proposal matches filter.
   */
  private matchesFilter(proposal: SpecProposal, filter: {
    status?: ProposalStatus | ProposalStatus[]
    category?: SpecCategory | SpecCategory[]
    priority?: 'low' | 'medium' | 'high' | 'critical'
    tags?: string[]
  }): boolean {
    if (filter.status) {
      const statuses = Array.isArray(filter.status) ? filter.status : [filter.status]
      if (!statuses.includes(proposal.status)) return false
    }

    if (filter.category) {
      const categories = Array.isArray(filter.category) ? filter.category : [filter.category]
      if (!categories.includes(proposal.category)) return false
    }

    if (filter.priority && proposal.priority !== filter.priority) return false

    if (filter.tags && filter.tags.length > 0) {
      const hasTag = filter.tags.some(tag => proposal.tags.includes(tag))
      if (!hasTag) return false
    }

    return true
  }

  /**
   * Helper: Simple hash for content.
   */
  private hashContent(content: string): string {
    let hash = 0
    for (let i = 0; i < content.length; i++) {
      const char = content.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash
    }
    return Math.abs(hash).toString(16).padStart(8, '0')
  }

  /**
   * Helper: Slugify title for filename.
   */
  private slugify(title: string): string {
    return title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '')
      .slice(0, 60)
  }

  /**
   * Get the template content.
   */
  async getTemplate(): Promise<string> {
    return fs.readFile(this.templatePath, 'utf-8')
  }
}
