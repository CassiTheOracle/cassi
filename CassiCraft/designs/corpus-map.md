# The Corpus Map

A consolidation pass over the CassiCraft design corpus: the family map, the
phase-gate rollup, the Phase-1 build-order, and the consistency audit. This is a
**meta-document** — it maps what has been designed; it designs nothing, adds no
[design] flags, and re-derives no number. Every canonical figure below is cited
from the corpus's own authority, [`corpus-reconciliation.md`](./corpus-reconciliation.md),
never recomputed here.

---

## 1. The corpus, stated once

The corpus is **198 design documents, all indexed** — landed in waves 1–63,
the final wave closing the program, plus two user-requested arrivals outside the
wave numbering, that together form one design bible for a Minecraft overhaul
steered by the Cassi two-fluid field. **The corpus is complete.**
Every document is a face of one thesis: the two-fluid field is the substrate;
blocks, mobs, and planets are its epiphenomena. The engine's architecture is
the asynchronous domain + tick-sampler spine of
[`async-field-domain.md`](./async-field-domain.md) — the physics publishes
snapshots at cadence, the synchronously-ticking world samples them, and the
world never blocks on the physics.

The through-line holds across every doc, and it is a single law with four teeth:

- **No free energy, everywhere.** Nothing mints order. Every gain has a costed
  `(1−q)` waste or a bounded book.
- **The field is indifferent.** It does not oppose you or favor you; it is not a
  judge with mercy, it is a law.
- **Deterministic and legible.** The same state, the same channels, the same
  read; nothing is hidden-only, never a hidden roll of the dice.
- **Accessible.** The reads are wearable, buildable, plantable instruments — a
  player who chooses to can read what the field is doing.

The canonical numbers anchor is [`corpus-reconciliation.md`](./corpus-reconciliation.md)
§2: the `64³` grid, the ≈ 6 MiB field-only publish (q + pot + `∇(g·Φ)` vec3-trim + ρ),
`ξ = φ⁶ ≈ 17.94`, `φ⁻² ≈ 0.382`, `dt = 0.05`, `τ_c = 0.5`, the `π/ρ` clamp `0.72`,
`ω₀² = 20.0`, `q ≈ 0.947`, the ≈ 1–6 ms/tick sample budget, the ≈ 2,000 entity
cap, the 192³/64³/12³ box. Every design doc cites these verbatim; none re-derives.

**The count, stated once.** The designs/ directory holds **198 `.md` design
documents** (plus this map and `corpus-reconciliation.md`, the two meta-docs),
and the README index holds **199 rows — every row indexed, every one resolving
on disk, zero ghosts and zero `(next)` placeholders.** All 198 design docs are
indexed; **none is pending.** The waves run 1–63. The final seven arrivals close
the program across the last three waves — wave 61 (`the-tunnel` the horizontal's
engineered line, `the-waterfall` the falling water, `the-crane` the lifted load),
wave 62 (`the-comet` the passing bright, `the-bog` the soft ground, `the-atoll`
the ring reef), and wave 63 (`the-anchor` the held station, the seacraft's
resting) — completing the vertical, the water, the economy, the sky, the
landscape, and the movement stacks. The two user-requested arrivals outside the
wave numbering (`the-incantation` the spoken perturbation, `world-difficulty` the
turbulence dial) remain flagged separately. The map counts and rolls up the full
198-doc corpus; `corpus-map.md` and `corpus-reconciliation.md` are the map and
its ledger, not members of it.

---

## 2. The family map

The corpus spans **twenty-four primary families**. Each doc sits in exactly one
primary family (the assignment used to tally §2 and §3); several are honestly
cross-listed into a second or third family below without changing that primary.
The family through-lines below are read from the docs' own frames and headers,
then verified against the director's classification — where the docs differ from
the director's list, the frame wins and the divergence is noted. The column
headers list the family's full membership (primary + cross-listed); the primary
family for the recurring cross-listings is named in the ambiguities note that
closes this section.

