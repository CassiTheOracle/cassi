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
departure and spectral-spread bounds on critical transfer. Exact source budgets
extend the conditional estimate to smooth forcing. Explicit initial-data and
kinematic controls delimit scalar-energy and local-geometric closure arguments.
An exact globally smooth mixing family excludes amplitude-linear cumulative
critical-transfer bounds while admitting a finite nonlinear bound of its own.
Arbitrary-data critical production, global regularity and a Cassi
canonical-density-to-physical-momentum constitutive map remain open.

The separate fluid-feasibility study derives the conservative momentum flux
of a restricted first-order action branch and audits the actual density solver.
Its 246 checks include 28 native trajectories. The ordinary Navier–Stokes
controls pass; the native self-sourced force produces mean acceleration in a
periodic box. A physical closed-fluid completion remains open.

The separate selected capillary/thermal closure conserves momentum and
total energy and produces nonnegative entropy, with exact homogeneous
canonical conversion. Its 395 checks cover 27 model trajectories and an
independent differentiation-matrix reference. Microscopic transport and
physical-fluid identification remain open.

## 1. Document index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `turbulence/kolmogorov-from-phi.md` | Turbulence spectra from the two-fluid PDE | Derived conditional / Hypothesized closures |
| 2 | `turbulence/navier-stokes-transfer-boundary.md` | Critical transfer, cubic heat correction, and coercivity | Derived identities and obstructions / conditional small-data estimates |
| 3 | `turbulence/navier-stokes-stress-geometry.md` | Exact stress evolution and helical covariance conditions | Derived filtered identities / Hypothesized geometric closure |
| 4 | `turbulence/navier-stokes-depletion-dynamics.md` | Exact fine-scale transfer response, matter binding and exterior-memory comparison | Derived filtered identities and instantaneous obstructions / Conditional continuation estimate |
| 5 | `turbulence/navier-stokes-strain-departure.md` | Energy-coupled departure, spectral concentration, forced budgets and cumulative mixing obstruction | Derived conditional estimates and cumulative mixing obstruction / Open arbitrary-data critical work |
| 6 | `turbulence/cassi-fluid-feasibility.md` | Conservative action reduction, native-force obstruction, reacting capillary/thermal closure and actual flow controls | Derived conditional mechanical and thermal identities / Tested solver controls / Open physical-fluid completion |

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
$c_{\rm S}\sqrt{\eta\mathcal C}\,Y$.
The exact spectral-spread budget has an uncontrolled nonlinear production
term. A smooth periodic datum develops spread immediately from zero;
a positive-moment scalar construction has divergent critical norm despite
positive departure. The separate departure and recurrence schedules pass
71 and 134 checks respectively. The forced budget and scaling controls have
215 passing checks in both the frozen preregistered run and the separate post-run
qualification. The qualification explicitly covers all three source-work signs
and the scaled Gaussian maximum speed, with qualified endpoint force assumptions.
Critical duality bounds smooth forcing within the conditional spectral estimate.
Initial energy and prescribed force norms also bound total direct critical
source work. Finite accumulated transfer above a fixed fraction of viscous
dissipation suffices for continuation; controlling that accumulation remains open.
Parabolic magnification makes the source vanish; a nontrivial unforced limit
still requires velocity and pressure bounds and suitable compactness.
The unforced mixing analysis evolves an exact invariant family at eight
amplitudes and two Fourier resolutions, with a separate zero-shear control.
Its 601 checks pass. The continuum comparison proves that accumulated
excess transfer divided by initial squared critical norm is unbounded as the
amplitude increases. Every member is globally smooth and preserves odd
Cartesian phase symmetry. A neighboring-frequency cancellation supplies
a finite nonlinear initial-data bound within that same family.
Arbitrary-data critical work, general regularity and unforced blow-up
remain open in this analysis.

### 2.6 Cassi fluid mechanics and thermal closure

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
schedule; concentration arrest is **NOT_RUN**. Physical viscosity, material
normalization and a rotational hydrodynamic reduction remain open.

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
- `field-experience/probe-outcome-ledger.md`—measured classifications and evidence paths
- `computations/cassi-fluid-thermodynamics-prereg.md`—selected fluid equations and fixed thermal controls
- `computations/cassi_fluid_thermodynamics.py`—reacting capillary/thermal model and command-line evolution
- `computations/verify_cassi_fluid_thermodynamics.py`—395-check thermal receipt, 27 model trajectories and independent numerical reference
