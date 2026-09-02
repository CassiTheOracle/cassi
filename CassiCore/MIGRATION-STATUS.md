# CassiCore Migration Status — FINAL (focused shape)

**Date:** 2026-08-14
**Root:** `packages/*` — **22 retained packages** under `@cassicore/*` (focused mind +
substrate; all standalone-surface / app / bridge packages deleted).
**Source (read-only):** `D:\carina\workspaces\cassicore` (committed `d63358da`)

The P0–P7 modular migration of the CassiCore monorepo is **complete**, ending in the
owner-ratified **focused shape**: a thin ohmypi **spine** extension wrapping the
**mind runtime**, owning the cognitive state while ohmypi owns providers/sessions/tools.
**P6 (2026-08-14, owner-ratified) removed the 4 UI apps + 3 external bridges**;
**P4 (2026-08-14) executed the model-access cutover** (slimmed `@cassicore/model-pool`,
deleted `@cassicore/providers` + `@cassicore/ai`); **P5 (2026-08-14) executed the
sessions cutover + memory backend** — the retained brain + host composition
folded into `@cassicore/mind-runtime`, the admin mind-health read slice folded
into `mind-runtime/src/health`, the mcp-gateway consolidated schemas re-homed
into `@cassicore/tools/schemas`, and the standalone host/session/tool-surface
packages (`host` surface, `pipeline`, `commands`, `workers`, `plugins`, `jobs`,
`mcp`, `admin-api`, `mcp-gateway`) retired; **P7 (2026-08-14) deleted the `host`
empty-shell placeholder**, leaving **22 retained packages**. The zero-import
**focus gate** (`npm run verify:focus`) is the migration's acceptance test and
PASSES. All 22 retained packages typecheck **0 errors** and every retained suite
is green (**2336 tests**).

---

## 1. Packages landed (29 + 2 P3 = 31; P4 deleted providers + ai) — historical landing record

> **Final focused shape (P7):** 22 packages retained. Deleted along the way:
> `providers` + `ai` (P4), `commands`/`workers`/`plugins`/`jobs`/`mcp`/`pipeline`/
> `admin-api`/`mcp-gateway` (P5), `cassi-tui`/`cassi-watch`/`prism`/`webui`/
> `claude-code-mcp`/`hermes-agent-gateway`/`opencode` (P6), and `host` (P7). The
> table below is the migration provenance for every package that was landed
> (including those now deleted); §2 lists the current 22 retained packages.

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
| P3 | `@cassicore/model-pool` | `core/model-pool/*` | ModelPool — **P4 slimmed to retained `ModelHandle` shim + `mind_complete` acquirer** |
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
| P7 | `@cassicore/admin-api` | `core/admin-api.ts` + `core/admin-api/*` | HTTP route registry (55 files) |
| P7 | `@cassicore/mcp-gateway` | `mcp/*` (42 files) | MCP gateway server |
| P7 | `@cassicore/workspace` | `core/workspace/*` | workspace loader/system-prompt |
| P8 | `@cassicore/cassi-tui` | `cassi-tui/` (30) | Ink/React terminal UI (own manifest + bin `cassi`) |
| P8 | `@cassicore/cassi-watch` | `cassi-watch/` (12) | Ink/React watch app (bin `cassicore-watch`) |
| P8 | `@cassicore/prism` | `prism/` (24) | Three.js/WebGL field visualizer (Vite) |
| P8 | `@cassicore/webui` | `webui/` (134) | Next.js portal + `observatory` Vite sub-app (renamed `agent-ui`→`@cassicore/webui`) |
| P8 | `@cassicore/claude-code-mcp` | `integrations/claude-code/` (17) | external-facing bridge — name/bin preserved as-is |
| P8 | `@cassicore/hermes-agent-gateway` | `integrations/hermes-agent/` (17) | external-facing bridge — name/bin preserved as-is |
| P8 | `@cassicore/opencode` | `integrations/opencode/` (3) | bare-file opencode plugin (`cassicore.mjs` + install.sh) |

### 29. `@cassicore/host` — the thin host (turn 4, this phase)

> **DELETED (P7, 2026-08-14).** The host surface migrated here was retired: P5 reduced
> it to an empty-shell placeholder (retained brain moved to `@cassicore/mind-runtime`),
> and P7 deleted the shell (`git rm -r packages/host`). The landing/sub-tree record
> below is kept as provenance.

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