| Family | Primary docs | Through-line | Completeness note |
|---|---|---|---|
| Foundations / the field | `volumetric-terrain`, `async-field-domain`, `chunk-field-quantization`, `material-regimes`, `energy-harnessing`, `coherence-technologies`, `custom-blocks`, `reason-field`, `corpus-reconciliation` (referee) | The substrate itself — the async domain, the quantization, the regimes, the energy law, and the reasoning layer that the whole rest is designed on top of. | **The corpus's load-bearing spine.** Architecture, budgets, and canonical numbers live here; every later doc cites back. `reason-field` (LATER) is the domain-side resolution that everything mechanical gates on. |
| The player | `coherence-magic`, `resonance-tutor`, `mouths-eye`, `life-signal`, `the-smell`, `the-touch` | Channeling, learning, tasting, classifying, scenting, touching — the player's six field-acts, all pure consumers of the publish. | Complete and unusually Phase-1-lean: five of six are ship-now. `life-signal` closes five peers' classifier questions (§3/§6). `the-smell` is the field's scent — the read that comes on the wind before you look; `the-touch` is the sixth sense — the field read by contact, the closest most dangerous read. |
| The instruments | `field-instruments`, `the-reading-ahead`, `the-clock`, `the-hourglass`, `the-tide-staff`, `the-bell`, `the-mirror`, `the-stratum-read`, `the-beacon`, `the-lantern`, `the-seeker`, `the-compass`, `the-silence`, `the-map`, `the-balefire` | Consumers with an idiom — every instrument reads an already-published channel, never adds one (the family rule from `field-instruments` §1.4). | The largest family (15). **Complete:** the reading, the timing, the holding, the finding, the night, the silence. The Weatherglass closes the corpus's "named but never instrumented" gap. `the-balefire` is the beacon's hazard-form — light raised to alarm (cross-listed to danger). |
| The danger layer | `field-hazards`, `signature-predator`, `wound-remembered`, `the-blight`, `the-scar-lifecycle`, `the-stillness`, `the-threshold` | The field's extremes — storms, the desert, BH accretion, the Coda, the blight, the wound's fate, the boundary. Danger is a read of the same channels, never a second physics. | Complete as a layer; the storm-provenance probe (`field-hazards` open-Q2) is its one open mechanical gate, owned by `weather-not-storm` §3. |
| The stranger-object layer | `signature-predator`, `the-blight`, `the-feral-instrument`, `the-scavenger`, `the-commensal`, `the-mirror-creature`, `the-witness`, `the-guardian`, `the-herald`, `the-mimic`, `the-moth`, `the-shepherd`, `the-broker`, `the-tutelary`, `the-pooka`, `the-siren` | The faces of the field's own creatures — each honest to what it is, each distinct from the other fifteen, each net-neutral or net-negative (nothing mints). | **The sixteen faces are distinct and verified.** (Cross-listed: `signature-predator` and `the-blight` primary in danger.) `the-broker` is the thirteenth face — the trading stranger; `the-tutelary` the fourteenth — the shadow-kin, the first personal face bound to a line; `the-pooka` the fifteenth — the fear-fed stranger, the layer's first emotional-territory face; `the-siren` the sixteenth — the resonant lure, the stranger that calls by harmonizing with your own signature. |
| The society stack | `schema-that-settles`, `shared-ledger`, `the-census`, `the-election`, `the-exile`, `the-festival`, `the-funeral`, `the-family`, `the-oath`, `the-treaty`, `the-apprenticeship`, `the-market`, `the-school`, `the-dispute`, `the-window-pulse`, `the-gatekeeper`, `the-spring-caretaker`, `the-midwife`, `the-baptism`, `the-shrine`, `the-rumor`, `the-generations`, `the-hand-over` | The window's shared order read off the Q4 op-stream — the ledger, the election, the exile, the dispute all resolve deterministically on the settled record. | The corpus's social engine, anchored by `schema-that-settles` (the op-schema, landed). `the-market`'s op-record matches schema §2.1 **verbatim**. `the-spring-caretaker` is the well's person-office; `the-midwife` the birth-ward; `the-baptism` the first-name; `the-shrine` the built remembrance; `the-hand-over` the steward's passing — the office-to-office transition as an audited, legible transfer, the governance stack's continuity act. `the-rumor` (the told-unverified) and `the-generations` (the succession chain) extend the stack's telling and succession faces (rumor cross-listed to culture). |
| The culture stack | `the-story`, `the-rite-of-passage`, `the-name`, `the-language`, `the-chronicle`, `the-archive`, `field-music` | The settlement's record, made narrative and ritual — the shaped versus the recorded, the rite that binds, the literacy that reads. | Complete; `the-archive` is the raw under-layer, `the-story` the shaped capstone, and the never-adds honesty (chronicle §5) is carried through every layer. |
| The economy | `the-market`, `the-gift`, `the-loan`, `the-commons-tithe`, `the-toll`, `the-fallow`, `the-granary`, `the-compost`, `the-quarry`, `the-wage`, `the-inn`, `the-mint`, `the-orchard`, `the-terrace`, `the-votive`, `the-crane`, `farm-that-feeds` | Exchange, giving, borrowing, tithing, tolling, depletion, storage, giving-back, the cut, the wage, the held bed, the struck unit, the planted stand, the stepped hold, the giving-to-the-field, the lifted load — every economic act books on the settled op-record; **the economy's only generosity is the gift.** | **Complete** — the market's honest inverse (the gift), the temporal instrument (the loan), the depletion (the fallow), the store (the granary), the first giving-back (the compost), the labor-flow that prices work (the wage), the held bed (the inn), the struck unit (the mint), the planted stand (the orchard), the stepped hold (the terrace), the giving-to-the-field (the votive), and the lifted load (`the-crane` — the mechanical advantage that never mints, the carry's vertical assist) all found. |
| The identity stack | `schema-that-settles` (member-id), `the-name`, `the-inheritance`, `the-child`, `the-family`, `the-lock` | What a player is in the field — the Π-anchor, the name, the lineage, the will, the joint hold, the permanent binding. | The member-id is [design]-landed; the persistent-Π mechanics are theory-ratified (LATER). The stack is designed and scaffolded now, mechanically deferred. |
| The memory stack | `field-archaeology`, `the-chronicle`, `the-memory-palace`, `seed-garden`, `the-echo`, `the-language`, `the-stratum-read`, `the-archive`, `the-archivist` | The field's kept past, read — the residue in place, the settlement's chosen memory, the vault, the heard echo, the strata, the raw record and its keeper. | Complete top to bottom: raw (`the-archive`/`the-archivist`) through kept (`the-memory-palace`) through told (`the-chronicle`/`the-story`). |
| The time stack | `tide-of-the-attractor`, `patient-field`, `the-cold`, `the-window-year`, `fate-of-a-window`, `the-drift-road`, `the-window-pulse`, `the-season-change`, `the-eclipse` | Human-scale time as a local quantity — the tide's tempo, the patience, the winter, the calendar, the window's fate, the drift's verdict, the collective pulse, the turn, the scheduled dark. | **Complete** — the corpus's time docs. The tide probe (`tide-of-the-attractor` §5a, Phase-1.5) is the single measurement the rest lean on. `the-eclipse` is the window's darkening — a rare scheduled moment when the read goes dark (cross-listed to sky). |
| The movement stack | `the-walk`, `coherence-highway`, `world-seams`, `the-pilgrim`, `the-atlas-of-windows`, `the-interstitial`, `the-harbor`, `the-fall`, `the-swim`, `the-marsh`, `the-cart`, `the-carry`, `the-climb`, `the-dive`, `the-migration`, `the-ford`, `the-sledge`, `the-raft`, `the-palanquin`, `the-caravan`, `the-seacraft`, `the-anchor` | Crossing, riding, descending, diving, the great moving, the winter carry, the water freight, the carried seat, the long-train, the open-water hull, the held station — every movement is a costed read of the gradient; the fall is the one movement with no skill-buff. | **Complete** — ground, road, air, water, descent, and the between. The walk/carry/climb/cart/fall are Phase-1-able; the voyage stack (interstitial, harbor, atlas) is Phase-2+ gated. `the-migration` is the movement-capstone; `the-ford` the river's natural shallow; `the-sledge` the winter sled; `the-raft` the river's bulk-carrier; `the-palanquin` the carried seat; `the-caravan` the long-train; `the-seacraft` the open-water vessel; `the-anchor` the held station — the reversible mooring, the hold against the drift, the seacraft's resting. |
| The weather | `weather-not-storm`, `field-hazards` (the storm), `the-flood`, `the-cold`, `the-wind`, `the-season-change`, `the-rain`, `the-dawn`, `the-blizzard`, `the-mirage`, `the-fog`, `the-drought`, `the-lightning` | The envelope's two-fluid waves as weather — the provenance classifier, the flood, the winter, the wind, the rain, the turn, the dawn, the whiteout, the deceitful read, the held blur, the receding, the sky's sudden. | The storm's provenance probe is the deciding gate; otherwise the weather stack reads known channels. `the-blizzard` is the moving white-out; `the-mirage` the deceitful read (danger cross); `the-fog` the held blur that hides what it wraps; `the-drought` the receding — the event of the ground's water leaving, distinct from the dry land itself; `the-lightning` the sky's sudden — the storm's gathered charge letting go at once, the discharge that is release not message. |
| The vertical | `the-sky` (via `atmosphere-orbits-auroras`), `the-zenith`, `the-sea`, `the-sea-floor`, `the-strata` (via `deep-field-diving`), `the-cave`, `the-bedrock`, `the-breath`, `the-dive`, `the-swim`, `the-understory`, `the-shaft`, `the-tunnel` | The window's full height — the ceiling, the middle, the interface, the hollow, the floor — and the body's descent through it. | **Complete**: top mirror of the deep, middle, first interface, cave, absolute floor, the diver's air, the canopy floor, the dug line, and the dug passage. `the-shaft` is the vertical's engineered descent; `the-tunnel` is its horizontal twin — the under-hill crossing that completes the line in both directions. |
| The practices | `the-vigil`, `the-working-song`, `the-husbander`, `the-stilling`, `the-shout`, `the-chant`, `the-incantation` | Deliberate held acts — the watch, the coordinated work, the wild's care, the voluntary quiet, the loud call, the sustained voice, the spoken perturbation. | Seven practice docs; the corpus's own frames number them — the vigil first, the chant the fifth named practice (holding in voice what a group holds in song), alongside the stilling's claim as the fourth. `the-incantation` is the practices layer's directed grammar — the field's script written back, the reverse of the Language, a MEDIUM-LATE doc with a PHASE-1-ABLE simplest-utterance slice. |
| The landscape | `the-landform-name`, `the-cave` (cross), `the-marsh`, `the-sea-floor` (cross), `the-spring`, `the-causeway`, `the-desert`, `the-river`, `the-ford` (cross), `the-estuary`, `the-delta`, `the-meadow`, `the-canal`, `the-cistern`, `the-dune`, `the-whirlpool`, `the-bog`, `the-waterfall`, `the-atoll` | The named land and its places — the landform, the hollow, the slow sea, the shelf, the wellspring, the crossing, the dry land, the living line, the natural shallow, the third water, the branched mouth, the open pasture, the dug water, the held water, the moving sand, the spinning drain, the soft ground, the falling water, the ring reef. | Complete as a regime-set: the river (primary landscape) and the ford (primary movement) both in-corpus; the water-places close with `the-whirlpool` (the spinning drain), `the-bog` (the soft ground that gives, the marsh's deeper cousin), `the-waterfall` (the falling water, gravity's own display), and `the-atoll` (the ring reef, the sea's crown). |
| The wild | `field-emergent-ecology`, `the-roost`, `the-shepherd` | The biosphere precipitated from the field, and the places its creatures live. | The ecology gives the organism-class run; the roost (its home) and the shepherd (its gatherer) are designed around it. |
| The cosmology | `pocket-cosmos`, `world-seams`, `the-interstitial`, `the-between` | The recursion grown inward, the edges between windows, the sparse medium, the field's own outside. | The corpus's most-gated quarter: LATER/Phase-2+ by design. |
| The settlement's rooms | `house-that-steers`, `the-observatory`, `the-harbor`, `the-school`, `the-granary` | The buildings as coherence architecture — the steered house, the reading room, the door to the between, the learning, the store. | Complete; the house/observatory hold Phase-1 held-structure slices. |
| The primitives | `the-tool`, `the-sea`, `the-fallow`, `the-market`, `the-gift`, `the-carry`, `the-walk` (cross-listed) | The rung-matched work object and the inventory primitives — the bite, the pack, the held regime. | `the-tool` is Phase-1-able and notably the corpus's overlooked primitive ("the thing ignored because the corpus went straight from materials to machinery"). |
| The body | `player-remains`, `the-burden`, `sleep`, `the-cooked-field`, `the-breath`, `the-carry`, `the-dive` (cross-listed) | The player's body as a field-state — death, the loan-with-interest, rest, the meal, the reservoir of air, the carried weight. | Complete; death is Phase-1-exceptable in concept (respawn logic, not physics). |
| The sky / leaving | `atmosphere-orbits-auroras`, `ksp-kernel`, `world-seams`, `the-meteor`, `world-difficulty`, `the-comet` | Up, out, and between — the atmosphere, the KSP bodies, the long dark, the falling bright, the world's ambient tempo, the returning body. | Phase 2 by design; the KSP kernel needs the meshless/tree frontier. `the-meteor` is the rarest sky-event; `the-comet` its periodic cousin — the passing bright, the returning body on its long orbit (a MEDIUM-LATE doc, gated on the sky's announced-momentum). `world-difficulty` sits here as the envelope's settings face — not sky physics but the world-birth turbulence dial (the ambient-activity setting scaling the field's own tempo), its Phase-1-able ambient-noise slice buildable now and its weather-frequency dial gated; it is the corpus's one user-requested world-settings doc, and no dedicated world-settings family exists yet. |
| Life (biosphere/minds) | `field-emergent-ecology`, `field-npc-ai` | Mobs as precipitates of the field; NPC minds as the field's own organization (the reason-field). | `field-emergent-ecology` is a pre-registered Phase-1 probe; `field-npc-ai` is Phase-1-able with intentionality as a consumer. |
| Genesis | `resonance-seeds` | The origin, made playable. | A single doc, deep-later; the recursion's parent. |

