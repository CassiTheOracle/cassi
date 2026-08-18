# Site-native open-tile ray traversal — report

Date: 2026-08-17
Topology: sampled-JFA open adjacency, consumed through exact CSR
Verdict: **SUPPORTS controlled diagnostic traversal; production ensemble gate remains.**

`compute/cassi_voronoi_ray_traverse.glsl` converts tile sites with `site_world = site_tile − extent + window_center`, computes the finite open-tile slab exit, and traverses continuous bisector planes only across the exact CSR rows derived from sampled adjacency. CSR rows are deterministic ascending site IDs and preserve every bitset edge without a degree cap. The original bitset remains the sampled-topology authority; no live engine/renderer integration is claimed.

The kernel uses

```
r = s_j − s_i
F0 = |r|² − 2 r·(p − s_i)
dt = F0 / (2 r·rd)
```

with `den > 1e-7`, `eps_t=max(1e-5,2e-6·max(1,|t_current|))`, strict progress, and lower site ID for ties. The per-step neighbor work is proportional to the current CSR row degree rather than all-site or bitset-row scanning; CSR construction is the separate exact count/scan/fill phase.

The focused GPU sequence probe now supplies offsets plus neighbors and retains the three-site checks: the ray enters site 2 before site 1 at `t=1.00999999`, the reverse ray terminates, and repeated/zero-progress transitions are zero. `_diag/render_adjacency_probe.gd` additionally checks exact degrees and ascending CSR rows against the CPU bitset oracle.

The corrected continuous fixture probe uses sampled open graphs—not complete graphs—for regular and anisotropic controls. It passes regular coverage, the δ=1/64 sliver witness, degenerate classification, open seam suppression, and anisotropic coverage (6/6). These are controlled fixtures, not the full live BCC/perturb/shear/Fibonacci adoption ensemble. The kernel remains open-only; periodic image offsets and topology-generation wiring are not implemented.
