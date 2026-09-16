# Native local Yang/Yin junction measurement

## Status: INCONCLUSIVE—no organized local intersection detected

The narrower hypothesis was tested directly: perhaps the field contains only a small piece of the proposed structure—one localized Yang/Yin current crossing—rather than a resolved double helix.

Across the six primary evolving arms and all **246** retained final-window frames, the measurement evaluated **7,465** independently selected joint-current neighborhoods. **None qualified as a local paired-current intersection.** Since no single frame contained a qualifying junction, there was no three-frame persistent track.

This does not strengthen the earlier result into a disproof. The parent native-resolution endpoint-gradient check remains failed at the two-neighbor site 512, so the formal physics verdict remains **INCONCLUSIVE**. Descriptively, however, the retained fields do not show the organized local two-channel structure proposed here.

## What “one intersection” means in this analysis

Two ideal helical strands wind around one another without intersecting. A single observed crossing could instead be:

- a projected crossing of two separate channels;
- a closest-approach region;
- a local paired-current junction; or
- a short fragment whose larger winding is unresolved.

The registered measurement tests the first three as local geometry. It does not label a crossing as a helix, infer material conversion, or identify the signed field amplitudes as separate material populations.

At each saved state, the analysis reconstructs native Yang and Yin **graph wave-energy currents**. Candidate centers are selected from simultaneous component-current intensity inside the initial particle radius. Selection uses the joint intensity only—it does not optimize the later crossing score. At most 32 spatially separated centers are retained per frame.

Within radius **2.5 site spacings** of each center, the two components are fitted independently. A junction requires both components to have:

- at least 8 effective current-bearing sites;
- line-like spatial covariance, principal/secondary ratio at least 1.5;
- current coherence at least 0.5;
- current-to-line alignment at least 0.7.

The fitted lines must cross at an angle of at least 30 degrees, approach within 0.75 site spacing, and reach that approach inside the fitted local segments. A persistent junction requires at least three consecutive saved frames with spatially and directionally matched component axes. Full criteria and stopping rules are frozen in [the specification](native_local_junction_spec.json) and [preregistration](native_local_junction_prereg.md).

## Results

| Arm | Frames | Candidate neighborhoods | Qualifying intersections | Longest qualifying track |
|---|---:|---:|---:|---:|
| R=12, seed 20260915 | 41 | 1,312 | 0 | 0 |
| R=9, seed 20260915 | 41 | 1,312 | 0 | 0 |
| R=6, seed 20260915 | 41 | 1,125 | 0 | 0 |
| R=12, seed 20260916 | 41 | 1,312 | 0 | 0 |
| R=9, seed 20260916 | 41 | 1,312 | 0 | 0 |
| R=6, seed 20260916 | 41 | 1,092 | 0 | 0 |
| **Total** | **246** | **7,465** | **0** | **0** |

Most joint-current neighborhoods were not close to a paired-channel classification:

| Failed condition | Candidate neighborhoods |
|---|---:|
| Yang current coherence below 0.5 | 7,409 |
| Yin current coherence below 0.5 | 7,432 |
| Yang channel linearity below 1.5 | 7,283 |
| Yin channel linearity below 1.5 | 7,300 |
| Yang current-to-axis alignment below 0.7 | 5,213 |
| Yin current-to-axis alignment below 0.7 | 5,166 |
| Component lines separated by less than 30 degrees | 2,571 |
| Closest approach outside the fitted local segments | 44 |

These conditions overlap; the counts are not mutually exclusive. No candidate failed only one condition. Two candidates failed exactly two conditions, 22 failed three, and all remaining candidates failed at least four.

### Strongest near-miss

The closest candidate to the registered class occurs in the R=6, seed 20260916 arm at **t=24.4**, centered on site 6000. Its fitted lines have:

- crossing angle **39.29 degrees**;
- closest approach **0.118 site spacing**;
- component-centroid separation **0.228 site spacing**;
- Yang linearity **1.612** and coherence **0.539**;
- Yin linearity **1.257** and coherence **0.159**.

