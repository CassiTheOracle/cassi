# Carrier Creation and Continuum Density Trapping

## Status: Derived conditional carrier, parent-vacuum, dilation, fixed-charge and chiral-current identities / Hypothesized physical completion / Tested prepared binding, spatial spectra and microscopic boundaries—September 2026

## Abstract

The first-order carrier action preserves an exactly empty closed carrier sector. Its stored Cartesian localized fields fail a smooth-carrier diagnostic: the squared-spacing-weighted edge energy stays nearly constant while the carrier concentrates on one parity sublattice. A separate continuum-consistent radial calculation independently reproduces static binding at prepared $Q_C=16$ and $256$. The population-256 endpoint has lower energy per carrier, a larger RMS radius and a more strongly depleted mediator core than the population-16 endpoint. These two qualified endpoint measurements establish no preferred particle size, scaling law or quantum-number assignment. The $Q_C=4$ profiles spread with the domain, and the stopped $Q_C=64$ endpoint is unqualified. Smooth $Q_C=16$ constrained spatial stability remains `INCONCLUSIVE`. Microscopic production, full dynamics, normalization and physical particle identity remain open.

A Hypothesized positive-inertia carrier parent has a signed conserved charge and a low-frequency limit matching the first-order equation. Its prescribed-background Gaussian calculation reproduces the standard scalar pair-production correspondence across 31 mode trajectories. The temporal coefficient and action normalization remain unselected, and the calculation omits interacting backreaction and localized production.

The same parent's classical scalar potential has an exact global vacuum boundary. In three dimensions, spatial dilation excludes an energetically stable regular localized single-frequency state with zero signed Noether charge. This restriction leaves charged prepared states, multi-frequency dynamics, quantum bound states and additional topological sectors outside its scope. Ten parent-coefficient witnesses pass independent homogeneous minimization, charge-energy reconstruction and radial-dilation quadrature.

At fixed signed parent charge, all 24 frozen radial embeddings have positive measured amplitude curvature. Independent banded spectra and rank-one inertia brackets verify this finite-grid result. Nine of twelve domain/resolution comparisons pass; the three population-16 domain comparisons fail. The aggregate radial domain qualification remains `INCONCLUSIVE`, and the calculation supplies no all-sector or real-time stability conclusion.

The selected population-256 parent subset also supports the measured angular and phase sectors on all four finite grids. All 96 eigenvalues agree with an independent operator construction. Seven of eight spatial domain/resolution comparisons pass; the first non-translation dipole eigenvalue fails the domain comparison. The combined scalar-parent spatial verdict is `INCONCLUSIVE`. Exact nodelessness and monotonicity give conditional continuum positivity identities, whose assumptions are not established by these sampled profiles.

An independently verified physical-unit calculation leaves a family of scalar models at one imposed vacuum mass, speed and internal generator unit. At the fixed dimensionless coefficients, the extra scalar core-cell assignment is contradicted. The proposed Dirac chiral-scalar map also has exact positivity and Hermiticity obstructions. These results distinguish unit calibration from microscopic particle identification.

The helper's positive component quadratics are twice the chiral-current number densities in its declared spinor representation. Closed Dirac evolution depends on relative coherence and does not supply the canonical population conversion. Adding the specified minimal conversion channel to a massive Dirac Hamiltonian shifts the stationary ratio away from $\varphi$ and allows leakage from the positive-energy one-particle subspace. Independent finite-dimensional witnesses verify these conditional boundaries; a physical reservoir, quantum-state prescription and production interaction remain unselected.

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

## 8. Conditional hyperbolic-parent correspondence

A positive temporal stiffness supplies a candidate quantum creation channel while retaining the first-order spatial equation in its low-frequency limit. The parent action, signed charge, common-cone condition and stationary embedding are derived in `foundations/particle-stationary-action-closure.md` §8.8. This physical extension is Hypothesized. The finite benchmark fixes the mathematical action normalization; the physical prefactor $\mathcal N_Q=\rho_0\ell_Q^3$ remains open.

For the prescribed homogeneous mediator transition, the canonical quadratic modes obey

$$
f^2(t)=\frac{1-\tanh(t/T)}2,\qquad
\ddot u_k+\Omega_k^2(t)u_k=0,
\qquad
\Omega_k^2(t)=\frac{k^2}{2a}+\frac1{4a^2}
+\frac{e_C-h_C[1-f^2(t)]}{a}.
$$

The in-vacuum is normalized by $u_k=e^{-i\Omega_{\rm in}t}/\sqrt{2\Omega_{\rm in}}$ at the finite start. The standard exact occupation for this tanh history is

$$
n_k^{\rm exact}=
\frac{\sinh^2[\pi T(\Omega_{\rm out}-\Omega_{\rm in})/2]}
{\sinh(\pi T\Omega_{\rm in})\sinh(\pi T\Omega_{\rm out})}.
$$

Particle and antiparticle occupations are equal by the global symmetry, so the produced pairs carry zero net signed charge. The quantum in-vacuum has nonzero fluctuations. Exactly zero classical field and velocity still remain zero under the parent equation.

### 8.1 Measured mode correspondence

All 31 frozen mode trajectories and their independent raw-array reconstruction pass. They comprise 27 combinations of $a\in\{1/16,1/32,1/64\}$, $k\in\{0,1,2\}$ and $T\in\{0.05,0.25,1\}$, three constant-background controls and one extended-time-window control. The coefficients and schedule are fixed numerical witnesses; no witness value is selected as physical.

At $k=0,\ T=0.05$, the measured occupations are:

| Parent coefficient $a$ | $\Omega_{\rm in}$ | $\Omega_{\rm out}$ | Occupation per particle/antiparticle mode |
|---|---:|---:|---:|
| $1/16$ | 8.7177978871 | 5.3518952511 | 0.0412273297560 |
| $1/32$ | 16.7332005307 | 13.6119640595 | 0.00212720576601 |
| $1/64$ | 32.7414110875 | 29.7080987462 | 0.0000127085600700 |

The largest discrepancies across the complete finite schedule are:

| Check | Largest measured discrepancy | Frozen limit |
|---|---:|---|
| Absolute occupation error against the exact formula | $4.0246\times10^{-16}$ | $10^{-10}+10^{-7}n_k^{\rm exact}$ |
| Sampled Wronskian defect | $6.0618\times10^{-14}$ | $10^{-8}$ |
| Bogoliubov normalization defect | $6.0174\times10^{-14}$ | $10^{-8}$ |
| Energy-work defect divided by $\max(1,|E_i|,|E_f|,|W|)$ | $5.7215\times10^{-14}$ | $10^{-8}$ |
| Independent Simpson-work discrepancy divided by $\max(1,|W|)$ | $6.0026\times10^{-15}$ | $10^{-7}$ |
| Constant-background occupation | $8.5573\times10^{-30}$ | $10^{-12}$ |
| Extended-window occupation difference | $5.9674\times10^{-16}$ | $10^{-9}$ |

Every sampled $T=1$ occupation lies below its $T=0.05$ counterpart by the required absolute margin. Very small adiabatic occupations are qualified only by the absolute-error criterion; the calculation assigns no relative precision to values below numerical resolution.

