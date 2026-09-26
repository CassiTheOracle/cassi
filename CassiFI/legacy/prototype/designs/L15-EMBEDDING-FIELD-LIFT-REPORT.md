# CassiQwen L15 — Embedding-to-Field Lift Report

## Verdict

**PASS. Geometry classification: SUPPORTS.**

The fixed 1,536-dimensional Fourier codec reconstructed its inputs at step zero within the pre-registered tolerances, the canonical CassiCosmos mind engine accepted byte-identical full-field seeds, and every declared field remained finite and bounded through 2,048 PDE steps (`t=10.24`). The canonical anchor ordering `near > orthogonal > opposite` held at all eight checkpoints.

This is a codec, transport, and long-horizon numerical result. It does not establish semantic quality, action-selection gain, nonlinear field computation, or a reason to alter the default no-field Qwen path.

## Frozen protocol

Pre-registration: `L15-EMBEDDING-FIELD-LIFT-PREREG.md`

The run used:

- `D=1536` real embedding coefficients;
- a shader-native x-fastest `32^3` periodic grid;
- 768 conjugate Fourier-mode pairs;
- `EY=max(s,0)` and `EI=max(-s,0)/phi`;
- canonical `anchor`, `near`, `orthogonal`, and `opposite` vectors;
- shuffled-basis `anchor` and `near` controls;
- one byte-zero control;
- checkpoints `0, 1, 4, 16, 64, 256, 1024, 2048`;
- `dt=0.005`, giving terminal `t=10.24`.

The Qwen server, prompts, weights, logits, sampling, KV cache, and production field adapter were not used or modified.

## Results

### C1 — CPU codec contract: PASS

| Statistic | Measured | Gate |
|---|---:|---:|
| Maximum pairwise-cosine error | `5.319831605733506e-10` | `<= 2e-6` |
| Maximum observed relative-L2 reconstruction error | `6.749143210652746e-9` | `<= 2e-6` |
| Minimum observed input/decoded cosine | `0.9999999999999981` | `>= 0.999999` |
| Repeated encoding | byte-identical | required |

All canonical and shuffled fixture round trips passed. The step-zero energy outside the selected Fourier subspace was approximately `9.1e-16`.

### C2 — GPU full-field seed contract: PASS

All six nonzero step-zero GPU readbacks were byte-identical to their prepared `EY/EI` buffers. Decoding the GPU fields reproduced the CPU C1 result, including maximum pairwise-cosine error `5.319831605733506e-10`. The zero arm was byte-zero.

The canonical engine now exposes an explicit in-process `seed_full_field(EY, EI)` method. It validates the complete input before mutation, uploads `EY/EI/Q`, zeros velocity, density, and the existing scratch buffer, clears pending deposits, and resets step/time without reallocating RIDs or changing the bridge protocol.

### C3 — extended horizon: PASS

Every case was present and finite at every declared checkpoint. The maximum component magnitude over the entire receipt was `0.025971053168177605`, below the frozen bound of `10`. The zero control remained byte-zero through 2,048 steps.

| Horizon | Near cosine | Orthogonal cosine | Opposite cosine | Ordered |
|---:|---:|---:|---:|---|
| 0 | `0.899999999891142` | `2.117977645786575e-10` | `-0.9999999999999978` | yes |
| 16 | `0.9000178936577404` | `-0.0002663004529628175` | `-0.9999999999999997` | yes |
| 256 | `0.8999624938630852` | `0.00038998444064099533` | `-0.9999999999999953` | yes |
| 1024 | `0.8993296252697703` | `0.0074235852966173` | `-0.9999999999999797` | yes |
| 2048 | `0.8976090504838232` | `0.027907707211250538` | `-0.9999999999999547` | yes |

At 2,048 steps, decoded norms were `0.8345944543` for anchor, `0.8358263050` for near, `0.8304121330` for orthogonal, and `0.8345944451` for opposite. The maximum terminal energy outside the selected subspace across the canonical examples was `9.117108663261272e-13`.

The shuffled-basis anchor/near cosine at 2,048 steps was `0.9003017436494961`, versus `0.8976090504838232` for canonical ordering, a difference of `0.002692693165672888`. This is recorded as basis sensitivity only; the protocol assigned it no adoption threshold.

## Independent receipt

Reduced receipt: `embedding-field-lift.json`

Raw artifact hashes:

```text
seed  316919f7641e6dbd1bb947880ee514967dc23a47371837d53059c926269f7bc8
gpu   2d5763993af2e9b1b1649ed302502005d0c925179c391a90e8c080f57e7d1b06
```

`verify_embedding_field_lift.py` independently rebuilt the canonical and shuffled mode orders, decoded the raw float32 GPU fields with NumPy FFTs, checked all C1–C3 gates and hashes, and ended `ALL CHECKS PASSED` with the same terminal geometry.

## Canonical engine regression

The focused windowed `verify_mind_engine` arm passed all 29 checks, including the new Gate H full-field seed contract. Arm 26 also passed in each of three complete 33-arm battery executions.

The complete battery did not produce a 33/33 receipt on this run series:

1. `32/33`: `verify_gravity_modes` failed one timing comparison (`realsim 0.030 ms/step` versus `river 0.026 ms/step`); an immediate standalone recheck passed `58/58`.
2. `32/33`: `verify_gridless_physics` hit its topology timeout; an immediate standalone recheck passed in `2.3 s`.
3. `32/33`: `verify_gravity_modes` failed a different timing comparison (`river-self 0.028 ms/step` versus `river 0.026 ms/step`).

No L15 or mind-engine numerical contract failed. The battery limitation is retained rather than represented as green.

## Evidence tiers

### T1 — Measured

- The fixed Fourier codec round-trips the frozen 1,536-D vector board within C1 tolerances.
- Full-field GPU seed readback is byte-identical at step zero.
- All declared arms remain finite and bounded through 2,048 steps.
- The pre-registered canonical ordering holds at every checkpoint.
- Mode allocation measurably affects the long-horizon similarity by a small amount.

### T2 — Inferred

- A distributed Fourier lift avoids the information loss of reducing one embedding to one `(x,y,z)` deposit.
- The retained ordering is consistent with the existing linear two-fluid operator acting as a stable spectral transform on this synthetic board.

### T3 — Not established

- No model-native semantic embeddings were evaluated.
- No retrieval, correction, generation, or arbitration improvement was measured.
- No nonlinear computation was demonstrated; the current raster two-fluid operator is linear in `EY/EI`.
- No compatibility between Qwen embeddings and the Gemma/TRELLIS gate-vector space was shown.
- No production write path or Qwen intervention is authorized.

## Disposition

Retain the codec, generic full-field seed API, extended-horizon probe, reduced receipt, and independent verifier as a default-off experimental capability. The operational Qwen path remains field-off. A later semantic experiment must freeze one exact model-native embedding source and compare evolved-field output against raw cosine, no evolution, and matched linear baselines before any adoption claim.
