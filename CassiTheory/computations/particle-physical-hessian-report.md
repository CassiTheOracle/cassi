# Particle Physical Hessian Report

## Status: Tested—September 2026

## Abstract

This report records the finite-grid PA42 physical-Hessian campaign frozen in
`computations/particle-physical-hessian-prereg.md`. The selected
`P:separated_core` field passes the independent background and physical-quotient
construction gates. The independently implemented Hessian-vector product is
symmetric to $4.44\times10^{-16}$ in the registered bilinear probes, reproduces
the global $U(1)_C$ phase Rayleigh quotient at
$9.43\times10^{-17}$, and agrees with directional finite differences.

The augmented quotient-gradient gate does not pass:

$$
g_{\rm aug,RMS}=3.975253382771617\times10^{-4}
>3\times10^{-4}.
$$

The frozen decision tree therefore gives

$$
\boxed{\mathrm{INCONCLUSIVE\text{—}HESSIAN\ PREFLIGHT}}.
$$

No eigenvalue or eigenmode is evaluated. The result establishes an explicit
finite-grid $C_4$, fixed-charge, boundary-preserving coupled gauge quotient and
a verified Hessian action on it. It does not establish energetic stability or
instability. Localization, carrier retention, domain and resolution
convergence, and the mixed PA43 dynamical spectrum remain open.

## 1. Frozen question

The campaign asks whether the PA42 second variation of

$$
\mathcal L_{\omega_C}=\widehat E_{\rm phys}-\widehat\omega_C q_C
$$

can be evaluated on the Q2-qualified `P:separated_core` background after the
fixed-charge tangent condition, strict Dirichlet shell, $C_4$ field class, and
full coupled local-$SU(2)_Q$ gauge image are removed. The carrier fluctuation is
complex, so the retained physical coordinates include both
$\delta\chi_R$ and $\delta\chi_I$. The global $U(1)_C$ phase direction remains
a physical zero-mode candidate.

The registered background is

- artifact: `runs/20260902_particle_stationary_q2_recovery_v2/fields_P_separated_core.npz`;
- artifact SHA-256: `99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550`;
- grid: $(R,N,\Delta x)=(4,17,0.5)$;
- fixed charge: $q_C=4$;
- multiplier: $\widehat\omega_C=0.9619135625713447$.

The preregistered order is independent preflight, primary twelve-mode solve,
and independent six-mode verification. A failed preflight stops before the
primary spectrum.

## 2. Frozen implementation and evidence

The implementation freeze is commit `45f40f8e68a95df882dd96f136ea4918498da131`. Its source manifest is
`computations/particle_physical_hessian_manifest.json`, whose canonical SHA-256
is `f7454609672a5a660119c333a0de7461ad0fa9c7e3963bead6fd011a7f87bf8b`.
The frozen program digests are:

| Source | Canonical SHA-256 |
|---|---|
| preregistration | `d09804abf666a3a888f1706f56e4ceac651ee08e20ccb7bab063564c53a69980` |
| primary program | `4a0e324142ba937388498890cb73089b677f7c3c1e9d8f6c3e3c54295b702b35` |
| independent verifier | `8d2386b519f602daf1ccc01bcf85e6eeb4df38aeb6d090b93b976a86bcefe3ba` |

Text digests canonicalize CRLF to LF; the NPZ digest is byte-exact. The
independent verifier imports neither the primary Hessian program nor the
stationary solver. It separately implements the PA32 energy, second-order
finite differences, fixed-charge tangent, symmetry bases, coupled gauge map,
quotient metric, automatic-differentiation Hessian-vector product, and
directional checks.

The receipt is
`runs/20260902_particle_physical_hessian/preflight_verification.json`. The run
uses Python 3.12.10, NumPy 2.5.1, SciPy 1.18.0, PyTorch
2.12.0+rocm7.14.0, and the AMD Radeon RX 7900 XTX with the registered ROCm
environment.

## 3. H1—background identity

The independent port reproduces every frozen stationary scalar:

| Quantity | Independent value | Absolute difference | Gate |
|---|---:|---:|---:|
| physical energy | $3.8542001269281165$ | $0$ | **PASS** |
| physical gradient RMS | $1.936974511462466\times10^{-4}$ | $5.15\times10^{-19}$ | **PASS** |
| cutoff virial | $1.891010204543639\times10^{-3}$ | $4.57\times10^{-12}$ | **PASS** |
| $\widehat\omega_C$ | $0.9619135625713446$ | $1.11\times10^{-16}$ | **PASS** |
| $q_C$ | $4$ | $0$ | **PASS** |

All shell residuals are zero. The largest $C_4$ projection residual is
$2.22\times10^{-16}$. The artifact schema, finiteness, coordinates, coefficient
point, and SHA-256 also match. H1 passes.

## 4. H2—physical quotient

The independent construction gives:

| Object | Result |
|---|---:|
| scalar $C_4$ dimension | $855$ |
| spatial-vector $C_4$ dimension | $2535$ |
| boundary-gradient map | $4614\times855$, rank $296$ |
| allowed gauge-parameter dimension per color | $559$ |
| coupled gauge map | $15299\times1677$, rank $1677$ |
| base tangent dimension | $15299$ |
| physical quotient dimension | $13622$ |
| pivot-block condition number | $105.75823298425655$ |
| quotient parameterization residual | $5.07\times10^{-15}$ |
| metric-inverse probe residual | $8.53\times10^{-13}$ |

