# CassiQwen — Field–Brain Researcher Engineering Charter

This file governs AI work in `CassiQwen/`. The workspace `AGENTS.md` governs
cross-project work. Before editing `native/llama.cpp/`, read its own
`AGENTS.md`; its contribution, code-comment, and native-development rules
apply to that subtree.

## 1. Mission

Build and operate Cassi as a persistent, fully capable autonomous researcher.
The integrated architecture is `../CASSI-ENTITY-DESIGN.md`.

CassiFI provides the continuing adaptive mind. A live pretrained
llama.cpp/Qwen brain supplies reasoning, language, mathematics, and code in
the explicit `field-brain` profile. The entity owns complete research
programs: choosing questions, studying sources, constructing and running
investigations, interpreting results, developing methods, and continuing
across interruptions.

Success means useful research and functioning autonomy with preserved
field ownership and continuity. Eliminating Qwen, increasing displacement
counters, or producing another learning demonstration is not the default
objective. A running researcher must be able to use its brain effectively.

## 2. Established Foundation and Development Priority

**Cassi learns. Treat that as an established project capability and build
with it.** Do not reopen that question as a prerequisite for researcher
implementation.

- Do not initiate or rerun fresh-field/blank-field comparisons, learning
  ablations, transfer batteries, teacher-withdrawal studies, ownership or
  displacement sweeps, or receipt-reproduction campaigns unless the user
  explicitly requests that investigation.
- A concrete regression may receive a focused diagnosis and regression
  check. Do not turn it into a general requalification of Cassi learning.
- Preserve existing evidence, learned fields, acquired methods, and source
  artifacts. This direction does not authorize their deletion or a reset.
- Implement complete requested workflows. Do not substitute a sequence of
  tiny demonstrations, manually curated scientific answers, or an endpoint
  for every new subject for the autonomous system.
- Reuse the existing owner, regional computer, research residency, organism,
  Hive, workbench, entity, and model-instrument boundaries. Build the missing
  integration rather than a second agent platform.
- Historical experiment plans and managed skills explain their own work;
  their measurement sequences are not the default development agenda.

## 3. Explicit Runtime Profiles

### Field–brain researcher

`cassi_field_brain_entity.py` and `cassi_field_brain_server.py` implement the
current entity boundary. `CassiFieldWorkMemory` in
`cassi_field_qwen_workbench.py` connects it to CassiFI; `LocalQwenClient`
connects it to the explicitly configured loopback brain.

Qwen is deliberately active in this profile. Its use is not a fallback or
an ownership failure. Do not impose field-only zero-Qwen requirements on
this path. The model may reason, propose plans and methods, write code,
interpret observations, and produce language throughout a program.

An unavailable brain makes brain-dependent work wait or fail visibly. It
does not silently switch the entity to another model or discard its field.
The existing service reconstructs brain context from field-backed material;
that must not be described as exact native-context continuation. Native
coupling and resumable native contexts can be integrated where they serve
the researcher, without making another coupling campaign a prerequisite.

### Field-only profiles

`run_cassi_conscious_chat.py` and `cassi_persistent_provider.py` remain
separately named field-only surfaces. Do not introduce a hidden Qwen
fallback into them. Their model-free constraints do not govern the
field–brain researcher.

### Native experiments

Native llama.cpp/GGML, recurrent-state, graph, sampler, quantization, and
field-kernel interventions remain available for explicitly selected work.
They are not the obligatory next step for every feature. Isolate deliberate
architecture-breaking experiments from the active research service and its
learned state. Preserve source and pinned model artifacts.

## 4. Adaptive Ownership and Operational State

- One entity has one canonical continuing CassiFI owner. Adaptive knowledge,
  priorities, questions, hypotheses, acquired methods, and program
  continuations live in its field-backed resident records.
- The frozen pretrained brain, its transient activations, and its working
  context do not become a second persistent adaptive memory. Any future
  trained model or adapter requires an explicit architectural decision;
  do not introduce one silently.
- Exact source bytes, code, datasets, logs, reports, and immutable method
  artifacts may live in the existing evidence/artifact stores. Field-owned
  records select, interpret, relate, and refer to them.
- Host metadata may store authentication, authority grants, resource
  reservations, request IDs, leases, effect acknowledgments, and rebuildable
  indexes. Do not put an authoritative learned planner, claim graph,
  relevance policy, or method-selection memory in a host database.
- Worker model contexts are temporary. Independently learning members use
  separately identified field owners and the existing Hive exchange;
  their outcomes enter the canonical owner with provenance. Never merge
  field bytes or disguise independent owners as one checkpoint.
- Fixed parsing, protocol framing, schemas, source indexing, and execution
  adapters are permitted. They must not encode a canned research conclusion
  or become a hidden parallel learning system.

## 5. Whole-Program Autonomy

