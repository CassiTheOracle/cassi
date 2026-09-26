# CassiPi

CassiPi makes the Cassi field the sole owner of an Oh My Pi agent’s usable context. Oh My Pi still runs the model, tools, permissions, session files, and interface. CassiPi records the agent’s evidence in the canonical CassiFI runtime, asks the field which exact sources fit the next request, and gives only that bounded projection to the provider.

This is a private, pinned integration. It does not add a second memory database, semantic ranker, embedding index, or shadow learned state.

## Compatibility

The supported host is exactly:

- `@oh-my-pi/pi-coding-agent` 18.1.10;
- upstream commit `f241301c83726afe75a847e919b89977a54dafbe`;
- the patch in `host/patches/oh-my-pi-18.1.10-context-owner.patch`;
- the canonical FI runtime identified by `fi-runtime/runtime-manifest.json`.

Stock Oh My Pi 18.1.10 cannot enforce exclusive context ownership. CassiPi therefore fails closed on the stock host rather than falling back to native compaction or another context mutator. The compatible binary is built separately and never replaces the installed `omp.exe`.

The context-owner patch is carried against 18.1.10 only. Upstream 18.3.2 changed the session, compaction, and provider paths the patch rewrites, so `cassipi` stays on the pinned host while ordinary `omp` keeps advancing; a later port re-derives the patch against the newer upstream and repeats the release and probe verification.

The packaged host is supported and measured on Windows 11 x64. Other operating systems and host builds are not declared compatible by this release.

## What owns what

- Oh My Pi owns model/provider calls, tools, approvals, transcripts, and UI.
- The patched host exposes one singleton `context.owner` seam and routes provider context, compaction, handoff, tree movement, branching, and session identity changes through it.
- The CassiPi extension is the one host adapter, one `cassi_memory` tool, and one `/cassi` command.
- The packaged Python worker delegates exact evidence, adaptive state, checkpoints, and field queries to the current CassiFI `FieldIntelligenceOwner`. Its thin CassiPi adapter owns only host bindings, lifecycle markers, projections, and the RPC boundary.
- Source bytes remain in CassiFI's bounded exact-evidence store. Atlas checkpoints contain the numeric field and source revision identities, never unbounded transcript text or a second learned text model.

The worker listens only on loopback, authenticates every request with a per-launch bearer secret and a per-scope token, rejects incompatible runtime identities, and allows one process owner per data directory.

Every provider request carries the host's fixed overhead (system prompt plus tool catalog, about 22k tokens), the owner's field-selected evidence, the protected pending turn, and the output reserve; native history is never sent. The evidence bound is `CASSIPI_MAX_EVIDENCE_TOKENS`, 16,384 tokens by default. Compaction rewrites the stored session to a bounded field projection (`compactionTokenBudget`, at most 4,096 tokens) instead of a provider-generated summary, so it costs no provider call and keeps the original sources exactly recallable.

One entry whose canonical bytes exceed 640 KiB cannot travel inside the worker's 1 MiB request envelope as a single exact source. The extension skips that entry, warns once, and counts it under `observation_skips` in `/cassi status`; the entry stays in the Oh My Pi transcript and the turn continues. Across the two largest local sessions, 15 of 50,295 entries (0.03%) exceeded 700 KiB.

Observation cost is bounded by the observation, not by accumulated evidence. The control ledger records one head checkpoint per stored key, and validating that ledger once reconstructed the whole atlas state for every recorded head on every save, so a long-lived field paid a full state decode per stored source. Each recorded head is now verified once per retention floor: checkpoint manifests and their pages are immutable content-addressed objects, and history compaction publishes the floor before it deletes anything, so a head verified under the current floor stays readable until the floor moves.

On a real 300-entry compaction segment (260,322 raw tokens) the observation phase fell from 571 s to 22 s across repeated runs, which is 72–74 ms per entry, with identical field state, checkpoint manifest, and control ledger bytes. Three walks of accumulated evidence went with it: a capacity check reads a total maintained as evidence files are written and removed, a head that names the checkpoint the owner already holds is not decoded a second time, and identity and digest validation answers once per distinct value instead of once per index access. Per-observation latency now measures flat across the segment — 33–36 ms in process from 100 to 300 stored entries, where the same replay without the value cache climbed from 33 ms to 46 ms. What remains is the commit's own state encoding and its durability writes. Receipts: `probes/receipts/real-session-projection.json` and `probes/receipts/real-session-projection-prior-runtime.json`.

