/**
 * Vendor stub for the AI provider-model registry.
 *
 * Source: `core/ai/` (D:) — owned by `@cassicore/ai` (P8), NOT part of P6.
 * `model-capabilities.ts` lazily dynamic-imports this registry probe at runtime
 * and gracefully falls back when it is unavailable (try/catch -> null).
 *
 * Until @cassicore/ai publishes, this stub exports MODELS as undefined so the
 * capability-registry probe returns null (clean fallback, no throw — the D:
 * code already guards `models?.[key]`). Re-point to `@cassicore/ai` at P8.
 */
export const MODELS = undefined
export const models = undefined
export default { MODELS: undefined, models: undefined }
