# Custom Blocks as Authored Field Regimes

**Question under design:** how "creating a custom block" works in CassiCraft. In
vanilla modded Minecraft, a custom block is a new *block-ID* carrying its own
texture, model, and behavior tables (`falling`, `flowing`, `conductive`,
`explosive`, hardness, fuel). CassiCraft has already collapsed the per-material
behavior table into constant-tuples (`material-regimes.md` §6), so here a custom
material is **the same act as authoring a new regime**: a tuple
`(ξ, ω₀², θ_c, n)` plus a name, with every behavior (fall, flow, burn, explode,
conduct, hardness, fuel, appearance) *derived from the law* rather than written
as code. This is the Powder Toy custom-element editor dream, with one crucial
difference: **not every tuple is realizable**, so authoring is *bounded invention
within the law*.

Companion to:
- [`material-regimes.md`](./material-regimes.md) — THE dependency. A material
  *is* a regime: state `(ρ, q, ε², energy)` + identity `(ξ, ω₀², θ_c, n)`; the
  §6 rule-table collapse; hardness = rung (§4); combustion-vs-explosive as a
  discharge rate (§3/§5). Its §7 open-question 1 (per-material γ/ν/μ) and 3
  (per-cell ω₀²/ξ in the PDE) are the *gates* this document's registry sits
  behind.
- [`volumetric-terrain.md`](./volumetric-terrain.md) — blocks as field
  iso-surfaces; precision tools = rung; the dual world (geometry iso-surfaces +
  coarse 1 m gameplay grid, both projections of one continuum).
- [`energy-harnessing.md`](./energy-harnessing.md) — deep-rung matter = stored
  coherence; the `(1−q)` waste law as the glow of any working field system.
- [`coherence-magic.md`](./coherence-magic.md) — the player as a coherence
  source; channeling = field operations at a chosen rung; overdraw →
  full-cascade discharge; **Q4 is the player-return channel** this system is a
  consumer of.
- [`coherence-technologies.md`](./coherence-technologies.md) — concept 4
  (coherent materials: conductivity = coherence, purity as a crafting axis) and
  concept 5 (cascade staging: the ~10-rung bridge limit).
- [`async-field-domain.md`](./async-field-domain.md) — the seam; Q4 job-dict
  inputs. Blocks re-quantize from the published snapshot.
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — block
  quantization; hysteresis `τ_c`/`τ_c−δ`; the coarse 1 m block as a sub-cell
  *sample* of the field (not a stored block-id with a rules entry).

Every number below is engine-verbatim or taken from the docs above, which are
themselves engine-grounded; anything extended beyond the docs is flagged
**[assumption]**.

---

## 1. The regime registry

The **regime registry** is the data-driven table that replaces the block-id
registry. A block-id entry in vanilla carries shape, texture, and a pointer into
a per-material behavior switch. Here each entry is exactly:

```
Regime {
  name        : string            // "Aurellite", "Glass-sea", "Viol-bark"
  ξ           : float             // chord coupling to gravity,  ξ = φ⁶ ≈ 17.94 engine default
  ω₀²         : float             // resonance,  ω₀² = 20.0 engine default
  θ_c         : float             // condensation threshold,  qi_condensation_threshold = 0.5
  n           : int               // rung depth along the cascade
  // presentation hints (see §4) — NOT behavior, but cached-render suggestions
  palette     : [r,g,b], [r,g,b]  // base hue from n + q, dither hints for roughness
}
```

Every **behavior** a block-id used to hard-code is a *derived column* of these
five numbers under the law — nothing is stored. `material-regimes.md` §6 is the
collapse table this registry formalizes:

