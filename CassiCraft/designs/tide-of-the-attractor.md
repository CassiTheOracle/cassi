# The Tide of the Attractor: The Living World's Slowest Breath

**Question under design:** how the whole living world shares one temporal tempo —
a **season** that is not weather but the mixing clock given a face. If
[`world-seams.md`](./world-seams.md) makes *where* matter (the spatial horizon of
anchored windows), the **tide** makes *when* matter: on a long cycle a region's
operating coherence `q` breathes between **harvest** (the field at its most
organized: high `q`, low `ε²`, cheap machines, ore precipitating, the biosphere's
attractor basins at full strength) and **thin** (q troughs: machines glow bright
and wasteful off the `(1−q)` floor, organisms shed, the desert-margin creeps).
The player does not fight a weather event; they **read and plan around a season.**

Crucially, this document adds **no new engine term.** The tide is a *pacing lens*
over an attractor relaxation the field is already living — the theory's mixing
clock made readable and playable. Every system an existing design doc already
composes onto the field's `q`/`ε²`/`ρ`/`∇(g·Φ)` channels gets a large-scale
rhythmic context, the temporal twin of world-seams' spatial horizon.

Companion to:
- [`energy-harnessing.md`](./energy-harnessing.md) — the Qi bath (§4.4) is the
  tide's cheap-zone anchor; the `(1−q)` glow (§2) is the waste read; the ambient
  cascade pump (§1.7) is the background drift the tide rides; the constraint
  economy (§6) caps conversion at both tides.
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — biome⇔regime (§4);
  the recognition rule (§6b); **the biosphere drifts with the field** (§4.2) — and
  the tide shifts which basins persist through the cycle.
- [`field-hazards.md`](./field-hazards.md) — the desert (§3) is the tide's trough
  *made regional*; the tide gives the desert a predictable season, so prevention
  becomes **husbandry with a clock.** The storm's `ε²`-front (§2) is the short
  event the tide's phase frames.
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — weather =
  envelope waves (§1.3); the tide is the **long-period envelope mode**; the
  aurora (§3) is a field diagnostic across the tide.
- [`material-regimes.md`](./material-regimes.md) — a tide-high region runs
  near-lossless at the `(1−q)` floor (§3); ore precipitation = `q` accumulation
  (§3); hardness = rung (§4).
- [`coherence-magic.md`](./coherence-magic.md) — channeling efficiency rides the
  tide; resonance with the field (§3.1).
- [`field-music.md`](./field-music.md) — the ambience breathes with the tide.
- [`field-archaeology.md`](./field-archaeology.md) — residue is stable only where
  local `q` stays above its dissolution threshold (`§6b`); the tide's trough
  threatens that stability and can **expose** shallow residue.
- [`custom-blocks.md`](./custom-blocks.md) — **realizability is contextual**
  (§2, §7 Q2); the tide shifts which tuples are realizable at a given phase.
- [`world-seams.md`](./world-seams.md) — the temporal twin; the long dark's voyage
  can be timed to the tide.

Theory grounding (CassiTheory — read-only, cited by relative path):
- `CassiTheory/speculations/qi-as-time-clock.md` — the **mixing clock**
  `T = 2π/[λ(1−q)]`, n-independent, the attractor's relaxation cadence; the
  `(1−q)` openness gate `λ_mix = λ(1−q)` (§2.2); the distinction between the
  **flow clock** (`dτ ∝ q`, high-q = "more time") and the **openness clock**
  (`dτ ∝ (1−q)`, mixing runs faster where q is low) (§3) — the tide uses the
  *openness* reading, because (1−q) is the relaxation rate.
- `CassiTheory/speculations/qi-time-ladder-derivation.md` — the mixing clock
  `T = 2π/[λ(1−q)]` has **exponent 0** (n-independent) (§7); the **winding bound**
  `|δn| ≤ atan(φ)/2π ≈ 0.162` rungs per relaxation (sub-rung phase offset,
  n-independent) (§5); the frame's honest claim that no independent φ-exponent
  time ladder closes, and that a designed schedule *realizes* rather than
  *derives* tempo (§8).
- `CassiTheory/foundations/spiral-dynamics.md` §2.1 — the mixing clock and its
  uniform per-rung rate (`dn/dt = (λ/2π)(1−q)`).

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived), engine-verbatim, or flagged
**[design]** / **[probe]** where it extends engine terms to a *presented* rhythm
the engine does not (yet) drive. The line between the field's real attractor
relaxation and the designed seasonal reading is drawn in §5 and never blurred.

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| The tide = ? | The **mixing clock `T = 2π/[λ(1−q)]` given a face** — a long cycle where a region's operating coherence `q` breathes between a harvest (organized) and a thin (trough) phase. A *pacing lens*, not a new engine term. |
| What breathes | the window's/region's **regional `q`** — low at thin (machines waste `(1−q)`, basins shed), high at harvest (near-lossless, organisms thrive, ore precipitates). |
| What's constant | the field's own physics. No new term, no new channel; the tide reads/paces the `q` the engine already publishes. |
| The clock's status | the mixing clock `T = 2π/[λ(1−q)]` is **derived** in the theory solver (the `(1−q)` gate), but the **engine kernel is q-free** (`ω₀²·(EY−φ·EI)`), so the tide's "relaxation-cadence" reading is a **proposed/interpretive lens** whose measurability is the open probe — see §5(a). |
| Player lever | plan around the season: **husbandry with a clock** (prevent the desert at its trough), **harvest the harvest**, do **Still-Room-scale deep work** at harvest, **voyage** at the right phase. |
| Readable | the reader (regional q trend), the sky (aurora brightness), a Weatherglass-style ambient, the `(1−q)` glow floor. |
| Feasibility | **Probe = Phase-1.5** (a measurement on the living-terrain demo); the **pacing lens is design over existing channels** once the period is measured; the **season-system composes every existing doc onto the shared tempo**. |

