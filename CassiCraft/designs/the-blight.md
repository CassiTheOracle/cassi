# The Blight: The Field's Life Turned Against the Field — An Ecology-Level Hazard with a Lifecycle

**Question under design:** the corpus's danger layer (`field-hazards.md`) designs
every hazard as a **field-regime event** — the storm's `ε²` front, the desert's
`q` collapse, the BH's accretion, the Coda's scarcity-feeding, the cold's
long-thin, the flood's long-thick. Each is a *regime state the field falls into*.
None is **ecological** — none is a danger that *lives, spreads, and is made of
the field's own life*. This document designs **the Blight**: the over-bloom of
[`field-emergent-ecology.md`](./field-emergent-ecology.md) §4 **made a danger** —
a region's organisms pushed past their band by a **sustained wrong-band** (a
`q`-floor or `ε²`-bias that persists long enough) **corrupt**: their growth
stays, their feeding turns from the field's own coherence to the *region's* own
coherence, and they become a **living drain the field cannot shed** — an
ecology-level hazard that *spreads* (the corrupted organisms propagate the
wrong-band), *draws* (a blight is a standing drain — the region's `q` falls
around it, the harvest dies), and *corrupts* (a healthy organism that spends too
long in a blight's band turns). **The Blight is the field's life turned against
the field** — the corpus's first hazard with a **lifecycle** (seeding, growing,
spreading, dying) instead of an onset.

