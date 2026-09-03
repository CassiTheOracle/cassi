# Particle Physical Hessian Precision Report

## Status: Tested—September 2026

## Abstract

This report records the finite-grid PA42 physical-Hessian campaign frozen in
`computations/particle-physical-hessian-precision-v2-prereg.md`. Its input is
the independently verified higher-precision `P:separated_core` background with
physical-gradient RMS $5.471248126403578\times10^{-5}$. The independently
constructed preflight passes H1–H3 on a 13,622-dimensional fixed-charge,
strict-shell, $C_4$, coupled-gauge quotient. Primary and independent sparse
eigensolvers agree on the six lowest modes to
$3.11\times10^{-14}$ in absolute eigenvalue.

The six matched lowest eigenpairs contain one numerically near-zero
global-$U(1)_C$ carrier-phase symmetry mode, no negative mode, and five positive
modes. The frozen finite-matrix receipt uses the operational label
`PASS—NONNEGATIVE C4 FINITE-GRID PA42 HESSIAN`; under H5–H6, that label records
only the absence of a negative mode among those six independently matched
lowest eigenpairs.

The near-zero phase mode carries a high-frequency fraction of $0.33454$, above
the registered $0.20$ cutoff. Its separate spatial verdict is
`INCONCLUSIVE—GRID-SCALE CLASSIFIED MODE`. The localized X2 $N=29$ background
and its separate constrained low-spectrum result are recorded in
`computations/particle-localized-physical-hessian-report.md`; this diffuse
campaign remains a one-point finite-matrix sign classification. It does not
establish continuum stability, localization, carrier retention, or PA43
dynamical stability.

## 1. Frozen question and background

The campaign evaluates the second variation of

$$
\mathcal L_{\omega_C}=\widehat E_{\rm phys}-\widehat\omega_C q_C
$$

on the higher-precision stationary field after imposing the fixed-charge
tangent, strict Dirichlet shell, $C_4$ field class, and quotient by the full
allowed local-$SU(2)_Q$ gauge image. The carrier fluctuation remains complex,
and the global $U(1)_C$ phase direction remains a physical zero-mode
candidate.

The registered background is:

- artifact:
  `runs/20260902_particle_stationary_precision_v5/fields_block01.npz`;
- SHA-256:
  `ac4c54fa0e5ed61f73cb86b5e83d0061806fc2e5d1725894bad9e8e89457a61e`;
- grid: $(R,N,\Delta x)=(4,17,0.5)$;
- charge: $q_C=4$;
- multiplier: $\widehat\omega_C=0.9619139451720476$;
- physical energy: $3.854183410304054$;
- physical-gradient RMS: $5.471248126403578\times10^{-5}$;
- cutoff virial: $1.348199173228824\times10^{-4}$.

The execution order is independent preflight, primary twelve-mode solve, then
independent six-mode verification. The eigenspectrum is admissible only because
H1–H3 pass.

## 2. Frozen implementation and evidence graph

The implementation freeze is commit
`9cc6b67357ed42b6c143fcc8407fc751be994576`. Its source manifest is
`computations/particle_physical_hessian_precision_v2_manifest.json`, with
canonical SHA-256
`bc8a0c108fb0c7ef9ecc2cbaf238c724fac9e47cebccd4adc72a1a271c8f7e22`.
The frozen source digests are:

| Source | Canonical SHA-256 |
|---|---|
| preregistration | `7ec3ed173bfc1c8f1824423a7c02c18e19a265bd0ed87396cc5b3cd1bf129c54` |
| primary wrapper | `13b8dd2d3451960276cc5be31f0b62a99f821603b389beb09eea37e118ddf0de` |
| independent verifier | `c4b903a9ebfe146176b2f5b1475cd7f6e78606341645d220c48525e723d4b6c0` |
| PA42 operator engine | `4a0e324142ba937388498890cb73089b677f7c3c1e9d8f6c3e3c54295b702b35` |
| precision-background manifest | `1307cc689272eb0100655299232719079ca34697e6e6f74451efb50270d6fc33` |

