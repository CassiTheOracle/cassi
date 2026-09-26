# Cassi in DeepSeek Harness

## Decision and scope

**Design, source-checked against the installed Harness.** Build a native Cordis integration that makes the continuing Cassi entity available through Harness conversations, a research portfolio, evidence views, and Harness-owned tools. Cassi remains the researcher. Harness supplies its interactive work surface and execution machinery.

The target experience is one Cassi across conversations: discuss a question, attach it to a continuing program, leave the interface, and return to the work and its evidence. A new chat creates a new conversation scope within that lifetime. It does not create another field checkpoint.

At this revision, the first host/client slice exists in [`dsh-cassi-entity/`](dsh-cassi-entity/) with the side-by-side [`dsh-cassi-profile/`](dsh-cassi-profile/) launch manifest. It covers the existing loopback entity routes, the `/cassi` RPC channel, the `cassi-entity` adapter, explicit portfolio/guidance/evidence tools, the core typed-turn lifecycle, and the scoped exact-source bridge. The live Harness execution bridge is exercised through `cassi_list_programs`: the real `ToolRuntime` result is submitted to the entity, the turn continues, and the adapter returns the committed response. The source bridge registers `cassi_read_source` only for configured host roots, returns bounded bytes with full-source and window digests, and sends that exact result through the same typed continuation; the entity retains and interprets it as attributed tool evidence. The dedicated portfolio UI below remains a specified follow-on surface; no installed Harness package, profile, credential, or default model was changed while producing this integration.

The [entity design](../CASSI-ENTITY-DESIGN.md) owns identity and cognition. The [current entity service](cassi_field_brain_server.py), [resident researcher](cassi_autonomous_researcher.py), and [entity implementation](cassi_field_brain_entity.py) define the implemented boundary.

## Installed baseline

| Surface | Inspected state |
|---|---|
| CLI package | `@deepseek-ai/dsh`, version `0.1.1-rc.2` |
| CLI installation | `C:/Users/Carina/AppData/Roaming/npm/node_modules/@deepseek-ai/dsh` |
| Dependency root used by the references below | That directory's `node_modules/@deepseek-ai` |
| User home | `C:/Users/Carina/.dsh` |
| Web profile | Bundles `@deepseek-ai/dsh-base` and `@deepseek-ai/dsh-web-app` |
| Configured web default | `cassi-native-qi`, model `Qwen3.8-27B-Q4_K_M.gguf`, OpenAI-compatible route at `http://127.0.0.1:8084/v1` |
| Observed 8084 backend | Qwen3.5 0.8B Q4_0 at the same route; the configured model label and served artifact do not currently match |
| Other retained route | `cassi-field`, the F5 provider at `http://127.0.0.1:8083/v1` |
| Continuing entity | Loopback-only service at `http://127.0.0.1:8090`, no API credential |
| Entity's active brain | Qwen 3.8 27B Q2_K_XL at `http://127.0.0.1:8085`; SHA-256 `fd4730dd8aad070517978752b63d530aeb1740d2283cab9fa24f1e404032ddb0` |

The two existing Harness provider routes do not connect to the resident entity. The entity has no `/v1/models` or `/v1/chat/completions` route. Pointing the existing OpenAI adapter at port 8090 would fail rather than create this integration.

Keep the installed profile intact. Develop a side-by-side Cassi profile/home, using the same installed CLI, with only the required bundles and the integration package. `DSH_HOME` is an existing supported home override. Do not copy credential databases or start another field owner as part of profile creation.

## Ownership

| Component | Owns | Does not own |
|---|---|---|
| Cassi entity | Adaptive field, commitments, research agenda, retained understanding, scientific interpretation, model work | Browser session state or permission grants |
| Entity's Qwen adapter | Brain requests and their actual outputs, bounded context and generation | A separate persistent learned memory |
| Harness host integration | Identity mapping, loopback transport, delivery cursors, durable execution acknowledgments | Learned ranking, an alternative agenda, direct field writes |
| Harness tool runtime | Tool schemas, execution pipeline, permissions, interactive approvals, cancellation, actual tool outcomes | Scientific conclusions or automatic approval of Cassi requests |
| Harness client | Conversation and portfolio views, steering controls, evidence presentation | Entity API contract or the authoritative research state |

