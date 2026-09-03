# Localized Carrier Physical Hessian Report

## Status: Tested—September 2026

## Abstract

This report measures the constrained static curvature of the finest localized,
nodeless, carrier-retaining stationary field in the PA42 particle action. The
frozen background is the independently verified $N=29$, $R=4$ field at the
Mapped coupling $h_C=2.9598260763447164$. The physical fluctuation space keeps
fixed charge $Q_C=4$, fixes the outer shell, preserves $C_4$, retains the full
complex carrier, and quotients the complete allowed local-$SU(2)_Q$ gauge
image. The numerical gauge-fixing energy is excluded from the physical
functional.

Independent sparse implementations construct the same 77,000-dimensional
physical operator. Their six lowest eigenvalues agree within
$5.9953\times10^{-14}$. The six matched lowest eigenpairs contain one
numerically near-zero global $U(1)_C$ carrier-phase symmetry mode, no negative
mode, and five positive modes. The first
positive eigenvalue is $0.01527618220595$, more than 25 times the registered
uncertainty $\epsilon_\lambda=6.092903959\times10^{-4}$. The independently
matched low-spectrum result is

$$
\boxed{\mathrm{NO\ NEGATIVE\ MODE\ AMONG\ SIX\ MATCHED\ LOWEST\ C4\ PA42\ EIGENPAIRS}}.
$$

The phase mode has high-frequency fraction $0.8744032081$, above the frozen
$0.20$ cutoff. Its field weight is entirely in the carrier-imaginary component,
so the diagnostic exposes the localized carrier's odd-even grid structure.
The separate spatial verdict is
`INCONCLUSIVE—GRID-SCALE CLASSIFIED MODE`. A localized Hessian resolution
sequence is unavailable. The result qualifies six matched lowest eigenpairs in
one finite-grid symmetry class; continuum energetic stability and PA43 temporal
stability remain open.

## 1. Frozen question and source field

The campaign evaluates the second variation of

$$
\mathcal L_{\omega_C}=\widehat E_{\rm phys}-\widehat\omega_C q_C
$$

on the finest field from the independently verified carrier-resolution
sequence. The source is:

- artifact:
  `runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X2_block01.npz`;
- byte-exact SHA-256:
  `db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0`;
- grid: $(R,N,\Delta x)=(4,29,2/7)$;
- charge: $q_C=4$;
- multiplier: $\widehat\omega_C=0.0034164531971490053$;
- physical energy: $1.5251878559994063$;
- physical-gradient RMS: $3.090108443313949\times10^{-7}$;
- cutoff virial: $9.092469919592924\times10^{-8}$;
- carrier radius: $1.6314313026374387$;
- core length: $2.2977937729044924$;
- outer carrier fraction: $1.0708172350337447\times10^{-4}$;
- maximum density depletion: $0.9856286941942967$;
- negative norm fraction: $0$.

The source campaign verdict is
`EMERGES—THREE-LEVEL RESOLUTION-CONSISTENT LOCALIZED RETAINED BRANCH`.
This Hessian campaign changes no source coefficient or field value.

## 2. Physical tangent and quotient

The perturbation contains complex $\Psi$, real adjoint $h$, spatial gauge
field $a_i^a$, and complex carrier $\chi_C$. Its admissible space applies four
constraints in sequence:

1. zero outer-shell variation in every field;
2. exact $C_4$ covariance;
3. the fixed-charge tangent $\delta Q_C=0$;
4. orthogonal projection away from the complete allowed infinitesimal
   local-$SU(2)_Q$ gauge image.

The global carrier phase is retained as a physical direction. Gauge parameters
vanish on the shell and satisfy the frozen one-sided normal-derivative
condition. A sparse matrix $G$ represents their coupled action, and

$$
P=I-G(G^TG)^{-1}G^T
$$

projects onto the physical quotient. The eigensolver acts on

$$
K_\mu=PKP+8(I-P),
$$

which leaves physical eigenvalues below the gauge lift unchanged.

The independently reproduced dimensions are:

| Object | Dimension |
|---|---:|
| scalar $C_4$ basis | 4,941 |
| spatial-vector $C_4$ basis | 14,769 |
| allowed gauge basis per color | 3,925 |
| coupled gauge image | 11,775 |
| fixed-charge base tangent | 88,775 |
| physical quotient | 77,000 |

The gauge Gram matrix has estimated condition number $60.4976239581$.
Independent projector probes give maximum relative gauge-orthogonality and
idempotence residuals at the $10^{-15}$ level.

