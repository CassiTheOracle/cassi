# Field Instruments: The Weatherglass and the Far Mirror

**Question under design:** how the CassiCraft field is read when you are *not*
stopping to read it. Every existing field-read is either **aimed** (the
coherence reader **Sense** — `coherence-magic.md` §2 — a tool you hold and aim)
or **ambient** (sound, `field-music.md`; the sky, `atmosphere-orbits-auroras.md`).
Nothing designs the **always-on, glanceable read** — a pocket gauge, a hanging
bauble, that samples the published local `q`/`ε²`/`∇(g·Φ)` at the player's own
position *continuously*, with no aiming and no overlay. This document is that
design: **the Weatherglass**, a permanent magnetometer-at-a-glance (Phase-1
shippable, the mute player's guaranteed-equal instrument), and its ranged
descendant **the Far Mirror**, a built condenser-lens observer that resolves the
*sparse far-window publish* (`world-seams.md` gate (b)) into a legible chart of
another place's coherence.

One shared read idiom, two instruments — and a family rule that makes every
later instrument a **consumer of the same publish with a presentation idiom,
never a new channel.**

Companion to:
- [`coherence-magic.md`](./coherence-magic.md) — **THE dependency.** Sense §2
  (the Phase-1 coherence reader, a read-only rung-0 consumer of the publish);
  §5.1 the read-only-consumer discipline (an instrument reads the published
  snapshot, never physics state). **The Weatherglass is the same Sense channel
  repackaged as always-on.**
- [`field-music.md`](./field-music.md) — **the accessibility rule §6** (sound is
  an enhancement, never the only channel); the ambience (the `(1−q)` waste hum,
  the storm growl, the desert's silence). **The Weatherglass is the mute
  player's guaranteed-equal form of those sounds.**
- [`field-hazards.md`](./field-hazards.md) — the pre-warning channels §2.3
  ("reader ε² noise rises / auroras flicker / the (1−q) glow shifts"); the
  desert's `q`-collapse §3. **A continuous glanceable read of the same
  channels.**
- [`world-seams.md`](./world-seams.md) — **THE Far Mirror dependency.** Gate
  (b): a distant window is a *sparse simulation* from its condensed-body/site
  publish only (~KB), full 64³ only on approach; §2.2 beacon-reading navigation
  ("is it a window?"). **The Far Mirror upgrades that to "what is that window's
  full chart?"**
- [`energy-harnessing.md`](./energy-harnessing.md) — remote siting of reservoirs
  (§0/§2); the `(1−q)` glow (§2); the Qi bath (§4.4).
- [`field-npc-ai.md`](./field-npc-ai.md) — a far commons' health as a
  destination-decider (§3 — a village is a Qi bath whose health is its effective
  intelligence).
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — the aurora
  as the far read, resolved instrumentally (§3.3); the sky as the reader's
  atmospheric form.
- [`coherence-technologies.md`](./coherence-technologies.md) — concept 2 the
  gravity dial / condenser (the Far Mirror's optics); concept 4 the Qi bath;
  concept 3 the detuned boundary.
- [`field-archaeology.md`](./field-archaeology.md) — the sky's read of a far
  wound at range (§3.3); the reader as the scan tool (§3.1).
- [`async-field-domain.md`](./async-field-domain.md) — the publish contract §2.1
  (the channels every instrument samples); §2.2 the sparse condensed-body/site
  array (the Far Mirror's honest underlay).

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived), engine-verbatim, or flagged
**[design]** (a presentation/aesthetic choice over real channels). The line is
drawn exactly where the corpus draws it (`atmosphere-orbits-auroras.md` §5c):
**the channels are real; the instrument's *idiom* is [design].** No instrument
in this family ever introduces a new physics claim or a new published channel.

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| The always-on read = ? | The **Weatherglass** — a worn pocket gauge / hanging bauble sampling local `q`/`ε²`/`∇(g·Φ)` at the player's position continuously, with no aiming and no overlay. The same read-only Sense channel repackaged as glanceable. |
| The glanceable idiom = ? | calm steady lume when coherent; a **climbing glow** when `ε²` rises (a storm's front, `field-hazards.md` §2.3); **dead flat grey** when `q` collapses (the desert, §3); the gradient as a **lean**. |
| The family rule = ? | **Every instrument is a consumer of the same publish with a presentation idiom — never a new channel.** The glanceable presentation of the published channels is the family's base; later instruments extend it (the Still Room = a room-scale Weatherglass; the Far Mirror = the Weatherglass aimed outward at a sparse far-window publish). |
| The ranged descendant = ? | The **Far Mirror** — a built condenser-lens observer (`coherence-technologies.md` concept 2 optics) resolving the *sparse far-window publish* (`world-seams.md` gate (b), ~KB) into a legible chart: `q`-band health, `ε²` drains (far storm / far desert), condensed-body count and whether any is a young BH, envelope-band thickness. |
| Player-facing = ? | The Weatherglass is a simple worn object (Phase-1, craftable from a few field-organized materials). The Far Mirror is a built structure — a condenser tower, a designed composition of optics + the sparse publish. |
| Honest gates | (a) Weatherglass is Phase-1, pure consumer — **genuinely nothing new**. (b) Far Mirror gates on the two-window LOD / sparse far-window sim (`world-seams.md` gate (b), Phase 2+); the *chart* is a designed rendering of that honest underlay [design]. (c) glanceable must complement — not duplicate — the reader (aim vs glance), with accessibility parity a hard rule. (d) performance: the Weatherglass is one extra sample at the player's position (nothing); the Far Mirror reads ~KB, not the grid. |
| Feasibility | **Phase-1**: the Weatherglass — ship it now; it de-risks and pre-shapes every later instrument. **Later**: the Far Mirror — gated on world-seams' sparse publish. The family rule is the load-bearing takeaway. |

---

## 1. The Weatherglass — the always-on, glanceable field read

### 1.1 The instrument and its position

Every current field-read occupies one of two ergonomic modes. Sense
(`coherence-magic.md` §2) is **aimed**: a hand-held coil you hold and point, the
published `q`/`ε²`/`∇(g·Φ)` rendered as a magnetometer overlay — a tool you
*stop for*. Sound (`field-music.md`) is **ambient**: the field you *stand in*,
heard continuously but without spatial/quantitative precision. The sky
(`atmosphere-orbits-auroras.md` §3.3) is ambient at scale. Nothing fills the
empty middle — a read that is **always-on and glanceable**: continuous, no
aiming, no overlay, telling you the field's state at your own position the way a
wristwatch tells time.

**The Weatherglass closes that gap.** It is a small, worn object — a pocket
gauge, a hanging bauble — that continuously samples the *local* published
channels at the player's position. It is physically embedded in the world (a
physical object you craft, wear, and can hand to another player), not a HUD
overlay: you *see it* on your character, and its state is its readout.

> **The Weatherglass is the same read-only Sense channel repackaged as
> always-on — zero new physics, a pure Phase-1 consumer of the already-published
> snapshot.** It adds nothing to the publish (`corpus-reconciliation.md`: `q` 1 +
> ε² + `∇(g·Φ)` 3 + ρ 1, the ≈ 6 MiB snapshot the sampler already consumes), and
> it respects `coherence-magic.md` §5.1's discipline exactly: it is a *read-only*
> consumer of the published buffers, never a touch on physics state. It is, in
> the corpus's word, a **magnetometer-always-on** — the reader's magnetometer
> read, continuously, at no cost. It is the Sense channel's *ergonomics*, not a
> new read.

### 1.2 The glanceable idiom — what each channel state looks like

The Weatherglass presents **four channels, four glanceable forms**. All four
are [design] presentations of real published channels; the *mapping* is faithful
(the channels this doc reads are the same ones `field-hazards.md` §2.3 warns
with and `coherence-magic.md` §2 Sense renders).

| Published channel | Glanceable form | What it shows |
|---|---|---|
| **q** (coherence, `[0,1]`, attractor ≈ 0.947) | a **lume/glow** — the bauble's own light | high local `q` → calm, steady, bright lume. This is the *default healthy state* of the field, and the Weatherglass's resting brightness tells you the field around you is holding the φ-lock. |
| **ε²** (decoherence) | a **climbing glow** — brightness that *rises* over the steady lume | rising local `ε²` → the glow climbs toward the top of the bauble. This is the *non-equilibrium* tell: a storm's leading edge (`field-hazards.md` §2.3 — "reader ε² noise rises"), a scar, a decoherence well. The climb is directional and continuous, so you see it *rising* before the storm's dissolution front arrives. |
| **(1−q)** (the waste fraction, per `energy-harnessing.md` §2) | a **waste tint** — a colored wash distinct from the coherent lume | every working system bleeds `(1−q)` as glow; the Weatherglass shows the *local* fraction — how wasteful the field here is running. A bright wasteful locality reads warmly; a clean region reads cool. Theoretically this is `1−q` of the same channel; the [design] is which *hue* denotes waste. |
| **∇(g·Φ)** (the river gradient) | a **lean** — the bauble tilts toward the downhill of the gradient | the gradient points toward matter and steers the field (`energy-harnessing.md` §1.1); the Weatherglass leans the way a body would move under the river law `a = −G_N·(π/ρ)·∇(g·Φ)` (`coherence-magic.md` §1). You glance and know "downhill is that way." |

With these four, the field's extremes read at a glance — exactly the pre-warning
channels `field-hazards.md` §2.3 names:

> **The desert's signature is dead flat grey.** When local `q` collapses toward
> the noise floor (`households` — `field-hazards.md` §3.1: `q ≈ 1e-3…1e-1` at
> noise up to the attractor), the lume **dies to flat grey** — nothing climbing,
> no lean, the waste tint gone. The most unsettling state of the weatherglass is
> the *absence of a reading*, exactly as the desert's most unsettling sound is
> *silence* (`field-music.md` §2.3). A grey Weatherglass is the physics of `q`
> collapse made visible in your hand.

### 1.3 The accessibility rule made hard

`field-music.md` §6 is a hard rule, not a nice-to-have:

> **Sound is an enhancement of the reader, never the only channel.** A mute
> player must not lose information: every diagnostic above is also readable on
> the reader overlay and the sky. A player with sound off plays the game the
> reader-based docs already specify.

The **Weatherglass is the mute player's guaranteed-equal instrument** — the
glanceable twin of every diagnostic sound. `field-music.md` gives each hazard an
audible form; the Weatherglass gives each a glanceable one, on the same channels,
so a player who cannot (or chooses not to) hear loses *nothing*:

| Sound (`field-music.md`) | Glanceable twin (this doc) | Same channel |
|---|---|---|
| The storm growl (§2.2) — rising dissonance as ε² ramps | the **climbing glow** (§1.2) | ε² |
| The desert's silence (§2.3) — nothing to sonify where q collapsed | **dead flat grey** (§1.2) | q |
| The `(1−q)` efficiency hum (§1) — waste heard | the **waste tint** (§1.2) | (1−q) |
| The residue / ghost-halo hum (field-music §2.4; archaeology §3.1) | the **quiet q-locked lume** at a coherent anomaly | q / ε² |
| An approaching window's hum from the dark (field-music §5) | the Far Mirror's chart (§3) | sparse far publish |

The rule is *hard* because it is *structural*: every sound is driven from a
published channel, and every channel the Weatherglass presents is the *same
published channel* — so the twin is guaranteed by the architecture, not tuned in.
There is no "sound-off mode" of the Weatherglass; there is one field, read two
ways. The Weatherglass is the form of `field-music.md`'s accessibility promise
made physically guaranteed.

### 1.4 The Weatherglass in Phase-1 terms

Concretely, the Weatherglass is the **same data path as Sense, at zero marginal
cost**:

- **Sample point:** a single trilinear sample of the published `q`/`ε²`/`∇(g·Φ)`
  at the player's world position — the "one extra sample at the player's
  position" of gate (d). The sampler already evaluates the field for entity
  steering (`async-field-domain.md` §3.3); the Weatherglass is one more read off
  the same immutable publish, inside the ≈ 1–6 ms server sample budget
  (`corpus-reconciliation.md`).
- **Refresh cadence:** follows the publish cadence (every Kth physics job, not
  per tick, `async-field-domain.md` §2.3). The Weatherglass is a *glance* — it
  does not need 20 Hz; the publish's cadence is its natural refresh.
- **Render:** a tiny object on the player model whose material/emissive reads the
  four forms above. **[design]** the exact object shape, the lume color, the lean
  curve, and the grey threshold are the instrument's aesthetic; the *channel
  mapping* is honest.

This is the whole instrument. There is genuinely nothing new — which is the
point of shipping it first (§6).

---

## 2. The instrument family architecture — one idiom, many instruments

### 2.1 The family rule

> **Every instrument in this family is a consumer of the same publish with a
> presentation idiom — never a new channel.**

Every field-read in the corpus already obeys this: Sense renders the published
buffers (`coherence-magic.md` §5.1), sound sonifies them (`field-music.md` §1),
the sky renders them at scale (`atmosphere-orbits-auroras.md` §1.5), the reader
in the dark navigates a window-star by them (`world-seams.md` §2.2), archaeology
reads a residue signature with the same instrument (`field-archaeology.md` §3.1).
The **instrument family** is the deliberate codification of that pattern: a
shared **base read idiom** (the glanceable presentation of the published
channels) that each instrument extends by changing **range, scale, or target** —
never by inventing a channel.

The Weatherglass is the family's **base and its proving ground**:

| Instrument | Idiom | Target | Status |
|---|---|---|---|
| **Sense** (reader) | aimed magnetometer overlay | local published `q`/`ε²`/`∇(g·Φ)` | Phase-1 (`coherence-magic.md` §2) |
| **Weatherglass** | glanceable lume/lean | local, at the player | **Phase-1 (this doc)** |
| **Still Room** | a room-scale Weatherglass | the room's locality, rendered large | later — the *same idiom*, larger scale |
| **Far Mirror** | the Weatherglass aimed outward | a distant window's sparse publish | Phase 2+ (this doc §3) |
| **any future instrument** | a consumer of the publish with a presentation idiom | whatever locality/range is legible | — |

### 2.2 The base idiom is the shared read

The Weatherglass's four forms (§1.2) **are** the family's base vocabulary. A
later instrument does not invent a fifth form for a new channel; it *places the
same four forms at a different scale or range*:

- **The Still Room** — a structural descendant: a wall- or room-sized display
  rendering the *same* local sample set (or a small cluster of sample points) as
  the four forms, scaled up so a whole room or the whole village visually drifts
  with the local field. It is a Weatherglass with a longer optical arm and a
  bigger lens — no new channel, just a bigger canvas. (The Qi-bath commons of
  `field-npc-ai.md` §3.1 would mount one at its core — a village *sees* its bath's
  health the way a player wears theirs.) **The Still Room at two further scales,
  reverse-pointers (two-way):** the *bed* is a personal Still-Room interval —
  the same coherent/patient read at the body's scale (`sleep.md` §3; the night's
  clearing and risk are the Still Room's logic on one sleeper); the *seed-garden's
  vault* is the Still Room's read at preservation scale — the deep-rung, high-`q`
  hold where the window's deepest orders are kept above their `q_dissolve`
  (`seed-garden.md` §3, the same four-forms read re-pointed at a stored seed's
  shelf). All three scale this §2.2 idiom with no new channel.
- **The Far Mirror** — the Weatherglass's lens *repointed outward*: instead of
  sampling "here," it samples "there." It is the same base idiom (the chart of
  §3.2 is literally the four forms laid out for a distant place), with **range**
  as the only new dial — and that dial's honesty is the underlay of §3.1.

This is the family answer to the corpus's standing refrain that the field must
*move* for placement-constrained mechanics to be fun (`coherence-technologies.md`
Q2): the instruments do not ask the field to move more; they present *the same
movement* in more places and more scales. The field is one law; the instruments
are all reads of it.

---

## 3. The Far Mirror — reading another window

### 3.1 The honest underlay: the sparse far-window publish

The Far Mirror does **not** invent a ranged channel. It reads the sparse
far-window record that `world-seams.md` already designs:

> **Gate (b)** (`world-seams.md` §6): *"A distant window is a **sparse**
> simulation, not a second full 192³ box. While it is a star (far away), it is
> rendered from its **body/site publish record only** — the sparse condensed-body
> array (`async-field-domain.md` §2.2, tens-to-hundreds of records, ~KB) — not
> its dense grid. It becomes a full second domain *only* on approach."*

So the honest footing is exactly the ~KB sparse record `async-field-domain.md`
§2.2 already specifies: the **condensed bodies** (the merge lineage's
"dust → object → BH", tens-to-hundreds of sparse records at Phase-1 scale) and
the **meshless sites** (2·16³ = 8192 moving-Voronoi records, `corpus-
reconciliation.md`). The Far Mirror **reads that record** — it does not (and
cannot) ask the engine to publish a far window's dense grid. **[design]** The
*chart* of §3.2 is a designed rendering of that honest underlay; the underlay
itself is `world-seams.md` gate (b)'s sparse sim, flagged throughout.

The optics are the condenser lens of `coherence-technologies.md` concept 2 — "a
structure that *geometrically concentrates* ambient coherence into a `q → 1`
node"; the pyramid-as-lens concentration, `(base/apex)²`, the shape-is-the-tuner
rule. **The Far Mirror is the condenser's lens *aimed at a window-star***: a
built tower whose internal geometry focuses the sparse far-window publish's
resolved structure into the legible chart.

> **The upgrade arc, stated once.** Beacon-reading (`world-seams.md` §2.2) tells
> you, with the reader pointed at a distant window-star: *is it a window at all,
> or a false gleam? is it healthy or wounded? is it a body or a world?* **The Far
> Mirror upgrades that to the full chart**: not "this star is a window," but
> "this window's `q`-band is healthy, it has an `ε²` drain growing on its west
> face (a storm forming?), three condensed bodies of which one reads as a young
> BH, and a thin envelope band." The reader answers *what am I looking at*; the
> Far Mirror answers *what is that place's state.*

### 3.2 The chart — the four forms, laid out for a distant place

The Far Mirror's readout is the same base idiom (§2.2) spread over the sparse
far-window record. Each row is one of the family's four forms, resolved from the
sparse publish's entries:

| Chart row (the base idiom at range) | Resolved from the sparse record | Strategic use |
|---|---|---|
| **`q`-band health** — the far window's operating coherence | the bodies'/sites' aggregate coherence **vs. the `(1−q)` waste they shed** (sparse records carry `q`/ρ per record, `energy-harnessing.md` §2) | triage a destination's general health before committing to it |
| **`ε²` drains** — rising-decoherence reads | a sparse body/site cluster with elevated local `ε²` — the "climbing glow" of §1.2, resolved far | a **far storm** (`field-hazards.md` §2.3) if the ε² is elevated and moving/clustered; a **far desert** (`field-hazards.md` §3.1) if it is broad `q`-collapse instead — the four-form distinction (climbing vs grey) works at range too |
| **Condensed-body count, and whether any is a young BH** | the sparse condensed-body array; the BH record's presence/`mass` (`async-field-domain.md` §2.2; `energy-harnessing.md` §1.6) | know before you sail whether the destination holds a reservoir (`energy-harnessing.md` §1.6, §2.6) or a growing hazard (`field-hazards.md` §4) |
| **Envelope-band thickness** | the far window's boundary-layer band resolved from its sites' envelope gradients (the sky's envelope-top band of `atmosphere-orbits-auroras.md` §1.3/§3.3, read from spare) | a thick, bright band = a large coherent body/world; a thin one = a small body or a failing shell |

The chart is deliberately **the four forms of §1.2 spread over "there"**: a
healthy far window shows a steady bright `q`-band, small stable waste, no
climbing `ε²`, a calm body list; a dangerous one shows a climbing `ε²` drain
(that storm growing west), grey pockets (desert creeping), or a young-BH record
the player must weigh before spending a coherence-budget voyage
(`world-seams.md` §2.3) to reach it.

### 3.3 The strategic role

The Far Mirror is the **destination-decider** the corpus's later-Phase systems
name but never build:

| Use | What the Far Mirror resolves | Cross-ref |
|---|---|---|
| **Triage a destination before a coherence-budget voyage** | "Is the place I'm committing my voyage's coherence to (`world-seams.md` §2.3's constraint economy) healthy enough to be worth it?" — the `q`-band, the drains, the BH records | `world-seams.md` §2.2/§2.3 |
| **Remote-site reservoirs** | "Where, far away, is an energy draw I want?" — a young BH (`energy-harnessing.md` §1.6), a bright drain (`(1−q)` glow, §2), a Qi-bath-able high-`q` core — read before sailing | `energy-harnessing.md` §0/§1/§4.4 |
| **Read a far commons' health before joining** | "Is the NPC settlement I'm sailing to (`field-npc-ai.md` §3 — a village is a Qi bath; its health is its effective intelligence) alive and coherent, or deserted?" — the commons' `q`-band and any creeping `ε²` | `field-npc-ai.md` §3 |

All three are the same act: **consult the far place's honest sparse record, not
a guess**. The Far Mirror does not divine the future — it presents the present
sparse state of another window, which is exactly the information a coherence
budget's commitment should gate on.

### 3.4 The Far Mirror's build

The Far Mirror is a **built structure, not a handheld**: a condenser tower — a
designed composition of `coherence-technologies.md` concept 2's shape-is-the-
tuner optics over the sparse-publish reader. The player assembles it (a wide
base, a narrowing apex — the lens of the pyramid-as-Qi-lens, concentration
`(base/apex)²`) and aims it at a window-star; the tower's internal geometry
focuses the sparse record into the chart. It is the Weatherglass's lens *repointed
outward*, made big enough to resolve a far, thin signal.

**The honest boundary:** every number the Far Mirror reads is the ~KB sparse
record (`world-seams.md` gate (b)); the lens is concept 2's **already-designed**
optics (concentration, shape-is-the-tuner); the chart is [design]. It is not the
weatherglass's physics plus *new* physics — it is the same family idiom with a
longer optical arm. That's what keeps it honest and Phase-2+ rather than
fiction: the underlay is a designed sim, but it is the *same designed sim the
corpus already gates.*

---

## 4. Player-facing — crafting and feel

| | Weatherglass | Far Mirror |
|---|---|---|
| **What it is** | a worn pocket gauge / hanging bauble | a built condenser tower |
| **Build** | a small craft from a few field-organized materials (a shallow high-`q` residue / Qi-bath-adjacent material) | a designed structure — the lenses and supports of `coherence-technologies.md` concept 2, aimed at a window-star |
| **Build cost** | trivial (Phase-1 object) | a real build (Phase 2+, downstream of the sparse far-window sim) |
| **Interaction** | none — it is always on, glance at your wrist | aimed once at a window-star, read the chart |
| **The feel** | **the field becomes a constant companion, not a tool you stop for.** The core claim of the always-on read: you internalize the local field's rhythm by living in it, the way you internalize a heartbeat. | **"another window" stops being a vague star and becomes a charted place.** The strategic feel of the ranged read: you plan *with* the far place's state, not around a guess. |

The Weatherglass is the **guaranteed-equal** instrument in the corpus's exact
sense: `field-music.md` §6's accessibility rule is met with a *physical object any
player can craft*, not a settings toggle. A player who turns sound off is not
diminished — they wear the field on their wrist.

---

## 5. Honest gates

**(a) The Weatherglass is Phase-1 and pure consumer — genuinely nothing new.**
It adds one trilinear sample at the player's position off the already-published
snapshot and renders it as a small object. It does not write, does not add a
channel, does not wait on any later-Phase system. This is the honest statement
with no hedging: **the Weatherglass introduces no new physics, no new channel, no
new engine code.** The only new thing is its *ergonomics* — and those are the
point.

**(b) The Far Mirror gates on the two-window LOD / sparse far-window sim**
(`world-seams.md` gate (b), Phase 2+). The *chart* is a designed rendering of
that honest underlay — flag **[design]**. It cannot exist before the sparse
far-window publish does; it reads only what that publish carries. It is honest
sequential work on `world-seams.md`'s skeleton, exactly as `world-seams.md`
itself is on `ksp-kernel.md`.

**(c) The glanceable idiom does not duplicate the reader.** Sense is *aimed*
(coherence-magic §2 — you stop and point); the Weatherglass is *glanceable*
(always-on, hands-free). The two are complements, like a compass and a map — the
reader answers "what is that," the Weatherglass answers "what is this, now,
constantly." And the accessibility parity is a **hard rule, not a tuning goal**:
every diagnostic sound in `field-music.md` has a glanceable twin on the same
channel (§1.3), structurally guaranteed by the shared-publish architecture.

**(d) Performance.** The Weatherglass is one extra sample at the player's
position — nothing against the ≈ 1–6 ms/tick server sample budget
(`corpus-reconciliation.md`). The Far Mirror reads ~KB, not the grid: the sparse
condensed-body array (`async-field-domain.md` §2.2, tens-to-hundreds of records)
is the *only* thing it reads, so it never approaches the ~6 MiB dense publish,
let alone a second 64³ grid. The LOD budget that `world-seams.md` gate (b) gates
on is the same budget the Far Mirror respects by construction.

---

## 6. Feasibility verdict

**Phase-1: the Weatherglass — ship it now.** It is the cheapest possible
field-instrument: one consumer of the already-published snapshot, rendered as a
worn object. Shipping it first **de-risks and pre-shapes** every later instrument
in the family: it builds and proves the base idiom (the four glanceable forms)
once, so the Still Room and the Far Mirror inherit a tested vocabulary instead of
each inventing its own read. It also *closes the accessibility rule in Phase-1* —
`field-music.md` §6's "mute player loses nothing" becomes literally true the day
the Weatherglass lands, before any later-Phase system exists to test it against.

**Later: the Far Mirror** — gated on `world-seams.md` gate (b)'s sparse
far-window sim (Phase 2+), and honest sequential work there. Its chart is [design]
over that honest underlay; its optics are `coherence-technologies.md` concept 2's
already-designed condenser lens. It turns "another window" from a vague star
(beacon-reading, `world-seams.md` §2.2) into a charted place — the destination-
decider the corpus's voyage (`world-seams.md`), reservoir-siting (`energy-
harnessing.md`), and commons-health (`field-npc-ai.md` §3) systems all name.

**The load-bearing takeaway is the family rule:** *every instrument is a consumer
of the same publish with a presentation idiom, never a new channel.* It is what
makes the Weatherglass a pure Phase-1 consumer, what keeps the Far Mirror honest
against its sparse underlay, and what guarantees the accessibility parity
structurally rather than by effort. **The field is one law; the instruments are
all reads of it, and adding one never adds to the field.**

---

## Cross-references

- [`coherence-magic.md`](./coherence-magic.md) — **Sense §2** (the read-only Phase-1
  consumer whose channel the Weatherglass repackages); **§5.1** the read-only-consumer
  discipline both instruments inherit; the magnetometer framing; the river law
  `a = −G_N·(π/ρ)·∇(g·Φ)` that gives the Weatherglass's lean.
- [`field-music.md`](./field-music.md) — **the accessibility rule §6** (sound is an
  enhancement, never the only channel); the ambience; the storm growl / desert's
  silence / `(1−q)` hum — every one of which has a Weatherglass twin (§1.3).
- [`field-hazards.md`](./field-hazards.md) — the pre-warning channels §2.3 ("reader ε²
  noise rises / auroras flicker / the (1−q) glow shifts"); the desert's `q`-collapse
  §3 (the weatherglass's grey); the storm's climbing-ε² front (the weatherglass's climb).
- [`world-seams.md`](./world-seams.md) — **gate (b)** the sparse far-window sim (the Far
  Mirror's honest underlay, ~KB); **§2.2** beacon-reading (the upgrade arc — "is it a
  window?" → the Far Mirror's chart); **§2.3** the coherence-budget voyage (what the
  Far Mirror triages).
- [`energy-harnessing.md`](./energy-harnessing.md) — the `(1−q)` waste law §2 (the
  Weatherglass's waste tint, the Far Mirror's drain reads); the Qi bath §4.4 (siting);
  remote reservoir siting §0/§1.
- [`field-npc-ai.md`](./field-npc-ai.md) — §3 a village is a Qi bath (read a far
  commons' health as a destination-decider).
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — the aurora as the
  far read, resolved instrumentally §3.3; the envelope-top band and pole discharges
  (the Far Mirror's envelope-thickness row); the sky as the reader's atmospheric form.
- [`coherence-technologies.md`](./coherence-technologies.md) — **concept 2 the gravity
  dial / condenser** (the Far Mirror's optics; shape-is-the-tuner); concept 4 the Qi
  bath (the Still Room's natural mount); concept 3 the detuned boundary.
- [`field-archaeology.md`](./field-archaeology.md) — the sky's read of a far wound at
  range §3.3; the reader as the scan tool §3.1.
- [`async-field-domain.md`](./async-field-domain.md) — the publish contract §2.1 (the
  channels every instrument samples); §2.2 the sparse condensed-body/site array (the Far
  Mirror's ~KB underlay).
- [`the-dawn.md`](./the-dawn.md) — **the family's becoming.** §4 there reads §2.1 this
  doc's family rule as the dawn's own: a consumer of the published `q`/`(1−q)` over the
  transition window, with the instrument family's presentation idiom, never a new channel,
  never a write (§1/§2 there); §1.2 the Weatherglass's four forms are the idiom the
  breaking renders. Reverse pointer: the dawn is the family's transition-read member.
- [`the-stratum-read.md`](./the-stratum-read.md) — **a depth-axis member of the family.**
  §2.1 there reads §2.1 this doc's family rule as the Stratum-Read's spine — a consumer of
  the publish with a presentation idiom, never a new channel; §1.4's sample-at-position
  pattern is the one-sample-per-stratum cost it follows; §1.2 the Weatherglass's state read
  is the pulled-layer / scar-grey / heal-fade idiom. Reverse pointer: the Stratum-Read is a
  depth-axis member of this instrument family.
- [`the-smell.md`](./the-smell.md) — **the family rule.** §2.1 there reads instruments
  as consumers with an idiom, never a new channel. Reverse pointer: smell is the
  family's sniff-idiom consumer, never a new channel.
- [`the-spring-caretaker.md`](./the-spring-caretaker.md) — **the family rule.** §2.1
  there reads consumers with an idiom never a new channel; §1.2 the Weatherglass (the
  well's rate read). Reverse pointer: the caretaker is a consumer of the publish with
  a keeping-idiom, never a new channel.
- [`the-migration.md`](./the-migration.md) — **the family rule.** §2.1 there reads
  consumers with an idiom never a new channel. Reverse pointer: the migration is a
  consumer of the publish at people-scale, never a new channel.
- [`the-estuary.md`](./the-estuary.md) — **the family rule.** §2.1 there reads consumers
  with an idiom never a new channel. Reverse pointer: the estuary is a consumer of the
  publish, never a new channel.
- [`the-tutelary.md`](./the-tutelary.md) — **the family rule.** §2.1 there reads
  consumers of the publish never a new channel; §1.4 the sample-at-position pattern;
  §1.3/§5c accessibility. Reverse pointer: the tutelary's reads are consumers, never
  a new channel.
- [`the-midwife.md`](./the-midwife.md) — **the family rule.** §2.1 consumers with an idiom never a new channel; §1.4 the sample-cost profile; §1.2 the Weatherglass. Reverse pointer: the midwife's first read is a bounded consumer.
- [`the-inn.md`](./the-inn.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the inn’s reads are consumers, never a new channel.
- [`the-blizzard.md`](./the-blizzard.md) — **the buried reads.** §1.2 the glanceable forms; §1.4 the sample-cost; §2.1 the family rule (the blizzard’s reads are consumers, never a new channel). Reverse pointer: the white buries the reader’s and Weatherglass’s reads under the driven signal.
- [`the-understory.md`](./the-understory.md) — **the family rule.** §2.1 consumers never a new channel; §1.2 the Weatherglass’s state read. Reverse pointer: the understory’s reads are consumers of the published vertical channels.
- [`the-mirage.md`](./the-mirage.md) — **the family rule.** §2.1 consumers never a new channel; §1.2 the glanceable forms; §1.4 the sample-cost; §5 the honest forms. Reverse pointer: the false-positive lives in the interpretation, never the instrument.
- [`the-mint.md`](./the-mint.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: a coin’s read is a consumer of the publish, never a new channel.
- [`the-orchard.md`](./the-orchard.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the orchard’s reads are consumers.
- [`the-delta.md`](./the-delta.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the delta’s reads are consumers.
- [`the-sledge.md`](./the-sledge.md) — **the family rule.** §2.1 consumers never a new channel; §1.4 the sample-cost; §1.2 the four forms. Reverse pointer: the sledge’s reads are consumers of the publish.
- [`the-raft.md`](./the-raft.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the raft’s reads are consumers.
- [`the-eclipse.md`](./the-eclipse.md) — **the family rule.** §1.2 the glanceable forms; §2.1 consumers of the same publish (the eclipse’s day-reads dim because they consume the dimmed publish); §1.3 accessibility. Reverse pointer: the eclipse-dimmed reads are consumers of the dimmed publish.
- [`the-pooka.md`](./the-pooka.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the pooka’s reads are consumers.
- [`the-chant.md`](./the-chant.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the chant’s reads are consumers.
- [`the-touch.md`](./the-touch.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the touch’s reads are consumers.
- [`the-siren.md`](./the-siren.md) — **the family rule.** §2.1 consumers with an idiom never a new channel; §1.4 the sample-cost; §1.3 accessibility. Reverse pointer: the siren’s reads are consumers, the entrainment never hidden-only.
- [`the-meadow.md`](./the-meadow.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the meadow’s reads are consumers.
- [`the-canal.md`](./the-canal.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the canal’s reads are consumers.
- [`the-cistern.md`](./the-cistern.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the cistern’s reads are consumers.
- [`the-meteor.md`](./the-meteor.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the meteor’s reads are consumers.
- [`the-balefire.md`](./the-balefire.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the balefire’s reads are consumers.
- [`the-baptism.md`](./the-baptism.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the baptism’s reads are consumers.
- [`the-palanquin.md`](./the-palanquin.md) — **the family rule.** §2.1 consumers never a new channel; §1.4 the sample-cost; §1.3/§5c accessibility. Reverse pointer: the palanquin’s reads are consumers, the carried seat never hidden-only.
- [`the-fog.md`](./the-fog.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the fog’s reads are consumers, the blur never hidden-only.
- [`the-drought.md`](./the-drought.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the drought’s reads are consumers.
- [`the-caravan.md`](./the-caravan.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the caravan’s reads are consumers.
- [`the-dune.md`](./the-dune.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the dune’s reads are consumers.
- [`the-terrace.md`](./the-terrace.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the terrace’s reads are consumers.
- [`the-votive.md`](./the-votive.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the votive’s reads are consumers.
- [`the-shrine.md`](./the-shrine.md) — **the family rule.** §2.1 every instrument a consumer, never a new channel; §1.2 the four glanceable forms; §3.1 the sparse far-window underlay. Reverse pointer: the shrine’s register and leavings read through the instruments.
- [`the-lightning.md`](./the-lightning.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the lightning’s reads are consumers.
- [`the-crossroads.md`](./the-crossroads.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the crossroads’s reads are consumers.
- [`the-rumor.md`](./the-rumor.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the rumor’s reads are consumers.
- [`the-generations.md`](./the-generations.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the generations’s reads are consumers.
- [`the-shaft.md`](./the-shaft.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the shaft’s reads are consumers.
- [`the-hand-over.md`](./the-hand-over.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the hand-over’s reads are consumers.
- [`the-seacraft.md`](./the-seacraft.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the seacraft’s reads are consumers.
- [`the-whirlpool.md`](./the-whirlpool.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the whirlpool’s reads are consumers.
- [`the-incantation.md`](./the-incantation.md) — **the family rule.** §2.1 a consumer, never a new channel; §1.2 the Weatherglass’s forms; §1.3 accessibility. Reverse pointer: the incantation is a designed use of the landed mechanics, fully legible, never a hidden rite.
- [`world-difficulty.md`](./world-difficulty.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: world-difficulty’s reads are consumers.
- [`the-tunnel.md`](./the-tunnel.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the tunnel’s reads are consumers.
- [`the-waterfall.md`](./the-waterfall.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the waterfall’s reads are consumers.
- [`the-crane.md`](./the-crane.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the crane’s reads are consumers.
- [`the-comet.md`](./the-comet.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the comet’s reads are consumers.
- [`the-bog.md`](./the-bog.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the bog’s reads are consumers.
- [`the-atoll.md`](./the-atoll.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the atoll’s reads are consumers.
- [`the-anchor.md`](./the-anchor.md) — **the family rule.** §2.1 consumers never a new channel. Reverse pointer: the anchor’s reads are consumers.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers
  (~6 MiB publish, 64³ grid, the ≈ 1–6 ms sample budget, ξ = φ⁶ ≈ 17.94, φ⁻² ≈ 0.382)
  cited, not re-derived.
