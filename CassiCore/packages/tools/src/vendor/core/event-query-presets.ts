/**
 * VENDOR RUNTIME STUB — `core/event-query-presets.ts` (host, P7).
 *
 * Placeholder for the event-query preset catalog consumed by query-events.ts
 * (tools). Signature-faithful stubs (empty preset catalog); owned by the host
 * package (P7). Re-pointed there.
 */
import type { ComplexEventQuery, QueryPreset } from '@cassicore/foundation'

/** Preset query catalog for the event bus (host, P7). */
export const QUERY_PRESETS: QueryPreset[] = []

/** Get a preset query by name. */
export function getPreset(name: string): QueryPreset | undefined {
  return QUERY_PRESETS.find((p) => p.name === name)
}

/** List all presets. */
export function getAllPresets(): QueryPreset[] {
  return QUERY_PRESETS
}

/** List presets in a category. */
export function getPresetsByCategory(category: string): QueryPreset[] {
  return QUERY_PRESETS.filter((p) => p.category === category)
}

/** List preset categories. */
export function getCategories(): string[] {
  return [...new Set(QUERY_PRESETS.map((p) => p.category).filter(Boolean))]
}

/** Return the query for a named preset (undefined if unknown). */
export function executePreset(name: string): ComplexEventQuery | undefined {
  return getPreset(name)?.query
}

/** Register a preset. */
export function registerPreset(_preset: QueryPreset): void {
  /* host seam placeholder */
}

/** List preset names. */
export function getPresetNames(): string[] {
  return QUERY_PRESETS.map((p) => p.name)
}

/** Search presets by term. */
export function searchPresets(_searchTerm: string): QueryPreset[] {
  return []
}

/** Generate preset documentation. */
export function generatePresetDocs(): string {
  return ''
}
