#!/usr/bin/env node
/**
 * context-enrichment.ts — Shared context-fetching and formatting module
 *
 * Used exclusively by `cassi_enrich`. The enrichment pipeline now runs queries
 * through the Query Intelligence layer (query-intelligence.ts) before searching:
 *
 *   1. Normalize + extract entities   — synchronous
 *   2. Fetch archive metadata          — cached, fast
 *   3. Build query variants            — exact + entity + expanded
 *   4. Multi-variant parallel search   — 6–9 searches, deduplicated
 *   5. Cross-source merge + rank       — adaptive weights, diversity bonus
 *   6. Top Relevant section            — best 5 across all sources
 *   7. Per-source full lists           — memory / archive / session history
 *   8. Empty recovery                  — fallback searches + term suggestions
 */

import { fetchWithTimeout } from './helpers.js';
import {
  normalizeQuery,
  extractEntities,
  extractKeyTerms,
  getArchiveMetadata,
  buildQueryVariants,
  searchMultiVariant,
  mergeAndRank,
  recoverFromEmpty,
  formatTopRelevantEntry,
  scoreCRAGQuality,
  MIN_TOP_RELEVANT_SCORE,
  MIN_SOURCE_DISPLAY_SCORE,
  type RankedSearchResult,
  type CRAGAssessment,
} from './query-intelligence.js';


/** Timeout for each individual context fetch (memory, archive, index). */
export const CONTEXT_FETCH_TIMEOUT_MS = 5_000;

/**
 * Maximum characters to display for a single session index entry.
 * Content beyond this is windowed to the region around the FTS match.
 */
export const MAX_INDEX_DISPLAY_CHARS = 800;


/** Limits for each context source. */
export interface ContextLimits {
  memoryLimit: number;
  archiveLimit: number;
  indexLimit: number;
}

/** Result of context fetching and formatting. */
export interface ContextEnrichmentResult {
  /** Formatted markdown block (empty string if no context found). */
  markdown: string;
  /** Whether any context was found from any source. */
  hasContext: boolean;
  /** Number of results per source. */
  counts: {
    memory: number;
    archive: number;
    index: number;
  };
}


/**
 * Fetches memory entries matching a query.
 * @param baseUrl - CassiCore admin API base URL
 * @param query - Search query string
 * @param limit - Maximum number of results to return
 * @returns Array of memory search results
 */
export async function fetchMemory(
  baseUrl: string,
  query: string,
  limit: number
): Promise<unknown[]> {
  try {
    const params = new URLSearchParams({ query, limit: String(limit) });
    const res = await fetchWithTimeout(`${baseUrl}/memory/search?${params}`, {
      timeoutMs: CONTEXT_FETCH_TIMEOUT_MS,
    });
    if (!res.ok) return [];
    const data = await res.json().catch(() => null);
    if (!data) return [];
    return Array.isArray(data) ? data : ((data as any)?.results ?? []);
  } catch {
    return [];
  }
}

/**
 * Fetches archive entries matching a query.
 * @param baseUrl - CassiCore admin API base URL
 * @param query - Search query string
 * @param limit - Maximum number of results to return
 * @returns Array of archive search results
 */