The finite-mode energy includes its vacuum reference. For the $a=1/16$ fast witness, $E_i=8.7177978871$, $E_f=5.7931839517$ and external work is $-2.9246139353$. The out-vacuum energy is $\Omega_{\rm out}=5.3518952511$, leaving positive excitation energy $E_f-\Omega_{\rm out}=0.4412887007$. Lowering the mode frequency lowers its vacuum reference while producing excitations relative to the final vacuum. These are finite-mode quantities; a renormalized continuum stress tensor is outside the calculation.

### 8.2 Stationary embedding and physical scope

The same two qualified spatial profiles have a conditional stationary embedding in each parent. The frequency equation is $\omega+a\omega^2=\omega_C$, and the normalized signed charge is $\mathcal Q_a=(1+2a\omega)Q_C$:

| Prepared spatial $Q_C$ | $a$ | Parent frequency $\omega$ | Parent signed charge $\mathcal Q_a$ |
|---:|---|---:|---:|
| 16 | $1/16$ | 0.2829190680 | 16.5658381361 |
| 16 | $1/32$ | 0.2853767711 | 16.2853767711 |
| 16 | $1/64$ | 0.2866379970 | 16.1433189985 |
| 256 | $1/16$ | −0.4338414950 | 242.1170721606 |
| 256 | $1/32$ | −0.4277969110 | 249.1552494245 |
| 256 | $1/64$ | −0.4248987635 | 252.6008098916 |

The physical charge normalization also contains $\mathcal N_Q$. The enlarged fixed-charge dynamical constraint differs from the original fixed-$Q_C$ spatial calculation, whose frozen stability verdict remains `INCONCLUSIVE`.

The correspondence verdict is **`PASS`** in both receipts, with zero independent mismatches. It verifies the supplied quadratic equations, input identities and finite numerical schedule. The parent coefficient materially changes the measured occupations, and the current first-order action does not select it. The Gaussian calculation omits the quartic interaction and mediator backreaction without establishing their effects as negligible; its canonical interaction strength $u_C/(\mathcal N_Qa^2)$ remains unselected. Perturbative excitations of the canonical field are scalar bosons. Interacting production, localized capture, fermionic matter, physical quantum numbers, normalization and empirical matching require additional supported mechanisms.

The accepted source and specification identities, all 31 raw trajectories and the independent verification are in `runs/20260906_matter_formation_hyperbolic_parent/`. The stationary fields are fixed inputs; the binding and spatial-stability verdicts retain their stated scope.

## 9. Classical parent vacuum and neutral stationary localization

The status of the exterior vacuum is a separate requirement for interpreting carrier excitations as physical matter. The zero-signed-charge sector has an exact classical potential condition, derived in `foundations/particle-stationary-action-closure.md` §8.9. With $z=f^2$, $n=|\chi|^2$ and $B=e_C+1/(4a)$,

$$
V_a(z,n)=\frac{u_\rho}{4}(z-1)^2+
[B-h_C(1-z)]n+\frac{u_C}{2}n^2.
$$

This potential is nonnegative for all $z,n\ge0$ exactly when

$$
\boxed{h_C-e_C-\frac1{4a}\le\sqrt{\frac{u_\rho u_C}{2}}.}
$$

At the Mapped coefficient point, the classical vacuum boundary and the separate depleted-background mass crossing are

$$
a_{\rm vac}=\frac1{4(h_C-e_C-\sqrt{u_\rho u_C/2})}
=0.3142233129944425,
\qquad
a_{\rm dep}=\frac1{4(h_C-e_C)}
=0.113131075190101.
$$

The three coefficients used in the Gaussian pair correspondence lie below both boundaries. A negative instantaneous carrier mass squared at an externally held depleted mediator can occur while the full coupled potential remains nonnegative. Above $a_{\rm vac}$, a homogeneous carrier-populated phase has lower classical energy than the exterior vacuum; the exterior remains a local potential minimum. This supplies no nucleation rate, formation history or quantum-vacuum conclusion.

### 9.1 Independent numerical checks

The frozen specification is `computations/matter-formation-parent-vacuum-prereg.md`. The primary program uses polynomial identities and closed Gaussian integrals. The independent verifier minimizes the unreduced two-variable potential from all 25 starts at each of ten coefficients and integrates the original radial energy densities. All 250 minimizations report success; their largest projected-gradient norm is $3.9968\times10^{-15}$.

| Parent coefficient | Global canonical potential minimum |
|---|---:|
| $1/64$ | 0 |
| $1/32$ | 0 |
| $1/16$ | 0 |
| $1/8$ | 0 |
| $1/4$ | 0 |
| $0.9a_{\rm vac}$ | 0 |
| $a_{\rm vac}$ | 0 analytically; numerical value $-2.2204\times10^{-16}$ |
| $1.1a_{\rm vac}$ | −0.1049035183501719 |
| $1/2$ | −0.4617526056741839 |
| $1$ | −0.9204591247603631 |

Both receipts report **`PASS`**, with zero independent mismatches. The complete finite schedule contains 60 weighted complex charge-energy witnesses and 50 three-dimensional Gaussian dilation integrals. The largest independent discrepancies are:

| Quantity | Maximum discrepancy |
|---|---:|
| Scaled polynomial factorization residual | $7.6521\times10^{-16}$ |
| Scaled signed-charge residual | $4.4409\times10^{-16}$ |
| Scaled canonical/original Hamiltonian-shift residual | $3.5527\times10^{-15}$ |
| Scaled kinetic-bound residual | $2.6866\times10^{-14}$ |
| Absolute global-minimum difference | $2.2204\times10^{-16}$ |
| Scaled closed-integral versus independent-quadrature energy difference | $6.7472\times10^{-16}$ |
| Scaled direct versus spatial-dilation energy difference | $6.5600\times10^{-16}$ |

The canonical CRLF-to-LF source identities are:

- Primary: `8ef9b8d78163b12da265b61516bf456025e9f51e9809d90b7b7875f0dc72640e`.
- Independent verifier: `9efbcd5242324b235180e7eac90e4ad9e5f6579cf2a1f6b58f5422a202ae8f5a`.
- Preregistration: `0ee3ced90d43c41c96cd85aaff2627f84d40ec39b3217613ee5b70c2f0e9d7ef`.

The raw primary receipt SHA-256 is `509d590dd5e1db61c9455f676e6a4d9fd861b6411e83a83e4a89aec23b7e8015`. Both receipts, every optimizer endpoint and the independent quadrature error estimates are retained in `runs/20260906_matter_formation_parent_vacuum/`. The verifier explicitly checks reported values, complete row schedules, source identities, failure flags and row types. Both programs refuse existing receipts.

### 9.2 Consequence for neutral stationary matter

Zero signed Noether charge imposes a stronger restriction than gauge neutrality. The carrier is a gauge singlet even when its signed global charge is nonzero. For a single-frequency stationary carrier, $\mathcal Q_a=(1+2a\omega)Q_C$, so a nonzero profile with $\mathcal Q_a=0$ requires $\omega=-1/(2a)$ and is static in canonical variables.

In three dimensions, spatial dilation then gives $E(\lambda)=\lambda\mathcal T+\lambda^3\mathcal U$. A stationary state must satisfy $\mathcal T+3\mathcal U=0$. When $V_a\ge0$, the nonnegative terms exclude a nontrivial regular finite-energy solution. If a stationary solution exists where the potential can be negative, its dilation curvature is $E''(1)=-2\mathcal T<0$. The dilation preserves zero signed charge.

