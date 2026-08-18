# Site-native open-tile ray traversal — report

Date: 2026-08-17
Topology: sampled-JFA open adjacency
Verdict: **SUPPORTS controlled diagnostic traversal; production ensemble gate remains.**

`compute/cassi_voronoi_ray_traverse.glsl` converts tile sites with `site_world = site_tile − extent + window_center`, computes the finite open-tile slab exit, and traverses continuous bisector planes only across sampled adjacency edges. Crossings at or beyond the slab exit are suppressed.

The kernel uses

```
r = s_j − s_i
F0 = |r|² − 2 r·(p − s_i)
dt = F0 / (2 r·rd)
```

with `den > 1e-7`, `eps_t=max(1e-5,2e-6·max(1,|t_current|))`, strict progress, and lower site ID for ties.

Focused GPU sequence probe passes 7/7: the three-site ray enters site 2 before site 1 at `t=1.00999999`, the reverse ray terminates, and repeated/zero-progress transitions are zero.

The corrected continuous fixture probe now uses sampled open graphs—not complete graphs—for regular and anisotropic controls. It passes regular coverage, the δ=1/64 sliver witness, degenerate classification, open seam suppression, and anisotropic coverage (6/6). These are controlled fixtures, not the full live BCC/perturb/shear/Fibonacci adoption ensemble. The kernel remains open-only; periodic image offsets and topology-generation wiring are not implemented.
