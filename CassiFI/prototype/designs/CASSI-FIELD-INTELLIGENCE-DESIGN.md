# Cassi Field Intelligence

## Status: Qi v2 multi-scale native path—2026-08-23

This document specifies a field-only intelligence architecture for Cassi. It is
an isolated reference design and does not replace the verified v2 world-model
provider. The reference implementation is:

```text
cassi_field_intelligence.py
```

Its contracts are exercised by:

```text
test_cassi_field_intelligence.py
run_cassi_field_intelligence_smoke.py
```

The intended endpoint is a single persistent field intelligence rather than a
neural network with a field attached to it.

## Design thesis

The architecture has one adaptive persistent object:

\[
X_t \in \mathbb{R}^{S\times 9M\times B}.
\]

Each of the \(S\) scale banks contains two coupled complex Yang/Yin fields,
their complex velocities, and one temporal imbalance accumulator per mode:

```text
state[s, 9*m + 0, b] = Re(EY_s,m)
state[s, 9*m + 1, b] = Im(EY_s,m)
state[s, 9*m + 2, b] = Re(EI_s,m)
state[s, 9*m + 3, b] = Im(EI_s,m)
state[s, 9*m + 4, b] = Re(VY_s,m)
state[s, 9*m + 5, b] = Im(VY_s,m)
state[s, 9*m + 6, b] = Re(VI_s,m)
state[s, 9*m + 7, b] = Im(VI_s,m)
state[s, 9*m + 8, b] = epsilon2_ema_s,m
```

Qi is organized phase flow derived from Yang/Yin, not a third stored field.
The controller measures temporal current within a bank and scale current
between demodulated neighboring banks. Its canonical local coherence is:

\[
\rho=|E^Y|^2+|E^I|^2,\qquad
\varepsilon=|E^Y|^2-\varphi|E^I|^2,
\]

\[
\overline{\varepsilon^2}_t
=(1-\tau)\overline{\varepsilon^2}_{t-1}+\tau\varepsilon_t^2,
\qquad
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\overline{\varepsilon^2}},
\qquad \tau=\varphi^{-1}.
\]

There is no second adaptive latent vector, memory matrix, embedding table,
optimizer state, or learned output vocabulary. Slower scale banks are memory
because they are parts of \(X_t\). The optional associative-KV wrapper may keep
a bounded exact-recent ring as an ephemeral cache; it is not learned and is
deliberately excluded from field-only checkpoints.

A complete event cycle is:

```text
fixed boundary sense
    → bounded Yang/Yin differential evolution at every scale
    → derived Qi current, coherence, and trust gates
    → fixed-codebook cross-scale de-resonance
    → phase-conjugate measurement or correction
    → gated fast-to-slow consolidation in X_t
    → optional closed-boundary imagination
```

Perception, prediction, memory, uncertainty, action, and text emission are
boundary conditions and measurements of this one multi-scale field. They are
not separate learned heads.

## Constitutional rules

The field-only implementation MUST satisfy these rules:

1. The only adaptive persistent tensor is `[S, 9*M, B]` Qi field state.
2. Qi current and coherence are derived measurements; Qi is never stored as a
   third field.
3. Fixed scalar controls and fixed mode/probe/codebook descriptors are allowed.
4. Boundary transducers are deterministic functions of their input and fixed
   configuration. They are not learned embeddings.
5. There are no `torch.nn` layers, trainable parameters, Gaussian latent heads,
   softmax classifiers, optimizer tensors, or learned vocabulary matrices.
6. The same field/operator path used for prediction is used in residual
   correction. Correction is not a separate classical learning head.
7. Scale geometry and cross-scale bindings are fixed, not learned masks.
8. A checkpoint contains the field plus immutable contract metadata only; the
   exact-recent ring is intentionally ephemeral.
9. Native promotion must preserve the field output as a live graph result. A
   host callback is not a field update.

