# Sampled-JFA versus continuous faces — corrected fixture report

Date: 2026-08-17
Domain: open tile
Verdict: **CONTROLLED FIXTURE PASS — live production ensemble remains open.**

The original regular/anisotropic fixture accidentally used a complete graph and was tautological. The corrected probe reconstructs a sampled open graph from N=32 nearest-site labels for every arm, then compares all-site continuous next faces against that sampled graph.

```
PASS regular sampled next-face coverage misses=0
PASS sliver oracle witness next=1 t=2.00000000
PASS sliver sampled graph contains witness
PASS degenerate control classified
PASS open seam edge omitted
PASS anisotropic sampled next-face coverage misses=0
RESULT: PASS (6 checks, 0 failures)
```

The mandatory sliver uses δ=1/64. The open seam arm suppresses the opposite-side periodic contact. The anisotropic replay scales sites and physical cell dimensions by diag(φ,1,φ²).

This corrects the earlier evidence but remains a controlled fixture—not full adoption. Production still requires live GPU JFA labels, live 8,192-site BCC/perturb/shear ensembles, frozen Fibonacci directions, false-positive certification, deterministic topology bytes, topology-generation wiring, and periodic image tests if periodic rendering is enabled.
