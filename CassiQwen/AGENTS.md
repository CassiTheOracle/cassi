# CassiQwen — Engineering Charter

> CassiQwen is a radical experiment in how much of an existing LLM can be
> siphoned into field intelligence, and how extensively inference can be changed.
> It is **not** a production-safety project. Speed and context are already
> unusable; preserving quality, compatibility, baseline behavior, or
> conservative fallbacks is secondary. The governing question is maximal
> architectural intervention and the actual displacement of Qwen state and
> compute. Quality regression and failed language behavior are valid
> experimental outcomes.

This file governs AI work in `CassiQwen/`. It does not override the workspace
root `AGENTS.md` for cross-repo facts, but for anything inside this directory
this file wins. **Deeper rules win:** for work inside
`native/llama.cpp/`, read and obey `native/llama.cpp/AGENTS.md`; its
contribution, code-comment, and AI-usage constraints apply there even when
they are stricter than this charter.

This is a private local fork and intervention laboratory, not an upstream
submission. The project owner has explicitly authorized the invasive
interventions named here. That standing authorization satisfies the nested
file's design-ownership and large-change confirmation requirement for work
within this experiment. It does not authorize a commit, push, upstream issue
or pull request, public disclosure, or a change outside `CassiQwen/`.

## 1. Mission and Success Order

**Mission.** Replace Qwen's native inference machinery with field intelligence
as far as the architecture can be pushed, and measure how far that reaches.

Success is ranked in this order:

1. **Causal field ownership** — the field demonstrably makes token, state, or
   compute decisions that Qwen would otherwise have made.
2. **Native displacement** — native tensors, ops, layers, output rows, or
   weight bytes are removed, bypassed, compressed, offloaded, or replaced and
   the difference is measured.
3. **Field capacity** — the field sustains bounded, finite, inspectable
   dynamics over the longest feasible event horizon.
4. **Task signal** — any task-relevant behavior the field produces.

Language quality, throughput, baseline parity, and user-facing usefulness come
**after these four goals**. Regressing them is an acceptable outcome. An
experiment that owns more of inference but emits gibberish is a success at
levels 1–2; a polite reply that routes every decision through unchanged Qwen
is a failure.

## 2. Governing Question and Preferred Decision Rule

The governing question is: *how much of Qwen can the field own?*

**Preferred decision rule.** When a choice arises between preserving Qwen
behavior and increasing field ownership, an agent MUST choose field ownership
unless the user says otherwise. This is the default, not a suggestion. "Keep
Qwen working" is not a tie-breaker.

## 3. Intervention Ladder

Interventions are ordered from least to most displacing. An agent SHOULD climb
as high as the current experiment demands; stopping at a lower rung in order
to preserve Qwen is only justified when the user asks for it.

1. **Additive graph steering.** A field reads a Qwen activation and changes a
   downstream signal; Qwen still owns its native state, LM head, and sampler.
   (Current `--cassi-qi-field` correction before the LM head.)
2. **Field-conditioned selection.** Qwen produces candidates; the field ranks
   or filters them; Qwen's sampler commits. Field owns selection within a
   fixed candidate set. (Current F5 reranker.)
3. **Field-owned emission.** The field emits tokens/events through a fixed
   deterministic boundary transducer; Qwen logits are not blended in. Qwen may
   remain only as an explicitly offline frozen teacher or measurement source.
4. **Field-owned state.** Recurrent state, memory, and consolidation live in
   the field; Qwen KV/cache/attention state for the owned sequences is reduced
   to an optional ephemeral cache or removed.
5. **Field-owned layers / compute.** One or more transformer layers, the LM
   head, the sampler, or the embedding lookup are executed by the field or by
   field-conditioned kernels; the corresponding Qwen path is bypassed and its
   weights are not read for the owned work.
6. **Field-owned inference.** The field is the runtime; Qwen is reduced to a
   teacher, a tokenizer/vocabulary, or a selectively queried static matrix
   bank — not a full autoregressive runtime.

