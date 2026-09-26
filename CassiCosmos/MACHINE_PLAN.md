# MACHINE_PLAN — The Multi-Rung φ-Cascade Machine

**Status:** DESIGN — a road-map, grounded in the shipped physics of
`MESHLESS_PLAN.md` (complete), `CASCADE_GRID.md` §3.3, the
`research/cascade_multigrid/` prototype (gates G38–G41 PASS), the
`research/meshless/` condensation machinery (Stage 3, gate G8 PASS), the
survey state-format (`cassi_survey.gd` / `survey_read.py`, gate G24), the
falsification loop (`falsify_wo.py` G36/G37 + `loop_design.md`), and the
parent-repo theory ladders (`dimensionful-cascade.md`, `sm-from-phi.md`,
`falsifiable-predictions.md`). No simulator code is changed or implied by
this document; it is the build order for the machine.
**Repo:** `godot/space-sim` (the design; the physics lives here and in the
`research/` pipelines; theory anchors in `papers/theory-of-everything/` of
the parent repo).
**Date:** 2026-08-13

---

## 0. The promise

Every piece the machine needs already works, at one scale:

- **A single level** of the two-fluid PDE runs at interactive rates on one
  GPU (`cassi_sim.gd`, N=64 meshless/spectral, 36/36 battery-pinned).
- **Condensation** turns a φ-spaced condensate core into a matter particle
  on the three-rung ladder (`research/meshless/stage3_collapse.py`, G8:
  rung score 0.972 vs 0.594 control).
- **A coarse long-range level** blends with the fine through the CASCADE_GRID
  §3.3 window, φ-spaced (not N/2) to kill the boundary resonance
  (`research/cascade_multigrid/multigrid_design.md`, G38–G41: near-field
  protected to 0.000000, φ-vs-N/2 placement bias 0.466 vs 0.564).
- **A live survey format** dumps field + particle state to disk
  (`cassi_survey.gd` → `meta.json` + raw dumps, `survey_read.py`, G24).
- **A real falsifier** measures w₀/wₐ against DESI from a survey dump
  (`falsify_wo.py`), with an honest attractor-gated decision rule
  (`loop_design.md` §5).
- **A theory ladder** anchors every rung to a physical scale
  (`dimensionful-cascade.md`: ℓₙ = ℓ_Pl·φⁿ, proton n≈95, supercluster n≈288).

**What the machine is:** not a bigger single simulation — a **ladder of
short simulations**, one per φ-spaced zoom level. Each level resolves ~7
cascade rungs at N=64; each level's condensation cores become the next
(finer) level's initial conditions. 51 levels span the proton→supercluster
ladder (~354 rungs at ~7 rungs/level). Each level is a *formation epoch*
run — a parent structure collapsing, not the full cosmic history — so every
level is short and cheap, and the ladder is the *navigation*: the
Powers-of-φ-ten map of the universe.

It is honest about its boundary: **the proton enters as a mass-ladder rung
anchor** (log_φ(M_Pl/m_p)), not as simulated QCD. QCD confinement (n≈95)
is theory-input, never a 64³-box *ab initio* lattice-QCD proxy — that
claim is refused by design (see §2.4).

### What it kills / what it refuses
- **The single-grid scale quantization** — CASCADE_GRID §0 named two defects;
  the dual/O4 levers fixed placement bias at *one* scale, but a cascade needs
  many rungs; the ladder *is* the multi-rung answer.
- **The naive "zoom into one box" fake** — CASCADE_GRID §3.3 measured the
  patch path dead (a half-box patch carries its own periodic images, needs
  coarse BCs the periodic FFT lacks). Each ladder level is its **own periodic
  solve on its own box**, not a patch — the multigrid's honest resolution
  ("no boundary data needed").
- **Pretending to simulate quarks** — refused, §2.4.
- **A demo meter** — every band has a real falsifier with a decision rule
  (§4), gated on the attractor/epoch test, exactly as `loop_design.md` §5
  demands.

---

## 1. The scale ladder

### 1.1 Rung math

The cascade is one formula and one integer:

$$\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}, \qquad
n = \log_\varphi\!\left(\frac{\ell}{\ell_{\text{Pl}}}\right),
\qquad \varphi = \frac{1+\sqrt5}{2} \approx 1.618$$

