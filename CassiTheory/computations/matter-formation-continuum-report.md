# Carrier Creation and Continuum Density Trapping

## Status: Tested—September 2026

## Abstract

The first-order carrier action preserves an exactly empty closed carrier sector. Its stored Cartesian localized fields fail a smooth-carrier diagnostic: the squared-spacing-weighted edge energy stays nearly constant while the carrier concentrates on one parity sublattice. A separate continuum-consistent radial calculation independently reproduces static binding at prepared $Q_C=16$ and $256$. The population-256 endpoint has lower energy per carrier, a larger RMS radius and a more strongly depleted mediator core than the population-16 endpoint. These two qualified endpoint measurements establish no preferred particle size, scaling law or quantum-number assignment. The $Q_C=4$ profiles spread with the domain, and the stopped $Q_C=64$ endpoint is unqualified. Smooth $Q_C=16$ constrained spatial stability remains `INCONCLUSIVE`. Microscopic production, full dynamics, normalization and physical particle identity remain open.

## 1. Scope and frozen evidence

The protocol is `computations/matter-formation-continuum-prereg.md`. Its canonical CRLF-to-LF SHA-256 is `806ce855d738325bb2596da0f7dafe4270c13992bf5690f7ab03c95f99ed245f`.

The source is the scale-independent, constant-vacuum-boundary, topologically trivial sector of `foundations/particle-stationary-action-closure.md`, with unit scale measure and

$$
u_\rho=u_\varphi=u_H=4,\qquad \gamma_x=k_{Cx}=u_C=1,
\qquad e_C=0.75,\qquad h_C=2.9598260763447164.
$$

The coefficient $h_C$ is Mapped: it is selected numerically in the particle-support campaign. The charges $4,16,64,256$ are prepared dimensionless populations. They carry no identification with electric charge, baryon number, a particle count, or a measured rest mass. No coefficient is fitted or scanned in this calculation.

A complete matter mechanism requires a physically specified microscopic action and production channel, finite-energy continuum states, their stability and formation dynamics, physical normalization, particle quantum numbers and statistics, and independent empirical discrimination. Static density trapping addresses one part of this chain.

## 2. Empty-sector obstruction

The carrier population cannot emerge from exactly empty carrier data under the supplied equations. The continuity law in `foundations/particle-stationary-action-closure.md` §8.7 gives

$$
\frac{dQ_C}{dt}=0,\qquad Q_C=\int|\chi_C|^2\,d^3x\,ds\ge0,
\qquad
\boxed{Q_C(0)=0\ \Longrightarrow\ \chi_C(t)=0.}
$$

This statement assumes a well-posed evolution and no boundary carrier flux. A changing density trap multiplies the carrier field in its homogeneous first-order equation. It changes the motion and energy of an existing population without supplying a source for an empty population.

The normal-ordered carrier Hamiltonian also preserves number: hopping terms, density potentials and the quartic repulsion commute with the number operator. `computations/matter_formation_action_check.py` evaluates a two-mode algebraic witness containing all three term types. Its maximum number commutator is $1.3322676296\times10^{-15}$. A sequence of time-dependent density potentials leaves the vacuum difference and induced number exactly zero in the computation. The finite-mode witness checks the algebra; the continuum conservation law establishes the conditional obstruction.

A relativistic field can carry a signed Noether charge while supporting particle–antiparticle production with zero total signed charge. The present nonnegative carrier norm does not supply those degrees of freedom or an interaction that creates them. A microscopic extension needs a declared quantum state, an energy source and physically normalized couplings before a production rate can be calculated.

## 3. The Cartesian carrier branch is ultraviolet-dominated

The nearest-neighbour gradient exposes structure that the centred derivative fails to control. All four source artifact hashes match the preregistration. The independent implementation reproduces every scalar diagnostic and parity fraction within the frozen tolerance, with zero mismatches.

