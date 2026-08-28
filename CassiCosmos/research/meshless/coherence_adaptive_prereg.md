# Coherence-gated adaptive compute — pre-registration (3 arms)

Date: 2026-08-17
Owner: Carina ("can we use coherence to optimize any of these algorithms?" → "Build all 3, please!")
Series: boxless_field design §8 (coherence-gated adaptive compute = the field-AI thesis applied to the solver's own cost)
Frozen before any engine/shader edit. Each arm is independent, default-off, additive, and MUST keep the battery bit-identical.

## 0. Why this is the thesis

Merge already prunes by q (`q > φ⁻²`). The general form: **the solver spends its
compute budget where the coherence is** — the same "intelligence as steering"
principle turned on the solver's own cost. Three arms, each independently tunable,
each gated default-OFF so the default battery is bit-identical by construction.

## 1. Arm 1 — coherence-filtered site search (true boxless *picture*, per-frame)

**Problem:** the boxless qhist reader (shipped `0f71503`) proves the site-direct
read is correct and envelope-independent, but the per-frame **instancer** display
(`tri_coherence`/`tri_phase`) still samples the wrapped grid — so the *picture* still
needs the envelope, and a naive per-frame nearest-site over 8192 sites per particle is
too expensive.

**Mechanism:** when `boxless_field` is ON, the instancer's coherence/phase at a
particle comes from the moving-Voronoi sites via a **coherence-filtered search** —
not a brute-force 8192 loop. On the steer cadence (every ML_REBUILD steps) a small
GPU pass reduces the sites to a **compact shortlist of coherent sites** (indices +
positions + psi_y/psi_i, for sites with q ≥ q_floor, e.g. q_floor = φ⁻² ≈ 0.382).
The per-particle instancer sample scans only that shortlist (the structured subset),
so the cost tracks the coherent content, not the mesh count.

**Root files:** `cassi_instancer.glsl` (site sample path, gated by `boxless_field`),
a new shortlist-building pass (reduction), `cassi_sim.gd`/engine wiring to bind the
sites + shortlist into the instancer uniform set.
**Gating:** `boxless_field` (already exported) AND the shortlist built only when it's on.
**Default:** OFF — instancer reads the grid exactly as today (bit-identical).

## 2. Arm 2 — coherence-adaptive Barnes-Hut θ(q)

**Problem:** the tree gravity walk opens a node by geometry only:
`open = (!is_leaf) && (half/sep > theta || contains)` with theta fixed at 0.5.
High-q condensate (an organized force field) wants more precision (tighten); incoherent
voids (coarse multipole fine) want fewer node evals (loosen).

**Mechanism:** add a **per-node mean coherence q_n** to the tree node table (a new
`nodeQq` float buffer written by the build's mode-6 MOMENTS pass from the source q's).
In the walk, the effective opening criterion for a node becomes
`theta_eff = theta · (1 − α·(q_n − q_cent))`, clamped to a sane band
(e.g. [0.3·θ, 2·θ]). High q_n → theta_eff < theta → *more* opens (tighter in
condensate); low q_n → theta_eff > theta → *fewer* opens (coarser in voids). α and the
clamp are host constants; q_cent is the field's running mean q (already read as
`_q_mean`).

**Root files:** `cassi_tree_build.glsl` (moment pass writes `nodeQq`), a new `nodeQq`
buffer + uniform binding, `cassi_tree_gravity.glsl` (θ_eff in the open test + a new PC
`q_cent`/`alpha`/`theta_scale`), `cassi_sim.gd` + engine wiring, `layout.gd`.
**Gating:** new `coherence_theta` toggle (default OFF → θ_eff ≡ θ, bit-identical).
**Metric (frozen):** with `coherence_theta` ON on a galaxy-like blob, measure (a) the
node-eval count per particle (fewer in voids = the win) and (b) the force trajectory
matches the OFF run within a tolerance (correctness — the adaptive θ must not change
the physics beyond the opening tolerance). Probe before/after.

## 3. Arm 3 — q-weighted envelope + coherence-gated steering cadence

Two sub-arms, both default-off additive.

### 3a. q-weighted COM (the envelope follows the coherent core)
**Problem:** the window tracker (`read_com`, engine) follows a **plain mass-weighed**
COM — stray void particles drag the envelope, which is the "doesn't adjust
accurately" complaint.

**Mechanism:** `read_com()` also reads `_field_q` and weights each subsampled
particle's position by its **field coherence q** (the coherent core dominates; void
particles contribute ~nothing). New `q_weighted_com` toggle (default OFF → plain COM,
bit-identical). The sim's `_track_window_center` consumes the published COM unchanged
(it already just follows `_pub_com`).

### 3b. coherence-gated steering/rebuild cadence
**Problem:** the mesh rebuilds every fixed `ML_REBUILD` steps. Coherent (high-q)
cells move rigidly (phase-lock) and stay valid longer — rebuilding them as often as
incoherent cells wastes compute.

