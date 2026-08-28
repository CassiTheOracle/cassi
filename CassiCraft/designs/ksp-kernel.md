# The KSP Kernel: Bodies, Vehicles, and Coherence-Injection Rockets

**Question under design:** the **mechanics** of leaving the living world — what
orbitable bodies are, how a vehicle moves through the field, how thrust,
rendezvous, docking, and landing work — as *field operations* on the
meshless/tree frontier, not as Newtonian fixtures bolted onto the block world.

This is the **mechanics half** of the sky. The **phenomenology half** is
[`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — the envelope
you climb out of, the orbit decay and re-entry glow, the softening precession,
the aurora navigation beacons. That doc deliberately does **not** design
vehicles, thrust, or rendezvous; here is where they are designed. The two must
read together: this doc supplies *how* a rocket does field work; the sky doc
supplies *what it feels like* from the ground and from orbit.

The design is field-theoretic end to end: **a rocket is a condensation drive
pointed at the sky** ([`energy-harnessing.md`](./energy-harnessing.md) §5.2),
**spending stored coherence upward** (deep-rung matter as fuel),
and **staging, rendezvous, docking, and collision all happen in the smooth
continuous domain the field uses** — the same river law, the same tree-gravity
arm, the same (1−q) waste law that already steer terrain, mobs, and ore.

The README phase map places this at **Phase 2 — the KSP kernel**, the moment
CassiCraft "becomes a synthetic universe" ([`../README.md`](../README.md)). It
is the **closing document of the corpus**: the last OPEN index slot. It is
Phase 2 *by design*, not Phase 1, and it has **no Phase-1 slice** — its
prerequisites (the tree arm, condensed bodies, the Q4 channel, the sync path)
are the in-progress engine frontier, and this doc contributes the complete
mechanics design that those prerequisites unlock.

**Grounded in** (read-only): the engine shaders
`CassiCosmos/compute/cassi_nbody_gravity.glsl` (river law, RealSim terms,
**tree-river mode 5** — the open-boundary Barnes-Hut tree, its vcap /
reabsorb-sphere safety guard), `CassiCosmos/compute/cassi_two_fluid.glsl` (the
PDE source terms an engine IS), `CassiCosmos/compute/cassi_particle_merge.glsl`
(the merge lineage: order-selective coherence gate, gravitational binding,
subsonic inflow, virial stopping scale), the threading contract
`CassiCosmos/scripts/cassi_physics_engine.gd` (`submit_steps(target, block)`,
`JOB_STEP_CAP = 64`, `TREE_JOB_STEP_CAP = 8`, `readback_snapshot(packed)`, the
movable home-window `_window_center`), and the corpus docs named above. Every
number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived), engine-verbatim, or flagged
**[assumption]** / **[design]** where it extends engine terms to gameplay the
engine does not (yet) drive.

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| Body = ? | A **local condensation the tree arm steers** (not a spawn) — the merge lineage (`dust → object → body/BH`) condensed to a **sparse publish record**; a body is a **capacitor at its rung** (energy-harnessing §3). |
| Vehicle = ? | A **rigid body** (six-DOF + angular) in the continuous domain, **not** a voxel contraption — a vehicle is a **field operation**, an authored coherence-injection device. |
| Thrust = ? | The engine **injects EY** via the PDE **source terms**; the field's gradient pushes back via the **river coupling** = reaction. A **condensation drive pointed at the sky**, spending stored coherence. |
| Thrust-vs-blast | **Controlled organizational discharge = thrust**; **overdraw → full-cascade discharge = explosion** (material-regimes §3/§5, coherence-magic §4.3). A rate/threshold boundary, not a material flag. |
| Orbital mechanics | The **river law + tree-gravity** (mode 5, open boundary) = the orbital field; δv budget in **coherence terms**; orbit decay via RealSim drag below the ceiling; re-entry = the (1−q) glow trail. |
| Docking | **Phase-matching** — match your ship's coherence phase to the target's so the field couples you smoothly (`M` ≈ 1); mismatched phase = `M` ≈ 0 **refusal** (detuned-boundary physics). |
| Sync path | Free-flight = **async**; player-touched (boarding, input-thrust, docking contact) = **sync `block=true`** for that one vehicle's locality, bounded by `JOB_STEP_CAP = 64`. |
| Fuel | **Stored coherence = deep-rung matter**; energy density = rung; the (1−q) glow as the efficiency diagnostic — a wasteful engine glows. |
| Feasibility | **Phase 2**. Prerequisites: tree arm, condensed bodies, Q4 channel, the sync path. This doc contributes the complete mechanics those prerequisites unlock. No Phase-1 slice. |

---

## 1. Bodies — what an orbit exists around

### 1.1 A body is a local condensation the tree arm steers, not a spawn

An orbitable body is **not** a spawned "planet block" a mod places in the sky.
It is the **merge lineage** (`dust → object → body`/BH) already realized in the
engine's condensation scanner and particle-merge passes, propagated to the
scale at which its own gravitational hold shapes the open field. The engine
does the physics intrinsically; the design only layers the *game* on top of
what the law already produces.

The lineage is grounded in `cassi_particle_merge.glsl`:

- **Order-selective coherence gate** — two dust bits merge only when
  `q_sel = q_coh·q_ord > φ⁻² ≈ 0.382` (the canonical φ⁻² merge gate): the
  pair is coherent *and* ordered (a scale-invariant gradient ratio on
  `q_ord`), not merely dense.
- **Gravitational binding** — `½μ|v_rel|²·d < G_eff·m₁m₂` with
  `G_eff = G_N·(1+ξ·q_mid)`: the pair's kinetic energy cannot escape its own
  mutual attraction. This is the same `G_eff` (with `ξ = φ⁶ ≈ 17.94`) the river
  law's chord factor `g = 1 + (φ⁶−1)q` rides on.
- **Subsonic inflow** — only matter moving below the coherence sound speed
  `c_s = h₀/dt` binds (`|v_t| < c_s`): fast infall does not join the growing
  body, it passes through.
- **Virial stopping scale** — a relaxed target (`2K ≥ |W|`,
  self-supporting) **stops accepting infall**: a body at virial equilibrium is
  a coherent, self-supporting structure, and that is the natural end of *its*
  growth. **[design]** "A planet is a body that kept condensing and
  virial-stopping at a larger scale" — the stopped scale is the size at which
  the local field's coherence budget balances its own gravity. This is the
  same lineage line the ecology doc extends one rung up to *organism*
  ([`field-emergent-ecology.md`](./field-emergent-ecology.md) §2.1): "dust →
  object → organism" vs "dust → object → body" are the *same* act at different
  virial-stop scales.

In CassiCraft's meshless/tree frontier this lineage is what makes a body **a
local condensation the tree arm steers** — the README's own claim
("Why the meshless arm is not optional"): bodies exist only on the
open-boundary tree arm because the grid arm is a periodic torus that wraps.
`cassi_nbody_gravity.glsl` mode 5 (`TREE-RIVER`) replaces the spectral-Poisson
river chain with an open-boundary Barnes-Hut tree over the moving-Voronoi
sites, applying the river law's per-target prefactor to the tree walk's output:

```
a = −G_N·(π/ρ)·∇Φ_g,   with ∇Φ_g from the tree walk,  (π/ρ) = clamp(·, 0, 0.72)
```

So a body is, in **both** the topology sense and the force sense, a local
condensation the tree arm steers: it is a site in the tree that contributes
`w_s = m_s·g_s` weight to the walk, and the `∇Φ_g` every other particle and
vehicle feels around it comes from that condensation's own extended field.

### 1.2 Bodies are sparse, small publish records — a capacitor at its rung

A body does **not** need to live in the dense grid. `async-field-domain.md`
§2.2 already specifies **condensed bodies as "a sparse, small array (tens to
hundreds at Phase 1 scale), dominated by the merge record buffers"** — separate
from the 262,144-cell dense grid, so the sampler does not walk the grid to
find `n` moving objects. Adopted unchanged:

| Publish aspect | Value | Engine source |
|---|---|---|
| Channel | **Condensed bodies** | the merge chain (`particle_merge`, `dust → object → BH`); `pos[].w` carries mass/death |
| Count | **sparse** — tens to hundreds at Phase-1 scale | async §2.2 |
| Size | ~KB (fp16-packed halves the body/site arrays) | async §2.3 |
| Load | body records ride the body/site buffer, not the grid | async §2.2 |

Because a body is a publish record, not terrain, **its atmosphere envelope is a
property of that body's field, not the window's** (atmosphere doc §2.4): a
distant moon or planet you approach carries its own hydrostatic shell, sampled
locally from its own field structure, and only that local sample is rendered.

**A body is a capacitor at its rung** ([`energy-harnessing.md`](./energy-harnessing.md)
§1.5, §3). The merge lineage's ordered matter *is* stored coherence: a body is
a volume of deep-rung ordered matter, and its capacity is the stored coherence
of that rung's ordering. This is load-bearing for the whole KSP economy —
**the gravitational well an orbit rides and the fuel a rocket burns are the
same substance** (a body's deep-rung coherence), which is exactly why a rocket
can spend *stored coherence* to climb *that well* (§3).

### 1.3 Body scale/ranges at Phase 2

The canonical numbers constrain what "a body" can be on the meshless frontier:

- **Phase-1/2 box**: the chunk-aligned `(1,1,1)·192³ m / 12³-chunk` box
  (`chunk-field-quantization.md` §1.2), `64³ = 3 m` whole cells, `dt = 0.05`
  (one field step per Minecraft tick). The box *re-homes* via the movable
  home-window (`_window_center`, `bh[0].yzw` — `async-field-domain.md` §7 Q1's
  open sub-question; engine supports the seam, policy unsettled).
- **Tree body scale**: a body is a tree site; its softening (`eps2`, the
  Plummer softening `a = bh[2].x`; the globally-softened
  `G_N⟨c−p⟩/(|c−p|²+ε²)^{3/2}` form) means **close orbits are smooth, no
  point-mass singularity at periapsis** (atmosphere doc §2.3). **[assumption]**
  The *in-game* body size and softening are Phase-2 measurements — the theory's
  own pulsar softening bound (`σ < 370 km`) is galactic, not the box scale; the
  qualitative behavior (softened, non-Newtonian-precessing orbits) is the
  designed feel even before the number sits.

**A body emerges from the field; it is not spawned.** The player does not
"place a planet." A body is a condensation that crossed the merge lineage's
gates and virial-stopped — a thing the field organized. Spawning would be a
different system; the design **forbids** it because a spawned body would not be
a capacitor at its rung (it would carry no stored coherence, no merge history,
no envelope with a pressure-bearing field — and the atmosphere critique of
`phi_attractor_synthesis.md` §4 applies: an empty ghost box does not grow a
standing atmosphere; only a *condensed, pressure-bearing* body does).

**Why a planet is the same lineage as an organism** (ecology §2.1): both are
self-supporting coherence structures that crossed the merge gates and
virial-stopped. The organism stops at a scale where it is a moving, steered
coherence store; the planet stops at a scale where its own hold dominates the
local field. **One lineage, two virial-stop scales** — the honest answer to
"is a body physics or biology": neither; both are the same condensation law
looked at from different stopped scales.

---

## 2. Vehicles — rigid bodies as field operations

### 2.1 The vehicle is a field operation, not a voxel contraption

A vehicle is **not** a machine-gun assembly of blocks with a "thrust" flag.
`async-field-domain.md` §3.4 already names the representation: vehicles are
**rigid bodies (six-DOF + angular) integrated by the sampler against the local
pot gradient and field values** — a larger state on the same steering path
mob/item drift uses, not a new physics class. The vehicle's motion is:
continuous (a smooth rigid body in the smooth domain), field-steered (the river
law is the only movement law), and **not quantized to voxels** — the vessel has
no block-internal behavior; it reads and perturbs the field.

The reason for "not a voxel contraption" is architectural, not stylistic. A
voxel vehicle would have to be re-integrated against the *coarse 1 m gameplay
grid* (`chunk-field-quantization.md` §1.4's collision/inventory layer), which is
precisely the expensive dual-world tail the corpus keeps downstream. A rigid
body on the continuous domain rides the same `∇(g·Φ)`, `ρ`, `q`, `ε²` publish
every entity already samples, at the ≈ 40 ns/entity steering cost
(`chunk-field-quantization.md` §4.2). **The vehicle is a field operation**: it
is a moving coherence structure (a ship is "a bigger moving coherence store" —
the ecology doc's creatures are the small case), a body the field steers and
the player tunes.

### 2.2 The coherence-injection rocket

The thrust engine **is** the PDE's source terms. `cassi_two_fluid.glsl` gives
the organized-perturbation injection `source_ey` exactly:

```
ey_new = ey_old + vx_new·dt + source_ey(i,j,k)·dt²
source_ey → s·exp(−4r²) + ρ·0.001   (a Gaussian organized-perturbation seed)
```

A rocket engine injects **EY (Yang) — organized perturbation** into the field
at its nozzle, exactly as a fire front does (`material-regimes.md` §3
combustion "injects EY through the source terms") and exactly as a channeling
player does (`coherence-magic.md` §1 "a bounded EY injector"). The engine is
therefore a **condensation drive pointed at the sky** (`energy-harnessing.md`
§5.2), and the reaction is the **river coupling**: the injected EY raises local
ρ and gradients the field; the field pushes back along its own `∇(g·Φ)` well in
the direction *opposite* the injection. There is no Newtonian action-reaction
law bolted on — thrust is the field's gradient pushing against the
coherence-injection device that perturbed it.

Concretely, the coupling chain (all engine-real):

| Step | Field quantity | Grounding |
|---|---|---|
| Burn fuel (release stored coherence) | withdrawal of deep-rung matter → controlled **EY source** into the PDE | energy-harnessing §2.5 (§3 storage); material-regimes §5 |
| Inject organized perturbation | `source_ey` Gaussian seed, `s·exp(−4r²)` at the nozzle | `cassi_two_fluid.glsl` `source_ey` |
| Thrust = reaction | the injected EY raises local ρ / perturbs `∇(g·Φ)`; the river law's field pressure pushes the vehicle along the gradient | river law `a = −G_N·(π/ρ)·∇(g·Φ)`; the "field's gradient pushes back" (README) |
| Direction | the well is steered "at the sky" by nozzle orientation — the condensation drive faces up | energy-harnessing §5.2; [design] nozzle = orientation of the injection volume |

**[assumption]** The engine's `source_strength` is a global PC constant; a
*directionally localized, vehicle-attached* injection (the nozzle) is the
sampler's Q4 job-dict input (a per-op source record `{op, worldPos, rung,
magnitude, sustain}` — `coherence-magic.md` §5.1, `custom-blocks.md` §2), not
an engine term today. The *mechanism* (organized perturbation → river reaction)
is engine-real; the *vehicle-attached placement* is the finite input that turns
`source_ey` into a thruster.

### 2.3 Thrust vs blast — the controlled/full-cascade boundary

The thrust-vs-blast boundary is **the fire-vs-explosive rate boundary** of
`material-regimes.md` §3/§5, adopted verbatim and applied to a vehicle:

- **Controlled organizational discharge = thrust (fuel).** The engine releases
  stored coherence at a rate the field can re-lock (`ω₀²` restoration feeds the
  drain); the injection stays *organized*, the vehicle gains coherent
  acceleration, and the waste is a modest (1−q) glow.
- **Full-cascade discharge = blast (explosion).** Overdrawing thrust — pulling
  more coherence out of the reservoir than the field can re-lock (`ω₀²`
  restoration can no longer feed the drain) — tips the injection from
  organized to *random* perturbation; the φ-lock fails (`EY − φ·EI` runs away),
  and the accumulated ε² relaxes **in one organized-front release**, an
  explosive shock (a steep `∇(g·Φ)` + a `c_s`-traveling coherence impulse).
  This is exactly `coherence-magic.md` §4.3's overdraw trigger and
  `material-regimes.md`'s explosive pathway (§3: "stored coherence released by
  perturbation", the full-cascade collapse).

**The boundary is a rate/threshold ratio, not a material flag.**
`material-regimes.md` §3(a) and `coherence-magic.md` §4.3 fix the same
two-way: overdraw = organized perturbation exceeds the field's organization
capacity and collapses to a random-perturbation discharge. For a rocket this
means **throttle is a coherence-rate control, not a fuel-flow control**: the
engine's permitted thrust is bounded by the local field's re-lock rate, and a
player who forces more thrust than the medium can organize *and* whose fuel is
deep-rung explosive-primed matter gets the blast. This is the single mechanical
check on the KSP loop's central temptation — **a rocket is a controlled bomb**
in the most literal sense, and overdrawing it is the blast.

**Consequence for fuel choice:** fuel = stored coherence, and deep-rung matter
is *harder to ignite* (*controlledly*) because its coherence is better locked
(`material-regimes.md` §5: "deep-rung matter is harder to ignite, so fuel isn't
simply 'more rung = more fuel'; it's the regime where controlled release is
achievable"). Fuel is the *blend* — shallow-rung matter releases controllably,
deep-rung matter stores densely but must be metered or it detonates. The KSP
design inherits this tension: **high-specific-impulse fuel (deep rung) is
high-blast-risk; the throttle discipline is the safety.**

### 2.4 Staging in field terms — a stage is a rung of the propulsion cascade

Staging is not "drop a heavier tank." In cascade language
(`coherence-technologies.md` concept 5, the ~10-rung bridge limit of
`cascade-infrastructure.md` §1.1 carried only by `custom-blocks.md` §2), a
**single coherence source can reach only a limited window of local field
scale** — roughly `φ⁻¹⁰ ≈ 0.008` attenuation past ~10 rungs
(`coherence-technologies.md` §5a). To climb a deep well you must *chain*: each
stage anchors q at its own scale and passes the integrated organization upward.

**[design]** A **stage** of a CassiCraft rocket is **one rung of the propulsion
cascade** — a coherence-injection unit tuned to a specific organization scale.
The first (low) stage injects shallow-rung coherence (high, cheap controlled
release — the "gas" of the rocket), climbing the envelope where drag is dense
and the field can re-lock fast. Successive stages inject deeper-rung coherence,
each reaching a higher altitude band because the re-lock rate the medium can
sustain thins as you climb. The stage *drops* when its rung's coherence source
is spent — releasing the spent capacitor (a deep-rung matter is a capacitor at
its rung, §1.2) back to the field. Staging is thus **the ~10-rung bridge limit
made mechanical**: no single engine spans the ground-to-orbit coherence range,
so you stage up the cascade exactly as the theory's gate chains stage up. This
is the design's one deliberate inheritance from `coherence-technologies.md`
concept 5, whose staging language otherwise lives in `custom-blocks.md` §2.

---

## 3. Thrust, orbital mechanics, and the KSP loop

### 3.1 The orbital field is the river law + tree gravity

The orbit a vehicle rides is **the open-boundary field of the tree arm**, not a
Newtonian gravity model. The orbital acceleration is the river law of mode 5:

```
a = −G_N·(π/ρ)·∇Φ_g    (tree walk's ∇Φ_g;  π/ρ = the target's Yang fraction)
```

Two consequences the feel doc already states and this doc operationalizes:

- **π/ρ is per-target.** The "gravitational constant" an orbit feels is scaled
  by the *vehicle's* own Yang fraction, `π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)`.
  A vehicle that runs decohered (low `π/ρ`) couples weakly to the well — it
  falls more slowly and is easier to push out of orbit. This is the field's
  built-in handle for *inertial damping* (`coherence-technologies.md` concept 2:
  suppressing `π/ρ` lightens mass — paid continuously, `r → 1`, `Q → 0`). The
  KSP kernel uses this as the **mass-lightening** throttle: a ship that holds
  low `π/ρ` "rides light" and needs less δv (but pays the (1−q) waste of the
  hold). §6(e) flags this as a determinism-critical coupling to audit.
- **The softening wandering is the orbit's clock, not a bug.** The tree/BH
  softening gives the non-Newtonian retrograde per-orbit precession
  (`Δφ = −√(2π)(σ/a)³(1+e²/4)/(1−e²)³`), growing `(σ/a)³` and diverging toward
  high eccentricity (atmosphere doc §2.3). **Orbits wander and re-form their
  ellipses over many orbits** — which is exactly the *feel* (alive, not
  clockwork) and the *mechanics constraint*: rendezvous is not "match a
  Keplerian orbit," it is approach-and-phase-match against a drifting, softened
  well (§3.4).

### 3.2 The δv budget is a coherence budget, and the glow is the efficiency read

KSP's δv is spent rocket fuel. Here **δv is spent stored coherence**, so the
δv budget is a **coherence withdrawable from deep-rung matter**, and the
efficiency diagnostic is the **`(1−q)` glow**:

- **Energy density = rung.** Deeper-rung fuel releases more coherence per unit
  matter (`energy-harnessing.md` §1.5, §3), so it delivers more δv per tank for
  the same stored volume.
- **A wasteful engine glows.** Every field operation bleeds
  `E_waste = (1−q)·E_throughput` as visible glow (`material-regimes.md` §3a;
  `energy-harnessing.md` §2; `qi-bubble-propulsion.md` §2.5). A rocket running
  at partial coherence (a mis-set throttle, a near-blast discharge, a poorly
  phase-matched burn) wastes the `(1−q)` fraction **as a bright visible trail**
  (the same sky glow the atmosphere doc's re-entry trail is). **The player
  reads engine efficiency directly in the exhaust's glow** — a bright, glowing
  rocket is a wasteful one, exactly the `coherence-technologies.md` §4c reading
  applied to a thruster.
- **The envelope is where δv bleeds.** Below the ceiling the atmosphere's gas
  regime is live and the three RealSim drag terms bleed orbital energy
  (`a_drag = −γ·(ρ_local/ρ_ref)·v`, viscosity shear, friction — §1.5 of the
  atmosphere doc; `material-regimes.md` §3). **Orbit decay is RealSim drag
  below the ceiling**, and **re-entry is the (1−q) glow turned to the sky** (a
  descending, decelerating body runs at less than full coherence against the
  medium it tears through, glows brighter as `ρ_local` rises — atmosphere doc
  §2.3). To *stay up* you must hold altitude above the ceiling where the drag
  terms coast; the KSP loop's job is to manage that decay with injected
  coherence.

### 3.3 The loop: launch → orbit → rendezvous/docking → landing

**Launch — climb the envelope's ρ gradient, drag then coast.** The rocket
crews against the γ/ν/μ terms; each stage (§2.4) lifts the vehicle up the `ρ`
gradient against envelope drag until it clears the gas floor (the Kármán-line
analog, atmosphere doc §1.4) and *coasts in near-vacuum* where the drag terms
vanish. The ascent reads as *the transition from fighting drag to coasting*,
because that is exactly what the field's drag floor does.

**Orbit — single-anchor stability via anchor-to-body.** The seam decision is
the atmosphere doc's **anchor-to-body recommendation**, adopted as ownership
shared with the async seam:
> an orbited body *becomes the anchor* (the window re-homes to the followed
> body), making "orbiting a body" a *local, single-anchor* problem (the
> followed body = the home window's center) rather than a two-anchor one
> (atmosphere doc §2.4; `async-field-domain.md` §7 Q1).

The engine already supports the seam: `_window_center` / `bh[0].yzw` is
shipped per job, updated per job from the sim's slow-cadence COM tracker. In KSP
terms, once the player enters a body-orbit, the **followed body becomes the
home-window center** and the orbit is a stable single-anchor orbit. This is the
one relocation-policy decision the KSP kernel owns together with the async seam
(§6(b)). From inside it, "the sky is stable and the world is the thing that
moves" (atmosphere doc §2.4) — which is what makes orbit a usable gameplay
state rather than a fight against the box.

**Rendezvous/docking — phase-matching.** §3.4, below.

**Landing/return — re-condensing into the envelope.** Re-entry is the glow
trail (§3.2); touchdown is **re-condensing into the envelope** — the vehicle
descends through the gas floor into the region where `ρ ≥ θ_c` condenses the
terrain, its motion transitioning from orbital (tree-river, near-coast) to
atmospheric (RealSim drag), then grounding against the condensation threshold.
There is no separate "landing physics"; the vehicle rides the same
`ρ`-gradient it climbed on launch, reversed, and the touchdown is where the
field it descended through has enough organized matter to hold it.

### 3.4 Docking = phase-matching (the Cassi-native mechanic)

Rendezvous/docking is the design's most novel piece and the one that makes the
KSP loop *field-native* instead of Newtonian. It uses the theory's
**phase-matching factor `M`** — the factor deciding whether a perturbation can
couple to a target — made a *docking mechanic*.

**The physics.** `coherence-technologies.md` concept 3 (the φ-detuned boundary)
summarizes the documented framework property: the phase-matching factor `M`
between a perturbation and a target decides whether the perturbation can couple
— random attack is `M ≈ 0` and cascade-suppressed; organized, phase-matched
attack is `O(1)` per interaction (`CassiTheory/foundations/quantum-measurement-derivation.md`
§3.1; `qi-bubble-propulsion.md` §2.2). A **φ-detuned boundary** is a surface
held at a private phase offset so any incoming perturbation lacking that phase
finds `M ≈ 0` and *cannot transfer momentum across it* — it converts organized
kinetic energy smoothly to diffuse heat (a flush of glow) instead of coupling.

**[design] — Docking is phase-matching, and a mis-matched approach is
refused, not bounced.** A ship is a coherence-injection device with a *coherence
phase* (the phase of its own EY injection rhythm, set by the resonance
`ω₀²`-aligned channeling of §2.2 — the local field's oscillation the injection
should match, `coherence-magic.md` §3.1). A target (a space station, another
ship, a body's docking node built on a detuned-boundary skin:
`coherence-technologies.md` concept 3) holds its own phase. Docking succeeds
when the ship **matches its injection phase to the target's** so `M ≈ 1` and
the field couples them smoothly — a gentle, coherent capture. Mismatched phase
(`M ≈ 0`) means the target **refuses**: the approach converts to diffuse
heat/glow instead of coupling, the ship slides off rather than being absorbed,
exactly the detuned-boundary refusal of concept 3.

**Why this is the honest mechanic, not a toy:**
- **It is the theory's own coupling criterion.** There is no separate
  "docking magnet." The `M` between the ship's perturbation and the target's
  boundary is the real quantity that decides whether organized coherence can
  transfer across a surface, and docking is the smooth-coupling limit of it.
- **It gives the KSP loop an information game.** Matching phase is not a
  timing minigame bolted on — it is reading the target's phase (via a probe,
  `coherence-technologies.md` concept 3's "must sweep the phase before you can
  couple") and aligning your engine's injection rhythm to it. The *reward* for
  a clean auto-match is a smooth capture; the *error* is a refused, glowing
  approach (the `(1−q)` heat flush).
- **It composes with the sync path** (§4): docking contact is a
  player-touched, outcome-critical event, so it goes through the synchronous
  `block=true` path — the field must give the *specific, instant* answer to
  "did the phase match?" at the moment of contact.

**[design]** The *tool* the ship uses to read a target's phase is the
**coherence reader in space** (§5.1) — the same published-q probe the ground uses,
pointed at the target to reveal its phase so the ship can match it. There is no
"docking HUD number"; there is the field's phase made readable, and the player
aligns the engine to it.

---

## 4. The sync-path contract

### 4.1 Two fidelity loops, adopted from the async seam

`async-field-domain.md` §4 already defines the two fidelity paths; the KSP
kernel is the **second** loop's primary consumer:

| Situation | Loop | §4 reference |
|---|---|---|
| Free-flight vehicles (no player), terrain, mobs, items | **async** (`submit_steps(block=false)`) | async §4.1 |
| Player boards a vehicle / thrusts under input / docking contact | **sync** (`block=true`) for that one vehicle's locality | async §4.2 |

**Async free-flight:** the sampler integrates a free-flying vehicle at its own
fixed sub-step from the freshest publish, emitting continuous vehicle intent
(§3.4 of `async-field-domain.md`) — the same path as mob steering, just a larger
six-DOF state. Non-blocking by construction: the server tick never waits on it.

**Sync player-touched:`** boarding, thrusting under live input, and docking
contact fire `submit_steps(target, block=true)` for *that one vehicle's
locality.* The synchronous path returns the **fresh publish** for that job
(`_wait_executed` blocks until a publish with `executed >= target`), stalling a
few ticks for a physics answer the player directly feels. **Guardrail:** this
path is allowed only for a bounded locality — **one vehicle / one player**,
gated to rarely fire, and the server blocks only as long as the per-job cap
dictates.