| Behavior (derived, not stored) | Formula / source |
|---|---|
| Falling / pile angle | river law `a = −G_N·(π/ρ)·∇(g·Φ)` + RealSim friction μ, q-at-rest (`material-regimes.md` §3) |
| Fluid leveling | low ω₀² + low rest-q, viscosity shear (`§3`) |
| Heat conduction | ω₀² (lock-restoration rate) × ξ (`§3`) |
| Conductivity | ξ × ω₀² (`§3`) |
| Hardness | `n`, the rung (`§4`) |
| Ignition resistance | decoherence-resistance = deeper `n` (`§3`) |
| Combustion vs explosive | **discharge rate**: controlled organization front @ `c_s` vs full-cascade collapse (`§3`, `§5`) |
| Fuel value | `n`, ω₀², ignitability — controlled coherence release (`§5`) |
| Ore precipitation | where local q exceeds `θ_c` by coherence, not ρ (`§3`) |
| Stored energy | deep-rung ordered matter, the `(1−q)`-free battery (`energy-harnessing.md` §3) |

**How the registry is applied to blocks.** The dual-world grid of
`chunk-field-quantization.md` makes a block's *value* a lookup of its sampled
state against constant-tuples, **not** a stored id with a rules entry. A 1 m
Cassi block is a trilinear sample of `(ρ, q, ε²)` integrated over its meter
(`chunk-field-quantization.md` §1.3); its material identity is *which tuple
governs it* at that state. The registry is the table of tuples the sampler can
select from; a block's "id" is just a pointer to a tuple, and a phase change is a
threshold crossing in state within one tuple — never a NEW material
(`material-regimes.md` §1). Re-quantization is the engine already re-sampling;
adding the registry only means the sample selects which tuple governs.

### Worked examples — materials you can only *author*

These are not vanilla analogies — vanilla has no concept of them because vanilla
hard-coded each behavior separately and could not combine the knobs a tuple
opens:

| Regime | ξ | ω₀² | θ_c | n | Emergent signature (derived, no code) |
|---|---|---|---|---|---|
| **Conductor-clay** | high (ξ ≈ φ⁶) | very high | low | deep | Water-like on the *density* axis (low θ_c → it pools and flows) but a high-conductivity, high-ω₀² channel — a *flowing wire*. The same tuple that makes it spread makes it a coherence conduit: it levels like melted metal and routes coherence along the pool. Vanilla cannot have "a liquid that is also a wire." |
| **Slow-burn timber** | mid | low-mid | mid | mid | High-ignitability (shallow n, mid ω₀² feeds a slow front) paired with a *very low ξ* → barely falls, piles shallow. It burns as a slow, controllable fuel front and sheds the `(1−q)` glow at a low rate — a base-heater you can walk on without it being a lava/wood either/or. |
| **Non-Euclidean ore** | mid | mid | high (near 1) | deep | The θ_c is reached *by q* not ρ (per §3 ore rule), so it only precipitates where coherence accumulates very hard and never where you merely pile density. A deep-rung, high-θ_c deposit that exists *only* as an ore — impossible to mine-and-recast because cast matter (dense but decohered) falls short of its q-θ_c; you can only ever *find* it in place. |

These are the payoff of authoring: each is a combination of knobs that vanilla's
per-behavior tables simply could not express, and each emerged from the law with
**zero behavior code**.

---

## 2. The material lab — an in-world authoring surface

The lab is **not an inventory GUI with sliders that spawn a block ID**. It is a
**field operation** — a coherence-magic channeling surface, designed per
`coherence-magic.md`'s Q4 player-return channel. The lab is a *place* you stand
in, and defining a material is a *channeling act*, not a menu edit.

**The lab structure.** A physical, in-world apparatus — a framed region the
player builds (concept 5 of `coherence-technologies.md`: cascade staging; the
~10-rung bridge limit means a lab at one scale cannot reach every rung, so a
deeper-rung lab is a bigger, costlier build). Inside it the player does two
things for each candidate tuple:

