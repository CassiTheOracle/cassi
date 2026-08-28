# Field Hazards: The Danger Layer of a Living World

**Question under design:** how a living field world has *stakes*. The corpus has
invoked "scars," "ε² wells," "corruption" as dangers across fourteen documents
without ever designing the danger itself. This document is that design: a world
that can genuinely be **wounded** (decoherence storms), **starve** (the desert —
a coherence drought), and **end** (BH accretion — the end of the cascade). All
three are the field's own behavior at its extremes, not spawned enemies.

This is a *danger layer*: it sits on top of the material/energy/ecology/archaeology
systems and reuses only what they already publish, so every hazard is a
**presented reading** of field channels the engine already computes. It is the
threat-side companion to [`energy-harnessing.md`](./energy-harnessing.md)'s
reservoir-side "field operations" stance — where that doc asks *what the field
gives*, this doc asks *what the field takes back.*

Companion to [`material-regimes.md`](./material-regimes.md) (dissolution — ε²
dominates → matter un-condenses; the fire-vs-explosive discharge rate; the
`(1−q)` waste law; the gas regime), [`energy-harnessing.md`](./energy-harnessing.md)
(anti-corruption §5.4 — invest coherence to hold ground against decay; the Qi
bath §4.4; the no-free-energy cap §6), [`field-emergent-ecology.md`](./field-emergent-ecology.md)
(organisms need the q coherent band at low ε²; the biosphere drifts with the
field), [`coherence-magic.md`](./coherence-magic.md) (the ε² vent; overdraw →
full-cascade discharge; the reader — hazards should be *readable* before they
arrive), [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
(auroras as field diagnostics — the sky reads the storm first; the `(1−q)` glow),
[`field-archaeology.md`](./field-archaeology.md) (the dig perturbs the field; deep
excavation lowers regional q — archaeology can **cause** hazards),
[`world-seams.md`](./world-seams.md) + [`ksp-kernel.md`](./ksp-kernel.md) (the
ultimate response to a world-ending hazard: leave the window — evacuation by
ship), and [`volumetric-terrain.md`](./volumetric-terrain.md) (terrain heals —
hazards fight the heal).

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived), quoted verbatim from the engine
shaders (`CassiCosmos/compute/*.glsl`), or flagged **[design]** / **[assumption]**
where it extends engine terms to a *presented* hazard the engine does not (yet)
drive. The line between engine-real and designed is drawn in §6 and never blurred.

---

## Summary table

| Hazard | Field channel it is | Pace | Readable before it arrives | Response (coherence, not HP) |
|---|---|---|---|---|
| **Decoherence storm** | a moving `ε²` front | fast (waves at `c_s`) | auroras flicker / reader ε² noise rises / `(1−q)` glow shifts | shelter in a high-`q` refuge, vent discipline, anti-corruption holds; it passes, scars remain |
| **The desert** | a regional `q` collapse | slow (creeps) | the reader darkens, glow fades, life thins | **prevent** — anti-corruption investment, Qi-bath husbandry |
| **BH accretion** | a `∇(g·Φ)` sink eating `q·cell_vol` | slow→terminal | the sky falls over time, accretion front approaches | feed it (choice), starve it, or **evacuate the window** |

The through-line: **no monster table, no spawned enemy.** Every hazard is already
expressible in the published channels `ρ`, `q`, `ε²`, `∇(g·Φ)` — the same four the
sampler reads every tick. The design work is not a new system; it is the
*presentation* (and the pacing, §5) that turns "the field is doing something" into
a hazard a player understands and can answer.

---

## 1. The principle: the threat is the field's own extremes

CassiCraft's danger is not a hostile AI, a mob they can kill, or a damage number.
It is the field itself doing what the field does at its **extremes**. The spine,
stated once:

> **No monster table. No spawned enemies. Every hazard is the field's behavior at
> an extreme — a region of `(ρ, q, ε², ∇(g·Φ))` that has run away from the
> φ-attractor and is reasserting the law's logic against the player's work.**

The three named hazards are not three systems; they are three *orders of
extremity* of the same two-fluid field:

| Hazard | The extreme | The field's own dynamics at that extreme |
|---|---|---|
| **Decoherence storm** | `ε² = (EY − φ·EI)²` spikes and **travels** | a wave front of disorder propagating at the coherence sound speed `c_s = h₀/dt` (engine merge-shader definition) — the same organized-perturbation-front mechanics as combustion ([`material-regimes.md`](./material-regimes.md) §3), but the *disordering* one |
| **The desert** | `q` collapses **region-wide** | the φ-attractor's tendency to organize is locally defeated: the drain outruns every maintainer, the field-poor interstitial (`world-seams.md` §2.1) creeps into a window |
| **BH accretion** | a `∇(g·Φ)` sink that **never stops** | the merge lineage's deep end: `mass += acc_rate · qi_local · cell_vol` (`cassi_bh_integrate.glsl`) — a body that virial-stopped too late keeps eating matter along the gradient, the end of the cascade |

The design consequence is that **hazards are honest**: they are not authored to
attack the player; they are the field's real channels read with *intent*. A storm
is the PDE's wave operator runaway; a desert is a window's field drifting to a
field-poor state; a BH is the merge lineage's terminal branch. Because they are
the field's own behavior, they cannot be "deleted" — only answered with the
field's own tools (coherence, vent discipline, anti-corruption, evacuation), never
with a damage stat.

This mirrors the ecology's rejection of the mob table
([`field-emergent-ecology.md`](./field-emergent-ecology.md) §2.1): creatures are
field precipitates, not spawn-table entries; **hazards are the same — field
events, not spawn-table threats.** Life and danger are two faces of "the field
organizes where it can"; hazards are where the field *dis*organizes, or organizes
into a sink.

---

## 2. Decoherence storms — the wound that travels

### 2.1 What it is, in the field's terms

