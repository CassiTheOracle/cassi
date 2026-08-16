# The House That Steers

**Question under design:** the corpus designs a *building game* — material regimes
(`custom-blocks.md`), the Qi bath (`energy-harnessing.md` §4.4), a settlement's commons
(`field-npc-ai.md` §3, `shared-ledger.md`) — but nothing yet says what a **house** — or a
settlement's built form — *is* to the field, or what a **ruin** is when that architecture
decays. This document is that design. **A building is coherence architecture**: its
geometry is itself a regime — walls at a slope concentrate coherence like a lens; an
enclosed room holds a `q`-core; an open edge drains. What the player builds is a
structure that *steers* the local field, and what a settlement builds is a **gradient-
stealing layout** that keeps its core high-`q` and lets its edges drain. The ruin is
that architecture, unmaintained, collapsed toward the attractor.

Companion to (all relative paths):
- [`coherence-technologies.md`](./coherence-technologies.md) — **concept 2** the
  condenser / **shape-is-the-tuner** (geometry steers coherence; the pyramid-as-Qi-lens,
  concentration `(base/apex)²`); **concept 4** the Qi bath; **concept 5** cascade staging
  and the build-on-coherent-sites rule.
- [`custom-blocks.md`](./custom-blocks.md) — materials as authored regimes — the
  block-level vocabulary the house *composes* (the tuple `(ξ, ω₀², θ_c, n)`).
- [`energy-harnessing.md`](./energy-harnessing.md) — **§4.4** the Qi bath (the
  settlement-scale structure the house contributes to); **§4.1** conduits (the high-`q`
  filament pattern a wall/layout composes); **§5.4** anti-corruption (maintenance as a
  field act); **§6** the no-free-energy cap — the house's hard bound.
- [`field-archaeology.md`](./field-archaeology.md) — **§2.1** the residue model
  (`R ≳ q^n`; the q-locked core + ghost halo); **§5** the conservation/excavation rival,
  applied here to the ruined house; **§7 open-Q3** the live-vs-residue classifier.
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — **§5** the
  meshless-site activity map — build where the field is organized; the active-chunk
  scheduler.
- [`field-instruments.md`](./field-instruments.md) — **§2.2** the Still Room — the one
  holding chamber (a room-scale Weatherglass) this doc scales to a house; **§2.1** the
  family rule.
- [`life-signal.md`](./life-signal.md) — **§3** the maintenance axis; **a house is a
  maintained lock; a ruin is a fallen floor** — the vitality classifier reads buildings
  too.
