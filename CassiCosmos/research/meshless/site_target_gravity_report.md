# Unified gravity-target and topology-refit experiment — report

Date: 2026-08-31  
Preregistrations: `research/meshless/site_target_gravity_prereg.md`,
`research/meshless/gravity_recovery_prereg.md`,
`research/meshless/gravity_interpolation_diagnostic_prereg.md`,
`research/meshless/gravity_fmm_local_prereg.md`, and
`research/meshless/gravity_fmm_local_tree_control_prereg.md`  
Verdict: **REJECT** the registered G61 site-target reconstructions;
**UNEVALUABLE** G67 after loss of its frozen receipt; **ADOPT** the default-off
hierarchical retained-moment refit; **DOES NOT SUPPORT** the registered
higher-order local/FMM reconstruction; **STOP** the helix-conditioned branch

## 1. Question and decision

The experiment tested whether the existing meshless field, Barnes-Hut tree,
Voronoi sites, and double-helix flow diagnostics could be combined into a
cheaper gravity path without changing the force contract.

Two independent cost reductions were measured:

1. walk the tree at 8,192 field sites instead of at every particle, then
   reconstruct particle acceleration from site values;
2. retain an unchanged Morton hierarchy and refresh only live source values and
   node moments instead of repeating the full tree preparation.

Both initially registered arms failed their frozen acceptance gates.
Site evaluation was fast but its reconstructed particle force was inaccurate.
The first retained-topology attempt preserved the final particle gradient but
used a direct range scan for every node, failed byte identity for raw node
slots, and missed the required preparation-speed ratio. Those two production
branches were removed. A later preregistered recovery replaced the direct node
scan with a bottom-up child-moment reduction; Section 9 records its passing
result and default-off adoption.

## 2. Baseline

The production tree preparation is exactly 123 dispatches:

- 2 initialization dispatches: counter reset and root seed;
- 1 live-source gather;
- 91 bitonic-sort stages for 8,192 sources;
- 28 breadth-first split/commit dispatches;
- 1 node-moments dispatch.

The unchanged tree then walks at exact particle positions. The final focused
run preserved the established production contracts:

- G31: all 2,000 particle gradients finite and all targets in-box;
- G30: GPU tree versus the same-source numpy prototype median relative error
  `1.429e-5`, below the `1e-2` ceiling;
- `verify_meshless_gravity.tscn`: exit `0`.

## 3. Site-target gravity — G61/G62

### Cost

The amended synchronized timing population compared 2,097,152 particle targets
with 8,192 site targets, using three warmups and eleven alternating measured
runs. The frozen follow-up site/control median ratio was `0.2297`, so G62
**PASS**. The final focused rerun returned `0.2340`, the same classification.

The target-count reduction is therefore real: evaluating the existing tree at
the field sites costs about 23% of the large particle-target control on this
RX 7900 XTX.

### Force fidelity

The same exact-position particle gradient was the reference. All registered
reconstruction candidates failed the unchanged G61 thresholds of median error
`<= 0.01` and 99th-percentile error `<= 0.05`:

| Reconstruction | Median relative error | 99th percentile | G61 |
|---|---:|---:|---|
| nearest site | `0.1296` | `0.3939` | FAIL |
| 8-neighbor inverse-distance | `0.1410` | `0.4178` | FAIL |
| 16-neighbor affine/tidal fit | `0.07755` | `0.2185` | FAIL |

The affine fit improved the median but remained roughly 7.8 times above the
median limit and 4.4 times above the tail limit. G62's cost win cannot override
G61. Site-target gravity is **REJECT**. Its engine/sim toggle and target-buffer
resize were removed, as was its target-index branch in
`compute/cassi_site_nbody.glsl`. The separate G63 probe-only refresh remains in
`compute/cassi_tree_build.glsl` and does not implement site targeting.

## 4. Persistent topology refit — G63

The independent refit probe retained particle targets. It changed live mass and
both Yang/Yin source values while site positions stayed fixed, then compared a
two-dispatch source-refresh-plus-moments path against a fresh 123-dispatch
build.

Identity result:

