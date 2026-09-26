# The Wind: The Directional Weather — a Window's Moving Current, the Weather Stack's Flow-Face

**Question under design:** the corpus's weather stack is all **fronts, statics, and
recessions** — the **storm** a `c_s`-traveling `ε²` *front* ([`field-hazards.md`](./field-hazards.md)
§2), the **cold** a *static* long-thin held at the `q` floor ([`the-cold.md`](./the-cold.md),
q near the noise floor over a season), and (honestly un-landed here) the fog and the
drought the task's premise names but which are **not present on disk** (noted absent in
§6's open questions, not cited as existing). Every shape the weather takes is a *region* or
a *front* — **none is a directional transport: no wind, no moving *current* of
coherence/ε² through the air.** The weather has no **flow-face**. This document is that
design: **the Wind is the directional weather — a moving current of coherence/ε² through
the air**, the weather stack's flow-face, the one form that is not a region or a front but a
**directional current moving through** — the honest reason a storm arrives *when* it does
and a settlement reads the wind to know what the field is carrying toward it.

Companion to (all relative paths):
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — **THE air.** §1.3
  wind = `FieldVel`, the envelope's two-fluid waves ARE weather, and the medium's own
  velocity is written per cell (`vel[id] = vec4(∂EY/∂t, ∂EI/∂t, 0, ε²)`, `cassi_two_fluid.glsl`
  pass B); §1.5 wind lines = `FieldVel` color-coded by `q`; §2.4 the altitude wind over the
  moving-Voronoi site field. **The wind is the field's own current at its motion, not a new
  channel.**
- [`the-zenith.md`](./the-zenith.md) — **THE ceiling's air.** §2 the atmosphere's `(1−q)`
  waste escaping at the window's top; the zenith reads "the atmosphere holds well, the loss
  is small" — **the wind at altitude is the same air the zenith tops, read as a current**
  rather than a drain.
- [`field-hazards.md`](./field-hazards.md) — **THE storm-front / the front-vs-flow line.**
  §2 the storm is a `c_s`-traveling `ε²` front; **a wind moves that front faster or fans it
  apart — the front is the discrete event, the wind the current that carries it**; §5.1
  readable-before-it-arrives — the wind's carry is readable the same way.
- [`weather-not-storm.md`](./weather-not-storm.md) — **THE provenance classifier.** §2 the
  weather-vs-punishment read over the storm's published dynamics; **the wind's own
  provenance — what carries what, whose storm it is carrying — is this classifier's
  sibling**, the storm-provenance probe (§3) re-read for a moving current.
- [`coherence-highway.md`](./coherence-highway.md) — **THE road.** §1/§1.1 the `∇(g·Φ)`
  haul a cart rides downhill for free; **a tailwind cheapens that descent — the wind at
  your back is the gradient's own weather**; §3.1 the conduit (the wind is not a conduit —
  it is flow, ungated).
- [`the-walk.md`](./the-walk.md) — **THE crossing.** §2/§2a the stride-cost read at the
  player's position over `q`/`ε²`/`∇(g·Φ)`; **a headwind taxes the walk — a step against
  the current labors the way a step against the lean does**; §4b the ridge→scar→margin
  Phase-1 slice the wind's own slice sits beside.
- [`the-blight.md`](./the-blight.md) — **THE spore-band.** §2 the wrong-band; §6e the
  readable approach; **a wind may carry the blight's seeding across the window — the
  wrong-band's own travel, the way the sea doc's river carries a water-borne blight
  downstream** ([`the-sea.md`](./the-sea.md) §4 "spread by the water's own flow").
- [`energy-harnessing.md`](./energy-harnessing.md) — **THE waste + THE cap.** §2 the
  `(1−q)` waste law `E_waste = (1−q)·E_throughput` (the wind's glow is the law, read at
  its current); §1.7 the ambient attractor pump **forbidden to charge a capacitor** (a wind
  is flow, never a store); **§6 the no-free-energy cap (`output ≤ φ⁻¹·input`): a wind
  converts nothing — no transport that yields, no wind-farm into a travel-mint**.
- Skimmed as needed: [`the-marsh.md`](./the-marsh.md) — **the slow sea, the air's marsh.**
  §2/§3 the tessellated `q` hiding, the wake's blur; **the wind is the air's *moving* face
  of the same field's own motion — like the marsh's low-flow water, the wind provides
  nothing; the transport is the field's own current, honest.** [`signature-predator.md`](./signature-predator.md)
  §1.2 — **a wind carries signatures too** (the trail's legibility is a function of
  transport; a moving field carries a channeler's vent downwind).

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md) (the
canonical set — **cited, not re-derived**), engine-verbatim, or flagged **[design]** (a
designed surface / current-form / carry / movement-cost over real channels,
probe-calibrated) / **[probe]** (a pre-registered Phase-1 measurement). **The honest
boundary is drawn in §5 and never blurred: the `FieldVel` channel, the `(1−q)` waste law,
the storm's front, the `∇(g·Φ)` haul, the stride-cost read, the blight's seeding, and the
provenance classifier are their source docs' landed pieces; the wind's composition — the
flow's form, the carry, the cost-and-aid to movement — is this doc's [design] over them,
probe-calibrated.**

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| The Wind = ? | the **directional weather** — a moving current of coherence/ε² through the air: the weather stack's **flow-face**, the one form that is not a region or a front but a **directional current moving through**. Distinct from the storm's discrete `c_s` front and the static forms' regions: **the wind is flow, not a region.** |
| The flow = ? | the **field's own current at its motion** — `FieldVel` (the published medium velocity, `atmosphere-orbits-auroras.md` §1.3) read as a directional transport; the atmosphere's read at its motion and the zenith's altitude air (`the-zenith.md` §2). **The wind's form — its current's structure, its direction's source — is this doc's [design]** over the published channels, probe-calibrated. |
| The carry = ? | the **load-bearing design**: the wind **transports** — moves a storm's leading edge faster or fans a fog apart ("a wind moves a storm's front", `field-hazards.md` §2), carries a blight's spore-band across the window (`the-blight.md` §3), the honest reason a storm arrives *when* it does: **a settlement reads the wind to know what the field is carrying toward it** (`field-hazards.md` §5.1 readable-before-it-arrives; the provenance classifier's sibling, `weather-not-storm.md` §2). |
| The cost-and-aid = ? | the **load-bearing honesty**: the wind is a **cost-and-aid to movement** — a tailwind cheapens the road's journey (`coherence-highway.md` §1), a headwind taxes the walk (`the-walk.md` §2) — **the gradient's own weather**; and the **no-free-energy cap held**: **a wind provides nothing — no transport that yields** (`energy-harnessing.md` §6). |
| The honest boundary = ? | the storm's front, the air's read (`FieldVel`), the `∇(g·Φ)` haul, the stride-cost, the blight's seeding, the provenance classifier are their source docs' **landed** pieces; **the wind's composition — the flow's form, the carry, the cost-and-aid — is this doc's [design]** over them, probe-calibrated. |
| Honest gates = ? | (a) the [design]/engine-real line; (b) **PHASE-1-ABLE** — a bounded directional transport read over the published channels, rendered as a moving current with a mouth-and-tail, is a consumer, the Phase-1 slice stated; (c) determinism (same window, same field state → same wind — a hard gate; the current is deterministic, never a seeded gust roll); (d) the no-free-energy cap (a wind converts nothing — no transport that yields; the carry is the field's own; the cost-and-aid is a real exchange, never a mint); (e) accessibility (the wind's direction and carry readable from the instruments — never hidden-only; a settlement reads the wind the way it reads the storm). |
| Feasibility | **PHASE-1-ABLE — the weather stack's flow-face. State the slice and the gates (§5, §7).** |

