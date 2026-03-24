/**
 * Blackboard Search & Pagination Types
 *
 * Provides regex-based search and cursor-based pagination across all
 * blackboard board types: channels, scratchpad, tool log, artifacts,
 * plan steps, and report sections.
 */

import type {
  BlackboardChannel,
  BlackboardEntry,
  FluxScratchpadEntry,
  FluxToolRecord,
  ArtifactEntry,
  PlanStep,
  PlanStepStatus,
  ReportSection,
  ReportSectionType,
  ReportSectionStatus,
} from './flux-team.js'

// ── Constants ──

/** Maximum allowed pattern length to mitigate ReDoS */
export const MAX_PATTERN_LENGTH = 200

/** Default page size when no limit is specified */
export const DEFAULT_SEARCH_LIMIT = 50

/** Maximum page size */
export const MAX_SEARCH_LIMIT = 500

// ── Cursor ──

/**
 * Internal cursor structure for cursor-based pagination.
 * Encodes the position of the last returned item in the sorted result set.
 *
 * For boards with composite sort keys (e.g. channels: priority DESC, timestamp DESC),
 * `sortValue` carries the primary sort dimension (priority).
 */
export interface SearchCursor {
  /** Timestamp of the last returned item (ms since epoch) */
  ts: number
  /** ID of the last returned item */
  id: string
  /** Primary sort value (e.g. priority for channels, order for plan steps) */
  sortValue?: number
}

// ── Paginated Result ──

/**
 * Generic paginated result container returned by all search methods.
 */
export interface PaginatedResult<T> {
  /** Items in this page */
  items: T[]
  /** Total matching items (before pagination) */
  total: number
  /** Whether more items exist after this page */
  hasMore: boolean
  /** Opaque cursor for the next page (undefined if last page) */
  cursor?: string
  /** Number of items in this page */
  pageSize: number
}

// ── Base Search Options ──

/**
 * Common search options shared by all board-specific search methods.
 */
export interface BaseSearchOptions {
  /** Regex pattern to match against board-specific fields (case-insensitive) */
  pattern?: string
  /** Opaque cursor from a previous result for pagination */
  cursor?: string
  /** Maximum items per page (default: DEFAULT_SEARCH_LIMIT, max: MAX_SEARCH_LIMIT) */
  limit?: number
  /** Filter by author */
  author?: string
  /** Only items created at or after this timestamp */
  since?: number
  /** Only items created at or before this timestamp */
  until?: number
}

// ── Board-Specific Search Options ──

/**
 * Search options for channel entries.
 * Pattern matches: content, author, tags (space-joined).
 */
export interface ChannelSearchOptions extends BaseSearchOptions {
  /** Specific channel to search (if omitted, searches all channels) */
  channel?: BlackboardChannel
  /** Filter by exact tag match (entry must have ALL specified tags) */
  tags?: string[]
  /** Filter by minimum priority */
  minPriority?: number
  /** Filter by maximum priority */
  maxPriority?: number
}

/**
 * Search options for scratchpad entries.
 * Pattern matches: key, value.
 */
export interface ScratchpadSearchOptions extends BaseSearchOptions {
  /** Include expired entries (default: false) */
  includeExpired?: boolean
}

/**
 * Search options for tool log records.
 * Pattern matches: tool name, nodeId.
 */
export interface ToolLogSearchOptions extends BaseSearchOptions {
  /** Filter by tool name (exact match) */
  tool?: string
  /** Filter by nodeId (exact match) */
  nodeId?: string
  /** Filter by error status */
  isError?: boolean
}

/**
 * Search options for artifact entries.
 * Pattern matches: path, author.
 */
export interface ArtifactSearchOptions extends BaseSearchOptions {
  /** Filter by operation type */
  operation?: 'created' | 'modified' | 'deleted'
}

/**
 * Search options for plan steps.
 * Pattern matches: title, description, tags (space-joined).
 */
export interface PlanSearchOptions extends BaseSearchOptions {
  /** Filter by step status */
  status?: PlanStepStatus
  /** Filter by assignee */
  assignee?: string
  /** Filter by step priority */
  priority?: 'high' | 'medium' | 'low'
}

/**
 * Search options for report sections.
 * Pattern matches: title, content, author.
 */
export interface ReportSearchOptions extends BaseSearchOptions {
  /** Filter by section type */
  type?: ReportSectionType
  /** Filter by section status */
  status?: ReportSectionStatus
}

// ── Cross-Board Search ──

/** Board types that can be searched */
export type SearchableBoard =
  | 'channel'
  | 'scratchpad'
  | 'toolLog'
  | 'artifact'
  | 'plan'
  | 'report'

/**
 * Options for cross-board unified search.
 */
