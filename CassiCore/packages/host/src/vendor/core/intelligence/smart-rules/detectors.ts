/**
 * Dead-end detection heuristics for Smart Rules Recovery module.
 *
 * Detects conversation dead-ends: empty responses, deflections, tool loops, and stuck patterns.
 */

export interface DeadEndDetection {
  type: 'empty_response' | 'deflection' | 'tool_loop' | 'stuck_loop'
  confidence: number  // 0-1
  details: string
}

/**
 * Detect dead-end patterns in a turn response.
 *
 * @param response - The LLM response text
 * @param toolCalls - Array of tool calls made in this turn with success status
 * @param recentHistory - Recent conversation history for loop detection
 * @returns Detection result if dead-end found, null otherwise
 * @dep callers: onTurnEnd (core/intelligence/smart-rules/index.ts)
 * @dep calls: detectEmptyResponse, detectDeflection, detectToolLoop, detectStuckLoop
 * @dep flows: OnTurnEnd → EstimateChars (2/5), OnTurnEnd → CalculateOverlap (2/4)
 * @dep module: Smart-rules
 * @dep risk: LOW | 1 caller, 2 flows, 1 module
 */
export function detectDeadEnd(
  response: string,
  toolCalls: Array<{ name: string; success: boolean }>,
  recentHistory: Array<{ role: string; content: string; toolCalls?: Array<{ name: string }> }>,
): DeadEndDetection | null {
  // Check for empty response
  const emptyResponse = detectEmptyResponse(response, toolCalls)
  if (emptyResponse) return emptyResponse

  // Check for deflection
  const deflection = detectDeflection(response, toolCalls)
  if (deflection) return deflection

  // Check for tool loop
  const toolLoop = detectToolLoop(toolCalls)
  if (toolLoop) return toolLoop

  // Check for stuck loop (repeated message patterns)
  const stuckLoop = detectStuckLoop(response, recentHistory)
  if (stuckLoop) return stuckLoop

  return null
}

/**
 * Detect empty responses with no tool calls.
 * Confidence: 0.9
 * @dep callers: detectDeadEnd (core/intelligence/smart-rules/detectors.ts)
 * @dep calls: trim
 * @dep flows: OnTurnEnd → EstimateChars (3/5)
 * @dep module: Smart-rules
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
function detectEmptyResponse(
  response: string,
  toolCalls: Array<{ name: string; success: boolean }>,
): DeadEndDetection | null {
  const trimmedResponse = response.trim()

  // Response < 20 chars with no tool calls
  if (trimmedResponse.length < 20 && toolCalls.length === 0) {
    return {
      type: 'empty_response',
      confidence: 0.9,
      details: `Response too short (${trimmedResponse.length} chars) with no tool calls`,
    }
  }

  return null
}

/**
 * Detect deflection patterns (declining to help without attempting alternatives).
 * Confidence: 0.8
 */
function detectDeflection(
  response: string,
  toolCalls: Array<{ name: string; success: boolean }>,
): DeadEndDetection | null {
  const lowerResponse = response.toLowerCase()

  // Common deflection patterns
  const deflectionPatterns = [
    "i can't",
    "i'm unable",
    "i don't have access",
    "i cannot",
    "i'm not able",
    "i do not have",
    "unfortunately i",
    "i'm sorry but",
    "i apologize but",
    "i'm not allowed",
  ]

  const hasDeflection = deflectionPatterns.some(pattern => lowerResponse.includes(pattern))

  // Only flag as deflection if no tool calls were made
  if (hasDeflection && toolCalls.length === 0) {
    return {
      type: 'deflection',
      confidence: 0.8,
      details: 'Response contains deflection language with no tool usage',
    }
  }

  return null
}

/**
 * Detect repeated tool call failures (tool loop).
 * Confidence: 0.85
 */
function detectToolLoop(
  toolCalls: Array<{ name: string; success: boolean }>,
): DeadEndDetection | null {
  if (toolCalls.length < 3) return null

  // Check if same tool called 3+ times consecutively with failures
  let consecutiveFailures = 0
  let lastToolName: string | null = null

  for (const call of toolCalls) {
    if (call.name === lastToolName && !call.success) {
      consecutiveFailures++
    } else {
      consecutiveFailures = call.success ? 0 : 1
      lastToolName = call.name
    }

    if (consecutiveFailures >= 3) {
      return {
        type: 'tool_loop',
        confidence: 0.85,
        details: `Tool '${call.name}' has failed ${consecutiveFailures} consecutive times`,
      }
    }
  }

  return null
}

/**
 * Detect repeated message patterns in recent history (stuck loop).
 * Confidence: 0.9
 * @dep callers: detectDeadEnd (core/intelligence/smart-rules/detectors.ts)
 * @dep calls: trim, calculateOverlap
 * @dep flows: OnTurnEnd → CalculateOverlap (3/4)
 * @dep module: Smart-rules
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
function detectStuckLoop(
  response: string,
  recentHistory: Array<{ role: string; content: string; toolCalls?: Array<{ name: string }> }>,
): DeadEndDetection | null {
  if (recentHistory.length < 5) return null

  // Get last 5 assistant messages
  const assistantMessages = recentHistory
    .filter(msg => msg.role === 'assistant')
    .slice(-5)

  if (assistantMessages.length < 5) return null

  // Normalize response for comparison (lowercase, remove extra whitespace)
  const normalizedResponse = response.toLowerCase().replace(/\s+/g, ' ').trim()

  // Check if similar pattern appears in recent messages
  let matchCount = 0
  for (const msg of assistantMessages) {
    const normalizedMsg = msg.content.toLowerCase().replace(/\s+/g, ' ').trim()

    // Check for substantial overlap (simple heuristic: >50% character overlap)
    const overlap = calculateOverlap(normalizedResponse, normalizedMsg)
    if (overlap > 0.5) {
      matchCount++
    }
  }

  // If 3+ out of 5 recent messages are similar, we're in a stuck loop
  if (matchCount >= 3) {
    return {
      type: 'stuck_loop',
      confidence: 0.9,
      details: `Same message pattern repeated in ${matchCount} of last 5 turns`,
    }
  }

  return null
}

/**
 * Calculate simple overlap ratio between two strings.
 * Returns a value between 0 and 1.
 * @dep callers: detectStuckLoop (core/intelligence/smart-rules/detectors.ts)
 * @dep calls: has
 * @dep flows: OnTurnEnd → CalculateOverlap (4/4)
 * @dep module: Smart-rules
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
function calculateOverlap(str1: string, str2: string): number {
  if (!str1 || !str2) return 0

  const words1 = str1.split(' ')
  const words2 = str2.split(' ')

  const set2 = new Set(words2)
  const commonWords = words1.filter(word => set2.has(word))

  const maxWords = Math.max(words1.length, words2.length)
  return maxWords > 0 ? commonWords.length / maxWords : 0
}
