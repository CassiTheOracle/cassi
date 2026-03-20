#!/usr/bin/env node
/**
 * query-intelligence.ts — Query Intelligence pipeline for cassi_enrich
 *
 * Transforms a raw user query into richer search results through:
 *   1. Normalization and entity extraction   — fast, synchronous
 *   2. Dynamic query expansion               — fetches archive metadata (cached)
 *   3. Multi-variant parallel search         — 6-9 searches, deduplicated
 *   4. Cross-source merge and rank           — adaptive weights, diversity bonus
 *   5. Empty result recovery                 — fallback searches + term suggestions
 *
 * All public functions degrade gracefully — exceptions are caught and the
 * caller receives empty arrays / null, never a thrown error.
 */

import { fetchWithTimeout } from './helpers.js';
import {
  fetchMemory,
  fetchArchive,
  fetchSessionIndex,
  type ContextLimits,
} from './context-enrichment.js';


/** Structured entities parsed out of the raw query string. */
export interface ExtractedEntities {
  /** CassiCore compact session refs: S0, S1#M3, S0#M1.B0.P2 */
  sessionRefs: string[];
  /** Tool function names: bash, cassi_do, gitnexus_query, etc. */
  toolNames: string[];
  /** File/directory paths: core/intelligence/memory/, auth.ts */
  filePaths: string[];
  /** Provider identifiers: anthropic, github-copilot, kimi */
  providers: string[];
}

/** A single query variant with a relative weight and a label for debugging. */
interface QueryVariant {
  query: string;
  /** 0–1; used to scale raw search scores before merging */
  weight: number;
  label: 'exact' | 'entity' | 'expanded';
}

/** Archive metadata snapshot returned by the browse endpoint. */
interface MetadataItem {
  name: string;
  count: number;
}

interface ArchiveMetadata {
  tags:     MetadataItem[];
  entities: MetadataItem[];
  topics:   MetadataItem[];
  fetchedAt: number;
}

/** A search result annotated with its source and pre-ranking score. */
export interface RankedSearchResult {
  raw:          unknown;
  source:       'memory' | 'archive' | 'index';
  baseScore:    number;
  finalScore:   number;
  variantLabel: string;
}

/** Result from the empty-recovery path. */
export interface FallbackResult {
  results:       unknown[];
  suggestedTerms: string[];
  /** true when results came from a broad/low-threshold search */
  usedBroad:     boolean;
}


/** Metadata cache TTL — tags/entities/topics change slowly. */
const METADATA_CACHE_TTL_MS = 5 * 60_000;

/** Max fetch timeout for metadata browse calls. */
const BROWSE_TIMEOUT_MS = 4_000;

/** Known provider names for entity extraction. */
const KNOWN_PROVIDERS = new Set([
  'anthropic', 'github-copilot', 'kimi', 'kimi-coding', 'qwen', 'alibaba-coding',
  'copilot-sdk', 'openai', 'gemini', 'gpt-4', 'gpt-5', 'claude',
]);

/** Stop words filtered out of key-term extraction. */
const STOP_WORDS = new Set([
  'the','a','an','and','or','but','in','on','at','to','for','of','with','by',
  'from','is','it','as','be','has','had','are','was','were','will','have',
  'that','this','which','what','how','why','when','where','who','do','does',
  'did','can','could','would','should','may','might','shall','not','no','yes',
  'if','so','then','into','out','up','down','get','set','use','let','new',
  'just','also','about','like','more','some','any','all','very',
]);

// Tags/entities/topics are archive-wide aggregates and change at most every
// few minutes, so a single shared TTL cache is appropriate.

let _metadataCache: ArchiveMetadata | null = null;
let _metadataCacheFetching = false;


/**
 * Normalize a query string: collapse whitespace, trim, preserve code symbols
 * (underscores, hyphens, slashes, dots) but strip standalone punctuation.
 */
