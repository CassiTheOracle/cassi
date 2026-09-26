# World Seams and the Long Dark: Between the Anchored Field Windows

**Question under design:** what lies **between** the finite field windows, why the
[`ksp-kernel.md`](./ksp-kernel.md) ships exist, and the voyage that becomes the
game's horizon. The KSP kernel designs *how* a vehicle moves through the field
(thrust, orbits, docking, the sync contract); this document designs **what a ship
is *for* beyond orbiting its own sky** — leaving your window, sailing the long
dark between windows, and arriving at (or founding) another living world.

This is the **destination half** of the KSP universe. The kernel supplies the
mechanics; here is where those mechanics point. The doc deliberately does **not**
redesign any mechanical system — it reuses the kernel's ships, the atmosphere
doc's beacons, the energy doc's fuel, the async seam's re-home — and answers only
their *purpose* and *scale*.

The physics the whole design rides on is the theory's **local-field mixture
treatment**: the law lives in the local anchored fields, and the global observable
is the *measured mixture* of them (`CassiTheory/cosmology/cosmology-from-phi.md`
— the σ8 reading is "the window-integrated per-cell mixture," the window's content
is a history not an endpoint, "mixture = mean-field"). The dark between windows is
that mixture's **empty measure** — the vast place where there is no window to
integrate. The KSP kernel is the vehicle that crosses it.

**Grounded in** (read-only): the corpus docs named below, the engine's synchronous
seam and movable home-window (`CassiCosmos/scripts/cassi_physics_engine.gd`
`_window_center` / `bh[0].yzw`, `submit_steps(block=true)`, `JOB_STEP_CAP = 64`,
`TREE_JOB_STEP_CAP = 8`), and the local-field-mixture treatment as it appears in
`CassiTheory/cosmology/` and `CassiTheory/speculations/`'s long-voyage / propulsion
concepts. Every number is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived), engine-verbatim, or flagged
**[assumption]** / **[design]** where it extends engine terms to a world-scale
gameplay the engine does not (yet) drive.

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| Window = ? | The **anchored 192³ m / 64³-cell / 12³-chunk box** (`chunk-field-quantization.md` §1.2); the field "where it matters"; the local-field treatment's concrete instance. The law lives in it; the interior is the mixture it contributes. |
| Window's edge = ? | The envelope falls off, the published grid fades, the field-poor interstitial begins. Beyond the edge: the same window-relative tiling, other windows, and the dark. |
| The dark = ? | A **field-poor interstitial** (NOT vacuum): ρ below the gas floor everywhere, q low but nonzero — the mixture's empty measure. Ships can steer but cannot aerate; the (1−q) glow is the brightest thing in it. |
| Navigation | A distant window's sky reads as a star — its pole discharges and envelope-top band are the "stars" of this universe (`atmosphere-orbits-auroras.md` §3). Beacon-reading is the only fix; there is no map. |
| The voyage | A **coherence-budget problem** (`energy-harnessing.md`): deep-rung fuel blends (`ksp-kernel.md` §2.3), the (1−q) glow as the range gauge, the constraint economy as the honest length-limiter. |
| Destination / origin | Another player's anchored window, or a **window seeded by the player** — the field condenses a fresh anchor; terrain precipitates from an empty box; the biosphere emerges (ecology in miniature). |
| Seam at world scale | **Anchor-to-window** (extends `ksp-kernel.md`'s anchor-to-body): a distant window becomes the re-home target. Overlap/merge is a seam-of-competition policy the async seam (Q1) must own. |
| Player-facing arc | Build the ship → stock the coherence → sail the dark → found the window → choose: return (trophies) or grow the new world. |
| Feasibility | **Phase 2+**, downstream of the KSP kernel. The dark's representation is **[design]** beyond the engine's window seam. |

---

## 1. What a window is, precisely

### 1.1 The anchored box — the local-field treatment made concrete

A **window** is the anchored field domain: the chunk-aligned
`(1,1,1)·192³ m / 12³-chunk` box with `64³ = 3 m` whole cells (`box_aspect=(1,1,1)`,
`cluster_radius=64` → full 192³ m; `chunk-field-quantization.md` §1.2, the resolution
of `async-field-domain.md` §7 Q1). Canonical:

| Quantity | Value | Source |
|---|---|---|
| Box | 192³ m full extent | chunk §1.2 (resolves async Q1) |
| Cells | 64³ = 262,144 cells | corpus; engine `grid_N` |
| Cell | 3 m per axis | chunk §1.2 |
| Chunks | 12×12×12 = 1,728 | chunk §1.2 |
| Blocks | 1 m = 1/3 trilinear sub-cell sample | chunk §1.3 |
| Field-only publish | ≈ 6 MiB (q 1 + pot 1 + ∇(g·Φ) vec3 3 + ρ 1) | corpus; chunk §2 |
| dt | 0.05 (one field step per Minecraft tick) | corpus; chunk §1.2 |
| Home-window center | `_window_center` / `bh[0].yzw`, shipped per job | async §7 Q1; engine |
| Per-tick sample | ≈ 1–6 ms server; domain ≈ 0.5–1.5 ms per step | corpus; chunk §4 |

The window is the **local-field treatment's** concrete instance: it is the box the
field "where it matters" fills (`async-field-domain.md` §1.1: the grid advects with
the world anchor rather than spanning the infinite surface). The physics is
window-relative — `world → grid` maps through `_window_center` in the nbody sampler
(`cassi_nbody_gravity.glsl:278-284`) — so the window is **the unit the law runs in**,
and everything the player experiences as "the world" is what this box's field
quantizes onto the gameplay grid (`chunk-field-quantization.md` §2).

### 1.2 The law lives in the windows; the global is their mixture

This is the load-bearing physics of the whole seam, stated once and reused
throughout. The theory's **local-field-mixture treatment** — the σ8 work in
`CassiTheory/cosmology/` — is exactly this:

> The observed global is the **window-integrated per-cell mixture** of the local
> fields. The window's content is a *history* (its q-evolution over the measured
> window), not a single endpoint; the mixture is the mean-field over cells.
> (`CassiTheory/cosmology/cosmology-from-phi.md`, the σ8 reading; the same
> structure underlies the w₀/w_a and H₀ local-field work and the
> `desi-lattice-averaging.md` "distance channel" washout.)

