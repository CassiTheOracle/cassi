# The Resonance Tutor: Learning to Channel by Feeling Your Own Past Hands

**Question under design:** how a player *learns* the CassiCraft magic system. The
whole power-design thesis ([`coherence-magic.md` §6](./coherence-magic.md)) is that
there are no particle-effect spells — every ability is a visible field operation, so
the magic system doubles as a physics teaching tool. Every workstream in the corpus
delivers a *mechanic* (a field operation, a score, an instrument, an NPC); none
delivers the *pedagogy* — the on-ramp that turns "the mechanic is the physics" from a
design promise into something a new player actually *feels*. **This document is that
on-ramp: the teaching loop that makes "magic feels like physics" literally true by
having the player learn from their own recorded history.**

The principle, stated once:

> **Every field operation the player performs is already recorded.** The Q4
> player-return channel ([`async-field-domain.md`](./async-field-domain.md) §7 Q4) —
> and `coherence-magic.md` §5.1's per-op record `{op, worldPos, rung, magnitude, sustain}`
> is the *same* op-schema a coherence score composes ([`field-music.md`
> §4.1](./field-music.md)). The Resonance Tutor replays your **own past self's**
> channeling as a guided exercise — *"do what you did when you healed that scar"* —
> with the field's response then, shown beside your re-enactment now, and your current
> phase drifting from your past self's presented as a **visual gap to close**. **The
> player does not learn channeling from a manual; they learn it by feeling the
> difference between their own two hands, a week apart.**

Companion to:
- [`coherence-magic.md`](./coherence-magic.md) — **THE dependency.** The Q4 op-schema
  §5.1 (`{op, worldPos, rung, magnitude, sustain}`, batched into the player-return
  job); the six abilities as field operations §2; the reader (Sense) §2; resonance
  with the field §3.1; the overdraw boundary §4.3; the thesis §6.
- [`field-music.md`](./field-music.md) — **the shared record format.** A coherence
  score is a sequence of the *same* Q4 records §4.1/§4.2; the composer and the Tutor
  share the record format — the Tutor is the **spoken companion to the played score**;
  the phase-matching `M` of §4.3.
- [`field-instruments.md`](./field-instruments.md) — **the live display.** The
  Weatherglass as the always-on read; the family rule §2.1 — the Tutor is a **consumer
  of the same publish + the Q4 records, never a new channel**; the §5.1 accessibility
  guarantee.
- [`field-npc-ai.md`](./field-npc-ai.md) — **the teacher NPC.** §3 the village's deep
  reader; §5.1 the read primitives; an NPC that knows what you did.
- [`field-archaeology.md`](./field-archaeology.md) — **the personal inverse problem.**
  §4.4 the reconstruction idiom, applied to your own traces; your past self as the
  readable object.
- [`tide-of-the-attractor.md`](./tide-of-the-attractor.md) — **the season-correction.**
  The tide changes the field your past self channelled in; the Tutor corrects for the
  regime difference.
- [`player-remains.md`](./player-remains.md) — **the informational twin.** A trace
  outlives you; your past self's channeling is a record that survives death; the
  fossil's twin.
