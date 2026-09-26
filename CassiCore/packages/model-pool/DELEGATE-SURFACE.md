# `@cassicore/model-pool` — Retained / DELEGATE surface split (P2)

**Phase:** CASSICORE-FOCUS §6 P2 (input to P4).
**Source of truth:** `CASSICORE-FOCUS-PLAN.md` §5 verdict #19 (model-pool **PORT**),
§2 model-access decision, §4.4 session mapping; `packages/tools/src/ports/README.md`
(P1 manifest, "Model access" row).

---

## Bottom line

The mind keeps ONLY the `ModelHandle` cast + a shim of `acquire/release` that
produces an **ohmypi-backed** handle (calls `mind_complete` or spawns a task
agent). Budget/billing/fallback/centralized routing is dropped — ohmypi owns
routing. **Executed at P4 (2026-08-14):** the delegate machinery + host provider
pool were deleted and replaced by `createMindCompleteAcquirer(...)`. Full checklist
in §4 below.

---

## 1. Retained surface (P4 preserves this seam)

| Symbol | Module | Kind | Retained-role |
|---|---|---|---|
| `ModelHandle` | `src/types.ts` (`§184-201`) | interface | The mind's cast over an ohmypi completion. `complete()`/`stream()` retarget to `mind_complete`/task-agents at P4; `release()`/`[Symbol.dispose]()` stay. |
| `ModelCompletionOpts` | `src/types.ts` (`§173-178`) | interface (extends foundation `CompletionOpts`) | Completion options passed through the retained handle. |
| `ModelCapabilities` | `src/types.ts` (`§19-32`) | interface | Capabilities metadata on the handle (contextWindow, maxOutputTokens, supportsTools/Images, source, costTier). `costTier` is arguably delegate-ish but is part of `ModelHandle` — keep for now; trim if unused at P4. |
| `ModelHandleImpl` | `src/model-handle.ts` | class | The retained completion runtime. **P4:** repoint `providerInstance.complete()` → ohmypi completion; strip `budgetManager`/`fallbackManager` tie-ins. |
| `ModelPool` (type) | `src/index.ts` (class) | class/type | The retained acquire-factory **shape**: `acquire(slot, template, sessionId, override?) → Promise<ModelHandle>` (+ `release`/`dispose`). At P4 the *class* is replaced by an ohmypi-backed shim satisfying this same acquire contract. |

**Canonical import:** retained surface is re-exported from `src/ports/index.ts`
(subpath `@cassicore/model-pool/ports`, added P2) and mirrored in the barrel
`@cassicore/model-pool`. Mind consumers should import `ModelHandle`,
`ModelCompletionOpts`, `ModelCapabilities`, `ModelHandleImpl`, `ModelPool` only
via these two entry points.

### Retained consumers (today — after P2 split)
| Consumer | Imports | Notes |
|---|---|---|
| `packages/mini-helix/src/mini-helix-runner.ts` | `ModelHandle, ModelCompletionOpts` (`@cassicore/model-pool/types`) | retained — unchanged |
| `packages/mini-helix/src/mini-helix-types.ts` | `ModelHandle` | retained — unchanged |
| `packages/constellation/src/vendor/mini-helix/mini-helix-runner.ts` | `ModelHandle, ModelCompletionOpts` | retained — unchanged |
| `packages/constellation/src/vendor/mini-helix/mini-helix-types.ts` | `ModelHandle` | retained — unchanged |
| `packages/helix/src/index.ts` | `ModelPool` (type; `setModelPool`) | retained acquire-shim type — unchanged |
| `packages/constellation/src/constellation-orchestrator.ts` | `ModelPool` (type; `setModelPool`) | retained acquire-shim type — unchanged |
| `packages/host/src/vendor/core/intelligence/context-distiller.ts` | `ModelPool` (type; `setModelPool`) | retained type (host vendored) |
| `packages/host/src/daemon.ts` | `ModelPool` (class via `import('@cassicore/model-pool')`) | **delegate/construction** — see §2; retains the acquire-cast but constructs the pool |
| `packages/host/src/vendor/core/intelligence/workspace/radiance-loop.ts` | `ModelHandle` (factory shape) | retained type |

