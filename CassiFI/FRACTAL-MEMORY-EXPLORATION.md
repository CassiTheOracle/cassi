# A Fractal Scaffold for Durable Field Memory

An exploration record for one program: build a fractal (multiscale recurring)
scaffold inside the field, place transceivers to guide the field's dynamics into
deep recurring patterns, and use those patterns as a place where information can
be durably saved and later recovered.

Motivation: an observational thread elsewhere in the workspace suggested
core–shell organization with currents exchanging between centers. This document
explores how such multiscale recurrence could serve as memory in CassiFI's own
field machinery.

## Preamble

### The three layers

- **Scaffold** — the recurring arrangement: which regions exist, how they nest,
  how they are wired, what the boundary conditions are. Here it is declared
  geometry and topology (`ResonantProfile.coordinates`, `.edges`, `.topology` in
  `cassi_resonant_field.py`), not learned content.
- **Durable memory** — persistent differences outliving the activity that wrote
  them: canonical adaptive state inside the one `RegionalMachineImage`
  (`cassi_field_regions.py`, `cassi_learning_computer.py`, design §32.3).
- **Activity** — waves, currents, and transients that retrieve, carry, or
  transform what is stored: heartbeat, breath, circulation, packet impulses,
  transceiver ticks (§26.6–§26.8, §27.2).

The premise is that scaffold and activity together decide which durable
differences are cheap to write, cheap to reach, and safe to keep under
interference. The sections below explore that premise.

### What "deepest recurring pattern" has to mean

It cannot mean the field's single strongest attractor: descending to one dominant
mode trades memory for convergence and destroys the distinctions that make recall
useful. §33.10 gives the operative contrast — a recurring quiet state versus a
hidden countdown that also reports quiet until it fires, where equal current
observations do not distinguish them. The target is the opposite shape:
regularities surviving across scales and contexts **while exceptions stay
recoverable**. §33.20 requires that a consolidation gain destroying a rare
required exception is not acceptable consolidation, and that capacity pressure
never silently turns unknown into false; §18.1 represents capacity rather than
denying it. Every direction below is judged against that requirement.

### Current capabilities

- **One canonical adaptive state**, one tensor `[1, 9M, 1]`; host caches are
  disposable — "Deleting every cache must preserve the next logical transition"
  (design §32.3). Checkpoints, journals, limits, and revocation fences live in
  `cassi_field_owner.py` (§32.4, §32.16).
- **Fixed seven-pool two-strand body.** `ResonantProfile` in
  `cassi_resonant_field.py` fixes `pools == 7`, at least four paired ports per
  pool, an oriented circuit with endpoint returns, intra/inter-pool exchange, a
  bounded heartbeat, an activity-modulated breath, and 112 phase-space
  coordinates (§26.3–§26.8, §26.24).
- **Recursive scale decomposition.** `balanced-contiguous-haar-phase-space-v1`
  maps an ordered contiguous packet path into orthonormal position/momentum
  common/counterflow coefficients via `analyze_helical_packet`,
  `split_helical_packet`, `compose_helical_packets` (§26.18) — a disposable view
  of canonical words, not stored state.
- **Explicit resolution change.** `expand_resolution`/`reduce_resolution` publish
  layout transitions with declared error accounting; projections of one fixed
  sixteen-port body measured `0.00252243` and `0.00130892` reconstruction error
  at four and eight ports per pool (§26.24).
- **Bounded wave writes.** `apply_helical_packet_impulse` and the regional
  `packet-impulse` write one scale or detail mode as bounded common/counterflow
  momentum with recorded work (§26.18).
- **Knowledge-bearing transceivers.** `cassi_field_transceiver.py` condenses
  named charts and ports into a temporal realization with explicit ports,
  retained working state, a one-tick connection delay, output uncertainty, and
  error-controlled condensation (§27.1–§27.4). Limits: `_MAX_DENSE_DIM = 512`,
  `_MAX_RANK = 64`, `_MAX_PORTS = 4096`, `_MAX_TICKS = 4096`,
  `REGIONAL_KERNEL_MAX_WORK = 4096`.
- **Learned temporal memory and skills.** `cassi_temporal_field.py`,
  `cassi_temporal_inquiry.py` (§28); online and one-shot-oracle arms complete
  `6/6` transfer tasks and frozen memory `0/6` (README "Active learning
  comparison").
- **Packet-aware reasoning.** `cassi_field_cognition.py` holds a bounded frontier
  under one allowance, publishes reservations, refines one support, and refuses
  dependent reads through a correction barrier (README "Packet-aware reasoning").
- **Exact structural oracles.** `cubic_kernel_decision.py`,
  `run_frame_separation_probe.py`, `run_mixed_schaefer_frame_obstruction.py`
  decide width and frame questions exactly for declared finite families (README,
  "Mixed direct-sum frame obstruction", "Frame separation inside nullity three").



### Leading hypothesis (INFERENCE)

**INFERENCE.** A hierarchy of paired circulation cells — nested scales, each
holding a common mode and a counterflow mode between its strands — with
transceiver access concentrated at the informative interfaces between levels
rather than spread evenly. The claimed consequence is selective cross-level
access: a broad query reaches the organizing coarse pattern without descending
into every detail, and a precise query recovers a detail without activating the
whole body. Existing measurements are suggestive but do not establish it: the
body separates common from relative coordinates (§26.5), the packet basis
separates parent scale from localized detail (§26.18), and measured own-pool
response fractions already lie between `0.9153` and `0.9707` (§26.24). Whether
nesting those facts yields selective access, rather than more ports, is what the
sections below test.

### Comparison sketch

Any advantage claim must survive a matched comparison. §26.22 already asks for
undivided, isolated, meaningfully coupled, and degree/strength-matched rewired
organizations at matched bytes and actual computation; §26.24 reports that
comparison at held workspace bytes `2088`, with meaningful and rewired bodies both
at 90 edges and total absolute edge strength `1.7134218127191345`, and states it
shows causal transport rather than superior task performance. The program extends
it to six arrangement families:

1. current paired helix (`topology="meaningful-helix"`); 2. flat regular
(`"undivided"`); 3. matched random rewiring (`"rewired"`); 4. nested core–shell;
5. recursive paired-loop modules; 6. task-selected placement.

Families 1–3 have profile support — `ResonantProfile.__post_init__` accepts
exactly `{meaningful-helix, undivided, isolated, rewired}`; families 4–5 are
reachable as declared pool graphs over `projected_transport` and
`projected_inv_mass` and were measured once by the geometry harness; family 6 is
**INFERENCE** at the profile level. The survival harness has since given families
4 and 5 a measured survival contrast against the helix default at `k = 4` written
items (`0.3351631005750861` for `nested-core-shell` and `0.061124304880849925` for
`recursive-paired-loops` against `0.0764836820747603`), and its attribution arms
put that gain on the projected inverse-mass profile rather than on the projected
rail (`mass-only` `0.33445984698946024`, delta `+0.25797616491469993`, against
`rail-only` `0.07447116639609798`, delta `-0.002012515678662322`), which is a
scaffold comparison at matched declared activity and item count, not the
matched-budget task comparison this sketch asks for. Matched budgets across families: workspace
bytes (the §26.24 convention), connection count and total absolute edge strength,
the same input/observation stream, and the same work measured in actual operator
applications rather than nominal steps (§32.16). The challenge set, each with an
existing precedent: partial-cue recall (`run_temporal_learning_scenario.py`);
delayed relationships (§27.3 one-tick delay); competing contexts
(`cassi_temporal_field.py`, §28.2; §26.24 phase-conditioned task); selective
correction (reasoning correction barrier; §27.5 selective intervention);
unfamiliar combinations of learned parts (connected composition at `0.02565`
pooled held-out RMSE without observing the new pairs).

### Cross-reference to the concurrent harnesses

Twenty-three runner/regression pairs, written by other sessions in this checkout, are
this map's empirical components:
`run_fractal_geometry_exploration.py` / `test_fractal_geometry_exploration.py`,
`run_fractal_memory_exploration.py` / `test_fractal_memory_exploration.py`,
`run_fractal_durability_exploration.py` / `test_fractal_durability_exploration.py`,
`run_fractal_placement_exploration.py` / `test_fractal_placement_exploration.py`,
`run_fractal_survival_exploration.py` /
`test_fractal_survival_exploration.py`,
`run_fractal_ladder_exploration.py` / `test_fractal_ladder_exploration.py`,
`run_fractal_metric_exploration.py` / `test_fractal_metric_exploration.py`
and `run_fractal_lattice_exploration.py` /
`test_fractal_lattice_exploration.py`, and `run_fractal_feedback_exploration.py` /
`test_fractal_feedback_exploration.py`, `run_owner_write_path_exploration.py` /
`test_owner_write_path_exploration.py`, `run_memory_consumer_path.py` /
`test_memory_consumer_path.py` and `run_owner_surface_options.py` /
`test_owner_surface_options.py`, and `run_owner_nested_cycle.py` /
`test_owner_nested_cycle.py`, and `run_memory_store_scale.py` /
`test_memory_store_scale.py`, and `run_store_addressing_rank.py` /
`test_store_addressing_rank.py`, and `run_store_addressing_capacity.py` /
`test_store_addressing_capacity.py`, and `run_store_addressing_tree.py` /
`test_store_addressing_tree.py`, and `run_scale_composition_surface.py` /
`test_scale_composition_surface.py`, and
`run_fractal_parent_summary_application_exploration.py` /
`test_fractal_parent_summary_application_exploration.py`, and
`run_fractal_bidirectional_recursive_memory_cell.py` /
`test_fractal_bidirectional_recursive_memory_cell.py`, and
`run_fractal_recursive_memory_cell.py` /
`test_fractal_recursive_memory_cell.py`, and
`run_fractal_multicycle_recursive_memory_cell.py` /
`test_fractal_multicycle_recursive_memory_cell.py`. The independent verifier is
`verify_fractal_multicycle_recursive_memory_cell.py`. All twenty-three runners
exist and have been run from this directory, and each writes a receipt that
parses:

```powershell
python run_fractal_geometry_exploration.py --output _diag/fractal-geometry/exploration.json
python run_fractal_memory_exploration.py --output _diag/fractal-memory/exploration.json
python run_fractal_durability_exploration.py --output _diag/fractal-durability/exploration.json
python run_fractal_placement_exploration.py --output _diag/fractal-placement/exploration.json
python run_fractal_survival_exploration.py --output _diag/fractal-survival/exploration.json
python run_fractal_ladder_exploration.py --output _diag/fractal-ladder/exploration.json
python run_fractal_metric_exploration.py --output _diag/fractal-metric/exploration.json
python run_fractal_lattice_exploration.py --output _diag/fractal-lattice/exploration.json
python run_fractal_feedback_exploration.py --output _diag/fractal-feedback/exploration.json
python run_owner_write_path_exploration.py --output _diag/owner-write-path/exploration.json
python run_memory_consumer_path.py --output _diag/memory-consumer-path/exploration.json
python run_owner_surface_options.py --output _diag/owner-surface-options/exploration.json
python run_owner_nested_cycle.py --output _diag/owner-nested-cycle/exploration.json
python run_memory_store_scale.py --output _diag/memory-store-scale/exploration.json
python run_store_addressing_rank.py --output _diag/store-addressing-rank/exploration.json
python run_store_addressing_capacity.py --block declared-profile
python run_store_addressing_capacity.py --block higher-resolution
python run_store_addressing_capacity.py --block merge --output _diag/store-addressing-capacity/exploration.json
python run_store_addressing_tree.py --block declared-profile
python run_store_addressing_tree.py --block higher-resolution
python run_store_addressing_tree.py --block merge --output _diag/store-addressing-tree/exploration.json
python run_scale_composition_surface.py --block declared-profile
python run_scale_composition_surface.py --block higher-resolution
python run_scale_composition_surface.py --block merge --output _diag/scale-composition-surface/exploration.json
python run_fractal_parent_summary_application_exploration.py --output _diag/fractal-parent-summary-application/exploration.json
python -m pytest test_fractal_parent_summary_application_exploration.py -q
python run_fractal_bidirectional_recursive_memory_cell.py --output _diag/fractal-bidirectional-recursive-memory-cell/exploration.json
python -m pytest test_fractal_bidirectional_recursive_memory_cell.py -q
python run_fractal_recursive_memory_cell.py --output _diag/fractal-recursive-memory-cell/exploration.json
python -m pytest test_fractal_recursive_memory_cell.py -q
python run_fractal_multicycle_recursive_memory_cell.py --output _diag/fractal-multicycle-recursive-memory-cell/exploration.json
python verify_fractal_multicycle_recursive_memory_cell.py --receipt _diag/fractal-multicycle-recursive-memory-cell/exploration.json
python -m pytest test_fractal_multicycle_recursive_memory_cell.py -q
python -m pytest test_fractal_geometry_exploration.py test_fractal_memory_exploration.py test_fractal_durability_exploration.py test_fractal_placement_exploration.py test_fractal_survival_exploration.py test_fractal_ladder_exploration.py test_fractal_metric_exploration.py test_fractal_lattice_exploration.py test_fractal_feedback_exploration.py test_owner_write_path_exploration.py test_memory_consumer_path.py test_owner_surface_options.py test_owner_nested_cycle.py test_memory_store_scale.py test_store_addressing_rank.py test_store_addressing_capacity.py test_store_addressing_tree.py test_scale_composition_surface.py -q
```

- `_diag/fractal-geometry/exploration.json`, schema
  `cassifi.fractal-geometry-exploration.v1`, `receipt_sha256`
  `01ff3e8637a3bb9c071b55a5de404b7cdc1e4dccdec35cb2dcb6af709f5bc2b4`.
- `_diag/fractal-memory/exploration.json`, schema
  `cassifi.fractal-memory-exploration.v1`, `receipt_digest`
  `04c6ed7c7a55ef66e22ddbea159e052e0232ec1735076064f7a83b15f53125a8`.
- `_diag/fractal-durability/exploration.json`, schema
  `cassifi.fractal-durability-exploration.v1`, `receipt_digest`
  `b560ab05d8f8d43fb701425807b051aa4e573a2efe0dcece500b5dccfaa9cb99`.
- `_diag/fractal-placement/exploration.json`, schema
  `cassifi.fractal-placement-exploration.v1` (its `declarations` block carries
  `cassifi.fractal-placement-receipt.v1`), `receipt_sha256`
  `045b8a418968613377cfde962f7255e84385323b3ea6325ceebb401e25b948b7`.
- `_diag/fractal-survival/exploration.json`, schema
  `cassifi.fractal-survival-exploration.v1`, `content_digest`
  `3458c0842ac391d098bd7d454c43a2e9163b7f70679bbab3a1172b4c8a25ffe2`.
- `_diag/fractal-ladder/exploration.json`, schema
  `cassifi.fractal-ladder-exploration.v1`, `content_digest`
  `6208400bec247bf31920642c28d235430010c5da8152de4a0ea59c7825072935`.
- `_diag/fractal-metric/exploration.json`, schema
  `cassifi.fractal-metric-exploration.v1`, `content_digest`
  `70d201c05f28790077c3ce12c2b2d3012a13e53c9ac5712bfe28adca9c997aae`.
- `_diag/fractal-lattice/exploration.json`, schema
  `cassifi.fractal-lattice-exploration.v1`, `receipt_sha256`
  `006dc8b0ae312d56f5efb6bda9896586ab26857e7c9cd66710da93548623dd92` (the only
  digest field it carries; its `comparisons` block names the canonical-JSON rule
  its content digest would use).
- `_diag/fractal-feedback/exploration.json`, schema
  `cassifi.fractal-feedback-exploration.v1`, `receipt_digest`
  `fdc2e1443d95e010bae1bb8974980e9e1dff5047946f135dbaa5d30c243eb63b` (the only
  digest field it carries; the receipt holds no wall-clock key, so its file is
  reproducible byte for byte).
- `_diag/owner-write-path/exploration.json`, schema
  `cassifi.owner-write-path-exploration.v1`, `receipt_digest`
  `a1f5c4ffe42a9c25182cf25ec54ab2e5bff7ff51147e2d51d98a6234072e9f7c` (the only
  digest field it carries; the receipt holds a `runtime_seconds` key, so its
  digest is stable across re-runs while its file hash is not).
- `_diag/memory-consumer-path/exploration.json`, schema
  `cassifi.memory-consumer-path.v1`, `receipt_digest`
  `3933e8ecc0aeedd1a9722c0bd282006d5217b516b3acf504133e973cb48b5f07` (the only
  digest field it carries; the receipt holds a `runtime_seconds` key, which its
  declared strip set removes because the measured body carries no inner
  wall-clock field).
- `_diag/owner-surface-options/exploration.json`, schema
  `cassifi.owner-surface-options.v1`, `receipt_digest`
  `a9a85f9b1e4a32b19c81e5476d94e78835c95739998b3f4b770d613d8ef7e455` (the only
  digest field it carries; the receipt holds an `elapsed_seconds` block, with a
  per-selection `elapsed_seconds` inside the overlap enumeration, and its
  declared strip set removes those leaves with the same four keys).
- `_diag/owner-nested-cycle/exploration.json`, schema
  `cassifi.owner-nested-cycle.v1`, `receipt_digest`
  `909ec09da53fd0b6946dca2dc18ad71c481ffaa2d9bbc76846f18cf382bbe1aa` — the frozen
  receipt, kept in place (file sha256
  `9c150e72d2d8d0bd13e08977f7c2de8b66fae0230f1cdcee05a24023493a4d81`), whose body
  still recomputes under the rule its runner now applies because excluding a key the
  body does not carry is a no-op; its own `declared.receipt_digest.taken_over` prose is
  frozen with it and describes the retired source-line binding. The same measurements
  under the current rule are published beside it at
  `_diag/owner-nested-cycle/exploration.layout-decoupled.json`,
  schema the same, `receipt_digest`
  `bd7a83d40f5013b6c9d71e5b0abb2fc0cd45f1e751122a1a6f6332a7993f736a`, file sha256
  `0e1089a07b5eb60ad80afc9b3d854cbbc1a38718d5c9bfc1315ba50fbed47f4c`. Both carry the
  digest field alone, both hold a `runtime_seconds` key, and both are taken over the
  same four declared strip keys; what the current rule is read over is stated below in
  "Determinism of the receipts").
- `_diag/memory-store-scale/exploration.json`, schema
  `cassifi.memory-store-scale.v1`, `receipt_digest`
  `d769cd297109d4885ee62a3256b649b5b0bb9504dd395daf8c1ee6a794ae2c77` (the only
  digest field it carries; the receipt holds a `runtime_seconds` key and two
  nested `elapsed_seconds` leaves inside its transceiver receipts, and it also
  publishes four surface digests that chain over a manifest carrying such a leaf
  — `A2`'s and `C1`'s owner ledger digests before and after their acts. Its
  declared strip set removes the family's four clock keys and, by the declared
  rule, the values derived from a stripped value, the chained manifest hash and
  the ledger digest computed over it, so on a re-run its digest holds while its
  file hash moves; see "Determinism of the receipts" for the rule, the defect it
  repairs and the runs that measure it. Unlike the nested cycle receipt, its
  digested body is the measurements alone — it carries no construction or
  source-line record — so its digest binds no source line, and its three
  `honest_negatives` blocks are declared empty lists: what bounds the claim is
  stated in the document and in the receipt's own four limitations, not as a
  receipt field).
- `_diag/store-addressing-rank/exploration.json`, schema
  `cassifi.store-addressing-rank.v1`, `receipt_digest`
  `59c22ecaabd1b952c370ea6d09f8fbddfd7231cf11ac44f64446e1b68c809510` (the only
  digest field it carries; the receipt holds a `runtime_seconds` key, and it reuses
  the store-scale receipt's declared strip rule rather than re-deriving one — the
  strip keys are declared as `run_memory_store_scale.STRIP_KEYS`, the family's four
  clock keys plus the three declared clock-derived digests, the digest is taken by
  that runner's own `receipt_digest`, and the rule recorded beside it is "the same
  declared rule as the store-scale receipt: derived-from-stripped values are
  stripped as a class" — so what it declares is what it applies, and the body holds
  `owner_ledger_sha256` leaves in its arm snapshots, which the declared set covers.
  Its digested body is the measurements alone — it carries no construction or
  source-line record — so its digest binds no source line, and on a re-run its
  digest holds while its file hash moves; see "Determinism of the receipts" for the
  rule and the runs that measure it.)
- `_diag/store-addressing-capacity/exploration.json`, schema
  `cassifi.store-addressing-capacity.v1`, `receipt_digest`
  `a3278fd1ef046f31f65f142f8e9f7831663ad4c868bffc5e33d7a41c0d3d3574` (the only
  digest field it carries at the top level, beside the two declared blocks it merges;
  the receipt holds a `runtime_seconds` key and each block holds one of its own, and
  it reuses the store-scale receipt's declared strip rule exactly as the rank receipt
  does — `declared.content_digest_strip_keys` is `run_memory_store_scale.STRIP_KEYS`
  and `declared.content_digest_strip_keys_source` reads "run_memory_store_scale.STRIP_KEYS,
  reused rather than re-derived" — so its digest holds while its file hash moves, and
  the same statement covers the merged body's own `runtime_seconds` and the per-level
  runtimes nested inside it. The two block files beside it carry their own
  `content_digest` under the same rule — `block-declared-profile.json` at
  `57e319c56d678115f8e6aa5e08d598480c8f042fe9dbba9e5ee44b9eddb4041d` and
  `block-higher-resolution.json` at
  `14d04223b4a7b93a683bcda3e7eb45603afc456c9ee14ba13c5d9bc272efdd2b` — and the
  merged receipt is those two records, the shared table, the ceiling reading and the
  verdicts assembled from them, so the three digests cover different bodies: a reader
  comparing a merged receipt against a block file must re-run the merge rather than
  compare the two values. Its digested body is the measurements and the table's own
  shape, with no construction or source-line record, so no edit to its runner moves
  its digest unless a measured number or a published row moves; see "Determinism of
  the receipts" for the rule, the merge control and the one thing about this family's
  re-runs that is recorded rather than repaired.)
- `_diag/fractal-recursive-memory-cell/exploration.json`, schema
  `cassifi.fractal-recursive-memory-cell.v2`, `content_digest`
  `5b254001650c8dce821a7a265ea4134ea5f223c8732b1a6a02ec3ddfcdb6ab28`,
  verdict `PASS_FIELD_OWNED_CLOSED_TWO_CYCLE_ACTIVE_UPWARD_RECURRENCE`.
- `_diag/fractal-multicycle-recursive-memory-cell/exploration.json`, schema
  `cassifi.fractal-multicycle-recursive-memory-cell.v1`, `content_digest`
  `2286b85bdb599baaec552545c72d90b3f15c552fdbd3003ae2db56c4f3d467c3`,
  verdict `PASS_FIELD_OWNED_BOUNDED_MULTICYCLE_UPWARD_RECURRENCE`.

- `_diag/scale-composition-surface/exploration.json`, schema `cassifi.scale-composition-surface.v1`, `receipt_digest` `19c38e6435efd380893469c78ff619a432405f3f56c26b92ba758901b63a3627` over the two declared blocks (`block-declared-profile.json` `87684098d3e222f160c96b6ba0823755f32dac0d4a861b0fb63518d301a2d8d2`, `block-higher-resolution.json` `2e16e6e07578c684b092e8a91f32c546e1add49fcfd6d561193bf9544859242a`). Its digested body is the measurements and the sweep table, with no construction or source-line record, so no edit to its runner moves its digest unless a measured number or a published row moves; the blocks are the block `content_digest` values of the same rule, and a reader comparing the merged receipt against a block file must re-run the merge rather than compare the two values.

Their figures are quoted in "Measured results from the concurrent harnesses"
below.

### Boundaries

No intelligence, consciousness, or biological-equivalence claim is made. Memory
utility is unproven until exercised, and a self-similar scaffold establishes
nothing by looking so. This is a present-state design and exploration record; it
states no conclusion about whether the program should proceed. Unmeasured
proposals are marked **INFERENCE**.

## A. Candidate geometries

### A.1 Nested core–shell
**Status.** No core–shell profile exists, and `coordinates` has no hook, so a literal shell radius is inexpressible; the expressible form is a declared pool graph over `projected_transport` plus a shell `projected_inv_mass`, which has now been measured once (see the harness section).
**Measured.** `nested-core-shell` is second-least localized of the ten non-`undivided` arrangements — median IPR `0.15986442406282375`, just above the `helix7` baseline `0.1565230898708423` and far below `recursive-paired-loops` `0.28602472976220794` — while carrying the second-highest retention `0.9077268956564812` and the second-worst condensation bound `106.7058285863892` (`_diag/fractal-geometry/exploration.json`). The survival receipt measures the same profile as the strongest of the three declared scaffolds at `k = 4` written items: recovery `0.3351631005750861` after the declared activity against the `helix7` default's `0.0764836820747603` and `recursive-paired-loops`' `0.061124304880849925`, a difference of `0.2586794185003258` against the declared `0.02` profile margin (`_diag/fractal-survival/exploration.json`).
**First step (INFERENCE).** Vary the shell metric decay and transport decay around the measured `nested-core-shell` point and re-run the retention and access sweeps at equal edges.
**Measures.** Retention mean, site dependence, and access coverage against the measured `nested-core-shell` values `0.9077268956564812` and `0.06856885869537555`.
**Counts against.** A variant whose access coverage does not exceed the `helix7` baseline `0.06111459857739958` while its declared link strength rises well above it.
**Run.** Bound `max_operator_effort = 4096`; profile-only change (reconstructible mechanics); validator support exists only through `projected_transport`/`projected_inv_mass`, which makes `topology` metadata-only.

### A.2 Recursive paired-loop modules
**Status.** Loops exist — circuit plus intra-pool and neighbouring-pool exchange (§26.4) — but no loop is carried by smaller copies of itself.
**Measured.** `recursive-paired-loops` is the most localized of the eleven arrangements, median IPR `0.28602472976220794` against the `helix7` baseline `0.1565230898708423` and `undivided` `0.025638847681613515`, with `14` distinct frequencies at `0.01` against the baseline `34` (`_diag/fractal-geometry/exploration.json`). The survival receipt measures its written-item endurance as the weakest of the three declared scaffolds: recovery `0.2702850816137677` for the single declared item and `0.061124304880849925` at `k = 4` after the declared activity, against the `helix7` default's `0.29462880739045766` and `0.0764836820747603` (`_diag/fractal-survival/exploration.json`).
**First step (INFERENCE).** For depth two, replace each depth-one circuit edge by a scaled copy on disjoint ports, then re-measure the depth-one peaks.
**Measures.** Whether composed peaks contain the depth-one peaks as sub-peaks; count of positive-frequency eigenvalues (§26.19 reports fourteen).
**Counts against.** Peaks dissolving into a continuum, or fewer distinguishable responses than the parent body.
**Run.** Depth two roughly quadruples ports, bounded by `ports_per_pool <= 4096` and `max_ports = 1_000_000`; cost is `O(N)` storage and `O(E)` exchange (§26.18).

### A.3 Helices within helices
**Status.** One helix with engineering pitch: half-turn separation, one turn across seven pool intervals (§26.4). No multi-scale embedding exists.
**First step (INFERENCE).** A literal radius modulation is unavailable, because `coordinates` is computed from a fixed formula with no declared hook; the expressible proxy redistributes metric-derived edge weights `c_uv = c_0/(l_uv*sqrt(V_u V_v))` at fixed arc length and edge set, then re-runs the transfer measurement.
**Measures.** Whether a strength-only metric redistribution moves the measured peaks, separated from any graph change.
**Counts against.** A pitch change moving nothing, or moving everything non-specifically — §26.4 already leaves computation unchanged under any metric-preserving rigid motion, and the geometry receipt shows density-matched graph-only changes leaving 64-tick retention within `0.00011141722933116771`.
**Run.** Geometry recomputation plus one response sweep, well inside `max_operator_effort`; reconstructible mechanics.

### A.4 Branching fractals
**Status.** Nothing exists; the nearest structure is the packet path, a binary tree over a contiguous interval (`_packet_support`), not over space.
**First step (INFERENCE).** Embed a depth-`d` binary tree adjacency on the coordinate curve with leaves bound to ports, then measure leaf-to-interior scaling.
**Measures.** Impulse-to-response ratio as a function of depth and branch index, over two depths.
**Counts against.** A response depending on leaf position rather than depth, or no consistent exponent between depths.
**Run.** Depth <= 4 keeps `ports_per_pool <= 4096`; reconstructible mechanics; §26.4's rule that extra ports add no independent models binds.

### A.5 Porous (Sierpiński/sponge-like) fractals
**Status.** Nothing exists; §26.18's `O(N)` workspace and bounded-scope chart storage are the closest structural statements.
**First step (INFERENCE).** Build the depth-`d` Sierpiński incidence on the port set and compare spectral gap and transfer against the undivided body at equal ports.
**Measures.** Spectral gap, transport localization, and total work per query.
**Counts against.** A smaller spectral gap than an equally sparse random graph at matched edges — pores costing mixing without buying separation.
**Run.** Construction is polynomial in port count, bounded by `max_ports` and workspace byte limits; fixed incidence, so reconstructible mechanics.

### A.6 Hyperbolic and ultrametric arrangements
**Status.** Nothing exists; the packet basis is a balanced tree, so the natural home for an ultrametric is coefficient space, which no implementation uses.
**First step (INFERENCE).** Replace the Euclidean coefficient norm by a tree distance and measure sibling-subtree interference at equal retained count.
**Measures.** Retained coefficients needed to reproduce a target packet at fixed tolerance, against `_MAX_RANK = 64`.
**Counts against.** No retention reduction, or a reduction paid for by an error bound above the recorded `2.0741977936686043e-7` online allowance (§27.5).
**Run.** Coefficient arithmetic only; reconstructible mechanics; must not displace the canonical `q_Y, q_I, p_Y, p_I` words (§26.18).

### A.7 Quasiperiodic layouts
**Status.** No quasiperiodic layout exists, and quasiperiodic *intervals* are inexpressible because `coordinates` has no hook; the expressible variant is a quasiperiodic strength distribution on the chain, which the geometry harness has measured once.
**First step (INFERENCE).** Vary the Fibonacci-like link scales around the measured `quasiperiodic-chain` point and compare against the flat ladder at matched link count and total strength.
**Measures.** Retention mean and access coverage against the measured `quasiperiodic-chain` `0.9070771225854412` and flat-ladder `0.9070780849024244`, both at declared link strength `10.2`.
**Counts against.** No separation between the two at matched total strength, which is the expected outcome; §23.3 already lists the golden-ratio question as open.
**Run.** Strength redistribution on an existing path; reconstructible mechanics; §26.20 warns against assuming fixed synthetic peaks after a geometry change.

### A.8 Multiple interacting centers
**Status.** Partly present: seven pools with exchange (§26.4), and skill coupling reaches all seven pools while a matched control stays quiescent (README). A second circulation center has no support: `ResonantProfile` carries one heartbeat frequency, work allocation, and amplitude, and the geometry harness's declared pool graphs express interaction strength only.
**First step (INFERENCE).** First express a two-center pool graph as a declared pool graph, then decide separately whether a second actuator phase is needed at all.
**Measures.** Signed circuit power per center and inter-center transport in the declared convention already reported (`9.73e-8`, §26.24).
**Counts against.** Nonzero power with no change in any readout — the decorative case §27.3 already excludes for drives.
**Run.** §26.7's rule that heartbeat support is a source mechanism and no circulation theorem bounds the claim; a second actuator is new descriptor state, and pool count stays fixed at seven.

## B. Scale control

### B.1 Scale ratio (doubling, golden, task-selected)
**Status.** Only the packet basis has a ratio, and it is balanced: each split divides the interval as evenly as integer port counts permit (§26.18).
**First step (INFERENCE).** Parameterize the split ratio and compare coefficients needed for fixed reconstruction tolerance across balanced and golden splits.
**Measures.** Coefficient count at fixed tolerance against `_MAX_RANK = 64` and the existing `16`-of-`112` linear reduction (§27.2).
**Counts against.** A ratio needing more coefficients at equal tolerance than the balanced split.
**Run.** Coefficient arithmetic; bounded by `_MAX_TICKS = 4096`; no new adaptive state; §23.3 lists this question as open.

### B.2 Hierarchy depth
**Status.** General depth remains unmeasured: the packet view's depth is a disposable view rather than stored state (§26.18); the frozen-parent receipt measures one declared L→LL field application, not hierarchy depth.
**First step (INFERENCE).** Find the retained-level count at which `compose_helical_packets` reproduces the source state inside the declared roundoff allowance.
**Measures.** The depth at which composition roundoff is reached and the corresponding coefficient count.
**Counts against.** §26.18's statement that dropping details does not preserve future dynamics in general; a depth at which details are free would contradict it.
**Run.** Bounded by `_MAX_TICKS`; reconstructible mechanics; the trap is reporting a static reconstruction depth as a dynamical one.

### B.3 Branching factor
**Status.** Exactly two in the packet basis and effectively two-strand in the body; nothing higher exists.
**First step (INFERENCE).** Extend the split to arity three at a port count divisible by three and compare retained coefficients at equal tolerance.
**Measures.** Coefficients per unit detail removed, and whether parent/detail orthogonality survives.
**Counts against.** Loss of orthogonality, breaking invertibility and the reversible regrouping guarantee (§26.18).
**Run.** Small bounded arithmetic; reconstructible mechanics; any new basis needs its own declared identity, as `balanced-contiguous-haar-phase-space-v1` has.

### B.4 Effective dimension
**Status.** The body is one-dimensional in pool coordinate with two strands; nothing measures an effective dimension of graph or coupling.
**Measured.** Every arrangement shares one spectral shape — state dimension `112`, `112` complex modes, zero real modes — while distinct frequencies at `0.01` fall from `34` (`helix7`) to `14` (`recursive-paired-loops`), `9` (`isolated`), and `1` (`undivided`), and every median inverse participation ratio stays well above the uniform reference `0.008928571428571428` (`_diag/fractal-geometry/exploration.json`).
**First step (INFERENCE).** Compute the spectral dimension of the frozen linearized operator and correlate it with measured transport locality.
**Measures.** Spectral dimension and the exponent relating response time to distance.
**Counts against.** A lattice-like dimension predicting measured transport no better than a line, which would make the geometric language uninformative.
**Run.** Frozen-operator eigen-decomposition, which §26.18 declares reconstructible mechanics rather than adaptive state.

### B.5 Gap distribution
**Status.** Only peaks are reported (`measure_body_response`); §26.19 supplies the eigenvalue view of the frozen generator.
**First step (INFERENCE).** Record the full positive-frequency spectrum and its gaps rather than seven peaks, and compare gap statistics across the six families.
**Measures.** Gap-ratio distribution and whether distinguishable peak count tracks pool count (§26.23 gives fourteen for seven pools).
**Counts against.** Gaps shrinking as port count rises, making the cavity language of §26 a resolution artifact.
**Run.** Frozen-operator measurement; reconstructible mechanics; bounded by `max_operator_effort`.

### B.6 Exact versus approximate self-similarity
**Status.** Nothing exists; the split is familiar from the solver work, where the width-two certificate is exact and polynomial while the recognizer's complement search is `binomial(n, rank)` (README).
**First step (INFERENCE).** Declare which relations survive a resolution change exactly — permutations and zero-mode extension (§26.18) — and which hold only within allowance.
**Measures.** The exact invariant set of `expand_resolution` against the approximate set.
**Counts against.** Any invariant claimed exact that a round trip moves beyond tolerance.
**Run.** Two bounded layout transitions on an existing path; no new adaptive state.

### B.7 Symmetry and deliberate defects
**Status.** Nothing exists; the body is already non-uniform (inertance `m_i = 1.3**i`, volumes varying by `1.0 + 0.05*(...)`), but the asymmetry is uninvestigated.
**First step (INFERENCE).** Compare a perfectly symmetric profile against the current asymmetric one at matched total strength.
**Measures.** Peak separability and localization under both profiles.
**Counts against.** No measurable separation gain, meaning symmetry breaking is not doing the work the cavity design assumes.
**Run.** Two response sweeps; reconstructible mechanics; learned chart bytes must stay unchanged as §26.24 records.

### B.8 Boundary conditions (closed, reflective, leaky)
**Status.** The circuit is closed: it crosses the upper endpoint and returns along Yin, with endpoint conversion as real edges and no disappearing flux (§26.4). No leaky boundary exists.
**First step (INFERENCE).** Add one declared leak edge at an endpoint with recorded extracted work and measure whether boundary readout retains an interior trace.
**Measures.** Extracted work against retained interior response, using the existing injected/extracted work separation (§26.7).
**Counts against.** Extracted work independent of interior state, defeating boundary readout as a mechanism.
**Run.** §26.10 already requires extracted work to be recorded separately; a leak must not hide an unstable step (§26.10, §26.21).

## C. Transceiver placement

### C.1 Controllability placement
**Status.** Ports are placed geometrically; `condense_workspace` takes explicit `input_ids`/`output_ids`, and §27.1 states the compiler does not discover a decomposition.
**Measured.** The input-lift column norms are structurally `1.0` for every arrangement, so drive reach is a construction invariant of the declared objective rather than a placement property; what varies is measured response coverage, `undivided` `0.1876359247979643`, `nested-core-shell` `0.05333366820720189`, `helix7` `0.03217022111014065` (`_diag/fractal-geometry/exploration.json`).
**Measured (placement).** The write side is structural in the same way — the canonical `input_lift` equals the declared port pin to `0.0` in every arrangement, and the pin coincides with the read pick-off within `2.220446049250313e-16` against a declared `1e-9` tolerance — so what varies is modal reach: `helix7` reaches most modes from port `23` (`30.16113222426118` effective modes) against `16.699271940345195` at its declared drive port `0`, while `undivided` reaches `104.76234683324073` of the `112` modes from port `9` (`_diag/fractal-placement/exploration.json`).
**First step (INFERENCE).** For one declared target response, enumerate port subsets of bounded size and record which reach it with least input energy.
**Measures.** Minimum input work per unit target deviation against the recorded input-order dependence `0.5377682406803815` (§27.5).
**Counts against.** A placement unable to beat arbitrary selection by more than the measured order-dependence spread.
**Run.** Enumeration inside the `512`-coordinate and `64`-retained compiler limits (§27.2); reconstructible mechanics unless placements are separately admitted.

### C.2 Observability placement
**Status.** Outputs are declared, not selected; §27.3 fixes the one-tick delay and requires every receiver to read the same predecessor snapshot.
**Measured.** Output-row norms are likewise structurally `1.0` everywhere, so read sensitivity does not distinguish placements; the discriminating quantity is coverage, and the best-covered body carries the worst condensation bound — `undivided` at coverage `0.1876359247979643` against bound `156.8624881544609` (`_diag/fractal-geometry/exploration.json`).
**Measured (placement).** Read sensitivity is structural too — the canonical `output_rows` equals the declared port pick-off to `0.0` — and the best read port is a different index from the best drive port in nine of the eleven arrangements, `helix7` reading most modes from port `20` at `31.092616984755292` against `17.684995813748003` at its declared read port `1`, with per-port write-versus-read Spearman correlation `0.9693486590038314` in `helix7` and between `0.6945812807881774` and `0.9994526546250684` across the set (`_diag/fractal-placement/exploration.json`).
**First step (INFERENCE).** Select outputs maximizing the separately observable dimension of retained state under the frozen linearization.
**Measures.** Fraction of retained coordinates distinguishable from the declared outputs, against the recorded `2.0741977936686043e-7` allowance.
**Counts against.** Adding outputs that reduce nothing, meaning existing ports already observe the retained state.
**Run.** Frozen-operator arithmetic; reconstructible mechanics; `_MAX_PORTS = 4096` bounds the domain.