## 3. Frozen implementation and evidence identity

The protocol is frozen in
`computations/particle-localized-physical-hessian-prereg.md`. Its source
manifest is
`computations/particle_localized_physical_hessian_manifest.json`, with
canonical SHA-256
`cf4787a177637915bce4f39e388f596d0276c685695797f77ebbecf6c0bf719a`.
The frozen implementation digests are:

| Source | Canonical SHA-256 |
|---|---|
| preregistration | `7cf7a8cdcc301ecebab7abc753e13698ebebe3e58d6024311d458a6ad7bd5869` |
| primary driver | `98e2e7c406c6cefdbeadca67e08407940c83777cca99669b4e74e8fd69f241cd` |
| independent verifier | `24699c79727ae25f17a5fd0d7d110f678f898108d07254e4c5d0d1a91a49bab6` |
| stationary action engine | `3143682f8a1052c60243c906b029a5f291a5d767d17b4ebe622deb23d22c5ad1` |
| source campaign manifest | `8d1f18cb18d3635960ec7be1076688bcbd1f1fbc5fda1d86e851c46f8b3ff853` |

Text digests replace CRLF with LF before UTF-8 hashing; NPZ digests are
byte-exact. Both programs
validate the manifest before constructing the operator. The independent
verifier imports neither the primary Hessian driver nor the stationary or
resolution-recovery driver. It separately implements the physical energy,
$C_4$ bases, gauge map, fixed-charge tangent, projector, Hessian-vector product,
and eigensolve.

Coefficient expansion uses fixed sparse COO basis multiplication. Deterministic
PyTorch algorithms remain enabled for the second derivatives on ROCm. A direct
cross-implementation probe on the same random physical direction gives zero
projector difference, zero reconstructed-field difference, HVP relative
difference $3.6109\times10^{-17}$, and matching directional curvature
$31.725889288923675$.

Controlled manifests changing $h_C$ by $10^{-6}$ or changing the frozen
physical energy are rejected before operator construction with exit code 1.
Their receipts are preserved under
`runs/20260903_particle_localized_physical_hessian/tamper/`.

## 4. LH1—background identity

The independent implementation reproduces the frozen background scalars. The
physical-energy difference is $4.44\times10^{-16}$, the physical-gradient RMS
difference is $5.51\times10^{-20}$, and the cutoff-virial difference is
$1.71\times10^{-12}$. The source SHA-256, grid, coordinates, charge,
multiplier, coefficients, finiteness, shell data, and $C_4$ transformation
laws agree. Shell residuals vanish, and the largest field $C_4$ residual is
$2.2204460493\times10^{-16}$. LH1 passes.

## 5. LH2—sparse physical quotient

The two implementations independently recover the dimensions in §2. The
receipt stores the coupled gauge map as a compressed noncarrier block
`noncarrier_shape=[78894,11775]`; its conceptual full embedding is
`embedded_shape=[88775,11775]`. Equation (LH17) sets
$\delta_\alpha\chi=0$, so the omitted carrier rows are implicit exact zeros:
$88775-78894=(N_S-1)+N_S=9881$. The two shape fields therefore describe one
map in compressed and embedded storage, not different quotient dimensions.
The allowed gauge map has full registered column count. Its sparse Gram matrix
is positive definite at the measured extremal eigenvalues $0.6199901283$ and
$37.5079296417$. Projector, gauge-orthogonality, fixed-charge, shell, and
$C_4$ probes pass. LH2 passes.

## 6. LH3—operator preflight

The independently constructed physical operator passes the frozen checks:

- augmented quotient-gradient RMS:
  $6.4297892511\times10^{-7}<5\times10^{-6}$;
- global phase Rayleigh quotient: within the $10^{-10}$ zero-mode limit;
- four seeded bilinear-symmetry probes: pass;
- three seeded automatic-differentiation and finite-difference curvature
  probes: pass;
- finite operator outputs and physical constraints: pass.

The full preflight returns exit code 0 before the primary eigensolve. LH3
passes.

## 7. LH4—paired low spectra

The primary solver requests eight smallest-algebraic eigenpairs with seed
424242, `ncv=40`, tolerance $10^{-9}$, and at most 2,000 iterations. The
independent solver requests six with seed 314159 and `ncv=32` under the same
tolerance and iteration cap.

