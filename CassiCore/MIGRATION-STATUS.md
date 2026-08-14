# CassiCore P7/P8 Migration Status

**Date:** 2026-08-14
**Root:** `packages/*` (31 landed packages under `@cassicore/*`)
**Source (read-only):** `D:\carina\workspaces\cassicore` (committed `d63358da`)

The P0–P8 modular migration of the CassiCore monorepo is **complete**:
foundation through the thin host and the standalone `@cassicore/ai` provider
layer are landed, all 31 packages typecheck **0 errors**, and every package's
test suite is green. This file records the landed surface, count totals,
quarantines, and remaining work.

---

## 1. Packages landed (31)

All migrated with **history-preserving import splices** (two-stage filter-repo
`--path` → `--path-rename`; per-file flags to avoid the Windows fast-import
flush `OSError [Errno 22]`). No mailmap; import merges use
`--allow-unrelated-histories`. Consumers typecheck against built `dist/`.

| phase | package | source (D:) | note |
|---|---|---|---|
| P1 | `@cassicore/foundation` | `core/{config/system-settings, types/, ports/}` | shared substrate + paths port |
| P1 | `@cassicore/events` | `core/{event-bus,logger,events/}` | EventBus/Logger |
| P1 | `@cassicore/utils` | `core/utils/*` | generic utilities (paths excluded → foundation) |
| P2 | `@cassicore/commands` | `core/commands.ts` + `commands/*` | `CommandDispatcher` |
| P2 | `@cassicore/workers` | `workers/*` | channel workers + echo-channel |
| P2 | `@cassicore/plugins` | `core/plugin-*`, `plugins/*` | PluginHost + plugin API |
| P2 | `@cassicore/jobs` | `core/jobs/*` | JobManager |
| P2 | `@cassicore/workflow` | `core/workflow/*` | WorkflowEngine/Registry |
| P3 | `@cassicore/pipeline` | `core/session-pipeline/*`, `core/pipeline/*` | TurnPipeline + SessionPipeline |
| P3 | `@cassicore/mcp` | `core/mcp/*` | MCP client/registry |
| P3 | `@cassicore/model-pool` | `core/model-pool/*` | ModelPool |
| P4 | `@cassicore/mnemic-field` | `core/intelligence/mnemic-field/*` | MnemicField |
| P4 | `@cassicore/cortex-pineal-dialectic` | `core/intelligence/{cortex,dialectic,dmn,pineal}/*` | CPD |
| P4 | `@cassicore/lamina-locus-bridge` | `core/intelligence/{lamina,locus-bridge}/*` | lamina + locus-bridge |
| P4 | `@cassicore/dreamer-reverie-subconscious` | `core/intelligence/{dreamer,reverie,subconscious}/*` | DRS |
| P5 | `@cassicore/aurora` | `core/intelligence/aurora/*` | Aurora cognitive loop |
| P5 | `@cassicore/constellation` | `core/intelligence/constellation/*` | Constellation |
| P5 | `@cassicore/helix` | `core/intelligence/helix/*` | Helix |
| P5 | `@cassicore/flux-team` | `core/intelligence/flux-team/*` | FluxTeam blackboard |
| P5 | `@cassicore/thalamus` | `core/intelligence/thalamus/*` | Thalamus |
| P5 | `@cassicore/embeddings` | `core/intelligence/embeddings/*` | Embeddings |
| P5 | `@cassicore/cognitive-feed` | `core/intelligence/cognitive-feed/*` | Cognitive feed |
| P5 | `@cassicore/mini-helix` | `core/intelligence/mini-helix/*` | Mini-Helix |
| P5 | `@cassicore/training-trust-ledger` | `core/intelligence/{training,trust-ledger}/*` | Training + trust ledger |
| P6 | `@cassicore/tools` | `core/tools/*` | ToolExecutor/ToolRegistry |
| P7 | `@cassicore/providers` | `core/providers/*` (live) | model provider SDK clients |
| P7 | `@cassicore/admin-api` | `core/admin-api.ts` + `core/admin-api/*` | HTTP route registry (55 files) |
| P7 | `@cassicore/mcp-gateway` | `mcp/*` (42 files) | MCP gateway server |
| P7 | `@cassicore/workspace` | `core/workspace/*` | workspace loader/system-prompt |
| P8 | `@cassicore/ai` | `ai/` (46 files, standalone npm pkg) | AI provider layer (self-contained; own package.json) |