Text digests replace CRLF with LF before UTF-8 hashing; binary artifacts use
byte-exact hashes.
The independent verifier imports neither the primary PA42 program nor the
stationary optimizer. It separately constructs the PA32 energy, symmetry
bases, fixed-charge tangent, allowed coupled gauge map, quotient metric,
automatic-differentiation Hessian-vector product, finite-difference checks, and
six-mode eigensolve.

The manifest is the reproducible pre-execution snapshot. Four living theory
documents appear in that snapshot because they define the campaign boundary.
Their current forms incorporate this measured result and intentionally have
different hashes. Reproduction therefore uses commit
`9cc6b67357ed42b6c143fcc8407fc751be994576` together with the manifest digest,
while this report and the synchronized theory summaries are downstream result
surfaces.

## 3. Strict JSON receipt boundary

The primary wrapper converts scientific scalar leaves recursively before
serialization. Python dictionaries, lists, and tuples are traversed; NumPy
scalars, zero-dimensional NumPy arrays, and zero-dimensional Torch tensors are
converted through `.item()`. Nonscalar arrays and tensors raise an error.
`json.dumps(..., allow_nan=False)` rejects nonfinite JSON numbers. This keeps
the scientific operator unchanged while making every terminal primary receipt
strictly serializable.

## 4. H1—background identity

The independent implementation reproduces every frozen stationary scalar:

| Quantity | Independent value | Absolute difference | Result |
|---|---:|---:|:---:|
| physical energy | $3.854183410304054$ | $0$ | **PASS** |
| physical-gradient RMS | $5.471248126403577\times10^{-5}$ | $1.36\times10^{-20}$ | **PASS** |
| cutoff virial | $1.348199189448731\times10^{-4}$ | $1.62\times10^{-12}$ | **PASS** |
| $\widehat\omega_C$ | $0.9619139451720476$ | $0$ | **PASS** |
| charge $q_C$ | $4$ | $0$ | **PASS** |

All shell residuals are zero. The largest $C_4$ projection residual is
$2.22\times10^{-16}$. The artifact schema, finiteness, coordinates,
coefficient point, and SHA-256 agree with the frozen inputs. H1 passes.

## 5. H2—physical quotient

The independent construction gives:

| Object | Result |
|---|---:|
| scalar $C_4$ dimension | 855 |
| spatial-vector $C_4$ dimension | 2535 |
| boundary-gradient map | $4614\times855$, rank 296 |
| allowed gauge-parameter dimension per color | 559 |
| coupled gauge-map dimension | 1677 |
| base fixed-charge tangent dimension | 15299 |
| physical quotient dimension | 13622 |
| pivot-block condition number | $145.03286091757573$ |
| quotient parameterization residual | $6.6423\times10^{-15}$ |
| metric-inverse probe residual | $9.3972\times10^{-13}$ |

The boundary-gradient rank remains 296 at relative cutoffs $10^{-10}$,
$10^{-11}$, and $10^{-12}$. The coupled gauge map has full registered rank
1677. H2 passes.

## 6. H3—operator preflight

The independently implemented Hessian action passes every registered
algebraic and directional check:

- the largest four-pair bilinear symmetry residual is
  $6.38\times10^{-16}$;
- the global phase generator has zero coordinate-reproduction residual;
- its Rayleigh quotient is $1.380176660079838\times10^{-17}$, below
  $10^{-10}$;
- all three seeded HVP and energy-curvature directional checks pass;
- the augmented quotient-gradient RMS is
  $1.122864422122550\times10^{-4}$, below $3\times10^{-4}$.

The exact coordinate-count factor is

$$
\sqrt{\frac{15^3\times17}{13622}}=2.052300312622504.
$$

Applied to the independently reproduced source-gradient RMS, it gives
$1.122864424025335\times10^{-4}$, only $1.90\times10^{-13}$ from the measured
quotient value. This relation is diagnostic; the direct augmented-gradient
measurement decides H3. The measured value lies below the limit by
$1.877135577877449\times10^{-4}$, a factor of 2.6717. H3 passes.

