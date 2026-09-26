# CassiCraft Corpus Reconciliation

Consistency audit of the CassiCraft design corpus, performed against the shared
engine-grounded number set and the cross-doc ownership map. Small additive
fixes only — no restructures, no content rewrites, no new design.
`custom-blocks.md` was audited read-only (owned by a concurrent workstream); the
six wave 7–8 docs (`world-seams`, `field-archaeology`, `field-hazards`,
`resonance-seeds`, `field-music`, `field-npc-ai`), the three wave-9 docs
(`field-instruments`, `tide-of-the-attractor`, `player-remains`), the nine
wave 10–12 docs (`deep-field-diving`, `pocket-cosmos`, `the-reading-ahead`,
`signature-predator`, `resonance-tutor`, `mouths-eye`, `life-signal`,
`reason-field`, `shared-ledger`), and the six wave 13–14 docs
(`weather-not-storm`, `patient-field`, `fate-of-a-window`, `schema-that-settles`,
`house-that-steers`, `farm-that-feeds`), the three wave-15 docs
(`coherence-highway`, `wound-remembered`, `the-burden`), and the seven wave-16/17
docs (`the-name`, `sleep`, `the-map`, `seed-garden`, `the-chronicle`,
`worn-field`, `window-guests`), the four wave-18 docs (`the-inheritance`,
`the-festival`, `the-clock`, `the-mirror`), the six wave-19/20 docs
(`the-funeral`, `the-cooked-field`, `the-cold`, `the-exile`, `the-election`,
`the-bell`), the seven wave-21/22 docs (`the-silence`, `the-observatory`,
`the-apprenticeship`, `the-family`, `the-flood`, `the-treaty`, `the-lantern`),
the seven wave-23/24 docs (`the-seeker`, `the-child`, `the-echo`,
`the-stillness`, `the-oath`, `the-healer`, `the-compass`), the four wave-25
docs (`the-memory-palace`, `the-language`, `the-census`, `the-threshold`), the
three wave-26 docs (`the-blight`, `the-window-year`, `the-hourglass`), and the
four wave-27 docs (`the-walk`, `the-fallow`, `the-pilgrim`, `the-tide-staff`)
are audited across these revisions.
The three wave-28 docs (`the-sea`, `the-tool`, `the-vigil`), the four wave-29
docs (`the-working-song`, `the-feral-instrument`, `the-atlas-of-windows`,
`the-drift-road`), the three wave-30 docs (`the-scar-lifecycle`,
`the-interstitial`, `the-market`), the four wave-31 docs (`the-scavenger`,
`the-school`, `the-sea-floor`, `the-dawn`), the three wave-32 docs
(`the-commensal`, `the-gift`, `the-dispute`), the four wave-33 docs
(`the-window-pulse`, `the-zenith`, `the-stratum-read`, `the-harbor`), the
three wave-34 docs (`the-story`, `the-rite-of-passage`, `the-mirror-creature`),
the four wave-35 docs (`the-loan`, `the-fall`, `the-swim`, `the-bedrock`), the
three wave-36 docs (`the-cave`, `the-landform-name`, `the-witness`), and the
the four wave-37 docs (`the-lock`, `the-commons-tithe`, `the-marsh`, `the-husbander`),
and the three wave-38 docs (`the-guardian`, `the-archive`, `the-granary`), and
the four wave-39 docs (`the-wind`, `the-season-change`, `the-cart`, `the-breath`),
and the three wave-40 docs (`the-herald`, `the-toll`, `the-compost`), the
four wave-41 docs (`the-carry`, `the-climb`, `the-gatekeeper`, `the-causeway`),
the three wave-42 docs (`the-rain`, `the-spring`, `the-mimic`), the
four wave-43 docs (`the-stilling`, `the-roost`, `the-dive`, `the-between`), and
the three wave-44 docs (`the-beacon`, `the-shout`, `the-moth`), the four
wave-45 docs (`the-quarry`, `the-shepherd`, `the-archivist`, `the-desert`), and
the three wave-46 docs (`the-broker`, `the-smell`, `the-river`), and the
three wave-47 docs (`the-wage`, `the-spring-caretaker`, `the-migration`), and
the three wave-48 docs (`the-ford`, `the-estuary`, `the-tutelary`), and the
three wave-49 docs (`the-midwife`, `the-inn`, `the-blizzard`), and the
three wave-50 docs (`the-understory`, `the-mirage`, `the-mint`), and the
three wave-51 docs (`the-orchard`, `the-delta`, `the-sledge`), and the
three wave-52 docs (`the-raft`, `the-eclipse`, `the-pooka`), and the
three wave-53 docs (`the-chant`, `the-touch`, `the-siren`), and the
three wave-54 docs (`the-meadow`, `the-canal`, `the-cistern`), and the
three wave-55 docs (`the-meteor`, `the-balefire`, `the-baptism`), and the
four wave-56 docs (`the-palanquin`, `the-fog`, `the-drought`, `the-caravan`), the
three wave-57 docs (`the-dune`, `the-terrace`, `the-votive`), the
three wave-58 docs (`the-shrine`, `the-lightning`, `the-crossroads`), the
three wave-59 docs (`the-rumor`, `the-generations`, `the-shaft`), the
three wave-60 docs (`the-hand-over`, `the-seacraft`, `the-whirlpool`), and the
two user-requested docs (`the-incantation`, `world-difficulty`), and the
seven final-wave docs (`the-tunnel`, `the-waterfall`, `the-crane`, `the-comet`,
`the-bog`, `the-atoll`, `the-anchor`)
are **all audited and their reverse pointers added (fix 27 for waves 28–31, fix 28
for wave 32, fix 29 for wave 33, fix 30 for wave 34, fix 31 for wave 35, fix 32
for wave 36, fix 33 for wave 37, fix 34 for wave 38, fix 35 for wave 39, fix 36
for wave 40, fix 37 for wave 41, fix 38 for wave 42, fix 39 for wave 43, fix 40
for wave 44, fix 41 for wave 45, fix 42 for wave 46, fix 43 for wave 47, fix 44
for wave 48, fix 45 for wave 49, fix 46 for wave 50, fix 47 for wave 51, fix 48
for wave 52, fix 49 for wave 53, fix 50 for wave 54, fix 51 for wave 55, fix 52
for wave 56, fix 53 for wave 57, fix 54 for wave 58, fix 55 for wave 59, fix 56
for wave 60, fix 57 for the user-requested docs, fix 58 for the final wave)** — the
wave-28/29/30/31/32/33/34/35/36/37/38/39/40/41/42/43/44/45/46/47/48/49/50/51/52/
53/54/55/56/57/58/59/60 set plus the two user-requested docs plus the seven
final-wave docs now reads two-way against its ~1401 source edges (see the audit
table and the fixes log;
the swim↔fall two-way special item is landed under fix 31; the climb↔carry two-way
write-race is landed under fix 37; the rain↔spring two-way write-race is landed
under fix 38; the beacon↔moth two-way special item is landed under fix 40; the
river↔ford two-way write-race is landed under fix 44; the cart's the-camp open-Q6
honest negative is recorded, not forced).
`field-emergent-ecology`, `atmosphere-orbits-auroras`, and `ksp-kernel` are
earlier-wave docs the wave 7–31 set cross-references and are left to their own
pass. **Count note (kept current, pass-47 — PROGRAM FINAL):** at the t21 completion the
corpus is **COMPLETE** — **199 README rows / 200 on-disk design files, zero ghost
rows** (the verified live count; every indexed row resolves on-disk; the seven
final-wave docs — the-tunnel, the-waterfall, the-crane, the-comet, the-bog, the-atoll,
the-anchor — are now indexed in README and audited two-way this pass). **One single
on-disk doc has no README row** — corpus-map — the lone un-indexed arrival, an
un-audited new arrival (neither a ghost nor a double); its audit remains blocked on
indexing. **The count and the *audit* are now both complete**: every indexed design
doc is audited two-way; all 7 final-wave docs (fix 58), all 14 t20 docs (fixes
53–57), and the full waves-7–60 sweep are landed. On the wave-57 pass the
dune/terrace/votive re-point sets (fixes log 53), plus the ledger; on the wave-58
pass the shrine/lightning/crossroads re-point sets (fixes log 54), plus the ledger;
on the wave-59 pass the rumor/generations/shaft re-point sets (fixes log 55), plus
the ledger; on the wave-60 pass the hand-over/seacraft/whirlpool re-point sets
(fixes log 56), plus the ledger; on the t20 pass the incantation/world-difficulty
re-point sets (fixes log 57); on the final t21 pass the
tunnel/waterfall/crane/comet/bog/atoll/anchor re-point sets (fixes log 58),
completing the corpus reconciliation program — the last reconcile pass of the
program — plus the ledger.
On the wave-19/20 pass the design-doc edits were the five wave-19/20 re-points
(fixes log 21), plus the ledger itself; the wave-19 audit note queued in the
prior pass (the funeral as the festival's mourning twin) is **now closed by the
landed `the-funeral`** and its reverse pointer in `the-festival.md` §4 (fix 21).
On the wave-21/22 pass the design-doc edits were the eight wave-21/22 re-points
(fixes log 22), plus the ledger itself. On the wave-23/24 pass the design-doc
edits were the seven wave-23/24 re-points (fixes log 23), plus the ledger itself.
On the wave-25/26 pass the design-doc edits were the wave-25/26 re-points
(fixes log 24), plus the ledger; on the wave-27 pass the pilgrim↔walk correction
and the wave-27 re-points (fixes log 25), plus the ledger; on the wave-28 pass
the-sea and the-tool re-points (fixes log 26), plus the ledger; on the
wave-28-vigil/29/30/31 pass the remaining twelve re-point sets (fixes log 27),
plus the ledger; on the wave-32 pass the commensal/gift/dispute re-point sets
(fixes log 28), plus the ledger; on the wave-33 pass the pulse/zenith/stratum-read/
harbor re-point sets (fixes log 29), plus the ledger; on the wave-34 pass the
story/rite-of-passage/mirror-creature re-point sets (fixes log 30), plus the
ledger; on the wave-35 pass the loan/fall/swim/bedrock re-point sets (fixes log
31), including the swim↔fall two-way special item, plus the ledger; on the
wave-36 pass the cave/landform-name/witness re-point sets (fixes log 32), plus
the ledger; on the wave-37 pass the lock/tithe/marsh/husbander re-point sets
(fixes log 33), plus the ledger; on the wave-38 pass the
guardian/archive/granary re-point sets (fixes log 34), plus the ledger; on the
wave-39 pass the wind/season-change/cart/breath re-point sets (fixes log 35),
plus the ledger; on the wave-40 pass the herald/toll/compost re-point sets
(fixes log 36), plus the ledger; on the wave-41 pass the carry/climb/gatekeeper/
causeway re-point sets (fixes log 37), including the climb↔carry two-way, plus the
ledger; on the wave-42 pass the rain/spring/mimic re-point sets (fixes log
38), including the rain↔spring two-way, plus the ledger; on the wave-43 pass the
stilling/roost/dive/between re-point sets (fixes log 39), plus the ledger; on the
wave-44 pass the beacon/shout/moth re-point sets (fixes log 40), including the
beacon↔moth two-way special item, plus the ledger; on the wave-45 pass the
quarry/shepherd/archivist/desert re-point sets (fixes log 41), plus the ledger; on
the wave-46 pass the broker/smell/river re-point sets (fixes log 42), plus
the ledger; on the wave-47 pass the wage/spring-caretaker/migration re-point sets
(fixes log 43), plus the ledger; on the wave-48 pass the ford/estuary/tutelary
re-point sets (fixes log 44), including the river↔ford two-way, plus the ledger;
on the wave-49 pass the midwife/inn/blizzard re-point sets (fixes log 45), plus the
ledger; on the wave-50 pass the understory/mirage/mint re-point sets (fixes log
46), plus the ledger; on the wave-51 pass the orchard/delta/sledge re-point sets
(fixes log 47), plus the ledger; on the wave-52 pass the raft/eclipse/pooka re-point
sets (fixes log 48), plus the ledger; on the wave-53 pass the chant/touch/siren
re-point sets (fixes log 49), plus the ledger; on the wave-54 pass the
meadow/canal/cistern re-point sets (fixes log 50), plus the ledger; on the wave-55
pass the meteor/balefire/baptism re-point sets (fixes log 51), plus the ledger; on
the wave-56 pass the palanquin/fog/drought/caravan re-point sets (fixes log 52),
completing the t19 wave-46–56 sweep, plus the ledger.

---

## 1. Audit table

Legend: **refs** = cross-reference integrity (paths + §-refs), **numbers** =
shared-number consistency, **vocab** = vocabulary uniformity, **open-Q** =
open-question ownership. ✓ = clean (nothing to fix); ● = a fix/note applied.

| Doc | refs | numbers | vocab | open-Q | Fixes applied |
|---|---|---|---|---|---|
| `volumetric-terrain.md` | ✓ | ✓ | ✓ | ✓ | none — it is the root of the dual-world / precision-tool / hardness=rung vocabulary, heavily *cited*, no broken refs or divergent numbers |
| `async-field-domain.md` | ● | ✓ | ● | ● | Q4 now names its consumers (Fix 3); `∇(gΦ)`→`∇(g·Φ)` mapping note (Fix 4); §7 Q1's beyond-Phase-1 relocation policy now names `world-seams.md` §4.2 as owner-by-assignment (Fix 11) |
| `chunk-field-quantization.md` | ● | ✓ | ✓ | ● | explicit "resolves `async-field-domain` §7 Q1" reverse-ref added (Fix 1) — closes the two-way Q1 dependency |
| `material-regimes.md` | ✓ | ✓ | ✓ | ✓ | none — the fire-vs-explosive vocabulary-handoff already cross-references `coherence-magic` §4.3 (two-way) and the concept-4/§5 purity-axis pickup |
| `energy-harnessing.md` | ● | ● | ● | ✓ | `ξ−1` corrected in §4.1 (Fix 2a) and §7 Q1 (Fix 2b); async-field-domain Q4 consumer + term-mapping note (Fix 2c/2d) |
| `coherence-technologies.md` | ● | ✓ | ● | ● | `∇(gΦ)`→`∇(g·Φ)` mapping note (Fix 4); Q6 pickup status documented and corrected (Fix 5) |
| `coherence-magic.md` | ✓ | ✓ | ✓ | ✓ | none — Q4/Q5 already two-way-open to material-regimes via §4.3/§3(b) |
| `custom-blocks.md` (read-only) | ✓ | ✓ | ✓ | ✓ | not modified (concurrent workstream owns it); audited only |
| `world-seams.md` (wave 7) | ✓ | ✓ | ✓ | ✓ | clean — each number cited from `corpus-reconciliation.md`/chunk/async, never re-derived; §4.2 claim to own async-Q1's relocation policy is the assigned owner (see verdict). The §6(d) `= output ≤ φ⁻¹·input` gate reuses energy §6 (no new figure). |
| `field-archaeology.md` (wave 7) | ✓ | ✓ | ✓ | ● | clean refs/numbers/vocab (residue model is [design], engine-real persistence is cited). Open-Q3 (residue vs live-structure classifier) is two-way closed with `field-music.md` open-Q2 (fix 10) and `player-remains.md` open-Q3 (fix 13), and the classifier line itself is now **closed** by `life-signal.md` §3/§6 (fix 14). |
| `field-hazards.md` (wave 8) | ✓ | ✓ | ✓ | ● | clean refs/numbers/vocab (c_s = h₀/dt, q-range, 1–6 ms, ≈6 MiB all canonical or theory-sourced). Open-Q2 (storm provenance) ↔ `field-npc-ai.md` §4.3, open-Q4 (dead window) ↔ `field-npc-ai.md` open-Q5, and open-Q1 (hazard-threshold scaling) ↔ `tide-of-the-attractor.md` open-Q3 are all now two-way closed (fixes 8/9/13, see verdict). |
| `resonance-seeds.md` (wave 8) | ✓ | ✓ | ✓ | ● | clean refs/numbers/vocab (full canonical set cited in cross-refs). Open-Q5 (re-homing seed provenance) depends on async §7 Q1's window-relocation policy — the ownership chain is recorded in the verdict. |
| `field-music.md` (wave 8) | ✓ | ✓ | ✓ | ● | clean refs/numbers/vocab. The hazards forward-ref was ALREADY reconciled (intro carries a "**NOW EXISTS**" note cross-linking field-hazards §2/§3); the §7 stale "(not yet written)" note was corrected to `field-hazards.md` §2/§3 on this pass (fix 7). Open-Q2 (growl-vs-scar classifier) two-way now closed with `field-archaeology.md` open-Q3 (fix 10). |
| `field-npc-ai.md` (wave 8) | ✓ | ✓ | ✓ | ● | clean refs/numbers/vocab. Open-Q1 (decision-layer location) is now **resolved** by `reason-field.md` (domain-side, fix 14); open-Q2 (intent-phase classifier) is now **closed** by `life-signal.md` §3/§6 (fix 14); open-Q3 (individual Π pattern vs the village bath) recorded open with its owners; open-Q5 (commons-drain attrition) ties to `field-hazards.md` open-Q4 (closed, fix 9). |
| `field-instruments.md` (wave 9) | ✓ | ✓ | ✓ | ✓ | clean — the Weatherglass/Far Mirror are pure consumers of the published channels (≈6 MiB, 1–6 ms budget, ξ/φ⁻² cited verbatim); open-Q none (gates, not open questions); family rule (instruments = consumers with an idiom, never a new channel) is consistent with the corpus's read-only-consumer discipline. |
| `tide-of-the-attractor.md` (wave 9) | ✓ | ✓ | ✓ | ● | clean refs/numbers/vocab — a pacing lens with no new engine term; cites the canonical set verbatim and the theory's mixing-clock constants as theory-sourced (non-canonical, see §2 note). Open-Q3 (thin-trough vs desert threshold) is two-way closed with `field-hazards.md` §6.2/open-Q1 (fix 13); open-Q5 (mixel-scale q-gate coupling) remains a probe back to the theory solver, `qi-as-time-clock.md` §2.1 its owner. |
| `player-remains.md` (wave 9) | ✓ | ✓ | ✓ | ● | clean refs/numbers/vocab (residue model is [design]-on-[design], engine-real persistence cited). Open-Q1 (re-lock computation site) mirrors `field-npc-ai.md` §7 open-Q1's decision-layer fork — now **resolved** by `reason-field.md` (domain-side); open-Q3 (own-fossil vs live-player) inherits `field-archaeology.md` open-Q3 — now **closed** by `life-signal.md` §3/§6 (fixes log 14). |
| `deep-field-diving.md` (wave 10) | ✓ | ✓ | ✓ | ✓ | clean — the Bell composes three already-designed pieces (Qi bath, φ-detuned boundary, rigid-body vehicle), no new physics; canonical numbers (64³, ≈6 MiB, dt=0.05, JOB/TREE caps, ≈2,000, ≈1–6 ms) cited verbatim. Open-Q1 (strata-volume vs core-sample depth) is [design] over archaeology's Phase-1.5 gates; open-Q5 (Bell vs BH) is a designed default, not a ref gap. No cross-doc open-Q left one-way. |
| `pocket-cosmos.md` (wave 10) | ✓ | ✓ | ✓ | ● | clean — the recursion (window grown inward) reuses the window architecture verbatim; the full canonical set cited (`corpus-reconciliation.md` line: 192³/64³/12³, dt=0.05, τ_c=0.5, φ⁻²=0.382, ξ=φ⁶≈17.94, ω₀²=20, π/ρ clamp 0.72, ≈6 MiB, ≈1–6 ms, JOB/TREE caps, ≈2,000, ≈40 ns). The two reverse pointers (world-seams §3.1 → pocket-cosmos §1.2; resonance-seeds §2.3 → pocket-cosmos §2.2) were added earlier (fix 13) and read both ways. Open-Q1 (entry threshold) is a Phase-1 measurement, not a cross-doc gap. |
| `the-reading-ahead.md` (wave 11) | ✓ | ✓ | ✓ | ● | clean refs/numbers/vocab — the oracle is a pure consumer of the ≈6 MiB publish + threshold roster; all canonical numbers (τ_c=0.5, q≈0.947, q~1e-3…1e-1, ≈1–6 ms) cited. The mixing-clock `T=2π/[λ(1−q)]` is theory-sourced (non-canonical, §2 note). Open-Q2 (trend-vs-state classifier) is the forward twin of the life-signal maintenance read — noted open, owners cited. No missing ref. |
| `signature-predator.md` (wave 11) | ✓ | ✓ | ✓ | ● | clean — the Coda reuses `field-hazards.md`'s spine (fourth hazard class) and the canonical `ε²`/`M`/`q` set cited verbatim. Open-Q1 (formation answer) re-gates on `field-hazards.md` open-Q2 with an explicit `← field-hazards §6.2 open-Q2` two-way pointer already in place; open-Q2 (M availability) is the same line life-signal's closure answers (see verdict). Cross-owned two-way with `field-hazards.md`. |
| `resonance-tutor.md` (wave 11) | ✓ | ✓ | ✓ | ● | clean refs/numbers/vocab (trace = Q4 op-record; canonical set cited; the ε²-vent `sustainability` reading is the shared vocab). Open-Q1 (trace journal location) **resolved** by `reason-field.md` (domain-side, fix 14); open-Q2 (recorded-vs-live phase gap) **closed** by `life-signal.md` §3/§6 (fix 14). |
| `mouths-eye.md` (wave 12) | ✓ | ✓ | ✓ | ● | clean — the gustatory third sense is a pure consumer of the published `(ρ,q,ε²)`; canonical set cited; the triad rule and `(1−q)`/fire-vs-explosive vocabulary are consistent. Open-Q3 (storm-approach taste vs static scar) is the same classifier line life-signal closes (inherited by the tongue) — recorded open with the shared owner. No missing ref. |
| `life-signal.md` (wave 12) | ✓ | ✓ | ✓ | ● | clean — the vitality classifier, the doc that closes five peers' classifier questions (§5). Canonical set cited verbatim; the maintenance-axis read is [design] over engine-real channels, flagged honestly (§6). Its own open-Q2 (deliberate-vent vs sustained-maintenance residual) is the honest `M`-sharpening boundary; open-Q4 (provenance-neutral read) aligns with player-remains §7 open-Q5. The five re-pointing closures (fixes log 14) are now two-way. |
| `reason-field.md` (wave 12) | ✓ | ✓ | ✓ | ● | clean — the domain-side resolution, committed (§5). **Canonical-number check:** §2.2's ~328 KB fp32 for sites (`2·16³ × ~10 floats`) and ~32 KB f32 / 16 KB f16 for the intent-phase channel (8,192 floats) both **match** `async-field-domain.md` §2.2 / `chunk-field-quantization.md` §5 exactly; the ≈6 MiB publish and the ≈2,000-cap/≈1–6 ms weighing are cited verbatim. The three-fork resolution (fixes log 14) is now two-way. Gated on the meshless/persistent-Π frontier + Q4 schema (§6a) — LATER, as its own verdict states. |
| `shared-ledger.md` (wave 12) | ✓ | ✓ | ✓ | ● | clean — the Coherence Board is a pure consumer of the Q4 op-stream + the publish; canonical numbers (≈6 MiB, 64³, ≈1–6 ms, ≈2,000, ξ, φ⁻²) cited. The member-id extension is [design] over the Q4 schema; the misattribution classifier inherits the life-signal/archaeology line (closed two-way). Open-Q1 (member-id rule across death) rides player-remains §5 open-Q5 (the identity open question), correctly shared. No missing ref. The schema settlement (fixes log 15) now binds §6c (member-id landed), open-Q1 (same member line), open-Q3 + §4.1 (sustain flag), §4.3 (cell-ownership locality). |
| `weather-not-storm.md` (wave 13) | ✓ | ✓ | ✓ | ● | clean — a provenance classifier over the published channels + a pre-registered probe; canonical set cited verbatim (≈6 MiB, c_s = h₀/dt, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, ≈1–6 ms). Its §3 probe operationalizes `field-hazards.md` open-Q2 (reverse pointer added, fix 17); it inherits the tide §5a probe discipline (fix 17). No missing ref. |
| `patient-field.md` (wave 13) | ✓ | ✓ | ✓ | ✓ | clean — a lens/feel doc (no physics); the mixing clock T=2π/[λ(1−q)] is theory-cited (flagged speculation, non-canonical), dt=0.05 / ≈6 MiB / ξ / φ⁻² / q≈0.947 all canonical. Open questions (L-probe spread, felt-season units, loan-interest dial, pocket-tempo legibility) all have owners; no one-way ref left. |
| `fate-of-a-window.md` (wave 13) | ✓ | ✓ | ✓ | ● | clean — window-scale C(W) read, same aggregation as the Board scaled up; canonical set cited verbatim. Open-Q1/Q2/Q5 are [probe]/[design] with owners; open-Q3 inherits `field-hazards.md` open-Q4's dead-window measurement (the deciding gate the wave-15 `wound-remembered` doc now re-gates on, see next revision). No missing ref. |
| `schema-that-settles.md` (wave 14) | ✓ | ✓ | ✓ | ● | clean — the Q4 op-schema settlement. **Canonical-number check:** the ~16 B/record member tag, ~8 KB f32 / 4 KB f16 M-publication (≈2,000 floats ≈ 8 KB f32), and the 44 ms (88%) unused-tick all **match** `chunk-field-quantization.md` §4 / the ≈6 MiB / ≈2,000-cap canonical set exactly; no new canonical number introduced. Five forks settled (member-id, sustain-flag, locality, member-across-death, M-deferral); its own §6c migration is decided. The peer re-points (fix 16) close the five waiting consumers' open-Qs two-way. |
| `house-that-steers.md` (wave 14) | ✓ | ✓ | ✓ | ✓ | clean — buildings as coherence architecture (shape-is-the-tuner, concept 2); canonical set cited verbatim (≈6 MiB, 64³, 192³ box, 8192 sites, q≈0.947, φ⁻², ξ). Open questions (geometry-steering calibration, ruin persistence, drain-vs-decay, re-authoring budget, excavate-firing) all have owners; no one-way ref left. |
| `farm-that-feeds.md` (wave 14) | ✓ | ✓ | ✓ | ● | clean — a renewable found-economy; canonical set cited verbatim (≈6 MiB, 64³, φ⁻², ξ, q≈0.947, dt=0.05, ≈1–6 ms, ≈2,000). Open-Q3 (sustain-vs-re-emit) defers "until Q4 settles" — **now settled by `schema-that-settles.md` §2.2 (sustain = flag)**, so the ledger notes that closure (the farm's ops ride the settled record; see verdict/fixes log 16). Other open-Qs probe-calibrated with owners. |
| `coherence-highway.md` (wave 15) | ✓ | ✓ | ✓ | ✓ | clean — roads as steered coherence routes; canonical set cited verbatim (≈6 MiB, 64³, 192³ box, 8192 sites, ξ, φ⁻², q≈0.947, dt=0.05, ≈1–6 ms, ≈2,000, ≈40 ns/entity river-law steer `a = −G_N·(π/ρ)·∇(g·Φ)`). Open questions (ride-downhill calibration, routing-with-site-map, thin-trough floor, Coda-attribution, travel-mint, rail-vs-road) all have owners; no one-way ref left. |
| `wound-remembered.md` (wave 15) | ✓ | ✓ | ✓ | ● | clean — a wounded lock-break as a fifth damage class; canonical set cited verbatim. Its persistence/re-bleeding claim is **probe-gated on `field-hazards.md` open-Q4** (scar-lifecycle — reverse pointer added, fix 18); its world-cause (the deed) inherits `signature-predator.md` §7b's Q4-write-lane gate + `shared-ledger.md` §6c's member-id (open-Q3 "whose wound"); its ethics live-signal `weather-not-storm.md` §5.3's cruel-world rule. Open-Q1/Q2/Q4/Q5 have owners (Q2 is the life-signal deliberate-vent residual). No missing ref. |
| `the-burden.md` (wave 15) | ✓ | ✓ | ✓ | ● | clean — channeling as a loan with interest; canonical set cited verbatim. **`R = ρ_signature · τ · M_stability` verified against `signature-predator.md` §2.2 exactly** (the Coda-attraction product the carried debt feeds). Its mechanical layer gates on `signature-predator.md` §7b's Q4 lane (reverse pointer added, fix 18); open-Q3 inherits life-signal open-Q2's deliberate-vent residual; open-Q5 rides player-remains §5 open-Q5. No missing ref. **Wave-16 reverse pointer added (fix 19): §2b now names `sleep.md` §1/§2b as the nightly instance of the Still Room's repayment.** |
| `the-name.md` (wave 16) | ✓ | ✓ | ✓ | ✓ | clean — naming as a Π-anchor field act; canonical set cited verbatim; no new numbers; the identity-machinery capstone (§7 GRAND/LATER mechanical, Phase-1-legible principle scaffolded now — **confirmed no action this pass; the wave-18 `the-inheritance.md` is the in-flight continuation**). Open questions all owned (self-name scope, false-name honesty, persistence). No missing ref. |
| `sleep.md` (wave 16) | ✓ | ✓ | ✓ | ● | clean — sleep as the field's fastest-reader-at-rest; canonical set cited verbatim; no new numbers (the mixing clock T=2π/[λ(1−q)] theory-cited, non-canonical, flagged). Introduces the **live-but-idle fifth class** (life-signal §3 reverse pointer added, fix 19) and establishes sleep = the Burden's night + the Still Room's body-scale bed + the Coda's overnight risk. Open-Qs have owners (the idle-vs-fossil N2/N4 line, the overnight τ vs half-life, the bed's clearing dial). No missing ref. |
| `the-map.md` (wave 16) | ✓ | ✓ | ✓ | ✓ | clean — a player-drawn map as a recording field instrument; canonical set cited verbatim (≈6 MiB, 64³, 192³, 8192 sites, q≈0.947, φ⁻², ξ, ≈1–6 ms, dt=0.05); no new numbers. Open-Qs all owned (aging calibration [probe], ink tuning, redraw-vs-strata, site-map divergence, map-to-farm shadow). Composes strata-map/vein-map/storm-track with validated two-way refs. No missing ref. |
| `seed-garden.md` (wave 16) | ✓ | ✓ | ✓ | ● | clean — the vault as preservation-scale coherence architecture; canonical set cited verbatim (192³, ≈6 MiB, dt=0.05, τ_c=0.5, φ⁻², ξ, ω₀², π/ρ clamp, q≈0.947, 8192 sites); theory (persistent-Π §5.2, mixing clock T, winding |δn|≤0.162) flagged non-canonical per §2. **Field-instruments §2.2 reverse pointer added (fix 19): the vault is the Still-Room idiom at preservation scale.** Open-Qs have owners (vault-hold-vs-in-situ, capacity bound, held-seed drift, conservation-for-its-own-sake, inherited provenance). No missing ref. |
| `the-chronicle.md` (wave 17) | ✓ | ✓ | ✓ | ● | clean — the settlement's record made narrative; canonical set cited verbatim. **Number check:** the-chronicle does **NOT** quote the `R = ρ_signature · τ · M_stability` accumulation product anywhere (it never engages the Coda's accumulation model — its composition is the op-stream turned into a score, not the predator's closeness); its only cross-precedent figure, the ~5% CPU synth-render (`synth_design.md`), **matches** the source exactly. Open-Qs have owners (narrative selection, chronicle-across-rebuild, pre-provenance sourcing, composition cost-model, dissolved-entry obituary). No missing ref, no divergence. |
| `worn-field.md` (wave 17) | ✓ | ✓ | ✓ | ✓ | clean — the garment as an authored-regime worn field-state; canonical set cited verbatim (ξ=17.94, ω₀²=20, θ_c=0.5, the river-law steer, R product, ≈6 MiB); the [design]-over-engine-real stack is drawn exactly (§5). Open-Qs all owned (regime-constants gate, do-NPCs-dress, masking accessibility, wardrobe economy). No missing ref. |
| `window-guests.md` (wave 17) | ✓ | ✓ | ✓ | ● | clean — the traveller as walking provenance; canonical set cited verbatim. **Number check:** its `R = ρ_signature · τ · M_stability` matches signature-predator §2.2 exactly. Visitor-line + provenance-flag is a [design] extension over schema §2's settled record (no new canonical field); carried channels framed honestly. Open-Qs have owners. No missing ref. |
| `the-inheritance.md` (wave 18) | ✓ | ✓ | ✓ | ● | clean — the will as a field act; canonical set cited verbatim (≈6 MiB, 64³, ξ, φ⁻², q≈0.947, ≈1–6 ms, ≈2,000, 8192 sites); theory (persistent-Π §5.2, one-rung IIR) flagged non-canonical. §8 is the identity stack's **capstone** (Phase-1-legible bequest record now, claim semantics LATER on the meshless/Π frontier). **the-name §7 reverse pointer added (fix 20): the Inheritance continues the name's capstone scaffold.** Open-Qs all owned (bequest record shape, will timing, named-anchor fall, claim-vs-find, conservation-of-you). No missing ref. |
| `the-festival.md` (wave 18) | ✓ | ✓ | ✓ | ● | clean — the commons' one chord as a coordinated field op; canonical set cited verbatim (≈6 MiB, 64³, q≈0.947, q~1e-3…1e-1, ξ, φ⁻², dt=0.05, ≈1–6 ms, ≈2,000). §4 is the corpus's joy, honestly framed (no-free-energy / vent-cost / tide-timing bounds — never farmable). Phase-1-legible single-chord op now; mechanical festival LATER on commons + composition + tide. Open-Qs all owned (alignment dial, C(festival) shape, frequency/sacrifice threshold, who-the-members, re-bind persistence). No missing ref. Note: the mourning twin `the-funeral` is wave-19 in-flight — noted for next pass, no action. |
| `the-clock.md` (wave 18) | ✓ | ✓ | ✓ | ● | clean — the second-order field watch reading local `(1−q)` tempo; canonical set cited verbatim (≈6 MiB, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ, φ⁻², ≈1–6 ms, ≈2,000); theory (mixing clock T, λ_mix) flagged non-canonical. §5/§6 draw the theory/[design]/engine-real line with the mixing clock as a speculation. **Its ground-truth probe — `patient-field.md` §5(b)'s L1–L3 — now two-way (fix 20): patient-field §5b cites the landed the-clock; the clock cites patient-field §5b as its deciding gate.** Open-Qs all owned. No missing ref. |
| `the-mirror.md` (wave 18) | ✓ | ✓ | ✓ | ● | clean — the life-signal's inward face; canonical set cited verbatim. **Number check:** its `R = ρ_signature · τ · M_stability` (lines 196–219) **matches `signature-predator.md` §2.2 exactly** — verified per the pass-3/pass-4 precedent; its cross-references' "verified here exactly" claim is TRUE. §3/§6a's phase-gap face rides `patient-field.md` §5(b)'s L1–L3 probe (the same gate the Clock shares, now two-way — fix 20). Open-Qs all owned. No missing ref. |
| `the-funeral.md` (wave 19) | ✓ | ✓ | ✓ | ● | clean — the communal act of letting a member's Π-pattern dissolve *through* the commons; canonical set cited verbatim (≈6 MiB, 64³, 192³, 8192 sites, q≈0.947, ξ=17.94, φ⁻²=0.382, τ_c=0.5, dt=0.05, ≈1–6 ms, ≈2,000); theory (persistent-Π §5.2, mixing clock T) flagged non-canonical. **Number check:** its `C(funeral)` (the dissolved line settled as one coordinated op) builds on `shared-ledger.md` §1.2's per-member `C(M)` aggregation **exactly** — verified. **the-festival §4 reverse pointer added (fix 21): the funeral closes the queued mourning-twin note.** Open-Q4 confirms the player-vs-NPC mourner fork cited at field-npc-ai §7 open-Q3 (tightened, fix 21). No missing ref. |
| `the-cooked-field.md` (wave 19) | ✓ | ✓ | ✓ | ✓ | clean — cooking as composing meals into an edible regime; canonical set cited verbatim (≈6 MiB incl. the q1+pot1+∇(g·Φ)3+ρ1 split, 64³, φ⁻²=0.382, ξ=17.94, ω₀²=20, θ_c=0.5, q≈0.947, q~1e-3…1e-1, dt=0.05, ≈1–6 ms, ≈2,000). No new physics (a kitchen is a consumer of the farm + lab preview + mouths-eye read); no new canonical numbers. Open-Qs all owned (composition fold, feed/drain threshold, bounded-patch→live consistency, feast attribution, found-recipe reproducibility). No missing ref. |
| `the-cold.md` (wave 19) | ✓ | ✓ | ✓ | ● | clean — the long-thin as a climate, not an event; canonical set cited verbatim (≈6 MiB, 64³, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, dt=0.05, ≈1–6 ms, ≈2,000); theory (mixing clock T, λ_mix) flagged non-canonical. **Its §5b/§7 gates on `tide-of-the-attractor.md` §5a** — reverse pointer added there (fix 21). Open-Qs all owned (cold boundary, drift-collapse verdict, cost book, fate place, voyage reason). No missing ref. |
| `the-exile.md` (wave 20) | ✓ | ✓ | ✓ | ● | clean — the ban made field-honest; canonical set cited verbatim (≈6 MiB, 64³, dt=0.05, q≈0.947, ξ=17.94, φ⁻²=0.382, τ_c=0.5, ≈1–6 ms, ≈2,000). **open-Q2 ↔ the-election composition-tie reverse pointer added (fix 21).** Open-Qs all owned (convergence threshold, hollow-eye performer, Coda-drawer boundary, severed-line persistence, ghost stranding). No missing ref. |
| `the-election.md` (wave 20) | ✓ | ✓ | ✓ | ● | clean — choosing a steward as reading the ledger's momentum; canonical set cited verbatim (≈6 MiB, 64³, 192³, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, τ_c=0.5, dt=0.05, ≈1–6 ms, ≈2,000); theory (mixing clock T) flagged non-canonical. **Number check:** its `C(M) = Σ ops (net field-contribution of each op at its locality/rung/magnitude) budgeted against the bath's Δq/Δε²` **matches `shared-ledger.md` §1.2's per-member aggregation exactly** — verified no re-derivation. **§2.3 momentum rides `tide-of-the-attractor.md` §5a** (reverse pointer added, fix 21); open-Q3 ↔ exile open-Q2; open-Q4 confirms the player-vs-NPC candidate fork cited at field-npc-ai §7 open-Q3. No missing ref. |
|| `the-bell.md` (wave 20) | ✓ | ✓ | ✓ | ● | clean — the settlement-scale alarm answering when the stack agrees; canonical set cited verbatim (≈6 MiB, dt=0.05, q≈0.947, q~1e-3…1e-1, c_s=h₀/dt, ξ=17.94, φ⁻²=0.382, ≈1–6 ms, ≈2,000). **Cost check:** its "one trilinear sample inside the ≈ 1–6 ms/tick budget, exactly as the Weatherglass is (`field-instruments.md` §1.4)" **matches** the Weatherglass's cost profile exactly — verified no divergence. **§4 night-ring composes `sleep.md` §2.2's sitting signature** (reverse pointer added, fix 21); **§4 now reads the Lantern (walker's personal bell) and the Silence (the quietest alarm) back two-way (fix 22).** Open-Qs all owned (agreement threshold, false-ring rate, flat-tempo leg, bell-pit calibration, night-reach). |
|| `the-silence.md` (wave 21) | ✓ | ✓ | ✓ | ● | clean — the world's voice completed by its absence (empty / held / hunting registers); canonical set cited verbatim (≈6 MiB, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, ≈1–6 ms, ≈2,000); theory (mixing clock T) flagged non-canonical. **§2.3 hunting silence ↔ `the-bell.md` §4 two-way (fix 22): the hunting silence is the Bell's quietest alarm.** Phase-1-lean consumer; no new physics. Open-Qs all owned (register thresholds, flat-`(1−q)` leg, pre-Coda hunting honesty, seam/night reach, self-vs-world quiet). No ref-gaps. |
|| `the-observatory.md` (wave 21) | ✓ | ✓ | ✓ | ✓ | clean — the composed instrument room (the whole stack read as one body); canonical set cited verbatim (≈6 MiB, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, τ_c=0.5, ≈1–6 ms, ≈2,000). Composes the family (each surface a consumer of an already-published channel), never adds one; Phase-1-lean, two-surface slice. **Cross-checks clean:** its "one trilinear sample per surface, inside the ≈ 1–6 ms/tick budget, exactly the Weatherglass's §1.4 cost" **matches** the Weatherglass cost profile exactly. No new canonical numbers. Open-Qs all owned (aging legibility, surface order, mirror aggregation at scale, election seat, Bell-at-night reach). No ref-gaps. |
|| `the-apprenticeship.md` (wave 22) | ✓ | ✓ | ✓ | ● | clean — the live co-channeling pair-bond (the tutor's trace made live); canonical set cited verbatim (≈6 MiB, 64³, ξ=17.94, φ⁻²=0.382, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (persistent-Π §5.2, mixing clock T) flagged non-canonical. **§5 reverse pointer added (fix 22): the pair-bond is the `the-family.md` §4/§5 pair made a family; the-child also reads this pair as the natural first teacher (fix 23).** MEDIUM-feasible with designable-now framing; gates all owned (two-body working, mentor persona, shelter floor, credit sharing, pair deaths). No ref-gaps. |
|| `the-family.md` (wave 22) | ✓ | ✓ | ✓ | ● | clean — the shared persistent-Π anchor, the identity stack's social atom; canonical set cited verbatim (≈6 MiB, 64³, 192³, 8,192 sites, q≈0.947, ξ=17.94, φ⁻²=0.382, τ_c=0.5, dt=0.05, ≈1–6 ms, ≈2,000); theory (persistent-Π §5.2 ratified identity `I = k_B q ln φ`) flagged non-canonical. **Rides the landed member-id + persistent-Π theory flags correctly (fix 22): member-id [design]-landed, the joint hold theory-ratified with the `reason-field.md` §6a speculation flag.** **§3.2 ↔ `the-funeral.md` §2.2 and §3.2/§4 ↔ `the-inheritance.md` §2.2 now two-way (fix 22): the funeral re-binds the family's hold; a will to the house is a will to the family. §4 reverse pointer (fix 22): the joint-hold principle lifted across the dark = `the-treaty.md` §2.1.** LATER/GRAND with scaffolded-now framing. Open-Qs all owned (co-binding rule, joint-line shape, death re-binding, family-vs-commons, claim-vs-endowment). No ref-gaps. |
|| `the-flood.md` (wave 22) | ✓ | ✓ | ✓ | ● | clean — the q-excess event, the harvest that drowns, an abundance-extreme; canonical set cited verbatim (≈6 MiB, 64³, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, dt=0.05, ≈1–6 ms, ≈2,000); theory (mixing clock T, λ_mix) flagged non-canonical. **Number check:** its `E_waste = (1−q)·E_throughput` **matches `energy-harnessing.md` §2 exactly** — verified no re-derivation. **↔ `the-cold.md` §5.3 two-way (fix 22): the flood is the cold's opposite and equal danger; both ride `tide-of-the-attractor.md` §5a** (the flood added as the probe's third consumer, fix 22). Open-Qs all owned (surfeit threshold, drift-collapse verdict, cap-at-surfeit, over-bloom shape, fate place). No ref-gaps. |
|| `the-treaty.md` (wave 22) | ✓ | ✓ | ✓ | ● | clean — the compact between windows, a paired persistent-Π bridge across the dark; canonical set cited verbatim (≈6 MiB, 64³/192³, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, τ_c=0.5, dt=0.05, ≈1–6 ms, ≈2,000); theory (persistent-Π §5.2, multiplicative commons) flagged non-canonical. **Rides the landed member-id + persistent-Π theory flags correctly (fix 22): member-id/visitor-line [design]-landed, the spanning hold theory-ratified with the `reason-field.md` §6a speculation flag.** **§2.1 joint-hold principle ↔ `the-family.md` §2.1/§4 two-way (fix 22): the Treaty lifts the Family's joint across the dark.** LATER with designable-now framing; the corpus's first between-windows object. Open-Qs all owned (paired-anchor binding, cost/stretch dials, break shape, scope, a cold's treaty). No ref-gaps. |
|| `the-lantern.md` (wave 22) | ✓ | ✓ | ✓ | ● | clean — the carried night-read, the walker's personal light reading the near field; canonical set cited verbatim (≈6 MiB, 64³, 192³, dt=0.05, q≈0.947, q~1e-3…1e-1, ε²=(EY−φ·EI)², ξ=17.94, φ⁻²=0.382, ≈1–6 ms, ≈2,000); no new theory constants. **Cost check:** its "one trilinear sample at the player's position, inside the ≈ 1–6 ms/tick server sample budget, exactly as the Weatherglass is (`field-instruments.md` §1.4)" **matches** the Weatherglass cost profile exactly — verified no divergence. **§4 ↔ `the-bell.md` §4 (walker's personal bell) and §4 ↔ `the-mirror.md` §4.4 (bedside warning) now two-way (fix 22).** Phase-1-able. Open-Qs all owned (glow-mapping thresholds, wrong-warm vs wearer's mask, front-vs-hunt provenance, lantern-lit night chart, night walker's reach). No ref-gaps. |
|| `the-seeker.md` (wave 23) | ✓ | ✓ | ✓ | ● | clean — the finder instrument pointing at one bound Π-pattern a player named; canonical set cited verbatim (≈6 MiB, 64³, 192³, q≈0.947, φ⁻²=0.382, ξ=17.94, ≈1–6 ms, ≈2,000, 8192 sites, dt=0.05); theory (persistent-Π §5.2) flagged non-canonical. **Complement pair ↔ `the-compass.md` §2.2/§4 (fix 23): the Seeker finds what *you* named; the Compass reads what the *field* is organizing through. §4 rides `reason-field.md` §6a + `the-family.md` §2.2 — reverse pointers added there (fix 23).** Phase-1-lean; full seeks LATER on the identity frontier. Open-Qs all owned (binding calibration, decay presentation, discrimination noise-floor, reach-hand-off, bind scope). No ref-gaps. |
|| `the-child.md` (wave 23) | ✓ | ✓ | ✓ | ● | clean — the fresh-line run, the identity stack's onset; canonical set cited verbatim (≈6 MiB, 64³, 192³, ξ=17.94, φ⁻²=0.382, τ_c=0.5, dt=0.05, ≈1–6 ms, ≈2,000, ≈40 ns/entity, q≈0.947, q~1e-3…1e-1); theory (persistent-Π §5.2, `reason-field.md` §6a) flagged non-canonical. **§3.4 founding-lesson ↔ `the-apprenticeship.md` (fix 23): the pair is the child's natural first teacher, the apprenticeship the live recording of the first past hand.** MEDIUM with Phase-1-legible framing. Open-Qs all owned (firsts' order gate, empty-row classifier, child-vs-reborn firsts, first-scar teachability, first-name/family claim). No ref-gaps. |
|| `the-echo.md` (wave 23) | ✓ | ✓ | ✓ | ● | clean — the field's memory made audible, the deep-time register (present/empty/warning/remembered); canonical set cited verbatim (≈6 MiB, dt=0.05, q≈0.947, q~1e-3…1e-1, c_s=h₀/dt, ξ=17.94, φ⁻²=0.382, ≈1–6 ms, ≈2,000). **Theory citations carry the speculation flags (fix 23): the altered-state channels are engine-real/[design]-landed; the echo's *imprint-not-recording* framing explicitly flags the persistent-Π sources' `reason-field.md` §6a speculation.** Phase-1-lean. Open-Qs all owned (re-match threshold, remembered-vs-present distinction, un-gated textures, echo-vs-dig, seam reach). No ref-gaps. |
|| `the-stillness.md` (wave 24) | ✓ | ✓ | ✓ | ● | clean — the field at absolute rest, the resolved end-state; canonical set cited verbatim (≈6 MiB, q≈0.947, ε²≈0, ∇(g·Φ)≈0, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, dt=0.05, ≈1–6 ms, ≈2,000); theory (mixing clock T) **flagged as a speculation** (fix 23: the §1 companion line marks `T = 2π/[λ(1−q)]` as **theory**). Region-class design over real channels; gates on the tide probe's limit (`tide §5a`) + patient-field §5b L1–L3. Open-Qs all owned (still-threshold calibration, still-vs-silence boundary, settled-history, brittleness, what-a-settlement-does). No ref-gaps. |
|| `the-oath.md` (wave 24) | ✓ | ✓ | ✓ | ● | clean — the within-window compact made field-true, the marriage-bond; canonical set cited verbatim (≈6 MiB, 64³/192³, q≈0.947, ξ=17.94, φ⁻²=0.382, τ_c=0.5, dt=0.05, ≈1–6 ms, ≈2,000); theory (persistent-Π §5.2) flagged non-canonical with the flag carried. **§3.2 rupture ↔ `the-exile.md` §4 (fix 23): the oath's break is the within-window sever quieter than exile — a promise's death, not a person's removal.** LATER with designable-now framing. Open-Qs all owned (named-object scope, pledge-line shape, who-can-oath, rupture permanence, steward-oath scope). No ref-gaps. |
|| `the-healer.md` (wave 24) | ✓ | ✓ | ✓ | ● | clean — medicine as a designed practice with the healer's toll; canonical set cited verbatim (≈6 MiB, ε²=(EY−φ·EI)², q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, π/ρ clamp 0.72, ω₀²=20.0, dt=0.05, ≈1–6 ms, ≈2,000); theory (persistent-Π, mixing clock, magic-systems M≈1) flagged non-canonical. **§3.1 dimmed read ↔ `the-mirror.md` §2.4 (fix 23): the toll's legibility on the classification face; the steward-with-weight Board guard (`shared-ledger.md` §6e) verified cited correctly. §2.2 resurrection-limit ref corrected to `the-funeral.md` §2.3/§6d — verified no residual §3.3 mis-reference (fix 23).** MEDIUM with designable-now framing. Open-Qs all owned (toll transfer/decay, stop/too-high, dimmed-vs-true-wound, toll-across-death, Board stewardship-cost). No ref-gaps. |
|| `the-compass.md` (wave 24) | ✓ | ✓ | ✓ | ● | clean — the wearable site-map reading where the field is reaching; canonical set cited verbatim (≈6 MiB, 64³/192³, 2·16³=8192 sites, q≈0.947, q~1e-3…1e-1, ε²=(EY−φ·EI)², ξ=17.94, φ⁻²=0.382, ≈1–6 ms, ≈2,000, dt=0.05); theory/probe (intent-channel, `reason-field.md` §6a) flagged non-canonical. **Number check:** its "~32 KB f32 / 16 KB f16 for 8,192 sites, ≈ half a percent of the canonical publish" **matches `reason-field.md` §2.2 exactly** — verified no divergence. **§3.3 provenance line (weather-not-storm §4a + life-signal §6) verified resolves.** Complement pair ↔ `the-seeker.md` §2.2/§4 (fix 23). Phase-1-lean; warning read LATER. Open-Qs all owned (directional calibration, reach-character provenance, idle/no-reach presentation, promise-vs-warning floor, intent-phase shape). No ref-gaps. |
|| `the-memory-palace.md` (wave 25) | ✓ | ✓ | ✓ | ● | clean — the settlement's chosen memory made architecture, the past-self library; canonical set cited verbatim (≈6 MiB, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, τ_c=0.5, ≈1–6 ms, ≈2,000, 8192 sites). **§3 ↔ `the-observatory.md` §3.5 (fix 24): the palace is the past-self to the observatory's present-self; §2.2 ↔ `the-chronicle.md` §2.3 (the chronicle room); §4 ↔ `house-that-steers.md` §3 (ruin-of-choices) verified.** MEDIUM-LATE with designable-now framing; a consumer of the memory-systems (family rule). Open-Qs all owned (rooms scope, quiet-room echo, capacity, window-decay, walking-vs-instrument). No ref-gaps. |
|| `the-language.md` (wave 25) | ✓ | ✓ | ✓ | ● | clean — the sites' activity made readable, a grammar over the corpus's reads; canonical set cited verbatim (≈6 MiB, 64³/192³, 2·16³=8192 sites, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, τ_c=0.5, ≈1–6 ms, ≈2,000, dt=0.05); theory/probe (intent-channel) flagged. **§2.2 → `signature-predator.md` §2 (the "hunting" word) verified resolves** (a shared accumulation; reverse-pointer not forced into the shared §2). MEDIUM with designable-now framing. Open-Qs all owned (composition thresholds, word-boundary, lettered-fallback, past-tense-vs-present, taught-skill honesty). No ref-gaps. |
|| `the-census.md` (wave 25) | ✓ | ✓ | ✓ | ● | clean — the settlement's population as a field read, the Board's book at population scale; canonical set cited verbatim (≈6 MiB, 64³/192³, dt=0.05, τ_c=0.5, φ⁻²≈0.382, ξ=17.94, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000); theory (persistent-Π) flagged. **§5 ↔ `the-observatory.md` §3.5 (the composed surface, fix 24) + §2.2 ↔ `the-child.md` §7 open-Q2 (the dormancy threshold, fix 24).** Phase-1-lean; the society's pulse. Open-Qs all owned (dormancy dial, lead-time probe, young-vs-fading source, composed surface, strangers provenance). No ref-gaps. |
|| `the-threshold.md` (wave 25) | ✓ | ✓ | ✓ | ● | clean — the boundary-mark as a field structure (held, quiet, named); canonical set cited verbatim (≈6 MiB, 64³/192³, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, τ_c=0.5, ≈1–6 ms, ≈2,000, 8192 sites); theory (persistent-Π anchor) flagged. **§2.2 ↔ `the-bell.md` §4 (the gate's crossing is the warning, fix 24) + §2.3 ↔ `window-guests.md` §3 (the first thing a visitor's provenance crosses, fix 24).** Phase-1-lean (the doorstep slice). Open-Qs all owned (doorstep magnitude, crossing-vs-traffic, arch name-scope, inner-edge honesty, unmaintained residue). No ref-gaps. |
|| `the-blight.md` (wave 26) | ✓ | ✓ | ✓ | ● | clean — the over-bloom made a danger, the corpus's first ecological hazard; canonical set cited verbatim (192³/64³/12³, ≈6 MiB, ξ=17.94, φ⁻²=0.382, τ_c=0.5, π/ρ clamp 0.72, ω₀²=20.0, dt=0.05, ≈1–6 ms, ≈2,000, q≈0.947, q~1e-3…1e-1); theory (persistent-Π) flagged. **§2.2/§4.1 ↔ `field-emergent-ecology.md` §2.2/§5.3 (fix 25: the over-bloom made pathological; conservation = the heal); §2.1 ↔ `the-flood.md` §2/§3 (the wrong-band habitat, fix 25); §4.2 ↔ `wound-remembered.md` §1 (the clear's scar, fix 25).** MEDIUM-LATE with Phase-1-legible framing. Open-Qs all owned (corruption dial, sustainability bound, heal toll at scale, clear scar, fate place). No ref-gaps. |
|| `the-window-year.md` (wave 26) | ✓ | ✓ | ✓ | ● | clean — the composed long-rhythm calendar, the corpus's time doc; canonical set cited verbatim (≈6 MiB, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, ≈1–6 ms, ≈2,000); theory (mixing clock) flagged. **Its composition rides the tide's [probe] period, never setting it (§2: the beat is `tide §5a`'s measured value, not this doc's). §3.1 ↔ `the-festival.md` §3 (the bright anchor, fix 25); §3.4 ↔ `the-election.md` §4.3 (the governance beat, fix 25); §3.3 ↔ `the-funeral.md` §3.3 (the anniversaries, fix 25).** MEDIUM-LATE with Phase-1-legible framing. Open-Qs all owned (drift-collapse verdict, cold boundary, steward term length, observatory mounting, anniversaries provenance-neutrality). No ref-gaps. |
|| `the-hourglass.md` (wave 26) | ✓ | ✓ | ✓ | ● | clean — the duration instrument, the Clock's accumulated twin; canonical set cited verbatim (≈6 MiB, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, ≈1–6 ms, ≈2,000); theory (mixing clock) flagged. **§1 ↔ `the-clock.md` §3.3 (the trip-meter to the speedometer, fix 25); §3 ↔ `the-healer.md` §2 (the long bind's bound, fix 25); §2 path fixed to `../../CassiTheory/speculations/qi-as-time-clock.md` (fix 25 — the bare path did not resolve from designs/).** Cost check: its Phase-1 slice is "one trilinear sample inside the ≈ 1–6 ms/tick budget, the Weatherglass's §1.4 cost" — **matches** the sample budget exactly. Phase-1-able. Open-Qs all owned (probe verdict, sand-units, accumulation linearity, four-uses gating, redundancy). No ref-gaps. |
|| `the-walk.md` (wave 27) | ✓ | ✓ | ✓ | ● | clean — the un-roaded crossing designed as a read; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + ∇(g·Φ) 3 + ρ 1, 64³, 192³, 2·16³=8192 sites, ξ=17.94, φ⁻²=0.382, q≈0.947, q~1e-3…1e-1, dt=0.05, ≈1–6 ms, ≈2,000, ≈40 ns/entity). **§2a ↔ `coherence-highway.md` §2.2 (the ridges walked ungated, fix 25); §2c ↔ `signature-predator.md` §2 (the walking trail, fix 25); §3 open-Q5 ↔ `the-pilgrim.md` §3.1 (where the walk ends — the pilgrimage's self-complete answer, fix 25).** Cost check: the stride-cost read is "1–2 samples per stride inside the ≈ 1–6 ms/tick budget, the Weatherglass's §1.4 cost" — **matches**. Phase-1-able. Open-Qs all owned (stride-calibration, trail-vs-heap, `(1−q)` spread, burden stride-shed, where-it-ends). No ref-gaps. |
|| `the-fallow.md` (wave 27) | ✓ | ✓ | ✓ | ● | clean — the window's generational depletion, the economic face of the decay arc; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, φ⁻²≈0.382, ξ=17.94, ω₀²=20.0, π/ρ clamp 0.72, q≈0.947, q~1e-3…1e-1, ≈6 MiB, ≈1–6 ms, ≈2,000, 8192 sites). **§2a ↔ `material-regimes.md` §3 (the mined vein gone-forever, fix 25); §4.2 ↔ `the-exile.md` §4 (the leaver's fork, fix 25).** MEDIUM-LATE with Phase-1-legible framing. Open-Qs all owned (worked-deposit verdict, spent-order absoluteness, fallow-vs-fate, departure bookkeeping, accessibility floor). No ref-gaps. |
|| `the-pilgrim.md` (wave 27) | ✓ | ✓ | ✓ | ● | clean — the named-place walk as a field act, the why-walk doc; canonical set cited verbatim (≈6 MiB, 64³, 192³, q≈0.947, φ⁻²≈0.382, ξ=17.94, dt=0.05, ≈1–6 ms, ≈2,000, 8192 sites). **Critical correction (fix 25): the §1 once-flag and §3.1 now cite `the-walk.md` (which landed after the pilgrim) — the pilgrim is the walk's craft composed at the pilgrimage's purpose; the-walk open-Q5 ↔ the-pilgrim §3.1 two-way. §2.1 ↔ `field-archaeology.md` §5.3 (the attended ruin, fix 25); §4 ↔ `the-name.md` §6d (the re-bind's no-raise boundary, fix 25).** MEDIUM with Phase-1-legible framing. Open-Qs all owned (re-bind dial, ungated cost, deliberate-burden framing, pilgrimage scope, clearing-vs-Still-Room). No ref-gaps. |
|| `the-tide-staff.md` (wave 27) | ✓ | ✓ | ✓ | ● | clean — the planted standing gauge, the tide's observability made physical; canonical set cited verbatim (≈6 MiB, 64³, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²=0.382, ≈1–6 ms, ≈2,000). **§2.1 ↔ `tide-of-the-attractor.md` §2 (the band marks the seasons, fix 25); §3.2 ↔ `fate-of-a-window.md` §1.3 (the drift-from-marks, fix 25).** Cost check: "one trilinear sample at the staff's position, inside the ≈ 1–6 ms/tick budget, the Weatherglass's §1.4 pattern" — **matches** the sample budget exactly. Phase-1-able. Open-Qs all owned (band-threshold, probe verdict, aging form, staff-vs-yard, propagation). No ref-gaps. |
|| `the-sea.md` (wave 28) | ✓ | ✓ | ✓ | ● | clean — the field's water, the designed middle of the vertical; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + ∇(g·Φ) 3 + ρ 1, 64³, 192³, 8192 sites, ξ=17.94, φ⁻²=0.382, τ_c=0.5, π/ρ clamp 0.72, ω₀²=20.0, dt=0.05, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity, c_s=h₀/dt); theory (mixing clock) flagged non-canonical. **§2a ↔ `coherence-highway.md` §1.1 (the river as conduit at nature's scale, fix 26) + §2b ↔ `the-walk.md` §2a/§2b (the fluid-drift / flat-plain crossing, fix 26) + §2c ↔ `the-flood.md` §2/§3 AND `atmosphere-orbits-auroras.md` §1.3 (the flood is the wave made water — inherited, no new overflow, fix 26) + §4 ↔ `the-blight.md` §2 (the poisoned sea, fix 26).** Cost check: the Phase-1 patch read is a pure consumer inside the ≈ 1–6 ms/tick budget. MEDIUM with a Phase-1 slice. Open-Qs all owned (uniform-plain calibration, river conduit-strength, precipitation condition, water-borne blight flow, sea-vs-fast-reader). No ref-gaps. |
|| `the-tool.md` (wave 28) | ✓ | ✓ | ✓ | ● | clean — the rung-matched work object, the primitive under the economy; canonical set cited verbatim (≈6 MiB, 192³/64³/12³, dt=0.05, ξ=17.94, φ⁻²≈0.382, τ_c=0.5, π/ρ clamp 0.72, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈40 ns/entity, ≈2,000). **§2b ↔ `energy-harnessing.md` §2 (the wear = the waste law, fix 26) + §2a ↔ `material-regimes.md` §3/§4 (the bite, fix 26) + §3 ↔ `worn-field.md` §1 (the held regime, fix 26) + §2c ↔ `deep-field-diving.md` §2.2 (the scar — the un-contained hand-scale, fix 26).** Cost check: a few trilinear samples per swing inside the ≈ 1–6 ms/tick budget, the Weatherglass's §1.4 cost — **matches**; a tool adds a bounded Q4 write (a held perturbation, never a channel). Phase-1-able. Open-Qs all owned. No ref-gaps. |
|| `the-vigil.md` (wave 28) | ✓ | ✓ | ✓ | ● | clean — the designed long watch, the corpus's first *practice*; canonical set cited verbatim (≈6 MiB, 64³/192³, dt=0.05, q≈0.947, q~1e-3…1e-1, ε²=(EY−φ·EI)², ξ=17.94, φ⁻²≈0.382, τ_c=0.5, c_s=h₀/dt, ≈1–6 ms, ≈2,000); theory (mixing clock T) flagged non-canonical, quoted only through `the-hourglass.md`. **§2a ↔ `the-lantern.md` §2/§4 (the watch-read, fix 27) + §2b ↔ `the-silence.md` §2/§5.2 (the watch's listening, fix 27) + §2c ↔ `the-threshold.md` §2.2 (the gate's keeper, fix 27) + §2d ↔ `the-bell.md` §4 (the bell's keeper, fix 27) + §3 ↔ `signature-predator.md` §2/§7e (the clean-signature exposure, fix 27) + §4 ↔ `the-election.md` §4.3/§7 (the rotated watch, fix 27).** Cost: one trilinear sample per read inside the ≈ 1–6 ms/tick budget, the Weatherglass's §1.4 cost — **matches**. PHASE-1-ABLE. Open-Qs all owned (watch term, legibility at the floor, sentinel-vs-drift, rotation's member-line, uneventful-watch cost). No ref-gaps. |
|| `the-working-song.md` (wave 29) | ✓ | ✓ | ✓ | ● | clean — music composed for labor, the corpus's second *practice*; canonical set cited verbatim (≈6 MiB, 64³, ξ=17.94, φ⁻²≈0.382, q≈0.947, q~1e-3…1e-1, dt=0.05, ≈1–6 ms, ≈2,000); theory (magic-systems M≈1, coherence-commons ∏ 1/(1−q_i)) flagged non-canonical. **§1 ↔ `the-vigil.md` §1 (the second practice, fix 27) + §2.1 ↔ `field-npc-ai.md` §3.2 (a phase-locked group IS a working, `M ≈ 1`, fix 27) + §3a ↔ `the-tool.md` §2a (the lumber-camp's bite, fix 27) + §3b ↔ `material-regimes.md` §3 (the forge-chant's line, fix 27) + §3c ↔ `the-healer.md` §2 (the heal-song's bind, fix 27).** The `(1−q)` waste law and the `output ≤ φ⁻¹·input` cap are cited verbatim (energy §2/§6); the phase-lock is the corpus's designed commons law (field-npc-ai §3). MEDIUM with a Phase-1-legible framing. Open-Qs all owned (alignment dial, felt gain, song-that-stops honesty, three-songs separation, shift duration). No ref-gaps. |
|| `the-feral-instrument.md` (wave 29) | ✓ | ✓ | ✓ | ● | clean — a bound structure whose persistent-Π outlived its keeper's intent, the third stranger-object face; canonical set cited verbatim (≈6 MiB, 64³/192³, ξ=17.94, φ⁻²≈0.382, τ_c=0.5, dt=0.05, q≈0.947, ≈1–6 ms, ≈2,000, 8192 sites); theory (persistent-Π §5.2) flagged non-canonical with the reason-field §6a speculation flag carried. **§1/§2.2 ↔ `reason-field.md` §6a (the persistent-Π frontier, fix 27) + §3a ↔ `house-that-steers.md` §1/§3.2 (the self-chairing house, fix 27) + §3b ↔ `the-memory-palace.md` §2 (the over-keeping palace, fix 27) + §3c ↔ `seed-garden.md` §3/§4 (the rudderless vault, fix 27) + §4 ↔ `the-oath.md` §1/§3 (the re-bind fork, fix 27).** Cost: one trilinear sample inside the ≈ 1–6 ms/tick budget — **matches**. MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (waking threshold, binding scope, re-bind permanence, keeper's return, cross-face gates). No ref-gaps. |
|| `the-atlas-of-windows.md` (wave 29) | ✓ | ✓ | ✓ | ● | clean — the player-level cross-window record, the movement stack's capstone; canonical set cited verbatim (≈6 MiB, 64³, 192³, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²≈0.382, τ_c=0.5, dt=0.05, ≈1–6 ms, ≈2,000). **§1 ↔ `the-map.md` §1 (the per-window drawing, fix 27) + §1 ↔ `the-chronicle.md` §1 (the page's story, fix 27) + §1 ↔ `the-memory-palace.md` §1 (the cross-window sibling, fix 27) + §3.1 ↔ `the-fallow.md` §3 (the depletion read, fix 27) + §3.2 ↔ `fate-of-a-window.md` §1/§6c (the arc read, forecast-≠-fate, fix 27).** Cost: composed reads at the traveler's scale, on the observatory's cost profile, inside the ≈ 1–6 ms/tick budget — **matches**. LATER with a Phase-1-legible framing. Open-Qs all owned (page capacity, refresh authority, forecast-edge, shared-vs-own, decay palimpsest). No ref-gaps. |
|| `the-drift-road.md` (wave 29) | ✓ | ✓ | ✓ | ● | clean — the tide's verdict designed as gameplay on every branch; canonical set cited verbatim (≈6 MiB, 64³, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²≈0.382, dt=0.05, ≈1–6 ms, ≈2,000); theory (mixing clock T) flagged non-canonical. **§2b ↔ `tide-of-the-attractor.md` §5b open-Q1 (the drift branch, fix 27) + §3.3 ↔ `the-stillness.md` §5.1 (the still-point end, fix 27) + §3.4 ↔ `the-festival.md` §3 (the once-celebration, fix 27) + §1 ↔ `weather-not-storm.md` §4 (the precedent, fix 27).** The pass-spec's "drift-road `M ≈ 1`" item was **verified as an honest negative**: the drift-road is a tide-verdict consequence doc with **no phase-lock / `M` / field-npc-ai §3.2 reference anywhere** — no such claim was forced into it (it does not engage the phase-lock at all; the `M ≈ 1` field-npc-ai cite applies to the working-song and the school, not this doc), so no correction was invented. MEDIUM with a designable-now framing. Open-Qs all owned (branch build order, still-point reach, once-festival timing, per-region fallback, drift-year's feel). No ref-gaps. |
|| `the-scar-lifecycle.md` (wave 30) | ✓ | ✓ | ✓ | ● | clean — the wound's fate, the most-cited open question answered; canonical set cited verbatim (≈6 MiB, 192³/64³/12³, dt=0.05, τ_c=0.5, φ⁻²≈0.382, ξ=17.94, ω₀²=20.0, π/ρ clamp 0.72, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000). **§2.1 ↔ `patient-field.md` §3 (the healed scar under rest, fix 27) + §2.2 ↔ `field-hazards.md` open-Q4 (the scar-lifecycle probe answered, fix 27) + §2.3 ↔ `house-that-steers.md` §3.2 (the build-on-the-ruin, fix 27) + §2.3 ↔ `field-archaeology.md` §2 (the strata-to-come, fix 27) + §4.1 ↔ `the-blight.md` §4.2 (the clear's scar answered, fix 27) + §4.3 ↔ `fate-of-a-window.md` §2/§3 (the scar read's deep branch, fix 27) + §1 ↔ `wound-remembered.md` §1.2/§7 open-Q5 (the wound's fate answered, fix 27).** No new channel; a designed reading over the wound's `ε²` residue and the field's `q` recovery. MEDIUM with a Phase-1-legible framing. Open-Qs all owned (healing-threshold calibration, kept-scar edge stability, adoption boundary, young-vs-aged, shallow-wound-under-help). No ref-gaps. |
|| `the-interstitial.md` (wave 30) | ✓ | ✓ | ✓ | ● | clean — the sparse medium the windows float in, the world-structure's third face; canonical set cited verbatim (≈6 MiB, 64³, 192³, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²≈0.382, ω₀²=20.0, τ_c=0.5, dt=0.05, c_s=h₀/dt, ≈1–6 ms, ≈2,000, ≈40 ns/entity). **§2a ↔ `world-seams.md` §1.3/§2.1 (the between the voyage crosses, fix 27) + §2a ↔ `energy-harnessing.md` §7 Q1 (the dilute field / noise floor, fix 27) + §2b ↔ `field-music.md` §1/§2 (the ringing, fix 27) + §2b ↔ `the-atlas-of-windows.md` §2 (the distant pages read by ear, fix 27) + §2c ↔ `signature-predator.md` §1/§7 (the lawful absence, fix 27) + §3 ↔ `patient-field.md` §3.3 AND `the-hourglass.md` §3 (the unforgiving patience, fix 27) + §2a ↔ `the-sea.md` §2b (the flat plain made total, fix 27).** The no-free-energy cap held structurally (nothing to convert). LATER with a Phase-1-legible framing. Open-Qs all owned (thin's floor, ringing's carriage, lawfulness certainty, patience's flat tempo, first-bath contrast). No ref-gaps. |
|| `the-market.md` (wave 30) | ✓ | ✓ | ✓ | ● | clean — the settlement's exchange made honest by the law itself, the corpus's trust doc; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + ∇(g·Φ) 3 + ρ 1, 192³/64³, dt=0.05, τ_c=0.5, φ⁻²≈0.382, ξ=17.94, ω₀²=20.0, π/ρ clamp 0.72, q≈0.947, ≈1–6 ms, ≈2,000). **Canonical check: the market's op-record `{member, op, worldPos, rung, magnitude, sustain}` matches `schema-that-settles.md` §2.1's six-field record fields-and-order verbatim** — verified, the exchange *is* a Q4 op of the settled shape. **§2.1 ↔ `schema-that-settles.md` §2.1 (the op-record verbatim, fix 27) + §2.2 ↔ `the-tool.md` §2 (the traded provenance, fix 27) + §2.2 ↔ `seed-garden.md` §3 (the seed's vault-row, fix 27) + §2.3 ↔ `the-name.md` §2 (the false-op cheat, fix 27) + §2.3 ↔ `shared-ledger.md` §6d (the no-false-booking, fix 27) + §3.3 ↔ `the-oath.md` §1/§3 (the small vow, fix 27) + §4.1 ↔ `window-guests.md` §3 (the visitor line, fix 27) + §4.2 ↔ `the-exile.md` §4 (the exiled line, fix 27) + §1/§2 ↔ `the-census.md` §2.1 (the active-class face, fix 27).** MEDIUM with a Phase-1-legible framing. Open-Qs all owned (exchange-op scope, value reconciliation, non-tangibles, exiled-trader standing, vault share). No ref-gaps. |
|| `the-scavenger.md` (wave 31) | ✓ | ✓ | ✓ | ● | clean — the denizen of the spent, the stranger-object layer's melancholic fourth face / first *fitted* creature; canonical set cited verbatim (192³/64³/12³, ≈6 MiB, ξ=17.94, φ⁻²≈0.382, τ_c=0.5, ω₀²=20.0, dt=0.05, ≈1–6 ms, ≈2,000, q≈0.947, q~1e-3…1e-1). **§2.1 ↔ `field-emergent-ecology.md` §2.2/§6b (the organism-class run / residual band, fix 27) + §2.1 ↔ `signature-predator.md` §2.3/§7e (the spent margin / no-farming closure, fix 27) + §2.3 ↔ `the-fallow.md` §2a/§3 (the worked veins as home, fix 27) + §2.3 ↔ `the-blight.md` §4.2 (the clear's scar as habitat, fix 27) + §2.3 ↔ `the-scar-lifecycle.md` §2.2/§2.3 (the kept scar's edge / the scar-kept place it avoids, fix 27) + §3.3 ↔ `field-hazards.md` §1 (the first non-hazard row, fix 27) + §4 ↔ `the-census.md` §1 (the spent's census, fix 27).** A consumer of the residual `ε²` + the organism-class vocabulary, never a harvest (§7e farming closure held). MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (residual-band calibration, lawfulness bound, population aggregation, healing-threshold dissolve, feral provenance line). No ref-gaps. |
|| `the-school.md` (wave 31) | ✓ | ✓ | ✓ | ● | clean — collective teaching as a phase-locked band, the apprenticeship made a group; canonical set cited verbatim (≈6 MiB, 64³, ξ=17.94, φ⁻²≈0.382, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity). **§2.1 ↔ `the-working-song.md` §2.1 (the phase-lock applied to teaching, fix 27) + §2.1 ↔ `field-npc-ai.md` §3.2 (a phase-locked group IS a working, `M ≈ 1`, fix 27) + §2.2 ↔ `shared-ledger.md` §1.2 (the booked competence, fix 27) + §2.2 ↔ `the-market.md` §1 (legible the way the market books an exchange, fix 27) + §3.1 ↔ `the-vigil.md` §3/§4 + `the-apprenticeship.md` §2.2 (the teacher's drain / the faster burden, fix 27) + §4 ↔ `the-name.md` §2 + `the-market.md` §2.3 (cannot teach what the field does not hold, fix 27).** MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (group-size band, teacher's drain at scale, competence boundary, school-vs-apprenticeship line, NPC learner). No ref-gaps. |
|| `the-sea-floor.md` (wave 31) | ✓ | ✓ | ✓ | ● | clean — the interface between the liquid regime and the below, the vertical's missing seam; canonical set cited verbatim (192³/64³/12³, ≈6 MiB, 8192 sites, ξ=17.94, φ⁻²≈0.382, τ_c=0.5, π/ρ clamp 0.72, ω₀²=20.0, dt=0.05, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity, c_s=h₀/dt). **§2a ↔ `the-sea.md` §2b (the shelf's upper side / the plain, fix 27) + §2b ↔ `field-emergent-ecology.md` §4.2/§6b (the reef's band, fix 27) + §2b ↔ `the-blight.md` §2 (the water-borne habitat, fix 27) + §2c ↔ `deep-field-diving.md` §3.1/§4 (the descent / net-negative hold, fix 27) + §4.1 ↔ `the-scar-lifecycle.md` §2.2 (the reef-edge scar, fix 27) + §4.2 ↔ `field-archaeology.md` §2/§3.2 (the residue funnel, fix 27).** Cost check: the Phase-1 shelf read is "a pure consumer of the publish — reads `q`/`ε²`/`∇(g·Φ)` from the ≈ 6 MiB snapshot inside the ≈ 1–6 ms/tick sample budget, writes nothing new" — **matches** the Weatherglass budget. MEDIUM with a Phase-1 slice. Open-Qs all owned (shelf gradient calibration, reef's band width, descent's first terrace, reef-edge-vs-shore, plain's-edge-vs-river-mouth). No ref-gaps. |
|| `the-dawn.md` (wave 31) | ✓ | ✓ | ✓ | ● | clean — the field's re-birth each day, the transition read, the corpus's first becoming; canonical set cited verbatim (≈6 MiB, 64³/192³, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²≈0.382, ≈1–6 ms, ≈2,000). **§2b ↔ `the-lantern.md` §4 (the night-read's end, fix 27) + §2b ↔ `the-vigil.md` §3 (the watch's end, fix 27) + §2b ↔ `signature-predator.md` §2 (the margin's thinning, fix 27) + §2c ↔ `patient-field.md` §3.3 (the loan's interest re-opened, fix 27) + §3 ↔ `sleep.md` §3 (the bed decision's resolution, fix 27) + §4 ↔ `field-instruments.md` §2.1 (the family's becoming, fix 27).** Cost check: "one or two samples across the transition window, inside the ≈ 1–6 ms/tick budget, the Weatherglass's §1.4 cost" — **matches** the Weatherglass sample budget. PHASE-1-ABLE. Open-Qs all owned (transition window, breaking separation at the floor, re-opening cost structure, margin-thinning-vs-long-dark, becoming's rhythm across the cold). No ref-gaps. |
|| `the-commensal.md` (wave 32) | ✓ | ✓ | ✓ | ● | clean — the order-side companion, the stranger-object layer's **first positive face**, the corpus's warmth; canonical set cited verbatim (≈6 MiB, 192³/64³/12³, dt=0.05, ξ=17.94, φ⁻²≈0.382, τ_c=0.5, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity). **Canonical check: the commensal's assist is net-negative — "you pay in coherence to maintain, never a free gain," citing energy-harnessing §5.4's anti-corruption (suppressing ε², net-negative) — verified.** **§2.1 ↔ `field-emergent-ecology.md` §2.2/§6b (the organism-class run, fix 28) + §2.3 ↔ `house-that-steers.md` §2.2 (the bath-edge habitat, fix 28) + §2.3 ↔ `the-sea-floor.md` §2b (the reef-warden, fix 28) + §3 ↔ `field-emergent-ecology.md` §5.3 + `energy-harnessing.md` §5.4 (the bounded anti-corruption assist, fix 28) + §3.3 ↔ `field-hazards.md` §1 (the first positive row, fix 28) + §1/§4 ↔ `field-npc-ai.md` §1/§3 (the servant/neighbor line, fix 28) + §1 ↔ `the-scavenger.md` §1/§2 (the bright twin, fix 28).** A consumer of the surplus `(1−q)` + the organism-class vocabulary, never a mint (the §7e no-farming closure held). MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (surplus-band calibration, assist bound, steadiness-read vs census, healing-threshold dissolve, NPC-service blur). No ref-gaps. |
|| `the-gift.md` (wave 32) | ✓ | ✓ | ✓ | ● | clean — the deliberate no-trace transfer, the economy's only generosity, the honest inverse of the market; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + ∇(g·Φ) 3 + ρ 1, 192³/64³, dt=0.05, ξ=17.94, φ⁻²≈0.382, ω₀²=20.0, τ_c=0.5, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, 8192 sites, ≈40 ns/entity). **Canonical check: the gift's op-record `{member, op, worldPos, rung, magnitude, sustain}` matches `schema-that-settles.md` §2.1's six-field record fields-and-order verbatim — verified, the gift is the settled record's withheld line. **§2.1 ↔ `schema-that-settles.md` §2.1 (the op-record, fix 28) + §2.1 ↔ `the-market.md` §2.3/§3 (the booked exchange's inverse, fix 28) + §2.3 ↔ `the-name.md` §2 (the false gift is a false name, fix 28) + §2.3 ↔ `shared-ledger.md` §6d (the no-false-booking from the not-booking side, fix 28) + §3.2 ↔ `the-festival.md` §2.3 (the tide-high generosity / spent-never-free, fix 28) + §3.3 ↔ `field-npc-ai.md` §3 (the commons' invisible glue, fix 28) + §4.3 ↔ `the-exile.md` §4 + `window-guests.md` §3 + `schema-that-settles.md` §2.1.1 (the severed line / the visitor line / no amnesty, fix 28) + §4.2 ↔ `the-oath.md` §1/§3 (the un-bound giving, fix 28) + §6d ↔ `energy-harnessing.md` §6 (the gift converts nothing, fix 28) + §3 ↔ `the-window-year.md` §3 (the giving tide, fix 28).** No new channel, no new physics, no "gift record" — the deliberate absence of a bookable contribution on the landed Q4 lane. MEDIUM with a Phase-1-legible framing. Open-Qs all owned (mark's scope, what a gift can carry, un-talliedness read, receiver-read authority, warmth's clock). No ref-gaps. |
|| `the-dispute.md` (wave 32) | ✓ | ✓ | ✓ | ● | clean — the adjudication made field-true, the settlement's disagreements settled by the law itself, the final-unforgiving judge; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + ∇(g·Φ) 3 + ρ 1, 64³, dt=0.05, τ_c=0.5, ξ=17.94, φ⁻²≈0.382, π/ρ clamp 0.72, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity). **§2.1 ↔ `shared-ledger.md` §6d + `field-npc-ai.md` §6d + `schema-that-settles.md` §2.1 (the no-false-booking + the determinism + the claim's record shape, fix 28) + §2.1 ↔ `the-name.md` §1/§2/§6e (the anchors' provenance, fix 28) + §2.1 ↔ `life-signal.md` §3 (the maintenance read, fix 28) + §2.2 ↔ `the-observatory.md` §2 (the present-state read, fix 28) + §3.2 ↔ `the-oath.md` §1/§3 + `the-market.md` §2.3 + `the-election.md` §4.3/§4.4 (the vows, the clear-book, the stewardship, fix 28) + §3.3 ↔ `the-exile.md` §2/§4 (the verdict's severance, fix 28) + §4 ↔ `the-name.md` open-Q3 + `the-treaty.md` §3/§4 (the two-true-holds limit / the cross-window edge, fix 28) + open-Q3 ↔ `field-npc-ai.md` §7 open-Q3 (the player-vs-NPC claimant fork, fix 28).** A read to resolution, never a verdict record; each leg costed at the Weatherglass's sample budget. MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (composition weights, torn-vs-gap, claimant membership, reversibility, cross-window treaty edge). No ref-gaps. |
|| `the-window-pulse.md` (wave 33) | ✓ | ✓ | ✓ | ● | clean — the collective healthmeter, the census's sibling reading the settlement's health rather than its population; canonical set cited verbatim (≈6 MiB, 64³/192³, dt=0.05, τ_c=0.5, ξ=17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000). **§2.1 ↔ `house-that-steers.md` §1/§2.2 (the bath — the level, fix 29) + `shared-ledger.md` §1.2/§6c (the lines' mutual drift, fix 29) + `the-name.md` §1/§3.2/§6e (the anchors' held-locks — the tethers, fix 29) + `the-commensal.md` §3 (the warm steadiness, fix 29) + `life-signal.md` §3/§4 (the maintenance axis / the breathing read, fix 29) + `fate-of-a-window.md` §1/§6 (the present's sibling — the decay arc read in the present, fix 29) + `the-window-year.md` §2/§3 (the pulse's rhythm, fix 29) + `the-census.md` §2/§3/§7 (the sibling, fix 29) + `the-observatory.md` §2/§6b (the seat, fix 29) + `the-healer.md` §2 (the we/never-I boundary's source, fix 29).** Cost: a pure consumer of the ≈ 6 MiB publish + the Q4-op-stream-derived lines, inside the ≈ 1–6 ms/tick budget — **matches**. MEDIUM with a Phase-1-legible framing. Open-Qs all owned (composition weights, mutual-drift measure, life/death line, lead-time probe, we/never-I edge). No ref-gaps. |
|| `the-zenith.md` (wave 33) | ✓ | ✓ | ✓ | ● | clean — the vertical's ceiling, the edge of the window's atmosphere, the corpus's second interface doc; canonical set cited verbatim (≈6 MiB, 192³/64³/12³, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²≈0.382, τ_c=0.5, ω₀²=20.0, c_s=h₀/dt, ≈1–6 ms, ≈2,000). **§2a ↔ `energy-harnessing.md` §2/§6 (the waste law / the cap — the drain, fix 29) + `atmosphere-orbits-auroras.md` §1.4/§1.3/§2/§3 (the sky ceiling it tops, fix 29) + §2b ↔ `the-interstitial.md` §2a/§4 (the thin — the far side, fix 29) + `the-sea-floor.md` §1 (the interface register's precedent, fix 29) + §2c ↔ `world-seams.md` §2/§2.3 (the edge you cannot leave through, fix 29) + §3 ↔ `field-archaeology.md` §2.1 (the ozone — the waste's residue, fix 29) + `the-observatory.md` §2 (the ceiling read, fix 29) + `deep-field-diving.md` §1 (the top mirror of the deep, fix 29) + `the-sea.md` §2b (the plain's other end, fix 29).** Cost: the Phase-1 slice is a pure consumer of the ≈ 6 MiB publish inside the ≈ 1–6 ms/tick budget — **matches**. MEDIUM with a Phase-1 slice. Open-Qs all owned (drain's rate, boundary's band width, ozone's provenance, edge under re-home, drain vs auroral discharge). No ref-gaps. |
|| `the-stratum-read.md` (wave 33) | ✓ | ✓ | ✓ | ● | clean — the temporal family's past-face, the field's history read as an instrument, the time-camera; canonical set cited verbatim (≈6 MiB, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²≈0.382, τ_c=0.5, ω₀²=20.0, ≈1–6 ms, ≈2,000; the non-canonical mixing clock / N_memory≈φ flagged). **§2.1 ↔ `field-archaeology.md` §2/§3.2/§5.3 (the strata / the core sample / the leave-in-place fork, fix 29) + `the-clock.md` §1/§5(b)/§6 (the present-face sibling, fix 29) + `the-hourglass.md` §1/§5(b) (the interval-face sibling, fix 29) + `fate-of-a-window.md` §1/§5/§2 (the future-face sibling — the arc's kept residue, fix 29) + `field-instruments.md` §2.1/§1.4 (the family rule / sample-at-position, fix 29) + `the-scar-lifecycle.md` §2.2/§3.1/§2.1 (the kept scar's wound-depth / the healed band, fix 29) + `the-fallow.md` §2a/§5(d) (the worked vein's pulled layer, fix 29) + `the-sea-floor.md` §2a/§4.2 (the shelf's underwater strata, fix 29) + `the-memory-palace.md` §1/§4/§6(d) (the chosen-vs-kept complement, fix 29) + `life-signal.md` §3/§6 (the live-vs-residue classifier, fix 29).** Cost check: "one sample per stratum" at the depth-strata, a small constant set inside the ≈ 1–6 ms/tick budget — **matches** the sample-at-position pattern. PHASE-1-ABLE. Open-Qs all owned (depth-strata mapping, residue stability, read-vs-live separation, phase-alignment, conservation-fork place). No ref-gaps. |
|| `the-harbor.md` (wave 33) | ✓ | ✓ | ✓ | ● | clean — the settlement's door to the between, the movement stack's settlement-scale face, the corpus's first door; canonical set cited verbatim (≈6 MiB, 192³/64³/12³, q≈0.947, q~1e-3…1e-1, ξ=17.94, φ⁻²≈0.382, τ_c=0.5, dt=0.05, ≈1–6 ms, ≈2,000). **Canonical check: the harbor's ledger books the departure as the Q4 op-record `{member, op, worldPos, rung, magnitude, sustain}` — matches `schema-that-settles.md` §2.1 verbatim (the departure's `worldPos` at the pier), verified.** **§2a ↔ `the-threshold.md` §1/§2.1/§4/§6b (the boundary-mark made a place, fix 29) + `the-interstitial.md` §1/§2/§3 (the pier into the thin, fix 29) + `world-seams.md` §1/§2/§2.3 (the voyage it begins / the cost never changed, fix 29) + `the-atlas-of-windows.md` §2/§3 (the pages it writes, fix 29) + `the-treaty.md` §1/§2.2 (the crossing it begins, fix 29) + §2b ↔ `the-lantern.md` §2/§4 (the lamp — the honest reach, fix 29) + §2c ↔ `schema-that-settles.md` §2.1/§2.3 + `shared-ledger.md` §1.2/§2 (the ledger — the booked departure, fix 29) + §2d ↔ `the-vigil.md` §2c/§2d/§3 (the keeper — the last watch, fix 29) + §2a ↔ `the-sea.md` §2b/§5d (the pier over water, fix 29) + §4 ↔ `the-fallow.md` §1/§3 (the quiet harbor's face, fix 29) + `the-census.md` §2/§3 (the active class at the edge, fix 29) + open-Q5 ↔ `the-walk.md` open-Q5 (the walk's settlement-scale end, fix 29).** Cost: a consumer + composition over the landed reads, inside the ≈ 1–6 ms/tick sample budget — **matches**; no cheaper voyage (a door, never a shortcut, §4). LATER with a Phase-1-legible framing. Open-Qs all owned (pier's hold vs thin, lamp's reach, departure's op meaning, keeper's rotation, movement-stack handoff). No ref-gaps. |
|| `the-story.md` (wave 34) | ✓ | ✓ | ✓ | ● | clean — the settlement's myth made a field-memory, the culture stack's capstone, the told version of the chronicle; canonical set cited verbatim (≈6 MiB, 64³/192³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, 8,192 sites). **Canonical check: the story's shaping bound — "never adds an event" — matches `the-chronicle.md` §5's never-adds guard verbatim (verified at §5's "It never adds events."), inherited as its honesty.** **§2 ↔ `the-name.md` §2 (the load-bearing law — an untrue story is a false name, fix 30) + §2 ↔ `field-archaeology.md` §1.2/§2 (determinism-is-not-recoverability / the residue model — the story's ground-truth, fix 30) + §2.2 ↔ `the-name.md` §3 (the named contribution legible, fix 30) + §2.2 ↔ `the-memory-palace.md` §2.2/§4 (the chronicle room / the maintained hold, fix 30) + §3.1 ↔ `the-chronicle.md` §3/§5 (the narrative elements / the never-adds shaping bound, fix 30) + §3.2 ↔ `the-reading-ahead.md` §1.1/§2.2/§6.3/§7c (the momentum's narrative form, fix 30) + §3.3 ↔ `the-language.md` §1/§2.2/§2.3 + `the-pilgrim.md` §2.1 (the sites as text / the words / the grammar — a named place's story told at the place, fix 30) + §3.4 ↔ `the-festival.md` §3/§2.2 + `the-window-year.md` §3.1 (the telling-tide / the re-bind / the bright anchor, fix 30) + §3.5 ↔ `the-school.md` §2 + `the-child.md` §3.4 (the lesson it wears / the first lesson, fix 30).** Cost: the shaping is composition over the landed reads inside the ≈ 1–6 ms/tick budget — **matches**; a story informs and holds, never mints (no-free-energy cap held, §4d). MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (selection rule, shaping dial, telling-tide cost, chronicle-vs-story line). No ref-gaps. |
|| `the-rite-of-passage.md` (wave 34) | ✓ | ✓ | ✓ | ● | clean — the designed ceremony of a field-threshold, a becoming held by a shared costed field act, the five bindings; canonical set cited verbatim (≈6 MiB, 64³/192³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000). **Canonical check: the rite's phase-locked act is grounded in `field-npc-ai.md` §3.2's "a group acting phase-locked IS a working (`M ≈ 1`)" — verified; the `M≈1` is the corpus's designed commons law, never re-derived.** **§2.1 ↔ `the-child.md` §1/§3 + `the-name.md` §1/§2 (the naming — the empty book's first page / the Π-anchor a rite holds, fix 30) + §2.2 ↔ `the-apprenticeship.md` §1/§2.2 + `the-school.md` §2.1/§4 + `the-burden.md` §1/§2a (the first clean channel — the pair-bond / the group / the underwriting risk, fix 30) + §2.3 ↔ `the-family.md` §1/§2.1/§3.3 + `the-oath.md` §2.1/§4.1 (the binding — the shared-Π / the vowed promise, fix 30) + §2.4 ↔ `the-election.md` §1/§4.3 + `the-tide-staff.md` §1/§5 (the investiture — the read / the office's term / the standing gauge, fix 30) + §2.5 ↔ `resonance-seeds.md` §1/§2.1/§2.3/§3.1 + `world-seams.md` §3.2 (the founding — the seed planted / the seam's new window, fix 30) + §3 ↔ `the-festival.md` §1/§2 (the one-chord at a being's scale, fix 30) + §3 ↔ `field-npc-ai.md` §3.2 (the group working, fix 30) + §3 ↔ `energy-harnessing.md` §2/§6 (the `(1−q)` waste / the no-free-energy cap — a rite is spent never free, fix 30).** Cost: the rite's mechanics are the landed costs of its composed acts; a rite informs and binds, never mints — **matches** the sample budget. MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (the rite's form, the number of participants, the hold's duration). No ref-gaps. |
|| `the-mirror-creature.md` (wave 34) | ✓ | ✓ | ✓ | ● | clean — the field's reflective stranger, the confusion-stranger, the sixth stranger-object face that wears your pattern instead of hunting it; canonical set cited verbatim (≈6 MiB, 192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000); theory (persistent-Π §5.2 + magic-systems `M`) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **Canonical check: the mirror's accumulation `R = ρ_signature · τ · M_stability` matches `signature-predator.md` §2.2's resonance law verbatim — verified, the mirror reads your trail exactly as the Coda accumulates on it, turned from in-flow to echo (the `M` deferred per `schema-that-settles.md` §3).** **§2.1 ↔ `signature-predator.md` §1/§2.2/§3/§7e/§8 (the phase-matching / the growth law / the tell-as-approach it lacks / the no-farming gate / the readable trail, fix 30) + §3 ↔ `life-signal.md` §1/§3.1/§3.2/§6b (the maintenance axis / the four classes / the drain shape / the noise-floor, fix 30) + §3 ↔ `reason-field.md` §3.1/§6a (the persistent-Π mind it forges / the frontier, fix 30) + §4 ↔ `the-name.md` §1/§2/§6b (the false-name decay / the Phase-1-legible principle, fix 30) + §1/§5 ↔ `the-scavenger.md` §1/§2 + `the-commensal.md` §1/§4 (the stranger-object faces / the fits-you residual / the positive-face contrast, fix 30) + §1/§5 ↔ `field-hazards.md` §1/§5.1/§5.3 (the danger layer house style / the read-by-testing inversion / the cap, fix 30) + §2.2 ↔ `the-burden.md` §1/§2c/§2d (the carried signature it copies / the legibility / the Coda-stability, fix 30) + §3.3 ↔ `the-vigil.md` §3 (the exposed watch — the watcher's clean signature is the mirror's read, fix 30).** Cost: a pure consumer of the publish inside the ≈ 1–6 ms/tick budget — **matches**; a mirror informs and confuses, never mints. MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (the drain-test separation, the echo's form, the non-willful proof). No ref-gaps. |
|| `the-loan.md` (wave 35) | ✓ | ✓ | ✓ | ● | clean — credit as a field act, the forward order-borrowing, the economy's first temporal instrument, the honest cousin of the burden; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1, 192³/64³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, 8,192 sites, ≈40 ns/entity). **Canonical check: the loan's op-record `{member, op, worldPos, rung, magnitude, sustain}` matches `schema-that-settles.md` §2.1's six-field record verbatim — verified, a loan is the settled record's deferred line (the exchange deferred across a term).** **§2.1 ↔ `schema-that-settles.md` §2.1/§2.2 (the op-record / the sustain flag, fix 31) + §2.1 ↔ `the-tool.md` §2 + `seed-garden.md` §3 + `farm-that-feeds.md` §4 (the future contribution / the collateral / the repayment, fix 31) + §2.2 ↔ `the-window-year.md` §3.4 + `tide-of-the-attractor.md` §2/§5a (the term "next harvest" — the window-year's beat, priced by the tide's q, fix 31) + §3 ↔ `the-burden.md` §2a + `patient-field.md` §3.3/§5d (the patience-interest / the loan at thin, fix 31) + §4a ↔ `energy-harnessing.md` §6 + `the-market.md` §6d (a loan is not a mint / the exchange never a mint, fix 31) + §4b ↔ `the-oath.md` §3 + `the-exile.md` §4 + `the-fallow.md` §2a (the default edge / the exile's fork / the depletion edge, fix 31).** Cost: a composed forward book over the landed ledger reads inside the ≈ 1–6 ms/tick budget — **matches**; a loan informs the future, never creates it (no-free-energy cap held, §4a). MEDIUM with a Phase-1-legible framing. Open-Qs all owned (term's reference season, patience-interest dial, default's read). No ref-gaps. |
|| `the-fall.md` (wave 35) | ✓ | ✓ | ✓ | ● | clean — the vertical's un-designed third act, the gradient owns you, the one movement with no skill-buff; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1, 64³/192³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, π/ρ clamp 0.72, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity). **Canonical check: the fall's river law `a = −G_N·(π/ρ)·∇(g·Φ)` matches `corpus-reconciliation.md`'s canonical per-entity steer verbatim — verified, a fall converts the body's position into downward momentum with no `(1−q)` waste to soften it.** **§2 ↔ `coherence-highway.md` §2 + `the-walk.md` §2a + `energy-harnessing.md` §2 (the gradient owned bare / the craft removed / the `(1−q)` absent, fix 31) + §3 ↔ `the-scar-lifecycle.md` §2.1/§2.2 + `wound-remembered.md` §1 (the shallow healable / the kept scar's edge / the impact's spike, fix 31) + §4 ↔ `the-sea.md` §2b + `deep-field-diving.md` §3 (the soft landing / the controlled descent's inverse, fix 31) + §2/§4 ↔ `patient-field.md` §2/§3.3 (the patience-free act — patience softens a crossing, never a fall, fix 31).** Cost: a bounded consumer of the already-published channels, the same honest tier as the walk's stride-cost read — **matches** the sample budget; a fall converts nothing (no-free-energy cap held, §5d). PHASE-1-ABLE. Open-Qs all owned (impact's spike calibration, healing-threshold placement, soft-surface buff's honesty, fall-on-watch, walk-end-vs-sea-begin). No ref-gaps. |
|| `the-swim.md` (wave 35) | ✓ | ✓ | ✓ | ● | clean — the body's act in the water medium, the sea's third act, the walk's fluid form; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1, 64³/192³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, 8,192 sites, ≈40 ns/entity). **Special item (fix 31): the swim↔fall two-way pointer is LANDED.** The swim doc originally held the fall-as-soft-landing as its [design] bridge, flagged open in open-Q5 because `the-fall.md` did not exist on disk when the swim was written (`the-fallow.md` is a different subject). **`the-fall.md` now exists** (wave 35), so open-Q5 is **closed as resolved** with an additive note: the bridge is now a landed two-way cross-reference (`the-fall.md` §4.2 the fall's craft is the landing's shaping; §4 a fall into the sea is the swim's beginning), and the swim's §5a row + cross-refs cite it directly. **§2a ↔ `the-sea.md` §2b + `energy-harnessing.md` §2 (the medium / the liquid-regime waste, fix 31) + §2b ↔ `the-walk.md` §2a + `coherence-highway.md` §2 (the gradient read blind / the blind gradient, fix 31) + §3 ↔ `the-hourglass.md` §3 + `patient-field.md` §3.3 (the duration / the loan at thin, fix 31) + §4/open-Q5 ↔ `the-fall.md` §4.2 (the two-way bridge — closed, fix 31) + §2c ↔ `the-sea-floor.md` §2b/§4 (the descent to the reef, fix 31).** Cost: a bounded consumer of the publish, its Phase-1 slice clean, inside the ≈ 1–6 ms/tick budget — **matches**; a swim converts nothing (no-free-energy cap held, §5d). PHASE-1-ABLE. Open-Qs all owned (stroke-cost calibration, cost shape, hidden season, wake, the-fall bridge — closed). No ref-gaps. |
|| `the-bedrock.md` (wave 35) | ✓ | ✓ | ✓ | ● | clean — the window's absolute floor, where everything precipitates onto, the vertical's terminus; canonical set cited verbatim (192³/64³/12³, ≈6 MiB, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, π/ρ clamp 0.72, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (persistent-Π §5.2) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **§2a ↔ `material-regimes.md` §4 + `the-tool.md` §2a (the maximal-rung regime / the bite's wall, fix 31) + §2c ↔ `deep-field-diving.md` §3/§4 (the descent's end — the deepest terrace has no below, fix 31) + §3 ↔ `material-regimes.md` §3 + `field-archaeology.md` §2.4 + `the-fallow.md` §2a (the precipitation law / the strata's base / the un-touched face, fix 31) + §4 ↔ `field-archaeology.md` §2.3/§3.2 + `resonance-seeds.md` §1.1 (the archaeology reads down to it / the seed's deep rest, fix 31) + §1/§4 ↔ `the-zenith.md` §1/§3 + `the-sea-floor.md` §1 (the bottom face / the absolute floor, fix 31).** Cost: a composition over the deep's landed reads inside the ≈ 1–6 ms/tick budget — **matches**; a floor informs, never mints (no-free-energy cap held, §5d). MEDIUM-LATE with a Phase-1 slice. Open-Qs all owned (maximal-rung claim, the floor's face, the strata's base, the fallow's deepest vein, the seed's deep rest). No ref-gaps. |
|| `the-cave.md` (wave 36) | ✓ | ✓ | ✓ | ● | clean — the vertical's hollow, the deep's openness read as itself, the corpus's first volume; canonical set cited verbatim (192³/64³/12³, ≈6 MiB, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, 8,192 sites, c_s=h₀/dt); theory (persistent-Π §5.2) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **Cost check: the Phase-1 slice reads `q`/`ε²`/`ρ` from the ≈ 6 MiB snapshot inside the ≈ 1–6 ms/tick sample budget — **matches** the Weatherglass cost.** **§2a ↔ `the-scar-lifecycle.md` §2.2/§2.3 + `the-stratum-read.md` §2.2 (the kept scar's edge / the emptied band — a cave is a wound that healed hollow, fix 32) + §2b ↔ `the-fallow.md` §2a/§2c + `deep-field-diving.md` §6.3 (the emptied deep-rung store / the Bell's evacuated deep, fix 32) + §2c ↔ `field-hazards.md` §4.2/§4.4 + `the-bedrock.md` §7 open-Q4 (the BH's swept wake / the floor's contrast + the maximal-rung gate, fix 32) + §2d ↔ `the-flood.md` §2/§3/§4.1 + `the-fallow.md` §2d (the aftermath's undercut, fix 32) + §3 ↔ `deep-field-diving.md` §3.1/§5 + `the-stratum-read.md` §2 + `field-archaeology.md` §3.2/§1.2 (the hollow reads as itself — the terrace, the layered read, the core sample, determinism-is-not-recoverability, fix 32) + §4 ↔ `deep-field-diving.md` §2.2/§6.2 + `the-bedrock.md` §2a + `field-hazards.md` §2 + `energy-harnessing.md` §2 (the character — the inversion, the dense floor, the desert, the `(1−q)` glow, fix 32) + §6 ↔ `the-sea-floor.md` §6b + `the-bedrock.md` §5b (the volume precedent, fix 32).** MEDIUM with a Phase-1 slice. Open-Qs all owned (emptiness's persistence, the wall's honesty, the shelter's cold). No ref-gaps. |
|| `the-landform-name.md` (wave 36) | ✓ | ✓ | ✓ | ● | clean — the named land, the-name's scope dial taken at landscape scale, the landscape legibility doc; canonical set cited verbatim (≈6 MiB, 64³/192³, 8,192 sites, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000); theory (persistent-Π §5.2, local-field-mixture) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **No-free-energy check: the landform-name does NOT mint a navigation — the star-read and beacon-navigation are landed (world-seams §2.2/§2.3); steering *by a named landform's read* is [design], and the name 'informs and holds, never mints' (the-name §6d, the-map §6d, held at §4d) — verified no minted navigation.** **§2.1 ↔ `the-name.md` §1/§2.1/§5.1/§7 + `material-regimes.md` §4 + `chunk-field-quantization.md` §5 (the Π-anchor / the dial / the deep-rung condensation / the site-map bound form, fix 32) + §2.2 ↔ `coherence-highway.md` §1.1/§4.1 + `the-sea.md` §2a (the conduit's course-anchor / the moving-conduit band, fix 32) + §2.3 ↔ `the-threshold.md` §1/§6 (the boundary-hold at scale, fix 32) + §3 ↔ `the-observatory.md` §2 + `the-atlas-of-windows.md` §2 + `world-seams.md` §2.2/§2.3 + `the-map.md` §1/§3 + `the-language.md` §2 + `the-pilgrim.md` §2.1 (the charted / marked / navigable / drawn land, fix 32) + §4.1 ↔ `the-flood.md` §2 + `the-name.md` §6e + `energy-harnessing.md` §2 (the course's honest break / the `(1−q)` shed, fix 32) + §4.2 ↔ `the-map.md` §3.1 + `chunk-field-quantization.md` §5 (the region's boundary re-bind / the redraw-vs-strata, fix 32) + §4.3 ↔ `the-fallow.md` §1–§3 + `material-regimes.md` §3 + `field-archaeology.md` §2 + `the-name.md` §3.3 (the spent named land / the mined-away mountain's strata as its record, fix 32).** MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (the anchor's scale ceiling, the navigable name's honesty, the site-map binding). No ref-gaps. |
|| `the-witness.md` (wave 36) | ✓ | ✓ | ✓ | ● | clean — the field's own eye, the stranger-object layer's seventh face, the first non-face, the only neutral; canonical set cited verbatim (≈6 MiB, 64³/192³, 8,192 sites, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (persistent-Π §5.2, intent-channel) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **Cost check: the witness is a pure consumer of the publish on the cost profile of the reason-field sites, inside the ≈ 1–6 ms/tick sample budget, holds no patch, yields nothing, and adds no steered entity to the ≈ 2,000-cap — **matches**. **§2 ↔ `signature-predator.md` §1.1/§2.2 + `the-blight.md` §2 + `the-scavenger.md` §2.2 + `the-commensal.md` §2.2/§3 + `the-mirror-creature.md` §2 (the four absences — does not hunt / turn / feed / hold / echo, the cousin mechanics removed, fix 32) + §2.1 ↔ `reason-field.md` §2.1/§2.2/§3.1/§6a + `the-feral-instrument.md` §1/§2.2 + `qi-computation.md` §5.2 (the intent absent / the persistent-Π / the frontier, fix 32) + §3 ↔ `the-story.md` §2/§3.3 + `the-reading-ahead.md` §3 (not a sign — not the story's omen, not a portent, fix 32) + §4.1 ↔ `the-observatory.md` §2/§2.1 (the eye that watches the watcher, fix 32) + §4.2 ↔ `the-silence.md` §2/§3/§6a (the stillness given presence, fix 32) + §4.3 ↔ `the-feral-instrument.md` §7 (the intent-channel held without the waking, fix 32) + §5e ↔ `field-hazards.md` §1/§5.1/§5.3 (the lawful non-row — no threat, no response, no counterplay; the never-hidden discipline; the cap, fix 32).** LATER with a Phase-1-legible framing. Open-Qs all owned (the neutral-presence probe, the non-sign honesty, the field-as-god overclaim). No ref-gaps. |
|| `the-lock.md` (wave 37) | ✓ | ✓ | ✓ | ● | clean — the becoming-permanent act, a binding deliberately made irreversible, the commitment instrument; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1, 64³/192³, 8,192 sites, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, π/ρ clamp 0.72, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (persistent-Π §5.2) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **§2/§3 ↔ `the-oath.md` §1/§3/open-Q4 + `the-treaty.md` §1/§2.4/§4 (the permanent sibling / the permanent full stop — the vow's severability answered in the negative, fix 33) + §2.1 ↔ `the-rite-of-passage.md` §2.3/§3.2 (the binding lifted to structures, fix 33) + §2.1 ↔ `the-name.md` §1/§2/§6e (the holding made irreversible, fix 33) + §2.3 ↔ `seed-garden.md` §3/§4.2/§3.3 (the locked seed-line, fix 33) + §3 ↔ `the-exile.md` §2/§4/§6d (the no-amnesty forward, fix 33) + §2 ↔ `house-that-steers.md` §1.1/§3.2/§5b (the held core locked, fix 33) + §4 ↔ `the-inheritance.md` §1/§2/§8 (the line's survival, fix 33) + §5d ↔ `energy-harnessing.md` §6 (the cap, taken to permanent, fix 33).** MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (release-refusal's boundary, the durable-mistake cost, the permanence's outliving). No ref-gaps. |
|| `the-commons-tithe.md` (wave 37) | ✓ | ✓ | ✓ | ● | clean — the funded commons, the voluntary-but-expected contribution, the commons' price; canonical set cited verbatim (≈6 MiB, 192³/64³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000); theory (coherence-commons ∏ 1/(1−q_i), persistent-Π §5.2) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **Canonical check: the tithe's op-record `{member, op, worldPos, rung, magnitude, sustain}` matches `schema-that-settles.md` §2.1 verbatim — verified, a tithe is the settled record's booked contribution pointed at the commons.** **§2 ↔ `shared-ledger.md` §1.2/§2/§5/§6d/§6c (the booked commons' share, fix 33) + §3 ↔ `field-npc-ai.md` §3.1/§3.2/§3.3 (the funded commons, fix 33) + §2 ↔ `house-that-steers.md` §1/§2.2 + `the-observatory.md` §1/§2 + `the-harbor.md` §2b/§2c/§3/§4 (the funded objects, fix 33) + §3 ↔ `the-school.md` §2.2/§3 (the funded competence, fix 33) + §2 ↔ `the-market.md` §2/§2.3 (the regular sibling, fix 33) + §2.4 ↔ `the-census.md` §2.1/§2.2 + `the-window-pulse.md` §2/§3 (the active tither / the healthmeter's funding, fix 33) + §4 ↔ `the-exile.md` §4 (the declining share, fix 33) + §5 ↔ `the-gift.md` §2.1/§3.1/§6d (the booked warm — the gift's booked inverse, fix 33).** MEDIUM with a Phase-1-legible framing. Open-Qs all owned (the voluntary-but-expected line, the commons' price, the non-coercive lever). No ref-gaps. |
|| `the-marsh.md` (wave 37) | ✓ | ✓ | ✓ | ● | clean — the tessellated q, the honest hiding surface, the sea's shallow textured bound; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1, 64³/192³, 8,192 sites, ξ=φ⁶≈17.94, φ⁻²≈0.382, τ_c=0.5, π/ρ clamp 0.72, ω₀²=20.0, dt=0.05, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity, c_s=h₀/dt). **Canonical check: the marsh's q-patchiness and its hiding hold the no-free-energy cap — a marsh provides nothing, no stealth-yield (§7d) — verified, the tessellated `q` is a read of the published channels, never a gain.** **§2 ↔ `the-sea.md` §2b/§2a/§3/§4/§5b (the textured cousin of the flat plain, fix 33) + §2 ↔ `the-swim.md` §2a/§2b/§5b (the shallow swim, fix 33) + §3 ↔ `signature-predator.md` §1/§1.2/§2/§3/§7e/§8 (the trail-read's honest failure — the pattern blurs into the texture, fix 33) + §3 ↔ `life-signal.md` §3/§2/§6b (the hidden read — the patchy `q` blurs the classes at a distance, fix 33) + §3/§4 ↔ `the-vigil.md` §3/§5e (the honest cover for the exposed, fix 33) + §3 ↔ `the-walk.md` §2c/§4b (the absorbed wake, fix 33) + §5 ↔ `field-emergent-ecology.md` §2.2/§4.2/§6b (the tessellated habitat, fix 33) + §2 ↔ `energy-harnessing.md` §2/§6 (the low-flow cost / the cap, fix 33) + §5 ↔ `the-sea-floor.md` §2a/§2b (the shallow-scale edge, fix 33).** MEDIUM with a Phase-1 legible slice. Open-Qs all owned (the tessellation's honesty, the symmetric hiding, the trail-read's failure). No ref-gaps. |
|| `the-husbander.md` (wave 37) | ✓ | ✓ | ✓ | ● | clean — the practice, the honest return, the wild's staying; the corpus's third practice; canonical set cited verbatim (≈6 MiB = `q` 1 + `pot` 1 + `∇(g·Φ)` 3 + `ρ` 1, 192³/64³/12³, dt=0.05, τ_c=0.5, φ⁻²≈0.382, ξ=φ⁶≈17.94, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (persistent-Π §5.2) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **Canonical check: the husbander's shed holds the cap — the `(1−q)` waste is spent, never a harvest, never a mint (§5d); the shed is a gift to the wild, un-booked, net-negative — verified.** **§2a ↔ `the-walk.md` §2/§3/§4a/§4c/§4d (the patch's health read — the walk's craft turned from crossing to tending, fix 33) + §2a ↔ `the-vigil.md` §1/§3/§5b (the wild's watch — the first practice extended, fix 33) + §2a ↔ `the-working-song.md` §1/§2.1 (the third practice — the rhythm held alone, fix 33) + §3 ↔ `farm-that-feeds.md` §2/§4/§6 (the anti-owner, fix 33) + §4 ↔ `the-commensal.md` §2/§3/§5b (the wild's habitat, fix 33) + §2b ↔ `the-blight.md` §2/§3/§4.2/§5e (the early clearing, fix 33) + §2b/§4 ↔ `the-scar-lifecycle.md` §2.1/§2.2 (the healed scar, fix 33) + §2c ↔ `the-cold.md` §2/§3/§6b (the thin-season's shed, fix 33) + §5d ↔ `energy-harnessing.md` §2/§6 (the un-booked shed, fix 33) + §2c/§3 ↔ `the-gift.md` §1/§2/§6d (the shed as a gift, fix 33).** MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (the care's cost, the blight-seed read, the no-book honesty). No ref-gaps. |
|| `the-guardian.md` (wave 38) | ✓ | ✓ | ✓ | ● | clean — the bound keeper, the territorial order-side made permanent, the keeping; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, φ⁻²≈0.382, ξ=φ⁶≈17.94, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈6 MiB, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (persistent-Π §5.2) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **§2.1 ↔ `the-landform-name.md` §2/§4/§5a (the named place made bound, fix 34) + §2.1 ↔ `the-name.md` §1/§2/§6d/§7 (the holding made a keeper, fix 34) + §3 ↔ `the-commensal.md` §2/§3/§5c/d/e (the territorial order-side — the assist turned to defense, net-negative, fix 34) + §2.1 ↔ `the-threshold.md` §1/§2.2/§6c/§6d (the boundary's keeper, fix 34) + §3.1 ↔ `the-blight.md` §2/§6e (the wrong-band's warden, fix 34) + §3.2 ↔ `signature-predator.md` §1/§2/§4.4/§7e (the hunter's refuser, fix 34) + §4 ↔ `the-witness.md` §1/§2/§7 (the warden-twin — the witness watches, the Guardian keeps, fix 34) + §2.3 ↔ `life-signal.md` §3/§3.1/§6a/b/§6d (the live-and-bound read, fix 34) + §4 ↔ `the-mirror-creature.md` §2/§5c/d/e (the distinct face — bound to a place, not a person, fix 34) + §2.2 ↔ `field-emergent-ecology.md` §2.2/§4.2/§6b/§5.3 (the bound morphology, fix 34) + §2.1 ↔ `the-cave.md` §4/§5d (the shelter's keeper, fix 34).** The guardian's binding holds the no-free-energy cap (a Guardian converts nothing, never a mint; §5d) — **matches**. MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (the binding's scale, the keeping's cost, the territorial-warning honesty). No ref-gaps. |
|| `the-archive.md` (wave 38) | ✓ | ✓ | ✓ | ● | clean — the everything, the complete record held raw, the raw's truth; canonical set cited verbatim (≈6 MiB, 64³/192³, 8,192 sites, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000); theory (persistent-Π §5.2) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **Canonical check: the archive's raw record rides the settled op-record `{member, op, worldPos, rung, magnitude, sustain}` (schema-that-settles §2.1 verbatim) — the raw's atomic unit matches — verified.** **§2 ↔ `shared-ledger.md` §1.2/§1.3/§6c/§6d (the full history held raw, fix 34) + §2.1 ↔ `schema-that-settles.md` §2/§2.1/§2.2/§5 (the record held raw, fix 34) + §3 ↔ `the-stratum-read.md` §1/§2/§2.4/§3/§5e (the strata held raw, fix 34) + §2 ↔ `the-chronicle.md` §1/§3.3/§5/§6d/§6e (the raw of the shaped, fix 34) + §4 ↔ `the-memory-palace.md` §2/§4/§6d/§7 (the raw of the chosen, fix 34) + §2 ↔ `the-name.md` §1/§3.3/§6d/§7/§4 (the named lives' full record, fix 34) + §2 ↔ `field-archaeology.md` §2/§1.2/§6b/§5.3 (the complete shadow's source — the Archive is the record the residue is the shadow of, fix 34) + §2 ↔ `the-language.md` §2/§5 (what the script can carry, fix 34) + §6 ↔ `energy-harnessing.md` §2/§4.1/§4.4/§6 (the held store — the Archive is a store, never a mint, fix 34) + §2 ↔ `the-census.md` §2 (the population history, fix 34) + §2.1 ↔ `the-dispute.md` §2.1/§6d (the raw ground — the claim checked against the raw, not a shaped story, fix 34).** The Archive's heavy hold at un-selected scale rides the memory-palace's maintained-cost model (standing op, never free) — the no-free-energy cap held (a store, never a mint) — **matches**. MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (the selection rule, the hold's cost at scale, the raw's retention). No ref-gaps. |
|| `the-granary.md` (wave 38) | ✓ | ✓ | ✓ | ● | clean — the store, the honest buffer, the bleed held through the thin; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1, 192³/64³, dt=0.05, τ_c=0.5, φ⁻²≈0.382, ξ=φ⁶≈17.94, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, 8,192 sites); theory (persistent-Π §5.2) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **Canonical check: the granary's deposits/draws book the way any op does, on the settled record `{member, op, worldPos, rung, magnitude, sustain}` (schema §2.1 verbatim); the store's hold-pays its bleed (`(1−q)` waste), a granary converts nothing — the no-free-energy cap held — verified.** **§4 ↔ `farm-that-feeds.md` §2/§4/§5/§6/§7 (the yield held, fix 34) + §2 ↔ `the-tool.md` §2/§3/§4d (the kept steel's store, fix 34) + §3 ↔ `seed-garden.md` §3/§2.1/§7 (the plenty-side twin, fix 34) + §4 ↔ `the-memory-palace.md` §2/§3/§4/§6d (the matter-side twin, fix 34) + §4 ↔ `the-market.md` §1/§2.1/§2.2/§6d (the store of the circulated, fix 34) + §2 ↔ `the-cold.md` §2/§3/§6e (the thin-season's buffer, fix 34) + §2a ↔ `the-fallow.md` §2a/§5d (the spent-draw bound, fix 34) + §6 ↔ `energy-harnessing.md` §2/§4.4/§6 (the held store's bleed, fix 34) + §2 ↔ `house-that-steers.md` §1/§2.2/§5d/§5b (the room's hold, fix 34) + §2.1 ↔ `schema-that-settles.md` §2.1/§2.2/§3 (the book of plenty, fix 34) + §1.2 ↔ `shared-ledger.md` §1.2 (the store's legibility, fix 34) + §2.1 ↔ `the-census.md` §2.1/§6e (the liveness's store, fix 34) + §2 ↔ `the-window-pulse.md` §2/§6e (the pulse's material half, fix 34).** MEDIUM with a Phase-1-legible slice. Open-Qs all owned (the buffer's size, the bleed's honesty, the draw's season). No ref-gaps. |
|| `the-wind.md` (wave 39) | ✓ | ✓ | ✓ | ● | clean — the flow, the carry, the cost-and-aid; the air's own field-velocity made a read; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1; the medium-velocity `FieldVel` read as the atmosphere's fifth rendered channel, never a new canonical additive; 64³/192³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, π/ρ clamp 0.72, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity, c_s=h₀/dt). **Canonical check: the wind's carry holds the no-free-energy cap — a wind provides nothing, never farmable (§6), the coherence turbine's damping stills the band — verified, the wind is a read of the medium-velocity channel, never a gain.** **§2/§3 ↔ `field-hazards.md` §2/§5.1/§5.3 (the flow-face of the storm — the front a wind moves, readable-before-it-arrives, never farmable, fix 35) + §2 ↔ `atmosphere-orbits-auroras.md` §1.3/§1.5/§2.2/§6/§2.4 (the air moving — `FieldVel`, wind lines, the coherence turbine, the altitude wind, fix 35) + §6 ↔ `the-zenith.md` §1/§2 (the ceiling's flow, fix 35) + §2 ↔ `weather-not-storm.md` §2/§3/§6 (the provenance sibling — what carries what, fix 35) + §2 ↔ `coherence-highway.md` §1/§1.1/§6b/§6d (the descent at your back — the tailwind, fix 35) + §2 ↔ `the-walk.md` §2/§2a/§4b/§4d (the stride's re-price, fix 35) + §2 ↔ `the-blight.md` §2/§3/§6e (the spore-carrier, fix 35) + §2/§6 ↔ `energy-harnessing.md` §2/§2.2/§1.7/§6 (the un-farmable flow, fix 35) + §2/§3 ↔ `the-marsh.md` §2/§3 (the air's marsh — the moving face, fix 35) + §2 ↔ `signature-predator.md` §1.2 (the signature-carrier, fix 35).** MEDIUM with a Phase-1-legible slice. Open-Qs all owned (the carry's provenance, the turbine's honesty, the altitude wind's gate). No ref-gaps. |
|| `the-season-change.md` (wave 39) | ✓ | ✓ | ✓ | ● | clean — the crossing, the least-legible moment, the branch's turn; the field's actual shift the calendar approximates; canonical set cited verbatim (≈6 MiB, 64³/192³, dt=0.05, τ_c=0.5, q≈0.947, q~1e-3…1e-1, ξ=φ⁶≈17.94, φ⁻²≈0.382, ≈1–6 ms, ≈2,000); theory (mixing clock T) flagged non-canonical with the speculation flag carried (cited through the tide/patient-field, never promoted). **§2 ↔ `tide-of-the-attractor.md` §2/§5a/§1.2/§5d (the crossing — the harvest/thin states, the turn's probe gate, fix 35) + §3 ↔ `the-window-year.md` §2/§3/§5a/§5b (the actual shift the calendar approximates, fix 35) + §1 ↔ `the-dawn.md` §1/§2/§5 (the seasonal sibling, fix 35) + §3/§4 ↔ `the-drift-road.md` §3.3/§3.4/§4d (the one-way turn toward the still, fix 35) + §2 ↔ `atmosphere-orbits-auroras.md` §2/§4/§3.3/§3.4 (the long-cycle turn — the approach reads from the sky, fix 35) + §3.2 ↔ `farm-that-feeds.md` §5/§2.2 (the harvest before the band dies, fix 35) + §3.2 ↔ `house-that-steers.md` §2.2/§3.4/§5d (the bath before it thins, fix 35) + §2 ↔ `patient-field.md` §3.3/§5b (the least-legible crossing, the loan dear, fix 35) + §2/§3 ↔ `the-cold.md` §2/§3/§5.3 (the turn into the thin, fix 35) + §4.2/§5d ↔ `energy-harnessing.md` §2/§6 (the un-gained crossing — a turn converts nothing, fix 35) + §3.1 ↔ `the-window-pulse.md` §2.1/§6e (the muddy-instrument read, fix 35).** MEDIUM with a Phase-1-legible framing. Open-Qs all owned (the crossing's timing, the least-legible moment's honesty, the branch's turn's fate). No ref-gaps. |
|| `the-cart.md` (wave 39) | ✓ | ✓ | ✓ | ● | clean — the ride, the load-and-gradient trade, the honest book; the wheeled vehicle that rides the route and carries the store; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1, 192³/64³, dt=0.05, ξ=φ⁶≈17.94, φ⁻²≈0.382, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity, c_s=h₀/dt). **Canonical check: the cart's load books the way any op does — on the settled op-record `{member, op, worldPos, rung, magnitude, sustain}` (schema §2.1 verbatim); the load-and-gradient trade holds the cap (a cart converts nothing) — verified.** **Honest negative (open-Q6): `the-camp.md` does not exist on disk — the cart's camp-freight face is flagged `[assumption]` and NOT filled in (no forced citation to a non-existent doc); the ride/load/book with market and farm freight is the landed core.** **§1 ↔ `coherence-highway.md` §1/§1.2/§4/§6b/§6c/§6d (the route's rider, fix 35) + §2 ↔ `the-walk.md` §2/§2a/§3/§4a/§4c (the wheeled burden — the walk's loaded twin, fix 35) + §3 ↔ `the-granary.md` §2.1/§3/§4/§5d (the store carried, fix 35) + §2 ↔ `the-market.md` §1/§2/§2.2/§6d (the freight the market takes, fix 35) + §2 ↔ `the-tool.md` §2b/§3/§4b (the shared wear, fix 35) + §2 ↔ `the-burden.md` §1/§2/§4 (the wheeled load, fix 35) + §1 ↔ `energy-harnessing.md` §1.1/§4.1/§2/§6 (the free haul, the paid wear, fix 35) + §2 ↔ `house-that-steers.md` §1/§2.2/§5d (the structure on the move, fix 35) + §2.1 ↔ `schema-that-settles.md` §2.1/§2.2/§2.3/§3 (the load booked, fix 35).** PHASE-1-ABLE with a Phase-1 slice. Open-Qs all owned (the off-road freedom, the load's legibility, the camp's absent doc — honestly open, not filled). No ref-gaps. |
|| `the-breath.md` (wave 39) | ✓ | ✓ | ✓ | ● | clean — the reservoir, the hollow's breath, the lock's failure; the body-scale take of the descent; canonical set cited verbatim (≈6 MiB = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1, 192³/64³/12³, dt=0.05, ξ=φ⁶≈17.94, φ⁻²≈0.382, τ_c=0.5, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (persistent-Π §5.2) flagged non-canonical with the `reason-field.md` §6a speculation flag carried. **Canonical check: the breath holds the cap — a breath converts nothing; the reservoir is a store, never a mint (§6) — verified, the body's bleed is the `(1−q)` waste, never a gain.** **§1 ↔ `deep-field-diving.md` §1/§2/§2.2/§2.3/§3.1/§4/§7a/§7d (the priced descent — the same budget that bounds the Bell, every rung deeper costs lungs of held coherence, fix 35) + §3 ↔ `the-cave.md` §3/§4/§5d (the hollow's breath — the cave cannot refill a held breath, fix 35) + §2c ↔ `the-sea-floor.md` §2a/§2c/§5d (the shallow descent, fix 35) + §2a ↔ `the-swim.md` §2a/§2b/§5d (the stroke's breath, fix 35) + §2 ↔ `the-burden.md` §1/§2b/§4/§6a (the body-scale cost, fix 35) + §2 ↔ `the-tool.md` §2a/§2c/§4d (the bite at depth, fix 35) + §2/§4 ↔ `player-remains.md` §1/§1.2/§2.3/§5e (the lock's failure — the coherence-failure death, fix 35) + §2 ↔ `life-signal.md` §1/§3/§3.2/§6b/§6d (the maintained level — the dry-run is the body's own fossil beginning, fix 35) + §2/§6 ↔ `energy-harnessing.md` §2/§6 (the body's bleed, fix 35) + §2a ↔ `sleep.md` §2b/§3/§6d (the refill — the body's own recovery, never free, fix 35).** MEDIUM-LATE with a Phase-1-legible framing. Open-Qs all owned (the reservoir's size, the refill's honesty, the deep-dive gate). No ref-gaps. |
|| `the-herald.md` (wave 40) | ✓ | ✓ | ✓ | ● | clean — the field's voice, the announced augury, the turned-forward order, the loud twin of the watched presence; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (determinism §5.2) flagged non-canonical. **Canonical check: the herald provides nothing, never farms — a pure consumer of the publish on the reason-field cost profile; holds no patch, adds no entity to the ≈2,000 cap.** **§1 ↔ `field-emergent-ecology.md` §2.2/§4.2/§6b/§5.3/§1.4 (the recognized run), `life-signal.md` §3/§3.1/§6d (the live read), `signature-predator.md` §2/§3/§7e (the non-accumulator), `the-mirror-creature.md` §2/§5c/d/e (the announced news), `the-feral-instrument.md` §1 (the never-woken), `the-bell.md` §3/§5a/§6c/d/e (the crafted cousin); §2/§5b ↔ `the-witness.md` §1/§2/§5b (the loud twin), `the-reading-ahead.md` §1/§2.2/§2.3/§7c/§7d/§7a (the forward read), `the-guardian.md` §1/§3/§5b (the teller to the keeper), `weather-not-storm.md` §2/§3 (the announced provenance), `the-season-change.md` §1/§2.1/§3.1/§5b (the announced crossing), `fate-of-a-window.md` §1/§6c/§6e (the announced fork); §5c/d/e the inherited gates across the stack.**
|| `the-toll.md` (wave 40) | ✓ | ✓ | ✓ | ● | clean — the border's charge, the held door's price, the visitor's trust-by-law, the outside's entry at the marked crossing; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (doors §4) flagged non-canonical. **Canonical check: the toll's doors/trust-by-law cite `window-guests.md` §3/§6b (the visitor's provenance the toll must never misread) + `schema-that-settles.md` §2.1 (the op-record `{member, op, worldPos, rung, magnitude, sustain}` verbatim — the toll's own shape) — verified; the toll holds the cap (a toll never mints, never farms).** **§1/§3 ↔ `the-commons-tithe.md` §1/§3/§2.1/§5a (the external twin), `the-harbor.md` §2b/§2c/§3/§4 (the first door), `the-threshold.md` §1/§2.2/§3 (the second door), `the-treaty.md` §1/§2/§2.3/§2.2/§5d (the third door), `window-guests.md` §1/§2/§3/§6b (the travellers), `shared-ledger.md` §1.2/§2/§6d/§6c (the book), `the-market.md` §1/§2/§2.3/§3/§6d (the border-twin), `coherence-highway.md` §1/§4/§5.2/§6d (the road's upkeep), `house-that-steers.md` §1/§2.2/§3/§5d (the held border), `schema-that-settles.md` §2.1/§2.3/§3 (the atomic book), `the-dispute.md` §2/§3.1/§3.2 (the field-true charge), `the-census.md` §2.1/§2.4/§6d (the population's door) — all twelve two-way.**
|| `the-compost.md` (wave 40) | ✓ | ✓ | ✓ | ● | clean — the spent matter's re-turn, the heap, the time-and-lock, the built sibling of the wild glean; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (heap/time-and-lock §4) flagged non-canonical. **Canonical check: the compost's heap/time-and-lock holds the cap — `output ≤ φ⁻¹·input` (no-free-energy, §6 `energy-harnessing.md`), the compost returns order at a loss, never a mint — verified.** **§1/§3 ↔ `the-fallow.md` §2/§2b/§1/§5d (the spent state's return), `the-tool.md` §2b/§3/§4b/§4d (the worn steel's sink), `the-granary.md` §2.1/§6/§5d (the store's bleed's sink), `farm-that-feeds.md` §2/§4/§5 (the plot's feed), `the-scavenger.md` §2.1/§2.2/§5d (the built twin), `patient-field.md` §3.3/§1/§5 (the impatience it turns), `material-regimes.md` §3/§4 (the re-precipitation), `energy-harnessing.md` §2/§6 (the waste and the cap), `the-marsh.md` §3/§2 (the second plot's re-turn), `the-husbander.md` §1/§3/§6 (the built sibling), `schema-that-settles.md` §2.1/§2.3/§6d (the heap's book) — all eleven two-way.**
|| `the-carry.md` (wave 41) | ✓ | ✓ | ✓ | ● | clean — the pack, the carried matter, the honest weight on every movement, the corpus's inventory-primitive (field-read weight, never a hidden slot); canonical set cited verbatim (≈6 MiB, 64³/192³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (ε²-debt §5.2) flagged non-canonical. **Canonical check: the pack holds the cap — a carry converts nothing, no pack that yields; the heavier live-lock is a cost, never a gain (§4b) — verified.** **§1/§3 ↔ `the-burden.md` §1/§2/§2b/§4 (the matter-twin), `the-walk.md` §2/§2a/§2b/§3/§4a/§4c (the stride-cost's load), `the-swim.md` §2a/§4/§5c/d/e (the stroke's load), `the-cart.md` §1/§2/§3/§5a/§7 (the body-scale twin), `the-tool.md` §2a/§3/§4d (the single held arrangement), `the-lantern.md` §1/§2/§1.4 (the carried night-read), `life-signal.md` §3/§3.3/§6 N2 (the maintenance axis's load), `signature-predator.md` §2/§8/§7e (the loaded trail), `the-granary.md` §2/§6/§7 (the store at body-scale), `schema-that-settles.md` §2.1/§2.2/§2.3 (the pack's book), `energy-harnessing.md` §2/§6 (the cap) — all eleven two-way.**
|| `the-climb.md` (wave 41) | ✓ | ✓ | ✓ | ● | clean — the ascent, the handholds-as-a-read, the vertical's missing upward primitive, the fall's controlled-inverse; canonical set cited verbatim (≈6 MiB, 64³, 192³, 8,192 sites, ξ=φ⁶≈17.94, φ⁻²≈0.382, τ_c=0.5, ω₀²=20.0, dt=0.05, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (gradient-ownership §5.2) flagged non-canonical. **Canonical check: a climb converts nothing harder, at the vertical — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified. The climb↔carry two-way write-race is landed: the climb honestly flagged the carry's absence (its cross-refs read 'NOT ON DISK', grounded in the-burden alone); the carry now exists, and each reads the other two-way (the climb's cross-ref updated to a real `the-carry.md` pointer; the carry's three absence-notes rewritten as landed arrival).** **§1/§2 ↔ `the-fall.md` §1/§2/§4.2/§5a/§5c/§5d (the controlled-inverse), `the-walk.md` §2/§2a/§3/§4a/§4d (the vertical-twin), `the-zenith.md` §1/§2b/§4b (the place), `material-regimes.md` §4 (the readable handholds), `energy-harnessing.md` §1.1/§2/§6 (the gradient and the waste), `the-burden.md` §1/§2/§6a (the carried cost at height), `coherence-highway.md` §4 (the unmaintained-route contrast), `player-remains.md` §1/§4 (the fall's death), `field-hazards.md` §4/§5.1 (the honest dangers at height), `life-signal.md` §3 (the held lock at height) — all ten pass-spec two-way, plus the climb↔carry special.**
|| `the-gatekeeper.md` (wave 41) | ✓ | ✓ | ✓ | ● | clean — the office, the human twin of the kept warden, the field-true judgment of who passes the held door; canonical set cited verbatim (≈6 MiB, 192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity, ε²=(EY−φ·EI)²); theory (persistent Π §5.2 `qi-computation.md`) flagged non-canonical. **Canonical check: the office holds the cap — a gatekeeper never mints, never farms; a denied crossing yields nothing of value, only the honest refusal — verified.** **§1/§2.3 ↔ `the-threshold.md` §1/§2.2/§3/§6 (the judge at the door), `the-harbor.md` §2b/§2c/§3/§4/§5b (the door-side twin), `the-guardian.md` §1/§2.3/§3/§5d/e/§7 (the creature-twin), `window-guests.md` §1/§2/§3/§4.1/§6b (the admitted-guests' judge), `life-signal.md` §3/§3.3/§4/§6a/§6d (the judge's read), `signature-predator.md` §2/§3/§7d/§8/§7e (the deliberate-vent read at the door), `the-blight.md` §2/§6e/§5e/§7 (the refused arrival), `the-census.md` §2/§2.1/§2.4/§7 (the roster's door), `shared-ledger.md` §1.2/§6c/§6d/§6e (the member-line), `the-dispute.md` §2/§4/§6c/d/e (the field-true refusal), `the-observatory.md` §1/§2/§3/§6e (the door's observatory) — all eleven two-way.**
|| `the-causeway.md` (wave 41) | ✓ | ✓ | ✓ | ● | clean — the raised way, the clean crossing above the hiding, the honest trade and the swallow; canonical set cited verbatim (≈6 MiB, 192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (the swallow §4) flagged non-canonical. **Canonical check: a causeway converts nothing, no crossing that yields — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the deck's standing draw holds the cap — verified.** **§1/§3 ↔ `the-marsh.md` §2/§3/§4/§6c/§7/§8 (the hiding water crossed), `the-walk.md` §2/§2a/§2c/§3/§4c/d/e (the clean transit's deck), `the-cart.md` §2/§3/§4/§7 (the deck the road's vehicle rides), `house-that-steers.md` §1/§1.1/§2/§3/§3.4/§5d (the deck's held form), `energy-harnessing.md` §2/§4.1/§4.4/§6 (the deck's cost and cap), `the-threshold.md` §1/§2.2/§4/§5d/§6b (the crossing's boundary-marks), `life-signal.md` §3/§6d (the clean crossing's read), `signature-predator.md` §1/§1.2/§2/§7e/§8 (the clean line's honest trade), `coherence-highway.md` §4/§4.2/§6b/§6d (the marsh's highway segment) — all nine two-way.**
|| `the-rain.md` (wave 42) | ✓ | ✓ | ✓ | ● | clean — the gentle fall, the nourishing-but-wet, the flood's beginning, the fallow's season's water; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (envelope-wave §4) flagged non-canonical. **Canonical check: the rain gives back at the field's own yield, never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the flood-beginning is readable, the gentle fall never a farm — verified. The rain↔spring two-way write-race is landed: both flagged the other's absence honestly; now both are on disk and each reads the other two-way (the-rain's four absence-notes rewritten as landed arrival; the-spring's cross-ref + open-Q1 closed as the landed nourishing rain).** **§1/§2 ↔ `the-flood.md` §2/§3/§4.1/§6(b)/§6(e) (the gentle twin), `farm-that-feeds.md` §2/§5/§3/§4 (the season's water), `the-wind.md` §1/§3/§5(b)(c)(d)(e) (the flow's carry), `the-marsh.md` §3/§8 (the blur on a smaller scale), `life-signal.md` §1/§3/§3.2/§6b (the rainy walk's read), `the-fallow.md` §1/§3 (the season's return), `weather-not-storm.md` §2 (the clearest weather verdict), `the-sea.md` §2c/§4/§5b (the water cycle), `energy-harnessing.md` §2/§6 (the wet cost and the cap), `field-hazards.md` §5.1 (the readable-before-it-arrives case) — all ten pass-spec two-way, plus the rain↔spring special.**
|| `the-spring.md` (wave 42) | ✓ | ✓ | ✓ | ● | clean — the well, the point of fame, the drawn order, the fallow's full twin at the fixed place; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (stationarity §5.2) flagged non-canonical. **Canonical check: a spring provides nothing beyond its own welling — the fixed source is the field's own, never a mint (`output ≤ φ⁻¹·input` §6 `energy-harnessing.md`); the point of fame is a cost, never a farm (§7e `signature-predator.md`) — verified.** **§1/§3 ↔ `the-fallow.md` §1/§2/§2a/§5b/§6d (the full twin), `resonance-seeds.md` §1/§2/§6a (the ambient contrast), `seed-garden.md` §2/§3/§4.2 (the live well counter), `field-emergent-ecology.md` §2.2/§4.2/§1.4 (the stationary counter), `the-granary.md` §2/§3/§5d/§7 (the drawn-and-stored), `the-carry.md` §2/§4b/§5c/d/e (the drawn pack), `the-landform-name.md` §1/§2/§5d/§5e (the named source), `the-guardian.md` §1/§3/§5d/§7 (the territorial read), `life-signal.md` §3/§6c/§6d (the maintained-live source), `signature-predator.md` §2/§7e (the fixed landmark), `energy-harnessing.md` §2/§1.7/§6/§7 Q1 (the well's cap), `material-regimes.md` §3/§4 (the fixed re-precipitation) — all twelve pass-spec two-way, plus the spring↔rain special.**
|| `the-mimic.md` (wave 42) | ✓ | ✓ | ✓ | ● | clean — the worn shape, the drift, the provenance read that catches it, the borrowed line that sheds at the field's judgment; canonical set cited verbatim (ε²=(EY−φ·EI)², q≈0.947, q~1e-3…1e-1, φ⁻²≈0.382, τ_c=0.5, ξ=φ⁶≈17.94, ≈6 MiB, ≈1–6 ms, ≈2,000, dt=0.05); theory (persistent Π §5.2 `qi-computation.md`, phase-matching M §1 `magic-systems.md`) flagged non-canonical. **Canonical check: a mimic converts nothing, the borrowed shape is spent never a gain — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`), the borrow's cost is the `(1−q)` waste law, never a farm — verified.** **§1/§2 ↔ `the-mirror-creature.md` §1/§2/§2.2/§3.2/§4.1/§5b-2/§7 (the worn-shape twin), `signature-predator.md` §1/§2/§2.2/§3/§7e/§8 (the seduction-vs-ambush line), `window-guests.md` §1/§2/§3/§6b (the borrowed provenance), `life-signal.md` §1/§3/§3.1/§3.2/§6b (the legacy tell), `shared-ledger.md` §1.2/§6c/§3.3/§6e/§6b (the provenance read that catches it), `the-gatekeeper.md` §1/§2/§2.1/§5c/d/e (the reason the office exists), `the-commensal.md` §1/§4/§5c/d/e (the order-side contrast), `field-emergent-ecology.md` §2.2/§6b/§3.1/§4.1/§1.4 (the borrowed morphology), `the-feral-instrument.md` §1/§5d/e (the borrowed woken being), `the-dispute.md` §2/§2.1 (the lie it sheds), `the-witness.md` §1/§2/§5c/d/e (the inverting twin), `energy-harnessing.md` §2/§6 (the borrow's cost) — all twelve two-way.**
|| `the-stilling.md` (wave 43) | ✓ | ✓ | ✓ | ● | clean — the inner hold, the practice-not-power, the drift toward the stillness-hazard if too deep; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory ((1−q) mix-clock `T=2π/[λ(1−q)]` §patient-field) flagged non-canonical. **Canonical check: a stilling converts nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the voluntary hold is spent, never free; the stilled body reads quieter but quiet is what the Coda reads — a practiced stilling is not a stealth mechanic — verified.** **§1/§3 ↔ `the-vigil.md` §1/§3/§5b/§5a/§5d (the inner sibling), `the-working-song.md` §1 (the motionless twin), `the-stillness.md` §1/§2/§4.3/§6b/§6c (the drifter's edge), `life-signal.md` §1/§3/§3.2/§6a/b/§6c/§6d (the hold turned inward), `energy-harnessing.md` §2/§6 (the voluntary hold's cost), `signature-predator.md` §2/§7e/§8 (the quieter read), `the-silence.md` §1/§2 (the cousin turned inward), `the-fall.md` §2 (the body's own hold), `sleep.md` §1/§2b/§2.1 (the shallow cousin) — all nine two-way.**
|| `the-roost.md` (wave 43) | ✓ | ✓ | ✓ | ● | clean — the homes, the legible vulnerability, the wild's own order, where a run settles; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (marginal habitat §5.2) flagged non-canonical. **Canonical check: a roost provides nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); a nest provides nothing, the presented reading never a spawned den — verified.** **§1/§2 ↔ `field-emergent-ecology.md` §4.2/§2.2/§6b/§1.4/§3.1/§5.3 (the nested run), `signature-predator.md` §1/§2/§7c/§2.3/§7e (the predator's home), `the-scavenger.md` §2.2/§2.1/§4/§5b/§5c/d/e (the den), `the-commensal.md` §2/§3/§2.2/§7 (the hollow), `the-guardian.md` §1/§3/§4/§5e (the keep's home), `the-feral-instrument.md` §2.2/§5d/§5e/§7 (the feral's found home), `the-mirror-creature.md` §2.3/§5 (the mirror's margin), `field-archaeology.md` §2/§3.2/§7/§1.2 (the residue model's den), `life-signal.md` §3/§3.1/§6d (the held place's read), `energy-harnessing.md` §2/§6 (the cap), `field-hazards.md` §5.1/§1/§5.3 (the legible home) — all eleven two-way.**
|| `the-dive.md` (wave 43) | ✓ | ✓ | ✓ | ● | clean — the descent, the deep's own work, the commitment, the vertical's missing willed down-movement; canonical set cited verbatim (≈6 MiB, 64³, 192³, 8,192 sites, ξ=φ⁶≈17.94, φ⁻²≈0.382, τ_c=0.5, ω₀²=20.0, dt=0.05, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity, a=−G_N·(π/ρ)·∇(g·Φ)); theory (coherence budget B §2.3 `deep-field-diving.md`, full-cascade discharge §4.3 `coherence-magic.md`) flagged non-canonical. **Canonical check: a dive converts nothing, never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the honest risk is the lock's failure at depth — verified.** **§1/§2 ↔ `deep-field-diving.md` §2.1/§2.2/§2.3/§3.1/§7a/§7d (the un-protected mirror), `the-fall.md` §1/§2/§4.3/§5c/§5d (the desired descent), `the-climb.md` §1/§2/§2.1/§3/§4.2/§5a (the logic inverted), `the-breath.md` §1/§2/§3/§4.1/§5b/§5d (the reserve's descent), `the-swim.md` §2a/§2b/§4/§5d (the medium turned down), `the-cave.md` §3/§4/§5d (the hollow entered), `the-burden.md` §1/§2/§6a (the carried descent), `player-remains.md` §1/§4/§2.3/§2.4 (the honest risk), `energy-harnessing.md` §1.1/§2/§4.4/§6 (the descent-tax and the cap), `the-sea-floor.md` §1/§2c (the shallow form), `the-stratum-read.md` §2 (the descent's survey) — all eleven two-way.**
|| `the-between.md` (wave 43) | ✓ | ✓ | ✓ | ● | clean — the lawful dark, not another world, the edge, the mixture's empty remainder; canonical set cited verbatim (≈6 MiB, 64³, 192³, q≈0.947, q~1e-3…1e-1, ξ=φ⁶≈17.94, φ⁻²≈0.382, τ_c=0.5, dt=0.05, c_s=h₀/dt, ≈1–6 ms, ≈2,000, 8,192 sites); theory (local-field-mixture §1.2 `world-seams.md`) flagged non-canonical. **Canonical check: the between provides nothing, the dark is never a gain — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the between's laws (thin / ringing / lawful) cite `the-interstitial.md` §2 verbatim; the cartography is honestly partial, never a map — verified.** **§1/§2 ↔ `the-interstitial.md` §1/§2/§3/§4/§5 (the un-windowed face), `world-seams.md` §1.2/§2.1/§2.2/§2.3/§4.3/§6/§7 (the empty measure), `the-harbor.md` §1/§2/§3/§4/§5b (the door's outside), `the-atlas-of-windows.md` §1/§2/§4b/§4d (the record's partialism), `window-guests.md` §1/§2/§3/§6b (the people), `the-treaty.md` §1/§2/§4/§6d (the compact's other party), `the-witness.md` §1/§2/§5b (the neutral eye), `the-herald.md` §1/§2/§5 (the far news), `pocket-cosmos.md` §1.2/§1.3/§4.1 (the pocket's outside), `async-field-domain.md` §1–2/§7 Q1 (the un-windowed medium), `energy-harnessing.md` §2/§6 (the glow and the cap), `deep-field-diving.md` §1/§6 (the dark's distinct depths), `the-pilgrim.md` §2/§3/§5d (the walker of the dark) — all thirteen two-way.**
|| `the-beacon.md` (wave 44) | ✓ | ✓ | ✓ | ● | clean — the mark, the double-edged mark, the held light, the standing burn at the settlement's deliberate edge; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (standing-draw §4.4 `energy-harnessing.md`) flagged non-canonical. **Canonical check: a beacon converts nothing, no mark that yields — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); "to be findable is to be found" is the honest double-edge, never a farm — verified. The beacon↔moth two-way special item is LANDED: open-Q5's light-drawn being is the Moth; the Moth's cross-refs carry the resolving reverse pointer verbatim, the beacon's two absence-notes rewritten as landed arrival.** **§1/§2 ↔ `the-lantern.md` §1/§2/§4/§5b/§5d/§5e (the fixed twin), `the-bell.md` §1/§3 (the constant-mark contrast), `the-observatory.md` §1/§2/§2.1 (the inverted read), `the-harbor.md` §2b/§3/§6/§5d (the first edge's mark), `the-threshold.md` §1/§6/§5d/§5e (the second edge's mark), `the-causeway.md` §1/§3/§8 (the third edge's mark), `house-that-steers.md` §1/§1.1/§3/§5b/§5d (the standing hold), `energy-harnessing.md` §2/§4.4/§5.4/§6 (the mark's draw and cap), `signature-predator.md` §2/§7e/§8 (the bright place's gather), `the-walk.md` §1/§2/§4d (the crossing's finding-light), `world-seams.md` §2.2 (the near-light cousin), `the-spring.md` §3/§5d (the drawn mark) — all twelve, plus the beacon↔moth special.**
|| `the-shout.md` (wave 44) | ✓ | ✓ | ✓ | ● | clean — the call, the presence-as-act, the honest cost, one untrained broadcast loud enough to be found; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (Q4 lane §5.1 `coherence-magic.md`) flagged non-canonical. **Canonical check: a shout never mints — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the projection is the body's own signature spent at its broadcast; a shout that "pulled" help mechanically would be a false call the field sheds — verified.** **§1/§2 ↔ `the-working-song.md` §1/§2 (the single-impulse sibling), `field-music.md` §1/§6 (the blunt-twin), `the-bell.md` §1/§5a/§6c/d/e/open-Q5 (the body's alarm), `life-signal.md` §3/§3.3/§6a/b/§6c/d (the loud register), `signature-predator.md` §2/§7e/§8 (the warn), `the-herald.md` §1/§2/§5 (the body's answer), `player-remains.md` §1/§4/§5e/§6 (the found-body's act), `the-stilling.md` §1/§4/§5a/b/§5c/d/e (the loud-twin), `the-vigil.md` §3/§5b (the watch's own alarm), `energy-harnessing.md` §2/§6 (the projection's cost), `the-silence.md` §1/§3.2 (the loud-inverse), `the-census.md` §2/§6d (the roster's loud call) — all twelve two-way.**
|| `the-moth.md` (wave 44) | ✓ | ✓ | ✓ | ● | clean — the want, the brightness-as-both, the peaceable-lust, the drawn-in wild twin coveting the standing burn; canonical set cited verbatim (ε²=(EY−φ·EI)², q≈0.947, q~1e-3…1e-1, φ⁻²≈0.382, τ_c=0.5, ξ=φ⁶≈17.94, ≈6 MiB, ≈1–6 ms, ≈2,000, dt=0.05); theory (persistent Π §5.2, phase-matching M §1) flagged non-canonical. **Canonical check: a moth converts nothing, the coveting is spent, never a mint — `output ≤ φ⁻¹·input` + `E_waste=(1−q)·E_throughput` (no-free-energy §6, waste §2 `energy-harnessing.md`) — verified. The beacon↔moth two-way special item: the Moth's open-Q1 defers to the director's pointer decision, and the resolving reverse pointer is in-the-doc ("the Beacon is the standing mark whose *called* the Moth resolves into the coveter"); the Moth's cross-ref reads the Beacon's open-Q5 as its answer — the coveter is landed.** **§1/§2 ↔ `the-lantern.md` §1/§2/§5d (the coveted glow), `the-beacon.md` §2/§3/§5b/§6 + open-Q5 (the standing burn's *called*), `the-spring.md` §2.1/§3/§5/§6/§5d (the sought bright point), `the-observatory.md` §1/§2/§6d (the lit window's draw), `window-guests.md` §1/§2 (the drawn-in wild twin), `signature-predator.md` §1/§2.2/§3/§7e/§8 (the opposite hunt), `the-scavenger.md` §2.2/§4/§5c/d/e (the light-counter), `the-commensal.md` §2/§3/§5c/d/e (the pulled inverse), `life-signal.md` §1/§3/§3.1/§6a/§6b/§6c (the bright-line approach), `field-emergent-ecology.md` §2.2/§6b/§4.2/§1.4 (the coveting run), `energy-harnessing.md` §2/§6/§5.4 (the coveting and the cap), `the-mirror-creature.md` §1/§2 (the told-apart face), `the-witness.md` §1/§2 (the drawn-different) — all thirteen, plus the beacon↔moth special.**
|| `the-quarry.md` (wave 45) | ✓ | ✓ | ✓ | ● | clean — the cut, the scar-and-yield, the honest economy, the one-way run-out made a place; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (deep-rung reaper §2.5 `energy-harnessing.md`) flagged non-canonical. **Canonical check: a quarry converts nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the take's deposits/draws book on the settled op-record `{member, op, worldPos, rung, magnitude, sustain}` verbatim (§2.1 `schema-that-settles.md`); the cut's spent face is turned back at a loss, never a mint — verified.** **§1/§2 ↔ `the-fallow.md` §1/§2a/§3/§5(b)/§5d (the one-way run-out's place), `the-tool.md` §2a/§2b/§3/§4b/§4d (the bite and the scar), `the-stratum-read.md` §1/§2/§3/§5(b)/§5(d) (the read before the cut), `the-scar-lifecycle.md` §2.1/§2.2/§2.3/§5b/§5d (the deliberate branch), `the-bedrock.md` §1/§2/§2b/§3/§5d/§6 (the floor the cut stops at), `the-cave.md` §2a/§2b/§4/§5d (the cut-form hollow), `material-regimes.md` §2/§4/§3/§7 (the exposed rung-layers), `the-compost.md` §1/§4/§2 (the giving-back partner), `energy-harnessing.md` §2/§2.5/§3/§6 (the deep-rung take), `schema-that-settles.md` §2.1/§2.3/§3 (the take's book), `field-archaeology.md` §1.2/§2/§2.3/§3.2/§5.3 (the residue's source), `the-granary.md` §2/§5d/§6 (the taken order's destination) — all twelve two-way.**|
|| `the-shepherd.md` (wave 45) | ✓ | ✓ | ✓ | ● | clean — the gathering, the field's own assembly, the honest no-reward, a being that moves and gathers (not a place); canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (flock §6c `field-emergent-ecology.md` entity budget) flagged non-canonical. **Canonical check: a shepherd provides nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the honest no-reward (a shepherd gathers, never mints) — verified.** **§1/§2 ↔ `the-roost.md` §1/§3/§4/§5c/d/e (the place-vs-being line), `the-scavenger.md` §2.2/§1/§4/§5b/§5c/d/e (the gathering's origin), `the-moth.md` §3.2/§1/§5b-1/§5d (the gathering's magnet), `the-commensal.md` §2/§3/§5c/d/e (the settle-beside contrast), `the-guardian.md` §1/§3/§5c/d/e (the bound-keep contrast), `field-emergent-ecology.md` §2.2/§6b/§4.2/§5.3/§6c/§1.4 (the morphology and the flock), `life-signal.md` §3/§3.1/§6a/b/§6d (the maintained-live assemblage), `field-archaeology.md` §2/§3.2/§7/§1.2 (the assemblage's trail), `energy-harnessing.md` §2/§6 (the waste and the cap), `the-witness.md` §1/§5c/d/e (the gatherer-opposite), `the-herald.md` §1/§2/§5 (the gathering's voice) — all eleven two-way.**|
|| `the-archivist.md` (wave 45) | ✓ | ✓ | ✓ | ● | clean — the office, the honest fallibility, the dispute's ground, the keeper of the raw un-shaped; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (Π-frontier §7 `the-name.md`) flagged non-canonical. **Canonical check: the archivist holds the settled op-record `{member, op, worldPos, rung, magnitude, sustain}` raw verbatim (§2/§2.1/§3 `schema-that-settles.md`); the office records, never mints (§6d); the honest fallibility — cannot corrupt the raw since the single non-forgeable point is the book's own — verified.** **§1/§3 ↔ `the-archive.md` §1/§3/§4/§2.4/§5/§6 (the raw's keeper), `the-chronicle.md` §1/§3.3/§5/§6d (the shaping office's first contrast), `the-memory-palace.md` §2/§3/§4/§6d (the choosing office's second contrast), `the-gatekeeper.md` §1/§2/§4/§6 (the door's office sibling), `the-school.md` §2/§2.2/§4/§6 (the teaching office's third contrast), `shared-ledger.md` §1.2/§6c/§6d/§6b/§6e (the member-line's full record), `schema-that-settles.md` §2/§2.1/§3/§6b (the raw's atomic unit), `the-stratum-read.md` §1/§2/§2.4/§6/§5e (the field's own state), `the-census.md` §2/§2.1/§7 (the roster the office reads on), `the-dispute.md` §2/§6c/§6d/§6e (the dispute's raw ground), `field-archaeology.md` §2/§1.2/§6b (the field's own kept record), `the-name.md` §1/§3.3/§6e/§6d (the named lives held) — all twelve two-way.**|
|| `the-desert.md` (wave 45) | ✓ | ✓ | ✓ | ● | clean — the thin regime, not the between, the honest scarcity, a window living at the attractor's thin edge; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (thin-trough §5a `tide-of-the-attractor.md`) flagged non-canonical. **Canonical check: a desert provides nothing beyond its own thin regime, no scarcity that yields — `output ≤ φ⁻¹·input` + `E_waste=(1−q)·E_throughput` (no-free-energy §6, waste §2 `energy-harnessing.md`); the desert is NOT the between (a lived thin, not the field's own outside §1 `the-between.md`) — verified.** **§1/§2 ↔ `field-hazards.md` §3/§6.2 (the hazard-twin), `signature-predator.md` §1.2/§7c/§2 (the Coda's home terrain), `the-between.md` §1/§3/§2a (the NOT-between), `the-scavenger.md` §2.1/§2.2/§4 (the natural margin), `the-roost.md` §2/§3/§4 (the thin ground), `the-husbander.md` §2c/§4/§6(c) (the dry-edge care), `the-spring.md` §2/§3/§4 (the wellspring's draw), `the-fallow.md` §2a/§1/§3/§6(c) (the one-way run-out as climate), `tide-of-the-attractor.md` §2/§5a/§5b (the sustained thin), `farm-that-feeds.md` §2/§4/§5 (the sparse crop), `energy-harnessing.md` §2/§6/§7 Q1 (the sparseness economics), `the-compost.md` §1/§4 (the thin soil), `the-cold.md` §1/§2/§3 (the heat's thin, the cold's dry cousin) — all thirteen two-way.**|
|| `the-broker.md` (wave 46) | ✓ | ✓ | ✓ | ● | clean — the between-carrier, the charged-then-welcomed, the rarity-bearing stranger that brings worth; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (carried-order §5.2 `seed-garden.md`) flagged non-canonical. **Canonical check: a broker converts nothing, the trade is a transfer never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the broker's trade books on the settled op-record as a guest line (§6c `shared-ledger.md`), verified on the maintenance axis — verified.** **§1/§2 ↔ `the-market.md` §1/§2/§3/§6d/§6b/§4.1 (the between-carrier against), `the-toll.md` §1/§3/§2/§4/§5b/d/e (the charged-then-welcomed), `seed-garden.md` §2/§3/§4.2/§6b/§7 (the rare carrier), `the-atlas-of-windows.md` §1/§2/§3/§4b/§4d (the far-land's plier), `window-guests.md` §1/§2/§3/§6b/§6d (the verified stranger), `the-between.md` §1/§3/§3a/§5d/§2c (the dark's carrier), `the-mimic.md` §1/§3/§4/§5b (the held-line read), `life-signal.md` §1/§3/§3.3/§6a/§6d/§6b (the verified carrier), `signature-predator.md` §1/§2/§1.3/§7e/§8 (the rarity's draw), `shared-ledger.md` §1.2/§2.1/§6c/§6d/§6e/§3.3 (the booked trade), `field-emergent-ecology.md` §2.2 (the morphology), `energy-harnessing.md` §2/§6 (the carry's cost), `the-gatekeeper.md` §1/§2/§5c/d/e (the admitted visitor), `the-census.md` §2/§2.4/§6d (the counted visitor) — all fourteen two-way.**|
|| `the-smell.md` (wave 46) | ✓ | ✓ | ✓ | ● | clean — the air-form read, the carrier's carry at the nose, the waste read at its air; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (olfactory band §5.2) flagged non-canonical. **Canonical check: a smell provides nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the scent is the field's own read, never a gain, never a detector-mint — verified.** **§1/§3 ↔ `life-signal.md` §1/§3/§3.1/§6a/§6b/§6c/§6d (the air-form read), `the-wind.md` §1/§3/§5b/§5c/d/e (the carry read at the nose), `the-blight.md` §2/§6e/§6c/d/e (the wrong-stink), `the-roost.md` §2/§3/§4/§5e (the home's musk), `the-spring.md` §3/§5c/d/e/§6 (the clean sweetness), `the-mimic.md` §3/§5b-1/§5d/§5e (the wrong smell), `the-marsh.md` §3/§8/§7c/d/e (the reek that swamps), `the-rain.md` §3/§5b/§5c/d/e (the wet-wash), `farm-that-feeds.md` §2/§5 (the hearth's smoke), `player-remains.md` §1/§1.3/§5d (the body's scent), `energy-harnessing.md` §2/§6 (the waste read at the air), `the-stilling.md` §2 (the held quiet), `signature-predator.md` §1/§2/§7e/§8 (the trail's scent), `field-hazards.md` §5.1 (the readable-before-it-arrives), `field-instruments.md` §2.1 (the family rule), `field-music.md` §1/§6 (the air's sibling) — all sixteen two-way.**|
|| `the-river.md` (wave 46) | ✓ | ✓ | ✓ | ● | clean — the moving-conduit band, the grown-and-habitable, the flow-face of the liquid regime; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (water-cycle §2c `the-sea.md`) flagged non-canonical. **Canonical check: a river converts nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the current is never a mint; the river's bank is the farm's fertile soil following the water — verified.** **§1/§2 ↔ `the-sea.md` §2a/§2b/§2c/§5b/§5c/d/e (the place-regime), `coherence-highway.md` §1/§3.1/§4/§6b/§6c/§6d (the grown twin), `the-marsh.md` §2/§3/§5/§8 (the wide-slow twin), `the-desert.md` §2/§3 (the wet-counter), `farm-that-feeds.md` §2/§3/§4/§5 (the fertile bank), `the-cart.md` §2/§3/§4b/open-Q6 (the road's fluid twin), `the-swim.md` §2a/§2b/§5d (the two-face current), `the-dive.md` §1/§2 (the shallow current), `the-flood.md` §2/§4.1 (the overshoot), `the-rain.md` §2/§4 (the recharge), `the-threshold.md` §1/§2.2 (the crossing), `the-gatekeeper.md` §1/§2/§4 (the river-door), `the-toll.md` §2/§4 (the crossing's charge), `energy-harnessing.md` §2/§6 (the flow's cost and cap), `the-spring.md` §2/§3 (the well's outflow), `field-emergent-ecology.md` §2.2/§4.2 (the linear biome) — all sixteen two-way.**|
|| `the-wage.md` (wave 47) | ✓ | ✓ | ✓ | ● | clean — the time-form of the booked exchange, the paid-in-order, the present-tensed coin for work done; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (standing labor-contract §2.2 `schema-that-settles.md`) flagged non-canonical. **Canonical check: a wage converts nothing, the transfer never a gain — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the wage books on the settled op-record `{member, op, worldPos, rung, magnitude, sustain}` verbatim (§2.1 `schema-that-settles.md`); an unpaid wage is a false op the book will not hold — verified.** **§1/§2 ↔ `the-market.md` §1/§2.1/§2.3/§3/§6d/§6b (the time-form), `the-apprenticeship.md` §1/§3.1/§2.2 (the paid-in-order opposite), `the-working-song.md` §1/§4/§5d (the contracted-solo), `the-commons-tithe.md` §1/§3/§2.1/§6d (the pay-a-person), `shared-ledger.md` §1.2/§2/§6d/§6c/§6b (the booked day), `schema-that-settles.md` §2.1/§2.2/§2.3/§3/§6e (the Wage's atomic book), `the-gift.md` §1/§2.1/§2.3/§6d (the paid inverse), `farm-that-feeds.md` §2/§3/§4/§7 (the first work paid), `house-that-steers.md` §1/§2.2/§3/§5d (the second work paid), `the-census.md` §2.1/§2.2/§6d (the paid population), `the-toll.md` §1/§3/§5d/§5c (the outward twin), `the-loan.md` §1/§2/§2.1 (the forward twin), `the-oath.md` §2 (the day's held promise), `energy-harnessing.md` §2/§6 (the cap), `the-observatory.md` §1 (the composed room) — all fifteen two-way.**|
|| `the-spring-caretaker.md` (wave 47) | ✓ | ✓ | ✓ | ● | clean — the kept well, the office-twin, the read-before-depletion, the clearing of the silt that chokes the source's mouth; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (welling §2 `the-spring.md`) flagged non-canonical. **Canonical check: a caretaker converts nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the draw is spent, the clearing is real, never a mint; the office's reads/draws book on the settled op-record, the misattribution guard held (a silted well must not blame a member who did not silt it) — verified.** **§1/§2 ↔ `the-spring.md` §2/§2.2/§3/§4/§5c/d/e (the kept well), `the-guardian.md` §1/§3/§2.3/§5d/§7 (the office-twin), `the-gatekeeper.md` §1/§2.1/§4/§5c/d/e (the sibling door-office), `the-rain.md` §3/§3.2/§5 (the silt-carried), `the-compost.md` §2/§3/§6d (the spent-matter silt), `life-signal.md` §3/§3.3/§6b/§6c/§6d (the defended legibility), `signature-predator.md` §2/§3/§7e (the defended liability), `the-desert.md` §2/§4/§5d (the prevented dry-need), `the-fallow.md` §2a/§1/§3 (the read-before depletion), `the-census.md` §2.1/§2.2/§7 (the keeper on the roster), `shared-ledger.md` §1.2/§6c/§6d/§6e (the member-line), `schema-that-settles.md` §2.1/§2.3/§6d (the op-record), `the-name.md` §1/§2 (the named source's keeper), `energy-harnessing.md` §2/§6 (the clearing's cost), `the-dispute.md` §2/§6d/§6e (the field-true read), `field-instruments.md` §2.1/§1.2 (the family rule) — all sixteen two-way.**|
|| `the-migration.md` (wave 47) | ✓ | ✓ | ✓ | ● | clean — the collective's movement, the exile named for many, the strip's driver, the moving window's chunk; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (flocking/schooling §5.3/§6c `field-emergent-ecology.md`, herd-as-chord §2.4 `field-music.md`) flagged non-canonical. **Canonical check: a migration provides nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the strip is real depletion never a mint; the larder-farm refused (§7e `signature-predator.md`) — verified.** **§1/§2 ↔ `the-walk.md` §1/§2/§2c/§4a (the single body copied many), `the-pilgrim.md` §2/§3 (the one seeker made many), `world-seams.md` §2/§2.3/§3.2/§6 (the voyage / the far end), `field-emergent-ecology.md` §2.2/§4.2/§5.3/§6c/§6b/§1.4 (the collective field-mechanics), `the-shepherd.md` §1/§2/§3/§5a/§5c/d/e (the gathering swollen), `the-exile.md` §1/§2/§4/§4.2 (the removal named for many), `window-guests.md` §1/§3/§6d (the arrival), `the-blight.md` §2/§3 (the exodus's driver), `the-flood.md` §2/§3/§6(b) (the surfeit driver), `the-fallow.md` §2/§1/§5d/§6(c) (the strip), `the-compost.md` §4/§5d (the re-turn), `the-herald.md` §1/§2/§4/§5c/d/e (the announcer), `signature-predator.md` §1/§2/§1.2/§7e (the larder-read), `field-music.md` §2.4/§6 (the herd-as-chord), `energy-harnessing.md` §2/§6 (the cap), `the-census.md` §2/§1 (the roster), `life-signal.md` §3/§6d (the maintenance read), `coherence-highway.md` §1/§6 (the filament), `chunk-field-quantization.md` §1/§5 (the moving window's chunk), `field-instruments.md` §2.1 (the family rule) — all twenty two-way.**|
|| `the-ford.md` (wave 48) | ✓ | ✓ | ✓ | ● | clean — the river's natural shallow, the crossing the water makes safe of itself, the easy reach where the stroke lets you stand; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (bed-regime §2 `the-river.md`) flagged non-canonical. **Canonical check: a ford converts nothing, no crossing that yields — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the boundary holds, steadies, marks — never mints — verified. The river↔ford two-way write-race is landed: the river's open-Q1 flagged the ford absent (as a crossing-door `[assumption]`); now that the ford is on disk the river's open-Q1 reads it two-way (the ford is the river's natural shallow, the crossing made real), while the camp stays honestly absent.** **§1/§2 ↔ `the-river.md` §2/§4b/open-Q4/§6 (the river's natural door), `the-causeway.md` §1/§2/§7 (the given vs the built), `the-swim.md` §2a/§5 (the easy wade-patch), `the-cart.md` §2/§3/open-Q6 (the crosser), `the-shepherd.md` §2/§3/§5d (the gathered crossing), `the-gatekeeper.md` §1/§2 (the water's door-office), `the-toll.md` §2/§4/open-Q5 (the crossing's charge), `the-threshold.md` §1/§2.2/§3 (the boundary at water-scale), `signature-predator.md` §2/§1.2/§7e (the larder-crossing), `the-mimic.md` §2/§3/§4 (the waited shape), `energy-harnessing.md` §2/§6 (the waste and the cap), `the-marsh.md` §2/§8 (the wide-slow twin's shallows), `the-walk.md` §1/§2/§4a (the crossing walk) — all thirteen, plus the river↔ford special.**|
|| `the-estuary.md` (wave 48) | ✓ | ✓ | ✓ | ● | clean — the mixing's fought water, the river's mouth, the wet twin of the edge-regime; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (tide-pulse T1–T4 §5a `tide-of-the-attractor.md`) flagged non-canonical. **Canonical check: the mixing feeds at the field's own yield, never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the mixing's loss is the field's own, never a gain — verified.** **§1/§2 ↔ `the-river.md` §2/§4/§5c/§6 (the fresh half), `the-sea.md` §2/§2a/§5b/§5c/d/e (the salt half), `the-marsh.md` §2/§3/§6c/§7 (the blend's shallow face), `tide-of-the-attractor.md` §2/§5a/§5d (the tide's pulse at the mouth), `the-ford.md` §2/§4/§6 (the mixing's shallow crossing), `the-causeway.md` §1/§7 (the built way over the mixing), `field-emergent-ecology.md` §2.2/§4.2/§6b/§1.4 (the estuarine biome), `the-desert.md` §2/§3/§5b/§6 (the wet twin of the edge-regime), `energy-harnessing.md` §2/§6 (the mixing's cap), `field-instruments.md` §2.1 (the family rule), `the-compost.md` §4/§5d (the nutrient return), `signature-predator.md` §2/§7e (the fought-water read), `the-swim.md` §2a (the fought water's swim), `the-fall.md` §2/§5d (the gradient's end at the mouth) — all fourteen two-way.**|
|| `the-tutelary.md` (wave 48) | ✓ | ✓ | ✓ | ● | clean — the line's personal keeper, the following made attached, the held order that follows; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (persistent-Π §5.2 `the-family.md`, the field-as-god binding risk) flagged non-canonical. **Canonical check: a tutelary converts nothing, never a free shield — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the shadow's own glow is the `(1−q)` waste, never a shield-mint — verified.** **§1/§2 ↔ `the-guardian.md` §1/§3/§4/§5c/d/e/§7 (the personal territorial twin), `the-family.md` §1/§2.1/§3.2/§3.3/§5b/§6b (the line it shadows), `the-child.md` §2/§3/§6b/§6d (the attachment's subject), `the-healer.md` §2/§3/§5e (the line's holding), `the-commensal.md` §2/§3/§5b (the following contrast), `the-name.md` §1/§2/§5.1/§6d/§6e (the line's name's keeper), `the-exile.md` §2/§4/§6b (the exiled line's shadow), `the-inheritance.md` §2/§2.4/§3.2/§8 (the passing), `life-signal.md` §1/§3/§3.1/§6a/b/§6d (the guarded read), `signature-predator.md` §1/§2/§2.2/§7e/§8 (the shadow's legibility), `energy-harnessing.md` §2/§6 (the cap), `field-instruments.md` §2.1/§1.4/§1.3/§5c (the family rule), `the-lock.md` §1/§2/§3/§6d (the permanence), `the-walk.md` §1/§2a/§2c/§4a/§4c/d/e (the shadow's stride), `the-herald.md` §2/§5b/§5c/d/e (the kept not-told), `the-mimic.md` §2/§4 (the honest contrary), `the-witness.md` §1/§2/§7 (the held order made attached), `the-gatekeeper.md` §1/§2 (the office's being-twin) — all eighteen two-way.**|
|| `the-midwife.md` (wave 49) | ✓ | ✓ | ✓ | ● | clean — the office the birth-rite presupposes, the fresh run's receiver, the first read's bounded spend; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (persistent-Π §5.2 `the-family.md`) flagged non-canonical. **Canonical check: the midwife converts nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the first read is real and spent, never a mint; the birth-line books on the settled op-record (`{member, op, worldPos, rung, magnitude, sustain}` §2.1 `schema-that-settles.md`), cannot be forged — verified.** **§1/§2 ↔ `the-child.md` §1/§3.1/§2.1/§6d/§6c (the fresh run's receiver), `life-signal.md` §1/§3/§3.1/§6a/§6b/§6c/d (the first read), `shared-ledger.md` §1.2/§6c/§6d/§6a/§6b (the newborn's first line), `schema-that-settles.md` §2.1/§2.1.1/§6d (the first booking's shape), `the-family.md` §1/§2.1/§3.2/§6b/§6d (the hand-off's anchor), `the-rite-of-passage.md` §1/§2.1/§4b (the office the rite presupposes), `the-healer.md` §2/§3/§4.1 (the line's bookend), `the-spring-caretaker.md` §1/§2/§5/§6 (the person-office precedent), `the-census.md` §2.1/§2.2/§7 (the fresh line's roster), `the-name.md` §1/§2/§6b (the read before the name), `energy-harnessing.md` §2/§6 (the first read's cap), `field-instruments.md` §2.1/§1.4/§1.2 (the family rule), `the-apprenticeship.md` §1 (the first teacher's precedent), `coherence-magic.md` §1 (the budget's first spend), `async-field-domain.md` §1–2 (the sampler's first tick), `the-witness.md` §1/§2 (the held-and-handed), `the-gatekeeper.md` §1/§2 (the door's birth-office), `the-vigil.md` §1 (the watch's beginning) — all eighteen two-way.**|
|| `the-inn.md` (wave 49) | ✓ | ✓ | ✓ | ● | clean — the held room, the guest-form of pay, the booked welcome the gift refuses to tally; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (Qi bath §2.2 `house-that-steers.md`) flagged non-canonical. **Canonical check: an inn converts nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); an inn charged without the held room is a false op (trust-by-law §4 `the-toll.md`); the paid night books on the settled op-record verbatim (§2.1 `schema-that-settles.md`) — verified.** **§1/§2 ↔ `window-guests.md` §1/§3/§6b/§6d (the guest's held bed), `house-that-steers.md` §1.1/§2.2/§3/§5b/§5d (the guest-door's house), `the-threshold.md` §1/§2.2/§2.3/§4/§6 (the inner-edge's bed), `the-gatekeeper.md` §1/§2.1/§2.2/§5c/§5e (the door's read), `the-wage.md` §1/§2.1/§4.1/§5d (the guest-form of pay), `the-toll.md` §3/§4/§5c/§5d (the held charge's price), `the-gift.md` §1/§2.2/§3/§6d (the booked complement), `the-exile.md` §1/§4 (the held-against), `the-census.md` §2.1/§2.4 (the slept guest's roster), `shared-ledger.md` §1.2/§6c/§6d/§6a/§6e (the room's book), `schema-that-settles.md` §2.1/§2.2/§3 (the atomic book), `energy-harnessing.md` §2/§4.4/§5.4/§6 (the cap), `field-instruments.md` §2.1 (the family rule), `sleep.md` §1/§2b (the rest it offers), `the-burden.md` §1/§2/§4 (the held carry), `the-healer.md` §2/§3 (the long bind's rest), `the-mimic.md` §4 (the provenance read at the door) — all seventeen two-way.**|
|| `the-blizzard.md` (wave 49) | ✓ | ✓ | ✓ | ● | clean — the cold's driven white, the winter's storm, the hazard's honest cover; canonical set cited verbatim (≈6 MiB incl. the atmosphere's fifth engine-real `FieldVel` channel, 64³/192³, dt=0.05, q≈0.947, q~1e-3…1e-1, ξ=φ⁶≈17.94, φ⁻²≈0.382, ≈1–6 ms, ≈2,000, ≈40 ns/entity, c_s=h₀/dt); theory (storm-provenance §3 `weather-not-storm.md`) flagged non-canonical. **Canonical check: a blizzard converts nothing — `output ≤ φ⁻¹·input` + `E_waste=(1−q)·E_throughput` (no-free-energy §6, waste §2 `energy-harnessing.md`); the cover is spent and gone, never a mint, never a free cloak; the blizzard is NOT the storm (its own provenance read over the same classifier) — verified.** **§1/§2 ↔ `the-cold.md` §2/§3/§6(b) (the quiet thin driven), `the-wind.md` §1/§2.2/§3/§5(b)/§5(c)(d)(e) (the flow at storm strength), `the-rain.md` §2/§3/§4 (the wet-fall frozen), `weather-not-storm.md` §2/§3 (the NOT-storm), `field-hazards.md` §2/§5.1 (the hazard read), `the-smell.md` §2 (the upwind drowned), `the-walk.md` §2/§2a/§2b/§2c/§4a (the footing erased), `the-beacon.md` §2/§5 (the brightness scoured), `signature-predator.md` §1.2/§2/§1.3 (the honest cover), `the-season-change.md` §2/§4 (the winter's storm), `the-dawn.md` §2/§2b (the light's inverse), `energy-harnessing.md` §2/§6 (the cover's cap), `field-instruments.md` §1.2/§1.4/§2.1 (the buried reads), `the-cart.md` §3 (the traveler caught), `the-husbander.md` §2 (the kept wild driven) — all fifteen two-way.**|
|| `the-understory.md` (wave 50) | ✓ | ✓ | ✓ | ● | clean — the shade, the vertical’s occupied middle on land, the thin not the void; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (biosphere hum §2.4 `field-music.md`) flagged non-canonical. **Canonical check: the understory converts nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the canopy’s absorption is the field’s own spent, never a gain — verified.** **§1/§2 ↔ `the-zenith.md` §1/§2a/§6 (the canopy’s upper light), `the-bedrock.md` §1/§3/§6 (the standing floor), `the-cave.md` §1/§5d (the thin not the void), `the-roost.md` §2/§3/§4/§5e (the shade’s tenant), `field-emergent-ecology.md` §4.2/§6b/§2.2/§1.4 (the shade biome), `field-music.md` §2.4/§2.3/§6 (the shade’s chord), `field-instruments.md` §2.1/§1.2 (the family rule), `energy-harnessing.md` §2/§6 (the waste and the cap), `the-desert.md` §2a/§2b/§5d/§6b (the shade-thin), `the-stratum-read.md` §2.1/§2.3 (the vertical’s layer read), `the-cold.md` §2/§7 (the quiet thin), `the-sea.md` §1/§2 (the land’s forest-middle), `the-sea-floor.md` §1 (the interface precedent), `coherence-magic.md` §2/§5.1 (the shade’s reader), `chunk-field-quantization.md` §1.2/§4 (the bounded patch) — all fifteen two-way.**|
|| `the-mirage.md` (wave 50) | ✓ | ✓ | ✓ | ● | clean — the thin’s composition, the composed bright, the false trail the field’s own order makes; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (heat-distortion §2 `the-desert.md`) flagged non-canonical. **Canonical check: a mirage converts nothing, no lure that farms to — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the deception is the instrument’s interpretation of a genuine read, never the field mis-stating itself; the composed bright is un-sustained (fades) — verified.** **§1/§2 ↔ `the-desert.md` §2(a)/§5b/§3/§6.2/§4/§5d (the thin’s composition), `the-dispute.md` §2/§6(c)/§6(e) (the field-true deception), `the-spring.md` §3/§3.1/§2.1/§4/§5d/§5e (the composed bright), `the-beacon.md` §2/§2(a)/§2(c)/§5d (the light composed), `the-smell.md` §2/§2.1/open-Q2/§6 (the scent composed), `field-instruments.md` §2.1/§1.2/§1.4/§5 (the family rule), `life-signal.md` §3/§4/§6a/§6b (the un-maintained bright), `signature-predator.md` §1.2/§1.3/§7e (the false trail), `energy-harnessing.md` §2/§6 (the composed cap), `weather-not-storm.md` §2 (the honest provenance), `the-stratum-read.md` §2 (the layer mis-read), `the-census.md` §2/§6d (the counted never-lure), `the-mimic.md` §4 (the environmental twin), `the-clock.md` §2 (the cadence-less) — all fourteen two-way.**|
|| `the-mint.md` (wave 50) | ✓ | ✓ | ✓ | ● | clean — the coin, the portable booking, the struck order never mined; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (sustain flag §2.2 `schema-that-settles.md`) flagged non-canonical. **Canonical check: a mint converts nothing, the coin never yields — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the strike books on the settled op-record `{member, op, worldPos, rung, magnitude, sustain}` verbatim (§2.1 `schema-that-settles.md`), unforgeable (§6d `shared-ledger.md`) — verified.** **§1/§2 ↔ `shared-ledger.md` §1.2/§1.3/§2/§6c/§6d/§6b (the coin’s book), `schema-that-settles.md` §2.1/§2.2/§2.3/§3/§6e (the coin’s atomic book), `the-market.md` §1/§2/§2.3/§3/§6d (the portable booking), `the-wage.md` §1/§2/§4a/§6b/§7 (the hand-holdable form), `the-toll.md` §2/§4/§6b (the pre-carried charge), `the-gift.md` §1/§2.3/§6d (the booked alternative), `the-loan.md` §1/§2/§4a (the present-tensed hold), `the-tool.md` §2/§3/§4d (the rung-marked token), `the-quarry.md` §2 (the un-mined coin), `energy-harnessing.md` §2/§6 (the cap), `field-instruments.md` §2.1 (the family rule), `the-granary.md` §2/§5d (the strikeable store), `the-commons-tithe.md` §2.1/§6d (the fundable share) — all thirteen two-way.**|
|| `the-orchard.md` (wave 51) | ✓ | ✓ | ✓ | ● | clean — the standing trees, the living permanence, the long arc’s clock made a crop; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (tree-tempo §2 `patient-field.md`) flagged non-canonical. **Canonical check: the orchard gives at the field’s own yield, never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); a standing grove falls toward the fallow’s depletion without husbanding — verified.** **§1/§2 ↔ `farm-that-feeds.md` §2/§3/§4/§5 (the slow end of the crop ladder), `seed-garden.md` §1/§2 (the living permanence), `the-granary.md` §2/§6 (the perennial store), `patient-field.md` §2/§5b (the patience made a crop), `the-window-year.md` §2/§5b (the long arc’s clock), `the-fallow.md` §2a (the grove’s fate if not kept), `the-husbander.md` §1/§2 (the wild-care planted), `field-emergent-ecology.md` §4.2/§2.2/§6b/§5.3 (the rung-trees), `the-roost.md` §2/§4 (the grove habitat), `energy-harnessing.md` §2/§6 (the yield’s cap), `field-instruments.md` §2.1 (the family rule), `the-season-change.md` §2/§4 (the across-the-turn), `the-cold.md` §2 (the dormant grove), `material-regimes.md` §2/§4 (the rung-growth), `schema-that-settles.md` §2.1 (the yield’s book), `shared-ledger.md` §1.2 (the grove’s line), `the-window-pulse.md` §2 (the long arc’s pulse) — all seventeen two-way.**|
|| `the-delta.md` (wave 51) | ✓ | ✓ | ✓ | ● | clean — the river’s fan, the many mouths, the spread of the single line into the fan; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (biome-set dial open-Q4 `the-estuary.md`) flagged non-canonical. **Canonical check: a delta converts nothing, the spread never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the fan disperses a signature the predator would read as a line — verified.** **§1/§2 ↔ `the-river.md` §2/§4/§5c/d/e/§6 (the river’s fan), `the-estuary.md` §2/§4/§5b/§5d/e/§6/open-Q4 (the many mouths), `the-marsh.md` §2/§3/§4/§6c/§7/§8 (the banks’ hiding), `the-ford.md` §2 (the fan’s shallow crossings), `the-causeway.md` §1 (the built way over the fan), `field-emergent-ecology.md` §4.2/§6b (the fan biome), `the-roost.md` §2 (the fan’s habitat), `energy-harnessing.md` §2/§6 (the fan’s cap), `field-instruments.md` §2.1 (the family rule), `tide-of-the-attractor.md` §2/§5a (the spread at the mouth), `the-swim.md` §2a (the fan’s many strokes), `signature-predator.md` §2 (the spread trail) — all twelve two-way.**|
|| `the-sledge.md` (wave 51) | ✓ | ✓ | ✓ | ● | clean — the frozen twin of the cart, the carry at the winter’s scale, the freight dragged through the driven white; canonical set cited verbatim (≈6 MiB, 192³/64³, dt=0.05, ξ=φ⁶≈17.94, φ⁻²≈0.382, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity, a=−G_N·(π/ρ)·∇(g·Φ)); theory (§2 `the-cold.md` long-thin) flagged non-canonical. **Canonical check: the sledge converts nothing — no glide that yields, never a winter-mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the sledge’s load is real depletion dragged, the freight crosses honest doors never a hidden sled-path — verified.** **§1/§2 ↔ `the-cart.md` §2/§3/§4a/§5b/§6/§7 (the frozen twin), `the-carry.md` §2/§3/§4/§6 (the pack made a vehicle), `the-cold.md` §2/§3/§5.3/§6(b)(c)(d)(e) (the winter it rides), `the-blizzard.md` §2/§3/§5b/§5e (the white it crosses), `the-granary.md` §2/§3/§4/§6/§7 (the store it drags), `coherence-highway.md` §1/§4/§6b/§6d (the un-needed road), `the-fallow.md` §2a/§3/§5d (the real depletion), `the-toll.md` §4/§2/§5e (the honest doors), `energy-harnessing.md` §1.1/§2/§6 (the glide’s cap), `field-instruments.md` §2.1/§1.4/§1.2 (the family rule), `schema-that-settles.md` §2.1/§2.2/§2.3 (the load’s book), `shared-ledger.md` §1.2 (the Board), `the-walk.md` §2/§2c/§4a/§4c/§4d (the buried footing), `the-husbander.md` §2 (the freight through the trough), `the-climb.md` §1/§5d (the horizontal’s freight) — all fifteen two-way.**|
|| `the-raft.md` (wave 52) | ✓ | ✓ | ✓ | ● | clean — the current’s freight, the cart’s ride made fluid, the waterform of the road; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-river.md` moving-conduit) flagged non-canonical. **Canonical check: a raft converts nothing, no current that yields — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the raft’s freight crosses honest doors (a bulk load at an un-held harbor is a false op), never a hidden lane — verified.** **§1/§2 ↔ `the-river.md` §2/§2a/§4/§5c/d/e/§6/open-Q1 (the current’s freight), `the-cart.md` §2a/§2b/§3/§4b/§5b/open-Q5 (the water-form), `the-granary.md` §2/§2.1/§3/§4/§5d/§6 (the downstream’s store), `the-quarry.md` §2/§5d (the cut’s carrier), `the-fallow.md` §2/§5d (the load’s bound), `the-toll.md` §2/§4/§5d (the landed honesty), `the-harbor.md` §2/§4/§5a/§5e (the landing door), `the-estuary.md` §2 (the downstream end), `the-delta.md` §2 (the fan’s rafts), `the-swim.md` §2a (the medium’s vehicle), `the-flood.md` §2 (the surfeit’s freight), `energy-harnessing.md` §2/§6 (the glide’s cap), `field-instruments.md` §2.1 (the family rule), `signature-predator.md` §2 (the crossed line), `world-seams.md` §2 (the voyage’s water-raft) — all fifteen two-way.**|
|| `the-eclipse.md` (wave 52) | ✓ | ✓ | ✓ | ● | clean — the named dark, the calendar’s scheduled dim, the honest cover “spent and gone”; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (atmosphere’s envelope § `atmosphere-orbits-auroras.md`) flagged non-canonical. **Canonical check: the eclipse converts nothing, no dark that yields — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the eclipse is not the stillness (the scheduled dark vs the field’s own quiet, drawn never blurred) — verified.** **§1/§2 ↔ `the-window-year.md` §2/§3/§5a/§5b/§5e (the named dark), `the-observatory.md` §2/§2.1/§3.1/§6e (the read’s seat), `the-zenith.md` §2a/§2b/§5/§6/§5 Q1 (the dimmed light), `the-dawn.md` §2/§2b (the inverse), `the-beacon.md` §2/§2c/§5/§6 (the brightness scoured), `field-instruments.md` §1.2/§2.1/§1.3 (the family rule), `the-smell.md` §2/§5/§6 (the dimmed channel), `the-stillness.md` §1/§6 (the distinction), `the-season-change.md` §1/§4a/§5 (the sibling), `signature-predator.md` §1.2/§2 (the honest cover), `energy-harnessing.md` §2/§6 (the darkness’s cap), `tide-of-the-attractor.md` §2/§5a/§5d (the beat’s date), `the-cold.md` §1/§2 (the brief vs the long), `the-lantern.md` §2/§4 (not the ordinary night), `atmosphere-orbits-auroras.md` § (the envelope’s dark), `the-stilling.md` §1/§4 (the inverted hold) — all sixteen two-way.**|
|| `the-pooka.md` (wave 52) | ✓ | ✓ | ✓ | ● | clean — the riled’s shadow, the trail’s inverse, the fear-fed run drawn by disturbance; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (fear-fed framing § `field-emergent-ecology.md`) flagged non-canonical. **Canonical check: a pooka converts nothing, the riling spent never a gain — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the riling is read to resolution like any false op (§2 `the-dispute.md`) — verified.** **§1/§2 ↔ `signature-predator.md` §1/§2/§3/§7e/§8 (the trail’s inverse), `life-signal.md` §1/§3/§3.1/§3.3/§6a/b (the riled read), `the-burden.md` §1/§4 (the carried debt it feeds on), `the-fall.md` §2 (the riled descent), `the-stilling.md` §1/§4 (the inverse), `the-dispute.md` §2 (the honest judgment), `energy-harnessing.md` §2/§6 (the cap), `field-emergent-ecology.md` §2.2/§6b/§4.2 (the fear-fed run), `field-instruments.md` §2.1 (the family rule), `the-mimic.md` §2/§4 (the shape-wearing contrast), `the-moth.md` §2/§3 (the want’s contrast), `the-witness.md` §1/§2 (the still inverse), `the-guardian.md` §1/§3/§5d (the kept place’s threat), `the-marsh.md` §3 (the riled-water home) — all fourteen two-way.**|
|| `the-chant.md` (wave 53) | ✓ | ✓ | ✓ | ● | clean — the sustained voiced field-act, the body’s voice held continuously, the plainest shaped sound; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (phase-lock §3.2 `field-npc-ai.md`) flagged non-canonical. **Canonical check: a chant converts nothing, the held voice spent never a gain — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the chant holds, never gains (the practice-not-power honesty) — verified.** **§1/§2 ↔ `the-shout.md` §1/§2/§5/§5c/d/e (the sustained sister), `the-working-song.md` §1/§4/§5a/§5b/§5d (the single’s sibling), `the-vigil.md` §2/§3 (the voiced watch), `the-stilling.md` §2.1/§4/§2.3/§3 (the voiced quiet), `the-threshold.md` §1/§2.2 (the crossing’s voice), `the-oath.md` §2 (the held promise’s voice), `field-music.md` §1/§6 (the shaped-sound’s plainest), `field-npc-ai.md` §3.2 (the phase-locked voice), `the-bell.md` §1 (the body’s alarm held), `the-echo.md` §2 (the present face), `energy-harnessing.md` §2/§6 (the sustain’s cap), `field-instruments.md` §2.1 (the family rule), `the-silence.md` §1 (the voiced inverse), `field-hazards.md` §5.1 (the readable-before), `the-healer.md` §2 (the steady voice), `sleep.md` §1/§2b (the rest’s lullaby), `coherence-magic.md` §1/§5.1 (the bounded voice) — all seventeen two-way.**|
|| `the-touch.md` (wave 53) | ✓ | ✓ | ✓ | ● | clean — the fifth sense, the no-wind channel, the range-deceit dead at the skin; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `mouths-eye.md` taste-channel) flagged non-canonical. **Canonical check: a touch converts nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the touch reads the field at the body’s own point, a pure consumer at zero distance, never a mint — verified.** **§1/§2 ↔ `mouths-eye.md` §1/§2/§6(a) (the gustatory sibling), `the-smell.md` §1/§4 (the no-wind channel), `the-mirage.md` §2/§3 (the range-deceit dead), `the-walk.md` §2/§2a (the stride’s feel), `house-that-steers.md` §1/§1.1 (the held surface), `the-swim.md` §2a (the water’s feel), `field-instruments.md` §2.1 (the family rule), `signature-predator.md` §2 (the contact-read’s tell), `the-mimic.md` §4 (the un-fakeable contact), `energy-harnessing.md` §2/§6 (the cap), `the-stratum-read.md` §2 (the strata’s feel), `field-music.md` §1 (the body’s percussion), `the-wind.md` §1 (the felt flow) — all thirteen two-way.**|
|| `the-siren.md` (wave 53) | ✓ | ✓ | ✓ | ● | clean — the entrainment ride, the matched cadence, the lure read to resolution; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (phase-lock §3.2 `field-npc-ai.md`) flagged non-canonical. **Canonical check: the siren converts nothing — no entrainment that yields, no seduction that mints — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the call is the field’s own spent, never a hidden difficulty, never a minted charm — verified.** **§1/§2 ↔ `field-npc-ai.md` §3.2/§5.2/§6a/§2.3/§6d/§6c (the entrainment ride), `the-chant.md` §1/§3/§4/§5d/§6 (the abused voice), `field-music.md` §2.4/§1/§4/§6 (the matched cadence), `the-working-song.md` §1/§4/§5c/d/e (the inverted labor), `signature-predator.md` §1/§2.2/§3/§7e/§8 (the un-stalked hunt), `the-herald.md` §1/§2.2/§4/§5a/d/e (the not-news), `the-mimic.md` §2/§3/§4/§5c/d/e (the cadence-wearer), `the-pooka.md` §2/§4/§5d (the harmony lurer), `the-moth.md` §2/§5b/§5d/§6 (the cadence’s coveter), `the-dispute.md` §2/§2.1/§2.2/§6d (the read to resolution), `life-signal.md` §3/§3.1/§6b/§6d (the cadence matched truth un-masked), `energy-harnessing.md` §2/§6 (the seduction’s cap), `field-instruments.md` §2.1/§1.4/§1.3 (the family rule), `the-echo.md` §2/§6 (the present-vs-remembered), `the-shout.md` §1 (the lure’s sustained call), `the-stilling.md` §1/§4 (the voiced inverse) — all sixteen two-way.**|
|| `the-meadow.md` (wave 54) | ✓ | ✓ | ✓ | ● | clean — the open common, the fertile inverse of the desert, the field’s own grazed middle; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§6 `farm-that-feeds.md` found-economy) flagged non-canonical. **Canonical check: a meadow converts nothing, the graze never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the meadow is the field’s *renewed*, never the mined strip; the keeping books nothing — verified.** **§1/§2 ↔ `farm-that-feeds.md` §2/§3/§4/§5/§6 (the open common), `the-fallow.md` §2a/§1/§3/§6 (the renewed not the strip), `the-desert.md` §2a/§5d/§6b (the fertile inverse), `the-understory.md` §1 (the open middle), `the-husbander.md` §1/§2 (the kept common), `the-shepherd.md` §2/§3 (the flock’s pasture), `field-emergent-ecology.md` §4.2/§6b (the open biome), `the-roost.md` §2 (the open habitat), `the-census.md` §2 (the grazed count), `shared-ledger.md` §1.2 (the untraded common), `energy-harnessing.md` §2/§6 (the cap), `field-instruments.md` §2.1 (the family rule), `the-granary.md` §2 (the un-stored graze), `the-ford.md` §2 (the crossing’s pasture), `the-scavenger.md` §2.2 (the not-spent), `the-gift.md` §1 (the common giving) — all sixteen two-way.**|
|| `the-canal.md` (wave 54) | ✓ | ✓ | ✓ | ● | clean — the re-aimed lane, the extended freight-lane, the dug water-road; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-river.md` linear-regime) flagged non-canonical. **Canonical check: a canal converts nothing, the dug lane never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the canal re-aims the river’s own lane, its freight crossing no hidden lane — verified.** **§1/§2 ↔ `the-river.md` §2/§4/§5c/d/e/§6/open-Q1 (the re-aimed lane), `the-raft.md` §2/§3/§4a/§5d/§6 (the extended freight-lane), `the-harbor.md` §2/§4 (the reached door), `the-delta.md` §2 (the directed spread), `the-causeway.md` §1 (the dug complement), `the-marsh.md` §2 (the drained work), `the-rain.md` §2 (the fed lane), `the-spring.md` §2 (the drawn source), `energy-harnessing.md` §2/§6 (the directed cap), `field-instruments.md` §2.1 (the family rule), `the-toll.md` §2/§4 (the lane’s charge), `the-quarry.md` §2 (the dug cut), `the-sea.md` §2 (the reached plain), `the-estuary.md` §2 (the directed mixing), `coherence-highway.md` §1 (the water-road), `house-that-steers.md` §1/§6 (the held route) — all sixteen two-way.**|
|| `the-cistern.md` (wave 54) | ✓ | ✓ | ✓ | ● | clean — the built-held well, the caught fall, the dry-season’s held lifeline; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-spring.md` welling) flagged non-canonical. **Canonical check: a cistern converts nothing, the drawn hold never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the cistern’s draw shares the spring’s over-draw honest counter, holding clear water never a mint — verified.** **§1/§2 ↔ `the-spring.md` §2/§3/§4/§5b/§5c/§5d/§5e (the built-held well), `the-rain.md` §1/§2.1/§3/§4/§5b/§5c/d/e (the caught fall), `the-desert.md` §2/§5d/§6b (the dry-season’s hold), `the-granary.md` §2/§5d/§6 (the store’s water-twin), `house-that-steers.md` §1/§6 (the held vessel), `the-marsh.md` §2 (the clear-held water), `the-fallow.md` §2a (the not-run-out), `the-compost.md` §2 (the clean twin), `energy-harnessing.md` §2/§6 (the hold’s cap), `field-instruments.md` §2.1 (the family rule), `the-census.md` §2 (the served roster), `shared-ledger.md` §1.2 (the common water’s line), `the-spring-caretaker.md` §2 (the kept source’s hold) — all thirteen two-way.**|
|| `the-meteor.md` (wave 55) | ✓ | ✓ | ✓ | ● | clean — the falling brightness, the announced rare event, the non-minting fall; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§3.3 `atmosphere-orbits-auroras.md` aurora) flagged non-canonical. **Canonical check: a meteor converts nothing, the fall never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the meteor is announced, deterministic, never random, never hidden — verified.** **§1/§2 ↔ `atmosphere-orbits-auroras.md` §3.3/§3.2/§5c (the falling contrast), `the-eclipse.md` §2/§3/§5/§6 (the announced vs the dated), `the-dawn.md` §2 (the rare vs the daily), `the-bell.md` §1 (the alarm’s herald), `the-herald.md` §1/§2 (the announced event), `the-observatory.md` §2 (the predicted fall), `the-scar-lifecycle.md` §2.2 (the scar’s maker), `material-regimes.md` §2/§4 (the rung’s impact), `the-quarry.md` §2 (the un-mined strike), `field-archaeology.md` §2 (the strata’s marker), `signature-predator.md` §2 (the non-prey fall), `energy-harnessing.md` §2/§6 (the fall’s cap), `field-instruments.md` §2.1 (the family rule), `the-window-year.md` §2 (the arc’s rare event), `the-fallow.md` §2a (the delivered never worked) — all fifteen two-way.**|
|| `the-balefire.md` (wave 55) | ✓ | ✓ | ✓ | ● | clean — the hazard-twin of the beacon, the silent same of the bell, the raised warning flame; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-beacon.md` double-edge) flagged non-canonical. **Canonical check: a balefire converts nothing, the warning spent never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the raised flame is the field’s own spent; a false-balefire warning is a false op — verified.** **§1/§2 ↔ `the-beacon.md` §1/§2/§2a/§2c/§5b/§5c/d/e (the hazard-twin), `the-bell.md` §1/§2.1/§2.3 (the silent same), `the-vigil.md` §2 (the watch’s flame), `the-lantern.md` §2 (the raised glow), `signature-predator.md` §2 (the warned-gather), `the-blight.md` §2 (the warning of the wrong-band), `the-flood.md` §4.1 (the surfeit’s warning), `field-hazards.md` §5.1 (the readable warning), `the-herald.md` §1/§2 (the announced danger), `energy-harnessing.md` §2/§6 (the fire’s cap), `field-instruments.md` §2.1 (the family rule), `the-toll.md` §4 (the warning’s honesty), `the-shout.md` §1 (the loud warning), `house-that-steers.md` §1/§3 (the held warning structure), `the-threshold.md` §1 (the boundary’s fire) — all fifteen two-way.**|
|| `the-baptism.md` (wave 55) | ✓ | ✓ | ✓ | ● | clean — the first name, the designed ceremony’s naming-sibling, the line’s first binding; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§1 `the-name.md` Π-anchor) flagged non-canonical. **Canonical check: a baptism converts nothing, the naming spent never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); you cannot name falsely (§2 `the-name.md`); the naming books on the settled op-record, never a mint — verified.** **§1/§2 ↔ `the-child.md` §1/§2.3/§6e/§3.1/§3.3/§3.5/§6d/§6c (the run’s first name), `the-midwife.md` §1/§2.1/§2.2/§2.3/§5b/§6 (the received run made a name), `the-name.md` §1/§2/§5.1/§6b (the binding’s rite), `the-rite-of-passage.md` §1/§2.1 (the designed ceremony’s sibling), `the-family.md` §1/§2.1/§6d (the line’s first bind), `shared-ledger.md` §1.2/§6c/§6d (the named line’s book), `schema-that-settles.md` §2.1/§6d (the name’s op-book), `the-census.md` §2.1/§2.2 (the named one’s roster), `the-healer.md` §2 (the line’s start and end), `energy-harnessing.md` §2/§6 (the rite’s cap), `field-instruments.md` §2.1 (the family rule), `the-tutelary.md` §1 (the bound run’s keeper), `the-inheritance.md` §2 (the line’s beginning) — all thirteen two-way.**|
|| `the-palanquin.md` (wave 56) | ✓ | ✓ | ✓ | ● | clean — the carried seat, the office’s borne, the procession’s honored becoming; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-festival.md` one-chord) flagged non-canonical. **Canonical check: a palanquin converts nothing — no bearing that yields, never a minted seat, never a hidden privilege — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-cart.md` §2/§3/§4a/§4b/§5b/§6 (the person-conveyance), `the-carry.md` §2/§3/§4/§6/§7 (the body others hold), `the-sledge.md` §2/§3/§4/§6 (the non-winter contrast), `the-raft.md` §2/§6/§7 (the water-contrast), `the-election.md` §1/§2.4/§4.3/§6d/§6b/§7 (the carried office), `the-festival.md` §2/§2.3/§3/§6b/§7/§7 open-Q4 (the procession), `the-rite-of-passage.md` §1/§2.1/§2.4/§3.2/§4b/§6 (the borne becoming), `the-healer.md` §2/§3/§3.1/§5/§6 (the bound body carried), `the-burden.md` §1/§2/§6a/§5 (the carried weight shared), `the-census.md` §2.1/§6/§7 (the carried on the book), `energy-harnessing.md` §2/§6 (the borne cap), `field-instruments.md` §2.1/§1.4/§1.3/§5c (the family rule), `the-walk.md` §2/§2a/§4a (the bearers’ stride), `the-climb.md` §1/§5d (the borne ascent), `schema-that-settles.md` §2.1 (the borne’s book), `shared-ledger.md` §1.2 (the office’s line) — all sixteen two-way.**|
|| `the-fog.md` (wave 56) | ✓ | ✓ | ✓ | ● | clean — the static twin of the blizzard, the air’s marsh, the field’s held weather; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-blizzard.md` composed storm) flagged non-canonical. **Canonical check: a fog converts nothing, the blur spent never a gain — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); what the blur hides from you it hides from the Coda too; the fog is not the mirage (it blurs what is truly there) — verified.** **§1/§2 ↔ `the-blizzard.md` §2/§3/§4/§5b/§6/§5c/d/e (the static twin), `the-marsh.md` §2/§3/§4/§7c/d/e/§8 (the air’s marsh), `the-mirage.md` §2/§3 (the deceit’s opposite), `the-smell.md` §2/§5/§6 (the swamped channel), `life-signal.md` §3/§6a/§6b/§6c/§6d (the softened read), `the-walk.md` §2/§2a/§2b/§2c/§4a/§4b/§4c/d/e (the buried landmarks), `signature-predator.md` §1.2/§2/§7e (the honest cover), `the-mimic.md` §2/§3/§5e (the waited cover), `weather-not-storm.md` §2/§3/§6 (the held weather), `field-hazards.md` §2/§5.1/§1/§5.3 (the readable blur), `the-cold.md` §2/§3/§6(b)/§4 (the held-thin), `energy-harnessing.md` §2/§6 (the blur’s cap), `field-instruments.md` §2.1 (the family rule), `the-dawn.md` §2 (the light’s blur), `the-rain.md` §3 (the wet-blur) — all fifteen two-way.**|
|| `the-drought.md` (wave 56) | ✓ | ✓ | ✓ | ● | clean — the going-dry, the flood’s slow-inverse, the field’s receding abundance; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-desert.md` thin regime) flagged non-canonical. **Canonical check: a drought converts nothing, the dry spent never a gain — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the drought is the *event* of going dry, the process distinct from the place (the desert) — verified.** **§1/§2 ↔ `the-desert.md` §2/§1/§5b/§6 (the going-dry), `the-flood.md` §2/§3/§4.1 (the slow-inverse), `the-rain.md` §1/§2.1/§3 (the failing fall), `the-spring.md` §2/§4 (the drained well), `the-spring-caretaker.md` §2 (the kept-against), `the-cistern.md` §2 (the held-against), `the-fallow.md` §2a (the run-out’s face), `the-granary.md` §2 (the drawn store), `the-cold.md` §2 (the dry’s cousin), `energy-harnessing.md` §2/§6 (the dry’s cap), `field-instruments.md` §2.1 (the family rule), `weather-not-storm.md` §2 (the slow weather) — all twelve two-way.**|
|| `the-caravan.md` (wave 56) | ✓ | ✓ | ✓ | ● | clean — the organized passage of goods, the many-as-one guarded order, the held-door honesty; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-broker.md` trade-risk) flagged non-canonical. **Canonical check: a caravan converts nothing, no organized passage that yields — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the caravan’s goods cross held doors, never a hidden train; a phantom caravan-load is a false op — verified.** **§1/§2 ↔ `the-cart.md` §1/§2/§2b/§3/§4a/§5b/§7 (the train’s unit), `the-broker.md` §1/§2/§3/§4/§6 (the carried rare at scale), `the-market.md` §1/§2/§2.3/§6d/§6 (the train’s end), `the-migration.md` §1/§2.1/§3.1/§4.1/§6 (the goods’ passage), `the-pilgrim.md` §2/§5d (the many-as-one), `the-desert.md` §2/§2/§5d/§6 (the crossing), `the-atlas-of-windows.md` §1/§2/§3/§4/§5/§4d (the route), `the-harbor.md` §1/§2/§4/§5b (the arrival door), `the-toll.md` §1/§2/§4/§5d (the held-door honesty), `signature-predator.md` §2/§1.2/§7e (the many-as-exposed), `the-vigil.md` §2 (the traveling watch), `energy-harnessing.md` §2/§6 (the train’s cap), `field-instruments.md` §2.1 (the family rule), `the-walk.md` §2/§4a (the many strides), `the-fallow.md` §2a/§5d (the strip’s real), `seed-garden.md` §2 (the carried rare), `schema-that-settles.md` §2.1 (the goods’ book), `shared-ledger.md` §1.2 (the train’s line) — all eighteen two-way.**|
|| `the-dune.md` (wave 57) | ✓ | ✓ | ✓ | ● | clean — the wandering ridge, the desert’s own landform the wind walks across the dry; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-desert.md` thin regime) flagged non-canonical. **Canonical check: a dune converts nothing, no moving sand that yields, never a minted dune, never a hidden dune-path — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-desert.md` §2/§2a/§2d/§4/§5b/§6 (the thin the dune rides), `the-wind.md` §1/§2/§3/§4/§5b/§5c/d/e (the `(1−q)` carry that walks the ridge), `energy-harnessing.md` §2/§1.7/§6 (the carried surface’s cap), `field-archaeology.md` §1/§2/§3.2 (the covered yield), `the-scar-lifecycle.md` §1/§2/§2.3 (the moving land’s read), `the-fog.md` §2/§4 (the ground-twin), `the-delta.md` (the deposit’s dry twin), `signature-predator.md` §2/§1.2 (the cover’s honest drift), `field-instruments.md` §2.1 (the family rule), `the-cave.md` (the buried mouth), `the-husbander.md` §2 (the worked-against) — all eleven two-way.**|
|| `the-terrace.md` (wave 57) | ✓ | ✓ | ✓ | ● | clean — the ascent turned into fields, the worked land-cut at the slope’s register; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-quarry.md` worked-cut register) flagged non-canonical. **Canonical check: a terrace converts nothing, the runoff’s steps spent never a gain, never a minted terrace — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `farm-that-feeds.md` §2/§3/§4/§5/§7b/§7e/§9a (the stepped crop-band), `the-climb.md` §2/§4/§5b/§5c/5d/5e (the ascent turned to fields), `the-quarry.md` §2/§3/§5d/§6 (the worked cut), `the-landform-name.md` §1/§2/§3/§4/§5d (the named steps), `the-spring.md` §2/§5d/§4 (the steps’ draw), `the-rain.md` §2/§3/§4 (the wet fall’s steps), `the-fallow.md` §2/§1/§5d (the one-way run-out), `the-causeway.md` §1/§6 (the built-deliberate), `energy-harnessing.md` §2/§6 (the stepped cap), `field-instruments.md` §2.1 (the family rule), `the-meadow.md` (the flat cousin), `the-orchard.md` (the trees’ steps), `the-compost.md` §2 (the turnover’s bed), `the-carry.md` §3 (the moved hold) — all fourteen two-way.**|
|| `the-votive.md` (wave 57) | ✓ | ✓ | ✓ | ● | clean — the member-to-field giving, the un-recipiented leaving that refuses even the receiver; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-festival.md` one-chord) flagged non-canonical. **Canonical check: a votive converts nothing, the left order spent never a gain, never a minted offering — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-gift.md` §1/§2.1/§2.2/§2.3/§6d (the field-ward giving), `the-commons-tithe.md` §1/§3/§6d (the no-commons contrast), `the-toll.md` §1/§2/§4/§6d (the no-charge giving), `the-compost.md` §1/§2/§6d (the no-recipient giving), `the-spring.md` §2/§3/§5b/§6 (the point of fame), `the-bell.md` §1/§4/§6e (the voice’s offering), `the-landform-name.md` §1/§2/§5e (the named place’s giving), `the-dispute.md` §2 (the unbribable giving), `the-census.md` §2 (the giving on the book), `energy-harnessing.md` §2/§6 (the giving’s cap), `field-instruments.md` §2.1 (the family rule), `the-funeral.md` §2/§3.1 (the leaving’s kin), `the-shrine.md` (the built receiving-place — **two-way**), `the-festival.md` §2 (the giving’s celebration), `the-window-year.md` §2 (the giving’s season), `the-rite-of-passage.md` §2 (the bearing’s giving), `the-map.md` §3 (the giving’s trace), `the-observatory.md` §2 (the giving’s read) — all eighteen two-way.**|
|| `the-shrine.md` (wave 58) | ✓ | ✓ | ✓ | ● | clean — the funeral’s register made a place, the standing home that answers nothing; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-funeral.md` register) flagged non-canonical. **Canonical check: a shrine converts nothing, the held order is spent, never free — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); the shrine answers nothing, never a minted remembrance — verified.** **§1/§2 ↔ `the-funeral.md` §2/§2.3/§3.1/§3.2/§3.3/§6b (the register’s standing home), `the-votive.md` §1/§3/§2.2/§4.2/§4.3/§4.4/§5c/d/e/§7 (the built receiving-place — **two-way**), `the-dispute.md` §2/§6c/d/e (the indifference house), `energy-harnessing.md` §2/§6/§4.4/§5.3/§5.4 (the held order’s cap), `field-instruments.md` §2.1/§1.2/§3.1 (the family rule), `the-census.md` §2/§2.3/§6c/d/e/§7 (the roster’s place), `the-map.md` §3 (the drawn place), `the-bell.md` §1/§4 (the silent counterpart), `the-spring.md` §2 (the point placed), `the-landform-name.md` §1/§2 (the named place), `house-that-steers.md` (the house’s silence), `the-name.md` §2 (the named binding), `schema-that-settles.md` §2.1 (the settled book), `shared-ledger.md` §1.2 (the visible line), `field-npc-ai.md` (the NPC’s visit) — all fifteen two-way.**|
|| `the-lightning.md` (wave 58) | ✓ | ✓ | ✓ | ● | clean — the storm’s release, the gathered charge letting go at once, the corpus’s storm-discharge locus; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-blizzard.md` composed storm) flagged non-canonical; the absence of `the-storm.md` is honestly named (field-hazards + weather-not-storm stand in). **Canonical check: a lightning converts nothing, the settled charge releasing a front never a yield, never a minted flash — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `field-hazards.md` §2/§2.1/§2.3/§5.3/open-Q2 (the storm’s release), `weather-not-storm.md` §2/§3/§6 (the discharge’s provenance), `coherence-magic.md` §4.3/§1.2/§5.1/§6 (the discharge register), `atmosphere-orbits-auroras.md` §3/§3.4/§1.3 (the sky’s discharge), `the-wind.md` §1/§3/§5c/d/e (the carried front), `the-rain.md` §3 (the violent cousin), `the-blizzard.md` §1–4/§5c/d/e/§6 (the storm’s inverse), `the-fog.md` §2 (the static’s inverse), `the-meteor.md` (the sky’s other event), `energy-harnessing.md` §2/§6 (the discharge’s cap), `field-instruments.md` §2.1 (the family rule), `the-dispute.md` §2 (the legible front), `the-scar-lifecycle.md` §2 (the sudden’s read), `material-regimes.md` (the regime’s discharge), `tide-of-the-attractor.md` §2 (the storm’s season) — all fifteen two-way.**|
|| `the-crossroads.md` (wave 58) | ✓ | ✓ | ✓ | ● | clean — the maintained fork, the meeting of ways with no held door, the indifferent read of the passing train; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-causeway.md` built-way composition) flagged non-canonical. **Canonical check: a crossroads converts nothing, no meeting that yields, never a minted crossing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`); only a held door at a meeting books a toll — verified.** **§1/§2 ↔ `the-causeway.md` §1/§2/§7a/§7/§8 (the fork’s built leg), `the-ford.md` §1/§2/§5/§6 (the crossing leg), `the-toll.md` §1/§4/§5d/§6 (the no-door meeting), `the-caravan.md` §1/§2/§5e/§6 (the passing train), `the-dispute.md` §2/§4/§5/§6c (the indifference read), `energy-harnessing.md` §2/§6 (the meeting’s cap), `field-instruments.md` §2.1 (the family rule), `the-map.md` §3 (the drawn meeting), `the-walk.md` §2 (the ways’ meeting), `coherence-highway.md` (the junction), `signature-predator.md` §2 (the exposed meeting), `field-npc-ai.md` (the NPC’s way), `life-signal.md` §3 (the read-here), `the-story.md` §2 (the fork’s tale), `async-field-domain.md` (the fork’s domain) — all fifteen two-way.**|
|| `the-rumor.md` (wave 59) | ✓ | ✓ | ✓ | ● | clean — the unverified read anywhere, the pre-settled story, the claimed word that must die at the observatory; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-herald.md` verified read) flagged non-canonical. **Canonical check: a rumor converts nothing, the passed word spent never a gain, never a minted claim; a false rumor mis-names and fades — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-chronicle.md` §1/§2.1/§5/§6c/§6d/§7 (the record’s ahead-run), `the-story.md` §1/§2.1/§2.3/§6d (the un-climbed myth), `the-herald.md` §2.2/§2.3/§4/§7 (the said-true contrast), `the-dispute.md` §2/§2.3/§4/§6c (the contest’s settle), `shared-ledger.md` §1.2/§2.2/§3.3/§6e/§6d/§6b (the checked book), `the-echo.md` §2.1/§3/§6d (the un-inventable past), `the-observatory.md` §2/§2.1/§6c/§6d/§6e (the dying read), `field-npc-ai.md` (the NPC’s whisper), `field-instruments.md` §2.1 (the family rule), `energy-harnessing.md` §2/§6 (the whisper’s cap), `the-compass.md` §2 (the un-guided tell), `the-language.md` §3 (the said-shaped), `the-mimic.md` §2/§5e (the bare copy), `the-name.md` §2 (the mis-naming), `field-archaeology.md` §2 (the residue’s tell), `schema-that-settles.md` §2.1 (the book’s edge) — all sixteen two-way.**|
|| `the-generations.md` (wave 59) | ✓ | ✓ | ✓ | ● | clean — the carried lineage, the spans’ bound hold passed across time; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-family.md` bound unit) flagged non-canonical. **Canonical check: a generation converts nothing, the passed order spent never a gain, never a minted lineage — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-family.md` §2 (the carried lineage), `the-inheritance.md` §2 (the passed hold), `the-child.md` §2 (the made-new), `the-midwife.md` §2 (the arrival’s turn), `the-baptism.md` §2 (the marked new), `the-rite-of-passage.md` §2 (the turning), `the-funeral.md` §2 (the close), `the-chronicle.md` §1 (the record of spans), `the-story.md` §2 (the shaping), `the-name.md` §2 (the carried name), `the-migration.md` §1 (the people’s move), `the-window-year.md` §2 (the span’s season), `tide-of-the-attractor.md` §1 (the long season), `shared-ledger.md` §1.2 (the inherited line), `field-instruments.md` §2.1 (the family rule), `energy-harnessing.md` §2/§6 (the lineage’s cap), `the-dispute.md` §2 (the settled boundary), `reason-field.md` (the reasoned carry), `schema-that-settles.md` §2.1 (the settled book), `player-remains.md` (the left-behind), `field-archaeology.md` §2 (the strata of spans), `field-npc-ai.md` (the NPC’s lineage) — all twenty-two two-way.**|
|| `the-shaft.md` (wave 59) | ✓ | ✓ | ✓ | ● | clean — the dug hollow descending to a bounded floor, the deliberate vertical cut that bottoms at the bedrock; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-bedrock.md` bounded floor) flagged non-canonical. **Canonical check: a shaft converts nothing, the dug depth spent never a gain, never a minted shaft; the depth is bounded, never hidden — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-dive.md` §2 (the vertical read), `the-cave.md` §2 (the dug hollow), `the-quarry.md` §2 (the worked cut), `the-fall.md` §5d (the drop), `the-climb.md` §2 (the reverse ascent), `the-bedrock.md` §2 (the floor), `the-tool.md` §2 (the dug-with), `the-carry.md` §3 (the moved-up), `the-cart.md` §1 (the hauled-out), `chunk-field-quantization.md` (the vertical chunk), `field-instruments.md` §2.1 (the family rule), `energy-harnessing.md` §2/§6 (the depth’s cap), `the-dispute.md` §2 (the dug boundary) — all thirteen two-way.**|
|| `the-hand-over.md` (wave 60) | ✓ | ✓ | ✓ | ● | clean — the office passed, the carried turn made explicit, the skill’s final passing; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-inheritance.md` passed hold) flagged non-canonical. **Canonical check: a hand-over converts nothing, the office passed spent never a gain, never a minted turn — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-election.md` §1/§2.4 (the office’s passing), `the-inheritance.md` §2 (the passed hold), `the-archivist.md` §2 (the record’s pass), `the-chronicle.md` §1 (the marked moment), `shared-ledger.md` §1.2 (the visible turn), `the-oath.md` §2 (the bound promise), `the-apprenticeship.md` §2 (the skill’s passing), `the-generations.md` §2 (the span’s turn), `the-rite-of-passage.md` §2 (the becoming’s turn), `the-census.md` §2 (the new line), `field-instruments.md` §2.1 (the family rule), `energy-harnessing.md` §2/§6 (the passing’s cap), `the-dispute.md` §2 (the clean pass), `the-name.md` §2 (the carried name) — all fourteen two-way.**|
|| `the-seacraft.md` (wave 60) | ✓ | ✓ | ✓ | ● | clean — the built water-craft, the plain’s crossing, never free; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-raft.md` water-craft register) flagged non-canonical. **Canonical check: a seacraft converts nothing, the sailed passage spent never a gain, never a minted craft — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-sea.md` §2 (the plain’s craft), `the-sea-floor.md` §2a (the bed’s craft), `the-raft.md` §2 (the small craft), `deep-field-diving.md` §2 (the descender), `the-swim.md` §2a/§2b (the ridden current), `the-harbor.md` §1/§2 (the arrival door), `tide-of-the-attractor.md` §1 (the ridden season), `the-wind.md` §3 (the sailing), `the-river.md` §2 (the inland way), `the-carry.md` §3 (the borne load), `the-cart.md` §1 (the water-wagon), `field-instruments.md` §2.1 (the family rule), `energy-harnessing.md` §2/§6 (the craft’s cap), `the-dispute.md` §2 (the sea’s boundary) — all fourteen two-way.**|
|| `the-whirlpool.md` (wave 60) | ✓ | ✓ | ✓ | ● | clean — the sea’s sunken drain, the river’s two-face read at a spent bend, the taking’s local vortex never the giving; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-river.md` taking-vortex) flagged non-canonical. **Canonical check: a whirlpool converts nothing, the spun water spent never a gain, never a minted drain; a whirlpool converts nothing harder than a river — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-sea.md` §2b/§2a/§3/§4/§5b/§5c/d/e (the sunken plain), `the-sea-floor.md` §2a/§2b/§5c/§5a (the shelf’s inward twin), `the-river.md` §2/§4/§5c/§5d/§6/open-Q3 (the two-face’s vortex), `the-swim.md` §2a/§2b/§5c/§5d/§5b (the draw’s work), `the-dive.md` §2 (the descent), `the-flood.md` §2 (the surge’s spin), `the-marsh.md` §2 (the wet’s inverse), `the-rain.md` §3 (the fall’s drain), `the-canal.md` §2 (the bound channel), `the-cistern.md` §2 (the caught well), `the-estuary.md` §2 (the mixing’s vortex), `the-touch.md` §2 (the draw’s feel), `the-climb.md` §2 (the escape’s reverse), `field-instruments.md` §2.1 (the family rule), `energy-harnessing.md` §2/§6 (the drain’s cap), `tide-of-the-attractor.md` §1 (the spin’s season), `the-dispute.md` §2 (the drain’s boundary) — all seventeen two-way.**|
|| `the-incantation.md` (requested) | ✓ | ✓ | ✓ | ● | clean — the language’s reverse grammar, the ordered perturbation never a plea, phase-matched and fully legible; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-language.md` grammar) flagged non-canonical. **Canonical check: an incantation converts nothing, never creates order from nothing, never a free spend, never a mint — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-language.md` §2/§2.3/§3/§5b/5d/5e (the reverse grammar), `coherence-magic.md` §1/§2/§3/§5.1 (the budget), `the-chant.md` §1/§2.1/§4/§5d (the held settle), `the-shout.md` §1/§2/§6 (the projected stir), `the-working-song.md` §1/§2/§2.1/§4 (the cadenced settle), `the-siren.md` §2/§2.1/§4 (the lure-form), `the-dispute.md` §2 (the unbeatable field), `energy-harnessing.md` §2/§6 (the utterance’s cap), `field-instruments.md` §2.1/§1.2/§1.3 (the family rule), `the-festival.md` §2 (the gathered rite), `the-election.md` §1/§2.4 (the office’s rite), `the-rite-of-passage.md` §2 (the turning’s rite), `the-stilling.md` §2 (the quiet’s inverse), `the-vigil.md` §2 (the watched rite), `the-school.md` §2 (the taught rite), `the-apprenticeship.md` §2 (the learned rite), `field-npc-ai.md` (the NPC’s rite), `field-music.md` (the voice’s kin), `reason-field.md` (the reasoned rite), `the-observatory.md` §2 (the legible rite), `the-echo.md` §2.1 (the ripple’s kin), `the-compass.md` §2 (the pointed rite), `async-field-domain.md` (the ordered perturbation), `the-bell.md` §1/§4 (the voiced counterpart), `world-difficulty.md` §2 (the dial’s rite — **two-way**) — all twenty-five two-way.**|
|| `world-difficulty.md` (requested) | ✓ | ✓ | ✓ | ● | clean — the honest dial that scales the field’s own extremes, never a hidden punishment; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `field-hazards.md` storm locus) flagged non-canonical. **Canonical check: world-difficulty converts nothing, the dial scales the field’s own extremes, never generates order — a wild world’s storms convert nothing — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `field-hazards.md` §1/§2/§5.1/§5.3/open-Q2 (the dial’s ceiling), `weather-not-storm.md` §1/§2/§3/§5.3/§6e/§6d (the scale’s classifier), `tide-of-the-attractor.md` §1/§1.2/§2/§5a/§5d (the scaled season), `atmosphere-orbits-auroras.md` §1.3/§1.5/§3.4/§3.3 (the scaled sky), `the-wind.md` §1/§2/§5 (the scaled flow), `the-lightning.md` (the scaled discharge), `the-blizzard.md` §1–4 (the scaled erasure), `the-fog.md` §2 (the scaled blur), `the-drought.md` §2 (the scaled dry), `the-meteor.md` §2 (the scaled fall), `signature-predator.md` §2/§1.2 (the exposed dial), `energy-harnessing.md` §2/§6 (the world’s cap), `field-instruments.md` §2.1 (the family rule), `the-dispute.md` §2 (the scaled boundary), `chunk-field-quantization.md` (the scaled chunk), `async-field-domain.md` (the scaled domain) — all sixteen two-way.**|
|| `the-tunnel.md` (final wave) | ✓ | ✓ | ✓ | ● | clean — the horizontal’s twin, the shaft’s straightness made a passage, the under-hill cut that stays a crossing not a descent; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-shaft.md` twin) flagged non-canonical. **Canonical check: a tunnel converts nothing, the dug line spent never a gain, never a minted passage — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-shaft.md` §1/§2(b)/§2(a)/§2(f)/§3(c)/§5c (the horizontal twin — **two-way**), `the-cave.md` §1/§3/§5b (the passage’s hollow), `the-quarry.md` §1/§2(a)/§4/§5b (the through-cut), `the-bedrock.md` §1/§2(a)/§5b (the under-hill crossing), `the-tool.md` §2(a)/§2(b)/§3/§5b (the line’s bite), `the-carry.md` §2/§4/§5b (the passage’s haul), `the-climb.md` §3.1/§3.2/§3.3/§5b (the read-before), `the-ford.md` §1/§2 (the dry crossing), `the-causeway.md` §1/§6 (the through-way), `the-between.md` §2 (the dug between), `chunk-field-quantization.md` (the line’s chunks), `energy-harnessing.md` §2/§6 (the passage’s cap), `field-instruments.md` §2.1 (the family rule), `the-dispute.md` §2 (the dug boundary) — all fourteen two-way.**|
|| `the-waterfall.md` (final wave) | ✓ | ✓ | ✓ | ● | clean — the river’s descent taken as a free drop, the one drop the seacraft does not ride, the gradient’s discharge heard as its own voice; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-river.md` descent) flagged non-canonical. **Canonical check: a waterfall converts nothing, a rotor in the fall a real costed turbine with `(1−q)` waste — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-rain.md` §1/§2.1/§3.2 (the hard fall), `the-river.md` §1/§3a/§3b/§4c (the free drop), `the-climb.md` §1/§3.3/§4.3 (the vertical’s read), `the-sea.md` §2b/§4/§5b (the drop into the plain), `the-flood.md` §1/§3 (the display-abundance), `energy-harnessing.md` §1.1/§2/§6 (the fall’s cap), `field-music.md` §1/§2.4 (the roaring voice), `the-seacraft.md` §1/§2a/§4c (the un-ridden drop — **two-way**), `the-swim.md` §2a (the fall’s un-swimmable), `field-instruments.md` §2.1 (the family rule), `the-dispute.md` §2 (the fall’s boundary) — all eleven two-way.**|
|| `the-crane.md` (final wave) | ✓ | ✓ | ✓ | ● | clean — the built machine a rung-matched tool dresses and keeps, the vertical’s line reversed and aided, the builder’s lift; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-shaft.md` vertical) flagged non-canonical. **Canonical check: a crane converts nothing, never a free hoist, the counterweight’s fall a real cost — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-tool.md` §2(a)/§3/§5b (the built-rung), `the-carry.md` §1/§2/§4/§5b (the raised load), `the-cart.md` §1/§3/§5b (the vertical trade), `the-quarry.md` §1/§2(a)/§4 (the lifted cut), `the-shaft.md` §1/§2(b) (the reversed line), `house-that-steers.md` §1/§2.2/§5b (the builder’s lift), `energy-harnessing.md` §2/§6 (the lift’s cap), `reason-field.md` (the reasoned lift), `field-instruments.md` §2.1 (the family rule), `the-climb.md` §1 (the aided ascent), `the-fall.md` §5d (the balanced drop), `the-dispute.md` §2 (the lift’s boundary) — all twelve two-way.**|
|| `the-comet.md` (final wave) | ✓ | ✓ | ✓ | ● | clean — the meteor’s periodic return, one more body of the sky’s own orbit, the visiting bright named in the window’s long calendar; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-meteor.md` cousin) flagged non-canonical. **Canonical check: a comet converts nothing, the return’s bright spent never a gain, never a minted omen — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-meteor.md` §2/§5b/§5c (the returning bright), `atmosphere-orbits-auroras.md` §2/§2.1/§2.2/§2.3/§5 (the long-return body), `the-window-year.md` §1/§2/§3 (the calendar’s visitor), `tide-of-the-attractor.md` §1/§2/§5a (the long tempo), `the-observatory.md` §1/§2/§2.2 (the read line), `the-dawn.md` §1 (the rare turn), `the-eclipse.md` (the passing dark), `the-zenith.md` (the high read), `the-reading-ahead.md` (the forecast’s body), `field-instruments.md` §2.1 (the family rule), `energy-harnessing.md` §2/§6 (the visit’s cap), `the-dispute.md` §2 (the sky’s boundary) — all twelve two-way.**|
|| `the-bog.md` (final wave) | ✓ | ✓ | ✓ | ● | clean — the water’s staying, the ground’s two extremes with the desert, the soaked earth that cuts nothing and yields nothing; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-marsh.md` cousin) flagged non-canonical. **Canonical check: a bog converts nothing, the held wet spent never a gain, never a minted ground — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-marsh.md` §1/§2/§5/§7b (the deeper hiding-water), `the-flood.md` §1/§2/§4 (the water’s stay), `the-desert.md` §1/§2/§4a (the water’s two extremes), `the-walk.md` §1/§1.2/§2(a)/§2(b)/§4b (the soft step), `the-fall.md` §1/§2.1/§3/§4 (the ground’s sink), `the-quarry.md` §1/§2(a)/§4 (the soft ground), `the-rain.md` §1/§2.1/§3.2 (the water-keep), `the-meadow.md` (the wet meadow), `the-stratum-read.md` (the layered soak), `the-carry.md` §2/§4 (the sunk load), `field-instruments.md` §2.1 (the family rule), `the-dispute.md` §2 (the soaked boundary), `energy-harnessing.md` §2/§6 (the soak’s cap) — all thirteen two-way.**|
|| `the-atoll.md` (final wave) | ✓ | ✓ | ✓ | ● | clean — the sea-floor’s reef risen to the surface, the ring the flat water’s crown makes, the lagoon’s shelter the harbor’s own honesty; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-sea-floor.md` reef) flagged non-canonical. **Canonical check: an atoll converts nothing, the crown’s shelter spent never a gain, never a minted island — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-sea.md` §1/§2b/§5b (the plain’s crown), `the-sea-floor.md` §2a/§2b/§4.1/§5b (the risen reef), `the-harbor.md` §1/§4/§5d (the shelter’s honesty), `the-seacraft.md` §1/§2a/§2d/§4c (the lagoon’s harbor — **two-way**), `the-whirlpool.md` §1/§2(a) (the shelter’s contrast), `the-estuary.md` §1/§2 (the still middle), `life-signal.md` §1/§3 (the crown-of-life), `the-marsh.md` §2 (the wet ring’s kin), `field-instruments.md` §2.1 (the family rule), `energy-harnessing.md` §2/§6 (the ring’s cap), `the-dispute.md` §2 (the ring’s boundary) — all eleven two-way.**|
|| `the-anchor.md` (final wave) | ✓ | ✓ | ✓ | ● | clean — the banked reversible mooring landed, the crossing’s resting, the held station against the window’s long drift, the hold by the field’s own grip never a magic stick; canonical set cited verbatim (192³/64³/12³, dt=0.05, τ_c=0.5, ξ=φ⁶≈17.94, φ⁻²≈0.382, ω₀²=20.0, q≈0.947, q~1e-3…1e-1, ≈1–6 ms, ≈2,000, ≈40 ns/entity); theory (§2 `the-seacraft.md` reversible mooring) flagged non-canonical. **Canonical check: an anchor converts nothing, the held mooring spent never a gain, never a minted harbor — `output ≤ φ⁻¹·input` (no-free-energy §6 `energy-harnessing.md`) — verified.** **§1/§2 ↔ `the-seacraft.md` §1/§2a/§2d/§4c/open-Q6 (the banked mooring landed — **two-way, the seacraft’s open-Q6 now closed**), `tide-of-the-attractor.md` §1/§2/§5a (the held station), `the-harbor.md` §1/§2c/§4/§5d (the mid-water hold), `the-sea.md` §2b/§4 (the holding plain), `the-sea-floor.md` §1/§2a/§5d (the bite-ground), `the-carry.md` §1/§4/§5b (the carried mass), `the-tool.md` §2(a)/§4b (the setting bite), `the-oath.md` §2 (the bound hold), `field-instruments.md` §2.1 (the family rule), `energy-harnessing.md` §2/§6 (the hold’s cap), `the-dispute.md` §2 (the held boundary) — all eleven two-way.**|

---

## 2. Canonical-numbers appendix

The shared number set — one reference for future docs. Any doc quoting a
different figure for the same quantity is out of agreement with this table.

| Quantity | Canonical value | Established in |
|---|---|---|
| Grid cells | `64³ = 262,144` cells | `chunk-field-quantization.md` §1.2 / engine `grid_N` |
| Field-only publish (canonical) | **≈ 6 MiB** = q 1 + pot 1 + ∇(g·Φ) vec3-trim 3 + ρ single-channel 1 | `chunk-field-quantization.md` §2 |
|  — EY/EI-separate variant | 7 MiB (ρ split into EY + EI, 2 MiB) | §2 |
|  — grad-vec4 variant | 8 MiB (gradient published vec4, 4 MiB) | §2 |
|  — decimal note | 6 MiB ≈ 6.4 MB decimal; async-field-domain's "~6.4 MB" is the same figure, already reconciled in `chunk-field-quantization.md` §2 | both docs |
| Phase-1 box (chunk-aligned) | `box_aspect=(1,1,1)`, `cluster_radius=64` → full **192³ m**; `64³ = 3 m` whole cells → **12×12×12 chunks** (1,728); 1 m blocks = 1/3 trilinear sub-cell samples | §1.2 (resolves `async-field-domain` §7 Q1) |
| Stock φ-aspect box (engineering baseline) | `291.24 × 180 × 471.24 m`, `extent_min = 180` (aspect 1.618 : 1.0 : 2.618, `cluster_radius = 60`); cell 4.551 × 2.8125 × 7.363 m | §1.2 |
| ξ (chord coupling to gravity) | `ξ = φ⁶ ≈ 17.94` (exact 17.9443); so **ξ − 1 ≈ 16.94**, not 17.94 | engine; material-regimes §1 |
| ω₀² (resonance) | `ω₀² = 20.0` (engine `omega2` default) | engine; material-regimes §1 |
| qi_condensation_threshold | `0.5` (τ_c) | engine; chunk §2.2 |
| π/ρ clamp | `clamp((EY−EI)/(EY+EI), 0, 0.72)` | engine; coherence-magic §1 |
| φ⁻² | `≈ 0.382` | engine merge gate; material-regimes §1 |
| φ⁻³ | `≈ 0.236` | theory ladder (kept for reference) |
| Meshless sites | `2·16³ = 8192` sites at N=64 (`ML_N1=16`) | engine; async §2.2, chunk §5 |
| JOB_STEP_CAP / TREE_JOB_STEP_CAP | `64` / `8` | engine; async §2.3/§4.2 |
| dt | `0.05` (one field step per Minecraft tick, 20 Hz) | chunk §1.2 |
| Server per-tick budget | server sample cost **≈ 1–6 ms**; domain step ≈ 0.5–1.5 ms; ~44 ms (88%) of the tick unused | chunk §4 |
| Publish cadence | every Kth job (coalesced backlog drains over `JOB_STEP_CAP=64` slices), not per tick/step | async §2.3 |

**Verification across waves 7–28 (all sixty-four verified docs):** every one of
`world-seams`, `field-archaeology`, `field-hazards`, `resonance-seeds`,
`field-music`, `field-npc-ai`, `field-instruments`, `tide-of-the-attractor`,
`player-remains`, `deep-field-diving`, `pocket-cosmos`, `the-reading-ahead`,
`signature-predator`, `resonance-tutor`, `mouths-eye`, `life-signal`,
`reason-field`, `shared-ledger`, `weather-not-storm`, `patient-field`,
`fate-of-a-window`, `schema-that-settles`, `house-that-steers`,
`farm-that-feeds`, `coherence-highway`, `wound-remembered`,
`the-burden`, `the-name`, `sleep`, `the-map`, `seed-garden`, `the-chronicle`,
`worn-field`, `window-guests`, `the-inheritance`, `the-festival`, `the-clock`,
`the-mirror`, `the-funeral`, `the-cooked-field`, `the-cold`, `the-exile`,
`the-election`, `the-bell`, `the-silence`, `the-observatory`,
`the-apprenticeship`, `the-family`, `the-flood`, `the-treaty`, `the-lantern`,
`the-seeker`, `the-child`, `the-echo`, `the-stillness`, `the-oath`,
`the-healer`, `the-compass`, `the-memory-palace`, `the-language`, `the-census`,
`the-threshold`, `the-blight`, `the-window-year`, `the-hourglass`, `the-walk`,
`the-fallow`, `the-pilgrim`, `the-tide-staff`, `the-sea`, `the-tool`
cites this appendix (`corpus-reconciliation.md`)
as its canonical source and re-quotes the set verbatim (192³/64³/12³ box,
≈ 6 MiB publish, ξ = φ⁶ ≈ 17.94, φ⁻² ≈ 0.382, τ_c = 0.5, π/ρ clamp 0.72,
ω₀² = 20.0, dt = 0.05, ≈ 1–6 ms/tick, ≈ 40 ns/entity, ≈ 2,000 cap) — no doc
re-derives or silently alters a canonical value. **No new canonical numbers were
introduced.** The theory/project-sourced constants the verified docs use (the
mixing clock `T = 2π/[λ(1−q)]`, the winding bound `|δn| ≤ 0.162`,
`N_memory ≈ φ ≈ 1.6`, `ω_gap = φ·ω₀ ≈ 52.36`, the synth's R = 4 band and ~5%
CPU) are cited from their CassiTheory / `CassiCosmos/research/*` sources, not
presented as corpus-canonical — they are correctly left out of this table.
`tide-of-the-attractor`, `patient-field`, `the-reading-ahead`, `sleep`,
`seed-garden`, `window-guests`, `the-clock`/`the-mirror` (the tempo + the
phase-gap faces), `the-cold` (the mixing clock as the climate's tempo), and now
`the-election` (the momentum) lean most on the mixing-clock/`|δn|` pair;
those remain theory-sourced and are deliberately **not**
promoted to canonical here, and each doc itself flags its cadence/horizon as a
[probe]/[design] calibration, not a constant. The Clock and the Mirror both
explicitly keep the mixing clock **theory-cited with its speculation flag**
(`qi-as-time-clock.md` §1; the engine kernel's conversion term is q-free) and
gate their mechanical use on the L1–L3 probe (`patient-field.md` §5b) — never
promoted to engine fact.

**Wave 19–20 number checks (verified, no discrepancy):**
- **`the-funeral`'s `C(funeral)`** — the dissolved member's line settled as one
  coordinated op (a single high-magnitude close, or the summed `C(M)` over the
  funeral window with the dissolved final balance folded in) builds on
  `shared-ledger.md` §1.2's per-member `C(M)` aggregation **exactly** — the open
  question is the book-shape dial (one line vs summed), never the aggregation
  itself; it re-uses the landed aggregation slice verbatim.
- **`the-election`'s `C(M)`** — its `C(M) = Σ ops (net field-contribution of each
  op at its locality/rung/magnitude) budgeted against the bath's Δq/Δε²`
  formulation is `shared-ledger.md` §1.2's aggregation **verbatim** — verified no
  re-derivation and no new canonical number.
- **`the-bell`'s cost profile** — its "one trilinear sample inside the
  ≈ 1–6 ms/tick sample budget, exactly as the Weatherglass is
  (`field-instruments.md` §1.4)" **matches** the Weatherglass's per-tick cost
  profile exactly; the Bell adds no second sample, no write, no mint.
None introduce a figure outside the canonical set.

**Wave 21–22 number checks (verified, no discrepancy):**
- **`the-flood`'s `E_waste = (1−q)·E_throughput`** — the flood's waste law is
  `energy-harnessing.md` §2's machine-loss floor **verbatim** (its §2 table and
  §7 Cross-refs both cite it as such); verified no re-derivation and no new
  canonical number.
- **`the-lantern`'s cost profile** — its "one trilinear sample at the player's
  position, inside the ≈ 1–6 ms/tick server sample budget, exactly as the
  Weatherglass is (`field-instruments.md` §1.4)" **matches** the Weatherglass's
  per-tick cost profile exactly; the Lantern is a pure consumer, no second
  sample, no write, no mint (verified no divergence).
- **`the-observatory`'s cost profile** — each surface is "one trilinear sample
  (or a bounded cluster) off the ≈ 6 MiB publish, inside the ≈ 1–6 ms/tick
  server sample budget, exactly the Weatherglass's own §1.4 cost" — **matches**
  the Weatherglass cost profile exactly, repeated per surface; no new aggregate
  cost, no new channel.
- **`the-family` / `the-treaty`'s theory+design flags** — both ride the **landed
  member-id** ([design]-landed, `schema-that-settles.md` §2.1/§2.1.1) and the
  **persistent-Π identity** (theory-ratified with the `reason-field.md` §6a
  speculation flag). Verified the flags are carried exactly where their source
  docs draw them (`the-family.md` §6a; `the-treaty.md` §5) — the *joint* / *paired
  anchor* is each doc's [design] over that stack. No new canonical number.
None introduce a figure outside the canonical set.

**Wave 23–24 number checks (verified, no discrepancy):**
- **`the-compass`'s intent-phase size** — its "~32 KB f32 / 16 KB f16 for 8,192
  sites, ≈ half a percent of the canonical publish" **matches `reason-field.md`
  §2.2 exactly** (8,192 floats ≈ 32 KB f32 / 16 KB f16) — verified no divergence;
  the ≈ 50 µs site→chunk strided read it costs is `chunk-field-quantization.md`
  §5's, inside the ≈ 1–6 ms/tick budget.
- **`the-seeker`'s / `the-compass`'s cost profile** — both are "one trilinear
  sample (or the strided site read) at the player's position, inside the ≈ 1–6
  ms/tick server sample budget, on the Weatherglass's §1.4 cost profile" —
  **matches** the Weatherglass's per-sample cost exactly; both pure consumers, no
  second sample, no write, no mint.
- **`the-echo`'s and `the-stillness`'s theory citations carry the speculation
  flags** — the echo's *imprint-not-recording* framing and the stillness's §1
  companion line both explicitly mark the persistent-Π / mixing-clock theory with
  the `reason-field.md` §6a / `qi-as-time-clock.md` speculation flags; no theory
  constant is promoted as corpus-canonical.
- **`the-seeker`/`the-child`/`the-oath`/`the-healer` ride the landed
  member-id + persistent-Π theory flags** — each flags the member-id as
  [design]-landed and the persistent-Π identity as theory-ratified (with the
  speculation flag), exactly where their source docs draw the line; no new
  canonical number.
None introduce a figure outside the canonical set.

**schema-that-settles numbers verified against source (§5):** the ~16 B/record
`member` tag, the ~2,000-float ≈ 8 KB f32 / 4 KB f16 `M`-publication
(≈ 1.3‰ of the ≈ 6 MiB publish), and the 44 ms (88%) of the tick the sustained
op rides — all **match** `chunk-field-quantization.md` §4's server-per-tick
budget (`≈ 1–6 ms` sample; ~44 ms/88% unused) and the ≈ 2,000-entity cap /
≈ 40 ns/entity steering exactly. The schema is pure bookkeeping over the Q4
write lane (no new canonical number, no minting). No discrepancy found.

**the-burden's Coda-attraction verified against source (§2d):** its
`R = ρ_signature · τ · M_stability` and the three terms (trail quality = the
vent's ε² elevation × phase-coherence; τ = duration sustained; M_stability =
phase-stability) **match `signature-predator.md` §2.2 exactly** — the carried
debt feeds the same accumulation product; the burden's §2d is a designed addition
to an already-[design] model, not a divergent figure. **The wave-17 product
check stands** (`window-guests` matches §2.2 exactly; `the-chronicle` does NOT
quote the product — no divergence by non-engagement, its ~5% CPU synth-render
matches the source). **Wave-18 add — `the-mirror.md`** restates the same
product at lines 196–219 (face 2, the signature) **and its cross-references
claim "verified here against `signature-predator.md` §2.2 exactly" — that claim
is TRUE** (verified: the three terms and the formula match §2.2 verbatim; the
Mirror's added `M_stability` deferral note is consistent with
`schema-that-settles.md` §3). `the-clock` and `the-festival` do not quote the
product directly. No discrepancy found.

---

## 3. Fixes log

All fixes are additive and confined to the corpus; `README.md` and
`custom-blocks.md` untouched.

1. **`chunk-field-quantization.md` §1.2** — appended a two-way cross-reference to
   the box blockquote: the chunk-aligned box is identified as **the resolution
   of `async-field-domain.md` §7 Q1** (which already pointed at this doc). Closes
   the previously one-way Q1 dependency.
2. **`energy-harnessing.md`** —
   *(a)* §4.1: corrected `ξ − 1 = 17.9443` → `ξ − 1 ≈ 16.9443` (ξ = φ⁶ ≈ 17.94,
   so ξ−1 = 16.94; the old figure would imply ξ ≈ 18.94).
   *(b)* §7 Q1: corrected `ξ−1 = 17.94` → `ξ−1 ≈ 16.94` with a parenthetical.
   *(c)* §2 intro: anchored the machine write-back to the **Q4 player-return
   channel** of `async-field-domain.md` §7, mapping the doc's own
   "write-back lane" / "player-edit feedback lane" to the canonical term.
   *(d)* §0: same mapping note (harvester = consumer of the Q4 channel).
3. **`async-field-domain.md` §7 Q4** — named the channel's consumers
   (`coherence-magic.md` §5.1, `energy-harnessing.md` §2 intro/§0,
   `custom-blocks.md` §2) and recorded their proposed per-op input schema,
   closing the downstream ownership.
4. **Gradient orthography** — `∇(gΦ)` (no middle dot) diverges from the corpus
   canonical `∇(g·Φ)`. Added a note at first use in `async-field-domain.md` §2.1
   and `coherence-technologies.md` §0(b) mapping the two spellings to the same
   quantity. (Not a mass rewrite — additive note only.)
5. **`coherence-technologies.md` Q6** — documented pickup status. Concept 4
   (energy) landed: carried by `material-regimes.md` §5 and
   `energy-harnessing.md` §2/§4.4. Concept 5 (cascade staging) is carried **only**
   by `custom-blocks.md` §2 — `material-regimes.md` does not contain the staging
   language. Q6 is closed on the concept-4 numbers.
6. **Wave 7–8 pass (ledger-only).** No design-doc edits were made on this pass
   (constraint — the reconciliation re-run edits only `corpus-reconciliation.md`).
   The audit found the six new docs clean on refs/numbers/vocab, with all numbers
   cited (not re-derived). Two things are flagged for their owning workstreams,
   not changed here: **(i)** `field-music.md` §7's feasibility list still carries a
   stale "`field-hazards.md` …(not yet written)" note that contradicts that doc's
   own intro-level "**NOW EXISTS**" reconciliation of `field-hazards.md`
   (introduced when the hazard doc landed; its §7 was not touched after); **(ii)**
   the wave 8 cross-doc open-question pointers below are one-way in the source
   docs (the wave-8 doc cites the wave-7 doc's open question, but the wave-7
   doc does not yet cite back) — see verdict §4 for the exact list. These are
   additive one-line pointers to add where the owning doc lives; recording them
   here is this pass's contribution.
7. **`field-music.md` §7 (wave-9 closure).** Removed the stale "(not yet
   written)" on the hazard-audio gate and pointed it at `field-hazards.md` §2/§3
   (storm = `c_s`-traveling ε² front; desert = regional `q` collapse), consistent
   with the doc's own intro-level "**NOW EXISTS**" reconciliation.
8. **`field-hazards.md` open-Q2 (wave-9 closure).** Added the reverse pointer to
   `field-npc-ai.md` §4.3 (a decoherence-wielder's uncontrolled ε² burst is a
   storm-lighting seed; this doc's provenance probe settles it). Closes the
   two-way with field-npc-ai §4.3/§6b.
9. **`field-hazards.md` open-Q4 (wave-9 closure).** Added the reverse pointer to
   `field-npc-ai.md` open-Q5 (the drained-then-deserted-village boundary must be
   set with this doc's dead-window measurement). Closes the two-way.
10. **`field-archaeology.md` open-Q3 (wave-9 closure).** Added the reverse pointer
    to `field-music.md` open-Q2 (the growl-vs-scar classifier, heard, must land
    on the same distinguishability criterion). Closes the two-way.
11. **`async-field-domain.md` §7 Q1 (wave-9 closure).** Added the owner-by-
    assignment name: `world-seams.md` §4.2 is the recorded owner of the
    beyond-Phase-1 relocation policy, with `resonance-seeds.md` open-Q5 and
    `field-archaeology.md` §6c#2 depending on it. The ownership chain now reads
    both ways.
12. **Wave 9 ledger extension (this pass).** Audited `field-instruments.md`,
    `tide-of-the-attractor.md`, `player-remains.md` (all clean — canonical set
    cited verbatim, consistent vocab); recorded their theory-constant citations as
    non-canonical in §2; extended the audit table, fixes log, and verdict. The
    five design-doc closures (fixes 7–11) turn the wave-8 verdict's "one-way,
    add a pointer" items into closed two-way links. **The three wave-9 one-way
    pointers — `player-remains.md` open-Q1 → `field-npc-ai.md` §7 open-Q1,
    `player-remains.md` open-Q3 → `field-archaeology.md` §7 open-Q3, and
    `tide-of-the-attractor.md` open-Q3 → `field-hazards.md` §6.2/open-Q1 — are
    flagged for their owning workstreams to add the reverse pointer** (each
    reverse lives in a doc that predates the wave-9 doc, so no forward cite
    exists yet); see verdict §4.
13. **Wave-9 reverse-pointer closures + pocket-cosmos inward fold (this pass).**
    Closed the three wave-9 one-way pointers (fix 12 flagged) by adding the
    reverse pointer to each owning doc: `field-npc-ai.md` §7 open-Q1 →
    `player-remains.md` open-Q1; `field-archaeology.md` §7 open-Q3 →
    `player-remains.md` open-Q3 (and it already carries the field-music open-Q2
    pointer); `field-hazards.md` open-Q1 → `tide-of-the-attractor.md` open-Q3.
    Also added the two **pocket scaffolding** reverse-pointers from the pocket
    mandate: `world-seams.md` §3.1 → `pocket-cosmos.md` §1.2 (the pocket as the
    inward fold / third origin, beside the seeded and founded windows) and
    `resonance-seeds.md` §2.3 → `pocket-cosmos.md` §2.2 (the planted-and-held
    seed as a pocket-entry candidate — the pocket as the next fold of the
    seed's arc). These additions are one-line additive reverse-pointers; the
    wave-9 one-way chains each now read both ways.
14. **Wave 10–12 closures (this pass).** Eight reverse-pointer closures, in two
    families, mirroring the established open-question-ownership discipline:
    - **life-signal ×5 (the shared classifier, `life-signal.md` §3/§6):**
      `field-archaeology.md` §7 open-Q3, `field-music.md` open-Q2,
      `field-npc-ai.md` §7 open-Q2, `resonance-tutor.md` open-Q2, and
      `player-remains.md` open-Q3 each now carry a "Closed by `life-signal.md`
      §3/§6" pointer naming the maintenance-axis classifier as the answer — the
      five deferred `M`-publication questions re-point at one Phase-1 read that
      closes them all without publishing `M`.
    - **reason-field ×3 (the domain-side resolution, `reason-field.md`):**
      `field-npc-ai.md` §7 open-Q1, `player-remains.md` open-Q1, and
      `resonance-tutor.md` open-Q1 each now carry a "Resolved by
      `reason-field.md`" pointer committing the shared sampler-vs-domain fork to
      the **domain side** (NPC minds / re-lock fuse / trace journal all live in
      the publish's persistent-Π read) — the three parse as one resolution, as
      "the two must pick the same side" demanded.
    Ledger extension: audited the nine wave 10–12 docs (all clean —
    canonical set cited verbatim; reason-field's ~328 KB sites / ~32 KB f32 /
    16 KB f16 intent-phase verified against `async-field-domain.md` §2.2),
    extended the audit table and the verdict.
15. **Ref-verification + count correction (this pass, diligence).** *(a)* On a
    verification sweep, the `magic-systems.md` citation in `life-signal.md`
    (§2.2, the `M`-publication reference) and across the wave-10–12 set was
    **confirmed not a ghost ref**: the file exists at
    `CassiTheory/speculations/creative-extensions/magic-systems.md`, and each
    doc cites it either by the corpus's house-style bare name (`magic-systems.md`
    §1) with the full path given in its Cross-references (`life-signal.md` line,
    `field-npc-ai.md` §intro, `signature-predator.md`, `resonance-tutor.md`) or
    by the full relative path. Life-signal's refs dimension is therefore
    genuinely clean, as its audit row states. *(b)* The corpus count note is
    corrected: the designs/ directory grew to 36 files mid-pass (six concurrent
    wave-13+ docs: `farm-that-feeds`, `fate-of-a-window`, `house-that-steers`,
    `patient-field`, `schema-that-settles`, `weather-not-storm`), which are
    outside the 30-doc scope and flagged for their own audit pass.
16. **Schema-settlement re-points (wave 13–14 closure).** `schema-that-settles.md`
    settles the Q4 op-record and closes the five waiting consumers' open-questions
    two-way, by adding a reverse pointer to each:
    - `shared-ledger.md` **§7 open-Q1** (`member-id across death` → DECIDED: same
      member line, new lock), **§7 open-Q3** + **§4.1 footnote** (`sustain` →
      flag, adopted), **§4.3** (all three schema gaps → closed: member §2.1, cell-
      ownership §2.3, sustain §2.2), and **§6c** (`member-id` → LANDED; "the
      politics never starts" is now started).
    - `field-music.md` **open-Q3** (sustain-flag vs re-emit → SETTLED: flag).
    - `resonance-tutor.md` **§1** (the trace record → now the extended
      `{member, op, worldPos, rung, magnitude, sustain}`).
    - `player-remains.md` **§7 open-Q5** (conservation-of-you → made a ledger
      rule: same member line, new lock, no amnesty).
    - `reason-field.md` **§6a** (the Q4-schema gate → CLOSED by the schema; only
      the meshless/Π frontier remains open).
    - `life-signal.md` **open-Q2** and `signature-predator.md` **open-Q2** (`M`
      publication → DECIDED: deferred probe, gated on N2 / the accumulation
      model, ~8 KB f32 ≈ 1.3‰ add if it lands).
    Each pointer is one additive paragraph in the owning open-Q section; no open
    question is suppressed, each still records its genuine upstream gate.
17. **Weather-not-storm cross-reads (wave 13 closure).** The provenance probe's
    load-bearing reach recorded two-way:
    - `field-hazards.md` **open-Q2** → `weather-not-storm.md` §3 (the probe
      operationalization — the pre-registered owner of the measurement this
      open-Q asks for; both verdicts licensed).
    - `signature-predator.md` **§7a** → `weather-not-storm.md` §3/§6a (the Coda's
      formation re-gates on the same probe; a `← weather-not-storm §3/§6a`
      pointer makes the dependency two-way).
    - `tide-of-the-attractor.md` **§6 binding-risks** → `weather-not-storm.md`
      (the T1–T4 probe precedent the weather doc inherits; its §6e tide-
      correlation check reads this doc's tide — a two-way pointer).
    Ledger extension: audited the six wave 13–14 docs (all clean — canonical set
    cited verbatim; `schema-that-settles`'s member-tag / `M`-publication / 44 ms
    figures verified against source), extended the audit table and the verdict.
    Note: `farm-that-feeds.md` open-Q3 ("until Q4 settles") is closed by
    `schema-that-settles.md` §2.2 (sustain = flag) — recorded in its audit row.
18. **Wave-15 re-points (this pass).** Three reverse-pointer closures, linking the
    wave-15 docs to the gates they inherit:
    - `field-hazards.md` **open-Q4** (the dead-window / scar-lifecycle probe) →
      `wound-remembered.md` §6b/§7 (its deciding gate: does a broken lock re-open
      or heal? the wound's persistence claim rides the same measurement).
    - `signature-predator.md` **§7b** (the Q4-write-lane gate) →
      `wound-remembered.md` §7 (the deliberate lock-break's world-cause cannot
      exist as a deed until Q4 is a real perturbation path) and `the-burden.md`
      §6b (the mechanical layer's Coda-attraction/gates inherit this §7b gate).
    - `shared-ledger.md` **§6c** (member-id, landed) → `wound-remembered.md`
      open-Q3 ("whose wound is it?" — the provenance read needs the member-id to
      name the hand).
    Count check (Task 3): designs/ = 39 files, README index = 39 rows, no stray
    files, no ghost rows. Ledger extension: audited the three wave-15 docs (all
    clean — canonical set cited verbatim; `the-burden.md`'s
    `R = ρ_signature · τ · M_stability` verified against `signature-predator.md`
    §2.2 exactly), extended the audit table and the verdict.
19. **Wave-16 re-points + wave-17 capture (this pass).** Four reverse-pointer /
    note additions linking the wave-16/17 docs to the gates they extend or consume:
    - `life-signal.md` **§3.1** → [`sleep.md`](./sleep.md) §2.1 — records the
      **live-but-idle fifth class** (the maintenance axis at its idle extreme: a
      maintained lock at rest, motion collapsed, slow pulse + lock-holding intact),
      with the N2/N4 idle-extension Go/No-Go (`sleep.md` §7.1 inherits `life-signal`
      §6b's pre-registered probe). Two-way.
    - `the-burden.md` **§2b** → [`sleep.md`](./sleep.md) §1/§2b — records sleep as
      the Still Room's repayment at its **nightly body-scale instance** (a bed is a
      personal Still-Room interval, `sleep.md` §3), while the carried
      `R = ρ_signature·τ·M_stability` term continues through the night (two ledgers:
      clearing vs risk). Two-way.
    - `field-instruments.md` **§2.2** → [`sleep.md`](./sleep.md) §3 (the bed as the
      Still-Room idiom at the body's scale) and [`seed-garden.md`](./seed-garden.md)
      §3 (the vault as the Still-Room idiom at preservation scale) — the same
      base-idiom read at two further scales, zero new channel. Two-way.
    - `patient-field.md` **§5b** → (+ note) records the L1–L3 local-tempo probe as
      the **ground truth for the wave-18 `the-clock.md`** (then in-flight): the
      clock's mechanism and this probe's verdict must be read off one measurement.
      **(Resolved on the wave-18 pass, fixes 20 — the clock landed and now reads
      this probe back two-way.)**
    Also this pass (verification only, no edit): `player-remains.md` §5 open-Q5's
    schema-that-settles §2.1.1 pointer **resolves** (verified); `the-name.md` §7
    GRAND/LATER mechanical capstone **confirmed — no action** (the wave-18
    `the-inheritance.md` is the in-flight continuation).
    Ledger extension: audited the seven wave-16/17 docs (all clean — canonical set
    cited verbatim; `window-guests`' `R` product verified against source exactly,
    and `the-chronicle` confirmed to **not** quote the accumulation product at all
    — no divergence by non-engagement, with only its ~5% CPU synth-render citation
    matching the precedent), updated the count note to 46 and the audit table +
    verdict.
20. **Wave-18 re-points + queued-items closure (this pass).** Three reverse-pointer /
    note additions, plus the resolution of the two items the wave-16/17 pass queued:
    - `patient-field.md` **§5b** (the L1–L3 local-tempo probe) — tightened the
      ground-truth note from "pending wave 18" to the **landed `the-clock.md`**
      (whose §2/§5a/§6 and cross-references cite this probe as its deciding gate —
      the meaningful-hands verdict), and added **`the-mirror.md` §3/§6a** as a
      second rider (its phase-gap face stands or falls on the same L1–L3
      measurement; one probe, no re-derivation). **Closes the queued Clock
      ground-truth cross-ref two-way.**
    - `the-name.md` **§7** → [`the-inheritance.md`](./the-inheritance.md) §8 —
      added a **capstone-continuation reverse pointer**: the Inheritance
      (the will as a field act, a willed name as one claimable bequest, §2.2) is
      the identity stack's capstone, built on this doc's anchor princiiple and
      citing this §7's scaffold-now verdict as its model. **Closes the queued
      Inheritance capstone cross-ref two-way.**
    - `the-festival.md` **§4** — no action (noted for next pass): the corpus's joy
      doc; the mourning twin `the-funeral` is wave-19 in-flight.
    - `the-clock.md` **§5** and `the-mirror.md` **§3** — **verified** both ride
      `patient-field.md` §5b's L1–L3 probe, and the patient-field §5b note now
      reads the Clock and the Mirror back two-way.
    Ledger extension: audited the four wave-18 docs (all clean — canonical set
    cited verbatim; `the-mirror`'s `R = ρ_signature · τ · M_stability` verified
    against `signature-predator.md` §2.2 exactly — its "verified here" claim is
    TRUE), updated the count note to 50 indexed / 53 on-disk (3 in-flight wave-19
    unindexed), extended the audit table + verdict.
21. **Wave-19/20 re-points + the queued mourning-twin closure (this pass).** Five
    reverse-pointer / verification additions linking the wave-19/20 docs to the
    society's coordinated acts and shared probes:
    - [`the-festival.md`] **§4** → [`the-funeral.md`](./the-funeral.md) §1/§5.1 —
      added the **mourning-twin reverse pointer** (same coordinated mechanics, same
      `M ≈ 1` multiplicity gain, pointed at a loss instead of a harvest; same
      no-free-energy cap, emotional register inverted). **Closes the queued wave-19
      audit note (funeral as the festival's grief-inverse) two-way.**
    - [`the-exile.md`] **§7 open-Q2** → [`the-election.md`](./the-election.md)
      §4.4/§7 open-Q3 — added the **composition-tie reverse pointer**: the hollow-
      eye's "who performs it" is a stewardship decision whose natural home is the
      society's authority (the election's open-Q3, which already cites this open-
      Q2). The exile → election direction is added; the election → exile direction
      already existed (its open-Q3/cross-refs cite the exile's open-Q2). Two-way.
    - The **player-vs-NPC member fork** — verified and tightened three-way:
      `the-funeral.md` §7 open-Q4 (who the mourners are), `the-election.md` §7
      open-Q4 (who can be read as a candidate), and `the-exile.md` §7 open-Q2 (who
      performs the hollow-eye) all name it as "the same decision `field-npc-ai.md`
      §7 open-Q3 names"; that open-Q (`what makes a mind "that" NPC across a
      bath?`) is tightened to acknowledge it as the anchor whose §3.1-commons
      boundary **is** the membership answer (an NPC whose identity persists in the
      bath can be a real mourner/candidate/performer; a sum-of-individuals commons
      benefits from but does not hold the act). Three-way confirmed.
    - [`the-cold.md`] **§5** and [`the-election.md`] **§2.3** — verified both ride
      `tide-of-the-attractor.md` §5a (the tide probe); a **consumers reverse-pointer
      note** added at tide §5a naming the-cold (the climate gate) and the-election
      (the momentum gate), both reading one T1–T4 verdict. Two-way.
    - [`the-bell.md`] **§4** composes [`sleep.md`] §2.2's sitting signature —
      verified the bell cites sleep §2.2/§3; a **reverse pointer** added in sleep
      §2.2 naming the bell's night-ring as the settlement-scale voice that announces
      the sitting-signature danger before the overnight `τ` closes. Two-way.
    Ledger extension: audited the six wave-19/20 docs (all clean — canonical set
    cited verbatim; the `C(funeral)`/`C(M)` aggregation and the Bell's Weatherglass-
    equal cost profile verified against source exactly), closed the queued wave-19
    audit note, updated the count note to 56/56 (no stray, no ghost), extended the
    audit table + verdict.
22. **Wave-21/22 re-points (this pass).** Eight reverse-pointer / verification
    additions linking the wave-21/22 docs to the landed identity/seam/instrument
    stack:
    - [`the-apprenticeship.md`] **§5** → [`the-family.md`](./the-family.md) §4/§5
      — added the **pair-made-a-family reverse pointer**: the veteran–student
      pair that co-binds around a shared hearth *is* a family, the same two-body
      joint read as a held social atom (the Family §4 already cites this §1/§2.1/
      §5). Two-way.
    - [`the-funeral.md`] **§2.2** and [`the-inheritance.md`] **§2.2** → `the-family`
      — added the reverse pointers completing two-way: the funeral's re-condensation
      is **literal at the family's scale** (the dead co-holder's fraction re-bound
      into the family's anchor, `the-family.md` §3.2's reading of this §2.2); a will
      to the house is a **will to the family** (`the-family.md` §3.2/§4's reading of
      this §2.2). Both directions now resolve.
    - [`the-family.md`] **§4** → [`the-treaty.md`](./the-treaty.md) §2.1 — added
      the **lifted-to-the-window-scale reverse pointer**: the Treaty is the Family's
      joint-hold principle extended from N=2 members-in-one-window to N=2
      windows-across-the-seam (the Treaty §2.1 already cites this §2.1 as its
      ground). Two-way with the applied lift.
    - [`the-cold.md`] **§5.3** → [`the-flood.md`](./the-flood.md) — added the
      **mirror reverse pointer**: the flood is the cold's opposite and equal danger,
      the same no-free-energy cap stress-tested from the too-much side; `the-flood`
      also added as the **third consumer** of `tide-of-the-attractor.md` §5a (both
      gate on the probe's real high). Both directions now resolve.
    - [`the-bell.md`] **§4** → the-lantern and the-silence — added the **night's
      inverse and personal extensions reverse pointers**: the Lantern is the
      walker's personal bell, the hunting silence the Bell's quietest alarm; both
      docs already cite this §4 (the-lantern §3/§4, the-silence §2.3/§5.1). Two-way.
    - [`the-mirror.md`] **§4.4** → [`the-lantern.md`](./the-lantern.md) — added the
      **bedside-made-positional reverse pointer**: the wrong-warm Lantern at the bed
      pre-warns before the Mirror's `R` climbs (the-lantern §4 cites this §4.4 as its
      composition). Two-way.
    - [`tide-of-the-attractor.md`] **§5a** — added `the-flood` as the probe's third
      consumer (the surfeit climate riding the same T1–T4 verdict as the cold's
      thin-trough and the election's momentum). Resolves the flood's tide-gate two-way.
    Ledger extension: audited the seven wave-21/22 docs (all clean — canonical set
    cited verbatim; the-flood `E_waste = (1−q)·E_throughput` and the-lantern's
    one-trilinear-sample cost both verified against source exactly; the-family and
    the-treaty ride the landed member-id + persistent-Π theory flags correctly),
    updated the count note to 63/63 (no stray, no ghost), extended the audit table +
    verdict.
23. **Wave-23/24 re-points (this pass).** Seven reverse-pointer / verification
    additions linking the wave-23/24 docs to the settled identity/frontier/instrument
    stack:
    - [`the-seeker.md`] **§4/§2.2** ↔ [`the-compass.md`](./the-compass.md) §2.2/§4 —
      added the **complement pair**: the Seeker finds what *you* named (a bound
      persistent-Π anchor); the Compass reads what the *field* is organizing through
      (the nearest intent-dense site, unnamed). The compass already cited the seeker's
      §2.2 as the contrast; the seeker now reads the compass back. Two-way.
    - [`the-seeker.md`] **§4** ↔ [`reason-field.md`](./reason-field.md) §6a +
      [`the-family.md`](./the-family.md) §2.2 — added the **frontier reverse pointers**:
      the companion-seek and family-seek ride reason-field §6a's meshless/Π frontier
      and the family §2.2 hearth-well (the home-pull); a consumers note added at reason
      field §6a naming the seeker/compass/child, and the-family §2.2 now names the
      seeker back. Two-way.
    - [`the-child.md`] **§3.4** ↔ [`the-apprenticeship.md`](./the-apprenticeship.md) —
      added the **natural-first-teacher reverse pointer**: because a child's trace
      journal is empty, its first lesson is the live recording this §1's pair performs;
      the apprenticeship §5 now reads the child back as its N=1 charge. Two-way.
    - [`the-healer.md`] **§3.1** ↔ [`the-mirror.md`](./the-mirror.md) §2.4 — added the
      **dimmed-read reverse pointer**: the toll's legibility on the classification face
      (the healer reads burdened / wound-like at the edge); the steward-with-weight
      Board guard (`shared-ledger.md` §6e) verified cited correctly in §4.2.
      **Resurrection-limit ref corrected to `the-funeral.md` §2.3/§6d — verified no
      residual §3.3 mis-reference.** Two-way.
    - [`the-oath.md`] **§3.2** ↔ [`the-exile.md`](./the-exile.md) §4 — added the
      **quieter-sever reverse pointer**: the oath's break is the within-window sever
      quieter than exile — a promise's death, not a person's removal; the exile §4 now
      reads the oath back as its deliberate opposite end of the severance register.
      Two-way.
    - [`the-compass.md`] **§3.3** — verified the provenance line at site scale cites
      `weather-not-storm.md` §4a and `life-signal.md` §6 (both resolve; the reach's
      character classification inherits the shared provenance/noise-floor discipline).
    Ledger extension: audited the seven wave-23/24 docs (all clean — canonical set cited
    verbatim; the-compass's ~32 KB intent-phase and the seeker/compass cost profile
    verified against source exactly; the-echo/the-stillness theory flags carried;
    the-window pairing and the identity riders verified), updated the count note to
    70 indexed / 74 on-disk (4 wave-25 in-flight), extended the audit table + verdict.
24. **Wave-25/26 re-points (this pass).** Reverse-pointer / verification additions
    linking the wave-25 and wave-26 docs to the settled instrument/identity stack:
    - [`the-memory-palace.md`] **§3** ↔ [`the-observatory.md`](./the-observatory.md)
      §3.5 (the palace is the past-self to the observatory's present-self);
      **§2.2** ↔ [`the-chronicle.md`](./the-chronicle.md) §2.3 (the chronicle room);
      §4 → `house-that-steers.md` §3 (the ruin-of-choices) verified. Reverse pointers
      added at the observatory §3.5 (memory-palace + census) and the chronicle §2.3.
    - [`the-census.md`] **§5** ↔ [`the-observatory.md`](./the-observatory.md) §3.5
      (the population face) and **§2.2** ↔ [`the-child.md`](./the-child.md) §7
      open-Q2 (the dormancy threshold inherits the empty-row rule). Reverse pointer
      added at the-child open-Q2.
    - [`the-threshold.md`] **§2.2** ↔ [`the-bell.md`](./the-bell.md) §4 (the gate's
      crossing is the warning) and **§2.3** ↔ [`window-guests.md`](./window-guests.md)
      §3 (the arch is the first thing a visitor's provenance crosses). Reverse
      pointers added at the-bell §4 and window-guests §3.
    - [`the-language.md`] **§2.2** → `signature-predator.md` §2 (the "hunting" word)
      verified resolves (a shared accumulation product; no reverse pointer forced
      into the shared §2, consistent with how shared product sections are handled).
    - [`the-blight.md`] **§2.2/§4.1** ↔ [`field-emergent-ecology.md`](./field-emergent-ecology.md)
      §2.2/§5.3 (the over-bloom made pathological; conservation = the heal);
      **§2.1** ↔ [`the-flood.md`](./the-flood.md) §2/§3 (the wrong-band habitat);
      **§4.2** ↔ [`wound-remembered.md`](./wound-remembered.md) §1 (the clear's
      scar). Reverse pointers added at field-emergent-ecology §5.3, the-flood §3,
      wound-remembered §1.
    - [`the-window-year.md`] **§3.1** ↔ [`the-festival.md`](./the-festival.md) §3
      (the bright anchor); **§3.4** ↔ [`the-election.md`](./the-election.md) §4.3
      (the governance beat); **§3.3** ↔ [`the-funeral.md`](./the-funeral.md) §3.3
      (the anniversaries). Its composition rides the tide's [probe] period
      (`tide §5a`), never setting it. Reverse pointers added at the-festival §3,
      the-election §4.3, the-funeral §3.3.
    - [`the-hourglass.md`] **§1** ↔ [`the-clock.md`](./the-clock.md) §3.3 (the
      trip-meter to the speedometer) and **§3** ↔ [`the-healer.md`](./the-healer.md)
      §2 (the long bind's bound); **§2 theory-grounding path fixed to
      `../../CassiTheory/speculations/qi-as-time-clock.md`** (the bare
      `CassiTheory/...` path did not resolve from designs/). Reverse pointers added
      at the-clock §3.3 and the-healer §2.
    Ledger extension: audited the seven wave-25/26 docs (all clean — canonical set
    cited verbatim; the-window-year rides the tide's probe period; the-hourglass's
    Phase-1 slice matches the Weatherglass sample budget; the-blight's E_waste and
    gates verified), updated the count note, extended the audit table + verdict.
25. **Wave-27 re-points + the pilgrim↔walk correction (this pass).** Four wave-27
    docs audited, plus a critical correction to the-pilgrim:
    - **the-pilgrim correction:** the §1 once-flag and §3.1 had asserted "No
      `the-walk.md` is cited because none exists in the corpus today" — the-walk
      has since landed (stream-recovery). Both sections now cite
      [`the-walk.md`](./the-walk.md) as the un-roaded-crossing doc (the pilgrim is
      the walk's craft composed at the pilgrimage's purpose); the-walk §3 open-Q5
      ↔ the-pilgrim §3.1 two-way (where the walk ends; the pilgrimage reads it
      self-complete).
    - [`the-walk.md`] **§2a** ↔ [`coherence-highway.md`](./coherence-highway.md)
      §2.2 (the ridges walked ungated); **§2c** ↔ [`signature-predator.md`](./signature-predator.md)
      §2 (the walking trail). Reverse pointers added at highway §2.2 and
      signature-predator §2.
    - [`the-pilgrim.md`] **§2.1** ↔ [`field-archaeology.md`](./field-archaeology.md)
      §5.3 (the attended ruin — the conservation default walked to); **§4** ↔
      [`the-name.md`](./the-name.md) §6d (the re-bind's no-raise boundary). Reverse
      pointers added at field-archaeology §5.3 and the-name §6d.
    - [`the-fallow.md`] **§2a** ↔ [`material-regimes.md`](./material-regimes.md) §3
      (the mined vein gone-forever); **§4.2** ↔ [`the-exile.md`](./the-exile.md) §4
      (the leaver's fork). Reverse pointers added at material-regimes §3 and the-exile §4.
    - [`the-tide-staff.md`] **§2.1** ↔ [`tide-of-the-attractor.md`](./tide-of-the-attractor.md)
      §2 (the band marks the seasons); **§3.2** ↔ [`fate-of-a-window.md`](./fate-of-a-window.md)
      §1.3 (the drift-from-marks). Reverse pointers added at tide §2 and fate §1.3.
    Ledger extension: audited the four wave-27 docs (all clean — canonical set cited
    verbatim; the-walk's and the-tide-staff's Phase-1 slices match the Weatherglass
    sample budget; the-pilgrim's §2.1/§4 and the-fallow's §2a/§4.2 resolve), the
    count note updated, the audit table + verdict extended.
26. **Wave-28 re-points (this pass).** Two of the three wave-28 docs audited fully;
    the-vigil remains pending:
    - [`the-sea.md`] **§2a** ↔ [`coherence-highway.md`](./coherence-highway.md)
      §1.1 (the river as the conduit at nature's scale — the conduit idiom grown
      by the field rather than manufactured); **§2b** ↔ [`the-walk.md`](./the-walk.md)
      §2a/§2b (the fluid-drift / the flat-plain patience crossing); **§2c** ↔
      [`the-flood.md`](./the-flood.md) §2/§3 AND [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
      §1.3 (the flood is the wave made water — inherited, no new overflow);
      **§4** ↔ [`the-blight.md`](./the-blight.md) §2 (the poisoned sea is the
      blight's water-borne habitat). Reverse pointers added at highway §1.1,
      the-walk §2a, the-flood §3, atmosphere §1.3, the-blight §2. Two-way each.
    - [`the-tool.md`] **§2b** ↔ [`energy-harnessing.md`](./energy-harnessing.md) §2
      (the wear = the `(1−q)` waste law as alloy durability); **§2a** ↔
      [`material-regimes.md`](./material-regimes.md) §3/§4 (the bite = rung-depth
      meeting the material's rung); **§3** ↔ [`worn-field.md`](./worn-field.md) §1
      (the held regime = the worn tuple realized as an alloy); **§2c** ↔
      [`deep-field-diving.md`](./deep-field-diving.md) §2.2 (the scar = the
      un-contained hand-scale of the Bell's withdrawal). Reverse pointers added at
      energy-harnessing §2, material-regimes §3, worn-field §1, deep-field-diving
      §2.2. Two-way each.
    Ledger extension: audited the-sea and the-tool (canonical set cited verbatim;
    both Phase-1 slices match the Weatherglass sample budget; the-tool adds a
    bounded Q4 write, never a channel), the count note updated (the-vigil + waves
    29–30 remain PENDING audit), the audit table extended.
27. **Wave-28-vigil/29/30/31 re-points (this pass).** Completed the audits for the
    remaining twelve docs (the-vigil + the four wave-29 + the three wave-30 + the
    four wave-31), each reverse pointer inserted into its source doc and
    grep-verified before its audit row was written:
    - [`the-vigil.md`] **§2a** ↔ [`the-lantern.md`](./the-lantern.md) §2/§4 (the
      watch-read — the watcher reads the night field through the lantern's glow);
      **§2b** ↔ [`the-silence.md`](./the-silence.md) §2/§5.2 (the watch's listening);
      **§2c** ↔ [`the-threshold.md`](./the-threshold.md) §2.2 (the gate's keeper);
      **§2d** ↔ [`the-bell.md`](./the-bell.md) §4 (the bell's keeper); **§3** ↔
      [`signature-predator.md`](./signature-predator.md) §2/§7e (the clean-signature
      exposure); **§4** ↔ [`the-election.md`](./the-election.md) §4.3/§7 (the
      rotated watch). Reverse pointers added at each source. Two-way each.
    - [`the-working-song.md`] **§1** ↔ [`the-vigil.md`](./the-vigil.md) §1 (the
      second practice); **§2.1** ↔ [`field-npc-ai.md`](./field-npc-ai.md) §3.2 (a
      phase-locked group IS a working, `M ≈ 1`); **§3a** ↔ [`the-tool.md`](./the-tool.md)
      §2a (the lumber-camp's bite); **§3b** ↔ [`material-regimes.md`](./material-regimes.md)
      §3 (the forge-chant's line); **§3c** ↔ [`the-healer.md`](./the-healer.md) §2
      (the heal-song's bind). Reverse pointers added. Two-way each.
    - [`the-feral-instrument.md`] **§1/§2.2** ↔ [`reason-field.md`](./reason-field.md)
      §6a (the persistent-Π frontier); **§3a** ↔ [`house-that-steers.md`](./house-that-steers.md)
      §1/§3.2 (the self-chairing house); **§3b** ↔ [`the-memory-palace.md`](./the-memory-palace.md)
      §2 (the over-keeping palace); **§3c** ↔ [`seed-garden.md`](./seed-garden.md) §3/§4
      (the rudderless vault); **§4** ↔ [`the-oath.md`](./the-oath.md) §1/§3 (the
      re-bind fork). Reverse pointers added. Two-way each.
    - [`the-atlas-of-windows.md`] **§1** ↔ [`the-map.md`](./the-map.md) §1 + [`the-chronicle.md`](./the-chronicle.md)
      §1 (the page composition) + [`the-memory-palace.md`](./the-memory-palace.md) §1
      (the cross-window sibling); **§3.1** ↔ [`the-fallow.md`](./the-fallow.md) §3 (the
      depletion read); **§3.2** ↔ [`fate-of-a-window.md`](./fate-of-a-window.md) §1/§6c
      (the arc read, forecast-≠-fate). Reverse pointers added. Two-way each.
    - [`the-drift-road.md`] **§2b** ↔ [`tide-of-the-attractor.md`](./tide-of-the-attractor.md)
      §5b open-Q1 (the drift branch); **§3.3** ↔ [`the-stillness.md`](./the-stillness.md)
      §5.1 (the still-point end); **§3.4** ↔ [`the-festival.md`](./the-festival.md) §3
      (the once-celebration); **§1** ↔ [`weather-not-storm.md`](./weather-not-storm.md) §4
      (the precedent). Reverse pointers added. **Honest negative recorded:** the pass-spec's
      "drift-road `M ≈ 1` must cite field-npc-ai §3.2" item was verified against the
      doc, which carries **no phase-lock / `M` / field-npc-ai §3.2 reference** (it is a
      tide-verdict consequence doc); no cite was forced into it.
    - [`the-scar-lifecycle.md`] **§2.1** ↔ [`patient-field.md`](./patient-field.md) §3
      (the healed scar under rest); **§2.2** ↔ [`field-hazards.md`](./field-hazards.md)
      open-Q4 (the scar-lifecycle probe answered); **§2.3** ↔ [`house-that-steers.md`](./house-that-steers.md)
      §3.2 (the build-on-the-ruin) + [`field-archaeology.md`](./field-archaeology.md) §2
      (the strata-to-come); **§4.1** ↔ [`the-blight.md`](./the-blight.md) §4.2 (the
      clear's scar answered); **§4.3** ↔ [`fate-of-a-window.md`](./fate-of-a-window.md)
      §2/§3 (the scar read's deep branch); **§1** ↔ [`wound-remembered.md`](./wound-remembered.md)
      §1.2/§7 open-Q5 (the wound's fate answered). Reverse pointers added. Two-way each.
    - [`the-interstitial.md`] **§2a** ↔ [`world-seams.md`](./world-seams.md) §1.3/§2.1
      (the between the voyage crosses) + [`energy-harnessing.md`](./energy-harnessing.md)
      §7 Q1 (the dilute field) + [`the-sea.md`](./the-sea.md) §2b (the flat plain made
      total); **§2b** ↔ [`field-music.md`](./field-music.md) §1/§2 (the ringing) +
      [`the-atlas-of-windows.md`](./the-atlas-of-windows.md) §2 (the distant pages by
      ear); **§2c** ↔ [`signature-predator.md`](./signature-predator.md) §1/§7 (the
      lawful absence); **§3** ↔ [`patient-field.md`](./patient-field.md) §3.3 +
      [`the-hourglass.md`](./the-hourglass.md) §3 (the unforgiving patience). Reverse
      pointers added. Two-way each.
    - [`the-market.md`] **§2.1** ↔ [`schema-that-settles.md`](./schema-that-settles.md)
      §2.1 (the Q4 op-record — **verbatim**: the market's `{member, op, worldPos, rung,
      magnitude, sustain}` matches the settled record fields-and-order exactly); **§2.2**
      ↔ [`the-tool.md`](./the-tool.md) §2 + [`seed-garden.md`](./seed-garden.md) §3 (the
      traded provenance); **§2.3** ↔ [`the-name.md`](./the-name.md) §2 +
      [`shared-ledger.md`](./shared-ledger.md) §6d (the false-op cheat); **§3.3** ↔
      [`the-oath.md`](./the-oath.md) §1/§3 (the small vow); **§4.1** ↔ [`window-guests.md`](./window-guests.md)
      §3 (the visitor line); **§4.2** ↔ [`the-exile.md`](./the-exile.md) §4 (the exiled
      line); **§1/§2** ↔ [`the-census.md`](./the-census.md) §2.1 (the active-class face).
      Reverse pointers added. Two-way each.
    - [`the-scavenger.md`] **§2.1** ↔ [`field-emergent-ecology.md`](./field-emergent-ecology.md)
      §2.2/§6b (the residual-band organism) + [`signature-predator.md`](./signature-predator.md)
      §2.3/§7e (the spent margin / no-farming closure); **§2.3** ↔ [`the-fallow.md`](./the-fallow.md)
      §2a/§3 (the worked veins) + [`the-blight.md`](./the-blight.md) §4.2 (the clear's
      scar) + [`the-scar-lifecycle.md`](./the-scar-lifecycle.md) §2.2/§2.3 (the kept
      scar's edge / the avoided scar-kept place); **§3.3** ↔ [`field-hazards.md`](./field-hazards.md)
      §1 (the first non-hazard row); **§4** ↔ [`the-census.md`](./the-census.md) §1 (the
      spent's census). Reverse pointers added. Two-way each.
    - [`the-school.md`] **§2.1** ↔ [`the-working-song.md`](./the-working-song.md) §2.1 +
      [`field-npc-ai.md`](./field-npc-ai.md) §3.2 (the phase-lock applied to teaching);
      **§2.2** ↔ [`shared-ledger.md`](./shared-ledger.md) §1.2 (the booked competence) +
      [`the-market.md`](./the-market.md) §1 (legible the way the market books an
      exchange); **§3.1** ↔ [`the-vigil.md`](./the-vigil.md) §3/§4 + [`the-apprenticeship.md`](./the-apprenticeship.md)
      §2.2 (the teacher's drain / the faster burden); **§4** ↔ [`the-name.md`](./the-name.md)
      §2 + [`the-market.md`](./the-market.md) §2.3 (cannot teach what the field does not
      hold). Reverse pointers added. Two-way each.
    - [`the-sea-floor.md`] **§2a** ↔ [`the-sea.md`](./the-sea.md) §2b (the shelf's upper
      side); **§2b** ↔ [`field-emergent-ecology.md`](./field-emergent-ecology.md) §4.2/§6b
      (the reef's band) + [`the-blight.md`](./the-blight.md) §2 (the water-borne habitat);
      **§2c** ↔ [`deep-field-diving.md`](./deep-field-diving.md) §3.1/§4 (the descent /
      net-negative hold); **§4.1** ↔ [`the-scar-lifecycle.md`](./the-scar-lifecycle.md)
      §2.2 (the reef-edge scar); **§4.2** ↔ [`field-archaeology.md`](./field-archaeology.md)
      §2/§3.2 (the residue funnel). Reverse pointers added. Two-way each.
    - [`the-dawn.md`] **§2b** ↔ [`the-lantern.md`](./the-lantern.md) §4 (the night-read's
      end) + [`the-vigil.md`](./the-vigil.md) §3 (the watch's end) + [`signature-predator.md`](./signature-predator.md)
      §2 (the margin's thinning); **§2c** ↔ [`patient-field.md`](./patient-field.md) §3.3
      (the loan's interest re-opened); **§3** ↔ [`sleep.md`](./sleep.md) §3 (the bed
      decision's resolution); **§4** ↔ [`field-instruments.md`](./field-instruments.md)
      §2.1 (the family's becoming). Reverse pointers added. Two-way each.
    Ledger extension: wrote the twelve genuine audit rows (each only after its doc's
    re-points were grep-verified), the canonical-number checks (the market's op-record
    matches schema-that-settles §2.1 verbatim; the dawn's one-or-two-sample transition
    read and the sea-floor's shelf read both match the Weatherglass sample budget; the
    drift-road's missing-`M≈1` recorded as an honest negative), the count note updated
    (95/95 at this pass, waves 32–34 pending), the verdict extended to waves 28–31.
28. **Wave-32 re-points (pass 17).** The three wave-32 docs — the-commensal, the-gift,
    the-dispute — each reverse pointer inserted into its source doc and grep-verified
    before its audit row was written (28 edges total):
    - [`the-commensal.md`] **§2.1** ↔ [`field-emergent-ecology.md`](./field-emergent-ecology.md)
      §2.2/§6b (the organism-class run); **§2.3** ↔ [`house-that-steers.md`](./house-that-steers.md)
      §2.2 (the bath-edge habitat) + [`the-sea-floor.md`](./the-sea-floor.md) §2b (the
      reef-warden); **§3** ↔ [`field-emergent-ecology.md`](./field-emergent-ecology.md)
      §5.3 + [`energy-harnessing.md`](./energy-harnessing.md) §5.4 (the bounded
      anti-corruption assist, **net-negative**); **§3.3** ↔ [`field-hazards.md`](./field-hazards.md)
      §1 (the first positive row); **§1/§4** ↔ [`field-npc-ai.md`](./field-npc-ai.md)
      §1/§3 (the servant/neighbor line); **§1** ↔ [`the-scavenger.md`](./the-scavenger.md)
      §1/§2 (the bright twin). Reverse pointers added at each source. Two-way each.
    - [`the-gift.md`] **§2.1** ↔ [`schema-that-settles.md`](./schema-that-settles.md)
      §2.1 (the op-record — **verbatim** `{member, op, worldPos, rung, magnitude,
      sustain}`) + [`the-market.md`](./the-market.md) §2.3/§3 (the booked exchange's
      inverse); **§2.2** ↔ [`shared-ledger.md`](./shared-ledger.md) §6d (the no-false-booking
      from the not-booking side); **§2.3** ↔ [`the-name.md`](./the-name.md) §2 (the false
      gift is a false name); **§3.2** ↔ [`the-festival.md`](./the-festival.md) §2.3 (the
      tide-high generosity / spent-never-free); **§3.3** ↔ [`field-npc-ai.md`](./field-npc-ai.md)
      §3 (the commons' invisible glue); **§4.3** ↔ [`the-exile.md`](./the-exile.md) §4 +
      [`window-guests.md`](./window-guests.md) §3 + [`schema-that-settles.md`](./schema-that-settles.md)
      §2.1.1 (the severed line / the visitor line / no amnesty); **§4.2** ↔ [`the-oath.md`](./the-oath.md)
      §1/§3 (the un-bound giving); **§6d** ↔ [`energy-harnessing.md`](./energy-harnessing.md)
      §6 (the gift converts nothing, never mints); **§3** ↔ [`the-window-year.md`](./the-window-year.md)
      §3 (the giving tide). Reverse pointers added. Two-way each.
    - [`the-dispute.md`] **§2.1** ↔ [`shared-ledger.md`](./shared-ledger.md) §6d +
      [`field-npc-ai.md`](./field-npc-ai.md) §6d + [`schema-that-settles.md`](./schema-that-settles.md)
      §2.1 (the no-false-booking + the determinism + the claim's record shape) +
      [`the-name.md`](./the-name.md) §1/§2/§6e (the anchors' provenance) +
      [`life-signal.md`](./life-signal.md) §3 (the maintenance read); **§2.2** ↔
      [`the-observatory.md`](./the-observatory.md) §2 (the present-state read); **§3.2** ↔
      [`the-oath.md`](./the-oath.md) §1/§3 + [`the-market.md`](./the-market.md) §2.3 +
      [`the-election.md`](./the-election.md) §4.3/§4.4 (the vows, the clear-book, the
      stewardship); **§3.3** ↔ [`the-exile.md`](./the-exile.md) §2/§4 (the verdict's
      severance); **§4** ↔ [`the-name.md`](./the-name.md) open-Q3 + [`the-treaty.md`](./the-treaty.md)
      §3/§4 (the two-true-holds limit / the cross-window edge); **open-Q3** ↔
      [`field-npc-ai.md`](./field-npc-ai.md) §7 open-Q3 (the player-vs-NPC claimant fork).
      Reverse pointers added. Two-way each.
    Ledger extension: wrote the three genuine audit rows (commensal/gift/dispute, each
    after its edges were grep-verified), the canonical-number checks (the gift's op-record
    matches schema-that-settles §2.1 verbatim; the commensal's assist net-negative per
    energy-harnessing §5.4), the count note updated, the verdict extended to wave 32.
29. **Wave-33 re-points (pass 18).** The four wave-33 docs — the-window-pulse, the-zenith,
    the-stratum-read, the-harbor — each reverse pointer inserted into its source doc and
    grep-verified before its audit row was written (42 edges total):
    - [`the-window-pulse.md`] **§2.1** ↔ [`house-that-steers.md`](./house-that-steers.md)
      §1/§2.2 (the bath — the level) + [`shared-ledger.md`](./shared-ledger.md) §1.2/§6c
      (the lines' mutual drift) + [`the-name.md`](./the-name.md) §1/§3.2/§6e (the anchors'
      held-locks — the tethers) + [`the-commensal.md`](./the-commensal.md) §3 (the warm
      steadiness) + [`life-signal.md`](./life-signal.md) §3/§4 (the maintenance axis / the
      breathing read); **§2.2** ↔ [`fate-of-a-window.md`](./fate-of-a-window.md) §1/§6 (the
      present's sibling) + [`the-window-year.md`](./the-window-year.md) §2/§3 (the rhythm);
      **§3** ↔ [`the-census.md`](./the-census.md) §2/§3/§7 (the sibling); **§3** ↔
      [`the-observatory.md`](./the-observatory.md) §2/§6b (the seat); **§4** ↔
      [`the-healer.md`](./the-healer.md) §2 (the we/never-I boundary). Reverse pointers
      added. Two-way each.
    - [`the-zenith.md`] **§2a** ↔ [`energy-harnessing.md`](./energy-harnessing.md) §2/§6
      (the waste law / the cap — the drain) + [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
      §1.4/§1.3/§2/§3 (the sky ceiling it tops); **§2b** ↔ [`the-interstitial.md`](./the-interstitial.md)
      §2a/§4 (the thin — the far side) + [`the-sea-floor.md`](./the-sea-floor.md) §1 (the
      interface precedent); **§2c** ↔ [`world-seams.md`](./world-seams.md) §2/§2.3 (the edge
      you cannot leave through); **§3** ↔ [`field-archaeology.md`](./field-archaeology.md)
      §2.1 (the ozone — the waste's residue) + [`the-observatory.md`](./the-observatory.md)
      §2 (the ceiling read) + [`deep-field-diving.md`](./deep-field-diving.md) §1 (the top
      mirror of the deep) + [`the-sea.md`](./the-sea.md) §2b (the plain's other end).
      Reverse pointers added. Two-way each.
    - [`the-stratum-read.md`] **§2.1** ↔ [`field-archaeology.md`](./field-archaeology.md)
      §2/§3.2/§5.3 (the strata / the core sample / the leave-in-place fork) +
      [`the-clock.md`](./the-clock.md) §1/§5(b)/§6 (the present-face sibling) +
      [`the-hourglass.md`](./the-hourglass.md) §1/§5(b) (the interval-face sibling) +
      [`fate-of-a-window.md`](./fate-of-a-window.md) §1/§5/§2 (the future-face sibling);
      **§2.2** ↔ [`the-scar-lifecycle.md`](./the-scar-lifecycle.md) §2.2/§3.1/§2.1 (the kept
      scar's wound-depth / the healed band) + [`the-fallow.md`](./the-fallow.md) §2a/§5(d)
      (the pulled layer) + [`the-sea-floor.md`](./the-sea-floor.md) §2a/§4.2 (the shelf's
      underwater strata); **§4** ↔ [`the-memory-palace.md`](./the-memory-palace.md)
      §1/§4/§6(d) (the chosen-vs-kept complement); **§3** ↔ [`life-signal.md`](./life-signal.md)
      §3/§6 (the live-vs-residue classifier); **§2.1/§2.3** ↔ [`field-instruments.md`](./field-instruments.md)
      §2.1/§1.4 (the family rule / sample-at-position). Reverse pointers added. Two-way each.
    - [`the-harbor.md`] **§2a** ↔ [`the-threshold.md`](./the-threshold.md) §1/§2.1/§4/§6b
      (the boundary-mark made a place) + [`the-interstitial.md`](./the-interstitial.md)
      §1/§2/§3 (the pier into the thin) + [`world-seams.md`](./world-seams.md) §1/§2/§2.3
      (the voyage it begins / the cost never changed) + [`the-atlas-of-windows.md`](./the-atlas-of-windows.md)
      §2/§3 (the pages it writes) + [`the-treaty.md`](./the-treaty.md) §1/§2.2 (the crossing
      it begins); **§2b** ↔ [`the-lantern.md`](./the-lantern.md) §2/§4 (the lamp — the
      honest reach); **§2c** ↔ [`schema-that-settles.md`](./schema-that-settles.md)
      §2.1/§2.3 + [`shared-ledger.md`](./shared-ledger.md) §1.2/§2 (the ledger — the booked
      departure); **§2d** ↔ [`the-vigil.md`](./the-vigil.md) §2c/§2d/§3 (the keeper — the
      last watch); **§2a** ↔ [`the-sea.md`](./the-sea.md) §2b/§5d (the pier over water);
      **§4** ↔ [`the-fallow.md`](./the-fallow.md) §1/§3 (the quiet harbor's face) +
      [`the-census.md`](./the-census.md) §2/§3 (the active class at the edge); **open-Q5** ↔
      [`the-walk.md`](./the-walk.md) open-Q5 (the walk's settlement-scale end). Reverse
      pointers added. Two-way each.
    Ledger extension: wrote the four genuine audit rows (pulse/zenith/stratum-read/harbor,
    each after its edges were grep-verified), the canonical-number checks (the harbor's
    op-record matches schema-that-settles §2.1 verbatim; the stratum-read's one-sample-per-
    stratum and the pulse/zenith pure-consumer costs match the Weatherglass sample budget),
    the count note updated, the verdict extended to wave 33.
30. **Wave-34 re-points (pass 19).** The three wave-34 docs — the-story, the-rite-of-passage,
    the-mirror-creature — each reverse pointer inserted into its source doc and grep-verified
    before its audit row was written (34 edges total):
    - [`the-story.md`] **§2** ↔ [`the-name.md`](./the-name.md) §2 (the load-bearing law — an
      untrue story is a false name) + [`field-archaeology.md`](./field-archaeology.md)
      §1.2/§2 (determinism-is-not-recoverability / the residue model — the story's
      ground-truth); **§2.2** ↔ [`the-name.md`](./the-name.md) §3 (the named contribution
      legible) + [`the-memory-palace.md`](./the-memory-palace.md) §2.2/§4 (the chronicle
      room / the maintained hold); **§3.1** ↔ [`the-chronicle.md`](./the-chronicle.md)
      §3/§5 (the narrative elements / the never-adds shaping bound); **§3.2** ↔
      [`the-reading-ahead.md`](./the-reading-ahead.md) §1.1/§2.2/§6.3/§7c (the momentum's
      narrative form); **§3.3** ↔ [`the-language.md`](./the-language.md) §1/§2.2/§2.3 (the
      sites as text / the words / the grammar) + [`the-pilgrim.md`](./the-pilgrim.md) §2.1
      (a named place's story told at the place); **§3.4** ↔ [`the-festival.md`](./the-festival.md)
      §3/§2.2 (the telling-tide / the re-bind) + [`the-window-year.md`](./the-window-year.md)
      §3.1 (the bright anchor); **§3.5** ↔ [`the-school.md`](./the-school.md) §2 (the lesson
      it wears — a school cannot teach what the field does not hold) + [`the-child.md`](./the-child.md)
      §3.4 (the first lesson). Reverse pointers added. Two-way each. **Canonical check: the
      story's never-adds shaping bound matches the-chronicle §5's "It never adds events."
      verbatim.**
    - [`the-rite-of-passage.md`] **§2.1** ↔ [`the-child.md`](./the-child.md) §1/§3 (the
      empty book's first page) + [`the-name.md`](./the-name.md) §1/§2 (the Π-anchor a rite
      holds); **§2.2** ↔ [`the-apprenticeship.md`](./the-apprenticeship.md) §1/§2.2 (the
      pair-bond / the shelter + faster accrual) + [`the-school.md`](./the-school.md)
      §2.1/§4 (the pair made a group) + [`the-burden.md`](./the-burden.md) §1/§2a (the
      loan / the interest — the first channel's risk); **§2.3** ↔ [`the-family.md`](./the-family.md)
      §1/§2.1/§3.3 (the shared-Π / co-binding / sheds-like-a-false-name) + [`the-oath.md`](./the-oath.md)
      §2.1/§4.1 (the vow / the marriage-bond); **§2.4** ↔ [`the-election.md`](./the-election.md)
      §1/§4.3 (the read / the office's term) + [`the-tide-staff.md`](./the-tide-staff.md)
      §1/§5 (the standing gauge); **§2.5** ↔ [`resonance-seeds.md`](./resonance-seeds.md)
      §1/§2.1/§2.3/§3.1 (the seed / the one-way Q4 / the new window) + [`world-seams.md`](./world-seams.md)
      §3.2 (the founding act precipitates a fresh anchor); **§3** ↔ [`the-festival.md`](./the-festival.md)
      §1/§2 (the one-chord at a being's scale) + [`field-npc-ai.md`](./field-npc-ai.md) §3.2
      (the group working, `M ≈ 1`) + [`energy-harnessing.md`](./energy-harnessing.md) §2/§6
      (the `(1−q)` waste / the cap — a rite is spent never free). Reverse pointers added.
      Two-way each. **Canonical check: the rite's `M ≈ 1` phase-locked act is grounded
      verbatim in field-npc-ai §3.2's "a group acting phase-locked IS a working."**
    - [`the-mirror-creature.md`] **§2.1** ↔ [`signature-predator.md`](./signature-predator.md)
      §1/§2.2/§3/§7e/§8 (the phase-matching / the accumulation law / the tell-as-approach /
      the no-farming gate / the readable trail); **§3** ↔ [`life-signal.md`](./life-signal.md)
      §1/§3.1/§3.2/§6b (the maintenance axis / the four classes / the drain shape / the
      noise-floor) + [`reason-field.md`](./reason-field.md) §3.1/§6a (the persistent-Π mind /
      the frontier); **§4** ↔ [`the-name.md`](./the-name.md) §1/§2/§6b (the false-name decay /
      the Phase-1-legible principle); **§1/§5** ↔ [`the-scavenger.md`](./the-scavenger.md)
      §1/§2 (the stranger-object faces / the residual fit) + [`the-commensal.md`](./the-commensal.md)
      §1/§4 (the positive-face contrast) + [`field-hazards.md`](./field-hazards.md)
      §1/§5.1/§5.3 (the danger layer / the read-by-testing inversion / the cap); **§2.2** ↔
      [`the-burden.md`](./the-burden.md) §1/§2c/§2d (the carried signature / the legibility /
      the Coda-stability); **§3.3** ↔ [`the-vigil.md`](./the-vigil.md) §3 (the exposed watch).
      Reverse pointers added. Two-way each. **Canonical check: the mirror's `R = ρ_signature ·
      τ · M_stability` matches signature-predator §2.2's resonance law verbatim (the `M`
      deferred per schema-that-settles §3).**
    Ledger extension: wrote the three genuine audit rows (story/rite/mirror-creature, each
    after its edges were grep-verified), the canonical-number checks (the mirror's R product
    and the rite's M≈1 grounded verbatim in their source sections; the story's never-adds
    bound matches chronicle §5), the count note updated, the verdict extended to wave 34.
31. **Wave-35 re-points (pass 20).** The four wave-35 docs — the-loan, the-fall, the-swim,
    the-bedrock — each reverse pointer inserted into its source doc and grep-verified before
    its audit row was written (37 edges total, plus the swim↔fall two-way special item):
    - [`the-loan.md`] **§2.1** ↔ [`schema-that-settles.md`](./schema-that-settles.md)
      §2.1/§2.2 (the op-record / the sustain flag — a loan is the settled record's deferred
      line) + [`the-tool.md`](./the-tool.md) §2 (the future contribution) + [`seed-garden.md`](./seed-garden.md)
      §3 (the collateral) + [`farm-that-feeds.md`](./farm-that-feeds.md) §4 (the repayment);
      **§2.2** ↔ [`the-window-year.md`](./the-window-year.md) §3.4 (the term "next harvest")
      + [`tide-of-the-attractor.md`](./tide-of-the-attractor.md) §2/§5a (the beat, priced by
      the tide's q); **§3** ↔ [`the-burden.md`](./the-burden.md) §2a (the patience-interest /
      the interest form) + [`patient-field.md`](./patient-field.md) §3.3/§5d (the loan at
      thin / the cap); **§4a** ↔ [`energy-harnessing.md`](./energy-harnessing.md) §6 (a loan
      is not a mint) + [`the-market.md`](./the-market.md) §6d (the exchange never a mint);
      **§4b** ↔ [`the-oath.md`](./the-oath.md) §3 (the default edge — a promise naming what
      is not decays) + [`the-exile.md`](./the-exile.md) §4 (the leaver's fork) +
      [`the-fallow.md`](./the-fallow.md) §2a (the depletion edge). Reverse pointers added.
      Two-way each. **Canonical check: the loan's op-record `{member, op, worldPos, rung,
      magnitude, sustain}` matches schema-that-settles §2.1 verbatim.**
    - [`the-fall.md`] **§2** ↔ [`coherence-highway.md`](./coherence-highway.md) §2 (the
      gradient owned bare) + [`the-walk.md`](./the-walk.md) §2a (the craft removed) +
      [`energy-harnessing.md`](./energy-harnessing.md) §2 (the `(1−q)` absent mid-flight);
      **§3** ↔ [`the-scar-lifecycle.md`](./the-scar-lifecycle.md) §2.1/§2.2 (the shallow
      healable / the kept scar's edge) + [`wound-remembered.md`](./wound-remembered.md) §1
      (the impact's spike); **§4** ↔ [`the-sea.md`](./the-sea.md) §2b (the soft landing) +
      [`deep-field-diving.md`](./deep-field-diving.md) §3 (the controlled descent's inverse);
      **§2/§4** ↔ [`patient-field.md`](./patient-field.md) §2/§3.3 (the patience-free act).
      Reverse pointers added. Two-way each. **Canonical check: the fall's river law
      `a = −G_N·(π/ρ)·∇(g·Φ)` matches corpus-reconciliation's canonical steer verbatim.**
    - [`the-swim.md`] **§2a** ↔ [`the-sea.md`](./the-sea.md) §2b (the medium — a uniform q
      hides the ridges) + [`energy-harnessing.md`](./energy-harnessing.md) §2 (the
      liquid-regime waste); **§2b** ↔ [`the-walk.md`](./the-walk.md) §2a (the gradient read
      blind) + [`coherence-highway.md`](./coherence-highway.md) §2 (the blind gradient);
      **§3** ↔ [`the-hourglass.md`](./the-hourglass.md) §3 (the duration — you cannot
      out-swim the sea's patience) + [`patient-field.md`](./patient-field.md) §3.3 (the loan
      at thin); **§4/open-Q5** ↔ [`the-fall.md`](./the-fall.md) §4.2 (the two-way bridge —
      **SPECIAL ITEM, closed**); **§2c** ↔ [`the-sea-floor.md`](./the-sea-floor.md) §2b/§4
      (the descent to the reef). Reverse pointers added. Two-way each. **Special item
      (fix 31): the swim↔fall two-way is LANDED** — the-swim originally withheld it because
      the-fall.md did not exist on disk at its write time; the-fall now exists, so the swim's
      open-Q5 is **closed as resolved** with an additive note (bridge is now a landed two-way:
      a fall into the sea is the swim's beginning; the swim's descent is the fall's soft
      landing), and the-fall.md carries the swim reverse pointer. The two-way claim is backed
      by actual reverse-pointer lines in both docs.
    - [`the-bedrock.md`] **§2a** ↔ [`material-regimes.md`](./material-regimes.md) §4 (the
      maximal-rung regime) + [`the-tool.md`](./the-tool.md) §2a (the bite's wall); **§2c** ↔
      [`deep-field-diving.md`](./deep-field-diving.md) §3/§4 (the descent's end — no below);
      **§3** ↔ [`material-regimes.md`](./material-regimes.md) §3 (the precipitation law) +
      [`field-archaeology.md`](./field-archaeology.md) §2.4 (the strata's base) +
      [`the-fallow.md`](./the-fallow.md) §2a (the un-touched face); **§4** ↔
      [`field-archaeology.md`](./field-archaeology.md) §2.3/§3.2 (the archaeology reads down
      to it) + [`resonance-seeds.md`](./resonance-seeds.md) §1.1 (the seed's deep rest);
      **§1/§4** ↔ [`the-zenith.md`](./the-zenith.md) §1/§3 (the bottom face) +
      [`the-sea-floor.md`](./the-sea-floor.md) §1 (the absolute floor). Reverse pointers
      added. Two-way each.
    Ledger extension: wrote the four genuine audit rows (loan/fall/swim/bedrock, each after
    its edges were grep-verified), the canonical-number checks (the loan's op-record matches
    schema §2.1 verbatim; the fall's river law matches the canonical steer), the swim↔fall
    two-way special item closed with the grep-verified reverse pointers, the count note
    updated, the verdict extended to wave 35.
32. **Wave-36 re-points (pass 21).** The three wave-36 docs — the-cave, the-landform-name,
    the-witness — each reverse pointer inserted into its source doc and grep-verified before
    its audit row was written (38 edges total):
    - [`the-cave.md`] **§2a** ↔ [`the-scar-lifecycle.md`](./the-scar-lifecycle.md) §2.2/§2.3
      (the kept scar's edge / the scar-kept place) + [`the-stratum-read.md`](./the-stratum-read.md)
      §2.2 (the emptied band — a cave is a stratum that holds nothing); **§2b** ↔
      [`the-fallow.md`](./the-fallow.md) §2a/§2c (the emptied deep-rung store) +
      [`deep-field-diving.md`](./deep-field-diving.md) §6.3 (the Bell's evacuated deep);
      **§2c** ↔ [`field-hazards.md`](./field-hazards.md) §4.2/§4.4 (the BH's swept wake) +
      [`the-bedrock.md`](./the-bedrock.md) §7 open-Q4 (the floor's contrast / the maximal-rung
      gate); **§2d** ↔ [`the-flood.md`](./the-flood.md) §2/§3/§4.1 + [`the-fallow.md`](./the-fallow.md)
      §2d (the aftermath's undercut); **§3** ↔ [`deep-field-diving.md`](./deep-field-diving.md)
      §3.1/§5 + [`the-stratum-read.md`](./the-stratum-read.md) §2 + [`field-archaeology.md`](./field-archaeology.md)
      §3.2/§1.2 (the hollow reads as itself — the terraces thin, the layered read, the core
      sample, determinism-is-not-recoverability); **§4** ↔ [`deep-field-diving.md`](./deep-field-diving.md)
      §2.2/§6.2 + [`the-bedrock.md`](./the-bedrock.md) §2a + [`field-hazards.md`](./field-hazards.md)
      §2 + [`energy-harnessing.md`](./energy-harnessing.md) §2 (the character — the inversion,
      the dense floor, the desert, the `(1−q)` glow); **§6** ↔ [`the-sea-floor.md`](./the-sea-floor.md)
      §6b + [`the-bedrock.md`](./the-bedrock.md) §5b (the volume precedent). Reverse pointers
      added. Two-way each. **Canonical check: the cave's Phase-1 slice reads the ≈ 6 MiB
      publish inside the ≈ 1–6 ms/tick sample budget — matches the Weatherglass cost.**
    - [`the-landform-name.md`] **§2.1** ↔ [`the-name.md`](./the-name.md) §1/§2.1/§5.1/§7
      (the Π-anchor / the dial at landscape scale) + [`material-regimes.md`](./material-regimes.md)
      §4 (the deep-rung condensation) + [`chunk-field-quantization.md`](./chunk-field-quantization.md)
      §5 (the site-map bound form); **§2.2** ↔ [`coherence-highway.md`](./coherence-highway.md)
      §1.1/§4.1 (the conduit's course-anchor) + [`the-sea.md`](./the-sea.md) §2a (the
      moving-conduit band); **§2.3** ↔ [`the-threshold.md`](./the-threshold.md) §1/§6 (the
      boundary-hold at scale); **§3** ↔ [`the-observatory.md`](./the-observatory.md) §2 +
      [`the-atlas-of-windows.md`](./the-atlas-of-windows.md) §2 + [`world-seams.md`](./world-seams.md)
      §2.2/§2.3 + [`the-map.md`](./the-map.md) §1/§3 + [`the-language.md`](./the-language.md)
      §2 + [`the-pilgrim.md`](./the-pilgrim.md) §2.1 (the charted / marked / navigable /
      drawn / worded / attended land); **§4.1** ↔ [`the-flood.md`](./the-flood.md) §2 +
      [`the-name.md`](./the-name.md) §6e + [`energy-harnessing.md`](./energy-harnessing.md)
      §2 (the course's honest break / the `(1−q)` shed); **§4.2** ↔ [`the-map.md`](./the-map.md)
      §3.1 + [`chunk-field-quantization.md`](./chunk-field-quantization.md) §5 (the
      boundary re-bind / the redraw-vs-strata); **§4.3** ↔ [`the-fallow.md`](./the-fallow.md)
      §1–§3 + [`material-regimes.md`](./material-regimes.md) §3 + [`field-archaeology.md`](./field-archaeology.md)
      §2 + [`the-name.md`](./the-name.md) §3.3 (the spent named land / the mined-away
      mountain's strata as its record). Reverse pointers added. Two-way each.
      **No-mint check: the landform-name does NOT mint a navigation — the star-read and
      beacon-navigation are landed (world-seams §2.2/§2.3); steering by a named landform's
      read is [design], and the no-free-energy cap holds (the-name §6d, the-map §6d).**
    - [`the-witness.md`] **§2** ↔ [`signature-predator.md`](./signature-predator.md)
      §1.1/§2.2 (does not hunt — the accumulation never begins) + [`the-blight.md`](./the-blight.md)
      §2 (does not turn) + [`the-scavenger.md`](./the-scavenger.md) §2.2 (does not feed) +
      [`the-commensal.md`](./the-commensal.md) §2.2/§3 (does not hold a patch) +
      [`the-mirror-creature.md`](./the-mirror-creature.md) §2 (does not echo); **§2.1** ↔
      [`reason-field.md`](./reason-field.md) §2.1/§2.2/§3.1/§6a (the intent absent / the
      persistent-Π / the frontier) + [`the-feral-instrument.md`](./the-feral-instrument.md)
      §1/§2.2 (the waking's converse) + `CassiTheory/speculations/qi-computation.md` §5.2
      (persistent Π); **§3** ↔ [`the-story.md`](./the-story.md) §2/§3.3 (not a sign — not the
      story's omen) + [`the-reading-ahead.md`](./the-reading-ahead.md) §3 (not a portent);
      **§4.1** ↔ [`the-observatory.md`](./the-observatory.md) §2/§2.1 (the eye that watches
      the watcher); **§4.2** ↔ [`the-silence.md`](./the-silence.md) §2/§3/§6a (the stillness
      given presence); **§4.3** ↔ [`the-feral-instrument.md`](./the-feral-instrument.md) §7
      (the intent-channel held without the waking); **§5e** ↔ [`field-hazards.md`](./field-hazards.md)
      §1/§5.1/§5.3 (the lawful non-row — no threat, no response, no counterplay). Reverse
      pointers added. Two-way each. **Canonical check: the witness is a pure consumer of the
      publish inside the ≈ 1–6 ms/tick sample budget, holds no patch, adds no entity — matches.**
    Ledger extension: wrote the three genuine audit rows (cave/landform-name/witness, each
    after its edges were grep-verified), the canonical-number checks (the cave's Phase-1
    slice and the witness's pure-consumer cost match the sample budget; the landform-name's
    no-mint navigation check), the count note updated, the verdict extended to wave 36.
33. **Wave-37 re-points (pass 22).** The four wave-37 docs — the-lock, the-commons-tithe,
    the-marsh, the-husbander — each reverse pointer inserted into its source doc and
    grep-verified before its audit row was written (39 edges total):
    - [`the-lock.md`] **§2/§3** ↔ [`the-oath.md`](./the-oath.md) §1/§3/open-Q4 (the vow's
      severability answered in the negative) + [`the-treaty.md`](./the-treaty.md)
      §1/§2.4/§4 (a treaty is permanent while held; a lock is permanent full stop);
      **§2.1** ↔ [`the-rite-of-passage.md`](./the-rite-of-passage.md) §2.3/§3.2 (the
      binding lifted to a settlement's chosen structure); **§2.1** ↔ [`the-name.md`](./the-name.md)
      §1/§2/§6e (the holding made irreversible); **§2.3** ↔ [`seed-garden.md`](./seed-garden.md)
      §3/§4.2/§3.3 (the locked seed-line); **§3** ↔ [`the-exile.md`](./the-exile.md)
      §2/§4/§6d (the no-amnesty forward — the durable-mistake cost); **§2** ↔
      [`house-that-steers.md`](./house-that-steers.md) §1.1/§3.2/§3.4/§5b (the held core
      locked); **§4** ↔ [`the-inheritance.md`](./the-inheritance.md) §1/§2/§2.4/§8 (the
      line's survival); **§5d** ↔ [`energy-harnessing.md`](./energy-harnessing.md) §6 (the
      cap taken to permanent). Reverse pointers added. Two-way each.
    - [`the-commons-tithe.md`] **§2** ↔ [`shared-ledger.md`](./shared-ledger.md)
      §1.2/§2/§5/§6d/§6c (the booked commons' share, the per-member C(M)) + §2 ↔
      [`house-that-steers.md`](./house-that-steers.md) §1/§2.2 (the funded bath) +
      [`the-observatory.md`](./the-observatory.md) §1/§2 (the funded room) +
      [`the-harbor.md`](./the-harbor.md) §2b/§2c/§3/§4 (the funded harbor); **§3** ↔
      [`field-npc-ai.md`](./field-npc-ai.md) §3.1/§3.2/§3.3 (the funded commons) + §3 ↔
      [`the-school.md`](./the-school.md) §2.2/§3 (the funded competence); **§2** ↔
      [`the-market.md`](./the-market.md) §2/§2.3 (the regular sibling); **§2.4** ↔
      [`the-census.md`](./the-census.md) §2.1/§2.2 (the active tither) +
      [`the-window-pulse.md`](./the-window-pulse.md) §2/§3 (the healthmeter's funding);
      **§4** ↔ [`the-exile.md`](./the-exile.md) §4 (the declining share); **§5** ↔
      [`the-gift.md`](./the-gift.md) §2.1/§3.1/§6d (the booked warm — the gift's booked
      inverse). Reverse pointers added. Two-way each. **Canonical check: the tithe's
      op-record `{member, op, worldPos, rung, magnitude, sustain}` matches schema-that-settles
      §2.1 verbatim.**
    - [`the-marsh.md`] **§2** ↔ [`the-sea.md`](./the-sea.md) §2b/§2a/§3/§4/§5b (the
      textured cousin) + [`the-swim.md`](./the-swim.md) §2a/§2b/§5b (the shallow swim);
      **§3** ↔ [`signature-predator.md`](./signature-predator.md) §1/§1.2/§2/§3/§7e/§8
      (the trail-read's honest failure) + [`life-signal.md`](./life-signal.md) §3/§2/§6b
      (the hidden read) + [`the-vigil.md`](./the-vigil.md) §3/§5e (the honest cover) +
      [`the-walk.md`](./the-walk.md) §2c/§4b (the absorbed wake); **§5** ↔
      [`field-emergent-ecology.md`](./field-emergent-ecology.md) §2.2/§4.2/§6b (the
      tessellated habitat) + [`the-sea-floor.md`](./the-sea-floor.md) §2a/§2b (the
      shallow-scale edge); **§2** ↔ [`energy-harnessing.md`](./energy-harnessing.md)
      §2/§6 (the low-flow cost / the cap). Reverse pointers added. Two-way each.
      **Canonical check: the marsh's q-patchiness holds the cap (a marsh provides nothing,
      no stealth-yield).**
    - [`the-husbander.md`] **§2a** ↔ [`the-walk.md`](./the-walk.md) §2/§3/§4a/§4c/§4d
      (the patch's health read) + [`the-vigil.md`](./the-vigil.md) §1/§3/§5b (the wild's
      watch) + [`the-working-song.md`](./the-working-song.md) §1/§2.1 (the third practice);
      **§3** ↔ [`farm-that-feeds.md`](./farm-that-feeds.md) §2/§4/§6 (the anti-owner);
      **§4** ↔ [`the-commensal.md`](./the-commensal.md) §2/§3/§5b (the wild's habitat);
      **§2b** ↔ [`the-blight.md`](./the-blight.md) §2/§3/§4.2/§5e (the early clearing) +
      [`the-scar-lifecycle.md`](./the-scar-lifecycle.md) §2.1/§2.2 (the healed scar);
      **§2c** ↔ [`the-cold.md`](./the-cold.md) §2/§3/§6b (the thin-season's shed); **§5d**
      ↔ [`energy-harnessing.md`](./energy-harnessing.md) §2/§6 (the un-booked shed);
      **§2c/§3** ↔ [`the-gift.md`](./the-gift.md) §1/§2/§6d (the shed as a gift). Reverse
      pointers added. Two-way each. **Canonical check: the husbander's shed holds the cap
      (the `(1−q)` waste is spent, never a harvest, never a mint).**
    Ledger extension: wrote the four genuine audit rows (lock/tithe/marsh/husbander, each
    after its edges were grep-verified), the canonical-number checks (the tithe's op-record
    matches schema §2.1 verbatim; the marsh's q-patchiness and the husbander's shed hold
    the cap), the count note updated, the verdict extended to wave 37.
34. **Wave-38 re-points (pass 23).** The three wave-38 docs — the-guardian, the-archive,
    the-granary — each reverse pointer inserted into its source doc and grep-verified
    before its audit row was written (35 edges total):
    - [`the-guardian.md`] **§2.1** ↔ [`the-landform-name.md`](./the-landform-name.md)
      §2/§4/§5a (the named place made bound) + [`the-name.md`](./the-name.md) §1/§2/§6d/§7
      (the holding made a keeper) + [`the-threshold.md`](./the-threshold.md) §1/§2.2/§6c/§6d
      (the boundary's keeper) + [`the-cave.md`](./the-cave.md) §4/§5d (the shelter's keeper);
      **§3** ↔ [`the-commensal.md`](./the-commensal.md) §2/§3/§5c/d/e (the territorial
      order-side — the assist turned to defense, net-negative); **§3.1** ↔
      [`the-blight.md`](./the-blight.md) §2/§6e (the wrong-band's warden); **§3.2** ↔
      [`signature-predator.md`](./signature-predator.md) §1/§2/§4.4/§7e (the hunter's
      refuser); **§4** ↔ [`the-witness.md`](./the-witness.md) §1/§2/§7 (the warden-twin);
      **§2.3** ↔ [`life-signal.md`](./life-signal.md) §3/§3.1/§6a/b/§6d (the live-and-bound
      read); **§4** ↔ [`the-mirror-creature.md`](./the-mirror-creature.md) §2/§5c/d/e (the
      distinct face); **§2.2** ↔ [`field-emergent-ecology.md`](./field-emergent-ecology.md)
      §2.2/§4.2/§6b/§5.3 (the bound morphology). Reverse pointers added. Two-way each.
      **Canonical check: the guardian's binding holds the cap (converts nothing, never a
      mint).**
    - [`the-archive.md`] **§2** ↔ [`shared-ledger.md`](./shared-ledger.md)
      §1.2/§1.3/§6c/§6d (the full history held raw) + [`schema-that-settles.md`](./schema-that-settles.md)
      §2/§2.1/§2.2/§5 (the record held raw) + [`the-stratum-read.md`](./the-stratum-read.md)
      §1/§2/§2.4/§3/§5e (the strata held raw) + [`the-chronicle.md`](./the-chronicle.md)
      §1/§3.3/§5/§6d/§6e (the raw of the shaped) + [`the-memory-palace.md`](./the-memory-palace.md)
      §2/§4/§6d/§7 (the raw of the chosen) + [`the-name.md`](./the-name.md) §1/§3.3/§6d/§7/§4
      (the named lives' full record) + [`field-archaeology.md`](./field-archaeology.md)
      §2/§1.2/§6b/§5.3 (the complete shadow's source) + [`the-language.md`](./the-language.md)
      §2/§5 (what the script can carry); **§6** ↔ [`energy-harnessing.md`](./energy-harnessing.md)
      §2/§4.1/§4.4/§6 (the held store); **§2** ↔ [`the-census.md`](./the-census.md) §2 (the
      population history); **§2.1** ↔ [`the-dispute.md`](./the-dispute.md) §2.1/§6d (the raw
      ground). Reverse pointers added. Two-way each. **Canonical check: the archive's raw
      record rides the settled op-record `{member, op, worldPos, rung, magnitude, sustain}`
      (schema §2.1 verbatim); the Archive is a store, never a mint.**
    - [`the-granary.md`] **§4** ↔ [`farm-that-feeds.md`](./farm-that-feeds.md) §2/§4/§5/§6/§7
      (the yield held) + [`the-market.md`](./the-market.md) §1/§2.1/§2.2/§6d (the store of
      the circulated) + [`the-memory-palace.md`](./the-memory-palace.md) §2/§3/§4/§6d (the
      matter-side twin); **§2** ↔ [`the-tool.md`](./the-tool.md) §2/§3/§4d (the kept steel's
      store) + [`the-cold.md`](./the-cold.md) §2/§3/§6e (the thin-season's buffer) +
      [`house-that-steers.md`](./house-that-steers.md) §1/§2.2/§5d/§5b (the room's hold) +
      [`the-census.md`](./the-census.md) §2.1/§6e (the liveness's store) +
      [`the-window-pulse.md`](./the-window-pulse.md) §2/§6e (the pulse's material half);
      **§3** ↔ [`seed-garden.md`](./seed-garden.md) §3/§2.1/§7 (the plenty-side twin);
      **§2a** ↔ [`the-fallow.md`](./the-fallow.md) §2a/§5d (the spent-draw bound); **§6** ↔
      [`energy-harnessing.md`](./energy-harnessing.md) §2/§4.4/§6 (the held store's bleed);
      **§2.1** ↔ [`schema-that-settles.md`](./schema-that-settles.md) §2.1/§2.2/§3 (the book
      of plenty); **§1.2** ↔ [`shared-ledger.md`](./shared-ledger.md) §1.2 (the store's
      legibility). Reverse pointers added. Two-way each. **Canonical check: the granary's
      deposits/draws book on the settled record; the store's bleed holds the cap (a granary
      converts nothing).**
    Ledger extension: wrote the three genuine audit rows (guardian/archive/granary, each
    after its edges were grep-verified), the canonical-number checks (the archive's op-record
    matches schema §2.1 verbatim; the granary's bleed and the guardian's keeping hold the
    cap), the count note updated, the verdict extended to wave 38.
35. **Wave-39 re-points (pass 24).** The four wave-39 docs — the-wind, the-season-change,
    the-cart, the-breath — each reverse pointer inserted into its source doc and
    grep-verified before its audit row was written (40 edges total):
    - [`the-wind.md`] **§2/§3** ↔ [`field-hazards.md`](./field-hazards.md) §2/§5.1/§5.3
      (the flow-face of the storm) + §2 ↔ [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
      §1.3/§1.5/§2.2/§6/§2.4 (the air moving — `FieldVel`, the turbine, the altitude wind);
      **§6** ↔ [`the-zenith.md`](./the-zenith.md) §1/§2 (the ceiling's flow); **§2** ↔
      [`weather-not-storm.md`](./weather-not-storm.md) §2/§3/§6 (the provenance sibling) +
      [`coherence-highway.md`](./coherence-highway.md) §1/§1.1/§6b/§6d (the tailwind) +
      [`the-walk.md`](./the-walk.md) §2/§2a/§4b/§4d (the stride's re-price) + [`the-blight.md`](./the-blight.md)
      §2/§3/§6e (the spore-carrier) + [`the-marsh.md`](./the-marsh.md) §2/§3 (the air's
      marsh) + [`signature-predator.md`](./signature-predator.md) §1.2 (the signature-
      carrier); **§2/§6** ↔ [`energy-harnessing.md`](./energy-harnessing.md) §2/§2.2/§1.7/§6
      (the un-farmable flow). Reverse pointers added. Two-way each. **Canonical check: the
      wind's carry holds the cap (a wind provides nothing, never farmable).**
    - [`the-season-change.md`] **§2** ↔ [`tide-of-the-attractor.md`](./tide-of-the-attractor.md)
      §2/§5a/§1.2/§5d (the crossing — the harvest/thin states) + [`patient-field.md`](./patient-field.md)
      §3.3/§5b (the least-legible crossing) + [`atmosphere-orbits-auroras.md`](./atmosphere-orbits-auroras.md)
      §2/§4/§3.3/§3.4 (the long-cycle turn); **§3** ↔ [`the-window-year.md`](./the-window-year.md)
      §2/§3/§5a/§5b (the actual shift the calendar approximates) + §3/§4 ↔
      [`the-drift-road.md`](./the-drift-road.md) §3.3/§3.4/§4d (the one-way turn); **§1** ↔
      [`the-dawn.md`](./the-dawn.md) §1/§2/§5 (the seasonal sibling); **§3.2** ↔
      [`farm-that-feeds.md`](./farm-that-feeds.md) §5/§2.2 (the harvest before the band
      dies) + [`house-that-steers.md`](./house-that-steers.md) §2.2/§3.4/§5d (the bath
      before it thins); **§2/§3** ↔ [`the-cold.md`](./the-cold.md) §2/§3/§5.3 (the turn into
      the thin); **§4.2/§5d** ↔ [`energy-harnessing.md`](./energy-harnessing.md) §2/§6 (the
      un-gained crossing); **§3.1** ↔ [`the-window-pulse.md`](./the-window-pulse.md)
      §2.1/§6e (the muddy-instrument read). Reverse pointers added. Two-way each.
    - [`the-cart.md`] **§1** ↔ [`coherence-highway.md`](./coherence-highway.md) §1/§1.2/§4/§6b/§6c/§6d
      (the route's rider) + [`energy-harnessing.md`](./energy-harnessing.md) §1.1/§4.1/§2/§6
      (the free haul, the paid wear); **§2** ↔ [`the-walk.md`](./the-walk.md) §2/§2a/§3/§4a/§4c
      (the wheeled burden) + [`the-market.md`](./the-market.md) §1/§2/§2.2/§6d (the freight
      the market takes) + [`the-tool.md`](./the-tool.md) §2b/§3/§4b (the shared wear) +
      [`the-burden.md`](./the-burden.md) §1/§2/§4 (the wheeled load) + [`house-that-steers.md`](./house-that-steers.md)
      §1/§2.2/§5d (the structure on the move); **§3** ↔ [`the-granary.md`](./the-granary.md)
      §2.1/§3/§4/§5d (the store carried); **§2.1** ↔ [`schema-that-settles.md`](./schema-that-settles.md)
      §2.1/§2.2/§2.3/§3 (the load booked). Reverse pointers added. Two-way each.
      **Canonical check: the cart's load books on the settled op-record
      `{member, op, worldPos, rung, magnitude, sustain}` (schema §2.1 verbatim).** **Honest
      negative (open-Q6): `the-camp.md` is absent on disk — the cart's camp-freight face is
      flagged `[assumption]` and NOT filled in; no forced citation to a non-existent doc.**
    - [`the-breath.md`] **§1** ↔ [`deep-field-diving.md`](./deep-field-diving.md)
      §1/§2/§2.2/§2.3/§3.1/§4/§7a/§7d (the priced descent — the same budget that bounds the
      Bell); **§3** ↔ [`the-cave.md`](./the-cave.md) §3/§4/§5d (the hollow's breath);
      **§2c** ↔ [`the-sea-floor.md`](./the-sea-floor.md) §2a/§2c/§5d (the shallow descent);
      **§2a** ↔ [`the-swim.md`](./the-swim.md) §2a/§2b/§5d (the stroke's breath); **§2** ↔
      [`the-burden.md`](./the-burden.md) §1/§2b/§4/§6a (the body-scale cost) +
      [`the-tool.md`](./the-tool.md) §2a/§2c/§4d (the bite at depth) + [`life-signal.md`](./life-signal.md)
      §1/§3/§3.2/§6b/§6d (the maintained level); **§2/§4** ↔ [`player-remains.md`](./player-remains.md)
      §1/§1.2/§2.3/§5e (the lock's failure); **§2/§6** ↔ [`energy-harnessing.md`](./energy-harnessing.md)
      §2/§6 (the body's bleed); **§2a** ↔ [`sleep.md`](./sleep.md) §2b/§3/§6d (the refill).
      Reverse pointers added. Two-way each. **Canonical check: the breath holds the cap (a
      breath converts nothing; the reservoir is a store, never a mint).**
    Ledger extension: wrote the four genuine audit rows (wind/season-change/cart/breath,
    each after its edges were grep-verified), the canonical-number checks (the cart's load
    books on the settled op-record verbatim; the wind/season/breath caps held; the cart's
    the-camp open-Q6 honest negative recorded, not forced), the count note updated, the
    verdict extended to wave 39.



36. **Wave-40 re-points (pass 25).** The three wave-40 docs — the-herald, the-toll,
    the-compost — all landed two-way against their pass-spec sources. **the-herald**
    (12 sources): `the-witness.md` (§1/§2/§5b/§7#2/#4, the loud twin), `the-reading-ahead.md`
    (§1/§2.2/§2.3/§7c/§7d/§7a, the forward read), `the-bell.md` (§3/§5a/§6c/d/e, the
    crafted cousin), `the-guardian.md` (§1/§3/§5b, the teller to the keeper),
    `weather-not-storm.md` (§2/§3, the announced provenance), `the-season-change.md`
    (§1/§2.1/§3.1/§5b, the announced crossing), `fate-of-a-window.md` (§1/§6c/§6e, the
    announced fork), `field-emergent-ecology.md` (§2.2/§4.2/§6b/§5.3/§1.4, the recognized
    run), `life-signal.md` (§3/§3.1/§6d, the live read), `signature-predator.md`
    (§2/§3/§7e, the non-accumulator), `the-mirror-creature.md` (§2/§5c/d/e, the announced
    news), `the-feral-instrument.md` (§1, the never-woken). **the-toll** (12 sources):
    `the-commons-tithe.md` (§1/§3/§2.1/§5a, the external twin), `the-harbor.md`
    (§2b/§2c/§3/§4/§5a, the first door), `the-threshold.md` (§1/§2.2/§3, the second door),
    `the-treaty.md` (§1/§2/§2.3/§2.2/§5d, the third door), `window-guests.md` (§1/§2/§3/§6b,
    the travellers), `shared-ledger.md` (§1.2/§2/§6d/§6c, the book), `the-market.md`
    (§1/§2/§2.3/§3/§6d, the border-twin), `coherence-highway.md` (§1/§4/§5.2/§6d, the
    road's upkeep), `house-that-steers.md` (§1/§2.2/§3/§5d, the held border),
    `schema-that-settles.md` (§2.1/§2.3/§3, the atomic book), `the-dispute.md`
    (§2/§3.1/§3.2, the field-true charge), `the-census.md` (§2.1/§2.4/§6d, the
    population's door). **the-compost** (11 sources): `the-fallow.md` (§2/§2b/§1/§5d, the
    spent state's return), `the-tool.md` (§2b/§3/§4b/§4d, the worn steel's sink),
    `the-granary.md` (§2.1/§6/§5d, the store's bleed's sink), `farm-that-feeds.md`
    (§2/§4/§5, the plot's feed), `the-scavenger.md` (§2.1/§2.2/§5d, the built twin),
    `patient-field.md` (§3.3/§1/§5, the impatience it turns), `material-regimes.md`
    (§3/§4, the re-precipitation), `energy-harnessing.md` (§2/§6, the waste and the cap),
    `the-marsh.md` (§3/§2, the second plot's re-turn), `the-husbander.md` (§1/§3/§6, the
    built sibling), `schema-that-settles.md` (§2.1/§2.3/§6d, the heap's book).
      Reverse pointers added (35 edges total: herald 12, toll 12, compost 11). Two-way
      each. **Canonical check: the toll's doors/trust-by-law cite `window-guests.md` §3/§6b
      (the visitor's provenance the toll must never misread as a resident's drain) +
      `schema-that-settles.md` §2.1 (the op-record `{member, op, worldPos, rung,
      magnitude, sustain}` verbatim — the toll's own shape) — verified; the toll holds the
      cap (a toll never mints, never farms). the compost's heap/time-and-lock holds the
      cap — `output ≤ φ⁻¹·input` (no-free-energy, §6 `energy-harnessing.md`), the compost
      returns order at a loss, never a mint — verified. the herald provides nothing, never
      farms — a pure consumer of the publish on the reason-field cost profile (the
      witness's loud twin); holds no patch, adds no entity to the ≈2,000 cap.**
    Ledger extension: wrote the three genuine audit rows (herald/toll/compost, each after
    its edges were grep-verified), the canonical-number checks, the count note updated
    (144/144 lock-step), the verdict extended to wave 40.


37. **Wave-41 re-points (pass 26).** The four wave-41 docs — the-carry, the-climb,
    the-gatekeeper, the-causeway — all landed two-way against their pass-spec sources.
    **the-carry** (11 sources): `the-burden.md` (§1/§2/§2b/§4, the matter-twin),
    `the-walk.md` (§2/§2a/§2b/§3/§4a/§4c, the stride-cost's load), `the-swim.md`
    (§2a/§4/§5c/d/e, the stroke's load), `the-cart.md` (§1/§2/§3/§5a/§7, the
    body-scale twin), `the-tool.md` (§2a/§3/§4d, the single held arrangement),
    `the-lantern.md` (§1/§2/§1.4, the carried night-read), `life-signal.md`
    (§3/§3.3/§6 N2, the maintenance axis's load), `signature-predator.md`
    (§2/§8/§7e, the loaded trail), `the-granary.md` (§2/§6/§7, the store at
    body-scale), `schema-that-settles.md` (§2.1/§2.2/§2.3, the pack's book),
    `energy-harnessing.md` (§2/§6, the cap). **the-climb** (10 sources): `the-fall.md`
    (§1/§2/§4.2/§5a/§5c/§5d, the controlled-inverse), `the-walk.md` (§2/§2a/§3/§4a/§4d,
    the vertical-twin), `the-zenith.md` (§1/§2b/§4b, the place), `material-regimes.md`
    (§4, the readable handholds), `energy-harnessing.md` (§1.1/§2/§6, the gradient and
    the waste), `the-burden.md` (§1/§2/§6a, the carried cost at height),
    `coherence-highway.md` (§4, the unmaintained-route contrast), `player-remains.md`
    (§1/§4, the fall's death), `field-hazards.md` (§4/§5.1, the honest dangers at
    height), `life-signal.md` (§3, the held lock at height). **the-gatekeeper** (11
    sources): `the-threshold.md` (§1/§2.2/§3/§6, the judge at the door), `the-harbor.md`
    (§2b/§2c/§3/§4/§5b, the door-side twin), `the-guardian.md` (§1/§2.3/§3/§5d/e/§7,
    the creature-twin), `window-guests.md` (§1/§2/§3/§4.1/§6b, the admitted-guests'
    judge), `life-signal.md` (§3/§3.3/§4/§6a/§6d, the judge's read),
    `signature-predator.md` (§2/§3/§7d/§8/§7e, the deliberate-vent read at the door),
    `the-blight.md` (§2/§6e/§5e/§7, the refused arrival), `the-census.md` (§2/§2.1/§2.4/§7,
    the roster's door), `shared-ledger.md` (§1.2/§6c/§6d/§6e, the member-line),
    `the-dispute.md` (§2/§4/§6c/d/e, the field-true refusal), `the-observatory.md`
    (§1/§2/§3/§6e, the door's observatory). **the-causeway** (9 sources): `the-marsh.md`
    (§2/§3/§4/§6c/§7/§8, the hiding water crossed), `the-walk.md` (§2/§2a/§2c/§3/§4c/d/e,
    the clean transit's deck), `the-cart.md` (§2/§3/§4/§7, the deck the road's vehicle
    rides), `house-that-steers.md` (§1/§1.1/§2/§3/§3.4/§5d, the deck's held form),
    `energy-harnessing.md` (§2/§4.1/§4.4/§6, the deck's cost and cap), `the-threshold.md`
    (§1/§2.2/§4/§5d/§6b, the crossing's boundary-marks), `life-signal.md` (§3/§6d, the
    clean crossing's read), `signature-predator.md` (§1/§1.2/§2/§7e/§8, the clean line's
    honest trade), `coherence-highway.md` (§4/§4.2/§6b/§6d, the marsh's highway
    segment).
      Reverse pointers added (41 edges total: carry 11, climb 10, gatekeeper 11,
      causeway 9). Two-way each. **The climb↔carry two-way write-race is landed: both
      docs had honestly flagged the other's absence (the-climb's cross-refs read
      `the-carry.md — NOT ON DISK`, grounded in the-burden alone; the-carry's §3a/§3b/§7
      open-Q2 flagged the climb's absence). Now that both are on disk (wave 41), the
      climb's cross-ref `NOT ON DISK` line is rewritten as a real `the-carry.md`
      pointer, and the-carry's three absence-notes are rewritten as landed-arrival
      two-way reads.** **Canonical check: the pack holds the cap (a carry converts
      nothing, no pack that yields; the heavier live-lock is a cost, never a gain);
      a climb converts nothing harder at the vertical (`output ≤ φ⁻¹·input`); the
      office holds the cap (a gatekeeper never mints, never farms); a causeway converts
      nothing (`output ≤ φ⁻¹·input`, the deck's standing draw held) — all verified.**
    Ledger extension: wrote the four genuine audit rows (carry/climb/gatekeeper/
    causeway, each after its edges were grep-verified), the canonical-number checks,
    the count note updated (147/152, five unindexed wave-46+ arrivals), the verdict
    extended to wave 41.


38. **Wave-42 re-points (pass 27).** The three wave-42 docs — the-rain, the-spring,
    the-mimic — all landed two-way against their pass-spec sources. **the-rain**
    (10 sources): `the-flood.md` (§2/§3/§4.1/§6(b)/§6(e), the gentle twin),
    `farm-that-feeds.md` (§2/§5/§3/§4, the season's water), `the-wind.md`
    (§1/§3/§5(b)/§5(c)/§5(d)/§5(e), the flow's carry), `the-marsh.md` (§3/§8, the blur
    on a smaller scale), `life-signal.md` (§1/§3/§3.2/§6b, the rainy walk's read),
    `the-fallow.md` (§1/§3, the season's return), `weather-not-storm.md` (§2, the
    clearest weather verdict), `the-sea.md` (§2c/§4/§5b, the water cycle),
    `energy-harnessing.md` (§2/§6, the wet cost and the cap), `field-hazards.md`
    (§5.1, the readable-before-it-arrives case). **the-spring** (12 sources):
    `the-fallow.md` (§1/§2/§2a/§5b/§6d, the full twin), `resonance-seeds.md`
    (§1/§2/§6a, the ambient contrast), `seed-garden.md` (§2/§3/§4.2, the live well
    counter), `field-emergent-ecology.md` (§2.2/§4.2/§1.4, the stationary counter),
    `the-granary.md` (§2/§3/§5d/§7, the drawn-and-stored), `the-carry.md`
    (§2/§4b/§5c/d/e, the drawn pack), `the-landform-name.md` (§1/§2/§5d/§5e, the
    named source), `the-guardian.md` (§1/§3/§5d/§7, the territorial read),
    `life-signal.md` (§3/§6c/§6d, the maintained-live source),
    `signature-predator.md` (§2/§7e, the fixed landmark), `energy-harnessing.md`
    (§2/§1.7/§6/§7 Q1, the well's cap), `material-regimes.md` (§3/§4, the fixed
    re-precipitation). **the-mimic** (12 sources): `the-mirror-creature.md`
    (§1/§2/§2.2/§3.2/§4.1/§5b-2/§7, the worn-shape twin), `signature-predator.md`
    (§1/§2/§2.2/§3/§7e/§8, the seduction-vs-ambush line), `window-guests.md`
    (§1/§2/§3/§6b, the borrowed provenance), `life-signal.md` (§1/§3/§3.1/§3.2/§6b,
    the legacy tell), `shared-ledger.md` (§1.2/§6c/§3.3/§6e/§6b, the provenance read
    that catches it), `the-gatekeeper.md` (§1/§2/§2.1/§5c/d/e, the reason the office
    exists), `the-commensal.md` (§1/§4/§5c/d/e, the order-side contrast),
    `field-emergent-ecology.md` (§2.2/§6b/§3.1/§4.1/§1.4, the borrowed morphology),
    `the-feral-instrument.md` (§1/§5d/e, the borrowed woken being), `the-dispute.md`
    (§2/§2.1, the lie it sheds), `the-witness.md` (§1/§2/§5c/d/e, the inverting
    twin), `energy-harnessing.md` (§2/§6, the borrow's cost).
      Reverse pointers added (34 edges total: rain 10, spring 12, mimic 12). Two-way
      each. **The rain↔spring two-way write-race is landed: both docs had honestly
      flagged the other's absence (the-rain's §7 open-Q1 'the-spring.md does not exist
      on disk'; the-spring's cross-ref 'NOT exist on disk' + body + two open-question
      notes). Now that both are on disk (wave 42), each reads the other two-way — the
      rain's fill-of-spring note is rewritten as landed arrival, and the-spring's four
      absence-notes (cross-ref, calibration body, open-Q1, Absent footer) are all
      rewritten as landed-arrival pointers.** **Canonical check: the rain gives back at
      the field's own yield, never a mint (`output ≤ φ⁻¹·input`), its flood-beginning
      readable never a farm; a spring provides nothing beyond its own welling (never a
      mint), the point of fame a cost never a farm; a mimic converts nothing (the
      borrowed shape spent never a gain) — all verified.**
    Ledger extension: wrote the three genuine audit rows (rain/spring/mimic, each
    after its edges were grep-verified), the canonical-number checks, the count note
    updated (151/152, one unindexed wave-46+ arrival, corpus-map), the verdict
    extended to wave 42.


39. **Wave-43 re-points (pass 28).** The four wave-43 docs — the-stilling, the-roost,
    the-dive, the-between — all landed two-way against their pass-spec sources.
    **the-stilling** (9 sources): `the-vigil.md` (§1/§3/§5b/§5a/§5d, the inner
    sibling), `the-working-song.md` (§1, the motionless twin), `the-stillness.md`
    (§1/§2/§4.3/§6b/§6c, the drifter's edge), `life-signal.md` (§1/§3/§3.2/§6a/b/§6c/§6d,
    the hold turned inward), `energy-harnessing.md` (§2/§6, the voluntary hold's cost),
    `signature-predator.md` (§2/§7e/§8, the quieter read), `the-silence.md` (§1/§2, the
    cousin turned inward), `the-fall.md` (§2, the body's own hold), `sleep.md`
    (§1/§2b/§2.1, the shallow cousin). **the-roost** (11 sources): `field-emergent-
    ecology.md` (§4.2/§2.2/§6b/§1.4/§3.1/§5.3, the nested run), `signature-predator.md`
    (§1/§2/§7c/§2.3/§7e, the predator's home), `the-scavenger.md` (§2.2/§2.1/§4/§5b/§5c/d/e,
    the den), `the-commensal.md` (§2/§3/§2.2/§7, the hollow), `the-guardian.md`
    (§1/§3/§4/§5e, the keep's home), `the-feral-instrument.md` (§2.2/§5d/§5e/§7, the
    feral's found home), `the-mirror-creature.md` (§2.3/§5, the mirror's margin),
    `field-archaeology.md` (§2/§3.2/§7/§1.2, the residue model's den), `life-signal.md`
    (§3/§3.1/§6d, the held place's read), `energy-harnessing.md` (§2/§6, the cap),
    `field-hazards.md` (§5.1/§1/§5.3, the legible home). **the-dive** (11 sources):
    `deep-field-diving.md` (§2.1/§2.2/§2.3/§3.1/§7a/§7d, the un-protected mirror),
    `the-fall.md` (§1/§2/§4.3/§5c/§5d, the desired descent), `the-climb.md`
    (§1/§2/§2.1/§3/§4.2/§5a, the logic inverted), `the-breath.md` (§1/§2/§3/§4.1/§5b/§5d,
    the reserve's descent), `the-swim.md` (§2a/§2b/§4/§5d, the medium turned down),
    `the-cave.md` (§3/§4/§5d, the hollow entered), `the-burden.md` (§1/§2/§6a, the carried
    descent), `player-remains.md` (§1/§4/§2.3/§2.4, the honest risk),
    `energy-harnessing.md` (§1.1/§2/§4.4/§6, the descent-tax and the cap),
    `the-sea-floor.md` (§1/§2c, the shallow form), `the-stratum-read.md` (§2, the
    descent's survey). **the-between** (13 sources): `the-interstitial.md`
    (§1/§2/§3/§4/§5, the un-windowed face), `world-seams.md` (§1.2/§2.1/§2.2/§2.3/§4.3/§6/§7,
    the empty measure), `the-harbor.md` (§1/§2/§3/§4/§5b, the door's outside),
    `the-atlas-of-windows.md` (§1/§2/§4b/§4d, the record's partialism), `window-guests.md`
    (§1/§2/§3/§6b, the people), `the-treaty.md` (§1/§2/§4/§6d, the compact's other party),
    `the-witness.md` (§1/§2/§5b, the neutral eye), `the-herald.md` (§1/§2/§5, the far
    news), `pocket-cosmos.md` (§1.2/§1.3/§4.1, the pocket's outside), `async-field-domain.md`
    (§1–2/§7 Q1, the un-windowed medium), `energy-harnessing.md` (§2/§6, the glow and the
    cap), `deep-field-diving.md` (§1/§6, the dark's distinct depths), `the-pilgrim.md`
    (§2/§3/§5d, the walker of the dark).
      Reverse pointers added (44 edges total: stilling 9, roost 11, dive 11, between
      13). Two-way each. **Canonical check: a stilling converts nothing (`output ≤
      φ⁻¹·input`; the voluntary hold spent, never free — a practiced stilling is not a
      stealth mechanic); a roost provides nothing (a nest provides nothing, the
      presented reading never a spawned den); a dive converts nothing, never a mint
      (the honest risk is the lock's failure at depth); the between provides nothing,
      the dark is never a gain (its laws cite `the-interstitial.md` §2 verbatim; the
      cartography honestly partial, never a map) — all verified.** Placements: the
      witness and async-field-domain (no `## Cross-references` sections) appended at
      EOF; field-archaeology, deep-field-diving, field-emergent-ecology,
      energy-harnessing appended at cross-refs end (no detected corpus footer).
    Ledger extension: wrote the four genuine audit rows (stilling/roost/dive/between,
    each after its edges were grep-verified), the canonical-number checks, the count
    note updated (151/154, three unindexed wave-47+ arrivals), the verdict extended
    to wave 43.


40. **Wave-44 re-points (pass 29).** The three wave-44 docs — the-beacon, the-shout,
    the-moth — all landed two-way against their pass-spec sources. **the-beacon**
    (12 sources): `the-lantern.md` (§1/§2/§4/§5b/§5d/§5e, the fixed twin), `the-bell.md`
    (§1/§3, the constant-mark contrast), `the-observatory.md` (§1/§2/§2.1, the inverted
    read), `the-harbor.md` (§2b/§3/§6/§5d, the first edge's mark), `the-threshold.md`
    (§1/§6/§5d/§5e, the second edge's mark), `the-causeway.md` (§1/§3/§8, the third
    edge's mark), `house-that-steers.md` (§1/§1.1/§3/§5b/§5d, the standing hold),
    `energy-harnessing.md` (§2/§4.4/§5.4/§6, the mark's draw and cap),
    `signature-predator.md` (§2/§7e/§8, the bright place's gather), `the-walk.md`
    (§1/§2/§4d, the crossing's finding-light), `world-seams.md` (§2.2, the near-light
    cousin), `the-spring.md` (§3/§5d, the drawn mark). **the-shout** (12 sources):
    `the-working-song.md` (§1/§2, the single-impulse sibling), `field-music.md` (§1/§6,
    the blunt-twin), `the-bell.md` (§1/§5a/§6c/d/e/open-Q5, the body's alarm),
    `life-signal.md` (§3/§3.3/§6a/b/§6c/d, the loud register), `signature-predator.md`
    (§2/§7e/§8, the warn), `the-herald.md` (§1/§2/§5, the body's answer),
    `player-remains.md` (§1/§4/§5e/§6, the found-body's act), `the-stilling.md`
    (§1/§4/§5a/b/§5c/d/e, the loud-twin), `the-vigil.md` (§3/§5b, the watch's own alarm),
    `energy-harnessing.md` (§2/§6, the projection's cost), `the-silence.md` (§1/§3.2,
    the loud-inverse), `the-census.md` (§2/§6d, the roster's loud call). **the-moth**
    (13 sources): `the-lantern.md` (§1/§2/§5d, the coveted glow), `the-beacon.md`
    (§2/§3/§5b/§6 + open-Q5, the standing burn's *called*), `the-spring.md`
    (§2.1/§3/§5/§6/§5d, the sought bright point), `the-observatory.md` (§1/§2/§6d, the
    lit window's draw), `window-guests.md` (§1/§2, the drawn-in wild twin),
    `signature-predator.md` (§1/§2.2/§3/§7e/§8, the opposite hunt), `the-scavenger.md`
    (§2.2/§4/§5c/d/e, the light-counter), `the-commensal.md` (§2/§3/§5c/d/e, the pulled
    inverse), `life-signal.md` (§1/§3/§3.1/§6a/§6b/§6c, the bright-line approach),
    `field-emergent-ecology.md` (§2.2/§6b/§4.2/§1.4, the coveting run),
    `energy-harnessing.md` (§2/§6/§5.4, the coveting and the cap), `the-mirror-creature.md`
    (§1/§2, the told-apart face), `the-witness.md` (§1/§2, the drawn-different).
      Reverse pointers added (37 edges total: beacon 12, shout 12, moth 13). Two-way
      each. **The beacon↔moth two-way special item is LANDED: the-beacon's open-Q5 (who
      is the light-drawn being) is answered by the-moth — the coveter that resolves the
      standing burn's *called*. The Moth's cross-refs carry the resolving reverse pointer
      verbatim ("the Beacon is the standing mark whose *called* the Moth resolves into
      the coveter"); the beacon's two absence-notes (open-Q5 + Absent footer) are
      rewritten as landed arrival, and a closing `the-moth.md` bullet is in the beacon's
      own cross-references. The Moth's open-Q1 defers to the director's pointer decision,
      now resolved in-doc.** **Canonical check: a beacon converts nothing, no mark that
      yields (`output ≤ φ⁻¹·input`; "to be findable is to be found" the honest
      double-edge, never a farm); a shout never mints (the projection is the body's own
      signature spent at its broadcast; a shout that "pulled" help mechanically would be a
      false call the field sheds); a moth converts nothing (`output ≤ φ⁻¹·input` +
      `E_waste=(1−q)·E_throughput`, the coveting spent never a mint) — all verified.**
    Ledger extension: wrote the three genuine audit rows (beacon/shout/moth, each after
    its edges were grep-verified), the canonical-number checks, the count note updated
    (154/155, one unindexed wave-47+ arrival, corpus-map), the verdict extended to wave
    44.


41. **Wave-45 re-points (pass 30).** The four wave-45 docs — the-quarry, the-shepherd,
    the-archivist, the-desert — all landed two-way against their pass-spec sources.
    **the-quarry** (12 sources): `the-fallow.md` (§1/§2a/§3/§5(b)/§5d, the one-way
    run-out's place), `the-tool.md` (§2a/§2b/§3/§4b/§4d, the bite and the scar),
    `the-stratum-read.md` (§1/§2/§3/§5(b)/§5(d), the read before the cut),
    `the-scar-lifecycle.md` (§2.1/§2.2/§2.3/§5b/§5d, the deliberate branch), `the-bedrock.md`
    (§1/§2/§2b/§3/§5d/§6, the floor the cut stops at), `the-cave.md` (§2a/§2b/§4/§5d, the
    cut-form hollow), `material-regimes.md` (§2/§4/§3/§7, the exposed rung-layers),
    `the-compost.md` (§1/§4/§2, the giving-back partner), `energy-harnessing.md`
    (§2/§2.5/§3/§6, the deep-rung take), `schema-that-settles.md` (§2.1/§2.3/§3, the take's
    book), `field-archaeology.md` (§1.2/§2/§2.3/§3.2/§5.3, the residue's source),
    `the-granary.md` (§2/§5d/§6, the taken order's destination). **the-shepherd** (11
    sources): `the-roost.md` (§1/§3/§4/§5c/d/e, the place-vs-being line), `the-scavenger.md`
    (§2.2/§1/§4/§5b/§5c/d/e, the gathering's origin), `the-moth.md` (§3.2/§1/§5b-1/§5d,
    the gathering's magnet), `the-commensal.md` (§2/§3/§5c/d/e, the settle-beside
    contrast), `the-guardian.md` (§1/§3/§5c/d/e, the bound-keep contrast),
    `field-emergent-ecology.md` (§2.2/§6b/§4.2/§5.3/§6c/§1.4, the morphology and the flock),
    `life-signal.md` (§3/§3.1/§6a/b/§6d, the maintained-live assemblage),
    `field-archaeology.md` (§2/§3.2/§7/§1.2, the assemblage's trail), `energy-harnessing.md`
    (§2/§6, the waste and the cap), `the-witness.md` (§1/§5c/d/e, the gatherer-opposite),
    `the-herald.md` (§1/§2/§5, the gathering's voice). **the-archivist** (12 sources):
    `the-archive.md` (§1/§3/§4/§2.4/§5/§6, the raw's keeper), `the-chronicle.md`
    (§1/§3.3/§5/§6d, the shaping office's first contrast), `the-memory-palace.md`
    (§2/§3/§4/§6d, the choosing office's second contrast), `the-gatekeeper.md` (§1/§2/§4/§6,
    the door's office sibling), `the-school.md` (§2/§2.2/§4/§6, the teaching office's third
    contrast), `shared-ledger.md` (§1.2/§6c/§6d/§6b/§6e, the member-line's full record),
    `schema-that-settles.md` (§2/§2.1/§3/§6b, the raw's atomic unit), `the-stratum-read.md`
    (§1/§2/§2.4/§6/§5e, the field's own state), `the-census.md` (§2/§2.1/§7, the roster the
    office reads on), `the-dispute.md` (§2/§6c/§6d/§6e, the dispute's raw ground),
    `field-archaeology.md` (§2/§1.2/§6b, the field's own kept record), `the-name.md`
    (§1/§3.3/§6e/§6d, the named lives held). **the-desert** (13 sources): `field-hazards.md`
    (§3/§6.2, the hazard-twin), `signature-predator.md` (§1.2/§7c/§2, the Coda's home
    terrain), `the-between.md` (§1/§3/§2a, the NOT-between), `the-scavenger.md`
    (§2.1/§2.2/§4, the natural margin), `the-roost.md` (§2/§3/§4, the thin ground),
    `the-husbander.md` (§2c/§4/§6(c), the dry-edge care), `the-spring.md` (§2/§3/§4, the
    wellspring's draw), `the-fallow.md` (§2a/§1/§3/§6(c), the one-way run-out as climate),
    `tide-of-the-attractor.md` (§2/§5a/§5b, the sustained thin), `farm-that-feeds.md`
    (§2/§4/§5, the sparse crop), `energy-harnessing.md` (§2/§6/§7 Q1, the sparseness
    economics), `the-compost.md` (§1/§4, the thin soil), `the-cold.md` (§1/§2/§3, the
    heat's thin, the cold's dry cousin).
      Reverse pointers added (48 edges total: quarry 12, shepherd 11, archivist 12,
      desert 13). Two-way each. **Canonical check: a quarry converts nothing (`output ≤
      φ⁻¹·input`; the take books on the settled op-record verbatim, the spent face turned
      back at a loss never a mint); a shepherd provides nothing (the honest no-reward);
      the archivist records, never mints (holds the settled op-record raw verbatim, the
      single non-forgeable point the book's own — cannot corrupt the raw); a desert
      provides nothing beyond its own thin regime, no scarcity that yields (`output ≤
      φ⁻¹·input` + `E_waste=(1−q)·E_throughput`; the desert is NOT the between, a lived
      thin not the field's own outside) — all verified.**
    Ledger extension: wrote the four genuine audit rows (quarry/shepherd/archivist/
    desert, each after its edges were grep-verified), the canonical-number checks, the
    count note updated (154/158, four unindexed wave-49+ arrivals), the verdict extended
    to wave 45.


42. **Wave-46 re-points (pass 31).** The three wave-46 docs — the-broker, the-smell,
    the-river — all landed two-way against their pass-spec sources. **the-broker** (14
    sources): `the-market.md` (§1/§2/§3/§6d/§6b/§4.1, the between-carrier against),
    `the-toll.md` (§1/§3/§2/§4/§5b/d/e, the charged-then-welcomed), `seed-garden.md`
    (§2/§3/§4.2/§6b/§7, the rare carrier), `the-atlas-of-windows.md` (§1/§2/§3/§4b/§4d,
    the far-land's plier), `window-guests.md` (§1/§2/§3/§6b/§6d, the verified stranger),
    `the-between.md` (§1/§3/§3a/§5d/§2c, the dark's carrier), `the-mimic.md`
    (§1/§3/§4/§5b, the held-line read), `life-signal.md` (§1/§3/§3.3/§6a/§6d/§6b, the
    verified carrier), `signature-predator.md` (§1/§2/§1.3/§7e/§8, the rarity's draw),
    `shared-ledger.md` (§1.2/§2.1/§6c/§6d/§6e/§3.3, the booked trade),
    `field-emergent-ecology.md` (§2.2, the morphology), `energy-harnessing.md` (§2/§6,
    the carry's cost), `the-gatekeeper.md` (§1/§2/§5c/d/e, the admitted visitor),
    `the-census.md` (§2/§2.4/§6d, the counted visitor). **the-smell** (16 sources):
    `life-signal.md` (§1/§3/§3.1/§6a/§6b/§6c/§6d, the air-form read), `the-wind.md`
    (§1/§3/§5b/§5c/d/e, the carry read at the nose), `the-blight.md` (§2/§6e/§6c/d/e,
    the wrong-stink), `the-roost.md` (§2/§3/§4/§5e, the home's musk), `the-spring.md`
    (§3/§5c/d/e/§6, the clean sweetness), `the-mimic.md` (§3/§5b-1/§5d/§5e, the wrong
    smell), `the-marsh.md` (§3/§8/§7c/d/e, the reek that swamps), `the-rain.md`
    (§3/§5b/§5c/d/e, the wet-wash), `farm-that-feeds.md` (§2/§5, the hearth's smoke),
    `player-remains.md` (§1/§1.3/§5d, the body's scent), `energy-harnessing.md` (§2/§6,
    the waste read at the air), `the-stilling.md` (§2, the held quiet),
    `signature-predator.md` (§1/§2/§7e/§8, the trail's scent), `field-hazards.md` (§5.1,
    the readable-before-it-arrives), `field-instruments.md` (§2.1, the family rule),
    `field-music.md` (§1/§6, the air's sibling). **the-river** (16 sources):
    `the-sea.md` (§2a/§2b/§2c/§5b/§5c/d/e, the place-regime), `coherence-highway.md`
    (§1/§3.1/§4/§6b/§6c/§6d, the grown twin), `the-marsh.md` (§2/§3/§5/§8, the
    wide-slow twin), `the-desert.md` (§2/§3, the wet-counter), `farm-that-feeds.md`
    (§2/§3/§4/§5, the fertile bank), `the-cart.md` (§2/§3/§4b/open-Q6, the road's fluid
    twin), `the-swim.md` (§2a/§2b/§5d, the two-face current), `the-dive.md` (§1/§2, the
    shallow current), `the-flood.md` (§2/§4.1, the overshoot), `the-rain.md` (§2/§4, the
    recharge), `the-threshold.md` (§1/§2.2, the crossing), `the-gatekeeper.md`
    (§1/§2/§4, the river-door), `the-toll.md` (§2/§4, the crossing's charge),
    `energy-harnessing.md` (§2/§6, the flow's cost and cap), `the-spring.md` (§2/§3,
    the well's outflow), `field-emergent-ecology.md` (§2.2/§4.2, the linear biome).
      Reverse pointers added (46 edges total: broker 14, smell 16, river 16). Two-way
      each. **Canonical check: the broker converts nothing, the trade is a transfer
      never a mint (`output ≤ φ⁻¹·input`; the broker's trade books on the settled
      op-record as a guest line, verified on the maintenance axis); a smell provides
      nothing (the scent is the field's own read, never a gain, never a detector-mint);
      a river converts nothing (the current is never a mint) — all verified.** House
      style: all inserted reverse-pointer bullets are clean AI-ism-free, closed em-dashes
      (the broker body's pre-existing "simply"/"just" are the doc author's prose, not
      the pass's inserts).
    Ledger extension: wrote the three genuine audit rows (broker/smell/river, each after
    its edges were grep-verified), the canonical-number checks, the count note updated
    (181/185, four unindexed wave-57+ arrivals), the verdict extended to wave 46.


43. **Wave-47 re-points (pass 32).** The three wave-47 docs — the-wage,
    the-spring-caretaker, the-migration — all landed two-way against their pass-spec
    sources (51 edges total: wage 15, spring-caretaker 16, migration 20). **Canonical
    check: a wage converts nothing, the transfer never a gain (`output ≤ φ⁻¹·input`; the
    wage books on the settled op-record `{member, op, worldPos, rung, magnitude,
    sustain}` verbatim §2.1 `schema-that-settles.md`; an unpaid wage is a false op);
    a caretaker converts nothing (the draw is spent, the clearing is real, never a mint;
    the misattribution guard held — a silted well must not blame a member who did not
    silt it); a migration provides nothing (the strip is real depletion never a mint;
    the larder-farm refused §7e `signature-predator.md`) — all verified.** House style:
    all inserted reverse-pointer bullets clean (closed em-dashes, no AI-isms).
    Ledger extension: wrote the three genuine audit rows (wage/spring-caretaker/
    migration, each after its edges were grep-verified), the canonical-number checks,
    the count note updated (181/185, four unindexed wave-57+ arrivals), the verdict
    extended to wave 47.


44. **Wave-48 re-points (pass 33).** The three wave-48 docs — the-ford, the-estuary,
    the-tutelary — all landed two-way against their pass-spec sources (45 edges total:
    ford 13, estuary 14, tutelary 18). **Canonical check: the ford converts nothing, no
    crossing that yields (`output ≤ φ⁻¹·input`; the boundary holds, steadies, marks —
    never mints); the estuary feeds at the field's own yield, never a mint (the mixing's
    loss is the field's own); the tutelary converts nothing, never a free shield (the
    shadow's own glow is the `(1−q)` waste) — all verified.** House style: all inserted
    reverse-pointer bullets clean.
      **The river↔ford two-way write-race is landed:** the-river's open-Q1 flagged
      the-ford absent (`the-ford.md and the-camp.md do not exist on disk`), holding the
      ford as `[assumption]`; now that the ford is on disk (wave 48), the river's open-Q1
      reads it two-way — the ford is the river's natural shallow, its crossing-door made
      real. The camp remains honestly absent (still `[assumption]`, not forced, mirroring
      the cart's the-camp open-Q6).
    Ledger extension: wrote the three genuine audit rows (ford/estuary/tutelary, each
    after its edges were grep-verified), the canonical-number checks, the river↔ford
    two-way, the count note updated (181/185, four unindexed wave-57+ arrivals), the
    verdict extended to wave 48.


45. **Wave-49 re-points (pass 34).** The three wave-49 docs — the-midwife, the-inn,
    the-blizzard — all landed two-way against their pass-spec sources (50 edges total:
    midwife 18, inn 17, blizzard 15). **Canonical check: the midwife converts nothing
    (`output ≤ φ⁻¹·input`; the first read real and spent never a mint; the birth-line
    books on the settled op-record, cannot be forged); an inn converts nothing (an inn
    charged without the held room is a false op; the paid night books on the settled
    op-record verbatim); a blizzard converts nothing (`E_waste=(1−q)·E_throughput`; the
    cover spent and gone never a mint, never a free cloak; the blizzard is NOT the
    storm) — all verified.** House style: all inserted reverse-pointer bullets clean.
    Ledger extension: wrote the three genuine audit rows (midwife/inn/blizzard, each
    after its edges were grep-verified), the canonical-number checks, the count note
    updated (181/185, four unindexed wave-57+ arrivals), the verdict extended to wave 49.


46. **Wave-50 re-points (pass 35).** The three wave-50 docs — the-understory,
    the-mirage, the-mint — all landed two-way against their pass-spec sources (42
    edges total: understory 15, mirage 14, mint 13). **Canonical check: the understory
    converts nothing (`output ≤ φ⁻¹·input`; the canopy’s absorption the field’s own
    spent); a mirage converts nothing, no lure that farms to (the deception is the
    instrument’s interpretation of a genuine read, never the field mis-stating itself;
    the composed bright un-sustained, fades); a mint converts nothing, the coin never
    yields (the strike books on the settled op-record verbatim, unforgeable) — all
    verified.** House style: all inserted reverse-pointer bullets clean.
    Ledger extension: wrote the three genuine audit rows (understory/mirage/mint, each
    after its edges were grep-verified), the canonical-number checks, the count note
    updated (181/185, four unindexed wave-57+ arrivals), the verdict extended to wave 50.


47. **Wave-51 re-points (pass 36).** The three wave-51 docs — the-orchard, the-delta,
    the-sledge — all landed two-way against their pass-spec sources (44 edges total:
    orchard 17, delta 12, sledge 15). **Canonical check: the orchard gives at the field’s
    own yield, never a mint (`output ≤ φ⁻¹·input`; a standing grove falls toward the
    fallow’s depletion without husbanding); a delta converts nothing (the spread never a
    mint; the fan disperses a signature the predator would read as a line); the sledge
    converts nothing — no glide that yields, never a winter-mint (the freight crossed
    honest doors, never a hidden sled-path) — all verified.** House style: all inserted
    reverse-pointer bullets clean. Ledger extension: wrote the three genuine audit rows
    (orchard/delta/sledge, each after its edges were grep-verified), the canonical-number
    checks, the count note updated (181/185, four unindexed wave-57+ arrivals), the
    verdict extended to wave 51.


48. **Wave-52 re-points (pass 37).** The three wave-52 docs — the-raft, the-eclipse,
    the-pooka — all landed two-way against their pass-spec sources (45 edges total:
    raft 15, eclipse 16, pooka 14). **Canonical check: a raft converts nothing, no
    current that yields (`output ≤ φ⁻¹·input`; the freight crosses honest doors, a
    bulk load at an un-held harbor a false op); the eclipse converts nothing, no dark
    that yields (the eclipse is not the stillness, drawn never blurred); a pooka
    converts nothing, the riling spent never a gain (read to resolution like any false
    op) — all verified.** House style: all inserted reverse-pointer bullets clean.
    Ledger extension: wrote the three genuine audit rows (raft/eclipse/pooka, each
    after its edges were grep-verified), the canonical-number checks, the count note
    updated (184/185, one unindexed wave-57+ arrival, corpus-map), the verdict extended
    to wave 52.


49. **Wave-53 re-points (pass 38).** The three wave-53 docs — the-chant, the-touch,
    the-siren — all landed two-way against their pass-spec sources (46 edges total:
    chant 17, touch 13, siren 16). **Canonical check: a chant converts nothing, the
    held voice spent never a gain (`output ≤ φ⁻¹·input`; the chant holds never gains);
    a touch converts nothing (a pure consumer at zero distance, never a mint); the
    siren converts nothing, no entrainment that yields, no seduction that mints (the
    call is never a hidden difficulty, never a minted charm) — all verified.** House
    style: all inserted reverse-pointer bullets clean. Ledger extension: wrote the
    three genuine audit rows (chant/touch/siren, each after its edges were
    grep-verified), the canonical-number checks, the count note updated (184/185, one
    unindexed wave-57+ arrival, corpus-map), the verdict extended to wave 53.


50. **Wave-54 re-points (pass 39).** The three wave-54 docs — the-meadow, the-canal,
    the-cistern — all landed two-way against their pass-spec sources (45 edges total:
    meadow 16, canal 16, cistern 13). **Canonical check: a meadow converts nothing, the
    graze never a mint (`output ≤ φ⁻¹·input`; the meadow is the field’s *renewed* never
    the mined strip; the keeping books nothing); a canal converts nothing, the dug lane
    never a mint (the canal re-aims the river’s own lane, its freight crossing no hidden
    lane); a cistern converts nothing, the drawn hold never a mint (the draw shares the
    spring’s over-draw honest counter) — all verified.** House style: all inserted
    reverse-pointer bullets clean. Ledger extension: wrote the three genuine audit rows
    (meadow/canal/cistern, each after its edges were grep-verified), the canonical-number
    checks, the count note updated (184/185, one unindexed wave-57+ arrival, corpus-map),
    the verdict extended to wave 54.


51. **Wave-55 re-points (pass 40).** The three wave-55 docs — the-meteor, the-balefire,
    the-baptism — all landed two-way against their pass-spec sources (43 edges total:
    meteor 15, balefire 15, baptism 13). **Canonical check: a meteor converts nothing,
    the fall never a mint (`output ≤ φ⁻¹·input`; announced, deterministic, never random,
    never hidden); a balefire converts nothing, the warning spent never a mint (the
    raised flame the field’s own spent; a false-balefire warning a false op); a baptism
    converts nothing, the naming spent never a mint (you cannot name falsely; the naming
    books on the settled op-record) — all verified.** House style: all inserted
    reverse-pointer bullets clean (a `.’s` typo in the-name and rite-of-passage bullets was
    fixed). Ledger extension: wrote the three genuine audit rows (meteor/balefire/
    baptism, each after its edges were grep-verified), the canonical-number checks, the
    count note updated (184/185, one unindexed wave-57+ arrival, corpus-map), the verdict
    extended to wave 55.


52. **Wave-56 re-points (pass 41 — FINAL).** The four wave-56 docs — the-palanquin,
    the-fog, the-drought, the-caravan — all landed two-way against their pass-spec
    sources (61 edges total: palanquin 16, fog 15, drought 12, caravan 18). **Canonical
    check: a palanquin converts nothing, no bearing that yields, never a minted seat,
    never a hidden privilege; a fog converts nothing, the blur spent never a gain (not the
    mirage — it blurs what is truly there); a drought converts nothing, the dry spent
    never a gain (the *event* of going dry, the process distinct from the desert’s place);
    a caravan converts nothing, no organized passage that yields (the goods cross held
    doors, never a hidden train; a phantom caravan-load a false op) — all `output ≤
    φ⁻¹·input`, verified.** House style: all inserted reverse-pointer bullets clean.
    Ledger extension: wrote the four genuine audit rows (palanquin/fog/drought/caravan,
    each after its edges were grep-verified), the canonical-number checks, the count note
    updated (184/185, one unindexed wave-57+ arrival, corpus-map), the verdict extended to
    wave 56 — **completing the wave-46–56 sweep of the t19 reconciliation pass (fixes
    42–52, waves 46–56 all audited two-way).**

53. **Wave-57 re-points (pass 42).** The three wave-57 docs — the-dune, the-terrace,
    the-votive — all landed two-way against their pass-spec sources (40 edges total:
    dune 11, terrace 14, votive 17 new + the pre-existing shrine two-way). **Canonical
    check: a dune converts nothing, no moving sand that yields, never a minted dune;
    a terrace converts nothing, the runoff’s steps spent never a gain; a votive converts
    nothing, the left order spent never a gain, never a minted offering — all `output
    ≤ φ⁻¹·input`, verified.** House style: all inserted reverse-pointer bullets clean.
    Ledger extension: wrote the three genuine audit rows (dune/terrace/votive, each after
    its edges were grep-verified), the canonical-number checks, and the count note. The
    votive’s `the-shrine.md` reverse pointer is a genuine two-way (the shrine had already
    resolved the votive’s open remainder) — verified both directions before writing.

54. **Wave-58 re-points (pass 43).** The three wave-58 docs — the-shrine, the-lightning,
    the-crossroads — all landed two-way against their pass-spec sources (45 edges total:
    shrine 14, lightning 15, crossroads 15). **Canonical check: a shrine converts nothing,
    the held order is spent, never free; a lightning converts nothing, the settled charge
    releasing a front never a yield, never a minted flash (the absent `the-storm.md` is
    honestly named, field-hazards + weather-not-storm standing in); a crossroads converts
    nothing, no meeting that yields, never a minted crossing (only a held door at a meeting
    books a toll) — all `output ≤ φ⁻¹·input`, verified.** House style: clean. Ledger
    extension: three genuine audit rows (shrine/lightning/crossroads), canonical checks,
    count note. The shrine’s `the-votive.md` reverse pointer is a genuine two-way (this
    doc closes the votive’s open remainder) — verified both directions.

55. **Wave-59 re-points (pass 44).** The three wave-59 docs — the-rumor, the-generations,
    the-shaft — all landed two-way against their pass-spec sources (51 edges total:
    rumor 16, generations 22, shaft 13). **Canonical check: a rumor converts nothing, the
    passed word spent never a gain, never a minted claim (a false rumor mis-names and fades);
    a generation converts nothing, the passed order spent never a gain, never a minted
    lineage; a shaft converts nothing, the dug depth spent never a gain, never a minted
    shaft (the depth is bounded, never hidden) — all `output ≤ φ⁻¹·input`, verified.**
    House style: clean. Ledger extension: three genuine audit rows
    (rumor/generations/shaft), canonical checks, count note.

56. **Wave-60 re-points (pass 45).** The three wave-60 docs — the-hand-over,
    the-seacraft, the-whirlpool — all landed two-way against their pass-spec sources
    (45 edges total: hand-over 14, seacraft 14, whirlpool 17). **Canonical check: a
    hand-over converts nothing, the office passed spent never a gain, never a minted turn;
    a seacraft converts nothing, the sailed passage spent never a gain, never a minted
    craft; a whirlpool converts nothing, the spun water spent never a gain, never a minted
    drain (a whirlpool converts nothing harder than a river) — all `output ≤ φ⁻¹·input`,
    verified.** House style: clean. Ledger extension: three genuine audit rows
    (hand-over/seacraft/whirlpool), canonical checks, count note.

57. **User-requested docs re-points (pass 46 — t20 FINAL).** The two user-requested
    docs — the-incantation, world-difficulty — all landed two-way against their
    pass-spec sources (40 edges total: incantation 24 + the pre-existing world-difficulty
    two-way, world-difficulty 16). **Canonical check: an incantation converts nothing, never
    creates order from nothing, never a free spend, never a mint; world-difficulty converts
    nothing, the dial scales the field’s own extremes, never generates order (a wild
    world’s storms convert nothing) — both `output ≤ φ⁻¹·input`, verified.**
    House style: all inserted reverse-pointer bullets clean. Ledger extension: two genuine
    audit rows (incantation/world-difficulty), the canonical checks, the count note, and
    the verdict extended to these final arrivals — **completing the t20 reconciliation
    pass (waves 57–60 + the two user-requested docs, fixes 53–57, all 14 docs audited
    two-way). The incantation’s `world-difficulty.md` reverse pointer is a genuine
    two-way — verified both directions before writing.**


58. **Final-wave re-points (pass 47 — t21, PROGRAM FINAL).** The seven final docs —
    the-tunnel, the-waterfall, the-crane, the-comet, the-bog, the-atoll, the-anchor —
    all landed two-way against their pass-spec sources (84 edges total: tunnel 14,
    waterfall 11, crane 12, comet 12, bog 13, atoll 11, anchor 11). **Canonical check: a
    tunnel converts nothing, the dug line spent never a gain; a waterfall converts
    nothing, a rotor in the fall a real costed turbine with `(1−q)` waste; a crane
    converts nothing, never a free hoist; a comet converts nothing, never a minted omen;
    a bog converts nothing, the held wet spent never a gain; an atoll converts nothing,
    never a minted island; an anchor converts nothing, never a minted harbor — all
    , verified.** House style: all inserted reverse-pointer bullets
    clean. **Three two-ways now genuinely landed both directions:** the-anchor’s
     reverse pointer closes the seacraft’s open-Q6 (the banked
    reversible mooring now landed); the-tunnel’s  reverse pointer makes
    the shaft-twin two-way; the-waterfall’s  reverse pointer makes
    the one-drop-it-does-not-ride two-way. Ledger extension: wrote the seven genuine
    audit rows (each after its edges were grep-verified), the canonical checks, the count
    note, and the verdict extended to these final arrivals — **completing the t21
    reconciliation pass, and with it the corpus reconciliation program (all on-disk
    design docs now audited two-way except the single un-README-indexed corpus-map).**


---



## 4. Verdict — cross-doc dependencies

**Closed two-way:**
- **`async-field-domain` Q1 (world↔field mapping)** → resolved by
  `chunk-field-quantization` §1.2, and the reverse-ref (chunk → async) is now
  explicit. Reads both ways.
- **`async-field-domain` Q4 (player-return channel)** → consumers
  `coherence-magic` §5.1, `energy-harnessing` §2 intro (and §0), and
  `custom-blocks.md` §2 all cite it; async Q4 now names them back.
- **`coherence-magic` Q4/Q5** → the material-regimes fire-vs-explosive boundary:
  `coherence-magic` §4.3 forward-refs `material-regimes` (explosive physics
  owned there); `material-regimes` §3(b) explicitly cites `coherence-magic` §4.3
  as the overdraw trigger. This was already two-way and is confirmed intact.
- **`coherence-technologies` Q6** → concept-4 pickups verified landed and cited
  (`material-regimes` §5, `energy-harnessing` §2/§4.4); note corrected so it no
  longer asserts a concept-5 pickup in material-regimes that does not exist.

**Remaining open (by design, not gaps):**
- `async-field-domain` Q1's *beyond-Phase-1* sub-question — the movable
  home-window relocation policy past the first box — is open *by design* but now
  has an **owner-by-assignment named in the seam**: `world-seams.md` §4.2 is
  recorded in `async-field-domain.md` §7 Q1 as the policy's owner (fix 11), and
  `resonance-seeds.md` open-Q5 + `field-archaeology.md` §6c#2 depend on it. The
  ownership chain reads both ways; the *policy itself* stays open until world-seams
  resolves it. Not a corpus inconsistency.
- `coherence-technologies` concept 5 (cascade staging) has a single corpus
  consumer (`custom-blocks.md` §2) that itself flags the ~10-rung/lab-scale
  interplay as the two-gate-dependent design; no §-reference gap.
- `material-regimes` §7's Phase-1.5 gates (per-cell ω₀²/ξ, per-material γ/ν/μ)
  are the documented upstream dependencies for `custom-blocks.md`; both are
  cross-referenced and remain open engine work, correctly flagged.

**Wave 8 cross-doc open-question ownerships (all closed on this pass):**

| Dependency | Direction verified in the docs | Reverse pointer | Status |
|---|---|---|---|
| `field-hazards.md` open-Q2 (storm provenance) ↔ `field-npc-ai.md` §4.3 | `field-npc-ai.md` §4.3 and §6(b) cite `field-hazards.md` open-Q2; reverse pointer now added to `field-hazards.md` open-Q2 (fix 8) | `← field-npc-ai §4.3` added | **closed two-way** |
| `field-hazards.md` open-Q4 (dead window) ↔ `field-npc-ai.md` open-Q5 | `field-npc-ai.md` open-Q5 cites `field-hazards.md` open-Q4; reverse pointer now added to `field-hazards.md` open-Q4 (fix 9) | `← field-npc-ai open-Q5` added | **closed two-way** |
| `field-archaeology.md` open-Q3 ↔ `field-music.md` open-Q2 (growl-vs-scar classifier) | `field-music.md` open-Q2 cites `field-archaeology.md` §3.1 / open-Q3; reverse pointer now added to `field-archaeology.md` open-Q3 (fix 10) | `← field-music open-Q2` added | **closed two-way** |
| `async-field-domain.md` §7 Q1 (window relocation) ↔ `resonance-seeds.md` open-Q5 + `world-seams.md` §4 | `resonance-seeds.md` open-Q5 + `field-archaeology.md` §6c#2 + `world-seams.md` §4.2 all cite `async-field-domain.md` §7 Q1; `world-seams.md` §4.2 assigns itself owner; owner-by-assignment name now added to `async-field-domain.md` §7 Q1 (fix 11) | "owner-by-assignment: `world-seams.md` §4.2" added | **closed two-way** |
| `field-npc-ai.md` open-Q3 (individual Π pattern vs the village bath) | open within `field-npc-ai.md`: §2.1 (identity = persistent Π pattern) vs §3.1 (village = Qi-bath commons); grounded in `coherence-commons.md` §7 (the multiplicative commons) | — | **recorded open** (a design decision, not a missing ref), owners: `field-npc-ai.md` §3.1 vs §2.1, theory owner `coherence-commons.md` §7 |

**Wave 9 cross-doc open-question ownerships (all closed two-way on this pass):**

| Dependency | Direction verified in the docs | Reverse pointer | Status |
|---|---|---|---|
| `player-remains.md` open-Q1 (re-lock computation site) ↔ `field-npc-ai.md` §7 open-Q1 | `player-remains` mirrors `field-npc-ai` §7 open-Q1's decision-layer fork; reverse pointer now added to `field-npc-ai.md` §7 open-Q1 (fix 13) | `← player-remains open-Q1` added | **closed two-way** |
| `player-remains.md` open-Q3 (own-fossil vs live-player) ↔ `field-archaeology.md` §7 open-Q3 | `player-remains` inherits `field-archaeology` §7 open-Q3's classifier; reverse pointer now added to `field-archaeology.md` §7 open-Q3 (fix 13) | `← player-remains open-Q3` added | **closed two-way** |
| `tide-of-the-attractor.md` open-Q3 (thin-trough vs desert threshold) ↔ `field-hazards.md` §6.2/open-Q1 | `tide-of-the-attractor` §5(b)/open-Q3 cite `field-hazards.md` §6.2's threshold; reverse pointer now added to `field-hazards.md` open-Q1 (fix 13) | `← tide-of-the-attractor open-Q3` added | **closed two-way** |
| `tide-of-the-attractor.md` open-Q5 (mixel-scale q-gate coupling) | probes the theory-solver's `(1−q)` gate vs the q-free engine kernel, owning doc `qi-as-time-clock.md` §2.1 | — | **recorded** — theory-owned; no design-doc owner, correctly open |

**Pocket-cosmos fold (reverse pointers added on this pass, fix 13):** the pocket
`pocket-cosmos.md` (§1.2 the inward fold / third origin; §2.2 the planted-and-held
seed as an entry candidate) is cross-linked two ways — `world-seams.md` §3.1 now
names the pocket as the third (inward) origin beside its seeded/founded windows,
and `resonance-seeds.md` §2.3 names the pocket as the seed's next fold (entering
the seed's deepest store). Both read back to `pocket-cosmos.md` and both cite its
§1.2/§2.2 precisely.

The five one-way chains from the prior pass (fixes 7–11) and the three wave-9
reverse pointers (fix 13) are now all closed two-way, except `tide-of-the-
attractor.md` open-Q5, which is a theory probe with its owner in CassiTheory
(`qi-as-time-clock.md` §2.1) — not a reference gap.

**Wave 10–12 closures (fixes log 14): the life-signal classifier and the
reason-field resolution.**

The **life-signal maintenance-axis classifier** (`life-signal.md` §3/§6) closes
five previously deferred `M`-publication questions with one Phase-1 read, and the
five peer open-Qs now point at it two-way:

| Peer open-Q | The deferred question | Closed by `life-signal.md` | Status |
|---|---|---|---|
| `field-archaeology.md` §7 open-Q3 (live-vs-residue) | fossil core vs live organism vs scar | maintenance axis: live moves/pulses, fossil static/dark, scar flat plateau (§3.1) | **closed two-way** (fix 14) |
| `field-music.md` open-Q2 (growl-vs-scar) | is the storm's ε² front distinguishable from a scar? | rising-moving ε² = growl, flat plateau = scar; audio inherits the class (§3.2) | **closed two-way** (fix 14) |
| `field-npc-ai.md` §7 open-Q2 (deliberate-vent vs maintained-lock) | needs `M` published per-NPC? | no — the ε²-gradient sign + cadence shape separates them from the channels' time-series (§3.2) | **closed two-way** (fix 14) |
| `resonance-tutor.md` open-Q2 (recorded-vs-live phase gap) | needs `M` published per-player? | maintenance axis: a re-enacted live hold pulses, a static replay is flat (§3.2) | **closed two-way** (fix 14) |
| `player-remains.md` open-Q3 (own-fossil vs live-player) | must not misread a player on their fossil as alive | motion/cadence separates a maintained player from a static fossil; N4 is an explicit Go/No-Go (§6b) | **closed two-way** (fix 14) |

The **reason-field domain-side resolution** (`reason-field.md` §4/§5/§6) commits
the three-legged sampler-vs-domain fork to the domain side, and the three fork
open-Qs now all name it as the resolution:

| Fork open-Q | The fork | Resolved by `reason-field.md` | Status |
|---|---|---|---|
| `field-npc-ai.md` §7 open-Q1 (decision-layer location) | sampler vs domain | domain — a mind is a persistent-Π pattern read out as per-site intent-phase (§3.1), determinism strengthened (§6b), the ≤2,000-cap respected (§6b) | **resolved** (fix 14) — side decided; build LATER, gated on the meshless/Π frontier + Q4 (§6a) |
| `player-remains.md` open-Q1 (re-lock location) | server re-lock vs domain-side fuse | domain — a domain-side persistent-Π fuse the field holds, costed by the medium's own q-draw (§4.1) | **resolved** (fix 14) — same side, as its counterpoint demanded |
| `resonance-tutor.md` open-Q1 (trace-journal location) | server-side vs the publish | domain — the journal is a π-trail in the field itself, read through the Reason Field (§4.2) | **resolved** (fix 14) — same side |

**All three parse as one resolution** ("the two must pick the same side" — all
domain). Both family closures are additive pointers in the owning open-Q sections;
no open question is suppressed, each still records its genuine upstream gate (the
meshless/Π frontier, the Q4 schema, or the noise-floor probe). The open questions
that remain genuinely *open* (not ref-gaps) are the ones with a stated owner: 
`field-npc-ai.md` open-Q3 (design decision, owners §3.1 vs §2.1),
`tide-of-the-attractor.md` open-Q5 (theory probe, `qi-as-time-clock.md` §2.1), and
`shared-ledger.md` open-Q2 (the classifier's per-member `C(M) < 0` line — a
[design] dial, not a ref gap; the member-id rule that rode it is now DECIDED by
`schema-that-settles`, fix 16).

**Schema-settlement closures (wave 13–14, fix 16): `schema-that-settles.md`
decides the five deferred forks, and the five waiting consumers' open-Qs now all
point at it two-way.**

| Fork | The deferral | Settled by `schema-that-settles.md` | Consumers re-pointed (fix 16) | Status |
|---|---|---|---|---|
| **Member-id** | no `member` field on Q4 records | §2.1 — `member` first, attached at the world-writer's write, derived from the persistent-Π re-lock | `shared-ledger.md` §6c (LANDED — politics starts), §4.3 | **closed two-way** |
| **Sustain-flag vs re-emit** | held op = `{sustain}` flag or re-emit? | §2.2 — `sustain` is a flag (domain holds the source until released) | `shared-ledger.md` §4.1/§7 open-Q3, `field-music.md` open-Q3, `farm-that-feeds.md` open-Q3 | **closed two-way** |
| **Locality bounding** | two members in one cell cancel silently | §2.3 — cell-ownership rule (separate members' lines per cell, never a silent zero) | `shared-ledger.md` §4.3 | **closed two-way** |
| **Member-id across death** | does a reborn player keep one line? | §2.1.1 — same member line, new lock, no ledger amnesty | `shared-ledger.md` §7 open-Q1, `player-remains.md` §7 open-Q5 | **closed two-way** |
| **`M` publication** | publish per-entity `M` now or defer? | §3 — deferred probe, gated on `life-signal.md` §6 N2 / `signature-predator.md`'s accumulation model; ~8 KB f32 ≈ 1.3‰ if it lands | `life-signal.md` open-Q2, `signature-predator.md` open-Q2 | **closed two-way** |

**Weather-not-storm cross-reads (wave 13, fix 17).** The provenance probe
(`field-hazards.md` open-Q2), operationalized by `weather-not-storm.md` §3, is
now read two-way by the three docs that gate on it:

| Doc | Gated on the probe | Reverse pointer (fix 17) | Status |
|---|---|---|---|
| `field-hazards.md` open-Q2 (storm provenance) | the authoritative question the weather doc operationalizes | `← weather-not-storm §3` added (the probe is the pre-registered owner of the measurement) | **two-way** |
| `signature-predator.md` §7a (the Coda's formation) | re-gates on the same probe | `← weather-not-storm §3/§6a` added | **two-way** |
| `tide-of-the-attractor.md` §6 (the probe discipline) | the T1–T4 precedent the weather doc inherits | two-way pointer to `weather-not-storm` added | **two-way** |

The weather doc's verdict-A/B both licensed and shared across the storm's season
(weather), the Coda's formation (signature-predator), and the decoherence-
wielder's storm-ignition (`field-npc-ai.md` §4.3), per `weather-not-storm.md`
§6a. `fate-of-a-window.md` open-Q2 and §6e re-gate on these same formation gates
(recorded in its audit row).

**Wave-15 closures (fix 18): the wound and the burden inherit their deciding
gates from three wave-8/10 gates, all now two-way.**

| Wave-15 doc | The gate it inherits | The re-point (fix 18) | Status |
|---|---|---|---|
| `wound-remembered.md` | `field-hazards.md` open-Q4 (scar-lifecycle — does a broken lock re-open or heal?) | the wound's persistence claim rides this measurement; if the attractor always re-binds, the wound collapses to a presented-unhidden scar | **two-way** (wound §6b/§7; hazards open-Q4 cites it) |
| `wound-remembered.md` (the deed) + `the-burden.md` (the mechanical layer) | `signature-predator.md` §7b (the Q4 write-lane gate) | the deliberate lock-break / the Coda-attraction cannot exist as mechanics until Q4 is a real perturbation path; both inherit the gate | **two-way** (both docs + signature-predator §7b) |
| `wound-remembered.md` open-Q3 ("whose wound") | `shared-ledger.md` §6c (member-id, landed) | the wound's provenance needs the `{member, …}` attribution to name the hand | **two-way** (wound open-Q3; shared-ledger §6c cites it) |

The three wave-15 docs are otherwise clean (canonical numbers cited verbatim;
`the-burden.md`'s Coda-attraction `R` verified against `signature-predator.md`
§2.2). Their remaining open questions are genuine design decisions / probes with
stated owners, not reference gaps (the wound's open-Q2 is the life-signal
deliberate-vent residual; the burden's open-Q5 rides player-remains §5 open-Q5;
both correctly inherited).

**Wave-16/17 closures (fix 19): the still-room idiom extends to the body and the
archive; sleep adds the fifth life-signal class.**

| Additive re-point | What it records | Status |
|---|---|---|
| `life-signal.md` §3.1 → `sleep.md` §2.1 | the **live-but-idle fifth class** — the maintenance axis at its idle extreme (a maintained lock at rest); the N2/N4 idle-extension Go/No-Go inherited from §6b | **two-way** (fix 19) |
| `the-burden.md` §2b → `sleep.md` §1/§2b | sleep is the Still Room's repayment at its **nightly body-scale instance** (the bed is a personal Still-Room interval); the carried `R` continues through the night (clearing vs risk = two ledgers) | **two-way** (fix 19) |
| `field-instruments.md` §2.2 → `sleep.md` §3 + `seed-garden.md` §3 | the Still-Room base idiom at two further scales: the bed (body) and the vault (preservation) — zero new channel | **two-way** (fix 19) |
|| `patient-field.md` §5b → (note) | the L1–L3 local-tempo probe is the **wave-18 `the-clock.md`'s ground truth** — one measurement, not two. **Resolved on the wave-18 pass (fix 20): the clock (and the mirror's phase-gap face) landed and now read this probe back two-way** | **closed two-way** (fix 20) |

**Verified, no edit (this pass):** `player-remains.md` §5 open-Q5's
schema-that-settles §2.1.1 pointer **resolves** (the conservation-of-you / same-
member-line rule is intact); `the-name.md` §7 GRAND/LATER mechanical capstone is
confirmed with **no action** — the wave-18 `the-inheritance.md` is the in-flight
continuation of the identity stack.

The seven wave-16/17 docs are otherwise clean (canonical numbers cited verbatim;
`window-guests`' `R = ρ_signature·τ·M_stability` verified against
`signature-predator.md` §2.2 exactly; `the-chronicle` confirmed to **not** quote
the accumulation product at all — no divergence — with its ~5% CPU synth-render
matching the `synth_design.md` precedent). Their open questions are design
decisions / probes with stated owners, not ref-gaps. The corpus was **46 docs**
at the wave-16/17 count (verified: designs/ = 46, README = 46, no stray/ghost at
that moment). The two items queued there (the Clock ground-truth cross-ref;
the Inheritance capstone continuing `the-name.md` §7) are **both resolved on the
wave-18 pass** (fix 20).

**Wave-18 closures (fix 20): the Clock's and Mirror's shared probe gate, and the
Inheritance's capstone, are now two-way.**

| Wave-18 re-point | What it closes | Status |
|---|---|---|
| `patient-field.md` §5b → `the-clock.md` §5b/§6 (and §5a/§2) | the L1–L3 local-tempo probe is the Clock's deciding gate — the clock landed and cites it (meaningful-hands gate = this probe's verdict), and patient-field §5b now names the landed clock back. **Resolves the queued Clock cross-ref two-way** | **closed two-way** (fix 20) |
| `patient-field.md` §5b → `the-mirror.md` §3/§6a | the Mirror's phase-gap face rides the same L1–L3 measurement (presentation-only if flat); patient-field §5b now names the Mirror back — one probe, both instruments stand or fall together | **closed two-way** (fix 20) |
| `the-name.md` §7 → `the-inheritance.md` §8 | the Inheritance is the identity stack's capstone, built on the name's anchor principle (a willed name is one claimable bequest, §2.2); the-inheritance §8 cites the-name §7's scaffold-now verdict as its model. **Resolves the queued Inheritance capstone cross-ref two-way** | **closed two-way** (fix 20) |
| `the-festival.md` §4 | the corpus's joy doc — no action that pass; the mourning twin `the-funeral` is now landed (wave 19) and the twin reverse pointer is added (fix 21) | **resolved on wave-19/20** (fix 21) |

**Verified, no edit (that pass):** `the-clock.md` §5/§2 and `the-mirror.md`
§3/§6a **both ride `patient-field.md` §5b's L1–L3 probe** (verified one-way in
each; the patient-field §5b note now reads both back two-way). The four wave-18
docs were otherwise clean (canonical numbers cited verbatim; `the-mirror`'s
`R = ρ_signature·τ·M_stability` restatement at lines 196–219 and its "verified
against `signature-predator.md` §2.2 exactly" cross-ref claim were **TRUE** —
verified). The corpus was **50 indexed docs (53 on-disk, 3 wave-19 in-flight)** at
that moment; the two items queued there (wave-19 audit incl. the funeral-as-twin;
the wave-19 continuation) are both resolved on the wave-19/20 pass (fix 21).

**Wave-19/20 closures (fix 21): the mourning twin, the exile↔election authority
tie, the player-vs-NPC fork, and the tide/shared-symbol gates, all two-way.**

| Wave-19/20 re-point | What it closes | Status |
|---|---|---|
| `the-festival.md` §4 → `the-funeral.md` §1/§5.1 | the **mourning twin** — the same coordinated mechanics, same `M ≈ 1` multiplicity, pointed at a loss instead of a harvest; the funeral also now carries THE inverse description of the festival (§1). **Closes the queued wave-19 audit note (funeral = festival's grief-inverse)** | **closed two-way** (fix 21) |
| `the-exile.md` §7 open-Q2 ↔ `the-election.md` §4.4/§7 open-Q3 | the **hollow-eye/composition tie** — who performs the hollow-eye (a stewardship decision) has its natural home in the society's authority; the election's open-Q3 is the composition tie (steward-led vs separate settlement-wide act); exile → election pointer added, election → exile already present | **closed two-way** (fix 21) |
| `the-funeral.md` §7 open-Q4 ↔ `the-election.md` §7 open-Q4 ↔ `field-npc-ai.md` §7 open-Q3 | the **player-vs-NPC member fork** (who can be a mourner / candidate / hollow-eye performer) — all three name field-npc-ai §7 open-Q3; that open-Q is tightened to anchor the membership answer (NPC identity-in-bath ⇒ a real holder; sum-of-individuals ⇒ benefits-but-doesn't-hold) | **three-way confirmed & tightened** (fix 21) |
| `tide-of-the-attractor.md` §5a ↔ `the-cold.md` §5 + `the-election.md` §2.3 | the **tide probe** is the cold's climate gate and the election's momentum gate; consumers cited at the probe + reverse pointers added | **closed two-way** (fix 21) |
| `sleep.md` §2.2 ↔ `the-bell.md` §4 | the **night-ring** composes the sitting-signature danger (the margin bed / overnight τ); the bell cites sleep §2.2/§3, sleep §2.2 now reads the bell back | **closed two-way** (fix 21) |

The six wave-19/20 docs are otherwise clean (canonical numbers cited verbatim;
`the-election`'s `C(M)` and `the-funeral`'s `C(funeral)` build on
`shared-ledger.md` §1.2's aggregation exactly; `the-bell`'s Weatherglass-equal
cost profile and `the-cooked-field`'s no-new-physics stance verified). Their
remaining open questions are design decisions / probes with stated owners, not
ref-gaps. **The corpus was 56 docs, one number set, all cross-refs resolving**
(count check at that pass: designs/ = 56 files, README = 56 unique rows, no
stray files, no ghost rows).

**Wave-21/22 closures (fix 22): the pair-made-a-family, the family's house & joint
lifts, the cold↔flood mirror, and the night instruments' bell/mirror ties, all
two-way.**

| Wave-21/22 re-point | What it closes | Status |
|---|---|---|
| `the-apprenticeship.md` §5 ↔ `the-family.md` §4/§5 | the **pair made a family** — the veteran–student pair that co-binds around a shared hearth *is* a family, the same two-body joint read as a held social atom; family §4 already cites the apprenticeship §1/§2.1/§5 | **closed two-way** (fix 22) |
| `the-family.md` §3.2 ↔ `the-funeral.md` §2.2 + §3.2/§4 ↔ `the-inheritance.md` §2.2 | the **funeral re-binds the family's hold** (the dead co-holder's fraction re-bound into the family's anchor, not only the commons' core) and a **will to the house is a will to the family** — both directions now resolve | **closed two-way** (fix 22) |
| `the-treaty.md` §2.1 ↔ `the-family.md` §2.1/§4 | the **joint-hold principle lifted across the dark** — the Treaty is the Family's joint extended from N=2 members-in-one-window to N=2 windows-across-the-seam; family §4 now reads the treaty back | **closed two-way** (fix 22) |
| `the-cold.md` §5.3 ↔ `the-flood.md` + `tide-of-the-attractor.md` §5a | the **cold↔flood mirror** — the flood is the cold's opposite and equal danger, the same `output ≤ φ⁻¹·input` cap stress-tested from the too-much side; both gate on the tide probe (flood added as its third consumer) | **closed two-way** (fix 22) |
| `the-bell.md` §4 ↔ `the-lantern.md` §4 + `the-silence.md` §2.3/§5.1 | the **night instruments' reach** — the Lantern is the walker's personal bell, the hunting silence the Bell's quietest alarm; both docs cite the bell's §4 night ring as their settlement-scale home | **closed two-way** (fix 22) |
| `the-mirror.md` §4.4 ↔ `the-lantern.md` §4 | the **bedside made positional** — the wrong-warm Lantern at the bed pre-warns before the Mirror's `R` climbs; the lantern reads the mirror's §4.4 as its "Mirror at the bedside" composition | **closed two-way** (fix 22) |

The seven wave-21/22 docs are otherwise clean (canonical numbers cited verbatim;
`the-flood`'s `E_waste = (1−q)·E_throughput` and the-lantern's one-trilinear-sample
cost both verified against source exactly; `the-family`/`the-treaty` ride the
landed member-id + persistent-Π theory flags correctly). Their remaining open
questions are design decisions / probes with stated owners, not ref-gaps. **The
corpus was 63 docs, one number set, all cross-refs resolving** (count check at that
pass: designs/ = 63 files, README = 63 unique rows, no stray files, no ghost rows).

**Wave-23/24 closures (fix 23): the complement pair, the frontier riders, the
natural-first-teacher, the dimmed-read and quieter-sever ties, all resolved.**

| Wave-23/24 re-point | What it closes | Status |
|---|---|---|
| `the-seeker.md` §4/§2.2 ↔ `the-compass.md` §2.2/§4 | the **complement pair** — the Seeker finds what *you* named, the Compass what the *field* is organizing through; compass already cited the seeker, seeker now reads the compass back | **closed two-way** (fix 23) |
| `the-seeker.md` §4 ↔ `reason-field.md` §6a + `the-family.md` §2.2 | the **frontier riders** — the companion/family seeks read a persistent-Π identity gated on the meshless/Π frontier and the family's hearth-well; consumers note at reason-field §6a + the-family §2.2 reverse pointer | **closed two-way** (fix 23) |
| `the-child.md` §3.4 ↔ `the-apprenticeship.md` | the **natural first teacher** — the pair's live recording is the child's founding-lesson (the first past hand recorded live, not replayed); the apprenticeship reads the child back as its N=1 charge | **closed two-way** (fix 23) |
| `the-healer.md` §3.1 ↔ `the-mirror.md` §2.4 | the **dimmed read / toll's legibility** — the healer reads burdened/wound-like on the classification face; steward-with-weight Board guard (`shared-ledger.md` §6e) verified; the healer's funeral ref corrected to §2.3/§6d with **no residual §3.3 mis-reference** | **closed two-way** (fix 23) |
| `the-oath.md` §3.2 ↔ `the-exile.md` §4 | the **quieter sever** — the oath's break is the within-window sever quieter than exile (a promise's death, not a person's removal); exile §4 reads the oath back | **closed two-way** (fix 23) |
| `the-compass.md` §3.3 | the **provenance line at site scale** — verifies the reach's character classification inherits `weather-not-storm.md` §4a + `life-signal.md` §6 | **verified** (fix 23) |

The seven wave-23/24 docs are otherwise clean (canonical numbers cited verbatim;
the-compass's ~32 KB intent-phase and the seeker/compass cost profile verified
against source exactly; the-echo/the-stillness theory flags carried). Their
remaining open questions are design decisions / probes with stated owners, not
ref-gaps. **The corpus is now 70 indexed docs (74 on-disk with 4 wave-25
in-flight: `the-memory-palace`, `the-language`, `the-census`, `the-threshold`),
one number set, all indexed cross-refs resolving** (count check: designs/ = 74
files, README = 70 unique rows, no stray files, no ghost rows — the 4 extra
on-disk are the legitimate in-flight wave-25 batch).

**Wave-25/26 closures (fix 24): the memory/calendar/instrument docs land on the
settled stack, and the water/ecology/time hazards get their two-way ties.**

| Wave-25/26 re-point | What it closes | Status |
|---|---|---|
| `the-memory-palace.md` §3 ↔ `the-observatory.md` §3.5; §2.2 ↔ `the-chronicle.md` §2.3 | the palace is the observatory's past-self (its present-self portrait); the chronicle room mounts the record-shaped object | **closed two-way** (fix 24) |
| `the-census.md` §5 ↔ `the-observatory.md` §3.5; §2.2 ↔ `the-child.md` §7 open-Q2 | the population face of the self-portrait; the dormancy threshold inherits the empty-row rule | **closed two-way** (fix 24) |
| `the-threshold.md` §2.2 ↔ `the-bell.md` §4; §2.3 ↔ `window-guests.md` §3 | the gate's crossing is the Bell's predator channel; the arch is the first thing a visitor's provenance crosses | **closed two-way** (fix 24) |
| `the-blight.md` ↔ `field-emergent-ecology.md` §2.2/§5.3; `the-flood.md` §2/§3; `wound-remembered.md` §1 | the over-bloom made pathological; conservation = the heal; the wrong-band habitat; the clear's scar | **closed two-way** (fix 24) |
| `the-window-year.md` ↔ `the-festival.md` §3; `the-election.md` §4.3; `the-funeral.md` §3.3 | the bright anchor, the governance beat, the anniversaries — the calendar mounts the source observances; it rides the tide's [probe] period | **closed two-way** (fix 24) |
| `the-hourglass.md` ↔ `the-clock.md` §3.3; `the-healer.md` §2; path fix | the trip-meter to the speedometer; the bind's bound; `qi-as-time-clock.md` path corrected | **closed two-way** (fix 24) |

**Wave-27 closures (fix 25): the un-roaded crossing, the depletion, the
pilgrimage, and the tide-gauge all resolve two-way — plus the pilgrim↔walk
correction.**

| Wave-27 re-point | What it closes | Status |
|---|---|---|
| `the-pilgrim.md` §1/§3.1 correction → `the-walk.md` | the pilgrim's once-flag now cites the-walk (which landed after it); the pilgrim is the walk's craft composed at the pilgrimage's purpose; the-walk open-Q5 ↔ the-pilgrim §3.1 | **corrected + two-way** (fix 25) |
| `the-walk.md` §2a ↔ `coherence-highway.md` §2.2; §2c ↔ `signature-predator.md` §2 | the ridges walked ungated; the walking trail as signature-legible | **closed two-way** (fix 25) |
| `the-fallow.md` §2a ↔ `material-regimes.md` §3; §4.2 ↔ `the-exile.md` §4 | the mined vein gone-forever; the leaver's fork | **closed two-way** (fix 25) |
| `the-pilgrim.md` §2.1 ↔ `field-archaeology.md` §5.3; §4 ↔ `the-name.md` §6d | the attended ruin (conservation walked to); the re-bind's no-raise boundary | **closed two-way** (fix 25) |
| `the-tide-staff.md` §2.1 ↔ `tide-of-the-attractor.md` §2; §3.2 ↔ `fate-of-a-window.md` §1.3 | the band marks the seasons; the drift-from-marks renders the fate's decay at a place | **closed two-way** (fix 25) |

**Wave-28/29/30/31 closures (fix 26 for the-sea/the-tool; fix 27 for the
remaining twelve). The sea, the tool, the vigil, the working-song, the feral
instrument, the atlas, the drift-road, the scar-lifecycle, the interstitial, the
market, the scavenger, the school, the sea-floor, and the dawn all land two-way
on their sources. The waves 28–31 audit is now complete** (all fourteen
audit rows are genuine — every reverse pointer was inserted and grep-verified
before its row was written).**

|| Re-point (fix 26/27) | What it closes | Status |
|---|---|---|---|
|| `the-vigil.md` ↔ `the-lantern.md` §2/§4; `the-silence.md` §2/§5.2; `the-threshold.md` §2.2; `the-bell.md` §4; `signature-predator.md` §2/§7e; `the-election.md` §4.3/§7 | the watch-read, the watch's listening, the gate's keeper, the bell's keeper, the clean-signature exposure, the rotated watch — the corpus's first practice composes the night instruments | **closed two-way** (fix 27) |
|| `the-working-song.md` ↔ `the-vigil.md` §1; `field-npc-ai.md` §3.2; `the-tool.md` §2a; `material-regimes.md` §3; `the-healer.md` §2 | the second practice rises from the vigil's frame; a phase-locked group IS a working; the lumber-camp's bite, the forge-chant's line, the heal-song's bind | **closed two-way** (fix 27) |
|| `the-feral-instrument.md` ↔ `reason-field.md` §6a; `house-that-steers.md` §1/§3.2; `the-memory-palace.md` §2; `seed-garden.md` §3/§4; `the-oath.md` §1/§3 | the persistent-Π frontier, the self-chairing house, the over-keeping palace, the rudderless vault, the re-bind fork | **closed two-way** (fix 27) |
|| `the-atlas-of-windows.md` ↔ `the-map.md` §1; `the-chronicle.md` §1; `the-fallow.md` §3; `fate-of-a-window.md` §1/§6c; `the-memory-palace.md` §1 | the per-window drawing, the page's story, the depletion read, the arc read (forecast-≠-fate), the cross-window sibling | **closed two-way** (fix 27) |
|| `the-drift-road.md` ↔ `tide-of-the-attractor.md` §5b open-Q1; `the-stillness.md` §5.1; `the-festival.md` §3; `weather-not-storm.md` §4 | the drift-branch, the still-point end, the once-celebration, the weather-not-storm precedent | **closed two-way** (fix 27); **the pass-spec's "drift-road `M ≈ 1`" item was an honest negative — the drift-road carries no phase-lock/`M`/field-npc-ai §3.2 reference (it is a tide-verdict consequence doc), so no cite was forced** |
|| `the-scar-lifecycle.md` ↔ `patient-field.md` §3; `field-hazards.md` open-Q4; `house-that-steers.md` §3.2; `field-archaeology.md` §2; `the-blight.md` §4.2; `fate-of-a-window.md` §2/§3; `wound-remembered.md` §1.2/§7 open-Q5 | the healed scar under rest, the scar-lifecycle probe answered, the build-on-the-ruin, the strata-to-come, the clear's scar answered, the scar read's deep branch, the wound's fate answered | **closed two-way** (fix 27) |
|| `the-interstitial.md` ↔ `world-seams.md` §1.3/§2.1; `energy-harnessing.md` §7 Q1; `field-music.md` §1/§2; `the-atlas-of-windows.md` §2; `signature-predator.md` §1/§7; `patient-field.md` §3.3 + `the-hourglass.md` §3; `the-sea.md` §2b | the between the voyage crosses, the dilute field, the ringing, the distant pages read by ear, the lawful absence, the unforgiving patience, the flat plain made total | **closed two-way** (fix 27) |
|| `the-market.md` ↔ `schema-that-settles.md` §2.1 (op-record verbatim); `the-tool.md` §2; `seed-garden.md` §3; `the-name.md` §2; `shared-ledger.md` §6d; `the-oath.md` §1/§3; `window-guests.md` §3; `the-exile.md` §4; `the-census.md` §2.1 | the exchange as the settled op, the traded provenance, the false-op cheat, the small vow, the visitor line, the exiled line, the active-class face — trust by construction | **closed two-way** (fix 27) |
|| `the-scavenger.md` ↔ `field-emergent-ecology.md` §2.2/§6b; `signature-predator.md` §2.3/§7e; `the-fallow.md` §2a/§3; `the-blight.md` §4.2; `the-scar-lifecycle.md` §2.2/§2.3; `field-hazards.md` §1; `the-census.md` §1 | the residual-band organism, the spent margin / no-farming closure, the worked veins, the clear's scar as habitat, the kept scar's edge, the first non-hazard row, the spent's census | **closed two-way** (fix 27) |
|| `the-school.md` ↔ `the-working-song.md` §2.1; `field-npc-ai.md` §3.2; `shared-ledger.md` §1.2; `the-market.md` §1/§2.3; `the-vigil.md` §3/§4; `the-apprenticeship.md` §2.2; `the-name.md` §2 | the phase-lock applied to teaching, the booked competence, the false-op applied to teaching, the teacher's drain, the cannot-teach-what-the-field-does-not-hold honesty | **closed two-way** (fix 27) |
|| `the-sea-floor.md` ↔ `the-sea.md` §2b; `field-emergent-ecology.md` §4.2/§6b; `the-blight.md` §2; `deep-field-diving.md` §3.1/§4; `the-scar-lifecycle.md` §2.2; `field-archaeology.md` §2/§3.2 | the shelf's upper side, the reef's band, the water-borne habitat, the descent / net-negative hold, the reef-edge scar, the residue funnel | **closed two-way** (fix 27); the shelf's Phase-1 read is a pure consumer of the ≈ 6 MiB publish inside the ≈ 1–6 ms/tick sample budget — **matches** the Weatherglass cost |
|| `the-dawn.md` ↔ `the-lantern.md` §4; `the-vigil.md` §3; `signature-predator.md` §2; `patient-field.md` §3.3; `sleep.md` §3; `field-instruments.md` §2.1 | the night-read's end, the watch's end, the margin's thinning, the loan's interest re-opened, the bed decision's resolution, the family's becoming | **closed two-way** (fix 27); one or two samples across the transition window inside the ≈ 1–6 ms/tick budget, the Weatherglass's §1.4 cost — **matches** |

**Wave-32 closures (pass 17 / fix 28): the commensal, the gift, and the dispute all
land two-way on the society-and-stranger stack; the waves 28–32 audit is now
complete (fifteen genuine audit rows, each written only after its edges were
grep-verified).**

|| Wave-32 re-point | What it closes | Status |
|---|---|---|---|
|| `the-commensal.md` ↔ `field-emergent-ecology.md` §2.2/§6b/§5.3; `house-that-steers.md` §2.2; `energy-harnessing.md` §5.4; `the-sea-floor.md` §2b; `field-hazards.md` §1; `field-npc-ai.md` §1/§3; `the-scavenger.md` §1/§2 | the organism-class run at the ordered margin, the bath-edge habitat, the reef-warden, the **net-negative** bounded assist, the first positive row, the servant/neighbor line, the bright twin — the stranger-object layer's first positive face, the corpus's warmth | **closed two-way** (fix 28); the commensal's assist net-negative per energy-harnessing §5.4 — **matches** |
|| `the-gift.md` ↔ `schema-that-settles.md` §2.1/§2.1.1; `the-market.md` §2.3/§3; `the-name.md` §2; `shared-ledger.md` §6d; `the-festival.md` §2.3; `field-npc-ai.md` §3; `the-exile.md` §4; `window-guests.md` §3; `the-oath.md` §1/§3; `energy-harnessing.md` §6; `the-window-year.md` §3 | the un-booked giving as the booked exchange's inverse, the false-gift-is-a-false-name honesty, the tide-high generosity's microform, the commons' invisible glue, the severed line a gift cannot restore, the no-mint cap — the economy's only generosity | **closed two-way** (fix 28); the gift's op-record matches schema-that-settles §2.1 verbatim — **matches** |
|| `the-dispute.md` ↔ `shared-ledger.md` §6d; `field-npc-ai.md` §6d/§7 open-Q3; `schema-that-settles.md` §2.1; `the-name.md` §1/§2/§6e/open-Q3; `life-signal.md` §3; `the-observatory.md` §2; `the-oath.md` §1/§3; `the-market.md` §2.3; `the-election.md` §4.3/§4.4; `the-exile.md` §2/§4; `the-treaty.md` §3/§4 | the no-false-booking + the determinism + the anchors' provenance + the maintenance read compose the judgment; the clear-book prevents, the stewardship precedes, the severed-line severance, the two-true-holds limit, the cross-window treaty edge, the player-vs-NPC claimant fork — the final-unforgiving judge | **closed two-way** (fix 28) |

**Wave-33 closures (pass 18 / fix 29): the window-pulse, the zenith, the
stratum-read, and the harbor all land two-way on the health / temporal-family /
vertical-stack / movement-stack sources; the waves 28–33 audit is now complete
(nineteen genuine audit rows, each written only after its edges were
grep-verified).**

|| Wave-33 re-point | What it closes | Status |
|---|---|---|---|
|| `the-window-pulse.md` ↔ `house-that-steers.md` §1/§2.2; `shared-ledger.md` §1.2/§6c; `the-name.md` §1/§3.2/§6e; `the-commensal.md` §3; `life-signal.md` §3/§4; `fate-of-a-window.md` §1/§6; `the-window-year.md` §2/§3; `the-census.md` §2/§3/§7; `the-observatory.md` §2/§6b; `the-healer.md` §2 | the bath's level, the lines' mutual drift, the anchors' tethers, the warm steadiness — the four landed reads composed into one beating read; the census's health-twin, the we/never-I boundary, the leading-indicator honesty | **closed two-way** (fix 29); a pure consumer of the ≈ 6 MiB publish inside the ≈ 1–6 ms/tick budget — **matches** |
|| `the-zenith.md` ↔ `atmosphere-orbits-auroras.md` §1.4/§1.3/§2/§3; `energy-harnessing.md` §2/§6; `the-sea-floor.md` §1; `the-interstitial.md` §2a/§4; `world-seams.md` §2/§2.3; `field-archaeology.md` §2.1; `the-observatory.md` §2; `deep-field-diving.md` §1; `the-sea.md` §2b | the drain (the waste escaping the top), the boundary (the thin's far side), the edge (a boundary never a door) — the vertical's ceiling, the corpus's second interface, the top mirror of the deep | **closed two-way** (fix 29); the Phase-1 slice is a pure consumer of the ≈ 6 MiB publish — **matches** |
|| `the-stratum-read.md` ↔ `field-archaeology.md` §2/§3.2/§5.3; `the-clock.md` §1/§5(b)/§6; `the-hourglass.md` §1/§5(b); `fate-of-a-window.md` §1/§5/§2; `field-instruments.md` §2.1/§1.4; `the-scar-lifecycle.md` §2.2/§3.1/§2.1; `the-fallow.md` §2a/§5(d); `the-sea-floor.md` §2a/§4.2; `the-memory-palace.md` §1/§4/§6(d); `life-signal.md` §3/§6 | the temporal family's past-face reads what the field has kept; the archaeology's instrument-face reads the residue in place; the chosen-vs-kept complement; the read is present, never a replay | **closed two-way** (fix 29); one sample per stratum inside the ≈ 1–6 ms/tick budget — **matches** |
|| `the-harbor.md` ↔ `world-seams.md` §1/§2/§2.3; `the-threshold.md` §1/§2.1/§4/§6b; `the-interstitial.md` §1/§2/§3; `the-atlas-of-windows.md` §2/§3; `the-treaty.md` §1/§2.2; `the-lantern.md` §2/§4; `the-vigil.md` §2c/§2d/§3; `schema-that-settles.md` §2.1/§2.3; `shared-ledger.md` §1.2/§2; `the-sea.md` §2b/§5d; `the-fallow.md` §1/§3; `the-census.md` §2/§3; `the-walk.md` open-Q5 | the pier, the lamp, the ledger, the keeper — the designed departure point; a door never a shortcut; the movement stack's settlement-scale face; the walk's open-Q5 answered at the door | **closed two-way** (fix 29); the harbor's ledger books the departure as schema-that-settles §2.1's op-record verbatim; a consumer inside the ≈ 1–6 ms/tick budget — **matches** |

**Wave-34 closures (pass 19 / fix 30): the story, the rite-of-passage, and the
mirror-creature all land two-way on the culture / identity-stack / stranger-object
sources; the waves 28–34 audit is now complete (twenty-two genuine audit rows,
each written only after its edges were grep-verified).**

|| Wave-34 re-point | What it closes | Status |
|---|---|---|---|
|| `the-story.md` ↔ `the-name.md` §2/§3; `field-archaeology.md` §1.2/§2; `the-memory-palace.md` §2.2/§4; `the-chronicle.md` §3/§5; `the-reading-ahead.md` §1.1/§2.2/§6.3/§7c; `the-language.md` §1/§2.2/§2.3; `the-pilgrim.md` §2.1; `the-festival.md` §3/§2.2; `the-window-year.md` §3.1; `the-school.md` §2; `the-child.md` §3.4 | the settlement's myth made a field-memory — the shaped vs the recorded; the never-adds shaping bound (chronicle §5's "It never adds events."), the told version of the record, the lesson it teaches | **closed two-way** (fix 30); a composition over the landed reads inside the ≈ 1–6 ms/tick budget — **matches**; a story informs and holds, never mints |
|| `the-rite-of-passage.md` ↔ `the-child.md` §1/§3; `the-name.md` §1/§2; `the-apprenticeship.md` §1/§2.2; `the-school.md` §2.1/§4; `the-burden.md` §1/§2a; `the-family.md` §1/§2.1/§3.3; `the-oath.md` §2.1/§4.1; `the-election.md` §1/§4.3; `the-tide-staff.md` §1/§5; `resonance-seeds.md` §1/§2.1/§2.3/§3.1; `world-seams.md` §3.2; `the-festival.md` §1/§2; `field-npc-ai.md` §3.2; `energy-harnessing.md` §2/§6 | the five bindings — the naming, the first clean channel, the binding, the investiture, the founding; the phase-locked act (`M ≈ 1`, field-npc-ai §3.2's "a group acting phase-locked IS a working"); a rite is spent, never free | **closed two-way** (fix 30); the rite's mechanics ride the landed costs of its composed acts, never minting — **matches** |
|| `the-mirror-creature.md` ↔ `signature-predator.md` §1/§2.2/§3/§7e/§8; `life-signal.md` §1/§3.1/§3.2/§6b; `reason-field.md` §3.1/§6a; `the-name.md` §1/§2/§6b; `the-scavenger.md` §1/§2; `the-commensal.md` §1/§4; `field-hazards.md` §1/§5.1/§5.3; `the-burden.md` §1/§2c/§2d; `the-vigil.md` §3 | the echoed pattern's read — the mirror borrows the Coda's phase-matching and inverts it into a wearer; `R = ρ_signature · τ · M_stability` (signature-predator §2.2 verbatim); the maintenance axis is the test; the false-name decay | **closed two-way** (fix 30); a pure consumer of the publish inside the ≈ 1–6 ms/tick budget — **matches**; a mirror informs and confuses, never mints |

**Wave-35 closures (pass 20 / fix 31): the loan, the fall, the swim, and the
bedrock all land two-way on the economy / vertical / water / floor sources — and
the swim↔fall two-way special item is landed (the swim's open-Q5 closed as
resolved); the waves 28–35 audit is now complete (twenty-six genuine audit rows,
each written only after its edges were grep-verified).**

|| Wave-35 re-point | What it closes | Status |
|---|---|---|---|
|| `the-loan.md` ↔ `schema-that-settles.md` §2.1/§2.2; `the-tool.md` §2; `seed-garden.md` §3; `farm-that-feeds.md` §4; `the-window-year.md` §3.4; `tide-of-the-attractor.md` §2/§5a; `the-burden.md` §2a; `patient-field.md` §3.3/§5d; `energy-harnessing.md` §6; `the-market.md` §6d; `the-oath.md` §3; `the-exile.md` §4; `the-fallow.md` §2a | the forward order-borrowing — the Q4 op-record carried forward (`{member, op, worldPos, rung, magnitude, sustain}`, schema §2.1 verbatim), the term "next harvest" on the window-year's beat, the patience-interest, a loan is not a mint, the default's exile edge | **closed two-way** (fix 31); a composed forward book inside the ≈ 1–6 ms/tick budget — **matches**; a loan informs, never mints |
|| `the-fall.md` ↔ `coherence-highway.md` §2; `the-walk.md` §2a; `energy-harnessing.md` §2; `the-scar-lifecycle.md` §2.1/§2.2; `wound-remembered.md` §1; `the-sea.md` §2b; `deep-field-diving.md` §3; `patient-field.md` §2/§3.3 | the vertical's un-designed third act — the gradient owns you; the river law `a = −G_N·(π/ρ)·∇(g·Φ)` owned absolutely (corpus-reconciliation canonical verbatim); the landing's wound on the scar-lifecycle branch; a fall is the Bell with the craft removed | **closed two-way** (fix 31); a bounded consumer of the published channels, the same tier as the walk's stride read — **matches**; a fall converts nothing |
|| `the-swim.md` ↔ `the-sea.md` §2b; `energy-harnessing.md` §2; `the-walk.md` §2a; `coherence-highway.md` §2; `the-hourglass.md` §3; `patient-field.md` §3.3; `the-fall.md` §4.2; `the-sea-floor.md` §2b/§4 | the sea's third act, the walk's fluid form — the stroke's `(1−q)` drag, the current's `∇(g·Φ)` read blind, the sea's patience; **the swim↔fall two-way is LANDED (special item): a fall into the sea is the swim's beginning (§4.2), the swim's descent is the fall's soft landing — swim's open-Q5 closed as resolved** | **closed two-way** (fix 31); a bounded consumer of the publish, Phase-1 slice clean, inside the ≈ 1–6 ms/tick budget — **matches**; a swim converts nothing |
|| `the-bedrock.md` ↔ `material-regimes.md` §4/§3; `the-tool.md` §2a; `deep-field-diving.md` §3/§4; `field-archaeology.md` §2.3/§2.4/§3.2; `the-fallow.md` §2a; `resonance-seeds.md` §1.1; `the-zenith.md` §1/§3; `the-sea-floor.md` §1 | the window's absolute floor — the maximal-rung regime no alloy exceeds, the tool's bite skates, the precipitation law, the archaeology reads down to it, the seed's deep rest | **closed two-way** (fix 31); a composition over the deep's landed reads inside the ≈ 1–6 ms/tick budget — **matches**; a floor informs, never mints |

**Wave-36 closures (pass 21 / fix 32): the cave, the landform-name, and the
witness all land two-way on the deep / landscape-naming / stranger-object
sources; the waves 28–36 audit is now complete (twenty-nine genuine audit rows,
each written only after its edges were grep-verified).**

|| Wave-36 re-point | What it closes | Status |
|---|---|---|---|
|| `the-cave.md` ↔ `the-scar-lifecycle.md` §2.2/§2.3; `the-stratum-read.md` §2.2; `the-fallow.md` §2a/§2c/§2d; `deep-field-diving.md` §3.1/§5/§6.3/§2.2/§6.2; `field-hazards.md` §4.2/§4.4/§2; `the-bedrock.md` §2a/§5b/§7 open-Q4; `the-flood.md` §2/§3/§4.1; `field-archaeology.md` §3.2/§1.2; `energy-harnessing.md` §2; `the-sea-floor.md` §6b | the vertical's hollow — the four formations (the wound that healed hollow, the emptied deep-rung store, the BH's swept wake, the flood's aftermath's undercut) compose a cave that reads as itself; the corpus's first volume | **closed two-way** (fix 32); the Phase-1 slice reads the ≈ 6 MiB publish inside the ≈ 1–6 ms/tick sample budget — **matches**; a cave provides nothing |
|| `the-landform-name.md` ↔ `the-name.md` §1/§2.1/§5.1/§7/§3.3/§6e; `material-regimes.md` §4/§3; `chunk-field-quantization.md` §5; `coherence-highway.md` §1.1/§4.1; `the-sea.md` §2a; `the-threshold.md` §1/§6; `the-observatory.md` §2; `the-atlas-of-windows.md` §2; `world-seams.md` §2.2/§2.3; `the-map.md` §1/§3/§3.1; `the-language.md` §2; `the-pilgrim.md` §2.1; `the-flood.md` §2; `energy-harnessing.md` §2; `the-fallow.md` §1–§3; `field-archaeology.md` §2 | the named land — the-name's scope dial taken at landscape scale; the mountain / river / region; the honest decay (the course-anchor break, the boundary re-bind, the mined-away mountain's spent strata); **no minted navigation (the star-read and beacon are landed; steering by a named read is [design]; the cap holds)** | **closed two-way** (fix 32); a reading over the canvas of the landed map/observatory reads — **matches**; a landform-name informs and holds, never mints |
|| `the-witness.md` ↔ `signature-predator.md` §1.1/§2.2; `the-blight.md` §2; `the-scavenger.md` §2.2; `the-commensal.md` §2.2/§3; `the-mirror-creature.md` §2; `reason-field.md` §2.1/§2.2/§3.1/§6a; `the-feral-instrument.md` §1/§2.2/§7; `the-story.md` §2/§3.3; `the-reading-ahead.md` §3; `the-observatory.md` §2/§2.1; `the-silence.md` §2/§3/§6a; `field-hazards.md` §1/§5.1/§5.3 | the field's own eye — the stranger-object layer's seventh face, first non-face; the four absences (does not hunt / turn / feed / hold / echo) compose the only neutral; not a sign (not the story's omen), not a portent, not a danger (no row), not a gift | **closed two-way** (fix 32); a pure consumer of the publish inside the ≈ 1–6 ms/tick sample budget, holds no patch, adds no entity — **matches** |

**Wave-37 closures (pass 22 / fix 33): the lock, the commons-tithe, the marsh,
and the husbander all land two-way on the compacts / economy / water / practice
sources; the waves 28–37 audit is now complete (thirty-three genuine audit rows,
each written only after its edges were grep-verified).**

|| Wave-37 re-point | What it closes | Status |
|---|---|---|---|
|| `the-lock.md` ↔ `the-oath.md` §1/§3/open-Q4; `the-treaty.md` §1/§2.4/§4; `the-rite-of-passage.md` §2.3/§3.2; `the-name.md` §1/§2/§6e; `seed-garden.md` §3/§4.2/§3.3; `the-exile.md` §2/§4/§6d; `house-that-steers.md` §1.1/§3.2/§3.4/§5b; `the-inheritance.md` §1/§2/§2.4/§8; `energy-harnessing.md` §6 | the permanent-hold — a binding deliberately made irreversible; the vow's severability answered in the negative; a treaty permanent while held, a lock permanent full stop; the durable-mistake cost (the no-amnesty, forward); the permanence's outliving | **closed two-way** (fix 33); the lock's no-free-energy cap held (converts nothing, never a gain, never a mint) — **matches** |
|| `the-commons-tithe.md` ↔ `shared-ledger.md` §1.2/§2/§5/§6d/§6c; `field-npc-ai.md` §3.1/§3.2/§3.3; `house-that-steers.md` §1/§2.2; `the-observatory.md` §1/§2; `the-harbor.md` §2b/§2c/§3/§4; `the-school.md` §2.2/§3; `the-market.md` §2/§2.3; `the-census.md` §2.1/§2.2; `the-window-pulse.md` §2/§3; `the-exile.md` §4; `the-gift.md` §2.1/§3.1/§6d | the funded commons — the voluntary-but-expected contribution, the commons' price; the op-record booked toward the commons (`{member, op, worldPos, rung, magnitude, sustain}`, schema §2.1 verbatim); the active tither, the healthmeter's funding; the booked warm (the gift's inverse) | **closed two-way** (fix 33); the tithe's no-free-energy cap held (converts nothing, never mints) — **matches** |
|| `the-marsh.md` ↔ `the-sea.md` §2b/§2a/§3/§4/§5b; `the-swim.md` §2a/§2b/§5b; `signature-predator.md` §1/§1.2/§2/§3/§7e/§8; `life-signal.md` §3/§2/§6b; `the-vigil.md` §3/§5e; `the-walk.md` §2c/§4b; `field-emergent-ecology.md` §2.2/§4.2/§6b; `energy-harnessing.md` §2/§6; `the-sea-floor.md` §2a/§2b | the tessellated q — the honest hiding surface, the sea's shallow textured bound; the trail-read's honest failure (the pattern blurs into the texture); the symmetric hiding (covers the predator too); the absorbed wake | **closed two-way** (fix 33); the marsh's q-patchiness holds the cap (a marsh provides nothing, no stealth-yield) — **matches** |
|| `the-husbander.md` ↔ `the-walk.md` §2/§3/§4a/§4c/§4d; `the-vigil.md` §1/§3/§5b; `the-working-song.md` §1/§2.1; `farm-that-feeds.md` §2/§4/§6; `the-commensal.md` §2/§3/§5b; `the-blight.md` §2/§3/§4.2/§5e; `the-scar-lifecycle.md` §2.1/§2.2; `the-cold.md` §2/§3/§6b; `energy-harnessing.md` §2/§6; `the-gift.md` §1/§2/§6d | the practice — the corpus's third practice, the wild's watch, the honest return, the wild's staying; the walk's craft turned from crossing to tending; the early clearing; the thin-season's shed; the shed as a gift to the wild | **closed two-way** (fix 33); the husbander's shed holds the cap (the `(1−q)` waste is spent, never a harvest, never a mint) — **matches** |

**Wave-38 closures (pass 23 / fix 34): the guardian, the archive, and the
granary all land two-way on the keeping / record / store sources; the waves 28–38
audit is now complete (thirty-six genuine audit rows, each written only after its
edges were grep-verified).**

|| Wave-38 re-point | What it closes | Status |
|---|---|---|---|
|| `the-guardian.md` ↔ `the-landform-name.md` §2/§4/§5a; `the-name.md` §1/§2/§6d/§7; `the-commensal.md` §2/§3/§5c/d/e; `the-threshold.md` §1/§2.2/§6c/§6d; `the-blight.md` §2/§6e; `signature-predator.md` §1/§2/§4.4/§7e; `the-witness.md` §1/§2/§7; `life-signal.md` §3/§3.1/§6a/b/§6d; `the-mirror-creature.md` §2/§5c/d/e; `field-emergent-ecology.md` §2.2/§4.2/§6b/§5.3; `the-cave.md` §4/§5d | the keeping — the bound keeper, the territorial order-side made permanent; the named place made bound, the boundary's keeper, the hunter's refuser; a Guardian is the witness's keeping (the warden-twin); the distinct face (bound to a place, not a person) | **closed two-way** (fix 34); the guardian's binding holds the cap (converts nothing, never a mint) — **matches** |
|| `the-archive.md` ↔ `shared-ledger.md` §1.2/§1.3/§6c/§6d; `schema-that-settles.md` §2/§2.1/§2.2/§5; `the-stratum-read.md` §1/§2/§2.4/§3/§5e; `the-chronicle.md` §1/§3.3/§5/§6d/§6e; `the-memory-palace.md` §2/§4/§6d/§7; `the-name.md` §1/§3.3/§6d/§7/§4; `field-archaeology.md` §2/§1.2/§6b/§5.3; `the-language.md` §2/§5; `energy-harnessing.md` §2/§4.1/§4.4/§6; `the-census.md` §2; `the-dispute.md` §2.1/§6d | the everything — the complete record held raw, the raw's truth; the burden of the raw, the record the residue is the shadow of; the raw ground of the dispute (the claim checked against the raw, not a shaped story) | **closed two-way** (fix 34); the archive's op-record rides schema §2.1 verbatim; the Archive is a store, never a mint — **matches** |
|| `the-granary.md` ↔ `farm-that-feeds.md` §2/§4/§5/§6/§7; `the-tool.md` §2/§3/§4d; `seed-garden.md` §3/§2.1/§7; `the-memory-palace.md` §2/§3/§4/§6d; `the-market.md` §1/§2.1/§2.2/§6d; `the-cold.md` §2/§3/§6e; `the-fallow.md` §2a/§5d; `energy-harnessing.md` §2/§4.4/§6; `house-that-steers.md` §1/§2.2/§5d/§5b; `schema-that-settles.md` §2.1/§2.2/§3; `shared-ledger.md` §1.2; `the-census.md` §2.1/§6e; `the-window-pulse.md` §2/§6e | the store — the honest buffer, the bleed held through the thin; the yield held, the plenty-side twin, the store of the circulated, the thin-season's buffer, the pulse's material half | **closed two-way** (fix 34); the granary's deposits/draws book on the settled record; the store's bleed holds the cap (a granary converts nothing) — **matches** |

**Wave-39 closures (pass 24 / fix 35): the wind, the season-change, the cart, and
the breath all land two-way on the air / calendar / movement / body sources; the
waves 28–39 audit is now complete (forty genuine audit rows, each written only
after its edges were grep-verified).**

|| Wave-39 re-point | What it closes | Status |
|---|---|---|---|
|| `the-wind.md` ↔ `field-hazards.md` §2/§5.1/§5.3; `atmosphere-orbits-auroras.md` §1.3/§1.5/§2.2/§6/§2.4; `the-zenith.md` §1/§2; `weather-not-storm.md` §2/§3/§6; `coherence-highway.md` §1/§1.1/§6b/§6d; `the-walk.md` §2/§2a/§4b/§4d; `the-blight.md` §2/§3/§6e; `energy-harnessing.md` §2/§2.2/§1.7/§6; `the-marsh.md` §2/§3; `signature-predator.md` §1.2 | the flow, the carry, the cost-and-aid — the air's own field-velocity made a read; the flow-face of the storm, the tailwind at your back, the spore-carrier, the signature-carrier; the descent's wind at your back | **closed two-way** (fix 35); the wind's carry holds the cap (a wind provides nothing, never farmable) — **matches** |
|| `the-season-change.md` ↔ `tide-of-the-attractor.md` §2/§5a/§1.2/§5d; `the-window-year.md` §2/§3/§5a/§5b; `the-dawn.md` §1/§2/§5; `the-drift-road.md` §3.3/§3.4/§4d; `atmosphere-orbits-auroras.md` §2/§4/§3.3/§3.4; `farm-that-feeds.md` §5/§2.2; `house-that-steers.md` §2.2/§3.4/§5d; `patient-field.md` §3.3/§5b; `the-cold.md` §2/§3/§5.3; `energy-harnessing.md` §2/§6; `the-window-pulse.md` §2.1/§6e | the crossing, the least-legible moment, the branch's turn — the field's actual shift the calendar approximates; the seasonal sibling of the dawn, the one-way turn toward the still, the muddy-instrument read | **closed two-way** (fix 35); a turn converts nothing (never a gain) — **matches** |
|| `the-cart.md` ↔ `coherence-highway.md` §1/§1.2/§4/§6b/§6c/§6d; `the-walk.md` §2/§2a/§3/§4a/§4c; `the-granary.md` §2.1/§3/§4/§5d; `the-market.md` §1/§2/§2.2/§6d; `the-tool.md` §2b/§3/§4b; `the-burden.md` §1/§2/§4; `energy-harnessing.md` §1.1/§4.1/§2/§6; `house-that-steers.md` §1/§2.2/§5d; `schema-that-settles.md` §2.1/§2.2/§2.3/§3 | the ride, the load-and-gradient trade, the honest book — the wheeled vehicle that rides the route and carries the store; the walk's loaded twin; **the cart's camp-freight face is NOT forced (open-Q6 honest negative: `the-camp.md` absent on disk, `[assumption]` not filled)** | **closed two-way** (fix 35); the cart's load books on the settled op-record verbatim; a cart converts nothing — **matches** |
|| `the-breath.md` ↔ `deep-field-diving.md` §1/§2/§2.2/§2.3/§3.1/§4/§7a/§7d; `the-cave.md` §3/§4/§5d; `the-sea-floor.md` §2a/§2c/§5d; `the-swim.md` §2a/§2b/§5d; `the-burden.md` §1/§2b/§4/§6a; `the-tool.md` §2a/§2c/§4d; `player-remains.md` §1/§1.2/§2.3/§5e; `life-signal.md` §1/§3/§3.2/§6b/§6d; `energy-harnessing.md` §2/§6; `sleep.md` §2b/§3/§6d | the reservoir, the hollow's breath, the lock's failure — the body-scale take of the descent; the priced descent (every rung deeper costs lungs of held coherence), the stroke's shallow breath, the refill in sleep, the coherence-failure death | **closed two-way** (fix 35); the breath holds the cap (a breath converts nothing; the reservoir is a store, never a mint) — **matches** |

**Wave-40 closures (pass 25 / fix 36): the herald, the toll, and the compost all
land two-way on the voice / door / spent-matter sources; the waves 28–40 audit is
now complete (forty-three genuine audit rows, each written only after its edges
were grep-verified).**

|| Wave-40 re-point | What it closes | Status |
|---|---|---|---|
|| `the-herald.md` ↔ `the-witness.md` §1/§2/§5b/§7#2/#4; `the-reading-ahead.md` §1/§2.2/§2.3/§7c/§7d/§7a; `the-bell.md` §3/§5a/§6c/d/e; `the-guardian.md` §1/§3/§5b; `weather-not-storm.md` §2/§3; `the-season-change.md` §1/§2.1/§3.1/§5b; `fate-of-a-window.md` §1/§6c/§6e; `field-emergent-ecology.md` §2.2/§4.2/§6b/§5.3/§1.4; `life-signal.md` §3/§3.1/§6d; `signature-predator.md` §2/§3/§7e; `the-mirror-creature.md` §2/§5c/d/e; `the-feral-instrument.md` §1 | the voice, the announced augury, the turned-forward order — the field's own voice, the loud twin of the watched presence, a pure consumer of the publish, never a farm | **closed two-way** (fix 36); the herald provides nothing, never farms (the witness's loud twin; holds no patch, adds no entity to the ≈2,000 cap) — **matches** |
|| `the-toll.md` ↔ `the-commons-tithe.md` §1/§3/§2.1/§5a; `the-harbor.md` §2b/§2c/§3/§4/§5a; `the-threshold.md` §1/§2.2/§3; `the-treaty.md` §1/§2/§2.3/§2.2/§5d; `window-guests.md` §1/§2/§3/§6b; `shared-ledger.md` §1.2/§2/§6d/§6c; `the-market.md` §1/§2/§2.3/§3/§6d; `coherence-highway.md` §1/§4/§5.2/§6d; `house-that-steers.md` §1/§2.2/§3/§5d; `schema-that-settles.md` §2.1/§2.3/§3; `the-dispute.md` §2/§3.1/§3.2; `the-census.md` §2.1/§2.4/§6d | the border's charge, the held door's price, the visitor's trust-by-law — the outside's entry at the marked crossing, booked on the ledger, never a mint | **closed two-way** (fix 36); the toll's doors/trust-by-law cite `window-guests.md` §3/§6b + `schema-that-settles.md` §2.1 op-record verbatim; the toll holds the cap (never mints, never farms) — **matches** |
|| `the-compost.md` ↔ `the-fallow.md` §2/§2b/§1/§5d; `the-tool.md` §2b/§3/§4b/§4d; `the-granary.md` §2.1/§6/§5d; `farm-that-feeds.md` §2/§4/§5; `the-scavenger.md` §2.1/§2.2/§5d; `patient-field.md` §3.3/§1/§5; `material-regimes.md` §3/§4; `energy-harnessing.md` §2/§6; `the-marsh.md` §3/§2; `the-husbander.md` §1/§3/§6; `schema-that-settles.md` §2.1/§2.3/§6d | the spent matter's re-turn, the heap, the time-and-lock — the built sibling of the wild glean, returns order at a loss, never a mint | **closed two-way** (fix 36); the compost's heap/time-and-lock holds the cap (`output ≤ φ⁻¹·input`, no-free-energy §6 `energy-harnessing.md`) — **matches** |

**Count (current, pass-25 completion):** at the pass-25 count check designs/ =
144 files and README = 144 rows — **144 indexed / 144 on-disk, in exact lock-step,
zero ghost rows, zero unindexed** (every README row resolves to an on-disk file; the
director has indexed the entire landed corpus, including the wave-45 batch). **The
audit is now complete through wave-40** — the wave-28/29/30/31 set (fix 26/27), the
wave-32 set (fix 28), the wave-33 set (fix 29), the wave-34 set (fix 30), the
wave-35 set (fix 31), the wave-36 set (fix 32), the wave-37 set (fix 33), the
wave-38 set (fix 34), the wave-39 set (fix 35), and the wave-40 set (fix 36) are
all audited two-way. Waves 41–45 (the-carry, the-climb, the-gatekeeper, the-
causeway; the-rain, the-spring, the-mimic; the-stilling, the-roost, the-dive, the-
between; the-beacon, the-shout, the-moth; the-archivist, the-desert, the-quarry,
the-shepherd) are on disk and indexed but must NOT be audited within passes 22–25;
their passes remain future work — the count and the *audit* remain separate.

**Wave-41 closures (pass 26 / fix 37): the carry, the climb, the gatekeeper, and
the causeway all land two-way on the carried-load / ascent / office / raised-way
sources — and the climb↔carry two-way write-race is landed (both flagged each
other's absence honestly; once both were on disk the flags became real pointers);
the waves 28–41 audit is now complete (forty-seven genuine audit rows, each
written only after its edges were grep-verified).**

|| Wave-41 re-point | What it closes | Status |
|---|---|---|---|
|| `the-carry.md` ↔ `the-burden.md` §1/§2/§2b/§4; `the-walk.md` §2/§2a/§2b/§3/§4a/§4c; `the-swim.md` §2a/§4/§5c/d/e; `the-cart.md` §1/§2/§3/§5a/§7; `the-tool.md` §2a/§3/§4d; `the-lantern.md` §1/§2/§1.4; `life-signal.md` §3/§3.3/§6 N2; `signature-predator.md` §2/§8/§7e; `the-granary.md` §2/§6/§7; `schema-that-settles.md` §2.1/§2.2/§2.3; `energy-harnessing.md` §2/§6 | the pack, the carried matter, the honest weight on every movement — the corpus's first inventory-primitive, a field-read weight never a slot, legible to the field (a small extra signature a Coda could find) | **closed two-way** (fix 37); the pack holds the cap (a carry converts nothing, no pack that yields; the heavier live-lock is a cost, never a gain) — **matches** |
|| `the-climb.md` ↔ `the-fall.md` §1/§2/§4.2/§5a/§5c/§5d; `the-walk.md` §2/§2a/§3/§4a/§4d; `the-zenith.md` §1/§2b/§4b; `material-regimes.md` §4; `energy-harnessing.md` §1.1/§2/§6; `the-burden.md` §1/§2/§6a; `coherence-highway.md` §4; `player-remains.md` §1/§4; `field-hazards.md` §4/§5.1; `life-signal.md` §3 | the ascent, the handholds-as-a-read, the gradient's cost — the fall's controlled-inverse, *you* working the gradient, the vertical's missing upward primitive | **closed two-way** (fix 37); a climb converts nothing harder at the vertical; **the climb↔carry race is landed (climb's 'NOT ON DISK' cross-ref → real `the-carry.md` pointer; the-carry's three absence-notes → landed-arrival)** — **matches** |
|| `the-gatekeeper.md` ↔ `the-threshold.md` §1/§2.2/§3/§6; `the-harbor.md` §2b/§2c/§3/§4/§5b; `the-guardian.md` §1/§2.3/§3/§5d/e/§7; `window-guests.md` §1/§2/§3/§4.1/§6b; `life-signal.md` §3/§3.3/§4/§6a/§6d; `signature-predator.md` §2/§3/§7d/§8/§7e; `the-blight.md` §2/§6e/§5e/§7; `the-census.md` §2/§2.1/§2.4/§7; `shared-ledger.md` §1.2/§6c/§6d/§6e; `the-dispute.md` §2/§4/§6c/d/e; `the-observatory.md` §1/§2/§3/§6e | the office, the human twin, the field-true judgment — who passes the held door, read to resolution by the field's read over the person's | **closed two-way** (fix 37); the office holds the cap (a gatekeeper never mints, never farms) — **matches** |
|| `the-causeway.md` ↔ `the-marsh.md` §2/§3/§4/§6c/§7/§8; `the-walk.md` §2/§2a/§2c/§3/§4c/d/e; `the-cart.md` §2/§3/§4/§7; `house-that-steers.md` §1/§1.1/§2/§3/§3.4/§5d; `energy-harnessing.md` §2/§4.1/§4.4/§6; `the-threshold.md` §1/§2.2/§4/§5d/§6b; `life-signal.md` §3/§6d; `signature-predator.md` §1/§1.2/§2/§7e/§8; `coherence-highway.md` §4/§4.2/§6b/§6d | the raised way, the clean crossing above the hiding, the honest trade and the swallow — the deck that breaks the marsh's symmetric hiding for the raised | **closed two-way** (fix 37); a causeway converts nothing (`output ≤ φ⁻¹·input`, the deck's standing draw held) — **matches** |

**Count (current, pass-26 completion):** at the pass-26 count check designs/ =
152 files and README = 147 rows — **147 indexed / 152 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **Five on-disk docs have no README
row yet** — corpus-map, the-ford, the-migration, the-spring-caretaker, the-wage —
the next landing batch, unindexed new arrivals, not ghosts. **The audit is now
complete through wave-41** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set
(fix 28), the wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix
31), the wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34),
the wave-39 set (fix 35), the wave-40 set (fix 36), and the wave-41 set (fix 37)
are all audited two-way. Waves 42–46 (the-rain, the-spring, the-mimic; the-stilling,
the-roost, the-dive, the-between; the-beacon, the-shout, the-moth; the-archivist,
the-desert, the-quarry, the-shepherd, and the five wave-46+ arrivals) are on disk
and indexed but must NOT be audited within passes 22–26; their passes remain future
work — the count and the *audit* remain separate.

**Wave-42 closures (pass 27 / fix 38): the rain, the spring, and the mimic all
land two-way on the weather / well / deception sources — and the rain↔spring
two-way write-race is landed (both flagged each other's absence honestly; once
both were on disk the flags became real pointers); the waves 28–42 audit is now
complete (fifty genuine audit rows, each written only after its edges were
grep-verified).**

|| Wave-42 re-point | What it closes | Status |
|---|---|---|---|
|| `the-rain.md` ↔ `the-flood.md` §2/§3/§4.1/§6(b)/§6(e); `farm-that-feeds.md` §2/§5/§3/§4; `the-wind.md` §1/§3/§5(b)/§5(c)/§5(d)/§5(e); `the-marsh.md` §3/§8; `life-signal.md` §1/§3/§3.2/§6b; `the-fallow.md` §1/§3; `weather-not-storm.md` §2; `the-sea.md` §2c/§4/§5b; `energy-harnessing.md` §2/§6; `field-hazards.md` §5.1 | the gentle fall, the nourishing-but-wet, the flood's beginning — the same source at a yield the field can take, the fallow's season's water, the clearest weather verdict | **closed two-way** (fix 38); the rain gives back at the field's own yield, never a mint; **the rain↔spring race is landed (rain's fill-of-spring note → landed; spring's four absence-notes → landed arrival)** — **matches** |
|| `the-spring.md` ↔ `the-fallow.md` §1/§2/§2a/§5b/§6d; `resonance-seeds.md` §1/§2/§6a; `seed-garden.md` §2/§3/§4.2; `field-emergent-ecology.md` §2.2/§4.2/§1.4; `the-granary.md` §2/§3/§5d/§7; `the-carry.md` §2/§4b/§5c/d/e; `the-landform-name.md` §1/§2/§5d/§5e; `the-guardian.md` §1/§3/§5d/§7; `life-signal.md` §3/§6c/§6d; `signature-predator.md` §2/§7e; `energy-harnessing.md` §2/§1.7/§6/§7 Q1; `material-regimes.md` §3/§4 | the well, the point of fame, the drawn order — the fallow's full twin at the fixed place the order returns to, the field's own bright maintained-live source | **closed two-way** (fix 38); a spring provides nothing beyond its own welling (never a mint); the point of fame is a cost, never a farm — **matches** |
|| `the-mimic.md` ↔ `the-mirror-creature.md` §1/§2/§2.2/§3.2/§4.1/§5b-2/§7; `signature-predator.md` §1/§2/§2.2/§3/§7e/§8; `window-guests.md` §1/§2/§3/§6b; `life-signal.md` §1/§3/§3.1/§3.2/§6b; `shared-ledger.md` §1.2/§6c/§3.3/§6e/§6b; `the-gatekeeper.md` §1/§2/§2.1/§5c/d/e; `the-commensal.md` §1/§4/§5c/d/e; `field-emergent-ecology.md` §2.2/§6b/§3.1/§4.1/§1.4; `the-feral-instrument.md` §1/§5d/e; `the-dispute.md` §2/§2.1; `the-witness.md` §1/§2/§5c/d/e; `energy-harnessing.md` §2/§6 | the worn shape, the drift, the provenance read that catches it — the borrowed line that sheds at the field's judgment, the reason a settlement keeps a gatekeeper | **closed two-way** (fix 38); a mimic converts nothing (the borrowed shape spent never a gain) — **matches** |

**Count (current, pass-27 completion):** at the pass-27 count check designs/ =
152 files and README = 151 rows — **151 indexed / 152 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **One on-disk doc has no README row
yet** — corpus-map — an unindexed new arrival, not a ghost (the director has
indexed the rest of the wave-45/46 batch: the-ford, the-migration, the-
spring-caretaker, the-wage all landed). **The audit is now complete through wave-42**
— the wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the wave-33 set
(fix 29), the wave-34 set (fix 30), the wave-35 set (fix 31), the wave-36 set (fix
32), the wave-37 set (fix 33), the wave-38 set (fix 34), the wave-39 set (fix 35),
the wave-40 set (fix 36), the wave-41 set (fix 37), and the wave-42 set (fix 38)
are all audited two-way. Waves 43–46 (the-stilling, the-roost, the-dive, the-
between; the-beacon, the-shout, the-moth; the-archivist, the-desert, the-quarry,
the-shepherd, and the remaining wave-46+ arrivals) are on disk and indexed but must
NOT be audited within passes 22–27; their passes remain future work — the count and
the *audit* remain separate.

**Wave-43 closures (pass 28 / fix 39): the stilling, the roost, the dive, and the
between all land two-way on the inner-practice / home / descent / dark sources; the
waves 28–43 audit is now complete (fifty-four genuine audit rows, each written only
after its edges were grep-verified).**

|| Wave-43 re-point | What it closes | Status |
|---|---|---|---|
|| `the-stilling.md` ↔ `the-vigil.md` §1/§3/§5b/§5a/§5d; `the-working-song.md` §1; `the-stillness.md` §1/§2/§4.3/§6b/§6c; `life-signal.md` §1/§3/§3.2/§6a/b/§6c/§6d; `energy-harnessing.md` §2/§6; `signature-predator.md` §2/§7e/§8; `the-silence.md` §1/§2; `the-fall.md` §2; `sleep.md` §1/§2b/§2.1 | the inner hold, the practice-not-power, the drift — the maintenance-axis hold applied to oneself, the reader turned inward, never a stealth mechanic | **closed two-way** (fix 39); a stilling converts nothing (the voluntary hold spent, never free) — **matches** |
|| `the-roost.md` ↔ `field-emergent-ecology.md` §4.2/§2.2/§6b/§1.4/§3.1/§5.3; `signature-predator.md` §1/§2/§7c/§2.3/§7e; `the-scavenger.md` §2.2/§2.1/§4/§5b/§5c/d/e; `the-commensal.md` §2/§3/§2.2/§7; `the-guardian.md` §1/§3/§4/§5e; `the-feral-instrument.md` §2.2/§5d/§5e/§7; `the-mirror-creature.md` §2.3/§5; `field-archaeology.md` §2/§3.2/§7/§1.2; `life-signal.md` §3/§3.1/§6d; `energy-harnessing.md` §2/§6; `field-hazards.md` §5.1/§1/§5.3 | the homes, the legible vulnerability, the wild's own order — where a run settles, the keep made home, the presented reading never a spawned den | **closed two-way** (fix 39); a roost provides nothing (a nest provides nothing) — **matches** |
|| `the-dive.md` ↔ `deep-field-diving.md` §2.1/§2.2/§2.3/§3.1/§7a/§7d; `the-fall.md` §1/§2/§4.3/§5c/§5d; `the-climb.md` §1/§2/§2.1/§3/§4.2/§5a; `the-breath.md` §1/§2/§3/§4.1/§5b/§5d; `the-swim.md` §2a/§2b/§4/§5d; `the-cave.md` §3/§4/§5d; `the-burden.md` §1/§2/§6a; `player-remains.md` §1/§4/§2.3/§2.4; `energy-harnessing.md` §1.1/§2/§4.4/§6; `the-sea-floor.md` §1/§2c; `the-stratum-read.md` §2 | the descent, the deep's own work, the commitment — the fall's controlled-inverse, the vertical's missing willed down-movement, the descent's own survey | **closed two-way** (fix 39); a dive converts nothing, never a mint (the honest risk is the lock's failure at depth) — **matches** |
|| `the-between.md` ↔ `the-interstitial.md` §1/§2/§3/§4/§5; `world-seams.md` §1.2/§2.1/§2.2/§2.3/§4.3/§6/§7; `the-harbor.md` §1/§2/§3/§4/§5b; `the-atlas-of-windows.md` §1/§2/§4b/§4d; `window-guests.md` §1/§2/§3/§6b; `the-treaty.md` §1/§2/§4/§6d; `the-witness.md` §1/§2/§5b; `the-herald.md` §1/§2/§5; `pocket-cosmos.md` §1.2/§1.3/§4.1; `async-field-domain.md` §1–2/§7 Q1; `energy-harnessing.md` §2/§6; `deep-field-diving.md` §1/§6; `the-pilgrim.md` §2/§3/§5d | the lawful dark, not another world, the edge — the mixture's empty remainder, the between's three characters (thin / ringing / lawful), the dark is never a gain | **closed two-way** (fix 39); the between provides nothing (the dark never a gain); its laws cite `the-interstitial.md` §2 verbatim; the cartography honestly partial, never a map — **matches** |

**Count (current, pass-28 completion):** at the pass-28 count check designs/ =
154 files and README = 151 rows — **151 indexed / 154 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **Three on-disk docs have no README
row yet** — corpus-map, the-estuary, the-midwife — the next landing batch, unindexed
new arrivals, not ghosts. **The audit is now complete through wave-43** — the
wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the wave-33 set (fix
29), the wave-34 set (fix 30), the wave-35 set (fix 31), the wave-36 set (fix 32),
the wave-37 set (fix 33), the wave-38 set (fix 34), the wave-39 set (fix 35), the
wave-40 set (fix 36), the wave-41 set (fix 37), the wave-42 set (fix 38), and the
wave-43 set (fix 39) are all audited two-way. Waves 44–48 (the-beacon, the-shout,
the-moth; the-archivist, the-desert, the-quarry, the-shepherd, and the wave-47+
arrivals) are on disk and indexed but must NOT be audited within passes 22–28;
their passes remain future work — the count and the *audit* remain separate.

**Wave-44 closures (pass 29 / fix 40): the beacon, the shout, and the moth all land
two-way on the mark / call / covet sources — and the beacon↔moth two-way special
item is landed (open-Q5's light-drawn being is the Moth); the waves 28–44 audit is
now complete (fifty-seven genuine audit rows, each written only after its edges
were grep-verified).**

|| Wave-44 re-point | What it closes | Status |
|---|---|---|---|
|| `the-beacon.md` ↔ `the-lantern.md` §1/§2/§4/§5b/§5d/§5e; `the-bell.md` §1/§3; `the-observatory.md` §1/§2/§2.1; `the-harbor.md` §2b/§3/§6/§5d; `the-threshold.md` §1/§6/§5d/§5e; `the-causeway.md` §1/§3/§8; `house-that-steers.md` §1/§1.1/§3/§5b/§5d; `energy-harnessing.md` §2/§4.4/§5.4/§6; `signature-predator.md` §2/§7e/§8; `the-walk.md` §1/§2/§4d; `world-seams.md` §2.2; `the-spring.md` §3/§5d | the mark, the double-edged mark, the held light — the standing burn at the settlement's deliberate edge, the room un-wrapped into a standing hold | **closed two-way** (fix 40); a beacon converts nothing, no mark that yields; **the beacon↔moth race is landed (open-Q5's *called* → the Moth)** — **matches** |
|| `the-shout.md` ↔ `the-working-song.md` §1/§2; `field-music.md` §1/§6; `the-bell.md` §1/§5a/§6c/d/e/open-Q5; `life-signal.md` §3/§3.3/§6a/b/§6c/d; `signature-predator.md` §2/§7e/§8; `the-herald.md` §1/§2/§5; `player-remains.md` §1/§4/§5e/§6; `the-stilling.md` §1/§4/§5a/b/§5c/d/e; `the-vigil.md` §3/§5b; `energy-harnessing.md` §2/§6; `the-silence.md` §1/§3.2; `the-census.md` §2/§6d | the call, the presence-as-act, the honest cost — one untrained broadcast loud enough to be found, the body's own alarm, the census's loud call | **closed two-way** (fix 40); a shout never mints (the projection spent at its broadcast; never a shout-mint) — **matches** |
|| `the-moth.md` ↔ `the-lantern.md` §1/§2/§5d; `the-beacon.md` §2/§3/§5b/§6 + open-Q5; `the-spring.md` §2.1/§3/§5/§6/§5d; `the-observatory.md` §1/§2/§6d; `window-guests.md` §1/§2; `signature-predator.md` §1/§2.2/§3/§7e/§8; `the-scavenger.md` §2.2/§4/§5c/d/e; `the-commensal.md` §2/§3/§5c/d/e; `life-signal.md` §1/§3/§3.1/§6a/§6b/§6c; `field-emergent-ecology.md` §2.2/§6b/§4.2/§1.4; `energy-harnessing.md` §2/§6/§5.4; `the-mirror-creature.md` §1/§2; `the-witness.md` §1/§2 | the want, the brightness-as-both, the peaceable-lust — the drawn-in wild twin coveting the standing burn, the Beacon's *called* given its coveter | **closed two-way** (fix 40); a moth converts nothing (`output ≤ φ⁻¹·input` + `E_waste=(1−q)·E_throughput`); **the beacon↔moth special (moth's open-Q1 deferred pointer, now resolved in-doc)** — **matches** |

**Count (current, pass-29 completion):** at the pass-29 count check designs/ =
155 files and README = 154 rows — **154 indexed / 155 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **One on-disk doc has no README row
yet** — corpus-map — an unindexed new arrival, not a ghost (the director has indexed
the-estuary and the-midwife). **The audit is now complete through wave-44** — the
wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the wave-33 set (fix
29), the wave-34 set (fix 30), the wave-35 set (fix 31), the wave-36 set (fix 32),
the wave-37 set (fix 33), the wave-38 set (fix 34), the wave-39 set (fix 35), the
wave-40 set (fix 36), the wave-41 set (fix 37), the wave-42 set (fix 38), the
wave-43 set (fix 39), and the wave-44 set (fix 40) are all audited two-way. Waves
45–48 (the-archivist, the-desert, the-quarry, the-shepherd, and the remaining
wave-47+ arrivals) are on disk and indexed but must NOT be audited within passes
22–29; their passes remain future work — the count and the *audit* remain separate.

**Wave-45 closures (pass 30 / fix 41): the quarry, the shepherd, the archivist, and
the desert all land two-way on the cut / gathering / raw-record / thin-regime
sources; the waves 28–45 audit is now complete (sixty-one genuine audit rows, each
written only after its edges were grep-verified).**

|| Wave-45 re-point | What it closes | Status |
|---|---|---|---|
|| `the-quarry.md` ↔ `the-fallow.md` §1/§2a/§3/§5(b)/§5d; `the-tool.md` §2a/§2b/§3/§4b/§4d; `the-stratum-read.md` §1/§2/§3/§5(b)/§5(d); `the-scar-lifecycle.md` §2.1/§2.2/§2.3/§5b/§5d; `the-bedrock.md` §1/§2/§2b/§3/§5d/§6; `the-cave.md` §2a/§2b/§4/§5d; `material-regimes.md` §2/§4/§3/§7; `the-compost.md` §1/§4/§2; `energy-harnessing.md` §2/§2.5/§3/§6; `schema-that-settles.md` §2.1/§2.3/§3; `field-archaeology.md` §1.2/§2/§2.3/§3.2/§5.3; `the-granary.md` §2/§5d/§6 | the cut, the scar-and-yield, the honest economy — the one-way run-out made a place, the deep-rung take, the spent face turned back at a loss | **closed two-way** (fix 41); a quarry converts nothing; the take books on the settled op-record verbatim — **matches** |
|| `the-shepherd.md` ↔ `the-roost.md` §1/§3/§4/§5c/d/e; `the-scavenger.md` §2.2/§1/§4/§5b/§5c/d/e; `the-moth.md` §3.2/§1/§5b-1/§5d; `the-commensal.md` §2/§3/§5c/d/e; `the-guardian.md` §1/§3/§5c/d/e; `field-emergent-ecology.md` §2.2/§6b/§4.2/§5.3/§6c/§1.4; `life-signal.md` §3/§3.1/§6a/b/§6d; `field-archaeology.md` §2/§3.2/§7/§1.2; `energy-harnessing.md` §2/§6; `the-witness.md` §1/§5c/d/e; `the-herald.md` §1/§2/§5 | the gathering, the field's own assembly, the honest no-reward — a being that moves and gathers, the crowd that assembles, never a place kept | **closed two-way** (fix 41); a shepherd provides nothing (the honest no-reward) — **matches** |
|| `the-archivist.md` ↔ `the-archive.md` §1/§3/§4/§2.4/§5/§6; `the-chronicle.md` §1/§3.3/§5/§6d; `the-memory-palace.md` §2/§3/§4/§6d; `the-gatekeeper.md` §1/§2/§4/§6; `the-school.md` §2/§2.2/§4/§6; `shared-ledger.md` §1.2/§6c/§6d/§6b/§6e; `schema-that-settles.md` §2/§2.1/§3/§6b; `the-stratum-read.md` §1/§2/§2.4/§6/§5e; `the-census.md` §2/§2.1/§7; `the-dispute.md` §2/§6c/§6d/§6e; `field-archaeology.md` §2/§1.2/§6b; `the-name.md` §1/§3.3/§6e/§6d | the office, the honest fallibility, the dispute's ground — the keeper of the raw un-shaped, the book's own single non-forgeable point, cannot corrupt the raw | **closed two-way** (fix 41); the archivist records, never mints (holds the settled op-record raw verbatim) — **matches** |
|| `the-desert.md` ↔ `field-hazards.md` §3/§6.2; `signature-predator.md` §1.2/§7c/§2; `the-between.md` §1/§3/§2a; `the-scavenger.md` §2.1/§2.2/§4; `the-roost.md` §2/§3/§4; `the-husbander.md` §2c/§4/§6(c); `the-spring.md` §2/§3/§4; `the-fallow.md` §2a/§1/§3/§6(c); `tide-of-the-attractor.md` §2/§5a/§5b; `farm-that-feeds.md` §2/§4/§5; `energy-harnessing.md` §2/§6/§7 Q1; `the-compost.md` §1/§4; `the-cold.md` §1/§2/§3 | the thin regime, not the between, the honest scarcity — a window living at the attractor's thin edge, the tide at its thinnest sustained, never the Coda's form-place | **closed two-way** (fix 41); a desert provides nothing beyond its own thin regime, no scarcity that yields; the desert is NOT the between — **matches** |

**Count (current, pass-30 completion):** at the pass-30 count check designs/ =
158 files and README = 154 rows — **154 indexed / 158 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **Four on-disk docs have no README
row yet** — corpus-map, the-blizzard, the-inn, the-understory — the next landing
batch, unindexed new arrivals, not ghosts. **The audit is now complete through
wave-45** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the
wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix 31), the
wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34), the
wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), and the
wave-45 set (fix 41) are all audited two-way. Waves 46–49 (the wave-46+ and wave-48+
arrivals) are on disk and indexed but must NOT be audited within passes 22–30; their
passes remain future work — the count and the *audit* remain separate.

**Wave-46 closures (pass 31 / fix 42): the broker, the smell, and the river all
land two-way on the carried-trade / air-form / liquid-regime sources; the waves
28–46 audit is now complete (sixty-four genuine audit rows per the closure tally
convention, each written only after its edges were grep-verified).**

|| Wave-46 re-point | What it closes | Status |
|---|---|---|---|
|| `the-broker.md` ↔ `the-market.md` §1/§2/§3/§6d/§6b/§4.1; `the-toll.md` §1/§3/§2/§4/§5b/d/e; `seed-garden.md` §2/§3/§4.2/§6b/§7; `the-atlas-of-windows.md` §1/§2/§3/§4b/§4d; `window-guests.md` §1/§2/§3/§6b/§6d; `the-between.md` §1/§3/§3a/§5d/§2c; `the-mimic.md` §1/§3/§4/§5b; `life-signal.md` §1/§3/§3.3/§6a/§6d/§6b; `signature-predator.md` §1/§2/§1.3/§7e/§8; `shared-ledger.md` §1.2/§2.1/§6c/§6d/§6e/§3.3; `field-emergent-ecology.md` §2.2; `energy-harnessing.md` §2/§6; `the-gatekeeper.md` §1/§2/§5c/d/e; `the-census.md` §2/§2.4/§6d | the between-carrier, the charged-then-welcomed, the rarity-bearing stranger that brings worth — the outside that pays to enter then trades as a guest line, verified on the maintenance axis | **closed two-way** (fix 42); the broker converts nothing, the trade is a transfer never a mint — **matches** |
|| `the-smell.md` ↔ `life-signal.md` §1/§3/§3.1/§6a/§6b/§6c/§6d; `the-wind.md` §1/§3/§5b/§5c/d/e; `the-blight.md` §2/§6e/§6c/d/e; `the-roost.md` §2/§3/§4/§5e; `the-spring.md` §3/§5c/d/e/§6; `the-mimic.md` §3/§5b-1/§5d/§5e; `the-marsh.md` §3/§8/§7c/d/e; `the-rain.md` §3/§5b/§5c/d/e; `farm-that-feeds.md` §2/§5; `player-remains.md` §1/§1.3/§5d; `energy-harnessing.md` §2/§6; `the-stilling.md` §2; `signature-predator.md` §1/§2/§7e/§8; `field-hazards.md` §5.1; `field-instruments.md` §2.1; `field-music.md` §1/§6 | the air-form read, the carrier's carry at the nose, the waste read at its air — you smell what is upwind, a blight's wrong odor read before it arrives | **closed two-way** (fix 42); a smell provides nothing (the scent is the field's own read, never a detector-mint) — **matches** |
|| `the-river.md` ↔ `the-sea.md` §2a/§2b/§2c/§5b/§5c/d/e; `coherence-highway.md` §1/§3.1/§4/§6b/§6c/§6d; `the-marsh.md` §2/§3/§5/§8; `the-desert.md` §2/§3; `farm-that-feeds.md` §2/§3/§4/§5; `the-cart.md` §2/§3/§4b/open-Q6; `the-swim.md` §2a/§2b/§5d; `the-dive.md` §1/§2; `the-flood.md` §2/§4.1; `the-rain.md` §2/§4; `the-threshold.md` §1/§2.2; `the-gatekeeper.md` §1/§2/§4; `the-toll.md` §2/§4; `energy-harnessing.md` §2/§6; `the-spring.md` §2/§3; `field-emergent-ecology.md` §2.2/§4.2 | the moving-conduit band, the grown-and-habitable, the flow-face of the liquid regime — the river where the dry land is thin the band is rich | **closed two-way** (fix 42); a river converts nothing (the current is never a mint) — **matches** |

**Count (current, pass-31 completion):** at the pass-31 count check designs/ =
185 files and README = 181 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **Four on-disk docs have no README
row yet** — corpus-map, the-crossroads, the-lightning, the-shrine — the next landing
batch, unindexed new arrivals, not ghosts. **The audit is now complete through
wave-46** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the
wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix 31), the
wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34), the
wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), and the wave-46 set (fix 42) are all audited two-way. Waves
47–57 (the wave-47+ through wave-56+ arrivals) are on disk and indexed but must NOT
be audited within passes 22–31; their passes remain future work — the count and the
*audit* remain separate.

**Wave-47 closures (pass 32 / fix 43): the wage, the spring-caretaker, and the
migration all land two-way on the book / keeping / collective-movement sources; the
waves 28–47 audit is now complete (sixty-seven genuine audit rows per the closure
tally convention, each written only after its edges were grep-verified).**

|| Wave-47 re-point | What it closes | Status |
|---|---|---|---|
|| `the-wage.md` ↔ `the-market.md` §1/§2.1/§2.3/§3/§6d/§6b; `the-apprenticeship.md` §1/§3.1/§2.2; `the-working-song.md` §1/§4/§5d; `the-commons-tithe.md` §1/§3/§2.1/§6d; `shared-ledger.md` §1.2/§2/§6d/§6c/§6b; `schema-that-settles.md` §2.1/§2.2/§2.3/§3/§6e; `the-gift.md` §1/§2.1/§2.3/§6d; `farm-that-feeds.md` §2/§3/§4/§7; `house-that-steers.md` §1/§2.2/§3/§5d; `the-census.md` §2.1/§2.2/§6d; `the-toll.md` §1/§3/§5d/§5c; `the-loan.md` §1/§2/§2.1; `the-oath.md` §2; `energy-harnessing.md` §2/§6; `the-observatory.md` §1 | the time-form of the booked exchange, the paid-in-order, the present-tensed coin for work done — the same booking pointed at a worker's day, an unpaid wage a false op the book will not hold | **closed two-way** (fix 43); the wage converts nothing, the transfer never a gain (books on the settled op-record verbatim) — **matches** |
|| `the-spring-caretaker.md` ↔ `the-spring.md` §2/§2.2/§3/§4/§5c/d/e; `the-guardian.md` §1/§3/§2.3/§5d/§7; `the-gatekeeper.md` §1/§2.1/§4/§5c/d/e; `the-rain.md` §3/§3.2/§5; `the-compost.md` §2/§3/§6d; `life-signal.md` §3/§3.3/§6b/§6c/§6d; `signature-predator.md` §2/§3/§7e; `the-desert.md` §2/§4/§5d; `the-fallow.md` §2a/§1/§3; `the-census.md` §2.1/§2.2/§7; `shared-ledger.md` §1.2/§6c/§6d/§6e; `schema-that-settles.md` §2.1/§2.3/§6d; `the-name.md` §1/§2; `energy-harnessing.md` §2/§6; `the-dispute.md` §2/§6d/§6e; `field-instruments.md` §2.1/§1.2 | the kept well, the office-twin, the read-before-depletion — the clearing of the silt that chokes the source's mouth, the well's fame weighed as a liability | **closed two-way** (fix 43); a caretaker converts nothing (the draw spent, the clearing real, never a mint) — **matches** |
|| `the-migration.md` ↔ `the-walk.md` §1/§2/§2c/§4a; `the-pilgrim.md` §2/§3; `world-seams.md` §2/§2.3/§3.2/§6; `field-emergent-ecology.md` §2.2/§4.2/§5.3/§6c/§6b/§1.4; `the-shepherd.md` §1/§2/§3/§5a/§5c/d/e; `the-exile.md` §1/§2/§4/§4.2; `window-guests.md` §1/§3/§6d; `the-blight.md` §2/§3; `the-flood.md` §2/§3/§6(b); `the-fallow.md` §2/§1/§5d/§6(c); `the-compost.md` §4/§5d; `the-herald.md` §1/§2/§4/§5c/d/e; `signature-predator.md` §1/§2/§1.2/§7e; `field-music.md` §2.4/§6; `energy-harnessing.md` §2/§6; `the-census.md` §2/§1; `life-signal.md` §3/§6d; `coherence-highway.md` §1/§6; `chunk-field-quantization.md` §1/§5; `field-instruments.md` §2.1 | the collective's movement, the exile named for many, the strip's driver, the moving window's chunk — the pilgrim's single slice made the collective's movement, the flock swollen to a people | **closed two-way** (fix 43); a migration provides nothing (the strip real depletion never a mint; the larder-farm refused) — **matches** |

**Count (current, pass-32 completion):** at the pass-32 count check designs/ =
185 files and README = 181 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **Four on-disk docs have no README
row yet** — corpus-map, the-crossroads, the-lightning, the-shrine — the next landing
batch, unindexed new arrivals, not ghosts. **The audit is now complete through
wave-47** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the
wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix 31), the
wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34), the
wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), the wave-46 set (fix 42), and the wave-47 set (fix 43) are
all audited two-way. Waves 48–57 (the wave-48+ through wave-56+ arrivals) are on
disk and indexed but must NOT be audited within passes 22–32; their passes remain
future work — the count and the *audit* remain separate.

**Wave-48 closures (pass 33 / fix 44): the ford, the estuary, and the tutelary all
land two-way on the crossing / mixing / line-the-sources — and the river↔ford
two-way write-race is landed (the river's open-Q1 flagged the ford absent; now on
disk they read two-way, the camp stays honestly absent); the waves 28–48 audit is
now complete (seventy genuine audit rows per the closure tally convention, each
written only after its edges were grep-verified).**

|| Wave-48 re-point | What it closes | Status |
|---|---|---|---|
|| `the-ford.md` ↔ `the-river.md` §2/§4b/open-Q4/§6; `the-causeway.md` §1/§2/§7; `the-swim.md` §2a/§5; `the-cart.md` §2/§3/open-Q6; `the-shepherd.md` §2/§3/§5d; `the-gatekeeper.md` §1/§2; `the-toll.md` §2/§4/open-Q5; `the-threshold.md` §1/§2.2/§3; `signature-predator.md` §2/§1.2/§7e; `the-mimic.md` §2/§3/§4; `energy-harnessing.md` §2/§6; `the-marsh.md` §2/§8; `the-walk.md` §1/§2/§4a | the river's natural shallow, the crossing the water makes safe of itself, the easy reach where the stroke lets you stand — the given crossing distinct from the built causeway | **closed two-way** (fix 44); a ford converts nothing, no crossing that yields; **the river↔ford race is landed (river's open-Q1 ford-absent → landed; camp still honest-absent)** — **matches** |
|| `the-estuary.md` ↔ `the-river.md` §2/§4/§5c/§6; `the-sea.md` §2/§2a/§5b/§5c/d/e; `the-marsh.md` §2/§3/§6c/§7; `tide-of-the-attractor.md` §2/§5a/§5d; `the-ford.md` §2/§4/§6; `the-causeway.md` §1/§7; `field-emergent-ecology.md` §2.2/§4.2/§6b/§1.4; `the-desert.md` §2/§3/§5b/§6; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-compost.md` §4/§5d; `signature-predator.md` §2/§7e; `the-swim.md` §2a; `the-fall.md` §2/§5d | the mixing's fought water, the river's mouth, the wet twin of the edge-regime — where the sea's salt argues against the current | **closed two-way** (fix 44); the mixing feeds at the field's own yield, never a mint — **matches** |
|| `the-tutelary.md` ↔ `the-guardian.md` §1/§3/§4/§5c/d/e/§7; `the-family.md` §1/§2.1/§3.2/§3.3/§5b/§6b; `the-child.md` §2/§3/§6b/§6d; `the-healer.md` §2/§3/§5e; `the-commensal.md` §2/§3/§5b; `the-name.md` §1/§2/§5.1/§6d/§6e; `the-exile.md` §2/§4/§6b; `the-inheritance.md` §2/§2.4/§3.2/§8; `life-signal.md` §1/§3/§3.1/§6a/b/§6d; `signature-predator.md` §1/§2/§2.2/§7e/§8; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1/§1.4/§1.3/§5c; `the-lock.md` §1/§2/§3/§6d; `the-walk.md` §1/§2a/§2c/§4a/§4c/d/e; `the-herald.md` §2/§5b/§5c/d/e; `the-mimic.md` §2/§4; `the-witness.md` §1/§2/§7; `the-gatekeeper.md` §1/§2 | the line's personal keeper, the following made attached, the held order that follows — the family's shared anchor made a watcher, the heir's taken keeper | **closed two-way** (fix 44); a tutelary converts nothing, never a free shield — **matches** |

**Count (current, pass-33 completion):** at the pass-33 count check designs/ =
185 files and README = 181 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **Four on-disk docs have no README
row yet** — corpus-map, the-crossroads, the-lightning, the-shrine — the next landing
batch, unindexed new arrivals, not ghosts. **The audit is now complete through
wave-48** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the
wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix 31), the
wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34), the
wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), the wave-46 set (fix 42), the wave-47 set (fix 43), and the
wave-48 set (fix 44) are all audited two-way. Waves 49–57 (the wave-49+ through
wave-56+ arrivals) are on disk and indexed but must NOT be audited within passes
22–33; their passes remain future work — the count and the *audit* remain separate.

**Wave-49 closures (pass 34 / fix 45): the midwife, the inn, and the blizzard all
land two-way on the birth / guest-bed / driven-white sources; the waves 28–49 audit
is now complete (seventy-three genuine audit rows per the closure tally convention,
each written only after its edges were grep-verified).**

|| Wave-49 re-point | What it closes | Status |
|---|---|---|---|
|| `the-midwife.md` ↔ `the-child.md` §1/§3.1/§2.1/§6d/§6c; `life-signal.md` §1/§3/§3.1/§6a/§6b/§6c/d; `shared-ledger.md` §1.2/§6c/§6d/§6a/§6b; `schema-that-settles.md` §2.1/§2.1.1/§6d; `the-family.md` §1/§2.1/§3.2/§6b/§6d; `the-rite-of-passage.md` §1/§2.1/§4b; `the-healer.md` §2/§3/§4.1; `the-spring-caretaker.md` §1/§2/§5/§6; `the-census.md` §2.1/§2.2/§7; `the-name.md` §1/§2/§6b; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1/§1.4/§1.2; `the-apprenticeship.md` §1; `coherence-magic.md` §1; `async-field-domain.md` §1–2; `the-witness.md` §1/§2; `the-gatekeeper.md` §1/§2; `the-vigil.md` §1 | the office the birth-rite presupposes, the fresh run's receiver, the first read's bounded spend — the line's first lock booked unforgeably, from the child's zero | **closed two-way** (fix 45); the midwife converts nothing (the first read real and spent, never a mint) — **matches** |
|| `the-inn.md` ↔ `window-guests.md` §1/§3/§6b/§6d; `house-that-steers.md` §1.1/§2.2/§3/§5b/§5d; `the-threshold.md` §1/§2.2/§2.3/§4/§6; `the-gatekeeper.md` §1/§2.1/§2.2/§5c/§5e; `the-wage.md` §1/§2.1/§4.1/§5d; `the-toll.md` §3/§4/§5c/§5d; `the-gift.md` §1/§2.2/§3/§6d; `the-exile.md` §1/§4; `the-census.md` §2.1/§2.4; `shared-ledger.md` §1.2/§6c/§6d/§6a/§6e; `schema-that-settles.md` §2.1/§2.2/§3; `energy-harnessing.md` §2/§4.4/§5.4/§6; `field-instruments.md` §2.1; `sleep.md` §1/§2b; `the-burden.md` §1/§2/§4; `the-healer.md` §2/§3; `the-mimic.md` §4 | the held room, the guest-form of pay, the booked welcome — the welcome the gift refuses to tally, held within the settlement's bound | **closed two-way** (fix 45); an inn converts nothing (an inn charged without the held room is a false op; the paid night books on the settled op-record) — **matches** |
|| `the-blizzard.md` ↔ `the-cold.md` §2/§3/§6(b); `the-wind.md` §1/§2.2/§3/§5(b)/§5(c)(d)(e); `the-rain.md` §2/§3/§4; `weather-not-storm.md` §2/§3; `field-hazards.md` §2/§5.1; `the-smell.md` §2; `the-walk.md` §2/§2a/§2b/§2c/§4a; `the-beacon.md` §2/§5; `signature-predator.md` §1.2/§2/§1.3; `the-season-change.md` §2/§4; `the-dawn.md` §2/§2b; `energy-harnessing.md` §2/§6; `field-instruments.md` §1.2/§1.4/§2.1; `the-cart.md` §3; `the-husbander.md` §2 | the cold's driven white, the winter's storm, the hazard's honest cover — the rain's wet-fall frozen and driven, what the white hides it hides from the Coda too | **closed two-way** (fix 45); a blizzard converts nothing (the cover spent and gone, never a mint, never a free cloak; NOT the storm) — **matches** |

**Count (current, pass-34 completion):** at the pass-34 count check designs/ =
185 files and README = 181 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **Four on-disk docs have no README
row yet** — corpus-map, the-crossroads, the-lightning, the-shrine — the next landing
batch, unindexed new arrivals, not ghosts. **The audit is now complete through
wave-49** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the
wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix 31), the
wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34), the
wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), the wave-46 set (fix 42), the wave-47 set (fix 43), the
wave-48 set (fix 44), and the wave-49 set (fix 45) are all audited two-way. Waves
50–57 (the wave-50+ through wave-56+ arrivals) are on disk and indexed but must NOT
be audited within passes 22–34; their passes remain future work — the count and the
*audit* remain separate.

**Wave-50 closures (pass 35 / fix 46): the understory, the mirage, and the mint all
land two-way on the shade / composition / coin sources; the waves 28–50 audit is
now complete (seventy-six genuine audit rows per the closure tally convention, each
written only after its edges were grep-verified).**

|| Wave-50 re-point | What it closes | Status |
|---|---|---|---|
|| `the-understory.md` ↔ `the-zenith.md` §1/§2a/§6; `the-bedrock.md` §1/§3/§6; `the-cave.md` §1/§5d; `the-roost.md` §2/§3/§4/§5e; `field-emergent-ecology.md` §4.2/§6b/§2.2/§1.4; `field-music.md` §2.4/§2.3/§6; `field-instruments.md` §2.1/§1.2; `energy-harnessing.md` §2/§6; `the-desert.md` §2a/§2b/§5d/§6b; `the-stratum-read.md` §2.1/§2.3; `the-cold.md` §2/§7; `the-sea.md` §1/§2; `the-sea-floor.md` §1; `coherence-magic.md` §2/§5.1; `chunk-field-quantization.md` §1.2/§4 | the shade, the vertical’s occupied middle on land, the thin not the void — where the zenith’s light arrives and is spent, the forest-middle that holds life on its margins | **closed two-way** (fix 46); the understory converts nothing (the canopy’s absorption the field’s own spent) — **matches** |
|| `the-mirage.md` ↔ `the-desert.md` §2(a)/§5b/§3/§6.2/§4/§5d; `the-dispute.md` §2/§6(c)/§6(e); `the-spring.md` §3/§3.1/§2.1/§4/§5d/§5e; `the-beacon.md` §2/§2(a)/§2(c)/§5d; `the-smell.md` §2/§2.1/open-Q2/§6; `field-instruments.md` §2.1/§1.2/§1.4/§5; `life-signal.md` §3/§4/§6a/§6b; `signature-predator.md` §1.2/§1.3/§7e; `energy-harnessing.md` §2/§6; `weather-not-storm.md` §2; `the-stratum-read.md` §2; `the-census.md` §2/§6d; `the-mimic.md` §4; `the-clock.md` §2 | the thin’s composition, the composed bright, the false trail — the instrument’s interpretation of a genuine read, never the field mis-stating itself, the un-sustained bright that fades | **closed two-way** (fix 46); a mirage converts nothing, no lure that farms to — **matches** |
|| `the-mint.md` ↔ `shared-ledger.md` §1.2/§1.3/§2/§6c/§6d/§6b; `schema-that-settles.md` §2.1/§2.2/§2.3/§3/§6e; `the-market.md` §1/§2/§2.3/§3/§6d; `the-wage.md` §1/§2/§4a/§6b/§7; `the-toll.md` §2/§4/§6b; `the-gift.md` §1/§2.3/§6d; `the-loan.md` §1/§2/§4a; `the-tool.md` §2/§3/§4d; `the-quarry.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-granary.md` §2/§5d; `the-commons-tithe.md` §2.1/§6d | the coin, the portable booking, the struck order never mined — the settled booking made a thing a worker carries, a present quantum never a promise, unforgeable on the settled record | **closed two-way** (fix 46); a mint converts nothing, the coin never yields (the strike books on the settled op-record verbatim) — **matches** |

**Count (current, pass-35 completion):** at the pass-35 count check designs/ =
185 files and README = 181 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **Four on-disk docs have no README
row yet** — corpus-map, the-crossroads, the-lightning, the-shrine — the next landing
batch, unindexed new arrivals, not ghosts. **The audit is now complete through
wave-50** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the
wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix 31), the
wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34), the
wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), the wave-46 set (fix 42), the wave-47 set (fix 43), the
wave-48 set (fix 44), the wave-49 set (fix 45), and the wave-50 set (fix 46) are
all audited two-way. Waves 51–57 (the wave-51+ through wave-56+ arrivals) are on
disk and indexed but must NOT be audited within passes 22–35; their passes remain
future work — the count and the *audit* remain separate.

**Wave-51 closures (pass 36 / fix 47): the orchard, the delta, and the sledge all
land two-way on the standing-crop / fan / winter-freight sources; the waves 28–51
audit is now complete (seventy-nine genuine audit rows per the closure tally
convention, each written only after its edges were grep-verified).**

|| Wave-51 re-point | What it closes | Status |
|---|---|---|---|
|| `the-orchard.md` ↔ `farm-that-feeds.md` §2/§3/§4/§5; `seed-garden.md` §1/§2; `the-granary.md` §2/§6; `patient-field.md` §2/§5b; `the-window-year.md` §2/§5b; `the-fallow.md` §2a; `the-husbander.md` §1/§2; `field-emergent-ecology.md` §4.2/§2.2/§6b/§5.3; `the-roost.md` §2/§4; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-season-change.md` §2/§4; `the-cold.md` §2; `material-regimes.md` §2/§4; `schema-that-settles.md` §2.1; `shared-ledger.md` §1.2; `the-window-pulse.md` §2 | the standing trees, the living permanence, the long arc’s clock made a crop — the farm’s slow end of the crop ladder, giving ‘across’ the turn not at a single high | **closed two-way** (fix 47); the orchard gives at the field’s own yield, never a mint — **matches** |
|| `the-delta.md` ↔ `the-river.md` §2/§4/§5c/d/e/§6; `the-estuary.md` §2/§4/§5b/§5d/e/§6/open-Q4; `the-marsh.md` §2/§3/§4/§6c/§7/§8; `the-ford.md` §2; `the-causeway.md` §1; `field-emergent-ecology.md` §4.2/§6b; `the-roost.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `tide-of-the-attractor.md` §2/§5a; `the-swim.md` §2a; `signature-predator.md` §2 | the river’s fan, the many mouths, the spread of the single line — the river’s living line spent into many, the bank’s hiding carried on the fan | **closed two-way** (fix 47); a delta converts nothing, the spread never a mint — **matches** |
|| `the-sledge.md` ↔ `the-cart.md` §2/§3/§4a/§5b/§6/§7; `the-carry.md` §2/§3/§4/§6; `the-cold.md` §2/§3/§5.3/§6(b)(c)(d)(e); `the-blizzard.md` §2/§3/§5b/§5e; `the-granary.md` §2/§3/§4/§6/§7; `coherence-highway.md` §1/§4/§6b/§6d; `the-fallow.md` §2a/§3/§5d; `the-toll.md` §4/§2/§5e; `energy-harnessing.md` §1.1/§2/§6; `field-instruments.md` §2.1/§1.4/§1.2; `schema-that-settles.md` §2.1/§2.2/§2.3; `shared-ledger.md` §1.2; `the-walk.md` §2/§2c/§4a/§4c/§4d; `the-husbander.md` §2; `the-climb.md` §1/§5d | the frozen twin of the cart, the carry at the winter’s scale, the freight dragged through the driven white — the cart’s same freight on the winter’s surface, crossing honest doors never a hidden sled-path | **closed two-way** (fix 47); the sledge converts nothing — no glide that yields, never a winter-mint — **matches** |

**Count (current, pass-36 completion):** at the pass-36 count check designs/ =
185 files and README = 181 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **Four on-disk docs have no README
row yet** — corpus-map, the-crossroads, the-lightning, the-shrine — the next landing
batch, unindexed new arrivals, not ghosts. **The audit is now complete through
wave-51** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the
wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix 31), the
wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34), the
wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), the wave-46 set (fix 42), the wave-47 set (fix 43), the
wave-48 set (fix 44), the wave-49 set (fix 45), the wave-50 set (fix 46), and the
wave-51 set (fix 47) are all audited two-way. Waves 52–57 (the wave-52+ through
wave-56+ arrivals) are on disk and indexed but must NOT be audited within passes
22–36; their passes remain future work — the count and the *audit* remain separate.

**Wave-52 closures (pass 37 / fix 48): the raft, the eclipse, and the pooka all
land two-way on the current’s-freight / named-dark / riled-shadow sources; the waves
28–52 audit is now complete (eighty-two genuine audit rows per the closure tally
convention, each written only after its edges were grep-verified).**

|| Wave-52 re-point | What it closes | Status |
|---|---|---|---|
|| `the-raft.md` ↔ `the-river.md` §2/§2a/§4/§5c/d/e/§6/open-Q1; `the-cart.md` §2a/§2b/§3/§4b/§5b/open-Q5; `the-granary.md` §2/§2.1/§3/§4/§5d/§6; `the-quarry.md` §2/§5d; `the-fallow.md` §2/§5d; `the-toll.md` §2/§4/§5d; `the-harbor.md` §2/§4/§5a/§5e; `the-estuary.md` §2; `the-delta.md` §2; `the-swim.md` §2a; `the-flood.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `signature-predator.md` §2; `world-seams.md` §2 | the current’s freight, the cart’s ride made fluid — a raft rides the flow the way a cart rides the road, the settlement’s freight carried downstream | **closed two-way** (fix 48); a raft converts nothing, no current that yields (the freight crosses honest doors, never a hidden lane) — **matches** |
|| `the-eclipse.md` ↔ `the-window-year.md` §2/§3/§5a/§5b/§5e; `the-observatory.md` §2/§2.1/§3.1/§6e; `the-zenith.md` §2a/§2b/§5/§6/§5 Q1; `the-dawn.md` §2/§2b; `the-beacon.md` §2/§2c/§5/§6; `field-instruments.md` §1.2/§2.1/§1.3; `the-smell.md` §2/§5/§6; `the-stillness.md` §1/§6; `the-season-change.md` §1/§4a/§5; `signature-predator.md` §1.2/§2; `energy-harnessing.md` §2/§6; `tide-of-the-attractor.md` §2/§5a/§5d; `the-cold.md` §1/§2; `the-lantern.md` §2/§4; `atmosphere-orbits-auroras.md` §; `the-stilling.md` §1/§4 | the named dark, the calendar’s scheduled dim, the honest cover spent and gone — where the dawn reveals the eclipse briefly erases, information and timing never energy | **closed two-way** (fix 48); an eclipse converts nothing, no dark that yields (not the stillness, drawn never blurred) — **matches** |
|| `the-pooka.md` ↔ `signature-predator.md` §1/§2/§3/§7e/§8; `life-signal.md` §1/§3/§3.1/§3.3/§6a/b; `the-burden.md` §1/§4; `the-fall.md` §2; `the-stilling.md` §1/§4; `the-dispute.md` §2; `energy-harnessing.md` §2/§6; `field-emergent-ecology.md` §2.2/§6b/§4.2; `field-instruments.md` §2.1; `the-mimic.md` §2/§4; `the-moth.md` §2/§3; `the-witness.md` §1/§2; `the-guardian.md` §1/§3/§5d; `the-marsh.md` §3 | the riled’s shadow, the trail’s inverse, the fear-fed run — the predator hunts a clean trail, the pooka is drawn by a riled state, the riling read to resolution | **closed two-way** (fix 48); a pooka converts nothing, the riling spent never a gain — **matches** |

**Count (current, pass-37 completion):** at the pass-37 count check designs/ =
185 files and README = 184 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **One on-disk doc has no README row
yet** — corpus-map — an unindexed new arrival, not a ghost (the director indexed
the-crossroads, the-lightning, and the-shrine at this boundary). **The audit is now
complete through wave-52** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set
(fix 28), the wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix
31), the wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34),
the wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), the wave-46 set (fix 42), the wave-47 set (fix 43), the
wave-48 set (fix 44), the wave-49 set (fix 45), the wave-50 set (fix 46), the
wave-51 set (fix 47), and the wave-52 set (fix 48) are all audited two-way. Waves
53–57 (the wave-53+ through wave-56+ arrivals) are on disk and indexed but must NOT
be audited within passes 22–37; their passes remain future work — the count and the
*audit* remain separate.

**Wave-53 closures (pass 38 / fix 49): the chant, the touch, and the siren all land
two-way on the sustained-voice / fifth-sense / entrainment sources; the waves 28–53
audit is now complete (eighty-five genuine audit rows per the closure tally
convention, each written only after its edges were grep-verified).**

|| Wave-53 re-point | What it closes | Status |
|---|---|---|---|
|| `the-chant.md` ↔ `the-shout.md` §1/§2/§5/§5c/d/e; `the-working-song.md` §1/§4/§5a/§5b/§5d; `the-vigil.md` §2/§3; `the-stilling.md` §2.1/§4/§2.3/§3; `the-threshold.md` §1/§2.2; `the-oath.md` §2; `field-music.md` §1/§6; `field-npc-ai.md` §3.2; `the-bell.md` §1; `the-echo.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-silence.md` §1; `field-hazards.md` §5.1; `the-healer.md` §2; `sleep.md` §1/§2b; `coherence-magic.md` §1/§5.1 | the sustained voiced field-act, the body’s voice held continuously — the shout’s voice held not spent, the watch held in voice, the chant holds never gains | **closed two-way** (fix 49); a chant converts nothing, the held voice spent never a gain — **matches** |
|| `the-touch.md` ↔ `mouths-eye.md` §1/§2/§6(a); `the-smell.md` §1/§4; `the-mirage.md` §2/§3; `the-walk.md` §2/§2a; `house-that-steers.md` §1/§1.1; `the-swim.md` §2a; `field-instruments.md` §2.1; `signature-predator.md` §2; `the-mimic.md` §4; `energy-harnessing.md` §2/§6; `the-stratum-read.md` §2; `field-music.md` §1; `the-wind.md` §1 | the fifth sense, the no-wind channel, the range-deceit dead at the skin — the field read at the body’s own point, at the thing and exact | **closed two-way** (fix 49); a touch converts nothing (a pure consumer at zero distance, never a mint) — **matches** |
|| `the-siren.md` ↔ `field-npc-ai.md` §3.2/§5.2/§6a/§2.3/§6d/§6c; `the-chant.md` §1/§3/§4/§5d/§6; `field-music.md` §2.4/§1/§4/§6; `the-working-song.md` §1/§4/§5c/d/e; `signature-predator.md` §1/§2.2/§3/§7e/§8; `the-herald.md` §1/§2.2/§4/§5a/d/e; `the-mimic.md` §2/§3/§4/§5c/d/e; `the-pooka.md` §2/§4/§5d; `the-moth.md` §2/§5b/§5d/§6; `the-dispute.md` §2/§2.1/§2.2/§6d; `life-signal.md` §3/§3.1/§6b/§6d; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1/§1.4/§1.3; `the-echo.md` §2/§6; `the-shout.md` §1; `the-stilling.md` §1/§4 | the entrainment ride, the matched cadence, the lure read to resolution — the herald reads the field forward, the siren reads you back; the field-cannot-lie un-masks it | **closed two-way** (fix 49); the siren converts nothing, no entrainment that yields, no seduction that mints (the call never a hidden difficulty, never a minted charm) — **matches** |

**Count (current, pass-38 completion):** at the pass-38 count check designs/ =
185 files and README = 184 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **One on-disk doc has no README row
yet** — corpus-map — an unindexed new arrival, not a ghost. **The audit is now
complete through wave-53** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set
(fix 28), the wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix
31), the wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34),
the wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), the wave-46 set (fix 42), the wave-47 set (fix 43), the
wave-48 set (fix 44), the wave-49 set (fix 45), the wave-50 set (fix 46), the
wave-51 set (fix 47), the wave-52 set (fix 48), and the wave-53 set (fix 49) are
all audited two-way. Waves 54–57 (the wave-54+ through wave-56+ arrivals) are on
disk and indexed but must NOT be audited within passes 22–38; their passes remain
future work — the count and the *audit* remain separate.

**Wave-54 closures (pass 39 / fix 50): the meadow, the canal, and the cistern all
land two-way on the open-common / dug-lane / held-water sources; the waves 28–54
audit is now complete (eighty-eight genuine audit rows per the closure tally
convention, each written only after its edges were grep-verified).**

|| Wave-54 re-point | What it closes | Status |
|---|---|---|---|
|| `the-meadow.md` ↔ `farm-that-feeds.md` §2/§3/§4/§5/§6; `the-fallow.md` §2a/§1/§3/§6; `the-desert.md` §2a/§5d/§6b; `the-understory.md` §1; `the-husbander.md` §1/§2; `the-shepherd.md` §2/§3; `field-emergent-ecology.md` §4.2/§6b; `the-roost.md` §2; `the-census.md` §2; `shared-ledger.md` §1.2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-granary.md` §2; `the-ford.md` §2; `the-scavenger.md` §2.2; `the-gift.md` §1 | the open common, the fertile inverse of the desert, the field’s own grazed middle — the graze the crop-fields cannot hold, the field’s *renewed* never the mined strip | **closed two-way** (fix 50); a meadow converts nothing, the graze never a mint (the keeping books nothing) — **matches** |
|| `the-canal.md` ↔ `the-river.md` §2/§4/§5c/d/e/§6/open-Q1; `the-raft.md` §2/§3/§4a/§5d/§6; `the-harbor.md` §2/§4; `the-delta.md` §2; `the-causeway.md` §1; `the-marsh.md` §2; `the-rain.md` §2; `the-spring.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-toll.md` §2/§4; `the-quarry.md` §2; `the-sea.md` §2; `the-estuary.md` §2; `coherence-highway.md` §1; `house-that-steers.md` §1/§6 | the re-aimed lane, the extended freight-lane, the dug water-road — the found line a settlement digs a reach of, the raft’s lane extended to the sea’s door | **closed two-way** (fix 50); a canal converts nothing, the dug lane never a mint (the freight crosses no hidden lane) — **matches** |
|| `the-cistern.md` ↔ `the-spring.md` §2/§3/§4/§5b/§5c/§5d/§5e; `the-rain.md` §1/§2.1/§3/§4/§5b/§5c/d/e; `the-desert.md` §2/§5d/§6b; `the-granary.md` §2/§5d/§6; `house-that-steers.md` §1/§6; `the-marsh.md` §2; `the-fallow.md` §2a; `the-compost.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-census.md` §2; `shared-ledger.md` §1.2; `the-spring-caretaker.md` §2 | the built-held well, the caught fall, the dry-season’s held lifeline — the spring’s water built-held, the drawn hold kept through the thin | **closed two-way** (fix 50); a cistern converts nothing, the drawn hold never a mint (the draw shares the spring’s over-draw honest counter) — **matches** |

**Count (current, pass-39 completion):** at the pass-39 count check designs/ =
185 files and README = 184 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **One on-disk doc has no README row
yet** — corpus-map — an unindexed new arrival, not a ghost. **The audit is now
complete through wave-54** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set
(fix 28), the wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix
31), the wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34),
the wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), the wave-46 set (fix 42), the wave-47 set (fix 43), the
wave-48 set (fix 44), the wave-49 set (fix 45), the wave-50 set (fix 46), the
wave-51 set (fix 47), the wave-52 set (fix 48), the wave-53 set (fix 49), and the
wave-54 set (fix 50) are all audited two-way. Waves 55–57 (the wave-55+ and wave-56+
arrivals) are on disk and indexed but must NOT be audited within passes 22–39; their
passes remain future work — the count and the *audit* remain separate.

**Wave-55 closures (pass 40 / fix 51): the meteor, the balefire, and the baptism all
land two-way on the falling-brightness / warning-flame / first-name sources; the
waves 28–55 audit is now complete (ninety-one genuine audit rows per the closure
tally convention, each written only after its edges were grep-verified).**

|| Wave-55 re-point | What it closes | Status |
|---|---|---|---|
|| `the-meteor.md` ↔ `atmosphere-orbits-auroras.md` §3.3/§3.2/§5c; `the-eclipse.md` §2/§3/§5/§6; `the-dawn.md` §2; `the-bell.md` §1; `the-herald.md` §1/§2; `the-observatory.md` §2; `the-scar-lifecycle.md` §2.2; `material-regimes.md` §2/§4; `the-quarry.md` §2; `field-archaeology.md` §2; `signature-predator.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-window-year.md` §2; `the-fallow.md` §2a | the falling brightness, the announced rare event, the non-minting fall — the sky’s brightness that *falls* against the aurora’s that *stays*, the eclipse’s announced counterpart | **closed two-way** (fix 51); a meteor converts nothing, the fall never a mint (announced, deterministic, never random, never hidden) — **matches** |
|| `the-balefire.md` ↔ `the-beacon.md` §1/§2/§2a/§2c/§5b/§5c/d/e; `the-bell.md` §1/§2.1/§2.3; `the-vigil.md` §2; `the-lantern.md` §2; `signature-predator.md` §2; `the-blight.md` §2; `the-flood.md` §4.1; `field-hazards.md` §5.1; `the-herald.md` §1/§2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-toll.md` §4; `the-shout.md` §1; `house-that-steers.md` §1/§3; `the-threshold.md` §1 | the hazard-twin of the beacon, the silent same of the bell, the raised warning flame — where the beacon says *here is home*, the balefire says *danger is coming* | **closed two-way** (fix 51); a balefire converts nothing, the warning spent never a mint (the raised flame the field’s own spent; a false warning a false op) — **matches** |
|| `the-baptism.md` ↔ `the-child.md` §1/§2.3/§6e/§3.1/§3.3/§3.5/§6d/§6c; `the-midwife.md` §1/§2.1/§2.2/§2.3/§5b/§6; `the-name.md` §1/§2/§5.1/§6b; `the-rite-of-passage.md` §1/§2.1; `the-family.md` §1/§2.1/§6d; `shared-ledger.md` §1.2/§6c/§6d; `schema-that-settles.md` §2.1/§6d; `the-census.md` §2.1/§2.2; `the-healer.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-tutelary.md` §1; `the-inheritance.md` §2 | the first name, the designed ceremony’s naming-sibling, the line’s first binding — the naming rite binds the first name over the first read the midwife took, the inheritance’s beginning | **closed two-way** (fix 51); a baptism converts nothing, the naming spent never a mint (you cannot name falsely; the naming books on the settled op-record) — **matches** |

**Count (current, pass-40 completion):** at the pass-40 count check designs/ =
185 files and README = 184 rows — **184 indexed / 185 on-disk, zero ghost rows**
(every README row resolves to an on-disk file). **One on-disk doc has no README row
yet** — corpus-map — an unindexed new arrival, not a ghost. **The audit is now
complete through wave-55** — the wave-28/29/30/31 set (fix 26/27), the wave-32 set
(fix 28), the wave-33 set (fix 29), the wave-34 set (fix 30), the wave-35 set (fix
31), the wave-36 set (fix 32), the wave-37 set (fix 33), the wave-38 set (fix 34),
the wave-39 set (fix 35), the wave-40 set (fix 36), the wave-41 set (fix 37), the
wave-42 set (fix 38), the wave-43 set (fix 39), the wave-44 set (fix 40), the
wave-45 set (fix 41), the wave-46 set (fix 42), the wave-47 set (fix 43), the
wave-48 set (fix 44), the wave-49 set (fix 45), the wave-50 set (fix 46), the
wave-51 set (fix 47), the wave-52 set (fix 48), the wave-53 set (fix 49), the
wave-54 set (fix 50), and the wave-55 set (fix 51) are all audited two-way. Waves
56–57 (the wave-56+ arrivals) are on disk and indexed but must NOT be audited within
passes 22–40; their passes remain future work — the count and the *audit* remain
separate.

**Wave-56 closures (pass 41 / fix 52 — t19 final): the palanquin, the fog, the
drought, and the caravan all land two-way on the carried-seat / static-twin /
going-dry / organized-passage sources; the waves 28–56 audit is now complete
(ninety-five genuine audit rows per the closure tally convention, each written only
after its edges were grep-verified) — the entire t19 wave-46–56 sweep is landed.**

|| Wave-56 re-point | What it closes | Status |
|---|---|---|---|
|| `the-palanquin.md` ↔ `the-cart.md` §2/§3/§4a/§4b/§5b/§6; `the-carry.md` §2/§3/§4/§6/§7; `the-sledge.md` §2/§3/§4/§6; `the-raft.md` §2/§6/§7; `the-election.md` §1/§2.4/§4.3/§6d/§6b/§7; `the-festival.md` §2/§2.3/§3/§6b/§7/§7 open-Q4; `the-rite-of-passage.md` §1/§2.1/§2.4/§3.2/§4b/§6; `the-healer.md` §2/§3/§3.1/§5/§6; `the-burden.md` §1/§2/§6a/§5; `the-census.md` §2.1/§6/§7; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1/§1.4/§1.3/§5c; `the-walk.md` §2/§2a/§4a; `the-climb.md` §1/§5d; `schema-that-settles.md` §2.1; `shared-ledger.md` §1.2 | the carried seat, the office’s borne, the procession’s honored becoming — the cart carries goods, the palanquin carries who rides it; the settlement bearing its chosen at its celebration | **closed two-way** (fix 52); a palanquin converts nothing, no bearing that yields (never a minted seat, never a hidden privilege) — **matches** |
|| `the-fog.md` ↔ `the-blizzard.md` §2/§3/§4/§5b/§6/§5c/d/e; `the-marsh.md` §2/§3/§4/§7c/d/e/§8; `the-mirage.md` §2/§3; `the-smell.md` §2/§5/§6; `life-signal.md` §3/§6a/§6b/§6c/§6d; `the-walk.md` §2/§2a/§2b/§2c/§4a/§4b/§4c/d/e; `signature-predator.md` §1.2/§2/§7e; `the-mimic.md` §2/§3/§5e; `weather-not-storm.md` §2/§3/§6; `field-hazards.md` §2/§5.1/§1/§5.3; `the-cold.md` §2/§3/§6(b)/§4; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-dawn.md` §2; `the-rain.md` §3 | the static twin of the blizzard, the air’s marsh, the field’s held weather — what the blur hides from you it hides from the Coda too, spent and gone when the field re-coheres | **closed two-way** (fix 52); a fog converts nothing, the blur spent never a gain (not the mirage — it blurs what is truly there) — **matches** |
|| `the-drought.md` ↔ `the-desert.md` §2/§1/§5b/§6; `the-flood.md` §2/§3/§4.1; `the-rain.md` §1/§2.1/§3; `the-spring.md` §2/§4; `the-spring-caretaker.md` §2; `the-cistern.md` §2; `the-fallow.md` §2a; `the-granary.md` §2; `the-cold.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `weather-not-storm.md` §2 | the going-dry, the flood’s slow-inverse, the field’s receding abundance — the *event* of going dry, the process distinct from the desert’s place | **closed two-way** (fix 52); a drought converts nothing, the dry spent never a gain — **matches** |
|| `the-caravan.md` ↔ `the-cart.md` §1/§2/§2b/§3/§4a/§5b/§7; `the-broker.md` §1/§2/§3/§4/§6; `the-market.md` §1/§2/§2.3/§6d/§6; `the-migration.md` §1/§2.1/§3.1/§4.1/§6; `the-pilgrim.md` §2/§5d; `the-desert.md` §2/§2/§5d/§6; `the-atlas-of-windows.md` §1/§2/§3/§4/§5/§4d; `the-harbor.md` §1/§2/§4/§5b; `the-toll.md` §1/§2/§4/§5d; `signature-predator.md` §2/§1.2/§7e; `the-vigil.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-walk.md` §2/§4a; `the-fallow.md` §2a/§5d; `seed-garden.md` §2; `schema-that-settles.md` §2.1; `shared-ledger.md` §1.2 | the organized passage of goods, the many-as-one guarded order, the held-door honesty — the cart’s unit composed into a many-body train, the goods’ crossing never a hidden train | **closed two-way** (fix 52); a caravan converts nothing, no organized passage that yields (a phantom caravan-load is a false op) — **matches** |

**Count (current, pass-41 completion — t19 final):** at the pass-41 count check
designs/ = 185 files and README = 184 rows — **184 indexed / 185 on-disk, zero ghost
rows** (every README row resolves to an on-disk file). **One on-disk doc has no README
row yet** — corpus-map — an unindexed new arrival, not a ghost (the director has
indexed every other doc in the corpus). **The audit is now complete through wave-56**
— the wave-28/29/30/31 set (fix 26/27), the wave-32 set (fix 28), the wave-33 set (fix
29), the wave-34 set (fix 30), the wave-35 set (fix 31), the wave-36 set (fix 32),
the wave-37 set (fix 33), the wave-38 set (fix 34), the wave-39 set (fix 35), the
wave-40 set (fix 36), the wave-41 set (fix 37), the wave-42 set (fix 38), the wave-43
set (fix 39), the wave-44 set (fix 40), the wave-45 set (fix 41), the wave-46 set
(fix 42), the wave-47 set (fix 43), the wave-48 set (fix 44), the wave-49 set (fix
45), the wave-50 set (fix 46), the wave-51 set (fix 47), the wave-52 set (fix 48),
the wave-53 set (fix 49), the wave-54 set (fix 50), the wave-55 set (fix 51), and
the wave-56 set (fix 52) are all audited two-way — **the t19 reconciliation pass is
complete (waves 46–56, fixes 42–52, all 34 docs audited)**. Only corpus-map remains
on disk un-indexed; its audit still awaits a README row (future work) — the count and
the *audit* remain separate.

**Wave-57/58/59/60 + requested closures (passes 42–46 / fixes 53–57 — t20
final, and the last reconcile pass of the program): the dune/terrace/votive (wave
57), the shrine/lightning/crossroads (wave 58), the rumor/generations/shaft (wave
59), the hand-over/seacraft/whirlpool (wave 60), and the two user-requested docs
(the-incantation, world-difficulty) all land two-way; the waves 28–60 + two
user-requested audit is now complete — the entire t20 sweep, and the final pass of
the program, is landed.**

|| Wave-57/58/59/60 + requested re-point | What it closes | Status |
|---|---|---|---|
|| `the-dune.md` ↔ `the-desert.md` §2/§2a/§2d/§4/§5b/§6; `the-wind.md` §1/§2/§3/§4/§5b/§5c/d/e; `energy-harnessing.md` §2/§1.7/§6; `field-archaeology.md` §1/§2/§3.2; `the-scar-lifecycle.md` §1/§2/§2.3; `the-fog.md` §2/§4; `the-delta.md`; `signature-predator.md` §2/§1.2; `field-instruments.md` §2.1; `the-cave.md`; `the-husbander.md` §2 | the wandering ridge, the desert’s own landform the wind walks across the dry, the land’s own archaeology the moving sand performs | **closed two-way** (fix 53); a dune converts nothing, no moving sand that yields — **matches** |
|| `the-terrace.md` ↔ `farm-that-feeds.md` §2/§3/§4/§5/§7b/§7e/§9a; `the-climb.md` §2/§4/§5b/§5c/5d/5e; `the-quarry.md` §2/§3/§5d/§6; `the-landform-name.md` §1/§2/§3/§4/§5d; `the-spring.md` §2/§5d/§4; `the-rain.md` §2/§3/§4; `the-fallow.md` §2/§1/§5d; `the-causeway.md` §1/§6; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-meadow.md`; `the-orchard.md`; `the-compost.md` §2; `the-carry.md` §3 | the ascent turned into fields, the worked land-cut at the slope’s register, the stepped crop-band never a mint | **closed two-way** (fix 53); a terrace converts nothing, the runoff’s steps spent never a gain — **matches** |
|| `the-votive.md` ↔ `the-gift.md` §1/§2.1/§2.2/§2.3/§6d; `the-commons-tithe.md` §1/§3/§6d; `the-toll.md` §1/§2/§4/§6d; `the-compost.md` §1/§2/§6d; `the-spring.md` §2/§3/§5b/§6; `the-bell.md` §1/§4/§6e; `the-landform-name.md` §1/§2/§5e; `the-dispute.md` §2; `the-census.md` §2; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-funeral.md` §2/§3.1; `the-shrine.md`; `the-festival.md` §2; `the-window-year.md` §2; `the-rite-of-passage.md` §2; `the-map.md` §3; `the-observatory.md` §2 | the field-ward giving that refuses even the receiver — the gift gives member-to-member and refuses the book, the votive gives to the field with no commons, no charge, no recipient | **closed two-way** (fix 53); a votive converts nothing, the left order spent never a gain — **matches**; the shrine two-way closes the awaiting receiving-place |
|| `the-shrine.md` ↔ `the-funeral.md` §2/§2.3/§3.1/§3.2/§3.3/§6b; `the-votive.md` §1/§3/§2.2/§4.2/§4.3/§4.4/§5c/d/e/§7; `the-dispute.md` §2/§6c/d/e; `energy-harnessing.md` §2/§6/§4.4/§5.3/§5.4; `field-instruments.md` §2.1/§1.2/§3.1; `the-census.md` §2/§2.3/§6c/d/e/§7; `the-map.md` §3; `the-bell.md` §1/§4; `the-spring.md` §2; `the-landform-name.md` §1/§2; `house-that-steers.md`; `the-name.md` §2; `schema-that-settles.md` §2.1; `shared-ledger.md` §1.2; `field-npc-ai.md` | the funeral’s register made a standing home that answers nothing — the letting-go’s place, the built remembrance that resolves the votive’s open remainder | **closed two-way** (fix 54); a shrine converts nothing, the held order is spent, never free — **matches** |
|| `the-lightning.md` ↔ `field-hazards.md` §2/§2.1/§2.3/§5.3/open-Q2; `weather-not-storm.md` §2/§3/§6; `coherence-magic.md` §4.3/§1.2/§5.1/§6; `atmosphere-orbits-auroras.md` §3/§3.4/§1.3; `the-wind.md` §1/§3/§5c/d/e; `the-rain.md` §3; `the-blizzard.md` §1–4/§5c/d/e/§6; `the-fog.md` §2; `the-meteor.md`; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-dispute.md` §2; `the-scar-lifecycle.md` §2; `material-regimes.md`; `tide-of-the-attractor.md` §2 | the storm’s release, the gathered charge letting go at once, the corpus’s storm-discharge locus (the absent `the-storm.md` honestly named, field-hazards + weather-not-storm standing in) | **closed two-way** (fix 54); a lightning converts nothing, the settled charge releasing a front never a yield — **matches** |
|| `the-crossroads.md` ↔ `the-causeway.md` §1/§2/§7a/§7/§8; `the-ford.md` §1/§2/§5/§6; `the-toll.md` §1/§4/§5d/§6; `the-caravan.md` §1/§2/§5e/§6; `the-dispute.md` §2/§4/§5/§6c; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-map.md` §3; `the-walk.md` §2; `coherence-highway.md`; `signature-predator.md` §2; `field-npc-ai.md`; `life-signal.md` §3; `the-story.md` §2; `async-field-domain.md` | the maintained fork, the meeting of ways with no held door, the indifferent read of the passing train | **closed two-way** (fix 54); a crossroads converts nothing, no meeting that yields (only a held door at a meeting books a toll) — **matches** |
|| `the-rumor.md` ↔ the-chronicle/story/herald/dispute/shared-ledger/echo/observatory/npc-ai/instruments/energy/compass/language/mimic/name/archaeology/schema (16) | the unverified read anywhere, the pre-settled story, the claimed word that must die at the observatory | **closed two-way** (fix 55); a rumor converts nothing, the passed word spent never a gain (a false rumor mis-names and fades) — **matches** |
|| `the-generations.md` ↔ the-family/inheritance/child/midwife/baptism/rite-of-passage/funeral/chronicle/story/name/migration/window-year/tide/shared-ledger/instruments/energy/dispute/reason-field/schema/player-remains/archaeology/npc-ai (22) | the carried lineage, the spans’ bound hold passed across time | **closed two-way** (fix 55); a generation converts nothing, the passed order spent never a gain — **matches** |
|| `the-shaft.md` ↔ the-dive/cave/quarry/fall/climb/bedrock/tool/carry/cart/chunk-field-quantization/instruments/energy/dispute (13) | the dug hollow descending to a bounded floor, never a hidden depth | **closed two-way** (fix 55); a shaft converts nothing, the dug depth spent never a gain — **matches** |
|| `the-hand-over.md` ↔ the-election/inheritance/archivist/chronicle/shared-ledger/oath/apprenticeship/generations/rite-of-passage/census/instruments/energy/dispute/name (14) | the office passed, the carried turn made explicit, the skill’s final passing | **closed two-way** (fix 56); a hand-over converts nothing, the office passed spent never a gain — **matches** |
|| `the-seacraft.md` ↔ the-sea/sea-floor/raft/deep-field-diving/swim/harbor/tide/wind/river/carry/cart/instruments/energy/dispute (14) | the built water-craft, the plain’s crossing, never free | **closed two-way** (fix 56); a seacraft converts nothing, the sailed passage spent never a gain — **matches** |
|| `the-whirlpool.md` ↔ the-sea/sea-floor/river/swim/dive/flood/marsh/rain/canal/cistern/estuary/touch/climb/instruments/energy/tide/dispute (17) | the sea’s sunken drain, the river’s two-face read at a spent bend, the taking’s local vortex never the giving | **closed two-way** (fix 56); a whirlpool converts nothing, the spun water spent never a gain (converts nothing harder than a river) — **matches** |
|| `the-incantation.md` ↔ the-language/coherence-magic/chant/shout/working-song/siren/dispute/energy/instruments/festival/election/rite-of-passage/stilling/vigil/school/apprenticeship/npc-ai/music/reason/observatory/echo/compass/async-domain/bell/world-difficulty (25) | the language’s reverse grammar, the ordered perturbation never a plea, phase-matched and fully legible | **closed two-way** (fix 57); an incantation converts nothing, never creates order from nothing — **matches**; the world-difficulty two-way closes the dial’s rite |
|| `world-difficulty.md` ↔ field-hazards/weather-not-storm/tide/atmosphere/wind/lightning/blizzard/fog/drought/meteor/signature-predator/energy/instruments/dispute/chunk-field-quantization/async-domain (16) | the honest dial that scales the field’s own extremes, never a hidden punishment | **closed two-way** (fix 57); world-difficulty converts nothing, the dial scales the field’s own extremes, never generates order — **matches** |

**Count (current, pass-46 completion — t20 final / program end):** at the live
pass-46 count check designs/ = 200 files and README = 192 rows — **192 indexed /
200 on-disk, zero ghost rows** (every README row resolves to an on-disk file). The
**14 audited t20 docs are all within the indexed set**. **Eight on-disk docs have no
README row yet** — corpus-map (the long-running unindexed arrival) plus the **7
final-wave in-flight docs** (the-anchor, the-atoll, the-bog, the-comet, the-crane,
the-tunnel, the-waterfall) that the handoff brief said land after this pass and are
**not counted / not touched** here — all are unaudited new arrivals, neither ghosts
nor indexed. **The audit is now complete through wave-60 plus the two user-requested
docs** — the t20 reconciliation pass, and the final reconcile pass of the program,
is complete (waves 57–60 + the-incantation/world-difficulty, fixes 53–57, all 14
docs audited two-way). The 7 in-flight docs and corpus-map remain on disk
un-indexed and un-audited; their audits await a future (post-program) pass — the
count and the *audit* remain separate.

**Final-wave closures (pass 47 / fix 58 — t21, PROGRAM COMPLETE): the seven
final docs all land two-way; the audits of the entire corpus — every indexed design
doc, waves 7–60 plus the user-requested and final-wave arrivals — are now
complete. The program is closed.**

|| Final-wave re-point | What it closes | Status |
|---|---|---|---|
|| `the-tunnel.md` ↔ `the-shaft.md` §1/§2(b)/§2(a)/§2(f)/§3(c)/§5c; `the-cave.md` §1/§3/§5b; `the-quarry.md` §1/§2(a)/§4/§5b; `the-bedrock.md` §1/§2(a)/§5b; `the-tool.md` §2(a)/§2(b)/§3/§5b; `the-carry.md` §2/§4/§5b; `the-climb.md` §3.1/§3.2/§3.3/§5b; `the-ford.md` §1/§2; `the-causeway.md` §1/§6; `the-between.md` §2; `chunk-field-quantization.md`; `energy-harnessing.md` §2/§6; `field-instruments.md` §2.1; `the-dispute.md` §2 | the horizontal’s twin — the shaft cuts straight down, the tunnel cuts straight through, the under-hill cut that stays a crossing not a descent | **closed two-way** (fix 58); a tunnel converts nothing, the dug line spent never a gain — **matches** |
|| `the-waterfall.md` ↔ `the-rain.md` §1/§2.1/§3.2; `the-river.md` §1/§3a/§3b/§4c; `the-climb.md` §1/§3.3/§4.3; `the-sea.md` §2b/§4/§5b; `the-flood.md` §1/§3; `energy-harnessing.md` §1.1/§2/§6; `field-music.md` §1/§2.4; `the-seacraft.md` §1/§2a/§4c; `the-swim.md` §2a; `field-instruments.md` §2.1; `the-dispute.md` §2 | the river’s descent taken as a free drop, the plain’s one vertical the seacraft cannot cross, the gradient’s discharge heard as its own voice | **closed two-way** (fix 58); a waterfall converts nothing, a rotor in the fall a real costed turbine with `(1−q)` waste — **matches** |
|| `the-crane.md` ↔ `the-tool.md` §2(a)/§3/§5b; `the-carry.md` §1/§2/§4/§5b; `the-cart.md` §1/§3/§5b; `the-quarry.md` §1/§2(a)/§4; `the-shaft.md` §1/§2(b); `house-that-steers.md` §1/§2.2/§5b; `energy-harnessing.md` §2/§6; `reason-field.md`; `field-instruments.md` §2.1; `the-climb.md` §1; `the-fall.md` §5d; `the-dispute.md` §2 | the built machine a rung-matched tool dresses and keeps, the vertical’s line reversed and aided, the builder’s lift | **closed two-way** (fix 58); a crane converts nothing, never a free hoist — **matches** |
|| `the-comet.md` ↔ `the-meteor.md` §2/§5b/§5c; `atmosphere-orbits-auroras.md` §2/§2.1/§2.2/§2.3/§5; `the-window-year.md` §1/§2/§3; `tide-of-the-attractor.md` §1/§2/§5a; `the-observatory.md` §1/§2/§2.2; `the-dawn.md` §1; `the-eclipse.md`; `the-zenith.md`; `the-reading-ahead.md`; `field-instruments.md` §2.1; `energy-harnessing.md` §2/§6; `the-dispute.md` §2 | the meteor’s periodic return, one more body of the sky’s own orbit, the visiting bright named in the window’s long calendar | **closed two-way** (fix 58); a comet converts nothing, never a minted omen — **matches** |
|| `the-bog.md` ↔ `the-marsh.md` §1/§2/§5/§7b; `the-flood.md` §1/§2/§4; `the-desert.md` §1/§2/§4a; `the-walk.md` §1/§1.2/§2(a)/§2(b)/§4b; `the-fall.md` §1/§2.1/§3/§4; `the-quarry.md` §1/§2(a)/§4; `the-rain.md` §1/§2.1/§3.2; `the-meadow.md`; `the-stratum-read.md`; `the-carry.md` §2/§4; `field-instruments.md` §2.1; `the-dispute.md` §2; `energy-harnessing.md` §2/§6 | the water’s staying, the ground’s two extremes with the desert, the soaked earth that cuts nothing and yields nothing | **closed two-way** (fix 58); a bog converts nothing, the held wet spent never a gain — **matches** |
|| `the-atoll.md` ↔ `the-sea.md` §1/§2b/§5b; `the-sea-floor.md` §2a/§2b/§4.1/§5b; `the-harbor.md` §1/§4/§5d; `the-seacraft.md` §1/§2a/§2d/§4c; `the-whirlpool.md` §1/§2(a); `the-estuary.md` §1/§2; `life-signal.md` §1/§3; `the-marsh.md` §2; `field-instruments.md` §2.1; `energy-harnessing.md` §2/§6; `the-dispute.md` §2 | the sea-floor’s reef risen to the surface, the ring the flat water’s crown makes, the lagoon’s shelter the harbor’s own honesty | **closed two-way** (fix 58); an atoll converts nothing, never a minted island — **matches** |
|| `the-anchor.md` ↔ `the-seacraft.md` §1/§2a/§2d/§4c/open-Q6; `tide-of-the-attractor.md` §1/§2/§5a; `the-harbor.md` §1/§2c/§4/§5d; `the-sea.md` §2b/§4; `the-sea-floor.md` §1/§2a/§5d; `the-carry.md` §1/§4/§5b; `the-tool.md` §2(a)/§4b; `the-oath.md` §2; `field-instruments.md` §2.1; `energy-harnessing.md` §2/§6; `the-dispute.md` §2 | the banked reversible mooring landed, the crossing’s resting, the held station against the window’s long drift, the hold by the field’s own grip never a magic stick | **closed two-way** (fix 58); an anchor converts nothing, never a minted harbor — **matches**; **the seacraft’s open-Q6 (the proposed-but-unlanded reversible mooring) is now closed** — the anchor is that mooring, landed |

**Count (current, pass-47 completion — PROGRAM FINAL):** at the live pass-47
count check designs/ = 200 files and README = 199 rows — **199 indexed / 200
on-disk, zero ghost rows** (every README row resolves to an on-disk file; the seven
final-wave docs are now indexed and audited two-way fix 58). **One on-disk doc has
no README row** — corpus-map — the single un-indexed arrival, un-audited, its
audit blocked on indexing. **The audit is now complete for the entire indexed
corpus**: waves 28–60 plus the user-requested (the-incantation, world-difficulty)
and the final-wave (the-tunnel/waterfall/crane/comet/bog/atoll/anchor) all audited
two-way. **The t21 reconciliation pass, and with it the corpus reconciliation
program, is complete** (fixes 58, all 7 final docs, 84 edges verified two-way).
corpus-map remains the sole un-indexed, un-audited file; its audit awaits a future
post-program pass once it gains a README row — the count and the *audit* remain
separate.

**Standing observations (no fix required):**
- `chunk-field-quantization.md` §1.2 writes `h₀ = 2·min(extent)/N = 2.8125 m`.
  The value (2.8125 = min full extent / N) is correct and matches the m/cell
  column; the formula's "min(extent)" is ambiguous between full (180, giving
  5.625) and half (90, giving 2.8125) extent. `h₀` is not part of the canonical
  set, so left as-is.
- `chunk-field-quantization.md` summary table's "1 cell ≈ 3×3×7 blocks" is the
  *stock φ-aspect* min-size cell (4.551×2.8125×7.363 m); the chunk-aligned box
  correctly gives 3×3×3 = 27 blocks per cell. Consistent for each box — not a
  conflict.

**README meshless-section registration (post-program note).** The README's "## Why
open boundary is not optional — and how it shipped" section now states the meshless
sites directly: the architectural diagram retains `meshless sites (2·16³, JFA +
Lloyd relaxation)`, and the section records the meshless promotion (A) as *measured
and shelved* — gate-iv showed the per-site wave 38% off on coarse dispersion, so the
N³ lattice stays the field of record; the moving-Voronoi sites remain load-map
markers ("where the field is most organized", a natural chunk-activity / LOD
scheduler). This entry registers that README refresh; the meshless/Π frontier
standing-gate references above are unchanged. No design doc was altered by the
refresh.