Thus the declared classical scalar parent cannot supply an energetically stable, regular, localized single-frequency zero-signed-charge stationary particle. The result is a conditional application of Derrick's scaling argument. It leaves charged stationary binding, spatially separated opposite charges, multi-frequency evolution, quantum bound states and additional gauge, scale or topological structures as distinct mechanisms requiring evidence. The finite Gaussian integration profiles check the energy functional and scaling law; they are not stationary solutions.

## 10. Radial energetic stability at fixed signed parent charge

The temporal energy needed to maintain a nonzero signed charge can stabilize a population-changing direction. The relevant constraint is the parent's $\mathcal Q$, while its spatial carrier population $N=\int c^2$ may vary. Minimizing over carrier velocities gives

$$
\mathscr E_{\mathcal Q}=E_{\rm sc}+\frac{(N-\mathcal Q)^2}{4aN},
\qquad
H_{\mathcal Q}=H_0+\frac{1+4a\omega_C}{2aN}gg^T,
\qquad g=\nabla N.
$$

Here $H_0$ is the unprojected amplitude Hessian of $E_{\rm sc}-\omega_CN$. The derivation in `foundations/particle-stationary-action-closure.md` §8.10 includes the velocity minimization, stationary signed-charge embedding, conditional charge-slope criterion and fixed-charge dilation energy. No physical temporal coefficient or charge normalization is selected.

### 10.1 Frozen schedule and independent operators

The calculation in `computations/matter-formation-charged-stability-prereg.md` uses eight qualified immutable fields: prepared populations 16 and 256, each at $(R,n)=(12,192),(12,384),(12,768),(24,768)$. Each field is embedded at $a=1/64,1/32,1/16$, giving 24 parent rows. No field is relaxed. All source residuals pass; the largest is $6.7560\times10^{-5}$ against $10^{-4}$.

The primary implementation assembles dense mass-weighted matrices and calculates the six lowest base and parent eigenpairs. The independent implementation assembles an interleaved symmetric banded operator, computes the complete base spectrum, solves the population response independently and brackets every parent eigenvalue using the rank-one inertia identity. All 144 eigenvalue brackets pass. Both receipts report numerical **`PASS`**, with zero failures.

| Numerical check | Largest measured discrepancy or residual | Frozen limit |
|---|---:|---:|
| Independent base-eigenvalue absolute difference | $1.0498\times10^{-11}$ | $10^{-7}\max(1,|\lambda|)$ |
| Eigenpair relative residual across both implementations | $3.6169\times10^{-11}$ | $10^{-8}$ |
| Eigenvector orthonormality error | $2.4425\times10^{-15}$ | $10^{-8}$ |
| Base response-solve relative residual | $8.4425\times10^{-12}$ | $10^{-8}$ |
| Shifted banded-solve relative residual | $1.3213\times10^{-11}$ | $10^{-8}$ |
| Scaled independent population-response difference | $4.8142\times10^{-12}$ | $10^{-8}$ |
| Scaled direct-versus-closed dilation-energy difference | $1.7607\times10^{-11}$ | $10^{-8}$ |

Every base operator has exactly one resolved negative eigenvalue and no unresolved zero. Its population response $S=g^TH_0^{-1}g$ is negative. The 24 factors $1+\gamma S$ range from $-234.68944$ to $-15.81224$, agreeing with the positive parent spectra under the checked one-negative-index hypothesis. This is a finite-grid response calculation; it supplies no continuum branch derivative.

### 10.2 Measured curvature and domain qualification

Every frozen embedding supports radial energetic stability on its own finite grid. The measured minimum eigenvalues are:

| Prepared $Q_C$ | Domain $R$ | Cells | $a=1/64$ | $a=1/32$ | $a=1/16$ |
|---:|---:|---:|---:|---:|---:|
| 16 | 12 | 192 | 0.9589907397 | 0.9577469155 | 0.9551534094 |
| 16 | 12 | 384 | 0.9580731065 | 0.9568219660 | 0.9542133831 |
| 16 | 12 | 768 | 0.9578429000 | 0.9565899198 | 0.9539775461 |
| 16 | 24 | 768 | 0.9317264859 | 0.9312207337 | 0.9301194666 |
| 256 | 12 | 192 | 1.9565876296 | 1.8838741027 | 1.7309992899 |
| 256 | 12 | 384 | 1.9573637360 | 1.8846467876 | 1.7317432938 |
| 256 | 12 | 768 | 1.9575574044 | 1.8848396143 | 1.7319289729 |
| 256 | 24 | 768 | 1.9573543271 | 1.8846429818 | 1.7317426072 |

All minima exceed the row's stationary-error threshold $\eta$, whose maximum is $6.7560\times10^{-4}$. The finite-grid aggregate is

$$
\boxed{\text{SUPPORTS—finite-grid radial fixed-charge energetic stability}.}
$$

All six resolution comparisons pass. All three population-256 domain comparisons also pass, with minimum-eigenvalue differences from $6.8662\times10^{-7}$ to $9.4089\times10^{-6}$. The population-16 domain comparisons fail:

| Parent coefficient | Same-spacing $R=12$ versus $24$ difference | Frozen tolerance |
|---|---:|---:|
| $1/64$ | 0.0263466206 | 0.0095807311 |
| $1/32$ | 0.0256012323 | 0.0095682197 |
| $1/16$ | 0.0240939164 | 0.0095421338 |

These domain comparisons use 384 cells at $R=12$ and 768 cells at $R=24$. Nine of twelve frozen comparisons pass, so the separate aggregate remains

$$
\boxed{\text{INCONCLUSIVE—radial domain/resolution qualification}.}
$$

The population-256 subset meets the measured radial comparison criteria. The radial calculation alone supplies no angular or phase qualification; those sectors are evaluated separately in §11. Real-time persistence, nonlinear orbital stability, infinite-volume coercivity and localized creation remain open. The fixed-population spatial verdict in §7 remains `INCONCLUSIVE—constrained smooth-branch spatial stability`. Finite-grid radial support does not select a physical particle size, charge, mass or statistics.

### 10.3 Accepted evidence identities

The canonical CRLF-to-LF SHA-256 identities are:

- Primary: `383cc899ee3638762d63050f3c34bd4a8a688cfa81a3fe864f09e40e7b8f57ec`.
- Independent verifier: `be1d8837d9dc85125020a6eb7ed53b2f9faa7a7d4f37252f5ee27043d7d09e80`.
- Preregistration: `97f8e8db7bb7912832920a776189fc5adbc3db55d4465fc0826037b94b43a874`.

The raw primary receipt SHA-256 is `540bf259441b42ac476189dcd8593ae3b57a4fe25bb8fe17c846d5465068b0bc`. The primary receipt, eight hash-bound spectral arrays, complete independent base spectra, 288 shifted-solve diagnostics, all dilation energies and independent verification are retained in `runs/20260906_matter_formation_charged_stability/`. Existing own receipts and primary spectral artifacts cannot be overwritten by either reproduction program.

## 11. Scalar-parent angular and phase qualification

The four population-256 profiles support the measured remaining scalar spatial sectors on each finite grid, while their domain comparison leaves the combined result inconclusive. The calculation selects these immutable fields because all twelve inherited charged radial embeddings and all six corresponding radial comparisons qualify. It does not repeat the population-16 calculation or alter its verdict.

### 11.1 Conditional continuum identities and frozen operators

