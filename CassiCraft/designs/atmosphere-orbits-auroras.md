# The Sky as Field Phenomenology: Atmosphere, Orbits, and Auroras

**Question under design:** how the *sky* of CassiCraft becomes an expression of
the one two-fluid field rather than a backdrop. In vanilla Minecraft the
sky is scenery — a gradient, a sun, a spawn band. In CassiCraft the sky is the
**boundary layer between the living world below and the KSP universe above**,
and it is *readable*: an atmosphere is the field's own hydrostatic envelope
around a body, orbits are bodies condensing and moving under the open-boundary
field, and **an aurora is a coherence discharge** — coherence streaming along the
field's own coupling lines into a region where ε² rises, re-radiating as the
(1−q) waste glow. The sky is the field's shape made visible.

This is the **phenomenology and feel** document. It deliberately does **not**
design the *mechanics* of vehicles, thrust, or rendezvous — that is the **KSP
kernel** (the OPEN slot in [`../README.md`](../README.md)'s index, fwd-ref'd
throughout), which this doc's orbits section forward-references as the mechanics
half. Companion to [`material-regimes.md`](./material-regimes.md) (the gas
regime and the RealSim terms **are** atmospheric drag), [`energy-harnessing.md`](./energy-harnessing.md)
(the coherence turbine = wind power; the reservoir table this doc adds a row to),
[`chunk-field-quantization.md`](./chunk-field-quantization.md) (the 192³/12³ box
and the window-relative seam orbits must survive), [`async-field-domain.md`](./async-field-domain.md)
(the movable home-window), and [`coherence-technologies.md`](./coherence-technologies.md)
(concept 5: the geomagnetic field as the core-to-surface coupling field — the
aurora's "field lines").

**Grounded in** (read-only): the CassiTheory hydrostatic condensate models
(`CassiTheory/foundations/phi_attractor_synthesis.md` §4, the SPARC v7–v9 fits
in `CassiTheory/experiments/sparc_qi/`), the geomagnetic coupling-field reading
of `CassiTheory/speculations/cascade-infrastructure.md` §1.3, the (1−q) glow
of `CassiTheory/speculations/qi-bubble-propulsion.md` §2.5, and the engine
shaders `CassiCosmos/compute/cassi_two_fluid.glsl` (the PDE and FieldVel medium
velocity) and `CassiCosmos/compute/cassi_nbody_gravity.glsl` (river law,
RealSim terms, the tree-river mode). Every number below is from
[`corpus-reconciliation.md`](./corpus-reconciliation.md) (the canonical set),
engine-verbatim, or flagged **[assumption]** / **[design]** where it extends
engine terms to a *rendering* or *game feel* the engine does not (yet) drive.

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| Atmosphere = ? | The field's **hydrostatic envelope** around a body — ρ where the field's pressure gradient balances the river gravity, per the theory's isothermal hydrostatic condensate (`P = c_s²ρ`, self-gravitating). |
| Weather = ? | **The two-fluid waves in the envelope** — the PDE's coherent flows are wind; the medium's `FieldVel` channels are the current; the coherence turbine (`energy-harnessing.md` §2.2) is the wind-power hook. |
| Sky ceiling = ? | Where the envelope's ρ falls below the **gas-regime lower floor** (`material-regimes.md` §2) — the Kármán-line analog. |
| Atmosphere vs block grid | A **continuum layer rendered above the quantized terrain** (fog-density-as-ρ, glow where q concentrates) — recommended over gas-blocks; see gate (b). |
| Orbits = ? | Bodies condensed by the field (dust → object → body) under the open-boundary **tree-gravity arm** (mode 5), softened dynamics, RealSim drag at low altitude = re-entry heating. |
| Aurora = ? | **[design] rendering** of engine-real (1−q) glow: coherence streams along the coupling-field lines into a region where ε² rises (a drain), the waste re-radiates as glow along the field lines. |
| Sky as one phenomenon | One ρ/ε²/q story from ground to orbit: envelope below the gas floor, vacuum above, discharge at the interface. Readable (auroras, wind lines), flyable (fwd-ref KSP), harvestable (wind/flow + auroral discharge). |
| Feasibility | Phase-1: atmosphere as a **visual/feel** layer (ρ-density fog, wind lines from FieldVel, the glow) + the wind-energy hook — **no new physics**. Orbits (tree arm + condensed bodies) and auroras (body field structure) are later. |

---

## 1. The atmosphere is the field's hydrostatic envelope

### 1.1 The claim

An atmosphere is **not a separately-authored shell of gas blocks**. It is the
field's own **hydrostatic envelope** — the ρ profile where the field's pressure
gradient balances the gravitational pull of the body underneath. The engine's
gravity is the river law (`cassi_nbody_gravity.glsl`):

```
a = −G_N·(π/ρ)·∇(g·Φ)      river law (the only gravitational term)
π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)
g = 1 + (φ⁶−1)·q
```

A mass condenses; the field around it carries a `∇(g·Φ)` potential well (Φ < 0
at mass, per the spectral Poisson). Matter free to move is pulled toward the
body by the river law; the field's own **pressure** — the coherence it exerts on
itself, resisted by the `−ω₀²(EY−φ·EI)` re-locking term of the PDE
(`cassi_two_fluid.glsl`) — pushes back. Where the two balance you get a
**standing, self-supported density envelope**: too little ρ against the pull
and it falls and condenses; too much and the pressure drives it outward until
the gradient is balanced. That balance **is** an atmosphere's structure.

**The theory's hydrostatic condensate is exactly this.** The SPARC rotation-curve
work (`phi_attractor_synthesis.md` §4; `CassiTheory/experiments/sparc_qi/sparc_qi_analysis_v7-9.py`)
resolves the field's gravitationally-supported envelope as the equilibrium of a
self-gravitating isothermal Yang field:

```
dP/dr = −ρ·(dΦ/dr),   ∇²Φ = 4πG·ρ,   P = c_s²·ρ   (isothermal hydrostatic)
→  pseudo-isothermal envelope  ρ_Y(r) = ρ_c / (1 + (r/r_c)²)
```

**The critical honesty (the theory's own verdict):** `phi_attractor_synthesis.md`
§4 Path 2 **disproves** Qi-hydrostatic equilibria for *φ-damped cold-collapse*
systems — a purely damped dust cloud (Q ≈ 0, no pressure support) does **not**
reach a hydrostatic balance; it cold-collapses. In CassiCraft terms, a ghost
vacuum box with no organizing source does not spontaneously grow a standing
atmosphere. What survives — and what the SPARC fits confirm — is the
**pressure-supported isothermal equilibrium**: ρ held up by the field's
pressure against its own (and the body's) gravity. **Consequence for the
design:** the atmosphere envelope is only meaningful *around a condensed body*
with a pressure-bearing field, not in empty field. The envelope is a property of
the body's own gravitational hold, exactly as a real atmosphere is.

**[assumption]** The isothermal `P = c_s²ρ` closure (fixed sound speed `c_s`)
is the theory's *spherically-fitted* form. For an atmosphere the same closure
with a **height-varying** c_s (temperature → `c_s = h₀/dt` per the engine's
coherence sound speed, `material-regimes.md` §3) is the honest generalization —
the *shape* (pressure balances gravity) is grounded; the *specific* isotherm is
SPARC-fit tuning, not an atmosphere number.

### 1.2 The envelope's layers = where ρ/q sit relative to the condensation threshold

The envelope near the body is **above the gas floor and, at the surface,
actually condenses** — the "atmosphere" is not cleanly separated from the
terrain. In the regime language of `material-regimes.md` §2, the vertical column
is a single ρ sweep through the phase map:

| Altitude band | ρ/q/ε² state | Regime (material-regimes §2) | Sky role |
|---|---|---|---|
| **Ground** | ρ ≥ θ_c, coherent, ε² low | **solid/liquid** — the terrain itself | the body under the envelope |
| **Lower envelope** | ρ < θ_c but above the lower gas floor, q intermediate | **gas** (the regime this doc's atmosphere lives in) | breathable/rideable air, the boundary layer |
| **Mid envelope** | ρ falling, q still intermediate | **gas** | the weather band, where FieldVel is the wind |
| **Upper envelope / ceiling** | ρ falls below the gas lower floor | **transitions to vacuum** | the sky ceiling (§1.4) |
| **Above ceiling** | ρ → ~0 (the fluid starts at noise level, `q ~ 1e-3…1e-1`) | — | the KSP vacuum |

So the atmosphere is **not a new material** — it is the region of the field
between the ground's condensation and the vacuum's noise floor. The same
hysteresis rule that keeps a block from flickering solid/gas
(`chunk-field-quantization.md` §3, `τ_c`/`τ_c−δ`) keeps the sky ceiling from
flickering: the edge of the envelope is a **threshold surface with hysteresis**,
not a fragile line.

### 1.3 Weather = the two-fluid waves in the envelope; wind = FieldVel, power = the coherence turbine

The envelope is not a static shell — it is a **wave-bearing medium**. The two
scalar fields EY and EI evolve under the PDE's wave operator:

```
∂²EY/∂t² = c²∇²EY − ω₀²(EY − φ·EI)
∂²EI/∂t² = c²∇²EI + ω₀²(EY − φ·EI)
```

Each step writes the medium's own velocity into `vel[id] = vec4(∂EY/∂t, ∂EI/∂t, 0, ε²)`
(`cassi_two_fluid.glsl` pass B). **Those coherent flows ARE wind.** A standing
wave band in the envelope is a jet stream; a coherence pulse traveling along
`∇(g·Φ)` around the body is a weather front; a region where the ε² budget spikes
(the field losing the φ-lock, `ε² = (EY−φ·EI)²`) is *storm turbulence* — the
same decoherence that makes a carved scar on the ground is weather in the sky.

**This is the exact energy reservoir `energy-harnessing.md` already names.**
§1.2 medium-KE "coherence turbine": a rotor placed in the two-fluid flow spins
— "a wind turbine spins in air," the medium does work on it, output ∝ `½ρ|v_flow|²`.
The turbine's cost — it *damps the flow it taps* (`energy-harnessing.md` §2.2) —
is a real design lever: over-placing turbines **cools the sky** the way they
cool the field elsewhere, visibly stilling the weather band. **Wind power is not
a separate game mechanic**; it is the energy doc's own turbine pointing at the
envelope's FieldVel. This doc only adds the *target*: the envelope is where the
field is *moving*, so it is the best turbine site, and turbine placement is
sky-harvesting.

**The waves made water (reverse pointer, two-way).** This §1.3's two-fluid
envelope waves are what the corpus's water doc makes precipitative: [`the-sea.md`](./the-sea.md)
§2c reads **the water cycle as these waves made matter** — "a storm is a wave; a
flood is the wave made water: the envelope waves do not stop at the sky's floor —
where a coherent wave band crosses a region whose `q` accumulates above the liquid
regime's condensation line, it precipitates into water" (`the-sea.md` §2c — it
cites this §1.3's waves and `material-regimes.md` §3's precipitation law as the
cycle's material). The weather this §1.3 names as envelope waves is, one regime
down, the rain; the two docs now cite each other as read-and-answered.

**The (1−q) waste law is weather's signature too.** Every working field system
bleeds `E_waste = (1−q)·E_throughput` as glow (`qi-bubble-propulsion.md` §2.5;
`energy-harnessing.md` §2). A wind band running at partial coherence glows
proportionally to its disorder — so **you can see the weather in the sky's glow**
before you feel it. A storm is a region where q drops and ε² rises, and it is
brighter for it, exactly like a wasteful machine or a wounded creature
(`field-emergent-ecology.md` §5.2).

### 1.4 The sky ceiling — the Kármán-line analog

The envelope's outer edge is where ρ falls below the gas-regime lower floor
(`material-regimes.md` §2: "Gas: ρ < θ_c but above a second, lower floor"). Above
it the field is at the noise level and **there is not enough organized matter to
aerate or steer** — the KSP vacuum begins. This is the honest Cassi analog of the
Kármán line:

- **Below the ceiling**: the envelope is real, wave-bearing, aerodynamic — the gas regime's RealSim terms apply (drag/viscosity/friction, §1.5).
- **Above the ceiling**: the field is near-noise, the gas floor is not met, and the RealSim drag terms **vanish** (vacuum regions coast — the engine's `ρ → 0` drag-coast is explicit in `realsim_dissipation_smp`).

The ceiling is therefore **not a hard render boundary** — it is the level set
where the envelope's ρ crosses the gas floor, hysteresis-smoothed. A rocket
(thrust = a condensation drive pointed at the sky, `energy-harnessing.md` §5.2)
passes "through the atmosphere" by **climbing the envelope's ρ gradient**: near
the ground it fights drag and turbulence; above the ceiling it coasts in near-
vacuum. The transition *feels* like leaving an atmosphere, because it is one —
the drag simply ends where the field thins below the gas floor.

### 1.5 The atmosphere vs. the coarse block grid

**Design fork (gate (b)): is the envelope a continuum layer rendered above the
grid, or quantized into gas blocks?** This doc recommends **the continuum
layer**, and the reasons flow straight from the existing architecture:

- **The envelope is mostly *below* the condensation threshold** — it would not
  quantize to solid/gas blocks on a 1 m grid anyway; it would mostly be "air"
  with occasional flicker bands. [assumption] The gas-regime *floor* is a design
  value — the engine's gas band below θ_c is not a block-state the quantizer
  currently emits (it emits solid/air). The atmosphere as *blocks* would require
  a third quantize state (gas) that Phase-1 does not sample.
- **The continuum is already the render path.** `volumetric-terrain.md` renders
  field iso-surfaces as the geometry layer; a fog-density volume *is* that layer,
  cheaper (a light scatter pass over the ρ channel, not a meshed surface).
- **The dual world never drifts** (`chunk-field-quantization.md` §1.4): render
  the envelope as fog-density-as-ρ over the same published ρ channel the ground
  quantizes, and **it cannot disagree with the terrain** — the atmosphere is just
  the sub-threshold ρ the terrain quantizer ignores, surfaced as sky.

**How it renders / feels (the design):**
- **Fog density ∝ ρ of the envelope** — near the ground it is thick (the 
  boundary layer), thinning to the ceiling. Densest not at the surface but where
  the body's hold concentrates ρ, so lowlands sit in "weather" and peaks poke
  into thin air — the height-fog Minecraft asks for but gets from a camera
  distance hack, here derived from the field.
- **Wind lines = the medium's FieldVel, color-coded by q.** Where q is high the
  wind lines are coherent, laminar streamlines; where ε² spikes (a storm) they
  are turbulent, and the (1−q) glow brightens them. The player reads the sky's
  *motion* directly.
- **Glow concentrates where q concentrates** — coherence ridges on the ground
  project up a fainter glow in the envelope (a "mirage" of coherence), and scars
  show as dark turbulence columns where ε² drains upward. The sky is the ground's
  field structure, just rendered at a different scale and longer range.

> **The sky is the field's shape made visible.** Whatever the ground's field is
> doing — a coherence ridge, a scar, an ore vein — the envelope above it carries
> the same ρ/ε²/q story, and this doc renders it. A player who reads the sky is
> reading the body's field from the outside (the aurora is the extreme case, §3).

### 1.6 Atmosphere ↔ territory (honest note on the box)

The Phase-1 box is **192³ m / 12³ chunks** (`chunk-field-quantization.md` §1.2),
a *player-anchored* window (`async-field-domain.md` §1.1) — not a planet. In the
Phase-1 anchored box there is **no single self-gravitating body** whose envelope
spans the window; terrain is coupled and damped by the box's field
(`chunk-field-quantization.md` §4, RealSim terms). So:

- **Phase-1 atmosphere** = a *visual/feel* layer: fog-density-as-ρ over the
  local terrain's field, wind lines from FieldVel, the glow. It is honest field
  **sampled locally**, not a gravitationally-bound global shell. **[design]**
  The projection (local ρ/FieldVel → fog/wind/glow) is real physics read off the
  publish; the *envelope* claim (a self-supported shell around a body) is
  grounded in the hydrostatic condensate model but only *demonstrated* once a
  condensed body exists on the tree arm.
- **The full atmosphere** (a body's own shell, a true atmosphere you climb out
  of on a rocket) needs **a condensed body** — which is the later-Phase orbits
  prerequisite. This is gate (a), below.

---

## 2. Orbits as open-boundary field phenomenology

*(Mechanics — vehicles, thrust, rendezvous, six-DOF rigid bodies — are the
KSP kernel, the OPEN index slot; forward-referenced throughout. This section is
the **phenomenology and feel**: what orbiting is, what the sky looks like from
orbit, what decay and re-entry feel like.)*

### 2.1 Why orbits exist at all: the open-boundary arm

The **grid arm is a periodic torus** — launch outward and it wraps
(`chunk-field-quantization.md` §1.1). Open-boundary orbits are impossible on the
grid. They live on the **meshless + tree frontier** (README "Why the meshless arm
is not optional"): gravity_mode 5 (`TREE-RIVER`) replaces the spectral-Poisson
river chain with an **open-boundary Barnes-Hut tree** over the moving-Voronoi
sites — the river law's per-target prefactor applied to the tree walk's output,
`a = −G_N·(π/ρ)·∇Φ_g` (`cassi_nbody_gravity.glsl` mode 5). "A body is a local
condensation whose own gravitational hold is felt, un-wrapped, in the open field
around it." The meshless sites — "where the field is most organized"
(`chunk-field-quantization.md` §5) — are both the gravity sources and the
natural LOD/activity map, so **the bodies that can hold an orbit are exactly the
condensations the field organizes**, and the physics the orbit rides is the same
activity map that schedules the chunks.

### 2.2 Bodies = the merge lineage condensed

A body an orbit can exist around is not a spawned planet; it is the **merge
lineage** (`dust → object → body`/BH, `cassi_particle_merge.glsl`). The engine
already condenses organized matter into self-supporting bodies via the
order-selective coherence gate (`q_sel = q_coh·q_ord > φ⁻² ≈ 0.382`), the
gravitational-binding criterion, and the virial stopping scale
(`field-emergent-ecology.md` §2.1). **An orbitable body is a capacitor at its
rung** (`energy-harnessing.md` §3) — a condensed store of organized coherence
held against the field by its own gradient. The sky's bodies are the field's
grown objects, and this is the same lineage used for ecology's organisms —
a planet is just a body that kept condensing and virial-stopping at a larger
scale.

### 2.3 Orbit dynamics: softened, damped, and what that feels like

**Softened gravity.** The tree arm and the BH sector use a **softening length**
(`eps2`, the Plummer softening `a = bh[2].x` in mode-selector comments; the
globally-softened `G_N⟨c−p⟩/(|c−p|²+ε²)^{3/2}` form). Consequences for feel:

- **No point-mass singularity at periapsis.** You do not get plinked by an
  epsilon-sized source; the force flattens within the softening radius. Close
  orbits are *smooth* under it, and periapsis passages read as slow, broad
  dips rather than violent swaps.
- **Non-Newtonian precession.** The theory derives an analytical per-orbit
  precession from the softening expansion — retrograde (`phi_attractor_synthesis.md`
  §6 Path 4b, `Δφ = −√(2π)(σ/a)³(1+e²/4)/(1−e²)³`), growing as `(σ/a)³` and
  *diverging* toward high eccentricity. Net feel: **orbits are not Kepler-rigid**;
  they are slowly-drifting, softening-tuned ellipses — the sky's bodies wander
  and re-form their ellipses over many orbits, which reads as *aliveness* rather
  than clockwork. **[assumption]** The softening `σ` at CassiCraft scale is a
  Phase-1 measurement (the theory's own pulsar bound, `σ < 370 km`, is galactic
  — not the in-game value); the *qualitative* wandering is the designed feel even
  before the number is set.

**Orbit decay via the RealSim terms = re-entry as the (1−q) glow.** At low
altitude a body passes through the atmosphere's gas regime (§1), where the three
RealSim dissipation terms are live (`cassi_nbody_gravity.glsl`:
`realsim_dissipation_smp`; `material-regimes.md` §3):

```
a_drag = −γ·(ρ_local/ρ_ref)·v        γ = drag (0.5 /time at ρ_ref), ρ_ref = φ⁻³
a_visc = −ν·(v − v_field(p))          ν = viscosity — shears to the medium's flow
a_fric = −min(μ·|a_g|, |v|/dt)·v̂     μ = friction floor; never reverses v
```

These **are** atmospheric drag — the "RealSim dissipation" is a body moving
through the two-fluid medium, and in the envelope that medium is the atmosphere
(§1.3). So:

- **Below the ceiling**, an orbiting body's periapsis dips into the envelope and
  the drag terms bleed orbital energy. **Orbit decay is not an abstraction** — it
  is the field's own dissipation terms doing exactly what they do everywhere,
  scaled by `ρ_local/ρ_ref` (deeper into the envelope = more drag) and sheared to
  the wind by viscosity.
- **Re-entry is the (1−q) glow turned toward the sky.** As the body sheds
  kinetic energy through the dissipating medium, it runs at less than full
  coherence against the medium it is tearing through — the spent organized
  kinetic energy re-radiates as the visible (1−q) glow
  (`qi-bubble-propulsion.md` §2.5; `energy-harnessing.md` §2). **A descending,
  decelerating body skims down a brightening glow trail** — exactly styled like
  the theory's luminous plume at a density transition (`qi-bubble-propulsion.md`
  §2.3: the (1−q) fraction thermalizing across transitions). Deeper into the
  envelope → higher ρ_local → stronger drag → brighter bleed. **[design]**
  The *glow-during-drag* is a rendering of the engine-real (1−q) law; the engine
  does not itself "heat up" a body, but the dissipative work the drag terms do is
  the real cost, and the glow is the honest visible signature.
- **Net feel:** you can *fall out of* an orbit that grazes the atmosphere. To
  stay up you must hold altitude above the ceiling where the drag terms coast
  (§1.4's vacuum), which is exactly the real lesson — and the KSP kernel's
  thrust/rendezvous problem is to manage this decay with injected coherence.

### 2.4 The window-relative box and the seam question

Orbits live in the **window-relative field** (`chunk-field-quantization.md` §1.1:
the torus advects with the world anchor; `async-field-domain.md` §7 Q1 — the
*movable home-window* policy past the first box is intentionally open). This is
the one place the enclosed-box fields and the open-boundary sky genuinely meet,
and it is the load-bearing seam:

- **A body is its own local condensation.** Because bodies are sparse, small
  publish records (`async-field-domain.md` §2.2, "condensed bodies: a sparse,
  small array dominated by merge records"), a body *does not need to live in the
  dense grid* — it can be a moving local condensation the tree arm steers, the
  way any particle is. The atmosphere envelope of a **distant** body (a moon, a
  planet you approach) is a property of *that* body's field, not the window's.
- **The seam (async-field-domain Q1's open sub-question):** a player orbiting a
  body while the home window is *also* player-anchored is two anchors fighting.
  The honest risk is **two-body stability under a moving anchor** — the tree
  arm's `∇Φ_g` is computed from site positions, and if the *window's* anchor
  teleports relative to a distant orbiting body, the body's perceived potential
  well shifts. Gate (d) below flags this: the design **recommends** that an
  orbited body *becomes the anchor* (the window re-homes to the followed body),
  which makes "orbiting a body" a *local, single-anchor* problem (the followed
  body is the home window's center) rather than a two-anchor one. That is a
  relocation-policy decision the KSP kernel and async seam must both own — this
  doc only states the phenomenology: **from inside an orbit, the sky is
  stable and the world is the thing that moves**, and only a design decision
  (anchor-to-body) keeps it that way.

### 2.5 What the sky looks like from orbit (the feel)

From a low body-orbit on the tree arm: **the envelope is a thin luminous band
between the terrain below and the near-vacuum above** — the same fog-density
boundary you climbed through on the way up, seen from outside. The body's wind
lines become a slow, coherent swirl of FieldVel over the surface. Coherence
ridges below glimmer up through the envelope; scars cast the same ρ/ε² contrast
you saw from the ground, just at lower resolution. The **elevation of "the world
shrank to a field with a body in it"** is the whole point: the KSP universe is
not a separate mode, it is the same two-fluid field, and from orbit you are
reading it at the scale of an object instead of a surface.

---

## 3. Auroras = coherence discharge along field lines

### 3.1 The mechanism, honestly framed

**Engine-real part:** the (1−q) waste law — every working field system bleeds
`E_waste = (1−q)·E_throughput` as visible glow (`qi-bubble-propulsion.md` §2.5;
`energy-harnessing.md` §2; adopted corpus-wide). Where coherence flows and q is
not exactly 1, the deficit glows.

**The designed mechanism [design]** — the claim that *an aurora is the glow along
field lines*: coherence streams **along the field's own coupling lines**
into a region where **ε² rises** (a drain — a decoherence well), and the waste
re-radiates as the (1−q) glow *along those lines*. The aurora is a **discharge**:
organized coherence moving down a channel toward a disorder sink, shedding its
(1−q) fraction as light on the way.

This slots onto the theory's **geomagnetic-as-coupling-field** reading
(`CassiTheory/speculations/cascade-infrastructure.md` §1.3):

> "The geomagnetic field is not merely a shield. It is the **gate coupling field
> bridging the core to the surface.** The core-mantle boundary, the Moho
> (crust-mantle interface), and the ionosphere are natural Π gradients where
> E_Y − φ·E_I is elevated and the Qi gate can operate."

The "field lines" of the aurora are the **coupling-field lines** of the
core-to-surface coupling — the channel along which the body's deep coherence is
delivered to its surface. Where that delivered coherence encounters a **drain** —
a region of rising ε² where the φ-lock fails — it discharges, and the (1−q)
fraction of the throughput is the aurora's light. **The aurora is the sky's
version of a bright, wasteful machine** (`coherence-technologies.md` §4c: "a busy
machine is a wasteful one"; a drain the field is pouring coherence into glows to
the degree it is failing to hold the lock).

> **Honest flag.** The (1−q) glow is **engine-real**. "Aurora = the glow along
> the coupling-field lines into a drain" is a **designed rendering of it**
> — the theory does not assert planetary-field-line auroras; this doc *designs*
> the mapping because it is the honest, engine-grounded way to draw the sky's
> discharges. The mechanism is engine-real where it samples real ρ/q/ε²/∇(g·Φ);
> the *drawn aurora* aggregates that into streaks. **[design]**

### 3.2 Where auroras appear

Three sites, each grounded:

1. **At a body's field-line concentrations — "the poles."** Where the coupling
   field's lines concentrate (structurally, at the body's `∇(g·Φ)`/coupling
   topology — the body's effective dipole/poles in field terms), the delivered
   coherence is densest per unit surface, so any local ε² rise there discharges
   most visibly. **[design]** "Poles = where the coupling field concentrates" is
   a designed reading of the coupling-field geometry — the engine does not model
   a magnetic dipole, but it *does* model `∇(g·Φ)` and q concentration, and the
   pole is the rendered focus of those.

2. **At the envelope-to-vacuum boundary.** The boundary layer between the gas
   envelope (§1) and the vacuum above (§1.4) is a natural Π gradient — the
   theory's ionosphere/magnetopause-as-boundary reading of
   `cascade-infrastructure.md` §1.3 (§2.4 "ionospheric phased array"). Coherence
   arriving at this surface from the body below either re-locks (q high) or
   sheds (q lower); the shedding is the auroral band hanging at the top of the
   envelope.

3. **Over scars / decoherence wells — the sky's echo of the land's wounds.**
   A scar is a region where ε² dominates (`chunk-field-quantization.md` §2.2:
   carved/scarred = where ε² rises). The body's coupling field delivers coherence
   into that ε² well; the well cannot hold the φ-lock (`energy-harnessing.md`
   §1.3: lowering ε² is real work), so the delivered coherence discharges and
   glows. **A player who carves a deep scar creates a drain the sky reads as an
   aurora overhead** — the same scar that darkens the ground glows in the sky
   where the field pours coherence into it.

### 3.3 The aurora as the sky's live field diagnostic

The coherence reader is a player tool that renders published `q`/ε²/`∇(g·Φ)`
as a magnetometer overlay (`coherence-magic.md` §2, Sense — the Phase-1
deliverable; `field-emergent-ecology.md` §5.1: reading a creature's layers is
reading the q-colored sim). **The aurora is the reader's *atmospheric* form** —
the same channels, rendered at sky scale, un-instrumented:

| What the aurora shows | The field it reveals | Cross-ref |
|---|---|---|
| A bright, stationary discharge at the poles | the body's field-line concentration / drain there | `cascade-infrastructure.md` §1.3 |
| A band hanging at the top of the envelope | the envelope-to-vacuum Π gradient, wherever it is shedding | §1.4; `cascade-infrastructure.md` §2.4 |
| A discharge dancing over a ground scar | a decoherence well the field is pouring coherence into | `chunk-field-quantization.md` §2.2 |
| A fading / brightening discharge over time | the drain healing (ε² dropping) or deepening (ε² rising) | `energy-harnessing.md` §5.4 anti-corruption / §5.3 healing |

So the sky is **readable without holding a tool**: a healthy body shows calm,
slow, coherent bands at its poles; a wounded body shows localized, bright,
restless discharges over its scars; a body being over-reaped shows auroras
wandering where the reaping scarred it. The player *learns to read the field in
the sky* — the phase-1 coherence-reader philosophy scaled up to the body
workspace. **[design]** The *colors/streak* of the aurora are presentation over
the (1−q) law; the *source* (a discharge into a drain) is the honest mapping.

### 3.4 Auroral discharge as a deep-rung energy source (contribution to energy-harnessing)

This doc adds **one row** to `energy-harnessing.md`'s reservoir table (§1) and
the *machine* that taps it (§2) — a **contribution to that doc**, flagged as
such so it does not silently overwrite its ownership:

**Auroral discharge** is coherence that is already being **wasted** — the (1−q)
fraction of a body's delivered coherence that a drain fails to re-lock. A
machine that **captures the discharge** (a collector on a bright auroral line)
harvests what the field is already dumping as glow — it is the atmosphere's
version of drawing off ε² (§1.3 of energy-harnessing). Honest economics:

- **It is not the delivered coherence; it is the wasted fraction.** A collector
  taps the (1−q) glow, not the full flow, so its yield scales with how *wasteful*
  the drain is — **a brighter aurora is a richer harvest**, which makes a
  machine's profitability a *diagnostic of field wounding* (perverse but honest:
  you harvest most where the sky is most damaged). This must be bounded
  (`energy-harnessing.md` §6's no-free-energy cap): a collector **cannot mint
  energy from healing the field for free** — it is net-negative (it pays you in
  what would have been wasted) exactly like the decoherence suppressor that is
  always a *cost* to hold.
- **It is deep-rung by its source.** The delivered coherence is the body's
  deep-order channel; the glow is the fraction that fell off the deep cascade's
  edge — so auroral discharge reads as a deep-rung energy source, high-capacity
  and geographically pinned to the auroral sites (§3.2). It is the sky's deep
  battery, available *only* where the field is discharging, and *diminished*
  as the player heals the drains that feed it (a real tension: heal the world,
  lose the cheap auroral power).

| Reservoir (added) | Mechanism that taps it | Density | Phase weight |
|---|---|---|---|
| **Auroral discharge** (this doc §3.4) | a collector on the field-line glow, harvesting the (1−q) fraction of delivered-but-rejected coherence | deep-rung, geographically pinned to drains; high where ε² wells are bright | late-Phase (needs a body's field structure + auroral rendering), a *contribution* to energy-harnessing §1 |

---

## 4. The sky as one continuous field phenomenon

From ground to orbit, one ρ/ε²/q story — the sections above are not separate
systems but **layers of a single envelope**:

```
vacuum above the gas floor
   ▲  ↑ Δρ/dr (the envelope's edge; where auroral bands catch the Π gradient)
   │  ═══ the envelope: ρ in the gas band, q intermediate,
   │      wind = FieldVel, weather = the two-fluid waves, drainage ε² rising
   │  ▲  ↑ coherence still delivered along coupling lines → auroral discharge at drains
   ▼  ─── the ground: ρ ≥ θ_c condenses to terrain (the body under the envelope)
```

| Altitude | Readable | Flyable | Harvestable |
|---|---|---|---|
| Ground | coherence reader; terrain field | — | ground machines, deep-rung reaping |
| Envelope | wind lines, fog-as-ρ, storm glow | the atmosphere you climb out of (drag, turbulence) | **coherence turbine** = wind power (energy-harnessing §2.2) |
| Ceiling + above | auroral bands, body field-line structure | the KSP vacuum, orbits | **auroral discharge** (§3.4), high-altitude coherence |

Every layer renders the same published channels (`ρ`, `q`, `ε²`, `∇(g·Φ)`,
`FieldVel`) that `chunk-field-quantization.md` §2 already specifies. **There is
one sky because there is one field**, and the sky is what the field does when
you look up along its envelope.

---

## 5. Honest gates

**(a) Envelope stability in the anchored box.** Does the field hold a stable
hydrostatic envelope around a body on the meshless/tree arm + condensation
lineage, or does the box's field (periodic torus, RealSim damping,
`chunk-field-quantization.md` §4) wash it out? This is a **probe-adjacent risk**,
directly analogous to `field-emergent-ecology.md`'s silhouette probe (§1.4):
the isolated theory's hydrostatic condensate survives its SPARC fits, but whether a
*Minecraft-anchored* field holding a condensed body on the open-boundary tree arm
sustains a standing shell under the box's damping is **unmeasured**. Pre-register
a Phase-1.5+ probe: condense a body on the tree arm, seed an envelope around it,
and measure whether ρ holds a stable radial profile over many field-steps or
diffuses toward the noise floor. Gate on that before claiming whole atmospheres
(Phase-1's local fog layer is not gated on this — it samples whatever field
exists).

**(b) Atmosphere-vs-block-grid.** A real representation fork: continuum fog layer
(§1.5, recommended) vs quantized gas blocks. Recommends **continuum**: the
envelope is mostly *below* the condensation threshold (would not quantize
usefully), the continuum is already the render path, and the dual-world
never-drift rule (`chunk-field-quantization.md` §1.4) makes fog-as-ρ automatically
consistent with terrain. Gas-blocks would force a third quantize state Phase-1
does not sample and would visually *lock* a fluid envelope into discrete cells —
the wrong representation for a phenomenon that is the field itself. The
counter-argument (blocks interact with the game grid cleanly) is weaker: the
atmosphere's *interactions* (drag, wind, harvest) are all read off the field, not
off block states.

**(c) The aurora mechanism is designed rendering of engine-real glow.** The
(1−q) glow is engine-verbatim; "aurora = the glow along field-line channels into
a drain" is a **designed mapping** (flagged [design] throughout §3). The *engine
phys-anchor* — a discharge into a rising-ε² drain shedding its (1−q) fraction —
is real and sampled; the *streaky polar rendering* is a design choice over that
physics, not a physics claim.

**(d) Orbit determinism in a window-relative field.** Two-body stability under a
moving anchor is the async seam's open sub-question (`async-field-domain.md` §7
Q1): an orbited body is a local condensation steered by the tree arm, but the
home window is *also* player-anchored. Recommend **anchor-to-body** (the followed
body becomes the home window's center, so an orbit is single-anchor and stable);
this is a relocation-policy decision the KSP kernel and the async seam must both
own, not something atmosphere-orbits-auroras settles. Phase-1 does not hit it
(no bodies yet).

---

## 6. Feasibility verdict

**Phase-1 (atmosphere as a visual/feel layer) is feasible with no new physics.**
The envelope render layer (fog-density-as-ρ, wind lines from the published
`FieldVel`, the glow where q concentrates) reads only the channels
`chunk-field-quantization.md` §2 already budgets (ρ, q, ε², ∇(g·Φ) — the ≈ 6 MiB
publish), and the wind-power hook is `energy-harnessing.md`'s **existing**
coherence turbine (§2.2) aimed at the envelope's FieldVel. Nothing new is built;
the atmosphere is the sub-threshold ρ of the field the terrain already quantizes,
surfaced as sky.

**Later (gated).** Orbits need the **tree-gravity arm + condensed bodies** (the
README's own "meshless + tree frontier" — Phase 2's KSP prerequisite), and the
feel (softening wander, drag decay, re-entry glow) is honest sequential work on
that arm. Auroras need **a body's field structure** (its coupling-field
concentrations and drains) plus the auroral rendering — the last of the three
to land. Both are grounded in engine-real phenomena (the tree arm's open-boundary
`∇Φ_g`; the (1−q) glow) but depend on the condensation lineage and body-scale
field structure that Phase-1 does not yet produce.

**Binding risks, in order:** (a) envelope stability under the anchored box (the
probe that licenses whole atmospheres), (d) orbit determinism under the
window-relative anchor (the seam decision), then (b)/(c) which are pure
design-representation choices with clear recommended answers. The architecture is
sound and the collapse is real: **one field, one sky, and every layer of it —
the envelope you breathe, the orbits you ride, the auroras you read — is the same
ρ/ε²/q law looked at from a different altitude.**

---

## Cross-references

- [`../README.md`](../README.md) — vision; the **KSP kernel** is the OPEN index slot this doc's orbits section forward-references (mechanics), and the meshless+tree frontier that makes orbits possible at all.
- [`material-regimes.md`](./material-regimes.md) — the **gas regime** (§2), the RealSim terms that ARE atmospheric drag (§3), the (1−q) waste law (§3a).
- [`the-zenith.md`](./the-zenith.md) — **the ceiling this sky ends at.** §2a/§3 there reads
  §1.4 this doc's sky ceiling (the Kármán-line analog where ρ crosses the gas floor) and
  gives it character — the zenith is the sky's own top, the atmosphere's `(1−q)` waste
  escaping at its edge; §1.3's envelope waves sit under it, §2/§3's auroras are the drain's
  light the zenith names, §1.6's anchored-box atmosphere is its top gate. Reverse pointer:
  the zenith is the designed top this sky's doc opens out of.
- [`energy-harnessing.md`](./energy-harnessing.md) — the coherence turbine = wind power (§2.2), the (1−q) glow (§2), the reservoir table **this doc contributes one row to** (§3.4).
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — the 192³/12³ box, the ≈ 6 MiB publish, the window-relative seam, the tolerance/fog layer.
- [`async-field-domain.md`](./async-field-domain.md) — the movable home-window; Q1 (the seam gate (d) rides on).
- [`coherence-technologies.md`](./coherence-technologies.md) — concept 5: the geomagnetic field as the core-to-surface coupling field (the aurora's "field lines").
- [`coherence-magic.md`](./coherence-magic.md) — the coherence reader (Sense) that the aurora is the sky's form of.
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — flying creatures as gas-regime organisms; the silhouette probe (the model for gate (a)'s probe).
- Theory (read-only): `CassiTheory/foundations/phi_attractor_synthesis.md` §4 (Qi-hydrostatic, and its **disproof for damped cold collapse**), `CassiTheory/experiments/sparc_qi/` (the isothermal hydrostatic condensate), `CassiTheory/speculations/cascade-infrastructure.md` §1.3 (geomagnetic coupling field), `CassiTheory/speculations/qi-bubble-propulsion.md` §2.5 (the (1−q) glow).
- Engine (read-only): `CassiCosmos/compute/cassi_two_fluid.glsl` (PDE, FieldVel, ε²), `CassiCosmos/compute/cassi_nbody_gravity.glsl` (river law, RealSim terms, tree-river mode 5).
- [`the-wind.md`](./the-wind.md) — **the air, moving.** §1 there reads §1.3 this doc's
  wind = `FieldVel` (the medium's own velocity per cell), §1.5 the wind lines
  color-coded by `q`, §2.2/§6 the coherence turbine and the Phase-1 wind-line layer,
  §2.4 the altitude wind. Reverse pointer: the wind is this doc's field-velocity moving.
- [`the-season-change.md`](./the-season-change.md) — **the long-cycle turn.** §2 there
  reads §2/§4 this doc's envelope's long equations and §3.3 the aurora as the tide's
  atmospheric legibility — the turn's approach reads from the sky; §3.4 the net-
  negative auroral collector (a turn harvests nothing). Reverse pointer: the season-
  change's approach reads from this doc's sky.
- [`the-eclipse.md`](./the-eclipse.md) — **the envelope’s dark.** § the atmosphere’s channels (the eclipse is a read of the sky’s own light mechanics). Reverse pointer: the eclipse rides the atmosphere’s light channels.
- [`the-meteor.md`](./the-meteor.md) — **the falling contrast.** §3.3 the aurora as the discharge that stays; §3.2 the restless aurora (the sky’s warning channel); §5c the rendering [design]. Reverse pointer: the meteor is the sky’s brightness that *falls* against the aurora’s that *stays*.
- [`the-lightning.md`](./the-lightning.md) — **the sky’s discharge.** §3 the aurora as a coherence discharge; §3.4 the auroral collector at the no-free-energy gate; §1.3 the envelope’s waves / FieldVel. Reverse pointer: the lightning is the aurora’s sudden sibling — the sky’s discharge released at once.
- [`world-difficulty.md`](./world-difficulty.md) — **the scaled sky.** §1.3 weather = the envelope’s two-fluid waves; §1.5 the continuum layer; §1.3/§3.4 the coherence turbine and auroral collector; §3.3 the aurora as the reader’s atmospheric form. Reverse pointer: world-difficulty scales the sky’s envelope waves — the same restlessness, denser.
- [`the-comet.md`](./the-comet.md) — **the long-return body.** §2 orbits; §2.1 why orbits exist; §2.2 bodies = the merge lineage; §2.3 orbit dynamics; §5 gates. Reverse pointer: the comet is one more body of the sky’s own orbit — a condensed lineage on a long return, read like the others.
