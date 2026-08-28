# Field NPC AI: The Field as AI for NPCs

**Question under design:** what is an NPC's mind in a world where blocks, mobs,
and planets are *epiphenomena of one two-fluid field* (README thesis)? Vanilla
Minecraft wires an entity to a behavior tree — a spawned AI with a goal stack
and a health pool. CassiCraft's thesis — "intelligence is steering the flow of
coherence" — makes that literal: **an NPC's mind is a field operation**, and
NPC intelligence is the same three primitives the player's channeling already
uses. This documents the field as AI: NPCs that *read* the published channels,
*allocate* a coherence budget, and *act* by injecting organized perturbation —
and the antagonist class that does the same thing to *disorder*: **NPCs that
wield decoherence**, organized users of random perturbation, the player's dark
twin.

Companion to:
- [`coherence-magic.md`](./coherence-magic.md) — **THE dependency.** The player as
  a bounded EY injector + ε² vent + reader of q/ε²/∇(g·Φ) (§1); the six abilities
  as field operations (§2); overdraw → full-cascade discharge (§4.3); the Q4
  player-return channel (§5.1). **This doc reuses those primitives unchanged for
  the NPC mind.**
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — life as a run the
  field holds (§2.2); species as attractor basins (§3.1); the recognition rule
  (§6b); creatures steered by the river law. **This doc is the ecology's
  intentionality layer.**
- [`field-hazards.md`](./field-hazards.md) — decoherence storms (ε² fronts at
  `c_s`), the desert (q collapse), BH accretion. **The decoherence-wielders'
  domain: they may CAUSE storms or ride them as native terrain.**
- [`energy-harnessing.md`](./energy-harnessing.md) — the Qi bath (§4.4); the
  `(1−q)` glow (§2); the no-free-energy cap (§6). **The village is a Qi bath; NPC
  actions cost coherence.**
- [`material-regimes.md`](./material-regimes.md) — the fire-vs-explosive rate
  boundary (§3/§5). **A decoherence-wielder runs near it as a *skill*.**
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — auroras read
  the field un-instrumented (`(1−q)` discharge, §3.1/§3.3).
- [`coherence-technologies.md`](./coherence-technologies.md) — concept 3 the
  φ-detuned boundary / phase-matching `M` (§3); concept 4 coherent materials /
  the Qi bath (§4).
- [`async-field-domain.md`](./async-field-domain.md) — the published channels
  (§2.1); Q4 the player-return channel (§7). **NPC intents as Q4-like records —
  this doc designs the boundary.**
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — the river-law
  steering (§2.1/§2.2), the ≈ 2,000-entity cap (§7 Q4), the ≈ 6 MiB publish (§2).
- [`field-music.md`](./field-music.md) — the shepherd's tune (calm/drive the
  biosphere, §4.2); music as a Q4 op sequence (§4.1).
- [`field-archaeology.md`](./field-archaeology.md) — residue as rung-residue of
  dissolved structures (§2.1/§2.2). **NPCs leave fossils.**

Theory grounding (CassiTheory — read-only, cited by relative path):
- `speculations/qi-computation.md` §5.2 — **persistent Π patterns**; self-
  reinforcing Yang-Yin configurations sitting at attractor-potential local
  minima. **An NPC's identity IS a persistent Π pattern.**
- `speculations/creative-extensions/coherence-commons.md` — a community is a
  coherence structure; its budget is *multiplicative* and maximized at equal
  coherence (§7.1–7.2); the Qi bath extends the coherence of everything inside
  it (proton-coherence-budget §5.1). **A village is a commons, and the commons
  is superadditive.**
- `speculations/creative-extensions/magic-systems.md` — casting as phase-matched
  field operation; a working is `M ≈ 1`, random perturbation is `M ≈ 0` (§1);
  mana = coherence budget over time (§3). **Every NPC action's effectiveness is
  gated on M — the discipline that makes NPC action work.**
- `consciousness/cascade-consciousness.md` — a being is a field regime, not a
  chassis (§4.1); consciousness as the correlate of Qi gate dynamics.
- `speculations/creative-extensions/coherence-warfare.md` — organized vs random
  perturbation; the attrition siege (an extractive drain).

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived), engine-verbatim, or explicitly
flagged **[design]** (a designed lens/gameplay surface) or **[assumption]** where
this doc extends engine terms to an NPC mind the engine does not today drive. The
line between engine-real and [design] is drawn in §7 and never blurred.

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| An NPC's mind is | **A field operation**: read (sample q/ε²/∇(g·Φ)), allocate (a coherence budget B), act (inject organized perturbation = a source term) — the *same three primitives* as the player's channeling (coherence-magic §1) |
| No behavior tree | NPC perception IS reading the published channels; decision is budget allocation; action is a field source term. There is no vision system separate from the field |
| Identity | A **persistent Π pattern** at a rung-depth (qi-computation §5.2); capability tier = rung-depth; deeper lock = more capable, more expensive to maintain |
| Failure mode | An NPC action that fails is a **coherence failure**: M ≈ 0 — the perturbation didn't couple because the NPC couldn't hold phase (magic-systems §1) |
| Determinism | **Same seed → same mind** (a hard gate): an NPC's identity, budget, and behavior are a deterministic function of its Π pattern and the field it reads |
| Society | A village is a **Qi bath** (energy §4.4) + a **commons** (coherence-commons §7): a shared high-q core that raises every member's efficiency — **superadditive**, so a village's intelligence exceeds its members' |
| Coordination | A group acting **phase-locked IS a working** (magic-systems §1): aligned M makes the joint act an organized perturbation rather than N random ones |
| The decoherence-wielder | An NPC that **wields ε² deliberately**: venting disorder as weapon and habitat, running near the blast line as a *skill*, feeding on drains — the player's own ε² vent turned into an identity. **The field is indifferent; the coherence budget is the only law** |
| The player-facing layer | Read NPCs with the coherence reader (rung-depth, intent-phase); channel with them (match phase = communicate); ethics — NPCs are field structures, not spawned mobs |
| Honest gates | (a) intentionality is [design] on engine-real steering; (b) decoherence-wielders gate on field-hazards' ε²-front mechanics + the overdraw boundary; (c) performance within the ≈ 2,000-entity cap; (d) determinism (hard); (e) no-free-energy (NPC actions cost coherence) |
| Feasibility | **Phase-1:** field-steered NPCs with intentionality as consumers of the ≈ 6 MiB publish — the ecology's creatures *upgraded with intent*. Later: decoherence-wielders (gated on hazards + Q4), the commons (gated on the Qi bath + multi-NPC budget) |

