/**
 * Heartbeat Reader
 *
 * Reads HEARTBEAT.md from the workspace and detects if it's empty
 * (only whitespace, blank lines, and markdown headers).
 */

import { promises as fs } from 'fs'
import * as path from 'path'

import { rootLogger } from '@cassicore/events'

const logger = rootLogger.child('heartbeat-reader')

export interface HeartbeatFileResult {
  exists: boolean
  content: string
  isEmpty: boolean
}

/**
 * Check if content is "empty" — only whitespace, blank lines, and markdown headers
 */
function isContentEmpty(content: string): boolean {
  const lines = content.split('\n')
  
  for (const line of lines) {
    const trimmed = line.trim()
    
    // Skip blank lines
    if (trimmed === '') {
      continue
    }
    
    // Skip markdown headers (# Header, ## Header, etc.)
    if (/^#+\s/.test(trimmed)) {
      continue
    }
    
    // Found actual content
    return false
  }
  
  return true
}

/**
 * Read HEARTBEAT.md from the workspace
 */
export async function readHeartbeatFile(
  workspaceRoot: string,
  heartbeatFilePath: string
): Promise<HeartbeatFileResult> {
  const fullPath = path.isAbsolute(heartbeatFilePath)
    ? heartbeatFilePath
    : path.join(workspaceRoot, heartbeatFilePath)
  
  try {
    const content = await fs.readFile(fullPath, 'utf-8')
    return {
      exists: true,
      content,
      isEmpty: isContentEmpty(content),
    }
  } catch (err) {
    // File doesn't exist or can't be read
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
      return {
        exists: false,
        content: '',
        isEmpty: true,
      }
    }
    
    // Other error — log and treat as empty
    logger.error('Failed to read heartbeat file', { error: String(err) })
    return {
      exists: false,
      content: '',
      isEmpty: true,
    }
  }
}
