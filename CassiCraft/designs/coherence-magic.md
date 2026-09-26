# The Player Power System: Channeling One's Own Coherence

**Question under design:** replace spell tiers with a single mechanism — the
player as a **coherence source** who performs *field operations*, so every
"spell" is a visible manipulation of the Cassi two-fluid field, and the magic
system doubles as a physics teaching tool for the whole CassiCraft world.

Companion to:
- [`../README.md`](../README.md) — the vision (the two-fluid field is the
  substrate; blocks, mobs, planets are its epiphenomena).
- [`volumetric-terrain.md`](./volumetric-terrain.md) — the player as
  coherence-manipulator; precision tools = cascade rung; terrain condenses and
  heals.
- [`async-field-domain.md`](./async-field-domain.md) — the seam; **Q4 is the
  player-return channel** this system is a consumer of.
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — mining as a
  perturbation (lower local ρ, raise local ε²).

Physics grounding (engine source of truth, quoted verbatim where load-bearing):
- [`CassiCosmos/compute/cassi_two_fluid.glsl`](../../CassiCosmos/compute/cassi_two_fluid.glsl)
  — the PDE, q, ε², and the source (perturbation-injection) terms.
- [`CassiCosmos/compute/cassi_nbody_gravity.glsl`](../../CassiCosmos/compute/cassi_nbody_gravity.glsl)
  — the river law, `∇(g·Φ)`, and the Yang fraction π/ρ.
- [`CassiCosmos/compute/cassi_condensation.glsl`](../../CassiCosmos/compute/cassi_condensation.glsl)
  — the condensation threshold.

Every number below is engine-verbatim or the Phase-1 mapping established by the
companion quantization doc. Assumptions are flagged `[assumption]`.

---

## 1. The player as a coherence source

The engine already gives us the player's "body" in field terms. From
`cassi_nbody_gravity.glsl`:

```
ρ      = EY + EI                                    (density)
ε      = EY − φ·EI                                   (decoherence)
ε²     = (EY − φ·EI)²                                 (decoherence channel)
q      = ρ² / (ρ² + φ⁻² + ε²)                        (coherence, 0→1; attractor ≈ 0.947)
π/ρ    = clamp((EY−EI)/(EY+EI), 0, 0.72)            (the Yang fraction)
a      = −G_N·(π/ρ)·∇(g·Φ),   g = 1 + (φ⁶−1)·q      (the river law)
```

The φ-attractor is the locked equilibrium `EY = φ·EI` (where ε = 0). **q — the
fraction of the field's energy that is *organized* rather than lost to
decoherence — is the natural gauge of a player's power.** This is the design's
central mapping:

> **Coherence budget B** — a per-player scalar, `B ∈ [0,1]`, modeled on the
> field's own `q`. The player is a **bounded EY injector** (they can pour Yang
> into the field, raising local ρ and organization) and an **ε² vent** (channeling
> necessarily sheds decoherence that the field must absorb / heal around).

### 1.1 Why the player is a *bounded* EY injector and an *ε² vent*

The two-fluid PDE's source terms (`cassi_two_fluid.glsl` `source_ey` /
`source_ei`) are exactly that: a Gaussian organized-perturbation seed plus a
small ρ-feedback term, injected as `source · dt²`. Channeling reuses this **same
mechanism, not a new one** — the player's ability to act is literally the field's
existing ability to accept an organized perturbation. The constraint that keeps
it from being free energy is the *budget* below.

The boundedness has three independent grounds:

1. **The ε² vent is a conservation discipline.** Every channeled operation
   raises local `EY` out of φ-lock, and per the ε² channel `ε² = (EY − φ·EI)²`
   that *is* decoherence by definition. Channeling cannot create organized
   field without shedding its decoherence byproduct — the field (and the world
   it quantizes) must heal around the vent. "Overdraw" is exactly when the
   shed ε² outruns the field's recovery.