- Skim as needed: [`the-reading-ahead.md`](./the-reading-ahead.md) — the prophet's
  momentum read run backward on your own channeling.

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived), engine-verbatim, or explicitly flagged
**[design]** (a presentation/pedagogical choice over real channels). The line is drawn
exactly where the corpus draws it: **the channels and records are real; the Tutor's
pedagogical idiom is [design].**

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| The trace = ? | **Already a format.** Every channeled op is a Q4 record `{op, worldPos, rung, magnitude, sustain}` (`coherence-magic.md` §5.1); a music score is a sequence of the same records (`field-music.md` §4.1). **No new recording system exists** — the Tutor reads records the corpus already creates. |
| The playback = ? | **Guided re-enactment.** The Tutor replays your past self's channeling: the sequence of ops, the field's response then (from the published channels at trace-time — the publish history the Weatherglass could have shown), and your re-enactment now, with the **phase gap** (your current injection phase vs your past self's) shown visually as a gap to close. |
| The season-correction = ? | The tide (`tide-of-the-attractor.md`) changes the field your past self channelled in; the Tutor corrects for the regime difference (what worked at harvest may need more at thin tide) — which is itself a lesson. |
| The teacher NPC = ? | A village's deep reader (`field-npc-ai.md` §3/§5.1) carrying your traces: an NPC that knows what you did and can demonstrate it back — the prophet's read (momentum) run backward on your own channeling. The Tutor is a place, an NPC, and an instrument — all reading the same records. |
| The pedagogy = ? | **Learning by feeling your own past hands.** From re-enacting your own past successes (confidence) to re-enacting your past failures ("here is where your phase broke and the overdraw began" — §4.3 taught on your own near-miss), to composing new channeling by *mixing your own past selves* (the composer's input, `field-music.md` §4.3). |
| Player-facing = ? | The onboarding engine ("magic feels like physics"); the mastery loop (each session tightens the phase gap); the social shape (share traces — teaching a friend by giving them *your* channeling; the found-economy of skill). |
| Honest gates = ? | (a) the trace exists (Phase-1); (b) the playback presentation (phase-gap display, season-correction) is [design]; (c) the teacher NPC gates on `field-npc-ai.md`'s read primitives; (d) accessibility — the Tutor is an enhancement of the reader/Weatherglass idiom, never the only channel (`field-music.md` §6); (e) determinism — a trace is deterministic; the re-enactment's response is deterministic given the same (tide-corrected) field state. |
| Feasibility = ? | **Phase-1, ship-now:** the trace format exists, the playback is a presentation of the publish + records, no new physics. The teacher NPC is later (gated on `field-npc-ai.md`). This is the corpus's smallest, highest-leverage instrument — the one that makes every other doc's thesis teachable. |

---

## 1. The trace — already a format

The single load-bearing fact of this document is that **the recording system already
exists, and nothing new needs to be built to have a trace.**

`coherence-magic.md` §5.1 specifies the Q4 player-return channel: every channeled
operation is a job-dict input — a per-op record

```
{op, worldPos, rung, magnitude, sustain}
```

batched into the player-return job at the sampler/world-writer cadence
(`async-field-domain.md` Q4). This is the *only* record a channeled action ever is.
And `field-music.md` §4.1 makes the consequence explicit: **a coherence score is a
timed sequence of those same records.** Playing a score is emitting its ops through
the Q4 channel in order — the score is just composition of the same records.

> **There is no new recording system.** The Q4 op-records *are* the trace. A player
> who has channeled condense, dissolved a scar, steered a current, held a shield has
> already left an ordered sequence of Q4 records — the same op-schema a score composes
> and the same records a `coherence-magic.md` coherence score is built from. The
> Resonance Tutor is a **reader** of records the corpus already creates; it adds no
> recording, no new channel, no write.
>
> **The record is now settled (two-way with [`schema-that-settles.md`](./schema-that-settles.md)):
> the trace is the extended `{member, op, worldPos, rung, magnitude, sustain}`**
> (§2.1 adds `member` first — a trace carries its author's identity, giving the
> journal provenance — and §2.2 makes `sustain` a flag, so a held phase books as one
> compact record, not a re-emit spam). The tutor's §4.2 journal (gated on the Q4
> schema being settled, `reason-field.md` §6a) can be designed against a final
> record; the doc's own §6a/§7 open-Q1 ride the journal's *persistence/scope*, which
> stays with the Reason Field's domain-side publish, on top of the now-final record.

Two consequences fall out immediately:

1. **Every trace already carries its provenance.** `worldPos` and `rung` locate the
   action in the world and on the cascade ladder; `op` names the six operations
   (`coherence-magic.md` §2); `magnitude` and `sustain` carry its cost and duration.
   A trace is not a vague "you did something here" — it is a precise, ordered
   specification of exactly which field operations you performed, where, at what
   rung, for how long.
2. **The tutor and the composer are the same reader.** `field-music.md` §4.1/§4.2
   establishes that a score is a Q4 sequence; the Tutor reads the same sequence to *teach*
   it back. The composer edits and replays a score as a field act; the Tutor replays
   your *own* history as an exercise. **The Tutor is the spoken companion to the played
   score** — the same records, the composer arranging them forward, the Tutor re-presenting
   the ones you already made so you can feel them again. Neither invent a format; both
   consume the one `field-music.md` and `coherence-magic.md` already define.

**The trace outlives you.** `player-remains.md` is the informational twin: your body's
deep-rung core persists as a fossil, and `field-archaeology.md` §4.4's reconstruction
idiom reads a dissolved structure from its residue (residue → tuple → behavior). The
Resonance Tutor's trace is the *other* persistence: the sequence of what you *did* (the
Q4 records) persists independently of the body, as a record `player-remains.md`'s fossil
is readable structure. A fossil is what the field kept of the structure you were; a
trace is what the Q4 channel kept of the operations you performed. Both outlive the
run; the Tutor reads the latter. **[design]** The exact persistence lifetime and
storage of the trace records (how long the Q4 journal is kept, whether it is per-window,
per-player, or per-world) is a designed decision over the Q4 schema — the *records exist*
is engine-real, the *journal of them* is this doc's design (open-Q1).

