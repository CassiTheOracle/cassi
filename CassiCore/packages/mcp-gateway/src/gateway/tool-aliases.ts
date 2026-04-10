#!/usr/bin/env node
/**
 * tool-aliases.ts — Unified tool alias resolution for the CassiCore MCP gateway.
 *
 * Handles four categories of tool name errors in a single, structured pipeline:
 *
 *   1. Prefix normalization   — strips leading cassi_, serena_, playwright_,
 *                               gitnexus_, duckduckgo_ prefixes.
 *   2. Exact alias table      — maps deprecated / external / shorthand names to
 *                               their current canonical equivalents, optionally
 *                               injecting args (e.g. action: 'search').
 *   3. Chained resolution     — aliases may point to other aliases (max 3 hops,
 *                               cycle-safe).
 *   4. Fuzzy matching         — if nothing matches, Levenshtein similarity ≥ 0.8
 *                               auto-resolves; below that threshold the match is
 *                               surfaced as a "Did you mean?" suggestion in the
 *                               error message but is never applied automatically.
 *
 * Integration:
 *   - routeToolCall (cassicore-gateway.ts) calls resolveToolAlias() at entry,
 *     replacing the old resolveDeprecatedToolName() function.
 *   - normalizeToolName (do-tool.ts) delegates prefix stripping here so the
 *     logic lives in one place.
 *   - When all resolution fails, enrichUnknownToolError() adds a "Did you mean?"
 *     hint to the thrown error.
 */

// Types

/**
 * A resolved target for an alias entry.
 *
 * `name`  — the canonical registered tool name.
 * `args`  — an optional partial args object to *merge* into the call args.
 *           Existing caller args take precedence (the patch fills in gaps).
 */
export interface AliasEntry {
  name: string;
  args?: Record<string, unknown>;
}

/**
 * A flat alias table: alias name → resolved entry.
 * The canonical registered names must NOT appear here as keys; they are
 * handled by the gateway switch/if chain directly.
 */
export type AliasTable = Record<string, AliasEntry>;

// Canonical tool names (the ground truth the gateway actually registers)

/** Every name the gateway handles directly — used for fuzzy matching candidates. */
export const CANONICAL_TOOL_NAMES: readonly string[] = [
  // Core tools
  'bash', 'read', 'write', 'edit',
  // Meta-wrapper / context tools
  'do', 'enrich',
  // Consolidated domain tools
  'agent', 'memory', 'session', 'intelligence', 'artifact',
  'code', 'file', 'browser', 'web', 'config', 'model',
  'training',
];

// Prefix stripping rules
// Applied first, before the alias table lookup, to reduce table size.

/**
 * Prefixes that may be stripped from a tool name.  The stripped result is
 * then looked up in the alias table (and may resolve directly to a canonical
 * name if the bare name is registered).
 */
const STRIP_PREFIXES: readonly string[] = [
  'cassi_',
  'serena_',
  'playwright_browser_',
  'playwright_',
  'gitnexus_',
  'duckduckgo_',
];

/**
 * Strip at most one known prefix from a tool name.
 * Returns `null` if no prefix matched.
 * @dep callers: normalizeToolName (mcp/gateway/do-tool.ts), resolveToolAlias (mcp/gateway/tool-aliases.ts)
 * @dep flows: Start → StripKnownPrefix (5/5)
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */
export function stripKnownPrefix(name: string): string | null {
  for (const prefix of STRIP_PREFIXES) {
    if (name.startsWith(prefix)) {
      return name.slice(prefix.length);
    }
  }
  return null;
}

// Exact alias table

/**
 * Canonical alias table.
 *
 * Keys   — every alias (deprecated, external MCP, shorthand) that should be
 *           accepted in place of the real tool name.
 * Values — `{ name }` or `{ name, args }` targeting a canonical tool.
 *
 * HOW: Entries are checked *after* prefix stripping, so you only need to
 * list the unprefixed form here if the prefix rule already covers it.
 * Full names (with prefix) are also fine — they take precedence.
 */