**The honest design question this doc answers:** whether a blight can be
*healed* (the band restored, the corrupted organisms shed back into the field)
or only *cleared* (the region burned/purged — a hard, scarring act). The design
commits: **heal is the corpus's preferred act** (conservation = anti-corruption,
`field-emergent-ecology.md` §5.3), **clear is the honest emergency** (the
healer's toll too high, the blight too wide), and **the scar of a clear is the
blight's monument**.

Companion to (the docs the blight reads — all relative paths):
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — **THE over-bloom.**
  §4 the shallow species that do not shed; the q-accumulation's bloom; §4.1 the
  biosphere drifts with the field, selection-without-a-selector; §4.2 regime
  ⇔ biome; §5.2 the `(1−q)` glow as the health-meter; **§5.3 conservation =
  anti-corruption (the blight's healing frame)**; §6b the recognition rule
  (coherence band `[q_low, q_high]` + `ε²` ceiling + size, held for `T_org` —
  the corrupted organism's *failed* gate).
- [`the-flood.md`](./the-flood.md) — **THE wrong-band habitat.** §2 the surfeit
  (regional `q` held above the enriching band); the over-bloom (the shallow
  species that do not shed); **§3 the shedding through the `(1−q)` waste — the
  self-limit a blight's own feeding must, honestly, obey; §4 the husbandry
  (anti-bloom as the blight's prevention)**; §6(b) the gates the blight
  inherits.
- [`farm-that-feeds.md`](./farm-that-feeds.md) — **THE crop band.** §2 a crop
  precipitates in a band and holds it (the blight overshoots the band — the
  farmer's warning, §2.1); §6a the cultivated distinction — **a farm reads
  *maintained*, a blight's organism reads *maintained-then-corrupt*** (the
  Life-Signal's maintenance axis).
- [`energy-harnessing.md`](./energy-harnessing.md) — **THE drain.** §2 the
  `(1−q)` waste law `E_waste = (1−q)·E_throughput` (what a corrupted organism's
  wrong feeding wastes through — and what its own self-limit obeys); **§6 the
  no-free-energy cap (`output ≤ φ⁻¹·input` — a blight is a drain, never a
  harvest)**.
- [`life-signal.md`](./life-signal.md) — **THE maintenance axis.** §3 a
  maintained lock *pulses*; §3.1 the classes (a blighted organism reads as
  **maintained-then-corrupt** — the pulse that keeps going after its feeding has
  turned against the region).
- [`the-healer.md`](./the-healer.md) — **THE heal.** §2 the long bind (the band
  restored, the corrupted organisms shed back into the field — the heal applied
  at ecology scale); the healer's toll (the heal is spent, never a mint).
- [`field-hazards.md`](./field-hazards.md) — **THE danger layer's house style.**
  §1 hazards are the field's own extremes (the blight joins as the first
  *ecological* one); §5.1 readable-before-it-arrives; §5.3 the no-free-energy
  gate; §6.2 the player-agency gate (a hazard preventable by maintenance vs a
  scripted trigger).
- [`weather-not-storm.md`](./weather-not-storm.md) — **THE provenance frame.**
  The blight's source read: is the wrong-band the field's own (a flood's
  over-bloom, a place's season) or the settlement's own (an over-provisioned
  bath, an over-husbanded plot)? The provenance read separates them, exactly as
  it separates weather from punishment.

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived): the `192³/64³/12³` box, the ≈ 6 MiB
publish, `ξ = φ⁶ ≈ 17.94`, `φ⁻² ≈ 0.382` (the merge gate `q_sel > φ⁻²`), `τ_c =
0.5` (condensation threshold), the `π/ρ` clamp `0.72`, `ω₀² = 20.0`, `dt = 0.05`,
the ≈ 1–6 ms/tick server sample budget, per-entity ≈ 40 ns river-law steering,
the ≈ 2,000-entity cap, the `q ≈ 0.947` attractor, the `q ~ 1e-3…1e-1` noise
floor. Anything that extends engine terms to a *corrupted* organism is flagged
**[design]**; anything that stands on a question this design cannot yet answer
is flagged **[probe]**. **The honest boundary is drawn in §5 and never blurred:
the organisms' growth/shed and the q-bands are engine-real / [design]-landed
(their source docs' line); the wrong-band persistence is the flood's/the tide's
[design]; the corruption threshold, the lifecycle, and the heal/clear fork are
this doc's [design] over them, probe-calibrated.**

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| The Blight = ? | **The over-bloom made a danger** — a region's organisms pushed past their band by a sustained wrong-band corrupt: their growth stays, their feeding turns to the region's own coherence, and they become a living drain the field cannot shed. **The field's life turned against the field**; the corpus's first *ecological* hazard — with a lifecycle instead of an onset. |
| What corrupts | the **sustained wrong-band** — a `q`-floor or `ε²`-bias persisting past a threshold (the flood's surfeit as the habitat); a healthy organism that spends too long in that band turns (`field-emergent-ecology.md` §4's over-bloom made pathological). |
| What corruption IS | the organism's **maintained growth stopping its shed** — the run stops dying back into the field and starts feeding *on it*; the corrupted organism as a **living drain** (the region's `q` falls around it — the harvest dies, the band widens). |
| The corruption threshold | **how long past band before an organism turns** — this doc's **[design]**, probe-calibrated (§2). |
| The lifecycle | **seeding** (the wrong-band persists, the first organism turns) → **growing** (the corrupted propagate the wrong-band — the blight spreads by making its own habitat) → **drawing** (the standing drain — the region's `q` falls, the harvest dies) → **dying** (the honest end: the blight's own `(1−q)` waste eventually chokes it — it sheds back *if nothing feeds it*; a fed blight persists). |
| The honest danger | a blight is **sustainable** — it can live off the region it drains; **the first hazard that does not need an external source**. |
| The heal vs the clear | **healing** (the band restored — the long bind at ecology scale; the healer's toll `the-healer.md` §2; the corrupted organisms shed back) = the corpus's preferred act; **clearing** (the region purged — a hard, scarring act; the blight burned out, the region's own `q` spent, a scar left — the wound-class consequence) = the honest emergency. |
| Feasibility | **MEDIUM-LATE with a Phase-1-legible framing — the danger layer's first living hazard.** State both (§7). |

---

## 1. The Blight, stated once

> **The Blight is the over-bloom made a danger — the field's life turned against
> the field.** It is what a region's ecology becomes when a **sustained
> wrong-band** (a `q`-floor or an `ε²`-bias persisting past a threshold) pushes its
> organisms past their band: their **growth stays** (the run the field was holding
> does not die back), their **feeding turns** from the field's own ordering to the
> *region's* own coherence, and they become a **living drain the field cannot
> shed** — a standing `q`-sink that the region's own ecology feeds, spreads, and
> cannot clear on its own. It is the corpus's first *ecological* hazard (not a
> regime event) and its first hazard with a **lifecycle** (seeding, growing,
> spreading, dying) instead of an onset.

The corpus's danger layer designs *events* — each a regime the field falls into,
with a front and a verdict ([`field-hazards.md`](./field-hazards.md) §1). The
storm is the PDE's wave runaway; the desert is a `q` collapse; the BH is the
merge lineage's terminal branch. Even the seasons — the cold, the flood — are the
field's *state* held over the long horizon. None of them **lives**. The blight
is the first one that does because its fuel is the field's own organisms: it is
not a regime that happens to a region; it is a region's *life* that has been
flipped into a drain.

**Two load-bearing anchors ground this — both in the sources.**

**First, the over-bloom is already designed.** [`field-emergent-ecology.md`](./field-emergent-ecology.md)
§4 designs the biosphere that drifts with the field, and names the **shallow
species that do not shed**: the single-scale morphs that would normally de-cohere
at thin are *held* at a surfeit, so the recognition gate's coherence band is met
*everywhere* and creatures precipitate too readily and hold too long — **the
q-accumulation's bloom**. [`the-flood.md`](./the-flood.md) §2 names the same
over-bloom as the surfeit's ecology ("the shallow species do not shed — they
over-bloom and crowd"). **The blight is that over-bloom made pathological**: what
the flood's surplus merely *crowds*, a wrong-band that *persists* **corrupts** —
the bloom's organisms stop shedding back into the field and start feeding on it.

**Second, the wrong-band is the flood's habitat.** [`the-flood.md`](./the-flood.md)
§2 is the `q`-surfeit — regional `q` held above the enriching band over a long
season, the over-bloom, the deafening resonance. A blight needs *that* wrong-band
to *persist* — a `q`-floor that stays, or an `ε²`-bias that does not clear — and
when it persists *long enough past the organisms' band*, the over-bloom crosses
from crowd to corruption. **The flood is the wrong-band's season; the blight is
its aftereffect — what the region's own life does when the wrong-band outlives
the season.**

**The honest scope of the claim:** the **organisms' growth/shed and the `q`-bands
are engine-real / [design]-landed** (exactly where their source docs draw the
line — `field-emergent-ecology.md` §6b's recognition band, §2.2's growth-as-a-run,
§5.2's `(1−q)`-glow health-meter); **the wrong-band persistence is the flood's /
the tide's [design]** ([`the-flood.md`](./the-flood.md) §5 — the surfeit, the
season); **the corruption threshold, the lifecycle, and the heal/clear fork are
this doc's [design] over them**, probe-calibrated. That is the line §5 draws and
never blurs.

---

## 2. The corruption mechanics

### 2.1 What corrupts — the sustained wrong-band

Corruption does not "happen" to a healthy region; it is a *wrong-band that
persists past a threshold*. The field has two wrong-band directions, both already
in the corpus:

| Wrong-band | What it is, in field terms | Source grounding |
|---|---|---|
| **The `q`-floor / surfeit** | regional `q` held *above* the enriching band — the flood's habitat; the field too organized to shed its own shallow species | [`the-flood.md`](./the-flood.md) §2 (the surfeit); §3 (the harvest-tide overshoot); [`tide-of-the-attractor.md`](./tide-of-the-attractor.md) §5a (the accumulation the flood over-runs) |
| **The `ε²`-bias** | a persistent elevated decoherence that *widens* the band — the organisms' recognition floor is met but the drain does not clear, so they hold against a field that is actively de-ordering beneath them | [`field-hazards.md`](./field-hazards.md) §2 (the decoherence state), §3 (the `q` collapse); [`field-emergent-ecology.md`](./field-emergent-ecology.md) §6b (the `ε²` ceiling below which an organism must hold) |

**The flood's surfeit as the blight's habitat.** The load-bearing wrong-band is
the flood's: a `q`-floor that *persists* past the enriching band
([`the-flood.md`](./the-flood.md) §2). A single high-`q` harvest peak is bounty;
a *season* of held-over-band `q` is a flood; **a wrong-band that outlives the
season, or that a settlement's husbandry lets stand, is the ground a blight seeds
in.** The flood itself is self-limiting (§3 — the surfeit wastes upward and
recedes); **the blight is what happens when the wrong-band is *fed* — by a
sustained `q`-floor the region's own ecology now maintains, or by a settlement's
over-provisioned bath that never depletes** (`energy-harnessing.md` §4.4 — a bath
"that never recedes", which the flood doc already names as the oversaturated
extreme). **[design] The persistence threshold — how long a wrong-band must hold
before it starts corrupting, not merely crowding — is this doc's dial, probe-
calibrated against the tide's measured accumulation.**

### 2.2 What corruption IS — the maintained run stops dying back

The corruption event is the point where a kept-over-bloom organism's biology
inverts. This is grounded in exactly what the sources already land:

> **Corruption is the organism's maintained growth stopping its shed — the run
> the field was holding stops dying back into the field and starts feeding on
> it.**

[`field-emergent-ecology.md`](./field-emergent-ecology.md) §2.2 designs life as a
**run the field holds** — a configuration the field actively maintains, that
*dies/dissolves* when the `ε²` drain outruns the φ-lock and **sheds coherence
back to the field** (a scarless death because the body *was* field). §4.1 names
the shallow species that *do not shed* at a surfeit — they over-crowd. **The
blight makes that pathological**: the organism's *maintained* growth — the thing
that, running normally, returns to the field on death (§2.2's dissolve) — stops
dying *back into* the field and starts feeding *on* it.

Concretely, the inversion on the engine's real quantities:
- **Normally**: a maintained run holds `q` against `ε²`, feeds on local
  coherence, and dissolves back when the drain outruns the lock
  ([`field-emergent-ecology.md`](./field-emergent-ecology.md) §2.2). Its
  `(1−q)` glow pulses at the maintainer's cadence
  ([`life-signal.md`](./life-signal.md) §3.1).
- **Corrupted**: the run **does not shed** — its growth stays (§4's over-bloom
  held past its point), and its feeding **turns from the field's own ordering to
  the region's own coherence**. What it withdraws is no longer the ambient
  organizing drift; it is the *region's already-organized `q`* — so each corrupted
  organism is a **living `q`-drain** at its own locus.

**The corrupted organism as a living drain.** A normal organism's feeding
withdraws local coherence and, on death, returns it (conservation of the field's
organization — §5.3's conservation = anti-corruption is precisely this return kept
healthy). A corrupted organism *withdraws* but does not *return* — it holds its
growth against the region's `q`, feeding on the region's own organization. The
consequences are exactly the sources' disasters, now ecology-made:

| The drain's effect | What it does to the region | Grounding |
|---|---|---|
| **The region's `q` falls around it** | each corrupted organism is a standing `q`-sink; the local band the region's *healthy* organisms, crops, and matter need is drained beneath them | [`the-flood.md`](./the-flood.md) §3 (a drain — "the region's `q` falls"); [`field-emergent-ecology.md`](./field-emergent-ecology.md) §4.2 (a low-`q` regime is ecological failure); [`energy-harnessing.md`](./energy-harnessing.md) §4.4 (a drain starves what it sits in) |
| **The harvest dies** | crops precipitate only where `q` sits in their band (`farm-that-feeds.md` §2.1); a blight's falling `q` pulls the bed under the crop band, so the harvest dissolves | [`farm-that-feeds.md`](./farm-that-feeds.md) §2.1/§4 (a crop's run is the bed's band); [`field-hazards.md`](./field-hazards.md) §3 (drought kills the biosphere's band) |
| **The band widens** | as the corrupted drain lowers the region's `q`, the healthy organisms that *would* have shed now find the field de-ordering beneath them — their recognition ceiling (`ε²`) and band floor are met in a region that can no longer hold them — so more of them turn | [`field-emergent-ecology.md`](./field-emergent-ecology.md) §4.2 (regime ⇔ biome — a low-`q` region precipitates fewer/different organisms); the corruption threshold's self-widening, [design] §5 |

**The corruption threshold — how long past band before an organism
turns.** The exact duration an organism must spend in a blight's wrong-band before
its run inverts (growth-stays + feeding-turns) is **this doc's [design] dial,
probe-calibrated** — the same threshold-judgment tier as the ecology's recognition
rule ([`field-emergent-ecology.md`](./field-emergent-ecology.md) §6b) and the
Life-Signal's class boundaries ([`life-signal.md`](./life-signal.md) §3/§6a). It is
deliberately *slower than the organism's own shed cycle* (so a normal thin-tide
organism, which sheds and dissolves, never corrupts) and *shorter than the
season* (so a genuine flood, which sheds at its end, does not seed a blight unless
something *feeds* the wrong-band). The dial is not a physics constant; it is the
designed "line" between the flood's self-limiting bloom and the blight's lasting
drain.

**The water-borne habitat (reverse pointer, two-way).** This §2's wrong-band has a
liquid-regime face: [`the-sea.md`](./the-sea.md) §4 reads **a poisoned sea as the
blight's water-borne habitat** — a `q`-floor or `ε²`-bias held in the liquid regime
is exactly this §2's wrong-band, made to live in the water and spread by the
river's own flow ("a region's life turned against the field, spread by the water's
own flow"; `the-sea.md` §4 — it inherits this §2's corruption and §6b's gates at
water scale, and its §7 open-Q4's water-borne flow-vector is this doc's corruption
threshold applied to the filament). The blight is the sea's poisoned life; the two
docs now cite each other as read-and-answered.

---

## 3. The blight's lifecycle

A blight is not an event that arrives; it is the corpus's first hazard with a
**lifecycle** — it is *seeded*, it *grows*, it *spreads*, it *draws*, and it
*dies* — and each stage is a designed reading over the engine-real channels the
corpus already publishes.

| Lifecycle stage | What the field does | The designed reading ([design]) | Deterministic gate |
|---|---|---|---|
| **Seeding** | a wrong-band (a `q`-floor or `ε²`-bias) *persists* past the threshold (§2.1); the first over-bloom organism's run stops shedding and turns (§2.2) | the first corrupted organism — its `(1−q)` glow shifts from the healthy *bad-bright* of the over-bloom (`the-flood.md` §3, the wrong-bright shedding did not get captured) to the *drain's* signature: a maintained pulse that is now *drawing* the region's `q` down around it | same region, same field state → same place and moment corruption begins |
| **Growing** | the corrupted organisms **propagate the wrong-band** — each drain lowers the local `q`, widening the band into *its own* habitat, so the healthy organisms in the widened band turn in turn | the blight **spreads by making its own habitat**: it is not a front that arrives (no `c_s`-traveling `ε²` edge, no monotone `q` collapse) but a *growing set of living drains* that each prepares the ground for the next | same field state → the blight's growth curve (how many corrupted, how fast) is deterministic |
| **Drawing** | the standing drain is at full weight — the region's `q` falls around the corrupted mass, the harvest dies, the healthy band is gone | the blight's peak: a region where the field's own life has become a net `q`-sink, and every instrument reads the drain (the reader's `q` falls, the crop glow dies, the wrong-bright drain persists) | same field state → the blight's extent (which cells, how deep the `q` draw) is deterministic |
| **Dying** | **the honest end**: the blight's own `(1−q)` waste (each corrupted organism wastes `(1−q)·E_throughput` as it feeds, [`energy-harnessing.md`](./energy-harnessing.md) §2) eventually *chokes* it — a fed-blight's run cannot sustain the increasing waste its own feeding generates, so the corrupted organisms shed back into the field, **if nothing feeds it** | the recede: the wrong-bright drains dim, the corrupted runs dissolve back, the band restores — the same "the surfeit wastes upward" self-limit of [`the-flood.md`](./the-flood.md) §3, inherited by the blight's organisms | same field state → when and how hard the blight sheds back is deterministic |

### 3.1 The honest danger: a blight is *sustainable*

The load-bearing twist that makes a blight a *Cassi* hazard, and the sharpest
statement in this doc:

> **A blight is sustainable — it can live off the region it drains, and it is
> the first hazard that does not need an external source.**

Every other hazard the corpus designs needs a source. The storm's `ε²` injection
has a provenance ([`weather-not-storm.md`](./weather-not-storm.md) — weather vs
an aimed event); the desert is *caused* — over-reaping, an over-provisioned BH,
sustained overdraw ([`field-hazards.md`](./field-hazards.md) §3.2); the BH needs
its accretion; the Coda needs a channeling trail. **A blight's source is its own
drain.** A blight that seeds once (a flood's over-bloom that a settlement let
stand, an over-provisioned bath) can then run on the region's *own* `q` — the
corrupted organisms feed on the very coherence their feeding drains, and as long
as **something** keeps the wrong-band fed (an uncorrected `q`-floor, an unhealed
`ε²`-bias, a settlement that keeps the over-provisioned bath live) the blight
persists and spreads. The honest reading of "dying" is therefore carefully the
one the flood doc draws: **the blight sheds back *if nothing feeds it* — a fed
blight persists.** The lifecycle's self-limit (the `(1−q)` waste choking a
starved blight) is real ([`energy-harnessing.md`](./energy-harnessing.md) §2) but
it only fires when the wrong-band is removed; a blight whose habitat is maintained
is a standing, self-sustaining drain. **This is why a blight cannot simply be
"waited out" the way a flood's surge is — the flood recedes on its own; a blight
recedes only when the field is no longer feeding it.**

---

## 4. The heal vs the clear

The blight's honest fork — can a region's own life be *restored*, or must it be
*purged* — is the design's question, and the corpus's own systems supply both
answers.

### 4.1 Healing — the long bind applied to a region

> **Healing a blight is restoring the band — the long bind ([`the-healer.md`](./the-healer.md)
> §2) applied at ecology scale: the wrong-band's `q` is pushed back under the
> organisms' band, the corrupted organisms' runs are *shed* (not killed — their
> maintained growth is let die back into the field), and the region returns to
> the enriching band. It is slow, it is costed, and the healer's toll is real.**

The healing frame **is** the corpus's preferred act, and it is grounded in
`field-emergent-ecology.md` §5.3: **conservation = anti-corruption**. The doc's
own words — a player who *suppresses decoherence in a region keeps its biome
alive: the organisms don't die, the coherence doesn't bleed out, the species'
attractor basin stays populated* — is precisely what healing a blight means,
inverted at the failure: the corrupted drains must be *shed back into the field*,
not fed, and the region's `q` must be held back up so the healthy basin returns.
The heal rides four landed pieces:

| The heal's piece | What it is | Grounded in |
|---|---|---|
| **The long bind at ecology scale** | the healer's toll-model applied to a *region* — holding the region's torn `q` together while the attractor re-tensions and the band re-locks | [`the-healer.md`](./the-healer.md) §2 (the bind is a re-lock hold; §2.1 "holding the torn edges together while the attractor re-tensions") |
| **The corrupted organisms shed** | the corrupted runs' maintained growth is *allowed to die back* — the anti-bloom thinning of [`the-flood.md`](./the-flood.md) §4.2 at the ecological scale, letting the drain's mass dissolve into the field instead of feeding it | [`the-flood.md`](./the-flood.md) §4.2 (thinning the bloom); [`field-emergent-ecology.md`](./field-emergent-ecology.md) §2.2 (death = dissolve back to field) |
| **The band restored** | anti-corruption spent to hold the `q` up / `ε²` down under the organisms' band, so healthy organisms no longer turn | [`energy-harnessing.md`](./energy-harnessing.md) §5.4 (anti-corruption holds ground); `field-emergent-ecology.md` §5.3 (conservation = anti-corruption) |
| **The healer's toll, real** | each region-wide bind leaves the healer's carried `ε²` rising, their read dimming toward the drain's color, needing the Still Room's patient time | [`the-healer.md`](./the-healer.md) §3.1 (the risen Burden, the dimmed read, the Still-Room clearing) |

**The heal is spent, never a mint.** [`energy-harnessing.md`](./energy-harnessing.md)
§6 is inherited unchanged: healing a blight is a **net-negative hold** — you pay
fed coherence to push the `q` back under the band, the corrupted organisms'
shedding is a *withdrawal of their stored coherence* (a reaper's by-product,
scarring per §2.5), and the healer's toll is carried and cleared only by rest.
There is **no gain from healing a blight** — what you get is a region restored to
the enriching band, which is exactly what the region's own life was before the
blight, never more. The heal's legibility (the toll on the mirror, the restored
band on the reader) is the honest proof the coherence was spent
([`the-healer.md`](./the-healer.md) §5e).