The fixed-signed-charge Hamiltonian supplies the angular amplitude and carrier-phase operators without a new coefficient. The population penalty contributes a rank-one correction only to the real radial amplitude. The other sectors retain the spatial multiplier $\omega_C=\omega+a\omega^2$, including its temporal-inertia contribution. The general carrier stiffness is $k_{Cx}D_\ell$.

For an exact nodeless stationary carrier, the phase operator has a nonnegative quadratic form and a global-phase zero direction. An exact positive radial profile with strictly increasing mediator amplitude and strictly decreasing carrier amplitude also has a cooperative nonnegative dipole form, with translation as its possible kernel. Positive angular ordering extends this statement to higher angular degrees. These are conditional identities with regularity and vanishing-boundary-term assumptions (`foundations/particle-stationary-action-closure.md` §8.11).

The frozen numerical specification is `computations/matter-formation-parent-spatial-prereg.md`. It uses prepared $Q_C=256$ at $(R,n)=(12,192),(12,384),(12,768),(24,768)$, without relaxation or interpolation. Each source passes the first-variation and population checks. The largest source residual is $2.5246\times10^{-5}$ against $10^{-4}$; the largest relative population error is $3.3307\times10^{-16}$ against $10^{-10}$. Every source uses $\eta=5\times10^{-4}$.

Six lowest algebraic eigenpairs are computed for each of the dipole and quadrupole amplitude operators $H_1,H_2$ and phase operators $L_0,L_1$. The primary uses dense mass-weighted matrices. The independent verifier constructs face conductances directly, uses an interleaved symmetric banded amplitude matrix and tridiagonal phase matrix, and checks the primary vectors against these independent operators. The translation and phase candidates are identified by maximum absolute overlap among the six eigenvectors; their signs are checked before excluding either candidate from a nonsymmetry gap.

Both receipts have numerical **`PASS`** and zero failures:

| Numerical check | Largest measured value | Frozen limit |
|---|---:|---:|
| Primary versus independent eigenvalue difference, 96 values | $7.6343\times10^{-12}$ | $10^{-7}\max(1,|\lambda|)$ |
| Primary normalized eigenpair residual | $2.5807\times10^{-11}$ | $10^{-8}$ |
| Independent normalized eigenpair residual | $2.4569\times10^{-11}$ | $10^{-8}$ |
| Primary-vector residual against the independent operator | $2.5922\times10^{-11}$ | $10^{-8}$ |
| Largest orthonormality error across both constructions | $5.1159\times10^{-15}$ | $10^{-8}$ |

### 11.2 Symmetry candidates and measured spatial gaps

Every grid passes its angular and phase energetic criteria. The table lists the identified translation eigenvalue, the first amplitude eigenvalue excluding that candidate, the quadrupole minimum, the first phase eigenvalue excluding the global-phase candidate, and the dipole-phase minimum:

| Domain $R$ | Cells | Translation eigenvalue | $H_1$ nonsymmetry gap | $\min H_2$ | $L_0$ nonsymmetry gap | $\min L_1$ |
|---:|---:|---:|---:|---:|---:|---:|
| 12 | 192 | 0.0001089316 | 2.5042184055 | 0.3210196012 | 1.4267000631 | 0.3693591472 |
| 12 | 384 | 0.0000272588 | 2.5041595205 | 0.3209348770 | 1.4271586155 | 0.3693626985 |
| 12 | 768 | 0.0000067325 | 2.5041448207 | 0.3209135875 | 1.4272735335 | 0.3693635299 |
| 24 | 768 | 0.0000272397 | 2.3799505428 | 0.3209348571 | 1.4271584571 | 0.3693626916 |

The minimum translation overlap is $0.9999994547$. Every phase overlap exceeds $0.99999999999998$, and the largest absolute phase eigenvalue is $8.7881\times10^{-13}$. All four nonsymmetry metrics exceed $\eta$ on every grid; no lowest eigenvalue is below $-\eta$.

The symmetry-vector diagnostics distinguish close overlap from an exact null vector. The sampled translation-vector operator residual ranges from $0.00353488$ to $0.01037067$ and is not monotone under refinement. These are descriptive residuals, distinct from the eigenpair residuals and frozen symmetry-eigenvalue tests. Sampled mediator differences include small negative values; the largest-box carrier has zero-valued samples and small positive differences. These arrays do not establish the exact positivity and strict monotonicity assumptions of the continuum identities.

The sector verdict is therefore

$$
\boxed{\text{SUPPORTS—finite-grid scalar angular and phase energetic qualification}.}
$$

### 11.3 Domain qualification and parent interpretation

The frozen domain comparison prevents a finite-grid positive spectrum from being presented as a domain-converged stability result. Resolution compares $R=12$ at 384 and 768 cells; domain size compares $(R,n)=(12,384)$ and $(24,768)$ at the same spacing. Each tolerance is the greater of one percent of the larger absolute metric and the two source thresholds.

| Metric | Resolution difference | Resolution tolerance | Domain difference | Domain tolerance | Resolution / domain |
|---|---:|---:|---:|---:|---|
| $H_1$ nonsymmetry gap | $1.4700\times10^{-5}$ | 0.0250415952 | 0.1242089777 | 0.0250415952 | PASS / FAIL |
| $\min H_2$ | $2.1290\times10^{-5}$ | 0.0032093488 | $1.9850\times10^{-8}$ | 0.0032093488 | PASS / PASS |
| $L_0$ nonsymmetry gap | $1.1492\times10^{-4}$ | 0.0142727353 | $1.5848\times10^{-7}$ | 0.0142715862 | PASS / PASS |
| $\min L_1$ | $8.3142\times10^{-7}$ | 0.0036936353 | $6.9331\times10^{-9}$ | 0.0036936270 | PASS / PASS |

Seven of eight comparisons pass. The dipole nonsymmetry gap changes from $2.5041595205$ to $2.3799505428$, exceeding its domain tolerance. Both values are positive and above their respective exterior carrier spatial gaps, approximately $2.34418$. The comparison does not identify a negative mode or establish the infinite-volume spectral character of this eigenvector. Its frozen domain result remains failed.

The inherited radial qualification is satisfied, but the spatial comparison is not. Both implementations therefore give

$$
\boxed{\text{INCONCLUSIVE—scalar spatial domain/resolution qualification}}
$$

and

$$
\boxed{\text{INCONCLUSIVE—finite-grid scalar parent spatial energetic qualification}.}
$$

All three temporal witnesses $a=1/64,1/32,1/16$ lie below $a_{\rm dep}=0.1131310752$ and $a_{\rm vac}=0.3142233130$. Across the twelve embeddings, the canonical exterior frequency gap squared $(e_C-\omega_C)/a$ ranges from $18.75324548$ to $75.01684870$; the depleted-mediator carrier mass squared ranges from $28.64278278$ to $882.57113111$. These positive conditional quantities select no physical temporal coefficient or action normalization.

The measured result concerns the scale-independent scalar restriction. Continuum coercivity, nonlinear orbital stability, real-time formation, gauge and scale sectors, quantum backreaction and particle identity remain separate requirements. Neither the population-16 radial-domain result nor its fixed-population spatial result is changed by this selected population-256 calculation.

### 11.4 Accepted identities and failure control

The canonical CRLF-to-LF SHA-256 identities are:

