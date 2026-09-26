# Betelgeuse morphology comparison — preregistration

Status: PRE-REGISTERED before the first executable probe run — 2026-09-02

## Pre-analysis amendment 1 — fixed released-panel crop

The first two harness attempts stopped before `GATE INPUT_INTEGRITY` and before
any observational statistic: the implementation's largest-dark-component
locator first applied an unnecessary panel-size bound and then allowed B7's
black color-bar pixels to join the sky background. The released v2 panels are
all `1320 x 1020` pixels and share the printed sky-axis interior
`x = [174,1125), y = [7,958)`, exactly `951 x 951` pixels. This exact raster
dimension and crop are now frozen in place of automatic dark-pixel detection.
No beam, mask, statistic, threshold, null, or verdict rule changes.


## Question

Does the released, peer-reviewed 2023 ALMA image set establish (1) non-axisymmetric surface structure that persists across observing bands after matching angular resolution, and (2) enough independent resolved structure to support a Cassi-specific cellular/grid comparison?

This is an image-level observability probe. It cannot establish that a proton is a small star, that Betelgeuse contains a Cassi lattice, or that similar-looking colors imply common dynamics.

## Frozen primary inputs and provenance

The executable downloads the three version-2 Figure 1 panels from W. R. F. Dent et al., *ALMA high-resolution observations of Betelgeuse: Persistent structure spanning the inner atmosphere*, arXiv:2608.19339v2 (accepted by A&A):

- Band 6: `https://arxiv.org/html/2608.19339v2/Fig1a_BetelB6_SUR_v2.png`
- Band 7: `https://arxiv.org/html/2608.19339v2/Fig1b_BetelB7_SUR_v2.png`
- Band 8: `https://arxiv.org/html/2608.19339v2/Fig1c_BetelB8_SUR_v2.png`

The public outreach image supplied by the user is ESO image `potw2634a`, released 2026-08-24 and credited to ALMA (ESO/NAOJ/NRAO)/W. Dent et al. It is provenance context only; it is not a quantitative input because its color stretch and presentation processing are not the paper's common comparison surface.

The executable records the final URL, byte count, SHA-256 digest, raster dimensions, and retrieval UTC for every input. A failed download, non-image response, or changed panel geometry is `INCONCLUSIVE_INPUT` and stops analysis rather than silently changing the crop.

## Frozen observational facts

The paper gives restored synthesized beams:

| Band | Beam FWHM (mas) | Position angle |
|---|---:|---:|
| B6 | 19.6 x 14.1 | 47 deg |
| B7 | 10.7 x 9.5 | 19 deg |
| B8 | 7.7 x 6.6 | 2 deg |

The nominal optical stellar diameter is 42 mas, so the frozen disk radius is 21 mas. Independent Gaussian beam areas over that disk are computed as

`N_beam = pi R^2 / [pi major minor / (4 ln 2)]`.

This count is an upper bound on independent morphology elements in a rendered image, not a count of physical cells.

## Frozen raster extraction

1. Convert each RGB panel to linear luminance with the fixed sRGB transfer function and coefficients `(0.2126, 0.7152, 0.0722)`.
2. Require the released raster geometry `1320 x 1020` and extract the common printed sky-axis interior `x = [174,1125), y = [7,958)`, exactly `951 x 951` pixels. The panel maps linearly to `[-45,+45] mas` in both coordinates, as printed on Figure 1. Any geometry change stops as `INCONCLUSIVE_INPUT`.
3. Resample every extracted panel to a common `951 x 951` coordinate grid with bilinear interpolation. No centroid registration, rotation, feature alignment, or hand-selected crop is allowed.
4. The stellar disk is `r <= 21 mas`. Quantitative residual statistics use `r <= 18 mas` to exclude the steep limb. The beam marker, labels, axes, and color bar are therefore outside the analysis mask.
5. Normalize each band by its median luminance inside `r <= 18 mas`. Subtract a radial median profile in fixed 1 mas annuli. Standardize the resulting residual to zero mean and unit RMS inside the analysis mask.

The rendered color map is monotone but not calibrated brightness data. Consequently only normalized morphology is compared; no flux, temperature, or physical contrast is inferred from raster colors.

