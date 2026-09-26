# The Farm That Feeds: A Shallow Rooted Coherence Store You Tend

**Question under design:** how the food production loop closes. `mouths-eye.md`
gave eating-as-act — but nothing *grows* the food; the corpus has ore-by-`q`
precipitation (`material-regimes.md` §3) but no arable production loop. This
document designs the farm: **a shallow rooted coherence store you tend** — the
ore rule extended to a *cultivated* edible regime, so a farmer is a
**precipitation steward**: keeping the bed's `q` in the crop's band,
husbanding the bed's Qi-bath, and harvesting at the **tide-high** when the
crop's stored coherence peaks. What you harvest is field-fed, edible stored
coherence; a thin-tide farm starves unless the farmer stewards the band through
the trough. This completes the found-economy made renewable (`custom-blocks.md`
§6) and gives the tide a productive, player-facing reason to matter.

Companion documents it composes (all read, none modified):
- [`material-regimes.md`](./material-regimes.md) — **THE rule it extends.** §3
  the precipitation law (a regime precipitates where `q` accumulates above a
  band); §2 the regime table (crops as shallow-rung regimes); the `(1−q)` waste
  law §3(a).
- [`energy-harnessing.md`](./energy-harnessing.md) — **the bed's physics.** §4.4
  the Qi bath (the bed's bath, superadditive); §5.4 anti-corruption (weeding as
  a field act); §6 the no-free-energy cap (a farm cannot mint).
- [`tide-of-the-attractor.md`](./tide-of-the-attractor.md) — **the harvest
  tide.** §2 harvest (q high) vs thin (q low); §5d the tide is information and
  timing, not energy; the thin trough as the farmer's season.
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — the hint made
  arable. §5.2 "farming = field husbandry"; §2.2 life as a run the field holds (a
  crop is a run); the `(1−q)` glow as the health-meter (§5.2).
- [`mouths-eye.md`](./mouths-eye.md) — **what the harvest becomes.** Eating as a
  field act; deep-rung = intense, high-`q` = bright; a meal is a withdrawal,
  never a mint (§3.2, the `output ≤ φ⁻¹·input` cap).
- [`coherence-magic.md`](./coherence-magic.md) — **the op-record.** §5.1 the Q4
  op-schema (`{op, worldPos, rung, magnitude, sustain}`); the
  read-only-consumer discipline; the player as bounded EY injector + ε² vent.
- [`life-signal.md`](./life-signal.md) — **the ecology tie.** The maintenance
  axis §1/§3: a *maintained* lock pulses; the farm's stewardship is how the
  Life-Signal reads a crop as *maintained*, the designed distinction.
