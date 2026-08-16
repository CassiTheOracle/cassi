# The Schema That Settles: The Q4 Player-Return Op-Schema, Settled

**Question under design:** the corpus's most load-bearing unresolved plumbing —
the exact shape of the Q4 player-return op-record. Five deferred questions, five
waiting consumers, no owner. Every consumer of the Q4 record parks a fork on
"the owner" — and nothing owns the settlement. This document is that owner. It
resolves the **extended record**

```
{ member, op, worldPos, rung, magnitude, sustain }
```

committing to each fork with reasons. Not a new face on the Corpus — the
**contract the faces are waiting on.**

The record this extends is `coherence-magic.md` §5.1's per-op schema
`{op, worldPos, rung, magnitude, sustain}`, batched into the player-return job at
the sampler/world-writer cadence — carried by `async-field-domain.md` §7 Q4, the
Q4 player-return channel. This document **does not add a channel, a lane, a
subsystem, or a physics claim.** It settles the *shape of the records that channel
already carries.*

Companion to (all relative paths):
- [`coherence-magic.md`](./coherence-magic.md) — **THE schema source.** §5.1 the
  per-op record `{op, worldPos, rung, magnitude, sustain}`; the six ops as field
  operations §2; the ε² vent and coherence budget §1; Q2 the sustain-vs-re-emit
  fork; the Q4 single-writer lane §5.1/§5.2.
- [`async-field-domain.md`](./async-field-domain.md) — **THE lane.** §7 Q4 the
  player-return channel, the single-writer world-writer path (§5.2 — the only
  mutator, no forged contributions); the published channels §2.1.
- [`shared-ledger.md`](./shared-ledger.md) — **THE first consumer to demand the
  settlement.** §4.1 sustain-vs-reemit socially; §4.2 the member-id demand; §4.3
  the schema gaps (locality granularity, no member field); §6c member-id = the
  Board's #1 binding risk ("the politics never starts until the id lands"); §7
  open-Q3 member-id across death.
- [`reason-field.md`](./reason-field.md) — §4.3 the Q4 lane is unchanged by the
  domain-side intent channel — **this doc settles the Q4 *write* lane, not the
  Reason Field's domain→sampler read**; §6a the Q4 schema being settled is a
  gate for the costed re-lock and the trace journal.
- [`field-music.md`](./field-music.md) — open-Q3 the sustain-flag vs re-emit
  question; §4.1 a score is a Q4 op sequence (a consumer of the settled record).
- [`player-remains.md`](./player-remains.md) — §2 the re-lock the member-id
  derives from (a fresh persistent Π pattern re-locked where the local field's
  coherence holds); §7 open-Q5 the conservation-of-"you" (the same identity
  question as the member-id across death); §5(c)/§5(a) the [design]-on-[design]
  stack.
- [`life-signal.md`](./life-signal.md) — open-Q2 the deliberate-vent vs
  sustained-maintenance residual, deferred on the per-entity `M` publication.