## 7. H4—paired eigenspectra

The primary eigensolver requests twelve smallest-algebraic eigenpairs with
seed 424242, `ncv=48`, tolerance $10^{-9}$, and maximum 2000 iterations. The
independent eigensolver requests six with seed 314159 and `ncv=32` under the
same tolerance and iteration cap.

| Mode | Primary $\lambda$ | Independent $\lambda$ | Classification |
|---:|---:|---:|---|
| 1 | $-6.103841273556209\times10^{-7}$ | $-6.103841305748136\times10^{-7}$ | near-zero global $U(1)_C$ |
| 2 | $0.0491908775615871$ | $0.0491908775615739$ | positive |
| 3 | $0.0549386005341202$ | $0.0549386005341229$ | positive |
| 4 | $0.0569953708815061$ | $0.0569953708815372$ | positive |
| 5 | $0.0591400976972423$ | $0.0591400976972636$ | positive |
| 6 | $0.110295138622614$ | $0.110295138622604$ | positive |

The remaining six primary eigenvalues are

$$
0.112946613227633,
\ 0.113909477043164,
\ 0.114872728979523,
\ 0.168565879641404,
\ 0.169808531802018,
\ 0.405468888938283.
$$

The maximum absolute difference across the six matched eigenvalues is
$3.1052\times10^{-14}$. The largest residual among the matched primary modes is
$2.0261\times10^{-11}$; the independent maximum is
$8.0442\times10^{-11}$. The complete twelve-mode primary archive has maximum
residual $9.1817\times10^{-10}$ and metric-orthogonality residual
$5.5511\times10^{-15}$. The independent metric-orthogonality residual is
$1.4211\times10^{-14}$. Mode archives, quotient constraints, directional
curvatures, and finiteness checks all pass. H4 passes.

## 8. H5–H7—sign and spatial classification

The registered eigenvalue uncertainty is

$$
\epsilon_\lambda=1.122864422122550\times10^{-3}.
$$

The first eigenvalue lies inside this near-zero band. Its minimum global
$U(1)_C$ overlap across the two implementations is $0.9999973509913581$.
The next five matched modes lie above the positive threshold, and their
smallest-step directional curvatures are independently positive. H5 and H6
pass: there is no verified negative mode, exactly one near-zero mode is matched
between the two implementations and identified with the global phase direction,
and the other five matched modes are positive.

The near-zero mode has:

| Spatial diagnostic | Primary | Independent | Gate |
|---|---:|---:|:---:|
| participation number | $423.584760791031$ | $423.584760791105$ | PASS: $\ge16$ |
| high-frequency fraction | $0.334536622712838$ | $0.334536622712750$ | FAIL: $>0.20$ |

H7 therefore fails. This does not change the exact finite-matrix sign branch;
it supplies the separate spatial verdict

$$
\boxed{\mathrm{INCONCLUSIVE\text{—}GRID\text{-}SCALE\ CLASSIFIED\ MODE}}.
$$

## 9. Frozen verdict tree

| Gate | Measured condition | Result |
|---|---|:---:|
| H1 | background, action, shell, $C_4$, charge, and artifact identity pass | **PASS** |
| H2 | dimensions, boundary ranks, coupled gauge rank, metric, and constraints pass | **PASS** |
| H3 | augmented gradient, global phase, symmetry, HVP, and finite differences pass | **PASS** |
| H4 | paired eigensolves, residuals, orthogonality, mode archive, and comparisons pass | **PASS** |
| H5 | no verified negative mode among the six matched lowest modes | **PASS** |
| H6 | one global-phase near-zero mode and five positive matched modes | **PASS** |
| H7 | every negative or near-zero mode passes the spatial diagnostic | **FAIL** |

The frozen finite-grid receipt uses the operational label
`PASS—NONNEGATIVE C4 FINITE-GRID PA42 HESSIAN`. Its scope is the absence of a
negative mode among the six independently matched lowest eigenpairs.