2. **The Yang fraction is clamped.** `π/ρ` is `clamp(·, 0, 0.72)`; saturating
   it past 0.72 is unphysical for the law. A player's injection that would push
   π/ρ past the clamp is a *hard* ceiling on raw Yang output.
3. **q is bounded.** `q ≤ 1` by construction (denominator ⊇ numerator); there is
   no unbounded scalar to spend.

### 1.2 The budget, its recovery, and overdraw

| Quantity | Definition | Recovering | What it gates |
|---|---|---|---|
| **B (coherence budget)** | per-player `q`-modeled scalar, `[0,1]` | standing in high-q field regions, rest, resonance — §3 | the *size and rung* of operations you can sustain |
| **Rung** | which cascade organization scale you operate at — §4 | unlocked (mastery), not consumed | the *depth* of each operation |
| **ε² debt** | the decoherence you've shed but the field hasn't yet healed | field auto-heal rate (§5) | the blowback risk on overdraw |

**Recovery:** the budget refills toward 1 only where the *local field* is
coherent. Standing in a high-q region (a coherence ridge, an intact high-ρ
formation, near places where the field is organized) pulls B up; standing in a
carved/ε²-rich scar keeps B depressed because you are surrounded by your own
medium's disorder. Rest (not acting) bleeds ε² debt into the field at the field's
own healing rate rather than your forced rate. This makes *environment* a
first-class resource — the economy of the magic is the geography of coherence.

**Overdraw:** channeling past your current B (spending more than your q-modeled
budget holds, or sustaining a deep rung longer than the ε² vent can shed) does
not just fizzle — it **inverts the operation**. The un-ventable ε² accumulates
locally, the φ-lock fails, and the local field sheds coherence toward
disorganization. This is the game-side face of the theory's coherence-budget
distinction between *organized* and *random* perturbation: channeling *within*
budget is organized (productive, the field reorganizes around it); overdraw tips
the injection into *random* perturbation (the field cannot organize it, it
spreads as ε²). The discharge consequence is §4.3 — tied to the material
explosives concept.

---

## 2. Channeling mechanics — abilities as field operations at a chosen rung

Every ability is **one field operation** performed at a chosen cascade rung.
There is no separate "spell" — there is a manipulation of ρ, ε², or ∇(g·Φ) at a
scale, and the world effect is that manipulation made visible as it quantizes
onto the gameplay grid. The operation language is the same one the world already
uses (from `chunk-field-quantization.md`: ρ ≥ τ_c → solid, ε² above a floor →
dissolve, q above a band → ore/precipitation).

Each row: *(field operation)* → *(visible world effect)*, *(cost)*, *(rung)*.

