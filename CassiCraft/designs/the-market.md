# The Market: The Settlement's Exchange, Made Honest by the Law Itself

**Question under design:** the corpus gives a settlement its *shared book* (the
Shared Ledger's Coherence Board, `shared-ledger.md`, reads who contributed), its
*leadership* (the Election reads who leads), its *promises* (the Oath reads what
was vowed), its *kin* (the Family reads who is bound), and its *joy* (the
Festival reads what was celebrated) — but **no exchange**: nothing designs how
*things change hands* between members. Minecraft's barter is undesigned: players
trade freely with no field consequence and no trust — a trade is just a drag-
drop with a server rule, outside the field entirely. This document designs the
Market: **the settlement's exchange designed as a field act** — a **trade
booked on the shared ledger**, made honest **by the law itself, not by
enforcement**:

> **A trade's fairness is not a rule; it is a *field property*.** Because the
> ledger's no-false-booking (schema-that-settles' op-record) books every exchange
> as `{member, op, worldPos, rung, magnitude, sustain}`, a trade *cannot be lied
> about*: the traded item's provenance is booked (the worked vein's rung, the
> harvested yield's magnitude — the tool's edge, the seed's vault-row), and the
> no-false-naming of the-name extends to goods — **you cannot falsely name what
> you offer** (honesty is thermodynamics). A market is thus **trustworthy by
> construction** — the field books the truth of every exchange, and the only
> enforcement is the book's own readability. **A trader who would cheat cannot:
> the cheat is not a rule violation, it is a *false op* the field will not
> book.**

The Market is the corpus's **trust doc** — the exchange made honest by the
law's own mechanics, never by a sheriff. It is what Minecraft's barter becomes
when every hand-change is a field-write the world's single honest book records,
read back at settlement scale.