## 1b. Focused runtime (P3) — the spine + mind runtime

P3 (CASSICORE-FOCUS-PLAN §6 P3, DONE 2026-08-14) adds **two new packages** — the
hybrid shape plan §1.1/§4: a thin ohmypi **spine** extension wrapping a host-agnostic
**mind runtime** always-on process.

### 30. `@cassicore/mind-runtime` — the focused always-on cognitive process

The retained composition from `@cassicore/host`'s daemon (plan §5 verdict 26) MINUS
providers/sessions/CLI/ACP/admin-api. Owns `MnemicField` + the retained intelligence
layer (`createIntelligence`), the orchestration bus + unified loop, the retained
mind-tool deps → `registerMindTools` (the P3 retained-mind seam split from
`registerCoreTools`, which is unchanged), and a narrow `127.0.0.1:7273` channel.
Defines the channel-contract types (spine imports them; runtime imports zero ohmypi/spine).

| area | detail |
|---|---|
| `src/boot.ts` | composition root (paths ports, intelligence layer, MnemicField + injections, unified loop, retained tool deps) |
| `src/channel/server.ts` / `protocol.ts` | the 11-endpoint localhost channel (§3.2) + contract types |
| `src/memory/backend.ts` | `MnemicMemoryAdapter` — status/search/save over MnemicField |
| `src/context/candidates.ts` | durable exact-journal drain to CassiFI context observation, counterflow planning, and field ranking; only an `update` carrying distinct persisted before/after revisions becomes a transition, while snapshots and unrelated events produce `no_transition_data`; acknowledgement waits for both provider calls so restart retries cannot skip planning |
| `src/session-store.ts` | `MindSessionMirror` — ohmypi session mirrors |
| `src/run.ts` | `cassi-mind` bin |
| tests | 22 vitest (boot + retained-tools runtime + channel contract + bearer auth) |

The retained brain composition (`createIntelligence` + vendored `core/intelligence/**`)
was relocated OUT of `@cassicore/host` into this package's own `src/vendor/` at P5
(P7 deleted the host shell). Depends ONLY on retained mind packages (no `@cassicore/host`,
no ohmypi, no spine imports); the retained brain composition comes from its local
`src/vendor/core/intelligence/` tree.

### 31. `@cassicore/spine` — the ohmypi extension

The only package that touches ohmypi. Default factory `cassiSpine(pi)`:
- registers the **13 plan §4.2 mind tools** as thin delegates (12 retained:
  `collect_thoughts`, `graph_discover`, `list_sessions`, `list_subagents`,
  `get_subagent_status`, `get_subagent_result`, `system_health`, `debug_session`,
  `universal_search`, `cassandra_query_events`, `cassandra_context_inspect`,
  `query_events` — plus `mind_complete`) with schemas rebuilt from the retained
  `@cassicore/tools` definitions, delegating `{tool, params, sessionId}` to the runtime.
- hidden `[SPINE-TYPES]` seam tools (`_reflect`/`_remember`/`_coordinate`/
  `_check_peers`/`remember`/`memory_search`, `hidden:true, defaultInactive:true`).
- `mind_complete` model-access bridge (§2.3): `ctx.models.resolve` + injectable transport.
- lifecycle `session_start/switch/branch/compact/shutdown` → `/v1/session/mirror` +
  `appendEntry('mind.runtime.state', …)` snapshots; `mcp_notification` → `/v1/events/push`.
- `MnemicMemoryBackend` — memory status/search/save proxying `/v1/memory/*`.
- **`[SPINE-TYPES]` shim** (`src/oh-my-pi-types.ts`): faithful type shim of the pinned
  `@oh-my-pi/pi-coding-agent@17.3.4` surface so CI is self-contained (the real root's
  native allocator fails to load headlessly). Tests stub the `ExtensionAPI` — no live ohmypi.

Tests: 16 vitest (registered-tools, lifecycle-bridge, memory-backend adapter).

**Retained-surface pointer:** the retained mind-tool definitions are re-exported from
`@cassicore/tools` (barrel `implementations/mind-definitions.ts`) for spine schema
fidelity; `registerMindTools` is the P3 retained-mind registration seam
(DELEGATE-SURFACE §1/§4.1). `registerCoreTools` runtime behavior is unchanged.

---

## 2. Test counts per package — the 22 retained packages (all green)

