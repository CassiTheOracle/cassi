# CassiFI paper prototype

This directory is the self-contained **local implementation and evidence bundle** for [the technical paper](cassi-technical-paper.md). The CassiFI parent directory is available for post-prototype development; this tree keeps the paper implementation identifiable.

## Paper, implementation, and future work

- [The technical paper](cassi-technical-paper.md) is a mechanism-first explanation of continual learning, exact factual recall, uncertainty, internal transparency, nonverbal planning/revision, and efficiency. Preliminary measurements and reproduction details are in its appendices; named requirements define unresolved research and integration work.
- [`paper-version.json`](paper-version.json) is the v2 binding for the current paper, source closure, configuration, schemas, data/checkpoints, portable receipts, historical lineage, environment, and licensing status. It binds every inventoried byte by relative path, size, and SHA-256.
- [`IMPLEMENTATION-AND-PUBLICATION-PLAN.md`](IMPLEMENTATION-AND-PUBLICATION-PLAN.md) records the executed implementation/evaluation programme, its raw evidence, and the remaining publication blockers.
- Canonical provider ownership, crash-safe action handling, the deterministic end-to-end local loop, and evaluation reports are implemented in release `cassifi-implementation-portable-3`. System readiness remains `not_ready`: matched energy/FLOP instrumentation and the separately authorized authenticated FI–CassiCosmos adapter are absent.
- `artifacts/` and `_diag/` retain historical evidence. Existing receipts, reports, design inputs, and checkpoint bytes are not rewritten to hide old paths or hashes. `artifacts/portable-release/` contains the new release receipts and raw evaluation outputs.
- [`public-release-policy.json`](public-release-policy.json) and [`PUBLIC-RELEASE.md`](PUBLIC-RELEASE.md) define the fail-closed public-release boundary: no private corpora, trained checkpoints, raw historical evidence, upload, or publication action.

## Layout

| Path | Purpose |
|---|---|
| `cassi_*.py` | Field/controller/provider modules used by the paper implementation and its retained experiments |
| `run_*.py` | Bounded scenarios and paper result reproduction |
| `runtime/` | Terminal, native analytic-world, and provider-facing entry points |
| `training/` | Field-owned training entry points |
| `verification/`, `tests/` | Artifact reconstruction and focused behavioral checks |
| `configs/`, `schemas/` | Exact controller profiles and existing schema payloads |
| `data/corpora/` | Four locally retained corpus files, hash-bound but excluded from public distribution while redistribution rights are unresolved |
| `data/corpus-provenance.json` | Original locations, expected hashes, sizes, and unresolved redistribution status |
| `artifacts/`, `_diag/`, `designs/` | Retained checkpoints, receipts, raw measurements, and their documentary inputs |
| `evidence/external/` | Copied external receipt evidence cited by the paper; not an embedded Cosmos/Core runtime |

The flat Python module names are preserved. Entry points locate configuration and artifacts relative to this directory. Canonical geometry and transport helpers are here, not imported from `legacy/flow`. Retired, model-assisted, and unused experiments live outside this package in `../legacy/prototype/`; they are reference material, not supported launchers.

## Run from this directory

Use Python 3.12 with NumPy, PyTorch, and pytest installed. The canonical implementation evaluation runs CPU-only and does not require a Qwen model, CassiCore process, or Godot installation. Exact installed versions and environment variables for the relocation runs are retained with their receipts; this is not a cross-platform dependency lock.


Before running or comparing a copied bundle, verify its exact version:

```powershell
cd CassiFI/prototype  # from the Cassi workspace root
python verification/verify_paper_bundle.py
```

This checks every inventoried byte, the source-closure receipt, historical byte comparison, licensing fail-closed state, all eight evaluation statuses, clean-process reproduction, and the release digest chain. It rejects unversioned files, absolute paths in portable receipts, and manifest/receipt mismatches.
```powershell
python -m pytest tests -q
python run_general_task_gauntlet.py --phase full --output artifacts/portable-release/general-task-gauntlet.json
python run_grounded_counterflow_deliberation.py
python runtime/run_cassi_field_agent.py --help
python cassi_persistent_provider.py --help
```