Companion to (all relative paths):
- [`shared-ledger.md`](./shared-ledger.md) — **THE book the market writes on.**
  §1.2 the per-member net `C(M)` over the tide (the trade books into the same
  per-member read); **§2.2 the four member-identities** (a trade changes a
  member's `C(M)` read, so exchange and contribution are the same book); **§6d
  the single-writer no-false-booking** (the op-stream is unforgeable — the
  market's honesty is the ledger's own); §6c the landed member-id (the two
  hands a trade binds).
- [`schema-that-settles.md`](./schema-that-settles.md) — **THE trade's
  bookable shape.** **§2.1 the op-record `{member, op, worldPos, rung,
  magnitude, sustain}`** — the exchange *is* a Q4 op of that shape; §2.3 the
  cell-ownership rule (two members' lines never merge silent); **§3 the single
  non-forgeable point** (the world-writer's write — the market's book is
  written there, and nowhere else); §2.2 the sustain flag (a held offer's
  semantics).
- [`the-name.md`](./the-name.md) — **THE no-false-naming extended to goods.**
  §1 the Π-anchor (a named item is a held thing); **§2 you cannot name falsely
  — honesty is thermodynamics** (you cannot falsely name what you offer; a
  falsely-named offer decays); §3.2 the named contribution is legible (a
  traded, provenance-tagged item books); §6d a name holds, never mints (an
  offer's honest value is the book's read, never the trader's word).
- [`the-tool.md`](./the-tool.md) — **THE traded item's provenance.** §2 the
  edge reads where the metal came from (a traded pick's alloy-`q` is booked);
  the worked vein's rung booked into the item; §4b the Phase-1-able slice.
- [`seed-garden.md`](./seed-garden.md) — **THE vault's row.** §3 the vault
  holds each seed's order; **§4.2 a seed is order, never power** (the traded
  seed's provenance — its vault-row — is the honest price); the trade as the
  vault's *share* decision (§4.1).
- [`farm-that-feeds.md`](./farm-that-feeds.md) — **THE yield.** §4 the harvest
  is edible stored coherence (the traded yield's magnitude); **a farm cannot
  mint** (a traded harvest carries the same field-bound yield, never added);
  §7f the cultivated-vs-wild read.
- [`the-oath.md`](./the-oath.md) — **THE exchange as a small vow.** §1 the vow
  the field can hold; §2 the standing op / bookable keeping; **§3 the field
  will not hold a false claim** (a trade's promise is a within-window vow the
  field books); §3.2 the quieter sever (a broken trade's promise unresolves).
- [`window-guests.md`](./window-guests.md) — **THE visitor's line.** §1 enough
  a stranger is a walking provenance; **§3 the visitor line** (a foreign
  trader's item reads by provenance, booked, never folded resident).
- [`the-census.md`](./the-census.md) — **THE population read.** §1/§2 the
  active class (a trade is a booked op, so a lively market is a lively active
  class); §6d a census informs, never mints (the market's reads are the
  book's, never a difficulty meter).
- Skim as needed: [`the-exile.md`](./the-exile.md) (§4 the severed line — an
  exiled member's trades read differently), [`the-festival.md`](./the-festival.md)
  (§4 the commons' one chord — the market's activity as a settlement pulse),
  [`the-election.md`](./the-election.md) (§2 the steward's line — the market's
  guard never mints a steward's office).

Every number below is from [`corpus-reconciliation.md`](./corpus-reconciliation.md)
(§2 the canonical set — cited, not re-derived), engine-verbatim, or explicitly
flagged **[design]** (this doc's composition / trust-by-construction framing over
landed pieces) / **[probe]** (a measurement the design gates on). The honest
boundary is drawn in §6 and never blurred: **the ledger, the op-record, the
name's holding, the provenance, the yield, and the vows are their source docs'
landed pieces; the market's *composition* — the exchange as a booked op, the
trust-by-construction framing, the price as the book's read — is this document's
[design] over them.** No claim here pretends the engine writes "trade" or
"market" records beyond the Q4 op it already writes; a trade is a *booked
exchange*, designed, not a new engine act.

---

## Summary table

| Question | Answer (concrete) |
|---|---|
| The Market = ? | **the settlement's exchange designed as a field act** — a trade booked on the shared ledger, made honest **by the law itself, not by enforcement**: no-false-booking and no-false-naming extend to goods, so a market is trustworthy by construction. |
| A trade = ? | a **Q4 op booked as `{member, op, worldPos, rung, magnitude, sustain}`** (schema-that-settles §2.1) — the exchange's shape is the op-record's own; the traded item's provenance is booked (the tool's edge, the seed's vault-row, the yield's magnitude). |
| The load-bearing honesty | **the cheat is not a rule violation, it is a false op the field will not book** — a trader who would cheat cannot; the market's trust is the book's own readability, never a sheriff. |
| The trust by construction | the market needs **no enforcement** because the field's book *is* the enforcement — every exchange's truth is booked at the single non-forgeable point (schema-that-settles §3); the price is the book's read (a thing's booked rung/magnitude is its honest value — the market *informs*, never sets; no hidden pricing, no market-maker). |
| The exchange as a small vow | a trade is a **within-window vow the field books** (the-oath §1/§3) — the promise to deliver, held or rupturing the way any bookable keeping is. |
| The edges | a stranger's trade reads by provenance (window-guests — the visitor line); an exiled member's trades read differently (the-exile §4 — honest, but the severed member's standing is read); the market's activity is the census's active-class face (read honestly, never a difficulty meter). |
| Honest gates | (a) the [design]/engine-real line — the landed pieces vs this doc's composition; (b) **MEDIUM** — gated on the Q4 op-record's member-id and the ledger's single-writer discipline (Phase-1.5), with the **framing Phase-1-legible** (the honest-exchange principle is statable now against shared-ledger + the-name); (c) determinism (same trade, same field state → same book — a hard gate); (d) the no-free-energy cap (a market informs, never mints — the exchange is the same coherence's transfer, never a gain); (e) accessibility (the market's reads are the ledger's own — never hidden-only). |
| Feasibility | **MEDIUM with a Phase-1-legible framing** — the corpus's trust doc, the exchange made honest by the law's own mechanics. State both. |

---

## 1. The Market, stated once

Minecraft's barter is the corpus's one un-designed economic act. Every other
society-designer is a *field act*: the ledger books who contributed
(`shared-ledger.md`), the election reads who leads, the family binds who is
kin, the festival celebrates what was shared. But a trade — *"my harvest for
your pick"* — is silently presupposed, a drag-drop with a server rule, outside
the field entirely. It has no consequence and no trust: two players agree on
nothing but a server event, and there is no record of what changed hands, what
it was worth, or whether the promise was kept. That is the hole this document
closes.

> **The Market is the settlement's exchange designed as a field act.** A trade
> is a **Q4 op booked on the shared ledger** — genuinely, the world-writer's
> single-writer record of an exchange — and it is made honest **by the law
> itself, not by enforcement**: the ledger's no-false-booking books every
> exchange as `{member, op, worldPos, rung, magnitude, sustain}`
> (`schema-that-settles.md` §2.1), so a trade **cannot be lied about**; and the
> no-false-naming of `the-name` extends to goods, so **you cannot falsely name
> what you offer**. A market is thus **trustworthy by construction** — the field
> books the truth of every exchange, and the *only* enforcement is the book's
> own readability.

**The honest flag, once.** The pieces a trade composes are all landed — the Q4
op-record (`schema-that-settles.md` §2.1), the member-id at the non-forgeable
point (§3), the name's holding (`the-name.md` §1/§2), the tool's provenance
(`the-tool.md` §2), the seed's vault-row (`seed-garden.md` §3), the yield's
magnitude (`farm-that-feeds.md` §4), the oath's within-window vow (`the-oath.md`
§1). **The market's *composition* — that an exchange *is* a booked op of that
shape, that this makes it trustworthy by construction, that its price is the
book's read — is this document's [design] over them.** No new channel, no new
physics, no "trade record" the engine writes beyond the Q4 op it already writes:
a trade is a *booked exchange*, designed, and the design's whole honesty is that
it *uses* the field's own book the way the ledger, the oath, and the census
already do.

The Market is the corpus's **trust doc** because it is the one place the field's
honesty is pointed at *the exchange of things between people* — the social
primitive Minecraft never trusted. Where the ledger says *who contributed* and
the oath says *what was vowed*, the Market says **what changed hands — honestly,
because the law books it.**

---

## 2. The honest trade — the mechanics

### 2.1 A trade is a Q4 op — the exchange's shape is the op-record's own

Every field act in the game already lands on the same public, ordered stream as
a Q4 op-record (`shared-ledger.md` §1.1). A trade is **no exception and no new
kind of record** — it is the same bookable op, pointed at an *exchange of
possession*:

```
{ member, op, worldPos, rung, magnitude, sustain }
```

the settled record (`schema-that-settles.md` §2.1), where the trade's exchange
is written into the fields the schema already carries:

| Record field | What a trade writes into it | Landed meaning |
|---|---|---|
| `member` | **the two hands the trade binds** — the giver's and receiver's member-ids at the single non-forgeable write | `schema-that-settles.md` §2.1, §3 — the world-writer attaches the id at *its* write; a trade's two lines are attributable because the book is |
| `op` | the **exchange** — the transfer/offer op (a designed op over the op-stream, `coherence-magic.md` §2's set, applied to possession) | the op names the field act; an exchange is an op of the bookable set |
| `worldPos` | the **market's / the exchange's cell** — where the hand-change books, at cell granularity | `schema-that-settles.md` §2.3 — the cell-ownership rule: two members' books in one cell never merge silent |
| `rung` | the **traded item's rung** — the worked vein's depth, the seed's vault-order, the tool's bite-depth | the item's provenance books its rung (below, §2.2) |
| `magnitude` | the **traded yield's magnitude** — the harvest's stored coherence, the item's honest mass of order | `farm-that-feeds.md` §4 — a yield's magnitude is booked, never made up |
| `sustain` | the **held offer's semantics** — a standing offer / a kept promise's hold | `schema-that-settles.md` §2.2 — a held offer books as one standing record, never a spam |

**The exchange's shape is the op-record's own.** The market does not add a
"trade" schema, a separate "market" channel, or a second book. A trade *is* a Q4
op of the record's own shape — the exchange is booked into the fields the
settlement already reads, on the stream the Board already aggregates
(`shared-ledger.md` §1.2). This is the family rule (`field-instruments.md` §2.1 —
a consumer of the publish with an idiom, never a new channel) applied to the
*exchange itself*: **the market is a booked exchange, not a new instrument.**

### 2.2 The traded item's provenance is booked — the tool's edge, the seed's vault-row, the yield's magnitude

Because a trade is a Q4 op carrying `rung` and `magnitude`, **what changes hands
is not an anonymous block — it is the item's own field-booked provenance.** Each
traded thing carries where it came from, booked into the record:

| Traded thing | The provenance booked | The honest read | Cross-ref |
|---|---|---|---|
| **A tool (a pick)** | the **worked vein's rung** and the **alloy's `q`** — the edge tells where the metal came from | a dull high-ε² blade books as scar-tainted; a clean high-q blade as clean — **no trader can pass a scar-tainted pick off as clean, because the edge's read is booked** | `the-tool.md` §2 (the edge reads the metal's history), §3 (the tool does not hide its lineage) |
| **A seed** | the **vault-row / origin-order** — the deepest Π pattern's provenance | the seed's vault-row is booked; **a trader cannot falsely call a common seed a rare one**, because the order's provenance is the record's | `seed-garden.md` §3 (the vault holds each seed's order), §4.2 (a seed is order, never power) |
| **A harvest** | the **yield's magnitude** — the stored coherence, the bed's `q`, the tide it was taken at | the yield's magnitude is booked; **a trader cannot inflate a thin-tide harvest as rich**, because the magnitude is the field's own | `farm-that-feeds.md` §4 (the harvest's stored coherence), §7 (a farm cannot mint) |
| **Any named thing** | the **name's anchor** — a name holds only what the field truthfully holds | a falsely-named offer is a false name, and decays — **you cannot falsely name what you offer** | `the-name.md` §1/§2 |

**The no-false-naming extends to goods.** `the-name.md` §2 is the design's heart,
and it transfers to the exchange unchanged:

> **You cannot falsely name what you offer — honesty is thermodynamics.** A name
> holds only on the structure it truthfully names; a false name decays
> (`the-name.md` §2). An offer is a *naming* — "this is a clean pick, this is a
> deep seed, this is a rich harvest" — and it holds only if the field is holding
> that truth. **A trader cannot falsely name the thing they offer, because the
> offer's provenance (the rung, the magnitude, the edge, the vault-row) is
> booked into the same record the field wrote.** The false offer is a false op
> the field will not hold.

### 2.3 The load-bearing claim — the cheat is not a rule violation, it is a false op the field will not book

This is the doc's single load-bearing statement, stated once and never blurred:

> **A trader who would cheat cannot. The cheat is not a rule violation — it is a
> *false op* the field will not book.** In Minecraft, a cheating trade is a
> *rule* a server must catch and *enforce* (a moderator, an anti-dupe, a ban).
> In the Market there is nothing to enforce, because the trade's truth is not a
> promise a rule guards — it is a **booked record the single-writer lane
> already wrote truthfully**. To offer a scar-tainted pick as clean, a false
> seed as rare, a thin harvest as rich, is to hand the world an op that *names
> what is not there* — and the field does not hold it (`the-name.md` §2). The
> cheat is not a violation a sheriff must catch; it is a **false op** — a lie the
> book cannot record, because the book is exactly what the domain executed
> (`shared-ledger.md` §6d; `schema-that-settles.md` §3). **The market's trust is
> the book's own readability — never a sheriff.**

Concretely, the three ways a barter-cheat could go, and why each fails *by the
book*:

| Barter-cheat | Minecraft (a rule) | The Market (a field property) |
|---|---|---|
| **"I'll give you a clean pick" (it's scar-tainted)** | a moderator must inspect, a rule must catch the swap | the pick's alloy-`q` is booked (`the-tool.md` §2); the offer that names it clean is a false name that decays (`the-name.md` §2) — **the book cannot record the lie** |
| **"This seed is the window's rare one" (it's common)** | a server flag, a trading rule | the seed's vault-row / origin-order is booked (`seed-garden.md` §3); the false rare-offer is a false op the book does not hold |
| **"A fair trade, no trick" (they take the item, don't deliver)** | a server must ban the non-delivery | the trade is a within-window vow (`the-oath.md` §1); a promise not kept is a false claim the field does not hold — **the non-delivery is a ruptured oath, legible on the book** (§2.4) |

**The honest register.** The book does not *punish* a cheat in the Minecraft
sense — there is no ban-hammer, no moderator. The book's honesty is stronger and
quieter: **the cheat cannot be done, because the false op is not bookable.** A
player who tries to falsely name an offered thing finds the offer does not hold
— the false name decays, the item's booked provenance does not change, and the
book reads the truth of what was actually exchanged. **That is the enforcement:
not a punishment, but the impossibility.** The cheat is a false op the field
will not record.

---

## 3. The trust by construction

### 3.1 The market needs no enforcement because the field's book *is* the enforcement

The design's whole claim is that a market is **trustworthy by construction** —
the trust is not granted by a rule, a sheriff, a reputation score, or a
market-maker; it is a **structural property of where the book is written**:

> **Every exchange's truth is booked at the single non-forgeable point.**
> `schema-that-settles.md` §3: the world-writer is the *only* server-side
> mutator; the member-id and every op attach at *its* write — the one place a
> record cannot be forged. A trade's truth (the member-id, the rung, the
> magnitude, the sustain) is written there and nowhere else. **There is no second
> book a cheater could write into, no server path that skips the honest record,
> no player-touch that edits physics state** (`shared-ledger.md` §6d). The
> single-writer seam is the enforcement; the market's trust is that seam,
> read at settlement scale.

This inherits the two no-forge strengths the ledger already names verbatim:

| The book's strength | What it means for the Market | Source |
|---|---|---|
| **The op-stream is single-writer** | a trade cannot be faked into the book — the record is exactly what the domain executed, ordered and logged; there is no "white-heal then dissolve" forge, and no "fake a clean trade" forge | `shared-ledger.md` §6d; `async-field-domain.md` §5.2 |
| **The member-id attaches at the non-forgeable point** | a trade's two hands are attributable, and the attribution is the world-writer's, never a player's | `schema-that-settles.md` §2.1, §3 |

### 3.2 The price is the book's read, never the book's set — no hidden pricing, no market-maker

A market must decide what a thing is worth. The Market *does not decide*: it
**reads** the thing's booked value off the field, and the book *informs* the
exchange rather than *setting* it.

> **A thing's booked rung/magnitude is its honest value — the market *informs*
> the exchange, never sets it.** A deep-rung pick's value is the rung and the
> alloy-`q` booked into it; a rare seed's is its origin-order; a rich harvest's
> is its stored coherence and the tide it was taken at
> (`the-tool.md` §2, `seed-garden.md` §3, `farm-that-feeds.md` §4). **The price
> is not a number a market-maker sets, a hidden supply/demand engine, or a
> reputation score; it is the item's own booked provenance, read.** Two members
> trading a pick for a harvest each *read* the other's booked value and the
> exchange is fair to the extent their reads agree on the field's truth. **The
> Market does not price anything; it presents what the field already booked, and
> the exchange happens against that honest read.**

This is the no-hidden-pricing discipline, and it has a hard consequence for the
design:

| What the Market is NOT | Why | Source |
|---|---|---|
| **a market-maker** | there is no agent that sets a price, holds an inventory, or earns a spread — the book has no maker, only readers | this doc §3.2; the corpus has no merchant-authority |
| **a hidden pricing engine** | supply/demand, rarity-charts, and price-servers would be a second, hidden information source — the book's recorded truth is the only value, and it is public | `shared-ledger.md` §6e (the book is public); `the-census.md` §6e (never hidden-only) |
| **a difficulty meter / economy dial** | the market's activity must never read as a game-difficulty lever — a lively market is a lively population, read honestly, never a tuned economy | `fate-of-a-window.md` (a window's difficulty is field state, not a setting); `the-census.md` §2 |

**The informed exchange.** The honest consequence of "the price is the book's
read" is that **the market and the item's field-value are the same thing.** A
trader who understands the field — who can read a tool's edge, a seed's row, a
harvest's tide — trades well; a trader who cannot reads badly. **The skill of
trading is the skill of *reading the field truthfully* (the-name §2.3's "naming
is the player's act of truthful reading" applied to goods).** The Market
rewards honest eyes, never a hidden economy, because the value is the book's
honest record.

### 3.3 The exchange as a small vow — the field-enforceable promise

A trade is not just a record; it is a **within-window vow the field books**
(`the-oath.md` §1 — the deliberate, costed promise the field will not hold
falsely):

> **[design] A trade is a small oath — the promise to deliver, booked the way a
> vow's keeping is.** When two members trade, each makes a named promise —
> "I give you this clean pick, you give me this harvest" — bound over the
> exchange's op, the way a vow binds two Π patterns to a named keeping
> (`the-oath.md` §2.1). The promise is **a within-window vow the field holds**
> (`the-oath.md` §3 — the field will not hold a false claim): the delivery is
> booked into the op, and **a delivery that does not come is a promise not kept —
> a false claim the field does not hold, read on both books the way a broken
> oath reads** (`the-oath.md` §3.2, the quieter sever).

This is the trust's final layer: the *exchange* is honest by the book (§3.1),
its *value* is honest by the read (§3.2), and its *promise* is honest by the
oath (§3.3). **A trade is a bookable, vowed, read-true exchange** — the three
honesties the corpus already has, composed into the one act Minecraft left
untrusted.

**The honest register, once:** the trade-vow's rupture is deliberately the
*oath's quieter sever* — a promise's death, not a person's removal
(`the-oath.md` §3.2); a broken trade does not exile or ban, it unresolves the
promise's book, legibly. The Market's enforcement is never more than the book's
own reading.

---

## 4. The market's edges — the honest boundaries

The Market is not a closed ring of residents. Its edges are where the field's
honesty is sharpest, and each is a landed read:

### 4.1 A stranger's trade reads by provenance — the visitor's line

When a traveller from another window trades in your market, their item is not an
anonymous good — it is **walking provenance** (`window-guests.md` §1), and the
trade reads it so:

| A stranger's trade | The read | Cross-ref |
|---|---|---|
| **Their item's provenance is booked, not assumed** | the traded thing's origin — the foreign field it was raised in — is read through the same provenance the visitor line books; **the settlement does not take a guest's item on trust, it reads where it came from** | `window-guests.md` §3 (the visitor line: a contribution with provenance); §2.2 (the foreign order) |
| **The guest's trade books as a visitor line, never a resident's** | a foreign trader's exchange books to the window's book but marked *from elsewhere* — **never folded into a resident's `C(M)`, never fused with the window's honest economy** | `window-guests.md` §3.1/§3.2; `shared-ledger.md` §2.2 |
| **A guest's item is the same honest read** | the foreign thing's rung/magnitude is booked like a resident's — **provenance surfaces the item's truth, it does not exempt it from the book** | `the-tool.md` §2; `seed-garden.md` §3 |

**The honest principle.** A stranger's trade is *legible* by provenance — the
window reads what arrived and where it came from — but it is *booked* exactly
as honestly as a resident's. **The visitor's provenance is the Market's guest-
face of the no-false-naming**: you cannot falsely *label* a foreign item either,
because its origin is booked (`window-guests.md` §6d — a guest's arrival
perturbs, never mints).

### 4.2 An exiled member's trades read differently — the severed line's standing

The Exile is the corpus's hard edge: a member's line is severed by the book and
the board, un-residented to a guest-of-nowhere (`the-exile.md` §4, §3). An
exiled member's trades in the Market read **honestly but differently**:

| An exiled member's trade | The read | Cross-ref |
|---|---|---|
| **The trade itself is honest** | the exiled member's exchange is booked the same truthful way — their item's provenance is real, the no-false-booking does not stop because the line is severed | `shared-ledger.md` §6d (the op-stream is honest regardless of standing) |
| **But the severed member's standing is read** | the trade books to a **closed, severed line** — the Board revisits the exile's severed status, not a resident's contribution; an exiled offer is legible *as* severed, the way a guest-of-nowhere books as foreign | `the-exile.md` §4 (the lone traveller with a severed line); `window-guests.md` §3 (the un-residented line) |
| **The exchange with an exile is a decision, not a default** | the settlement trades with a severed member knowing the book reads their standing — **the honest read informs the choice; it never silently hides or silently forgives** | `the-exile.md` §4/§2; `schema-that-settles.md` §2.1.1 (no amnesty) |

**The honest boundary, once.** The Market is **not an amnesty machine**: an
exiled member's trades are as honest as any — the book cannot be lied to — but
they **read differently on the Board's book**, because the severed member's
standing is booked and honest (`the-exile.md` §4). The market's edge is *honest,
never hidden, never quietly reversed*.

### 4.3 The market's activity is the census's active-class face — read honestly, never a difficulty meter

The Census reads the settlement's population off the already-booked lines
(`the-census.md` §1). Since a trade is a booked op (§2.1), **a lively market is
literally a lively active class** — the same book, read two ways:

> **The market's activity is the census's active-class face.** The active class
> counts who booked a contribution this tide (`the-census.md` §2.1); a trade
> *is* a contribution-booked op, so a market with many exchanges reads as a
> window whose members are *present and exchanging*. The Market and the Census
> read the *same* book at different scales — the Market at the single exchange,
> the Census at the population. **A lively market is a lively population; a
> quiet one is a quiet season — read honestly, never as a tuned difficulty
> meter, never as an economy the design forces to "stay healthy."**

The honest discipline, inherited from the Census and the Fate:

| The market-activity read must NOT be | because | Source |
|---|---|---|
| a **difficulty meter** | a window's difficulty is field state, never a game setting; the market's liveness is feedback, not a dial | `fate-of-a-window.md` §1; `the-census.md` §6d |
| a **hidden-only economy signal** | the market's activity is the board's book at exchange scale — public, never hidden | `shared-ledger.md` §6e; `the-census.md` §6e |
| a **mint-of-liveliness** | a lively market informs the census's active class; it does not *produce* population or coherence (the no-free-energy cap, §6d) | `the-census.md` §6d; `energy-harnessing.md` §6 |

---

## 5. The honest boundary and gates

### (a) The [design]/engine-real line

The line, drawn once and never blurred, mirroring `shared-ledger.md` §6 and
`the-oath.md` §5:

| Layer | Status | Basis |
|---|---|---|
| The **Q4 single-writer op-stream**; the world-writer the only mutator | **engine-real** | `async-field-domain.md` §5.2/§7 Q4; `corpus-reconciliation.md` |
| The **op-record `{member, op, worldPos, rung, magnitude, sustain}`**, with the member-id attached at the world-writer's write (the single non-forgeable point) | **[design]**-landed over the engine-real lane | `schema-that-settles.md` §2.1, §3/§6 |
| The **member-id's persistent-Π ground** | **theory-ratified** (with `reason-field.md` §6a's speculation flag) | `qi-computation.md` §5.2; `player-remains.md` §2 |
| The **no-false-naming** (a false name decays; honesty is thermodynamics) | **[design]**, landed over the theory-ratified persistent-Π holding | `the-name.md` §2/§6 |
| The **tool's provenance** (the edge reads where the metal came from); the **seed's vault-row**; the **yield's magnitude**; the **farm's cultivated-vs-wild** read | landed [design] over real channels | `the-tool.md` §2/§4; `seed-garden.md` §3; `farm-that-feeds.md` §4/§7f |
| The **visitor line** (a foreign trade books with provenance); the **exiled severed line** | landed [design] over the settled record | `window-guests.md` §3; `the-exile.md` §4 |
| The **small oath** (the exchange as a within-window vow the field books) | landed [design] over the pledge-line / broken-oath honesty | `the-oath.md` §1/§3 |
| **The market's composition** — the exchange *as* a booked op of §2.1's shape, the **trust-by-construction** framing, the **price as the book's read** | **[design]** over the landed pieces — this doc | **this doc** — a designed composition of the corpus's own honesties, never a new physics, never a new channel |

**The boundary, stated once and kept:** the Q4 lane and the op-record are
engine-real / [design]-landed; the no-false-naming, the provenance, the yield,
and the vows are their source docs' landed pieces; **the market's composition —
the exchange as a booked op, the trust-by-construction framing, the price as the
book's read — is this document's [design] over them.** No claim here pretends
the engine writes a "trade" or "market" record beyond the Q4 op it already
writes, or that the field "decides" a trade is fair — the field books the truth
of what was exchanged, and this doc designs the *market* that reads it honestly.
The family rule is absolute: **the Market performs no new channel, only a
designed composition and read over the channels the settlement already holds.**

### (b) MEDIUM — gated on the Q4 op-record's member-id and the ledger's single-writer discipline

The **mechanical** market — a live exchange booked as a Q4 op, read at
settlement scale, trustworthy by construction — is **MEDIUM**, gated on the two
artifacts the whole trust-by-construction rests on:

| Gate | What it needs | Status |
|---|---|---|
| **The Q4 op-record's `member` field** | the two hands a trade binds must be attributable; the market's per-line books need the identity (§2.1) | **landed** — `schema-that-settles.md` §2.1 binds the member-id; the market is *built to the settled record* (the ID has landed; the market's *booked exchange* composition rides it) |
| **The ledger's single-writer discipline** | the book-must-be-honest strength (§3.1) is the async world-writer's no-forge seam (`async-field-domain.md` §5.2); the market's no-cheat-by-construction depends on it | **Phase-1.5** — the single-writer lane is engine-real and Phase-1, but the *multi-member* exchange at settlement scale (two hands booking, the Board aggregating the trade as a contribution) rides `shared-ledger.md`'s Phase-2/1.5 live-bath heart |

**The honest split.** The *single* primer is Phase-1-able (one player's ows can
book an exchange against the landed member-id and the Board's aggregation slice,
`shared-ledger.md` §6b); **the *settlement's* market — two or more members
exchanging and the book aggregating the trade as a per-line `C(M)` — is Phase-1.5,
gated on the ledger's single-writer discipline running at multi-member scale and
the Qi-bath being a real shared core the trades move** (exactly `shared-ledger.md`'s
own Phase-2 heart). **MEDIUM**, not LATER: the market rides *landed* pieces (the
op-record, the member-id, the no-false-naming, the provenance, the vow) — it does
not wait on a meshless/Π frontier or a new physics; it waits on the ledger's
single-writer discipline being live at settlement scale.

**But the framing is Phase-1-legible — statable now against shared-ledger + the-name:**

> **The honest-exchange principle — a trade booked, provenance-tagged, never
> falsely named — is statable now.** The scaffold does not need the multi-member
> ledger to be live to state the rule: a trade is a Q4 op of the settled record's
> shape (§2.1); a traded item's provenance is booked (the tool's edge, the seed's
> vault-row, the yield's magnitude — §2.2); you cannot falsely name what you
> offer — honesty is thermodynamics, so the cheat is a false op the field will
> not book (§2.3); a market needs no enforcement because the book *is* the
> enforcement (§3); the price is the book's read, never its set (§3.2); and the
> exchange is a small vow the field holds (§3.3). Every one of those is a
> *designed statement* the corpus can hold now, against the landed member-id
> (`schema-that-settles.md` §2.1), the single-writer lane (`async-field-domain.md`
> §5.2), the no-false-naming (`the-name.md` §2), the provenance pieces
> (`the-tool.md`, `seed-garden.md`, `farm-that-feeds.md`), and the vow
> (`the-oath.md` §3) — whether or not the live multi-member market is built.

**What Phase-1 gains from the scaffold:** (1) the **honest-exchange principle** —
the designed statement that an exchange is a booked, provenance-tagged, never-
falsely-named op — is itself a Phase-1-legible truth about how the world *should*
behave, pre-registered the way `the-name.md` §6b and `the-oath.md` §6b scaffold
their principles; (2) the **single-exchange book** — one player's booked
exchange against the landed member-id + the Board's aggregation slice
(`shared-ledger.md` §6b) — is renderable from the first windowed demo, de-risking
the whole "a trade is a booked op" claim before the society exists; (3) the
**composition's vocabulary** — provenance-tagged value, price-as-read, book-
enforced honesty — is a designed stance the later settlement-scale market builds
against, so the corpus can hold the *designed statement* now even though the
*live market* is MEDIUM/Phase-1.5.

### (c) Determinism — same trade, same field state → same book (a hard gate)

The field is deterministic (one PDE; `field-archaeology.md` §1.2; `shared-ledger.md`
§6). The Market inherits it as a **hard gate** (the doc's required framing):

> **Same trade, same field state → same book.** A trade's booked op is a
> deterministic function of the two members' lines, the item's provenance, and
> the field state — the same exchange, at the same field state, books the same
> `{member, op, worldPos, rung, magnitude, sustain}` record, every run. The
> trade's honesty is not a seeded-RNG judgment about whether an exchange "was
> fair" — the book either records the item's true provenance or it does not, and
> it does so reproducibly. A reloaded market at the same field state reads the
> same exchange-value, the same per-line book, the same trade-vow's holding. There
> is no randomness about a cheat "getting caught" — a false op either books (it
> cannot) or it doesn't, deterministically. **[design]** The *exchange op's
> semantics* (which possession-transfer the op names) is a designed dial — but
> once set, the booking is deterministic.

### (d) The no-free-energy cap — a market informs, never mints

`energy-harnessing.md` §6 (`output ≤ φ⁻¹·input`), inherited as a hard bound
(this doc's required framing):

> **A market informs an exchange; it never mints coherence.** A trade is the
> **same coherence's transfer from one member's line to another's** — a clean
> pick's stored order, a seed's origin-order, a harvest's stored coherence move
> *between* books, never *into* the settlement as new. The exchange is a
> **transfer, never a gain**: the sum of the two members' `C(M)` after a trade
> is the same coherence that existed before, re-allocated, and `output ≤ φ⁻¹·input`
> holds through the exchange exactly as it does through any op
> (`shared-ledger.md` §1.3 — "nobody is a net mint"; the no-free-energy cap is
> unchanged). **A market cannot mint a harvest, cannot synthesize a rare seed by
> trading for it, cannot turn exchange-activity itself into coherence.** And the
> **no-false-booking is the cap's bookkeeping face**: because the book records
> the item's true provenance, no entry can *inflate* a value — a falsely-priced
> trade would be a false op, never a real gain. **There is no trade that
> yields** — the Market is the corpus's trust doc for the same reason it is not
> a mint: the exchange's honesty and its no-gain are the same book.

### (e) Accessibility — the market's reads are the ledger's own, never hidden-only

Per the instrument-family rule (`field-instruments.md` §2.1) and the corpus's
never-hidden-only discipline (`shared-ledger.md` §6e; `the-oath.md` §6e):

> **The Market's reads are the Ledger's own — never hidden-only.** A traded
> item's provenance is read off the same book the Board already aggregates
> (`shared-ledger.md` §1.2/§2.1); a trade-vow's keeping or rupture reads on the
> same pledge-line the Oath uses (`the-oath.md` §2.2); the market's activity is
> the same active-class count the Census reads (`the-census.md` §2.1). **A
> player who never uses a "market" surface loses nothing** — the honest value of
> any item is legible from the reader (`coherence-magic.md` §2 the edge's read),
> the Weatherglass, and the Board's public book, more laboriously. There is no
> hidden pricing engine, no trade-secret value, no second book. **A market that
> hid its prices would be a secret economy the design's own honesty forbids.**

---

## 6. Feasibility verdict

**MEDIUM with a Phase-1-legible framing — the corpus's trust doc, the exchange
made honest by the law's own mechanics. State both.**

**MEDIUM (the settlement's live market):** a multi-member exchange booked as a
Q4 op, read at settlement scale, trustworthy by construction — gated on the two
artifacts the whole trust rests on: **the Q4 op-record's `member` field**
(landed, `schema-that-settles.md` §2.1 — the market is *built to the settled
record*) and **the ledger's single-writer discipline at multi-member scale**
(`shared-ledger.md`'s Phase-2/1.5 heart — the Qi-bath shared core real, several
members' books live). **MEDIUM**, not LATER, because the market rides *landed*
pieces — the op-record, the member-id, the no-false-naming, the provenance, the
vow — it adds **no new channel, no new physics, no second book**, and it does
not wait on a meshless/Π frontier. It is the exchange composed out of the
corpus's own already-true honesties.

**Phase-1-legible framing (the honest-exchange principle):** whether or not the
live market is built, the corpus can now hold the load-bearing truths — **a
trade is a Q4 op of the settled record's shape** (§2.1); **a traded item's
provenance is booked** (the tool's edge, the seed's vault-row, the yield's
magnitude — §2.2); **you cannot falsely name what you offer — honesty is
thermodynamics, so the cheat is a false op the field will not book** (§2.3);
**a market needs no enforcement because the book is the enforcement** (§3);
**the price is the book's read, never its set** (§3.2); **and the exchange is a
small vow the field holds** (§3.3). Every one is a designed statement statable
now against the landed member-id, the single-writer lane, the no-false-naming,
the provenance pieces, and the vow — the same scaffold-now verdict as
`the-name.md` §6b, `the-oath.md` §6b, and `the-census.md` §6b.

**What it fills.** The corpus designs who contributes (the ledger), who leads
(the election), what was vowed (the oath), who is kin (the family), and what was
celebrated (the festival) — but never *how things change hands*. Minecraft's
barter is the one economic act with no field consequence and no trust. **The
Market is that untrusted act made honest by the law's own mechanics** — the
exchange designed as a booked op, provenance-tagged, never falsely named, its
trust the book's own readability, **never a sheriff.**

**Binding risks, in order:**

1. **The "fairness-as-rule" slide (§2.3/§6b).** The sharpest failure is the
   Market reading as a *rule* the game enforces — a "fairness detector," a
   moderator, an anti-dupe — instead of the *field property* that the cheat is a
   false op the book will not hold. The single-writer seam + the no-false-naming
   are what make it structural, not a rule; a market that reads as a server rule
   has missed the design. The Phase-1.5 single-writer-at-scale gate is the risk's
   honest face.
2. **The "price-as-set" overclaim (§3.2).** The Market *informs* the exchange
   with the book's read; it must never read as *setting* an economy, a
   difficulty dial, or a market-maker's price. The no-hidden-pricing discipline
   and the no-mint cap (§6d) hold it; a market that reads as a tuned economy is
   a lie the corpus's honesty forbids.
3. **The "guest-trade as resident" blur (§4.1).** A stranger's trade must read by
   provenance and book as a visitor line, never silently fold into a resident's
   `C(M)` — the misattribution guard of `window-guests.md` §3/§6e, held at the
   exchange. The market's guest-face is the same honest line as the Board's.
4. **The exiled-trade as amnesty (§4.2).** An exiled member's trades are honest
   but read differently; the market must never read as a way to slip an exiled
   line back into the window's economy quietly — the severed standing is booked
   and read (`the-exile.md` §4; `schema-that-settles.md` §2.1.1 no amnesty).
5. **The no-free-energy cap (§6d).** The market must never read as a mint — no
   trade that yields, no exchange-activity that produces coherence, no
   "trade to farm a read." The no-false-booking is the cap's bookkeeping face:
   the book records true provenance, so no entry can inflate a value.

**None contradicts the async, dual-world, or regime-collapse architecture** — the
Market adds no physics and no channel: it is a *designed composition and read*
over the existing single-writer Q4 lane, the landed member-id, the no-false-
naming, the provenance pieces, the small oath, and the Board's book — the
exchange made honest by the field's own mechanics.

> **The honest statement that makes this doc load-bearing: the corpus gives a
> settlement its book, its leadership, its promises, its kin, and its joy — but
> never its *exchange*. Minecraft's barter is undesigned: players trade with no
> field consequence and no trust, a drag-drop with a server rule outside the
> field entirely. The Market is that untrusted act designed as a field act: a
> trade is a Q4 op booked on the shared ledger — the exchange's shape is the
> op-record's own — and it is made honest *by the law itself, not by
> enforcement*. A traded item's provenance is booked (the tool's edge, the
> seed's vault-row, the yield's magnitude), the no-false-naming extends to goods
> (you cannot falsely name what you offer — honesty is thermodynamics), and the
> load-bearing truth is that **a trader who would cheat cannot: the cheat is not
> a rule violation, it is a false op the field will not book.** The market needs
> no enforcement because the field's book *is* the enforcement — every
> exchange's truth is booked at the single non-forgeable point, and its price is
> the book's own read (the market *informs*, never sets; no hidden pricing, no
> market-maker). The exchange is a small vow the field holds; a stranger's trade
> reads by provenance; an exiled member's trades read differently; the market's
> liveness is the census's active-class face, never a difficulty meter. It is
> deterministic, non-minting (the exchange is the same coherence's transfer,
> never a gain), and accessible (the market's reads are the ledger's own). The
> composition is this doc's design; the honesty it composes is the field's own.
> The framing is Phase-1-legible against the landed pieces; the live market is
> MEDIUM, gated on the op-record's member-id and the ledger's single-writer
> discipline at scale. The Market is the corpus's trust doc — the exchange made
> honest by the law's own mechanics, never by a sheriff.** The social primitive
> Minecraft left trusted-to-nothing, given the field's own book.

---

## Open questions

1. **The exchange-op's scope (§2.1).** A trade is a Q4 op of §2.1's shape, but
   *which* of the bookable ops the transfer names — is "exchange" a designed
   near-op over `coherence-magic.md` §2's five writes, or a designed
   possession-transfer read over the same lane — is a [design] dial against the
   settled op set. The op must stay on the bookable set (the family rule); the
   exact transfer-op semantics is designed. **[design]**
2. **The value-reconciliation when two members' reads disagree (§3.2).** The
   price is the book's read; but two traders may *read* the same item's value
   differently (one prices a pick high, the other low — both honest reads of the
   same booked rung). Is the exchange "fair" when the read differs — is the
   field's honest value a *single* truth, or a per-eye read over one booked
   record? The design's default is that the booked provenance is one truth and
   the eyes differ on *how much it matters* (a designed, honest spread, never a
   hidden price); the exact reconciliation is [design]. **[design]**
3. **Non-tangibles (§2.1/§3.3).** Can a trade exchange a *service* (a held
   keep, a maintained anchor, a favour — the kept acts of `the-oath.md` §2)
   rather than a thing? The honest register is that a service-trade is a small
   vow (a bookable keeping, §3.3) — but the boundary between "a traded thing,
   provenance-booked" and "a traded keeping, pledge-booked" is a [design] dial
   against the pledge-line's read. **[design]**
4. **The exiled-trader's standing over time (§4.2).** Does an exiled member who
   trades *repeatedly* in the market's honest lines eventually creep toward
   resident-standing, or does the severed line stay severed until a designed
   decision (`the-exile.md` §4's "reversible only by the same honest process")?
   The design's default is the latter (severed is severed until re-earned); the
   boundary is [design] over the exile's return rule. **[design]**
5. **The market's relationship to the vault's share (§4.1 of seed-garden).** A
   traded seed leaves the vault (the origin leaves your window); is its post-trade
   provenance the vault-row it left, or does the exchange re-anchor the seed's
   provenance to the *new* holding vault? Inherits `seed-garden.md` §4.1/§7's
   open-Q (the vault's holding-vs-loss); the market reads the provenance either
   way, but the trading of *irreplaceable order* (a seed is order, not power,
   `seed-garden.md` §4.2) is a designed stakes-decision. **[design]**

---

## Cross-references

- [`shared-ledger.md`](./shared-ledger.md) — **THE book the market writes on.**
  §1.2 the per-member `C(M)` per tide (a trade books into the same read); §2.2
  the member-identities; §6d the single-writer no-false-booking (the market's
  honesty); §6c the landed member-id (the trade's two hands); §6b the
  aggregation slice (the single-exchange book is Phase-1-able).
- [`schema-that-settles.md`](./schema-that-settles.md) — **THE trade's
  bookable shape.** §2.1 the op-record `{member, op, worldPos, rung, magnitude,
  sustain}` (the exchange is a Q4 op of that shape); §2.2 the sustain flag; §2.3
  the cell-ownership rule; **§3 the single non-forgeable point** (the market's
  book is written there, and nowhere else).
- [`the-school.md`](./the-school.md) — **THE false op applied to teaching.** A school
  that teaches a false craft is a false name — §2.3's "the cheat is a false op the field
  will not book" (§2.3 this doc) applied to the passing of knowledge (§4 there); §6d's
  "a market informs, never mints" is inherited by the school's "informs, never mints" (§5d
  there). Reverse pointer: the school borrows the market's false-op honesty for teaching.
- [`the-gift.md`](./the-gift.md) — **the book's deliberate silence.** §2.1 there makes
  §1/§2.1 this doc's booked exchange its *inverse* — the market's honesty is being booked,
  the Gift's is not being (§2.1 there); §3's trust-by-construction ("the market is honest
  *because* it is booked") is the exact claim the Gift inverts; §2.3's no-false-booking is
  held from the not-booking side. Reverse pointer: the Gift is the market's quiet against
  the book.
- [`the-dispute.md`](./the-dispute.md) — **the clear-book that prevents.** §2.3 there reads
  §2.3 this doc as the disputes the book *prevents* — a contested exchange cannot arise
  from a false op, because the cheat is a false op the field will not book; §2.1 a trade is
  a Q4 op (the dispute's claim shape). Reverse pointer: the market's honesty pre-empts the
  disputes the field would otherwise judge.
- [`the-name.md`](./the-name.md) — **THE no-false-naming extended to goods.**
  §1 the Π-anchor; **§2 honesty is thermodynamics — you cannot falsely name what
  you offer**; §3.2 the named contribution is legible; §6d a name holds, never
  mints.
- [`the-tool.md`](./the-tool.md) — **THE traded item's provenance.** §2 the edge
  reads where the metal came from (a traded pick's alloy-`q` is booked); §3 the
  tool does not hide its lineage; §4b the Phase-1-able slice.
- [`seed-garden.md`](./seed-garden.md) — **THE vault's row.** §3 the vault holds
  each seed's order; **§4.2 a seed is order, never power**; §4.1 the
  keep/plant/trade/fade decision.
- [`farm-that-feeds.md`](./farm-that-feeds.md) — **THE yield.** §4 the harvest is
  edible stored coherence (the traded yield's magnitude); §7 a farm cannot mint;
  §7f the cultivated-vs-wild read.
- [`the-oath.md`](./the-oath.md) — **THE exchange as a small vow.** §1 the vow
  the field can hold; §2 the bookable keeping; **§3 the field will not hold a
  false claim**; §3.2 the quieter sever (a broken trade's promise unresolves).
- [`window-guests.md`](./window-guests.md) — **THE visitor's line.** §1 a
  stranger is a walking provenance; **§3 the visitor line** (a foreign trade
  books with provenance); §6d a guest's arrival perturbs, never mints.
- [`the-census.md`](./the-census.md) — **THE population read.** §1/§2 the active
  class (a trade is a booked op, so a lively market is a lively population);
  §6d a census informs, never mints; §6e the book's accessibility.
- [`the-exile.md`](./the-exile.md) — **§4 the severed line** (an exiled member's
  trades read honestly but read the severed standing); §2/§6b the provable, never
  fiat, inherited; `schema-that-settles.md` §2.1.1 no amnesty.
- [`energy-harnessing.md`](./energy-harnessing.md) — **§6 the no-free-energy cap**
  (`output ≤ φ⁻¹·input` — the exchange is a transfer, never a gain); §4.4 the Qi
  bath (the shared core a settlement market moves).
- [`async-field-domain.md`](./async-field-domain.md) — **§5.2/§7 Q4 the single-
  writer seam** — the no-forge strength the market's trust rides.
- [`fate-of-a-window.md`](./fate-of-a-window.md) — §1 a window's difficulty is
  field state, not a setting (the market-activity read is feedback, never a
  difficulty dial).
- [`field-instruments.md`](./field-instruments.md) — **§2.1 the family rule** (the
  Market is a consumer of the publish with a composition idiom, never a new
  channel); §1.2 the Weatherglass idiom the market's read composes.
- [`the-loan.md`](./the-loan.md) — **the forward book.** §4a there reads §6d this
  doc's no-free-energy discipline (an exchange never a mint) and §2.1 the op-record
  shape the loan books as the exchange deferred; §2.3 the false-trade guard the
  forward book inherits. Reverse pointer: a loan is the market's future-minted
  promise, honestly never free.
- [`the-commons-tithe.md`](./the-commons-tithe.md) — **the regular sibling.** §2 there
  reads §2 this doc's trade as a booked op of the settled record's shape (the tithe is
  the same booking pointed at the commons), §2.3 the no-false-booking, §6d never mints.
  Reverse pointer: the tithe is the market's booking pointed at the commons.
- [`the-granary.md`](./the-granary.md) — **the store of the circulated.** §4 there reads
  §1 this doc's exchange-as-field-act and §2.1 a trade is a Q4 op — the granary
  *holds* what the market *circulates*, booked the same way; §2.2 the provenance; §6d
  never mints. Reverse pointer: the granary is the market's store-side twin.
- [`the-cart.md`](./the-cart.md) — **the freight the market takes.** §2 there reads §1/
  §2 this doc's exchange-as-booked-op and §2.2 the traded item's provenance — the
  cart's freight is the booked item carried to the market; §6d never mints. Reverse
  pointer: the cart carries the market's booked freight.
- [`the-toll.md`](./the-toll.md) — **the border-twin.** §1/§2 there reads the booked
  exchange (a trade is a Q4 op — a toll is the same booking pointed at the border),
  §2.3 the cheat is a false op (a toll demanded without the held door is a false op),
  §3 the trust by construction, §6d a market informs never mints. Reverse pointer: the
  toll is the market's booking, pointed at the border.
- [`the-broker.md`](./the-broker.md) — **the between-carrier.** §1 there reads the
  trade as a booked op among members; §2 the provenance-booked exchange; §3 the trust-
  by-construction; §6d a market informs never mints (the Broker's no-mint held); §6b
  the framing. Reverse pointer: the broker is the market's between-carrier against.
- [`the-wage.md`](./the-wage.md) — **the time-form.** §1/§2.1 there reads the trade
  as a Q4 op (the wage is the same booking pointed at a worker's day); §2.3 an unpaid
  wage is a false op; §3 the trust-by-construction; §6d a market informs never mints;
  §6b the framing. Reverse pointer: the wage is the market's time-form of the booked
  exchange.
- [`the-mint.md`](./the-mint.md) — **the portable booking.** §1/§2 a trade is a Q4 op (the coin is that booking made portable); §2.3 the cheat is a false op (a false coin is a false op); §3 the trust-by-construction; §6d informs never mints. Reverse pointer: the coin prices the market’s exchange, made portable.
- [`the-caravan.md`](./the-caravan.md) — **the train’s end.** §1/§2 the booked exchange (the abroad-goods the caravan makes arrive); §2.3 a phantom caravan-load is a false op; §6d informs never mints; §6 the framing. Reverse pointer: the caravan’s arrival books at the market’s traded end.
- [`corpus-reconciliation.md`](./corpus-reconciliation.md) — **§2 the canonical
  numbers** (the ≈ 6 MiB publish = q 1 + pot 1 + `∇(g·Φ)` 3 + ρ 1; the 192³/64³
  box; `dt = 0.05`; `τ_c = 0.5`; `ξ = φ⁶ ≈ 17.94`; `φ⁻² ≈ 0.382`; `ω₀² = 20.0`;
  `π/ρ` clamp 0.72; `q ≈ 0.947` attractor; the ≈ 1–6 ms/tick budget; the ≈ 2,000
  cap); cited, not re-derived.
- Theory (read-only): `CassiTheory/speculations/qi-computation.md` §5.2
  (persistent Π patterns — the provenance a traded item's order books, with the
  `reason-field.md` §6a speculation flag); `CassiTheory/speculations/creative-extensions/
  coherence-commons.md` §7 (the multiplicative commons — the same coherence a
  trade re-allocates, never mints).