The host may cache a versioned projection for display. Every cached scientific item names its entity revision and source; caches are replaceable from the entity. Session transcripts remain useful records of the interaction, not an alternate adaptive lifetime.

There is one execution owner for each action. A locally executed Cassi read stays local to the entity. A Harness-delegated action is executed only by Harness and returns through the entity's result-admission boundary. Neither side independently retries the other's unknown external effect.

## Runtime shape

```text
Harness browser
  conversation | research portfolio | evidence | approvals
                         |
           Harness host Cordis integration
           /cassi RPC + native Cassi adapter
           session attribution + delivery ledger
               |                         |
       loopback entity API     Harness ToolRuntime
               |                   sandbox / approval / jobs
       one continuing Cassi entity       |
       field owner + research director <- exact tool outcome
               |
       one scheduled Qwen brain lane
```

The package has a host face and a web client face, following the installed `dsh.client` package convention. It registers through public services rather than patching the installed bundle files.

### Host face

The proposed package provides:

- One process-scoped `CassiEntityClient`, configured with the loopback entity URL and no entity API credential.
- A logical `/cassi` RPC channel registered through `ctx.connection.rpc.handle`, restricted to the installed loopback authority policy. Its typed dispatcher exposes only the declared entity operations; it is not an arbitrary URL proxy.
- A native `LlmAdapter` registered as `cassi-entity` for Cassi conversations. The visible model label denotes the continuing entity and separately displays its current brain identity.
- Small explicit tools for querying the portfolio, admitting a program, adding guidance, reading evidence, and requesting a lifecycle change from ordinary Harness sessions.
- When configured with `sourceRoots`, a scoped `cassi_read_source` tool that returns exact bounded bytes, full-source/content SHA-256 digests, and a base64 byte representation through the typed result path.
- An execution bridge for entity work orders, using Harness's real `ToolRuntime`, scoped agent context, and approval service.
- A replaceable portfolio cache and persistent delivery bookkeeping, with no independent learned state.

The entity API is restricted to loopback and accepts requests without an API credential. Keep project and tool scope checks in the host before forwarding requests. A project identifier supplied by model text is never an authorization credential.

### Client face

Use the existing sidebar and conversation slots to provide:

1. **Cassi conversation.** Direct discussion with the continuing entity, with a visible link to the selected project and program.
2. **Research portfolio.** Active, paused, blocked, and completed programs; current question; latest committed finding; evidence links; remaining cycle allowance where available.
3. **Program detail.** Mission, frontier, claims, uncertainties, method, report, actual activity, and the reason work is waiting.
4. **Steering.** Add guidance, pause, resume, cancel, or admit a new mission. Present the distinction between a saved instruction and an acknowledged stop.
5. **Evidence.** Exact artifact identity and bounded content, separated visually from Cassi's interpretation. Render source text inertly.
6. **Approval inbox.** Exact pending target, arguments, scope, and current result. Approval remains Harness's interactive operation.

The portfolio lives outside the per-session projection store. Closing a conversation or compacting its transcript does not erase or stop the entity's programs. Unloading the plugin disconnects its transport and settles its own workers; it does not terminate a separately supervised entity.

## Existing entity API usable immediately

| Operation | Existing route | Relevant behavior |
|---|---|---|
| Inspect | `GET /v1/state`, `/v1/research/status`, `/v1/research/capabilities` | Read-only; capabilities describe the runtime, not a blanket grant |
| Talk to Cassi | `POST /v1/messages` | Takes request, conversation, project, content, and observation time; returns a committed response after inference, despite the HTTP 202 status |
| Admit a mission | `POST /v1/programs` | Durable admission precedes background execution |
| Inspect portfolio | `GET /v1/programs`, `/v1/programs/{id}` | Current field-backed projection |
| Steer | `POST /v1/programs/{id}/guidance` | Owner-retained guidance |
| Control | `POST /v1/programs/{id}/control` | Pause, resume, cancel, complete, or wake |
| Watch a program | `GET /v1/programs/{id}/events?after={sequence}&wait={seconds}` | Bounded SSE batch; wait is capped at 60 seconds |
| Read evidence | `GET /v1/research/artifacts/{sha256}` | Loopback-only immutable bytes |
| Read entity activity | `GET /v1/events?after={cursor}` | Separate entity-journal cursor |
| Typed conversation | `POST /v1/turns`, `GET /v1/turns/{id}`, `GET /v1/turns/{id}/events?after={cursor}`, `POST /v1/turns/{id}/cancel` | Durable accepted/committed/failed/cancelled turn events; duplicate request identities replay without another brain admission; event delivery is cursor-based |
| Typed tool results | `POST /v1/turns/{id}/tool-results` | Validates the turn's operation state and request identity; terminal or mismatched submissions return a typed conflict until the Harness execution bridge supplies a pending operation |

