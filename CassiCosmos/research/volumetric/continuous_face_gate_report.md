# Sampled-JFA versus continuous faces — gate report

Date: 2026-08-17
Domain: open tile
Verdict: **SUPPORTS first open-tile traversal prototype.**

The sampled-JFA adjacency is exact only on accelerator-grid labels. `_diag/continuous_face_oracle.gd` therefore compares its retained edges against a full all-site continuous next-face calculation on deterministic controls.

```
PASS regular next-face coverage misses=0
PASS sliver oracle witness next=1 t=2.00000000
PASS sliver sampled contains witness
PASS degenerate classified
PASS open seam edge omitted
PASS anisotropic next-face coverage misses=0
RESULT: PASS (6 checks, 0 failures)
```

The mandatory sliver uses δ=1/64 at N=32; the continuous p0→p1 face at x=4 is retained by the sampled graph. The δ=0 four-way event is classified degenerate rather than used as an ordinary-face gate. The open seam arm drops p0↔p1 across x=0/L. The anisotropic replay scales physical coordinates by diag(φ,1,φ²).

This supports a first traversal prototype that enumerates sampled-JFA neighbors and uses continuous bisector planes. It does not establish complete continuous Delaunay equivalence for arbitrary site configurations. Production adoption still requires live BCC/perturb/shear ensembles, progress/repeat gates, topology-generation wiring, and explicit periodic-image validation if periodic rendering is enabled.
