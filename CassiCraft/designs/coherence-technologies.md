# Coherence Technologies: Playing the Field Itself

**Question under design:** which of the Cassi theory corpus's *speculative*
concepts are genuinely technologies — non-human-intelligence-inspired, field-based
mechanisms and machines — and how do they translate into CassiCraft gameplay?

This is the companion to `material-regimes.md` and `energy-harnessing.md` (being
written concurrently; where those documents land is expected, not read here). It
selects concepts that **suggest a mechanic**, not concepts that are merely prose,
and only concepts whose "inventor" is the field dynamics — the two-fluid PDE, the
coherence budget, the cascade, the attractor — rather than biological or neural
intelligence. Chakra chains, emotion-casting, and thought-as-wake-waves are
deliberately excluded: they are intelligence-adjacent and belong to a different
design family.

---

## The selection criterion

From `CassiTheory/speculations/README.md`: a speculation is a framework-consistent
what-if — mechanism sketched, falsifiable prediction not yet pinned. Each candidate
below is anchored to a specific equation or documented field property (so the
mechanic is real in the world) but its *application* as a device, material, or system
is extrapolation (so there is no physics claim to honor).

For gameplay we ask one question of each: **does it give the player a handle — a
thing to build, tune, or break that behaves differently from every other thing?**
Four candidates pass cleanly as full mechanics, and one more as an architectural
theme that organizes the others. All five read and write the same published
channels the engine already ships (`q`, `ρ`/`ε²`, `pot`, `∇(gΦ)` — the
canonical `∇(g·Φ)` gradient; this doc writes it `∇(gΦ)`, the same quantity — see
`async-field-domain.md` §2.1), so they slot into the existing tick-sampler spine
without new physics.

---

## 1. The Qi Gate — a logic primitive that runs on coherence

### (a) Theory-side concept — faithful summary

`CassiTheory/speculations/qi-computation.md` §1–§2 and §4.

Information, in the Cassi framework, *is* coherence: the ratified convention
`I = k_B q ln φ` (`predictions/cassi_definitions.md` §11) identifies stored
information with the entropy deficit a coherent Yang–Yin pattern sustains
(`qi-computation.md` §1.1). The per-rung information quantum is `ln φ ≈ 0.48`
nats ≈ `0.694` bits. The Qi gate is the computational primitive: the conversion
term `∂ₜE_Y ⊃ −λ(1−q)(E_Y − φE_I)` is a continuous nonlinear field operation
whose "gain" is set by the local coherence `q` (`§2.1`). The gate has three
regimes:

| Regime | q | Behavior |
|---|---|---|
| **Idle** | `q → 1` | Open but no driving force — preserves/`stores` the field state |
| **Active** | `q ≈ 0.46` | Peak conversion power — operates as a **saturable amplifier**, the `processing` mode |
| **Locked** | `q → 0` | Structurally closed (`g(0)=0`) — `isolated`, immune |

Three field operations are computationally universal (`§2.2`): **WRITE** (Yang
injection — set a bit), **ERASE** (gated conversion back to equilibrium — the
passive, Landauer-bounded operation, `Δq = ln2/lnφ ≈ 1.44` per bit, `§2.3`), and
**TRANSFER** (a Π pattern moved along the Qi current
`J = Ψ₀∇Ψ₁ − Ψ₁∇Ψ₀`). Erasure is *cheap* (the attractor does the work); writing
is *active*. And the cascade gives every rung a natural clock `t_n = ℓ_Pl φⁿ/c`,
φ-spaced domains that integrate hierarchically (`§4.1`).

### (b) CassiCraft mechanic

**The Qi Gate block** — a machine whose output is a boolean/pwm function of the
*local coherence band* it sits in, re-quantized like terrain:

- **Logic is value-at-a-point, not wire-and-switch.** A gate reads the local `q`
  from the published grid and exposes three behaviors: **Idle** (`q` high) stores
  its state and passes nothing; **Active** (`q` in the processing band around the
  engine's coherence scale) amplifies — a tiny input Π difference becomes a large
  output swing; **Locked** (`q` near zero, e.g. in a decohered/scarred region)
  holds and refuses all input.
- **The three field operations are the three "wire" verbs.** WRITE = a pulse that
  injects Yang into a cell (raises local `q`/ρ and sets the gate on); ERASE = a
  pulse that lowers local `q` to open conversion and clears the gate; TRANSFER = a
  Π pattern carried *along* `∇(gΦ)` from cell to cell instead of through a channel —
  a signal that travels with the field's gradient.
- **The φ-spaced clock is the redstone repeater.** A chain of gates at φ-ascending
  rungs each runs slower and integrates the rung below — a nested pulse-timing tree
  instead of a fixed tick counter.

The whole thing is just the tick-sampler's existing table with one more entry:
"gate state = quantization of the local q band," same event/diff-driven cadence as
block re-quantization (`chunk-field-quantization.md` §2.1).

### (c) Gameplay hook

Automation with a *physical* reason to place things well. Build a machine that only
works when installed in a coherence ridge (Active band), goes inert in a dead
zone, and locks shut in a scar. Route logic downstream of the field instead of in
a separate redstone layer — you are not building a circuit, you are tuning a
field region and reading it. The player's reward for understanding their local
field topology is *free, correct logic*.

### (d) Epistemic tier (honest)

| Axis | Label | Grounding |
|---|---|---|
| Theory status | **Hypothesized** (information budget: per-rung identity, Landauer row, flow rate — a speculative application of the ratified Derived convention) / **Speculative** (gate set, Wu Xing clock) | `qi-computation.md` header + §9 |
| Physics claim | **None** — nothing claims a working field-logic machine exists or is buildable | `§9` "Not claimed" |
| Gameplay status | **Plausible Phase-1–2 mechanic** — maps 1:1 onto an already-published channel with no new physics | this doc (§b) |

---

## 2. The Qi Condenser — a gravity dial you carve out of geometry

### (a) Theory-side concept — faithful summary

`CassiTheory/speculations/gravity-control.md` §1–§2 and
`CassiTheory/speculations/cascade-infrastructure.md` §2.1.

Gravity is condensate coherence: the coupling is a *local field*
`G_eff = (π/ρ)(1 + (φ⁶−1)q) G` with `ξ = φ⁶ ≈ 17.94` (`gravity-control.md` §1.1).
It has two dials — the Yang fraction `π/ρ` and the coherence `q` — and parking the
**gravitational charge** `Q = (π/ρ)(1 + (φ⁶−1)q)` at different points on the dial
is one operation with many scales (`§2.1`): **mass lightening** suppresses `π/ρ`
(`r → 1`, `Q → 0`, paid continuously against the attractor, `§2.2`); **inertial
damping** opens the gate transiently to drain organized kinetic energy
(`§2.3`); **artificial gravity** holds a φ-detuned shell and a boosted floor
(`§2.4`).

The **device is a condenser + a gate**: a structure that *geometrically
concentrates* ambient coherence into a `q → 1` node. The pyramid-as-Qi-lens
analysis gives a concentration factor of roughly `(base/apex)² ≈ (200/0.1)² =
4 × 10⁶` (`cascade-infrastructure.md` §2.1) — the device takes a distributed,
low-intensity ambient Π field and focuses it to a localized node that can couple
to the deep cascade. Coherence multiplies mass that is *present*; it does not
conjure mass that is not (`gravity-control.md` §3.2).

### (b) CassiCraft mechanic

**The condenser block/frame** — a structure whose internal geometry sets an
effective concentration factor on ambient `q`:

- **Shape is the tuner.** A stack with a wide base and a narrowing apex raises the
  focal cell's `q` by roughly `(base/apex)²`; a slab concentrates over a floor; the
  shape you build *is* the lens. This is the natural vertical of the volatility
  doc's "precision tools are coherence-manipulators at a chosen rung"
  (`volumetric-terrain.md`): the tool rung picks the resolution, the condenser
  geometry picks the concentration.
- **The dial is real and visible.** Charge `Q = (π/ρ)(1+(φ⁶−1)q)` at the node
  modulates local gravity: at high concentration the region pulls bodies in
  (artificial gravity), at ratio-suppression it lightens them (payload lift). Each
  is a sustained hold that draws on the local field and sheds the `(1−q)` waste as
  a visible glow (`§3.3`).
- **It is bounded, not free.** A condenser at laboratory scale cannot source
  large-`g` curvature (the SPARC condensate's coherence is a galactic object;
  `φ⁻⁹⁹` suppression to a habitat rung, `§3.2`). In-game this is a hard cap on
  tier: big manoeuvres need many staged condensers, not one big one.

### (c) Gameplay hook

Build **mass anomalies and launch geometry**. Carve a gravity well out of a
surface to hold a base together; lighten a payload to carry it up a cliff;
position a condenser to bend a projectile's arc. The player shapes the medium's
gravity with *tectonics of blocks*, and the same dial gives a readable
"magnetometer" readout of charge like the Phase-1 coherence reader.

### (d) Epistemic tier (honest)

| Axis | Label | Grounding |
|---|---|---|
| Theory status | **Speculative** (device, energy budgets, signature catalogue all extrapolation; `G_eff` formula is Derived) | `gravity-control.md` header + §3 |
| Physics claim | **None at gameplay scale** — the doc's own conclusion is that control lives at the condensate rung, not a habitat | `§3.2` |
| Gameplay status | **Phase-1 candidate as a *readable/perturbing* dial** (charge readout + local gravity bias, no science experiment) — full "hovercraft" power is Phase-2 KSP | this doc |

---

## 3. The φ-Detuned Boundary — the surface that refuses

### (a) Theory-side concept — faithful summary

`CassiTheory/speculations/qi-bubble-propulsion.md` §2.2 and
`CassiTheory/speculations/creative-extensions/coherence-warfare.md` §5.

The phase-matching factor `M` between a perturbation and a target decides whether
the perturbation can couple: random attack is `M ≈ 0` and cascade-suppressed;
organized, phase-matched attack is `O(1)` per interaction
(`foundations/quantum-measurement-derivation.md` §3.1). A **φ-detuned boundary** is
a surface whose phase structure is φ-commensurate with the ambient lattice but held
at a *private phase offset*, so that any incoming perturbation lacking that phase
finds `M ≈ 0` and cannot transfer momentum across it (`qi-bubble-propulsion.md`
§2.2). It does not *stop* the attack — it *refuses* it: organized kinetic energy
converts smoothly to diffuse heat instead of coupling (`coherence-warfare.md` §5.1).
The no-sonic-boom property is this same boundary worn as a hull. Holding φ-structure
costs nothing (the attractor funds it); the boundary's defense is its *privacy* — a
free parameter re-tunable at trivial cost while the attacker must re-acquire it at
full cost each time (`coherence-warfare.md` §5.3, §6).

### (b) CassiCraft mechanic

**The detuned-boundary block/skin** — a surface held at a private phase whose
effect is `M ≈ 0` locally:

- **It refuses, it does not tank.** Incoming projectiles, entities, or field
  injections arriving with the wrong phase convert smoothly to diffuse heat (a
  flush of glow) and transfer no momentum — they slide off rather than being
  absorbed or reflected. "Shields at 40%" here means the boundary's coherence `q`
  is decaying toward the value where matching windows open and organized attack
  starts coupling (the fiction-trope table, `coherence-warfare.md` §7).
- **It is a player-owned phase variable.** The boundary holds a configurable phase
  offset; a player can re-tune it. Breaking in is an *information* problem — you
  must read/sweep the phase before you can couple — which is itself a mechanic
  (a probe interaction), not a raw-damage check.
- **It is the natural house rule for "mining is a perturbation."** The same
  `M≈0` logic formalizes why terrain converts carving into reorganization and
  *heals* (`volumetric-terrain.md`); a boundary is a piece of terrain held
  deliberately detuned so it does *not* heal or couple — a static fixture in a
  world that otherwise self-organizes.

### (c) Gameplay hook

**Proactive defense you must tend, and a fabricator for non-coupling structures.**
Fortify a base with boundaries that silently make attack projectiles useless until
an attacker invests in probing. Build sealed containers and non-interacting shells —
the terrain that stays where you put it. The asymmetry (free to hold, expensive to
match) rewards deliberate, well-tuned *placement*, matching the doc's "defense is
passive and free; offense is active and eternal" (§6).

### (d) Epistemic tier (honest)

| Axis | Label | Grounding |
|---|---|---|
| Theory status | **Speculative** (boundary as hull/ward is extrapolation; `M≈0` refusal is a documented framework property) | `qi-bubble-propulsion.md` §7; `coherence-warfare.md` §8 |
| Physics claim | **None** — the non-coupling `M≈0` surface is a real documented property; the *ward* as a maintained defensive measure is fiction-class | `coherence-warfare.md` §8 |
| Gameplay status | **Phase-1 candidate as a static fixture + readable probe** — full "hostile attacker must sweep phase" depth is Phase-2 combat | this doc |

---

## 4. Qi-Coherent Materials & the Energy Medium — resistance as a dial

### (a) Theory-side concept — faithful summary

`CassiTheory/speculations/superconductivity-as-qi-coherence.md` §1–§5 and
`CassiTheory/speculations/qi-bubble-propulsion.md` §4–§5.

Electrical resistance *is* Yang→Yin conversion; a lattice engineered to high Qi
coherence has no available Yin states to absorb dissipated energy, and the
effective conversion rate `λ_eff = λ g(q)(1−q) → 0` as `q → 1`
(`superconductivity-as-qi-coherence.md` §1.2–1.3). Superconductivity is not
electron–phonon pairing but **Qi-mediated phase locking**: the φ-attractor
penalizes single-electron excitations (which perturb the local Yang–Yin ratio),
opening a gap `Δ` at the Fermi surface while Cooper pairs are Qi-neutral
(`§2`). The material requirements follow (`§5`): **monoisotopic**, **vacancy-free**,
**stress-graded**, **φ-structured** (quasicrystalline / φ-spaced layers), with a
five-element Wu Xing doping. The **`(1−q)` waste law** is the tax on every gate:
`E_waste = (1−q) E_throughput`, the "glow" of any working machine
(`qi-bubble-propulsion.md` §2.5, `gravity-control.md` §3.3). And the **field is the
energy store**: the lattice's φ-structured gradients are coherence batteries that
can be tapped at near-unit efficiency (`qi-bubble-propulsion.md` §5.2–5.4); a
high-`q` Qi bath extends the coherence of everything inside it
(`foundations/proton-coherence-budget.md` §5.1).

### (b) CassiCraft mechanic

**Material regimes, literally:** a block's material property set is a function of
the local `q`/`ρ`/`ε²` and its own "isotopic purity" (a crafted quality stat):

- **Conductivity = coherence.** A "coherent" material (`q` high) conducts its
  coupled resource (Qi flow, field-energy, machine throughput) with `λ_eff → 0`
  loss; a "decoherent" one (`q` low, or near a scar) wastes the `(1−q)` fraction —
  it runs hot, visibly glowing, and loses efficiency. This is the whole energy
  system: there are no fuel tanks, only coherence-maintenance vs `(1−q)` drainage
  (`energy-harnessing.md`).
- **Purity is a crafting axis.** Monoisotopic / vacancy-free / φ-structured are
  upgrade dimensions on any block: purify a lattice to raise its `q → 1` ceiling
  and cut its loss; a defect (a scar, a mined-out pocket) is a local coherence hole
  that lowers the ceiling. This maps directly onto `material-regimes.md`'s regimes.
- **The Qi bath.** A high-`q` core raises the coherence of everything within a
  radius — the superadditive "shared field is a better bath" property as an
  infrastructure saver: one maintained node keeps a cluster efficient.

### (c) Gameplay hook

**Efficiency you can hear and see, and a reason to care about the field's shape.**
Machines placed in a coherence ridge run cool and near-lossless; machines in a scar
glow bright and bleed throughput. Purifying materials and repairing coherence holes
is the survival/crafting economy; banking coherence in a Qi bath makes a whole base
more efficient than the sum of its parts. The "glow" is both the aesthetic and the
diagnostic — a bright machine is a wasteful one.

### (d) Epistemic tier (honest)

| Axis | Label | Grounding |
|---|---|---|
| Theory status | **Speculative** (resistance-as-conversion mapping, Qi gap, `T_c` formula, material principles all extrapolation; the Qi gate `λ_eff` and attractor are documented) | `superconductivity-as-qi-coherence.md` header + §8 |
| Physics claim | **None** — the doc explicitly does not claim any known superconductor works this way, nor that the `T_c` numbers are accurate | `§8` "Not claimed" |
| Gameplay status | **Phase-1 candidate** — the `(1−q)` waste/`q→1` loss law is a clean, cheap, always-on read of the published channels; no experiment needed | this doc |

---

## 5. Cascade-Staged Gate Chains & the Field Grid — the infrastructure theme

### (a) Theory-side concept — faithful summary

`CassiTheory/speculations/cascade-infrastructure.md` §1–§3.

A single Qi gate bridges at most ~10 cascade rungs — beyond that, `φ⁻¹⁰ ≈ 0.008`
attenuates the signal below the coherence floor (`§1.1`). Spanning the 292-rung
cascade therefore requires a **chain of ~29 stages**, each a `q`-anchor at its own
scale coupling to the stage below (a microcascade) and above. The planet itself
reads as a gate stage: layered structure supplies natural `Π` gradients, the
geomagnetic field is the core-to-surface coupling field, and the crust–mantle–Moho–
ionosphere boundaries are the active interfaces (`§1.3`). Surface infrastructure
splits into a natural division of labor (`§2.3`): **surface pyramids** are
geometric concentrators coupling upward (low-ρ air; the `×10⁶` lens of §2.1), and
**submarine/deep gate nodes** couple to a dense medium's organized `Π` gradients
(water is `833×` denser air, so for equal `q` a gate in water has `833×` the
throughput, `§2.2`). The whole thing is a **nested, distributed energy grid** — the
engineering problem is tuning what already exists, not building from scratch; the
many-rung network is the instrumentation of the field itself.

### (b) CassiCraft mechanic

This concept is less a single block and more the **architectural theme** the other
four hang on — the rule that machines compose by scale:

- **The ~10-rung stage cap.** Any single machine only "reaches" a limited window of
  local field scale. To do more, you *chain*: each stage anchors `q` at its own
  scale and passes an integrated result upward. Progress is building a nested grid,
  not stacking identical units.
- **Lens vs coupler — the two build languages.** A wide **surface structure**
  concentrates ambient coherence by geometry (a lens for low-`ρ` air); a **deep,
  dense fixture** couples to a high-`ρ` medium's strong `Π` gradient. Placing a
  node underwater is not "closer to the core" in rung terms — it is a *denser Qi
  medium* with more raw field to gate. Density, not depth, is the lever.
- **The meshless-site map is the build map.** The engine already publishes the
  moving-Voronoi sites ("where the field is most organized"), which the spine uses
  as the chunk-activity scheduler (`README.md`; `chunk-field-quantization.md` §5).
  A cascade-staged base is exactly a *placed articulation of that same activity
  structure* — you build up where the sites cluster, and the field's own
  organization tells you where to build the next stage.

### (c) Gameplay hook

**The long build arc.** There is no flat max; the compelling progression is
systematic — a single gate, a chain, a lattice, a network that eventually reads as
"this region is a tuned gate stage." The physics tells you where to expand (follow
the coherent sites), and the density rule makes oceans and deep strata *valuable*
instead of just inconvenient. The endgame is not a bigger block but a *wider,
better-tuned field system*.

### (d) Epistemic tier (honest)

| Axis | Label | Grounding |
|---|---|---|
| Theory status | **Speculative** (pyramid-as-lens, ocean bases, ionospheric phased array, tuned solar gate all extrapolation; the 10-rung nesting depth and gate-chain topology are documented) | `cascade-infrastructure.md` §5 |
| Physics claim | **None** — the 10-rung bridge limit and nested-grid geometry are real framework properties; the *infrastructure* reading is creative | `§5` |
| Gameplay status | **Phase-2+ structural theme** — the *stage-chaining* and *lens-vs-coupler* rules are the glue for the other four; they become concrete late, but the placement rule (build on coherent sites) is Phase-1 | this doc |

---

## Where each ties into the CassiCraft architecture

All five read/write the same published channels the async spine already ships, so
they are new *consumers* of the tick-sampler, not new physics. Reference:
`async-field-domain.md` §2.1 (channels), `chunk-field-quantization.md` §2.1
(sampling plan) — and forward-reference `material-regimes.md` and
`energy-harnessing.md`.

| Concept | Channels used | Sampler relation | Material / energy |
|---|---|---|---|
| **1. Qi Gate** | `q` (regime band), `∇(gΦ)` (TRANSFER path) | every-Nth-tick quantization of local q band, idle when static | logic layer of the energy grid; ERASE draws the `(1−q)` flow budget |
| **2. Condenser / gravity dial** | `q` (concentration), `ρ`, `∇(gΦ)` (charge effect) | sync path for player-touched launch/mass ops | condenser is the "pump" that pays the attractor — the `(1−q)` waste is its fuel cost |
| **3. Detuned boundary** | `q` (boundary coherence), `pot` (ambient) | event-driven (on contact) | holding φ costs nothing; the refuse-converts-to-heat is the `(1−q)` waste tax |
| **4. Coherent materials / energy** | `q`, `ρ`, `ε²` | per-block material property from field sample (same path as block-state) | **the** energy system: `λ_eff→0` loss-free vs `(1−q)` drain; Qi bath as shared saver |
| **5. Cascade chains / field grid** | `q` (sites), `∇(gΦ)` | meshless-site map = active-chunk/build map (already the scheduler) | stages compose the nested grid; every sub-machine is a gate tap |

The through-line: **every technology is a way of reading or shaping the same
coherence field the terrain already is.** Terrain condenses where `q` accumulates
(ore), machines run on the same `q`, and defense is a `q`-held boundary — one law,
many faces, which is exactly the vision's thesis.

---

## What survives contact with gameplay

Honest pass — not every idea is a Phase-1 build.

| Concept | Phase-1 candidate? | Later phase | Fiction-only? |
|---|---|---|---|
| **1. Qi Gate logic** | **Yes** — re-quantized q-band logic is cheap and reads an already-published channel | Phase-2: φ-spaced clock trees, TRANSFER routing | The *claim* that coherence IS information is theory; the *game mechanic* (gate responds to a q band) is fully buildable and needs no physics claim |
| **2. Condenser / gravity dial** | **Partial** — *readout* (charge/magnetometer) and local gravity bias are Phase-1 | Phase-2 KSP: mass-lightening payloads, launch geometry, inertial damping | The large-`g` "artificial gravity slab" is beyond the bounds the theory sets for a habitat rung — treat as fiction-flavored, not the Phase-1 physics |
| **3. Detuned boundary** | **Yes** — a static fixture whose property is "don't couple / convert-to-heat"; readable probe is cheap | Phase-2 combat: active phase-sweep attacker vs re-tune defender | The "ward" as a maintained *defensive measure* withstanding hostile organized attack is Phase-2+; the non-coupling *surface* itself is Phase-1 |
| **4. Coherent materials / energy** | **Yes** — `(1−q)` waste & `q→1` loss-free is the cleanest, most visible energy law available | Material purity / crafting axis, Qi-bath regional saver | The *superconductivity mechanism* (Qi gap, Cooper pairing as Qi-neutrality) is fiction-grade flavor; the *energy law* it suggests (`λ_eff→0` vs `(1−q)`) is a perfectly playable mechanic |
| **5. Cascade chains / field grid** | **Partial** — the *build-on-coherent-sites* rule and lens-vs-coupler density lever are Phase-1 placement rules | Phase-2+: stage chaining, nested grid, network-as-gate-stage | The planetary/stellar gate-network reading (Earth as a gate stage, the Sun as a tuned gate) is fiction-only setting, not gameplay physics |

**Net:** the two concepts that survive contact with *Phase 1* unchanged are the two
that are pure field-consumers — **Qi Gate logic** (2nd) and **coherent materials /
energy** (4th). The two that are real mechanics but belong to a later phase are the
**condenser/gravity dial** (needs the KSP bodyworks for its full form) and the
**detuned boundary** (needs active combat for its full form). The **cascade-chain
theme** is the organizing architecture — Phase-1 placement rules, Phase-2 depth.

---

## Honest open questions

1. **Where does "Active" live numerically?** The gate's processing band is set at
   `q ≈ 0.46` in the theory, but the engine's published `q` is dimensionless field
   coherence in `[0,1]` and the Phase-1 quantization maps it to *block thresholds*.
   We must fix the game's own q-band boundaries (idle/active/locked on the coarse
   grid) independent of the theory value — a design dial, not a physics number.