The maximal endpoint is explicit: Qwen MAY end up as a teacher, a tokenizer or
vocabulary, or a static matrix bank queried on demand, rather than a running
LM. Agents SHOULD design toward the highest rung the experiment can reach and
report the rung actually attained.

## 4. Causal Ownership Versus Native Replacement

A change counts as **causal field ownership** only when the field changes a
committed token, state transition, cache decision, layer result, or compute
route. A change counts as **native replacement** only when native tensors,
state, ops, layers, output rows, or weight accesses are demonstrably removed,
bypassed, compressed, offloaded, or replaced. Record both dimensions: causal
ownership may be nonzero while native displacement remains zero.

The following count as neither causal ownership nor native replacement:

- A duplicate sidecar that runs alongside Qwen and is ignored by the graph.
- A field result computed but never consumed by a live graph output or a
  committed token/state decision.
- A reranker whose result never changes the committed token and has no
  counterfactual receipt.
- A compatibility shim whose only purpose is to keep Qwen bit-identical.

An off-graph host callback MAY steer or emit, but it MUST be labeled as an
off-graph intervention; it does not count as a native-graph intervention. A
field op that a backend prunes because its result is dead owns nothing. For a
graph-native claim, field state MUST be a live graph result and its
asynchronous copy MUST be synchronized before the next event.

## 5. Intervention Ownership Receipt

Every intervention MUST produce an **ownership receipt** that names, for the
measured run, the native resources the field displaced and the decisions the
field owns. At minimum the receipt reports:

- **Native dynamic-state bytes removed** — KV/cache/attention/recurrent bytes
  per sequence that the field eliminated or compressed, and the remaining
  native-state footprint.
- **Native ops / layers / output rows actually skipped** — which graph nodes
  or LM-head rows were bypassed or not materialized per token, and a count of
  computed-vs-skipped ops where measurable.
- **Qwen weight bytes touched or offloaded per token** — bytes read from
  Qwen weights per generated token (or a credible estimate), and which weight
  regions were not accessed.
- **Decisions the field owns** — which token selections, state updates, cache
  writes, or layer outputs were determined by the field versus left to Qwen,
  with the counts for each.

**Minimum completion.** An intervention is complete when it is runnable and
inspectable and the receipt shows causal field ownership. Gibberish output and
slower execution are valid outcomes and do not block completion. If native
displacement is zero, the receipt MUST say so and MUST NOT call the result a
replacement. A receipt with neither native displacement nor a field-owned
decision is a failed intervention, regardless of output quality.

## 6. Field-First Ownership

The field is the primary adaptive object; Qwen is the substrate being siphoned.
Where a function can be served by the field or by Qwen, an agent MUST route it
through the field unless the user directs otherwise. New memory, selection,
consolidation, and emission logic belongs in the field or its fixed boundary,
not in a new Qwen-side module. Qwen components that an intervention renders
idle SHOULD be bypassed, offloaded, or removed rather than retained as a warm
fallback.

### Cassi-native architecture requirement

Adopted and live Cassi architecture MUST be Cassi-native. The sole adaptive
persistent object is `QiFieldState` with layout `[S, 9M, B]`; derived
diagnostics are not additional state. Sensing, evolution, emission, correction,
and consolidation MUST use the fixed Qi codebook and bounded field laws in
`cassi_qi_field.py`.

Live or adopted Cassi paths MUST NOT contain learned embeddings, neural layers,
trained projection heads, vocabulary matrices, optimizers, backpropagation,
loss-trained parameters, engineered feature encoders, softmax sampling,
temperature, top-k/top-p truncation, or multinomial selection. Fixed
serialization, protocol framing, UTF-8 conversion, and deterministic
phase-conjugate boundary probes are permitted because they add no adaptive
state. Conventional models and training code may exist only as explicitly
offline comparators or teachers, must be unreachable from live Cassi imports,
and never count as Cassi-owned computation.


## 7. Permitted Interventions

