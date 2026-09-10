# Turbulence—Spectra and Navier–Stokes Geometry

## Status: Index—September 2026

## Abstract

This directory contains the framework's turbulence sector: a conditional
two-fluid spectral analysis that separates the inherited Navier–Stokes
$-5/3$ kinetic-energy spectrum from optional Cassi closures. The source
$E_\varepsilon(k)$, scale-dependent gravity factor, and Qi-quality spectrum
$q(k)$ are conditional diagnostics; their optional closure forms are
Hypothesized, and each test must state its assumptions and retain its receipt.
The directory therefore records which ingredients are inherited, which are
optional model choices, and which claims remain unestablished.

The Navier–Stokes analyses develop exact critical-norm transfer identities,
heat-correction estimates, filtered stress dynamics, quantitative strain
departure and spectral-spread bounds on critical transfer. The spread has an
exact nonnegative viscous dissipation and centered nonlinear production;
finite cumulative positive production gives a Prodi–Serrin continuation
criterion. Exact source budgets extend the conditional estimate to smooth
forcing. Explicit initial-data and kinematic controls delimit scalar-energy
and local-geometric closure arguments. An exact globally smooth mixing family
excludes amplitude-linear cumulative bounds for critical transfer, spread
dissipation and positive spread production while admitting a finite nonlinear
critical-transfer bound of its own. A signed curl-spectrum refinement gives
a critical scalar-Beltrami residual criterion and closes radial positive
production conditionally on its time integral. A smooth positive-doublet
family has bounded first-order phase energy with unbounded enstrophy and
critical residual. Arbitrary-data production, global regularity and a Cassi
canonical-density-to-physical-momentum constitutive map remain open.

The separate fluid-feasibility study derives the conservative momentum flux
of a restricted first-order action branch and audits the actual density solver.
Its 246 checks include 28 native trajectories. The ordinary Navier–Stokes
controls pass; the native self-sourced force produces mean acceleration in a
periodic box. A physical closed-fluid completion remains open.

The selected capillary/thermal closure conserves momentum and total energy and
produces nonnegative entropy, with exact homogeneous canonical conversion. Its
395 checks cover 27 model trajectories and an independent
differentiation-matrix reference.

The radiative-material closure adds established LTE photon transfer to the
selected thermal fluid. Its M1 moments carry photon energy and momentum,
Kirchhoff emission closes thermal exchange, and a covariant source gives
equal-and-opposite material coupling. The comprehensive schedule passes 33 of
34 checks and rejects its fixed $\Delta t=0.01$ source-accuracy target. A
separate 9-check qualification supports $\Delta t=0.001$ source subcycling.
Physical temperature, density, opacity, ionization and electromagnetic current
maps remain open.

The compressible extension evolves mass, momentum and total energy with a
multilevel EOS and shock jump conditions. Finite ionization and excitation
networks provide line and continuum coefficients from evaluated atomic data.
Gravitational contraction, accretion and nuclear mass defect enter one
stellar luminosity ledger. Discrete ordinates preserve distinct crossing
beams. Its fixed source-snapshotted schedule passes **70 of 70 checks**, and
the separate integrity qualification passes **25 of 25 checks** across state
recovery, invalid-input rejection, exchange cancellation, source ledgers and
scientific-prerequisite classification. Physical Cassi material
identification and a production solver remain open.

The phase-current reduction derives Mermin–Ho vorticity, full-doublet Hopf
helicity and a two-scale-band periodic Beltrami class. Its 227 checks support
exact scalar-diffusion/viscosity equivalence for that fixed-winding field and
contradict the equivalence for general phase potentials. A separate 84-check
follow-up proves that bounded first-order positive-doublet energy does not
control enstrophy or the critical scalar-Beltrami residual. Microscopic
material transport, whole-field dynamical concentration control,
arbitrary-flow closure and global regularity remain open.

