# Field-Particle Zero-Time Identity Recovery Preregistration

## Status: Frozen—September 2, 2026

## 1. Question

Can the accepted coupled RK4 field evolution satisfy exact zero-time canonical
identity without changing any nonzero-time equation, numerical coefficient,
run length, or acceptance threshold?

## 2. Frozen implementation

The only shader change is an early `dt == 0.0` branch in the RK4 integration
pass. Every state and velocity output is copied directly from its canonical
base buffer. Stage-one accumulators are cleared. No Hamiltonian derivative is
used to form an output value in this branch.

The nonzero-time RK4 implementation, five-point configuration derivative,
unit experimental temporal coefficients, seed, and all prior thresholds remain
unchanged.

## 3. Registered run

Run `res://scenes/verify_field_particles.tscn` windowed once after importing
the shader. Use the existing stationary control (`dt = 0.01`, 64 steps) and
boost control (`dt = 0.01`, 40 steps, speed `0.1`). The independent NumPy
verifier runs from the same arm.

## 4. Frozen decision rule

`PASS—FIELD-PARTICLE IDENTITY RECOVERY` requires every existing FP0–FP9 check,
the independent verifier, and these exact conditions:

- zero-time state difference is zero bytes;
- requested-state seed identity passes independently;
- stationary PA12 energy drift is at most `5e-3`;
- stationary carrier charge drift is at most `2e-3`;
- final outer carrier fraction is at most `2e-4`;
- vacuum maximum residual is at most `2e-6`;
- boosted displacement is positive and retained charge is at least `0.99`.

Any failed condition gives `FAIL—FIELD-PARTICLE IDENTITY RECOVERY`. Results are
recorded before any further implementation change.