export const TOOL_ALIASES: AliasTable = {


  // helix_* → agent tool with type+action injected (lumen/dyad consolidated into helix)
  helix_project:    { name: 'agent', args: { type: 'helix',  action: 'project'    } },
  helix_status:     { name: 'agent', args: { type: 'helix',  action: 'status'     } },
  helix_jobs:       { name: 'agent', args: { type: 'helix',  action: 'jobs'       } },
  helix_watch:      { name: 'agent', args: { type: 'helix',  action: 'watch'      } },
  helix_cancel:     { name: 'agent', args: { type: 'helix',  action: 'cancel'     } },
  helix_sessions:   { name: 'agent', args: { type: 'helix',  action: 'sessions'   } },
  helix_messages:   { name: 'agent', args: { type: 'helix',  action: 'messages'   } },
  helix_tool_calls: { name: 'agent', args: { type: 'helix',  action: 'tool_calls' } },
  helix_events:     { name: 'agent', args: { type: 'helix',  action: 'events'     } },

  // flux_* → agent tool
  flux_team:        { name: 'agent', args: { type: 'flux', action: 'team'    } },
  flux_run:         { name: 'agent', args: { type: 'flux', action: 'run'     } },
  flux_inspect:     { name: 'agent', args: { type: 'flux', action: 'inspect' } },
  flux_watch:       { name: 'agent', args: { type: 'flux', action: 'watch'   } },

  // constellation_* → agent tool
  constellation_project: { name: 'agent', args: { type: 'constellation', action: 'project' } },
  constellation_status:  { name: 'agent', args: { type: 'constellation', action: 'status'  } },
  constellation_watch:   { name: 'agent', args: { type: 'constellation', action: 'watch'   } },
  constellation_steer:   { name: 'agent', args: { type: 'constellation', action: 'steer'   } },


  memory_store:          { name: 'memory', args: { action: 'store'          } },
  memory_search:         { name: 'memory', args: { action: 'search'         } },
  memory_recent:         { name: 'memory', args: { action: 'recent'         } },
  memory_delete:         { name: 'memory', args: { action: 'delete'         } },
  memory_kv_get:         { name: 'memory', args: { action: 'kv_get'         } },
  memory_kv_set:         { name: 'memory', args: { action: 'kv_set'         } },
  memory_kv_del:         { name: 'memory', args: { action: 'kv_del'         } },
  memory_stats:          { name: 'memory', args: { action: 'stats'          } },
  archive_search:        { name: 'memory', args: { action: 'archive_search' } },
  archive_get:           { name: 'memory', args: { action: 'archive_get'    } },
  archive_related:       { name: 'memory', args: { action: 'archive_related'} },
  archive_recent:        { name: 'memory', args: { action: 'archive_recent' } },
  browse:                { name: 'memory', args: { action: 'browse'         } },
  universal_search:      { name: 'memory', args: { action: 'universal_search'} },

  // Shorthands
  mem:                   { name: 'memory' },
  remember:              { name: 'memory', args: { action: 'store'  } },
  recall:                { name: 'memory', args: { action: 'search' } },


  sessions:              { name: 'session', args: { action: 'list'         } },
  session_detail:        { name: 'session', args: { action: 'detail'       } },
  session_prune:         { name: 'session', args: { action: 'prune'        } },
  session_conversation:  { name: 'session', args: { action: 'conversation' } },
  session_export:        { name: 'session', args: { action: 'export'       } },
  resolve_ref:           { name: 'session', args: { action: 'resolve_ref'  } },
  index_session:         { name: 'session', args: { action: 'index'        } },
  index_search:          { name: 'session', args: { action: 'index_search' } },
  index_stats:           { name: 'session', args: { action: 'index_stats'  } },


  activity:              { name: 'intelligence', args: { action: 'activity'      } },
  thinker:               { name: 'intelligence', args: { action: 'thinker'       } },
  subconscious:          { name: 'intelligence', args: { action: 'subconscious'  } },
  consciousness:         { name: 'intelligence', args: { action: 'consciousness' } },
  trace:                 { name: 'intelligence', args: { action: 'trace'         } },
  effectiveness:         { name: 'intelligence', args: { action: 'effectiveness' } },
  budget:                { name: 'intelligence', args: { action: 'budget'        } },
  evolution:             { name: 'intelligence', args: { action: 'evolution'     } },
  blindspots:            { name: 'intelligence', args: { action: 'blindspots'    } },
  snapshot:              { name: 'intelligence', args: { action: 'snapshot'      } },
  trust:                 { name: 'intelligence', args: { action: 'trust'         } },
  consequences:          { name: 'intelligence', args: { action: 'consequences'  } },
  dialectic:             { name: 'intelligence', args: { action: 'dialectic'     } },
  intel:                 { name: 'intelligence' },


  share_file:            { name: 'artifact', args: { action: 'share'    } },
  open_file:             { name: 'artifact', args: { action: 'open'     } },
  file_admin:            { name: 'artifact', args: { action: 'admin'    } },
  file_artifact_write:   { name: 'artifact', args: { action: 'write'    } },
  file_artifact_read:    { name: 'artifact', args: { action: 'read'     } },
  file_artifact_list:    { name: 'artifact', args: { action: 'list'     } },
  file_artifact_delete:  { name: 'artifact', args: { action: 'delete'   } },
  file_artifact_versions:{ name: 'artifact', args: { action: 'versions' } },
  file_artifact_share:   { name: 'artifact', args: { action: 'share'    } },
  file_artifact_stats:   { name: 'artifact', args: { action: 'stats'    } },
  file_artifact_gc:      { name: 'artifact', args: { action: 'gc'       } },


  // GitNexus tools → code consolidated
  gitnexus_query:          { name: 'code', args: { action: 'query'          } },
  gitnexus_context:        { name: 'code', args: { action: 'context'        } },
  gitnexus_impact:         { name: 'code', args: { action: 'impact'         } },
  gitnexus_cypher:         { name: 'code', args: { action: 'cypher'         } },
  gitnexus_detect_changes: { name: 'code', args: { action: 'detect_changes' } },
  gitnexus_list_repos:     { name: 'code', args: { action: 'list_repos'     } },
  gitnexus_rename:         { name: 'code', args: { action: 'rename_graph'   } },

  // Serena code-intelligence tools → code consolidated
  serena_find_symbol:              { name: 'code', args: { action: 'symbol'         } },
  serena_find_referencing_symbols: { name: 'code', args: { action: 'refs'           } },
  serena_get_symbols_overview:     { name: 'code', args: { action: 'overview'       } },
  serena_rename_symbol:            { name: 'code', args: { action: 'rename_symbol'  } },
  serena_replace_symbol_body:      { name: 'code', args: { action: 'replace_symbol' } },
  serena_insert_after_symbol:      { name: 'code', args: { action: 'insert_after'   } },
  serena_insert_before_symbol:     { name: 'code', args: { action: 'insert_before'  } },

  // Serena pattern-search → code or file (code when code-focused)
  serena_search_for_pattern: { name: 'code', args: { action: 'search_pattern' } },

  // Serena file tools → file consolidated
  serena_list_dir:          { name: 'file', args: { action: 'list'  } },
  serena_find_file:         { name: 'file', args: { action: 'find'  } },


  mkdir:                { name: 'file', args: { action: 'mkdir'  } },
  delete:               { name: 'file', args: { action: 'delete' } },
  exists:               { name: 'file', args: { action: 'exists' } },


  playwright_browser_navigate:          { name: 'browser', args: { action: 'navigate'      } },
  playwright_browser_snapshot:          { name: 'browser', args: { action: 'snapshot'      } },
  playwright_browser_click:             { name: 'browser', args: { action: 'click'         } },
  playwright_browser_type:              { name: 'browser', args: { action: 'type'          } },
  playwright_browser_take_screenshot:   { name: 'browser', args: { action: 'screenshot'    } },
  playwright_browser_evaluate:          { name: 'browser', args: { action: 'evaluate'      } },
  playwright_browser_tabs:              { name: 'browser', args: { action: 'tabs'          } },
  playwright_browser_wait_for:          { name: 'browser', args: { action: 'wait'          } },
  playwright_browser_press_key:         { name: 'browser', args: { action: 'press_key'     } },
  playwright_browser_fill_form:         { name: 'browser', args: { action: 'fill_form'     } },
  playwright_browser_select_option:     { name: 'browser', args: { action: 'select'        } },
  playwright_browser_hover:             { name: 'browser', args: { action: 'hover'         } },
  playwright_browser_drag:              { name: 'browser', args: { action: 'drag'          } },
  playwright_browser_close:             { name: 'browser', args: { action: 'close'         } },
  playwright_browser_navigate_back:     { name: 'browser', args: { action: 'back'          } },
  playwright_browser_resize:            { name: 'browser', args: { action: 'resize'        } },
  playwright_browser_console_messages:  { name: 'browser', args: { action: 'console'       } },
  playwright_browser_network_requests:  { name: 'browser', args: { action: 'network'       } },
  playwright_browser_handle_dialog:     { name: 'browser', args: { action: 'handle_dialog' } },
  playwright_browser_file_upload:       { name: 'browser', args: { action: 'file_upload'   } },
  playwright_browser_run_code:          { name: 'browser', args: { action: 'run_code'      } },
  playwright_browser_install:           { name: 'browser', args: { action: 'install'       } },


  web_fetch:             { name: 'web', args: { action: 'fetch'        } },
  web_search:            { name: 'web', args: { action: 'search'       } },
  duckduckgo_search:     { name: 'web', args: { action: 'search'       } },
  duckduckgo_fetch_content: { name: 'web', args: { action: 'fetch_content' } },
  google_search:         { name: 'web', args: { action: 'search'       } },
  fetch:                 { name: 'web', args: { action: 'fetch'        } },
  search:                { name: 'web', args: { action: 'search'       } },


  config_get:            { name: 'config', args: { action: 'get'              } },
  config_set:            { name: 'config', args: { action: 'set'              } },
  providers:             { name: 'config', args: { action: 'providers'        } },
  provider_metrics:      { name: 'config', args: { action: 'provider_metrics' } },
  provider_config:       { name: 'config', args: { action: 'provider_config'  } },
  cfg:                   { name: 'config' },


  model_directive:       { name: 'model' },
  set_model:             { name: 'model', args: { action: 'set'   } },
  get_model:             { name: 'model', args: { action: 'get'   } },
  clear_model:           { name: 'model', args: { action: 'clear' } },


  training_stats:        { name: 'training', args: { action: 'stats'       } },
  training_search:       { name: 'training', args: { action: 'search'      } },
  training_objects:      { name: 'training', args: { action: 'objects'     } },
  training_resolve:      { name: 'training', args: { action: 'resolve'     } },
  training_labels:       { name: 'training', args: { action: 'labels'      } },
  training_quality:      { name: 'training', args: { action: 'quality'     } },
  training_annotations:  { name: 'training', args: { action: 'annotations' } },
  training_ingest:       { name: 'training', args: { action: 'ingest'      } },
  training_tag:          { name: 'training', args: { action: 'tag'         } },
  training_export:       { name: 'training', args: { action: 'export'      } },


  // Bare action names that agents sometimes call as standalone tools
  find_symbol:           { name: 'code', args: { action: 'symbol'         } },
  find_referencing_symbols: { name: 'code', args: { action: 'refs'        } },
  get_symbols_overview:  { name: 'code', args: { action: 'overview'       } },
  replace_content:       { name: 'file', args: { action: 'edit'           } },
  replace_symbol_body:   { name: 'code', args: { action: 'replace_symbol' } },
  insert_after_symbol:   { name: 'code', args: { action: 'insert_after'   } },
  insert_before_symbol:  { name: 'code', args: { action: 'insert_before'  } },
  search_for_pattern:    { name: 'code', args: { action: 'search_pattern' } },
  list_dir:              { name: 'file', args: { action: 'list'           } },
  find_file:             { name: 'file', args: { action: 'find'           } },
  check_onboarding_performed: { name: 'code', args: { action: 'overview' } },
  initial_instructions:  { name: 'code', args: { action: 'overview'       } },
  onboarding:            { name: 'code', args: { action: 'overview'       } },
};