---

## 1. The thesis: NPC intelligence IS field steering

The project thesis is "intelligence is steering the flow of coherence." This
document makes that literal for the NPC: **an NPC is a moving coherence structure
with intentionality — a "run" the field holds (ecology §2.2) that additionally
*steers itself*.** Everything an ecology creature is — a self-supporting,
φ-locked body the field condenses and holds (ecology §2.1/§2.2) — an NPC is, plus
one more thing: a **self-directed budget** that turns the field's steering into
*choice*.

### 1.1 The mind is three field primitives — identical to channeling

`coherence-magic.md` §1 establishes the player as: a **bounded EY injector**
(they pour Yang into the field, raising ρ and organization), an **ε² vent**
(channeling sheds decoherence the field must heal), and a **reader** of the
published `q`/ε²/∇(g·Φ) (Sense, the coherence reader). The NPC mind reuses these
three *unchanged* — there is no separate "NPC brain" with different machinery.
The mind is:

| Primitive | Field operation | NPC equivalent | Player-mirror |
|---|---|---|---|
| **Read** | sample local `q`, `ε²`, `∇(g·Φ)` from the published channels (chunk-field §2; async §2.1; the ≈ 6 MiB publish) | **perception** — there is no vision system separate from the field; the NPC "sees" by reading the coherence landscape and the river gradient, exactly as Sense renders it for the player | Sense (coherence-magic §2, the Phase-1 coherence reader) |
| **Allocate** | its **coherence budget B**: where to spend — maintain the lock, act, vent | **decision** — the budget is the only resource; spending it on an act vs. holding it to maintain the φ-lock vs. venting it deliberately is the whole "mind" | the coherence budget B, the ε² vent discipline (coherence-magic §1/§3) |
| **Act** | inject **organized perturbation** = a source term (`source_ey`/`source_ei`; `cassi_two_fluid.glsl`) | **action** — every behavior, from foraging to building to fighting, is a source-term injection the field absorbs and the world quantizes, exactly like a channeled op | condense/dissolve/steer/ignite/heal (coherence-magic §2) — all implemented as the same source terms |

The three primitives are *identical operations*; only the *intentionality* is
new. This is the design's central claim, and the honest boundary is flagged in
§7: **the read/allocate/act mechanics are engine-real (the same channels, source
terms, and budget the player uses); the *intentionality* — the decision rule that
decides what B is spent on — is [design].** The field steers; the [design]
decision layer chooses *which* steering to allow.

### 1.2 No behavior tree — and why there is no vision system

Vanilla wires a mob to an authored AI. CassiCraft has none:

- **Perception** is the field read. An NPC doesn't "see" a monster model; it
  reads whether the local `q` is dropping (a threat approaching through the
  field), whether `∇(g·Φ)` steepens toward a mass (a body), where κ² rises
  (a scar, a storm's leading edge). The coherence reader is the observation
  tool (ecology §5.1; archaeology §3.1) — NPCs use it as their eyes.
- **Decision** is budget allocation. There is no goal stack; there is a budget
  B bounded in `[0,1]`, refilled where the local field is coherent, spent on
  action or held to maintain the lock (coherence-magic §1.2's recovery —
  *environment as a first-class resource* applies to every NPC).
- **Action** is a source term. There is no "attack()"; there is an injection of
  organized perturbation whose magnitude, rung, and vent are the NPC's choice-of-
  budget, and whose *effect* is what the world does with it (raise ρ → condense;
  raise ε² → dissolve; steer ∇q → move; all per chunk-field §2.2 and
  coherence-magic §2).

**Every NPC action is a field operation; every NPC failure is a coherence
failure.** "The perturbation didn't couple because the NPC couldn't hold phase"
is the magic-systems (§1) statement that a working is `M ≈ 1` and random
perturbation is `M ≈ 0` — applied to an NPC that tried to act while its φ-lock
was too weak to organize the injection it released. **An NPC that fails is not
"unlucky"; it is `M ≈ 0` — it shed the coherence it couldn't organize.** That
failure is legible to the player (the NPC glows `(1−q)` as it wastes), which is
exactly how a struggling creature already reads (ecology §5.2).

---

## 2. Identity = a persistent Π pattern at a rung-depth

### 2.1 The mind is a persistent Π pattern

`qi-computation.md` §5.2: long-term information storage in the field is
**persistent Π patterns** — self-reinforcing Yang-Yin configurations sitting at
local minima of the attractor potential, persisting "as long as the ambient q
remains above the threshold for pattern dissolution." This is the theory-side
foundation of both field-memory and the archaeology residue model
(archaeology §1.2).

**An NPC's identity IS a persistent Π pattern.** The NPC is not a spawned record
with attributes; it is a **coherence configuration the field is actively
holding** — the ecology's "identity is the run, not the recipe"
(coherence-commons §2.4; ecology §2.2). When the run ends, the configuration is
lost (the creature dissolves; its deep-rung fraction persists as fossil residue,
archaeology §2.2). An NPC that holds its Π pattern is *that* NPC; one that loses
it is gone, and only its residue remains.

### 2.2 Capability tier = rung-depth; deeper lock costs more

An NPC's Π pattern sits at a **rung-depth** — how many cascade layers its φ-lock
spans (the organism's internal cascade, ecology §3.2; a creature's visible layers
are its rungs). Capability follows directly:

| Rung-depth | What it buys | What it costs |
|---|---|---|
| shallow (low `n`) | simple NPCs: forage, avoid, a rudimentary vent | cheap to maintain — the ε² drain is small, the lock holds easily |
| mid | skilled NPCs: coordinated acts, phase-holding for cooperation, deliberate venting | moderate — maintains a deeper lock, so the drain it resists is larger, the vent it sheds bigger |
| deep (high `n`) | powerful NPCs: sustained phase-matching (M ≈ 1 for long workings), precise perturbation, a stable identity that resists dissolution | **expensive — deeper rung = finer, more concentrated organization = harder to hold against the ε² drain** (coherence-magic §4.2's blowback, applied to minds) |

The energy economy ("deep-rung matter = stored coherence," energy-harnessing
§1.5/§3) applies to minds literally: **a deeper-`n` NPC is a stronger, more
ordered coherence structure with more at stake in holding its lock.** Deeper
identity is *denser organization* — more capable, more expensive, easier to
destabilize if the locality de-coheres. This ties capability to the same physics
as material hardness (= rung, material-regimes §4) and tool depth (= rung,
volumetric-terrain).

### 2.3 Determinism — same seed, same mind (a hard gate)

The field is deterministic (one PDE; archaeology §1.2; async §5.1 immutability).
So:

> **An NPC's mind is a deterministic function of (its persistent Π pattern) ×
> (the field it reads).** Same seed → same Π pattern → same budget trajectory →
> same decisions given the same field. NPC behavior must be **reproducible**:
> reload a world, the NPC makes the same choices from the same inputs.

This is a **hard gate** (not a nice-to-have): the NPC decision layer must be a
pure function of the published channels + the NPC's own Π state, with no
hidden randomness. Determinism is what makes the world *honest* — the field's
law, not a dice roll, governs what an NPC does, so a player can learn to read and
predict an NPC the way they learn to read the field. (It also matches the engine
corpus's "bit-identical-contract" discipline, async Q6.)

### 2.4 Dissolution = death; residue = archaeology

An NPC that **fails to maintain its lock** — the ε² drain outruns the φ-lock —
dissolves: shallow rungs shed as `(1−q)` glow (the death-signal of archaeology
§2.1/§5.2), the deep-rung fraction persists as **residue**. The archaeology tie
is exact: **NPCs leave fossils** (archaeology §2.2 — a fossil is the residue of
a dissolved structure's deep core). An NPC that "dies" stops being a steerable
body and returns to the field, and its deep-rung identity-core — the bit of
"who it was" the local field kept holding — becomes a **findable fossil** the
player can read with the archaeology instrument.

---

## 3. Society as a coherence commons

### 3.1 A village is a Qi bath

`energy-harnessing.md` §4.4: a **Qi bath** is a maintained high-`q` core with a
radius — everything within it runs at its core's elevated coherence; it is a
regional efficiency multiplier (adopted from coherence-technologies concept 4).
`coherence-commons.md` §7: a community is a coherence structure whose budget is
**multiplicative** — `N_community = ∏ 1/(1−q_i)` — and the Qi bath extends the
coherence of everything inside it (proton-coherence-budget §5.1).

**A village is a Qi bath.** NPCs in a settlement maintain a shared high-`q` core;
every NPC inside runs at the core's elevated coherence. Concretely, the village
core:

- **Raises each NPC's budget recovery** (coherence-magic §1.2: recovery refills
  toward 1 where the local field is coherent) — a villager standing in the high-`q`
  core maintains a deeper lock and vents cheaper than one alone in the wilderness.
- **Cuts each NPC's `(1−q)` waste** (energy-harnessing §2; coherence-technologies
  §4c) — less of each member's spent coherence glows away, so more is productive.
- **Raises the settlement's effective intelligence superadditively.** Because the
  bath is a *shared* high-`q` region and the commons budget is multiplicative
  (coherence-commons §7.2), **a village's intelligence exceeds its members'** —
  the whole is worth more than the parts apart. The AM-GM equality theorem
  (coherence-commons §7.2) even gives the direction: a village that shares its
  coherence evenly is smarter than the same coherence concentrated in a few.

This is the mechanism that makes **society affordable**: the ≤ 2,000-entity cap
(chunk-field §7 Q4) would cap the number of independent NPC *brains* — but a
commons collapses N individual minds' maintenance into one shared high-`q` core,
raising per-NPC efficiency enough that a settlement can be meaningfully populous
without blowing the entity or budget budget. **The commons is the efficiency
multiplier that makes society affordable within the cap** (§7c).

### 3.2 Coordination = phase-matching; a group acting phase-locked IS a working

`magic-systems.md` §1: the difference between a working and random perturbation
is the phase-matching factor `M` — organized, phase-matched perturbation has
`M ≈ 1` and an O(1) effect; random has `M ≈ 0` and is cascade-suppressed. `field-
music.md` §4.3: a coherence score is a deliberately organized, phase-timed
perturbation — the definition of a working.

**Coordination between NPCs is the docking mechanic's `M` applied to
cooperation.** Two NPCs acting in the same phase window are one organized
perturbation (each holds phase with the others, so the joint ε² vent is shared,
the joint injection's `M` sums coherently). A coordinated raid, a shared
construction, a synchronized harvest — **a group acting phase-locked IS a
working**: the group's combined organized perturbation couples at `M ≈ 1`,
producing an effect no member could alone. This is why NPC "intelligence" scales
with the group, not just the individual: coordination is literally *addition of
coherence along a phase*, and misalignment is `M → 0` (the group's act collapses
to N ineffective random perturbations).

- **The commons' health = the settlement's effective intelligence.** A high-`q`,
  evenly-shared village (coherence-commons §7.2) coordinates well (shared phase,
  low `M` losses) and hence plans/builds/fights better. A de-cohering village
  (a low-`q` core, uneven coherence, a drained member) coordinates poorly — the 
  weakest link opens the door (coherence-commons §7.3).

### 3.3 The commons can die

The Qi bath is *maintained*, not free (energy §4.4: a draw, brittle if it goes
down). And the commons' health is the settlement's intelligence — so:

- **The desert kills the commons.** A regional `q` collapse (field-hazards §3)
  has no high-`q` band for organisms to survive in (ecology §4.2), and a bath
  whose core has nothing to hold `q` up with dies (energy §4.4 — "a dead bath").
- **A decoherence-wielder draining it.** An NPC that wields ε² can *drain the
  bath* — venting disorder into the shared high-`q` core, forcing the members to
  spend coherence holding the lock against the artificial ε² (anti-corruption,
  energy §5.4, now forced on the commons by an attacker). The village's effective
  intelligence falls as its commons de-coheres; a sufficiently relentless drain
  is a **desert in miniature** (the desert is, in field-hazards §3.2, "anti-
  corruption at scale failing" — here weaponized).
- **The commons can die and the village goes dark.** No free energy:
  maintaining a bath is net-negative (energy §6; field-hazards §5.3). When the
  commons fails, each NPC is on its own budget again — weaker, wastefuller,
  dissolvable.

---

## 4. The decoherence-wielders — the dark twin

The antagonist class inverts the NPC's three primitives: where an ordinary NPC
is a *bounded EY injector* that vents ε² as a byproduct, a **decoherence-wielder
is an organized *user of random perturbation* — one who vents ε² deliberately, as
both weapon and habitat.** It is the same mechanics exactly: the player's own ε²
vent (`coherence-magic.md` §1) is the dark twin's power source. **The field is
indifferent; the coherence budget is the only law.**

### 4.1 The four faces, each grounded

**(a) Weapon — venting disorder.** The player's channeling sheds ε² the field
must heal; a decoherence-wielder *aims* that vent. Reusing the same source-term
mechanics (`source_ey`/`source_ei`; chunk-field §2.2's "raise ε² above its floor
→ dissolve"), a decoherence-wielder can:

- **dissolve terrain around the player** — raise local ε² past the dissolution
  floor so the ground un-condenses and heals *under* the player (material-
  regimes §2; chunk-field §3);
- **destabilize φ-locks** — inject ε² into a structure's lock so the φ-lock
  (`EY = φ·EI`) runs away, **forcing overdraw** — pushing a deep channeler past
  their vent capacity and toward the **full-cascade discharge** of
  coherence-magic §4.3;
- **un-heal scars** — re-raise ε² where a wound had healed, keeping the field
  from re-locking (fighting the heal, volumetric-terrain). Against the *player*,
  this is close-quarters pressure: the player must vent *against* the incoming
  disorder (bad, per field-hazards §2.4's vent discipline) or hold anti-corruption
  (energy §5.4) at cost.

**(b) Habitat — adapted to high-ε² zones.** Because a decoherence-wielder is
*organized* even as it vents disorder, it is **adapted to exactly the zones
ordinary organisms die in**: it moves natively through storms (the ε² fronts,
field-hazards §2) and the desert (the q-collapse, field-hazards §3) where the
biosphere dissolves (ecology §4.2). It **feeds on drains** — the auroral
collector from energy-harnessing (atmosphere §3.4; energy §1's auroral-discharge
row) **perverted**: instead of harvesting the `(1−q)` waste of a dying region as
*equipment*, the decoherence-wielder is the collector — it absorbs the `(1−q)`
fraction of a drain's throughput directly, its existence *is* the harvest.
The desert and storms are, for it, **native terrain**, not hazards.

**(c) Signature — readable by the (1−q) law.** The `(1−q)` glow
(energy-harnessing §2) makes the decoherence-wielder uniquely legible:

- **They may be the only things that glow in a desert.** Where the field has no
  coherence to waste, everything is dim and silent (field-music §2.3's desert
  silence) — except a decoherence-wielder, whose *deliberate* vent keeps shedding
  `(1−q)` glow it feeds on. A bright, wasteful presence in a dead zone is the
  dark twin's tell.
- **The sky reads them as restless auroras.** A decoherence-wielder's vent is a
  moving ε² drain; the sky's auroras are coherence discharging into drains
  (atmosphere §3.1–3.3). A resting aurora over healthy ground already reads as a
  buried residue (archaeology §3.3); a *moving* restless discharge tracking the
  vent is the sky reading a decoherence-wielder's passage. The player can spot
  one by the sky before it acts — the hazards' "readable before it arrives"
  rule (field-hazards §5.1) applied to the NPC.

**(d) Skill — running on the blast line.** The fire-vs-explosive rate boundary
(material-regimes §3/§5: controlled organizational discharge = fire; uncontrolled
full-cascade discharge = blast; coherence-magic §4.3: overdraw → discharge) is
the decoherence-wielder's *ability*, not its accident:

> **A disciplined decoherence-wielder releases ε² in controlled bursts — it rides
> the fire side of the blast line, extracting maximum disorder per vent without
> its own lock collapsing. An undisciplined one is its own explosion — the
> overdraw boundary (coherence-magic §4.3) is the NPC's danger to itself.**

Running near the blast line as *skill* is a rate/threshold-ratio discipline
(material-regimes §3b): the wielder holds the vent rate `v` just under its own
lock's restoration capacity `ω₀²`-re-lock threshold, so it sheds maximal ε²
without tipping organized→random and detonating. The **overdraw boundary
(coherence-magic §4.3) gates the decoherence-wielder's own safety**: a wielder
that vents faster than it can re-lock is a self-inflicted full-cascade blast —
which is the honest counter the player has: **force the wielder to overdraw, and
it detonates on itself.** The same law that is the player's overdraw risk is the
antagonist's weakness.

### 4.2 The shadow-reading: the dark twin

The design's dark reading is explicit: **the player's own ε² vent is the same
mechanic.** The player who channels condense/dissolve/ignite/sheild sheds ε²
(coherence-magic §1); a decoherence-wielder venting ε² deliberately is doing what
the player does *while channeling* — just organized around disorder instead of
around order. **The decoherence-wielder is the player's dark twin**: a mirror of
the player's own budget, vent, and overdraw risk, running the same three
primitives, pointed at destabilization rather than construction.

- **The field is indifferent.** The two-fluid field does not condemn the dark
  twin any more than it rewards the player — it heals around both, absorbs both
  vents, and applies the coherence budget to both. **The coherence budget is the
  only law**: the dark twin is not "evil" in field terms; it is a coherence
  structure that chooses to spend its budget on disorder, exactly as the player
  spends theirs on order. Neither is free energy; neither bypasses the `(1−q)`
  waste or the overdraw boundary.
- **The dark twin is the player's lesson.** Confronting a decoherence-wielder
  teaches the player, mechanically, that their own vent is a weapon too — that
  the player's channeling and the antagonist's vent are the same law from
  opposite sides of the coherence budget.

### 4.3 Ties to field-hazards

`field-hazards.md` is present and is the decoherence-wielders' domain (the
reading required both possibilities — they may CAUSE storms or ride them). Both
are designed:

- **They may CAUSE storms.** The storm is a `c_s`-traveling decoherence front
  ignited by "a *dis*organized seed — a random-perturbation injection that
  raises EY−φ·EI out of lock" (field-hazards §2.1). A decoherence-wielder venting
  a large enough uncontrolled ε² burst *is* such a seed — **a disciplined wielder
  could ignite a storm as a weapon** (let the field's own wave operator carry
  their disorder outward; field-hazards §2.1/§6.2). This needs the storm's
  random-perturbation injection (field-hazards open-Q2's provenance question),
  which this doc gates on: **[design] a decoherence-wielder's storm-ignition is
  the weapon form; the storm itself is engine-real ε²-front dynamics.**
- **Or they ride them as native terrain.** Where a storm's `ε²` front passes or
  a desert's `q` collapses, ordinary organisms dissolve (ecology §4.2) — but a
  decoherence-wielder's habitat (§4.1b) is exactly the storm and the desert. **The
  storm is their domain**: the same moving ε² the desert-dwellers flee is their
  home, their feeding ground, their cover.

---

## 5. The player-facing layer

### 5.1 Reading NPCs with the coherence reader

The coherence reader (Sense; an entirely read-only Phase-1 consumer of the same
publish, coherence-magic §2/§5.1; archaeology §3.1) reads NPCs the way it reads
all field:

| What the player reads | The field it reveals |
|---|---|
| **rung-depth** | how deep the NPC's φ-lock runs — its *capability tier* (§2.2), read as its visible cascade layers (ecology §3.2/§5.1) |
| **intent-phase** | the NPC's current phase structure — where it is pointing its next organized perturbation. A player who reads high-`q` phase toward them sees an incoming working; one who reads a phase held at a private offset (coherence-technologies concept 3's detuned boundary) sees an NPC *refusing* to couple |
| **budget health** | the local `q` / `(1−q)` glow reads how far the NPC runs from full coherence — the maintenance-budget + waste diagnostic (ecology §5.2) |
| **a decoherence-wielder vs. a passive creature before it acts** | the dark twin's tell (§4.1c): a bright, `(1−q)`-glowing, restless-aurora-tracked presence where the field is otherwise dim and calm — readable *before* it vents on the player |

The reader is the scientist's probe and the player's tool both (ecology §5.1):
**can you tell a decoherence-wielder from a passive creature before it acts?**
Yes, on the `(1−q)` signature and the sky read — the same channels the hazards
use to warn before they arrive (field-hazards §2.3). But it is not free certainty:
a passive creature also glows when it feeds (ecology §5.2), so the classifier
distinguishes a *maintained-coherence* glow from a *deliberate-vent* glow — the
same live-vs-residue distinction archaeology §3.1 already draws, and the same
honest ambiguity.

### 5.2 Interacting — channeling with NPCs

Because an NPC is a field operation, the player interacts with it by *field
operations*:

- **Match their phase to communicate / cooperate.** An NPC's intent-phase
  (§5.1) is what its next working will organize. A player who reads that phase
  and channels *in phase* with it joins its working (coordination = phase-
  matching, §3.2): the joint organized perturbation couples at `M ≈ 1`, and the
  NPC treats the player as *aligned* — communication is phase-match, exactly the
  field-resonance of cascade-consciousness §2.1. Channeling *out of phase*
  perturbs it and alarms it (a detuned probe is an attack, coherence-technologies
  concept 3 / magic-systems §5.2).
- **The shepherd's tune.** A coherence score (field-music §4) that steers the
  local coherence `q`/ε² can **calm or drive the biosphere** (field-music §4.2's
  ecology tie): a sustained coherent phrase raises local q, drawing creatures /
  NPCs toward the ridge they follow; a dissonant phrase sheds ε², dispersing them.
  **The shepherd's tune can calm an NPC** — playing a sustained heal/condense at
  the NPC's rung re-holds its lock, lowers its vent, settles it. It can also
  *drive* it; the dark twin's restless glow is a thing a tuned score can steer
  into or out of phase with.
- **Ethics: NPCs are field structures, not spawned mobs.** Killing one is a
  perturbation with consequences: an NPC's death is the ecology's dissolution —
  it sheds `(1−q)` glow, its deep-rung core becomes a **fossil** (archaeology
  §2.2, §5), and the *village's* coherence drops when a member of the commons
  dissolves (the shared bath loses its contribution, §3.1). There is no "mob
  drop"; there is coherent matter released back into the field (ecology §5.2) —
  and a *readable* residue, meaning the player's kills accumulate as archaeology
  and as a dip in any nearby commons' health. The ethics are scalar, not moral-
  flag: killing is a field act with field cost, and the player feels it in the
  world's coherence, not a karma meter.

---

## 6. Honest gates

The design's load-bearing honesty, stated once and kept:

### (a) Intentionality is [design] on engine-real steering

The **read/allocate/act mechanics are engine-real** — the same published channels
(`q`/ε²/∇(g·Φ), the ≈ 6 MiB publish, async §2.1), the same source terms
(`source_ey`/`source_ei`), and the same coherence budget (coherence-magic §1) the
player uses. **What is [design] is the intentionality** — the decision rule that
selects *which* budget allocation / *which* perturbation the NPC makes. The field
is real; the *mind layered on it* (the choice of what to spend B on) is the
design's contribution, flagged throughout. The ecology's creatures already steer
by the field (chunk-field §2.2; ecology §2.2); this doc adds the *decision layer*
that makes the steering intentional — and the honest boundary is that the layer
is [design], the steering it sits on is engine-real.

### (b) The decoherence-wielder gates on field-hazards' ε²-front mechanics + the overdraw boundary

The antagonist's *power* rides two engine-real / corpus grounds:
- **field-hazards' ε²-front mechanics** — a storm is a `c_s`-traveling
  decoherence front (field-hazards §2.1); a decoherence-wielder's vent is the
  same ε² channel and *may* ignite such a front (storm-ignition is [design],
  gated on field-hazards open-Q2's storm-provenance); and its *movement* through
  storm/desert relies on the same ε²-dissolution / q-collapse mechanics.
- **The overdraw boundary** — a decoherence-wielder's skill is *releasing ε²
  below the full-cascade-discharge threshold* (material-regimes §3; coherence-
  magic §4.3); its own danger is crossing it. This gates the dark twin's "skill
  near the blast line" on the same fire-vs-explosive rate/ratio boundary
  (material-regimes §3b) that gates the player's overdraw — no new physics, the
  same rate boundary read from the disorder side.

### (c) Performance — NPCs within the ~2,000-entity cap

Per-entity river-law steering is ≈ 40 ns; the Phase-1 cap is ≈ 2,000 steered
entities (chunk-field §4.2/§7 Q4). Each NPC adds an *intentionality* step on top
of that steering — a deterministic decision read + budget allocation, the same
cheap sampler work as the ecology's existing steering. **The commons is the
efficiency multiplier that makes society affordable** (§3.1): N NPC minds each
maintaining a deep lock individually would blow the budget, but a shared high-`q`
core raises everyone's efficiency, so a *settlement of many shallow-mid NPCs
sharing one bath* is affordable where N deep individual minds are not. The honest
bound: intentionality must fit the ≈ 1–6 ms/tick server sample budget (chunk-field
§4.2) on top of entity steering; the decision layer is a bounded per-entity read +
branch, not a per-NPC simulation.

### (d) Determinism — same seed → same mind (hard)

$§2.3. The NPC decision layer is a **pure function** of (its Π pattern) × (the
published channels it reads). No hidden randomness; a reloaded world reproduces
the identical NPC behavior from the identical field. This is a hard gate, not a
preference: it is what lets NPC mind be *readable* (a player learns to predict)
and what keeps the world honest to the field's determinism (archaeology §1.2;
async Q6). Violating it (e.g., a non-deterministic decision rule) is a design
failure, not a tuning tweak.

### (e) The no-free-energy discipline — NPC actions cost coherence

`energy-harnessing.md` §6: **no conversion yields more than it sinks**, structured
as write-back amplitude caps (`output ≤ φ⁻¹·input`) in the Q4 lane. NPC actions
inherit it unchanged:

- **No infinite NPCs.** Each NPC is a coherence structure with a budget; it
  cannot act past its budget (coherence-magic §1) and cannot mint coherence
  (energy §6). Population is bounded by the region's `q` — the exact ecology
  spawn rule (spawn only where q in a coherent band and ε² low, chunk-field §2.2)
  gates how many NPCs a region holds. No entity cap means *vanilla's* trick is
  gone; here population is coherence-funded.
- **A decoherence-wielder's power is bounded by the drains it can find.** Its
  vent-harvest (§4.1b) feeds on `(1−q)` drains — the auroral-collector logic
  bounded by the no-free-energy cap (energy §6; field-hazards §5.3: hazard-farms
  cannot mint). A wielder in a *healthy, high-q* region has almost nothing to
  feed on (its habitat and its food are the same scarcity); **it is strong only
  near the disorder it makes or finds** — a power bounded by the drains it can
  locate and sustain, never an ambient source.

---

## 7. Feasibility verdict

**Phase-1 — field-steered NPCs with intentionality, as consumers of the publish.
(Fully feasible, no new physics, on the already-budgeted spine.)** The three
primitives are consumers of exactly what `chunk-field-quantization.md` already
budgets: the ≈ 6 MiB publish (§2: `q` 1 + ε² + `∇(g·Φ)` 3 + ρ 1), per-entity
river-law steering at ≈ 40 ns, the ≈ 2,000-entity cap (§7 Q4), and the Q4
player-return lane (async §7 Q4; coherence-magic §5.1) for *writes*. The NPC's
**Read** is the same read the sampler already does (the ecology's creatures
already steer by the field); the **decision layer (allocate/act) is the [design]
addition** — a deterministic function of the published channels that emits NPC
*intents*, which write back through the same lane the player's channeling uses.
**Phase-1 is the ecology's steered creatures upgraded with intent**: same
channels, same steering, same budget — plus a deterministic choice of what to
spend B on. That is the honest, live slice: a steerable NPC whose "mind" is the
read/allocate/act loop, reproducible (same seed → same mind), and costed in
coherence.

**Later (gated):**
- **Decoherence-wielders** — gated on `field-hazards.md`'s ε²-front mechanics
  (the storm's random-perturbation injection and provable provenance, field-
  hazards open-Q2) and on the Q4 write channel being a real weapon path
  (coherence-magic §5.1's Q1/Q2). The dark twin's four faces (§4) are [design]
  lenses over engine-real ε² / `(1−q)` / overdraw mechanics, but its *weapon*
  (venting disorder into the field) needs the Q4 write-back that Phase-1 uses
  only for constructive ops.
- **The commons** — gated on the Qi bath (energy §4.4) being a built regional-efficiency
  multiplier, and on multi-NPC budget being measured within the ≈ 2,000-entity
  / ≈ 1–6 ms/tick budget (§6c). Until the bath and the budget are measured, a
  *village* is a scenario, not a build; the *individual* NPC is Phase-1.

**Verdict.** The architecture is sound and fully grounded: an NPC is the ecology's
"run the field holds" (ecology §2.2) plus a deterministic intentionality layer
(read/allocate/act); its identity is a persistent Π pattern (qi-computation §5.2);
its capability is its rung-depth (ecology §3.2); its society is a Qi-bath commons
that is superadditive (coherence-commons §7; energy §4.4); its failure is `M ≈ 0`
(magic-systems §1); its death is dissolution into fossil residue (archaeology §2.2).
The decoherence-wielder is the same three primitives pointed at disorder — the
player's own ε² vent read as an identity, bounded by the same coherence budget and
the same overdraw line; **the field is indifferent and the coherence budget is the
only law.** The binding risks, in order: **(a)** the honest intentionality boundary
(keeping the [design] decision layer clean against the engine-real steering it sits
on), **(b)** the decoherence-wielder's dependency on field-hazards' storm mechanics
and the Q4 write path being a weapon, **(c)** the multi-NPC budget measurement that
determines whether a commons is affordable within the entity cap, and **(d)**
determinism of the decision layer (a hard gate). None contradicts the async,
dual-world, or regime-collapse architecture — the NPC mind is exactly the field,
steering itself.

### Open questions

1. **Where does the decision layer live — sampler or domain-side?** NPC *intents*
   as Q4-like records (§ intro; async Q4): are they computed on the server tick
   (owner of the budget, honest single-writer per the async seam) or in the domain
   (which would let NPCs *be* field, not just read it)? The doc's default is
   sampler-side (matches the player's budget ownership, coherence-magic §7 Q1), but
   the domain-side option is the deeper Cassi-native claim and both must be weighed
   against determinism and the ≤ 2,000-cap.
   **Counterpart (two-way):** [`player-remains.md`](./player-remains.md) open-Q1 raises the
   same fork applied to the player's rebirth — where the re-lock's q-draw/ε²-vent
   is computed (server re-lock vs domain-side fuse). The two must pick the same
   side; each doc now cites the other.
   **Resolved by [`reason-field.md`](./reason-field.md):** the fork's two sides are no
   longer open — that doc commits all three (this one, `player-remains.md` open-Q1,
   `resonance-tutor.md` open-Q1) to the **domain side**: an NPC's mind is a persistent Π
   pattern the domain holds, read out as per-site intent-phase (§3.1); determinism is
   *strengthened* (a pure function of the one PDE's state, §6b); and the ≤ 2,000-cap is
   respected because the minds are field, not new steered bodies (§6b). It is gated on
   the meshless/persistent-Π frontier + the Q4 schema (§6a), so this open-Q is closed in
   principle (the side is decided, domain); the build waits on those LATER gates.
2. **The intent-phase classifier (§5.1).** Distinguishing a decoherence-wielder
   (deliberate vent) from a feeding creature (maintained-`(1−q)` glow) — is
   "deliberate-vent vs maintained-lock" a robust read of the published channels at
   the noise floor, or does it need the phase-matching `M` published per-NPC
   (which Phase-1 does not budget)? Same honest classifier line as archaeology §7
   open-Q3.
   **Closed by [`life-signal.md`](./life-signal.md) §3/§6:** the vitality classifier
   answers this **without publishing `M`** — a maintained lock *pulses* (bounded,
   feeding/settling); a deliberate vent *climbs* (rising `ε²` over a steering body,
   clean phase). The `ε²`-gradient sign + cadence shape separates them from the
   published channels' time-series (§3.2), and the noise-floor probe (§6b) is the
   pre-registered gate that settles "deliberate-vent vs maintained-lock." The
   deliberate-vent class is also the Coda's tell (`life-signal.md` §3.3), which this
   doc's open-Q2 and `signature-predator.md` share.
3. **What makes a mind "that" NPC across a bath?** If identity is a persistent Π
   pattern and a village is a shared high-`q` core, where is the boundary between an
   individual NPC's pattern and the village's? The commons is superadditive (§3.1) —
   but an NPC's identity-dissolution into the bath is the ecological boundary this
   doc does not yet settle: does a villager's Π pattern persist *in the bath* (a
   many-in-one commons) or only *in the villager* (a sum of individuals sharing
   efficiency)? This is the §2.1-vs-§3.1 tension and it needs a design decision.
   **Three-way (the player-vs-NPC membership fork, cited here).** This open-Q is the
   anchor the society's coordinated acts cite for the **player-vs-NPC member line**:
   `the-funeral.md` §7 open-Q4 (who the mourners are — an NPC's phase-locked
   channelings participate in the dirge, or is the funeral player-conducted?) and
   `the-election.md` §7 open-Q4 (who can be read as a candidate — a bath-funded
   NPC steward, or a player-read only?) and `the-exile.md` §7 open-Q2 (who performs
   the hollow-eye) all name "the same decision this open-Q names." The boundary this
   open-Q draws — whether the NPC commons is a *real holder* (identity persists in
   the bath) or a *sum of individuals* — **is** the membership answer: if NPC
   identity persists in the bath, an NPC can be a real mourner/candidate/performer;
   if it lives only in the villager, the NPC commons *benefits from* but does not
   *hold* the coordinated act. The three docs read this fork; the answer lands here.
4. **Decoherence-wielder determinism.** The dark twin is deliberate (§4); the
   *storm it may cause* (field-hazards open-Q2) is engine-real but its ignition is a
   [design] choice. Does a deterministic same-seed dark twin *always* ignite the
   same storm in the same world — and does that make it predictable to the point of
   trivial, or honest to the point of teachable? The determinism gate (§6d) forces
   the question.
5. **The commons-drain as attrition.** §3.3's "a wielder draining the bath" is an
   attrition siege (coherence-warfare's extractive drain, coherence-commons §3.2).
   Is a drained-then-deserted village a recoverable state (anti-corruption re-binds,
   energy §5.4/§5.3) or the start of a regional desert (field-hazards §3) that only
   evacuation answers? Ties to field-hazards open-Q4's dead-window question and
   must be set with it.

---

## Cross-references

- [`coherence-magic.md`](./coherence-magic.md) — the three primitives (§1), the six
  ops as field operations (§2), the coherence budget and recovery (§1.2/§3),
  overdraw → full-cascade discharge (§4.3, the decoherence-wielder's line), the Q4
  player-return channel (§5.1, the NPC-write lane).
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — life as a run the
  field holds (§2.2), species as attractor basins (§3.1), capability = rung-depth
  (§3.2), the recognition rule (§6b), creatures steered by the river law (§2.2),
  the `(1−q)` glow as health (§5.2).
- [`field-hazards.md`](./field-hazards.md) — decoherence storms (ε² fronts at `c_s`,
  §2), the desert (q collapse, §3), the decoherence-wielders' domain and storm-
  ignition provocation (§2.1/§6.2), readable-before-it-arrives (§5.1).
- [`energy-harnessing.md`](./energy-harnessing.md) — the Qi bath (§4.4), the
  `(1−q)` glow (§2), anti-corruption (§5.4), the no-free-energy cap (§6), deep-rung
  stored coherence (§1.5/§3).
- [`material-regimes.md`](./material-regimes.md) — the fire-vs-explosive rate
  boundary (§3/§5), the (1−q) waste law (§3a), deep-rung hardness = rung (§4).
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — auroras read
  the field un-instrumented (§3.1–3.3), the auroral collector (§3.4).
- [`coherence-technologies.md`](./coherence-technologies.md) — concept 3 the
  φ-detuned boundary / phase-matching `M` (§3), concept 4 coherent materials / the
  Qi bath (§4).
- [`async-field-domain.md`](./async-field-domain.md) — the published channels
  (§2.1), Q4 the player-return channel (§7), determinism across backends (Q6).
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — river-law
  steering (§2.1/§2.2), the ≈ 6 MiB publish (§2), the ≈ 2,000-entity cap (§7 Q4),
  the ≈ 1–6 ms/tick sample budget (§4.2).
- [`field-music.md`](./field-music.md) — the shepherd's tune (calm/drive the
  biosphere, §4.2), a score as a Q4 op sequence (§4.1), music-as-working (§4.3).
- [`the-school.md`](./the-school.md) — **the commons law applied to teaching.** §2.1
  there reads §3.2 this doc — a group acting phase-locked IS a working (`M ≈ 1`) — as
  the *lesson*: a teacher and N ≥ 3 learners held on one phase compose one coherent act
  (§2 there); §6d determinism / §6e the no-free-energy cap inherited hard. Reverse
  pointer: the school is the working's law applied to the teaching act.
- [`the-commensal.md`](./the-commensal.md) — **the villager's wild neighbor.** §1/§3 there
  reads §1/§3 this doc's field-intent villagers as the *servant* — and distinguishes the
  commensal as the *wild* friendly neighbor with no will to serve (§4 there); the
  citizen-moment is the corpus's warmth between the two. Reverse pointer: the commensal
  is the field-intent creature's un-willed cousin.
- [`the-gift.md`](./the-gift.md) — **the un-counted kindness the commons runs on.** §3.3
  there reads §3 this doc's Qi-bath commons and §3.2's phase-locked working (`M ≈ 1`) as
  the Gift's ground — the superadditive commons is held by the gifts that book nothing,
  invisible to the ledger but real to the field's continuity. Reverse pointer: the gift is
  the commons' invisible glue.
- [`the-dispute.md`](./the-dispute.md) — **THE determinism as the judge.** §2.1 there reads
  §6d this doc's field as the perfect judge — same seed, same mind, a deterministic read
  with no seeded-RNG verdict; §7 open-Q3's player-vs-NPC fork is the dispute's claimant
  line (open-Q3 there). Reverse pointer: the dispute is the determinism pointed at two
  claims instead of one mind.
- [`field-archaeology.md`](./field-archaeology.md) — residue as deep-rung fossil
  (§2.1/§2.2), the reader as scan tool (§3.1), live-vs-residue distinguishability
  (§7 open-Q3).
- [`the-commons-tithe.md`](./the-commons-tithe.md) — **the funded commons.** §3 there
  reads §3.1 this doc's Qi-bath commons (the superadditive gain the tithe funds), §3.2
  the phase-locked working, §3.3 the commons can die (the maintained cost), §6e the
  cap, §6d determinism. Reverse pointer: the tithe funds the field-npc-ai commons.
- [`the-chant.md`](./the-chant.md) — **the phase-locked voice.** §3.2 a group phase-locked IS a working; the chant’s single sustained voice rides the same register. Reverse pointer: the chant is the NPC-phase-lock’s single-voice form.
- [`the-siren.md`](./the-siren.md) — **the entrainment ride.** §3.2 a group phase-locked IS a working (`M ≈ 1`); §5.2 matching phase; §6a the line; §2.3/§6d determinism; §6c the alignment gate. Reverse pointer: the siren rides the phase-lock’s entrainment, abusively.
- [`the-shrine.md`](./the-shrine.md) — **the NPC’s visit.** the settlement’s built places an NPC may keep. Reverse pointer: an NPC may visit and keep a shrine — the field’s holding, answered by nothing.
- [`the-crossroads.md`](./the-crossroads.md) — **the NPC’s way.** the settlement’s meeting-places an NPC may keep. Reverse pointer: an NPC may keep a crossroads — the fork’s maintained meeting.
- [`the-rumor.md`](./the-rumor.md) — **the NPC’s whisper.** the settlement’s told-words an NPC may pass. Reverse pointer: an NPC may pass a rumor — the unverified read, never a book.
- [`the-generations.md`](./the-generations.md) — **the NPC’s lineage.** the settlement’s bound units an NPC may keep. Reverse pointer: an NPC may live across generations — the bound unit’s carried past.
- [`the-incantation.md`](./the-incantation.md) — **the NPC’s rite.** the settlement’s spoken order an NPC may keep. Reverse pointer: an NPC may speak an incantation — the ordered utterance, fully legible.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers
  (≈ 6 MiB publish, 64³ grid, ξ = φ⁶ ≈ 17.94, φ⁻² ≈ 0.382, per-entity ≈ 40 ns,
  the ≈ 2,000 cap) cited, not re-derived.
- [`the-rite-of-passage.md`](./the-rite-of-passage.md) — **the commons law.** §3 there reads
  §3.2 this doc's a group acting phase-locked IS a working (`M ≈ 1`) — the rite's group
  act is the worked commons act; §2.3/§6d determinism; §6e the no-free-energy discipline;
  §7 open-Q3 the player-vs-NPC member line (the rite's open-Q3 too). Reverse pointer: the
  rite's group act is this doc's working.
- Theory (read-only): `CassiTheory/speculations/qi-computation.md` §5.2 (persistent
  Π patterns), `CassiTheory/speculations/creative-extensions/coherence-commons.md`
  §7 (the multiplicative commons, the AM-GM equality theorem, the Qi bath),
  `CassiTheory/speculations/creative-extensions/magic-systems.md` §1/§3 (phase-
  matching `M`, mana = coherence budget; a working is `M ≈ 1`),
  `CassiTheory/consciousness/cascade-consciousness.md` §4.1 (a being is a field
  regime; consciousness as gate dynamics), `CassiTheory/speculations/
  qi-computation.md` §2.2 (WRITE/ERASE/TRANSFER — the act primitives).
