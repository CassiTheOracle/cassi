# Field-Emergent Ecology: Mobs as Precipitates of the Field

**Question under design:** how the *living things* of CassiCraft come to be. In vanilla
Minecraft a mob is an entry in a spawn table with a wired behavior: an idle AI, a
noise walk, a hostile-flag latch. CassiCraft's thesis is that blocks, mobs, and
planets are *epiphenomena of one field* (README). This document designs the
ecology arm: creatures are **not spawned from a mob table** — they are the field's
own living synthesis, transient coherence structures that crossed a persistence
threshold and condensed into bodies.

The design is grounded in an **observed phenomenon** from the CassiCosmos physics
engine: a *collisionless* particle cloud (organized only by the river law + the
two-fluid PDE) continually shifts through multi-layer shapes whose silhouettes
resemble living things. This is the seed. This document designs *around* that
observation, and explicitly puts it forward as a **pre-registered Phase-1 probe**
to verify — not as engine-verbatim fact.

Companion to:
- [`../README.md`](../README.md) — Phase 3 "Field-emergent ecology"; the thesis that
  one law produces blocks, mobs, and planets.
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — entity steering by
  the river law, §2.2 mob spawning "where q is in a coherent band and ε² low",
  per-entity ≈ 40 ns, Phase-1 cap ≈ 2,000 steered entities, §6 required snapshot
  extension (∇(g·Φ) publish).
- [`coherence-magic.md`](./coherence-magic.md) — the player as a coherence source;
  the coherence reader (Sense); the ε² vent; overdraw → full-cascade discharge.
- [`energy-harnessing.md`](./energy-harnessing.md) — deep-rung matter = stored
  coherence; the `(1−q)` waste law as the visible glow; anti-corruption; the §6
  no-free-energy cap.
- [`material-regimes.md`](./material-regimes.md) — materials as field regimes;
  hardness = rung; the fire-vs-explosive discharge rate; the merge lineage.
- [`custom-blocks.md`](./custom-blocks.md) — authoring = regime tuples; the material
  lab; the found-vs-invented economy (the species-authoring parallel).
- [`coherence-technologies.md`](./coherence-technologies.md) — concept 4 (coherent
  materials), concept 5 (cascade staging).

Theory grounding (CassiTheory — read-only, cited by relative path):
- `CassiTheory/speculations/creative-extensions/universal-biology.md` — the cascade
  ladder as a convergent biological scaffold; **life as rung-bounded phenomena**;
  morphology constrained by the φ-attractor (golden-angle phyllotaxis, Fibonacci
  branching, criticality) before chemistry; **Creative** tier.
- `CassiTheory/speculations/creative-extensions/coherence-commons.md` — **identity is
  the run, not the recipe**; life as a coherence process that persists against the
  drain.
- `CassiTheory/speculations/creative-extensions/coherence-commons.md` §1.1/§7 and
  `CassiTheory/foundations/proton-coherence-budget.md` — the coherence product, the
  Qi bath, transient-vs-eternal structure.
- `CassiTheory/consciousness/cascade-consciousness.md` — consciousness as coherent
  field configuration in a medium ($\rho$ sets the signal-to-noise); a being is a
  field regime, not a chassis.

Physics grounding (engine source of truth, quoted verbatim where load-bearing):
- `CassiCosmos/compute/cassi_nbody_gravity.glsl` — the river law, `∇(g·Φ)`, the
  Yang fraction π/ρ, q.
- `CassiCosmos/compute/cassi_particle_merge.glsl` — the "dust → object" merge
  lineage: the order-selective coherence gate `q_sel = q_coh·q_ord > φ⁻²`, the
  gravitational-binding criterion, the super/subsonic-inflow gate, the virial
  stopping scale.
- `CassiCosmos/compute/cassi_condensation.glsl` — the q-threshold condensation
  scanner that nucleates bodies.
- `CassiCosmos/scripts/nbody_sim.gd` — the collisionless N-body (`N=2000`, gravity
  only, no collisions) that the silhouette observation runs on.

Every number below is from `corpus-reconciliation.md` (the canonical set — cited,
not re-derived), engine-verbatim, or explicitly flagged **[assumption]** or
**[probe]** where it stands on a question this design cannot yet answer from the
docs.

---

## 1. The observation, honestly framed

### 1.1 What the sim actually does

The seed phenomenon runs on the engine's standalone **collisionless N-body**
(`CassiCosmos/scripts/nbody_sim.gd`, `N=2000`), a fully GPU-side O(1) sim where
particles feel **exclusively the river-law gravity** — there is no collision pass,
no pair-repulsion beyond softening, no authored "shape." Each particle obeys the
single law its server-doc form reuses for entity steering:

