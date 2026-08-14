/**
 * VENDOR RUNTIME STUB — `core/event-query-parser.ts` (host, P7).
 *
 * Placeholder for the natural-language event-query parser consumed by
 * query-events.ts (tools). Signature-faithful stubs (no pattern engine);
 * owned by the host package (P7). Re-pointed there.
 */
import type { ComplexEventQuery } from '@cassicore/foundation'

/** Parsed result of a simple event query string. */
export interface ParsedQuery {
  success: boolean
  query: ComplexEventQuery
  translation: string
  matchedPattern?: string
  error?: string
}

/** A single query suggestion row. */
export interface QuerySuggestion {
  label: string
  query: string
  category?: string
}

/** A registered NL query pattern. */
export interface QueryPattern {
  name: string
  pattern: RegExp
  category?: string
  extract(match: RegExpMatchArray): Record<string, unknown>
  build(params: Record<string, unknown>): ComplexEventQuery
}

/** Parse a simple natural-language query into a complex structured query. */
export function parseSimpleQuery(_simple: { query: string; limit?: number }): ParsedQuery {
  return {
    success: false,
    query: { mode: 'complex', types: [] },
    translation: '',
    error: `Query parsing not available — event-query-parser is a host (P7) seam.`,
  }
}

/** Build query suggestions for an interactive context. */
export function getQuerySuggestions(_context?: { sessionId?: string; agentId?: string }): QuerySuggestion[] {
  return []
}

/** Validate a query string. */
export function validateQuery(_query: string): { valid: boolean; error?: string; parsed?: ParsedQuery } {
  return { valid: false, error: `Query validation not available — host (P7) seam.` }
}

/** Register a query pattern. */
export function registerPattern(_pattern: QueryPattern): void {
  /* host seam placeholder */
}

/** List registered patterns. */
export function getRegisteredPatterns(): QueryPattern[] {
  return []
}
