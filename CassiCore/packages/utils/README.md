# @cassicore/utils

Generic utilities extracted from CassiCore's `core/utils/` (history-preserved via
`git filter-repo` import splice). `core/utils/paths.ts` is **not** here — it lives
in `@cassicore/foundation` (paths port, P1).

## Surface

- `signalPromise` / `throwIfAborted` (`abort.ts`)
- `ActivityTimeout` (`activity-timeout.ts`)
- `CachedValue` / `createCachedValue` (`cached-value.ts`)
- `CircuitBreaker` / `CircuitOpenError` / `createCircuitBreaker` (`circuit-breaker.ts`)
- `generateShortId` / `generateReadableId` (`ids.ts`)
- `clamp` / `lerp` / `remap` (`math.ts`)
- `TTLCache` / `createTTLCache` (`ttl-cache.ts`)

## Vendored

- `src/vendor/core/logger.ts` — faithful runtime copy of `core/logger.ts`
  (`rootLogger`), imported by `circuit-breaker.ts`. Re-pointed to
  `@cassicore/events` when that package publishes (P6 turn 3).

Depends on `@cassicore/foundation` only.
