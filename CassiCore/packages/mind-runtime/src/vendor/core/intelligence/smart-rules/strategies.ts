/**
 * Recovery strategies for Smart Rules Recovery module.
 *
 * Provides concrete actions to recover from detected dead-ends.
 */

import type { DeadEndDetection } from './detectors.js'

export interface RecoveryAction {
  type: 'inject_prompt' | 'rewrite_response' | 'suggest_alternative'
  content: string
}

/**
 * Get a recovery strategy based on the detected dead-end type.
 *
 * @param detection - The dead-end detection result
 * @returns Recovery action to take
 */
export function getRecoveryStrategy(detection: DeadEndDetection): RecoveryAction {
  switch (detection.type) {
    case 'empty_response':
      return getEmptyResponseStrategy()

    case 'deflection':
      return getDeflectionStrategy()

    case 'tool_loop':
      return getToolLoopStrategy(detection)

    case 'stuck_loop':
      return getStuckLoopStrategy()

    default:
      // Fallback for unknown types
      return {
        type: 'inject_prompt',
        content: 'The previous response encountered an issue. Please reconsider the approach and provide a concrete next step.',
      }
  }
}

/**
 * Recovery strategy for empty responses.
 * Injects a prompt encouraging concrete action.
 */
function getEmptyResponseStrategy(): RecoveryAction {
  return {
    type: 'inject_prompt',
    content: 'The previous response was empty. Please analyze the conversation context and provide a concrete next step.',
  }
}

/**
 * Recovery strategy for deflection patterns.
 * Suggests concrete alternatives based on available tools.
 */
function getDeflectionStrategy(): RecoveryAction {
  return {
    type: 'rewrite_response',
    content: 'Instead of declining, consider: 1) What tools are available that might help? 2) Can you break down the request into smaller, achievable steps? 3) Is there partial information you can provide that would be useful?',
  }
}

/**
 * Recovery strategy for tool loops.
 * Suggests alternative approaches when a tool repeatedly fails.
 *
 * @param detection - Contains details about which tool is failing
 */
function getToolLoopStrategy(detection: DeadEndDetection): RecoveryAction {
  // Extract tool name from details if possible
  const toolMatch = detection.details.match(/Tool '([^']+)' has failed/)
  const toolName = toolMatch ? toolMatch[1] : 'unknown'

  // Extract failure count
  const countMatch = detection.details.match(/failed (\d+) consecutive/)
  const failCount = countMatch ? countMatch[1] : 'multiple'

  return {
    type: 'suggest_alternative',
    content: `Tool '${toolName}' has failed ${failCount} consecutive times. Consider alternative approaches: 1) Check if the tool parameters are correct 2) Try a different tool that achieves similar results 3) Break down the operation into smaller steps 4) Verify prerequisites are met before retrying`,
  }
}

/**
 * Recovery strategy for stuck loops.
 * Provides structured guidance to break repetitive patterns.
 */
function getStuckLoopStrategy(): RecoveryAction {
  return {
    type: 'inject_prompt',
    content: 'A conversation loop has been detected. Break the pattern by: 1) Summarizing what has been tried 2) Identifying what\'s different about the remaining attempts 3) Trying a fundamentally different approach 4) Asking clarifying questions if the goal is unclear',
  }
}
