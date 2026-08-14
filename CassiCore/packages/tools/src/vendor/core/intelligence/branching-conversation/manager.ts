/**
 * Branching Conversation Manager
 * 
 * Manages conversation trees with support for:
 * - Branch creation and switching
 * - Decision tree tracking
 * - Session continuity markers
 * - Tree traversal and serialization
 */

import { generateShortId } from '../utils/ids.js'
import type { Message } from "@cassicore/foundation"
import type {
  BranchingMessage,
  TurnNode,
  ConversationBranch,
  BranchingSession,
  SessionConfig,
  DecisionPoint,
  DecisionAlternative,
  ContinuityMarker,
  SerializedConversationTree,
} from './types.js'

/**
 * Branching Conversation Manager
 * 
 * This class manages conversation trees with branching support.
 * It extends the linear session model to support decision trees and alternative paths.
 */
export class BranchingConversationManager {
  private sessions = new Map<string, BranchingSession>()
  
  /**
   * Create a new session with tree-based history.
   */
  createSession(
    sessionId: string,
    channelId: string,
    senderId: string,
    config: SessionConfig,
  ): BranchingSession {
    const now = new Date()
    const session: BranchingSession = {
      id: sessionId,
      channelId,
      senderId,
      turnTree: new Map(),
      rootTurnId: null,
      branches: new Map(),
      activeBranchId: 'main',
      config,
      createdAt: now,
      lastActiveAt: now,
      tokenCount: 0,
    }
    
    // Create main branch
    const mainBranch: ConversationBranch = {
      id: 'main',
      rootTurnId: '',
      currentTurnId: '',
      turnIds: [],
      createdAt: now,
      lastActiveAt: now,
      metadata: { name: 'Main', description: 'Primary conversation path' },
    }
    session.branches.set('main', mainBranch)
    
    this.sessions.set(sessionId, session)
    return session
  }
  
  /**
   * Get a session by ID.
   */
  getSession(sessionId: string): BranchingSession | undefined {
    return this.sessions.get(sessionId)
  }
  
  /**
   * Add a turn to the active branch.
   * 
   * @param sessionId - Session identifier
   * @param message - Message content
   * @param parentTurnId - Parent turn ID (defaults to current active turn)
   * @returns The created turn ID
   */
  addTurn(
    sessionId: string,
    message: Message,
    parentTurnId?: string,
  ): string {
    const session = this.sessions.get(sessionId)
    if (!session) {
      throw new Error(`Session ${sessionId} not found`)
    }
    
    const now = new Date()
    const turnId = generateShortId(8)
    const activeBranch = session.branches.get(session.activeBranchId)
    
    if (!activeBranch) {
      throw new Error(`Active branch ${session.activeBranchId} not found`)
    }
    
    // Determine parent turn
    const actualParentTurnId = parentTurnId || activeBranch.currentTurnId || session.rootTurnId
    
    // Create branching message
    const branchingMessage: BranchingMessage = {
      ...message,
      turnId,
      parentTurnId: actualParentTurnId,
      timestamp: now,
      branchPath: session.activeBranchId,
    }
    
    // Create turn node
    const depth = actualParentTurnId 
      ? (session.turnTree.get(actualParentTurnId)?.depth || 0) + 1
      : 0
      
    const turnNode: TurnNode = {
      message: branchingMessage,
      children: [],
      depth,
    }
    
    // Add to turn tree
    session.turnTree.set(turnId, turnNode)
    
    // Update parent's children
    if (actualParentTurnId) {
      const parentNode = session.turnTree.get(actualParentTurnId)
      if (parentNode) {
        parentNode.children.push(turnId)
      }
    }
    
    // Update root if this is the first turn
    if (!session.rootTurnId) {
      session.rootTurnId = turnId
      activeBranch.rootTurnId = turnId
    }
    
    // Update active branch
    activeBranch.currentTurnId = turnId
    activeBranch.turnIds.push(turnId)
    activeBranch.lastActiveAt = now
    activeBranch.branchIndex = activeBranch.turnIds.length - 1
    
    // Update session
    session.lastActiveAt = now
    
    // Update token count (approximate)
    const contentLength = typeof message.content === 'string' 
      ? message.content.length 
      : JSON.stringify(message.content).length
    session.tokenCount += Math.ceil(contentLength / 4)
    
    return turnId
  }
  