```
a = −G_N·(π/ρ)·∇(g·Φ),   π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72),
q = ρ²/(ρ²+φ⁻²+ε²),      g = 1 + (φ⁶−1)·q            (river law, cassi_nbody_gravity.glsl)
```

Because the law's acceleration is *gradient-driven* (it points along `∇(g·Φ)`, the
direction of steepening field) rather than pairwise-Coulomb, the cloud's phase space
is not the smooth collapse of a gravitating gas — it organizes into coherent flows
that pinch, fold, and layer.

### 1.2 Why coherence coloring reveals "layers"

When the same cloud is colored by **coherence `q`** (`q = ρ²/(ρ²+φ⁻²+ε²)`, the
fraction of local energy that is organized rather than lost to decoherence), the
field's structure becomes legible at multiple scales at once. High-`q` regions
brighten where the φ-lock (`EY = φ·EI`) holds; low-`q` regions (where `ε² =
(EY−φ·EI)²` is high) darken where the law is unraveling. The engine's own
**cascade structure** — a ladder of organization scales (`ξ = φ⁶ ≈ 17.94`, the
rung-scaling physics of `corpus-reconciliation.md`, `CassiTheory/foundations/
dimensionful-cascade.md`) — means that coherent structure at *different* scales shows
up as *distinct brightness layers* in one q-colored frame: the same law that orders
a galaxy orders a swirl at a decimeter. The "silhouettes" are the field's own
coherent filaments, and the "layers" are cascade rungs (`CassiTheory/speculations/
creative-extensions/universal-biology.md`: the ladder structures **bodies** as nested
gate chains, each rung a layer).

### 1.3 The honest status: a claim, not a fact

The owner's observation — that these multi-layer shapes **contain the silhouettes of
birds, fish, dinosaurs, shells, and flowers**, and that the shapes *continually
evolve* — is a real, striking phenomenon worth designing around. It is **not** yet a
verified property of the engine in the CassiCraft host. It sits in the zone the corpus
already teaches us to treat carefully: the φ-ladder biases structure toward a small
set of *preferred* morphologies (`universal-biology.md` §2, the golden angle, the
Fibonacci branching; Creative tier), but whether a *Minecraft-anchored* field with
terrain coupling and damping reproduces them is unmeasured. **Nothing in this
document asserts the silhouette phenomenon as engine-verbatim fact.** It is the
**pre-registered probe** below.

### 1.4 Pre-registered Phase-1 probe — does a collisionless cloud produce stable organism-like morphology?

This is the Phase-1 experiment that decides whether the ecology is field-real or a
transient curiosity. Protocol (run on the actual sim, not a model):

| Probe step | Action | Deciding output |
|---|---|---|
| P1 | Evolve a collisionless cloud (`N=2000`, river-law gravity, softening as `nbody_sim.gd`) on the Phase-1 box (`chunk-field-quantization.md` §1.2: `(1,1,1)·192³ / 12³-chunk`, 64³ cells, `dt=0.05`) from a cold Gaussian IC. | A long run log of particle state. |
| P2 | Color by coherence `q` (the published `field_q` channel, `corpus-reconciliation.md`: ≈ 6 MiB snapshot includes q) and record layer positions over time. | A temporal series of q-colored silhouettes. |
| P3 | Catalog **repeated** silhouettes/layers: which shapes recur, at what cadence, at what scale separation. | A list of recurring morphologies + their rung-separation. |
| P4 | Decide: **stable attractor set** (a bounded set of recurring organisms the law revisits) vs **transient soup** (continuous shape turnover with no recurrence). | The verdict this probe exists to produce. |

**Honest gate.** The design is *worth building* only if the probe shows a **stable
recurrence** — a small set of morphologies the field returns to, separated by layer
structure — rather than a homogeneous transient soup. Both outcomes are legitimate and
informative: an attractor set licenses the whole ecology below; a transient soup still
licenses the *recognition* machinery (§2) and the field-as-spawner (creatures as
transient coherence that occasionally precipitates), just without the strong
"species-as-attractor-basins" claim (§3). The probe's verdict is recorded against this
pre-registered decision before any gameplay follows from it. **[probe]**

---

## 2. The ecology as field-emergent

### 2.1 Rejecting the mob table

