/**
 * Blackboard Search Utilities
 *
 * Provides cursor encode/decode, pattern validation, regex compilation,
 * and generic pagination helpers used by all Blackboard search methods.
 */

import {
  MAX_PATTERN_LENGTH,
  DEFAULT_SEARCH_LIMIT,
  MAX_SEARCH_LIMIT,
} from '../types/blackboard-search.js'
import type {
  SearchCursor,
  PaginatedResult,
  BaseSearchOptions,
} from '../types/blackboard-search.js'

// Re-export constants for convenience
export {
  MAX_PATTERN_LENGTH,
  DEFAULT_SEARCH_LIMIT,
  MAX_SEARCH_LIMIT,
} from '../types/blackboard-search.js'


/**
 * Encode a cursor position into an opaque Base64url string.
 * Uses URL-safe Base64 so cursors can be passed as query parameters without encoding.
 */
export function encodeCursor(cursor: SearchCursor): string {
  const json = JSON.stringify(cursor)
  return Buffer.from(json, 'utf-8')
    .toString('base64url')
}

/**
 * Decode an opaque cursor string back into a SearchCursor.
 * Returns null if the cursor is invalid or malformed.
 */
export function decodeCursor(opaque: string): SearchCursor | null {
  try {
    const json = Buffer.from(opaque, 'base64url').toString('utf-8')
    const parsed = JSON.parse(json)
    if (typeof parsed.ts !== 'number' || typeof parsed.id !== 'string') {
      return null
    }
    return parsed as SearchCursor
  } catch {
    return null
  }
}

/**
 * Encode a composite cursor that contains per-board cursors for cross-board search.
 * @dep callers: searchAll (core/intelligence/flux-team/blackboard.ts), blackboard-search.test.ts (tests/flux-team/blackboard-search.test.ts)
 * @dep module: Flux-team
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function encodeCompositeCursor(
  cursors: Record<string, string>,
): string {
  return Buffer.from(JSON.stringify(cursors), 'utf-8').toString('base64url')
}

/**
 * Decode a composite cursor back into per-board cursor strings.
 * Returns null if invalid.
 * @dep callers: searchAll (core/intelligence/flux-team/blackboard.ts), blackboard-search.test.ts (tests/flux-team/blackboard-search.test.ts)
 * @dep module: Flux-team
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function decodeCompositeCursor(
  opaque: string,
): Record<string, string> | null {
  try {
    const json = Buffer.from(opaque, 'base64url').toString('utf-8')
    const parsed = JSON.parse(json)
    if (typeof parsed !== 'object' || parsed === null) return null
    return parsed as Record<string, string>
  } catch {
    return null
  }
}


/**
 * Validate a regex pattern string.
 * Returns an error message if invalid, or null if valid.
 * @dep callers: compilePattern (core/intelligence/flux-team/blackboard-search.ts), blackboard-search.test.ts (tests/flux-team/blackboard-search.test.ts)
 * @dep flows: SearchAll → ValidatePattern (4/4)
 * @dep module: Flux-team
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */
export function validatePattern(pattern: string): string | null {
  if (pattern.length > MAX_PATTERN_LENGTH) {
    return `Pattern too long (${pattern.length} chars, max ${MAX_PATTERN_LENGTH})`
  }
  try {
    new RegExp(pattern, 'i')
    return null
  } catch (err) {
    return `Invalid regex: ${String(err)}`
  }
}

/**
 * Compile a pattern string into a RegExp.
 * Uses case-insensitive flag only (no 'g' flag to avoid stateful lastIndex issues).
 * Throws if the pattern is invalid or too long.
 * @dep callers: searchChannel (core/intelligence/flux-team/blackboard.ts), searchScratchpad (core/intelligence/flux-team/blackboard.ts), searchToolLog (core/intelligence/flux-team/blackboard.ts), searchArtifacts (core/intelligence/flux-team/blackboard.ts), searchPlan (core/intelligence/flux-team/blackboard.ts) [+2]
 * @dep calls: validatePattern
 * @dep flows: SearchAll → ValidatePattern (3/4)
 * @dep module: Flux-team
 * @dep risk: HIGH | 7 callers, 1 flow, 1 module
 */
export function compilePattern(pattern: string): RegExp {
  const error = validatePattern(pattern)
  if (error) {
    throw new Error(error)
  }
  return new RegExp(pattern, 'i')
}

/**
 * Test if any of the given fields match the compiled pattern.
 * @dep callers: searchChannel (core/intelligence/flux-team/blackboard.ts), searchScratchpad (core/intelligence/flux-team/blackboard.ts), searchToolLog (core/intelligence/flux-team/blackboard.ts), searchArtifacts (core/intelligence/flux-team/blackboard.ts), searchPlan (core/intelligence/flux-team/blackboard.ts) [+2]
 * @dep calls: test
 * @dep flows: SearchAll → MatchesAny (3/3)
 * @dep module: Flux-team
 * @dep risk: HIGH | 7 callers, 1 flow, 1 module
 */
export function matchesAny(regex: RegExp, fields: (string | undefined)[]): string[] {
  const matched: string[] = []
  for (const field of fields) {
    if (field && regex.test(field)) {
      matched.push(field)
    }
  }
  return matched
}


/**
 * Normalize and clamp the `limit` option.
 * @dep callers: searchChannel (core/intelligence/flux-team/blackboard.ts), searchScratchpad (core/intelligence/flux-team/blackboard.ts), searchToolLog (core/intelligence/flux-team/blackboard.ts), searchArtifacts (core/intelligence/flux-team/blackboard.ts), searchPlan (core/intelligence/flux-team/blackboard.ts) [+2]
 * @dep flows: SearchAll → NormalizeLimit (3/3)
 * @dep module: Flux-team
 * @dep risk: HIGH | 7 callers, 1 flow, 1 module
 */