The covariance validation in the variational field keeps its direct factorization only when the smallest eigenvalue sits inside the decomposition's own accuracy band. The spectral-bounds check already pins every eigenvalue between `ridge - tolerance` and `upper + tolerance`, so outside that band the factorization cannot reject anything and its threaded LAPACK dispatch is pure overhead; measured per-observation latency is unchanged in the typical case, and the check still runs whenever the spectrum cannot decide the sign.

The launcher overlay keeps the host's compaction threshold clear of the floor the host cannot summarize: its own system prompt and tool catalog (about 22k tokens on the pinned host) plus the field summary the owner writes (about 4k tokens). A threshold at that floor makes the host compact, find nothing left to summarize, and drop the pending turn without reporting an error, so the installer writes `compaction.thresholdTokens: 60000` and the owner probe keeps the same headroom. The threshold bounds the stored transcript, not what the provider sees: every request carries the field projection, and the host appends a field summary plus the kept tail to the session file, so raising or lowering it changes rewrite frequency and on-disk detail rather than the model's context.

## Build the private artifacts

Prerequisites are Bun 1.3.14 or newer, Node 20 or newer, npm, Python 3.12, the installed CassiFI environment, and the pinned host checkouts under `.host-work/`.

```text
npm install
npm run package:runtime
bun .host-work/patched/packages/coding-agent/scripts/build-binary.ts
npm run package:release
```

`package:runtime` rebuilds `fi-runtime/` from the CassiFI-owned closure and verifies every file before atomically replacing the old package. `package:release` verifies the runtime, confirms that the host patch applies to the pinned upstream commit, packages only the explicit plugin/runtime allowlist, and writes these ignored artifacts to `dist/`:

- the private CassiPi npm archive;
- the verified runtime manifest;
- the exact host pin and patch;
- the compatible Windows x64 host binary;
- `release-manifest.json`, containing every artifact hash and compatibility identity.

No evidence store, imported memory, session transcript, runtime descriptor, bearer secret, test fixture, `.probe` directory, or `.host-work` checkout is included. The verified runtime closure contains 73 allowlisted Python files: the current CassiFI field, atlas, cognition, owner, learning computer, regional and program runtimes, resident hive, affect, communication, temporal, and transceiver capabilities, and the loopback worker. It contains no trained checkpoint, corpus, tokenizer, embedding model, or legacy Qi runtime.

## Install into a separate profile

Create the official isolated rehearsal profile without touching the normal profile:

```text
python scripts/install_rehearsal.py
```

The installer verifies the release hashes, installs the package through Oh My Pi’s plugin manager under `~/.omp/profiles/cassipi-rehearsal`, and sets `context.owner` to `cassipi` only in that profile. It also disables the first-run provider wizard and startup splash only in the isolated profile; it does not copy, select, or authenticate any provider. Re-running with `--reuse` is the upgrade rehearsal:

```text
python scripts/install_rehearsal.py --reuse
```

For every named profile, the generated launcher binds `CASSIPI_PROFILE_ID=omp-profile:<name>`, `CASSIPI_DATA_HOME=<profile-root>/cassipi`, and `CASSIPI_FI_RUNTIME=<profile-root>/local-plugins/cassipi/fi-runtime`. It also clears `PI_PROFILE` and `PI_CODING_AGENT_DIR`, so a named profile cannot silently reuse the default OMP profile or another CassiPi field lineage.

The installer writes and reads back the exclusive owner profile: stock memory and autolearn are off; native compaction is limited to the owner-routed `soft` entry point; asynchronous, automatic-continuation, idle, useless-drop, and superseded-read paths are off; legal mid-turn ownership remains on. It does not copy authentication, sessions, databases, or plugin state from another profile.

Install against the active main profile with:

```text
python scripts/install_rehearsal.py --main --reuse
```

