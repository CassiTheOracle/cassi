# LOCAL-MODEL-VISION — Qwen as the Language Cortex of the Cassi Mind

**Root:** `C:\Users\Carina\workspaces\Cassi\CassiCore\`
**Type:** DESIGN deliverable.
**Date:** 2026-08-17
**Status:** PROPOSED — implementation begins with the frozen Phase L0 transport gate in `LOCAL-MODEL-LLAMA-SERVER-PREREG.md`.
**Companion inputs:**
- `CASSICORE-FOCUS-PLAN.md` — provider ownership, mind-runtime, and `mind_complete` boundary.
- `packages/model-pool/DELEGATE-SURFACE.md` — retained `ModelHandle` contract and deleted provider machinery.
- `CASSI-MIND-PLAN.md` — field bridge, projection, and measured field-as-model program.
- `../UNIFICATION.md` — cross-repository substrate and field-I/O map.

---

## 0. Executive decision

CassiCore will integrate a local quantized Qwen-class model through an unmodified `llama-server` loopback endpoint. The model remains the language cortex: it supplies linguistic priors, semantic transformation, candidate generation, and response rendering. CassiCore remains the focused cognitive mind: it owns sessions, tools, provenance, MnemicField, and orchestration. The CassiCosmos mind engine remains the persistent two-fluid substrate: it receives bounded semantic deposits and returns sparse attractor projections. The first implementation reuses the retained `MindCompleteTransport`; it does not restore the deleted provider pool, create an `@cassicore/providers` package, or fork `llama.cpp`.

The integration deepens only when a pre-registered comparison shows that the preceding layer beats simpler alternatives. The intended progression is transport → shadow observation → field-conditioned retrieval → candidate arbitration → chunk-boundary generation steering → quantization-residual closure → native `libllama` integration. Qwen weights remain frozen until the external field signal earns an adapter experiment.

---

## 1. Grand vision

The finished local system is a layered cognitive machine rather than a language model surrounded by decorative physics:

```text
User / world / tools
        │
        ▼
CassiCore focused mind
  ├─ sessions and task state
  ├─ provenance and event journal
  ├─ MnemicField durable engrams
  ├─ orchestration and tool policy
  └─ local-model transport
        │                     │
        ▼                     ▼
llama.cpp / Qwen GGUF    Cassi mind engine
  ├─ language priors      ├─ Yang/Yin state
  ├─ semantic transforms  ├─ bounded deposits
  ├─ candidates           ├─ field evolution
  └─ response rendering   └─ attractor projection
        │                     │
        └──────── steering ───┘