| Cartesian $N$ | Carrier high-frequency fraction | Centred carrier gradient energy | Edge carrier gradient energy | $\Delta x^2T_{\rm edge}$ | Largest parity norm fraction |
|---:|---:|---:|---:|---:|---:|
| 17 | 0.8716648329 | 1.8113757 | 47.8448041 | 11.9612010 | 0.9994605271 |
| 21 | 0.8737952054 | 1.7445004 | 74.8200570 | 11.9712091 | 0.9997837076 |
| 25 | 0.8741672013 | 1.7137257 | 107.8149354 | 11.9794373 | 0.9998762357 |
| 29 | 0.8744032064 | 1.6915998 | 146.7857405 | 11.9825094 | 0.9998631608 |

The finest source has $99.98631608\%$ of its carrier norm on one parity sublattice. Its high-frequency fraction agrees with the localized Hessian's recorded phase diagnostic within $2\times10^{-9}$. The two finest edge-to-centred energy ratios exceed the threshold of four, and their $\Delta x^2T_{\rm edge}$ values agree much more closely than the required 20%.

The scaled edge energy changes by approximately $0.18\%$ across the four grids, while the unscaled edge energy grows from $47.84$ to $146.79$. This combination identifies persistent lattice-scale structure in the stored fields. It does not exclude other localized solutions of a continuum-consistent action.

For a centred derivative,

$$
\widehat D_0(k)=\frac{i\sin(k\Delta x)}{\Delta x},
\qquad
\widehat{D_0^*D_0}(k)=\frac{\sin^2(k\Delta x)}{\Delta x^2}.
$$

The Nyquist zero allows oscillatory fields to have small centred-gradient energy. In contrast, the edge energy has symbol $4\sin^2(k\Delta x/2)/\Delta x^2$. The periodic alternating control has centred energy zero and edge energy 8192. The smooth Gaussian controls have edge-to-centred ratios near one and negligible high-frequency power. Thus the measurement distinguishes a smooth profile from the stored parity-concentrated carrier.

The machine-readable scientific verdict is `CONTRADICTS`. Its scoped label is

$$
\boxed{\text{CONTRADICTS—smooth-carrier interpretation on the measured sequence}.}
$$

The edge energy is a diagnostic on the immutable carrier arrays. It is not the energy of a re-relaxed full gauge action, and four grids do not establish an infinite-sequence theorem. The stored finite-grid stationary and Hessian results retain their numerical scope. A continuum particle claim cannot use them without resolving this ultraviolet structure.

## 4. Exact scalar reduction and numerical method

The trivial continuum sector admits a density-trap calculation without the Cartesian centred-derivative pathology. The covariant diamagnetic inequality and constant-composition representative reduce its energy infimum to the scalar functional in `foundations/particle-stationary-action-closure.md` §8.7. Clipping $0\le f\le1$ and simultaneous rearrangement of the depletion $w=1-f$ and carrier $c$ give a radial infimum under the stated Sobolev, boundary and topology assumptions. These statements concern infima; they do not establish attainment on infinite space or classify all stationary solutions.

The finite-volume computation uses exact spherical cell volumes, one gradient contribution per radial face, zero origin flux, and the outer half-cell Dirichlet conductance. Both the optimizer gradient and the stationary residual follow this same action and mass inner product. Carrier normalization is direct and positive. A directional finite-difference check of the normalization pullback agrees to relative error $2.47\times10^{-9}$ at step $10^{-5}$ and $6.18\times10^{-10}$ at step $10^{-6}$; the charge-normal residual is orthogonal to the carrier in the volume inner product. These are implementation checks before the physical campaign.

Each prepared charge uses four frozen coarse profiles at $R=12$ with 192 cells: Gaussian widths 1, 2 and 4, and a diffuse cosine. The lowest-energy qualified endpoint is continued to 384 and 768 cells. The $R=24$, 768-cell domain control is initialized from $R=12$, 384 cells, preserving the spacing. Every coarse profile is retained in the receipts. Continuation stops when a field fails the physical stationary tolerance.