### 4.2 The bounds (canonical numbers)

- **`JOB_STEP_CAP = 64`** — a coalesced backlog drains over many short
  bounded-slice jobs; one sync `block=true` job is `≤ 0.25 s` (a hitch, not a
  freeze), per the engine's perf-decomp note (`cassi_physics_engine.gd:66`).
  The sync contact's locality is *bounded to the vehicle's own neighborhood*, so
  the stall is a short local-slice answer, not a monster chain.
- **`TREE_JOB_STEP_CAP = 8`** — a tree-cadence job's step budget is capped so
  the tree staging readbacks drain a short queue. A vehicle in dock/contact
  *under the tree arm* (mode 5) hits the tighter cap: docking phase-matching is
  a tree-context operation and its synchronous publish is bounded by
  `TREE_JOB_STEP_CAP = 8`.
- **Entity budget:** per-entity steering ≈ 40 ns
  (`chunk-field-quantization.md` §4.2), cap ≈ **~2,000 steered entities**
  (§7 Q4). Bodies and vehicles are **few, meaningful** — they are the largest,
  most expensive steered states, budgeted jointly (§6(c)).

### 4.3 The Q4 channel for vehicle intents

Vehicle operations (throttle, boarding, docking-match, fuel-withdrawal) are
**Q4 player-return inputs** (`async-field-domain.md` §7 Q4) —
job-dict records `{op, worldPos, rung, magnitude, sustain}` pushed by the
sampler into the *next* `submit_steps`, never by the vehicle touching physics
state. The single-writer rule is preserved: the world-writer applies vehicle
orientation/position through the normal server tick; the domain absorbs the
throttle-injection as a source input and the docking-match as a phase record,
exactly as `coherence-magic.md` §5.1 and `custom-blocks.md` §2 already prescribe
the channel for channeling and material-authoring. **[assumption]** The throttle
`magnitude` is the `source_strength` dial; the docking-match is the target's
phase offset (the detuned-boundary free parameter, §3.4). Bounded by the §6
no-free-energy cap: **no vehicle conversion yields more than it sinks**
(`energy-harnessing.md` §6), so thrust amplitude is capped at the field's
re-lock rate (the thrust-vs-blast boundary, §2.3).

