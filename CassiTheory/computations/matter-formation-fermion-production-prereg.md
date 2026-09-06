# Finite-Mode Fermion Production and Semiclassical Backreaction

## Status: Frozen conditional quantum-production protocol—September 2026

## Abstract

A real scalar mass interaction supplies a Hermitian candidate for particle–antiparticle production once a Dirac field, fermionic anticommutation relations and an initial vacuum are declared. This calculation checks exact quench and pulse correspondences and a closed finite-mode semiclassical backreaction model. Its scalar source, quantum state and energy/charge ledgers are explicit. The field content, coupling, box, retained modes and oscillator are selected benchmark inputs. Their identification with the canonical two-fluid variables, physical particle parameters, continuum renormalization and localized formation remain open. No existing frozen program or receipt is modified.

## 1. Scientific question and scope

The tested question is whether the declared real scalar mass interaction admits independently reconstructed fermion pair production with Pauli bounds, zero net vector charge and an explicit energy source, and whether its selected finite-mode semiclassical feedback closes the energy ledger at convergent time resolution.

The optional free Dirac sector is declared in `foundations/unified-lagrangian.md` §§2.1–2.4. The present candidate adds a real scalar source through

$$
\mathcal L_\psi=\bar\psi[i\gamma^\mu\partial_\mu-(m_0+y f)]\psi.
$$

In four spacetime dimensions, $[f]=[m_0]=M$, $[\psi]=M^{3/2}$ and $y$ is dimensionless. This interaction preserves the vector $U(1)$ symmetry. It introduces a scalar source and microscopic quantum content as independent assumptions. It supplies no canonical two-density closure, selected Cassi coupling, electromagnetic charge assignment, bound particle, irreversible equilibration or measured production rate.

Use natural units and dimensionless quantities scaled by an uncalibrated reference mass with numerical value $m_0=1$. A rectangular periodic box has side lengths $(1,1,4\pi)$ in inverse reference-mass units, volume $V=4\pi$, and the retained momentum cells are $\mathbf p_j=(0,0,p_j)$ with $p_j=(0,0.5,1,2)$, each of multiplicity one. These are four explicitly selected cells, not a continuum quadrature or isotropic cutoff. Each Dirac block contains two spin states. The corresponding particle and hole momenta are opposite. No ultraviolet renormalization or approximation-error bound for the scalar mean field is established by this finite model.

## 2. Fermionic state and exact observables

Use the Dirac representation

$$
\beta=\begin{pmatrix}1_2&0\\0&-1_2\end{pmatrix},\quad
\alpha_z=\begin{pmatrix}0&\sigma_z\\\sigma_z&0\end{pmatrix},\quad
H_j(f)=p_j\alpha_z+(1+yf)\beta.
$$

The fermionic covariance is $(C_j)_{ab}=\langle\hat\psi_{j,b}^\dagger\hat\psi_{j,a}\rangle$. Its initial vacuum value is $C_{j,0}=P_{j,-}(0)$, where

$$
E_j(f)=\sqrt{p_j^2+(1+yf)^2},\qquad
P_{j,\pm}(f)=\tfrac12(1_4\pm H_j(f)/E_j(f)).
$$

The vacuum has zero excitation number and a rank-two covariance. It differs from setting an ordinary complex spinor amplitude to zero. The quadratic quantum evolution is $\dot C_j=-i[H_j,C_j]$, hence its covariance spectrum, trace and projector identity are preserved.

Define occupations per spin state and total excitation energy by

$$
n_j^+=\tfrac12\operatorname{tr}(P_{j,+}C_j),\qquad
n_j^-=\tfrac12\operatorname{tr}[P_{j,-}(1_4-C_j)],\qquad
\mathcal E_{\rm exc}=\sum_j4E_j n_j^+.
$$

The exact vector-charge identity is $2(n_j^+-n_j^-)=\operatorname{tr}C_j-2=0$. Pauli bounds are $0\le C_j\le1_4$ and $0\le n_j^\pm\le1$. Occupation relative to an instantaneous projector in a driven background is a declared diagnostic; quench and cyclic pulse endpoints have constant asymptotic Hamiltonians.

## 3. Quench and cyclic-pulse correspondences

For a mass change $m_0=1\to m_1$, let $E_a=\sqrt{p^2+m_a^2}$. The covariance is continuous at a sudden quench. The occupation per spin is

$$
n_{\rm quench}=\tfrac12\left(1-\frac{p^2+m_0m_1}{E_0E_1}\right).
$$

The work per spin is $W=\tfrac12\operatorname{tr}[(H_1-H_0)C_0]$, the vacuum-energy change is $\Delta E_{\rm vac}=E_0-E_1$, and $W=\Delta E_{\rm vac}+2E_1n_{\rm quench}$.