The fixed resonance bank is functionally a measurement operator. It is more
accurate to call it a **fixed boundary probe** than to claim that the system
has no readout at all.

## Native compatibility

The canonical reference and native implementation share these frozen
identities:

```text
cassi.qi.native-linear-scale-component-mode.v2
cassi.qi.multiscale-de-resonant.v2
cassi.qi.multiscale-prime-quadratic-chirp.v2
```

The scale-component-mode layout is separate from the older
`GGML_OP_CASSI_MODAL` and single-scale `GGML_OP_CASSI_FIELD_STEP` layouts.
Those paths remain available, but the CLI makes them mutually exclusive with
the Qi path.

Existing `cassi_modal_torch.py` still supplies the native mode symbols and the
Yang/Yin convention. The Qi reference extends that state with fixed scale
banks, bank-specific codebooks, temporal imbalance, and derived current gates;
it does not import a learned adapter.

Native promotion is complete through `GGML_OP_CASSI_QI_FIELD_STEP`. The Qwen35
graph consumes a selected layer input, evolves the multi-scale field, injects
the live correction before the LM head, and queues the per-sequence state for
exact context save/restore. The public ctypes boundary remains uninvolved.

## Fixed boundary alphabet

### Text

The base text boundary is byte-level. A byte is an integer in `0..255`; no
Qwen token embedding is needed to sense it. Additional control symbols require
an explicitly larger fixed alphabet and enough field modes for their probes.

The reference transducer uses a deterministic quadratic-chirp phase:

\[
\theta_{a,m} = 2\pi\frac{
 ((a+1)(m+1)^2 + (a+1)^2(m+1)) \bmod P
}{P},
\qquad P=4093,
\]

\[
C_{a,m}=\exp(i\theta_{a,m}).
\]

`C` is generated on demand from the immutable formula. It is not stored as a
trainable matrix. The formula, alphabet size, wave width, and profile ID are
bound into the checkpoint fingerprint.

The reference path uses a fixed wave bank for both sensing and probing. Native
large-vocabulary decoding should not materialize a dense `V×M` dot product.
It should use fixed descriptors and deterministic score-descending/token-ID
tie-breaking. A two-stage resonance scan is the preferred implementation:

```text
fixed coarse probes over all candidates
    → fixed top-R candidates
    → fixed fine probes over R
    → deterministic token ID tie-break
```

No ordinary Qwen logits are blended into field-native emission.

### Other modalities

A continuous input `x` uses a fixed range map followed by the same phase
transducer. For each input coordinate `d`, fixed integer coefficients can be
generated from `(mode, coordinate, prime)`; the resulting complex wave is
written into the same field. Image patches, audio frames, actuator feedback,
and tool events therefore differ only by their boundary descriptor, not by a
new learned encoder.

This does not mean that raw pixels or arbitrary audio become semantically
useful automatically. The fixed transducer must have sufficient injectivity
and field capacity. A modality-specific learned encoder would violate the
strict field-only constitution, although a frozen external sensor may be used
as an explicitly declared compatibility/teacher boundary.

## Field dynamics

Let

\[
D_m=E^Y_m-\phi E^I_m,
\qquad \phi=1.618033988749895.
\]

`D` is a transient differential view, never a second persistent tensor.

For fixed modal symbol `σ_m`, fixed restoring coefficient `Ω_m²`, damping
`γ_m`, and step `h`, the field evolves by a velocity-first symplectic step:

\[
A^Y_m=(\sigma_m-\Omega_m^2)E^Y_m
      +\Omega_m^2\phi E^I_m-\gamma_mV^Y_m,
\]

\[
A^I_m=\sigma_mE^I_m
      +\Omega_m^2(E^Y_m-\phi E^I_m)-\gamma_mV^I_m,
\]

\[
V^Y_m\leftarrow V^Y_m+hA^Y_m,
\qquad
V^I_m\leftarrow V^I_m+hA^I_m,
\]