```

The model's KV cache preserves exact recent linguistic state. The Cassi field preserves active dynamical state. MnemicField preserves durable semantic and episodic memory. The model weights preserve broad learned language and world structure. None is asked to impersonate the others.

The long-term aim is for Qwen to become the language cortex of a field-native intelligence: it proposes and verbalizes; the field organizes competing possibilities and persistent pressures; MnemicField remembers; CassiCore selects tools and carries goals across sessions. If the field proves useful, smaller Cassi-native modules may eventually absorb some deliberation and steering functions while Qwen remains the high-capacity semantic component.

---

## 2. Non-negotiable architecture boundaries

### 2.1 `llama.cpp` owns quantized inference

`llama-server` loads the GGUF, owns transformer execution and the KV cache, applies the model's chat template, and exposes an OpenAI-compatible loopback API. CassiCore does not parse GGUF tensors, manage GPU kernels, or implement another tokenizer.

### 2.2 ohmypi remains the default provider owner

`CASSICORE-FOCUS-PLAN.md` delegates ordinary provider routing, secrets, fallback, quota, and agent sessions to ohmypi. Local inference is an explicit injected transport for the focused mind, not a resurrection of the deleted provider stack. Interactive agent turns may continue to use ohmypi providers; the local model initially serves retained pure-completion loops and controlled research arms.

### 2.3 CassiCore owns cognition and provenance

CassiCore decides which memories and evidence reach the model, records the exact model/build/quantization/sampling provenance, and owns the policy that decides whether to answer, retrieve, use a tool, revise, clarify, or stop.

### 2.4 The field is a controller, not a truth oracle

Field coherence measures organization, not factual correctness. Tool observations, source provenance, user decisions, and direct evidence remain distinct inputs. A fluent unsupported claim cannot become true because it forms a stable attractor.

### 2.5 Default-off influence and exact fallback

Every active Cassi steering mechanism begins disabled. Field-off must preserve the ordinary local-model request and response contract. Engine-down behavior must never fabricate a response or silently substitute a different model; field-dependent features degrade to their field-off baseline, while local-model failure remains a concrete error.

---

## 3. Why quantized Qwen plus Cassi is a strong research pairing

A dense 27B-class model fits the workstation only through quantization or offload. That constraint creates a precise Cassi research target: treat the quantized model as a coarse solver and learn or derive only the residual behavior that compression loses.

Let the higher-quality reference produce logits or behavioral increments $z_t^{H}$ and the Q4 model produce $z_t^{Q4}$. The missing increment is

$$
r_t = z_t^{H} - z_t^{Q4}.
$$

A later Cassi closure may estimate a bounded correction

$$
\hat r_t = g_\theta(F_t, h_t), \qquad z'_t = z_t^{Q4} + \alpha_t \hat r_t,
$$

where $F_t$ is persistent field state and $\alpha_t$ is guarded. This does not ask the field to relearn language. It asks whether a small dynamical controller can recover task-relevant structure lost under compression more efficiently than simply running the larger quantization.

The first phases require no hidden states or logits. They test memory selection and deliberation through the server API. Internal residual correction is licensed only if those external dynamics show a model-independent gain.

---

## 4. Integration surfaces

### 4.1 Local completion transport

The existing retained seam is canonical:

```ts
MindCompleteTransport(
  resolved,
  messages,
  opts,
): Promise<{ content: string; usage?: unknown; model?: string }>
```

A `createLlamaServerTransport` adapter calls `POST /v1/chat/completions`, maps CassiCore messages to the OpenAI-compatible request, applies a bounded timeout and caller cancellation, validates the response, and maps token usage into the existing shape. `createMindCompleteAcquirer` then exposes the same retained `ModelHandle` contract to the mind.

### 4.2 Shadow field observation

The first Cassi layer observes without acting. Each completion trajectory records:

- request and response identifiers;
- selected memory IDs and provenance;
- model, GGUF hash, llama.cpp build, backend, and quantization;
- sampling controls and context size;
- field deposits, field step count, and projected attractors;
- what the field would have selected;
- actual task outcome.

Shadow mode must not alter messages, sampling, token budget, or response.

### 4.3 Field-conditioned retrieval

MnemicField or conventional semantic search first supplies a bounded candidate set. The Cassi field may then organize interactions among those candidates and return a reranking. It does not replace the search index. The field arm must beat both vector-only retrieval and a parameter-matched simpler reranker before adoption.

### 4.4 Candidate arbitration

Qwen emits bounded structured candidates such as answer, retrieve, use-tool, revise, clarify, or stop. The field receives candidate/evidence deposits and projects a decision. The comparison holds candidates and token budget fixed across scalar, recurrent, and Cassi gates.

### 4.5 Chunk-boundary generation steering

If arbitration succeeds, generation may pause at semantic boundaries such as sentence, paragraph, tool-call, or explicit reasoning-step completion. Cassi updates between chunks and may continue, retrieve, revise, call a tool, or finalize. Per-token HTTP feedback is excluded from the initial design because it creates synchronization overhead and repeats the measured failure mode of over-frequent closed-loop injection.

### 4.6 Quantization-residual closure

A Q5/Q6 or unquantized reference generates calibration traces. A Q4 model plus a small field-conditioned adapter attempts to recover only the measured residual. Baselines include ordinary LoRA, an MLP adapter, a GRU/recurrent controller, and a Cassi adapter with free or shuffled constants. Cassi earns attribution only if its structural ablations degrade the result.

### 4.7 Native integration

A native `libllama` host is considered only after the server-level arms pass. It may provide persistent decode sequences, direct logits, sampler control, embeddings, KV operations, and dynamic adapter selection. A maintained `llama.cpp` fork is the final option, not the starting point.

---

## 5. Field semantics for the first program

The first program uses explicit operational meanings rather than claiming that an LLM hidden state is literally a physical field:

- Yang deposit: active proposal, commitment, positive evidence, or action pressure.
- Yin deposit: counterproposal, uncertainty, counterevidence, or receptive pressure.
- Coherence $q$: organized magnitude of the active state.
- Disequilibrium $\varepsilon$: unresolved Yang/Yin relation.
- Attractor projection: a sparse controller readout, never a confidence score by itself.

The encoder that maps semantic items to spatial deposits is an experimental seam. Initial coordinates must be deterministic, versioned, and replayable. Learned coordinates require a separate gate; they cannot be introduced during a retrieval or arbitration comparison.

---

## 6. Phased program

### L0 — local transport foundation

Implement and verify a dependency-free loopback HTTP adapter for unmodified `llama-server`. The adapter is opt-in and is injected into the existing `createMindCompleteAcquirer` seam. No field behavior changes.

**Exit:** request mapping, response mapping, model identity, usage, timeout, cancellation, malformed-response handling, and non-2xx errors are covered; a real loopback-compatible smoke proves the request path.

### L1 — frozen local-model receipt

Run the exact Qwen GGUF on the selected backend. Record model checksum, llama.cpp version, backend, context, VRAM, prompt-processing speed, generation speed, and deterministic smoke output. Compare HIP and Vulkan on the same GGUF before choosing the workstation default.

**Exit:** one pinned configuration is stable and replayable.

### L2 — shadow Cassi observation

Encode turns, selected memories, and structured candidates into the field; record the projected decision without changing the local model path.

**Exit:** field-on-shadow and field-off produce identical model requests and responses while yielding useful, replayable telemetry.

### L3 — field-conditioned retrieval

Rerank a bounded MnemicField candidate set through the field.

**Exit:** the field arm beats vector-only, MnemicField-only, and a simpler reranker on pre-registered long-horizon memory tasks at acceptable latency.

### L4 — field-governed deliberation

Generate the same candidate actions for all arms and compare decision mechanisms.

**Exit:** the Cassi gate improves correct action selection or reduces unnecessary model/tool compute beyond matched recurrent baselines.

### L5 — chunk-boundary steering

Permit bounded field decisions between semantic generation chunks.

**Exit:** task outcome improves without language-quality regression, repetitive loops, or unstable field saturation.

### L6 — adaptive compute

Use field state to decide whether to stop, retrieve, branch, call a tool, or invoke a stronger quantization/reference model.

**Exit:** better task quality per joule, token, or wall-clock than fixed inference policy.

### L7 — quantization closure

Train a small field-conditioned residual adapter around frozen Q4 Qwen using a higher-quality reference.

**Exit:** Q4+Cassi closes a pre-registered fraction of the Q4→reference gap and beats parameter-matched non-field adapters at lower total deployment cost than the reference.

### L8 — native `libllama` host

Move only the proven controller inward for lower overhead and richer state access.

**Exit:** native integration preserves the server-level verdict and materially improves latency or capability.

### L9 — field-native distillation

Distill selected deliberation, memory, or correction functions into smaller Cassi-native modules. Qwen remains available as the language cortex and teacher.

**Exit:** a smaller local system preserves the adopted behavioral contract with lower compute.

---

## 7. Evaluation contract

Every active arm is pre-registered before its first outcome-producing run. Each comparison fixes:

- model and GGUF hash;
- llama.cpp build and backend;
- prompt template;
- task corpus and split;
- seed and sampling policy;
- context and output budgets;
- candidate set where applicable;
- field initialization and step protocol;
- statistic, baselines, stopping rule, and decision tree.

Primary evaluation domains are:

1. memory selection and stale-decision rejection;
2. contradiction handling and revision after evidence;
3. tool-call precision and unnecessary-tool rate;
4. long-horizon goal retention;
5. context tokens and model forward passes;
6. latency, VRAM, and energy where measurable;
7. field stability, saturation, and oscillatory indecision;
8. provenance accuracy and unsupported-claim rate.

Perplexity is supporting evidence, not the sole adoption metric.

---

## 8. Hardware strategy

The first workstation target is the RX 7900 XTX with a Q4-class GGUF, batch size one, moderate context, and a compact mind field. Qwen receives most GPU memory. CassiCore remains CPU-resident. The full CassiCosmos universe renderer does not run during model benchmarks. The controller uses sparse `project k` reads rather than full field readbacks and updates at turn or semantic boundaries.

HIP and Vulkan are both candidates. Backend selection is measured on the exact model rather than assumed. Separate process/device contexts remain the default; cross-process GPU-buffer sharing is out of scope until a measured transfer bottleneck warrants it.

---

## 9. Security, privacy, and failure behavior

- Bind local inference to loopback by default.
- Do not expose an unauthenticated local-model endpoint beyond the workstation.
- Never place provider secrets in CassiCore; the local server needs none.
- Treat model output and retrieved content as untrusted data.
- Preserve direct user instructions and system constraints outside field arbitration.
- On field failure, degrade to the exact field-off local-model path.
- On local-model failure, return a concrete error; do not fabricate from memory.
- On steering divergence, disable influence for the turn and retain the trace.
- Preserve source provenance when memories conflict; do not average contradictions into false consensus.

---

## 10. Explicit rejections

| Rejected start | Reason |
|---|---|
| Restore `@cassicore/providers` or `@cassicore/ai` | Violates the focused architecture and duplicates ohmypi ownership. |
| Fork `llama.cpp` immediately | Adds native maintenance before an external field signal exists. |
| Fine-tune all Qwen weights | Expensive, weak attribution, and unnecessary for retrieval/arbitration gates. |
| Insert arbitrary $\varphi$ constants | Decoration without a measured mechanism. |
| Treat coherence as factual confidence | Internal organization does not establish truth. |
| Update the field every token over HTTP | Excess synchronization and an unearned high-frequency feedback loop. |
| Replace vector retrieval with a PDE corpus scan | Reimplements a solved search stage inefficiently; field value is candidate interaction. |
| Run Qwen and the full reality simulation concurrently in the first gate | Confounds VRAM, queue contention, latency, and stability. |

---

## 11. First implementation slice

The first slice is deliberately narrow:

1. add `createLlamaServerTransport` beside the retained `MindCompleteTransport`;
2. use built-in `fetch`, with no runtime dependency;
3. accept explicit endpoint, timeout, and optional API token configuration;
4. call non-streaming `/v1/chat/completions`;
5. validate success and error payloads;
6. merge caller cancellation with the timeout;
7. return content, model, and usage in the retained shape;
8. export the factory from `@cassicore/model-pool`;
9. cover the observable HTTP contract with a loopback server;
10. leave runtime selection opt-in and field influence absent.

The frozen details and decision tree are in `LOCAL-MODEL-LLAMA-SERVER-PREREG.md`.

---

## 12. Completion criterion for the vision

The vision is realized when a quantized local model can serve as Cassi's language cortex while the field demonstrably improves at least one load-bearing cognitive function—memory selection, action arbitration, adaptive compute, or quantization residual recovery—against simpler matched baselines, without sacrificing provenance, stability, or the field-off contract.

<!-- End of LOCAL-MODEL-VISION-PLAN. -->