### 4.2 Clearing — the honest emergency

> **Clearing a blight is purging the region — a hard, scarring act: the blight
> burned out, the region's own `q` spent, a scar left. It is a wound-class
> consequence ([`wound-remembered.md`](./wound-remembered.md) — the deliberate break
> that refuses), and it is the honest emergency when healing is not enough.**

Clearing is not a second, cheaper path; it is the **failure and emergency** of
healing. It is chosen when the healer's toll is too high to hold (a blight too
wide, a healer already at the overdraw edge — [`the-healer.md`](./the-healer.md)
§3.2's "when the toll is too high") or the blight is too wide for any bind to
span. Clearing resolves the blight by **removing the field's life that became the
drain** — the corrupted organisms are not shed, they are *burned out*: their
stored coherence released destructively, the region's `q` spent to do it, and a
**scar left behind** — the wound-class consequence
([`wound-remembered.md`](./wound-remembered.md) §1: a scar that refuses; the
`ε²`-well of a region purged clean).

**The clear is scarring, and the scar is the blight's monument.** A cleared blight
leaves a region the field must heal around — the scar reads on the instruments
(the fallen floor, `life-signal.md` §3.1's scar), the basin is emptied, and the
region's return to life is the patient, slow re-bind ([`field-hazards.md`](./field-hazards.md)
§3.3 — a field with no `q` left to spend on its own correction heals only by the
`ω₀²` attractor over game-time). **The honest decision is between "heal: slow,
costed, the toll real, the region restored" and "clear: fast, hard, scarring, the
region gutted"** — and the blight's residue, the scar of the clear, is *its*
monument, the archaeology the region's future reads.

