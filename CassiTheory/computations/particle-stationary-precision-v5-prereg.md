# Particle Stationary Precision Continuation Campaign

## Status: Preregistered—September 2026

## Abstract

This campaign applies a deterministic, bounded continuation to the selected
`P:separated_core` finite-grid particle background. It seeks a physical
first-variation RMS of at most $1.20\times10^{-4}$ while preserving PA32 gates
Q1–Q4. The coefficient point, charge, field class, grid, boundary values,
$C_4$ projector, finite-difference stencil, quadrature, source artifact, and
optimizer family are fixed. The first qualifying endpoint from at most eight
fresh strong-Wolfe L-BFGS blocks is selected.

The source-coordinate threshold is an acquisition target. A separately frozen
PA42 campaign must recompute and pass the physical-quotient augmented-gradient
preflight before any eigenvalue calculation.

## 1. Question and target

The registered question is whether the fixed initial condition reaches

$$
\boxed{
\|\delta\widehat E\|_{\mathrm{source,RMS}}
\le 1.20\times10^{-4}
}
\tag{HP1}
$$

with Q1–Q4 all passing.

The published PA42 quotient has dimension $13622$ and its source diagnostic
uses $15^3\times17=57375$ components. The normalization factor is

$$
s=\sqrt{\frac{57375}{13622}}=2.052300119747167.
\tag{HP2}
$$

Thus the PA42 limit $3\times10^{-4}$ corresponds algebraically to
$1.461774371688562\times10^{-4}$ in the source normalization. The stricter
campaign target gives

$$
s(1.20\times10^{-4})=2.462760143696600\times10^{-4},
\tag{HP3}
$$

approximately $18\%$ below that limit. This estimate motivates the acquisition
target. The successor PA42 preflight remains the decision authority; the
scaling does not establish that normalization is the sole contribution to its
augmented gradient.

## 2. Frozen initial condition

The sole initial condition is:

- artifact:
  `runs/20260902_particle_stationary_q2_recovery_v2/fields_P_separated_core.npz`;
- SHA-256:
  `99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550`;
- family and basin: `P:separated_core`;
- grid: $(R,N,\Delta x,\Delta V)=(4,17,0.5,0.125)$;
- charge: $Q_C=4$;
- physical energy: $3.8542001269281165$;
- source physical-gradient RMS:
  $1.936974511462466\times10^{-4}$;
- source cutoff virial: $1.891010204220114\times10^{-3}$;
- carrier multiplier:
  $\widehat\omega_C=0.9619135625713447$.

No random number generator is used. The hash-bound artifact is the complete
seed field.

The NPZ contains finite, C-contiguous `float64` arrays:

| Key | Shape |
|---|---:|
| `x` | `(17,)` |
| `psi_real` | `(17,17,17,2)` |
| `psi_imag` | `(17,17,17,2)` |
| `h` | `(17,17,17,3)` |
| `a` | `(17,17,17,3,3)` |
| `c` | `(17,17,17)` |

The fixed shell is

$$
\psi=(\varphi^{-1/2},\varphi^{-1}),\qquad
h=(0,0,1),\qquad a=0,\qquad c=0,
\tag{HP4}
$$

with zero `psi_imag`.

## 3. Frozen physical and numerical problem

The campaign uses the PA32 dimensionless static functional and physical field
map in `computations/particle_stationary_bvp.py` at

$$
\alpha_{\mathfrak s}=\gamma_x=\gamma_{\mathfrak s}
=k_{C x}=k_{C\mathfrak s}=u_C=u_{\rho}=u_{\varphi}=u_H=1,
\quad e_C=0.75,\quad h_C=1.50,\quad q_C=4,
\quad \xi_g=1.
\tag{HP5}
$$

The no-flux scale sector remains active, $a_0=a_0^{\mathfrak s}=0$. The exact
numerical operator uses:

- `torch.gradient` at spacing $0.5$, including its one-sided boundary stencil;
- uniform volume weight $\Delta V=0.125$;
- the source $C_4$ projection order;
- fixed shell masks;
- the carrier softplus map followed by exact $Q_C=4$ normalization;
- deterministic `float64` computation on the exposed ROCm device.

The optimizer minimizes

$$
\widehat E_{\mathrm{objective}}
=\widehat E_{\mathrm{physical}}+\widehat E_{\mathrm{gauge\ fix}}.
\tag{HP6}
$$

The gate in (HP1) is recomputed from $\widehat E_{\mathrm{physical}}$ in
physical field coordinates. The numerical gauge-fixing term does not enter
PA42.

## 4. Source validation tolerance

Both drivers recompute the source state. Every frozen scalar $x_0$ must agree
with its recomputation $x$ under

$$
|x-x_0|\le10^{-8}+10^{-6}|x_0|.
\tag{HP7}
$$

This is the same numerical comparison used for independent endpoint
verification. It is a receipt-reproduction tolerance, not a physical gate.
The physical gates retain their exact frozen thresholds.

The canonical-preimage reconstruction must round-trip every physical field
with relative-infinity residual at most $5\times10^{-12}$.
The source artifact's fixed-shell residual is evaluated directly by the primary
and independently recomputed by the verifier; its maximum must not exceed
$10^{-12}$.

## 5. Frozen continuation

The primary driver is
`computations/particle_stationary_precision_v5.py`. It uses the frozen
continuation engine in `computations/particle_stationary_precision_v3.py` with
the v5 output paths, v5 manifest path, fixed-shell assertion (HP4), and
source-validation rule (HP7) supplied by the driver.

