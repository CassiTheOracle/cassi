# P3 — `@cassicore/flux-team` + `@cassicore/mini-helix` — Migration Table (Planning Deliverable)

**Sources (READ-ONLY, D:):** `core/intelligence/flux-team/` + `core/intelligence/mini-helix/`
**Destinations:** `C:\Users\Carina\Workspaces\CassiCore\packages\flux-team\src\` and `packages\mini-helix\src\`
**Recon:** `C:\Users\Carina\Workspaces\CassiCore\recon-data.json`
**Plan:** `C:\Users\Carina\Workspaces\CassiCore\CASSI-MIND-PLAN.md` §5-P3, §4
**Exemplars (house format):** `P1-foundation-migration-table.md`, `P2-helix-migration-table.md`
**Date:** 2026-08-13
**Status:** PLANNING — executor applies rules verbatim in a later wave. Nothing migrated, nothing committed.

> **Constraint honored:** no file under `D:\carina\workspaces\cassicore` is modified (plan §5 line 27). This
> deliverable is the only file written by this drafting pass; it is NOT git-added/committed (a parallel
> session is committing in the workspace — this file must stay untracked).

> **Two packages, one phase.** This phase migrates TWO `@cassicore/*` packages (plan §5-P3). Each has its own
> dest layout, vendor tree, and rewrite table. **Part A = `@cassicore/flux-team`** (deprecated blackboard
> cluster), **Part B = `@cassicore/mini-helix`**. They share the P1 foundation substrate and both consume a
> common vendor stub (`core/model-pool/types.ts`) and a common foundation surface — so their two history
> imports + two rewrite commits are sequenced independently (see §6) but reference the same foundation barrel.

> **Cross-package dependency established at P3:** the P2 helix package (IN FLIGHT) vendored
> `core/intelligence/mini-helix/mini-helix-runner.ts` (runtime `createMiniHelixSession` placeholder) +
> `mini-helix-types.ts` as *stubs* that re-point to `@cassicore/mini-helix` at P3. Publishing
> `@cassicore/mini-helix` is what REPLACES those helix stubs (§3.1 / Open Flag 6). Nothing in P2 helix imports
> flux-team's `index.ts`; helix imports flux-team files directly (`blackboard.js`, `plan-handler.js`) — those
> re-point to `@cassicore/flux-team` at P3 (Part B repoint log §3.1).

---

# PART A — `@cassicore/flux-team`

**Source (READ-ONLY):** `D:\carina\workspaces\cassicore\core\intelligence\flux-team\`
**Destination:** `C:\Users\Carina\Workspaces\CassiCore\packages\flux-team\src\`

## A1. Live-set (files to migrate)

Source dir `core/intelligence/flux-team/` contains **6 files, 0 subdirectories** (verified via directory
listing). Liveness verdicts are from `recon-data.json` (`deadFiles` / `uncertainFiles`). **0 DEAD, 1 UNCERTAIN
(`index.ts`), 5 LIVE.** The `index.ts` UNCERTAIN is resolved to **migrate** (it is the package entry barrel over
the 5 LIVE siblings — see Open Flag 1). No flux-team file appears in `deadFiles`.

| # | source path (D:) | dest path (packages/flux-team/src/) | size | recon verdict | verdict note |
|---|---|---|---|---|---|
| 1 | `blackboard.ts` | `blackboard.ts` | 66.3 KB | LIVE | `Blackboard` class (2160 lines); highest fanout |
| 2 | `blackboard-tools.ts` | `blackboard-tools.ts` | 63.1 KB | LIVE | meta-tool schemas + `handleBlackboardToolCall` (1740 lines) |
| 3 | `plan-handler.ts` | `plan-handler.ts` | 12.9 KB | LIVE | `PlanHandler` (⊃ P1/P2 `PlanHandler` type consumer) |
| 4 | `global-blackboard-registry.ts` | `global-blackboard-registry.ts` | 10.0 KB | LIVE | `GlobalBlackboardRegistry` (⊃ P1 type stub) |
| 5 | `blackboard-search.ts` | `blackboard-search.ts` | 10.1 KB | LIVE | runtime search/cursor helpers (distinct from `types/blackboard-search.ts` → foundation) |
| 6 | `index.ts` | `index.ts` (package entry barrel) | 1.8 KB | UNCERTAIN | `live-name-ref:48`; resolves to **MIGRATE** (pure barrel re-exporting the 5 LIVE siblings — Open Flag 1) |

**Live-set count (flux-team): 6 migrated files** (5 LIVE + `index.ts` UNCERTAIN→migrate as entry barrel). **0 DEAD, 0 excluded-uncertain.**

> **`blackboard-search.ts` naming collision (resolved).** The plan's scope line says "blackboard, blackboard-search,
> global-blackboard-registry, blackboard-tools" — but ONLY the **flux-team runtime** `blackboard-search.ts`
> (cursor encode/decode, pagination, pattern validation, ~285 lines) is in this directory. The **type-only**
> `types/blackboard-search.ts` (9.5 KB) is a DIFFERENT file that went to **foundation in P1** (P1 exemplar row 7). Both
> exist; flux-team's runtime `blackboard-search.ts` imports the foundation type file. **Do not conflate them:** the
> flux-team file migrates here; the foundation type file stays in `@cassicore/foundation`. See A4a/A4c.

**Explicitly EXCLUDED (flux-team):** none. **DEAD:** 0. **UNCERTAIN resolved:** `index.ts` → migrate (§A1 row 6).

---

## A2. Rewrite table (Part A flux-team — mechanical string-substitution pairs)

**Mirror rule for vendor type stubs.** Every external (non-flux-team, non-foundation) target is reproduced as a
**type stub at `src/vendor/<rel-path-from-D-repo-root>.ts`** (the Constellation A3 / P1 / P2 pattern).

**Foundation rule (P3-specific).** Every import resolving to the P1 shared substrate → **`@cassicore/foundation`**
(named import of the symbols flux-team uses from that foundation module; executor verifies each is in the landed
foundation barrel — see A4d). NOT vendored, NOT relative.

**Extension rule.** Source keeps `.js` import specifiers verbatim; only the specifier is rewritten. For
`@cassicore/foundation` the `.js` extension is dropped (package specifier).

**Scope rule.**
- **DO NOT touch** Node builtins (`crypto`, `node:crypto`, `node:fs`, `node:path`, `node:os`) and internal
  imports that remain valid after relocation (all `./X.js` siblings — the FLAT layout keeps every flux-team
  internal import unchanged).
- **REWRITE** (a) every P1-foundation import → `@cassicore/foundation`, and (b) every import resolving OUTSIDE the
  P3 live-set + outside foundation → `./vendor/<rel-from-D-repo-root>.js` stub. **DEPTH FIX (P2 lesson): the
  flux-team and mini-helix files land FLAT at `src/`, BESIDE `src/vendor/`, so the vendor prefix is `./vendor/...`
  (one dot) — NOT the `../vendor/...` used by P2 helix. A `../vendor/` prefix would resolve outside `src/` and is
  wrong for a flat layout.**
- Apply only to actual `import` / `import type` / re-export / inline `import('…')` statements — NOT to
  string/comment content resembling imports (files carry `// REMOVED: …` comments and inline
  `import('../../../types/flux-team.js')` type casts at lines ~1304/1576/1662/1695/1720 — ALL rewritten as
  foundation).
- Inline `import('…')` type expressions on listed targets are rewritten identically.

### A2.1 Foundation rewrite pairs (→ `@cassicore/foundation`)

| original specifier | dest specifier | consumed by (source files + symbols) |
|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | blackboard (`ILogger`), global-blackboard-registry (`ILogger`), plan-handler (`ILogger`) |
| `../../../types/flux-team.js` | `@cassicore/foundation` | blackboard (`BlackboardChannel`, `BlackboardEntry`, `BlackboardState`, `BlackboardSubscription`, `FluxScratchpadEntry`, `FluxToolRecord`, `ArtifactEntry`, `FluxCellResult`, `Plan`, `PlanStep`, `PlanStepStatus`, `Report`, `ReportSection`, `ReportSectionType`, `ReportSectionStatus`, `ReportQualityMetrics` — type-only + inline casts), global-blackboard-registry (`BlackboardChannel/Entry/State`, `FluxScratchpadEntry`, `FluxToolRecord`, `ArtifactEntry`, `PlanStep`, `ReportSection` — type-only), plan-handler (`Plan`, `PlanStep` — type-only), blackboard-tools (inline `import('../../../types/flux-team.js')` type casts at lines 1304, 1576, 1605, 1662, 1695, 1698, 1721 — **7 sites**, type-casting `ReportSectionType`, `PlanStep`, `Plan`, `BlackboardChannel`, `ReportSectionStatus`) — **COVERAGE: all inline casts enumerated, all → foundation** |
| `../../../types/blackboard-search.js` | `@cassicore/foundation` | blackboard (`PaginatedResult`, `ChannelSearchOptions`, `ScratchpadSearchOptions`, `ToolLogSearchOptions`, `ArtifactSearchOptions`, `PlanSearchOptions`, `ReportSearchOptions`, `CrossBoardSearchOptions`, `CrossBoardSearchResult`, `CrossBoardResultItem`, `BoardSearchResult`, `SearchableBoard`, `ChangeWindow`, `BoardChanges`, `BlackboardWatchResult`, `WatchSummary` — type-only), global-blackboard-registry (`PaginatedResult`, `ChannelSearchOptions`, `ScratchpadSearchOptions`, `ToolLogSearchOptions`, `ArtifactSearchOptions`, `PlanSearchOptions`, `ReportSearchOptions`, `CrossBoardSearchOptions`, `CrossBoardSearchResult`, `ChangeWindow`, `BlackboardWatchResult`, `SearchableBoard` — type-only), blackboard-search (`MAX_PATTERN_LENGTH`, `DEFAULT_SEARCH_LIMIT`, `MAX_SEARCH_LIMIT` — **runtime constants** + `SearchCursor`, `PaginatedResult`, `BaseSearchOptions` — type-only, + re-export `export { MAX_PATTERN_LENGTH, DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT }`), blackboard-tools (inline `import('../../../types/blackboard-search.js')` type cast at line 1639 — **1 site**) — **COVERAGE: exhaustive; all inline casts across both dirs enumerated** |
| `../../../types/runtime.js` | `@cassicore/foundation` | blackboard-tools (`CompletionOpts` — type-only) |

### A2.2 Vendor stub rewrite pairs (→ `./vendor/<rel-from-D-repo-root>.js`)

| original specifier | dest specifier | consumed by (symbols) |
|---|---|---|
| `../shared-tools/commit-tool.js` | `./vendor/core/intelligence/shared-tools/commit-tool.js` | blackboard-tools (`COMMIT_CHANGES_TOOL` — **runtime const**, `handleCommitChanges` — **runtime fn**; see A4e) |

### A2.3 Internal (unchanged) + builtins

- **Internal (stay valid under flat layout, 0 rewrites):** `./blackboard.js`, `./blackboard-tools.js`,
  `./blackboard-search.js`, `./global-blackboard-registry.js`, `./plan-handler.js` — all flux-team siblings land
  in the same `src/` dir, so every `./X.js` import is unchanged.
- **Builtins/npm (unchanged):** `crypto` (blackboard), `node:crypto`/`node:fs`/`node:path` (blackboard-tools),
  `node:fs`/`node:path`/`node:os` (global-blackboard-registry). 0 npm external deps in flux-team.

### A2.4 Rewrite-pair tally (Part A flux-team)

- **Foundation (`@cassicore/foundation`): 4 unique pairs.**
- **Vendor type/runtime stub (`./vendor/...`): 1 unique pair.**
- **Internal (unchanged `./X.js`): 0 rewrite pairs** (all stay valid under flat layout) — 5 internal specifiers stay.
- **Builtins (unchanged): 0 rewrite pairs** (`crypto`, `node:crypto`, `node:fs`, `node:path`, `node:os`).
- **Total rewrite pairs (Part A): 5.** (Global per-specifier replacement; `../../../types/flux-team.js` occurs in
  multiple files and as 7 inline `import('…')` casts in blackboard-tools.ts + 1 inline
  `import('../../../types/blackboard-search.js')` cast (line 1639) — the executor replaces EVERY occurrence per file.)

---

## A3. Destination layout (Part A flux-team)

```
packages/flux-team/
  package.json                     # name: "@cassicore/flux-team", type: module, deps: @cassicore/foundation
  tsconfig.json                    # rootDir src/ outDir dist/ declaration true
  vitest.config.ts                 # ported flux-team tests (tests/flux-team/**)
  README.md                        # MUST carry the source DEPRECATED marker (see A4a)
  src/
    index.ts                       # entry barrel = migrated flux-team/index.ts verbatim (re-exports
                                   #   Blackboard, GlobalBlackboardRegistry, blackboard-tools surface)
    blackboard.ts                  # Blackboard class (2160 lines)
    blackboard-tools.ts            # meta-tool schemas + handleBlackboardToolCall (1740 lines)
    blackboard-search.ts           # runtime search/cursor helpers (RUNTIME — distinct from foundation type)
    global-blackboard-registry.ts  # GlobalBlackboardRegistry
    plan-handler.ts                # PlanHandler (deprecated-in-source, kept for BC)
    vendor/                        # stubs ONLY — mirror original D: rel-paths (see A3.1)
      core/
        intelligence/
          shared-tools/commit-tool.ts   # COMMIT_CHANGES_TOOL (runtime const), handleCommitChanges (runtime fn)
```

**Internal-import consequences (all satisfied by the layout):** all 6 files land FLAT at `src/`, so every
`./X.js` flux-team-internal import stays valid unchanged. Foundation imports → `@cassicore/foundation`; the
single vendor stub is one `./vendor/...` hop.

### A3.1 Repoint log (Part A flux-team — vendor stubs / owning consumers)

flux-team is the OWNING package for the blackboard symbols that P1 and P2 vendored as stubs. At P3, those stubs
are re-pointed to `@cassicore/flux-team` and deleted.

| consumer package's stub (`src/vendor/...`) | exported symbols flux-team now provides | this phase re-points it to |
|---|---|---|
| foundation (P1) `core/intelligence/flux-team/plan-handler.ts` | `PlanHandler` | `@cassicore/flux-team` |
| foundation (P1) `core/intelligence/flux-team/blackboard.ts` | `Blackboard` | `@cassicore/flux-team` |
| foundation (P1) `core/intelligence/flux-team/global-blackboard-registry.ts` | `GlobalBlackboardRegistry` | `@cassicore/flux-team` |
| helix (P2, in flight) `core/intelligence/flux-team/plan-handler.ts` | `PlanHandler` | `@cassicore/flux-team` |
| helix (P2, in flight) `core/intelligence/flux-team/blackboard.ts` | `Blackboard` | `@cassicore/flux-team` |

flux-team's OWN vendor stub (this phase): `core/intelligence/shared-tools/commit-tool.ts`
(`COMMIT_CHANGES_TOOL`, `handleCommitChanges`) → owning package `@cassicore/*-shared-tools` (or a P5 shared
grouping) → **re-point at P5** (not P3).
flux-team's foundation type imports → `@cassicore/foundation` (already published, P1).

---

## A4. Known-hard items (Part A flux-team)

### A4a. Deprecation contract — blackboard is DEPRECATED in source; GlobalWorkspace supersedes at P5

`flux-team/index.ts` header (verbatim) states:

> "NOTE: Blackboard is deprecated per docs/design/constellation-enhancements-roadmap.md. Migration to
> GlobalWorkspace + HelixSynapse is pending (Phase 2). … REMOVED: FluxTeamOrchestrator, FluxCell, TopologyEngine,
> … are all deleted. All orchestration now uses Helix and Constellation."

**P3 decision default (from plan §5-P3, adopted):** import the LIVE blackboard files **as-is** (they are live at
runtime — see A4b), **mark `@cassicore/flux-team` package DEPRECATED in its README** (a `> **DEPRECATED:** …`
notice at the top mirroring the source header), and let the **overhaul session's GlobalWorkspace migration supersede**
it. The package's `index.ts` already carries the "Pending Removal (Phase 2)" banner — keep it verbatim.

**P5 contract note (GlobalWorkspace rewiring):** the plan (§3e.1 / P5 `@cassicore/lamina`/workspace grouping +
`core/intelligence/workspace/index.ts`) owns `GlobalWorkspace`, `CognitiveSignal`, `SignalType` (already vendored
in foundation + helix). When the P5 `workspace`/`lamina` package lands, the overhaul session's GlobalWorkspace
migration supersedes the blackboard; **the plan does NOT schedule blackboard deletion in P3** — deletion follows the
phase-gated D: debt scrub (§5) AFTER flux-team's migration is verified. **Contract note: do not let P3 delete or
trim any blackboard code; the deprecation marker is a README + header note only, not a behavioral change.**

### A4b. Is flux-team "registry-discovered"? (why the 5 blackboard files are LIVE)

The plan's P3 note says the blackboard files are "registry-discovered (live at runtime)". My verification of the
source (daemon.ts:2032-2051 registry `discover()` skip-set; `core/intelligence/index.ts`; grep of all live
importers) shows the more precise truth:

- **`flux-team/` is NOT in the daemon registry skip-set** (daemon.ts:2033-2051), and `registry.discover()` scans
  each intelligence subdir's `index.ts` for a `BaseCognitiveModule` subclass.
- **`flux-team/index.ts` exports NO `BaseCognitiveModule` subclass** (it re-exports `Blackboard`,
  `GlobalBlackboardRegistry`, and blackboard-tools functions) — so the registry's prototype-chain walk finds no
  registered module under `flux-team/`. It is NOT a registered intelligence module.
- **The blackboard files are LIVE by direct import-reachability** (recon §3e.1 override #1-fanout, not registry):
  `core/daemon.ts:31` imports `global-blackboard-registry.js`; `core/admin-api/blackboard.ts:25-26,42` imports
  `blackboard.js` + `blackboard-search.js` + `global-blackboard-registry.js`; `helix/*`, `constellation/*`,
  `cassi-agent/base-posture-runner.ts:41-42`, `ai-engineer/`, `ai-scientist/`, `dialectic/index.ts`,
  `context-distiller.ts`, `base/cognitive-module.ts:47` import `blackboard.js` / `plan-handler.js` /
  `global-blackboard-registry.js`.

**Conclusion (recorded):** the blackboard cluster crosses as LIVE via import-reachability, not registry discovery.
The registry-discovery framing in the plan is directionally right (these are runtime-live, so the "migrate LIVE
only" rule admits them) but the mechanism is direct imports. This does not change the P3 default — migrate all 6.
Marked [VERIFY] in Open Flag 2 for the executor to re-confirm the import-set state at P3 execution (the overhaul
session may rewire `core/intelligence/*`).

### A4c. Blackboard class transitive deps (the `blackboard.ts` cluster)

From a direct import-block read of `blackboard.ts` (head + full import block):

- `crypto` (`randomUUID`) — builtin.
- `../../../types/interfaces.js` → **foundation** — type-only `ILogger`. **NOTE: blackboard.ts does NOT import
  `IEventBus`** (the task hypothesis asked) — it pulls only `ILogger` from `interfaces.ts` (which is where
  `IEventBus` also lives, but blackboard doesn't reference it).
- `../../../types/flux-team.js` → **foundation** — type-only `BlackboardChannel/Entry/State/Subscription`,
  `FluxScratchpadEntry`, `FluxToolRecord`, `ArtifactEntry`, `FluxCellResult`, `Plan/PlanStep/PlanStepStatus`,
  `Report/ReportSection/ReportSectionType/ReportSectionStatus/ReportQualityMetrics`.
- `../../../types/blackboard-search.js` → **foundation** — type-only `PaginatedResult`, `ChannelSearchOptions`,
  `ScratchpadSearchOptions`, `ToolLogSearchOptions`, `ArtifactSearchOptions`, `PlanSearchOptions`,
  `ReportSearchOptions`, `CrossBoardSearchOptions/Result/ResultItem`, `BoardSearchResult`, `SearchableBoard`,
  `ChangeWindow`, `BoardChanges`, `BlackboardWatchResult`, `WatchSummary`.
- `./blackboard-search.js` → **flux-team internal runtime** — `compilePattern`, `matchesAny`, `normalizeLimit`,
  `decodeCursor`, `encodeCursor`, `paginate`, `passesBaseFilters`, `decodeCompositeCursor`,
  `encodeCompositeCursor` (all flux-team-local runtime helpers; migrate with the package — no event bus dep).

**No event-bus, no model-pool, no tools dependency in the `Blackboard` class itself.** Its only external runtime
dep is `crypto`. The `global-blackboard-registry.ts` adds `node:fs`, `node:path`, `node:os` (disk persistence).
The `blackboard-tools.ts` adds `shared-tools/commit-tool.js` (vendor) + `node:crypto/fs/path`.

### A4d. Foundation barrel coverage for flux-team/mini-helix (verify before rewiring)

Both P3 packages import ONLY these four foundation modules: `types/interfaces.ts` (`ILogger`/`IEventBus`),
`types/flux-team.ts`, `types/blackboard-search.ts`, `types/runtime.ts` (`CompletionOpts`, `Message`, `ContentBlock`,
`CompletionChunk`). All four are in the P1 live-set (P1 exemplar rows 1, 5, 7, 3). **The landed foundation `src/index.ts`
barrel MUST re-export these modules' named symbols.** Two specific verify points:
- `MINI_HELIX_DEFAULTS`/`MiniHelix*` come from **mini-helix** itself (NOT foundation) — foundation does not need them.
- The 3 search-limit **constants** (`MAX_PATTERN_LENGTH`, `DEFAULT_SEARCH_LIMIT`, `MAX_SEARCH_LIMIT`) are
  re-exported by flux-team's `blackboard-search.ts` from foundation's `types/blackboard-search.ts` — they are
  **runtime values**, so foundation must export them as values (not `import type`). [VERIFY] they are on the
  foundation barrel (§5 Open Flag 5).

### A4e. Vendor `commit-tool.ts` is a RUNTIME dependency, not type-only

`blackboard-tools.ts` imports `COMMIT_CHANGES_TOOL` (a runtime `ToolSchema` const) and `handleCommitChanges` (a
runtime function) from `core/intelligence/shared-tools/commit-tool.ts` (207 lines; itself imports `child_process`
+ foundation `ILogger`). A bare `throw` type stub breaks blackboard-tools at runtime (the tool schema is referenced
when `handleBlackboardToolCall` routes `commit_changes`). **Default: port `commit-tool.ts` as an exact-copy
self-contained stub at `src/vendor/core/intelligence/shared-tools/commit-tool.ts`** (it is a pure tool factory +
`execSync` wrapper; the only host dep is foundation `ILogger`). Re-point to `@cassicore/*-shared-tools` at P5. The
other Part A vendor (flux-team's own tree) has no further runtime stubs.

---

## A5. Open flags (Part A flux-team) — see combined §5 for the full ≤8 list

(Part A flags are shared with Part B in the combined open-flag list §5. Flags 1, 2, 5, 7, 8 below.)

---

# PART B — `@cassicore/mini-helix`

**Source (READ-ONLY):** `D:\carina\workspaces\cassicore\core\intelligence\mini-helix\`
**Destination:** `C:\Users\Carina\Workspaces\CassiCore\packages\mini-helix\src\`

## B1. Live-set (files to migrate)

Source dir `core/intelligence/mini-helix/` contains **3 files, 0 subdirectories** (verified). **0 DEAD, 1 UNCERTAIN
(`index.ts`), 2 LIVE.** The `index.ts` UNCERTAIN is resolved to **migrate** (package entry barrel over live
siblings — see Open Flag 1).

| # | source path (D:) | dest path (packages/mini-helix/src/) | size | recon verdict | verdict note |
|---|---|---|---|---|---|
| 1 | `mini-helix-runner.ts` | `mini-helix-runner.ts` | 15.0 KB | LIVE | `createMiniHelixSession` + `MiniHelixRunner` (513 lines) — the P2 helix stub target |
| 2 | `mini-helix-types.ts` | `mini-helix-types.ts` | 7.3 KB | LIVE | `MiniHelix*` types + `MINI_HELIX_DEFAULTS` (252 lines) |
| 3 | `index.ts` | `index.ts` (package entry barrel) | 520 B | UNCERTAIN | `live-name-ref:5`; resolves to **MIGRATE** (pure barrel re-exporting the 2 LIVE siblings — Open Flag 1) |

**Live-set count (mini-helix): 3 migrated files** (2 LIVE + `index.ts` UNCERTAIN→migrate as entry barrel). **0 DEAD, 0 excluded-uncertain.**

> **`mini-helix/index.ts` import-reachability, resolved.** All live consumers import the runner/types FILES
> directly (see below), NOT the `mini-helix/index.js` barrel — verified by grep:
> `constellation/corpus-mini-helix.ts:35-36`, `constellation/meditation/focused-seeding.ts:16-17`,
> `helix/brainstem-mini-helix.ts:34-38`, `helix/brainstem-tools.ts:21-25`, `tests/mini-helix.test.ts:8-15` all
> `import ... from '../mini-helix/mini-helix-runner.js'` / `'.../mini-helix-types.js'` directly. `index.ts`'s 5
> name-refs are `MiniHelix*` STRING references (`useMiniHelixCorpus`, `miniHelixDeps`), not imports. By the strict
> quarantine rule ("leave in the source set only if import-reachable by a live file") it is unreferenced — BUT it
> is the required package entry barrel and re-exports ONLY live siblings (no fabrication risk). Per Open Flag 1,
> **default = migrate** it as the package's `src/index.ts`. If the executor prefers the pure quarantine reading,
> hand-write a fresh barrel with the identical re-exports (content is 21 lines, 100% live re-exports).

---

## B2. Rewrite table (Part B mini-helix — mechanical string-substitution pairs)

Same **Mirror rule** / **Foundation rule** / **Extension rule** / **Scope rule** as Part A (§A2). All 3 files land
FLAT at `src/`.

### B2.1 Foundation rewrite pairs (→ `@cassicore/foundation`)

| original specifier | dest specifier | consumed by (source files + symbols) |
|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | mini-helix-runner (`ILogger`, `IEventBus`), mini-helix-types (`ILogger`, `IEventBus`) |
| `../../../types/runtime.js` | `@cassicore/foundation` | mini-helix-runner (`Message`, `ContentBlock`, `CompletionChunk`, `CompletionOpts`), mini-helix-types (`Message`, `ContentBlock`) |

### B2.2 Vendor stub rewrite pairs (→ `./vendor/<rel-from-D-repo-root>.js`)

| original specifier | dest specifier | consumed by (symbols) |
|---|---|---|
| `../../model-pool/types.js` | `./vendor/core/model-pool/types.js` | mini-helix-runner (`ModelHandle`, `ModelCompletionOpts` — type-only), mini-helix-types (`ModelHandle` — type-only) |

### B2.3 Internal (unchanged) + builtins

- **Internal (stay valid under flat layout, 0 rewrites):** `./mini-helix-types.js`, `./mini-helix-runner.js`.
- **Builtins/npm (unchanged):** none. **0 npm external deps** in mini-helix (no `better-sqlite3`).

### B2.4 Rewrite-pair tally (Part B mini-helix)

- **Foundation (`@cassicore/foundation`): 2 unique pairs.**
- **Vendor type stub (`./vendor/...`): 1 unique pair.**
- **Internal (unchanged `./X.js`): 0 rewrite pairs** (2 internal specifiers stay).
- **Builtins (unchanged): 0.**
- **Total rewrite pairs (Part B): 3.** (Global per-specifier replacement per file.)

### B2.5 Coverage audit — all imports accounted for (P2 lesson applied)

Exhaustive re-extraction of **every** import token (including inline `import('…')` and multiline) from ALL 9
migrated files (6 flux-team + 3 mini-helix), with block/line comments stripped, confirms **zero uncovered
imports**:

- **Part A flux-team** (6 files): 4 foundation specifiers + 1 vendor specifier + 5 internal (unchanged) +
  5 builtin names — every token in §A2.1/A2.2/A2.3. The 8 inline `import('…')` cast sites in blackboard-tools.ts
  (7× flux-team.js, 1× blackboard-search.js) are all → foundation and enumerated in §A2.1.
- **Part B mini-helix** (3 files): 2 foundation specifiers + 1 vendor specifier + 2 internal (unchanged) +
  0 builtins — every token in §B2.1/B2.2/B2.3.

**No `mcp/*`, `cassi-agent/base-posture-runner`, `utils/activity-timeout`, or `constellation/*` imports exist in
the flux-team/mini-helix source dirs** (those were P2 helix/module gaps, not P3 — re-verified absent here). The
full per-file token listing used for this audit is recorded in the drafting ticket. **Nothing to add beyond the
pairs already listed.**

---

## B3. Destination layout (Part B mini-helix)

```
packages/mini-helix/
  package.json                     # name: "@cassicore/mini-helix", type: module, deps: @cassicore/foundation
  tsconfig.json                    # rootDir src/ outDir dist/ declaration true
  vitest.config.ts                 # ported mini-helix tests (tests/mini-helix.test.ts)
  src/
    index.ts                       # entry barrel = migrated mini-helix/index.ts verbatim: re-exports the 13
                                   #   MiniHelix* types + MINI_HELIX_DEFAULTS + createMiniHelixSession
    mini-helix-runner.ts           # createMiniHelixSession + MiniHelixRunner (513 lines)
    mini-helix-types.ts            # MiniHelix* types + MINI_HELIX_DEFAULTS (252 lines)
    vendor/                        # type stubs ONLY — mirror original D: rel-paths (see B3.1)
      core/
        model-pool/types.ts        # ModelHandle, ModelCompletionOpts (type-only; re-point P6)
```

**Internal-import consequences (all satisfied by the layout):** all 3 files land FLAT at `src/`, so
`./mini-helix-types.js` / `./mini-helix-runner.js` internal imports stay valid unchanged. Foundation imports →
`@cassicore/foundation`; the single `model-pool/types` vendor stub is one `./vendor/...` hop.

### B3.1 Repoint log (Part B mini-helix — the P3-injects-into-P2 step)

mini-helix is the OWNING package for the mini-helix symbols P2 (helix, IN FLIGHT) vendored as stubs. At P3, the
executor re-points those helix stubs to `@cassicore/mini-helix` AND deletes them (P2 §3.1).

| consumer package's stub (`src/vendor/...`) | exported symbols | this phase re-points it to |
|---|---|---|
| helix (P2, in flight) `core/intelligence/mini-helix/mini-helix-types.ts` | `MiniHelixTool/…/MiniHelixConfig` | `@cassicore/mini-helix` |
| helix (P2, in flight) `core/intelligence/mini-helix/mini-helix-runner.ts` | `createMiniHelixSession` (**runtime fn placeholder** — P2 Open Flag 5) | `@cassicore/mini-helix` |

mini-helix's OWN vendor stub (this phase): `core/model-pool/types.ts` (`ModelHandle`, `ModelCompletionOpts`) →
owning package `@cassicore/model-pool` → **re-point at P6** (not P3).
mini-helix's foundation type imports → `@cassicore/foundation` (published, P1).

> **`createMiniHelixSession` real signature — the P2 helix stub must match this EXACTLY** (from
> `mini-helix-runner.ts` lines 43-49, verbatim):
> ```ts
> export function createMiniHelixSession(
>   tools: MiniHelixTool[],
>   config: MiniHelixConfig,
>   deps: MiniHelixDeps,
> ): MiniHelixSession
> ```
> `MiniHelixTool[] = { def: MiniHelixToolDef; handler: MiniHelixToolHandler }[]`; `MiniHelixConfig` carries
> `consumer: 'corpus'|'brainstem'`, `systemPrompt: string`, …; `MiniHelixDeps = { logger: ILogger; eventBus?,
> handleFactory, … }`; returns the `MiniHelixSession` interface (`run(userMessage?): Promise<MiniHelixResult>`,
> `cancel(): void`, …). The P2 table (§2.2, symbol map) already captured these names correctly. Verify the landed
> P2 stub against this signature before wiring (Open Flag 5).

---

## B4. Known-hard items (Part B mini-helix)

### B4a. mini-helix is a pure library — no BaseCognitiveModule, no registry discovery

`mini-helix/index.ts` exports types + `createMiniHelixSession` (a factory) — it does **NOT** extend
`BaseCognitiveModule`, and `mini-helix` is NOT in the daemon registry skip-set either (daemon.ts:2033-2051 omits
it) because it has no discoverable module class. It is a **library consumed by explicit imports** from
constellation (Corpus + meditation) and helix (Brainstem) — exactly the P2 table's finding. **P7 host note:** the
mini-helix package must NOT be treated as a registered intelligence module; it is a dependency of the
constellation/helix packages, wired via import. No seam beyond the package-import boundary.

### B4b. Mini-helix model-pool dependency (the only external)

Both `mini-helix-runner.ts` and `mini-helix-types.ts` import `ModelHandle`/`ModelCompletionOpts` from
`../../model-pool/types.js` — TYPE-ONLY (mini-helix uses `handleFactory` to acquire handles; it does not
construct `ModelHandle` internals). This is a clean type stub → `@cassicore/model-pool` (P6). **No `better-sqlite3`,
no subprocess/worker entries** (grep for fork/worker_threads/import.meta.url across the 3 mini-helix files → none).

### B4c. Test surface

- `tests/flux-team/` — **4 test files** (blackboard-search.test.ts, blackboard-watch.test.ts, blackboard.test.ts,
  plan-handler.test.ts), all importing `../../core/intelligence/flux-team/blackboard(.search).js` /
  `plan-handler.js` + foundation types (`types/interfaces.js`, `types/flux-team.js`). Port → `packages/flux-team/tests/`
  with imports repointed to `@cassicore/flux-team` + `@cassicore/foundation`. They use only `vitest` + mock loggers
  (self-contained) → **NOT host-wired**; count in P3 flux-team passing total.
- `tests/mini-helix.test.ts` — imports `createMiniHelixSession` + `MiniHelix*` from mini-helix AND
  `createBrainstemTools`/`buildBrainstemSystemPrompt` from **helix** `brainstem-tools.js` + `BrainstemToolContext`.
  Port → `packages/mini-helix/tests/`, repointing the mini-helix imports to `@cassicore/mini-helix`; the **helix**
  brainstem-tools references become `@cassicore/helix` (P2) imports. Since helix (P2) is the upstream producer,
  the ported mini-helix test is a **cross-package test** — **Default: treat as host-wired** (`tests/host-wired/`
  quarantine per plan §6) until P2 lands, then re-point and count in P3 DONE once `@cassicore/helix` is present.
  Report actual ported-vs-quarantined vitest counts (Open Flag 7).

---

## B5. Open flags (Part B mini-helix) — see combined §5

---

# §5. Combined open flags (Part A + Part B — max 8; defaults recommended)

1. **`index.ts` UNCERTAIN resolution for BOTH packages (flux-team/index.ts + mini-helix/index.ts) → migrate as
   package entry barrel.** Both are pure barrels re-exporting ONLY live siblings (`flux-team/index.ts` → 5 live
   flux-team files; `mini-helix/index.ts` → 2 live mini-helix files). Neither is import-reachable by a live file
   as a barrel, but each is the package's required `src/index.ts`. **Default: migrate both verbatim.** If the
   strict quarantine reading is preferred for mini-helix (truly unreferenced), hand-write a fresh 21-line barrel
   with identical re-exports (no fabrication); for flux-team, the barrel's re-exports overlap the live-file
   imports (foundation/P2 consumers import the files, not the barrel) — treat the same way. Mark [VERIFY] at P3
   execution that no live consumer imports these barrels via a path we missed.
2. **flux-team "registry-discovered" claim vs import-reachability (A4b).** The plan says blackboard files are
   "registry-discovered"; my source verification shows `flux-team/index.ts` exports no `BaseCognitiveModule`
   subclass and the cluster is live via direct imports (daemon, admin-api, helix, constellation, cassi-agent,
   ai-engineer, ai-scientist, dialectic, context-distiller, base/cognitive-module). This does NOT change the P3
   default (migrate all 6). [VERIFY] at P3 execution that the overhaul session hasn't rewired/swapped any of these
   flux-team consumers or the blackboard files themselves. **Default: migrate the 5 live files + index barrel as
   spec'd; deprecation marker only, no behavioral trim.**
3. **`shared-tools/commit-tool.ts` (Part A vendor) is a RUNTIME dependency.** blackboard-tools calls
   `handleCommitChanges` and references `COMMIT_CHANGES_TOOL` at runtime; a type-only stub breaks it. **Default:
   port commit-tool.ts as an exact-copy self-contained stub** (pure tool factory + `execSync` re-export; only host
   dep is foundation `ILogger`). Re-point to `@cassicore/*-shared-tools` at P5. Mark [VERIFY] blackboard-tools'
   `commit_changes` route is not exercised in a way the stub can't satisfy (it is a full faithful copy, so this is
   low risk).
4. **`model-pool/types.js` (Part B vendor) is type-only — clean stub.** `ModelHandle`/`ModelCompletionOpts` are
   TYPE-ONLY in both mini-helix files; a faithful type stub satisfies the build with zero runtime risk. **Default:
   vendor the type stub now, re-point to `@cassicore/model-pool` at P6.** No open decision.
5. **Foundation barrel must export the runtime search constants.** flux-team's `blackboard-search.ts`
   re-exports `MAX_PATTERN_LENGTH`, `DEFAULT_SEARCH_LIMIT`, `MAX_SEARCH_LIMIT` from foundation's
   `types/blackboard-search.js` as VALUES (runtime), and blackboard.ts imports `compilePattern`/`paginate`/etc.
   from flux-team's own runtime file. Verify the landed P1 foundation barrel exports these 3 constants as named
   value exports (not `import type`), plus `ILogger`/`IEventBus`/`CompletionOpts`/`Message`/`ContentBlock`/
   `CompletionChunk` and the flux-team/blackboard-search type names both P3 packages consume. **Default: if any
   is missing from the foundation barrel, add it in P3's rewrite commit (foundation is published; a follow-up
   foundation edit + re-point is cleaner than vendoring).** [VERIFY].
6. **P2→P3 mini-helix stub replacement is a REQUIRED P3 TASK.** Publishing `@cassicore/mini-helix` replaces
   helix's `src/vendor/core/intelligence/mini-helix/mini-helix-runner.ts` (runtime `createMiniHelixSession`
   placeholder) + `mini-helix-types.ts` stubs with real `@cassicore/mini-helix` imports. **Add to the P3 executor
   playbook (A6/B6): "repoint helix mini-helix stubs to real @cassicore/mini-helix"** after the mini-helix package
   lands and typechecks. Sequence: mini-helix package builds → helix stub swap → helix typecheck. (Plan's P2
   executor was told this lands at P3.) [VERIFY] helix's stub signature matches B3.1's quoted `createMiniHelixSession`
   signature before wiring.
7. **Ported test surface & host-wired split.** `tests/flux-team/**` (4 files) is self-contained → port into
   `@cassicore/flux-team/tests/`, repoint to package imports, **count in P3 passing total**. `tests/mini-helix.test.ts`
   imports helix `brainstem-tools.js` (P2) → **Default: port to `tests/host-wired/` quarantine** (plan §6) until P2
   helix is present, then re-point to `@cassicore/helix` and count once helix lands. Report actual ported-vs-
   quarantined vitest counts with P3 DONE (plan §6).
8. **Deprecation marker scope (flux-team README).** `@cassicore/flux-team` is shipped **DEPRECATED**: mark the
   README (`> **DEPRECATED:** blackboard is superseded by GlobalWorkspace + HelixSynapse (per
   docs/design/constellation-enhancements-roadmap.md); this package is migrated as-is for live blackboard
   consumers until the overhaul session's GlobalWorkspace migration supersedes it at P5.`) and keep the source
   header banner in `index.ts` verbatim. Do NOT add runtime deprecation warnings or trim code. **Default: README +
   header note only**, no behavioral change; deletion is phase-gated (see A4a). Confirm the README marker wording
   at P3 execution.

---

# §6. Executor playbook (P3 later wave — verbatim, mirrors P1/P2 §6)

**Part A (flux-team) and Part B (mini-helix) are independent packages; sequence them separately but back-to-back
in one phase.** Each gets its own history-splice import commit + rewrite-delta commit (plan §3c). See plan §4.3
for the exact filter-repo command (this phase runs it twice, once per path set).

1. **Part A — history import.** Temp-clone D: (`git clone --no-checkout --no-local`), then
   `git filter-repo --force --path core/intelligence/flux-team --path-rename core/intelligence/flux-team:packages/flux-team/src --mailmap …`.
   Fetch + splice (add/add, take `--theirs` for conflicted import files), verify `git log --follow`, commit the
   import (one commit). **Do the same for Part B** with `--path core/intelligence/mini-helix --path-rename
   core/intelligence/mini-helix:packages/mini-helix/src` (SECOND import commit, or a second splice if disjoint —
   prefer two separate filter-repo runs → two commits). Part A and B are independent; either order. **NEVER merge
   a stale fragment: re-verify the D: paths have not moved since the temp clone (plan §3d).**
2. **Copy the LIVE files.** Part A: copy the **6 flux-team files** (§A1) into `packages/flux-team/src/` mirroring
   dest (flat, `.ts` extensions, `.js` import specifiers verbatim). Part B: copy the **3 mini-helix files** (§B1)
   into `packages/mini-helix/src/`. **Do NOT copy any DEAD files (0 in both) — flux-team and mini-helix have no
   excluded DEAD files this phase.**
3. **Apply the rewrite pairs per file — a GLOBAL replace per specifier (some occur MULTIPLE times per file, e.g.
   inline `import('../../../types/flux-team.js')` casts in blackboard-tools.ts at 7 sites + 1
   `import('../../../types/blackboard-search.js')` site (line 1639) — 8 inline casts total, ALL → foundation;
   replace EVERY occurrence per file, not first-match).**
   - Part A: 4 foundation pairs → `@cassicore/foundation` (§A2.1) + 1 vendor pair → `./vendor/core/intelligence/
     shared-tools/commit-tool.js` (§A2.2; **use `./vendor/...` — one dot — flat `src/` layout, per the P2 depth fix**).
   - Part B: 2 foundation pairs → `@cassicore/foundation` (§B2.1) + 1 vendor pair → `./vendor/core/model-pool/types.js`
     (§B2.2; **`./vendor/...` one-dot prefix — flat `src/` layout**).
   - Do NOT touch builtins (`crypto`, `node:crypto/fs/path/os`) or internal `./X.js` sibling imports. Leave
     `// REMOVED: …` / commented-out blackboard imports untouched.
4. **Write the vendor stubs.** Part A: `src/vendor/core/intelligence/shared-tools/commit-tool.ts` — **exact-copy
   runtime** port of `commit-tool.ts` (Open Flag 3). Part B: `src/vendor/core/model-pool/types.ts` — faithful
   **type-only** stub for `ModelHandle`, `ModelCompletionOpts` (Open Flag 4). Self-contained (builtin/foundation types only).
5. **Write public barrels.** `packages/flux-team/src/index.ts` = migrated `flux-team/index.ts` verbatim
   (deprecation banner intact). `packages/mini-helix/src/index.ts` = migrated `mini-helix/index.ts` verbatim.
   Preserve ALL export names (helm: `Blackboard`, `GlobalBlackboardRegistry`, `GlobalBlackboardEntry`,
   `handleBlackboardToolCall`, `isBlackboardMetaTool`, `getBlackboardToolSchemas`, `getPlanToolSchemas`,
   `isPlanMetaTool`, `BLACKBOARD_TOOL_NAMES`, `PLAN_META_TOOL_NAMES`, `REPORT_TOOL_NAMES`, `REPORT_TOOLS`,
   `ALL_POSTURES_PLAN_TOOLS`, `EXECUTIVE_PLAN_TOOLS`; mini-helix: the 13 `MiniHelix*` types + `MINI_HELIX_DEFAULTS`
   + `createMiniHelixSession`).
6. **Package scaffold.** Each: `package.json` (`@cassicore/flux-team` / `@cassicore/mini-helix`, `type: module`,
   deps `@cassicore/foundation`; flux-team has NO `better-sqlite3`, mini-helix has NONE of it either — both are
   dependency-light), tsconfig (rootDir src/outDir dist/declaration true), vitest.config.ts, `.gitignore`. flux-team
   README carries the **DEPRECATED** marker (Open Flag 8); mini-helix README is a normal package README.
7. **Re-point the owning consumers (§A3.1 / §B3.1).** After Part A lands: re-point foundation's + helix(P2)'s
   `flux-team/{plan-handler,blackboard,global-blackboard-registry}.ts` vendor stubs → `@cassicore/flux-team`, delete
   the stubs. After Part B lands: re-point helix's `mini-helix/{mini-helix-types,mini-helix-runner}.ts` vendor stubs
   → `@cassicore/mini-helix` and delete (Open Flag 6). **Verify the helix `createMiniHelixSession` stub signature
   matches §B3.1's quoted real signature before wiring.**
8. **Tests.** Port `tests/flux-team/**` (4 files) → `packages/flux-team/tests/`, repoint to `@cassicore/flux-team` +
   `@cassicore/foundation`. Port `tests/mini-helix.test.ts` → `packages/mini-helix/tests/`; its helix
   `brainstem-tools.js` imports go to `tests/host-wired/` quarantine until P2 helix lands (Open Flag 7).
9. `npm run typecheck` (`tsc --noEmit`) in each package; fix ONLY mechanical path errors. Then `npm test` for the
   ported suites (skip project-wide suites, per the worker contract). Do NOT `npm install` beyond noting
   `@cassicore/foundation`.
10. **Commit discipline (plan §3c):** per package, (1) history-splice import commit, (2) rewrite-delta commit
    (this table + vendor + package.json + barrels). Keep import and rewrite in SEPARATE commits. Verify
    `git log --follow` before each rewrite commit. Do NOT commit to D:; the workspace push is handled by the
    session owner (parallel sessions are committing there — leave this file untracked).

---

# §7. Reply summary (for the session owner)

- **Live-set counts:** flux-team **6** migrated (5 LIVE + `index.ts` UNCERTAIN→entry barrel; 0 DEAD);
  mini-helix **3** migrated (2 LIVE + `index.ts` UNCERTAIN→entry barrel; 0 DEAD).
- **Rewrite-pair counts by class:**
  - Part A flux-team: foundation **4** · vendor **1** · internal(unchanged) **0** · builtins **0** = **5 totals.**
  - Part B mini-helix: foundation **2** · vendor **1** · internal(unchanged) **0** · builtins **0** = **3 totals.**
  - Combined P3: foundation **6** (4+2) · vendor **2** (1+1) · internal **0** · builtins **0** = **8 rewrite pairs.**
- **Dest layouts:** see §A3 (flux-team) and §B3 (mini-helix) trees.
- **Open flags (8, defaults recommended):** §5 — (1) index.ts→entry-barrel migrate, (2) registry-vs-import
  reachability, (3) commit-tool runtime vendor, (4) model-pool type-only vendor, (5) foundation search-constants
  barrel check, (6) P2→P3 mini-helix stub replacement, (7) test host-wired split, (8) flux-team deprecation marker.
- **P3-injects-into-P2:** publishing `@cassicore/mini-helix` replaces helix's `mini-helix-runner.ts` /
  `mini-helix-types.ts` vendor stubs (playbook step 7 / Open Flag 6).