### 4.3 The design's decision

> **Heal is the corpus's preferred act (conservation = anti-corruption,
> [`field-emergent-ecology.md`](./field-emergent-ecology.md) §5.3) — the band
> restored, the corrupted organisms shed back into the field, the toll spent
> under the cap. Clear is the honest emergency (the healer's toll too high, the
> blight too wide) — a hard, scarring act whose scar is the blight's monument.
> A world that could never heal its own life turning would be cruel; a world
> that always could would make the drain weightless. Both are real, and the
> player reads which is which.**

---

## 5. The honest boundary

| Quantity | Status | Basis |
|---|---|---|
| The organisms' **growth/shed** — a maintained run the field holds, dissolving back to the field on death | **engine-real / [design]-landed** — the ecology's real lifecycle, cited | [`field-emergent-ecology.md`](./field-emergent-ecology.md) §2.2; §4 (the over-bloom, the shallow species that don't shed); the `(1−q)` glow as health-meter §5.2 |
| The **`q`-bands** — where regimes/organisms/crops precipitate, the recognition rule `[q_low, q_high]` + `ε²` ceiling + size | **engine-real / [design]-landed** — the precipitation law + the recognition rule, probe-tuned | [`field-emergent-ecology.md`](./field-emergent-ecology.md) §6b; [`farm-that-feeds.md`](./farm-that-feeds.md) §2.1; [`material-regimes.md`](./material-regimes.md) §3 |
| The `(1−q)` **waste law** `E_waste = (1−q)·E_throughput`; the no-free-energy cap `output ≤ φ⁻¹·input` | **engine-real** | [`energy-harnessing.md`](./energy-harnessing.md) §2/§6 |
| The **maintenance axis** (a maintained lock pulses) | **[design]** over engine-real channels | [`life-signal.md`](./life-signal.md) §3 |
| **The wrong-band persistence** — a `q`-floor or `ε²`-bias holding past a threshold | **[design]** — the flood's/the tide's | [`the-flood.md`](./the-flood.md) §2/§5 (the surfeit, the season); [`tide-of-the-attractor.md`](./tide-of-the-attractor.md) §5a (the accumulation) |
| **The corruption threshold** — how long past band before an organism turns | **this doc's [design]**, probe-calibrated | this doc §2.2; the ecology recognition-rule + life-signal threshold family |
| **The lifecycle** — seeding, growing, spreading, drawing, dying; the sustainability (a fed blight persists) | **this doc's [design]** over the above | this doc §3; [`the-flood.md`](./the-flood.md) §3 (the shedding self-limit) |
| **The heal/clear fork** — heal = the long bind at ecology scale + the toll; clear = the region purged, a scar left | **this doc's [design]** over the healer's/energy's/ecology's landed pieces | this doc §4; [`the-healer.md`](./the-healer.md) §2/§3; `field-emergent-ecology.md` §5.3; `wound-remembered.md` §1 |

**The line, stated once and never blurred:** the organisms' growth/shed and the
`q`-bands are **engine-real / [design]-landed** (exactly where their source docs
draw it); **the wrong-band persistence is the flood's/the tide's [design]**; **the
corruption threshold, the lifecycle, and the heal/clear fork are this doc's
[design] over them**, probe-calibrated. No claim here pretends the engine "has a
blight"; the engine publishes the organisms, the bands, and the `(1−q)` waste —
and the blight is the designed reading that turns a *sustained* wrong-band's
over-bloom into a living drain. **Determinism is a hard gate: same region, same
field state → same blight's shape** (§6c).

---

## 6. Honest gates

### (a) The [design]/engine-real line

Drawn in §5 and never blurred. The organisms' growth/shed, the `q`-bands, the
`(1−q)` waste law, and the maintenance axis are the source docs' own landed
quantities; **the wrong-band persistence is the flood's/the tide's [design]**;
**the corruption threshold, the lifecycle, and the heal/clear fork are this doc's
[design]** over them. A reader can always say "this is the engine's real organism
growth/shed / band / waste law" vs. "this is the corpus's designed wrong-band
lens" vs. "this is this doc's corruption-threshold/lifecycle/heal-clear design."

### (b) MEDIUM-LATE, gated on the ecology's over-bloom being real + the band mechanics

The blight as a **full living hazard** — the corruption threshold, the lifecycle,
the heal/clear fork, the drain economy — is **MEDIUM-LATE**, gated in order on:

- **The ecology's over-bloom being real** ([`field-emergent-ecology.md`](./field-emergent-ecology.md)
  §4/§1.4's P4 verdict) — does the field actually hold the shallow, non-shedding
  species at a surfeit to the point of a crowd? The blight corrupts the over-bloom;
  **if there is no over-bloom, there is nothing to corrupt.** P4 returning
  "transient soup" softens the species claim but *not* the drain premise — even
  transient coherence that stops shedding and feeds on the region is corruptible —
  yet the "living, spreading, made of the field's own life" framing is strongest
  with a real over-bloom.
- **The band mechanics (Phase-1.5 regime constants)** — the per-cell `ω₀²`/`ξ`
  and per-material dissipation (`material-regimes.md` §7 Q1/Q3, the Phase-1.5
  gates) that let organisms be *differentiated* from the law (so a corrupted
  organism has a real band to overshoot against). The blight composes the band
  mechanics; they must be real before the corrupted drain reads as distinct.
- **The flood's wrong-band persistence being real** (its §6(b) gates: the tide
  probe's `q`-accumulation + the §6 cap holding at the surfeit) — the blight
  seeds in a *sustained* wrong-band; if the flood's surfeit self-limits and never
  persists (nothing feeds it), a blight can only seed from a settlement's
  *prolonged* wrong-band (the honest fallback, §7).
- **The §6 no-free-energy cap holding for the drain** (§6d) — the blight is a
  drain, never a harvest; before any blight gameplay, the cap must hold (a
  corrupted organism cannot be "farmed" for net gain, exactly as a flood cannot).

**The framing is Phase-1-legible** even before the ecology's live bloom lands. The
**corruption principle** — *a sustained wrong-band turns a maintained run into a
drain* — is **statable now** against the two landed pieces the task names: the
**farm's band** ([`farm-that-feeds.md`](./farm-that-feeds.md) §2.1 — a crop
precipitates in a band and holds it; a blight overshoots the band) and the
**life-signal's maintenance axis** ([`life-signal.md`](./life-signal.md) §3 — a
maintained run pulses; a blight's organism reads as *maintained-then-corrupt*, the
pulse that keeps going after its feeding turned). Both are Phase-1-legible reads
over the existing publish + the existing band + the existing maintenance channel:
**the designed statement — "a region whose wrong-band persists past its
organisms' hold turns its own maintained life into a standing, self-sustaining
drain that heals (slowly, costed) or clears (hard, scarring)" — is pre-registered;
the mechanical corruption threshold and the living hazard are later**, gated on
the ecology's over-bloom and the band mechanics.