## 1. Document index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `turbulence/kolmogorov-from-phi.md` | Turbulence spectra from the two-fluid PDE | Derived conditional / Hypothesized closures |
| 2 | `turbulence/navier-stokes-transfer-boundary.md` | Critical transfer, cubic heat correction, and coercivity | Derived identities and obstructions / conditional small-data estimates |
| 3 | `turbulence/navier-stokes-stress-geometry.md` | Exact stress evolution and helical covariance conditions | Derived filtered identities / Hypothesized geometric closure |
| 4 | `turbulence/navier-stokes-depletion-dynamics.md` | Exact fine-scale transfer response, matter binding and exterior-memory comparison | Derived filtered identities and instantaneous obstructions / Conditional continuation estimate |
| 5 | `turbulence/navier-stokes-strain-departure.md` | Energy-coupled departure, radial and signed spectral spread, critical scalar-Beltrami residual, forced budgets and cumulative mixing obstruction | Derived conditional estimates and helical reduction / Static phase-energy coercivity contradicted / Open arbitrary-data critical work |
| 6 | `turbulence/cassi-fluid-feasibility.md` | Conservative action reduction, native-force obstruction, reacting capillary/thermal closure, phase-current summary and actual flow controls | Derived conditional mechanical, thermal, and phase-current identities / Tested solver, rotational and phase-coercivity boundaries / Open physical-fluid completion |
| 7 | `turbulence/cassi-fluid-phase-current-hydrodynamics.md` | Mermin–Ho rotation, helicity topology, two-band Beltrami flow, first-order coercivity and viscosity projection boundaries | Derived conditional current and topology identities / Tested rotational, memory and coercivity boundaries / Open microscopic viscosity and arbitrary-flow closure |
| 8 | `turbulence/cassi-radiative-material-closure.md` | LTE emission, multigroup M1 transport, conservative material coupling and CassiCosmos handoff | Derived conditional transfer, conservation and entropy identities / Tested kernels / Open Cassi material calibration |
| 9 | `turbulence/compressible-radiative-plasma-closure.md` | Compressible hydrodynamics, shocks, species and line kinetics, persistent stellar energy accounting and multi-angle crossing beams | Derived conditional / Tested reference controls and integrity qualification / Open Cassi material identification and production implementation |

## 2. Document summaries

### 2.1 Conditional Kolmogorov spectrum

The source document separates the inherited incompressible Navier–Stokes
kinetic-energy spectrum from the optional $q$-gated turbulence closure. Its
$k_\varphi$, $E_\varepsilon(k)$, gravity-factor, and $q(k)$ expressions are
conditional diagnostics: their rates, regimes, slopes, and amplitudes depend
on declared gate, flux, shell-averaging, and gravity-coupling assumptions.

### 2.2 Critical transfer and coercivity

`turbulence/navier-stokes-transfer-boundary.md` derives the signed all-scale
budget and a cubic heat correction. A phase-tuned family has unbounded
positive critical norm on one corrected-energy level set. The quartic
remainder has both signs; standard estimates close the small-data regime.

### 2.3 Filtered stress geometry

`turbulence/navier-stokes-stress-geometry.md` retains pressure correlations,
third moments, and viscous terms in the exact stress and strain equations.
It states the assumptions behind a helical covariance model and an
all-scale anisotropy estimate, with fixed controls for local isotropy,
helix deformation, surrounding strain, and scale dependence.

### 2.4 Fine-scale transfer and matter binding

`turbulence/navier-stokes-depletion-dynamics.md` isolates a kinetic-energy-controlled
coarse contribution while retaining full stress in the fine contribution.
The averaged fine transfer can increase from zero, and a fixed multiscale
control exceeds viscous-only absorption. A data-controlled cumulative
estimate remains open. The matter comparison distinguishes qualified
loaded-core redistribution from the positive constrained energy that
establishes conditional unwound binding.
A separate applicability note, outside the frozen matter comparison,
retains the exterior initial state and the assumptions of the Hypothesized
source action; it supplies no numerical bound on the nonlinear NS forcing.

### 2.5 Strain departure and critical spectral concentration