### 4.4 The anchor-to-body owned by the seam

Adopted from the atmosphere doc (§2.4, §5 gate (d)) and owned jointly with the
async seam: **anchor-to-body** (the followed body becomes the home-window
center) makes an orbit single-anchor. This is a **relocation-policy decision**
the KSP kernel and async seam must both own — the engine's `_window_center`
supports the re-home; the *policy* (when the anchor flips to a body, how it
flips back on landing) is a §6(b) gate. §4 lives under the sync contract because
the anchor relocation is itself a player-touched, outcome-critical event (the
moment you enter orbit the window re-homes) — it belongs in the synchronous
path's purview.

---

## 5. Player-facing — field engineering from the ground to orbit

### 5.1 Building a rocket as field engineering

A rocket is **an authored coherence-injection device**, and it rides the same
authoring surface as a custom block. `custom-blocks.md` §1 defines a material as
a regime tuple `(ξ, ω₀², θ_c, n)`; a ship is **the same tuple realized as a
device** — the player dials its coupling constants like a regime:

| Ship parameter | Regime dial | Field meaning |
|---|---|---|
| Hull | `ω₀²` (resonance) | how fast the field re-locks around the ship → blast-resistance (thrust-vs-blast ceiling), conduction of the injection |
| Mass | `ξ` (chord coupling) | how hard the well couples → heavier/heavier-attractive, or lightened (`π/ρ` suppression for inertial damping, concept 2) |
| Nozzle | `θ_c` (condensation threshold) + `n` (rung) | which rung's coherence the thruster releases — shallow (cheap, low δv) vs deep (high δv, high blast risk, §2.3) |
| Fuel | deep-rung matter | **stored coherence** (energy-harnessing §3); its rung sets the specific impulse |