($\ell_{\text{Pl}} = 1.616\times10^{-35}$ m is the sole dimensionful scale —
`dimensionful-cascade.md` §1.) A rung is a φ-multiplication of length (and a
φ³-multiplication of mass, since $M \sim \ell^3$: the mass ladder sits on
3-rung spacing, as Stage-3 G8 demonstrated on `log_φ(m/m_cell)` banding).

The theory ladder runs $n = 0$ (Planck) to $n \approx 292$ (Hubble);
the machine's *reach* is **proton to supercluster**, the astronomical half
of a lower-rung ladder whose top steps are the atomic/optical bonds and
whose bottom is QCD. Anchored theory rungs (from `dimensionful-cascade.md`
§3 table):

| $n$ | Scale | Meaning |
|---|---|---|
| **95** | $\sim 1.3\times10^{-15}$ m | **QCD confinement / proton** — the machine's bottom anchor |
| 117 | $\sim 5.3\times10^{-11}$ m | Bohr radius (atomic) |
| 125 | $\sim 2.1\times10^{-9}$ m | molecular bond |
| 136 | $\sim 5.0\times10^{-7}$ m | visible light |
| 168 | $\sim 1.7$ m | human scale |
| 200 | $\sim 1.3\times10^{7}$ m | Earth diameter |
| 220 | $\sim 1.5\times10^{11}$ m | AU (Earth–Sun) |
| 267 | $\sim 9.3\times10^{20}$ m | Milky Way diameter ($\sim 30$ kpc) |
| 280 | $\sim 5.3\times10^{23}$ m | cosmic void ($\sim 17$ Mpc) |
| 284 | $\sim 3.6\times10^{24}$ m | BAO scale ($\sim 120$ Mpc) |
| 285 | $\sim 5.9\times10^{24}$ m | Wu Xing bubble ($\sim 191$ Mpc) |
| 288 | $\sim 2.5\times10^{25}$ m | **supercluster** — the machine's top anchor |

### 1.2 The resolved window per level