The boundary-gradient rank is unchanged at relative cutoffs
$10^{-10}$, $10^{-11}$, and $10^{-12}$. The coupled gauge map is also full rank
at all three cutoffs, with singular-value interval
$[0.8176573203083152,3.5702938387634995]$. An inspected allowed generator has
$\max_{\partial\Omega}|\delta a|=5.10\times10^{-16}$. H2 passes.

## 5. H3—operator preflight

The independently implemented operator passes its algebraic and
directional checks:

- the largest four-pair bilinear symmetry residual is
  $4.44\times10^{-16}$, below $10^{-9}$;
- the global phase generator is reproduced with zero coordinate residual;
- its Rayleigh quotient is $9.43\times10^{-17}$, below $10^{-10}$;
- all three seeded directional checks pass;
- their largest smallest-step HVP relative error is
  $9.91\times10^{-12}$, below $5\times10^{-5}$;
- their largest smallest-step energy-curvature discrepancy is
  $3.36\times10^{-6}$, below the registered mixed tolerance;
- the two smallest steps agree to at worst $2.84\times10^{-6}$.

The augmented quotient-gradient RMS is

$$
g_{\rm aug,RMS}=3.975253382771617\times10^{-4},
$$

which exceeds the frozen $3\times10^{-4}$ limit. H3 fails on this condition
alone.

The source Q2 diagnostic and the quotient diagnostic use different registered
normalizations. The source divides the represented gradient norm by
$\sqrt{15^3\times17}$, while PH19 divides the quotient covector norm by
$\sqrt{13622}$. Applying only this dimension factor to the independently
reproduced source value gives

$$
\left(1.936974511462466\times10^{-4}\right)
\sqrt{\frac{15^3\times17}{13622}}
=3.975253395416241\times10^{-4}.
$$

This differs from the measured quotient value by
$1.26\times10^{-12}$. The H3 outcome is therefore consistent with the same
represented background gradient under the two frozen RMS definitions. The
registered cutoff remains decisive; it is not replaced by the source Q2
cutoff after observing the result.

## 6. Verdict

The frozen gate sequence is:

| Gate | Result | Verdict |
|---|---|---:|
| H1—artifact, action, and background identity | all frozen values reproduced | **PASS** |
| H2—physical-space construction | ranks, dimensions, conditioning, and constraints pass | **PASS** |
| H3—Hessian action and finite differences | operator checks pass; augmented quotient gradient exceeds its limit | **FAIL** |
| H4—paired eigensolves | stopped before evaluation | **NOT EVALUATED** |
| H5—negative physical mode | stopped before evaluation | **NOT EVALUATED** |
| H6—nonnegative finite-grid Hessian | stopped before evaluation | **NOT EVALUATED** |
| H7—spatial mode resolution | stopped before evaluation | **NOT EVALUATED** |

The scientific verdict is

$$
\boxed{\mathrm{INCONCLUSIVE\text{—}HESSIAN\ PREFLIGHT}}.
$$

The domain-and-resolution verdict remains

$$
\boxed{\mathrm{INCONCLUSIVE\text{—}NO\ Q2\ DOMAIN/RESOLUTION\ BACKGROUNDS}}.
$$

No sign claim follows for the PA42 physical Hessian. In particular, the
ungated norm of the Hessian acting on the global-phase tangent is not an
eigenvalue residual and carries no stability interpretation; the registered
phase diagnostic is its Rayleigh quotient.

## 7. Scientific boundary

The campaign establishes three reusable finite-grid facts at the selected
point:

1. the strict-shell, $C_4$ gauge-parameter space has dimension $559$ per color;
2. its full action on $(\delta\Psi,\delta\Phi,\delta a)$ has rank $1677$;
3. the fixed-charge, gauge-quotiented, complex-carrier physical tangent has
   dimension $13622$, with a symmetric and finite-difference-verified Hessian
   action.

The selected background is not stationary enough for the independently frozen
PH19 gate. A future campaign requires a separately registered background whose
quotient augmented-gradient RMS passes its declared threshold before any
spectrum is computed. Under the same observed normalization relation, the
current $3\times10^{-4}$ quotient cutoff corresponds to a source-style RMS no
larger than approximately $1.461774371688562\times10^{-4}$. That value is a
readiness translation, not a revised gate or an achieved result.

Even a passing finite-grid PA42 spectrum would leave localization, carrier
retention, domain and resolution convergence, unrestricted basin ordering,
physical calibration, temporal coefficients, and the PA43 mixed dynamical
spectrum unresolved.

## References

- `computations/particle-physical-hessian-prereg.md`—frozen operator, quotient, gates, and verdict tree.
- `computations/particle_physical_hessian.py`—frozen primary twelve-mode eigensolver, stopped by H3 before execution.
- `computations/verify_particle_physical_hessian.py`—independent energy, quotient, Hessian action, and preflight receipt.
- `computations/particle-stationary-q2-recovery-report.md`—selected Q2-qualified finite-grid background.
- `foundations/particle-stationary-action-closure.md` §8.6—PA42 energetic Hessian and PA43 mixed pencil.
- `foundations/matter-completion-boundary.md` §10—particle-spectrum qualification boundary.