Because this is the custom-blocks authoring pattern, **building a rocket *is*
lab work**: the material lab of `custom-blocks.md` §2 (a Q4 channeling surface)
is the natural place to author the ship's regime — dial the constants, see the
predicted signature (thrust curve, glow, blast threshold) run in the small
bounded-lab patch, then realize it. The ship does not come from a crafting
recipe; it comes from **authoring a boundary condition the law then fulfills**,
exactly `custom-blocks.md`'s thesis. The found-vs-invented economy maps over: a
deep-rung fuel blend or a high-`ω₀²` hull is *invented* (expensive, vent-risky)
or *found* (read-only, bounded by what the field has precipitated).

### 5.2 Instruments — reading the field from orbit

The **coherence reader** (`coherence-magic.md` §2, Sense) is the Phase-1
deliverable; from orbit it is the flight instrument. It renders the same
published `q`, `ε²`, `∇(g·Φ)` over the vehicle — and, critically, **the
`∇(g·Φ)` / `pot` channels are the spacecraft's navigation system**:

- **Δv / orbit state** — the sampler integrates the vehicle against `pot` /
  `∇(g·Φ)` (async §3.4: "integrated against the local pot gradient"); the reader
  shows the well's shape and the vehicle's position in it, replacing KSP's
  map-projection with a field-magnetometer read.