Vanilla responsibility is a **table**: an idle AI, a health pool, a loot drop. The
ecology rejects this at the root. A CassiCraft creature is **not a spawned entity
with an authored behavior** — it is a **transient coherence structure that crossed a
persistence/organization threshold and condensed into a body**. The engine already
supplies the entire physical lineage this rides on: the merge chain
`dust → object → …`, which `cassi_particle_merge.glsl` realizes with an
**order-selective coherence gate** (`q_sel = q_coh·q_ord > φ⁻² ≈ 0.382`), a
**gravitational-binding criterion** (`G_eff = G_N·(1+ξ·q_mid)`), a **subsonic-inflow
requirement** (only sub-coherence-sound-speed matter binds), and a **virial stopping
scale** (a relaxed, self-supporting structure stops accepting infall). This is the
engine's own "organized matter precipitates into a body" — the ecology extends it one
rung up the ladder from *object* to *organism*.

**The claim:** a creature is what the field precipitates when a locally-organized
coherence structure holds together long enough and coherently enough to cross the
recognition threshold (§6b). It is the same physical act as condensing ore or
nucleating a body — just at the *organism* organization scale, reached by "dust →
object → **organism**" up the merge lineage.

### 2.2 The lifecycle

| Stage | What the field does | Engine/physics anchor |
|---|---|---|
| **Structure forms** | A river-law flow folds a region of field into a coherent configuration (the collisionless cloud's filaments/P1). | `cassi_nbody_gravity.glsl` gradient arm; the silhouette probe. |
| **Persists** | The structure holds coherence `q` against the `ε²` drain — the φ-lock (`EY = φ·EI`) resists decoherence. Life at this stage is **coherence that persists**. | `ε² = (EY−φ·EI)²`; the attractor (`coherence-magic.md` §1); the `(1−q)` waste `CassiTheory/speculations/qi-bubble-propulsion.md` §2.5. |
| **Recognized** | The structure crosses a persistence × coherence-band × size threshold (§6b) — from a transient field event to a *candidate* organism. | the recognition rule (this doc's core judgment). |
| **Precipitates** | The candidate condenses down the merge lineage into a **body** — a self-supporting, coherence-carried object that is now a *steerable entity* on the tick-sampler. | `cassi_particle_merge.glsl` (bind + virial stop); `chunk-field-quantization.md` §2.2 entity steering. |
| **Lives** | The body is **steered by the river law** (the same `a = −G_N·(π/ρ)·∇(g·Φ)` all entities use, `chunk-field-quantization.md` §2.1) and feeds on local coherence — seeking high-`q` regions, avoiding `ε²` wells, exactly as the field's own gradient points. Metabolism = **maintaining the φ-lock**. | `a = −G_N·(π/ρ)·∇(g·Φ)`; the river law as the sole movement law. |
| **Dies/dissolves** | The `ε²` drain outruns the φ-lock; the body sheds coherence, un-condenses, and its matter returns to the field — a scarless death because the body *was* field. | `ε²` dissolution; the field heals toward its attractor (`chunk-field-quantization.md` §2.2). |

**Life as persistent coherence.** The through-line is `coherence-commons.md`'s
*identity-as-the-run*: an organism is not a recipe (a species table) but a **run** — a
configuration the field is actively maintaining. When the run ends, the creature is
not "killed"; the field stops holding the configuration and it returns to the medium.
This is the honest, non-dualist death the field demands: matter is conserved, only the
configuration is lost.

---

## 3. Morphology from the law

### 3.1 The field explores morphology space; species are attractor basins

The silhouette observation (P1) is only the start. The claim this design commits to,
**contingent on the probe's P4 verdict**: the field's dynamics **explore morphology
space**, and "species" are not fixed entity types but **attractor basins the field
revisits**. Birds, fish, shells, flowers are not hand-authored mobs — they are
**recurring archetypes in the coherence landscape**, the same way the φ-ladder makes
golden-angle phyllotaxis and Fibonacci branching *preferred* structures
(`universal-biology.md` §2, Creative tier). The field does not produce arbitrary
random shapes because the **law has preferred structures**: the φ-attractor is the
maximally-irrational configuration that sustains multi-scale (multi-rung) order, so
the morphologies that hold coexist across rungs **persist**, while single-scale or
φ-incommensurate shapes de-cohere and dissolve. That is the entire basis of "morphology
from the law": **preferred structures persist; everything else is transient.**

### 3.2 The multi-layer structure = the organism's internal cascade

The engine's own two-fluid field is a **cascade** of organization scales (the ξ-rung
physics; `corpus-reconciliation.md`; `cassi_particle_merge.glsl`'s order-selective
gate rewarding smooth phase-locked order at multiple scales). An organism — a bird, a
fish, a shell — **is a nested set of cascade layers**: shell laminae, flower petals,
fish scales, the segmentation of a body — **each layer a rung**. This is exactly the
`universal-biology.md` §3 reading of the organism as a **gate chain**: a row of
cascade bubbles that moves coherence across the rungs a single gate cannot span, with
Fibonacci-admissible node counts and φ-elliptical geometry. And it is *directly
observable* in the q-colored sim: P2's "layers" are the organism's internal rungs
made legible by coherence coloring. **A creature's visible layered body is its
cascade depth.**

### 3.3 Difference from vanilla and from "random shapes"

| | Vanilla mob | Random shape soup | Field-emergent organism |
|---|---|---|---|
| Origin | spawn table entry | unconstrained noise | the field's own coherent collapse (P1) |
| Structure | authored model/behavior | no persistence | nested cascade layers = rungs (P2, §3.2) |
| Persistence | designed (health/duration) | none | `q` held against `ε²` (§2.2) |
| Recurrence | fixed species | none | attractor basins the law revisits (P4, §3.1) |
| Dynamics | scripted AI | stochastics | the river law steers (§2.2) |

Unlike vanilla's authored biology **and** unlike unconstrained shape-noise, the field
returns to a bounded set of preferred morphologies *because the law's preferred
structures are what can persist*. This is the probe's whole stake: P4's "stable
attractor set vs transient soup" is precisely the line between an ecosystem and a
visual curiosity.

---

## 4. The evolving biosphere

### 4.1 Evolution-by-field, not evolution-by-mutation

Vanilla and conventional procedural-life both evolve by *mutation*: a genome, a
selection filter. Here there is no genome. The biosphere evolves **by the field's
dynamics drifting through morphology space**: structures appear where the field folds
coherently, thrive where they can hold the lock against the local ε² drain, change /
vanish as the ambient coherence redistributes, and the **world stabilizes whatever
persists**. This is *selection without a selector* — no fitness function, no
reproduction rule; only "what the law can hold together long enough to keep
returning." It inherits the attractor's own stability theory from `coherence-commons.md`
§1.1: the deep, distributed, multi-rung configurations persist; the shallow,
concentrated ones are transient by construction.

### 4.2 Biome ⇔ regime mapping

Because a creature precipitates only where the local field state admits its
coherence-band + size (the spawn rule of `chunk-field-quantization.md` §2.2: spawn only
where `q` is in a coherent band and `ε²` is low), **the local `(q, ρ, ε²)` regime is a
biome**:

| Regime | Local field state | Fauna it precipitates | Cross-ref |
|---|---|---|---|
| **Coherent ridge** | high `q`, low `ε²` | deep, layered, φ-locked organisms (the "shells/flower" morphologies — many-layer internal cascades) | a Qi-bath-like region (`coherence-technologies.md` concept 4) |
| **Living plain** | mid `q`, mid-low `ε²` | agile, mobile morphologies (birds/fish — river-gradient steepness drives pursuit) | the river-law steering band |
| **Scarred/decohered well** | high `ε²`, low `q` | few or no organisms; any that form are transient, shedding coherence fast | scars (`energy-harnessing.md` §5.4 anti-corruption) are ecological failure |
| **Condensation front** | `q` accumulating, crossing `τ_c` | precipitation events — bodies condensing *out of* the front | the merge lineage; `cassi_condensation.glsl` |

**The biosphere drifts with the field.** Since terrain condenses and heals, coherence
ridges migrate, scars close (`chunk-field-quantization.md`, `volumetric-terrain.md`),
and the biome map moves with them. A species that thrived on a coherence ridge must
follow the ridge or dissolve; a scar that heals repopulates. The ecosystem is
*the field's own geography of organization*, continuously reshaped — which is the
README's thesis made visible: the living world is not a place where mobs spawn; it is
a place where the field is alive, and life is what that aliveness resolves into.

---

## 5. Player interaction

### 5.1 The coherence reader sees the layers

The player's **Sense / coherence reader** (`coherence-magic.md` §2, the Phase-1
deliverable) is literally the observation tool of P2: it renders the published `q`
(`field_q`) as a magnetometer overlay. **Reading a creature's nested layers is
therefore identical to reading the q-colored sim** — the reader does not show the mob;
it shows the organism's internal cascade (§3.2). A player "x-rays" a creature to see
how many rungs it holds, how deep its φ-lock runs, where its coherence is leaking.
This is the cleanest tie in the design: the player's tool and the scientist's probe
share the exact same channel.