`turbulence/navier-stokes-strain-departure.md` couples kinetic energy and
strain enstrophy to obtain an earlier departure-or-breakdown deadline
than Miller's stated energy comparison. Known global regularity gives an
actual departure bound for axisymmetric, swirl-free data. An integrated
defect identity and a necessary excess-dose bound quantify departure.
Optimal scalar centering bounds critical remainder work, and energy
orthogonality bounds the complete nonlinear transfer by
$c_{\rm S}\sqrt{\eta\mathcal C}\,Y$. The exact spread dissipation
$$
\mathcal Q=2KG+2E^2-\mathcal C Y
$$
controls both $\eta E^2$ and $\eta\mathcal C Y$, and centers the nonlinear
production
$$
\mathscr P_{\mathcal V}=K\mathcal A-\mathcal C F.
$$
Finite $\int(\mathscr P_{\mathcal V})_+dt$ bounds the critical norm and its
dissipation, giving a Prodi–Serrin continuation criterion. The remaining
all-data target is a finite initial-$H^3$-controlled bound on that cumulative
positive production. A smooth periodic datum develops positive production
immediately from zero spread; a positive-moment scalar construction has
divergent critical norm despite positive departure. The separate departure
and recurrence schedules pass 71 and 134 checks respectively.

The forced budget and scaling controls have 215 passing checks in both the
frozen preregistered run and the separate post-run qualification. The
qualification covers all three source-work signs and the scaled Gaussian
maximum speed, with qualified endpoint force assumptions. Critical duality
bounds smooth forcing within the conditional spectral estimate. Initial energy
and prescribed force norms also bound total direct critical source work.
Finite accumulated transfer above a fixed fraction of viscous dissipation
suffices for continuation; controlling that accumulation remains open.
Parabolic magnification makes the source vanish; a nontrivial unforced limit
still requires velocity and pressure bounds and suitable compactness.

The unforced mixing analysis evolves an exact invariant family at eight
amplitudes and two Fourier resolutions, with a separate zero-shear control.
Its 601 checks pass. The continuum comparison proves that accumulated excess
transfer, spread dissipation and positive spread production divided by initial
squared critical norm are unbounded as the amplitude increases. Every member
is globally smooth and preserves odd Cartesian phase symmetry. A
neighboring-frequency cancellation supplies a finite nonlinear
critical-transfer bound within that same family. Arbitrary-data cumulative
production, general regularity and unforced blow-up remain open in this
analysis.

The signed curl spectrum retains helical polarization. Its positive spread
is $(K/2)\|\omega-Hu/(2K)\|_2^2$, and finite
$$
\int_0^T\left\|\omega-\frac{H}{2K}u\right\|_3^2dt
$$
controls enstrophy and the cumulative positive radial-spread production.
This is a critical conditional reduction, not an arbitrary-data estimate.
The accompanying 84-check analysis also constructs a smooth one-band
positive doublet with bounded first-order phase energy and divergent
enstrophy and $L^3$ residual.

### 2.6 Cassi fluid mechanics, thermal closure and phase currents

`turbulence/cassi-fluid-feasibility.md` derives pressure, counterflow momentum
flux and quantum stress from the ungauged positive-density first-order action
with a supplied carrier mass. Its exactly proportional common-phase branch is
compatible and irrotational; viscosity and the canonical irreversible
conversion require additional constitutive physics. The canonical density
system has a nonnegativity argument and a constant-reference relative entropy
under stated continuum assumptions.

The implemented self-sourced force has a nonzero periodic mean for smooth
positive data, contradicting a closed-fluid internal-stress interpretation.
The fixed 246-check schedule includes 28 CPU float64 native RK2 trajectories:
conversion, exact self-acceleration, decaying shear, two-dimensional
Taylor–Green flow, prescribed forced shear and short-time three-dimensional
Taylor–Green flow against an independent dealiased RK4 reference.
Promotion to a physical replacement fluid is **REJECT** under this bounded
schedule; concentration arrest is **NOT_RUN**. Physical viscosity and
material normalization remain open.

The selected constant-density completion in §7 has a variational capillary
stress, an explicit heat equation and nonnegative entropy production.
Its full-affinity reaction reduces to canonical gated conversion for
homogeneous composition. The 395-check schedule covers 27 model trajectories,
including viscous heating, conduction, coupled three-dimensional flow,
capillary release from rest and Galilean covariance. A separate
differentiation-matrix/DOP853 evolution agrees with the FFT endpoint.
Smooth-solution composition and temperature positivity bounds accompany
the finite-grid evidence. The result **SUPPORTS** the declared
constitutive budgets; physical replacement and global regularity remain
**UNESTABLISHED**.

### 2.7 Phase-current rotation and the viscosity boundary