The separate domain-and-resolution verdict for this diffuse campaign is

$$
\boxed{\mathrm{INCONCLUSIVE\text{—}NO\ Q2\ DOMAIN/RESOLUTION\ BACKGROUNDS}}.
$$

## 10. Receipt hashes and execution

The evidence directory is
`runs/20260903_particle_physical_hessian_precision_v2/`. The SHA-256 values
below were computed externally over each named evidence file; they are not
values read from hash fields inside the JSON files. For each JSON file, CRLF
pairs are replaced with LF in the UTF-8 text before hashing; the JSON is neither
parsed nor reserialized. `eigenmodes.npz` is hashed byte-for-byte:

| Evidence | SHA-256 convention | SHA-256 |
|---|---|---|
| `preflight_verification.json` | CRLF-normalized text | `236ace4ec3aa5bc40b09011dfc9425c003c1420f77585e7c2fd80d42f1265bfa` |
| `results.json` | CRLF-normalized text | `9f0ff0a06093e4359da1cc769741fc61c58597b957c85181ae3147c3a329da24` |
| `eigenmodes.npz` | byte-exact | `233ce5d86b309fe3ba918ac062dfde00bd1a75efe32875e5132bafe6c0d5172a` |
| `verification.json` | CRLF-normalized text | `933452203fd3169d73bab625dccd551f2b59281db72646cdaa6efa7057a60769` |

The commands are:

```text
python computations/verify_particle_physical_hessian_precision_v2.py --preflight
python computations/particle_physical_hessian_precision_v2.py
python computations/verify_particle_physical_hessian_precision_v2.py
```

The environment is Python 3.12.10, NumPy 2.5.1, SciPy 1.18.0, PyTorch
2.12.0+rocm7.14.0, and the AMD Radeon RX 7900 XTX, with
`CUDA_VISIBLE_DEVICES=0`,
`PYTORCH_HIP_ALLOC_CONF=expandable_segments:True`, and `HSA_ENABLE_SDMA=0`.

## 11. Scientific boundary

This campaign fixes the six-mode PA42 low-spectrum sign classification for one
registered finite matrix in one $C_4$ symmetry class. Its six independently
matched lowest eigenpairs contain one numerically near-zero global carrier-phase
symmetry mode, no negative mode, and five positive modes within the frozen
uncertainty.

The following remain open:

- a spatially resolved representation of the global phase mode;
- additional outer-domain and finer-grid backgrounds for this diffuse campaign;
- the localized X2 branch's Hessian-resolution sequence and continuum comparison;
- domain and resolution convergence of the quotient spectrum;
- carrier localization and the retention inequality;
- perturbations outside the $C_4$ class and represented finite box;
- unrestricted basin ordering and infinite-domain existence;
- physical calibration of mass, radius, charge, spin, and statistics;
- temporal coefficient groups and the PA43 mixed dynamical pencil;
- continuum thresholds, decay channels, and lifetime.

## References

- `computations/particle-physical-hessian-precision-v2-prereg.md`—frozen PA42 operator, quotient, eigensolvers, gates, and verdict tree.
- `computations/particle_physical_hessian_precision_v2.py`—serialization-safe primary twelve-mode driver.
- `computations/verify_particle_physical_hessian_precision_v2.py`—independent preflight and six-mode verifier.
- `computations/particle-stationary-precision-v5-report.md`—higher-precision stationary background.
- `foundations/particle-stationary-action-closure.md` §8.6—PA42 energetic Hessian and PA43 mixed pencil.
- `foundations/matter-completion-boundary.md` §10—particle-spectrum qualification boundary.
- `foundations/core-trapped-charge-support.md`—retained-charge support boundary.
- `computations/particle-localized-physical-hessian-report.md`—localized X2 $N=29$ constrained PA42 spectrum and spatial qualification.
- `foundations/nonabelian-magnetic-core-boundary.md`—non-Abelian core and confinement boundary.
