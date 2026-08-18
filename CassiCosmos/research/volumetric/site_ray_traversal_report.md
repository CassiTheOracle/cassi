# Site-native open-tile ray traversal — report

Date: 2026-08-17
Topology: sampled-JFA open adjacency
Verdict: **SUPPORTS diagnostic traversal kernel.**

`compute/cassi_voronoi_ray_traverse.glsl` consumes raw tile-space sites, converts them using `site_world = site_tile − extent + window_center`, and traverses continuous bisector planes only across sampled adjacency edges. It records each visited site and boundary parameter.

The kernel uses the frozen local form

```
r = s_j − s_i
F0 = |r|² − 2 r·(p − s_i)
dt = F0 / (2 r·rd)
```

with `den > 1e-7`, `eps_t=max(1e-5,2e-6·max(1,|t_current|))`, strict forward progress, and lower site ID for ties within epsilon.

Focused local-RD probe:

```
PASS local RD
PASS shader loads
PASS pipeline builds
PASS ray0 enters site2 first  sequence=[0,2,1]
PASS ray0 first hit analytic  t=1.00999999
PASS reverse ray terminates    count=1
PASS strict progress           repeated/zero=0
RESULT: PASS (7 checks, 0 failures)
```

The three-site ray deliberately enters site 2 before site 1, guarding against replacing directional bisector traversal with nearest-Euclidean-neighbor logic. This is an open-tile diagnostic kernel; periodic image offsets, topology-generation wiring, live BCC ensembles, and multi-face vertex resolution remain required before final renderer adoption.