Program event sequences and entity event cursors are different namespaces. Keep separate cursors and deduplicate by event identity. The program stream uses a global research sequence filtered by program, so gaps in one program's sequence are valid.

The host adapter parses the complete SSE batch, delivers it, saves its cursor, then reissues the bounded request. It honors cancellation and backs off on transport failures. Do not assume a permanently open stream, browser `EventSource` credentials, or server support for `Last-Event-ID`. The current route takes `after` explicitly.

The installed Harness mux documents its `since` recovery option as unimplemented. It also has a fixed set of session-oriented frames. Use the generic unary `/cassi` RPC channel for bounded event long-polls rather than pretending the existing mux already carries entity events. A custom RPC channel avoids modifying the core API domain and every generated remote type.

## Cassi conversations in the existing agent loop

The native adapter is the model-facing part of a larger entity integration. Harness's loop remains a transient dispatcher for conversation blocks and tool calls. Cassi owns the cognitive continuation behind that adapter.

The installed `GenerateOptions` includes `sessionId`, messages, system text, tools, an abort signal, and an optional auxiliary-call purpose. It does not provide a stable committed user-event identity by itself. Therefore an adapter that blindly posts the entire message array to `/v1/messages` would learn old turns repeatedly after retries or compaction.

Bind the adapter to a host delivery ledger populated from committed Harness session events:

- Map an explicit installation ID and session ID to one Cassi conversation ID.
- Bind project IDs to approved canonical workspace roots in host configuration.
- Assign each admitted user event a stable request identity derived from its installation, session, and event sequence. Persist the exact payload and observation timestamp before sending it.
- Replay a timed-out mutation with the same identity and exact payload. Changed content requires a new identity.
- Record accepted entity turns and returned message IDs so transcript reconstruction never resubmits them as new experience.
- Treat edited messages, corrections, and explicit research guidance as new versioned events. Do not rewrite accepted history.
- A Harness session fork opens a new conversation scope in the same Cassi lifetime, unless the user explicitly requests an entity fork. It never copies the field.

For a basic conversation, the legacy `/v1/messages` result can still be emitted as a complete text block. The native adapter no longer relies on that route: it submits a typed turn, reads the bounded event batch, and emits the committed response and actual usage. The legacy route cannot supply typed operation identities or cancellation reconciliation.

### Typed conversation lifecycle

The core typed lifecycle is now implemented in the entity service and `cassi-entity` adapter:

| Operation | Current behavior |
|---|---|
| `POST /v1/turns` | Admits one typed user event with the actual tool catalogue, host scope, project, request identity, and current authority; owner admission and one brain attribution produce a committed or failed turn |
| `GET /v1/turns/{id}` | Inspects durable turn disposition after a disconnect |
| `GET /v1/turns/{id}/events?after={cursor}` | Delivers cursor-addressed typed events, including acceptance, commit, failure, and cancellation reconciliation |
| `POST /v1/turns/{id}/tool-results` | Validates exact result identity and turn state, accepts a matching pending Harness-owned operation result, and resumes the typed turn; terminal or mismatched submissions remain typed conflicts |
| `POST /v1/turns/{id}/cancel` | Records a cancellation request and distinguishes a terminal reconciliation from a future in-flight cancellation |

The entity journal persists the turn records and typed events. Repeating the same request identity and exact payload returns the existing disposition without another field admission or brain call. The current adapter consumes the committed event and translates it into the installed `StreamChunk` contract: block start, one complete text delta, block end, actual usage when present, and exactly one terminal finish.