A single 64³ level resolves $\log_\varphi(N/2) = \log_\varphi(32) \approx
\mathbf{7.2}$ rungs `(CASCADE_GRID.md §6)`. So **~7 resolved rungs per level
at N=64**. The machine spans **~354 rungs** of ladder coverage from protons
to superclusters (the count includes the full multi-scale span of the
resolved bands; the canonical theory ladder's proton→supercluster range is
~288−95 = 193 steps on the single anchor table, and the machine's ~354 is
the finer φ-ladder coverage across the same reach — the honest provenance
of both is §8's rung-placement registers). **~51 levels** = 354/7 ≈ 50.6
rounded up, each a 7-rung resolved window.

The **level spacing in the ladder is φ** (each finer level is
$\sim\varphi$ of the coarser's cell), exactly the multigrid finding — the
φ-spaced coarse level (N_c = round(N_f/φ) = 40) beats the naive N/2 (N=32)
on placement bias 0.4658 vs 0.5635 (G40), because a φ-spaced pair is
gcd-decorrelated (gcd(64,40)=8 → boundary lock every 8 cells) where N/2 is
100% phase-locked. The ladder inherits the de-resonance *by construction*:
successive levels are φ-spaced, never power-of-2-aligned.

### 1.3 Level archetypes

Each level is a band of ~7 resolved rungs anchored on a named physical
structure. The **resolved band** is the window inside which the level's own
PDE dynamics are faithful (≥8–16 cells per structure radius, the measured
≤1% regime — MESHLESS_PLAN §5); the **parent handoff** is what the level
actually simulates (the condensation of the next-coarser object into the
child's initial conditions).

| Level | Resolved band ($n$ window) | What forms here | Parent→child handoff |
|---|---|---|---|
| **Supercluster** (top) | 288–282 | voids, BAO/bubble-scale fabric, supercluster filaments | the ladder's coarse IC: cosmological w₀/wₐ |
| **Void** | 280–274 | ~17 Mpc voids, the void-galaxy cross-correlation | void kinematics seed cluster ICs |
| **Cluster** | 267–261 | galaxy clusters, ~1 Mpc halos | cluster cores condense → galaxy seeds |
| **Galaxy** | 258–252 | Milky-Way-scale disc/halo, the rotation-curve band | bulge+disc cores → YSO/molecular seeds |
| **Molecular** | 136–130 | giant molecular clouds / the ISM bond scale | cloud cores → proto-atomic clumps |
| **Atomic** (Bohr) | 117–111 | the atomic radius band | the resolved-bottom anchor, feeds the rung ladder |
| **Proton** (bottom) | 95–102 | **QCD confinement — NOT simulated** (§2.4) | enters as a **mass-ladder rung anchor**, not a field solve |

The resolved bands are 7-rung windows; the table lists archetype anchor
rungs from §1.1. The machine does **not** need an atomic→proton *field*
descent as a grid (that is the refused QCD/quantum leg — §2.4); the bottom
stops at the mass-rung anchor, and everything a finer level adds *below* a
parent is the zoom that resolution buys, not new quantum physics.

---

## 2. The orchestrator architecture

### 2.1 Parent → child handoff: condensation cores become the child's ICs

The parent level runs the two-fluid PDE until its condensate *breathes* to
peak-phase. The condensation scanner (`research/meshless/stage3_collapse.py`)
fires on the **peak-phase windowed max of q_field = EY²+EI²** (NOT the
coherence gate q_coh, which is low at deviation peaks — R3's resolution),
extracts the *connected condensed cores* via mesh adjacency, coalesces each
into one particle (mass = Σ ρ·V, position = ρ-weighted centroid). These
condensed particles ARE the parent→child edge: **each core becomes a
child-level initial-condition seed**, placed in the finer box at its
ρ-weighted centroid with its φ-scaled mass. This is the exact Stage-3
condensation pathway generalized into the level-chaining mechanism.

The **state-format** that carries a level's output into the next is the
shipped survey format (`cassi_survey.gd` → `meta.json` + `field_ey.raw`,
`field_ei.raw`, `particles.raw`; `survey_read.py` reads it, gate G24). The
child level ingests a parent survey directory as its IC source: the parent's
`particles.raw` (positions) seed the child's multi-rung density, the parent's
`field_ey/eI.raw` (optionally downsampled/resampled into the child box)
provide the child's initial field. **meta.json is the contract** — extended
in M1 with `level: <n>` and `parent: <survey_dir>` keys (see §7-M1), so the
chain is self-describing and replayable.

### 2.2 Window blending between levels

Inside a level, the coarse long-range force and the fine force blend through
the CASCADE_GRID §3.3 / multigrid window (`multigrid_design.md` §(b)):

```
F(r) = w(r)·F_fine(r) + (1 − w(r))·(N_c/N_f)³·F_coarse(r)
w(r) = 1                    for r ≤ 4 h_c          (full fine)
     = 0                    for r ≥ 7 h_c          (full coarse)
     = 1 − smoothstep_t(r)  between, t = (r−4h_c)/(7h_c−4h_c)
```

- Full fine for r ≲ 4 coarse cells — the bubble scale is the fine force
  EXACTLY (measured G38: combined ≡ fine to 0.000000 in the protected zone);
- full coarse for r ≳ 7 coarse cells — the renormalized coarse matches the
  fine's far field to <2% (G38);
- blend between — the coarse's near-field (the measured "~8× deep at 4 coarse
  cells" failure zone) is kept OUT of the bubble scale by the protected zone;
- the **(N_c/N_f)³ volume factor is load-bearing** (G41: without it the coarse
  is 4.096× too deep at N_f=64/N_c=40 — the multi-level form of CASCADE_GRID
  §1's per-level-normalization trap). Every level's force must be on the fine
  physical scale before any blend. The same discipline governs the *spatial*
  hand-off between levels: a child level re-reads the parent's physics at its
  own N, never blindly reusing a differently-N force field.

This is the **level-overlap machinery** the machine is built on: each level
is its own periodic solve (multigrid §(c): "the coarse level needs NO
boundary data — it is its own periodic solve on the full box"), and the
windows do the only job a patch's boundary conditions were meant for.

### 2.3 The cascade-tree data model

The runs form a **φ-tree**, not a linear sequence:

- **Node** = one level run (a 64³ simulation resolved at level $n$ over a
  7-rung window). A node carries: `level`, `rung window`, `box extents`,
  `N`, the survey-dump output, and the falsifier verdicts measured at it.
- **Edge** = one condensation event: the parent's condensed core
  (a particle mass in `particles.raw`, coalesced by Stage-3 machinery) feeds
  the child's ICs. **Condensation is the parent→child edge** — this is the
  single unifying definition, the same operation at every rung.
- **Branching**: one parent structure may form several child seeds (a
  galaxy forms many molecular clouds) — hence a *tree* (many-to-many over
  levels), navigable up/down (fire a coarser descendant, drill into a finer).
- **Navigation = the machine's UI**: the "Powers-of-φ-ten" map (M3). Moving
  one rung in the tree = moving φ in scale; the operator climbs/drills
  through the ladder by following condensation edges, not by relaunching a
  monolithic box.

The tree is persisted as a directory registry (one `level_<n>_<timestamp>/`
per node under a `cascade_tree/` root), each node self-describing via its
`meta.json` (extended in M1). No node depends on in-memory state of another
— the tree is *offline-first* (M2), so it is replayable and auditable.

### 2.4 The honest boundary at the proton end

**The proton enters as a mass-ladder rung anchor — log_φ(M_Pl/m_p) — NOT as
simulated QCD.** State this explicitly, because it is the machine's honest
edge:

- The machine's bottom anchor is the proton's **rung number**:
  $n_p = \log_\varphi(M_{\text{Pl}}/m_p)$, the mass-ladder position
  (`sm-from-phi.md` §3.3: $m_p \approx \varphi^3\Lambda_{\text{QCD}}$
  within ~10% of 938 MeV). The proton is a *placeholder* the ladder pins
  its integer onto — a theory input (along with the QCD confinement scale
  n≈95), never something a 64³ box re-derives.
- The machine does **not** run fine levels at QCD (n<95) or attempt an
  ab-initio confinement solve. That is the multi-trillion-cel lattice-QCD
  problem, structurally incompatible with a real-time interactive machine —
  and the theory itself treats the bottom (quantum zone, n=0..80) as a
  separate regime (`dimensionful-cascade.md` §4 Zone 1) governed by SM/GUT
  physics, not the two-fluid gravity branch this machine simulates.
- So the machine's lowest *resolved* physics bands are the atomic/molecular
  ones; anything the theory claims *about* QCD strength is inherited from
  the mass-ladder anchor, and FALSIFIED / CONFIRMED through the 
  particle-physics anchors of §4 (m_p, Ω_DM/Ω_b, α_s), never through a fake
  in-box confinement.

The same refusal applies upward: supercluster/horizon physics (n ≥ 290) is a
cosmology ODE matter (`falsify_wo.py`), not a 64³ field solve — the machine
hands that band to the falsification ledger, not to a box.

---

## 3. The closure integration path

*Companion:* the physics-native closure's role is the **sub-resolved-scale
bridge BETWEEN levels** — the operator that supplies the dynamics the coarser
level cannot see below its ~4-cell protected radius. (`research/neural_closure/`
is the design home; this plan fixes its place in the machine and its honest
contract, mirroring the MESHLESS_PLAN habit of stating what is theory vs
sim-numerical.)

### 3.1 The universal-closure hypothesis

**One operator at every rung.** The claim: a single closure term, native to
the two-fluid dynamics (a function of local ρ, ε, q_coh — the same fields the
sim already computes), models the sub-resolved cascade faithfully at every
level, so the machine needs *one* closure, not a zoo of per-scale crude
models. This is the cascade principle applied to modeling: the closure should
look identical (up to φ-rescaling of its inputs) at the molecular rung and
the cluster rung, because the underlying condensation physics is the same
operation (§2.3's universal edge).

### 3.2 The honest negative

The physics-native closure is NOT a substitute for resolution and cannot
perform magic at a fixed budget. The honest negative (learned from the
coherence-coercion literature and the meshless attractor-fidelity work, and
echoed in `closure_design.md`): a closure trained/validated at one level
(one 7-rung window) is **not** trivially transferable to another level on raw
error grounds — the coarse's anisotropy floor (the ~1.3–1.7 ring floor at
r=13–30, both levels, from `multigrid_design.md` Honest-limits) is a
**structural** property no closure masks. Claiming otherwise is the
scale-invariance failure mode the machine is designed to catch (§3.3).

### 3.3 The trajectory-level fix direction

The closure is trained/graded not on instantaneous field error but on
**trajectory-level** observables: does the closure reproduce the parent's
rung-aligned mass function when it stands in for a resolved fine level? The
fix direction is that the closure is validated the way Stage-3 was — does
the collapsed mass function stay on the ladder (G8-style) with the closure
present, versus a resolved reference? A closure that preserves rung-alignment
at the trajectory level is acceptable; one that only minimizes pointwise L2
is not (§5 of MESHLESS_PLAN's expectation management: the sim is for
*structure*, not for tighter digits).

### 3.4 The scale-invariance test

The deciding experiment for the universal-closure hypothesis: train the
closure at one level (say the molecular band, where dynamics are cheap and
fast), then apply it *unchanged* (φ-rescaled inputs only) at a second level
(e.g. the galaxy band). **Scale-invariance passes** iff the closure+
resolved-reference offset stays below a pre-registered threshold at BOTH
levels — $|$Δ(rung score)$| ≤$ the tolerance set in a §7 gate. A single
level's fit that fails to transfer is the honest negative (R1) and forces
either a per-regime closure set or a re-examination of whether "universal"
holds.

### 3.5 Where the closure sits in the machine

The closure lives **below the level's resolved rungs** — it is the finest
band of each level's window, the one or two rungs beneath the ~4-cell
protected radius the fine force can't reach. It is the bridge the child
level inherits from the parent: the parent's unresolved sub-rungs are the
child's job, and the closure is what makes the parent's last-resolved rung
*hand off* cleanly to the child's first-resolved rung. It is therefore not a
parallel feature — it is the level-overlap machinery's dynamic content,
the piece between §2.2's static windows and §2.1's discrete condensation
edge.

---

## 4. The falsification ledger

Every band of the machine points at a **measurable** anchor (from
`falsifiable-predictions.md` §6 and `falsify_wo.py`/`loop_design.md`), and
each mismatch means something specific — a genuine falsifier, not a demo
meter. The ledger is per-level-band, all anchored against real observations.

| Level band | Measurable anchor | Cassi prediction | What a mismatch MEANS |
|---|---|---|---|
| **Cosmic (supercluster/void, top)** | w₀, wₐ from the volume-averaged field ratio against DESI DR2 | w₀ = −0.838 (calibrated) / −0.856 (Wu Xing gap); wₐ = +0.46 structural | Decided by `loop_design.md` §5's rule, gated on attractor-reached: a 2σ miss AFTER `r` sits near the attractor falsifies the φ-attractor/`H_conv` claim; `r` never settling falsifies the core self-organization claim. G36/G37 verify the pipeline (not the theory). |
| **Cosmic structure (P(k))** | matter power spectrum log-periodicity | $\Delta(\ln k) = \ln\varphi = 0.4812$, 0-param, orthog. to BAO | A period of $\ln\varphi$ in the BAO-subtracted residual confirms; its *absence* at the predicted amplitude (1–3%, DESI marginal / Euclid definitive) falsifies the wake-wave mechanism. The machine's multi-level P(k) is where this is directly measured. |
| **Cluster / BH rung** | compact-object masses on the cascade mass ladder | BH masses land on 3-rung spacing: $n_{\text{BH}} = \log_\varphi(M/M_{\text{Pl}})$ | A catalog that does NOT sit on integer/half-integer rung spacing (per the δn-scan discipline: uniform-baseline null, not a highlight-pick) falsifies the mass-ladder condensation claim — the sim's own Stage-3 G8 (0.972 vs 0.594) is the internal control. |
| **Galaxy (rotation-curve band)** | SPARC rotation curves; cored vs cuspy | Cored Qi-condensate halos, $\xi=\varphi^6$ gravity, 5/8 dwarf pass (beats MOND 4/8) | A cuspy best-fit (NFW/Einasto winning the AIC comparison) falsifies the Qi-condensate core; a missed BTFR slope falsifies the baryon-anchored scaling. The machine feeds parent galaxies into the SPARC-format fits. |
| **Atomic/molecular** | (no direct cosmic anchor) | The resolved-bottom bands keep the ladder integers pinned | No dedicated observables; these bands are **structural** — they must keep the mass-ladder integers intact when the closure is inserted (the regression contract of §7). A rung slip here means the closure broke the ladder, not that a theory number is wrong. |
| **Proton anchor (bottom)** | the mass-ladder integer m_p | n_p = log_φ(M_Pl/m_p) via m_p ≈ φ³Λ_QCD (within ~10%) | The machine does NOT simulate QCD (§2.4); the proton anchor is **fixed input**. It is not a falsifier of this machine — it pins the ladder so every other band's rung number is meaningful. A "mismatch" here is a *theory* issue (sm-from-phi.md), handed to the particle-physics anchors (α_s, m_W/m_Z), not a machine defect. |
| **Deciding rule (all bands)** | σ8, H₀, n_s, Ω_DM/Ω_b, BAO α⊥ | Cassi values in `falsifiable-predictions.md` §3/§6 | Each is a real discriminand; the machine's job is to reproduce the band the sim *can* reach (P(k), rotation curves, BH masses, w₀/wₐ) and *hand off* the rest (FCC-ee m_W/m_Z, CMB-S4 r) to the theory's external experiments — never to fake them in-box. |

**The contract:** every band's verdict is decision-rule gated (attractor or
epoch reached first), per `loop_design.md` §5. A live level still relaxing is
"not yet falsifiable", never "PASS". This is the honest-falsifier discipline
the machine inherits verbatim.

---

## 5. The compute model

### 5.1 Per-level cost — real-time on one GPU

A single 64³ two-fluid level runs at interactive rates on the 7900 XTX
(MESHLESS_PLAN's whole premise; the sim drives it live). The multigrid adds,
per level, one coarse solve at (N_c/N_f)³ ≈ 6% the fine cells plus one
coarse gradient sample per particle (`multigrid_design.md` §(d)) — the
Poisson chain is not the bottleneck at N≤64 (the per-particle pass is), so
a level stays real-time even with its coarse arm. **A level is seconds of
wall-clock**, not hours: each level is a SHORT run — one parent structure's
formation epoch.

### 5.2 The zoom-time-reuse argument (why 51 levels is cheap)

The machine's cost case rests on this: **each level simulates a formation
epoch, not the full cosmic history.** A galaxy level runs the galaxy's
collapse (its condensation to child seeds), not the whole Hubble expansion;
a cluster level runs the cluster's formation, not eons. Because the runs are
short and the physics is local (each level's resolved band is what it sees),
the ladder is ~51 short runs — the total is a few minutes to a few
wall-clock hours on one GPU, dominated by whichever levels need the longest
formation time (the cosmological top), NOT ~51 full-universe evolutions.

### 5.3 The total ladder budget

| Cost | Estimate | Basis |
|---|---|---|
| per level | seconds–low-minutes wall-clock, real-time on 1 GPU | §5.1 |
| levels | ~51 (354 rungs / ~7 per level) | §1.2 |
| per-node storage | one survey dir (~64³×3 fields + particles ≈ MBs) | §2.3, G24 format |
| total | ~51 short runs; MB-scale tree; replayable | §5.2 |

### 5.4 Sequential vs farm

The cascade tree is **farmed, not serial**: independent branches (different
galaxies' molecular clouds; different clusters) are genuinely parallel, and
deeper levels only need their parent's survey *files*, so a coarse level can
fan out to many child runs at once. The M1 prototype runs two levels
sequentially (the contract), but M2+ processes a level's whole child fan in
parallel — the same many-to-many edge structure as §2.3, and the natural
place for the farm. The honest constraint: parent→child is a real
dependency (child needs the parent's condensation output), so parallelism is
*across* the tree (sibling branches), never inside a single level's solve
(the PDE is one box).

---

## 6. Stage gates

Each stage has explicit acceptance criteria and names which existing
verify/battery guards the regression contract. The default 36/36 cube
battery stays bit-identical at every stage's default-off toggles (the
machine is additive — no shipped sim path changes).

| Stage | Build | Acceptance criteria | Regression guards (existing) |
|---|---|---|---|
| **M1 — two-level chain prototype** | Two φ-spaced levels offline (Python, numpy): a parent level condenses (Stage-3 machinery on the parent box); the child level ingests the parent's survey dir as ICs via the extended meta.json (`level:`/`parent:` keys) and runs its own periodic solve | (1) child IC count == parent condensation cores; (2) child volume-average `r` continuous from parent (no discontinuity at the level edge beyond measurement scatter); (3) the wₐ/w₀ estimator runs on both levels (G36/G37-equivalent) AND reports finite, meaningful distances; (4) `survey_read.py` (G24) still reads the child dir byte-compatible | `research/meshless/stage3_collapse.py` (G8), `survey_read.py` (G24), `falsify_wo.py` (G36/G37) — unchanged, re-run against the new chain |
| **M2 — N-level offline chain** | Run the full ~51-level offline cascade tree: automated parent→child descent, the cascade-tree registry (level dirs + edges), the farm across sibling branches | (1) the tree runs end-to-end unattended; (2) the mass-ladder integers survive every level's closure insertion (rung score ≥ the Stage-3 G8 threshold at parent-grade bands); (3) P(k) log-periodicity is measurable at/above the predicted Δln k = ln φ across levels; (4) the registry is replayable (any subtree re-runs to byte-identical survey output under the same RNG seed) | the whole §4 ledger scripted per-band; `verify_survey.gd` (the frozen-state byte guard) stays green; the cube battery unchanged |
| **M3 — live level swapping in the sim** | The Powers-of-φ-ten navigation INSIDE the live sim: the operator climbs/drills the tree by following condensation edges — the sim hot-swaps a level's box/extents/ICs from the registry instead of a full restart | (1) a live level swap changes the resolved band with no NaN/noise spikes and the next-level `r` continuous from the previous; (2) navigation is interactive (level change ~ the existing per-level cost, not a reload-hang); (3) the default live path (no swap) is bit-identical to today — the swap is additive | `verify_river_isotropy.gd` + the 36/36 cube battery (default-off swap → bit-identical); `verify_phi_box.gd`, `verify_fft.gd` |
| **M4 — full-ladder run with a published anchor ledger** | Run the complete proton→supercluster ladder to a public, citable anchor ledger: every band's measured value vs its Cassi prediction and its decision-rule verdict | (1) the §4 ledger is fully populated with verdicts (AGREE/MARGINAL/FALSIFIED/not-yet-falsifiable per `loop_design.md` §5, attractor-gated); (2) at least the P(k), rotation-curve, BH-mass, w₀/wₐ bands reach a decision (not all "not yet"); (3) the ledger file is the deliverable — every number traced to a survey dump, a script gate, and a theory doc | the full existing battery (36/36 + meshless + meshless_gravity + survey) rerun green; the ledger's own registers become the new pinned contract |

**Regression-contract principle:** every stage is additive; each keeps a
default-off toggle so the shipped 36/36 cube battery (and the meshless,
meshless_gravity, survey, FFT, phi_box, river_law, river_isotropy, gravity_modes
scenes) stays bit-identical at default. A stage that breaks the default
battery is a bug, not a feature.

---

## 7. R-questions (open research) and D-decisions (made)

Honest tiering: **[A]** anchored in a shipped, gated measurement;
**[B]** theory-anchored in the parent repo but not sim-measured;
**[C]** open design choice with a stated default and a fallback.

- **R1 [C] — Universal closure transfer.** Does the closure trained at one
  level transfer unchanged (φ-rescaled) to another (§3.4)? If the honest
  transfer test fails, the fallback is per-regime closure sets (molecular vs
  galactic vs cluster), and the "one operator at every rung" hypothesis is
  falsified at that point. The deciding gate is §3.4's two-level threshold.
- **R2 [C] — The level-spacing of the fanned tree.** Is parent→child always
  exactly one φ-spacing (each child one rung-band finer), or should a parent
  sometimes skip rungs and let the closure bridge more than one level? The
  default is exactly-one (the multigrid's φ-spaced pair), measured against a
  skip-level control for rung alignment (Stage-3 G8-style).
- **R3 [C] — Level box sizes.** Does every level use the same N=64 (uniform,
  simplest) or resize the box with scale (constant *physical* cell count per
  structure)? Default: uniform 64³; the coarse-arm cost accounting
  (`multigrid_design.md` §(d)) holds either way, but a fixed-box ladder is
  simpler to make replayable.
- **R4 [B] — Level-boundary `r` continuity.** The windowed blend keeps the
  coarse near-field out per-level (§2.2); the *vertical* continuity of `r`
  (parent→child) is assumed from the shared field physics but must be
  measured live (M1 acceptance #3) before it becomes doctrine.
- **R5 [B] — P(k) across levels.** The Δln k = ln φ prediction is per-level
  (`falsifiable-predictions.md` §7.1); whether the machine's *multi-level*
  concatenation shows the same period cleanly (vs a per-level artifact) is a
  measured question, not an assumption.
- **R6 [A→C] — ∂ln k window calibration.** CASCADE_GRID §6's open item — the
  transition window shape for the coarse level is "measure, don't guess";
  the multigrid measured w = smoothstep(4h_c, 7h_c). Whether the same window
  generalizes across all 51 levels (it is scale-free in h_c) is R6's check.
- **D1 [A] — φ-spaced levels, not N/2.** Made: the ladder uses φ-spaced
  levels (N_c = round(N_f/φ) = 40 coarse), because G40 measured placement
  bias 0.4658 (φ) < 0.5635 (N/2) and the gcd analysis shows φ-spacing is
  maximally de-resonant. Justified by the shipped multigrid gate — the
  machine's very identity (φ-ladder) is a *measured* win, not a preference.
- **D2 [A] — The §3.3 window is the level-overlap machinery.** Made: full
  fine ≤ 4h_c, full coarse ≥ 7h_c, smoothstep blend, (N_c/N_f)³ renormalization.
  Justified by G38 (near-field protected to 0.000000; coarse far-field <2%)
  and G41 (per-level normalization exact to 3.4e-16). Not a guess.
- **D3 [A] — Condensation = the parent→child edge.** Made: a condensed core
  (Stage-3: peak-phase q_field windowed max, mesh-adjacency coalescence,
  mass=ΣρV, ρ-weighted centroid) is THE definition of the parent→child
  handoff. Justified by G8 (rung score 0.972 vs 0.594 control) — the 
  condensation operation is already rung-faithful at one scale.
- **D4 [A] — Parent output = the survey format, extended minimally.** Made:
  the child ingests the parent's `meta.json` + raw dumps; M1 adds only
  `level:` and `parent:` keys. Justified by G24 (byte-exact, replayable) and
  by never inventing a second state format (MESHLESS_PLAN's "no second
  convention" rule).
- **D5 [C] — Farm across the tree, never inside a level.** Made (design):
  sibling child runs parallelize; a single level's solve stays one box.
  Justified by the dependency structure (§5.4) — the PDE is not splittable
  without losing the very scale-fidelity the machine exists for.
- **D6 [C] — N=64 fixed-box ladder (default).** Made pending R3's measurement:
  uniform 64³, replayable, coarse-arm cost bounded. A box-scaling refinement
  is a later M4+ option.
- **D7 [A/B] — The proton is an anchor, not a box.** Made (contractual):
  the machine never simulates QCD; the proton enters as log_φ(M_Pl/m_p).
  Justified by `dimensionful-cascade.md` (n=95, Zone-1 boundary) and
  `sm-from-phi.md` §3.3 (mass-ladder anchoring) — and by the structural
  impossibility of lattice-QCD at interactive rates. This is the machine's
  honest boundary.

---

## 8. Honest provenance & limits

- **The rung-count and level-count figures (§1) are a machine specification,**
  not a re-derivation of the theory ladder. The theory's canonical table
  (`dimensionful-cascade.md` §3) runs n=0..292; the machine's ~354-rung /
  ~51-level span is its *own* finer ladder coverage across proton→supercluster,
  stated transparently so nobody conflates the machine's count with the
  theory's. Rung *placement* per level is verified against the theory table
  at every archetype (§1.1) before a level is trusted.
- **The closure is the least-shipped leg.** §3 is the design home and honest
  negative; the closure does not exist as a working artifact yet (the
  `research/neural_closure/` doc is the plan, not a shipped gate). Its claim
  is explicit and tested by R1's transfer gate before it enters the machine.
- **The live-swap (M3) is the largest sim risk** (hot-swapping a box/extents
  change in `cassi_sim.gd`); it is gated after the offline chain (M2) proves
  the physics, and it stays additive (default-off, battery-bit-identical).
- **The false-confirmation floor.** The ~1.3–1.7 ring-anisotropy floor at
  r=13–30 (both levels, φ-box per-axis h spread) is NOT fixed by the machine
  (§2.2's multi-level force does not claim to). Nothing in the ladder
  converts a structural anisotropy into a spurious rung "hit"; the §4 ledger's
  uniform-baseline nulls (δn-scan, log-periodicity calibration) are what
  keep the machine honest against its own floors.

---

## 9. First action

**M1 — the two-level offline chain prototype**, exactly the MESHLESS_PLAN
"small, self-contained, retires the largest risk first" pattern: a Python
(numpy) parent level that condenses (reusing `research/meshless/stage3_collapse.py`),
writes its survey dir with the extended `meta.json` (`level:`, `parent:`),
and a child level that ingests it and runs its own φ-spaced coarse+fine
solve. This is self-contained, reuses the shipped survey/condensation/
falsification machinery unchanged, and proves the parent→child handoff +
level-overlap + r-continuity (M1 acceptance #2/#3) before a single line of
sim code changes. The regression contract is the unchanged G8/G24/G36/G37
gates re-run against the chain.