For a cyclic square pulse $m_0\to m_1$ at time zero, duration $T$, then $m_1\to m_0$, use $C_T=e^{-iH_1T}C_0e^{iH_1T}$. The exact occupation is

$$
n_{\rm pulse}=\frac{p^2(m_1-m_0)^2}{E_0^2E_1^2}\sin^2(E_1T).
$$

Its total quench work per spin is

$$
W=\tfrac12\operatorname{tr}[(H_1-H_0)C_0+(H_0-H_1)C_T]=2E_0n_{\rm pulse}.
$$

Use momenta $(0,0.5,1,2)$ outermost and excursion masses $(0.5,2)$ next. Emit eight quench rows first. Then emit 24 pulse rows with durations $(0.25,1,3)$ innermost. The $p=0$ rows are exact zero-production controls. All other registered rows have positive analytic occupation. No scan or optimized pulse is permitted.

Each `pulse_rows` entry has exactly: `kind` (`quench` or `pulse`), `p`, `mu_initial`, `mu_excursion`, `duration` (zero for a quench), `occupation`, `hole_occupation`, `analytic_occupation`, `work`, `vacuum_energy_change`, `excitation_energy` (per spin), `work_balance_residual`, `charge_residual`, `projector_residual`, `hermiticity_residual`, `trace_residual`. Residuals are absolute; projector and Hermiticity residuals are Frobenius norms divided by $\sqrt2$ for a four-component covariance, matching a single independent two-component block. Trace residual is $|\operatorname{tr}C/2-1|$ and charge residual is $|n^+-n^-|$.

## 4. Closed semiclassical Hamiltonian and energy partition

Let $f$ be a homogeneous real classical scalar and $\Pi=V\dot f$ its canonical momentum. The finite-model Hamiltonian is

$$
\mathcal H=\frac{\Pi^2}{2V}+\frac{V\Omega^2f^2}{2}
+\sum_j\operatorname{tr}\{H_j(f)[C_j-C_{j,0}]\}.
$$

The fixed-reference subtraction removes a constant and a linear scalar term, making the declared vacuum at $f=\Pi=0$ stationary. It is a specified finite-model convention, not a claim of renormalized continuum QFT. The equations are

$$
\dot f=\Pi/V,\qquad
\dot\Pi=-V\Omega^2f-y\sum_j\operatorname{tr}\{\beta(C_j-C_{j,0})\},\qquad
\dot C_j=-i[H_j(f),C_j].
$$

Their continuous-time total energy is conserved. Decompose it into

$$
\mathcal E_s=\Pi^2/(2V)+V\Omega^2f^2/2,\quad
\Delta\mathcal E_{\rm vac}=\sum_j[-2E_j(f)-\operatorname{tr}(H_j(f)C_{j,0})],\quad
\mathcal H=\mathcal E_s+\Delta\mathcal E_{\rm vac}+\mathcal E_{\rm exc}.
$$

The vacuum-polarization term can be negative. Scalar energy loss alone must not be equated to excitation energy. The scalar is a mean field; scalar–fermion entanglement and non-Gaussian fermion interactions are outside this model.

Selected inputs are $\Omega=3$, $y=0.25$, $f(0)=0$, $\Pi(0)=3V$, final time $12$. Thus the initial total energy is $9V/2$. All four blocks start at their vacuum covariances. No physical mass or particle-data fit is used.

## 5. Fixed numerical method and schedule

The primary uses full four-component covariance matrices. The independent implementation uses the two-component Hamiltonian $h=(p,0,1+yf)$ and a Bloch vector $r_j$ with $C_{j,\uparrow}=(1_2+r_j\cdot\sigma)/2$, initially $r_j=-h_j(0)/E_j(0)$. The down-spin block is $\sigma_zC_{j,\uparrow}\sigma_z$. In the full representation the up-spin indices are $(0,2)$ and down-spin indices $(1,3)$. The independent implementation may reconstruct a four-component covariance solely to compare retained arrays; it must not import primary functions or use a four-component propagator for its own dynamics.

Use the symmetric exact-subflow composition $A(\tau/2)B(\tau)A(\tau/2)$. Subflow $A$ changes only $f$ by $\tau\Pi/V$. During $B$, $f$ is fixed, the fermion covariance evolves exactly under $H_j(f)$, and $\Pi$ integrates its time-dependent force exactly:

$$
\Pi' = \Pi-\tau V\Omega^2 f-y\sum_j\operatorname{tr}\{\beta[\mathcal I_j-\tau C_{j,0}]\},
\quad \mathcal I_j=\int_0^\tau e^{-iH_jt}C_je^{iH_jt}\,dt.
$$

For $K=H/E$, the primary evaluates