|| package | files | tests |
|---|---|---|---|
|| aurora | 36 | 698 |
|| cognitive-feed | 1 | 97 |
|| constellation | 25 | 568 |
|| cortex-pineal-dialectic | 4 | 143 |
|| dreamer-reverie-subconscious | 8 | 184 |
|| embeddings | — | passWithNoTests |
|| events | — | passWithNoTests |
|| flux-team | 4 | 186 |
|| foundation | 1 | 10 |
|| helix | 9 | 75 |
|| lamina-locus-bridge | 1 | 8 |
|| **mind-runtime** | **4** | **25** |
|| mini-helix | 1 | 21 |
|| mnemic-field | 6 | 89 |
|| model-pool | 1 | 10 (retained-handle/acquire-shim; pool machinery deleted) |
|| **spine** | **3** | **16** |
|| thalamus | 6 | 97 |
|| tools | 3 | 39 |
|| training-trust-ledger | 2 | 53 |
|| utils | — | passWithNoTests |
|| workflow | — | passWithNoTests |
|| workspace | 1 | 17 |

**22 retained packages typecheck 0 errors; all retained suites green (2336 tests).**

> **P7 (2026-08-14) — final focused shape:**
> deleted the `host` empty-shell placeholder (it exported only `HOST_RETIRED=true`;
> nothing imported it; zero-import guard verified before deletion). **Packages
> 23 → 22.** Host was passWithNoTests, so the suite total stays **2336**. The new
> zero-import **focus gate** (`npm run verify:focus`, [[`scripts/verify-focus-gate.mjs`]])
> is the migration's acceptance test: it asserts no retained package statically
> imports `@cassicore/{host,providers,ai,admin-api,mcp-gateway,mcp,pipeline,commands,
> workers,plugins,jobs,cassi-tui,cassi-watch,prism,webui,claude-code-mcp,
> hermes-agent-gateway,opencode}`, nor a bare pre-migration `core/intelligence/` or
> `core/daemon` path, and asserts the mind-runtime/spine dependency contract (mind-runtime
> has no host/spine dep; spine depends on mind-runtime + tools). **PASSES (exit 0).**
>
> **P6 (2026-08-14):** removed the 7 passWithNoTests standalone apps/bridges
> (`cassi-tui`, `cassi-watch`, `prism`, `webui`, `claude-code-mcp`,
> `hermes-agent-gateway`, `opencode`) from the count — deleted per owner
> ratification, history-preserved in git.
>
> **P4 (2026-08-14) model-access cutover — test-gate relaunch:**
> deleted `@cassicore/providers` (120) + `@cassicore/ai` (36) and the
> model-pool pool-machinery suite (32 → 10 retained-handle). **New total:
> 2498 passed (from 2676)** — the only drops are `providers` 120 + `ai` 36 +
> model-pool's 22 pool-machinery tests; every retained suite (helix 75,
> constellation 568, mini-helix 21, host 17, mind-runtime 22, spine 16,
> model-pool 10, admin-api 9, …) is green. The host's provider pool was
> replaced by the retained `mind_complete` acquirer (transitional — completions
> ride the shim until the spine/ohmypi path is live, P5/P6).
>
> **P5 (2026-08-14) sessions cutover — test-gate relaunch:**
> deleted the standalone host surface (`host` → empty-shell placeholder), the
> session/tool-surface packages (`pipeline`, `commands`, `workers`, `plugins`,
> `jobs`, `mcp`, `admin-api`, `mcp-gateway`), and the redundant memory mind
> tools (`_reflect`/`_remember`/`remember`/`memory_search`). The retained brain
> (`createIntelligence` + vendored `core/intelligence/**`) moved into
> `@cassicore/mind-runtime` (`src/vendor/`); the admin mind-health read slice
> folded into `mind-runtime/src/health` (+4 tests); the mcp-gateway consolidated
> schemas re-homed into `@cassicore/tools/schemas`; the pipeline overflow/
> classification helpers moved to `@cassicore/utils`. **New total: 2336 passed
> (from 2498)** — dropped: host 17, admin-api 9, mcp-gateway 40, pipeline 2,
> workers 97, commands/plugins/jobs/mcp passWithNoTests, + the 4 deleted memory
> tools' coverage. Added: mind-runtime health (+4, 22 → 25). Every retained
> suite (helix 75, constellation 568, aurora 698, mnemic-field 89, tools 39,
> spine 16, mind-runtime 25, …) stays green. Zero-import guard clean: no
> retained package imports `@cassicore/pipeline|commands|workers|plugins|jobs|
> mcp|admin-api|mcp-gateway|host`.

