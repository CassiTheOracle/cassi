# Betelgeuse color-map endpoint check — preregistration

Status: PRE-REGISTERED after the v1 raster verdict and before this successor run — 2026-09-02

## Parent result retained

The frozen parent campaign is `betelgeuse_morphology_prereg.md`; its receipt is `_diag/stellar_cells/betelgeuse_morphology.json`. It returned:

- O1 `INCONCLUSIVE_RASTER_SATURATION` because 90.7–96.3% of disk pixels had **any** sRGB channel at least 254/255;
- O2 `INCONCLUSIVE_LOW_MORPHOLOGY_COUNT`;
- O3 `NOT_TESTED_BY_THIS_OBSERVATION`.

That result is not replaced or relabeled. The parent statistic did exactly what it specified. It is scientifically unsuitable as a clipping sentinel for the paper's `hot` false-color map because red intentionally reaches 255 throughout ordinary in-range orange values.

## Successor question

Does the released raster reach the **near-white upper color-map endpoint** over more than the same frozen 10% disk-area limit?

The successor defines an endpoint pixel as one for which **all three** sRGB channels are at least 254/255. This is a new statistic, preregistered after the parent result. It is not described as a bug fix or as if it had been the original rule.

## Frozen inputs and integrity

The executable reads the parent receipt and its three locally retained source panels. It must verify:

1. the parent receipt SHA-256 and schema are recorded in the successor receipt;
2. each source byte SHA-256 equals the digest frozen in the parent receipt;
3. each raster remains `1320 x 1020` pixels;
4. the crop remains `x = [174,1125), y = [7,958)`; and
5. the disk mask remains `r <= 21 mas` on the `951 x 951`, `[-45,+45] mas` grid.

Any mismatch stops without a successor verdict.

## Frozen decision rule

Compute the all-channel endpoint fraction independently for B6, B7, and B8.

- `ENDPOINT_ACCEPTABLE` only if every fraction is at most `0.10`.
- `ENDPOINT_EXCESSIVE` otherwise.

If endpoint saturation is acceptable, re-evaluate parent O1 using the already-frozen parent booleans for its other three conditions: every pair correlation at least 0.25, registered mean above the 121-rotation null 95th percentile, and at least one retained positive component in every band. No morphology, correlation, component, beam, or null statistic is recomputed or changed.

The successor O1 is:

- `SUPPORTS_RESOLUTION_STABLE_NONAXISYMMETRY` only if endpoint saturation is acceptable and all three carried parent conditions are true;
- `INCONCLUSIVE_RASTER_ENDPOINT_SATURATION` if the endpoint is excessive;
- `DOES_NOT_SUPPORT_RESOLUTION_STABLE_NONAXISYMMETRY` otherwise.

O2 and O3 are carried unchanged from the parent receipt. In particular, a positive O1 remains evidence only for shared large-scale, non-axisymmetric image morphology. It is not evidence for circular cells, a Cassi lattice, proton/star identity, or a common mechanism.

## Output and stopping rule

One deterministic execution writes `_diag/stellar_cells/betelgeuse_morphology_v2.json`, including the parent receipt digest, verified source digests, endpoint fractions, carried conditions, verdicts, and limitations. Stop after this one execution. Do not change the endpoint definition or threshold in response to the result.

## Registered receipt-integrity replay — 2026-09-02

The first successor receipt has SHA-256
`49de976fe56f95ee6e2048e33b6d1c2467d95ae8fce9c9ec7bb165b8b55775cd`.
Post-run inspection found one receipt-contract omission: the executable used the
frozen crop directly but did not assert that every parent provenance entry
recorded that same crop. The retained parent receipt does record
`[174, 7, 1125, 958]` for B6, B7, and B8.

Exactly one integrity replay is authorized after adding that missing assertion.
The replay must require the prior receipt hash above, retain the same parent and
source bytes, and record the parent crop beside each source check. It changes no
endpoint, threshold, mask, carried statistic, decision rule, or scientific
verdict.

## Final parent-constant binding replay — 2026-09-02

The first integrity replay receipt has SHA-256
`1a0fbaf6e0a0ec2155f88cf777b187b45fb0449cad8d7729ecb6a17150333095`.
It closed the parent-crop omission, but review found that the executable still
used the frozen `951`, `45 mas`, and `21 mas` grid/mask constants without
comparing them to the same fields in the parent receipt.

Exactly one additional integrity replay is authorized after adding those three
parent-constant assertions. It must require the receipt hash above, retain the
complete earlier replay chain, and change no source, crop, endpoint, threshold,
mask, statistic, decision rule, or scientific verdict.