It passes the geometric proximity, angle, support, Yang linearity, Yang coherence and alignment conditions. It fails because the Yin activity is neither sufficiently line-like nor directionally coherent. The mean component-current dot product is **+0.370**, so it is not an antiparallel Yang/Yin pair either.

This near-miss is best interpreted as overlapping local activity with one somewhat organized component, not two resolved current strands meeting at a junction. The conclusion follows the frozen thresholds; they were not adjusted around this case.

## Calibration

The detector passes both declared positive controls:

- an analytic orthogonal crossing of two Gaussian current tubes;
- the same crossing after a three-dimensional rotation.

It rejects all declared negative controls:

- parallel separated tubes;
- a single-component tube;
- isotropic radial counterflow;
- zero current.

The calibration therefore shows that the pipeline can recognize a compact intersection without requiring a global axis, half-turn, long helix, or preferred orientation.

## Independent verification

The independent verifier imports no local-junction detector. It reconstructs native final-state graph currents from raw fields and CSR topology, checks the generated witnesses, independently repeats final-frame candidate calculations, and rebuilds temporal track counts from all saved frame artifacts.

| Independent check | Comparisons or observations | Result |
|---|---:|---|
| Analytic calibration values | 2,443 | Agreement |
| Raw-derived final current witnesses | 491,538 scalar values | Agreement within 1e-10 absolute + relative tolerance |
| Final-frame candidate structures | 10,447 values | Agreement within 1e-10 absolute + relative tolerance |
| Temporal coverage | 246 frames | Complete |
| Candidate denominator/numerator | 7,465 / 0 | Reproduced |

A firing check copies an actual final-state witness and sets its Yin current vectors to zero. The independent candidate pool changes from 2,513 joint-current sites to zero, and evaluated centers change from 32 to zero. The original witness remains hash-identical. Thus the simultaneous-component gate is demonstrably active rather than reporting a vacuous zero.

The independent audit status is **PASS** for artifact and calculation reproduction. It does not override the parent numerical-quality failure or turn this result into a clean physics exclusion.

## Interpretation

The smaller hypothesis was worth testing because the previous global detector necessarily rejected a lone crossing. The local detector removes that assumption—and still finds no organized paired-current junction in the retained observations.

What the data do show is plentiful simultaneous Yang/Yin current activity. What they lack is the combination of local line structure and directional coherence needed to call that activity two strands. The dominant failure is not distance: fitted lines often pass close together. It is that one or both component-current neighborhoods are diffuse or internally canceling rather than behaving like coherent tubes.

Therefore the current evidence supports this bounded statement:

> No resolved macroscopic double helix and no calibrated local two-channel intersection are present in the retained native observations. Local Yang/Yin activity is predominantly diffuse at the registered 2.5-site-spacing scale.

The formal verdict remains **INCONCLUSIVE** because of the parent GPU/reference gradient discrepancy. This analysis also cannot exclude a sub-site feature, a structure between saved times, a curved/toroidal motif not locally line-like, or a material exchange mechanism absent from the native state variables.

The next clean step is unchanged: repair or eliminate the sparse two-neighbor gradient reconstruction, then repeat these frozen local and global measurements. Adding a crossing or winding force before that repeat would answer a different question by constructing the desired geometry.

## Artifacts

- [Measured local-junction analysis](../../_diag/native_local_junction_20260915/analysis.json)
- [Independent verification](../../_diag/native_local_junction_20260915/verification.json)
- [Parent counterflow measurement](../../_diag/native_counterflow_20260915/analysis.json)
- [Parent native campaign](../../_diag/native_sphere_20260915d/campaign.json)

To reproduce into a new output directory from the CassiCosmos repository root:

```text
python research/stellar_cells/native_local_junction_analyze.py --output _diag/native_local_junction_recheck
python research/stellar_cells/native_local_junction_verify.py --output _diag/native_local_junction_recheck
```

The retained result can be audited without regeneration using `python research/stellar_cells/native_local_junction_verify.py`.