**Mechanism:** the rebuild threshold becomes adaptive to the running `_q_mean`:
`thresh = round(ML_REBUILD / (1 + β·q_mean))` — high mean-q → longer interval
(rebuild less), low mean-q → closer to the fixed base. New `adaptive_rebuild` toggle
(default OFF → fixed ML_REBUILD, bit-identical). Root: `cassi_sim.gd` line ~1338
(`_ml_step_count >= threshold`) + the cell PC already carries the steer time
(`dt·ML_REBUILD` at float 60 — a longer interval must feed the same encoding).

## 4. Statistic / metric / decision tree (frozen, no post-hoc tuning)

**Bit-identity (-a, -2, -3 all MUST pass):**
- `assert_layout` **0 mismatches**.
- `verify_voronoi3d` 9/9, `verify_voronoi3d_moving` 10/10, `verify_meshless_reconstruct`
  7/7, `verify_meshless_gravity` (tree arm) — ALL green with every new toggle OFF, and
  `verify_meshless_gravity`'s trajectory is **bit-identical** to the pre-change run
  (this is the arm that exercises the tree walk — the critical one for Arm 2).
- Default sim run: no `_field_*` / force change when toggles are off.

**Arm 2 correctness (ON):** on a galaxy/blob, with `coherence_theta` ON, the
time-averaged force (or the first-K-step trajectory) matches the OFF run within the
θ-opening tolerance (probe compares max |Δa/a| ≤ 1e-3, else FAIL-review). The **win**
metric is node-evaluations-per-particle: ON < OFF in incoherent regions (report the
ratio; PASS if the void-region ratio ≤ 0.85, i.e. ≥15% fewer evals in voids).

**Arm 1 correctness (ON):** on a dense coherent blob, instancer site-coherence vs the
grid trilinear in-window agree ≤ 1e-3 (reuse the boxless_probe pattern); and the
shortlist count is a small fraction of 8192 in a sparse-field run (the cost win).

**Arm 3a correctness (ON):** a blob with a few stray void particles far outside;
the q-weighted COM stays near the blob while the plain COM is dragged toward the
strays. Report both; PASS if q-weighted COM displacement from the blob < 30% of the
plain COM displacement.

**Arm 3b correctness (ON):** running mean-q high → the rebuild interval is longer than
fixed; report measured interval; no NaN/instability over a test run.

**Decision tree (applied per arm):**
1. Bit-identity fails → **REJECT** that arm (revert; keep only the pre-reg/design).
2. Bit-identity passes but ON-correctness fails → **FAIL-review** (fix or drop that arm).
3. Both pass → **SUPPORTS** for that arm; record in the report.

## 5. Pre-registered run plan

1. Implement **Arm 3a** (q-weighted COM; smallest, self-contained).
2. Implement **Arm 3b** (adaptive cadence).
3. Implement **Arm 2** (nodeQq + θ_eff — the tree-table change; most delicate).
4. Implement **Arm 1** (shortlist + instancer site path; needs the boxless wiring).
5. After each: parse-gate, glslang (edited shaders, two-arg `atan` rule), Godot
   `--import`, `assert_layout`, the relevant arms (windowed; the tree arm +
   `verify_meshless_gravity` for Arm 2), bit-identity check, revert `.glsl.import`/
   `project.godot`/`main.tscn` churn, commit path-limited (CassiCosmos local-only).
6. Consolidated probe (per §4) + `coherence_adaptive_report.md`.

## 6. Non-goals

- No change to the sites' field evolution or the deposit (same as boxless_field pre-reg).
- No change to the default physics when every toggle is OFF (bit-identity is the gate).
- Arm 1 does not change the *force* of merge/condensation; it changes only the instancer
  *display* coherence/phase source (grid → sites when boxless_field is on).
- No touching owner-live files (`main.tscn`, `project.godot`, `research/`, `tools/`,
  `scenes/mind_engine*`, `verify_telescoping_weak.*`).

## 7. Risks

- **Arm 2 node-table change**: adding `nodeQq` touches the build MOMENTS pass + the walk
  reads + the tree uniform set + `layout.gd` — a mismatch breaks the tree arm (which
  `verify_meshless_gravity` catches). Mitigation: follow the boxless append precedent
  (additive buffer, guarded reads, `assert_layout` gate).
- **Arm 1 shortlist cadence**: the shortlist must rebuild on the steer cadence, not per
  frame; a stale shortlist reads stale coherence. Mitigation: rebuild in the same
  `ML_REBUILD` block as `_mesh_rebuild()`, and gate ON only when `boxless_field` is on.
- **Arm 3 α/β tuning**: the α (Arm 2) and β (Arm 3b) constants are host exports; a bad
  value could over-loosen (loss of precision) or over-shorten (no win). They're
  default-OFF; the probe measures the actual effect before adoption, and the default
  never changes.

Pre-registered signature: frozen. Any change to §1-§5 requires a new version + owner
acknowledgement.