### (c) Determinism — a hard gate

The field is deterministic (one PDE; `life-signal.md` §6d, `the-cold.md` §6(c),
`the-flood.md` §6(c)):

> **Same region, same field state → same blight's shape.** The blight's seeding
> location/point, its growth curve, its extent, its drain depth, and its dying
> behavior are a **pure function of the region's real `q`/`ε²`/organism
> trajectory** — no seeded-RNG, no player-relative variance. A settlement that
> faces the same field state faces exactly the same blight, and a player can
> learn to read *which* wrong-band is corrupting and *why*. **This is a hard
> gate: the blight's shape is deterministic — it never spawns, it precipitates.**

### (d) The no-free-energy cap — a blight is a drain, never a harvest

Held without exception (inherited from [`energy-harnessing.md`](./energy-harnessing.md)
§6 and [`field-hazards.md`](./field-hazards.md) §5.3):

> **Nothing is gained from a blight — the field's life turned against the field
> is the corpus's sharpest temptation to mint, and the cap closes it: the heal
> is spent (the toll the honest proof, [`the-healer.md`](./the-healer.md) §2.2),
> the clear scars (the region's own `q` spent, `wound-remembered.md`).** A
> corrupted organism's wrong feeding cannot be tapped for net gain (it wastes
> `(1−q)` and withdraws without returning — a net-negative drain, never a
> reservoir); a blight's "bounty" is exactly the flood's — the richer the
> wrong-band, the more it wastes (`the-flood.md` §3), never the more it gives. A
> player who tries to farm a blight reads the waste and the scar, not a harvest.