export function normalizeLimit(limit?: number): number {
  if (!limit || limit <= 0) return DEFAULT_SEARCH_LIMIT
  return Math.min(limit, MAX_SEARCH_LIMIT)
}

/**
 * Apply cursor-based pagination to a pre-sorted, pre-filtered array of items.
 *
 * The items must already be sorted in the desired order. This function:
 * 1. Finds the cursor position (if cursor is provided)
 * 2. Slices items starting after the cursor position
 * 3. Returns a PaginatedResult with the sliced items and metadata
 *
 * @param items - Pre-sorted, pre-filtered items
 * @param limit - Page size
 * @param cursor - Decoded cursor from the previous page (or null for first page)
 * @param getId - Extract the ID from an item (for cursor encoding)
 * @param getTimestamp - Extract the timestamp from an item (for cursor encoding)
 * @param getSortValue - Extract the primary sort value (e.g. priority) for cursor encoding
 * @param ascending - If true, items are sorted ascending (lower values first). Default: false (DESC).
 * @dep callers: searchChannel (core/intelligence/flux-team/blackboard.ts), searchScratchpad (core/intelligence/flux-team/blackboard.ts), searchToolLog (core/intelligence/flux-team/blackboard.ts), searchArtifacts (core/intelligence/flux-team/blackboard.ts), searchPlan (core/intelligence/flux-team/blackboard.ts) [+1]
 * @dep calls: findCursorPosition, encodeCursor
 * @dep module: Flux-team
 * @dep risk: MEDIUM | 6 callers, 0 flows, 1 module
 */
export function paginate<T>(
  items: T[],
  limit: number,
  cursor: SearchCursor | null,
  getId: (item: T) => string,
  getTimestamp: (item: T) => number,
  getSortValue?: (item: T) => number | undefined,
  ascending = false,
): PaginatedResult<T> {
  const total = items.length

  // Find cursor position
  let startIndex = 0
  if (cursor) {
    const cursorIndex = items.findIndex(item => getId(item) === cursor.id)
    if (cursorIndex >= 0) {
      startIndex = cursorIndex + 1
    } else {
      // Cursor item was evicted/deleted — find position by sort fields
      startIndex = findCursorPosition(items, cursor, getTimestamp, getSortValue, ascending)
    }
  }

  // Slice
  const pageItems = items.slice(startIndex, startIndex + limit)
  const hasMore = startIndex + limit < total

  // Build next cursor from last item
  let nextCursor: string | undefined
  if (hasMore && pageItems.length > 0) {
    const lastItem = pageItems[pageItems.length - 1]
    const cursorObj: SearchCursor = {
      ts: getTimestamp(lastItem),
      id: getId(lastItem),
    }
    const sv = getSortValue?.(lastItem)
    if (sv !== undefined) {
      cursorObj.sortValue = sv
    }
    nextCursor = encodeCursor(cursorObj)
  }

  return {
    items: pageItems,
    total,
    hasMore,
    cursor: nextCursor,
    pageSize: pageItems.length,
  }
}

/**
 * Find the logical position for a cursor whose item has been evicted.
 * Uses the cursor's sort fields to find where it would have been.
 *
 * When descending: finds first item with lesser sort values (item is "after" cursor in DESC order).
 * When ascending: finds first item with greater sort values (item is "after" cursor in ASC order).
 */
function findCursorPosition<T>(
  items: T[],
  cursor: SearchCursor,
  getTimestamp: (item: T) => number,
  getSortValue?: (item: T) => number | undefined,
  ascending = false,
): number {
  for (let i = 0; i < items.length; i++) {
    const itemTs = getTimestamp(items[i])
    const itemSv = getSortValue?.(items[i])

    if (cursor.sortValue !== undefined && itemSv !== undefined) {
      // Composite sort
      if (ascending) {
        if (itemSv > cursor.sortValue) return i
        if (itemSv === cursor.sortValue && itemTs > cursor.ts) return i
      } else {
        if (itemSv < cursor.sortValue) return i
        if (itemSv === cursor.sortValue && itemTs < cursor.ts) return i
      }
    } else {
      // Simple sort
      if (ascending) {
        if (itemTs > cursor.ts) return i
      } else {
        if (itemTs < cursor.ts) return i
      }
    }
  }
  // Cursor is beyond all items
  return items.length
}


/**
 * Apply common BaseSearchOptions filters to determine if an item passes.
 * Board-specific filters are handled by individual search methods.
 * @dep callers: searchChannel (core/intelligence/flux-team/blackboard.ts), searchScratchpad (core/intelligence/flux-team/blackboard.ts), searchToolLog (core/intelligence/flux-team/blackboard.ts), searchArtifacts (core/intelligence/flux-team/blackboard.ts), searchPlan (core/intelligence/flux-team/blackboard.ts) [+1]
 * @dep flows: SearchAll → PassesBaseFilters (3/3)
 * @dep module: Flux-team
 * @dep risk: MEDIUM | 6 callers, 1 flow, 1 module
 */
export function passesBaseFilters(
  opts: BaseSearchOptions,
  author?: string,
  timestamp?: number,
): boolean {
  if (opts.author && author !== opts.author) return false
  if (opts.since && timestamp !== undefined && timestamp < opts.since) return false
  if (opts.until && timestamp !== undefined && timestamp > opts.until) return false
  return true
}