- Primary: `3593f57f660e43b59cb13d0e448ce2bd293f2c6bc3cf1e72dcb606681189a27a`.
- Independent verifier: `6ed3b31684e65d73c828cb8854075c8d0f7b7f1d14a4a8f7669f938aead4ba98`.
- Preregistration: `df72e1873a25a0787d19492e09eba2433b0c9786398ee1b9f56803fd1e44d2a1`.

The raw primary receipt SHA-256 is `9445ff33b33b664bf15e09b499bb185f18bfeb9f8a9393c388afef7c7affa79c`; the independent receipt SHA-256 is `2994e44ee2566ecc4e7ce660dc5d0510a088b694e0224086792eda2854f148dd`. Both receipts, four hash-bound spectral arrays, all symmetry diagnostics and the eight comparisons are retained in `runs/20260906_matter_formation_parent_spatial/`. The independent receipt binds the primary raw hash and verifies the accepted charged-radial receipt chain.

The registered missing-source control invokes both actual programs against an empty source directory. Both return exit code 1 and preserve failed JSON receipts with zero eigenvalue rows. The primary records all four missing-source errors and the incomplete comparison schedule; the verifier rejects the failed input and retains its errors without eigensolves. These control receipts reside under `control_missing_sources/` and carry no scientific stability conclusion. The canonical receipts and source files remain unchanged.

## 12. Physical normalization and microscopic identity

The scalar model has a **Derived conditional** family of physical unit assignments with the same imposed vacuum mass, propagation speed and internal generator unit. The free temporal coefficient and its invariant frequency ratios distinguish these models. The registered numerical witnesses are consistency checks on that algebraic construction. The core-cell exclusion and chiral-scalar obstruction are also conditional algebraic results with independently reconstructed numerical witnesses; they supply no interacting formation trajectory or measured particle identity.

### 12.1 Fixed inputs and independent reconstruction

The frozen specification is `computations/matter-formation-normalization-prereg.md`. It retains the dimensionless coefficients $u_\rho=4$, $u_C=1$, $k_{Cx}=1$, $e_C=0.75$ and the Mapped $h_C=2.9598260763447164$. The single input is the population-256 profile at $R=12,n=768$, raw SHA-256 `95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a`. Both implementations validate its accepted spatial receipt chain. Neither relaxes a field or recomputes a spatial eigenvalue.

The primary uses NumPy shell quadrature and four-component Weyl matrices. The independent verifier reconstructs population and energy by direct face and local-potential loops, and spinor bilinears by two-component contractions. Both receipts have `numerical_pass: true` and empty failures. They reproduce

$$
N=256,\qquad
\omega_C=-0.422077842309661,\qquad
E_{\rm sc}=-55.50990756715602,\qquad
T=78.81491551669352
$$

to the registered tolerance. The negative $E_{\rm sc}$ is the dimensionless static functional; its value alone is not a physical rest energy.

Both energy reconstructions use the homogeneous state $f=1$, $C=0$ at zero velocity as their common zero. The same static functional supplies
$H_{\rm original}=E_{\rm sc}+a\omega^2N$ and
$H_{\rm can}=E_{\rm sc}+[1/(2a)+\omega_C]N$, with
$\omega=\Omega-1/(2a)$. There is no independent offset fitted to either Hamiltonian.

The receipt field `original_frequency` is $\omega=(\sqrt{1+4a\omega_C}-1)/(2a)$, the branch solving $\omega+a\omega^2=\omega_C$ with positive $1+2a\omega$. The fixed profile supplies the common $\omega_C$; each selected $a$ therefore has its own $\omega$ and charge $\mathcal Q=N\sqrt{1+4a\omega_C}$.

### 12.2 One mass leaves a normalization family

The external target is $\mathscr E_*=0.511\ \mathrm{MeV}$, taken from the electron mass entry. It is imposed as the *vacuum canonical scalar mass* $\hbar M_a(1)/t_Q$. The common propagation speed is set to $c$, and the scalar's own $U(1)$ generator is assigned one unit by $\mathcal N_Q\mathcal Q=1$. This generator is distinct from electric charge. No electron spin, statistics or interaction is assumed.

The conditional identities in `foundations/particle-stationary-action-closure.md` §8.12 give

$$
\frac{\ell_Q}{\lambda_*}
=\sqrt{\frac{1/(2a)+2e_C}{k_{Cx}}},
\qquad
t_Q=\frac{\ell_Q}{c}\sqrt{\frac{k_{Cx}}{2a}},
\qquad
\mathcal N_Q=\frac1{\sqrt{1+4a\omega_C}\,N},
\qquad
\lambda_*=\frac{\hbar c}{\mathscr E_*}.
$$

All three preregistered witnesses satisfy the mass, speed, charge and Hamiltonian identities with normalized residuals below $10^{-10}$. These residuals check identities enforced by the construction. Define the implied mass energy and speed by
$m_{\rm imp}=\hbar M_a(1)/t_Q$ and
$v_{\rm imp}=(\ell_Q/t_Q)\sqrt{k_{Cx}/(2a)}$.
For the dimensionless energy checks, let
$A_H=H_{\rm can}-H_{\rm original}$,
$B_H=\mathcal Q/(2a)$,
$A_\mu=H_{\rm can}-\Omega\mathcal Q$ and
$B_\mu=E_{\rm sc}-\omega_CN$.
The denominators fixed in the preregistration and used by both programs are:

| Receipt field | Absolute numerator | Denominator |
|---|---|---|
| `mass_residual` | $\lvert m_{\rm imp}-\mathscr E_*\rvert$ | $\mathscr E_*$ |
| `speed_residual` | $\lvert v_{\rm imp}-c\rvert$ | $c$ |
| `charge_residual` | $\lvert\mathcal N_Q\mathcal Q-1\rvert$ | $1$ |
| `energy_shift_residual` | $\lvert A_H-B_H\rvert$ | $\max(1,\lvert H_{\rm can}\rvert,\lvert H_{\rm original}\rvert,\lvert\mathcal Q/(2a)\rvert)$ |
| `chemical_energy_residual` | $\lvert A_\mu-B_\mu\rvert$ | $\max(1,\lvert H_{\rm can}\rvert,\lvert\Omega\mathcal Q\rvert,\lvert E_{\rm sc}\rvert,\lvert\omega_CN\rvert)$ |

The unit floor in the final two rows belongs to the dimensionless energy convention. The receipt uses `exterior_mass` for $M_a(1)$, `canonical_frequency` for $\Omega$, `charge` for $\mathcal Q$, and the source summary's `N`, `omega_C` and `static_energy` for $N$, $\omega_C$ and $E_{\rm sc}$. Direct reconstruction of all 30 stored residuals agrees exactly with the retained values; their maximum is $2.220446049250313\times10^{-16}$.

| $a$ | $\ell_Q$ (m) | $t_Q$ (s) | $\ell_{\rm tail}$ (m) | $E_QH_{\rm can}/\mathscr E_*$ |
|---|---:|---:|---:|---:|
| $1/64$ | $2.2350537582\times10^{-12}$ | $4.2173753918\times10^{-20}$ | $1.4598046666\times10^{-12}$ | 0.9707310816 |
| $1/32$ | $1.6154167965\times10^{-12}$ | $2.1553801684\times10^{-20}$ | $1.0550945226\times10^{-12}$ | 0.9432196612 |
| $1/16$ | $1.1902203530\times10^{-12}$ | $1.1229273589\times10^{-20}$ | $7.7738140264\times10^{-13}$ | 0.8927907492 |

