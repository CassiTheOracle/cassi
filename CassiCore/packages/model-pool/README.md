# @cassicore/model-pool

Model pool, model handles, budget/fallback management, billing models and
capability caching extracted from CassiCore's `core/model-pool/`. History-preserved
import splice. `core/model-pool/templates.ts` excluded (DEAD).

## Surface

- `ModelPool` — the pool (barrel export, `index.ts`)
- `ModelHandle` / `ModelCapabilities` / `BudgetScope` / `BudgetLimits` / `PoolEvent`
  etc. (`types.ts`)
- `FallbackManager`, `BudgetManager`, `ModelHandleImpl`, `BillingModel`,
  `ModelCapabilitiesFetcher`

Pulls **no** provider client SDKs (OpenAI/Anthropic/etc.) — it depends only on
foundation types, `@cassicore/utils` (TTLCache, CircuitBreaker), and a vendored
`CostClassifier`.

## Vendored

- `src/vendor/core/providers/cost-classifier.ts` — faithful runtime copy of
  `core/providers/cost-classifier.ts` (`CostClassifier`, self-contained/pure),
  imported by `billing-models.ts`. Re-pointed to `@cassicore/ai` (or a cost home)
  at P7/P8.

Depends on `@cassicore/foundation` and `@cassicore/utils`.