An independent implementation recomputes all finite-volume quantities from raw arrays, then solves the continuum radial equations by adaptive collocation for the qualified bound branches. It uses neither primary gradients nor primary operator routines. The source hashes and all NPZ hashes are checked before comparisons.

## 5. Measured static results

The original prepared population spreads, while larger prepared populations can bind at these selected coefficients. The table contains the finest $R=12$ endpoints, including the unqualified, stopped $Q_C=64$ continuation:

| Prepared $Q_C$ | Energy | Exterior threshold $e_CQ_C$ | Frequency $\omega_C$ | Carrier RMS radius | Verdict |
|---:|---:|---:|---:|---:|---|
| 4 | 3.1263033611 | 3 | 0.7787659711 | 6.2447280124 | DOES NOT EMERGE in tested basins |
| 16 | 10.6754974802 | 12 | 0.2879217680 | 1.6393501068 | EMERGES, conditional static binding |
| 64 | 9.4407095155 | 48 | −0.1784742340 | 1.8999249908 | INCONCLUSIVE; stopped continuation, unqualified |
| 256 | −55.5099075672 | 192 | −0.4220778423 | 2.7549255181 | EMERGES, conditional static binding |

For $Q_C=4$, all four coarse endpoints are qualified and diffuse. Increasing the domain from $R=12$ to $R=24$ changes the RMS radius from 6.2447 to 12.6305, the energy from 3.1263 to 3.0329, and the frequency from 0.77877 to 0.75789. The carrier follows the box while its energy approaches the exterior threshold of 3. The tested profiles do not produce a localized bound branch. This finite search does not prove nonexistence at $Q_C=4$.

For $Q_C=16$, all four coarse profiles reach qualified bound endpoints. The two finest fixed-domain grids differ in energy by $0.009614\%$ and radius by $0.013544\%$; their frequency difference is $8.5390\times10^{-5}$. The same-spacing domain comparison agrees in energy to $2.75\times10^{-9}$ relative and in radius to $3.03\times10^{-7}$ relative. The carrier fraction outside half the $R=24$ domain is $9.90\times10^{-10}$.

For $Q_C=64$, the finest density-field residual is $1.3512224134\times10^{-4}$ against the frozen limit $10^{-4}$. The carrier residual is $6.6119238427\times10^{-6}$. The optimizer reports its own relative-energy stopping condition, but the physical residual rejects qualification. The declared continuation stops, so no larger-domain endpoint or continuum collocation is evaluated for this charge. The outcome is retained without a retry or threshold change.

For $Q_C=256$, the two finest grids differ in energy by $0.010123\%$ and radius by $0.001588\%$; their frequency difference is $1.2064\times10^{-5}$. The same-spacing domain comparison also passes. Its carrier fraction outside half the $R=24$ domain is $1.15\times10^{-12}$.

The independent continuum collocation results are:

| Prepared $Q_C$ | Continuum energy | Continuum frequency | Continuum RMS radius | Relative energy difference from finest FV |
|---:|---:|---:|---:|---:|
| 16 | 10.6758395100 | 0.2879502058 | 1.6394238845 | $3.2038\times10^{-5}$ |
| 256 | −55.5080345553 | −0.4220738661 | 2.7549401291 | $3.3742\times10^{-5}$ |

Both collocation solves converge at the frozen tolerance, use 1536 nodes and satisfy the independent energy, radius and frequency comparisons. The verifier reports `pass: true` with zero failures for its numerical comparisons. Its aggregate scientific verdict is `INCONCLUSIVE`, and its exit code is 1, because the registered $Q_C=64$ branch is inconclusive. This aggregate does not erase the separate verified outcomes for the other charges.

## 6. Energy normalization and physical meaning

The homogeneous potential separates local density minimization from the density of a zero-pressure bulk droplet. Writing $n=c^2$ in the fully depleted $f=0$ profile gives