| Ability | Field operation | Visible world effect | Cost | Rung |
|---|---|---|---|---|
| **Sense** (the "coherence reader") | read local `q`, `ε²`, `∇(g·Φ)` (the published snapshot's `field_q`, ε², `grad` buffers) and render them as a magnetometer overlay | you *see* the field: coherence ridges glow, scars darken, the river gradient arrows the "downhill" a body would take | ~0 (a read-only rung-0 channel; the reader itself is the Phase-1 deliverable) | rung 0 |
| **Condense** | raise local `ρ = EY+EI` past `τ_c = 0.5` where `q` is already high | solid matter grows there (blocks solidify from the iso-surface; ore enriches where q accumulates) | B, sized to the volume raised | rung n (deeper = denser/finer growth) |
| **Dissolve** | raise local `ε²` above its dissolution floor — the mining perturbation of `chunk-field-quantization.md` made *deliberate, aimable* | carved matter returns to air; the field reorganizes and the scar heals behind you | B + raises your own ε² debt (you are mid-scar) | rung n (deeper = cleaner, further-reaching carve) |
| **Steer** | inject a local current along `∇(g·Φ)` so nearby entities/items/you move with the river law `a = −G_N·(π/ρ)·∇(g·Φ)` | currents in matter: push/pull, redirect falling items and (Phase 3) mobs; the world flows as its law says | B proportional to the steer weight × affected mass | rung n (deeper = heavier objects, longer range) |
| **Ignite** | launch an *organized-perturbation front* — a propagating `EY` pulse along the PDE's wave operator `∂²EY/∂t² = c²∇²EY − ω₀²(EY − φ·EI)` | a visible front that runs along the medium, shedding ε² at its edges; interacts with what it crosses | B, plus a fast ε² vent (the front *is* moving organization) | rung n — **forward-reference `material-regimes.md`** (companion, being written concurrently): ignition sits on that doc's regime boundaries (organized vs explosive regimes); the front's kinetics and its "explosive" outcome are defined there |
| **Shield / Heal** | suppress local `ε²` and restore coherence — inject *opposing* Yin (EI) to re-lock `EY = φ·EI` in a region | a region's coherence returns: scars heal, carved blocks re-condense toward the attractor, and entities inside stop shedding q | B sustained while holding; requires *net-zero* over the hold or the vent backs up | rung n (deeper = heal-to-coherence faster / over a larger volume) |

### 2.1 The same operation at every rung (no separate tools)

Consistently with `volumetric-terrain.md` ("precision tools are
coherence-manipulators at a chosen rung — one physics, one tool language,
arbitrarily deep"), an ability is **not** leveled into distinct spells. Condense
at rung 1 grows a coarse block; at rung 3 it crystallizes finer structure /
richer ore within the same cell. Dissolve at rung 1 is a coarse pick; at rung 4
a sub-block sculpting chisel. The *operation* is identical; only the cascade
scale differs. This is what lets the magic double as physics teaching — the
player learns that "deeper" is not a damage number but a smaller organization
scale.

### 2.2 Why each op is *visible*

The world layer is a quantization of the same continuum (both layers sample the
same published snapshot — they cannot drift within a snapshot,
`chunk-field-quantization.md` §1.4). So a channeled manipulation of ρ/ε² **is** a
visible change: the iso-surface moves, blocks re-quantize, ore precipitates.
Sense makes even the *steering gradient* visible as arrows. There is no
particle-effect that is not a real field event, and no field event that is not
visible. That identity is the thesis (see §6).

---

## 3. Costs & recovery — tied to the coherence budget

Cost is expressed in the theory's own terms: **organized vs random perturbation,
single-rung vs full-cascade attack.**

- **Within budget = organized perturbation.** The injection is a coherent
  `EY`/`EI` structure the field can absorb; the world effect is constructive
  (condense, steer, shield), the shed ε² is a local, healable vent.
- **Over budget = random perturbation.** The injection exceeds what q can
  organize; it sheds as ε² and the field's response is the *disorganization*
  event of §4.3. This is the same physics as a carved scar, but player-initiated.

**Cost model bounds:**
- The **hard ceilings are physical** (π/ρ ≤ 0.72, q ≤ 1, ρ ≥ τ_c for solidity) —
  they come from the law, not a hand-tuned mana bar.
- The **sustained constraint is the ε² vent.** Any op has a vent rate
  `v = d(ε²)/dt` at the op's locality; the field heals ε² at the ambient heal
  rate `h`. Within budget ⇔ `v ≤ h` sustained. This binds channeling *duration*,
  not just size — a budget of 1 is not a license to hold ignite forever; it is a
  license to let the vent settle.
- **Recovery is geographic + temporal:** high-q environment raises the ceiling,
  rest lowers the vent rate, resonance (§3.1) couples your B to the field's
  actual coherence rather than an abstract bar.

### 3.1 Resonance with the field

The engine's telemetry (`tel[]` in the river shader) already tracks q min/max,
π/ρ clamps, and sample counts per step. **Resonance** is the game-side rule: your
channeling is *more efficient* (lower vent, faster recovery) when your operation
is aligned with the local field's natural rhythm — when the phase of your
injection matches the field's own oscillation (`ω₀²` in the PDE's restoring
`−ω₀²(EY − φ·EI)` term), and when your sense-read `∇(g·Φ)` shows you pushing
*with* the gradient rather than against it. Pushing against the local flow costs
more vent for the same effect; matching it costs less. This teaches, mechanically,
what `a = −G_N·(π/ρ)·∇(g·Φ)` means: the field steers, and the strongest operations
are the ones the field was already inclined to do.

`[assumption]` — whether resonance is exposed as a timing minigame or an implicit
efficiency multiplier is a tuning decision; the *coupling* (efficiency ∝ local
field alignment) is the physics-grounded rule.

---

## 4. Progression — rung mastery, not spell tiers

Progression is: **unlock access to deeper cascade rungs**, and learn to sustain
deeper channeling without overdraw. There are no "spell levels"; there is a
mastery landscape over the same six operations at successively finer scales.

### 4.1 Rung access

A player begins at rung ~1–2 (coarse organization: block-scale condense/dissolve,
short steer, weak shield). Unlocking a deeper rung is the *skill of holding the
φ-lock at that scale longer / over a larger volume* while keeping the vent within
the field's heal rate. The engine's own rung structure (`volumetric-terrain.md`:
precision tool resolution ⇔ rung; φ-scaled refinements) is the ladder. This is
deliberately **not** a resource-gated tech tree — it is a *capacity* gate, gated
by the same budget physics the ops use. You master rung n by demonstrating you can
channel a rung-n operation to completion without the vent backing up.

### 4.2 Depth ⇔ effect ⇔ blowback

| Rung | Effect | Blowback risk |
|---|---|---|
| shallow (1–2) | coarse, local, cheap to sustain | low; vent well within heal |
| mid (3–4) | finer structure / richer ore / longer-range steer / broader shield | moderate; vent starts to compete with ambient heal |
| deep (5+) | sub-block precision, heavy-object steer, full-region heal, fast ignition fronts | high; vent now dominates the locality — you *are* the scar while you channel |

The scoring of "deeper = greater effect + greater ε² blowback risk" is not
arbitrary: deeper rung = smaller organization scale = finer, more concentrated
injection = a larger excursion of ε² relative to the field's ability to heal that
scale.

### 4.3 Overdraw → full-cascade discharge

Overdrawing a deep rung past the vent's capacity tips the injection from
organized to random perturbation; the local φ-lock fails (`EY − φ·EI` runs away),
and the accumulated ε² relaxes **in one organized-front release** — a
**full-cascade discharge** that runs the medium's *own* dynamics out and in,
shedding ε² across rungs as it goes, with a destructive / explosive outcome where
the medium is dense.

> **This is the load-bearing forward-reference to `material-regimes.md`**
> (companion, being written concurrently). The detail of what a full-cascade
> discharge does mechanically — the regime boundary at which a field front
> becomes explosive, its radius/magnitude vs stored ε² — is that document's
> domain, not re-derived here. This document only fixes the *trigger*: overdraw =
> organized perturbation exceeds the field's organization capacity and collapses
> to a random-perturbation discharge. The material doc defines the explosive
> *physics*; this one defines the player-facing *cause*.

---

## 5. Integration — the world responds, the energy system is fed

### 5.1 Q4: the player-return channel is the plumbing

From `async-field-domain.md` Q4: player edits/injections round-trip into the
domain **as job-dict inputs** (`submit_steps` job dict carrying inputs like
`window_center`), never by the server thread touching physics state, and never by
the worker reading game state (§5.2). The magic system is a **consumer of that
channel**:

- The **sense-read** path is a *read-only* consumer of the published snapshot
  (`field_q`, ε², `grad` — the same buffers `chunk-field-quantization.md` §2
  already specifies for the sampler). A coherence reader is just a stylized
  visualization of the publish the world already samples.
- **Every operation** (condense / dissolve / steer / ignite / shield) is a
  *write* into the next job's dict: a job input encoding "at world-position p,
  raise ρ by Δρ" / "raise ε² by Δε² over radius r at rung n". The world-writer
  (the only server-side mutator) applies the sampler's intent; the domain absorbs
  the perturbation in the next `submit_steps` and heals — exactly the
  `chunk-field-quantization.md` §6 gap (#3 player-edit feedback loop) this system
  is built on.

The constraint from the seams doc — **the server thread never touches physics
state** — is preserved *by construction*: the magic system never references a
field array directly; it emits job-dict perturbations, and the world effect is
the domain + sampler + world-writer chain quantizing them back. The open question
(Q4's "exact input schema and cadence") is partly this doc's job to bound: the
input schema is a small per-op record {op, worldPos, rung, magnitude, sustain}
batched into the player-return job; cadence follows the sampler/world-writer
cadence of `chunk-field-quantization.md` §2.1.

### 5.2 The world responds

- **Terrain heals around your channeling.** Condense and dissolve both perturb
  the local field; the medium's attractor pulls it back, exactly as
  `volumetric-terrain.md` and `chunk-field-quantization.md` describe mining. A
  channeler's work is a *conversation with the medium*, not a static edit.
- **Mobs respond to your coherence signature.** Per `chunk-field-quantization.md`
  §2.2, entities steer by the river law and spawn where q is in a band and ε² is
  low. Your channeling moves q/ε²; mobs therefore react to *what you do to the
  field* — they drift toward coherence you raise, avoid the scars you shed, and
  (Phase 3, field-emergent ecology, README) the field precipitates them where your
  sustained organization accumulates. Your "signature" is your honest footprint in
  q/ε² — there is no stealth channeling that does not also change the field you
  are sensed through.
- **Machines can be fed by a channeler.** The energy system (`cassicraft-energy`
  companion workstream) will have machines that consume *organized field input*.
  A channeler's condense/ignite/shield output — a sustained, coherent field
  manipulation — is that input's natural source: a machine in a high-q region the
  player is sustaining draws on coherence the player organized. The magic is not
  a parallel fantasy system bolted onto the energy system; it is the *hand-held
  pump* that energizes it, both running on the field's q/ρ/ε².

---

## 6. The thesis

> **No particle-effect spells.** Every "spell" is a real field operation, so the
> magic system doubles as a physics teaching tool for the whole CassiCraft world.

Because: (a) every op is one of the six operations on ρ/ε²/∇(g·Φ) the world itself
uses; (b) the world layer is a quantization of the same published snapshot, so
the op's effect *is* the visible terrain/entity change — there is no event that is
either invisible or non-field; (c) cost, ceiling, and blowback all come from the
field's own equations (q, π/ρ clamp, ε² vent, coherence budget), not a game stat.
A player who channels is a player *reading the field*: sense shows the gradient,
condense/dissolve/steer/ignite/shield manipulate the channels the law is made of,
and mastery is literally understanding coherence organization. The pedagogy is
not bolted on — the mechanic is the physics.

---

## 7. Honest open questions and Phase-1 verdict

### Open questions

1. **Q1 — Budget-to-field mapping without touching physics state.** The cleanest
   (`B = player's local q`) requires reading the published snapshot on the
   server — which the sampler already does, so this is *feasible*,
   but it needs the Q4 input schema resolved: how the player's q-modeled `B`
   (server-side, in the world-writer/sampler) stays in phase with the *domain's*
   q (which the player cannot touch directly) without the server re-deriving
   field state. Bound: the sampler reads the published q at the player's world
   position; B follows it via the job-cadence publish — but the *write* of ops and
   the *read* of the field are on different cadences, and the player's vent / ε²
   debt must be tracked where? (Server-side as a derived quantity is the natural
   answer — it makes the server the honest owner of the budget and the domain the
   honest owner of the field.)
2. **Q2 — Sustained-op cadence.** Condense/shield that "hold" a manipulation want
   a per-tick (or per-N-tick) perturbation, not a one-shot. Whether the player-return
   job carries a *sustain flag* (domain maintains the source until told to stop)
   or the server re-emits the op each job, and how sustain interacts with the
   domain's per-job step caps, is open.
3. **Q3 — Steer's mass coupling.** The river law `a = −G_N·(π/ρ)·∇(g·Φ)` scales
   acceleration by π/ρ, not by a player-tunable force. Whether "steer" perturbs
   the *field* (so the law then does the steering) or injects a directly player-
   weighted acceleration is a real fork — the field-first option is more
   "magic feels like physics"; the direct option is more controllable. Phase-1
   default `[assumption]`: perturb the field, let the law steer.
4. **Q4 — Overdraw's distinguishability from a scar.** A full-cascade discharge
   and an ordinary carved scar both raise ε² / lower q. If they quantize identically,
   the "explosive" outcome is indistinguishable from terrain damage, weakening the
   teachable tension. Needs the material-regimes doc's regime boundary to make the
   discharge *structurally* different (organized-front relaxing across rungs vs an
   amorphous scar).
5. **Q5 — Ignite's coupling to material-regimes.** The ignition front travels on
   the PDE wave operator; its speed, its explosive threshold, and its blowback
   curve all belong to the material doc. This design only fixes that ignite is a
   *moving organized-perturbation front* and that overdrawing it is the discharge
   trigger. The two docs must land on the same front-vs-explosive boundary.

### Phase-1 verdict

**The magic system is a Phase-1 consumer of Phase-1 deliverables, not a Phase-1
engineering burden.** Sense is the Phase-1 coherence reader already budgeted in
`chunk-field-quantization.md` (the published `field_q`/ε²/`grad` buffers are
already required for the readable field). Condense and dissolve are the Phase-1
terrain mechanisms (ρ/ε² quantization) with the player-return channel (Q4) as
their input — the "mining is a perturbation" feedback loop is a required
engine-side change regardless of the magic system. Shield/heal is condense +
opposing-EI at the same rung, no new physics. Steer and ignite are Phase-1-optional
— steer needs the ∇(g·Φ) publish (also budgeted) and ignite needs material-regimes.

**Verdict: feasible as a Phase-1 slice** — the coherence reader + condense +
dissolve + shield on an existing publish and the Q4 player-return channel make a
demoable "magic feels like physics" core with **zero new physics**; every channeled
op is the world's own quantization machinery driven by a job-dict input. The
binding risks are the seams, not the game: the Q4 input schema (this doc's Q1/Q2)
and the overdraw-vs-scar distinguishability that depends on the concurrent
material-regimes doc (Q4/Q5 above). Neither contradicts the async model — the
magic system is deliberately built as a *consumer* of the channel, never a touch
on physics state.
- [`the-midwife.md`](./the-midwife.md) — **the budget's first spend.** §1 the bounded EY injector + reader. Reverse pointer: the midwife's first read is the line's first bounded spend.
- [`the-understory.md`](./the-understory.md) — **the shade’s reader.** §2 Sense (the instrument whose channels the understory reads as the shade’s thin); §5.1 the read-only discipline. Reverse pointer: the understory reads the shade as a bounded consumer.
- [`the-chant.md`](./the-chant.md) — **the bounded voice.** §1 the bounded injector + reader; §5.1 the read-only discipline. Reverse pointer: the chant is a bounded voiced act, never a channel.
- [`the-lightning.md`](./the-lightning.md) — **the discharge register.** §4.3 the overdraw → full-cascade discharge; §1.2 the ε² debt; §5.1 the read-only discipline; §6 the open overdraw-vs-scar line. Reverse pointer: the lightning is the overdraw’s full-cascade discharge at weather scale.
- [`the-incantation.md`](./the-incantation.md) — **the budget.** §1 the coherence budget; §2 the six ops; §3 the cost bound; §5.1 the Q4 lane. Reverse pointer: the incantation’s spend is this budget and this lane.