Strict monotonicity, $d(\ell_Q^2)/da=-\lambda_*^2/(2k_{Cx}a^2)<0$, proves the nonuniqueness for distinct admissible $a$. The numerical consistency checks return the frozen verdict

$$
\boxed{\text{SUPPORTS—conditional one-mass normalization nonuniqueness}.}
$$

The verdict labels the registered numerical consistency check. The
monotonicity implication is Derived conditional, while the selected mass,
one-generator convention and core-cell assignment retain their Mapped
Fit-Status Ledger entries. These statuses describe different objects.

The last column is a conditional soliton-energy conversion. The mass calibration fixes a vacuum frequency, while the soliton energy includes its spatial and temporal energy. The ratios are outputs with no particle-matching threshold. A one-unit classical generator normalization does not establish a one-fermion quantum state or justify a semiclassical approximation.

The source-unit transformations in `foundations/particle-stationary-action-closure.md` (PA36)–(PA37) preserve $\ell_Q$, $a$, $\mathcal N_Q$, $u_C/(\mathcal N_Qa^2)$ and $\Omega^2/M_a^2(1)$. The displayed family changes invariant quantities; it does not merely enumerate redundant choices of $g_Q$, $v_Q$, $\mu_{x,\mathfrak s}$ or $\lambda_H$. The tail comparison uses $a>0$, $k_{Cx}>0$, $e_C>\omega_C$ and $1+4a\omega_C>0$, all satisfied by the registered witnesses.

### 12.3 The selected scalar core-cell assignment fails

An additional identification of the scale $\ell_Q$ with the target Compton wavelength requires $a=[2(k_{Cx}-2e_C)]^{-1}$. Its denominator is $-1$ at the fixed coefficients, so no positive root exists. The external target gives $\lambda_*=3.8615847424\times10^{-13}\ \mathrm m$ and cascade coordinate $107.0793429067$ under the declared Planck convention.

The global-vacuum inequality permits $a\le a_{\rm vac}=0.3142233130$. Since $\ell_Q(a)$ decreases with $a$, the full allowed interval has

$$
\ell_Q\ge6.7893919382\times10^{-13}\ \mathrm m,
\qquad
n_{\ell_Q}\ge108.2519735475.
$$

The mapped electron cell $[107,108]$ spans $[3.7169257276,6.0141121609]\times10^{-13}\ \mathrm m$. Its upper endpoint is smaller than this minimum. Both implementations therefore give

$$
\boxed{\text{CONTRADICTS—selected scalar electron-core assignment}.}
$$

The excluded assignment concerns $\ell_Q$ at these selected coefficients. The carrier decay length, profile radius and Compton wavelength are separately defined observables. The measured electron mass and its descriptive cascade coordinate retain their external and Mapped provenance.

### 12.4 Changing units preserves the failed spatial comparison

The failed domain comparison in §11 has difference $0.12420897766027794$ and tolerance $0.02504159520461554$. Their ratio is $4.960106440718456$. Multiplying both spectral endpoints and the tolerance by $10^{-12}$, $1$ or $10^{12}$ preserves this ratio to floating-point precision and leaves all three comparisons failed. The inherited verdict remains exactly `INCONCLUSIVE—finite-grid scalar parent spatial energetic qualification`. A unit assignment changes no dimensionless stability evidence.

### 12.5 Chiral scalars cannot supply the proposed positive densities

The obstruction follows from the adjoint identity, independently of a mass scale. In the Weyl convention $\psi=(L,R)$,

$$
B_R=\bar\psi P_R\psi=L^\dagger R,
\qquad
B_L=\bar\psi P_L\psi=R^\dagger L=B_R^*.
$$

The adjunction residual is zero. Simultaneous real nonnegative values imply equality; imposing $B_R=\varphi B_L$ then forces both to vanish. The five registered spinors include the explicit pairs $(i,-i)$, $(-1,-1)$, $(1,1)$ and $(0,0)$. A spinor with positive frame-density ratio $n_R/n_L=\varphi$ instead gives $B_R=B_L=\sqrt\varphi$. The positive frame densities $R^\dagger R,L^\dagger L$ are different observables.

Even after factoring out a hypothetical common mass bridge, the displayed ordinary-square interaction is generally complex. At the registered complex witness and real targets $A=\varphi,B=1$,

$$
AB_R+BB_L=0.6180339887498949\,i,
\qquad
\frac{(B_R-A)^2+(B_L-B)^2}{2}
=0.8090169943749475-0.6180339887498949\,i.
$$

These finite-dimensional witnesses confirm the exact conjugacy and reality obstructions:

- `CONTRADICTS—chiral-scalar nonnegative-density identification`;
- `CONTRADICTS—displayed chiral projection interaction as a physical real action`.

They are algebraic checks of the specified map and interaction, with no fermion-production simulation. The conditional sector-scale arithmetic survives, but it selects no admissible operator or transport rate (`foundations/sector-coupling-derivation.md` §1). A local scalar normalization also preserves its $2\pi$ rotation phase $+1$, whereas a Dirac spinor has phase $-1$. Fermionic topological solitons would require a separate configuration space and quantization absent from this scalar restriction.

Other nonnegative spinor observables remain available. The existing `two-fluid/cassi_dirac_bridge.py` evaluates $\|u-v\|^2,\|u+v\|^2$ for its upper/lower two-component blocks, as well as Pauli spin and current bilinears. The two nonnegative forms sum to $2\psi^\dagger\psi$ and are separate from the tested $B_R,B_L$. Their chiral-current interpretation and dynamical boundary are the subject of the distinct frozen calculation in §13 (`foundations/sector-coupling-derivation.md` §§1.5–1.6). Physical energy-density normalization and fine-structure interpretation remain unestablished.

### 12.6 Accepted identities and failed-input control

The canonical CRLF-to-LF SHA-256 identities are:

- Primary: `a27972cb109215ceea48a938659045e1f901cd30b992830dfbbfef42744702f0`.
- Independent verifier: `57242571fb9c5e48f58054dbcbf02c299ac37bd814d0468e16fd35002fbf1e5b`.
- Preregistration: `35dcaac325932c32f486bace0f8ad71a232dc4f87fb1aa85893fa0cb81dac732`.

The raw primary receipt SHA-256 is `3c1fba6f2ea5cedf3d774a2dfcf33d7691add503dd56588ae41f1afe315bca0b`; the independent receipt SHA-256 is `81962ce27615f5da0603cac665b75138ca9fb19bff689d7d58d3443b757880eb`. They are retained in `runs/20260906_matter_formation_normalization/`. The independent receipt binds the primary raw hash and recomputes every numerical payload field.

The tested expressions and target choices are transcribed explicitly in the frozen preregistration §§3–4. Its hash binds that algebra together with the two executable implementations. The receipt does not hash the mutable explanatory source documents; their citations locate the derivation and interpretation, while the preregistration supplies the tested expressions.

The registered empty-source control invokes both actual programs. Both exit 1 and preserve their failed receipts with empty source summaries, unit families, core assignments, rescaling results and spinor results. The primary reports the missing field; the verifier rejects the failed primary input. All control verdicts are bare `INCONCLUSIVE` and carry no scientific conclusion.

## 13. Positive spinor observables and the conversion boundary

### 13.1 Comparison convention and independent methods