$$
V(0,n)=\frac{u_\rho}{4}+(e_C-h_C)n+\frac{u_C}{2}n^2.
$$

Minimizing this energy density over $n$ yields

$$
n_*=\frac{h_C-e_C}{u_C}=2.2098260763,\qquad
V(0,n_*)=\frac{u_\rho}{4}-\frac{(h_C-e_C)^2}{2u_C}
=-1.4416656438.
$$

For a fixed carrier population with variable bulk volume, minimizing $V/n$ instead gives the zero-pressure values

$$
n_{\rm sat}=\sqrt{\frac{u_\rho}{2u_C}}=1.4142135624,\qquad
e_{\rm sat}=e_C-h_C+\sqrt{\frac{u_\rho u_C}{2}}
=-0.7956125140.
$$

These expressions use the declared quartic convention $u_Cn^2/2$. They neglect interfaces and gradients. The local energy-density minimizer $n_*$ is not the zero-pressure density of a large finite-population droplet. The negative values are relative to the declared homogeneous exterior reference; no absolute mass scale follows.

### 6.1. Measured charge dependence

The qualified population-256 endpoint is larger and more strongly depleted than the population-16 endpoint. The following post-campaign descriptive calculation reads immutable arrays without relaxation or changes to any verdict (`computations/matter-formation-scaling-prereg.md`; `computations/matter_formation_scaling.py`):

| Prepared $Q_C$ | Qualification | $E/Q_C$ | $r_{C,\mathrm{rms}}$ | $r_{C,\mathrm{rms}}/Q_C^{1/3}$ | $\min f$ | $\max c^2$ |
|---:|---|---:|---:|---:|---:|---:|
| 4 | Qualified, diffuse | 0.7815758403 | 6.2447280124 | 3.9339321369 | 0.9969615518 | 0.0041890641 |
| 16 | Qualified, bound | 0.6672185925 | 1.6393501068 | 0.6505765210 | 0.3255853164 | 1.3788520596 |
| 64 | Stopped continuation, unqualified | 0.1475110862 | 1.8999249908 | 0.4749812477 | 0.0436415096 | 1.9012591373 |
| 256 | Qualified, bound | −0.2168355764 | 2.7549255181 | 0.4338735814 | 0.0029885727 | 1.7815422848 |

The comparison of bound states is restricted to the two qualified endpoints at prepared populations 16 and 256. The stopped population-64 values supply no qualified stationary result, and the population-4 states are diffuse. This descriptive analysis assigns no morphology classification or scaling exponent. The finite charge set leaves the size dependence between sampled populations, any asymptotic law and any preferred particle size undetermined.

The large bound endpoint is also independent of the tested box size at fixed spacing. Direct reconstruction gives:

| Prepared $Q_C$ | Relative energy difference, $R=12$ versus $24$ | Relative RMS-radius difference | Interpretation |
|---:|---:|---:|---|
| 4 | $2.9865\times10^{-2}$ | $5.0558\times10^{-1}$ | The carrier spreads with the box |
| 16 | $2.7482\times10^{-9}$ | $3.0284\times10^{-7}$ | Bound endpoint agrees at the tested spacing |
| 256 | $2.4654\times10^{-11}$ | $2.5548\times10^{-10}$ | Bound endpoint agrees at the tested spacing |

These comparisons use $R=12$ with 384 cells and $R=24$ with 768 cells. Agreement of the static profile does not establish domain-converged fluctuation spectra.

At total prepared population 256, the qualified single-lump energy is $-55.5099075672$. Sixteen asymptotically separated population-16 lumps have trial energy $16E(16)=170.8079596834$ under the common exterior reference and negligible interactions. This particular energetic comparison favors the single large lump by $226.3178672506$. It supplies no real-time merger result and no stability test against every possible partition. Population 8 is absent, so there is no population-16 two-lump fission calculation. The diffuse population-4 box states cannot serve as localized fragments.

### 6.2. Physical identification boundary