The table and timings below are the recorded run summary. The exact frozen raw
receipt no longer survives, so they are not a currently replayable gate.

| Observable | Result |
|---|---|
| source ordering | byte-identical |
| active node count | identical (`11,963`) |
| active node ranges | **not byte-identical** |
| per-particle gradient | byte-identical |
| gradient finiteness | PASS |

Synchronized preparation samples, in microseconds:

- fresh: `[4508, 4292, 4433, 4617, 4641, 4419, 4469, 4199, 4427, 4257, 4471]`, median `4433`;
- refit: `[1911, 1924, 1962, 1977, 1974, 1843, 2015, 1721, 1957, 1695, 2019]`, median `1957`;
- refit/fresh ratio: `0.441462`, above the frozen `0.25` ceiling.

The frozen G63 receipt was registered as SHA-256
`23b6fe726b181e7f5f64297eb8a3c95790f1030644ce1f44d3b70b211999070c`; the
surviving canonical-path file hashes to
`1d3002c000660a6d64c9a4a5ab4fb432aaa9f0590895098293b2367154b52a12`.
G63 is therefore **UNEVALUABLE** from surviving artifacts, and
`stage5c_refit_verify.py` now exits `2` on that mismatch instead of assigning a
verdict. The direct all-node range-scan path remains unadopted. Shader mode 11
is used only to refresh live sources before the accepted bottom-up leaf and
child reduction in modes 12/13; no production path uses the
mode-11-plus-mode-6 direct refit.

## 5. Initial double-helix stopping decision

The preregistered helix use was deliberately narrow: a live integer-winding
statistic could only tune the Barnes-Hut opening decision after an accepted
site-target or persistent-refit arm. It was never permitted to add a new force
term.

G63 rejected the last eligible arm in the initial experiment, so that decision
tree stopped before G65. The accepted recovery refit later reopened G65 under
the frozen recovery protocol; Section 9 records the fresh negative observation.
No helix-conditioned opening code was written.

## 6. Retained artifacts

- `research/meshless/site_target_gravity_prereg.md` contains the frozen gates,
  amendments, raw G63 samples, and stopping decision.
- `scripts/verify_meshless_gravity.gd` produces the production G30/G31 receipt
  plus the rejected G61/G62 and G63 research receipts.
- `research/meshless/stage5b_verify.py` exits on the established production
  G30/G31 contract and separately labels the site-target result `REJECT`.
- `research/meshless/stage5c_refit_verify.py` evaluates G63 and intentionally
  exits nonzero for the measured failed receipt.
- `_diag/meshless_gravity_gpu.json` and `_diag/tree_refit_gpu.json` are the
  gitignored raw outputs.

No site-target, hybrid-correction, direct range-scan refit, or helix toggle
remains. The only adopted mechanism is the default-off
`tree_hierarchical_refit` engine/sim option described in Section 9.

## 7. Verification receipt

| Check | Result |
|---|---|
| Godot shader import after cleanup | PASS, exit `0` |
| focused `verify_meshless_gravity.tscn` after rollback | PASS, exit `0` |
| `stage5b_verify.py` production G30/G31 | PASS, exit `0` |
| `stage5b_verify.py` site-target diagnostic | G61 FAIL, G62 PASS, `REJECT` |
| `stage5c_refit_verify.py` | G63 UNEVALUABLE, frozen SHA absent, exit `2` |
| initial 35-arm GPU battery | **31 PASS / 4 FAIL** |

The initial full battery was run, but it was not green. Arms 5
(`verify_meshless_sim`), 7 (`verify_gridless_physics`), 23
(`verify_meshless_sim_aniso`), and 24 (`verify_particle_vanish`) timed out.
Their logs repeatedly report `Couldn't create Vulkan swapchain (VkResult error
-11)`; arms 5 and 23 also enter the existing zero-particle decoupled path and
report zero-size particle-buffer bindings. The focused gravity arm was arm 19
and passed. The required windowed global-RenderingDevice arms cannot be
replaced by headless runs on this rig, so the battery result is recorded as
incomplete rather than presented as a green contract.

## 8. Learned constraint