### C.3 Joint write/read placement
**Status.** No joint criterion exists; input and output identities are declared per realization (§27.1).
**First step (INFERENCE).** Choose the port pair minimizing write energy plus read uncertainty for one channel and compare with the independent choices from C.1 and C.2.
**Measures.** Total work to write and read one retained relation at matched retention.
**Counts against.** A joint optimum equal to the independent pair, showing read and write do not compete.
**Run.** Bounded enumeration inside the same compiler limits; reconstructible mechanics.

### C.4 Mode-sensitive placement
**Status.** Partly present: `_packet_spatial_mode`, `_packet_momentum_direction`, and `apply_helical_packet_impulse` address one selected mode (§26.18).
**Measured (placement).** Per-port modal participation is now measured for all `28` ports of every arrangement: `helix7`'s best drive port reaches `30.16113222426118` effective modes with maximum single-mode dominance `0.060672656173647845` and distinguishability `0.15544913878819414`, against `16.699271940345195`, `0.07601016227233853` and `0.09588508701247875` at its declared drive port `0`, and no port index sits in the top five of every arrangement (`_diag/fractal-placement/exploration.json`).
**First step (INFERENCE).** Rank ports by participation in retained low-frequency modes and test whether mode-ranked placement lowers work per unit modal amplitude.
**Measures.** Impulse work per unit amplitude against the recorded `5e-4` per-impulse convention (README).
**Counts against.** No reduction versus unranked placement.
**Run.** Uses the existing packet API; reconstructible mechanics; well inside the `4096` work limit.

### C.5 Boundary and junction placement
**Status.** Nothing exists, but junctions are identifiable: pool boundaries, strand crossings, and the two endpoints (§26.4).
**First step (INFERENCE).** Place one transceiver at the upper endpoint, one at a pool boundary, and one in a pool interior, comparing sensitivity to an interior impulse.
**Measures.** Sensitivity ranking across the six families.
**Counts against.** Junctions no better than interiors, removing the simplest support for access at informative interfaces.
**Run.** Three transceivers within `_MAX_TICKS = 4096`; capacity accounting already includes transceiver programs, retained bytes, and ports (§27.4).

### C.6 Orientation-sensitive ports
**Status.** Present: every edge has a declared orientation with an antisymmetric reverse entry, checked by `__post_init__` on `projected_transport` (§26.4).
**First step (INFERENCE).** At one port, compare a forward impulse with the same impulse reversed and record the difference.
**Measures.** Orientation asymmetry in retained response against the recorded CPU/GPU agreement `1.73e-12` (§26.24).
**Counts against.** An asymmetry smaller than the arithmetic agreement, making the signal unresolvable at the current profile.
**Run.** Two impulse applications; reconstructible mechanics; no new state.

### C.7 Distributed sampling
**Status.** The viewer already samples distributively — 56 strand samples and 90 signed-power edges from a canonical snapshot, with pixels barred from becoming observations (README).
**Measured (placement).** The read side measured there is a single-port pick-off, one port per direction, so simultaneous multi-port reads are outside the measurement; the best single pick-off in `helix7` reaches `31.092616984755292` effective modes of the `112`, and the viewer's distributive sampling pattern is not covered (`_diag/fractal-placement/exploration.json`).
**First step (INFERENCE).** Treat the viewer's sampling pattern as a readout basis and measure how much of a known retained relation it recovers from a frozen snapshot.
**Measures.** Recovered fraction versus sampling density against the `56`-sample precedent.
**Counts against.** §26.19's statement that a snapshot is not an invertible representation of the field; full recovery would contradict it.
**Run.** Read-only, bounded by snapshot limits; reconstructible mechanics; rendering cannot create observations.

### C.8 Relation-guided placement
**Status.** Nearest analogue is the binding allocator: prefer the pool holding the most already-bound variables from admitted chart scopes, then least occupied, then lowest identity (§26.4) — not relation-guided placement.
**Measured (placement).** Greedy choice over all `784` write/read pairs beats the declared binding order by `1.8678148349343988` at depth `2` in `helix7` but ends at `0.9386358118225462` at depth `7`, the restricted reorder of the seven declared pairs beats it by at most `1.2471229232579588`, and the best pair there is the self-pair `(0, 0)` at transfer `0.8357831008621412` — so the declared order is beaten at shallow depth and the greedy advantage does not hold to depth `7` (`_diag/fractal-placement/exploration.json`).
**First step (INFERENCE).** Place ports at the variables named by the supported relation being condensed and compare retained accuracy against arbitrary ports.
**Measures.** Held-out error against the recorded `3.4902023479447672` prediction for target `3.5`, absolute error `0.009797652055232753` (§27.5).
**Counts against.** No improvement over arbitrary ports, weakening the placement half of the program.
**Run.** One condensation plus one held-out measurement; reconstructible mechanics; condensation still trains no separate weights (§27.1).

## D. Connection structure

### D.1 Strictly local coupling
**Status.** Present: `ResonantProfile.edges` builds metric-weighted intra-pool and neighbouring-pool exchange edges; the circuit is local in pool coordinate (§26.4).
**Measured.** The strictly local `isolated` arrangement, whose cross-pool strength is `0.0` and whose rail is intra-only at `0.5574148972939752`, retains `0.9070591118113311` against `helix7` `0.9070808366086672`, so deleting every cross-pool link barely moves 64-tick retention (`_diag/fractal-geometry/exploration.json`).
**First step (INFERENCE).** Measure reach versus tick count for a strictly local edge set to establish local propagation speed as the reference for D.2.
**Measures.** Distance reached per unit field time from measured transfer.
**Counts against.** Reach saturating before crossing adjacent pools, making local coupling insufficient for cross-scale memory.
**Run.** `max_ticks_per_batch = 64` per batch; reconstructible mechanics.

### D.2 Sparse long-range links
**Status.** Nothing exists; `rewired` is a comparison partner, not a designed long-range set.
**Measured.** `sparse-long-link`, a declared long-range set at strength `13.6` with cross-pool strength `1.0406536888666962`, retains `0.9070782070287032` — within `1.4978129159182174e-06` of the matched `flat-ladder` at the same mass metric (`_diag/fractal-geometry/exploration.json`).
**First step (INFERENCE).** Add one long-range edge per pool pair at matched total strength, replacing an equal amount of local strength.
**Measures.** Reduction in ticks-to-reach against loss of localization at matched bytes and operator applications.
**Counts against.** §26.24's finding that meaningful and rewired bodies both have 90 edges and strength `1.7134218127191345` and both predict their own responses.
**Run.** One profile variant per run; reconstructible mechanics; needs validator support for the new topology string.

### D.3 Upward and downward scale connections
**Status.** One declared L→LL field-level application now exists: a frozen register is prolonged through the native LL impulse, not a general upward/downward graph.
**Measured.** The frozen-parent receipt reports distinct LL final states for parent-on and parent-off, with zero LR sibling delta; it is one field-level causal wiring path, not a general hierarchy measurement.
**First step (INFERENCE).** Extend beyond this one declared relation to a second level or relation, then test whether a child impulse reaches a parent scale without passing through every sibling.
**Measures.** Parent-scale response against sibling activation count.
**Counts against.** Sibling activation rising in proportion to sibling number, showing cross-scale access is not selective.
**Run.** Bounded; reconstructible mechanics; §26.18's lost-energy and semantic-error accounting applies to any upward coupling that drops details.

### D.4 Lateral connections
**Status.** Present: exchange edges connect neighbouring pools, and both strands occupy every paired port (§26.4).
**Measured.** Lateral structure is the one graph feature the comparison isolates: density-matched rail changes move per-pool retention by at most `0.00011141722933116771`, while mass-metric changes move it by `0.03436382025490936` and `0.03435675520060377` (`_diag/fractal-geometry/exploration.json`).
**First step (INFERENCE).** Excite one pool and record same-layer neighbour responses, separating same-strand from cross-strand contributions.
**Measures.** Neighbouring-pool cross-talk at matched strength.
**Counts against.** Cross-talk at or above own-pool response, making lateral connections a liability.
**Run.** One sweep; reconstructible mechanics; the `0.9153`–`0.9707` own-pool fractions bound the expectation.

### D.5 Reciprocal versus directed coupling
**Status.** Present and constrained: transport is antisymmetric with a declared orientation and antisymmetric reverse entry, checked in `__post_init__` (§26.4).
**First step (INFERENCE).** Compare the conservative directed graph against an explicitly dissipative directed variant at equal total strength.
**Measures.** Readout difference and any change in the source/dissipation balance, using the recorded `5.11e-19` defect convention (§26.24).
**Counts against.** A change only through added dissipation with no structural consequence.
**Run.** Requires declaring a relaxation of the antisymmetry check; §26.4's antisymmetry is a constraint to declare rather than silently relax.

### D.6 Higher-order (triple and beyond) interactions
**Status.** Present only as the quartic relative term `beta/4 * sum d_j^4` with `beta = 0.08` (§26.5, §26.20); explicit three-body port coupling does not exist.
**First step (INFERENCE).** Add a bounded triple-product term on one port triple and count distinguishable states against the quartic term alone.
**Measures.** Distinguishable stable or metastable configurations at matched total energy.
**Counts against.** §27.2's record that nonlinear `beta > 0` responses retain the full wave operator with no dimension reduction: a term buying no new state adds cost without content.
**Run.** Nonlinear integration uses the full operator, so respect `max_operator_effort`; nonlinear work is not compressible today.

### D.7 Context-dependent connections
**Status.** Partly present: `topology` selects among four profiles and `projected_transport` can carry a modified antisymmetric operator (§26.4), but no edge changes with active context or branch.
**First step (INFERENCE).** Make one edge weight depend on the declared active branch identity and test whether two branches hold distinguishable readouts from the same charts.
**Measures.** Branch-separated readout difference against the recorded `2.574385` phase-conditioned difference (§26.24).
**Counts against.** §26.4's rule that transport never averages incompatible branches: silent branch leakage violates it rather than demonstrating a feature.
**Run.** Descriptor-level; reconstructible mechanics; branch-local state identity must survive.

### D.8 Distance-dependent strength and delay
**Status.** Strength is present and metric-derived (§26.4); delay exists only at the transceiver level as a declared one-tick connection delay (§27.3).
**First step (INFERENCE).** Add an explicit per-edge transport delay and measure whether arrival timing at two equal-strength, different-length edges carries information.
**Measures.** Timing-resolved response against the recorded quadrature errors `1.437e-3`, `3.409e-4`, `7.591e-5` at intervals `0.08`, `0.04`, `0.02` (§26.24).
**Counts against.** Timing unresolvable above those errors at the current step.
**Run.** The measured refinement bounds the claim; reconstructible mechanics; must not break the discrete gradient (§26.11).

## E. Recurring dynamics

### E.1 Localized nonlinear states
**Status.** Localization is measured (own-pool fractions `0.9153`–`0.9707`, §26.24) and the relative coordinate carries the quartic term (§26.5), but no persistent localized state is reported.
**First step (INFERENCE).** Drive one pool with a bounded impulse and search a bounded energy range for a state still localized after the drive is removed.
**Measures.** Residual localization after source removal, against the passive decay §26.7 requires when the heartbeat is off.
**Counts against.** Survival bounded by the `0.012` damping rate (§26.20) rather than by nonlinear trapping.
**Run.** Bounded by `max_ticks_per_batch` and the nonlinear operator budget; reconstructible mechanics.

### E.2 Multiple stable states
**Status.** Not established for the continuous body; the temporal path keeps competing contexts distinct with 36 initial states growing to 43 and 39 (README), but those are categorical.
**First step (INFERENCE).** Integrate several declared initial conditions per pool band to equilibrium with sources off and count distinct terminal patterns.
**Measures.** Terminal-pattern count and basin sizes.
**Counts against.** One terminal pattern for all initial conditions, or a count tracking numerical noise.
**Run.** Passive relaxation well inside budget; reconstructible mechanics; §26.21 requires rejecting a nonfinite or invalid state rather than rounding it.

### E.3 Metastable states
**Status.** Not established; §26.4 notes that neck conductance and cavity inertance determine localization and dwell time, and requires measured response to establish distinguishable pools.
**First step (INFERENCE).** Measure dwell time per pool band under a fixed small perturbation and compare it with the breath period.
**Measures.** Dwell-time distribution relative to breath phase.
**Counts against.** Dwell times equal to the inverse damping rate, showing no structure beyond linear relaxation.
**Run.** Bounded passive integration; reconstructible mechanics; breath stays a deterministic regulator, not a learned policy (§26.8).

### E.4 Standing-wave modes
**Status.** Structurally present: the frozen generator is `L = nu (J - Gamma) grad^2 H` (§26.19); the reference body measured seven peaks and fourteen positive-frequency eigenvalues (§26.23).
**First step (INFERENCE).** Excite each measured peak at its own frequency, record mode shapes, and test whether two modes coexist without destroying each other.
**Measures.** Mode-shape overlap matrix and cross-damping.
**Counts against.** Pairwise overlap so high that no two modes are simultaneously addressable.
**Run.** Forced response at bounded amplitude; reconstructible mechanics; §26.19's warning that a quadrature argument is not automatically an eigenmode phase binds interpretation.

### E.5 Traveling packets and circulating sequences
**Status.** Present: the heartbeat is a powered circulation source (§26.7) with measured signed circuit-power `9.73e-8`, and skill formation walks `prime -> align -> open` with signals `[1/sqrt(3), 0, 0, 1/sqrt(3), 0, 0, 1/sqrt(3)]` (README).
**First step (INFERENCE).** Inject a short ordered impulse sequence at one port and read that port later to test whether the sequence is retained as a traveling pattern.
**Measures.** Later-time readout discriminability between two orderings against the recorded `0.5377682406803815` ordering effect (§27.5).
**Counts against.** Order-independent later readout, meaning circulation carries no sequence.
**Run.** Two sequences at bounded amplitude; reconstructible mechanics.

### E.6 Winding and linked structures
**Status.** The embedding declares one complete turn across seven pool intervals (§26.4) and cites a winding-quantized construction, but no winding is measured.
**First step (INFERENCE).** Compute the paired-strand phase winding around the circuit over one breath period from a bounded run.
**Measures.** Integer winding per period and its stability across initial conditions.
**Counts against.** A winding that is not integer-stable, meaning linking describes a drawing rather than an invariant.
**Run.** Readout arithmetic on one bounded run; §26.4 states the pitch is engineering geometry, not a canonical winding theorem.

### E.7 Ordered, transitional, and chaotic regimes
**Status.** Not characterized; the reference body is damped (`0.012`) with a bounded source, so the expected regime is ordered, and §26.21 makes detuning reportable.
**First step (INFERENCE).** Sweep heartbeat work across a bounded range and classify each point by peak sharpness and response reproducibility.
**Measures.** Peak Q factor and run-to-run agreement per point.
**Counts against.** A reproducible regime with no distinguishable peaks, or a regime that is not reproducible at all.
**Run.** Each point is a bounded run; the `0.006` per-beat ceiling (§26.20) keeps the sweep narrow.

### E.8 Alternative pattern-forming mechanisms
**Status.** Interference and resonance are implemented; an excitable ring exists in `cassi_constraint_dynamics.py` but drives solver decisions, not the resonant body.
**First step (INFERENCE).** Reuse the excitable ring law on the port set and compare retained patterns against the resonant body at matched work.
**Measures.** Distinguishable retained patterns per unit work.
**Counts against.** Cheaper but restart-unstable patterns, failing the durability requirement.
**Run.** Existing bounded kernel; reconstructible mechanics; §26.1 keeps the body as numerical structure, so a second law must remain a variant of the same field.

## F. Time, phase, strands

### F.1 Frequency hierarchies
**Status.** Partly present: inertance is a geometric ladder `m_i = 1.3**i` (§26.20) and measured peaks fall from `0.979583` to `0.434167` (§26.24); no designed hierarchy across nested scales exists.
**Measured.** The coarsest rung holds `0.003380437390550838` of the deposited energy along the driven direction after 256 ticks against `0.17236141393990917` for the finest, while total packet energy ratio stays between `0.5506036009198637` and `0.6260661715482054` — so the rungs differ in directional retention, not in total energy (`_diag/fractal-memory/exploration.json`).
**First step (INFERENCE).** Assign one inertance band per nesting level in a depth-two scaffold and measure whether level peaks separate cleanly.
**Measures.** Peak separation between levels against separation within a level.
**Counts against.** Overlapping bands, making a level indistinguishable from its parent.
**Run.** One profile plus one sweep; `m_i` stays declared profile, since learned gains must be supported relations (§26.3).

### F.2 Independent memory lifetimes (frequency is not persistence)
**Status.** Separated in design and code: three clocks are kept distinct (§26.9) and §26.1 states epistemic type, lifetime, and persistence are independent; not measured is whether a fast mode can outlast a slow one.
**Measured.** Rung width orders directional retention but not monotonically with width: retained projection after 256 ticks is `0.003380437390550838` at width 28, `0.0005481693441272088` at width 14, `0.08970751453852188` at width 7, and `0.17236141393990917` at width 3 (`_diag/fractal-memory/exploration.json`).
**First step (INFERENCE).** For two modes at different frequencies, measure each decay time under the same dissipation and drive.
**Measures.** Decay time per mode versus frequency.
**Counts against.** Decay time a strict function of frequency, collapsing this direction into F.1.
**Run.** Two bounded passive decays; §26.10's `2 nu_min gamma mu_H` rate applies only under its stated hypotheses.

### F.3 Relative-phase encoding
**Status.** Present in readout: §26.13 requires quadratures, forbids subtraction across the phase wrap, and reports missing phase below an amplitude threshold; the viewer reports `R = |mean exp(i(theta_Y - theta_I))|`.
**First step (INFERENCE).** Encode one bit per pair as the sign of the relative phase and measure recovery after a bounded delay.
**Measures.** Recovery versus delay, and the amplitude floor where phase becomes undefined.
**Counts against.** Chance-level recovery at delays inside the measured decay window.
**Run.** Bounded; reconstructible mechanics; the §26.13 threshold rule is a constraint — below it the result is missing phase, not zero.

### F.4 Common and difference channels
**Status.** Present by construction: §26.5 defines `x = (q_Y + q_I)/sqrt2` as the semantic workspace and `d = (q_Y - q_I)/sqrt2` as the resonant lift, and the packet basis has common/counterflow channels (§26.18).
**Measured.** Common and counterflow lanes are distinguishable but not independent: driving momentum-common leaves `0.5941439169696623` on its own channel and `0.046214265960628` on momentum-counterflow, while the largest cross-family term is `0.6428602403846356` from position-common to momentum-common (`_diag/fractal-memory/exploration.json`).
**First step (INFERENCE).** Write one item into the common channel and a rival into the difference channel, then test recovery of each.
**Measures.** Cross-channel recovery, i.e. whether reading `x` disturbs `d`.
**Counts against.** Mutual disturbance above the declared roundoff allowance.
**Run.** Two impulses plus readout; §26.18's statement that these are a view of the same four words means independence would be a finding, not a restatement.

### F.5 Cross-frequency interaction (beats, locking, conversion)
**Status.** Unmeasured as a memory mechanism; §26.2 cites `de-resonance-principle.md` §1.2 that a frequency ratio alone determines neither locking, transfer, stability, nor useful computation.
**First step (INFERENCE).** Drive two pools at nearby frequencies and record whether a beat envelope appears and whether its phase is readable.
**Measures.** Beat frequency and envelope-phase stability.
**Counts against.** An envelope too unstable to read; the cited constraint also forbids claiming locking from the ratio alone.
**Run.** Bounded forced response; the correct tool is the measured transfer `T(omega) = C(i omega I - L)^{-1} B` (§26.19), not a static Hessian.

### F.6 Selective resonance
**Status.** Implied by measured peaks and localizations, not demonstrated; §26.10 withholds new heartbeat work without a conservative positive bound, and §26.8 describes demand pacing.
**First step (INFERENCE).** Excite one on-resonance and one off-resonance pool together and measure accumulated energy in each.
**Measures.** Addressed-to-unaddressed energy ratio.
**Counts against.** Ratio near one, meaning a bounded source with a phase-integral allocation (`F(theta)`, §26.7) does not select.
**Run.** Bounded; reconstructible mechanics; the `0.006` per-beat ceiling bounds the achievable ratio.

### F.7 Sustained versus intermittent drive
**Status.** Both exist: the heartbeat runs continuously in a persistent owner, while rest lowers demand and a paused owner has no heartbeat work (§26.14); their effect on retained structure is uncompared.
**First step (INFERENCE).** Run one body continuously and one in bursts at equal total work, then compare retained patterns.
**Measures.** Retention difference at equal total work.
**Counts against.** §26.14's rule that rest cannot execute an action, create an observation, or raise source confidence bounds what may be attributed to scheduling.
**Run.** Equal-total-work comparison inside the existing ledger; equal received work, not requested, is the honest comparison.

### F.8 Local versus global clocks
**Status.** Three global clocks exist — evidence logical tick, field time, wall time (§26.9) — and hidden catch-up is rejected: restart never silently simulates missed beats; no per-region clock exists.
**First step (INFERENCE).** Give one nested level a subdivision counter distinct from field time and test whether level-local timing is recoverable after restart.
**Measures.** Recovered local phase after exact restart against the global counter alone.
**Counts against.** Local timing fully derivable from the global counter, showing the extra clock adds nothing.
**Run.** A real local clock is new adaptive state and must be declared in the canonical field; §26.9's no-accidental-forgetting rule binds.

## G. Write, retrieve, representation

### G.1 The durable storage medium question
**Status.** Open by design: §26.1 keeps learned memory, provisional work, and acknowledged outcomes distinct, and §26.13 says the wave becomes durable knowledge only through an admitted supported update. The memory harness measured departure-and-relaxation in packet coefficient space once, without any checkpoint: with the heartbeat on, the control arm drifts to `0.02616802125195171`, a small disturbance to `0.02644077052253202`, and a large one to `0.030227999631645543`; with the heartbeat off, the same disturbances relax to `0.0019031772406660008` and `0.013457592303609243` from a zero control. Neither condition restores the reference, so this is decay accounting, not demonstrated storage.
**Measured.** The durability harness writes one declared item at budget `0.001` and reads it back in the declared read frame: recovery is `1.0` with no activity and `1.0` after an exact `ResonantWorkspace.as_dict`/`from_dict` round trip — state digest and page digest identical, read-frame maximum absolute difference `0.0` — and `0.29462880739045766` after `64` ticks of bounded canonical activity with sources and heartbeat on, identical with and without that restart, so the identity established is workspace-level restart identity for a written item and not a durable store, the owner transition surface exposing no packet-impulse operation (`owner_checkpoint_carries_written_item` false, `prepared_query_addressed_written_packet` false) (`_diag/fractal-durability/exploration.json`). The survival receipt shows that figure is scaffold-dependent rather than a property of the written item alone: the same declared item on the same declared activity recovers `0.3481552374975245` on `nested-core-shell` and `0.2702850816137677` on `recursive-paired-loops` against the `0.29462880739045766` default, and the `k = 4` gap is far wider — `0.3351631005750861` on `nested-core-shell` against `0.0764836820747603`, a difference of `0.2586794185003258` against the declared `0.02` margin — so what is stored and how long it lasts both depend on which declared scaffold carried it (`_diag/fractal-survival/exploration.json`).
**Measured (retrieval).** A declared consumer does read a written direction back through the owner's own `read_packet_deposit` and act on what it read, on one declared profile, one declared policy and one declared budget: the target direction's deposit reads `0.005023718074326502` against a declared floor of half the freshly captured deposit (`0.002511834142857143`), and the act lands along the remembered direction with share `1.0`, against `0.0` with nothing written and `3.229441440156545e-66` when the same page and the same write carry a suppressed read. What does not follow is a store: the act is itself an owner write, and it doubles the deposit it read, `0.005023718074326502 -> 0.01004738636004079`, with no non-destructive actuator on the public surface (`_diag/memory-consumer-path/exploration.json`). The memory store scale receipt measures the other half of that sentence: a non-destructive act does exist, but on a declared coupled input realization built from the owner's own written page and driven outside the owner's surface, where the readout moves `0.00042512371321049393 -> -0.0034833204837238702` while all four of the owner's declared surface digests stay byte-identical and the stored read is unchanged; no operation writes that realization's state back into the page, so the owner's write path remains the only actuator that moves the owner's page (`_diag/memory-store-scale/exploration.json`).
**First step (INFERENCE).** Write one bit through `packet-impulse`, checkpoint, restart, and read it back through the prepared-query path, so the bit lives in `resonant_workspace` rather than a chart.
**Measures.** Bit recovery after exact restart and after bounded unrelated work.
**Counts against.** §26.24's record that readouts are frozen against unrelated heartbeats: a bit surviving only while nothing else happens is not durable.
**Run.** One checkpoint round trip; the conflict to state plainly is §32.3's separation of learned state from provisional work.

### G.2 Localized versus distributed writing
**Status.** Both available: `apply_helical_packet_impulse` writes one mode, and skill coupling divides `1e-3` of admission work between two common-mode impulses of `5e-4` each (README).
**Measured.** Independent items written at the same per-item budget of `0.001` interfere as they accumulate: after restart plus activity the minimum per-item recovery is `0.0039787604750989355` at `k = 2`, `0.0764836820747603` at `k = 4` and `0.05063053711608721` at `k = 8`, the read packet's declared-frame share rises `0.3443303224621802` → `0.4811366377266782` → `0.5871936760100912`, and a later write deposits as little as `0.440745721562222` of its isolated capture — so the interference half is measured at three item counts while the localized-versus-distributed comparison itself remains unmeasured (`_diag/fractal-durability/exploration.json`).
**First step (INFERENCE).** Write the same bit localized and distributed at equal total energy, then compare recovery, cross-item interference, and read disturbance.
**Measures.** Recovery rate and cross-item interference at equal work.
**Counts against.** §26.24's report that coupled power reaches all seven pools after eight ticks: distributed writing may reach everything without distinguishing anything.
**Run.** Four bounded runs; reconstructible mechanics.

### G.3 Alternative encodings (amplitude, sign, relative phase, order)
**Status.** All four reachable — packet coefficient, signed generalized power, pair-phase statistic, and the transceiver's measured input-order dependence — but none characterized as an encoding.
**First step (INFERENCE).** Encode the same three-symbol message four ways and measure error rate at fixed delay.
**Measures.** Symbols recoverable per unit energy per encoding.
**Counts against.** An encoding not exceeding the ambiguity already present in the frozen-rest calibration (§26.24).
**Run.** Sixteen short runs; §26.13's phase threshold and §26.19's non-invertible rendering bound the options.

### G.4 Coarse content plus explicit detail
**Status.** The strongest precedent remains the packet hierarchy, which retains parent scale plus descendant details losslessly to roundoff; a separate frozen L→LL probe now applies a parent signal at the native child scale, but does not encode coarse content or a semantic query.
**First step (INFERENCE).** Store one item as coarse content plus a detail, answer a coarse query from the coarse part alone, and a precise query by descending.
**Measures.** Work and activated-port count for coarse versus precise queries.
**Counts against.** A precise query activating as much as the whole body; §33.10 also forbids a coarse state erasing a needed distinction.
**Run.** Uses the existing packet API and reasoning frontier; reconstructible mechanics.

### G.5 Associative retrieval
**Status.** Partly present: categorical temporal inference consumes only the current event, shares states across compatible continuations, and keeps conflicting outcomes distinct (§28.2); partial-key retrieval of a resonant pattern is untested.
**First step (INFERENCE).** Write three patterns, corrupt one, and read back candidate matches within a bounded tick count.
**Measures.** Correct-match rate versus corruption fraction and tick bound.
**Counts against.** Correct retrieval only at corruption within numerical noise.
**Run.** Bounded read-only; §28.2's rule that uncertainty clears only on fully supported evidence is the anti-false-completion constraint.

### G.6 Readout from boundaries
**Status.** Not implemented; transceivers read declared output ports at one tick (§27.3) and the viewer reads a snapshot (§26.19), neither a scaffold boundary.
**First step (INFERENCE).** Read only at the two scaffold endpoints and test whether an interior item is recoverable from them.
**Measures.** Recovered fraction from endpoint readout versus full readout.
**Counts against.** Endpoints recovering nothing until the state is nearly quiescent, making boundary readout a slow channel.
**Run.** Read-only after a bounded run; §27.3's rule that a transceiver response cannot authorize an effect applies to any boundary readout.

### G.7 Context-separated retrieval
**Status.** Present categorically: 12 participant contexts recovered online and six under frozen memory, with shared-ingredient contexts kept separate (README, §28.2).
**First step (INFERENCE).** Write the same nominal key in two contexts and test whether retrieval returns the context-appropriate item without activating the other.
**Measures.** Correct-context rate and cross-context activation.
**Counts against.** Cross-context activation at or above the correct-context level.
**Run.** Bounded; §26.4 requires Boolean and symbolic alternatives to stay typed branches rather than metric coordinates.

### G.8 Compositional retrieval
**Status.** Present and measured: connected composition reaches pooled held-out RMSE `0.02565` without observing the new pairs, against `0.01619` directly trained and `1.95717` for the prior (README); composition requires ordered siblings from one source state.
**First step (INFERENCE).** Build a query from parts stored separately and test retrieval of the combination with the same-state rule enforced.
**Measures.** Composition error against the `0.02565` and `0.01619` precedents at matched retention.
**Counts against.** Composition error no better than the prior, meaning the scaffold does not support recomposition.
**Run.** Bounded; the existing refusal of cross-source composition is a rule to preserve.

## H. Development

### H.1 Task-directed transceiver insertion
**Status.** Insertion is explicit: `condense_transceiver` derives a realization from named charts and ports, and §27.1 states the compiler does not autonomously discover a decomposition.
**First step (INFERENCE).** Rank candidate insertion sites by a bounded utility estimate from actual computation cost, admitted through the ordinary evidence path (§32.16).
**Measures.** Estimate versus later measured cost at the chosen site.
**Counts against.** An estimate no better than the deterministic allocator's ranking (§26.4).
**Run.** Bounded selection plus one condensation per site; a learned ranking is new adaptive state and belongs in the canonical field.

### H.2 Information-preserving relocation and rebinding
**Status.** Present but deliberately expensive: expansion doubles the needed pool's ports and publishes a layout transition, and rebinding occupied ports requires the §26.18 transformation and error accounting (§26.4).
**First step (INFERENCE).** Move one stored item to a zero-initialized port at equal resolution using only the exact path and read it back.
**Measures.** Recovery after relocation against the declared roundoff allowance.
**Counts against.** Loss beyond the allowance on the exact path.
**Run.** One layout transition; seven macro-pools stay seven and occupied modes are never silently dropped (§26.21).

### H.3 Growth and pruning
**Status.** Present as `expand_resolution`/`reduce_resolution` with declared certificates and as owner capacity management (§32.16); automatic pruning of resonant structure does not exist.
**First step (INFERENCE).** Reduce resolution of one level while a foreign bit lives in another and test whether the foreign bit survives.
**Measures.** Foreign-bit recovery after a local reduction, with recorded lost mode energy.
**Counts against.** §26.21's rule against silently dropping evidence or occupied modes: dropping an unrelated occupied mode is a defect.
**Run.** Two layout transitions; the measured reduction errors `0.00252243` and `0.00130892` bound the claim.

### H.4 Activity-driven self-organization
**Status.** Not implemented; structural change is explicit, and §32.16 states a cache hit cannot alter logical fuel or create adaptive feedback.
**First step (INFERENCE).** Accumulate edge-weight observations as supported evidence and let an admitted structural revision consume them rather than editing weights in place.
**Measures.** Whether the evidence-derived change reproduces the direct-edit structural change at matched evidence.
**Counts against.** §26.1 forbids a per-pool Hebbian matrix or oscillator-weight learner; a change that is not an admitted supported update is out of scope.
**Run.** Bounded; the new state must be chart evidence, not a sidecar.

### H.5 Splitting and merging regions
**Status.** Not implemented; direct-sum behaviour is characterized only in the solver work, where frame structure is closed under direct sums and widths combine by maximum (README).
**First step (INFERENCE).** Split one pool's ports into two declared sub-regions at equal total ports and test whether the parent peaks are recoverable.
**Measures.** Peak recovery after split and after re-merge.
**Counts against.** Parent peaks lost on split.
**Run.** One profile variant; §32.6 describes entity merge and split as versioned correspondence changes invalidating dependents.

### H.6 Error-directed restructuring
**Status.** Substantially present categorically: structural learning is triggered by retained unresolved distinction, systematic prediction error, or recurrent plan repair (§33.12), and the reasoning path publishes an invalidation barrier (README).
**First step (INFERENCE).** Route one measured recovery failure into the existing repair path and observe whether the repair changes a placement or a scale choice.
**Measures.** Whether the repair acts on scaffold structure or only on a chart.
**Counts against.** §33.12's requirement that an abstraction replace a repeated computation in the live computer.
**Run.** Bounded; uses existing retained work; dependent reads stay refused until known causes are checked.

### H.7 Slow structural consolidation
**Status.** The default is the opposite: the heartbeat does not advance the evidence clock and no accidental forgetting follows from separate clocks (§26.9); §33.20 permits consolidation preserving declared distinctions and lineage.
**First step (INFERENCE).** Define one consolidation — merging two scales whose responses fall inside a declared tolerance — and record exactly which questions become unanswerable.
**Measures.** Storage or work saved against the listed unanswerable questions.
**Counts against.** §33.20's rule that a gain destroying a rare required exception is unacceptable consolidation.
**Run.** Bounded; consolidation is an assessed operation with new lineage state and must preserve open obligations and revocation fences.

### H.8 Transfer across tasks and modalities
**Status.** Measured for skills and temporal memory: fresh participants complete `6/6` transfer tasks in `108` interactions while frozen memory completes `0/6` in `204`, and six reduced-sensory modalities reach `18/18` (README); no scaffold analogue exists.
**First step (INFERENCE).** Use one scaffold for two challenge families and check that first-task placement is not worse than arbitrary on the second.
**Measures.** Second-task recovery at first-task placement versus a matched alternative.
**Counts against.** Placement worse than arbitrary on the second task, i.e. overfitting.
**Run.** Two bounded challenge runs; the `0/6` frozen baseline is the control to keep.

## I. Stability, capacity, fidelity

### I.1 Recovery after disturbance
**Status.** Present at owner level: exact restart, retry idempotency, interrupted-batch recovery, and rejection of a checkpoint crossing the revocation fence are exercised (§26.24, README); pattern recovery after a structural disturbance is untested. The memory harness measured the disturbance-response shape once over a 4096-tick horizon at 512-tick stride: under live activity a large disturbance leaves a final excess of `0.004059978379693834` and a small one `0.00027274927058031084`, while with activity off the same arms relax to `0.013457592303609243` and `0.0019031772406660008`; the live condition's own control drifts to `0.02616802125195171`, so live recovery is not separable from ongoing drift.
**First step (INFERENCE).** Zero one port band, advance a bounded number of ticks, and test whether a foreign pattern elsewhere is unaffected and the disturbed band recovers.
**Measures.** Foreign-band and disturbed-band recovery versus tick count.
**Counts against.** Spread beyond the disturbed band at more than measured cross-talk.
**Run.** Bounded passive ticks; §26.21's rollback rule applies if the step fails.

### I.2 Avoiding one dominant attractor
**Status.** An explicit design concern rather than an implemented guard: §33.10 rejects merging repeated tokens, §33.20 requires retaining rare exceptions, §18.1 represents capacity, and §26.21 lists merged responses as reportable.
**First step (INFERENCE).** Run a long bounded passive integration from several initial conditions and record whether response peaks remain separated.
**Measures.** Distinguishable peak count at the end versus the start.
**Counts against.** Peak merging during an unforced run, which §26.21 requires to be reported rather than concealed.
**Run.** Bounded by the tick limits but longer than one batch; reconstructible mechanics.

### I.3 Interference and capacity limits
**Status.** Limits are explicit and enforced: `max_ports = 1_000_000`, `max_workspace_bytes` and `max_state_bytes` both `64 * 1024 * 1024`, `max_ticks_per_batch = 64`, `max_operator_effort = 4096`, `max_history_entries = 4096`, `max_pending_operations = 1024`; interference between stored items is now measured at three counts — the durability receipt's restart-and-activity arms at `k = 2/4/8` report minimum per-item recoveries of `0.0039787604750989355`, `0.0764836820747603` and `0.05063053711608721`, with no refusal up to `k = 8` and a sequential-write deposit attenuation as low as `0.440745721562222` of the isolated capture (`_diag/fractal-durability/exploration.json`) — while the `k` at which refusal replaces degradation remains unmeasured. The survival receipt adds the same interference at fixed item count but varying declared scale spacing: at `k = 2` on the declared default profile, a near pair (`left-detail` with `right-detail`, declared scale distance `0`) reads minimum per-item recovery `0.051463903480489785` with maximum off-diagonal deposit share `1.5938203196470795`, a far pair (`root-scale` with `right-right-detail`, distance `2`) reads `0.37505473969085323` and `1.1418392277684646`, and the distance-1 pair (`left-detail` with `left-left-detail`) is the outlier with the largest unwritten-direction fraction `0.6927050860352755`; so placing items at the same declared scale depth costs recovery even when the declared directions are orthogonal within the `1e-24` allowance, while the confusion ordering itself tracks the projected connection graph rather than the mass metric: it survives the rail change alone and inverts once only the mass metric changes (`_diag/fractal-survival/exploration.json`).
**First step (INFERENCE).** Store `k` items at fixed energy per item and measure recovery of each as `k` grows.
**Measures.** Items recoverable per unit work versus `k`, and the `k` at which refusal replaces degradation.
**Counts against.** §26.21 requires refusal rather than silent dropping, so a curve that never refuses would mean the accounting is not being reached.
**Run.** Bounded by the byte limits; actual operator applications are the accounting convention, not nominal steps.

### I.4 Selective revision
**Status.** Present and measured: a selective knowledge intervention changes one transceiver's response by `2.9988190742743757` while the unrelated transceiver stays intact (§27.5), and revocation removes only affected derived kernels (§27.4).
**First step (INFERENCE).** Apply the same pattern to a wave-stored item: overwrite one and measure whether a second changes.
**Measures.** Unrelated-item change after a targeted overwrite.
**Counts against.** Any measurable change in the unrelated item, showing wave storage lacks chart storage's revision locality.
**Run.** Bounded; the `2.9988190742743757` precedent sets the intended-change scale.