1. **Dial the constants.** Four actions that map onto field operations rather
   than sliders:
   - `ξ` — *coupling*: tune the effective gravity chord `g = 1 + (ξ−1)q` by
     shaping the lab's density/mass concentration (borrowing the condenser
     language of `coherence-technologies.md` concept 2). High-ξ = build denser.
   - `ω₀²` — *resonance*: tune the lock-restoration rate by matching your
     channeling rhythm to the local field's `ω₀²` (the resonance efficiency
     rule of `coherence-magic.md` §3.1).
   - `θ_c` — *condensation threshold*: dial how much ρ (or q, §1 ore rule) must
     accumulate before this regime condenses — set by how far below ambient
     coherence you hold the region.
   - `n` — *rung*: which cascade organization scale the precipitation is locked
     to. Per cascade staging, this is the staged depth of the lab.

2. **See the predicted emergent signature.** The lab computes, **from the same
   formulas the world uses** (the registry's derived columns of §1, not a
   side-simulator with separate physics), a preview of both *behavior* and
   *appearance*:
   - Behavior preview: a small live patch of the candidate regime exercised
     inside the frame — the law runs it (small bounded locality, the
     synchronous-touch path of `async-field-domain.md` §4.2 for player-touched
     outcome). You watch the patch fall/flow/burn/conduct *as the world would*.
   - Appearance preview: the §4 render mapping applied to the tuple, shown as a
     swatch/iso-surface sample.

3. **Realize it.** Accepting the tuple issues a **precipitation intent** — a job
   input `{op: "precipitate", tuple, worldPos, rung, magnitude, sustain}`
   pushed through **Q4**, the player-return channel (`coherence-magic.md` §5.1).
   The domain's condensation scanner (the merge lineage, `cassi_condensation`)
   then **precipitates the new material where the local state matches the
   tuple** — i.e. the field itself condenses the new regime out of a region that
   already satisfies its `(ξ, ω₀², θ_c, n)`. The world effect is the sampler
   re-quantizing the published snapshot, exactly as with any channeled op. The
   player is *authoring a boundary condition the law then fulfills*, not
   spawning a block.

**Why it is a channeling surface, not an inventory GUI.** Two coherent-magic
constraints make the lab honest rather than menu-driven:

- **It is bounded by the player's coherence budget `B ∈ [0,1]`** and the ε² vent
  (`coherence-magic.md` §1.2). Dialing is *costly*: each tuple you hold toward
  realization is a sustained channeling act; overdraw tips locally into a
  random-perturbation discharge (the exact overdraw→discharge rule of
  `coherence-magic.md` §4.3). A lab is a place you *work in*, not a UI you open.
- **It is a write into the Q4 dict, never a touch on physics state.** The lab
  never references a field array; it emits job inputs, and the world-writer +
  sampler + domain chain quantizes them back (`coherence-magic.md` §5.1). The
  async seam is preserved *by construction*.

**[assumption]** Realization via "region whose local state matches the tuple" is
an extension of the ore-precipitation mechanism (`material-regimes.md` §3): ore
selects which material precipitates from a q band; the lab *specifies* the tuple
for a chosen region. Both ride the condensation scanner; the *specification input*
is the design's addition, grounded in the existing "coherence accumulates →
finer deposit" claim.

---

## 3. Realizability — which tuples exist (the honest physics)

**Not every `(ξ, ω₀², θ_c, n)` is stable in the law.** The field only precipitates
regimes that are **attractor-consistent within engine-real ranges**, and the lab
must show *stability*, not just behavior. The boundaries:

**Physical ceilings (from the law, not hand-tuned):**
- `q ∈ [0,1]` by construction; the φ-attractor sits near `q ≈ 0.947`
  (`coherence-magic.md` §1). A regime that demands a resting `q` the law cannot
  hold (e.g. a coherent `q → 1` solid whose tuple math wants `ε²` high) is
  unstable: the field relaxes, the regime does not precipitate.
- `π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)`. A tuple that needs a Yang fraction
  above the clamp is *unphysical for the law*; it cannot bind.