The dominant lesson is that fewer gravity targets and fewer dispatches are not
sufficient by themselves:

- site-target evaluation removes walk work, but the registered G61
  reconstructions do not preserve the particle-force contract;
- the recorded direct range-scanning run removed 121 dispatches but still
  consumed about 44% of a fresh build; its frozen raw receipt is no longer
  available for a gate replay.

The accepted recovery keeps exact particle evaluation and changes the
moment-update algorithm. The separately preregistered diagnostic below shows
that affine error is not concentrated at Voronoi boundaries or in the deepest
Barnes-Hut walks. No alternative target-sharing basis is adopted from that
result.

## 9. Preregistered recovery — G67 through G72

### G67 frozen-input status

The recovery verifier now implements G67's own registered thresholds:
overall median `<= 0.01`, p99 `<= 0.05`, high-q and high-mass medians
`<= 0.02`, and opposite fraction `<= 0.001`. It previously imported the G61
helper, whose high-q and high-mass limits were incorrectly stricter at `0.01`.

The exact G67 input was frozen as SHA-256
`268900a2c13e5c3165e0f27e2466f5727d54d8d5571fb7cf77a13f1b26045e4d`.
That artifact was overwritten; the surviving canonical-path receipt hashes to
`e8db9eed2fe0a69ccdd82e38b575dd42667af2f9e7548b2d37999dd47dd00ea7`.
The verifier now checks the hash before analysis and exits `2` with
`UNEVALUABLE` on mismatch. Earlier H1/H2 scratch numbers cannot be used to
assign the frozen gate. Arm H is unadopted, and G68/G69 were not run.

### Separate interpolation failure-mechanism diagnostic

A new preregistration acquired one distinct receipt,
`_diag/gravity_interpolation_diagnostic_gpu.json`, SHA-256
`97baf4808cd9a0e889fb65fbd98ce9ef997bd57f38d5d12a792bcbd83ecefafc`.
It compared exact site samples with a corrected exact particle walk and replayed
the production opening decisions from the captured tree:

- the legacy particle-index self-exclusion had zero bit or interaction-count
  effect in this acquisition: median, p99, and maximum gradient difference
  were all `0`; it is `LEGACY-SAFE` for this receipt only;
- nearest-site error was median `0.12895`, p99 `0.39462`;
- registered diagnostic IDW16 error was median `0.16167`, p99 `0.44794`;
- affine16 error was median `0.076862`, p99 `0.227116`;
- CPU traversal replay matched all 2,000 GPU interaction counts exactly.

Affine median error across boundary-margin quartiles, nearest boundary to
deepest cell interior, was `[0.03032, 0.05505, 0.08156, 0.10503]`. Across
mean accepted-depth quartiles, shallowest to deepest, it was
`[0.19020, 0.12129, 0.06363, 0.02676]`. The registered ratios were `0.28869`
for near-boundary/deep-interior and `0.14069` for deepest/shallowest walk, both
opposite the preregistered failure signatures. The diagnostic verdict is
**UNRESOLVED**: it rules out concentration at cell boundaries or deep opening
as the explanation, but it does not rule out exact site evaluation, another
interpolant, or a higher-order local/FMM expansion.

### Higher-order local/FMM reconstruction — G73/G74

The follow-up kept the exact 8,192 gathered source sites and 2,000 particle
targets from the diagnostic receipt. For each target's nearest-site owner it
evaluated the nearest 256 sources directly, fitted the remaining site gradient
with a reusable Cartesian harmonic potential expansion from 48 neighboring
site samples, and measured expansion orders 1 through 5. The order-5 candidate
used 291 direct or expansion terms per particle.

G73 is frozen as **INCONCLUSIVE**. Its receipt,
`_diag/gravity_fmm_local_result.json`, hashes to
`7db051faeab1985e990662b89308ab80b7502cdfcf21d388cc8b6257a3b4515f`.
The registered all-source pair-sum control was not like-for-like with the GPU
Barnes-Hut reference: an accepted internal node uses aggregate
`W^(2/3)` softening and a quadrupole, while the pair sum used per-source
softening and no accepted-node quadrupole. That control cannot validate or
invalidate the candidate.