- **Engine efficiency** — the `(1−q)` glow is the live throttle diagnostic
  (§3.2); a wasteful burn reads as a bright plume.
- **Docking target phase** — reading the target's `q` reveals its phase so the
  player can align the engine to it (§3.4) — the probe interaction of the
  detuned boundary (concept 3).

**The auroras are navigation beacons** — adopted from the sky doc (§3): a
coherence discharge at a body's field-line concentrations marks a drain (and a
deep-rung harvest site); a bright, stationary polar discharge and a band at the
envelope top are the readable field structure a pilot uses to orient over the
body. An aurora is not decoration — it is the body's field state, legible at
range, and thus the KSP equivalent of a landmark.

### 5.3 The sky as the boundary layer

The sky is the **boundary layer between the living world and the KSP
universe** (atmosphere doc §4): one `ρ/ε²/q` story from ground to orbit. For the
player this means the launch is not a mode-switch — it is climbing the same
envelope they breathe, past the wind lines, through the ceiling into the vacuum.
The vehicle's instruments, the ground's reader, and the auroral beacons all
render the same channels; **there is one sky because there is one field, and
flying is reading it at a different altitude.**

---

## 6. Honest gates

**(a) The tree arm is the in-progress engine frontier.** The KSP kernel lands
**only when the meshless/tree work and the condensation lineage land.** The
README is explicit: the meshless + tree frontier is the in-progress engine arm
that makes open-boundary orbits possible at all; a body is a local condensation
the tree arm steers (§1.1), which requires the mode-5 arm (tree build + walk
over the moving-Voronoi sites — `TREE_JOB_STEP_CAP=8` bounded, tree-in-list) and
the condensation/merge lineage to be live. Gate **(a) = this dependency is
stated and absolute**: no tree arm, no bodies, no orbits, no KSP kernel. Nothing
in this document is Phase-1; it is the mechanics the prerequisites unlock.