At most eight fresh L-BFGS blocks run sequentially:

| Setting | Value |
|---|---:|
| `max_iter` | `880` |
| `max_eval` | `1100` |
| `history_size` | `20` |
| `tolerance_grad` | `1e-10` |
| `tolerance_change` | `1e-12` |
| line search | `strong_wolfe` |
| dtype | `float64` |
| deterministic algorithms | enabled |
| device selector | `CUDA_VISIBLE_DEVICES=0` |

A block resets only the L-BFGS history. Its initial physical state is exactly
the accepted endpoint of the preceding block. At every endpoint the driver
writes:

- `fields_blockNN.npz` and its byte-stream SHA-256;
- optimizer iterations, function evaluations, wall time, and full closure
  history;
- physical diagnostics and Q1–Q4 gates;
- auxiliary objective-coordinate gradient RMS and maximum optimizer receipts.

The first block satisfying (HP1) and all Q1–Q4 gates is selected, and no later
block runs. If no endpoint qualifies, block 8 is terminal. Selection never uses
the lowest observed residual or energy among nonqualifying checkpoints.

## 6. Independent verification

The independent driver is
`computations/verify_particle_stationary_precision_v5.py`. It does not import
the v5 primary driver. It parameterizes the independent v3 verifier with the
v5 output and manifest paths. Physical energy, gradient, virial, boundary,
magnetic-flux, and $C_4$ calculations come from
`computations/verify_particle_stationary_q2_recovery_v2.py`, not from either
precision primary.

Before optimization it verifies:

1. every manifest hash;
2. source artifact hash, keys, dtype, contiguity, shapes, grid, finite values,
   and shell values;
3. source Q1–Q4 diagnostics under (HP7);
4. canonical-preimage reconstruction;
5. a fresh v5 output directory.

Final verification independently loads every checkpoint with
`allow_pickle=False`, recomputes diagnostics and gates, checks the optimizer
schedule and artifact hashes, rejects unregistered files, and proves that the
selected checkpoint is the first qualifying endpoint. Primary and verifier
endpoint scalars use the same tolerance (HP7). The saved physical fields
determine every recomputed diagnostic. The auxiliary
`objective_raw_gradient_rms` and `objective_raw_gradient_max` values are
optimizer-receipt scalars; each must be present, finite, and nonnegative. HP-C
depends only on the independently recomputed physical-gradient RMS and Q1–Q4.

Text-manifest entries hash LF-normalized bytes for `.md`, `.py`, and `.json`.
Binary artifacts hash their exact byte streams. Receipts identify the manifest
file by its LF-normalized SHA-256.

## 7. Output and immutability

The campaign writes only beneath
`runs/20260902_particle_stationary_precision_v5/`:

- `preflight_verification.json`;
- `results.json`;
- `verification.json`;
- `fields_blockNN.npz`.

A completed or interrupted output directory is immutable. An interruption
returns `INCONCLUSIVE—EXECUTION OR VERIFICATION`; a restart requires a new
campaign path and preregistration.

## 8. Gates and verdicts

| Gate | Pass condition |
|---|---|
| HP-A | Manifest, source schema, source scalars, shell values, and reconstruction preflight pass |
| HP-B | Every executed block has finite optimizer state, fields, diagnostics, and a hash-valid artifact |
| HP-C | The selected endpoint is the first with source physical-gradient RMS $\le1.20\times10^{-4}$ and Q1–Q4 all passing |
| HP-D | Independent verification reproduces every physical checkpoint diagnostic and validates every auxiliary optimizer receipt, gate, artifact, and selection |

The verdict tree is:

1. HP-A fail $\Rightarrow$ `INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`; no block
   runs.
2. HP-B fail or HP-D fail $\Rightarrow$
   `INCONCLUSIVE—EXECUTION OR VERIFICATION`.
3. HP-A, HP-B, and HP-D pass while HP-C fails at block 8 $\Rightarrow$
   `INCONCLUSIVE—PRECISION CAP`.
4. HP-A–HP-D pass $\Rightarrow$ `PASS—HIGHER-PRECISION BACKGROUND`.

A passing endpoint qualifies only for a separately frozen PA42 preflight. It
does not establish localization, domain convergence, resolution convergence,
energetic stability, dynamical stability, a physical particle, or a mass
prediction.

## 9. Next registered decision

The next decision is fixed:

- `PASS—HIGHER-PRECISION BACKGROUND`: freeze a successor PA42 campaign around
  the selected artifact and its recomputed $\widehat\omega_C$;
- any inconclusive verdict: preserve the receipts and do not run a PA42
  eigenspectrum from this campaign.

The successor PA42 eigensolver runs only if its independently recomputed H1–H3
preflight passes.

## References

- `computations/particle_stationary_bvp.py`—stationary action, physical field
  map, numerical objective, and Q1–Q4 diagnostics.
- `computations/particle_stationary_q2_recovery_v2.py`—canonical reconstruction
  and L-BFGS continuation engine.
- `computations/verify_particle_stationary_q2_recovery_v2.py`—independent
  physical diagnostics.
- `computations/particle_stationary_precision_v3.py`—frozen parameterized
  continuation engine.
- `computations/verify_particle_stationary_precision_v3.py`—frozen independent
  precision verifier.
- `computations/particle-physical-hessian-prereg.md`—PA42 quotient and preflight
  contract.
- `computations/particle-physical-hessian-report.md`—measured PA42 precision
  boundary.
