# Second-Order Field Energy: PA12 Multiline-Anchor Recovery

## Status: Pre-registered—September 2026

## 1. Trigger

The execution governed by
`computations/navier-stokes-second-order-field-energy-audit-recovery-prereg.md`
records **94/95** checks in
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.recovery1-failed.json`,
SHA-256
`7cf8a368d8e85c2044873bf25d1b6f20c42394ac1fb6fc2231b3c76ef3284875`.
The verifier SHA-256 is
`f6f4a5ab845f1897bfad63fad836e92d53b72432833bf044f792d7e930244a73`.

B07 remains the only failed check. The PA12 extractor searches for the literal
single-line phrase “The static Hamiltonian density is”. The source wraps that
phrase across two lines, so the start anchor is absent and the extracted
region is empty. The magnetic term and its frozen source hash remain correct.

## 2. Fixed correction

Extract the PA12 region between the exact equation tags `\tag{PA11}` and
`\tag{PA12}`. Require

$$
\frac1{4\mu_x}\mathcal F_{ij}^a\mathcal F_{ij}^a
\tag{SOR2}
$$

inside that nonempty region. No other substantive check, coefficient,
tolerance, source equation, numerical fixture or interpretation changes.

Add this protocol to the source-existence and frozen-hash manifest. The final
inventory contains exactly **97 checks**: F01–F10 source-existence checks,
F11–F19 frozen-hash checks, and the unchanged 78 A–E checks.

## 3. Decision rule

Run the verifier once after the exact tag-anchor correction. Success requires
**97/97** checks, schema
`cassi.navier-stokes.second-order-field-energy.verification.v2`, and terminal
`ALL CHECKS PASSED`. Any failure records
`FAIL—SECOND-ORDER FIELD ENERGY AUDIT` and blocks documentary integration.
The run writes
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`
and leaves all retained failure and v1 receipts unchanged.