## Frozen resolution matching

B7 and B8 are convolved to the B6 restoring beam. Each restoring beam is represented by a two-dimensional Gaussian covariance from its major/minor FWHM and position angle. The additional convolution covariance is `C_B6 - C_source`; it must be positive semidefinite. Convolution is applied in Fourier space on the common angular grid. B6 is unchanged.

The implementation includes two unconditional synthetic checks before touching the downloaded morphology:

1. A centered radial Gaussian disk with `sigma = 12 mas` must produce residual RMS below `0.03` of its `r <= 18 mas` median after the same 1 mas radial-profile subtraction.
2. A synthetic B8 Gaussian point spread to B6 must have covariance eigenvalues within 5% of the direct B6 Gaussian covariance.

Failure is a harness failure, not an observational verdict.

## Frozen statistics

For the three beam-matched standardized residual maps:

1. `pair_correlation`: Pearson correlation for B6-B7, B6-B8, and B7-B8 inside `r <= 18 mas`.
2. `mean_pair_correlation`: arithmetic mean of those three values.
3. `positive_components`: eight-connected components above `+0.75 RMS`; discard components smaller than one quarter of a B6 beam area. Record count and component area in B6-beam units for each band.
4. `saturation_fraction`: fraction of disk pixels with any sRGB channel at least 254/255. More than 10% in any band makes raster morphology `INCONCLUSIVE_RASTER_SATURATION`.

The alignment control preserves every band's radial profile, power, beam, and component shapes while destroying shared sky orientation: rotate B7 and B8 residuals independently by all nonzero multiples of 30 degrees, producing 121 fixed pairs. Recompute `mean_pair_correlation` for each pair. The registered statistic is compared with the 95th percentile of this null distribution. No random seed or Monte Carlo stopping rule is involved.

## Frozen decision tree

### O1 — cross-band non-axisymmetry

- `SUPPORTS_RESOLUTION_STABLE_NONAXISYMMETRY` only if every pair correlation is at least `0.25`, the registered mean exceeds the alignment-null 95th percentile, all three bands retain at least one qualifying positive component, and raster saturation is acceptable.
- `DOES_NOT_SUPPORT_RESOLUTION_STABLE_NONAXISYMMETRY` if the inputs and harness are valid but any of those conditions fails.
- `INCONCLUSIVE_INPUT`, `INCONCLUSIVE_HARNESS`, or `INCONCLUSIVE_RASTER_SATURATION` as defined above.

This verdict tests shared large-scale structure, not circular cells or a mechanism.

### O2 — Cassi-specific cellular/grid comparison

A specific morphology comparison requires both:

- at least 20 independent beam areas in the common-resolution disk; and
- at least five qualifying components in each band, so a topology distribution rather than one or two hotspots is available.

If either condition fails, the frozen verdict is `INCONCLUSIVE_LOW_MORPHOLOGY_COUNT`. If both pass, the result is still `INCONCLUSIVE_NO_CASSI_FORWARD_MODEL` until a separately preregistered live Cassi field snapshot is projected through the same angular response and compared against generic Gaussian and cellular nulls. Visual similarity alone can never produce a positive Cassi-specific verdict.

### O3 — proton/star identity

Always `NOT_TESTED_BY_THIS_OBSERVATION`. A stellar atmosphere is a gravitational, radiative plasma; a proton is a quantum chromodynamic bound state. A cross-scale claim would require a dimensionless dynamical invariant from a specified scale-covariant action, not an outreach-image resemblance.

## Outputs and stopping rule

One deterministic run writes `_diag/stellar_cells/betelgeuse_morphology.json`, including provenance, frozen constants, self-checks, beam counts, all statistics, gate booleans, verdicts, and limitations. It prints one `GATE` line for input integrity, each self-check, resolution matching, raster suitability, and report writing, followed by the three verdicts. `ALL CHECKS PASSED` means only that the preregistered analysis executed correctly; it does not turn an inconclusive scientific outcome into support.

Stop after this one run. Do not alter crop detection, thresholds, angles, masks, beam parameters, or decision rules in response to the result. Any correction requires a dated amendment written before a rerun.
