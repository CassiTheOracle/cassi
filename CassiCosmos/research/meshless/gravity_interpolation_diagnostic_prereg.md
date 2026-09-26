# Gravity interpolation failure-mechanism preregistration

Date frozen: 2026-08-31  
Status: frozen before diagnostic GPU acquisition or analysis  
Predecessor: `research/meshless/gravity_recovery_prereg.md`

## 1. Scope

This is a one-run explanatory diagnostic. It does not amend G67, register a
replacement force, or authorize a hybrid/FMM or production tree-walk change.

The exact G67 input named in the predecessor, SHA-256
`268900a2c13e5c3165e0f27e2466f5727d54d8d5571fb7cf77a13f1b26045e4d`, is no
longer present. The file currently at `_diag/meshless_gravity_gpu.json` has
SHA-256 `e8db9eed2fe0a69ccdd82e38b575dd42667af2f9e7548b2d37999dd47dd00ea7`.
Therefore G67 is unevaluable from the surviving artifacts; the new acquisition
must not be substituted into that frozen gate.

The current target-position walk also applies `srcorder[ps] == target_index`
self-exclusion. That identity is valid for a site target whose index is its
source ID, but not for an unrelated particle target. The diagnostic therefore
measures and neutralizes this accidental exclusion before interpreting
interpolation error. It does not change the legacy path.

## 2. Frozen acquisition

Run `res://scenes/verify_meshless_gravity.tscn` once, windowed, with its checked-
in scene parameters and no seed search or parameter change. Add a diagnostic-
only walk selector that still reads `tpos` but disables source-ID self-
exclusion; selector `1` must retain the legacy behavior bit-for-bit. From the
same first full tree, record:

- legacy particle gradients and interaction counts (selector `1`);
- corrected particle gradients and interaction counts (diagnostic selector);
- site gradients using selector `1`, where target index equals source ID;
- active `ncf` (`geometric_center.xyz`, `half`);
- active `nw` (`weight`, `center_of_mass.xyz`);
- active `nr` (`range_start`, `range_end`, `child_base`, `child_count`);
- complete `srcorder`, particle positions, and site positions.

Capture the tree arrays immediately after the full build and before any refit
probe. Write the diagnostic receipt only to the distinct path
`_diag/gravity_interpolation_diagnostic_gpu.json`; record its SHA-256 before
analysis. Never use it as the G67 input.

Stopping rule: exactly one successful acquisition. A shader/runtime failure or
an incomplete/non-finite receipt makes this diagnostic `INCONCLUSIVE`; do not
change the seed, opening angle, site count, or interpolation neighborhood.

## 3. Accidental-exclusion check

Compare legacy and corrected particle gradients with the corrected result as
reference. Report median, p99, and maximum relative error; opposite-direction
fraction; the fraction of bit-different gradient vectors; and interaction-count
differences.

The legacy particle reference is `LEGACY-SAFE` only if median relative error is
`<= 1e-6`, p99 `<= 1e-5`, maximum `<= 1e-4`, opposite-direction fraction is
zero, and all interaction counts match. Otherwise report `LEGACY-BIASED` and do
not use legacy particle gradients as physical evidence. All interpolation
statistics below use only the corrected particle reference regardless of this
verdict.

A production correction is outside this diagnostic. If `LEGACY-BIASED`, it
requires a separate frozen preregistration and default-off/bit-identity checks
before changing selector `1` or any engine caller.

## 4. Frozen reconstructions

Using only the diagnostic receipt, compare the corrected exact GPU tree
gradient at each particle with these three reconstructions from exact GPU tree
gradients sampled at sites:

1. nearest site;
2. inverse-distance weighting over the 16 nearest sites, using
   `1 / max(distance, 1e-12)` weights;
3. unconstrained affine least squares over the 16 nearest sites with columns
   `[1, dx, dy, dz]`.

No local-force correction, extra neighbor count, regularization, fitted
threshold, or alternative basis is allowed.

For each reconstruction report overall median and 99th-percentile relative
force error, opposite-direction fraction, and finite-output status. The force
floor is `|reference| > 1e-8`.

## 5. Frozen failure strata

### Distance to the owning Voronoi-cell boundary

For particle `p` with nearest site `o`, compute the exact Euclidean margin to
its closest owning-cell bisector:

$$
b(p)=\min_{j\ne o}
\frac{\lVert p-r_j\rVert^2-\lVert p-r_o\rVert^2}
{2\lVert r_j-r_o\rVert}.
$$

Report reconstruction error in quartiles of `b`, ordered from the smallest
margin (nearest a cell boundary) to the largest (deepest cell interior).

### Barnes–Hut accepted-node depth

Replay only the production traversal decisions on the recorded topology:

- `contains = all(abs(target - node_com) <= node_half)`;
- open a non-leaf when `node_half / max(separation, 1e-30) > theta` or
  `contains`;
- otherwise accept the node with no particle/source-index self-exclusion;
- derive node depth as
  `round(log2(root_half / node_half))`.

For every particle, sum accepted-node depths and divide by its accepted-node
count. The replayed count must equal the corrected GPU interaction count for
every particle. Any mismatch makes all depth-stratified results
`INCONCLUSIVE`.

Report reconstruction error in quartiles of mean accepted-node depth, ordered
from shallowest to deepest traversal.

## 6. Frozen interpretation

Use the affine reconstruction for the mechanism verdict; nearest and IDW are
controls.

- `BOUNDARY-DOMINATED` requires monotonically non-increasing affine median error
  from the nearest-boundary quartile to the deepest-interior quartile, and a
  nearest-boundary/deepest-interior median-error ratio `>= 2.0`.
- `DEPTH-DOMINATED` requires monotonically non-decreasing affine median error
  from the shallowest-depth quartile to the deepest-depth quartile, and a
  deepest/shallowest median-error ratio `>= 2.0`.
- If both conditions pass, report `MIXED: BOUNDARY + DEPTH`.
- If neither passes, report `UNRESOLVED`.

These labels explain the registered interpolation's failure distribution only.
They do not establish that exact site evaluation, a different interpolation,
or a higher-order local/FMM expansion is impossible. Any such mechanism needs
a separate frozen preregistration before implementation.