### I.5 Read disturbance
**Status.** Partly addressed: §26.13 gives readout semantics without writing, §26.24 freezes readouts against unrelated heartbeats, and the viewer cannot feed pixels back; readout-induced perturbation of a wave-stored pattern is measured at the store level against a declared `0.05` band but not against the `2e-12` `ResonantProfile` tolerance.
**Measured (read neutrality).** The owner's own read of a written direction, taken on the held page, changes no page digest and no generation and returns the same readout when repeated, in each of the receipt's declared episodes; what moves the deposit is the consumer's *act*, not its read — one owner write of the direction it read doubles the owner-side recovery of that direction, `0.005023718074326502 -> 0.01004738636004079` (`_diag/memory-consumer-path/exploration.json`). Drift of the stored pattern under repeated reads was unmeasured there and is now measured at the store level: over eight rounds that read every declared direction at every stage, the cells of the items the consumer has not yet acted on move by `5.551115123125783e-16` at most against the receipt's declared `0.05` allowance, while the acted items' cells leave that band by the act's own doubling (`_diag/memory-store-scale/exploration.json`).
**First step (INFERENCE).** Read one pattern `n` times and measure drift in it and in an unrelated pattern.
**Measures.** Drift versus `n` against the `2e-12` `ResonantProfile` tolerance and the declared roundoff allowance.
**Counts against.** Drift above tolerance, making repeated reads lossy.
**Run.** Bounded; the prepared-query path, which reads without another solve (§26.24), is the non-disturbing alternative.

### I.6 Evidence versus generated activity
**Status.** Enforced: §26.13 consumes external observations once, §32.3 admits telemetry for learning only with identity and dependencies in the field first, and §27.3 labels transceiver outputs `temporal-prediction` and adds no observed support.
**Measured.** The read's declaration is now measured both ways on one declared profile. As shipped it is a `temporal-prediction` with `evidence_added` false: it moves no evidence clock, no logical tick and no evidence-store event, and `0` of the `2649` leaves on the four declared surfaces diffed. The same recovered deposit declared as evidence through the owner's own admission rule moves the evidence clock `0 -> 1`, adds one evidence-store event and one declared contribution, and moves `29` of those `2649` leaves — `13` clocks, `11` digests, `2` counts, `2` resources and `1` version — of which `0` are decision inputs, while the written page stays fixed under both (`_diag/owner-surface-options/exploration.json`).
**First step (INFERENCE).** Compare evidence clock and support counts before and after a bounded read-and-replay cycle.
**Measures.** Evidence-clock and support-count deltas across a pure read cycle.
**Counts against.** Any nonzero delta, a direct violation of the stated separation.
**Run.** Bounded; this checks an existing rule rather than adding a capability.

### I.7 Energy and work accounting
**Status.** Complete for the body: each batch reports start/end energy, learned-memory identity, positive heartbeat work, extracted work, dissipated work, observation/parameter/layout/boundary work, residual work, and the balance defect — measured at `5.11e-19` (§26.10, §26.24).
**Measured.** The same ledger closed across eight repeated drive cycles at `0.001` per cycle over 64 ticks: relative closure residual `-8.673617379884035e-19` against a `1e-12` allowance, accumulated balance defect `-5.670750429884193e-19`, maximum absolute phase defect `2.087998046107861e-18`, final measured energy `0.007537496474352549` under a `1.0` ceiling (`_diag/fractal-memory/exploration.json`).
**First step (INFERENCE).** Add a pattern-write category so storing an item is charged as work rather than absorbed.
**Measures.** Balance closure with write work broken out, and per-item write cost.
**Counts against.** A balance closing only when writes are unaccounted, which §32.16 forbids as moving cost into unreported work.
**Run.** Uses the existing ledger; reconstructible mechanics.

### I.8 Finite precision and resolution
**Status.** Declared and partly measured: cells are canonical nonnegative u32 words represented exactly in float64 (§32.4), CPU/GPU agreement is `1.73e-12` against a `1e-8` allowance (§26.24), and the transceiver tolerance is `2e-12`.
**First step (INFERENCE).** Find the smallest pattern amplitude surviving a checkpoint round trip and a bounded number of ticks.
**Measures.** Amplitude floor for reliable recovery.
**Counts against.** A floor high enough to bound useful capacity far below the port count.
**Run.** Bounded; §32.4 requires any packed backend to preserve the same logical words and digest semantics.

## J. Mathematics

### J.1 Renormalization and closure across regions
**Status.** Static reduction exists with measured limits: §26.18 gives the exact Schur reduction for a declared boundary, states that a zero-frequency Schur complement in place of `L_AB exp(L_BB (t-s)) L_BA` loses delay and resonance, and reports conservative bounds `3.41e4` and `4.87e4`. The memory harness measured the analysis-order side once: deep regrouping error `1.5612511283791264e-17` and channel reconstruction error `1.3877787807814457e-17` against a `1e-14` allowance, with the canonical page digest unchanged, and per-rung retention ratios spanning `0.5506036009198637` to `0.6260661715482054` after 256 ticks. That bounds the view, not the dynamic transfer across nesting levels.
**First step (INFERENCE).** Ask whether a nested scale's retained boundary state reproduces the parent transfer over a declared frequency band, not merely at DC.
**Measures.** Band-limited transfer error for the reduced model versus the full body.
**Counts against.** Band error growing with nesting depth, showing closure is not uniform.
**Run.** Frozen-operator arithmetic; §26.18 requires basis, error, lost mode energy, and readout allowance in the reduction receipt.

### J.2 Graph spectrum and transport
**Status.** Partly measured — peaks spaced `0.00458333`, localization `0.9153`–`0.9707`, fourteen positive-frequency eigenvalues for the 28-dimensional generator (§26.23, §26.24) — but the spectrum/transport relation on a nested graph is unmeasured.
**First step (INFERENCE).** Compute each family's frozen spectral gap and correlate it with measured mean response time.
**Measures.** Gap-to-transport correlation across the six families.
**Counts against.** A correlation no better than unweighted graph distance, meaning metric-derived weights do no spectral work.
**Run.** One eigen-decomposition per family; §26.18 declares spectral estimates reconstructible mechanics, keeping this cheap.

### J.3 Fast correction with slow forgetting
**Status.** Separated in mechanism, unquantified: correction publishes an invalidation barrier advancing in bounded quanta (README), forgetting has an exact target and revocation effect and is never hidden allocator behavior (§32.16), and the heartbeat does not advance the evidence clock (§26.9).
**First step (INFERENCE).** Measure correction latency in ticks and the retention horizon of an uncorrected item in the same run at equal work.
**Measures.** Correction latency versus retention horizon.
**Counts against.** Latency comparable to the horizon, falsifying the separation as an engineering property.
**Run.** Bounded; recomputation after revision is retained machine work, not a scan of external evidence (§33.20).

### J.4 Cross-scale feedback bounds
**Status.** The Yang–Mills obligation map's finite boundary-sector result fixes all eight boundary links in the fundamental representation, gives `dim Ran P_boundary = 14` and `Q_boundary W_p P_boundary != 0` for a boundary-touching plaquette, and concludes the construction must supply covariant partial isometries for an enlarged sector family or keep an energy-dependent transfer (`../CassiTheory/computations/yang-mills-uniform-feshbach-obligation-map.md`, UFA101–UFA102, §4.4.6).
**First step (INFERENCE).** Ask the same question for the scaffold: at a declared leakage bound, does a fixed-sector coarse description admit exact closure, or must it carry the sectors the fine level generates?
**Measures.** Whether a declared reduced description reproduces the parent transfer at that leakage bound, or demonstrably cannot.
**Counts against.** The cited result predicts the negative answer for a fixed-sector description, so closure on a static coarse description would call the leakage accounting into question.
**Run.** Frozen-operator arithmetic on a small refinement; the cited result is about that lattice and must not be restated as a claim about this field.

### J.5 Information-theoretic capacity
**Status.** Capacity is declared in bytes, ports, and work rather than stored bits: `max_workspace_bytes`, `max_ports`, and the `64`-coordinate transceiver retention ceiling; §18.1 represents capacity rather than denying it and §26.21 requires refusal rather than dropping.
**First step (INFERENCE).** Measure independently recoverable symbols at fixed readout error as stored count grows, reported next to byte and port ceilings.
**Measures.** Recoverable symbols versus allocated ports and bytes.
**Counts against.** Saturation far below port count, showing interference dominates.
**Run.** Bounded; the fixed temporal field is reported at `3,234,816` bytes per owner and the resonant field at `2,088` bytes.

### J.6 Predictive depth
**Status.** Defined as a design obligation and partly measured: §33.10 requires horizon, context, tolerance, and unresolved separating tests to travel with each predictive class, and the temporal path reaches `81/81` held-out predictions against `63/81` for a current-observation-only diagnostic over `4,096` continuation steps (README).
**First step (INFERENCE).** Ask how many ticks ahead a wave-stored pattern stays predictable, recorded with its tolerance rather than as one number.
**Measures.** Prediction accuracy versus horizon, with the first failing separating test.
**Counts against.** Depth tracking the readout tolerance rather than the dynamics.
**Run.** Bounded; §33.10's rule that finite agreement is evidence for a tested abstraction, not global equivalence, binds.

### J.7 Complexity of boundary descriptions
**Status.** The repository's most concrete compact-description result, in the solver work: a width-two certificate is a sorted set of `k` original column indices, checked by nonsingularity of `K_F` and support at most two in every column of `K_F^{-1} K`, with polynomial bit bound `O(r + k*r + k*log(k))`, placing existential internal width-two basis recognition in NP; no polynomial finder and no polynomial-size NO certificate are provided, and the analyzer still checks `binomial(n, rank)` complements (README).
**First step (INFERENCE).** Ask whether a nested scaffold's interface admits a small certificate of the same kind — a bounded index set whose conjugates have bounded support — and measure certificate size against interface size for the two implemented profiles.
**Measures.** Certificate size versus interface size and polynomial checkability in the interface description.
**Counts against.** A smallest certificate growing like the interface, meaning the boundary is not compressible and cross-level access is paid at every step.
**Run.** Finite arithmetic on the two existing profiles; the structural results (`omega = 3` over `32,232` bases; no width-two dual frame among `1,620` switches screened against `C(27,5) = 80,730` five-subsets) are finite-family and must not be reported as general classification.

### J.8 Scaling of useful computation
**Status.** Measured narrowly: the adaptive field completed `111/120` requests with no overall winner, occupying `138,240` policy bytes, and a profiling pass cut validation calls from `152.0` million to `63.5` million (README); §26.24 records roughly `6.34 ms` on CPU against `46.29 s` for the first GPU invocation including setup, with no throughput or energy advantage.
**First step (INFERENCE).** Measure work per recovered item versus nesting depth at fixed item count, listing construction cost separately from query cost.
**Measures.** Query work versus depth, with construction cost broken out.
**Counts against.** Depth dependence linear in total port count rather than path length, showing the hierarchy is a relabeling of a flat body.
**Run.** Bounded; §26.18 gives `O(N)` workspace and `O(E)` sparse exchange; the absent winner forbids assuming a scaling advantage from depth.

## Alignment with existing measured limits

- **No established advantage of the seven-pool or helical organization.** §26.24 matches meaningful and rewired bodies at workspace bytes `2088`, edge count `90`, and total absolute edge strength `1.7134218127191345`, and states it shows "phase-conditioned field learning and causal transport, not superior task performance from the seven-pool organization"; the README adds no compression, no semantic agreement between branches, and no helical-transport advantage over a matched comparison graph. The geometry receipt points the same way at its single measured point: ten of eleven retention means lie within `0.0007` of the helix baseline, and the highest access coverage `0.08893715155611294` belongs to the flat `undivided` body rather than to any nested arrangement.
- **No nonlinear compression.** The compact path reduces `112` coordinates to `16` with maximum output difference `3.552713678800501e-15` over `32` ticks and zero full wave-operator applications, but nonlinear `beta > 0` responses retain the complete wave operator and are not compressed by fitting a linear map (§27.2, §27.5).
- **No end-to-end scaling claims.** The curriculum result (`1.95717` prior to `0.01619` pooled held-out RMSE) is temporal numerical compression of a learned instrument relation; §26.24 calls the reduction response bounds conservative and says they do not establish useful tight-tolerance compression.
- **Geometric similarity alone establishes nothing.** §26.4: a rigid motion preserving metric and graph leaves computation unchanged; the pitch is engineering geometry, not a canonical winding theorem; seven pools means seven cavities with distinguishable useful responses, not a count.
- **Visual or structural order does not bound dynamics.** The sibling helical depletion study found ordered helical families developing positive stretching production by the first nonzero checkpoint while only the exact Beltrami control holds at roundoff, concluding that a shared curl sign or visually ordered tube does not supply a sign-definite depletion (`../CassiTheory/turbulence/navier-stokes-helical-dynamic-depletion.md`, Abstract, §7).
- **Fixed-sector closure fails in the modelled case.** Yang–Mills UFA101 is the same shape of warning for cross-scale descriptions: an exact transfer map confined to one fixed boundary sector does not close.
- **Capacity pressure refuses rather than degrades.** §26.21 requires refusal of allocation or an already certified reduction, and forbids silently dropping evidence or occupied modes.

## First three bounded explorations

Each is **INFERENCE** as proposed. Items 1 and 2 have since been partly run —
item 2 by the durability harness and the newer survival harness, item 1's
survival half by the survival harness — and item 3 by the placement harness, at
the level each can measure; each is restated below with its measured outcome and
what remains untested.

1. **Does nesting add selectivity at matched budget?** Extend the §26.22/§26.24 four-way comparison with families 4 and 5, holding workspace bytes, edge count, total edge strength, and operator applications fixed, and report own-region localization beside the measured `0.9153`–`0.9707` band. Runner: `run_resonant_field_scenario.py` with two added profiles; harness: `run_fractal_geometry_exploration.py`, which has already run both families once and found their retention means within `0.0007` of the helix baseline while both sit above the `undivided` point that has the highest access coverage. **Run.** `run_fractal_survival_exploration.py` (`_diag/fractal-survival/exploration.json`) now supplies the survival half of the comparison at the declared default profile's own activity: at four written items `nested-core-shell` recovers `0.3351631005750861` against the helix default's `0.0764836820747603` and `recursive-paired-loops`' `0.061124304880849925`, while on a single written item the same profiles read `0.3481552374975245`, `0.29462880739045766` and `0.2702850816137677`; so nesting is not uniformly better — it pays off only as items accumulate, and it pays off against a fixed declared activity rather than against a task — and its attribution arms locate the payoff: with only the nested rail projected the `k = 4` figure is `0.07447116639609798` (delta `-0.002012515678662322` against the default, below the declared `0.02` margin) while with only the nested mass profile it is `0.33445984698946024` (delta `+0.25797616491469993`, above it), so nesting pays off through its mass profile rather than through its connection graph. What remains is the matched-budget task comparison: nothing here holds workspace bytes, connection count, total edge strength or operator applications fixed across families, so whether nesting adds *selectivity* for an actual partial-cue or competing-context task is still unmeasured, as is the matched-bytes and matched-edge-strength comparison this item asks for.
2. **Does a wave-stored item survive restart and unrelated work?** As proposed: write one item through `packet-impulse`, checkpoint, advance bounded unrelated heartbeats, and read back through the prepared-query path, reporting recovery against the `2e-12` tolerance and the declared roundoff allowance. Runner: `run_resonant_field_scenario.py` plus the owner checkpoint path; harness: `run_fractal_memory_exploration.py`, which measured retention, closure, and disturbance relaxation without a checkpoint, so restart survival was the untested half. **Run.** `run_fractal_durability_exploration.py` (`_diag/fractal-durability/exploration.json`) has now measured it at the workspace level. Recovery is `1.0` with no activity and `1.0` after an exact `ResonantWorkspace.as_dict`/`from_dict` round trip — state digest and page digest identical, read-frame maximum absolute difference `0.0` — and `1.0`, `0.9999999999999992`, `0.9999999999999996` in the restart-only `k=2`/`4`/`8` arms. Bounded unrelated activity (`64` ticks, samples at `8`/`16`/`32`/`64`, sources and heartbeat on) drops the headline item to `0.29462880739045766`, identical with and without the restart, and the multi-item arms to minimum per-item recoveries of `0.0039787604750989355` (`k=2`), `0.0764836820747603` (`k=4`) and `0.05063053711608721` (`k=8`). What remains untested: owner-checkpoint-level restart carrying the item — the owner transition surface exposes no packet-impulse operation, and the receipt records `owner_checkpoint_carries_written_item` false; readback through the prepared-query path — `prepared_query_addressed_written_packet` false, because the prepared query resolves `bias`, `input`, `output` through chart evidence; the `2e-12` transceiver tolerance, which this receipt does not exercise, its declared allowances being `1e-12` per-write energy roundoff, `1e-24` item-direction orthogonality and a `0.05` control margin; and whether the item survives an owner-level checkpoint at all. The restart identity measured is workspace-level; a durable store remains unestablished.
3. **Does interface placement beat interior placement?** As proposed: put one transceiver at an endpoint, one at a pool boundary, and one in a pool interior, and compare retained held-out relation error against the recorded `0.009797652055232753` absolute error for the existing instrument. Runner: `run_field_transceiver_scenario.py`; the ranking feeds back into C.8. **Run.** `run_fractal_placement_exploration.py` (`_diag/fractal-placement/exploration.json`) has now measured port placement on the declared `beta = 0` linearization for all eleven arrangements: the write pin and the read pick-off are one state vector (`2.220446049250313e-16` maximum difference against a declared `1e-9` tolerance), the highest-reaching drive port is `23` in `helix7` (`30.16113222426118` effective modes) against `16.699271940345195` at the declared drive port `0`, the best joint write/read pair there is `(0, 0)` with transfer `0.8357831008621412`, and no port index appears in every arrangement's top five. What remains untested: the endpoint, pool-boundary and pool-interior classification the proposal asks for — the candidate space is every port of the paired strand pair, so a placement measured here is an index, not a junction class — and the retained held-out relation error comparison against `0.009797652055232753`, which the harness does not measure.

## Measured results from the concurrent harnesses

All twenty-three runners exist in this checkout and have been run. Their exact commands:

```powershell
python run_fractal_geometry_exploration.py --output _diag/fractal-geometry/exploration.json
python run_fractal_memory_exploration.py --output _diag/fractal-memory/exploration.json
python run_fractal_durability_exploration.py --output _diag/fractal-durability/exploration.json
python run_fractal_placement_exploration.py --output _diag/fractal-placement/exploration.json
python run_fractal_survival_exploration.py --output _diag/fractal-survival/exploration.json
python run_fractal_ladder_exploration.py --output _diag/fractal-ladder/exploration.json
python run_fractal_metric_exploration.py --output _diag/fractal-metric/exploration.json
python run_fractal_lattice_exploration.py --output _diag/fractal-lattice/exploration.json
python run_fractal_feedback_exploration.py --output _diag/fractal-feedback/exploration.json
python run_owner_write_path_exploration.py --output _diag/owner-write-path/exploration.json
python run_memory_consumer_path.py --output _diag/memory-consumer-path/exploration.json
python run_owner_surface_options.py --output _diag/owner-surface-options/exploration.json
python run_owner_nested_cycle.py --output _diag/owner-nested-cycle/exploration.json
python run_memory_store_scale.py --output _diag/memory-store-scale/exploration.json
python run_store_addressing_rank.py --output _diag/store-addressing-rank/exploration.json
python run_store_addressing_capacity.py --block declared-profile
python run_store_addressing_capacity.py --block higher-resolution
python run_store_addressing_capacity.py --block merge --output _diag/store-addressing-capacity/exploration.json
python run_store_addressing_tree.py --block declared-profile
python run_store_addressing_tree.py --block higher-resolution
python run_store_addressing_tree.py --block merge --output _diag/store-addressing-tree/exploration.json
python run_scale_composition_surface.py --block declared-profile
python run_scale_composition_surface.py --block higher-resolution
python run_scale_composition_surface.py --block merge --output _diag/scale-composition-surface/exploration.json
python run_fractal_parent_summary_application_exploration.py --output _diag/fractal-parent-summary-application/exploration.json
python run_fractal_bidirectional_recursive_memory_cell.py --output _diag/fractal-bidirectional-recursive-memory-cell/exploration.json
python -m pytest test_fractal_geometry_exploration.py test_fractal_memory_exploration.py test_fractal_durability_exploration.py test_fractal_placement_exploration.py test_fractal_survival_exploration.py test_fractal_ladder_exploration.py test_fractal_metric_exploration.py test_fractal_lattice_exploration.py test_fractal_feedback_exploration.py test_owner_write_path_exploration.py test_memory_consumer_path.py test_owner_surface_options.py test_owner_nested_cycle.py test_memory_store_scale.py test_store_addressing_rank.py test_store_addressing_capacity.py test_store_addressing_tree.py test_scale_composition_surface.py -q
python -m pytest test_fractal_parent_summary_application_exploration.py -q
python -m pytest test_fractal_bidirectional_recursive_memory_cell.py -q
python run_fractal_recursive_memory_cell.py --output _diag/fractal-recursive-memory-cell/exploration.json
python -m pytest test_fractal_recursive_memory_cell.py -q
python run_fractal_multicycle_recursive_memory_cell.py --output _diag/fractal-multicycle-recursive-memory-cell/exploration.json
python verify_fractal_multicycle_recursive_memory_cell.py --receipt _diag/fractal-multicycle-recursive-memory-cell/exploration.json
python -m pytest test_fractal_multicycle_recursive_memory_cell.py -q
```

`_diag/fractal-geometry/exploration.json` (`receipt_sha256`
`01ff3e8637a3bb9c071b55a5de404b7cdc1e4dccdec35cb2dcb6af709f5bc2b4`),
`_diag/fractal-memory/exploration.json` (`receipt_digest`
`04c6ed7c7a55ef66e22ddbea159e052e0232ec1735076064f7a83b15f53125a8`),
`_diag/fractal-durability/exploration.json` (`receipt_digest`
`b560ab05d8f8d43fb701425807b051aa4e573a2efe0dcece500b5dccfaa9cb99`),
`_diag/fractal-placement/exploration.json` (`receipt_sha256`
`045b8a418968613377cfde962f7255e84385323b3ea6325ceebb401e25b948b7`),
`_diag/fractal-survival/exploration.json` (`content_digest`
`3458c0842ac391d098bd7d454c43a2e9163b7f70679bbab3a1172b4c8a25ffe2`),
`_diag/fractal-ladder/exploration.json` (`content_digest`
`6208400bec247bf31920642c28d235430010c5da8152de4a0ea59c7825072935`),
`_diag/fractal-metric/exploration.json` (`content_digest`
`70d201c05f28790077c3ce12c2b2d3012a13e53c9ac5712bfe28adca9c997aae`) and
`_diag/fractal-lattice/exploration.json` (`receipt_sha256`
`006dc8b0ae312d56f5efb6bda9896586ab26857e7c9cd66710da93548623dd92`) and
`_diag/fractal-feedback/exploration.json` (`receipt_digest`
`fdc2e1443d95e010bae1bb8974980e9e1dff5047946f135dbaa5d30c243eb63b`) and
`_diag/owner-write-path/exploration.json` (`receipt_digest`
`a1f5c4ffe42a9c25182cf25ec54ab2e5bff7ff51147e2d51d98a6234072e9f7c`) and
`_diag/memory-consumer-path/exploration.json` (`receipt_digest`
`3933e8ecc0aeedd1a9722c0bd282006d5217b516b3acf504133e973cb48b5f07`) and
`_diag/owner-surface-options/exploration.json` (`receipt_digest`
`a9a85f9b1e4a32b19c81e5476d94e78835c95739998b3f4b770d613d8ef7e455`) and
`_diag/owner-nested-cycle/exploration.json` (`receipt_digest`
`909ec09da53fd0b6946dca2dc18ad71c481ffaa2d9bbc76846f18cf382bbe1aa`, the frozen
receipt) and its current-rule companion
`_diag/owner-nested-cycle/exploration.layout-decoupled.json` (`receipt_digest`
`bd7a83d40f5013b6c9d71e5b0abb2fc0cd45f1e751122a1a6f6332a7993f736a`) and
`_diag/memory-store-scale/exploration.json` (`receipt_digest`
`d769cd297109d4885ee62a3256b649b5b0bb9504dd395daf8c1ee6a794ae2c77`) and
`_diag/store-addressing-rank/exploration.json` (`receipt_digest`
`59c22ecaabd1b952c370ea6d09f8fbddfd7231cf11ac44f64446e1b68c809510`) all exist
and parse. Each states its own bound in the file: the geometry receipt covers
"bounded numerical exploration of declared connection/metric scaffolds;
arrangements are candidate scaffolds, not memory or task claims"; the memory
receipt covers "Canonical-field numerical measurements in controlled conditions
only" with "nothing here demonstrates task-level memory utility, semantic
content, retrieval by a consumer, or any advantage over alternative
architectures"; the durability receipt covers "Canonical-field numerical
measurements in controlled conditions only" with the restart leg described as
"workspace-level restart identity, not owner-checkpoint identity for the written
item" and closes "Nothing here demonstrates task-level memory utility, semantic
content, retrieval by a consumer, owner-level checkpoint identity for a written
item, or any advantage over alternative architectures"; the placement
receipt covers "bounded measurement of modal access on the declared
linearization; placements are candidate ports, not memory or task claims"; and
the survival receipt covers "Controlled canonical-field measurement only" and
closes on the same negative list, adding that its "pair contrasts are measured on
the declared default profile unless the receipt says otherwise."; the ladder
receipt covers "Canonical-field numerical measurements in controlled conditions
only" with "No task memory claim." and records that its flat-inertia profile is
"cited from metric harness (k4 0.8948910529922045, eleven times field default) —
not re-derived"; the metric receipt covers "Controlled canonical-field
measurement only, on the canonical seven-pool body at the declared resolution"
and closes "Nothing here establishes task-level memory utility, semantic
content, retrieval by a consumer, or any advantage over alternative
architectures"; and the lattice receipt's `declarations.boundary` lists eleven
bounds beginning "Every number is a geometric, spectral, survival or placement
proxy on a declared scaffold." and ending "No arrangement claim here is a claim
about memory utility, learning, or task performance."; and the feedback receipt
covers "Canonical-field numerical measurements in controlled conditions only" and
closes "Nothing here demonstrates task-level memory utility, semantic content,
retrieval by a consumer, owner-level checkpoint identity, a distribution of
outcomes over profiles or items, or any advantage over alternative
architectures."; and the owner write path receipt covers "Canonical-field
numerical measurements in controlled conditions only", states that its read half
"is a prediction of the canonical page under the write's own declared direction,
not an observation", closes "Nothing here demonstrates task-level memory utility,
semantic content, retrieval by a consumer, a distribution of outcomes over
profiles or items, owner-level capacity beyond the declared limits, or any
advantage over alternative architectures", and records one live consequence
rather than repairing it — that the durability harness's own recon "says the
owner exposes no packet-impulse operation, which this additive transition
supersedes; that harness is frozen evidence and is deliberately left untouched.";
the memory consumer path receipt declares its task as "one declared
deterministic policy over one declared set of candidate directions on one
declared profile" and closes "nothing here measures a distribution over
profiles, items, budgets or policies", recording beside it that the consumer's
act "is the owner's write path, which is the only write actuator on the public
surface"; and the owner surface options receipt covers "Canonical-field
measurements in controlled conditions only" over one declared profile, "one
declared written packet item at one declared write budget", one declared
observation channel and one declared resolution ladder, states that "Nothing
here changes a default: both options are measured off the shipped path", and
closes "The authority figures are the transceiver's declared input-scan
convention ... not a physical claim about the channel" with its overlap
enumeration bounded to its declared lattice; and the owner nested cycle receipt
declares one written item, `root-scale`, at one declared write budget of `0.001`
on four declared bodies, and its five declared limitations close the figures:
the two rails "are two declared bodies, not a family: the rail factor is read at
one nested arrangement only", the metric factor "is read at two declared settings
of the ladder family plus the survival harness's own shell metric in the reference
legs; no conclusion about metrics in general follows", "the figures are one
declared item's", the hold horizon is the consumer path's declared `16` ticks,
and the no-loop control "is measured at the declared hold horizon and is a no-drive
hold"; and the memory store scale receipt declares four bounds of its own — that
its acts sit on "one declared profile, one declared direction set, one declared
act budget and one declared drive amplitude", so "nothing here measures a
distribution over profiles, items or budgets"; that the coupled realization's act
"is measured as a movement of the realization's own declared readout and of its
own working state, which no operation writes back into the page: ... the
non-destructive act is measured on the surface that carries it"; that "the store's
hold is short by declaration, so this receipt makes no claim about holding eight
items over a long horizon"; and that the identity control "is a direction
measurement, not a claim that acting on a memory is useful in any wider sense"; and
the store addressing rank receipt declares its own bounds and its `not_shown` list —
that its crowded state is "one declared operating point: the declared items, the
declared write budget, the declared hold horizon and this profile; nothing here
measures a distribution over densities, gates or profiles", that the rank reading's
"floor is the measured finite-difference floor plus the declared relative numerical
floor, and a deficiency below that floor would not be visible", that the shared
arm's "zero separation is the declared structural control: when every item is
addressed at one placement the read is the same call, so the arm measures the
addressing semantics rather than a dynamical collapse", and that "the arms address
one written page; the store-scale hold's own doubling is not exercised in the
placement arms, only at the crowded held state of part one"; and the store
addressing capacity receipt declares five bounds of its own — that
the sweep measures "one declared metric row at two resolutions, the delivered write
budget, the delivered hold horizon and one probe amplitude", so "nothing here
measures a distribution over profiles, budgets, holds or amplitudes"; that the
declared family "is extended along the field's own dyadic scale tree only, so the
capacity reading is a claim about that tree, not about arbitrary packet
placements"; that "the probe budget is fixed while the level's own page deposit
grows with N, so a failure would be a failure at this probe budget"; that "the rank
reading is a finite-difference reading; a deficiency below the level's own measured
floor plus the declared relative floor would not be visible"; and that "the counts
that did not run are listed with their reasons: an unrun level is not evidence of a
ceiling, and the structural inventory is measured separately from the arms". Its
`not_shown` list holds the two readings it cannot give from its own statistic —
(multi-item-per-probe) placement would carry more than the port count; the delivered
statistic addresses one item per probe".
Every figure
below is read from those twenty-three files. All twenty-three measure canonical-field
numerical
proxies — geometric/access, modal-access, the owner transition surface itself, or
one declared consumer's act on it, a declared frozen-parent application, or a
declared live child-detail-to-parent application; none
measures task-level memory utility
or task performance.

### Geometry

Eleven declared arrangements, each at 7 pools by 4 ports, state dimension `112`
for all of them, seed `20260915`. Every arrangement is linearly stable at rest:
the largest real eigenvalue part runs from `-0.0119999999999999` (`undivided`) to
`-0.006985912603637359` (`helix7`), with `112` complex modes and zero real modes
throughout.

- **Localization**, median inverse participation ratio at a uniform reference of
  `0.008928571428571428`, orders from most to least localized as
  `recursive-paired-loops` `0.28602472976220794`, `quasiperiodic-chain`
  `0.2703946322772237`, `random-rewire-matched` `0.2686921872219767`,
  `flat-ladder` `0.2612791610024881`, `sparse-long-link` `0.2598500257258747`,
  `isolated` `0.21519555154393477`, `rewired` `0.18646413840480963`,
  `core-shell-defect` `0.1679133974860576`, `nested-core-shell`
  `0.15986442406282375`, `helix7` `0.1565230898708423`, down to `undivided`
  `0.025638847681613515`. Distinct frequencies at `0.01`: `helix7` `34`,
  `recursive-paired-loops` `14`, `isolated` `9`, `undivided` `1`.
- **Retention** (`advance end_energy / post-impulse energy` over `64` ticks at
  work budget `0.02`, sources off, impulses at pools 0, 3, 6): `core-shell-defect`
  `0.9077286700547321` and `nested-core-shell` `0.9077268956564812` at the top,
  `helix7` `0.9070808366086672`, `flat-ladder` `0.9070780849024244`,
  `undivided` `0.8847964256309172` at the bottom.
- **Rail versus mass.** Where the mass metric differs, retention moves: `helix7`
  against `undivided` by `0.03436382025490936`, `helix7` against
  `nested-core-shell` by `0.03435675520060377` (maximum per-pool retention
  difference, margin `0.01`). Where the mass metric is identical and only the
  rail differs, retention barely moves: `flat-ladder` against
  `random-rewire-matched` by `0.00011141722933116771`, against `sparse-long-link` by
  `1.4978129159182174e-06`, against `quasiperiodic-chain` by `1.5997480643514805e-06`
  (margin `0.001`). Mass-metric changes therefore move 64-tick retention two and
  a half orders of magnitude more than density-matched graph-only changes.
- **Access.** Structural coverage is best for `undivided`
  (`0.08893715155611294`), next for `nested-core-shell` and `core-shell-defect`
  (`0.06856885869537555`), and near `0.0610` for the rest. Measured response
  coverage after `32` ticks under the same declared learned objective agrees:
  `undivided` `0.1876359247979643`, `nested-core-shell` `0.05333366820720189`,
  `core-shell-defect` `0.05333366494600142`, `helix7` `0.03217022111014065`, and
  `0.031961867203564365` for `isolated`. The condensation error bound is worst exactly where
  coverage is best: `undivided` `156.8624881544609`, `nested-core-shell`
  `106.7058285863892`, `core-shell-defect` `106.70635306736138`, and `isolated` `48.54435878433857` lowest of
  the eleven.
- **Which hooks drive dynamics.** Input-lift column norms and output-row norms
  are structurally `1.0` for every arrangement — the declared objective pins the
  drives and picks off the reads — so placement cannot be told apart through
  them. `projected_transport` replaces the rail entirely: all seven declared pool
  graphs report `rail_equals_edge_rail` false, so their declared `edges` are
  ignored and `topology` is metadata only. Without it, `topology` drives the rail
  only when it differs from the canonical one: `topology_changes_rail` is true
  for `undivided`, `isolated`, and `rewired`, and false for `helix7`.
  `projected_inv_mass` is used by `nested-core-shell` and `core-shell-defect`
  alone, and those two are exactly the pair with the highest retention
  (`0.9077268956564812`, `0.9077286700547321`) and the largest damping magnitude
  (`-0.008012734785549591`, `-0.007993866938594274` against about `-0.0071487745285719745` elsewhere).
  `projected_quartic_weights` moves only the nonlinear term: its probe records
  `linear_generator_max_abs_difference` `0.0` and `linear_spectrum_changed`
  false while `nonlinear_retention_changed` is true (counterflow retention
  `0.9775527826649286` to `0.9775504586504036`, common `0.9697989827108273` to
  `0.9697989827109739`).
- **Determinism.** Replays reproduce retention, the generator, the rail, the
  profile, and the eigenvalue digest exactly for every arrangement.

Five implementation limits are recorded alongside, and they bind several
directions above: `pools` is fixed at exactly 7 with `ports_per_pool` at least 4;
`ResonantProfile.coordinates` has no hook, so spatial spacing cannot be
expressed; `profile.edges` is ignored whenever `projected_transport` is set;
`projected_inv_mass` accepts only a positive per-port vector or an SPD matrix on
the paired coordinates; and `projected_quartic_weights` is per-port and cannot
change the `beta = 0` linear spectrum at all.

### Memory

One declared 28-port packet path, drive budget `0.001`, `beta = 0.08`.

- **Per-rung retention** at horizon `256` ticks. The retained projection of the
  deposited energy along the driven direction is `0.003380437390550838` for the
  width-28 rung, `0.0005481693441272088` at width 14, `0.08970751453852188` at
  width 7, and `0.17236141393990917` at width 3. Total packet energy ratio stays
  between `0.5506036009198637` and `0.6260661715482054` across the same arms.
  Narrow rungs hold their driven share; wide rungs lose the driven direction
  without losing comparable total energy.
- **Cross-channel transfer** after `256` ticks, as the share of driven-channel
  energy landing in each response channel. The diagonal is `0.5941439169696623`
  (momentum-common), `0.5898223965205114` (momentum-counterflow),
  `0.22856014307374511` (position-common), `0.22835114131645576`
  (position-counterflow); the largest off-diagonal is `0.6428602403846356` from
  position-common to momentum-common; the channel swap symmetry maximum absolute
  residual is `0.0043399768455958596`. Position channels are not directly
  drivable: the receipt records `position_channels_drivable` false, because no
  canonical impulse writes position lanes, and its two position arms are
  prepared by a declared composite instead.
- **Repeated drive** over eight cycles of eight ticks at `0.001` per cycle closes
  the ledger: relative closure residual `-8.673617379884035e-19` against a `1e-12`
  allowance, accumulated balance defect `-5.670750429884193e-19`, maximum
  absolute phase defect `2.087998046107861e-18`, final measured energy
  `0.007537496474352549` under a `1.0` ceiling.
- **Recovery** over a `4096`-tick horizon at `512`-tick stride, distance measured
  in packet coefficient space. With activity off, both arms recover about the
  same fraction — `0.9029200239619808` for the small disturbance and
  `0.9029193243881666` for the large one — from a control that stays at `0.0`.
  With activity on, the large arm recovers `0.785259548583942` while the small
  arm recovers `-0.21035947971598867`, a recorded negative: the live control
  drifts to `0.02616802125195171` and swamps a `0.0001` disturbance.
- **Profile dependence.** Only damping moves the measured page. Halved, doubled,
  and zeroed damping each leave the page different from the default, halved
  shifting the retained projection by `1.0370342695741048` at the coarsest rung
  and zeroed by `1.063631499341105`. `quiet-damping-double`, `activity-tau-short`,
  and a descriptor-only change leave the canonical page bit-identical at every
  rung with retained projection ratio exactly `1.0`, even though the state digest
  still changes because it covers the declared profile descriptor.
- **View integrity.** Analysis, splitting, and recomposition stay inside the
  declared `1e-14` allowance: maximum coefficient reconstruction error
  `1.5612511283791264e-17`, channel reconstruction error
  `1.3877787807814457e-17`, and the canonical page and state digests unchanged.
  The packet digest is not bit-identical after regrouping
  (`packet_digest_bit_identical_after_regrouping` is false on every path), so this
  is numerical reconstruction, not byte-identical packet recovery.

### Durability

One declared `28`-port read-frame path and eight declared items — `root-scale`
(width `28`), `root-detail` (`28`), `left-detail` (`14`), `right-detail` (`14`),
and `left-left-detail`, `left-right-detail`, `right-left-detail`,
`right-right-detail` (all `7`) — each written at budget `0.001`. Seventeen arms run
the four combinations of restart and unrelated activity, two single-item
controls, `k = 2/4/8` multi-item arms, and five declared source-off counterparts
of those activity arms. Every share and distance is measured
in the declared read frame (`[28, 4]` packet coefficients on basis
`balanced-contiguous-haar-phase-space-v1`). Unrelated activity is `64` ticks of
`advance_workspace` with sources and heartbeat on, sampled at `8`, `16`, `32` and
`64`; the source-off counterparts advance the same ticks at the same samples and
change one declared argument, `source_enabled`, which zeroes the heartbeat's work
allowance and nothing else, so the heartbeat and breath phase clocks, the body's
own damping and nonlinear coupling, and its dissipation keep running. Restart is
`ResonantWorkspace.as_dict -> from_dict`.