The general-task gauntlet distinguishes successful diagnostics from system readiness. `diagnostic_checks_passed: true` does not imply `readiness_validated: true`; the expected retained readiness remains `not_ready`. `--require-ready` intentionally turns that missing readiness into a nonzero command result.

Some historical runners write their default artifact directory. For reproduction, use a distinct output directory wherever supported and capture stdout/stderr/exit status. Do not run a trainer's default output over the retained paper artifacts. Command-level reproduction details are in paper Appendix C.

## Portable corpus training and replay

The active manifest uses paths relative to `configs/cassi-qi-corpus-first-wave.json`. The loader checks each full-file SHA-256 before reading episodes. The old absolute-path manifest is preserved at `artifacts/historical-configs/cassi-qi-corpus-first-wave.json`.

Create a **new** lineage rather than overwriting a paper checkpoint:

```powershell
python training/train_cassi_field_language.py --manifest configs/cassi-qi-corpus-first-wave.json --config configs/cassi-qi-corpus-language.json --output-dir artifacts/portable-release/cassi-qi-corpus-language
python verification/verify_cassi_corpus_language.py --config configs/cassi-qi-corpus-language.json --artifact-dir artifacts/portable-release/cassi-qi-corpus-language --output artifacts/portable-release/cassi-qi-corpus-language/verification-receipt.json
```

New training receipts store paths relative to their artifact directory. To replay the unchanged historical receipt against the bundled sources, explicitly bind their portable manifest:

```powershell
python verification/verify_cassi_corpus_language.py --manifest configs/cassi-qi-corpus-first-wave.json --output artifacts/portable-release/historical-language-replay.json
```

The override must match the recorded source IDs, sizes, and hashes. It is not a missing-file fallback and cannot silently substitute a different corpus. Historical source/trainer hashes differ from current code; a successful historical replay establishes data/field reconstruction under the executed verifier, not an exact historical software build.

## Scope and evidence boundaries

The provider-owned canonical field now carries routing, transition, action-journal, and observation/consolidation state. Optional particle-program drafting, Qwen/model-assisted experiments, and the legacy learned world model remain outside canonical execution; absence of those paths is recorded by the implementation receipt.

CassiCore and CassiCosmos remain external integration applications, not hidden Python dependencies of this bundle. The local analytic world demonstrates the provider-owned lifecycle but does not establish live Cosmos execution. Gap 8 is therefore explicitly `not_ready` until the separately authorized authenticated adapter and windowed GPU receipt exist.

Natural-language failures, abstentions, bounded grammar/capacity, `NULL_NO_SYMBOL_CHANGE`, and `not_ready` remain part of the paper boundary. The implementation receipt measures the target-blind bounded grammar and its finite candidate space; it does not upgrade the paper's unrestricted language claims.

## Copying and publication

The local bundle may be copied for private reproduction, including Git-ignored `data/corpora/`, `artifacts/`, and `_diag/`. A Git checkout alone omits those payloads. `paper-version.json` inventories exact release bytes but is not a download mechanism.

The four source copies total 4,482,680,317 bytes. Their redistribution rights remain unresolved, so the public-release policy excludes their bytes and all trained or historical checkpoints. Source code is licensed under Apache-2.0; the manuscript and original figures are licensed under CC BY 4.0. No corpus was uploaded or published.

Build and verify the physically separate public-safe release with:

```powershell
python verification/public_release.py build --output ../cassifi-paper-public-1
python verification/public_release.py verify --root ../cassifi-paper-public-1
python verification/public_release.py smoke --root ../cassifi-paper-public-1
```

Version 0.1.0 is author-approved for external publication. The builder generates a fixed synthetic prompt/continuation fixture and verifies the corpus-free release; it does not itself upload, publish, accept legal terms, or alter the release policy.
