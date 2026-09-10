# Cassi Framework: Prediction vs Experiment Audit

## Status: Reference—September 2026

## Abstract

This audit compares Cassi claims with calculations, simulations, and
observations at their registered epistemic tiers. It records quantitative
matches, tensions, null results, and the source artifacts required to reopen
failed gates.

**All values computed with `python`—no generative arithmetic.**

---

## 1. Particle Physics (Standard Model)

### 1.1 Electroweak

| Prediction | Cassi Value | Experimental Value | MoE | Status |
|-----------|-------------|-------------------|-----|--------|
| $\sin^2\theta_W$ (at $m_Z$) | $0.23607 = \varphi^{-3}$ | $0.23122 \pm 0.00004$ |—| **2.1% high**—the running angle crosses $\varphi^{-3}$ at $\mu_* \approx 233$ GeV (running is upward, so the GUT-scale gap is not closed by RG; see `standard-model/sm-radiative-corrections.md` §3.3) |
| $m_W/m_Z$ | $0.8740 = \sqrt{1-\varphi^{-3}}$; 0.878 with $\rho$-correction | $0.8813$ |—| **0.36% error** after radiative corrections (tree: 0.82%) |
| $\delta_{\text{CKM}}$ | $68.8^\circ = 180 \cdot \varphi^{-2}$ | $69.2^\circ$ | $\pm 3.0^\circ$ | ⚠️ **Mapped** (4-candidate $\varphi$-search; ledger row 482; within the repo anchor's MoE, $2.1\sigma$ from the PDG 2024 value $65.55^\circ \pm 1.55^\circ$) |

### 1.2 CKM Matrix

| Element | Cassi Prediction | Experimental | Status |
|---------|-----------------|--------------|--------|
| $\|V_{us}\|$ | $\varphi^{-3} \approx 0.236$ | $0.225$ | **5% off**—nearest $\varphi$-power is close but not exact; Wolfenstein hierarchy requires additional flavor structure |
| $\|V_{cb}\|$ | Wolfenstein $A\lambda^2$ with $\lambda \approx \varphi^{-3}$ | $0.041$ | **Consistent**—magnitude set by hierarchy, not direct $\varphi$-power |
| $\|V_{ub}\|$ | Wolfenstein $A\lambda^3(\rho-i\eta)$ with $\lambda \approx \varphi^{-3}$ | $0.004$ | **Consistent**—magnitude set by hierarchy |
| $\delta_{\text{CKM}}$ | $\pi\varphi^{-2} \approx 68.8^\circ$ | $\sim 68^\circ$ | ⚠️ **Mapped** (4-candidate selection; ledger row 482)—the "unitarity triangle closure" derivation is not shown and is not the source of the value |

The CKM phase value is a Mapped selection (ledger row 482), not a derived quantity. Magnitudes follow the Wolfenstein hierarchy with $\lambda \approx \varphi^{-3}$; exact $\varphi$-powers for individual elements require additional Yukawa structure. See `standard-model/cp-violation.md`.

### 1.3 Neutrino Masses

Neutrino masses are not cleanly derivable from $\varphi$ alone. The seesaw mechanism gives $m_\nu = y_\nu^2 v_0^2 / M_R$ where both $y_\nu$ and $M_R$ are independent $\varphi$-powers, producing a two-parameter family. For observed $m_\nu \sim 0.01\text{--}0.1$ eV with $v_0^2/M_{\text{Pl}} \sim 5\times10^{-6}$ eV, the constraint $2n_y - n_R \approx 16$ emerges—satisfiable by many pairs. The framework predicts normal ordering and no sterile neutrinos, but individual mass eigenvalues require the full seesaw + PMNS cascade RGE. See `foundations/neutrino-masses.md`.

### 1.4 GUT Scale Running

| Quantity | Cassi Prediction | Experimental | Status |
|----------|-----------------|--------------|--------|
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi) \approx 1/53.2$ | No common SM intersection: $\alpha_1=\alpha_2$ at $10^{13}$ GeV ($\alpha^{-1}\approx 42$), $\alpha_2=\alpha_3$ at $10^{17}$ GeV ($\alpha^{-1}\approx 47$) | ❌ **Not realized by SM running**—requires $\Delta b = 1.70$ beyond-SM content |
| $\alpha_s(M_Z)$ from RGE (SM, 6 flavors) | $0.058$ | $0.118$ | ❌ **2.0× too small**—requires $\Delta b \approx 1.70$ in particle content between $M_Z$ and $M_{\text{GUT}}$ |

---

## 2. Cosmology

| Quantity | Cassi Value | Experimental | Deviation | Status |
|----------|-------------|--------------|-----------|--------|
| $w_0$ (DESI DR2) | $-0.87$ (Calibrated baseline) | $\approx -0.75 \pm 0.06$ (Table 9 [INF]) | $2\sigma$ baseline; $3.6\sigma$ at fixed $r_0$ with the ratified coupling | ⚠️ **Tension** (baseline; worsens at fixed $r_0$) |
| $w_a$ (DESI DR2) | $+0.012$ (+$\xi$ baseline) → $-0.38$ (B2, unstable) → **$(-1, 0)$ pure-Λ window (stable realization—10/12)** | $\approx -0.73 \pm 0.28$ | $2.7\sigma$ baseline; $1.25\sigma$ (B2, unstable); $2.61\sigma$ (stable realization) | ⚠️ **Tension**—the baseline and stable realization are in tension; the B2 value belongs to an unstable density trajectory, and the DESI anchor is the calibration target |
| $n_s$ (Planck 2018) | $0.9691 = 1 - 2\varphi^{-1}/N_e$, $N_e = 40$ | $0.9649 \pm 0.0042$ | $1.0\sigma$ (closed form) | ⚠️ **Mapped**—the gate slow-roll trajectory does not reproduce it: $(n_s, r) = (0.813, 0.188)$ under 1 step = 1 e-fold, $(0.914, 0.060)$ with $N_e = 40$ literal (`computations/slow_roll_trajectory.py`) |
| $r$ (tensor-to-scalar) | $0.0075$ ($12/N_e^2$ at $N_e = 40$ Mapped window; 0.003 needs $N_e = 63.2$) | $< 0.032$ (BK18) |—| ⚠️ **Mapped**—$\varphi^{-12}$ is fitted to the target; the trajectory gives $r$ excluded by the BK18 bound, and the two quoted numbers do not coexist on one trajectory; 0.0075 lies below BK18 and is testable at CMB-S4 |
| $H_0$ (Hubble tension) | ≈ 65.8 km/s/Mpc (pipeline, CMB-inferred) | Planck $67.4\pm0.5$, SH0ES $73.0\pm1.0$ | $\Delta H_0 = -7.2$ (−9.9%) | ⚠️ **Not resolved**—the full H(z) fit (`computations/hz_full_fit.py`) does not resolve the tension under calibrated $w(a)$; the −7.2 value comes from extrapolation beyond the calibrated range (registry C3/T4) |

---

## 3. Gravity

