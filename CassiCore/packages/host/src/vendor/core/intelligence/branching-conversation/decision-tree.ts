/**
 * Decision Tree Utilities
 * 
 * Helper functions for working with decision trees in branching conversations.
 * Provides algorithms for tree traversal, path finding, and analysis.
 */

import type {
  BranchingSession,
  TurnNode,
  DecisionPoint,
  DecisionPath,
  BranchingMessage,
} from './types.js'

/**
 * Decision Tree Analyzer
 * 
 * Provides utilities for analyzing and traversing decision trees.
 */
export class DecisionTreeAnalyzer {
  /**
   * Find all decision points in a session.
   */
  static findDecisionPoints(session: BranchingSession): DecisionPoint[] {
    if (!session.decisionTree) {
      return []
    }
    
    return session.decisionTree.decisionPoints
  }
  
  /**
   * Get the current decision path.
   */
  static getCurrentPath(session: BranchingSession): DecisionPath | null {
    return session.decisionTree?.currentPath || null
  }
  
  /**
   * Find all paths from root to leaf nodes.
   */
  static findAllPaths(session: BranchingSession): BranchingMessage[][] {
    if (!session.rootTurnId) {
      return []
    }
    
    const paths: BranchingMessage[][] = []
    
    // DFS to find all paths
    const dfs = (turnId: string, currentPath: BranchingMessage[]) => {
      const node = session.turnTree.get(turnId)
      if (!node) return
      
      const newPath = [...currentPath, node.message]
      
      // If leaf node (no children or only one child that's continuation)
      if (node.children.length === 0) {
        paths.push(newPath)
        return
      }
      
      // Explore all children
      for (const childId of node.children) {
        dfs(childId, newPath)
      }
    }
    
    dfs(session.rootTurnId, [])
    
    return paths
  }
  
  /**
   * Find the shortest path between two turns.
   */
  static findShortestPath(
    session: BranchingSession,
    fromTurnId: string,
    toTurnId: string,
  ): BranchingMessage[] | null {
    // Use BFS for shortest path
    const visited = new Set<string>()
    const queue: Array<{ turnId: string; path: BranchingMessage[] }> = []
    
    const startNode = session.turnTree.get(fromTurnId)
    if (!startNode) return null
    
    queue.push({ turnId: fromTurnId, path: [startNode.message] })
    visited.add(fromTurnId)
    
    while (queue.length > 0) {
      const { turnId, path } = queue.shift()!
      
      if (turnId === toTurnId) {
        return path
      }
      
      const node = session.turnTree.get(turnId)
      if (!node) continue
      
      // Explore children
      for (const childId of node.children) {
        if (!visited.has(childId)) {
          const childNode = session.turnTree.get(childId)
          if (childNode) {
            queue.push({
              turnId: childId,
              path: [...path, childNode.message],
            })
            visited.add(childId)
          }
        }
      }
      
      // Also explore parent if exists
      if (node.message.parentTurnId && !visited.has(node.message.parentTurnId)) {
        const parentNode = session.turnTree.get(node.message.parentTurnId)
        if (parentNode) {
          queue.push({
            turnId: node.message.parentTurnId,
            path: [...path, parentNode.message],
          })
          visited.add(node.message.parentTurnId)
        }
      }
    }
    
    return null
  }
  
  /**
   * Calculate depth of a turn in the tree.
   */
  static getTurnDepth(session: BranchingSession, turnId: string): number {
    const node = session.turnTree.get(turnId)
    return node?.depth || 0
  }
  
  /**
   * Calculate branching factor at a turn.
   */
  static getBranchingFactor(session: BranchingSession, turnId: string): number {
    const node = session.turnTree.get(turnId)
    return node?.children.length || 0
  }
  
  /**
   * Find all leaf nodes (end points) in the tree.
   */
  static findLeafNodes(session: BranchingSession): TurnNode[] {
    const leaves: TurnNode[] = []
    
    for (const node of session.turnTree.values()) {
      if (node.children.length === 0) {
        leaves.push(node)
      }
    }
    
    return leaves
  }
  
  /**
   * Find all fork points (turns with multiple children).
   */
  static findForkPoints(session: BranchingSession): TurnNode[] {
    const forks: TurnNode[] = []
    
    for (const node of session.turnTree.values()) {
      if (node.children.length > 1) {
        forks.push(node)
      }
    }
    
    return forks
  }
  