// Fuzzy matching (Levenshtein distance)

const FUZZY_AUTO_RESOLVE_THRESHOLD = 0.7;
const MAX_CHAIN_DEPTH = 3;
const MIN_SUFFIX_LENGTH = 4;

/**
 * Normalised Levenshtein similarity in [0, 1].
 * 1.0 = identical, 0.0 = completely different.
 */
export function levenshteinSimilarity(a: string, b: string): number {
  if (a === b) return 1;
  const la = a.length;
  const lb = b.length;
  if (la === 0 || lb === 0) return 0;

  const dp: number[] = Array.from({ length: lb + 1 }, (_, i) => i);
  for (let i = 1; i <= la; i++) {
    let prev = i;
    for (let j = 1; j <= lb; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      const cur = Math.min(
        dp[j] + 1,       // deletion
        prev + 1,        // insertion
        dp[j - 1] + cost // substitution
      );
      dp[j - 1] = prev;
      prev = cur;
    }
    dp[lb] = prev;
  }

  const distance = dp[lb];
  return 1 - distance / Math.max(la, lb);
}

/**
 * Find the best fuzzy match for `name` among `candidates`.
 * Returns `{ match, similarity }` or `null` if no candidate exceeds `minSimilarity`.
 * @dep callers: suggestToolName (mcp/gateway/tool-aliases.ts), resolveToolAlias (mcp/gateway/tool-aliases.ts)
 * @dep calls: levenshteinSimilarity
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function findBestFuzzyMatch(
  name: string,
  candidates: readonly string[],
  minSimilarity = 0.5
): { match: string; similarity: number } | null {
  let best: { match: string; similarity: number } | null = null;
  for (const candidate of candidates) {
    const similarity = levenshteinSimilarity(name, candidate);
    if (similarity >= minSimilarity && (!best || similarity > best.similarity)) {
      best = { match: candidate, similarity };
    }
  }
  return best;
}

// Resolution pipeline

/**
 * Resolve a tool name + args through the alias pipeline.
 *
 * Resolution order:
 *   1. If `name` is already a canonical name → return as-is.
 *   2. Look up `name` in the alias table (exact).
 *   3. Strip one known prefix and try step 1 & 2 again.
 *   4. Follow alias chains (up to MAX_CHAIN_DEPTH hops, cycle-safe).
 *   5. Fuzzy match against canonical names; auto-resolve if similarity ≥ threshold.
 *
 * Returns `null` if nothing matched (caller should throw an enriched error).
 *
 * @param name    Raw tool name from the caller
 * @param args    Current call args (will have alias patches merged in)
 * @param table   Alias table to use (defaults to TOOL_ALIASES)
 * @param canonicals  Canonical names to recognise as final targets
 * @dep callers: resolveToolAlias (mcp/gateway/tool-aliases.ts), routeToolCall (mcp/cassicore-gateway.ts)
 * @dep calls: add, stripKnownPrefix, findBestFuzzyMatch, resolveToolAlias, has
 * @dep flows: Start → StripKnownPrefix (4/5)
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */
export function resolveToolAlias(
  name: string,
  args: unknown,
  table: AliasTable = TOOL_ALIASES,
  canonicals: readonly string[] = CANONICAL_TOOL_NAMES
): { name: string; args: unknown } | null {
  const seen = new Set<string>();
  let current = name;
  let mergedArgs: Record<string, unknown> = args != null && typeof args === 'object'
    ? { ...(args as Record<string, unknown>) }
    : {};

  for (let hop = 0; hop < MAX_CHAIN_DEPTH; hop++) {
    if (seen.has(current)) break; // cycle guard
    seen.add(current);

    // 1. Already canonical?
    if (canonicals.includes(current)) {
      return { name: current, args: mergedArgs };
    }

    // 2. Exact alias table lookup
    const entry = table[current];
    if (entry) {
      current = entry.name;
      if (entry.args) {
        // Alias args provide defaults; caller args take precedence
        mergedArgs = { ...entry.args, ...mergedArgs };
      }
      continue; // follow the chain
    }

    // 3. Strip one known prefix and retry
    const stripped = stripKnownPrefix(current);
    if (stripped && stripped !== current) {
      current = stripped;
      continue;
    }

    // 4. Suffix match against alias table keys
    // Handles bare names left after partial prefix stripping (e.g. 'search_for_pattern'
    // matches the alias key 'serena_search_for_pattern')
    if (current.length >= MIN_SUFFIX_LENGTH) {
      const suffixKey = Object.keys(table).find(
        (key) => key.endsWith(`_${current}`) && key !== current,
      );
      if (suffixKey) {
        const sfxEntry = table[suffixKey];
        current = sfxEntry.name;
        if (sfxEntry.args) {
          mergedArgs = { ...sfxEntry.args, ...mergedArgs };
        }
        continue;
      }
    }

    // Nothing found for this hop — stop early
    break;
  }

  // 4. Check canonical again after all hops
  if (canonicals.includes(current)) {
    return { name: current, args: mergedArgs };
  }

  // 5. Fuzzy match against all known names (canonical + alias keys)
  const allKnown = [...canonicals, ...Object.keys(table)];
  const fuzzy = findBestFuzzyMatch(name, allKnown, FUZZY_AUTO_RESOLVE_THRESHOLD);
  if (fuzzy) {
    // Re-run resolution on the fuzzy match target so arg patches are applied
    const resolved = resolveToolAlias(fuzzy.match, args, table, canonicals);
    if (resolved) return resolved;
  }

  return null; // caller decides what to do
}