The execution-aware continuation is implemented for the registered Harness tools: the adapter emits a stable tool-call identity, opens the pending entity operation, and accepts the matching actual `ToolRuntime` result before resuming the turn. Two live runs exercise `cassi_list_programs` through this boundary, and the source bridge smoke exercises the same continuation with exact bytes and digests. The host now also exposes a bounded work-order broker when `workOrderTools` is configured: it binds the complete order to a request digest, checks the allowlist and current scope, dispatches through `ctx.tools.execute` with the enclosing parent token, records an fsynced JSONL ledger, and returns an exact terminal outcome.

Where Harness dispatches a conversation tool call, the entity must record that operation as externally owned and must not execute it locally. The next adapter invocation presents the matching actual tool result rather than replaying the prior user message. Each contribution remains attributed to field selection, Qwen generation, or an external executor.

Auxiliary `purpose: compaction` and `purpose: session-title` calls are not user messages. Route them through an explicitly non-learning auxiliary mode using the same scheduled brain, or an explicitly configured Harness helper. They must not create research commitments, self-conversations, or duplicate learning. No fallback to ordinary model-only chat is allowed when the entity is unavailable.

## Research execution through Harness

The current researcher executes its own scoped capabilities. The host now supplies a bounded synchronous work-order seam rather than an HTTP alias for arbitrary shell commands.

The implemented broker:

- accepts only configured `workOrderTools`; the wrapper cannot dispatch itself or any unlisted Harness tool;
- binds entity/program/operation identity, effect class, field predecessor, authority metadata, budget, expected output, and immutable argument content into `cassi.harness.work-order.v1`;
- checks the visible tool in the current agent scope, then uses `ctx.tools.execute` with the enclosing `parent` token so native and Code Mode policy remain authoritative;
- persists `started` and terminal rows to an fsynced JSONL ledger when `workOrderLedgerFile` is configured. A terminal operation replays its exact outcome; a prior `started` row becomes `unknown-effect` and is never automatically re-executed;
- requires an explicit `allowed-once` approval for configured tools and all effect classes outside the host's pre-authorized set. Missing, rejected, cancelled, or malformed approvals fail closed;
- distinguishes `succeeded`, `failed`, `cancelled-before-dispatch`, `unknown-effect`, `scope-denied`, and approval/executor failures. Nested result content and deferred contexts are returned through the normal outer ToolRuntime result.

This first seam is deliberately synchronous and bounded to tools that Harness already owns. It does not claim a background worker lease, progress protocol, portfolio resource accounting, or generated-code containment. Those require a real Harness execution session and an enforceable restricted backend; they remain the next operating increment rather than being simulated by the broker.

Each work order binds entity, program, operation, field predecessor, broker schema version, immutable argument digest, authority reference, budget, and expected result form. Admission checks current source and authority versions before the field interprets the result.

Use `ctx.tools.execute` through the normal policy pipeline, never call a tool's implementation directly. Respect the installed native/code tool-presentation mode; the broker passes the real parent token and advertises only what that scoped executor can dispatch.

A background program still needs a real Harness-owned execution session and an open audited turn. The approval service explicitly rejects idle asks. Build a dedicated execution-turn lifecycle around the installed agent/session facilities before adding leases or unattended work; do not manufacture an `Agent`-shaped object or launch a second autonomous reasoning loop. If no such authorized execution turn or human answerer is available, the bounded work order remains waiting or fails closed.

The configured initial subset should cover scoped reads, searches, artifact construction, and already-authorized computations. Arbitrary generated code remains unavailable until an enforceable containment backend actually restricts filesystem, network, credentials, and child processes. A timeout, Windows process job, or a package named sandbox is not evidence of those restrictions.
### Scoped exact-source reads

`cassi_read_source` is registered only when the host supplies a non-empty `sourceRoots` list. Every requested path is relative, resolves to one regular file under exactly one configured root after real-path containment checks, and fails closed when it is missing, ambiguous, absolute, or outside scope. The source file is bounded to 1 MiB and each returned window to 8 KiB by default. The result carries the root-relative source path, full source SHA-256 and byte length, selected byte range, content SHA-256, base64 bytes, and a UTF-8 presentation for interpretation. A pre-authorized read does not prompt once per file; the host root is the authority boundary. The typed result admission stores the exact result in Cassi's attributed tool evidence before the brain interprets it. `sourceRoots: []` exposes no source-read tool.