**(b) Two-body stability under a moving anchor.** The seam question
(`async-field-domain.md` §7 Q1; atmosphere doc gate (d)): an orbited body is a
local condensation steered by the tree arm, but the home window is *also*
player-anchored. Two anchors fight. The design **recommends anchor-to-body**
(the followed body becomes the home-window center → single-anchor orbit),
but that is a **relocation-policy decision the async seam must own too** — how
the window re-homes, when the anchor flips to a body, how it flips back on
landing, and whether the tree's `∇Φ_g` remains stable through the re-home
(right now the tree walk reads site positions; a teleporting anchor shifts the
perceived well). Gate: pre-register a Phase-2 probe — enter a body-orbit with
anchor-to-body and measure orbital stability against a drifting
`_window_center` over many field-steps.

**(c) Body/vehicle budgets within the ≈ 2,000-entity cap.** Bodies and vehicles
are the largest steered states; the cap ≈ 2,000 steered entities
(`chunk-field-quantization.md` §7 Q4) is shared. The design's discipline: bodies
are **few, meaningful** (the merge lineage's virial stop keeps body count
sparse — tens to hundreds at Phase-1/2 scale, async §2.2) and vehicles are
**at most a handful per active window** (sync-path scope, §4.1). The dense
morphological sky (field soup, auroras) is free to render from the publish; only
*bodies* and *steered vehicles* are budgeted. Gate: budget bodies + vehicles
jointly against the cap; a body/vehicle-heavy region cannot exceed it.