---

## 2. The playback — guided re-enactment

### 2.1 What the Tutor shows

Replaying a trace is three simultaneous things, all consumers of records that already
exist:

| Layer | What it is | Source |
|---|---|---|
| **The sequence** | the ordered list of ops your past self performed — condense, hold, steer, release — with their `worldPos`/`rung`/`magnitude`/`sustain`. | the Q4 trace (§1) |
| **The field then** | the field's response to each op at trace-time: the `q`/`ε²`/ρ response your past self's channeling actually caused, sampled from the *published channels at the moment of the trace*. | the publish history — the same `q`/`ε²`/`∇(g·Φ)` the Weatherglass and Sense read (`field-instruments.md` §1; `coherence-magic.md` §2), stored alongside the trace |
| **Your re-enactment now** | you perform the same ops in the same order at the same positions, and the *live* field's response is shown beside the past one. | the live publish, sampled as you channel |

The **presentation** of all three follows the instrument family rule
(`field-instruments.md` §2.1): **the Tutor is a consumer of the same publish + the Q4
records with a presentation idiom, never a new channel.** It adds nothing to the
publish — it renders, in the reader/Weatherglass idiom, the same channels the world
already publishes, and it reads the trace records that Q4 already writes. **[design]**
The *idiom* (how the three layers are laid out — a side-by-side "then/then-now" of the
Weatherglass-style read, a ghost of the past field over the live one) is a designed
presentation; the *channels* it presents are real.

### 2.2 The phase gap — the teaching instrument

The core of the playback is the **phase gap**. [`coherence-magic.md` §3.1] establishes
that resonance is the game-side rule: your channeling is *more efficient* when aligned
with the local field's natural rhythm — the phase of your injection matching the
field's own oscillation (the PDE's restoring `−ω₀²(EY − φ·EI)` term) and your pushing
*with* rather than against `∇(g·Φ)`. `field-music.md` §4.3 ties this to the theory's
phase-matching `M`: an organized, phase-matched perturbation has `M ≈ 1`; random,
unmatched perturbation is `M ≈ 0`. `coherence-technologies.md` §3 makes the detuned
boundary the "surface that refuses," and `field-npc-ai.md` §5.1 its intent-phase read.

The Tutor turns this abstract `M` into a **visible, personal, closable gap**:

> **The phase gap is the difference between your current injection phase and your past
> self's, shown as a visual gap to close.** During the re-enactment, the Tutor displays
> — in the Weatherglass/reader idiom — the *phase your past self held* at each op (the
> injection phase that produced the recorded field response) and the *phase you are
> holding now*. They drift apart; the presentation shows the separation as a gap to
> *close* by re-matching your timing and alignment to your past self's. Closing the gap
> is re-achieving the phase-match `M ≈ 1` — the difference between a working
> (`field-music.md` §4.3) and a cascade-suppressed `M ≈ 0` miss.

This is what makes the Tutor a *teaching instrument* rather than a replay: the player
does not *watch* their past self channel (that would be a video); they **do it again,
with the target of their own past phase shown as the gap, and they feel the effort of
closing it.** The gap is the tangible form of the resonance lesson of `coherence-magic.md`
§3.1 — the player learns, by feeling the resistance of an unmatched phase and the
release of a matched one, that *matching the field's rhythm is the actual skill*, not
the spell key. **[design]** The exact phase-gap visual (two overlaid phase dials, a
who-behind-how-far marker, a "closing" meter as `M` improves) is the idiomatic
presentation choice; the *quantity* it presents (your injection phase vs your recorded
past phase, and their match `M`) is grounded in §3.1 and §4.3 of `coherence-magic.md`.

### 2.3 The season-correction — the tide changes the field your past self channelled in

A trace is a snapshot of *a field at one time*. `tide-of-the-attractor.md` makes the
consequence unavoidable: on a long cycle a region's operating coherence `q` breathes
between **harvest** (high `q`, low `ε²`, cheap machines, the field organizing) and
**thin** (q troughs, machines wasteful off the `(1−q)` floor, the field de-organizing).
`coherence-magic.md` §1.2 makes channeling ride that: recovery refills toward 1 only
where the local field is coherent; the vent is small where the field heals fast
(harvest) and backs up where it heals slowly (thin). **Your past self's trace was
performed in a field of a particular tide phase; when you re-enact it, the field may be
at a different phase.**