| Prediction | Cassi Value | Experimental | Status |
|-----------|-------------|--------------|--------|
| Mercury perihelion | $42.98''$/cy in an optional metric/force closure | $42.98'' \pm 0.01''$/cy | ⚠️ **Conditional GR reproduction**—the canonical branch supplies no metric or attractive-force closure |
| $G_{\text{eff}}/G$ (fixed point) | $\varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}}) \approx 3.73$ ($q_{\text{eq}} = \varphi^2/(\varphi^2+\varphi^{-2}) \approx 0.873$ at the reference density; $\pi/\rho = \varphi^{-3}$) |—| ✅ **Algebraic at the φ-fixed point**—the equilibrium Qi boost $(\varphi^{10}+1)/(\varphi^4+1) \approx 15.79$ times the imbalance $\pi/\rho = \varphi^{-3}$; the "equilibrium Yang fraction" label is Mapped, ledger row 500; the dilute limit $q \to 0$ ($\rho \to 0$ on the $\varphi$-line) gives $\varphi^{-3} \approx 0.236$ |
| Quantum free fall | $\Delta\phi=-m_g^2g^2T^3/(3\hbar m_i)$ for an ideal closed ballistic path; $m_g=m_i=m$ gives $-mg^2T^3/(3\hbar)$ | Published $^{87}\mathrm{Rb}$ Quantum Galileo Interferometer phase, about 80 rad over about 13 oscillations with an approximately 2.5% residual to the full apparatus model ([doi:10.1126/sciadv.aec8045](https://doi.org/10.1126/sciadv.aec8045)) | ✅ **Derived conditional correspondence**—the centre-of-mass result follows after a uniform Earth potential is supplied; the measurement gives no atom-to-$(E_Y,E_I,q)$ map, composite-graviton test, or numerical Cassi-$q$ inference |
| $v_C/v_B$ (MW rotation) | $2.8$–$3.0$ | $2.5$–$3.0$ | ⚠️ **Calibrated/Mapped comparison**—the normalization and halo variables are fitted inputs |
| Dwarf spheroidal mass discrepancy | Optional fixed-composition endpoint $v_{\text{obs}}/v_{\text{Newt}}\leq\varphi^3=4.2361$ | Nominal fixed-$M_\star/L_V=1$ proxy screen exceeds the endpoint in 7/8 objects; the lower propagated $\sigma_{\text{los}}/R_e$ bound exceeds it in 6/8 | ⚠️ **Diagnostic catalog screen**—stellar-mass posteriors, membership/binary models, equilibrium cuts, and a population likelihood remain open; no Cassi/MOND verdict is assigned |
| Solar-System $q(r)$ | No canonical profile |—| ⚠️ **Undetermined**—the quoted MESSENGER value $1.1\times10^{-6}$ has no registered derivation |
| Gravitational-wave strain | Optional chord sensitivity scenario |—| ⚠️ **Hypothesized**—no Cassi metric, waveform derivation, or sourced event-level precision input |
| GW dispersion (GW170817) | Implemented probe $c_{\text{eff}}/c \to \sqrt{1+\varphi^{-6}} \approx 1.0275$ at low $k$ | $-3\times10^{-15} \le (v_g-c)/c \le +7\times10^{-16}$ (Abbott et al.) | ❌ **Rejected**—exceeds upper bound by $>3.9\times10^{13}$; viable only if modified to recover $c$ or decoupled from observed GWs |
| Gaussian physical covariance | $G_E(x)=e^{-\sigma^2x/2}/x$ gives decreasing $xG_E(x)$ for $\sigma>0$ | A standard unsubtracted nonnegative scalar spectral measure requires nondecreasing $xG_E(x)$ | **REJECT under the declared physical-covariance assumptions**—QFC4 and an independent calculation establish the obstruction; auxiliary/regulator uses and interacting unitarity require separate physical qualification (`gravity/quantum-gravity.md` §3.1) |

The material, source/response, clock, apparatus and interacting-quantum
closure inventory is in `foundations/quantum-free-fall-correspondence.md`
§11. Its canonical-domain and information-loss checks QFC1–QFC3 pass;
they supply no numerical atomic $q$ or gravitational response.

---

## 4. Atomic Physics

| Atom | Cassi Value (E_h) | Experimental (E_h) | Error | Status |
|------|------------------|--------------------|-------|--------|
| H 1s (Schrodinger) | $-0.500$ | $-0.500$ | $0\%$ | ✅ **Exact** |
| He 1s^2 (LDA, N=64) | $-2.928$ | $-2.903$ | $0.9\%$ | ✅ **Chemical accuracy** |
| He 1s^2 (Dirac-KS) | $-2.996$ | $-2.903$ | $3.2\%$ | ✅ **Consistent** |

---

## 5. Summary

### Selected Quantitative Comparisons

| Sector | Prediction | Accuracy |
|--------|-----------|----------|
| SM | $\delta_{\text{CKM}} = \pi\varphi^{-2}$ | $<1\%$ |
| Cosmology | $w_0 = -0.87$, $w_a = +0.012$ (Calibrated baseline; with the ratified conversion→expansion coupling $w_a = -0.38$ (B2, unstable); stable realization: pure-Λ $(-1, 0)$—12) | $2\sigma$/$2.7\sigma$ baseline → $3.6\sigma$ (fixed $r_0$, B2)/$1.25\sigma$ (B2, unstable); $4.17\sigma$/$2.61\sigma$ (stable realization—12) |
| Cosmology | $n_s = 0.9691$ (closed form, $N_e = 40$; $N_e$ Mapped—ledger) | $1.0\sigma$ formula-level; the gate slow-roll trajectory does not reproduce it (2026-08-06, `computations/slow_roll_trajectory.py`) |
| Cosmology | $r = 0.0075$ ($12/N_e^2$, $N_e = 40$ Mapped—ledger; the $\varphi^{-12} \approx 0.003$ reading needs $N_e = 63.2$) | Formula-consistent at the window, below bound; the trajectory's $r$ is excluded by BK18; the two numbers do not coexist on the trajectory (2026-08-06) |
| Cosmology | $H_0$: pipeline CMB-inferred ≈ 65.8 km/s/Mpc | Not resolved—the full H(z) fit (`computations/hz_full_fit.py`) leaves the calibrated $w(a)$ tension intact; the −7.2 value comes from extrapolation beyond the calibrated range (registry C3/T4) |
| Atomic | He ground state (LDA, N=64) | $0.9\%$ |
| Gravity | $v_C/v_B$ (MW rotation; calibrated/mapped inputs) | Conditional comparison within $2.5$–$3.0$ range |

The electroweak quantities ($\sin^2\theta_W = \varphi^{-3}$: +2.1% at $m_Z$,
exact at $\mu_* = 233$ GeV; $m_W/m_Z = 0.878$ after the $\rho$ correction:
−0.36%) are falsifiable and pending FCC-ee; their status is in §1.1.

The dwarf-spheroidal result is a nominal catalog screen. McConnachie Table 4
supplies stellar-mass proxies fixed by $M_\star/L_V=1$; stellar-population and
fixed-$M/L$ systematics are omitted. Under the optional fixed-composition map,
7/8 nominal ratios exceed $\sqrt{\varphi^6}=\varphi^3=4.2361$, and 6/8 remain
above it at the lower propagated $\sigma_{\text{los}}/R_e$ bound. These counts
identify targets for object-level likelihoods and assign no Cassi or MOND
verdict. See the §3 Gravity table and
`experiments/phi_attractor_paths/path10_dwarf_galaxies.py`.

### Framework Limitations

Quantities not derivable from $\varphi$ to useful precision—they depend
on particle content, mixing structure, or RGE running that $\varphi$ alone
does not determine.

| Quantity | Best Cassi Match | Deviation | Requires |
|----------|-----------------|-----------|----------|
| $v_0/M_{\text{Pl}}$ | $\varphi^{-80}$ | $5.3\%$ | Correction factor |
| $m_e$ | $v_0\varphi^{-26}/\sqrt{2} \approx 0.64$ MeV | $25\%$ | New mixing physics |
| $\alpha_s(M_Z)$ | RGE from $\alpha_{\text{GUT}}$ | $2.0\times$ | Particle content ($\Delta b \approx 1.70$) |
| CassiFI physical-field identification | Finite regulated quantum construction under QF1–QF4 | DQ1, DQ2, DQ4, DQ5, DQ7, DQ8, and DQ9 fail the canonical-to-quantum promotion criteria | Symplectic canonical lift, Fisher ensemble derivation, guidance/equilibrium selection, physical-sector maps, interacting continuum limit, and a Cassi-specific discriminator (`foundations/quantum-measurement-derivation.md` §8.1) |
| Moment-map/Kähler projection architecture | GQ1 phase-fibre causality passes; GQ5 finite Kähler compatibility passes conditionally | GQ2, GQ3, GQ4, GQ6, and GQ7 fail; equal moduli can have projected accelerations $0$ and $-4$ | Exact phase symmetry/reduction, reservoir or conditional-ensemble projection, cotangent reconstruction, physical-sector maps, and a no-fit holonomy (`foundations/quantum-measurement-derivation.md` §8.3) |
| Finite carrier physical identification | QC1–QC9 finite reservoir with exact conditional mesoscopic drift, fluctuation, transport-noise, and instrument projection | The QF1 complex-field density and the carrier-projected density are additive sectors with no source-derived state map | A nonduplicating QF1-to-carrier map, physical carrier identity, bath separation, carrier count, and physical timescale (`foundations/quantum-measurement-derivation.md` §8.4) |
| Shared-support loop projection | Four direction-preserving Yang/Yin populations on one closed support project exactly to the canonical PDE; their species Gram matrix fills the affine bubble volume, with the rank-one boundary on the projective shell; the frozen internal spectrum gives an explicit zero-mode gap | The construction is many-to-one and kinematic in phase; it supplies no QF1-to-carrier map, amplitude evolution, quantum statistics, or universal spatial scale ratio | Direct carrier and phase identification, a phase law coupled to the positive population generator, an observable proportional to the coherence moment, and independent geometry or dynamics fixing $R/L_B$ (`foundations/loop-to-bubble-projection-theorem.md`) |
| Regulated pure Yang–Mills comparison | Gauss invariance gives the girth-four electric threshold; Yarotsky's theorem supplies a uniform strong-bare-coupling gap; the ground-state transform identifies each finite regulated physical gap with the exact-vacuum gauge-invariant Poincaré rate; a conditional full-holonomy block theorem gives $\lambda_{\mathrm{gi}}\ge\lambda_{\mathrm{loc}}/(A_{\mathrm{AT}}\rho)$; the fixed and independent schedules pass 305 and 120 checks | The equal-weight one-plaquette state is excluded as the exact interacting vacuum on the stated lattice families, conditional gaps alone do not imply a volume-uniform rate, and static pure configuration marginalization does not reproduce the exact quantum block. Uniform weak-bare-coupling bounds for exact-vacuum local rates, tensorization and boundary comparison remain open | Cutoff- and volume-uniform bounds for $\lambda_{\mathrm{loc}}$, $A_{\mathrm{AT}}$, $\rho$ and the boundary comparison; a four-dimensional continuum construction with the required axioms; a positive continuum mass independent of the regulator; any Cassi microscopic identification (`foundations/loop-to-bubble-projection-theorem.md` §§9.4–9.16) |
| Yin/Yang/Qi dynamical geometry and matter-completion boundary | Canonical populations, coherence fibre, relative currents, endpoint/Wilson channels and bounded two-domain interface form an explicit effective matrix balance. The nine-part boundary derives conditional exterior, interface, transport, power, reservoir, stress, gravity, particle-map and fluctuation requirements; its algebraic receipts pass. The stored Cartesian localized field has six independently matched lowest constrained finite-grid eigenpairs, with a near-zero phase mode and five positive modes. Independent continuum calculations at the same Mapped coupling support prepared scalar binding at $Q_C\in\{16,256\}$ | The first-order carrier preserves an exactly empty closed sector. The stored Cartesian sequence puts $99.98631608\%$ of its finest carrier norm on one parity sublattice and fails the smooth-carrier diagnostic. Smooth $Q_C=16$ constrained spatial stability is INCONCLUSIVE because the coarse translation and same-spacing domain criteria fail. The qualified scalar endpoints become larger with lower energy per carrier as prepared population increases; no preferred particle size or quantum-number assignment is established | A complete mechanism requires a specified microscopic carrier and production interaction, quantum state, energy source, normalized coefficients, qualified continuum and temporal stability, actual formation dynamics, particle quantum numbers and empirical discrimination. The frozen inconclusive results are retained without threshold changes. The population-256 single lump has lower energy than the trial of sixteen separated population-16 lumps, but this specific comparison supplies no universal fission or dynamical merger result (`computations/matter-formation-continuum-report.md`; `foundations/matter-completion-boundary.md`; `foundations/particle-stationary-action-closure.md`) |
| Interscale stress and attenuation bridge | Exact scale-window momentum ledger; reciprocal positive-stress scale chain; canonical boundary flux; Hermitian-Robin scattering; gauge-covariant frozen endpoint response; selected-point golden matching; closed-current and stationary spatial-flux boundaries; first-order source-action Nambu response; a separately declared Wilson-link transport channel with exact endpoint and relative-charge conservation; and a conditional closed-action total-stress Ward identity | The AR1–AR6 response receipt passes; the DR receipt remains `FAIL` at DR5. The registered EL9 action alone has zero coherent current on closed homogeneous time-harmonic backgrounds, and closed spatial domains have zero integrated source at each endpoint. The Wilson extension closes the homogeneous circuit conditionally, while $t_\Upsilon$ remains free and its finite scale edge has no local bulk derivation. The formal closed stress does not identify the physical carrier or the reservoir's local action and stress. Physical energy, inertial mass, amplitude stability, and the full coupled spectrum remain open | A physical stress carrier, density/current-to-momentum map, physical species-port identification, selected endpoint potentials and nonzero-current background, microscopic damping, temporal relative-gauge connection, microscopic $t_\Upsilon$ and local scale-bulk completion, explicit reservoir action, doubled port-flux law, coupled fluctuation spectrum, carrier velocity or impedance, signed return routing, and an identified observable (`foundations/endpoint-link-and-localization-boundary.md` §§3.6–3.11; `foundations/interscale-stress-attenuation-boundary.md`; `foundations/matter-completion-boundary.md` §7; `computations/endpoint_action_response_report.md`; `computations/matter_completion_boundary_report.md`) |
| Charged-endpoint stationary spatial flux | Exact source normalization $\mathcal I_{\mathrm{link},v}=-2\Gamma_v$, local balance $\partial_t|\Upsilon_v|^2+\nabla\cdot\mathbf J_{\Upsilon,v}=\Gamma_v$, periodic inverse-divergence reconstruction, and gradient cost positive for nonzero source when $K_v>0$ and $u_v>0$; SF1–SF6 pass at $K_v=2.3$, $u_v=0.9$ | Every closed endpoint domain has zero integrated $\Gamma_v$ at each scale vertex, so spatial flux cannot sustain a uniform nonzero circuit source by itself | A sign-changing coupled rail source, physical boundary flux, or the separately declared Wilson-link channel with a selected physical coefficient; selected $U_v$, $K_v$, $u_v$, normalization, and source profile (`foundations/endpoint-link-and-localization-boundary.md` §3.10; `computations/endpoint_spatial_flux_prereg.md`; `computations/endpoint_spatial_flux_check.py`; `computations/endpoint_spatial_flux_report.md`) |
| Wilson-link inter-vertex endpoint transport | The separately declared gauge-invariant hopping term carries equal-and-opposite endpoint number current, closes the homogeneous circuit when $I_{-\to+}=\mathcal J_Q$, supplies local relative-charge conservation through its scale-edge current, and has capacity $I_c=2t_\Upsilon u_-u_+/\hbar$; IT1–IT6 pass at one normalized point | $t_\Upsilon$ is a free Hypothesized coupling and the finite Wilson edge is nonlocal along $\mathfrak s$; the receipt imposes the rail bilinears and tests no amplitude or coupled rail-endpoint spectrum | A microscopic derivation and physical value for $t_\Upsilon$, a local scale-bulk completion or justified finite edge, a self-consistent rail solution, selected endpoint amplitudes and potentials, and the coupled stability spectrum (`foundations/endpoint-link-and-localization-boundary.md` §3.11; `computations/endpoint_intervertex_transport_prereg.md`; `computations/endpoint_intervertex_transport_check.py`; `computations/endpoint_intervertex_transport_report.md`) |

---

### Matter formation evidence

The first-order carrier action preserves an exactly empty carrier sector,
so physical carrier production remains unspecified. Its stored Cartesian
localized sequence is parity-concentrated and fails the frozen
smooth-carrier diagnostic. A separate continuum-consistent scalar
calculation supports prepared static binding at $Q_C=16$ and $256$,
reproduced by independent collocation; the tested $Q_C=4$ profiles spread
and $Q_C=64$ misses its residual tolerance. The smooth $Q_C=16$ constrained
spectra have no resolved negative eigenvalue on the tested grids, while
the combined stability verdict remains `INCONCLUSIVE` under the frozen
symmetry and domain comparisons. No physical matter-production,
particle-mass or spin/statistics claim follows
(`computations/matter-formation-continuum-report.md`).

**Conditional quantum carrier parent.** An optional positive temporal
stiffness gives a signed conserved charge and a low-frequency limit matching
the first-order carrier equation. Its 31 prescribed-background Gaussian
trajectories reproduce the exact scalar pair-production correspondence with
zero independent mismatches. This is a conditional numerical `PASS`; the
physical extension remains Hypothesized. The temporal coefficient and
action normalization are unselected, and the calculation drops the quartic
interaction and mediator backreaction without establishing their effects as
negligible. The stationary profiles carry a different conserved charge in
the parent, so existing fixed-population stability results do not transfer
to its full dynamics (`computations/matter-formation-continuum-report.md` §8).
The same classical scalar action has a nonnegative canonical potential
exactly when $h_C-e_C-1/(4a)\le\sqrt{u_\rho u_C/2}$. In three dimensions,
spatial dilation excludes an energetically stable, regular finite-energy
single-frequency state with zero signed charge. Gauge neutrality alone
does not imply this charge condition. Charged stationary states,
multi-frequency dynamics, quantum bound states and additional topological
sectors require separate treatment
(`foundations/particle-stationary-action-closure.md` §8.9).

**Charged radial energetic support.** Fixing the parent's signed charge
adds a derived positive rank-one population penalty to the amplitude
Hessian. All 24 frozen embeddings have positive finite-grid radial
curvature, confirmed by independent banded operators and 144 eigenvalue
brackets. Nine of twelve domain/resolution comparisons pass; all three
population-16 domain comparisons fail. The aggregate radial-domain verdict
is `INCONCLUSIVE`. Population 256 meets its radial comparison criteria,
without establishing all-sector, real-time or nonlinear stability
(`computations/matter-formation-continuum-report.md` §10).

**Scalar angular and phase support.** All four selected population-256
grids support the remaining scalar sectors; the independent operator
construction matches all 96 eigenvalues. Seven of eight spatial comparisons
pass. Doubling the box changes the first non-translation dipole eigenvalue
by $0.1242089777$, exceeding the $0.0250415952$ tolerance. The combined
scalar-parent spatial verdict is `INCONCLUSIVE`. Conditional continuum
positivity identities do not establish exact nodelessness, monotonicity or
nonlinear stability for these sampled profiles
(`computations/matter-formation-continuum-report.md` §11).

**Charged-field collective spectrum.** The declared fundamental-plus-adjoint
vacuum has a gauge-invariant common-phase observable
$\mathcal O_N=\Psi^T i\sigma^2(\Phi^a\sigma^a)\Psi$. Full connection
projection and linear Gauss elimination retain a gapless phase branch.
Independent spectra and wave solutions pass the frozen comparisons;
the supplied model-unit speed squared is $0.8649109511178478$.
Boundary-phase selection and a fixed total common-number charge allow
local phase fluctuations. This leaves a physical bulk channel alongside
transverse magnetic screening. No quantum condensate, physical speed
calibration, exchange statistics or localized matter formation follows
(`computations/matter-formation-continuum-report.md` §40;
`foundations/matter-completion-boundary.md` §20).

**Conditional temporal support obstruction.** The same charged-field action has
no stationary gauge-electric support in the declared relative-equilibrium
class when fields are smooth and finite-energy on $\mathbb R^3$, the scale
measure is one, boundary work vanishes, all temporal coefficients are
positive, and external charges, imposed voltage and reservoirs are absent.
Completing the temporal square gives a positive exterior common-phase inertia;
finite energy forces $\omega_N=0$, after which the homogeneous Gauss identity
forces $\mathcal A_0=0$, including a bounded core where both charged fields
vanish. All six interval spectra, six imposed-voltage controls and three
negative-coefficient controls pass and reconcile to
`SUPPORTS-conditional temporal support obstruction`
(`computations/matter-formation-continuum-report.md` §41;
`foundations/particle-stationary-action-closure.md` §4.4). This excludes
gauge-electric support only in that stationary isolated sector; it does not
exclude general time-dependent or multifrequency solutions, other vacua,
external sourcing or quantum bound states.

At $\chi_C=0$, fixing nonzero common-number momentum $P_N$ instead gives a
Gaussian constrained initial-data sequence with
$E_R=P_N^2/[2J_t(2\pi)^{3/2}R^3]\to0$ as $R\to\infty$, so the infimum is zero
without a zero-energy minimizer. $P_N$ has action units and $P_N/\hbar$ is
the number normalization; it is distinct from the first-order density excess
$\delta Q_N$ and the neutral-carrier number $Q_C$. This is a variational
spreading sequence, not a dispersal trajectory or a universal metastability
theorem. The model-unit $J_t=0.8971293123871708$ is a supplied numerical
witness, not calibration or a physical parameter prediction. These results
leave the existing scalar-carrier binding evidence unchanged and do not
establish complete physical matter formation.

**Physical normalization and carrier identity.** The same imposed
$0.511\ \mathrm{MeV}$ vacuum scalar mass, propagation speed $c$ and one
internal $U(1)$ generator unit admit three independently reconstructed
temporal coefficients with distinct physical core scales. Their canonical
soliton energies are $0.9707310816$, $0.9432196612$ and $0.8927907492$
times the imposed vacuum mass target. This leaves particle identification
and the temporal coefficient unselected. At the fixed coefficients, the
smallest core scale allowed by the global-vacuum inequality is
$6.7893919382\times10^{-13}\ \mathrm m$, above the mapped electron-cell
upper endpoint $6.0141121609\times10^{-13}\ \mathrm m$; the extra core-cell
assignment is contradicted. Changing units preserves the failed spatial
difference/tolerance ratio $4.9601064407$.

The proposed Dirac chiral scalars are conjugates,
$B_R^\dagger=B_L$, so their simultaneous real positive values are equal.
They cannot realize a nonzero $\varphi$ density ratio. The displayed
linear and ordinary-square projection interactions are generically
non-Hermitian even with a common mass bridge. Independent matrix and
two-component witnesses confirm these exact obstructions. The formal
$\varphi^{-6}/v_0^2$ sector scale supplies no microscopic operator or
equilibration prediction. The scalar's internal generator has no selected
electromagnetic identification, and its normalization supplies no fermion
spin or statistics (`computations/matter-formation-continuum-report.md` §12;
`foundations/sector-coupling-derivation.md` §1).

**Positive spinor observables and conversion.** The helper's component
quadratics are twice the chiral-current number densities in the declared
representation. The exact Dirac population source depends on relative
coherence. At the golden population ratio, phase-opposed witnesses have
sources $\pm0.9717365435$ while the canonical source vanishes. A
positive-energy rest state has stationary Dirac populations and a nonzero
canonical source. The specified massive Dirac Hamiltonian plus minimal
conversion lift also shifts the stationary ratio below $\varphi$ and
permits positive-energy leakage. All 520 independent payload comparisons
pass for the frozen witnesses. The physical reservoir, energy-density
normalization, quantum occupations and production interaction remain open
(`foundations/sector-coupling-derivation.md` §§1.5–1.6;
`computations/matter-formation-continuum-report.md` §13).

A separately declared real scalar mass source gives conditional
fermion pair excitation with reciprocal semiclassical feedback.
Independent full-covariance and Bloch-vector dynamics agree on all
32 analytic rows and six trajectories; all 1,185 checks pass, covering
1,494,186 raw scalar comparisons. The finest closed trajectory reaches
per-spin occupation $0.5729566253$ with relative energy error
$5.6211\times10^{-5}$ and time-convergence ratio $4.00277$. This establishes
the specified finite-mode energy/charge ledger. Physical field content
and scales, continuum renormalization, a canonical density reduction
and localized particle formation remain open
(`computations/matter-formation-continuum-report.md` §14).

The continuum witness passes all 645 independent comparisons,
including 539 numerical values, with largest absolute discrepancy
$2.1828\times10^{-11}$. Sudden quench/pulse pair density diverges
linearly and excitation energy quadratically. The specified static
subtraction has largest cutoff-512 limit error $8.4548\times10^{-8}$;
the initial-overlap energy grows logarithmically. At unchanged
parameters, $B=0.00165786399054<1$ excludes every two-body bound level
in the leading nonrelativistic Yukawa reduction. This leaves
renormalized dynamics, relativistic and many-body binding, and
physical particle matching open
(`computations/matter-formation-continuum-report.md` §§15.1–15.5).

The collective local-density extension also has no state below the
separated-particle threshold on its mass-depleting $|m|\le1$ branch, including
the specified local one-loop sea energy. This is a conditional restriction on that
benchmark model; renormalized spatial formation, many-body dynamics and
physical matching remain open
(`computations/matter-formation-continuum-report.md` §§15.6–15.7).

The scalar-vacuum qualification passes 16 symbolic and exact-rational
checks. The specified local static one-loop energy has scalar
reference curvature $9$, but
$\mathcal U(64)<-8265011/64<0$. A neutral plateau with increasing
radius has negative volume energy dominating its gradient and
interface costs, so the local functional has no global lower bound.
Its directly evaluated witness is $-168382.922633654$ in the supplied
normalization. This restriction leaves full nonlocal quantum energy,
metastability, valence spectra and physical matching open
(`computations/matter-formation-continuum-report.md` §16).

The compact-target comparison uses an independently supplied
$SU(2)_{\rm top}$ field with positive static energy and degree $B_{\rm top}$.
The shifted-angle solve supports finite-domain stationarity and radial
energetic qualification; the direct-angle solve is `INCONCLUSIVE`. Its degree
does not arise from a smooth pointwise bridge from the two canonical real
densities, and the qualified contractible density domains have trivial degree
image. The compact field, production channel and quantum statistics remain
additional Hypothesized inputs (`computations/matter-formation-continuum-report.md`
§§18.1–18.7).

At fixed nonzero fundamental and adjoint norms, the gauge quotient leaves a
physical relative $S^2$. Joint gauge cancellation removes a pure-gauge
representative while leaving the invariant relative field constant; it does
not screen a nonconstant relative texture. The registered unit-Hopf trial
has negative connection-amplitude curvature, a shape-specific instability.
The complete variation qualification passes six groups with $59/59$ exact
identities and $8/8$ predicates. Every exact unit-adjoint nonzero-Hopf field
in the stated fixed-fundamental soft action has negative first amplitude
variation, and the included hard Faddeev–Hopf loops contract in that soft
domain. Amplitude-relaxed metastability, production, normalization and
physical identification remain open
(`computations/matter-formation-continuum-report.md` §§19–20).

The added compact chiral benchmark passes its frozen structural, stationary,
calibration and radial-relaxation gates. The finite-domain degree-one hedgehog
has virial relative residual $1.70047\times10^{-11}$. The nucleon and Delta
masses map the two action coefficients to
$e_B=5.416264578979231$ and
$f_B=64.29440244394192\ \mathrm{MeV}$. A broadened prepared $B=1$ field
relaxes toward the stationary solution with final inner excess fraction
$2.93897\times10^{-5}$, total-energy drift below
$3.95\times10^{-4}$ and degree error below
$2.23\times10^{-16}$. The magnetic-moment magnitude ratio and
pion–nucleon coupling meet their thresholds; the absolute isoscalar radius,
proton and neutron magnetic moments, and axial coupling miss the 10-percent
criterion. An independent implementation passes all 78 checks and reproduces
the primary `ADOPT—Mapped conditional leading colour-neutral chiral baryon
benchmark` verdict. The field, action, quantum rule and degree-one initial
sector remain supplied inputs. Hash-checked reconciliation against the six
physical-completion requirements returns `FAIL`, so complete physical matter
formation remains open (`computations/matter-formation-continuum-report.md`
§§30–31).

The separate massive bubble-lattice comparison has a stationary degree-one
radial profile with virial relative residual $9.11\times10^{-12}$. Its
Hamiltonian energy is $77.4452509080$; the inherited radial calibration
convention uses twice that value. Three measured masses set $\mu$ and the
effective coefficients $e_B=4.842429173417474$ and
$f_B=54.126511603191005\ \mathrm{MeV}$, with length unit
$0.7528581473116732\ \mathrm{fm}$. All six target-bearing out-of-fit
diagnostics contradict their thresholds: the electric radius, proton and
neutron magnetic moments, their magnitude ratio, axial coupling and
pion–nucleon coupling. The magnetic radius is reported without a frozen
target and is excluded from that count.

The supplied massive action has a conserved stress tensor and isospin current,
while a coupling to the canonical Cassi sectors remains unselected. The
finite-site configuration space is simply connected and enforces no odd
Finkelstein–Rubinstein character. Its classical impulse and radial profile
therefore leave the quantum state, renormalization and physical particle
identification open. The winding-density endpoint integrals are spatially
unqualified, so the formation decision uses a signed-preimage degree
calculation with 16 fixed regular values. Its vacuum, degree-one hedgehog,
separated-pair, orientation-reversal and reproducibility controls pass. Every
trajectory snapshot is admissible, unambiguous and net-degree zero; pair state
agrees between the full/half time steps and the two finest spatial grids at
all nine shared samples. No snapshot has exactly one hit of each sign for
every target, fixing `DOES NOT EMERGE` through $T=4$ for the supplied action
and impulse. The massive-model normalization is **Mapped**, and physical
matter formation remains **Hypothesized/Open**
(`computations/matter-formation-continuum-report.md` §§32.1–32.7).

The supplied signed scalar interface has independently qualified
normal-bound carrier modes and a surface-growth interval
$0.2722637330<a\le0.3142233130$ with nonnegative bulk potential. Its
complex-direction energetic eigenvalue is $-2$ at $u_\rho=4$, so the
underlying wall is unstable in the stated complex-field subspace.
Surface growth is fastest at zero tangential wave number. The 36 numerical
eigenpairs and source-bound rejection controls qualify this conditional
interface result; they provide no stable finite bubble, incoming-flux
capture or particle cluster. Physical matter formation remains
**Hypothesized/Open**
(`computations/matter-formation-continuum-report.md` §33).

The supplied scalar parent also has a qualified positive-amplitude
coexistence interface at $a=1/16$. Independent collocation and
discrete-energy fronts agree within $1.1948\times10^{-6}$ in surface cost
and $2.2085\times10^{-6}$ pointwise in the fields. The unpinned
finite-grid scalar Hessians satisfy the frozen energetic criteria,
and all four missing/altered-section controls reject invalid input.
The positive surface cost $\sigma=0.8738238914$ enters conditional
large-charge droplet asymptotics. Their stationary scope leaves finite
formation dynamics to a separate calculation. The joint interface verdict is
`SUPPORTS-conditional charged coexistence interface`
(`computations/matter-formation-continuum-report.md` §34).

Diffuse initially charged clouds have independently reproduced finite-time
radial condensation in this supplied scalar parent. Widths $4$ and $8$
at signed charge $\mathcal Q_a=256$ retain independent mean core fractions
$0.7476513$ and $0.5637353$, compared with $0.0545181$ and $0.1537575$
when coupling is disabled. Both widths meet the frozen charge-retention
and mediator-depletion criteria at every sampled time in $32\le t\le48$
on all five schedules. All 64 spatial, domain, time-step and independent
metric comparisons pass. Direct reconstruction of 1,078 field snapshots
across 22 trajectory archives gives maximum normalized diagnostic error
$2.4716341\times10^{-14}$; the five required invalid-input controls reject
their inputs. The exact verdict is
`EMERGES-conditional finite-charge radial condensation`.
The calculation supplies initial charge and restricts the mediator to a real
field. Quantum creation, microscopic action and state selection, and physical
units remain open. For these radiating trajectories, nonradial and
mediator-phase stability, infinite-time survival and particle identity remain
open; the continuum minimizer theorem below is a separate result. Physical
matter formation remains **Hypothesized/Open**
(`computations/matter-formation-continuum-report.md` §35;
`foundations/matter-completion-boundary.md` §17).

The supplied scalar action admits localized continuum energy minimizers.
For the specified positive coefficients and real-mediator/full-complex-carrier
energy space on $\mathbb R^3$, strict binding $I(Q)<\Omega_\infty Q$ implies attainment
and compactness of all minimizing sequences modulo translations and carrier
phase, and Lyapunov orbital stability of the entire fixed-$Q$ minimizer set
under arbitrary small full-energy-space perturbations, including nonradial
perturbations and nearby charges. The verified trial certifies this inequality
for every $Q>Q_{\rm tr}$, with $Q_{\rm tr}\approx149.36022508149227$; at $Q=256$,
$E_{\rm trial}/Q=8.283930463343918<\Omega_\infty=8.717797887081348$.
Here $Q$ is the dimensionless supplied signed charge, distinct from prepared
$Q_C$; the action coefficients are $a=1/16$, $c_\Psi=1/8$ and
$h_C=2.9598260763447164$. This conditional minimizer-set theorem is distinct
from the finite-time radiating-cloud trajectories above: it does not prove
uniqueness, selected profile stability, asymptotic convergence, or cloud
membership, capture or stability, and it excludes complex mediator and gauge
sectors. Physical action selection, quantum creation and state, physical
normalization, spin, statistics, particle identity and physical completion
remain open (`computations/matter-formation-continuum-report.md` §36;
`foundations/matter-completion-boundary.md` §18).

The Hypothesized interscale action has a conditional collective-response
derivation. Eliminating density fluctuations gives a positive phase kinetic
form. With admissible longitudinal connection variation, one bulk branch
propagates and the remaining relative-density fluctuation is static.
The zero spatial/scale mode is gapless; a projected gap depends on supplied
scale boundary data, density and stiffnesses. Exact elimination of the
surrounding field gives causal memory and initial forcing. These results
constrain a local formation model while leaving the bubble's physical
initial state, quantum rule, microscopic action selection and particle
identity open. Complete physical matter formation remains
**Hypothesized/Open** (`computations/matter-formation-continuum-report.md`
§37; `foundations/interscale-current-soliton.md` §12).

The primary quadratic calculation passes 28 checks and its independent
reconstruction passes 24. Full and retarded-memory evolutions agree within
$9.54310\times10^{-13}$ in local complex amplitude; the independent
full-energy drift is $1.26859\times10^{-11}$. The uncoupled local-empty and
globally empty controls give zero local population. These fixed-witness
results carry the verdict `SUPPORTS-conditional cascade response`.

The microscopic-selection calculation qualifies limits on proposed particle
identifications. A scalar half-angle operator fails the full spatial
angular-momentum algebra. Ordinary two-mode Bose/Fermi transfers agree with
the canonical unsaturated drift at one carrier but differ at two; fully
occupied fermionic modes are blocked while the canonical drift leaves their
Pauli domain. Chiral anomaly cancellation admits multiple color counts and,
with a right-handed neutrino, a continuous charge family. These are
**Derived conditional** constraints on supplied microscopic constructions.

The primary passes 68 checks and the independent reconstruction passes 54;
their largest trajectory probability disagreement is
$1.2378986724570495\times10^{-13}$. All four frozen prerequisite controls
return `INCONCLUSIVE` with empty scientific payloads. The joint verdict is
`SUPPORTS-conditional microscopic selection constraints`. Physical action
selection, quantum state and renormalization, particle identity and complete
matter formation remain **Hypothesized/Open**
(`computations/matter-formation-continuum-report.md` §38;
`foundations/matter-completion-boundary.md` §19).


## 6. Mechanism Layer: Two-Fluid Gate Drive Physics (PDE-tested)

| Claim | Tested result | Status |
|---|---|---|
| Held configuration (standing init): in-channel recurring drive drains at short times (ε retained 0.26 at $t=2$, below the undriven floor at t = 4); cross-channel drive at ε-parity pumps (2.08×); the pumped state is sticky, and affirmation recovers the site below the floor at the t = 4 window | `consciousness/gender-as-qi-configuration.md` §8–§8.1 (2026-08-02) | ✅ **Supported at short times** (t ≲ 4 ≈ 0.2/λ at the §8 period); at t = 40 = 2/λ the sustained in-channel drive sits above the decaying undriven floor (drain transient, `consciousness/gender-as-qi-configuration.md` §8.3, 2026-08-04) |
| Open gate (churning init): every recurring drive form and amplitude ≥ 0.09 pumps; no drive form or amplitude settles the gate | `consciousness/neurodivergence-as-gate-configuration.md` §9–§9.2 (2026-08-04) | ✅ **Null on settling** |
| Sub-threshold open-gate drives (0.025–0.05) quench the mean ε transiently without closing the gate; the quench resolves at $t = 40 = 2/\lambda$ as a driven transient, not a lock | `consciousness/neurodivergence-as-gate-configuration.md` §9.3–§9.4 (2026-08-04) | ✅ **Driven transient (partial-lock rejected)** |

The pump/drain asymmetry is bounded at the held-configuration regime—the held drain at short times, ≈ 0.2/λ (`consciousness/gender-as-qi-configuration.md` §8.3); an open gate is not settlable by any recurring drive.

### Computational-Test Program 2026-08-05/06

Thirteen committed computational tests (`runs/` archives the outputs; scripts in `two-fluid/` and `computations/`). Cross-cutting verdicts: the two consciousness-mechanism flagships (pinch two-point, two-bubble dynamical revival) are nulled; the wake structural trio (P44/P43/F₂/F₁) is confirmed; the R-matrix mechanism realization is partial (Wood only); the Q7 canonical real-density organized/random branch-selection ansatz is null in this realization and does not exercise the separate regulated wavefunctional sector; the five-channel $w_a$ shift is real but via gate-structure dynamics, not the documented control-release mechanism; the H₀-tension resolution does not survive the full simultaneous fit; the slow-roll numbers are Mapped with trajectory evidence; the σ₈ headline is normalization-dominated.

| # | Claim | Tested result (2026-08-05/06) | Verdict |
|---|-------|------------------------------|---------|
| 1 | Pinch two-point: φ-scaled correlation peaks after crossing the pinch | Field crosses cleanly (t_c = 8.8, r̄ 0.5→1.19) but ⟨r(x)r(x+d)⟩ develops no φ-scaled peaks post-crossing; pre/post indistinguishable; above-pinch counterfactual featureless (`two-fluid/run_pinch_correlation.py`; run record is not retained in this checkout; regenerate with that script) | ❌ **Null** |
| 2 | Two-bubble dynamical revival at large separations | Revival structure gate-independent (max per-sep delta 0.0003) and frozen from t = 0 (corr(t=0)==corr(t=1000)); nominal {31,34,37} wrap under periodic BCs to {17,14,11}; 2026-07-19 aggregate ratios reproduce but inflated by the φ-set occupying smaller physical distances (distance-matched 1.1–1.7×) (`two-fluid/run_two_bubble_gate_scan.py`; run record is not retained in this checkout; regenerate with that script) | ❌ **Null on dynamics** (static-geometry protocol feature) |
| 3 | R-matrix sheng redistribution in the five-channel solver | gate_model='five' realizes it only for Wood closure, allocated by ACTIVE openness b_i·w_i not baseline b_i; measured Wood blend (0, 0, 0.5, 0.309, 0.191) vs R-row (0, 0.447, 0.276, 0.171, 0.106)—ordering matches, proportions don't; rows 2–5 have no gate term; Earth cannot close (w3 ≡ 1) (`two-fluid/run_rmatrix_redistribution.py`; run record is not retained in this checkout; regenerate with that script) | ⚠️ **Partial** (Wood only) |
| 4 | Five-channel w_a shift toward DESI | Five-channel gate gives w_a = −0.425 ± 0.1 vs single-channel ≈ −0.09 ± 0.10 at the PDE layer (−0.44 ± 0.15 differential; five ~1.1σ from DESI w_a = −0.73 ± 0.28); measured Δ(1−q) ≈ ±0.01, not the documented +0.055—the shift is gate-structure dynamics, not control-release; pentagon gate NaN at a ≈ 0.38–0.66 at the default cap; five_ke inconclusive (`two-fluid/run_pde_wa_test.py`, `two-fluid/run_pde_wa_5channel.py`; run record is not retained in this checkout; regenerate with those scripts) | ⚠️ **Partial-support** (mechanism mismatch) |
| 5 | Q7 canonical real-density organized-vs-random branch selection | No organized drive (uniform, anti-phase, single-path) selects a branch of the symmetric two-branch state; equal-power random drive rectifies both branches into a same-sign phase lock; the state has no fast coherent oscillation ($P_0$ is an FFT artifact), so the phase-matching channel was unreachable at $t=4$ (`two-fluid/run_coherence_budget_contrast.py`, `runs/q7_coherence_budget/`). The test contains no configuration-space wavefunctional, quantum-equilibrium ensemble, or topological apparatus sector and therefore supplies no verdict on that conditional quantum construction. | ❌ **Null** for the real-density ansatz (protocol caveat) |
| 6 | TR3 phase-matched trigger | Fire trigger re-locks Fire (23× control)—phase-matched re-lock confirmed; Wood trigger also re-activates the released site into Wood (39× control)—reactivation is channel-selective, not lock-memory-specific (`two-fluid/run_trigger_wx2_tests.py`, runs/20260806_001658_trigger_wx2/) | ⚠️ **Partial** |
| 7 | WX2 κ³ = 0.236-per-cycle damping | Not reproduced: per-P0 retention 0.944 vs 0.764 predicted; gate-level mean 0.389 vs 0.764; sub-critical direction holds; ke ring adds no locked-channel damping (Δγ < 0.001) (same script) | ❌ **Not matched** |
| 8 | Wake structural trio (P44 checkerboard, P43 closure, F₂/F₁ sharpening) | P44: nulls at (m+½)ℓ_{n+1} to 0.0023 grid precision, beats at m·ℓ_{n+1} to 0.00015; P43: beats land on m·ℓ_{n+1} to grid scale; F₂/F₁ = 0.617621 vs 1/φ = 0.618034 (−0.07%), cross-ratio φ³ exact, requires the documented Π∇Φ force form (`two-fluid/run_wake_structural_probes.py`, commit 168a11a) | ✅ **Supported** |
| 9 | N_pde χ-bridge | Closes in [0.5, 1.0] only under the N² (2D section) reading (χ = 0.980); literal 3D count gives χ = 47; "exact closure" 2350.6 is a back-solved constant rearrangement (m_e·v₀²·φ⁹); documented L/dt values appear in no run script; code-default N=64 gives χ = 1.74 (out of band) (`computations/n_pde_bridge_check.py`) | ⚠️ **Convention underdetermined** |
| 10 | Proton stability mechanisms | The stated GUT inputs give $\tau_p=1.29\times10^{37}$ yr, 2.1 orders above Hyper-K reach; the boxed $3.99\times10^{34}$ yr corresponds to $M_{\text{GUT}}\approx4.7\times10^{15}$ GeV rather than the registered input. The separate coherence-budget chain uses $N_p^{\mathrm{budget}}=91.46$, giving $N_{\max}=\varphi^{4505.5758}$; its $\tau_p\sim10^{910}$ yr value requires the Hypothesized per-step profile and Compton-cycle trial map. The scale circuit has zero total flow, normalized relative current $0.0162173$ and normalized energy $0.0509481$ on the Mapped proton interval. Point flux, an auxiliary core and a neutral carrier supply conditional support. The separate particle action preserves an empty closed carrier sector. Its Cartesian localized branch has a finite-grid low spectrum but fails the smooth-carrier diagnostic; independently reproduced prepared smooth scalar binding has INCONCLUSIVE constrained spatial stability. Physical production, normalization, proton identity and decay rate remain open (`computations/matter-formation-continuum-report.md`; `foundations/proton-coherence-budget.md`) | **Conditional mechanisms; finite-grid spectrum and prepared smooth scalar binding Tested; physical rate open** |
| 11 | σ₈ magnitude | The 2026-08-07 truth campaign (`runs/44-truth-campaign/`, N = 32/64/128, the linear-P(k) IC normalization—pk_norm ≡ 1; the tophat-field P(k) fudge it replaces is N-dependent: 8e-5 at N=32, σ₈_field 0.0068/0.0011/0.0002 at N=32/64/128 for a σ₈_Pk = 0.8 IC): the total **−20.5%** (σ₈_ΛCDM 0.9917 vs σ₈_Cassi 0.7884 at a_f = 1.80; resolution-converged: −20.4% at N=32 → −20.5% at N=64/128; the D = 0 re-measurement of the same row—the doctrine default, 2026-08-08, brief 63, N=128—reads **−22.9%**, σ₈_Cassi 0.7649: the totals carry the diffusion, Δ 2.37 pp; the mechanism row is D-insensitive) and the mechanism-attributable row **+29.7%** (G_eff = 1.297, q 0.30 → 0.41—the doctrine r₀'s deep-Yin window relaxes upward, growth enhancement; r₀-dependent: +29.4% at the derived r₀ = 0.0472, N=128; resolution-converged to 0.1 pp across N ∈ {32, 64, 128}); the +24% ΛCDM linear-growth reference reproduces exactly; the −50 pp total-vs-μ gap is the expanding box's own growth deficit (δ_rms −15.7% at N=128 while ΛCDM linear growth is +24%)—a regime/transport property, not resolution; "~5%" is a Mapped target (μ = 0.98 → −5.3%) (`computations/sigma8_reconciliation.py`—the μ-only row, σ₈(P·G_eff²) = G_eff·σ₈(P)); doctrine 2026-08-07: P-A operative, IC r₀ = 0.0472/1/23; the settlement rows −16.6% (R = 0.834) / −15.2% are the growth-window machinery's reading | ⚠️ **Measured** (doctrine-IC rows: mechanism +29.7% D-insensitive; total −22.9% at the D=0 doctrine default / −20.5% at the campaign's D=0.001—the totals carry the diffusion) |
| 12 | Full H(z) fit resolves H₀ tension | Under calibrated CPL values (w₀ = −0.87, w_a = +0.012 baseline, −0.38 coupling), Cassi w(a) does not resolve: dark energy negligible at z~1000–1100, R_cmb = 1.00000, χ² ≈ 25.1 (same as ΛCDM, anchor separation 5.0σ); ΔH₀ = −7.2 comes only from the ODE pipeline model whose w(a) is right-clamped at +0.37 (radiation-like) for z > 99—an extrapolation beyond the calibrated range (a ≥ 0.01) (`computations/hz_full_fit.py`) | ❌ **Not resolved** |
| 13 | Slow-roll trajectory gives n_s = 0.9691, r = φ⁻¹² | (n_s, r) = (0.813, 0.188) under 1 step = 1 e-fold; (0.914, 0.060) with N_e = 40 literal (1 step = ln φ physical e-folds)—n_s 12–36σ from Planck, r excluded by BK18; the two claimed numbers do not coexist (r = φ⁻¹² only at ~135 physical e-folds before the window end, where n_s = 0.9883, +5.6σ); N_e = 40 is a start-threshold choice, not a derived count; ledger Mapped flags confirmed (`computations/slow_roll_trajectory.py`) | ❌ **Fails** (Mapped with trajectory evidence) |

---

## 7. Synchrotron Polarimetry

| Prediction | Cassi Value | Experimental | Status |
|-----------|-------------|--------------|--------|
| Log-periodic polarization orientation (prediction 48) | $\text{PA}(\nu\varphi^k) = \text{PA}(\nu)$ (mod $\pi$), period $\Delta(\ln\nu) = \ln\varphi$; 90° rotation at quarter-rung separation ($\nu_2/\nu_1 = \varphi^{1/4}$); half-rung pair ($\nu_2/\nu_1 = \sqrt\varphi$) parallel (mod $\pi$) | Crab Nebula mm-band PA is constant (~138–142°) over $\Delta\ln\nu = 1.26$ (2.6 rungs); 0/10 band pairs within 3σ | ❌ **Null at face value**—prediction 48 does not fit the Crab Nebula mm-band polarization angle: the constant-PA fit beats the log-periodic spiral fit, and the spiral is excluded against a search-corrected uniform-angle null (p = 0.77) (`experiments/demystifying_cosmos/pa_logperiodic_test.py`, 2026-08-06) |

---

## 8. Space-Sim Coherence-Field Measurement (owner's live config)

Measured in the owner's space-sim (Godot; headless probe; commits af9d2f9,
3eb605b there, not pushed) at the **true live config**: 128³ grid, 2.5M
particles, meshless tree gravity ON, dual-grid ON, black holes ON, multi-rung
seed ON ×6, single cluster, cluster_radius 50, gravity_mode 4, river
calibration, φ-aspect box $(φ,1,φ^2)$, source_strength 0, dt 0.05.

| Quantity | Measured | Reading |
|----------|----------|---------|
| Coherence ripple speed $v_c$ | ≈ 0.92 cells/unit-t ≈ the wave speed c | ✅ **Confirmed**—coherence ripples at the wave speed, distinct from particle motion ("coherence ripples differently than it moves") |
| Particle/coherence speed ratio | $v_p \approx 559$, $v_c/v_p \approx 0.00164$, ratio ~610×, ~900σ separation from equal | ✅ **Confirmed**—coherence ≈ 610× slower than particles; both q conventions agree |
| Clumping morphology | Single dominant box-scale mode; theory-q radial fractions (shells to 10) ≈ 1.0, 0.169, 0.0352, 0.00502, 0.00101, 0.000618, …; color q ($E_Y^2+E_I^2$) ≈ 1.0, 0.359, 0.164, 0.0626, 0.0198; dominant_mode_count = 1 | ✅ The field clumps (single-scale condensation) |
| Emergent φ-clump ladder | ladder_ratios empty; autocorr clump-lags empty; pre-registered MIN_MODES=3 gate fails | ❌ **NO-PHI-LADDER**—single-scale clumping, not a φ-spaced clump ladder, in the sim's free dynamics; both q conventions agree |

The clumping null is recorded against the *emergent φ-spaced clump ladder*
sub-claim only; the condensation-lattice morphology claim
(`foundations/qi-as-spatial-spacing-signal.md` §2) is untouched. Caveat on
record: the null used radial-only $|k|$-shell collapse, which can **hide** a
ladder if an ellipsoidal clump smears power across shells but cannot
**create** secondary modes; a direction-resolved per-axis spectrum was not
run. The ripple confirmation supports the two-channel (wave-phase vs advective) separation of the wedge doc §1.
---

## 9. Physical-Becoming Hierarchy Audit (present-state, `foundations/physical-becoming-hierarchy.md`)

The physical-becoming integration adds a microscopic actual-physics sector, an agent-level reaction hierarchy, an EFT operator basis, gravity closure, and an open-system bath to the canonical two-fluid framework. The two rows below audit the present-state physical-completion gates that the audit found either conditional or unclosed; they are **not** gravity-sector predictions and are kept distinct from the §3 gravity table.

| Gate | Present-state claim | Status |
|---|---|---|
| Canonical q-gated response (conditional canonical reduction; catalog Prediction 55) | Derived conditionally from the two-fluid PDE: fixed-ρ reference tail $\Gamma=\lambda/3$, q-curvature $-\varphi^2\varepsilon^2/9$, spatial pole $Dk^2+\lambda/3$. Physical-unit transduction is left open. Verified by `computations/verify_physical_becoming_reduction.py`. | ⚠️ **Derived conditional on the selected q-gated PDE; not experimentally tested** |
| Two-singlet EFT basis | The unrestricted two-singlet EFT basis is radiatively closed at one loop. The restricted φ-attractor quartic surface fails one-loop RG invariance except on the O(2) radial ray with $\lambda_A=0$, so it functions as a matching condition rather than a UV prediction. | ⚠️ **Radiatively closed (unrestricted); matching-only on the φ-attractor quartic ray** |

These rows record the current completion state of the physical-becoming integration without upgrading any claim in `foundations/physical-becoming-hierarchy.md`.

---

## 10. Phase-Staggered Scale-Gap Campaign (2026-08-27)

The frozen parent and closure protocols are
`field-experience/phase-staggered-scale-gap-pre-registration.md` and
`field-experience/phase-staggered-scale-gap-lock-in-pre-registration.md`.
The combined record is
`field-experience/phase-staggered-scale-gap-report.md`.

| Claim | Decisive measurement | Status |
|---|---|---|
| Supplied adjacent-rung beat layers | closure residual $1.776\times10^{-15}$; node maximum $2.305\times10^{-14}$; adjacent/next-nearest demodulated correlations $-1/+1$; unequal-amplitude contrast residual $0$ | **SUPPORTS supplied-wave phase parity and contrast law** |
| Ordinary radial beat as multiplicative ladder | additive residual $0$; log-spacing RMS $0.502630$ | **CONTRADICTS multiplicative spacing from ordinary radial beating** |
| Default second-order imbalance threshold | exact $\Omega_g=\varphi\omega_{0,\mathrm{wave}}$; lock-in $\kappa_{\rm fit}=0.705275510$ vs $0.705284664$ expected; sub-gap attenuation $3.067\times10^{-6}$ | **SUPPORTS second-order channel threshold** |
| Driven radial phase layers | tuned $k_\rho/k_\epsilon=1.618096626$; generic control $1.311855471$; valid parent/lock-in propagating rates agree within $1.319\times10^{-4}$ | **EMERGES CONDITIONAL on a supplied harmonic drive; parent time-domain Stage D remains INCONCLUSIVE** |
| Endogenous $\Omega_*$ selection | exact $\varphi$ ratio occurs only at supplied $\Omega_*=\varphi^{3/2}\omega_{0,\mathrm{wave}}$; current live source path has no harmonic selector | **CONTRADICTS automatic $\varphi$-ratio selection** |
| Phase staggering as a transfer gap | uniform-chain central gap $8.228\times10^{-17}$ under exact gauge equivalence | **CONTRADICTS phase-only gap** |
| Physical link-magnitude modulation | declared $K_1=1.25$, $K_2=0.75$ chain has gap $1.0000000000000007$ and 12-cell transmission $4.738\times10^{-6}$; the live wave pass computes $q$ after update and does not feed it back into coupling magnitudes | **EMERGES CONDITIONAL; node-to-link constitutive law remains open** |
| Canonical nested radial ladder | prior four-arm first-order and undriven second-order `NO RINGS` receipts remain controlling; driven layers are additive | **REJECT tested dynamical realization of Prediction 51** |

Both parent time-domain receipts retain `INCONCLUSIVE`: their sub-gap lock-in
windows contain undamped travelling transients, and a literal
all-metrics-finite reading also flags the intentionally undefined D0/D3
reference and fit fields. The independent frequency-domain closure is `PASS`;
it does not relabel either parent receipt. The post-execution integrity audit
also finds that the executed C4 Boolean used $10^{-9}$ while the registered
threshold is $10^{-12}$: the measured $4.056\times10^{-11}$ is a formal C4
failure under the registration. The committed source gate now matches the
registered threshold, and no additional evidentiary run is introduced.

---

## 11. Conditional Qi-Loop Mass-Cascade Campaign (2026-08-27)

The frozen protocol, executed record, and conditional algebra are
`field-experience/qi-loop-mass-cascade-pre-registration.md`,
`field-experience/qi-loop-mass-cascade-report.md`, and
`foundations/qi-loop-mass-cascade.md`.

| Claim | Decisive measurement | Status |
|---|---|---|
| $\varphi$-separated compact phase-gradient branch | Exact Fibonacci record list; maximum identity residual $1.0165147637976205\times10^{-14}$; $\sqrt2$ control gap $0.09366495891647209$; 19-mode ring sector passes radial/phase/current and supplied-scale gates | **EMERGES CONDITIONAL**—the compact topology, normalized coefficients, and tension law are supplied |
| Unique mass positions from the ring energy | 1,163 stable primitive modes across the scan, up to 528 in one occupied $\varphi$-log cell; coefficient span $0.1146965060733196$ rung against a $0.01$ gate | **DOES NOT EMERGE**—the current ring law leaves topology and constitutive selection open |
| Frozen-receipt integrity | All four frozen qualification checks pass; an independent verifier recomputes 172 Boolean values and 692 finite scalars with zero differences | **PASS** |

The calculation uses no particle catalog or measured particle mass. Its
classical loop energy is a conditional proxy, not an $\hbar\Omega$ quantum
identification or a physical mass assignment.
