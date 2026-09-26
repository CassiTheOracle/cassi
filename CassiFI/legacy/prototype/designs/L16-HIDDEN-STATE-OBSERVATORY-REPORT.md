# CassiQwen L16 — Qwen Hidden-State Field Observatory Report

## Verdict

**PASS.**

The installed Qwen3.8-27B llama.cpp runtime exposed a real 5,120-float intermediate residual during ordinary Vulkan prompt inference through the b10472 layer-input capture API. Capture-off and capture-on inference produced identical final-prompt logits under the frozen parity metric. The captured residual round-tripped through the `32^3` CassiCosmos two-fluid field at step zero and remained finite, bounded, and in the selected Fourier subspace through 2,048 PDE steps (`t=10.24`).

This is a read-only capture and transport result. It does not measure model quality, semantic preservation, retrieval, correction, generation, or a benefit from feeding an evolved state back into Qwen. No Qwen activation, weight, KV state, prompt, logit, sample, server route, or production field adapter was modified.

## Frozen runtime receipt

| Field | Measured value |
|---|---|
| GGUF | `Qwen3.8-27B-Q4_K_M.gguf` |
| GGUF SHA-256 | `7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169` |
| Architecture | `qwen35` |
| llama.cpp package | b10472, receipt-pinned commit `60eeeb608` |
| `llama_version()` | `0.1.1-dev` |
| Device | Vulkan0, AMD Radeon RX 7900 XTX |
| Requested GPU layers | `99` |
| Model layer count | `64` |
| Hidden width | `5120` |
| Captured hook | input residual of layer `32` |
| Prompt tokens | `15` |
| Captured row | final prompt-token row `14` |
| Raw hidden L2 norm | `87.89932483616994` |

The probe resolved and recorded the exact local DLL exports:

```text
?llama_set_embeddings_layer_inp@@YAXPEAUllama_context@@I_N@Z
?llama_get_embeddings_layer_inp@@YAPEAMPEAUllama_context@@I@Z
```

The model was run in two fresh, otherwise-identical contexts. The capture-enabled context requested the selected layer input before normal causal prompt decode and copied the final prompt-token row after decode. It did not supply any model input beyond the frozen token batch.

## H1 — capture parity: PASS

| Statistic | Measured | Gate |
|---|---:|---:|
| Final-prompt argmax token | `271` in both arms | equal |
| Top-16 token IDs | rank-identical | equal at every rank |
| Maximum absolute logit difference | `0` | `<= 1e-6` |
| Captured state | 5,120 finite float32 values | required |
| Captured L2 norm | `87.89932483616994` | finite and positive |

This is direct evidence that enabling the read-only layer-input extraction did not perturb this measured inference output under the frozen setup.

## H2 — codec and GPU seed transport: PASS

The codec stores direction and norm separately:

$$
\mathbf u = \frac{\mathbf h}{\lVert\mathbf h\rVert_2},
\qquad
\hat{\mathbf h}=\lVert\mathbf h\rVert_2\,\mathrm{decode}(E_Y,E_I).
$$

The 5,120 directional coefficients use 2,560 conjugate pairs in the shader-native x-fastest `32^3` Fourier lattice. The norm is a receipt sidecar, not an unbounded PDE drive.

| Arm | Restored cosine at CPU step zero | Relative L2 error | GPU `EY/EI` step-zero seed |
|---|---:|---:|---|
| Canonical modes | `0.9999999999999986` | `1.2026532906563381e-8` | byte-identical |
| Shuffled modes | `0.9999999999999999` | `1.2306745058146607e-8` | byte-identical |

Selected-subspace residual energy at step zero was `8.178434102551063e-16` for canonical mode order and `8.02142141110199e-16` for shuffled order.

## H3 — extended-horizon field transport: PASS

All three arms—canonical hidden state, shuffled hidden state, and byte-zero control—were evaluated at:

```text
0, 1, 4, 16, 64, 256, 1024, 2048 steps
```

with `dt=0.005`. The terminal time is `t=10.24`.

| Statistic | Measured |
|---|---:|
| Largest `abs(EY)` or `abs(EI)` across all arms/checkpoints | `0.02008778415620327` |
| Frozen field bound | `10` |
| Finite arm/checkpoint receipts | `24 / 24` |
| Zero control | byte-zero at all eight checkpoints |
| Maximum terminal canonical subspace residual energy | `7.4443919642828e-13` |
| Maximum terminal shuffled subspace residual energy | `5.95849428140721e-13` |

The field trajectory is phase-bearing rather than an identity transform. The canonical direction has cosine `-0.9998884165232709` at step 64 and `-0.9999983054589299` at step 256, then returns to `0.9932782947573974` at step 2,048. Its terminal decoded-direction norm is `0.8155214422698209`; its restored relative L2 error is `0.21212196437456077`.

The shuffled control follows a closely related phase path, ending with direction cosine `0.9930712834504198`, decoded-direction norm `0.9419618689958222`, and restored relative L2 error `0.12814678393165124`.

Those values are descriptive, as pre-registered. They demonstrate that the exact hidden residual can be carried through the field and decoded after extended evolution; they do not show semantic preservation at every time, nor do they authorize applying the decoded state to the model.

## Independent verification

`verify_l16_hidden_state_observatory.py` independently:

1. validates capture metadata, raw float32 byte hashes, hidden norm, top-16 ranking, and parity;
2. reconstructs the canonical and shuffled mode orders with NumPy;
3. decodes all raw `EY/EI` fields under x-fastest layout;
4. checks H1/H2/H3, step/time, bounds, zero control, GPU step-zero bytes, and receipt hashes;
5. ends `ALL CHECKS PASSED`.

Raw artifact hashes:

```text
capture 920e1b3a645555247794a6e36acb7f918978dbb96f87ae54a43f25e577d6c805
seed    f9d72952de143646221b7cde895542ffa9b43ead95677c1f3ae125b0859d6326
gpu     a552224bfd5eaeb3a9feb5fe08eb520f7ece4e0763883fb678f0689163b09ddb
```

## Evidence boundaries

### T1 — measured

- Local llama.cpp inference exposed the selected Qwen layer input residual through the installed WIP API.
- The capture hook left the frozen final-prompt logits unchanged.
- The full 5,120-D residual transported into and out of the field within H2 tolerances at step zero.
- All declared field trajectories were finite, bounded, and retained negligible energy outside their selected Fourier subspaces through 2,048 steps.
- The field trajectory changes phase and amplitude over time; the raw residual is not invariant through evolution.

### T2 — inferred

- A full model-native hidden state can use the CassiCosmos field as a reversible-at-initialization transport coordinate system without the prior three-coordinate deposit bottleneck.
- The separated norm sidecar avoids injecting arbitrary activation magnitude as a field drive while allowing scale-aware readout comparisons.

### T3 — not established

- Whether any horizon improves next-token prediction, correction, retrieval, or generation.
- Whether a decoded state can be safely reintroduced at this or any model hook.
- Whether behavior exceeds matched linear, no-evolution, or static residual baselines.
- A semantic meaning for Yang versus Yin channels or for raw hidden-dimension ordering.
- Any production Qwen/CassiCore integration.

## Disposition

Keep the hidden-state probe, 5,120-D codec path, L16 field scene, raw receipts, and independent verifier as a read-only lab capability. The production Qwen path remains field-off, and the local server remains a separate launcher. Any transient hidden-state intervention requires a new pre-registration with model-output parity, no-evolution, shuffled-basis, matched-norm static-residual, and matched-linear controls.
