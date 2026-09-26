# Leaf-only density-aware softening — probe report

Status: VERDICT = CONTRADICTS (leaf-only does NOT restore theta-consistency)
Date: 2026-08-16
Prereg: `research/meshless/leafsoft_prereg.md` (frozen before the run)
Probe: `research/meshless/leafsoft_probe.py` (numpy, deterministic)

## Trace (run output, verbatim numbers)

```
leaf-only probe: N=8192 theta=0.50 eps2=1.0e-06 max_levels=14
=== G17 leaf-only tree vs density-aware direct ===
G17 leaf-only tree vs direct       median=3.025e+00 99th=7.028e+01  (target med<=1e-02)  GATED
=== G18 self-exclusion (leaf-only tree vs direct) ===
[G18] leaf-only  median=3.025e+00  99.9th=9.242e+01  max=1.089e+02  (n>0.1: 8192/8192)
--- informational (NOT gated) ---
leaf-only tree vs GPU dump         median=3.600e+02 99th=1.613e+03
current per-node law vs direct (baseline) median=9.857e-01 99th=9.936e-01
---- gate ----
[FAIL] G17 (leaf-only tree vs direct)  med=3.025e+00
[FAIL] G18 (leaf-only)  med=3.025e+00  p999=9.242e+01
VERDICT: CONTRADICTS
```

## Verdict (frozen decision tree)

**CONTRADICTS** — leaf-only softening does NOT restore G17/G18 to their frozen
thresholds. Both gates fail HARDER than the current per-node law:
- G17 median 3.03 (target ≤ 1e-2) vs the current law's 0.985
- G18 median 3.03, p999 92.4 (target median ≤ 0.01, p999 ≤ 0.5), n>0.1 = 8192/8192
- leaf-only tree vs GPU dump: median 360 relative error — the variant diverges
  ~360× FROM THE GPU, i.e. it is not the law the GPU implements and is far from it.

## Why leaf-only is wrong (mechanism, from the walk path)

Under leaf-only, every accepted INTERNAL (non-leaf) node reverts to the global
`eps2 = 1e-6`. In the dense 8192 config (4096 Plummer sources in a 0.6 box,
mass-weighted W per site), a target near such a heavy internal node gets
`monop = -W·d/(ds2 + 1e-6)^(3/2)` with W ≫ 1 and small ds2: the unsoftened
singular near-field. This is precisely the singularity that `4ce2912`'s
density-aware softening was added to remove (shader comment lines 43-54;
the per-node force cap at lines 171-188 exists because dense-node near-fields
spiked even WITH the softening). Reverting internal nodes to global eps2
reintroduces it → the tree over-predicts near-field force massively, giving
median 360× over the GPU and G17/G18 ~3.0. The hypothesis's premise (that
only leaf/capped cells carry the heating) is contradicted by the probe and by
the shader's own design (heavy internal accepted nodes are a near-field
heating source).

## Probe sanity (faithfulness)

The probe's `current`-mode walk (per-node W^(2/3) on every accepted node)
reproduces the GPU dump to median 3.83e-7 with alignment 1.000000 — identical
to the G16 margin. So the leaf-only result is a genuine consequence of the
variant, not a probe bug.

## Analytic heating-protection check (reported, NOT gated)

From the code path (`cassi_tree_gravity.glsl:131` leaf = `ccount == 0`;
max-depth-capped coincident cells are leaves in the build, `cassi_tree_build`
mode 5/8; and the per-node softening at `:123-124,146,167`):

- **Preserved under leaf-only:** the `W^(2/3)` term survives on exactly the
  heavy max-depth-capped leaf cells (W ≫ 1): a capped cell is a leaf, so it
  gets `eps2 + W^(2/3)`. The two-body heating protection that lives on those
  capped cells is unchanged.
- **LOST under leaf-only:** the same `W^(2/3)` term is removed from every
  INTERNAL accepted node. The shader's own history (commit 4ce2912 message:
  "a·r' swung from −0.86 to ~0" via per-node softening; and the per-node force
  cap at `:171-188` added because dense-node near-fields reached 10⁴–10⁶)
  shows heavy internal dense nodes ARE a heating source. Leaf-only unsoftens
  exactly those nodes, so the overall heating protection is NOT preserved —
  only the capped-leaf subset is.

## Recommendation for the shader owner

Do NOT switch to leaf-only softening on this evidence: it is CONTRADICTED.
The current per-node `eps2 + W^(2/3)` law is the faithful GPU behavior and G16
(passes at 3.8e-7). The G17/G18 residual (median 0.985) is a genuine
consequence of aggregate-node far-field softening, not a fixable-by-leaf-only
artifact. Any shader change must be a separate, pre-registered decision by the
owner; this probe supplies a negative result ruling out the leaf-only arm.
No shader edit was made; no section of this result was gated on a weakened
threshold.