The density-depletion mechanism is related to scalar non-topological soliton constructions such as the Friedberg–Lee–Sirlin model. Heeck and Sokhashvili study a relativistic second-order complex carrier with a Noether charge and a real-scalar mediator. Here $c$ is the nonnegative modulus of a first-order, gauge-neutral carrier with explicit self-repulsion and a conserved nonnegative population. The stationary ansatz has a rotating global carrier phase, while the measured binding is conditional density-trap self-binding at prepared population. Its microscopic interpretation, signed charge content and quantization require separate specification. A radial scalar profile supplies no derivation of fermionic spin, exchange statistics or the observed particle spectrum.

## 7. Constrained smooth-branch spectrum

The smooth $Q_C=16$ solution has positive measured fixed-charge radial curvature, but the registered calculation does not establish domain-converged stability. The protocol in `computations/matter-formation-stability-prereg.md` fixes four raw stationary fields, six lowest eigenpairs per operator, the charge constraint, symmetry tests and resolution comparisons before evaluation. The mass-weighted amplitude Hessians $H_0|_{T_Q}$ and $H_1$ cover radial and dipole perturbations; a separate operator covers the carrier's imaginary component. Higher angular degrees add a nonnegative diagonal term to $H_1$ within this discretization.

For an exact positive stationary carrier, the ground-state identity in
`foundations/particle-stationary-action-closure.md` §8.7 makes the phase
quadratic form nonnegative and assigns its zero mode to the global carrier
phase. The numerical phase spectrum therefore checks the operator and
stationarity; it supplies no independent resolution of the coupled-amplitude
stability question. The frozen numerical criteria below remain unchanged.

| Domain $R$ | Cells | $\lambda_{\min}(H_0|_{T_Q})$ | Dipole translation eigenvalue | Carrier phase eigenvalue | Per-grid verdict |
|---:|---:|---:|---:|---:|---|
| 12 | 192 | 0.9602007145 | $1.0813732\times10^{-3}$ | $-6.34\times10^{-14}$ | INCONCLUSIVE |
| 12 | 384 | 0.9592902485 | $2.7061763\times10^{-4}$ | $-4.62\times10^{-13}$ | SUPPORTS |
| 12 | 768 | 0.9590618442 | $6.7573474\times10^{-5}$ | $-7.95\times10^{-13}$ | SUPPORTS |
| 24 | 768 | 0.9322048141 | $2.7062583\times10^{-4}$ | $-6.78\times10^{-13}$ | SUPPORTS |

Every measured eigenpair residual is below $2.19\times10^{-11}$, and the phase and translation overlaps exceed $0.9999998$. The coarsest translation eigenvalue exceeds its zero-mode tolerance $5\times10^{-4}$. The two finest fixed-domain radial minima agree: their difference is $0.0002284042$ against tolerance $0.0095929025$. The same-spacing domain difference is $0.0270854344$, exceeding that tolerance. The frozen combined verdict is therefore

$$
\boxed{\text{INCONCLUSIVE—constrained smooth-branch spatial stability}.}
$$

The independent program reconstructs the stiffness, multiplier, constraint basis and spectra directly from the immutable fields. Its accepted receipt reports `pass: true`, zero comparison failures and the same scientific verdict; exit code 1 preserves the inconclusive outcome. No negative eigenvalue is resolved below the stationary-error tolerance. No field is relaxed, omitted or rescanned in this calculation.

The accepted source identities and numerical correction scope are recorded in `computations/matter_formation_stability_execution.json`. The accepted primary and independent receipts are in `runs/20260906_matter_formation_stability_corrected/`. Acceptance requires the recorded canonical source hashes, all four raw-field hashes and the preregistration hash to agree. Receipts outside this accepted chain have no evidentiary role in the table.

The relation to the additional spatial fields is conditional and explicit. For a unit multiplet orientation $u$, unitarity gives $\operatorname{Re}(u^\dagger D_i u)=0$, hence

