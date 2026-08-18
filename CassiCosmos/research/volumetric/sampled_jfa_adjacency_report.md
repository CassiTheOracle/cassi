# Sampled-JFA open adjacency — acceptance report

Date: 2026-08-17
Graph source: `sampled_jfa`
Seam policy: `open_tile`
Verdict: **ADOPT as the sampled accelerator graph; not yet a continuous-Voronoi traversal authority.**

## Construction

`compute/cassi_voronoi_render_adjacency.glsl` builds a symmetric per-site bitset from the final JFA label field. Mode 0 clears the bitset; mode 1 visits each accelerator cell and its in-bounds +x/+y/+z faces. A differing pair of valid labels sets both adjacency bits. Repeated raster contacts deduplicate through `atomicOr`.

The shader uses the live label convention `x*N*N + y*N + z`. Negative labels and `INT_MAX` are invalid. Boundary faces do not wrap: periodic-image traversal requires directed edges carrying an image offset and is outside this bitset.

## Focused verification

Standalone local-RD probe `_diag/render_adjacency_probe.gd` compares GPU bytes against an independent CPU open-boundary +axis oracle.

```
PASS pipeline builds
PASS split-x                 gpu=[2,1]   cpu=[2,1]
PASS uniform                 gpu=[0,0]   cpu=[0,0]
PASS dedup-many-faces        gpu=[2,1]   cpu=[2,1]
PASS invalid-middle          gpu=[0,0,0] cpu=[0,0,0]
PASS open-seams-all-axes     gpu=[6,5,3] cpu=[6,5,3]
RESULT: PASS (6 checks, 0 failures)
```

The all-axis seam control intentionally excludes the `(0,2)` periodic seam edge; its rows `[6,5,3]` contain only open in-bounds contacts. The dedup control presents many identical label contacts but produces one symmetric edge.

## Limitation and next gate

This graph is exact for the sampled JFA label field only. It can miss continuous Voronoi slivers smaller than the accelerator grid and can inherit JFA label approximations. Before direct cell-to-cell ray traversal is adopted, the sampled graph must be compared against the full all-site continuous next-face oracle on regular, sliver, degenerate, seam, and anisotropic controls. A missing continuous next face is a hard rejection for using sampled adjacency as the sole traversal topology.