- Skimmed as needed: [`field-instruments.md`](./field-instruments.md) §2.2 (the
  Still Room — patient, coherent time clears debt; the farm is where the player
  spends that time), [`shared-ledger.md`](./shared-ledger.md) (a farm's daily
  act books on the settlement's Coherence Board).

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived): the ≈ 6 MiB publish (`q` 1 + pot 1 +
`∇(g·Φ)` 3 + ρ 1), the `64³ = 262,144` grid, `φ⁻² ≈ 0.382` (`τ_c = 0.5`), `ξ = φ⁶
≈ 17.94`, the `q ≈ 0.947` attractor, the `q ~ 1e-3…1e-1` noise floor, `dt = 0.05`,
the ≈ 1–6 ms/tick server budget, the ≈ 2,000-entity cap. Anything that extends
engine terms to a *presented* crop is flagged **[design]**; anything the engine's
real terms cannot supply today is flag **[design]**/**[assumption]**. The line —
**the precipitation law is engine-real; the crop constants, the bands, and the
harvest rule are designed and probe-calibrated** — is drawn in §7 and never
blurred.

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| The farm = ? | a **shallow rooted coherence store you tend** — a cultivated bed whose soil `q` is held inside a crop's precipitation band by the player, harvested at tide-high. |
| A crop = ? | a **shallow-rung regime** (`material-regimes.md` §2's table at crop scale): a high-`q` structure riding a maintained `q`-band in its soil; its growth is a **run the field holds** (`field-emergent-ecology.md` §2.2). |
| The farmer = ? | a **precipitation steward**: keeps the bed's `q` in the crop's band (weeding = anti-corruption), husbanding the bed's Qi-bath (§4.4), harvesting at tide-high. |
| The harvest = ? | field-fed, **edible stored coherence** (`mouths-eye.md`): deep-rung = intense, high-`q` = bright; a well-stewarded crop is bright and mild, a starved one dim and harsh. |
| The tide's role = ? | the **player-facing economy**: harvest at tide-high, starve at thin unless stewarded — the farm gives the tide a productive reason to matter beyond atmosphere and hazards. |
| Honest cap = ? | a farm **cannot mint** (`energy-harnessing.md` §6): yield is bounded by the bed's `q` and the tide; stewardship moves the yield *within* that bound. |
| Feasibility = ? | **PHASE-1-ABLE** — a cultivated precipitation band is a consumer of the existing publish + a bounded Q4 write, no new physics. |

---

## 1. The farm, stated once

> **A farm is a shallow rooted coherence store you tend.** The ore rule
> (`material-regimes.md` §3: *a vein is a region where the identity tuple's θ_c
> is exceeded not by ρ but by local q — coherence condenses into a high-`q`
> material*) is extended to a *cultivated* edible regime: **a plant is a
> shallow-rung high-`q` structure riding a maintained `q`-band in its soil.**
> The farmer is a **precipitation steward** — the bed's `q` kept in the crop's
> band, the band held against the `(1−q)` waste and the region's drift, the
> harvest taken at the peak.

The load-bearing move is the word *cultivated*. The precipitation law is
engine-real and indifferent: wherever local `q` accumulates above a band, *some*
regime precipitates (`material-regimes.md` §3). A wild ore vein and a crop are
the *same law* — the difference is that a vein precipitates where the field
happens to organize, while a **crop precipitates where a player holds the band**.
The farmer does not make coherence appear; they **tend the conditions that let
the field's own precipitation rule make food where it would otherwise make ore
— or nothing.**

Three of the corpus's existing statements are the farm's load-bearing anchors:
- **The crop is a regime, not a recipe.** A plant is `material-regimes.md` §2's
  table at crop scale: a point in `(ρ, q, ε²)` plus a constant-tuple `(ξ, ω₀²,
  θ_c, n)`. There is no "wheat block"; there is a shallow-`n` regime the field
  precipitates when the bed's `q` sits in its band.
- **Farming is field husbandry.** `field-emergent-ecology.md` §5.2 already
  names it: *"Instead of a pen, a farm is a maintained Qi bath: raise and hold a
  region's coherence, and the organisms the field precipitates there persist…
  farming is field husbandry — you tend the coherence, not the animal."* This
  document makes that hint **arable** — the pen-less "farm" (a region held above
  a coherence floor) becomes a *plot with a crop-band and a harvest clock*.
- **What you harvest is what eating is.** `mouths-eye.md` §3.2: *a meal is a
  withdrawal, never a mint.* The farm does not create food from nothing; it
  **concentrates the field's stored coherence into an edible form** the mouth
  can withdraw. A harvest is the deepest use of the found-economy
  (`custom-blocks.md` §6) — food the player *grew* rather than found, but still
  field-fed.

---

## 2. The crop as a field regime

### 2.1 What a crop IS

A crop is a **shallow-rung regime** — the material table of `material-regimes.md`
§2 at the small, fast-cycling end of the rung ladder. Three properties define it:

- **Its band** — the `q`-range within which it precipitates. This is the
  crop's identity (the mapping `q`-interval → `n`/constants is, per
  `material-regimes.md` §3's own **[assumption]**, the design's addition, grounded
  in "coherence accumulates → finer deposit").
- **Its rung** — **shallow** (`n` low). A shallow-rung structure is cheap to
  hold (low stored coherence, low `ε²`-resistance, per `material-regimes.md` §4:
  shallower rung = less ordered = faster to precipitate, quicker to dissolve). A
  crop is the *fast* end of the precipitation ladder: it forms in minutes of
  field-time where a deep ore vein would take the long cycle.
- **Its growth as a run the field holds** — `field-emergent-ecology.md` §2.2:
  life is a *run*, a configuration the field is actively maintaining. A crop is
  exactly that: as long as the bed's `q` stays in its band, the field holds the
  plant's coherence configuration against the `ε²` drain; when the band is lost
  (neglect, thin tide, over-reaping), the run ends and the plant dissolves back
  to field — a scarless crop failure, because the plant *was* field.

The crop's **stored coherence grows** the longer the run is held: the
`(1−q)` glow (`field-emergent-ecology.md` §5.2) is the plant's health-meter — a
well-maintained crop glows low and holds its lock; a starved one glows bright
and wasteful exactly as a starving creature does. **The plant's stored coherence
is the harvest; its `(1−q)` waste is the read of whether the stewarding is
working.**

### 2.2 The crop table (designed, probe-calibrated)

The **law** is engine-real; the **crop constants** are designed and
probe-calibrated against it (see §7(a)). Every crop below is a shallow-rung
regime placed on the `material-regimes.md` §2 table, its band and rung **[design]**
constants to be tuned on the Phase-1 living-terrain demo, exactly as
`field-emergent-ecology.md`'s recognition rule and `life-signal.md`'s thresholds
are probe-tuned.

| Crop | Rung `n` (shallow) | `q`-band it precipitates in (soil-coherence) | Cycle (how long the run must be held) | Harvest | Taste [design] |
|---|---|---|---|---|---|
| **Grain** | `n ≈ 0` (shallowest) | wide band, low floor — precipitates on a living plain (`q` mid, `ε²` low) | **short** — the fast, forgiving crop; holds over a normal harvest phase | stored coherence peaks at tide-high; withdraw it then | bright, mild — the tonic crop |
| **Root** | `n ≈ 1` | narrow band, **higher** floor — wants a *held* coherence, the bed's Qi-bath core | **medium** — must be held through at least one full harvest-to-thin swing to deepen | deeper stored coherence (the rung's "richer, finer" per §3) | sweet, dense — the deeper-rung table's richer end |
| **Bitter green** | `n ≈ 0` | band at the **thin edge** — precipitates where marginal `q` meets a scar's flank | medium, **fragile** — the real stewarding test; drops its band first when `q` slips | shallow, but *field-fed on a scar's edge* — eating it withdraws coherence near disorder | bitter, sharp — the crop that grows where the field is wounded, the `ε²`-adjacent flavor |
| **Deep-heart (rare)** | `n ≈ 2` | high floor, near the attractor (`q ≈ 0.947`) at a Qi-bath core | **long** — must be held through a thin trough (fallowing) to reach its depth | the deepest shallow-rung stored coherence a farm can raise | dense, sweet, cold-matched — a regime the field would rather make as ore |

The **[design]** line is explicit: the *precipitation mechanics* (does a regime
precipitate where `q` sits in a band) are the engine's real law; **which crop
occupies which band, its rung, its cycle length, and its harvest peak are
designed constants calibrated by Phase-1 probe** (the family of
`field-emergent-ecology.md` §6b's recognition parameters and `life-signal.md`'s
phase thresholds). The crop table is a *presentation* of the real precipitation
rule, not a new physics.

---

## 3. The farmer's acts

Every act is a **bounded Q4 write** (`coherence-magic.md` §5.1) — an op record
`{op, worldPos, rung, magnitude, sustain}` round-tripped into the domain as a
job-dict input — or a **read-only consumer of the publish** (the Weatherglass
family rule of `field-instruments.md` §2.1: a consumer with an idiom, never a
new channel). None touches physics state; the single-writer lane
(`async-field-domain.md` §5.2) is preserved, so a farm's ops are unforgeable
records on the settlement's stream (`shared-ledger.md` §6d).

| Act | What it is in field terms | The op it is | Cross-ref |
|---|---|---|---|
| **Weeding** | **anti-corruption** — spending fed coherence to suppress `ε²` below the dissolution floor, so the bed's `q` stays in the crop's band and nothing drains the lock. Removing what de-orders the bed (a scar's rising `ε²`, a competing high-`ε²` structure) *is* weeding. | a **bounded Q4 write** (the anti-corruption `shield`/`heal` op of `coherence-magic.md` §2; `energy-harnessing.md` §5.4) | `energy-harnessing.md` §5.4; `coherence-magic.md` §2 |
| **Husbanding** | **maintaining the bed's Qi-bath** — holding a maintained high-`q` core with a radius over the plot. The `(1−q)` waste law makes the bath **superadditive**: a shared bed (several crops, or several players') raises capacitor dwell and cuts `(1−q)` glow across the whole plot, so a tended field beats a same-size scatter. The bath is a standing draw ("brittle if it goes down", `energy-harnessing.md` §4.4). | a **sustained Q4 write** (the `{sustain}` flag of `coherence-magic.md` §5.1 — the domain holds the bath's core source until told to stop, the schema's open Q2) or a re-emitted op per job | `energy-harnessing.md` §4.4; `coherence-magic.md` §5.1 Q2 |
| **Harvesting** | **taking the crop at tide-high** — when the field is most organized (`q` high, `ε²` low, `material-regimes.md` §3 near-lossless), the crop's stored coherence peaks (`tide-of-the-attractor.md` §2 harvest row). Withdrawing it at the peak is the deep-rung reaper's act at plant scale (`mouths-eye.md` §3.1). | a **bounded Q4 write** (the meal/withdraw op of `mouths-eye.md` §3, carrying the harvest's stored coherence into the budget) | `tide-of-the-attractor.md` §2; `mouths-eye.md` §3.1/§3.4 |
| **Fallowing** | **letting the bed rest through a thin trough** — at thin tide (`q` low, `ε²` high), the crop's band is under threat; a farmer either holds the band at a cost (feeds the bath through the trough, `energy-harnessing.md` §4.4's "brittle if it goes down") or **lets it rest** — dissolves the crop's run and re-seeds at the next harvest. The farmer stewards the band *through* the thin, or the farm starves. | **fallowing is a read-only + bounded-write composite**: reading the regional-`q` trend (a consumer of the publish) to *decide* when to hold vs. rest, then a bounded dissolve/re-seed write | `tide-of-the-attractor.md` §5d (the thin floor above the desert's dissolution); `field-instruments.md` §2.2 (the Still Room's patient-time tie) |

**The act-capping statement:** every farmer's act is a **bounded Q4 write** — its
magnitude capped by the no-free-energy rule of `energy-harnessing.md` §6
(`output ≤ φ⁻¹·input` amplitude caps in the write-back lane) — or a **read-only
consumer** of the publish (reading the bed's `q`, the regional-`q` trend, the
tide phase; the Weatherglass family rule). Weeding, husbanding, and harvesting
write; **observing the bed's health and reading the tide are free reads** — a
farmer is legible through the reader/glass exactly as any other field operator
(§7(e)).

---

## 4. What you harvest

**Field-fed, edible stored coherence.** The harvest is `mouths-eye.md`'s subject
made arable: what a well-stewarded crop stores is *organized field* — the longer
and higher the bed's `q`, the deeper the crop's run holds, and the more stored
coherence the harvest carries into the eater's budget.

The **mouths-eye tie, honest:**
- **Deep-rung = intense.** A deeper crop run (root, deep-heart) holds more
  stored coherence and tastes *denser, sweeter* — but it is *harder to raise* and
  (per `mouths-eye.md` §3.3) the more a deep φ-locked store *is* explosive-primed
  if harvested wrong. The eating experience *is* the crop's field history.
- **High-`q` = bright.** A crop raised in a well-held high-`q` bed reads *bright
  and mild* on the tongue (the coherent-ridge flavor of `mouths-eye.md` §1.2); a
  starved crop — its run held against a falling bed, the `(1−q)` glow climbing —
  reads *dim and harsh* (the `ε²`-adjacent bitter). **The flavor IS the field
  history**: a player can taste whether the crop was stewarded or abandoned,
  exactly as `mouths-eye.md` §5.3's connoisseur reads a vintage.

**The honest cap — a farm cannot mint.** This is `energy-harnessing.md` §6
inherited unchanged, through the farm's *and* the meal's route:
- The farm **cultivates what the field provides** — it holds a `q`-band so the
  precipitation rule concentrates existing coherence into a crop; it does not
  create coherence. The ambient attractor drift (`energy-harnessing.md` §1.7)
  that every organized region rides is present, but **forbidden to charge a
  capacitor** (a farm cannot store a tide as wealth) and capped by
  `output ≤ φ⁻¹·input`.
- A harvest is a **withdrawal** (`mouths-eye.md` §3.2): it takes *already-ordered*
  stored coherence out of the plant into the eater's budget, de-ordering the
  plant (death → dissolve), minus the `(1−q)` toll of the meal.
- **Yield is bounded by the bed's `q` and the tide.** At harvest tide, a
  well-held bed yields richly (the field is organized, near-lossless); at thin
  tide, the same bed yields less and wastes more. **The player's stewardship
  moves the yield within that bound** — a badly-tended bed yields its bound's
  minimum, a well-stewarded one its maximum — but nothing the farmer does lifts
  the bound itself. There is **no free-energy from farming**, exactly as there
  is none from hazard-farming or tide-farming (`tide-of-the-attractor.md` §5d).

---

## 5. The tide's productive face

The corpus already knows the tide in the atmosphere (`atmosphere-orbits-auroras.md`:
the sky breathes, auroras brighten) and in the hazards (`field-hazards.md`: the
desert takes at the trough, storms ride the decohered field). **The farm is the
tide's first productive, player-facing economy** — the place where the season's
rhythm *gives* rather than merely threatens:

| Tide phase | The farm | The player |
|---|---|---|
| **Harvest** (`q` high, `ε²` low, near-lossless) | crops' stored coherence **peaks**; the bed's band is cheapest to hold; the `(1−q)` waste floor is small — the harvest is rich | **harvest the harvest** (`tide-of-the-attractor.md` §3.2): the deep-rung reaper's act at plant scale is a harvest-tide act |
| **Thin** (`q` low, `ε²` high, wasteful) | the crop's band is under threat; the `(1−q)` toll on every harvest rises; fallow dissolves the run; the desert-margin creeps (`field-hazards.md` §3) | **the farmer's season** — the patient-field tie (`field-instruments.md` §2.2: patient, coherent time clears debt — a farm is where that time is spent): read the trend, husband the bath through, or fallow and wait |

**The thin trough is the farmer's season — not a wipe, but a *calendar*.** A
farm is the corpus's closest thing to the Still Room (`field-instruments.md`
§2.2) made productive: the same *patient, coherent time that clears debt* is
what lets a crop's run deepen (root, deep-heart) and what a well-stewarded bed
spends to survive a thin trough. The tide's trough is **designed to read as
*wasteful*, not *deserted*** (the thin floor must sit above the desert's
dissolution threshold, `tide-of-the-attractor.md` open-Q3) — and a farm is where
the difference is most visible: **a stewarded bed holds its crop through the
thin; a neglected one starves.** That is the tide given a reason to matter.

**No free-energy from the tide's gift.** `tide-of-the-attractor.md` §5d is
inherited unchanged: the harvest is the field's *organized state*, not a mint. A
farm does not "harvest a high tide for free power" — it withdraws stored
coherence the field actually organized, at the `(1−q)` floor, bounded by the
bed's `q`. **The tide's gift to the farmer is information and timing, not
energy** — exactly the doc's own words, applied to the food loop.

---

## 6. Completing the found-economy made renewable

`custom-blocks.md` §6 splits the economy into *found* (cheap, read-only, bounded
by what the field has made) and *invented* (expensive, spent coherence,
unbounded within the realizable space). The farm is the corpus's first
**renewable found-economy**: a found regime (the crop) that the player *grows at
the source* rather than finds in the wild, harvested and re-seeded on the tide's
cycle.

- **It does not invent new food.** A crop is a regime the field's precipitation
  rule already makes (it is just that, in the wild, the same `q`-band makes a
  vein or a transient edible instead of a farmed plot). The farm concentrates
  what the field provides; it does not author a new material (`custom-blocks.md`
  §3's *realizability is contextual* holds — a farmed crop is a regime the local
  field state actually holds).
- **It books on the settlement's ledger.** Every farmer's act is a Q4 record on
  the single-writer stream; `shared-ledger.md` §1.2 classifies the ops directly:
  weeding/husbanding = the `heal`/anti-corruption class (a **contribution** — it
  feeds the shared high-`q` core, the bath), a deep over-reap = a **drain**. A
  farmer who stewards a bed through a thin tide is literally
  **steward-of-the-tide** (`shared-ledger.md` §2.2) — the settlement's Board
  shows the farmer's contribution as a recognized, bounded achievement. **The
  steward-of-the-tide's daily act is a harvest.**

---

## 7. Honest gates

### (a) The [design]/engine-real line

| Claim | Status |
|---|---|
| A regime precipitates where local `q` accumulates above a band (`material-regimes.md` §3) | **engine-real** — the precipitation law; the condensation scanner's `q`-threshold nucleation |
| The band → crop mapping (which `q`-interval precipitates which shallow-rung regime), the crop's rung, cycle length, and harvest peak | **[design]** — the crop constants, Phase-1 probe-calibrated (the family of `field-emergent-ecology.md` §6b and `life-signal.md` thresholds) |
| The `(1−q)` waste law, the Qi-bath superadditivity, the no-free-energy cap (`output ≤ φ⁻¹·input`) | **engine/theory-real** — inherited unchanged from `energy-harnessing.md` §2/§4.4/§6 |
| The eating experience (deep-rung = intense, high-`q` = bright) | **[design]** — `mouths-eye.md`'s taste-map, itself [design] over real channels |

### (b) Phase-1-able: a cultivated precipitation band

A farm is a **consumer of the existing publish + a bounded Q4 write — no new
physics.** It:
- **reads** the bed's `q`/`ε²` and the regional-`q` trend from the ≈ 6 MiB
  publish the sampler already consumes (the ≈ 1–6 ms/tick budget,
  `corpus-reconciliation.md`);
- **writes** weeding/husbanding/harvest ops through the Q4 lane
  (`coherence-magic.md` §5.1), amplitude-capped by §6's no-free-energy rule;
- **Phase-1 demo:** hold a plot's `q` in the crop's band (weed the `ε²`, hold the
  bath) and harvest at the high — the exact consumer+bounded-write pattern the
  Weatherglass (`field-instruments.md` §6) and the ecology's precipitation demo
  (`field-emergent-ecology.md` §7) already prove. No new engine code.

### (c) Determinism — a hard gate

> **Same bed state, same tide → same yield.** The field is deterministic (one
> PDE; `life-signal.md` §6d's hard gate); the farm's yield is a pure function of
> the bed's published `q`/`ε²` over the crop's run and the tide phase, with no
> hidden randomness. A reloaded bed at the same field state and the same tide
> yields the same harvest, every time. This is what makes a farm *trustworthy
> as husbandry* — the player's acts map deterministically to the yield, so
> stewardship is a learned, honest skill.

### (d) The no-free-energy cap — no minting, stated

A farm **cannot mint** (`energy-harnessing.md` §6); it *cultivates* what the
field provides. State it plainly: **no yield exceeds what the bed's `q` and the
tide bound; `output ≤ φ⁻¹·input` amplitude caps hold the write-back lane; the
ambient attractor drift is forbidden to charge a planted store; a harvest is a
withdrawal, never net-positive.** The farm is a *stewardship economy*, not a
generator.

### (e) The accessibility rule — the bed's health is readable

The bed's `q`/`ε²` and the `(1−q)` glow are published channels; **the bed's
health is readable from the reader/glass, never hidden-only.** A farmer reads
the crop's stored coherence, the bed's band, and the tide phase through the
existing instruments (`coherence-magic.md` §2 Sense; `field-instruments.md` §1.2
Weatherglass — the lume/glow/waste-tint vocabulary), with the `(1−q)` glow as the
health-meter (`field-emergent-ecology.md` §5.2). This is the triad/accessibility
rule of `field-music.md` §6 and `mouths-eye.md` §2.1: **the farm is an
enhancement of the shared publish, never a hidden-only or only-channel mechanic.**
A player who never farms loses nothing the corpus gives; a player who farms
reads the same field the instruments already show.

### (f) The ecology tie — cultivated, not wild

A farm must **not read as a wild precipitate.** The precipitation law makes ore
veins and transient edibles wherever `q` accumulates; a farm is the *same law*
under active stewardship. The distinction is the **Life-Signal's maintenance
axis** (`life-signal.md` §1/§3):

- A **wild precipitate** (ore vein, transient edible) reads as *unmaintained* —
  a static `q`-locked store with no lock-maintenance cadence (`life-signal.md`
  §3.1's static-residue class).
- A **crop** reads as *maintained* — its `(1−q)` glow **pulses at the
  steward's cadence** (the farmer's weeding/husbanding writes keeping the band
  held, exactly the maintained-lock signature of `life-signal.md` §3). The
  Life-Signal's maintained axis is the **designed distinction** that tells a
  farm from a vein: **a farm is a *cultivated* run of the field — the farmer's
  stewardship is literally a lock they are actively holding**, and the
  maintenance read sees it.

This is a *designed* distinction (the maintenance axis is itself [design] over
real channels, `life-signal.md` §6a), and it is load-bearing: it is what lets the
tide's harvest rule apply only to farmed crops, and what lets stewardship be
*recognized* (contributing to the ledger, feeding the bath) rather than
indistinguishable from a field event.

---

## 8. Open questions

1. **The crop-band calibration.** Where exactly does a shallow-rung `q`-interval
   precipitate a crop vs. an ore vein vs. nothing (`material-regimes.md` §3's
   band→material rule, at crop scale)? Phase-1 probe on the living-terrain demo —
   the same calibration family as `energy-harnessing.md` §7 Q1's unit-scale
   problem, applied to agriculture.
2. **Thin-trough fallow timing.** At what `q`/trend reading does a farmer *must*
   fallow vs. *can* husband the band through? This is the farm's own instance of
   `tide-of-the-attractor.md`'s thin-floor (must read *wasteful*, never cross
   into the desert's *deserted*); the hold-vs-rest boundary is probe-tuned.
3. **The `{sustain}` vs re-emit settle.** Husbanding the bath wants the sustain
   flag (`coherence-magic.md` §5.1 Q2; `shared-ledger.md` §4.1) so a sustained
   farmer books cleanly as a contribution rather than a spam-reemitter; if
   re-emit wins, the farm's ops still work but the ledger reads noisier. Open
   until Q4 settles.
4. **Harvest peak detection.** The harvest *tide* is the regional `q` trend
   (measured per `tide-of-the-attractor.md` §5a's probe); the *crop's* stored-
   coherence peak within that phase — how close to the tide's apex a plant must
   be taken to get a "well-stewarded" (bright, mild) harvest vs. a thin one — is
   a designed window over the crop's run, probe-calibrated.

---

## 9. Feasibility verdict

**PHASE-1-ABLE — the fastest concrete win in the batch.**

The farm completes the corpus's food-production loop (the one act `mouths-eye.md`
left ungrown), gives the tide a **productive**, player-facing reason to matter
(the harvest economy, distinct from the tide's atmospheric and hazard faces), and
is a **pure consumer + bounded-write design**:
- **reads** the published `q`/`ε²`/regional-`q` trend and the `(1−q)` glow (the
  ≈ 6 MiB publish, the ≈ 1–6 ms/tick budget — cited, not re-derived);
- **writes** weeding/husbanding/harvest ops through Q4, capped by
  `energy-harnessing.md` §6's no-free-energy rule;
- **no new physics, no new channel, no new engine code.**

Its Phase-1 demo is the smallest useful slice of the whole thesis: **hold a
plot's `q` in the crop's band (weed the `ε²`, husband the bath) and harvest at
the high** — the exact consumer+bounded-write pattern the Weatherglass and the
ecology's precipitation demo already prove, on the already-built async field
domain. It closes the found-economy made renewable, ties the tide to food, and
gives the farmer a stewardship skill the deterministic field makes honest.

**Binding risks, in order:** **(a)** the crop-band calibration (§8.1) — whether
the precipitation law, probe-tuned, reliably precipitates a crop where a farmer
holds the band (the design's grounded premise); **(b)** the harvest-peak window
(§8.4) — whether "harvest at tide-high" reads cleanly in field terms; **(c)** the
no-free-energy gate held against "farm a high tide for free power"
(`tide-of-the-attractor.md` §5d, inherited); **(d)** the cultivated-vs-wild
distinction's Honesty (§7f) — the maintenance read must keep a farm from reading
as a vein. **None contradicts the async, dual-world, or regime-collapse
architecture** — the farm adds no physics; it reads the field the world already
publishes and writes a bounded op the world already executes, completing the
loop that eating opened.

---

## Cross-references

- [`material-regimes.md`](./material-regimes.md) — **§3 the precipitation law** (a
  regime precipitates where `q` accumulates above a band) — the farm's physics; **§2
  the regime table** (crops as shallow-rung regimes); §3(a) the `(1−q)` waste law; §4
  hardness = rung (a shallow crop = cheap to hold, quick to cycle).
- [`energy-harnessing.md`](./energy-harnessing.md) — **§4.4 the Qi bath** (the bed's
  bath; maintained, superadditive, a draw); **§5.4 anti-corruption** (weeding as a
  field act); **§6 the no-free-energy cap** (`output ≤ φ⁻¹·input` — a farm cannot mint);
  §2 the `(1−q)` waste as the crop's glow/health-meter.
- [`tide-of-the-attractor.md`](./tide-of-the-attractor.md) — **§2 the harvest tide**
  (when the crop's stored coherence peaks) and the thin trough (when a farm starves
  unless stewarded); §3.2 harvest-the-harvest; §5d the tide's gift is information and
  timing, not energy.
- [`field-emergent-ecology.md`](./field-emergent-ecology.md) — **§5.2 the "farming =
  field husbandry" hint made arable**; §2.2 life as a run the field holds (a crop is a
  run); the `(1−q)` glow as health-meter (§5.2).
- [`mouths-eye.md`](./mouths-eye.md) — **what the harvest becomes**: eating as a field
  act; deep-rung = intense, high-`q` = bright (§1.2/§4.3); a meal is a withdrawal,
  never a mint (`output ≤ φ⁻¹·input`, §3.2).
- [`coherence-magic.md`](./coherence-magic.md) — **§5.1 the Q4 op-schema**
  (`{op, worldPos, rung, magnitude, sustain}`) every farmer's act is a consumer of;
  the read-only-consumer discipline; Q2 the `{sustain}` flag (husbanding's open settle).
- [`life-signal.md`](./life-signal.md) — **§1/§3 the maintenance axis** (a maintained
  lock pulses; the farm's stewardship is how a crop reads as *maintained*, the designed
  distinction from a wild precipitate); §6d determinism (hard gate).
- [`field-instruments.md`](./field-instruments.md) — **§2.2 the Still Room** (the
  farm's quiet-time cousin — patient, coherent time clears debt); §2.1 the family rule
  (a farmer's reads are consumers of the publish, never a new channel); §1.2 the
  bed-health reads.
- [`shared-ledger.md`](./shared-ledger.md) — **a farm's contribution books on the
  settlement's Coherence Board** as `C(M)` per tide (§1.2); the farmer = the
  steward-of-the-tide's daily act (§2.2); §4.1 the `{sustain}`/re-emit settle's social
  weight.
- [`custom-blocks.md`](./custom-blocks.md) — **§6 the found-economy** (the farm is a
  *renewable* found-economy — it grows a found regime at the source, never invents new
  food); §3 realizability is contextual (a farmed crop is a regime the local field
  actually holds).
- [`the-loan.md`](./the-loan.md) — **the repayment.** §2.1 there reads §4 this doc's
  harvest — the farm's yield is the loan's natural repayment, the forward order's
  honest end. Reverse pointer: the farm feeds the loan's due.
- [`the-husbander.md`](./the-husbander.md) — **the anti-owner.** §3 there reads §2/§4
  this doc's crop and harvest — the farm makes the field *yield*; the husbander makes
  it *remain* (§3 there); §6 the farm books on the ledger (the husbander's care books
  nothing). Reverse pointer: the husbander is the farm's inverse, the anti-owner.
- [`the-granary.md`](./the-granary.md) — **the yield held.** §4 there reads §2 this
  doc's crop band and the harvest (the granary's first store — a shallow-rung
  regime), §5 the tide-high harvest vs. the thin, §6 a harvest books on the ledger, §7
  the honest gates. Reverse pointer: the granary is the farm's yield held through the
  thin.
- [`the-season-change.md`](./the-season-change.md) — **the harvest before the band
  dies.** §3.2 there reads §5 this doc's harvest/thin table and §2.2 the crop-band —
  the farm's action at the turn: harvest before the band dies. Reverse pointer: the
  farm's harvest is timed to this doc's turn.
- [`the-compost.md`](./the-compost.md) — **the plot's feed.** §2 there reads the crop
  band (the depleted bed the feed restores toward), §4 the yield law *yield ≤ bed's q +
  the tide* (the bound the compost's feed never lifts), §5 the thin trough. Reverse
  pointer: the compost feeds the farm's depleted bed.
- [`the-rain.md`](./the-rain.md) — **the season's water.** §2 there reads the crop as
  a shallow-rung regime precipitating where the bed's `q` sits in a band; §5 the
  harvest's dependence on the season's water (the thin trough starves, the
  harvest-tide peaks); §3 the farmer's bounded Q4; §4 the yield bounded by the bed's
  `q`. Reverse pointer: the rain feeds the farm's bed at the season's yield.
- [`the-desert.md`](./the-desert.md) — **the sparse crop.** §2 there reads the crop as
  a shallow-rung regime; §4 the harvest bound; §5 the thin trough as the farmer's
  season. Reverse pointer: the desert's sparse farm still could feed, thinly.
- [`the-smell.md`](./the-smell.md) — **the hearth's smoke.** §2 there reads the crop's
  band; §5 the tide's harvest. Reverse pointer: a settlement's hearth-smoke from over
  the hill is the waked hearth's own maintained-coherence read on the air.
- [`the-river.md`](./the-river.md) — **the fertile bank.** §2 there reads the crop
  band; §3 the farmer's bounded writes; §4 the harvest bound; §5 the stewardship.
  Reverse pointer: the river's bank is the farm's fertile soil following the
  water.
- [`the-wage.md`](./the-wage.md) — **the first work paid.** §2/§3 there reads the plot
  and the farmer's bounded writes; §4 the harvest is stored coherence; §7 a farm
  cannot mint. Reverse pointer: the wage prices the first work, a withdrawal never a
  farm-mint.
- [`the-orchard.md`](./the-orchard.md) — **the slow end of the crop ladder.** §2 the shallow-rung crop (the orchard’s standing trees are the slow end); §3 the keeper’s shared lane; §4 “a farm cannot mint”; §5 the harvest/thin table (the orchard gives *across* the turn). Reverse pointer: the orchard is the farm’s slow, standing end of the crop ladder.
- [`the-meadow.md`](./the-meadow.md) — **the open common.** §2 the crop band; §3 the farmer’s bounded writes (the meadow’s keeping books nothing); §4 the harvest (a withdrawal never a mint); §5 the farm’s fallow; §6 the found-economy. Reverse pointer: the meadow is the farm’s open common — the graze the crop-fields cannot hold.
- [`the-terrace.md`](./the-terrace.md) — **the stepped crop-band.** §2 the crop as a shallow-rung regime; §3 the farmer’s bounded Q4 writes; §4 the harvest as stored coherence; §5 the tide’s harvest/thin; §7b the Phase-1 band gate; §7e the bed-health; §9a the binding risk inherited at the slope. Reverse pointer: the terrace is the farm’s steps at the slope — a stepped crop-band that holds the same lane.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical numbers
  (the ≈ 6 MiB publish, the 64³ grid, `φ⁻² ≈ 0.382`, `ξ = φ⁶ ≈ 17.94`, the `q ≈ 0.947`
  attractor, `q ~ 1e-3…1e-1` noise, `dt = 0.05`, the ≈ 1–6 ms/tick budget, the ≈ 2,000
  entity cap); cited, not re-derived.
