# @cassicore/mind-runtime

The **focused CassiCore mind runtime** — the always-on cognitive process that owns
`MnemicField`, the retained intelligence layer, the orchestration loops, and a narrow
`127.0.0.1` channel exposed to the ohmypi **spine** (`@cassicore/spine`).

This package replaces the standalone-daemon surface of `@cassicore/host` (plan §5
verdict 26 — "PORT → replaced by the focused runtime + spine"): it is the retained
composition that builds `MnemicField` + injections, **minus** providers / sessions /
CLI / ACP / admin-api (plan §5 verdicts 22-31).

## Dependency rule

- **Host-agnostic core.** `@cassicore/mind-runtime` imports **zero** ohmypi and **zero**
  spine. It depends only on retained mind packages (`mnemic-field`, `helix`,
  `constellation`, `aurora`, `thalamus`, `flux-team`, `cortex-pineal-dialectic`,
  `mini-helix`, `workflow`, `foundation`, `events`, `utils`, `tools`, `model-pool`) and
  on `@cassicore/host` for the **retained brain composition** (`createIntelligence`,
  `createUnifiedIntelligenceLoop`, `BranchingConversationManager`, `createOrchestrationBus`).
- **Mind-mind boundary.** The runtime *owns* the channel contract (types in
  `src/channel/protocol.ts`, re-exported from the barrel). `@cassicore/spine` imports
  ONLY those types; the runtime never imports the spine.

## Anatomy

| File | Role |
|---|---|
| `src/boot.ts` | **Composition root** — paths ports, `createIntelligence` + module wiring, orchestration bus, `MnemicField` open + injections (meditation/memory/archivist/constellation/cortex), unified loop, retained mind-tool deps → `registerMindTools`. Config read direct from `CASSICORE_HOME` + env (no watcher). |
| `src/channel/server.ts` | `MindChannelServer` — the narrow `127.0.0.1` HTTP/1.1 JSON channel. |
| `src/channel/protocol.ts` | The **channel contract types** (spine imports these). |
| `src/memory/backend.ts` | `MnemicMemoryAdapter` — `status/search/save` over the running `MnemicField` (the ohmypi memory-backend adapter surface, plan §3). |
| `src/session-store.ts` | `MindSessionMirror` — mind-side record of the ohmypi sessions the spine mirrors. |
| `src/run.ts` | `cassi-mind` bin entry. |

## Channel endpoints (`127.0.0.1:7273`)

All `POST /…` JSON except `GET /v1/health`. Auth: loopback-bind + optional `Bearer`
token from `CASSI_MIND_TOKEN`. `requestId` is echoed verbatim.

| Endpoint | Purpose | Request → Response |
|---|---|---|
| `POST /v1/tools/execute` | dispatch a retained mind tool | `{tool, params, sessionId}` → `{ok, result}` \| `{ok:false, error}` |
| `POST /v1/session/mirror` | session lifecycle mirror | `{event, sessionId, cwd?, branchFrom?, summary?}` → `{ack:true}` |
| `POST /v1/events/push` | push harness events (mcp_notification …) | `{type, payload, sessionId}` → `{ack:true}` |
| `POST /v1/snapshot` | mind-state for `appendEntry` | `{}` → `{state}` |
| `POST /v1/health` | verbose liveness | `{}` → `{status, uptimeMs, fieldStats?, lightningStatus?}` |
| `GET /v1/health` | plain liveness | `200 ok` |
| `POST /v1/memory/status` | memory adapter `status()` | `{}` → `{backend, stats}` |
| `POST /v1/memory/search` | memory adapter `search()` | `{query, limit?, type?}` → `{results:[{id,content,score,metadata}]}` |
| `POST /v1/memory/save` | memory adapter `save()` | `{content, type?, metadata?, sessionId?}` → `{id}` |
| `POST /v1/shutdown` | graceful stop | `{}` → `{ok}` |

## Config (brief Open Item 10)

Read direct from env — **no** `Config.load()` / watcher / layered config:

- `CASSICORE_HOME` — data/field home (default `~/.cassicore`).
- `CASSI_MIND_PORT` — channel port (default `7273`).
- `CASSI_MIND_TOKEN` — optional shared bearer token.
- `CASSI_MIND_QUIET=1` — suppress log output (for detached spawn).
- `CASSI_MIND_LIGHTNING` / `CASSI_MIND_RERANKER` — MnemicField mode overrides.

## Model access (P4 boundary)

This phase boots the retained mind with **no live LLM handles** — the daemon's
`setMeditationHandleFactory` / `setCorpusLLMProvider` / `setBrainstemLLMProvider` calls
are P4 cutover (task-agents / `mind_complete`), so provider-facing loops simply never
fire. The retained `ModelHandle` cast seam lives in `@cassicore/model-pool` for P4.

## Tests

Vitest, node environment, `pool: forks` (temp homes + sqlite/lmdb files are per-file).
No live ohmypi / spine. Covers boot smoke (retained core registers retained mind tools,
MnemicField opens, injections wired), the retained mind-tools runtime execution, and
the full channel contract (§3.2) + bearer-token auth.