\[
E^Y_m\leftarrow E^Y_m+hV^Y_m,
\qquad
E^I_m\leftarrow E^I_m+hV^I_m.
\]

The reference additionally applies a fixed rational saturation:

\[
z\leftarrow\frac{z}{1+\kappa |z|^2},
\]

or an equivalent fixed amplitude/energy envelope. This is a stability law,
not a learned activation head. Every step reports finite-state and energy
telemetry.

### Fast and slow bands

A fixed partition selects fast and slow modal bands. The current reference
selects the modes with the smallest absolute native symbol for the slow band;
the remaining modes are fast. A production profile must freeze this partition
and bind it into the operator identity.

Fast modes provide current event sensitivity. Slow modes retain associations.
Both are coordinates in `X_t` and both evolve under the same field law.

## Prediction and emission

After sensing and fixed evolution, form a phase-conjugate fast boundary flux:

\[
J_m=D_m+\tau(V^Y_m-\phi V^I_m).
\]

The fast query is normalized transiently:

\[
q_F(m)=\frac{P_FJ_m}{\max(|P_FJ_m|,\epsilon)}.
\]

A fixed mode pairing maps fast query phases to the slow probe surface. The
reference path uses aligned fast/slow mode order; a native profile may use a
frozen permutation and phase map.

The slow differential field is measured against the query:

\[
R_S(m)=H_S(m)q_S(m),
\qquad H_S=P_SD.
\]

For fixed probe wave `p_a` for event `a`:

\[
z_a=\frac{1}{M_S}\sum_{m\in S}\overline{p_a(m)}R_S(m),
\qquad
s_a=|z_a|^2.
\]

Emission is the fixed deterministic maximum of `s_a`, with token/event ID as
tie-break. No logits, learned vocabulary row, or softmax is involved.

The reference `CassiFieldEmission` also reports:

- available/no-signal state;
- resonance score vector;
- flux magnitude;
- top-two margin;
- uncertainty derived from margin and signal availability.

These are measurements of the field, not separately learned uncertainty or
value heads.

## Learning rule

When the observed successor `y` arrives, generate its fixed probe wave `p_y`
and compute residual:

\[
e=p_y-R_S.
\]

The phase-conjugate correction is the fixed adjoint/LMS direction:

\[
\Delta H_S(m)=
\eta\frac{\overline{q_S(m)}e(m)}{|q_S(m)|^2+\epsilon}.
\]

This is the reciprocal part of the design: prediction binds the slow field by
`q_S`; correction unbinds the residual with `\overline{q_S}`. There is no
association matrix `H(q)` and no optimizer update.

The correction is written directly into the Yang/Yin coordinates:

\[
E^Y_S\leftarrow E^Y_S+
\frac{\Delta H_S}{1+\phi^2},
\]

\[
E^I_S\leftarrow E^I_S-
\frac{\phi\Delta H_S}{1+\phi^2}.
\]

Therefore:

\[
\Delta(E^Y_S-\phi E^I_S)=\Delta H_S.
\]

A fixed slow retention and rational saturation follow the correction. Optional
velocity impulses must also be written into the same eight-lane field state.
The reference implementation has no running statistics or persistent learning
rate state.

## Memory and consolidation

Consolidation is not a second recurrent module. It is a fixed relaxation of the
same field:

```text
fast differential amplitude → fixed damping
slow differential amplitude → slow retention
fast velocity → fixed damping
slow velocity → fixed momentum retention
fixed field evolution → bounded state
```

The expected signature of useful memory is:

- transient fast energy decays after an event;
- task-relevant slow energy persists;
- successor resonance improves after correction;
- frozen-field and shuffled-target controls do not show the same improvement;
- field state remains finite over long event streams.

A memory tensor, EMA buffer, learned plasticity matrix, or optimizer momentum
would violate the single-field rule even if it were called a “field summary.”

