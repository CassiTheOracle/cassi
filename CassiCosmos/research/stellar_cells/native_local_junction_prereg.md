# Native local Yang/Yin junction measurement

## Status: Analysis specification frozen before local-junction outcomes—2026-09-15

The previous registered measurement found no resolved macroscopic double helix. This analysis tests the narrower suggestion that the observable may be only a small local piece: one crossing, closest-approach region, or paired-current junction. It reuses the retained native-sphere fields and the already derived native graph wave-energy currents. It introduces no force, phase, topology, material species, GPU run or production change.

A geometrical intersection is not itself a double helix. Two ideal helical strands do not intersect. This measurement can support a localized paired-current motif, but it cannot establish a helix, material conversion, or an expansive/contractive species identity.

The machine-readable criteria are frozen in `native_local_junction_spec.json`. Six primary evolving arms are measured over all 41 saved states from code time 24 through 32. The parent raw data and counterflow analysis are SHA-bound and read-only. Output goes to `res://_diag/native_local_junction_20260915`.

## Candidate construction

At every saved frame, calculate the native Yang and Yin graph-current vectors from the reciprocal bond powers. Restrict candidate centers to sites inside the initial particle radius R about the instantaneous particle mass COM. For each component define current intensity w=V|J|. Rank sites by the geometric mean of the two component intensities after separately normalizing each by its within-sphere maximum. Require joint score at least 0.05, retain at most 32 ranked centers, and apply deterministic nonmaximum suppression at distance 2h. This selection exposes attempted counts and never chooses a center by its eventual line-fit score.

For each retained center, use all sites within 2.5h. Require at least 12 sites. Separately fit the Yang and Yin current channels using the intensity-weighted position covariance. Each component must have effective sample count at least 8 and principal-to-secondary covariance ratio at least 1.5. Its intensity-weighted mean current must have directional coherence at least 0.5 and absolute alignment at least 0.7 with its fitted line.

Treat fitted lines as unoriented geometry. A local crossing candidate requires an acute angle of at least 30 degrees between them, closest line-to-line approach no greater than 0.75h, closest points no farther than 2.5h along either line from the fitted centroids, and component-centroid distance no greater than 2.5h. Record the signed mean-current dot product and whether currents are converging, diverging, transverse or opposed as diagnostics; do not redefine a geometrical crossing according to a preferred Yang/Yin role.

A persistent junction requires a qualifying candidate in at least three consecutive saved frames. Match only candidates whose centers move by at most 2h and whose component axes agree with absolute cosine at least cos(30 degrees). Candidate matching never swaps Yang and Yin identities. When multiple successors qualify, take the nearest then lexicographically smallest site id. Retain all candidates so this deterministic track selection cannot hide alternatives.

## Calibration and controls

Before science classification, exercise the exact detector on analytic orthogonal Gaussian current tubes, the same crossing under a three-dimensional rotation, parallel separated tubes, a single-component tube, isotropic radial counterflow and zero current. Only the two crossing cases should pass. These fixtures demonstrate detector behavior; they are not evidence that the native PDE forms a junction.

The frozen-field parent arms remain zero-current controls from the previous measurement. This local analysis measures only the six evolving primary arms because zero-current rejection is covered analytically and already established exactly on every frozen native frame.

## Verification and stopping

An independent verifier must not import the local detector. It reloads final-window current witnesses or raw fields, reconstructs candidate selection and at least the strongest candidate's component statistics for every arm, checks all artifact hashes and denominators, and verifies track counts. It must also mutate one actual candidate statistic or current vector in a copied artifact so a qualifying predicate is shown to fire. Original artifacts remain unchanged.

The native-resolution endpoint condition from the parent measurement remains binding. The 8,192-site arms contain a two-neighbor gradient reconstruction failure at site 512. A detected persistent junction is therefore a measured candidate requiring later confirmation after that defect is repaired; a nondetection remains formally INCONCLUSIVE rather than a clean absence verdict. No dense GPU run is triggered by a local descriptive candidate in this analysis.

The stopping rule is one pass over the six registered arms and 246 saved observations. Do not scan neighborhood radii, score floors, crossing angles or persistence lengths after seeing outcomes. Report candidate counts, strongest near-misses, persistence lengths, calibration behavior, numerical-quality boundary and the distinction between a local crossing and a helix.
