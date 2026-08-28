/**
 * Branching Conversation Middleware
 * 
 * Middleware for the turn pipeline to support branching conversations.
 * Integrates with BranchingConversationManager to track turns in a tree structure.
 */

import { rootLogger } from '@cassicore/events'
import type { TurnContext, TurnResult } from '@cassicore/foundation'

/** D:-only (not in @cassicore/foundation): turn middleware fn type. */
type TurnMiddleware = (ctx: TurnContext, next: () => Promise<TurnResult>) => Promise<TurnResult>
import type { BranchingConversationManager } from './manager.js'
import type { BranchingMessage } from './types.js'

const logger = rootLogger.child('branching-middleware')

/**
 * Create middleware that integrates branching conversation tracking.
 * 
 * This middleware:
 * - Tracks each turn in the conversation tree
 * - Maintains branch state and active branch
 * - Supports fork/merge operations
 * - Provides continuity markers
 * 
 * @param manager - Branching conversation manager instance
 * @returns Turn middleware function
 */
export function makeBranchingConversationMiddleware(
  manager: BranchingConversationManager,
): TurnMiddleware {
  return async (ctx: TurnContext, next: () => Promise<TurnResult>): Promise<TurnResult> => {
    const sessionId = ctx.session.id
    
    // Ensure session exists in manager
    if (!manager.getSession(sessionId)) {
      manager.createSession(
        sessionId,
        ctx.session.channelId,
        ctx.session.senderId,
        ctx.session.config,
      )
    }
    
    // Add user message to tree before processing
    const userMessage: BranchingMessage = {
      role: 'user',
      content: ctx.inbound.content,
      turnId: generateTurnId(),
      parentTurnId: null, // Will be set by manager
      timestamp: new Date(),
      branchPath: manager.getActiveBranch(sessionId)?.id || 'main',
    }
    
    // Add the turn (manager will determine parent based on active branch)
    const turnId = manager.addTurn(sessionId, ctx.inbound as any, undefined)
    
    // Update context with turn ID for downstream middleware
    ;(ctx as any).turnId = turnId
    
    // Proceed with turn processing
    const result = await next()
    
    // Add assistant response to tree after processing
    const assistantMessage: BranchingMessage = {
      role: 'assistant',
      content: result.response,
      turnId: generateTurnId(),
      parentTurnId: turnId, // Parent is the user turn we just added
      timestamp: new Date(),
      branchPath: manager.getActiveBranch(sessionId)?.id || 'main',
    }
    
    manager.addTurn(sessionId, assistantMessage as any, turnId)
    
    return result
  }
}

/**
 * Create middleware for branch switching.
 * 
 * This middleware allows dynamic branch switching during a turn.
 * Useful for exploring alternative conversation paths.
 * 
 * @param manager - Branching conversation manager instance
 * @returns Turn middleware function
 */
export function makeBranchSwitchMiddleware(
  manager: BranchingConversationManager,
): TurnMiddleware {
  return async (ctx: TurnContext, next: () => Promise<TurnResult>): Promise<TurnResult> => {
    // Check if branch switch is requested (via context metadata)
    const branchSwitch = (ctx as any).branchSwitch
    if (branchSwitch?.targetBranchId) {
      try {
        manager.switchBranch(ctx.session.id, branchSwitch.targetBranchId)
      } catch (error) {
        logger.warn(`Failed to switch branch: ${(error as Error).message}`)
        // Continue with current branch
      }
    }
    
    return await next()
  }
}

/**
 * Create middleware for decision point tracking.
 * 
 * This middleware automatically creates decision points when multiple
 * alternatives are detected in the conversation flow.
 * 
 * @param manager - Branching conversation manager instance
 * @returns Turn middleware function
 */
