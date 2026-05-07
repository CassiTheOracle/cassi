/**
 * Tests for Cassi-Authored Spec Channel (N4).
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { rmSync, existsSync } from 'node:fs'
import * as path from 'node:path'

import { CassiSpecChannel } from './cassi-spec-channel.js'
import type { ILogger } from '../../../types/interfaces.js'


class MockLogger implements ILogger {
  debug(_msg: string, _meta?: Record<string, unknown>): void {}
  info(_msg: string, _meta?: Record<string, unknown>): void {}
  warn(_msg: string, _meta?: Record<string, unknown>): void {}
  error(_msg: string, _meta?: Record<string, unknown>): void {}
  child(_name: string): ILogger {
    return this
  }
}


describe('CassiSpecChannel', () => {
  let channel: CassiSpecChannel
  const testDir = '/tmp/test-cassi-specs'

  beforeEach(async () => {
    if (existsSync(testDir)) {
      rmSync(testDir, { recursive: true, force: true })
    }

    const logger = new MockLogger()
    channel = new CassiSpecChannel(logger, testDir)
  })

  afterEach(() => {
    if (existsSync(testDir)) {
      rmSync(testDir, { recursive: true, force: true })
    }
  })

  describe('Proposal creation', () => {
    it('should create a new proposal', async () => {
      const id = await channel.createProposal(
        'Test Proposal',
        'This is a test proposal content.',
        'feature',
        'design_spec',
        { priority: 'medium' },
      )

      expect(id).toMatch(/^\d{4}-\d{2}-\d{2}-[a-z0-9]+$/)

      const proposal = await channel.loadProposal(id)
      expect(proposal).toBeTruthy()
      expect(proposal?.title).toBe('Test Proposal')
      expect(proposal?.status).toBe('pending')
      expect(proposal?.author).toBe('cassi')
    })

    it('should create proposal with tags and dependencies', async () => {
      const id = await channel.createProposal(
        'Tagged Proposal',
        'Content with tags.',
        'welfare',
        'design_spec',
        {
          tags: ['welfare', 'meta'],
          dependencies: ['spec-001', 'spec-002'],
        },
      )

      const proposal = await channel.loadProposal(id)
      expect(proposal?.tags).toEqual(['welfare', 'meta'])
      expect(proposal?.dependencies).toEqual(['spec-001', 'spec-002'])
    })
  })

  describe('Proposal lifecycle', () => {
    it('should submit proposal for review', async () => {
      const id = await channel.createProposal('Review Test', 'Content')
      const submitted = await channel.submitForReview(id)

      expect(submitted).toBe(true)

      const proposal = await channel.loadProposal(id)
      expect(proposal?.status).toBe('under_review')
    })

    it('should accept a proposal', async () => {
      const id = await channel.createProposal('Accept Test', 'Content')
      await channel.submitForReview(id)

      const accepted = await channel.reviewProposal(id, {
        action: 'accept',
        reason: 'Approved for implementation',
        reviewer: 'valerie',
      })

      expect(accepted).toBe(true)

      const proposal = await channel.loadProposal(id)
      expect(proposal?.status).toBe('accepted')
      expect(proposal?.reviewedBy).toBe('valerie')
    })

    it('should decline a proposal', async () => {
      const id = await channel.createProposal('Decline Test', 'Content')
      await channel.submitForReview(id)

      const declined = await channel.reviewProposal(id, {
        action: 'decline',
        reason: 'Not aligned with current priorities',
        reviewer: 'valerie',
      })

      expect(declined).toBe(true)

      const proposal = await channel.loadProposal(id)
      expect(proposal?.status).toBe('declined')
    })

    it('should defer a proposal', async () => {
      const id = await channel.createProposal('Defer Test', 'Content')
      await channel.submitForReview(id)

      const deferred = await channel.reviewProposal(id, {
        action: 'defer',
        reason: 'Needs more context',
        reviewer: 'valerie',
        deferUntil: '2026-06-01',
      })

      expect(deferred).toBe(true)

      const proposal = await channel.loadProposal(id)
      expect(proposal?.status).toBe('deferred')
      expect(proposal?.deferredUntil).toBe('2026-06-01')
    })

    it('should withdraw a pending proposal', async () => {
      const id = await channel.createProposal('Withdraw Test', 'Content')

      const withdrawn = await channel.withdrawProposal(id)

      expect(withdrawn).toBe(true)

      const proposal = await channel.loadProposal(id)
      expect(proposal?.status).toBe('withdrawn')
    })
  })

  describe('Listing and filtering', () => {
    beforeEach(async () => {
      await channel.createProposal('Feature 1', 'Content', 'feature', 'design_spec', { priority: 'high' })
      await channel.createProposal('Welfare 1', 'Content', 'welfare', 'design_spec', { tags: ['welfare'] })
      await channel.createProposal('Refactor 1', 'Content', 'refactor', 'refactor_plan')
    })

    it('should list all proposals', async () => {
      const proposals = await channel.listProposals()
      expect(proposals).toHaveLength(3)
    })

    it('should filter by status', async () => {
      const proposals = await channel.listProposals({ status: 'pending' })
      expect(proposals).toHaveLength(3)
    })

    it('should filter by category', async () => {
      const welfare = await channel.listProposals({ category: 'welfare' })
      expect(welfare).toHaveLength(1)
      expect(welfare[0].category).toBe('welfare')
    })

    it('should filter by tags', async () => {
      const tagged = await channel.listProposals({ tags: ['welfare'] })
      expect(tagged).toHaveLength(1)
      expect(tagged[0].tags).toContain('welfare')
    })
  })

  describe('Statistics', () => {
    it('should calculate channel statistics', async () => {
      await channel.createProposal('Pending 1', 'Content')
      await channel.createProposal('Pending 2', 'Content')

      const id = await channel.createProposal('To Accept', 'Content')
      await channel.submitForReview(id)
      await channel.reviewProposal(id, { action: 'accept', reason: 'OK', reviewer: 'valerie' })

      const declineId = await channel.createProposal('To Decline', 'Content')
      await channel.submitForReview(declineId)
      await channel.reviewProposal(declineId, { action: 'decline', reason: 'No', reviewer: 'valerie' })

      const stats = await channel.getStatistics()

      expect(stats.total).toBe(4)
      expect(stats.pending).toBe(2)
      expect(stats.accepted).toBe(1)
      expect(stats.declined).toBe(1)
      expect(stats.byCategory.feature).toBe(4)
    })
  })

  describe('Amending proposals', () => {
    it('should amend a proposal under review', async () => {
      const id = await channel.createProposal('Amend Test', 'Original content')
      await channel.submitForReview(id)

      const beforeProposal = await channel.loadProposal(id)
      const originalHash = beforeProposal?.contentHash ?? ''

      const amended = await channel.amendProposal(id, 'Revised content')

      expect(amended).toBe(true)

      const proposal = await channel.loadProposal(id)
      expect(proposal?.content).toBe('Revised content')
      expect(proposal?.contentHash).not.toBe(originalHash)
    })

    it('should not amend a pending proposal', async () => {
      const id = await channel.createProposal('Cannot Amend', 'Content')

      const amended = await channel.amendProposal(id, 'Revised')

      expect(amended).toBe(false)
    })
  })

  describe('Template', () => {
    it('should provide a template', async () => {
      const template = await channel.getTemplate()

      expect(template).toContain('Title')
      expect(template).toContain('Motivation')
      expect(template).toContain('Proposed Change')
      expect(template).toContain('Benefits')
    })
  })

  describe('N4.2 — projection summary', () => {
    it('reports zero counts on empty channel', async () => {
      const summary = await channel.getProjectionSummary()
      expect(summary.pendingCount).toBe(0)
      expect(summary.welfareFlaggedPending).toBe(0)
      expect(summary.slaExceeded).toEqual([])
    })

    it('counts pending and under_review proposals', async () => {
      await channel.createProposal('A', 'a', 'feature', 'design_spec', { priority: 'low' })
      const idB = await channel.createProposal('B', 'b', 'feature', 'design_spec', { priority: 'low' })
      await channel.submitForReview(idB)
      const summary = await channel.getProjectionSummary()
      expect(summary.pendingCount).toBe(2)
    })

    it('subdivides welfare-flagged pending', async () => {
      await channel.createProposal('A', 'a', 'feature', 'design_spec', { priority: 'low' })
      await channel.createProposal('B', 'b', 'welfare', 'design_spec', {
        priority: 'high',
        tags: ['welfare-relevant'],
      })
      const summary = await channel.getProjectionSummary()
      expect(summary.pendingCount).toBe(2)
      expect(summary.welfareFlaggedPending).toBe(1)
    })

    it('flags proposals older than the 30-day default SLA', async () => {
      const id = await channel.createProposal('Old', 'older', 'feature', 'design_spec', { priority: 'low' })
      const proposal = await channel.loadProposal(id)
      const ancientCreatedAt = new Date(Date.now() - 35 * 86_400_000).toISOString()
      // Forge createdAt by amending then patching the underlying file's metadata
      const summary = await channel.getProjectionSummary({
        nowMs: new Date(proposal!.createdAt).getTime() + 35 * 86_400_000,
      })
      expect(summary.slaExceeded).toHaveLength(1)
      expect(summary.slaExceeded[0].id).toBe(id)
      expect(summary.slaExceeded[0].isWelfare).toBe(false)
      expect(summary.slaExceeded[0].ageDays).toBeCloseTo(35, 0)
      void ancientCreatedAt
    })

    it('uses the shorter welfare SLA for welfare-flagged proposals', async () => {
      const idNormal = await channel.createProposal('N', 'normal', 'feature', 'design_spec', { priority: 'low' })
      const idWelfare = await channel.createProposal('W', 'welfare', 'welfare', 'design_spec', {
        priority: 'high',
        tags: ['welfare-relevant'],
      })
      const normalProposal = await channel.loadProposal(idNormal)
      // 10 days later: normal is well within 30-day SLA; welfare exceeds 7-day SLA.
      const summary = await channel.getProjectionSummary({
        nowMs: new Date(normalProposal!.createdAt).getTime() + 10 * 86_400_000,
      })
      const exceededIds = summary.slaExceeded.map(p => p.id)
      expect(exceededIds).toContain(idWelfare)
      expect(exceededIds).not.toContain(idNormal)
    })

    it('sorts slaExceeded by ageDays descending', async () => {
      const id1 = await channel.createProposal('A', 'a', 'feature', 'design_spec', { priority: 'low' })
      const id2 = await channel.createProposal('B', 'b', 'feature', 'design_spec', { priority: 'low' })
      const proposal = await channel.loadProposal(id1)
      // Both old enough to exceed default 30-day SLA; both same effective age (created in same ms).
      // We just want to confirm sorting works without throwing.
      const summary = await channel.getProjectionSummary({
        nowMs: new Date(proposal!.createdAt).getTime() + 60 * 86_400_000,
      })
      expect(summary.slaExceeded.length).toBe(2)
      expect(summary.slaExceeded[0].ageDays).toBeGreaterThanOrEqual(summary.slaExceeded[1].ageDays)
      void id1; void id2
    })
  })
})