---

## 1. The Wind, stated once

The corpus's weather has every shape but moving. The **storm** is a `c_s`-traveling `ε²`
front — a *discrete event* that travels but is not *flow* ([`field-hazards.md`](./field-hazards.md)
§2: "a wave front of disorder propagating at the coherence sound speed"). The **cold** is a
*static* long-thin — the `q` floor held over a season, the drain that wears
([`the-cold.md`](./the-cold.md)). What the weather stack has never designed is the *
direction* underneath it all — the air that *moves* even when no front is passing. The
atmosphere doc already names it in passing — **"the PDE's coherent flows ARE wind; the
medium's `FieldVel` channels are the current"** ([`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
§1.3) — but no doc gives that current a face, a form, or a consequence. The Wind is that
face, stated once and kept:

> **The Wind is the directional weather — a moving current of coherence/ε² through the
> air: the weather stack's flow-face, the one form that is not a region or a front but a
> directional current moving through.** It is the field's own current at its motion — the
> published `FieldVel` medium velocity read as a transport, the atmosphere's read at the
> altitude where it moves (`atmosphere-orbits-auroras.md` §1.3/§2.4, the zenith's air at
> the top). It **transports** — a wind moves a storm's leading edge faster or fans a fog
> apart, carries a blight's spore-band across the window, carries a signature's trail
> downwind — the honest reason a storm arrives *when* it does: **a settlement reads the
> wind to know what the field is carrying toward it.** And it is a **cost-and-aid to
> movement** — a tailwind cheapens the road's descent, a headwind taxes the walk — the
> gradient's own weather, and never a mint: **a wind provides nothing — no transport that
> yields.** It is the weather stack's **flow-face**: the form that is not a region or a
> front but a **directional current moving through** — the honest motion beneath every
> front's arrival and every static's persistence.