- Condensation needs `ρ ≥ θ_c` with the quantizer's hysteresis
  (`chunk-field-quantization.md` §3): `τ_c` to solidify, `τ_c − δ` to dissolve.
  A tuple whose `θ_c` sits *inside the hysteresis band* or above the range the
  engine can sustain jitters — a meta-state between solid and dissolved that
  flickers or never holds.
- The φ-lock: `ε² = (EY − φ·EI)²`. A regime whose constants demand sustained
  decoherence (`ε²` far from 0) at fixed ρ fights the attractor and is
  intrinsically unstable — it can only exist *fed* (a scar, a heated region),
  not as a resting precipitate. This is what separates a *material* (a stable
  position the field returns to) from a *transient* (a fed state such as fire or
  plasma, which `material-regimes.md` §2 already treats outside the material
  table).

**Engine-real ranges (config dials today, gates tomorrow):**
- `ξ = φ⁶ ≈ 17.94` engine default, `ω₀² = 20.0` default. Per-material, these
  require the **per-cell ω₀²/ξ feeding the PDE** — `material-regimes.md` §7 Q3,
  the gated **Phase-1.5** extension. Until then the whole field runs *one* ξ and
  *one* ω₀², so only that one tuple is engine-real; the registry cannot diverge
  before Phase-1.5 lands.
- Per-material dissipation γ/ν/μ is the **second gate** (`material-regimes.md`
  §7 Q1, the load-bearing differentiator): without per-regime γ/ν/μ, sand and
  water reduce to "one law, different thresholds," and the registry's behavioral
  richness is not expressible. The registry's behavioral *columns* thus stay
  dependent on both Phase-1.5 gates, not on the registry itself.

**Hysteresis-stability on the coarse 1 m grid.** A coarse block is a sub-cell
trilinear sample (`chunk-field-quantization.md` §1.3); a regime must precipitate
consistently when that sample re-quantizes over ticks. A tuple whose
precipitation depends on sub-cell detail the 1 m sample averages away, or whose
`θ_c` boundary sits close to the ambient field's jitter, fails hysteresis-stability.

### Boundary semantics — what "unrealizable" looks like

The lab shows **stability**, not just a behavior preview, and it denies
creativity the moment it crosses a real boundary. Two honest failure modes,
both *field refusals* (the law refuses; there is no error dialog):

- **No precipitation.** The event `{op: "precipitate", tuple, …}` is submitted,
  the condensation scanner evaluates the local state, and the region does **not**
  cross the tuple's `θ_c` at the requested rung → nothing condenses. The world
  effect is "the field doesn't make this here," which is *correct* — the lab can
  be tuned so the state does match, or the tuple simply is not realizable in
  that location. This teaches the localization of realizability: a tuple
  realizable in a deep coherent region may be unrealizable in airy rubble.
- **Immediate meta-decay.** If a realization is attempted that *is* inside the
  physical ceilings but not attractor-stable (e.g. a high-`q`‑at-high-`ε²`
  contradiction, or a `θ_c` in the hysteresis band), the field precipitates and
  **immediately re-dissolves** / corrupts toward the attractor — a meta-material
  that cannot hold. The player sees it condense, then shed `ε²` and return to a
  stable neighbor regime. This is the visible "invalid" path: not a rejection
  message but a *physics verdict* the field renders.

**[assumption]** The "stability" classification (which tuples the law precipitates
vs decays) is not fully known analytically today — it is a *measured* property
of the engine's PDE at each candidate tuple. The lab therefore runs the law, not
a rule table, to classify: realizability is *determined by the physics at
authoring time* and cached, not hard-coded. Where the boundary sits *numerically*
is an honest open question (§7).

---

## 4. Emergent visuals — appearance derived from the regime

Since blocks are **iso-surfaces of the field** (`volumetric-terrain.md`), a
material's visual identity *derives from its regime* — no authored texture is
needed. The render layer of volumetric-terrain applied per-regime gives custom
blocks their look for free from their constants. The mapping rules:

