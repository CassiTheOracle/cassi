# Yang–Mills Artifact Audit

## Status: Execution record—September 2026

## Abstract
This record identifies the current source-bound finite receipts for the Yang–Mills block investigations and separates their evidence boundaries. The connected-block schedule, closed-Wilson coverage, cylindrical block map and exact-vacuum block controls remain distinct finite constructions, each with its own receipt and scope.

## 1. Finite artifact inventory

| Construction | Primary evidence | Independent evidence | Current finite disposition |
|---|---|---|---|
| Connected blocks | `runs/yang_mills_connected_blocks/current-verification.json` — 79 checks | The directory retains the raw-artifact reconciliation and source snapshots | Finite geometry and local operator controls pass; theorem and continuum inputs retain their declared analytical scope |
| Closed-Wilson repeated-edge coverage | `runs/yang_mills_closed_wilson_repeated_edge_coverage/verification.json` — 41/41 controls, classification `REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE`, ranks $865,867,867,867$ | `verification-independent.json` — 24/24 arithmetic and source-binding checks | The finite coverage construction is incomplete at the smallest coupling; its stopping rule forbids another finite word extension in this campaign |
| Cylindrical block map | `runs/yang_mills_block_map_recovery_20260914/verification.json` — 53 checks | `verification-independent-repaired.json` — 9 aggregate independent reconstructions; `verification-independent.json` is retained as a failed diagnostic | The seeded path, electric, genuine-refinement, subdivision and scale controls pass; exact analytical adoption remains open |
| Exact-vacuum blocks | `runs/yang_mills_vacuum_blocks_recovery_20260914/verification.json` — 305 checks | `verification-independent.json` — 78 source, fixture, local-energy and Gaussian reconstruction checks | The fixed group, derivative, local-energy and Gaussian controls pass; exact-vacuum analytical adoption and continuum control remain open |

The block-map independent reconstruction regenerates the primary seeded matrices without importing the primary verifier. Its largest path, electric, refined-block and subdivision errors are respectively $3.14\times10^{-16}$, $8.88\times10^{-16}$, $4.44\times10^{-16}$ and $2.37\times10^{-16}$. The vacuum independent reconstruction regenerates all five group fixtures and 45 local-energy rows and uses the explicit sine basis for the ten connected Gaussian rows. Its largest normalized Gaussian discrepancy is $1.81\times10^{-14}$.

## 2. Source and receipt binding

The accepted block-map pair is bound to
`computations/yang-mills-block-map-prereg.md`,
`computations/verify_yang_mills_block_map.py`,
`computations/verify_yang_mills_loop_gap.py` and
`computations/reconcile_yang_mills_block_map.py` by the adjacent manifests and
source snapshots in
`runs/yang_mills_block_map_recovery_20260914/`. The accepted vacuum pair uses
the corresponding protocol, primary verifier, shared helper and
`computations/reconcile_yang_mills_vacuum_blocks.py` snapshots in
`runs/yang_mills_vacuum_blocks_recovery_20260914/`.

A direct binding check reports `PASS` for each accepted receipt: every declared source hash equals the live source hash, every frozen source snapshot is byte-identical to its live source, every accepted receipt has zero failed checks, and each independent receipt records the SHA-256 of its primary receipt. The preserved block-map failed diagnostic remains outside the accepted pair.

## 3. Evidence boundary

The connected-block result supplies a strong-coupling finite-depth control under its displayed theorem hypotheses. The repeated-edge campaign supplies a finite coverage result with a measured rank deficiency and an explicit stopping rule. The cylindrical block-map result measures leakage for a fixed bare refinement and distinguishes pure graph subdivision from genuine plaquette refinement. The exact-vacuum result checks finite group, derivative, local-energy and Gaussian block identities.

Each construction retains its own missing obligations for an interacting fibre, uniform resolvent estimate, thermodynamic limit, continuum field and regulator-independent mass. The artifact set supplies no Cassi microscopic identification.

## 4. Continue

The next useful work is analytical reconciliation of the displayed block-map and exact-vacuum identities, followed by construction of a gauge-compatible interacting fibre or an equivalent Feshbach transfer operator. The finite receipts should be reused as fixed controls. The closed-Wilson repeated-edge campaign should remain stopped under its registered deficiency rule rather than extending the word family or changing the coupling schedule.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.10–9.17—connected blocks, exact-vacuum blocks and cylindrical block map.
- `computations/yang-mills-connected-block-prereg.md`—connected-block schedule.
- `computations/yang-mills-closed-wilson-repeated-edge-coverage-prereg.md`—closed-Wilson stopping rule.
- `computations/yang-mills-vacuum-block-prereg.md`—exact-vacuum block schedule.
- `computations/yang-mills-block-map-prereg.md`—cylindrical block-map schedule.
- `field-experience/probe-outcome-ledger.md` §§16, 19 and 21—current evidence classifications.
