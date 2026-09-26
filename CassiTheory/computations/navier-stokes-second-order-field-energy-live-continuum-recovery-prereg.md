# Second-Order Field Energy: Live Continuum Correspondence Recovery

## Status: Pre-registered—September 2026

## 1. Trigger

The execution governed by
`computations/navier-stokes-second-order-field-energy-equation-tag-recovery-prereg.md`
records **107/107** checks in
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.equation-tag-recovered.json`,
SHA-256
`df82e9f22e15ca69bc4d97154db0a0a038b66e8543d33d887c3ccd3244264bd0`.
The verifier SHA-256 is
`c02b16c41ef00015a932a814bf1523905ec318c2ba0e95915f4e3c43e7d212d0`.

Independent source review identifies one remaining correspondence defect.
`CassiCosmos/compute/cassi_two_fluid.glsl` applies the extent- and grid-dependent
periodic finite-difference operators `lap_ey_at` and `lap_ei_at`. In `pass_a`,
`lap_ey` and `lap_ei` enter their acceleration assignments with coefficient
one. The paper instead calls the arbitrary-coefficient continuum expression
$c_s^2\Delta$ the literal live shader core. The $c_s^2=0.01$ entry in
`parameter-inventory.md` belongs to named pressure solvers and is not a hidden
coefficient of this shader.

## 2. Fixed interpretation and source check

The paper must distinguish three statements:

1. the literal source-free, unclamped shader branch uses a shared discrete
   operator $\Delta_h$ with normalized coefficient one;
2. the displayed $c_s^2\Delta$ equation is a continuum analytical family whose
   normalized live correspondence is $c_s^2=1$;
3. the exact Hamiltonian conservation statement belongs to that continuous-time
   continuum family, not to the shader's finite-difference, finite-time-step
   runtime update.

The generalized coefficient remains useful because the weighted symmetrizer
and conversion potential are independent of its nonnegative value. It is not
identified with the separately registered pressure-solver value $0.01$.

Add **A22**. Inside the comment-stripped `lap_ey_at` region, require the
extent-dependent axis spacings, one mixed-plane coefficient and one mixed-plane
stencil term. Inside `pass_a`, require the exact unit-coefficient assignments
for both `lap_ey` and `lap_ei`. The check establishes discrete-source form and
normalization only; it does not assert exact runtime energy conservation.

No shader, Navier–Stokes identity, scalar symmetrizer, coefficient value,
fixture, tolerance or other mathematical check changes. Add this recovery
protocol to the source-existence and frozen-hash manifest after it is written
and before implementation. The terminal inventory contains exactly **110
checks**: F01–F14 source-existence checks, F15–F27 frozen-source hash checks,
A01–A22, B01–B13, C01–C19, D01–D16 and E01–E13.

## 3. Decision rule

Run the corrected verifier once. Success requires **110/110** checks, schema
`cassi.navier-stokes.second-order-field-energy.verification.v2`, and terminal
`ALL CHECKS PASSED`. Any failure records
`FAIL—SECOND-ORDER FIELD ENERGY AUDIT` and blocks documentary integration.
The run writes
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`
and leaves every retained failed, v1, 97-check, 103-check, 105-check and
107-check receipt unchanged.