$$
\mathcal I=\left(\frac\tau2+\frac{\sin2E\tau}{4E}\right)C
+\left(\frac\tau2-\frac{\sin2E\tau}{4E}\right)KCK
-i\frac{1-\cos2E\tau}{4E}[K,C].
$$

The independent program rotates $r$ about $\hat h$ by angle $2E\tau$ and integrates that rotation:

$$
\int_0^\tau r(t)dt=\tau r_\parallel+
\frac{\sin2E\tau}{2E}r_\perp+
\frac{1-\cos2E\tau}{2E}(\hat h\times r).
$$

Its fermionic scalar force is $-2y\sum_j(r_{j,z}-r_{j,0,z})$. Use stable sine/sinc limits where needed. Never clamp occupations, renormalize covariances, project eigenvalues, rescale energy or alter the scalar trajectory to repair a residual.

Six trajectories are required in this exact order:

| Case | Step | Steps | $y$ | Initial $\Pi$ | Scalar fermion force |
|---|---:|---:|---:|---:|---|
| `closed_coarse` | 0.02 | 600 | 0.25 | $3V$ | included |
| `closed_medium` | 0.01 | 1200 | 0.25 | $3V$ | included |
| `closed_fine` | 0.005 | 2400 | 0.25 | $3V$ | included |
| `feedback_off` | 0.005 | 2400 | 0.25 | $3V$ | omitted |
| `coupling_zero` | 0.005 | 2400 | 0 | $3V$ | included |
| `pump_zero` | 0.005 | 2400 | 0.25 | 0 | included |

The feedback-off control retains fermionic evolution but omits only its force on $\Pi$. The full Hamiltonian is still diagnosed, so its drift is visible. The other two controls must have no resolved production. All trajectories retain every step, including initial and final states. Final time is fixed; no extension to find a peak is allowed.

For convergence compare $u=(f,\Pi/(3V),n_0^+,n_1^+,n_2^+,n_3^+)$ over every common time. Let $D_{cm}=\max\|u_c-u_m\|_\infty$ and $D_{mf}=\max\|u_m-u_f\|_\infty$. The convergence ratio is $D_{cm}/D_{mf}$. `feedback_effect` is the maximum absolute difference of $(f,\Pi/(3V))$ between `closed_fine` and `feedback_off` over all their common times. `production_peak` is the largest closed-fine occupation over nonzero momenta and all times.

## 6. Artifacts and independent comparison

The primary program is `computations/matter_formation_fermion_production.py`; the independent program is `computations/verify_matter_formation_fermion_production.py`. Both are standalone NumPy scripts. The primary CLI requires `--output-dir`. The independent CLI requires `--input-dir` and `--output-dir`. No primary import or shared numerical helper is allowed.

The primary writes one `<case>.npz` for each trajectory with exactly `time`, `f`, `pi` (shape `(steps+1,)`) and `covariance_re`, `covariance_im` (shape `(steps+1,4,4,4)`), all float64 and finite. The verifier writes `independent_<case>.npz` containing `time`, `f`, `pi` and `bloch` (shape `(steps+1,4,3)`). Archives must be read with `allow_pickle=False`.

Receipts are `results.json` with schema `cassi.matter-formation.fermion-production.v1` and `verification.json` with schema `cassi.matter-formation.fermion-production.verification.v1`. Both have `schema`, `identities`, `artifacts`, `pulse_rows`, `trajectory_summaries`, `convergence`, `verdicts`, `numerical_pass`, `failures`. Canonical source identities have keys `primary`, `verifier`, `prereg`, each with root-relative `path` and SHA-256 of UTF-8 text after CRLF-to-LF normalization. `prereg` refers to this file. Artifact identities have the case names as keys and output-directory-relative `path` and raw-byte `sha256`. The verifier additionally has `input_sha256`, `input_artifacts` and `independent_checks`.

Each trajectory summary has exactly: `case`, `steps`, `dt`, `duration`, `g`, `initial_pi`, `final_f`, `final_pi`, `final_particle` (four values), `final_hole` (four), `peak_particle` (four), `max_projector_residual`, `max_hermiticity_residual`, `max_trace_residual`, `max_charge_residual`, `min_covariance_eigenvalue`, `max_covariance_eigenvalue`, `min_mass`, `max_mass`, `initial_total_energy`, `final_total_energy`, `max_total_energy_error`, `relative_energy_error`, `final_scalar_energy`, `final_vacuum_energy`, `final_excitation_energy`, `energy_partition_residual`. Here `g` records the selected Yukawa coefficient $y$. Norm conventions match §3 and maxima range over all steps and modes. Eigenvalue extrema include all four eigenvalues per mode. Relative energy error is maximum absolute total-energy error divided by $\max(1,|\mathcal H(0)|)$. The energy partition residual is the maximum absolute discrepancy between the direct Hamiltonian and its three-term partition.