G74 changed only that control. The existing density-aware `BHOctree` evaluated
the same 32 rounded particle indices from the same source sites and retained
every source leaf because particle targets have no source identity. Its median
relative error against the GPU walk was `1.422e-5`, its recorded p99 was
`0.02303`, every value was finite, and the opposite-vector fraction was `0`;
the preregistered tree control passed. Target-domain geometry, order-5 rank,
conditioning, and finiteness controls also passed.

| Order | Median error | p99 error | High-q median | High-mass median | Fidelity |
|---:|---:|---:|---:|---:|---|
| 1 | `0.23003` | `0.46158` | `0.25958` | `0.22706` | FAIL |
| 2 | `0.039492` | `0.081465` | `0.045655` | `0.032868` | FAIL |
| 3 | `0.018123` | `0.10023` | `0.017160` | `0.026930` | FAIL |
| 4 | `0.014835` | `0.11473` | `0.011965` | `0.019915` | FAIL |
| 5 | `0.022891` | `0.13475` | `0.023087` | `0.024723` | FAIL |

Order 4 reached the lowest median error, but its p99 remained `0.11473`, more
than twice the frozen `0.05` limit. The primary order-5 candidate degraded on
both median and tail error and failed the median, p99, high-q, and high-mass
limits. Its 291-term work proxy was also about ten times the production tree's
median 29 interactions per particle; that is an operation-count proxy, not a
runtime measurement.

G74 therefore **DOES NOT SUPPORT** this fixed-near-field harmonic local
reconstruction. Nothing from this arm is adopted into production. The result
receipt, `_diag/gravity_fmm_local_result_v2.json`, hashes to
`5c06965ba134e404144a8b56fdcb805fc1ac27336ca00320ba84d6ebca67f46a`.


### Why the first refit was slow, and the replacement

The rejected G63 path used only two dispatches but recomputed every active
node's moments by scanning that node's full source range. The same source was
therefore revisited at every tree level: fewer dispatches did not remove the
`O(N log N)` memory and arithmetic work. Fresh builds also allocate node slots
with atomics, explaining why raw node-range arrays can differ while the final
force is identical.

The recovery keeps the Morton topology and replaces that scan with a true
hierarchy:

1. mode 11 refreshes live source mass and Yang/Yin values in retained order;
2. mode 12 evaluates exact moments only for leaves;
3. fourteen mode-13 passes combine child mass, center of mass, charge, and
   translated quadrupoles from depth 13 to the root.

This is 16 dispatches rather than 123, but more importantly each retained node
is reduced from its direct children once. The final focused receipt measured:

| Gate | Measurement | Verdict |
|---|---|---|
| G70 structure | node count, order, ranges, and centers unchanged | PASS |
| G70 force | median `2.358e-7`, p99 `4.124e-7`, max `4.930e-7`, opposite `0` | PASS |
| G71 fresh preparation | median `4243.281 µs` per preparation | reference |
| G71 hierarchical refit | median `76.531 µs` per preparation | PASS |
| G71 ratio | `0.018036`; refit faster in all 11 paired samples | PASS |

That is a measured `55.4×` preparation speedup for the retained-topology case.
The production engine now exposes `tree_hierarchical_refit`, default `false`.
When enabled it refits only while the site-topology generation, home-window
center, and box scale match the retained tree. A generation or geometry change
forces a complete build before refitting resumes.

### Production stability — G72

The windowed local-engine gate ran 32 one-step calls with the toggle enabled.
It observed 2 full builds, 30 hierarchical refits, 12 refits before the first
site-topology transition, and one mandatory transition full build. The first
gravity preparation after the transition was full. Positions, velocities,
accelerations, site Yang/Yin values, and both compared tree gradients were
finite.

The verifier invokes the production `_tree_run_in_list()` twice on the same
frozen source state and reads `_tree_grad` after each walk: once after a
hierarchical refit and once after forcing the feature-off full build. It
therefore compares particle gradients produced by the walk, not merely moment
buffers. Retained node order and ranges are identical through the refit; only a
fresh atomic rebuild may assign equivalent children to different raw slots.
The registered run's maximum relative force difference was `1.482e-5` over
512 particles with no opposite vectors. A post-diagnostic recheck again met
every G72 condition, with maximum difference `8.388e-6`. G72 **PASS**.

