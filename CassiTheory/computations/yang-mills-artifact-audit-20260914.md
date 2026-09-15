# Yang–Mills Artifact Audit

## Status: Execution record—September 2026

## Abstract
This record identifies the current source-bound finite receipts for the Yang–Mills block investigations and separately records finite execution artifacts whose source snapshot or independent binding is unresolved. The connected-block schedule, closed-Wilson coverage, cylindrical block map, exact-vacuum blocks and exact-block spectrum remain distinct finite constructions, each with its own receipt and evidence boundary.

## 1. Finite artifact inventory

| Construction | Primary evidence | Independent evidence | Current finite disposition |
|---|---|---|---|
| Connected blocks | `runs/yang_mills_connected_blocks/current-verification.json` — source-bound primary receipt, 79 checks | No separate raw-review or independent-reconciliation receipt is present in the current directory | Finite geometry and local operator controls pass; protocol-level analytical qualification and reconciliation remain unavailable |
| Closed-Wilson repeated-edge coverage | `runs/yang_mills_closed_wilson_repeated_edge_coverage/verification.json` — 41/41 controls, classification `REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE`, ranks $865,867,867,867$ | `verification-independent.json` — 24/24 arithmetic and source-binding checks | The finite coverage construction is incomplete at the smallest coupling; its stopping rule forbids another finite word extension in this campaign |
| Cylindrical block map | `runs/yang_mills_block_map_recovery_20260914/verification.json` — 53 checks | `verification-independent-repaired.json` — 9 aggregate independent reconstructions; `verification-independent.json` is retained as a failed diagnostic | The seeded path, electric, genuine-refinement, subdivision and scale controls pass; exact analytical adoption remains open |
| Exact-vacuum blocks | `runs/yang_mills_vacuum_blocks_recovery_20260914/verification.json` — 305 checks | `verification-independent.json` — 78 source, fixture, local-energy and Gaussian reconstruction checks | The fixed group, derivative, local-energy and Gaussian controls pass; exact-vacuum analytical adoption and continuum control remain open |
| Exact-block conditional spectrum | `runs/yang_mills_exact_block_spectrum/verification.json` — raw SHA-256 `e1ecf4d54d165dceb00a244de7b1c68b3a43dabb5dd345f63c8f846be9921147`; execution `PASS`, scientific classification `INCONCLUSIVE`; 20 Ritz rows, 180 scheduled boundary rows and zero qualified boundary rows | `verification-independent.json` — raw SHA-256 `f4a01fefe85ff195bd9d20e2c273291470a0c526d0b99b50812774184756558b`; 20 reconstructed rows and self-checks, with no source/protocol/primary hash fields | Local finite/cutoff execution record only. The analytical nodal control records a sign-changing projected Ritz density with amplitudes `2.094120531213694` and `-0.03437408376157869` and `unrestricted_conditional_gap: 0`; the verifier's `validation.passed` controls do not establish a positive conditional gap. The verifier does not compute the transport score, so no score or margin verdict is issued. The primary embeds source digest `148461e21a4ff1fe5601a44d3de6c4069bc9012fa1a56d912c01e1c12fc15723`, but no retained source snapshot matches it; the live working-tree source hashes to `8940ec3bad4b55611e7afba70b5f582bb685c59dc589578fbfdfb87e5382a168`. The independent file is arithmetic/self-check only, not a source-bound reconciliation; neither receipt supplies UFA32 or a uniform-gap result |

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
The exact-block pair is excluded from the accepted source-bound set. The primary records protocol digest `a2cf6db4c8a82d69982d2df3b9ebd5673c17705dd092969bb161d365a7285446` and helper digest `83f6ed011fa467ddfe6cd506f71a1168d85326741c115ae72b3cd90e507a4628`, but its embedded primary-source digest has no matching snapshot in the retained tree. The exact-spectrum run directory contains no manifest. The checked historical commit `d933c584` has verifier-source digest `d3caa296292ca99c7ba5b4100bc3b305025d5b4177b011ffe0190f935e20f44d`, which does not match the embedded `148461e21a4ff1fe5601a44d3de6c4069bc9012fa1a56d912c01e1c12fc15723` digest. The independent receipt contains only its schedule, rows and self-checks; it has no source, protocol or primary-receipt binding fields.

## 3. Evidence boundary

The connected-block result supplies a strong-coupling finite-depth control under its displayed theorem hypotheses. The repeated-edge campaign supplies a finite coverage result with a measured rank deficiency and an explicit stopping rule. The cylindrical block-map result measures leakage for a fixed bare refinement and distinguishes pure graph subdivision from genuine plaquette refinement. The exact-vacuum result checks finite group, derivative, local-energy and Gaussian block identities.

Each construction retains its own missing obligations for an interacting fibre, uniform resolvent estimate, thermodynamic limit, continuum field and regulator-independent mass. The artifact set supplies no Cassi microscopic identification.
The exact-block result is a finite diagnostic of a cutoff Ritz measure. Its numerical rows remain available for comparison, but the unresolved source snapshot and unbound independent output prevent treating the pair as sealed evidence for the Hamiltonian fibre or a uniform gap.

## 4. Continue

The finite receipts should be reused as fixed controls. The closed-Wilson repeated-edge campaign should remain stopped under its registered deficiency rule rather than extending the word family or changing the coupling schedule. The exact-block files should remain local audit artifacts: do not promote their finite Ritz rows to UFA32 evidence or start another finite run until the declared fibre, boundary-sector, metric, contour and uniform-constant proof objects are instantiated.

The next useful work is analytical reconciliation of the displayed block-map and exact-vacuum identities, followed by construction of a gauge-compatible interacting fibre or an equivalent Feshbach transfer operator. Any new receipt requires a protocol update only if it changes the graph trajectory, source family, cutoff order, constants or stopping rule.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.10–9.17—connected blocks, exact-vacuum blocks and cylindrical block map.
- `computations/yang-mills-connected-block-prereg.md`—connected-block schedule.
- `computations/yang-mills-closed-wilson-repeated-edge-coverage-prereg.md`—closed-Wilson stopping rule.
- `computations/yang-mills-vacuum-block-prereg.md`—exact-vacuum block schedule.
- `computations/yang-mills-block-map-prereg.md`—cylindrical block-map schedule.
- `computations/yang-mills-exact-block-spectral-prereg.md` and `field-experience/probe-outcome-ledger.md` §§27–30—exact-spectrum provenance qualification and unavailable dependent nodal/bowtie receipts.
- `field-experience/probe-outcome-ledger.md` §§16, 19 and 21—current evidence classifications.
