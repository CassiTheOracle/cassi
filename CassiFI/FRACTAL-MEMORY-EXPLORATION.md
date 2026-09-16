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

Ten runner/regression pairs, written by other sessions in this checkout, are
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
`test_fractal_feedback_exploration.py`, and `run_owner_write_path_exploration.py` /
`test_owner_write_path_exploration.py`. All ten runners exist and have been run
from this directory, and each writes a receipt that parses:

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
python -m pytest test_fractal_geometry_exploration.py test_fractal_memory_exploration.py test_fractal_durability_exploration.py test_fractal_placement_exploration.py test_fractal_survival_exploration.py test_fractal_ladder_exploration.py test_fractal_metric_exploration.py test_fractal_lattice_exploration.py test_fractal_feedback_exploration.py test_owner_write_path_exploration.py -q
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
**Status.** Depth exists only inside the packet view, which is a disposable view rather than stored state (§26.18).
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
**Status.** Nothing exists for the canonical field; nearest relations are the packet basis, where parent scale and detail are orthogonal combinations of child coefficients (§26.18), and the nested reduction (§26.24).
**Measured.** Nothing cross-scale was measured. All eleven arrangements vary pool-to-pool transport, and the receipt splits the rail into `intra_pool_strength_l1` and `cross_pool_strength_l1` with no separate upward or downward channel (`_diag/fractal-geometry/exploration.json`).
**First step (INFERENCE).** Declare parent and child regions and couple them by one upward and one downward edge, then test whether a child impulse reaches the parent scale without passing through every sibling.
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
**Status.** The strongest precedent: the packet hierarchy retains parent scale plus descendant details losslessly to roundoff, and §26.18 states dropping details does not preserve future dynamics in general.
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
**Status.** Partly addressed: §26.13 gives readout semantics without writing, §26.24 freezes readouts against unrelated heartbeats, and the viewer cannot feed pixels back; readout-induced perturbation of a wave-stored pattern is unmeasured.
**First step (INFERENCE).** Read one pattern `n` times and measure drift in it and in an unrelated pattern.
**Measures.** Drift versus `n` against the `2e-12` `ResonantProfile` tolerance and the declared roundoff allowance.
**Counts against.** Drift above tolerance, making repeated reads lossy.
**Run.** Bounded; the prepared-query path, which reads without another solve (§26.24), is the non-disturbing alternative.

### I.6 Evidence versus generated activity
**Status.** Enforced: §26.13 consumes external observations once, §32.3 admits telemetry for learning only with identity and dependencies in the field first, and §27.3 labels transceiver outputs `temporal-prediction` and adds no observed support.
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

All ten runners exist in this checkout and have been run. Their exact commands:

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
python -m pytest test_fractal_geometry_exploration.py test_fractal_memory_exploration.py test_fractal_durability_exploration.py test_fractal_placement_exploration.py test_fractal_survival_exploration.py test_fractal_ladder_exploration.py test_fractal_metric_exploration.py test_fractal_lattice_exploration.py test_fractal_feedback_exploration.py test_owner_write_path_exploration.py -q
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
`a1f5c4ffe42a9c25182cf25ec54ab2e5bff7ff51147e2d51d98a6234072e9f7c`) all exist
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
supersedes; that harness is frozen evidence and is deliberately left untouched."
Every figure
below is read from those ten files. All ten measure canonical-field numerical
proxies — geometric/access, modal-access, or the owner transition surface itself;
none measures memory utility
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

### Reading the ten receipts together

