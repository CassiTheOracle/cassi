# Analyses—Data Analyses of Observations Against the Framework

## Status: Index—August 2026

## Abstract

This directory collects documents whose substance is a **data analysis**: a real observational dataset (gravitational-wave catalogs, galaxy surveys, rotation curves) run against a specific framework claim, with the verdict recorded. Each document states the data provenance, the exact prediction or hypothesis tested, the epistemic tier of every claim it makes, and the script that reproduces the numbers. Reading order follows data availability: start with the largest, most decisive datasets. Analyses whose verdict is still open describe the decisive follow-up test explicitly.

The boundary with the rest of the repo: `speculations/` holds framework-consistent what-ifs with no data attached, `hypotheses/` holds pinned low-parameter predictions, and `experiments/` holds the scripts themselves—an analysis document lives here and points at its script there.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `gwtc4-mass-ladder.md` | Gravitational-wave masses | Speculative—August 2026 |

## Document Summaries

### `gwtc4-mass-ladder.md`—GWTC-4.0 and the Cascade Ladder: Black-Hole Masses as Rung Diagnostics

The fourth gravitational-wave transient catalog (218 events, more than double the first three runs) is mapped onto the cascade ladder through the framework's derived coherence-capacity relation $\boxed{N_{\text{BH}} = \log_\varphi(M/M_{\text{Pl}})}$ (`gravity/quantum-gravity.md` §7.4). The stellar-black-hole zone (rungs ~182–194) is unmapped territory between the rung-185 and rung-200 anchors; the LVK primary-mass peaks (10, ~20, 35 M$_\odot$) land at rungs 186.4/187.9/189.0 with 1.44/1.16-rung spacings—not an integer grid. A full-posterior search over all 173 catalog events (5.06M samples, O1–O4a) finds **no significant comb at the predicted period ln $\varphi$** ($\Delta\ln L = +1.9$ vs null median +12.8, p ≈ 1.0) and no periodicity at any period; a marginal rung-fraction excess (p ≈ 0.02) is the one feature to track with GWTC-5. The loudest event ever recorded (GW230814_230901, SNR 42.1) shows a statistically insignificant ringdown deviation, consistent with the framework's GR-exact prediction ($q \to 0$ at compact densities)—a binary falsifier if it survives. Reproduced by `experiments/gwtc4_mass_ladder/phi_mass_search.py` (figure `experiments/gwtc4_mass_ladder/phi_mass_figure.py`).

## Cross-References

- `speculations/README.md`—the what-if incubator (analyses used to live there)
- `experiments/gwtc4_mass_ladder/phi_mass_search.py`—the reproducing search (extract_samples.py, phi_mass_figure.py alongside; PNGs gitignored)
- `gravity/quantum-gravity.md` §7.4—the derived rung relation used by analysis 1
- `predictions/falsifiable-predictions.md`—the prediction catalog that analyses test
- `open-questions-cassi-answers.md`—the epistemic registry