> **The Tutor must season-correct.** "What worked at harvest may need more at thin
> tide" is not flavor — it is the physics of §1.2: the same op that healed a scar when
> the field was organized and healing fast will vent-to-overdraw more readily when the
> field is thin and healing slowly. The Tutor does not replay your past phase as a fixed
> target; it **corrects the past phase for the regime difference** — showing "here is
> what your past self did at harvest; this is how the *same intent* must be adjusted for
> the thin field you are standing in now."

And this correction is itself the lesson. The Tutor surfaces the tide's
regime table (`tide-of-the-attractor.md` §2: at thin, the vent backs up, resonance is
hard to match, overdraw risk rises) *on your own prior act*: it shows that your past
harvest-phase hold, attempted unchanged at thin, would cross the overdraw boundary
(`coherence-magic.md` §4.3) — and lets you feel the corrected version that stays within
budget. The player learns not just *how they channelled*, but **why their own past
channeling was a harvest act** — the temporal-horizon lesson of `tide-of-the-attractor.md`
§3.3 made personal. **[design]** The correction rule (the mapping from a trace's
recorded tide phase to the target phase at the re-enactment tide) is a designed
pedagogical lens over the real tide physics; it gates on the tide's own measure
(`tide-of-the-attractor.md` §5a's probe — see gate (b) §6).

---

## 3. The teacher NPC — a village that knows what you did

The corpus already designs the mechanism for an NPC that can know and demonstrate a
player's channeling. `field-npc-ai.md` §1.1 gives every NPC the same three field
primitives the player uses — **read** (sample `q`/`ε²`/`∇(g·Φ)` from the published
channels), **allocate** (a coherence budget B), **act** (inject organized perturbation
as a source term). §5.1 makes the reader able to read an NPC's **intent-phase** — where
it is pointing its next organized perturbation. And `the-reading-ahead.md` designs the
**prophet**: an NPC with a deep reader whose warnings are true because they read the
field's momentum, the forward-inverse of `field-archaeology.md` §4.4 (residue → regime
becomes momentum → outcome).

The Tutor's teacher NPC is that machinery pointed **inward at the player**:

> **A village's deep reader can carry your traces.** An NPC with the read primitives of
> `field-npc-ai.md` §3/§5.1 holds your Q4 trace as its read history — it *knows what you
> did* because it reads the same records the Tutor reads. And because an NPC can act by
> injecting organized perturbation (§1.1), it can **demonstrate your trace back to you**:
> "here is what you did," performed as a deliberate, phase-matched operation in the
> field — the prophet's read (`the-reading-ahead.md` §4), run **backward**, from your
> recorded history instead of toward a future.

So the Tutor is deliberately three things that read the *same* records:

| Form | What it is | Source |
|---|---|---|
| **A place** | a room-scale Weatherglass ("the Still Room," `field-instruments.md` §2.2) mounted at the village's Qi-bath commons core — a space that *shows* your history's field responses at scale. | `field-instruments.md` §2.2 (the Still Room); `field-npc-ai.md` §3.1 (a village is a Qi bath) |
| **An instrument** | the playback itself — the reader/Weatherglass idiom (§2.2) replaying your trace's phase gap, gateable to Phase-1. | §2 of this doc |
| **An NPC** | a village reader that has *learned your history* and demonstrates it back, correcting you as you re-enact. | `field-npc-ai.md` §1.1/§3/§5.1; `the-reading-ahead.md` §4 |

