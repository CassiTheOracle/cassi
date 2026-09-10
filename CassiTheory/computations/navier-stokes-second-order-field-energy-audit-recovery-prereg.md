# Second-Order Field Energy: PA12 Source-Region Recovery

## Status: Pre-registered—September 2026

## 1. Trigger

The first execution under
`computations/navier-stokes-second-order-field-energy-audit-amendment.md`
records **92/93** checks in
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.initial-failed.json`.
Its SHA-256 is
`6e266ad33fd4193c2d4e61e5df98562cc8343015f0eef4626e72f5b0900d65a2`.
The verifier SHA-256 for that execution is
`e3831536e9de807b1f711a205ab69fa5a5d2f3a5d9e0f8ea9d81fdc363b4d166`.

The only failed check is B07. The audit amendment scopes the electric
curvature coefficient to the tagged PA11 Lagrangian region. The magnetic
curvature coefficient belongs to the static Hamiltonian density in the
adjacent tagged PA12 region:

$$
\mathcal H_P\supset
\frac1{4\mu_x}F_{ij}^aF_{ij}^a.
\tag{SOR1}
$$

B07 searched PA11 for the PA12 term. The canonical source, its frozen hash,
the gauge-energy algebra and every numerical or symbolic check remain
unchanged.

## 2. Fixed implementation correction

The verifier must:

1. extract PA11 from the source-free particle-sector action through
   `\tag{PA11}`;
2. extract PA12 from “The static Hamiltonian density is” through
   `\tag{PA12}`;
3. require the electric term inside PA11;
4. require the magnetic term inside PA12;
5. retain the PA14-scoped complete Gauss check.

This recovery protocol is added to the source-existence and frozen-hash
manifest. The resulting inventory has exactly **95 checks**: F01–F09 are
source-existence checks, F10–F17 are frozen-hash checks, and A01–E11 retain
the 78 substantive checks fixed by the audit amendment.

## 3. Decision rule

Run the corrected verifier once. All **95/95** checks must pass, the receipt
must use schema
`cassi.navier-stokes.second-order-field-energy.verification.v2`, and terminal
output must end with `ALL CHECKS PASSED`. Any failure retains
`FAIL—SECOND-ORDER FIELD ENERGY AUDIT` and blocks documentary integration.
The corrected run writes
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`
and leaves every failed and v1 receipt unchanged.