### (e) Accessibility — the blight's approach is readable, never hidden-only

Per the instrument-family rule ([`field-instruments.md`](./field-instruments.md)
§2.1) and the flood's legibility rule ([`the-flood.md`](./the-flood.md) §6(e)):

> **The blight's approach is the band's overshoot — the same read the
> instruments already show.** The corrupted organism's `(1−q)` glow shifts from
> the over-bloom's wrong-bright to the *drain's* maintained-but-drawing pulse
> (which the Life-Signal's breathing read names — [`life-signal.md`](./life-signal.md)
> §4.1); the reader's `q` falls around the blight; the crop glow dies (the
> harvest band gone); the region's `q` trend reads like a slow, *living* drain
> rather than a collapsing desert (the drain is maintained, not fallen). A player
> who never uses a "blight" overlay loses nothing — the band's overshoot is the
> same published `q`/`ε²`/`(1−q)` the instruments always show, read over the
> wrong-band's persistence. **The blight is an idiom over real channels, never a
> gated information source — and its provenance** (is the wrong-band the field's
> own, or the settlement's over-provisioned husbandry?) **is readable the
> weather-not-storm way** ([`weather-not-storm.md`](./weather-not-storm.md) §4 —
> the source read), so the world never punishes opaque.

---

## 7. Feasibility verdict

**MEDIUM-LATE as the full living hazard, with a Phase-1-legible framing — the
danger layer's first living hazard. State both.**

- **The full blight — the corruption threshold, the lifecycle, the sustained
  drain, the heal/clear fork — is MEDIUM-LATE.** It gates on the **ecology's
  over-bloom being real** ([`field-emergent-ecology.md`](./field-emergent-ecology.md)
  §4/§1.4's P4); on the **band mechanics (Phase-1.5 regime constants)** that
  differentiate organisms so a corrupted run has a real band to overshoot; on
  the **flood's wrong-band persistence** (its §6(b) gates: the tide's `q`-
  accumulation + the §6 cap at the surfeit); and on the **healer's transfer being
  real** ([`the-healer.md`](./the-healer.md) §5b) for the heal to be a costed,
  non-mint act. It **adds no new physics and no new channel**: it is a designed
  reading over the organisms, the bands, the maintenance axis, and the `(1−q)`
  waste the sources already land. Its honesty is that the blight-as-hazard —
  the corruption threshold, the lifecycle, the sustainability, the heal/clear
  fork — is **[design]** over that landed stack, probe-calibrated.
- **The Phase-1-legible framing — the corruption principle — is statable now.**
  Even before the ecology's live bloom or the band mechanics land, the *designed
  statement* is holdable today against the **farm's band**
  ([`farm-that-feeds.md`](./farm-that-feeds.md) §2.1 — a run precipitates in a
  band and holds it) and the **life-signal's maintenance axis**
  ([`life-signal.md`](./life-signal.md) §3 — a maintained run pulses): **a
  sustained wrong-band turns a maintained run into a standing, self-sustaining
  drain; it heals (the long bind at ecology scale, the toll real) or clears (the
  region purged, a scar left).** That principle is a pure consumer of the publish
  + the maintenance read + the band — the precise Phase-1 pattern the Weatherglass
  and the cold's slice already prove ([`field-instruments.md`](./field-instruments.md)
  §5a; [`the-cold.md`](./the-cold.md) §6(b)). **The danger layer's first *living*
  hazard — the field's own life turned against the field — is the Phase-1 gain;
  the *mechanical* blight (the corruption dial, the drain economy, the heal/clear
  decision) is later, gated as above.**

**Binding risks, in order:** **(a)** the ecology's P4 verdict — if the field never
holds the shallow over-bloom, the "made of the field's own life" framing softens
to "transient corruption" (a weaker but still-honest drain reading, the task's
own honest fallback); **(b)** the flood's wrong-band persistence — if the surfeit
never persists on its own, a blight can only seed from a settlement's *prolonged*
wrong-band (the provenance read, [`weather-not-storm.md`](./weather-not-storm.md),
is then the safety valve — the world never punishes opaque); **(c)** the §6 cap
held for the drain — a corrupted organism must never be farmable for net gain, or
the blight becomes a free-energy bug; **(d)** the heal/clear honesty — the heal
must be costed-real (the toll legible) and the clear must scar, or the fork
collapses to a free reset; **(e)** keeping the [design] line in §5 honest — the
blight never reads as a new engine term or a hidden difficulty meter, only as a
designed reading of the real organisms, bands, maintenance, and waste.

