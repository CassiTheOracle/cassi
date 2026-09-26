# Spinor Closure Implementation Recovery

## Status: Implementation recovery record—September 2026

## Abstract

The registered spinor calculation has an independently verified receipt pair in the implementation-recovery directory. A preserved primary receipt and its source revision also identify an independent process that exits with a Python name-resolution error. The governing scientific preregistration §7 permits a recorded implementation repair in a new directory. This record identifies the verdict-label repair and descriptive bridge-docstring correction, with unchanged scientific definitions, inputs and decision rules. Both primary scientific payloads are exactly equal.

## 1. Preserved execution evidence

The governing scientific protocol is `computations/matter-formation-spinor-closure-prereg.md`. Its canonical SHA-256 is `5dbf22bd9f3c316f0b5b05a8945310c11b57a24fc77684efa0dd4f8a3ec8302d`.
Only this scientific preregistration is included in the receipts' protocol identity. The present recovery record supplies documentary provenance for the implementation defect and destination.

The source revision `60a766a2a17c706849ddac8b6c632ccec24a86ab` preserves the exact program and bridge source identities for the attempt in `runs/20260906_matter_formation_spinor_closure/`.

| Artifact or process | Recorded state |
|---|---|
| `results.json` | `numerical_pass: true`, empty failures; raw SHA-256 `ea4c48dbc8ed4910fa292d4c3fa78a7158e2152805abf15c5e19650795393ea0` |
| Independent process | Exit 1: `NameError: name 'VERDICTS' is not defined` in `assess_science`; no `verification.json` |
| Bridge initialization smoke | Exit 0 with `--test-init --grid 4`, `CUDA_VISIBLE_DEVICES=-1`, and UTF-8 output; four-component shape and unit norm printed |

The independent process reaches its evidence-assessment function after the payload-comparison loop. An exception without an independent receipt does not constitute scientific acceptance. The primary receipt remains preserved and is not overwritten.

## 2. Source changes

The verifier receives its supported verdict labels explicitly from the already-defined scientific payload. The change removes references to the undefined `VERDICTS` name, without changing a mathematical expression, input, threshold, row order or decision rule.

The bridge's `emergent_alpha` docstring states the implemented denominator regularizer and unweighted grid mean. Its executable method, the other helper methods, the displayed initialization outputs and all numerical inputs remain unchanged. This diagnostic has no established physical fine-structure interpretation.

Canonical source identities for the recovery are:

| Source | SHA-256, CRLF normalized to LF |
|---|---|
| `computations/matter_formation_spinor_closure.py` | `480d4f2df56ebf714910720fca6ff79a34d66cc66bcad79a8d936042054d239c` |
| `computations/verify_matter_formation_spinor_closure.py` | `41f187ebc4f004734944595b196124365c06c4ddd7887b9e57155bc8598e7984` |
| `two-fluid/cassi_dirac_bridge.py` | `845358c9d3d56a2d6c68732fcf7b5c037fe0cc23188ae5688886de2867cd1e1f` |
| `two-fluid/cassi_bridge_v2.py` | `b49bebc966b66307a47a8d52d52da3817cc6f9c6de9452a44219090a5ed3f2cd` |

## 3. Commands and destination

The primary command uses `--output-dir runs/20260906_matter_formation_spinor_closure_implementation_recovery`; the independent command supplies that same directory to both `--input-dir` and `--output-dir`. Both processes exit 0 with `numerical_pass: true` and empty failures. The independent receipt records 520 recursive comparisons and zero mismatches.

The two registered controls are retained under that directory: `control_missing_bridge/` for the primary with a nonexistent `--bridge-source`, and `control_missing_primary/` for the verifier with a nonexistent `--input-dir`. Both processes exit 1 and both receipts have empty scientific payloads.

The final bridge source has a separate successful initialization receipt at `bridge_initialization.json`, including its canonical source hash, command, environment, exit status and captured output. This repeats the initialization on the source identified in §2; its executable diagnostics and inputs are unchanged. The smoke establishes execution of the descriptive surface and supplies no physical fine-structure or field-production validation.

## 4. Acceptance and retained boundary

The primary scientific fields `constants`, `operators`, `phase_witnesses`, `positive_energy_witnesses`, `fixed_stationary`, `gated_stationary` and `verdicts` equal their preserved counterparts exactly. Their source-identity metadata records the declared implementation changes.

Both recovery receipts satisfy the governing numerical criteria. Their raw SHA-256 values are `2fe4e3d8783c3efaf8f9dcc91cb0491b528a0a35fa7f454d787b3d63939902e9` (primary) and `34cb48325e86d904093c86ba7e00c311021bfd0f32e0b625d488065cc91fdf5c` (independent). These are conditional finite-dimensional witnesses; physical reservoir, Fock-space and matter-production identifications remain open. The stopping rule in the scientific preregistration remains in force.

## References

- `computations/matter-formation-spinor-closure-prereg.md`—scientific definitions and frozen decision tree.
- `computations/matter_formation_spinor_closure.py`—four-component primary witness program.
- `computations/verify_matter_formation_spinor_closure.py`—independent reconstruction and evidence assessment.
- `two-fluid/cassi_dirac_bridge.py`—component diagnostics and initialization surface.
- `computations/matter-formation-continuum-report.md`—integrated evidence and scope.
