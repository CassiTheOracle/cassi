# CassiCore — Technical Debt Recon (read-only) for `cassi-mind` Migration

**Repo:** `D:\carina\workspaces\cassicore` · **Scan date:** 2026-08-13
**Purpose:** Inventory old unused files and debt so the `cassi-mind` migration plan can schedule removals. Nothing was deleted or modified.
**Note (history-preservation scope):** The migration will history-import every migrated file. Each entry below therefore flags **tracked** (has git history → history-importable) vs **untracked** (no history → must be plain-copied + noted, or zero-cost to remove). See §9.

---

## 1. Backup / artifact files

`*.bak` `*.patch` `*.orig` `*.old` `*~` `*.tmp` `*.log` — excluding node_modules, .git, vindexes binaries.

### Non-log backups (source-code adjacent)
| File | Size | Tracked? | Ignored? | Verdict |
|---|---|---|---|---|
| `core/intelligence/constellation/constellation-pipeline.ts.bak` | 12,236 B | untracked | yes (`*.bak`) | SAFE-TO-REMOVE (zero cost) |
| `core/intelligence/constellation/constellation-pipeline.ts.patch` | 3,177 B | **tracked** | no | SAFE-TO-REMOVE (stale patch; has history) |
| `packages/larql/nix/patches/use-system-protoc.patch` | 2,392 B | tracked | no | **KEEP** — active Nix build patch (larql's own repo); do not remove |
| `webui/.next/cache/webpack/*/index.pack{.gz,}.old` (4 files) | 26,749,905 B | untracked | yes (`webui/.next/`) | SAFE-TO-REMOVE (build-cache `.old` residue, regenerable) |

### Log files (`*.log`, `logs/`)
All gitignored (`*.log`, `logs/`, `nohup.out`). Total **~59.5 MB (151 files)**.
- Largest single: `data/training/logs/llama-teacher-20260310_062633.log` **51.7 MB**
- `training/cassi/logs/` — ~140 per-run training logs (~7 MB)
- `data/finetune-qwen/training.log` + `training_v2.log`, `phi_garden_sparse13*.log`, `training/cassi/*.log`

All SAFE-TO-REMOVE (no runtime importers; logs are gitignored).

---

## 2. Legacy / abandoned top-level trees

| Path | Size | Tracked | Ignored | Consumers / notes | Verdict |
|---|---|---|---|---|---|
| `hermes-tools/` | 7 MB | 130 tracked | no | Python bridge tooling. **REMOVED-tree candidate** — see §8: only consumer is the **deprecated, orphaned** `core/tools/hermes-bridge.ts` (`../../hermes-tools/bridge.py`). Live path uses `~/.hermes/hermes-agent`, not this repo tree. | **ASK-USER / SAFE-TO-REMOVE** (needs confirmation that `hermes-tools` isn't a manually-operated external repo copy) |
| `integrations/hermes-agent/` | 58 MB (tree) | 17 tracked | no | Live MCP bridge source (Hermes↔CassiCore). Consumed by `registerHermesTools`/thalamus classifier; installed to `~/.hermes/plugins`. Has `AGENTS.md`. | **KEEP** (active integration) |
| `integrations/claude-code/` | includes untracked `dist/` (1 MB, ignored) | 17 tracked | dist ignored | Live Claude Code integration (hook server), referenced by `integrations/claude-code/src/*` and daemon. `dist/` is build output. | **KEEP** (active); `dist/` build output SAFE-TO-REMOVE |
| `integrations/opencode/` | tiny | 3 tracked | no | Live OpenCode integration (`src/cassicore.mjs`, `install.sh`). | **KEEP** (active) |
| `.hermes/` | 1 MB | 12 tracked + 5 untracked | no | `plans/*.md` — 17 historical plan docs (May 2026). Not the live hermes home (`~/.hermes`); repo copy is plan archive. | **ASK-USER** (small historical plans; no code importer) |
| `tmp/` | 0.7 MB | 0 tracked | yes (`tmp/`) | 4 `proxy-request-*.json` probe dumps (May 3). No consumers. | **SAFE-TO-REMOVE** (zero cost) |
| `fractals/` | 57 MB | 0 tracked | yes (`fractals/`) | 16 `.glb` demo exports + `mnemic_galaxy_*.html`, `last_state.json` — fractal visualization renders. No code importer. | **SAFE-TO-REMOVE** (regenerable demo assets); ASK-USER if kept as portfolio |
| `data/` (root, non-workspace code) | 525 MB | 1 tracked (`memory.db`) | mixed | See breakdown below. Not a code dir for migration. | see rows |
| `vindexes/` | **~19.5 GB** | 0 tracked | **no** (untracked) | LARQL/TRELLIS model weights (see §"vindexes detail"). Runtime loads from `~/.cassicore/models` (HOME), **not** this repo tree. Docs pattern `larql serve --dir ./vindexes/`. | **ASK-USER** (huge; only local copy of weights — confirm before removal) |
| `training/` | 1735 MB | 229 tracked (parent) | no | Nested git repo (own `.git`) of 262 Python experiment scripts; idle since 2026-06-13 (2 months). No TS/core importer. Own full history. | **KEEP** (own repo/history) — do not delete in migration; migrate as its own unit; or **ASK-USER** to archive |
| `scripts/*.py` | 2.15 MB (168 files) | **25 tracked / 143 untracked** | no | Standalone Python research/util scripts; no TS importer (`nla_server.py` only mentioned in a comment). | **SAFE-TO-REMOVE** (143 have zero history; 25 tracked have history — remove too, no live importer) |
| `.playwright-mcp/` | tiny | 3 tracked | no | 3 `page-*.yml` Playwright session snapshots (Apr 2026). Tool-generated; no importer. | **SAFE-TO-REMOVE** |
| `.claude/worktrees/` | 0 B (empty) | 0 tracked | no | Empty dir | **SAFE-TO-REMOVE** |
| `.serena/cache/` | **489 MB** | 0 tracked | yes (`.serena/.gitignore:/cache`) | TypeScript project cache, regenerable. | **SAFE-TO-REMOVE** |
| `.gitnexus/` | **220 MB** (`.gitnexus/lbug` 219,949,440 B) | 0 tracked | yes (`.gitnexus`) | Embedded DB from another machine (`meta.json` points `/home/valerie/...`); not tracked, io index. | **SAFE-TO-REMOVE** |
| `.opencode/` | 1 MB | 0 | yes (`.opencode/`) | OpenCode agent runtime state. | **SAFE-TO-REMOVE** (regenerable) |
| `.cassicore-teams/` | 0 B | 0 | yes (`.cassicore-teams/`) | empty team-worktree dir | **SAFE-TO-REMOVE** |
| `mind-plugin/` | <0.1 MB | 0 tracked (3 untracked) | no | Brand-new (2026-08-13) minimal plugin: `package.json`, `src/index.ts`, `src/mind-client.ts`. | **KEEP** — untracked so migration must PLAIN-COPY + note (no history) |

### `data/` breakdown
| Subtree | Size | Ignored? | Verdict |
|---|---|---|---|
| `data/dyad.db`, `helix.db`, `lumen.db` | 0 B each | yes (`data/*.db`) | SAFE-TO-REMOVE (empty, untracked) |
| `data/memory.db` | 0 B | **tracked**, not ignored | SAFE-TO-REMOVE (0-byte empty sqlite committed to git) |
| `data/training/` (incl. `logs/`) | 58 MB | yes (`data/training/`) | SAFE-TO-REMOVE (logs+artifacts) |
| `data/finetune-qwen/` | 19 MB | yes (`data/finetune-*/`) | SAFE-TO-REMOVE (untracked fine-tune scratch) |
| `data/dialectic-training*/` (3 dirs) | 46 MB | yes (`data/dialectic-training*/`) | SAFE-TO-REMOVE |
| `data/distill/` (`models` 393 MB + `cache`) | 405 MB | **no**, untracked | **ASK-USER** — trained distillation model checkpoints; no importer in core, but large research assets |
| `data/*.log` | see §1 | yes | SAFE-TO-REMOVE |

### `vindexes/` detail (`vindexes/trellis2-4b/`)
All **untracked**, root `.gitignore` has NO vindexes rule → appears as `??`. 29 files, ~19.5 GB:
```
hf_weights/ckpts/*.safetensors        5 × ~2.58 GB (slat_flow_img2shape/slatt ... 1_3B bf16)
gate_vectors.bin       1,509,949,440 B
down_weights.bin       1,509,949,440 B
embeddings.bin           201,326,592 B
down_meta.bin              2,211,856 B
+ shape/tex enc & dec safetensors, tokenizer.json, index.json, manifests
```
**Consumers (grep `vindex` in core/):** `core/entry/vindex-loader.ts`, `core/daemon.ts` (loadVindex), `core/daemon/boot-intelligence-post.ts` (tryLoad). RUNTIME loads from `~/.cassicore/models/*.vindex` (HOME dir), **not** this repo `vindexes/`. The repo tree matches the file layout larql expects (`down_weights.bin`, `gate_vectors.bin`) — it is a **staging/export copy**. Verdict **ASK-USER**: confirm no alternate local copy (e.g. `~/.cassicore/models`) before removing 19.5 GB.

---

## 3. Duplicate files (same name)

### True byte-identical duplicate
| Path A | Path B | Size | MD5 |
|---|---|---|---|
| `training/cassi/twisted_cord.py` (Jun 4) | `training/experiments/twisted_cord.py` (Jun 2) | 16,795 B each | **identical** `31b08e09…` |

### Same-name, different-content duplicates (stale/relocated copies candidate)
Tracked source files with identical basenames in different dirs (not `index.ts`/`types.ts`/`config.ts`/`constants.ts` common-module noise):
| Name | Paths (sizes) |
|---|---|
| `cassi-omega.pt` | `training/cassi/checkpoints/cassi-omega.pt` (17,536,579 B, on-disk) ← git tree also lists `training/cassi/cassi-omega.pt` (phantom: **not on disk**) |
| `computeActiveAgents.test.ts` | `core/tests/` (1361 B) vs `tests/core/` (1369 B) — same test duplicated |
| `claustrum-recorder.test.ts` | `core/intelligence/aurora/` (4686 B) vs `tests/unit/aurora/` (5087 B) — duplicated |
| `brainstem-bridge.test.ts` | `tests/` (10054 B) vs `tests/constellation/topology/` (18915 B) — dup name, different fixture |
| `embedding-cache.test.ts` | `tests/` (9635 B) vs `tests/constellation/topology/` (16123 B) — dup |
| `topology-graph.test.ts` | `tests/` (27709 B) vs `tests/constellation/topology/` (34350 B) — dup |
| `event-stream.test.ts` | `tests/ai/utils/` (464 B) vs `tests/subconscious/` (9433 B) — dup |
| `session-store.test.ts` | `tests/` vs `core/intelligence/branching-conversation/` |
| `manager.test.ts` | `core/intelligence/branching-conversation/` (13074) vs `tests/core/intelligence/branching-conversation/` (13649) |
| `blackboard.ts` / `code-store.ts` / `cortex.ts` / `config.ts` / `events.ts` etc. | repeated module name colocations inside `core/` (cross-ref'd by unique import paths — legitimate, NOT dupes) |

**Verdict:** `twisted_cord.py` (identical) is a definite cleanup. The duplicate-named test files are **duplicate coverage** (both import live targets) — flag for consolidation, not blanket removal (the newer `tests/<sub>/` variant is likely authoritative).

---

## 4. Dead test files

All **306** tracked `*.test.ts` were cross-checked by resolving their top-of-file local import target (`.js` specifier → `.ts` source). **0 dead tests found** — every repo-local import target exists on disk.

However, `core/__tests__/hierarchy-bridge.test.ts` imports `../hierarchy-bridge.js` → `core/hierarchy-bridge.ts` exists (2 `as any`), so not dead.

**Non-dead but redundant:** the duplicate-named test files in §3 (both variants live). Recommend keeping the sub-tree variant and deleting the older top-level `tests/<name>.test.ts` copy in the same cleanup as §3 (ASK-USER which is authoritative).

---

## 5. Comment / lint debt counts (per directory)

All counts over **tracked** TS/TSX/JS/MJS/CJS source (1497 files).

### TODO / FIXME / HACK
| Dir | Count | Notes |
|---|---|---|
| `core/intelligence` | 15 | corpus.ts 5, pineal/seed.ts 3, helix/unified-session.ts 3, +1 each |
| `core/tools` | 1 | implementations/cassi-shell.ts |
| `tests` | 2 | workflow-batch-edit, flux-team/blackboard tests |
| `scripts/check-contributing.ts` | (22) | **false positives** — this IS the pre-commit linter that *detects* these tokens; not debt |

**Repo-wide real debt: ~18 TODO/FIXME/HACK** — consistent with the pre-commit hook banning them; essentially clean.

### `@ts-ignore` / `@ts-nocheck`
| Dir | Count |
|---|---|
| `core/intelligence` | 3 |
| `tests` | 5 (github-copilot-loadbalancer 2, reverie 3) |
| `webui/observatory` | 1 |

### `as any`
| Dir | Count |
|---|---|
| **core** | **1357** |
| tests | 930 |
| ai | 35 |
| mcp | 33 |
| commands | 17 |
| scripts | 10 |
| integrations | 9 |
| cassi-tui | 7 |
| webui | 4 |
| cassi-watch | 3 |
| workers | 1 |

Top core `as any` targets: `core/daemon.ts` 86, `core/daemon/boot-intelligence-post.ts` 53, `core/intelligence/helix/helix-posture-runner.ts` 50, `constellation-pipeline.ts` 42, `admin-api.ts` 29, `admin-api/memory.ts` 28, `mnemic-field/index.ts` 26, `helix/helix-pipeline.ts` 25, `context-manager.ts` 24. By core subdir: **intelligence 754, admin-api 163, daemon.ts 86, tools 60, daemon 55**.

---

## 6. Gitignore coverage vs tracked

| Path | Ignored? | Tracked? | Notes |
|---|---|---|---|
| `.opencode/` | **yes** | no | ignored |
| `.hermes/` | **no** | **yes (12)** + 5 untracked | NOT ignored — tracked plan docs |
| `.playwright-mcp/` | **no** | **yes (3)** | NOT ignored, tracked |
| `.serena/cache/` | yes (`.serena/.gitignore:/cache`) | no | ignored by nested .gitignore |
| `.serena/memories/` | yes | no | ignored |
| `.gitnexus` | yes | no | ignored |
| `tmp/` | yes | no | ignored |
| `data/training/`, `data/finetune-*/`, `data/dialectic-training*/`, `data/*.db` | yes | `memory.db` tracked (0-byte) | ignored except memory.db |
| `data/distill/` | **no** | no | **NOT ignored**, untracked 405 MB |
| `fractals/` | yes | no | ignored |
| `vindexes/` | **no** | no | **NOT ignored**, untracked 19.5 GB → shows as `??` in git status |
| `training/` | no | 229 tracked | nested git repo |
| `scripts/` | no | 25 of 168 `.py` tracked | 143 untracked |
| `integrations/claude-code/dist/` | yes (`dist/`) | no | build output |
| `webui/.next/` | yes | no | build output |
| `*.log` / `logs/` / `nohup.out` | yes | no | logs ignored |
| `*.bak` `*.backup` `*.old` | yes | `.patch` NOT ignored | |
| `core/**/*.js` (compiled) | yes | no | TS-source-only tracking |

**Gaps to fix in migration:** `vindexes/` and `data/distill/` are large and NOT gitignored (they'll pollute git status + plain-copy logic); `vindexes/` and `data/distill` should be added to `.gitignore` or removed before migration.

---

## 7. Stale doc drift — samples

- `docs/design/finish-thalamus-migration.md` — migration plan references **`core/intelligence/injection-aggregator.ts` which no longer exists** (module already deleted; doc is stale).
- `core/intelligence/constellation/index.ts:183` — code comment `// REMOVED: Constellation Audit Trail — wrote to FileArtifactStore which is gone.`
- `core/intelligence/flux-team/blackboard-tools.ts` — references removed FileArtifactStore (denominates Flux-team deprecated).
- `core/tools/implementations/universal-search.ts:316` — `// Artifact search removed: FileArtifactStore deleted (cassi://files/ retired)`.
- `docs/design/aurora-*.md` — design docs describing vindex/claustrum features whose runtime paths were replaced by the deferred `~/.cassicore/models` loader (behavior drift, not hard deletion).

No literal `FileArtifactStore` string under `docs/`; the drift lives in design docs vs removed code, and `finish-thalamus-migration.md` is the clearest doc→deleted-module reference.

---

## 8. Hermes wiring status (core → hermes)

**Verdict: Hermes tool bridge is LIVE in the daemon via MCP; the repo `hermes-tools/` tree is only consumed by a deprecated, orphaned module.**

Live hermes import sites (core, excluding `integrations/`):
| Core file | Imports / use | Status |
|---|---|---|
| `core/daemon.ts` | `registerHermesTools` from `./tools/hermes-tools.js`; `getHermesMcpClient`/`shutdownHermesMcpClient` from `./tools/hermes-mcp-client.js` | **LIVE** |
| `core/tools/hermes-tools.ts` | delegates to `hermes-mcp-client.js` | **LIVE** |
| `core/tools/hermes-mcp-client.ts` | spawns `~/.hermes/hermes-agent` (HOME), MCP JSON-RPC | **LIVE** (active path) |
| `core/intelligence/thalamus/classifier.ts` | maps `hermes_sessions_*`, `hermes_context_*`, `hermes_memory_*`, `hermes_cognitive_*` tools | **LIVE** |
| `core/providers/hermes-bridge.ts` | `HermesBridgeProvider` / `getHermesBridgeProvider` | **ORPHANED** — no importer; only defs (daemon's provider map built via `providers/index.ts`, which never instantiates it) |
| `core/tools/hermes-bridge.ts` | `../../hermes-tools/bridge.py` | **ORPHANED + DEPRECATED** (header: "replaced by hermes-mcp-client.ts… will be removed") — not imported anywhere |

**Reclaims only `core/tools/hermes-bridge.ts` (deprecated, orphaned) and `core/providers/hermes-bridge.ts` (orphaned) are dead and safe to remove.** They are the ONLY consumers of repo `hermes-tools/`.
- `system-settings.ts` `MODEL_DIRECTIVE_TIER_DEFAULTS` uses `provider: 'hermes'` but is itself unused (no consumer found) — nominal leftover.
- Live bridge reads **`~/.hermes` (HOME)** — the repo `hermes-tools/` and `.hermes/` are NOT the runtime hermes install.
- **Do NOT remove** `core/tools/hermes-mcp-client.ts`, `hermes-tools.ts`, or the `hermes_*` classifier mappings.

---

## 9. Tracked vs untracked per code directory (for history-preserving import)

`git status --porcelain` + `git ls-files --others --exclude-standard` for each migration-scoped dir.

| Code dir | Tracked | **Untracked (`??`)** | History-preservation note |
|---|---|---|---|
| `core/` | 879 | **0** | fully history-importable |
| `types/` | 25 | **0** | |
| `workers/` | 8 | **0** | |
| `mcp/` | 42 | **0** | |
| `commands/` | 8 | **0** | |
| `integrations/` | 37 | **0** | |
| `packages/larql/` | 1 (gitlink, mode 160000, commit `d45ebfd`) | 0 in parent | **nested git repo** (own `.git`, own commits, no `.gitmodules`) → migrate **from its own repo history**, not the parent |
| `cassi-tui/` | 30 | **0** | |
| `webui/` | 134 | **0** | |
| `prism/` | 24 | **0** | |
| `ai/` | 46 | **0** | |
| `cassi-watch/` | 12 | **0** | |

**All twelve code directories are 100% tracked — zero untracked files.** History-import can carry every migrated code file.

Near-code dirs that ARE partially/fully untracked (affect the plan's copy logic):
| Dir | untracked | note |
|---|---|---|
| `scripts/` | **143** of 168 `.py` | only 25 tracked → 143 need plain-copy + note (or removal, §2) |
| `docs/` | **7** of 65 (cassi-findings, cassi-ml-and-cord, cassi-principle, cassi-three-problems, distillation-design, student-model-plan, vulkan-compute-plan) | no history → plain-copy + note |
| `mind-plugin/` | **3 of 3** (package.json, src/index.ts, src/mind-client.ts) | no history → plain-copy + note |
| `.hermes/` | 5 plan docs | no history |
| `training/` | 228 (parent view) but own nested repo | migrate as own unit |
| `vindexes/`, `data/`, `fractals/`, `tmp/`, `.gitnexus/` | all untracked | not code dirs → generally removal candidates |

---

## Reclaimable totals by category

| Category | Reclaimable | History cost |
|---|---|---|
| **1. Backup/artifacts + logs** | ~**59.5 MB** (logs) + ~26.8 MB (webui .next `.old`) + tiny `.bak/.patch` | ~0 (mostly untracked/ignored; `.patch` tracked) |
| **2a. Tool caches/state (`.serena/cache`, `.gitnexus`, `.opencode`, `tmp`, `.cassicore-teams`, `.claude/worktrees`, `.playwright-mcp`)** | ~**710 MB** | zero (all untracked/ignored) |
| **2b. Generated/demo output (`fractals`, `webui/.next`, claude-code `dist`, `data/training`, `data/finetune-*`, `data/dialectic-*`)** | ~**530 MB** | zero (untracked/ignored) |
| **2c. `data/` 0-byte dbs + empty trees** | ~0 | `memory.db` tracked |
| **2d. `scripts/*.py` (143 untracked)** | ~**1.8 MB** | zero (untracked) |
| **2e. `vindexes/`** | ~**19.5 GB** | zero (untracked) — ASK-USER |
| **2f. `data/distill`** | ~**405 MB** | zero — ASK-USER |
| **3. `twisted_cord.py` duplicate** | ~16.8 KB | tracked (both copies) |
| **4. Duplicate-named test files** | ~150 KB | tracked, both live — ASK-USER |
| **5. `core/tools/hermes-bridge.ts` + `core/providers/hermes-bridge.ts`** | ~24 KB + `hermes-tools/` 7 MB | tracked |
| **6. `docs/` drift** | n/a (doc edits, not removal) | tracked |

**Grand total confidently SAFE-TO-REMOVE: ≈ 1,302 MB (~1.3 GB)** excluding the two ASK-USER giants.
**With `vindexes/` (19.5 GB) + `data/distill` (405 MB) if user OKays: ≈ 21.2 GB.**

Top 10 largest individual debt items:
1. `vindexes/` (untracked TRELLIS/LARQL weights) — **~19.5 GB** — ASK-USER
2. `training/` nested repo artifacts (logs+checkpoints, own history) — 1735 MB — KEEP/ASK-USER
3. `.serena/cache/typescript` — **489 MB** — SAFE
4. `webui/.next` build cache — 364 MB — SAFE
5. `data/distill/models` — 393 MB — ASK-USER
6. `.gitnexus/lbug` — **220 MB** — SAFE
7. `data/training/` (+logs) — 58 MB — SAFE
8. `fractals/` GLB demos — 57 MB — SAFE
9. `integrations/claude-code/dist/` — 1 MB — SAFE
10. `data/finetune-qwen/` + `data/dialectic-*` — 65 MB — SAFE

---

## Rules honored
- **KEEP** everything with a live importer: `integrations/*` (active), `core/tools/hermes-mcp-client.ts` / `hermes-tools.ts` (live daemon wiring), `packages/larql/nix/patches/use-system-protoc.patch` (active Nix build), `mind-plugin/` (new), all `core/` code.
- **Untracked live files** (scripts/*.py, mind-plugin, docs/*) are flagged with the plain-copy+note requirement in §9 — removing an untracked file has **zero** migration cost.
- Nothing was deleted or modified; `.recon-tmp` scratch dir removed after use.