- **Neither an immediate read nor the round trip costs anything measurable.**
  The `immediate` arm (no restart, no activity) and `restart-no-activity` both
  read the item back at recovery `1.0`; the state digest and the page digest are
  identical across the round trip, the read frame is bit-identical with maximum
  absolute difference `0.0`, and `restart_state_sha256` equals
  `write_state_sha256`
  (`d9523ed23939bfcf40a9546c6f5907597271c2db78c8218de31cbe2bf2ccd6fe`). The
  restart-only multi-item arms recover `1.0`, `0.9999999999999992` and
  `0.9999999999999996` at `k = 2`, `4` and `8`.
- **The advance, not the restart, is what costs the item.** `restart-and-activity`
  recovers `0.29462880739045766`, exactly the `activity-no-restart` figure, so
  the restart adds nothing measurable to the loss; total packet energy ratio is
  `0.9834193298916879`. The share recorded over the activity run is
  `0.7993982114191338` at `8` ticks, `0.37081467958401865` at `16`,
  `0.05042973026688151` at `32` and `0.29462880739045766` at `64`.
- **The source state does not carry the loss.** Five declared source-off
  counterparts repeat the write, the round trip and the read tick of
  `activity-no-restart`, `restart-and-activity`, `no-item-restart-and-activity`,
  `restart-and-activity-k2` and `restart-and-activity-k4` with
  `source_enabled=False`, which the receipt's `source_control` block reports as
  disabling the heartbeat's positive work alone: `positive_heartbeat_work_total`
  is exactly `0.0` on every source-off arm against at least `0.000267862004213958`
  on every source-on arm, and the heartbeat and breath phases and the field tick
  count are identical between each pair. The single item reads
  `0.31149818467501866` with the source off, against `0.29462880739045766` with it
  on, identical with and without the restart; the `k = 2` arm's minimum per-item
  recovery is `0.02024216942315969` against `0.0039787604750989355`, and the
  `k = 4` arm's `0.0626599491514189` against `0.0764836820747603`. The derived
  figure is source-on minus source-off at the same tick, each against a declared
  `0.01` margin: `-0.016869377284561005` for the single item,
  `-0.016263408948060755` at `k = 2` and `0.013823732923341409` at `k = 4`, so the
  smallest magnitude `0.013823732923341409` still reaches the margin and the
  source state does move the read-tick recovery. What it moves far more is the
  frame's total energy: the single-item ratio falls from `0.9834193298916879` with
  the source on to `0.7720435496915942` with it off (`0.21137578020009373`), and
  the no-item background arm's drift from its pre-activity frame is
  `0.023122492931584436` with the source on against exactly `0.0` with it off.
  The comparison the attribution rests on: with the source off the written
  direction's alignment falls faster than the frame's total energy — retention
  `0.31149818467501866` against `0.7720435496915942`, a difference of
  `-0.4605453650165755` against the declared `0.05` margin — and the same
  comparison holds with the source on (`0.29462880739045766` against
  `0.9834193298916879`, difference `-0.6887905225012303`). The per-tick
  source-off series is `0.7967617761274481`, `0.36884561619700146`,
  `0.030975071077481122` and `0.31149818467501866` against the source-on
  `0.7993982114191338`, `0.37081467958401865`, `0.05042973026688151` and
  `0.29462880739045766`. **INFERENCE.** The direction is lost by the body's own
  dynamics rather than by the declared source: switching the only declared source
  off leaves the direction where it was while leaving the frame far less total
  energy, so a refresh or consolidation schedule would re-inject a direction the
  passive body does not hold, and the fix family the measurement points to is the
  body's own metric and coupling — making the written direction one the body's
  propagation and dissipation preserve — rather than a stronger or more frequent
  write.
- **Control separation holds for the headline item.** Its `0.29462880739045766`
  exceeds the write-A-read-B control share `0.10678589435332199` by more than the
  declared `0.05` margin, on both deposit shares and shares of the current packet
  energy. The control arm that writes `left-detail` instead does not separate: it
  recovers `0.050794994233057715` along its own direction against
  `0.08884798194983937` along a direction it did not write, and the receipt marks
  it not distinguishable. The no-item arm writes no item, so its recovery
  fraction is `null`; it drifts to `0.023122492931584436` from its pre-activity
  state against `0.10860479286570802` for `restart-and-activity`, with
  background shares `0.003276269512241885` and `0.15176379246475397`.
- **Interference grows with item count.** Sequential writes into a non-empty
  field deposit less than the isolated capture: measured-over-captured
  attenuation is `0.440745721562222` (`root-detail`), `0.546926417343561`
  (`left-detail`) and `0.9222958352473959` (`right-detail`) in the restart-only
  arms. After activity the minimum per-item recovery is
  `0.0039787604750989355` at `k = 2`, `0.0764836820747603` at `k = 4` and
  `0.05063053711608721` at `k = 8`, while the read packet's declared-frame
  projection fraction rises `0.3443303224621802` → `0.4811366377266782` →
  `0.5871936760100912` and its distance from the pre-activity state rises
  `0.11753645459467629` → `0.18503125395234504` → `0.2915379872544576`. In the
  restart-only arms that projection fraction is `1.0` (`k = 2`, `8`) and
  `0.9999999999999999` (`k = 4`).
- **The owner probe.** The production owner is reachable under a bounded
  deterministic setup in a temporary home: its checkpoint preserves the
  canonical workspace (`workspace_state_sha256_preserved_across_restart` and
  `workspace_field_ticks_preserved_across_restart` both true) and its prepared
  query is restart-stable (`prepared_query_restart_stable` true). But
  `packet_impulse_transition_available` is false and
  `prepared_query_addressed_written_packet` is false: the owner transition
  surface exposes no packet-impulse operation, and the prepared query resolves
  `bias`, `input` and `output` through chart evidence. The receipt therefore
  records `owner_checkpoint_carries_written_item` false.
- **Declared allowances.** Item-direction orthogonality allowance `1e-24`
  against measured maximum off-diagonal squared cosine `1.2175164122802152e-32`,
  directions mutually orthogonal; per-write energy roundoff allowance `1e-12`
  against balance defect `0.0` and applied work `0.0010000000000000002` at
  requested `0.001`; control margin `0.05`; source-off margin `0.01` against the
  smallest measured magnitude of the source-on minus source-off recovery
  `0.013823732923341409`; alignment-versus-energy margin `0.05` against the
  measured differences `-0.6887905225012303` with the source on and
  `-0.4605453650165755` with it off.

This is a controlled proxy rather than a task measurement: an item outliving a
workspace round trip and bounded activity does not establish task utility, and
the durable-store question stays open. The receipt's own bound, verbatim:
"Canonical-field numerical measurements in controlled conditions only: one
bounded packet impulse written into the canonical page, bounded unrelated
canonical activity with sources and heartbeat on together with declared
counterparts of that activity whose only difference is the source state, and an
exact workspace round trip for the restart leg. The restart leg is
workspace-level restart identity, not owner-checkpoint identity for the written
item, because no owner transition accepts a packet impulse. Nothing here
demonstrates task-level memory utility, semantic content, retrieval by a
consumer, owner-level checkpoint identity for a written item, or any advantage
over alternative architectures."

### Survival

The survival harness reuses the durability harness's declared items, arms,
activity and readout by import and the geometry harness's declared arrangements
by import, and it reuses neither harness's `main`. Three contrasts are measured.
The scaffold contrast runs the headline single-item arm and the `k = 4` arm on
three declared profiles under identical declared activity: `64` ticks of
`advance_workspace` with sources and heartbeat on, sampled at `8`, `16`, `32` and
`64`, at the same write budget `0.001` in the same declared `[28, 4]` read frame.
The attribution contrast reruns those same declared arms on single-channel arms
built through the same declared profile hooks: `rail-only` carries
`nested-core-shell`'s projected transport with the canonical mass metric,
`mass-only` carries its projected inverse-mass profile with the canonical rail,
and the compound `nested-core-shell` carries both, so the compound gain
decomposes into a rail component and a mass component, each against its own
declared margin `0.02`, with the sum of the two against the compound gain under a
declared additivity tolerance `0.01`. That contrast also reports the geometry
harness's other declared mass contrast, `undivided`, whose `topology` hook moves
both channels at once — uniform volumes rescale every canonical edge weight
through the declared weight rule — so it is recorded as a compound topology-hook
arm and excluded from the two-channel decomposition. The spacing contrast writes
declared item pairs at declared scale distances and compares their off-diagonal
deposit-share structure and per-item recovery after that same activity, and the
attribution contrast reruns it on the `rail-only` and `mass-only` arms so the
channel that carries it can be named. Declared scale distance is the absolute
difference of declared scale depth — the number of `L`/`R` branches in an item's
declared packet path, root `0`, `L`/`R` `1`, two-branch paths `2` — cross-checked
on every profile against `log2(port_count / measured support width)` of the
captured write direction, and never a tree or branch-graph distance, which would
make a depth-1 sibling pair and a root-versus-depth-2 pair equally distant.

- **The mass-metric profile carries the `k = 4` survival gain; the connection
  graph contributes nothing measurable.** Recovery after the declared activity,
  per declared arm: `helix7` `0.29462880739045766` single and `0.0764836820747603`
  at `k = 4`; `rail-only` (the nested rail with the default mass metric)
  `0.2914883254405012` and `0.07447116639609798`, a `k = 4` delta of
  `-0.002012515678662322` against the default, below the declared `0.02` margin;
  `mass-only` (the default rail with the nested mass profile)
  `0.349290029461373` and `0.33445984698946024`, a delta of
  `+0.25797616491469993`, above it. The compound `nested-core-shell` reads
  `0.3481552374975245` and `0.3351631005750861`, and its `k = 4` gain
  `0.2586794185003258` decomposes into those two single-channel components — rail
  `-0.002012515678662327`, mass `+0.25797616491469993` — whose sum
  `0.2559636492360376` matches it to a residual of `0.0027157692642881814`
  against the declared `0.01` additivity tolerance. On the single-item arm the
  same decomposition reads rail `-0.003140481949956475` and mass
  `+0.05466122207091534`, residual `0.0020056899861079502`, tolerance `0.01`.
  Both component margins are declared, and on these numbers only the mass
  component reaches its own: the rail component stays below its `0.02` margin in
  both declared arms — `0.002012515678662327` at `k = 4` and
  `0.003140481949956475` on the single item, i.e. `0.00780116907051381` and
  `0.05745356270816881` of the mass component's magnitude — while the mass
  component reaches its own (`0.25797616491469993` and `0.05466122207091534`), so
  the receipt's derived verdict names the mass channel as the carrier in both
  arms.
- **The other declared profiles, for completeness.** `recursive-paired-loops`
  sits below the default on both arms (`0.2702850816137677` and
  `0.061124304880849925`, deltas `-0.024343725776689973` and
  `-0.015359377193910381`); `undivided` reads `0.207725416099125` and
  `0.08288217617861876` (deltas `-0.08690339129133265` and
  `+0.006398494103858454`). Against the declared profile margin `0.02` every
  difference reaches except the `k = 4` arm on `recursive-paired-loops` and on
  `undivided`, which fall below it, so the margin discriminates in both
  directions on measured numbers rather than ratifying a single outcome.
- **The default profile reproduces the durability receipt exactly.** `helix7`
  recovers `0.29462880739045766` here, the durability receipt's own headline
  figure, and the geometry harness's `helix7` build carries hook fields identical
  to `ResonantProfile()`. The harness's declared `0.05` control margin still
  separates the headline item (`0.29462880739045766` against control share
  `0.10678589435332199`).
- **Far-separated items survive better than near ones, and the near pair is the
  more confused.** On the declared default profile, the near pair (`left-detail`
  with `right-detail`, declared scale distance `0`, disjoint adjacent supports)
  reads minimum per-item recovery `0.051463903480489785` with maximum
  off-diagonal deposit share `1.5938203196470795` and unwritten-direction
  fraction `0.16409644426401782`; the far pair (`root-scale` with
  `right-right-detail`, distance `2`, nested supports) reads
  `0.37505473969085323`, `1.1418392277684646` and `0.16800161152328036`. Both
  declared `0.05` margins are reached (`0.4519810918786149` more confusion and
  `0.32359083621036344` more recovery), so the spacing contrast separates on the
  default profile.
- **The distance-1 pair breaks the ordering, and the rail channel drives the
  spacing separation.** The intermediate pair (`left-detail` with
  `left-left-detail`, distance `1`, nested supports) has both the lowest
  confusion `0.2679860056230932` and the lowest recovery
  `0.009645431892084735` of the three, with by far the largest
  unwritten-direction fraction `0.6927050860352755`; on that interference-specific
  figure the near and far pairs are indistinguishable (`-0.003905167259262543`).
  Under the same margins the spacing contrast separates on `helix7` and
  `recursive-paired-loops` but not on `nested-core-shell`, where the confusion
  ordering inverts (near `0.3459138643534228` against far `0.909941930523071`).
  The attribution arms name the channel: with only the rail projected,
  `rail-only` still separates, its confusion difference `0.42952229136107434` and
  recovery difference `0.3127625666999712` both reaching the declared `0.05`
  margins; with only the mass metric changed, `mass-only` does not, its confusion
  difference `-0.5390276642816413` and recovery difference `-0.0077118319203438035`
  both below the margins and both of the wrong sign. The separation therefore
  belongs to the declared connection graph, and the projected inverse-mass
  profile removes it rather than the reverse.
- **The contrasts are activity-specific, and none is a storage claim.** With
  the same pairs written and restarted but no activity, the near and far pairs
  recover `1.0` on all three profiles (the mid pair reads `0.9999999999999997`)
  and the receipt's `unwritten_direction_energy_fraction_total` sits at the
  `1e-32` rounding level (`4.908608656186611e-33` to `2.0611330256211534e-32`),
  consistent with the declared items being orthogonal to within the declared
  `1e-24` allowance. On the default profile the declared off-diagonal deposit
  share still reads `2.455407094428614` near and `1.9665240147275729` far, but the
  recovery difference is `0.0`, so the same declared margins report
  `recovery_separates` false and `separates` false — the receipt's own control
  against a margin that the write amplitudes alone would otherwise satisfy.

**Headline reading.** Scaffold choice changes live multi-item survival, and the
attribution contrast says which hook does it: at four written items the nested
core–shell keeps `0.3351631005750861` against the default's `0.0764836820747603`,
that compound gain `0.2586794185003258` decomposes into a mass component
`+0.25797616491469993` and a rail component `-0.002012515678662327`, the
mass-metric arm alone reproduces nearly all of it (`mass-only`
`0.33445984698946024`) while the rail-only arm stays below the declared margin
(`0.07447116639609798`), and the two components sum to the compound gain to
within `0.0027157692642881814` of the declared `0.01` additivity tolerance. So
nesting pays off through its mass profile, not through its connection graph.
Within a scaffold, items at declared scale distance `2` survive better than items
at declared scale distance `0` (`0.37505473969085323` against
`0.051463903480489785` minimum per-item recovery), and that separation is the
rail's: it survives the rail change alone (`rail-only`, recovery difference
`0.3127625666999712`) and is absent once only the mass metric changes
(`mass-only`, recovery difference `-0.0077118319203438035`). Both effects are
activity-specific: the same pairs written and restarted with no activity recover
`1.0` and the spacing contrast reports `recovery_separates` false and
`separates` false.

The receipt's own bound, verbatim: "Controlled canonical-field measurement only:
declared packet items written into the canonical page through the canonical
packet impulse at the durability harness's declared budget, the same declared
unrelated canonical activity (sources and heartbeat on) for every profile and
every pair, and the canonical workspace round trip for the restart leg. The
scaffold contrast reuses the durability harness's declared arms by import and the
geometry harness's declared arrangements by import; the attribution contrast
builds its single-channel arms from the one declared hook each of them carries,
so its components are differences of measured recoveries, not a causal separation
of the two hooks inside one run. The declared 'undivided' arm is a topology-hook
contrast that moves both the rail and the mass metric, so it is reported as a
compound arm and is excluded from the two-channel decomposition. Nothing here
demonstrates task-level memory utility, semantic content, retrieval by a
consumer, owner-level checkpoint identity for a written item, or any advantage
over alternative architectures: the recovery figures are shares of a measured
deposit along a measured direction, and the pair contrasts are measured on the
declared default profile unless the receipt says otherwise."

### Placement

Eleven declared arrangements — the geometry harness's four profile-backed ones
(`helix7`, `undivided`, `isolated`, `rewired`) and its seven declared pool graphs
(`flat-ladder`, `nested-core-shell`, `recursive-paired-loops`,
`core-shell-defect`, `sparse-long-link`, `quasiperiodic-chain`,
`random-rewire-matched`) — each at 7 pools by 4 ports and state dimension `112`.
The declared `beta = 0` linear generator is rebuilt exactly as the geometry
harness builds it and densely eigendecomposed: `112` modes, `0` zero-magnitude
modes, eigenvector condition numbers from `1.0000000000022564` (`undivided`) to
`13.797501905657343` (`quasiperiodic-chain`) against the declared limit `1e8`,
eigen-residual `3.644735674336824e-15` against `1e-10`, and every arrangement
reproduced deterministically (generator, pin, top sets and selection identical on
replay). The candidate space is all `28` ports, the transfer table is all `784`
ordered write/read pairs, selection depth is `7`, and the reported top sets hold
`5` placements.

- **The write pin is the read pick-off.** `pin_vs_pickoff_max_abs_difference` is
  `2.220446049250313e-16` in every arrangement against the declared
  `pin_tolerance` of `1e-9`, and the construction reproduces the production
  kernels exactly: `input_lift_vs_port_pin_max_abs_difference` `0.0` and
  `output_rows_vs_port_pickoff_max_abs_difference` `0.0`. The same state vector
  is written and read, so any write/read asymmetry reported is the
  dual-versus-primal modal expansion rather than a difference in port
  functionals, and every placement difference below comes from the arrangement's
  eigenbasis alone. That expansion is not small: the dual-versus-Euclidean drive
  difference is `0.34617085351214527` in `helix7` and `2.8361655808202366` in
  `quasiperiodic-chain`.
- **Top placements per arrangement**, as best drive port by effective modes, best
  read port, and best joint write/read pair by transfer:
  - `helix7` drive `23` `30.16113222426118`, read `20` `31.092616984755292`, joint `(0, 0)` `0.8357831008621412`.
  - `undivided` drive `9` `104.76234683324073`, read `9` `104.76234683324148`, joint `(5, 22)` `0.7740332635272998`.
  - `isolated` drive `17` `15.467945729124956`, read `17` `15.518538449831233`, joint `(3, 1)` `0.8156746959614276`.
  - `rewired` drive `7` `31.43039964283109`, read `24` `34.514361954032054`, joint `(6, 6)` `0.69177994594555`.
  - `flat-ladder` drive `3` `16.782326088792374`, read `24` `17.211800052807966`, joint `(9, 9)` `0.8481958762442885`.
  - `nested-core-shell` drive `8` `30.81361035373595`, read `24` `32.50269914509668`, joint `(14, 14)` `0.8693415659191424`.
  - `recursive-paired-loops` drive `15` `26.432246954195232`, read `16` `26.26876079309506`, joint `(22, 22)` `0.8325215942988119`.
  - `core-shell-defect` drive `8` `30.757271580667638`, read `20` `30.86107905201761`, joint `(10, 17)` `0.8470987791032016`.
  - `sparse-long-link` drive `3` `18.21504759161972`, read `24` `19.152314430835116`, joint `(26, 26)` `0.7878309566893678`.
  - `quasiperiodic-chain` drive `3` `16.7686156733969`, read `24` `17.236924821708723`, joint `(14, 13)` `0.8677110419238352`.
  - `random-rewire-matched` drive `3` `15.486563203475633`, read `16` `16.354861126908354`, joint `(25, 25)` `0.8464003836161407`.
- **Greedy selection beats the declared binding order at shallow depth, not at
  depth `7`.** The declared order drives on local port `0` and reads on local
  port `1` (ports `0, 4, …, 24` and `1, 5, …, 25`). In `helix7` the greedy
  coverage ratio against that order is `1.8551138935527258` at depth `2` for
  drive, `1.8327720215078473` at depth `2` for read and `1.8678148349343988` at
  depth `2` for joint, but `0.9960210404210216`, `1.0090025635641628` and
  `0.9386358118225462` at depth `7`. The peak lands at depth `1` or `2` in every
  arrangement, at depth `3` for the read family of `isolated` and
  `random-rewire-matched`, and the depth-`7` joint ratio exceeds `1` everywhere
  except `helix7`. Restricted to the seven declared binding ports the ratio
  returns to `1.0` at depth `7` by construction, peaking in `helix7` at
  `1.8238428326431955` (drive), `1.4993067629611112` (read) and
  `1.2471229232579588` (joint), each at depth `2`. Over the whole candidate space
  the largest peak is `5.474869903047155` (`recursive-paired-loops` joint, depth
  `1`), and the largest depth-`7` gains are `1.7432642262553795`
  (`sparse-long-link` joint) and `1.7217689533971068` (`nested-core-shell`
  joint).
- **Selection is myopic at the depth this receipt covers.** The greedy rule takes
  the best-scoring candidate one step at a time, and its depth-`2` advantage does
  not survive to depth `7`: in `helix7` the joint greedy curve rises to
  `96.36319123865479` at depth `4`, falls to `94.37736003975897` at depth `5`,
  and ends at `99.9111042223814`, below the declared order's
  `106.44288547693948`. Final ratios below `1` appear the same way elsewhere
  (`helix7` drive `0.9960210404210216`; read in `flat-ladder`
  `0.961165715359322`, `sparse-long-link` `0.9719131343022288` and
  `quasiperiodic-chain` `0.9848584447196246`).
- **Best and worst write-read pairs.** Over all `784` ordered pairs in `helix7`
  the best transfer is the self-pair `(0, 0)` at `0.8357831008621412` (reverse
  `0.8320175697252943`), the worst is `(27, 0)` at `4.329323400802432e-16`, and
  the mean is `0.13180732083016702`; maximum absolute asymmetry between a pair
  and its reverse is `0.07039626517811481` (mean `0.009502236059097901`). The
  self-pair result matches: `0.9285714285714286` of `helix7` write ports have
  their own port as strongest read partner (ports `1` and `26` excepted), the
  best pair is a self-pair in seven of the eleven arrangements, and `undivided` —
  where the write and read tables coincide — places its best pair at `(5, 22)`
  and self-pairs only `0.42857142857142855` of ports.
- **Write rank and read rank move together.** The per-port Spearman correlation
  between drive effective modes and read effective modes runs from
  `0.6945812807881774` (`isolated`) to `0.9994526546250684` (`undivided`), and is
  `0.9693486590038314` in `helix7`.
- **No consensus placement across arrangements.** No port appears in all eleven
  top-five sets: consensus size `0` for the drive, read and joint families alike.
  Mean Jaccard overlap of the top-five sets is `0.23607503607503608` (drive),
  `0.23852813852813853` (read) and `0.08275613275613275` (joint), the eleven
  arrangements yield `10`, `10` and `11` distinct top-five sets, and the maximum
  overlap `1.0` belongs to `flat-ladder` against `quasiperiodic-chain` in the
  drive and read families, with the joint maximum `0.42857142857142855`.
- **Retention cross-check.** The per-port Spearman between drive effective modes
  and the geometry harness's 64-tick retention walk is `0.8214285714285714` in
  `helix7` but `-0.2857142857142857` in `undivided` and `0.10714285714285714` in
  `nested-core-shell`, so modal reach and site retention are not the same
  measurement.
- **Three declared separations, each able to fail, are satisfied here.** In
  `helix7` ports `0` and `4` separate by `2.0` beyond the declared margin
  (`16.699271940345195` against `26.854653850935087` effective modes, measured
  separation `10.155381910589892`); in `nested-core-shell` ports `3` and `13` by
  `2.0` (`30.374138813884965` against `12.115344721921064`, measured
  `18.2587940919639`); and the arrangements `helix7` and
  `recursive-paired-loops` by `1.0` on their best placements
  (`30.16113222426118` against `26.432246954195232`, measured
  `3.7288852700659483`).
- **Recorded limits.** One port per direction, so simultaneous multi-port reads
  are outside the measurement; the write pin and the read pick-off coincide as
  state vectors, so reported asymmetry is the dual-versus-primal modal expansion;
  eigenvector gauge is fixed at unit 2-norm, so only signature magnitudes are
  compared and phase is excluded; the eigendecomposition is dense and
  non-symmetric, and a basis above the declared conditioning limit would be
  refused rather than reported; a placement is a port index, not an interior,
  junction or boundary classification; the retention cross-check uses one
  declared work budget and one horizon; and no placement can change the scaffold
  size, since the arrangements share pool count, port resolution and coordinates.

The receipt's own bound is "bounded measurement of modal access on the declared
linearization; placements are candidate ports, not memory or task claims", and
its declared boundary closes the reading: "Coverage, dominance and transfer are
scalar proxies on a declared linear scaffold, not measured task performance,
learning, recall quality or memory utility."

### Ladder

The same canonical 28-port body, one declared packet impulse per item at the
durability harness's declared budget, sources off, heartbeat zero, sampled every
`16` ticks to a declared horizon of `256`, read in the durability harness's
declared frame. Lifetime is the first sample below one twentieth of the post-write
alignment, censored at the horizon; a window/occupancy reading and a modal
projection onto the frozen linear generator `geometry.linear_generator` (`beta =
0`, `dt = 0.08` per tick) are reported beside it. Three declared profiles carry the
same ladder: the default `helix7`, `mass-only` and `flat-inertia`
(`_diag/fractal-ladder/exploration.json`, `content_digest`
`6208400bec247bf31920642c28d235430010c5da8152de4a0ea59c7825072935`). The body the
hooks run on is nonlinear (`beta = 0.08`, uniform quartic weights), so every modal
number is a reading of its declared linearization.

- **The rung-width ladder is not monotone in width.** Mean lifetime reads `32`
  ticks at width `28`, `72` at width `14` and `76` at width `7`, so
  `monotone_coarse_to_fine` is false and `ratio_coarsest_to_finest_means` is
  `0.42105263157894735`; the per-item lifetime groups are `[32, 32]`,
  `[32, 112]` and `[32, 64, 80, 128]`, occupancy is `0.26666666666666666`, and a
  log-linear fit over the three width means gives slope `0.3515651750984813`,
  intercept `3.5573413391827953` and `r_squared` `0.2660566747657408`.
- **The ladder's ordering belongs to the inertia profile, not the arrangement.**
  `mass-only` reads `80`, `80` and `60` at widths `28`, `14` and `7` —
  `monotone_coarse_to_fine` true, ratio `1.3333333333333333`, mean deltas `48`,
  `8` and `-16`, log slope `-0.23444356069654226`, `r_squared`
  `0.20526904889933706` — while `flat-inertia` crosses at the same sample at every
  width (`32` ticks, ratio `1.0`, slope `-4.2737188203366333e-16`, `r_squared`
  `0.0`). The receipt's `measure_dependent_ordering` is true on `mass-only` and
  false on `helix7` and `flat-inertia`.
- **Per-item lifetime, not a mean, carries the figure.** On `helix7` the eight
  written items finish at `0.003380437390550838` (root scale), then
  `0.0054472315525127095` (root detail), `0.001623168679797181` (left detail),
  `0.01931743706665975` (right detail), `0.047794482324372264` (left-left),
  `0.03897985663025755` (left-right), `0.132755198663829` (right-left) and
  `0.3338832936791157` (right-right); the corresponding first crossings are
  `32`, `32`, `112`, `32`, `64`, `80`, `32` and `128` ticks. On `flat-inertia` all
  eight cross at `32` and their final alignments spread from `0.6978200306386195`
  through `0.6633051673775967`, `0.6064154850657543`, `0.6051365415195096`,
  `0.5101926832254299`, `0.5019816568426033` and `0.49434921923110037` down to
  `0.4913539663563793`.
- **A corroborated linear predictor carries most of each progression.** Projecting
  the impulse onto the frozen generator tracks the measured progression at Pearson
  `0.993806638968675`, RMS `0.02501498423876922` and rank `0.9707757278886651` on
  `helix7`; `0.9974297813944415`, `0.01466451641459733` and `0.9753937007874016`
  on `mass-only`; `0.9578783270613275`, `0.07939443645455307` and
  `0.9237433620216078` on `flat-inertia`. Its block is named `exact_predictor`
  while carrying the label `"corroborated to 0.02, not exact"`: on `helix7` the
  first sample where prediction departs from measurement by more than `0.02` is
  `128` (right-detail), `96` (left-left), `112` (left-right and right-left) and
  `144` (right-right), while root-scale, root-detail and left-detail never depart
  inside the horizon; on `flat-inertia` every item departs at `112`. The same
  predictor reproduces the canonical walk to a `max_abs_error` of
  `0.007916000386612648` against the declared `0.02`, and repeating the impulse at
  work budgets `0.0005` and `0.001` gives `0.007916000386612655` and
  `0.007916000386612648`, so the residual is the linearization and not the write
  amplitude.
- **The predictor ranks the ladder but does not pick the write.** Its ordering of
  the items matches the measured ordering exactly on `helix7` and `mass-only`
  (rank `1`) and not at all on `flat-inertia` (rank `0`, where every item ties);
  `tracks_decay_rates` is false, true and false. Over the `56` declared single
  positions the best predicted final alignment is `0.5647630171763798`, whose
  measured retention is `0.47079331020702286`, while the narrowest declared
  channel — width `2`, max weight `0.09894576033966113`, effective lifetime
  `13.347961769626993`, not in the slow band — measures `0.10352647488220304`
  against a predicted `0.000723452743269613`; and the
  `predictor_optimized` search over write recipes improves nothing, its best
  measured recipe being the best single position at `0.3338832936791157` rather
  than the `0.003380437390550838` headline.
- **Concentration, not arrangement, orders the ladder.** On `helix7` the rank
  correlation of an item's maximum mode weight with its lifetime is
  `0.9132233209773137` and of its concentration `0.7483357769119654` (the
  effective-mode count correlates at its exact negative); on `flat-inertia` both
  ranks read `0`, because every one of its items crosses at the same sample and
  lifetime no longer varies. The
  modal ceiling says how much is left: on `helix7` the algebraic bound is
  `9.303861956486` against a realized `16.584510354073913`, a shortfall of
  `7.280648397587914` with the realized item still at `0.22024825904117448` when
  it crosses at `128`; `mass-only` reads `9.707498303036152` against
  `17.719952878690098`; `flat-inertia` reads `7.958290633252321` against
  `7.961201946246623` for a shortfall of `0`, because its best single write is
  already slow. For `helix7` the slow band is `48` modes with e-fold times
  `1503.9600396415437` to `1789.3152561759243` ticks, the whole spectrum spans
  `1042.0543715706076` to `1789.3152561759243` and is read as `5` discrete bands
  with `continuum` false; landing slow-dominated requires a mean maximum weight of
  `0.08151805813243117` and a mean effective lifetime of `19.372227574075932`,
  which is a gap of `2.787717220002019` to the realized figure and
  `10.068365617589933` to the algebraic bound. `flat-inertia` reads `3` bands with
  gaps `0.00001342321384208145` and `0.000013423213842071041`.
- **Recorded limits.** Lifetime is a first crossing of one declared threshold
  (one twentieth of post-write alignment), censored at the horizon, so a longer
  life than `256` ticks is not measured; the modal numbers are a projection onto
  the declared linear generator at `beta = 0` while the body itself is nonlinear;
  the profiles are declared rather than searched; the flat profile is a declared
  metric, so its flatness is a statement about that metric rather than about the
  arrangement; and the lifetime and occupancy readings are two readings of one
  trace.

The receipt's own bound is "Canonical-field numerical measurements in controlled
conditions only", on "three declared profiles (helix7, mass-only, flat-inertia)
via canonical hooks", and it closes: "Lifetime is first below-threshold censored at
horizon; window/occupancy give second measures." — "No task memory claim."

### Metric

The same canonical seven-pool body with the survival harness's declared readout
and arms taken by import: one ranked arm at k = 4 with the declared k = 2 and k = 8
arms reported beside it, a declared ranking margin of `0.02` and a headline margin
of `0.2`. The receipt declares `22` profiles — a designed family of graded shell
contrasts plus random controls and reference profiles — and every one of them moves
only the projected inverse-mass hook, so this is a ranking of `21` of them on one
rail, with one declared second rail measured for generalization
(`_diag/fractal-metric/exploration.json`, `content_digest`
`70d201c05f28790077c3ce12c2b2d3012a13e53c9ac5712bfe28adca9c997aae`).

- **A hard shell around the core is the best declared metric.** `shell-contrast-0.005`
  recovers `0.8442150578491289` against the canonical default's `0.0764836820747603`
  (difference `0.7677313757743686`), with a total packet energy ratio of
  `0.9697560926480527` and a heartbeat work total of `7.655591034869303e-12`; the
  best member of the graded family is its extreme endpoint
  (`best_is_extreme_endpoint_of_the_graded_family` true), the construction rule
  being `projected_inv_mass[port] = contrast ** ring_distance(pool, core)` with
  core pool 3. Every ranking row reproduces the survival harness's cited figures
  exactly — `helix7` `0.0764836820747603`, `mass-only` `0.33445984698946024`,
  `nested-core-shell` `0.3351631005750861`, absolute difference `0` against a
  declared reproduction tolerance of `1e-12` — and the canonical hook profile
  matches the default generator bit for bit with a k4 difference of `0`.
- **The advantage does not scale with the write set.** The best profile's
  advantage over the default is `0.7025931092793387` at k = 2 and
  `0.7677313757743686` at k = 4 but `-0.050619721471980315` at k = 8; its k = 2,
  k = 4 and k = 8 recoveries are `0.7065718697544376`, `0.8442150578491289` and
  `0.00001081564410689725`, and no profile scales at every declared k. Read beside
  the declared activity confound — a profile that makes most ports very heavy also
  reduces the work the body's own heartbeat can inject — the best profile that
  keeps the body working is `nested-shell-metric` at `0.33445984698946024` with
  heartbeat work `0.00014731806257090187`, not the headline.
- **A lifetime ladder in the ratios does not become a banded ladder.** Across the
  `8` declared ladder profiles the band-ratio claim fails for all six geometric
  ladders at the declared tolerance of `0.1`: deviations `0.12431527929747012`
  (ratio 1.3), `0.2606858588414554` (phi), `0.2341566167141048` (1.5),
  `0.7017369648207413` (inverse phi), `0.48351959024067015` (phi squared) and
  `0.2606044014952175` (matched random). Ranked at k = 4, `ladder-uniform` reads
  `0.8948910529922045`, the default ratio 1.3 `0.0764836820747603`, phi
  `0.044516447778668485`, inverse phi `0.036347809212466616`, matched random
  `0.028652029009751525`, 1.5 `0.006478454927961688`, phi squared
  `0.002268253837956744` and arithmetic-equal-width `0.001753557587223216`. Phi
  beats neither the default ladder (`0.044516447778668485` against
  `0.0764836820747603`, difference `-0.03196723429609182`) nor its matched random
  control (`-0.01586441876891696`). Where a ladder does exist, its band ratio is
  order-independent — phi `1.246732297240734` against matched random
  `1.2468338568814694` — while its lifetime ladder ratio is order-determined (phi
  `1.209598097853437` against matched random `0.9234604180833687`).
- **The flat metric wins the ranking.** `flat-inertia` reads `0.9089176819482955`,
  `0.8948910529922045` and `0.8733468983727672` at k = 2, k = 4 and k = 8, which
  is `0.5650469075766262`, `0.5604312060027443` and `0.8580719754261275` above the
  reference metric; its horizon instrument mean is `0.5713193437821241` against
  the default's `0.07289763824838687`, with minima of `0.4913539663563793` against
  `0.001623168679797181`, all `8` declared items above the default and none below,
  and a transfer mean of `0.566812948558346` against `0.13180732083016702`. Its
  rank agreement with the default is only `0.06830855337962112`: it wins on level,
  not on ordering.
- **The margin shrinks once the clocks are matched.** The flat profile reaches its
  declared e-fold count at `216` ticks while the default's declared horizon is
  `256` (tick scale `0.84375`), so its lead falls from
  `0.49842170553373727` at the declared horizon to `0.0216390553375755` at equal
  time — still above the declared margin of `0.02`, with a window mean lead of
  `0.1893940145911284`, final means of `0.09453669358596237` against
  `0.07289763824838687` and a slowest-decay ratio of `1.1826247147274347`. The
  mechanism is a narrower decay span (`0.00025395969505240257` against
  `0.005009622697615415`) with more of each written direction in the slow modes
  (overlap difference `0.20909112949821995`, participation difference
  `0.042544423599891745`); the default's slow overlap and participation minima are
  `2.1153182505063406e-11` and `3.644052786967645e-11`.
- **Two declared band rules disagree on exactly one profile.** Over the `9`
  profiles where both rules are declared they agree on `8` and disagree on
  `ladder-uniform` alone — the ladder harness's range-relative rule reads `3`
  bands there where this runner's ratio-relative rule reads `1` continuum — and
  neither rule is claimed as the band structure.
- **Cross-talk is the discriminator the flat metric passes.** On the flat profile
  every declared item keeps its own slot: the smallest own-minus-largest-unwritten
  figure is `0.49119910771343345` against the default's `-0.22728039960892008` at
  a declared margin of `0.05`, all `8` items are distinguished, the
  own-over-unwritten ratio is `369.63703999954527` against `1.1658013985730282`
  (nested-shell-metric `1.3418163408514272`, nested-core-shell-reference
  `1.8621900771074582`), and the mean largest unwritten share is
  `0.001545622548494672` against the default's `0.06253006587366897`. The same
  block still records `every_profile_keeps_item_content` false: the profiles
  `default-inertance`, `nested-shell-metric` and `nested-core-shell-reference` are
  listed in `profiles_without_item_content`, so keeping item content is not a
  property of every declared metric.
- **Local contrast is not a substitute for a global shell.** In the declared
  family of `6` local-contrast profiles (contrasts `0.25`, `0.5`, `2` and `4` on
  pool 3, and `0.5` and `2` on pairs 2-5), every declared contrast lands below the
  flat anchor, none improves on the flat profile at k = 4 or k = 8, and only the
  direction is right: retention falls as the contrast magnitude grows.
- **The ranking generalizes past the rail it was ranked on.** On the declared
  second rail, `recursive-paired-loops`, the same top profile reads
  `0.8562202612048629` against the default metric's `0.061124304880849925`
  (difference `0.795095956324013`, margin `0.02`), with the default reproducing
  the survival harness's cited figure exactly (absolute difference `0`).
- **One aimed write is cited, not re-measured.** The receipt carries a
  `cited_external_figure`: a declared `RRRR`/detail impulse of width `2` retains
  `0.47079331020702286` on the same no-hook canonical default body, dominant in
  the slow band with a slow weight of `0.999999999999905`, cited at a tolerance of
  `0.000001` from
  `_diag/fractal-ladder/exploration.json#exhaustive_write_surface.helix7.measured_top[0]`,
  whose receipt `content_digest` is
  `6208400bec247bf31920642c28d235430010c5da8152de4a0ea59c7825072935`. The receipt
  records that the two slow-mode figures it reads beside that citation are its own
  measurements, not the cited harness's, so the table separates "this write was
  not aimed at a slow mode" from "this body cannot store".