**Ambiguities the map refuses to force.** `signature-predator` and `the-blight`
are both danger *and* stranger faces — they are named in both families and
primary in danger, because their frames lead with the hazard spine before the
predator/blight face. `the-tool` and `the-carry` are primitives and body/movement
(they are cross-listed, not forced). `the-sea-floor` and `the-cave` are primary
vertical and secondary landscape. `the-interstitial` is primary cosmology and
secondary movement. `the-cold` is primary weather and secondary time. `the-ford`
is primary movement and secondary landscape — the river's natural shallow, the
causeway's given-natural twin, whose crossing is a movement read and whose
shallow is a landscape place. `the-estuary`
is primary landscape and secondary water/weather — the third water, the
first designed boundary between two designed places, composing the tide and the
two waters (the sea and the river). `the-delta` is primary landscape and
secondary movement — the branched mouth, the corpus's only network-region
terrain. `the-mirage` is primary weather and secondary danger — the deceitful
read, the first doc where the danger is in the reading's interpretation, never
in the field lying. `the-eclipse` is primary time and secondary sky — the
window's scheduled darkening. `the-raft` is primary movement and secondary
water — the river's bulk-carrier. `the-inn` is primary economy and secondary
society — the held bed, the traveler's welcome. `the-orchard` is primary economy
and secondary landscape — the planted stand, the farm's slow fixed cousin. The
wave 53–56 landings add two more honest cross-lists: `the-canal` and `the-cistern`
are primary landscape and secondary water — the engineered waterway and the
built store of the spring, the corpus's first engineered navigations; `the-balefire`
is primary instruments and secondary danger — the beacon's hazard-form, light
raised to alarm; `the-siren` is a stranger-object face (primary) whose lure is
an instrument's call — the resonant harmonization, cross-listed to instruments;
`the-baptism` is primary society and secondary identity/culture — the first-name,
the ceremony of giving a new being its name at birth; `the-meteor` is primary
sky (the sky/leaving family); `the-touch` is primary the-player (the senses) with
a cross to the body — the skin-read, the field read by contact. The economy
and the society stack overlap on `the-market`, `the-toll`, `the-commons-tithe` —
the market is primary economy but its trust-by-law is a society read; the map
marks it economy-primary and notes the society cross. Where a frame is genuinely
ambiguous, the ambiguity is recorded here rather than resolved.

