# The Census: The Settlement's Population Read Off the Already-Booked Member Lines

**Question under design:** the corpus gives a settlement its *social reads* —
the Board books per-member contribution (`shared-ledger.md`), the Observatory
reads the window's present (`the-observatory.md`), the Chronicle records what
happened (`the-chronicle.md`), the Election reads who leads. But **nothing reads
the settlement's population as a field read**: who is here, who is absent,
whose line is fading, whether the window is growing or thinning. The per-member
lines the Board already books (`shared-ledger.md` §1.2) are a **demographic**
before any census exists — each line is a member's booked, recorded presence —
and the corpus has never read them as such. This document is that read: **the
Census, the settlement's population reading** — a designed aggregation of the
already-booked per-member lines into *who is here, who is absent, whose line is
fading, whether the window is growing or thinning*.

The load-bearing fact, stated once:

> **The Board's per-member book is a demographic read before any census
> exists.** Every member-id the world-writer attaches to a Q4 record
> (`schema-that-settles.md` §2.1) books a line that is either *currently
> contributed* (the window's working population), *long-unbooked* (a fading
> line — honestly distinct from a beginning), *closed by dissolution* (the
> departed), *a foreign provenance line* (the strangers), or *severed* (the
> exiled). The Census aggregates those already-booked states into a
> **population reading** — not new telemetry, never a new channel, but the
> Board's own book read as a demographic, the way the Weatherglass reads the
> field's `q`/`ε²` at a glance. **The Board's book at population scale is the
> settlement's pulse.**

This is the corpus's **quiet-sign doc** — the society-health read that makes a
shrinking window *readable* the way the Weatherglass makes a thinning field
readable. It is a **[design]** aggregation over the already-landed per-member
book and the settled entries — never a new channel, never new telemetry — and
its central reading is that **a shrinking window is not a crash: it is a season
where the active count trends down, the dormant count rises, and the departed's
entries accumulate.** The Census is the first honest sign of a window's fate
(`fate-of-a-window.md` §1) turning — read before the glass shows it, because
**the people thin before the field does.**

