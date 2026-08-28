# CassiCraft

Minecraft as a **living Cassi universe**: redesigning the block world around the
two-fluid field so that terrain, structure, ecology, and physics are
*epiphenomena of one law* rather than hand-authored game rules.

This directory is the **design and ideas home** for the overhaul. Not a mod
yet — the designs, module architecture, mechanics, and feasibility notes that
will become the mod. Companion workspace: the four Cassi repos
(`CassiCosmos/` = the physics engine to rehost, `CassiTheory/` = the laws,
`CassiCore/` + `CassiAI/` = orchestration/archive).

## The thesis (one line)

> Minecraft stops being the game and becomes the observation + interaction
> surface of a running Cassi universe: the two-fluid field is the substrate;
> **blocks, mobs, and planets are its epiphenomena**.

## Architectural spine

Everything below rests on the engine's already-battle-tested decoupling: the
physics runs as an **asynchronous domain** on its own thread/GPU and *publishes*
snapshots; the synchronously-ticking world *samples* it. The world never blocks
on the physics; the physics never waits on the tick.

```
┌─ Field domain (async, own thread / GPU) ───────────────┐
│  two-fluid PDE on a deforming curvilinear mesh         │
│  meshless sites (2·16³, JFA + Lloyd relaxation)        │
│  tree-gravity mode-5 (open boundary)                   │
│  condensation → dust → objects → BH                    │
└────────────────┬── publishes q, ε², ρ, ∇(gΦ), bodies ──┘
                 │  (at cadence, not per tick)
┌────────────────▼── Tick-sampler (server, 20 Hz) ───────┐
│  chunk ↔ field quantization                            │
│  entity / mob / item steering                          │
│  rigid-body vehicles (the KSP layer)                   │
└─────────────────────────────────────────────────────────┘
```

## Corpus arc

The corpus spans ten families, each one line of the same thesis — one field, and
every design is one of its faces. The doc index below is the living authority on
what exists; this section is how the families order:

- **Foundation** — volumetric-terrain, async-field-domain, chunk-field-quantization
  (representation, seam, budget)
- **Matter & power** — material-regimes, energy-harnessing, coherence-technologies
  (the laws of substance and energy)
- **The player** — coherence-magic, custom-blocks, resonance-tutor, mouths-eye —
  channeling, authoring, learning
- **Life** — field-emergent-ecology, field-npc-ai (the biosphere, NPC minds)
- **Sky & leaving** — atmosphere-orbits-auroras, ksp-kernel, world-seams,
  deep-field-diving (up, out, between, down)
- **Time & deep past** — tide-of-the-attractor, field-archaeology, player-remains
  (tempo, residue, death)
- **Danger** — field-hazards, signature-predator (the field's extremes, the field
  that hunts)
- **Genesis & recursion** — resonance-seeds, pocket-cosmos (origin, the inward fold)
- **Culture** — field-music, field-instruments, the-reading-ahead (the world's
  voice, eyes, and omens)
- **Referee** — corpus-reconciliation

The phases remain as the arc's build order: **Phase 1** = Foundation + Matter &
power + the Phase-1 slices; **Phase 2** = Life, Sky & leaving; **Phase 2+/3** = the
rest. The architecture (async domain + tick sampler + continuous bodyworks) is
unchanged across all of it — you only turn on more of the same law.

## Why open boundary is not optional — and how it shipped

