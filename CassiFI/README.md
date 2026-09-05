# CassiFI

CassiFI develops field-owned intelligence: adaptive memory, inference,
deliberation, action, and learning remain explicit parts of persistent field
state. The canonical paths do not use a language model or a parallel learned
sidecar as a fallback.

## Active implementation

The bounded CPU/float64 implementation at this repository root contains:

| Path | Role |
|---|---|
| [`FIELD-INTELLIGENCE-DESIGN.md`](FIELD-INTELLIGENCE-DESIGN.md) | Mathematical and systems specification |
| [`cassi_field_atlas.py`](cassi_field_atlas.py) | Typed field atlas, evidence support, updates, inference, programs, and source retraction |
| [`cassi_field_cognition.py`](cassi_field_cognition.py) | Decision certificates, inquiry, structure selection, constructions, explanations, and plan repair |
| [`cassi_field_owner.py`](cassi_field_owner.py) | Single-owner persistence, immutable checkpoints, journals, authority, capacity, and exactly-once effects |
| [`cassi_variational_field.py`](cassi_variational_field.py) | Common variational learning and inference operator |
| [`run_field_intelligence_scenario.py`](run_field_intelligence_scenario.py) | Controlled-world learning, recall, planning, action, restart, and forgetting scenario |
| [`run_variational_field_scenario.py`](run_variational_field_scenario.py) | Numerical learning, inference, revision, intervention, and restart scenario |

Run the implemented paths from this directory:

```powershell
python run_field_intelligence_scenario.py --horizon-episodes 24
python -m unittest -v test_field_intelligence.py
python run_variational_field_scenario.py --output _diag/variational-field-math/scenario.json
python -m pytest test_variational_field.py -q
```

The scenarios are controlled reference environments. They do not establish
open-domain language acquisition, calibrated probability, causal
identifiability, GPU superiority, physical energy savings, or live
CassiCosmos operation.

## Technical paper and reproducibility bundle

[`prototype/`](prototype/README.md) contains the versioned technical paper,
its self-contained Python reference implementation, exact configuration,
tests, and reproducibility evidence:

- [`prototype/cassi-technical-paper.md`](prototype/cassi-technical-paper.md)
- [`prototype/paper-version.json`](prototype/paper-version.json)
- [`prototype/public-release-policy.json`](prototype/public-release-policy.json)

Large corpus inputs, checkpoints, diagnostics, and retained run artifacts are
local and Git-ignored. The version manifest binds their identities; the
distributable bundle excludes private corpora, trained checkpoints, and raw
historical evidence.

[`legacy/prototype/`](legacy/prototype/README.md) contains reference-only
experiments outside the active import closure.

## Repository boundaries

- Root modules and `prototype/` are independent implementations; neither is a
  fallback for the other.
- CassiCore and CassiCosmos are external integrations, not hidden Python
  dependencies.
- Generated files belong under `_diag/` or the declared artifact directories,
  not beside source modules.

Source code is licensed under Apache-2.0. The technical paper and its original
figure are licensed under CC BY 4.0; see `prototype/LICENSE-PAPER`.
