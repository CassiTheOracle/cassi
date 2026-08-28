# Sampled-JFA open adjacency — acceptance report

Date: 2026-08-17
Graph source: `sampled_jfa`
Seam policy: `open_tile`
Verdict: **ADOPT as the sampled accelerator graph; CSR is an exact derived traversal acceleration, not a continuous-Voronoi authority.**

## Construction

`compute/cassi_voronoi_render_adjacency.glsl` builds the symmetric per-site bitset from the final JFA label field. Mode 0 clears the bitset; mode 1 visits each accelerator cell and its in-bounds +x/+y/+z faces. A differing pair of valid labels sets both adjacency bits. Repeated raster contacts deduplicate through `atomicOr`.

`compute/cassi_voronoi_adjacency_csr.glsl` compacts that bitset exactly in two modes: a degree pass counts every set bit, then a deterministic fill emits neighbors in ascending site-ID order. The host owns the exclusive scan of the degree array into `offsets[0..n_sites]`; `offsets[n_sites]` is the exact neighbor-array length. There is no degree cap or overflow fallback. The original bitset remains the topology authority and CSR is a lossless derived representation.

The shaders use the live label convention `x*N*N + y*N + z`. Negative labels and `INT_MAX` are invalid. Boundary faces do not wrap: periodic-image traversal requires directed edges carrying an image offset and is outside this bitset/CSR contract.

## Focused verification

Standalone local-RD probe `_diag/render_adjacency_probe.gd` compares GPU bytes against an independent CPU open-boundary +axis oracle, then checks every CSR degree and ascending row against the same bitset. The focused traversal probe `_diag/ray_traverse_probe.gd` now binds CSR offsets plus neighbor indices rather than the bitset.

The intended probe output remains the same topology checks, with additional exact-degree and exact-CSR-row checks. No live production renderer or engine wiring is claimed here.

## Limitation and next gate

This graph is exact for the sampled JFA label field only. It can miss continuous Voronoi slivers smaller than the accelerator grid and can inherit JFA label approximations. Before direct cell-to-cell ray traversal is adopted, the sampled graph must be compared against the full all-site continuous next-face oracle on regular, sliver, degenerate, seam, and anisotropic controls. A missing continuous next face is a hard rejection for using sampled adjacency as the sole traversal topology.