| Mode | Primary $\lambda$ | Independent $\lambda$ | Classification |
|---:|---:|---:|---|
| 1 | $-8.7464857303\times10^{-12}$ | $-8.7763337466\times10^{-12}$ | near-zero global $U(1)_C$ |
| 2 | $0.0152761822059468$ | $0.0152761822059506$ | positive |
| 3 | $0.457303785634702$ | $0.457303785634711$ | positive |
| 4 | $0.472606455418973$ | $0.472606455418950$ | positive |
| 5 | $0.484905573777774$ | $0.484905573777792$ | positive |
| 6 | $0.497593547859250$ | $0.497593547859190$ | positive |

The remaining two primary eigenvalues are

$$
0.503770700910244,
\qquad
0.532711440622402.
$$

The maximum paired eigenvalue difference is
$5.99520433298\times10^{-14}$. The independent maximum absolute residual is
$2.01801221558\times10^{-10}$. Reapplying the independent operator to the
primary modes gives maximum absolute residual
$2.74074868724\times10^{-13}$. Eigenvector archives, finiteness, quotient
constraints, and orthogonality checks pass. LH4 passes.

## 8. LH5–LH7—sign, phase, and spatial classification

The registered eigenvalue uncertainty is

$$
\epsilon_\lambda
=10\max\!\left(
  6.4297892511\times10^{-7},
  6.0929039591\times10^{-5},
  2.0180122156\times10^{-10},
  5.9952043330\times10^{-14}
\right)
=6.0929039591\times10^{-4}.
$$

One matched eigenvalue lies in the near-zero band. Both implementations give
its overlap with the global $U(1)_C$ phase direction as
$0.9999999999982437$. Its component fraction is $1.0$ in
$\operatorname{Im}\chi_C$, with all other fractions below
$2\times10^{-28}$. The other five matched eigenvalues are positive, and the
smallest positive value exceeds $\epsilon_\lambda$ by a factor of 25.07. LH5
and LH6 pass.

The near-zero phase mode has participation number $209.1593672342$, above the
minimum 16, and high-frequency fraction $0.8744032081$, above the maximum
$0.20$. The six-mode spatial-resolution fields are:

| JSON index | $\lambda$ classification | Primary `spatially_resolved` | Independent `spatially_resolved` |
|---:|---|:---:|:---:|
| 0 | near-zero carrier phase | `false` | `false` |
| 1 | positive $0.01527618220595$ | `false` | `false` |
| 2 | positive $0.45730378563470$ | `true` | `true` |
| 3 | positive $0.47260645541897$ | `false` | `false` |
| 4 | positive $0.48490557377777$ | `false` | `false` |
| 5 | positive $0.49759354785925$ | `false` | `false` |

Thus only JSON index 2 passes the spatially resolved gate among the six
matched modes. The global-phase mode and the $0.0153$ positive mode fail it,
as do indices 3–5. Four of the five positive modes exceed the high-frequency
cutoff, but high-frequency fraction is not itself the spatial-resolution
criterion. LH7 applies to negative and near-zero modes, so the positive
classification flags do not alter the frozen LH7 gate; they reinforce the need
for a finer-grid spectral sequence before a continuum interpretation.

The analytic phase direction is proportional to the stationary carrier field.
Its high-frequency fraction identifies odd-even structure in the localized
carrier profile. No second near-zero eigenpair appears among these six
eigenpairs. The tested low-spectrum sign remains valid, while the spatial
interpretation stays inconclusive.

## 9. Frozen verdict tree

| Gate | Measured condition | Result |
|---|---|:---:|
| LH1 | source artifact, action, grid, coefficients, shell, $C_4$, and charge agree | **PASS** |
| LH2 | sparse bases, fixed-charge tangent, gauge map, Gram solve, and projector agree | **PASS** |
| LH3 | augmented gradient, symmetry, phase, HVP, finite differences, and constraints pass | **PASS** |
| LH4 | paired eigensolves, residuals, orthogonality, archives, and cross-application pass | **PASS** |
| LH5 | no verified negative mode among the six matched lowest modes | **PASS** |
| LH6 | one global-phase near-zero mode and five positive matched modes | **PASS** |
| LH7 | every negative or near-zero mode passes the frozen spatial diagnostic | **FAIL** |

The verifier records `infrastructure_pass=true` for LH1–LH4 and `pass=true`
for LH1–LH6. Its process exit code follows `pass`; LH7 controls the separate
spatial verdict. The verifier's frozen receipt label is
`PASS—NONNEGATIVE LOCALIZED C4 FINITE-GRID PA42 HESSIAN`. Under the registered
LH5 rule, this label is operationally limited to the absence of a negative
mode among the six independently matched lowest algebraic eigenpairs. The
reporting verdict is