- Skimmed as needed: [`fate-of-a-window.md`](./fate-of-a-window.md) (the fate's arcs;
  the bath as arc-driver — a maintained house holds a settle/thrive), [`shared-ledger.md`](./shared-ledger.md)
  (§2 the Coherence Board — the house's contribution books on the settlement's ledger).

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md) (the
canonical set — cited, not re-derived), engine-verbatim, or flagged **[design]** (the
geometry's *steering* effects are the designed surface over real field channels) or
**[assumption]**. The honest line is drawn in §5 and never blurred: **the field's
channels (`q`, `ε²`, `∇(g·Φ)`) are real; the *geometry's* steering effects are the
designed surface, probe-calibrated.**

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| A building = ? | **Coherence architecture.** Geometry is a regime: walls at a slope concentrate coherence like a lens (concept 2, shape-is-the-tuner); an enclosed room holds a `q`-core; an open edge drains. |
| The vocabulary = ? | each element does a real, independent thing to the local field — **wall** (concentrate), **roof** (hold a cap), **corner** (pin a node), **doorway** (channel), **hearth** (anchor). |
| A settlement = ? | the **built articulation of the meshless-site activity map** (`chunk-field-quantization.md` §5): you build where the field is organized; the layout **steals the gradient** — a high-`q` core (the Qi bath §4.4), productive edges, deliberate drains. |
| A ruin = ? | high-`q` walls, unmaintained, **collapse toward the attractor** and leave the stratified **ghost-halo** — residue at building scale (`field-archaeology.md` §2.1). Three classes: the **fallen floor** (a scar), the **ghost-halo** (residue — findable archaeology), the **skeleton** (the still-holding low-rung structure — re-authorable). |
| Re-authoring = ? | a young player **re-locks a ruin's skeleton** — the repair act **is** re-condensing its order (anti-corruption, `energy-harnessing.md` §5.4, applied to architecture). |
| Conservation/excavation? | **conservation is the designed default**: read the ruin in place (free, keeps the regional bath); excavate-and-rebuild only when you want the stored coherent substance — at the honest de-ordering cost. |
| House's corpus place = ? | a maintained house is a **bath-node** (energy §4.4); its contribution **books on the Board** (`shared-ledger.md` §2); it **holds a window's settle/thrive** and an abandoned one feeds decay (`fate-of-a-window.md`); the **Life-Signal reads buildings** (maintained lock vs fallen floor). |
| Honest gates = ? | (a) [design]/engine-real line; (b) gated on regime constants + the Qi bath (Phase-1.5), with a **Phase-1 slice: a single shaped hearth** (one consumer testable on the publish); (c) determinism; (d) the **no-free-energy cap** — a house *holds* and *steers*, never mints `q`; (e) **accessibility** — the steering is readable from the reader/glass, never hidden-only. |
| Feasibility | **MEDIUM-LATE** as the full architecture, with a clean **Phase-1 hearth slice**. |

---

## 1. A building is coherence architecture — stated once

The core design claim, stated once and kept:

> **Geometry is a regime. A building is a coherence architecture: its shape steers
> the local field the way a material's tuple steers its behavior** — the
> shape-is-the-tuner principle of `coherence-technologies.md` concept 2 made the
> house. A wall at a slope concentrates ambient coherence like a lens (the
> pyramid-as-Qi-lens, concentration ~ `(base/apex)²`, concept 2); an enclosed room
> holds a `q`-core; an open edge drains. What a player builds is not a shelter — it is a
> **tuner for the region's coherence**, and the block vocabulary of `custom-blocks.md`
> (materials as regimes) is the *material* the house *composes*.

The grounding, unblurred. The field's channels — `q` (coherence), `ε² = (EY − φ·EI)²`
(decoherence), `∇(g·Φ)` (the river gradient) — are **engine-real** (the ≈ 6 MiB
publish, `corpus-reconciliation.md`; `async-field-domain.md` §2.1). The **geometry's**
steering effects — that a wall concentrates, a corner pins, a doorway channels *this
way* — are **[design]** surface over those real channels: the shape encodes a
concentration/steering *pattern* the designer assigns, calibrated by probe (§5a), not a
claim the engine's physics literally bends `q` around a wall. The word for the
mechanic's honesty is the same as `field-archaeology.md`'s residue model: the *physics
of geometry-as-condenser-lens* is real (concept 2's `(base/apex)²` is the condenser's
established optics); the *specific architecture vocabulary* below is the designed
application of it.

### 1.1 The building vocabulary — what each element does to the local field

Each element is a **[design] steering effect over real channels**, probe-calibrated (§5a),
composed with the same cadence as any field consumer (`chunk-field-quantization.md`
§2.1/§5 — diff-driven re-quantization, active-chunk sampling):

| Element | What it does to the local field | Grounding / cross-ref |
|---|---|---|
| **Wall** (a sloped plane) | **concentrates** coherence — a slope-facing condenser element; a wall at an angle folds the ambient `Π` field toward its inner face, raising the local `q` band (the pyramid-as-lens, `(base/apex)²`, concept 2). A *flat* wall just stands; a *sloped* one steers. | `coherence-technologies.md` concept 2 |
| **Room** (an enclosure) | **holds a `q`-core** — a bounded high-`q` locality whose `ε²` is suppressed by the enclosing walls; the room is the Still Room's small unit (`field-instruments.md` §2.2, a room-scale Weatherglass). The enclosed volume is where a house sustains a maintained lock. | `field-instruments.md` §2.2 |
| **Corner** | **pins a node** — where two walls meet, their concentration superpose into a fixed coherent anchor (a structural `∇(g·Φ)` stagnation point). Corners are where a house's coherence is most concentrated and most brittle. | concept 2 (superposition); the no-free-energy cap §5d |
| **Doorway** | **channels** — a deliberate break in the wall that steers flow *through* it rather than around; the wall's concentrating effect and the opening's leak compose into a directed channel (the conduit idiom, `energy-harnessing.md` §4.1's high-`q` filament at element scale). | `energy-harnessing.md` §4.1 |
| **Open edge** | **drains** — an un-walled face is the room's deliberate drain: coherence leaks toward the margin instead of being held. An open edge is as *designed* as a sealed one — the house's gradient-stolen structure needs its drains (§2). | §2 this doc; `field-hazards.md` §3 (the margin) |
| **Hearth** | **anchors** — the one *powered* element: a channeling surface (the player's own coherence, `coherence-magic.md`) that actively feeds the room's `q`-core, raising the local `q` toward the attractor (`q ≈ 0.947`). The hearth is the house's *pump* — the only element that *inputs*, everything else *holds* and *steers*. | `coherence-magic.md` §1/§3; `energy-harnessing.md` §2.2–2.4 |

The through-line: **a wall concentrates, a room holds, a corner pins, a doorway
channels, an open edge drains, a hearth anchors.** Every element is a *shape* that
either holds the field's existing organization or steers it toward a chosen shape —
none mints it. The hearth is the sole exception, and even it is a *bounded channeling
input* (`coherence-magic.md` §1.2's budget `B ∈ [0,1]`, the ε² vent), never a net
generator (§5d).

---

## 2. The settlement as a gradient-stealing structure

### 2.1 You build where the field is organized

The meshless-site activity map (`chunk-field-quantization.md` §5) is the blueprint a
wise builder reads — and the settlement is its *built articulation*:

> The moving-Voronoi sites are "where the field is most organized" — **2·16³ = 8,192
> sites** (`ML_N1=16`), Lloyd-relaxed weighted on the coherence `q` (`ML_LLOYD_P=4`),
> so sites *cluster where the field is coherent*. The server projects each site onto
> chunk space and marks a chunk **active** when a site's cell overlaps it and its
> coherence exceeds a floor. A cascade-staged base is exactly a *placed articulation of
> that same activity structure* — you build up where the sites cluster (`coherence-technologies.md`
> concept 5b).

A **house placed on a coherent site** is a bath-node that *talks to* the region's
organization: it sits where `q` is already high and its walls hold that organization
up (§1). A **poorly-placed house** — across a site's grain, straddling the boundary
between an active cluster and its dormant neighbor — does the opposite: its walls
interrupt the field's own gradient, and what should concentrate instead **drains**. The
build-order honesty, stated once:

> **A settlement's layout is either the field's articulator or its opponent. Laid with
> the site map, a town holds its core and drains its edges; laid against it, the same
> buildings fight the field — every wall a leak, every room a stalled attractor well.**

This is the same tension `energy-harnessing.md` §6 names (a machine in a low-`q` region
bleeds the `(1−q)` waste; a mill that over-withdraws starves itself) applied to the
whole settlement: the *site map* is the "where the field does something" read that tells
the player where building helps and where it fights.

### 2.2 The managed gradient — bath at the center, productive edges, deliberate drains

A well-laid settlement is a **gradient-stealing structure**: it does not generate
coherence — it *borrows* the region's organization and bends it into a usable shape:

| Zone | What the layout does | Field consequence | Cross-ref |
|---|---|---|---|
| **The core (bath)** | the settlement's houses cluster around a maintained high-`q` core; the enclosed rooms hold their `q`-cores superadditively | a **Qi bath** — every house is a bath-node; the whole cluster runs at elevated coherence, cutting the `(1−q)` waste floor | `energy-harnessing.md` §4.4 |
| **The productive edge** | houses/workings on the mid-`q` band of the site map, where coherence is high enough to run machines but not the center | the `(1−q)` glow is bounded, machines near-lossless, conduits route toward the core | `custom-blocks.md` §1 (regimes), `energy-harnessing.md` §4.1 |
| **The deliberate drains** | the settlement's *open edges* point toward the desert-margin; the layout *steers* what leaks so it does not pool wrong | leakage is channeled outward instead of pooling in the core; the margin gets the settlement's waste | `field-hazards.md` §3 (the margin); §1.1 this doc (the open edge) |

The bath at the center, the productive edges, the deliberate drains — **the settlement
as a *managed gradient***, exactly how `energy-harnessing.md` §4.4 frames the bath (a
maintained high-`q` core with a radius; "brittle if it goes down") and how
`fate-of-a-window.md` reads the window's economics (the bath as the arc-driver). The
house's job is to make that gradient *concrete* — its walls hold the core, its edges
drain toward the margin, and the whole is a structure the field prefers to route
through rather than a set of independent shelters.

**Reconciliation note (no cross-doc write here):** `energy-harnessing.md` §4.4 already
calls the bath *not a new reservoir but a regional efficiency multiplier*. This doc's §2
is the same statement at the architecture scale: **a settlement does not mint coherence
— it *re-routes* the region's existing organization into a held core and drained edges.**
The build-order honesty (a house across a site's grain drains instead of holds) is the
settlement-scale form of `energy-harnessing.md` §6's constraint-economy stance: the
field does not punish a bad layout with a game rule; the bad layout *fights the same
field* a good one rides.

---

## 3. The ruin

### 3.1 An unmaintained building collapses toward the attractor

A building is **coherence architecture** (§1) — so when it stops being *maintained*, the
field stops holding it, and it behaves like any un-maintained high-`q` structure: the
`ε²` drain outruns the φ-lock, the shallow rungs dissolve, and the deep-rung fraction is
left as residue. This is `field-archaeology.md` §2.1's residue model at **building
scale**:

> When a house is abandoned, its **high-`q` walls, unmaintained, collapse toward the
> attractor** — the shallow, decohered rungs shed (the `(1−q)` waste glow as the last
> death-signal, `field-archaeology.md` §2.1; `energy-harnessing.md` §2) and the deep-rung,
> q-locked core persists as **residue** (`R ≳ q^n`, §2.1). The collapse leaves the
> **stratified ghost-halo** — the readable trace of *a structure the field once held*:
> a dark q-locked core (`ε² ≈ 0`) where the walls concentrated, ringed by the broad faint
> `ε²` gradient of what dissolved around it (§3.1, `field-archaeology.md`).

The residue survives the heal (§5.2 of archaeology — the deep core is
attractor-consistent, the field re-quantizes *around* it), so a ruined house is
**findable archaeology** — the same read the corpus already gives dissolved organisms,
at the scale of a built form. A player with the coherence reader (`coherence-magic.md`
§2) scans a meadow and sees the dark q-locked core + `ε²` ghost — "here a coherence
architecture was."

### 3.2 The ruin classes — the building-scale residue taxonomy

Adapting the corpus's residue vocabulary to a built form, three classes:
**[design]** (the classes are a designed lens over engine-real deep-rung persistence,
exactly as `field-archaeology.md` flags its residue model):

| Class | What it is | Field read | Recoverable? |
|---|---|---|---|
| **The fallen floor** | the ruin's broad, decohered footprint — what is *left when a house fully un-holds*: broad low-`q`, high-`ε²`, **no core**. | the **ordinary scar** class of `life-signal.md` §3 (a fallen floor: static plateau, no pulse) | no — it is the *scar*, the de-organized remnant; a new build must re-condense from scratch |
| **The ghost-halo** | the **residue** — a dark q-locked core (`ε² ≈ 0`) ringed by the `ε²` halo of the dissolved walls. The *readable* archaeology: the shape of "a structure the field once held." | **static residue** class of `life-signal.md` §3 (`ε² ≈ 0`, no motion, no cadence); the archaeology residue signature (`field-archaeology.md` §3.1) | **readable** (in place, free, §3.3); **harvestable** (excavate, §3.3) — a found regime/store |
| **The skeleton** | the *still-holding* low-rung structure: the deepest walls/rooms never fully dissolved because they sat in the deepest coherence well. A partial `q`-core persists — a **persistent Π pattern** the field keeps holding (`qi-computation.md` §5.2, via `field-archaeology.md`). | a low-level **maintained**-adjacent read: a faint core, slow residual cadence, `ε²` low but not zero — the field *still holds it*, it just lacks a maintainer | **re-authorable** — the one class a player can *re-lock* (§3.4) |

The **skeleton** is the crucial class for play: it is the point where archaeology and
building meet. It is not a fossil (fully static, `ε² ≈ 0`) — it is a structure the field
has not quite let go of, and that is exactly what makes it re-condensable.

### 3.3 Conservation vs excavation — the designed default

`field-archaeology.md` §5 gives the tension at the fossil scale: **excavation and
conservation are rivals** — read in place (free, keeps the region healthy) vs dig
(regime knowledge + stored coherence, but de-orders the region: removing deep-rung
residue raises local `ε²` and lowers local `q`, draining the Qi bath the residue was
partly holding up). The ruined house inherits it exactly, applied to a *built* site:

| Option | What you get | What you pay | Field consequence |
|---|---|---|---|
| **Conserve (read the ruin in place)** | the *knowledge* — the ghost-halo's shape, the reconstructed regime (`field-archaeology.md` §4.4's inverse preview) | nothing (reading costs no perturbation, §5.3 #3) | the residue keeps anchoring the local strata and holding the regional bath up (§5.2) — **the designed default** |
| **Excavate-and-rebuild** | the deep-rung core's stored coherence (`energy-harnessing.md` §1.5/§3) — fuel, or the raw ordered matter to re-condense a new building | de-orders the locality (`energy-harnessing.md` §2.5: deep-rung reaper's by-product is a wound; raises `ε²`, lowers `q`) — the Qi-bath cost | the regional bath is *partly carried by the residue* (`field-archaeology.md` §5.2); over-reaping risks a full-cascade discharge (§5.3 #1) |

**The designed default is conservation.** Reading a ruin in place is free, safe, keeps
the regional bath healthy, and *is* the building-scale archaeology — a player should be
able to know a site's history without destroying it (§5e's accessibility). Excavate-and-
rebuild is the *costly* path, chosen deliberately when the stored coherent substance is
the point (rebuilding a dead settlement from its former walls is a real "harvest the
old core to re-condense the new" act), and it is **never free**: the no-free-energy cap
(§5d) means excavation can only *move* coherence, never mint it.

### 3.4 Re-authoring — the repair act is re-condensing the order

The **skeleton** class (§3.2) is the re-authorable ruin, and the honest core of the
building-as-field-work claim:

> **A young player re-authors a ruin by re-locking its skeleton.** The skeleton is the
> still-holding low-rung structure — the field still holds its `q`-core, it just lacks a
> maintainer. Repair is not *replacing blocks*; it is **re-condensing the skeleton's
> order** — feeding coherence (the hearth's anchor, §1.1, and anti-corruption,
> `energy-harnessing.md` §5.4) to raise the skeleton's `q` back toward the attractor and
> restore its `ε²` suppression. The repair act IS the re-condensation: you are not
> rebuilding a ruined house, you are **re-locking the order the field never quite
> released**, and each wall you re-lock re-concentrates the coherence the next requires.

This is `energy-harnessing.md` §5.4's anti-corruption — *spend coherence to hold ground
against decay* — applied to architecture: re-authoring is the *preventive/restorative*
field act that keeps `ε²` below the dissolution floor for a structure instead of a scar.
And it rides the same budget discipline (§5d): re-locking a skeleton is a *hold* on the
existing order plus a *bounded channeling input* from the hearth — never a net mint.

---

## 4. The house's place in the corpus

A maintained house is not an isolated shelter; it ties the building form into the
corpus's settlement-scale and window-scale systems:

| Tie | The house's role | The mechanism | Cross-ref |
|---|---|---|---|
| **The Qi bath** | **a maintained house is a bath-node; a settlement's houses ARE the bath's structure** — their enclosed rooms hold the `q`-cores whose superadditivity is the regional multiplier. | the room's held `q`-core (§1.1) feeds the bath's radius (§2.2); a house that stops being maintained stops feeding the cluster's coherence | `energy-harnessing.md` §4.4; §1/§2 this doc |
| **The Coherence Board** | **a house's contribution books on the settlement's ledger** — building/holding a house is a field op (condense/anti-corruption at a coherent site, `shared-ledger.md` §1.2), so it lands on the Board's per-member `C(M)` as a contribution; a drained/ruined house drains the book. | the op-stream records every condense/heal the house's construction and maintenance produce; the Board sums them per tide | `shared-ledger.md` §1.2/§2; `fate-of-a-window.md` §2 |
| **The fate of the window** | **a maintained house holds a window's settle/thrive; an abandoned one feeds its decay** — the house's built form is part of the window's coherence economics (its walls hold the bath up, its abandoned edges drain toward the margin). | the bath's `q` (which houses hold or leak) is the fate's primary arc-driver; a settlement whose houses decay drives `C(W) < 0` | `fate-of-a-window.md` §1.1–1.3, §2; `energy-harnessing.md` §4.4 |
| **The Life-Signal** | **a house is a maintained lock; a ruin is a fallen floor** — the vitality classifier reads buildings too, and its noise-floor line applies to architecture. | a maintained house is the **maintained-live** class (steady, held `q`, `ε² ≤` floor, the hearth's bounded pulse); a skeleton is a low-level maintained-adjacent read; a fallen floor is the **ordinary-scar** class; a ghost-halo is **static residue** | `life-signal.md` §3; §3.2 this doc |

The house is the corpus's built-form *union*: it is at once a bath-node, a Board
contribution, a fate's driver, and a Life-Signal subject — all because it is coherence
architecture (§1). The first sentence of this project's thesis — "the two-fluid field is
the substrate; blocks, mobs, and planets are its epiphenomena" (`README.md`) — is, for
the built form, this doc's claim: a house is a held shape of the field, and what the
player builds is a structure that steers it.

---

## 5. Honest gates

### (a) The [design]/engine-real line

| Claim | Status | Support / basis |
|---|---|---|
| **The field channels are real**: `q` (`field_q`, 1 MiB), `ε² = (EY − φ·EI)²`, `∇(g·Φ)` (grad, 3 MiB), `ρ` (1 MiB) — the ≈ 6 MiB publish | **engine-real** | `corpus-reconciliation.md`; `async-field-domain.md` §2.1; `chunk-field-quantization.md` §2 |
| **Deep-rung ordered matter is stored coherence and persists as residue**; a dissolving structure sheds `(1−q)` and leaves the deep q-locked core (`R ≳ q^n`) | **engine-real** (persistence) / **[design]** (the residue model) | `field-archaeology.md` §1.1/§2.1; `energy-harnessing.md` §1.5/§3 |
| **The geometry's steering effects** — that a wall concentrates, a room holds, a corner pins, a doorway channels, an open edge drains, a hearth anchors (§1.1) | **[design]** over engine-real channels, **probe-calibrated** | this doc §1/§5a; the condenser-lens optic is concept 2's established `(base/apex)²` |
| **A settlement as a gradient-stealing structure** (§2); the ruin classes (§3.2); re-authoring as re-condensing (§3.4) | **[design]** — the architecture vocabulary, layered on the real soak-and-residue asymmetry | this doc §2/§3; `field-archaeology.md` §5 flags the residue model |

The line is never blurred: **the channels and the persistence are real; the geometry's
steering is the designed surface, and it is calibrated by probe, not asserted.** The
probe (§5b) is what turns the §1.1 vocabulary from "claims" into "calibrated dials."

### (b) Phases and gates — gated on the Qi bath *and* a Phase-1 hearth slice

The full building-as-coherence-architecture depends on the corpus's established
Phase-1.5 gates:

- The **Qi bath** (`energy-harnessing.md` §4.4) gates the *settlement* form (§2) — the
  regional `q`-multiplier over a cluster of held `q`-cores is a Phase-1.5+ system.
- The **regime constants** (`custom-blocks.md` §7 Q3 / `material-regimes.md` §7 Q3 —
  per-cell `ω₀²`/ξ feeding the PDE) gate the *material* vocabulary the house composes.
- The **residue model** (`field-archaeology.md` §6c — the strata-vs-heal probe) gates the
  *ruin* (§3).

So the **full architecture is MEDIUM-LATE** (§6). But there is a clean **Phase-1 slice**:

> **Phase-1: a single shaped hearth.** One structure that *locally steers coherence* —
> a hearth (§1.1) with a sloped wall, an enclosure's first corner, an open edge, placed
> on a coherence ridge. It needs **nothing beyond the already-published channels**: it
> is a *consumer* (the room's `q`/`ε²` read from the ≈ 6 MiB publish) plus a *bounded
> channeling input* (the hearth's EY-withdraw, `coherence-magic.md` §1.2's budget —
> already the Coherence Board's / a machine's consumer pattern, `shared-ledger.md` §7b).
> It is testable **on the publish**: build the shaped hearth on a Phase-1 living-terrain
> demo and measure whether the room's `q` holds elevated-`ε²`-suppressed vs an equal
> volume of flat terrain — a consumer, family rule (`field-instruments.md` §2.1). The
> hearth is the one element with an *input*; every other element's steering is a pure
> read-and-hold, so the slice proves the whole vocabulary's feasibility without waiting
> on the bath or the regime gates.

The Phase-1 hearth is the proof-of-principle: **a shaped structure that locally steers
coherence, testable on the publish.** It de-risks the entire vocabulary (§1.1) — if a
sloped wall measurably holds the room's `q` above flat terrain, every other element
follows the same measured pattern.

### (c) Determinism

The field is deterministic (one PDE; `field-archaeology.md` §1.2; `life-signal.md` §6d's
hard gate). The house's steering inherits it:

> **Same layout, same field state → same steering.** The building's effect is a
> deterministic function of the layout (its geometry) and the local field channels — no
> hidden randomness, no player-relative variance. A player who re-reads a house, or
> rebuilds the same shape in the same field state, gets the same measured concentration.
> This is what makes the vocabulary *learnable* and the site map a *blueprint* rather
> than a guess.

### (d) The no-free-energy cap — a house holds and steers, never mints

The corpus's single hard rule (`energy-harnessing.md` §6: **no conversion yields more
than it sinks**, `output ≤ φ⁻¹·input`, coded as amplitude caps on the write-back lane)
applies to architecture unchanged — and this doc states it as a hard design bound:

> **A house cannot mint coherence. It *holds* and *steers* what the field provides —
> it never generates `q`.** A house that "generates" coherence is a lie the cap forbids.
> The highest a house's `q`-core can go is what the *field* already provides at that site
> (the coherent region it sits in, `chunk-field-quantization.md` §2.2) plus a *bounded
> channeling input* from the hearth (`coherence-magic.md` §1.2's budget). The room's held
> `q`-core (§1.1) is the field's organization *held up*, not produced; the settlement's
> bath (§2.2) is the region's coherence *re-routed*, not conjured. Any building mechanic
> that reads as "this structure made `q`" is a physics lie — the wall concentrates what
> the field already provides, and the cap encodes it in the write-back amplitude exactly
> as the machine layer's cap does.

This is the load-bearing stated once: **a house does not generate coherence; a house
steers it.** The bath at the center, the productive edges, the deliberate drains — all
borrow from the region the field already organized.

### (e) Accessibility — never a hidden-only effect

The built form's steering must be readable from the existing field-reading surfaces, per
`field-music.md` §6 (an enhancement, never the only channel) and the instrument family
rule (`field-instruments.md` §2.1):

- The **reader / Sense** (`coherence-magic.md` §2) renders a house's `q`-core and the
  ruins' ghost-halo + q-locked core — building steering is *visible in the field read*.
- The **Weatherglass / Still Room** (`field-instruments.md` §1.2/§2.2) shows the local
  `q`, the `ε²` climb, the waste tint, the lean — a player sees a house *holding* (steady
  `q`, flat-low `ε²`) vs a ruin *draining* (climbing `ε²`, grey).
- The **Life-Signal** (`life-signal.md` §4) reads buildings as maintained-lock vs
  static-residue vs fallen-floor — a house *breathes*; a ruin does not.

A player who never uses a "coherence architecture" overlay loses nothing — the steering
is the *same channels the reader/glass already show*, read at the building's scale. The
[design] §1.1 vocabulary is an *idiom over real channels*, never a hidden mechanic.

---

## 6. Feasibility verdict

**MEDIUM-LATE as the full architecture, with a clean Phase-1 hearth slice.**

- **The full architecture (the settlement as gradient-stealing structure, §2; the
  ruin classes and re-authoring, §3)** is **MEDIUM-LATE**: it gates on the Qi bath
  (`energy-harnessing.md` §4.4, Phase-1.5+), the per-cell regime constants (`custom-blocks.md`
  §7 Q3, Phase-1.5), and the residue model's strata-vs-heal probe (`field-archaeology.md`
  §6c) — the same gates every material/archaeology system shares. Its honesty is that it
  adds **no new physics, no new channel**: a house is a field consumer (reads the ≈ 6
  MiB publish) plus a bounded write-back (the hearth, through the Q4
  lane `coherence-magic.md` §5.1), on the cost profile of a machine (`energy-harnessing.md`
  §2) and the Board's aggregation slice (`shared-ledger.md` §7b).
- **The Phase-1 slice — a single shaped hearth** — is the architecturally real,
  testable-on-the-publish proof. It needs only the published channels + the player's
  coherence budget (`coherence-magic.md` §1.2), measures whether a sloped wall holds the
  room's `q` above flat terrain, and thereby de-risks the entire vocabulary (§1.1) and
  the build-order honesty (§2.1) without waiting on the bath or the regime gates.

**Binding risks, in order:** **(a)** the geometry-steering calibration probe (§5b — does
a sloped wall *measurably* hold `q` over flat terrain in the Phase-1 demo? The whole
vocabulary rests on that measurement, exactly as the strata claim rests on its
strata-vs-heal probe); **(b)** the no-free-energy cap's enforcement in the write-back
amplitude (§5d — a house must never read as a `q` mint; the same mechanical guard
`energy-harnessing.md` §6 demands); **(c)** the ruins' residue-fraction tuning
(`field-archaeology.md` §6b — `R ≳ q^n` and `q_dissolve` determine whether ruins
accumulate toward findable archaeology or erode away); **(d)** the settlement's drains
never reading as "the house is failing" (§2 — the deliberate drains must be visibly
*deliberate*, not a defect flagged by the fate's decay read as a margin drain). None
contradicts the async, dual-world, or regime-collapse architecture — a house is a
consumer of the field, and its built form is the corpus's own thesis made structure.

> **The honest statement that makes this doc load-bearing: the corpus designs a
> building game but never says what a building IS to the field. The answer is that a
> building is coherence architecture — geometry as a regime, the shape-is-the-tuner
> principle at the scale of a house. What the player builds is a structure that steers
> the field; what a settlement builds is a gradient-stealing layout that holds its core
> and drains its edges; what a ruin is, unmaintained, is the readable ghost-halo of a
> structure the field once held. And the honesty that keeps it a design and not a
> physics lie is the cap: a house does not generate coherence — it holds and steers what
> the field provides, the way the corpus's single law is one field and every built form
> one of its composed faces.**

---

## Open questions

1. **The geometry-steering calibration.** The §1.1 vocabulary (wall concentrates, room
   holds, corner pins, doorway channels, open edge drains) is [design]-over-real-channels
   *assuming the concentration reads measurably*. Is a sloped wall's `(base/apex)²`
   condenser effect strong enough, at house scale in the Phase-1 box (192³ m), to hold a
   room's `q` above flat terrain *without* the bath's regional multiplier? The Phase-1
   hearth slice (§5b) is the pre-registered probe that answers it — a negative answer
   (walls steer too weakly at house scale) would push the mechanic to pure read-only
   "go build on the coherent sites" without per-element steering dials. **[probe]**
2. **Ruin persistence vs decay.** Inherits `field-archaeology.md` §6b/§7 Q1: does a
   static, undammed ruin's q-locked core hold forever (attractor-consistent) or erode?
   The findability of the ghost-halo, and whether the skeleton (§3.2) stays re-authorable
   or ages into a fallen floor, both depend on it. **[design]/[probe]**, Phase-1.5
   (off the residue-persistence calibration).
3. **The delimiter between deliberate drain and decay.** A settlement's deliberate open
   edge (§2) must read as *designed*, not as a margin drain the fate flags as decay
   (`fate-of-a-window.md` §2 — the margin's creep is the decay arc's signature). Is the
   drained edge distinguishable from an over-drained margin on the read, or does the
   layout's honesty require a label (a "steered drain" vs a "failed bath") the channels
   alone cannot give? **[design]** — must not cross the classifier line
   (`field-archaeology.md` §7 open-Q3, `life-signal.md` §3).
4. **Re-authoring's budget bound.** Re-locking a skeleton (§3.4) spends coherence (the
   hearth's bounded input + anti-corruption, `energy-harnessing.md` §5.4) to restore the
   order the field still partially holds. Is a restored house's held `q`-core *permanently*
   below what a fresh build on the same site could reach (the structure's original
   organization is partially spent), which would make re-authoring an honest *humble* act
   rather than a strictly-better rebuild? **[design]** — the charge/scan asymmetry of
   §3 (`energy-harnessing.md` §3) is the candidate frame.
5. **Excavate-and-rebuild's firing.** Conservation is the designed default (§3.3). Is
   excavating a ruin's core ever *necessary* (not just cheaper for stored fuel) — i.e.,
   is the deep-rung residue of a built form a regime/fuel class a player cannot get any
   other way (`field-archaeology.md` §4.1's found-only framing, applied to a ruin), or is
   it always a strategic choice? If it is ever *the only* source of a material, the
   excavation path stops being a real rival and the conservation default breaks. Needs
   the found-economy's realizability-time boundary (`custom-blocks.md` §7 Q2,
   `field-archaeology.md` §7 Q4). **[design]**

---

## Cross-references

- [`coherence-technologies.md`](./coherence-technologies.md) — **concept 2** the
  condenser / shape-is-the-tuner (`(base/apex)²`, the wall/lens); **concept 4** the Qi
  bath; **concept 5** cascade staging / build-on-coherent-sites (§2.1 this doc).
- [`custom-blocks.md`](./custom-blocks.md) — materials as authored regimes — the block
  tuple `(ξ, ω₀², θ_c, n)` the house composes (§1); the found/invented economy (§3.3
  this doc Q5); the Phase-1.5 regime-constant gate (§5b).
- [`energy-harnessing.md`](./energy-harnessing.md) — **§4.4** the Qi bath (the house as
  bath-node, §2/§4); **§4.1** conduits (the wall/doorway channel idiom, §1.1); **§5.4**
  anti-corruption (re-authoring as re-condensing, §3.4); **§6** the no-free-energy cap
  (the house never mints, §5d); **§2** the `(1−q)` waste law (the ruin's death-glow); **§3**
  storage / the charge-scar asymmetry.
- [`field-archaeology.md`](./field-archaeology.md) — **§2.1** the residue model (`R ≳
  q^n`; the q-locked core + ghost halo — the ruin); **§5** conservation vs excavation
  (applied to the house, §3.3); **§7 open-Q3** the live-vs-residue classifier (the
  Life-Signal tie, §4); the residue-logic gates (§5b/§6).
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — **§5** the
  meshless-site activity map — build where the field is organized (the settlement's
  blueprint, §2.1); the ≈ 6 MiB publish and the sampler budget (§1/§5 of this doc).
- [`field-instruments.md`](./field-instruments.md) — **§2.2** the Still Room (the
  room-scale Weatherglass the house's room scales from); **§2.1** the family rule (the
  §5b consumer/hearth slice is a pure consumer with a presentation idiom).
- [`life-signal.md`](./life-signal.md) — **§3** the maintenance axis — the four classes
  (a house = maintained lock; a ruin's fallen floor = ordinary scar; the ghost-halo =
  static residue); the classifier reads buildings too (§4).
- [`fate-of-a-window.md`](./fate-of-a-window.md) — the four arcs; the bath as arc-driver
  (a maintained house holds settle/thrive; an abandoned one feeds decay, §4); the fate's
  attribution (§5d Q3).
- [`shared-ledger.md`](./shared-ledger.md) — **§2** the Coherence Board, `C(M)` per
  member — a house's construction/maintenance contribution books there (§4); the
  Phase-1-able aggregation slice (§7b) the hearth slice's consumer pattern shares.
- [`the-feral-instrument.md`](./the-feral-instrument.md) — **the self-chairing house.**
  §1/§2.2 there reads the house that started steering itself as a feral (a): §1 this
  doc's coherence architecture held past its author's intent; §3.2's skeleton — the
  still-holding low-rung structure — is the feral past re-authorability (§2.2 there).
  Reverse pointer: the feral is the house's coherence architecture that kept its order
  long enough to act on it.
- [`the-scar-lifecycle.md`](./the-scar-lifecycle.md) — **the build-on-the-ruin.** §2.3
  there reads §3.2 this doc's skeleton (the still-holding, re-authorable structure) and
  §3.4's re-authoring as the scar-kept place's foundation — a deliberate wound's residue
  adopted as foundation, built *on*, never mined *from* (§2.3/§5d there). Reverse pointer:
  the scar-kept place is the ruin's foundation made deliberate.
- [`the-commensal.md`](./the-commensal.md) — **the bath-edge's companion.** §2.3 there
  reads §2.2 this doc's managed gradient as its habitat — the commensal lives beside the
  kept, grazing the bath-fringe's `(1−q)` surplus and holding a small patch's order; §5d's
  no-free-energy cap is held (§5d there — a commensal holds a patch, never mints it).
  Reverse pointer: the commensal shows the settlement's managed gradient keeping wild company.
- [`the-window-pulse.md`](./the-window-pulse.md) — **the settlement's health read at the
  bath.** §2.1 there reads §2.2 this doc's Qi bath as the pulse's level — the bath's
  `(1−q)` trend is the settlement's maintenance read at scale; §1 this doc's coherence
  architecture is the body the pulse reads; §5b's bath gates are the pulse's MEDIUM gate.
  Reverse pointer: the pulse reads the held bath as the settlement's life's level.
- [`the-lock.md`](./the-lock.md) — **the held core locked.** §2.2 there reads §1.1 this
  doc's held core and §3.2 the skeleton — a locked claim is a house's held core locked
  against dissolution; §5b the geometry-steering probe (the lock's hold gate); §3.4
  re-authoring's re-condensation. Reverse pointer: the lock makes a house's hold
  irreversible.
- [`the-granary.md`](./the-granary.md) — **the room's hold.** §2 there reads §1/§2.2
  this doc's building vocabulary (the granary as a room's hold), §5d holds and steers
  never mints, §5b the geometry-steering probe (the granary's hold gate). Reverse
  pointer: the granary is a house's room given to store.
- [`the-toll.md`](./the-toll.md) — **the held border.** §1 there reads the coherence
  architecture, §2.2 the Qi bath ("brittle if it goes down"), §3 the ruin (an
  unmaintained hold collapses — the un-held door's honest loss), §5d holds never mints.
  Reverse pointer: the toll is the held structure's honest entry charge.
- [`the-causeway.md`](./the-causeway.md) — **the deck's held form.** §1 there reads the
  built form (a structure that steers the field — the deck's phase-kept hold); §1.1
  the vocabulary (the room the deck un-wraps); §2 the managed gradient; §3 the ruin
  (an unmaintained hold collapses — the swallow); §3.4 re-authoring; §5d the cap.
  Reverse pointer: the causeway is a house-that-steers form, the deck.
- [`the-beacon.md`](./the-beacon.md) — **the standing hold.** §1/§1.1 there reads the
  coherence architecture (the Beacon's tower is the room un-wrapped into a standing
  hold); §3 the ruin; §5b the hearth slice; §5d holds-and-steers, never mints.
  Reverse pointer: the beacon is the room un-wrapped into a standing mark.
- [`the-wage.md`](./the-wage.md) — **the second work paid.** §1/§2.2 there reads the
  house and the Qi bath; §3 the ruin; §5d a house holds never mints. Reverse pointer:
  the wage can pay to keep a house-that-steers held.
- [`the-inn.md`](./the-inn.md) — **the guest-door’s house** §1.1 the room that holds a `q`-core; §2.2 the Qi bath; §3 the ruin (an unmaintained inn collapses); §5b the probe; §5d a house holds never mints. Reverse pointer: the inn is the house’s room, held as a guest-door.
- [`the-touch.md`](./the-touch.md) — **the held surface.** §1/§1.1 the built form (the touch reads a held structure’s surface at contact). Reverse pointer: the touch reads the house-that-steers’s held wall.
- [`the-canal.md`](./the-canal.md) — **the held route.** §1/§6 the held structure (the canal’s dug lane is a held structure that steers water). Reverse pointer: the canal is a house-that-steers form holding a water-lane.
- [`the-cistern.md`](./the-cistern.md) — **the held vessel.** §1/§6 the held structure (the cistern is a built vessel that holds). Reverse pointer: the cistern is a held vessel that steers nothing — it holds.
- [`the-balefire.md`](./the-balefire.md) — **the held warning structure.** §1/§3 the held structure (a held balefire dies with the structure). Reverse pointer: the balefire is a held structure that steers a warning.
- [`the-shrine.md`](./the-shrine.md) — **the house’s silence.** the built order the house steers vs the shrine’s answered-nothing. Reverse pointer: unlike the house, the shrine answers nothing — a place that holds and does not steer.
- [`the-crane.md`](./the-crane.md) — **the builder’s lift.** §1 a building is coherence architecture; §2.2 the managed gradient; §5b the building’s phase. Reverse pointer: the crane is the builder’s lift — how the settlement raises the stone its coherence-architecture stands on.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers
  (≈ 6 MiB publish, 64³ grid, 192³ box, `q ≈ 0.947` attractor, `φ⁻² ≈ 0.382`, `ξ = φ⁶ ≈
  17.94`, the ≈ 1–6 ms/tick sample budget, 8,192 meshless sites); cited, not re-derived.
- [`README.md`](../README.md) — the thesis ("blocks, mobs, and planets are its
  epiphenomena") the house makes literal.
- [`the-commons-tithe.md`](./the-commons-tithe.md) — **the first funded object.** §2
  there reads §1 this doc's coherence architecture and §2.2 the Qi bath ("brittle if it
  goes down") — the tithe funds the maintained high-`q` core; §3 the ruin; §5d a house
  holds never mints; §5b the bath gates. Reverse pointer: the tithe keeps the house's
  bath held.
- [`the-season-change.md`](./the-season-change.md) — **the bath before it thins.** §3.2
  there reads §2.2 this doc's managed gradient and §3.4 re-authoring — the
  settlement's action at the turn: husband the bath before it thins; §5d the cap.
  Reverse pointer: the season-change is when the bath is husbanded.
- [`the-cart.md`](./the-cart.md) — **the structure on the move.** §1/§3 there read §1/
  §2.2 this doc's built-form vocabulary — a cart is a held structure, the wheel-
  carriage a room's hold on the move; §5d never mints (the cart's cap). Reverse
  pointer: the cart is a house's room on wheels.