- [`signature-predator.md`](./signature-predator.md) — open-Q2 the phase-matching
  availability (does the Coda's `M` need publishing, the same deferral).
- [`resonance-tutor.md`](./resonance-tutor.md) — §1 the trace record the journal
  reads (a consumer of this schema); §4.2 the trace journal (gated on the Q4
  schema being settled, `reason-field.md` §6a).
- [`field-npc-ai.md`](./field-npc-ai.md) — §2.1 the persistent-Π identity the
  member-id borrows; §7 open-Q1 the decision-layer fork (resolved to the domain
  side by `reason-field.md`, the domain-side re-lock this doc's member-id binds).

Theory grounding (CassiTheory — read-only, cited by relative path, **flagged as
speculation where the doc's own source flags it**):
- `CassiTheory/speculations/qi-computation.md` §5.2 — persistent Π patterns:
  long-term field storage as Yang-Yin configurations at attractor-potential
  minima, persisting while ambient `q` stays above dissolution. `reason-field.md`
  §6a records that the engine's *persistent-Π-as-memory* is a speculative /
  creative extrapolation — the doc's own §9 labels it. **The member-id derives
  from this structure; the persistence is theory-ratified, the *identity-attach*
  is this document's [design].**
- `CassiTheory/speculations/creative-extensions/magic-systems.md` §1 — the
  phase-matching factor `M` (organized, phase-matched perturbation has `M ≈ 1`;
  random has `M ≈ 0`) — the per-entity `M` publication question of §5.

Every number below is from
[`corpus-reconciliation.md`](./corpus-reconciliation.md) **§2 (the canonical set —
cited, not re-derived)**. The honest line is drawn the way the corpus draws it
everywhere: **the schema's surface is [design]; the single-writer Q4 write path it
rides is engine-real; the persistent-Π identity the member-id derives from is
theory-ratified (with its speculation flag); no number here is new.**

---

## 1. The fork list, stated once

Five deferred questions, each with its waiting consumers and the "owner" the
docs currently defer to. **This document convicts itself of all five:** it owns
the settlement, taking each consumer's strongest documented preference as a
commitment where one exists.

| # | The deferred question | Waiting consumers | The current "owner" (the deferral) |
|---|---|---|---|
| **1** | **Member-id.** The canonical schema `{op, worldPos, rung, magnitude, sustain}` has no member field; the Board's per-member attribution is impossible until one lands. | `shared-ledger.md` §4.2 (the Board), §6c ("the politics never starts until the id lands"), §1.3 (the aggregation object `C(M)` per member) | `shared-ledger.md` §4.2 flags it as a **[design] extension** "the world-writer attaches at write time" — but no doc binds the world-writer to do it. The Board's open-Q1 (§7) parks "needs a stable binding"; the binding's *rule* is unowned. **Deferred to "the owner" = this doc.** |
| **2** | **Sustain-flag vs re-emit.** Is a held op a `{sustain}` flag (the domain maintains the source until told to stop) or a per-job re-emit? | `shared-ledger.md` §4.1 (social: a sustained healer vs a spam-reemitter book differently), `coherence-magic.md` §7 Q2 (the owner), `field-music.md` open-Q3 (music's sustained phrases map to the op records) | `coherence-magic.md` §7 Q2 owns it; `shared-ledger.md` §7 open-Q3 records its *preference* (sustain-flag) and defers to "the schema's Q2"; `field-music.md` open-Q3 defers to "Q4 is resolved." **Deferred to the schema owner = this doc.** |
| **3** | **Locality bounding.** Two members in one cell, one healing and one dissolving, book a net that hides both — per-op locality must be bounded. | `shared-ledger.md` §4.3 (the Board surfaces the gap); §1.2 (contribution vs drain is read at `worldPos`) | `shared-ledger.md` §4.3 names the need; no doc owns the rule. **Deferred to the schema owner = this doc.** |
| **4** | **Member-id across death.** Does a reborn player keep one member line or open a new one? | `shared-ledger.md` §7 open-Q3 (the Board needs a stable binding), `player-remains.md` §7 open-Q5 (conservation-of-"you") | `player-remains.md` §7 open-Q5 poses it as the identity open-question; `shared-ledger.md` §7 open-Q3 defers ("the identity is the existing open question"). **Deferred to a design decision = this doc.** |
| **5** | **The phase-match `M` publication.** Is per-entity `M` published now (Phase-1) or kept a deferred probe? | `life-signal.md` open-Q2 (the vent-vs-sustained residual), `signature-predator.md` open-Q2 (the Coda's `M`-readability), and through them the Board's Coda-attribution guard (`shared-ledger.md` §5/§6e) | `life-signal.md` §2/§7 and `signature-predator.md` §7 open-Q2 both defer "needs `M` published per-entity (Phase-1 does not budget it)." **Deferred to a cost decision = this doc.** |

**The commitment, stated once.** The five forks are not five open questions — they
are **one schema decision with five faces** (what rides on each field of the
extended record), and they settle together. This document takes the consumers'
documented preferences as commitments where they are recorded:

- **Sustain-flag** — `shared-ledger.md` §4.1's social case and §7 open-Q3's
  preference is a commitment; a held healer must book cleanly, not as a spammer.
- **Member-id** — `shared-ledger.md` §4.2's designed extension is the only
  coherent point (the world-writer's single write); this doc binds the rule.
- **Locality** — `shared-ledger.md` §4.3's "per-op locality bounding" is the
  requirement; this doc designs the cell-ownership rule.
- **Member-id across death** — `player-remains.md` §7 open-Q5's "conservation-of-
  you" is the identity; this doc decides the ledger rule it implies.
- **M publication** — both `life-signal.md` open-Q2 and `signature-predator.md`
  open-Q2 state the two sides' cost; this doc decides which cost to pay (and at
  what phase), per §5.

---

## 2. The resolved schema

```
{ member, op, worldPos, rung, magnitude, sustain }
```

**member first — because attribution is the read's spine** (`shared-ledger.md`
§4.2), and every consumer that gates on the settlement gates on the identity it
carries. Field by field, what each settles, and why.

### 2.1 `member` — the make-or-break field

**What it carries.** A stable **member-id** — the Board's per-member identity
(`shared-ledger.md` §1.3's `C(M)` key), the trace journal's provenance, the
coherence score's author. The Board's politics starts exactly when this field
lands.

**Where it attaches — the design settles the engine's single non-forgeable
point.** The member-id attaches **at the world-writer's write** — the *only*
server-side mutator (`async-field-domain.md` §5.2: no player, no server code, no
sampler touches physics state; player edits round-trip as job-dict inputs). The
world-writer is already the single write point; adding the id at *its* write is
the **only non-forgeable point** — a contributor cannot write a fake id into the
ledger, because the id on a record is written by the same authority that writes
the op, and the ledger is exactly the domain's executed op record
(`shared-ledger.md` §6d's no-forge strength, extended to identity).

**What the id is derived from.** The id is derived from the player's
**persistent-Π re-lock** (`player-remains.md` §2: rebirth is re-locking a fresh
persistent Π pattern where the local field's coherence holds). The id is a
**label bound to the re-lock pattern the world-writer already sees at the player's
rebirth** — the same persistent-Π structure the Reason Field re-holds for the
player (domain-side fuse, `reason-field.md` §4.1). It is **not** a UUID minted by
a server; it is a stable tag over the field-held identity the re-lock realizes.

**The [design] line, drawn exactly.** The Q4 write path is **engine-real**
(single-writer, `async-field-domain.md` §5.2). The `member` field on records is
**[design]** — a designed extension over that engine-real lane, exactly as
`shared-ledger.md` §4.2 flags it. The persistent-Π identity it derives from is
**theory-ratified** (`qi-computation.md` §5.2) with `reason-field.md` §6a's
speculation flag carried on the *identity-as-memory* claim. The world-writer
attaches a designed tag over a real engine event. No claim here pretends the
engine writes "member" records today.

**Why the world-writer (not the domain, not the sampler).** The domain writes no
identity record (`shared-ledger.md` §4.2: "the engine writes no identity"); the
sampler is read-only and must stay so (`async-field-domain.md` §1 — sampler
derives intent, never mutates). The world-writer is the *only* mutation point on
the server thread, and the re-lock it already applies the player's body around is
the player-return event the id must tag. This is the one place the corpus's own
single-writer discipline makes forge-impossible attribution structurally
available. **Settled: world-writer attach.**

#### 2.1.1 Member-id across death — DECIDED: same member line, new lock

The fourth fork (`shared-ledger.md` §7 open-Q3; `player-remains.md` §7 open-Q5) is
the **identity decision** the id field forces: when a player dies and re-locks a
fresh persistent Π pattern (`player-remains.md` §2), do they keep the same member
line on the ledger, or open a new one? **This document decides: the same member
line, with the new lock re-binding to it.**

The rule, stated once:

> **A reborn player keeps the same member line.** The member-id is bound to the
> player's persistent-Π re-lock — and because rebirth *is* re-locking a fresh
> persistent Π pattern (`player-remains.md` §2: "the player re-condenses by
> re-locking a fresh persistent Π pattern"), the re-lock is the *same identity*
> (`player-remains.md` §7 open-Q5: "identity is a persistent Π pattern," the
> only freshness is the *lock*, not the *self*). The world-writer, which already
> applies the re-lock around the body, binds the new lock to the existing member-id.
> **The member line is conservation-of-"you" made a ledger rule.**

**The reasons (the settlement's commit):**

1. **The persistent-Π re-lock is the same identity** per `player-remains.md` §2 /
   §7 open-Q5. `player-remains.md` §7 open-Q5 poses the fork and its own stance is
   the second half — "you are a fresh run over your own remains," where the
   continuity is the window's memory of the player. The member line *is* where the
   window's memory of the player lives; a fresh line would break that continuity
   precisely where the doc says it holds.
2. **The Board's arc reads need a continuous line** per `shared-ledger.md` §7
   open-Q3 and §1.3. The Board renders a member's `C(M)` *per tide over many
   cycles* — steward vs margin-causer is a sustained pattern, "never a single
   event" (`shared-ledger.md` §3.3's attrition guard). A fresh line after every
   death would fragment a long steward's arc into unbookable stubs and reset the
   margin-causer's attribution; the classifier needs the continuous net a single
   line provides.
3. **"Find your own past" needs a stable target.** `player-remains.md` §3's
   "find your own past" framing and `resonance-seeds.md` §1.2 (the Π pattern as
   "who you are") are only assertable if the *reborn* player can claim the old
   fossil's line as their own. A new line would orphan the fossil into a stranger's
   line and read as mere archaeology, not self.

**The honest cost of the rejected re-take side.** A fresh line per death would let
a reborn player **start clean socially** — a margin-causer could "die into a new
identity" and shed their negative `C(M)`, and a long steward could farm a clean-seeming
drain. That is the real appeal of re-take, and it is exactly why it is rejected:
it **orbits the continuous arc conservation-of-you exists to preserve**
(`player-remains.md` §7 open-Q5) and, worse, it turns death into a **ledger
amnesty** — a non-cosmetic consequence the corpus's determinism and honesty
discipline (`shared-ledger.md` §3.3, `field-npc-ai.md` §6d) forbid. The settled
rule keeps death's *field* cost (the re-lock's q-draw, `player-remains.md` §2.2)
and its *identity* cost (the line persists; the run is new) without granting a
social reset. The Board therefore needs no "reborn = new member" branch — it
aggregates one continuous `C(M)` line per member across deaths, closed only on the
dissolved entry (`shared-ledger.md` §2.2's settled balance, `player-remains.md`
§3). **Settled: same member line, new lock, no ledger amnesty.**

### 2.2 `sustain` — adopted over re-emit

**The settlement.** `sustain` is a **flag**, not a re-emit cadence. A held op
(shield, heal-in-place, a still room, a score's sustained phrase) carries
`sustain = true` and means **the domain maintains the source until told to stop**
(`coherence-magic.md` §7 Q2's defined option), not that the server re-sends the op
each job.

**Why the flag wins (the shared-ledger preference, made a commitment).**
`shared-ledger.md` §4.1 is unambiguous about the social consequence — and the
Board is the first consumer whose *design depends* on the settlement:

| Schema choice | A sustained healer books as | A spam-reemitter books as |
|---|---|---|
| **sustain flag** (adopted) | **one** high-magnitude, long-sustain record — a continuous contribution | N re-emitted records of the same magnitude — a noisy book |
| per-job re-emit (rejected) | N identical records | the same N — **indistinguishable** on magnitude alone |

A society that wants clean books (holding vs fiddling) mechanically rewards the
`{sustain}` semantics; `shared-ledger.md` §4.1 records that preference, and this
doc adopts it as a commitment. A held steward is a bath-maintainer
(`shared-ledger.md` §1.2: heal/sustained shield = contribution); a refresh-
reemitter is noise. The flag is what keeps those two bookable apart.

**The cost — the domain must hold the leak.** A sustain flag means the domain
carries the source's perturbation across jobs (the op is a standing job-dict
input until the release). `coherence-magic.md` §3 bounds it: sustained channeling
is bounded by the ε² vent rate `v ≤ h` (the field's heal rate) — a sustain is
only legal while the vent settles; overdraw is the §4.3 discharge. So the held
leak is *self-bounding*: the domain holds exactly what the op's budget physics
allows, and the release (`sustain = false` / a cancel) ends it. Budgeted against
the canonical **≈ 1–6 ms/tick** server sample cost (`corpus-reconciliation.md`
§2) — a sustained op is a standing input in the job dict, not a per-tick compute;
it costs the world-writer the same bounded write per cadence as any op, sized
against the 44 ms (88%) of the tick `chunk-field-quantization.md` §4 reports
unused.

**[design]** The sustain *semantics* (a standing source until released) are
designed over the engine-real Q4 write lane; the *vent bound* that makes sustain
legal is engine-real physics. The release signal is a designed op (a `sustain =
false` record with the same `member`/`op`/`worldPos`).

### 2.3 `worldPos` + a designed locality bound — two members in one cell

**The requirement** (`shared-ledger.md` §4.3): two members in the same cell, one
healing and one dissolving, must not book a net that hides both. The granularity
of `worldPos` alone cannot stop a contribution and a drain from canceling silently
inside one cell.

**The cell-ownership rule (designed).** The record's `worldPos` is at **cell
granularity** (the 3 m whole cells / 1 m sub-cell samples of the chunk-aligned
Phase-1 box, `corpus-reconciliation.md` §2). The locality bound is: **one member
books one disposition per cell per tide-window at a bounded range.** Concretely,
per `member` × `worldPos`-cell, the op-stream aggregates to a **single net
field-contribution** over the tide's accounting window (`shared-ledger.md` §1.3's
`C(M)` per `[t_k, t_k+T]`) — heal and dissolve at the same cell by the *same*
member net against each other, but a **contribution and a drain by *different*
members at one cell do not cancel**; they are attributed separately, because the
membership is on the record. The locality rule the schema fixes: **an op binds to
the cell its `worldPos` names, and the ledger's per-member sum reads each member's
net over that cell independently.** Two members in one cell book two lines, never
one silent zero.

**[design]** The cell-granularity attribution is a designed aggregation rule over
the engine-real `worldPos` and the engine-real single-writer stream. The
classifier line of `shared-ledger.md` §6e (a contribution and a drain are read by
the op's field effect at its locality/rung, `§1.2`) is unchanged — the rule only
stops them from *merging across members*.

### 2.4 `rung` and `magnitude` — the cost and depth, unchanged in kind

`rung` (the cascade scale the op operates at) and `magnitude` (the perturbation's
size / cost) are carried over from `coherence-magic.md` §5.1 unchanged — they are
not the focus of a fork; they are the op's already-settled cost and depth. They
feed `coherence-magic.md` §1.2's budget `B` and `shared-ledger.md` §1.2's
disposition (a deep-rung dissolve at a thin tide is a margin-causer's signature).
The record grows `member` first; `rung` and `magnitude` keep their meaning
verbatim from the schema this extends.

### 2.5 The `op` — the six operations, unchanged

`op` names the six field operations of `coherence-magic.md` §2
(condense / dissolve / steer / ignite / shield-heal / sense). Sense is a rung-0
read; the five writes round-trip through Q4. The record's op field is unchanged;
the settlement adds the identity and sustain semantics that make the ops *bookable
per member.*

### 2.6 Status flags on the settlement, once

| Record field | Status | Basis |
|---|---|---|
| The Q4 write path (`async-field-domain.md` §7 Q4; the world-writer the only mutator, §5.2) | **engine-real** | `async-field-domain.md` §1/§5.2 — the acyclic, type-enforced seam |
| `op`, `worldPos`, `rung`, `magnitude` as `coherence-magic.md` §5.1 defines them | **engine-real** (the schema's carried fields) | `coherence-magic.md` §5.1; `async-field-domain.md` §7 Q4 |
| **`member` on records, attached at the world-writer's write** | **[design]** | `shared-ledger.md` §4.2; this doc §2.1 — the engine writes no identity; the designed tag over the real write |
| **Member-id across death — same member line, new lock** | **[design]** (identity rule over the theory-ratified re-lock) | `player-remains.md` §2/§7 open-Q5; `shared-ledger.md` §7 open-Q3; this doc §2.1.1 — the persistent-Π re-lock is the same identity; the world-writer re-binds the new lock to the same line |
| **`sustain` as a flag (standing source)** | **[design] over engine-real vent physics** | `coherence-magic.md` §7 Q2; the vent bound `v ≤ h` is engine-real (§2.2) |
| **The cell-ownership locality rule** | **[design]** | `shared-ledger.md` §4.3; this doc §2.3 |
| The player's **persistent-Π identity** the member-id derives from | **theory-ratified** (with `reason-field.md` §6a's speculation flag on the memory claim) | `qi-computation.md` §5.2; `player-remains.md` §2; `field-npc-ai.md` §2.1 |

---

## 3. The M publication decision

The per-entity phase-match `M` (`magic-systems.md` §1: organized, phase-matched
perturbation has `M ≈ 1`; random `M ≈ 0`) — published now or kept a deferred
probe? Both `life-signal.md` open-Q2 and `signature-predator.md` open-Q2 defer the
answer; this document decides it.

**The two sides' costs.**

| Side | What it buys | What it costs |
|---|---|---|
| **Publish `M` now** | Sharpens `life-signal.md`'s vent-vs-sustained ambiguity (open-Q2's residual) and `signature-predator.md`'s attribution (open-Q2's trail phase-stability) at the source; the Board's Coda-attribution guard (`shared-ledger.md` §5/§6e) gets the phase-structure directly instead of inferring it | **Publish bytes + per-entity budget.** `M` is a per-entity scalar: appended to each body/steered record. Against the canonical ≈ 6 MiB publish and the ≈ 2,000-entity cap (`corpus-reconciliation.md` §2), a per-entity `M` is ~2,000 floats ≈ 8 KB f32 / 4 KB f16 — *not* the grid's multi-MB class, but it is a **new per-entity read** the sampler must compute each cadence, and `life-signal.md` §2 already shows the distinction can be carried by the time-series without it |
| **Defer `M` (a probe)** | Keeps the publish lean (no per-entity field yet, no new cadence read); answers "the time-series carries it" — `life-signal.md`'s own **Phase-1 answer** (§2, §7): the maintenance axis (pulsing vs flat, rising vs static) separates live from residue, deliberate vent from maintained lock, *without* `M`, from the published channels' time-series. `signature-predator.md`'s Phase-1 readable-trail slice (§8) is likewise a pure consumer that does not need `M` | The vent-vs-sustained *residual* stays open (open-Q2's ambiguity); the Coda's trail "phase-stability" collapses toward duration × ε²-magnitude (`signature-predator.md` open-Q2's consequence); the Board infers phase-structure from cadence shape rather than reading it |

**The decision: defer `M` to a Phase-1.5 probe.** This document adopts
`life-signal.md`'s Phase-1 answer as the settlement's: the maintenance axis
carries the vent-vs-sustained and growl-vs-scar distinctions *without* per-entity
`M`, from the published channels' time-series (`life-signal.md` §2/§3.2). The
`M` publication therefore **does not ship with the Phase-1 schema** — it is a
deferred probe, gated on two things:

1. **`life-signal.md` §6 N2 returning an irreducible ambiguity** between a
   deliberate vent and a sustained maintained lock on cadence shape alone — the
   pre-registered probe's verdict, not a preference.
2. **`signature-predator.md` open-Q2 needing phase, not just duration ×
   ε²-magnitude**, once the Coda's accumulation model is built.

If either returns, `M` is published as a **later, small per-entity scalar** —
~8 KB f32 per publish against the ≈ 6 MiB canonical (≈ 1.3‰), a bounded add, **not
a Phase-1 blocker.** If neither returns, the corpus's "the time-series carries
it" answer stands and `M` stays an optional depth (the doc's own honest
formulation in `life-signal.md` §3.2 and `signature-predator.md` §7 Q2).

**The published-vs-deferred consequence for each consumer of the `M`-question:**

| Consumer | Published now | Deferred probe (adopted) |
|---|---|---|
| `life-signal.md` (open-Q2 vent-vs-sustained) | the residual reads at the source | the Phase-1 maintenance axis carries it; the residual is an honest open-Q until the probe; if N2 is ambiguous, `M` publishes later |
| `signature-predator.md` (open-Q2 `M`-readability) | the trail's phase-stability reads directly | the readable-trail slice ships Phase-1 without `M`; the accumulation model's `M_stability` is a [design] probe until `M` publishes |
| `shared-ledger.md` (the Coda-attribution guard, §5/§6e) | the Board reads the Coda's phase directly | the Board relies on the cadence-shape / ε²-gradient read (`life-signal.md` §3.2) and keeps the "must not blame a hunted player for a Coda's ε²" guard as the classifier line — a social cost, not a blocker |

**The cost of the choice, honest.** Deferring keeps Phase-1 lean and exact
(`life-signal.md`'s own Phase-1 verdict); it leaves the vent-sustained residual
and the Coda's sharpest discriminator open until the probe and the accumulation
model. That is the settlement — a decision, with the deferred cost stated, not a
punting.

---

## 4. The consumers, unblocked

What the settlement unlocks for each waiting consumer. **The re-pointing note:** a
reconciliation pass re-points the open-question sections after this doc lands
(constraint: this doc does not edit the peers' open-Q sections); each consumer's
gate below is the exact thing the settlement closes.

| Consumer | What the settlement unblocks for it | The gate it closes |
|---|---|---|
| **`shared-ledger.md`** | The Board's politics **starts**: `member` on every record makes per-member `C(M)` attributable (`shared-ledger.md` §1.3), the cell-ownership rule stops per-cell silent cancellation (§4.3), the sustain flag books a steward cleanly vs a spammer (§4.1), and the member-across-death rule gives it the stable binding its §7 open-Q3 demanded. "The politics never starts until the id lands" — the id has landed. | §6c gate (member-id), §7 open-Q3 (member-across-death), §4.1/§4.3 (sustain + locality) |
| **`field-music.md`** | The sustain question **books socially**: a score's sustained phrase maps to `sustain = true` records (one held record per phrase, not N re-emits), so the composer's record count and the ledger's book agree; open-Q3 (music-as-field-operation cadence) is resolved. | open-Q3 (sustain-flag vs re-emit) |
| **`resonance-tutor.md`** | The trace journal's record is **settled**: the Q4 op-record now carries `member`, so a trace carries its author's identity (provenance), and the sustain flag makes a trace's held phases a compact, faithful record (one sustained record per hold, not a spam of re-emits). The journal's persistence/scope (open-Q1) still rides the Reason Field's domain-side publish (`reason-field.md` §4.2), but the *record it journals* is now final. | §1 the trace record; the Q4-schema leg of `reason-field.md` §6a |
| **`player-remains.md`** | The re-lock's identity is **bound**: the member-across-death rule ties the re-lock's persistent-Π pattern to a stable member line ('conservation-of-you' made a ledger rule), so the "find your own past" framing (§3) has a defined identity target; the re-lock cost (open-Q1) stays a domain-side fuse (`reason-field.md` §4.1) but the Q4 schema it writes through is settled. | §7 open-Q5 (conservation-of-you), the Q4-schema leg of `reason-field.md` §6a, `player-remains.md` §5(b) |
| **`reason-field.md`** | The Q4 gate **closes**: its §6a gate on "the Q4 schema must be settled" is now closed — the costed re-lock and the trace journal can be designed against a final record (`reason-field.md` §4.3 preserves the Q4 write lane's ownership; this doc settles the lane's record). | §6a's Q4-schema gate |
| **The Coda (`signature-predator.md`) + `life-signal.md`** | The `M` question's Phase-1 answer is decided (deferred probe, §3): the readable-trail slice ships without `M`; if the probe returns ambiguity, `M` publishes as a small later scalar. Attribution sharpens when `M` lands; neither is blocked at Phase-1. | open-Q2 of both docs (the `M`-publication deferral) |

---

## 5. The cost ledger

Every cost of the settlement, against a canonical number (`corpus-reconciliation.md`
§2 — cited, not re-derived).

| Cost | What it is | Sized against |
|---|---|---|
| **The `member` field on every record** | One id per op record, attached at the world-writer's write. A member-id is a stable tag (a hash/label over the re-lock pattern) — ~16 B per record, trivially small against the records' own payload. The real cost is the **world-writer's bookkeeping**: it must hold the re-lock → member-id binding per player and attach it on each write, a bounded lookup, no new channel. | the ≈ 6 MiB publish (`q` 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1) and the ≈ 1–6 ms/tick sample budget — a per-record tag and a per-player binding table, inside both |
| **The sustain-flag semantics** | The domain holds the source's leak until the release — a standing job-dict input. This is **self-bounding**: a sustain is only legal while the vent settles (`v ≤ h`, `coherence-magic.md` §3); overdraw is the §4.3 discharge. The cost is the domain carrying one standing perturbation + the world-writer's release bookkeeping, not a per-tick compute. | the ≈ 1–6 ms/tick budget, and the ~44 ms (88%) of the tick `chunk-field-quantization.md` §4 reports unused — the standing input is write-time, not per-tick CPU |
| **The locality (cell-ownership) rule** | The world-writer's bookkeeping: per `member` × cell, a per-tide net. This is the same aggregation the Board needs anyway (`shared-ledger.md` §1.3's `C(M)`); the settlement only fixes the *rule* (separate members' lines per cell, never merge). | a per-cell hash bucket over the op-stream — inside the sampler/ledger aggregation cost already budgeted, not a grid walk (the ledger reads the op-stream, never the 64³ array) |
| **The `M` publication (deferred, if later adopted)** | A per-entity `M` appended to each body/steered record: ~2,000 floats ≈ **8 KB f32 / 4 KB f16** per publish. Not shipped Phase-1 (this settlement defers it); if the probe returns ambiguity, it is a bounded add | the ≈ 6 MiB publish (≈ 1.3‰ add) and the ≈ 2,000-entity cap / ≈ 40 ns/entity steering (`corpus-reconciliation.md` §2) — a per-entity scalar read on the steering pass already done |
| **The one-time schema change** | Records written *before* the settlement (per §6 down): a designed migration, one field added, one flag added — see §6c. | a migration pass over the Q4 journal at the settlement's landing, not a per-tick cost |

Every cost is bookkeeping over the engine-real write lane — **none mints
coherence, none adds a channel, none moves the no-free-energy cap.** Q4 writes
what it already writes; the settlement changes what the records carry, not the
physics they perturb.

---

## 6. Honest gates

### (a) [design] plumbing over the engine-real Q4 lane

The schema is the **designed surface**; the single-writer path it rides is
**engine-real.** `async-field-domain.md` §5.2's world-writer-the-only-mutator
seam is unchanged and is what makes the member-id non-forgeable; the `member` /
`locality` rules are designed aggregation over that real write (the §2.6 table,
kept once and never blurred). The persistent-Π identity is theory-ratified with
`reason-field.md` §6a's speculation flag. No claim here pretends the engine writes
"member," "sustain," or "owner line" records.

### (b) Determinism — the schema adds none

The field is deterministic (one PDE; `player-remains.md` §5e; `field-npc-ai.md`
§2.3/§6d). The schema is **bookkeeping over deterministic writes**: the same ops,
the same field events, produce the same records; only the *fields on* those
records are new. The member-id is a pure function of the re-lock pattern (a
deterministic field event); the sustain flag is a designed label over a bounded
hold; the locality rule is a deterministic aggregation. **Same ops, same records,
same world** — the settlement introduces no nondeterminism.

### (c) Backwards compatibility — a designed migration, decided

Records written before the settlement (taken under `coherence-magic.md` §5.1's
five fields) predate `member`/`sustain`-as-flag semantics. **The design chooses a
migration, not a break:** the pre-settlement op-stream is a bounded Phase-1
journal (the Q4 records a Phase-1 player already leaves, `resonance-tutor.md`
§6a). At the settlement's landing, the migration:

1. **Back-fills the member field** from the world-writer's re-lock binding where
   it exists — a pre-settlement player's records get their id tagged at migration,
   the same non-forgeable authority, run once.
2. **Interprets pre-settlement `sustain` occurrences as the flag** (the op's
   duration already implied a held operation; the flag makes the interpretation
   explicit). A pre-settlement sustained healer's records, lacking the flag,
   default to the *re-emit* reading only where no `{sustain}` intent was recorded
   — the honest cost of the change, stated: a pre-settlement sustained hold may
   book as N re-emits. The migration flags these and lets the Board's classifier
   (the same cadence-shape net of `life-signal.md` §3.2) re-read them.
3. **Keeps the ledger a true reader of what the world was told** — it never edits
   the executed op, only re-tags the identity the world-writer owns.

This is a **decided migration** — the settlement lands as an additive field +
flag over the existing record, not a format break that orphans Phase-1 traces.

### (d) The no-free-energy cap is preserved

The schema is **bookkeeping; it cannot mint.** `energy-harnessing.md` §6's cap
(`output ≤ φ⁻¹·input`) is unchanged — adding a member-id to a record adds no
coherence, the sustain flag holds an op the vent physics already bounds, and the
locality rule only re-aggregates real ε²/ρ effects. **A member's `C(M)` cannot be
unboundedly positive** (`shared-ledger.md` §1.3): the record can be attributed to
a person, but it still carries the same net-negative-or-bounded field effect.
"Nobody is a net mint" was already true; the settlement makes it *legible per
member*, it does not move the cap.

### (e) The settlement is Phase-1 — must land with the first Q4 consumer

The schema is **pure schema over the already-required Q4 lane** (`coherence-magic.md`
§5.1; `async-field-domain.md` §7 Q4). It carries no new physics, no new channel,
no new write; it only fixes the fields of records the lane already carries. Per
§4, its first consumers are all Phase-1 deliverable legs: the Board's aggregation
slice (`shared-ledger.md` §6b — one player's stream), the tutor's trace
(`resonance-tutor.md` §6a), the readable-trail/P1 music bases (life-signal/service).
**The settlement ships with the first Q4 consumer** — the moment a Phase-1 player
emits a Q4 op-record, the record is the extended `{member, op, worldPos, rung,
magnitude, sustain}`. It cannot land later than the first write, or the first
consumer's journal books against a moving target.

---

## 7. Feasibility verdict

**PHASE-1 — the corpus's most-deferred fork closed as a contract.**

The settlement is a **pure schema decision over the engine-real Q4 write lane**:
an additive `member` field + a `sustain`-as-flag semantics + a designed
cell-ownership rule, all bookkeeping, none requiring new physics or a new channel.
It is Phase-1 because the lane it rides is Phase-1 (`coherence-magic.md` §5.1;
`async-field-domain.md` §7 Q4) and its first consumers are Phase-1-legible
($4). It is a **contract doc** — the thing the five waiting consumers gate on,
resolved in one place.

**What ships with it.** The first Q4 consumer — a Phase-1 player's op-stream
already records the extended schema; the Board's single-player aggregation slice
(`shared-ledger.md` §6b), the tutor's Phase-1 trace (`resonance-tutor.md` §6a),
and the readable-trail / Phase-1 music bases all ride a settled record. Phase 1.5
deferred (not blocked): the `M` publication (probe-gated, §3) and the costed
re-lock / trace journal's domain-side publish (`reason-field.md` §4.1, gated on
the meshless/persistent-Π frontier — *not* on this schema).

**What each un-settled alternative would have cost.**

| If we had NOT settled | The cost |
|---|---|
| **Member-id** unbound | the Board aggregates ops, not people; "the politics never starts" (`shared-ledger.md` §6c) indefinitely; every tracing/provenance feature journals against a moving, to-be-invented identity |
| **Sustain** left open | a sustained healer and a spam-reemitter book indistinguishably (`shared-ledger.md` §4.1) — the ledger loses the steward/spammer distinction permanently, and every score/trace's held phases book as N re-emits |
| **Locality** unbounded | two members in one cell cancel silently (`shared-ledger.md` §4.3) — the Board's cleanest attribution window is a blind spot |
| **Member-id across death** unruled | a reborn player's line is ambiguous — the ledger can't tell a long steward's continuous arc from a fresh member's, and player-remains' "find your own past" has no stable identity target |
| **`M`** unpunted | if published now, ~8 KB + a per-entity cadence read for a sharpening Phase-1 does not yet need (life-signal's maintenance axis carries it, §3); if deferred without a decision, the two open-Q2s stay unowned — which is exactly the state this doc ends |

> **The honest statement that makes this doc load-bearing: the corpus's most
> deferred plumbing decision is not a physics question, it is a schema
> commitment — and the consumers it unblocks are the corpus's most load-bearing
> faces (the Board's politics, the tutor's trace, the re-lock's identity, the
> Q4 gate). Nothing here names a new mechanism; everything here names the fields
> and rules that make the world's already-real op-stream bookable per person.
> The schema is the surface; the single-writer lane it rides is engine-real; the
> settlement is Phase-1. It is the contract the faces were waiting on — settled
> here, owned here, and the corpus's most-deferred fork closes as a Phase-1
> contract that ships with the first Q4 consumer.**

---

## Cross-references

- [`coherence-magic.md`](./coherence-magic.md) — the Q4 op-schema §5.1 extended
  here; the six ops §2; the ε² vent & budget §1; Q2 the sustain-vs-re-emit fork;
  the single-writer lane §5.1/§5.2; the vent bound that makes sustain legal §3.
- [`async-field-domain.md`](./async-field-domain.md) — §7 Q4 the player-return
  channel the records ride; §1/§5.2 the single-writer world-writer (the member-id's
  non-forgeable attach point); §2.1 the published channels.
- [`shared-ledger.md`](./shared-ledger.md) — the schema gaps §4.3; the sustain
  social consequence §4.1; the member-id demand §4.2; the binding risk §6c; the
  member-across-death open-Q3 §7; the aggregation object §1.3; the Coda guard §5.
- [`reason-field.md`](./reason-field.md) — §4.3 the Q4 write lane untouched; §6a
  the Q4-schema gate this doc closes; §4.1 the domain-side re-lock fuse the
  member-id binds.
- [`field-music.md`](./field-music.md) — open-Q3 the sustain question; §4.1 a
  score is a Q4 op sequence (a consumer of the settled record).
- [`the-market.md`](./the-market.md) — **the exchange booked as the settled op.**
  §2.1 there reads §2.1 this doc's op-record `{member, op, worldPos, rung, magnitude,
  sustain}` verbatim — a trade *is* a Q4 op of that shape, booked at §3 this doc's single
  non-forgeable point; §2.1.1's same-member-line (no amnesty) is inherited by an exiled
  trader's line (§4.2 there). Reverse pointer: the market's honesty is this doc's
  no-false-booking — every exchange is the settled record.
- [`the-gift.md`](./the-gift.md) — **the settled record's withheld line.** §2.2 there
  reads §2.1 this doc's op-record as the shape a gift's **withheld** bookable line rides —
  the transfer moves but no `C(M)` contribution books; §2.1.1's no-amnesty is held at a
  gift (a gift cannot restore an exiled line, §4.3 there); §2.3's cell-ownership is the
  no-trace display's ground. Reverse pointer: the gift is the settled record's deliberate
  absence.
- [`the-dispute.md`](./the-dispute.md) — **the record as the claim's shape.** §2.1 there
  reads §2.1 this doc's op-record `{member, op, worldPos, rung, magnitude, sustain}` as the
  exact shape a claim is written in — a dispute checks two claims against the same executed
  stream; §2.1.1's same-member-line (no amnesty) and §2.3's cell-ownership (two claims
  never merge silent) are the dispute's walls. Reverse pointer: the dispute reads this
  doc's single non-forgeable record to final judgment.
- [`the-harbor.md`](./the-harbor.md) — **the departure books at the pier.** §2c there reads
  §2.1 this doc's Q4 op-record `{member, op, worldPos, rung, magnitude, sustain}` as the
  harbor's ledger — the departure's `worldPos` at the pier is the settled record's locality
  read at the harbor; §2.3's cell-ownership names the pier's cell; §2.2's sustain flag (a
  held voyage is a bounded hold). Reverse pointer: the harbor's departure is a Q4 op of this
  doc's settled shape.
- [`player-remains.md`](./player-remains.md) — §2 the re-lock the member-id
  derives from; §7 open-Q5 conservation-of-"you" (the member-across-death rule);
  §5 the [design] stack.
- [`life-signal.md`](./life-signal.md) — open-Q2 the vent-vs-sustained residual,
  answered Phase-1 by the maintenance axis without `M` (§3 of this doc);
  §6 the probe that gates the later `M` publication.
- [`signature-predator.md`](./signature-predator.md) — open-Q2 the `M`-readability,
  answered by the Phase-1 trail + the deferred-probe decision (§3 of this doc).
- [`resonance-tutor.md`](./resonance-tutor.md) — §1 the trace record (the settled
  schema), §4.2 the journal gated on the settled Q4 schema.
- [`field-npc-ai.md`](./field-npc-ai.md) — §2.1 the persistent-Π identity the
  member-id borrows; §7 open-Q1 (resolved domain-side by `reason-field.md`).
- [`chunk-field-quantization.md`](./chunk-field-quantization.md) — the 1 m / 3 m
  cell granularity (`corpus-reconciliation.md` §2) the locality rule uses.
- [`energy-harnessing.md`](./energy-harnessing.md) — §6 the no-free-energy cap the
  schema preserves (it cannot mint); §4.4 the Qi bath the Board's `C(M)` reads.
- [`the-loan.md`](./the-loan.md) — **the deferred line.** §2.1 there reads §2.1 this
  doc's Q4 op-record shape `{member, op, worldPos, rung, magnitude, sustain}` (a loan
  is a Q4 op of the settled record's shape, the exchange deferred) and §2.2 the sustain
  flag (the forward book — the term-carried hold). Reverse pointer: a loan is the
  settled record's deferred line.
- [`the-archive.md`](./the-archive.md) — **the record held raw.** §2/§5 there read §2
  this doc's settled op-record `{member, op, worldPos, rung, magnitude, sustain}` (the
  Archive's atomic unit), §2.1 the member-id at the one non-forgeable write, §2.2 the
  sustain flag, §5 the cost ledger. Reverse pointer: the Archive is the settled record
  held complete.
- [`the-granary.md`](./the-granary.md) — **the book of plenty.** §2.1 there reads §2.1
  this doc's op-record (the granary's deposits/draws book the way any op does), §2.2
  the sustain flag (the held store books as one record), §3 the single non-forgeable
  point. Reverse pointer: the granary books its store on the settled record.
- [`the-toll.md`](./the-toll.md) — **the toll's atomic book.** §2.1 there reads the Q4
  op-record `{member, op, worldPos, rung, magnitude, sustain}` (the toll's shape), §2.3
  the cell-ownership locality (the toll's `worldPos` at the door's cell), §3 the single
  non-forgeable point (the toll's honesty is the book's own). Reverse pointer: the
  toll books on the settled op-record verbatim.
- [`the-compost.md`](./the-compost.md) — **the heap's book.** §2.1 there reads the
  op-record `{member, op, worldPos, rung, magnitude, sustain}` — the Compost's deposits
  of spent matter and draws of feed book the way any op does; §2.3 the cell-ownership
  rule; §6d the cap preserved. Reverse pointer: the compost books on the settled
  op-record.
- [`the-carry.md`](./the-carry.md) — **the pack's book.** §2.1 there reads the
  op-record `{member, op, worldPos, rung, magnitude, sustain}` — what is carried books
  as a held item; §2.2 the sustain flag (the held load books as one standing record);
  §2.3 the cell-ownership rule. Reverse pointer: the carry books on the settled
  op-record.
- [`the-quarry.md`](./the-quarry.md) — **the take's book.** §2.1 there reads the
  op-record `{member, op, worldPos, rung, magnitude, sustain}` (the take's deposits/
  draws book the way any op does); §2.3 the cell-ownership rule; §3 the single
  non-forgeable write. Reverse pointer: the quarry's take books on the settled
  op-record.
- [`the-archivist.md`](./the-archivist.md) — **the raw's atomic unit.** §2 there reads
  the settled op-record `{member, op, worldPos, rung, magnitude, sustain}`; §2.1 the
  member-id at the single non-forgeable write; §3 the single non-forgeable point — the
  reason the Archivist cannot corrupt the raw; §6b no-nondeterminism. Reverse pointer:
  the archivist holds the settled op-record raw.
- [`the-wage.md`](./the-wage.md) — **the Wage's atomic book.** §2.1 there reads the Q4
  op-record `{member, op, worldPos, rung, magnitude, sustain}` (the wage's shape);
  §2.2 the sustain flag (a standing labor-contract); §2.3 cell-ownership; §3 the single
  non-forgeable point; §6e ships with the first Q4 consumer. Reverse pointer: the
  wage books on the settled op-record verbatim.
- [`the-spring-caretaker.md`](./the-spring-caretaker.md) — **the op-record.** §2.1 there
  reads `{member, op, worldPos, rung, magnitude, sustain}`; §2.3 the cell-ownership
  rule; §6d the cap preserved. Reverse pointer: the caretaker's read and draw book
  on the settled op-record.
- [`the-midwife.md`](./the-midwife.md) — **the first booking's shape.** §2.1 `{member, op, worldPos, rung, magnitude, sustain}`; §2.1.1 same-member-line; the single non-forgeable write; §6d the cap. Reverse pointer: a child is the settled line's first lock, booked by the midwife.
- [`the-inn.md`](./the-inn.md) — **the atomic book.** §2.1 the op-record (the paid night’s shape); §2.2 the sustain flag (a held night’s semantics); §3 the single non-forgeable point. Reverse pointer: the inn’s honesty is the settled book’s own.
- [`the-mint.md`](./the-mint.md) — **the coin’s atomic book.** §2.1 the op-record `{member, op, worldPos, rung, magnitude, sustain}` (the strike books as an op); §2.2 the sustain flag; §2.3 the cell-ownership rule; §3 the single non-forgeable point; §6e ships with the first Q4 consumer. Reverse pointer: a coin’s strike books on the settled op-record, unforgeable.
- [`the-orchard.md`](./the-orchard.md) — **the yield’s book.** §2.1 the op-record (the harvest books as any op). Reverse pointer: the orchard’s yield books on the settled record.
- [`the-sledge.md`](./the-sledge.md) — **the load’s book.** §2.1 the op-record (the sledge’s load books as any op); §2.2 the sustain flag; §2.3 the cell-ownership rule. Reverse pointer: the sledge’s freight books on the settled record.
- [`the-baptism.md`](./the-baptism.md) — **the name’s op-book.** §2.1 the op-record (the naming books as an op); §6d the cap. Reverse pointer: the baptism’s naming books on the settled record.
- [`the-palanquin.md`](./the-palanquin.md) — **the borne’s book.** §2.1 the op-record (the carried seat books as any op). Reverse pointer: the palanquin’s borne books on the settled record.
- [`the-caravan.md`](./the-caravan.md) — **the goods’ book.** §2.1 the op-record (the caravan’s freight books as any op). Reverse pointer: the caravan’s goods book on the settled record.
- [`the-shrine.md`](./the-shrine.md) — **the settled book.** §2.1 the op-record. Reverse pointer: the shrine’s leavings book on the settled record like any order — never a forgotten line.
- [`the-rumor.md`](./the-rumor.md) — **the book’s edge.** §2.1 the op-record. Reverse pointer: the rumor’s claim is checked against the settled record — it cannot exceed what the book holds.
- [`the-generations.md`](./the-generations.md) — **the settled book.** §2.1 the op-record. Reverse pointer: a generation’s order books on the settled record — never a silent drop.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — §2 the canonical
  numbers (≈ 6 MiB publish, ≈ 1–6 ms/tick, ≈ 2,000 cap, ≈ 40 ns/entity, 3 m cell,
  the unused ≈ 44 ms) cited, not re-derived.
- Theory (read-only): `CassiTheory/speculations/qi-computation.md` §5.2
  (persistent Π patterns — the member-id's ground, with the speculation flag
  `reason-field.md` §6a carries); `CassiTheory/speculations/creative-extensions/
  magic-systems.md` §1 (the phase-matching `M` of §5).
- [`the-cart.md`](./the-cart.md) — **the load booked.** §2.1 there reads §2.1 this
  doc's op-record (a cart's load books the way any op does), §2.2 the sustain flag
  (a held load books as one standing record), §2.3 the cell-ownership rule, §3 the
  single non-forgeable point. Reverse pointer: the cart's load books on the settled
  record.