The same records feed all three — the tutor's identity is that it is **not a new
system**: it is the place, the NPC, and the instrument that already exist, all turned to
re-presenting the player's own recorded channeling. **[design]** The *teacher persona*
(the NPC's guidance, its corrections, its "you broke phase here" feedback) is a designed
layer over the `field-npc-ai.md` NPC's read/allocate/act mechanics — the *mechanism*
(a deterministically re-enacting NPC that co-channels with you) is `field-npc-ai.md`'s,
the *pedagogical script* is this doc's. Gated (gate (c) §6).

---

## 4. The pedagogy — learning by feeling your own past hands

The actual teaching arc is where the Tutor's promise lands. It is not a tutorial level
that teaches a mechanic once; it is a **mastery loop over your own history** into which
the field's physics is the content.

### 4.1 The aha loop

> **The Tutor shows the field's response to your past self (the Weatherglass display);
> you re-enact it; you feel the difference.** The "aha" is not "I did it right" — it is
> the *felt* recognition that your past self's phase, its alignment with `∇(g·Φ)`, its
> sustain against the vent, is something you can *re-produce from your own body*, and
> that the field's response confirms the reproduction. The teaching is embodied: you do
> not read about the ε² vent; you re-perform a hold you once made and feel the vent back
> up at thin tide because you are *in* the field that says so.

Because every op is a visible field operation (`coherence-magic.md` §6: "the mechanic is
the physics"), the re-enactment *is* the physics lesson. The vent that backs up, the
phase that drifts, the `M` that drops to `≈ 0` — these are not a bar or a debuff; they
are the field's own response to your re-enactment, shown in the same channels the
Weatherglass always presents. **The aha loop is the thesis of §6 made literal: the
mechanics of your own past hands teach the field's reality.**

### 4.2 The teaching arc — from success to failure to composition

The arc of the Tutor's exercises mirrors a real mastery progression, all over *your own
records*:

| Stage | The exercise | What it teaches | Grounding |
|---|---|---|---|
| **Re-enact your past successes** | replay a trace where you *did* something well — a clean condense, a shield that held, a heal that re-locked a scar. Close the phase gap against a self that succeeded. | confidence + the shape of a working: what `M ≈ 1` feels like, from a target you have already achieved. | `coherence-magic.md` §2; §3.1 (resonance) |
| **Re-enact your past failures** | replay a trace where the vent backed up or the phase broke — *"here is where your phase broke and the overdraw began."* | the overdraw boundary (`coherence-magic.md` §4.3) taught on your own near-miss — not a lecture about organized-vs-random perturbation, but a re-lived moment where *you* crossed it. | `coherence-magic.md` §4.3; `field-music.md` §3 (overdraw = feedback) |
| **Compose by mixing your own past selves** | take the phase-hold of one trace, the sustain of another, the alignment of a third, and *combine them into new channeling.* | composition itself — the tutor's input to the composer (`field-music.md` §4.3)| `field-music.md` §4.3 (the composer mixes phase-timed sequences) |

The third stage is the deep payoff: because the Tutor's records and the composer's
records are the same format, **your own past selves are the raw material of new
channeling.** You do not invent a working from a blank page; you *recombine the
phase-matched pieces of the successes you already made*, the way a composer reuses
phrase-shapes. The tutor hands the composer a vocabulary built from what your body has
already learned to do. **[design]** The mixing interface (how the tutor presents
"take the hold of #4, the release of #7") is the idiomatic presentation; the *fact that
your traces are composable into new Q4 sequences* is grounded in `field-music.md` §4.

---

## 5. Player-facing

### 5.1 Onboarding — "magic feels like physics"

The Tutorial's first use is the **onboarding engine.** New players do not get a manual;
they get the Reader (Phase-1, `coherence-magic.md` §2) and, as they *do* their first
few field operations, the Tutor begins recording and replaying them back. The first
"you did this, and this is what the field did" — shown as the Weatherglass-reading
beside the re-enactment — is the moment the thesis clicks: **channeling is not a spell
bar with particle effects; it is visible field operations, and the evidence is your own
first condense, replayed.** Onboarding is not a tutorial level; it is the player's own
first operations becoming their first lesson.

### 5.2 The mastery loop

Every session tightens the phase gap. The player's goal state is not "learned the
mechanic once"; it is that each re-enactment closes the gap faster and holds it longer —
`M` staying near 1 through more of the sequence, the vent staying within the heal rate
across a thin-tide correction. The Tutor's own metric (the closed gap, the matched
phase held) is literally the resonance and overdraw physics of `coherence-magic.md`
§3.1/§4.3, so **mastery is measured in the field's own units, not a skill XP bar.** A
player who has tightened their phase gap has, mechanically, learned to channel — which
is to say, *learned to read and match the field.*

### 5.3 The social shape — teaching by giving away your hands

The Q4 trace is a record, and records can be given. **A player can share a trace —
teaching a friend by giving them *your* channeling as an exercise.** The found-economy
of skill mirrors `custom-blocks.md` §5's "sharing is exchanging ordered matter" and
`player-remains.md` §3.2's "you cannot invent the player you were; you can only find it"
— but here the *found* object is a performed channeling, not a residue. A veteran who
shares a refined shield-trace gives a newer player a *target with a real provenance*: a
phase-gap exercise against an actual prior human's working, not an authored ideal. The
Tutor becomes a **social instrument** — the way a songbook passes a phrase between
players, the Q4 record passes a *channeling* between them. **[design]** The sharing
mechanics (how a trace is copied, whether it is per-window or portable, the
found-economy of "a gifted trace") are designed over the Q4 record; the *record* is the
same one §1 establishes.

---

## 6. Honest gates

### (a) The trace exists — Phase-1

The foundational gate is already closed: **Q4 records are Phase-1** (`coherence-magic.md`
§5.1 — a per-op record `{op, worldPos, rung, magnitude, sustain}` into the player-return
job; `async-field-domain.md` Q4). Phase-1 ships Sense (read-only, the coherence reader)
plus condense/dissolve/shield on the existing publish with zero new physics
(`coherence-magic.md`'s Phase-1 verdict). Every one of those operations is recorded as a
Q4 record. **So a player in Phase-1 already leaves a trace the moment they channel.**
The Tutor's Phase-1 slice is: keep a journal of a player's Q4 records (open-Q1 — the
storage decision), and present them back in the reader/Weatherglass idiom (§2.2). No new
recording, no new channel, no new write — **pure presentation of records that already
exist.**

### (b) The playback presentation is [design]

The *presentation* — the phase-gap visual (§2.2), the side-by-side "then vs now," the
season-correction rule (§2.3) — is a **designed pedagogical idiom over real channels**,
flagged throughout. It must not be mistaken for engine drama. Specifically:

- The **phase-gap display** is a designed rendering of the real injection-phase and
  phase-match `M` of `coherence-magic.md` §3.1 / `field-music.md` §4.3.
- The **season-correction** is a designed mapping from a trace's recorded tide phase to
  the re-enactment's tide, and it gates on the tide being *measurable* —
  `tide-of-the-attractor.md` §5a's probe. Until the probe returns a real season, the
  correction collapses to a *drift* reading (thin-toward-harvest), not a calendar
  correction; the honest drift reading is preferred over forcing a cycle
  (`tide-of-the-attractor.md` §1.2). **[design]** the correction's form; **[probe]** the
  tide's reality it depends on.

### (c) The teacher NPC gates on `field-npc-ai.md`'s read primitives

The NPC that demonstrates your trace back (§3) is a `field-npc-ai.md` NPC whose decision
layer weights your recorded history. It therefore inherits every `field-npc-ai.md` gate:
engine-real read/allocate/act primitives (§1.1), hard determinism (§6d), the commons and
coherence budget (§6e). **The teacher NPC is Phase-1-later**, gated on
`field-npc-ai.md`'s Phase-1 field-steered NPCs (a deterministic NPC that co-channels —
the *mechanism* — needs the NPC decision layer to exist), with the *teacher persona* (the
guidance script) a **[design]** layer on top. The **place** (the Still Room) and the
**instrument** (the playback) are not so gated — they are pure consumers and can ship
with Phase-1.

### (d) Accessibility — the Tutor is an enhancement, never the only channel

`field-music.md` §6 is a hard rule: sound is an enhancement, never the only channel; a
mute player loses nothing. `field-instruments.md` §5.1 makes the Weatherglass the
guaranteed-equal instrument. The Tutor obeys the same discipline by construction: it
read-only *presents* the channels the reader and Weatherglass already present, so
**nothing the Tutor teaches is information a player cannot get from the reader and
Weatherglass on their own.** The Tutor is a *lesson* — a guided re-presentation of
records you could read unaided — not a *requirement*. Critically, **the pedagogy never
becomes a dependency**: the world must remain playable, and the field readable, for a
player who never enters the Tutor; `coherence-magic.md`'s §6 thesis ("the mechanic is
the physics") must hold with or without the guided re-enactment loop. The Tutor is the
*spoken* companion (`field-music.md` §4.1) — an enhancement of the reader/Weatherglass
idiom, never the only path to understanding.

### (e) Determinism — a trace is a deterministic record

The field is deterministic (one PDE; `field-archaeology.md` §1.2; `field-npc-ai.md` §2.3's
hard gate). Therefore:

> **A trace is a deterministic record, and the re-enactment's field response is
> deterministic given the same field state.** Same Q4 record sequence + same (tide-
> corrected) field state → identical response, to the body of the player re-enacting
> and to any NPC demonstrating it. Determinism is what makes the Tutor an *honest*
> teacher: the phase gap you cannot close is a real mismatch against a real recorded
> phase, not a seeded-RNG judge; the overdraw you re-live is the same overdraw the field
> produced then, reproduced because the physics is reproducible.

This is a hard gate, inherited from the corpus's determinism discipline. **[design] The
re-enactment is a presentation of a deterministic response, not an authored scripted
outcome** — a player who re-matches the recorded phase *gets* the recorded response,
because that is what the deterministic field does.

---

## 7. Feasibility verdict

**Phase-1, ship-now.** The trace format exists (Q4 op-records, `coherence-magic.md`
§5.1 — the same records a score composes, `field-music.md` §4.1). The playback is a
**presentation of the publish + records** — the reader/Weatherglass idiom (§2.2) over
channels the corpus already publishes, reading records Q4 already writes. No new
recording, no new channel, no new physics, no new write. The minimal Phase-1 slice — a
player journal of Q4 records (open-Q1), re-presented in the existing read idiom as a
phase-gap exercise — is pure consumer work on the already-shipped Sense/Weatherglass
surface and the already-budgeted Q4 channel, inside the same ≈ 1–6 ms/tick sample
budget (`corpus-reconciliation.md`).

| Piece | Phase | Gate |
|---|---|---|
| The Q4 trace (the record exists) | **Phase-1** | already closed (`coherence-magic.md` §5.1) |
| The playback — phase-gap presentation | **Phase-1** (presentation, no new physics) | [design] idiom over real channels |
| The season-correction | Phase-1.5 (drift) / gated (calendar) | `tide-of-the-attractor.md` §5a's probe ([probe]) |
| The teacher NPC | later | `field-npc-ai.md`'s read primitives (§6c) |
| The found-economy of shared traces | later | the trace journal + `custom-blocks.md` §5 sharing discipline |

**This is the corpus's smallest, highest-leverage instrument — the one that makes every
other doc's thesis teachable.** The magic system's claim (`coherence-magic.md` §6: no
spell tiers, every ability is a field operation, the magic doubles as a physics teaching
tool) is not self-evidently teachable — it needs an on-ramp a player actually *feels*.
The Tutor is that on-ramp, and it costs almost nothing: it reuses the recording the
corpus already makes, the display it already builds (the Weatherglass), the format the
composer already shares (the Q4 sequence), and — later — the NPC that already reads. It
adds no subsystem; it turns records that already exist into the player's own past hands,
so that "magic feels like physics" is not a promise the player must take on faith but
**something they learn by feeling the difference between their two hands, a week apart.**

**Binding risks, in order:**
1. **The trace journal persistence (open-Q1)** — the Q4 *records* exist, but the *journal*
   of them (how long it is kept, whether per-window/per-player/per-world) is this doc's
   design and must not break the Q4 schema or cadence.
2. **The tide probe (gate b)** — the season-correction depends on the tide being
   measurable; until `tide-of-the-attractor.md` §5a returns, the correction is an honest
   drift reading, and forcing a calendar would violate the tide doc's own honesty.
3. **The [design] line on the phase-gap and the season-correction** — keeping the
   pedagogy idiomatic ([design]) and never presenting it as engine drama is the same
   discipline the corpus practices; the quantities (phase, `M`, the overdraw boundary)
   it presents are real.
4. **Not becoming a dependency (gate d)** — the Tutor must remain an enhancement; the
   world and field must stay readable and playable for a player who never enters it.
   Violating this would invert the accessibility and no-manual promises it exists to serve.

---

## Open questions

1. **The trace journal's persistence and scope.** The Q4 records exist as job-dict
   inputs; keeping a player-addressable *journal* of them (how long, per-window or
   per-player, how it survives the seam) is a designed decision over the Q4 schema.
   Does it live server-side (owner of the budget, honest single-writer) or alongside the
   async publish? The same sampler-vs-domain fork as `field-npc-ai.md` §7 open-Q1 and
   `player-remains.md` open-Q1.
   **Resolved by [`reason-field.md`](./reason-field.md):** the fork's three legs pick the
   same side there — **the trace journal lives in the same domain-side publish** (§4.2):
   the record of what the player did is a π-trail in the field itself (every channeled op
   is a perturbation the field absorbed, `coherence-magic.md` §5.2), readable through the
   Reason Field the way a fossil residue is readable through `field-archaeology.md` §3.1.
   The journal is the field's own record, not a server log appended to the Q4 queue; the
   tutor replays the intentionality the field kept. Gated on the same meshless/persistent-
   Π frontier + Q4 schema (§6a).
2. **The phase-gap vs the live classifier.** Does "your injection phase now vs your
   recorded past phase" robustly read from the publish at the same confidence as
   `field-npc-ai.md` §7 open-Q2's intent-phase, or does the Tutor need the phase-match
   `M` published per-player (which Phase-1 does not budget)? Same honest classifier line
   as archaeology §7 open-Q3 and field-music open-Q2.
   **Closed by [`life-signal.md`](./life-signal.md) §3/§6:** the vitality classifier
   resolves the recorded-vs-live phase gap on the **maintenance axis** — a re-enacted
   *live* hold *pulses* (the maintainer is active); a static replay is *flat* (nothing
   holds it) — separable without per-player `M` (§3.2). The Tutor's `M`-target stays a
   designed pedagogical quantity over the same maintenance read; the phase-gap display
   is its presentation of what §2.2 measures.
3. **The season-correction's honesty.** When the tide is a drift (not yet a real
   season), does the Tutor's "you must adjust for thin" remain honest as a *lesson*, or
   does it risk asserting a calendar the probe has not confirmed? The correction must
   never present a designed phase as a physics fact before `tide-of-the-attractor.md`
   §5a's verdict.
