# P5 — Group B (`@cassicore/dreamer-reverie-subconscious`, `@cassicore/lamina-locus-bridge`, `@cassicore/training-trust-ledger`, `@cassicore/workspace`, `@cassicore/embeddings`) — Migration Table (Planning Deliverable)

**Sources (READ-ONLY, D:):** `core/intelligence/{dreamer,reverie,subconscious}`, `{lamina,locus-bridge}`, `{training,trust-ledger}`, `{workspace,code-analysis}`, `{embeddings,shared}` — all under `D:\carina\workspaces\cassicore\core\intelligence\`
**Destinations:** `C:\Users\Carina\Workspaces\CassiCore\packages\{dreamer-reverie-subconscious,lamina-locus-bridge,training-trust-ledger,workspace,embeddings}\src\`
**Recon:** `C:\Users\Carina\Workspaces\CassiCore\recon-data.json`
**Plan:** `C:\Users\Carina\Workspaces\CassiCore\CASSI-MIND-PLAN.md` §5-P5 (Group B), §4, §3e.1 (registry seam)
**Exemplars (house format):** `P1-foundation-migration-table.md`, `P2-helix-migration-table.md`, `P3-flux-team-mini-helix-migration-table.md`, `P4-mnemic-field-migration-table.md`
**Date:** 2026-08-13
**Status:** PLANNING — executor applies rules verbatim in a later wave. Nothing migrated, nothing committed.

> **Constraint honored:** no file under `D:\carina\workspaces\cassicore` is modified (plan §5 line 27). This
> deliverable is the ONLY file written by this drafting pass; it is NOT git-added/committed (a parallel
> session is committing in the workspace — this file must stay untracked; read-only on D:).

> **Five packages, one phase, five independent imports.** This phase migrates FIVE `@cassicore/*` packages
> (plan §5-P5, Group B). Each has its own dest layout, vendor tree, and rewrite table: **Part A =
> `@cassicore/dreamer-reverie-subconscious`**, **Part B = `@cassicore/lamina-locus-bridge`**,
> **Part C = `@cassicore/training-trust-ledger`**, **Part D = `@cassicore/workspace`**,
> **Part E = `@cassicore/embeddings`**. They share the P1 foundation substrate and several inbound/outbound
> vendor stubs already committed in the landed packages (foundation P1, helix P2, flux-team P3, mini-helix P3,
> constellation pre-existing). Sequencing note: Parts A/B/D import OTHER Group-B packages' symbols (reverie→lamina,
> workspace→none, subconscious→none), but since all five land in the same phase those become `@cassicore/*`
> package imports once both are present (executor orders the rewires so the owner package publishes first).

> **Grouping adjusted from the plan's P5 table — evidence-based (see Open Flag 1).** The plan's §5-P5 grouping
> scattered these dirs as `@cassicore/reflective` (dreamer/reverie/subconscious), `@cassicore/lamina`
> (lamina/locus-bridge/workspace/global-workspace), `@cassicore/trust` (training/trust-ledger/permission-oracle),
> `@cassicore/workspace` (workspace/code-analysis/context-distiller/module-session-registry/posture-store), and
> `@cassicore/embeddings` (embeddings/embedding-service + shared/*). The task brief's explicit P5-Group-B package
> set (authoritative) is followed here: the five packages below, with each dir assigned to exactly one package.
> Deliberate diffs from the plan (flagged): (1) `lamina`+`locus-bridge` are grouped BOTH here AND the plan's
> `@cassicore/lamina` row — the brief puts `workspace`/`code-analysis` in a separate `@cassicore/workspace`
> package rather than folding them into lamina; (2) `context-distiller.ts`, `module-session-registry.ts` are
> NOT Group-B dirs (they are standalone siblings under `core/intelligence/`) — they are left as vendor stubs and
> their owning-package placement is deferred (§Open Flag 3); (3) `shared/*` moves with `@cassicore/embeddings`
> per the brief (plan row had `posture-store` under workspace); (4) `permission-oracle` is NOT Group B (P5-A/park).

---

# PART A — `@cassicore/dreamer-reverie-subconscious`

**Sources (READ-ONLY, D:):** `core/intelligence/dreamer/`, `core/intelligence/reverie/`, `core/intelligence/subconscious/`
**Destinations:** `packages/dreamer-reverie-subconscious/src/{dreamer,reverie,subconscious}/`

## A1. Live-set (files to migrate)

The three source dirs are FLAT (0 subdirectories each; verified). Liveness from `recon-data.json`
(`deadFiles` / `uncertainFiles`): **0 DEAD, 0 UNCERTAIN** across all three dirs — every file is LIVE.

**`src/dreamer/*.ts` — 4 files (depth 1)**
| # | source (D:) | dest (packages/dreamer-reverie-subconscious/src/) | bytes | recon verdict |
|---|---|---|---|---|
| 1 | `dreamer/index.ts` | `dreamer/index.ts` | 10253 | LIVE (entry barrel — `DreamerModule extends BaseCognitiveModule`, §A4a) |
| 2 | `dreamer/dream-engine.ts` | `dreamer/dream-engine.ts` | 13889 | LIVE |
| 3 | `dreamer/dream-prompt.ts` | `dreamer/dream-prompt.ts` | 7627 | LIVE |
| 4 | `dreamer/types.ts` | `dreamer/types.ts` | 4333 | LIVE |

**`src/reverie/*.ts` — 7 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 5 | `reverie/index.ts` | `reverie/index.ts` | 27442 | LIVE (entry barrel — `ReverieModule extends BaseCognitiveModule`, §A4a) |
| 6 | `reverie/prompt.ts` | `reverie/prompt.ts` | 7103 | LIVE |
| 7 | `reverie/retrieval-labeler.ts` | `reverie/retrieval-labeler.ts` | 5605 | LIVE |
| 8 | `reverie/retrieval-labeler-types.ts` | `reverie/retrieval-labeler-types.ts` | 2124 | LIVE |
| 9 | `reverie/tool-filter.ts` | `reverie/tool-filter.ts` | 3727 | LIVE |
| 10 | `reverie/trigger.ts` | `reverie/trigger.ts` | 3847 | LIVE |
| 11 | `reverie/types.ts` | `reverie/types.ts` | 2470 | LIVE |

**`src/subconscious/*.ts` — 6 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 12 | `subconscious/index.ts` | `subconscious/index.ts` | 19300 | LIVE (entry barrel — `Subconscious` class + `createSubconscious`, §A4a) |
| 13 | `subconscious/event-stream.ts` | `subconscious/event-stream.ts` | 9618 | LIVE |
| 14 | `subconscious/heuristic-observer.ts` | `subconscious/heuristic-observer.ts` | 33165 | LIVE |
| 15 | `subconscious/llm-observer.ts` | `subconscious/llm-observer.ts` | 22407 | LIVE |
| 16 | `subconscious/system-model.ts` | `subconscious/system-model.ts` | 26406 | LIVE |
| 17 | `subconscious/types.ts` | `subconscious/types.ts` | 5330 | LIVE |

**Live-set count (Part A): 17 files** (4 dreamer + 7 reverie + 6 subconscious). **0 DEAD, 0 quarantined-uncertain.**

> **`reverie/index.ts` package entry vs registry:** `reverie/index.ts` exports `ReverieModule extends BaseCognitiveModule`
> (priority 14). It is manually instantiated in `createIntelligence()` (`new ReverieModule(logger)`), NOT
> discovered via the IntelligenceRegistry — but `reverie` is also NOT in the daemon registry skip-set
> (daemon.ts:2032-2051 lists `subconscious`, `embeddings`, `dreamer`, `trust-ledger` but omits `reverie`). This is
> the exact P7 host wiring gap to close (see §A4a / Open Flag 2): the P7 explicit-wiring replacement must register
> `ReverieModule` exactly as `createIntelligence()` does today and must not let the host auto-discover a second
> instance.

---

## A2. Rewrite table (Part A — mechanical string-substitution pairs)

**Mirror rule for vendor stubs.** Every escaping (non-Part-A-live, non-foundation, non-landed-package) target is
reproduced as a **type stub at `src/vendor/<rel-path-from-D-repo-root>.ts`** (Constellation A3 / P1–P4 pattern;
faithful type surface; runtime symbols flagged).

**Depth rule (P2/P4 lesson (a) — CRITICAL).** All 17 Part-A files land at depth 1 (`src/<dir>/file.ts`). Two
prefix forms apply uniformly:
- Foundation specifiers: any `../../../types/*.js`, `../../config/system-settings.js`, `../base/cognitive-module.js`,
  `../../utils/paths.js` → **`@cassicore/foundation`** (package specifier — no depth prefix needed).
- Vendor specifiers (non-foundation escapes): from `src/<dir>/file.ts`, the vendor stub prefix is **`../../vendor/...`**
  (two hops: `src/<dir>/` → `src/` → `src/vendor/`). This is uniform across all Part-A files.
- Landed-package specifiers: `../base/cognitive-module.js`→`@cassicore/foundation`, `../flux-team/…`→`@cassicore/flux-team`,
  `../mnemic-field/…`→`@cassicore/mnemic-field`, `../lamina/…`→`@cassicore/lamina-locus-bridge` (Part B, same phase).

**Foundation rule.** Every import resolving to the P1 shared substrate → `@cassicore/foundation` (named import;
executor verifies each symbol in the landed foundation barrel — §A4d `[VERIFY]`).

**Landed-package rule.** Every import of an ALREADY-published package (foundation P1, helix P2, flux-team/mini-helix
P3, constellation pre-existing, and the four sibling Group-B packages in THIS phase) → the real `@cassicore/*`
package import IF the symbol is exported by that package's barrel; else a vendor stub. §A2.2 marks the resolved cases.

**Extension rule.** Source keeps `.js` import specifiers verbatim; only the specifier is rewritten (extension
preserved; the `.js` is dropped for `@cassicore/*` package specifiers).

**Scope rule.** DO NOT touch Node builtins (`node:crypto/fs/path/os/util`), npm (`better-sqlite3`, `uuid`), `./X.js`
same-dir internal, or `../<same-package-dir>/X.js` intra-package cross-dir imports (all preserved under the mirror).
REWRITE only foundation/landed/vendor escapes. Apply only to actual `import`/`import type`/re-export/inline
`import('…')`/`require()` statements — NOT string/comment content (several files carry `// REMOVED:`-style comments
and doc-comment singleton notes like `import { getEmbeddingService } from './embedding-service.js'` INSIDE a comment
in `embedding-service.ts` — do NOT rewrite those; they are provenance notes).

### A2.1 Foundation + landed-package rewrite pairs (→ `@cassicore/*`)

| original specifier | dest | consumed by (files + symbols) |
|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | dreamer/dream-engine (`ILogger`), dreamer/index (`ILogger`, `IEventBus`), reverie/index (`ILogger`, `IEventBus`), subconscious/event-stream (`ILogger`, `IEventBus`), subconscious/heuristic-observer (`ILogger`), subconscious/index (`ILogger`, `IEventBus`, `ILogger`+`IGlobalWorkspace`-typed), subconscious/llm-observer (`ILogger`, `IEventBus`), subconscious/system-model (`ILogger`) |
| `../../../types/intelligence.js` | `@cassicore/foundation` | dreamer/dream-engine (`DreamerConfig` — type via `../types`? no — verified: `MemoryConfig`-family), dreamer/index, subconscious/index, subconscious/llm-observer, subconscious/system-model |
| `../../../types/runtime.js` | `@cassicore/foundation` | subconscious/index, subconscious/llm-observer (`CompletionOpts`, `Message`, `ContentBlock`, `CompletionChunk`) |
| `../../../types/events.js` | `@cassicore/foundation` | subconscious/event-stream, subconscious/heuristic-observer, subconscious/system-model (`RuntimeEvent`, `EventOf`, `Unsubscribe`) |
| `../../../types/flux-team.js` | `@cassicore/foundation` | subconscious/llm-observer (type-only `Report`) |
| `../../config/system-settings.js` | `@cassicore/foundation` | dreamer/index, reverie/index, subconscious/llm-observer (MODEL_DEFAULTS / SYSTEM_SETTINGS) |
| `../base/cognitive-module.js` | `@cassicore/foundation` | dreamer/index (`BaseCognitiveModule`), reverie/index (`BaseCognitiveModule`) |
| `../gaming-mode.js` | `@cassicore/foundation` | dreamer/index, subconscious/llm-observer (`isGamingMode` — runtime fn) |
| `../reasoning-bank/index.js` + `../reasoning-bank/types.js` | (see §A2.2 — NOT landed; vendor) | — |
| `../../runtime/audit/index.js` | (see §A2.2 — NOT landed; vendor) | — |

### A2.2 Vendor stub rewrite pairs (→ `../../vendor/<rel-from-D-repo-root>.js`)

| original specifier(s) | dest stub (`src/vendor/…`) | consumed by (symbols) | runtime-or-type |
|---|---|---|---|
| `../reasoning-bank/index.js` (dreamer/dream-engine, dreamer/index) | `../../vendor/core/intelligence/reasoning-bank/index.js` | `ReasoningBank`, `createReasoningBank` | **RUNTIME** (see Open Flag 4) |
| `../reasoning-bank/types.js` (dreamer/dream-engine) | `../../vendor/core/intelligence/reasoning-bank/types.js` | `ReasoningBankConfig`, `ReasoningBankEntry` | type |
| `../lamina/index.js` (reverie/index) | **`@cassicore/lamina-locus-bridge`** (Part B, same phase) | `LaminaField` (type — `setLamina`) | landed-package re-point |
| `../lamina/types.js` (reverie/prompt) | **`@cassicore/lamina-locus-bridge`** (Part B) | `LaminaCaller` (type) | landed-package re-point |
| `../mnemic-field/index.js` (reverie/index) | **`@cassicore/mnemic-field`** (P4 landed) | `MnemicField` (type) | landed-package re-point |
| `../mnemic-field/types.js` (reverie/index) | **`@cassicore/mnemic-field`** (P4 landed) | `EngramType`, `SynapseType` | landed-package re-point |
| `../mnemic-field/cortex.js` (reverie/index) | **`@cassicore/mnemic-field`** (P4 landed) | `Cortex` (type) | landed-package re-point |
| `../../runtime/audit/index.js` (reverie/index ×2, reverie/types) | `../../vendor/core/runtime/audit/index.js` | `AuditStore`, `AuditRecord`, `AuditLogLevel` | **RUNTIME** (see Open Flag 4) |
| `../../runtime/audit/index.js` (subconscious: none — subconscious does NOT import audit) | — | — | n/a |
| `../cortex/index.js` (subconscious/index, subconscious/llm-observer) | `../../vendor/core/intelligence/cortex/index.js` | `CorticalField` (type) | type |
| `../module-session-registry.js` (subconscious/index, subconscious/llm-observer) | `../../vendor/core/intelligence/module-session-registry.js` | `ModuleSessionRegistry` (type) | type |
| `../session-digest.js` (subconscious/index) | `../../vendor/core/intelligence/session-digest.js` | `SessionDigest`, `DigestOptions` | type |
| `../flux-team/global-blackboard-registry.js` (subconscious/llm-observer) | **`@cassicore/flux-team`** (P3 landed) | `GlobalBlackboardRegistry` (type) | landed-package re-point |

> **`gaming-mode.js` → foundation?** `gaming-mode.js` is `core/intelligence/gaming-mode.ts` — a standalone
> sibling, NOT part of foundation (it is not `types/*`, `config/*`, `base/*`, `utils/paths`, or `phrase-prototypes`).
> Per the plan's P5 grouping, `gaming-mode` is an "other remaining sibling" folding into a coalesced auxiliary
> package, NOT foundation. **Correction to §A2.1:** `../gaming-mode.js` is a **VENDOR target**, not foundation.
> → `../../vendor/core/intelligence/gaming-mode.js` (`isGamingMode` — RUNTIME). See Open Flag 5.

### A2.3 Internal (unchanged) + builtins/npm

- **Internal (stay valid under mirror, 0 rewrites):** every `./X.js` same-dir sibling (e.g. dreamer/dream-engine →
  `./dream-prompt.js`+`./types.js`; reverie/index → `./prompt.js`+`./retrieval-labeler.js`+`./retrieval-labeler-types.js`
  +`./tool-filter.js`+`./trigger.js`+`./types.js`; subconscious/index → `./event-stream.js`+`./heuristic-observer.js`
  +`./llm-observer.js`+`./system-model.js`+`./types.js`). **No intra-Package-A cross-dir imports** (dreamer/reverie/
  subconscious have no imports between each other — verified).
- **Builtins/npm (unchanged):** `uuid` (subconscious/heuristic-observer, subconscious/llm-observer,
  subconscious/system-model), `node:crypto/fs/path/os` (as present). 0 `better-sqlite3` in Part A.

### A2.4 Rewrite-pair tally (Part A)

| class | unique targets | files touched |
|---|---|---|
| **Foundation + landed (`@cassicore/*`)** | **9** (interfaces, intelligence, runtime, events, flux-team/types, system-settings, cognitive-module, gaming-mode→**vendor**, reason-bank→vendor) — net **7 foundation** + **2 landed** (flux-team GBR is landed, gaming-mode/reasoning-bank/audit/cortex/module-session/session-digest are vendor) | 17 |
| **Vendor type/runtime stub (`../../vendor/...`)** | **7** (reasoning-bank/index, reasoning-bank/types, runtime/audit, cortex/index, module-session-registry, session-digest, gaming-mode) | 12 |
| **Internal (unchanged `./X.js`)** | **0 rewrite pairs** | — |
| **Builtins/npm (unchanged)** | **0 rewrite pairs** | — |
| **TOTAL rewrite pairs** | **16 unique targets** (9 package + 7 vendor) | 17 files carry ≥1 rewrite |

Global per-specifier replacement (some occur MULTIPLE times: `react`-style no — `../../runtime/audit/index.js` ×2 in
reverie/index.ts:36,37; `../cortex/index.js` in subconscious/index + llm-observer).

---

## A3. Destination layout (Part A)

```
packages/dreamer-reverie-subconscious/
  package.json                     # name: "@cassicore/dreamer-reverie-subconscious", type: module,
                                   #   deps: @cassicore/foundation, uuid  (§A4c)
  tsconfig.json                    # rootDir src/ outDir dist/ declaration true
  vitest.config.ts                 # ported tests (tests/dreamer, reverie, subconscious)
  README.md
  src/
    dreamer/                       # depth 1
      index.ts                     # entry barrel: DreamerModule (BaseCognitiveModule), createDreamer
      dream-engine.ts  dream-prompt.ts  types.ts
    reverie/                       # depth 1
      index.ts                     # entry barrel: ReverieModule (BaseCognitiveModule)
      prompt.ts  retrieval-labeler.ts  retrieval-labeler-types.ts
      tool-filter.ts  trigger.ts  types.ts
    subconscious/                  # depth 1
      index.ts                     # entry barrel: Subconscious class + createSubconscious
      event-stream.ts  heuristic-observer.ts  llm-observer.ts  system-model.ts  types.ts
    vendor/                        # stubs ONLY — mirror original D: rel-paths (§A2.2)
      core/
        runtime/audit/index.ts     # AuditStore, AuditRecord, AuditLogLevel (RUNTIME — see Open Flag 4)
        intelligence/
          reasoning-bank/index.ts  # ReasoningBank (RUNTIME), createReasoningBank
          reasoning-bank/types.ts  # ReasoningBankConfig, ReasoningBankEntry (type)
          cortex/index.ts          # CorticalField (type)
          module-session-registry.ts  # ModuleSessionRegistry (type)
          session-digest.ts        # SessionDigest, DigestOptions (type)
          gaming-mode.ts           # isGamingMode (RUNTIME)
```

**Internal-import consequences:** all `./X.js` siblings preserved by the per-dir mirror. Cross-dir reverie→lamina /
reverie→mnemic-field / subconscious→cortex / subconscious→module-session-registry / subconscious→flux-team resolve to
`@cassicore/*` (Part B, P4, P3). Vendor stubs: one `../../vendor/...` hop from any `src/<dir>/` file.

### A3.1 Repoint log (Part A — OUTBOUND stubs this package now OWNS)

None of the three Part-A dirs was previously vendored as a group, but **`dreamer/types.ts`** (`DreamerConfig`) was
vendored in foundation (P1):

| consumer stub (`src/vendor/...`) | exported symbols | this phase re-points it to |
|---|---|---|
| foundation (P1) `core/intelligence/dreamer/types.ts` | `DreamerConfig` (type, re-exported by foundation `types/intelligence.ts`) | `@cassicore/dreamer-reverie-subconscious` |

### A3.2 Repoint log (Part A — INBOUND stubs this package consumes, owned elsewhere)

Part A's own vendor stubs re-point to their owning packages at later phases:
| this-package stub | owning package | re-point at |
|---|---|---|
| `core/reasoning-bank/{index,types}.ts` | `@cassicore/auxiliary` (or schema-pool P5-A) | P5-A / P6 |
| `core/intelligence/cortex/index.ts` | `@cassicore/cortex` (P5-A) | P5-A |
| `core/intelligence/module-session-registry.ts` | host/wiring (P7) | P7 (§Open Flag 3) |
| `core/intelligence/session-digest.ts` | host/wiring (P7) | P7 |
| `core/intelligence/gaming-mode.ts` | `@cassicore/auxiliary` (P5-A) | P5-A |
| `core/runtime/audit/index.ts` | `@cassicore/events` (P6) | P6 |

---

## A4. Known-hard items (Part A)

### A4a. Registry-discovery surface — THREE subclasses, all explicitly wired (P7 note)

All three Part-A `index.ts` files export an intelligence entry that the host must wire **explicitly**, NOT
auto-discover, to preserve the P1/P2/P3 registry deal:

- **`dreamer/index.ts`**: `export class DreamerModule extends BaseCognitiveModule` (name `'dreamer'`) + factory
  `createDreamer(logger, config?)` returning `DreamerModule`. **In daemon registry skip-set** (daemon.ts:2046).
  `createIntelligence()` calls `createDreamer(...)` and `dreamer.setFullMemory(memory)` (+ optional
  `setReasoningBank`). Barrel also re-exports `dream-engine` and `types`.
- **`reverie/index.ts`**: `export class ReverieModule extends BaseCognitiveModule` (name `'reverie'`, priority 14) +
  `createReverieModule` (not present — instantiated directly `new ReverieModule(logger)`).
  **NOT in daemon registry skip-set** — the P7 host MUST add `reverie` to its explicit-wiring (or skip) set or it
  would be auto-discovered twice. Barrel sets `lamina`/`audit`/`mnemic` via `setLamina`/`setAudit`/`setMnemic`.
- **`subconscious/index.ts`**: `export class Subconscious` (does NOT extend BaseCognitiveModule) + factory
  `createSubconscious(logger, config?)`. **In daemon registry skip-set** (daemon.ts:2038). Wired explicitly:
  `subconscious.setMemory`, `setLiveSessionGetter`, `setProvider` (daemon), and `reconcile`.
- `trust-ledger` (Part C) and the embeddings singleton (Part E) are the other registry-skip-set members in Group B
  (Part C §C4a, Part E §E4a).

**P7 host contract:** the `@cassicore/host` (P7) explicit-wiring replacement must register exactly these modules
(DreamerModule, ReverieModule, Subconscious-as-a-module), preserve each class's public method surface
(`setFullMemory`, `setReasoningBank`, `setLamina`, `setAudit`, `setMnemic`, `setMemory`, `setLiveSessionGetter`,
`setProvider`, `reconcile`), and keep the registry skip-set equivalent for `dreamer`/`reverie`/`subconscious` so no
duplicate instances arise. Do NOT rename barrel exports.

### A4b. `reverie` auto-discovery trap (the one the plan did not name)

`reverie` is conspicuously ABSENT from the daemon registry skip-set (daemon.ts:2032-2051 lists `subconscious`,
`embeddings`, `dreamer`, `trust-ledger`, `permission-oracle`, plus others — but not reverie). Since
`ReverieModule extends BaseCognitiveModule` (name `reverie`), a registry `discover()` over `intelligence/` WOULD pick
it up unless excluded. In the CURRENT source `createIntelligence()` manually does `new ReverieModule(logger)` and the
registry scan's skip-set simply omits reverie — which means today there is a latent risk of double-instantiation that
the source tolerates only because the registry directory-scan is not actually run over the compiled dir in every
deployment. **For the P7 host, this MUST be resolved:** either add `reverie` to the host's explicit-wiring skip-set
(the safe default mirroring dreamer/trust-ledger) or deliberately auto-discover it and remove `new ReverieModule` from
`createIntelligence()`. Default: treat reverie exactly like dreamer (explicit-wire + skip). Open Flag 2.

### A4c. Runtime vendored symbols in Part A (must be faithful impls, not bare type stubs)

Four Part-A vendor/landed targets are RUNTIME, not type-only (P2 Open-Flag-5 / P4 Open-Flag-8 pattern):
- **`reasoning-bank/index.js` (+types)**: `createReasoningBank` is a runtime factory dreamer calls in its
  constructor/init; `ReasoningBank` methods are invoked. **Default:** vendor an exact-copy self-contained stub
  (reasoning-bank is a pure in-memory registry + query engine — no host deps beyond `ILogger`); re-point to the
  owning auxiliary/coalesced package at P5-A/P6.
- **`runtime/audit/index.js` `AuditStore`**: a runtime class (SQLite-backed audit ledger). dreamer/reverie WRITE to
  it. **Default:** port `AuditStore` as an exact self-contained stub OR a confirmed-safe minimal in-memory impl; the
  real persistence port lives in P6 `@cassicore/events`. Mark `[VERIFY]` the copied impl matches source.
- **`gaming-mode.js` `isGamingMode`**: pure boolean helper (`process.env`/config read) — port exact copy.
- **`lamina/index.js`/`lamina/types.js`** and **`mnemic-field/*`**: these re-point to the REAL packages (Part B / P4),
  NOT stubs — no runtime stub needed.
- **`cortex/index.js` `CorticalField`** (subconscious): type-only in subconscious (used for field typing + wiring)
  → clean type stub. `module-session-registry` / `session-digest`: type-only → clean type stubs; `session-digest` is
  RUNTIME-consumed by the daemon but subconscious only references it by type.

### A4d. Foundation barrel coverage for Part A (verify before rewiring)

Part A imports foundation modules: `interfaces`, `intelligence`, `runtime`, `events`, `flux-team/types`,
`system-settings`, `base/cognitive-module`. All are P1-live (P1 exemplar rows 1,3,2,19,5, + config/base). **The
landed foundation `src/index.ts` barrel MUST re-export:** `ILogger`, `IEventBus`, `RuntimeEvent`, `EventOf`,
`Unsubscribe`, `CompletionOpts`, `Message`, `ContentBlock`, `CompletionChunk`, `MODEL_DEFAULTS`, `SYSTEM_SETTINGS`,
`BaseCognitiveModule`, and the `flux-team` type surface (`Report`, …) — all named value/type exports carried from the
source modules. `isGamingMode` is NOT foundation (it is a sibling util; §Open Flag 5 — vendor, not foundation).

---

# PART B — `@cassicore/lamina-locus-bridge`

**Sources (READ-ONLY, D:):** `core/intelligence/lamina/`, `core/intelligence/locus-bridge/`
**Destinations:** `packages/lamina-locus-bridge/src/{lamina,locus-bridge}/`

## B1. Live-set (files to migrate)

Both source dirs FLAT (0 subdirs). Recon: **0 DEAD, 0 UNCERTAIN** — all files LIVE.

**`src/lamina/*.ts` — 6 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 1 | `lamina/index.ts` | `lamina/index.ts` | 679 | LIVE (entry barrel — `LaminaField`, `LaminaStore`, re-exports) |
| 2 | `lamina/lamina-field.ts` | `lamina/lamina-field.ts` | 4969 | LIVE |
| 3 | `lamina/lamina-store.ts` | `lamina/lamina-store.ts` | 14378 | LIVE |
| 4 | `lamina/claude-memory-importer.ts` | `lamina/claude-memory-importer.ts` | 9228 | LIVE |
| 5 | `lamina/pineal-bridge.ts` | `lamina/pineal-bridge.ts` | 2542 | LIVE |
| 6 | `lamina/types.ts` | `lamina/types.ts` | 4315 | LIVE |

**`src/locus-bridge/*.ts` — 6 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 7 | `locus-bridge/index.ts` | `locus-bridge/index.ts` | 19906 | LIVE (entry barrel — `LocusBridge` class) |
| 8 | `locus-bridge/context-curator.ts` | `locus-bridge/context-curator.ts` | 10517 | LIVE |
| 9 | `locus-bridge/history-scorer.ts` | `locus-bridge/history-scorer.ts` | 12330 | LIVE |
| 10 | `locus-bridge/spark-extractor.ts` | `locus-bridge/spark-extractor.ts` | 7127 | LIVE |
| 11 | `locus-bridge/types.ts` | `locus-bridge/types.ts` | 7678 | LIVE |
| 12 | `locus-bridge/window-assembler.ts` | `locus-bridge/window-assembler.ts` | 12055 | LIVE |

**Live-set count (Part B): 12 files** (6 lamina + 6 locus-bridge). **0 DEAD, 0 quarantined.**

> **`locus-bridge/context-curator.ts` — cross-phase NOT-conflict resolved.** The plan's Appendix B-8 flagged a
> `context-curator.ts` [UNCERTAIN]. That is `helm`'s `core/intelligence/helix/context-curator.ts` (P2 scope, excluded
> there as tsconfig-excluded dead). The `locus-bridge/context-curator.ts` here is a DIFFERENT file (LIVE, imported by
> `locus-bridge/index.ts`) — no [UNCERTAIN] entry, migrates. Do not conflate.

---

## B2. Rewrite table (Part B — mechanical string-substitution pairs)

Same **Mirror / Foundation / Landed / Extension / Scope / Depth** rules as Part A (§A2). All Part-B files land at
depth 1. Vendor prefix `../../vendor/...`; foundation → `@cassicore/foundation`.

### B2.1 Foundation + landed-package rewrite pairs (→ `@cassicore/*`)

| original specifier | dest | consumed by (files + symbols) |
|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | lamina/claude-memory-importer (`ILogger`), lamina/lamina-field (`ILogger`), lamina/lamina-store (`ILogger`), lamina/pineal-bridge (`ILogger`), locus-bridge/context-curator (`ILogger`), locus-bridge/history-scorer (`ILogger`), locus-bridge/index (`ILogger`, `IEventBus`), locus-bridge/spark-extractor (`ILogger`), locus-bridge/window-assembler (`ILogger`) |
| `../../utils/paths.js` | `@cassicore/foundation` | lamina/claude-memory-importer (`getDataDir`), lamina/lamina-store (`getDataDir`) |
| `../../runtime/audit/index.js` | (see §B2.2 — vendor) | — |
| `../utils/prefixed-id.js` | (see §B2.2 — vendor) | — |
| `../pineal/types.js` | (see §B2.2 — vendor) | — |

### B2.2 Vendor stub rewrite pairs (→ `../../vendor/<rel-from-D-repo-root>.js`)

| original specifier(s) | dest stub (`src/vendor/…`) | consumed by (symbols) | runtime-or-type |
|---|---|---|---|
| `../../runtime/audit/index.js` (lamina/claude-memory-importer ×2, lamina/lamina-field, lamina/lamina-store, lamina/types) | `../../vendor/core/runtime/audit/index.js` | `AuditStore` (type + runtime wiring), `AuditRecord`, `AuditLogLevel` | **RUNTIME** (see Open Flag 4) |
| `../utils/prefixed-id.js` (lamina/lamina-store) | `../../vendor/core/intelligence/utils/prefixed-id.js` | `prefixedId` (runtime fn) | **RUNTIME** |
| `../pineal/types.js` (lamina/pineal-bridge) | `../../vendor/core/intelligence/pineal/types.js` | `PinealSnapshot`-family types | type |

### B2.3 Internal (unchanged) + builtins/npm

- **Internal (stay valid under mirror, 0 rewrites):** all `./X.js` same-dir siblings. **No cross-dir lamina↔locus-bridge
  imports** (locus-bridge is self-contained + foundation; lamina has no locus-bridge import) — verified.
- **Builtins/npm (unchanged):** `node:crypto`, `node:fs`, `node:os`, `node:path` (lamina), `better-sqlite3`
  (lamina/lamina-store). 0 `uuid` in Part B.

### B2.4 Rewrite-pair tally (Part B)

| class | unique targets | files touched |
|---|---|---|
| **Foundation (`@cassicore/foundation`)** | **2** (interfaces, paths) | 10 |
| **Vendor type/runtime stub (`../../vendor/...`)** | **3** (runtime/audit, utils/prefixed-id, pineal/types) | 5 |
| **Internal (unchanged `./X.js`)** | **0 rewrite pairs** | — |
| **Builtins/npm (unchanged)** | **0 rewrite pairs** | — |
| **TOTAL rewrite pairs** | **5 unique targets** | 12 files (10 with ≥1 rewrite) |

---

## B3. Destination layout (Part B)

```
packages/lamina-locus-bridge/
  package.json                     # name: "@cassicore/lamina-locus-bridge", type: module,
                                   #   deps: @cassicore/foundation, better-sqlite3
  tsconfig.json                    # rootDir src/ outDir dist/ declaration true
  vitest.config.ts
  README.md
  src/
    lamina/                        # depth 1
      index.ts                     # entry barrel: LaminaField, LaminaStore (+ re-exports)
      lamina-field.ts  lamina-store.ts  claude-memory-importer.ts  pineal-bridge.ts  types.ts
    locus-bridge/                  # depth 1
      index.ts                     # entry barrel: LocusBridge class + helper re-exports
      context-curator.ts  history-scorer.ts  spark-extractor.ts  types.ts  window-assembler.ts
    vendor/                        # stubs ONLY — mirror D: rel-paths (§B2.2)
      core/
        runtime/audit/index.ts     # AuditStore (RUNTIME), AuditRecord, AuditLogLevel
        intelligence/
          utils/prefixed-id.ts     # prefixedId (RUNTIME)
          pineal/types.ts          # PinealSnapshot-family types (type)
```

**Internal-import consequences:** all `./X.js` siblings preserved by mirror. Vendor stubs: one `../../vendor/...` hop.
Foundation `getDataDir` via `@cassicore/foundation` (ports seam).

### B3.1 Repoint log (Part B — OUTBOUND stubs now owned / INBOUND consumed)

**Inbound stubs this package now OWNS** (re-point consumer stubs → `@cassicore/lamina-locus-bridge`, delete stubs):
| consumer stub (`src/vendor/...`) | exported symbols | this phase re-points to |
|---|---|---|
| helix (P2) `core/intelligence/lamina/index.ts` | `LaminaField` (type) — helix-conductor, helix-posture-runner, helix-pipeline | `@cassicore/lamina-locus-bridge` |
| constellation (pre-existing) `lamina/index.ts` | `LaminaField` (type) — constellation-pipeline, constellation-orchestrator, helix-goal-lamina | `@cassicore/lamina-locus-bridge` |

**Part B's own vendor stubs → owning packages (later phases):**
| this-package stub | owning package | re-point at |
|---|---|---|
| `core/runtime/audit/index.ts` | `@cassicore/events` (P6) | P6 |
| `core/intelligence/utils/prefixed-id.ts` | `@cassicore/utils` (P6) | P6 |
| `core/intelligence/pineal/types.ts` | `@cassicore/cortex` (P5-A) | P5-A |

---

## B4. Known-hard items (Part B)

### B4a. Registry / discovery surface — NO BaseCognitiveModule in lamina-locus-bridge (P7 note)

Neither `lamina/index.ts` nor `locus-bridge/index.ts` exports a `BaseCognitiveModule` subclass.
- **lamina** (`index.ts`): barrel re-exports `LaminaField`, `LaminaStore`, `LaminaCaller`, types — a field + store
  library. `lamina` is NOT in the daemon registry skip-set (it has no discoverable module class) and is instantiated
  explicitly in `createIntelligence()` (`new LaminaField(logger)`) and wired to `constellation.setLamina`.
- **locus-bridge** (`index.ts`): exports `class LocusBridge` (NOT a BaseCognitiveModule; it takes
  `LocusBridgeDeps` with memory/logger/etc.) + `createLocusBridge` factories over helper exports
  (`ContextCurator`, `HistoryScorer`, `WindowAssembler`, `BridgeSparkExtractor`). Instantiated in
  `createIntelligence()` (`new LocusBridge({...})`). Barrel re-exports helper classes + `DEFAULT_LOCUS_BRIDGE_CONFIG`.

**P7 host contract:** wire `LaminaField` and `LocusBridge` explicitly (they are injected into constellation /
daemon), preserve the barrel export names (`LaminaField`, `LaminaStore`, `LocusBridge`, `ContextCurator`,
`HistoryScorer`, `WindowAssembler`, `BridgeSparkExtractor`, `DEFAULT_LOCUS_BRIDGE_CONFIG`, `DEFAULT_BRIDGE_LUMINANCE_WEIGHTS`).
Neither is registry-discovered.

### B4b. `LaminaStore` uses `better-sqlite3` + `prefixedId` (vendor RUNTIME fn)

`lamina-store.ts` opens `better-sqlite3` (lamina store DB under `getDataDir()`) and calls `prefixedId` (a small
`crypto.randomUUID`-based id prefixer) from `core/intelligence/utils/prefixed-id.js`. **Default:** add `better-sqlite3`
as a Part-B npm dep (matches P1/P2/P4 decision); port `prefixedId` as an exact self-contained copy in the vendor stub
(pure, no host deps); re-point to `@cassicore/utils` at P6.

### B4c. `claude-memory-importer.ts` — external one-way import + execSync (host-wired seam)

`claude-memory-importer.ts` (`ClaudeMemoryImporter`) scans Claude Code's per-project memory dir via `node:fs/os/path`
and imports notes into lamina via an audit trail (`AuditStore`). It is instantiated in `createIntelligence()` with
`new ClaudeMemoryImporter(logger, lamina, {}, undefined, memory, audit)` — cross-wired to foundation memory + audit.
**Default:** migrate the file as-is (it is LIVE + imported by lamina/index or createIntelligence); the `audit` it
writes to is the vendored `AuditStore` stub (Open Flag 4). It uses `node:fs`/`node:os`/`node:path` (builtins) + the
audit vendor stub — no subprocess spawn beyond the D: claude-code dir scan. Not a process entry.

### B4d. Packed note — `locus-bridge` is fully self-contained except foundation

locus-bridge has NO vendor escapes at all — only foundation `interfaces` + internal `./X.js`. Cleanest of the five
packages. The only "hard" part is the `LocusBridge` constructor deps (`memory`, `mongoose`-shaped session store, etc.)
which are type-wired via `LocusBridgeDeps` — those resolve to foundation types or the host.

---

# PART C — `@cassicore/training-trust-ledger`

**Sources (READ-ONLY, D:):** `core/intelligence/training/`, `core/intelligence/trust-ledger/`
**Destinations:** `packages/training-trust-ledger/src/{training,trust-ledger}/`

## C1. Live-set (files to migrate)

Both source dirs FLAT (0 subdirs). Recon: **0 DEAD, 0 UNCERTAIN** — all files LIVE.

**`src/training/*.ts` — 8 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 1 | `training/index.ts` | `training/index.ts` | 5902 | LIVE (entry barrel — `TrainingWarehouse` class) |
| 2 | `training/background-tagger-worker.ts` | `training/background-tagger-worker.ts` | 10790 | LIVE (tick-based worker class, NOT a process entry — §C4c) |
| 3 | `training/sdk-tagger.ts` | `training/sdk-tagger.ts` | 24016 | LIVE |
| 4 | `training/training-ingest.ts` | `training/training-ingest.ts` | 48636 | LIVE |
| 5 | `training/training-reader.ts` | `training/training-reader.ts` | 17293 | LIVE |
| 6 | `training/training-store.ts` | `training/training-store.ts` | 36872 | LIVE |
| 7 | `training/training-tagger.ts` | `training/training-tagger.ts` | 21317 | LIVE |
| 8 | `training/training-types.ts` | `training/training-types.ts` | 12168 | LIVE |

**`src/trust-ledger/*.ts` — 2 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 9 | `trust-ledger/index.ts` | `trust-ledger/index.ts` | 16370 | LIVE (entry barrel — `TrustLedger extends BaseCognitiveModule`, `createTrustLedger`) |
| 10 | `trust-ledger/types.ts` | `trust-ledger/types.ts` | 7549 | LIVE |

**Live-set count (Part C): 10 files** (8 training + 2 trust-ledger). **0 DEAD, 0 quarantined.**

---

## C2. Rewrite table (Part C)

Same rules as §A2. All files depth 1; vendor prefix `../../vendor/...`; foundation → `@cassicore/foundation`.

### C2.1 Foundation + landed-package rewrite pairs (→ `@cassicore/*`)

| original specifier | dest | consumed by (files + symbols) |
|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | training/background-tagger-worker, training/index, training/sdk-tagger, training/training-ingest, training/training-reader, training/training-store, training/training-tagger, trust-ledger/index (`ILogger`, `IEventBus`) |
| `../base/cognitive-module.js` | `@cassicore/foundation` | trust-ledger/index (`BaseCognitiveModule`) |
| `../flux-team/global-blackboard-registry.js` | **`@cassicore/flux-team`** (P3 landed) | training/training-tagger (`GlobalBlackboardRegistry` — type) |
| `../../utils/ttl-cache.js` | (see §C2.2 — vendor) | — |

### C2.2 Vendor stub rewrite pairs (→ `../../vendor/<rel-from-D-repo-root>.js`)

| original specifier(s) | dest stub (`src/vendor/…`) | consumed by (symbols) | runtime-or-type |
|---|---|---|---|
| `../../utils/ttl-cache.js` (trust-ledger/index) | `../../vendor/core/utils/ttl-cache.js` | `TTLCache` (runtime class) | **RUNTIME** (see Open Flag 4) |

### C2.3 Internal (unchanged) + builtins/npm

- **Internal (stay valid under mirror, 0 rewrites):** all `./X.js` same-dir siblings (training/index → `./training-store.js`,
  `./training-ingest.js`, `./training-tagger.js`, `./training-reader.js`, `./training-types.js`; sdk-tagger →
  `./training-store.js`+`./training-tagger.js`+`./training-types.js`; background-tagger-worker →
  `./sdk-tagger.js`+`./training-store.js`; etc.). **No cross-dir training↔trust-ledger imports** (verified).
- **Builtins/npm (unchanged):** `node:crypto`, `node:fs`, `node:path`, `better-sqlite3` (training-store, training-ingest).

### C2.4 Rewrite-pair tally (Part C)

| class | unique targets | files touched |
|---|---|---|
| **Foundation + landed (`@cassicore/*`)** | **3** (interfaces, cognitive-module, flux-team-GBR→landed) | 9 |
| **Vendor type/runtime stub (`../../vendor/...`)** | **1** (utils/ttl-cache) | 1 |
| **Internal (unchanged `./X.js`)** | **0 rewrite pairs** | — |
| **Builtins/npm (unchanged)** | **0 rewrite pairs** | — |
| **TOTAL rewrite pairs** | **4 unique targets** | 9 files with ≥1 rewrite |

---

## C3. Destination layout (Part C)

```
packages/training-trust-ledger/
  package.json                     # name: "@cassicore/training-trust-ledger", type: module,
                                   #   deps: @cassicore/foundation, better-sqlite3
  tsconfig.json                    # rootDir src/ outDir dist/ declaration true
  vitest.config.ts
  README.md
  src/
    training/                      # depth 1
      index.ts                     # entry barrel: TrainingWarehouse + re-exports
      training-store.ts  training-ingest.ts  training-tagger.ts  training-reader.ts
      training-types.ts  sdk-tagger.ts  background-tagger-worker.ts
    trust-ledger/                  # depth 1
      index.ts                     # entry barrel: TrustLedger (BaseCognitiveModule) + createTrustLedger
      types.ts
    vendor/                        # stubs ONLY — mirror D: rel-paths (§C2.2)
      core/
        utils/ttl-cache.ts         # TTLCache (RUNTIME)
```

### C3.1 Repoint log (Part C — inbound/outbound)

**Inbound stubs owned by this package:** NONE pre-vendored (training/trust-ledger were never vendored in P1–P3).
**Part C's own stubs → owning packages (later phases):** `core/utils/ttl-cache.ts` → `@cassicore/utils` at P6.

---

## C4. Known-hard items (Part C)

### C4a. Registry / discovery surface — `TrustLedger` is a BaseCognitiveModule in the skip-set (P7 note)

`trust-ledger/index.ts` exports `export class TrustLedger extends BaseCognitiveModule` (name `'trust-ledger'`) +
`export function createTrustLedger(logger)`. **In daemon registry skip-set** (daemon.ts:2049) and manually
instantiated in `createIntelligence()` (`createTrustLedger` + `trustLedger.setMemory(memory)`, then
`permissionOracle.setTrustLedger(trustLedger)`). `training/index.ts` exports `class TrainingWarehouse` (NOT a
BaseCognitiveModule — a plain store/aggregate) + `createTrainingWarehouse`-style factory; `training` is NOT in the
skip-set (no module class to discover), instantiated `new TrainingWarehouse({dataDir,sources}, logger)` in
`createIntelligence()`.

**P7 host contract:** register `TrustLedger` as an explicit module (skip auto-discovery, mirroring dreamer);
`TrainingWarehouse` is a plain wired companion (no registry entry). Preserve `createTrustLedger`, `createTrainingWarehouse`,
`TrustLedger.setMemory`, and the `TrainingWarehouse` constructor + method surface.

### C4b. `TrainingWarehouse` data-dir + SQLite (the daemon-couple seam)

`training/index.ts` reads `config.get('dataDir')` and instantiates `TrainingWarehouse({ dataDir, sources }, logger)` —
the training DB lives under the daemon's `dataDir`. **Default:** the package constructor keeps accepting a
`dataDir` + `sources` option (the P7 host supplies `@cassicore/foundation`'s `getDataDir()`); the migration does NOT
hardcode the daemon path. `background-tagger-worker.ts` ticks and calls `TrainingTagger` with a `TaggerLLM` adapter
that the daemon injects after providers are ready (per `createIntelligence` wiring) — that adapter is a port the host
or P6 `@cassicore/model-pool` provides; migrate the worker as-is.

### C4c. `background-tagger-worker.ts` is NOT a subprocess entry

Grep for `require.main|worker_threads|import.meta.url ===|spawn|\.fork(` across the Part-C set → **no matches**.
`background-tagger-worker.ts` is a tick-based in-process worker class (`start()`/`stop()`), not a standalone process.
It migrates as a normal library file. (Contrast: mnemic-field's `backfill-worker.ts`/`umap-worker.cjs` ARE subprocess
entries — not present here.)

### C4d. `TrustLedger` outgoing to `permission-oracle` (P5-A, not this phase)

`createIntelligence` calls `permissionOracle.setTrustLedger(trustLedger)`. `permission-oracle` is a P5-A sibling
(NOT Group B). Trust-ledger exports the instance to permission-oracle at the HOST wiring, not via an import — so
Part C has no permission-oracle import to rewrite. Note it explicitly so the P5-A package knows it consumes the real
`@cassicore/training-trust-ledger`'s `TrustLedger`.

---

# PART D — `@cassicore/workspace`

**Sources (READ-ONLY, D:):** `core/intelligence/workspace/`, `core/intelligence/code-analysis/`
**Destinations:** `packages/workspace/src/{workspace,code-analysis}/`

## D1. Live-set (files to migrate)

Both source dirs FLAT (0 subdirs). Recon: **0 DEAD, 0 UNCERTAIN** — all files LIVE.

**`src/workspace/*.ts` — 12 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 1 | `workspace/index.ts` | `workspace/index.ts` | 2064 | LIVE (entry barrel — `GlobalWorkspace`, RadianceLoop, re-exports) |
| 2 | `workspace/global-workspace.ts` | `workspace/global-workspace.ts` | 20564 | LIVE (**GlobalWorkspace** — the GWT / blackboard successor, §D4a) |
| 3 | `workspace/attention-schema.ts` | `workspace/attention-schema.ts` | 4753 | LIVE |
| 4 | `workspace/coalition.ts` | `workspace/coalition.ts` | 5857 | LIVE |
| 5 | `workspace/cognitive-signal.ts` | `workspace/cognitive-signal.ts` | 9778 | LIVE |
| 6 | `workspace/expectation-model.ts` | `workspace/expectation-model.ts` | 9069 | LIVE |
| 7 | `workspace/feedback-tracker.ts` | `workspace/feedback-tracker.ts` | 2524 | LIVE |
| 8 | `workspace/luminance.ts` | `workspace/luminance.ts` | 6303 | LIVE |
| 9 | `workspace/radiance-loop.ts` | `workspace/radiance-loop.ts` | 12425 | LIVE |
| 10 | `workspace/radiance-types.ts` | `workspace/radiance-types.ts` | 7455 | LIVE |
| 11 | `workspace/workspace-memory.ts` | `workspace/workspace-memory.ts` | 4792 | LIVE |
| 12 | `workspace/workspace-observer.ts` | `workspace/workspace-observer.ts` | 7529 | LIVE |

**`src/code-analysis/*.ts` — 10 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 13 | `code-analysis/index.ts` | `code-analysis/index.ts` | 1477 | LIVE (entry barrel — `analyzeDeadCode`, `analyzeHotspots`, …) |
| 14 | `code-analysis/cochange-analyzer.ts` | `code-analysis/cochange-analyzer.ts` | 5315 | LIVE |
| 15 | `code-analysis/context-assembler.ts` | `code-analysis/context-assembler.ts` | 17060 | LIVE |
| 16 | `code-analysis/dead-code-analyzer.ts` | `code-analysis/dead-code-analyzer.ts` | 7857 | LIVE |
| 17 | `code-analysis/feedback-tracker.ts` | `code-analysis/feedback-tracker.ts` | 11314 | LIVE |
| 18 | `code-analysis/gitnexus-bridge.ts` | `code-analysis/gitnexus-bridge.ts` | 12502 | LIVE |
| 19 | `code-analysis/hotspot-analyzer.ts` | `code-analysis/hotspot-analyzer.ts` | 9082 | LIVE |
| 20 | `code-analysis/schema-introspector.ts` | `code-analysis/schema-introspector.ts` | 4359 | LIVE |
| 21 | `code-analysis/specificity-scorer.ts` | `code-analysis/specificity-scorer.ts` | 5052 | LIVE |
| 22 | `code-analysis/types.ts` | `code-analysis/types.ts` | 5656 | LIVE |

**Live-set count (Part D): 22 files** (12 workspace + 10 code-analysis). **0 DEAD, 0 quarantined.**

---

## D2. Rewrite table (Part D)

Same rules as §A2. All files depth 1; vendor prefix `../../vendor/...`; foundation → `@cassicore/foundation`.

### D2.1 Foundation + landed-package rewrite pairs (→ `@cassicore/*`)

| original specifier | dest | consumed by (files + symbols) |
|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | workspace/global-workspace (`ILogger`), workspace/radiance-loop (`ILogger`), workspace/workspace-observer (`ILogger`), code-analysis/cochange-analyzer, context-assembler, dead-code-analyzer, feedback-tracker, gitnexus-bridge, hotspot-analyzer, schema-introspector (`ILogger`) |
| `../cortex/index.js` (workspace/radiance-loop) | (see §D2.2 — vendor) | — |
| `../constellation/meditation/solo-runner.js` (workspace/radiance-loop, workspace/workspace-observer) | **`@cassicore/constellation`** (landed) — IF exported; else vendor | `runSoloExplorer` (**RUNTIME** — dynamic `import()`), `ToolCallResult` (type) |

### D2.2 Vendor stub rewrite pairs (→ `../../vendor/<rel-from-D-repo-root>.js`)

| original specifier(s) | dest stub (`src/vendor/…`) | consumed by (symbols) | runtime-or-type |
|---|---|---|---|
| `../cortex/index.js` (workspace/radiance-loop) | `../../vendor/core/intelligence/cortex/index.js` | `CorticalField` (type) | type |
| `../constellation/meditation/solo-runner.js` (workspace/radiance-loop, workspace/workspace-observer) | **`@cassicore/constellation`** — **Default: VENDOR as a faithful stub** at `../../vendor/core/intelligence/constellation/meditation/solo-runner.ts` IF the constellation barrel does not export `runSoloExplorer`/`ToolCallResult` (see Open Flag 6) | `runSoloExplorer` (**RUNTIME** — dynamic `import()`), `ToolCallResult` (type) | **RUNTIME** (dynamic import — see Open Flag 6) |

### D2.3 Internal (unchanged) + builtins/npm

- **Internal (stay valid under mirror, 0 rewrites):** all `./X.js` same-dir siblings (global-workspace →
  `./attention-schema.js`+`./coalition.js`+`./cognitive-signal.js`+`./feedback-tracker.js`+`./luminance.js`+
  `./radiance-types.js`+`./workspace-memory.js`; radiance-loop → `./cognitive-signal.js`+`./expectation-model.js`+
  `./global-workspace.js`+`./radiance-types.js`+`./workspace-observer.js`; code-analysis internals; etc.). **No
  cross-dir workspace↔code-analysis imports** (verified — code-analysis is fully self-contained + foundation).
- **Builtins/npm (unchanged):** `node:child_process`, `node:fs`, `node:path`, `node:util`, `node:crypto`,
  `better-sqlite3` (code-analysis/feedback-tracker, schema-introspector).

### D2.4 Rewrite-pair tally (Part D)

| class | unique targets | files touched |
|---|---|---|
| **Foundation + landed (`@cassicore/*`)** | **2** (interfaces, constellation-solo-runner→landed/vendor) | 12 |
| **Vendor type/runtime stub (`../../vendor/...`)** | **1** (cortex/index) + solo-runner (if vendored) | 3 |
| **Internal (unchanged `./X.js`)** | **0 rewrite pairs** | — |
| **Builtins/npm (unchanged)** | **0 rewrite pairs** | — |
| **TOTAL rewrite pairs** | **3 unique targets** (interfaces, cortex, solo-runner) | 13 files with ≥1 rewrite |

---

## D3. Destination layout (Part D)

```
packages/workspace/
  package.json                     # name: "@cassicore/workspace", type: module,
                                   #   deps: @cassicore/foundation, better-sqlite3
  tsconfig.json                    # rootDir src/ outDir dist/ declaration true
  vitest.config.ts
  README.md
  src/
    workspace/                     # depth 1
      index.ts                     # entry barrel: GlobalWorkspace, RadianceLoop, plus re-exports
      global-workspace.ts  attention-schema.ts  coalition.ts  cognitive-signal.ts
      expectation-model.ts  feedback-tracker.ts  luminance.ts  radiance-loop.ts
      radiance-types.ts  workspace-memory.ts  workspace-observer.ts
    code-analysis/                 # depth 1
      index.ts                     # entry barrel: analyzeDeadCode, analyzeHotspots, prepareContext, …
      cochange-analyzer.ts  context-assembler.ts  dead-code-analyzer.ts  feedback-tracker.ts
      gitnexus-bridge.ts  hotspot-analyzer.ts  schema-introspector.ts  specificity-scorer.ts  types.ts
    vendor/                        # stubs ONLY — mirror D: rel-paths (§D2.2)
      core/
        intelligence/
          cortex/index.ts          # CorticalField (type)
          constellation/meditation/solo-runner.ts  # runSoloExplorer (RUNTIME, if not landed — Open Flag 6)
```

### D3.1 Repoint log (Part D — inbound/outbound)

**Inbound stubs this package now OWNS** (re-point consumer stubs → `@cassicore/workspace`, delete stubs):
| consumer stub (`src/vendor/...`) | exported symbols | this phase re-points to |
|---|---|---|
| foundation (P1) `core/intelligence/workspace/index.ts` | `GlobalWorkspace, CognitiveSignal, SignalType, WorkspaceResponse` (cognitive-module types) | `@cassicore/workspace` |
| helix (P2) `core/intelligence/workspace/index.ts` | `CognitiveSignal, GlobalWorkspace, SignalType` (helix-conductor, helix-locus, helix-pipeline, helix-posture-runner, posture-module, types) | `@cassicore/workspace` |
| constellation (pre-existing) `workspace/index.ts` | `GlobalWorkspace` (corpus-types, constellation-pipeline, constellation-orchestrator) | `@cassicore/workspace` |
| constellation (pre-existing) `workspace/global-workspace.ts` | `GlobalWorkspace` (helix-goal-lamina, locus/graph-attention-bridge, territory-bridge) | `@cassicore/workspace` |
| constellation (pre-existing) `workspace/cognitive-signal.ts` | `CognitiveSignal, SignalType` (helix-goal-lamina, signal-pattern-digest, territory-bridge) | `@cassicore/workspace` |
| constellation (pre-existing) `code-analysis/feedback-tracker.ts` | `ContextFeedbackTracker` (constellation-pipeline) | `@cassicore/workspace` |
| constellation (pre-existing) `code-analysis/specificity-scorer.ts` | `scoreSpecificity` (constellation-pipeline) | `@cassicore/workspace` |
| constellation (pre-existing) `code-analysis/types.ts` | `CodeAnalysisResult`-family (fast-decomposer) | `@cassicore/workspace` |

**Part D's own stubs → owning packages (later phases):** `core/intelligence/cortex/index.ts` → `@cassicore/cortex`
(P5-A); `core/intelligence/constellation/meditation/solo-runner.ts` → `@cassicore/constellation` (Open Flag 6).

---

## D4. Known-hard items (Part D)

### D4a. Registry / discovery surface — `GlobalWorkspace` is the blackboard successor (P7 + overhaul note)

`workspace/index.ts` re-exports `GlobalWorkspace` (the class in `global-workspace.ts`) + `RadianceLoop`, plus
`CognitiveSignal`/`SignalType`/`DEFAULT_WORKSPACE_CONFIG`/`AttentionSchema`/`Coalition`/`Ratings`/`FeedbackResult`/
`CredibilityRecord`. **`GlobalWorkspace` is NOT a BaseCognitiveModule** and `workspace` is NOT in the daemon registry
skip-set — it is instantiated explicitly (`new GlobalWorkspace(logger.child('workspace'))`) in `createIntelligence()`
and injected into constellation/other modules via `setGlobalWorkspace`. It is the **GWT broadcast surface that the
overhaul session's GlobalWorkspace migration and the deprecated `flux-team` blackboard both target** (plan §3e.1/P5,
flux-team §A4a). **Coordination:** the overhaul session may rewire GlobalWorkspace as the field's broadcast/journal
(plan §7) — record the "package publishes before their rewiring" default (§8 Q6) and confirm at P5B-execution they
haven't already rewired `core/intelligence/workspace/*`.

**P7 host contract:** `GlobalWorkspace` is explicitly wired (NOT registry-discovered), injected into constellation's
`setGlobalWorkspace` and any module needing the GWT. Preserve barrel export names verbatim.

### D4b. `radiance-loop.ts` dynamic `import()` of `runSoloExplorer` (runtime coupled to constellation)

`workspace/radiance-loop.ts` does a DYNAMIC `import('../constellation/meditation/solo-runner.js')` calling
`runSoloExplorer(...)` at runtime (line 121) and a TYPE import of `ToolCallResult` (line 31); `workspace-observer.ts`
does a type-only `ToolCallResult` import (line 22). Because `@cassicore/constellation` is a LANDED package that
already contains `src/meditation/solo-runner.ts`, the ideal is to re-point to `@cassicore/constellation` — **IF** its
public barrel re-exports `runSoloExplorer` + `ToolCallResult` (the meditation index imports them internally but the
top-level `constellation/index.ts` barrel may not). **Default: check the constellation barrel at execution; if
`runSoloExplorer`/`ToolCallResult` are NOT exported at package top level, vendor a faithful stub (type `ToolCallResult`
+ a runtime `runSoloExplorer` forwarding import) and re-point at P7 host wiring when the constellation barrel is
expanded.** This is a dynamic-import runtime coupling — a `throw` stub WOULD break radiance-loop at runtime if it
runs the solo-runner path, so a forwarding stub (or landed re-point) is required. Open Flag 6.

### D4c. code-analysis is batch tooling — `node:child_process` invokes git/sqlite, NOT subprocess entries

All five code-analysis files that match `child_process` (`cochange-analyzer`, `context-assembler`, `dead-code-analyzer`,
`gitnexus-bridge`, `hotspot-analyzer`) use `execSync`/`spawn` to run `git`/schema tools with EXPLICIT `cwd` — library
usage, NOT standalone process entries (no `require.main`, no `import.meta.url ===`, no `fork`). They migrate as normal
files. `schema-introspector` + `feedback-tracker` open `better-sqlite3`. **Default:** add `better-sqlite3` as a Part-D
npm dep; keep `node:child_process` builtins. No process-isolation needed.

---

# PART E — `@cassicore/embeddings`

**Sources (READ-ONLY, D:):** `core/intelligence/embeddings/`, `core/intelligence/shared/`
**Destinations:** `packages/embeddings/src/{embeddings,shared}/`

## E1. Live-set (files to migrate)

Both source dirs FLAT (0 subdirs). Recon: **0 DEAD, 0 UNCERTAIN** — all files LIVE.

**`src/embeddings/*.ts` — 5 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 1 | `embeddings/embedding-service.ts` | `embeddings/embedding-service.ts` | 15931 | LIVE (exports `getEmbeddingService` — §E4a) |
| 2 | `embeddings/reranker-service.ts` | `embeddings/reranker-service.ts` | 9948 | LIVE (exports `getRerankerService` — §E4a) |
| 3 | `embeddings/sqlite-index.ts` | `embeddings/sqlite-index.ts` | 11622 | LIVE (exports `SqliteVectorIndex`, `getVectorIndex`) |
| 4 | `embeddings/background-worker.ts` | `embeddings/background-worker.ts` | 17797 | LIVE (tick worker class — NOT a process entry, §E4c) |
| 5 | `embeddings/types.ts` | `embeddings/types.ts` | 1095 | LIVE |

**`src/shared/*.ts` — 2 files (depth 1)**
| # | source (D:) | dest | bytes | recon verdict |
|---|---|---|---|---|
| 6 | `shared/posture-store.ts` | `shared/posture-store.ts` | 57654 | LIVE (exports `composeSystemPrompt`, `getBaseIdentity`, `hasContext`) |
| 7 | `shared/token-estimation.ts` | `shared/token-estimation.ts` | 1197 | LIVE (exports `CHARS_PER_TOKEN`, `estimateTokens`, `estimateChars`) |

**Live-set count (Part E): 7 files** (5 embeddings + 2 shared of `embeddings` pkg). **0 DEAD, 0 quarantined.**

> **`embeddings` has NO `index.ts` — the package barrel is WRITTEN BY the packager** (§E4a / Open Flag 7). The source
> dir contains no `index.ts`; the package needs a hand-authored `src/index.ts` exposing `getEmbeddingService`,
> `getRerankerService`, `SqliteVectorIndex`/`getVectorIndex`, the `embeddings/types` surface, and (if the owner wants
> the shared util on the surface) `composeSystemPrompt`/`estimateTokens`. This is a fresh barrel (no source file to
> splice); it is added in the rewrite-delta commit, not the history import.

---

## E2. Rewrite table (Part E)

Same rules as §A2. All files depth 1; vendor prefix `../../vendor/...`; foundation → `@cassicore/foundation`.

### E2.1 Foundation + landed-package rewrite pairs (→ `@cassicore/*`)

| original specifier | dest | consumed by (files + symbols) |
|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | embeddings/background-worker (`ILogger`), embeddings/embedding-service (`ILogger`), embeddings/reranker-service (`ILogger`), embeddings/sqlite-index (`ILogger`) |
| `../gaming-mode.js` (embeddings/background-worker) | (see §E2.2 — vendor) | — |

### E2.2 Vendor stub rewrite pairs (→ `../../vendor/<rel-from-D-repo-root>.js`)

| original specifier(s) | dest stub (`src/vendor/…`) | consumed by (symbols) | runtime-or-type |
|---|---|---|---|
| `../gaming-mode.js` (embeddings/background-worker) | `../../vendor/core/intelligence/gaming-mode.js` | `isGamingMode` (runtime fn) | **RUNTIME** |

### E2.3 Internal (unchanged) + builtins/npm

- **Internal (stay valid under mirror, 0 rewrites):** `./embedding-service.js` (background-worker ×2), `./sqlite-index.js`
  (background-worker ×2) — all same-`embeddings/`-dir siblings. `shared/*` are self-contained (NO imports — posture-store
  and token-estimation have zero import statements; verified).
- **Builtins/npm (unchanged):** `crypto`, `fs`, `path`, `os` (bare builtins — `embedding-service.ts` imports
  `createHash from 'crypto'`, `readFileSync/... from 'fs'`, `join/dirname from 'path'`; `sqlite-index.ts` uses
  `import fs from 'fs'` + `import path from 'path'`; `background-worker.ts` uses `import fs from 'fs'` + `import path
  from 'path'`), `better-sqlite3` (sqlite-index, background-worker). **Note the bare `'crypto'/'fs'/'path'/'os'` are
  Node builtins in the source (not npm) — leave unchanged.**

### E2.4 Rewrite-pair tally (Part E)

| class | unique targets | files touched |
|---|---|---|
| **Foundation (`@cassicore/foundation`)** | **1** (interfaces) | 4 |
| **Vendor type/runtime stub (`../../vendor/...`)** | **1** (gaming-mode) | 1 |
| **Internal (unchanged `./X.js`)** | **0 rewrite pairs** | — |
| **Builtins/npm (unchanged)** | **0 rewrite pairs** | — |
| **TOTAL rewrite pairs** | **2 unique targets** | 5 files with ≥1 rewrite |

---

## E3. Destination layout (Part E)

```
packages/embeddings/
  package.json                     # name: "@cassicore/embeddings", type: module,
                                   #   deps: @cassicore/foundation, better-sqlite3
  tsconfig.json                    # rootDir src/ outDir dist/ declaration true
  vitest.config.ts
  README.md
  src/
    index.ts                       # PACKAGER-WRITTEN barrel (no source index.ts — Open Flag 7):
                                   #   getEmbeddingService, getRerankerService, SqliteVectorIndex/getVectorIndex,
                                   #   embeddings/types surface, composeSystemPrompt/estimateTokens (shared)
    embeddings/                    # depth 1
      embedding-service.ts  reranker-service.ts  sqlite-index.ts  background-worker.ts  types.ts
    shared/                        # depth 1
      posture-store.ts  token-estimation.ts
    vendor/                        # stubs ONLY — mirror D: rel-paths (§E2.2)
      core/
        intelligence/gaming-mode.ts  # isGamingMode (RUNTIME)
```

### E3.1 Repoint log (Part E — inbound/outbound)

**Inbound stubs this package now OWNS** — **the headliner of Group B's inbound sweep** (the brief flagged these):
| consumer stub (`src/vendor/...`) | exported symbols | this phase re-points to | runtime-or-type |
|---|---|---|---|
| helix (P2) `core/intelligence/shared/posture-store.ts` | `composeSystemPrompt` (helix-postures) | `@cassicore/embeddings` | **RUNTIME** |
| helix (P2) `core/intelligence/shared/token-estimation.ts` | `estimateTokens` (helix-posture-runner, context-chunk-index) | `@cassicore/embeddings` | **RUNTIME** |
| helix (P2) `core/intelligence/embeddings/embedding-service.ts` — if ANY (checked: none in helix) | — | — | — |
| constellation (pre-existing) `embeddings/embedding-service.ts` | `getEmbeddingService` (**RUNTIME** — topology/embedding-cache, gravity-engine, topology-graph, constellation-pipeline, constellation-orchestrator) | `@cassicore/embeddings` | **RUNTIME** |
| constellation (pre-existing) `embeddings/types.ts` | `RerankerMode`, `EmbeddingService`-family types | `@cassicore/embeddings` | type |
| constellation (pre-existing) `shared/posture-store.ts` | `composeSystemPrompt` (flex-posture) | `@cassicore/embeddings` | **RUNTIME** |
| constellation (pre-existing) `subconscious/types.ts` | `SubconsciousConfig`-family | `@cassicore/dreamer-reverie-subconscious` (Part A) | type |

> **`getEmbeddingService`/`getRerankerService` canonical home.** These are singletons with a RUNTIME impl
> (`embedding-service.ts`/`reranker-service.ts` export `getEmbeddingService`/`getRerankerService` factories). The
> constellation `embeddings/embedding-service.ts` stub shadows this; the real `@cassicore/embeddings` exports must
> REPLACE it (not leave a throw stub) or constellation's embedding paths break at runtime. **The constellation stub
> must be deleted and rewired to the real package.** See Open Flag 8.

**Part E's own stub → owning packages (later phases):** `core/intelligence/gaming-mode.ts` → `@cassicore/auxiliary`
(P5-A).

---

## E4. Known-hard items (Part E)

### E4a. `getEmbeddingService` / `getRerankerService` — runtime singletons, host-wired via env (the canonical-home item)

Both services are **self-contained HTTP clients**: `embedding-service.ts` wraps vLLM `/v1/embeddings` (config via
`EMBEDDING_SERVER_URL`, `EMBEDDING_MODEL_TAG`, `EMBEDDING_DIM`, `EMB_TIMEOUT_MS`, `EMB_BATCH_SIZE`, cache
envs); `reranker-service.ts` wraps zerank-server `/v1/rerank` OR vLLM `/v1/completions` (config via
`RERANKER_SERVER_URL`, `RERANKER_TIMEOUT_MS`). **No larql, no Python bridge, no API keys baked in** — the endpoints are
env-provided (host supplies them at runtime). The only external deps are Node builtins (`crypto/fs/path`),
`better-sqlite3` (sqlite-index, background-worker), and foundation `ILogger`. `sqlite-index.ts` reads/writes a
persistent vector DB (under `getDataDir()`-style path via `path`/os home, not via foundation paths — it uses
`join(homedir(), ...)` / env; see Open Flag 8 for the data-dir seam).

**Port contract:** the real `@cassicore/embeddings` package exports `getEmbeddingService`, `getRerankerService`,
`SqliteVectorIndex`, `getVectorIndex`, plus the `embeddings/types` surface. Constellation + helix re-point their
runtime stubs to these real exports. The env-var wiring stays host-side (the package reads `process.env` at module
load — keep that; do NOT move the endpoint config into the host until P7 decides).

### E4b. `background-worker.ts` is NOT a subprocess entry (but has a `BackgroundEmbeddingWorker` class the daemon holds)

`background-worker.ts` exports `BackgroundEmbeddingWorker` (a `start()`/`stop()` tick class) and the daemon holds it
on `daemon.bgEmbeddingWorker` (daemon.ts:200), `getBackgroundEmbeddingWorker()` (daemon.ts:484). It is NOT a
`worker_threads`/fork process — it ticks in-process. It imports `./embedding-service.js`+`./sqlite-index.js`
(internal) + `../gaming-mode.js` (vendor) + `better-sqlite3` + foundation `ILogger`. Migrates as a normal library
file; the daemon's `getBackgroundEmbeddingWorker()` hook re-points to `@cassicore/embeddings` at P7.

### E4c. `shared/*` semantics vs placement (posture-store is CassiAgent posture; token-estimation is context-budget)

The brief assigned `shared/*` to `@cassicore/embeddings`; the plan's P5 table assigned `shared/posture-store` to
`@cassicore/workspace` and `shared/token-estimation` to `@cassicore/embeddings` (or utils). **Resolution (default):
ship BOTH under `@cassicore/embeddings` per the brief** (this is the canonical extraction; helix/constellation's
`shared/posture-store.ts`+`shared/token-estimation.ts` stubs re-point here). `posture-store` is semantically
CassiAgent-user-facing (3 energetic directions x agent types) but its consumers today are helix + constellation —
both land on the embeddings export. If the owner later prefers a dedicated `@cassicore/posture` package, the re-point
is trivial (single stub path). Open Flag 8 note.

### E4d. Registry / discovery surface — NO intelligence module in embeddings (P7 note)

`embeddings` has NO `index.ts` and NO `BaseCognitiveModule` subclass — it is a **service library, not a discovered
module**. It IS in the daemon registry skip-set (daemon.ts:2040) but only to prevent the `discover()` from treating the
dir as a module (it has no `index.ts`, so discovery would skip it anyway — the skip-set entry is defensive). The P7
host wires `getEmbeddingService`/`getRerankerService`/`SqliteVectorIndex` as injected singletons (they are consumed by
P4 mnemic-field and P5-A cortex via their own vendor stubs). The packager MUST write `src/index.ts` (§E1 note / Open
Flag 7).

---

# §5. Combined open flags (all five parts — max 8; defaults recommended)

1. **Grouping confirmed vs the plan's P5 table (evidence-backed).** The brief's five-package Group B set is adopted;
   both `lamina+locus-bridge` AND `workspace+code-analysis` are separate packages (the plan folded workspace under
   `@cassicore/lamina`). `shared/*` goes to `@cassicore/embeddings` (not `workspace`). `context-distiller.ts` +
   `module-session-registry.ts` are standalone siblings (NOT Group B dirs) — they stay vendored and their owning
   package is deferred (§Open Flag 3). **Default: follow the brief; record the diff in the plan's P5 table update.**
   `[VERIFY]` at execution that the owner still wants `@cassicore/lamina-locus-bridge` (vs separating lamina and
   locus-bridge) — the brief's name is explicit, keep it.
2. **`reverie` auto-discovery trap (Part A §A4b).** `ReverieModule extends BaseCognitiveModule` but `reverie` is NOT
   in the daemon registry skip-set; `createIntelligence()` manually does `new ReverieModule(logger)`. **Default: the
   P7 host wires `reverie` explicitly AND adds it to its skip-set (mirror dreamer/trust-ledger) so no duplicate
   instance.** Confirm the other session's registry contract (plan §7) tolerates `reverie` in the skip-set. `[VERIFY]`.
3. **`module-session-registry.ts` + `context-distiller.ts` placement (Part A/C imports → vendor, owner deferred).**
   Both are standalone siblings under `core/intelligence/` consumed by subconscious (`module-session-registry.js`,
   type) and others. The plan mapped both into its `@cassicore/workspace` row, but they are NOT Group-B dirs. **Default:
   leave them as Part-A vendor stubs now; assign the real owning package (workspace or a coalesced auxiliary) at
   P5-A/P7.** This also means the EXISTING foundation(P1)/helix(P2) `module-session-registry.ts` stubs are NOT
   re-pointed in P5B (not owned this phase). `[VERIFY]` the final home.
4. **Runtime vendored symbols — five faithful impls required (Parts A/B/C).** `createReasoningBank` + `AuditStore`
   (Part A), `prefixedId` + `AuditStore` (Part B), `TTLCache` (Part C), `isGamingMode` (Parts A/E), `runSoloExplorer`
   (Part D — dynamic-import). **Default:** port exact self-contained copies into the vendor stubs (all are pure,
   host-dep-light: `ILogger`-only or none); re-point to owning packages at P5-A/P6/P7. A bare `throw` on ANY of these
   breaks the calling code at runtime (dreamer constructor calls `AuditStore`, lamina writes via `prefixedId`, trust
   ledger caches via `TTLCache`). Mark `[VERIFY]` each copy matches source at execution.
5. **`gaming-mode.js` is a VENDOR target, NOT foundation (corrected).** `core/intelligence/gaming-mode.ts`
   (`isGamingMode` helper) is a standalone sibling, not part of the P1 foundation substrate (not `types/*`, config,
   base, utils/paths, phrase-prototypes). **Default:** vendor `src/vendor/core/intelligence/gaming-mode.ts` in Parts A
   and E; re-point to `@cassicore/auxiliary` at P5-A. (My initial table draft labeled it foundation — corrected in
   §A2.2/E2.2. No source change.)
6. **`radiance-loop.ts` / `workspace-observer.ts` → `@cassicore/constellation` vs vendor `solo-runner` (Part D).**
   `constellation` is a landed package owning `src/meditation/solo-runner.ts`, but its top-level barrel may not export
   `runSoloExplorer`/`ToolCallResult`. **Default: at execution, if the constellation barrel re-exports them → re-point
   to `@cassicore/constellation`; else vendor a faithful forwarding stub and re-point at P7.** Because the `import()`
   is dynamic + runtime, a `throw` stub is unacceptable. `[VERIFY]` constellation barrel + confirm the overhaul session
   hasn't moved `radiance-loop`/`solo-runner`.
7. **`@cassicore/embeddings` needs a packager-written `src/index.ts` (no source barrel).** The `embeddings/` dir has no
   `index.ts`. **Default:** the packager writes a fresh `src/index.ts` re-exporting `getEmbeddingService`,
   `getRerankerService`, `SqliteVectorIndex`/`getVectorIndex`, the `embeddings/types` surface, `composeSystemPrompt`,
   `estimateTokens`/`estimateChars`/`CHARS_PER_TOKEN`. This is a NEW file (no history import — added in the
   rewrite-delta commit). Confirm the owner wants `shared/*` composables on the package surface (they are, for helix/
   constellation consumption). Also confirm the `embeddings` data-dir seam: `sqlite-index.ts` resolves its DB path via
   env/`homedir()` (not foundation `getDataDir`) — decide at P7 whether to move it to the foundation paths port.
8. **Inbound re-point scope = the full Group-B set across FOUR landed packages (foundation, helix, constellation,
   flux-team)** — the biggest per-phase inbound sweep. The stubs to re-point to a Group-B package: **workspace** owns
   foundation(1) + helix(1) + constellation(5 incl. code-analysis×3); **lamina-locus-bridge** owns helix(1) +
   constellation(1); **dreamer-reverie-subconscious** owns foundation(1 dreamer/types); **embeddings** owns helix(2
   shared + any embedding) + constellation(4: embeddings×2, shared×1, subconscious/types×1); **flux-team** is the owner
   of a GBR symbol the Part-A/C packages IMPORT (not a stub to delete — it's the re-point destination). **Default:
   perform the re-point for ALL of these as a REQUIRED P5B executor task,** sequence each consumer package's
   re-point + typecheck after the owning Group-B package lands. Delete each stub. **Runtime stubs among these
   (must be real, not throw):** `getEmbeddingService`, `composeSystemPrompt`, `estimateTokens`, `isGamingMode`,
   `AuditStore`(if not relocated to P6), `prefixedId`, `TTLCache`, `runSoloExplorer`. See §3.1/§A3.2/§B3.1/§C3.1/§D3.1/
   §E3.1 for the full tables.

---

# §6. Executor playbook (P5B later wave — verbatim, mirrors P1–P4 §6)

Each of the five packages is independent; sequence them so a package that EXPORTS a symbol lands before a package
that IMPORTS it from `@cassicore/*` (but all re-points are best done after ALL five publish, since they interlock only
via shared stubs). Recommended order: **E (embeddings) and B (lamina-locus-bridge) and C (training-trust-ledger) first
(most inbound-re-point-heavy / self-contained), then A (dreamer-reverie-subconscious, imports lamina), then D
(workspace, imports constellation).** Within each: history-splice import commit → rewrite-delta commit → inbound
re-point commit(s) (plan §3c).

1. **History import (×5).** Temp-clone D: (`git clone --no-checkout --no-local`), then per package run
   `git filter-repo --force --path core/intelligence/<dirs…> --path-rename <dir>:packages/<pkg>/src --mailmap …`.
   Group A: three paths (dreamer, reverie, subconscious) → ONE filter-repo run → one import commit into
   `packages/dreamer-reverie-subconscious/src/{dreamer,reverie,subconscious}` (filter-repo with multiple `--path` +
   `--path-rename` pairs). Group B: `core/intelligence/lamina --path-rename ...:packages/lamina-locus-bridge/src/lamina`
   AND `core/intelligence/locus-bridge --path-rename ...:.../src/locus-bridge` (two paths → one commit, or two —
   prefer one filter-repo with 2 `--path`/`--path-rename` pairs). Group C: training + trust-ledger. Group D: workspace
   + code-analysis. Group E: embeddings + shared. Fetch + splice each (add/add, take `--theirs` for conflicted
   import files), verify `git log --follow`, commit. **NEVER merge a stale fragment: re-verify the D: paths have not
   moved/been rewired since the temp clone (plan §3d — the overhaul session is live).**

2. **Copy the LIVE files (§A1/B1/C1/D1/E1).** Keep `.ts` extensions + `.js` import specifiers verbatim. Do NOT copy any
   DEAD (none in scope) or UNCERTAIN (none). Package-split: A=17, B=12, C=10, D=22, E=7 (total 68), all LIVE.

3. **Apply the rewrite pairs per file — a GLOBAL replace per specifier, DEPTH-CORRECT per file (P2/P4 lesson (a)); all
   migrated files sit at `src/<dir>/` so the uniform vendor prefix is `../../vendor/...`, foundation is
   `@cassicore/foundation`, and landed/`@cassicore/*` are package specifiers.** Compute each specifier from the file's
   own dest dir; never a single sed across the tree. Foundation (`../../../types/*`, `../../config/system-settings`,
   `../base/cognitive-module`, `../../utils/paths`) → `@cassicore/foundation`. Landed (`flux-team GBR`, `mnemic-field`,
   `lamina`→Part B, `constellation` solo-runner) → the `@cassicore/*` package. Vendor → `../../vendor/<rel-from-D-repo-root>.js`.
   Do NOT touch builtins/npm/internal `./X.js` (and bare `crypto/fs/path/os` in embeddings are builtins — leave them).

4. **Write the vendor stubs** per §A2.2/B2.2/C2.2/D2.2/E2.2. Type-only = faithful type surfaces. The RUNTIME ones
   (Open Flags 4/5/6/8): `createReasoningBank`, `AuditStore`, `prefixedId`, `TTLCache`, `isGamingMode` → exact
   self-contained copies. `runSoloExplorer` → forwarding re-export of `@cassicore/constellation` IF exported, else a
   faithful stub (Open Flag 6). `getEmbeddingService`/`composeSystemPrompt`/`estimateTokens` are NOT Part-consumer
   stubs — they are re-pointed INBOUND from other packages to the real `@cassicore/embeddings` (§6 step 7).

5. **Write/verify public barrels.** A: `src/dreamer/index.ts`, `src/reverie/index.ts`, `src/subconscious/index.ts`
   preserved verbatim (do NOT rename exports — DreamerModule/ReverieModule/Subconscious + their factory/method
   surfaces). B: `src/lamina/index.ts`, `src/locus-bridge/index.ts` verbatim (LaminaField, LaminaStore, LocusBridge +
   helper re-exports). C: `src/training/index.ts`, `src/trust-ledger/index.ts` verbatim (TrainingWarehouse,
   TrustLedger/createTrustLedger). D: `src/workspace/index.ts`, `src/code-analysis/index.ts` verbatim (GlobalWorkspace,
   RadianceLoop, analyze*). E: **write a fresh `src/index.ts`** (no source barrel — Open Flag 7).

6. **Package scaffold (×5).** `package.json` (`@cassicore/<name>`, `type: module`, deps `@cassicore/foundation`
   + `better-sqlite3` [B, C, D, E] + `uuid` [A]), tsconfig (rootDir src/outDir dist/declaration true),
   vitest.config.ts, `.gitignore`, README. No `lmdb`/`cassi-larql` in Group B (no native deps beyond better-sqlite3).

7. **Inbound re-point (REQUIRED — Open Flag 8).** After E (embeddings) lands: re-point helix's
   `shared/{posture-store,token-estimation}.ts` + constellation's `embeddings/{embedding-service,types}.ts` +
   `shared/posture-store.ts` → `@cassicore/embeddings`, delete stubs (the runtime `getEmbeddingService`/`composeSystemPrompt`/
   `estimateTokens` must resolve to the real fns). After B (lamina-locus-bridge) lands: re-point helix's `lamina/index.ts`
   + constellation's `lamina/index.ts` → `@cassicore/lamina-locus-bridge`. After D (workspace) lands: re-point
   foundation's `workspace/index.ts`, helix's `workspace/index.ts`, constellation's `workspace/{index,global-workspace,
   cognitive-signal}.ts` + `code-analysis/{feedback-tracker,specificity-scorer,types}.ts` → `@cassicore/workspace`.
   After A (dreamer-reverie-subconscious) lands: re-point foundation's `dreamer/types.ts` + constellation's
   `subconscious/types.ts` → `@cassicore/dreamer-reverie-subconscious`. Re-typecheck each consumer after swapping.
   `flux-team` is the re-point DESTINATION for Part-A/C `GlobalBlackboardRegistry` (already published at P3) — no stub
   to delete, just import `@cassicore/flux-team`.

8. **Tests.** Port the matching `tests/**` per package (`tests/dreamer`, `tests/reverie`, `tests/subconscious`,
   `tests/lamina`, `tests/locus-bridge`(void), `tests/training`, `tests/trust-ledger`, `tests/workspace`,
   `tests/code-analysis`, `tests/embeddings`, `tests/shared` as present in D:). Host-wired tests that import
   `core/daemon.ts`/`createIntelligence()` routes → `tests/host-wired/` quarantine (plan §6); do NOT count them in
   passing totals. Report actual ported-vs-quarantined vitest counts with P5B DONE.

9. `npm run typecheck` (`tsc --noEmit`) in each of the five packages + each re-pointed consumer (foundation, helix,
   constellation); fix ONLY mechanical path errors. Then `npm test` for the ported suites (skip project-wide suites,
   per worker contract). Do NOT `npm install` beyond noting the deps.

10. **Commit discipline (plan §3c):** per package, (1) history-splice import commit, (2) rewrite-delta commit (this
    table + vendor + barrel(s) + package.json), (3) inbound re-point commit(s) across foundation/helix/constellation.
    Keep import/rewrite/re-point in SEPARATE commits; verify `git log --follow` before each rewrite commit; do NOT
    commit to D:; the workspace push is handled by the owner (parallel sessions commit there — leave this file
    untracked).

### Files with no external or relocated imports (copy verbatim, zero rewrites)
Part A: `reverie/tool-filter.ts`, `reverie/trigger.ts`, `subconscious/heuristic-observer.ts`(builtin `uuid` only),
`subconscious/system-model.ts`(foundation `events/intelligence/interfaces` all→foundation — still 0 rewritten? no:
`../../../types/*`→foundation, so these DO carry rewrites). **Zero-rewrite files are only those with NO foundation and
NO vendor/landed escape and no builtin that changes: none in Part A (every file imports foundation `types/*`).**
Part B: `locus-bridge/spark-extractor.ts`(foundation interfaces only → 1 rewrite), `locus-bridge/window-assembler.ts`(foundation
interfaces → 1). Part C: none (all import foundation or a landed/vendor). Part D: `code-analysis/index.ts`(no imports),
`workspace/radiance-types.ts`(no imports — clean), `workspace/cognitive-signal.ts`(no imports), `workspace/index.ts`
(pure barrel, no imports). Part E: `shared/posture-store.ts`, `shared/token-estimation.ts` (no imports — clean),
`embeddings/types.ts` (no imports — clean). **These 6+ files copy verbatim with zero rewrites.**

---

# §7. Reply summary (for the session owner)

- **Live-set counts (all LIVE; 0 DEAD, 0 UNCERTAIN across all five packages):**
  - `@cassicore/dreamer-reverie-subconscious`: **17** (dreamer 4 + reverie 7 + subconscious 6).
  - `@cassicore/lamina-locus-bridge`: **12** (lamina 6 + locus-bridge 6).
  - `@cassicore/training-trust-ledger`: **10** (training 8 + trust-ledger 2).
  - `@cassicore/workspace`: **22** (workspace 12 + code-analysis 10).
  - `@cassicore/embeddings`: **7** (embeddings 5 + shared 2).
  - **Total Group B: 68 files migrated.**
- **Rewrite-pair totals by class:**
  - Foundation (`@cassicore/foundation`): A **7** · B **2** · C **3** · D **1** · E **1** = **14 unique foundation pairs.**
  - Landed `@cassicore/*` (flux-team GBR ×2 uses, mnemic-field, lamina→PartB, constellation solo-runner): ~**4 unique**
    (counted with the `@cassicore/*` package classes; merged into the foundation+landed rows above per package).
  - Vendor type/runtime stub (`../../vendor/...`): A **7** · B **3** · C **1** · D **1** (+solo-runner if vendored) ·
    E **1** = **13–14 unique vendor pairs.**
  - Internal (unchanged `./X.js`): **0 rewrite pairs** (all preserved by mirror). Builtins/npm: **0.**
  - **Grand total: ~30 unique rewrite targets** across 68 files; 24± files carry ≥1 rewrite (the rest are zero-rewrite
    pure/no-import files).
- **Inbound-stub sweep (grep of workspace packages, NOT D:):** Group-B vendor stubs exist in **THREE landed packages**
  (foundation P1, helix P2, constellation pre-existing) + flux-team is a re-point DESTINATION (already published). No
  mini-helix Group-B imports. Full re-point set:
  - → `@cassicore/workspace`: foundation(1 `workspace/index`), helix(1 `workspace/index`), constellation(5:
    `workspace/{index,global-workspace,cognitive-signal}` + `code-analysis/{feedback-tracker,specificity-scorer,types}`).
  - → `@cassicore/lamina-locus-bridge`: helix(1 `lamina/index`), constellation(1 `lamina/index`).
  - → `@cassicore/embeddings`: helix(2 `shared/{posture-store,token-estimation}`), constellation(3 `embeddings/
    {embedding-service,types}` + `shared/posture-store`) — runtime `getEmbeddingService`/`composeSystemPrompt`/
    `estimateTokens` must resolve to the real `@cassicore/embeddings`.
  - → `@cassicore/dreamer-reverie-subconscious`: foundation(1 `dreamer/types`), constellation(1 `subconscious/types`).
  - **runtime-vs-type:** runtime = `getEmbeddingService`, `composeSystemPrompt`, `estimateTokens`, `isGamingMode`,
    `AuditStore`, `prefixedId`, `TTLCache`, `runSoloExplorer` (all must be real, not throw stubs). type = `GlobalWorkspace`,
    `CognitiveSignal`, `SignalType`, `LaminaField`, `CorticalField`, `ModuleSessionRegistry`, `SessionDigest`,
    `DreamerConfig`, `SubconsciousConfig`-family, `ToolCallResult`.
- **Registry-discovery surfaces (P7 note):** Group B has exactly **three `BaseCognitiveModule` subclasses** —
  `DreamerModule` (dreamer), `ReverieModule` (reverie), `TrustLedger` (trust-ledger) — plus `Subconscious` (plain class,
  wired like a module). ALL are **explicitly wired in `createIntelligence()`** (NOT registry-discovered); daemon
  skip-set lists `subconscious`/`embeddings`/`dreamer`/`trust-ledger` (NOT reverie — the gap, Open Flag 2).
  `GlobalWorkspace`, `LaminaField`, `LocusBridge`, `TrainingWarehouse`, `getEmbeddingService` singleton are explicit
  wired companions. The P7 host must reproduce all these wirings + keep the skip-set equivalent.
- **Open flags (8, defaults recommended):** §5 — (1) grouping vs plan, (2) reverie auto-discovery trap, (3)
  module-session-registry/context-distiller placement, (4) runtime vendored symbols, (5) gaming-mode is vendor-not-foundation,
  (6) radiance-loop→constellation vs vendor solo-runner, (7) embeddings fresh index.ts barrel, (8) inbound re-point scope
  across foundation/helix/constellation (+ runtime-vs-type).