### 29. `@cassicore/host` — the thin host (turn 4, this phase)

| source (D:) | dest (host) | note |
|---|---|---|
| `core/entry/*` (5) | `src/entry/` | supervisor, daemon-main, vindex-loader, code-extractor |
| `core/daemon.ts` (166 KB) | `src/daemon.ts` | composition root — (b)-lite: imports + wiring re-pointed only |
| `core/daemon/boot-intelligence-post.ts`, `primary-session-router.ts` | `src/daemon/` | live daemon modules (primary-session-router = the table's 35th file) |
| `core/cli/*` (12) | `src/cli/` | cassicore CLI + runtime |
| `core/bridge/*` (6 live) | `src/bridge/` | ACP (bin/client/server/translator/types) + openai createBridge |
| `core/version.ts` | `src/version.ts` | CASSICORE_VERSION / CASSICORE_BUILD_STRING |
| `scripts/qwen-renew-accounts.ts` | `src/scripts/` | P8 AI deps re-point |
| `bin/{cassicore,cassi-acp}` | `bin/` | launcher scripts (package.json `bin`) |

**Excluded (DEAD):** `core/daemon/{boot-channels,boot-providers,boot-types,channel-loader}.ts`.
**Quarantined (UNCERTAIN):** `core/daemon/{boot-configuration,boot-intelligence-pre,boot-pipeline-tools,intelligence-wiring}.ts`,
`core/bridge/acp/index.ts` — plus D:-only singleton brain files vendored into
`src/vendor/core/` (createIntelligence closure).

**daemon +87 note:** `D:` `core/daemon.ts` carries +87 **UNCOMMITTED** lines
from the live overhaul session. The host import is from **committed `d63358da`**
only; those +87 lines stay OUT (parallel session owns them).

---

## 2. Test counts per package (all green)

| package | files | tests |
|---|---|---|
| admin-api | 2 | 9 |
| **ai** | **1** | **36** |
| aurora | 36 | 698 |
| cognitive-feed | 1 | 97 |
| commands | — | passWithNoTests |
| constellation | 25 | 568 |
| cortex-pineal-dialectic | 4 | 143 |
| dreamer-reverie-subconscious | 8 | 184 |
| embeddings | — | passWithNoTests |
| events | — | passWithNoTests |
| flux-team | 4 | 186 |
| foundation | 1 | 10 |
| helix | 9 | 75 |
| **host** | **2** | **17** (bridge-acp 12 + acp-roundtrip 5; qwen 1 skipped) |
| jobs | — | passWithNoTests |
| lamina-locus-bridge | 1 | 8 |
| mcp | — | passWithNoTests |
| mcp-gateway | 1 | 40 |
| mini-helix | 1 | 21 |
| mnemic-field | 6 | 89 |
| model-pool | 1 | 32 |
| pipeline | 1 | 2 |
| plugins | — | passWithNoTests |
| providers | 5 | 120 |
| thalamus | 6 | 97 |
| tools | 3 | 39 |
| training-trust-ledger | 2 | 53 |
| utils | — | passWithNoTests |
| workers | 2 | 97 |
| workflow | — | passWithNoTests |
| workspace | 1 | 17 |

**All 31 packages typecheck 0 errors; all suites green.**

### Quarantined to `tests/host-wired/` (excluded from default runs)

Host-wired suites that import `core/daemon.js` / wrong-host modules (assertions
kept UNCHANGED; re-pointed imports; house headers):

| package | files (host-wired) |
|---|---|
| admin-api | 3 (`admin-model-api`, `admin-plugin-api` — env-blocked by copilot-sdk ESM; `admin-observability-boot` — daemon.js) |
| aurora | 2 |
| constellation | 8 |
| cortex-pineal-dialectic | 2 |
| helix | 1 |
| mcp-gateway | 1 |
| mnemic-field | 2 |
| providers | 1 |
| thalamus | 2 |
| tools | 6 |

Plus vendored D:-only test files under `src/vendor/**` excluded from the host
default run (they test unmigrated D: internals).

---

## 3. Remaining work

1. **~~P8 `@cassicore/ai`~~ — DONE (this phase).** The whole `ai/` tree landed as
   `@cassicore/ai` (P8, turn 1); **model-pool** and **providers** now depend on
   `@cassicore/ai` and their `src/vendor/{core/ai,ai}` throw-stubs were deleted.
   - `qwen-renew-accounts.ts` (host + admin-api) still imports
     `../vendor/core/ai/src/providers/cassicore/qwen.js` — those faithful
     `QwenProvider` stubs **stay** (host/admin are the runtime and the daemon
     vendor-holds the qwen surface). A later pass can re-point host/admin
     qwen-renew-accounts to `@cassicore/ai` once the daemon's vendored brain is
     slimmed (item 5).
2. **Host-vendor stub re-points (host-turn / P8)** — tools' `vendor/core`
   `{session-store,turn-pipeline,tool-proxy-middleware,workspace-loader,
   resource-limits}` + mcp/tools `vendor/core/version` → `@cassicore/host`
   (host root barrel now exports version/session-store/turn-pipeline so the
   target is resolvable). **Deferred:** these re-points introduce a
   `host ↔ tools|mcp` dependency **cycle** (host already depends on tools/mcp);
   resolve the cycle first (P8 or a dedicated dep-cleaning pass), then re-point
   and delete the stubs.
3. **`core/daemon.ts` +87 uncommitted overhaul lines** — reconcile with the D:
   parallel session; re-import if they become canonical.
4. **D: cleanup decisions** — the source repo's 374+ dirty working-tree files
   (live overhaul session + CRLF) are not mine; the owner decides whether to
   commit/sweep them, and whether the mirror (`D:/carina/.cassi-mirror`) is
   retained.
5. **Overhaul handoff points** — the daemon's vendored `createIntelligence`
   brain closure (`src/vendor/core/intelligence/*`) can be slimmed once the
   overhaul session's field-as-truth transform lands; `mnemic-field`
   `store.onWrite` stays UNOCCUPIED (P4 handshake) until the overhaul encoder.

---

## 4. Commit chains (this phase)

### P7 host chain

```
2a3a9116 chore(p7): scaffold @cassicore/host
69f379ef import(host): history from cassicore HEAD@d63358da
c8f9986c refactor(p7:host): typecheck 0 — daemon import rewiring + vendored brain closure
5eb88aea test(p7): port host bridge tests (17 green)
0073eec0 feat(p7): host wiring matrix — paths ports + package-relative resolveWorker
f48afc62 feat(p7): host root barrel (@cassicore/host resolvable)
b8a6e4d6 fix(p7): host vitest excludes vendored D:-only tests
7a5a5b03 feat(p7): owning-package barrel publishes + trust-ledger exports-map fix
```

### P8 ai chain (turn 1)

```
92c03574 chore(p8): scaffold @cassicore/ai — configs, manifest, deps
a81ea3d4 import(ai): history from cassicore HEAD@d63358da
538a77ae refactor(p8:ai): restore providers/cassicore bodies from own history + fix models.ts generics
26bf30f8 feat(p8): re-point model-pool + providers to @cassicore/ai (delete vendor stubs)
da80d65e test(p8): port ai-model-defaults suite (36 green) + align @cassicore/ai manifest
```

**NOTE providers/cassicore restore:** `ai/src/providers/cassicore/{opencode-go,
alibaba-coding,deepseek,kimi-coding,openrouter,zai,qwen,openai-compatible-base}.
ts` were deleted from the D: tree at `4f06418d` (leaving dangling re-exports in
the barrel + `src/index.ts`). P8 restored all 8 byte-identical from the ai
path's own imported history (`4f06418d^`) — fully self-contained, no D: `core/`
deps — so `@cassicore/ai` typechecks and the providers contract (7 provider
classes + `QwenOAuthCredentials`) is real.
