/**
 * Constellation Unified Cell
 *
 * Consolidates FluxCell and TriadCell into a single composable execution unit.
 *
 * Core insight: Both cells are containers for Helix execution with different
 * composition strategies:
 * - FluxCell: graph-based topology with conditional transitions
 * - TriadCell: hierarchical parent-child relationships with message passing
 *
 * The unified cell supports both strategies simultaneously.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { HelixSession, HelixSessionConfig, HelixResult } from '../helix/unified-session.js'
import type { Blackboard, BlackboardSummary } from '../flux-team/blackboard.js'
import type { BlackboardState } from '../../../types/flux-team.js'

// Hierarchy types (from Triad)
export interface HierarchyMessage {
  id: string
  fromCellId: string
  toCellId: string
  type: 'result' | 'context' | 'command' | 'query'
  payload: unknown
  timestamp: number
}

export interface CellHierarchy {
  depth: number
  maxDepth: number
  parentId?: string
  children: string[]
  siblingIndex: number
}

// Topology types (from Flux)
export interface TopologyNode {
  id: string
  type: 'task' | 'control' | 'parallel' | 'merge'
  config?: HelixSessionConfig
  condition?: Condition
  parallelBranches?: string[][]
}

export interface TopologyEdge {
  from: string
  to: string
  condition?: Condition
}

export interface Topology {
  nodes: Map<string, TopologyNode>
  edges: Map<string, TopologyEdge[]>
  entryNode: string
}

export interface Condition {
  type: 'expression' | 'tool-result' | 'consensus'
  expression?: string
  toolName?: string
  threshold?: number
}

export interface ConditionContext {
  lastResult?: HelixResult
  cellResults: Map<string, HelixResult>
  variables: Map<string, unknown>
}

// Genome types (from Flux)
export interface AgentTraits {
  divergent: number
  convergent: number
  executive: number
}

export interface AgentGenome {
  id: string
  name: string
  description: string
  traits: AgentTraits
  baseHelixConfig: Partial<HelixSessionConfig>
  preferredModel?: string
}

// Cell configuration
export interface ConstellationCellConfig {
  // Identity
  cellId: string
  goal: string

  // Execution
  helixConfig: HelixSessionConfig

  // Hierarchy (from Triad)
  hierarchy?: {
    parentId?: string
    depth: number
    maxDepth: number
    siblingIndex: number
  }

  // Topology (from Flux)
  topology?: {
    currentNodeId?: string
    nodeConfig?: TopologyNode
  }

  // Genome
  genome: AgentGenome

  // Blackboard
  blackboard?: Blackboard

  // Lifecycle
  checkpointInterval?: number
  maxDurationMs: number
}

// Cell status
export type CellStatus = 'idle' | 'running' | 'paused' | 'completed' | 'cancelled' | 'error'

export interface CellProgress {
  status: CellStatus
  currentPhase: string
  helixProgress?: import('../helix/unified-session.js').HelixProgress
  childrenProgress?: Map<string, CellProgress>
  durationMs: number
  tokenUsage: number
}

// Cell result
export interface CellResult {
  outcome: 'success' | 'failure' | 'cancelled' | 'paused'
  result?: string
  helixResult?: HelixResult
  childResults?: Map<string, CellResult>
  tokenUsage: number
  durationMs: number
  checkpoint?: CellCheckpoint
}

export interface CellCheckpoint {
  timestamp: number
  status: CellStatus
  helixState?: unknown
  hierarchyState?: unknown
  topologyState?: unknown
}

// Cell interface
export interface ConstellationCell {
  readonly cellId: string
  readonly config: ConstellationCellConfig

  // Execution
  execute(): Promise<CellResult>
  cancel(): void
  pause(): void
  resume(): void

  // Hierarchy operations (from Triad)
  spawnChild(config: Partial<ConstellationCellConfig>): ConstellationCell
  getChildren(): ConstellationCell[]
  getParent(): ConstellationCell | undefined
  sendToParent(message: Omit<HierarchyMessage, 'id' | 'fromCellId' | 'timestamp'>): void
  receiveFromParent(): HierarchyMessage[]
  receiveFromChildren(): HierarchyMessage[]

  // Topology operations (from Flux)
  getCurrentNode(): TopologyNode | undefined
  evaluateTransition(targetNodeId: string, context: ConditionContext): boolean
  transitionTo(nodeId: string, context?: ConditionContext): Promise<boolean>

  // Status
  getStatus(): CellStatus
  getProgress(): CellProgress

  // Blackboard
  getBlackboard(): BlackboardState | undefined
  getBlackboardSummary(): BlackboardSummary | undefined
}

// Dependencies
export interface ConstellationCellDependencies {
  logger: ILogger
  createHelixSession: (config: HelixSessionConfig) => HelixSession
  onChildSpawn?: (parent: ConstellationCell, child: ConstellationCell) => void
  onMessage?: (message: HierarchyMessage) => void
}

// Factory function
export function createConstellationCell(
  config: ConstellationCellConfig,
  deps: ConstellationCellDependencies,
): ConstellationCell {
  return new ConstellationCellImpl(config, deps)
}

// Implementation
class ConstellationCellImpl implements ConstellationCell {
  readonly cellId: string
  readonly config: ConstellationCellConfig
  private deps: ConstellationCellDependencies

  private status: CellStatus = 'idle'
  private helixSession?: HelixSession
  private children = new Map<string, ConstellationCell>()
  private parent?: ConstellationCell
  private inbox = new Map<string, HierarchyMessage[]>() // fromCellId -> messages
  private outbox: HierarchyMessage[] = []

  private startTime = 0
  private tokenUsage = 0
  private currentNodeId?: string

  constructor(config: ConstellationCellConfig, deps: ConstellationCellDependencies) {
    this.cellId = config.cellId
    this.config = config
    this.deps = deps
    this.currentNodeId = config.topology?.currentNodeId

    // Wire parent if provided
    if (config.hierarchy?.parentId) {
      // Parent will be set via setParent after creation
    }
  }

  setParent(parent: ConstellationCell): void {
    this.parent = parent
  }

  async execute(): Promise<CellResult> {
    if (this.status === 'running') {
      throw new Error(`Cell ${this.cellId} is already running`)
    }

    this.status = 'running'
    this.startTime = Date.now()

    this.deps.logger.info('constellation:cell:execute:start', {
      cellId: this.cellId,
      goal: this.config.goal.slice(0, 100),
      hasParent: !!this.parent,
      childCount: this.children.size,
    })

    try {
      // Check max depth
      if (this.config.hierarchy && this.config.hierarchy.depth >= this.config.hierarchy.maxDepth) {
        this.deps.logger.warn('constellation:cell:max-depth-reached', {
          cellId: this.cellId,
          depth: this.config.hierarchy.depth,
        })
        return this.buildResult('success', 'Maximum depth reached')
      }

      // Check timeout
      if (Date.now() - this.startTime > this.config.maxDurationMs) {
        this.deps.logger.warn('constellation:cell:timeout', { cellId: this.cellId })
        return this.buildResult('failure', 'Timeout')
      }

      // Execute based on cell type
      let result: CellResult

      if (this.children.size > 0) {
        // Parent cell: coordinate children (from Triad)
        result = await this.executeAsParent()
      } else if (this.config.topology?.nodeConfig) {
        // Topology node: execute with topology awareness (from Flux)
        result = await this.executeWithTopology()
      } else {
        // Leaf cell: execute Helix session
        result = await this.executeHelix()
      }

      // Send result to parent
      if (this.parent) {
        this.sendToParent({
          type: 'result',
          payload: result,
          toCellId: this.parent.cellId,
        })
      }

      this.status = result.outcome === 'success' ? 'completed' : result.outcome

      this.deps.logger.info('constellation:cell:execute:complete', {
        cellId: this.cellId,
        outcome: result.outcome,
        durationMs: result.durationMs,
      })

      return result
    } catch (error) {
      this.status = 'error'
      this.deps.logger.error('constellation:cell:execute:error', {
        cellId: this.cellId,
        error: String(error),
      })
      return this.buildResult('failure', String(error))
    }
  }

  private async executeHelix(): Promise<CellResult> {
    // Create and run Helix session
    this.helixSession = this.deps.createHelixSession(this.config.helixConfig)

    const helixResult = await this.helixSession.run()

    this.tokenUsage += helixResult.tokenUsage.total

    return {
      outcome: 'success',
      result: helixResult.conclusion,
      helixResult,
      tokenUsage: this.tokenUsage,
      durationMs: Date.now() - this.startTime,
    }
  }

  private async executeAsParent(): Promise<CellResult> {
    // Execute children (from Triad pattern)
    const childResults = new Map<string, CellResult>()

    // Execute children in parallel
    const childPromises = Array.from(this.children.values()).map(async child => {
      const result = await child.execute()
      childResults.set(child.cellId, result)
      return result
    })

    await Promise.all(childPromises)

    // Synthesize results
    const synthesis = await this.synthesizeChildResults(childResults)

    // Execute Helix session for synthesis if needed
    let helixResult: HelixResult | undefined
    if (this.config.helixConfig) {
      const synthesisConfig: HelixSessionConfig = {
        ...this.config.helixConfig,
        goal: `Synthesize results from ${childResults.size} children: ${this.config.goal}`,
        context: synthesis,
      }
      this.helixSession = this.deps.createHelixSession(synthesisConfig)
      helixResult = await this.helixSession.run()
      this.tokenUsage += helixResult.tokenUsage.total
    }

    return {
      outcome: 'success',
      result: helixResult?.conclusion || synthesis,
      helixResult,
      childResults,
      tokenUsage: this.tokenUsage,
      durationMs: Date.now() - this.startTime,
    }
  }

  private async executeWithTopology(): Promise<CellResult> {
    const node = this.config.topology?.nodeConfig
    if (!node) {
      return this.executeHelix()
    }

    switch (node.type) {
      case 'task':
        return this.executeHelix()

      case 'control':
        // Control nodes don't execute Helix, they just evaluate conditions
        return {
          outcome: 'success',
          result: 'Control node evaluated',
          tokenUsage: 0,
          durationMs: Date.now() - this.startTime,
        }

      case 'parallel':
        // Execute parallel branches
        if (node.parallelBranches) {
          const branchResults: HelixResult[] = []
          for (const branch of node.parallelBranches) {
            // Execute each branch (simplified - in reality would spawn child cells)
            const branchResult = await this.executeHelix()
            if (branchResult.helixResult) {
              branchResults.push(branchResult.helixResult)
            }
          }
          return {
            outcome: 'success',
            result: `Executed ${branchResults.length} parallel branches`,
            tokenUsage: this.tokenUsage,
            durationMs: Date.now() - this.startTime,
          }
        }
        return this.executeHelix()

      case 'merge':
        // Merge results from multiple branches
        return this.executeAsParent()

      default:
        return this.executeHelix()
    }
  }

  private async synthesizeChildResults(
    childResults: Map<string, CellResult>,
  ): Promise<string> {
    const summaries: string[] = []
    for (const [childId, result] of childResults) {
      summaries.push(`Child ${childId}: ${result.result?.slice(0, 200) || 'No result'}`)
    }
    return summaries.join('\n\n')
  }

  // Hierarchy operations
  spawnChild(partialConfig: Partial<ConstellationCellConfig>): ConstellationCell {
    const childId = `${this.cellId}-child-${this.children.size}`

    const childConfig: ConstellationCellConfig = {
      cellId: childId,
      goal: partialConfig.goal || `Sub-task of: ${this.config.goal}`,
      helixConfig: partialConfig.helixConfig || this.config.helixConfig,
      hierarchy: {
        parentId: this.cellId,
        depth: (this.config.hierarchy?.depth || 0) + 1,
        maxDepth: this.config.hierarchy?.maxDepth || 3,
        siblingIndex: this.children.size,
      },
      genome: partialConfig.genome || this.config.genome,
      maxDurationMs: partialConfig.maxDurationMs || this.config.maxDurationMs,
    }

    const child = createConstellationCell(childConfig, this.deps)
    child.setParent(this)
    this.children.set(childId, child)

    this.deps.onChildSpawn?.(this, child)

    this.deps.logger.debug('constellation:cell:child-spawned', {
      parentId: this.cellId,
      childId,
      depth: childConfig.hierarchy.depth,
    })

    return child
  }

  getChildren(): ConstellationCell[] {
    return Array.from(this.children.values())
  }

  getParent(): ConstellationCell | undefined {
    return this.parent
  }

  sendToParent(
    message: Omit<HierarchyMessage, 'id' | 'fromCellId' | 'timestamp'>,
  ): void {
    if (!this.parent) return

    const fullMessage: HierarchyMessage = {
      id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      fromCellId: this.cellId,
      toCellId: message.toCellId,
      type: message.type,
      payload: message.payload,
      timestamp: Date.now(),
    }

    this.outbox.push(fullMessage)
    this.deps.onMessage?.(fullMessage)
  }

  receiveFromParent(): HierarchyMessage[] {
    if (!this.parent) return []
    return this.parent.inbox.get(this.cellId) || []
  }

  receiveFromChildren(): HierarchyMessage[] {
    const messages: HierarchyMessage[] = []
    for (const [childId, childMessages] of this.inbox) {
      if (this.children.has(childId)) {
        messages.push(...childMessages)
      }
    }
    return messages
  }

  // Topology operations
  getCurrentNode(): TopologyNode | undefined {
    return this.config.topology?.nodeConfig
  }

  evaluateTransition(targetNodeId: string, context: ConditionContext): boolean {
    // Simplified condition evaluation
    const node = this.config.topology?.nodeConfig
    if (!node?.condition) return true

    switch (node.condition.type) {
      case 'expression':
        // Evaluate expression against context
        return true // Simplified
      case 'consensus':
        // Check if agreement level meets threshold
        return context.lastResult?.confidence >= (node.condition.threshold || 0.8)
      default:
        return true
    }
  }

  async transitionTo(nodeId: string, context?: ConditionContext): Promise<boolean> {
    // Update current node
    this.currentNodeId = nodeId
    if (this.config.topology) {
      this.config.topology.currentNodeId = nodeId
    }

    this.deps.logger.debug('constellation:cell:topology:transition', {
      cellId: this.cellId,
      toNode: nodeId,
    })

    return true
  }

  // Lifecycle
  cancel(): void {
    this.status = 'cancelled'
    this.helixSession?.cancel()
    for (const child of this.children.values()) {
      child.cancel()
    }
  }

  pause(): void {
    this.status = 'paused'
    this.helixSession?.pause()
    for (const child of this.children.values()) {
      child.pause()
    }
  }

  resume(): void {
    if (this.status === 'paused') {
      this.status = 'running'
      this.helixSession?.resume()
      for (const child of this.children.values()) {
        child.resume()
      }
    }
  }

  // Status
  getStatus(): CellStatus {
    return this.status
  }

  getProgress(): CellProgress {
    const helixProgress = this.helixSession?.getProgress()
    const childrenProgress = new Map<string, CellProgress>()

    for (const [childId, child] of this.children) {
      childrenProgress.set(childId, child.getProgress())
    }

    return {
      status: this.status,
      currentPhase: this.currentNodeId || 'execution',
      helixProgress,
      childrenProgress,
      durationMs: Date.now() - this.startTime,
      tokenUsage: this.tokenUsage,
    }
  }

  // Blackboard
  getBlackboard(): BlackboardState | undefined {
    return this.config.blackboard?.getSnapshot()
  }

  getBlackboardSummary(): BlackboardSummary | undefined {
    return this.config.blackboard?.getSummary()
  }

  private buildResult(outcome: 'success' | 'failure', result?: string): CellResult {
    return {
      outcome,
      result,
      tokenUsage: this.tokenUsage,
      durationMs: Date.now() - this.startTime,
    }
  }
}

// Topology engine for graph-based execution
export class UnifiedTopologyEngine {
  private topology: Topology
  private cellFactory: (nodeId: string, config: Partial<ConstellationCellConfig>) => ConstellationCell
  private executedNodes = new Set<string>()
  private results = new Map<string, CellResult>()

  constructor(
    topology: Topology,
    cellFactory: (nodeId: string, config: Partial<ConstellationCellConfig>) => ConstellationCell,
  ) {
    this.topology = topology
    this.cellFactory = cellFactory
  }

  async execute(entryNodeId?: string): Promise<Map<string, CellResult>> {
    const startNode = entryNodeId || this.topology.entryNode
    await this.executeNode(startNode)
    return this.results
  }

  private async executeNode(nodeId: string): Promise<CellResult> {
    if (this.executedNodes.has(nodeId)) {
      return this.results.get(nodeId)!
    }

    const node = this.topology.nodes.get(nodeId)
    if (!node) {
      throw new Error(`Node not found: ${nodeId}`)
    }

    this.executedNodes.add(nodeId)

    // Create cell for this node
    const cell = this.cellFactory(nodeId, {
      helixConfig: node.config,
      topology: {
        currentNodeId: nodeId,
        nodeConfig: node,
      },
      maxDurationMs: 300000, // 5 minutes default
    })

    // Execute cell
    const result = await cell.execute()
    this.results.set(nodeId, result)

    // Determine next nodes based on edges and conditions
    const outgoingEdges = this.topology.edges.get(nodeId) || []
    const nextNodes: string[] = []

    for (const edge of outgoingEdges) {
      if (this.evaluateCondition(edge.condition, result)) {
        nextNodes.push(edge.to)
      }
    }

    // Execute next nodes
    for (const nextNodeId of nextNodes) {
      await this.executeNode(nextNodeId)
    }

    return result
  }

  private evaluateCondition(condition: Condition | undefined, result: CellResult): boolean {
    if (!condition) return true

    switch (condition.type) {
      case 'consensus':
        return result.helixResult?.confidence >= (condition.threshold || 0.8)
      default:
        return true
    }
  }
}

// Helper to create topology from Flux-style config
export function createTopology(
  nodes: TopologyNode[],
  edges: { from: string; to: string; condition?: Condition }[],
  entryNode: string,
): Topology {
  const nodeMap = new Map<string, TopologyNode>()
  for (const node of nodes) {
    nodeMap.set(node.id, node)
  }

  const edgeMap = new Map<string, TopologyEdge[]>()
  for (const edge of edges) {
    const existing = edgeMap.get(edge.from) || []
    existing.push({
      from: edge.from,
      to: edge.to,
      condition: edge.condition,
    })
    edgeMap.set(edge.from, existing)
  }

  return {
    nodes: nodeMap,
    edges: edgeMap,
    entryNode,
  }
}