After the split **no mind consumer imports any delegate symbol** (FallbackManager,
BudgetManager, BillingModel, budget/billing types, etc.).

---

## 2. DELEGATE surface — P4 deletes or replaces

### 2a. Pool machinery classes (all consumed ONLY inside the model-pool package today — verified by grep, plus host's pool construction)

| File | Exported symbols | Consumed by (today) | What replaces it at P4 |
|---|---|---|---|
| `src/fallback-manager.ts` | `FallbackManager` (+ chain/circuit internals) | `index.ts` (ModelPool ctor), `model-handle.ts` (failure reporting) | Dropped. ohmypi owns provider routing/fallback. Handle's `determineFailureReason`/`reportFailure` paths removed. |
| `src/budget-manager.ts` | `BudgetManager` | `index.ts`, `model-handle.ts` | Dropped. ohmypi owns quota/budget; retained handle becomes a thin cast. |
| `src/capability-cache.ts` | `CapabilityCache` | `index.ts` (ModelPool ctor) | Replaced by ohmypi provider capability resolution. |
| `src/model-capabilities.ts` | `ModelCapabilitiesFetcher` | `capability-cache.ts`, `index.ts` | Replaced by ohmypi; the `ModelCapabilities` *type* survives (retained). |
| `src/billing-models.ts` | `BillingModel` enum, `RequestCounter`, `CopilotRequestCounter`, `TokenRequestCounter`, `AlibabaRequestCounter`, `getBillingModel`, `getRequestCounter`, `getCostTier`, `UsageSnapshot` | `budget-manager.ts`, `capability-cache.ts`, `index.ts`, `types.ts` | Deleted. Note dependency: imports `CostClassifier` from `@cassicore/providers` (which itself is DELEGATE/DELETE in §30) — both die together. |

### 2b. Delegate-adjacent types in `src/types.ts` (die with the pool)

`BillingModel` (`§79`), `BudgetLimits`, `BudgetUsage`, `BudgetScope`, `BudgetTier`,
`BudgetWarning` (`§97-166`), `ModelSlotConfig`, `FallbackChain` (`§40-71`),
`PoolEvent` (`§217`), `CircuitState` (`§209`), `ModelPoolConfig` (`§290`,
incl. `blockedProviders`/`allowedModels` rate-limit tie-ins), `PoolStats` (`§329`).

- `ModelPoolConfig`/`PoolStats` are currently re-exported from the barrel for the
  host (`packages/host/src/daemon.ts` constructs `new ModelPool({ fallbackChains,
  budgetScopes, ... })` and reads stats/wiring). They are the **host's** delegate
  wiring surface — NOT retained mind surface. P4 removes them with the class.

### 2c. The `ModelPool` class itself (`src/index.ts`)

The class is the **delegate pool implementation** that the host currently
constructs:

```
packages/host/src/daemon.ts:1443-1470  new ModelPool({ fallbackChains, budgetScopes, ... }); setProviders(providers)
packages/host/src/daemon.ts:1474      intelligence.helix.setModelPool(helixModelPool)          // retained acquire-cast
packages/host/src/daemon.ts:1482      intelligence.constellation.setModelPool(helixModelPool)  // retained acquire-cast
packages/host/src/daemon.ts:2317,2333 helixModelPool.acquire('unity', …)/acquire('mini-helix:brainstem', …)
packages/host/src/daemon.ts:2479      meditation handleFactory → helixModelPool.acquire('unity', …)
```

**At P4:** replace the host's `new ModelPool(...)` construction with an
**ohmypi-backed shim** — a `mind_complete`-centered acquirer (per focus-plan §2.3 /
`mind_complete` bridge) — so the retained `setModelPool(acquire-shim)` calls
still typecheck and run. The retained `ModelPool` *type* (acquire shape) is what
survives; the class body is deleted.