  /**
   * Fork the current branch to create a new alternative path.
   * 
   * @param sessionId - Session identifier
   * @param newBranchId - New branch identifier
   * @param metadata - Optional branch metadata
   * @returns The created branch
   */
  forkBranch(
    sessionId: string,
    newBranchId: string,
    metadata?: { name?: string; description?: string },
  ): ConversationBranch {
    const session = this.sessions.get(sessionId)
    if (!session) {
      throw new Error(`Session ${sessionId} not found`)
    }
    
    const activeBranch = session.branches.get(session.activeBranchId)
    if (!activeBranch) {
      throw new Error(`Active branch ${session.activeBranchId} not found`)
    }
    
    // Create new branch starting from current turn
    const now = new Date()
    const newBranch: ConversationBranch = {
      id: newBranchId,
      rootTurnId: activeBranch.rootTurnId,
      currentTurnId: activeBranch.currentTurnId,
      turnIds: [...activeBranch.turnIds], // Copy all turns up to current point
      createdAt: now,
      lastActiveAt: now,
      metadata: {
        name: metadata?.name || `Branch ${newBranchId}`,
        description: metadata?.description || `Fork from ${session.activeBranchId}`,
        tags: ['fork'],
      },
    }
    
    session.branches.set(newBranchId, newBranch)
    return newBranch
  }
  
  /**
   * Switch to a different branch.
   * 
   * @param sessionId - Session identifier
   * @param branchId - Branch to switch to
   * @returns The activated branch
   */
  switchBranch(sessionId: string, branchId: string): ConversationBranch {
    const session = this.sessions.get(sessionId)
    if (!session) {
      throw new Error(`Session ${sessionId} not found`)
    }
    
    const branch = session.branches.get(branchId)
    if (!branch) {
      throw new Error(`Branch ${branchId} not found`)
    }
    
    session.activeBranchId = branchId
    branch.lastActiveAt = new Date()
    
    return branch
  }
  
  /**
   * Merge a source branch into the active branch.
   * 
   * @param sessionId - Session identifier
   * @param sourceBranchId - Branch to merge from
   * @param strategy - Merge strategy
   * @returns Success status
   */
  mergeBranch(
    sessionId: string,
    sourceBranchId: string,
    strategy: 'append' | 'replace' | 'integrate' = 'append',
  ): boolean {
    const session = this.sessions.get(sessionId)
    if (!session) {
      throw new Error(`Session ${sessionId} not found`)
    }
    
    const activeBranch = session.branches.get(session.activeBranchId)
    const sourceBranch = session.branches.get(sourceBranchId)
    
    if (!activeBranch || !sourceBranch) {
      return false
    }
    
    const now = new Date()
    
    switch (strategy) {
      case 'append':
        // Append turns from source branch that are not in active branch
        const newTurns = sourceBranch.turnIds.filter(
          id => !activeBranch.turnIds.includes(id)
        )
        activeBranch.turnIds.push(...newTurns)
        activeBranch.currentTurnId = sourceBranch.currentTurnId
        break
        
      case 'replace':
        // Replace active branch with source branch
        activeBranch.turnIds = [...sourceBranch.turnIds]
        activeBranch.currentTurnId = sourceBranch.currentTurnId
        activeBranch.rootTurnId = sourceBranch.rootTurnId
        break
        
      case 'integrate':
        // Smart integration - find divergence point and merge from there
        const divergenceIndex = this.findDivergencePoint(
          activeBranch.turnIds,
          sourceBranch.turnIds
        )
        
        if (divergenceIndex >= 0) {
          // Keep common prefix, append source branch suffix
          activeBranch.turnIds = [
            ...activeBranch.turnIds.slice(0, divergenceIndex + 1),
            ...sourceBranch.turnIds.slice(divergenceIndex + 1),
          ]
          activeBranch.currentTurnId = sourceBranch.currentTurnId
        }
        break
    }
    
    activeBranch.lastActiveAt = now
    session.lastActiveAt = now
    
    return true
  }
  