An agent MAY, without special permission, patch or rework any of the following
inside this directory, subject to the evidence and integrity rules below:

- **Native llama.cpp / GGML** — `native/llama.cpp/ggml/include/ggml.h`,
  `ggml/src/ggml.c`, `ggml/src/ggml-cpu/ops.cpp`, `ops.h`,
  `ggml/src/ggml-vulkan/ggml-vulkan.cpp`,
  `ggml/src/ggml-vulkan/vulkan-shaders/cassi_qi_field_step.comp`,
  `ggml/src/ggml-backend-meta.cpp`, and the Qwen35 graph in
  `src/models/qwen35.cpp`, `src/llama-graph.cpp`, `src/llama-graph.h`,
  `src/llama-context.cpp`, `src/llama-context.h`.
- **Token flow** — sensing, routing, emission, and the boundary between byte /
  token events and field events.
- **Cache and attention** — KV layout, context save/restore, eviction, and the
  attention op, including replacing them with field-owned recurrent state.
- **Recurrent state** — field state shape, scale banks, consolidation, and
  persistence; native context-state sections are fair game.
- **Layers and embeddings** — transformer layers, residual injection, and the
  embedding table; an agent MAY bypass, freeze, or field-condition them.
- **LM head and sampler** — the output projection and the sampling algorithm;
  an agent MAY replace them with fixed-resonance emission or field-owned
  selection.
- **Quantization and weights** — how Qwen weights are stored, loaded, and
  accessed; an agent MAY offload, bypass, freeze, or selectively query weight
  regions.
- **Cassi-native field laws and boundaries** — fixed codebooks, deterministic
  boundary transducers, bounded field dynamics, phase-conjugate resonance
  emission and correction, and field-state persistence.

Qwen MAY remain an explicitly offline frozen teacher, tokenizer, vocabulary,
or selectively queried matrix bank. Its outputs may enter Cassi only through a
fixed boundary as observations or correction targets; no Qwen or conventional
model state may become part of the adopted Cassi runtime.

## 8. Destructive Experiments and Integrity Boundaries

Destructive architectural experiments are explicitly permitted. An agent MAY
break Qwen generation, corrupt output, regress perplexity, bypass or replace
native subsystems in a derived build, and leave that build unable to run in
its ordinary configuration — as long as the experiment is inspectable and
the receipt is accurate.

The following MUST NOT be violated:

- **Workspace integrity.** Do not delete or modify other people's uncommitted
  work. Do not run destructive git operations. One session pushes; stage
  path-limited and coordinate before touching a shared file.
- **Source-artifact integrity.** Keep source code, tests, and the pinned base
  GGUF recoverable. An experiment MUST be reversible from source.
- **Honest reporting.** Never claim displacement, ownership, parity, or quality
  that the receipt does not show. A null or negative result is a deliverable.

## 9. No Silent Fallbacks

An agent MUST NOT add a silent fallback, compatibility shim, or transparent
degradation path that masks the experimental path. If the field path fails,
the failure MUST be visible in the receipt and the runtime output. "Fail
closed to Qwen" is forbidden unless the user explicitly asks for a named,
declared comparator mode. Existing declared comparator modes (e.g. F5
`baseline`, the `--no-cassi-qi-field` graph) are allowed because they are
explicit and named; silently routing field failures back to Qwen is not.

## 10. Evidence Requirements

Evidence is minimal and runtime-grounded. An agent MUST produce, for each
intervention:

- **Actual execution** — the intervention ran, not just compiled.
- **Counters / memory / timing** — native-state bytes, op/row counts, weight
  bytes per token, and wall-clock or token-rate deltas where measurable.
- **Checkpoint identity** — when field state persists, a fingerprint / hash /
  identity check proving the field round-trips exactly.

Quality metrics (perplexity, factuality, coherence, human preference) and
performance metrics (tokens per second, latency) are secondary. They MAY be
reported, but they do not gate the experiment, and a negative delta in them is
an acceptable outcome. No preregistration, frozen statistic, or publication
ceremony is required unless the user explicitly asks for it.