The positive component map admits an exact current interpretation, with a separately declared normalization for comparison to the canonical density law. In the Dirac representation write $\psi_D=(u,v)$ and transform to $L=(u-v)/\sqrt2$, $R=(u+v)/\sqrt2$. The helper returns

$$
Y_{\rm bridge}=2L^\dagger L,\qquad I_{\rm bridge}=2R^\dagger R.
$$

The witnesses use $E_Y=L^\dagger L$, $E_I=R^\dagger R$, $z=L^\dagger R$ and natural units $\hbar=c=1$. This is a bookkeeping convention for classical complex amplitudes. It supplies no physical conversion from spinor number density to energy density and no quantum particle/antiparticle prescription.

The frozen protocol is `computations/matter-formation-spinor-closure-prereg.md`. The primary evaluates four-component matrix identities and direct stationary linear systems. The independent implementation uses two-component evolution, explicit positive-energy spinors and scalar stationary equations; it imports no primary routines. The schedule contains eight phase-sensitive states, five positive-energy states, three frozen-rate stationary states and six self-consistent gated stationary states. Every mass frequency, density and rate is a selected numerical witness input.

### 13.2 Relative coherence prevents closed two-population dynamics

The Dirac mass transfers chiral population according to the phase of the cross-bilinear. With selected mass frequency $\mu$,

$$
\boxed{
\partial_tE_Y+\nabla\cdot\mathbf j_Y=2\mu\operatorname{Im}z,\qquad
\partial_tE_I+\nabla\cdot\mathbf j_I=-2\mu\operatorname{Im}z,}
$$

where $\mathbf j_Y=-L^\dagger\boldsymbol\sigma L$ and $\mathbf j_I=R^\dagger\boldsymbol\sigma R$. The phase witnesses have spatially constant bilinears, hence zero current divergence. The pair $L=\sqrt p(1,0)$, $R=\pm i\sqrt{1-p}(1,0)$ has identical populations and currents but opposite Dirac sources. At $p=\varphi^{-1}$ and $\mu=1$, the measured sources are $\dot E_Y=\pm0.9717365435132914$ while the canonical imbalance vanishes.

The positive-energy restriction also supplies a discrepancy without the unrestricted phase preparation. All five free eigenspinors have stationary densities. At rest, $E_Y=E_I=1/2$, whereas the selected canonical law with $\lambda=0.02$ gives $q=0.6768384136$ and

$$
(\dot E_Y,\dot E_I)_{\rm can}
=(+0.00199724844245,-0.00199724844245).
$$

The general projector argument in `foundations/sector-coupling-derivation.md` §1.5 explains the missing state information. For a fixed Hermitian Hamiltonian, a projected derivative depending only on two complementary populations for every density matrix must vanish. A nonzero autonomous reduced conversion therefore requires extra dynamical state, a restricted preparation or a controlled open-system reduction.

### 13.3 The massive minimal lift changes the stationary ratio

The canonical two-jump dissipator reproduces its declared density equations as a conversion subflow. A homogeneous Dirac mass adds the off-diagonal Hamiltonian $H=\mu\sigma_x$ in the chiral basis. For fixed trace $\rho$, define $\delta=E_Y-E_I$, $s=1+\varphi$ and $\delta_*=(\varphi-1)\rho/s$. At frozen positive rate $\kappa$, the combined stationary equations give

$$
\boxed{
\delta_{\rm st}=\frac{\delta_*}{1+8\mu^2/(s^2\kappa^2)},\qquad
z_{\rm st}=-\frac{2i\mu\delta_{\rm st}}{s\kappa}.}
$$

The primary solves the stationary matrix equation directly. The independent program evaluates this formula and, for $\kappa=\lambda(1-q)$, solves the scalar self-consistency equation. The latter has one root between zero and $\delta_*$ for $\mu>0$. The registered massless controls recover $\varphi$; every massive row has a ratio strictly between one and $\varphi$.

| Rate prescription | $\rho$ | $\mu$ | $E_Y/E_I$ | $\delta_{\rm st}/\delta_*$ |
|---|---:|---:|---:|---:|
| Frozen $\kappa=0.02$ | 1 | 0 | 1.618033989 | 1 |
| Frozen $\kappa=0.02$ | 1 | 0.01 | 1.447213595 | 0.774115996 |
| Frozen $\kappa=0.02$ | 1 | 0.1 | 1.015767540 | 0.033134958 |
| Gated, $\lambda=0.02$ | 1 | 0 | 1.618033989 | 1 |
| Gated, $\lambda=0.02$ | 1 | 0.01 | 1.120476214 | 0.240674914 |
| Gated, $\lambda=0.02$ | 1 | 0.1 | 1.001681928 | 0.003559386 |
| Gated, $\lambda=0.02$ | 4 | 0 | 1.618033989 | 1 |
| Gated, $\lambda=0.02$ | 4 | 0.01 | 1.016230776 | 0.034100596 |
| Gated, $\lambda=0.02$ | 4 | 0.1 | 1.000183731 | 0.000389112 |

All nine stationary fibres are positive; their smallest measured eigenvalue is $0.3819660112501051$. These are stationary identities and finite-dimensional witnesses. The combined state-dependent Hamiltonian/dissipator flow has no all-time stability result in this calculation.

### 13.4 Positive-energy leakage has a separate physical meaning

The same chiral conversion jumps fail to preserve the positive-energy one-particle subspace. For a normalized positive-energy rest state $\psi_+$, the negative-energy projector gives

$$
\boxed{
\ell_-=\sum_a\|P_-J_a\psi_+\|^2
=\frac{1+\varphi}{4}\kappa>0.}
$$

The primary obtains $\ell_-$ from the full dissipator trace; the verifier sums transition amplitudes. At the selected rest-state gate, $\kappa=0.00646323172772$ and $\ell_-=0.00423024008509$. This diagnostic is a transition between amplitude subspaces. A physical interpretation requires a Fock-space state, occupations, Pauli blocking, an energy source and charge conservation. The diagnostic itself supplies no pair-production rate.

### 13.5 Accepted receipts and scoped verdicts

The accepted primary and independent receipts are in `runs/20260906_matter_formation_spinor_closure_implementation_recovery/`. Both processes exit 0, both receipts have `numerical_pass: true` and empty failures, and all 520 recursive comparisons pass. The largest independent scalar difference is $7.08\times10^{-16}$ and the largest primary identity residual is $2.22\times10^{-16}$. The raw receipt SHA-256 values are:

- Primary: `2fe4e3d8783c3efaf8f9dcc91cb0491b528a0a35fa7f454d787b3d63939902e9`.
- Independent: `34cb48325e86d904093c86ba7e00c311021bfd0f32e0b625d488065cc91fdf5c`.

The independent receipt binds the primary raw hash. Both bind the canonical source identities of the two programs, scientific preregistration and two bridge files. The scientific protocol's canonical SHA-256 is `5dbf22bd9f3c316f0b5b05a8945310c11b57a24fc77684efa0dd4f8a3ec8302d`.

The recovery record `computations/matter-formation-spinor-closure-implementation-recovery.md` identifies the preserved primary attempt, its source revision and an independent-process name-resolution defect. The scientific definitions and decision rules are unchanged, and the two primary scientific payloads are exactly equal. The two registered missing-input controls both exit 1 with empty scientific payloads. The final bridge source also passes its CPU initialization smoke at grid size four; that execution supplies no full-grid propagation or physical validation.

