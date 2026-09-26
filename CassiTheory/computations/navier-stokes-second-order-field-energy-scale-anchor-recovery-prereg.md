# Second-Order Field Energy: Scale-Term Anchor Recovery

## Status: Pre-registered—September 2026

## 1. Trigger

The execution governed by
`computations/navier-stokes-second-order-field-energy-equation-recovery-prereg.md`
records **102/103** checks in
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.scale-anchor-failed.json`,
SHA-256
`0506dc9da9004862c29578c416925f0de817fae814144aa7a869903ee689a439`.
The verifier SHA-256 is
`1627633ee23e21282d7269c895ea880ac29e59af13180aa9f5f0cb5f276f6fd0`.

B12 is the only failure. The PA11 and PA12 scale-curvature terms are present,
but the check removes all whitespace from each tagged source region while
retaining the space in each expected LaTeX command `\mathfrak s`. Source
compaction therefore produces `\mathfraks`, so both literal comparisons fail.
All mathematical, independent projected-equation and other source checks pass.

## 2. Fixed correction

Apply the same whitespace-compaction function to each expected B12 LaTeX token
before comparing it with the compact PA11 or PA12 region. Require both

$$
\frac{\epsilon_{\mathfrak s}}{2}
\mathcal F_{t\mathfrak s}^a\mathcal F_{t\mathfrak s}^a
\tag{SAR1}
$$

and

$$
\frac{1}{2\mu_{\mathfrak s}}
\mathcal F_{i\mathfrak s}^a\mathcal F_{i\mathfrak s}^a
\tag{SAR2}
$$

inside their respective tagged equation regions after identical compaction.
No source equation, mathematical fixture, coefficient, tolerance,
interpretation or other check changes.

Add this recovery protocol to the source-existence and frozen-hash manifest
after it is written and before implementation. The terminal inventory contains
exactly **105 checks**: F01–F12 source-existence checks, F13–F23 frozen-source
hash checks, and the unchanged 82 A–E checks.

## 3. Decision rule

Run the corrected verifier once. Success requires **105/105** checks, schema
`cassi.navier-stokes.second-order-field-energy.verification.v2`, and terminal
`ALL CHECKS PASSED`. Any failure records
`FAIL—SECOND-ORDER FIELD ENERGY AUDIT` and blocks documentary integration.
The run writes
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`
and leaves every retained failure, v1, 97-check and 103-check failed receipt
unchanged.