**(d) Sync-path cost bounded.** A player-touched sync `block=true` must be
bounded: **one vehicle's locality**, `JOB_STEP_CAP = 64` (≤ 0.25 s), and
`TREE_JOB_STEP_CAP = 8` when the vehicle is under the tree arm / in dock contact
(§4.2). Gate: measure a worst-case dock-contact + re-home sync stall against the
stated cap; it must be a hitch, not a freeze. The world's *continuous* state is
never read synchronously — only the specific player-touched outcome (async
seam §4.2).

**(e) Determinism of vehicle physics vs the async domain.** The engine's
bit-identical-contract discipline (the two-fluid shader's determinism fix, the
"bit-identical battery" language) sets the standard; vehicle physics must match
to a defined tolerance whether read on the async free-flight loop or the sync
contact loop (the async seam's Q6 parity question). Two specific sub-gates:
(i) the mode-5 safety guard (the `vcap = 120·emax` velocity cap and the
`R_safe = 1e4·emax` reabsorb sphere, `cassi_nbody_gravity.glsl` lines 850-863)
must never trip on a legitimate orbit — vehicles cannot approach a body so
closely that the guard's hard reabsorb kicks in; and (ii) the `π/ρ`-weighted
mass-lightening (§3.1) is a *continuous field read* — its determinism across
the async/sync boundary is a Phase-2 measure, since an inertial-damped vehicle
("rides light") couples differently to the well on the two loops.

---

## 7. Feasibility verdict

**This is Phase 2, and it is the closing document of the corpus.** By the
README's phase map, the KSP kernel is the Phase-2 deliverable ("the moment it
becomes a synthetic universe"); it has **no Phase-1 slice** — everything
mechanical above is gated on the in-progress engine frontier. The prerequisites
are stated plainly:

- **the meshless/tree arm** (mode-5 open-boundary gravity over the
  moving-Voronoi sites — the thing that makes open-boundary orbits possible);
- **condensed bodies** (the merge lineage live enough to produce sparse,
  virial-stopped body records the sampler reads without walking the grid);
- **the Q4 player-return channel** (vehicle intents, throttle, docking-match —
  the same channel `coherence-magic`, `energy-harnessing`, and `custom-blocks`
  already build on);
- **the synchronous path** (`submit_steps(block=true)`, `JOB_STEP_CAP`,
  `TREE_JOB_STEP_CAP` — already engine-real, adopted here).

**What this document contributes now** is the **complete mechanics design those
prerequisites unlock**: bodies as tree-steered local condensations (capacitors
at their rung), vehicles as rigid-body field operations, thrust as
`source_ey`-injected organized perturbation with the field's river gradient as
the reaction, the thrust-vs-blast rate boundary, cascade staging, the
coherence-budget δv loop, phase-matching docking, the sync-path contract with
its bounds, and the player-facing field-engineering surface. None of it is
engine-invented; all of it is engine-real physics composed into the KSP loop.

**Binding risks, in order:** (a) the tree arm + condensation lineage landing
(the absolute dependency), (b) two-body stability under anchor-to-body (the
seam decision owned with the async seam), (d) sync-path cost bounded, (e)
vehicle determinism across the two loops. The architecture is sound because the
collapse is real: **a rocket is a condensation drive pointed at the sky,
spending stored coherence upward, riding the same river law and (1−q) glow that
steer the ground** — there is no separate space-physics; there is the one
two-fluid field, and leaving the living world is climbing its envelope.

---

## Cross-references

- [`../README.md`](../README.md) — vision; the phase map (KSP = Phase 2); "Why the meshless arm is not optional" (the tree frontier this doc's bodies/orbits live on). **This doc closes the index's final `(next)` slot.**
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — **the phenomenology half** (this doc is the mechanics): the envelope, orbit decay via RealSim drag, re-entry glow, softening precession, auroras as beacons, and the **anchor-to-body recommendation adopted here**.
- [`async-field-domain.md`](./async-field-domain.md) — **the seam**: `submit_steps(block)` sync/async loops, `JOB_STEP_CAP`/`TREE_JOB_STEP_CAP`, the sparse body publish, the Q4 player-return channel, the movable home-window (Q1 — gate (b)'s anchor-to-body rides here).
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — the 192³/12³ box, per-entity steering ≈ 40 ns / ≈ 2,000 cap, the ≈ 6 MiB publish, the river-law entity steering.
- [`material-regimes.md`](./material-regimes.md) — the gas regime and RealSim terms (atmospheric drag), the **fire-vs-explosive rate = thrust-vs-blast boundary**, hardness/fuel = rung.
- [`energy-harnessing.md`](./energy-harnessing.md) — deep-rung matter = fuel/storage; the rocket as a condensation drive (§5.2 "spends stored coherence upward"); the (1−q) glow; the §6 no-free-energy discipline (thrust amplitude cap).
- [`coherence-magic.md`](./coherence-magic.md) — the player as coherence source; the ε² vent; **overdraw → full-cascade discharge** (the rocket's blast boundary, §4.3); the coherence reader (the space instrument, §2).
- [`custom-blocks.md`](./custom-blocks.md) — authoring = regime tuples; the material lab; **a rocket as an authored coherence-injection device on the same surface**.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers (cited, not re-derived).
- [`coherence-technologies.md`](./coherence-technologies.md) — concept 2 (the gravity dial / condenser — the mass-lightening throttle), concept 3 (the φ-detuned boundary / phase-matching `M` — the docking mechanic), concept 5 (cascade staging — the ~10-rung bridge limit behind rocket staging).
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — creatures as moving coherence stores (a ship is a bigger one); the merge lineage one rung up to organism (a planet is the same lineage at a larger virial stop).
- Engine (read-only): `CassiCosmos/compute/cassi_nbody_gravity.glsl` (river law, RealSim, **tree-river mode 5** + its safety guard), `CassiCosmos/compute/cassi_two_fluid.glsl` (PDE source terms — the thrust engine), `CassiCosmos/compute/cassi_particle_merge.glsl` (the merge lineage gates), `CassiCosmos/scripts/cassi_physics_engine.gd` (threading contract, `JOB_STEP_CAP`, `TREE_JOB_STEP_CAP`, `readback_snapshot(packed)`, `_window_center`).