export function makeDecisionPointMiddleware(
  manager: BranchingConversationManager,
): TurnMiddleware {
  return async (ctx: TurnContext, next: () => Promise<TurnResult>): Promise<TurnResult> => {
    // Check if decision point is requested
    const decisionPoint = (ctx as any).decisionPoint
    if (decisionPoint?.alternatives && decisionPoint.chosenAlternativeId) {
      try {
        manager.createDecisionPoint(
          ctx.session.id,
          (ctx as any).turnId || '',
          decisionPoint.alternatives,
          decisionPoint.chosenAlternativeId,
        )
      } catch (error) {
        logger.warn(`Failed to create decision point: ${(error as Error).message}`)
      }
    }
    
    return await next()
  }
}

/**
 * Create middleware for continuity markers.
 * 
 * This middleware creates continuity markers at strategic points
 * to enable session recovery after daemon restarts.
 * 
 * @param manager - Branching conversation manager instance
 * @param checkpointInterval - Number of turns between checkpoints (default: 10)
 * @returns Turn middleware function
 */
export function makeContinuityMarkerMiddleware(
  manager: BranchingConversationManager,
  checkpointInterval: number = 10,
): TurnMiddleware {
  // Track turns per session for checkpoint timing
  const turnCounters = new Map<string, number>()
  
  return async (ctx: TurnContext, next: () => Promise<TurnResult>): Promise<TurnResult> => {
    const sessionId = ctx.session.id
    
    // Increment turn counter
    const count = (turnCounters.get(sessionId) || 0) + 1
    turnCounters.set(sessionId, count)
    
    // Create checkpoint every N turns
    if (count % checkpointInterval === 0) {
      try {
        manager.createContinuityMarker(
          sessionId,
          `Checkpoint after ${count} turns`,
          { turnCount: count },
        )
      } catch (error) {
        logger.warn(`Failed to create continuity marker: ${(error as Error).message}`)
      }
    }
    
    return await next()
  }
}

/**
 * Generate a unique turn ID.
 */
function generateTurnId(): string {
  return `turn_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`
}

/**
 * Utility: Get current branch information for a session.
 */
export function getCurrentBranchInfo(
  manager: BranchingConversationManager,
  sessionId: string,
) {
  const session = manager.getSession(sessionId)
  if (!session) {
    return null
  }
  
  const activeBranch = manager.getActiveBranch(sessionId)
  if (!activeBranch) {
    return null
  }
  
  return {
    branchId: session.activeBranchId,
    branchName: activeBranch.metadata?.name || session.activeBranchId,
    turnCount: activeBranch.turnIds.length,
    lastActiveAt: activeBranch.lastActiveAt,
  }
}

/**
 * Utility: List all branches with summary info.
 */
export function listBranchesWithInfo(
  manager: BranchingConversationManager,
  sessionId: string,
) {
  const branches = manager.listBranches(sessionId)
  
  return branches.map(branch => ({
    id: branch.id,
    name: branch.metadata?.name || branch.id,
    description: branch.metadata?.description,
    turnCount: branch.turnIds.length,
    isActive: manager.getActiveBranch(sessionId)?.id === branch.id,
    lastActiveAt: branch.lastActiveAt,
  }))
}

/**
 * Utility: Get conversation tree visualization data.
 */
export function getTreeVisualization(
  manager: BranchingConversationManager,
  sessionId: string,
) {
  const session = manager.getSession(sessionId)
  if (!session) {
    return null
  }
  
  // Build tree structure for visualization
  const buildTreeNode = (turnId: string): any => {
    const node = session.turnTree.get(turnId)
    if (!node) {
      return null
    }
    
    return {
      id: turnId,
      role: node.message.role,
      content: typeof node.message.content === 'string' 
        ? node.message.content.substring(0, 100) 
        : '[complex content]',
      depth: node.depth,
      children: node.children.map(buildTreeNode).filter(Boolean),
      branch: node.message.branchPath,
    }
  }
  
  if (!session.rootTurnId) {
    return null
  }
  
  return buildTreeNode(session.rootTurnId)
}
