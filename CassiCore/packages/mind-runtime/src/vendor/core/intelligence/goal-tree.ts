/**
 * GoalTree — Manages the recursive goal decomposition tree for team sessions.
 *
 * Provides operations for building, traversing, and updating the goal tree:
 * - addChild: create a child goal under a parent (with depth validation)
 * - updateStatus: update a goal's status with upward propagation
 * - getLeaves: find all leaf goals (no children)
 * - getPendingDependencies: find blockers for a goal
 * - isComplete: recursive completion check
 * - getProgressSummary: human-readable progress string
 * - serialize / deserialize: for persistence
 *
 * The tree is stored as a flat Record<string, GoalNode> for O(1) lookups,
 * with parent/child references via IDs.
 */

import { generateReadableId } from '@cassicore/utils'

import type { GoalNode, GoalStatus, GoalResult } from '../../types/team.js'

export class GoalTree {
  private nodes: Record<string, GoalNode> = {}
  private rootId?: string

  constructor(existingNodes?: Record<string, GoalNode>, rootId?: string) {
    if (existingNodes) {
      this.nodes = { ...existingNodes }
      this.rootId = rootId
    }
  }


  /**
   * Create the root goal for the tree.
   * @returns The root GoalNode
   */
  createRoot(title: string, description: string, metadata?: Record<string, unknown>): GoalNode {
    if (this.rootId) {
      throw new Error('GoalTree already has a root node')
    }

    const id = generateReadableId('goal')
    const node: GoalNode = {
      id,
      title,
      description,
      status: 'pending',
      depth: 0,
      children: [],
      dependencies: [],
      priority: 0,
      createdAt: Date.now(),
      metadata,
    }

    this.nodes[id] = node
    this.rootId = id
    return node
  }

  /**
   * Add a child goal under a parent.
   * Validates depth against maxDepth to prevent runaway recursion.
   */
  addChild(
    parentId: string,
    title: string,
    description: string,
    opts: {
      roleHint?: string
      priority?: number
      dependencies?: string[]
      maxDepth?: number
      metadata?: Record<string, unknown>
    } = {},
  ): GoalNode {
    const parent = this.nodes[parentId]
    if (!parent) {
      throw new Error(`Parent goal ${parentId} not found`)
    }

    const childDepth = parent.depth + 1
    const maxDepth = opts.maxDepth ?? 3
    if (childDepth > maxDepth) {
      throw new Error(`Cannot add child: depth ${childDepth} exceeds maxDepth ${maxDepth}`)
    }

    // Validate dependencies exist
    if (opts.dependencies) {
      for (const depId of opts.dependencies) {
        if (!this.nodes[depId]) {
          throw new Error(`Dependency goal ${depId} not found`)
        }
      }
    }

    const id = generateReadableId('goal')
    const node: GoalNode = {
      id,
      parentId,
      title,
      description,
      status: 'pending',
      depth: childDepth,
      children: [],
      dependencies: opts.dependencies ?? [],
      roleHint: opts.roleHint,
      priority: opts.priority ?? 0,
      createdAt: Date.now(),
      metadata: opts.metadata,
    }

    this.nodes[id] = node
    parent.children.push(id)

    return node
  }


  /**
   * Update a goal's status. Propagates upward:
   * - If all siblings are 'completed', parent becomes 'completed'
   * - If any sibling 'failed' and no siblings are 'in_progress', parent becomes 'failed'
   * - If any sibling is 'in_progress', parent stays 'in_progress'
   */
  updateStatus(goalId: string, status: GoalStatus, result?: GoalResult): void {
    const node = this.nodes[goalId]
    if (!node) {
      throw new Error(`Goal ${goalId} not found`)
    }

    const prevStatus = node.status
    node.status = status

    // Update timestamps
    if (status === 'in_progress' && !node.startedAt) {
      node.startedAt = Date.now()
    }
    if (status === 'completed' || status === 'failed' || status === 'cancelled') {
      node.completedAt = Date.now()
    }

    // Attach result
    if (result) {
      node.result = result
    }

    // Propagate upward
    if (node.parentId && prevStatus !== status) {
      this.propagateStatus(node.parentId)
    }
  }