The exact scientific verdicts are:

- `SUPPORTS—nonnegative chiral-current interpretation of the component map`.
- `CONTRADICTS—closed Dirac realization of canonical two-density conversion`.
- `CONTRADICTS—golden population fixed point for the specified massive Dirac and minimal conversion lift`.
- `CONTRADICTS—positive-energy invariance of the specified chiral conversion channel`.

These conclusions constrain the stated observable map, free Dirac dynamics and minimal jump construction. They leave alternative physical interactions and controlled coarse-graining open. Full matter formation still requires a microscopic production law and its energy/charge ledgers, physical normalization, quantum-state and particle identities, interacting backreaction, localized formation and continuum temporal stability.

## 14. Reproduction and retained boundary

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
python computations/matter_formation_hyperbolic_parent.py
python computations/verify_matter_formation_hyperbolic_parent.py
python computations/matter_formation_parent_vacuum.py
python computations/verify_matter_formation_parent_vacuum.py
python computations/matter_formation_charged_stability.py
python computations/verify_matter_formation_charged_stability.py
python computations/matter_formation_parent_spatial.py
python computations/verify_matter_formation_parent_spatial.py
python computations/matter_formation_normalization.py
python computations/verify_matter_formation_normalization.py
python computations/matter_formation_spinor_closure.py --output-dir runs/20260906_matter_formation_spinor_closure_implementation_recovery
python computations/verify_matter_formation_spinor_closure.py --input-dir runs/20260906_matter_formation_spinor_closure_implementation_recovery --output-dir runs/20260906_matter_formation_spinor_closure_implementation_recovery
```

The lattice diagnostic and algebraic witness are in `runs/20260906_matter_formation/`. The 27 radial endpoint arrays, primary results, independent verification and two collocation arrays are in `runs/20260906_matter_formation_radial/`. The charge and coefficient schedule is frozen; changing an output directory does not authorize a new physical scan. The primary and independent programs preserve first-execution receipts.

The remaining physical requirements are a selected microscopic production action and quantum state, absolute normalization, interacting backreaction, particle identities and statistics, real-time localized formation and nonlinear stability, scale-dependent sectors, and empirical discrimination. The conditional hyperbolic parent supplies one explicitly normalized Gaussian correspondence, finite-grid radial fixed-charge support and selected population-256 angular/phase support. Its physical coefficient and action normalization remain open. The fixed-population spatial, signed-charge radial-domain and selected scalar-parent spatial calculations retain their distinct inconclusive aggregate verdicts.

## References

- `computations/matter-formation-continuum-prereg.md`—frozen continuum, lattice and creation calculations.
- `computations/matter-formation-stability-prereg.md`—frozen constrained spatial operators and decision tree.
- `computations/matter_formation_stability_execution.json`—accepted source identities and numerical correction scope.
- `computations/matter-formation-scaling-prereg.md`—post-campaign descriptive scope with frozen input identities.
- `computations/matter_formation_scaling.py`—population, radius, depletion, bulk and specific-partition summaries.
- `runs/20260906_matter_formation_scaling/scaling.json`—hash-bound descriptive results; parent verdicts unchanged.
- `computations/matter-formation-hyperbolic-parent-prereg.md`—frozen temporal-parent family, Gaussian schedule and correspondence decision.
- `computations/matter_formation_hyperbolic_parent.py`—primary oscillator trajectories, stationary embeddings and finite correspondence checks.
- `computations/verify_matter_formation_hyperbolic_parent.py`—independent raw-array reconstruction and source-work quadrature.
- `runs/20260906_matter_formation_hyperbolic_parent/results.json` and `runs/20260906_matter_formation_hyperbolic_parent/verification.json`—accepted primary and independent correspondence receipts.
- `computations/matter-formation-parent-vacuum-prereg.md`—frozen classical vacuum, charge-energy and dilation identities and numerical checks.
- `computations/matter_formation_parent_vacuum.py`—closed-form potential and Gaussian energy reconstruction.
- `computations/verify_matter_formation_parent_vacuum.py`—independent two-variable minimization and radial quadrature.
- `runs/20260906_matter_formation_parent_vacuum/results.json` and `runs/20260906_matter_formation_parent_vacuum/verification.json`—accepted classical parent-boundary receipts.
- `computations/matter-formation-charged-stability-prereg.md`—frozen signed-charge Hessian, response, inertia brackets and radial qualification schedule.
- `computations/matter_formation_charged_stability.py`—primary dense radial spectra and fixed-charge dilation energies.
- `computations/verify_matter_formation_charged_stability.py`—independent banded spectra, response solves and rank-one inertia brackets.
- `runs/20260906_matter_formation_charged_stability/results.json` and `runs/20260906_matter_formation_charged_stability/verification.json`—accepted finite-grid radial support and inconclusive aggregate radial-domain qualification.
- `computations/matter-formation-parent-spatial-prereg.md`—frozen scalar angular and phase operators, symmetry criteria and combined domain qualification.
- `computations/matter_formation_parent_spatial.py`—primary dense angular and phase spectra on the immutable population-256 subset.
- `computations/verify_matter_formation_parent_spatial.py`—independent banded and tridiagonal operators, primary-vector checks and radial inheritance verification.
- `runs/20260906_matter_formation_parent_spatial/results.json` and `runs/20260906_matter_formation_parent_spatial/verification.json`—accepted finite-grid sector support and inconclusive combined scalar-parent spatial qualification.
- `computations/matter-formation-normalization-prereg.md`—frozen mass-unit, core-cell and chiral-scalar identification checks.
- `computations/matter_formation_normalization.py`—primary scalar energy, normalization family and matrix-bilinear witnesses.
- `computations/verify_matter_formation_normalization.py`—independent face quadrature, unit reconstruction and two-component witnesses.
- `runs/20260906_matter_formation_normalization/results.json` and `runs/20260906_matter_formation_normalization/verification.json`—accepted conditional normalization nonuniqueness and scoped identification exclusions.
- `computations/matter-formation-spinor-closure-prereg.md`—frozen chiral-current, closed-conversion, massive stationary and positive-energy checks.
- `computations/matter-formation-spinor-closure-implementation-recovery.md`—source provenance, implementation defect, accepted receipts and controls.
- `computations/matter_formation_spinor_closure.py`—primary matrix identities and direct stationary linear solves.
- `computations/verify_matter_formation_spinor_closure.py`—independent component dynamics, scalar stationary equations and transition amplitudes.
- `foundations/sector-coupling-derivation.md` §1—dimensional, positivity, Hermiticity, chiral-current and dynamical-closure boundaries of the displayed Dirac identifications.
- `two-fluid/cassi_dirac_bridge.py`—component-quadratic, spin and current diagnostics; physical energy-density and fine-structure interpretations remain unestablished.
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
- [Das, Galante and Myers, *Smooth and fast versus instantaneous quenches in quantum field theory*](https://arxiv.org/abs/1505.05224)—standard scalar tanh-quench correspondence.
- [Camilo and Abdalla, *Momentum-space entanglement after smooth quenches*](https://doi.org/10.1140/epjc/s10052-019-6581-2)—general in/out-mass profile and exact Bogoliubov occupation.
- [Derrick, *Comments on Nonlinear Wave Equations as Models for Elementary Particles*](https://doi.org/10.1063/1.1704233)—finite-energy spatial-dilation restriction.