export interface CrossBoardSearchOptions {
  /** Regex pattern to match (case-insensitive) */
  pattern: string
  /** Board types to search (default: all) */
  boards?: SearchableBoard[]
  /** Maximum items per board (default: DEFAULT_SEARCH_LIMIT) */
  limitPerBoard?: number
  /** Opaque cursor for pagination (per-board cursors encoded together) */
  cursor?: string
  /** Filter by author */
  author?: string
  /** Only items created at or after this timestamp */
  since?: number
  /** Only items created at or before this timestamp */
  until?: number
}

/**
 * A single search result from cross-board search, tagged with its board type.
 */
export type CrossBoardResultItem =
  | { board: 'channel'; channel: BlackboardChannel; item: BlackboardEntry; matchedFields: string[] }
  | { board: 'scratchpad'; item: FluxScratchpadEntry; matchedFields: string[] }
  | { board: 'toolLog'; item: FluxToolRecord; matchedFields: string[] }
  | { board: 'artifact'; item: ArtifactEntry; matchedFields: string[] }
  | { board: 'plan'; item: PlanStep; matchedFields: string[] }
  | { board: 'report'; item: ReportSection; matchedFields: string[] }

/**
 * Per-board result in the cross-board search response.
 */
export interface BoardSearchResult<T> {
  /** Items matching in this board */
  items: T[]
  /** Total matching items in this board */
  total: number
  /** Whether more items exist in this board */
  hasMore: boolean
  /** Cursor for paginating this specific board */
  cursor?: string
}

/**
 * Cross-board search response.
 * Results grouped by board with per-board pagination.
 */
export interface CrossBoardSearchResult {
  /** Grouped results by board type */
  boards: {
    channel?: BoardSearchResult<CrossBoardResultItem & { board: 'channel' }>
    scratchpad?: BoardSearchResult<CrossBoardResultItem & { board: 'scratchpad' }>
    toolLog?: BoardSearchResult<CrossBoardResultItem & { board: 'toolLog' }>
    artifact?: BoardSearchResult<CrossBoardResultItem & { board: 'artifact' }>
    plan?: BoardSearchResult<CrossBoardResultItem & { board: 'plan' }>
    report?: BoardSearchResult<CrossBoardResultItem & { board: 'report' }>
  }
  /** Total matches across all boards */
  totalMatches: number
  /** Boards ranked by match count (highest first) */
  rankedBoards: Array<{ board: SearchableBoard; count: number }>
  /** Composite cursor encoding all per-board cursors */
  cursor?: string
}

// ── Blackboard Watch Tool Types ──

/**
 * Time window for change tracking.
 * Used by getChangesSince() methods.
 */
export interface ChangeWindow {
  /** Start timestamp (ms since epoch) */
  since: number
  /** End timestamp (ms since epoch). Defaults to Date.now() if not specified. */
  until?: number
}

/**
 * Aggregated changes from all board types within a time window.
 */
export interface BoardChanges {
  /** New or updated channel entries, tagged with their channel */
  channels: Array<{ channel: BlackboardChannel; entry: BlackboardEntry }>
  /** Scratchpad entries created or updated in window */
  scratchpad: Array<FluxScratchpadEntry>
  /** Tool log records in window */
  toolLog: Array<FluxToolRecord>
  /** Artifact entries in window */
  artifacts: Array<ArtifactEntry>
  /** Plan steps created or updated in window, with operation type */
  plan: Array<{ step: PlanStep; operation: 'created' | 'updated' }>
  /** Report sections created, updated, or superseded in window, with operation type */
  report: Array<{ section: ReportSection; operation: 'created' | 'updated' | 'superseded' }>
}

/**
 * Input options for the bb_global_watch MCP tool.
 */
export interface BlackboardWatchOptions {
  /** Board name to watch */
  name: string
  /** Accumulation window in seconds (default: 60). Used if since/cursor not provided. */
  intervalSeconds?: number
  /** Unix timestamp (ms) to get changes since. Overrides intervalSeconds. */
  since?: number
  /** Opaque cursor from previous poll. Overrides since and intervalSeconds. */
  cursor?: string
  /** Filter which board types to include (default: all) */
  boards?: SearchableBoard[]
  /** Include full entry content or metadata only (default: true) */
  includeContent?: boolean
}

/**
 * Summary statistics for watch result.
 */
export interface WatchSummary {
  /** Total number of changes across all boards */
  totalChanges: number
  /** Count of changes by board type */
  byBoard: Record<SearchableBoard, number>
  /** Count of changes by operation type (created, updated, deleted/superseded) */
  byOperation: Record<'created' | 'updated' | 'deleted', number>
}

/**
 * Output shape for the bb_global_watch tool.
 * Contains accumulated changes over the specified time window.
 */
export interface BlackboardWatchResult {
  /** Board name that was watched */
  boardName: string
  /** Current timestamp when poll was executed */
  pollTime: number
  /** Start of the accumulation window (ms) */
  windowStart: number
  /** End of the accumulation window (ms) */
  windowEnd: number
  /** Opaque cursor for next poll (encodes windowEnd) */
  nextCursor: string
  /** Summary statistics */
  summary: WatchSummary
  /** Detailed changes by board type */
  changes: BoardChanges
}