| Regime axis | Visual consequence | Grounding |
|---|---|---|
| **Deeper `n`** | **crystalline / ordered**: sharp, faceted iso-surfaces, higher specular/regularity — deeper rung = more ordered matter (`material-regimes.md` §4). | deeper rung = lower ε² = the iso-surface is clean, facets read as sub-block rung refinement (`volumetric-terrain.md`). |
| **Higher `ε²` handling / low `q`** | **chaotic / rough**: noisy, pitted iso-surfaces, blurry edges — decoherence scar material that reads as disorder. | ε² = decoherence channel; high-ε² regions are how carved/scarred terrain looks (`chunk-field-quantization.md` §2.2). |
| **Higher `q`** | **bright / coherent**: luminous, saturated hue from the q-band (mirroring ore's "finer/richer as q rises"), a clean gradient sheen. | q = coherence; ore precipitates where q accumulates and is finer/richer with q (`material-regimes.md` §3; `chunk-field-quantization.md` §2.2). |
| **High `(1−q)` while active** | **live glow**: the energy-harnessing `(1−q)` waste law rendered as a visible glow when the material is *working* (feeding a machine, holding a conduit line, mid-conversion). | the `(1−q)` glow is the always-on energy diagnostic (`coherence-technologies.md` concept 4; `energy-harnessing.md` §1.3/§6 "the glow"). A *bright machine is a wasteful one* (`coherence-technologies.md` §4c). |

So the **base palette** is a function of `(n, q, ε²)`: hue/order from `n`,
saturation from `q`, roughness/dither from `ε²`/decoherence; the **glow is a
live state**, not a static texture — a custom conductor *glows brighter* the
more loss it is bleeding, giving the `(1−q)` law a first-person visual. This is
the render layer of volumetric-terrain applied per-regime: the iso-surface
already carries the field; the material merely *colors and textures it* according
to the same numbers that give it behavior. Two custom materials with the same
tuple look identical by construction (visual identity is one-to-one with the
regime); a phase-changed block (state moved within one tuple) keeps its color but
changes its roughness/glow — a hot block of the same material is visibly the same
*hue* at a different disorder (`material-regimes.md` §1).

**[assumption]** The *exact* color/roughness mapping (which `n` → which facet
density, which `ε²` → which dither) is a presentation-hint layer over the field
iso-surface, not new physics. It is cached in the registry's `palette` hints so
the world does not re-derive appearance every render, but the *semantics* (order↔n,
bright↔q, rough↔ε², glow↔(1−q)) are fixed by the law.

---

## 5. The modding surface

**How the community adds materials: a data file of tuples, no behavior code.** A
mod contributes a registry file:

```json
{
  "name": "conductor-clay",
  "regime": { "ξ": 17.9, "ω₀²": 42.0, "θ_c": 0.3, "n": 6 },
  "palette": { "base": [80, 200, 255], "glow_tint": [120, 255, 255] }
}
```

The mod runtime **registers the tuple into the living regime registry**; the
sampler's block-quantization then selects it wherever the field's sampled state
matches its tuple. There is **no behavior code to write** — the mod author tunes
four numbers and hints, and the law supplies fall/flow/burn/explode/conduct/hard/
fuel/appearance. Contrast with vanilla block JSONs:

| | Vanilla block JSON | CassiCraft regime entry |
|---|---|---|
| Identity | block-ID (+ registered name) | tuple `(ξ, ω₀², θ_c, n)` + name |
| Shape | explicit model / geometry | iso-surface of the field — none authored |
| Texture | authored image file | derived from `(n, q, ε²)` (render layer, §4) |
| Behavior | model JSON + `onPlace`/`onTick` Java hooks, per-material flags | derived columns of the law (§1) — **no hooks** |
| Novelty | new block with hand-authored rules | new *point in the regime space* |

**Persistence and sharing — a "found" material becomes an ingredient, not a
recipe.** Player-authored materials persist in a **world-level registry** (the
world's own regime table, layered over the base/mod tables — the player's
inventions are facts of *that world's* field, saved with the world, not global
constants). Because deep-rung matter is **stored coherence**
(`material-regimes.md` §5; `energy-harnessing.md` §1.5), an invented material is
an *ordered substance*, and ordering it is the fuel/energy economy's substance:
a material a player realized in their world is a **hand-off of rung access**, not
a blueprint. Sharing/trading an invented material is therefore not exchanging a
recipe (a written tuple anyone could read) but **exchanging a sample of the
ordered matter** — an ingredient with environmental provenance: the deeper-rung
or more coherent a traded material, the more stored coherence it carries, and the
more it is worth *as energy/fuel* (`energy-harnessing.md` §3). A mod publishing a
tuples-file and a player shipping a *sample* ride the same registry; the sample is
just the tuple realized in matter a consumer can re-condense rather than re-dial.

---

## 6. The invention economy — discovery vs. authoring

**The tension: are materials *found* (the field has precipitated them; the lab
documents them) or *invented* (the player dials novel tuples)?** Recommend a
**hybrid**:

- **The lab reveals the realizable space.** Running the law at candidate tuples
  (and the world's own spontaneous precipitation elsewhere) *maps* which tuples
  are attractor-stable (§3). A "found" material is one the field already
  precipitates and the lab has *documented* — the registry fills in from what
  the world does on its own, and the lab reads it out. Finding is free knowledge:
  it tells you a region of regime space exists.
- **The player invents within it.** Because not every stable tuple has happened
  to precipitate in a given world, and because novel combinations (§1's worked
  examples) do *new* things, the player can dial tuples the field has not — this
  is *invention*, and it persists into the world registry (§5).
- **Invented materials become "found" for others.** Once realized and registered,
  a novel material is part of that world's field; any other player (or a mod's
  data pipeline) can *encounter* it in place rather than dial it. `(1−q)` while
  active marks it for the senses; precipitation in a region that satisfies it
  makes it discoverable.

**Why invent when you can find?** Finding is cheaper (read-only: the lab
documents, no channeling cost, no vent risk) but is *restricted to what the
field has happened to precipitate in that world*. Invention costs channeling
budget and carries the vent/overdraw and realizability risk (§2, §3), but it is
the *only* path to materials the local field has not produced — and those are
precisely the materials that do novel things (a flowing wire, a q-only-ore,
§1). The economy's cost is thus the coherence-budget asymmetry of
`energy-harnessing.md` §3: **finding is cheap but bounded by what the field has
made; inventing is expensive (stored coherence spent) but unbounded within the
realizable space.** A deep-rung or high-`q` invention is worth more than a found
equivalent precisely because its ordering is *novel* — coherence assembled by a
player rather than incidental — which is the `(1−q)`-waste fuel economy's source
of scarcity.

---

## 7. Honest open questions & feasibility verdict

### Open questions

1. **Lab-preview vs. async-domain consistency.** The lab preview runs the law in
   a small bounded locality (the §2 sync-touch path), but *real* precipitation
   happens in the async domain at its own cadence and from the surrounding field
   it is embedded in. Will a tuple that previews stable in the isolated lab frame
   necessarily precipitate identically in the live, continuously-evolving domain
   (neighboring coherence, ongoing heal/perturbation)? The isolated frame
   removes coupling the real world has. Needs a Phase-1.5 probe comparing
   lab-preview stability to live precipitation for the same tuples.
2. **Determinism of "same tuple → same material" across worlds.** The registry
   is deterministic *within* a world (same tuple → same derived behaviors and
   appearance). But realizability (§3) is a *property of the local field state*:
   a tuple realizable in a deep coherent region may be unrealizable in rubble, and
   two worlds with different field histories will precipitate different stable
   sets. Is "Aurellite" a *material* with a fixed identity everywhere it manages
   to precipitate, or a *description* that yields whatever the local field
   condenses? Preferred stance **[assumption]**: identity is the tuple (fixed);
   realizability is contextual (world- and region-dependent). Confirm the
   registry keeps identity and realizability as separate axes.
3. **Where does the realizable-space boundary live *numerically*?** Which
   `(ξ, ω₀², θ_c, n)` tuples the law precipitates vs decays (§3) is not yet a
   closed form — it is a *measured* property of the PDE. Until Phase-1.5 gates
   (per-cell constants) land and a scan populates the stability map, the lab's
   "unrealizable" classification is empirical, not derived. Is a partial
   analytic bound derivable from the attractor/q-clamp before the gates, or does
   the boundary only exist conditional on them?
4. **The two gates.** Everything behavioral in §1 is downstream of
   `material-regimes.md`'s Phase-1.5 per-material-constants engine work (per-cell
   ω₀²/ξ feeding the PDE, §7 Q3) and per-material dissipation γ/ν/μ (§7 Q1). The
   registry is **not** buildable before both land — until then the field runs one
   ξ/ω₀² and one dissipation, so a multi-tuple registry has nothing to select
   between.