The grid arm is a **periodic torus** — launch outward and it wraps; a fixed box
is a scale limiter. The open-boundary answer is now shipped in the engine
(`CassiCosmos`): the **B path** — a tracking envelope whose coarse grid re-fits
to the structure's percentile envelope (grow/shrink hysteresis, soft move cap,
aspect-preserving), fine patches that ride condensed structures, and the
tree-gravity arm (mode 5) as the open direct-sum force. The science run pushed
two clusters to **1.50× the old box half-extent** with no periodic image (the
boundary zone's mass content 0.00119 of the peak) — the box follows the world
instead of clipping it. The meshless promotion (A) was measured and shelved:
gate-iv showed the per-site wave 38% off on coarse dispersion, so the N³
lattice stays the field of record. The moving-Voronoi sites still earn their
keep: they mark "where the field is most organized" — a natural chunk-activity
/ LOD scheduler — the physics is also the load map.

## Document index

| Document | Contents |
|---|---|
| `designs/volumetric-terrain.md` | Replacing 1m blocks with a volumetric, multi-scale field terrain + precision tools |
| `designs/async-field-domain.md` | Async field domain + tick-sampler module architecture |
| `designs/chunk-field-quantization.md` | Chunk ↔ field quantization + per-tick budget |
| `designs/material-regimes.md` | Materials as field regimes (Powder-Toy physics sandbox) |
| `designs/energy-harnessing.md` | Energy harvesting, storage, transport, and what it does |
| `designs/coherence-technologies.md` | Coherence technologies from the CassiTheory speculations |
| `designs/coherence-magic.md` | Player power system: channeling one's own coherence |
| `designs/custom-blocks.md` | Custom blocks as authored field regimes |
| `designs/corpus-reconciliation.md` | Corpus consistency ledger + canonical numbers |
| `designs/field-emergent-ecology.md` | Field-emergent ecology: mobs as precipitates of the field |
| `designs/atmosphere-orbits-auroras.md` | The sky as field phenomenology: atmosphere, orbits, auroras |
| `designs/ksp-kernel.md` | KSP kernel: bodies, vehicles, coherence-injection rockets |
| `designs/world-seams.md` | World seams and the long dark: travel between anchored windows |
| `designs/field-archaeology.md` | Field archaeology: the world's deep past as readable residue |
| `designs/field-hazards.md` | Field hazards: the danger layer (storms, the desert, BH accretion) |
| `designs/resonance-seeds.md` | Resonance seeds: the genesis design, made playable |
| `designs/field-music.md` | Field music: the world sings; sonification as a field operation |
| `designs/field-npc-ai.md` | Field NPC AI: the field as AI for NPCs, incl. decoherence-wielders |
| `designs/field-instruments.md` | Field instruments: the Weatherglass and the Far Mirror |
| `designs/tide-of-the-attractor.md` | The tide of the attractor: the living world's shared tempo |
| `designs/player-remains.md` | The remains of the player: death and rebirth as field acts |
| `designs/deep-field-diving.md` | The diving bell: the craft that descends into the strata |
| `designs/pocket-cosmos.md` | The pocket cosmos: a window grown inward |
| `designs/the-reading-ahead.md` | The reading ahead: prophecy as reading the field's momentum |
| `designs/signature-predator.md` | The signature predator: the field that learns your hand |
| `designs/resonance-tutor.md` | The resonance tutor: learning to channel from your own past hands |
| `designs/mouths-eye.md` | The mouth's eye: tasting the field, eating it as an act |
| `designs/life-signal.md` | The life-signal: the vitality classifier (does it breathe?) |
| `designs/reason-field.md` | The reason field: the decision layer made field |
| `designs/shared-ledger.md` | The shared ledger: a window's society read off the Q4 op-stream |
| `designs/weather-not-storm.md` | Weather, not storm: the provenance classifier over the danger layer |
| `designs/patient-field.md` | The patient field: human-scale time as a local quantity |
| `designs/fate-of-a-window.md` | The fate of a window: difficulty as field state, not game setting |
| `designs/schema-that-settles.md` | The schema that settles: the Q4 op-schema, settled |
| `designs/house-that-steers.md` | The house that steers: the ruin and the building as field architecture |
| `designs/farm-that-feeds.md` | The farm that feeds: agriculture as grown, tide-fed coherence |
| `designs/coherence-highway.md` | The coherence highway: ground transport as steering infrastructure |
| `designs/wound-remembered.md` | The wound remembered: the deliberate break of the phi-lock |
| `designs/the-burden.md` | The burden: channeling as a loan with interest |
| `designs/the-name.md` | The name: naming as a field act |
| `designs/sleep.md` | Sleep: the field's fastest reader, at rest |
| `designs/the-map.md` | The map: the player-drawn chart as a field instrument |
| `designs/seed-garden.md` | The seed-garden: a vault that holds the window's orders |
| `designs/the-chronicle.md` | The chronicle: a settlement's record, made narrative |
| `designs/worn-field.md` | The worn field: clothing as a field-state |
| `designs/window-guests.md` | The window's guests: the traveller as walking provenance |
| `designs/the-inheritance.md` | The inheritance: the will as a field act |
| `designs/the-festival.md` | The festival: the commons' one chord, a settlement's joy |
| `designs/the-clock.md` | The clock: a field watch reading the local tempo |
| `designs/the-mirror.md` | The mirror of the self: reading your own maintenance |
| `designs/the-funeral.md` | The funeral: the field's communal handling of its dead |
| `designs/the-cooked-field.md` | The cooked field: a meal as a composed regime |
| `designs/the-cold.md` | The cold: a window's winter, the long thin as a season |
| `designs/the-exile.md` | The exile: the ban made field-honest |
| `designs/the-election.md` | The election: choosing a steward is reading the ledger's momentum |
| `designs/the-bell.md` | The bell: the settlement's warning instrument |
| `designs/the-silence.md` | The silence: the world's voice, read by its absence |
| `designs/the-observatory.md` | The observatory: the settlement's reading room |
| `designs/the-apprenticeship.md` | The apprenticeship: craft passed hand to hand |
| `designs/the-family.md` | The family: the shared persistent-Pi anchor |
| `designs/the-flood.md` | The flood: the harvest that drowns |
| `designs/the-treaty.md` | The treaty: the compact between windows |
| `designs/the-lantern.md` | The lantern: the carried night-read |
| `designs/the-seeker.md` | The seeker: the instrument that points at one named thing |
| `designs/the-child.md` | The child: the fresh line, the run born in its window |
| `designs/the-echo.md` | The echo: the field's memory, heard |
| `designs/the-stillness.md` | The stillness: the field at absolute rest |
| `designs/the-oath.md` | The oath: the vow within a window, the pledge the field can hold |
| `designs/the-healer.md` | The healer: the long bind and the healer's toll |
| `designs/the-compass.md` | The compass of intent: the instrument of the field's attention |
| `designs/the-memory-palace.md` | The memory-palace: the settlement's chosen memory, made architecture |
| `designs/the-language.md` | The language: the field's script, the sites as text |
| `designs/the-census.md` | The census: the settlement's population as a field read |
| `designs/the-threshold.md` | The threshold: the boundary-mark the field respects |
| `designs/the-blight.md` | The blight: the field's life turned against the field |
| `designs/the-window-year.md` | The window's year: the composed long-rhythm calendar |
| `designs/the-hourglass.md` | The hourglass: the duration instrument, the clock's accumulated twin |
| `designs/the-walk.md` | The walk: the un-roaded crossing, the pedestrian's relation to the gradient |
| `designs/the-fallow.md` | The fallow: a window's generational depletion, the economic face of the decay arc |
| `designs/the-pilgrim.md` | The pilgrim: the named-place walk as a field act |
| `designs/the-tide-staff.md` | The tide-staff: the planted standing gauge, a settlement's own tide-instrument |
| `designs/the-sea.md` | The sea: the field's water, the designed middle of the vertical |
| `designs/the-tool.md` | The tool: the rung-matched work object |
| `designs/the-vigil.md` | The vigil: the long watch through the dark, the nocturnal guard |
| `designs/the-working-song.md` | The working-song: music for labor, the coordinated rhythm that makes work a coherent act |
| `designs/the-feral-instrument.md` | The feral instrument: the waking thing, the kept structure that outlived its keeper's intent |
| `designs/the-atlas-of-windows.md` | The atlas of windows: the traveler's record of every window seen |
| `designs/the-drift-road.md` | The drift-road: the tide's verdict, both branches designed as gameplay |
| `designs/the-scar-lifecycle.md` | The scar-lifecycle: the wound's fate — heal, persist, or become a place |
| `designs/the-interstitial.md` | The interstitial: the sparse medium the windows float in |
| `designs/the-market.md` | The market: the settlement's exchange, made honest by the law itself |
| `designs/the-scavenger.md` | The scavenger: the denizen of the spent, the fit creature that lives on what a window discards |
| `designs/the-school.md` | The school: collective teaching as a phase-locked band, the apprenticeship made a group |
| `designs/the-sea-floor.md` | The sea-floor: the reef where the water meets the deep, the vertical's first interface |
| `designs/the-dawn.md` | The dawn: the field's re-birth each day, the transition read |
| `designs/the-commensal.md` | The commensal: the order-side companion, the field's first cooperative creature |
| `designs/the-gift.md` | The gift: the un-booked giving, the honest inverse of the market |
| `designs/the-dispute.md` | The dispute: adjudication by the field, the disagreement settled by the law itself |
| `designs/the-window-pulse.md` | The window's pulse: the collective healthmeter, the settlement's life as a beating read |
| `designs/the-zenith.md` | The zenith: the vertical's ceiling, the edge of the window's atmosphere |
| `designs/the-stratum-read.md` | The stratum-read: the field's kept past read as an instrument |
| `designs/the-harbor.md` | The harbor: the settlement's door to the between |
| `designs/the-story.md` | The story: the settlement's myth made a field-memory, the told version of the chronicle |
| `designs/the-rite-of-passage.md` | The rite of passage: the designed ceremony of a field-threshold, the becoming's honoring act |
| `designs/the-mirror-creature.md` | The mirror-creature: the field's reflective stranger, the stranger that wears your pattern |
| `designs/the-loan.md` | The loan: credit as a field act, forward order-borrowing |
| `designs/the-fall.md` | The fall: the moment the gradient owns you, the one movement with no skill-buff |
| `designs/the-swim.md` | The swim: the body in the water medium, the walk's fluid form |
| `designs/the-bedrock.md` | The bedrock: the window's absolute floor, where everything precipitates onto |
| `designs/the-cave.md` | The cave: the vertical's hollow, the deep's openness read as itself |
| `designs/the-landform-name.md` | The landform-name: the named land, the-name's scope dial at landscape scale |
| `designs/the-witness.md` | The witness: the field's own eye, the neutral stranger that only watches |
| `designs/the-lock.md` | The lock: the becoming-permanent act, a binding deliberately made irreversible |
| `designs/the-commons-tithe.md` | The commons-tithe: the settlement's collective contribution, how a window funds its shared order |
| `designs/the-marsh.md` | The marsh: the slow sea, the shallow textured water that hides |
| `designs/the-husbander.md` | The husbander: the wild-care practice, tending what you do not own |
| `designs/the-guardian.md` | The guardian: the defensive stranger, the being bound to a named place that keeps it |
| `designs/the-archive.md` | The archive: the settlement's raw record, the memory stack's un-curated under-layer |
| `designs/the-granary.md` | The granary: the storehouse, the settlement's everyday order held against the lean |
| `designs/the-wind.md` | The wind: the directional weather, the weather stack's flow-face |
| `designs/the-season-change.md` | The season-change: the turn, the designed passage between a window's tides |
| `designs/the-cart.md` | The cart: the wain, the road's vehicle that rides the highway's gradient |
| `designs/the-breath.md` | The breath: the diver's air, the body's finite reservoir at depth |
| `designs/the-herald.md` | The herald: the announcing stranger, the being that tells the field's news before it arrives |
| `designs/the-toll.md` | The toll: the border economy, what a settlement charges at its door to the between |
| `designs/the-compost.md` | The compost: the turning, spent order deliberately fed back to the field |
| `designs/the-carry.md` | The carry: the pack, the designed physical weight a body carries and its field-cost |
| `designs/the-climb.md` | The climb: rising on the field, the body gaining height against the gradient |
| `designs/the-gatekeeper.md` | The gatekeeper: the threshold's human office, the person who reads who may enter |
| `designs/the-causeway.md` | The causeway: the raised crossing, a built way over the water that hides |
| `designs/the-rain.md` | The rain: the nourishing weather, the flood's gentle twin, the weather stack's harvest-weather |
| `designs/the-spring.md` | The spring: the wellspring, a fixed bounded place where the field's order rises of itself |
| `designs/the-mimic.md` | The mimic: the deceptive stranger, the being that wears a shape it is not |
| `designs/the-stilling.md` | The stilling: the voluntary quiet, the deliberate inner act of holding oneself still |
| `designs/the-roost.md` | The roost: the wild's home, the place where the field's creatures live |
| `designs/the-dive.md` | The dive: the willed descent, the deliberate act of choosing to go down |
| `designs/the-between.md` | The between: the cosmology of the field's own outside, the dark the windows float in |
| `designs/the-beacon.md` | The beacon: the sown standing light, the fixed mark a settlement plants at its edge |
| `designs/the-shout.md` | The shout: the body's loud field-call, the tool-less alarm and the self-broadcast in one |
| `designs/the-moth.md` | The moth: the light-drawn stranger, the being that covets brightness |
| `designs/the-quarry.md` | The quarry: the open cut, the deliberate mining-ground where a window takes order from the deep's face |
| `designs/the-shepherd.md` | The shepherd: the gathering stranger, the being that collects the wild's own |
| `designs/the-archivist.md` | The archivist: the raw record's keeper, the person whose office is to not curate |
| `designs/the-desert.md` | The desert: the dry land, the living regime of absence |
| `designs/the-river.md` | The river: the living line, the one great linear landscape, a path and a home at once |
| `designs/the-broker.md` | The broker: the trading stranger, the being that carries rarity across windows |
| `designs/the-smell.md` | The smell: the field's scent, the read that comes on the wind before you look |
| `designs/the-wage.md` | The wage: the paid share, labor priced, the market's time-honored form |
| `designs/the-spring-caretaker.md` | The spring-caretaker: the well's person-office, the settlement's keeper of its own source |
| `designs/the-migration.md` | The migration: the great moving, the designed passage of a collectivity across the field |
| `designs/the-ford.md` | The ford: the river's natural shallow, the crossing the water makes safe of itself |
| `designs/the-estuary.md` | The estuary: the salt-mouth, the third water where the river meets the sea |
| `designs/the-tutelary.md` | The tutelary: the shadow-kin, the stranger bound to a line, not a place |
| `designs/the-midwife.md` | The midwife: the birth-ward, the office that receives the new line's first maintenance |
| `designs/the-inn.md` | The inn: the held bed, the traveler's roofed room in a settlement, the window-guest's held shelter |
| `designs/the-blizzard.md` | The blizzard: the white driving storm, cold and wind and driven snow merged into a moving obscuring white-out |
| `designs/the-understory.md` | The understory: the canopy floor, the vertical's forest middle, the shade-band between the zenith's height and the ground's footprint |
| `designs/the-mirage.md` | The mirage: the deceitful read, the weather that makes the field mis-read itself |
| `designs/the-mint.md` | The mint: the struck unit, order made a named, held, physical token |
| `designs/the-orchard.md` | The orchard: the planted stand, the perennial grove that outlasts a season |
| `designs/the-delta.md` | The delta: the branched mouth, the living line's fan, the corpus's only network-region terrain |
| `designs/the-sledge.md` | The sledge: the winter sled, the loaded carriage built for the white and the deep cold |
| `designs/the-raft.md` | The raft: the flat freight, the river's bulk-carrier, the water-borne barge that rides the current |
| `designs/the-eclipse.md` | The eclipse: the window's darkening, a rare scheduled moment when the read goes dark |
| `designs/the-pooka.md` | The pooka: the fear-fed, the stranger that eats panic, drawn and strengthened by the field's riled |
| `designs/the-chant.md` | The chant: the held voice, a sustained single voiced act that holds a working in place |
| `designs/the-touch.md` | The touch: the skin-read, the sixth sense, the field read by contact |
| `designs/the-siren.md` | The siren: the resonant lure, the stranger that calls by harmonizing with your own signature |
| `designs/the-meadow.md` | The meadow: the open pasture, the grazed common, the wild middle between the cultivated and the wasted |
| `designs/the-canal.md` | The canal: the dug water, an engineered waterway, the river's freight-lane made to reach the sea |
| `designs/the-cistern.md` | The cistern: the held water, the built store of the spring, water kept against the dry |
| `designs/the-meteor.md` | The meteor: the falling bright, the rarest sky-event, a body that arrives |
| `designs/the-balefire.md` | The balefire: the warning-light, the beacon's hazard-form, light raised to alarm |
| `designs/the-baptism.md` | The baptism: the first-name, the ceremony of giving a new being its name at birth |
| `designs/the-palanquin.md` | The palanquin: the carried seat, the conveyance that carries a person, not a load |
| `designs/the-fog.md` | The fog: the held blur, the weather that hides what it wraps |
| `designs/the-drought.md` | The drought: the receding, the event of the ground's water leaving, distinct from the dry land itself |
| `designs/the-caravan.md` | The caravan: the long-train, the organized trading convoy, the broker's goods at many-body scale |
| `designs/the-dune.md` | The dune: the moving sand, the ridge the wind walks across the desert, the land that migrates |
| `designs/the-terrace.md` | The terrace: the stepped hold, farming cut into a slope, the climb made to feed |
| `designs/the-votive.md` | The votive: the giving-to-the-field, an offering left at a place, the gift's other face |
| `designs/the-shrine.md` | The shrine: the built remembrance, the funeral's register made a place, the votive's leaving given a built home |
| `designs/the-lightning.md` | The lightning: the sky's sudden, the storm's gathered charge letting go at once, the discharge that is release not message |
| `designs/the-crossroads.md` | The crossroads: the meeting of ways, the way's place where the road branches, the legible choice-point |
| `designs/the-incantation.md` | The incantation: the spoken perturbation, the field's script written back, the directed-manipulation grammar the Language reads but no voice speaks |
| `designs/world-difficulty.md` | World difficulty: the turbulence dial, the world-birth setting that scales the field's ambient activity within its own law, never a punishment, never a power source |
| `designs/the-rumor.md` | The rumor: the told-unverified, the story that travels before the truth does, the field's own hearsay that dies at the read |
| `designs/the-generations.md` | The generations: the long chain, the succession made a people, the settlement that outlives its founders because the field holds what they made |
| `designs/the-shaft.md` | The shaft: the dug descent, the vertical's engineered line, the mine's straightness made a place, the deep made reachable by design |
| `designs/the-hand-over.md` | The hand-over: the steward's passing, the office-to-office transition as an audited, legible transfer of how the settlement runs |
| `designs/the-seacraft.md` | The seacraft: the open-water vessel, the sailable hull that rides the wind's current across the sea, the raft's and the ferry's sea-going successor |
| `designs/the-whirlpool.md` | The whirlpool: the spinning drain, a rotating low-q vortex that pulls what enters it, the water's own trap, the first rotating hazard |
| `designs/the-tunnel.md` | The tunnel: the dug passage, the horizontal's engineered line, the shaft's horizontal twin, the under-hill crossing that never mints |
| `designs/the-waterfall.md` | The waterfall: the falling water, the cliff's water, the descent made visible, gravity's own display that converts nothing |
| `designs/the-crane.md` | The crane: the lifted load, the mechanical advantage that never mints, the carry's vertical assist |
| `designs/the-comet.md` | The comet: the passing bright, the sky's visitor, the returning body, the meteor's periodic cousin — never a portent |
| `designs/the-bog.md` | The bog: the soft ground, the ground that gives, the marsh's deeper cousin, the step that sinks — legible before you commit |
| `designs/the-atoll.md` | The atoll: the ring reef, the sea's crown, the reef made a ring, the boundary that encloses a still middle |
| `designs/the-anchor.md` | The anchor: the held station, the reversible mooring, the hold against the drift, the seacraft's resting |