---

## 3. The phase-gate rollup

Every doc's feasibility verdict is read from its own frame (the `Feasibility = ?`
/ `Honest gates` lines). The classes below are the corpus's own vocabulary — the
docs say **PHASE-1-ABLE**, **MEDIUM**, **MEDIUM-LATE**, **LATER** (and the hybrids
"MEDIUM with a Phase-1-legible framing" / "PHASE-1-ABLE slice + MEDIUM-LATE full").
Rollup over the **198 design docs** (the 199-row README minus the
meta-doc `corpus-reconciliation`, itself a referee; `corpus-map.md` is the map,
not a corpus member; all 198 are indexed, none carried):

| Verdict class | Count | Docs |
|---|---|---|
| **PHASE-1-ABLE** (ships at Phase-1) | **61** | `volumetric-terrain`, `async-field-domain`, `chunk-field-quantization`, `material-regimes`, `energy-harnessing`, `coherence-technologies`, `coherence-magic`, `field-emergent-ecology`, `atmosphere-orbits-auroras`, `field-hazards`, `field-music`, `field-npc-ai`, `field-instruments`, `player-remains`, `resonance-tutor`, `mouths-eye`, `life-signal`, `schema-that-settles`, `farm-that-feeds`, `the-burden`, `sleep`, `the-map`, `worn-field`, `the-clock`, `the-mirror`, `the-bell`, `the-silence`, `the-lantern`, `the-seeker`, `the-census`, `the-threshold`, `the-hourglass`, `the-walk`, `the-tide-staff`, `the-sea`, `the-tool`, `the-vigil`, `the-stratum-read`, `the-harbor`, `the-dawn`, `the-swim`, `the-carry`, `the-cart`, `the-rain`, `the-wind`, `the-fall`, `the-echo`, `the-compass`, `the-stilling`, `the-shout`, `the-cooked-field`, `the-marsh`, `the-wage`, `the-touch`, `the-shrine`, `the-shaft`, `the-tunnel`, `the-waterfall`, `the-crane`, `the-bog`, `the-anchor` |
| **MEDIUM** (designable-now, gated 1.5+) | **56** | `coherence-highway`, `the-apprenticeship`, `the-beacon`, `the-causeway`, `the-cave`, `the-child`, `the-climb`, `the-commons-tithe`, `the-compost`, `the-gift`, `the-healer`, `the-husbander`, `the-language`, `the-loan`, `the-market`, `the-moth`, `the-pilgrim`, `the-quarry`, `the-rite-of-passage`, `the-roost`, `the-scar-lifecycle`, `the-sea-floor`, `the-spring`, `the-stillness`, `the-window-pulse`, `the-working-song`, `the-zenith`, `the-ford`, `the-broker`, `the-smell`, `the-inn`, `the-blizzard`, `the-understory`, `the-mirage`, `the-mint`, `the-orchard`, `the-sledge`, `the-eclipse`, `the-chant`, `the-meadow`, `the-canal`, `the-cistern`, `the-balefire`, `the-palanquin`, `the-fog`, `the-drought`, `the-dune`, `the-terrace`, `the-votive`, `the-lightning`, `the-crossroads`, `world-difficulty`, `the-rumor`, `the-seacraft`, `the-whirlpool`, `the-atoll` |
| **MEDIUM-LATE** (Phase-1-legible framing or slice) | **63** | `deep-field-diving`, `fate-of-a-window`, `house-that-steers`, `shared-ledger`, `signature-predator`, `the-archive`, `the-archivist`, `the-atlas-of-windows`, `the-bedrock`, `the-between`, `the-blight`, `the-breath`, `the-chronicle`, `the-cold`, `the-commensal`, `the-desert`, `the-dispute`, `the-dive`, `the-drift-road`, `the-election`, `the-exile`, `the-fallow`, `the-family`, `the-feral-instrument`, `the-flood`, `the-funeral`, `the-gatekeeper`, `the-guardian`, `the-herald`, `the-interstitial`, `the-landform-name`, `the-lock`, `the-memory-palace`, `the-mimic`, `the-mirror-creature`, `the-observatory`, `the-reading-ahead`, `the-scavenger`, `the-school`, `the-season-change`, `the-shepherd`, `the-story`, `the-toll`, `the-window-year`, `weather-not-storm`, `wound-remembered`, `the-spring-caretaker`, `the-migration`, `the-river`, `the-estuary`, `the-tutelary`, `the-midwife`, `the-delta`, `the-raft`, `the-pooka`, `the-siren`, `the-meteor`, `the-baptism`, `the-caravan`, `the-incantation`, `the-generations`, `the-hand-over`, `the-comet` |
| **LATER / GRAND** (mechanical, scaffolded-now) | **12** | `pocket-cosmos`, `reason-field`, `resonance-seeds`, `seed-garden`, `the-festival`, `the-granary`, `the-inheritance`, `the-name`, `the-oath`, `the-treaty`, `the-witness`, `window-guests` |
| **PHASE-1.5 / Phase-2 gated** (measurement or frontier first) | **6** | `custom-blocks`, `field-archaeology`, `ksp-kernel`, `patient-field`, `tide-of-the-attractor`, `world-seams` |