Main-profile installation keeps the existing agent configuration and credential databases unchanged, enforces byte-identical `~/.omp/agent/config.yml` before and after installation, and records both hashes in the receipt. The `cassipi` launcher uses that configuration as its base, binds its field under `~/.omp/cassipi`, loads the pinned host and CassiPi extension explicitly, and applies the complete exclusive-owner configuration through `~/.omp/cassipi-owner.json`. That overlay turns stock memory/autolearn off and configures the owner-routed 60,000/4,000/64-token compaction boundary only inside `cassipi`. The global CassiPi registry entry remains disabled, while ordinary upstream `omp` retains the user’s Mnemopi, autolearn, compaction, and enabled `remote-pi…

Use `--profile <name>` for another isolated named profile. Launch the rehearsal profile through its copied compatible host and profile-scoped launcher:

```text
C:\Users\Carina\.omp\profiles\cassipi-rehearsal\launch-cassipi.cmd
```

`C:\Users\Carina\.bun\bin\cassipi.cmd` is the short command for the active-profile installation. `omp` currently uses the ordinary installed Oh My Pi 18.3.2 host with enabled `remote-pi`; `cassipi` uses the independently pinned Oh My Pi 18.1.10 host with global extensions disabled and CassiPi loaded explicitly. The two commands share the active profile’s model roles, provider credentials, presentation settings, and task configuration, but only `cassipi` activates exclusive field ownership.

Verify the isolated installed artifact with `npm run probe:installed`. Verify the named profile’s actual launcher and persistent data home with an owner-RPC status check, then verify both active-profile launch paths without an external provider:

```text
bun run scripts/probe-cassipi-owner.ts --installed-profile cassipi-rehearsal --live-profile-status
bun run scripts/probe-cassipi-owner.ts --installed-root C:/Users/Carina/.omp --launcher-only
npm run probe:ordinary
```

Do not launch the owner extension with stock `omp.exe`; use `cassipi`.

## Memory controls

The model sees one approval-gated tool, `cassi_memory`, with these actions:

- `recall`: field-selected evidence, optionally pinned by an exact revision ID;
- `remember`: add an exact user-declared source at task, branch, project, or profile scope;
- `correct`: add a replacement revision linked to the exact superseded revision;
- `forget`: preview only; model/tool arguments can never authorize deletion;
- `inspect`: read state, pending operations, a source identity, or a bounded projection.

Direct user controls use the one `/cassi` command:

```text
/cassi status
/cassi inspect state
/cassi inspect source project <64-character-revision-id>
/cassi remember project Use the compatible CassiPi profile for this project.
/cassi correct project <64-character-revision-id> Use the corrected statement.
/cassi forget project <64-character-revision-id>
/cassi pause
/cassi resume
/cassi recovery
/cassi computer <action> <json-object>
```

The computer surface is deliberately host-controlled and remains inside `/cassi`, not a second model-callable tool. It drives the resident regional computer of the current CassiFI runtime:

```text
/cassi computer configure {"arguments":{"resident_pages":8}}
/cassi computer advance {"arguments":{"steps":4}}
/cassi computer submit {"arguments":{"kernel":"python","state":{...}}}
/cassi computer resources {}
/cassi computer residency {}
/cassi computer circulation {}
```

`<action>` is one of the runtime's canonical actions (`configure`, `load`, `advance`, `submit`, `call`, `cancel-call`, `invoke`, `invoke-settled`, `authorized-invoke`, `restart`, `grow`, `solve`, `continue-solve`, `residency`, `circulation`, `communicate`, `cancel-communication`, `resources`, `adopt-paged`, `bind-method-inputs`, `place`, `enable-ngram`, `learn-ngram`). Each action has an exact set of required and optional argument keys, and any other key is rejected. The command is bound to the authenticated host scope; mutating actions carry a deterministic operation ID so a repeated identical command replays instead of executing twice; the read-only `resources`, `residency`, and `circulation` actions carry none. Command results are echoed as the runtime's own bounded receipts. Proposed actions remain proposals; field state never bypasses Oh My Pi execution approval.

`/cassi forget` first shows the exact revision closure and external-copy limits. Nothing changes if confirmation is declined. Approval mints a hidden, one-use, short-lived token; the worker revokes the approved revisions, removes their managed exact bytes and field contributions, publishes a verified successor checkpoint, and verifies that they cannot be projected or exactly recalled. Oh My Pi transcripts and external backups are reported as external copies and are not silently claimed as erased.

`/cassi pause` persists capture state across worker and host restarts. While paused, context ownership remains fail-closed and write operations are rejected. `/cassi status` reports readiness, authenticated scope, runtime and manifest identities, field/journal/checkpoint heads, capture state, the latest projection accounting, the current provider-context receipt, and startup recovery status. If the worker is unavailable, status reports an explicit unavailable state rather than implying native fallback.

## Migration

The current runtime no longer packages or dispatches the read-only predecessor importer. `CassiFI/runtime/test_cassipi_worker.py` pins that absence: importing `cassi_cassipi_import` from the built runtime must fail, and operations the worker does not implement are rejected as `UNSUPPORTED_OPERATION`. `CassiFI/runtime/cassi_cassipi_import.py` still exists in CassiFI’s own tree with its adapter tests, but it is not part of the shipped runtime closure and CassiPi no longer exposes it through `/cassi`.

Moving predecessor memory into a live field is an explicit CassiFI-side operation, not part of the CassiPi host surface. The cutover does not load prototype Qi checkpoints or earlier CassiPi adaptive sidecars; nothing on the predecessor side is treated as current field intelligence.

## Recovery and rollback

1. Stop the isolated CassiPi host normally so the worker can detach and checkpoint.
2. Run `/cassi status`; compare the runtime, manifest, field, evidence, and checkpoint identities with the last receipt.
3. Run `/cassi recovery` to reconcile a prepared native transition after interruption.
4. If the worker crashed, retry status once; the client discards an unreachable descriptor and the single-owner worker recovers from CassiFI's exact-evidence store, checkpoint chain, and CassiPi control ledger.
5. If the runtime or host identity changed, stop. Rebuild the pinned artifacts or restore a prior private release with `python scripts/install_rehearsal.py --profile <profile-name> --release C:\path\to\previous-dist --reuse`. Re-run `npm run probe:installed`; never allow stock host compaction as a fallback.
6. Rollback is profile-local: exit the CassiPi profile and launch the prior profile with its prior host. Reapplying the newer release uses the same installer command without `--release`. Keep the CassiPi data directory intact until its rollback receipt and any external-copy obligations have been reviewed.

## Verification

Focused local verification does not call an external provider:

```text
npm run typecheck
npm test
npm run verify:release-host
npm run package:runtime
npm run probe:field-control
npm run probe:owner
npm run probe:ordinary
npm run measure:integration
python scripts/measure_real_session.py --max-messages 800
python scripts/measure_stock_compaction.py
python -m pytest ../CassiFI/test_field_intelligence.py ../CassiFI/runtime/test_cassipi_worker.py ../CassiFI/runtime/test_cassipi_runtime_package.py ../CassiFI/runtime/test_cassipi_forget_generation.py ../CassiFI/runtime/test_packaged_learning_computer.py ../CassiFI/runtime/test_cassipi_import.py -q
bun test ./.host-work/patched/packages/coding-agent/test/extensions-runner.test.ts ./.host-work/patched/packages/coding-agent/test/agent-session-handoff.test.ts ./.host-work/patched/packages/coding-agent/test/agent-session-prune-persistence.test.ts
bun --cwd=.host-work/patched/packages/coding-agent run check:types
```

`verify:release-host` hashes both the patched 18.1.10 executable and `oh-my-pi-18.1.10-context-owner.patch`, compares those bytes with the generated private-release manifest, recomputes the patched-source identity from the verified patch hash and upstream commit, and executes the patched host's `--version` path. The installer independently performs the same binary, patch, and patched-source identity checks before mutating a profile and records the accepted identities in its receipt. The separate historical `verify:host-pin` command checks the original unpatched `omp/18.1.10` binary identity and therefore requires that stock binary to be supplied or restored; the ordinary installation has since advanced past 18.1.10 and is deliberately not downgraded.

Set `CASSIPI_TRACE_FILE` to a writable path to record every owner operation and context-owner hook invocation as JSON lines. A turn that produces no provider request leaves no other trace, so this is how an owner-side wait is separated from a host-side one.

`probe:field-control`, `probe:owner`, and `measure:integration` use the locally packaged runtime, isolated data, and no external provider. The field-control probe verifies the adapter's control schema, intentional field advancement during query-time `think`, exact reopen identity before replay, source-backed message stability, and temporal state persistence across adapter restart. The owner probe runs the actual patched host against a local mock provider and exercises the host-controlled computer command surface, field-selected prior evidence, repeated manual compaction, summarized and unsummarized tree movement, handoff, branch creation, new/resumed sessions, persistent owner markers, and clean worker shutdown.

`measure_stock_compaction.py` accounts for the host's own compaction over the local session store, and `measure_real_session.py` replays a real session's compaction segment into a disposable field runtime with zero provider calls, projecting at several evidence caps and verifying that a relevance-rejected revision still returns exactly. Both write receipts under `probes/receipts/`.

`probes/receipts/owner-source-checkout.json` is the current `probe:owner` receipt against the locally packaged runtime: the patched host with the mock provider, three field-owned compactions, handoff, new, resume, branch, summarized and unsummarized tree movement, and clean worker shutdown. The evidence store's maintained byte total was checked against a fresh walk of the evidence directories on every capacity check of a 300-entry replay and never diverged.

`probes/receipts/case-matrix.json` is the historical v3-era battery receipt: 23 PASS cases, one remaining interactive `/clear` scenario, and one failed live-provider request-budget case. The failed gate preserves the functional compaction/resume evidence instead of relabeling the run as a pass.

The generated active-profile `cassipi` launcher was exercised with the local mock provider and disposable agent, session, and field roots. It loaded `cassifi.cassipi-field-intelligence.v3` through `cassipi-owner.json`; no live field state was changed. The ordinary-profile RPC smoke uses the installed Oh My Pi 18.3.2 path and global extension registry with the explicit bounded-startup overlay `probes/ordinary-smoke-config.yml`; it records the selected agent directory, agent-config hash, overlay path, and the observed plugin-registry state, asserts that CassiPi stays globally disabled, and completes a deterministic local-provider turn. It is a registry/provider coexistence check, not an unmodified active-configuration startup benchmark.

`npm run probe:installed` exercises the named profile's installed host, extension, and runtime but deliberately redirects its session and field data into `.probe`; its durable result is `probes/receipts/installed-owner-lifecycle.json`. It proves installed-artifact behavior, not startup from the named profile's persistent `<profile-root>/cassipi` field. The separate `--live-profile-status` launcher check starts that persistent data home, retrieves authenticated owner status, and requires clean descriptor removal after shutdown.

The generated rehearsal profile was reinstalled with a clean v3 field after its obsolete generated v1 checkpoint proved unmigratable: the v1 loader required `--migrate-v1`, and migration rejected it because the legacy evidence index was absent. This clean reinstall applied only to the disposable `cassipi-rehearsal` profile; the active CassiPi field was not replaced or imported.

The `cassipi-live` trial authenticated one profile-local OpenAI OAuth credential and used only synthetic latch data. A verification-only `compaction.keepRecentTokens: 1` overlay forced a legal manual boundary because the deliberately tiny one-turn fixture was below the normal 20,000-token recent-history floor. CassiPi produced a field-owned summary containing both the current and rejected latches, stopped cleanly, resumed the same session, and returned the exact expected latch pair.

The request-budget gate failed. Two prompt turns produced four external `openai-codex/gpt-5.6-sol` requests: the resumed turn emitted two tool-use responses containing four `cassi_memory` calls before its final response. `--no-tools` suppressed built-in tools but did not suppress the CassiPi extension tool. The complete session used 27,789 tokens and $0.1039848; no further provider request was made. The receipt records response, compaction, session, config, host, and raw-receipt hashes.

The worker shut down, and the synthetic session, workspace, and field were removed after receipt capture; the profile-local OAuth credential remains. The historical live-trial receipt observed the ordinary host at Oh My Pi 18.1.13; that version is retained in the receipt as historical evidence. The current ordinary `omp` host is 18.3.2 with `remote-pi@0.7.0`, while `cassipi` remains isolated on the pinned 18.1.10 owner host. Production provider cutover remains held.

### Measured supported envelope

`probes/receipts/integration-envelope.json` is the Windows 11 x64 measurement from the locally packaged `cassifi.cassipi-field-intelligence.v4` runtime. The closure contains the current CassiFI variational field, atlas, cognition, owner, learning computer, regional and program runtimes, resident hive, affect, communication, temporal, and transceiver capabilities, and the CassiPi adapter/worker. It packages no trained checkpoint or text encoder. The conservative exercised envelope was:

- 64 configured short candidates, with one field-selected candidate in this measured run;
- one 785,403-byte exact binary source inside the 1,048,576-byte worker request envelope;
- task, branch, project, and profile memory scopes;
- three attached clients spanning sibling branches and an unrelated project.

A same-scope repeated query preserved selected source identities and projected messages. Private sibling-branch and unrelated-project learning did not change those identities or messages, and no private source appeared in another client’s inventory or projection. Concurrent inventories use optimistic ownership: one request commits its persistent transition and stale peers fail closed with `STALE_FIELD_HEAD`; scope-leakage projections are then evaluated sequentially against fresh heads.

The current receipt records worker RSS, cold start/restart, cold and warm projection latency, compaction lifecycle latency, and the three-client optimistic-concurrency inventory wall time. These figures are regenerated by `npm run measure:integration`; the receipt, rather than prose copied from an older runtime, is the numeric authority.


`probes/receipts/local-artifact-retention.json` records the only two intentionally retained ignored artifacts: raw synthetic provider-comparison arms needed to audit the canonical comparison receipt, and the pre-upgrade private release snapshot needed for local rollback. Disposable owner sessions, v2 debug runtimes, temporary rehearsal state, loose archives, and stock-host probe state are removed after verification.

Budget sweeps used 468 tokens at 512, 768, and 2,048-token budgets for the selected mandatory source. Projection made zero external-model calls and declared no adaptive sidecar or semantic ranker. Requests up to the 1,048,576-byte transport ceiling reached request validation; oversized requests returned HTTP 413. A hard worker stop was recovered, and replaying a committed operation did not mutate the recovered owner state.

The enforced CassiFI limits are 16 MiB per exact source, 2 GiB total exact evidence, 64 MiB encoded atlas state, 100,000 variables, 100,000 charts, 64 branches per query, and 4,096 solver iterations. These are admission boundaries, not claims that the measurement filled them.

The local regression matrix covers exact byte spans, repeated compaction, retry/idempotence, owner timeout/unload, competing-owner rejection, lost acknowledgements, tree movement, forgetting, correction, import interruption, invalid UTF-8/binary sources, and recalled text that attempts to issue instructions. Recalled material is always rendered as attributed assistant evidence explicitly labeled untrusted, never as system or user instructions. The external-provider comparison below exercises changed premises, failed approaches, working-read replacement, and proposal-versus-result behavior.

### External-provider comparison

`probes/receipts/provider-comparison.json` is the completed isolated comparison on the pinned host and `cassipi-rehearsal` profile. It ran eight arms: stock and CassiPi for `openai-codex/gpt-5.6-sol` and `opencode-go/qwen3.8-flash`, each on two held-out synthetic workspaces with three compactions and four provider turns. All eight arms executed, and all four CassiPi arms passed premise correction, failed-approach recall, fresh-source continuation, proposal-versus-result, branch navigation, and independent verifier checks. The stock arms remain recorded as the baseline and did not pass the complete CassiPi continuity contract.

Every paired token and cost ratio stayed below the preregistered 1.5 regression ceiling. The median CassiPi-to-stock ratio was 0.962 for total tokens and 0.737 for provider cost; the largest pair was 1.083 for tokens and 0.893 for cost. The extension freezes the field-selected evidence set for one native agent turn while issuing a fresh, owner-validated projection receipt after each tool result. This keeps the provider prefix cacheable without hiding current native tool output or weakening field-head, journal-head, revocation, model, tokenizer, budget, or protected-source checks.

The run used disposable workspaces and data homes, synthetic project data, the isolated rehearsal profile, and the same patched host for both arms. It copied no credentials, did not modify the live profile, and made no public release. The receipt binds host, extension, runtime, and release identities and reports `READY_FOR_EXPLICIT_REVIEW`; that is evidence for a cutover review, not authorization to change a live profile.

## Distribution boundary

This package is marked `private` and is an internal Cassi artifact. No public release or redistribution license is granted here. The package allowlist contains only the CassiPi adapter, the current CassiFI runtime closure, and this guide; it excludes evidence stores, memories, transcripts, credentials, probes, checkouts, research corpora, paper sources, training data, checkpoints, and unrelated experiment artifacts. Upstream Oh My Pi and third-party components retain their own licenses.

The isolated provider comparison is complete. The subsequent live-profile trial is held at a failed request-budget gate; any further provider use requires a bounded extension-tool path and fresh explicit approval.