export async function fetchArchive(
  baseUrl: string,
  query: string,
  limit: number
): Promise<unknown[]> {
  try {
    const res = await fetchWithTimeout(`${baseUrl}/memory/archives/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit, sortBy: 'relevance' }),
      timeoutMs: CONTEXT_FETCH_TIMEOUT_MS,
    });
    if (!res.ok) return [];
    const data = await res.json().catch(() => null);
    if (!data) return [];
    return Array.isArray(data) ? data : ((data as any)?.results ?? []);
  } catch {
    return [];
  }
}

/**
 * Fetches session index entries matching a query.
 * @param baseUrl - CassiCore admin API base URL
 * @param query - Search query string
 * @param limit - Maximum number of results to return
 * @returns Array of session index search results
 */
export async function fetchSessionIndex(
  baseUrl: string,
  query: string,
  limit: number
): Promise<unknown[]> {
  try {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    const res = await fetchWithTimeout(`${baseUrl}/memory/index/search?${params}`, {
      timeoutMs: CONTEXT_FETCH_TIMEOUT_MS,
    });
    if (!res.ok) return [];
    const data = await res.json().catch(() => null);
    if (!data) return [];
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}


/**
 * Extract a display window from content, centered on the FTS match offset.
 * When content fits within MAX_INDEX_DISPLAY_CHARS it is returned in full.
 * Otherwise a window is sliced around the match, with leading/trailing ellipses
 * and a note indicating how much was omitted.
 * @param content - Full content string to window
 * @param matchOffset - Optional offset of the FTS match
 * @param resolveRef - Reference ID for full content resolution hint
 * @returns Windowed content string with ellipses and resolution hint
 */
export function centeredWindow(
  content: string,
  matchOffset: number | undefined,
  resolveRef: string
): string {
  if (content.length <= MAX_INDEX_DISPLAY_CHARS) return content;

  const pivot = matchOffset ?? 0;
  const half = MAX_INDEX_DISPLAY_CHARS / 2;

  // Slide window so it stays within bounds while keeping pivot near centre
  let start = Math.max(0, pivot - half);
  const end = Math.min(content.length, start + MAX_INDEX_DISPLAY_CHARS);
  start = Math.max(0, end - MAX_INDEX_DISPLAY_CHARS);

  const remaining = content.length - end;
  const prefix = start > 0 ? '…\n' : '';
  const suffix =
    remaining > 0
      ? `\n…[${remaining} chars not shown — \`cassi_resolve_ref("${resolveRef}")\` for full content]`
      : '';

  return prefix + content.slice(start, end) + suffix;
}


/**
 * Maximum characters for memory/archive entry content.
 * Matches MAX_INDEX_DISPLAY_CHARS for consistency across all context sources.
 */
export const MAX_ENTRY_DISPLAY_CHARS = 800;

/**
 * Smart head+tail truncation that preserves the most relevant parts of content.
 *
 * For conversation-style content, the beginning typically contains the question/topic
 * and the end contains the conclusion/answer — both are high-signal. The middle is
 * usually verbose reasoning or intermediate steps that are lower-value as context.
 *
 * If content fits within maxChars, it is returned unchanged.
 * Otherwise, the first ~40% and last ~40% are kept, with a brief omission marker
 * in between showing how much was skipped.
 * @param content - Content string to truncate
 * @param maxChars - Maximum characters to keep (default: MAX_ENTRY_DISPLAY_CHARS)
 * @returns Smart-truncated content string
 * @dep callers: formatArchiveEntry (mcp/gateway/context-enrichment.ts), formatMemoryEntry (mcp/gateway/context-enrichment.ts)
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function smartTruncate(content: string, maxChars: number = MAX_ENTRY_DISPLAY_CHARS): string {
  if (content.length <= maxChars) return content;

  // 40/40 split — head gets slightly more since topic/question comes first
  const headChars = Math.floor(maxChars * 0.4);
  const tailChars = Math.floor(maxChars * 0.4);
  const omitted = content.length - headChars - tailChars;

  // Try to break at line boundaries to avoid mid-sentence cuts
  let headEnd = headChars;
  const headNewline = content.lastIndexOf('\n', headChars);
  if (headNewline > headChars * 0.6) headEnd = headNewline;

  let tailStart = content.length - tailChars;
  const tailNewline = content.indexOf('\n', tailStart);
  if (tailNewline !== -1 && tailNewline < tailStart + tailChars * 0.4) tailStart = tailNewline + 1;

  const head = content.slice(0, headEnd).trimEnd();
  const tail = content.slice(tailStart).trimStart();

  return `${head}\n\n[...${omitted} chars omitted...]\n\n${tail}`;
}


/**
 * Formats a timestamp into a human-readable string.
 * @param ts - Timestamp value (number, string, Date, or undefined)
 * @returns Formatted date string or empty string if invalid
 * @dep callers: formatIndexEntry (mcp/gateway/context-enrichment.ts), formatArchiveEntry (mcp/gateway/context-enrichment.ts), formatMemoryEntry (mcp/gateway/context-enrichment.ts)
 * @dep module: Gateway
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */
export function formatDate(ts: number | string | Date | undefined): string {
  if (!ts) return '';
  try {
    const d = ts instanceof Date ? ts : new Date(typeof ts === 'string' ? ts : (ts as number));
    return d.toLocaleString();
  } catch {
    return '';
  }
}

/**
 * Formats a memory search result entry for display.
 * @param raw - Raw memory search result (entry with score or raw entry)
 * @param index - Zero-based index for numbering
 * @returns Formatted markdown string for the memory entry
 */
export function formatMemoryEntry(raw: unknown, index: number): string {
  // Memory search returns { entry: MemoryEntry, score: number }
  // or sometimes raw MemoryEntry shapes — handle both.
  const result = raw as any;
  const entry = result?.entry ?? result;
  const score: number = result?.score ?? 0;
  const date = formatDate(entry?.createdAt);
  const type: string = entry?.type ?? 'memory';
  const relevance = `${(score * 100).toFixed(0)}%`;

  const header = `#### ${index + 1}. [${type}] ${date} (relevance: ${relevance})`;
  const rawBody: string = entry?.content ?? JSON.stringify(entry);
  const body = smartTruncate(rawBody);

  return [header, body].join('\n');
}

/**
 * Format an archive search result with type-specific rendering.
 * Content is truncated via smartTruncate to keep context concise.
 * Thinking blocks are omitted — they are internal LLM reasoning
 * and not useful as context signals for a new conversation.
 * @param raw - Raw archive search result (entry with score or raw entry)
 * @param index - Zero-based index for numbering
 * @returns Formatted markdown string for the archive entry
 */
export function formatArchiveEntry(raw: unknown, index: number): string {
  // Archive search returns ArchiveSearchResult: { entry, score, matchType, highlights? }
  const result = raw as any;
  const entry = result?.entry ?? result;
  const score: number = result?.score ?? 0;
  const highlights: string[] | undefined = result?.highlights;

  const date = formatDate(entry?.timestamp);
  const type: string = entry?.type ?? 'entry';
  const source: string | undefined = entry?.source;
  const relevance = `${(score * 100).toFixed(0)}%`;

  const headerParts = [`#### ${index + 1}. [${type}] ${date} (relevance: ${relevance})`];
  if (source) headerParts.push(`· source: ${source}`);
  const header = headerParts.join(' ');

  const lines: string[] = [header];

  const content: string = entry?.content ?? '';
  const meta = entry?.metadata ?? {};

  switch (type) {
    case 'conversation': {
      // content is "USER: ...\n\nASSISTANT: ..."
      // Thinking blocks omitted — internal reasoning, not useful as context.
      lines.push(smartTruncate(content));
      break;
    }

    case 'thinking': {
      // For thinking-type entries, the thinking field IS the value.
      // Show a brief summary rather than the full reasoning chain.
      const thinking: string | undefined = entry?.thinking;
      if (thinking) {
        lines.push(smartTruncate(thinking));
      } else {
        lines.push(smartTruncate(content));
      }
      break;
    }

    case 'insight': {
      const level: string = meta?.level ?? 'ponder';
      lines.push(`**Level:** ${level}`);
      lines.push(smartTruncate(content));
      break;
    }

    case 'dialectic_yang':
    case 'dialectic_yin':
    case 'dialectic_serenity': {
      const branch = (meta?.dialecticBranch as string) ?? type.replace('dialectic_', '');
      lines.push(`**Branch:** ${branch}`);
      lines.push(smartTruncate(content));
      break;
    }

    case 'event': {
      const eventType: string = (meta?.eventType as string) ?? 'unknown';
      lines.push(`**Event type:** ${eventType}`);
      lines.push(smartTruncate(content));
      break;
    }

    case 'tool_call': {
      const toolName: string = (meta?.toolName as string) ?? 'unknown';
      const isError: boolean = !!(meta?.isError);
      const durationMs: number | undefined = meta?.durationMs as number | undefined;
      const statusLabel = isError ? ' **(ERROR)**' : '';
      const durLabel = durationMs != null ? ` · ${durationMs}ms` : '';
      lines.push(`**Tool:** \`${toolName}\`${statusLabel}${durLabel}`);
      lines.push(smartTruncate(content));
      break;
    }

    case 'pattern': {
      const confidence: number | undefined = meta?.confidence as number | undefined;
      const confLabel =
        confidence != null ? ` (confidence: ${(confidence * 100).toFixed(0)}%)` : '';
      lines.push(`**Pattern**${confLabel}`);
      lines.push(smartTruncate(content));
      break;
    }

    case 'reflection':
    case 'summary':
    default: {
      lines.push(smartTruncate(content));
      break;
    }
  }

  // Analysis summary as a footnote if it adds information beyond content
  const analysisSummary: string | undefined = entry?.analysis?.summary;
  if (analysisSummary && analysisSummary !== content) {
    lines.push('');
    lines.push(`*Summary: ${analysisSummary}*`);
  }

  // Highlighted match terms
  if (highlights && highlights.length > 0) {
    lines.push('');
    lines.push(`*Matched: ${highlights.join(', ')}*`);
  }

  return lines.join('\n');
}

/**
 * Format a session index search result (IndexSearchResult shape).
 * Handles all three block types: text, tool_use, tool_result.
 * Long content is windowed to the FTS match region via centeredWindow().
 * @param raw - Raw session index search result
 * @param index - Zero-based index for numbering
 * @returns Formatted markdown string for the index entry
 */
export function formatIndexEntry(raw: unknown, index: number): string {
  // IndexSearchResult: { entry: IndexEntry, rank, matchOffset? }
  const result = raw as any;
  const entry = result?.entry ?? result;
  const matchOffset: number | undefined = result?.matchOffset;

  const ref: string = entry?.ref ?? '';
  // Message-level ref for expand hint: strip .P{n} suffix so it resolves the whole message
  const msgRef = ref.replace(/\.P\d+$/, '');

  const role: string = entry?.role ?? 'unknown';
  const blockType: string = entry?.blockType ?? entry?.block_type ?? 'text';
  const meta = entry?.meta ?? {};
  const content: string = entry?.content ?? '';
  const date = formatDate(entry?.timestamp ?? entry?.createdAt);

  // Build tag badges from meta.tags (populated by classifyParagraph)
  const tags: string[] = Array.isArray(meta?.tags) ? (meta.tags as string[]) : [];
  // Always include the block type as a visual badge
  const allBadges = [blockType, ...tags].map(t => `\`${t}\``).join(' ');

  const headerParts = [`#### ${index + 1}. [${ref}] — ${role} · ${date}`];
  if (allBadges) headerParts.push(' ', allBadges);
  const lines: string[] = [headerParts.join('')];

  switch (blockType) {
    case 'tool_use': {
      // meta contains { name, id }
      const toolName: string = (meta?.name as string) ?? 'unknown';
      lines.push(`**Tool call:** \`${toolName}\``);
      // content is the JSON-serialised input — usually compact
      lines.push(centeredWindow(content, matchOffset, msgRef));
      break;
    }

    case 'tool_result': {
      // meta contains { tool_use_id, is_error }
      const isError: boolean = !!(meta?.is_error);
      const statusMark = isError ? '\u2717' : '\u2713';
      lines.push(`**Tool result** ${statusMark}`);
      lines.push(centeredWindow(content, matchOffset, msgRef));
      break;
    }

    case 'text':
    default: {
      // Text paragraphs are bounded by \n\n so rarely exceed MAX_INDEX_DISPLAY_CHARS,
      // but apply windowing defensively for edge cases.
      lines.push(centeredWindow(content, matchOffset, msgRef));
      break;
    }
  }

  lines.push('');
  lines.push(`*Expand message context: \`cassi_resolve_ref("${msgRef}")\`*`);

  return lines.join('\n');
}


/**
 * Fetch context from all sources through the Query Intelligence pipeline and
 * format into a markdown block for `cassi_enrich`.
 *
 * Pipeline:
 *   normalize → extract entities → cache metadata → build variants →
 *   multi-variant search (parallel) → merge+rank → Top Relevant + per-source sections
 *   → empty recovery if no results
 *
 * @param baseUrl CassiCore admin API base URL
 * @param query The search query (user message, topic, etc.)
 * @param limits Per-source result limits
 * @returns Context enrichment result with markdown and counts
 * @dep callers: executeEnrichTool (mcp/gateway/do-tool.ts)
 * @dep calls: normalizeQuery, extractKeyTerms, extractEntities, getArchiveMetadata, buildQueryVariants [+7]
 * @dep flows: FetchAndFormatContext → Json (1/4)
 * @dep module: Gateway
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export async function fetchAndFormatContext(
  baseUrl: string,
  query: string,
  limits: ContextLimits,
): Promise<ContextEnrichmentResult> {
  const { memoryLimit, archiveLimit, indexLimit } = limits;

  const normalized = normalizeQuery(query);
  const entities   = extractEntities(normalized);
  const keyTerms   = extractKeyTerms(normalized);

  const metadata = await getArchiveMetadata(baseUrl).catch(() => null);

  const variants = buildQueryVariants(normalized, entities, metadata);

  const [memSettled, arcSettled, idxSettled] = await Promise.allSettled([
    memoryLimit  > 0 ? searchMultiVariant('memory',  baseUrl, variants, memoryLimit)  : Promise.resolve([]),
    archiveLimit > 0 ? searchMultiVariant('archive', baseUrl, variants, archiveLimit) : Promise.resolve([]),
    indexLimit   > 0 ? searchMultiVariant('index',   baseUrl, variants, indexLimit)   : Promise.resolve([]),
  ]);

  const memoriesAll:  RankedSearchResult[] = memSettled.status  === 'fulfilled' ? memSettled.value  : [];
  const archivesAll:  RankedSearchResult[] = arcSettled.status  === 'fulfilled' ? arcSettled.value  : [];
  const indexAll:     RankedSearchResult[] = idxSettled.status  === 'fulfilled' ? idxSettled.value  : [];

  const hasResults = memoriesAll.length > 0 || archivesAll.length > 0 || indexAll.length > 0;

  if (!hasResults) {
    // WHY: recoverFromEmpty does additional fetch calls that could fail — wrap
    // so a fallback failure never kills the entire enrichment.
    let fallback: { results: unknown[]; suggestedTerms: string[]; usedBroad?: boolean };
    try {
      fallback = await recoverFromEmpty(baseUrl, normalized, keyTerms, metadata);
    } catch {
      fallback = { results: [], suggestedTerms: [] };
    }

    if (fallback.results.length === 0 && fallback.suggestedTerms.length === 0) {
      return { markdown: '', hasContext: false, counts: { memory: 0, archive: 0, index: 0 } };
    }

    // Format fallback output
    const lines: string[] = [];
    lines.push('## Cassi Context');
    lines.push(`> No exact matches found for: \`${query}\``);
    lines.push('');

    if (fallback.results.length > 0) {
      const label = fallback.usedBroad ? 'Broadly Related' : 'Recent Context';
      lines.push(`### ${label} (${fallback.results.length} result${fallback.results.length === 1 ? '' : 's'})`);
      lines.push('');
      for (const [i, r] of fallback.results.entries()) {
        // Route to the appropriate formatter based on entry shape
        const entry = (r as any)?.entry ?? r;
        if (entry?.type && ['conversation','tool_call','insight','pattern','event','reflection'].includes(entry.type)) {
          lines.push(formatArchiveEntry(r, i));
        } else {
          lines.push(formatMemoryEntry(r, i));
        }
        lines.push('');
      }
    }

    if (fallback.suggestedTerms.length > 0) {
      lines.push('### Suggested Searches');
      lines.push('');
      lines.push(`Try: ${fallback.suggestedTerms.map(t => `\`${t}\``).join(', ')}`);
      lines.push('');
    }

    const metaNote = metadata
      ? `*Search auto-expanded from ${metadata.tags.length} tags, ${metadata.entities.length} entities, ${metadata.topics.length} topics.*`
      : '*Could not load archive metadata for suggestions.*';
    lines.push(metaNote);

    return {
      markdown: lines.join('\n'),
      hasContext: true,
      counts: { memory: 0, archive: fallback.results.length, index: 0 },
    };
  }

  const allResults: RankedSearchResult[] = [...memoriesAll, ...archivesAll, ...indexAll];
  const topRelevant = mergeAndRank(allResults, normalized, 5);

  // CRAG quality scoring — evaluate retrieval quality and trigger fallback if needed
  const cragAssessment = scoreCRAGQuality(topRelevant, normalized);

  // Filter out 'incorrect' results and results below the relevance floor
  const filteredTopRelevant = topRelevant.filter(
    r => r.cragAction !== 'incorrect' && r.finalScore >= MIN_TOP_RELEVANT_SCORE
  );

  // If CRAG assessment triggers fallback (most results are low quality),
  // attempt recovery with broader search terms
  let cragFallback: { results: unknown[]; suggestedTerms: string[] } | null = null;
  if (cragAssessment.fallbackTriggered && filteredTopRelevant.length < 2) {
    try {
      cragFallback = await recoverFromEmpty(baseUrl, normalized, keyTerms, metadata);
    } catch {
      // WHY: Fallback is best-effort — don't let it fail the entire enrichment
    }
  }

  // Apply final limits with relevance floor — drop results whose raw backend
  // score is below the display threshold before slicing to requested limits.
  const memories       = memoriesAll.filter(m => m.rawScore >= MIN_SOURCE_DISPLAY_SCORE).slice(0, memoryLimit);
  const archiveEntries = archivesAll.filter(e => e.rawScore >= MIN_SOURCE_DISPLAY_SCORE).slice(0, archiveLimit);
  const indexEntries   = indexAll.slice(0, indexLimit);

  const lines: string[] = [];
  lines.push('## Cassi Context');
  lines.push(`> Auto-enriched for: \`${query}\``);
  lines.push('');

  // Top Relevant — cross-source merged section
  if (filteredTopRelevant.length > 0) {
    lines.push('### Top Relevant (cross-source)');
    if (cragAssessment.avgQuality < 0.35) {
      lines.push('_Quality: low — results may not fully match your query_');
    }
    lines.push('');
    for (const [i, r] of filteredTopRelevant.entries()) {
      lines.push(formatTopRelevantEntry(r, i));
      lines.push('');
    }
    lines.push('---');
    lines.push('');
  }

  // CRAG fallback results (when primary results were low quality)
  if (cragFallback && cragFallback.results.length > 0) {
    lines.push('### Broadly Related (CRAG fallback)');
    lines.push('');
    for (const [i, r] of cragFallback.results.slice(0, 3).entries()) {
      const raw = r as any;
      const content = raw?.content || raw?.entry?.content || String(r);
      const preview = content.length > 200 ? content.slice(0, 200) + '...' : content;
      lines.push(`${i + 1}. ${preview}`);
      lines.push('');
    }
    if (cragFallback.suggestedTerms.length > 0) {
      lines.push(`**Suggested searches:** ${cragFallback.suggestedTerms.join(', ')}`);
      lines.push('');
    }
    lines.push('---');
    lines.push('');
  }

  // Per-source full lists
  if (memories.length > 0) {
    lines.push(`### From Memory (${memories.length} result${memories.length === 1 ? '' : 's'})`);
    lines.push('');
    for (const [i, m] of memories.entries()) {
      lines.push(formatMemoryEntry(m.raw, i));
      lines.push('');
    }
  }

  if (archiveEntries.length > 0) {
    lines.push(`### From Archive (${archiveEntries.length} result${archiveEntries.length === 1 ? '' : 's'})`);
    lines.push('');
    for (const [i, e] of archiveEntries.entries()) {
      lines.push(formatArchiveEntry(e.raw, i));
      lines.push('');
    }
  }

  if (indexEntries.length > 0) {
    lines.push(`### From Session History (${indexEntries.length} result${indexEntries.length === 1 ? '' : 's'})`);
    lines.push('');
    for (const [i, e] of indexEntries.entries()) {
      lines.push(formatIndexEntry(e.raw, i));
      lines.push('');
    }
  }

  return {
    markdown: lines.join('\n'),
    hasContext: true,
    counts: {
      memory:  memories.length,
      archive: archiveEntries.length,
      index:   indexEntries.length,
    },
  };
}

/**
 * Proactive result shape returned by the admin API.
 */
export interface ProactiveResult {
  intentType: string;
  title: string;
  content: string;
  source: string;
  relevance: number;
  gatheredAt: number;
  sessionId: string;
}

/**
 * Fetch proactive results from the admin API endpoint.
 * Calls GET /proactive/:sessionId/results?wait_ms=5000 (implemented by Helix 2).
 *
 * @param baseUrl CassiCore admin API base URL
 * @param sessionId Session ID to fetch results for
 * @param opts Optional: waitMs (max blocking wait), maxAgeMs (max result age)
 * @returns Array of proactive results
 */
export async function fetchProactiveResults(
  baseUrl: string,
  sessionId: string,
  opts?: { waitMs?: number; maxAgeMs?: number }
): Promise<ProactiveResult[]> {
  const params = new URLSearchParams();
  if (opts?.waitMs !== undefined) params.set('wait_ms', String(opts.waitMs));
  if (opts?.maxAgeMs !== undefined) params.set('max_age_ms', String(opts.maxAgeMs));

  const url = `${baseUrl}/proactive/${sessionId}/results?${params.toString()}`;

  try {
    const res = await fetchWithTimeout(url, { timeoutMs: 10_000 });
    if (!res.ok) {
      // Endpoint may not be available yet (Helix 2 not deployed)
      return [];
    }
    const data = await res.json();
    return Array.isArray(data) ? data : (data?.results ?? []);
  } catch (err) {
    // Silently fail — proactive results are optional enhancement
    return [];
  }
}

/**
 * Format proactive results into markdown for inclusion in cassi_enrich output.
 *
 * Output format:
 * ### Proactive Intelligence (N results from background analysis)
 *
 * #### 1. [code_intent] Callers of validateSession
 * Found via GitNexus context — 4 callers across 3 files...
 * *Source: gitnexus_context | Relevance: 92%*
 *
 * @param results Array of proactive results
 * @returns Formatted markdown string
 */
export function formatProactiveResults(results: ProactiveResult[]): string {
  if (results.length === 0) return '';

  const lines: string[] = [];
  lines.push(`### Proactive Intelligence (${results.length} result${results.length === 1 ? '' : 's'} from background analysis)`);
  lines.push('');

  for (const [i, result] of results.entries()) {
    lines.push(`#### ${i + 1}. [${result.intentType}] ${result.title}`);
    lines.push(result.content);
    lines.push(`*Source: ${result.source} | Relevance: ${(result.relevance * 100).toFixed(0)}%*`);
    lines.push('');
  }

  return lines.join('\n');
}
