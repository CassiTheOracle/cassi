# Field-Particle RK4 Recovery Result

## Status: FAIL—September 2, 2026

## 1. Registered run

The first execution of `field_particle_rk4_recovery_prereg.md` used the pinned
PA42 `resolution_X2` state, the complete PA12 spatial Hamiltonian, the
registered five-point configuration derivative with `h = 1/32`, and a coupled
four-stage Runge–Kutta update. The stationary run used `dt = 0.01` for 64
steps (`T = 0.64`). The boosted control used `dt = 0.01` for 40 steps with
selected speed `0.1`.

The import, static-state, Hamiltonian-gradient, and physical-evolution checks
passed. The stationary measurements were:

| Quantity | Registered limit | Measured |
|---|---:|---:|
| Charge drift | `2e-3` | `4.8971096e-7` |
| Carrier-density RMS drift | `2e-3` | `8.3092300e-7` |
| Charged-field RMS drift | `5e-3` | `1.7767397e-8` |
| PA12 energy drift | `5e-3` | `2.0455729e-8` |
| Final outer carrier fraction | `2e-4` | `1.0708168e-4` |
| Carrier phase rate | within 20% of `omega_C` | `0.0034170290` |
| Final Gauss RMS | `2e-3` | `7.7171872e-7` |
| Vacuum maximum residual | `2e-6` | `8.4936613e-11` |

The boosted carrier moved by `0.0374414470` along the selected axis and
retained `0.9999999596` of its charge. The focused GPU work took 749 ms for
the stationary evolution and 479 ms for the boost evolution.

## 2. Frozen-gate result

FP3 failed. A zero-time RK4 dispatch changed six bytes in the canonical state.
The changed values are signed-zero encodings produced by multiplying a finite
rate by `dt = 0`; the floating-point values remain equal, but the registered
contract requires byte identity.

The independent verifier therefore also failed its requested-state seed
identity check. Its source-to-seed identity, physical energy reconstruction,
and all twelve selected Hamiltonian-gradient comparisons passed.

## 3. Verdict

**FAIL—FIELD-PARTICLE RK4 RECOVERY.**

The coupled RK4 dynamics meet every registered physical bound, but the frozen
zero-time byte-identity requirement is part of the acceptance contract. A
separate registered recovery adds an explicit `dt = 0` canonical copy path;
no nonzero-time equation or threshold changes.
