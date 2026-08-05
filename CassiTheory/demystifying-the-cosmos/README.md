# Demystifying the Cosmos—One Object per Document

## Status: Index—August 2026

## Abstract

This directory collects one analysis per observed object or structure, each read through the Cassi lens: what the observation says, which framework machinery maps onto it, where the object sits on the cascade ladder, and what falsifiable test the mapping enables. Files are named after the object's alphanumeric designation (PSR J1101−6101, and so on) so unnamed structures stay identifiable as we work through the catalog. Reading order: start wherever the most recent observation is, but the series is cumulative—later entries reuse the mappings established here (wake pair, coherence $q$, rung stratification).

The boundary with the rest of the repo: `analyses/` holds statistical data analyses against specific framework claims (verdicts recorded); this directory holds single-object explainers, tiered mappings rather than tests. Claims inside each document keep their source tiers (Derived machinery, Hypothesized applications), and each document ends with a falsifiable test and an explicit "what the framework cannot say" section.

## Document Index

| # | Document | Object | Epistemic |
|---|----------|--------|-----------|
| 1 | `PSR-J1101-6101.md` | Lighthouse pulsar (pulsar wind nebula, IXPE) | Hypothesized—August 2026 |

## Document Summaries

### `PSR-J1101-6101.md`—PSR J1101−6101: The Lighthouse Pulsar

The first object in the series: NASA's IXPE measured the X-ray polarization of the Lighthouse Nebula and found the filament's field aligned with the particle flow (>99% CL), a polarization degree higher than turbulent filament models allow, and a radio field nearly perpendicular to the trail where the X-ray field is parallel. The Cassi reading maps all three onto the two-fluid condensate: the pulsar is a spinning soliton (spin as SO(2) doublet winding, $s = \Delta n$), the bow shock and trail are the low-coherence wake of a moving coherent source, the filament is the coherent escape channel along the organized field, and the radio–X-ray divergence is energy stratification across cascade rungs—the field orientation winds one full turn per rung, $\boxed{\Theta(\nu) = \Theta_0 + (2\pi/\ln\varphi)\ln(\nu/\nu_0) \text{ (mod }\pi)}$. Closes with prediction 48: polarization angles should be log-periodic in photon energy, $\text{PA}(\nu\varphi^k) = \text{PA}(\nu)$, period $\ln\varphi \approx 0.4812$. Status: Hypothesized—August 2026.

## Cross-References

- `analyses/gwtc4-mass-ladder.md`—the rung map and the NS "no prediction" stance reused here
- `foundations/wake-geometry.md`—wake pair machinery (entry 1's core mapping)
- `foundations/spin-fibonacci-spiral.md`—SO(2) winding, spiral pitch, form-factor periodicity
- `predictions/falsifiable-predictions.md`—prediction 48 (log-periodic polarization orientation)
- `open-questions-cassi-answers.md`—the epistemic registry
- `experiments/demystifying_cosmos/pulsar_lighthouse_placements.py`—the reproducing placement script