- **Recorded limits.** The ranking is a ranking of the declared four-item arm at
  the declared horizon on one rail, at a declared resolution and one declared
  activity level; the heartbeat's work allowance is metric-dependent, so every
  entry is read as conditional on the body still working; the two local families
  are declared rather than searched; the band rules are declared tests rather than
  a spectrum claim; and the declared directions are not the default body's slow
  modes.

The receipt's own bound is "Controlled canonical-field measurement only, on the
canonical seven-pool body at the declared resolution", and its declared boundary
closes with its two design readings: "aim the write, and choose a metric under
which the declared item directions are slow modes."

### Lattice

The canonical seven-pool body read as a declared arrangement. `66` arrangements
are built from the field's own derived motif and measured with instruments imported
from the geometry, durability, survival and placement harnesses; `64` checks with
declared margins are recorded, of which `38` hold and `26` land outside theirs, and every
check carries a firing control (`_diag/fractal-lattice/exploration.json`,
`receipt_sha256`
`006dc8b0ae312d56f5efb6bda9896586ab26857e7c9cd66710da93548623dd92`; the receipt
carries that digest field only).

- **The built-in body is a double helix with no rungs between its strands.** It
  declares `28` positions, seven pools of four sub-stations, a station gap of
  `0.03571428571428571` (relative spread `2.7200464103316335e-15` against a `1e-12`
  allowance), a radius law `1 + 0.08 sin(pi t)` spanning
  `1.0044856357789753` to `1.0798741452014253`, the second strand as the point
  reflection of the first, strand-pair 3D distances with minimum
  `2.0089712715579506`, mean `2.101912611649286` and maximum
  `2.1597482904028507`, and inertances `1.3 ** pool` ranging from `1` to
  `4.826809000000001`. Its adjacency is `56` circuit entries, `28` intra-ring links
  and `6` neck links, with the intra rings and neck links declared on the Yang
  strand only (the Yin strand carries `0`), and the two strands meet only at the
  two endpoint bridges — so the motif has no rung ladder between strands. The
  field's own derived rail L1 `3.426843625438269` is reproduced to
  `1.3877787807814457e-17` against the `1e-12` allowance.
- **The phi spacing law does not move the figure it was declared to move.** On the
  bare motif, spacing the stations by phi leaves the survival k4 figure at
  `0.08845894491839329` against the uniform `0.07648368207476033`, a difference of
  `0.011975262843632956` below the declared margin of `0.02`; the phi coupling
  reads `0.08390375555651705` (difference `0.007420073481756717`); the phi-graded
  inter-copy coupling reads `0.07661544652594326` against the uniform
  `0.07483143508665194` (`0.0017840114392913275`) and against the matched-random
  control `0.07623218511236966` (`0.00038326141357360177`). The phi-band
  self-similarity index moves the wrong way: uniform `0.1992644351831003` against
  phi-spacing `0.08105033362408658` (quantity `-0.11821410155901373`, margin
  `0.05`), the octave band `-0.07067184674858429`, the phi-graded lattice
  `0.015260135811188444`, and the log-periodic order `-0.15940676993579642`
  (margin `0.01`). The positive control shows the instrument can see an order when
  one is declared — a phi ladder reads a phi order of `0.9999999999999999`, a 2.0
  ladder `0.9999999999999999`, and the arithmetic control only
  `0.30243656668881286` — and one geometric effect does hold: the phi station law's
  median mode participation ratio moves from `0.1565230898708429` to
  `0.2015156924591439` (difference `0.04499260258830101` against a `0.01` margin),
  where the phi-graded inter-copy coupling's does not (`0.18405385310766828` to
  `0.18298688531526747`, quantity `0.0010669677924008136`).
- **The rung law's gain is shared by the steep ramps.** Across `8` declared rung
  laws on the same `28` positions and the same declared channel total of
  `3.426843625438269` (maximum relative deviation `1.2959132612690103e-16`), the k4
  figure spans `0.2640718387297407`: the 1.5x ramp reaches `0.2646895818131007`,
  phi reaches `0.2510475666353221`, the centred law is worst at
  `0.0006177430833599711`, and the phi-minus-best-steep-ramp difference of
  `0.013642015177778632` sits below the declared margin of `0.02` — the receipt's
  reading is "shared by the steep ramps". Orientation matters more than shape (the
  phi ramp against its own reversal differs by `0.24766562338456635`, a shuffled
  phi ramp against the phi ramp by `0.10398078641278186`, a centred law against
  phi by `0.2504298235519621`), a single-position law still moves the figure by
  `0.061053936150844666`, and at k = `8` no law survives the declared margin (best
  uniform `0.044189144392425696`, delta `-0.006441392723661468`, phi
  `0.00022691821299357525`).
- **Damage to the mass channel is non-monotone rather than gradual.** In the
  declared interaction grid (rail fraction `0`, `0.25`, `0.5` and `1` against the
  mass channel off or on) the rail weight cuts the mass gain by
  `0.307957629349784`, but the mass leg's largest non-monotone step is
  `0.08265282093908742`, its half-slopes are `-0.3778148790362934` and
  `-0.2381003796632746` (a gap of `0.1397144993730188` above the `0.02` margin),
  and a linear fit in rail weight leaves a maximum absolute residual of
  `0.12543632788939646`; the declared shape label is "non-monotone or
  thresholded". The rail leg is monotone decreasing (Spearman `-1`, slope
  `-0.06559965926198179`, fit residual `0.022820825697295974`), and the grid
  reproduces the declared arms it is built from to `2.7755575615628914e-16`
  against `1e-12`.
- **The flat depth axis belongs to the declared shell laws.** On the equal-budget
  depth axis with the uniform shell law the k4 figure is `0.08414445644435513` at
  depth 1 and `0.0841168667762352` at depth 4, a deepest-minus-shallowest
  difference of `0.000027589668119928912` below the `0.02` margin, while the raw
  reference-law family separates strongly (`0.3351631005750861` at depth 1 to
  `0.0019170719781796512` at depth 4, spread `0.5919140403942391`); the receipt's
  depth-normalization reading records `place_of_the_flat_axis` as "depth itself",
  under the declared partitions. The depth-1 anchor reproduces the cited single nest exactly
  (`0.3351631005750861` at k4, median participation ratio
  `0.15986442406282375`, rail difference `0` against a `1e-9` tolerance), the axis
  saturates by the deepest declared depth (`0.0002174906702616386`), and the phi
  shell law at the deepest depth lands on the other side of its declared margin:
  `0.00014591695715924398` against the uniform `0.0841168667762352` (quantity
  `-0.08397094981907595`).
- **The attribution arms do not add.** The compound arm moves the survival k4
  figure by `0.0029094294864237674` while its two declared legs move it by
  `-0.05476911742465073` (rail) and `+0.25797616491469977` (mass), leaving
  additivity residuals of `0.20029761800362528` at k4 and `0.26354336047460836` at
  k2 against a declared tolerance of `0.01` — well outside it, which the receipt's
  boundary states is itself the measured statement that the two channels interact
  rather than a claim of linearity.
- **What the lattice does move.** On the k2 survival arm the best declared lattice
  beats the canonical body by `0.07247761292711728` (margin `0.02`); at k4 the best
  declared lattice is the compound arm `ring-phi-up-rungs-mass`, at
  `0.0793931115611841`, and it clears the body by only `0.002909429486423795` —
  below the margin — while sitting `-0.25576998901390197` against the cited nest it
  is built from; at k8 the best lattice falls `-0.04651377922538234` behind. The
  bare-motif rung arms do move the figure — `0.17456388456056174` for the phi rung
  law against the un-runged motif, `0.18797981348581083` between the two declared
  rung laws, and `0.1165845648604269` on the write-rank/read-rank agreement — and
  declaring the 28 strand-to-strand rungs on the uniform ring lattice takes that
  lattice from `0.07483143508665194` down to `0.0007645725064649555`, a move of
  `0.07406686258018698`.
  Access moves: the best lattice's coverage is `0.0738051162811333` against the
  canonical `0.06111459857739958`, clearing the `0.005` margin, while placement
  rank agreement moves the wrong way (`0.9693486590038314` to `0.9518336070060208`,
  quantity `-0.01751505199781056` against a margin of `0.05`) and the top-seven
  drive ports differ by `14`.
- **Recorded limits.** The expressible form is the rail the field's own weight rule
  assigns, not a lattice of positions; `profile.edges` is ignored whenever
  `projected_transport` is set, so each arrangement re-declares its structure
  through hooks and carries `topology` as metadata; a declared rung is one
  antisymmetric strand-pair entry, so a symmetric inter-strand exchange cannot be
  declared at all; the shell metric available to the mass arms is diagonal per
  position; the band statistics read a finite `112`-mode truncation, so none of
  them is a claim about a self-similar measure on an infinite lattice; the
  phi-graded rung law is an unbounded ramp that concentrates its channel at one end
  of the helix after normalization; the rung controls are declared laws of one
  declared channel total rather than a search; the interaction grid's intermediate
  rail fractions are new declared arrangements rather than interpolations; and the
  nested family's extra levels are declared partitions on the same seven pools, not
  additional spatial shells. The receipt records `14` limitations in total.

The receipt's own bound is that "Every number is a geometric, spectral, survival or
placement proxy on a declared scaffold", its rung and nested families are declared
rather than comparable across families ("cross-family rung magnitudes are not
comparable and are reported as measured numbers, not as a controlled contrast"),
and its `declarations.boundary` closes: "No arrangement claim here is a claim about
memory utility, learning, or task performance."

### Feedback

The canonical body with a closed transceiver loop around it. One iteration
advances the full page one tick, reads the canonical read frame, projects it onto
the captured write direction (`S_t`) and the declared quadrature direction
(`Q_t`), and applies one bounded packet impulse whose flow signal is
`cos(theta) * S_t + sin(theta) * Q_t`, at per-tick work no more than the declared
ceiling `0.001`. The loop runs on the full canonical page with the canonical read
frame as its read-back, is expressible with existing operations and adds none, and
its declared one-tick stream reproduces the durability harness's chunked stream
page for page at every declared sample (identical page digests at ticks `8`, `16`,
`32` and `64`, against an identity allowance of `0.0`). Sources are off, and the
drift baseline is the durability harness's source-off single-item series,
reproduced here at zero difference on those four samples. The declared phase grid
runs five angles at four gains and the neutral-gain sweeps run their own rungs,
each over the declared horizon of `64` ticks; the hold, quiet, capacity and split
families run the declared long horizon of `512` ticks, sampled every `16`
(`_diag/fractal-feedback/exploration.json`, `receipt_digest`
`fdc2e1443d95e010bae1bb8974980e9e1dff5047946f135dbaa5d30c243eb63b`).

- **The loop is a phase-inverted pump, not feedback at large.** The best arm is
  `closed-loop-phase-180deg-g4` at `19.60303769852896` alignment retention at the
  declared `64`-tick horizon, against the drift baseline's `0.31149818467501866`
  at the same horizon; the measured best angle is exactly
  `180` degrees, and `best_theta_is_the_quarter_period` is false by `90.0` degrees
  from the declared quarter period (`90.0` degrees, measured `93.08894631518223`
  degrees at tick `29`, a rotation rate of `3.2099636660407667` degrees per tick
  and zero measured overlap between the write direction and the declared
  quadrature lane). The in-phase variant fails: at `0` degrees the four declared
  gains reach `0.0073953865048774995`, `0.017988000220178244`,
  `0.07121302684347118` and `0.36457753849278435`, below the drift baseline at all
  but the last and meeting the declared prediction at none. The quadrature variant
  fails too: at `90` degrees they reach `0.08992325347010156`,
  `0.27693708787027854`, `0.9067817263489296` and `3.0859588728091385`, so they
  beat the drift baseline from gain `2` on, but at gain `4` their largest unwritten
  declared direction reaches `0.9829017399958195` against the declared allowance
  `0.220886485269163`, so none meets the prediction. Only the eight `135`- and
  `180`-degree arms meet it, and there the same share stays at or below
  `4.677033925098166e-05`. A loop
  fed back on either the in-phase or the quadrature component would not maintain
  the direction, so what is measured is the sign inversion specifically.
- **The neutral gain is a property of the field it was measured on.** Over the
  declared `64`-tick horizon, on the default `helix7` metric, the loop neither
  grows nor decays the written mode at `0.04765625`, bracketed by
  `[0.046875, 0.0484375]` (width
  `0.0015625000000000014`), with the probe below the bracket reading
  `0.9995050824774236` and the one above it `1.0022471864412241` at a declared
  tolerance of `0.002`. On the flat-inertia metric at the same horizon it is
  `0.02734375`, bracketed by
  `[0.026562500000000003, 0.028125]` (width `0.001562499999999998`), with
  `0.9987659126615722` below and `1.0015300650736005` above, and that profile's
  drift arm reads `0.37806235541656424` where the default's reads
  `0.31149818467501866`. The receipt's reading is that the gain solves the loop's
  declared work balance against the state's momentum at the moment of the drive, so
  it is an operating point of the field it was measured on and the flat profile's
  own gain is measured there rather than the default value being reused: the
  default value does not transfer. The declared loop-equation prediction of that
  gain is not inside its declared allowance (`prediction_within_allowance` false,
  relative error `0.273060510227869`), and the in-phase arms are recorded as
  outside the prediction's declared domain (relative error `85.56173315654915` at
  `0` degrees and gain `0.5`).
- **At its own neutral gain on the flat profile, one written item is held over
  `512` ticks.** The driven item's retention at the horizon is
  `1.0488762323951002`, its mid-window reading `1.0072066717386978` and its
  worst-half minimum `1.0085537084543224`, all above the written deposit, so the
  declared neutrality criterion holds; the largest unwritten declared direction
  reaches `0.007336271141679331`. Its own no-loop control — the same two items
  written and nothing driven — reads `0.37806235541656424` with an unwritten
  maximum of `0.007158387416335813`, so the hold exceeds its control by
  `0.6708138769785359` against the declared `0.01` margin. The held arm's frame
  energy ends at `0.7537586059726674` of its post-write value against the
  control's `0.45885005536433676`.
- **The loop is selective: it holds what it drives.** In that same two-item frame
  the driven `root-scale` holds at `1.0488762323951002` while the written but
  undriven `left-detail` decays to `0.2427198345795942`, `0.18792240142703198` of
  the written pair's remaining share. The falling frame energy belongs to that
  other content, not to the profile or to the gain: with only the held item written
  the frame ends at `1.0488853970132441` for `root-scale`, `1.0488855912498656`
  for `left-detail` and `1.0488857790032413` for `left-left-detail` at the same
  gain, and at the declared multiples of that gain `1.4526695345258913` (x2) and
  `2.456676953170718` (x4), so it rises at every declared rung —
  `every_declared_gain_falls` is false and `items_with_falling_energy_while_holding`
  is empty. The default metric's single-item hold rises as well (`1.1128929007050585`
  retention and frame `1.1130533006115702` at gain `0.04765625`), so the declared
  expectation of a falling frame under a quiet hold is not what the rows show.
- **On the flat profile the declared capacity curve does not turn over.** Counts
  `2`, `3`, `4` and `8` are each run under three declared schemes — one shared
  read-back with the per-tick ceiling split equally, one item per tick on a
  declared cycle, and a per-item read-back through each item's own direction and
  phase reference — each answered against its own declared no-loop control. Every
  scheme holds every declared item at every declared count, so the reported limit
  is the largest declared count, `8`, because nothing failed there. The smallest
  hold margin per scheme falls monotonically with count: `shared`
  `0.5652530134477354`, `0.5254826759202942`, `0.4900426102891538`,
  `0.40934017781357535`; `phase-locked-per-item` `0.5652521941360336`,
  `0.52548062317943`, `0.48934133015906806`, `0.40870679440163127`;
  `time-multiplex-adjacent` `0.5578442037732945`, `0.48474610044051747`,
  `0.4375437731057175`, `0.2400501989293624` — all far above the declared `0.01`
  margin. Work does not grow with count either: against the declared per-tick
  ceiling of `0.001` the schemes draw `7.366718699064544e-07`,
  `7.346518684627094e-07` and `7.346356547775289e-07` at count `2`, and
  `7.216088051565398e-07`, `6.94051207476963e-07` and `7.080430175022705e-07` at
  count `8`, never exceeding `7.65345384840313e-07`.
- **On the default metric the declared capacity is two in every regime, and the
  naive shared drive is not what holds it.** The declared criterion reads "two when
  at least one declared scheme holds both in that regime, one otherwise", and under
  it the reported figure is `2` in the neutral, bounded and amplifying regimes
  alike, each against the same drive-free two-item control
  (`headline_second_half_mean` `0.00620761471495241`, `second_second_half_mean`
  `0.021079762359478917`). What holds both is `phase-locked-per-item` in all three
  regimes and `time-multiplex-block` in all three, with
  `time-multiplex-adjacent` holding both only in the bounded regime; what fails to
  hold both is `locked-on-headline` in all three regimes and the shared two-item
  drive in all three regimes, with `time-multiplex-adjacent` also failing in the
  neutral and amplifying regimes. The shared drive is not merely short of the
  margin: at the amplifying gain it puts its second item below its own no-loop
  control, reading `0.0027182461250039205` against `0.021079762359478917`, a
  difference of `-0.018361516234474996`, while its driven item reads
  `270.8145923752895` against the same control's `0.00620761471495241`. Eight arms
  sit above the declared energy bound at their own horizon and none diverges
  (`divergent_arms` empty, largest frame-energy ratio `359.42231886017254`).
- **The two lanes share one refresh budget and stay separable.** In the shared
  two-item scheme the two items receive the same signed amplitude
  (`applied_amplitude_max_difference_between_items` `0.0`) and their per-tick
  increments move together (sign agreement `1.0`, correlation
  `0.9999959258492868`). Cross-lane leakage is negligible: the largest fraction of
  one item's drive increment landing in the other item's lane is
  `4.927962371328255e-17` of the driven item's own increment. Retention still
  follows the split of the budget — over the five declared splits of the per-tick
  ceiling the two items' back-half means swing by `0.20791294665986892` and
  `0.19223518174921572` against the declared `0.01` margin, and all five splits
  hold both items, so `split_dependent` is true — so what the two items share is
  the work budget their drive divides, not one item's state, and the verdict is one
  shared refresh budget with separable lanes. The receipt does not name a
  suppression mechanism for the shared scheme at this gain (`mechanism_measured`
  false) and reports the measured residuals instead.
- **A defect found in this harness was fixed before these figures were taken.**
  The per-tick cross-reading was keyed by the lane being read rather than by the
  driving item, so on a tick where more than one item was driven the later calls
  overwrote the earlier ones and only the last call's reading of the other lanes
  survived. It now keys by the driving item
  (`run_fractal_feedback_exploration.py:3123`), and the regression asserts each
  item's recorded cross-increment entries against the per-tick telemetry
  (`test_fractal_feedback_exploration.py`). What that invalidated is the cross-lane
  reading wherever a frame drives more than one item on a tick — the five split
  arms and the multi-item capacity arms above — which is exactly where the leakage
  fraction is read; the single-item and locked arms were unaffected.

The receipt's own bound is "Canonical-field numerical measurements in controlled
conditions only", and it records that a maintained pattern under the saturating
loop is accompanied by the measured frame-energy amplification and by a measured
disturbance of the unwritten declared directions above the baseline. It closes
that over the declared long horizon the growth is "decelerating but unbounded
growth inside the declared 512 ticks" with no plateau and no asymptotic energy
ratio claimed, that the measured neutral gain is "a property of the declared
horizon and read-back, not a stability threshold of the field's dynamics", and
that the capacity limit "is the largest number of declared items any *declared*
scheme holds, not a bound on schedules no declared loop implements". Nothing here
demonstrates task-level memory utility, semantic content, retrieval by a consumer,
owner-level checkpoint identity, a distribution of outcomes over profiles or
items, or any advantage over alternative architectures.

### Owner write path

The field's own canonical packet impulse lifted into a real owner transition, then
run through the declared closed loop and read back. One declared profile,
`ladder-uniform`, the metric harness's equal-total-inertia flat-inertia member
(`beta = 0.08`, `28` ports, `112` phase-space coordinates); one declared written
item, `root-scale`, with a declared two-item counterpart, `left-detail`; one
declared write budget of `0.001` per item; the feedback harness's `180`-degree
closed loop at this profile's own freshly measured neutral gain; the durability
harness's canonical `112`-coordinate read frame; and the declared long horizon of
`512` ticks sampled every `16` (`_diag/owner-write-path/exploration.json`,
`receipt_digest`
`a1f5c4ffe42a9c25182cf25ec54ab2e5bff7ff51147e2d51d98a6234072e9f7c`). The
receipt's `question` is whether the owner can accept a written impulse at all,
whether the impulse reaches the field, whether a pattern written through that path
survives the declared loop and reads back, and whether the owner can read a
written direction's deposit back as a declared prediction rather than as evidence.
The reading taken is the minimal one: lift the canonical impulse — the write route
every exploration harness already uses — into a transition the owner accepts,
rather than give the declared input realization authority it does not have.

- **The declared transceiver input is inert on this profile, and port selection
  is why.** In the shipped realization (`full`, compact map absent) the input
  moves the state exactly by its lift — a unit-norm lift
  (`0.9999999999999999`) times the scan's span predicts a state-delta norm of
  `3.4999999999999996` and the measured delta is `3.4999999999999996`, a fraction
  `1.0` of it — while the declared readout moves by
  `1.6263032587282567e-19`: the lift is supported on the input port's coordinates
  `[0, 28]` and the readout row on the output port's `[4, 32]`, whose overlap is
  empty and whose dot product is exactly `0.0`. In the declared `beta = 0`
  counterpart, where the compact path is admitted, the input is annihilated before
  it reaches the state — the compact map's drive column measures
  `2.6233574493654266e-19`, its direct term `[0.0]`, the state delta
  `9.15584511721332e-19` and the output spread exactly `0.0` across the declared
  scan — so the ledger of the two mechanisms is "annihilated in the reduced
  realization, invisible to the readout in the full one". The same construction
  fires once the declared precision carries a cross term
  (`0.007825627239176935` against `1.6263032587282567e-19`), so what closes the
  channel is this field's declared problem rather than a dead code path, and the
  shipped feedback receipt's own input-authority probes are cited beside it at
  `5.421010862427522e-19` (`7.532772993847057e-16` relative) on the durability
  profile and `0.0` on the declared beta-zero counterpart.
- **The owner accepts a written impulse.** `write_packet_impulse` publishes one
  immutable successor (`generation 0 -> 1`), keeps the logical tick and the
  evidence clock unchanged (`0` before and after), returns its retained result on
  an identical replay without writing again, refuses a conflicting call under the
  same identity (`FieldIntelligenceError: operation identity is already bound to
  different request semantics`), refuses a stale predecessor stamp
  (`FieldIntelligenceError: packet impulse predecessor does not match current
  state`) while accepting a matching one (`generation 2`), and preserves the
  written page, state digest and tick across a close and reopen — the page at
  close equals the reopened page
  (`b5b408a027dd8af109f22347fda0bf1c87fac220f9b1b2edd9fd10f89f41f3c0`), the
  state digest and the read frame are identical (maximum absolute difference
  `0.0`), and the generation is `2` on both sides of the close. The write keeps
  the evidence clock because a write is an intervention rather than evidence. The
  impulse itself deposits `0.005023668285714286` in the declared read frame,
  `1.0` of that item's own captured deposit against the declared fraction `0.5`,
  while the same write at zero requested work deposits `0.0`, fails the same
  predicate and leaves the page digest unchanged.
- **Route identity: the owner-written page is the page the existing route
  writes.** The same two declared items at the same budget, written once through
  each route and compared on the canonical page, the workspace state digest, the
  ledger and the read frame, agree exactly: page digest
  `cc46d71108efe1c1c1eaf72e00d4b6440f3d3576227d77972656ad5d20708d20`, state
  digest `243d73aaecf3ee77015e4488582403a333e01074a6fd160f3ca27d8b3887655b`,
  identical ledger, read frames differing by at most `0.0` against a declared
  identity allowance of `0.0`, and per-item deposits
  `0.005023668285714286` and `0.0050236682857142875` equal on both routes. The
  transition adds ownership, not a second drive.
- **The cycle holds the written direction at the field's own neutral gain.** The
  gain is re-measured in run at `0.02734375`, bracketed by
  `[0.026562500000000003, 0.028125]` (width `0.001562499999999998`) from five
  bisection probes over a four-gain grid on this profile, with the probe below the
  bracket reading `0.9987659126615722` and the one above it `1.0015300650736005`
  at a declared tolerance of `0.002` — so the default profile's gain does not
  transfer here. At that gain the owner-written item holds the declared `512`
  ticks at fidelity `1.0488848420422625` of its own deposit (frame-energy ratio
  `1.0488853970132441`, recovered deposit `0.005269249516334153`, `512` drive
  calls drawing `0.0003942357322945455` against the declared per-tick ceiling of
  `0.001`), exactly the figure the same item written through the existing route
  and held by the feedback harness's own loop reads back
  (`1.0488848420422625`, difference `0.0`), while the same owner-written page with
  no drive reads `0.38159216365362947`. The hold therefore beats its own no-loop
  control by `0.667292678388633` against the declared margin of `0.01` and passes
  the declared neutral floor `1.0` while the control does not. The readout is
  item-specific: the written direction reads `1.048884837881875` higher than a
  declared unwritten direction, whose share of the frame at the horizon is
  `4.160387481335385e-09`. The runner's own loop skeleton is licensed by an exact
  control rather than asserted — on a page both routes build from the same write,
  its sample rows, page digests and state digests are identical to the feedback
  harness's own loop across `32` compared samples, with maximum fidelity
  difference `0.0`.
- **The declared ports own disjoint supports, so overlapping selection is not a
  choice this profile offers.** All `28` ports are enumerated with their support
  coordinates — port `p`'s common pair `{p, 28+p}` and strand pair `{56+p, 84+p}`
  — and the search is exhaustive over the unordered pairs: all `378` pairs are
  disjoint and `0` overlap. The shipped selection is the measured inert one
  (spread `1.6263032587282567e-19`, dot `0.0`, empty overlap); the nearest
  overlapping selection, both declared variables bound to one port, is refused by
  the library (`ResonantNumericalError: inconsistent common-coordinate
  constraints`) on this profile and on the five other declared profiles tried; and
  the coupled-relation control fires (`0.007825627239176935`) *with the same two
  disjoint supports as the inert case*, so the authority it measures comes from
  the declared relation rather than from a shared coordinate. The receipt quotes
  the design text — "Ports refer to existing field variables. The current compiler
  selects explicitly requested charts and ports; it does not autonomously discover
  a useful decomposition." and "A changing input is a boundary drive" — and states
  its reading as a proposal beside the measurements: read strictly, the text
  supports giving the channel authority by declaring a coupling and not by
  choosing overlapping ports, which is also what this library can do, since an
  overlapping selection is refused here while a declared coupling is expressible
  and fires. The choice is left open and no declared problem is changed by this
  runner. The write touches lanes `2` and `3` of all `28` ports while the declared
  readout sits on lanes `0` and `1` of port `4`, which is the same disjointness
  seen on the canonical page rather than in the realization.
- **The read half names a written direction and moves nothing.** The surface
  publishes `44` operations, `13` of which declare no state transition; the new
  one is `read_packet_deposit`, declared `readout_kind` `temporal-prediction` with
  `evidence_added` false, and it recovers the written deposit exactly:
  `0.005023668285714286` against the written `0.005023668285714286`, a relative
  difference of `0.0` against a declared allowance of `1e-12`, the same number the
  library's own captured direction gives, and the same direction digest
  `f53777f3d2e0719db51e8d79869cecfe0fd626326805ea5d94ea81ab1c625d2c` the
  durability harness captured for that write. Both controls miss it and both can
  move: the same direction on a blank page recovers `0.0` and the declared
  direction the owner did not write recovers `0.0`, while under the declared
  direction-blind mutation the unwritten direction recovers
  `0.005023668285714286`, the clean readout returns once the mutation is removed,
  and the mutation leaves the page digest unchanged. The read leaves the page
  digest, the field generation and the evidence tick unchanged, with both
  published payloads byte-identical across the reads, and the checks are live: the
  write the read reads does move the page digest and the generation, and the
  owner's own observation-admission rule moves the evidence clock `0 -> 1` on a
  separate state of this profile. On a page carrying both declared items the read
  recovers `0.005023668285714286` and `0.0050236682857142875` of the page's whole
  read-frame energy `0.010047336571428573`, each at its own share
  (`0.4999999999999999` and `0.5000000000000001`), so recovery along a written
  direction is a measured projection rather than a page summary. The exposure scan
  counts the change: `2249` published key paths before the read operation, `0` of
  them naming a deposit or a written direction, and `2263` after, `5` of them
  naming one (`direction_sha256`, `flow_signal`, `read_frame_coordinates`,
  `read_frame_energy`, `recovered_deposit`), with the same matcher finding no path
  naming a word the surface does not publish. The closest surface the owner had
  before is the transceiver readout: it does carry the written page over a
  zero-input advance (outputs `[0.00042607530838883914, 0.0008505411534333908,
  0.0012723186506902757, 0.0016903370919887294]` against a blank page's zeros,
  maximum difference `0.0016903370919887294`), it reads its own output port's
  common pair `[4, 32]`, and it too is a temporal prediction.
- **Two items under a shared work split: an honest negative.** All five declared
  splits beat the no-loop control's own recovery (`root-scale`
  `0.37806235541656424`, `left-detail` `0.22859901291648002`) by more than the
  declared margin `0.01` — by `0.502446345187487` and `0.6349452847030262` — and
  retention follows each item's own share, but no split holds both items at the
  declared floor `1.0`. The uniform split gives `0.8805087006040512` and
  `0.8635442976195062`; the `0.9`/`0.1` split holds `root-scale` at
  `1.0213972076689257` and drops `left-detail` to `0.7357388573499184`; the
  mirrored `0.1`/`0.9` split does the reverse (`0.7500242107055632` against
  `0.9809364464264952`); the `0.7`/`0.3` and `0.3`/`0.7` splits land between them
  (`0.9496533808410705`/`0.8009423942107761` and
  `0.8139650722937104`/`0.9235428401962076`). So on this profile at this gain one
  shared drive channel does not neutrally hold two items: the split moves recovery
  between them rather than giving each its own lane. The `0.9`/`0.1` split is the
  only one where either item reaches the floor.
- **The remaining honest negatives are stated flatly.** The write is a faithful
  transport of the canonical packet impulse rather than a new drive mechanism, and
  the receipt makes no claim that it writes anything the existing route could not.
  The declared input realization is left exactly as the diagnosis measured it and
  remains inert. The read is a prediction rather than evidence, and the receipt
  states in one line what the other declaration would change — declared as
  evidence, the same read would have to enter the evidence store through the
  owner's own observation-admission rule, moving the evidence clock and with it
  the checkpoint generation, and turning the recovered deposit into an admitted
  observation about the world instead of a prediction of the page — and leaves
  that choice open rather than taking it. One frozen statement is now superseded
  and deliberately untouched: the durability receipt's `owner_probe` still records
  `packet_impulse_transition_available` false and
  `prepared_query_addressed_written_packet` false, with the reason that "the owner
  transition surface exposes no packet-impulse operation (advance accepts ticks
  and source_enabled only)", which this additive transition supersedes rather than
  repairs because that receipt is frozen evidence.
- **Collateral audit.** Outside this receipt, the edit's own collateral was
  audited, and the receipt declares where that audit lives without restating it:
  its `closure_audit` block names `_diag/owner-write-path/closure/`, whose
  `r2-verdict.json` is the closure summary and whose `closure-tests-per-file-r2.json`,
  `r2-summary.json`, `importer-closure-r2.json`, `r2-controls.json` and `r2/`
  carry the per-file test rows, the classified per-harness archive comparison, the
  import closure, the attribution controls and the harness captures those
  comparisons read. From those artifacts: a per-file test closure over `25` files
  (`25` passed, `0` failures, `440` tests and `29` subtests, `1543.8` s wall, with
  this harness's own file at `18 passed in 61.74s`); an import closure of the two
  edited modules reporting `57` affected artefacts out of `376` scanned, with no
  added or removed path and the same affected-artefact set as the previous round;
  and a re-run of sixteen harnesses in which four outputs are byte-identical to
  their archived copies — including this record's own feedback receipt
  (`8ebe4ca937776c00ad03785bbbe76403ee717422943026135e692c243c788026`) — and six
  are equal modulo timing keys. The audit also surfaced three standing
  pre-existing defects that this work neither causes nor repairs:
  `run_temporal_field_scenario.py` exits `1` in both rounds on its own control
  (`RuntimeError: working-state intervention did not change the matched-input
  prediction` at line `298`) and writes no report;
  `run_general_intelligence_program.py` times out at its default configuration, so
  only its test file is in the closure; and `run_packet_trace_check.py` is
  unreproducible while `_diag/selection-arms` has concurrent writers,
  differing only in `selection_arms` and `summary` and only by whether the
  baseline arm home was readable at read time.

The receipt's own bound is "Canonical-field numerical measurements in controlled
conditions only", and it records that the measured neutral gain "is an operating
point of the declared loop, horizon and readout on this profile, not a stability
threshold of the field's dynamics" and that the measured recovery fractions are
"properties of the declared readout, not of any consumer". Nothing here
demonstrates task-level memory utility, semantic content, retrieval by a
consumer, a distribution of outcomes over profiles or items, owner-level capacity
beyond the declared limits, or any advantage over alternative architectures. The
read half is a prediction of the canonical page under the write's own declared
direction, not an observation: it recovers what a write deposited and says nothing
about the world beyond the page it reads.

### Consumer path

One declared consumer on the owner's canonical page. One declared profile, the
metric harness's flat-inertia member `ladder-uniform`, held by the closed loop at
this profile's own measured neutral gain — `0.02734375`, bracketed
`[0.026562500000000003, 0.028125]` from the feedback harness's own refinement —
for `16` ticks at even horizon parity; one declared write and act budget of
`0.001` in every arm; the durability harness's read frame and its captured unit
directions; and three declared candidate directions — the target `root-scale`,
the fallback `left-detail` and the mismatch item `root-detail` — each captured
through the canonical packet impulse at that budget and measured pairwise
orthogonal in the read frame, with a greatest off-diagonal squared cosine of
`2.3960702554047607e-33` against a declared allowance of `1e-12`
(`_diag/memory-consumer-path/exploration.json`, `receipt_digest`
`3933e8ecc0aeedd1a9722c0bd282006d5217b516b3acf504133e973cb48b5f07`). The
receipt's `question` is whether reading the field's memory changes what a
consumer does, and whether that change is attributable to the retrieved content
rather than to the write's side effects on the field. The reading taken is the
minimal one: the consumer retrieves a declared direction through the owner's own
`read_packet_deposit`, compares the recovered deposit against a declared floor of
half the freshly captured deposit (`0.002511834142857143` against
`0.005023668285714286`), and performs exactly one owner write of the selected
declared direction — the remembered direction `root-scale` or the declared
fallback `left-detail` — at the declared budget, under a declared deterministic
policy that pursues the target if the retrieval reaches the floor and the
fallback otherwise.

- **The statistic is a field observable of the act rather than a restatement of
  the read.** It is the share of the act's own read-frame increment lying along
  each declared candidate, `dot(dframe, u_target)**2 / dot(dframe, dframe)`, with
  `dframe` taken between the frames before and after the consumer's act and `u`
  each captured unit direction. The act's budget is one declared value in every
  arm and every arm deposited something positive, so a zero share is a measured
  zero rather than an undefined ratio.
- **Memory used: the retrieval reaches the floor and the consumer pursues the
  target.** The target direction's deposit reads `0.005023718074326502` against
  the floor `0.002511834142857143`; the act's increment is
  `0.0008619191717734538` and its share along the target is `1.0`, against
  `3.0115911998889716e-64` along the fallback and `5.027550745802709e-31` along
  the mismatch item. Against the declared separation margin `0.5`, the memory arm
  beats every control by `1.0`.
- **Identity control: the field carries the target and the behaviour does not
  follow it.** The same write and the same hold on a page byte-identical to the
  memory arm's on arrival (`ad837e842348765037266bed195624c42bd2c43754df1f164a9d357a8d9e86c0`
  in both), with the consumer's read suppressed — the declared zero, no read call
  — leaves the consumer with `0.0`, short of the floor, so it pursues the
  fallback. Its share along the target is `3.229441440156545e-66` while the
  runner's own instrument read, taken on that same page and not passed to the
  consumer, recovers `0.005023718074326502`. The act still deposits
  `0.0050236012961321465`.
- **No memory: a measured zero.** Nothing is written and the declared horizon is
  advanced on a blank page with no drive. The retrieval returns `0.0`, the
  consumer pursues the fallback, and the share along the target is `0.0` against
  an act increment of `0.0050236682857142875`.
- **Mismatch control: the same mechanism writes a different item.** A different
  declared item, `root-detail`, is written and held by the same mechanism at the
  same budget. The target's retrieval then reads `4.1217363503130554e-13` — nearly
  ten orders below the declared floor — the consumer pursues the fallback, and the
  share along the target is `2.906568712007306e-65` against an act increment of
  `0.005023477863702145`. This is what separates an effect of the retrieved
  content from an effect of writing at all.
- **The predicate fires.** The no-memory field episode with the consumer's policy
  mutated to ignore the retrieval and pursue the target unconditionally returns a
  share along the target of `1.0` while its retrieval is `0.0`, so the predicate
  the memory arm satisfies is exercised on the same statistic and the controls'
  zeroes are not vacuous; the unmutated no-memory arm does not fire.
- **The gain is measured afresh here and is neutral on each page this receipt
  holds.** The refinement reproduces the owner write path receipt's own
  `0.02734375`, and the loop is judged neutral on the target's page at
  `1.0001475187841866` against `0.9119815524822384` with no drive, and on the
  mismatch item's page at `1.0001443993691275` against `0.9089294283996476`. The
  declared loop's tick body replayed from the same post-write page through the
  feedback harness's own `advance_workspace` and `apply_drive` reproduces the
  arm's held page at the horizon exactly.
- **The reads are declared predictions, and the invariance is live.** Every
  retrieval is a `temporal-prediction` with `evidence_added` false; no field
  episode and no consumer episode moves the evidence clock (`0` before and after
  in every arm), while the same published quantity moves `0 -> 1` under an
  admission through the owner's own observation rule on a separate state of this
  profile. The retrieval changes no page and no generation in any arm, and the
  held read returns the same readout when repeated.
- **Honest negatives.** Acting through the owner surface perturbs the memory it
  read: the owner's own read of the queried direction, taken immediately before
  and after the act, moves `0.005023718074326502 -> 0.01004738636004079`, doubling
  the target direction's deposit, and the receipt records that the owner's write
  path "is the only write actuator on the public surface", so no non-destructive
  actuator exists for this task on that surface — this negative is this receipt's
  own, and the memory store scale subsection below measures the non-destructive
  act on a coupled realization built from the page and driven outside the owner,
  where no operation writes back into it. The arms do not act with equal energy —
  `0.0008619191717734538` for the memory arm against `0.0050236012961321465`,
  `0.0050236682857142875`, `0.005023477863702145` and
  `0.005023668285714286` elsewhere — which is why the statistic is normalised by
  the increment's own energy and separates direction rather than effort. The held
  read is parity-conditioned: the declared loop's drive alternates sign every
  tick, the per-tick signed drive ratio is published for all `16` ticks
  (`1.00000495539176` at the horizon), the declared holds run at even horizon
  parity, and the written direction's relative difference `9.91080807587161e-06`
  sits inside the declared post-hold allowance `0.0001` while the unwritten
  direction's `0.9999999999555453` misses it. The task is narrow by declaration:
  one policy, three declared directions, one profile, one budget.