export function normalizeQuery(query: string): string {
  return query
    .replace(/[\r\n\t]+/g, ' ')  // newlines → spaces
    .replace(/[\u201c\u201d\u2018\u2019"']+/g, ' ')   // smart + plain quotes → spaces
    .replace(/\s{2,}/g, ' ')     // collapse runs of spaces
    .trim();
}

/**
 * Extract 2–8 key content terms from a query for metadata matching.
 * Filters stop-words and very short tokens.
 */
export function extractKeyTerms(query: string): string[] {
  return query
    .toLowerCase()
    .replace(/[`*?!;,.()\[\]{}]/g, ' ')
    .split(/\s+/)
    .filter(w => w.length > 2 && !STOP_WORDS.has(w))
    .slice(0, 8);
}


/**
 * Extract structured entities from a query string using lightweight regex
 * patterns. Targets machine-readable patterns that appear in CassiCore output
 * (session refs, tool names, file paths, provider IDs) — not free-form NLP.
 *
 * On extraction failure the relevant array is empty; callers always degrade
 * gracefully to the non-entity variant.
 */
export function extractEntities(query: string): ExtractedEntities {
  let sessionRefs: string[] = [];
  let toolNames:   string[] = [];
  let filePaths:   string[] = [];
  let providers:   string[] = [];

  try {
    // Session compact refs: S0, S1#M3, S0#M1.B0.P2
    const sessionRefRe = /\bS\d+(?:#M\d+(?:\.B\d+(?:\.P\d+)?)?)?\b/g;
    sessionRefs = [...query.matchAll(sessionRefRe)].map(m => m[0]);

    // Tool names: known prefixed names or core primitives
    const toolRe = /\b(?:cassi_|gitnexus_|serena_|playwright_)\w+\b|\b(?:bash|grep|glob|read|write)\b/g;
    toolNames = [...new Set([...query.matchAll(toolRe)].map(m => m[0]))];

    // File paths: word/word or word/word.ext patterns
    const fileRe = /\b(?:[\w-]+\/)+[\w.-]+\b/g;
    filePaths = [...new Set([...query.matchAll(fileRe)].map(m => m[0]))].slice(0, 4);

    // Provider IDs: explicit name matching
    const lower = query.toLowerCase();
    providers = [...KNOWN_PROVIDERS].filter(p => lower.includes(p));
  } catch {
    // Extraction is best-effort; return whatever we have
  }

  return { sessionRefs, toolNames, filePaths, providers };
}


async function fetchBrowse(baseUrl: string, category: 'tags' | 'entities' | 'topics'): Promise<MetadataItem[]> {
  try {
    const res = await fetchWithTimeout(
      `${baseUrl}/memory/archives/browse?category=${category}&minCount=1`,
      { timeoutMs: BROWSE_TIMEOUT_MS },
    );
    if (!res.ok) return [];
    const data = await res.json() as any;
    return Array.isArray(data?.items) ? data.items : [];
  } catch {
    return [];
  }
}

async function fetchRecentArchives(baseUrl: string, limit: number): Promise<unknown[]> {
  try {
    const res = await fetchWithTimeout(
      `${baseUrl}/memory/archives/recent?limit=${limit}`,
      { timeoutMs: 4_000 },
    );
    if (!res.ok) return [];
    const data = await res.json() as unknown;
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

/**
 * Return archive metadata (tags, entities, topics) from the module-level cache.
 * Fetches fresh data on first call or after TTL expiry, stale-while-revalidating
 * so callers never block on a slow browse endpoint.
 *
 * Returns null if the first fetch has never succeeded.
 */
export async function getArchiveMetadata(baseUrl: string): Promise<ArchiveMetadata | null> {
  const now = Date.now();

  // Cache hit
  if (_metadataCache && now - _metadataCache.fetchedAt < METADATA_CACHE_TTL_MS) {
    return _metadataCache;
  }

  // Stale-while-revalidate: return stale data immediately, refresh in background
  if (_metadataCache && !_metadataCacheFetching) {
    _metadataCacheFetching = true;
    void (async () => {
      try {
        const [tags, entities, topics] = await Promise.all([
          fetchBrowse(baseUrl, 'tags'),
          fetchBrowse(baseUrl, 'entities'),
          fetchBrowse(baseUrl, 'topics'),
        ]);
        _metadataCache = { tags, entities, topics, fetchedAt: Date.now() };
      } finally {
        _metadataCacheFetching = false;
      }
    })();
    return _metadataCache; // stale but instant
  }

  // First fetch: must block
  if (!_metadataCacheFetching) {
    _metadataCacheFetching = true;
    try {
      const [tags, entities, topics] = await Promise.all([
        fetchBrowse(baseUrl, 'tags'),
        fetchBrowse(baseUrl, 'entities'),
        fetchBrowse(baseUrl, 'topics'),
      ]);
      _metadataCache = { tags, entities, topics, fetchedAt: Date.now() };
    } catch {
      // Leave _metadataCache as null
    } finally {
      _metadataCacheFetching = false;
    }
  }

  return _metadataCache;
}


/**
 * Build up to 3 query variants from the normalized query, extracted entities,
 * and cached archive metadata.
 *
 * Variant 0 — "exact":    the original query, full weight
 * Variant 1 — "entity":   extracted entity terms only (if any found)
 * Variant 2 — "expanded": query + related terms from archive metadata (if any)
 */
export function buildQueryVariants(
  query: string,
  entities: ExtractedEntities,
  metadata: ArchiveMetadata | null,
): QueryVariant[] {
  const variants: QueryVariant[] = [{ query, weight: 1.0, label: 'exact' }];

  // Entity variant — searches purely on machine-readable symbols
  const entityTerms = [
    ...entities.toolNames,
    ...entities.filePaths.map(p => p.split('/').pop() ?? p),
    ...entities.providers,
  ].filter(Boolean).slice(0, 4);

  if (entityTerms.length > 0) {
    variants.push({ query: entityTerms.join(' '), weight: 0.8, label: 'entity' });
  }

  // Expanded variant — query augmented with related terms from archive metadata
  if (metadata) {
    const keyTerms = extractKeyTerms(query);
    const relatedTerms: string[] = [];

    for (const term of keyTerms.slice(0, 4)) {
      const t = term.toLowerCase();
      const push = (items: MetadataItem[], n = 2) =>
        items
          .filter(i => {
            const name = i.name.toLowerCase();
            return name.includes(t) || t.includes(name);
          })
          .slice(0, n)
          .forEach(i => relatedTerms.push(i.name));

      push(metadata.tags);
      push(metadata.entities);
      push(metadata.topics);
    }

    const queryWords = new Set(query.toLowerCase().split(/\s+/));
    const unique = [...new Set(relatedTerms)].filter(
      term => !queryWords.has(term.toLowerCase()),
    ).slice(0, 6);

    if (unique.length > 0) {
      variants.push({ query: `${query} ${unique.join(' ')}`, weight: 0.7, label: 'expanded' });
    }
  }

  return variants;
}


/**
 * Run all query variants against one source (memory / archive / index) in
 * parallel, deduplicate by entry ID, and return the full merged set.
 *
 * Each result is annotated with `baseScore = raw_score × variant_weight` so
 * results from lower-confidence variants rank below exact-query matches.
 */
export async function searchMultiVariant(
  source: 'memory' | 'archive' | 'index',
  baseUrl: string,
  variants: QueryVariant[],
  limit: number,
): Promise<RankedSearchResult[]> {
  const fetchFn =
    source === 'memory'  ? fetchMemory :
    source === 'archive' ? fetchArchive :
                           fetchSessionIndex;

  // Run all variants in parallel; fetch slightly more than limit to allow dedup
  const batchLimit = Math.ceil(limit * 1.5);
  const settled = await Promise.allSettled(
    variants.map(v => fetchFn(baseUrl, v.query, batchLimit)),
  );

  const seen = new Set<string>();
  const results: RankedSearchResult[] = [];

  for (const [i, result] of settled.entries()) {
    if (result.status !== 'fulfilled') continue;
    const variant = variants[i];

    for (const raw of result.value) {
      const r = raw as any;
      const entry = r?.entry ?? r;
      // Use entry id or a content-hash as dedup key
      const id =
        entry?.id ??
        entry?.ref ??
        `${source}::${String(entry?.content ?? '').slice(0, 80)}`;

      if (seen.has(id)) continue;
      seen.add(id);

      const rawScore: number =
        r?.score ?? r?.rank ?? r?.relevance ?? 0.5;

      results.push({
        raw,
        source,
        baseScore: rawScore * variant.weight,
        finalScore: 0, // computed in mergeAndRank
        variantLabel: variant.label,
      });
    }
  }

  return results;
}


/**
 * Detect query intent signals that should shift ranking weights.
 *
 * - "recent / latest / now / today" → boost recency weight
 * - "history / previous / archive"  → boost relevance weight
 * - Default                          → balanced 0.7 / 0.2 / 0.1
 */
function detectQueryIntent(query: string): {
  relevanceWeight: number;
  recencyWeight: number;
  diversityWeight: number;
} {
  const lower = query.toLowerCase();
  const recentSignals = ['recent', 'latest', 'current', 'just', 'now', 'today', 'new', 'last'];
  const historySignals = ['history', 'previous', 'before', 'archive', 'earlier', 'past', 'old'];

  if (recentSignals.some(s => lower.includes(s))) {
    return { relevanceWeight: 0.5, recencyWeight: 0.4, diversityWeight: 0.1 };
  }
  if (historySignals.some(s => lower.includes(s))) {
    return { relevanceWeight: 0.8, recencyWeight: 0.1, diversityWeight: 0.1 };
  }
  return { relevanceWeight: 0.7, recencyWeight: 0.2, diversityWeight: 0.1 };
}

function computeRecencyScore(raw: unknown): number {
  const r = raw as any;
  const entry = r?.entry ?? r;
  const ts: number | string | undefined =
    entry?.timestamp ?? entry?.createdAt ?? entry?.created_at;

  if (!ts) return 0.3;

  try {
    const msec = typeof ts === 'number' ? ts : new Date(ts).getTime();
    const ageHours = (Date.now() - msec) / 3_600_000;
    if (ageHours < 1)    return 1.0;
    if (ageHours < 24)   return 0.8;
    if (ageHours < 168)  return 0.6;  // 1 week
    if (ageHours < 720)  return 0.4;  // 30 days
    return 0.2;
  } catch {
    return 0.3;
  }
}

function getSessionKey(raw: unknown, source: string): string {
  const r = raw as any;
  const entry = r?.entry ?? r;
  return entry?.sessionId ?? entry?.ref?.split('#')[0] ?? source;
}

/**
 * Merge results from all three sources, apply adaptive ranking weights, and
 * return the top `topN` results ordered by final score.
 *
 * Ranking formula (adaptive):
 *   finalScore = baseScore × relevanceWeight
 *              + recencyScore × recencyWeight
 *              + diversityBonus × diversityWeight
 *
 * Diversity bonus: entries from sessions/sources that appear less frequently
 * in the full result set receive a proportional bonus.
 */
export function mergeAndRank(
  results: RankedSearchResult[],
  query: string,
  topN: number,
): RankedSearchResult[] {
  if (results.length === 0) return [];

  const { relevanceWeight, recencyWeight, diversityWeight } = detectQueryIntent(query);

  // Count occurrences per session for diversity scoring
  const sessionCounts = new Map<string, number>();
  for (const r of results) {
    const key = getSessionKey(r.raw, r.source);
    sessionCounts.set(key, (sessionCounts.get(key) ?? 0) + 1);
  }
  const maxCount = Math.max(...sessionCounts.values(), 1);

  const ranked = results.map(r => {
    const recency    = computeRecencyScore(r.raw);
    const sessionKey = getSessionKey(r.raw, r.source);
    const count      = sessionCounts.get(sessionKey) ?? 1;
    // Sessions that appear less often get a higher diversity bonus (0–1 range)
    const divBonus   = 1 - count / maxCount;

    const finalScore =
      r.baseScore  * relevanceWeight +
      recency      * recencyWeight   +
      divBonus     * diversityWeight;

    return { ...r, finalScore };
  });

  return ranked
    .sort((a, b) => b.finalScore - a.finalScore)
    .slice(0, topN);
}


/**
 * When the primary multi-variant search returns nothing, attempt recovery:
 *   1. Re-run archive search with a higher limit and accept lower-scoring results
 *   2. Fetch the most recent archive entries as temporal context
 *   3. Suggest related terms mined from archive metadata
 *
 * Always returns an object (never throws); empty arrays mean total failure.
 */
export async function recoverFromEmpty(
  baseUrl: string,
  query: string,
  keyTerms: string[],
  metadata: ArchiveMetadata | null,
): Promise<FallbackResult> {
  // Broader archive search (higher limit — filter client-side at score ≥ 0.25)
  const [broadSettled, recentSettled] = await Promise.allSettled([
    fetchArchive(baseUrl, query, 15),
    fetchRecentArchives(baseUrl, 5),
  ]);

  const broad: unknown[]  = broadSettled.status  === 'fulfilled' ? broadSettled.value  : [];
  const recent: unknown[] = recentSettled.status === 'fulfilled' ? recentSettled.value : [];

  // Keep broad results that have some relevance signal
  const filteredBroad = broad.filter(r => {
    const score: number = (r as any)?.score ?? 1;
    return score >= 0.25;
  });

  // Suggested search terms from archive metadata
  const suggestedTerms: string[] = [];
  if (metadata) {
    for (const term of keyTerms.slice(0, 4)) {
      const t = term.toLowerCase();
      const pick = (items: MetadataItem[]) =>
        items
          .filter(i => {
            const n = i.name.toLowerCase();
            return (n.includes(t) || t.includes(n)) &&
                   !query.toLowerCase().includes(n);
          })
          .slice(0, 2)
          .map(i => i.name);

      suggestedTerms.push(...pick(metadata.tags));
      suggestedTerms.push(...pick(metadata.entities));
      suggestedTerms.push(...pick(metadata.topics));
    }
  }

  const uniqueSuggestions = [...new Set(suggestedTerms)].slice(0, 5);
  const usedBroad = filteredBroad.length > 0;
  const results = usedBroad ? filteredBroad : recent.slice(0, 5);

  return { results, suggestedTerms: uniqueSuggestions, usedBroad };
}


/**
 * Format a single ranked cross-source result as a compact one-liner for the
 * "Top Relevant (cross-source)" section.
 */
export function formatTopRelevantEntry(r: RankedSearchResult, index: number): string {
  const raw   = r.raw as any;
  const entry = raw?.entry ?? raw;
  const score = Math.round(r.finalScore * 100);

  // Age label
  const ts: number | string | undefined =
    entry?.timestamp ?? entry?.createdAt ?? entry?.created_at;
  let ageLabel = '';
  if (ts) {
    try {
      const msec = typeof ts === 'number' ? ts : new Date(ts).getTime();
      const ageHours = (Date.now() - msec) / 3_600_000;
      if (ageHours < 1)         ageLabel = ' · just now';
      else if (ageHours < 24)   ageLabel = ` · ${Math.round(ageHours)}h ago`;
      else if (ageHours < 720)  ageLabel = ` · ${Math.round(ageHours / 24)}d ago`;
      else                      ageLabel = ` · ${Math.round(ageHours / 720)}mo ago`;
    } catch { /* ignore */ }
  }

  // Source label + snippet
  let sourceLabel: string;
  let snippet: string;

  switch (r.source) {
    case 'memory': {
      const type    = entry?.type ?? 'memory';
      sourceLabel   = `[Memory/${type}]`;
      const content: string = entry?.content ?? '';
      snippet = content.replace(/\n/g, ' ').slice(0, 120);
      break;
    }
    case 'archive': {
      const type    = entry?.type ?? 'entry';
      const summary = entry?.analysis?.summary as string | undefined;
      sourceLabel   = `[Archive/${type}]`;
      snippet = (summary ?? (entry?.content ?? '') as string).replace(/\n/g, ' ').slice(0, 120);
      break;
    }
    case 'index': {
      const ref   = entry?.ref ?? '';
      const role  = entry?.role ?? 'unknown';
      sourceLabel = `[Session/${ref}] ${role}`;
      const content: string = entry?.content ?? '';
      snippet = content.replace(/\n/g, ' ').slice(0, 120);
      break;
    }
  }

  return `${index + 1}. **${sourceLabel}** (${score}%)${ageLabel}  \n   ${snippet}`;
}