---

## 1. The physics — the mixing clock as a large-scale regional q oscillation

### 1.1 What the clock is, honestly

The theory's **mixing clock** is the attractor's relaxation cadence
(`qi-as-time-clock.md`; `spiral-dynamics.md` §2.1):

```
T = 2π/[λ(1−q)]        the n-independent mixing/re-conversion period
```

The mixing **rate** is `λ_mix = λ(1−q)` (`qi-as-time-clock.md` §2.2): high where
the field is far from φ-equilibrium (q → 0) and **suppressed where the field is
coherent** (q → 1). This is the theory-solver's `(1−q)` openness gate — the term
that says the φ-attractor conversion is gated by how *open* (sub-equilibrium) the
field is. The clock `T` is the *period of that relaxation*: how long a state
takes to re-convert/re-lock toward the φ-locked line.

Three things matter for the tide, all from the theory's own classification:

1. **The clock is n-independent (exponent 0).** `qi-time-ladder-derivation.md`
   §7: the mixing clock's τ-exponent is `0`, uniform across cascade rungs. It is
   not a per-rung φⁿ ladder; it is a **single large-scale cadence** that applies
   the same way across the box. That is exactly what a "season" is — one tempo,
   not a hierarchy of rung-clocks.
2. **It is the *relaxation* cadence, not a winding rate.** The winding bound
   `|δn| ≤ atan(φ)/2π ≈ 0.162` rungs per relaxation (`qi-time-ladder-derivation.md`
   §5) is a **sub-rung phase offset**, n-independent — a state's clock phase can
   lag only ±0.162 rungs. So the tide, if it is real, is a *phase* the field's
   relaxation accumulates and sheds, not a growing per-rung drift.
3. **The honesty the theory itself insists on.** The q-gate `λ_mix = λ(1−q)`
   is **derived in the theory solver** but the **current engine kernel is q-free**
   (`ω₀²·(EY−φ·EI)`, `qi-as-time-clock.md` §2.1). And "local time from Qi" is an
   **interpretation** (flow vs openness), not a consequence (§3). **Therefore the
   tide is not an engine-verbatim fact** — it is a *proposed reading* of the
   attractor relaxation whose measurability is the open probe (§5a). The *one
   engine-real direction* that survives: **the attractor organizes, so the field
   has long coherent (harvest) and long thin states.** That is the load-bearing,
   physics-grounded claim; the seasonal *period* is what must be measured.

### 1.2 The tide as a pacing lens, not a new term

The design stance, stated once:

> **The tide is a pacing lens over the attractor relaxation the field is already
> living — it does not inject anything, change any constant, or add a channel.
> It interprets the engine's real `q`/`ε²` relaxation as a large-scale temporal
> envelope and paces every composed system's *operations* off that envelope.**

Concretely, the lens is a **derived regional-q trend**: the window's field drifts
through long organized states and long thin states as the φ-attractor competes
with the `ε²` drain, terrain coupling, and the RealSim dissipation terms
(`field-emergent-ecology.md` §6a's coupling caveat). A "season" is the time
between two crossings of a designed `q` threshold — the moment the regional
operating coherence tips from thin to harvest, or back.

The direction is engine-real; the *period, amplitude, and phase-locking* are what
the probe must measure (§5a). The tide does **not** force a sinusoidal `q`; it
*observes* whatever `q`-trend the coupled field actually produces and then gives
it a playing surface. If the field's relaxation is monotone (only heals toward
the attractor, no oscillation), the tide collapses to a **drift**, not a season —
and the design should prefer the honest drift reading over forcing a cycle.

**(design) The two states the tide names.** Even before the period is measured,
the two *states* are physically meaningful and engine-real:

| State | Regional field | What it means |
|---|---|---|
| **Harvest** | `q` high, `ε²` low, near the attractor (`q ≈ 0.947` per `coherence-magic.md` §1) | the field is organized: machines run at the `(1−q)` floor (near-lossless), ore precipitates where `q` accumulates (`material-regimes.md` §3), the biosphere's basins hold at full strength. |
| **Thin** | `q` toward the noise floor (`q ~ 1e-3…1e-1`, `energy-harnessing.md` §7 Q1) | the field is running wasted: machines glow off the `(1−q)` floor, organisms shed, the desert-margin creeps (`field-hazards.md` §3). |

**[probe]** Whether the *transition* between them is a smooth oscillation (a real
cycle), a stepped drift, or washes out entirely under the box's terrain coupling
+ damping is exactly what §5(a) pre-registers. The design is honest that the
season-system's *cadence* (how long a season is) is **not** implied by the clock
formula alone — `T = 2π/[λ(1−q)]` gives a *local* relaxation period whose numeric
value in Minecraft time is a calibration, not a constant.

### 1.3 Why the tide matters: "when" is a real axis