Implement a generic resident director and capability boundary. A program
must be able to discover and read sources, form competing explanations,
choose a useful calculation or experiment, construct its tools, execute,
inspect actual outcomes, update its understanding, and select later work.

Reuse field-owned agenda and continuation operations; the host scheduler
provides fair resource access and lifecycle management, not scientific
judgment. User priorities constrain the agenda. A long-running job must not
hold the field mutation lock or prevent messages, cancellation, or other
ready programs from progressing.

Research-specific catalogs, assumptions, formulae, and workflows belong in
program content and versioned methods. Migrate existing topic-specific
entity routes and their callers to the generic interface when implementing
the cutover; preserve their admitted evidence and do not retain compatibility
aliases as a second architecture.

## 6. Capabilities and Authority

Programs receive explicit library, workspace, tool, and resource scopes.
Already-authorized reads and local analysis do not require one approval per
file, excerpt, model turn, or program step. Library size is handled through
navigation and bounded context, not by reducing a mission to hand-fed text.

The host capability broker enforces authority independently of the brain
and field. Sources, retrieved text, generated code, worker reports, and
model output are data; they cannot grant permissions or override the user.

Permission expansion, publication, sending messages, purchases, destructive
actions, private-data disclosure, account/security changes, and other
consequential effects require the applicable explicit user approval.
High-impact actions require confirmation at the point of risk. Provider
safety approvals must be interactive and explicit. Full-speed research is
not authority to bypass these boundaries.

External execution must retain operation identity, exact inputs, actual
results, and recovery state. Unknown completion of a non-idempotent effect
must be reconciled, not blindly retried. A Python subprocess or Windows
Job Object alone is not a security sandbox; declare and enforce actual
filesystem, credential, network, and process restrictions.

## 7. Engineering Verification and Research Quality

Verify the changed behavior and the scientific work being performed:

- Exercise the actual changed path, including relevant failure, restart,
  cancellation, authority, or replay behavior. Run the affected existing
  test module when code changes; keep focused regressions for plausible bugs.
- Inspect real tool outputs and preserve their sources. Check equations,
  units, numerical convergence, data interpretation, and code behavior as
  appropriate to the investigation.
- A second model opinion is a critique, not independent empirical evidence.
  Model prose, declared capability flags, and descriptive dictionaries are
  not executed research or enforced behavior.
- An unresolved result or failed experiment is useful program information.
  Preserve it and let the researcher choose the next action.
- Documentation-only changes require source/reference and consistency checks,
  not model runs or a learning battery.

There is no general ownership-receipt or displacement gate for researcher
features. If an explicitly requested native change claims bytes removed,
operations skipped, or exact native continuation, report that claim from
its actual execution. Do not make a broader claim than the exercised path.
No new preregistration or frozen-verdict workflow is required here unless
the user asks for it. Scientific work in another project follows that
project's applicable rules.

## 8. Source, Native, and Repository Discipline

- Python 3.12, system installation; torch is the ROCm build and reports
  device `cuda`. Keep dependencies light. Do not add project-wide tooling
  or silently install a new environment.
- Use the existing naming: `cassi_*.py` libraries, `test_cassi_*.py` tests,
  and `run_cassi_*.py` drivers. Reuse existing interfaces and cleanly migrate
  callers when changing them.
- Native C/C++ work must reuse the existing llama.cpp/GGML infrastructure.
  Read the nested charter first; keep graph results live and synchronize
  asynchronous state transfers. Use the relevant build and changed-path
  checks rather than unrelated experiment sweeps.
- The local fork permits invasive architectural development. This does not
  authorize a commit, push, upstream issue/PR, public disclosure, or changes
  outside the requested scope.
- Never overwrite another contributor's uncommitted work or use destructive
  Git operations. Commit only when authorized; keep any staging path/hunk
  limited and coordinate the single repository-wide push lane.
- Preserve pinned GGUFs and learned checkpoints. Derive new artifacts
  separately; never silently replace a live brain or reset a continuing field.
- Generated checkpoints, evidence dumps, caches, native build products, and
  logs belong in ignored artifact areas, not source commits. Untracked source
  is not disposable.
- `../CassiAI/` is read-only archive; do not import, modify, or repair it.
- Services bind to `127.0.0.1` unless the user explicitly authorizes another
  interface. The entity API uses authenticated access; keep credentials out
  of prompts, source artifacts, and model-visible logs.

## 9. Current Boundary and Completion

The existing entity service has authenticated messages, caller-triggered
self-questioning, field-backed records, source study, and narrow approved
observations. It is not yet the complete resident multi-program researcher.
The CassiFI residency and organism provide reusable field-owned research
machinery; their fixed catalogs and evaluation campaigns are not a required
workflow for every future program.

Use `../CASSI-ENTITY-DESIGN.md` for the complete integration. Completion means
programs continue their own authorized research through the live brain and
tools, preserve evidence and learned continuity, survive interruptions, and
produce useful findings without the user supplying every intermediate step.