---

## 3. What retains vs. what routes where (model-access mapping)

Per `CASSICORE-FOCUS-PLAN.md` §2.3:
- **Primary:** every turn-structured mind loop (helix posture runners,
  constellation strategies, mini-helix brainstem, cognitive-feed) becomes an
  **ohmypi task agent** → `handle.stream(messages)` is replaced by launching an
  agent session.
- **Fallback:** pure single-completion primitives (corpus-LLM summarizer,
  brainstem-LLM) go through the **`mind_complete` bridge tool** → the retained
  `ModelHandleImpl.complete()`/`stream()` can be implemented as one
  `mind_complete` call.

The retained port surface `src/ports/index.ts` is the compile-time contract for
both routes; at P4 its runtime (currently `ModelHandleImpl` over
`providerInstance.complete`) is retargeted behind that interface.

---

## 4. P4 executor checklist — **DONE (2026-08-14, P4 model-access cutover)**

> **Status: COMPLETE.** Model-access cutover executed in P4. The retained `ModelHandle`
> seam now routes through an injected `mind_complete` transport
> (`src/mind-complete.ts`, mirroring the spine bridge); the `ModelPool` class was
> replaced by `createMindCompleteAcquirer(...)` — a thin ohmypi-backed acquirer
> keeping the `acquire/release → ModelHandle` contract. Host + model-pool no
> longer import `@cassicore/providers`/`@cassicore/ai` (zero importers; both
> packages deleted). Pool-machinery suites died (model-pool 32 → 10 retained-handle
> tests).

1. ✅ `git rm` (history-preserving): `fallback-manager.ts`, `budget-manager.ts`,
   `capability-cache.ts`, `model-capabilities.ts`, `billing-models.ts` and the
   delegate types in `types.ts`.
2. ✅ Stripped budget/fallback fields from `ModelHandleImpl` + `ModelHandle`
   (`budgetScope?`), and dropped `determineFailureReason` — the retained handle
   is a `mind_complete`-backed cast (`src/model-handle.ts`).
3. ✅ Replaced the `ModelPool` class in `index.ts` with a thin ohmypi-backed
   acquirer — `createMindCompleteAcquirer({ transport, logger })` keeps
   `acquire`/`release` returning a retained `ModelHandle` (interface `ModelPool`
   retained for `setModelPool`).
4. ✅ Deleted `ModelPoolConfig`/`PoolStats`/`fallbackChains`/`budgetScopes` wiring
   from the host (`daemon.ts` §1443-1470 → `createMindCompleteAcquirer(...)`).
5. ✅ Deleted `@cassicore/providers` dep from the package manifest
   (`billing-models.ts` was its only consumer); `@cassicore/ai` dep also removed.
6. ✅ Re-ran retained mind suites (helix 75, constellation 568, mini-helix 21) +
   host 17. model-pool's own 32 tests (pool machinery) died with the class;
   replaced by 10 retained-handle tests.

**Shim design (the retained acquire contract):**
```ts
createMindCompleteAcquirer({ transport, logger })
  .acquire(slot, template?, sessionId?, override?) → Promise<ModelHandle>
```
Each handle is a `ModelHandleImpl` bound to `transport` (a `MindCompleteTransport`,
mirroring the spine `mind_complete` bridge). `complete()` returns one `TurnResult`;
`stream()` is a single-shot adaptation (one `token` chunk + `done`). The default
transport throws a documented 'not wired' error — the transitional P4 state until
the spine/ohmypi path is live (P5/P6).

---


**Test impact (P2):** no tests deleted — model-pool 32 still green; machinery kept.

---

## 5. Verified grep (P2) — no retained mind package imports delegate symbols

`grep -rE "FallbackManager|BudgetManager|CapabilityCache|billing|BillingModel|ModelPoolConfig|PoolStats" packages/{helix,constellation,mini-helix}/src` → **zero** matches on retained names; those files only touch `ModelHandle`/`ModelCompletionOpts`/`ModelPool` (type).
