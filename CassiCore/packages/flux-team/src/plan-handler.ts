/**
 * PlanHandler — Mediates plan tool calls from Lumen agents to the Blackboard.
 *
 * Wraps Blackboard plan operations with access control:
 *   - All postures: submit steps, view plan
 *   - Executive only: approve, reject, update, finalize steps
 *
 * Plan tools are meta-tools handled inline by LumenPostureRunner (same pattern
 * as dialectic meta-tools). They operate on the Blackboard's plan slot and
 * return JSON-formatted results.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { Plan, PlanStep } from '../../../types/flux-team.js'
import type { Blackboard } from './blackboard.js'

/** Posture names that can interact with the plan */
type PlanPosture = 'yang' | 'yin' | 'executive' | 'mentor'

/** Set of tool names that are plan meta-tools */
const PLAN_META_TOOL_NAMES = new Set([
  'plan_submit_step',
  'plan_view',
  'plan_approve_step',
  'plan_reject_step',
  'plan_update_step',
  'plan_finalize',
  'plan_claim_step',
  'plan_release_step',
  'plan_report_progress',
])

/** Tools restricted to Executive only */
const EXECUTIVE_ONLY_TOOLS = new Set([
  'plan_approve_step',
  'plan_reject_step',
  'plan_update_step',
  'plan_finalize',
])

/**
 * @deprecated Use Blackboard + handleBlackboardToolCall() from blackboard-tools.ts instead.
 * PlanHandler is kept for backward compatibility with older FluxTeam configurations.
 * Will be removed in a future cleanup pass.
 */
export class PlanHandler {
  private readonly blackboard: Blackboard
  private readonly logger: ILogger

  constructor(blackboard: Blackboard, logger: ILogger) {
    this.blackboard = blackboard
    this.logger = logger.child('plan-handler')
  }


  /**
   * Handle a plan tool call from a Lumen agent.
   *
   * Routes the call to the appropriate method with access control.
   *
   * @param toolName - The plan tool being called
   * @param input - Tool input parameters
   * @param posture - The calling posture (yang, yin, executive)
   * @returns JSON-formatted result string
   */
  handleToolCall(toolName: string, input: Record<string, unknown>, posture: PlanPosture): string {
    // Access control: executive-only tools
    if (EXECUTIVE_ONLY_TOOLS.has(toolName) && posture !== 'executive') {
      return JSON.stringify({
        error: `Tool '${toolName}' is restricted to the Executive posture. You (${posture}) can use plan_submit_step and plan_view.`,
      })
    }

    try {
      switch (toolName) {
        case 'plan_submit_step':
          return this.submitStep(input, posture)
        case 'plan_view':
          return this.viewPlan()
        case 'plan_approve_step':
          return this.approveStep(input)
        case 'plan_reject_step':
          return this.rejectStep(input)
        case 'plan_update_step':
          return this.updateStep(input)
        case 'plan_finalize':
          return this.finalize(input)
        case 'plan_claim_step':
          return this.claimStep(input, posture)
        case 'plan_release_step':
          return this.releaseStep(input, posture)
        case 'plan_report_progress':
          return this.reportProgress(input, posture)
        default:
          return JSON.stringify({ error: `Unknown plan tool: ${toolName}` })
      }
    } catch (err) {
      this.logger.error('Plan tool call failed', {
        toolName,
        posture,
        error: String(err),
      })
      return JSON.stringify({ error: String(err) })
    }
  }


  /**
   * Check if a tool name is a plan meta-tool.
   */
  static isPlanMetaTool(name: string): boolean {
    return PLAN_META_TOOL_NAMES.has(name)
  }

  /**
   * Get the set of plan meta-tool names.
   */
  static get toolNames(): Set<string> {
    return PLAN_META_TOOL_NAMES
  }