## 11. Historical L-Stage Language

Existing L-stage preregistration, adoption, and production-boundary language
in `CASSI-FIELD-INTELLIGENCE-DESIGN.md`, `*_prereg.md`, F0–F5 stage receipts,
and related documents is **historical experiment documentation**, not a
required workflow and not a limit on new CassiQwen interventions. An agent
MUST NOT treat a past stage gate, a `SUPPORTS` verdict, or a "production path"
label as authorization or as a boundary on what may be changed. Preserving the
no-field baseline is optional — useful as a comparator when the experiment
needs one, not an architectural obligation. Experimental field paths MAY be
default-on inside `CassiQwen/`; bit-identical no-field behavior is not a gate
unless the user explicitly requests it.

## 12. Repo Boundaries

- **CassiAI** (`../CassiAI/`) is a read-only archive. Consult its lessons
  (steering over prediction, increment-relative metrics); never import,
  modify, or "fix" its code or its `AGENTS.md`.
- **Generated weights, checkpoints, and logs** — `.pt` field checkpoints,
  `_diag/` dumps, `__pycache__`, native build products, and run logs — MUST live
  in gitignored or explicitly untracked artifact areas and MUST NOT be committed
  as source. This directory currently has no `.gitignore`; keep generated
  artifacts separate from `native/llama.cpp/` source and never treat untracked
  source as disposable.
- **Pinned base GGUF** — `Qwen3.8-27B-Q4_K_M.gguf` is the immutable reference
  model. Retain it; derive artifacts from it separately and do not overwrite
  it.
- **Loopback-only services.** Field, mind, and provider services bind to
  `127.0.0.1` only (current: F3 daemon `7600`, F5 provider `8083`, server
  `8084`). Do not expose them on a non-loopback interface unless the user asks.

## 13. Compiled-Code Discipline

Native C/C++ changes in `native/llama.cpp/` are in scope and encouraged when
they displace Qwen compute, but they carry extra cost: every merged line must be
understood, built, and maintained. Before writing native code, an agent SHOULD
read `native/llama.cpp/AGENTS.md` and the relevant existing patterns; reuse
existing infrastructure; keep changes as simple as the change allows; and make
the field op a **live graph result** with synchronized async copies. Vulkan
shader profiles are separate from the existing modal operator. The focused
parity harness is `native/llama.cpp/tests/test-cassi-qi-field.cpp`; CPU/Vulkan
parity and finite bounded dynamics are the native receipt.

## 14. Source and Test Conventions

- **Python 3.12**, system install; torch is the ROCm build (device reports
  `cuda`). No `requirements.txt`/`pyproject.toml`; keep scripts
  dependency-light.
- **Naming.** `cassi_*.py` for library modules, `test_cassi_*.py` colocated for
  tests, `run_cassi_*.py` for drivers/demos. Match the existing convention.
- **Tests** exercise real behavior and real runtime paths: live protocol,
  CPU/Vulkan parity, checkpoint identity, finite-state and bounded-energy
  checks, and the specific ownership boundary changed. A test that only
  asserts source text or incidental defaults is not a test.
- **Receipts over suites.** A green test run is necessary but not sufficient;
  the ownership receipt (Section 5) is the verdict.
- **Do not** introduce lint, typecheck, or project-wide build tooling where
  none exists; do not resurrect deleted daemon/core paths.

## 15. Runtime

The canonical live paths are field-only:

```text
python run_cassi_conscious_chat.py --config cassi-conscious-chat.json
python cassi_persistent_provider.py
```

Both load the adopted zero-teacher v3 organism checkpoint and must remain free
of llama.cpp, GGUF, Qwen tokenizer/output-head, KV/recurrent state, and teacher
imports. `start-llama-server.ps1` is retained only for separately invoked
offline teacher capture, native intervention experiments, and measured
displacement baselines. Its Qi, single-scale field, resonance, and modal graph
paths are never a fallback for the terminal or port-8086 provider.
