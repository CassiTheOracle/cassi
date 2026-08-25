# Demystifying the Cosmos—One Object per Document

## Status: Index—August 2026

## Abstract

This directory collects one analysis per observed object or structure, each read through the Cassi lens: what the observation says, which framework machinery maps onto it, where the object sits on the cascade ladder, and what object-level conditional check the mapping enables. Files are named after the object's alphanumeric designation (PSR J1101−6101, and so on) so unnamed structures stay identifiable as we work through the catalog. Reading order: start wherever the most recent observation is, but the series is cumulative—later entries reuse the mappings established here (wake pair, coherence $q$, rung stratification). The master map for the series is `unsolved-problems-in-astronomy.md`—the Wikipedia unsolved-problems list read through the framework, with a candidate-object roadmap for future entries.

The boundary with the rest of the repo: `analyses/` holds statistical data analyses against specific framework claims (verdicts recorded); this directory holds single-object explainers, not statistical tests. Claims inside each document keep their source tiers (Derived machinery, Hypothesized applications). Any falsifiable-test and "what the framework cannot say" sections here are object-specific conditional checks and limits, not framework-wide evidence or verdicts.

## Document Index

| # | Document | Object | Epistemic |
|---|----------|--------|-----------|
| 1 | `PSR-J1101-6101.md` | Lighthouse pulsar (pulsar wind nebula, IXPE) | Hypothesized—August 2026 |
| 2 | `NGC-5128.md` | Centaurus A (merger remnant, JWST MIRI/NIRCam) | Hypothesized—August 2026 |
|—| `unsolved-problems-in-astronomy.md` | The Wikipedia unsolved-problems list (master map + roadmap) | Reference—August 2026 |

## Document Summaries

### `PSR-J1101-6101.md`—PSR J1101−6101: The Lighthouse Pulsar

The first object in the series: NASA's IXPE measured the X-ray polarization of the Lighthouse Nebula and found the filament's field aligned with the particle flow (>99% CL), a polarization degree supporting lower turbulence than some models assume, and a radio field nearly perpendicular to the trail where the X-ray field is parallel. The Cassi reading is a Hypothesized, conditional mapping: the pulsar is modeled as a spinning soliton, while an added compact coordinate with a half-angle lift may *optionally* assign $s=\Delta n/2$ as a phenomenological spin label rather than a result of canonical real-density conversion. The bow shock and trail are mapped conditionally to the low-coherence wake of a moving coherent source, and the filament to a coherent escape channel. The physical mechanism remains open; the object-level P48 check is a null at face value.

### `NGC-5128.md`—NGC 5128 (Centaurus A): The Warped Parallelogram Galaxy

Webb's fourth-anniversary MIRI/NIRCam view of the nearest active merger remnant shows a warped parallelogram dust band across the center, an S-shaped ribbon structure, and a galaxy shaped by a 2-Gyr-old collision. The band's shape has a geometric resemblance to the cascade $r$-field of the string-bubble-cascade PDE (Panel E, with $r=E_Y/E_I$ pinned at $\varphi$ and wake rings at $\varphi$-scaled radii), but this resemblance is not a physical identification or evidence for a condensation field. The object-level conditional checks are $\varphi$-spaced radial wake rings ($r_{k+1}/r_k=\varphi$) and a boundary comparison using $R(\theta)=\frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta}{\theta}}$, which equals $1.7072\times$ only at the selected $\theta_{\mathrm{cond}}=0.45$ and varies with $\theta$; no $C=0.45$ edge survives the fixed-step PDE endpoint and the cosmological boundary receipt is null. Any edge comparison requires an independently identified dust-band boundary and remains a proxy mapping, not observational support or a universal, zero-parameter, canonical, or PDE output; status remains Hypothesized.

### `unsolved-problems-in-astronomy.md`—Unsolved Problems in Astronomy Through the Cassi Lens

The Wikipedia list of unsolved problems in astronomy, read through the framework: 68 problems across seven clusters, each tagged with one of four verdicts—**[Framework claim]**, **[Consistent mapping]**, **[Dissolved by construction]**, or **[No framework claim]**. Every tag traces to a repo document with its epistemic tier, and a tag never exceeds the tier of the document it cites. Most entries are [No framework claim]—the survey states plainly where the repo says nothing, adding a Speculative candidate direction only where the framework's machinery is genuinely shaped for one. A roadmap section lists candidate objects that would demystify each problem as a future entry.

## Cross-References

- `analyses/gwtc4-mass-ladder.md`—the rung map and the NS "no prediction" stance reused here
- `foundations/wake-geometry.md`—wake pair machinery (entry 1's core mapping)
- `foundations/spin-fibonacci-spiral.md`—SO(2) winding, spiral pitch, form-factor periodicity
- `predictions/falsifiable-predictions.md`—prediction 48 (log-periodic polarization orientation); predictions 38, 44 (entry 2's tests)
- `open-questions-cassi-answers.md`—the epistemic registry
- `visual-explainers/string_bubble_cascade.py`—the cascade r-field figure (entry 2's core resemblance)
- `experiments/demystifying_cosmos/pulsar_lighthouse_placements.py`—the reproducing placement script
- `experiments/demystifying_cosmos/ngc5128_placements.py`—NGC 5128 placements + the T1/T2 test helpers
