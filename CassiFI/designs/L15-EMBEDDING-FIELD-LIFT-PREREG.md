# CassiQwen L15 — Embedding-to-Field Lift Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-21

## Question

Can a finite model embedding be lifted into the existing CassiCosmos raster two-fluid state without a three-coordinate bottleneck, reconstructed from the signed field imbalance at step zero, and evolved through substantially longer horizons than the 16-step L11c/L14 probes without non-finite or unbounded state?

This is a codec, transport, and numerical-stability probe. It is not a semantic-quality, action-selection, Qwen-intervention, nonlinear-computation, or production-adoption experiment. The current `cassi_two_fluid.glsl` operator is linear in `EY` and `EI`; any benefit beyond a conventional linear transform is outside this protocol.

## Fixed codec

- embedding dimension: `D=1536`;
- grid: `N=32`, `V=N^3=32768`;
- field amplitude: `alpha=1`;
- Cassi ratio: `phi=1.618033988749895`;
- flat GPU layout: shader-native x-fastest `i = x + N*(y + N*z)`;
- transform arithmetic: float64 Fourier construction followed by one float32 rounding at the signed-volume boundary;
- field storage: float32 `EY` and `EI`.

Each finite nonzero input is L2-normalized. Consecutive embedding coefficient pairs are assigned to unique non-self-conjugate periodic 3D Fourier modes. Candidate modes are sorted by squared wrapped wave number, then signed `(kz,ky,kx)`, with one representative retained from each conjugate pair. For coefficients `(a,b)` at mode `k`, the complex spectrum is

```text
X[k]  = sqrt(V/2) * (a - i*b)
X[-k] = conjugate(X[k])
```

and a normalized inverse 3D FFT produces the real signed volume `s`. The two-fluid split is

```text
EY = max(s, 0)
EI = max(-s, 0) / phi
```

so `epsilon = EY - phi*EI = s` over real arithmetic. Float32 channel storage makes the negative branch ULP-close rather than byte-exact; exactness is judged by the frozen tolerances below.

Decoding computes `epsilon` from float32 `EY/EI`, applies the forward 3D FFT, and reads the same selected Fourier coefficients. The shuffled control uses the same codec and decoder after a deterministic Fisher-Yates permutation of the selected mode list with seed `0x51f71e1d`.

## Fixed vector board

A deterministic xorshift32/Box-Muller stream with seed `0x0c4551` generates three vectors. Gram-Schmidt produces orthonormal vectors `a`, `u`, and `v`. The board is:

1. `anchor = a`;
2. `near = 0.9*a + sqrt(1-0.9^2)*u`;
3. `orthogonal = v`;
4. `opposite = -a`.

The expected anchor cosines are therefore `1`, `0.9`, `0`, and `-1`, subject only to float32 fixture rounding. A separate zero-volume control contains no embedding.

## GPU arms and horizons

The existing canonical `cassi_mind_engine.gd` runs with `N=32`, `dt=0.005`, `auto_step=false`, `serve_bridge=false`, source strength zero, and Hamiltonian completion off.

Arms:

1. canonical basis: `anchor`, `near`, `orthogonal`, `opposite`;
2. shuffled basis control: `anchor`, `near`;
3. exact zero-field control.

Every arm starts from a full-buffer seed that resets field, velocity, density, pending deposits, step, and time. No TCP mutation or Qwen request is used.

Cumulative checkpoints are frozen at:

```text
0, 1, 4, 16, 64, 256, 1024, 2048 PDE steps
```

At `dt=0.005`, the terminal checkpoint is `t=10.24`, 128 times the L14 step horizon.

Each checkpoint records raw float32 `EY/EI`, step, time, field norms, maximum absolute component, and finiteness. Analysis decodes the embedding coefficients and records reconstruction error, decoded norm, pairwise cosine geometry, and energy outside the encoded Fourier subspace.

## Artifacts

Prepared seed:

```text
CassiCosmos/_diag/cassi_qwen_embedding_field_seed.json
```

Raw GPU receipt:

```text
CassiCosmos/_diag/cassi_qwen_embedding_field_gpu.json
```

Reduced analyzed receipt:

```text
CassiFI/artifacts/native/embedding-field-lift.json
```

The `_diag` artifacts retain full float32 fields as base64 and are the numerical source of truth. The reduced receipt must contain hashes of both raw artifacts.

## Gates and decision tree

### C1 — CPU codec contract

For every nonzero fixture at step zero:

- decoded cosine with the input is at least `0.999999`;
- relative L2 reconstruction error is at most `2e-6`;
- maximum pairwise-cosine error is at most `2e-6`;
- repeated encoding with the same basis is byte-identical;
- malformed, non-finite, zero-norm, wrong-size, and capacity-exceeding inputs are rejected.

### C2 — GPU seed contract

At the GPU step-zero checkpoint:

- shape is exactly `N^3` for both channels;
- all values are finite;
- decoded cosine, relative L2 error, and pairwise-cosine error satisfy C1;
- step and time are exactly zero;
- the zero control is byte-zero in both channels.

### C3 — extended-horizon contract

At every declared checkpoint:

- reported step equals the checkpoint;
- `abs(t - step*dt) <= 1e-6`;
- all raw field values and derived metrics are finite;
- `max(abs(EY), abs(EI)) <= 10`;
- every required arm and checkpoint is present;
- the zero control remains byte-zero.

### Geometry classification

If C1–C3 pass and all canonical decoded norms remain above `1e-6`:

- `SUPPORTS` if anchor similarity remains ordered `near > orthogonal > opposite` at every checkpoint;
- `CONTRADICTS` if that ordering reverses at any checkpoint;
- `INCONCLUSIVE` if a decoded norm falls to or below `1e-6`.

The shuffled-basis arm is a sensitivity control and is reported without an adoption threshold. No result in this protocol establishes semantic or action-quality benefit.

### Overall stage verdict

1. Missing/malformed artifacts, setup failure, wrong checkpoint semantics, non-finite state, or bound failure: `INVALID`.
2. A valid run that fails C1 or C2: `FAIL`.
3. C1, C2, and C3 all pass: `PASS`, accompanied by the separate geometry classification.

## Stopping rule

Run one deterministic preparation, the first complete windowed GPU receipt, one Node analysis, and one independent NumPy verification. A launch that produces no complete numerical receipt may be repaired without changing this protocol; no codec constant, vector, mode order, horizon, tolerance, or decision threshold changes after any valid numerical checkpoint is observed. No parameter sweep, Qwen call, prompt change, model-weight change, or production field wiring is permitted.

The canonical engine API regression is checked separately with the windowed `verify_mind_engine` arm and the full 33-arm battery. Those regression results do not change the L15 scientific verdict.