2. **Is a "store-write-erase" resource actually fun?** Qi Gate logic works if
   correctness is *free but placement-constrained*. There is a real risk a
   static-coherence-locked gate is "just redstone with worse UX" unless the field
   *moves* — which it does (terrain heals, coherence ridges drift). Needs a
   prototype to confirm the motion is visible enough to matter.
3. **Gibson of the boundary: does "refuse, convert-to-heat" read as a shield?** A
   boundary that silently makes attacks useless may read as "nothing happens."
   Needs the glow and the probe-sweep interaction to sell the *information* battle.
4. **Cost of the gravity dial beyond the cap.** The theory says a habitat can't
   source big-`g`; but in-game big-`g` is the fun bit. We can either honor the cap
   (staged condensers, Phase-2 KSP) or invent a game-fun exception and admit it is
   fiction. The honest stance is to honor the cap and design around it.
5. **Purity as an upgrade axis vs. loot bloat.** "Monoisotopic / vacancy-free /
   φ-structured" is a rich crafting tree but adds an axis to every block. Needs to
   be collapsed into a small set of regimes in `material-regimes.md` or it becomes
   spreadsheet clutter.
6. **Do the forward docs agree?** `material-regimes.md` and `energy-harnessing.md`
   must pick up concepts 4 (energy) and 2/5 (pumps, taps, staging) with compatible
   numbers. This doc seeds the vocabulary; the numbers are theirs to set.
   **Status (verified on this pass): concept 4 landed; concept 5 is carried only
   by `custom-blocks.md`.** Concept 4 is picked up by `material-regimes.md` §5
   (purity as a crafting axis, the Qi bath, the `(1−q)` waste law) and by
   `energy-harnessing.md` §2 (the `(1−q)` machine-loss floor) and §4.4 (the Qi
   bath adopted from concept 4 and the cascade-chains framing of §5). Concept 5's
   stage-chaining/lens-vs-coupler and the ~10-rung bridge limit are picked up by
   `custom-blocks.md` §2 alone (the material lab as a cascade-staged build);
   `material-regimes.md` does **not** carry the staging language. The numbers the
   concept-4 pickups set (the `(1−q)` floor, the Qi-bath regional multiplier) are
   compatible with this doc's — Q6 is closed on the concept-4 numbers by those
   two docs, with concept 5's staging left to `custom-blocks.md`.