## Imagination and persistence

Autonomous imagination is closed-boundary evolution:

```text
evolve field
→ emit fixed-resonance event
→ feed emitted event through fixed boundary sensor
→ consolidate
→ repeat
```

It does not call Qwen, use a KV cache, or consult a classical language head.

A live session checkpoint contains:

```text
Qi session schema
fixed configuration, codebook, and engine fingerprints
raw serialized float32 QiFieldState [S,9M,B]
bounded non-adaptive provenance metadata
```

Transcript metadata may be retained for audit and display, but it is not a
second adaptive state and is not replayed through the boundary on restore.

It does not contain:

```text
optimizer state
learned parameters
neural-layer state
engineered feature vectors
sampling RNG state
Qwen KV or recurrent state
teacher traces or vectors
candidate embedding or output rows
slow sidecar memory
```

The reference uses atomic `torch.save`/replace for the Python prototype. Native
promotion should use a framed binary payload with explicit dimensions, dtype,
profile IDs, SHA-256 metadata, and fail-closed mismatch checks.

## What makes the architecture distinct

The individual ingredients have substantial precedent:

- Hopfield and complex associative memories use dynamical attractors.
- Hyperdimensional/HRR systems bind and unbind fixed vectors.
- Reservoir and liquid-state systems use fixed dynamics with stateful readout.
- Predictive coding uses prediction error and reciprocal correction.
- Neural fields and physical neural systems use continuous spatial dynamics.
- Fast/slow plasticity uses multiple consolidation timescales.

The defensible novelty claim is the conjunction, not any one primitive:

> A bounded complex modal Yang/Yin field is the sole persistent adaptive object;
> fixed task-independent boundary transducers provide sensing and probing; the
> same transport/field path performs flux prediction and phase-conjugate
> residual correction; fixed fast/slow modal consolidation stores memory in that
> same field; and no learned tensor, optimizer/KV state, or task-trained output
> map is present.

This document does not claim that the architecture is globally unprecedented,
patent-clear, or already a general intelligence. “Cassi-native” means that the
adaptive state transition and learning law are field operations, not that every
fixed boundary descriptor is without precedent.

Relevant comparison sources include:

- Hopfield, “Neural networks and physical systems with emergent collective
  computational abilities,” PNAS 79 (1982), DOI
  [10.1073/pnas.79.8.2554](https://doi.org/10.1073/pnas.79.8.2554).
- Plate, “Holographic reduced representations,” IEEE TNN 6 (1995), DOI
  [10.1109/72.377968](https://doi.org/10.1109/72.377968).
- Jaeger, *The Echo State Approach to Analysing and Training Recurrent Neural
  Networks* (2001), DOI
  [10.24406/publica-fhg-291111](https://doi.org/10.24406/publica-fhg-291111).
- Maass, Natschläger, Markram, “Real-time computing without stable states,”
  Neural Computation 14 (2002), DOI
  [10.1162/089976602760407955](https://doi.org/10.1162/089976602760407955).
- Rao and Ballard, “Predictive coding in the visual cortex,” Nature 395 (1999),
  DOI [10.1038/4580](https://doi.org/10.1038/4580).
- Benna and Fusi, “Computational principles of synaptic consolidation,” Nature
  Neuroscience 19 (2016), DOI
  [10.1038/nn.4401](https://doi.org/10.1038/nn.4401).
- Kang, “Phase conjugation in nonlinear optical systems,” Optics Letters 15
  (1990), DOI [10.1364/OL.15.000637](https://doi.org/10.1364/OL.15.000637).

## Reference implementation status

The canonical Python reference currently provides:

- `[S, 9*M, B]` multi-scale Yang/Yin state with no learned parameters;
- bounded differential position and velocity evolution;
- temporal imbalance IIR and derived \(J\), \(q\), and \(\chi\) diagnostics;
- distinct fixed prime/quadratic-chirp codebooks for every scale;
- shared-symbol demodulation before cross-scale current and consensus;
- gated phase-conjugate reads, corrections, and fast-to-slow consolidation;
- field-only reset, imagination, and atomic checkpoint round-trip;
- associative KV `assist`, `compress`, and `replace` policies with an
  ephemeral exact-recent ring;
- architecture guards, finite-state checks, and batch isolation tests.

The earlier single-scale F1/F2 slices remain implemented in the pinned
`native/llama.cpp` tree. They add versioned field-only operations without
changing `GGML_OP_CASSI_MODAL`:

```text
GGML_OP_CASSI_FIELD_STEP
GGML_OP_CASSI_FIELD_RESONANCE
```

The F3 loopback daemon now exposes the Qi v2 controller on `127.0.0.1:7600`.
F4 remains an optional frozen L18/Qwen boundary sensor, and F5 consumes compact
Qi diagnostics without persisting teacher data. The ordinary OMP route remains
unchanged.

The deterministic smoke run uses the fixed mapping:

\[
f(x)=(3x+1)\bmod 8.
\]

It compares frozen, trained, and shuffled-target controls and records field
energy, maximum amplitude, finite-state status, and exact field-only restore.
The current multi-scale behavior receipt is
`_diag/qi/behavior-demo.json`. It compares one `[1, 288, 1]` bank with two
`[2, 144, 1]` banks at the same 288-element, 2,304-byte adaptive-state budget.
Across 24 seeded events, including 12 deliberately inverted repeats, the
one-scale control accepted all 12 inverted events at mean gate `1.0`; the
two-scale consensus accepted one at mean gate `0.08333`. Both terminal states
remained finite and bounded. This is measured false-resonance suppression with
conservative abstention, not a claim of improved recall or language quality.

## Adopted runtime boundary

The adopted terminal and provider use `cassi_field_language.py` directly over
one canonical `QiFieldState`. The Yang/Yin field is the only adaptive persistent
tensor. A fixed 260-symbol codec senses prompt boundaries, the Qi law performs
all state evolution and consolidation, and deterministic phase-conjugate
resonance argmax selects output. The emitted symbol is then sensed through the
same fixed boundary and committed into the successor Qi state.

`cassi_conscious_chat.py` persists exactly that Qi state plus bounded
non-adaptive transcript/provenance metadata. `cassi_persistent_provider.py`
gives each session the same state contract. Neither path imports the organism,
conscious-agent stack, learned world model, Qwen runtime, tokenizer, output
head, KV cache, recurrent state, optimizer, engineered feature encoder, or
probabilistic sampler.

The earlier `cassi_conscious_agent.py` and
`cassi_conscious_persistence.py` integration depended on the learned organism
language sector and the conventional learned world-model bridge. It has been
removed from the importable runtime and preserved under
`_diag/cassi-qi-native/obsolete-conscious-stack/` only for source recovery.
`cassi_conscious_field.py`, `cassi_conscious_protocol.py`,
`cassi_conscious_cortex.py`, and `cassi_conscious_world.py` remain offline
research references; none is an adopted language or serving dependency.

This is an inspectable field-owned computation contract, not evidence of
phenomenal consciousness, semantic competence, language quality, autonomous
safety, or real-world agency. An empty textual response terminated by the
field's fixed end-turn symbol is a valid present result; the runtime does not
mask it with a conventional decoder or fallback.

## Native implementation plan

### Stage F0 — Python reference

Required gates:

```text
single-field state shape and finite values
no classical module/parameter surface
fixed-code determinism and collision measurements
phase-conjugate correction changes only field state
field-only checkpoint is exact
frozen versus learned versus shuffled controls
```

### Stage F1 — CPU native operator — complete

The new `GGML_OP_CASSI_FIELD_STEP` accepts contiguous F32 sense waves,
native `[8*M,B]` state, fixed mode symbols, and sequence IDs. It emits a
phase-conjugate flux prefix and the next field state as a live graph output.
The CPU implementation uses the required sense → velocity-first evolution →
phase-conjugate flux order and routes interleaved tokens by sequence ID.

The companion `GGML_OP_CASSI_FIELD_RESONANCE` accepts field state plus fixed
complex probe waves and returns deterministic `[V,B]` resonance scores. It is
a measurement operator, not a learned output map.

### Stage F2 — Vulkan parity — complete

Both field operations have CPU and Vulkan paths, F32/contiguous support
guards, clone paths, backend-meta mirrored handling, deterministic mode
accumulation, and graph-live outputs. Vulkan shader profiles are separate
from the existing modal operator:

```text
cassi_field_step_f32
cassi_field_resonance_f32
```

The parity harness is:

```text
native/llama.cpp/tests/test-cassi-field-step.cpp
```

Its receipt on the RX 7900 XTX is:

```text
short-horizon max_abs_diff:       2.79396772e-09
resonance max_abs_diff:           2.32830644e-10
10,000-event CPU max_abs:         0.110890865
10,000-event Vulkan max_abs:      0.110890865
```

The harness also verifies that both Vulkan devices are discovered and that
the primary field path selects `Vulkan0`.

### Stage F3 — standalone Qi daemon — complete

`cassi_field_daemon.py` owns one fixed `QiFieldController` and one field-only
`QiFieldState` per session. It binds only to `127.0.0.1:7600` and uses strict
newline-delimited UTF-8 JSON under protocol `cassi.field-daemon.v2`:

```text
ping init clear load save reset sense sense_wave step evolve
consolidate emit diagnostics correct state shutdown
```

Requests accept only bounded finite payloads and the declared command fields.
Responses expose compact scalar/per-batch diagnostics and query scores, never
the adaptive field tensor. Save/load uses exact Qi v2 identity and SHA-256
checks and rejects legacy v1 or tampered checkpoints. The TCP-focused test
exercises the complete live protocol, including shutdown.

### Stage F4 — frozen-teacher compatibility mode — complete

`cassi_field_teacher.py` accepts a pinned L18 runtime configuration or a
caller-supplied residual. It performs explicit float64 L2 normalization and
a deterministic parameter-free rFFT lift into a field boundary wave. The
strict daemon command contains only the sense wave; rich audit receipts carry
norm/profile/parity metadata without retaining residuals.

Teacher checkpoints are rejected if they contain teacher state, traces, KV,
logits, or parameters. Teacher mode is a boundary sensor only. It does not
modify the field constitution and does not feed Qwen logits into resonance
emission.

### Stage F5 — controlled provider promotion — complete

`cassi_f5_provider.py` is a separate loopback OpenAI-compatible provider on
port `8083`. It is default-off at process configuration and requires both
`--enable-f5` and an explicit request field `cassi_field_mode: "field"`.
`"baseline"` uses the same pinned Qwen runtime without contacting or mutating
the field daemon; field-mode failure never falls back to baseline.

Each field event captures the frozen teacher boundary, sends the wave to the
F3 daemon, evolves and emits fixed resonance scores, reranks the ordinary
top-16 Qwen candidates through a deterministic byte-fingerprint boundary, and
commits the selected token normally. The field owner is the loopback F3
protocol; no Qwen logits, residuals, KV, traces, or teacher state are stored.
Only the field checkpoint and non-sensitive identity metadata are persisted.

The live receipt from
`run_cassi_f5_demo.py` (`Qwen3.8-27B-Q4_K_M.gguf`, Vulkan0, layer 32,
six generated tokens) records:

```text
field candidate coverage:       0.90625
field candidate collision:      0.03125
field token changes:             1/6
field event count:               6 -> 12 across the restored session
checkpoint identity:             stable
checkpoint hash:                 changed after the second save
teacher data persisted:          false
```

The HTTP endpoint was also exercised through `/health`, `/v1/models`, and
`/v1/chat/completions`; its field receipt changed one of four candidate
selections per request and restored the same field session from its checkpoint.
The declared comparison for that historical F5 receipt is the same-runtime
`baseline` mode. The adopted terminal and port-8086 provider now run the direct
Qi text engine and one `QiFieldState` per session. The F5 and organism-backed
hybrid providers are offline, and Qwen/llama.cpp remains explicit
teacher-and-baseline tooling only.

Promotion requirements:

1. CPU/Vulkan parity.
2. Exact field-only persistence.
3. Long-horizon bounded energy.
4. Frozen/shuffled controls.
7. A standalone provider receipt.
8. A declared comparison against the pinned Qwen teacher/baseline runtime.

All eight requirements are now mechanically exercised by the F0–F5 receipts.
The v3 field-only organism checkpoint is the live conscious terminal and
port-8086 provider. F5 remains an opt-in experimental promotion with a declared
Qwen baseline comparison; it is not the production default.
 

### F5 evidence campaign

The fixed 12-prompt campaign is recorded in
`_diag/f5/f5-evidence-live.json` and
`_diag/f5/f5-evidence-quality.json`. With eight output tokens and the
conservative field weight `0.25`, baseline throughput was `1.5607` tokens/s
and field throughput was `1.4555` tokens/s across two warm repetitions. The
field path therefore added measured overhead in this observatory runtime.
Factuality, coherence, instruction, and paired-task deltas were all
`DOES NOT EMERGE` at this bounded length.

With 32 output tokens and field weight `1.0`, factuality and coherence remained
`DOES NOT EMERGE`; instruction following and the paired task were
`INCONCLUSIVE`. Baseline and field means were `0.3333` and `0.4167` for
instruction following, and the paired 12-prompt score delta was `0.02083`
with bootstrap interval `[0.0, 0.0625]`. The exact sign test had one positive
pair and eleven ties (`p = 1.0`). The human packet is blinded and complete,
but its verdict remains `PENDING_HUMAN_SCORE`.

The provider-side teacher-forced receipt measures ordinary-Qwen baseline
perplexity only (`9.8493` on the five-token continuation); the F5 reranker
does not change Qwen logits, so a field teacher-forced perplexity claim is
`NOT_APPLICABLE_WITH_LOGIT_RERANKER`.

### Single-scale native Qwen graph promotion

The opt-in native flags are `--cassi-field-step` and
`--cassi-field-layer <layer>`, paired with `--no-cassi-modal`. The Qwen35
graph now consumes the selected layer input, runs
`GGML_OP_CASSI_FIELD_STEP`, injects its correction before the LM head, and
queues/restores the field state through a distinct context-state section.
The default graph remains unchanged when the flag is absent.

On the fixed 1,446-token corpus
`_diag/f5/quality_corpus.txt` with two context chunks, native
`llama-perplexity` reported:

```text
baseline: PPL = 1.0283 +/- 0.02290
field:    PPL = 1.0277 +/- 0.02197
```

The intervals overlap substantially; this is a small numerical receipt, not
evidence of a quality gain. The field graph completed successfully and its
measured perplexity difference is `INCONCLUSIVE`.

The blind human packet is intentionally a handoff artifact rather than a
self-scored claim. Human preference requires a scorer to use
`_diag/f5/human-quality/f5-human-preference-packet.json` and record the
corresponding answer key only after scoring.

### Multi-scale Qi native Qwen graph promotion — complete

The opt-in native controls are:

```text
--cassi-qi-field
--cassi-qi-field-layer <layer>
--cassi-qi-field-scales <1..4>
```

They select `GGML_OP_CASSI_QI_FIELD_STEP`, which carries the same nine
components per mode and scale as the Python reference. Qwen35 consumes the
selected layer input, applies the live field correction before the LM head,
and serializes the per-sequence Qi state in a distinct context section. The
baseline graph is unchanged when the flag is absent.

The focused CPU/Vulkan harness ran 10,000 events on the RX 7900 XTX. Its final
receipt was:

```text
one-event max_abs_diff:       5.45696821e-11
10,000-event flux difference: 7.75333722e-4
10,000-event state difference:7.06493855e-4
diagnostic max_abs_diff:      2.21395493e-3
CPU/Vulkan values finite:     true
CPU/Vulkan values bounded:    true
```

The native save/load test also passed full-context restore, sequence-removal
isolation, host sequence migration, and on-device sequence migration. Every
path reproduced the same deterministic eight-token continuation. The Qi
payload accepts a smaller saved sequence set into a larger context, zeroes
unused destination banks, and preserves the public sequence-remapping
contract.

The one-event path agrees to numerical precision; bounded long-horizon drift is
reported rather than hidden. A deterministic live Qwen run on the same prompt
produced coherent, physically correct baseline and Qi answers, while the Qi
trajectory changed and completed within the same 64-token budget. This is a
mechanical generation receipt, not evidence of a language-quality gain.


## Failure modes and falsifiers

### Fixed transducer collision

If distinct boundary events have high fixed-probe correlation, the field cannot
separate them. Measure pairwise correlation, score margin, and candidate
coverage. Do not fix this by silently adding a learned embedding.

### Cross-talk capacity

Distributed phase binding stores several associations in one slow surface. As
load rises, resonance noise can overwhelm the target. This is an architectural
capacity limit. Increase declared mode capacity or change the fixed mode/probe
profile; do not add a learned readout.

### Energy blow-up

Correction can inject energy faster than damping removes it. Reject unstable
profiles using a fixed CFL-like bound, per-event correction cap, rational
saturation, and long-horizon telemetry.

### Attractor collapse

A field that emits one event for every probe has not learned intelligence. The
frozen and shuffled controls, score margins, and event diversity gates must
catch this.

### Semantic insufficiency

A fixed byte transducer can learn a declared symbolic task without becoming a
language model. General text quality requires either sufficient field capacity
and a strong fixed tokenizer/probe boundary or a separately declared frozen
teacher interface. It must not be inferred from a toy successor result.

### Native graph elimination

If the field result is not consumed by an explicit output decision, a backend
may prune the operation or leave it causally irrelevant. In the adopted path,
`QiFieldController.emit` selects the symbol directly, and the emission receipt
is hash-linked to the committed successor Qi state.

## Current decision

The adopted terminal and port-8086 provider now use the direct multi-scale
Yang/Yin Qi state, fixed 260-symbol boundary, deterministic field evolution,
phase-conjugate resonance readout, and one atomic Qi checkpoint per session.
The tied-embedding language head, learned organism language sector, feature
projection, trainer, losses, optimizer, and probabilistic sampler are removed
from the live path. The conventional learned world model and organism research
stack are explicitly offline references. Qwen/llama.cpp remains an offline
teacher, intervention target, and measured displacement baseline only.

The frozen direct-state board reports `FIELD_DEPENDENT`: the live conditioned
field emitted the fixed end-turn symbol, while the zeroed field abstained. A
one-radian scale-0 Yang phase rotation changed state and receipt hashes but did
not change the selected end-turn symbol. The displacement receipt reports one
adaptive persistent Qi tensor; zero learned parameters, neural layers,
optimizer bytes, engineered feature width, or probabilistic sampling; and zero
live Qwen graph, state, weight, output-row, GGUF-open, and teacher counters.

These are mechanical ownership and field-presence results. They do not establish
semantic sensitivity, useful language, phenomenal consciousness, or a
language-quality improvement. Fixed-probe capacity, the abstention/recall
tradeoff, and semantic sufficiency remain exposed limits rather than hidden
neural fallbacks.
