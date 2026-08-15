# Retained Port Surface — P1 (input to P2)

This manifest records the **retained tool/model/mind ports** that survive the
CASSICORE-FOCUS focused-mind migration. It is the P2 input: P2 splits
`model-pool` + `tools` against exactly these seams.

Source of truth: `CASSICORE-FOCUS-PLAN.md` §5 verdicts #19 (model-pool PORT),
#20 (tools SPLIT), §6 P1/P2 rows; `MIGRATION-STATUS.md` §3.2 (the host↔tools|mcp
cycle this phase resolved).

---

## P1 outcome (this phase)

The 6 host-vendored stubs under `packages/{tools,mcp}` were resolved so the
deferred re-point to `@cassicore/host` (which would have created the
`host ↔ tools|mcp` cycle) is no longer needed. **Gate: zero `import ... from
'@cassicore/host'` outside the host package.**

| Stub | Resolution | Where |
|---|---|---|
| `tools/vendor/core/session-store.ts` | **Deleted** → port TYPE `SessionStore`; host injects the real `SessionStore` at boot via `CoreToolDeps.sessionStore` | `tools/src/ports/session-store.ts` |
| `tools/vendor/core/turn-pipeline.ts` | **Deleted** → port TYPE `TurnPipeline`; host injects the real pipeline via `CoreToolDeps.getPipeline` | `tools/src/ports/turn-pipeline.ts` |
| `tools/vendor/core/tool-proxy-middleware.ts` | **Relocated** — never host-owned (host has no counterpart); self-contained pass-through shim moved into tools proper | `tools/src/proxy-middleware.ts` |
| `tools/vendor/core/version.ts` | **Deleted** → constants moved to foundation (substrate-safe; tools+mcp+mcp-gateway already depend on it) | `foundation/src/config/version.ts` |
| `mcp/vendor/core/version.ts` | **Deleted** → same foundation constants | `foundation/src/config/version.ts` |
| `workspace-loader`, `resource-limits` | **Never materialized** — named in §3.2 but no file/symbol exists in tools/mcp/workspace. No action. | — |

The `mcp-gateway/src/vendor/core/version.ts` file is the **live** full version
module (git-describe, `getBuildIdentifier`), NOT a pure-constant stub and
imports no host — intentionally left untouched (out of the named P1 scope;
mcp-gateway is DELEGATE/retained-schemas per §28).

---

## Retained port surface

### Model access — `@cassicore/model-pool` (P2: PORT types + ohmypi-backed shim)

| Symbol | Module | Consumers |
|---|---|---|
| `ModelHandle` | `model-pool/src/types.ts` (§179+, `@cassicore/model-pool`) | `constellation` (constellation-pipeline, meditation/solo-runner), `mini-helix` vendor |
| `ModelCompletionOpts` | `model-pool/src/types.ts` | `mini-helix` vendor (mini-helix-runner) |
| `ModelHandleImpl` | `model-pool/src/model-handle.ts` | retained via model-pool index |

P2 will keep ONLY the `ModelHandle`/`ModelCompletionOpts` types + a shim of
`acquire/release` that produces an ohmypi-backed handle. Budget/billing/
fallback centralized routing is dropped (ohmypi owns routing).

### Tool type system — `@cassicore/tools` (retained as-is)

| Symbol | Module | Consumers |
|---|---|---|
| `ToolDefinition` | `tools/src/types.ts` | helix, constellation, flux-team, mcp-gateway, admin-api, cognitive-feed, host |
| `ToolExecutionContext` | `tools/src/types.ts` | every handler + helix/brainstem types |
| `ToolExecutor` | `tools/src/executor.ts` (class) | host turn-pipeline, mcp, pipeline, providers |
| `ToolRegistry` | `tools/src/registry.ts` (class, `ToolListOptions`) | host, helix, mcp, workflow, pipeline |
| `InteractiveToolSession` | `tools/src/interactive-tool-session.ts` (runtime + `isPrompt`/`extractText`/`splitForTelegram`, type `ParamSchema`/`PromptResult`/`ExecutionResult`/`SessionResult`) | `cognitive-feed` (runtime), `commands` |

### Mind-tool handler deps (retained; registered by the future spine)

| Symbol | Module | Consumers |
|---|---|---|
| `CollectThoughtsDeps` | `tools/src/implementations/collect-thoughts.ts` | `CoreToolDeps.collectThoughtsDeps`; registered via `makeCollectThoughtsHandler` |
| `GraphDiscoverDeps` (+ `setGraphDiscoverDeps` runtime) | `tools/src/implementations/graph-discover.ts` | constellation-pipeline re-points `setGraphDiscoverDeps` at runtime |
| `PeerToolDeps` | `tools/src/implementations/peer-coordination.ts` | `CoreToolDeps.peerToolDeps`; `_coordinate`/`_check_peers` |

### Host-injected seam types (new in P1) — `tools/src/ports/`

| Symbol | Module | Injection |
|---|---|---|
| `SessionStore` | `tools/src/ports/session-store.ts` (interface) | host passes real `SessionStore.open(...)` → `CoreToolDeps.sessionStore` |
| `TurnPipeline` | `tools/src/ports/turn-pipeline.ts` (interface) | host passes `getPipeline: () => this.pipeline` → `CoreToolDeps.getPipeline` |

### Version metadata — `@cassicore/foundation`

| Symbol | Module | Consumers |
|---|---|---|
| `CASSICORE_VERSION`, `CASSICORE_BUILD`, `CASSICORE_BUILD_STRING`, `NEXT_BUMP`, `GIT_REF`, `BUILD_DIRTY`, `GATEWAY_VERSION` + `BuildIdentifier`/`getBuildIdentifier`/`formatBuildId` | `foundation/src/config/version.ts` | tools `hermes-mcp-client` (client-info), mcp `client.ts` (SDK `Client` version) |

Host remains SSOT for the **actual build identity** (`host/src/version.ts`,
git-derived); foundation constants are the static reporting values.

---

## Zero-import guard (verified post-P1)

`grep -rE "import .* from '@cassicore/host'" packages/*/src` → **zero** matches
outside host. Comment-only prose mention appears in
`admin-api/vendor/core/{daemon/version, intelligence/turn-pipeline}.ts` and
`pipeline/vendor/core/workspace/loader.ts` (doc notes about the now-superseded
re-point); none are imports.