### 5.2 Hunting/farming = interacting with coherence structures

Because a creature is a **moving coherence store** (a self-supporting, φ-locked body
that holds organized matter — `energy-harnessing.md` §1.5 deep-rung stored coherence),
interacting with it is the energy economy:

- **Creatures glow by the `(1−q)` waste law.** Any working field system wastes
  `E_waste = (1−q)·E_throughput` as visible glow (`energy-harnessing.md` §2;
  `coherence-technologies.md` concept 4). A creature maintaining its φ-lock against a
  drain glows proportionally to how far from full coherence it runs — a starving or
  wounded creature is a brighter, more wasteful one. The glow is the ecological
  health-meter and the hunt-targeting diagnostic at once.
- **The stored coherence is fuel.** A harvested creature yields its ordered matter —
  a body that was a field configuration returns to the medium, and its depth-rung
  coherence is withdrawable (`material-regimes.md` §5 fuel = stored coherence). Hunting
  is a **deep-rung reaping** (`energy-harnessing.md` §2.5): it scars to reap and pays
  in the field's disorder, not in an item. There is no "mob drop"; there is coherent
  matter released back into the field.
- **Farming = sustaining a coherent region.** Instead of a pen, a farm is a **maintained
  Qi bath** (`coherence-technologies.md` concept 4; `energy-harnessing.md` §4.4): raise
  and hold a region's coherence, and the organisms the field precipitates there persist
  and can be reaped on a cycle. Farming is *field husbandry* — you tend the coherence,
  not the animal.

