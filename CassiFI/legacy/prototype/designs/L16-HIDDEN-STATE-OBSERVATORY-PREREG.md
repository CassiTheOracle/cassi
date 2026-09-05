# CassiQwen L16 — Qwen Hidden-State Field Observatory Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-22

## Question

Can the installed, hash-pinned Qwen3.8-27B GGUF expose one model-native intermediate residual state during ordinary llama.cpp Vulkan prompt inference, with capture disabled/enabled logits agreeing under a declared parity contract, and can that captured 5,120-dimensional state be transported through the default-off CassiCosmos two-fluid field codec through the same extended horizons as L15?

This is a read-only observatory and field-transport experiment. It does not inject an activation, alter weights, write KV cache state, modify the production server, expose a network endpoint, measure answer quality, or establish a semantic, retrieval, generation, or Cassi-specific computational benefit.

## Frozen runtime identity

| Field | Value |
|---|---|
| GGUF | `Qwen3.8-27B-Q4_K_M.gguf` |
| GGUF SHA-256 | `7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169` |
| Architecture | `qwen35` |
| llama.cpp build | `b10472`, commit `60eeeb608` |
| Local runtime | `CassiQwen/llama.dll` and sibling Vulkan DLLs |
| Production lane | Existing `llama-server.exe`, unchanged and field-off |

The lab probe dynamically binds only the local installed DLL. It validates `llama_version() == "0.1.1-dev"`, `llama_model_n_embd() == 5120`, finite hidden values, the GGUF SHA-256, and `0 < n_layer`; it records the local DLL SHA-256 and the exact resolved WIP export names. The b10472/commit identifier is pinned by the retained package receipt rather than claimed as a value returned by `llama_version()`. Any checked identity mismatch is `INVALID`.

## Capture contract

The native-layer API is the installed b10472 WIP API:

```cpp
llama_set_embeddings_layer_inp(ctx, layer_id, true);
llama_decode(ctx, prompt_batch);
llama_get_embeddings_layer_inp(ctx, layer_id);
```

It captures the **input residual stream of `layer_id`**. The selected layer is frozen by rule:

```text
layer_id = floor(llama_model_n_layer(model) / 2)
```

The probe captures the row for the final token of this one exact UTF-8 prompt:

```text
Cassi hidden-state observatory: reply with exactly one physical field name.
```

Tokenization uses `add_special=true` and `parse_special=true`. The prompt prefill is one ordinary causal `llama_decode` call, with all model layers requested for GPU offload and context/batch capacity fixed to 512 tokens. The probe records prompt bytes and SHA-256, token IDs, selected token index/id, model layer count, selected layer index, model width, runtime version, backend request, and float32 little-endian raw state.

A capture-off context and an otherwise-identical capture-on context are separately created from the same loaded model. They process the same token batch. The probe records full float32 logit SHA-256s, final-prompt argmax, top-16 token IDs/logits, and the maximum absolute logit difference.

### H1 — capture parity gate

- both contexts return normal decode completion;
- final-prompt argmax token IDs agree;
- top-16 token IDs agree at each rank;
- maximum absolute logit difference is at most `1e-6`;
- one capture-on hidden row has exactly 5,120 finite float32 values and nonzero L2 norm.

A failure is `FAIL`; malformed loading, ABI, metadata, output shape, or artifact conditions are `INVALID`.

## Hidden-state codec

The L16 codec uses `N=32`, `V=32768`, `D=5120`, `2560` real Fourier conjugate pairs, shader-native x-fastest layout `x + N*(y + N*z)`, `phi=1.618033988749895`, and unit field amplitude.

The raw state `h` is decomposed without loss at step zero:

```text
norm = ||h||_2
u = h / norm
```

Only unit direction `u` is lifted into the field. `norm` is an immutable scalar carried in the seed and reapplied after decoding. This avoids treating arbitrary model activation amplitude as a PDE drive while preserving original hidden-state scale for every decoded comparison:

```text
h_hat = norm * decode(EY, EI)
```

The split is:

```text
EY = max(s, 0)
EI = max(-s, 0) / phi
```

The experiment has three field arms:

1. `hidden_canonical`: captured residual, canonical low-wave-number mode order;
2. `hidden_shuffled`: same captured residual, deterministic Fisher–Yates mode permutation with L15 seed `0x51f71e1d`;
3. `zero`: byte-zero control.

No model receives a decoded field state.

## GPU horizons and artifacts

The canonical `cassi_mind_engine.gd` is instantiated with `N=32`, `dt=0.005`, `auto_step=false`, `serve_bridge=false`, zero source strength, and Hamiltonian completion off.

Frozen cumulative checkpoints:

```text
0, 1, 4, 16, 64, 256, 1024, 2048 PDE steps
```

The terminal horizon is `t=10.24`.

Artifacts:

```text
CassiFI/artifacts/native/hidden-state-capture.json
CassiCosmos/_diag/cassi_qwen_hidden_state_field_seed.json
CassiCosmos/_diag/cassi_qwen_hidden_state_field_gpu.json
CassiFI/artifacts/native/hidden-state-field-observatory.json
```

The capture receipt and seed contain the raw hidden state as base64 float32 little-endian. The GPU receipt contains raw `EY/EI` fields as base64 float32 little-endian. All numeric artifacts are written before process exit.

## Gates

### H2 — codec and GPU seed contract

For canonical and shuffled arms at CPU step zero and GPU step zero:

- restored hidden cosine with captured raw hidden is at least `0.999999`;
- restored relative L2 error is at most `2e-6`;
- GPU `EY/EI` are byte-identical to prepared seed fields at step zero;
- GPU step/time are exactly `0/0` within `1e-6` time tolerance;
- zero control is byte-zero.

### H3 — extended-horizon transport contract

At every arm and declared checkpoint:

- reported step equals the checkpoint;
- `abs(t - step*dt) <= 1e-6`;
- raw `EY/EI` and all derived values are finite;
- `max(abs(EY), abs(EI)) <= 10`;
- zero control remains byte-zero.

The reduced receipt reports normalized-direction cosine, restored-hidden cosine, restored relative L2 error, decoded norm, and energy outside the selected Fourier subspace at every checkpoint. Those trajectory values are descriptive; this protocol sets no semantic or intervention threshold.

### Stage verdict

1. Missing/malformed artifact, runtime identity mismatch, failed normal inference, wrong hidden shape, or H3 failure: `INVALID`.
2. Valid capture that fails H1 or H2: `FAIL`.
3. H1, H2, and H3 pass: `PASS`.

## Controls and stopping rule

The capture-off parity arm, capture-on arm, shuffled basis, canonical basis, and zero field are required. There is no retry, prompt change, layer change, model change, basis sweep, horizon sweep, decoding intervention, or server patch after a valid numerical capture. One repair is allowed only if no complete H1 receipt exists. Run one capture, one GPU receipt, one Node analysis, and one independent NumPy verification.

A later causal intervention requires a separate protocol and must compare no intervention, zero evolution, matched-norm static residual addition, shuffled modes, and a matched linear baseline. L16 grants no authority for that work.
