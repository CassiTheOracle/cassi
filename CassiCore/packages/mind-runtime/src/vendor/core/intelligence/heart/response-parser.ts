/**
 * Response Parser
 *
 * Parses agent responses for HEARTBEAT_OK contract enforcement.
 * Implements the ackMaxChars suppression logic.
 */

export interface ParseHeartbeatResponseResult {
  isOk: boolean
  alertContent: string
  reasoning?: string
  shouldSuppress: boolean
}

/**
 * Parse agent response for HEARTBEAT_OK contract
 * 
 * - HEARTBEAT_OK at start or end → isOk: true
 * - Strip HEARTBEAT_OK token, measure remaining content
 * - If remaining <= ackMaxChars → suppress (just an ack)
 * - If remaining > ackMaxChars → treat as alert, deliver
 * - HEARTBEAT_OK in middle → not treated specially
 * - No HEARTBEAT_OK → full alert, deliver everything
 */
export function parseHeartbeatResponse(
  response: string,
  ackMaxChars: number
): ParseHeartbeatResponseResult {
  const trimmed = response.trim()
  
  // Check for HEARTBEAT_OK at start or end
  const startsWithOk = trimmed.startsWith('HEARTBEAT_OK')
  const endsWithOk = trimmed.endsWith('HEARTBEAT_OK')
  
  if (!startsWithOk && !endsWithOk) {
    // No HEARTBEAT_OK found → full alert
    return {
      isOk: false,
      alertContent: trimmed,
      shouldSuppress: false,
    }
  }
  
  // Strip HEARTBEAT_OK from start and/or end
  let content = trimmed
  
  if (startsWithOk) {
    content = content.replace(/^HEARTBEAT_OK\s*/, '')
  }
  
  if (endsWithOk && content !== trimmed) {
    // Only strip from end if we didn't already modify from start
    // (to avoid double-processing if both start and end)
    content = content.replace(/\s*HEARTBEAT_OK$/, '')
  }
  
  content = content.trim()
  
  // If content is empty after stripping, it's a pure ack
  if (content.length === 0) {
    return {
      isOk: true,
      alertContent: '',
      shouldSuppress: true,
    }
  }
  
  // Check if remaining content exceeds threshold
  const shouldSuppress = content.length <= ackMaxChars
  
  return {
    isOk: true,
    alertContent: shouldSuppress ? '' : content,
    shouldSuppress,
  }
}