The final feature-off focused run also preserved G30/G31: all 2,000 gradients
were finite and in-box, and GPU-tree versus numpy-tree median relative error was
`1.429e-5`.

### Helix eligibility — G65

Because Arm R passed, G65 was run once under its frozen acquisition amendment.
The preregistered “run 31, then record after steps 32–34” sequence was executed
as 31 pre-snapshot one-step calls followed by one step and one readback for
each registered snapshot. The accepted engine configuration produced complete
live `EY`/`EI` snapshots at steps 32, 33, and 34 after a topology transition.
Every field and statistic was finite and phase-valid, with closure residual
`1.414e-16`; every snapshot
nevertheless contained zero nonzero plaquettes, zero closed winding rings, and
winding fraction `0`. G65 **FAILS**, so G66 is **STOPPED**. No helix force,
opening statistic, coefficient, or shader path was added.

### Final verification and artifacts

- diagnostic-mode `verify_meshless_gravity.tscn`: PASS, exit `0`, without
  changing `_diag/meshless_gravity_gpu.json` (SHA remained `e8db9eed…`);
- feature-off focused `verify_meshless_gravity.tscn` and
  `stage5b_verify.py`: G30/G31 PASS; registered G61 remains REJECT and G62 PASS;
- `stage4_verify.py` after the arm-5 lifecycle fix: existing G9/G10 remain
  non-green (`0.1281` normalized-field difference and `0.2302` median
  gradient-relative error); this gate is outside retained-tree acceptance;
- `gravity_interpolation_diagnostic.py`: `LEGACY-SAFE`, exact 2,000/2,000
  depth-count replay, mechanism `UNRESOLVED`;
- `gravity_fmm_local_verify.py --tree-control`: corrected tree control PASS;
  G74 **DOES NOT SUPPORT** the order-5 local/FMM candidate;
- `gravity_recovery_verify.py`: G67 UNEVALUABLE on missing frozen SHA, exit `2`;
- `stage5c_refit_verify.py`: G63 UNEVALUABLE on missing frozen SHA, exit `2`;
- `stage5d_hier_refit_verify.py` replayed the preserved
  `tree_hier_refit_gpu_registered_5c175d44.json` receipt: G70/G71 PASS;
- `verify_tree_hier_refit_engine.tscn`: G72 PASS with default-off true,
  32 steps, pre-transition refits, mandatory transition full build, finite
  readback, and 512/512 same-state walk gradients compared;
- `gravity_recovery_helix_verify.py`: expected G65 FAIL, G66 STOPPED;
- final 36-arm battery: **33 PASS / 3 FAIL**.

The two stale inline meshless verifier scenes were pinned to
`physics_decoupled=false`, matching their direct `_run_physics_steps` contract;
arms 5 and 23 then passed. The remaining full-battery failures were arm 7
(`verify_gridless_physics`) and arm 13 (`verify_presentation_layers`), which
did not complete after repeated Vulkan swapchain `-11` errors, plus diagnostic
arm 24 (`verify_particle_vanish`), which hit the same battery timeout but passed
when rerun alone. The result is not represented as a green 36/36 battery.

Recovery artifacts are
`research/meshless/gravity_recovery_prereg.md`,
`research/meshless/gravity_recovery_verify.py`,
`research/meshless/gravity_interpolation_diagnostic_prereg.md`,
`research/meshless/gravity_interpolation_diagnostic.py`,
`research/meshless/gravity_fmm_local_prereg.md`,
`research/meshless/gravity_fmm_local_tree_control_prereg.md`,
`research/meshless/gravity_fmm_local_verify.py`,
`research/meshless/stage5d_hier_refit_verify.py`,
`scripts/verify_tree_hier_refit_engine.gd`, and
`research/meshless/gravity_recovery_helix_verify.py`. Raw and preserved
receipts remain under `_diag/`.