[`world-seams.md`](./world-seams.md) makes *where* matter — the spatial horizon
of anchored windows. The tide is the **temporal horizon's twin**: it composes
every field operation onto a shared, readable rhythm, so the player's *timing*
becomes a first-class resource alongside *position*. A machine placed at a
coherence ridge is doing "where"; the same machine run at harvest vs thin is
doing "when." The tide is what makes the second axis exist as legible gameplay
rather than an invisible floor.

---

## 2. The regime table — what each system does at harvest vs thin

The tide is not one new mechanic; it is a **shared tempo every existing system
runs against**. Each row below reuses the source doc's own terms and adds the
tide's phase as the outer clock.

| System | At harvest (q high, ε² low) | At thin (q low, ε² high) | Cross-ref |
|---|---|---|---|
| **Energy — machine efficiency** | machines run near-lossless at the `(1−q)` floor: `E_waste = (1−q)·E_throughput` is small. The Qi bath's core holds cheaply. | machines bleed most of their throughput to the `(1−q)` glow; the same machine is bright-and-wasteful. Efficient deep work is deferred to harvest. | `energy-harnessing.md` §2, §4.4 |
| **Energy — the `(1−q)` glow as the waste read** | glow is faint on healthy structures — the field is economical. | glow brightens across the region — *everything* glows wasteful, and the glow is the tide's legibility (the player learns to read the phase by how bright the world runs). | `energy-harnessing.md` §2; `field-music.md` §1 (the efficiency hum) |
| **Energy — Qi-bath economics** | a maintained high-`q` core is cheap to hold (the drain that feeds it is small); harvesting is rich. | the bath's standing draw bites — it must spend more to hold its core `q` up against the thinning field; the bath is "brittle" exactly where `energy-harnessing.md` §4.4 warns. A thin-tide bath is a liability unless fed. | `energy-harnessing.md` §4.4 |
| **Energy — ambient cascade pump** | the background attractor drift (§1.7) is at its strongest (the field is organizing); a machine harvesting it is richest here. | the ambient pump is weakest (the field is not organizing as hard); it is nearly free but yields little — not a season to build cheap power on. | `energy-harnessing.md` §1.7 |
| **Energy — auroral collector** | auroras are calm, coherent bands (the sky's diagnosis of a healthy field) — yield is modest. | a thin, draining field pours coherence into wells; auroras over drains brighten (**a brighter aurora = richer harvest**), a perverse-but-honest "harvest the wounding" that the §6 no-free-energy cap still bounds. | `atmosphere-orbits-auroras.md` §3.1/§3.4; `field-hazards.md` §5.3 |
| **Ecology — attractor-basin persistence** | the basins the field revisits hold at full strength; deep, layered φ-locked organisms persist on coherence ridges. | basins shed: shallow, single-scale, φ-incommensurate morphs de-cohere and dissolve; only the deep-rung fraction persists as residue. The biosphere's *population* thins with the field. | `field-emergent-ecology.md` §3/§4 |
| **Ecology — spawning bands** | the `q` coherent band + low-`ε²` spawn rule (`chunk-field-quantization.md` §2.2) is widely met — creatures precipitate across the region. | the coherent band shrinks to the ridges the field still holds; spawning concentrates there. **At thin tide, reading the field finds where life still is.** | `field-emergent-ecology.md` §4.2; `chunk-field-quantization.md` §2.2 |
| **Hazards — the desert** | the desert-margin holds; anti-corruption holds a region up cheaply. | **the desert's seasonal creep**: the regional `q` collapse (`field-hazards.md` §3) is most likely to take at the tide's trough, when the field is already de-organizing. Prevention = husbandry done *before* the trough. | `field-hazards.md` §3 |
| **Hazards — the storm** | the field is organized, so a `ε²` front is less likely to ignite and less damaging once it passes a coherent region. | the field is already wasteful and decohered; an incoming `ε²` front (`field-hazards.md` §2) finds it *ready to dissolve*. Storms are **more frequent and more dissolving at thin tide**. | `field-hazards.md` §2 |
| **Atmosphere — the long-period envelope mode** | the envelope's waves are calm, coherent; the sky reads "healthy." | the envelope's turbulence grows (the `ε²` spikes of `atmosphere-orbits-auroras.md` §1.3 are weather); the sky darkens and the storm-band thickens. The tide is the longest-period envelope mode. | `atmosphere-orbits-auroras.md` §1.3 |
| **Atmosphere — aurora brightness** | auroras are calm, slow, coherent bands; the sky's diagnostic reads a healthy body. | auroras brighten/restless over drains (a wounded field reads bright at range) — a thin-tide sky is *brighter where it's worse*. The aurora is the tide's atmospheric legibility. | `atmosphere-orbits-auroras.md` §3.3 |
| **Materials — ore precipitation** | ore precipitates where `q` accumulates above `θ_c` by *coherence* (`material-regimes.md` §3). At harvest, `q` is accumulating — **ore veins form/fill**. | `q` is not accumulating (the field runs wasted); ore does not precipitate, and existing high-`ε²`-touched deposits can re-dissolve. **Mining trips are best planned to a harvest window.** | `material-regimes.md` §3 |
| **Materials — the `(1−q)` floor near-losslessness** | deep-rung matter holds its φ-lock; tools/mining at the `(1−q)` floor are near-lossless. | `(1−q)` is large; every operation wastes; reaping deep rungs scars more because the healing field is weaker. **The charge/scar asymmetry is worse at thin tide.** | `material-regimes.md` §3/§4; `energy-harnessing.md` §3 |
| **Materials — realizability shifts** | a tuple realizable at harvest (**`custom-blocks.md` §2/§7 Q2: realizability is contextual, a property of the local field state**) — a high-`q`-at-low-`ε²` regime condenses. | a harvest-`q` tuple may be **unrealizable at thin** — the same region no longer holds the `q`/`ε²` the tuple demands, so it *fails precipitation* ("the field doesn't make this here") or *meta-decays*. **Authoring is a harvest-time act.** | `custom-blocks.md` §3 |
| **Magic — channeling efficiency** | channeling is efficient: the ε² vent is small (the field heals fast), resonance (`coherence-magic.md` §3.1) is easy to match. B recovers fast standing in the high-`q` field. | the vent backs up (the field heals slowly), resonance is hard to match (the field's rhythm is decohered), overdraw risk rises. **Still-Room-scale channeling is a harvest act.** | `coherence-magic.md` §1.2, §3.1 |
| **Music — the ambience breathes** | the φ-tempered drone is rich, consonant, layered (the field-tempered ambience of `field-music.md` §1). | the ambience thins toward near-silence — the desert's signature, the honest sound of a field that "has nothing to say" (`field-music.md` §2.3). | `field-music.md` §1, §2.3 |
| **Archaeology — residue exposure** | residue is stable — the local `q` stays above its dissolution threshold (`field-archaeology.md` §6b), so strata hold and deep cores are q-locked under the surface. | **shallow residue can be exposed**: as regional `q` drops toward `q_dissolve`, residue the field could hold at harvest is threatened — and at the trough, an over-reaped/de-epscoped locality can re-dissolve residue, *surfacing* ghost halos that were buried. Thin tide is the archaeologist's window (find what the field is about to lose) and the conservation pressure. | `field-archaeology.md` §6b, §3.1 |
| **World-seams — the voyage** | a ship crossing the dark wants its own Qi bath strong; **timing the departure to the home window's harvest** gives the longest carried-field before the thin offload. The long dark's cost is a coherence budget (`world-seams.md` §2.3), and launching from a harvest window is the economic edge. | you *can* sail from thin, but you burn the reserve harder against the weaker carried field — a **voyage timed against the tide** is shorter/reachier for the same coherence. | `world-seams.md` §2.3 |

**Planted at a place (reverse pointer, two-way).** These two states (harvest/thin)
are what a settlement's *standing* tide-gauge marks: [`the-tide-staff.md`](./the-tide-staff.md)
§2.1 is the planted cast-`q` staff rooted at a place whose **band** reads which of
this §2's states it is in and whose rise/fall shows "the accumulation the probe
measures" (`the-tide-staff.md` §2.1/§2.2 — it cites this §2's states as the band's
two feet and §5a's probe as the drift's source). This §4's observability named the
tide's reads; the staff is its *physical, standing* form — the Weatherglass-style
ambient read made planted; the two docs now cite each other as read-and-answered.

---

## 3. Seasons as gameplay — read the tide, plan around it

### 3.1 The player's stance: husbandry with a clock

The tide is not a weather event to dodge; it is a **season to plan around.** The
desert is the cleanest expression (`field-hazards.md` §3): it is a consequence,
not a creature — the slow `q` collapse that a region's over-reaping /
over-provisioning / neglect drives. The tide gives that consequence a *predictable
worst*: **the desert is most likely to take at the tide's trough, when the field
is already de-organizing.** Prevention therefore becomes husbandry done *against
the clock*:

- **Watch the reader's regional-`q` trend.** As the trend falls toward thin, the
  desert's four causes (`field-hazards.md` §3.2: over-reaping, BH draw, sustained
  overdraw, field drift) become more dangerous — the field that would heal them is
  weak.
