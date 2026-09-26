# Conservative scale action and explicit reservoirs — preregistration

Status: PRE-REGISTERED before implementation and first run — 2026-09-02

## Scope and scientific boundary

This campaign completes the already default-off vector-Qi rotation sector with an explicit discrete scale action and two observable scale-boundary reservoirs. It compares what the cascade factor could attenuate. It does not claim that Betelgeuse cells and protons are the same object, derive QCD from stellar plasma, fit an astronomical image, or promote the scale action into CassiTheory.

The production branch remains the flux branch registered by `rotation_prereg.md`. Alternative branches are reference comparisons, not hidden production fallbacks.

## Declared discrete action

Each coarse spatial cell `C` and scale rung `a=0,...,S-1` carries displacement `u[a,C]` and canonical momentum `p[a,C]`. The scale coordinate is dimensionless,

`mathfrak s = log_phi(ell/ell_*)`,

with unit rung spacing, so adjacent rungs differ by a physical scale factor `phi`. The per-cell field inertia is `M_Q`. The closed field action is

```
L_field = sum[a,C] M_Q/2 |u_dot[a,C]|^2 - V_space - V_scale

V_space = sum[a,C] M_Q/2 [
    c_T^2 partial_j u_i partial_j u_i
  + (c_L^2-c_T^2) (div u)^2
]

V_scale = sum[a=0..S-2,C]
    M_Q omega_s^2 D[a+1/2]/2 |u[a+1,C]-u[a,C]|^2
```

where `D[a+1/2]=d^(a+1)` is the existing flux-interface coefficient. Variation gives the live interior equation

```
p_dot[a,C] = M_Q [
    c_T^2 laplacian(u[a,C])
  + (c_L^2-c_T^2) grad(div u[a,C])
] + J[a-1/2,C] - J[a+1/2,C]

J[a+1/2,C] = M_Q omega_s^2 D[a+1/2]
              (u[a,C]-u[a+1,C]).
```

Every internal interface therefore applies equal and opposite momentum impulses. `D` is a dimensionless constitutive coefficient in the potential; it is not an unexplained loss factor.

## Explicit scale-boundary reservoirs

Two per-spatial-cell reservoir fields represent the omitted scales below rung 0 and above rung `S-1`. Boundary `b` has displacement `u_R[b,C]`, momentum `p_R[b,C]`, positive inertia `M_R`, and nonnegative dimensionless coupling `kappa_b`. Add

```
L_R = sum[b,C] M_R/2 |u_R_dot[b,C]|^2
      - sum[b,C] M_Q omega_s^2 kappa_b/2
        |u_edge[b,C]-u_R[b,C]|^2.
```

The boundary impulse on the edge rung is

```
Delta p_edge = M_Q dt omega_s^2 kappa_b (u_R-u_edge),
Delta p_R    = -Delta p_edge.
```

The production defaults are `kappa_lower=kappa_upper=0`: both boundaries are explicitly present and closed. Opening a boundary requires an explicit configuration value. Reservoir displacement, momentum, next momentum, couplings, and inertia are exposed by verifier readback; bounded production telemetry exposes only aggregate boundary-impulse magnitudes.

The reservoir is co-located with its spatial cell. Boundary scale exchange therefore changes neither total linear momentum nor total orbital angular momentum: the field and reservoir impulses are opposite at the same spatial center. Existing intrinsic-spin correction excludes the new boundary pair so it is not counted twice.

## Unit map

Let simulation base units be `(L0,M0,T0)`. The engine stores per-cell rather than density variables:

| Quantity | Engine symbol | Physical unit and map |
|---|---|---|
| position/displacement | `x`, `u` | `L`; `u_phys=L0*u_sim` |
| time/timestep | `t`, `dt` | `T`; `t_phys=T0*t_sim` |
| field/reservoir inertia | `M_Q`, `M_R` | `M`; `M_phys=M0*M_sim` |
| canonical momentum | `p`, `p_R` | `M L/T`; `p_phys=M0 L0/T0*p_sim` |
| interface momentum rate | `J` | `M L/T^2`; `J_phys=M0 L0/T0^2*J_sim` |
| energy/heat | `E`, `Q_heat` | `M L^2/T^2`; `E_phys=M0 L0^2/T0^2*E_sim` |
| angular momentum | `L`, `spin_heat.xyz` | `M L^2/T`; multiply by `M0 L0^2/T0` |
| wave speeds | `c_T`, `c_L` | `L/T`; multiply by `L0/T0` |
| scale frequency | `omega_s` | `1/T`; divide simulation value by `T0` |
| scale coordinate/coefficient | `mathfrak s`, `d`, `D`, `kappa` | dimensionless |