`turbulence/cassi-fluid-phase-current-hydrodynamics.md` derives the
barycentric velocity of the phase-bearing action. One normalized Yang/Yin
doublet obeys the Mermin–Ho vorticity identity. An everywhere-positive global
doublet chart has zero integrated helicity on a closed domain; a smooth Hopf
doublet crosses component-zero circles and carries nonzero helicity. Two
fixed scale bands realize the periodic Beltrami flow
$u=A(\sin z,\cos z,0)$ with positive component populations.

Diffusing the two composition amplitudes gives exact viscous decay with
$\nu=D$ for that fixed-winding fixture. A nonzero phase-geometry commutator
contradicts the same identification for general phase potentials. Eliminating
closed exterior scale modes gives an exact memory kernel and initial-state
force; finite exterior systems recur. The selected exponential kernel has the
expected Markov limit, but the action does not yet supply its state, decay or
positive low-wave-number coefficient.

The fixed phase-current schedule passes **227 checks**, including exact
identities, odd-grid Fourier reconstructions, Hopf quadratures, memory
controls, independent raw-array reconstruction and source matching. It
**SUPPORTS** the conditional rotational class and restricted viscous
correspondence. The separate helical-spread follow-up passes **84 checks** and
**CONTRADICTS** static first-order phase-energy coercivity for enstrophy and
the critical scalar-Beltrami residual. Microscopic viscosity, a whole-field
dynamical concentration bound, arbitrary-flow hydrodynamics and
arbitrary-data regularity remain **UNESTABLISHED**.

### 2.8 Radiative material closure

`turbulence/cassi-radiative-material-closure.md` supplies a conditional
radiative extension of the selected capillary and thermal material. Planck
emission and Kirchhoff detailed balance determine LTE emissivity from a
supplied temperature and absorption coefficient. Frequency-group energy and
flux evolve under an M1 angular closure, while the material-frame four-force
transfers energy and momentum with the exact opposite increment applied to the
material. The gray homogeneous source conserves $CT+E$, produces entropy and
has a positive scalar implicit solve. The transport recovers the exact
constant-source slab, free-streaming M1 and optically thick diffusion limits.

The comprehensive fixed schedule records **33 of 34 passing checks**. Its one
failure rejects a normalized endpoint-error target at $\Delta t=0.01$ for the
coolest thermal-relaxation case. The fixed qualification passes **9 of 9
checks** at $\Delta t=0.004,0.002,0.001$, measures first-order refinement, and
meets the original accuracy limit at $0.001$ with zero stored energy drift.
This supports source subcycling under the supplied dimensionless coefficients.
The canonical densities still supply no physical temperature, mass density,
opacity, atomic populations or electromagnetic current. CassiCosmos
implementation therefore begins with a default-off, unit-calibrated
radiation state rather than the Observatory's appearance coefficients.

### 2.9 Compressible radiative plasma and stellar light

`turbulence/compressible-radiative-plasma-closure.md` supplies the conditional
completion required for thermal expansion, compression, shocks, species
emission, persistent stellar luminosity and intersecting sharp beams. The
material equations conserve mass, momentum and total energy and recover
Rankine–Hugoniot shocks from conservative fluxes. Level-resolved population
generators, Einstein coefficients and bound-free rates connect evaluated
atomic data to emissivity, opacity, ionization storage and heat. Nuclear mass
defect, gravitational contraction and accretion are finite accounted sources;
neutrino loss and escaping radiation are explicit destinations.

The angular transport retains intensity by frequency group and ordinate.
Counterpropagating beams with zero net flux therefore remain distinguishable,
and two axis-aligned beams cross without merging. The fixed verification
passes **70 of 70 checks** across symbolic identities, EOS recovery, four
normal shocks, population positivity, detailed balance, source ledgers,
quadrature moments, scattering and a crossing-beam stream. A separate
source-bound integrity qualification passes **25 of 25 checks** across
conservative-state and thermodynamic identities, rejection boundaries,
matter–radiation exchange cancellation, the complete stellar ledger, nuclear
conservation and missing-prerequisite classification. Atomic and nuclear data,
material units, initial composition and the Cassi field-to-baryonic-state map
remain supplied inputs or open identifications.

## References