### 5.3 Conservation = maintaining coherence regions

The energy doc's **anti-corruption** (`energy-harnessing.md` §5.4) — spending fed
coherence to suppress `ε²` and hold the dissolution threshold — is directly an
ecological act. A player who suppresses decoherence in a region keeps its biome alive:
the organisms don't die, the coherence doesn't bleed out, the species' attractor basin
stays populated. Conservation is not a separate "don't kill" mechanic; it is choosing
to *invest coherence in a region the field would otherwise dissolve*. The no-free-energy
rule (`energy-harnessing.md` §6) applies: this is a net-negative hold (you pay in
coherence to maintain), so it is always a player *cost*, never a free ecosystem.

**The over-bloom made a danger (reverse pointer, two-way).** This §4's shallow-species
over-bloom is what the danger layer's first *ecological* hazard is made of:
[`the-blight.md`](./the-blight.md) §1/§2.2 turns this over-bloom pathological — a
sustained wrong-band (the flood's surfeit) keeps the run the field was holding from
dying back, and the kept organism's feeding turns from the field's ordering to the
region's own coherence, a living drain that spreads (§2.2 there grounds corruption on
this §2.2's "run the field holds" and this §4's shallow species). **And this §5.3 is
the blight's healing frame**: conservation = anti-corruption is the heal — restore the
band, shed the corrupted organisms back (§4.1 there). The two docs now cite each other
as read-and-answered: the over-bloom (this §4) is the blight's raw material, the
conservation (this §5.3) its preferred cure.

### 5.4 Domestication/breeding = steering the field to stabilize a morphology

Breeding has no breeding mechanic. To "domesticate" a species a player must **steer
the field to make a desired morphology's attractor basin persist** — the custom-blocks
authoring parallel (`custom-blocks.md`). Where `custom-blocks.md` authors a *material*
as a regime tuple `(ξ, ω₀², θ_c, n)` through the material lab, **domestication authors
a *organism* as the same act**: shape the local regime until the field precipitates and
holds the morphology you want, then hold its coherence so it persists generation after
generation. A "custom creature" is a regime-authored case of the material lab — you
are not breeding genes, you are **maintaining a coherence configuration until it
stabilizes.** The found-vs-invented economy of `custom-blocks.md` §6 maps straight
over: finding a species is read-only (document a basin the field already has);
inventing/domesticating one is expensive (spent coherence + vent risk) but unbounded
within the realizable morphology space.

---

## 6. Honest risks and gates

### (a) The silhouette probe may fail

The ecology's strongest claim — species as **attractor basins** — is contingent on
P4 returning "stable attractor set." The honest failure mode: **the collisionless-cloud
morphology may not survive terrain coupling and damping in the Minecraft-anchored
field.** The isolated `nbody_sim.gd` cloud (P1) runs free; the CassiCraft host couples
the field to terrain, dissipates it through RealSim drag/viscosity/friction
(`material-regimes.md` §3), and anchors it to a box (`chunk-field-quantization.md`
§1.2), where the decoherence-floor environment of a finite world may wash out the
delicate multi-rung order that produced the silhouettes. **If P4 returns "transient
soup" or P1's ordering does not survive terrain coupling, the species-as-basins claim
softens to field-as-spawner** (§1.4): creatures become **transient coherence that
occasionally precipitates** rather than recurring archetypes. The recognition machinery
(§2) is load-bearing either way; only §3's strong "preferred morphologies" framing is
gated on the probe passing.

