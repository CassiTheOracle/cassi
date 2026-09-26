# Materials as Field Regimes (the Powder-Toy physics sandbox)

**Question under design:** how to replace Minecraft's per-material behavior
tables (falling sand, flowing water, diamond hardness, redstone conductivity,
TNT, ore worldgen, fuel values) with a single emergent source — the two-fluid
field — so that every material is a *point in the field regime* (density,
coherence, decoherence, energy) plus a small set of coupling constants, and
all behavior falls out of the same law that already steers gravity, terrain,
and the merge lineage.

This is the "Powder Toy" framing from the maintenance handoff: instead of a
chain of `if (material == SAND) fall(with_gravity) else if …` rules, one field
law produces granular piles, fluids, combustion fronts, conductivity channels,
ore precipitation, and hardness — with each material contributing only its
constants. Companion to [`volumetric-terrain.md`](./volumetric-terrain.md)
(terrain as iso-surfaces, precision tools = cascade rung), the dual-world grid
in [`chunk-field-quantization.md`](./chunk-field-quantization.md), and the
async seam in [`async-field-domain.md`](./async-field-domain.md).

Every number below is taken from the physics engine shaders
(`CassiCosmos/compute/*.glsl`) or explicitly flagged **[assumption]** where it
extends engine terms to behaviors the engine does not (yet) drive. Where a
mechanic is *design* (the engine's real terms cannot supply it today) it is
flagged [design] and separated from what the law actually does.

---

## 1. The thesis: a material is a field regime

A material is **not** a behavior key (`SAND`, `WATER`, `DIAMOND`). It is a
point in the field-state space — the same continuum the terrain already
quantizes against — plus coupling constants:

**State** = the position `(ρ, q, ε², energy)` in the regime:
- `ρ = EY + EI` — **density** (how much field).
- `q = ρ² / (ρ² + φ⁻² + ε²)` — **coherence** (how φ-locked Yang/Yin is;
  the engine's chord factor `g = 1 + (ξ−1)q` rides on it).
- `ε² = (EY − φ·EI)²` — **decoherence / disorder**. The engine's `vel[].w`
  carries exactly this per cell (`cassi_two_fluid.glsl` pass B).
- `energy` — the `ε²` budget plus the kinetic/strain content of the local wave
  field (heating is a budget of ε², §3).

**Identity** = the coupling constants:
- `ξ` — **chord coupling to gravity** (`ξ = φ⁶ = 17.9443` engine default; the
  coupling is `ξ − 1`). High-ξ matter couples harder to `∇(g·Φ)` and is heavier
  *and* more attractive.
- `ω₀²` — **resonance frequency** (`omega2`, default `20.0`). How strongly the
  field self-oscillates about the φ-locked line; sets the sound/coherence
  speed and the thermal carrier rate.
- `θ_c` — **condensation threshold** (the engine's `qi_condensation_threshold
  = 0.5`; the merge gate uses `φ⁻² ≈ 0.382`). The ρ crossing at which matter
  "condenses" into this material's dense state.
- `n` — **rung depth**, an integer/φ-scale along the cascade. Deeper rung =
  more ordered matter, higher hardness, higher stored coherence.

**Material identity = the constants; state = the position in the regime.**
Two blocks of the same material are the *same constants* at possibly
*different states* (a hot block of stone and a cold block of stone are the same
`(ξ, ω₀², θ_c, n)`; they differ in `(ρ, q, ε², energy)`). A phase transition is
a *threshold crossing in state*, not a different material. This is the 
collapse: one field, N materials = N constant-tuples, all behavior emergent.

The dual-world grid of `chunk-field-quantization` is the substrate: a coarse
1 m "Cassi block" carries its field sample `(ρ, q, ε²)` integrated over its
meter, and its material identity is a *lookup of the sampled state against
constant-tuples*, not a stored block-id with a rules entry. Re-quantization is
the engine already re-samples and re-thresholds; adding "material" only means
the sampled state selects which tuple governs it.

---

## 2. The emergent state machine: solid / liquid / gas / plasma

The vanilla phase machine is a per-block `BlockState`. Here it is **hysteresis
on the sampled thresholds**, reusing the exact hysteresis semantics of
`chunk-field-quantization.md` §3: `ρ ≥ τ_c` solidifies, `ρ ≤ τ_c − δ` dissolves,
so a jittering field does not flicker state every tick.

**Solid / liquid / gas / plasma are regions of the same (ρ, q, ε², energy)
space, not new materials:**

| Phase | Sampled condition (emergent) |
|---|---|
| **Solid** | `ρ ≥ θ_c` **and** `ε²` below a (material, n)-tuned floor — coherent, dense, φ-locked. |
| **Liquid** | `ρ ≥ θ_c` but `ε²` above the solid floor — dense yet decohered (the field cannot hold the φ-lock rigidly, so it flows). |
| **Gas** | `ρ < θ_c` but above a second, lower floor, with q intermediate — diffuse, poorly-held matter. |
| **Plasma** | `energy` (ε² budget) high enough that the local wave field is saturated — the coherence budget is spent as disorder even though ρ may be high. |

**Heat = the ε² budget.** Raising "temperature" means injecting decoherence —
perturbing the field so `ε² = (EY − φ·EI)²` grows while ρ is held. Heating a
solid raises its ε² until it crosses the solid→liquid `ε²` floor (melts);
raising further drives ρ out of condensation (boils), then saturates into the
plasma band. Heating is *not* a new scalar channel — it is the disorder the
law already tracks in `ε²`.

**Conduction is EMERGENT, not table-driven.** The law's Laplacian
(`c²∇²EY/EI`) diffuses field; a hot (high-ε²) region is a decoherence
surplus that **drains along `∇q`** — toward lower coherence — carrying its
disorder outward. This is exactly how the PDE already moves field: the
`ω₀²(EY − φ·EI)` term restores the φ-lock wherever ε² is high, releasing the
"heat" as wave energy that propagates at the coherence sound speed `c_s = h₀/dt`
(engine's merge-shader definition of sound). Materials with high `ω₀²` restore
the lock faster → conduct heat faster. **Conductivity is `ω₀²` (plus ξ for
how much the coupling transfers), no table.**

**Phase transitions = threshold crossings.** Solid↔liquid = the ε² floor;
liquid↔gas = the ρ condensation boundary; gas→plasma = the energy/ε²
saturation band. All reuse the quantizer's hysteresis (§3 of
`chunk-field-quantization`) so a marginally-crossing field anneals instead of
flickering.

**[assumption]** The engine drives `ε²` as a *derived* output of the PDE
(pass B), not as an explicitly injected resource. Heating therefore requires
a *source term* that raises ε² (or, equivalently, perturbs `EY − φ·EI`) — a
[design] injection, not an engine capability today. What is engine-real is
that a high-ε² region *does* relax toward the φ-lock and does emit wave energy
at `c_s`.

---

## 3. Powder-Toy behaviors, each tied to the law

Each classical Powder-Toy behavior is a *consequence* of the identity
constants plus the law — no material-specific rule.

### Falling sand / granular piles
Falling matter is the river law plus RealSim drag, on a coarse-grid particle
representation (dropped blocks are objects, per the condensation→dust→object
merge lineage). The motion of a sand grain is:
```
a = −G_N·(π/ρ)·∇(g·Φ)          river law (the only gravitational term)
  − γ·(ρ_local/ρ_ref)·v         RealSim drag
  − ν·(v − v_field)             RealSim viscosity (shear to the medium)
  − min(μ·|a_g|, |v|/dt)·v̂     RealSim friction (Coulomb floor)
```
(all three dissipation terms verbatim from `cassi_nbody_gravity.glsl`
`realsim_dissipation_smp`, gravity_mode 4). The **granular pile angle is not
assigned** — it is the emergent equilibrium between cohesion-carrying
coherence (the φ-lock keeps neighbors bound) and the friction floor μ. High-μ,
high-coherence matter (sand) forms steeper piles; low-μ, decohered matter
(water) collapses flat. Sand's "falls-with-gravity-then-rests-at-angle"
behavior is *the same law* as water's "flows-to-level" — only the constants
(μ, ω₀², θ_c, q at rest) differ. **No `gravity` flag per material.**

### Fluids
Water/lava are the sand law with low `ω₀²` (weak lock) and a low rest-q
(they cannot hold coherence, so they spread under viscosity rather than
piling). "Flowing" = the `−ν(v − v_field)` shear toward the medium's own
velocity plus the ρ-gradient: the field drains downhill because ρ concentrates
under the river law's `∇(g·Φ)`, and the fluid follows the flow the PDE already
evolves in `FieldVel` (`vel[].xy`). Leveling is the emergent minimizer of the
ε² budget — a tall fluent column costs more disorder than a flat one.

### Combustion = a self-sustaining organized-perturbation front
Burning matter injects EY (Yang) through the **source terms** — the same
`source_ey` organized-perturbation injection the PDE already supports
(`cassi_two_fluid.glsl` `source_ey`/`source_ei`). A fire front is a region
where organized perturbation is being injected at a rate that keeps `q` high
*and* `ε²` high (it both coheres and heats). The front propagates because the
injected EY perturbs the neighboring field, raising its coherence enough to
ignite it in turn. **Front speed ≈ the field's `c_s`** — the coherence sound
speed `h₀/dt` — because the front is a wave of coherence spreading through the
medium. High-`ω₀²` fuel burns faster; high-`n` deep-rung matter keeps its
coherence locked against the ε² it is being heated into, so it is harder to
ignite (fire resistance = decoherence-resistance = deeper rung). **[design]**
The source terms are engine-real (`source_strength`) but driving them
*per-material at a front location* is the sampler's job-dict input (the Q4
player-return channel of `async-field-domain.md`), not an engine term today.

### Explosives = stored coherence released by perturbation
An explosive is deep-rung, `ε² ≈ 0`, near-perfectly-φ-locked matter — a dense
reservoir of organized coherence held far from equilibrium *against* its
attractor. Perturbing it (a `ρ`/`ε²` kick from an incoming front or a tool)
lets the stored coherence **discharge as a full-cascade collapse**: the
φ-lock breaks across many rungs at once, releasing the wave energy as a
two-fluid shock front (a steep `∇(g·Φ)` + a `c_s`-traveling coherence impulse).
The blast radius scales with rung depth squared (the stored coherence is a
deeper-rung reservoir; releasing it discharges the whole cascade). This is the
same "organized vs random perturbation, single-rung vs full-cascade attack"
coherence-budget framing from the theory vocabulary: an explosive is matter
primed to fail along the *full-cascade* pathway. **[design]** The engine's
merge lineage produces condensed bodies; it does not model explosive
*discharge* — that is a new pass (a directionally-released perturbation whose
magnitude is the stored coherence), not an engine term.

### Vocabulary handoff (coherence-technologies / coherence-magic / energy-harnessing)

Two vocabulary points the companion workstreams depend on, adopted additively:

- **(a) The (1−q) waste law is adopted as the machine-loss law.** From the
  CassiTheory speculations (`superconductivity-as-qi-coherence.md` §1.2–1.3,
  `qi-bubble-propulsion.md` §2.5): every working machine wastes
  `E_waste = (1−q)·E_throughput` as visible "glow" — the cost of running any
  regime at partial coherence. This is the energy-law hook carried by
  `energy-harnessing.md` and `coherence-technologies.md` (concept 4): a
  mechanism running at coherence q is (1−q) inefficient, and that waste is an
  observable (it is the §2 ε² budget re-radiated as wave energy, the same field
  flow this doc's conduction already leaks). It is consistent with the regime
  model here — q is the sampled coherence, so the waste law is one line per
  block, plus the material's ω₀² setting how fast it glows off.
- **(b) This doc's fire-vs-explosive distinction is the boundary
  `coherence-magic.md` §4.3 keys off.** State it explicitly and name it: a
  **controlled organizational discharge = fire (fuel)**, an **uncontrolled
  full-cascade discharge = blast**. `coherence-magic.md` §4.3's *overdraw
  trigger → full-cascade discharge* is exactly the explosive pathway here: when
  a player/operator pulls more coherence out of a reservoir than it can
  re-lock (`ω₀²` restoration can no longer feed the drain), the controlled
  release crosses into the full-cascade regime and detonates. The boundary is
  thus a rate/threshold ratio, not a material flag.

### Conductivity = coherence routing along the field gradient
Redstone becomes **coherence routing**: a signal is a local, sustained
coherence band. It propagates along the path of least ε² — i.e. along the
**field gradient**, which is where `∇q` concentrates. High-`ξ` materials are
high-conductivity **channels** because the chord coupling `g = 1 + (ξ−1)q`
amplifies the field, letting a coherence band travel further before the ε²
drain kills it (conduction decays as ε² accumulates, per §2). Low-`ξ`
insulators are low-conductivity because a band running through them loses
coherence to disorder quickly. **Conductivity = ξ (coupling) × ω₀² (lock
restoration rate); a wire is just a high-ξ material, not a block with a
`conductive=true` flag.** Redstone repeaters/torches in vanilla are *power
regenerators*; here a repeater is a material whose ω₀² is high enough to
re-lock a fading coherence band — a powered relay, not a mechanical gate.

### Ore precipitation = q accumulation (forward to chunk-field-quantization)
Ore is not a worldgen height range (verbatim from `volumetric-terrain.md`);
it precipitates where q accumulates above a second threshold. In material
terms: **a vein is a region where the identity tuple's `θ_c` is exceeded not
by ρ but by local `q`** — coherence condenses into a high-`q`, deeper-rung
material (richer, finer-grained as q rises). This is the quantizer's ore
channel already specified; the material system only adds *what * the
precipitate is* (`n`, the constants of the ore's regime), selected by the
local q band. **[assumption]** The engine's condensation scanner
(`cassi_condensation.glsl`) threshold-crosses on q to nucleate bodies; the
*selection of which material precipitates from a q band* (mapping q-interval →
`n`/constants) is the design's addition, grounded in the existing
"coherence accumulates → finer deposit" claim.

**The worked deposit's one-wayness (reverse pointer, two-way).** This §3's
precipitation law is the *economic* face of the corpus's depletion doc:
[`the-fallow.md`](./the-fallow.md) §2a designates **the mined vein** as the first
one-way depletion — "the law precipitates where `q` accumulates; it does not
re-precipitate the *worked* vein," a mined locality's `q` spent and `ε²` raised
by the mining perturbation (`the-fallow.md` §2a — it cites this §3 and §4's
mining-perturbation as the gone-forever source, and §7 Q1/Q3's material-depletion
drift as its gate). Where this doc grows the vein, the fallow is what the window
reads about the vein once spent; the two docs now cite each other as
read-and-answered (you can steward a scarcity, you cannot un-mine an ore).

**The bite-law at the hand (reverse pointer, two-way).** This §3's
precipitation-perturbation and §4's hardness = rung are what the corpus's primitive
work object reads as *mining*: [`the-tool.md`](./the-tool.md) §2a makes **a pick's
bite its rung-depth** — "a tool whose rung meets or exceeds the material's rung
perturbs the field at that scale and *takes*, mining is the perturbation that
lowers `ρ` and raises `ε²` (this §3/§4), and it works only when the perturbation
can break that rung's lock; a short tool skates against a deeper-rung material"
(`the-tool.md` §2a — it cites this §3's precipitation and §4's hardness = rung as
the bite law, and §7 Q1's constants as the mechanical-bite gate). A tool swings
this §3/§4's law at hand-scale; the two docs now cite each other as
read-and-answered.

---

## 4. Hardness = rung depth

From `volumetric-terrain.md`: **precision tools are coherence-manipulators at
a chosen rung; tool resolution ⇔ rung; coarse pick ⇔ coarse rung, sculpting
chisel ⇔ fine rung; one physics, one tool language.** Material hardness slots
directly onto this:

- **Hardness is `n`, the rung depth.** A deeper-rung material is more ordered
  (lower ε²) and holds its φ-lock against a wider range of perturbation —
  that *is* hardness, physically.
- **Your tool's rung must meet the material's rung.** A coarse-rung pick
  perturbs the field at a coarse organization scale; against a deeper-rung
  material that perturbation is below the material's decoherence-resistance —
  the material does not scar, and the tool "does nothing" (it is too blunt /
  too soft). Matching-or-deeper-rung tools scar it — mining is a perturbation
  that lowers local ρ and raises local ε² (§3 of `chunk-field-quantization`),
  and it only takes when the perturbation can actually break that rung's
  lock.
- **Hardness is therefore not a per-block number a tool table compares
  against.** It is the material's `n`, and the tool-material interaction is the
  single law "does this perturbation exceed this rung's decoherence
  resistance?" — the same condition as ignition and blasting, just at a lower
  perturbation magnitude. A diamond block (`n` deep) is un-mineable with a
  coarse pick for exactly the same reason it does not burn — its coherence is
  too well-locked for a coarse attack.

**[assumption]** The theory's cascade is `n`-scaled φ organization; tying
*hardness to `n`* follows the precision-tool rung rule already in
`volumetric-terrain.md`, but mapping a *specific* vanilla hardness (say,
obsidian = 50) to a *specific* integer `n` is a tuning table, not physics —
the design keeps the rung semantics and leaves the constant mapping to
Phase-1 measurement.

---

## 5. Fuel / energy tie-in

Forward reference to `energy-harnessing.md` (a companion doc being written
concurrently; this section does not depend on it).

- **Deep-rung materials are stored coherence.** A diamond (or, in-game terms,
  a coal/diamond-block) is a deep-`n`, `ε² ≈ 0` reservoir. Its fuel value is
  the **controlled coherence release** of its stored organization — burning at
  a rate a fire front can sustain (a *controlled, organized* discharge), as
  opposed to an explosive's *full-cascade* discharge.
- **Fuel = how much coherence a material can release slowly.** The practical
  heat output is bounded by the material's stored coherence budget (depth of
  rung) and by how fast `ω₀²` lets the lock re-form (how fast it can feed the
  front without going explosive). Coal is a shallower coherent reservoir that
  releases at a controlled rate; diamond is a deeper one — but deep-rung
  matter is *harder to ignite* (§3), so fuel isn't simply "more rung = more
  fuel"; it's the regime where controlled release is achievable.
- **The combustion/explosive distinction is a rate on the same mechanism**:
  controlled organizational discharge = fire (fuel); uncontrolled full-cascade
  discharge = blast (TNT). `energy-harnessing.md` will build the harvest /
  storage backbone on top of these two rates.

**[assumption]** "Stored coherence released" as an *energy currency* is the
design's thermodynamic framing; the engine's field carries no explicit
"energy" channel — the release budget is the q/ε²/ρ content of the matter being
consumed, which is engine-real (it is exactly what the merge lineage banks as
mass/coherence). The *game-economic* conversion (how much work one diamond's
release does) is the companion doc's domain.

**Compatibility cross-reference.** `coherence-technologies.md` concept 4
(conductivity = coherence, purity as a crafting axis, Qi bath) is compatible
with this regime model and supplies the **"purity" axis** this doc's
constant-tuple table leaves open: here, a material's constants are fixed, but
its *state* q varies — and a purer (higher-q, lower-ε²) sample of the same
constants conducts better and wastes less, exactly the (1−q) waste law of §3
and coherence-technologies' purity-as-crafting axis. Crafting "improving" a
material is therefore raising its operating q toward the attractor, not
changing its identity constants. See §7 for the open question — whether
per-sample purity (state) and per-species identity (constants) separate cleanly
in the engine's one q channel.

---

## 6. Table-driven behavior collapse: the rule table you no longer need

Powder Toy / Minecraft's per-material rule table lists each behavior
explicitly: sand falls, water flows, diamond hard, redstone conductive, TNT
explodes, coal burns, ore spawns at height Y. The claim: **each row is a
projection of the same five numbers + the law**, and the *columns of the rule
table* are not independent properties but derived quantities.

| Behavior (rule-table column) | Emerges from | Law/term |
|---|---|---|
| Falling | gravity | river law `a = −G_N(π/ρ)∇(g·Φ)` |
| Granular pile angle | μ, q-at-rest | RealSim friction + coherence binding |
| Fluid leveling | ν, low ω₀², low rest-q | viscosity + ε²-budget minimization |
| Heat conduction | ω₀², ξ | ε² drains along ∇q, `ω₀²` re-locks |
| Burning | source injection + c_s | organized-perturbation front @ `c_s = h₀/dt` |
| Exploding | stored coherence | full-cascade discharge → shock front |
| Conductivity | ξ, ω₀² | coherence band along ∇q |
| Hardness | n | tool-rung vs decoherence-resistance |
| Ore | q accumulation | coherent precipitation above θ_c |
| Fuel value | n, ω₀², ignition | controlled coherence release |

**A concrete example table** — the identity tuples (constants) of a handful of
regimes, with state being the position and all behavior in §3 following:

| Regime | ξ (gravity chord) | ω₀² (resonance) | θ_c (condense) | n (rung) | Emergent signature |
|---|---|---|---|---|---|
| **Water** | low (couples weakly) | low (weak lock) | mid | shallow | flows to level, tensile ~0, conducts slowly |
| **Sand** | mid | mid | mid | shallow–mid | falls, piles at a μ-set angle, digs a scar |
| **Stone** | mid | mid | mid–high | mid | solid, blocky, mid hardness, slow conduction |
| **Diamond** | high | high | very high | deep | very hard (deep rung), fire-resistant, high fuel-if-ignitable, high ω₀² conduction |
| **Obsidian** | high | very high | high | deep (resilient) | very hard, ignition-resistant (ε² stays ≥ low), cold |
| **Fire regime** | — (a front, not a seat) | high (fast lock) | — | shallow | self-sustaining organized-perturbation front @ c_s |
| **Explosive** | high | — (primed) | very high, ε²≈0 | deep (full-cascade-primed) | stable until perturbed, then full discharge |

Water and sand are the *same law with different constants* — no per-material
`flow` / `fall` flag. Diamond and obsidian differ in hardness/ignition because
their ω₀² / n differ, not because a table says "obsidian : 50 hardness". Fire
and TNT are the *same* coherence-release mechanism at different rates
(controlled front vs full-cascade discharge). This is the collapse: the rule
table's N(behavior)×M(material) matrix becomes M constant-tuples and one law.
**[assumption]** The concrete magnitudes (which exact `ω₀²`/`n` value makes
water spread vs sand pile) are uncalibrated placeholders — the *semantics* are
the design, the *numbers* are Phase-1 tuning.

---

## 7. Honest open questions

1. **Which constants can the engine's real terms actually drive?** Engine-real
   today: ρ, q, ε² (`vel[].w`), `ω₀²` (PC param), ξ (`xi`), condensation
   threshold, the source terms, the river law, and all three RealSim
   dissipation terms (drag/viscosity/friction). The **dissipation terms are
   per-particle, not per-material** — the engine has one global γ, ν, μ for the
   whole run. Giving *different materials* different γ/ν/μ (sand piles at `μ_s`,
   water at `μ_w`) is **not engine-verbatim**: it needs a per-material
   coefficient read at the sampler/particle level, or a field-dependence in the
   dissipation that the shader does not currently evaluate. **This is the
   single largest feasibility gap**: without per-regime γ/ν/μ, sand and water
   cannot *behave differently* from the same law — they reduce to "one
   material with different thresholds," which is materially (pun) weaker.
2. **ε²-injection for heating.** The engine derives ε² as output; heating
   (raising ε² at fixed ρ) is a source-term [design] not present in the PDE
   today. Feasible (it mirrors `source_ey`), but the *thermal carrier rate*
   needs the `ω₀²`-driven re-lock to be measurable — otherwise heat is just
   ε² fading and "conduction" is unverifiable as a distinct quantity.
3. **Per-material ω₀² and ξ in one field.** The engine's PC has *one* `omega2`
   and *one* `xi` for the whole grid. Different materials = different values,
   but the PDE runs one parameter set. Driving per-cell constants means the
   material identity enters as a *per-cell field* (sampled like ρ/q/ε²) feeding
   `ω₀²`/xi into the per-cell update — a structural change to the PDE's PC
   contract, not a config dial. Must be designed before Phase 1, or Phase 1
   shows *one* regime (living terrain with no material differentiation).
4. **Explosion as a new pass.** Full-cascade discharge (directional stored-
   coherence release) is not engine-verbatim — the merge lineage condenses but
   never detonates. Adding it is a bounded new pass on the condensation
   scanner's lineage, but it is *new engine code*, not the existing chain.
5. **Hardness→rung constant mapping.** The rung *semantics* are grounded
   (volumetric-terrain's tool rule); mapping each vanilla hardness to a
   specific `n` is a tuning table (§4). Not a blocker, but it must be honest
   that the *numbers* are design.
6. **Conduction as a distinct observable.** Since heat = ε² and conduction =
   ε² draining along ∇q, "conduction" is not separable from the law's ordinary
   diffusion unless a *measurable* thermal carrier (temperature proxy) is
   defined. The doc proposes ε² budget; whether that is a usable gameplay
   quantity (does hot-wire visibly differ from cold high-ε²?) needs a Phase-1
   probe.

---

## Feasibility verdict

The **architecture is sound and the collapse is real**: solid/liquid/gas,
conduction, conductivity, ore, hardness, and the fire/explosive distinction all
follow from `(ρ, q, ε², energy) + (ξ, ω₀², θ_c, n)` under the existing two-fluid
law, river law, and RealSim terms — the dual-world grid of
`chunk-field-quantization` already samples everything the material system
needs, and the async seam of `async-field-domain` already carries the one
feedback channel (player/tool perturbation) combustion and mining both ride.

**The Phase-1 slice is feasible *for a restricted form*: showing the field
mechanics (condense, heal, granular pile from river + global-μ, ore by q
accumulation, hardness-by-rung on precision tools) with a *single* global
parameter set.** That deliverable is achievable within the existing engine +
the quantizer's thresholds; it demonstrates the *state machine* and the
*hardness/ore* claims with engine-real terms.

**The full Powder-Toy collapse (distinct materials behaving differently) is
NOT deliverable today**, because material *differentiation* requires either
(1) per-material dissipation coefficients (γ/ν/μ) or (2) per-cell ω₀²/ξ feeding
the PDE — both structural engine additions, not config. Without one of them,
every material is the same law with only threshold differences, and sand-vs-
water-vs-coal collapse to "one regime, different θ_c," which is not the thesis.

**Binding risks, in order:** per-material γ/ν/μ (the sand-vs-water distinction
— the load-bearing differentiator), per-cell ω₀²/ξ in the PDE (without which
there is no material identity in the field), then the [design] bits (ε²
injection, explosion pass) which are bounded additions. Recommend Phase 1 scope
= **single-regime living terrain + hardness-by-rung + ore-by-q + granular pile
from river + global RealSim μ**, with the per-material-constants extension as
the explicitly-gated Phase-1.5 so the material system is not conflated with the
terrain demo. That slice is achievable; the full table collapse is honest
sequential work on top of it.

---

## Cross-references

Documented consumers (all relative paths):
- [`the-working-song.md`](./the-working-song.md) — **the forge-chant's line.** §3b there
  reads this doc's §3 fire-vs-explosive rate boundary — a controlled discharge held *at*
  the line by the rhythm (the forge-chant paces a smith's discharge within it). Reverse
  pointer: the working-song holds the forge's discharge on this doc's line.
- [`the-tool.md`](./the-tool.md) — **the bite.** §4 hardness = rung (a tool's bite is its
  rung-depth); §2 the regime tuple the alloy *is* — the material stack the tool's bite
  lands on. Reverse pointer: the tool is this doc's regimes made a work object.
- [`the-fallow.md`](./the-fallow.md) — **the mined vein gone forever.** §3 the
  precipitation law — a worked deposit leaves a locality with `q` spent, `ε²` raised —
  the one-way depletion (the fallow's §2a). Reverse pointer: the fallow reads this doc's
  precipitation at its spent end.
- [`the-sea.md`](./the-sea.md) — **the liquid regime.** §2 Liquid = `ρ ≥ θ_c` with `ε²`
  above the solid floor — the phase this doc gives character as the sea's plain. Reverse
  pointer: the sea is this doc's liquid regime made the vertical's middle.
- [`the-bedrock.md`](./the-bedrock.md) — **the maximal rung.** §2a there reads §4 this
  doc's hardness-is-n (no alloy's rung exceeds the bedrock's — it is the maximal-
  rung regime the ladder descends to) and §3 the precipitation law (everything that
  precipitates, precipitates onto the bedrock). Reverse pointer: the bedrock is the
  deepest rung the ladder holds.
- [`the-landform-name.md`](./the-landform-name.md) — **the named regime at scale.**
  §2.1 there reads §4 this doc's hardness-is-n (a mountain is a large deep-rung
  condensation named the way a house is) and §4.3 reads §3 the precipitation law (the
  mined-away mountain's fallow). Reverse pointer: a mountain is this doc's deep-rung
  regime read as a named land.
- [`the-compost.md`](./the-compost.md) — **the re-precipitation.** §3 there reads the
  precipitation law (the field's own conservation the Compost assists), §4 hardness =
  rung (the worn steel's bite). Reverse pointer: the compost assists the regime's
  re-precipitation.
- [`the-climb.md`](./the-climb.md) — **the readable handholds.** §4 there reads
  hardness-as-rung (a deeper-`n` face holds its lock against perturbation — good
  holds); the face's `q`/`ε²`/rung read as holds. Reverse pointer: the climb reads
  the regime's handholds.
- [`the-spring.md`](./the-spring.md) — **the fixed re-precipitation.** §3 there reads the
  precipitation law — the field's own conservation the spring is a fixed instance of;
  §4 the mining perturbation that spends a worked locality. Reverse pointer: the
  spring is the regime's fixed re-precipitation.
- [`the-quarry.md`](./the-quarry.md) — **the exposed rung-layers.** §2/§4 there reads
  hardness = rung and the regime ladder; §3 the precipitation law (a vein is a
  `q`-accumulation); §7 the Phase-1.5 constants. Reverse pointer: the quarry exposes
  the regime's rung-layers.
- [`the-orchard.md`](./the-orchard.md) — **the rung-growth.** §2/§4 the regime ladder (the tree’s depth is a rung-growth). Reverse pointer: the orchard’s standing trees grow down the regime’s rungs.
- [`the-meteor.md`](./the-meteor.md) — **the rung’s impact.** §2/§4 the regime ladder (the meteor deposits deep-rung matter). Reverse pointer: the meteor strikes the regime’s rung-layers.
- [`the-lightning.md`](./the-lightning.md) — **the regime’s discharge.** the material register the flash rides. Reverse pointer: the lightning is the material regime’s discharge — the field’s own extreme, never free.