### Authority and interactive approval

Carry the exact target and arguments into Harness's tool presentation. Only an explicit `allowed-once` approval outcome authorizes a request that needs confirmation. `rejected`, `cancelled`, and `unavailable` do not.

Provider safety checks always require explicit interactive approval. Consequential actions and high-impact operations retain their point-of-risk confirmation requirements. A mission grant can authorize repeated bounded research reads; it cannot authorize publication, credential access, permission expansion, deletion, or another unrelated external effect by implication.

A loopback entity API is a local-service boundary, not a multi-user authentication system: keep the first integration local to the same trusted user and enforce project/tool scopes in the host. Scoped broker credentials and audience binding are required before enabling less-trusted or remote clients.

## Memory, context, and compaction

The integration stores only identity mappings, delivery records, cursors, immutable result references, and replaceable projections on the Harness side. Do not add an embeddings database, learned relevance cache, or another adaptation layer.

For ordinary non-Cassi Harness sessions that explicitly consult Cassi, the installed `systemPrompt.context` hook can contribute a bounded project snapshot. Its provider is synchronous; refresh the host cache outside prompt assembly and include the source revision and freshness. That context becomes a durable user-role snapshot in Harness, so label it as attributed evidence and never re-admit it as fresh user instruction.

For native Cassi conversations, the entity selects its own relevant memory. The adapter supplies newly admitted events and authorized current execution context rather than treating Harness's entire transcript as the entity's memory.

Harness compaction continues to compress its conversation/execution surface. It does not compact, reset, restore, or own Cassi's field. Recovery reloads the entity projection and pending operation dispositions, then reconstructs only the necessary Harness presentation.

## Scheduling and failure behavior

Use the existing single entity and one primary model lane. Foreground discussion gets timely admission; research proceeds at bounded action boundaries. Interactive priority must not create a second writer or launch another 27B model. Reserve the shared GPU before incompatible simulations.

| Condition | User-visible result and action |
|---|---|
| Entity unavailable | Cassi disconnected; keep the last view visibly stale; do not silently route to ordinary Qwen |
| Brain unavailable or output exhausted | Research retained, exact failure visible, no invented answer or empty successful turn |
| Harness closed | Existing entity-local work continues; Harness-leased work waits or reconciles |
| Browser disconnect | Host transport continues only within its grants; reconnect restores cursor and current state |
| Cancellation during an effect | Stop future dispatch and show pending reconciliation until acknowledged |
| Duplicate delivery | Same durable operation/result; no repeated learning or external execution |
| Scope revoked | Prevent new dispatch and recheck pending work; preserve evidence already gathered |
| Cycle allowance exhausted | Pause with the current frontier intact; resumption does not silently reset accounting |

The current director holds its cycle lock across planning and synthesis, so controls can wait behind inference. The bounded broker does not claim to solve that scheduling boundary: background leases, fair-share resources, quiescent cancellation acknowledgment, and a separately scheduled model lane still require an admitted control queue and real execution-session ownership. Do not advertise instantaneous cancellation for those unimplemented paths.

## Delivery order and acceptance

**Connect the real entity first.** The first host/client slice now connects the real entity through the loopback-scoped `/cassi` RPC channel, explicit portfolio/guidance/evidence tools, and a direct conversation surface. The already-running mission supplies real events; do not replace it with a demonstration field. The dedicated portfolio/evidence panel remains a client follow-on.

**Complete native conversations next.** The core typed turn lifecycle and native adapter are now present: delivery identities, durable event cursors, replay-safe admission, committed usage, terminal cancellation reconciliation, and a live Harness-owned tool continuation. The remaining conversation work is to prove session forks, auxiliary calls, and compaction through the installed host loop.

**Extend Harness execution.** The bounded work-order broker is now present for configured tools: exact identity/digest binding, normal ToolRuntime dispatch, durable replay/recovery, approval fail-closed behavior, scope denial, and cancellation classification are covered by smoke fixtures. The remaining operating depth is background leases, execution-turn ownership for unattended programs, progress/resource accounting, result admission into program evidence, and enforceable containment for generated code.