> **The honest statement that makes this doc load-bearing: the corpus's danger
> layer has designed every field-regime extreme — the storm's `ε²` front, the
> desert's `q` collapse, the BH's accretion, the Coda's scarcity, the cold's
> long-thin, the flood's long-thick — but never the *ecological*: the danger
> that lives, spreads, and is made of the field's own life. The Blight is that
> hazard — the over-bloom of [`field-emergent-ecology.md`](./field-emergent-ecology.md)
> §4 made pathological by a **sustained wrong-band** (the flood's surfeit as the
> habitat): a region's organisms pushed past their band **corrupt** — their
> growth stays, their feeding turns to the region's own coherence, and they
> become a **living drain the field cannot shed** that *spreads* (the corrupted
> propagate the wrong-band), *draws* (the region's `q` falls, the harvest dies),
> and *corrupts* (a healthy organism in the blight's band turns). It is the
> field's life turned against the field, the corpus's first hazard with a
> lifecycle instead of an onset — and its honest danger is that it is
> *sustainable*: it can live off the region it drains, the first hazard that
> does not need an external source.** The honest fork is heal vs. clear: healing
> restores the band — the long bind at ecology scale, the healer's toll real, the
> corrupted organisms shed back into the field (conservation = anti-corruption,
> and the corpus's preferred act); clearing purges the region — a hard, scarring
> act whose scar is the blight's monument (the honest emergency when the toll is
> too high or the blight too wide). **Nothing is gained from a blight: the heal
> is spent, the clear scars, and the `(1−q)` waste the blight's own feeding sheds
> is never a reservoir — the no-free-energy cap holds for the field's life turned
> against itself exactly as it holds for the field's extremes. MEDIUM-LATE, with
> the corruption principle statable now against the farm's band and the
> life-signal's maintenance axis; gated on the ecology's over-bloom being real
> and the band mechanics.**

---

## Open questions

1. **The corruption threshold's calibration (§2.2).** Where exactly, on the
   wrong-band's persistence, does a kept-over-bloom organism's run stop shedding
   and start feeding *on* the region — the dial that separates "a flood's
   self-limiting crowd" from "a blight's lasting drain"? A [design]/[probe]
   threshold against the ecology's P4 over-bloom and the band mechanics, tuned so
   a genuine flood (which sheds at its end) does not seed a blight unless
   something *feeds* the wrong-band. **[design]/[probe]**
2. **The sustainability's exact bound (§3.1).** When a blight's own `(1−q)` waste
   outruns what the region's drain can feed — the honest dying gate — is a probe
   measurement on the coupled living-terrain box: does a *fed* blight's waste grow
   monotonically toward a choking point, or can it settle into a steady-state
   drain? The former makes "a fed blight persists" time-bounded; the latter makes
   it indefinite (a stronger, more frightening sustainable hazard). **[design]/[probe]**
3. **The heal's toll at ecology scale (§4.1).** How the healer's individual-class
   toll-scale extends to a region-wide bind (`the-healer.md` §3.1's risen Burden,
   dimmed read, Still-Room clearing) is a designed dial over the transfer rate —
   does a settlement's healer book as steward-with-weight (the restoration is a
   contribution, `shared-ledger.md` §6e) or does a region-wide clear (not heal)
   read as the drain that ends it? Inherits the healer's open-Q1 transfer-rate fork
   unchanged, applied at ecology scale. **[design]/[probe]**
4. **The clear's scar vs. a wound (§4.2).** A cleared blight's scar — does it read
   as the wound-class consequence ([`wound-remembered.md`](./wound-remembered.md) §1
   — a scar that refuses) or as an ordinary, healable scar? The distinction rides
   the scar-lifecycle probe ([`field-hazards.md`](./field-hazards.md) open-Q4 — does
   a broken region re-bind or stay scarred?) and decides whether the clear is an
   honest, scarring trade or a clean reset. **[design]/[probe]** — inherited from
   the wound doc.
5. **The blight's place in the fate (§7).** The blight is the abundance-ecology
   twin of the flood's arc. Does a settlement that *heals* a blight (slower,
   costed, the toll) *strengthen* on the Board (a proven steward-of-the-restored-
   band, `shared-ledger.md` §2.2's steward-of-the-tide at the ecology end) while a
   settlement that *clears* one books a scar (the wound's legacy)? `fate-of-a-window.md`
   §6(c)'s forecast-≠-fate discipline says the blight is a conversation, not a
   sentence — but whether heal-vs-clear *reads differently* on the ledger is a
   designed decision. **[design]**

---

## Cross-references

- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — **THE over-bloom +
  THE conservation frame.** §4 the shallow species that do not shed / the
  q-accumulation's bloom; §2.2 life as a run the field holds (a corrupted organism
  is a run that stopped dying back); §4.2 regime ⇔ biome; **§5.2 the `(1−q)` glow as
  health-meter; §5.3 conservation = anti-corruption (the blight's healing frame)**;
  §6b the recognition rule (the band the blight overshoots).
- [`the-flood.md`](./the-flood.md) — **THE wrong-band habitat.** §2 the surfeit /
  the over-bloom; **§3 the shedding through the `(1−q)` waste (the self-limit the
  blight's own feeding obeys); §4 the husbandry (anti-bloom as the blight's
  prevention)**; §5/§6(b) the [design]-line, the gates the blight inherits; §6(e)
  the accessibility rule (the band's overshoot is the same read the instruments
  show).
- [`farm-that-feeds.md`](./farm-that-feeds.md) — **THE crop band.** §2 a crop
  precipitates in a band and holds it; §2.1 the farmer's warning (a blight
  overshoots the band — the harvest dies); §6a the cultivated distinction (a farm
  reads *maintained*, a blight's organism reads *maintained-then-corrupt*).
- [`energy-harnessing.md`](./energy-harnessing.md) — **THE drain + THE cap.** §2
  the `(1−q)` waste law `E_waste = (1−q)·E_throughput` (what a corrupted organism
  wastes and what chokes a starved blight); §5.4 anti-corruption (the heal's tool);
  **§6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a blight is a drain, never a
  harvest)**; §4.4 the Qi bath (an over-provisioned bath never receding is a
  wrong-band source).
- [`life-signal.md`](./life-signal.md) — **THE maintenance axis.** §3 a maintained
  lock pulses; §3.1 the classes (a blighted organism reads as **maintained-then-
  corrupt** — the pulse that keeps going after its feeding turned); §4.1 the
  breathing read; §6b/d the noise-floor probe + determinism gates.
- [`the-healer.md`](./the-healer.md) — **THE heal.** §2 the long bind — holding the
  torn edges while the attractor re-tensions (the heal applied at ecology scale);
  §2.2 the heal is spent, never a mint (the toll the honest proof); §3 the healer's
  toll (the region-wide bind's cost); §5b the transfer's gate.
- [`field-hazards.md`](./field-hazards.md) — **THE danger layer's house style.**
  §1 hazards are the field's own extremes (the blight joins as the first
  ecological one); §3 the `q` collapse the blight's falling region approaches;
  §5.1 readable-before-it-arrives; §5.3 the no-free-energy gate; §6.2 the
  player-agency gate; open-Q4 the scar-lifecycle probe (the clear's scar decision).
- [`weather-not-storm.md`](./weather-not-storm.md) — **THE provenance frame.** The
  blight's source read — is the wrong-band the field's own (a flood's over-bloom, a
  place's season) or the settlement's own (an over-provisioned bath, an
  over-husbanded plot)? The provenance read separates them and keeps the world from
  punishing opaque (§6e this doc).
- [`tide-of-the-attractor.md`](./tide-of-the-attractor.md) — the harvest/accumulation
  the wrong-band over-runs (§2, §3.2); **§5a the probe** (does the regional `q`
  accumulate — the wrong-band's gate, shared with the flood).
- [`wound-remembered.md`](./wound-remembered.md) — **THE clear's scar.** §1 a scar
  that refuses; the cleared blight's wound-class consequence; the scar-lifecycle
  probe (open-Q4 in field-hazards) the clear rides.
- [`the-scavenger.md`](./the-scavenger.md) — **the clear's scar as habitat.** §4.2's
  cleared scar — "the region purged, a scar left" — is the scavenger's home (§2.3
  there): where the blight was cleared *out*, the scavenger moves *in*, fitting the
  cleared scar's residual `ε²` rather than the corruption that caused it. Reverse
  pointer: the scavenger is the blight's clear's after-face.
- [`the-sea-floor.md`](./the-sea-floor.md) — **the water-borne habitat at the reef.** §2's
  wrong-band, spread by the water's flow, is what the sea-floor reads as a **reef-edge scar**
  (§2b/§4.1 there): the poisoned sea's shore is where the turned life concentrates, a
  standing `q`-sink read as the Scar-Lifecycle's kept boundary. Reverse pointer: the
  sea-floor reads the blight's water-borne habitat at the liquid regime's edge.
- [`the-scar-lifecycle.md`](./the-scar-lifecycle.md) — **the clear's depth answered.** §4.1
  there reads §4.2 this doc's clear ("the region purged, a scar left — its scar is the
  blight's monument") as the deep-wound instance: the clear spends the region's own `q`,
  a deep wound whose residue is a kept scar (§2.2 there) — the clear that does not scar
  was never a clear. Reverse pointer: the scar-lifecycle answers the clear's §4.2 open
  line; the clear that does not scar was never a clear.
- [`material-regimes.md`](./material-regimes.md) — **§3 the precipitation law** (the
  band the blight overshoots); §2 the regime table; the dissolution floor the
  blight's falling `q` approaches.
- [`fate-of-a-window.md`](./fate-of-a-window.md) — **THE arc.** §6(b) determinism (a
  hard gate the blight inherits); §6(c) forecast-≠-fate (the blight is a
  conversation, not a sentence).
- [`the-witness.md`](./the-witness.md) — **the not-turned.** §2 there reads §2 this
  doc's living-wrong turn — the witness does not turn (no band), the blight's inverse
  cousin in the stranger layer. Reverse pointer: the witness is the blight's non-turn.
- [`the-husbander.md`](./the-husbander.md) — **the early clearing.** §2b there reads
  §2 this doc's corruption mechanics, §3 the lifecycle, §4.2 the clear's scar (vs. the
  husbander's shallow-branch early clearing), §5e the seeding-read — the husbander
  reads the blight-seed at its start and clears it before it turns. Reverse pointer:
  the husbander clears the blight before it turns.
- [`the-guardian.md`](./the-guardian.md) — **the wrong-band's warden.** §3.1 there reads
  §2 this doc's band overshoot — what the Guardian drives off its ridge; §5e reads
  §6e the accessibility. Reverse pointer: a Guardian wardens the ridge against the
  wrong-band.
- [`the-wind.md`](./the-wind.md) — **the spore-carrier.** §2 there reads §2 the wrong-
  band and §3 the seeding's travel across the window — a wind carries the blight's
  seeding the way the sea's river carries a water-borne blight; §6e the readable
  approach. Reverse pointer: the wind carries the blight's seeding.
- [`the-gatekeeper.md`](./the-gatekeeper.md) — **the refused arrival.** §2 there reads
  the maintained-then-corrupt read (the arrival the office refuses); §6e the readable
  approach (the band's overshoot is the same read the instruments show — the
  office's refusal is legible); §5e the accessibility; §7 the verdict. Reverse
  pointer: the gatekeeper refuses the blight's wrong-band arrival.
- [`the-smell.md`](./the-smell.md) — **the wrong-stink.** §2 there reads the wrong-band;
  §6e the readable approach; §6c/d/e the gates. Reverse pointer: a blight's wrong
  odor is its approach read at the nose.
- [`the-migration.md`](./the-migration.md) — **the exodus's driver.** §2 there reads
  the wrong-band (the `q`-sink forces the move); §3 the standing drain. Reverse
  pointer: the blight's band is one migration driver.
- [`the-balefire.md`](./the-balefire.md) — **the warning of the wrong-band.** §2 the wrong-band (the balefire warns of the blight’s approach). Reverse pointer: the balefire is lit before the blight arrives.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers
  (the `192³/64³/12³` box, the ≈ 6 MiB publish, `ξ = φ⁶ ≈ 17.94`, `φ⁻² ≈ 0.382`,
  `τ_c = 0.5`, the `π/ρ` clamp `0.72`, `ω₀² = 20.0`, `dt = 0.05`, the ≈ 1–6 ms/tick
  budget, the ≈ 2,000 cap, `q ≈ 0.947` attractor, `q ~ 1e-3…1e-1` noise); cited, not
  re-derived.