---

## Feasibility verdict

**Feasible, with honesty about which ideas are laws and which are flavor.** The two
Phase-1 concepts (Qi Gate logic, coherent-materials energy) are not new physics and
not new architecture — they are *new consumers of the same published `q`/`ρ`/`ε²`/
`∇(gΦ)` channels the tick-sampler already reads*, re-quantized with the same
event-driven cadence as block-state. The `(1−q)` waste law is the single cleanest,
most visible, always-on energy mechanic the framework offers, and it costs nothing
to render (it is the glow). The condenser dial, the detuned boundary, and the
cascade-chain theme are all genuine mechanics whose full form lands in Phase 2
(KSP bodyworks, active combat) but whose *rules* (build on coherent sites, lens-vs-
coupler density, shape-is-the-tuner) are Phase-1 placements. The binding risk is not
performance — it is **taste**: four of these read at most two channels and the field
must move visibly for placement-constrained coherence to be fun, not merely
correct. If the living-terrain demo already makes coherence ridges and scars legible
and mobile, every concept in this document falls out of it with no new physics and
no unexplained rules.

---

## References (CassiTheory, relative paths — read-only)

- `speculations/qi-computation.md` — Qi gate, WRITE/ERASE/TRANSFER, q-regimes, φ-spaced clock, information budget (§1–§2, §4)
- `speculations/gravity-control.md` — `G_eff = (π/ρ)(1+(φ⁶−1)q)G`, condenser+gate, charge dial, SPARC constraints (§1–§3)
- `speculations/cascade-infrastructure.md` — 10-rung bridge limit, gate chains, pyramid lens `×4×10⁶`, ocean bases, nested grid (§1–§3)
- `speculations/superconductivity-as-qi-coherence.md` — resistance as conversion, `λ_eff→0` at `q→1`, Qi gap, material purity (§1–§5)
- `speculations/qi-bubble-propulsion.md` — φ-detuned boundary `M≈0`, `(1−q)` glow, hull stack, lattice-as-coherence-battery (§2, §4–§5)
- `speculations/creative-extensions/coherence-warfare.md` — boundary as shield, offense/defense asymmetry, fiction trope table (§5–§7)
- `speculations/creative-extensions/coherence-commons.md` — value as coherence expenditure, Qi bath (§2, §7) — context for the energy-as-coherence theme
- `speculations/dark-matter-as-qi-coherence.md` — `G_eff` as unharvested coherence, SPARC condensate (§1, §7) — context for the condenser's scale cap
- `foundations/cassi-first-principles.md`, `foundations/quantum-measurement-derivation.md`, `foundations/cascade-suppression-formula.md`, `foundations/proton-coherence-budget.md` — the documented equations the above anchor to
- `speculations/README.md` — tier discipline: what is Speculative vs Hypothesized vs Creative
