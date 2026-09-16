# Physical radiation P0/P1 implementation verification

## Status: FROZEN BEFORE GPU OR SCIENTIFIC RUNS—September 2026

## Scope

This schedule qualifies only the prescribed, one-way LTE continuum preview in `research/presentation/physical_radiation_design.md`. It does not qualify a native Cassi material mapping, simulation-owned thermal state, conservative radiation feedback, moving-medium transport, non-LTE populations, line radiation, or unresolved physical emitters. Those capabilities must return an explicit unavailable result until their own inputs and controls exist.

## Frozen inputs

- Observer: official CIE 1931 2-degree colour-matching functions, 360–830 nm at 1 nm, expected SHA-256 `fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1`.
- Display transform: CIE XYZ, D65 white point, to linear sRGB using the IEC 61966-2-1 matrix; no per-source white normalization.
- Spectral candidates: 16, 32 and 64 visible wavelength intervals with two bolometric tails. Boundaries are selected from the 471 observer samples at rounded equal-index intervals; frequency boundaries are the reversed wavelength transforms using physical `c`.
- Prescribed model: homogeneous LTE continuum, explicit temperature, absorption coefficient and SI length mapping; scattering and incident boundary intensity are zero for the first retained GPU arm.
- Camera approximation: frozen-state formal solution. It is not retarded or time-dependent radiation transport.

## CPU controls and stopping rule

For temperatures 2500, 4000, 6500, 10000 and 20000 K:

1. The sum of all group-integrated Planck radiances, including the two tails, must agree with `sigma*T^4/pi` within relative error `5e-8` in the double-precision reference.
2. Group-reconstructed chromaticity must agree with the 1 nm observer integral within `max(|dx|, |dy|) <= 0.006`.
3. All spectral radiances and XYZ components must be finite and nonnegative before the XYZ-to-RGB transform. Negative linear-RGB components are retained in raw output and handled only by the declared display gamut map.
4. The homogeneous transfer solution is checked for optical depths `0`, `1e-8`, `0.1`, `1` and `10`. The implementation must be continuous at zero opacity, finite, nonnegative, and within relative error `2e-12` of the double-precision analytic expression.
5. Unknown schema major versions, nonfinite values, nonpositive units/temperature, unordered or overlapping group coverage, observer hash mismatch, unsupported capabilities, and missing required fields must be rejected before GPU allocation.

Select the smallest visible group count that passes every colour and power control. If no candidate passes, stop without a GPU launch and revise this frozen schedule before testing a different layout. The retained CPU artifact is `research/presentation/reference/physical_radiation_reference.json` plus the console receipt emitted by `research/presentation/physical_radiation_reference.py --verify`.

## GPU controls and stopping rule

The retained windowed arm uses the selected layout and a synthetic homogeneous slab whose camera path lengths exercise empty, thin, moderate and opaque rays.

- **PR-G0—contracts and provenance:** local model, units, group layout, observer and prescribed snapshot load with exact immutable hashes; all frozen malformed inputs are rejected before allocation.
- **PR-G1—formal transfer:** pre-exposure linear XYZ/radiance output is finite; empty rays preserve the declared black boundary; sampled slab rays agree with the independent analytic reference within `3%` relative per visible XYZ component when the reference component exceeds `1e-10`, otherwise absolute error `1e-10`.
- **PR-G2—observer and display:** the white point and XYZ-to-linear-sRGB transform identifiers are present in runtime statistics and capture metadata; no source-by-source white normalization occurs.
- **PR-G3—read-only parity:** enabling, rendering and disabling the prescribed preview leaves the simulation’s solver payload bytes unchanged. Appearance preset save/load cannot enable coupled dynamics or restore physical state.
- **PR-G4—source identity and lifecycle:** snapshot/model/unit/group identity changes reset history; invalid or stale identities produce an unavailable state rather than stale pixels; uniform sets are released before owned images; shutdown returns all module-owned RIDs to invalid handles.
- **PR-G5—capture integrity:** a real captured PNG and its JSON sidecar identify the same source/publication, executed step/time, camera, actual dimensions, exposure, observer, model, units, groups, approximation and unavailable capabilities. Any optional raw file is floating-point linear data with declared units, never a relabelled PNG.
- **PR-G12—bounded resources and performance:** coefficient storage is bounded by canonical preview cells times groups; no per-group screen-depth atlas is allocated; the module reports estimated and allocated bytes. At 640×360, 16 visible groups, quality tier 1 and fixed exposure, the median added render-boundary interval over 90 post-warmup frames must be no more than 20 ms and p95 no more than 35 ms. A miss is reported as `HOLD`; it does not permit changing the physical group layout or coefficients.

Run the focused arm once after shader import settles. A harness/import failure may be corrected without changing scientific tolerances; any scientific or performance failure ends the run and is reported without coefficient retuning. The existing configured battery is run only after the focused arm and integration checks pass.

## Explicitly unavailable gates

PR-G6 through PR-G11 require, respectively, a qualified native material mapping, persistent engine thermal state, conservative remap/restart, stationary and moving transport, paired matter–radiation source accounting, and provider-specific richer physics. The present tree lacks those accepted inputs and fixtures. Runtime readiness must list the missing capabilities exactly; inherited Theory checks are references, not native qualification receipts.
