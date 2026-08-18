# Site-native reality renderer — pre-registration

Date: 2026-08-17
Status: frozen before implementation or measurement
Scope: first acceptance slice — GPU render-topology candidates and exact next-face equivalence

## 1. Question

Can the live 8,192-site moving-Voronoi field supply a compact GPU topology that reproduces the exact next Voronoi face along a ray, without projecting the field back onto the periodic raster grid?

This is the prerequisite for a site-native radiative-transfer renderer. The existing `cassi_volumetric.gdshader` remains the independent texture-raymarch reference; it is not the live architecture.

## 2. Frozen construction

### 2.1 Candidate graph

At every mesh rebuild, one GPU invocation per site scans the live site array and retains the `K = 32` nearest distinct sites by Euclidean distance. Candidate ordering is deterministic: ascending squared distance, then ascending site index for exact ties.

The output is a fixed-width `int candidate[n_sites * 32]` buffer plus `float candidate_d2[n_sites * 32]`. Slot `s*32+j` belongs to site `s`; absent slots are `-1/+INF`.

The first implementation is intentionally an all-site scan: `8192² = 67,108,864` simple distance evaluations per topology rebuild. It avoids an unverified spatial-hash truncation while measuring the real cost on the RX 7900 XTX. Optimization follows only after equivalence passes.

### 2.2 Exact reference for one ray segment

For current site `s`, ray `x(t) = ro + t rd`, `|rd| = 1`, and competitor site `j`, the equal-distance bisector is reached at

```
t_j = (|x0_j|² - |x0_s|²) / (2 rd·(x0_j - x0_s))
```

with `x0_k = site[k] - ro`. A candidate is forward only when the denominator is greater than `1e-7` and `t_j > t_current + eps_t`; `eps_t = max(1e-5, 2e-6 * max(1, |t_current|))`.

The next face is the valid competitor with the smallest `t_j`; ties within `eps_t` select the lowest site index. The full-reference result scans all sites. The runtime result scans the 32 candidates.

### 2.3 Domain

The first run exposed that `K = 32` is not sufficient for the frozen perturbed control: RT-2 produced one next-face mismatch (the full reference selected site 0 while the K=32 graph selected site 1). The candidate width was amended to `K = 64` with all other inputs and gates unchanged. The K=64 repeat produced RT-1 index mismatches = 0, RT-2 next-face mismatches = 0, and RT-3 next-t error = 0, but RT-1 squared-distance error remained `7.63e-6` against the frozen `2e-6` bound. Therefore fixed-K topology is **not adopted**. No live renderer wiring may consume this kernel until the distance oracle is made numerically equivalent without weakening the gate, or the fixed-K branch is replaced by an exact topology structure.

## 3. Frozen inputs

1. Perfect `2 × 16³` BCC lattice using the live site construction.
2. Bounded perturbation: every site displaced by a deterministic vector with magnitude `<= ML_MAX_DRIFT = 2.0`, seed `170817`.
3. Coherent shear: deterministic site displacement increasing linearly with x, capped at 2.0.
4. Degeneracy controls: duplicate-distance symmetry rays, face-grazing rays, rays beginning within `1e-5` of a bisector.

For each geometry, evaluate 16,384 deterministic `(site, ray direction)` cases. Directions use a fixed Fibonacci-sphere sequence. Origins lie inside the current site's local neighborhood: `site[s] + 0.1 * mean_candidate_spacing * dir_seed` and are rejected/replaced when a full all-site nearest scan says `s` is not the containing site.

## 4. Gates

All are mandatory.

- **RT-1 candidate identity:** GPU 32-nearest indices and squared distances equal the CPU brute-force KNN reference for every tested site. Index mismatches = 0; max relative d² error `<= 2e-6`.
- **RT-2 next-face equivalence:** candidate-scan next site equals the all-site brute-force next site in every non-tie case. Mismatches = 0.
- **RT-3 next-t equivalence:** max absolute `|t_candidate - t_full| <= 2e-5` for non-degenerate cases.
- **RT-4 progress:** every accepted segment has `t_next > t_current + eps_t`; zero-length/repeated transitions = 0.
- **RT-5 deterministic bytes:** two identical GPU topology builds are byte-identical.
- **RT-6 budget:** topology build GPU wall time `<= 8 ms` at 8,192 sites on the RX 7900 XTX. This is a cadence pass, not a per-frame pass.

## 5. Decision tree

1. Any RT-1, RT-4, or RT-5 failure → **REJECT** implementation and fix before further renderer work.
2. RT-2/RT-3 failure with the missing exact neighbor ranked 33–64 in the full KNN order → amend only by increasing frozen width to 64, rerun the entire gate, and disclose the amendment. No per-scene tuning.
3. RT-2/RT-3 failure with a missing neighbor ranked above 64 → **REJECT** fixed-K topology; move to a proven exact spatial structure before raymarch work.
4. RT-6 failure while RT-1–RT-5 pass → topology is correct but too slow; replace the all-site build with an exact spatial-hash/BVH construction and rerun byte-equivalence against this oracle.
5. RT-1–RT-6 pass → **ADOPT** the candidate topology and proceed to site-native ray traversal.

## 6. Non-claims

- This gate does not validate radiative transfer, palette, temporal accumulation, or particle-volume composition.
- This gate does not make the site PDE open-boundary.
- The K=32 result is not assumed exact before RT-2/RT-3 pass; the full all-site scan is the authority.
- Verification scripts and tolerances remain fixed after the first run.