**Why this is the weather stack's missing face, honestly.** Every other weather shape is
a *state* or an *event* read off the field: the storm is where `ε²` spikes and travels as a
front; the cold is where `q` holds at the floor; the desert (a regional `q` collapse,
[`field-hazards.md`](./field-hazards.md) §3) is a recession the field's own state produces.
None of them is the *air itself moving*. The engine publishes the medium's velocity every
step (`FieldVel`, `vel[id] = vec4(∂EY/∂t, ∂EI/∂t, 0, ε²)`, [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
§1.3), the atmosphere renders it as wind lines (§1.5), the energy doc taps it as the
coherence turbine (§2.2) — yet nothing designs the *weather* that current is. The Wind is
the corpus's answer: the directional current the storm rides, the static forms move
through, and the settlement reads to know what the field is carrying toward it.

The honest scope, stated once: **the `FieldVel` channel, the `(1−q)` waste law, the
storm's front, the `∇(g·Φ)` haul, the stride-cost read, the blight's seeding, and the
provenance classifier are their source docs' landed pieces; the wind's composition — the
flow's form, the carry, the cost-and-aid to movement — is this doc's [design] over them,
probe-calibrated.** The Wind never claims the engine "has wind"; it reads the published
current the engine already computes and presents it as the weather stack's flow-face — a
consumer of the ≈ 6 MiB publish exactly as the Weatherglass and the walk are, never a new
channel, never a write.

---

## 2. The flow — the wind is flow, not a region

### 2.1 The landed current — `FieldVel`, the medium's own motion

**The landed piece.** The atmosphere doc grounds wind in the engine's real medium
velocity. Each PDE step writes the two-fluid medium's velocity into the published channel
`vel[id] = vec4(∂EY/∂t, ∂EI/∂t, 0, ε²)` ([`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
§1.3, §1.5, §6 — the atmosphere renders "the same published channels (ρ, q, ε², ∇(g·Φ),
FieldVel)" (§4); the field-velocity channel `FieldVel` is engine-real, written per cell by
the PDE, and read by the atmosphere's wind-line layer and the coherence turbine —
[`energy-harnessing.md`](./energy-harnessing.md) §2.2 — inside the ≈ 1–6 ms/tick budget,
`corpus-reconciliation.md`).
`atmosphere-orbits-auroras.md` §1.3 is explicit: **"Those coherent flows ARE wind. A
standing wave band in the envelope is a jet stream; a coherence pulse traveling along
`∇(g·Φ)` around the body is a weather front."** The engine already publishes a current;
what the corpus lacks is a design that reads it *as the weather's flow-face*.

The distinction the task names — *the wind is flow, not a region* — is drawn against the
pile of the static forms. The storm is a discrete `c_s`-traveling `ε²` front
([`field-hazards.md`](./field-hazards.md) §2.1); the cold is a static long-thin at the `q`
floor ([`the-cold.md`](./the-cold.md) §2). Both are *where the field is* at an extreme. The
wind is different in kind: it is **the motion itself**, present in coherent and decoherent
air alike, defined not by a state boundary but by a direction and a speed. It is the
weather stack's **flow-face** — the one form that is a *current*, not a region.

### 2.2 The wind's form — this doc's [design] over the published current

The `FieldVel` channel is engine-real; *how the window reads it as a weather shape* is the
design. Mirroring the storm's "front as a presented event" ([`field-hazards.md`](./field-hazards.md)
§2.1's [design]) and the zenith's "drain's read" over the waste law ([`the-zenith.md`](./the-zenith.md)
§2a), the wind's **form** — its **mouth-and-tail** structure, its **direction's source** —
is this doc's [design], probe-calibrated:

|| Wind element | What it reads | Grounding |
|---|---|---|---|
|| **Direction** — which way the current flows | the local `FieldVel` vector, aggregated over a reading window (a bounded sample band, not a point) | [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) §1.3 (the `FieldVel` channel; jet streams, weather fronts); the Weatherglass's **lean** is the player's glanceable downhill toward `∇(g·Φ)` ([`field-instruments.md`](./field-instruments.md) §1.2) — the wind's direction is the same current, read as flow |
|| **Strength** — how fast / how much coherence-ε² it moves | `|FieldVel|` over the reading window, weighted by the local `q` (a high-`q` current carries more than a low-`q` eddy) | the coherence turbine's output ∝ `½ρ|v_flow|²` ([`energy-harnessing.md`](./energy-harnessing.md) §2.2) — the same magnitude the wind is |
|| **Mouth-and-tail** — the moving current's presented form | the wind reads as a **mouth** (where the current is drawing coherence/ε² from) and a **tail** (where it is shedding it downwind), rendered as a directional band over the flow | **[design]** — the *composition* of the published `FieldVel`/`q`/`ε²` into a moving band with a leading and trailing edge; the storm's front is a presented event (`field-hazards.md` §2), the wind is its flow-form |
|| **Altitude** — the wind the zenith and the air read | the wind at altitude is the same `FieldVel` read in the envelope's moving band — the weather band itself (`atmosphere-orbits-auroras.md` §1.3: the mid-envelope is "where FieldVel is the wind") | the zenith's atmosphere is the air this current tops ([`the-zenith.md`](./the-zenith.md) §1/§2); the zenith's drain is the waste the top sheds, the wind is the current that sheds it |

**[design]** — the wind's *form* (the mouth-and-tail band, the direction's aggregation
window, the strength's `q`-weighting) is this doc's designed surface over the published
`FieldVel`/`q`/`ε²`, probe-calibrated on the Phase-1 slice (§5b). What is landed is the
current itself (`FieldVel`, `atmosphere-orbits-auroras.md` §1.3) and its readability as
motion (wind lines, §1.5; the coherence turbine's drain, §2.2). **The flow adds no
physics; it names the current the engine already publishes, read as the weather's
flow-face.**

### 2.3 The provenance — the wind's own reading, the classifier's sibling

The wind's direction and strength are [design] over real channels, but *what* is moving is
also a provenance question — and the corpus already has the classifier for it.
[`weather-not-storm.md`](./weather-not-storm.md) §2 distinguishes weather from punishment
by whether the `ε²` extreme is **self-limiting and "where the field is"** vs **persistent
and "where the player is"**. The wind's carry inherits that read as its **sibling**: a wind
is the field's own current (weather — it moves because the field moves), and what it carries
(whose storm, whose blight-seeding, whose signature) is provenance over the same channels
`weather-not-storm.md` §3's probe already reads. **The wind does not need a new classifier;
it is the provenance classifier's flow-face** — the moving reading of the same `ε²`/`q`
the storm-provenance probe measures, applied to what the current transports.

---

## 3. The carry — the wind transports

This is the load-bearing design: **the wind is what moves the weather.** Every front and
every static exists *in* the air, and the air moves. The storm doc's own language already
invites it — a storm is a "moving dissolution boundary" ([`field-hazards.md`](./field-hazards.md)
§2.1) — and the honest reason a storm front arrives *when* and *where* it does is that a
current is carrying it. The carry is the wind's gift to the whole weather stack:

|| The carry | What the wind moves | Grounding |
|---|---|---|---|
|| **A storm's leading edge** | the storm's `c_s`-traveling `ε²` front moves *faster* downwind — the wind is a current the front's own wave propagation adds to; a strong wind pushes a storm's leading edge ahead of where the `∇ε²` front would travel alone | [`field-hazards.md`](./field-hazards.md) §2 — **"a wind moves a storm's leading edge faster or fans a fog apart," the front-vs-flow line**; the front travels at `c_s = h₀/dt` in the medium, and a moving medium advects the front ([`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) §1.3: the medium's flow IS wind) |
|| **A fog / blur apart** | a wind *fans* a static blur — the diffuse, region-bound decoherence or fog the wind's current disperses rather than carries whole | the static forms sit in the air; the current fans them ([`the-cold.md`](./the-cold.md)'s static long-thin is the static register; the wind moves it) — **[design]** the fan as the wind's dispersing of a region |
|| **A blight's spore-band** | the blight's seeding travels downwind — the wrong-band's own spread carried by the current, the way [`the-sea.md`](./the-sea.md) §4 carries a water-borne blight "spread by the water's own flow" | [`the-blight.md`](./the-blight.md) §3 — **the seeding's travel across the window**; the sea's river carries the wrong-band downstream ([`the-sea.md`](./the-sea.md) §4) — the wind is that same carry in the air |
|| **A signature's trail** | a wind carries a channeler's `ε²` vent downwind — the trail's legibility is a function of transport | [`signature-predator.md`](./signature-predator.md) §1.2 — **the trail is legible only where the field has no order to hide it**; a current moves that trail, so the predator's read (and the walker's honest exposure) follows the wind |

**The honest reason a storm arrives *when* it does — the readable-before-it-arrives honesty
applied to the carry.** [`field-hazards.md`](./field-hazards.md) §5.1 is the danger layer's
cardinal rule: hazards are **readable before they arrive** — the sky reads first, then the
hand-held reader (§2.3). The wind is the *direction* of that readability: a settlement that
reads the wind knows **which way its storm is coming from**, which fog it will fan, which
spore-band it is carrying toward the crops. The wind does not make a hazard predictable in
time; it makes it predictable in *direction* — the flow-face of the readable-before-it-
arrives honesty, the answer to "what is the field carrying toward it."

**[design]** — *which* carries (storm-front advection, fog-fanning, spore-band travel,
signature transport) the wind actually performs, and at what strength relative to the
carried object's own motion, is this doc's designed composition over the landed channels —
`FieldVel` (§2), the storm's front mechanics (`field-hazards.md` §2), the blight's seeding
(`the-blight.md` §3), the trail's legibility (`signature-predator.md` §1.2) — probe-
calibrated. The engine-real core is the current itself; the carry is the designed reading
that gives it weather meaning. **The storm never becomes "wind-dragged" physics; the wind
names the transport a settlement reads to know what the field is carrying toward it.**

---

## 4. The cost-and-aid — the wind is a cost-and-aid to movement

The wind's second load-bearing honesty is that it is the **gradient's own weather** for the
moving player — a real exchange with the two crossing systems the corpus already designs.

|| The movement | A tailwind / headwind does | Grounding |
|---|---|---|---|
|| **The road's descent** | a **tailwind cheapens the journey** — riding the field's `∇(g·Φ)` descent with a current at your back is the field's own haul, plus the wind's carry; a headwind taxes the return | [`coherence-highway.md`](./coherence-highway.md) §1 — **the descent's wind at your back**: the `∇(g·Φ)` haul is engine-real ([`energy-harnessing.md`](./energy-harnessing.md) §1.1), the wind is the same haul's current form; the highway's free-haul honesty (the field does the work) is preserved — a tailwind is *free movement*, never free energy (§4d) |
|| **The walk's stride** | a **headwind taxes the walk** — a step against the current labors the way a step against the lean does; a tailwind eases it | [`the-walk.md`](./the-walk.md) §2/§2a — **the stride's cost against the current**: the walk's stride-cost read is a designed aggregation over `q`/`ε²`/`∇(g·Φ)` at the player's position (§4a there); the wind adds a *flow* term to that read — a headwind is a stride's dearness, a tailwind a stride's cheapness, the gradient's own weather |

**The cost-and-aid is a real exchange.** The wind is not a decoration; it genuinely
re-prices movement — a traveler who reads the wind crosses *with* the field's current
(tailwind) or pays the headwind's tax (against it), the same honest asymmetry the walk's
favorable-step discount establishes ([`the-walk.md`](./the-walk.md) §2a/§4a) applied to the
air itself. It is the **gradient's own weather** because it is the same `FieldVel` current
(downhill toward matter in `∇(g·Φ)`, [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
§1.3) that already steers the walk and the road — the weather stack's flow-face re-pricing
the movement that crosses it.

**The no-free-energy cap — a wind provides nothing, no transport that yields.**
[`energy-harnessing.md`](./energy-harnessing.md) §6's hard rule — **no conversion yields
more than it sinks, `output ≤ φ⁻¹·input`** — holds the wind without exception, stated in
its register:

> **A wind converts nothing — there is no tailwind that harvests.** The tailwind's
> cheapness is **free *movement* — the field doing the work it always does on a thing
> moving down its current** — and free movement is not free *energy*: the traveler cannot
> bank a tailwind, cannot store the current, cannot turn a favorable wind into stored
> coherence. The `(1−q)` waste the wind sheds is spent, never collected; the carry is the
> field's own current, never a gain; the headwind's tax is a cost, never a source. **A wind
> that "generates" something is a lie the cap forbids; a wind that moves the field's own
> coherence honestly is the free, ungated, un-minting flow.** The §1.7 ambient attractor
> pump is **forbidden to charge a capacitor** ('energy-harnessing.md' §1.7); so is a wind —
> it cannot be farmed into a travel-mint, because the `(1−q)` waste and the current's own
> diminishing returns cost the very freedom the tailwind grants.

Three concrete guards, all inherited from the corpus's own no-free-energy discipline
([`energy-harnessing.md`](./energy-harnessing.md) §6; [`the-walk.md`](./the-walk.md) §4d;
[`coherence-highway.md`](./coherence-highway.md) §6d; [`the-sea.md`](./the-sea.md) §5d's
"no water-wheel farm"):
1. **No wind-farm into a travel-mint.** A turbine placed in the wind taps the `(1−q)`
   fraction the current wastes ([`energy-harnessing.md`](./energy-harnessing.md) §2.2 — the
   coherence turbine is a real reservoir), but it is net-negative and *damps the flow it
   taps* (§2.2: "the rotor dampens the flow") — over-placing turbines stills the weather
   band the way they cool the field elsewhere ([`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
   §1.3). A tailwind is never a stored yield; the turbine harvests only waste, bounded by
   the cap.
2. **The carry is the field's own, never a gain.** The wind moving a storm's front or a
   blight's spore-band is *transport of the field's own current* — it rearranges what the
   field already holds; it creates nothing. A settlement cannot "mine the wind's carry" any
   more than the river's flow ([`the-sea.md`](./the-sea.md) §5d).
3. **The cost-and-aid is a real exchange, never a mint.** A tailwind's cheap stride and a
   headwind's tax are a *relation to the current* (the walk's favorable-step honesty,
   [`the-walk.md`](./the-walk.md) §4d), not free-transport to bank forever — the headwind's
   tax and the current's own character cost the very freedom the tailwind grants.

The wind's gift is **movement's honesty** — direction read, carry understood, movement
re-priced by the field's own current — never energy, and never a mint.

---

## 5. The honest boundary and gates

### (a) The [design]/engine-real line

Drawn once and never blurred:

| Quantity | Status | Basis |
|---|---|---|
| The `FieldVel` publish — the medium's own velocity (`vel[id] = vec4(∂EY/∂t, ∂EI/∂t, 0, ε²)`) | **engine-real** | `atmosphere-orbits-auroras.md` §1.3/§4 (the atmosphere's fifth rendered channel; the PDE writes it per cell through `cassi_two_fluid.glsl` pass B); the coherence turbine reads it ([`energy-harnessing.md`](./energy-harnessing.md) §2.2); `corpus-reconciliation.md` (the ≈ 1–6 ms/tick budget the read sits inside) |
| The `(1−q)` waste law, `E_waste = (1−q)·E_throughput`; the no-free-energy cap (`output ≤ φ⁻¹·input`) | **landed** | `energy-harnessing.md` §2/§6 |
| The storm's `c_s`-traveling `ε²` front (a discrete event, not flow); the front-vs-flow line (a wind moves a storm's front) | **landed** | `field-hazards.md` §2 |
| The `∇(g·Φ)` haul a road rides / a walk steps with (engine-real); the step-with-the-lean discount | **engine-real** / **[design]** (the discount's tune) | `energy-harnessing.md` §1.1; `coherence-highway.md` §1; `the-walk.md` §2a/§4a |
| The blight's seeding — the wrong-band and the readable approach | **landed** (the wrong-band `the-blight.md` §2; the readable approach §6e) — the wind's carry of it [design] | `the-blight.md` §2/§6e; the sea's water-borne carry ([`the-sea.md`](./the-sea.md) §4) as the liquid precedent |
| The provenance classifier — weather vs punishment over the storm's channels | **landed** ([design]-over-real, per its own doc) | `weather-not-storm.md` §2/§4 |
| **The wind's composition** — the flow's form (mouth-and-tail, the direction's aggregation, the strength's `q`-weighting), the carry (storm/fog/blight/signature), the cost-and-aid (tailwind-cheap, headwind-tax) | **[design]**, probe-calibrated | **this doc** §2/§3/§4 |

**The line, stated once:** the storm's front, the air's read (`FieldVel`), the `∇(g·Φ)`
haul, the stride-cost, the blight's seeding, and the provenance classifier are their source
docs' **landed** pieces. **The wind's composition — the flow's form, the carry, the
cost-and-aid — is this doc's [design]** over them, probe-calibrated exactly as
[`the-zenith.md`](./the-zenith.md)'s drain and [`the-marsh.md`](./the-marsh.md)'s
tessellation are over their landed stacks. No claim here pretends the engine "has wind";
the engine has the published `FieldVel`, the waste law, the storm's front, and the
crossing hauls — and the Wind is the designed reading that gives the weather's current that
face its character.

### (b) PHASE-1-ABLE — a bounded directional transport read over the published channels

The **Phase-1 slice is stated, deliberately built as the honest core:**

> **Phase-1: a bounded directional transport read as a moving current with a mouth-and-tail.**
> Take a bounded band of the Phase-1 atmosphere's `FieldVel` ([`chunk-field-quantization.md`](./chunk-field-quantization.md)
> §1.2 — the 192³/64³/12³ box; the atmosphere's Phase-1 wind-line layer,
> [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) §1.5), read it as **a
> moving current of coherence/ε²** — aggregate the local `FieldVel` (and its `q`/`ε²`
> weighting) into a **direction, strength, and mouth-and-tail**, and **measure the
> carry** — that a storm's `ε²` front, a blight's seeding drift, or a walker's stride reads
> measurably *moved* by the current. It is a **pure consumer of the publish** — it reads
> `FieldVel`/`q`/`ε²`/`∇(g·Φ)`/`(1−q)` (the canonical publish plus the atmosphere's
> fifth, engine-real `FieldVel` channel, both already sampled by the Phase-1 wind-line
> layer) inside the ≈ 1–6 ms/tick sample budget, on the Weatherglass's cost profile (a
> bounded sample band, the sample-at-position pattern of `field-instruments.md` §1.4), and
> **writes nothing new**.
> It needs no envelope-stability gate (the local fog/wind layer is Phase-1,
> `atmosphere-orbits-auroras.md` §1.6), no condensed body, no auroral rendering — a
> consumer over the published channels, the current's motion and carry measured at
> Phase-1.

The slice de-risks the whole vocabulary: if a bounded band of `FieldVel` measurably reads
as a moving mouth-and-tail current, and that current measurably carries a front's `ε²`
or a walker's stride, every later wind element (the storm advection, the fog-fanning, the
spore-band travel) inherits the same measured, engine-real current — exactly the de-risking
pattern of the walk's ridge→scar→margin slice (`the-walk.md` §4b), the marsh's patchy-`q`
read (`the-marsh.md` §8), and the highway's ride-downhill (`coherence-highway.md` §6b). It
is the **flow-face proved at Phase-1** before any of the designed wind mechanics exist.

### (c) Determinism — a hard gate

The field is deterministic (one PDE; the corpus's hard-determinism discipline,
`life-signal.md` §6d; [`the-walk.md`](./the-walk.md) §4c; [`coherence-highway.md`](./coherence-highway.md)
§6c):

> **Same window, same field state → same wind.** The wind's direction, strength, mouth-and-tail,
> its carry (which way a front's `ε²` moves, which way a spore-band drifts), and the
> cost-and-aid (a headwind's tax, a tailwind's cheapness) are each a **pure function of the
> region's real `FieldVel`/`q`/`ε²` trajectory** — no seeded-RNG, no player-relative
> variance, **never a seeded gust roll**. A player who re-enters the same window at the
> same field state reads the same current, the same carry, the same movement-pricing —
> every time. **This is a hard gate: the wind is a *true, learnable* fact about the field —
> reproducible and teachable, never a mood.**

This is what makes the wind *learnable* (a settlement reads, then masters, its window's
current) and keeps the cost-and-aid a real exchange rather than a random tax. The reading
window fixes a designed constant and reads the deterministic channel series over it — the
same discipline the walk's stride-cost, the highway's ride, and the marsh's hiding hold.

### (d) The no-free-energy cap — a wind provides nothing

Held without exception, per [`energy-harnessing.md`](./energy-harnessing.md) §6 and
§4 this doc. **A wind converts nothing — no transport that yields; the carry is the field's
own; the cost-and-aid is a real exchange, never a mint** (the three guards of §4, all
inherited: no wind-farm into a travel-mint, no mining of the carry, no banking of a
tailwind). A wind cannot be farmed into a travel-mint any more than a road or a river can
([`coherence-highway.md`](./coherence-highway.md) §6d; [`the-sea.md`](./the-sea.md) §5d) —
the corollary of the same law that makes a road a route and a river a carrying surface:
**the wind moves the field's own coherence honestly, and provides nothing.**

### (e) Accessibility — the wind's direction and carry are readable from the instruments, never hidden-only

Per the instrument-family rule ([`field-instruments.md`](./field-instruments.md) §2.1) and
the accessibility hard rule ([`field-music.md`](./field-music.md) §6):

> **The wind's direction and carry are readable from the instruments — a settlement reads
> the wind the way it reads the storm.** The direction is the Weatherglass's **lean**
> (the bauble already tilts toward the downhill of `∇(g·Φ)`, `field-instruments.md` §1.2) —
> the wind's current is the same channel, read as flow; the wind lines render the same
> `FieldVel` at sky scale ([`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
> §1.5); the aura and the `(1−q)` waste tint show where the current is carrying discharge.
> A player who never uses a "wind overlay" loses nothing: the direction is the lean, the
> carry is the `ε²`/`q` the instruments already show at the front's approach, the blight's
> seeding is the band's overshoot the reader already shows ([`the-blight.md`](./the-blight.md)
> §6e). **The wind is an idiom over real channels, structurally guaranteed by the
> shared-publish architecture** (`field-instruments.md` §1.3) — the settlement reads the
> wind the way it reads the storm: from the same published `q`/`ε²`/`∇(g·Φ)`/`FieldVel`,
> never hidden-only.

---

## 6. Open questions

1. **The fog and the drought are absent from the corpus.** The task's premise names the
   weather stack's static forms — "the storm (a `c_s` *front*), the fog (a *static* blur),
   the cold (a *static* long-thin), the drought (a *receding* boundary)." On disk,
   **`the-cold.md` exists** (the static long-thin, confirmed); **`the-fog.md` and
   `the-drought.md` do not exist** on disk and are **not cited as existing docs here**.
   The wind's *fanning a fog apart* and the *drought* as a receding boundary are referenced
   only as the design's contrast and the carry's intended target; whether the fog and the
   drought are designed (and whether the wind fans a fog or recedes a drought-boundary) is
   open until those docs exist. The wind's *storm-carry* and *spore-band carry* are fully
   grounded in the docs present. **[absence noted honestly]**
2. **The mouth-and-tail calibration (§2/§5b).** How wide a `FieldVel` band reads as one
   coherent *current* (with a leading mouth and a trailing tail) vs. a noisy set of eddies
   — the aggregation window and the strength's `q`-weighting. A [design] dial,
   probe-calibrated against the Phase-1 slice; a too-narrow window reads as turbulence, a
   too-wide as a static mass movement rather than a flow. **[design]/[probe]**
3. **The carry's strength (§3).** Does the published `FieldVel` actually move a storm's
   `ε²` front or a blight's spore-band at a *felt* rate, or is the current too weak at
   window scale to read as "carrying" (the same honest finding the walk's stride-cost
   might return — a flat read pushes the carry to pure presentation)? The Phase-1 slice's
   carry measurement is the pre-registered probe. **[design]/[probe]**
4. **The headwind/tailwind's stride-weight (§4).** How much the wind re-prices the walk's
   stride (a headwind's tax, a tailwind's cheapness) against the favorable-step discount
   ([`the-walk.md`](./the-walk.md) §4a) — is the wind's movement-exchange *felt* as a real
   cost-and-aid, or static against the stride's own gradient read? A [design] dial,
   shared with the walk's stride-cost calibration. **[design]/[probe]**
5. **The altitude wind vs. the observed storm (§2).** The wind at the zenith and the mid-
   envelope is the same `FieldVel` the storm rides. Is the altitude wind the *same* current
   as the ground wind, or a distinct band (the weather band at altitude vs. the boundary
   layer at the ground) — the honest open question the zenith's drain-vs-boundary geometry
   already carries? Rides the envelope-stability and the anchored-box atmosphere gates
   (`atmosphere-orbits-auroras.md` §1.6/§5a), so the full altitude wind is Phase-1.5+; the
   Phase-1 slice reads the local current. **[probe]**, Phase-1.5.

---

## 7. Feasibility verdict

**PHASE-1-ABLE — the weather stack's flow-face. State the slice and the gates.**

The Wind is **Phase-1-able** because its whole load-bearing design — the
mouth-and-tail flow read and the carry measured — is a *bounded consumer of the
already-published channels*, the same honest tier as the Weatherglass (`field-instruments.md`
§6), the walk's stride-cost (`the-walk.md` §5), the marsh's patchy-`q` read
(`the-marsh.md` §8), and the atmosphere's Phase-1 wind-line layer (`atmosphere-orbits-auroras.md`
§6). No new channel, no new physics, no write, no Q4 dependence — it reads
`FieldVel`/`q`/`ε²`/`∇(g·Φ)`/`(1−q)` (the canonical publish plus the atmosphere's fifth,
engine-real `FieldVel` channel, both already sampled by the Phase-1 wind-line layer) inside
the ≈ 1–6 ms/tick budget, aggregates a bounded band into a directional current with a
mouth-and-tail, and presents the weather's flow-face: the current that moves the storm's
front, carries the blight's seeding, and re-prices movement.

**The Phase-1 slice (the first current):** on the living-terrain/atmosphere demo, **take a
bounded band of `FieldVel` and read the moving current** — the direction, strength, and
mouth-and-tail, and the carry (a front's `ε²`, a walker's stride) measured *moved* by it —
a pure consumer of the publish that proves the load-bearing claim (the weather's flow-face
is real, directional, and carrying) before any of the designed wind mechanics exist. It
de-risks the storm's advection and the blight's spore-travel by measuring the same
engine-real current the corpus already publishes, at its motion.

**The gates, all held (§5):** (a) the [design]/engine-real line — the `FieldVel`, the waste
law, the storm's front, the haul, the stride, the seeding, the provenance classifier are
landed; the wind's composition — the flow's form, the carry, the cost-and-aid — is
[design], probe-calibrated; (b) PHASE-1-ABLE — a bounded directional transport read over
the published channels, rendered as a moving mouth-and-tail current, the Phase-1 slice
stated; (c) determinism — same window, same field state → same wind, a **hard gate** (the
current is deterministic, never a seeded gust roll); (d) the no-free-energy cap — a wind
converts nothing, no transport that yields, the carry is the field's own, the cost-and-aid
a real exchange never a mint; (e) accessibility — the wind's direction and carry readable
from the instruments, never hidden-only, a settlement reads the wind the way it reads the
storm.

**Binding risks, in order:** **(a)** the **mouth-and-tail calibration** (§6 Q2) — does the
`FieldVel` band aggregate into one coherent directional current, or read as turbulence? The
Phase-1 slice is the pre-registered probe; a turbulent read pushes the wind to *a
directionless motion read* (weaker, the honest finding `the-marsh.md` §8 risk a
pre-registers) rather than a mouth-and-tail. **(b)** The **carry's strength** (§6 Q3) —
does the current measurably move a front or a spore-band, or is the transport too weak at
window scale to feel? A weak carry pushes the wind to *pure movement-presentation* (honest
direction, no mechanical carry), still legitimate. **(c)** Keeping the **no-free-energy cap
honest** (§5d) — the wind must never read as a travel-mint or a wind-farm yield; the §6 cap
and the turbine's damping ([`energy-harnessing.md`](./energy-harnessing.md) §2.2) hold it
mechanically, not by tuning hope. **(d)** The **fog/drought absence** (§6 Q1) — the carry
claims against the fog and the drought are held open until those docs exist; the storm and
spore-band carries are fully grounded. **None contradicts the async, dual-world, or
regime-collapse architecture** — the Wind is a consumer of the publish, and its flow-face
is the corpus's own current ([`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
§1.3) read as the weather's moving form.

> **The honest statement that makes this doc load-bearing: the corpus's weather stack is
> all fronts, statics, and recessions — the storm a `c_s` front, the cold a static long-thin,
> the drought a receding boundary — but no directional transport: no wind, no moving current
> of coherence/ε² through the air. The weather has no flow-face. The Wind is that face
> filled: the directional weather — a moving current of coherence/ε² through the air, the
> field's own current at its motion (the published `FieldVel`), distinct from the storm's
> discrete front and the static forms' regions: it is flow, not a region. It transports —
> moving a storm's leading edge faster, fanning a fog apart, carrying a blight's spore-band
> across the window, carrying a signature's trail downwind — the honest reason a storm
> arrives *when* it does, and the readable-before-it-arrives honesty applied to the carry: a
> settlement reads the wind to know what the field is carrying toward it, the provenance
> classifier's sibling. It is a cost-and-aid to movement — a tailwind cheapens the road's
> descent, a headwind taxes the walk — the gradient's own weather; and it provides nothing,
> the no-free-energy cap held: the carry is the field's own current, never a gain, a wind
> cannot be farmed into a travel-mint. PHASE-1-ABLE — the weather stack's flow-face —
> bounded and deterministic in its current, accessible and honest in its read: the one form
> that is not a region or a front but a directional current moving through.** The Wind is
> the weather's motion filled — the flow beneath every front's arrival and every static's
> persistence, read the way a settlement reads everything else: from the field itself.

---

## Cross-references

- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — **THE air.** §1.3 wind
  = `FieldVel`, the medium's own velocity per cell (`vel[id] = vec4(∂EY/∂t, ∂EI/∂t, 0, ε²)`);
  §1.5 wind lines color-coded by `q`; §2.2/§6 the coherence turbine that taps the current and
  the Phase-1 wind-line layer the Wind's slice rides; §2.4 the altitude wind.
- [`the-zenith.md`](./the-zenith.md) — **THE ceiling's air.** §1/§2 the atmosphere the
  current moves through at the window's top; the drain's read (the wind is the current that
  sheds the waste; a wind at altitude); the anchored-box atmosphere gate the full altitude
  wind rides.
- [`field-hazards.md`](./field-hazards.md) — **THE storm-front / the front-vs-flow line.**
  §2 the `c_s`-traveling `ε²` front a wind moves; **§5.1 readable-before-it-arrives** — the
  wind's carry is readable the same way; §5.3 no-free-energy (a storm's drains, a wind's
  carry — never farmable).