4. **The teacher NPC's determinism vs. live feedback.** `field-npc-ai.md` §6d makes an
   NPC a pure function of (Π pattern × channels). A teacher that *co-channels with* you
   and corrects as you re-enact must incorporate your live (changing) phase — is that
   still deterministic (same new input → same new correction) and legible as honesty,
   the same revision question `the-reading-ahead.md` open-Q5 raises for the prophet?
5. **The shared trace's provenance.** When a veteran gifts a refined trace to a newer
   player (§5.3), is the gifted trace *their* phase-gap target, and is a newer player
   physically able to reproduce a deep-rung phase they have not mastered — or does the
   found-economy of skill require the tutor to *gate* a shared trace by rung, exactly as
   rung access is gated by budget physics (`coherence-magic.md` §4)?

---

## Cross-references

- [`coherence-magic.md`](./coherence-magic.md) — **THE dependency**: the Q4 op-schema
  §5.1 (`{op, worldPos, rung, magnitude, sustain}`, already recorded); the six abilities
  §2; Sense/the reader §2; resonance §3.1 (the phase-gap's target and quantity);
  overdraw → full-cascade discharge §4.3 (taught on your own near-miss); the §6 thesis
  the Tutor makes teachable.
- [`field-music.md`](./field-music.md) — the shared record format §4.1/§4.2 (a score is
  a Q4 sequence; the Tutor reads the same); the phase-matching `M` of §4.3 (the reason a
  matched re-enactment is a working); overdraw = feedback §3; the accessibility rule §6.
- [`field-instruments.md`](./field-instruments.md) — the Weatherglass as the live
  display §1; the family rule §2.1 (the Tutor is a consumer of the publish + records,
  never a new channel); the Still Room §2.2 (the Tutor-as-place); §5.1 accessibility.
- [`field-npc-ai.md`](./field-npc-ai.md) — §1.1 the read/allocate/act primitives; §3 the
  village as Qi bath + deep reader; §5.1 the read primitives and intent-phase; §6 the
  gates (determinism, no-free-energy) the teacher NPC inherits.
- [`field-archaeology.md`](./field-archaeology.md) — §4.4 the reconstruction / inverse
  idiom (applied to your own traces); the reader-as-scan tool §3.1.
- [`tide-of-the-attractor.md`](./tide-of-the-attractor.md) — the season the Tutor
  corrects for; §2 the regime table (harvest vs thin); §1.2 the honest drift reading;
  §5a the probe the calendar correction gates on.
- [`player-remains.md`](./player-remains.md) — the informational twin: a trace outlives
  you; the fossil's readable-structure counterpart.
- [`the-reading-ahead.md`](./the-reading-ahead.md) — the prophet's read (momentum,
  forward-inverse of §4.4) run backward on your own channeling; the prophet's revision
  honesty (open-Q5, mirrored here).
- [`coherence-technologies.md`](./coherence-technologies.md) — concept 3 the phase-
  matching `M` / detuned boundary §3, the quantity the phase gap presents.
- [`async-field-domain.md`](./async-field-domain.md) — Q4 the player-return channel §7
  (the records' source); the publish contract §2.1.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers
  (≈ 6 MiB publish, 64³ grid, ξ = φ⁶ ≈ 17.94, φ⁻² ≈ 0.382, the ≈ 1–6 ms sample budget)
  cited, not re-derived.