### (b) The recognition threshold — the design's core judgment

**When does a transient become an organism?** This is the one judgment the engine's
channels do not settle. The proposed concrete rule, using the engine's real
`q`/`ε²` channels (no new physics):

> **A field structure is recognized as a candidate organism when it sustains, for a
> minimum window `T_org`, all three of:**
> 1. **coherence band**: local `q` inside a band `[q_low, q_high]` held above a floor,
>    set near the engine's coherence/condensation scale (`φ⁻² ≈ 0.382` merge gate to
>    `τ_c = 0.5` condensation threshold);
> 2. **decoherence ceiling**: `ε²` stays below a floor (i.e. it is *holding* the
>    φ-lock against the drain, not just briefly coherent);
> 3. **size / rung-depth**: it spans enough nested layers (rungs) to count as an
>    organism rather than a noise blip — at least 2–3 distinct cascade layers.
> A structure meeting all three for `T_org` **precipitates** down the merge lineage
> into a steerable body (§2.2); one that drops below any criterion before `T_org` is
> discarded as a transient.

`T_org`, `[q_low, q_high]`, and the ε² floor and layer-count are **Phase-1 probe-tuned
parameters** (this is precisely what P1–P4 calibrate), not physics constants. **[probe]**
The rule is deliberately three independent conditions so no single channel hijacks the
judgment: a bright-but-nonpersistent flicker (time), a persistent-but-decoherent eddy
(ε²), and a one-layer blip (size) all fail even if the others pass.

### (c) Entity budget — the ecology must precipitate *few, meaningful* organisms

The field's **morphological soup is free**: the transient, sub-threshold coherence
structures are the field itself, and coloring them costs nothing beyond rendering the
already-published `q` (`corpus-reconciliation.md`: ≈ 6 MiB snapshot; the world samples
it regardless). It is only **bodies** that are bounded. Per-entity river-law steering
is ≈ 40 ns (`chunk-field-quantization.md` §4.2), but the Phase-1 cap is ≈ 2,000
steered entities (§7 Q4). **The ecology must precipitate few, meaningful organisms, not
thousands.** The recognition rule (§6b) is the throttle: only structures that pass the
full three-condition gate for `T_org` become bodies, so most of the soup stays field
and only a bounded population condenses. The precipitation cadence must be budgeted
jointly with the ≈ 2,000 cap — the field is allowed to *look* teeming (it is free), but
the tick-sampler should body (steer) only the small set that crossed the gate.

### (d) Boundedness — the biosphere must not destabilize the terrain demo