  /**
   * Find the divergence point between two turn sequences.
   */
  private findDivergencePoint(turnsA: string[], turnsB: string[]): number {
    const minLength = Math.min(turnsA.length, turnsB.length)
    for (let i = 0; i < minLength; i++) {
      if (turnsA[i] !== turnsB[i]) {
        return i - 1
      }
    }
    return minLength - 1
  }
  
  /**
   * List all branches in a session.
   */
  listBranches(sessionId: string): ConversationBranch[] {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return []
    }
    
    return Array.from(session.branches.values())
  }
  
  /**
   * Get the active branch.
   */
  getActiveBranch(sessionId: string): ConversationBranch | undefined {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return undefined
    }
    
    return session.branches.get(session.activeBranchId)
  }
  
  /**
   * Delete a branch (cannot delete active branch).
   */
  deleteBranch(sessionId: string, branchId: string): boolean {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return false
    }
    
    if (branchId === session.activeBranchId) {
      throw new Error('Cannot delete active branch')
    }
    
    return session.branches.delete(branchId)
  }
  
  /**
   * Get all turns in a branch (in order).
   */
  getBranchTurns(sessionId: string, branchId: string): BranchingMessage[] {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return []
    }
    
    const branch = session.branches.get(branchId)
    if (!branch) {
      return []
    }
    
    return branch.turnIds
      .map(turnId => session.turnTree.get(turnId))
      .filter((node): node is TurnNode => node !== undefined)
      .map(node => node.message)
  }
  
  /**
   * Get the path from root to a specific turn.
   */
  getPathToTurn(sessionId: string, turnId: string): BranchingMessage[] {
    const session = this.sessions.get(sessionId)
    if (!session || !session.turnTree.has(turnId)) {
      return []
    }
    
    const path: BranchingMessage[] = []
    let currentTurnId: string | null = turnId
    
    // Traverse up to root
    while (currentTurnId) {
      const node = session.turnTree.get(currentTurnId)
      if (!node) break
      
      path.unshift(node.message)
      
      // Move to parent
      currentTurnId = node.message.parentTurnId
    }
    
    return path
  }
  
  /**
   * Get siblings of a turn (other branches from the same parent).
   */
  getSiblings(sessionId: string, turnId: string): BranchingMessage[] {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return []
    }
    
    const node = session.turnTree.get(turnId)
    if (!node) {
      return []
    }
    
    const parentNode = node.message.parentTurnId
      ? session.turnTree.get(node.message.parentTurnId)
      : null
      
    if (!parentNode) {
      return []
    }
    
    // Get all children except the current turn
    return parentNode.children
      .filter(childId => childId !== turnId)
      .map(childId => session.turnTree.get(childId))
      .filter((n): n is TurnNode => n !== undefined)
      .map(n => n.message)
  }
  
  /**
   * Find the lowest common ancestor of two turns.
   */
  findCommonAncestor(
    sessionId: string,
    turnId1: string,
    turnId2: string,
  ): BranchingMessage | null {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return null
    }
    
    // Get paths to root for both turns
    const path1 = this.getPathToTurn(sessionId, turnId1).map(m => m.turnId)
    const path2 = this.getPathToTurn(sessionId, turnId2).map(m => m.turnId)
    
    // Find last common turn ID
    let commonAncestorId: string | null = null
    for (let i = 0; i < Math.min(path1.length, path2.length); i++) {
      if (path1[i] === path2[i]) {
        commonAncestorId = path1[i]
      } else {
        break
      }
    }
    
    if (!commonAncestorId) {
      return null
    }
    
    const node = session.turnTree.get(commonAncestorId)
    return node ? node.message : null
  }
  
  /**
   * Create a decision point with alternatives.
   */
  createDecisionPoint(
    sessionId: string,
    turnId: string,
    alternatives: Array<{ id: string; label: string; description?: string }>,
    chosenAlternativeId: string,
  ): DecisionPoint {
    const session = this.sessions.get(sessionId)
    if (!session) {
      throw new Error(`Session ${sessionId} not found`)
    }
    
    const decisionPoint: DecisionPoint = {
      id: generateShortId(8),
      turnId,
      alternatives: alternatives.map(alt => ({
        id: alt.id,
        label: alt.label,
        branchId: alt.id, // Each alternative gets its own branch
        description: alt.description,
      })),
      chosenAlternativeId,
      timestamp: new Date(),
    }
    
    // Initialize decision tree if needed
    if (!session.decisionTree) {
      session.decisionTree = {
        decisionPoints: [],
        currentPath: {
          id: generateShortId(8),
          decisionPointIds: [],
          chosenAlternativeIds: [],
          branchIds: [],
        },
      }
    }
    
    // Add decision point
    session.decisionTree.decisionPoints.push(decisionPoint)
    
    // Update current path
    session.decisionTree.currentPath.decisionPointIds.push(decisionPoint.id)
    session.decisionTree.currentPath.chosenAlternativeIds.push(chosenAlternativeId)
    
    // Create branches for each alternative if they don't exist
    for (const alt of decisionPoint.alternatives) {
      if (!session.branches.has(alt.branchId)) {
        this.forkBranch(sessionId, alt.branchId, {
          name: alt.label,
          description: alt.description,
        })
      }
    }
    
    return decisionPoint
  }
  
  /**
   * Create a continuity marker for session recovery.
   */
  createContinuityMarker(
    sessionId: string,
    description?: string,
    metadata?: Record<string, unknown>,
  ): ContinuityMarker {
    const session = this.sessions.get(sessionId)
    if (!session) {
      throw new Error(`Session ${sessionId} not found`)
    }
    
    const activeBranch = session.branches.get(session.activeBranchId)
    if (!activeBranch) {
      throw new Error(`Active branch ${session.activeBranchId} not found`)
    }
    
    const marker: ContinuityMarker = {
      id: generateShortId(8),
      sessionId,
      turnId: activeBranch.currentTurnId,
      branchId: session.activeBranchId,
      timestamp: new Date(),
      description,
      metadata,
    }
    
    // Mark the current turn with continuity info
    const currentTurn = session.turnTree.get(activeBranch.currentTurnId)
    if (currentTurn) {
      currentTurn.message.continuityMarker = {
        sessionId,
        checkpointId: marker.id,
        isContinuity: true,
      }
    }
    
    return marker
  }
  
  /**
   * Serialize session to JSON for persistence.
   */
  serializeSession(sessionId: string): SerializedConversationTree | null {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return null
    }
    
    // Convert Maps to plain objects
    const turnTreeObj: Record<string, TurnNode> = {}
    for (const [key, value] of session.turnTree.entries()) {
      turnTreeObj[key] = value
    }
    
    const branchesObj: Record<string, ConversationBranch> = {}
    for (const [key, value] of session.branches.entries()) {
      branchesObj[key] = value
    }
    
    return {
      turnTree: turnTreeObj,
      branches: branchesObj,
      rootTurnId: session.rootTurnId,
      activeBranchId: session.activeBranchId,
      schemaVersion: 1,
    }
  }
  
  /**
   * Deserialize session from JSON.
   */
  deserializeSession(
    sessionId: string,
    data: SerializedConversationTree,
  ): BranchingSession {
    const session = this.sessions.get(sessionId)
    if (!session) {
      throw new Error(`Session ${sessionId} not found`)
    }
    
    // Convert plain objects back to Maps
    session.turnTree = new Map(Object.entries(data.turnTree))
    session.branches = new Map(Object.entries(data.branches))
    session.rootTurnId = data.rootTurnId
    session.activeBranchId = data.activeBranchId
    
    return session
  }
  
  /**
   * Get linear history for compatibility with existing code.
   * 
   * Returns the active branch's turns as a linear array.
   */
  getLinearHistory(sessionId: string): Message[] {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return []
    }
    
    const activeBranch = session.branches.get(session.activeBranchId)
    if (!activeBranch) {
      return []
    }
    
    return activeBranch.turnIds
      .map(turnId => session.turnTree.get(turnId))
      .filter((node): node is TurnNode => node !== undefined)
      .map(node => ({
        role: node.message.role,
        content: node.message.content,
        name: node.message.name,
      }))
  }
}