- [`weather-not-storm.md`](./weather-not-storm.md) — **THE provenance classifier.** §2 the
  weather-vs-punishment read; §3 the storm-provenance probe — **the wind's own provenance
  (what carries what, whose storm it is carrying) is this classifier's sibling**;
  §6 the hard gates (determinism, accessibility, the cap) the wind inherits.
- [`coherence-highway.md`](./coherence-highway.md) — **THE road.** §1/§1.1 the `∇(g·Φ)`
  haul; **§1 the descent's wind at your back** (the tailwind cheapens the journey); §6b the
  ride-downhill Phase-1 slice the wind's slice de-risks; §6d the no-free-energy cap.
- [`the-walk.md`](./the-walk.md) — **THE crossing.** §2/§2a the stride-cost read at the
  player's position; **the stride's cost against the current**; §4b the ridge→scar→margin
  Phase-1 slice; §4d the no-free-energy cap (a walk converts nothing — a wind re-prices the
  stride, never mints).
- [`the-blight.md`](./the-blight.md) — **THE spore-band.** §2 the wrong-band / §3 the
  seeding's **travel across the window**; §6e the readable approach — a wind carries the
  blight's seeding the way the sea's river carries a water-borne blight ([`the-sea.md`](./the-sea.md)
  §4).
- [`energy-harnessing.md`](./energy-harnessing.md) — **THE waste + THE cap.** §2 the
  `(1−q)` waste law (the wind's glow); §2.2 the coherence turbine (the wind-power hook, and
  the damping that stills the band); §1.7 the ambient pump forbidden to charge a capacitor;
  **§6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a wind provides nothing)**.