- `foundations/xi-derivation.md`—first-principles derivation of the Qi-gravity coupling $\xi = \varphi^6$ used in the velocity equation
- `foundations/bubble-edge-geometry.md` §1.2—condensation-vs-diffusion balance used as a conditional analogy
- `cassi-physics.md`—the two-fluid PDE as written in the core physics document
- `predictions/falsifiable-predictions.md`—registered prediction catalog; the break-scale test remains prospective unless explicitly registered
- `computations/navier_stokes_stress_geometry_prereg.md`—fixed fixtures, numerical tolerances, and decision rules
- `computations/verify_navier_stokes_transfer.py`—exact finite-Fourier transfer verification
- `computations/verify_navier_stokes_stress_geometry.py`—symbolic geometry checks and independent Fourier quadrature
- `computations/navier-stokes-depletion-prereg.md`—fixed instantaneous-response and absorption controls
- `computations/verify_navier_stokes_depletion.py`—exact fine-transfer algebra and independent FFT/quadrature reconstruction
- `computations/navier-stokes-strain-departure-prereg.md`—fixed analytical comparison and Gaussian controls
- `computations/verify_navier_stokes_strain_departure.py`—departure algebra, Gaussian moments and independent deadline quadrature
- `computations/navier-stokes-critical-recurrence-prereg.md`—fixed spectral-spread and scalar-budget schedule
- `computations/verify_navier_stokes_critical_recurrence.py`—exact critical derivatives and independent FFT reconstruction
- `computations/navier-stokes-forced-concentration-prereg.md`—fixed source budgets, rescaling and kinematic concentration controls
- `computations/cassi-fluid-feasibility-prereg.md`—fixed conservative, thermodynamic, native-force and actual-flow controls
- `computations/verify_cassi_fluid_feasibility.py`—symbolic identities, native RK2 trajectories and independent RK4 comparison
- `computations/verify_navier_stokes_forced_concentration.py`—forced Fourier identities, independent FFT reconstruction and Gaussian quadrature
- `computations/navier-stokes-mixing-budget-prereg.md`—fixed continuum-comparison and cumulative trajectory controls
- `computations/verify_navier_stokes_mixing_budget.py`—601-check mixing receipt, Fourier evolution and independent spatial reconstruction
- `computations/navier-stokes-helical-spread-prereg.md`—fixed signed-moment, residual, flow-control and phase-concentration checks
- `computations/verify_navier_stokes_helical_spread.py`—84-check exact helical-spread and phase-coercivity verifier
- `field-experience/probe-outcome-ledger.md`—measured classifications and evidence paths
- `computations/cassi-fluid-thermodynamics-prereg.md`—selected fluid equations and fixed thermal controls
- `computations/cassi_fluid_thermodynamics.py`—reacting capillary/thermal model and command-line evolution
- `computations/verify_cassi_fluid_thermodynamics.py`—395-check thermal receipt, 27 model trajectories and independent numerical reference
- `computations/cassi-fluid-phase-current-prereg.md`—fixed current, topology, diffusion and memory controls
- `computations/verify_cassi_fluid_phase_current.py`—227-check exact, Fourier, Hopf, memory and raw-array verifier
- `turbulence/cassi-fluid-phase-current-hydrodynamics.md`—conditional rotational reduction and viscosity projection boundary
- `turbulence/cassi-radiative-material-closure.md`—conditional LTE transfer, M1 moments, covariant material exchange and implementation boundary
- `computations/cassi-radiative-material-prereg.md`—fixed comprehensive radiative-material schedule
- `computations/cassi_radiative_material.py`—Planck, M1, transfer, source and diffusion reference kernels
- `computations/verify_cassi_radiative_material.py`—33/34 comprehensive radiative-material receipt generator
- `computations/cassi-radiative-material-qualification-prereg.md`—fixed source-step accuracy qualification
- `computations/verify_cassi_radiative_material_qualification.py`—9-check source-subcycling qualification
- `turbulence/compressible-radiative-plasma-closure.md`—compressible, species, stellar-source and multi-angle completion
- `computations/compressible-radiative-plasma-prereg.md`—fixed 70-check closure schedule
- `computations/compressible_radiative_plasma.py`—reference compressible radiative-plasma kernels
- `computations/verify_compressible_radiative_plasma.py`—source-snapshotted 70-check verifier
- `computations/compressible-radiative-plasma-integrity-prereg.md`—fixed 25-check state, exchange, ledger and prerequisite qualification
- `computations/verify_compressible_radiative_plasma_integrity.py`—source-bound integrity qualification verifier