// Error enrichment

/**
 * All known names: canonical tool names + every alias key.
 * Used for "Did you mean?" suggestions in error messages.
 */
export function allKnownToolNames(
  table: AliasTable = TOOL_ALIASES,
  canonicals: readonly string[] = CANONICAL_TOOL_NAMES
): readonly string[] {
  return [...canonicals, ...Object.keys(table)];
}

/**
 * Given an unrecognised tool name, produce a "Did you mean: X?" suggestion
 * string (or empty string if no near match exists).
 *
 * Uses a lower threshold than auto-resolution (0.5) so that typos get
 * mentioned even when we would not auto-resolve them.
 */
export function suggestToolName(
  name: string,
  table: AliasTable = TOOL_ALIASES,
  canonicals: readonly string[] = CANONICAL_TOOL_NAMES
): string {
  const all = allKnownToolNames(table, canonicals);
  const fuzzy = findBestFuzzyMatch(name, all, 0.5);
  if (!fuzzy) return '';
  return ` Did you mean: "${fuzzy.match}"?`;
}

/**
 * Build an enriched "Unknown tool" error message.
 *
 * Example: `Unknown tool: "bawsh". Did you mean: "bash"?`
 */
export function unknownToolError(
  name: string,
  table: AliasTable = TOOL_ALIASES,
  canonicals: readonly string[] = CANONICAL_TOOL_NAMES
): Error {
  const suggestion = suggestToolName(name, table, canonicals);
  return new Error(`Unknown tool: "${name}".${suggestion}`);
}
