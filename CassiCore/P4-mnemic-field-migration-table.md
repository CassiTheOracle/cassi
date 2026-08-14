# P4 — `@cassicore/mnemic-field` — Migration Table (Planning Deliverable)

**Source (READ-ONLY, D:):** `D:\carina\workspaces\cassicore\core\intelligence\mnemic-field\` (incl. subdirs `training/`, `self-model/`, `knowledge/`)
**Destination:** `C:\Users\Carina\Workspaces\CassiCore\packages\mnemic-field\src\` (MIRRORING the source subdir structure)
**Recon:** `C:\Users\Carina\Workspaces\CassiCore\recon-data.json`
**Plan:** `C:\Users\Carina\Workspaces\CassiCore\CASSI-MIND-PLAN.md` §5-P4, §4, §7 (coordination)
**Exemplars (house format):** `P1-foundation-migration-table.md`, `P2-helix-migration-table.md`, `P3-flux-team-mini-helix-migration-table.md`
**Date:** 2026-08-13
**Status:** PLANNING — executor applies rules verbatim in a later wave. Nothing migrated, nothing committed.

> **Constraint honored:** no file under `D:\carina\workspaces\cassicore` is modified (plan §5 line 27). This
> deliverable is the ONLY file written by this drafting pass; it is NOT git-added/committed (a parallel
> session is committing in the workspace — this file must stay untracked).
>
> **Key differences from P1/P2/P3 (handled explicitly at P4):**
> 1. **No uniform vendor prefix.** Unlike P1/P2/P3 (flat `src/` → one `../vendor/…` or `./vendor/…`), mnemic-field
>    has **subdirectories** (`self-model/`, `training/`, `knowledge/`) whose files sit one level deeper than the
>    top-level `index.ts`/`cortex.ts`/etc. The destination **mirrors those subdirs**, so the vendor/foundation
>    prefix is **per-depth**: top-level files use `./vendor/…`/`../../../types→@cassicore/foundation`; subdir
>    files use `../vendor/…`/`../../../../types→@cassicore/foundation`. Every specifier is computed per FILE (P2
>    lesson (a)).
> 2. **Exhaustive import enumeration.** All 50 migrated files' import blocks were read in full (inline + multiline
>    `from`, `import('…')`, `require()`) — the complete per-file specifier map is in §2 (P2 lesson (b)). Nothing
>    was left to "re-derive at execution".
> 3. **Coordination handshake (plan §7):** the overhaul session is REWIRING Mnemic Field into a journal with
>    `MindFieldEncoder` hooks at store/update/delete/connect/spike/consolidate. **Agreed default (recorded, not
>    acted): OUR package lands FIRST (boundary); they add hooks behind our store port LATER.** §4g proposes the
>    store-port interface the packer should anticipate; we do NOT implement hooks now.
> 4. **P4 injects-into-P2/P0:** publishing `@cassicore/mnemic-field` REPLACES inbound vendor stubs in
>    foundation (P1), helix (P2), AND constellation (pre-existing) — see the **Inbound-repoint table** §3.1.
>    The task brief flagged foundation + helix; **constellation ALSO vendors a large mnemic-field stub tree
>    the brief did not list — 22 constellation files consume it** (found in this sweep; §3.1).

---

## 1. Live-set (files to migrate)

Source tree `core/intelligence/mnemic-field/` contains **57 files in 4 directories** (verified via directory
listing): **42 top-level files** (+ `umap-worker.cjs`, + `field-encoder.test.ts`) and 3 subdirs — `training/` (5),
`self-model/` (6), `knowledge/` (4). Liveness from `recon-data.json` (`deadFiles` / `uncertainFiles`).

- **DEAD — excluded (4):**
  `backfill-runner.ts` (4.23 KB), `feature-backfill.ts` (5.60 KB), `feature-migrate-to-lmdb.ts` (2.99 KB),
  `segmentation.ts` (1 byte — empty file, no content).
- **UNCERTAIN (3):**
  - `archive-engram-mapper.ts` (3.33 KB) + `archive-ingestion-bridge.ts` (9.19 KB) — **quarantine default** (see
    §1.2): a self-contained pair, neither import-reachable by a live file.
  - `knowledge/index.ts` (0.57 KB) — **UNCERTAIN→migrate as the knowledge package-entry barrel** (§1.3).
- **Migrated live-set: 50 files** (all not DEAD; the 2 quarantined-uncertain excluded; `knowledge/index.ts` included).
- **Host-wired test (quarantine):** `field-encoder.test.ts` (§1.4) — the 51st live file, not in the `src/` set.

### 1.1 LIVE files (50)

All 50 below are LIVE: none appear in `deadFiles`; the only two quarantined-uncertain leaves
(`archive-engram-mapper`, `archive-ingestion-bridge`) are separately excluded below. Dest paths MIRROR the source
relative to `src/`.

**Top-level `src/*.ts` (+ `umap-worker.cjs`) — 36 files** (35 `.ts` runtime + `umap-worker.cjs`; `field-encoder.test.ts` is host-wired → §1.4)

| # | source (D:) | dest (packages/mnemic-field/src/) | bytes | notes |
|---|---|---|---|---|
| 1 | `index.ts` | `index.ts` | 175,154 | **MnemicField main class** (§4a) |
| 2 | `types.ts` | `types.ts` | 24,607 | Biggest shared type surface |
| 3 | `cortex.ts` | `cortex.ts` | 76,267 | `Cortex` class, better-sqlite3 |
| 4 | `consolidation.ts` | `consolidation.ts` | 78,385 | `ConsolidationEngine` |
| 5 | `kindling.ts` | `kindling.ts` | 43,817 | `KindlingEngine` |
| 6 | `schema.ts` | `schema.ts` | 22,795 | better-sqlite3 schema |
| 7 | `spatial-index.ts` | `spatial-index.ts` | 9,725 | HEALPix SpatialIndex |
| 8 | `healpix.ts` | `healpix.ts` | 5,530 | self-contained |
| 9 | `spatial-attention.ts` | `spatial-attention.ts` | 5,412 | `SpatialAttentionMapper` |
| 10 | `spatial-tokenizer.ts` | `spatial-tokenizer.ts` | 4,555 | self-contained |
| 11 | `attractor.ts` | `attractor.ts` | 11,584 | `AttractorManager` |
| 12 | `attractor-extractor.ts` | `attractor-extractor.ts` | 12,145 | imports `./index.js` + `./types.js` |
| 13 | `vq-prototypes.ts` | `vq-prototypes.ts` | 7,305 | `VQSectorPrototypes` |
| 14 | `polar-quant.ts` | `polar-quant.ts` | 8,810 | self-contained |
| 15 | `affect.ts` | `affect.ts` | 9,274 | `AffectRegister`, `attune` |
| 16 | `feature-index.ts` | `feature-index.ts` | 15,105 | SQLite FeatureIndex |
| 17 | `feature-index-lmdb.ts` | `feature-index-lmdb.ts` | 30,723 | **`lmdb` npm dep** (§4e) |
| 18 | `engram-decomposer.ts` | `engram-decomposer.ts` | 12,688 | `EngramDecomposer` |
| 19 | `engram-quality-scorer.ts` | `engram-quality-scorer.ts` | 5,603 | `EngramQualityScorer` |
| 20 | `edge-relators.ts` | `edge-relators.ts` | 5,254 | `EDGE_RELATORS_PHRASE_SET` etc. |
| 21 | `backpropagation.ts` | `backpropagation.ts` | 11,323 | `GradientEngine` |
| 22 | `lightning-indexer.ts` | `lightning-indexer.ts` | 9,358 | `LightningIndexer` |
| 23 | `llm-reranker.ts` | `llm-reranker.ts` | 10,374 | `LLMReranker` |
| 24 | `code-store.ts` | `code-store.ts` | 16,139 | `CodeStore`, better-sqlite3 |
| 25 | `code-ingestor.ts` | `code-ingestor.ts` | 9,152 | `CodeIngestor` (execSync w/ explicit cwd) |
| 26 | `gitnexus-bridge.ts` | `gitnexus-bridge.ts` | 7,093 | `GitNexusBridge` (execSync w/ explicit cwd) |
| 27 | `graph-attn-propagator.ts` | `graph-attn-propagator.ts` | 9,971 | **self-contained** (§4b) |
| 28 | `umap.ts` | `umap.ts` | 24,963 | `projectTo2D*` + worker spawn |
| 29 | `**umap-worker.cjs**` | `umap-worker.cjs` | 24,444 | **subprocess entry** (§4c) |
| 30 | `migration-jobs.ts` | `migration-jobs.ts` | 5,831 | `MigrationJobStore` |
| 31 | `migrate-memory.ts` | `migrate-memory.ts` | 28,211 | `migrateChunk`/`migrateMemory*` |
| 32 | `**backfill-worker.ts**` | `backfill-worker.ts` | 4,052 | **subprocess entry** (§4c) |
| 33 | `field-generator.ts` | `field-generator.ts` | 9,180 | |
| 34 | `visual-ingestor.ts` | `visual-ingestor.ts` | 8,708 | |
| 35 | `math-utils.ts` | `math-utils.ts` | 1,296 | self-contained |

> Total top-level migrated: 36 (35 runtime `.ts` + `umap-worker.cjs`). `field-encoder.test.ts` → host-wired quarantine
> (§1.4), not counted in the runtime import set.

**`src/training/*.ts` — 5 files (subdir depth 1)**

| # | source | dest | bytes |
|---|---|---|---|
| 36 | `training/indexer-trainer.ts` | `training/indexer-trainer.ts` | 10,973 |
| 37 | `training/weight-store.ts` | `training/weight-store.ts` | 8,202 |
| 38 | `training/muon.ts` | `training/muon.ts` | 6,155 |
| 39 | `training/newton-schulz.ts` | `training/newton-schulz.ts` | 4,044 |
| 40 | `training/retrieval-loss.ts` | `training/retrieval-loss.ts` | 7,442 |

**`src/self-model/*.ts` — 6 files (subdir depth 1)**

| # | source | dest | bytes |
|---|---|---|---|
| 41 | `self-model/index.ts` | `self-model/index.ts` | 562 |
| 42 | `self-model/self-model-field.ts` | `self-model/self-model-field.ts` | 10,677 |
| 43 | `self-model/inter-field-bridge.ts` | `self-model/inter-field-bridge.ts` | 15,365 |
| 44 | `self-model/ingestor.ts` | `self-model/ingestor.ts` | 28,623 |
| 45 | `self-model/annotation.ts` | `self-model/annotation.ts` | 22,036 |
| 46 | `self-model/types.ts` | `self-model/types.ts` | 3,201 |

**`src/knowledge/*.ts` — 3 files (subdir depth 1)**

| # | source | dest | bytes |
|---|---|---|---|
| 47 | `knowledge/knowledge-field.ts` | `knowledge/knowledge-field.ts` | 12,663 |
| 48 | `knowledge/ingestor.ts` | `knowledge/ingestor.ts` | 7,142 |
| 49 | `knowledge/types.ts` | `knowledge/types.ts` | 6,860 |

**Live-set count: 50 files** (36 top-level + 5 training + 6 self-model + 3 knowledge) migrated into `src/`;
`field-encoder.test.ts` (the 51st live file) ports to `tests/host-wired/` quarantine (§1.4). Total source tree = 57.

### 1.2 UNCERTAIN — QUARANTINE default (do NOT migrate)

| source (D:) | size | recon why | verify note |
|---|---|---|---|
| `archive-engram-mapper.ts` | 3.33 KB | `live-name-ref:2` | Self-contained leaf — imports ONLY `./types.js`. **No external importer** (grep: the only importer is `archive-ingestion-bridge.ts`). Quarantine: not import-reachable by any live file. |
| `archive-ingestion-bridge.ts` | 9.19 KB | `live-name-ref:1` | Imports `../../../types/interfaces.js` + `../unified-loop.js` + `./archive-engram-mapper.js` + `./index.js` + `better-sqlite3`. **No external importer anywhere** (grep of core/ shows only its own header mentions). Though it imports live infra (`unified-loop.ts`, `index.js`), nothing imports IT → dead leaf. Quarantine default. |

> **Default: EXCLUDE both from P4; record in the P0 debt baseline.** Neither is loaded by `index.ts`, `daemon.ts`,
> admin-api, or any live file. `unified-loop.ts` (imported by `archive-ingestion-bridge`) is itself a live sibling
> owned by P5 (or host), NOT migrated in P4 — so even if someone wanted the bridge it can't resolve until P5. Mark
> `[VERIFY]` at execution that the overhaul session has not wired these.

### 1.3 UNCERTAIN — MIGRATE as entry barrel

| source (D:) | size | recon why | verify note |
|---|---|---|---|
| `knowledge/index.ts` | 0.57 KB | `live-name-ref:6` | **Resolve to MIGRATE.** Pure barrel re-exporting the 3 LIVE knowledge siblings (`knowledge-field.js`, `ingestor.js`, `types.js`). The live consumers (`daemon.ts:1756,1771`, `admin-api/memory.ts:2513`) import the FILES (`knowledge/knowledge-field.js`, `knowledge/ingestor.js`), not this barrel — but it is the natural package-entry barrel for the knowledge surface. Mirror flux-team/mini-helix precedent (Open Flag 1): migrate verbatim as `knowledge/index.ts`. |

### 1.4 Test file (host-wired)

- `field-encoder.test.ts` (3.34 KB) — imports `../field-encoder/index.js` + `./index.js` + `vitest`. **Host-wired**
  (depends on the `field-encoder` runtime the overhaul session owns). **Default: port to `tests/host-wired/`
  quarantine** (plan §6), NOT into the package's live import set. See Open Flag 6.

---

## 2. Rewrite table (mechanical string-substitution pairs)

**Mirror rule for vendor stubs.** Every escaping (non-P4-live, non-foundation) target is reproduced as a **type
stub at `src/vendor/<rel-path-from-D-repo-root>.ts`** (Constellation A3 / P1/P2/P3 pattern). Stubs are faithful type
surfaces; the few RUNTIME symbols are handled in §4b/§4c.

**Foundation rule (P4-specific).** Every import resolving to the P1 shared substrate (`types/*`, `utils/paths`,
`phrase-prototypes`) → **`@cassicore/foundation`** (named import; executor verifies each symbol in the landed
foundation barrel — §4a symbol map, `[VERIFY]`).

**Extension rule.** Source keeps `.js` import specifiers verbatim; only the specifier is rewritten. For
`@cassicore/foundation` the `.js` extension is dropped (package specifier).

**Depth rule (P2 lesson (a) — CRITICAL).** The dest mirrors subdirs, so the vendor/foundation PREFIX is **per
depth**, NOT uniform:

| dest file location | foundation source prefix | foundation dest | vendor source prefix | vendor dest prefix |
|---|---|---|---|---|
| `src/*.ts` (top level) | `../../../types/…`, `../../utils/paths.js`, `../phrase-prototypes.js` | `@cassicore/foundation` | `../intelligence/…`, `../../utils/…` | `./vendor/…` |
| `src/{self-model,training,knowledge}/*.ts` (depth 1) | `../../../../types/…`, `../../../utils/paths.js` | `@cassicore/foundation` | `../../intelligence/…`/`../../aurora/…` etc. | `../vendor/…` |

Every specifier is computed from the file's own dest dir — **no bulk prefix assumption** (the P2/P3 flat-layout
`../vendor/`/`./vendor/` shortcut does NOT apply; see the P3 depth-fix note in reverse).

**Scope rule.**
- **DO NOT touch** Node builtins (`node:fs/path/crypto/url/module/worker_threads/child_process`,
  bare `worker_threads` in `umap-worker.cjs`), npm packages (`better-sqlite3`, `lmdb`, `vitest`), and **internal
  imports that remain valid after relocation** (the mirrored subdirs keep every `./X.js` sibling AND every
  `../X.js` intra-module import unchanged — see §2.3).
- **REWRITE** (a) every foundation import → `@cassicore/foundation`, (b) every import resolving OUTSIDE the P4
  live-set + outside foundation → `./vendor/…` or `../vendor/…` stub (per depth).
- Apply only to actual `import`/`import type`/re-export/inline `import('…')`/`require()` statements — NOT to
  string/comment content that resembles imports.
- Inline `import('…')`/`import()` type expressions on listed targets are rewritten identically (several `index.ts`
  trailing methods use inline `import('./types.js').X` / `import('./umap.js').UMAPOptions` — these are INTERNAL and
  unchanged).

### 2.1 Foundation rewrite pairs (→ `@cassicore/foundation`)

4 unique module targets; **12 files touch interfaces (2 depth forms), 3 touch paths (2 depth forms), 2 runtime,
1 phrase-prototypes.**

| original specifier(s) | dest | consumed by (files) |
|---|---|---|
| `../../../types/interfaces.js` (depth 0) **and** `../../../../types/interfaces.js` (depth 1) | `@cassicore/foundation` (`ILogger`, `IProvider`, `IEventBus`, …) | depth-0 (16): backpropagation, code-ingestor, code-store, consolidation, cortex, engram-decomposer, engram-quality-scorer, feature-index, feature-index-lmdb, gitnexus-bridge, index, kindling, lightning-indexer, llm-reranker, migrate-memory, spatial-attention.<br>depth-1 (6): knowledge/ingestor, knowledge/knowledge-field, self-model/ingestor, self-model/inter-field-bridge, self-model/self-model-field, training/indexer-trainer |
| `../../../types/runtime.js` (depth 0) | `@cassicore/foundation` (`IProvider`, `CompletionOpts`) | index, llm-reranker |
| `../../utils/paths.js` (depth 0) **and** `../../../utils/paths.js` (depth 1) | `@cassicore/foundation` (`getDataDir`) | depth-0: index.<br>depth-1: knowledge/knowledge-field, self-model/self-model-field |
| `../phrase-prototypes.js` (depth 0) | `@cassicore/foundation` (`SIGNAL_TYPE_PHRASES`, `EPISTEMIC_SHIFT_PHRASES`, `WORK_UNIT_ANNOTATION_PHRASES`) | index |

> **Symbol map — `[VERIFY]` against the landed foundation barrel before rewiring.** P1 ships all 19 live types +
> `ports/paths getDataDir` + `phrase-prototypes`. `getDataDir` must be re-exported at foundation package top level
> (the P1/§5-P1 ports seam). **Interfaces:** every symbol mnemic-field imports from `interfaces.js` (its whole
> `ILogger`/`IProvider`/`IEventBus` typing) lives in the migrated P1 `types/interfaces.ts`, so the splice carries
> it verbatim — but confirm the foundation `index.ts` barrel re-exports the FULL `interfaces.ts` surface (P1 §4a
> requires this; it does). If any symbol is absent, add it to the foundation barrel (foundation is published) before
> P4 typecheck.

### 2.2 Vendor stub rewrite pairs (→ `./vendor/…` depth 0 / `../vendor/…` depth 1)

Every escaping non-foundation target. **11 unique resolved targets** (per target, with per-depth specifier forms).

| original specifier(s) | dest stub (src/vendor/…) | depth | consumed by (symbols) |
|---|---|---|---|
| `../../utils/math.js` | `./vendor/core/utils/math.js` | 0 | affect (`cosineSimilarity`-family math fns — RUNTIME; see §4b) |
| `../memory-bridge/dream-engine.js` | `./vendor/core/intelligence/memory-bridge/dream-engine.js` | 0 | consolidation, index (`DreamEngine` — type) |
| `../reverie/retrieval-labeler-types.js` (depth 0) **and** `../../reverie/retrieval-labeler-types.js` (depth 1) | `./vendor/core/intelligence/reverie/retrieval-labeler-types.js` / `../vendor/…` | 0+1 | cortex (`RetrievalLabelTriple`?), index (`RetrievalLabelTriple`, `LabelerInputCandidate`), training/indexer-trainer (`RetrievalLabelTriple`) — type |
| `../aurora/larql-provider.js` | `./vendor/core/intelligence/aurora/larql-provider.js` | 0 | engram-decomposer (larql provider integration — type) |
| `../../aurora/types.js` | `../vendor/core/intelligence/aurora/types.js` | 1 | knowledge/knowledge-field (aurora type) |
| `../cortex/index.js` | `./vendor/core/intelligence/cortex/index.js` | 0 | index (`CorticalField` — type) |
| `../embeddings/embedding-service.js` (depth 0) **and** `../../embeddings/embedding-service.js` (depth 1) | `./vendor/core/intelligence/embeddings/embedding-service.js` / `../vendor/…` | 0+1 | index, self-model/self-model-field (`getEmbeddingService` — RUNTIME) |
| `../embeddings/reranker-service.js` | `./vendor/core/intelligence/embeddings/reranker-service.js` | 0 | index (`getRerankerService` — RUNTIME) |
| `../embeddings/types.js` | `./vendor/core/intelligence/embeddings/types.js` | 0 | types (`RerankerMode`, … — type) |
| `../field-encoder/types.js` | `./vendor/core/intelligence/field-encoder/types.js` | 0 | index (`MindFieldEncoder` — type; **the overhaul handshake seam**, §4g) |
| `../field-encoder/index.js` | `./vendor/core/intelligence/field-encoder/index.js` | 0 | field-encoder.test.ts (`MindFieldEncoder` impl — test only) |

> **Runtime-not-type vendored symbols (the three that must be faithful impls or confirmed-safe stubs, P2 Open
> Flag-5 pattern):** `getEmbeddingService` (embedding-service.js), `getRerankerService` (reranker-service.js),
> `_utils/math` helpers (math.js). `DreamEngine`, `CorticalField`, `RerankerMode`, `RetrievalLabelTriple`,
> `MindFieldEncoder`, aurora/embeddings types are type-only → clean type stubs. For the runtime ones, the stub must
> either re-export a self-contained faithful implementation OR a `throw` that is never exercised on the P4-tested
> code paths (see §4b; the overhaul session's `field-encoder`/`embeddings` packages will eventually replace these
> stubs). **Default: faithful type stubs for the type-only; for the three runtime symbols port exact pure copies if
> the local behavior is self-contained, else confirm-safe throw stub.** Mark `[VERIFY]` at execution.

### 2.3 Internal (unchanged) + builtins/npm

- **Internal (stay valid under the MIRROR layout — 0 rewrite pairs):** every `./X.js` between same-dir siblings AND
  every `../X.js` from a subdir back to the module root/top-level, e.g. `self-model/index.ts → ./ingestor.js`+
  `./inter-field-bridge.js`+`./self-model-field.js`+`./types.js`, `training/indexer-trainer.ts → ../cortex.js`+
  `../lightning-indexer.js`+`../types.js`+`./muon.js`+`./retrieval-loss.js`+`./weight-store.js`,
  `knowledge/knowledge-field.ts → ../index.js`+`../types.js`+`./types.js`, index.ts → the 25 top-level `./X.js`
  siblings and `./self-model/index.js`+`./training/indexer-trainer.js`. Because the destination MIRRORS the source
  subdir layout, **every intra-module import is preserved unchanged** (a key advantage of mirroring over flattening).
- **Builtins/npm (unchanged): `node:fs`, `node:path`, `node:crypto`, `node:url`, `node:worker_threads`,
  `node:module`, `node:child_process`, bare `worker_threads` (umap-worker.cjs), `better-sqlite3` (index, cortex,
  code-store, feature-index, migrate-memory, migration-jobs, schema, knowledge? — see §4e), `lmdb`
  (feature-index-lmdb; §4e), `vitest` (field-encoder.test.ts).**

### 2.4 Rewrite-pair tally by class (per-depth prefixes)

| class | unique module targets | by depth prefix | files touched |
|---|---|---|---|
| **Foundation → `@cassicore/foundation`** | **4** | `interfaces.js`: 2 forms (`../../../types/`×16 depth-0, `../../../../types/`×6 depth-1); `paths.js`: 2 forms (`../../utils/`×1 depth-0, `../../../utils/`×2 depth-1); `runtime.js`×2, `phrase-prototypes.js`×1 (single-form each) | 12 files carry ≥1 foundation escape |
| **Vendor type/runtime stub → `./vendor/…`/`../vendor/…`** | **11** | depth-0 (`./vendor/…`): math.js, dream-engine.js, reverie/retrieval-labeler-types.js, aurora/larql-provider.js, cortex/index.js, embeddings/embedding-service.js, embeddings/reranker-service.js, embeddings/types.js, field-encoder/types.js, field-encoder/index.js — 10 specifier strings; depth-1 (`../vendor/…`): aurora/types.js, embeddings/embedding-service.js, reverie/retrieval-labeler-types.js — 3 specifier strings (2 targets shared with depth-0) | 12 files |
| **Internal (unchanged `./X.js` / `../X.js` in-module)** | **0 rewrite pairs** (all preserved by mirror) | — | ~40 files have internal imports (unchanged) |
| **Builtins/npm (unchanged)** | **0 rewrite pairs** | — | most files |
| **TOTAL rewrite pairs** | **15 unique targets** (4 foundation + 11 vendor) | 13 depth-0 + 3 depth-1 vendor-specific-target files | 24 files carry ≥1 rewrite |

- **Foundation:** 4 pairs (interfaces, runtime, paths, phrase-prototypes). **Vendor:** 11 pairs. **Internal: 0.**
  **Builtins/npm: 0.** **Total: 15 rewrite pairs** (global per-specifier replacement per file; the interactions of
  `interfaces.js`/`paths.js`/`embedding-service.js`/`reverie/retrieval-labeler-types.js` across BOTH depths means the
  executor must apply the depth-correct form per file — never a single sed across the tree).

> **Subdir depth map:** `src/` (depth 0) = 36 top-level files; `src/training/` (depth 1) = 5; `src/self-model/`
> (depth 1) = 6; `src/knowledge/` (depth 1) = 3; `src/vendor/` mirrors the D: repo-root rel-path under
> `core/{utils,intelligence/…}`. Total 4 destination directories.

---

## 3. Destination layout proposal (mirror)

```
packages/mnemic-field/
  package.json                     # name: "@cassicore/mnemic-field", type: module,
                                   #   deps: @cassicore/foundation, better-sqlite3, lmdb  (§4e)
  tsconfig.json                    # rootDir src/ outDir dist/ declaration true
  vitest.config.ts                 # ported mnemic-field tests (tests/host-wired/ for encoder test)
  src/
    index.ts                       # MnemicField class + re-export barrel (§4a)
    types.ts  cortex.ts  consolidation.ts  kindling.ts  schema.ts
    spatial-index.ts  healpix.ts  spatial-attention.ts  spatial-tokenizer.ts
    attractor.ts  attractor-extractor.ts  vq-prototypes.ts  polar-quant.ts  affect.ts
    feature-index.ts  feature-index-lmdb.ts  engram-decomposer.ts  engram-quality-scorer.ts
    edge-relators.ts  backpropagation.ts  lightning-indexer.ts  llm-reranker.ts
    code-store.ts  code-ingestor.ts  gitnexus-bridge.ts  graph-attn-propagator.ts
    umap.ts  umap-worker.cjs         # (+ worker; co-located so import.meta.url resolves it)
    migration-jobs.ts  migrate-memory.ts  backfill-worker.ts   # subprocess entry (§4c)
    field-generator.ts  visual-ingestor.ts  math-utils.ts
    training/                        # depth 1 (mirror)
      indexer-trainer.ts  weight-store.ts  muon.ts  newton-schulz.ts  retrieval-loss.ts
    self-model/                      # depth 1 (mirror)
      index.ts  self-model-field.ts  inter-field-bridge.ts  ingestor.ts
      annotation.ts  types.ts
    knowledge/                       # depth 1 (mirror)
      index.ts  knowledge-field.ts  ingestor.ts  types.ts
    vendor/                          # stubs ONLY — mirror original D: rel-paths (§2.2)
      core/
        utils/math.ts
        intelligence/
          memory-bridge/dream-engine.ts
          reverie/retrieval-labeler-types.ts
          aurora/  { types.ts, larql-provider.ts }
          cortex/index.ts
          embeddings/  { embedding-service.ts, reranker-service.ts, types.ts }
          field-encoder/  { types.ts, index.ts }
  tests/
    host-wired/                      # field-encoder.test.ts quarantine (plan §6)
```

**Internal-import consequences (all satisfied by the MIRROR):** both `./X.js` siblings and `../X.js` subdir→root
imports are preserved unchanged because the subdir structure is copied exactly. Foundation imports →
`@cassicore/foundation` (any depth). Vendor stubs: one `./vendor/…` (top-level) or `../vendor/…` (subdir) hop.

### 3.1 Inbound-repoint log (vendor stubs IN OTHER PACKAGES → this package)

Publishing `@cassicore/mnemic-field` REPLACES every mnemic-field vendor stub already committed in the workspace
packages, re-pointing consumer imports to `@cassicore/mnemic-field` and deleting the stub files. **This is a P4
executor task** (mirrors P3-injects-into-P2). The sweep found mnemic-field stubs in **THREE** packages:

| consumer package | stub path(s) (`src/vendor/…`) | exported symbols consumed | re-point to |
|---|---|---|---|
| **foundation** (P1) | `core/intelligence/mnemic-field/edge-relators.ts` | `PhrasePrototypeSet` (phrase-prototypes) | `@cassicore/mnemic-field` |
| **helix** (P2) | `core/intelligence/mnemic-field/index.ts` | `MnemicField` (type) — brainstem, helix-conductor, helix-mnemic-bridge, helix-pipeline | `@cassicore/mnemic-field` |
| **helix** (P2) | `core/intelligence/mnemic-field/types.ts` | `EngramType`, `SynapseType` — helix-mnemic-bridge | `@cassicore/mnemic-field` |
| **constellation** (pre-existing) | `mnemic-field/index.ts` | `MnemicField` (type) — **22 files** (see list) | `@cassicore/mnemic-field` |
| **constellation** | `mnemic-field/types.ts` | `EngramType`, `SynapseType`, `Engram`, `EngramCreate`, `MnemicSynapse`, `EngramSearchResult`, `FieldStats`, etc. | `@cassicore/mnemic-field` |
| **constellation** | `mnemic-field/cortex.ts` | `Cortex`, `OrphanDistribution`, `OrphanSample` (+types re-export) | `@cassicore/mnemic-field` |
| **constellation** | `mnemic-field/graph-attn-propagator.ts` | `GraphAttnPropagator` (**runtime class**), `PropagatedEngram`, `PropagationPath`, `PropagationHop`, `GraphAttnPropagatorOpts` | `@cassicore/mnemic-field` |
| **constellation** | `mnemic-field/edge-relators.ts` | `PhrasePrototypeSet` | `@cassicore/mnemic-field` |
| **constellation** | `mnemic-field/self-model/self-model-field.ts` | `SelfModelField` (type), `StoreOptions`, `PatternMetadata`, `WeaknessMetadata` | `@cassicore/mnemic-field` |
| **constellation** | `mnemic-field/self-model/inter-field-bridge.ts` | `InterFieldBridge` (type), `PortalStatsEntry` | `@cassicore/mnemic-field` |

> **Constellation consumer files (22) that import `vendor/mnemic-field/…` — all re-point to `@cassicore/mnemic-field`:**
> consolidation/outcome-consolidator.ts, constellation-orchestrator.ts, constellation-pipeline.ts, corpus/corpus-patterns.ts,
> corpus-tools.ts, corpus-types.ts, cross-helix-dialectic.ts, decomposition-tracker.ts, graph-coordinator.ts,
> locus/graph-attention-bridge.ts, locus/mnemic-locus-memory-persistence.ts, meditation/corpus-synthesis.ts,
> meditation/field-health.ts, meditation/focused-seeding.ts, meditation/index.ts, meditation/meditation-feedback.ts,
> meditation/mnemic-bridge.ts, meditation/organizing-synthesis.ts, meditation/self-modeling-synthesis.ts,
> meditation/styles.ts, memory-injection.ts, territory-bridge.ts.
>
> **`GraphAttnPropagator` is consumed as a RUNTIME class** by constellation-pipeline.ts, graph-coordinator.ts,
> locus/graph-attention-bridge.ts — the real `@cassicore/mnemic-field` exports it (index.ts `export { GraphAttnPropagator }`,
> verified §4a). The constellation stub (with `class GraphAttnPropagator` methods) must be REPLACED BY THE REAL
> class, not left as a throw stub.
>
> **`dist/` artifacts:** the compiled `dist/vendor/…` copies (foundation/helix/constellation) regenerate on the next
> build from the re-pointed `src/`; do NOT hand-edit dist.

### 3.2 P4-imports-already-published-packages check

The task brief asked: any mnemic-field import of an already-published package (helix/constellation/flux-team/
mini-helix) → real package import if exported, else vendor stub. **Finding: mnemic-field imports NONE of the
already-published packages** — every external import escapes to foundation (→ `@cassicore/foundation`) or to
sibling intelligence dirs (memory-bridge, embeddings, field-encoder, cortex, reverie, aurora) that are P5- or
overhaul-owned. So NO already-published-package wiring is needed in P4 beyond the inbound re-point (§3.1). The
sibling-dir targets become vendor stubs, re-pointed to their owning P5 packages via the owning-phase repoint log
(§6). Mark `[VERIFY]` at execution that the overhaul session hasn't added an import of a published package.

---

## 4. Known-hard items

### 4a. `index.ts` — the MnemicField main class (the conductor/helix/constellation surface)

`src/index.ts` (175,154 B — the largest P4 file) both DEFINES `MnemicField` and acts as the public barrel. Its
**module-level exports** (what the host/conductor/helix/constellation type against — DO NOT RENAME, plan §3c):

- `export class MnemicField` — the main class.
- Barrel re-exports: `Cortex`, `KindlingEngine`, `ConsolidationEngine`, `GradientEngine`, `CodeStore`,
  `CodeIngestor`, `GitNexusBridge`, `SelfModelField`, `InterFieldBridge`, `SelfModelIngestor`, `GraphAttnPropagator`,
  `SpatialAttentionMapper`, `VQSectorPrototypes`, `cosineSimilarity`, `cosineDistance`, `EngramDecomposer`,
  `contentDensity`, `scoreSentencesByOverlap`, `featuresToKeySet`, `LightningIndexer`, `IndexerTrainer`, `attune`,
  `AffectRegister`, `resolveLabel`, `affectSimilarity`, `emotionalIntensity`, `classifyWithPhrases`,
  `EDGE_RELATORS_PHRASE_SET`, `projectTo2D`, `projectTo2DAsync`, `projectTo2DFromSAB`, `projectSingle`,
  `buildProjectionState`, and `export function slerpEmbedding` (module tail).
- Re-exported types: `VindexEmbedder`, `PropagatedEngram`/`PropagationPath`/`PropagationHop`/
  `GraphAttnPropagatorOpts`, `SectorAttentionResult`, `SpatialPosition`/`SpatialPositionWithToken`, `SentenceFeature`/
  `DensityMetrics`/`DecomposedContent`, `AssignResult`, `IngestOptions`/`IngestResult`, `ConsolidationResult`/
  `ConsolidationOptions`, `ProjectionResult`/`ProjectionState`/`UMAPOptions`/`UMAPProgressEvent`,
  `PhrasePrototypeSet`/`ClassificationResult`.

**The `MnemicField` public method surface** (what the conductor / helix / constellation / orchestration call —
preserve exact signatures, do not rename):

- **Wiring/setters:** `setRerankerProvider(provider, model?, enabled?)`, `setRerankerMode(mode)`,
  `setVindexEmbedder(embedder, source?)`, `setDecomposer(decomposer)`, `setForwardProvider(provider)`,
  `setFieldEncoder(encoder: MindFieldEncoder | null)` ← **overhaul seam**, `fieldDepositsSent()`,
  `drainFieldDeposits(): number[][]`, `setRetrievalPositionsEnabled(enabled)`, `drainRetrievalPositions()`,
  `setEmbeddingBackend(backend: 'vllm'|'vindex')`, `setForeshadow(fs)`, `setLightningMode(mode, trainConfig?)`,
  `setLightningShadowMode(enabled)`, `setCorticalField(cortex: CorticalField)`, `setDreamEngine(engine)`,
  `setLlmProvider(provider)`.
- **CRUD (the STORE seams — §4g):** `store(input: EngramCreate): Engram`, `get(id)`, `searchByProvenance`,
  `findFileByPath`, `findFileVersionsByPath`, `pruneFileReads`, `update(id, update)`, `delete(id)`, `list`,
  `connect(input: SynapseCreate): MnemicSynapse`, `disconnect`, `getEngramsByIdPrefix`, `getEngramsBySessionId`,
  `getTypedSynapses`, `bulkUpdateSynapseWeights`.
- **Replay:** `getReplayChildren`, `getReplayTimeline`, `getReplaySubgraph`, `replaySession`, `replayRun`,
  `getSessionSummary`.
- **Field/neural:** `neighbors`, `spike(input: SpikeCreate): ActivationSpike`, `spikes`, `spikeCount`,
  `createNucleus`, `nuclei`, `listNuclei`, `getNucleus`, `querySpatial`, `getPositions`, `searchText`, `tensions`,
  `tensionReport`, `computeSpikeImportance`, `computeAlpha`, `effectiveSparkPoint`, `stats`, `retrieve`,
  `retrieveByRegion`, `retrieveWithPatch`, `computeSectorDensity`, `computeHarmony`, `getHarmony`,
  `buildShadowContext`, `getBroadcastSparkModulation`, `getPrimedNuclei`, `getFractalDimension`.
- **Maintenance/migration:** `createMigrationJob`, `getMigrationJob`, `listMigrationJobs`, `updateMigrationJob`,
  `runMigrationJob` (→ `migrate-memory`), `_restoreProjectionState`, `rebuildProjection`, `reprojectAll`,
  `reprojectAllAsync`, `backfillEmbeddings`, `backfillAllEmbeddings`, `classifyAll`, `generateTypeSynapses`,
  `thalamusBackfill`, `close()`, `storeForSession`, `findExpertEngrams`, `getTrace`, `reinforceExpert`,
  `evolveExpert`, `checkExpertLifecycle`, `recordExpertOutcome`, `adjustPropagationWeights`,
  `classifyEdgePair`, `classifyPhrase`, `ensurePhraseEmbeddingsForSet`, `kindle`, `recordActivation`,
  `enableNeuralKindling`, `disableNeuralKindling`, `isNeuralKindlingEnabled`, `detectHubs`, `getHubs`,
  `recordEnrichFeedback`, `recordIndexerTrainingRequests`, `getForwardTraceCount`, `getPendingGradientCount`,
  `getOptimizerStateCount`, `getBackpropConfig`, `setBackpropConfig`, `pruneOldTraces`,
  `updateActiveAttentionEmbeddings`, `consolidate`, `consolidatePromotionCandidates`, `getFilaments`
  (`getConsolidationEngine`? no — `getCortex()`, `getConsolidationEngine()`, `getAffect()`, `getAffectRegister()`,
  `absorbAffectSignal`), `renderContext`, `buildDelegationContext`, `embedFilaments`, `backfillFilaments`,
  `getChains`, `getCrystallization`, `getExpertiseMetrics`, `getStaleDependents`, `getQueryFeatures`,
  `getFilamentCortex`, `trainLightningIndexer`, `getLightningStatus`, `queryLightningRetrievalEvents`,
  `getEngramDataForLabeling`, `getHubs` (duplicate?), `ingestSpatialPosition`, `ingestSpatialGrid`,
  `backfillEmbeddingsParallel`.

**Constructor seam (store/isolation):** `constructor(logger: ILogger, dbOrPath?: Database.Database | string)`.
When `dbOrPath` is a string/undefined, defaults to `path.join(getDataDir(), 'mnemic-field.db')` (foundation
`getDataDir`), derives the LMDB path `feature-index.lmdb` SAME-DIR relative to the SQLite file, tries
`LmdbFeatureIndex` (LMDB), falls back to SQLite `FeatureIndex`, and wires the HEALPix `SpatialIndex` to the LMDB env.
**No CWD/root-relative paths in the constructor** — the whole store cluster is self-consistent relative to
`getDataDir()`. This is the seam §4g's store-port should expose.

### 4b. `graph-attn-propagator.ts` — SELF-CONTAINED inside mnemic-field

Verified (full import block): it imports ONLY `./cortex.js` (type-only `Cortex`) + `./types.js` (type-only `Engram`,
`MnemicSynapse`, `SynapseType` + runtime const `SYNAPSE_PROPAGATION` — all mnemic-field-local). **It makes NO
external/sibling-dir imports.** Under the mirror, `./cortex.js`/`./types.js` stay valid → **zero rewrite pairs for
this file**. Its export surface (types + `GraphAttnPropagator` class) is what constellation consumes as a runtime
(§3.1).

### 4c. Subprocess / worker entries — path isolation

Two standalone process/worker entries exist. Verified path assumptions:

1. **`umap-worker.cjs` (24.4 KB, PLAIN CJS)** — **fully self-contained**: requires ONLY `worker_threads`
   (`parentPort`/`workerData`); the entire UMAP pipeline (NN-Descent → fuzzy set → PCA init → SGD layout) is inline.
   It is spawned from `umap.ts` via `new Worker(new URL(join(dirname(fileURLToPath(import.meta.url)), 'umap-worker.cjs'), import.meta.url))`
   (lines 138–143) — the worker path resolves **relative to `umap.ts`'s own location** via `import.meta.url`.
   Under the mirror, `umap.ts` and `umap-worker.cjs` stay CO-LOCATED in `src/` (→ compiled `dist/`), so this stays
   valid **unchanged — no CWD dependence**. **Recommendation: ship `umap-worker.cjs` as a package-runtime asset at
   `src/umap-worker.cjs`/`dist/umap-worker.cjs` co-located with `umap.js` (NOT a `bin/`), spawned via the existing
   `import.meta.url` worker constructor.** No package.json `bin/` entry needed — it is not a CLI, it is a worker
   thread.
2. **`backfill-worker.ts` (4.0 KB, TS worker)** — spawned from `index.ts` `BackfillWorkerPool` at
   **`new Worker('core/intelligence/mnemic-field/backfill-worker.ts', …)`** (line 4437) — **a D:-ROOT-RELATIVE
   STRING**. It also resolves the native addon via `process.env.CASSICORE_ROOT || process.cwd()` +
   `node_modules/cassi-larql` (lines 16–19) — **CWD/ROOT-dependent**. **This is the hard one:**
   - Worker path → must become package-relative: `new Worker(new URL('./backfill-worker.ts', import.meta.url))`.
   - `cassi-larql` native addon → the `packages/larql` Rust crate builds `crates/larql-napi/index.node`; the live
     consumer expects it at `node_modules/cassi-larql/index.node`. See §4e/Open Flag 4 for the native-dep caveat.
   - **Recommendation:** run backfill-worker as a `bin/` entry OR (better) keep it a package-relative worker AND make
     `cassi-larql` a documented peer dep the host provides (the plan does NOT migrate larql — §4.6/Open Flag 4).
   - `backfill-runner.ts` (the standalone JS-launcher process) is DEAD/excluded — so the only live spawn path is the
     index.ts `BackfillWorkerPool`, which we re-point in-package.

> **No `fork()`/CLI subprocesses besides the two workers** — `code-ingestor.ts`/`gitnexus-bridge.ts` use `execSync`
> with EXPLICIT `cwd` options (no CWD assumption; they take `rootDir`/`repoRoot` as constructor/options params), so
> they need no path rewrite. Verified.

### 4d. LMDB native dep (which files import `lmdb`)

- **`feature-index-lmdb.ts` (LIVE) imports `lmdb` (`open as lmdbOpen`)** — the only LIVE file; it is the LMDB-backed
  `LmdbFeatureIndex`. `feature-migrate-to-lmdb.ts` (DEAD) also imported it — excluded.
- `feature-index.ts` (LIVE) imports `./feature-index-lmdb.js` (internal) + `better-sqlite3` — so the SQLite feature
  index and the LMDB one are intertwined; feature-index-lmdb is load-bearing (index.ts tries it first, falls back to
  SQLite).
- **`lmdb` is a RUNTIME npm dependency of `@cassicore/mnemic-field`** (native mmap-backed store). Add `lmdb` to the
  package.json deps. **Native-dep caveat:** `lmdb` ships prebuilt binaries (napi-rs) — on non-standard platforms it
  needs a build toolchain. The workspace root package.json does NOT currently declare `lmdb`; it lives in the D:
  root package.json (`"lmdb": "^3.5.4"`). Add it as a P4 package dep. See Open Flag 4.

### 4e. Stored-persistence seams (SQLite + LMDB) — the coordination store-port

Writes go through:
- **SQLite (`better-sqlite3`):** the `MnemicField` DB (`mnemic-field.db`, WAL, at `getDataDir()`); `Cortex`,
  `CodeStore`, `FeatureIndex` (SQLite variant), `MigrationJobStore`, `schema.ts` each open `better-sqlite3`.
- **LMDB:** `LmdbFeatureIndex` (`feature-index.lmdb` alongside the SQLite file) + the HEALPix `SpatialIndex` wired to
  the same LMDB env.

`better-sqlite3`+`lmdb` are both P4 npm deps (workspace root lacks `lmdb`; `better-sqlite3` is a workspace dep — the
P1 decision added it to foundation; P4 declares it again for its own stores). The core/daemon wiring that mounts
mnemic-field is P7 host territory, not P4.

### 4f. Largest files and dominant imports

- **`index.ts` (175.2 KB):** 55 import specifiers — 25 internal `./X.js` + `./self-model/index.js` +
  `./training/indexer-trainer.js`, foundation (interfaces, runtime, paths, phrase-prototypes), vendor
  (dream-engine, embedding-service, reranker-service, cortex/index, field-encoder/types, reverie/retrieval-labeler-types),
  builtins (`node:fs/path/crypto/url/worker_threads`), npm (`better-sqlite3`). The single biggest rewrite center
  (4 foundation + 6 vendor escapes).
- **`consolidation.ts` (78.4 KB):** foundation `interfaces` + internal (`affect`, `backpropagation`, `cortex`,
  `engram-decomposer`, `engram-quality-scorer`, `feature-index-lmdb`, `types`) + vendor `dream-engine`. **No
  builtins/npm.**
- **`cortex.ts` (76.3 KB):** foundation `interfaces` + internal (`polar-quant`, `schema`, `types`) + vendor
  `reverie/retrieval-labeler-types` + `better-sqlite3` + `node:crypto`.
- **`kindling.ts` (43.8 KB):** foundation `interfaces` + internal (`affect`, `attractor`, `cortex`,
  `spatial-attention`, `spatial-index`, `types`). No vendor.
- **`feature-index-lmdb.ts` (30.7 KB):** foundation `interfaces` + internal (`cortex`, `feature-index`, `healpix`) +
  `lmdb`.
- **`migrate-memory.ts` / `migration-jobs.ts` / `backfill-worker.ts`:** `migrate-memory.ts` imports `./index.js`
  (internal cycle — index↔migrate-memory) + `better-sqlite3` + foundation + `./types.js`; `migration-jobs.ts`
  imports `./migrate-memory.js` + `better-sqlite3` + `node:crypto`.

Highest-frequency rewrite: `../../../types/interfaces.js` (16 files, depth 0) + `../../../../types/interfaces.js`
(6 files, depth 1) = **22 files** → `@cassicore/foundation` — the single most common pair.

### 4g. Coordination note — proposed store-port interface (anticipate, do NOT implement hooks)

**Recorded, not acted on** (plan §7): the overhaul session plans to make Mnemic Field's SQLite/LMDB a **journal**
with `MindFieldEncoder`-style hooks at `store`/`update`/`delete`/`connect`/`spike`/`consolidate`. **Agreed default:
OUR package lands FIRST (boundary), they add hooks behind our port LATER.** To make the future handshake
non-invasive, the P4 package should expose a minimal **store-port** the packer can slot hooks behind without
touching `MnemicField` internals:

```ts
// src/ports/store.ts  (P4 — propose only; NO hook implementation)
export interface MnemicFieldStore {
  store(input: EngramCreate): Engram
  get(id: string): Engram | null
  update(id: string, update: EngramUpdate): Engram | null
  delete(id: string): boolean
  connect(input: SynapseCreate): MnemicSynapse
  disconnect(sourceId: string, targetId: string, edgeType: string): boolean
  spike(input: SpikeCreate): ActivationSpike
  consolidate(options?: ConsolidationOptions): Promise<ConsolidationResult>
  // + a transactional write observer seam (future MindFieldEncoder hook target):
  onWrite?: (op: 'store'|'update'|'delete'|'connect'|'disconnect'|'spike', record: unknown) => void
}
// Default impl = the current MnemicField DB-backed store (SQLite + LMDB behind it).
// The overhaul session later binds a MindFieldEncoder journal observer through onWrite —
// P4 ships the interface + default; the hooks are THEIR follow-up.
```

The `MindFieldEncoder` type (from `../field-encoder/types.js`) is the concrete encoder contract the overhaul owns;
P4 vendors its type stub (`src/vendor/core/intelligence/field-encoder/types.ts`) so `setFieldEncoder` compiles, and
the store-port makes the journal seam explicit. **Do NOT wire `onWrite` to anything in P4** — it is a forward-looking
port surface only (flagging it so the executor leaves the seam unoccupied for the overhaul session).

---

## 5. Open flags (max 8 — defaults recommended)

1. **`knowledge/index.ts` UNCERTAIN → migrate as entry barrel.** It is not import-reachable by a live file as a
   barrel (daemon/admin-api import `knowledge/knowledge-field.js`/`ingestor.js` directly), but it re-exports ONLY
   live siblings. **Default: migrate verbatim as `src/knowledge/index.ts`** (mirrors flux-team/mini-helix index).
   If the strict quarantine reading is preferred, hand-write the identical 21-line barrel (pure re-export; no
   fabrication). Mark `[VERIFY]` at execution no live consumer imports it via a path we missed.
2. **`archive-engram-mapper.ts` + `archive-ingestion-bridge.ts` (UNCERTAIN pair) → quarantine/exclude.** Neither is
   import-reachable by a live file (they only import each other + live infra). **Default: exclude both from P4,
   record in the P0 debt baseline.** `[VERIFY]` at execution that the overhaul session has not wired them into a
   live path since recon (they are dated Apr — unchanged signature, but re-confirm).
3. **Native-dep `cassi-larql` (Rust nested repo, plan §4.6).** `backfill-worker.ts` (LIVE) requires the
   `cassi-larql/index.node` N-API addon at `node_modules/cassi-larql` via `CASSICORE_ROOT || cwd()`. The plan does
   NOT migrate `packages/larql` (Rust backend; NOT a P0–P7 module candidate). **Default: make `cassi-larql` a
   documented **peerDependency** of `@cassicore/mnemic-field` that the host (or the D: repo's daemon at P7) provides
   at the package's node_modules; re-point `backfill-worker.ts` to resolve it package-relatively
   (`createRequire(import.meta.url)('cassi-larql')` when installed, else a clear error). Do NOT vendor the native
   addon.** Mark `[VERIFY]` that the backfill path is not exercised on the P4-tested suite (it is a heavy one-shot
   backfill; the default `vitest` ported tests don't run it).
4. **`lmdb` npm native dep.** `feature-index-lmdb.ts` (LIVE) requires `lmdb` (native mmap). **Default: add `lmdb`
   (+ `better-sqlite3`) to `@cassicore/mnemic-field` deps; confirm the napi-rs prebuilt binary installs on the
   worker's platform (Windows x64 — yes, lmdb ships win32-x64 prebuilts).** If a build-toolchain host appears, fall
   back to declaring the SQLite `FeatureIndex` as the supported default and treat LMDB as optional (the constructor
   ALREADY falls back to SQLite when LMDB open throws — index.ts:632-638). Open Flag 4 double as the isolation
   caveat.
5. **`setFieldEncoder`/`MindFieldEncoder` + `field-encoder/` is the overhaul seam — vendor type stub, do NOT wire.**
   `index.ts` imports `MindFieldEncoder` from `../field-encoder/types.js` (sibling dir the overhaul owns, mtime
   TODAY). **Default: vendor a faithful type stub at `src/vendor/core/intelligence/field-encoder/types.ts`** so
   `setFieldEncoder(encoder)`/`fieldDepositsSent()`/`drainFieldDeposits()` compile; **do NOT implement any journal
   hooks** (recorded coordination, §4g). When the overhaul's field-encoder publishes, re-point the stub. `field-encoder.test.ts`
   → host-wired quarantine (Open Flag 6). Mark `[VERIFY]` the stub's interface matches `field-encoder/types.ts` at
   execution.
6. **`field-encoder.test.ts` is host-wired → `tests/host-wired/`.** It imports `../field-encoder/index.js` runtime
   (overhaul-owned, not P4 scope) + `./index.js` + `vitest`. **Default: port to `tests/host-wired/` quarantine**
   (plan §6), NOT into the package live suite; count it as quarantined, not passing, until the encoder packages
   land. Report actual ported-vs-quarantined vitest counts with P4 DONE.
7. **Inbound re-point scope is THREE packages (foundation + helix + constellation), not two.** The task brief named
   foundation + helix; the sweep also found **constellation's pre-existing `vendor/mnemic-field/` stub tree
   (index, types, cortex, edge-relators, graph-attn-propagator, self-model/{self-model-field,inter-field-bridge})
   consumed by 22 constellation files** — including the RUNTIME `GraphAttnPropagator`. **Default: re-point ALL 30
   inbound stub files across foundation(1)/helix(2)/constellation(7+) → `@cassicore/mnemic-field` and delete them
   (§3.1), as a REQUIRED P4 executor task.** Sequence: publish mnemic-field → swap each consumer's imports →
   delete stubs → re-typecheck each consumer package.
8. **`getEmbeddingService`/`getRerankerService`/`utils/math` are RUNTIME vendored symbols (not type-only).** A bare
   `throw` type stub breaks code that CALLS them (index.ts calls `getEmbeddingService()`/`getRerankerService()` in
   the constructor; affect.ts calls math helpers; self-model/self-model-field calls `getEmbeddingService`). **Default:
   port exact self-contained copies of these three into the vendor stubs** (they are pure factories/helpers with no
   host dep beyond foundation `ILogger`), so the P4 package runs without the sibling packages. Re-point to the owning
   packages (`@cassicore/embeddings` P5, `@cassicore/utils` P6) via the repoint log. Mark `[VERIFY]` that the copied
   impls match the source at execution (the overhaul may have moved them).

---

## 6. Executor playbook (P4 later wave — verbatim, mirrors P1–P3 §6)

1. **History import.** Temp-clone D: (`git clone --no-checkout --no-local`), then
   `git filter-repo --force --path core/intelligence/mnemic-field --path-rename core/intelligence/mnemic-field:packages/mnemic-field/src --mailmap …`.
   Fetch + splice (add/add, take `--theirs` for conflicted import files), verify `git log --follow`, commit the
   import (one commit). **NEVER merge a stale fragment: re-verify the D: paths have not moved/been rewired since
   the temp clone (plan §3d — the overhaul session is live).** If they have, re-clone the affected paths.
2. **Copy the 50 LIVE files** (§1.1) into `packages/mnemic-field/src/` MIRRORING the subdir structure (top-level +
   `training/` + `self-model/` + `knowledge/`), `.ts`/`.cjs` extensions + `.js` import specifiers verbatim. Do NOT
   copy the 4 DEAD (§1.1 note) or the 2 quarantined-uncertain (§1.2); DO copy `knowledge/index.ts` (§1.3).
3. **Apply the rewrite pairs per file — a GLOBAL replace per specifier, with the DEPTH-CORRECT prefix per file
   (P2 lesson (a) — no bulk sed).** Compute each specifier from the file's own dest dir:
   - Foundation (4 targets): `../../../types/interfaces.js`+`../../../../types/interfaces.js`→`@cassicore/foundation`
     (22 files), `../../../types/runtime.js`→`@cassicore/foundation` (2), `../../utils/paths.js`+`../../../utils/paths.js`→
     `@cassicore/foundation` (3), `../phrase-prototypes.js`→`@cassicore/foundation` (1). Only after P1's foundation
     package is present and its barrel re-exports every consumed symbol (§4a `[VERIFY]`).
   - Vendor (11 targets): top-level files → `./vendor/<rel-from-D-repo-root>.js`; subdir files →
     `../vendor/<rel-from-D-repo-root>.js` (§2.2).
   - Do NOT touch builtins/npm/internal `./X.js`/`../X.js` in-module imports.
4. **Write the vendor stubs** at `src/vendor/...` per §2.2/§3 tree. Type-only stubs = faithful type surface. For the 3
   RUNTIME symbols (Open Flag 8): port exact self-contained copies of `getEmbeddingService`, `getRerankerService`,
   and the `utils/math` helpers; `MindFieldEncoder` (Open Flag 5) is a TYPE stub only — do not wire hooks. For the
   subprocess entries: `umap-worker.cjs` co-located in `src/` (unchanged); `backfill-worker.ts` re-point the spawn to
   `new Worker(new URL('./backfill-worker.ts', import.meta.url))` and resolve `cassi-larql` package-relatively (Open
   Flag 3).
5. **Write `src/index.ts`** preserving ALL export names (§4a) — the `MnemicField` class, every barrel re-export, and
   `slerpEmbedding`. Do NOT rename any export or method.
6. **Package scaffold.** `package.json` (`@cassicore/mnemic-field`, `type: module`, deps `@cassicore/foundation` +
   `better-sqlite3` + `lmdb`; peerDeps note for `cassi-larql`), tsconfig (rootDir src/outDir dist/declaration true),
   vitest.config.ts, `.gitignore`. If shipping the subprocess as a `bin/`, add the entry — but see §4c
   recommendation (umap-worker stays package-runtime; backfill-worker is index-spawned).
7. **Inbound re-point (§3.1, REQUIRED).** After `@cassicore/mnemic-field` lands: re-point foundation's
   `edge-relators.ts` stub, helix's `mnemic-field/{index,types}.ts` stubs, AND constellation's `mnemic-field/*` stubs
   (index, types, cortex, edge-relators, graph-attn-propagator, self-model/*) → `@cassicore/mnemic-field`; delete the
   stubs. Re-typecheck foundation, helix, constellation (the `GraphAttnPropagator` runtime usage must resolve to the
   real class — Open Flag 7).
8. **Tests.** Port the in-module self-contained test(s) (`field-encoder.test.ts` → `tests/host-wired/` quarantine,
   Open Flag 6). Report actual ported-vs-quarantined vitest counts with P4 DONE. Note: there is no other in-tree test
   file under mnemic-field; the ported test surface is minimal and host-wired.
9. `npm run typecheck` (`tsc --noEmit`) in mnemic-field + the 3 re-pointed consumers; fix ONLY mechanical path
   errors. Then `npm test` for the ported suites (skip project-wide suites). Do NOT `npm install` beyond noting the
   deps; do NOT commit to D:.
10. **Commit discipline (plan §3c):** (1) history-splice import commit, (2) rewrite-delta commit (this table +
    vendor + package.json + barrels), (3) inbound re-point commit(s) across foundation/helix/constellation. Keep
    import/rewrite/re-point in SEPARATE commits; verify `git log --follow` before each rewrite commit. Do NOT commit
    to D:; the workspace push is handled by the owner (parallel sessions commit there — leave this file untracked).

### Files with no external or relocated imports (copy verbatim, zero rewrites)
`healpix.ts`, `polar-quant.ts`, `math-utils.ts`, `spatial-tokenizer.ts`, `attractor.ts`, `attractor-extractor.ts`,
`edge-relators.ts`, `field-generator.ts`, `visual-ingestor.ts`, `vq-prototypes.ts`, `graph-attn-propagator.ts`,
`spatial-index.ts`, `umap.ts`, `umap-worker.cjs` (self-contained worker), `backfill-worker.ts` (worker entry — the
spawn-path fix is in `index.ts`, §4c, not this file), `migration-jobs.ts`, `schema.ts`, `knowledge/index.ts`,
`knowledge/types.ts`, `self-model/annotation.ts`, `self-model/index.ts`, `self-model/types.ts`, `training/muon.ts`,
`training/newton-schulz.ts`, `training/retrieval-loss.ts`, `training/weight-store.ts` — **26 files**. All other
**24** live files carry ≥1 rewrite pair (foundation and/or vendor).

---

## 7. Reply summary (for the session owner)

- **Live-set count:** **50 files** migrated into `src/` (36 top-level + 5 `training/` + 6 `self-model/` + 3
  `knowledge/`); `field-encoder.test.ts` → host-wired quarantine (the 51st live file).
  **4 DEAD** excluded (`backfill-runner`, `feature-backfill`, `feature-migrate-to-lmdb`, `segmentation`(empty));
  **2 UNCERTAIN→quarantine** (`archive-engram-mapper`, `archive-ingestion-bridge`); **1 UNCERTAIN→migrate**
  (`knowledge/index` entry barrel).
- **Rewrite-pair counts by class (per-depth prefixes — NO uniform prefix):**
  - **Foundation → `@cassicore/foundation`: 4 unique targets** — interfaces.js (22 files: 16 depth-0
    `../../../types/`, 6 depth-1 `../../../../types/`), runtime.js (2, depth-0), paths.js (3: 1 depth-0
    `../../utils/`, 2 depth-1 `../../../utils/`), phrase-prototypes.js (1, depth-0).
  - **Vendor type/runtime stub: 11 unique targets** — 8 top-level files use `./vendor/…`, 3 subdir files use
    `../vendor/…` (embedding-service + reverie labels span both depths). 10 runtime vs type: dream-engine, cortex/,
    embeddings/types, reverie, aurora, field-encoder/types, field-encoder/index, math.js (runtime), embedding-service
    (runtime), reranker-service (runtime).
  - **Internal (unchanged under mirror): 0 rewrite pairs** (all `./X.js`+`../X.js` preserved). **Builtins/npm: 0.**
  - **Total rewrite pairs: 15 unique targets**; 24 files carry ≥1 rewrite.
- **Inbound-stub sweep (grep of workspace packages, NOT D:):** mnemic-field vendor stubs exist in **THREE**
  packages, not two: **foundation** (`core/intelligence/mnemic-field/edge-relators.ts`), **helix**
  (`mnemic-field/{index,types}.ts`), and **constellation** (`vendor/mnemic-field/{index,types,cortex,edge-relators,
  graph-attn-propagator,self-model/{self-model-field,inter-field-bridge}}.ts` — **22 constellation files consume
  these**, incl. the RUNTIME `GraphAttnPropagator`). All re-point to `@cassicore/mnemic-field` + stub deletion (§3.1).
  flux-team/mini-helix have NO mnemic-field refs.
- **Subdir depth map:** `src/` depth 0 = 36 files; `src/training/` depth 1 = 5; `src/self-model/` depth 1 = 6;
  `src/knowledge/` depth 1 = 3; `src/vendor/` = mirrored `core/{utils,intelligence/…}` stubs.
- **P4-specific handling:** (a) `index.ts` = `MnemicField` class + barrel, public surface quoted in §4a;
  (b) `graph-attn-propagator.ts` self-contained (zero rewrites); (c) subprocess entries: `umap-worker.cjs`
  self-contained + spawns via `import.meta.url` (unchanged, not a bin); `backfill-worker.ts` spawn path +
  `cassi-larql` native resolution must become package-relative (Open Flag 3); (d) `lmdb` = `feature-index-lmdb.ts`
  only live import → P4 npm dep (native caveat, Open Flag 4); (e) store-port interface proposed (§4g) to anticipate
  the overhaul journal handshake, NOT implemented; `MindFieldEncoder` vendored as a type stub (Open Flag 5).
- **Open flags (8, defaults recommended):** §5 — (1) knowledge/index→entry barrel, (2) archive pair→quarantine,
  (3) cassi-larql native peer dep, (4) lmdb native dep, (5) MindFieldEncoder/field-encoder type stub + no hooks,
  (6) field-encoder.test host-wired, (7) inbound re-point scope = 3 packages (foundation+helix+constellation),
  (8) runtime vendored symbols (embedding-service/reranker/math) -> faithful copies.