The ten receipts measure persistence, transfer, closure, disturbance response,
whether a written item survives a workspace round trip, how much of that survival
depends on which declared scaffold carries it and how far apart the items sit in
the declared scale hierarchy, which hooks actually move the body, which ports
reach which modes, how long a written direction lasts and why, which declared
metric best preserves it under bounded activity, what a declared lattice of
stations and rungs can and cannot move, whether a closed phase-inverted loop
can hold a written direction without spreading into the frame's other content,
and whether the owner's own transition surface can accept a written impulse,
carry it across a restart and read a written direction's deposit back.
Their common gap is narrower than "no memory" and is specific:
the written item outlives a workspace round trip and bounded activity, and the
owner write path now carries it inside the owner's own checkpoint closure through
an exactly-once owner operation that survives a close and reopen — but no receipt
retrieves it the way a consumer would, and none measures a task. Mass metric and damping
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
maintained direction under a measured work budget, not a durable store, and not
retrieval.
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
Nothing here shows a consumer retrieving the written item itself — the read half
returns its deposit, as a prediction — or a declared scaffold beating another on
a task.

### Determinism of the receipts

The ten receipts are content-deterministic: their cited digests are stable across
independent re-runs, while the raw file hash is not, because several harnesses
record wall-clock fields. The definition is the lattice runner's, which declares
"sha256 of the canonical JSON (sorted keys, no insignificant whitespace,
`allow_nan=False`) of the measured body with wall-clock fields stripped, before the
digest itself is attached"
(`run_fractal_lattice_exploration.py:4986-4990`) and applies it after the runtime
field is set (`run_fractal_lattice_exploration.py:4993-4998`); the stripped keys
are `elapsed_seconds`, `runtime_seconds`, `condensation_elapsed_seconds` and
`receipt_sha256` (`run_fractal_geometry_exploration.py:144-162`). Seven of the ten
carry at least one of those keys — geometry, ladder, lattice, metric,
owner-write-path, placement and survival — so a re-run of one of them changes the
file hash without changing the digest. The feedback receipt carries no wall-clock key at all, as the durability and
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
tests pass.

## Where a direction could not be grounded

- **No field-level self-similarity exists.** `ResonantProfile.__post_init__` accepts exactly `{meaningful-helix, undivided, isolated, rewired}` and fixes `pools == 7`, so no arrangement can change the pool count or the minimum port resolution of four. Spatial spacing is inexpressible because `coordinates` has no hook, and `profile.edges` is ignored whenever `projected_transport` is set, so declared arrangements re-declare their structure and carry `topology` as metadata only. Nested, recursive, ladder, quasiperiodic, and sparse-link layouts are therefore reachable as declared pool graphs and were measured once by the geometry harness, but they measure strength and metric declarations, not physical self-similarity; the porous, hyperbolic, and second-center variants (A.5, A.6, A.8) additionally need descriptor support that does not exist.
- **No demonstrated durable pattern-storage mechanism exists.** `resonant_workspace` is persisted working state and §26.1 keeps learned memory, provisional work, and acknowledged outcomes distinct; the durability receipt writes one declared item into the canonical page and reads it back unchanged across a workspace round trip and records, for its own build, that the owner transition surface accepted no packet impulse and that its restart identity was workspace-level, while the owner write path now adds that transition — an exactly-once owner operation carrying the written pattern inside the owner's checkpoint closure across a close and reopen, with the generation, the logical tick and the evidence clock preserved — and still demonstrates no consumer retrieval, so a durable store remains the program's central open item (G.1, `_diag/fractal-durability/exploration.json`, `_diag/owner-write-path/exploration.json`).
- **No multi-level scaffold has been measured at any depth.** Depth, branching, and cross-scale connections exist only inside the disposable packet basis (§26.18) or as nested resolution projections of one fixed body (§26.24), a different object from a many-level physical scaffold.
- **No activity-driven structural change exists.** Change is explicit — condensation, layout transition, revision, revocation — and §26.1 forbids a per-pool Hebbian matrix or oscillator-weight learner, so H.4 must route through admitted evidence.
- **The exact-solver and theory analogies are analogies.** The width-two certificate, the `omega = 3` measurement, and the one-sided frame test concern cubic incidence matrices; the boundary-sector result concerns a lattice Yang–Mills transfer; J.4 and J.7 use them as shapes of argument, not inherited findings.