A **decoherence storm** is a region where random perturbation dominates — a
localized, sustained injection of `ε² = (EY − φ·EI)²` that **travels** as a steep
`∇ε²` front through the field at the coherence sound speed `c_s = h₀/dt`. It is the
field's own wave dynamics, not a spawned effect:

- The PDE's source terms are exactly what such an injection looks like —
  `source_ey(i,j,k) = s·exp(−4r²) + ρ·0.001` ([`cassi_two_fluid.glsl`](../../CassiCosmos/compute/cassi_two_fluid.glsl)) —
  a Gaussian organized-perturbation seed. **A storm is a *dis*organized seed** — a
  random-perturbation injection that raises `EY − φ·EI` out of lock without a
  coherent structure to organize it. The engine-real waveform is the same
  `∂²EY/∂t² = c²∇²EY − ω₀²(EY − φ·EI)`; [`material-regimes.md`](./material-regimes.md) §3 already
  shows a *coherence* front (combustion) travels at `c_s`; a *decoherence* front is
  the mirror — the same wave operator carrying disorder outward.
- Because `ε² = (EY − φ·EI)²` is a *derived* channel written into `vel[].w` each
  step (`cassi_two_fluid.glsl` pass B), and because the material regime's **solid**
  phase requires `ρ ≥ θ_c` *and* `ε²` below a solid floor ([`material-regimes.md`](./material-regimes.md)
  §2), a front that raises local `ε²` above that floor **dissolves shallow matter
  in real time** — blocks un-condense, the land un-heals visibly as the storm
  passes. The storm is a moving dissolution boundary.
- **[design] The "storm front" as a presented event.** The engine's real waves
  propagate and dissolve; *which* random-perturbation source ignites one, its
  size and cadence, and its visible "rolling wave" presentation are the design's
  contribution (§6). The physics beneath — a `c_s`-traveling decoherence front
  that crosses the material dissolution floor — is the PDE's own dynamics.

### 2.2 The hazard's honest shape, grounded

| Storm property | Field mechanism | Grounding |
|---|---|---|
| Travels `∇ε²` at `c_s` | the wave operator spreads the injected disorder at the coherence sound speed | `c_s = h₀/dt` (merge-shader def.); [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) §1.3 (two-fluid waves ARE weather); [`material-regimes.md`](./material-regimes.md) §3 (front speeds ≈ `c_s`) |
| Shallow matter dissolves | raising `ε²` above the solid floor drives `ρ` below `θ_c` (hysteresis `τ_c/τ_c−δ`) | [`material-regimes.md`](./material-regimes.md) §2; [`chunk-field-quantization.md`](./chunk-field-quantization.md) §3 |
| Stops / passes | the `−ω₀²(EY − φ·EI)` term re-locks the φ-attractor once the injection ceases; the field heals toward the attractor | [`volumetric-terrain.md`](./volumetric-terrain.md) (terrain heals); [`energy-harnessing.md`](./energy-harnessing.md) §5.3 (healing is the default, feeding accelerates it) |
| Leaves scars | the deep-rung fraction resists the perturbation and persists as **residue** | [`field-archaeology.md`](./field-archaeology.md) §2.1 (scars heal, leave residue; deep-rung matter survives) — the archaeology of the storm |

### 2.3 Reading it first — the sky and the reader warn before the wall arrives

The corpus's cardinal rule for hazards is **readable before they arrive**
([`coherence-magic.md`](./coherence-magic.md): "hazards should be *readable* before
they arrive"). A storm obeys it on two channels:

| Pre-warning | Channel | Source |
|---|---|---|
| **Auroras flicker / become restless** | a storm's incoming `ε²` events create transient drains the coupling field pours coherence into; the `(1−q)` glow over those drains *dances* before the front arrives | [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) §3.2/§3.3 (a discharge over a drain; a *wounded* body shows restless bright discharges) |
| **The reader's `ε²` noise rises** | the storm's leading edge shows as rising `ε²` before the dissolution front | [`coherence-magic.md`](./coherence-magic.md) §2 (Sense renders the published `ε²`); [`field-emergent-ecology.md`](./field-emergent-ecology.md) §5.1 (reader = the q-colored sim) |
| **The `(1−q)` glow of everything dims or brightens wrongly** | a working structure at the storm's fringe sheds `(1−q)` waste abnormally — a bright wasteful region is *wrongly* bright | [`energy-harnessing.md`](./energy-harnessing.md) §2 (the `(1−q)` glow is the field's economic signature); [`coherence-technologies.md`](./coherence-technologies.md) §4 (a bright machine is a wasteful one) |

The sky reads the storm first (§3.3 of the atmosphere doc: the sky is the reader's
atmospheric form), then the hand-held reader confirms it, then the land dissolves.
**The pacer is the presentation (§5):** the storm never arrives un-announced; the
pre-warnings are what give the player the *window* to respond.

### 2.4 Player response — coherence, not HP

There is no health bar to survive a storm; there are field choices:

- **Shelter in a high-`q` refuge.** The `(1−q)` waste law ([`energy-harnessing.md`](./energy-harnessing.md)
  §2) makes a Qi bath / coherence-barrier regime ([`energy-harnessing.md`](./energy-harnessing.md)
  §4.4; [`coherence-technologies.md`](./coherence-technologies.md) §4) a *refuge*: inside it, the
  local `q` stays high against the incoming `ε²`, so structures resist the
  dissolution floor while the storm passes. A barrier regime ([`custom-blocks.md`](./custom-blocks.md)
  §1) is a depth `n` against decoherence-resistance — the same physics that makes
  deep-rung matter fire-resistant ([`material-regimes.md`](./material-regimes.md) §3) makes it
  storm-resistant.
