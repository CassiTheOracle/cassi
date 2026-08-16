# Field Music — The World Sings; Sonification Is a Field Operation

**Question under design:** how the CassiCraft world is *heard*. The coherence
landscape that draws birds and fish (the silhouette observation,
`field-emergent-ecology.md`) can be *listened to*: the same published field
channels (q, ε², ρ, ∇(g·Φ), FieldVel) that drive the reader and the sky can be
sonified into a world with an informative ambience. And the deepest claim: the
thesis of the whole project — "intelligence is steering the flow of coherence"
(README) — becomes a **composition system**: music *is* steering the flow of
coherence, made audible and intentional. Channeling the field IS playing it;
composing a coherence score IS programming it.

This is the **phenomenology and feel** document for audio, in the style of
[`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) (the sky doc):
it designs *what the world sounds like and what that means*, grounds every
mapping in the published channels the async domain already produces, and flags
every aesthetic choice **[design]**. It does **not** build the audio engine —
that is the domain of the mod-technology workstream.

Companion to:
- [`coherence-magic.md`](./coherence-magic.md) — **THE dependency.** The player as
  a coherence source; the six abilities as field operations; the coherence
  reader (Sense); overdraw → full-cascade discharge (§4.3). **This doc's
  "channeling is playing" and "overdraw is feedback" inherit that boundary.**
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — the aurora
  as the (1−q) glow along coupling lines into a drain (§3); **the aurora's field
  tone is this doc's sky chord.** The sky reads the field un-instrumented.
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — organisms as
  moving coherence stores, each at its cascade rung; **a herd is a chord** (§3.2
  this doc). The biosphere's attractor basins are its sonic form.
- [`field-archaeology.md`](./field-archaeology.md) — residue reads as an ε²
  ghost (§3.1); **the ghost-halo hum is archaeology's sonic twin of the reader
  scan.**
- [`energy-harnessing.md`](./energy-harnessing.md) — the (1−q) glow (§2) and
  **its tone**; the constraint economy (§6) — **music costs coherence**; the Qi
  bath (§4.4) — **a region's hum.**
- [`async-field-domain.md`](./async-field-domain.md) — **Q4, the player-return
  channel (§7)**: a composed/played coherence score is a Q4 input sequence; the
  published channels (§2.1) are what the sonification map samples.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical
  numbers; cited, not re-derived.
- [`field-hazards.md`](./field-hazards.md) — **NOW EXISTS.** The companion hazard
  doc. Its mechanics are consistent with this doc's hazard-audio mappings: the
  **storm IS a c_s-traveling ε² front** (field-hazards §2.1) whose §2.3 pre-warnings
  ("auroras flicker / reader ε² noise rises / the (1−q) glow shifts") this doc's
  §2.2 growl is the *audible* form of; the **desert IS a regional q collapse**
  (field-hazards §3.1) whose silence this doc's §2.3 is. Both audio forms are
  cross-referenced to field-hazards §2/§3 below.

Project precedent (read-only, the REAL sonification work — cited, not replicated):
- `CassiCosmos/research/sound_coherence_note.md` — **TIER-1**: the two-fluid
  field has an honest sound structure: the gapless ρ mode (acoustic branch,
  speed c_s = h₀/dt) *is* "waves of coherence"; the gapped ε mode (optical
  branch, ω_gap² = ω₀²(1+φ) ≈ 52.36) oscillates in place and cannot carry
  order. **Sound is waves of coherence — in the sim, by construction.**
- `CassiCosmos/research/meshless/synth_design.md` — **implemented and
  verified**: a real-time φ-tempered harmonic bank sonifies the two-fluid
  field via a no-FFT cascade meter (rung-scale box-difference energies of q),
  R = 4 rungs on the 64³ grid, a breather drone, per-rung detune. **This is
  the engineering precedent the whole sonification map rests on.**
- `CassiTheory/speculations/creative-extensions/magic-systems.md` — creative
  ground for "casting as phase-matched field operation"; the emotion-as-gate-
  configuration reading backs "the music of the field is its coherence."

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| Sound of the field = ? | The published channels sonified: q → pitch/timbre in φ-tuned intervals; ε² → dissonance/noise; ρ → amplitude/density; ∇(g·Φ) → spatial panning; FieldVel → motion/texture. The ambience is **informative, not decoration**. |
| The world's baseline = ? | A **field-tempered ambience** — a low, φ-spaced drone over the locality's q/ρ/FieldVel, sampled at the player's position and key structures, not per-cell. |
| Auroras / storms / the desert = ? | Auroras hum a sustained chord that tracks the drain's health; a storm approach is a rising dissonant growl (audible before the reader shows it); the desert's q-collapse is **silence** — the most unsettling sound is nothing. |
| Channeling = ? | The six abilities ARE musical gestures: condense = a chord, dissolve = a dissonant release, steer = a glissando, ignite = a rising phrase, heal = a resolution, sense = the pure tone of the reader. **Overdraw = feedback (clipping)** — inherits coherence-magic §4.3. |
| Composition = ? | Players record **coherence scores** — sequences of field operations that, played back, ARE field operations (a Q4 input sequence). **Music is programming the field.** Music costs coherence; a score can drive machines (energy), calm/drive the biosphere (ecology), hold a storm back (hazards). |
| Scientific hook = ? | Sonification as a dual-use diagnostic: hear hazards early (growl), find residues (ghost-halo hum), read the sky (aurora chords), hear a distant window's health from the dark (world-seams). The in-game form of the project's real sonification work. |
| Honest gates | The φ-ratio/mapping-of-channels is physics-grounded; the *aesthetic* (which timbre, which chord) is [design]. A 64³ field per-cell is impossible to sonify — **sonify sampled points** (player locality, key structures, the sky). Music-as-field-operation is gated on Q4 like every other channeled op. Sound is an enhancement of the reader, never the only channel (a mute player loses nothing). |
| Feasibility | **Phase-1** = the sonification map as ambience + the reader's audio form (no new physics — audio presentation of published channels, riding the synth precedent). **Later** = music as field operation, composition, hazard-audio integration (gated on Q4 mechanics + the hazard doc). |

---

## 1. The sound of the field — the sonification map

The Cassandra project already sonifies this exact field. `synth_design.md`
(implemented + verified on the RX 7900 XTX rig) maps the two-fluid cascade to a
**φ-tempered harmonic bank**: sine oscillators at `f_r = f0·φ^r` (f0 = 55 Hz →
55, 88.99, 143.99, 233.02 Hz across ~2 octaves), adjacent ratios exactly φ —
*not* the equal-tempered semitone — so the bank is deliberately "irrational,"
never coalescing into a stable chord; per-rung detune (±0.35%) makes it shimmer.
A no-FFT cascade meter (box-blurred-difference energies of q at each rung
scale, R = 4 on the 64³ grid) drives per-rung amplitude. **This is the sound of
the field as the project already hears it.** Field music inherits it and extends
it per-channel.

Each published channel (`async-field-domain.md` §2.1; `corpus-reconciliation.md`
≈ 6 MiB publish: q, ε², ρ, pot, ∇(g·Φ)) maps to an audible dimension, tuned to
the theory's φ-ratios:

| Published channel | Audible dimension | Grounding | Aesthetic choice [design] |
|---|---|---|---|
| **q** (coherence) | **pitch / consonance** → a φ-tuned interval against the tonic | the "coherent band is consonant" reading: q is the organized fraction; the attractor `EY = φ·EI` is the tonic. `synth_design.md` already pitches by q's rung energies. | which pitch = the tonic, the exact interval map |
| **ε²** (decoherence) | **noise / dissonance** | rising disorder = rising dissonance → the gapped ε mode (`sound_coherence_note.md` §2) is the *optical-phonon* analog that cannot carry order — dissonance is the honest sonic form of ε². | the noise spectral shape |
| **ρ** (density) | **amplitude / density** (the envelope's hum is louder where matter is) | ρ = EY+EI is the gapless coherence carrier (`sound_coherence_note.md` §2); more matter = more carrier = louder. | absolute loudness scaling |
| **∇(g·Φ)** (the river gradient) | **spatial panning / lateral motion** | the gradient points toward matter and steers the field (`energy-harnessing.md` §1.1); the river law steers sound the way it steers everything. | the pan law, whether steepness also raises pitch |
| **FieldVel** (the medium velocity) | **motion / texture** (wind lines are audible streams) | the two-fluid medium's own flow (`vel[id]` per cell); a rotor in it spins (`energy-harnessing.md` §2.2) — an audible stream is the turbine's sonic cousin. | the texture granularity |

**Two rules keep the map honest (not decoration):**

1. **Mathematics, not motif.** Every interval lives on the φ-ladder. The attractor
   (φ-lock) is the tonic; a fully coherent region sings a single consonant φ-note.
   Dissonance is not a "danger sting" bolted on — it *is* ε² heard. The player who
   learns the intervals learns the theory's ratios (ξ = φ⁶ ≈ 17.94, φ⁻² ≈ 0.382,
   ω_gap = φ·ω₀, the canonical numbers of `corpus-reconciliation.md`).
2. **The (1−q) waste law is the efficiency hum.** Every working field system
   bleeds `(1−q)` of its throughput as glow (`energy-harnessing.md` §2). In field
   music, that same fraction is an **efficiency hum** — a soft wash that rises as
   the local field runs wasteful. It is the sonic twin of the glow: the same
   quantity, heard instead of seen. A wasteful machine is audible because the
   field is actually wasting.

**The baseline is informative, not decorative.** The default ambience is a low
φ-tempered field-ambience sampled at the player's locality, key structures, and
the sky — not decoration, but the world's state as a continuous readable hum.
The reader (`coherence-magic.md` §2, Sense) is a *tool you hold*; the sound is
the field *you stand in*. A player who cannot read the reader overlay can still
hear "this ridge is coherent" or "this well is decohering."

**The performance floor [design].** `synth_design.md` is the honest precedent:
the cascade meter is a ~5% CPU budget, 4 tiny GPU passes + a 64-byte readback
every 150 ms, R = 4 rungs (grid-limited). Field music reuses that meter and adds
per-dimensional drivers on the same low-cadence poll. A 64³ field sonified
per-cell is **impossible** — the design sonifies **sampled points**: the
player's locality (a meter over the near field), key structures (condensed
bodies, machines, a Qi bath's core), and the sky (the auroral chord, the storm's
approach). The same LOD logic that makes the meshless sites the activity map
(`chunk-field-quantization.md` §5) makes them the audio map: the field is loud
where it is organized, and organized where it is.
`[design]` the exact sample/priority list is a tuning decision; the *rule* (never
walk the 262,144-cell array for audio) is inherited from the synth precedent and
the server-tick budget (`chunk-field-quantization.md` §4).

---

## 2. Auroras hum; storms growl; the desert is silent

The sky already reads the field (`atmosphere-orbits-auroras.md` §3.3: the
aurora *is* the reader's atmospheric form — the same channels, un-instrumented).
Field music makes the sky *audible* the same way.

### 2.1 The aurora's field tone — a sustained chord that tracks the drain's health

An aurora is coherence discharging along coupling-field lines into a region where
ε² rises, re-radiating the (1−q) fraction as glow
(`atmosphere-orbits-auroras.md` §3.1, engine-real (1−q) law). Its sound is the
sonic form of that discharge: **a sustained φ-spaced chord over the active
drain** — high-q, low-ε² where the lock holds (consonant); rising dissonance as
the drain's ε² climbs and the waste fraction grows. **The chord's shape is the
drain's health.** A healthy body shows calm, slow, coherent bands
(`atmosphere-orbits-auroras.md` §3.3) — a stable, consonant chord. A wounded
body's aurora is bright and restless — the chord sharpens, its detune
(`synth_design.md`'s ±0.35% shimmer) widens into audible beating. A drain
*healing* (ε² dropping) resolves back to a clean chord; a drain *deepening*
(ε² rising) climbs toward dissonance. `[design]` the exact chord voicing is the
sky's aesthetic; the *mapping* (chord-the-shape-of-ε²-over-the-drain) is honest.

### 2.2 A storm approach is a rising dissonant growl — sound as early warning

Weather is the two-fluid waves in the envelope; storm turbulence is the region
where the ε² budget spikes — **the same decoherence that makes a carved scar on
the ground is weather in the sky** (`atmosphere-orbits-auroras.md` §1.3). Field
music makes a storm's approach *audible before the reader shows it* — the same
pre-warning `field-hazards.md` §2.3 names visually ("auroras flicker / reader ε²
noise rises"), heard instead of seen, on the c_s-traveling ∇ε² front of
field-hazards §2.1: as a weather
front travels toward the player, its leading edge of rising ε² lowers q and the
local field's hum **darkens into a growl** — a low, dissonant, rising texture
tracking the approaching storm's ε² ramp-up. The sound is early warning because
it reads the field the sound *is*; the reader is a tool you aim, the growl is the
field arriving. `[design]` the growl's spectral character is the hazard's audio
aesthetic; the *detection* (rising ε² ahead = audible dissonance) is physics.

> **Cross-reference `field-hazards.md` §2.** The storm's *mechanics* live in that
> doc — a c_s-traveling ∇ε² front (§2.1) with pre-warnings on the sky and reader
> (§2.3). This doc fixes the audio form: **a storm is audible before it is
> visible/readable, because its ε² front is the sound itself** — the growl is the
> audible twin of the §2.3 aurora-flicker / ε²-noise pre-warning. The hazard doc owns
> what a storm *does*; this doc owns that the player *hears it coming*.

### 2.3 The desert's silence — the most unsettling sound is nothing

The strongest sound in field music is the **absence of sound**. A region where
the field's coherence collapses and q falls toward the noise floor
(`atmosphere-orbits-auroras.md` §1.2: the fluid's noise level, q ~ 1e-3…1e-1) is
a region with **almost nothing to sonify** — no organized ρ to carry the envelope's
hum, no φ-lock to sing a tonic, only thin, near-silent noise. This is precisely
the **desert** of `field-hazards.md` §3 — a regional q collapse (§3.1) whose
creep warning (the "reader darkens, glow fades, life thins," §3.3) this doc's
silence is the audible form of: the desert sounds
like a vacuum because *it is one*: the field has nothing to say. The most
unsettling sound in the game is the absence of the ambience the player has
learned to trust. This is the honest end of the map: **sound is what coherence
does; where there is no coherence, there is no sound.** `[design]` the design
deliberately makes silence a *feature*, not a bug — it is the desert's signature
and the player's warning that the field here is dead.

### 2.4 The biosphere's hum — organisms each hum at their rung; a herd is a chord

An organism is a **moving coherence store** — a self-supporting, φ-locked body
held at a cascade depth (`field-emergent-ecology.md` §2.2, §3.2). Its internal
cascade layers *are* its rungs, and each rung is an audible φ-interval. **An
organism hums at its rung-depth** — a small φ-tone determined by how deep its
φ-lock runs. Consequences:

- **A herd is a chord.** Creatures near each other, at different rung-depths,
  stack φ-intervals into a chord — the biosphere's hum is literally the field's
  living organization made audible. A flock of shallow, agile morphs
  (birds/fish, living-plain regimes, `field-emergent-ecology.md` §4.2) hums a
  high, bright, changing chord; a deep, layered φ-locked organism (a shell /
  flower morphology, the coherent-ridge regime) hums a lower, richer, steadier
  tone.
- **The (1−q) glow is audible as a wheeze.** A creature maintaining its φ-lock
  against a drain glows proportionally to its disorder (`field-emergent-ecology.md`
  §5.2) — and in field music it *wheezes* the same fraction. A starving or wounded
  creature is louder-and-waster in sound exactly as it is in light. The
  health-meter and the hunt-targeting diagnostic are heard as well as seen.
- **A dying creature's last glow (announcement) is a fading, brightening hum**
  — the same (1−q) death-signal `field-archaeology.md` §2.1 reads as the glow that
  draws the eye, heard as the fade that draws the ear.

`[design]` the exact per-rung instrument voices are the ecology's aesthetic; the
*mapping* (rung-depth → φ-interval, (1−q) → waste hum) is inherited from the
field economy.

---

## 3. Channeling is playing — magic as an instrument

`coherence-magic.md` is explicit: **there is no spell — there is a manipulation of
ρ, ε², or ∇(g·Φ) at a scale** (§2), and the player is a bounded EY injector and an
ε² vent (§1). Field music completes the identity: **what the player does to the
field, the player hears — and because the field is tuned to φ, what the player
hears is *music.*** The six abilities ARE musical gestures:

| Ability | Field operation (coherence-magic §2) | Musical gesture |
|---|---|---|
| **Sense** | read local q/ε²/∇(g·Φ), rung 0 | **the pure tone of the reader** — a clean, informative φ-tone: the reader as a tuning fork; coherent = consonant, decohering = sharpening |
| **Condense** | raise ρ past τ_c where q is high | **a chord** — the newly-solid matter sings a stable φ-chord at the chosen rung |
| **Dissolve** | raise local ε² above its floor | **a dissonant release** — the carved matter's ε² rises and the sound unwinds; a deliberate, aimable dissonance |
| **Steer** | inject a current along ∇(g·Φ) | **a glissando** — a φ-slide along the gradient you steer, rising as you push with the field, flatting against it |
| **Ignite** | an organized-perturbation front | **a rising phrase** — a propagating EY pulse along the wave operator; the front *is* moving organization, so it sounds like a phrase climbing through rungs |
| **Shield / Heal** | suppress ε², restore coherence | **a resolution** — injecting opposing EI re-locks EY = φ·EI, and the local field resolves to the tonic; the resolution IS the resolve (same word, same sound) |

**Overdraw = feedback.** The load-bearing boundary is `coherence-magic.md` §4.3:
overdrawing past the vent's capacity tips the injection from organized to random
perturbation, the φ-lock fails, and the accumulated ε² relaxes in one
**full-cascade discharge**. Field music's form of that is **audio feedback — a
scream/clipping** — the phase-matched musical signal saturating into raw noise
as organized perturbation collapses to random perturbation. The sound is not a
"you lose health" sting: it is the honest audio of the field's own organization
*being lost* — the tonic shattering into clipping as the organized branch goes
random. The escalation is audible in the same φ-terms as the physics: within
budget, the gesture stays in-tune (organized, constructive); past budget, it
cracks (random, destructive). `[design]` the exact clipping curve is the overdraw
aesthetic; the *identity* (overdraw = organized→random = tonal→noise) is the
physics of §4.3.

> **The player who learns the music learns the field.** Because every gesture is
> a real field operation and every operation has a real φ-sound, learning to
> "play" the magic is learning the field's ratios — the corpus's "magic feels
> like physics" made audible. A player who can hear overdraw coming (the rising
> dissonance of the vent backing up) has learned the ε² vent before the reader
> even flags it. Magic is an instrument; the instrument is the field.

**Resonance is ear-training.** `coherence-magic.md` §3.1: channeling is more
efficient when aligned with the local field's natural rhythm (matching the
`ω₀²` oscillation, pushing *with* ∇(g·Φ)). Field music makes that coupling
audible: **pushing with the field sounds consonant and costs less vent; pushing
against it sounds dissonant and costs more.** The timing minigame becomes
ear-training, the efficiency multiplier becomes the heard chord.

`[design]` the mapping from "operation" to "interval/sound" (which chord, which
glissando start/stop) is the audio aesthetic; the *structure* (each op is a
φ-scaled manipulation, hence a φ-musical gesture) is grounded in
`coherence-magic.md` §2.

---

## 4. Composition — music as a field operation

**The deepest design.** Because every channeled field operation IS a gesture, and
every gesture IS a field manipulation, the operations can be **recorded and
replayed as sequences** — and a played-back sequence is a **sequence of field
operations**. That is a **coherence score**: a musical composition that, played
back, steers the field. **Music is programming the field, literally.**

This is the thesis of the project made into a game system: the README's "the
two-fluid field is the substrate; blocks, mobs, and planets are its
epiphenomena" and the *theme* "intelligence is steering the flow of coherence"
both collapse into one mechanical statement — **a player who composes a score is
encoding a sequence of field operations, and the field responds to the score the
way it responds to any organized perturbation.** A lullaby that heals, a dirge
that dissolves: the music is not flavored as magic — it *is* magic, because the
score is field operations.

### 4.1 The mechanical frame — a Q4 input sequence

`async-field-domain.md` §7 Q4 is the player-return channel: player edits/injections
round-trip into the domain **as job-dict inputs** — every channeled op is a
consumer of that channel (`coherence-magic.md` §5.1: a per-op record
`{op, worldPos, rung, magnitude, sustain}` batched into the player-return job).
**A coherence score is a timed sequence of those records.** Playing a score = 
emitting its ops through the Q4 channel in order, at the score's tempo. The score
is therefore **gated on Q4 exactly like every other channeled op** — it is not a
separate magic; it is channeling with a musical editor and a sequencer in front
of it. The ops it emits are the same condense/dissolve/steer/ignite/heal records;
the score is just *composition of them*.

**Cost — music is a field operation, so it spends coherence.** Every op in a
score carries the op's cost (`coherence-magic.md` §2 cost column), and a playing
score is *the player sustaining a sequence*, so its total cost is the constraint
economy (`energy-harnessing.md` §6) applied to audio: **music spends coherence,
and the (1−q) waste is audible as the efficiency hum.** A score that overdraws
its sustain hits the §4.3 boundary — the feedback/clip of §3 — which holds mid-
score, not just while channeling live. Music is a real field act with a real
budget; there is no free music any more than there is free condense.

### 4.2 What a score can do — the ties

Because a score is a sequence of field operations, it inherits everything field
operations do:

- **Energy — a played score can drive machines.** A sustained, coherent field
  manipulation is the input machines consume (`coherence-magic.md` §5.2); a score
  that *holds* a high-q region (a sustained heal/condense at a chosen rung) is a
  **hand-held pump** running a machine — a collector drawing on organized
  coherence (`energy-harnessing.md` §2). A "power plant" can be a looped score
  that keeps a capacitor supplied. The score is the machine's fuel tape. **The
  no-free-energy gate (`field-hazards.md` §5.3) that closes hazard-farming closes
  score-farming too** — a score can't be written to *cause* a storm or desert and
  harvest its drains; a score, like the auroral collector, is amplitude-capped and
  net-negative, never a coherence mint.
- **Ecology — a shepherd's tune.** Mobs steer by the river law and move with the
  field's q/ε² (`chunk-field-quantization.md` §2.2, `field-emergent-ecology.md`
  §5.2); a score that steers the local coherence can **calm or drive the
  biosphere** — a sustained coherent phrase draws creatures toward a ridge (they
  drift toward the coherence the score raises), a dissonant phrase disperses them
  (they avoid the scar the score sheds). A "shepherd's tune" is literal: it moves
  the field's coherence, and the flock follows the coherence.
- **Hazards — a score can hold a storm back, at cost.** A storm is rising ε²
  (`atmosphere-orbits-auroras.md` §1.3); a score that sustains a local high-q /
  low-ε² hold (a continuous shield/heal, `coherence-magic.md` §2 Shield/Heal) is
  anti-corruption (`energy-harnessing.md` §5.4) — it holds the dissolution
  threshold. A played score can be a **calm maintained against the approaching
  growl**, at a sustained coherence cost. The tension is honest: holding a storm
  out spends the budget the storm's field is draining; the score that keeps the
  storm at bay is the score that keeps the player's coherence up, and it is a net
  cost (`energy-harnessing.md` §6 — no free hold).
- **Archaeology / seams — the score as a probe.** A score is also a *recorded
  read* (the Sense gesture is a pure tone); a player can "play" the read-back of a
  region's field the way a musician plays an instrument — **hearing a score that
  was recorded over a residue site carries the ghost-halo hum into the playback**
  (the archive doubles as a field recording).

`[design]` the interface (how a player records/edits/replays a score) is the
mod-technology design; the *physics* (a score = an ordered Q4 op sequence = a real
field act) is grounded.

### 4.3 The honest scope of the claim

"Music is programming the field" is asserted *mechanically*, not mystically: a
score is an ordered list of Q4 field-operation records, and the field responds to
the sequence the way it responds to any organized perturbation sequence. The
theory's phase-matching factor ℳ (`magic-systems.md` §1: organized, phase-matched
perturbation has ℳ ≈ 1 and an O(1) effect against random ℳ ≈ 0) is the *reason*
a disciplined score works at all: a score is exactly a **deliberately organized,
phase-timed perturbation** — the definition of a working. That is the real tie to
`magic-systems.md`: the creative theory says a working is a phase-matched field
operation; field music makes composition the game's machine for authoring
phase-matched sequences.

---

## 5. The scientific hook — dual-use

The coherence reader is a gameplay system AND a science tool: it renders the
published channels the scientist's probe also reads (`field-emergent-ecology.md`
§5.1 — the player's tool and the scientist's probe share the exact channel).
Field music extends that dual-use to hearing:

| Sonic diagnostic | Field it reveals | Gameplay + science twin |
|---|---|---|
| **The growl** of an approaching storm (§2.2) | rising ε² ahead | early warning (game) + the weather band's ε² front (the sky doc's storm, read auditorily) |
| **The aurora's chord shape** (§2.1) | the drain's ε² health | read the sky's health (game) + the (1−q) discharge law heard (atmosphere §3) |
| **The ghost-halo hum** of a residue (§2.4 / archaeology) | a q-locked deep core + ε² ghost halo | find residues by ear (game) + archaeology's residue-signature (§3.1) sonified |
| **A distant window's hum from the dark** | the beacon's coherence reaching you | find/guard the seam by ear (game) + the seam's coupling (world-seams) |
| **The biosphere's chord** (§2.4) | each creature's rung-depth, the herd's organization | spot deep organisms / a herd (game) + the ecology's rung-layered organisms heard |
| **The (1−q) efficiency hum** (§1) | how wasteful a system runs | hear a wasteful machine (game) + the energy doc's waste law heard |

The reading is the same instrument `field-archaeology.md` calls the 
archaeologist's instrument and `field-emergent-ecology.md` calls the observation
tool: **Sense + sound read the same channels; sound is the reader's hands-free
form.** The player who learns to hear the field can act where the overlay would be
cumbersome (while moving, while in combat, from a distance the reader doesn't
reach) — and the sound is *the in-game form of the project's real sonification
research*: `synth_design.md`'s verified φ-tempered bank and `sound_coherence_note.md`'s
"sound is waves of coherence" are the actual science, given a gameplay surface.

> **Dual-use, stated plainly.** The same sonification that makes the world beautiful
> makes it *readable*: sound presents the published channels that the reader and the
> sky also present, so the sound system is a diagnostic the way the reader is. It is
> not an adornment; it is a second instrument on the same field, and it connects the
> game to the project's real sonification work as the in-game form of that work.

---

## 6. Honest gates

**The φ-ratios and the channel→audible mapping are physics-grounded; the
aesthetics are [design].** The line is drawn exactly where `atmosphere-orbits-auroras.md`
draws its (§5c):
- **Grounded:** the channels (q, ε², ρ, ∇(g·Φ), FieldVel), the φ-tempered interval
  structure (`synth_design.md`), the ρ-carries-coherence / ε²-kills-it sound physics
  (`sound_coherence_note.md`), the (1−q) waste law as the efficiency hum
  (`energy-harnessing.md` §2), the overdraw boundary (`coherence-magic.md` §4.3).
- **[design]** the *which-timbre / which-chord / which-glissando* choices — the
  aesthetic layer over the honest mappings, exactly like the aurora's streak/
  colors (`atmosphere-orbits-auroras.md` §3.3).

**Sonify sampled points, never the whole grid.** A 64³ = 262,144-cell field
sonified per-cell is impossible (CPU + audio budget). The design sonifies the
player's locality, key structures (condensed bodies, machines, a Qi bath core),
and the sky — the same LOD logic as the meshless activity map
(`chunk-field-quantization.md` §5), riding `synth_design.md`'s verified ~5% CPU
budget. `[design]` the sample/priority list is tuning; the rule (never walk the
262,144-cell array for audio) is inherited.

**Sound is an enhancement of the reader, never the only channel.** A mute player
must not lose information: every diagnostic above (storm, residue, aurora health,
window health, overdraw risk) is **also readable on the reader overlay and the
sky.** Sound is a hands-free, range-reaching *enhancement*, not a required sense.
A player with sound off plays the game the reader-based docs already specify; a
player with sound on gets the same information more ambiently. This is a hard
accessibility rule, not a nice-to-have.

**Music-as-field-operation is gated on Q4 like everything else.** A coherence
score is a sequence of Q4 input records; it is a *consumer* of the player-return
channel. It cannot exist before the Q4 schema and cadence are resolved
(`coherence-magic.md` §5.1, Q1/Q2; `async-field-domain.md` Q4). Field music does
not invent a lane — it composes existing ones.

---

## 7. Feasibility verdict

**Phase-1 (feasible, no new physics): the sonification map as ambience + the
reader's audio form.** The ambience (the φ-tempered field-ambience sampled at the
player locality / key structures / the sky, per §1) and the reader's pure tone
(§3, Sense) are **audio presentation of the already-published channels** — the
q/ε²/ρ/∇(g·Φ)/FieldVel snapshot (`corpus-reconciliation.md` ≈ 6 MiB publish;
`async-field-domain.md` §2.1) that the sampler already consumes. No new physics,
no new channel, no Q4 write — only a new *consumer* of the existing publish, on
the cost profile of the verified synth precedent (`synth_design.md`: the cascade
meter + small harmonic bank, ~5% CPU). This is the audio twin of the Phase-1
sense-read path (`coherence-magic.md` §5.1: a read-only consumer of the publish).

**Later (gated):**
- **Music as a field operation** (channeling's gestures audible, §3, and overdraw
  = feedback) — gated on the **Q4 player-return channel** being a real write path
  (`async-field-domain.md` Q4; `coherence-magic.md` §5.1 Q1/Q2). The *sounds* of the
  gestures are Phase-1-presentable (they track the ops' effects on the publish); the
  *gated claim* — that the gesture reliably costs coherence and overdraw clips — needs
  the Q4 mechanics.
- **Composition / coherence scores** (§4) — gated on BOTH Q4 and the op-schema
  (`coherence-magic.md` §5.1) being resolved; a score is a Q4 op sequence.
- **Hazard-audio integration** (the storm's growl as a gated early-warning, the
  desert's silence) — gated on the **`field-hazards.md` doc** (§2/§3: the storm =
  `c_s`-traveling ε² front, the desert = regional `q` collapse) that owns the
  hazard mechanics; the audio forms are specified here, the hazard *behavior*
  is that doc's.
- **Ecology / aurora / archaeology / seam audio** (the herd chord, the aurora tone, the
  ghost-halo hum, the distant window's hum) — each rides its source doc's Phase gate:
  the aurora chord needs the auroral rendering (`atmosphere-orbits-auroras.md` §6,
  later); the herd chord needs the biosphere (`field-emergent-ecology.md` §7, later);
  the ghost-halo hum needs the residue model + core sample (`field-archaeology.md` §7,
  Phase-1.5+); the window hum needs the seam's audio reach (world-seams).

**Binding risks, in order:** (1) **Q4** — music-as-field-operation is a Q4 consumer,
and everything after Phase-1's ambience rides it; (2) **the hazard doc** — the growl
and the silence need the storm's mechanics defined before they can *do* anything,
though the audio forms are already specified here; (3) **audio budget** — the sampled-
point design rides the verified synth ~5% profile, but the multi-source ambience must
be measured under a live server tick; (4) **the aesthetic line** — keeping every
[design] choice honest against the grounded φ-mappings is a discipline the docs of this
corpus already practice.

**Verdict.** Field music is sound *as the coherence reader is light*: a second
instrument on the same published channels, grounded in the project's already-built and
-verified sonification (`synth_design.md`, `sound_coherence_note.md`). The ambience and
the reader's tone are Phase-1 audio presentation with **zero new physics** — the same
"no new channel, only a consumer of the publish" discipline as the Phase-1 sense-read.
The composition claim is gated on Q4 like every other channeled op, and it is the
design's deep tie: **the thesis that intelligence steers the flow of coherence becomes
the game's composition system — music is the tuning of the field, and the player who
learns to play it has learned the field.**

---

## Open questions

1. **Sampled-point list and priority.** Which structures get audio beyond the player
   locality and the sky (machines? the nearest Qi bath core? the nearest condensed
   body?), and how the set is scheduled without walking the grid. Phase-1 tuning.
2. **The growl as gated early-warning — is it a *gate* or a *cue*?** Does a storm's
   ε² front reliably distinguish "approaching storm" from "nearby scar" by sound
   alone (static ε² scar vs. rising, moving ε² front)? Needs the hazard doc's storm
   definition, then an audio-classification check (the same honest classifier line as
   `field-archaeology.md` §3.1 / open-Q3).
   **Closed by [`life-signal.md`](./life-signal.md) §3/§6:** the vitality classifier
   resolves exactly this — a growl is a *moving, rising* ε² gradient (a `c_s`-traveling
   front, `field-hazards.md` §2.1), a scar is a *flat* high-`ε²` plateau with no core;
   the audio inherits the same maintenance axis (§3.2) and noise-floor probe (§6b). The
   sound is an audible form of the classification this doc closes; `life-signal.md`
   §6(c) confirms the audio is an enhancement, never the only channel.
3. **Music-as-field-operation's cadence.** A score emits ops at musical tempo; `Q4`'s
   sustain flag (`coherence-magic.md` Q2 — whether a held op is a sustain flag or a
   re-emit) determines how a sustained phrase maps to the op records. Open until Q4
   is resolved.
   **SETTLED by [`schema-that-settles.md`](./schema-that-settles.md) §2.2: `sustain` is a
   flag (adopted over re-emit).** A score's sustained phrase maps to **one** held
   record per phrase (`sustain = true` — the domain maintains the source until the
   release), so the composer's record count and the Book agree; a score that re-emits
   a phrase N times would book as a noisy sequence. The score's sustained-hold cost is
   the self-bounding vent (`coherence-magic.md` §3), holding mid-score (`field-music.md`
   §1.3).
4. **Overdraw-as-feedback vs. the discharge's distinguishability.** §3 flags overdraw
   = clipped noise, but `coherence-magic.md` Q4 (§4.3) asks whether overdraw is
   structurally distinguishable from an ordinary scar. If not, the "scream" and the
   "dissonant dissolve" could be hard to tell apart by sound too — the audio inherits
   the same learning question the physics does.
5. **The desert's silence threshold.** At what local q / ε² band does the ambience
   fall below audible floor, and is that threshold tuned against the ambient noise
   floor (`energy-harnessing.md` §7 Q1's unit-calibration problem, applied to audio)?
   Phase-1 calibration.

---

## Cross-references

- [`coherence-magic.md`](./coherence-magic.md) — the six abilities as field operations (§2) this doc's musical gestures (§3) mirror; the coherence reader (§2, Sense) whose audio form §3 gives; the ε² vent and overdraw → full-cascade discharge (§4.3) that "overdraw = feedback" inherits; the Q4 op-schema (§5.1) that a coherence score composes; resonance (§3.1) that field music makes ear-audible.
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — the aurora as the (1−q) discharge (§3.1) that becomes the aurora's field tone (§2.1); weather = the envelope's ε² spikes (§1.3) that become the storm's growl (§2.2); the sky as the reader's atmospheric form (§3.3) — sound is the sky's *un-instrumented* hearing.
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — organisms as moving coherence stores at their rungs (§2.2, §3.2) that hum at their rung-depth (§2.4); the (1−q) glow as health-meter (§5.2) — its audible twin; creatures steer by the field a shepherd's score moves (§4.1).
- [`field-archaeology.md`](./field-archaeology.md) — residue as an ε² ghost (§3.1) that becomes the ghost-halo hum (§2.4/§5); the reader as the scan tool (§3.1) whose audio is the sonified scan.
- [`energy-harnessing.md`](./energy-harnessing.md) — the (1−q) waste law (§2) as the efficiency hum (§1); the constraint economy (§6) — music costs coherence (§4.1); machines as field operations (§2) a played score can feed (§4.2); the Qi bath (§4.4) — a region's hum's core.
- [`the-interstitial.md`](./the-interstitial.md) — **the ringing.** §2b there reads §1/§2
  this doc's sonification map as the between's ringing — the waves of every window's
  emissions carried through the thin, other worlds' sounds (§1/§2b there); §2.3 this doc's
  desert-silence is the between's logical floor (nothing to sonify). Reverse pointer: the
  interstitial is the ringing's medium, the carried distant-events chant.
- [`async-field-domain.md`](./async-field-domain.md) — the published channels (§2.1) the sonification map samples; **Q4, the player-return channel (§7)** that a coherence score is a consumer of (§4.1).
- [`material-regimes.md`](./material-regimes.md) — the φ-lock (§1) as the tonic; the fire-vs-explosive boundary (§3) = controlled vs. full-cascade discharge, the "rising phrase vs. clipping scream" distinction; deep-rung ordered matter = stored coherence (with `energy-harnessing.md` §1.5).
- [`the-shout.md`](./the-shout.md) — **the blunt-twin.** §1 there reads the shaped sound
  / the φ-tempered score; the shout is *raw broadcast* — no score, no composition; §6
  the accessibility rule. Reverse pointer: the shout is field-music's raw, un-scored
  sibling.
- [`the-smell.md`](./the-smell.md) — **the air's sibling.** §1 there reads the shaped
  sound; §6 the accessibility rule. Reverse pointer: smell is the air's read the way
  music is the air's sound.
- [`the-migration.md`](./the-migration.md) — **the herd-as-chord.** §2.4 there reads the
  biosphere hums at its rung-depth, a herd IS a chord; §6 the accessibility rule.
  Reverse pointer: the migrating many are a herd-as-chord at people-scale.
- [`the-understory.md`](./the-understory.md) — **the shade’s chord.** §2.4 the biosphere’s hum at rung-depth (the shade-band’s chord); §2.3 the desert’s silence (the near-silent calm); §6 the phi-ratios grounded. Reverse pointer: the understory hums at its rung-depth, a shade-band chord.
- [`the-chant.md`](./the-chant.md) — **the shaped-sound’s plainest.** §1 the shaped sound; §6 accessibility. Reverse pointer: the chant is field-music’s plainest sustained vocal.
- [`the-touch.md`](./the-touch.md) — **the body’s percussion.** §1 the shaped sound (the touch is the body’s own instrument). Reverse pointer: the touch is the body’s silent percussion.
- [`the-siren.md`](./the-siren.md) — **the matched cadence.** §2.4 an organism hums at its rung-depth; §1 the ambience; §4 a score is a Q4 sequence; §6 accessibility. Reverse pointer: the siren matches the hum’s cadence the field stands in.
- [`the-incantation.md`](./the-incantation.md) — **the voice’s kin.** the field’s voiced order. Reverse pointer: the incantation is field-music’s kin — the ordered voice perturbs the field.
- [`the-waterfall.md`](./the-waterfall.md) — **the roaring voice.** §1 the sound of the field; §2.4 the biosphere’s hum. Reverse pointer: a waterfall’s roar is the field’s own voice — the gradient’s discharge heard as the river’s loud.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers (φ, ξ = φ⁶ ≈ 17.94, φ⁻² ≈ 0.382, the ≈ 6 MiB publish, the 64³ grid, R=4 synth band) cited throughout.
- **`field-hazards.md`** — the storm growl (`field-hazards.md` §2 — the c_s-traveling ε² front; this doc's §2.2 growl is the audible form of its §2.3 pre-warning "auroras flicker / reader ε² noise rises") and the desert silence (`field-hazards.md` §3 — the regional q collapse; this doc's §2.3 silence is the audible form of its §3.1/§3.3 creep-darkening). This doc designs the audio; the hazard *mechanics* are field-hazards'. The no-free-energy gate that closes hazard-farming — `field-hazards.md` §5.3 — is cross-referenced in §4.2/§6 (a score can't mint coherence).
- Project precedent (read-only, the real sonification work): `CassiCosmos/research/sound_coherence_note.md` (sound = waves of coherence; the gapless ρ / gapped ε branches), `CassiCosmos/research/meshless/synth_design.md` (the implemented φ-tempered harmonic bank + cascade meter, verified), `CassiTheory/speculations/creative-extensions/magic-systems.md` (casting as phase-matched field operation — the creative ground for composition).
