# Kepler/TESS Period-Ratio Audit Report

## Status: Hypothesized—August 2026

## Abstract

The registered Prediction 54 window test was executed on an explicitly confirmed NASA Exoplanet Archive sample. The primary Kepler sample contains 476 multi-planet systems, 1,212 planets, 736 adjacent period ratios, and 562 ratios inside the fixed support $[1,3]$. The headline interval around $\varphi^{3/2}=2.058171$ contains 46 ratios and has descriptive folded-window score $z_{\rm win}=1.087$, so the registered classifier returns **INDETERMINATE**. The K2/TESS cross-check has $z_{\rm win}=2.120$, but it is secondary and the score is not a sampling significance. The target interval overlaps the registered 2:1 interval across $41.8\%$ of its width and occupies the known excess immediately wide of the 2:1 mean-motion resonance. The catalog therefore supplies no mechanism-specific evidence for a $\varphi$ field signal. The scientific verdict is **INCONCLUSIVE** for Cassi, and the current broad window is rejected as a clean discriminator from standard orbital dynamics.

## 1. Data and execution receipt

The acquisition uses the NASA Exoplanet Archive Planetary Systems (`ps`) TAP table. Candidate solutions occur in this table, so every query requires

```text
soltype='Published Confirmed' and default_flag=1
```

The raw response includes `soltype`, `default_flag`, `discoverymethod`, and `disc_facility`; the parser fail-closes unless every row satisfies the full sample predicate and exact facility label.

**Acquisition script:** `experiments/kepler_phi_ratios/acquire_kepler_catalog.py`  
**Analysis script:** `experiments/kepler_phi_ratios/run_phi_ratios.py`  
**TAP endpoint:** `https://exoplanetarchive.ipac.caltech.edu/TAP/sync`  
**Fetch time:** `2026-08-25T13:00:05Z`  
**Analysis receipt:** `data/runs/20260825_132506_phi_ratios.json` (SHA-256 `617a71d5eabe10511a7d640bf46bc192edac9e2062115eb09cc506319322432a`) in the local gitignored run directory

| sample | facility predicate | raw bytes SHA-256 |
|---|---|---|
| Kepler primary | `disc_facility='Kepler' and discoverymethod='Transit'` | `0da130b0641ac369d26fa2751b5ed544eefcb405d8d538d0370b2feb72255aae` |
| K2/TESS cross-check | `disc_facility in ('K2', 'Transiting Exoplanet Survey Satellite (TESS)') and discoverymethod='Transit'` | `61c240a20500e79942a4828f84a12cc3608e9a4c4af9be876f73f08e768b959a` |

The primary query returns 1,212 planets in 476 hosts. Ordering each host by orbital period gives 736 adjacent ratios; 562 lie in the registered support $1\leq P_{\rm out}/P_{\rm in}\leq3$. The planet multiplicities are 298 two-planet, 119 three-planet, 41 four-planet, 15 five-planet, two six-planet, and one eight-planet system.

The cross-check contains 489 planets in 201 hosts, 288 adjacent ratios in total, and 207 inside $[1,3]$.

## 2. Registered descriptive classifier

For a target window $W$ of half-width $h=0.05$, the script counts

$$
N(W)=\sum_i \mathbf 1\!\left(r_i\in W\right),
\qquad r_i=\frac{P_{{\rm out},i}}{P_{{\rm in},i}}.
$$

It then places equal-width windows at 40,001 seeded centers across $[1,3]$. If $E_{\rm win}$ and $s_{\rm win}$ are the mean and standard deviation of those window counts, the registered score is

$$
z_{\rm win}(W)=\frac{N(W)-E_{\rm win}}{s_{\rm win}}.
$$

This score compares one location in the observed histogram with generic locations in the same histogram. The registered center sweep includes truncated windows at the edges of $[1,3]$, so it is a design-specific descriptive reference rather than a translation-homogeneous null. It is not generated from repeated catalogs and does not provide a frequentist significance or a mechanism-specific likelihood ratio. The 562 in-support ratios come from 361 hosts; 137 hosts contribute more than one ratio, with a maximum of six, so pairwise independence does not hold.

For the Kepler sample,

$$
E_{\rm win}=28.1995,
\qquad
s_{\rm win}=16.3697.
$$

The registered formal rule returns **SUPPORTS** when the headline score reaches 2 while all non-Fibonacci controls remain below 2, **SUPPORTS NULL** when a control reaches 2 while the headline does not, and **INDETERMINATE** otherwise.

## 3. Primary Kepler result

| window | interval | count | $z_{\rm win}$ | role |
|---|---:|---:|---:|---|
| $\varphi^{3/2}$ | $[2.008171,2.108171]$ | 46 | $1.087$ | headline |
| $\varphi$ belt | $[1.568034,1.668034]$ | 43 | $0.904$ | secondary |
| 3:2 | $[1.45,1.55]$ | 67 | $2.370$ | Fibonacci / standard MMR |
| 2:1 | $[1.95,2.05]$ | 31 | $0.171$ | Fibonacci / standard MMR |
| 4:3 | $[1.283333,1.383333]$ | 23 | $-0.318$ | control |
| 7:3 | $[2.283333,2.383333]$ | 23 | $-0.318$ | control |
| 5:2 | $[2.45,2.55]$ | 21 | $-0.440$ | control |

The formal classifier result is

