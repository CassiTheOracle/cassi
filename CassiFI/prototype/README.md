# CassiFI reference implementation

This directory contains the versioned reference implementation and evidence
for [Cassi Field Intelligence: Persistent Learning, Exact Evidence, and
Transparent Nonverbal Deliberation](cassi-technical-paper.md).

## Contents

| Path | Purpose |
|---|---|
| `cassi-technical-paper.md`, `cassi-technical-paper.pdf` | Technical paper |
| `cassi_*.py` | Field, controller, provider, language, memory, and world modules |
| `run_*.py` | Bounded scenarios and result reproduction |
| `runtime/` | Terminal, analytic-world, and provider-facing entry points |
| `training/` | Field-owned training entry points |
| `verification/`, `tests/` | Bundle verification and behavioral checks |
| `configs/`, `schemas/` | Fixed controller profiles and payload schemas |
| `paper-version.json` | Exact file, byte, SHA-256, dependency, receipt, and license inventory |
| `artifacts/portable-release/` | Canonical evaluation, reproduction, licensing, and digest receipts |
| `data/corpus-provenance.json` | Local corpus identities and redistribution status |
| `public-release-policy.json` | Fail-closed exclusion rules for a distributable corpus-free bundle |
| `designs/` | Retained design and evaluation records referenced by source or receipts |

The flat Python module names are intentional. Entry points resolve
configuration and artifacts relative to this directory. Retired and
model-assisted experiments are isolated under `../legacy/prototype/` and are
never imported by the active implementation.

## Verify and run

Use Python 3.12 with NumPy, PyTorch, and pytest installed. The exact verifier
requires the owner-local retained artifact tree, including corpus-bound evidence
and state receipts; it cannot run from a source-only clone. Run it only when
that local tree is present:

```powershell
cd CassiFI/prototype
python verification/verify_paper_bundle.py
```

A source-only clone can inspect the implementation and run the focused
surfaces below, but cannot establish the private local evidence lineage.

Run the focused implementation surfaces:

```powershell
python -m pytest tests -q
python run_general_task_gauntlet.py --phase full --output artifacts/portable-release/general-task-gauntlet.json
python run_grounded_counterflow_deliberation.py
python runtime/run_cassi_field_agent.py --help
python cassi_persistent_provider.py --help
```

The provider owns routing, transition, action-journal, counterflow, and
observation/consolidation state in one checkpoint lineage. The retained local
scenario exercises teaching, recall, planning, authorization, execution,
observation, correction, restart, causal lesions, and crash reconciliation
without model calls or adaptive sidecars.

The reference evaluation does not contain matched energy/FLOP telemetry or an
authenticated live CassiFI–CassiCosmos run. CassiCore and CassiCosmos remain
external applications rather than embedded dependencies.

## Corpus training and replay

Every configured corpus is checked against its full-file SHA-256 before use.
Create a new output lineage rather than overwriting a retained checkpoint:

```powershell
python training/train_cassi_field_language.py --manifest configs/cassi-qi-corpus-first-wave.json --config configs/cassi-qi-corpus-language.json --output-dir artifacts/portable-release/cassi-qi-corpus-language
python verification/verify_cassi_corpus_language.py --config configs/cassi-qi-corpus-language.json --artifact-dir artifacts/portable-release/cassi-qi-corpus-language --output artifacts/portable-release/cassi-qi-corpus-language/verification-receipt.json
```

Replay the retained corpus receipt against the locally bound sources with:

```powershell
python verification/verify_cassi_corpus_language.py --manifest configs/cassi-qi-corpus-first-wave.json --output artifacts/portable-release/historical-language-replay.json
```

The override must match every recorded source identity, size, and hash.

## Distribution boundary

The four local corpus files and all trained or historical checkpoints are
excluded from the distributable bundle because redistribution rights are not
established. The builder also excludes raw historical evidence, diagnostics,
caches, archived experiments, and private paths.

Build, verify, and smoke the corpus-free bundle from this directory:

```powershell
python verification/public_release.py build --output ../cassifi-paper-public-1
python verification/public_release.py verify --root ../cassifi-paper-public-1
python verification/public_release.py smoke --root ../cassifi-paper-public-1
```

The generated bundle contains the paper, implementation source, fixed
configuration and schemas, one synthetic exchange fixture, exact inventories,
and bounded evaluation summaries. Source code and metadata are licensed under
Apache-2.0. The paper and original figure are licensed under CC BY 4.0.