  /**
   * Recursively propagate status changes upward through the tree.
   */
  private propagateStatus(goalId: string): void {
    const node = this.nodes[goalId]
    if (!node || node.children.length === 0) return

    const childStatuses = node.children.map(cid => this.nodes[cid]?.status).filter(Boolean)

    let newStatus: GoalStatus | undefined

    if (childStatuses.every(s => s === 'completed')) {
      // All children completed — parent is completed
      newStatus = 'completed'
    } else if (childStatuses.some(s => s === 'failed') && !childStatuses.some(s => s === 'in_progress')) {
      // Some failed, none in progress — parent failed
      newStatus = 'failed'
    } else if (childStatuses.some(s => s === 'in_progress' || s === 'completed')) {
      // At least one in progress or completed — parent is in progress
      newStatus = 'in_progress'
    } else if (childStatuses.some(s => s === 'blocked')) {
      // Some blocked, none in progress — parent is blocked
      newStatus = 'blocked'
    }

    if (newStatus && newStatus !== node.status) {
      node.status = newStatus
      if (newStatus === 'in_progress' && !node.startedAt) {
        node.startedAt = Date.now()
      }
      if (newStatus === 'completed' || newStatus === 'failed') {
        node.completedAt = Date.now()
        // Aggregate child results into parent result
        if (newStatus === 'completed') {
          node.result = this.aggregateChildResults(goalId)
        }
      }
      // Continue propagating upward
      if (node.parentId) {
        this.propagateStatus(node.parentId)
      }
    }
  }

  /**
   * Aggregate results from all children into a parent result summary.
   */
  private aggregateChildResults(goalId: string): GoalResult {
    const node = this.nodes[goalId]
    const childResults = node.children
      .map(cid => this.nodes[cid])
      .filter(c => c?.result)
      .map(c => c.result!)

    const summary = childResults.map(r => r.summary).filter(Boolean).join('\n- ')
    const totalTokens = childResults.reduce((sum, r) => sum + (r.tokensUsed || 0), 0)
    const totalDuration = childResults.reduce((sum, r) => sum + (r.durationMs || 0), 0)

    return {
      summary: `Completed ${childResults.length} sub-goals:\n- ${summary}`,
      tokensUsed: totalTokens,
      durationMs: totalDuration,
    }
  }


  /** Get a goal by ID. */
  get(goalId: string): GoalNode | undefined {
    return this.nodes[goalId]
  }

  /** Get the root goal. */
  getRoot(): GoalNode | undefined {
    return this.rootId ? this.nodes[this.rootId] : undefined
  }

  /** Get the root goal ID. */
  getRootId(): string | undefined {
    return this.rootId
  }

  /** Get all goals. */
  getAll(): Record<string, GoalNode> {
    return { ...this.nodes }
  }

  /** Get the total number of goals. */
  size(): number {
    return Object.keys(this.nodes).length
  }

  /**
   * Get all leaf goals (no children). These are the ones assigned to agents.
   */
  getLeaves(): GoalNode[] {
    return Object.values(this.nodes).filter(n => n.children.length === 0)
  }

  /**
   * Get all goals with a given status.
   */
  getByStatus(status: GoalStatus): GoalNode[] {
    return Object.values(this.nodes).filter(n => n.status === status)
  }

  /**
   * Get pending goals that have all dependencies satisfied (ready to start).
   */
  getReady(): GoalNode[] {
    return Object.values(this.nodes).filter(n => {
      if (n.status !== 'pending') return false
      // Check all dependencies are completed
      return n.dependencies.every(depId => {
        const dep = this.nodes[depId]
        return dep?.status === 'completed'
      })
    })
  }

  /**
   * Get IDs of goals that this goal is waiting on (pending dependencies).
   */
  getPendingDependencies(goalId: string): string[] {
    const node = this.nodes[goalId]
    if (!node) return []
    return node.dependencies.filter(depId => {
      const dep = this.nodes[depId]
      return dep && dep.status !== 'completed'
    })
  }

  /**
   * Get children of a goal, sorted by priority (descending).
   */
  getChildren(goalId: string): GoalNode[] {
    const node = this.nodes[goalId]
    if (!node) return []
    return node.children
      .map(cid => this.nodes[cid])
      .filter(Boolean)
      .sort((a, b) => b.priority - a.priority)
  }

  /**
   * Recursive completion check: is the entire tree complete?
   */
  isComplete(): boolean {
    if (!this.rootId) return false
    return this.isNodeComplete(this.rootId)
  }

  private isNodeComplete(goalId: string): boolean {
    const node = this.nodes[goalId]
    if (!node) return false
    if (node.status === 'completed') return true
    if (node.children.length === 0) return false // leaf that isn't completed
    return node.children.every(cid => this.isNodeComplete(cid))
  }

  /**
   * Check if the tree has any failed goals.
   */
  hasFailed(): boolean {
    return Object.values(this.nodes).some(n => n.status === 'failed')
  }