*(The map's tally: 61 + 56 + 63 + 12 + 6 = 198 — the complete corpus through
waves 1–63. The PHASE-1-ABLE class includes the docs whose frames say
PHASE-1-ABLE outright and those with a clean Phase-1 slice or Phase-1-lean
framing — e.g. the-marsh, the-wind, the-harbor — that cost inside the ≈ 1–6
ms/tick sample budget and add no engine term; the final-five Phase-1 added docs
(the-tunnel, the-waterfall, the-crane, the-bog, the-anchor) carry a full-MEDIUM
note in their frames. The rollup covers all 198 design docs; the two
user-requested arrivals (`the-incantation`, `world-difficulty`) are listed in
their own frame's verdict class, and none is carried pending the index.)*

### The honest reading

**What the corpus can ship at Phase-1 (54 docs).** The living-terrain stack
(`volumetric-terrain` + `chunk-field-quantization` + `material-regimes` over the
published channels), the reader + Weatherglass, the Life-Signal read, the
instruments (clock, hourglass, lantern, map, bell, silence, tide-staff, compass,
seeker, dawn, stratum-read), the movement primitives (walk, carry, climb, cart,
fall, swim), the practices (vigil, stilling, shout), the weather's harvest
(rain, dawn, wind's slice), the marsh, the tool, the worn field, sleep, the
cooked field, the first records (schema-that-settles + the census's
aggregation), the first paid-day book (the-wage), and the skin-read touch. These
are the corpus's Phase-1 slices.

**What needs Phase-1.5 measurements (the gated 6, plus the probe-heavy MEDIUMs).**
`tide-of-the-attractor` §5a's T1–T4 probe and `patient-field` §5b's L1–L3 probe
are the deciding measurements the time stack and the danger/cold/flood docs lean
on. `field-archaeology` needs residue-vs-live persistence. `custom-blocks` and
`reason-field` need the meshless/persistent-Π frontier. `ksp-kernel` and
`world-seams` need the tree arm and the Q4 seam.

**What waits on deeper gates.** The identity and cosmology stacks (the-name,
the-inheritance, the-oath, the-treaty, pocket-cosmos, seed-garden, the-witness)
are LATER/GRAND — their mechanics ride the persistent-Π frontier that
`reason-field` §6a names. None of them is a Phase-1 blocker; all are scaffolded
now and their principles are statable.

**The honest summary:** three in ten docs are directly Phase-1-able,
and the MEDIUM/MEDIUM-LATE tail carries a statable Phase-1-legible framing or
slice — so a Phase-1 demo is not blocked on the corpus's depth, only on the
engine's published channels and the Q4 op-stream, which the foundational docs
already commit.

---

## 4. The Phase-1 build-order

The consolidation's load-bearing section: the ordered build plan for a Phase-1
demo, derived from the corpus itself. Each step names the docs whose Phase-1
slices compose it, the canonical numbers it rests on, the publish/Q4-lane it
uses, and the determinism gate it must clear.

| # | Step | Ships | Proves | Defers | Publish / Q4 lane + determinism gate |
|---|---|---|---|---|---|
| 1 | **The living-terrain demo** | `volumetric-terrain` + `chunk-field-quantization` + `material-regimes` over the published channels | The field *is* the terrain — blocks as iso-surfaces, mining as a perturbation, ore as a scalar channel | The multi-rung precision tools | `64³`, ≈ 6 MiB publish, dt = 0.05, ≈ 1–6 ms/tick |
| 2 | **The reader + Weatherglass** | `coherence-magic` §2 (Sense) + `field-instruments` §1.4 | Reading is a pure consumer; the instrument rule holds | The Far Mirror | ≈ 6 MiB, q≈0.947, φ⁻², ξ |
| 3 | **The Life-Signal read** | `life-signal` §3/§6 (the vitality classifier) | One read closes the five peers' classifier questions | Per-entity `M` publication | ε²-gradient sign + cadence, a pure read |
| 4 | **The first walk + carry + climb costs** | `the-walk` + `the-carry` + `the-climb` Phase-1 slices | Movement is a costed read of `q`/`ε²`/`∇(g·Φ)` | The highway network | `a = −G_N·(π/ρ)·∇(g·Φ)`, ≈ 40 ns/entity |
| 5 | **The first practice — the stilling or the shout** | `the-stilling` (deliberate `ε²`-low/`q`-steady hold) or `the-shout` (loud-classified broadcast) | A Q4 write that steers, honestly | The group phase-lock | Q4 op-schema (`schema-that-settles` §2.1) |
| 6 | **The first stranger read** | `signature-predator` §8 (the readable-trail slice) + `the-moth` §5b (the brightness-draw read) | A stranger is read as a pattern, never faced blind | The Coda's live behavior | `R = ρ_signature · τ · M_stability`, ε²/cadence reads |
| 7 | **The first record** | `schema-that-settles` + `shared-ledger` (the Board aggregation) + `the-archivist` (the custodial hold) | The Q4 op-stream composes a settlement's record | The member-id across death | `{member, op, worldPos, rung, magnitude, sustain}` (schema §2.1 verbatim), 44 ms unused tick |
| 8 | **The first weather** | `the-rain` (bounded nourishing precipitation) or `the-wind` (directional flow read) | Weather is the envelope read, not a second system | The storm-provenance probe (open-Q2) | `FieldVel`, c_s = h₀/dt, ≈ 1–6 ms |
| 9 | **The first settlement room** | `house-that-steers`, `the-observatory`, or `the-shrine` as held structures | A building is coherence architecture (shape-is-the-tuner) — the shrine is the simplest, the built remembrance on the settled book | The Qi bath (Phase-1.5) | 192³ box, ≈ 6 MiB, ξ, q≈0.947 |
| 10 | **The thin-regime read** | `the-desert` Phase-1 slice (the dry land, the regime of absence) | The hazard layer begins legibly, before the storm | The desert's collapse mechanics | Thin-trough threshold (`tide-of-the-attractor` open-Q3 / `field-hazards` open-Q1) |

### The sequencing principle

The corpus's own discipline writes the order: **pure consumers first, Q4 writes
second, mechanics inherit their sources' gates.** Steps 1–4 are read-only
consumers of the ≈ 6 MiB publish — they cost inside the ≈ 1–6 ms/tick sample
budget, prove the surface, and need no new engine term. Step 5 is the first
bounded Q4 write, exercising the op-schema. Steps 7 and 9 exercise the Q4
op-stream and the settled record. Steps 6, 8, and 10 add the first strangers,
weather, and hazard — all still reads. Nothing in the Phase-1 build-order
requires the persistent-Π frontier, per-entity `M` publication, or the
Phase-1.5 material constants; the build that waits on those is the LATER stack,
which is designed but not sequenced here. The wage is the build-order's quiet
addition to step 7's first record: its **Phase-1 paid-day book** is a bounded
consumer + Q4 write (the same op-record the market books), the corpus's first
priced-labor line, viable alongside the first record rather than a new step. The
shaft and the incantation add the two newest Phase-1-able slices without new
steps: the shaft's dug line rides the landed movement/mine primitives beside the
walk (a vertical read that needs no new engine term), and the incantation's
simplest-utterance slice is a directed-manipulation read/write that extends step
5's first practice rather than displacing it. The seacraft's route-read (the
open-water hull's course over the wind's current) and the whirlpool's bounded
low-`q` drain-read (the spinning drain as a consumer) are the wave-60 additions —
both Phase-1-testable as readers, extending the water-crossing legs of the walk
and the swim without new engine terms. The final-wave slices close the Phase-1
loop: the tunnel's dug passage and the bog's softness-read are bounded cuts over
the landed movement/mine and q/ρ primitives, the waterfall's discharge-read is a
bounded read over `∇(g·Φ)`/`(1−q)`, the crane's lift is the carry's vertical
mechanism over carry/cart/tool, and the anchor's hold is the reversible mooring
over carry/tool/sea-floor — all buildable beside the walk now, with their full
forms gated on the deeper rendering and freight-line.

---

## 5. The consistency audit

The consolidation's honesty section. All three checks were re-run on this pass
against the on-disk corpus (not copied from the reconciliation, though the
reconciliation's own audit rows are cited for the deep history).

### (a) Canonical-numbers check (spot-check ~12 docs)

| Doc | 6 MiB | 17.94/φ⁶ | 0.382 | 0.947 | 1–6 ms | 40 ns | Op-record | Verdict |
|---|---|---|---|---|---|---|---|---|
| `the-walk.md` | ✔ | ✔ | ✔ | — | ✔ | ✔ | — | **OK** |
| `the-map.md` | ✔ | ✔ | ✔ | ✔ | — | — | — | **OK** |
| `the-clock.md` | ✔ | ✔ | ✔ | — | ✔ | — | — | **OK** |
| `the-moth.md` | ✔ | ✔ | ✔ | — | ✔ | ✔ | — | **OK** |
| `the-sea.md` | ✔ | ✔ | ✔ | — | ✔ | — | — | **OK** |
| `the-desert.md` | ✔ | ✔ | ✔ | — | ✔ | — | — | **OK** |
| `the-tool.md` | ✔ | ✔ | ✔ | — | ✔ | — | — | **OK** |
| `life-signal.md` | ✔ | ✔ | ✔ | — | ✔ | — | — | **OK** |
| `the-dispute.md` | ✔ | ✔ | ✔ | — | ✔ | ✔ | ✔ (schema §2.1 verbatim) | **OK** |
| `the-dawn.md` | ✔ | ✔ | ✔ | — | ✔ | — | — | **OK** |
| `the-stilling.md` | ✔ | ✔ | — | — | ✔ | — | — | **OK** |
| `the-stratum-read.md` | ✔ | ✔ | — | — | ✔ | — | — | **OK** |

Every sampled number resolves to the reconciliation's canonical set; the
per-doc gaps are absent-by-relevance (each doc cites its own subset), never
divergent. **No CONFLICT** in the sample. (Each doc carries the "cited, not
re-derived" discipline; a "re-derive" hit means the doc names the prohibition,
not that it re-derives.)

### (b) Cross-ref check (spot-check ~20 docs)

`volumetric-terrain`, `chunk-field-quantization`, `field-instruments`,
`life-signal`, `schema-that-settles`, `the-map`, `the-clock`, `the-hourglass`,
`the-tide-staff`, `the-walk`, `the-sea`, `the-stratum-read`, `the-observatory`,
`field-hazards`, `the-quarry`, `the-desert`, `the-moth`, `the-shout`, `the-dawn`,
`field-npc-ai` — every backtick `./*.md` reference in these resolves to a real
on-disk file. **No broken cross-ref** in the sample. The reconciliation's own
deep audit (fixes 1–52, certified through wave 56 — the t19 extension of the
historical record) is the ledger; this pass confirms the state is clean today.

### (c) Family-completeness check

- **The stranger layer's sixteen faces are distinct.** signature-predator, the
  blight, the feral-instrument, the scavenger, the commensal, the
  mirror-creature, the witness, the guardian, the herald, the mimic, the moth,
  the shepherd, the broker, the tutelary, the pooka, and the siren — each reads,
  hunts, turns, wears, gathers, watches, trades, shadows, is fed, or is lured in
  a way the others do not; the witness is the only neutral (the "first
  non-face"), the broker the first economic bridge, the tutelary the first
  *personal* face (bound to a line, not a place), the pooka the first
  *emotional-territory* face, and the siren the first *seduction* — the stranger
  that calls by harmonizing with your own signature.
- **The vertical is complete.** zenith (ceiling) → understory (the forest
  middle, the shade-band) → sea (middle) → sea-floor (first interface) → cave
  (hollow) → bedrock (floor), with the dive and the breath for the body's
  descent and the sky for the top mirror of the deep.
- **The economy is complete.** market, gift (the only generosity), loan,
  commons-tithe, toll (border), fallow (depletion), granary (store), compost
  (giving-back), quarry (the cut), wage (the labor-flow that prices work), inn
  (the held bed), mint (the struck unit), orchard (the planted stand), terrace
  (the stepped hold), votive (the giving-to-the-field, the gift's other face),
  farm (renewable) — every economic op books on the settled record, and nothing
  mints.
- **The movement stack is complete.** ground (walk), road (highway, cart),
  air (the sky's leaving), water (swim, ford, marsh, raft), the white and the
  deep cold (sledge), descent (fall, dive, climb), the carried seat (palanquin),
  the long-train (caravan), the between (interstitial, harbor, atlas), and the
  great moving (migration) — the movement-capstone the single-body forms
  presuppose.
- **The landscape is complete at its places.** the sea, the marsh, the river,
  the estuary (the third water, the first designed boundary), the delta (the
  branched mouth), the meadow (the grazed common), the canal (the dug water),
  the cistern (the held water), and the dune (the moving sand) — where the tide
  and the waters argue and the mix feeds at the field's own yield, never a mint.
- **The weather is complete at its extremes.** the storm, the flood, the cold,
  the dawn, the rain, the wind, the season-change — and the blizzard (the moving
  white-out), the mirage (the deceitful read), the fog (the held blur that hides
  what it wraps), and the drought (the receding, the event of the ground's water
  leaving).
- **The practices are a complete set.** the vigil (the watch, the first), the
  working-song (the coordinated work), the husbander (the wild's care), the
  stilling (the voluntary quiet, the fourth), the shout (the loud call), and the
  chant (the sustained voice, the fifth named practice — holding in voice what a
  group holds in song).
- **The society stack's person-offices and ceremonies are complete.** the
  gatekeeper (the door), the spring-caretaker (the source), the midwife (the
  birth-ward), and the baptism (the first-name) — the new being's first
  maintenance read, booked, and handed to the family's anchor in one held act.

### (d) The known engine-gap list (restated from `corpus-reconciliation.md`)

The reconciliation's binding list, updated with what the map reveals:

1. **Field-only snapshot publish** — the ≈ 6 MiB `(q, pot, ∇(g·Φ), ρ)` publish is
   the canonical contract; the EY/EI-separate (7 MiB) and grad-vec4 (8 MiB)
   variants are designed but the single-field publish is the Phase-1 target
   (`chunk-field-quantization` §2).
2. **`∇(g·Φ)` in the publish** — the river gradient must actually ride the
   publish (the vec3-trim, 3 MiB) for the walk/carry/climb/fall/cart reads and
   the river-law steer `a = −G_N·(π/ρ)·∇(g·Φ)` to work.
3. **The Q4 player-return channel** — `async-field-domain` Q4, the write lane
   back to the field; consumers (`coherence-magic` §5.1, `energy-harnessing` §2,
   `custom-blocks` §2) are named, and the schema is settled, but the live channel
   is engine work.
4. **Per-material constants** — `material-regimes` §7's Phase-1.5 gates (per-cell
   `ω₀²`/`ξ`, per-material `γ`/`ν`/`μ`) are the upstream dependency for
   `custom-blocks` and the tool's rung-matched bite; until they land, the whole
   field runs one `ξ` and the "regime dressing" is surface.
5. **The storm-provenance probe** — `field-hazards` open-Q2, operationalized by
   `weather-not-storm` §3: can the field spontaneously hold ordered `c_s` `ε²`
   structures at all. Every danger/stanger doc re-gates on it.

**New gaps the map reveals:** the Q4 player-return channel (#3) and the per-material
constants (#4) are the two genuinely open engine gates the entire MEDIUM/MEDIUM-LATE
tail sits on; the storm-provenance probe (#5) is the one measurement that unlocks
the danger and stranger layers' mechanical depth. All three were already the
reconciliation's binding list — the map only re-confirms them under a heavier
weight of dependent docs.

### (e) The honest gaps the map reveals

- **Families that are thin.** Genesis is a single doc (`resonance-seeds`); the
  wild is a single doc (`the-roost`) beneath the ecology and the shepherd;
  the primitives is a single doc (`the-tool`). None is a problem — each is a
  deep-rooted doc — but each is a one-node family that the corpus leans on
  heavily.
- **Open questions that recur across docs.** The identity open (member-id
  across death, `shared-ledger` open-Q1 riding `player-remains` §5 open-Q5);
  the deliberate-vent residual of life-signal open-Q2; the drift-collapse verdict
  read off one T1–T4 probe. The map's read: the recurs are concentrated in the
  identity and time stacks, and each has a named owner — they are designed-open,
  not abandoned-open.
- **A family with no Phase-1 slice.** The cosmology stack (pocket-cosmos,
  world-seams, the-between, the-interstitial) is the one family with **no**
  Phase-1-able primary member — every doc in it is LATER/Phase-2+ by design. The
  interstitial's Phase-1-legible framing is its only foothold. A Phase-1 demo
  does not need it, but it is the corpus's least-instantiable quarter.

---

## 6. The corpus's state — verdict

The 198-doc corpus (all indexed, the program's complete final state) **is a
complete design bible for the field-steered Minecraft**: every face of one law —
the substrate, the player's six acts, the instruments, the sixteen-faced stranger,
the danger, the society, the culture, the economy, the identity, the memory, the
time, the movement, the weather, the vertical, the practices, the landscape, the
wild, the cosmology, the rooms, the primitives, the body — is designed, costed
against the same canonical number set, and cross-referenced two-way through a
reconciliation ledger that now reads honestly through wave 56. It is **not
yet a live engine build**: the slices are designed and the mechanics gated, but
the published channels, the Q4 op-stream, and the per-material constants are
engine work, not design — the corpus commits to them, it does not do them.

Three honest cautions close the verdict. First, the reconciliation's deep audit
now reads honestly through wave 56 — reconcile t19 landed and verified, its
passes 31–41, fixes 42–52, including the wave 46–56 set and the seven typo
fixes. Reconcile t20 is landing in parallel, covering the wave-57/58/59/60
arrivals and the two user-requested docs (`the-dune`, `the-terrace`, `the-votive`;
`the-shrine`, `the-lightning`, `the-crossroads`; `the-rumor`, `the-generations`,
`the-shaft`; `the-hand-over`, `the-seacraft`, `the-whirlpool`; `the-incantation`,
`world-difficulty`). The seven final arrivals (the tunnel, waterfall, crane,
comet, bog, atoll, and anchor of waves 61–63) await their own audit pass, not yet
reconciliation-certified until then. Second, **all
198 docs are indexed and resolve** — nothing indexed sits outside the disk, and
nothing on disk sits outside the index; the final wave closed the last pending
gap. Third, the two
open engine gates (per-material constants, the storm-provenance probe) and the Q4
player-return channel carry the whole MEDIUM/MEDIUM-LATE tail; until they land,
the corpus's deep stack is designed but unshippable — which is the honest state a
design bible is meant to hold.

**The standing offers.** The **silhouette probe** on the CassiCosmos sim — measure
whether the live field actually realizes the Coda's `c_s` `ε²` structure the danger
and stranger layers assume. And the **first Phase-1 demo** — steps 1–10 of §4, a
living-terrain window with a reader, a life-signal, a walk, a stilling, a first
record, a first weather, and a thin-regime read — which needs only the published
channels and the Q4 op-stream, both already committed by the foundation docs.

**The honest next steps.** (1) Land the wave-40/41 engine gate — the per-material
constants and the Q4 player-return channel — as the reconciliation's binding list
demands. (2) Complete the audit: reconcile t20 certifies the wave-57/58/59/60
arrivals and the two user-requested docs, and the seven wave-61/62/63 final
arrivals (tunnel, waterfall, crane, comet, bog, atoll, anchor) get their own
pass so all 198 join the reconciliation's certified set. (3) Run the
silhouette probe and the tide probe (T1–T4) to convert the danger and time stacks
from design to measurement. (4) Then the first Phase-1 demo becomes not a promise
but a build order. The corpus is complete enough to begin; it is honest enough
to say exactly where.