5. **Realization coupling to the merge lineage.** Does "precipitate this tuple
   here" read as a new *condensed body/object* (join the merge lineage, becoming
   a capacitor at its rung) or a *terrain block-state* (a quantized coarse cell)?
   The two are the same continuum (ordering matter is storage whether it is a
   block or a body, `energy-harnessing.md` §3), but the *sampler path* differs.
   The lab's realization intent must pick one for handling.
6. **Mod-registered tuples vs. world-registered player inventions.** A mod's
   tuples live in the global/world data pipeline; a player's inventions persist
   in the world-level registry (§5). Collision rules, precedence, namespace
   hygiene, and how a mod can *adopt* a player-discovered material as a modded
   entry are unspecified. Needs the modding-surface contract before the community
   layer is real.

### Feasibility verdict

**The architecture is sound and the collapse is real.** Authoring a custom
block = authoring a tuple `(ξ, ω₀², θ_c, n)` is exactly the regime collapse
`material-regimes.md` §6 already establishes — every behavior column derived from
the law, no per-material code, appearance derived from the same constants. The
lab as a Q4 field operation preserves the async seam by construction
(`coherence-magic.md` §5.1): it emits job-dict inputs, never touches physics
state. The `(1−q)`-derived visuals and the found/invented economy reuse the
energy system's stored-coherence substance and its charge/scar asymmetry — no new
economy invented.

