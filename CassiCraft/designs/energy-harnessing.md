# Energy: Harvesting, Storage, Transport, and What It Does

**Question under design:** how a living field world is *powered* — where
usable energy lives in the two-fluid field, the mechanisms that tap it, how it
is stored and moved, and what it buys the player. Companion to
[`async-field-domain.md`](./async-field-domain.md) (the seam a harvesting
machine reads), [`chunk-field-quantization.md`](./chunk-field-quantization.md)
(the field channels a machine samples), and
[`volumetric-terrain.md`](./volumetric-terrain.md) (what deep-rung energy buys
the precision tools). `material-regimes.md` (rung-ordered matter) is written
concurrently; this doc forward-references it and does not wait on it.

Every quantity below is taken verbatim from the physics engine
(`CassiCosmos/compute/*.glsl`, `CassiCosmos/scripts/cassi_physics_engine.gd`)
or explicitly flagged **[assumption]** where the game derives from measured
engine physics rather than a benchmark. Nothing is invented.

---

## Summary table

| Question | Phase-1 answer (concrete) |
|---|---|
| Primary reservoir | **Potential gradients** `∇(g·Φ)` — "field hydro" (the river law's gradient, built per-step into `_grad_buf`) |
| Conversion idiom | **Machines are field operations** (inject/withdraw EY, channel ε², steer ∇q), NOT inventory-based generators |
| Storage | **Coherence capacitors** = deep-rung ordered matter (batteries by rung); the merge lineage (dust → object) is the growing store |
| Transport | High-ξ conduits (coherence routing) + pulses along `∇(g·Φ)`; a range/loss model |
| What it does | Power precision tools at deeper rungs; run vehicles/rockets; world-healing investment; anti-corruption |
| Economy stance | **Constraint, not currency** (Phase 1 recommendation) |
| Feasibility | Feasible — energy is already *in* the published/sample-able field channels; only the machines are new |

---

## 0. The core stance

CassiCraft's energy is not a new substance. The field already carries, in the
published channels a harvesting machine must read, every reservoir we want:
`ρ = EY+EI` (density), `q` (coherence), `ε² = (EY − φ·EI)²` (decoherence),
`pot` (potential Φ), `∇(g·Φ)` (the river gradient), and the medium's own
velocity (`vel[id] = (∂EY/∂t, ∂EI/∂t, 0, ε²)`). Energy harvesting is the act of
*reading* one of these and *perturbing* the field to convert it into
machine-usable work. There is no "energy item"; there are field operations.

This makes the machine layer consistent with the architectural spine: a
harvester is just another consumer of the async publish (like the tick-sampler)
plus a small write-back *into* the domain — the **Q4 player-return channel**
(`async-field-domain.md` §7 Q4), the "player-edit feedback lane" the companion
docs already flag as required. It does not invent a material economy
that would strand Cassi's own law.

---

## 1. The energy reservoirs (where usable energy lives)

### 1.1 Potential gradients `∇(g·Φ)` — "field hydro" (primary)

The river law (`cassi_nbody_gravity.glsl:7-12`) is
`a = −G_N·(π/ρ)·∇(g·Φ)`. The gradient `∇(g·Φ)` is built once per step into
`_grad_buf` (a `vec4`/cell; the gradient pass, `cassi_nbody_gravity.glsl:171-182`),
and `Φ < 0` at mass (spectral Poisson, `k=0` nulled). So `∇(g·Φ)` points toward
matter and *steepens* toward organized mass.

**As a reservoir:** a mass condenses, and the field around it carries a
potential-energy gradient. Let something *move down* that gradient and the field
does work on it — the exact work the river law already does on particles. A
machine that sits in the field and lets flux flow through a `∇(g·Φ)` well is
"field hydro": it taps the pressure the field exerts over distance, in the same
way a water wheel taps a pressure head. This is the **primary, honest,
always-present** reservoir — if there is matter, there is a gradient.

### 1.2 Medium kinetic energy — coherence turbines

The two-fluid medium carries its own kinetic energy. Each PDE step writes
`vel[id] = vec4(∂EY/∂t, ∂EI/∂t, 0, ε²)` (`cassi_two_fluid.glsl pass_b`), so the
medium genuinely has per-cell flow velocity. RealSim mode treats this as real:
viscosity couples particles to it, `a_visc = −ν·(v − v_field(p))`
(`cassi_nbody_gravity.glsl:109`).

**As a reservoir:** a rotor placed in the two-fluid flow spins — the medium does
work on it exactly as a wind turbine spins in air. Because the flow is a wave
field (two scalar channels), a "coherence turbine" in a standing-wave region is
a *standing-wave-to-rotation* converter: it rectifies the local oscillation into
torque.

### 1.3 The `ε²` budget — disorder as a resource

`ε² = (EY − φ·EI)²` is the decoherence channel, written into `vel[].w`. Where
the field loses the φ-locked Yang/Yin relation, `ε²` rises; carved/scarred
regions are exactly where `ε²` dominates (chunk-field-quantization §2.2). The
coherence-budget framing — organized vs random perturbation — makes extracting
from disorder a *real* conversion: lowering local `ε²` is doing positive work on
the field (pushing it back toward the φ-locked attractor).

**As a reservoir:** the theory's own organized-vs-random framing means disorder
is not mere absence of resource but a *barrier to work against*. A machine that
absorbs `ε²` (sinks it, draws it off) harvests the "difference from order" as
energy. **Honest caveat (§6):** this is the conversion whose stability must be
bounded — if a machine drains `ε²` but the PDE would have healed it for free,
the machine only speeds terrain healing; if it drains `ε²` in a region the field
is actively destroying, it is a *shield* that costs energy to run. It must never
be able to generate more than it consumes (no free-energy from the healing
attractor).

### 1.4 Phase-change latent energy — a condensation drive

Condensation is a threshold event: a block is solid when `ρ ≥ τ_c` with
hysteresis (`qi_condensation_threshold = 0.5`; chunk-field-quantization §2.2;
the engine's merge gate `q_sel > q_threshold` at `φ⁻²`). Dissolution is the
reverse: raise `ε²` and the block re-dissolves, the field reorganizing toward
its attractor.

**As a reservoir:** condensation *releases* coherence (a phase change from free
field to ordered matter); dissolution *absorbs* it. A controlled condensation
drive — feed density to cross the threshold, capture the released coherence;
then let the matter dissolve and re-capture it as the field draws back — is a
**latent-energy cycle**, the field-world analog of a heat pump cycling through a
phase change. It needs an input (the density to drive the condensation), so it
is a *converter*, not a source.

### 1.5 Deep-rung stored coherence — ordered matter as fuel / battery

> Forward reference: `material-regimes.md`, the companion doc being written
> concurrently. The cascade's φ-scaled organization scales mean deeper rungs =
> more ordered matter; that ordered matter is storable, withdrawable coherence.

**As a reservoir:** this is the "fuel" in the classical sense — but it is not a
fresh substance, it is *already-ordered matter*. Mining a deep-rung deposit
releases its stored coherence; *not* mining it holds that coherence as a
reserve. This links directly to storage (§3): the same ordered matter is both
the deepest fuel and the highest-capacitance battery.

### 1.6 BH accretion — deep-rung, high-yield, dangerous

The engine's BH sector accretes mass from local Qi continuously:
`mass += acc_rate · qi_local · cell_vol` (`cassi_bh_integrate.glsl:62`), and the
BH sector is the deep end of the merge lineage (`particle_merge`: dust → object
→ BH).

**As a reservoir:** a `∇(g·Φ)` well that is *still accreting* is the deepest,
highest-yield gradient in the field. Its energy density is enormous and it is
self-sustaining while it feeds. It is dangerously coupled to the field: near a
BH the same gradient that powers a harvester also shreds anything that taps it
(the river acceleration is unbounded in steepness). Harvesting a BH is a
high-capitalization, high-risk, late-game proposition.

### 1.7 Ambient cascade pumping — the attractor resonance

The two-fluid operator carries an explicit resonance, `ω₀²` (default `20.0`),
the `−ω₀²·(EY − φ·EI)` coupling that drives the fields toward the φ-locked
relation (`cassi_two_fluid.glsl:196-203`). This is the field's attractor: left
alone, the field *tends to organize*, injecting order.

**As a reservoir:** the attractor resonance is a *background source* — a machine
that sits in a region the field is naturally organizing and harvests the
resonant excess is "ambient cascade pumping". It is weak (it is the background
drift, not a steep gradient) but it is everywhere and costs nothing to find.
It is the reason a living world is a *net* energy environment rather than a
zero-sum one — but the amount must be capped (§6) so it never turns into
infinite free energy.

| Reservoir | Mechanism that taps it | Density | Phase-1 weight |
|---|---|---|---|
| `∇(g·Φ)` hydro | flux through a potential well | high, everywhere | **primary** |
| Medium KE turbine | rotor in two-fluid flow | medium, patchy | secondary |
| `ε²` budget | draw off decoherence (disorder → work) | medium, conditional | supported, capped |
| Phase-change latent | condensation/dissolution drive | medium, cyclic | secondary |
| Deep-rung coherence | mine ordered matter | high, finite | storage + late fuel |
| BH accretion | tap an accreting well | extreme, dangerous | late-game |
| Ambient resonance | harvest attractor drift | low, everywhere | background |
| **Auroral discharge** (sky doc [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) §3.4) | a collector on the field-line glow, harvesting the `(1−q)` fraction of delivered-but-rejected coherence | deep-rung, geographically pinned to drains; high where ε² wells glow | late-Phase (needs a body's field structure + auroral rendering) |

The **auroral-discharge collector** — the machine that taps this row — is owned
by the sky doc: its site geometry, yield model (scales with the drain's waste —
brighter aurora = richer harvest), and field-line rendering live in
[`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md) §3.4, not
here. It inherits this doc's §6 no-free-energy rule unchanged: it harvests only
the `(1−q)` fraction that would be wasted, is net-negative (it pays in what the
drain would have shed, never in new energy), and is *diminished as players heal
the field* — a real tension this doc does not resolve (heal the world, lose the
cheap auroral power).

---

## 2. Conversion mechanics — machines as field operations

The design rule: **no inventory generators.** A machine is a *local field
operation* — it reads the field, perturbs it (via the **Q4 player-return
channel** of `async-field-domain.md` §7 — the "write-back lane" / "player-edit
feedback lane" of the engine-gap list in `chunk-field-quantization.md` §6),
and the perturbation is what does work. A machine's
"input" slot accepts a field channel (a resource if you must attach a
word-probability to it is *EY to withdraw, ε² to channel, ∇q to steer*), never a
fire/bucket/crucible.

**The `(1−q)` waste law is the machine-loss floor.** Every working machine runs
at a coherence-dependent efficiency set by the field it sits in, not by the
machine: it wastes `E_waste = (1−q)·E_throughput` as visible glow
(idea sources: qi-bubble-propulsion.md §2.5, superconductivity-as-qi-coherence.md
§1.2; `coherence-technologies.md` concept 4). A machine in a **low-`q` region** —
a scar, a decoherence well — bleeds most of its throughput to glow; a machine on
a **coherence ridge** runs near-lossless. This is the cost *beneath* every
per-machine honest cost below: the hydraulic mill's gradient-flattening, the
turbine's damping, each add on top of the `(1−q)` floor. It is also the field's
shape made economically *legible* — the glow is the diagnostic a player reads to
find where energy actually flows.

**The wear-law at the hand (reverse pointer, two-way).** This §2's `(1−q)` waste
law is what the corpus's primitive work object reads as *tool wear*:
[`the-tool.md`](./the-tool.md) §2b designs **durability as the alloy's coherence
read through this law** — "a high-`q` low-waste alloy bites clean and lasts; a
scar-tainted alloy dulls fast," the `(1−q)` bleed read *into the edge itself* as
edge-wear (`the-tool.md` §2b — it cites this §2 as the waste law the wear rides,
and §3's charge/scar asymmetry as the deep bite's scar). A tool is the hand-scale
of this machine-loss floor; the two docs now cite each other as read-and-answered.

### 2.1 Hydraulic mill (taps `∇(g·Φ)`)

A wheel placed in a `∇(g·Φ)` well lets flux pass through it; the torque is
proportional to `|∇(g·Φ)|` integrated over the wheel's foot. The machine *reads*
the gradient from the publish (the `∇(g·Φ)` channel) and *perturbs* the local
`ρ` slightly downward on its outlet side — keeping flux flowing (a dam keeps a
head). Cost: it *flattens* the gradient it sits on over time (it consumes the
very head it needs), so mills are best near sustained condensations or on the
rim of an accreting region. Honest cost: a mill that over-withdraws starves
itself; flux stalls when `∇(g·Φ)` drops below the wheel's startup torque.

### 2.2 Coherence turbine (taps medium KE)

A rotor aligned with the local flow (`vel` channel) spins; output ∝ the kinetic
energy density `½·ρ·|v_flow|²`. It works best where the field is *moving* —
standing waves, spiral arms, the shear near a condensation drive. Cost: the
rotor *damps* the flow it taps (removing KE slows the medium), so turbines
cool the regions they power. Honest consequence: over-placing turbines can
stall the visual liveliness of the field — play-facing tension (§6).

### 2.3 Decoherence channel / suppressor (taps `ε²`)

A machine placed where `ε²` is high *sinks* it — reads `ε²`, and via the
feedback lane lowers the local `ε²` in the domain boundary term. Output ∝ the
`ε²` it removes. Cost: in a region the field is actively destroying, this is a
*shield that costs energy to run* (it resists the field's own tendency). In a
region the field would heal on its own, the machine only accelerates that
healing and is *nearly free* — which is why **the cap of §6 is mandatory**: the
design must not let a suppressor that would have been healed anyway mint energy.
Concrete gate (§6): output is capped at a fraction of what the machine itself
inputs, so a suppressor is always *net-negative* (it pays you in healing, not in
currency).

### 2.4 Condensation drive (taps phase-change latent)

A drive injects `EY` (raises local `ρ`) past `τ_c` to force a condensation,
capturing the released coherence; it can then withdraw `EY` to dissolve and
re-capture. This is a **converter**, not a source: it spends injected density to
extract the phase-change difference. Cost: a cycle that is Lossy yields less
back than it spends — the drive is only net-positive when it harvests a
looser-dissolving material than it condenses (the actual asymmetry the theory
gives via the cascade rungs — a cheap rung condenses, a deeper rung dissolves
reluctantly).

### 2.5 Deep-rung reaper (taps stored coherence)

A precision tool at a *chosen rung* (per volumetric-terrain.md) withdraws the
field at that rung, releasing the ordered matter's stored coherence. This is the
classical "mine fuel" — but it is a *withdrawal* of field, not a collected item.
Cost: removing deep rungs de-orders the local field (raises `ε²`, lowers `q`),
so reaping too deep too fast scars the terrain — the by-product is a landscape
wound, not a pile of blocks.

### 2.6 BH skimmer (taps accretion)

A high-capitalization rig on a live accreting well taps the steep gradient
without being shredded — by riding the flux already moving into the well rather
than trying to stop it. Cost: it *diverts* accelerating infall; a misread of the
well's steepness shreds the rig (the river acceleration is unbounded in
steepness). Late-game only.

| Machine | Taps | Perturbs | Honest cost |
|---|---|---|---|
| Hydraulic mill | `∇(g·Φ)` | lowers downstream `ρ` | flattens its own head; stalls if over-withdrawn |
| Coherence turbine | medium KE (`vel`) | dampens flow | cools the field it powers |
| Decoherence suppressor | `ε²` | lowers local `ε²` | net-negative; a shield costs to run |
| Condensation drive | phase-change latent | injects/withdraws `EY` | lossy cycle; only net+ across rungs |
| Deep-rung reaper | stored coherence | withdraws ordered matter | scars the terrain (raises `ε²`) |
| BH skimmer | accretion | diverts infall | shreds on a misread well |

---

## 3. Storage — coherence capacitors

Storage is **already-ordered matter.** The merge lineage is concrete:
`particle_merge` runs "dust → object → BH", with each merge conserving
mass+momentum and the survivor accumulating spin; deeper rungs = more organized
matter = more storable, withdrawable coherence (the `material-regimes.md`
companion's substance). So:

- **A capacitor is a volume of ordered matter at a rung.** Its capacity is the
  stored coherence of that rung's ordering. Rung n holds more per unit field
  than rung n−1.
- **Rung is the battery tier.** Higher-rung matter stores more and discharges
  deeper (can power deeper-rung tools, §5). It is also *harder to recharge* —
  you must re-condense it, which costs density and time.
- **The merge lineage is the growing store.** Objects are not just terrain; any
  *ordered object* (a condensed body, an artifact the field has organized) is
  a capacitor at its rung. Accumulating objects = accumulating store — the
  player literally builds a battery bank by letting the field organize matter.

**Charge/discharge asymmetry (honest):** charging (condensing to a deeper rung)
is slow and density-costly; discharging (reaping) is fast and scars. This
asymmetry is the *economic* heart of §6 — it is what makes energy a constraint
rather than a trivial tap. A maintained Qi bath (§4.4) softens the discharge
cost *regionally* — it raises the local `q` a reaper works in, cutting the
`(1−q)` glow waste — but never the scarring itself.

---

## 4. Transport — routing coherence, the range/loss model

### 4.1 High-ξ conduits (coherence routing)

The chord coupling `ξ = φ⁶` (shader constant; `ξ = φ⁶ ≈ 17.9443`, so the
`ξ − 1 ≈ 16.9443` used in the law's `g = 1 + (ξ−1)·q`) is the field's own
amplification factor toward matter. A **conduit** is a manufactured high-`q` filament that raises `ξ·q` along a path,
making that path the field's preferred channel for routing coherence. A conduit
connects source → sink by *steering ∇q*: place a conductor and coherence flows
down it instead of spreading. Cost: a conduit is itself a storage draw (it must
hold `q` up to be a channel), so it leaks while idle and needs a trickle charge
to stay live — conduits are *live infrastructure*, not passive wire.

### 4.2 Pulses along `∇(g·Φ)`

The other transport is *dynamic*: a pulse of withdrawn coherence travels along
`∇(g·Φ)`, the way a pressure wave travels down a pipe the potential gradient
defines. This is the **wire-free, long-haul** option (no filament to maintain)
but it is *directional* (always downhill in `∇(g·Φ)`, toward matter) and it
*fades*.

### 4.3 Range / loss model (concrete)

Both transports obey one loss law, chosen for consistency with the field:

```
Edelivered = Esource · exp(−α · L / λ_rung)
```

- `α` shapes the attenuation; `λ_rung` is the rung-dependent coherence length
  (deeper rungs route farther because their order decays slower).
- **Conduits** raise the effective `λ_rung` (they keep `q` up along the path),
  so the same distance costs less — but they have an up-front and idling charge.

**[assumption]** The exact `α` and `λ_rung` scale are game-tuned (the field has
no intrinsic "energy-loss-per-meter"); the *shape* — exponential-in-range, tuned
by rung and conduits — is the honest, minimal model. Phase 1 picks `α` and a
rung table so that a conduit roughly halves the loss of bare pulses, giving
transport a mechanical reason to exist without inventing arbitrary "wire
distance" numbers.

### 4.4 The Qi bath — regional efficiency multiplier

Adopted from `coherence-technologies.md` concept 4 (and the cascade-chains
framing, §5 there): a **Qi bath** is a maintained high-`q` core with a radius —
everything within it runs at its core's elevated coherence. It is *not* a new
reservoir; it is a **regional efficiency multiplier** on the reservoirs and
machines inside it. Concretely:

- Because the `(1−q)` waste law (§2) scales with local `q`, a bath's radius
  *simultaneously* raises capacitor dwell (less leakage in §3), conduit
  efficiency (longer effective `λ_rung`, §4.3), and machine throughput (less
  `(1−q)` glow) across the whole cluster — the parts are superadditive, not
  additive.
- A bath is *maintained*, not free: it is a draw (it must hold its core `q` up,
  like a conduit at larger scale), so it is a strategic building decision —
  cluster around a high-order core and the whole region runs cheaper, but the
  core itself is a standing cost that makes the cluster brittle if it goes
  down.

This is the third leg of transport's economics — with conduits (wire-like
routing) and pulses (wire-free long-haul) it is the *field-shaping* option: a
player doesn't move energy, they make a region the field itself prefers to route
through.

---

## 5. What energy does

### 5.1 Power precision tools at deeper rungs (→ volumetric-terrain.md)

The precision tools are *coherence-manipulators at a chosen rung*; tool
resolution ⇔ rung. **Energy is what lets you operate at a deeper rung than your
tool's idle capacity.** More precisely:

- Every tool has a natural (passive, ambient) rung it works at for free.
- Working at a deeper rung (finer sculpting) costs stored coherence — you must
  feed a capacitor whose rung ≥ the tool rung.
- Honest consequence: the tool language and the energy language are **the same
  scale**. To sculpt finely you must *own finely ordered matter*, which you get
  only by reaping it or by letting the field organize it. Precision and energy
  are one gradient.

### 5.2 Run vehicles / rockets (→ the KSP layer)

Vehicles and coherence-injection rockets (README Phase 2) need withdrawn
coherence as thrust/energy. Free-flight vehicles are steered by the sampler
against the local `pot` gradient; powered flight is *injecting* coherence to push
against that gradient. A rocket is a condensation drive pointed at the sky — it
spends stored coherence upward. Energy is what makes the KSP layer *go* instead
of just *fall*.

### 5.3 World-healing investment

Mining scars the field (raises `ε²`, lowers `q`); the field heals toward its
attractor on its own, but slowly. **Feeding coherence accelerates healing** —
spend stored coherence to push the local `ρ` back up / `ε²` down and the terrain
grows back faster. This is the positive, constructive sink: the player invests
energy to make the living world more alive. It is the explicit, non-zero-sum use
that makes a capacitor worth holding.

### 5.4 Anti-corruption

Where `ε²` dominates (decoherence wells, over-reaped scars, unintended
dissolution), the field de-organizes and terrain dissolves. Spending coherence
to *suppress* that `ε²` (run a decoherence suppressor with a fed source, §2.3)
holds ground against decay. Unlike healing (which adds), anti-corruption is
*preventive*: it keeps `ε²` below the dissolution threshold so blocks hold.

| Use | What it spends | Effect |
|---|---|---|
| Deeper-rung tools | capacitor at tool rung | finer sculpting, precision |
| Vehicles / rockets | withdrawn coherence | powered motion, orbit (Phase 2) |
| World healing | fed coherence | faster regeneration of scars |
| Anti-corruption | fed coherence, continuously | holds `ε²` below dissolution floor |

---

## 6. The economy question: currency, constraint, or pure enabler?

**Phase-1 recommendation: energy is a *constraint*, not a currency and not a
pure enabler.**

- **Not a currency.** Currencies require a medium of exchange (an "energy item"
  you trade). Energy here is a *field withdrawal*; it is not storable as an
  inventory token, it is stored as *ordered matter* (§3). Making it a currency
  would force exactly the block/inventory abstraction the dual-world grid wants
  to avoid, and it would invent scarcity where the field is a flowing quantity.
  Trade in *rung access* (owning ordered matter) is already the natural
  "value" — energy is the ranking beneath it, not the coin.
- **Not a pure enabler.** A pure enabler is free to use anywhere; but the
  reservoir-dependence (§2), the storage asymmetry (slow charge, fast scar),
  and the transport loss (§4) all make energy *bottleneck* real choices: where
  you build, how deep you dare scoop, what you can afford to leave unscarred.
  If it were free-enabler, the living-world tension (mine vs. let-it-organize)
  vanishes.
- **A constraint:** it shapes play by *limiting what a player can do at once,
  in a given place, with what the field has deposited*. You cannot power every
  deep-rung tool everywhere; you choose. That is the design intent.

**The one hard rule that makes this safe:** **no conversion yields more than it
sinks.** Concretely:

1. A decomposition machine's output is capped at a fraction of its input
   (**output ≤ φ⁻¹·input**, a clean cap from the theory's own ratio) so no
   reservoir becomes a net-energy mint.
2. The ambient attractor pump (§1.7) is **forbidden to charge a capacitor** —
   it may run passive machinery but never build stored currency, else the living
   field becomes a grinder.
3. The `ε²` budget (§1.3) can *pay in healing*, never in currency: a suppressor
   is net-negative and stakes its "benefit" as terrain regeneration, which the
   player must still see and choose.

These are design constraints (coded in the write-back lane's amplitude caps),
not physics claims — the theory does not forbid overdraw, so the *game* must.

| Stance | Why not for Phase 1 |
|---|---|
| Currency | forces an energy item; stranding the field's flowing character |
| Pure enabler | kills the mine-vs-organize tension; no play pressure |
| **Constraint (adopted)** | shapes where/how deep the player engages the field; the theory's own limits (charge/scar asymmetry, rung-dependent ranges) become play |

---

## 7. Honest open questions

1. **Unit/gameplay scale.** The engine's field values are unitless physics
   (`q ~ 1e-3…1e-1` at noise, `ρ ~ 1e-2…1e-1`, `φ⁻² = 0.382` threshold, `ξ−1 ≈
   16.94` — since `ξ = φ⁶ ≈ 17.94`). How do these map to "one mill puts out enough to run one tool for N
   seconds"? Needs a concrete calibration table, **assumed** here.
2. **The healing-free-energy trap (critical).** 1.3/6 assume the cap of
   "suppression pays in healing, not currency" holds; if a suppressor in a
   self-healing region reads as near-free output, is a Phase-1 player able to
   exploit it anyway (build a scar, let it heal, harvest the "excess")? Needs a
   mechanical gate, not just a stated rule.
3. **Conduit lifetime.** A conduit is a live draw (§4.1). Without a player
   maintaining real lines, do conduits meaningfully beat bare pulses at Phase-1
   box scale (192³ m, 12³ chunks)? If not, defer conduit transport to Phase 2.
4. **BH as player-accessible reservoir.** The engine accreting BHs is real
   physics, but a *skimmable* BH (§2.6) needs a safe-approach model (the river
   acceleration is unbounded in steepness). Is that Phase-1 or Phase-2 scope?
   **[assumption]** Phase-2.
5. **Cost of the write-back lane.** Every machine perturbs the domain via the
   player-edit feedback lane the companion docs flag as required-but-unbuilt. Is
   per-tick machine perturbation within the async-domain budget (the domain
   step is ~0.5–1.5 ms today, the tick ~1–6 ms)? **[assumption]** yes for a
   bounded number of active machines; measure.
6. **Determinism of machine reads.** Machines read the same immutable publish
   the tick-sampler does, so two machines can't drift. But N machines each
   pushing re-heal perturbations through the lane is N writers into the job dict
   — the single-writer rule (world-writer is the only mutator, per
   async-field-domain §5.2) constrains *game state*, not the domain input lane.
   Confirm the lane aggregates machine intents like it does player edits.

---

## 8. Feasibility verdict

**Feasible, and lightweight in the right way.** Every reservoir is a channel the
async domain already computes (or trivially publishes — `∇(g·Φ)` is the one
required snapshot addition, already flagged as needed for entity steering in
`chunk-field-quantization.md`). A harvesting machine is only a sampler-read plus
a bounded write-back perturbation — the exact pattern the seam already
prescribes (§0). The conversion idiom (machines = field operations) introduces
no new subsystem and no inventory abstraction; storage reuses the merge
lineage's own "dust → object" ordered matter; transport reuses `∇(g·Φ)` and the
chord coupling with a single tunable loss law. The one thing that would make it
a *bad* design is a net-positive conversion, and that is prevented by the single
hard rule in §6 (no conversion yields more than it sinks, encoded as amplitude
caps in the write-back lane) rather than by a fragile tuning hope. The honest
gaps — calibration table (Q1), the healing trap's mechanical gate (Q2), and a
bounded-machine perturbation budget (Q5) — are downstream measurement problems,
not architectural contradictions. Verdict: **energy as a field-strained
constraint is the right Phase-1 shape and is achievable within the already-built
async field domain.**

---

## Cross-references

Documented consumers (all relative paths):
- [`the-interstitial.md`](./the-interstitial.md) — **the dilute field.** §2a there reads
  §7 Q1 this doc's `q ~ 1e-3…1e-1` noise floor as the between's thin — a nearly-`q`-zero
  medium whose regime table has no rows; §3/§5d there holds §6 this doc's no-free-energy
  cap (the between provides nothing). Reverse pointer: the interstitial is this doc's waste
  and cap read at the field's most dilute.
- [`the-sea.md`](./the-sea.md) — **the liquid regime's power floor.** §2 this doc's
  `(1−q)` waste law and §4.1 the conduit are what the sea's carrying surface reads; §6 the
  cap ("a river carries, never powers") is inherited. Reverse pointer: the sea is this
  doc's conduit-and-waste made the vertical's middle.
- [`the-fallow.md`](./the-fallow.md) — **the one-way depletion.** §2 this doc's waste law
  read at a mined vein — `q` spent, `ε²` raised, the locality's residue — is the fallow's
  §2a spent state; §6 the cap (nothing gained from a fallow). Reverse pointer: the fallow
  is this doc's depletion made a window's economic face.
- [`the-commensal.md`](./the-commensal.md) — **the waste law's smallest grazer.** §2.2 there
  reads §2 this doc's `(1−q)` waste law at its smallest — the ordered run's negligible
  surplus a commensal grazes, never a drain; §5.4's anti-corruption (suppressing `ε²` to
  hold a region, **net-negative**) is the bounded assist it performs, and §6's
  no-free-energy cap is held (§5d there — a hold, never a mint). Reverse pointer: the
  commensal turns this doc's smallest waste into a wild companion's living.
- [`the-gift.md`](./the-gift.md) — **the gift converts nothing, never mints.** §6 there
  reads §6d's cap (`output ≤ φ⁻¹·input`) as the gift's hard bound — a gift is a transfer
  of the same coherence, never a gain; the un-booked status is a value deliberately not
  counted, never a value the book missed. Reverse pointer: the gift is this doc's cap from
  the not-booking side.
- [`the-zenith.md`](./the-zenith.md) — **the window's topmost drain.** §2a there reads §2
  this doc's waste law at the window scale — the atmosphere's `(1−q)` waste escaping the
  window at its top is the zenith's drain, slow honest readable; §6's cap is held (a
  ceiling informs, never mints — no drain that yields). Reverse pointer: the zenith names
  where this doc's already-real waste escapes the vertical's top.
- [`the-rite-of-passage.md`](./the-rite-of-passage.md) — **the cost law.** §3 there reads §2
  this doc's `(1−q)` waste (every working's floor) and §6 the no-free-energy cap (`output
  ≤ φ⁻¹·input`) — a rite is spent, never free; the rite inherits the cap as its spine.
  Reverse pointer: a rite is this doc's cap at a single being.
- [`the-loan.md`](./the-loan.md) — **the no-mint book.** §4a there reads §6 this
  doc's no-free-energy cap (`output ≤ φ⁻¹·input`) — **a loan is not a mint**, it
  informs the future, never creates it; a default is never a free gain. Reverse
  pointer: a loan is this doc's cap held over time.
- [`the-fall.md`](./the-fall.md) — **the (1−q) absence.** §2 there reads §2 this doc's
  waste law — no `(1−q)` spent mid-flight (the fall owns the gradient bare) and §6
  the no-free-energy cap (a fall converts nothing); §4.4 the Qi bath (the landing's
  absorption). Reverse pointer: a fall is this doc's waste absent, its cap held.
- [`the-swim.md`](./the-swim.md) — **the liquid-regime waste.** §2a there reads §2
  this doc's `(1−q)` waste law (the stroke's drag — the liquid regime's elevated
  waste) and §6 the no-free-energy cap (a swim converts nothing); §4.1 the field-
  hydro haul the current rides. Reverse pointer: a swim is this doc's waste law at
  stroke scale.
- [`the-cave.md`](./the-cave.md) — **the cavity's inverse.** §4 there reads §6 this
  doc's no-free-energy cap (a cave provides nothing) and §2 the `(1−q)` glow (the
  quiet cave's faint flat read); §4.4 the Qi bath (the cavity's costless-emptiness
  inverse). Reverse pointer: a cave is this doc's cap read as a hollow.
- [`the-landform-name.md`](./the-landform-name.md) — **the named land's shed.** §4.1
  there reads §2 this doc's `(1−q)` waste (the landform-name's shed — the honest
  decay is a field-shed, never a gain) and §6 the no-free-energy cap (a landform-name
  informs, never mints). Reverse pointer: a landform-name's decay is this doc's
  `(1−q)` shed at landscape scale.
- [`the-lock.md`](./the-lock.md) — **the cap, taken to permanent.** §5d there reads §6
  this doc's no-free-energy cap (`output ≤ φ⁻¹·input`) — a lock converts nothing: no
  permanence that yields; the permanent-hold is a hold never a gain; the durable mistake
  is a loss honestly booked, never a mint. Reverse pointer: a lock is this doc's cap
  made irreversible.
- [`the-marsh.md`](./the-marsh.md) — **the low-flow cost.** §2 there reads §2 this
  doc's `(1−q)` waste law (the marsh's low-flow cost, the uneven stride) and §6 the
  no-free-energy cap (a marsh provides nothing, no stealth-yield). Reverse pointer: the
  marsh is this doc's waste law at its shallow texture.
- [`the-husbander.md`](./the-husbander.md) — **the un-booked shed.** §5d there reads §2
  this doc's `(1−q)` waste law (the shed is spent, the circuit's stride cost) and §6
  the no-free-energy cap (a husbander converts nothing — never a harvest, never a
  mint). Reverse pointer: the husbander's shed is this doc's cap held as care.
- [`the-archive.md`](./the-archive.md) — **the held store.** §5 there reads §2 this
  doc's `(1−q)` waste law (the draw the Archive's hold pays) and §4.1/§4.4 the
  conduit/bath maintained-cost model; §6 the no-free-energy cap — the Archive is a
  store, never a mint. Reverse pointer: the Archive is this doc's cap held as a store.
- [`the-granary.md`](./the-granary.md) — **the held store's bleed.** §6 there reads §2
  this doc's `(1−q)` waste law (the granary's bleed) and §4.4 the Qi bath (the
  store's held high-`q` core); §6 the no-free-energy cap (a granary converts
  nothing). Reverse pointer: the granary is this doc's cap held as a store of plenty.
- [`the-wind.md`](./the-wind.md) — **the un-farmable flow.** §2 there reads §2 this
  doc's `(1−q)` waste law (the wind's glow), §2.2 the coherence turbine (the wind-
  power hook + the damping that stills the band), §1.7 the ambient pump forbidden to
  charge, §6 the no-free-energy cap (a wind provides nothing). Reverse pointer: the wind
  is this doc's waste law made a flow.
- [`the-season-change.md`](./the-season-change.md) — **the un-gained crossing.** §4.2/
  §5d there read §2 this doc's `(1−q)` waste law and §6 the cap — a turn converts
  nothing, the crossing is the field's own, never a gain. Reverse pointer: the
  season-change is this doc's cap held as a crossing.
- [`the-cart.md`](./the-cart.md) — **the free haul, the paid wear.** §1 there reads §1.1
  this doc's `∇(g·Φ)` field-hydro (the free haul the cart rides) and §4.1 the conduit;
  §2 the `(1−q)` waste law (the cart's wear); §6 the cap (a cart converts nothing).
  Reverse pointer: the cart rides the free haul and pays the wear.
- [`the-breath.md`](./the-breath.md) — **the body's bleed.** §2 there reads §2 this
  doc's `(1−q)` waste law (the body's bleed at depth) and §6 the no-free-energy rule
  — a breath converts nothing; the reservoir is a store, never a mint. Reverse pointer:
  the breath is this doc's cap held at body-scale.
- [`the-compost.md`](./the-compost.md) — **the waste and the cap.** §2 there reads the
  `(1−q)` waste law (the bleed through the turning, the worn steel, the spoiled
  surplus), §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — the compost returns order
  at a loss, never a mint). Reverse pointer: the compost holds the cap — it re-turns at
  a loss.
- [`the-carry.md`](./the-carry.md) — **the cap.** §2 there reads the `(1−q)` waste law
  (the pack's holding bleed); §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a
  carry converts nothing, no pack that yields). Reverse pointer: the carry holds the
  cap.
- [`the-climb.md`](./the-climb.md) — **the gradient and the waste.** §1.1 there reads
  `∇(g·Φ)` field-hydro; §2 the `(1−q)` waste law (the climb's per-hold cost); §6 the
  no-free-energy cap (`output ≤ φ⁻¹·input` — a climb converts nothing). Reverse
  pointer: the climb converts nothing harder, at the vertical.
- [`the-causeway.md`](./the-causeway.md) — **the deck's cost and cap.** §2 there reads the
  `(1−q)` waste law (the deck's real upkeep); §4.1 the conduit (the high-`q` filament
  the deck is); §4.4 the Qi bath / standing draw; §6 the no-free-energy cap (`output
  ≤ φ⁻¹·input` — a causeway converts nothing, no crossing that yields). Reverse
  pointer: a causeway converts nothing.
- [`the-rain.md`](./the-rain.md) — **the wet cost and the cap.** §2 there reads the
  `(1−q)` waste law (the rain's wet cost read at its fall); §6 the no-free-energy cap
  (`output ≤ φ⁻¹·input` — the rain gives back at the field's own yield, never a mint).
  Reverse pointer: the rain gives back at the field's yield, never a mint.
- [`the-spring.md`](./the-spring.md) — **the well's cap.** §2 there reads the `(1−q)`
  waste law (the well's hold wastes a little); §1.7 the ambient organizing the well
  surfaces; §6 the no-free-energy cap — a spring provides nothing beyond its own
  welling, the fixed source is the field's own, never a mint. Reverse pointer: a
  spring provides nothing beyond its own welling.
- [`the-mimic.md`](./the-mimic.md) — **the borrow's cost.** §2 there reads the `(1−q)`
  waste law (the borrow's cost); §6 the no-free-energy cap — a mimic converts nothing,
  the borrowed shape is spent never a gain. Reverse pointer: a mimic converts nothing.
- [`the-stilling.md`](./the-stilling.md) — **the voluntary hold's cost.** §2 there reads
  the `(1−q)` waste law (the held waste); §6 the no-free-energy cap (`output ≤ φ⁻¹
  ·input` — a stilling converts nothing). Reverse pointer: the voluntary hold is
  spent, never free.
- [`the-roost.md`](./the-roost.md) — **the cap.** §2 there reads the `(1−q)` waste law
  (the wild's own order a roost sits in); §6 the cap (a roost provides nothing).
  Reverse pointer: a roost provides nothing.
- [`the-dive.md`](./the-dive.md) — **the descent-tax and the cap.** §1.1 there reads
  `∇(g·Φ)` at the down-slope; §2 the `(1−q)` waste law; §4.4 the Qi bath; §6 the
  no-free-energy cap (`output ≤ φ⁻¹·input` — a dive converts nothing, never a mint).
  Reverse pointer: a dive converts nothing.
- [`the-between.md`](./the-between.md) — **the glow and the cap.** §2 there reads the
  `(1−q)` waste law (the glow that lights the between); §6 the no-free-energy cap
  (`output ≤ φ⁻¹·input` — the between provides nothing, the dark is never a gain).
  Reverse pointer: the between provides nothing; the dark is never a gain.
- [`the-beacon.md`](./the-beacon.md) — **the mark's draw and cap.** §2 there reads the
  `(1−q)` waste law (the Beacon's real upkeep); §4.4 the Qi bath / standing draw; §5.4
  anti-corruption; §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a beacon converts
  nothing, no mark that yields). Reverse pointer: a beacon converts nothing.
- [`the-shout.md`](./the-shout.md) — **the projection's cost.** §2 there reads the `(1−q)`
  waste law (the projection is the body's own signature, spent at its broadcast); §6
  the no-free-energy cap (never a gain, never a shout-mint — a shout that "pulled" help
  mechanically would be a false call the field sheds). Reverse pointer: a shout never
  mints.
- [`the-moth.md`](./the-moth.md) — **the coveting and the cap.** §2 there reads the
  `(1−q)` waste law — the visible glow that is the Moth's advertisement; §6 the
  no-free-energy cap — the Moth converts nothing, the coveting is spent, never a mint;
  §5.4 anti-corruption. Reverse pointer: a moth converts nothing.
- [`the-quarry.md`](./the-quarry.md) — **the deep-rung take.** §2 there reads the `(1−q)`
  waste law; §2.5 the deep-rung reaper (removing deep rungs de-orders the locality);
  §3 the charge/scar asymmetry; §6 `output ≤ φ⁻¹·input` (a quarry converts nothing).
  Reverse pointer: a quarry converts nothing.
- [`the-shepherd.md`](./the-shepherd.md) — **the waste and the cap.** §2 there reads the
  `(1−q)` waste law (the bright glow the crowd gathers on); §6 the no-free-energy cap (a
  Shepherd provides nothing). Reverse pointer: a shepherd provides nothing.
- [`the-desert.md`](./the-desert.md) — **the sparseness economics.** §2 there reads the
  `(1−q)` waste law (`E_waste = (1−q)·E_throughput`); §6 the no-free-energy cap (`output
  ≤ φ⁻¹·input` — a desert provides nothing beyond its own thin regime, no scarcity that
  yields); §7 Q1 the noise floor. Reverse pointer: a desert provides nothing beyond
  its own thin.
- [`the-broker.md`](./the-broker.md) — **the carry's cost.** §2 there reads the `(1−q)`
  waste law (the carry's bleed); §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a
  broker converts nothing, the trade is a transfer never a mint). Reverse pointer: a
  broker converts nothing.
- [`the-smell.md`](./the-smell.md) — **the waste read at the air.** §2 there reads the
  `(1−q)` waste law (the `(1−q)` glow is the economic signature the nose smells); §6 the
  no-free-energy cap (`output ≤ φ⁻¹·input` — a smell provides nothing, never a
  detector-mint). Reverse pointer: a smell provides nothing.
- [`the-river.md`](./the-river.md) — **the flow's cost and cap.** §2 there reads the
  `(1−q)` waste law; §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a river
  converts nothing, the current is never a mint). Reverse pointer: a river converts
  nothing.
- [`the-wage.md`](./the-wage.md) — **the cap.** §2 there reads the `(1−q)` waste law;
  §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a wage converts nothing, the
  transfer never a gain). Reverse pointer: a wage converts nothing.
- [`the-spring-caretaker.md`](./the-spring-caretaker.md) — **the clearing's cost.** §2
  there reads the `(1−q)` waste law (the clearing is a spent act); §6 the no-free-energy
  cap (`output ≤ φ⁻¹·input` — a caretaker converts nothing; the draw is spent, the
  clearing is real, never a mint). Reverse pointer: a caretaker converts nothing.
- [`the-migration.md`](./the-migration.md) — **the cap.** §2 there reads the `(1−q)`
  waste law (the moving band's glow); §6 the no-free-energy cap (`output ≤ φ⁻¹·input`
  — a migration provides nothing). Reverse pointer: a migration provides nothing.
- [`the-ford.md`](./the-ford.md) — **the waste and the cap.** §2 there reads the `(1−q)`
  waste law; §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a ford converts
  nothing, no crossing that yields). Reverse pointer: a ford converts nothing.
- [`the-estuary.md`](./the-estuary.md) — **the mixing's cap.** §2 there reads the `(1−q)`
  waste law (the mixing's loss is the field's own); §6 the no-free-energy cap (`output
  ≤ φ⁻¹·input` — the mixing feeds at the field's own yield, never a mint). Reverse
  pointer: the estuary feeds at the field's yield, never a mint.
- [`the-tutelary.md`](./the-tutelary.md) — **the cap.** §2 there reads the `(1−q)` waste
  law (the shadow's own glow); §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — the
  tutelary converts nothing, never a free shield). Reverse pointer: a tutelary
  converts nothing.
- [`the-midwife.md`](./the-midwife.md) — **the first read's cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — the midwife converts nothing, never a mint). Reverse pointer: a midwife converts nothing.
- [`the-inn.md`](./the-inn.md) — **the cap.** §2 the `(1−q)` waste law (the room’s floor shed); §4.4 the Qi bath; §5.4 anti-corruption; §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — an inn converts nothing). Reverse pointer: an inn converts nothing.
- [`the-blizzard.md`](./the-blizzard.md) — **the cover’s cap.** §2 the `(1−q)` waste law (`E_waste = (1−q)·E_throughput`); §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a blizzard converts nothing, the cover spent and gone, never a mint, never a free cloak). Reverse pointer: a blizzard converts nothing.
- [`the-understory.md`](./the-understory.md) — **the waste and the cap.** §2 the `(1−q)` waste law (the canopy’s absorption is the field’s own spent); §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — the understory converts nothing). Reverse pointer: the understory converts nothing.
- [`the-mirage.md`](./the-mirage.md) — **the composed cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a mirage converts nothing, no lure that farms to). Reverse pointer: a mirage converts nothing.
- [`the-mint.md`](./the-mint.md) — **the cap.** §2 the `(1−q)` waste law (the coin’s strike costs); §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a mint converts nothing, the coin never yields). Reverse pointer: a mint converts nothing.
- [`the-orchard.md`](./the-orchard.md) — **the yield’s cap.** §2 the `(1−q)` waste law (the grove’s steady held bleed); §6 the no-free-energy cap (“an orchard gives at the field’s own yield, never a mint”). Reverse pointer: the orchard gives never a mint.
- [`the-delta.md`](./the-delta.md) — **the fan’s cap.** §2 the waste law; §6 the no-free-energy cap (“a delta converts nothing, the spread never a mint”). Reverse pointer: a delta converts nothing.
- [`the-sledge.md`](./the-sledge.md) — **the glide’s cap.** §1.1 the field-hydro gradient; §2 the `(1−q)` waste law; §6 the no-free-energy cap (“the sledge converts nothing — no glide that yields, never a winter-mint”). Reverse pointer: a sledge converts nothing.
- [`the-raft.md`](./the-raft.md) — **the glide’s cap.** §2 the waste law; §6 the no-free-energy cap (“a raft converts nothing, no current that yields”). Reverse pointer: a raft converts nothing.
- [`the-eclipse.md`](./the-eclipse.md) — **the darkness’s cap.** §2 the waste law (the light’s spent the dimming reads); §6 the no-free-energy cap (“the eclipse converts nothing, no dark that yields”). Reverse pointer: an eclipse converts nothing.
- [`the-pooka.md`](./the-pooka.md) — **the cap.** §2 the waste law; §6 the no-free-energy cap (“a pooka converts nothing, the riling spent never a gain”). Reverse pointer: a pooka converts nothing.
- [`the-chant.md`](./the-chant.md) — **the sustain’s cap.** §2 the waste law (the chant’s sustain-spend); §6 the no-free-energy cap (“a chant converts nothing, the held voice spent never a gain”). Reverse pointer: a chant converts nothing.
- [`the-touch.md`](./the-touch.md) — **the cap.** §2 the waste law; §6 the no-free-energy cap (“a touch converts nothing, the read spent never a gain”). Reverse pointer: a touch converts nothing.
- [`the-siren.md`](./the-siren.md) — **the seduction’s cap.** §2 the waste law (the call’s real sustained spend); §6 the no-free-energy cap (“the siren converts nothing, no entrainment that yields, no seduction that mints; the call is never a hidden difficulty and never a minted charm”). Reverse pointer: the siren converts nothing.
- [`the-meadow.md`](./the-meadow.md) — **the cap.** §2 the waste law; §6 the no-free-energy cap (“a meadow converts nothing, the graze never a mint”). Reverse pointer: a meadow converts nothing.
- [`the-canal.md`](./the-canal.md) — **the directed cap.** §2 the waste law; §6 the no-free-energy cap (“a canal converts nothing, the dug lane never a mint”). Reverse pointer: a canal converts nothing.
- [`the-cistern.md`](./the-cistern.md) — **the hold’s cap.** §2 the waste law (the held water’s bleed); §6 the no-free-energy cap (“a cistern converts nothing, the drawn hold never a mint”). Reverse pointer: a cistern converts nothing.
- [`the-meteor.md`](./the-meteor.md) — **the fall’s cap.** §2 the waste law; §6 the no-free-energy cap (“a meteor converts nothing, the fall never a mint”). Reverse pointer: a meteor converts nothing.
- [`the-balefire.md`](./the-balefire.md) — **the fire’s cap.** §2 the `(1−q)` waste law (the raised flame is the field’s own spent); §6 the no-free-energy cap (“a balefire converts nothing, the warning spent never a mint”). Reverse pointer: a balefire converts nothing.
- [`the-baptism.md`](./the-baptism.md) — **the rite’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (“a baptism converts nothing, the naming spent never a mint”). Reverse pointer: a baptism converts nothing.
- [`the-palanquin.md`](./the-palanquin.md) — **the borne cap.** §2 the `(1−q)` waste law (the bearers’ labor spent, the borne body’s held cost); §6 the no-free-energy cap (“a palanquin converts nothing: no bearing that yields, never a minted seat, never a hidden privilege”). Reverse pointer: a palanquin converts nothing.
- [`the-fog.md`](./the-fog.md) — **the blur’s cap.** §2 the waste law; §6 the no-free-energy cap (“a fog converts nothing, the blur spent never a gain”). Reverse pointer: a fog converts nothing.
- [`the-drought.md`](./the-drought.md) — **the dry’s cap.** §2 the waste law; §6 the no-free-energy cap (“a drought converts nothing, the dry spent never a gain”). Reverse pointer: a drought converts nothing.
- [`the-caravan.md`](./the-caravan.md) — **the train’s cap.** §2 the `(1−q)` waste law (the train’s long glow); §6 the no-free-energy cap (“a caravan converts nothing, no organized passage that yields”). Reverse pointer: a caravan converts nothing.
- [`the-dune.md`](./the-dune.md) — **the desert’s cap.** §2 the `(1−q)` waste law (the sand the dune carries is the desert’s spent surface); §1.7 the ambient pump forbidden; §6 the no-free-energy cap (a dune converts nothing, no moving sand that yields, never a minted dune, never a hidden dune-path). Reverse pointer: a dune converts nothing.
- [`the-terrace.md`](./the-terrace.md) — **the stepped cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (output ≤ φ⁻¹·input — a terrace converts nothing, the runoff’s steps spent never a gain, never a minted terrace). Reverse pointer: a terrace converts nothing.
- [`the-votive.md`](./the-votive.md) — **the giving’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a votive converts nothing, the left order spent never a gain, never a minted offering). Reverse pointer: a votive converts nothing.
- [`the-shrine.md`](./the-shrine.md) — **the held order’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (output ≤ φ⁻¹·input — the shrine’s held order is spent, never free); §4.4 the Qi bath; §5.3/§5.4 maintenance/anti-corruption. Reverse pointer: a shrine converts nothing — held order, never free.
- [`the-lightning.md`](./the-lightning.md) — **the discharge’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a lightning converts nothing, the settled charge releasing a front never a yield, never a minted flash). Reverse pointer: a lightning converts nothing.
- [`the-crossroads.md`](./the-crossroads.md) — **the meeting’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a crossroads converts nothing, no meeting that yields, never a minted crossing). Reverse pointer: a crossroads converts nothing.
- [`the-rumor.md`](./the-rumor.md) — **the whisper’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a rumor converts nothing, the passed word spent never a gain, never a minted claim). Reverse pointer: a rumor converts nothing.
- [`the-generations.md`](./the-generations.md) — **the lineage’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a generation converts nothing, the passed order spent never a gain, never a minted lineage). Reverse pointer: a generation converts nothing.
- [`the-shaft.md`](./the-shaft.md) — **the depth’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a shaft converts nothing, the dug depth spent never a gain, never a minted shaft). Reverse pointer: a shaft converts nothing.
- [`the-hand-over.md`](./the-hand-over.md) — **the passing’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a hand-over converts nothing, the office passed spent never a gain, never a minted turn). Reverse pointer: a hand-over converts nothing.
- [`the-seacraft.md`](./the-seacraft.md) — **the craft’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a seacraft converts nothing, the sailed passage spent never a gain, never a minted craft). Reverse pointer: a seacraft converts nothing.
- [`the-whirlpool.md`](./the-whirlpool.md) — **the drain’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a whirlpool converts nothing, the spun water spent never a gain, never a minted drain). Reverse pointer: a whirlpool converts nothing.
- [`the-incantation.md`](./the-incantation.md) — **the utterance’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (an incantation never creates order from nothing, never a free spend, never a mint). Reverse pointer: an incantation converts nothing.
- [`world-difficulty.md`](./world-difficulty.md) — **the world’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a wild world’s storms convert nothing — the scaled extremes never a yield, never a minted difficulty). Reverse pointer: world-difficulty converts nothing — the dial scales the field’s own extremes, never generates order.
- [`the-tunnel.md`](./the-tunnel.md) — **the passage’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a tunnel converts nothing, the dug line spent never a gain, never a minted passage). Reverse pointer: a tunnel converts nothing.
- [`the-waterfall.md`](./the-waterfall.md) — **the fall’s cap.** §1.1 potential gradients `∇(g·Φ)` — field hydro; §2 conversion mechanics; §6 the no-free-energy cap (output ≤ φ⁻¹·input — a waterfall converts nothing, a rotor in the fall a real costed turbine with `(1−q)` waste). Reverse pointer: a waterfall converts nothing.
- [`the-crane.md`](./the-crane.md) — **the lift’s cap.** §2 conversion mechanics; §6 the no-free-energy cap (output ≤ φ⁻¹·input — a crane converts nothing, never a free hoist, the counterweight’s fall a real cost). Reverse pointer: a crane converts nothing.
- [`the-comet.md`](./the-comet.md) — **the visit’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a comet converts nothing, the return’s bright spent never a gain, never a minted omen). Reverse pointer: a comet converts nothing.
- [`the-bog.md`](./the-bog.md) — **the soak’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (a bog converts nothing, the held wet spent never a gain, never a minted ground). Reverse pointer: a bog converts nothing.
- [`the-atoll.md`](./the-atoll.md) — **the ring’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (an atoll converts nothing, the crown’s shelter spent never a gain, never a minted island). Reverse pointer: an atoll converts nothing.
- [`the-anchor.md`](./the-anchor.md) — **the hold’s cap.** §2 the `(1−q)` waste law; §6 the no-free-energy cap (an anchor converts nothing, the held mooring spent never a gain, never a minted harbor). Reverse pointer: an anchor converts nothing.