- **Vent discipline.** A storm is incoming `ε²`; channeling a vent into it
  ([`coherence-magic.md`](./coherence-magic.md) §1) *adds* to the local disorder. The discipline
  is to *not* channel against the storm's grain where the field can't re-lock, and
  to match resonance [`coherence-magic.md`](./coherence-magic.md) §3.1 — pushing with the field's
  natural re-lock rather than against it.
- **Anti-corruption holds.** [`energy-harnessing.md`](./energy-harnessing.md) §5.4 — spend fed
  coherence to suppress `ε²` below the dissolution floor and hold ground *while*
  the storm is overhead. Costed, continuous, net-negative — never free.

The storm *passes* (the field re-locks, heals), and the residue it leaves — the
deep-rung cores that survived, the `q`-locked pockets where shallow matter was
ahead of them — becomes **[`field-archaeology.md`](./field-archaeology.md)** : a storm scar is a
findable residue, the sky still reads it as an aurora over healed ground (§3.3 of
the archaeology doc). The storm is a wound the world heals around.

---

## 3. The desert — a coherence drought

### 3.1 What it is: `q` collapses region-wide

The **desert** is not a biome; it is a region where the field's operating coherence
`q` has **collapsed region-wide** — a window (or a large patch of one) where the
φ-lock cannot hold against a sustained, distributed `ε²` drain. It is the **slow**
hazard, and its tell is what *stops happening*:

| The desert kills | Why | Source |
|---|---|---|
| **The biosphere starves** | organisms precipitate only where `q` is in a coherent band and `ε²` low; a desert has no such band, and organisms that drift in shed coherence and dissolve | [`field-emergent-ecology.md`](./field-emergent-ecology.md) §2.2/§4.2 (the spawn rule; a low-`q` regime is ecological failure); §5.3 (conservation = anti-corruption) |
| **Terrain stops healing** | mining raises `ε²`, and the field heals toward its attractor only where the attractor can hold; a desert's low `q` means `ε²` scars do not close | [`volumetric-terrain.md`](./volumetric-terrain.md); [`chunk-field-quantization.md`](./chunk-field-quantization.md) §3 |
| **Ore stops precipitating** | precipitation is where `q` accumulates above a band; a desert has no accumulating `q` | [`material-regimes.md`](./material-regimes.md) §3 (ore by `q` accumulation); [`chunk-field-quantization.md`](./chunk-field-quantization.md) §2.2 |
| **The Qi bath dies** | a bath is a maintained high-`q` core; a desert's core has nothing to hold `q` up with — the bath's standing cost outruns its coherence | [`energy-harnessing.md`](./energy-harnessing.md) §4.4 ("a bath is a draw … brittle if it goes down") |

### 3.2 Causes — the desert is *made*, not spawned

The desert's causes are all **field interactions that already exist in the corpus**;
the desert is what they look like taken to region scale. This is the load-bearing
point: **a desert is not a creature to fight; it is a consequence to prevent.**