  /**
   * Submit a new step to the plan.
   *
   * Available to all postures. Steps start as 'proposed'.
   */
  private submitStep(input: Record<string, unknown>, posture: PlanPosture): string {
    const title = String(input.title ?? '')
    const description = String(input.description ?? '')

    if (!title || !description) {
      return JSON.stringify({ error: 'Both title and description are required.' })
    }

    const order = typeof input.order === 'number' ? input.order : this.getNextOrder()
    const priority = (['high', 'medium', 'low'] as const).includes(input.priority as any)
      ? (input.priority as 'high' | 'medium' | 'low')
      : 'medium'
    const dependencies = Array.isArray(input.dependencies)
      ? input.dependencies.map(String)
      : []
    const tags = Array.isArray(input.tags)
      ? input.tags.map(String)
      : []

    const step = this.blackboard.submitPlanStep({
      title,
      description,
      author: posture,
      order,
      dependencies,
      priority,
      tags,
    })

    this.logger.debug('Step submitted via tool', { stepId: step.id, title, posture })

    return JSON.stringify({
      success: true,
      step: this.formatStep(step),
      message: `Step "${title}" submitted as proposed. The Executive will review it.`,
    })
  }

  /**
   * View the current plan with all steps.
   *
   * Available to all postures.
   */
  private viewPlan(): string {
    const plan = this.blackboard.getPlan()
    if (!plan) {
      return JSON.stringify({
        plan: null,
        message: 'No plan has been initialized yet.',
      })
    }

    return JSON.stringify({
      plan: this.formatPlan(plan),
    })
  }

  /**
   * Approve a proposed step.
   *
   * Executive only. Changes step status from 'proposed' to 'approved'.
   */
  private approveStep(input: Record<string, unknown>): string {
    const stepId = String(input.step_id ?? input.stepId ?? '')
    if (!stepId) {
      return JSON.stringify({ error: 'step_id is required.' })
    }

    const step = this.blackboard.updatePlanStep(stepId, { status: 'approved' })
    if (!step) {
      return JSON.stringify({ error: `Step not found: ${stepId}` })
    }

    this.logger.debug('Step approved', { stepId })
    return JSON.stringify({
      success: true,
      step: this.formatStep(step),
      message: `Step "${step.title}" approved.`,
    })
  }

  /**
   * Reject a proposed step with a reason.
   *
   * Executive only.
   */
  private rejectStep(input: Record<string, unknown>): string {
    const stepId = String(input.step_id ?? input.stepId ?? '')
    const reason = String(input.reason ?? '')

    if (!stepId) {
      return JSON.stringify({ error: 'step_id is required.' })
    }
    if (!reason) {
      return JSON.stringify({ error: 'reason is required when rejecting a step.' })
    }

    const step = this.blackboard.updatePlanStep(stepId, {
      status: 'rejected',
      rejectionReason: reason,
    })
    if (!step) {
      return JSON.stringify({ error: `Step not found: ${stepId}` })
    }

    this.logger.debug('Step rejected', { stepId, reason })
    return JSON.stringify({
      success: true,
      step: this.formatStep(step),
      message: `Step "${step.title}" rejected: ${reason}`,
    })
  }

  /**
   * Update a step's fields.
   *
   * Executive only. Can modify title, description, order, priority,
   * dependencies, tags, and status.
   */
  private updateStep(input: Record<string, unknown>): string {
    const stepId = String(input.step_id ?? input.stepId ?? '')
    if (!stepId) {
      return JSON.stringify({ error: 'step_id is required.' })
    }

    const update: Record<string, unknown> = {}
    if (input.title !== undefined) update.title = String(input.title)
    if (input.description !== undefined) update.description = String(input.description)
    if (input.order !== undefined) update.order = Number(input.order)
    if (input.priority !== undefined) update.priority = String(input.priority)
    if (input.status !== undefined) update.status = String(input.status)
    if (input.dependencies !== undefined) {
      update.dependencies = Array.isArray(input.dependencies)
        ? input.dependencies.map(String)
        : []
    }
    if (input.tags !== undefined) {
      update.tags = Array.isArray(input.tags) ? input.tags.map(String) : []
    }
    if (input.outcome !== undefined) update.outcome = String(input.outcome)

    if (Object.keys(update).length === 0) {
      return JSON.stringify({ error: 'No fields to update. Provide at least one field besides step_id.' })
    }

    const step = this.blackboard.updatePlanStep(stepId, update as any)
    if (!step) {
      return JSON.stringify({ error: `Step not found: ${stepId}` })
    }

    this.logger.debug('Step updated', { stepId, fields: Object.keys(update) })
    return JSON.stringify({
      success: true,
      step: this.formatStep(step),
      message: `Step "${step.title}" updated.`,
    })
  }