For continuum comparison, cell volume is `V_C`; mass density is `rho_Q=M_Q/V_C`, momentum density is `p/V_C`, and the per-cell scale flux is `J=V_C T_{i mathfrak s}` for unit `Delta mathfrak s`. No physical values for `(L0,M0,T0)` are selected in this campaign, so the result is a closed nondimensional map rather than a proton or stellar calibration.

## Frozen implementation

- Append three storage buffers to `cassi_rotation_stress.glsl`: reservoir displacement, momentum, and next momentum, each shaped `[2, rotation_cells, vec4]`.
- Reuse the three existing spare push-constant floats for `M_R`, `kappa_lower`, and `kappa_upper`; do not change the 96-byte push-constant layout.
- Update each boundary reservoir exactly once in the field-kick pass and drift it in the field-drift pass.
- Create the buffers only when `rotation_stress_enabled=true`; the established default-off engine path remains untouched.
- Extend local verifier writes/readbacks and bounded telemetry. Do not publish full reservoir fields through the production snapshot.
- Keep the existing interior flux equation and default closed-boundary field results unchanged.

## Frozen branch comparison

At fixed nonzero displacement contrast and `d=phi^-1`:

1. **Readout-only:** dynamics use the unit coefficient; changing `d` changes no state impulse, so the normalized dynamic ratio is `1`.
2. **Open current:** a reduced resolved force is multiplied by `d` without an opposite receiver; its ratio is `d`, but its missing momentum is `(1-d)` times the unit impulse. It is rejected as a closed production law.
3. **Amplitude:** if the physical contrast is `d Delta u`, quadratic interface energy gives an impulse ratio `d^2`; equal and opposite forces close the ledger.
4. **Flux:** the action coefficient is `D=d`; the impulse ratio is `d`, and the interface or explicit reservoir receives the exact opposite impulse.
5. **Geometry:** excluded from numerical adoption because no live `G_(i mathfrak s)` generator exists and no universal `d` or `d^2` scaling follows.

A closed “current” implementation with an explicit receiver is dynamically the flux branch at fixed geometry; the campaign must report this identifiability degeneracy rather than count it as independent evidence.

## Raw receipts

The windowed local-RD scene writes `_diag/rotation_scale_completion_gpu.json` with complete configurations, producer SHA-256, and full pre/post field and reservoir arrays. `research/rotation/rotation_scale_completion_verify.py` independently recomputes action gradients, impulses, ledgers, and branch ratios, and writes `_diag/rotation_scale_completion_verify.json` bound to raw, producer, verifier, and preregistration SHA-256 values.

## Registered gates

### G92 — action gradient and unit closure

For a deterministic three-rung, two-reservoir double-precision fixture, central finite differences of the declared potential must match the analytic field and reservoir forces to relative `1e-6`. The receipt must contain every quantity and conversion in the frozen unit table with no dimension mismatch.

### G93 — GPU boundary impulse closure

Separate lower- and upper-boundary cases must each have nonzero edge impulse. Field plus both reservoirs must close linear momentum to relative `2e-6`; the active edge/reservoir impulses must be equal and opposite to relative `2e-6`; and GPU impulses must match the analytic action to relative `2e-5`.

### G94 — closed-boundary null

With both couplings zero, nonzero reservoir/edge displacement contrasts and zero momenta must leave all field and reservoir momentum bytes unchanged after one isolated step. Every reservoir value must remain finite.

### G95 — branch separation and ledger decision

Reference impulse ratios must match `1`, `d`, `d^2`, and `d` for readout, open-current, amplitude, and flux branches to relative `1e-12`. The open-current missing-momentum fraction must equal `1-d` to `1e-12` and fail a `1e-6` closure bound; amplitude and flux force sums must close to `1e-12`. The current/flux fixed-geometry degeneracy must be recorded.

### G96 — GPU coefficient scaling

For otherwise identical lower-boundary cases, GPU impulse ratios at `kappa=d` and `kappa=d^2` relative to `kappa=1` must match `d` and `d^2` within `2e-4` relative error, with finite states and identical impulse direction.

## Decision tree and stopping rule

G92–G96 all PASS: `ADOPT_EXPLICIT_FLUX_RESERVOIRS`; the flux branch remains the only production scale law.

Any source/configuration/hash/shape/finite-state failure: `INCONCLUSIVE—IMPLEMENTATION`.

A valid run with any gate failed: `REJECT_SCALE_COMPLETION_AS_IMPLEMENTED`.

Run each GPU case once and the independent verifier once. Retain negative outcomes; do not tune thresholds, seed vectors, field values, or couplings and rerun under this preregistration.