- **Invest early.** Anti-corruption (`energy-harnessing.md` §5.4) and Qi-bath
  husbandry (§4.4) are cheapest *before* the trough. **A living bath is the
  desert's answer** (`field-hazards.md` §3.3) — and a bath held through a thin tide
  is what keeps the margin from creeping in.

This is the honest seasonal read of the desert: **the tide does not remove the
hazard — it gives the player the planning window to prevent it.** A predictable
trough is still a trough; the season is a planning aid, not a removal (§5c).

### 3.2 Harvest the harvest

Conversely, the season tells the player when to *do the deep, expensive,
`q`-hungry work*:

| Act | Why harvest | Cross-ref |
|---|---|---|
| **Ore precipitation** | `q` is accumulating — veins form/fill. | `material-regimes.md` §3 |
| **Still-Room-scale channeling** | the vent is small, resonance is matchable, overdraw risk low. | `coherence-magic.md` §3.1 |
| **Authoring / custom-block realization** | a harvest-`q` tuple is realizable; at thin it may fail or meta-decay. | `custom-blocks.md` §3 |
| **Qi-bath construction / deep-rung mining** | cheap to organize, near-lossless floor, weaker scarring (the field heals fast). | `energy-harnessing.md` §4.4/§3 |
| **Auroral-collector farming of wells** | *(counter-intuitively)* thin is richer per-site, but bounded by the no-free-energy cap — a deliberate harvest-the-trough play, the same honesty as the "brighter aurora = richer harvest" of `atmosphere-orbits-auroras.md` §3.4. | `atmosphere-orbits-auroras.md` §3.4 |

### 3.3 "When" matters as much as "where" — the temporal horizon

The tide makes timing a resource. The player who learns to read the phase:

