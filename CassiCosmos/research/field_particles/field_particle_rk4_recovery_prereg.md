# Field-Particle RK4 Recovery Preregistration

## Status: Frozen—September 2, 2026

## 1. Scope

This recovery probe replaces the temporal discretization rejected in
`research/field_particles/field_particle_dynamics_report.md`. It does not alter
the pinned PA42 state, PA12 spatial Hamiltonian, boundary conditions, temporal
coefficient choice, or default-off production status.

The tested numerical changes are:

1. one coupled classical fourth-order Runge–Kutta step for all 18 canonical
   field coordinates and 16 second-order velocities;
2. four Hamiltonian-gradient evaluations at the standard RK4 stages;
3. a symmetric five-point configuration derivative,
   $[-E(q+2h)+8E(q+h)-8E(q-h)+E(q-2h)]/(12h)$, with `h = 1/32` times
   `max(1, abs(q))`;
4. `dt = 0.01`, 64 stationary steps, and total time `T = 0.64`;
5. the existing `dt = 0.01`, 40-step, speed-0.10 boost control.

For fixed values of every other coordinate, every term in PA12 is a polynomial
of degree at most four in the selected coordinate. The five-point derivative
therefore removes the two-point stencil's finite-`h` truncation term; float32
roundoff remains measured by the vacuum control.

## 2. Frozen acceptance gates

The run uses the same FP0–FP3 and FP5–FP9 gates declared in
`field_particle_dynamics_prereg.md`, with these additions and replacements:

- **RK4 identity:** `dt = 0` is byte-identical for canonical state and velocity.
- **Stationary charge:** relative drift is at most `2e-3`.
- **Stationary carrier density:** normalized RMS drift is at most `2e-3`.
- **Stationary charged field:** normalized RMS drift is at most `5e-3`.
- **Stationary energy:** relative PA12 energy drift is at most `5e-3`.
- **Stationary localization:** outer carrier fraction remains at most `2e-4`.
- **Carrier phase:** the center phase advances with the `exp(-i omega_C t)`
  sign and the measured rate is within 20% of registered `omega_C`.
- **Gauss law:** RMS residual remains at most `2e-3`.
- **Vacuum:** after two steps, every value is finite and maximum absolute state
  change is at most `2e-6`.
- **Boost:** the charge-weighted center moves in the selected direction and at
  least 99% of carrier charge remains.
- **Runtime:** the whole focused scene completes within 220 seconds.

The independent verifier must still reproduce the pinned energy and selected
Hamiltonian gradients. It uses the same registered five-point `h` but evaluates
the complete Hamiltonian independently with NumPy.

## 3. Stopping and verdict

The focused run executes once after the RK4 implementation parses and the
shader imports. Any failed gate produces
`FAIL—FIELD-PARTICLE RK4 RECOVERY`. Every gate passing produces
`PASS—EXPERIMENTAL FIELD-PARTICLE RK4 RUNTIME`.

A pass qualifies this default-off experimental runtime only. It does not select
PA43 temporal coefficients, demonstrate nonlinear attraction, authorize a
default-on cutover, or remove the legacy path.
