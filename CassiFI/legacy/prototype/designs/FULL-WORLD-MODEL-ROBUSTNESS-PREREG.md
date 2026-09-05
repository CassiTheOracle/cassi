# Full field-native world-model robustness preregistration

## Status: FROZEN BEFORE RUN—2026-08-22

## Purpose

Extend the completed single-seed benchmark with fixed multi-seed replication, a
matched generic recurrent control, and noisy partial-observation evaluation. The
original `FULL-WORLD-MODEL-BENCHMARK-PREREG.md` remains the primary performance
board; this is a separate robustness board and does not alter its verdict.

No real CassiCosmos trajectory archive is present in the workspace, so this board
uses deterministic synthetic trajectory families only and records that limitation.

## Frozen cases

- Family cases: `native` and `off-family`.
- Case seeds: `20260822`, `20260832`, `20260842`.
- Training seed for case `s`: `s + 1`.
- Evaluation seed for case `s`: `s + 2`.
- Episodes per case: `96`.
- Training episodes: `72`.
- Held-out episodes: `24`.
- Horizon: `32`.
- Observation/action/reward dimensions: `6/2/1`.
- Prefix for open-loop evaluation: `16` observed steps.
- Model configuration, modal profile, loss weights, optimizer, batch size, and
  gradient clip: identical to the frozen full-model benchmark.
- Full-model epochs: `30`.
- GRU control: deterministic one-layer GRU with hidden width `32`, trained for
  the same `30` epochs, batch size, optimizer, and episode split. Its parameter
  count is recorded rather than silently claimed to be equal.
- Noise board: clean-trained models evaluated with independent Gaussian noise
  `sigma=0.05` added only to the observed prefix; clean held-out targets remain
  the scoring target.
- No hyperparameter search, seed selection, early stopping, or retry after a
  failed case.

## Frozen metrics and gates

For each case/model, record teacher-forced observation MSE, clean open-loop
observation MSE, noisy-prefix open-loop observation MSE where applicable,
observation persistence baseline, reward MSE, continuation accuracy, parameter
count, training time, evaluation steps/second, peak device memory, finite flags,
and checkpoint round-trip difference.

1. **FAIL** if any case is missing, any metric/tensor is non-finite, any checkpoint
   round trip changes predictions by more than `1e-6`, or any case has a split,
   configuration, or digest mismatch.
2. For each family, the full model **SUPPORTS** clean replication if its median
   open-loop observation improvement over persistence is at least `5%` and its
   worst-case seed improvement is non-negative.
3. The GRU comparison is **SUPPORTS** when the full model's median clean
   open-loop observation MSE is no worse than the GRU median; otherwise it is
   `NULL` without invalidating the full-model board.
4. The noise board is **SUPPORTS** when the noisy-prefix full model remains at
   least `5%` better than persistence on the same noisy-prefix protocol; otherwise
   it is `NULL`.
5. Overall robustness is **SUPPORTS** only when all mechanical gates pass, both
   families support clean replication, the full model is no worse than the GRU
   on the frozen median comparison, and the noise board supports. Otherwise the
   honest verdict is `EMERGES`, `NULL`, or `FAIL` according to which gate fails.

## Evidence artifacts

The board writes:

- `full-world-model-robustness.json`;
- `FULL-WORLD-MODEL-ROBUSTNESS-REPORT.md`;
- per-case full-model and GRU checkpoints;
- per-case train/test dataset digests;
- preregistration and harness digests.
