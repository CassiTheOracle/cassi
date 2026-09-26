# Particle Stationary Higher-Precision Continuation Campaign

## Status: Preregistered—September 2026

## Abstract

This campaign asks whether one deterministic continuation of the selected
finite-grid particle background reaches a source-coordinate first-variation
RMS low enough to give the physical-Hessian preflight a numerical margin. The
coefficient point, charge, field class, grid, boundary values, $C_4$ projector,
finite-difference stencil, quadrature, source artifact, and optimizer family
remain fixed. The intervention consists of at most eight fresh strong-Wolfe
L-BFGS blocks, each beginning from the accepted endpoint of the preceding
block. The first endpoint meeting the frozen precision target is selected.

The source-coordinate target is a planning proxy. A separately frozen PA42
campaign must recompute the physical-quotient augmented gradient and pass its
own preflight before evaluating an eigenvalue.

## 1. Frozen question

Does deterministic continuation of the selected `P:separated_core` background
produce an endpoint satisfying

$$
\boxed{
\|\delta\widehat E\|_{\mathrm{source,RMS}}
\le 1.20\times10^{-4}
}
\tag{HP1}
$$

while retaining the registered PA32 Q1, Q3, and Q4 gates and the unchanged Q2
cutoff-virial bound?

The campaign changes no coefficient, field equation, constraint, boundary
value, grid point, seed field, diagnostic, or physical gate.

## 2. Source state and numerical margin

### 2.1 Immutable initial condition

The sole initial condition is:

- artifact:
  `runs/20260902_particle_stationary_q2_recovery_v2/fields_P_separated_core.npz`;
- SHA-256:
  `99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550`;
- family and basin: `P:separated_core`;
- grid: $(R,N,\Delta x,\Delta V)=(4,17,0.5,0.125)$;
- carrier charge: $Q_C=4$;
- source physical-gradient RMS:
  $1.936974511462466\times10^{-4}$;
- source cutoff virial: $1.891010204220114\times10^{-3}$.

The NPZ schema is fixed to C-contiguous finite `float64` arrays:

| Key | Shape |
|---|---:|
| `x` | `(17,)` |
| `psi_real` | `(17,17,17,2)` |
| `psi_imag` | `(17,17,17,2)` |
| `h` | `(17,17,17,3)` |
| `a` | `(17,17,17,3,3)` |
| `c` | `(17,17,17)` |

The registered shell values are

$$
\psi=(\varphi^{-1/2},\varphi^{-1}),\qquad
h=(0,0,1),\qquad a=0,\qquad c=0,
\tag{HP2}
$$

with zero imaginary carrier and zero `psi_imag` on the shell. The campaign
uses no random number generator; the seed field is the hash-bound artifact.

### 2.2 Precision target

The published PA42 quotient has dimension $13622$, while the source
first-variation RMS uses $15^3\times17=57375$ components. Their normalization
factor is

$$
s=\sqrt{\frac{57375}{13622}}=2.052300119747167.
\tag{HP3}
$$

The PA42 augmented-gradient limit $3\times10^{-4}$ corresponds algebraically
to the source-coordinate value

$$
\frac{3\times10^{-4}}{s}
=1.461774371688562\times10^{-4}.
\tag{HP4}
$$

The stricter target in (HP1) gives the planning estimate

$$
s(1.20\times10^{-4})
=2.462760143696600\times10^{-4},
\tag{HP5}
$$

leaving approximately $18\%$ below the PA42 limit. This scaling is used only
to select a numerical target. It does not determine the PA42 gate and does not
establish that normalization is the sole contribution to the measured
augmented gradient.

## 3. Frozen physical problem

The campaign uses the PA32 dimensionless static functional and exact physical
field map in `computations/particle_stationary_bvp.py`. The coefficient point
remains

$$
\alpha_{\mathfrak s}=\gamma_x=\gamma_{\mathfrak s}
=k_{C x}=k_{C\mathfrak s}=u_C=u_{\rho}=u_{\varphi}=u_H=4^0,
\quad e_C=0.75,\quad h_C=1.50,\quad q_C=4,
\quad \xi_g=1.
\tag{HP6}
$$

The no-flux scale sector remains active, $a_0=a_0^{\mathfrak s}=0$. The source
implementation fixes `torch.gradient` with spacing $0.5$ and its one-sided
boundary stencils, uniform $\Delta V=0.125$ quadrature, the source $C_4$
projector order, fixed shell values, carrier softplus map, and exact charge
normalization.

The optimizer minimizes the registered PA32 numerical objective

$$
\widehat E_{\mathrm{objective}}
=\widehat E_{\mathrm{physical}}+\widehat E_{\mathrm{gauge\ fix}}.
\tag{HP7}
$$

The physical-gradient diagnostic in (HP1) is recomputed from
$\widehat E_{\mathrm{physical}}$ in physical field coordinates. The numerical
gauge-fixing term is not part of PA42.

## 4. Frozen continuation

### 4.1 Reconstruction

The primary program reconstructs the source raw coordinates with the existing
canonical-preimage map:

- projected physical `psi_real`, `psi_imag`, `h`, and `a` become raw tensor
  preimages;
- the strictly positive interior carrier is inverted through the exact inverse
  softplus;
- fixed-shell masks, the $C_4$ projectors, softplus, and exact charge
  normalization are reapplied;
- the physical fields must round-trip with relative-infinity residual at most
  $5\times10^{-12}$.

### 4.2 Block schedule