Organisms perturb `ρ`/`ε²` as they live and dissolve, and their feeding/dissolution
could feed back into terrain condensation/healing. This is bounded by the energy doc's
**no-free-energy rule** (`energy-harnessing.md` §6): no conversion yields more than it
sinks, structured as **amplitude caps in the write-back lane** (`coherence-magic.md`
§5.1 Q4; `chunk-field-quantization.md` §6 #3). Concretely: a creature's local coherence
withdrawal is capped at `output ≤ φ⁻¹·input`-style amplitude caps in the perturbation
it pushes through the player-return channel, so **the ecosystem cannot mint coherence or
run ahead of the field's heal rate** — the terrain demo remains stable regardless of how
many organisms precipitate or dissolve. **[assumption]** The exact amplitude cap values
are Phase-1 tuning (the energy doc's Q2 mechanical-gate question applies here too), but
the *no-net-gain* discipline is inherited as a hard rule.

---

## 7. Feasibility verdict

**Phase-1 (a live, honest slice, no new physics):** the **silhouette probe** (P1–P4) on
the real collisionless cloud, the **recognition rule** (§6b) defined and calibrated
against the engine's `q`/`ε²` channels, and a **minimal precipitation demo** — let a
coherent structure cross the gate, precipitate down the merge lineage into a single
steerable body, and dissolve back to field, all on the already-published snapshot and the
already-engine-real merge pass (`cassi_particle_merge.glsl`). This is Phase-1 because it
consumes only what `chunk-field-quantization.md` already budgets (the `q`/`ε²`/`∇(g·Φ)`
publish, per-entity steering, the ≈ 2,000-entity cap) and `coherence-magic.md` §5.1's
Q4 write-back lane. Nothing new is built; the probe and the gate are readers of existing
channels.

**Later (gated on P4 passing and Phase-1.5 material gates):** the **full drifting
biosphere** (multiple precipitating species following coherence ridges, biome⇔regime
mapping, evolution-by-field) depends on per-cell ω₀²/ξ and per-material dissipation
(`material-regimes.md` §7 Q1/Q3, the Phase-1.5 gates) so organisms can be
*differentiated* from the law rather than reduced to one regime; **domestication**
depends on `custom-blocks.md`'s material-lab authoring surface (which itself sits on
those gates) to author organisms as regime tuples.

**Verdict.** The architecture is sound and fully grounded in engine-real physics: the
merge lineage's order-selective coherence gate and virial stopping scale *is* the
precipitation mechanism; the river law *is* the locomotion; the `ε²` drain *is* the
mortality; the `(1−q)` glow and the stored-coherence withdrawal *are* the hunting/farming
economy — with zero authored behavior beyond the recognition threshold. **The binding
risks are the probe (does the silhouette become a stable attractor set under terrain
coupling?) and the recognition judgment (where does the moral line sit so the gate is
honest?).** Phase-1's probe + gate + single-precipitation demo is achievable on the
already-built async field domain and settles both risks before any gameplay claim
follows.

### Open questions

1. **P4's threshold.** What counts as "stable recurrence" for an attractor-set verdict —
   how many returns, over what window, at what rung-separation? Pre-registered as the
   probe's decision rule (§1.4), to be colored in from the run.
2. **Recognition-rule calibration.** How do the engine's dimensionless `q ≈ 1e-3…1e-1`
   at noise-scale values map onto a game-legible `[q_low, q_high]` creature band
   (`energy-harnessing.md` §7 Q1's scale-calibration problem, applied to life)? Phase-1
   measurement.
3. **Organism coupling to the merge lineage's object→BH top.** When a recognized
   organism precipitates via `cassi_particle_merge.glsl`, does it *become* a merge-body
   (a capacitor/object at its rung) or a *terrain block-state* (a quantized cell)? The
   two are the same continuum (`custom-blocks.md` §7 Q5), but the sampler path differs
   and must be picked.
4. **The biosphere's drift vs. the box seam.** Organisms following a migrating coherence
   ridge near the `12³-chunk` box boundary encounter the re-home seam
   (`chunk-field-quantization.md` §7 Q1). Phase-1-exceptable (seam far from view), worth
   designing before a real world.

---

## Cross-references

Documented consumers (all relative paths):
- [`the-scavenger.md`](./the-scavenger.md) — **the residual-band organism.** §2.1 there
  reads an organism-class run in this doc's §2.2 sense ("a configuration the field is
  actively maintaining"), but its coherence band is the *spent* locality's residual one —
  §6b's recognition rule read inverted (§2.1 there); §5.3's conservation = anti-corruption
  is the healing that thins its count. Reverse pointer: the scavenger is an organism-class
  this doc's recognition rule admits only at the spent margin.
- [`the-sea-floor.md`](./the-sea-floor.md) — **the reef's band.** §2b there reads the
  regime⇔biome map (§4.2 this doc) at the sea's edge: the reef is the sea's life band, the
  ecology concentrating against the coherent edges the shelf reveals. Reverse pointer: the
  reef is this doc's biome mapping applied to the liquid regime's boundary.
- [`the-commensal.md`](./the-commensal.md) — **the surplus-margin organism.** §2.1 there
  reads an organism-class run in this doc's §2.2 sense (a config the field is actively
  maintaining), but its band is the *ordered* surplus margin — §6b's recognition rule read
  *inside* the coherent band, not inverted to the spent; §5.3's conservation = anti-corruption
  is the bounded assist it performs at the smallest scale; §4.2 the coherent ridge /
  precipitation front it lives on. Reverse pointer: the commensal is an organism-class this
  doc's recognition rule admits at the ordered margin.
- [`the-marsh.md`](./the-marsh.md) — **the tessellated habitat.** §5 there reads §2.2
  this doc's organism-class runs, §4.2 the regime⇔biome map, §6b the recognition rule
  — the marsh is its own fine-grained biome the plain could not hold. Reverse pointer:
  the marsh is the field's tessellated habitat.
- [`the-guardian.md`](./the-guardian.md) — **the bound morphology.** §2.2 there reads
  §2.2 this doc's organism-as-a-run the field holds, §4.2 the biome⇔regime mapping,
  §6b the recognition rule (the Guardian's morphology), and §5.3 conservation =
  anti-corruption (the keeping's honest frame). Reverse pointer: a Guardian is the
  ecology's morphology made a bound keeper.
- [`the-herald.md`](./the-herald.md) — **the recognized run.** §2.1 there reads §2.2
  this doc's organism-class run, §4.2 the biome⇔regime mapping, §6b the recognition
  rule (the Herald's admission), §5.3 conservation = anti-corruption, §1.4's P4 the
  probe that decides whether a holder exists. Reverse pointer: the herald is the
  ecology's recognized run, voiced.
- [`the-spring.md`](./the-spring.md) — **the stationary counter.** §2.2/§4.2 there reads
  the migrating ridges (species follow ridges or dissolve) — the Spring is stationary,
  a fixed well the field keeps full; §1.4 the silhouette probe (the migration's gate).
  Reverse pointer: the spring is the ecology's stationary well.
- [`the-mimic.md`](./the-mimic.md) — **the borrowed morphology.** §2.2/§6b there reads
  the organism-class runs — the Mimic's morphology; §3.1 species as attractor basins;
  §4.1 evolution-by-field; §1.4's P4 the deciding probe. Reverse pointer: the mimic
  composes borrowed shapes over the ecology's basins.
- [`the-roost.md`](./the-roost.md) — **the nested run.** §4.2 there reads the
  biome⇔regime map (the habitat each roost sits on); §2.2 the organism as a run the
  field holds (a roost is where a run settles); §6b the recognition rule; §1.4 the
  silhouette probe; §3.1 the attractor basins; §5.3 conservation = anti-corruption.
  Reverse pointer: a roost is the ecology's settled run.
- [`the-moth.md`](./the-moth.md) — **the coveting run.** §2.2 there reads the
  organism-class run the field holds — the Moth's ground; §6b the recognition rule; §4.2
  the biome map; §1.4's P4 the probe. Reverse pointer: the moth is the ecology's
  coveting run.
- [`the-shepherd.md`](./the-shepherd.md) — **the morphology and the flock.** §2.2 there
  reads the organism as a run the field holds (the Shepherd's morphology); §6b the
  recognition rule; §4.2 the biome⇔regime map; §5.3 conservation = anti-corruption; §6c
  the entity budget (the ≈2,000 cap that bounds the crowd); §1.4's P4. Reverse pointer:
  the shepherd is the ecology's gathering run.
- [`the-broker.md`](./the-broker.md) — **the morphology.** §2.2 there reads the
  organism-class run (the Broker as a mobile order-carrying being). Reverse pointer:
  the broker is the ecology's carried-order run.
- [`the-river.md`](./the-river.md) — **the linear biome.** §2.2 there reads the
  organism-class run; §4.2 the biome map. Reverse pointer: the river is the
  ecology's linear biome.
- [`the-migration.md`](./the-migration.md) — **the collective field-mechanics.** §2.2
  there reads the organisms as runs; §4.2 the ridge-migration; §5.3/§6c the
  flocking/schooling field-mechanics; §6b the recognition rule; §1.4's P4. Reverse
  pointer: the migration is the ridge-migration at full people-scale.
- [`the-estuary.md`](./the-estuary.md) — **the estuarine biome.** §2.2 there reads the
  organism-class runs; §4.2 the regime⇔biome map; §6b the recognition rule; §1.4's P4.
  Reverse pointer: the estuary's nutrient band is the ecology's life at the
  mixing.
- [`the-understory.md`](./the-understory.md) — **the shade biome.** §4.2 the biome⇔regime map (the shade’s narrow band admits fewer, thinner species); §6b the recognition rule; §2.2 the organism-as-a-run; §1.4’s P4. Reverse pointer: the shade’s life is a recognized run, never a hidden biome.
- [`the-orchard.md`](./the-orchard.md) — **the rung-trees.** §4.2 the biome map; §2.2 life as a run; §6b the recognition rule; §5.3 conservation. Reverse pointer: the orchard is the ecology’s recognized standing life.
- [`the-delta.md`](./the-delta.md) — **the fan biome.** §4.2 the biome map (the delta’s band where the many channels meet); §6b the recognition rule. Reverse pointer: the delta is the ecology’s fan-band biome.
- [`the-pooka.md`](./the-pooka.md) — **the fear-fed run.** §2.2 the organism-class run (the pooka’s morphology); §6b the recognition rule; §4.2 the biome map. Reverse pointer: the pooka is the ecology’s fear-fed run.
- [`the-meadow.md`](./the-meadow.md) — **the open biome.** §4.2 the biome map (the meadow’s fertile band); §6b the recognition rule. Reverse pointer: the meadow is the ecology’s recognized open run.