- [`the-marsh.md`](./the-marsh.md) — **the slow sea, the air's marsh (skimmed).** §2/§3 the
  low-flow water that provides nothing — the wind is the air's *moving* face of the same
  field's own motion, honest and un-minting.
- [`signature-predator.md`](./signature-predator.md) — **THE trail (skimmed).** §1.2 the
  trail's legibility only where the field has no order to hide it — a wind carries
  signatures too (a channeler's vent moves downwind).
- [`field-instruments.md`](./field-instruments.md) — **THE instruments.** §1.2 the
  Weatherglass's forms (the **lean** is the wind's direction read at a glance); §1.3
  accessibility (structural, shared-publish); §1.4 the sample-at-position cost profile the
  wind's bounded band follows; §2.1 the family rule (the wind is a read, never a channel).
- [`the-cold.md`](./the-cold.md) — **the static long-thin (the wind's static register).**
  §2 the `q` held at the floor over a season — the static form the wind moves through; the
  contrast that makes the flow-face distinct. (The fog and the drought are **absent on
  disk**; noted in §6 Q1, not cited as existing.)
- [`the-sea.md`](./the-sea.md) — **the liquid carry precedent.** §4 a river carries a
  water-borne blight "spread by the water's own flow" — the air's carry of a spore-band is
  the same transport in the air; §5d the "never a mint" the wind's no-yield mirrors.
- [`the-rain.md`](./the-rain.md) — **the flow's carry.** §1 there reads the directional
  current (`FieldVel`); §3 the carry (storm-front, spore-band, signature); §5(b) the
  Phase-1 slice; §5(c)/§5(d)/§5(e) determinism, no-mint, accessibility. Reverse
  pointer: the rain is carried on the wind.
- [`the-smell.md`](./the-smell.md) — **the carry read at the nose.** §1 there reads the
  flow's direction (`FieldVel`); §3 the directional carry; §5b the slice; §5c/d/e the
  gates. Reverse pointer: smell is the wind's carry — you smell what is upwind.
- [`the-blizzard.md`](./the-blizzard.md) — **the flow at storm strength.** §1 the directional current (`FieldVel`); §2.2 the strength’s `q`-weighting; §3 the carry; §5(b) the slice; §5(c)/(d)/(e) the gates. Reverse pointer: the blizzard is the wind’s carry at storm strength driving the cold’s thin.
- [`the-touch.md`](./the-touch.md) — **the felt flow.** §1 the directional current (the touch reads the wind’s push at the skin). Reverse pointer: the touch feels the wind’s current without needing upwind geometry.
- [`the-dune.md`](./the-dune.md) — **the walked ridge.** §1 the directional current; §2 the `FieldVel` carry; §3 the carry; §4 the cost-and-aid; §5b the Phase-1 mouth-and-tail slice; §5c/d/e determinism, no-mint, accessibility. Reverse pointer: the wind’s `(1−q)` carry moves the desert’s spent surface into the wandering ridge.
- [`the-lightning.md`](./the-lightning.md) — **the carried front.** §1 the directional current; §3 the carry — a wind moves the storm’s front; §5c/d/e determinism, no-mint, accessibility. Reverse pointer: the wind moves the lightning’s storm-front, the discharge riding the same moving field.
- [`the-seacraft.md`](./the-seacraft.md) — **the sailing.** §3 the carry. Reverse pointer: a sailcraft rides the wind’s carry — the current moved, never free.
- [`world-difficulty.md`](./world-difficulty.md) — **the scaled flow.** §1 the directional weather; §2 the `FieldVel` flow; §5 the gates. Reverse pointer: a wild world’s extra wind is never farmable — the current scaled, never a mint.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers (the ≈ 6
  MiB publish = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1; the medium-velocity `FieldVel` is the
  atmosphere doc's fifth *rendered* channel — "every layer renders the same published
  channels (ρ, q, ε², ∇(g·Φ), FieldVel)" ([`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
  §4/§6) — read the same way the atmosphere reads it, never a new canonical additive; the
  64³ grid; the 192³ box; `ξ = φ⁶ ≈ 17.94`; `φ⁻² ≈ 0.382`; `τ_c = 0.5`; the `π/ρ` clamp 0.72; `ω₀² = 20.0`;
  `dt = 0.05`; the `q ≈ 0.947` attractor; the `q ~ 1e-3…1e-1` noise; the ≈ 1–6 ms/tick
  budget; the ≈ 2,000 cap; the ≈ 40 ns/entity river-law steer `a = −G_N·(π/ρ)·∇(g·Φ)`;
  `c_s = h₀/dt`); **cited, not re-derived.**
