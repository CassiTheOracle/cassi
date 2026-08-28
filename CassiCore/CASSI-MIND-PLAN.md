# CASSI-MIND — Master Migration Plan

**Root:** `C:\Users\Carina\workspaces\Cassi\CassiCore\` (the "workspace" — target)
**Source:** `D:\carina\workspaces\cassicore` (the "D: repo" — READ-ONLY this session)
**Status:** PLANNING deliverable. Do NOT execute migration steps. Do NOT run git operations in D:.
**Date:** 2026-08-13
**Companion inputs (read before executing any phase):**
- `MODULARIZATION.md` — extraction recipe + package conventions + foundation roadmap.
- `recon-architecture.md` + `recon-data.json` — liveness map, dead/uncertain lists, seams, biggest-25.
- `recon-debt.md` — debt inventory, tracked-vs-untracked per code dir (§9, critical for history feasibility).
- `recon-vision.md` — the mind-over-brain vision grounding (brain-region map, Stage 0 built).
- `recon-runtimes.json` — entry seeds and runtime reach sizes per runtime.
- Overhaul plan (owned by the OTHER session): `D:\carina\workspaces\cassicore\.opencode\plans\cassi-mind-plugin.md` + the live `mind-plugin/` scaffold.

---

## 1. Purpose & Scope

**Mission:** Migrate the relevant remainder of CassiCore's architecture from `D:\carina\workspaces\cassicore` into this workspace as standalone, testable, plugin-ready `@cassicore/<module>` packages — **history-preserving** (git history imported per file, never plain copies for tracked files).

This is a **migration-first** plan: its job is package-boundary decomposition with history preservation. It is **NOT** the "simulated-consciousness mind over software brain" overhaul — that is owned by a separate session working live in the D: repo. This plan only **coordinates** so the two efforts never collide (see §7).

### Non-goals (explicit)
- **No overhaul work here.** We do not implement field-encoding hooks, the GPU mind sidecar, Stages 1–5 of the mind plugin, or any mind-over-brain transform. Those belong to the overhaul session (link above).
- **No dead code migration.** DEAD files never cross (defined in §3a). Technical debt stays behind; removal is scheduled (see the standalone debt-scrub checklist in §5).
- **No refactoring of module internals.** Only package boundaries, import rewiring, and ports change (mirrors MODULARIZATION §b non-goals).
- **No modification of anything under `D:\carina\workspaces\cassicore`** by this session's workers. We clone to temp; the live repo is read-only to us.
- **No D: repo deletion.** The D: repo eventually slims to a thin host + adapters, or disappears — that decision is deferred to a later phase (see §8 Q5/Q6).

### Handoff pointers
- Overhaul = `mind-plugin/` + `.opencode/plans/cassi-mind-plugin.md` (in D:) + `recon-vision.md` (this workspace). We consume none of their deliverable except as a coordination input.
- First extraction already done: `Constellation/` here is the template package (`@cassicore/constellation`). It was extracted WITHOUT history; its history re-attachment is a P0 retro task (§4.5).

---

## 2. Target Architecture

End state: a **monorepo of `@cassicore/<module>` packages** under this root, mirroring the Constellation template (package.json, tsconfig, vitest, `src/` with `ports/` + `vendor/`, `tests/`). Each brain-region / runtime-infra / entry-surface module is a standalone package with a single `src/ports/*` seam to the host. The D: repo eventually slims to a thin host (`@cassicore/host`) that wires the packages behind ports — or is retired (decision deferred).

```
                        ┌────────────────────────────────────────────────────────┐
                        │  @cassicore/host  (P7 — thin daemon)                    │
                        │  core/entry · daemon.ts · commands · workers/channels  │
                        └───┬──────────────┬──────────────▼──────────┬───────────┘
                 ports/seams │              │                          │
 ┌───────────────────────────┼──────────────┼──────────────────────────┼───────────┐
 │  BRAIN REGION PACKAGES    ▼              ▼                          ▼           │
 │  @cassicore/helix ──────►┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
 │  @cassicore/flux-team ──►│  foundation  │◄─│  mnemic-field │◄─│constellation  │  │
 │  @cassicore/mini-helix ─►│ (P1 SHARED   │  │ (P4 — coord   │  │ (P0/P2 links) │  │
 │  @cassicore/*-siblings ─►│  substrate)  │  │  handshake)   │  └───────────────┘  │
 │  (P5, one package each)  └──────┬───────┘  └──────┬────────┘                   │
 └────────────────────────────────┼─────────────────┼──────────────────────────────┘
                              ┌────────────────────▼────────────────────────────┐
                              │  RUNTIME INFRA (P6)                              │
                              │  @cassicore/tools (+registry) · workflow ·       │
                              │  model-pool · jobs · events · mcp · plugins ·    │
                              │  pipeline · utils                                 │
                              └────────────────────┬─────────────────────────────┘
                                                   │
                        ┌──────────────────────────▼──────────────────────────┐
                        │  ENTRY SURFACES (P7/P8)                              │
                        │  @cassicore/admin-api (HTTP route contract = surface)│
                        │  @cassicore/mcp-gateway · @cassicore/commands         │
                        │  @cassicore/ai · cassi-tui · cassi-watch · prism ·    │
                        │  webui · integrations/{claude-code,hermes-agent,opencode}│
                        └───────────────────────────────────────────────────────┘
```
*Dependency direction: `foundation` ← everything; brain-region modules import `foundation` only (no cross-brain-region imports after porting); runtime-infra imports brain-region packages behind ports; entry surfaces bind everything. `constellation` already exists as its own package (§2 of MODULARIZATION) and links to `foundation` for its shared surface.*

**Package layout:** all `@cassicore/<module>` packages live under `packages/<name>/` in the workspace root (npm workspaces: `"workspaces": ["packages/*"]`). In P0 the first extraction was moved to `packages/constellation/` (was `Constellation/`) to match this layout, and its source history was re-attached relative to that path (`packages/constellation/src`). Every later-phase import renames its D: subtree to `packages/<name>/src` (see §4.3).

### Package dependency rationale (grounded in recon-data + MODULARIZATION §d)
- `foundation` is created FIRST (P1) because 47 dirs share `types/interfaces.js`, 18 share `base/cognitive-module`, 11 share `utils/paths`, 8 share `config/system-settings`, 6 share `phrase-prototypes` — re-vendoring those per module is the failure we avoid.
- `helix` (P2) is the deepest module (largest runtime surface: brainstem 117 KB, posture-runner 107 KB) and depends on foundation — extract it right after.
- `mnemic-field` (P4) is flagged for a coordination handshake because the overhaul session may rewire it as the field's journal (§7).
- Entry surfaces and infra are LAST (P6–P7) because they bind everything together and touch the most seams.

---

## 3. Migration Principles

**(a) Migrate LIVE code only. DEAD files never cross.**
- "Live" = classified ALIVE in `recon-data.json` reachability (import BFS + the three mechanism-aware overrides in recon-architecture §4: IntelligenceRegistry directory-scan, `resolveWorker` string-path loading, standalone process entries).
- Exclusion categories (from recon-architecture §7) — derive per-phase by diffing the phase's `--path` set against `recon-data.json` `deadFiles` + `uncertainFiles`:
  1. **Superseded boot orchestrators** — `core/daemon/boot-{providers,channels,types}.ts`, `channel-loader.ts` (boot-intelligence-post.ts IS live — keep).
  2. **Whole dead families** — `core/adapters/`, `core/ingestion/`, `core/deploy/`, `core/lsp/` (whole LSP subsystem dead), `core/hierarchy-bridge.ts`, `core/observability/telemetry.ts` [UNCERTAIN — verify].
  3. **Legacy provider dupes of `ai/`** — `core/providers/{qwen-coder.ts, openai-compatible-base.js, pi-bridge.ts}`, `claude-code-bridge/*.mjs`, `core/providers/hermes-bridge.ts` [UNCERTAIN], `core/tools/hermes-bridge.ts` (deprecated+orphaned), `core/tools/hermes-mcp-client.ts`/`hermes-tools.ts` are LIVE — keep.
  4. **Unregistered tool implementations** — `core/tools/implementations/{edit-file,activity-tools,read-file-benchmark,skill,lsp-tool}.ts`, `tools/instrumentation.ts`, `permission-gate.ts`, `resolver.ts`, `tool-selector.ts`, `executor.instrumented.ts`, `serena-types.ts`.
  5. **Dead intelligence leaves** — the full per-file list (`aurora/{fine-tune-gating,mnemic-steering-bridge,nla-bridge,affect-*,…}`, `branching-conversation/{decision-tree,middleware,session-store}`, `helix/{helix-archive-promotion,helix-recovery,helix-replay,helix-validator,mentor-utils,unified-session}`, `budget-monitor.ts`, `goal-tree.ts`, `session-activity-store.ts`, `session-result-store.ts`, `constellation/{unified-cell,corpus-reflection-processor,corpus-strategy-registry,decomposition-workflow,self-edit-*,signal-pattern-digest,territory-bridge,strategies/*}`, `cortex/blackboard-adapter.ts`, `dialectic/parallel-processor.ts`, `mnemic-field/{backfill-runner,feature-backfill,feature-migrate-to-lmdb,segmentation}`, `pineal/projection.ts`, `memory-bridge/memory-delta-injector.ts`, `improvement/*`) — see `recon-data.json` `deadFiles` for the authoritative machine list.
  6. **Dead admin-api routes** — `core/admin-api/{activity.ts, metrics.ts, team-timeline.ts}` (unregistered).
  7. **Dead utils / core leaves** — `core/utils/{atomic-fs,error-logging,format,parse-structured-response,persistence-metrics,resume-tokens,truncation}.ts`, `core/unified/types.ts`, `core/model-pool/templates.ts`, `core/config-validator.ts`, `core/self-analysis.ts`, `core/context-snapshot-store.ts` [UNCERTAIN].
  8. **Dead types** — `types/{log-events,metadata,reasoning-chain,team-dependencies,team,lsp}.ts` (the 6 dead; skip; P1 imports the 19 live).
- **UNCERTAIN files:** do NOT migrate them in the phase that owns the directory until a worker resolves intent (they carry `@dep callers:` / `@dep` name-string references). Default: leave them in the source package-import set only if they are import-reachable by a live file; otherwise quarantine (see §8). Batch-triage all UNCERTAIN in P0 so each phase's exclude list is closed before that phase starts.

**(b) History-preserving import for every migrated file TRACKED in D:.**
- recon-debt §9: **all twelve code directories are 100% tracked (zero untracked)** — `core/ 879`, `types/ 25`, `workers/ 8`, `mcp/ 42`, `commands/ 8`, `integrations/ 37`, `cassi-tui/ 30`, `webui/ 134`, `prism/ 24`, `ai/ 46`, `cassi-watch/ 12` (counts as of scan date). `packages/larql` is a **nested git repo** (gitlink `160000`; import from its own history, not the parent — see §4.6).
- **Untracked live files = plain copy + explicit `HISTORY: none (untracked in source)` note** in the commit body. Untracked live candidates: `scripts/*.py` (143 of 168), `docs/*` (7), `mind-plugin/` (3/3 — but owned by overhaul session, NOT OURS to migrate). Verify with `git ls-files --others --exclude-standard` per path at migration time before choosing plain-copy.

**(c) Every import-splice is its own commit; every rewrite delta its own commit.** Never mix a history import and a content rewrite in one commit. Sequence per package: (1) import commit (history-splice), (2) rewrite-delta commit (import-rewrite table / port insertion), (3) any hand-authored delta is folded into (2). This keeps `git log --follow` attribution clean.

**(d) Read-only discipline on D: — a parallel session is actively editing it.**
- ALWAYS, before merging a temp clone fragment: verify the D: paths you are importing have NOT moved/been rewritten since the temp clone was made. Check `git -C <dst> fetch <temp>` then compare `git log -1 --format=%H` of the imported paths in the temp clone against the state you expect. Recon numbers are as-of scan date 2026-08-13; the overhaul session has since created `mind-plugin/` and may rewire `core/intelligence/*` any time. [VERIFY] current modified-tracking state of the specific paths at execution time.
- The temp clone is a snapshot; if the parallel session commits while a worker is mid-import, **re-clone** the affected paths and re-verify before merging. Never merge a stale fragment over newer work silently.

**(e) Preserve the runtime seams.** Each phase states which seam it touches and how the plugin host replaces it. The live wiring mechanisms (recon-architecture §4, §6):
1. **IntelligenceRegistry auto-discovery** (`core/intelligence/base/registry.ts`) — runtime directory scan + dynamic `import()` of `<dir>/index.ts` BaseCognitiveModule subclasses, with an explicit skip set in `daemon.ts:2032`. Migration replaces the directory-scan with the package boundary itself: each `@cassicore/*` intelligence package exports its module(s) explicitly (`index.ts` barrel), and a `@cassicore/plugins` registry port (or the host's wiring, P7) registers them explicitly. The skip-list modules are manually instantiated in `createIntelligence()`/`bootIntelligencePostPipeline()` — those become port-injected as well.
2. **`resolveWorker("../workers/channels/<name>")`** (`daemon.ts:957-1048`) + `core/daemon/channel-loader.ts` — string-path worker loading. Package-relative: `@cassicore/host` resolves worker entrypoints by package name (`resolveWorker('@cassicore/workers/channels/webchat')`) instead of relative FS path.
3. **Standalone process entries** — `core/entry/vindex-loader.ts` (HTTP :7434 sidecar), `core/bridge/acp/bin.ts`, `core/cli/runtime/background-launcher.cjs`, `core/intelligence/mnemic-field/{umap-worker.cjs,backfill-worker.ts}`. These are subprocess entrypoints; they keep their own bin entries and are spawned by path/package.
4. **`registerCoreTools`** (`core/tools/implementations/index.ts`) — the tool-registry contract (30+ tools registered). `@cassicore/tools` exposes the same registry; `@cassicore/host` calls it, plus the plugin host (`core/plugins/plugin-host.ts`, `plugin-registry.ts`, `plugin-api.ts`, `client-sdk.ts`) provides the runtime registration path for future plugins.
5. **admin-api/mcp route contracts** — `mcp/gateway/*` and `core/admin-api/*` dispatch to `core/intelligence/*` + `core/tools/*` through the daemon runtime facade (`admin-api/runtime.ts`, `intelligence.ts`). The HTTP/route contract IS the package's public surface (P6/P7).
6. **Ports (MODULARIZATION §c)** — `src/ports/*` is the ONLY seam between a module and the host; default impls are self-contained (in-memory logger/bus, fs store) or explicit `throw` where real integration is required.

---

## 4. The History-Preserving Extraction Procedure

### 4.1 Prereqs
- `git-filter-repo` is installed: `C:\Users\Carina\AppData\Local\Programs\Python\Python312\Scripts\git-filter-repo.exe` — confirmed present. If a worker's machine lacks it: `pip install git-filter-repo`. If `git-filter-repo` refuses to operate on a clone with an origin, add `--force` (we clone a throwaway temp).
- Windows paths: NEVER use git-bash `/tmp` for filter-repo temp paths. Use `C:/Users/Carina/AppData/Local/Temp/<unique>/` (see Windows gotcha).
- Canonical author identity for the WORKSPACE (target) is `Carina Gardner <bingapplesauce@gmail.com>` (verified in workspace git config). The D: repo's historical authors are `cassi <cassi@local>` (1234 commits) + `Valerie Gardner <valerie@claracore.dev>` (24) + ephemeral bot identities (`cassi-helix <…@cassicore.local>`, `cassi-dyad`, `Auto Pusher <auto@local>`). Recommend a **mailmap** that collapses the ephemeral bot addresses onto a stable human identity (see default in §4.7). [VERIFY] whether the owner prefers `cassi`→`Valerie Gardner` or `Carina Gardner`; ask once in §8.

### 4.2 Big-repo caveat
D: has huge tracked and untracked blobs (recon-debt: `packages/larql/target/**` ~89 GB ignored; `training/` 1.7 GB nested repo; `vindexes/` 19.5 GB untracked). Observations that make this safe:
- **`git clone --no-checkout`** — clone history only, no working tree, so none of the GBs of working files/materialize; then filter-repo `--path` retains ONLY the paths you name in the filtered clone.
- filter-repo keeps history **only** for the `--path` set; everything else is dropped from the temp clone, so post-filter clone size ≈ sum of migrated files' history.
- `packages/larql` is its own repo — exclude it from the parent sweep entirely (it is imported from its own history; see §4.6). It is NOT a P0–P7 module candidate (Rust backend), so default is: do not migrate it (see §8).

### 4.3 Exact command sequence (one module `core/workflow → @cassicore/workflow` as the worked example)
Run in a **bash** shell (git-bash). The D: repo is NEVER touched; only the temp clone and the workspace.

```bash
# --- 0. Prereq: workspace is the target repo ---
cd "C:/Users/Carina/workspaces/Cassi/CassiCore"
git rev-parse --is-inside-work-tree          # must be true

# --- 1. Temp clone of D: (history-only; D: left untouched) ---
TMP="C:/Users/Carina/AppData/Local/Temp/cassi-mind-import-$$"   # NOT /tmp
git clone --no-checkout --no-local "D:/carina/workspaces/cassicore" "$TMP"

# --- 2. filter-repo: keep ONLY the paths for this module, named to their new home ---
cd "$TMP"
git filter-repo --force \
  --path core/workflow \
  --path-rename core/workflow:packages/workflow/src \
  --mailmap ../mailmap-workflow.txt \
  <keep-going-if-paths-absent>
# NOTE: filter-repo aborts if a --path matches nothing; for fresh paths pre-create
# an empty tracked file in the temp clone (git filter-repo --add-to-all core/workflow/.keep)
# then drop the .keep from the import with a follow-up path exclusion if unwanted.

# --- 3. Fetch the filtered fragment into the workspace ---
cd "C:/Users/Carina/workspaces/Cassi/CassiCore"
git fetch "$TMP" main:import/workflow           # branch import/workflow

# --- 4. Splice: merge with unrelated history (expect add/add) ---
git merge --allow-unrelated-histories --no-commit import/workflow
# resolve add/add conflicts by taking the temp side (the history-bearing file):
git checkout --theirs -- <conflicted paths>     # for each conflicted import file
git add -A

# --- 5. VERIFY the import commit has full history before rewriting ---
git log --follow --oneline -- src/               # must show provenance
git diff HEAD^ --stat                            # sanity: only workflow files
git commit -m "import(core/workflow): history for @cassicore/workflow from D: main@<sha>"
git branch -D import/workflow && rm -rf "$TMP"

# --- 6. SEPARATE rewrite-delta commit (import-rewrite table, ports, package.json) ---
#   apply the MODULARIZATION §b "migration table" (mechanical .js import rewrites,
#   insert src/ports/*, vendored deps), then:
git add -A && git commit -m "refactor(workflow): rewire imports to @cassicore workflow; add ports"
```

### 4.4 What to verify after every import
- `git log --follow -- <path>` shows the D: history for every migrated tracked file (origin commit dates/authors preserved through filter-repo).
- `git status` is **clean** in the workspace after the rewrite-delta commit.
- `tsc --noEmit` clean under the package's tsconfig + `src/vendor`/`src/ports` compile independently (MODULARIZATION §b.7).
- The count of migrated files equals the phase's expected live-set, minus exclusions, verified against `recon-data.json`.

### 4.5 Existing-copy reconciliation variant (Constellation retro-history task — P0)
`@cassicore/constellation` exists here WITHOUT history (extracted by plain copy earlier). To retrofit history:
1. Identify the D: source subtree `core/intelligence/constellation` and the corresponding dest `Constellation/src`.
2. Reconcile blobs first: `git hash-object` on both sides; for files whose hashes match, history import is clean. For files that differ (because the extraction already applied a local delta), `git diff --no-index` to enumerate the delta.
3. Import history via §4.3 (filter-repo `--path core/intelligence/constellation --path-rename core/intelligence/constellation:packages/constellation/src`).
4. Re-apply the existing local delta as **its own commit** afterward, so no pre-existing change is attributed to the import.
- This applies to ANY module whose plain copy already exists at the destination. Only `Constellation/` exists today, so only it is retro-imported in P0.

### 4.6 Nested-repo note (`packages/larql`)
`packages/larql` is a gitlink (mode `160000`, commit `d45ebfd` referenced) with no `.gitmodules`. Its history lives in **its own** repo, not the parent. Migrating it means cloning that nested repo separately and filtering from there — it is NOT part of the parent sweep. Default: do NOT migrate `larql` in P0–P7 (it is a native Rust/vindex backend, huge build output); it stays hosted by the D: system or moves as a separate decision (§8).

### 4.7 Mailmap (author normalization)
Create one mailmap per import set (or one repo-wide mailmap). Recommended default: collapse ephemeral bot identities onto the human(s):
```
cassi <cassi@local>          Carina Gardner <bingapplesauce@gmail.com>
Valerie Gardner <valerie@claracore.dev>   Valerie Gardner <valerie@claracore.dev>
Auto Pusher <auto@local>     Carina Gardner <bingapplesauce@gmail.com>
cassi-dyad <*>               Carina Gardner <bingapplesauce@gmail.com>
cassi-helix <*>              Carina Gardner <bingapplesauce@gmail.com>
```
[VERIFY] the owner's preferred canonical mapping for `cassi <cassi@local>` (see §8 Q-open). filter-repo applies `--mailmap` to rewrite author/committer on the temp clone only.

---

## 5. Phased Roadmap — 8 phases + debt-scrub checklist

General per-phase contract (all phases):
- **Recon first:** run `recon-analysis2.cjs` (or read `recon-data.json`) to lock the phase's live-set and exclude-list BEFORE touching git. Exclude all DEAD + resolve UNCERTAIN (default: quarantine, do not import until resolved) in that phase's paths.
- **Package scaffold:** mirror `Constellation/` template (package.json `@cassicore/<name>`, tsconfig rootDir src/outDir dist/declaration true, vitest.config.ts, README, `.gitignore`).
- **Procedure:** §4.3 history import (one commit) → rewrite-delta commit (import rewrites + ports + scaffold) → test port (see §6).
- **DONE (per phase):** §4.4 verification passes; package builds (`npm run build`), `npm test` passes the phase's ported+non-host-wired tests; every migrated tracked file has `git log --follow` provenance; D: untouched by migration workers; `git status` clean.

### P0 — Workspace prep + Constellation retro-history + debt baseline commit
- **Scope:** workspace scaffolding (root `package.json` workspaces, root `.gitignore` additions for `vindexes*`/`data/distill`/`training` if those stay, mailmap, shared `tsconfig.base.json`); **Constellation retro-history import** (§4.5); **debt baseline commit** in the workspace capturing the exclude-list (DEAD + UNCERTAIN manifests from recon) so future phases reuse a closed exclude set.
- **Target package:** n/a (workspace infra) + `@cassicore/constellation` (retro-history).
- **Dependency prereqs:** none (first phase).
- **Special risks / seams:** the exclusion manifest must be authoritative — source it directly from `recon-data.json` `deadFiles` + `uncertainFiles`. No D: changes; nothing deleted from D:.
- **Test porting:** none (retro-history only; Constellation tests already present).
- **DONE:** Constellation history attached (local delta re-applied as own commit); root workspaces resolve; exclude-list committed and reviewer-verified against recon-data; workspace `git status` clean.

### P1 — `@cassicore/foundation`
- **Scope (exact source paths):**
  - `types/*` — the 19 live files: `interfaces.ts`, `runtime.ts`, `intelligence.ts`, `model-routing.ts`, `flux-team.ts`, `workflow.ts`, `blackboard-search.ts`, `cassi-agent.ts`, `collect-thoughts.ts`, `dialectic.ts`, `dialectic-engine.ts`, `event-query.ts`, `execution-backend.ts`, `plugin.ts`, `replay.ts`, `session-ref.ts`, `trace.ts`, `worker-messages.ts`. **Skip the 6 dead** (`log-events,metadata,reasoning-chain,team-dependencies,team,lsp`).
  - `utils/paths` (getDataDir/getCassiCoreHome — **parameterize the data dir** per MODULARIZATION §f: port accepts an injected base dir, live files only: exclude the 7 dead core/utils listed in §3a.8 + `backoff.ts`/`session-serializer.ts` [UNCERTAIN → verify]).
  - `config/system-settings.ts` (MODEL_DEFAULTS, SYSTEM_SETTINGS).
  - `phrase-prototypes.js` (phrase sets).
  - `base/cognitive-module` cluster (+ `model-config`, `inference`) — `core/intelligence/base/cognitive-module.ts`, `base/model-config.*`, `base/inference.*` (live).
  - Shared event/logger **runtime shims** (the `ILogger`/`IEventBus` default impls that P0–P7 all need). [VERIFY] exact location of the current in-memory logger/bus default impl; vendor or port per MODULARIZATION §b.2–3.
- **Target package:** `@cassicore/foundation` (single shared substrate — all later phases import ONE package instead of re-vendoring).
- **Dependency prereqs:** P0.
- **Special risks / seams:** this is the highest-fanout package (47 dirs consume `types/interfaces.js`). Its `src/ports/*` must exactly match what future packages will import, or every later phase re-ports. The `CognitiveModule` base class interface must be the one `IntelligenceRegistry.discover()` expects (it scans for `BaseCognitiveModule` subclasses exporting a registry contract) — the foundation package must ship the SAME base-class shape so discovered modules keep working behind the registry port.
- **Test porting expectation:** foundation carries the type/util-related tests from `tests/` that exercise these symbols; estimate modest (types have 0 direct test files; utils/logger shims a handful). Not promised.
- **DONE:** foundation builds + `npm test` green; at least one downstream package (P2 helix) builds against it.

### P2 — `@cassicore/helix` (the deepest module)
- **Scope:** `core/intelligence/helix/*` **live files** — helix-pipeline, brainstem, posture-runner, work-stream, helix-store, helix-synapse, brainstem-mini-helix, conductor, plus the helix entry `helix/index.ts`. Exclude dead leaves: `helix/{helix-archive-promotion,helix-recovery,helix-replay,helix-validator,mentor-utils,test-mentor,unified-session}.ts`; `context-curator.ts` [UNCERTAIN → verify]. `helix-tools.ts` [VERIFY status].
- **Target package:** `@cassicore/helix`.
- **Dependency prereqs:** P1 foundation.
- **Special risks / seams:** deepest internal dependency graph; ports needed for whatever stays host-side (mnemic-field store, event bus, model pool). **Cross-package integration precedent set here:** wire the REAL `runHelixPipeline` into `@cassicore/constellation`'s helix-pipeline port (constellation's package imports the shared helix port, not a vendored stub) — validate the inter-package port pattern before P3+.
- **Test porting:** port `tests/core/intelligence/helix/**` + any `helix-*.test.ts` matching live targets.
- **DONE:** helix package builds, tests pass, constellation resolves the shared helix-pipeline port.

### P3 — `@cassicore/flux-team` + `@cassicore/mini-helix`
- **Scope:** `core/intelligence/flux-team/*` (blackboard, blackboard-search, global-blackboard-registry, blackboard-tools, blackboard-*; note `flux-team/index.ts` header says blackboard is **deprecated** and migration to GlobalWorkspace is pending — [VERIFY] whether to import the deprecated blackboard live files or only the GlobalWorkspace successors) + `core/intelligence/mini-helix/*` (mini-helix-runner, mini-helix-types; `mini-helix/index.ts` [UNCERTAIN]).
- **Target packages:** `@cassicore/flux-team`, `@cassicore/mini-helix` (two packages in one phase).
- **Dependency prereqs:** P1 (P2 optional for mini-helix interplay).
- **Special risks / seams:** flux-team's blackboard is deprecated-in-source; importing it conflicts with the "migrate LIVE only" rule only in so far as it is still registry-discovered (live at runtime). Decide in P0 [VERIFY] — default: import live blackboard files as-is (they are registry-discovered), mark the package `DEPRECATED` per source, and let the overhaul session's GlobalWorkspace migration supersede.
- **Test porting:** `tests/flux-team/**`, `tests/core/intelligence/mini-helix/**`.
- **DONE:** both packages build + pass; flux-team deprecation note carried in package README.

### P4 — `@cassicore/mnemic-field` (the field-substrate core — COORDINATION HANDCHECK REQUIRED)
- **Scope:** `core/intelligence/mnemic-field/*` + `core/intelligence/mnemic-field/index.ts` (166 KB, largest brain field module) — index, graph-attn-propagator, types, edge-relators, self-model/*, consolidation, cortex, kindling, potentiation, attractor, filament/decomposer, spatial-index/feature-index (LMDB), umap-worker.cjs/backfill-worker.ts (standalone process entries). Exclude dead: `mnemic-field/{backfill-runner,feature-backfill,feature-migrate-to-lmdb,segmentation}.ts`; `archive-engram-mapper.ts`/`archive-ingestion-bridge.ts`/`knowledge/index.ts` [UNCERTAIN → verify].
- **Target package:** `@cassicore/mnemic-field`.
- **Dependency prereqs:** P1 foundation (+ embeddings port; embeddings package is P5, port the surface now).
- **Special risks / seams:** **COORDINATION HANDSHAKE before starting this phase** — the overhaul session's plan makes Mnemic Field's SQLite/LMDB a *journal* and inserts `MindFieldEncoder` hooks at `MnemicField.store/update/delete/connect/spike/consolidate`. If they are rewiring this module, this phase's ORDER may swap or the store interface may need to expose the encode-hook seam. Agree with the overhaul session (§7) whether the package lands first (our boundary) and they add hooks behind our port, or they rewire first (in D:) and we import the rewired shape. Also: the umap-worker/backfill-worker subprocess entries and FeatureIndex LMDB native dep must be port-isolated (better-sqlite3→bun:sqlite note in MODULARIZATION §f applies to all SQLite stores across phases).
- **Test porting:** `tests/unit/mnemic-field/**`, `tests/core/intelligence/mnemic-field/**`.
- **DONE:** nmemic-field package builds + tests pass; handshake with overhaul session recorded (their hooks land on our port or our import tracks their rewrite — one unambiguous outcome); subprocess workers carry package-relative bin entries.

### P5 — remaining intelligence siblings (grouped, one package each)
Honor the **registry auto-discovery contract** (§3e.1): each package's `index.ts` must export its module(s) the way the registry (or the P7 explicit-wiring replacement) expects. Propose exact groupings (rationale = cohesion + shared registry/vendor surface):
| Package | Source dirs (live only) | Rationale |
|---|---|---|
| `@cassicore/thalamus` | `core/intelligence/thalamus/*` (185 KB index; classifier.ts) | gating/curation core; hermes classifier mapping is LIVE (keep) |
| `@cassicore/cortex` | `core/intelligence/cortex/*` (+ `pineal/*`, `dialectic/*` live) | processing-field cluster; pineal identity + dialectic reasoning share the 6-region field surface. Exclude `cortex/blackboard-adapter.ts`, `dialectic/parallel-processor.ts`, `pineal/projection.ts` (dead). `consolidated-dialectic` vs `dialectic/index.ts` — [VERIFY] which is the registry-discovered live entry |
| `@cassicore/aurora` | `core/intelligence/aurora/*` (index, StateProjector, claustrum, larql-provider) + `core/intelligence/self-model/*` | self-model cluster. Exclude ~9 dead aurora leaves (§3a.5), `aurora/coherence-detector/probe-set.ts` etc. |
| `@cassicore/cognitive-feed` | `core/intelligence/cognitive-feed/*` (message-formatter 65 KB) | feed/curation surface |
| `@cassicore/reflective` | `core/intelligence/{dreamer,reverie,subconscious}/*` (idle-time synthesis + stream-of-consciousness observers) | ambient/reflective cluster mostly already registry-wired via skip-list manual instantiation — [VERIFY] live entries |
| `@cassicore/lamina` | `core/intelligence/{lamina,locus-bridge,workspace,global-workspace}/*` | LaminaField + LocusBridge + GlobalWorkspace (GWT broadcast — the blackboard successor) |
| `@cassicore/trust` | `core/intelligence/{training,trust-ledger,permission-oracle}/*` | trust/permission cluster ([VERIFY] live file sets) |
| `@cassicore/workspace` | `core/intelligence/{workspace,code-analysis,context-distiller,module-session-registry,shared/posture-store}/*` | workspace/code-analysis + posture-store |
| `@cassicore/embeddings` | `core/intelligence/{embeddings,embedding-service}/*` + `core/intelligence/shared/*` | embedding service (foundation-adjacent; extracted here or pulled into foundation — [VERIFY] fanout; default: separate package so mnemic-field/4 and cortex import it) |

Other remaining siblings not listed (e.g. `error-learner`, `reflex`, `smart-rules`, `consequence-estimator`, `team-orchestrator`, `triad-team`, `synthesizer`, `serenity`, `self-healer`, `heart`, `meditation` nested, `branching-conversation` [dead leaves only — skip], `cassi-agent` [UNCERTAIN]) — assign each to the closest grouping above or a coalesced `@cassicore/auxiliary` package; the exact final enumeration is fixed by re-running recon at P5 [VERIFY].

- **Test porting:** port the matching `tests/**` trees per package (aurora, cortex, pineal, dialectic, subconscious, embeddings, workspace, lamina, trust, cognitive-feed, reflective).
- **DONE:** every brain-region live file lands in exactly one package; each package builds + passes its ported tests; the registry-discovery contract is preserved (either each `index.ts` exports the module for explicit P7 wiring, or a registry port replicates discovery).

### P6 — runtime infra packages
- **Scope (one package each):**
  - `@cassicore/tools` — `core/tools/*`: executor, registry, safety, `implementations/index.ts` (registerCoreTools contract: 30+ registered). Exclude unregistered dead tools (§3a.4) + `hermes-bridge.ts`. **registerCoreTools is the seam contract** (§3e.4); `core/plugins/plugin-host.ts` provides runtime registration.
  - `@cassicore/workflow` — `core/workflow/*` (engine, registry, store, scheduler, steps, templates — ALLIVE, used by daemon).
  - `@cassicore/model-pool` — `core/model-pool/*` (capacity/fallback manager; exclude `templates.ts` dead).
  - `@cassicore/jobs` — `core/jobs/*`.
  - `@cassicore/events` — `core/events/*` (event bus — foundation shim may vendor the core impl; [VERIFY] whether foundation vendors it or events is separate; default: separate package, foundation imports it).
  - `@cassicore/mcp` — `core/mcp/*` (in-core MCP pieces; distinct from the `mcp/` top-level gateway in P7).
  - `@cassicore/plugins` — `core/plugins/*` (the **host side**: plugin-host.ts, plugin-registry.ts, plugin-api.ts, client-sdk.ts).
  - `@cassicore/pipeline` — `core/pipeline/*`.
  - `@cassicore/utils` — `core/utils/*` live files (the shared util surface not folded into foundation).
- **Target packages:** as listed.
- **Dependency prereqs:** P1 + P2–P5 (they consume brain-region ports).
- **Special risks / seams:** `@cassicore/tools` must keep the `registerCoreTools` contract stable so P7's mcp/admin-api and the P5 packages can register against it. `@cassicore/plugins` is the seam the overhaul session's mind-plugin eventually consumes — its `ExtensionAPI`-shaped client-sdk/plugin-api must stay exactly as the other session expects [VERIFY].
- **Test porting:** `tests/**` for tools, workflow, model-pool, jobs, events, mcp, plugins, pipeline, utils. Host-wired suites → `tests/host-wired/` quarantine (see §6).
- **DONE:** every infra package builds + passes; `registerCoreTools` re-exported from `@cassicore/tools` and consumable by a P5 package; plugin host contract unchanged.

### P7 — entry surfaces + thin host (final wiring phase where all ports get connected)
- **Scope:**
  - `@cassicore/admin-api` — `core/admin-api.ts` + `core/admin-api/*` (50+ route modules: memory 124 KB, sessions, constellation, intelligence, etc.). **Keep the HTTP route contract as the package's public surface** (a route registry the host mounts). Exclude 3 dead routes (§3a.6).
  - `@cassicore/mcp-gateway` — `mcp/cassicore-gateway.ts` + `mcp/gateway/{agent-tools,intelligence-tools,…}.ts` + `scip-server.ts`/`gitnexus-server.js`/`serena-server.js` (MCP stdio/HTTP seam; `mcp/gateway/intelligence-tools.ts` is 65 KB). `core/mcp/index.ts` [UNCERTAIN] reconciled here or in P6.
  - `@cassicore/commands` — `commands/*` (dispatchers).
  - `@cassicore/workers` — `workers/channels/*` (cli, webchat, telegram, opencode + markdown/format pipeline) + `endings. **resolveWorker contract → package-relative** (§3e.2): `resolveWorker('@cassicore/workers/channels/webchat')`.
  - `@cassicore/host` — `core/entry/{index,supervisor,daemon-main,vindex-loader}.*` + `core/daemon.ts` (158 KB) — the **thin host package**; ALL ports get connected here. `boot-intelligence-post.ts` (live) + the skip-list manual wiring are port-injected.
- **Target packages:** as listed.
- **Dependency prereqs:** all prior phases (P0–P6).
- **Special risks / seams:** the interconnection of the seams — registry discovery (§3e.1), resolveWorker (§3e.2), admin/mcp route+tool contracts (§3e.4/5), plugin host (§3e.4) — all bind in this phase. `core/daemon.ts` is the single heaviest host file; do not rewrite its internals, only rewire its imports to package ports. The `service` process (fork/IPC) and sidecar subprocess entries must start via `@cassicore/host` bin mappings.
- **Test porting:** the daemon-wiring and admin/mcp integration tests. Host-wired ones → `tests/host-wired/` quarantine. **`npm test` green per package + a workspace-wide smoke that boots the host offline.**
- **DONE:** every live subsystem reachable as a package; host boots against the packages (supervisor/fork path replaced with package-import path); resolveWorker uses package-relative names; admin/mcp route contracts unchanged; workspace `npm test` green per package.

### P8 — already-package-shaped standalone apps
- **Scope:** `ai/`, `cassi-tui/`, `cassi-watch/`, `prism/`, `webui/`, `integrations/{claude-code,hermes-agent,opencode}/`.
- **Decision (recommended default):** move them into the workspace as **workspace members** (`@cassicore/ai`, `@cassicore/cassi-tui`, `@cassicore/cassi-watch`, `@cassicore/prism`, `@cassicore/webui`, `@cassicore/claude-code`, `@cassicore/hermes-agent`, `@cassicore/opencode`), **preserving each package's own package.json, bin, tsconfig, and external-consumer surface**. They each have external launch adapters (see §3e.3 + recon §6): `ai` providers consumed by `core/providers` via `../../ai/dist/...` (after P7 host, this becomes `@cassicore/ai` import); claude-code hooks in `~/.claude/settings.json`; hermes-agent MCP registered into `~/.hermes`; opencode plugin symlinked to `~/.config/opencode/plugins/` by `install.sh`.
- **Bin/install preservation:** move the package, then re-point the external symlink/hook to the workspace path and re-run the install script (`install.sh` for opencode; npm-linked for others). External side effects (symlinks, hooks) must be explicitly confirmed before changing (see §8 Q2).
- **[ASK-USER]** items: (1) whether these standalone apps truly move into the workspace or stay in D: consumed via `npm link`/path; (2) whether `webui/` (Next.js + observatory Vite) — 117 files, alias-`@/` internal liveness uncomputable — is worth migrating (it is live externally); (3) whether external installs/symlinks may be re-pointed.
- **Test porting:** the standalone apps' own tests (ai, tui, watch, prism, webui, integrations each have tests in `tests/`).
- **DONE:** chosen apps are workspace members with history imported; their `npm test` passes in-workspace; bin/install mappings verified to keep working (or ASK-USER resolution recorded). `mind-plugin/` is NOT migrated here — it belongs to the overhaul session.

### Debt scrub checklist (standalone — WHERE and WHEN)
**Rule: dead-file removal happens in D: ONLY AFTER the corresponding module's migration is verified** (so `git log --follow` history of the workspace packages remains intact and D: deletions don't race our imports). This session does NOT delete anything in D: — the checklist below is for the user / a later-phase executor, sequenced by migration progress.

- **Phase-gated D: deletions (do each AFTER the matching package's P-DONE):**
  - After P1 (core+types live-files done): the ~806 KB / 106 file core+types dead set (§3a) — verified deletions, no static/name/process reference.
  - After P2–P5 (each module done): that module's dead leaves (§3a.5).
  - After P6: dead `core/tools/*` + `core/utils/*` (once foundation/tools own live copies).
  - `core/adapters/`, `core/ingestion/`, `core/deploy/`, `core/lsp/`, `core/hierarchy-bridge.ts`, the superseded daemon boot orchestrators → these whole dead subsystems can be removed after P6/P7 (the live trunks are migrated).
  - `core/providers/{qwen-coder,openai-compatible-base,pi-bridge,hermes-bridge}` + `claude-code-bridge/*.mjs` + `core/tools/hermes-bridge.ts` → after `@cassicore/ai` (P8) confirms `ai` exports supply qwen/openai-compatible (recon-architecture §9 rec.4). ALSO: `hermes-tools/` (7 MB) is only consumed by the orphaned `core/tools/hermes-bridge.ts`; its removal is **[ASK-USER]** (§8).
- **SAFE-TO-REMOVE anytime in D: (user-executable, ~1.3 GB)** — from recon-debt §2/§10, zero-cost (untracked/ignored), NOT this session's action:
  - `~59.5 MB` logs + `~26.8 MB` webui `.next` `.old`; `~710 MB` tool state (`.serena/cache` 489 MB, `.gitnexus/lbug` 220 MB, `.opencode`, `tmp`, `.cassicore-teams`, `.claude/worktrees`, `.playwright-mcp`); `~530 MB` generated/demo output (`fractals` 57 MB, `webui/.next` 364 MB, claude-code `dist`, `data/training` 58 MB, `data/finetune-*`, `data/dialectic-*`); `data/*.db` (incl. 0-byte tracked `data/memory.db`); `scripts/*.py` (143 untracked, ~1.8 MB — if not migrating them); the `training/cassi/twisted_cord.py` byte-identical duplicate.
- **[ASK-USER]** giants (do NOT touch without confirmation): `vindexes/` 19.5 GB (untracked; runtime loads from `~/.cassicore/models`, but only local copy of weights); `data/distill` 405 MB (untracked research checkpoints); `training/` 1.7 GB nested repo (own history; KEEP/archive/migrate-as-own-unit decision).
- **Workspace-side hygiene (P0):** add `vindexes*/`, `data/distill/`, `training/` to workspace `.gitignore` OR exclude them from plain-copy logic so they never pollute the workspace repo.

---

## 6. Test Strategy

- **Port tests WITH their modules.** Each package gets a `tests/` subdir (mirroring `Constellation/tests/`), carrying the D: test files whose targets that package owns (from `tests/**`, `core/**/__tests__/**`).
- **Quarantine host-wired tests.** Tests that import `core/daemon.ts`, live admin-api route dispatchers, mcp gateway wiring, or other host-only seams go into `tests/host-wired/` with a `test:host-wired` vitest config script (exactly the Constellation precedent: `vitest.host-wired.config.ts` + `"test:host-wired": "vitest run --config vitest.host-wired.config.ts"`). A host-wired test is any whose `describe`/import would fail without a mounted daemon/runtime.
- **Per-phase expected passing counts are ESTIMATED, not promised.** Base estimate per module = the live-target test files that module owns; the host-quarantined remainder is reported, not counted as passing (it is validated at P7 when the host wires everything). Do not inflate — report actual `vitest run` counts with the phase.
- **307 test files total** (≈3,300 KB) across the repo; the per-phase split follows the live-file ownership map. Track ported-vs-quarantined counts in each phase's DONE.
- **Workspace-wide command:** after P7 (and P8 apps), `npm test` green per package; a root aggregate script may run all packages. Do not run project-wide suites mid-phase (workers skip validation per the task contract).

---

## 7. Coordination with the Overhaul Session

**They own (do NOT touch, do NOT copy, do NOT migrate):**
- `mind-plugin/` (the `@cassi-mind` omp extension) and its Stages 1–5 roadmap in `.opencode/plans/cassi-mind-plugin.md`.
- The GPU field engine (`CassiCosmos` Godot sidecar) and the field's loopback TCP 7599 bridge.
- Any `MindFieldEncoder`-style write-gate hooks in `MnemicField.store`, `Thalamus.writeMessageEngram/curate`, `Constellation.insertBranch/appendEvent`, `GlobalWorkspace.submit/broadcast`, and the "SQLite as journal, field as state of truth" transform.

**What migration must NOT touch:** any D: path they are mid-rewiring at the time of a phase; the `core/intelligence/base/registry.ts` discovery contract they depend on for module registration; the `core/plugins` `ExtensionAPI`-shaped client-sdk/plugin-api surface their plugin will consume; `mind-plugin/` (3 untracked files — NOT ours to migrate; if ever needed, plain-copy + `HISTORY: none (untracked)` and only with their sign-off).

**Handshake points:**
- **P4 (mnemic-field):** explicit check before starting. If they are rewiring mnemic-field (journal/hooks), either (a) we land `@cassicore/mnemic-field` first and they add hooks behind our `store` port, or (b) they rewire in D: and we import the rewired shape. **Agree: "package publishes before their rewiring"** is the recommended default (keeps our history import stable), unless they already have uncommitted rewire in that subtree — then swap order. Record the agreed outcome in P4's DONE.
- **P7 (host wiring):** their Stage-N gates target `core/intelligence/*` paths we migrate. Agree the same "package publishes before rewiring" rule so our P7 import doesn't swallow their in-flight edits. If they need to run a Stage gate against a live module we've already extracted, they may consume our package via `npm link` (see below).
- **The two-session rule:** they write to `D:`; we write to `C:\Users\Carina\workspaces\Cassi\CassiCore` (this workspace). **Different repos — no shared working-tree collisions.** The ONLY cross-over: they may consume our published packages via `npm link` (e.g. `@cassicore/foundation`, `@cassicore/mnemic-field`, `@cassicore/plugins`) when their plan needs the extracted boundary. We never write into D:; they consume our artifacts read-only.

---

## 8. Open Questions for the User (defaults recommended — "all defaults" is a valid answer)

1. **D: uncommitted WIP (130 modified tracked files, 0 staged, ~1299 untracked as of scan date [VERIFY]).** Default: **migrate committed-only** — import history from `HEAD` of the temp clone; uncommitted WIP stays in D: (it is the overhaul session's live work). Only if the user commits D: first do we pick that up. (Recommended default: migrated-committed-only; never merge another session's uncommitted edits into our imports.)
2. **Do the P8 standalone apps (ai, cassi-tui, cassi-watch, prism, webui, integrations) move into the workspace as members, or stay in D: consumed via npm link/path?** Default: **move as workspace members**, preserving their own package.json + bin; re-point external installs (opencode plugin symlink, claude hooks) only with explicit confirmation of each external side effect. 
3. **`vindexes/` (19.5 GB untracked), `data/distill` (405 MB untracked), `training/` (1.7 GB nested repo).** Default: **do NOT migrate** any of them; add to workspace `.gitignore`/exclude; leave deletion of D: giants to a separate user decision. (These are unrelated to the code migration.)
4. **When do D: dead files get deleted?** Default: the **phase-gated schedule** in §5's debt scrub — delete each dead set from D: only AFTER that module's migration is verified. This session never deletes in D:; the user/later-phase executor applies it. (Alternative: leave all D: deletions entirely to the user post-migration.)
5. **Constellation retro-history import: yes/no?** Default: **yes** — P0 re-attaches history to the existing `Constellation/` package (plain-copied earlier) via §4.5, both because the user asked to keep git history for copied files and because it validates the existing-copy reconciliation variant early.
6. **P4/P7 ordering vs the overhaul session.** Default: **"package publishes before their rewiring"** applies at both handshakes (P4 mnemic-field, P7 host wiring) — we publish the extracted package, they rewire against our port. If they reveal uncommitted rewire in a subtree we are about to import, we swap order for that module. (Confirm the other session is aligned with this default.)
7. *(Reserved / optional)* Author canonicalization: map historical D: authors (`cassi <cassi@local>`, ephemeral bots) onto the workspace canonical identity `Carina Gardner <bingapplesauce@gmail.com>`, or preserve `cassi` as-is and only collapse the ephemeral bots? Default: collapse ephemeral bots, preserve the 1234-commit `cassi` identity as-is (attribution honesty). [VERIFY]

---

## 9. Definition of Done (whole migration)

- [ ] **Every live subsystem** (857 live source files across the 12 fully-tracked code dirs) is reachable as a `@cassicore/<module>` package, minus explicitly excluded DEAD/UNCERTAIN-quarantined files (recon-data `deadFiles`/`uncertainFiles`).
- [ ] **`foundation` is the single shared substrate** — no module re-vendors `types/*`, `utils/paths`, `config/system-settings`, `phrase-prototypes`, `base/cognitive-module` (only `src/vendor` faithful copies where ported, per MODULARIZATION §c).
- [ ] **Workspace `npm test` is green per package** (ported + host-wired configs registered); no package coerced by skipping its ported tests.
- [ ] **`git log --follow` verifies history for every migrated tracked file** (D: commit dates/authors preserved through filter-repo); every rewrite is a separate commit after its import splice; workspace `git status` clean at each phase end.
- [ ] **D: untouched by migration workers** (read-only discipline held; only temp clones used; no D: git operations by this session; no D: deletions without the §5 schedule + user sign-off).
- [ ] **Seams preserved:** registry auto-discovery contract (or explicit-wiring replacement), `resolveWorker` channel loading (package-relative), admin-api/mcp route+tool contracts, `registerCoreTools` registry — each stated per phase, connected behind ports at P7.
- [ ] **Coordination honored:** P4/P7 handshakes completed with the overhaul session under the agreed "package before rewiring" default; `mind-plugin/` and the overhaul roadmap untouched by migration.
- [ ] **Debt handled, not migrated:** ALL DEAD files (207, ~1.9 MB) stay in D: (or are deleted per §5); workspace contains live code only; the 1.3 GB SAFE-TO-REMOVE cleanup list is handed to the user/executor, not silently ignored.

---

## Appendix A — Quick per-phase one-liners
- **P0** Workspace prep + Constellation retro-history + committed debt exclude-list baseline.
- **P1** `@cassicore/foundation` — live types (19), utils/paths, system-settings, phrase-prototypes, cognitive-module cluster, logger/event shims; shared substrate.
- **P2** `@cassicore/helix` — deepest module; wire real runHelixPipeline into constellation's port.
- **P3** `@cassicore/flux-team` (deprecated blackboard) + `@cassicore/mini-helix`.
- **P4** `@cassicore/mnemic-field` — field substrate; COORDINATION HANDSHAKE with overhaul session before start.
- **P5** remaining intelligence siblings → grouped packages (thalamus, cortex+pineal+dialectic, aurora+self-model, cognitive-feed, reflective, lamina+workspace, trust, embeddings); preserve registry-discovery contract.
- **P6** runtime infra (tools+registry, workflow, model-pool, jobs, events, mcp, plugins, pipeline, utils).
- **P7** entry surfaces (admin-api, mcp-gateway, commands, workers, `@cassicore/host`) — all ports connected.
- **P8** standalone apps (ai, tui, watch, prism, webui, integrations) as workspace members; ASK-USER.
- **Debt scrub** phase-gated D: deletions + SAFE-TO-REMOVE ~1.3 GB list (user-executable).

## Appendix B — [VERIFY] items flagged during planning
1. Exact uncommitted-WIP counts in D: at execution time (130 modified tracked / 1299 untracked at scan; overhaul session is live-editing — never trust stale numbers).
2. Canonical mailmap target for `cassi <cassi@local>` (preserve vs → Carina Gardner) — §8 Q7/§4.7.
3. Location/impl of the in-memory logger/event-bus default shim for foundation P1 (§5-P1).
4. `flux-team` blackboard: import deprecated-but-registered live files vs only GlobalWorkspace successors (§5-P3).
5. `config/distiller` and `dialectic/consolidated` vs `dialectic/index` live entries in P5 (§5-P5).
6. `core/mcp/index.ts` placement (P6 event/pipeline vs P7 gateway) — default: P6 with `core/mcp/*`.
7. Whether any P5 sibling has a live file set not yet enumerated by recon (re-run recon at P5 to close the list).
8. `core/intelligence/helix/helix-tools.ts`, `context-curator.ts`, `backoff.ts`, `session-serializer.ts`, `mnemic-field/{archive-engram-mapper,archive-ingestion-bridge,knowledge/index}`, `cassi-agent/index` — each [UNCERTAIN] must be triaged before its phase (default: quarantine, do not import until a worker resolves intent from the referencing live file).
9. Existing-copy reconciliation applies ONLY to `Constellation/` today (no other package pre-exists) (§4.5).
10. `training/`, `vindexes/`, `data/distill` are excluded by default — confirm no module secretly requires them at runtime (§8 Q3).