The receipt's own bounds are its four declared limitations: the task is "one
declared deterministic policy over one declared set of candidate directions on
one declared profile", so "nothing here measures a distribution over profiles,
items, budgets or policies"; the consumer's act is the owner's write path, which
"is the only write actuator on the public surface", so "an actuator with a
different physical law would be a different task"; the hold horizon is short by
declaration and "makes no claim about holding over a long horizon", which the
owner write path receipt measures at `512` ticks; and the statistic "measures
which direction the consumer actuated, not whether acting on a memory is useful
in any wider sense". The receipt leaves one choice open rather than taking it —
whether the read is declared as a prediction or as evidence — and records that
this demonstration does not need the choice taken, because the consumer's
decision uses the retrieved deposit as a number and admits nothing. Its own
regression file, `test_memory_consumer_path.py`, carries `17` tests and passes.

### Owner surface options

Two declared options on one profile, the metric harness's flat-inertia member
`ladder-uniform`: an evidence reading of the written-direction read, and a
coupled input relation. Both are additive and default-off — the shipped read
stays the prediction reading and the shipped declared input stays the identity
precision — and the receipt declares one written packet item, `root-scale`, at
one declared write budget of `0.001`, one declared observation channel (a
declared variable over the declared deposit range and one declared chart over
it), the transceiver's own declared loop settings, and one declared resolution
ladder for the overlap enumeration (the four topology names the library validates
times three ports-per-pool settings times both beta settings)
(`_diag/owner-surface-options/exploration.json`, `receipt_digest`
`a9a85f9b1e4a32b19c81e5476d94e78835c95739998b3f4b770d613d8ef7e455`). Its
`declared` block states that "Nothing here changes a default: both options are
measured off the shipped path", and its `recommendation` keeps the coupled
relation opt-in because "it is orthogonal in the field to the owner write path on
every amplitude of the declared sweep" while leaving the shipped prediction
reading as the default, because adopting the evidence reading "would buy an
evidence clock that nothing downstream reads yet".

- **The evidence reading moves an owner's own clocks, counts, digests and
  resources, and no decision input.** `read_packet_deposit(..., as_evidence=True)`
  declares the same recovered deposit as an observation about the world through
  the owner's own observation-admission rule. Of the `2649` leaves on the four
  declared surfaces diffed (`inspect`, `inspect_resonance`, `inspect_computers`,
  `inspect_transceivers`), it moves `29`: `13` clocks, `11` digests, `2` counts,
  `2` resources and `1` version, and `0` decision inputs. The owner publishes `44`
  declared dispatch operations, of which only `continue_inquiry` and `query` name
  a decision or an observation. Both readings recover the same deposit,
  `0.005023668285714286`; the evidence reading raises the read operation's
  published key paths from `2266` to `2301`, while the shipped prediction reading
  moves `0` leaves.
- **Neither reading moves the page.** The written page
  `8f7e287ad2215ace5fcceba01b95e578f7de1412a5663a68ee27a017fb77aca1` is unmoved
  under both, and the channel the admission needs exists before the measurement:
  its `contribution_count` is `0` at version `1` before and `1` at version `2`
  after.
- **The controls make the admission an admission rather than a call that always
  succeeds.** Replayed under the same operation identity it publishes no second
  successor, keeps the same event and source identities, and moves `0` of the
  `2649` leaves; declared again under a fresh identity the event identity differs
  while the derived source revision is reused and the store holds both events; and
  on an owner with no declared channel for the observed variable the admission
  rule refuses it with `FieldIntelligenceError: unknown variable: packet-deposit`.
- **The coupled input has real authority over the declared readout.** The
  authority measure is the absolute spread of the declared readout over the
  declared input scan `(0.0, 0.5, 1.75, 3.5)`, window-averaged over ticks
  `1, 2, 4, 8, 16`: `0.28078002525017076` for the coupled relation against `0.0`
  for the shipped one on the declared profile, and `0.28077967389372793` against
  `6.83694100295039e-21` on the declared beta-zero counterpart. Its persistence is
  measured too — driven once on the first tick at `4.0`, the readout runs
  `-0.008933586830295898` to `-0.07342087766095308` across eight ticks, against
  `0.0` at every tick for the shipped relation.
- **It nevertheless reproduces the owner write page at no amplitude of the
  declared sweep.** Over the eleven declared amplitudes from `-4.0` to `4.0` the
  set reporting page identity is empty, and the closest the coupled route comes is
  the undriven base state at amplitude `0.0`, `0.07087784058303614` from the write
  in state-vector distance. At the declared scan amplitude `3.5` the deposit's
  relative difference is `0.446635087902169` and the read frame differs by
  `2.8577330538035777`. Page, workspace state digest and read frame together carry
  that verdict, and the predicate can fire: the reconstruction control — the
  write's own state carried by the same library mapping — reports identity.
- **What the owner's write stamps beyond the field is exactly the ledger.** The
  write's own state carried through the same page mapping the route uses yields a
  page digest identical to the owner's real page
  (`8f7e287ad2215ace5fcceba01b95e578f7de1412a5663a68ee27a017fb77aca1`) while the
  workspace state digest differs, and the metadata fields that differ are exactly
  `ledger` and `state_sha256`. Page-level identity alone would therefore have
  reported a route identity that the state digest denies.
- **The coupled relation costs about six times the shipped one per tick.** Over
  the same declared `64`-tick window, `0.0010491578132132418` per tick against
  `0.00017769687565305503` — `5.9041995496964965` times the shipped per-tick work
  — and against one owner write of the declared item, whose median is
  `0.22603339998750016` over `3` repeats, the two sit at
  `0.004641605237417396` and `0.0007861531776404806`. Every figure here is wall
  clock on this machine and lives under the receipt's declared timing key.
- **The overlap refusal is enumerated rather than sampled.** Across the declared
  lattice of `24` profiles the library refuses the same two declared variables on
  one shared port `24/24` times, with the single message
  `ResonantNumericalError: inconsistent common-coordinate constraints`, and admits
  the distinct-port selection `24/24` times. The mechanism is identified in the
  source: the condenser builds one constraint row per declared value at the
  declared ports (`cassi_resonant_field.py:1055-1058`), so the second write
  replaces the first and the row loses an entry while its target keeps its value,
  and the boundary check `norm(constraints @ result - targets) > tolerance`
  (`cassi_resonant_field.py:1139-1143`) reports the inconsistency. The controls
  bound the cause: the same overlapping selection with a zero declared value is
  admitted `24/24`, so what is refused is a nonzero target on a row that lost its
  entry rather than the shared port alone, and a topology name outside the four
  the library validates is refused outright.
- **Honest negatives.** The shipped declared relation is inert on the declared
  profile — an absolute spread of exactly `0.0` — but it is not algebraically
  zero: on the declared beta-zero counterpart the same identity relation reads
  `1.1201241244351606e-22` at tick `1`, rising to `2.4930204339016798e-20` at tick
  `16`. Nor does the normalised relative spread separate the two relations: it
  reads `1.0` for the inert relation on that counterpart as well, because a
  proportional response through the origin normalises to `1.0` whatever its size,
  which is why the receipt carries the relative figure beside the absolute one and
  asks a reader to compare the absolute spread. Neither option is adopted here,
  and the receipt's `declaring_nothing` block records that the opt-in helpers are
  called only in the defining module, this runner and this runner's test file,
  with the coupling-zero kernel and the shipped condenser kernel the same object —
  `sha256`
  `2a62257e06522248efbbc410c647e8421e42b8a4d46dbb409d142e5b5740c66e` on both
  sides — over identical dimensions.

Its declared bound is "Canonical-field measurements in controlled conditions
only", and its four declared limitations scope the figures: the authority figures
are "the transceiver's declared input-scan convention ... not a physical claim
about the channel"; the route identity "is a statement about this item, this
profile and this mapper"; the overlap enumeration covers only its declared
lattice, and "the library could accept a topology name outside the four it
validates"; and the evidence reading's cost figures are "single-run wall clock on
this machine". Nothing here demonstrates task-level memory utility, semantic
content or any advantage over alternative architectures, and neither option is
adopted. Its own regression file, `test_owner_surface_options.py`, carries `22`
tests and passes.

### Owner nested cycle

The whole owned memory chain measured up to this point — write
(`write_packet_impulse`), the closed-loop hold at the field's measured neutral
gain, read (`read_packet_deposit`) and the consumer's act — runs on one body, the
metric harness's `ladder-uniform`: the canonical rail with a flat inverse-mass
projection. That body cannot separate *what the field is built from* from *how
heavy it is*. This receipt runs the same chain on a declared `2 x 2` factorial of
bodies and asks the receipt's own declared question: "does the owner's own memory
behave differently inside a nested scaffold than on the flat rail, and is any
difference carried by the structure or by the mass metric?"
(`_diag/owner-nested-cycle/exploration.layout-decoupled.json`, `receipt_digest`
`bd7a83d40f5013b6c9d71e5b0abb2fc0cd45f1e751122a1a6f6332a7993f736a` — the only
digest field it carries, taken over each arm's construction record, which names the
builder that built the arm and carries no source position; the frozen receipt these
measurements were first published under is kept beside it at
`_diag/owner-nested-cycle/exploration.json`, still recomputing its own
`909ec09da53fd0b6946dca2dc18ad71c481ffaa2d9bbc76846f18cf382bbe1aa`; "Determinism of
the receipts" below reads both). The rail factor is the canonical body's rail against the
geometry harness's declared arrangement `nested-core-shell`, entered through
`geometry.build_profile(geometry.arrangement_named(...))` inside the metric
harness's own builder, and the metric factor is the flat inverse-mass control
(`ladder-uniform`) against the field's real default ladder at ratio `1.3`
(`ladder-ratio-1.3`). Within one rail the two metric levels are replaced by that
rail's own flat vector and that rail's own ladder, so the metric factor is read
across two metrics on one body; across one metric level the two cells carry the
*same* inverse-mass vector on two rails, so the rail factor is a structural
difference alone. Each arm's hold runs at *that arm's* neutral gain, measured on
that arm's own field by the feedback harness's refinement, and no arm's gain is
taken from another arm or another receipt.

- **The rail separates nothing at owner level; the mass metric carries the
  store.** The greatest absolute rail effect over the six declared figures is
  `0.0024079538724970373` (on drift retention at the ladder metric level), under
  every declared margin, while the metric separates the written deposit by
  `0.23497047733555232` relative — `0.005023668285714286` on both rails at the
  flat metric against `0.0038432545506445243` on both rails at the ladder metric
  — the written direction's no-drive retention at the horizon, measured over the
  neutral-gain refinement's own `64` ticks, by
  `-0.6011762211167079` (`0.9119815524822384` and `0.9102664519192295` at the
  flat metric against `0.31149818467501866` and `0.3090902308025216` at the
  ladder metric), and the arm's own neutral gain by `0.020312499999999997`, all
  against a declared margin of `0.02`.
- **The neutral gain is rail-invariant.** `0.02734375` at the flat metric on both
  rails and `0.04765625` at the ladder metric on both rails: the rail effect is
  exactly `0.0` at either metric level, in both directions of reading. This is the
  same pair of gains the feedback, owner write path and consumer path receipts
  report, and it is the figure that decides what the hold does, so a nested
  scaffold changes nothing about the loop's own setting.
- **Three figures where neither factor separates, and one small-but-nonzero rail
  effect.** `recovery_fraction` reads `1.0000099108080758` and `1.0000096247683181`
  flat, `1.0127222556685962` and `1.012745604635565` ladder: a greatest metric
  effect of `0.012735979867246838` and a greatest rail effect of
  `2.334896696876143e-05`, both under the `0.02` margin, because the hold runs at
  each arm's own measured gain and the figure is near one in every cell by
  construction of the instrument. `hold_frame_energy_ratio` reads
  `1.0000100338373779` and `1.0000098881260988` flat against `1.0128775402784498`
  and `1.0129009543007057` ladder, metric effect `0.012891066174606891` and rail
  effect `2.341402225591871e-05`. `act_share_along_target` is `1.0` in every cell
  with both effects exactly `0.0`. `written_deposit`, `neutral_gain` and
  `act_share_along_target` are the three figures whose rail effect is exactly
  `0.0`; the largest of the rail effects that are not exactly zero is drift
  retention's `-0.0024079538724970373` at the ladder metric, against
  `-0.0017151005630089422` at the flat one, an order of magnitude below the margin
  rather than absent.
- **The rails are different bodies and the metrics are not confounded.** The two
  rails' transport matrices differ by a relative Frobenius difference of
  `0.7162833917927574` (largest absolute entry difference
  `0.02599562175592876`) against a declared `1e-06` margin, while the two cells
  that share a metric level carry the same inverse-mass vector and the same
  transport, so neither factor is read through the other. The canonical rail is
  the field's own default body.
- **The reference legs carry the harness's signs but not its observable.** On the
  four non-factorial bodies the survival receipt's own decomposition, re-measured
  at the owner's store, reads a baseline of `0.31149818467501866` (canonical rail,
  default metric), a mass-only leg of `0.3405074383294046` (canonical rail, shell
  metric), a rail-only leg of `0.3090902308025216` (nested rail, default metric)
  and a compound scaffold of `0.3397384755436551` (nested rail, shell metric).
  The retention components are `0.029009253654385947` for the mass and
  `-0.0024079538724970373` for the rail against the survival receipt's
  `+0.25797616491469993` and `-0.002012515678662327` — the same signs on both
  components, the same call that the rail component does not reach the margin and
  the mass component does, and a mass component `8.89289217806871` times smaller,
  because the harness
  ranks multi-item survival under activity while this receipt measures one
  declared item's deposit and its no-drive retention through the owner's own
  operations. The legs carry no verdict of their own; the compound leg's own
  component is `0.028240290868636442` against a mass-plus-rail sum that differs by
  the interaction residual `0.0016389910867475321`.
- **The shipped owner-chain gain is reproduced exactly.** On the canonical-flat
  arm the refinement lands on `0.02734375` with the bracket
  `[0.026562500000000003, 0.028125]`, and the owner write path receipt's own
  `cycle.neutral_gain.measured_gain` is the same number with the same bracket: the
  measured difference is `0.0` for the gain and `0.0` for the drift retention
  beside it (`0.9119815524822384`), so this receipt's cycle runs the instrument
  the shipped chain ran rather than a lookalike.
- **The controls can fail, and the read is inert while the write is not.** With
  nothing written, all six arms fall back — share `0.0`, recovered deposit `0.0`,
  the declared fallback item selected. With the same write and the same hold but
  the retrieval declined, all six fall back too, with a share along the target of
  `3.229441440156545e-66` on the canonical-flat arm, `6.598282820579714e-65` on the
  canonical-ladder arm, `3.83376153420348e-32` and `2.537729131929811e-32` on the
  two nested cells, and `0.0` on the canonical-shell arm. Across all six arms the
  reads move nothing — page, workspace state, owner state and ledger all unmoved —
  while the act's write moves all four, and the further declared impulse applied in
  a scratch copy moves the page, the workspace state and the ledger, so the
  digest-equality predicates are not vacuously true. The declared candidates are
  distinct in the read frame: the greatest off-diagonal squared cosine is
  `2.3960702554047607e-33` against a declared `1e-12` allowance. A direction the
  arm did not write recovers `8.247535290728763e-11` of the written deposit on the
  canonical-flat arm and `9.448532734054032e-05` of it on the canonical-ladder arm,
  both under the declared ceiling of `0.5`. On the canonical-flat arm the same
  write held with no loop retains less than the held page —
  `0.002378840505081224` recovered against `0.005023718074326502`, at a horizon
  frame-energy ratio of `0.6769165389176107` — which is why the no-drive retention
  figure is read beside the held one rather than identified with it.
- **The owner's own inspection surface does not work on the nested rail.**
  `inspect_resonance` is available and matches the public `AtlasState` fields
  (`logical_tick`, `generation`, `state_sha256`) on all three canonical arms, and on
  all three nested arms it raises `FieldIntelligenceError: resonance inspection
  must be canonical JSON data`. The clocks in this receipt are therefore the public
  state fields that `inspect_resonance` wraps, with the equivalence measured where
  both work rather than assumed; and because the shipped consumer episode calls
  `inspect_resonance` twice, it runs on the canonical-flat arm only, where its held
  page digest, its written deposit `0.005023668285714286` and its recovery
  `1.0000099108080758` are identical to this runner's own cycle at a relative
  difference of `0.0`, and the nested arms' cycles run on this runner's route.
- **The gauge, the item and the horizon are declared.** One written item,
  `root-scale`, at a declared write budget of `0.001`, its capture
  `0.005023668285714286`; the hold horizon is the consumer path's declared `16`
  ticks with closed-loop drive accepted on every tick and none clipped; the act
  budget is `0.001`; the read floor is half the captured deposit. The cited lattice
  depth axis sits beside the factorial as the comparison one level up —
  `deepest_vs_shallowest_k4_difference` `2.7589668119928912e-05` against a
  saturation margin of `0.02`, i.e. flat, which is the harness-level statement this
  receipt's rail factor repeats one level down.

Its declared bounds are its five limitations, four of them quoted in the preamble
above: the rail factor is read at one nested arrangement only; the metric factor is
read at two declared ladder settings plus the survival harness's shell metric in the
reference legs, so that "no conclusion about metrics in general follows"; "the
figures are one declared item's"; the horizon "is the consumer-path runner's
declared 16 ticks, chosen there for a consumer demonstration rather than for a
lifetime measurement"; and the no-loop control "is measured at the declared hold
horizon and is a no-drive hold", so its separation from the held arm grows with the
horizon, which is why the compact test configuration runs it but does not judge it.
Nothing here
demonstrates task-level memory utility, semantic content, retrieval quality, or any
advantage over alternative architectures. Its own regression file,
`test_owner_nested_cycle.py`, carries `24` tests and passes.

### Memory store at scale

**The question and the grid are declared before anything runs.** The runner's own
docstring states the question it answers — "Does the store survive being used: the
non-destructive act, and a store under rounds." — and its declared grid:
"N = 8 declared items times R = 8 rounds = 64 measured cells, the full declared
grid; it fits the declared budget, so nothing was reduced"
(`part_b.matrix.grid_cells` `64`, `part_b.matrix.rounds` `8`). The receipt is
`_diag/memory-store-scale/exploration.json`; it asks
the same question in the same words (`question`) and carries one statistic for
both parts (`declared.statistic`). No library module was changed for it: all seven
of its `declared.declared_instruments` are pre-existing operations — the
durability harness's read frame and captures, the feedback harness's loop law and
gain, this family's own consumer path, the options receipt's realization kernel,
and the owner's own write, read and transceiver operations — so what is measured
is the shipped surface, not new code.

- **The act through the owner write is destructive, and its size is the item's own
  read.** A1 reads the written direction at `0.005023668285714286` before its act
  and `0.010047336571428577` after, a movement of `0.005023668285714291` — a factor
  of `2.000000000000001` on the read it acted on, and `0.5000000000000002` under
  the receipt's own relative-difference rule (`|after - before| / max`). The read
  is the owner's own `recovered_deposit` of the written direction, its
  `the_stored_memory_is_unchanged` is false, and the page moves. The act is one
  `write_packet_impulse` at the declared act budget `0.001`, applied
  `0.0009999999999999994` with impulse `0.029358562841211737` — so the destructive
  case is measured, not assumed, and the surface that carries it is the write path.
- **The act through the owner's own transceiver moves the readout and leaves the
  page alone.** A2 condenses the learned chart into the owner's own transceiver
  (full dimension `112`, `1` input, `1` output, `0` reduced, tangent `108`) and
  drives one `advance_transceiver` tick at the declared amplitude `1.75`. The
  published readout moves `0.0 -> 0.15330920422388622`. The page digest is
  identical before and after
  (`8f7e287ad2215ace5fcceba01b95e578f7de1412a5663a68ee27a017fb77aca1`), the
  workspace state digest is identical, the owner state and the owner ledger both
  move, and the generation advances by `1` while the logical tick does not. The
  stored memory's own read is `0.005023668285714286` on both sides, unchanged by
  `0.0` relative. The tick is a full nonlinear realization — `1` full step, `3`
  nonlinear iterations, `16` operator applications, error bound `0.0` — and the
  declared zero-stimulus comparison is readout `0.0` with movement `0.0` from the
  published value, so the movement above is the input's rather than the tick's own
  dynamics.