  /**
   * Get a human-readable progress summary.
   */
  getProgressSummary(): string {
    const all = Object.values(this.nodes)
    const total = all.length
    const completed = all.filter(n => n.status === 'completed').length
    const inProgress = all.filter(n => n.status === 'in_progress').length
    const failed = all.filter(n => n.status === 'failed').length
    const blocked = all.filter(n => n.status === 'blocked').length
    const pending = all.filter(n => n.status === 'pending').length

    const pct = total > 0 ? Math.round((completed / total) * 100) : 0
    const parts = [`${completed}/${total} goals completed (${pct}%)`]
    if (inProgress > 0) parts.push(`${inProgress} in progress`)
    if (blocked > 0) parts.push(`${blocked} blocked`)
    if (failed > 0) parts.push(`${failed} failed`)
    if (pending > 0) parts.push(`${pending} pending`)

    return parts.join(' | ')
  }

  /**
   * Get a structured progress report for the team.
   */
  getProgressReport(): {
    total: number
    completed: number
    inProgress: number
    failed: number
    blocked: number
    pending: number
    cancelled: number
    completionPct: number
    totalTokensUsed: number
    totalDurationMs: number
  } {
    const all = Object.values(this.nodes)
    const completed = all.filter(n => n.status === 'completed')
    const totalTokens = completed.reduce((s, n) => s + (n.result?.tokensUsed || 0), 0)
    const totalDuration = completed.reduce((s, n) => s + (n.result?.durationMs || 0), 0)

    return {
      total: all.length,
      completed: completed.length,
      inProgress: all.filter(n => n.status === 'in_progress').length,
      failed: all.filter(n => n.status === 'failed').length,
      blocked: all.filter(n => n.status === 'blocked').length,
      pending: all.filter(n => n.status === 'pending').length,
      cancelled: all.filter(n => n.status === 'cancelled').length,
      completionPct: all.length > 0 ? Math.round((completed.length / all.length) * 100) : 0,
      totalTokensUsed: totalTokens,
      totalDurationMs: totalDuration,
    }
  }

  /**
   * Render the tree as an indented text visualization.
   */
  renderTree(goalId?: string, indent = 0): string {
    const id = goalId ?? this.rootId
    if (!id) return '(empty tree)'

    const node = this.nodes[id]
    if (!node) return '(node not found)'

    const statusIcon = {
      pending: '○',
      in_progress: '◐',
      completed: '●',
      failed: '✗',
      blocked: '⊘',
      cancelled: '⊖',
    }[node.status] ?? '?'

    const prefix = '  '.repeat(indent)
    const agentTag = node.assignedAgentId ? ` [agent:${node.assignedAgentId}]` : ''
    const roleTag = node.roleHint ? ` (${node.roleHint})` : ''
    const line = `${prefix}${statusIcon} ${node.title}${roleTag}${agentTag}`

    const childLines = node.children.map(cid => this.renderTree(cid, indent + 1))
    return [line, ...childLines].join('\n')
  }


  /**
   * Assign an agent to a goal.
   */
  assignAgent(goalId: string, agentId: string): void {
    const node = this.nodes[goalId]
    if (!node) throw new Error(`Goal ${goalId} not found`)
    node.assignedAgentId = agentId
  }

  /**
   * Cancel a goal and all its descendants.
   */
  cancelSubtree(goalId: string): void {
    const node = this.nodes[goalId]
    if (!node) return
    if (node.status !== 'completed') {
      node.status = 'cancelled'
      node.completedAt = Date.now()
    }
    for (const childId of node.children) {
      this.cancelSubtree(childId)
    }
  }

  /**
   * Remove a goal and all its descendants from the tree.
   * Also removes references from parent.
   */
  removeSubtree(goalId: string): void {
    const node = this.nodes[goalId]
    if (!node) return

    // Remove from parent's children array
    if (node.parentId) {
      const parent = this.nodes[node.parentId]
      if (parent) {
        parent.children = parent.children.filter(cid => cid !== goalId)
      }
    }

    // Recursively remove children
    for (const childId of node.children) {
      this.removeSubtree(childId)
    }

    // Remove from dependencies of other goals
    for (const n of Object.values(this.nodes)) {
      n.dependencies = n.dependencies.filter(d => d !== goalId)
    }

    delete this.nodes[goalId]
    if (this.rootId === goalId) this.rootId = undefined
  }


  /**
   * Serialize the tree to a plain object for persistence.
   */
  serialize(): { nodes: Record<string, GoalNode>; rootId?: string } {
    return {
      nodes: JSON.parse(JSON.stringify(this.nodes)),
      rootId: this.rootId,
    }
  }

  /**
   * Deserialize from a persisted object.
   */
  static deserialize(data: { nodes: Record<string, GoalNode>; rootId?: string }): GoalTree {
    return new GoalTree(data.nodes, data.rootId)
  }
}
