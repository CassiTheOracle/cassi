/**
 * @cassicore/utils — public API.
 *
 * Generic utilities extracted from CassiCore core/utils (paths.ts excluded —
 * owned by @cassicore/foundation). Packager-written barrel (source dir had none).
 */
export { signalPromise, throwIfAborted } from './abort.js'
export { ActivityTimeout } from './activity-timeout.js'
export type { ActivityTimeoutOptions, TimeoutReason } from './activity-timeout.js'
export { CachedValue, createCachedValue } from './cached-value.js'
export type { CachedValueOptions } from './cached-value.js'
export { CircuitBreaker, CircuitState, CircuitOpenError, createCircuitBreaker } from './circuit-breaker.js'
export type { CircuitBreakerOptions } from './circuit-breaker.js'
export { generateShortId, generateReadableId } from './ids.js'
export { clamp, lerp, remap } from './math.js'
export { ContextOverflowError, isOverflowError, reclassifyAsOverflow, contentLength, stripToolFiller, isQuestionBlock, hasQuestionResult, buildToolUseMapFromMessages } from './overflow.js'
export { TTLCache, createTTLCache } from './ttl-cache.js'
export type { TTLCacheOptions } from './ttl-cache.js'