| Cause | Mechanism | It is macro-scale of… | Source |
|---|---|---|---|
| **Over-reaping** | withdrawing deep-rung matter de-orders the locality (`raise ε²`, `lower q`); done across a region, the regional `q` falls below what the field can hold | [`field-archaeology.md`](./field-archaeology.md) §5.1/§5.2 — *deep excavation lowers regional q*; the dig perturbation made macro | [`energy-harnessing.md`](./energy-harnessing.md) §2.5 (the deep-rung reaper's by-product is a wound) |
| **BH draw** | an accreting sink continuously eats `qi_local·cell_vol` at its position, dragging the surrounding `q` down | the energy doc's BH reservoir — but over-provisioned it *starves* the field it sits in | [`energy-harnessing.md`](./energy-harnessing.md) §1.6; this doc §4 |
| **Sustained player overdraw** | channeling past the vent capacity sheds `ε²` the field cannot re-lock — accumulated, regional | [`coherence-magic.md`](./coherence-magic.md) §1.2/§2 — overdraw inverts operations and tips toward random perturbation | [`coherence-magic.md`](./coherence-magic.md) §4.3 (overdraw → discharge) |
| **The field's own drift** | a window can drift into a field-poor state — the local-field mixture, and the desert is its *low* tail | the desert **is** the field-poor interstitial of [`world-seams.md`](./world-seams.md) §2.1 creeping *into* a window | the local-field-mixture treatment ([`world-seams.md`](./world-seams.md) §1.2) |

### 3.3 It creeps, it's caused, it can be *prevented* — not fought

The desert's design stance is the opposite of the storm's. A storm is ridden out;
**a desert is husbanded away**:

- **The desert creeps.** Because `q` falls bit by bit (`q ≈ 1e-3…1e-1` at noise up
  to the attractor ≈ 0.947; [`energy-harnessing.md`](./energy-harnessing.md) §7 Q1's scale) and
  terrain heals only where a drain is not, a desert visibly *spreads* from its
  cause — the reader darkens, the glow fades, life thins, then dies. There is a
  window to catch it before regional `q` crosses its own dissolution floor.
- **It is caused, so it is preventable.** The four causes of §3.2 all map to a
  *choice* the player made (reap too deep, over-provisioned a BH, over-channeled,
  let the window drift). The response is the same law in reverse:
  - **Anti-corruption investment** ([`energy-harnessing.md`](./energy-harnessing.md) §5.4) — spend fed
    coherence to suppress the `ε²` that's chasing `q` down; this is what keeps the
    desert from taking hold.
  - **Qi-bath husbandry** ([`energy-harnessing.md`](./energy-harnessing.md) §4.4) — a maintained
    high-`q` core is the desert's natural counter: it raises the regional operating
    `q`, cutting `(1−q)` waste everywhere inside and holding the dissolution floor
    at bay. A desert is, in the energy doc's own words, "a dead bath" — the design
    completes the sentence: *a living bath is the desert's answer.*
  - **Conservation** ([`field-emergent-ecology.md`](./field-emergent-ecology.md) §5.3) — the
    biosphere's anti-corruption invest is the same act as the desert's prevention.
- **It is never fought.** There is no "kill the drought." A desert that has fully
  taken a region has no `q` left to *spend* on its own correction — you cannot
  anti-corrupt a region that is already coherent-empty. The honest endgame of a
  failed prevention is a **dead window** (see §4's evacuation), or waiting for the
  `ω₀²` attractor to slowly re-bind the field over game-time.

The desert is the design's **pressure against carelessness**: the player's normal
economy (reap, channel, provision) is also the thing that, done thoughtlessly,
kills the field. Every other design doc's cost is this doc's threat at scale.

---

## 4. BH accretion — the end of the cascade

### 4.1 What it is, engine-real

The BH sector is the **deep end of the merge lineage** ([`cassi_particle_merge.glsl`](../../CassiCosmos/compute/cassi_particle_merge.glsl)
`dust → object → BH`). Its accretion is engine-verbatim
([`cassi_bh_integrate.glsl`](../../CassiCosmos/compute/cassi_bh_integrate.glsl)):

```
mass += acc_rate · qi_local · cell_vol      // Qi drawn from the surrounding field
a     += G_N · mass · Δ/(|Δ|² + ε²)^1.5      // softened point sink along ∇(g·Φ), from the BH term
```

A **BH that virial-stopped too late** is the hazard: it was supposed to stop
accepting infall (the merge lineage's virial stopping scale —
[`ksp-kernel.md`](./ksp-kernel.md) §1.1) but it keeps accreting Qi, so it is a
**coherence sink** that pulls matter in along `∇(g·Φ)` indefinitely. Fields docs
across the corpus name this honestly:

- [`energy-harnessing.md`](./energy-harnessing.md) §1.6 — "a `∇(g·Φ)` well that is *still accreting*
  is the deepest, highest-yield gradient … dangerously coupled … the river
  acceleration is unbounded in steepness."
- [`energy-harnessing.md`](./energy-harnessing.md) §3 — the merge lineage is the growing energy store;
  a BH is its terminal, non-stopping form.

### 4.2 The growing hazard: the accretion front is a moving dissolution boundary

Because a BH eats local Qi (`qi_local`) to grow its `mass`, and its pull grows with
`mass` (the softened sink term), BH accretion is **self-reinforcing and
never-ending**:

| Effect | Field mechanism | Result over time |
|---|---|---|
| **A coherence sink** | it withdraws `qi_local` continuously, lowering `q` in the shell around it | every accreting BH makes a *local desert* (§3) that widens as `mass` grows |
| **Matter pulled in along `∇(g·Φ)`** | the river law `a = −G_N·(π/ρ)·∇(g·Φ)` steepens toward the growing sink | objects, entities, and terrain condense-then-infall; the sky falls over time |
| **The accretion front is a moving dissolution boundary** | matter near the sink is shredded before it condenses — the real `∇ε²`/`∇(g·Φ)` shear dissolves what crosses the threshold | a visible frontier of dissolution creeping outward as `mass` grows |

**Engine-real:** the `acc_rate · qi_local · cell_vol` growth, the softened
sink force, the de-coherence (lowered `q`) of local field, and the
gradient-steepening toward mass
are all the BH sector's real dynamics. **[design]** The *gameplay framing* — "this
is a hazard you must answer" vs. "a reservoir to tap" — and the presented
dissolution-boundary front are this doc's addition (§6). **The BH is both hazard
and opportunity**, and the design keeps the two honest: the energy doc already
treats a BH skimmer as high-capitalization, high-risk ([`energy-harnessing.md`](./energy-harnessing.md)
§2.6); this doc is the threat side of the same object.

### 4.3 Player responses, in escalating order

| Response | What it is | Mechanism | Cost / risk |
|---|---|---|---|
| **Feed it deliberately** | treat the BH as a *controlled* reservoir — a place to dump excess coherence/matter the player chooses to route in | the energy doc's BH reservoir as a *choice*: the field's deepest store, harvested only at extreme risk ([`energy-harnessing.md`](./energy-harnessing.md) §1.6/§2.6) | controlled accretion is power; uncontrolled accretion is the hazard this doc names |
| **Starve it** | anti-corruption at scale — invest fed coherence to hold the surrounding `q` up so the BH has less `qi_local` to eat, and/or isolate it from matter inflow | the §3.2 BH-draw cause, answered by its §3.3 prevention (anti-corruption in the whole shell) | high sustained cost; a BH too massive may out-eat any hold |
| **Evacuate the window** | **the ultimate stakes**: a world can end, and the response to a dying world is **leaving it** | compose `world-seams.md` — build the ship ([`ksp-kernel.md`](./ksp-kernel.md) §2), stock the coherence, re-home via **anchor-to-window** to a distant window (or found one) | the voyage's coherence budget is the honest limiter ([`world-seams.md`](./world-seams.md) §2.3) — evacuation is a *costed*, real decision, not a respawn |

The escalation is the design's core claim for the BH: **the game's terminal hazard
has a real out** — not an invulnerability, but *a ship*. The shallow end of the
hazard (feed/starve) is Phase-1/2 mechanics; the evacuation that ends a world is
the composition of the KSP kernel + world-seams (Phase 2+).

### 4.4 BH as archaeology — what it ate

A BH's mass/position is a **persistent, sampled record** — the deep end of the
merge lineage, "the keeper of the deepest matter" ([`field-archaeology.md`](./field-archaeology.md)
§1.1, which names the BH records as engine-real). The hazard therefore carries the
world's memory into its endgame:

> A BH that has consumed a region holds the region's deepest matter as a single
> dense record. To "read" what it ate — the archaeology surface it accreted — is
> to interrogate the very sink that took it. The deepest fossil archive of a dead
> window is the BH that ended it.

This makes the BH not only the terminal hazard but the **terminal archive**: the
archaeology of what the cascade ended with is the cascade's most coherent—
and most expensive—residue ([`field-archaeology.md`](./field-archaeology.md) §4.1's deep-rung
stored-coherence frame). [design] Grounded in the engine-real BH record; the
"readable archive of what it ate" is the archaeology lens applied to the sink.

---

## 5. Stakes and pacing — difficulty as a design stance

### 5.1 Hazards are *respondable*, not unavoidable

Difficulty in CassiCraft is a **design stance, not a spawning budget**. Every hazard
above is, by construction:

1. **Readable before it arrives.** The storm has the sky + reader (§2.3); the
   desert's *creep* is itself its warning (the reader darkens, life thins);
   the BH is a persistent, sampled record that grows monotonically. **The sky
   reads first, then the hand-held reader** — the atmosphere doc's "the sky is the
   reader's atmospheric form" (§3.3) is exactly the pre-warning architecture.
2. **Costed in coherence, not HP.** Every response (§2.4, §3.3, §4.3) spends
   coherence — shelter's `(1−q)`-advantaged refuge holds by *being* coherent;
   anti-corruption is a fed drain; evacuation's reach is its coherence budget.
3. **Fails open, not closed.** If a player does nothing, the world does not
   instantly die — the storm passes and leaves scars (archaeology), the desert
   creeps (a long preventable window), the BH grows slowly (the evacuation path
   stays open until it is physically unreachable). The design *never* sneaks a
   spawn-kill at the player.

### 5.2 Pacing — the three hazards occupy three time-scales

| Hazard | Pace | Presented as | The tension it targets |
|---|---|---|---|
| Storm | fast (waves at `c_s`) | an event to ride out | over-channeling / vent discipline while the field is actively hostile |
| Desert | slow (creeps over the playable economy) | a consequence to prevent | over-reaping, over-provisioning, neglect — the *economy's own* pressure |
| BH | slow → terminal | a world to answer or leave | the endgame's stakes: a world can genuinely end, and escaping it is a decision |

### 5.3 The no-free-energy discipline — hazards cannot be gamed into coherence

The single hard rule that keeps the danger layer honest is the corpus's
**no-free-energy cap** ([`energy-harnessing.md`](./energy-harnessing.md) §6): *no conversion yields
more than it sinks*, structured as write-back amplitude caps (`output ≤ φ⁻¹·input`).
The danger layer inherits it unchanged, and it closes the obvious exploit:

> **The auroral collector already harvests the `(1−q)` drains the field sheds
> ([`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) §3.4). A storm or a desert *creates* such
> drains — so a player could be tempted to *farm* them.** The tension is designed,
> not accidental: the collector is net-negative (it taps only the `(1−q)` fraction
> that would be wasted, is bounded by the §6 cap, and is *diminished as the player
> heals the field*). A hazard-farm cannot mint coherence — brighter drains yield
> more, but the cap keeps it a costed, diminishing tap, never a grinder. The
> anti-corruption hold that prevents a desert is itself a net-negative spend
> (§3.3), so there is **no "intentionally cause a hazard to mine it" loop that
> pays.**

The §6 cap is a [design] gate (the theory does not forbid overdraw; the *game*
must, as the energy doc's own §6 states). The danger layer is where that gate is
most load-bearing, because hazards are exactly the places the field is most
"wasteful" — and therefore most tempting to harvest.

---

## 6. Honest gates

### 6.1 Engine-real vs designed — where each hazard's physics genuinely sits

| Hazard | Engine-real (the field does this) | [design] (the presentation/pacing/tuning) |
|---|---|---|
| **Decoherence storm** | `ε² = (EY − φ·EI)²` is a real derived channel; a random-perturbation injection raises it; a `c_s`-traveling wave front crosses the material dissolution floor; the field re-locks and heals | *which* source ignites a storm; the "storm front" as a presented rolling event; storm frequency/size/cadence; the visible pre-warning colors |
| **The desert** | `q` collapse is the field's state; `q`-dependent precipitation/steering/healing are engine-real; the field-poor state is the mixture's empty measure ([`world-seams.md`](./world-seams.md) §1.2/§2.1) | the *gameplay* of "drought" — the desert as a named, creeping, preventable consequence; the exact `q` thresholds (`[q_low, q_high]` scaling, [`energy-harnessing.md`](./energy-harnessing.md) §7 Q1) that separate "living plain" from "desert" |
| **BH accretion** | `mass += acc_rate·qi_local·cell_vol` (engine-verbatim), the softened sink force, the self-reinforcing `q` draw, the merge-lineage deep end | the *framing* (hazard vs reservoir); the "accretion front = moving dissolution boundary" as a presented frontier; feeding/starving/evacuation as the game's costs |

The line is never blurred: **the storm is the PDE's wave dynamics, the BH is the
BH sector, the `q` collapse is the field's state — all engine-real. The hazard
*pacing, frequency, tuning, and the "storm front"/"desert"/"accretion" as presented
events are design.** This mirrors the ecology's probe discipline ([`field-emergent-ecology.md`](./field-emergent-ecology.md)
§1.3): the physics is real; the *gameplay lens* is designed and flagged.

### 6.2 The player-agency gate — can hazards be prevented by maintenance?

The design's **recommendation is the former: hazards are preventable by
maintenance, not scripted triggers.** Concretely:

- **The desert is fully preventable by maintenance** (§3.3): anti-corruption
  investment, Qi-bath husbandry, and not over-reaping end every listed cause.
- **The storm is *influencable* by maintenance, not fully preventable:** you cannot
  stop the field from being perturbed (a distant cause, the field's own waves, an
  external drain), but you can *mitigate* it by vent discipline and by keeping
  sheltering regions coherent. The storm is the one hazard that can arrive with no
  player-caused trigger — it is the field's own extreme, not a punishment.
- **The BH is preventable only while young:** starve it (§4.3) before its `mass`
  outgrows any hold; once it out-eats anti-corruption, only evacuation remains.

**[design] No scripted triggers.** A hazard never fires because the game decided
it was time; it fires because the field's real channels crossed a designed
threshold (a local `ε²` budget exceeded, a regional `q` fell below a floor, a BH
`mass` passed a self-reinforcing point). The **thresholds** are the tuning the
design owns; the *trigger* is the field's own dynamics. This is the honest,
non-dm's-fiat way to put stakes in the world.

### 6.3 Performance / budget of a presented storm

A presented storm is a **reading of already-published, already-sampled channels** —
it costs nothing new to *detect* (the sampler already reads `ε²`/`q` every tick,
`corpus-reconciliation.md`: server ≈ 1–6 ms, the ≈ 6 MiB publish). The new costs
are:

| Cost | What it is | Gate |
|---|---|---|
| **Rendering the front** | the storm's dissolution edge is a *re-quantization* of blocks the field already quantizes (`chunk-field-quantization.md` §3) — it is not a new particle pass, but it *does* churn the dirty-chunk meshing scheduler | must stay within the mesh-regeneration budget the dual-world grid already sets ([`volumetric-terrain.md`](./volumetric-terrain.md): dynamic meshing is scheduled/budgeted per tick) |
| **Pre-warning rendering** | auroral flicker + `(1−q)` glow shifts are render-layer reads of the published channels — cheap, but must not double the sky pass | [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) §1.5 (continuum fog/wind layer; no new subsystem) |
| **Per-tick hazard evaluation** | detecting "a desert is forming" / "the BH reached a threshold" is a bounded sampler-side reads of `q`/`ε²`/BH records — not a grid walk | must fit in the server sample budget (≈ 1–6 ms per `corpus-reconciliation.md`); the sparse BH record is ~KB, not ~6 MiB ([`ksp-kernel.md`](./ksp-kernel.md) §1.2) |

The honest gate: **a presented storm must not exceed the meshing + sky-pass budget
the living-terrain demo already pays.** The storm changes *what* is meshed (blocks
dissolve/re-condense), not *how much* — so the gate is the same dirty-chunk + LOD
scheduler that already exists, at the same bound. Measure a worst-case storm-front
sweep against the per-tick budget before claiming it.

---

## 7. Feasibility verdict

**Phase-1 — nothing new; hazards are the same channels read with intent.** The
storm's detection, the desert's detection, and the BH's presence are all reads of
the published `q`/`ε²`/`∇(g·Φ)`/sparse-BH channels the sampler already reads
(`corpus-reconciliation.md`: the ≈ 6 MiB publish, the sparse condensed-body array,
the per-tick sample budget). The *physics* is engine-real: `ε²` fronts are the
PDE's wave dynamics; `q` collapse is the field's state; BH accretion is the BH
sector verbatim. **The Phase-1 deliverable is the *presentation*** — turning
"the field is doing something" (a rising `ε²` region, a thinning band, a growing
BH record) into a *readable* hazard with a *costed* response. That is almost
entirely design work over existing channels, not `new engine code`. The two
Phase-1-bound pieces are (§6.3) the storm-front meshing re-quantization budget and
the pre-warning render layer — both reuses of the existing living-terrain and
sky layers.

**Later — the evacuation composes world-seams (§4.3).** The BH's terminal response
— leaving a dying window — is `world-seams.md` + `ksp-kernel.md`, which are Phase 2+
(downstream of the tree arm, condensed bodies, the Q4 channel; [`ksp-kernel.md`](./ksp-kernel.md)
§7). A BH evacuation is *the* test that a world can end and the answer is a ship
([`world-seams.md`](./world-seams.md) §2, §3) — honest sequential work on the already-designed
KSP/world-seams stack.

**Verdict.** The danger layer is sound because it introduces **no new physics and
no new subsystem**: it is the corpus's existing field operations, read as threat.
Binding risks, in order: **(a)** the storm-front meshing budget (§6.3 — a storm is
a traveling re-quantization event and must not outpace the chunk scheduler),
**(b)** the hazard-threshold tuning that separates "a storm" from "weather" and
"the desert" from "a quiet region" (§6.2 — a *design* dial, not physics), and
**(c)** the no-free-energy gate held against hazard-farms (§5.3 — the one place a
[design] cap can break). None contradicts the async, dual-world, or regime-collapse
architecture. **The honest statement that makes this doc load-bearing: a living
world needs stakes, and CassiCraft's stakes are not enemies but the field's own
extremes — a world that can be wounded, can starve, and can end, and whose only
defenses are the coherence, the discipline, and the ship the player has earned.**
The corpus invoked "scars," "ε² wells," "corruption" as dangers across fourteen
documents; this design is the danger they were always pointing at.

### Open questions

1. **Hazard-threshold scaling (§6.2).** The engine's `q ~ 1e-3…1e-1` at noise up
   to `≈ 0.947` at the attractor ([`energy-harnessing.md`](./energy-harnessing.md) §7 Q1). Where
   exactly does "a living plain" become "a desert," and how hard a local `ε²`
   budget merits a "storm"? Phase-1 tuning, measured off the living-terrain demo.
   **Counterpart (two-way):** [`tide-of-the-attractor.md`](./tide-of-the-attractor.md)
   open-Q3 makes the reciprocal demand from the season side — its thin-trough
   `q` valley must sit *above* this threshold's desert line, so the season reads as
   "low tide," not "the desert arriving." The two thresholds must be set together;
   each doc now cites the other.
2. **Storm provenance.** A storm's random-perturbation injection — is it exogenous
   (the field's ambient waves producing it on their own) or seeded by player/distal
   drains? The design allows both (§2.1), but the *balance* determines whether
   storms feel like weather or like punishment. Needs a probe: does the engine, on
   its own live field with terrain-coupling + damping ([`field-emergent-ecology.md`](./field-emergent-ecology.md)
   §6a's field-coupling caveat), *ever* spontaneously form a `c_s`-traveling
   decoherence front, or does it always need an injection? The answer sets whether
   the storm is a pure-presentation reading or needs a designed trigger.
   **Counterpart (two-way):** a deliberate-`ε²` answer to the same question is in
   [`field-npc-ai.md`](./field-npc-ai.md) §4.3 — a decoherence-wielder venting a large
   enough uncontrolled `ε²` burst *is* such a seed (storm-ignition as a weapon); this
   doc's provenance probe settles whether that ignition needs an injection or can
   arise on its own.
   **Operationalized by [`weather-not-storm.md`](./weather-not-storm.md) §3** — that doc
   pre-registers this exact probe (can the field spontaneously hold an ordered `c_s`
   `ε²` structure at all?), with the statistic, decision tree, and stopping rule, and
   both verdicts licensed (verdict-A: storms are the field's extreme, weather is real;
   verdict-B: every storm carries a source — the classifier becomes the world's
   detector of whose storm it is). Its §6a gates the storm's season and the Coda's
   formation on the same verdict. This open-Q's answer is that probe's recorded
   output, not a fresh fork — the weather doc is the pre-registered owner of the
   measurement this question asks for.
3. **The BH starvation vs over-provisioning boundary.** A BH is both hazard and
   reservoir (§4.3). What `mass`/`qi_local`/`acc_rate` regime makes feeding it clean
   vs. makes its draw a self-reinforcing starvation? The energy doc's Q4 ("BH as
   player-accessible reservoir — Phase-1 or 2?") and this doc's hazard threshold are
   the same boundary from two sides; it must be set together.
4. **The dead window.** Once a desert fully takes a region (its `q` below any
   spendable floor), the design's honest end is "wait for the `ω₀²` re-bind over
   game-time" or "leave" (§3.3). Is a *fully dead, unrecoverable* window a real
   state, or does the attractor always eventually re-bind a region (making "desert"
   always recoverable-with-time)? The answer is a Phase-1 field-side measurement
   and it defines whether evacuation is *necessary* or *optional-timed*.
   **Counterpart (two-way):** [`field-npc-ai.md`](./field-npc-ai.md) open-Q5 asks the same
   boundary from the commons side — a drained-then-deserted village may be a
   recoverable state (anti-corruption) or the start of a regional desert here; the
   two must be set together.
   **Consumer (two-way):** [`wound-remembered.md`](./wound-remembered.md)
   `§6b`/`§7` treats this probe as its **deciding gate** — does a broken lock
   re-open or heal? Its persistence claim (a *deliberate* lock-break re-opens as a
   wound where an accidental dent heals as a scar) rides the same measurement: if
   the attractor always re-binds, the wound collapses to a presented-unhidden scar.
   The scar-lifecycle verdict this open-Q asks for and the wound's distinct-state
   claim are read off one result; the two docs now cite each other.
5. **Storm residue vs the archaeologist's model.** A storm scar is claimed to be
   residue (§2.4). Does a storm-created `q`-locked pocket + ghost halo read
   identically to the archaeology model's dissolved-organism residue
   ([`field-archaeology.md`](./field-archaeology.md) §3.1), or does it need its own signature? If it
   needs its own, archaeology gains a *natural* source of fresh residue; if it's
   ambiguous, the reader must be tuned to separate storm-scars from fossils (§6c of
   the archaeology doc).

---

## Cross-references

- [`material-regimes.md`](./material-regimes.md) — the dissolution floor, the `(1−q)` waste law, the fire-vs-explosive discharge rate, the gas regime — every hazard rides these (§1–§3).
- [`energy-harnessing.md`](./energy-harnessing.md) — the anti-corruption hold (§5.4) = every hazard's engine-real defender; the Qi bath (§4.4); the no-free-energy cap (§6); the BH reservoir (§1.6/§2.6) — the hazard's other face.
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — the `q`-band/low-`ε²` spawn rule the desert starves; the biosphere's drift; conservation = anti-corruption (§2, §4, §5.3).
- [`coherence-magic.md`](./coherence-magic.md) — the ε² vent, overdraw → full-cascade discharge, the reader — "hazards readable before they arrive" (§1–§2).
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — the sky reads the storm first (auroras = the reader's atmospheric form, §3.3); the `(1−q)` glow; the auroral collector at the §5.3 no-free-energy gate (§3.4).
- [`field-archaeology.md`](./field-archaeology.md) — the dig perturbs the field / lowers regional q (a desert cause, §3.2); storm scars and BH archives as residue (§2, §4).
- [`the-scavenger.md`](./the-scavenger.md) — **the danger layer's first non-hazard row.** §1's no-monster-table rule — "every hazard is the field at an extreme" — the scavenger obeys while being §3.3 there's *first positive row*: a residual-structure run that fits the spent, lawfully harmless to the maintained (a scavenger fed on your waste does not hunt you). Reverse pointer: the scavenger is the non-hazard the danger layer's §1 house style admits.
- [`the-scar-lifecycle.md`](./the-scar-lifecycle.md) — **the scar-lifecycle probe answered.**
  §4.1 there reads open-Q4 this doc (does a broken lock re-open or heal?) as decided: a
  shallow wound heals under rest, a deep one persists as a kept scar (§2 there) — the
  §6b/§7 re-bind-vs-persistence verdict the lifecycle's three fates ride. Reverse pointer:
  the scar-lifecycle is the answer open-Q4 awaited.
- [`the-commensal.md`](./the-commensal.md) — **the layer's first positive row.** §3.3 there
  reads §1 this doc's danger-layer house style (no monster table, every hazard the field at
  an extreme) and joins it as the **first non-hazard, the first positive face** — a
  surplus-margin run presented as a read, never a spawn (§5c there); §5.3's no-free-energy
  gate is the honest bound on its assist (§5d there). Reverse pointer: the commensal is the
  danger layer's lawful companion row.
- [`world-seams.md`](./world-seams.md) + [`ksp-kernel.md`](./ksp-kernel.md) — the evacuation the BH's endgame composes (§4.3); the field-poor interstitial a dead window becomes (§3).
- [`volumetric-terrain.md`](./volumetric-terrain.md) — terrain heals (hazards fight the heal); the dynamic-meshing budget the storm-front re-quantization must respect (§6.3).
- [`the-mirror-creature.md`](./the-mirror-creature.md) — **the sixth face.** §1/§5 there
  read §1 this doc's danger layer house style (the mirror joins the stranger layer as its
  sixth face) and §5.1 readable-before-it-arrives — inverted for the mirror (it is only
  readable by testing); §5.3 the no-free-energy gate it inherits. Reverse pointer: the
  mirror is the field's confusion-stranger.
- [`the-cave.md`](./the-cave.md) — **the BH's swept wake.** §2c there reads §4
  this doc's BH accretion (§4.2 the `q`-draw, §4.3 starvation, §4.4 what it ate) and
  open-Q4 the dead-window / re-bind verdict (whether the swept wake holds hollow).
  Reverse pointer: the cave is one hazard's lawful aftermath read as a place.
- [`the-witness.md`](./the-witness.md) — **the lawful non-row.** §5e there reads §1
  this doc's danger layer house style and §5.1 readable-before-it-arrives (the witness
  has no approach; it is only the field's attention) and §5.3 the no-free-energy gate
  — the witness is the danger layer's first non-face, not a hazard (no row, no
  threat, no response). Reverse pointer: the witness is the lone non-row of the
  threat table.
- [`the-wind.md`](./the-wind.md) — **the flow-face of the storm.** §2 there reads §2 this
  doc's `c_s`-traveling `ε²` front (a wind moves it) and §5.1 readable-before-it-arrives
  (the wind's carry reads the same way); §5.3 no-free-energy (a storm's drains, a
  wind's carry — never farmable). Reverse pointer: the wind is the flow-face the storm
  rides.
- [`the-climb.md`](./the-climb.md) — **the honest dangers at height.** §4 there reads
  the desert/BH (a thin face's `(1−q)` waste at height); §5.1 the
  readable-before-it-arrives discipline the climb's read inherits. Reverse pointer:
  the climb reads the hazards' thin-face waste.
- [`the-rain.md`](./the-rain.md) — **the readable-before-it-arrives case.** §5.1 there
  reads the hazards readable before they arrive (the rain's flood-beginning is
  readable the same way). Reverse pointer: the rain's flood-beginning is readable.
- [`the-roost.md`](./the-roost.md) — **the legible home.** §5.1 there reads
  readable-before-it-arrives (applied to home); §1 the no-monster-table house style
  (a roost is a presented reading, never a spawned den); §5.3 the no-free-energy gate.
  Reverse pointer: a roost is a presented reading, never a spawned den.
- [`the-desert.md`](./the-desert.md) — **the hazard-twin.** §3 there reads the desert
  (a regional `q` collapse, the slow preventable consequence); §6.2 the
  hazard-threshold tuning; the hazard's desert is where the Coda *forms* — this doc's
  desert is where a window *lives*. Reverse pointer: the desert is the hazard-twin
  where a window lives, not where the Coda forms.
- [`the-smell.md`](./the-smell.md) — **the readable-before-it-arrives.** §5.1 there
  reads the hazards readable before they arrive. Reverse pointer: the scent is the
  hazard's approach read before it arrives.
- [`the-blizzard.md`](./the-blizzard.md) — **the hazard read.** §2 the storm’s `c_s` front (what the blizzard is not); §5.1 readable-before-it-arrives. Reverse pointer: the blizzard is a hazard read of the same channels.
- [`the-chant.md`](./the-chant.md) — **the readable-before.** §5.1 the readable-before-it-arrives (a chant’s call readable ahead). Reverse pointer: the chant’s sustained call is readable before it resolves.
- [`the-balefire.md`](./the-balefire.md) — **the readable warning.** §5.1 readable-before-it-arrives (the balefire is the warning read ahead). Reverse pointer: the balefire is the hazard’s readable-before warning.
- [`the-fog.md`](./the-fog.md) — **the readable blur.** §2 the storm’s `c_s` front (what the fog is not); §5.1 readable-before; §1 the no-monster-table; §5.3 the no-free-energy. Reverse pointer: the fog’s blur is readable, never hidden-only.
- [`the-lightning.md`](./the-lightning.md) — **the storm’s release.** §2 the `c_s`-traveling `ε²` decoherence front; §2.1 the dis-organized injection; §2.3 readable-before-it-arrives; §5.3 the no-free-energy gate; open-Q2 the storm-provenance probe. Reverse pointer: the lightning is the storm’s release — the gathered charge letting go at once, the corpus’s storm discharge locus.
- [`world-difficulty.md`](./world-difficulty.md) — **the dial’s ceiling.** §1 the extremes; §2 the storm as a `c_s`-traveling `ε²` front; §5.1 readable-before-it-arrives; §5.3 the no-free-energy gate; open-Q2 the storm-provenance probe. Reverse pointer: world-difficulty scales the field-hazards’s extremes — never a hidden punishment, the honest dial of the field’s own behavior.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers (cited, not re-derived).
- Engine (read-only): `CassiCosmos/compute/cassi_two_fluid.glsl` (the PDE, ε², source terms), `CassiCosmos/compute/cassi_bh_integrate.glsl` (BH accretion — `mass += acc_rate·qi_local·cell_vol`), `CassiCosmos/compute/cassi_nbody_gravity.glsl` (river law `a = −G_N·(π/ρ)·∇(g·Φ)`; the softened BH sink term), `CassiCosmos/compute/cassi_condensation.glsl` (the `q > threshold` nucleation the storm pushes matter across).