**The registry is downstream of material-regimes' gated per-material constants
engine work (Phase-1.5), not a Phase-1 build.** As material-regimes itself
concludes, distinct materials behaving differently need the per-cell ω₀²/ξ PDE
extension and per-material dissipation — both structural engine additions that
are the Phase-1.5 gate. **The Phase-1 slice is a read-only lab** that documents
the engine-real regimes (the single ξ/ω₀² tuple the Phase-1 field runs) and
previews them — i.e. a *documentation + preview* surface over the one regime the
law currently realizes, with the lab's dials shown-but-locked until Phase-1.5
unlocks per-material constants. That slice needs no new physics (preview runs the
same law) and no new engine code beyond the player-return/condensation inputs the
lab shares with every channeled op.

**Binding risks, in order:** per-cell ω₀²/ξ + per-material dissipation (the two
Phase-1.5 gates — without them the registry has nothing to select between),
then the lab-preview/async consistency probe (Q1), then the numeric
realizable-boundary measurement (Q3). None is an architectural contradiction of
the async model or the regime collapse; each is honest sequential work downstream
of the gates. Verdict: **the regime registry is the right end-state; Phase-1
delivers a read-only lab that documents and previews the engine-real regimes, and
authoring (realization, multi-tuple selection) lands with the Phase-1.5
per-material-constants engine work it depends on.**
