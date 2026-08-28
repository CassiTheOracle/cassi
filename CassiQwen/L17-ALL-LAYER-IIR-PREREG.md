# CassiQwen L17 — All-Layer Residual IIR Field Observatory Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-22

## Question

Can one ordinary Vulkan prefill of the pinned Qwen3.8-27B model expose the final-prompt-token input residual for **every model layer**, and can those residuals drive one persistent CassiCosmos field in model-layer order through a stable infinite-impulse-response recurrence?

This is a read-only model observatory and a default-off field-memory experiment. It does not return a field state to Qwen, change an activation, patch model code or weights, alter KV state, add a server endpoint, or measure output quality.

## Frozen runtime and capture

The model, GGUF hash, runtime package, prompt bytes, tokenizer settings, GPU request, and output-parity contract are the L16 values in `L16-HIDDEN-STATE-OBSERVATORY-PREREG.md`.

The probe enables the installed b10472 WIP layer-input hook for every `layer_id` in:

```text
0, 1, ..., llama_model_n_layer(model) - 1
```

in one capture-on ordinary causal prompt decode. It copies the final prompt-token row from every enabled capture buffer. The expected model has 64 layers and width 5,120; a layer-count or width mismatch is `INVALID`.

The capture-off control uses the identical model and token batch with no enabled layer hooks. H1 passes only if:

- both decode calls complete normally;
- final-prompt argmax IDs agree;
- top-16 token IDs agree at every rank;
- maximum absolute difference across full float32 logits is at most `1e-6`;
- exactly one finite, nonzero 5,120-float state is present for every model layer;
- every capture buffer is identified by its true layer index and final prompt-token row.

The raw capture artifact is:

```text
CassiQwen/all-layer-hidden-state-capture.json
```

## Frozen field recurrence

Each layer state $h_l$ carries a separate finite norm and unit direction:

$$
r_l=\lVert h_l\rVert_2,
\qquad
u_l=h_l/r_l.
$$

Only $
u_l$ is encoded as a `D=5120`, `N=32` periodic Fourier field. Norms remain measured sidecar metadata; no raw model-state norm drives the PDE.

The persistent field starts byte-zero. For model layers in the specified order, with `retained_weight=0.9`, the generic full-field blend is:

$$
E_Y^{(l,+)}=0.9E_Y^{(l-1)}+0.1E_Y(\nu_l),
$$

$$
E_I^{(l,+)}=0.9E_I^{(l-1)}+0.1E_I(\nu_l).
$$

The canonical engine then advances exactly four existing PDE steps:

$$
F_l=P^4(F_l^+).
$$

This defines the IIR field state. The blend preserves current field clock, velocity, density, and scratch buffers; it replaces only canonical `EY/EI/Q` after validating every incoming value and the weight. It is default-off and is not reachable through TCP.

The ordinary CPU baseline is the same stable recurrence on raw unit directions:

$$
b_l=0.9b_{l-1}+0.1\nu_l.
$$

No baseline is represented as a Cassi claim.

## Arms

All arms use the same captured states, `phi=1.618033988749895`, unit field amplitude, `dt=0.005`, and 4 PDE steps per layer.

1. `forward_canonical`: layer order `0→63`, canonical Fourier mode order;
2. `reverse_canonical`: layer order `63→0`, canonical Fourier mode order;
3. `forward_shuffled`: layer order `0→63`, deterministic L15 shuffled Fourier order (`0x51f71e1d`);
4. `zero`: 64 zero full-field blends in forward layer count.

The reverse arm is a temporal-order control. The shuffled arm is a coordinate-allocation control. Neither is a model intervention.

After the 64th IIR update, each nonzero arm has a frozen continuation at cumulative additional horizons:

```text
0, 1, 4, 16, 64 PDE steps
```

Layer-update checkpoints are frozen at layer indices:

```text
0, 1, 2, 3, 7, 15, 31, 47, 63
```

## Artifacts

```text
CassiQwen/all-layer-hidden-state-capture.json
CassiCosmos/_diag/cassi_qwen_all_layer_iir_seed.json
CassiCosmos/_diag/cassi_qwen_all_layer_iir_gpu.json
CassiQwen/all-layer-iir-observatory.json
```

The seed contains raw `EY/EI` float32 little-endian base64 for every captured layer in canonical and shuffled bases. The GPU receipt retains raw field arrays for every frozen layer and continuation checkpoint, plus every-layer summary rows. Artifacts are written before exit.

## Gates

### H2 — seed and IIR blend contract

- all 64 canonical and shuffled CPU codec round trips have restored hidden cosine `>=0.999999` and relative L2 error `<=2e-6`;
- engine `blend_full_field` preserves the clock and rejects invalid input without mutation;
- each GPU first blend has the exact declared 90/10 channel mix of byte-zero field and first input, within float32 `2e-6` relative tolerance;
- zero arm remains byte-zero after every blend and PDE step.

### H3 — all-layer numerical transport contract

At every arm/layer/continuation checkpoint:

- field shape is exactly `N^3` per channel;
- reported layer count and PDE step/time obey the frozen recurrence;
- all raw/derived values are finite;
- `max(abs(EY), abs(EI)) <= 10`;
- selected raw checkpoint fields agree with their summaries;
- zero control remains byte-zero.

### H4 — temporal-order sensitivity

At the terminal pre-continuation state, let $F$ and $R$ be decoded directions of forward and reverse canonical arms. The receipt reports:

$$
\cos(F,R).
$$

- `SUPPORTS` if `1 - cosine >= 1e-4` while H1–H3 pass;
- `NULL` if `1 - cosine < 1e-4` while H1–H3 pass;
- `INVALID` if a prerequisite gate fails.

This gate asks only whether the declared recurrent field distinguishes layer order. It does not establish that the distinction is useful or causal for language behavior.

### Stage verdict

1. Missing/malformed artifacts, wrong runtime/capture shape, failed decode, non-finite state, clock/bound/zero failure: `INVALID`.
2. Valid artifacts that fail H1/H2: `FAIL`.
3. H1/H2/H3 pass: `PASS`, accompanied by H4 `SUPPORTS` or `NULL`.

## Stopping rule

Run one all-layer capture, one windowed GPU receipt, one Node analysis, and one independent NumPy verifier. Repair is permitted only if no complete numerical receipt exists. No prompt, model, capture layer set, weight, layer order, Fourier allocation, recurrence weight, step count, continuation horizon, or threshold changes after a valid H1 capture. No field state is ever injected into Qwen under L17.
