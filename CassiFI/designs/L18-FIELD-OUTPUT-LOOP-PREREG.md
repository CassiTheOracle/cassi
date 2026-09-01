# CassiQwen L18 field-output loop

## Status: AMENDED BEFORE FIRST VALID RUN — 2026-08-22

## Purpose

Build an experimental, model-native path from the complete hidden-state trajectory of each generated token into the next generated token. L18 is an exploration system, not a quality claim or a production integration.

## Core loop

For each ordinary generated token `t`:

1. capture all 64 layer-input residuals `h[t,l]` and the public final-output feature reference `z[t] = llama_get_embeddings_ith(t)` from the pinned local Qwen runtime;
2. normalize and Fourier-lift the 64 trunk residual directions into the `N=32` Cassi field layout;
3. blend each layer into one persistent field with retained weight `0.9`, then run four existing two-fluid PDE steps;
4. read back and decode the terminal field into a 5,120-dimensional field vector `m[t]`;
5. apply the frozen Qwen output RMS norm to `m[t]`, form the field-augmented output features `r[t] = z[t] + 0.15 * RMSNorm(m[t])`, then apply Q6_K `output.weight` directly to `r[t]` to produce output logits;
6. select one output token from those field-augmented logits, commit it as an ordinary Qwen token, and repeat.

The installed WIP layer API toggles/captures only the 64 trunk inputs. Its nominal layer-64 tap asserts during graph reservation in this pinned runtime, so L18 uses the documented public final-output embedding API as its separate output reference. The primary output seam is Qwen's frozen `output.weight` applied to field-augmented normalized output features. A secondary `llama_batch.embd` virtual-token bridge is included as an optional full-forward experimental mode, not misrepresented as a final-residual hook.

## Frozen first run

| Item | Value |
|---|---|
| Model | `Qwen3.8-27B-Q4_K_M.gguf`, SHA-256 `7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169` |
| Runtime | local llama.cpp b10472 / commit `60eeeb608`, Vulkan, 99 requested GPU layers |
| Field | `N=32`, `D=5120`, `phi=1.618033988749895`, x-fastest `x + N*(y + N*z)` layout |
| Depth recurrence | retained weight `0.9`, four PDE steps per layer |
| Token recurrence | one field state persists through the entire generated sequence |
| Output seam | field-augmented public final-output features passed through frozen Q6_K `output.weight`; optional virtual embedding mode |
| Default coupling | `0.15` times the normalized field output features |
| Output mode | field-augmented residual greedy token selection |
| First sequence limit | four committed generated tokens |
| Field engine | new windowed L18 lab scene, direct child engine, bridge disabled |

## Lab systems

Each generated-token event records:

- all trunk vectors, the public final-output feature reference, identities, norms, and hashes;
- field updates, state, and terminal EY/EI raw hashes;
- ordinary, field-only, field-augmented-output-feature, and optional virtual-embedding top-k logits;
- candidate ranks, selected token ID/piece, retrieval records, and a token-level plan;
- field-decoded vector metadata, output-feature metadata, output-head metadata, and optional virtual-embedding metadata;
- a JSONL live event and a final receipt.

The candidate selector ranks field-augmented output-feature vocabulary candidates. The field language head is the frozen Qwen `output_norm` plus `output.weight` evaluated on the decoded field vector; the residual output seam adds its normalized field features to the public final-output reference before `output.weight`. Memory retrieval is cosine search over earlier decoded field states and optional user-supplied memory records. The planner emits an explicit token-level candidate plan and only commits the selected language token; it has no external action interface.

## Mechanical verdict

The run is `PASS` when the model and windowed field lab complete the declared sequence with 64 finite trunk residuals plus one finite public final-output reference per committed token, a finite field readout after every depth recurrence, a finite 5,120-D decoded field vector, finite field-only and field-augmented logits, stable receipt hashes, and a nonempty generated token sequence. It is `FAIL` on a model, transport, field, decode, output-head, or output-seam error. Output quality, truth, usefulness, or semantic benefit are observations, not L18 verdict conditions.

## Stop rule

If the first run fails the mechanical contract, preserve its raw failure receipt and repair the named transport/ABI/field defect before changing coupling, prompt, recurrence, output mode, or sequence length. After a valid receipt, subsequent exploratory parameter changes use a new recorded run configuration.
