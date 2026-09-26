# The Tool: The Rung-Matched Work Object

**Question under design:** the corpus designs the instruments (which read —
[`field-instruments.md`](./field-instruments.md)), magic (which channels —
[`coherence-magic.md`](./coherence-magic.md)), custom blocks (regimes you place —
[`custom-blocks.md`](./custom-blocks.md)), the diving bell (a craft that descends —
[`deep-field-diving.md`](./deep-field-diving.md)), and the worn field (a garment —
[`worn-field.md`](./worn-field.md)). But no document designs the **primitive work
object** the whole economy rests on: the hand-tool the player holds and swings —
the pick, the axe, the primed-focus object whose bite actually *does* the mining.
`material-regimes.md` §4 fixes that hardness is rung depth, and §3/§5 fix the
fire-vs-explosive line, but nothing makes "your tool's rung must meet the
material's rung" a *thing in your hand*. **The most Minecraft-native object is
absent — silently presupposed by every harvest, mine, and carve.** This document
designs it: **the Tool is the rung-matched work object** — material-regimes'
hardness = rung (§4) made a thing in your hand.

A tool's *bite* is its rung-depth; its *durability* is its alloy's coherence read
through the `(1−q)` waste law ([`energy-harnessing.md`](./energy-harnessing.md) §2);
its *scar* is the honest charge/scar asymmetry of cutting deep
([`energy-harnessing.md`](./energy-harnessing.md) §3) — the asymmetry the diving
bell avoids at craft-scale. **A tool is a held regime:** the worn-field's tuple
(`worn-field.md` §1) realized as an alloy, a deliberate choice of bite-vs-scar you
swing, whose edge is itself a field read (a dull high-ε² blade tells you where the
metal came from — `wound-remembered.md`'s scar).

Companion to (all relative paths):
- [`material-regimes.md`](./material-regimes.md) — **THE bite and THE scar.**
  §4 hardness = rung (a tool's bite is its rung-depth; a shallow tool skates
  against a deeper-rung material); §3 the precipitation law and the fire-vs-explosive
  line (the honest trade of a deep bite); §2 the regime tuple `(ρ, q, ε², energy)` +
  `(ξ, ω₀², θ_c, n)` that the alloy *is*.
- [`energy-harnessing.md`](./energy-harnessing.md) — **THE wear and THE asymmetry.**
  §2 the `(1−q)` waste law (a high-q alloy bites clean and lasts; a low-q alloy
  bleeds its bite); §2.5 the deep-rung reaper (a deep tool scars the terrain it
  reaps); §3 the charge/discharge asymmetry (slow charge, fast scar) the tool's
  honest trade rides; §6 the no-free-energy cap.
- [`worn-field.md`](./worn-field.md) — **THE tuple worn.** §1 the `(ξ, ω₀², θ_c, n)`
  regime tuple realized on a body — a tool is the same tuple realized as an alloy
  in the hand, the active twin of the passive garment.
- [`deep-field-diving.md`](./deep-field-diving.md) — **THE craft-scale contrast.**
  §2.2 the net-negative hold (the tool is the hand-scale of the same hold);
  §3.2 the fire-vs-explosive line held at depth (the tool holds it at the bite,
  per swing, where the Bell holds it at the store).
- [`the-fallow.md`](./the-fallow.md) — **THE depletion.** §2a the mined vein (a
  worked deposit is gone forever — the tool's work is the window's depletion).
- [`the-walk.md`](./the-walk.md) — **THE carried load.** §3 a laden walk is a dear
  walk (the tool's weight in the crossing — a deep-rung tool is heavier under the
  river law).
- [`wound-remembered.md`](./wound-remembered.md) — **THE scar.** §1/§2 the
  scar-that-refuses and the maintenance-axis read (a dull high-ε² blade is the
  alloy's own scar history; the edge's read is where the metal came from).
- Skimmed: [`coherence-magic.md`](./coherence-magic.md) — §4.3 the overdraw (a tool's
  deep bite as the overdraw risk — a deep-rung swing is a controlled discharge held
  at the fire-vs-explosive line, and over-forcing it is the tool's blast).

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived), engine-verbatim, or explicitly flagged
**[design]** (a designed mapping / alloy surface over real channels, probe-calibrated)
or **[probe]** (a pre-registered Phase-1 measurement). The honest boundary is drawn
in §5 and never blurred: **the rung, the `(1−q)` waste, the precipitation law, and
the charge/scar asymmetry are their source docs' landed pieces; the bite/wear/scar
mappings and the held-regime framing are this doc's [design], probe-calibrated.**

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| The Tool = ? | The **rung-matched work object** — material-regimes' hardness = rung (§4) made a thing in your hand; the primitive under every harvest, mine, and carve, silently presupposed by the whole economy. |
| The bite = ? | a pick's bite is **its rung-depth** (hardness = rung, material-regimes §4): a deep-rung tool cuts down to deep matter; a shallow tool skates. |
| The wear = ? | the alloy's coherence reads as **durability** — the `(1−q)` waste law as tool-wear: a high-q low-waste alloy bites clean and lasts; a scar-tainted alloy dulls fast. The edge is a field read: a dull high-ε² blade tells you where the metal came from (wound-remembered's scar). |
| The scar = ? | the **charge/scar asymmetry at the tool** (energy-harnessing §3): a deep-rung tool cuts down to deep matter but scars the locality it cuts into more — the asymmetry the diving bell avoids at craft-scale. |
| The tool as a held regime = ? | the worn-field's tuple realized as an **alloy** — a deliberate choice of bite-vs-scar you swing; the edge's read is the alloy's own history (a clean high-q blade was forged from a clean locality; a scar-tainted blade was not). |
| Honest boundary = ? | the rung, the `(1−q)` waste, the precipitation law, and the charge/scar asymmetry are **their source docs' landed pieces**; the bite/wear/scar mappings and the held-regime framing are this doc's **[design]**, probe-calibrated. |
| Honest gates = ? | (a) the [design]/engine-real line; (b) **PHASE-1-ABLE** — a held work object bound to the published rung/`(1−q)` channels as bite/durability/scar is a bounded consumer + Q4 write, with the Phase-1 slice stated; (c) determinism; (d) the no-free-energy cap (a tool converts nothing); (e) accessibility (the tool's reads are the published channels, never hidden-only). |
| Feasibility = ? | **PHASE-1-ABLE** — the primitive work object, the thing ignored because the corpus went straight from materials to machinery. State the slice and the gates. |

---

## 1. The Tool, stated once

The corpus's closest primitives are all *mediated*. The instruments read the field
but do not move it. Magic channels the field but is a separate act, aimed with the
hand. Custom blocks are regimes you place at rest. The diving bell is a craft that
descends. The worn field is a regime worn passively. **None is the thing in your
hand that actually breaks the ground.** And yet the whole economy presupposes it:
hardness has a definition (`material-regimes.md` §4 — hardness is rung depth), ore
precipitates where `q` accumulates, the deep-rung reaper scar for its harvest, the
fallow depletes the worked vein — but the *instrument* that does all of it, that
turns "mining is a perturbation that lowers local ρ and raises local ε²"
(`material-regimes.md` §3/§4) into an act, is not designed. This is that design.

> **The Tool is the rung-matched work object.** It is material-regimes' hardness =
> rung (§4) made a thing in your hand — a held, aimed perturbation whose *bite* is
> its rung-depth. A deep-rung pick perturbs the field at a deep organization scale
> and cuts down to deep matter; a shallow pick perturbs shallowly and skates
> against anything finer. The tool is the primitive under every harvest, mine, and
> carve — the object the corpus jumped from materials to machinery without ever
> stopping to swing.

The Tool is **a held regime** (`worn-field.md` §1's tuple, realized as an alloy): an
authored `(ξ, ω₀², θ_c, n)` tuple, not a block with a "hardness" stat. Its three
reads — the bite, the wear, the scar — are each a designed mapping of a landed
source-doc quantity, and together they make the tool the honest, legible,
deterministic work of the field the whole economy rests on.

Distinct from everything adjacent: an instrument *reads*; a tool *moves matter*.
Magic is a body act; a tool is a held extension of it (the same ε²-perturbation
channel, aimed through an edge). A custom block is a placed regime; a tool is a
regime *you swing*. The garment is the passive twin — on you whether you act; the
tool is the active twin — taken up for the act. **Where magic channels the field and
the garment wears it, the tool works it — and working is the perturbation the whole
economy is made of.**

---

## 2. The tool's three reads

Each read is grounded in its source doc's real quantities; the *mapping* — how rung
reads as bite, how `(1−q)` reads as wear, how the charge/scar asymmetry reads as
scar — is this doc's **[design]**, probe-calibrated (§5), never asserted.

### (a) The bite — a pick's bite is its rung-depth

`material-regimes.md` §4 fixes hardness: **"Hardness is `n`, the rung depth. A
deeper-rung material is more ordered (lower ε²) and holds its φ-lock against a wider
range of perturbation — that *is* hardness, physically."** And the tool rule: **"Your
tool's rung must meet the material's rung. A coarse-rung pick perturbs the field at a
coarse organization scale; against a deeper-rung material that perturbation is below
the material's decoherence-resistance — the material does not scar, and the tool does
nothing."** The bite is this rule made a read:

> **A pick's bite is its rung-depth.** A tool whose rung meets or exceeds the
> material's rung perturbs the field at that scale and *takes* — mining is a
> perturbation that lowers local ρ and raises local ε² (material-regimes §3/§4),
> and it works only when the perturbation can break that rung's lock. A tool whose
> rung falls short does nothing against a deeper-rung material — the same condition
> as "a diamond block does not burn with a coarse fire": its coherence is too
> well-locked for a coarse attack (`material-regimes.md` §4).

**[design]** — the *bite mapping*. What the source doc lands is that the rung
semantics are real and the tool-material interaction is one law ("does this
perturbation exceed this rung's decoherence-resistance?" — the same condition as
ignition and blasting, at a lower magnitude). What is this doc's [design] is the
*swing-scale* of that law: how a deep-rung bite perturbs a deeper locality *per
swing*, how the bite's "takes" reads as a cut, and the per-swing perturbation
magnitude a held tool delivers (vs. the per-front magnitude of a fire). **This is
probe-calibrated** — the exact rung-step a pick's bite spans per swing, like every
other hardness→rung mapping, is Phase-1.5 tuning, not a stated number
(`material-regimes.md` §4's own honesty, and §7 open-Q5).

### (b) The wear — the alloy's coherence reads as durability

`energy-harnessing.md` §2 fixes the waste law: **"Every working machine wanders
`E_waste = (1−q)·E_throughput` as visible glow — the cost of running any regime at
partial coherence."** A tool is a working field system; its "throughput" is the
perturbation it delivers each swing. The wear is the waste law read as the tool's
own life:

> **A high-q low-waste alloy bites clean and lasts; a scar-tainted alloy dulls
> fast.** A tool forged from a coherent locality — an alloy whose own `q` sits high
> toward the attractor (`q ≈ 0.947`, canonical) — delivers its bite with minimal
> `(1−q)` bleed: the edge wastes little to glow, holds its organization, and keeps
> biting. A tool forged from a scar-tainted locality — an alloy whose `q` is dragged
> down, carrying the ε² of where it was mined — bleeds a larger `(1−q)` fraction
> *into the edge itself*: the edge sheds its organization as it bites, and the tool
> dulls fast. **The tool's wear is the `(1−q)` waste law made local, on the thing
> in your hand.**

**[design]** — the *wear mapping*. The source doc lands the waste law as the
machine-loss floor (a mechanism at coherence q is (1−q) inefficient, and the waste
is an observable glow). What is this doc's [design] is that *a tool's own alloy
carries a q* — that the metal the tool is made from holds the field-state of the
locality it was forged in (a clean high-q source → a clean high-q alloy; a
scar-tainted source → a dull-bleeding alloy) — and that the `(1−q)` bleed reads as
*durability* (edge wear), not just as glow. This is probe-calibrated: how much a
given alloy-`q` degrades the edge per swing, and how the edge's dullness presents,
are Phase-1 measurements over the published `q`/`ε²`.

**The edge as a field read.** Because the wear is the `(1−q)` waste law and the
waste is an observable, the alloy's history is legible *on the edge itself*:
`wound-remembered.md` §1/§2 reads a scar as a scar-that-refuses vs a dent-that-heals
off the published ε²-gradient and cadence. A dull, ε²-heavy blade is the same read
at hand-scale — a high-ε² edge *tells you where the metal came from*, exactly as a
wound's restless ε² names a deliberate break. A clean high-q blade was forged from a
clean locality; a scar-tainted blade was not — and the edge *says* so before the
smith does. This makes the tool's provenance honest by construction: its history is
not a hidden stat; it is the field's own channels read back from the metal.

### (c) The scar — the charge/scar asymmetry at the tool

`energy-harnessing.md` §3 fixes the asymmetry: **"Charge/discharge asymmetry
(honest): charging (condensing to a deeper rung) is slow and density-costly;
discharging (reaping) is fast and scars."** And §2.5 fixes the reaper's nature:
withdrawing deep rungs de-orders the local field (raises ε², lowers q) — the
by-product is a landscape wound. The tool's third read is this asymmetry held at the
hand's scale:

> **A deep-rung tool cuts down to deep matter but scars the locality it cuts into
> more.** A shallow bite removes shallow, low-rung matter with a modest ε² rise — a
> surface dent the field rounds. A deep-rung bite reaches deep, high-q matter but
> perturbs the locality at that deeper organization scale — it raises local ε²
> further and lowers q more, leaving a deeper scar for the same volume removed. **The
> scar is the honest price of the deep matter: the deeper the tool cuts, the more
> it wounds the ground it cuts.** This is the charge/scar asymmetry the diving bell
> avoids at craft-scale — the Bell collects through a contained shell, holding the
> scar at the shell and letting the region heal around it (`deep-field-diving.md`
> §2.2/§6.3); the tool does none of that. **The tool is the un-contained hand-scale
> face of the same withdrawal.**

**[design]** — the *scar mapping*. The source doc lands the charge/scar asymmetry as
the economic heart of the energy system (deep matter is slow to condense, fast and
scarring to reap) and the reaper's withdrawal de-orders its territory. What is this
doc's [design] is that *the tool's bite aggregates into that withdrawal* — that the
per-swing de-ordering scales with the tool's rung, so a deep tool's honest cost is
a deeper scar, and that the scar is the *visibility* of the no-free-energy cap at
the tool (below, §5d). This is probe-calibrated: the per-rung scar magnitude per cut
is a Phase-1.5 measurement, exactly like the reaper's scar magnitude
(`energy-harnessing.md` §2.5's honesty).

**The asymmetry as the tool's honest trade.** Because a deep tool bites deep *and*
scars deep, the tool is a deliberate choice, not a free upgrade: to reach the deep
matter you accept the deep scar. A shallow tool is gentle on the ground but cannot
reach the deep rungs. The player who wants deep matter *and* a clean locality must
either accept the scar, heal it (the world-repair of `energy-harnessing.md` §5.3), or
graduate to the craft-scale containment of the Bell. **The tool's scar is what makes
the deep bite honest — and what makes the Bell a meaningful later craft rather than a
redundancy.**

---

## 3. The tool as a held regime

`worn-field.md` §1 lands that a garment is the `(ξ, ω₀², θ_c, n)` regime tuple of
`custom-blocks.md` §1 realized as *worn* matter on the body. **A tool is the same
tuple realized as an *alloy* — a regime held in the hand, swung at the field.** The
garment is on you whether you act; the tool is taken up *for* the act. But they are
the same principle: a held regime is a deliberate coupling change, applied where the
hand reaches, and its three reads §2 are the alloy's tuple read out as behavior.

| Worn regime (garment) | Held regime (tool) |
|---|---|
| the `(ξ, ω₀², θ_c, n)` tuple as worn matter on the body | the same tuple as **an alloy in the hand** |
| re-shapes the wearer's own coupling, passively | re-shapes the hand's *perturbation*, actively — the edge delivers the tuple's bite |
| the passive, always-worn twin of the instrument | the **active twin** — taken up for the work act |
| a Q4 `{op, tuple, worldPos, rung, …}` write on the body | the same Q4 write, as the **forged tool's alloy tuple** held at the swing |

**The alloy's tuple reads as the tool's three reads.** The tuple's `n` is the bite
(§2a: rung-depth). The tuple's operative `q` (the field-state of the locality it was
forged from) is the wear (§2b: a high-q alloy bites clean, a scar-tainted one dulls).
The tuple's rung, swung, is the scar (§2c: a deep tool wounds deep). **A tool is
therefore not a crafted stat-block; it is the worn-field's tuple realized as a
deliberate bite-vs-scar choice you swing.** Forge high-rung, high-q matter and you
hold a deep, clean, heavy bite that scars deep. Forge shallow, low-q matter and you
hold a gentle, dull, quick blade that spares the ground and cannot reach the deep
rungs. **There is no free tool: every alloy is a point on the bite-vs-scar line,
and the cost of the deep bite is the deep scar.**

**The tool's honesty — the edge's read is the alloy's own history.** Because the
wear §2b is the `(1−q)` waste law and the waste is an observable edge-read, **a
clean high-q blade was forged from a clean locality; a scar-tainted blade was not —
and the blade says so.** A player who picks up a scavenged, scar-tainted pick and
swings it reads, in the fast-dulling edge and the heavy ε² it sheds, exactly what
wound-remembered's scar-that-refuses reads at terrain scale: *where the metal came
from*. There is no hidden "durability" stat; the tool's provenance is legible from
the field's own channels, on the tool itself. This is the held-regime framing's
ethical core: **the tool does not hide its lineage, because its lineage (the
locality's field-state it was forged from) is baked into the alloy it is made of.**

---

## 4. The honest boundary and gates

### (a) The [design]/engine-real line

| Quantity | Status | Basis |
|---|---|---|
| Hardness = rung depth (`n`); a tool's rung must meet the material's rung; mining is a perturbation that lowers ρ / raises ε² | **engine-real** | `material-regimes.md` §4/§3 |
| The `(1−q)` waste law, `E_waste = (1−q)·E_throughput` | **engine-real** | `energy-harnessing.md` §2 |
| The precipitation law — a worked deposit is gone forever | **engine-real** | `material-regimes.md` §3; `the-fallow.md` §2a |
| The charge/scar asymmetry (deep matter slow to condense, fast and scarring to reap); the deep-rung reaper's withdrawal de-orders its territory | **engine-real** | `energy-harnessing.md` §3/§2.5 |
| The fallow's depletion — a worked vein's locality is spent | **engine-real** | `the-fallow.md` §2a; `material-regimes.md` §3/§4 |
| The `ε²`/`q` maintenance-axis read (a scar that refuses vs a dent that heals) | **[design]**-landed over engine-real channels | `wound-remembered.md` §1/§2; `life-signal.md` §3 |
| **The bite mapping** — how rung reads as a per-swing cut on a held tool | **[design]**, probe-calibrated | this doc §2a |
| **The wear mapping** — that an alloy carries a field-state `q`, and the `(1−q)` bleed reads as edge durability | **[design]**, probe-calibrated | this doc §2b |
| **The scar mapping** — that the tool's per-swing de-ordering scales with its rung, aggregating into the reaper's withdrawal | **[design]**, probe-calibrated | this doc §2c |
| **The held-regime framing** — the tool as the worn-field's tuple realized as an alloy, a bite-vs-scar choice | **[design]** | this doc §3 |

The line is never blurred: **the rung, the `(1−q)` waste, the precipitation law, and
the charge/scar asymmetry are their source docs' landed pieces** — real, sourced,
already in the corpus. **The bite/wear/scar mappings and the held-regime framing are
this doc's [design]**, a designed surface over those landed quantities, probe-calibrated
like every peer read-doc's mapping. No claim here pretends the engine writes "tool"
records.

### (b) PHASE-1-ABLE — a held work object, bounded consumer + Q4 write

The Tool is **Phase-1-able** because its whole design is a bounded bind to the
published channels, with an honest mechanical slice gated on the Phase-1.5
per-material constants:

- **A tool is a bounded consumer + a bounded Q4 write.** It reads the published
  `ρ`, `q`, `ε²`, `∇(g·Φ)` at the swing's position (the ≈ 6 MiB publish,
  `corpus-reconciliation.md` — a few trilinear samples per swing, inside the
  ≈ 1–6 ms/tick budget, exactly the Weatherglass's cost profile
  `field-instruments.md` §1.4), and it perturbs the domain through the **Q4
  player-return channel** (`async-field-domain.md` §7) — the same write lane a
  machine or a channel uses. The tool is the *hand*-scale instance of the machine
  that is "a sampler-read plus a bounded write-back perturbation"
  (`energy-harnessing.md` §8). **No new channel, no new physics: a tool is a held,
  repeated, bounded perturbation off the publish, through the existing lane.**

- **The Phase-1 slice — the first pick over the living-terrain demo.** Concretely:
  on the Phase-1 living-terrain demo (`chunk-field-quantization.md` §1.2 box,
  `dt = 0.05`), **forge a shallow-rung pick from a clean locality, bite a real vein,
  read the wear, and feel the scar** — swing at a high-`q` precipitation, verify the
  perturbation lands as a bite (the material's rung is met), read the edge's
  `(1−q)`-driven wear over repeated swings, and read the locality's ε² rise as the
  scar. **This is the load-bearing first claim of the whole doc — that a held,
  rung-matched, bounded perturbation is a real, legible, costed work object** —
  before any material economy, any machinery, any craft tree. It proves the primitive
  the whole economy silently rests on.

- **The mechanical bite is gated on the Phase-1.5 per-material constants.** The
  *felt* bite — that a deep-rung tool reaches deep matter and a shallow one skates —
  needs the per-material/per-cell constants of `material-regimes.md` §7
  (`corpus-reconciliation.md` §4: the per-material `γ/ν/μ` + per-cell `ω₀²`/`ξ` that
  make distinct materials behave distinctly). Until those land, the tool's bite is a
  designed read over the base `(ρ, q, ε²)` — testable, but not yet the full
  rung-matched promise. **The Phase-1 slice states this honestly:** the *shallow*
  bite over a real vein (met rung, bounded perturbation, legible wear and scar) is
  Phase-1-able now; the *deep-rung* bite (hardness = rung made fully mechanical)
  lands with the Phase-1.5 constants. Same slice, honest staging.

### (c) Determinism — a hard gate

The field is deterministic (one PDE; `wound-remembered.md` §6c; `the-walk.md` §4c) and
the tool is a bounded read/write over it. Therefore:

> **Same tool, same field state → same bite, same wear.** The tool's bite (which
> rungs it breaks), its wear (how the `(1−q)` bleed degrades the edge), and its scar
> (how deep the locality's ε² rises) are each a **pure function of the tool's alloy
> tuple and the published field state it swings against** over its reading window —
> no hidden randomness, no player-relative variance. A player who re-swings the same
> pick at the same vein at the same field state gets the same cut, the same edge
> wear, the same scar. **This is a hard gate**, the property that makes the tool
> *readable* (a player learns a pick's bite, wear, and scar as true, reproducible
> facts about the field) rather than a hidden buff — inherited unchanged from the
> field's determinism.

### (d) The no-free-energy cap — a tool converts nothing

`energy-harnessing.md` §6's hard rule — **no conversion yields more than it sinks,
`output ≤ φ⁻¹·input`** — holds the tool exactly, stated in its most personal register:

> **A tool converts nothing — there is no bite that harvests more than it spends.**
> The tool does not generate coherence, ε², or matter; it is a bounded perturbation
> that *withdraws* ordered matter (the deep-rung reaper's withdrawal, §2.5) and
> *costs* coherence to hold its edge (the `(1−q)` waste, §2). **The deep bite's scar
> is the honest price of the deep matter** — the tool never returns more than it
> costs, because the deep scar (§2c) is the cap made visible at the hand. **The tool
> is never a mint** — there is no "dig with a high-q pick to synthesize coherence,"
> no tool that charges a capacitor by swinging, no edge that sheds into a harvestable
> drain (the Coda/Burden-farming closure, `signature-predator.md` §7e / `the-burden.md`
> §4, held unchanged). **And the tool's work is the fallow's depletion, held:**
> `the-fallow.md` §2a — a worked deposit is gone forever; a tool that re-bites a
> spent vein reads the empty, spent locality it cannot re-precipitate. **The tool
> works the window's depletion, never its mint** — the no-free-energy cap is the
> honest bound of everything it does.

### (e) Accessibility — the tool's reads are the published channels, never hidden-only

Per the instrument-family rule (`field-instruments.md` §2.1) and the accessibility
hard rule (`field-music.md` §6):

> **The tool's reads are the published channels.** The bite reads the material's and
> tool's rungs off the field's own `ρ`/`q`/`ε²`; the wear is the `(1−q)` glow and
> the edge's ε²; the scar is the locality's rising `ε²` and falling `q` — **every
> read the tool presents is also readable, more laboriously, from the reader overlay
> and the published channels themselves.** A player who never uses a "tool health" or
> "tool quality" HUD loses nothing: the tool's bite, wear, and scar are the same
> channels the reader (`coherence-magic.md` §2), the Weatherglass
> (`field-instruments.md` §1.2), and the glass always render, at the swing's scale.
> **The tool is an idiom over real channels, never a hidden mechanic** — structurally
> guaranteed by the shared-publish architecture. A dull high-ε² edge is *legible* as
> a dull high-ε² edge before any smith or HUD explains it.

---

## 5. Feasibility verdict

**PHASE-1-ABLE — the primitive work object, the thing ignored because the corpus
went straight from materials to machinery.**

The corpus designs the instruments (which read), the magic (which channels), the
custom blocks (which sit), the Bell (which descends), and the worn field (which you
wear) — but the hand-tool that actually *breaks the ground* was presupposed, never
designed. **The Tool fills the gap:** the rung-matched work object, hardness = rung
made a thing in your hand, with a bite (rung-depth), a wear (`(1−q)`-as-durability),
and a scar (the charge/scar asymmetry made honest at the hand), and the held-regime
framing that a tool is the worn-field's tuple realized as an alloy — a deliberate
bite-vs-scar choice whose edge reads its own history.

**The Phase-1 slice (the first pick):** on the living-terrain demo, forge a shallow
pick from a clean locality and **bite a real vein, read the wear, feel the scar** —
a bounded consumer of the publish + a bounded Q4 write, proving the load-bearing
claim (the primitive work object is a real, legible, costed act) before any material
economy or machinery exists. It de-risks the same `(1−q)` and charge/scar mechanics
the deep-rung reaper and the Bell rest on, at the hand's scale, first.

**The gates, all held (§4):** (a) the [design]/engine-real line — the rung, the
`(1−q)` waste, the precipitation law, and the charge/scar asymmetry are their source
docs' landed pieces; the bite/wear/scar mappings and the held-regime framing are this
doc's [design], probe-calibrated; (b) **PHASE-1-ABLE** — a held work object bound to
the published rung/`(1−q)` channels as bite/durability/scar, with the mechanical bite
gated on the Phase-1.5 per-material constants; (c) determinism — same tool, same field
state → same bite, same wear, a hard gate; (d) the no-free-energy cap — a tool
converts nothing, the deep bite's scar is the honest price of the deep matter, the
tool is never a mint, the fallow's cap held; (e) accessibility — the tool's reads are
the published channels, the edge's story never hidden-only.

**Binding risks, in order:** **(a)** the **Phase-1.5 per-material constants**
(`material-regimes.md` §7; `corpus-reconciliation.md` §4) — the *mechanical* bite
(hardness = rung fully felt) rides these; until they land, the tool's bite is a
designed read over the base channels, testable but not yet the full rung-matched
promise, and the doc says exactly what that means (§4b). **(b)** the **wear-adjacent
read strength** — does the `(1−q)`/edge-ε² wear read *felt* enough (an edge that
visibly dulls and reads its provenance) to be worth the designed surface, or does the
spread wash out at swing-pace? The Phase-1 slice is the pre-registered probe that
answers it; a flat read pushes the tool's wear to pure presentation, still legitimate.
**(c)** the **scar calibration** — the per-rung scar magnitude per cut is a Phase-1.5
measurement; if a shallow tool's scar is indistinguishable from a deep one's, the
bite-vs-scar trade collapses to a binary, and the doc's honesty about the deep matter
must weaken to match. **(d)** the **Q4 lane budget** — the tool is a bounded
repeated write through the player-return channel; like every machine
(`energy-harnessing.md` §7 Q5), it must be confirmed within the async-domain budget, a
per-tick measurement. None contradicts the async, dual-world, or regime-collapse
architecture — the tool is a consumer of the publish and a bounded writer through the
existing lane, the hand-scale of the withdrawal the whole economy already lands.

> **The honest statement that makes this doc load-bearing: the corpus's economy
> presupposes the hand-tool — the thing that bites the vein, wears as it works, and
> scars what it cuts — and never designed it. The Tool is that primitive: material
> regimes' hardness = rung made a thing in your hand, a held regime whose bite is
> its rung-depth, whose wear is the `(1−q)` waste law read as the alloy's own life,
> whose scar is the honest charge/scar asymmetry of cutting deep. A tool converts
> nothing and never mints; the deep bite's scar is the price of the deep matter; the
> edge reads the alloy's own history, so a clean blade was forged clean and a
> scar-tainted one says so. It is the primitive under every harvest, mine, and carve
> — and it is Phase-1-able, the honest first claim, before the corpus jumps from
> materials to machinery.**

---

## Open questions

1. **The bite calibration.** How a held tool's rung-step reads as a *per-swing cut*
   against a material's decoherence-resistance, and how deep a bite reaches per swing,
   are the probe-calibrated bite mapping (§2a/§4a). The Phase-1 slice measures the
   *shallow* bite (met rung over a real vein); the deep-rung bite's magnitude is a
   Phase-1.5 measurement, exactly as `material-regimes.md` §4/§7 open-Q5 honest about
   the hardness→rung constant table being tuning, not physics. **[probe]**
2. **The wear's felt strength (§5).** Does the `(1−q)`/edge-ε² wear read *felt* enough
   (a visibly dulling, provenance-reading edge) to justify the designed surface, or
   does the waste spread wash out at swing-pace — pushing the tool's wear to pure
   presentation? A flat read (the `(1−q)` spread too small, the same finding
   `the-walk.md` open-Q3 pre-registers for the shared L-probe) is an honest, weaker
   outcome. **[probe]**
3. **The scar's rung-dependence (§5).** How much more does a deep tool's rung scar
   the locality per cut than a shallow one's, and does it read distinctly enough that
   a player *chooses* bite-vs-scar rather than always taking the deepest tool? If the
   scar spread is too shallow to separate rungs, the trade collapses to a binary and
   must be re-framed. **[probe]** — the charge/scar asymmetry's hand-scale calibration.
4. **The alloy's carrying of a field-state `q`.** The wear mapping (§2b) assumes an
   alloy *holds* the field-state of the locality it was forged from — a clean source
   → clean alloy, a scar-tainted source → dull alloy. Is that provenance-baking real
   enough (does the forged matter's `q`/`ε²` persist in the object), or does it
   re-quantize to the operation's ambient `q`? The former keeps the honest edge-read;
   the latter weakens it to "the edge reads the swing's field, not the metal's."
   Rides the material-regimes §7 realizability and the merge lineage's object-storage
   (`ksp-kernel.md` §1.2 — a body is a capacitor at its rung). **[design]/[probe]**
5. **The tool's relation to the reaper and the Bell.** Is the deep tool the
   *un-contained* hand-scale of the reaper's withdrawal (§2c), with the Bell its
   craft-scale containment (`deep-field-diving.md` §2.2)? That composition is the
   designed default; whether a player *graduates* from deep-tool-scars to Bell-holds
   (a real progression) or the two coexist as separate localities is a designed tuning
   of the scar's severity. **[design]**

---

## Cross-references

- [`material-regimes.md`](./material-regimes.md) — **THE bite and THE scar.** §4 hardness = rung (a tool's bite is its rung-depth); §3 the precipitation law + the fire-vs-explosive line (the honest trade of a deep bite); §2 the regime tuple the alloy *is*; §7 the per-material-constants gate the mechanical bite lands with.
- [`energy-harnessing.md`](./energy-harnessing.md) — **THE wear and THE asymmetry.** §2 the `(1−q)` waste law (the tool's wear); §2.5 the deep-rung reaper (the tool's withdrawal and scar); §3 the charge/scar asymmetry (the tool's honest trade); §6 the no-free-energy cap (a tool converts nothing).
- [`worn-field.md`](./worn-field.md) — **THE tuple worn.** §1 the `(ξ, ω₀², θ_c, n)` regime tuple — the tool is the same tuple realized as an alloy, the active twin of the passive garment; §5/§6 the honest boundary and gates this doc mirrors.
- [`deep-field-diving.md`](./deep-field-diving.md) — **THE craft-scale contrast.** §2.2 the net-negative hold (the tool the hand-scale of the same hold, un-contained); §3.2 the fire-vs-explosive line held at the bite where the Bell holds it at the store; §6.3 the containment the tool lacks.
- [`the-fallow.md`](./the-fallow.md) — **THE depletion.** §2a the mined vein (a worked deposit is gone forever — the tool's work, the window's depletion); §5d the no-free-energy cap (the tool never a mint).
- [`the-working-song.md`](./the-working-song.md) — **the labor the song paces.** §3a there
  reads §2a this doc's bite as the repetitive, phase-locked perturbation the lumber-camp's
  rhythm coordinates; §4b there's bounded Q4 write is the op the song's strokes ride.
  Reverse pointer: the working-song turns the tool's bite into a coordinated working.
- [`the-market.md`](./the-market.md) — **the traded tool's provenance.** §2.2 there reads
  §2 this doc's edge — where the metal came from, the worked vein's rung, the alloy's `q`
  — as the traded pick's booked provenance: a scar-tainted blade books as scar-tainted, a
  clean one clean, so no trader can pass one off as the other (§2.2 there). Reverse
  pointer: the market's value books the tool's edge.
- [`the-walk.md`](./the-walk.md) — **THE carried load.** §3 the laden crossing (the tool's weight in the crossing — a deep-rung tool is heavier under the river law, the walk's dearness at hand-scale).
- [`wound-remembered.md`](./wound-remembered.md) — **THE scar.** §1/§2 the scar-that-refuses and the maintenance-axis read (a dull high-ε² blade reads the alloy's provenance; the edge's read is where the metal came from); §3.3 the cruel-world rule (an intentional scar readable as intentional — the scar-tainted blade's honesty).
- [`coherence-magic.md`](./coherence-magic.md) — skimming **§1** the player as a bounded EY injector + ε² vent (the hand's own coherence source the tool extends), **§4.3** the overdraw (a deep-rung swing as a controlled discharge held at the line; over-forcing it is the tool's blast), **§5.1** the Q4 player-return channel the tool's write rides.
- [`field-instruments.md`](./field-instruments.md) — **THE family rule (§2.1)** (a tool is a bounded consumer + write, never a new channel); §1.4 the sample-at-position cost pattern (a few samples per swing, inside the ≈ 1–6 ms/tick budget).
- [`async-field-domain.md`](./async-field-domain.md) — §7 Q4 the player-return channel the tool's bounded write-back rides.
- [`the-loan.md`](./the-loan.md) — **the future contribution.** §2.1 there reads §2
  this doc's provenance read (a loan books a tool's future work as the forward
  order's object — the picked contribution of a swing to come). Reverse pointer: a
  loan is a tool's future contribution booked.
- [`the-granary.md`](./the-granary.md) — **the kept steel's store.** §2 there reads §2
  this doc's (a) bite, (b) wear, (c) scar and §3 the held-regime tuple — the forge's
  store holds the alloy the tool will be; §4d a tool converts nothing. Reverse pointer:
  the granary holds the alloy the tool will be.
- [`the-cart.md`](./the-cart.md) — **the shared wear.** §2 there reads §2b this doc's
  `(1−q)` waste law as the alloy's life (the wheel-carriage's wear), §3 the held-
  regime tuple (a cart is a held regime on wheels), §4b the slice. Reverse pointer: the
  cart wears the way the tool does.
- [`the-breath.md`](./the-breath.md) — **the bite at depth.** §2 there reads §2a this
  doc's rung-matched work object (what the breath's reserve powers at depth), §2c the
  charge/scar asymmetry, §4d a tool converts nothing (the bite spends the breath, never
  mints it). Reverse pointer: the breath powers the tool's deep bite.
- [`the-compost.md`](./the-compost.md) — **the worn steel's sink.** §2b there reads the
  `(1−q)`-as-wear (the spent matter's first source), §3 the held regime, §4b the
  Phase-1-able wear read, §4d a tool converts nothing. Reverse pointer: the compost
  takes the tool's worn steel.
- [`the-carry.md`](./the-carry.md) — **the single held arrangement.** §2a there reads
  the bite (the rung-matched work object the pack holds); §3 the held-regime tuple (a
  pack is a held structure on the body); §4d a tool converts nothing (the pack's
  cap). Reverse pointer: the carry is the tool's held collection.
- [`the-quarry.md`](./the-quarry.md) — **the bite and the scar.** §2a there reads the
  bite (the rung-matched work the cut's face exposes); §2b the wear (`(1−q)`-as-
  durability); §3 the held regime; §4b the Phase-1 slice; §4d a tool converts nothing.
  Reverse pointer: the quarry works the tool's bite at the cut.
- [`the-mint.md`](./the-mint.md) — **the rung-marked token.** §2/§3 the bite, wear, scar, and held-regime tuple (the coin’s sigil marks its rung the way a tool’s edge reads its metal); §4d a tool converts nothing. Reverse pointer: the coin is the tool’s rung-marked token.
- [`the-shaft.md`](./the-shaft.md) — **the dug-with.** §2 the instrument. Reverse pointer: a shaft is dug with the tool’s honest work.
- [`the-tunnel.md`](./the-tunnel.md) — **the line’s bite.** §2(a) the pick’s bite is its rung-depth; §2(b) wear = waste; §3 the held regime; §5b PHASE-1-ABLE. Reverse pointer: a tunnel is dug by the tool’s bite repeated along the line.
- [`the-crane.md`](./the-crane.md) — **the built-rung.** §2(a) the pick’s bite is its rung-depth; §3 the held regime; §5b PHASE-1-ABLE. Reverse pointer: the crane is a built machine a rung-matched tool dresses and keeps.
- [`the-anchor.md`](./the-anchor.md) — **the setting bite.** §2(a) the pick’s bite is its rung-depth; §4b PHASE-1-ABLE. Reverse pointer: the anchor bites into the bed the way a tool bites into rung-matched matter — the hold’s grip a real bite, never a stick.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers (the ≈ 6 MiB publish = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1; the 192³/64³/12³ box; `dt = 0.05`; `ξ = φ⁶ ≈ 17.94`; `φ⁻² ≈ 0.382`; `τ_c = 0.5`; `π/ρ` clamp 0.72; `ω₀² = 20.0`; `q ≈ 0.947` attractor; `q ~ 1e-3…1e-1` noise; the ≈ 1–6 ms/tick sample budget; the ≈ 40 ns/entity river-law steer; the ≈ 2,000 entity cap); **cited, not re-derived.**
- [`the-bedrock.md`](./the-bedrock.md) — **the bite's wall.** §2a there reads §2a this
  doc's bite — a tool whose rung meets the material's rung perturbs it; **the tool's
  bite skates on the bedrock** (no tool exceeds the floor's rung). Reverse pointer:
  the bedrock is the wall the tool's bite cannot cross.
