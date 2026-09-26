# Second-Order Field Energy: Equation-Tag Citation Recovery

## Status: Pre-registered—September 2026

## 1. Trigger

The execution governed by
`computations/navier-stokes-second-order-field-energy-scale-anchor-recovery-prereg.md`
records **105/105** checks in
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.scale-anchor-recovered.json`,
SHA-256
`469b41f0099e888d0cee5464400cb80ed69a91f9e80496ae50a2ffa5341bfd91`.
The verifier SHA-256 is
`2ce7d38d86105a4efea688465e9f95e88ebab2642874e54a3edc86f87d7ca2f6`.

The equation-recovery protocol defines the independent projected velocity and
acceleration coefficients in (SER8) and (SER9). Its E12 and E13 bullets cite
nonexistent labels (SER10) and (SER11). The verifier implements the displayed
(SER8) and (SER9) formulas and its checks pass, so this is a protocol citation
defect rather than a mathematical or implementation failure.

## 2. Operative correction

For the complete evidence chain, the E12 reference in
`computations/navier-stokes-second-order-field-energy-equation-recovery-prereg.md`
means (SER8), and the E13 reference means (SER9). The frozen parent protocol
remains unchanged. No source equation, coefficient dictionary, fixture,
calculation, tolerance, interpretation or mathematical check changes.

Add this recovery protocol to the source-existence and frozen-hash manifest
after it is written and before the next execution. The terminal inventory
contains exactly **107 checks**: F01–F13 source-existence checks, F14–F25
frozen-source hash checks, and the unchanged 82 A–E checks.

## 3. Decision rule

Run the manifest-qualified verifier once. Success requires **107/107** checks,
schema `cassi.navier-stokes.second-order-field-energy.verification.v2`, and
terminal `ALL CHECKS PASSED`. Any failure records
`FAIL—SECOND-ORDER FIELD ENERGY AUDIT` and blocks documentary integration.
The run writes
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`
and leaves every retained failed, v1, 97-check, 103-check and 105-check receipt
unchanged.
