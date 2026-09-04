# Field-Particle Dynamics Result

## Status: FAIL—September 2, 2026

## 1. Registered run

The first execution of `field_particle_dynamics_prereg.md` used the pinned
PA42 `resolution_X2` state, the complete PA12 spatial Hamiltonian, float32 GPU
state, a two-point configuration-space derivative, and a one-stage kick/drift
update. The selected stationary run used `dt = 0.02` for 32 steps
(`T = 0.64`).

The import and static-state gates passed:

- source SHA-256: `db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0`;
- runtime-state SHA-256: `5d43794099f52f4343486a2f1b38787356301153bd48d033d0d42451160ab6d3`;
- runtime charge: `3.999999972288`;
- runtime PA12 energy: `1.525187889698`;
- outer carrier fraction: `1.07081723823e-4`;
- zero-step state difference: 0 bytes;
- initial Gauss-law RMS residual: 0.

An independent NumPy reconstruction reproduced the source/runtime byte layout,
charge, outer fraction, energy (`1.525187855385`), and twelve selected GPU
Hamiltonian-gradient entries.

## 2. Frozen-gate result

The stationary evolution failed FP4:

| Quantity | Registered limit | Measured |
|---|---:|---:|
| Charge drift | `2e-3` | `6.4749397e-3` |
| Carrier-density RMS drift | `2e-3` | `3.4443007e-2` |
| Charged-field RMS drift | `5e-3` | `3.4318166e-5` |
| Final PA12 energy | diagnostic | `3.702852383667` |
| Final outer carrier fraction | diagnostic | `6.5373099e-3` |
| Carrier phase rate | within 20% of `omega_C` | `0.0034361081` (passes) |
| Final Gauss RMS | `2e-3` | `1.6057691e-5` (passes) |

The vacuum control also changed by up to `9.5367432e-7` after two steps. This
is a real numerical force from the two-point configuration derivative, whose
finite-step truncation does not vanish at a quartic stationary point.

The boosted control moved in the selected direction by `0.0374900583` while
retaining `1.0000117033` of its charge, but that does not override the frozen
stationary failure.

## 3. Verdict

**FAIL—FIELD-PARTICLE RUNTIME.**

The spatial field representation and independent PA12 reconstruction pass. The
one-stage temporal update is not accepted. The next registered implementation
uses a coupled fourth-order Runge–Kutta update and the five-point derivative
that is exact for each coordinate's quartic PA12 dependence. No production
default changes follow from this run.