$$
\boxed{\text{INDETERMINATE: }z_{\rm win}(\varphi^{3/2})=1.087<2.}
$$

The elevated 3:2 window is a standard mean-motion resonance and cannot identify a $\varphi$ mechanism. The $\varphi$ belt itself is not elevated under the descriptive classifier.

## 4. K2/TESS cross-check

The K2/TESS window reference has $E_{\rm win}=10.3546$ and $s_{\rm win}=7.3790$.

| window | count | $z_{\rm win}$ |
|---|---:|---:|
| $\varphi^{3/2}$ | 26 | $2.120$ |
| $\varphi$ belt | 14 | $0.494$ |
| 3:2 | 28 | $2.391$ |
| 2:1 | 24 | $1.849$ |
| maximum non-Fibonacci control | 11 | $0.087$ |

This cross-check is outside the primary verdict. Its $2.120$ value is a descriptive score rather than a $2.12\sigma$ detection. The simultaneous elevation near 3:2 and 2:1 is consistent with ordinary resonant structure.

## 5. The 2:1 confound

The headline window has width $0.1$ and intersects the registered 2:1 window over

$$
[2.008171,2.05],
$$

which is $41.829\%$ of its width. In the primary sample, 23 of the 46 headline-window ratios lie in that explicit overlap and 23 lie above 2.05. In the cross-check, 17 of 26 lie in the overlap and nine lie above 2.05.

The boundary at 2.05 does not remove the physical confound. Kepler systems have a documented deficit immediately narrow of first-order resonances and an excess immediately wide of them. Fabrycky et al. report this asymmetry near 2:1 and 3:2, and Lithwick and Wu derive how eccentricity damping can move near-resonant pairs to the wide side. The value $\varphi^{3/2}=2.058171$ lies directly in that conventional comparison region.

The current control set does not resolve this degeneracy. The 4:3, 7:3, and 5:2 windows have different resonance orders and selection properties from the first-order 2:1 neighborhood. A target excess near 2.058 with quiet distant controls would remain compatible with standard near-resonant dynamics.

## 6. Secondary diagnostics

A conditional per-system log-uniform reshuffle fixes each system's observed inner and outer periods and randomizes only its interior periods. Across 1,000 realizations (seed 7), it gives headline-window count $25.078\pm3.502$, placing the observed count at standardized offset $5.975$. All 298 two-planet systems are unchanged because their multiplicity and span leave no interior degree of freedom; 12 of the 46 observed headline ratios are therefore present in every realization. This statistic diagnoses interior-spacing structure conditional on observed endpoints. It is not a generative orbital null and does not identify a $\varphi$ mechanism.

The synthetic-injection classifier sensitivity is:

| injected fraction | SUPPORTS fraction |
|---:|---:|
| 0.02 | 0.00 |
| 0.04 | 0.23 |
| 0.06 | 0.99 |
| 0.08 | 1.00 |
| 0.10 | 1.00 |
| 0.15 | 1.00 |
| 0.20 | 1.00 |

Each realization recomputes the folded-window reference at its injected sample size. The receipt records 200 realizations per amplitude, log-space scatter $0.02$, and RNG seed 20260813. These numbers characterize one artificial log-normal injection family centered on 2.058; they are not detection power against a physical orbital-dynamics model.

## 7. Verdict

| gate | result |
|---|---|
| explicit archive-confirmation predicate | PASS |
| one fixed ratio support for sample and window reference | PASS |
| corrected system multiplicities and size-matched injection calculation | PASS |
| registered primary classifier | **INDETERMINATE** |
| sampling significance | NOT ESTABLISHED |
| separation from standard 2:1 dynamics | FAIL |
| Cassi mechanism inference | **INCONCLUSIVE** |

The catalog does not support a Cassi field effect. It also does not falsify a disk-stage $\varphi$ template, because no derived transfer law maps that template into the mature detached-orbit distribution. Under the channel principle in `foundations/qi-as-spatial-spacing-signal.md` §4, disk gas is the more direct observable; detached planetary orbits require a specified preservation mechanism.

A discriminating period-ratio test would need a frozen conventional baseline that models first-order resonances, the wide-of-resonance asymmetry, catalog selection, and within-system dependence. It would compare an independently specified $\varphi$ component against that baseline with a likelihood or posterior predictive statistic. A Cassi-specific amplitude, width, and disk-to-orbit transfer law are required before such a component is defined.

## References

- `hypotheses/exoplanet-phi-spacing.md` §8—Prediction 54 design and present verdict.
- `predictions/falsifiable-predictions.md`—Prediction 54 registry entry.
- `foundations/qi-as-spatial-spacing-signal.md` §4—coherence-coupled versus detached matter channels.
- NASA Exoplanet Archive, Planetary Systems (`ps`) table and TAP service: `https://exoplanetarchive.ipac.caltech.edu/docs/planetarysystems_about.html`.
- Fabrycky et al., *Architecture of Kepler's Multi-transiting Systems: II*, arXiv:1202.6328—observed excess wide of first-order resonances.
- Lithwick and Wu, *Resonant Repulsion of Kepler Planet Pairs*, arXiv:1204.2555—eccentricity-damping mechanism for wide-of-resonance excesses.
- Steffen and Hwang, *The Period Ratio Distribution of Kepler's Candidate Multiplanet Systems*, arXiv:1409.3320—catalog-scale period-ratio structure and Monte Carlo analysis.