### Quarantined to `tests/host-wired/` (excluded from default runs)

Host-wired suites that imported `core/daemon.js` / the deleted host surface. These are
**permanently excluded** from the default runs (and contributed 0 to the 2336 total):
the host/daemon modules they wired against were deleted at P5/P7. Surviving quarantined
host-wired files inside the 22 retained packages (assertions kept UNCHANGED):

| package | files (host-wired, excluded) |
|---|---|
| aurora | 2 |
| constellation | 8 |
| cortex-pineal-dialectic | 2 |
| helix | 1 |
| mnemic-field | 2 |
| thalamus | 2 |
| tools | 6 |

(Former admin-api / mcp-gateway host-wired files vanished with those deleted packages.)

Plus vendored D:-only test files under `src/vendor/**` excluded from the default
run (they test unmigrated D: internals).

---

## 3. Remaining work (P7 closes the migration)

1. **Surface removal & host deletion — DONE.** P6 removed the 4 UI apps + 3 external
   bridges (`cassi-tui`, `cassi-watch`, `prism`, `webui`, `claude-code`,
   `hermes-agent`, `opencode`) per owner ratification; **P7 (2026-08-14) deleted the
   `host` empty-shell placeholder** (22 retained packages). Lockfile regenerated; all
   22 retained suites green (2336 tests); the focus gate (`npm run verify:focus`)
   passes. History preserved in git.
2. **Host-vendor stub re-points — RESOLVED by deletion.** The former tools `vendor/core`
   `{session-store,turn-pipeline,tool-proxy-middleware,workspace-loader,resource-limits}`
   + mcp/tools `vendor/core/version` re-points to `@cassicore/host` are moot: the host
   package is deleted. The retained coding-tool surfaces that referenced those seams
   keep their local in-package vendored copies (the `@cassicore/host ↔ tools|mcp`
   cycle died with the host shell). No further action.
3. **`core/daemon.ts` +87 uncommitted overhaul lines** — reconcile with the D:
   parallel session; re-import if they become canonical.
4. **D: cleanup decisions** — the source repo's 374+ dirty working-tree files
   (live overhaul session + CRLF) are not mine; the owner decides whether to
   commit/sweep them, and whether the mirror (`D:/carina/.cassi-mirror`) is
   retained.
5. **Overhaul handoff points** — the mind-runtime's vendored `createIntelligence`
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

### P8 apps chain (turn 2)

```
aa1bf7dd chore(p8b): scaffold standalone apps — workspace configs + external-bridge notes
a0651c22 import(apps): history from cassicore HEAD@d63358da — 7 standalone apps (237 files)
783b476e refactor(p8b): align 7 apps to workspace members — typecheck 0, coherent lockfile, react-18 types
f08fe091 test(p8b): add passWithNoTests test script to 7 standalone apps
```

**NOTE apps liveness:** recon-architecture §4.3 (external-host adapters) and
§4.4 (path-alias frontends) classify these 7 apps' whole trees as **live**
standalone packages. The `deadFiles`/`uncertainFiles` entries for them
(claude-code 7 D/4 U, hermes-agent 6 D/3 U, webui 85 D/30 U, prism 2 D,
cassi-tui 1 U) are **daemon-anchored import-BFS artifacts** — the daemon doesn't
import them, so BFS marks them dead/uncertain, but they are live external
process entries (webui `@/` alias unresolvable by BFS; integrations launched by
external hosts). Their full tracked trees (237 files) were migrated; only
truly-inert config noise (`eslint.config`, `next.config`, vite config, etc.)
was left where it didn't affect the standalone build/typecheck (webui
`observatory/` excluded from root typecheck only — preserved in-tree).

**NOTE webui react-18 unification:** webui committed `react ^18.3.1` with
`@types/react ^19` (skew). Aligned devDeps to `@types/react ^18` + fixed 8
bare-suffix `.tsx`-dir imports and 2 react-18 ref typings → typecheck 0.
prism pinned `@react-three/postprocessing 3.0.4` (3.0.5 needs three>=0.182 vs
committed ^0.172). Lockfile regenerated to be coherent with the 38 manifests
(the prior lock baked webui as `agent-ui` + react-19/types-19).
