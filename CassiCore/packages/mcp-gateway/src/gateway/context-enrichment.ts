#!/usr/bin/env node
/**
 * context-enrichment.ts — Shared context-fetching and formatting module
 *
 * Extracts the context enrichment logic used by `cassi_do` (and now `cassi_enrich`)
 * into a reusable module. Fetches memories, archive entries, and session index
 * results in parallel, then formats them into a markdown context block.
 */

import { fetchWithTimeout } from './helpers.js';

// ─── Constants ────────────────────────────────────────────────────────────────

/** Timeout for each individual context fetch (memory, archive, index). */
export const CONTEXT_FETCH_TIMEOUT_MS = 5_000;

/**
 * Maximum characters to display for a single session index entry.
 * Content beyond this is windowed to the region around the FTS match.
 */
export const MAX_INDEX_DISPLAY_CHARS = 800;

// ─── Types ────────────────────────────────────────────────────────────────────

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

// ─── Context Fetchers ─────────────────────────────────────────────────────────

export async function fetchMemory(
  baseUrl: string,
  query: string,
  limit: number
): Promise<unknown[]> {
  const params = new URLSearchParams({ query, limit: String(limit) });
  const res = await fetchWithTimeout(`${baseUrl}/memory/search?${params}`, {
    timeoutMs: CONTEXT_FETCH_TIMEOUT_MS,
  });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : ((data as any)?.results ?? []);
}

export async function fetchArchive(
  baseUrl: string,
  query: string,
  limit: number
): Promise<unknown[]> {
  const res = await fetchWithTimeout(`${baseUrl}/memory/archives/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit, sortBy: 'relevance' }),
    timeoutMs: CONTEXT_FETCH_TIMEOUT_MS,
  });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : ((data as any)?.results ?? []);
}

export async function fetchSessionIndex(
  baseUrl: string,
  query: string,
  limit: number
): Promise<unknown[]> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  const res = await fetchWithTimeout(`${baseUrl}/memory/index/search?${params}`, {
    timeoutMs: CONTEXT_FETCH_TIMEOUT_MS,
  });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

// ─── Windowing Helper ─────────────────────────────────────────────────────────

/**
 * Extract a display window from content, centered on the FTS match offset.
 * When content fits within MAX_INDEX_DISPLAY_CHARS it is returned in full.
 * Otherwise a window is sliced around the match, with leading/trailing ellipses
 * and a note indicating how much was omitted.
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

// ─── Content Truncation ───────────────────────────────────────────────────────

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

// ─── Formatters ───────────────────────────────────────────────────────────────

export function formatDate(ts: number | string | Date | undefined): string {
  if (!ts) return '';
  try {
    const d = ts instanceof Date ? ts : new Date(typeof ts === 'string' ? ts : (ts as number));
    return d.toLocaleString();
  } catch {
    return '';
  }
}

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

// ─── Main Context Assembly ────────────────────────────────────────────────────

/**
 * Fetch context from all three sources (memory, archive, session index) in
 * parallel and format into a markdown context block.
 *
 * This is the shared core used by both `cassi_do` and `cassi_enrich`.
 *
 * @param baseUrl   CassiCore admin API base URL
 * @param query     The search query (user message, tool context, etc.)
 * @param limits    Per-source result limits
 * @returns Formatted markdown block and metadata
 */
export async function fetchAndFormatContext(
  baseUrl: string,
  query: string,
  limits: ContextLimits
): Promise<ContextEnrichmentResult> {
  const { memoryLimit, archiveLimit, indexLimit } = limits;

  const [memoriesSettled, archiveSettled, indexSettled] = await Promise.allSettled([
    memoryLimit > 0 ? fetchMemory(baseUrl, query, memoryLimit) : Promise.resolve([]),
    archiveLimit > 0 ? fetchArchive(baseUrl, query, archiveLimit) : Promise.resolve([]),
    indexLimit > 0 ? fetchSessionIndex(baseUrl, query, indexLimit) : Promise.resolve([]),
  ]);

  const memories: unknown[] =
    memoriesSettled.status === 'fulfilled' ? memoriesSettled.value : [];
  const archiveEntries: unknown[] =
    archiveSettled.status === 'fulfilled' ? archiveSettled.value : [];
  const indexEntries: unknown[] =
    indexSettled.status === 'fulfilled' ? indexSettled.value : [];

  const hasMemories = memories.length > 0;
  const hasArchive = archiveEntries.length > 0;
  const hasIndex = indexEntries.length > 0;
  const hasContext = hasMemories || hasArchive || hasIndex;

  if (!hasContext) {
    return {
      markdown: '',
      hasContext: false,
      counts: { memory: 0, archive: 0, index: 0 },
    };
  }

  const lines: string[] = [];

  lines.push('## Cassi Context');
  lines.push(`> Auto-enriched for: \`${query}\``);
  lines.push('');

  if (hasMemories) {
    lines.push(
      `### From Memory (${memories.length} result${memories.length === 1 ? '' : 's'})`
    );
    lines.push('');
    for (const [i, m] of memories.entries()) {
      lines.push(formatMemoryEntry(m, i));
      lines.push('');
    }
  }

  if (hasArchive) {
    lines.push(
      `### From Archive (${archiveEntries.length} result${archiveEntries.length === 1 ? '' : 's'})`
    );
    lines.push('');
    for (const [i, e] of archiveEntries.entries()) {
      lines.push(formatArchiveEntry(e, i));
      lines.push('');
    }
  }

  if (hasIndex) {
    lines.push(
      `### From Session History (${indexEntries.length} result${indexEntries.length === 1 ? '' : 's'})`
    );
    lines.push('');
    for (const [i, e] of indexEntries.entries()) {
      lines.push(formatIndexEntry(e, i));
      lines.push('');
    }
  }

  return {
    markdown: lines.join('\n'),
    hasContext: true,
    counts: {
      memory: memories.length,
      archive: archiveEntries.length,
      index: indexEntries.length,
    },
  };
}