Companion to (all relative paths):
- [`shared-ledger.md`](./shared-ledger.md) — **the Census's data.** §1.2 the
  per-member net `C(M)` per tide-cycle `[t_k, t_k+T]` (the lines the Census
  reads); §2.2 the four member-identities (steward, neutral, margin-causer,
  dissolved) and the **Dissolved** entry — the departed class's settled close;
  §6b the **Phase-1-able aggregation slice** (render one member's contribution
  from the first windowed demo — the Census's own Phase-1 slice rides it);
  §6c the **landed member-id** (the line the Census aggregates against); §3.3/
  §6e the **misattribution ethics** — the Census must not read an empty row as a
  negative, inherited into the dormant class.
- [`the-child.md`](./the-child.md) — **§2.3/§6e the empty-row rule.** An empty
  `C(M)` row reads as *unbooked* — "a beginning, never a blank or a blame." **The
  Census inherits this rule into its dormant class:** a long-unbooked line is
  *not* a negative or a defection — it is a line that may be about to begin. The
  honest distinction (a child about to begin vs. a member who has stopped) is the
  dormancy read's spine.
- [`the-funeral.md`](./the-funeral.md) — **§2.2 the dissolved line settled.** The
  departing class: a member whose Π-pattern run ended, the balance settling
  against the bath. The Census's **departed** class is the Board's Dissolved
  entry read at population scale — the accumulating settled lines.
- [`window-guests.md`](./window-guests.md) — **§3 the visitor line.** The
  **strangers** class: a foreign identity that books with provenance
  (a provenance flag **[design]** over the settled record), never folded into a
  resident line. The Census reads the foreign lines' provenance.
- [`fate-of-a-window.md`](./fate-of-a-window.md) — **§1 the arcs.** A shrinking
  active count is the **strain/decay arc** turning (§1.3) — the Census is the
  population-level first-honest-sign of the fate's direction, read before the
  glass shows it.
- [`the-observatory.md`](./the-observatory.md) — **§2 the composed display.**
  The Census is a **new surface of the settlement's self-portrait** — the
  Observatory's demographic face, mounted beside the map and the mirror.
- [`the-election.md`](./the-election.md) — **§2/§2.4 the read needs a history.**
  The Census is the **population-level history** the candidate-read sits on —
  the many-tide book over the whole community, not one member.
- Skim as needed: [`the-cold.md`](./the-cold.md) (**§1/§5 the long thin** — what
  *thins* a settlement, not what kills it — the Census's honest subject;
  §5(e) the Board's per-tide `C(M)` summed across the cold), [`the-exile.md`](./the-exile.md)
  (**§4 the severed line** — the exiled class, honestly). [`tide-of-the-attractor.md`](./tide-of-the-attractor.md)
  (the tide as the census's accounting cycle — contribution read per-tide.

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(the canonical set — cited, not re-derived), engine-verbatim where stated, or
explicitly flagged **[design]** (this doc's designed aggregation/lens over real
channels) / **[probe]** (a measurement the design gates on) / **[assumption]**.
The honest boundary is drawn in §4 and never blurred: **the per-member lines and
the settled entries are [design]-landed over the engine-real Q4 op-stream
(`shared-ledger.md` §6c; `schema-that-settles.md` §2.1); the child's empty-row
rule and the misattribution ethics are inherited; the Census's *class aggregation
and quiet-sign read* are this document's [design] over that book.** It is a
*read*, never a new physics: the Census adds no channel, no write, no term — it
aggregates the lines the Board already books.

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| A settlement's population = ? | **The aggregation of the already-booked per-member lines** (`shared-ledger.md` §1.2) — a demographic read of *who is here, who is absent, whose line is fading, whether the window is growing or thinning*. |
| The Census = ? | the **population reading** — a designed aggregation of the board's book into **five classes**: the **active** (booked this tide — the window's working population), the **dormant** (long-unbooked — the child's empty-row honesty inherited), the **departed** (dissolved lines settled), the **strangers** (visitor lines with provenance), and the **exiled** (severed lines). |
| What it reads | the already-booked per-member lines and settled entries — **never new telemetry, never a new channel** (the family rule, `shared-ledger.md` §6). The Board's book at population scale. |
| The quiet signs | a shrinking window is **not a crash — a season** where the active count trends down, the dormant count rises, the departed's entries accumulate — the quiet signs the event-mechanics never catch, the cold's honesty at population scale. |
| The first-honest-sign | the Census is the first honest indicator of the fate's **strain/decay arc** turning (`fate-of-a-window.md` §1) — read before the glass shows it, because **the people thin before the field does**. |
| The honest boundary | the per-member lines + settled entries are [design]-landed over the Q4 lane; the child's empty-row rule and misattribution ethics are inherited; **the class aggregation and quiet-sign read are this doc's [design]** over the book — deterministic (same book → same census), never a new channel, never new telemetry. |
| Honest gates | (a) the [design]/engine-real line; (b) **PHASE-1-LEAN** — a demographic aggregation over the settled per-member lines is a bounded read, gated on the Board's aggregation slice (`shared-ledger.md` §6b) and the settled dissolution entries — the **Phase-1 slice: the active/dormant/departed count over the first windowed demo's member lines**; (c) determinism; (d) the no-free-energy cap (a census informs, never mints); (e) accessibility (the census is the Board's book at population scale — never hidden-only). |
| Feasibility | **PHASE-1-LEAN with a Phase-1 slice — the society's pulse.** A bounded demographic aggregation over lines the Board already books; the population reading designable and demoable now against the landed member-id and the Board's slice. State both (§7). |

---

## 1. The Census, stated once

The corpus's society reads its *members* and its *window*, but not its
*population*. The Board renders each member's net `C(M)` over a tide
(`shared-ledger.md` §1.2) — a per-line book. The Observatory reads the window's
present across the instrument stack (`the-observatory.md` §2). The Chronicle
records what happened (`the-chronicle.md`). The Election reads who should lead,
off the many-tide book (`the-election.md` §2). But **who is here — the count
that is a settlement's own pulse — has never been read as a field quantity.**

> **The Census is the settlement's population as a field read: a designed
> aggregation of the already-booked per-member lines into a *population
> reading* — the active (members who booked a contribution this tide), the
> dormant (long-unbooked), the departed (lines closed by dissolution), the
> strangers (visitor lines with provenance), and the exiled (severed lines).** It
> is the Board's book read as a demographic — the Weatherglass's glanceability
> applied to the society's numbers — the answer to "how is the settlement doing"
> not in the field's `q`/`ε²` but in its *people*.

**Why it is the quiet-sign doc.** The corpus's event-mechanics catch what
*happens* to a settlement — the storm's front, the desert's collapse, the Coda's
precipitation (`field-hazards.md`; `signature-predator.md`). The Cold catches
what *wears* it (`the-cold.md` §1 — "not what kills you, but what wears a
settlement thin"). The Census catches what *thins* it — **the population-level
shape before any event lands**: the active count that trends quietly down, the
dormant count that rises, the departed's settled entries that accumulate. Where
the event-mechanics read the field's *extremes*, the Census reads the society's
*ordinary drift* — and that drift is the first honest sign of a window's fate
turning.

> **A shrinking window is not a crash. It is a season where the active count
> trends down, the dormant count rises, and the departed's entries
> accumulate.** The event-mechanics never catch this — no storm announces it, no
> front precedes it, no hazard threshold holds it. It is the cold's honesty at
> population scale: the settlement thins across the tide-cycles before any one
> event lands. **The Census is the first honest indicator of the fate's
> strain/decay arc turning (`fate-of-a-window.md` §1) — read before the glass
> shows it, because the people thin before the field does.**

**[design]** What is engine-real / [design]-landed: the Q4 single-writer op-stream
(`async-field-domain.md` §7 Q4), the `member` field attached at the world-writer's
write (`schema-that-settles.md` §2.1), the per-member net `C(M)` aggregation
(`shared-ledger.md` §1.2), the **Dissolved** entry (`shared-ledger.md` §2.2), and
the visitor line's provenance flag (`window-guests.md` §3). What is *this doc's*
[design]: **the class aggregation and the quiet-sign read** — the naming of a
booked line as *dormant*, *departed*, *stranger*, or *exiled*, and the reading of
the active/dormant/departed trend as the fate's early sign. No claim here
pretends the engine writes "census," "demographic," or "dormant" records today.

---

## 2. The classes — each a designed read over the already-booked lines

Each class is a **designed read over the already-booked per-member lines** —
never new telemetry, never a new channel (the family rule, `shared-ledger.md`
§6 — the Census like the Board is a consumer of the published Q4 book). The
book's states are, per `shared-ledger.md` §1.2/§2.2 and the landed member-id:

| Class | The booked read | The honest rule it inherits | Cross-ref |
|---|---|---|---|
| **The active** | members who **booked a contribution this tide** — a net `C(M)` (any direction) over `[t_k, t_k+T]` | the window's **working population**; read per-tide against the tide's accounting cycle, so "active" is a season's cohort, never a static roster | `shared-ledger.md` §1.2 (the per-tide `C(M)`); `tide-of-the-attractor.md` (the accounting cycle) |
| **The dormant** | members who are **long-unbooked** — no net contribution over many tides | **the child's empty-row honesty inherited** (`the-child.md` §2.3/§6e): an empty row reads as *unbooked*, never blank, never blame — but a *long*-unbooked line is a fading one; the honest distinction between "a child about to begin" and "a member who has stopped" | `the-child.md` §2.3/§6e (the empty-row rule); `shared-ledger.md` §3.3 (the pattern guard — a dormant line is a *pattern over many tides*, never one empty tide) |
| **The departed** | lines **closed by dissolution** — the Board's **Dissolved** entry, the balance settling against the bath | **the funeral's settled entry** (`the-funeral.md` §2.2): not a silent drop, a *settled* close; the departed class is the accumulating set of those settled lines | `shared-ledger.md` §2.2 (the Dissolved entry); `the-funeral.md` §2.2 (the settled close); `player-remains.md` §2/§3 |
| **The strangers** | the **visitor lines** — foreign identities that book with a provenance flag (**[design]** over the settled record) | **window-guests' provenance** (`window-guests.md` §3): a contribution with provenance, not a resident — never folded into the resident books; the strangers class reads the *provenance*, so the window knows *where the lines came from* | `window-guests.md` §3 (the visitor line, provenance flag); `schema-that-settles.md` §2.1 |
| **The exiled** | lines **severed** — the settlement's coordinated hollow-eye closed the line by decision | **the exile's severed line** (`the-exile.md` §4): a guest-of-nowhere, a line closed *from* the commons; the exiled class reads the severed close honestly (a distinct class from the departed — dissolved by death vs. severed by decision) | `the-exile.md` §1/§3.3/§4 (the close, the guest-of-nowhere, the settled-by-decision); `schema-that-settles.md` §2.1.1 (no amnesty — an exiled line's record persists) |

### 2.1 The active — the window's working population

The **active** class is the simplest and the most load-bearing: **members who
booked a contribution this tide** — a net `C(M)` over `[t_k, t_k+T]`, any
direction (`shared-ledger.md` §1.2). It is the window's *working population*: the
count of lines that actually acted in the shared field this season. It is read
**per-tide**, against the tide's accounting cycle (`tide-of-the-attractor.md`),
so it is a season's cohort, never a static roster — the correct denominator for
every other class. A window whose active count holds steady or grows is a window
whose people are present; a window whose active count trends down is a window
whose people are leaving, one silence at a time (§3).

**[design]** The *tide-window boundary* of "this tide" is the tide's
`[t_k, t_k+T]` accounting cycle, already the Board's aggregation period —
the Census reads the same window the Board does, so "active" aligns exactly
with "booked a `C(M)` this tide." No new time unit.

### 2.2 The dormant — the empty-row honesty, inherited; and the fading line, honestly

The **dormant** class is where the Census must be sharpest, because it inherits
the corpus's single most important honesty rule — and must use it without
blunting it.

`the-child.md` §2.3/§6e states the empty-row rule: **an empty `C(M)` row reads
as *unbooked* — "a beginning, never a blank or a blame."** A child has no row
because it has never booked; a reborn line has no *this-tide* row because it has
not yet acted. **The Census inherits this rule wholesale** — a member with no
entry this tide is *unbooked*, never a non-member, never a negative
(`shared-ledger.md` §3.3's misattribution guard applied at population scale: the
Census must not read an empty row as a defection).

But the sharpest honesty the Census owns — the one that earns it its name — is
the honest distinction the child's doc leaves open (`the-child.md` §7 open-Q2:
"does a long-unbooked child row read as 'unoccupied member' or 'not yet
begun'?"). **The Census draws that line by duration:**

> **An empty row is *unbooked* — a line with no booking this tide. A
> *long*-unbooked line (no net `C(M)` over many tides) is a *fading line* — the
> honest distinction between "a child about to begin" and "a member who has
> stopped."** No line is read as *negative*; no line is read as *abandoned* in
> the blame sense. But a window that watches many of its lines go silent, tide
> after tide, is watching its active population drain into the dormant class —
> and that is a quiet sign, not a judgment (the child's honesty inherited: the
> *read* is recorded, never the blame).

The dormant class is therefore **two honest sub-reads from the same booked
data**: the **young-unbooked** (a line with no booking this tide that is
consistent with a beginning — a child, a reborn, a newly-arrived — `the-child.md`
§3) and the **fading** (a line *long*-unbooked, whose silence is a trend, not a
first). The *distinction's threshold* — how many tides of silence before
"about to begin" becomes "has stopped" — is a **[design]** dial against the
tide's measured period (`the-child.md` §7 open-Q2, the board's own stewardship
read extended to the census). It is set so a season's thin trough reads as
*quiet*, not *empty* — the cold's own floor discipline applied to people
(`tide-of-the-attractor.md` §5c; `the-cold.md` open-Q1's boundary).

### 2.3 The departed — the dissolved lines, settled and accumulating

The **departed** class is the Board's **Dissolved** entry read at population
scale (`shared-ledger.md` §2.2: "the member's Π-pattern run ended — the balance
settles against the bath on death"). The funeral settles the line by a
coordinated op (`the-funeral.md` §2.2) — a death is not a silent drop but a
*settled close*. The departed class is the **accumulating set of those settled
lines**: every dissolution the window settles, booked as a closed line.

The departed count is the Census's load-bearing *accumulator*. It is not a
judgment on any one death — death is a field act, honestly settled
(`player-remains.md` §1) — but **the *trend* of the departed class is a quiet
sign**: a window whose passed lines accumulate faster than its arriving ones is
a window whose population is not being replenished. That is the fate's decay arc
read in people (`fate-of-a-window.md` §1.3 — a decaying window's deaths become
its residue). **[design]** The departed class reads exactly the settled Dissolved
entries — no re-classification, no blame, the funeral's honesty that a settled
line is *settled*, not *lost*.

### 2.4 The strangers — the visitor lines, read by provenance

The **strangers** class is the visitor lines (`window-guests.md` §3): foreign
identities that book on the window's book with a **provenance flag** — **[design]**
over the settled record, never a new canonical field. A stranger's `C(M)`-round
is real (a contribution to / drain on the window's bath) but is attributed to a
**visitor line**, never folded into a resident book (§3.1 — "a contribution with
provenance, not a resident").

The Census reads the strangers as **the demographic's provenance surface**: the
count of foreign lines and *where they came from* — the window's openness to the
wider field made a readable number. A window with a steady stranger presence is a
window in conversation with other windows; a window whose stranger count rises as
its own active count falls is — honestly read — a window whose own lines are
thinning while other fields' lines visit, the quiet outward sign of a fate
shifting (`fate-of-a-window.md` §1 — the depart-and-rehome arc's population
face). The strangers class inherits `window-guests.md`'s guard entire: a
stranger's carried foreign ε² must never read as a resident's drain
(`shared-ledger.md` §3.3/§6e), and a stranger becomes resident only by decision,
never by duration (§3.2). **[design]** The *provenance read* (which origin-window
a visitor line is from) is `window-guests.md`'s designed presentation, read at
count.

### 2.5 The exiled — the severed line, honestly the fifth class

The **exiled** class is the severed line — the settlement's coordinated hollow-eye
closed a member's line *from* the commons (`the-exile.md` §3.3), by **decision**,
not by death. The Census reads it as a **distinct fifth class**, honestly:

> **The departed dissolved by death; the exiled severed by decision.** Both
> close a line; the departed's close is a settled field act (`player-remains.md`;
> `the-funeral.md` §2.2), the exiled's close is a *settled-by-decision* entry
> (`the-exile.md` §3.3), never amnesty, never erased — the record persists
> (`schema-that-settles.md` §2.1.1). The Census keeps them separate so the
> departed count (the field's losses, honestly settled) and the exiled count (the
> society's deliberate severances) are never conflated into one "gone" number.

The exiled class inherits the exile's hard ethics, verbatim: an exile is provable
from the book, never fiat; the misattribution guards are never relaxed for the
harder class (`the-exile.md` §2/§6b). The Census *counts* the severed lines
honestly — it never reads an exiled line as a departed one, and never
retroactively softens a severance into a loss. **[design]** The exiled class's
distinction (severed-by-decision vs. dissolved-by-death) is this doc's designed
read of the two distinct close kinds the book already books.

---

## 3. The quiet signs — what a demographic read shows

The Census exists to make the fate's ordinary drift *readable*. The event-
mechanics catch the field's extremes; the Census catches the society's
nonevent — the quiet thinning that no hazard threshold holds.

> **A shrinking window is not a crash. It is a season where the active count
> trends down, the dormant count rises, and the departed's entries
> accumulate.** No storm announces it; no front precedes it. It is the cold's
> honesty at population scale (`the-cold.md` §1 — "not what kills you, but what
> wears a settlement thin"): the *people* thin across the tide-cycles before any
> event lands.

Three quiet signs, each a trend over the per-tide classes (§2), each read the
way the Board reads its own book (`shared-ledger.md` §3.3 — a *pattern over many
tides*, never a single event):

| Quiet sign | The read | The fate it signals |
|---|---|---|
| **The active count trends down** | the working population shrinks tide over tide — fewer lines booking a contribution each season | the window's people are withdrawing; the **strain/decay arc's** population face (`fate-of-a-window.md` §1.3) — the first honest sign, months of tides before the field's `q` reads it |
| **The dormant count rises** | the young-unbooked grow old-unbooked; the "about to begin" lines stay silent into the "has stopped" — the fading class accumulates | the window is emptying from within — not by death, but by stillness; the drift toward the field-poor that is the decay arc's seed (`field-hazards.md` §3.2; `fate-of-a-window.md` §1.3) |
| **The departed's entries accumulate** | the settled Dissolved lines (and, honestly told, the severed exiled ones) outpace the arriving fresh lines | the window is not being replenished — a population that ends closes to the field-poor state (`the-cold.md` — a settlement thins through the decade; `fate-of-a-window.md` §1.3) |

**Why the Census reads before the field does.** The fate is a read of the
window's coherence economics `C(W)`, summed over the op-stream and the bath's
`q`/`ε²`, read forward (`fate-of-a-window.md` §1). But the *people* move first:
a member stops channeling (the active count dips) before a bath's `q` decays
appreciably; a settlement that never fully returns from a thin tide is already a
settlement whose population thin is legible as an active-count trend, seasons
before the glass's `(1−q)` glow reads as a cold. **Because the op-stream is the
single-writer record of who actually acted, the Census sees the population turn
the moment the last contributions stop — a leading indicator the field's `q` lags.**
This is the honest claim, stated without overreach: the Census does not *predict*
the fate's full arc (that is the oracle's forward-read, `fate-of-a-window.md`
§6c); it reads the *early* sign — the strain/decay arc turning in people, the 
quiet thinning that precedes the field's own reading.

**[design]** The *quiet-sign aggregation* (the per-tide class counts + the 
trends) is this doc's designed reading of the book; the *population turn itself*
(that an active-count dip precedes a bath decay) is an honest consequence of the
single-writer op-stream being the real record of action — a [design] reading of
a real precedence. **[probe]** Whether the active-count trend *systematically*
leads the field's `q` trend is a Phase-1 measurement (does an active dip precede
a bath decay in the living-terrain demo?), recorded honestly — the quiet-sign
claim stands as a *designed early-warning idiom* even if the lead-time proves
variable.

---

## 4. The honest boundary

The [design]/engine-real line, drawn once and never blurred:

| Layer | Status | Basis |
|---|---|---|
| The Q4 single-writer op-stream; the `q`/`ε²`/`ρ`/`∇(g·Φ)` publish | **engine-real** | `async-field-domain.md` §5.2/§7 Q4; `corpus-reconciliation.md` (the ≈ 6 MiB publish, the ≈ 1–6 ms/tick budget) |
| The **member-id** on records, attached at the world-writer's write | **[design], landed** | `schema-that-settles.md` §2.1 (the line the Census aggregates against); §2.1.1 the same-member-line rule; §2.3 the cell-ownership rule |
| The **per-member net `C(M)`** per tide and the **Dissolved/settled entries** | **[design]-landed over the Q4 op-stream** | `shared-ledger.md` §1.2/§2.2/§6c; `the-funeral.md` §2.2 |
| The **provenance flag** on the visitor line | **[design]** over the settled record | `window-guests.md` §3 |
| The **empty-row rule** (unbooked ≠ negative) and the **misattribution ethics** | **inherited** | `the-child.md` §2.3/§6e; `shared-ledger.md` §3.3/§6e |
| **The Census's class aggregation and quiet-sign read** — the naming of a booked line as active/dormant/departed/stranger/exiled, and the reading of the per-tide class trend as the fate's early sign | **[design]** over the above | **this doc** — a deterministic aggregation of the already-booked lines, never a new channel, never new telemetry |

**The boundary, stated once.** The per-member lines and the settled entries are
`[design]`-landed over the engine-real Q4 op-stream; the child's empty-row rule
and the misattribution ethics are inherited; **the Census's class aggregation and
the quiet-sign read are this doc's [design] over that book** — deterministic
(same book, same field state → same census — a hard gate), never a new channel,
never new telemetry. No claim here pretends the engine writes "census" or
"dormant" or "demographic" records, or that the field "knows" a member has
stopped; the field holds the op-stream, and the Census reads the already-booked
lines as a population.

---

## 5. The composition — the Census among the settlement's reads

The Census is not a solo instrument; it composes with the settlement's existing
reads as their **population face**.

| Composes with | The composition | Cross-ref |
|---|---|---|
| **The Observatory** | the Census is the settlement's self-portrait's **demographic surface** — mounted beside the map wall and the mirror's lume, the room gains a *population face*: the active count, the dormant shadow, the departed's settled roster, the strangers' provenance, read at a glance the way the room reads the field | `the-observatory.md` §2 (the composed display); §3 (where a settlement reads together) |
| **The Election** | the Census is the **population-level history** the candidate-read sits on — the election composes running `C(M)` + stewardship history + momentum (the-election §2); the Census provides the *community's* multi-tide background the candidate's line is read against — who was active, who faded, who departed, across the many tides | `the-election.md` §2/§2.4 (patterns over many tides; the read needs a history); §6e (the Board's public book) |
| **The Fate** | the Census is the fate's **early-warning population face** — the strain/decay arc's first-honest-sign, read before the glass shows it (§3); the fate's `C(W)` reads the field's economics, the Census reads the people who feed them | `fate-of-a-window.md` §1/§1.3 (the arcs; the strain/decay turning); §6(e) (the fate is a layer, never the only channel) |
| **The Chronicle** | the Census feeds the record — the demographic trend is the Chronicle's population chapter (who was here, who left) | `the-chronicle.md` (the settlement's record) |
| **The Cold** | the Census is the cold's population honesty made readable per-tide — a window thins through a cold, and the active/dormant trend *is* that thinning | `the-cold.md` §1/§5(e); §5.3 (husbandry is spent, never free) |

**The Observatory's demographic face (the composition, stated).** `the-observatory.md`
§2 composes the whole instrument stack into the settlement's self-portrait — the
map wall (the body), the clock (the tempo), the glass's core (the bath), the
mirror's lume (the community's own maintenance). **The Census is the room's
population face** — a surface that reads not the field's `q` but the society's
*count*, mounted where the settlement reads together, so the room tells not just
*how the field is* but *how the people are*. The election's candidate-read sits
on the population-level record the Census aggregates; the fate's early sign is
the quiet-sign read the Census makes legible. **The settlement's self-portrait
gains its population face — and with it the first honest sign of its fate.**

**[design]** The *composition* (which surfaces the Census mounts beside, how it
renders next to the map/mirror) is this doc's [design] over the Observatory's own
composition (`the-observatory.md` §4's [design] line); the *class reads* the
Census presents are the landed book.

---

## 6. Honest gates

### (a) The [design]/engine-real line

Drawn in §4 and never blurred. The Q4 lane is engine-real; the member-id and the
per-member/settled book are [design]-landed; the empty-row rule and misattribution
ethics are inherited; **the class aggregation and quiet-sign read are this doc's
[design]** — a deterministic aggregation over the already-booked lines, never a
new channel, never new telemetry, never a new instrument that asks the field to
talk more (the family rule, `shared-ledger.md` §6 / `field-instruments.md` §2.1).

### (b) PHASE-1-LEAN — a demographic aggregation over the settled per-member lines

The Census is **Phase-1-lean** because it is a **bounded aggregation over lines
the Board already books** — the purest consumer the corpus has, reading book-free
the very records the ledger's §6b slice already renders. The honest framing:

> **A demographic aggregation over the settled per-member lines is a bounded
> read — gated on the Board's aggregation slice (`shared-ledger.md` §6b) and the
> settled dissolution entries (`the-funeral.md` §2.2).** It needs nothing new:
> the landed member-id (`schema-that-settles.md` §2.1), the per-tide `C(M)`
> aggregation (`shared-ledger.md` §1.2), the Dissolved entry (§2.2), and the
> provenance flag on the visitor line (`window-guests.md` §3) — all pieces the
> corpus already ships.

**The Phase-1 slice, stated concretely: the active/dormant/departed count over
the first windowed demo's member lines.** Render one windowed demo's member lines
as the three primary classes — the **active** (who booked this tide), the
**dormant** (long-unbooked, the young-vs-fading distinction's Phase-1 seed), and
the **departed** (the settled Dissolved entries) — over the landed per-member
book and the settled entries, exactly as `shared-ledger.md` §6b renders one
member's `C(M)` line from the first demo. The strangers (a provenance flag on a
foreign line) and the exiled (a severed close) read the same book and are
**statable now** but **mechanically-gated** on the visitor line and the hollow-eye
being live (`window-guests.md` §6b LATER; `the-exile.md` §6b MEDIUM-LATE) — so
the Phase-1 slice ships the three core classes and the strangers/exiled as
designed, honest classes over the same aggregation. The slice de-risks the whole
population read: prove the class aggregation and the quiet-sign trend are
deterministic and legible on a single windowed demo before the society's live
multi-member read rides it.

### (c) Determinism — same book, same field state → same census

The field is deterministic (one PDE; `field-archaeology.md` §1.2; `shared-ledger.md`
§6 — the schema adds no nondeterminism). Inherited as a **hard gate**:

> **Same book, same field state → same census.** The per-member lines are the
> deterministic sum of the executed op-stream (`schema-that-settles.md` §6b); the
> class aggregation is a pure function of those lines and the settled entries; the
> quiet-sign trend is a deterministic read of the per-tide class counts. A
> reloaded window at the same book and field state reads the same active/dormant/
> departed/stranger/exiled counts, every run. There is no seeded-RNG luck about
> the settlement's population being counted one way or another — the book either
> shows a line as active this tide or it doesn't. **[design]** The *dormancy
> threshold* (how many silent tides before "about to begin" reads as "has
> stopped") is a designed dial, but once set the census is deterministic.

### (d) The no-free-energy cap — a census informs, never mints

`energy-harnessing.md` §6 (`output ≤ φ⁻¹·input`), inherited unchanged:

> **A census informs, never mints.** It is a *read* of the already-booked lines
> composed into a count — it converts no coherence, absorbs no drain, writes
> nothing, and grants the settlement no power, budget, or recovery it did not
> earn in the field. Counting the active population does not raise the window's
> `q`; knowing the dormant count does not re-activate a fading line (re-activating
> it is a member's own future channeling); knowing the departed count does not
> settle a line that is not yet settled. There is no "build a census to farm a
> read," no "counting that mints coherence" — information is not energy
> (`tide-of-the-attractor.md` §5d), exactly why the Census is Phase-1-lean and
> never corrupts the economy.

### (e) Accessibility — the census is the Board's book at population scale, never hidden-only

Per the instrument-family rule (`field-instruments.md` §2.1) and `shared-ledger.md`
§6e:

> **The Census is the Board's book at population scale — never hidden-only.** It
> presents, at a glance, what the mounted Coherence Board already books per
> member (`shared-ledger.md` §2.1): the active count is the sum of the tide's
> booked `C(M)` lines; the dormant is the sum of the long-empty rows, readable
> as the Board's unbooked rows made a count; the departed is the Dissolved
> entries' accumulation; the strangers read on the provenance-tagged visitor
> lines; the exiled on the severed closes. A settlement member who never uses a
> "census" surface loses nothing the Board's book does not already show, more
> laboriously — the population reading is an *idiom over the public book*, never
> a second, hidden information source. A census that hid its count would be a
> secret population the design's own honesty forbids.

---

## 7. Feasibility verdict

**PHASE-1-LEAN with a Phase-1 slice — the society's pulse. State both.**

**The Census is PHASE-1-LEAN** because it is the purest consumer in the corpus:
a bounded demographic aggregation over lines the Board already books
(`shared-ledger.md` §1.2/§2.2), the landed member-id, and the settled entries —
reading book-free the very records the ledger's §6b slice already renders. It
introduces **no new channel, no new physics, no new telemetry, no write** — it
is the Board's book read as a demographic, on the cost profile of the Board's own
aggregation slice (the ≈ 6 MiB publish, inside the ≈ 1–6 ms/tick sample budget,
`corpus-reconciliation.md`). The strangers and exiled classes ride their source
docs' gates (the visitor line, `window-guests.md` §6b LATER; the severed close,
`the-exile.md` §6b MEDIUM-LATE); the three core classes — active/dormant/departed
— are Phase-1-able now.

| Class | What it is | Gate | Phase |
|---|---|---|---|
| **The active / dormant / departed counts** over the per-member book and the settled entries | the Phase-1 slice — the three primary classes read from the landed `C(M)` book + the Dissolved entries | the Board's aggregation slice (`shared-ledger.md` §6b); the landed member-id (`schema-that-settles.md` §2.1); the settled Dissolved entries (`the-funeral.md` §2.2) | **Phase-1** (the slice: the active/dormant/departed count over the first windowed demo's member lines) |
| **The strangers** (visitor lines, provenance) | the foreign-line count read by provenance | the visitor line's provenance flag (`window-guests.md` §3 — designable book, mechanically-gated) | **Phase-1-able as a designed book** / LATER as a *live foreign line* |
| **The exiled** (severed lines) | the severed-by-decision close, honestly distinct from the departed | the hollow-eye + the severed close (`the-exile.md` §6b) | **MEDIUM-LATE** (inherits the exile) |
| **The quiet-sign trend** (active-down / dormant-up / departed-accumulating) | the per-tide trend read as the fate's early sign | the deterministic per-tide class counts + the [design] trend threshold | **Phase-1** (the trend over the slice's counts; the lead-time probe §3 is [probe]) |
| **The composition** — the Observatory's demographic face, the election's population history, the fate's early warning | the class read mounted as the settlement's self-portrait population surface | each ride its own doc's gates (the Observatory PHASE-1-LEAN; the election MEDIUM-LATE; the fate MEDIUM-LATE) | **PHASE-1** (the surface) / inherited for the acts that use it |

**The honest slice, stated:** **PHASE-1-LEAN** means the first windowed demo's
member lines, read as the active/dormant/departed counts over the landed book and
the settled entries — shipped as a bounded consumer, with the strangers and
exiled held as designed classes over the same aggregation, and the quiet-sign
trend read over the slice's per-tide counts. The *designed statement* is the
Phase-1 gain: **the Census makes the settlement's population a readable
quantity** — the Board's book at population scale, the first honest sign of a
window's fate turning, the society's pulse. **What is LATER** is the live
society-read — the multi-member demographics, the foreign-line provenance at
scale, the exile's severed count — each inheriting its source doc's gates.

**Binding risks, in order:**
1. **The dormant/thinning misread (§2.2/§3)** — the sharpest failure is the
   Census reading a *long-unbooked line* as a negative or a defection instead of
   a *fading line honestly* (the child's empty-row rule inherited) — an empty
   row must read *unbooked*, never blank, never blame (`shared-ledger.md` §3.3's
   pattern guard held at population scale, exactly as the Board holds it per
   member). The moment a "dormant count" reads as guilt, the Census breaks its
   own most load-bearing honesty.
2. **The quiet-sign overclaim (§3)** — the Census reads the *early* sign (the
   population turn precedes the field's), and it must not slip into predicting
   the fate's full arc (that is the oracle's forward-read, `fate-of-a-window.md`
   §6c). The lead-time is a **[probe]**, honestly recorded; the quiet-sign is a
   *designed early-warning idiom* either way, never a forecast dressed as one.
3. **The [design] line (§4)** — keeping the class aggregation and quiet-sign read
   strictly [design] over the landed book (the member-id, the `C(M)`, the
   Dissolved entries, the provenance flag), so the corpus never reads a Census
   as an engine data type or a hidden population meter.
4. **The class mis-separation (§2.5)** — the departed (dissolved by death, settled)
   and the exiled (severed by decision) must never conflate into one "gone"
   number, or the window's honest losses and its deliberate severances blur. The
   distinct close kinds the book already books are the honest spine.
5. **The no-free-energy gate (§6d)** — the Census must never read as a mint, a
   farmable "population bonus," or an office that generates a recoverable
   resource; it informs, never mints, and information is not energy.

**None contradicts the async, dual-world, or regime-collapse architecture** — the
Census adds no physics and no channel: it is a deterministic aggregation of the
already-booked per-member lines (`shared-ledger.md` §1.2/§6c), the settled
Dissolved entries (`the-funeral.md` §2.2), the provenance-tagged visitor lines
(`window-guests.md` §3), and the severed closes (`the-exile.md` §3.3), bounded by
the no-free-energy cap (`energy-harnessing.md` §6), timed to the tide's
accounting cycle (`tide-of-the-attractor.md`), and composed into the
Observatory's self-portrait (`the-observatory.md` §2). **The Census is the
society's pulse because it is the *right use of the book the society already
keeps* — the missing read that turns a per-member ledger into a population
reading, and with it the first honest sign of a window's fate turning.**

> **The honest statement that makes this doc load-bearing: the corpus reads a
> settlement's members (the Board's per-member `C(M)`), its window (the
> Observatory's composed display), its record (the Chronicle), and its candidates
> (the Election) — but never its *population*. The settlement's people, as a
> count that lives and thins, were unread. The Census closes that hole the
> thesis-true way: the population is a designed aggregation of the already-booked
> per-member lines — the active (who booked this tide), the dormant (long-
> unbooked, the child's empty-row honesty inherited — never a negative, but a
> long-silent line is a fading one), the departed (the settled Dissolved lines),
> the strangers (the visitor lines with provenance), and the exiled (the severed
> lines). It is the Board's book read as a demographic — the settlement's pulse —
> and its quiet-sign read is the first honest indicator of a window's fate
> turning: a shrinking window is not a crash, it is a season where the active
> count trends down, the dormant count rises, and the departed's entries
> accumulate, read before the glass shows it because the people thin before the
> field does. It composes with the Observatory's self-portrait as the
> population face, with the Election's candidate-read as the population-level
> history, and with the Fate as the early-warning sign. It is deterministic
> (same book, same field state → same census), public (the Board's book at
> population scale, never hidden), and non-minting (a census informs, never
> mints). PHASE-1-LEAN with a Phase-1 slice — the active/dormant/departed count
> over the first windowed demo's member lines — the society's pulse, named.**

---

## Open questions

1. **The dormancy threshold — when "about to begin" becomes "has stopped."** How
   many successive silent tides before a long-unbooked line reads as *fading*
   rather than *beginning*? It is the Census's sharpest [design] dial, set
   against the tide's measured period (`tide-of-the-attractor.md` §5b) so a
   season's thin trough reads as *quiet*, never *empty* — the same
   two-margins-set-together discipline as the cold's boundary
   (`the-cold.md` open-Q1) and the Board's `C(M) < 0` line
   (`shared-ledger.md` §7 open-Q2). **[design]/[probe]**
2. **The lead-time probe.** Does an active-count dip *systematically* precede a
   bath's `q` decay in the living-terrain demo — the quiet-sign claim's measured
   lead? A negative (the population and the field turn together) would not kill
   the Census — it would weaken the *early-warning* claim to a *coincident* one —
   and the design prefers the honest reading. **[probe]**
3. **The young-vs-fading sub-read's source.** The dormant class's honest
   distinction (a child / a reborn / a newly-arrived line vs. a long-stopped
   member) needs a designed read over the *same* book — does the Census
   distinguish them by the *same-member-line* rule (`schema-that-settles.md`
   §2.1.1: a child is a line's first lock, a reborn is a re-bound lock) and the
   visitor line (`window-guests.md` §3 — a newly-arrived stranger books as a
   visitor, not a dormant resident)? The distinction is a [design] read over the
   settled record; `the-child.md` §7 open-Q2 is the upstream owner. **[design]**
4. **The composed surface (§5).** Is the Census mounted as the Observatory's
   *fourth* surface (beside the map wall, the clock, the mirror), or does it
   render *into* the mirror's aggregated lume (the community self-read,
   `the-observatory.md` open-Q3's aggregation rule)? The former keeps the count
   distinct; the latter folds the demographic into the maintenance read. The
   composition is a [design] dial between this doc and the Observatory's own
   composition question; the *read* is the landed book either way. **[design]**
5. **The strangers' provenance at scale (§2.4).** How fine-grained does the
   provenance read need to be for the Census to be honest — *that* a line is
   foreign (count + origin-window), or the full `window-guests.md` §3 provenance
   presentation? The window's openness-number needs the former; a full foreign-
   line legibility would blur into the guest doc's own presentation. Inherits
   `window-guests.md` §3/§6b's designable-now vs. mechanical-LATER split.
   **[design]**

---

## Cross-references

- [`shared-ledger.md`](./shared-ledger.md) — **the book the Census reads.** §1.2
  the per-member net `C(M)` per tide (the lines the Census aggregates); §2.2 the
  four member-identities and the **Dissolved** entry (the departed class's
  settled close); §6b the **Phase-1-able aggregation slice** (the Census's own
  slice rides it); §6c the **landed member-id** (the line the Census counts);
  §3.3/§6e the **misattribution ethics** (an empty row is unbooked, never a
  negative — inherited into the dormant class); §3.3 the no-single-event guard
  (the quiet-sign trend reads a pattern over many tides).
- [`the-child.md`](./the-child.md) — **§2.3/§6e the empty-row rule.** An empty
  `C(M)` row reads as *unbooked* — "a beginning, never a blank or a blame" — the
  dormancy rule's spine (§2.2 this doc); §3 the firsts (the young-unbooked line);
  §7 open-Q2 the long-unbooked sub-read the dormancy threshold inherits.
- [`the-funeral.md`](./the-funeral.md) — **§2.2 the dissolved line settled.** The
  departed class's close; §7 the MEDIUM-LATE + Phase-1-legible framing (the
  model for this doc's).
- [`window-guests.md`](./window-guests.md) — **§3 the visitor line.** A
  contribution with provenance, not a resident — the strangers class; the
  provenance flag [design] over the settled record; §3.2 becomes-resident-by-
  decision (the strangers count stays foreign until a designed decision); §6d
  a guest's arrival perturbs, never mints.
- [`fate-of-a-window.md`](./fate-of-a-window.md) — **§1 the arcs.** The
  strain/decay arc (§1.3) whose population face the Census reads; §6c the
  forecast-≠-fate frame (the Census reads the *early sign*, never the full arc);
  §6 the fate reads the window's `C(W)`, the Census reads the people who feed it.
- [`the-observatory.md`](./the-observatory.md) — **§2 the composed display.** The
  Census as the settlement's self-portrait's **population face** (§5 this doc);
  §2.1 the family rule (the Census composes the family, never a new channel);
  open-Q3 the mirror-aggregation rule the composed surface inherits.
- [`the-election.md`](./the-election.md) — **§2/§2.4 the read needs a history.**
  The Census is the **population-level history** the candidate-read sits on —
  the many-tide book over the whole community (§5 this doc); §3.3 the pattern
  guard (shared by the quiet-sign trend).
- [`the-cold.md`](./the-cold.md) — **§1/§5 the long thin.** What *thins* a
  settlement, not what kills it — the Census's honest subject; §5(e) the Board's
  per-tide `C(M)` summed across the cold (the quiet-sign's long window);
  §7 the Phase-1-legible framing (the model for this doc's).
- [`the-exile.md`](./the-exile.md) — **§4 the severed line.** The exiled class
  (§2.5 this doc), honestly distinct from the departed; §3.3 the settled-by-
  decision close; §2/§6b the ethics inherited (an exile is provable, never fiat).
- [`the-scavenger.md`](./the-scavenger.md) — **the spent's census.** The same
  class-aggregation discipline this doc applies to the society — applied §4
  there to the spent localities' fitted denizens: a window's scavenger population
  is the honest census of its spent, a read and never a difficulty meter. Reverse
  pointer: the scavenger's population read is this doc's aggregation copied to
  the spent margin.
- [`the-window-pulse.md`](./the-window-pulse.md) — **the census's health-twin.** §2.1 there
  reads this doc's §2 five classes as the population read — the pulse's *who-is-here*;
  the pulse reads the settlement's *health*, not its count, and §3's quiet signs (the
  people thin before the field does) are the pulse's lines-drift-then-bath-fall
  leading-indicator honesty; §7's PHASE-1-LEAN verdict is the pulse's MEDIUM contrast, same
  data one scale up. Reverse pointer: the pulse is the census's sibling reading health
  rather than population.
- [`the-harbor.md`](./the-harbor.md) — **the active class at the door.** §2a there reads
  §2/§2.1 this doc's population classes as the harbor's face — the active class (members
  who booked this tide) is the departure record's face at the harbor; §3's quiet signs
  (the departures thin before the window's voyaging does); §6c determinism. Reverse
  pointer: the harbor reads the census's active class at the settlement's door.
- [`the-market.md`](./the-market.md) — **the active-class face.** §1/§2 there reads §2.1
  this doc's active class as the market's liveness — a trade is a booked op, so a lively
  market is a lively active class (§1 there); §6d there's informs-never-mints read is the
  census's §6d honestly (the market's reads are the book's, never a difficulty dial).
  Reverse pointer: the market's activity is the census's active-class read at the exchange.
- [`the-chronicle.md`](./the-chronicle.md) — **the record the Census feeds.** The
  demographic trend as the settlement's population chapter (§5 this doc); §3.3
  the dissolved-entry obituary.
- [`schema-that-settles.md`](./schema-that-settles.md) — **the schema.** §2.1 the
  landed member-id (the line the Census aggregates against); §2.1.1 the same-
  member-line rule (the young-vs-fading sub-read's source, open-Q3 this doc);
  §2.3 the cell-ownership rule; §6b the schema adds no nondeterminism (§6c this
  doc).
- [`energy-harnessing.md`](./energy-harnessing.md) — **the cap.** §4.4 the Qi
  bath; §6 the no-free-energy cap (`output ≤ φ⁻¹·input` — a census informs,
  never mints).
- [`tide-of-the-attractor.md`](./tide-of-the-attractor.md) — **the accounting
  cycle.** The Census reads `C(M)` per `[t_k, t_k+T]`; §5b the tide's measured
  period (the dormancy threshold's dial, open-Q1 this doc); §5d the no-free-
  energy/information stance (§6d this doc).
- [`field-instruments.md`](./field-instruments.md) — **the family rule §2.1**
  (the Census is a consumer with a presentation idiom, never a new channel);
  §1.3 accessibility (the Census is the Board's book at population scale, never
  hidden-only).
- [`the-commons-tithe.md`](./the-commons-tithe.md) — **the active tither.** §2 there
  reads §2.1 this doc's active class (a member who books a contribution this tide — a
  tithing member reads as a contributor) and §2.2 the dormant; §6d informs never mints.
  Reverse pointer: a tithing member reads as the census's contributor.
- [`the-archive.md`](./the-archive.md) — **the population history.** §4 there reads §2
  this doc's active/dormant/departed off the booked member-lines — the Archive holds
  the complete population history the Census counts aggregate. Reverse pointer: the
  Archive is the count's complete ground.
- [`the-granary.md`](./the-granary.md) — **the liveness's store.** §2.1 there reads
  §2.1 this doc's active class — the granary is the store that lets the market's
  liveness hold through the thin; §6e the never-hidden read. Reverse pointer: a full
  granary lets the active class's liveness hold.
- [`the-toll.md`](./the-toll.md) — **the population's door.** §2.1 there reads the
  active class (a member's crossing reads here — the tithe's internal book, not the
  toll's), §2.4 the strangers (the visitor lines the toll's payers read on), §6d a
  census informs never mints. Reverse pointer: the toll reads the census's strangers
  at the door.
- [`the-gatekeeper.md`](./the-gatekeeper.md) — **the roster's door.** §2 there reads the
  five classes (who is here); §2.1 the active (the admitted member's class); §2.4 the
  strangers — the admitted guest's provenance-read line, on the ledger, never the
  census; §7 the PHASE-1-LEAN verdict. Reverse pointer: the gatekeeper reads the
  census's admitted class at the door.
- [`the-shout.md`](./the-shout.md) — **the roster's loud call.** §2 there reads who is
  here, who answers — the shout as the census's loud call; §6d the informs-never-mints
  stance the shout's never-a-save holds. Reverse pointer: the shout calls the
  census's who-hears-who.
- [`the-archivist.md`](./the-archivist.md) — **the roster the office reads on.** §2
  there reads the five classes; §2.1 the active (the office-holder's own class); §7
  PHASE-1-LEAN. Reverse pointer: the archivist reads the census's booked lives.
- [`the-broker.md`](./the-broker.md) — **the counted visitor.** §2 there reads the five
  classes; §2.4 the strangers (the Broker's visitor line, never the active); §6d
  informs never mints. Reverse pointer: the broker reads on the census's stranger
  line.
- [`the-wage.md`](./the-wage.md) — **the paid population.** §2.1 there reads the active
  class (a paid worker reads active); §2.2 the dormant; §6d informs never mints.
  Reverse pointer: the wage's book reads on the census.
- [`the-spring-caretaker.md`](./the-spring-caretaker.md) — **the keeper on the roster.**
  §2.1 there reads the active class; §2.2 the dormant; §7 the PHASE-1-LEAN verdict.
  Reverse pointer: the caretaker books a kept contribution on the census.
- [`the-migration.md`](./the-migration.md) — **the roster.** §2 there reads the five
  classes (the migrating people's count); §1 the Board's book at population scale.
  Reverse pointer: the migration's book reads on the census.
- [`the-midwife.md`](./the-midwife.md) — **the fresh line's roster.** §2.1 the active class; §2.2 the child's empty-row honesty; §7 the PHASE-1-LEAN verdict. Reverse pointer: the midwife's first class-read gates on the census.
- [`the-inn.md`](./the-inn.md) — **the slept guest’s roster.** §2.1 the active class; §2.4 the strangers (the visitor line, never the census). Reverse pointer: a guest at the inn reads as a stranger, never a hidden resident.
- [`the-mirage.md`](./the-mirage.md) — **the counted never-lure.** §2 the classes; §6d informs never mints. Reverse pointer: the mirage never reads on the census — no resident, no counted.
- [`the-meadow.md`](./the-meadow.md) — **the grazed count.** §2 the classes (the grazers on the meadow read). Reverse pointer: the meadow’s grazers read on the census.
- [`the-cistern.md`](./the-cistern.md) — **the served roster.** §2 the classes (the settlement the cistern serves reads). Reverse pointer: the cistern serves the census’s settled.
- [`the-baptism.md`](./the-baptism.md) — **the named one’s roster.** §2.1 the active class (the first class-read the name earns); §2.2 the empty-row honesty. Reverse pointer: the baptized one first reads on the census’s active class.
- [`the-palanquin.md`](./the-palanquin.md) — **the carried on the book.** §2.1 the active class; §6/§7 the verdict. Reverse pointer: the seat carries who is on the book, legible.
- [`the-votive.md`](./the-votive.md) — **the giving on the book.** §2 the roster. Reverse pointer: the votive’s giving reads on the census’s book, never a mint.
- [`the-shrine.md`](./the-shrine.md) — **the roster’s place.** §2/§2.3 the departed class; §6c/d/e; §7 PHASE-1-LEAN. Reverse pointer: the shrine’s register presents the departed at a place — the census’s settled dissolved lines.
- [`the-hand-over.md`](./the-hand-over.md) — **the new line.** §2 the roster. Reverse pointer: a hand-over moves the census’s line — the carried turn re-booked.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — the canonical
  numbers (≈ 6 MiB publish, 64³ grid / 192³ box, `dt = 0.05`, `τ_c = 0.5`,
  `φ⁻² ≈ 0.382`, `ξ = φ⁶ ≈ 17.94`, `q ≈ 0.947` attractor, `q ~ 1e-3…1e-1` noise,
  the ≈ 1–6 ms/tick budget, the ≈ 2,000 cap) cited, not re-derived.