- **Builds the Qi bath and does deep-rung work at harvest** (cheap, near-lossless).
- **Prevents the desert at its seasonal worst** (before the trough, when the field
  is bare) — husbandry with a clock.
- **Times the voyage to the home window's harvest** (`world-seams.md` §2.3): a
  ship that leaves toward thin burns the carried field harder; leaving from a
  harvest window stretches the same coherence further across the dark.
- **Plans the archaeology dig for the trough** if they want to *find* what the
  field is about to lose (§2, archaeology row) — and for harvest if they want a
  stable, productive site.

The through-line is the corpus's own "field is where matters, and its state is
when": **the temporal horizon is the twin of the spatial one.** Just as a window
is a place the law fills, a season is a time the law is organized — and the
player reads both.

---

## 4. The observability — the tide is readable, not a hidden clock

The cardinal hazard rule of the corpus is **readable before it arrives**
(`coherence-magic.md`: hazards should be readable; `field-hazards.md` §5.1). The
tide obeys it on **four channels**, so a player learns the phase from the world's
own field, not from a HUD clock:

| Observable | What it reads | Cross-ref |
|---|---|---|
| **The reader (regional q trend)** | the coherence reader (`coherence-magic.md` §2 — the Phase-1 deliverable) already renders `q`/`ε²` as a magnetometer. The tide is a *trend* over that read: the reader shows the direction (q rising toward harvest, falling toward thin) and the band. | `coherence-magic.md` §2 |
| **The sky (aurora brightness)** | `atmosphere-orbits-auroras.md` §3.3: auroras are the reader's atmospheric form. A healthy body shows calm, coherent bands (harvest); a thin field shows restless, bright discharges over drains. **The sky is the tide's long-range legibility.** | `atmosphere-orbits-auroras.md` §3.3 |
| **A Weatherglass-style ambient read** | a small instrument that shows the local/regional `q` trend as a rising/falling marker — the "weather vane" of the coherence field. **[design]** an extension of the reader into a dedicated season instrument (the reader is a handheld scan; the weatherglass is a *mounted* trend monitor). | `coherence-magic.md` §2 (reader basis) |
| **The `(1−q)` glow floor** | `energy-harnessing.md` §2: every working machine wastes `(1−q)` as visible glow. At thin tide, *everything glows* — the world itself runs bright-and-wasteful. The player reads the phase by **how brightly the world burns.** | `energy-harnessing.md` §2; `field-music.md` §1 |

**The legibility rule.** The tide is designed to be **read, not hidden** — the
phase is a *trend* a player can learn to feel from the reader, the sky, and the
glow, exactly as they learn to read the desert's creep before it takes. There is
no invisible countdown; there is a field with a pulse, and the pulse is the
clock the whole tempo runs on.

---

## 5. Honest gates

### (a) The probe — does the box's regional q oscillate at all?

This is the load-bearing question, and it must be pre-registered the way the
ecology's silhouette probe is (`field-emergent-ecology.md` §1.4). The mixing
clock `T = 2π/[λ(1−q)]` is **derived in the theory solver but the engine kernel
is q-free** (`qi-as-time-clock.md` §2.1), so whether a *Minecraft-anchored* field
with terrain coupling + damping produces a *measurable* regional-`q` oscillation —
or washes out to a monotone drift — is unmeasured. **[probe]**

| Probe step | Action | Deciding output |
|---|---|---|
| T1 | Run the Phase-1.5 living-terrain demo (the coupled box, per `chunk-field-quantization.md` §1.2, `dt = 0.05`, normal terrain coupling + RealSim damping) from a seeded IC. | a long temporal series of the window's **regional `q`** (a box-averaged or ridge-weighted mean over the published `field_q`). |
| T2 | Band-filter/detrend the series and test for a dominant period against a null (white-noise / monotone-drift) model. | a period measure (or a "no oscillation" verdict) with a significance statement. |
| T3 | If a period exists, measure its **amplitude** (how far `q` swings between harvest and thin) and its **damping** (does the oscillation persist or decay over many periods?). | the season's amplitude + persistence. |
| T4 | Decide: **real season** (stable, measurable regional-`q` oscillation) vs **drift** (the field relaxes monotonically toward the attractor with no cycle) vs **washed out** (coupling + damping erase any large-scale rhythm). | the verdict this probe exists to produce. |

**Honest gate.** The season-system is *worth building* only if T4 returns a
**real season** (or at least a drift with a real amplitude the design can label
thin/harvest). Both other outcomes are legitimate and informative: a **drift**
means the tide collapses to a one-way "healing toward organized" arc (a game-time
recovery, not a cycle — playable, but not a "season"); a **washed-out** means the
large-scale rhythm does not survive the box, and the tide must move to the
*per-region* scale (each Qi-bath/ridge has its own local relaxation, read locally)
rather than a window-global tempo. The probe's verdict is recorded against this
pre-registered decision before any gameplay follows. **[probe]**

