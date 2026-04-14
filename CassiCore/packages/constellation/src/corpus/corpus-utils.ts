/**
 * Corpus Utilities — Stateless helper functions for the Corpus organizer.
 *
 * Extracted from corpus.ts to improve modularity and testability.
 * These functions have no dependencies on Corpus state.
 */

import type { CorpusDirectiveType } from '../corpus-types.js'
import type { GuidanceUrgency } from '../../helix/brainstem-types.js'


/**
 * Normalize a directive type string to a valid CorpusDirectiveType.
 *
 * @param raw - Raw string from LLM response
 * @returns Normalized directive type or null if unrecognized
 */
export function normalizeDirectiveType(raw: string): CorpusDirectiveType | null {
  const map: Record<string, CorpusDirectiveType> = {
    'guidance': 'guidance',
    'guide': 'guidance',
    'suggest': 'guidance',
    'redirect': 'redirect',
    'refocus': 'redirect',
    'change': 'redirect',
    'throttle': 'throttle',
    'slow': 'throttle',
    'priority-shift': 'priority-shift',
    'priority': 'priority-shift',
    'prioritize': 'priority-shift',
    'cancel': 'cancel',
    'stop': 'cancel',
    'abort': 'cancel',
  }
  return map[raw] ?? null
}


/**
 * Normalize an urgency string to a valid GuidanceUrgency.
 *
 * @param raw - Raw string from LLM response
 * @returns Normalized urgency or null if unrecognized
 */
export function normalizeUrgency(raw: string): GuidanceUrgency | null {
  const map: Record<string, GuidanceUrgency> = {
    'low': 'low',
    'medium': 'medium',
    'med': 'medium',
    'moderate': 'medium',
    'high': 'high',
    'critical': 'critical',
    'urgent': 'critical',
  }
  return map[raw] ?? null
}


/**
 * Extract file paths from tool call arguments.
 *
 * Handles various argument formats (JSON string, object, etc.)
 * Returns an array of file path strings found in common path fields.
 *
 * @param args - Tool call arguments (string, object, or unknown)
 * @returns Array of extracted file paths
 */
export function extractFilePaths(
  args: string | Record<string, unknown> | unknown
): string[] {
  const paths: string[] = []

  try {
    const obj = typeof args === 'string' ? JSON.parse(args) : args
    if (!obj || typeof obj !== 'object') return paths

    const record = obj as Record<string, unknown>

    // Common path field names
    for (const key of ['path', 'relative_path', 'filePath', 'file_path', 'file']) {
      if (typeof record[key] === 'string' && record[key]) {
        paths.push(record[key] as string)
      }
    }
  } catch {
    // Not parseable — ignore
  }

  return paths
}