  /**
   * Calculate tree statistics.
   */
  static getTreeStats(session: BranchingSession): {
    totalTurns: number
    maxDepth: number
    totalBranches: number
    forkPoints: number
    leafNodes: number
    averageBranchingFactor: number
  } {
    let maxDepth = 0
    let totalBranchingFactor = 0
    let forkCount = 0
    
    for (const node of session.turnTree.values()) {
      maxDepth = Math.max(maxDepth, node.depth)
      
      if (node.children.length > 0) {
        totalBranchingFactor += node.children.length
        if (node.children.length > 1) {
          forkCount++
        }
      }
    }
    
    const totalTurns = session.turnTree.size
    const averageBranchingFactor = totalTurns > 0 
      ? totalBranchingFactor / totalTurns 
      : 0
    
    return {
      totalTurns,
      maxDepth,
      totalBranches: session.branches.size,
      forkPoints: forkCount,
      leafNodes: this.findLeafNodes(session).length,
      averageBranchingFactor,
    }
  }
  
  /**
   * Find common prefix between two branches.
   */
  static findCommonPrefix(
    session: BranchingSession,
    branchId1: string,
    branchId2: string,
  ): BranchingMessage[] {
    const branch1 = session.branches.get(branchId1)
    const branch2 = session.branches.get(branchId2)
    
    if (!branch1 || !branch2) {
      return []
    }
    
    const commonTurns: BranchingMessage[] = []
    
    for (let i = 0; i < Math.min(branch1.turnIds.length, branch2.turnIds.length); i++) {
      if (branch1.turnIds[i] === branch2.turnIds[i]) {
        const node = session.turnTree.get(branch1.turnIds[i])
        if (node) {
          commonTurns.push(node.message)
        }
      } else {
        break
      }
    }
    
    return commonTurns
  }
  
  /**
   * Find divergence point between two branches.
   */
  static findDivergencePoint(
    session: BranchingSession,
    branchId1: string,
    branchId2: string,
  ): BranchingMessage | null {
    const branch1 = session.branches.get(branchId1)
    const branch2 = session.branches.get(branchId2)
    
    if (!branch1 || !branch2) {
      return null
    }
    
    for (let i = 0; i < Math.min(branch1.turnIds.length, branch2.turnIds.length); i++) {
      if (branch1.turnIds[i] !== branch2.turnIds[i]) {
        if (i > 0) {
          const node = session.turnTree.get(branch1.turnIds[i - 1])
          return node ? node.message : null
        }
        return null
      }
    }
    
    // One branch is prefix of the other
    return null
  }
  
  /**
   * Get all turns that are ancestors of a given turn.
   */
  static getAncestors(
    session: BranchingSession,
    turnId: string,
  ): BranchingMessage[] {
    const ancestors: BranchingMessage[] = []
    let currentTurnId: string | null = turnId
    
    while (currentTurnId) {
      const node = session.turnTree.get(currentTurnId)
      if (!node) break
      
      if (node.message.parentTurnId) {
        const parentNode = session.turnTree.get(node.message.parentTurnId)
        if (parentNode) {
          ancestors.unshift(parentNode.message)
          currentTurnId = node.message.parentTurnId
        } else {
          break
        }
      } else {
        break
      }
    }
    
    return ancestors
  }
  
  /**
   * Get all turns that are descendants of a given turn.
   */
  static getDescendants(
    session: BranchingSession,
    turnId: string,
  ): BranchingMessage[] {
    const descendants: BranchingMessage[] = []
    
    const dfs = (currentTurnId: string) => {
      const node = session.turnTree.get(currentTurnId)
      if (!node) return
      
      for (const childId of node.children) {
        const childNode = session.turnTree.get(childId)
        if (childNode) {
          descendants.push(childNode.message)
          dfs(childId)
        }
      }
    }
    
    dfs(turnId)
    
    return descendants
  }
  
  /**
   * Check if a turn is on the current active path.
   */
  static isOnActivePath(
    session: BranchingSession,
    turnId: string,
  ): boolean {
    const activeBranch = session.branches.get(session.activeBranchId)
    if (!activeBranch) return false
    
    return activeBranch.turnIds.includes(turnId)
  }
  
  /**
   * Find the most recent decision point before a turn.
   */
  static findRecentDecisionPoint(
    session: BranchingSession,
    turnId: string,
  ): DecisionPoint | null {
    if (!session.decisionTree) {
      return null
    }
    
    // Get path to turn
    const path = this.getAncestors(session, turnId)
    const turnNode = session.turnTree.get(turnId)
    if (turnNode) {
      path.push(turnNode.message)
    }
    
    // Find most recent decision point on this path
    for (let i = path.length - 1; i >= 0; i--) {
      const msg = path[i]
      const decisionPoint = session.decisionTree.decisionPoints.find(
        dp => dp.turnId === msg.turnId
      )
      
      if (decisionPoint) {
        return decisionPoint
      }
    }
    
    return null
  }
}