$$
|D(fu)|^2=|\nabla f|^2+f^2|Du|^2.
$$

At the trivial constant-composition representative, orientation gradients, gauge curvature, adjoint gradients and the composition/adjoint potentials contribute nonnegative quadratic squares. The scalar amplitude mixing remains in $H_\ell$. This decomposition requires the specified topology, stationary composition and compatible boundary data. It supplies no sign claim for additional couplings or nontrivial sectors.

A positive quadratic energy on the physical quotient of a finite closed Hamiltonian system, together with positive inertia, would exclude exponential linear growth. The measured approximate spatial Hessians do not establish those hypotheses for the infinite-volume field theory. Continuum coercivity, mixed temporal dynamics and nonlinear orbital stability remain open.

## 8. Reproduction and retained boundary

Run from the repository root into new, explicitly named output directories when the default receipts already exist:

```text
python computations/matter_formation_lattice.py
python computations/verify_matter_formation_lattice.py
python computations/matter_formation_action_check.py
python computations/matter_formation_radial.py
python computations/verify_matter_formation_radial.py
python computations/matter_formation_stability.py --output-dir runs/20260906_matter_formation_stability_corrected
python computations/verify_matter_formation_stability.py --input-dir runs/20260906_matter_formation_stability_corrected
python computations/matter_formation_scaling.py
```

The lattice diagnostic and algebraic witness are in `runs/20260906_matter_formation/`. The 27 radial endpoint arrays, primary results, independent verification and two collocation arrays are in `runs/20260906_matter_formation_radial/`. The charge and coefficient schedule is frozen; changing an output directory does not authorize a new physical scan. The primary and independent programs preserve first-execution receipts.

The remaining physical questions are the carrier-production action and quantum state, absolute normalization, particle identities and statistics, real-time formation and nonlinear stability, scale-dependent sectors, and empirical discrimination. The spatial stability result retains the frozen inconclusive verdict above.

## References

- `computations/matter-formation-continuum-prereg.md`—frozen continuum, lattice and creation calculations.
- `computations/matter-formation-stability-prereg.md`—frozen constrained spatial operators and decision tree.
- `computations/matter_formation_stability_execution.json`—accepted source identities and numerical correction scope.
- `computations/matter-formation-scaling-prereg.md`—post-campaign descriptive scope with frozen input identities.
- `computations/matter_formation_scaling.py`—population, radius, depletion, bulk and specific-partition summaries.
- `runs/20260906_matter_formation_scaling/scaling.json`—hash-bound descriptive results; parent verdicts unchanged.
- `foundations/particle-stationary-action-closure.md` §8.7—continuity law, conditional scalar reduction, radial equations and ultraviolet boundary.
- `foundations/matter-completion-boundary.md`—full matter-formation requirements.
- `computations/particle-carrier-resolution-recovery-report.md`—four stored Cartesian endpoints.
- `computations/particle-localized-physical-hessian-report.md`—localized finite-grid energetic spectrum and carrier-phase classification.
- `runs/20260906_matter_formation/lattice.json`—primary immutable lattice measurements.
- `runs/20260906_matter_formation/verification.json`—independent lattice measurements and zero mismatches.
- `runs/20260906_matter_formation/action.json`—creation and scalar-composition algebraic checks.
- `runs/20260906_matter_formation_radial/results.json`—all primary basins and continuation endpoints.
- `runs/20260906_matter_formation_radial/verification.json`—independent raw-array checks and charge-specific verdicts.
- `runs/20260906_matter_formation_stability_corrected/results.json`—accepted constrained spatial measurements and comparisons.
- `runs/20260906_matter_formation_stability_corrected/verification.json`—independent spectral agreement and inconclusive scientific verdict.
- [Heeck and Sokhashvili, *Revisiting the Friedberg–Lee–Sirlin soliton model*](https://arxiv.org/abs/2303.09566)—relativistic charged complex-scalar and real-mediator comparison; published March 2023.
