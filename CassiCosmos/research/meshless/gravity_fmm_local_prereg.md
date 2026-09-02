# Higher-order local/FMM gravity reconstruction preregistration

Date frozen: 2026-08-31  
Status: frozen before implementation or analysis  
Predecessor: `research/meshless/gravity_interpolation_diagnostic_prereg.md`

## 1. Question

Can one reusable expansion per owning Voronoi site reconstruct the exact
particle tree gradient when a fixed near field is evaluated directly and the
remaining source-free far field is represented by a higher-order harmonic
local expansion?

This is a CPU reconstruction experiment against an existing GPU receipt. It
does not amend G61 or G67, change a production shader, or authorize adoption.

## 2. Frozen input

Read only `_diag/gravity_interpolation_diagnostic_gpu.json`, SHA-256
`97baf4808cd9a0e889fb65fbd98ce9ef997bd57f38d5d12a792bcbd83ecefafc`.
The reference is `corrected_grad_b64`; site samples are `site_grad_b64`.
Abort as `INCONCLUSIVE` before analysis if the checksum, dimensions, finiteness,
`leaf_cap == 1`, or selector metadata differ.

Reconstruct source weights exactly as `cassi_tree_build.glsl` mode 7 and
`stage5b_verify.py` do:

- `mass = rho_mass(site_cell) * volume + max((EY + EI) * volume,
  field_floor * volume)`;
- `q = rho_field^2 / (rho_field^2 + phi^-2 + epsilon^2)` with
  `epsilon = EY - phi * EI`;
- `weight = mass * (1 + (xi - 1) * q)`.

The direct source primitive is the shader's leaf-cap-one monopole:

`weight * (source - target) * (distance^2 + eps2 + weight^(2/3))^(-3/2)`.

## 3. Frozen kernel control

For 32 particle indices from integer-rounded `linspace(0, Np - 1, 32)`, sum the
direct primitive over all sources and compare it with the corrected GPU tree
reference. The kernel control passes only if outputs are finite, median relative
error is `<= 1e-3`, p99 is `<= 1e-2`, and the opposite-direction fraction is
zero. Failure makes the expansion result `INCONCLUSIVE`; do not alter the
kernel or thresholds.

## 4. Frozen near/far split

Assign every particle to its exact nearest site. For each distinct owning site:

- choose the 256 nearest source sites, including the owner, as the fixed near
  set;
- choose the 48 nearest sites, including the owner, as far-field fit samples;
- use the 257th-nearest source distance as the first-excluded far radius;
- subtract the exact 256-source near force from each fit site's exact GPU tree
  gradient;
- fit the remaining far gradients once for that owner;
- reconstruct every particle in that owner cell as exact 256-source near force
  plus the fitted far expansion.

Nearest-neighbor ties are ordered by source index. No particle-specific fit,
adaptive neighbor count, regularization, weighting, seed search, or retry is
allowed.

The expansion is geometrically valid only if every particle's distance from its
owner divided by the owner's first-excluded far radius is `< 1`. Otherwise the
verdict is `INCONCLUSIVE`.

## 5. Frozen harmonic local expansions

Use dimensionless coordinates
`u = (position - owner_position) / first_excluded_far_radius`.

For each potential degree `p = 1, 2, 3, 4, 5`, construct the complete Cartesian
harmonic-polynomial space of degrees 1 through `p`:

- enumerate homogeneous monomials at each degree;
- construct the exact monomial Laplacian map;
- take its numerical null space by SVD;
- use gradients of those harmonic polynomials as the vector-field design.

There are `p * (p + 2)` coefficients: 3, 8, 15, 24, and 35. Fit all three far-
gradient components jointly by unweighted least squares over the fixed 48 site
samples, then evaluate the fitted gradient at owned particles.

Every degree-5 design must have rank 35. Record condition-number median, p99,
and maximum; p99 must be finite and `<= 1e10`. A rank failure or condition gate
failure makes the experiment `INCONCLUSIVE`.

`p=1` is the constant-far-field control. `p=5` is the registered higher-order
candidate; intermediate orders are convergence controls, not a parameter
search.

## 6. Frozen fidelity gate G73

For each order report:

- overall median and p99 relative force error using the floor
  `|reference| > 1e-8`;
- high-q-owner and high-mass-owner median error, with high strata defined by
  their 75th percentiles;
- opposite-direction fraction;
- finite-output status.

G73 passes for `p=5` only when:

- median `<= 0.01`;
- p99 `<= 0.05`;
- high-q median `<= 0.02`;
- high-mass median `<= 0.02`;
- opposite fraction `<= 0.001`;
- all outputs are finite.

## 7. Frozen interpretation and stopping rule

Run all five registered orders exactly once and write
`_diag/gravity_fmm_local_result.json` before printing a verdict.

- `SUPPORTS HIGHER-ORDER LOCAL/FMM` requires the kernel and validity controls,
  G73 PASS, `p=1` G73 FAIL, and both the p5 median and p99 no greater than 80%
  of their p1 values.
- `LOW-ORDER FAR FIELD SUFFICIENT` applies when `p=1` itself passes G73; do not
  claim a need for higher order.
- `DOES NOT SUPPORT` applies when all controls are valid but p5 fails G73 or
  fails the registered 20% improvement.
- `INCONCLUSIVE` applies on checksum, kernel, geometry, rank, conditioning, or
  finiteness failure.

Record, but do not gate on, the evaluation-work proxy `256 + 35 = 291` terms per
particle versus the corrected GPU tree interaction-count distribution. This
proxy excludes coefficient construction, memory traffic, dispatches, and GPU
layout; even a positive fidelity result is not a production performance or
adoption result.
