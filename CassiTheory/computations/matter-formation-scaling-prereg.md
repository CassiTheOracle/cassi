# Prepared-Carrier Lump Scaling: Descriptive Analysis

## Status: Derived conditional analysis specification—September 2026

## Abstract

This analysis summarizes immutable endpoints from the completed radial density-trap campaign. Their energies and radii are already observed. It is a post-campaign descriptive calculation, with no new physical gate, parameter scan, optimization, charge, or inference of real-time formation. The per-charge and stability verdicts remain unchanged.

## 1. Fixed inputs

Read `runs/20260906_matter_formation_radial/results.json`, raw SHA-256 `3ac6ec265c11d8eed2040c372d8862084be084ad0a640bbe0d8655e06e19a313`. Each raw NPZ must match the hash in that receipt. Use the four `q{4,16,64,256}_R12_n768_refine` endpoints for the charge table. Use the `R12_n384_refine` and `R24_n768_refine` endpoints at prepared populations 4, 16 and 256 for same-spacing domain comparisons. The stopped population-64 endpoint remains unqualified and is labeled as such in every output.

## 2. Descriptive statistics

For every selected endpoint, report the existing energy, multiplier, qualification and bound status; compute population and RMS radius directly from `r`, `volumes` and `c`; report minimum mediator amplitude, maximum carrier density, energy per prepared population, and radius divided by the cube root of population. Require direct population and radius to agree with the receipt under denominator `max(1, abs(a), abs(b))` at tolerance `1e-9`. This is an artifact identity check, not a physical acceptance criterion.

For the homogeneous depleted profile, distinguish two variations of

$$
V(0,n)=\frac{u_\rho}{4}+(e_C-h_C)n+\frac{u_C}{2}n^2.
$$

Minimizing energy density over $n$ gives $n_*=(h_C-e_C)/u_C$. Minimizing the bulk energy per carrier $V/n$ gives $n_{\rm sat}=\sqrt{u_\rho/(2u_C)}$ and $e_{\rm sat}=e_C-h_C+\sqrt{u_\rho u_C/2}$. Report both, the corresponding energy density, derivative at $n_*$, and pressure $u_Cn_{\rm sat}^2/2-u_\rho/4$. Gradients and interfaces are excluded from these homogeneous formulas.

At total prepared population 256, compare the qualified single-lump energy with the trial energy of sixteen mutually separated population-16 lumps, using a common exterior energy reference and neglecting interactions at infinite separation. This tests only that partition's energetic ordering within the selected scalar model. Population 8 is absent, so there is no population-16 two-lump fission calculation. The population-4 box states are diffuse and must not be counted as localized fragments.

## 3. Scope and stopping

Execute `computations/matter_formation_scaling.py` once after source settlement, writing a new `runs/20260906_matter_formation_scaling/` directory. Record source, specification and input hashes. Stop on any identity failure; do not relax fields or change thresholds. No output changes a frozen scientific verdict.

The measured charge dependence may be described as consistent with condensate-like droplets. It cannot establish a universal monotone law, an asymptotic exponent, a preferred particle size, stability against every partition, a dynamical merger, or a physical quantum-number assignment. A negative energy relative to the selected exterior reference is not an absolute mass measurement.

## References

- `computations/matter-formation-continuum-prereg.md`—frozen parent campaign.
- `computations/matter-formation-continuum-report.md`—stationary and constrained spatial evidence.
- `foundations/particle-stationary-action-closure.md` §8.7—scalar functional and empty-sector invariant.