  /**
   * Finalize the plan.
   *
   * Executive only. Sets plan status to approved, completed, or abandoned.
   */
  private finalize(input: Record<string, unknown>): string {
    const status = String(input.status ?? 'approved') as 'approved' | 'completed' | 'abandoned'
    const validStatuses = ['approved', 'completed', 'abandoned']
    if (!validStatuses.includes(status)) {
      return JSON.stringify({
        error: `Invalid status: ${status}. Must be one of: ${validStatuses.join(', ')}`,
      })
    }

    const summary = input.summary ? String(input.summary) : undefined

    const plan = this.blackboard.finalizePlan(status, 'executive', summary)
    if (!plan) {
      return JSON.stringify({ error: 'No plan exists to finalize.' })
    }

    this.logger.debug('Plan finalized', { planId: plan.id, status })
    return JSON.stringify({
      success: true,
      plan: this.formatPlan(plan),
      message: `Plan finalized as '${status}'.`,
    })
  }


  /**
   * Get the next step order number (max existing + 1).
   */
  private getNextOrder(): number {
    const plan = this.blackboard.getPlan()
    if (!plan || plan.steps.length === 0) return 1
    return Math.max(...plan.steps.map(s => s.order)) + 1
  }

  /**
   * Format a step for JSON output.
   */
  private formatStep(step: PlanStep): Record<string, unknown> {
    return {
      id: step.id,
      title: step.title,
      description: step.description,
      status: step.status,
      author: step.author,
      order: step.order,
      priority: step.priority,
      dependencies: step.dependencies,
      tags: step.tags,
      outcome: step.outcome,
      rejectionReason: step.rejectionReason,
    }
  }

  /**
   * Format a plan for JSON output.
   */
  private formatPlan(plan: Plan): Record<string, unknown> {
    const sortedSteps = [...plan.steps].sort((a, b) => a.order - b.order)
    return {
      id: plan.id,
      goal: plan.goal,
      status: plan.status,
      summary: plan.summary,
      approvedBy: plan.approvedBy,
      stepCount: plan.steps.length,
      steps: sortedSteps.map(s => this.formatStep(s)),
      statusBreakdown: {
        proposed: plan.steps.filter(s => s.status === 'proposed').length,
        approved: plan.steps.filter(s => s.status === 'approved').length,
        rejected: plan.steps.filter(s => s.status === 'rejected').length,
        in_progress: plan.steps.filter(s => s.status === 'in_progress').length,
        completed: plan.steps.filter(s => s.status === 'completed').length,
        blocked: plan.steps.filter(s => s.status === 'blocked').length,
      },
    }
  }

  // Work-claiming TODO methods (delegate to Blackboard)

  private claimStep(input: Record<string, unknown>, posture: PlanPosture): string {
    const stepId = String(input.step_id ?? input.stepId ?? '')
    if (!stepId) return JSON.stringify({ error: 'step_id is required.' })

    const step = this.blackboard.claimPlanStep(stepId, posture)
    if (!step) return JSON.stringify({ error: `Cannot claim step "${stepId}" — it may not exist, not be approved, or already claimed.` })

    return JSON.stringify({
      success: true,
      step: this.formatStep(step),
      message: `Step "${step.title}" claimed by ${posture}.`,
    })
  }

  private releaseStep(input: Record<string, unknown>, posture: PlanPosture): string {
    const stepId = String(input.step_id ?? input.stepId ?? '')
    if (!stepId) return JSON.stringify({ error: 'step_id is required.' })

    const ok = this.blackboard.releasePlanStep(stepId, posture)
    if (!ok) return JSON.stringify({ error: `Cannot release step "${stepId}" — it may not be in-progress or not assigned to you.` })

    return JSON.stringify({ success: true, message: `Step released and is now available for others.` })
  }

  private reportProgress(input: Record<string, unknown>, posture: PlanPosture): string {
    const stepId = String(input.step_id ?? input.stepId ?? '')
    if (!stepId) return JSON.stringify({ error: 'step_id is required.' })

    const progress = input.progress ? String(input.progress) : undefined
    const step = this.blackboard.reportPlanStepProgress(stepId, posture, progress)
    if (!step) return JSON.stringify({ error: `Cannot report progress on step "${stepId}" — it may not be in-progress or not assigned to you.` })

    return JSON.stringify({
      success: true,
      step: this.formatStep(step),
      message: `Progress reported.${progress ? ` Progress: ${progress}` : ''}`,
    })
  }
}
