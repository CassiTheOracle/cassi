# Field-Dynamics Particle Runtime Preregistration

## Status: Frozen engineering and finite-grid physics gates—September 2026

## 1. Scope

This campaign adds a default-off field-particle runtime to CassiCosmos. The
runtime evolves the reduced three-dimensional particle-sector fields used by
the localized CassiTheory stationary campaign:

\[
\Psi\in\mathbb C^2,\qquad
\Phi\in\mathbb R^3,\qquad
\mathcal A_i\in\mathfrak{su}(2)_Q,\qquad
\chi_C\in\mathbb C.
\]

The spatial Hamiltonian is the finite-grid PA12 specialization represented by
`CassiTheory/computations/particle_stationary_bvp.py`. The runtime uses the
source-free PA11 temporal structure in temporal gauge, with positive
unit-valued dimensionless temporal groups. Those groups are an explicit
uncalibrated numerical selection because CassiTheory has not selected the PA43
groups. Results qualify this experimental runtime only. They do not establish a
continuum particle, nonlinear attraction basin, physical species, mass, spin,
statistics, lifetime, or formation rate.

The localized input is the `h_C = 2.9598260763447164`, `Q_C = 4`, `R = 4`,
`N = 29` resolution-X2 block-01 field. A deterministic converter produces the
runtime float32 seed and records the source and output hashes.

## 2. Runtime authority

The opt-in runtime is field-authoritative:

- the canonical state is the field buffer;
- charge, center, radius, energy proxy, and velocity are derived from that
  buffer;
- render/object records are regenerated readouts;
- the legacy particle mass-deposit, KDK, accretion, and merge passes do not run
  in field-particle mode;
- the existing path remains byte-identical when the toggle is off.

Moving-mesh sites, tree nodes, and renderer instances may remain numerical
acceleration or presentation data. They must not become independent matter
state in this mode.

## 3. Discretization and temporal step

The runtime uses the same `N^3` Cartesian field layout, fixed outer shell,
second-order one-sided edge derivatives, centered interior derivatives, Pauli
generators, and PA12 coefficients as the source calculation. The carrier is
first order in time. The charged doublet, adjoint, and spatial gauge connection
are second order in time. A double-buffered compute pass prevents read/write
races.

The finite-grid force is the derivative of the declared discrete spatial
Hamiltonian. Temporal-gauge Gauss residual is measured directly from the
charged velocities and gauge electric field. No gauge-fixing energy may be
counted as physical energy.

## 4. Frozen checks

### FP0—seed provenance

The converter must verify the source NPZ SHA-256 before writing. The runtime
manifest must bind the source hash, output hash, field order, `N`, `R`, `dx`,
`h_C`, `Q_C`, and `omega_C`.

### FP1—import identity

After loading the float32 seed, every field component must agree with an
independent Python decode of the runtime binary to zero byte difference. The
outer shell must equal the registered vacuum/carrier boundary values exactly in
float32.

### FP2—static observables

Before evolution:

- carrier charge relative error from 4 is at most `2e-5`;
- carrier center norm is at most one grid spacing;
- carrier outer fraction is at most `2e-4`;
- all state values are finite;
- the physical energy reported by the independent verifier is within `5e-4`
  relative error of the float64 source evaluation.

### FP3—zero-step identity

A dispatch with `dt = 0` must leave the complete canonical field state
byte-identical.

### FP4—stationary-phase evolution

For the centered unboosted seed over the frozen short run:

- all values remain finite;
- carrier-charge relative drift is at most `2e-3`;
- carrier-density RMS drift is at most `2e-3`;
- the charged-field RMS drift is at most `5e-3`;
- carrier phase advances with the sign of `exp(-i omega_C t)`;
- the measured center phase rate agrees with `omega_C` to 20% once its total
  phase excursion exceeds the float32 floor.

### FP5—Gauss residual

The temporal-gauge Gauss RMS starts below `2e-4` and remains below `2e-3` for
the frozen stationary-phase run. The carrier is neutral and contributes no
`SU(2)_Q` source.

### FP6—derived readout purity

Reading the object catalog twice without stepping returns identical charge,
center, radius, velocity, and component count. Clearing and reconstructing the
catalog from the unchanged field leaves the next field step byte-identical to a
control that retained the catalog.

### FP7—boosted motion

A separately initialized low-speed boost must move the derived carrier center
in the selected direction while retaining at least 99% of its charge over the
short run. This is an engineering motion check, not a calibrated Lorentz or
Galilean particle law.

### FP8—field authority and rollback

With field-particle mode enabled, telemetry must report zero legacy particle
deposit, KDK, accretion, and merge dispatches. With the mode disabled, the
existing focused regression must remain byte-identical.

### FP9—runtime bound

The focused `N = 29` short run must complete without device loss or timeout on
the RX 7900 XTX. Runtime is reported, not used to claim production-scale
throughput.

### FP10—battery

The new windowed arm exits zero only when FP0–FP9 pass. The existing complete
battery must remain green with the field-particle feature disabled by default.

## 5. Controls

The focused arm includes:

1. the registered localized seed;
2. a zero-step identity control;
3. a vacuum control;
4. a low-speed boosted seed;
5. a readout-clear/reconstruction control;
6. the legacy feature-off regression.

## 6. Decision tree

- All FP0–FP10 checks pass: `PASS—EXPERIMENTAL FIELD-PARTICLE RUNTIME`.
- Any numerical, provenance, authority, conservation, or rollback check fails:
  `FAIL—FIELD-PARTICLE RUNTIME`.
- A failure is retained. Thresholds and stopping rules are not changed after
  the first frozen run.

A passing result authorizes the default-off experimental runtime. It does not
authorize enabling it by default or removing the legacy particle implementation.