- **A non-destructive act exists, on a surface outside the owner's.** A3 drives the
  declared coupled input realization, built from the owner's own written page by
  the options receipt's `realization_kernel`, and the receipt declares that surface
  exactly: "outside the owner's surface: the realization carries the page's
  declared write problem and its own working state, and no owner operation is
  called to drive it". The readout moves `0.00042512371321049393 ->
  -0.0034833204837238702`, and not one of the four declared digests moves across
  the act: page, workspace state, owner state and owner ledger are byte-identical,
  the generation moves by `0`, and the stored memory's own read is unchanged by
  `0.0` relative. That is the finding the part was declared to look for, and what
  carries the movement is the declared relation rather than the input code path:
  the shipped identity realization runs the same act with the same kernel and
  coupling `0.0` / diagonal `1.0` against the coupled row's `1.0` / `2.0`, and its
  readout moves `-1.6263032587282567e-19` under a declared
  `authority_allowance` of `1e-12` while the coupled row's moves
  `-0.003908444196934364`.
- **The authority is measured across the declared input scan, over the declared
  window.** The receipt's declared authority measure is "the absolute spread of
  the declared readout over the declared input scan (0.0, 0.5, 1.75, 3.5)"; over
  the declared window of `1, 2, 4, 8, 16` ticks it reads
  `0.280780027009766` averaged for the coupled row against
  `4.228388472693467e-19` for the shipped one, with `input_has_authority` true at
  every one of the coupled row's five ticks and false at every one of the shipped
  row's. At one tick the coupled spread is `0.007816888452568472` — the `7.83e-3`
  the earlier diagnosis recorded for a coupled relation — and the shipped row's
  one-tick spread is `1.6263032587282567e-19`, its `1.63e-19`.
- **The drive's own state is orthogonal to the written direction.** The coupled
  act's state increment is `1.755624357774615` long and its share along the written
  direction is `0.0002731061337570777` of a state `1.7558837523981736` long, with
  the receipt's own flag `the_stored_page_is_not_the_drive_state` true; the shipped
  realization's share is `2.283264906735626e-06`. So the realization moves its own
  working state and answers its own input without the state it carries pointing
  along the item the page holds.
- **The same drive on an unwritten page moves the readout by the same amount.** C1
  runs A2's act on the blank page
  (`d915342299b266cf98862d66f8f6985a32f53907f627a54198dbf4e988bb11c2`, the page
  A2's own owner started from) and moves the readout `0.0 ->
  0.15330920422388622`, A2's figure to the last digit, while the stored memory's
  read is `0.0` on both sides. The declared reading is that the movement is a
  property of the act and not of the stored memory; the regression file holds the
  two movements equal at `1e-9` relative for exactly that reason.
- **The store holds eight declared items and is used for eight rounds.** The eight
  items are written one at a time through the owner write path at the declared
  write budget `0.001` — each deposit `0.005023668285714286` or within
  `3.4531011550062046e-15` relative of it — held for the declared even horizon of
  `2` ticks with the feedback harness's per-item phase-locked drive law at this
  profile's own measured neutral gain, and then queried and acted on for the
  declared rounds. The hold's own figures are `16` drive calls, applied work
  `1.529459370730804e-06` under the declared `loop_work_ceiling` of `0.001`, and a
  frame-energy ratio at the horizon of `0.9986630010733931`. The same tick body
  replayed through the feedback harness's own primitives from the same start page
  produces the same held page digest
  (`f14f7d6eea1b762f2dcf9067eac2e78615808b41a0152bdea759c32c6029c746` both ways),
  so the held store is the declared loop's own page and not this route's.
- **Every round retrieved its queried direction, above the floor, and acted on it.**
  The rounds select the eight declared names in order, one per round; in each, the
  queried item's own read clears the declared floor of half that item's measured
  deposit (`0.005018608771789603` against `0.002511834142857143` in round `0`), the
  selected item is the queried item, and the act lands along the queried direction
  with share `1.0`. The page moves in every round and the generation advances by
  `8` across the loop, so the reads are taken on a page the acts keep changing.
  Recovery against each item's own measured deposit runs `1.9983510429957114` to
  `1.9989928646485124` at the horizon — the destructive act's own doubling, not
  decay.
- **The gain is this path's own measurement rather than a borrowed number.** The
  receipt runs the feedback harness's neutral-gain refinement on this profile:
  `0.02734375` inside the bracket `[0.026562500000000003, 0.028125]` at tolerance
  `0.002`, with drift retention at the horizon `0.9119815524822384` against
  `1.0001475187841866` at the measured gain on the headline item's own page, and
  all eight `neutrality_probes` declaring the gain neutral on their own page. The
  refinement's cross-receipt reference records that the owner-write-path receipt
  carries the same `0.02734375` and reports whether the two concord
  (`the_refinement_reproduces_the_cited_gain` true) instead of importing it.
- **The items the consumer has not yet acted on do not drift.** The read matrix is
  taken before any act and after every round, so each item carries a read at each
  stage: over the `28` never-acted cells the greatest drift is
  `5.551115123125783e-16` against the declared `read_drift_allowance` of `0.05`,
  while the cells of the items already acted on sit at ratios like
  `2.001008150695691` and leave that band. The band is passed by the cells it is
  meant to pass and failed by the ones it is meant to fail.
- **The falsifying leakage measurement is the single-item block.** One fresh owner
  per declared item writes that item alone through the owner write path and reads
  every declared direction on the resulting page: the greatest off-diagonal read is
  `2.396070255404761e-33` against the declared leakage allowance `0.05`, the least
  diagonal recovery is `0.9999999999999978`, and the measured separation factor is
  `4.1735003293176426e+32` against the declared minimum `10.0`. On the blank page
  the greatest read is `0.0`, i.e. `0.0` of the mean deposit. The diagonal witness
  is what makes those zeros a measurement rather than a dead instrument — the same
  read path returns the full deposit when the item is present — and the held page's
  own cross-item cells, the other measure the declared statistic names, are
  reported beside them: each cell divides a held-page read of the queried direction
  by that item's own measured deposit, so the cells run `0.9983510429957079` to
  `0.9989928646485154` across the queried directions and agree across reading items
  because the deposits they divide by agree to `3.4531011550062046e-15` relative.
  That agreement is the ratio's denominator rather than the store's rank, and the
  store addressing rank receipt measures this same held store's map directly: at
  this state it is full rank `8/8` with all `56` item pairs separated at the
  predicted `1.0`, the least at `0.9999999999999991`, so the store carries every
  declared item. See "Store addressing rank" and
  `_diag/store-addressing-rank/exploration.json`.
- **The declared directions are distinct in the read frame, measured rather than
  assumed.** Each item is written through the canonical packet impulse into a fresh
  field and the squared cosine between every pair is measured: the on-diagonal
  figures are `1.0`, the greatest off-diagonal squared cosine is
  `2.3960702554047607e-33` against a declared orthogonality allowance of `1e-12`,
  and the receipt states why that matters — the consumer's retrieval of an
  unwritten declared direction "is a projection on a direction the page does not
  carry", so the arms' separation rests on the declared directions being distinct.
- **The identity control still separates after the rounds.** Two fresh owners take
  copies of the store's final page — byte-identical,
  `29865fc077dae32f916be47419fc217a3bd6722761d2ce8d90c030bc03a972b6` for both —
  and run the declared consumer policy with its retrieval and with the retrieval
  suppressed. The normal arm retrieves `0.010041631265254113` against the floor
  `0.0025118341428571416`, selects the queried item
  (`right-right-detail`), and lands with share `1.0`; the suppressed arm makes `0`
  read calls, retrieves `0.0`, selects a different item, and lands at share
  `3.7927478729611577e-31`. Its own instrument read is `0.010041631265254113` — the
  figure the normal arm retrieved — so the field still carries the item and what
  fails is the retrieval. The share difference is `1.0` against the declared
  separation margin `0.5`.
- **The read-back is declared where the quadrature term vanishes.** Each item's
  phase reference is measured on that item's own isolated drift, and the store's
  phase read-back is declared at `180.0` degrees over `40` ticks, where the
  quadrature coefficient is `1.2246467991473532e-16` — a half turn's sine — so the
  store's own read-back carries no quadrature component into the round figures.
- **Every verdict is the receipt's own, and every one holds.** Part A's `13`, part
  B's `11` and the reading block's `24` verdicts are all true. The falsifiers are
  declared beside them in the runner's own source: each part block builds an
  `honest_negatives` list of `(verdict, why it would be false)` pairs filtered by
  that verdict, so those lists are empty here precisely because nothing failed, and
  the reading block's `honest_negatives` is the concatenation of the two. What
  bounds the claim above is therefore the receipt's own four limitations and the
  reading below rather than a further receipt field.

**Honest negatives.** Four of them, and none is a failed predicate: each bounds
what the figures above may be read as claiming.

- **The acts are destructive by design.** An acted item's read sits at twice its
  held read — A1's `0.005023668285714286 -> 0.010047336571428577`, the queried
  recoveries `1.9983510429957114` to `1.9989928646485124` at the horizon — and
  repeated use keeps accumulating, the same item's ratio reading
  `2.001008150695691` after its first round. The store survives being used; it does
  not survive being written to, and the act is the only thing measured to move it.
- **The held-page cross-item cells separate no reading item, and that belongs to
  the ratio's denominator rather than to the store's rank.** The measure the
  declared statistic asks for reads `0.9983510429957079` to `0.9989928646485154`
  across the queried directions, and across reading items it agrees to
  `3.4531011550062046e-15` relative, because each cell divides the same held-page
  read by a deposit that is equal for every item. The store addressing rank receipt
  measures that same held state's item-to-deposit map as full rank `8/8`, with all
  `56` pairs separated at the predicted `1.0` — the least at
  `0.9999999999999991` — once each item is addressed at its own placement. So the
  limit is the recovery statistic's at this operating point, not the store's
  ability to carry or separate the items. The falsifying measurement for the
  single-item block is unchanged — `2.396070255404761e-33` greatest off-diagonal
  read against a `4.1735003293176426e+32` separation factor — and it is stated as
  such here and in the receipt.
- **The coupled realization's act writes nothing back into the page.** The
  non-destructive act exists on the surface that carries it: the realization moves
  its own declared readout and its own working state, and no operation writes that
  state into the page — this family's own transceiver receipt states that no such
  operation exists today. So this is not an owner-level "act without writing" — the
  owner's write path remains the only actuator that moves the owner's page, which is
  what makes A1's doubling a property of acting at all.
- **The identity control separates two policy arms and says nothing about
  usefulness.** Its `1.0` share difference is a direction measurement taken on two
  copies of one page.

**Non-vacuity.** Those zeros and passes are worth what their controls make them
worth. The shipped identity realization is the can-fail control for "the readout
moves with the input": the same act, the same kernel, the same input code path and
a relation with no coupling, and its authority spread sits at
`4.228388472693467e-19` under an allowance of `1e-12` while the coupled row sits at
`0.280780027009766`. The drift band is passed by the `28` never-acted cells
(`matrix.never_acted_cells`) and failed by the acted ones. The off-diagonal zeros
come from a read path that returns the full deposit on the diagonal of every
single-item page. The unwritten-page control reads `0.0` on all eight directions.
And the digest is held to the measurements rather than to the prose, in both
directions: the regression file mutates five figures and requires the digest to
change on each — A1's readout movement,
`matrix.greatest_never_acted_read_drift`, `leakage.greatest_off_diagonal_read`,
`identity_control.share_difference` and `A2`'s `owner_ledger_moved` flag — and it
mutates the clock leaves and the chained ledger digests and requires the digest to
stay where it is. Its own regression file, `test_memory_store_scale.py`, carries
`9` tests and passes. The receipt's digest is content-deterministic under the
runner's own declared strip rule, which strips the clock leaves and, by rule, the
values derived from them; "Determinism of the receipts" states the rule, the defect
it repairs and the runs that measure it.

### Store addressing rank

This harness asks the store-scale receipt's own crowded state the question that
receipt left open, and its rule was declared before the first run. The receipt
`_diag/store-addressing-rank/exploration.json` (`receipt_digest`
`59c22ecaabd1b952c370ea6d09f8fbddfd7231cf11ac44f64446e1b68c809510`) carries the
runner's own `question` — "inside a crowded store, is the item-to-deposit map
rank-deficient, and does item-dependent placement restore the rank a shared
placement cannot carry?" — with its statistic, discriminator, decision rule and
controls fixed in the module docstring of `run_store_addressing_rank.py` before the
first run. One branch's wording was amended after that run and before the receipt
reported here, and the runner's docstring records the amendment: part one's branch
was declared as "the store carries every item and only the readout is collapsed",
the receipt measures the deposit vector's own constancy separately and finds it
false at the crowded state, and the branch therefore now names the read/deposit
*cells* the store-scale receipt reported rather than a scalar collapse. The branch
structure, every threshold and every control are unchanged, and the originally
declared wording would have asserted a scalar collapse the measurement does not
support.

The statistic is the deposit map. `J[i][j]` is the finite difference of the read
taken at item `i`'s own declared placement with respect to a probe write at item
`j`'s placement, divided by the probe work, with one fresh owner per probe on one
page so that no probe accumulates; `J` is `N x N` over the declared items and its
singular values are the deposit-difference spectrum. The rank is the count of
singular values above `tol = max(FLOOR_FACTOR * sigma_1(J(a) - J(a/2)), EPS_FACTOR *
sigma_1(J))`, with `FLOOR_FACTOR` `10` and `EPS_FACTOR` `1e-9`, the first term being
the measured finite-difference floor from the two probe works and the second the
declared numerical floor relative to the map's own scale. The discriminator is the
mean-diagonal normalization `Jn = J / mean(diag(J))`: an orthogonal pair is
predicted at exactly `1.0`, a duplicated pair at exactly `0.0`, a pair counts as
distinguishable when its separation exceeds `CONTRAST_FLOOR` `1e-3`, and the
specific arm must reach `1 - LOSS_ALLOWANCE` of the prediction for the declared
rule to hold.

- **Part one: at the crowded held state the map is full rank, so the store carries
  every declared item.** The crowded state is the store-scale runner's own held
  store, reused through its own machinery — the held-page read row that receipt
  publishes is this receipt's deposit vector, figure for figure — and there the map
  is `8/8`: eight singular values running from `5.023668285714291` to
  `5.023668285714283`, the smallest against a tolerance of `5.0236682857142915e-9`, a
  factor of `999999999.9999983`. The tolerance is dominated by the declared
  relative numerical floor rather than by measurement: the measured
  finite-difference floor is `1.6665350392316694e-14`, four orders below the
  `5.0236682857142915e-9` scale term. All `56` item pairs separate at the predicted
  `1.0` — the least `0.9999999999999991`, the greatest `1.000000000000001` — against
  the `1e-3` floor. The one-item reference state built by the same machinery is
  `8/8` too (`999999999.9999979` times its own tolerance), so the receipt selects
  its own discriminating branch: the degeneracy is in the readout cells, not in the
  map.
- **The scalar deposit carries nearly no item identity at that state, and the
  receipt says so as a measurement rather than a verdict.** The deposit vector is
  not constant at its own tolerance — its relative spread is
  `0.0005816266141306933` against a difference tolerance of `5.016951579499063e-12`,
  eight orders above it — but a difference operator of rank `7` and a greatest first
  difference of `2.9179925604416734e-06` over a `0.005016951579499063` mean
  magnitude is a readout that varies little with the item. The receipt separates
  the two readings in its `measured_flags` block: the crowded and reference rank
  flags are true, the constancy flag is false, `the_verdict_is_a_store_limitation`
  is false and `the_verdict_locates_the_degeneracy_outside_the_map` is true.
- **Part two: item-specific placement is what carries the addressing.** Three arms
  read one written page (`acb934c7f3a4a8317891008b5b5d4c2f260cf7ddf11e67127dc86d3ad8f3b8ab`,
  the same page in all three by the receipt's own flag), the same items at the same
  state, differing only in placement. With every item addressed at its own declared
  placement the map is `8/8` and all `56` pairs separate, the least at
  `0.9999999999999994` against the required `0.95`. With every item addressed at one
  shared placement the map is `1/8` — one singular value `40.18934628571427`, then
  `1.922216826801949e-15`, `1.6022113819069652e-46`, `2.490821831911961e-78`,
  `1.9987841724007425e-110` and three zeros — no pair separates, the least and
  greatest item separations are both `0.0` of `56` measured pairs, and the arm's own
  flags record that its rows and its columns are identical. With the second item
  addressed at the first's placement the rank is `7/8`, exactly one below the item
  count, the duplicated pair `root-scale`/`root-detail` sits at exactly `0.0`, and
  `54` of `56` pairs still separate; that arm's smallest singular value is
  `4.733597928504714e-16`, which is `4.7112962672770034e-08` of its own
  `1.0047336571428568e-8` tolerance. So the placement, not the shared direction, is
  what the map's rank rests on, and one duplicated placement costs exactly one
  dimension.
- **The controls fire or hold on their own readings.** The rank reading can fall
  below `N`: the duplicate arm is the firing instance at `7/8`. A zero-work probe
  moves no read — all `8` probes on the specific arm are rejected with requested and
  applied work `0.0`, the page does not move, and the whole response matrix is
  identically `0.0` down to its singular values — so the finite difference is the
  probe's and not the bookkeeping's. Every declared placement reads `0.0` on a fresh
  unwritten page (`d915342299b266cf98862d66f8f6985a32f53907f627a54198dbf4e988bb11c2`)
  through the same read call the arms use. The finite-difference floor is measured on
  the arm carrying the page's own half-probe sweep (`1.5400590297645216e-14`) and
  reused as a declared value by the other arms, each still supplying its own scale
  term — the shared arm's tolerance is `4.018934628571427e-8` and the specific arm's
  is `5.023668285714288e-9` — so the floor is shared and the scale is not. All `8` of
  part two's declared predicates and all `9` of its `reading.verdicts` are true,
  `failing_predicates` is empty, and `item_specific_placement_restores_the_rank` is
  true.

**What it does not show.** The receipt's own four limitations and its `not_shown`
entry bound the claim above, and two of those bounds matter most for a reader who
wants to take the result further.

- **The shared arm's zero separation is structural, not dynamical.** With every item
  addressed at one placement the two reads are literally the same call, so that arm
  calibrates the addressing semantics and supplies the floor scale; it is not a
  measurement of a field collapse, and no reading of this receipt should treat its
  `1/8` as a physical failure of the store.
- **The placement carries the addressing; the scalar does not carry item identity.**
  At this state the scalar readout is nearly item-independent, and a fractal scaffold
  that wanted item identity in the scalar deposit rather than in the placement is not
  supported by this receipt.
- The crowded state is one declared operating point: the declared eight items, the
  declared write budget, a `2`-tick hold at the measured neutral gain and this
  profile. Nothing here is a distribution over densities, gates, budgets or
  profiles.
- The rank is a finite-difference reading of a deterministic map, so a deficiency
  below its tolerance — about `1e-9` of the map's own scale, or the measured
  `1.6665350392316694e-14` finite-difference floor, whichever is larger — would be
  invisible.
- The placement arms address one written page, so the store-scale hold's own
  doubling is exercised only at the crowded held state of part one and not inside
  the arms, and which dynamical property of the field any future collapse would
  track (density, gate value, local rate) is not measured here — it would only be an
  interesting question at an operating point where the map did lose rank, and this
  one does not.

Its own regression file, `test_store_addressing_rank.py`, carries `15` tests
covering both the compact three-item build and the canonical receipt, and passes.

### Store addressing capacity

This harness asks the rank receipt's own placed store the question that receipt
leaves open — how many items the addressing carries at all — and its rule was
declared before the first run. The receipt
`_diag/store-addressing-capacity/exploration.json` (`receipt_digest`
`a3278fd1ef046f31f65f142f8e9f7831663ad4c868bffc5e33d7a41c0d3d3574`) carries the
runner's own `question` — "how many items does the placement addressing carry, and
what does its ceiling track -- the field's own scale-tree depth, the write budget,
the hold, the page's own deposit, or nothing inside the swept range?" — with its
statistic, its discriminator, its ceiling definition, its four declared branches and
its controls fixed in the module docstring of `run_store_addressing_capacity.py`
before the first run. The sweep is measured in two declared blocks, each with its own
`4200` s budget, its own declared counts and its own digest under the store-scale
rule the rank receipt reuses:
`_diag/store-addressing-capacity/block-declared-profile.json` (`content_digest`
`57e319c56d678115f8e6aa5e08d598480c8f042fe9dbba9e5ee44b9eddb4041d`, `661.96` s) and
`_diag/store-addressing-capacity/block-higher-resolution.json` (`content_digest`
`14d04223b4a7b93a683bcda3e7eb45603afc456c9ee14ba13c5d9bc272efdd2b`, `290.25` s).

The statistic is the rank receipt's own deposit map taken at larger item counts.
`J[i][j]` is the finite difference of the read at item `i`'s own declared placement
with respect to a probe write at item `j`'s placement, divided by the probe work,
with one fresh owner per probe on the level's own held page; the rank counts the
singular values above
`tol = max(FLOOR_FACTOR * sigma_1(J(a) - J(a/2)), EPS_FACTOR * sigma_1(J))`; the
margin is `sigma_min / tol`; the discriminator is the same mean-diagonal
normalization `Jn = J / mean(diag(J))` with an orthogonal pair predicted at exactly
`1.0` and a pair distinguishable above the same `1e-3` floor. What is new is the item
family and the sweep. The declared family is the field's own scale tree read as
items — "root scale, root detail, then every node detail of the port-count dyadic
tree in its own breadth-first left-before-right order", with every single-port node
refused by the field's own rule and recorded rather than declared — so the delivered
eight-item list is the head of that family and the sweep extends it along the
hierarchy the field itself declares rather than inventing items outside it. The
declared axes are `N = 8, 16, 24, 28, 32` at the delivered profile
(`ports_per_pool = 4`) and `N = 32` at the doubled resolution
(`ports_per_pool = 8`); every level is measured on its own held page, held for the
rank receipt's own `2` ticks at the block's own measured captures, neutral gain and
phase references, with the hold's applied drive work `0.0` and the probe budget fixed
at `0.001` throughout.

- **The inventory is the port count at both measured resolutions, and the boundary
  is the rule's own first leaf.** The family is addressable to exactly the port count
  on the real surface: `28` addressable of `28` declared at `ports_per_pool = 4` and
  `56` of `56` at `ports_per_pool = 8`, over `55` and `111` dyadic nodes with `28` and
  `56` leaves, with `28` and `56` single-port candidates refused by the field's own
  rule, and with the same head matching the delivered item list entry for entry. The
  declared family is orthonormal at the measured floor — greatest absolute
  off-diagonal Gram entry `3.331e-16` at resolution 4 and `1.110e-15` at resolution 8
  — so the items are the field's own modes rather than constructed stand-ins. The
  boundary is measured, not inferred: at resolution 4 the path `LLLL` returns
  `FieldIntelligenceError: a leaf packet has no detail mode` and an eleven-level path
  returns `FieldIntelligenceError: packet path descends beyond a leaf`, and at
  resolution 8 the same two refusals appear at `LLLLL` and `LLLLLLLLLLLL`.
- **Every constructed level is full rank, inside its margin and fully separated.**
  At the delivered resolution the four levels that ran are `8/8`, `16/16`, `24/24`
  and `28/28`, with every item pair distinguishable — `56`, `240`, `552` and `756`
  pairs, all of them above the `1e-3` floor — and least separations
  `0.9999999999999991`, `0.9999999999999993`, `0.9999999999999993` and
  `0.9999999999999994` against the required `0.95`; their margins `sigma_min / tol`
  are `999999999.9999983`, `999999999.9999988`, `999999999.9999983` and
  `999999999.9999983`, with the smallest singular value in every case near
  `5.02366828571428` against a tolerance of `5.02366828571429e-9` dominated by the
  declared relative floor (the measured finite-difference floors are
  `1.6665350392316694e-14`, `1.5574820584570354e-14`, `2.0018801284106946e-14` and
  `2.4515019881406782e-14`). The doubled-resolution level is `32/32` with
  `992` of `992` pairs separated, least separation `0.9999999999999988`, margin
  `999999999.9999971`, and its own measured floor `2.63723168339969e-14` against the
  same `5.0236682857142915e-9` tolerance. The page's own deposit grows linearly with
  the item count — total energy `0.0401356126359925`, `0.08026354308553695`,
  `0.12039147456963299`, `0.14045544103804175` and `0.16051937563758753`, about
  `0.00502` per item at every level, the same per-item figure the rank receipt's
  crowded state reports — while its relative spread rises from
  `0.0005816266141306933` to `0.004413012998190166`, so the scalar deposit stays
  nearly item-independent as the store widens, exactly as the rank receipt's
  part one found at eight items. The levels' own runtimes are `66.6` s, `163.5` s,
  `182.5` s, `219.3` s and `265.6` s in the swept order.
- **The ceiling is structural, and it is the delivered family's own inventory.** The
  declared ceiling definition — the smallest declared `N` at which the level is not
  constructible, or the specific arm's rank is below `N`, or its margin is at or
  below `1`, or its least separation falls below `1 - LOSS_ALLOWANCE` — is met by
  exactly one declared count, and it is a refusal rather than a measurement:
  `N = 32` at resolution 4 is not constructible, "the declared family has no item at
  this count at this resolution: the family's addressable inventory is 28 items and
  its next candidate path is refused by the field's own rule", so the ceiling reads
  `{"kind": "structural", "n": 32}` with `dynamical_ceiling` null and no failing
  measured level for the correlated-readings block to name. The same count is
  constructible one resolution up, where the inventory is `56`, and the receipt
  records that as the discriminating control: the number that stops the sweep is the
  field's own addressable count at that resolution rather than anything about the
  store's dynamics at `28` items. The branch selected is
  `capacity-tracks-the-declared-scale-tree`, whose declared reading is that "the
  capacity is the count of the field's dyadic nodes at that resolution, which is its
  port count, so the delivered eight-item list is a declared stopping depth rather
  than a field limit"; the degradation fit is reported as not fitted, because the
  least separation is the same value at every measured level
  (`0.9999999999999988` at the smallest, `0.9999999999999994` at the largest) and a
  fit over equal values would be degenerate. All `11` of the receipt's declared
  verdicts are true and its `honest_negatives` list is empty.
- **The declared controls fire at every measured level.** The duplicate arm's rank is
  exactly one below the item count at every level (`7`, `15`, `23`, `27`, `31`) with
  its duplicated pair at exactly `0.0` separation; the shared arm is rank `1` and
  separates no pair; the zero-work probe is rejected and its greatest response is
  `0.0`; a fresh owner's blank page reads `0.0` through the same call the arms use;
  and each level's tolerance carries its own measured finite-difference floor, taken
  on that level's specific arm and reused by its other arms. What the controls do not
  do is vary: they are the rank receipt's declared operating semantics held fixed
  across the sweep, so a level that had failed would have failed against the same
  controls the delivered eight-item measurement uses.

**What it does not show.** The receipt's own five limitations and its `not_shown`
list bound the claim above, and the two that matter most for a reader who wants to
take the result further are these.

- **The capacity reading is about the field's own scale tree, not about placements in
  general.** The family is extended along the declared dyadic hierarchy only, so the
  measured ceiling is the count of that tree's addressable nodes at the resolution
  swept — the port count — and the receipt declines to read it as a statement about
  arbitrary packet placements: what sets the addressing capacity "beyond the measured
  count of its own scale-tree nodes" is listed among the things it does not show.
- **The measurement is one declared operating point, at a fixed probe amplitude, with
  a rank reading that has a floor.** One declared metric row at two resolutions, the
  delivered write budget, the delivered hold horizon and one probe amplitude are
  swept, so nothing here is a distribution over profiles, budgets, holds or
  amplitudes; the probe budget is fixed while each level's own page deposit grows
  with `N`, so a failure would have been a failure at this probe budget; the rank
  reading is a finite-difference reading whose floor is the level's own measured
  half-probe floor plus the declared relative floor, so a deficiency below that would
  be invisible; and a level that did not run is reported with its reason and is not
  evidence of a ceiling — no level was cut at either resolution in the receipt
  published here, and the unconstructible count is measured separately from the arms.
  Whether a hierarchical placement carrying several items per probe would reach past
  the port count is the second thing the receipt declines to show, because the
  delivered statistic addresses one item per probe.

Its own regression file, `test_store_addressing_capacity.py`, carries `13` tests
covering the declared rule against the delivered item list, the addressable count as
the port count at two measured resolutions, the install and restore of the extended list,
the field's own refusals at a leaf detail and beyond a leaf, every declared level
accounted for as run, cut or refused, each measured row's booleans against its own
numbers with all five controls firing, the refuted-reads of the structural boundary,
the ceiling branch against the published numbers, and the merged and per-block
digests, and passes in `5.0` s beside the rank file's `15` tests in `47.8` s.

### Store addressing tree

The scale-tree receipt asks the question the capacity receipt's inventory raises and
does not answer: the store declares more scale-tree nodes than it addresses, because
its own rule refuses a single-port node, so does the addressing act as a *tree* or is
it a flat list wearing a tree-shaped address space? Its runner's own `question` states
it, and the runner's docstring fixes the answer's shape before the first run.

The question is answered only at the **field-exposed surfaces** the store's own
interface returns, and the receipt declares each one before the first run rather than
assembling it afterwards. The write surface is
`owner.write_packet_impulse(operation_id, path=, component=, flow_signal=,
work_budget=)`; the read surface is `owner.read_packet_deposit(path=, component=,
flow_signal=)`, and the field's own readout is labelled `readout_kind:
"temporal-prediction"` with `evidence_added: False` — a field-exposed API readout, not
an admitted observation. **No figure in this receipt is an observation.** The
addressability authority is one function, `capacity.declared_family(port_count)
["specs"]` — the delivered eight-item list extended by its own rule: `root-scale`
(path `""`, component `scale`), `root-detail` (`""`, `detail`), then every *interior*
node's detail mode, with every single-port node recorded as refused ("a leaf packet
has no detail mode"). Applied to the address space it gives three classes, and the
receipt publishes them per surface rather than smoothing them over:

| class | which surface | addressable |
|---|---|---|
| `declared_item` | the root's **scale** mode (family item `0`), the root's **detail** mode (family item `1`), and every interior node's detail mode | yes |
| `field_exposed_undeclared` | a node's **scale** mode anywhere below the root, and a single-port node's scale mode, which is that one port | no |
| `beyond_leaf` | a path that descends past a leaf: not a node at all | no surface exists |

Two path-sensitive facts are published rather than flattened. The root's **scale**
mode is `declared_family_item: true` (family item `0`) while every other node's scale
mode is `false`; and the root's scale item is **not a parent** — it has no children —
so the level catalogue's root parent is addressed at the root's **detail** mode,
family item `1`. Addressability is measured, not assumed: the label pass *executes*
every path's detail and scale surface once and records the outcome beside the label,
so at four ports per pool the receipt holds `55` probed paths and at eight ports `111`,
with the field's own refusal text carried at every single-port path.

**The four readings, and what each one is taken at.** All four are constructions over
readouts — every one of them divides one readout difference by another — and each is
labelled `observed: false, constructed_from_readouts: true` in the receipt, with its
surface, its node class, its construction and its parameters published in
`declared.reading_surfaces` and repeated in its own row beside its numbers:

- **R1 containment** — the parent's **declared-item detail** surface, addressed by the
  parent's own path (the root parent's is `root-detail`), read after the children are
  deposited at *their* declared-item detail surfaces, divided by the parent's own
  response at its own surface. Declared items throughout; carries the branch.
- **R2 aggregation** — the same parent surface, read after the children are deposited
  **alone** at the delivered store write budget, with **two** published denominators:
  the mean of what each child's own surface reads when deposited alone at that budget
  (`fraction_of_the_childrens_own_deposit`, the value the per-level aggregate
  publishes) and the parent's own deposit at its own surface
  (`fraction_of_the_parents_own_deposit`). It is a magnitude reading, not a finite
  difference, and its floor is the declared numerical term alone. Declared items
  throughout; carries the branch.
- **R3 sibling** — one child's declared-item detail surface, read after a deposit at
  its sibling's, divided by the child's own response at its own surface, against the
  same measurement for two items that are not siblings. Declared items throughout;
  carries the branch.
- **R4 descent** — the child's declared-item detail surface, read after a deposit at
  its parent's declared-item detail surface, divided by the parent's own response,
  against a source that is not an ancestor. Declared items throughout; carries the
  branch.
- **R1s/R2s companion** — the containment and aggregation constructions moved to the
  *scale* surfaces: the field-exposed surface where the field's own packet analysis
  composes a node's summary from its children (`_packet_analyze`'s size-weighted sum).
  Its declared item status is **path-sensitive and not uniformly undeclared** — the
  root's scale surface is family item `0`, every other companion surface is
  field-exposed — so its `declared_item` is published as `null` with its own
  `declared_item_scope`, and the surfaces it touched are listed by name in
  `reading.companion_scale_surfaces.declared_items_among_these_surfaces`
  (`["<root>/scale"]`). It does **not** carry the branch.
- **R5 descendants** (supplementary) — the parent's declared-item detail surface, read
  after deposits two levels below it, at this level's grandchildren's own declared-item
  surfaces, with its own half-budget floor. Declared items throughout, but its
  *sources* differ between resolutions by construction, so it does not carry the branch
  and its cross-resolution comparison is reported separately rather than folded into the
  matched control.
- **port fallback** — a single-port node's scale surface, which is that port itself:
  the field executes it and `capacity.declared_family` does not address the node as an
  item, so it is `declared_family_item: false` with `node_class: single_port_node`. It
  does not carry the branch.

**The branch rule, and the third branch with equal standing.** The runner declares
four branches and tests all of them: `the_tree_is_structural`,
`the_tree_is_decorative`, `no_field_exposed_parent_surface_exists`, and
`inconclusive`. The third is *not* a failure and not an inconclusive — it is a finding
about the address space, and it is **tested** rather than asserted: the test is the
parent's own declared detail write and read *executed per parent*, and the branch can
only fire if the field refuses a parent's detail mode. The capacity inventory is what
made that branch a live possibility (at four ports per pool the field declares `28`
addressable nodes against `55` tree nodes, so a parent could have been a node with no
address), and the measurement is what settles it: **every parent's own detail surface
executed at every level of both resolutions** — `7/7`, `15/15`, `23/23`, `27/27` at
four ports per pool and `31/31` at eight — so the third branch was tested and did not
fire at any level. A child's detail refusal is a *per-reading* surface limitation, not
this branch: `run_store_addressing_tree.py` names the refusal, labels the port/scale
fallback beside it, and never reads it as the absence of a parent surface.

**Measured.** The runner's declared cost cap (`MEASURED_TRIPLE_CAP = 6`, head and tail
of the level's own order, with `PORT_FALLBACK_CAP = 2`) bounds each level, and each
level's wall time is published: `125.6` s, `291.4` s, `329.3` s and `303.2` s at four
ports per pool, and `304.4` s at eight, for two blocks of `1075.25` s and `422.92` s
inside declared budgets of `4200` s each. The readings, over the measured triples:

| level | complete triples | measured | containment | aggregation | sibling | descent | R5 descendants | companion scale | port fallback |
|---|---|---|---|---|---|---|---|---|---|
| `N=8`, res 4 | `3` | `3` | `0.0` at floor `3/3` | `0.0` | `0.0` | `6.906202310012417e-16` | `0.9965520484153771`, at floor `1/3` | `2.99854884730343` | `0/0` |
| `N=16`, res 4 | `7` | `6` | `5.179651732509319e-16` at floor `6/6` | `5.179651732509314e-16` | `0.0` | `5.179651732509318e-16` | `0.9954509293041962`, at floor `3/6` | `2.9983162139910395` | `0/0` |
| `N=24`, res 4 | `9` | `6` | `5.179651732509312e-16` at floor `6/6` | `5.179651732509318e-16` | `0.0` | `1.2085854042521727e-15` | `0.9954194705159002`, at floor `3/6` | `2.9982552422519797` | `2/2`, `2.3706605918015504` |
| `N=28`, res 4 | `11` | `6` | `5.179651732509316e-16` at floor `6/6` | `5.179651732509313e-16` | `0.0` | `1.2085854042521733e-15` | `0.9973539855883697`, at floor `3/6` | `2.998595509734637` | `2/2`, `2.3706578097823616` |
| `N=32`, res 8 | `15` | `6` | `8.632752887515531e-16` at floor `6/6` | `8.63275288751553e-16` | `0.0` | `3.45310115500621e-16` | `0.9936970481231202`, at floor `3/6` | `2.998253367170277` | `0/0` |

Every level returns **`the_tree_is_decorative`**: every declared-item-surface reading
is at its floor at every measured triple, `present` is `0` and `assignment_specific`
is `0` for all four, and all six controls pass — the zero-work probes are rejected and
move nothing, the duplicate and shared pairs match the single write, every arm moved
the page, and every blank page reads nothing. The shuffled control is what sharpens
it: the same contents attached to a parent they were not built from change nothing, so
the readings are not reading the node count either.

Three further results bound the claim in the other direction, and each is a published
honest negative rather than a footnote:

- **The companion at the scale surfaces is not at the floor under the declared rule,
  and the floor is what hides it.** The companion containment runs `2.9985...` to
  `2.9986` times its own positive control — reproducible to five digits across levels
  and resolutions — while its declared two-term floor, whose finite-difference term is
  the level's own half-budget difference, sits *above* the response: `present` is `0`
  and every measured row carries
  `a_nonzero_response_the_declared_floor_hides: true`. The deposit reading at the same
  surfaces has no finite-difference term and *is* present, which pins the effect to the
  probe arms rather than to the scale surfaces as such. The companion carries its own
  predicates and cannot decide the branch.
- **A refined first branch is not refuted, it is at the floor with it.** R5 reaches
  `0.9936970481231202` to `0.9973539855883697` of its positive control when its sources
  exist — but at the floor at `1/3` (`N=8`) and `3/6` at every other level, because of
  the same finite-difference term, so the supplementary reading neither carries the
  branch nor contradicts it.
- **The parent can lack a child surface while never lacking its own.** `16` placement
  patterns at the coarser resolution have a parent surface at every resolution while a
  child surface does not exist at one — the parent's own detail surface executes and
  the child is a single-port node whose detail the field refuses. That is the port
  fallback's territory, and it is recorded with the field's own refusal text, never
  read as the parent's absence.

**The shuffled control across resolutions.** The same placement patterns are measured
at both resolutions on a page held under *each resolution's own* profile: `5` patterns
are measured at both, `6` at one only, and `24` paths exist only at the higher
resolution. Every pattern measured at both gives the same kind of reading — at the
floor at both — for the four declared readings, which is the control's job: a reading
that survived only where a parent surface genuinely exists would be distinguishable
from an artifact of the node count or of the aggregation, and none does. The
supplementary R5 reading is compared **separately** for the same reason it is
supplementary: its sources are each resolution's own grandchildren, so at two
resolutions it places *different nodes*, and its difference there (at `L` and `R`) is a
difference of placement, not a reading that follows the node count. The receipt says
so in `supplementary_reading_scope` and lists the two patterns rather than letting the
mismatch pass as agreement.

**What this receipt does not show.** Its own limitations, in its own terms: it measures
one declared operating point — one probe budget, one hold, one delivered write budget,
one page per level held at the delivered captures — so nothing here is a distribution
over operating points; it measures at most six complete triples per level, so its
readings are stated over the measured triples only and the unmeasured ones are not
claimed; it reports the *address* structure and nothing about semantics, task utility,
retrieval quality or any advantage over alternative architectures; every figure is a
construction over the field's own API readouts and no figure is an observation; and the
floor rule was fixed before the first run and is **not** retuned afterwards, which is
why the companion's large fractions are published as floor-hidden rather than promoted
to present readings. Whether the tree carries meaning at a surface *neither* the store's
family nor the field's own composition exposes is the thing it cannot see: this
measurement reaches the surfaces the field returns, and it says nothing about a
hierarchy that would only appear at surfaces that do not exist.

Its own regression file, `test_store_addressing_tree.py`, carries `25` tests covering
the declared cap against the level's own order with every parent an interior node, the
field's own refusals at a leaf detail and beyond a leaf on the real surface, the
receipt's blocks and levels with their complete and measured counts, every published
reading recomputed from its own responses and floor terms, every per-level aggregate
against the count of its own rows, the published branch against the branch the declared
rule returns, the structural and third branches both reachable on perturbed real
records, the surface census as the third branch's tested evidence, each reading's own
declared surface with its node class and addressability re-derived from
`capacity.declared_family`, the probed address space labelled per surface with a firing
control on a mutated block, the companion's floor-hidden fractions with their declared
scope, the supplementary reading with its own floor and placements, the port fallback
against the field's own refusal text, the cross-resolution matched control with the
supplementary mismatch reported separately, and the merged and per-block digests, and
passes in `2.0` s.

### Scale composition surface

The tree receipt found the addressing flat: containment, aggregation, sibling and
descent all sit at their floor. It also left one non-zero reading with no
structural control -- a companion at the scale surfaces standing about three times
its own positive control (`fraction_of_the_positive_control` ~2.998 at every level)
that the spent receipt nonetheless published `at_the_floor`, because the binding
term of its declared rule was the `10 * |r(B) - r(B/2)|` half-budget difference and
not the magnitude. `run_scale_composition_surface.py` re-takes that geometry with
the controls it lacked and asks the one question the companion leaves open: is a
node's scale response to deposits at its children a **composition** -- a function
of *which* children were written -- or magnitude alone?

**The rule was worked out on paper before the first arm.** The spent receipt's own
two-term rule, `|v| > max(10 * |v - v_half|, 1e-9 * |own|)`, does not measure a
reading's size. A reading that scales with the drive has
`|v - v_half| = |v| / 2`, so the half-budget term becomes `5 * |v|` -- five times
the reading -- and the reading can *never* clear it; a reading that has stopped
moving between neighbouring budgets has that term at or below the numerical term
and is judged on the numerical term alone. The rule is a statement about the
reading's **shape**: asking whether the reading scales with the budget asks for
exactly the shape the rule rejects by construction, and the informative measurement
is a **budget sweep**. So every measured row now sweeps a declared ladder --
`0.25, 0.5, 1, 2, 4` times the level's own write budget, fixed before the first run
-- and publishes the whole sweep: the treatment, its own positive control, and both
floor terms **separately** rather than folded into a `max`, at every point.

**What the sweep found, at all three measured levels (N=8 and N=28 at resolution 4,
N=32 at resolution 8):**

| reading | shape | plateau | declared rule admits | binding term at every point |
| --- | --- | --- | --- | --- |
| children's **own scale** surfaces to the parent's scale (R-B) | `still_climbing_with_the_drive` | none on the declared ladder | 0 of 15 sweep points per level | `10 * \|v - v_half\|`, 0.0310-0.2066 |
| children's **declared detail** surfaces to the parent's scale (R-A) | `under_the_numerical_term` | none (the reading is silent) | 0 of 15 | `1e-9 * \|own\|` |

The scale reading rises at every declared point and never plateaus: at N=28's first
row it goes `0.00502 -> 0.00812 -> 0.01372 -> 0.02425 -> 0.04470` while its own
positive control goes `0.00126 -> 0.00251 -> 0.00502 -> 0.01005 -> 0.02009`. Its
magnitude is therefore a **budget artifact**, and the receipt says so in those
words; the declared rule rejects that shape by construction (0 of 15 points
admitted, the half-budget term binding at every one), which is a different statement
from the reading being absent. The declared-detail path is **silent**: at or below
`1e-9 * |own|` (1.26e-12 to 2.01e-11) at every declared point, and bounded by that
term. Neither path reaches a plateau above the numerical term, so no row of this
receipt is claimed as composition evidence *from its sweep*.

**What carries the branch is therefore not the magnitude.** The composition branch
at all three levels rests on two comparisons that do not scale with the drive: the
**structural separation** from the shuffled-parent control (0.0129-0.0151 at the
rows where the field's own same-depth choice exists -- 2 of 3 rows per level; at the
root the field's own helper falls back to a descendant and the control is *refused
and recorded* rather than fabricated) against a measured floor of 0.0050-0.0058, and
the **count test** at a constant total budget -- two children at the write budget
each versus one child at twice it, the same total work -- which separates at every
measured row. The companions stay scoped beside the branch: the field's own
size-weighted composition companion has no control at these levels, the descendants
reading has a non-ancestor control on 2 of 3 rows, and the port fallback on 2 of 2
port rows (0 of 0 at N=8, which has no ports).

**The spent receipt's companions, audited from the pinned artifact before the first
arm.** The receipt re-reads `_diag/store-addressing-tree/` at its declared digests
and publishes, per level and per companion, whether the arm exists (proven by a
published value, never by a key: `arms_finite` is `True` for an arm passed as
`None`) and where a zero is **vacuous** -- the companion's zero at every measured
level is computed from a reading whose input was zero, so those zeros say nothing
about the structural question and are not read as a magnitude verdict. The
companion's structural question is likewise recorded as *untested* at every level
of the spent receipt, which is why this runner exists.

**Scope.** Every figure is a construction over the field's own readouts
(`readout_kind: "temporal-prediction"`, `evidence_added: False`) and **none is an
observation**. The sweep is declared for the two scale-surface geometries; the
descendants, port, field-composition and delivered-aggregation companions state
that they carry no sweep of their own rather than borrowing one. The branch is a
statement about the scale surfaces this level measured, at the two measured
resolutions, on this store.

Its own regression file, `test_scale_composition_surface.py`, carries `13` tests
covering the shuffled control's refusal of the field's cross-depth fallback, the
non-ancestor control never an ancestor, a descendant or equal, the placement null
never a sibling pair or a parent's own children, a missing control voting nothing, a
sweep that plateaus above the numerical term classified as evidence with both floor
terms published separately and the multiple the declared rule starts admitting, a
sweep that scales with the drive classified as a budget artifact and rejected at
every point by the rule's own arithmetic, a silent sweep named as bounded rather
than absent, the composition branch requiring a measured sweep, a separation and the
count test, and the merged receipt scanned for the word the declared rule rejects,
and passes in `1.4` s.

Its merged receipt is `_diag/scale-composition-surface/exploration.json`
(`receipt_digest` `19c38e6435efd380893469c78ff619a432405f3f56c26b92ba758901b63a3627`) over the two blocks
(`declared-profile` `87684098d3e222f160c96b6ba0823755f32dac0d4a861b0fb63518d301a2d8d2`,
`higher-resolution` `2e16e6e07578c684b092e8a91f32c546e1add49fcfd6d561193bf9544859242a`); the merged
receipt carries the sweep table itself as `the_declared_budget_sweep`, the
per-level sweep shapes, the plateau (or the statement that the ladder never reached
one) and both floor terms beside every point.

### Frozen parent application into an LL child

`cassi_resonant_field.py` now exposes the bounded parent-register path through
`write_parent_registers`, `freeze_parent`, `read_frozen_parent`,
`apply_frozen_parent_to_child`, and `recompute_parent_summary_from_child`.
`run_fractal_parent_summary_application_exploration.py` captures one L/LL field
state, freezes the L register, advances once with the source disabled, and
applies the frozen L level-zero momentum (`values[2:4]`, common/counterflow)
through the native LL scale impulse. Its focused regression is
`test_fractal_parent_summary_application_exploration.py`.

The frozen receipt `_diag/fractal-parent-summary-application/exploration.json`
(`content_digest`
`6a5f428650a40172358fe180075df5552d92c4ca621eed11b753de26afeadc05`) reports
`PASS_FIELD_OWNED_FROZEN_PARENT_APPLICATION`. From the same source-off child
state, parent-on applies effective flow `[0.03331300192959163, 1.0]` and
`0.0005` work, while parent-off applies `[0.0, 1.0]`; the final child states
are distinct. The frozen L values survive both arms unchanged (norm `0.0`),
the LR sibling delta is `0.0`, source-off heartbeat work is `0.0`, and
zero-work application is an identity (the state digest is unchanged).

The receipt's attempted can-fail controls reject a stale parent source digest
(`frozen parent source digest is stale`), a tampered freeze identity
(`frozen parent identity digest mismatch`), and live parent recomputation
(`parent recompute is locked while a frozen parent is active`). Its declared
`field_only` is `true`, while `semantic_memory_claim` and `hierarchy_claim` are
`false`.

**Boundary.** This is field-level causal wiring for one declared L→LL relation:
the frozen L register changes the native LL application while the register stays
fixed. It is not semantic recall, a task-level memory result, or evidence of a
general hierarchy or cross-scale architecture.

### Live LL-detail feedback into an L parent

`run_fractal_bidirectional_recursive_memory_cell.py` measures the native live
LL-detail → L route: a current LL detail packet is analyzed and applied to the
L parent through the declared relation, without freezing or persisting the child
packet as a memory object. The receipt
`_diag/fractal-bidirectional-recursive-memory-cell/exploration.json`
(`content_digest`
`cfd96dd3423f75168c6138753debe15c2b421a166bd5ac2b4e33e41f3cb7561d`)
reports `PASS_FIELD_OWNED_LIVE_CHILD_DETAIL_TO_PARENT`. Parent-on changes the
parent summary by `0.03417819603225304`, while parent-off is `0`; the applied
work is `0.0005000000000000002` and the reported balance defect is `0`.

The receipt's controls cover zero-work identity, applied-work balance, stale
child source/packet/relation rejection, tampered-relation rejection, and the
frozen-parent lock. The owner checkpoint reload/replay control replays the same
operation and preserves the same state. These are can-fail wiring and provenance
controls for the declared route.

**Boundary.** This is live current-field feedback from an LL detail into its L
parent. It is not retained child memory, semantic recall, or evidence of a
general hierarchy.

### Strict two-cycle active upward recurrence

The current strict receipt is `_diag/fractal-recursive-memory-cell/exploration.json`:
schema `cassifi.fractal-recursive-memory-cell.v2`, verdict
`PASS_FIELD_OWNED_CLOSED_TWO_CYCLE_ACTIVE_UPWARD_RECURRENCE`, and
`content_digest`
`5b254001650c8dce821a7a265ea4134ea5f223c8732b1a6a02ec3ddfcdb6ab28`.
It runs the causally matched cycle in `LL:detail` mode: frozen parent → child
application, release, live `LL:detail` → `L:scale` feedback, explicit parent-summary
recompute, refreeze, then a second frozen `LL:detail` application. The live upward
impulse is accepted with applied work `0.0005` and balance defect `0.0`.

The receipt records the register distinction explicitly. Before recompute, the
canonical L register remains equal to the register observed at the released child;
only the live field coordinates have received the upward impulse. The explicit
`recompute_parent_summary_from_child` call then materializes the updated parent
summary before refreezing. In the later-child contrast, full-loop versus
feedback-off deltas are field-state `0.023945903844438326`, effective-flow
`0.046296294312366`, and packet-state `0.010747066052609385`.

The source-off predecessor has `source_enabled: false` and positive heartbeat work
`0.0`; the matched sibling `LR` isolation quantity is `0.0`. The parent-off and
feedback-off arms remain controls for disabling the corresponding parent channels,
and stale source, packet, and relation digests on the upward route are rejected.

**Limitation.** This is a field-only, CPU/float64 causal-wiring result for the
declared L/LL route. It does not establish semantic memory, semantic retrieval,
embeddings, task utility, general hierarchy, or general cross-scale architecture.

### Bounded three-child active upward recurrence

The current bounded multicycle receipt is
`_diag/fractal-multicycle-recursive-memory-cell/exploration.json`:
schema `cassifi.fractal-multicycle-recursive-memory-cell.v1`, verdict
`PASS_FIELD_OWNED_BOUNDED_MULTICYCLE_UPWARD_RECURRENCE`, and
`content_digest`
`2286b85bdb599baaec552545c72d90b3f15c552fdbd3003ae2db56c4f3d467c3`. It
follows three bounded child routes — `D1/U1`, `D2/U2`, then `D3` terminal —
and releases the terminal child. The matched arms are feedback-on
`[on,on]` versus feedback-off `[off,off]`, with the parent enabled in both
arms. The later-child contrasts are field delta
`0.04336519945636155`, flow delta `0.027422444347092373`, and packet delta
`0.019405144059018598`; the persistence ratio is
`0.22825380024217662`, the selectivity ratio is `0.0`, and the source-off
heartbeat is `0.0`. Continuity work is `0.0005` for both the full and
parent-off arms.

The receipt's can-fail controls cover zero-work identity, zero-work downward
target identity, standalone upward zero-work identity, source-off heartbeat,
sibling isolation, immutable workspace round-trip, stale source rejection,
stale packet rejection, stale relation rejection, frozen-parent lock
rejection, persistence/selectivity mutation, and prior-receipt continuity.
The three-child route also requires nonzero downward target movement,
release/materialize/refreeze ordering, preservation of each nonterminal parent
register before materialization, and terminal release.

**Limitation.** This is field-level bounded recurrent causal wiring only: a
repeated `L↔LL` route. It does not establish semantic retrieval, embeddings,
task utility, or an `LLL` hierarchy. No geometry-superiority claim is made.

### Reading the twenty-three receipts together

The twenty-three receipts measure persistence, transfer, closure, disturbance response,
whether a written item survives a workspace round trip, how much of that survival
depends on which declared scaffold carries it and how far apart the items sit in
the declared scale hierarchy, which hooks actually move the body, which ports
reach which modes, how long a written direction lasts and why, which declared
metric best preserves it under bounded activity, what a declared lattice of
stations and rungs can and cannot move, whether a closed phase-inverted loop
can hold a written direction without spreading into the frame's other content,
whether the owner's own transition surface can accept a written impulse,
carry it across a restart and read a written direction's deposit back, whether
that deposit changes what a declared consumer does next, what a charged
reading of the read and a coupled input relation would each move, and which
factor the owner's own store follows once the body it runs on is varied by rail
and by metric, and whether a consumer can act through a surface the stored memory
does not feel while a store of eight declared items is used round after round, and
whether that crowded store's item-to-deposit map is rank-deficient once it is read
as a map rather than as a ratio — and if it is not, whether the placement of each
item is what carries the addressing, and how many items that addressing carries at
all: where the field's own declared family stops being constructible at one
declared resolution, and what fixes that number, and whether the address space is
a tree at its surfaces or a flat list under one, and whether the scale surface the
tree receipt left with a non-zero reading and no control composes from *which*
children were written or answers how much alone — measured as a declared budget
sweep rather than as a verdict at one drive.
Their common gap is narrower than "no memory" and is specific:
the written item outlives a workspace round trip and bounded activity, the
owner write path now carries it inside the owner's own checkpoint closure through
an exactly-once owner operation that survives a close and reopen, and the
consumer path now measures one declared consumer reading that deposit back and
acting on it — but the retrieval is a declared projection of the page under a
declared direction rather than anything semantic, and none measures a task. Mass metric and damping
control retention, and in the survival contrast the projected inverse-mass profile
carries the multi-item gain; graph geometry and topology, once the rail is
projected, mostly do not, though the rail is what carries the spacing separation.
Port placement reaches different modes in different arrangements, and no single
port is best everywhere. Survival after bounded activity is the one quantity
where the declared scaffold separates clearly, and it separates only once several
items share the body: four written items recover `0.3351631005750861` on
`nested-core-shell` against `0.0764836820747603` on the helix default, and the
attribution arms put `+0.25797616491469993` of that gain on the nested mass
profile against `-0.002012515678662327` on the nested rail, while a single
written item moves by `0.053526430107066814` or less. Spacing separates in the
same direction wherever the rail is projected — the near pair recovers
`0.051463903480489785` against the far pair's `0.37505473969085323` on the
default and `0.05193938203330472` against `0.36470194873327594` on `rail-only` —
and does not survive the mass-only arm, where the same pairs read
`0.3360889258416391` and `0.32837709392129527`; the declared off-diagonal figure
also carries a deposit-amplitude component that the no-activity arm exposes.
The ladder, metric and lattice receipts sharpen that gap from three directions.
Retention is largely a property of the metric rather than of the arrangement: a
declared hard
shell recovers `0.8442150578491289` where the canonical default recovers
`0.0764836820747603`, the same top profile generalizes to a second rail, and yet
the advantage inverts at the widest declared write set while the ranking survives
on the activity-preserving one. Lifetime is set by where the write's weight
concentrates among the modes rather than by the declared arrangement's width: the
coarse-to-fine ordering of the rung ladder is `mass-only`'s and not the body's, and
the linear predictor ranks the ladder while failing to pick the best write.
Structure is the direction that mostly does not pay: on the declared lattice the
phi spacing law misses its declared margin on station spacing, coupling and
inter-copy grading alike, the phi rung law's gain is shared by the steep ramps, the
depth axis is flat under the declared partitions, and the two attribution legs
interact instead of adding, while what does move is access coverage and the k2
survival arm.
The feedback receipt closes the loop and sharpens the gap differently. On the
default metric the phase grid's best arm is the `180`-degree one at gain `4`, at
alignment retention `19.60303769852896` against the drift baseline of
`0.31149818467501866` — a high-gain arm whose growth the receipt records as
decelerating but unbounded inside its declared horizon, distinct from the loop's
selected saturation setting at gain `16` — while a loop set to the
default profile's measured neutral gain `0.04765625` holds a single written item at
`1.1128929007050585` over `512` ticks. The gain that neither grows nor decays the
written mode is measured per field — `0.04765625` on the default metric and
`0.02734375` on the flat one, so the default's value does not transfer — and on the
flat profile at that gain a two-item frame's driven item holds `1.0488762323951002`
while the frame's other written item decays to `0.2427198345795942`, so what is
maintained is a driven direction rather than the profile. Read against its own
declared criterion, the loop's capacity is two items on the default metric and the
largest declared count, `8`, on the flat profile, because no declared scheme failed
there; and on the default the naive shared two-item drive is not among the schemes
that hold both, putting its second item below its own no-loop control. That is a
maintained direction under a measured work budget, not a durable store; what that
receipt does not measure is a consumer reading an item back, which the memory
consumer path measures separately.
The owner write path adds the transition the durability receipt could not measure,
and it changes the gap rather than closing it. The declared input realization is
measured exactly inert on that profile — the compact realization annihilates the
input's drive column before it reaches the state, and the full realization moves
the state exactly by the lift while the declared readout row stays exactly
orthogonal to it — so the write taken is the field's own canonical packet impulse,
and the owner-written page is measured to be the same page the existing aimed
narrow-path route writes, bit for bit. What that adds is ownership: one immutable
successor per operation identity, a refused conflicting call, a refused stale
predecessor stamp, the written pattern carried across a close and reopen, and a
read half that names a written direction and returns its deposit as a declared
temporal prediction moving neither the page nor either clock. The declared ports
own disjoint supports — all `378` pairs disjoint, `0` overlapping — so overlapping
selection is not available on this profile and the nearest one is refused by the
library, while the coupled-relation control fires with the same two disjoint
supports. The cycle holds the owner-written direction at this profile's own
`0.02734375`, against the default profile's `0.04765625`; what does not follow is
the two-item case, where every declared split beats its own control and no declared
split holds both items at the neutral floor.
The consumer path takes the retrieval question the earlier receipts leave open,
and answers it narrowly. A declared consumer retrieves the written direction
through the owner's own read operation — `0.005023718074326502` against a declared
floor of half the freshly captured deposit, `0.002511834142857143` — and its one
declared write lands along the remembered direction with share `1.0`, against
`0.0` with nothing written and against `3.229441440156545e-66` when the same write
and the same hold sit on a byte-identical page with the read suppressed, so the
behaviour follows the retrieved content rather than the field's side effects. The
mismatch control writes a different declared item through the same mechanism at
the same budget and the retrieval falls to `4.1217363503130554e-13` with the share
along the target at `2.906568712007306e-65`, while the mutated-policy leg restores
share `1.0` at retrieval `0.0`, so the controls' zeroes are measured rather than
vacuous. What that does not settle is what the act costs the memory: acting through
the owner surface doubles the target direction's own deposit,
`0.005023718074326502 -> 0.01004738636004079`, and the owner's write path is the
only write actuator on the public surface.
The owner surface options receipt measures the two ways this surface could be
extended and adopts neither. Declaring the read as evidence buys an admission that
moves `29` of the `2649` surface leaves — `13` clocks, `11` digests, `2` counts,
`2` resources and `1` version, and no decision input — while the written page stays
fixed and the shipped prediction reading moves nothing at all; declaring a coupled
input relation raises the declared readout's authority over the declared input scan
from `0.0` to a window-average `0.28078002525017076`, at `5.9041995496964965`
times the shipped relation's per-tick work, and still does not reproduce the owner
write page at any of the eleven declared amplitudes, whose closest member is the
undriven base state. The same receipt isolates what the owner's write stamps beyond
the field: the write's own state carried through the library's page mapping gives a
page digest identical to the owner's real page while the state digest differs, and
the fields that differ are the ledger and the state digest.
The nested cycle receipt moves the whole owner chain onto a varied body and finds
that the structural factor still does not pay. Writing, holding at each arm's own
measured gain, reading back and acting on a declared `2 x 2` of rails and metrics,
the greatest rail effect over its six figures is `0.0024079538724970373` against a
`0.02` margin, while the metric separates the written deposit by
`0.23497047733555232` relative and the written direction's no-drive retention by
`-0.6011762211167079` — so on the owner's own store it is once again the body's mass
that carries the item and not the scaffolding's shape, the same split the survival
receipt reports one level up with the same signs and a mass component
`8.89289217806871` times larger.
The neutral gain is invariant under the rail (`0.02734375` flat and `0.04765625`
ladder on both rails, rail effect exactly `0.0`), the canonical-flat arm reproduces
the shipped owner-chain gain with an absolute difference of `0.0`, and five of the
six figures carry a rail effect below `2.35e-05`; the figures that tie
entirely — `recovery_fraction` at `0.012735979867246838` and
`hold_frame_energy_ratio` at `0.012891066174606891` of metric effect — are the
honest negatives, and they tie because each hold runs at its own arm's gain. What
that receipt could not do is the other half of the same question: the owner's own
inspection surface raises `FieldIntelligenceError` on the nested rail, so the
nested arms' clocks come from the public state fields and the shipped consumer
episode runs on the canonical arm alone.
The store at scale receipt asks the two questions the consumer path leaves open —
whether an act can move a readout without moving the memory, and whether a store
of declared items survives being used — and answers both inside declared bounds.
The non-destructive act exists: driving the declared coupled input realization
moves its own readout `0.00042512371321049393 -> -0.0034833204837238702` while the
page, the workspace state, the owner state and the owner ledger stay
byte-identical and the stored read is unchanged, whereas the owner's write path
doubles the read it acts on (`0.005023668285714286 -> 0.010047336571428577`) and
the owner's own transceiver moves its readout `0.0 -> 0.15330920422388622` while
moving the owner state and the ledger and not the page. The same drive on an
unwritten page moves the readout by the transceiver's figure to the last digit, so
the movement is the act's and not the memory's; the shipped identity realization is
inert on the same act (`4.228388472693467e-19` against a `1e-12` allowance, where
the coupled row's window average is `0.280780027009766`), so the movement is the
declared relation's and not the input code path's; and the coupled act's own state
increment points `0.0002731061337570777` of itself along the written direction, so
it is not the owner's write in another guise. On the store half, eight declared
items are written and held, then retrieved and acted on for eight rounds: each
round's queried direction reads above its floor and is the item it acts on, the
never-acted cells drift by `5.551115123125783e-16` against a `0.05` band while the
acted ones leave it, the single-item pages leak `2.396070255404761e-33` across
items against a `4.1735003293176426e+32` separation factor, and the identity
control still separates on the final byte-identical page, `1.0` against
`3.7927478729611577e-31`, with the suppressed arm's own instrument read showing the
field still carries the item. What it does not show is an act that leaves the
owner's own page alone — the coupled surface is built outside the owner, and the
owner's write path remains its only actuator — nor a hold longer than the declared
horizon.
Nothing here shows a consumer retrieving the written item as anything but a
declared projection of the page under a declared direction, a declared scaffold
beating another on a task, or an act on the owner's own page that leaves it
untouched.

### Determinism of the receipts

All twenty-three receipts are content-deterministic for the source as it stands: their
cited digests are stable across independent re-runs, while the raw file hash is not,
because several harnesses record wall-clock fields. The definition is the lattice
runner's, which declares
"sha256 of the canonical JSON (sorted keys, no insignificant whitespace,
`allow_nan=False`) of the measured body with wall-clock fields stripped, before the
digest itself is attached"
(`run_fractal_lattice_exploration.py:4986-4990`) and applies it after the runtime
field is set (`run_fractal_lattice_exploration.py:4993-4998`); the stripped keys
are `elapsed_seconds`, `runtime_seconds`, `condensation_elapsed_seconds` and
`receipt_sha256` (`run_fractal_geometry_exploration.py:144-162`). The four
owner-side harnesses read their own declared sets rather than that constant, the
memory store scale receipt extends the set by rule rather than by list, and the
store addressing rank receipt reuses that extension — its strip keys are declared
as `run_memory_store_scale.STRIP_KEYS` and its digest is taken by that runner's own
helper — and the store addressing capacity receipt added here reuses it the same
way (`declared.content_digest_strip_keys_source`:
"`run_memory_store_scale.STRIP_KEYS`, reused rather than re-derived",
`run_store_addressing_capacity.py:1398-1400`); each of those is stated in its own
paragraph below. Nineteen of the twenty-three
carry at least one of those keys — geometry, ladder, lattice, live child-detail-to-parent,
memory consumer path, memory store scale, metric, owner nested cycle, owner surface
options, owner-write-path, placement, recursive memory cell, store addressing capacity,
store addressing rank, survival, frozen-parent application, and bounded multicycle
recurrence — so a re-run of one
of them changes the file hash without changing the digest; the memory consumer path
receipt declares that its measured body carries no inner wall-clock field, so its set
removes only the top-level `runtime_seconds`, and the owner surface options receipt
declares the same four keys with `receipt_digest` added and strips an
`elapsed_seconds` block that includes a per-selection `elapsed_seconds` inside its
overlap enumeration.
The owner nested cycle receipt is the one receipt here that used to bind its own
builders' source lines, and the change that removed that binding is worth recording
because of what the binding cost and what replaced it. Its definition is the same
lattice-runner rule with the same four stripped keys
(`run_owner_nested_cycle.py:203-206`), and its digested body excludes two keys by an
explicit declaration — `EXCLUDED_FROM_DIGEST = (DIGEST_FIELD, BUILDER_PROVENANCE_KEY)`
at `run_owner_nested_cycle.py:217-219`, read by `receipt_digest`
(`run_owner_nested_cycle.py:2613-2632`) rather than restated anywhere else, so what the
receipt declares is what it applies. The body it is taken over is, in the receipt's
current words, "the whole measured body with the wall-clock keys of the declared strip
set removed and the keys named in ``builder_provenance.excluded_from_the_digest``
excluded. The construction records name their builders (``built_by``,
``base_rail_builder``, ``declared_by``) and carry no source position, so the digest is
a function of the measurements and not of any file's layout: an edit above a builder
does not move it"
(`declared.receipt_digest.taken_over`, `run_owner_nested_cycle.py:2497-2509`).
The construction records are what changed underneath that sentence: each one names its
builders by `module.symbol` beside `declared_row`, `declared_row_index`, `declared_rule`
and `base_rail_arrangement`, and carries no source position at all
(`run_owner_nested_cycle.py:540-591`). The three fields the records no longer carry are
named as retired in the replacement block's own `replaces` list:
`declared.factorial.construction.<arm>.declared_at_line`, the same record's
`built_at_line` and `base_rail_builder_line`. What replaces them is a top-level
`builder_provenance` block, written at `run_owner_nested_cycle.py:2526` by
`builder_provenance_block` (`run_owner_nested_cycle.py:437-464`), which publishes the
normalisation it used, the hash it used, the excluded key list read from the same
constant the filter reads, the three replaced paths, and each builder's qualified symbol
mapped to a sha256 of its source region. The normalisation is stated so that a third
party can reproduce it: `inspect.getsource(builder)` — decorators, `def` line and the
whole body — with each line right-stripped, the region's trailing blank lines dropped,
the remainder dedented by its common leading whitespace, the lines joined with newlines
and hashed as UTF-8 (`run_owner_nested_cycle.py:227-232`). Per-line right-strip is what
makes the hash end-of-line insensitive, and the committed blob and the working file
produce identical builder hashes for every published builder.
The history is what makes the replacement worth having, so it stays. Under the retired
coupling the digest was a function of the runner file's layout as well as of its
content: a declaration comment block written as fourteen lines above `declared_row_for`
pushed that builder from line `418` to `432` in all four captured leaves and moved the
digest to `f2bc53fd4b0ce032d8aa84bc94f159aa1bd643012d71c0df73a1ef9b147a8a77`, with
every measured number identical, and compressing the block back restored both the layout
and the digest. That is a receipt bound to the live source lines of three different
files and moved by an unrelated comment block — the sensitivity this paragraph recorded
before the change, and the reason the option it then left open was taken. The decision
was to bind content instead of position, and it moved the frozen digest exactly once,
with the cost accounted leaf by leaf: `36` leaves removed (the three positional fields,
six arms, the two places each record appears — `arms.<arm>.cell` and
`declared.factorial.construction.<arm>`), `12` added, all of them inside the excluded
block (five builder hashes plus `definition`, `hash`, the two excluded keys and the
three `replaces` entries), and `3` changed (`declared.receipt_digest.taken_over`,
`receipt_digest`, `runtime_seconds`); nothing else differs between the frozen body and
the current one. The digest moved
`909ec09da53fd0b6946dca2dc18ad71c481ffaa2d9bbc76846f18cf382bbe1aa` →
`bd7a83d40f5013b6c9d71e5b0abb2fc0cd45f1e751122a1a6f6332a7993f736a`, reproduced by four
runs of the source as it stands with `runtime_seconds` the only leaf that varies between
them, and the current receipt is published beside the frozen one as
`_diag/owner-nested-cycle/exploration.layout-decoupled.json` (file sha256
`0e1089a07b5eb60ad80afc9b3d854cbbc1a38718d5c9bfc1315ba50fbed47f4c`). Because excluding
a key the body does not carry is a no-op, the frozen body still self-verifies under the
new rule — its digest is still `909ec09d…` — so the frozen receipt keeps recomputing
while the code moved on, and the prose frozen inside it that describes the retired
binding stays there as the record of why it was retired.
The new property is measured rather than declared, and both halves of it were measured
against the shipped source. The exact fourteen-line perturbation that used to produce
`f2bc53fd…` was re-applied above `declared_row_for`: the file hash moved
`9864992b864948b538ad5f2741f0b47654329a2cf0f0ae550e28fd7e0a719edd` →
`325a6b8a5be92263416d4ebe619ab4e95b7ac5e5159fddfa6beb506016ee0c14` and the builder's
line `494` → `508`, and the digest stayed `bd7a83d4…`; the revert restored the file
byte for byte. An eight-line comment block inserted above the metric runner's own builder
`metric.build_metric_profile` (`run_fractal_metric_exploration.py:1225` → `1233`) moved
that file's hash
`0f2fb722baf3eeef5521863faa50a3ddbacab626c02d0ed3f08b57a459a152a9` →
`f725c73b434c4c0a29a2b6069ea7c81200d907471543f93610c4de7ae9914109` and left the digest
and the published provenance block byte-identical. The other half is the mutation
control: a real statement inserted inside `declared_row_for` — in a scratch copy outside
the repository, never in the live runner — moved that builder's published hash
`153dd9493f6b7233e9cccd8431d134e5349a5b6d090ae1fcdb60015a7474e934` →
`fe0af7322354aa29bd9a1348a3b6a2bd4e5c741d6373832e2e2e570cdde43418` and no other
builder, while the digest stayed `bd7a83d4…` — so a layout edit is invisible to this
digest and a builder edit is visible in the block the receipt publishes beside it. Its
`24` tests pass in `55.67` s, and the three other receipts that share the convention —
owner surface options `a9a85f9b…`, owner write path `a1f5c4ff…`, memory consumer path
`3933e8ec…` — re-ran neutral: each still reproduces its frozen digest, and nothing in
the change imports or writes them.
One property of this receipt is unchanged and worth knowing before a release check leans
on it: `declared_by` sits inside the digested body, and the symbol it carries comes from
the module the function was loaded as (`qualified`, `run_owner_nested_cycle.py:467-471`),
so a receipt produced by running the script records this runner's own builder as
`__main__.declared_row_for` — as both shipped receipts do — while one produced by
importing the runner would record `run_owner_nested_cycle.declared_row_for` and digest
differently. Nothing here compares an imported build against a shipped one, so nothing
breaks today; a check that re-digests the shipped receipt from an import would see a
mismatch. Removing that asymmetry would move the digest again, so it is recorded as a
known property of the receipt rather than fixed here, and it is the same shape of
dependence the decoupling above removed — a digested field that tracks something outside
the measurement, there the runner's layout and here how the runner was loaded — one
field further in.
The memory consumer path receipt is the plainest case, and it is the one to compare
against: a docstring-only edit to its runner leaves its digest where it was, because its
digested body carries no source-line field. That was the contrast to the owner nested
cycle receipt above; after the decoupling the two stand on the same side — no receipt in
this family makes its digest a function of a source file's layout any more — so what a
reader still needs is which declared fields each body digests, because a digest is
evidence of "no change" only for the fields it covers.
The memory store scale receipt is the same case as the memory consumer
path one, on the other side of the owner: its digested body is the measurements
alone — `declared.content_digest_definition` is the lattice runner's own sentence
with this runner's rule spelled out, and it carries no construction or source-line
record — so no edit to its runner moves its digest unless a measured number moves.
Its rule is the family's rule extended by principle rather than by list: a key is
stripped when it is a declared wall-clock leaf and, by rule, when it is a value
derived from a stripped value — a chained manifest hash, a chained receipt hash, or a
digest computed over one — so derived-from-stripped values are stripped as a class
rather than listed case by case. The declared clock leaves are the family's four,
declared with their source ("`run_fractal_geometry_exploration.TIMING_KEYS` (the
clock leaves this family's receipts already declare, which include `receipt_sha256`,
a chained hash of a timed receipt) extended by this runner with the clock-derived
digests it publishes"), and the declared clock-derived digests are
`current_manifest_sha256`, `owner_ledger_sha256` and `parent_manifest_sha256`, each
with its own reason in `declared.content_digest_clock_derived_keys`.
That extension is what the chained clock requires, and this is the one receipt in
the family where the chain is real. Each of the four chained digests the receipt
carries — the owner ledger digests of `A2-owner-drive-act` and
`C1-drive-on-an-unwritten-page`, `before` and `after` their acts — is the runner's
own hash of the owner's event ids, active revision ids, event count and current
checkpoint manifest digest, and the manifest it hashes embeds its own transition
record, which carries that operation's `elapsed_seconds`; two builds of that arm in
one process, compared at their first published manifest, differ at exactly two
leaves — the nested
`transition.result.receipt.elapsed_seconds` and the `parent_manifest_sha256` that
chains the previous manifest into the next — while their event ids, active revision
ids, event count, page, workspace state and owner state are identical. A digest of a
timed receipt is therefore itself clock-derived, and it has to be stripped along with
the raw clock leaves, or the receipt's digest moves with the clock it strips; the
write arms' manifests, by contrast, carry no timing leaf at all, which is why `A1`'s
and `A3`'s ledger digests reproduce across builds and the two transceiver arms' do
not. What stays is declared too: every page, frame and state digest, which are content
addresses with no clock input, and the movement booleans the runner computes from the
stripped digests, so stripping the clock-derived digests removes no measurement of
what the surface did. The regression file holds both halves of that: it mutates the
ledger digests and the clock leaves and requires the digest to stay where it is, and
it mutates `A2`'s `owner_ledger_moved` flag and requires the digest to change.
Three full `8 x 8` runs of the source as it now stands measure its stability — the
frozen build at `64.26 s`, the harness's own second run, and an independent run made
for this document at `58.44 s` — and all three write
`d769cd297109d4885ee62a3256b649b5b0bb9504dd395daf8c1ee6a794ae2c77`. Between the
frozen build and that third run exactly seven leaves differ and every one of them is
a member of the declared strip set: the four chained ledger digests, the two nested
`elapsed_seconds` and `runtime_seconds`, with zero leaves differing outside the
set. The pre-fix build is kept beside the corrected receipt as
`_diag/memory-store-scale/exploration.pre-digest-strip.json` for a reader comparing
the two: every measured figure is byte-identical between them, and that body's own
`receipt_digest`, `fb0c967c45c9b8a345414fe1d297cccae3047a6431709be8a6971ae0739cfd3f`,
recomputes from it under the four-key set it declares.
The four owner-side harnesses each declare their own strip set and apply that
declaration rather than a shared constant, so what each receipt applies is structural
rather than a property of these bodies: a clock-derived value must be declared to
enter a digest and an undeclared one cannot. `run_owner_surface_options.py`
declares its set at `:137-141` and drops it in `strip_clock_leaves` at `:348`;
`run_owner_nested_cycle.py` declares at `:203-206` and drops at `:2625`;
`run_memory_consumer_path.py` declares at `:212-214` and drops at `:328`; and
`run_owner_write_path_exploration.py` declares at `:136-138` and drops at `:681`.
Each set is the family's four clock leaves with `CLOCK_DERIVED_KEYS` empty, plus, for
the owner surface options receipt, `receipt_digest` as a declared field of the set; the
owner nested cycle excludes two keys — the digest field and its `builder_provenance`
block, both named in its own `EXCLUDED_FROM_DIGEST` and filtered inside `receipt_digest`
rather than added to the strip set (`run_owner_nested_cycle.py:217-219`, `:2613-2632`)
— and the other two exclude the digest field where the digest is taken rather than in
the set (`run_memory_consumer_path.py:349` and
`run_owner_write_path_exploration.py:731`). The declarations are read rather than
duplicated for a reason worth keeping in view: a declaration that never fires is worse
than none, because it reads as a guarantee while enforcing nothing.
Each declaration is also what is applied — running each runner's own
`strip_clock_leaves` over a body carrying every declared key beside one control leaf
drops exactly the declared keys and leaves the control — and each receipt's digest
recomputes from its body under its own declared set. Three of the four digests are
unchanged from the frozen values and reproduce under two independent runs each, after
the change that gave the declarations liveness — the change that made each harness read
its own declaration instead of carrying a second copy — and with the source as it now
stands:
`a9a85f9b1e4a32b19c81e5476d94e78835c95739998b3f4b770d613d8ef7e455` for the owner
surface options, `3933e8ecc0aeedd1a9722c0bd282006d5217b516b3acf504133e973cb48b5f07`
for the memory consumer path and
`a1f5c4ffe42a9c25182cf25ec54ab2e5bff7ff51147e2d51d98a6234072e9f7c` for the owner
write path. The owner nested cycle's is the one that moved, once, to
`bd7a83d40f5013b6c9d71e5b0abb2fc0cd45f1e751122a1a6f6332a7993f736a` in the layout
decoupling its own paragraph above measures: it reproduces under four runs of the source
as it stands, and the frozen `909ec09d…` still recomputes from the frozen body under the
same rule, which is why that receipt is kept beside it rather than retired. Between the
two runs of each harness the only leaves that differ are leaves its declaration strips:
`59` inside the owner surface options receipt's
per-stage timing block, which the receipt carries under an `elapsed_seconds` key and
the rule drops whole, and `runtime_seconds` alone in each of the other three. So
determinism across these four is structural for the leaf clock class — a leaf in the
declared set is dropped by the rule whatever the body carries — while the chained
class is declared and not exercised in these four bodies: `CLOCK_DERIVED_KEYS` is
empty in all four by measurement of those bodies rather than by their exercise of the
rule, because the owner-side digests they carry — `ledger_sha256`, `owner_state_sha256`,
`page_sha256` and `workspace_state_sha256` — are content addresses with no clock
input. The body where the chain is real is the memory store scale receipt above, and
that is where the rule bites.
The store addressing capacity receipt is the second harness to reuse that declaration
after the rank receipt — `declared.content_digest_strip_keys` is the store-scale
runner's `STRIP_KEYS` and the
field beside it says so — and the control measured for it here is its own merge. Two
merges of the source as it stands, taken one after the other from the two shipped
block files, differ at exactly one leaf of the whole body, the top-level
`runtime_seconds` the declared set strips, and write
`a3278fd1ef046f31f65f142f8e9f7831663ad4c868bffc5e33d7a41c0d3d3574` twice, so its
digest is a function of the merged measurements rather than of the clock the merge ran
on; the same function strips the per-level runtimes nested inside the blocks' own
level records, so the levels' `runtime_seconds` leaves move no digest either. The
block receipts are the exception this family has to state rather than repair: the
higher-resolution block published here is a new shape — it carries the tail-level
fields (`tail_level_n`, `tail_level_constructible`, `tail_level_runtime_seconds`) its
earlier file did not — and the digest recorded for that earlier shape,
`e059ea0e0dbccecfa746f869768fcb8808889233102f6f63fdadf0c75395fa61`, does not
recompute from the current body with those three keys removed
(`4abdc0432527a2289d9c439441bb5c5ff0856eda4faadfa5b400e65a62e7d138`), while every
figure the earlier build's notes record does reproduce exactly: rank `32/32`, margin
`999999999.9999971`, least separation `0.9999999999999988`, `992` of `992` pairs, the
same smallest and largest singular values and the same `5.0236682857142915e-9`
tolerance, the same measured finite-difference floor `2.63723168339969e-14`, the same
deposit energy `0.16051937563758753`, the same depth census `{0: 2, 1: 2, 2: 4, 3: 8,
4: 16, 5: 24}` and the same two boundary refusals. What that leaves is an unexplained
difference between the retired file and the current body beyond the three added keys,
recorded here because the earlier file was overwritten by the re-run and no copy of it
survives to diff — so the current block and merged digests are the authority for this
receipt, and the retired value is quoted as the earlier build's own rather than as a
value this source reproduces.
The owner write path receipt is also the one that publishes the rule it applies: its
`content_digest_rule` block (`run_owner_write_path_exploration.py:688-713`) carries
the definition, both declared key classes, the strip set, the helper and the sentence
naming what the digest is computed over, and the digest excludes that block along with
the digest field (`run_owner_write_path_exploration.py:731`), so its body after the
change carries twelve more leaves than the frozen one — the rule's own keys — and the
same digest. That is the only channel in this family that publishes a rule without
moving a frozen digest: the owner surface options receipt publishes a
`digest_convention` block as well, but inside its digested body, where it was already
part of the frozen value.
The feedback receipt carries no wall-clock key at all, as the durability and
memory receipts also do not, so its file is reproducible byte for byte as well as
its digest. The Yang–Mills obligations receipt (`_diag/yang_mills_finite_obligations.json`) is
the same case from the other side: it carries a `wall_seconds` field that is not one
of the four keys above, and its stated digest covers the body with that field
removed, so it too is content-stable and not byte-stable. Independent re-runs from a
session that built none of these harnesses confirmed content equality for seven
receipts — the ladder, metric, lattice and feedback receipts, the Yang–Mills
obligations receipt (`_diag/yang_mills_finite_obligations.json`), the
compression-matrix receipt (`_diag/yang_mills_compression_matrix.json`) and the
owner write path receipt (`_diag/owner-write-path/exploration.json`) — and restored
the frozen copies of those files afterwards, which is why each live file and its
copy under `_diag/_repro_backup/` are equal byte for byte. Two of those re-runs
extended the evidence past content equality. An independent `--complete` build of
the compression matrix reproduced the in-receipt digest exactly
(`26da72f3bdbe52b47175e37368519e4465d33f66fecd77ea5b8162d7a7c0b1bc`) while the
two builds differed only in their wall clock, and that digest was recomputed from
the clock-stripped body of both files with the same result, so this receipt is
content-stable and not byte-stable and declares its own strip set inside its body.
An independent no-flag run of the owner write path reproduced its in-receipt digest
exactly
(`a1f5c4ffe42a9c25182cf25ec54ab2e5bff7ff51147e2d51d98a6234072e9f7c`) with exactly
one differing leaf, `runtime_seconds`, and zero non-timing differences; its `18`
tests pass. An independent re-run of the two receipts added here made the same
case for them: the memory consumer path runner reproduced its in-receipt digest
exactly (`3933e8ecc0aeedd1a9722c0bd282006d5217b516b3acf504133e973cb48b5f07`) with
`runtime_seconds` the only differing leaf, and the owner surface options runner
reproduced its own exactly
(`a9a85f9b1e4a32b19c81e5476d94e78835c95739998b3f4b770d613d8ef7e455`) with only
`elapsed_seconds` leaves differing, at the top level and one per overlap-enumeration
selection and nowhere else. Both re-runs wrote outside `_diag/`, so the frozen
receipts are unchanged; their `17` and `22` tests pass. The receipt added here is the
one the re-run check carries the most weight for in the other direction now, because
the property a re-run must not disturb is the digest's independence from the file:
four runs of the source as it stands reproduced
`bd7a83d40f5013b6c9d71e5b0abb2fc0cd45f1e751122a1a6f6332a7993f736a` exactly, with
`runtime_seconds` the only differing leaf across the whole body and zero non-timing
differences, and the two of them that re-ran after a layout perturbation had been
applied and reverted — the runner's own above `declared_row_for`, and the metric
runner's above `build_metric_profile` — are the control for the decoupling its own
paragraph above measures: the fourteen-line block that once moved this digest moved
nothing but the file hash and the report's idea of where the builder sits. The frozen
receipt reproduces its `909ec09da53fd0b6946dca2dc18ad71c481ffaa2d9bbc76846f18cf382bbe1aa`
from its own body under the same rule, and all four of those runs wrote outside
`_diag/`, so neither the frozen receipt nor its companion was touched by them. Its `24`
tests pass in `55.67` s.

## Where a direction could not be grounded

- **No field-level self-similarity exists.** `ResonantProfile.__post_init__` accepts exactly `{meaningful-helix, undivided, isolated, rewired}` and fixes `pools == 7`, so no arrangement can change the pool count or the minimum port resolution of four. Spatial spacing is inexpressible because `coordinates` has no hook, and `profile.edges` is ignored whenever `projected_transport` is set, so declared arrangements re-declare their structure and carry `topology` as metadata only. Nested, recursive, ladder, quasiperiodic, and sparse-link layouts are therefore reachable as declared pool graphs and were measured once by the geometry harness, but they measure strength and metric declarations, not physical self-similarity; the porous, hyperbolic, and second-center variants (A.5, A.6, A.8) additionally need descriptor support that does not exist.
- **No demonstrated durable pattern-storage mechanism exists.** `resonant_workspace` is persisted working state and §26.1 keeps learned memory, provisional work, and acknowledged outcomes distinct; the durability receipt writes one declared item into the canonical page and reads it back unchanged across a workspace round trip and records, for its own build, that the owner transition surface accepted no packet impulse and that its restart identity was workspace-level, while the owner write path now adds that transition — an exactly-once owner operation carrying the written pattern inside the owner's checkpoint closure across a close and reopen, with the generation, the logical tick and the evidence clock preserved — and still demonstrates no durable store: the consumer path now measures one declared consumer retrieving a written direction's deposit and acting on it, but as a declared projection of the page under a declared direction, and the memory store scale receipt now measures eight declared items holding and being used for eight declared rounds with every round's queried direction read above its floor and the items not yet acted on drifting by `5.551115123125783e-16` at most — a store that survives being used, with a hold that is "short by declaration, so this receipt makes no claim about holding eight items over a long horizon", and with every act on it destructive by design, so a durable store remains the program's central open item (G.1, `_diag/fractal-durability/exploration.json`, `_diag/owner-write-path/exploration.json`, `_diag/memory-consumer-path/exploration.json`, `_diag/memory-store-scale/exploration.json`).
- **No general multi-level scaffold has been measured at any depth.** Depth, branching, and cross-scale connections exist only inside the disposable packet basis (§26.18) or as nested resolution projections of one fixed body (§26.24), while the one frozen L→LL receipt measures a single field-level causal wiring path; neither is a many-level physical scaffold or proof of a general hierarchy.
- **No activity-driven structural change exists.** Change is explicit — condensation, layout transition, revision, revocation — and §26.1 forbids a per-pool Hebbian matrix or oscillator-weight learner, so H.4 must route through admitted evidence.
- **The exact-solver and theory analogies are analogies.** The width-two certificate, the `omega = 3` measurement, and the one-sided frame test concern cubic incidence matrices; the boundary-sector result concerns a lattice Yang–Mills transfer; J.4 and J.7 use them as shapes of argument, not inherited findings.

## Cue-conditioned field action (present state)

The task-grounded step is a synthetic field-coordinate controller, not a
semantic memory claim.  `run_cue_conditioned_field_action.py` writes declared
cue directions through field-owner write methods, reads the four candidates
through field-owner read methods, and emits one observable owner action per
selected cue.  Existing harness capture instrumentation supplies the coordinate
directions.  This scope is explicitly the field-owner read/write methods with
that existing instrumentation, not strict public-API-only isolation: the audit
found private helper and instrumentation imports (`arrangement._profile`,
`durability.capture_items`, and `consumer.frame`).  Nothing here establishes
semantic cue interpretation, language understanding, or task utility.

Measured-read selection ranks recovered deposits with direction-digest
tie-breaking.  It selects exactly two only if the second selected score clears
the named `SCORE_FLOOR = 1e-12` and the positive margin clears the separate
`SELECTION_MARGIN_FLOOR = 1e-12`.  Otherwise it abstains and records
`selected_cues=[]`, `selected_actions=[]`, `action_order=[]`, `acts=[]`,
`abstained=true`, and `action_count=0`; no owner action is attempted.  The
blank-no-memory and cue-read-suppressed controls require and verify those
zero-action fields.  Unconditional, wrong-mapping, and action-order controls
intentionally continue acting, preserving can-fail firing controls rather than
letting all-zero scores silently produce top-two actions.

The two training combinations recover exactly (`2/2`), and the held-out
two-cue combination under a new presentation order recovers exactly with
selection margin `0.0027042377351855105`.  The frozen receipt is
`_diag/cue-conditioned-field-action/exploration.json`, schema
`cassifi.cue-conditioned-field-action.v1`, digest
`373c963975ed58e434ff0d01d953c6756e95a3cf361755f9dbf2ba7aa1669844`.
The independent verifier imports neither the runner nor the audited field
implementation, rederives gated selection/action rows and both zero-action
control predicates from receipt rows, and passed `100` checks including
positive/negative firing anchors and the declared digest rule.  Reproduce with:

```powershell
python run_cue_conditioned_field_action.py --output _diag/cue-conditioned-field-action/exploration.json
python verify_cue_conditioned_field_action.py --receipt _diag/cue-conditioned-field-action/exploration.json
python -m pytest test_cue_conditioned_field_action.py -q
```

The result remains limited to controller behavior over the declared
field-coordinate protocol and this harness-instrumented owner path; broader
held-out generalization is unmeasured.

### Temporal/evidence action selection

This bounded probe uses the public temporal/evidence owner path
(`configure_temporal`, `learn_temporal`, `condense_temporal_skill`,
`bind_temporal`, read-only `select_temporal_action`, and
`advance_temporal`) rather than a fixed cue-to-action mapping.  The supported
arm selects `left-skill`/`left-step` with margin `0.035448902588912756` and
reaches expected observation `left-goal`; reversing presentation order leaves
the selected candidate and candidate-set digest unchanged.  Applying the
wrong action fails that expected goal, not merely the action-identity check.

Receipt:
`_diag/temporal-evidence-action-selection/exploration.json`,
`cassifi.temporal-evidence-action-selection.v1`,
`94efb7e88ca7c618b039daa7bc62a2df3225a64721e8fb6b67aa4c7d7354b9e1`.
The independent verifier and focused regression both pass.  The no-workspace
control is a true isolated lesion made after setup/learning by initializing a
fresh owner from `dataclasses.replace(learned_state,
resonant_workspace=None)`; both admissible operations then abstain with
`resonant-workspace-unavailable`, `field_setup.available=false`, and no
consequence.  Forbidden-operation and insufficient-margin controls remain
distinct abstentions.

The scope is one deterministic two-action controlled world and a
presentation permutation.  It does not establish open-vocabulary semantics,
broad planning, general world utility, workspace recovery, or persistence.

### Concurrent temporal/evidence action batch

The batch receipt
`_diag/temporal-evidence-action-batch/exploration.json` (schema
`cassifi.temporal-evidence-action-batch.v1`, digest
`289425f4dc6fb7d79c9915006a6bda76de47e6e24036d780e47603cae5c0c1ac`) records
11 canonically sorted independent cases executed by a bounded
`ProcessPoolExecutor`: 4 requested and 4 used workers, with completion and
per-case elapsed diagnostics excluded from the digest.  It measured the two
continuity rows, a three-candidate competition, one successful two-transition
multi-step case, an explicit unsupported held-out-composition case, an
order-permutation case, and no-workspace, insufficient-margin,
forbidden-operation, infeasible-operation, and wrong-consequence controls.
All controls fired; summary counts were rebuilt from rows by the independent
verifier.

The unsupported row trains only a singleton `bridge-step` primitive source and
records a held-out ordered two-step source whose digest is absent from all
training source digests.  The public temporal API requires a supported ordered
transition to occur contiguously in an admitted source; singleton primitives
therefore cannot compose this new transition.  Selection remains unresolved,
so this is an honest unsupported-capability result, not held-out
generalization.  The verifier independently decodes both source sets and has
mutation anchors for selected action, expected goal, held-out scope, case count,
worker concurrency, and a forbidden control.

Commands:

```powershell
python run_temporal_evidence_action_batch.py --output _diag/temporal-evidence-action-batch/exploration.json --workers 4
python verify_temporal_evidence_action_batch.py --receipt _diag/temporal-evidence-action-batch/exploration.json
python -m pytest test_temporal_evidence_action_batch.py -q
```

This is a bounded field-native categorical action-selection measurement over a
closed action/observation codec, with temporal reachability and deterministic
consequence only.  It does not establish open-vocabulary semantics, broad
planning, general world utility, or independent-distribution performance.

### Present-state boundary: ordered temporal composition

The canonical unsupported-capability receipt is
`_diag/temporal-composition-probe/receipt.json`, schema
`cassifi.temporal-composition-probe.v1`, content digest
`400e75f0135999d52170360bfc55ab72bc98e23195e94a6956bc3884109649f6`.  It
admits two singleton primitive sources independently into one temporal memory
and then exercises the exact public sequence
`configure_temporal -> learn_temporal -> condense_temporal_skill ->
bind_temporal -> compose_temporal_task -> propose_temporal_task ->
acknowledge_temporal_task`.  The first primitive is selected and acknowledged;
the second is unresolved at that post-transition state.  The denied-second
control also abstains, and source bytes prove that the held-out ordered pair is
absent from training.

The verdict is **UNSUPPORTED**: task syntax does not count as an unseen A→B
composition.  This result is scoped to the closed categorical codec and public
owner path; it does not establish general planning, open-vocabulary
recombination, or a successful unseen transition.  A supported result requires
B to be selected after A and the task to complete.  The exact API boundary is
that `compose_temporal_task` sequences existing skill bindings but does not
synthesize/transfer a skill policy at the preceding skill's destination.
Reproduce with:

```powershell
python run_temporal_composition_probe.py --output _diag/temporal-composition-probe/receipt.json
python verify_temporal_composition_probe.py --receipt _diag/temporal-composition-probe/receipt.json
python -m pytest test_temporal_composition_probe.py -q
```

### Present-state boundary: explicit materialized composition

The opt-in supported-composition receipt is
`_diag/temporal-materialized-composition/receipt.json`, schema
`cassifi.temporal-materialized-composition.v1`, content/receipt digest
`4584e905dc98565e7c1c218cd3d0b24b716ab6e336f0a3489e25cd7a860c3ac3`.
It retains the singleton A and B sources and proves from their decoded source
bytes that no A→B training edge was admitted.  After A is consumed, the
field-owned read-only proposal reports a derived hypothesis with no canonical
support; pre-commit B exposure is zero.  A separate explicit owner commit
validates the external B observation, materializes the proposed A-post→B edge
in the immutable TemporalField canonical planes, publishes changed field/memory
digests, and consumes B.

This is a distinct API path, not a fallback in `skill_action`,
`propose_temporal_task`, or `acknowledge_temporal_task`.  Mismatched,
ambiguous, unknown, stale, or replayed commits fail closed; the receipt includes
a mismatch control and the independent verifier checks that failed commits do
not mutate the prior field.  The supported claim is therefore limited to this
explicit closed-codec, externally observed, state-conditioned materialization
boundary.  It does not promote the derived proposal to training evidence and
does not claim general planning or external-world authority.

```powershell
python run_temporal_materialized_composition.py --output _diag/temporal-materialized-composition/receipt.json
python verify_temporal_materialized_composition.py _diag/temporal-materialized-composition/receipt.json
python -m pytest test_temporal_materialized_composition.py -q
```