The `convergence` object has exactly `coarse_medium_difference`, `medium_fine_difference`, `ratio`, `feedback_effect`, `production_peak`. `independent_checks` records comparison counts and all mismatches for source identities, receipt shape, artifact hashes, raw arrays and scientific summaries. The verifier recomputes both primary-array diagnostics and its own dynamics; it must not trust a primary PASS flag or a stored summary in place of either calculation. Scientific payload shapes and case order are exact. Float summary comparisons use $|a-b|\le2\times10^{-8}\max(1,|a|,|b|)$; reconstructed raw arrays use $2\times10^{-10}\max(1,|a|,|b|)$ pointwise. No numeric tolerance applies to strings, integers, paths, keys, order or hashes.

All outputs are exclusive-create. An existing result, verification or trajectory target must cause a visible nonzero exit without modification. No NaN or infinity is permitted in JSON or arrays. Required-input failure writes a fresh failure receipt with empty `pulse_rows`, `trajectory_summaries`, `convergence` and `verdicts`; it returns nonzero. Other numerical qualification failures retain the computed evidence and identify each failed criterion. Partial output from a failed attempt is preserved.

## 7. Qualification and frozen decisions

Numerical qualification requires:

1. Source identities, exact schedules, shapes and finite-value checks pass.
2. All analytic occupation and work-balance discrepancies are at most $2\times10^{-11}$; zero-momentum occupations are at most $2\times10^{-11}$ in magnitude and every other analytic row exceeds $10^{-8}$.
3. Covariance/projector, Hermiticity, normalized trace and charge residuals are at most $5\times10^{-10}$ throughout; covariance eigenvalues and occupations remain within $[-5\times10^{-10},1+5\times10^{-10}]$ without clipping.
4. Energy-partition residuals are at most $5\times10^{-10}$. All measured masses stay strictly positive, keeping the declared gapped particle diagnostic applicable.
5. The `closed_fine`, `coupling_zero` and `pump_zero` relative energy errors are at most $2\times10^{-4}$. No energy-conservation threshold is applied to `feedback_off`.
6. $D_{mf}>10^{-10}$ and $3\le D_{cm}/D_{mf}\le5$.
7. Every occupation in `coupling_zero` and `pump_zero`, and the zero-momentum occupation in every case, is at most $5\times10^{-10}$ in magnitude.
8. Independent source, raw-array and summary reconstruction pass their stated tolerances.

The `verdicts` object has two keys. `fermion_correspondence` is `SUPPORTS—finite-mode fermion pair correspondence` when its analytic, Pauli and charge checks qualify; otherwise it is `INCONCLUSIVE`. `closed_backreaction` is `SUPPORTS—energy-accounted semiclassical fermion production in the specified finite-mode model` when the closed numerical schedule qualifies and both `production_peak` and `feedback_effect` exceed $10^{-6}$. If that schedule qualifies but either threshold is not exceeded, it is `DOES NOT EMERGE—production and feedback at the registered thresholds`. A numerical or input qualification failure makes the affected verdict `INCONCLUSIVE`. `numerical_pass` reports numerical qualification independently of a scientifically negative threshold verdict; process exit is zero exactly when numerical qualification passes. The independent receipt must reconstruct the verdict from evidence.

One primary execution and one independent reconstruction are allowed after code inspection. One missing-preregistration primary control and one missing-primary-artifact verifier control must each return nonzero with empty scientific payloads. Programs may expose `--prereg` solely for the missing-preregistration control; the canonical run uses this file. The verifier control uses a copied input directory with one declared trajectory omitted, without modifying the accepted inputs.

An implementation defect permits code repair and a new output directory under this section. Preserve the failed attempt and the exact source revision, record the defect and changed source identities, and leave this scientific protocol unchanged. Numerical or scientific failure permits no parameter, tolerance, mode, final-time or verdict adjustment. The next scientific question requires a separate protocol.

## References

- `foundations/unified-lagrangian.md` §§2.1–2.4—optional Dirac field content and the physical-coupling boundary.
- `foundations/sector-coupling-derivation.md` §§1.5–1.6—chiral-current closure and positive-energy leakage constraints.
- `computations/matter-formation-continuum-report.md` §§8, 12–13—scalar correspondence, microscopic normalization and spinor-conversion scope.
- Patrick B. Greene and Lev Kofman, *Preheating of Fermions* (1998), [arXiv:hep-ph/9807339](https://arxiv.org/abs/hep-ph/9807339)—standard coherent fermion excitation and Pauli-bounded occupation context. This protocol uses its own explicitly specified finite-mode Hamiltonian and numerical schedule.