The program executes at most eight fresh L-BFGS blocks. Every block uses:

| Setting | Frozen value |
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

A fresh optimizer resets only the quasi-Newton history. The accepted physical
endpoint of block $j$ is the exact initial condition of block $j+1$.

At each endpoint the program writes:

- `fields_blockNN.npz`;
- its byte-stream SHA-256;
- optimizer iterations, function evaluations, wall time, and full closure
  history;
- the registered physical diagnostics and Q1–Q4 booleans.

The first block satisfying (HP1) and Q1–Q4 is selected and terminates the
campaign. No later block runs. If no block qualifies, block 8 is the terminal
endpoint and the verdict is inconclusive. No intermediate endpoint is selected
by lowest observed residual or energy.

### 4.3 Output paths

The campaign writes only beneath
`runs/20260902_particle_stationary_precision_v3/`:

- `preflight_verification.json`;
- `results.json`;
- `verification.json`;
- `fields_blockNN.npz`.

A completed or interrupted output directory is immutable. An interruption
returns `INCONCLUSIVE—EXECUTION OR VERIFICATION`; restarting requires a new
campaign path and preregistration.

## 5. Independent verification

The primary driver is
`computations/particle_stationary_precision_v3.py`. The independent driver is
`computations/verify_particle_stationary_precision_v3.py`; it does not import
the new primary program. It uses the independent physical-energy,
physical-gradient, virial, boundary, magnetic-flux, and $C_4$ implementations
in `computations/verify_particle_stationary_q2_recovery_v2.py` as a shared
verification library.
The manifest hashes LF-normalized bytes for `.md`, `.py`, and `.json` files
and exact byte streams for binary artifacts. The manifest file itself is
identified by the same LF-normalized SHA-256 policy in every receipt.

Before optimization it must verify:

1. every manifest hash;
2. the source artifact byte hash, keys, dtype, contiguity, shapes, grid, finite
   values, and shell data;
3. the source Q1–Q4 diagnostics and frozen scalar values;
4. the canonical-preimage round-trip;
5. the absence of an existing completed result at the output path.

Final verification independently loads every checkpoint with
`allow_pickle=False`, recomputes the registered diagnostics and Q1–Q4 gates,
checks the checkpoint hash and receipt values, and confirms that selection is
the first qualifying block. Primary and verifier scalars agree when

$$
|x_{\mathrm{verify}}-x_{\mathrm{primary}}|
\le 10^{-8}+10^{-6}|x_{\mathrm{verify}}|.
\tag{HP8}
$$

## 6. Gates and verdict tree

| Gate | Pass condition |
|---|---|
| HP-A | Source manifest, artifact schema, immutable scalars, shell data, and reconstruction preflight all pass |
| HP-B | Every executed block returns finite fields, finite objective values, finite gradients, and a hash-valid checkpoint |
| HP-C | The selected endpoint is the first block with source physical-gradient RMS $\le1.20\times10^{-4}$ and Q1–Q4 all passing |
| HP-D | Independent verification reproduces every checkpoint diagnostic, gate, and selection under (HP8) |

The verdict tree is:

1. HP-A fail $\Rightarrow$ `INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`; no block
   runs.
2. HP-B fail or HP-D fail $\Rightarrow$
   `INCONCLUSIVE—EXECUTION OR VERIFICATION`.
3. HP-A, HP-B, and HP-D pass while HP-C fails at block 8 $\Rightarrow$
   `INCONCLUSIVE—PRECISION CAP`.
4. HP-A–HP-D pass $\Rightarrow$ `PASS—HIGHER-PRECISION BACKGROUND`.

A `PASS` qualifies the artifact only for a separately frozen PA42 preflight.
It does not establish localization, domain convergence, resolution
convergence, energetic stability, dynamical stability, a physical particle,
or a mass prediction.

## 7. Stopping and interpretation

No coefficient, target, block count, optimizer setting, source artifact,
constraint, diagnostic, gate, or verdict may change once block 1 begins.

The next decision is fixed:

- `PASS—HIGHER-PRECISION BACKGROUND`: freeze a successor PA42 manifest around
  the selected artifact and its measured $\widehat\omega_C$, then run its
  independent preflight;
- either inconclusive verdict: preserve the receipt and do not run a PA42
  eigenspectrum from this campaign.

A successor PA42 preflight failure stops before eigenvalue evaluation. Only a
passing successor preflight admits the frozen eigensolver.

## References

- `computations/particle_stationary_bvp.py`—stationary action, field map,
  optimization objective, diagnostics, and Q1–Q4 gates.
- `computations/particle_stationary_q2_recovery_v2.py`—canonical-preimage
  reconstruction and deterministic L-BFGS continuation.
- `computations/particle_stationary_precision_v3.py`—frozen higher-precision
  continuation driver.
- `computations/verify_particle_stationary_precision_v3.py`—independent v3
  preflight and checkpoint verifier.
- `computations/verify_particle_stationary_q2_recovery_v2.py`—independent
  physical diagnostics used by the new verifier.
- `computations/particle-stationary-q2-recovery-report.md`—selected source
  artifact and Q2-qualified background result.
- `computations/particle-physical-hessian-prereg.md`—PA42 physical quotient,
  augmented functional, and preflight gate.
- `computations/particle-physical-hessian-report.md`—published H1–H3 result and
  measured precision boundary.
- `foundations/particle-stationary-action-closure.md`—PA32 stationary and PA42
  fluctuation authority.