Translate to CassiCraft, and a **window** is one such cell: a local anchored field
whose interior the game renders and steers, and the **world** — the thing the player
crosses between windows — is the measured mixture of what each window keeps organized.
The law does **not** need to run everywhere; it runs where it matters, in the
windows, and everything outside a window is the mixture's empty remainder. **[design]**
This is the honest mapping: the engine runs one (or a few) anchored boxes; the game
*declares* that the space between them is the mixture's empty measure, so no engine
support for "the whole universe" is required — only for *another window*.

### 1.3 A window's edge — the envelope, the fade, the field-poor interstitial

What the edge means, in the field's own terms (all engine-real channels):

| Depth from center | ρ / q / ε² state | What it is |
|---|---|---|
| **Interior** | ρ ≥ τ_c condenses, q high, ε² low | the living terrain + envelope you play in |
| **Envelope near edge** | ρ falling below gas floor, q intermediate | the sky's boundary layer (`atmosphere-orbits-auroras.md` §1) — fog-as-ρ, wind lines |
| **The edge (box face)** | the published grid's boundary | where the finite box's field *ends* |
| **Field-poor interstitial** | ρ below gas floor everywhere, q low (non-zero), ε² high | the dark — the mixture's empty remainder |

The edge is **not** a solid wall: the box is a periodic torus (`chunk-field-quantization.md`
§1.1) that re-homes as the anchor moves, so within a window the seam is far outside
view. But at *world scale* — when the question is "what is beyond this window" — the
edge is where the field's envelope falls off (the height-fog thins to nothing), where
the published grid the window owns *fades* because there is nothing to quantize, and
where the **field-poor interstitial** begins. **[design]** The edge's *rendered*
fade (fog → darkness) is a presentation of the published ρ dropping below the gas
floor, exactly as the sky ceiling is (`atmosphere-orbits-auroras.md` §1.4); nothing
is "cut off" — the field simply has no density to show past it.

**What is/isn't rendered beyond the edge:**

| Beyond the edge | Rendered? | Why |
|---|---|---|
| The window's own far-away box face / wrapped twin | No | a torus seam is a coordinate artifact, not a place (`chunk` §1.1); the re-home hides it |
| **Other windows** (distant anchored fields) | Yes, as **stars** — their pole discharges + envelope-top bands (`atmosphere-orbits-auroras.md` §3.3) | a distant window's own sky structure *is* visible as a point of light; this is the navigation beacon (see §2) |
| **The field-poor interstitial** (the dark) | Yes, as **darkness + the ship's own (1−q) glow** | ρ is below the fog floor, so nothing renders; only your vessel's waste glow and the distant window-stars pierce it |

So a window is **not an island with walls** — it is a place the law fills, and the
universe beyond it is the *same* field, so thin it reads as darkness. A distant
window is a *star* because it is the same law, dense somewhere else, and the (1−q)
law makes its drains bright at range (`atmosphere-orbits-auroras.md` §3).

---

## 2. The long dark between windows

### 2.1 What IS the dark, mechanically (gate (a), chosen)

The design **chooses the field-poor interstitial**, not vacuum, and the choice is
forced by the physics. Two candidates:

| Candidate | Can ships steer? | Why | Verdict |
|---|---|---|---|
| **True vacuum (no field)** | **No** — the river law `a = −G_N·(π/ρ)·∇(g·Φ)` has nothing to push against; ρ → 0 makes the coupling undefined; ships are dead | "no field: ships cannot steer" (the gate's warning) | **rejected** |
| **Field-poor interstitial** | **Yes, weakly** — ρ is below the gas floor (no aeration, no atmosphere) but *nonzero*; the river law still couples to a thin medium; q is low (the (1−q) waste is high, so you *glow*), and deep-rung fuel can keep the field around the ship organized | the law still runs, just thin; the (1−q) glow is the design's signature | **adopted** |

**The honest mechanism.** In the interstitial, ρ is below the gas floor everywhere
(`material-regimes.md` §2: gas needs ρ above a lower floor) but not zero — the field
is at its noise level (`q ~ 1e-3…1e-1`, `energy-harnessing.md` §7 Q1), thin enough
that nothing *aereates* (no standing envelope, no terrain, no weather — the RealSim
envelope terms vanish as in vacuum `atmosphere-orbits-auroras.md` §1.4), but present
enough that a **condensation drive pointed at the sky** (`energy-harnessing.md` §5.2)
still has a medium to inject EY into and push against. A ship in the dark is exactly
a **coherence-injection device maintaining its own local field**: it must *carry the
field* it sails through — a per-vehicle Qi-bath (`energy-harnessing.md` §4.4,
`coherence-technologies.md` concept 4) that keeps q up in the thin medium so the
river law can steer it.

**The (1−q) glow is the ship's signature — the brightest thing in the dark.** Every
working field system bleeds `E_waste = (1−q)·E_throughput` as visible glow
(`energy-harnessing.md` §2; `qi-bubble-propulsion.md` §2.5). In the field-poor dark,
it is not physics (there is nothing outside to see) but *signature*: **a ship in the
dark is the brightest thing there** because it is the only working field system for
leagues. A wasteful engine (low q, mis-set throttle, a near-blast discharge —
`ksp-kernel.md` §2.3) glows *brightest*, exactly as on the ground. **[design]** The
glow is the engine-real (1−q) law; the "brightest thing in the dark" framing is the
presentation that makes the economy legible — you gauge your own waste by how
brightly you burn.

### 2.2 Navigation — a distant window's sky is the star field

The atmosphere doc already establishes the aurora as a **navigation beacon**:
a coherence discharge at a body's field-line concentrations, a bright stationary
polar discharge and a band at the envelope top are the readable field structure a
pilot uses to orient (`atmosphere-orbits-auroras.md` §3.3, `ksp-kernel.md` §5.2).
This doc scales that to the world level:

> **A distant window reads as a star.** From the dark, the only thing visible is
> another window's *sky*: its pole discharges (the bright points) and its
> envelope-top band (the tint) — the exact same field structure the atmosphere doc
> renders, seen from outside at range. The "stars" of this universe are **other
> windows' boundary-layer discharges**, and the "constellation" is the local-field
> mixture's sparse measure of organized places.

**Reading a window-star is the navigation instrument.** The coherence reader
(`coherence-magic.md` §2 — the Phase-1 deliverable) pointed at a distant window-star
reveals it is not a point but a *field*: its polar discharges resolve into the
known "bright stationary + band" structure (`atmosphere-orbits-auroras.md` §3.2).
The reader cannot *tell you where* the star is in absolute space — the window is
window-relative, and the tiling has no global map — but it tells you:

- **Is it a window at all** (organized — polar discharge + band) or a false gleam
  (a drain's transient glow, `atmosphere-orbits-auroras.md` §3.2 site 3)?
- **Is it healthy or wounded** (calm coherent bands vs restless bright discharges —
  `atmosphere-orbits-auroras.md` §3.3)?
- **Is it a body or a world** (a small body's envelope vs a window's full
  boundary-layer band)?

**[design] — There is no map; there is only the reading.** Because windows are
window-relative and the interstitial has no global coordinate system, navigation is
**beacon-reading, not cartography**: you hold course on the star that resolves
right, drift on it, and re-read as it grows. This is the honest, Cassi-native
navigation: the phase-matching instinct of the theory (read the target's phase to
couple, `coherence-technologies.md` concept 3) applied to *place* — you sail toward a
field you can read, not a coordinate you computed.

### 2.3 The voyage is a coherence-budget problem — fuel, storage, range, and the honest limiter

The voyage's honest shape is the **constraint economy** (`energy-harnessing.md` §6:
energy is a constraint, not a currency; no conversion yields more than it sinks).
Concretely, a long voyage is a **coherence-withdrawal problem**:

| Voyage demand | The field it spends | Cross-ref |
|---|---|---|
| **Thrust** | stored coherence from deep-rung matter — δv budget is a coherence budget | `ksp-kernel.md` §3.2; `energy-harnessing.md` §5.2 |
| **Fuel blends** | deep-rung fuel is high-δv but high-blast-risk; shallow-rung releases controllably — the blend is the safety | `ksp-kernel.md` §2.3; `material-regimes.md` §5 |
| **Carried field (Qi bath)** | a small per-vehicle high-q core to keep q up in the thin medium so the river law steers | `energy-harnessing.md` §4.4 (a "bath" is a draw); `coherence-technologies.md` concept 4 |
| **Range gauge** | the (1−q) glow — a wasteful engine burns the reserve faster and glows brighter | `energy-harnessing.md` §2; §1.5 (lighter = more wasted) |
| **Storage** | the ship *is* a capacitor at its rung — a moving coherence store | `ksp-kernel.md` §1.2; `ecology` §2.2 (a ship is a bigger moving coherence store) |

**The constraint economy is the honest length-limiter (gate (d)).** There is **no
infinite space**: a voyage's reach is bounded by (a) the coherence you can carry
(the capacitor volume + rung), (b) the efficiency you navigate at (the (1−q) glow
is the live drain you see), and (c) the no-free-energy cap (`energy-harnessing.md`
§6: **no conversion yields more than it sinks**, structured as write-back amplitude
caps). You **cannot** sail indefinitely; a ship that overdraws its thrust burns to
blast (`ksp-kernel.md` §2.3), and a ship that exceeds its stored coherence runs out
the same way a car runs out of gas — except the failure is a *discharge* or a
stranded, dark hull, not a walk. **The constraint is a feature**: it makes a voyage
a *decision* (what to carry, how far to commit, whether the destination is worth the
return) rather than an endless treadmill. The long dark is the game's *horizon* — a
fixed, finite, expensive thing — not a loading screen.

### 2.4 Time and feel — long, quiet, risky

The voyage is the game's **horizon, not a loading screen**, and the feel flows
directly from the mechanics:

- **Long.** The interstitial is field-poor, so the domain cadence there is slow
  (the window is already window-relative; the ship's own Qi bath is a small
  bounded locality, `async-field-domain.md` §4 — free-flight async, `submit_steps(block=false)`).
  A crossing is measured in *coherence spent* and *beacon-drift* — hours of quiet
  holding course, not seconds of fast-travel.
- **Quiet.** In a place with nothing to render, the sound is the hull's (1−q)efficiency
  hum (low = efficient, rising = wasteful), the reader's field tones, and the
  beacon's distant signal. There is no ambient life because there is no field to
  be alive (the ecology precipitates only where q is in a coherent band and ε² low —
  `chunk-field-quantization.md` §2.2; there is none here). The quiet is the honest
  emptiness of the mixture's empty measure.
- **Risky.** The two real dangers are the **coherence budget** (run out and die dark)
  and the **thrust-vs-blast overdraw** (`ksp-kernel.md` §2.3) — forcing more thrust
  than the thin medium can re-organize, or igniting deep-rung fuel without the
  throttle discipline, tips the injection into a full-cascade discharge. There are
  no hosts in the dark; the medium itself is the only enemy, and it is indifferent.

> **The long dark is the game's horizon.** It is what the KSP kernel's ships are
> FOR: not orbiting a sky forever, but crossing the empty measure to a place the
> law keeps organized — or to found one.

---

## 3. Windows as destinations and origins

### 3.1 How another window comes to exist

Two sources, both grounded in the anchors the corpus already names:

| Origin | What it is | World-scale role |
|---|---|---|
| **Another player's anchored world** | a second live window running its own field domain | a *place to go* — destination by encounter |
| **A window seeded by the player** | the field condenses a **fresh anchor** at a point you plant | a *place to make* — destination by founding |

The design treats both as the **same kind of object**: a window is an anchored field
domain, wherever its anchor came from. There is no "server fabric" or "dimension"
distinction — there are windows, and the dark between them.

**The inward fold (reverse pointer, third origin):** both origins above grow a window
*outward* — into the dark (`§2.1`), or from a fresh seeded anchor. The pocket cosmos
names the third: a window **grown inward** — a deep-rung, high-`q` condensation inside
already-condensed matter, entered as the anchor of a smaller nested field domain
([`pocket-cosmos.md`](./pocket-cosmos.md) §1.2). This seam's outward origins and that
doc's inward fold are the two ends of one recursion; each now cites the other.

### 3.2 The founding act — a voyage's end is a new living world

The synthesis the design commits to, composing three corpus systems:

> A voyage's end is **condensing a fresh anchor**: you plant a coherence seed in the
> field-poor dark, the local field organizes around it (`volumetric-terrain.md`:
> terrain *condenses and heals*; `coherence-accumulates` of `chunk-field-quantization.md`
> §2.2 ore precipitation is the same act), the anchored box takes root, and — because
> a window is the local-field treatment's instance — **a new living world starts
> with whatever that fresh field condenses.**

The **founding act**, concretely:

| Step | The field does | Cross-ref |
|---|---|---|
| **Plant the seed** | the player asserts a **boundary condition** — a realizable coherence configuration — via the same Q4 channeling/authoring surface (`coherence-magic.md` §5.1, `custom-blocks.md` §2) | custom-blocks: "authoring a boundary condition the law then fulfills" |
| **Condense the anchor** | the local field organizes around the seed; ρ rises past τ_c, q accumulates (the ore/condensation scanner, `cassi_condensation` / `cassi_particle_merge.glsl`) | merge lineage: dust → object → body |
| **Terrain precipitates** | iso-surfaces quantize from the growing field — a 192³ window's worth of living terrain **condenses from an empty box** | `volumetric-terrain.md`; `chunk-field-quantization.md` §2 (ρ ≥ τ_c → solid) |
| **The biosphere emerges** | Phase-3 ecology **in miniature**: once the fresh field holds q in a coherent band at low ε², the recognition rule (`field-emergent-ecology.md` §6b) starts precipitating organisms — the field grows life before you plant any | ecology §2, §4 |

So the synthesis the task names is real: **the first thing you plant is authored
matter** (the seeded anchor, a custom block/regime in the `custom-blocks.md` sense),
**the first organisms precipitate from the new field** (ecology's recognition rule
on the fresh anchor's q-band), and the whole thing is **Phase-3 ecology in
miniature** — a new window is a new field, and a new field grows its own world.

### 3.3 What a fresh window starts with

Anchored to the canonical numbers and the corpus's honest staging:

| Aspect | Fresh window | Why |
|---|---|---|
| The local field | grows **from the anchor** — the seed raises local ρ/q; the box fills as the field organizes | `volumetric-terrain.md` condense-and-heal; `chunk-field-quantization.md` §2 |
| Terrain | **precipitates from an empty box** — no pre-generated worldgen; the field's ρ thresholds cut the iso-surfaces | `chunk-field-quantization.md` §2.2 (ρ ≥ τ_c → solid) |
| Biosphere | **emerges** once q holds a coherent band at low ε² (the ecology spawn rule) | `chunk-field-quantization.md` §2.2; `field-emergent-ecology.md` §2/§4 |
| The player's first act | **author** (a seeded regime / custom block) rather than *place from a menu* | `custom-blocks.md` §2; `coherence-magic.md` §5.1 |

The fresh window does **not** start as a full 192³ box of finished terrain — it
starts as a **bounded, growing anchor** that accumulates density and coherence, and
the box fills (and the world quantizes) as the field organizes. This is honest about
the engine: a founding is a **condensation event**, and the world is whatever that
condensation precipitates — the field's epiphenomenon, not a spawned save.

---

## 4. The seam policy at world scale

### 4.1 The two-anchor fight, resolved: anchor-to-window

`ksp-kernel.md` gate (b) and `atmosphere-orbits-auroras.md` gate (d) name the
movable-home-window problem: a player anchored to the world while the engine's
window re-homes per job. The kernel adopts **anchor-to-body** (an orbited body
becomes the home-window center → single-anchor orbit). This doc extends the same
principle **one scale up**:

> **Anchor-to-window**: when a ship crosses the dark and approaches another window,
> the *destination window* becomes the re-home target. The home-window center
> (`_window_center` / `bh[0].yzw`) re-homes to the destination window's anchor, and
> the approach is a **local, single-anchor** problem — the followed window is the
> home window's center, exactly as the followed body is in orbit.

The engine supports the re-home (`async-field-domain.md` §7 Q1: the movable
home-window is engine-real; only the policy is unsettled). **[design]** This doc
assigns the policy at world scale: **the window the player's physics is coupled to
wins the anchor.** When that window changes (leaving home, arriving at another), the
window re-homes. This is the natural completion of anchor-to-body — the same
*single-anchor* logic at one spatial scale larger, so the two compose: enter orbit
→ anchor-to-body; leave the body's sky → anchor-to-window; arrive at the next window
→ re-home to it and anchor-to-body again.

### 4.2 The async seam owns the policy (Q1's beyond-Phase-1 sub-question)

`async-field-domain.md` §7 Q1 leaves the *movable home-window relocation policy past
the first box* expressly open, and `corpus-reconciliation.md` §4 records it as a
standing open sub-question (engine supports the seam; policy unsettled). **This seams
doc is that policy's owner-by-assignment.** What it must define (and does, below):

| Policy axis | Design answer | Gate |
|---|---|---|
| When does the anchor flip to a destination window? | at the **approach threshold** — when the destination window's own field becomes the dominant local ρ/q the ship-coupling samples | gate (c): overlap |
| How does it flip back (return) | same anchor-to-window, reversed — the home window re-asserts when you re-enter its dominant field | gate (c) |
| Is the tree's ∇Φ_g stable through the re-home? | must be measured — the kernel's gate (b) flags a teleporting anchor shifts the perceived well (\(ksp\)-kernel §6b); at world scale the same probe applies | gate (a) of the kernel |

### 4.3 Overlap / merge — a seam of competing attractors (gate (c))

The honest question: **can two windows meet, and what happens to two anchored
fields that touch?** The design's answer, grounded in the physics:

| Case | What happens | Why |
|---|---|---|
| **Two windows never genuinely overlap** | the distance between anchored boxes is always > one window width, enforced by the **anchor-competition rule** below | a window is the law "where it matters" (`async` §1.1); two co-located full windows would be two laws in one place |
| **Approach (no contact)** | single-anchor via anchor-to-window (`§4.1`); the destination window's field reads as a growing star, then a sky | normal arrival |
| **Two anchors compete (the seam)** | neither box re-homes to the other's center; the two fields' boundaries **fade to the field-poor interstitial between them**, and the player's coupling picks the stronger local field | a seam of competing attractors is exactly what the local-field mixture predicts — two organized cells meet at their empty remainder |
| **Merge (the pathological case)** | **[design] disallowed for now**, flagged open: two full 64³ fields at the same point are two field runs and a determinism/performance problem, not a physics one | see gate (b) |

**The anchor-competition rule.** Two windows' fields do not "blend"; they resolve
into a **seam**: a band of the field-poor interstitial where neither anchor's
coherence dominates and ρ falls between the floors. The player's coupling (the
sampler's river-law sample, `chunk-field-quantization.md` §2.1) reads whichever
local field is stronger at each point, and the two boxes' published grids **never
need to be consistent** — their boundary is the empty measure, not a shared edge.
This is the honest, documented physics: the local-field mixture means *local fields
are the law, and the seam between them is the mixture's empty measure*, so there is
no two-anchor "who owns this voxel" collision to resolve — there is only a place the
field is thin, which neither window quantizes.

---

## 5. The player-facing arc

The endgame shape, composing the systems this corpus already designed:

```
Build the ship → Stock the coherence → Sail the dark → Found the window → Choose
```

| Stage | What the player does | What the field/systems do | Cross-ref |
|---|---|---|---|
| **Build the ship** | author a coherence-injection device — a regime tuple realized as a vessel (`custom-blocks` authoring surface) | the law gives it thrust, blast-limits, the (1−q) glow | `ksp-kernel.md` §2, §5.1; `custom-blocks.md` §2 |
| **Stock the coherence** | gather deep-rung stored coherence — the fuel blends, the capacitor (the hull is a capacitor at its rung) | storage is ordered matter; charging is slow, discharging fast and scarring (`energy-harnessing.md` §3) | `ksp-kernel.md` §1.2/§2.3; `energy-harnessing.md` §3/§5 |
| **Sail the dark** | navigate by window-star beacons, hold course, meter the glow, keep the Qi bath fed | the field-poor interstitial, the reader as the instrument, the (1−q) glow as the live range gauge | §2; `atmosphere-orbits-auroras.md` §3; `coherence-magic.md` §2 |
| **Found the window** | condense the anchor, plant the first authored matter, watch the ecology emerge | the field condenses a fresh window; terrain precipitates; organisms follow the q-band | §3; `volumetric-terrain.md`; `field-emergent-ecology.md` |
| **Choose** | return to the old world — or stay and grow the new | the choice is a real decision, not a cutscene | §5.1 / §5.2 |

### 5.1 Return — a voyage's trophies

The honest reward for the round-trip (you carried enough coherence to go **and**
come back — the constraint economy makes this a real ask):

| Trophy | What it is | Cross-ref |
|---|---|---|
| **Found-only regimes** | materials that precipitate only in the new window's field (a different field → a different realizable tuple set) — the `custom-blocks.md` found/ invented economy, now *world-located* | `custom-blocks.md` §1, §6 (realizability is contextual) |
| **Fossils** | the ecology's morphologies at the new window — a different attractor basin the field revisits, encountered *in place* | `field-emergent-ecology.md` §3 (species as attractor basins), §6b |
| **The archaeology of the old world** | returning to a home window that kept running is *finding your own past* — the old field condensed, healed, evolved while you were gone | `volumetric-terrain.md` heal — the field's own history |
| **Authored matter** | the first thing you planted is a *sample of your own ordering* — and as `custom-blocks.md` §5 notes, sharing a material is exchanging its ordered matter | `custom-blocks.md` §5 |

### 5.2 Stay — grow the new world

The alternative is the *genuine* endgame: don't come back. You **are** the new
world's first settler. Its field grows with you — the anchoring, the precipitating
terrain, the emerging biosphere are all in miniature what the home world was, and
they are *yours to have founded*. **The long voyage is what the KSP kernel's ships
are FOR**: not the orbit, but the crossing, and the choice of what to do on the far
side. Both branches — trophy-return and settler-stay — are complete plays of a
windowed universe, and the constraint economy is what makes the choice real: you
can afford to found *and* return, or found and settle, but the coherence to do both
forever is the game's honest ceiling.

---

## 6. Honest gates

**(a) What IS the dark, mechanically — chosen: field-poor interstitial, not vacuum.**
The gate the task posed is settled: `§2.1` rejects true vacuum (no field = ships
cannot steer — the river law has nothing to couple to, the "dead" branch) and
adopts the **field-poor interstitial** (ρ below the gas floor everywhere, q low but
nonzero) — the law still runs thin, ships carry their own Qi bath, and the (1−q)
glow is the signature. Gate: pre-register a Phase-2 probe — drive a condensation
drive in a ρ ≈ noise field and measure whether the river law couples enough to
steer, and whether a per-vehicle Qi bath holds q up long enough to be feasible.
**[probe]** This is the one mechanic the whole crossing stands on.

**(b) Two active windows = two field runs — the budget, and the distant-window LOD.**
Two anchored domains is two field domains, each with its own publish (each ≈ 6 MiB
canonical, each a domain step ≈ 0.5–1.5 ms) and its own sampler cost (≈ 1–6 ms
server per tick). **[design] A distant window is a *sparse* simulation, not a second
full 192³ box.** While it is a star (far away), it is rendered from its *body/site
publish record only* — the sparse condensed-body array (`async-field-domain.md` §2.2,
tens-to-hundreds of records, ~KB) — not its dense grid. It becomes a full second
domain *only* on approach (the anchor-to-window flip, §4), when the player's
physics is coupled to it. The LOD ladder: **far = sparse body record → near =
full 64³ window**, crossfaded at the approach threshold. Gate: measure whether one
sparse far window + one full near window stays within the per-tick budget (the
full box is confined to the coupled window; the far window costs ~KB, not ~6 MiB).

**(c) Window overlap/merge policy.** `§4.3` — two windows meet at the field-poor
interstitial (the mixture's empty measure); no shared edge, no voxel-ownership
collision, because neither window quantizes the seam. Approach is anchor-to-window
(single-anchor). **Merge (two full 64³ fields at the same point) is disallowed for
now** — that is two field runs and a determinism/performance problem, not a physics
one (`§6(b)`). Gate: the anchor-competition rule needs a probe — when a ship's
coupling straddles two windows' fields, confirm the sampler reads the stronger
local field and the seam stays field-poor (no cancellation blow-up where two anchors
compete).

**(d) The voyage's coherence budget is the honest length-limiter.** This is a
**feature**, not a bug: `§2.3` designs the constraint economy (the no-free-energy
cap, `energy-harnessing.md` §6, structured as write-back amplitude caps) so a voyage
is *bounded* — you cannot sail indefinitely. There is no "infinite space"; there is
a finite, expensive horizon, and that is what makes a crossing a decision. The gate
is economic, not a probe: confirm the write-back caps (`output ≤ φ⁻¹·input`) hold
so no fuel blend or Qi-bath becomes a net-coherence mint, and a stranded ship is a
real consequence, not a soft-reset.

---

## 7. Feasibility verdict

**This is Phase 2+**, downstream of the KSP kernel. The kernel's prerequisites
(the tree arm, condensed bodies, the Q4 player-return channel, the sync path —
`ksp-kernel.md` §7) are *also* this doc's prerequisites: a voyage needs a ship, a
ship needs the kernel's mechanics, and a ship's destination needs a window the
ship's navigation (a coherence reader in space, `ksp-kernel.md` §5.2) can resolve.
The founding act needs the ecology and custom-blocks authoring (Phase 2/3).

**What this document contributes now** is the **complete destination design** that
the kernel's ships unlock: a precise definition of the window as the local-field
treatment's instance (`§1`), the field-poor interstitial and its navigation by
window-star beacons (`§2`), the founding act and what a fresh window starts with
(`§3`), the anchor-to-window seam policy the async Q1 sub-question needs (`§4`),
and the full player-facing arc from build to found to choose (`§5`). None of it is
engine-invented; it recomposes engine-real physics (the movable home-window, the
sparse body publish, the (1−q) glow, the local-field mixture) into a world-scale
gameplay.

**The honest statement:** the dark's representation is **[design]** beyond the
engine's window seam. The engine supports the movable home-window (`_window_center`,
`async-field-domain.md` §7 Q1) and the sparse/condensed publish, but it does **not**
drive "a field-poor interstitial," "a distant window as a sparse sim," or "window
overlap as a seam of competing attractors" — those are the design choices this doc
makes and gates probe, not engine capabilities. The binding risks, in order:
**(a)** the interstitial-stearability probe (can a ship carry the field it sails
through), **(b)** the two-window budget and distant-window LOD (sparse vs full),
**(c)** the overlap/merge policy. The architecture is sound because the collapse is
real: **a window is where the law runs, the dark is the mixture's empty measure,
and the KSP kernel's ships are what crosses it** — there is no separate
interstellar physics, only the one two-fluid field, thinned to the point where it
becomes a horizon.

---

## Cross-references

- [`ksp-kernel.md`](./ksp-kernel.md) — **the ships this doc gives a destination to**: mechanics, thrust, fuel blends (§2.3), the coherence-budget δv (§3.2), anchor-to-body (§4.4), gate (b)'s two-anchor fight (resolved here at world scale by anchor-to-window, §4).
- [`async-field-domain.md`](./async-field-domain.md) — **the seam** this doc owns: the movable home-window (`_window_center` / `bh[0].yzw`, §7 Q1's open sub-question — the relocation policy this doc assigns), the sparse body publish (§2.2), sync/async loops and JOB caps (§4), the Q4 player-return channel.
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — the **192³/12³ window** (§1.2), the ≈ 6 MiB publish (§2), per-tick budget (§4), the meshless-site activity map.
- [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) — **the sky** of a distant window: the envelope as boundary layer (§1), the auroras as navigation beacons (§3.3) — the "stars" of this universe (§2.2), the envelope-top band and pole discharges.
- [`energy-harnessing.md`](./energy-harnessing.md) — **the fuel and the economy**: deep-rung stored coherence (§1.5/§3), the (1−q) glow (§2), the Qi bath (§4.4), the constraint stance and the no-free-energy cap (§6) — the voyage's honest length-limiter (§2.3).
- [`coherence-magic.md`](./coherence-magic.md) — the player as coherence source; **the coherence reader** — the navigation instrument in the dark (§2.2, §5).
- [`custom-blocks.md`](./custom-blocks.md) — authoring as regime tuples — **the first thing you plant** in a new window (§3.2); the found/invented economy (found-only regimes as voyage trophies, §5.1).
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — **the biosphere you carry / found**: the recognition rule (§6b), species as attractor basins (§3), the biosphere drifting with the field (§4) — the new window's emerging life (§3.3).
- [`the-interstitial.md`](./the-interstitial.md) — **the between this doc crosses.** §2a there
  reads §1.3/§2.1 this doc's field-poor interstitial — the mixture's empty measure — as the
  sparse medium the windows float in; §2a there's thin field gives that emptiness character.
  Reverse pointer: the interstitial designs the texture of this doc's voyage's between.
- [`the-zenith.md`](./the-zenith.md) — **the edge you cannot leave through.** §2c there
  reads §2 this doc's voyage as the honest edge — the zenith is the window's boundary, not
  its door: you leave a window by sailing the dark from a ship (`world-seams.md` §2), never
  by stepping off the ceiling; §2.3's coherence-budget length-limiter is the leaving the
  zenith eschews. Reverse pointer: the zenith names the boundary the voyage is the only way
  across.
- [`the-harbor.md`](./the-harbor.md) — **the departure's place.** §1/§2 there reads §1/§2
  this doc's voyage as the crossing the harbor begins — the named kept structure built at
  the window's edge holding the seam's anchor; §2.2's window-reads-as-a-star is the lamp's
  last light; §2.3's coherence-budget cost is the harbor never changes (a door, never a
  shortcut); §4's anchor policy the harbor sits at; §6/§7's Phase-2+ gates the full harbor
  rides. Reverse pointer: the harbor gives the voyage a home-ward departure place.
- [`the-rite-of-passage.md`](./the-rite-of-passage.md) — **the founding act.** §2.5 there reads
  §3.2 this doc's planting a coherence seed condenses a fresh anchor, terrain precipitates,
  the biosphere emerges — the founding rite is the seam's new-window beginning. Reverse
  pointer: the rite plants the seed that precipitates a world.
- [`the-landform-name.md`](./the-landform-name.md) — **the navigable name.** §3 there
  reads §2 this doc's voyage — steering by the named land; §2.2 a window as a star
  (the landmark the navigable name reads); §2.3 beacon-reading + the coherence budget
  (the honest bound of navigating by a name). Reverse pointer: the navigable name
  steers the voyage by named land.
- [`the-between.md`](./the-between.md) — **the empty measure.** §1.2 there reads the
  local-field-mixture (the dark is the mixture's empty remainder); §2.1 the
  field-poor interstitial; §2.2 a window reads as a star; §2.3 the coherence-budget
  crossing; §4.3 the seam of competing attractors; §6/§7 the Phase-2+ gates. Reverse
  pointer: the between is the mixture's empty remainder.
- [`the-beacon.md`](./the-beacon.md) — **the near-light cousin.** §2.2 there reads a
  distant window reads as a star; the Beacon is that read at the near scale. Reverse
  pointer: the beacon is the window's near-light.
- [`the-migration.md`](./the-migration.md) — **the voyage / the far end.** §2 there
  reads the crossing; §2.3 the coherence-budget; §3.2 the founding act; §6 the
  Phase-2+ gates. Reverse pointer: the migration's arrival is a voyage's founding
  act.
- [`the-raft.md`](./the-raft.md) — **the voyage’s water-raft.** §2 the crossing (the raft is a water-borne crossing, the voyage’s fluid leg). Reverse pointer: the raft is the voyage’s water-vehicle.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers (cited, not re-derived); the async Q1 open sub-question this doc's seam policy closes (§4).
- Theory (read-only): `CassiTheory/cosmology/cosmology-from-phi.md` — **the local-field-mixture treatment** (the window-integrated per-cell mixture; the global is the measured mixture of local fields — the physics of §1.2 and the dark as its empty measure); `CassiTheory/cosmology/desi-lattice-averaging.md` (the distance-channel washout — window-averaging suppresses a lattice wiggle, the mixture's smoothing); `CassiTheory/speculations/qi-bubble-propulsion.md` §2.5 (the (1−q) glow, the waste law the ship's signature rides); `CassiTheory/speculations/qi-bubble-propulsion.md` §3–4 (rung-shift and lattice geometry — creative-propulsion concepts a long voyage may borrow, flagged [design], not copied).
- Engine (read-only): `CassiCosmos/scripts/cassi_physics_engine.gd` (`_window_center` / `bh[0].yzw` — the movable home-window the seam policy drives; `submit_steps(block)`, `JOB_STEP_CAP = 64`, `TREE_JOB_STEP_CAP = 8`), `CassiCosmos/compute/cassi_nbody_gravity.glsl` (river law, mode-5 tree gravity — the medium the dark's thin field still couples to).