**Consumers of this probe's verdict (two-way, added on reconciliation):** three
docs gate their whole design on this §5a measurement, and each cites it — this
note reads them back:
- [`the-cold.md`](./the-cold.md) — the long-thin **climate** is this probe held
  across the decade: its §5(b)/§7 gates the cold as a real season on T4 ("does
  the regional `q` oscillate?" — if not, the cold collapses to a drift-reading),
  and its open-Q2 rides T4's verdict.
- [`the-election.md`](./the-election.md) — the forward-read's **momentum leg** is
  gated on this probe (§2.3: "does the regional `q` oscillate?") before "carrying
  toward harvest or strain" is a *measured* read rather than a designed dial.
- [`the-flood.md`](./the-flood.md) — the **surfeit** climate (the harvest-tide's
  too-much) rides this same probe's real high: its §6(b)/§7 gates the flood on the
  q-accumulation being a real harvest ("if the regional `q` does not accumulate a
  genuine high, there is nothing to overshoot — the flood collapses to a
  drift-reading"), the cold's mirror on the abundance sign.
All three read the one T1–T4 verdict once, each with its own consequence (a
cold's season; an election's momentum; a flood's surfeit); the probe is the
shared ground truth, and its drift-verdict weakens all three honestly, never
forced.

### (b) Cadence / amplitude tuning — what is a "season" in real time

The probe (T3) measures the *physics* period. Turning that into a **gameplay
season length** is a **design dial**, not a physics constant — `T = 2π/[λ(1−q)]`
is a local relaxation period whose numeric value in Minecraft time is a
calibration (`energy-harnessing.md` §7 Q1's unit-scale problem, applied to
tempo). **[design]** The design owns:
- **Season length**: the measured period, then scaled so a full cycle is a
  meaningful-but-not-punishing gameplay beat (order of tens of minutes to an hour
  of play, tentatively — tuned after T2). **[assumption]**
- **Amplitude**: how far the regional `q` swings between harvest and thin. The
  **thin floor must sit above the desert's dissolution threshold** (else every
  trough is a desert) but low enough that thin reads as "wasteful" not "dead."
  This is the same hazard-threshold scaling of `field-hazards.md` §6.2, applied to
  the season's valley.
- **Phase-locking / regional coherence**: whether the whole window breathes in
  phase, or different ridges relax at different local cadences (the T4
  washed-out case). A *regionally-correlated* tide is a clean shared tempo; a
  decoherent one is "each ridge has its own season" — a better-spatial, but
  design-heavier, reading.

### (c) The tide must not trivialize the desert

**A predictable trough is still a hazard.** The seasonality is a *planning aid*,
not a removal (`field-hazards.md` §3.3: a desert that has fully taken a region has
no `q` left to spend on its own correction). The tide gives the player a window
to prevent the desert *before* its worst — but:
- A thin tide is still a time of weak healing, bright waste, low ore, shedding
  organisms, and elevated storm danger. All the harshness of `field-hazards.md`
  holds.
- The tide does not erase the desert's causes (over-reaping, BH draw, sustained
  overdraw). A player who ignores the reader and over-reaps through a thin tide
  still drives a region to a dead window. The season makes neglect *preventable
  with foresight*, never costless.
- **[design] The thin trough must not cross into a scripted desert.** The tide's
  trough is a *designed* low `q` band; whether a region falls all the way into a
  genuine desert remains the player-caused consequence of `field-hazards.md` §3,
  not an automatic seasonal event. The phase lowers the *margin*; the player's
  husbandry decides whether the margin is defended.

### (d) The no-free-energy discipline

The harvest tide is **not free energy.** It is the field's *organized* state —
the same ambient cascade pump (`energy-harnessing.md` §1.7) that is everywhere
and capped. Three guards, all inherited from `energy-harnessing.md` §6
(no conversion yields more than it sinks, `output ≤ φ⁻¹·input` amplitude caps):

1. **A harvest window is not a free-power window.** Machines at harvest run
   near-lossless, but the *reservoirs* they tap are unchanged — a hydraulic mill
   still flattens its own head, a turbine still damps its flow (§2.1/§2.2). The
   tide raises *efficiency*, never the underlying reservoir yield. **You cannot
   store a harvest tide as free energy** — storage is ordered matter (§3), and
   ordering it still costs the charge/time asymmetry.
2. **A thin tide is not a reason to farm the desert.** The auroral collector
   brightens at thin (over `atmosphere-orbits-auroras.md` §3.4) — but it is
   amplitude-capped and net-negative (it taps only the `(1−q)` fraction that
   would be wasted) and *diminished as the player heals the field*. The
   no-free-energy gate of `field-hazards.md` §5.3 that closes hazard-farming
   closes **tide-farming** the same way: a player cannot *cause* a thin trough to
   mine its bright drains, nor *hold* a region in thin to farm wells — the write-
   back caps keep every conversion net-negative.
3. **Husbandry is a cost, not a free win.** Holding a Qi bath through a thin tide
   is a sustained draw (`energy-harnessing.md` §4.4, "a bath is a draw ... brittle
   if it goes down"). Preventing the desert at its trough is anti-corruption —
   net-negative spend. **The tide's gift is *information and timing*, not energy.**

---

## 6. Feasibility verdict

**Phase-1.5 — the probe.** The **probe (T1–T4)** is a measurement on the
already-built living-terrain demo (`chunk-field-quantization.md` §1.2 box,
`field_q` already published). It reads only the published channels and costs
nothing new — exactly the ecology's silhouette-probe discipline. This is
Phase-1.5 because it needs the *coupled* living-terrain box (terrain + damping),
not the bare Phase-1 field.

**The pacing lens is design over existing channels once the period is measured.**
When T4 returns a real season (or a drift), the *season-system* is a **lens** — it
changes no constant, adds no channel, injects no term. Every system in §2 already
reads `q`/`ε²`/`ρ`/`∇(g·Φ)`; the tide only *paces their operations off* a derived
regional-`q` trend. The observability (§4) reuses the reader, the aurora
rendering, the `(1−q)` glow, and the sonification bank that `energy-harnessing.md`,
`atmosphere-orbits-auroras.md`, and `field-music.md` already specify. **Nothing
new is built to have a season.**

**The season-system composes every existing doc onto the shared tempo.** Because
it is a lens, it does not add a subsystem; it *reads* the corpus's systems in a
temporal frame. The player-facing mechanics are all compilations of existing
acts — husbandry with a clock (`field-hazards.md` §3 + `energy-harnessing.md`
§4.4), harvest-tripping (`material-regimes.md` §3 ore + `coherence-magic.md` §3.1
channeling + `custom-blocks.md` §3 authoring), voyage-timing (`world-seams.md`
§2.3), and residue-exposure archaeology (`field-archaeology.md` §6b).

**Binding risks, in order:** **(a)** the probe — does the regional `q` oscillate
at all under terrain coupling + damping, or wash out (the season collapses to a
drift / per-region reading)? **(b)** the cadence/amplitude tuning (§5b) — what a
"season" is in real time, and keeping the thin floor above the desert's
dissolution threshold; **(c)** the no-free-energy gate held against tide-farming
(§5d). None is an architectural contradiction of the async, dual-world, or
regime-collapse architecture — the tide is the least invasive design in the corpus
because it *adds no physics*; it only reads a trend and paces operations against
it.
**[probe precedent — two-way with the storm]** [`weather-not-storm.md`](./weather-not-storm.md)
inherits this §5a probe discipline for its own provenance probe: its stopping-window
open-Q1 is set "following this doc's T1–T4 precedent," and its §6e tide-correlation
check books a thin-trough storm vs a harvest storm against *this* doc's tide
(season, not cause). This §5a probe and weather-not-storm's probe are the two
pre-registered field-measurements over the same coupled living-terrain box; each
doc cites the other's discipline and reads its verdict once.

> **The honest statement that makes this doc load-bearing: the whole field world
> already has one large-scale tempo — the attractor's relaxation cadence, the
> theory's mixing clock `T = 2π/[λ(1−q)]`. The tide is that clock given a face: it
> makes *when* matter as much as *where*, so the player does not fight weather but
> reads and plans around a season. Nothing new is added to the field; the field
> already lives it — the design gives that living a rhythm the player can feel in
> the sky, the glow, and the hum, and can act on with foresight instead of
> reaction.**

---

## Open questions

1. **Probe verdict calibration (T4).** What counts as "a real season" — how many
   periods, over what amplitude, at what damping before the regional-`q`
   oscillation is a cycle rather than a transient? Pre-registered as the probe's
   decision rule, colored in from the run. (Ecology's §1.4 P4 is the model.)
2. **Season length in real time.** The measured period, then scaled to a gameplay
   beat. Is a season order-of-tens-of-minutes, or does the box's relaxation make
   it hours (too slow to *feel* as a cycle) or minutes (so fast it's weather)?
   **[design]** — set after T2, not implied by the formula.
3. **Thin-trough vs desert threshold.** The seasonal valley must sit above
   `field-hazards.md` §6.2's hazard threshold for "a living plain" — the season
   reads as *wasteful*, not *deserted*. The two thresholds must be set together,
   and a season trough must never *automatically* cross into a desert (§5c).
4. **Regional vs local tempo.** If T4 returns "washed out" window-global, does
   the tide survive as a *per-Qi-bath / per-ridge* local relaxation (each
   organized region breathes at its own cadence, sensed locally)? That is the
   honest fallback, but it is a different, more spatial design than a shared
   tempo.
5. **The tide's coupling to the mixel-scale q-gate.** Since the engine kernel is
   q-free (`qi-as-time-clock.md` §2.1), the tide's *relaxation* reading assumes
   the theory-solver's `(1−q)` gate governs the living-terrain field. Does the
   coupled box actually relax at `λ_mix = λ(1−q)`, or at the engine's q-free
   `ω₀²` rate? The probe that measures the period answers this too — a period
   *matching* the q-gate model would support closing the engine gap; a q-free
   period would push the tide to a presentation-only reading.

---

## Cross-references

- [`energy-harnessing.md`](./energy-harnessing.md) — the Qi bath (§4.4) as the tide's cheap-zone anchor; the `(1−q)` glow (§2) as the waste read and legibility floor; the ambient cascade pump (§1.7) as the harvest drift; the constraint economy and §6 no-free-energy cap (§5d); the charge/scar asymmetry (§3) that thin tide worsens.
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — biome⇔regime (§4) the tide shifts; the recognition rule (§6b); the biosphere drifting with the field (§4.2); the silhouette probe (§1.4) as the model for the tide probe (§5a).
- [`field-hazards.md`](./field-hazards.md) — the desert (§3) as the tide's trough made regional; the storm's `ε²` front (§2) as the short event the phase frames; the hazard-threshold scaling (§6.2) the season's thin floor must respect.
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — weather = envelope waves (§1.3); the tide as the long-period envelope mode; the aurora (§3) as the tide's atmospheric legibility and the auroral-collector's thin-tide yield.
- [`material-regimes.md`](./material-regimes.md) — ore precipitation = `q` accumulation (§3); the `(1−q)` floor near-losslessness (§3); hardness = rung (§4) and its trough-worsened asymmetry.
- [`coherence-magic.md`](./coherence-magic.md) — the reader (Sense, §2) as the tide's primary observability channel; resonance with the field (§3.1) that makes channeling a harvest act; coherence budget / vent (§1.2) that thin tide degrades.
- [`field-music.md`](./field-music.md) — the ambience breathing with the tide (§1, §2.3); the efficiency hum as the audible twin of the `(1−q)` glow.
- [`field-archaeology.md`](./field-archaeology.md) — residue stability gated on local `q` (§6b); the tide's trough as the residue-exposure window; the dig's regional-`q` cost (§5.2).
- [`custom-blocks.md`](./custom-blocks.md) — realizability is contextual (§2, §7 Q2), so the tide shifts which tuples are realizable at a given phase — authoring is a harvest act (§2/§3).
- [`world-seams.md`](./world-seams.md) — the temporal twin of the spatial horizon; the long dark's voyage as a coherence budget that can be timed to the home window's harvest (§2.3).
- [`the-drift-road.md`](./the-drift-road.md) — **the tide's verdict designed as
  gameplay.** §2 there reads §5b open-Q1 this doc's drift-year and §4 open-Q4's
  per-region fallback as designed consequences — whichever of the three T1–T4 verdicts
  (§5a this doc) returns, every branch has a designed, readable reading, never an
  un-designed one. Reverse pointer: the drift-road is the tide probe's open-Q harvest
  — the verdict this doc pre-registers, designed on every branch.
- [`the-loan.md`](./the-loan.md) — **the beat.** §2.2 there reads §2 this doc's tide
  as the year's pulse **and §5a the harvest/thin regime** — the loan's term is due
  "next harvest," priced by the tide's q the same way a crossing is. Reverse pointer:
  the loan's repayment rides the tide's beat.
- [`the-season-change.md`](./the-season-change.md) — **the crossing.** §2 there reads §2
  this doc's harvest/thin states (the two feet the turn crosses between), §5a the probe
  (the turn's gate), §1.2 the honest drift reading, §5d the tide discipline. Reverse
  pointer: the season-change is the tide's crossing made a read.
- [`the-desert.md`](./the-desert.md) — **the sustained thin.** §2 there reads the
  harvest/thin states; §5a the probe; §5b the thin floor. Reverse pointer: the desert
  is the tide at its thinnest, sustained.
- [`the-estuary.md`](./the-estuary.md) — **the tide's pulse at the mouth.** §2 there
  reads the harvest/thin states; §5a the tide's pulse probe (T1–T4); §5d the no-mint.
  Reverse pointer: the estuary is the tide's pulse read at a water's mouth.
- [`the-delta.md`](./the-delta.md) — **the spread at the mouth.** §2 the harvest/thin states; §5a the pulse probe. Reverse pointer: the delta is the tide’s pulse read where the river spreads.
- [`the-eclipse.md`](./the-eclipse.md) — **the beat’s date.** §2 the harvest/thin states (the eclipse is not the thin); §5a the probe (the measured period that sets the date’s beat); §5d the no-free-energy discipline. Reverse pointer: the eclipse is not the tide’s thin — it is the calendar’s named beat.
- [`the-lightning.md`](./the-lightning.md) — **the storm’s season.** §2 the storm-frequency-at-thin. Reverse pointer: the lightning’s frequency rides the tide’s storm-at-thin row.
- [`the-generations.md`](./the-generations.md) — **the long season.** §1 the tide as a pacing lens. Reverse pointer: generations ride the tide’s long seasons.
- [`the-seacraft.md`](./the-seacraft.md) — **the ridden season.** §1 the tide as a pacing lens. Reverse pointer: the seacraft rides the tide’s seasons.
- [`the-whirlpool.md`](./the-whirlpool.md) — **the spin’s season.** §1 the tide as a pacing lens. Reverse pointer: the whirlpool’s spins ride the tide’s seasons.
- [`world-difficulty.md`](./world-difficulty.md) — **the scaled season.** §1 the tide as a pacing lens; §1.2 the harvest/thin states; §2 the storm-frequency-at-thin row; §5a the T1–T4 probe; §5d the no-free-energy discipline. Reverse pointer: world-difficulty scales the tide’s density, never its cause — the season’s frequency the dial multiplies.
- [`the-comet.md`](./the-comet.md) — **the long tempo.** §1 the tide as the large-scale regional q oscillation; §2 the regime table; §5a the probe. Reverse pointer: the comet rides the same long time as the tide — the sky’s visitor on the window’s own breath.
- [`the-anchor.md`](./the-anchor.md) — **the held station.** §1 the tide as the large-scale regional q oscillation; §2 the regime table; §5a the probe. Reverse pointer: the anchor holds against the tide’s pull and the current’s flow — the held station against the window’s own long drift.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers (φ, ξ = φ⁶ ≈ 17.94, the ≈ 6 MiB publish, the 64³ grid, `q ≈ 0.947` attractor, `q ~ 1e-3…1e-1` noise); cited, not re-derived.
- Theory (read-only): `CassiTheory/speculations/qi-as-time-clock.md` (the mixing clock `T = 2π/[λ(1−q)]`; the `(1−q)` openness gate; flow-vs-openness interpretation), `CassiTheory/speculations/qi-time-ladder-derivation.md` (exponent 0 for the mixing clock; the winding bound `|δn| ≤ 0.162`; the honest "designed schedule realizes, not derives" verdict), `CassiTheory/foundations/spiral-dynamics.md` §2.1 (the mixing clock and uniform per-rung rate).