$$
\boxed{\mathrm{NO\ NEGATIVE\ MODE\ AMONG\ SIX\ MATCHED\ LOWEST\ C4\ PA42\ EIGENPAIRS}},

$$
\boxed{\mathrm{INCONCLUSIVE\text{—}GRID\text{-}SCALE\ CLASSIFIED\ MODE}},
$$

and

$$
\boxed{\mathrm{INCONCLUSIVE\text{—}NO\ LOCALIZED\ HESSIAN\ RESOLUTION\ SEQUENCE}}.
$$

## 10. Receipt hashes and execution

The local evidence directory used for the verified run is
`runs/20260903_particle_localized_physical_hessian/`. The SHA-256 values below
were computed externally over each named evidence file; they are not values
read from hash fields inside the JSON files. For each JSON file, CRLF pairs are
replaced with LF in the UTF-8 text before hashing; the JSON is neither parsed
nor reserialized. `eigenmodes.npz` is hashed byte-for-byte:

| Evidence | SHA-256 convention | SHA-256 |
|---|---|---|
| `preflight_verification.json` | CRLF-normalized text | `3e7a79e982ba007c020f6c83a84f9cd3f6026e854cf8137436fdb8417218d0f0` |
| `results.json` | CRLF-normalized text | `07041ed86f266ba45ef967a4b16f12454e19495e5965a24680ed38d96f0ecb35` |
| `eigenmodes.npz` | byte-exact | `f612ff2eab683f830920386bac838bfb39ee988247c246765eca28de2a2cb9f7` |
| `verification.json` | CRLF-normalized text | `0ac3bf82aaaaa8c391c424dbda053d4242e2e83394b37431f2339b80b60bac08` |

The commands are:

```text
python computations/verify_particle_localized_physical_hessian.py --preflight
python computations/particle_localized_physical_hessian.py
python computations/verify_particle_localized_physical_hessian.py
```

The measured wall times are 9.25 s, 90.48 s, and 138.88 s, respectively. The
environment is Python 3.12.10, NumPy 2.5.1, SciPy 1.18.0, PyTorch
2.12.0+rocm7.14.0, and the AMD Radeon RX 7900 XTX, with
`CUDA_VISIBLE_DEVICES=0`,
`PYTORCH_HIP_ALLOC_CONF=expandable_segments:True`, and `HSA_ENABLE_SDMA=0`.

## 11. Scientific boundary

The campaign finds no negative mode among the six independently matched lowest
eigenpairs of one localized finite-grid PA42 stationary field after
fixed-charge restriction and complete allowed local-gauge projection within
$C_4$. It finds the only near-zero computed mode consistent with the analytic
carrier-phase symmetry and measures a positive gap above it.

The current boundary comprises:

- a localized Hessian sequence on finer grids and, where affordable, a larger
  domain;
- removal or convergence of the carrier's odd-even spatial structure;
- perturbations beyond $C_4$ and the represented finite box;
- infinite-domain existence and continuum spectral convergence;
- temporal coefficient groups and the PA43 mixed dynamical pencil;
- nonlinear perturbation evolution, radiation, and decay channels;
- physical calibration of mass, radius, charge, spin, and statistics;
- a formation mechanism and basin measure.

The next discriminating static calculation is a localized Hessian-resolution
campaign that tracks the phase-mode high-frequency fraction and the positive
gap together. Temporal stability becomes meaningful after that spatial
sequence resolves or identifies a persistent lattice branch.

## References

- `computations/particle-localized-physical-hessian-prereg.md`—frozen localized PA42 quotient, gates, and verdict tree.
- `computations/particle_localized_physical_hessian.py`—primary sparse eight-mode driver.
- `computations/verify_particle_localized_physical_hessian.py`—independent preflight and six-mode verifier.
- `computations/particle-carrier-resolution-recovery-report.md`—source localized-field resolution sequence.
- `computations/particle-physical-hessian-precision-v2-report.md`—separate diffuse-background PA42 spectrum.
- `foundations/particle-stationary-action-closure.md` §8.6—PA42 energetic Hessian and PA43 mixed pencil.
- `foundations/matter-completion-boundary.md` §10—particle-spectrum qualification boundary.
- `foundations/core-trapped-charge-support.md`—retained-charge support boundary.
- `foundations/nonabelian-magnetic-core-boundary.md`—non-Abelian core and confinement boundary.