These are dependency boundaries within one integration design. A portfolio panel alone does not complete the tool-owning conversational integration.

Acceptance uses the actual installed Harness surface and one existing Cassi lifetime:

1. Two chats observe the same program and field lineage while preserving their separate conversation scopes.
2. User guidance changes the real program; reopening a chat retains the accepted guidance and cursor.
3. Replaying the same admitted event and repeating a timed-out request do not cause another learning event or action.
4. A real exact-source read returns through Harness execution into Cassi's evidence and interpretation, with matching bytes/digest.
5. Revoked scope and a missing/rejected interactive answer prevent the actual effect. A source containing apparent instructions cannot change the grant.
6. Interrupting an unsafe execution produces an explicit unknown effect rather than automatic reexecution.
7. Compaction and auxiliary title generation do not create new Cassi messages; session fork does not fork the field.
8. Closing Harness leaves entity-local work intact. Restart reconnects to that same entity, not a new checkpoint.
9. Entity failure stays visible without a hidden provider fallback; browser payloads and logs contain no entity API credentials.
10. The installed original profile remains unchanged and can be launched independently.

## Source index

Installed references are relative to the dependency root in the baseline table. They name inspected public interfaces and implementations, not proposed files.

| Reference | Inspected source and relevance |
|---|---|
| H1 | `dsh-tools/lib/types/index.d.ts`: `ToolDefinition`, `ToolExecutionInput`, `ToolRuntime.register`, `schemas`, `execute`; cancellation and native/code dispatch rules |
| H2 | `dsh-user-approval/lib/types/index.d.ts`: `ApprovalRequest`, `ApprovalService.request`; only `allowed-once` grants and an open turn is required |
| H3 | `dsh-llm/lib/types/index.d.ts`: `LlmAdapter`, `LlmRuntime.registerAdapter`; `dsh-llm/lib/types/types.d.ts`: `StreamChunk`, `GenerateOptions`, auxiliary purpose |
| H4 | `dsh-client-connection/lib/types/rpc.d.ts`: `HostConnectionRpc.handle`, `ClientConnectionRpc.call`, authority policy, unary transport |
| H5 | `dsh-system-prompt/lib/types/index.d.ts`: `PromptContext`, synchronous context provider, `SystemPrompt.context`, `assemble` |
| H6 | `dsh-session/lib/types/index.d.ts` and `types.d.ts`: append-only events, identity, prepare/enter/announce/flush; `dsh-session-projection/lib/types/index.d.ts`: per-session projections |
| H7 | `dsh-compaction/lib/types/index.d.ts`: `CompactionEngine`; `dsh-compaction-basic/lib/types/index.d.ts`: conversation summary lifecycle |
| H8 | `dsh-host-apiproxy/lib/types/api/events.d.ts`: mux frame vocabulary and `since` limitation; `dsh-api-remotes/lib/types/remote-events.d.ts`: fixed forwarded-event list |
| H9 | `dsh-client-ui-jobs/package.json`: host/client exports and `dsh.client`; `dsh-client-ui-conversation/lib/types/client/index.d.ts` and `dsh-client-ui-sidebar/lib/types/client/index.d.ts`: UI extension patterns |
| H10 | `dsh-base/cordis.patch.yml`, `dsh-web-app/cordis.patch.yml`: real service composition; `dsh-home-paths/lib/types/index.d.ts`: `DSH_HOME` resolution |
| C1 | `cassi_field_brain_server.py`: current loopback routes, finite SSE batches, 60-second wait cap, no OpenAI provider routes |
| C2 | `cassi_field_brain_entity.py`: `receive_message`, one owner, attributed response admission, semantic reconstruction |
| C3 | `cassi_autonomous_researcher.py`: field agenda, program lifecycle, operation replay, artifact storage, capability scope and current cycle lock |

The first implementation should be a separately owned package in this workspace, with explicit peer dependencies on the inspected Harness interfaces. Upgrade checks re-read those interfaces; no edits to global `node_modules` are part of deployment.
