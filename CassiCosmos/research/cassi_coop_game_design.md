# Tideweavers: Confluence Relay

## Status: Concept—pre-prototype

## 1. Product premise

**Tideweavers** is a mobile cooperative game in which two to four players draw bounded perturbations into one shared Cassi field. A player does not place a finished picture into the world. A gesture changes a living state that the other players must read, inherit, redirect, stabilize, or recover.

**Player promise:**

> Leave your mark on a living world, then give the next player something real to respond to.

The game is a fictional social systems game driven by a two-field simulation. Its visual and audio mappings are artistic. Field ratios describe the simulation, not the people playing it.

This document is a product concept and implementation target. It does not claim that the current CassiCosmos production scene, current Workbench, or current theory already provides mobile multiplayer.

## 2. Why this is a strong Cassi-native game

A generic shared painting app would make drawings visible to other players. Tideweavers should make drawings **causally consequential**:

- one player can seed a region;
- another can reorganize its channel balance without simply adding more amplitude;
- another can redirect the resulting particle or field current;
- overlapping interventions change the later state rather than merely covering one another visually;
- the outcome can be measured, replayed, and attributed to the ordered operation history.

That turns Cassi's organizational language into a game mechanic without requiring players to accept a scientific or psychological interpretation.

The current Interactive Field Workbench is a useful foundation because it already exposes bounded `deposit`, `align`, and `impulse` operations, selected-region readouts, ordered command accounting, checkpoints, branches, and deterministic scenario replay. See [`interactivity_report.md`](interactivity/interactivity_report.md) and [`next_frontier_report.md`](interactivity/next_frontier_report.md).

## 3. Recommended first mode: cooperative Confluence Relay

### 3.1 Room and round

- 2–4 players;
- invite-only rooms for the first release;
- one authored field seed;
- a 3–5 minute round;
- four planning/settling tides;
- one visible shared objective;
- one final recovery shock;
- deterministic replay and result card.

The team might need to guide a luminous bloom through two or three relay gates, keep a current inside a corridor, or stabilize a fragile structure through successive disturbances. The exact objective should be selected from measured mobile-sized field behavior rather than assumed from the theory.

### 3.2 Player loop

1. **Read:** inspect the field through separate intensity, bounded-coherence, disequilibrium, density, and flow lenses.
2. **Trace:** draw one bounded glyph over a selected region.
3. **Commit:** choose when to lock the action; each player has a small per-tide budget.
4. **Resolve:** the authoritative simulation applies the operations in a canonical order and advances a fixed burst of steps.
5. **Interpret:** the team sees the changed field, objective progress, affected-region accounting, and each player's contribution.
6. **Adapt:** choose the next bounded intervention.
7. **Recover:** survive the final shock or receive a replayable failure state showing where the structure was lost.

The team wins through relay completion, post-shock recovery, and efficient interventions—not through maximum brightness, particle count, or visual noise.

### 3.3 What a drawing means

A drawing is an input gesture that compiles into a small canonical operation. The visible mark is a ghost overlay and attribution cue; the simulation effect is the validated operation.

| Player-facing verb | Underlying first-slice operation | Intended consequence |
|---|---|---|
| **Seed** | Balanced deposit | Creates bounded field material in a region |
| **Tune** | Channel alignment | Reorganizes existing local amplitude without simply injecting more |
| **Push** | Directional impulse | Redirects a selected particle/current toward or away from a route |

A first gesture grammar should be deliberately small: a tap, a two-point stroke, or a fixed arc with a center, radius, heading, tool, and capped strength. Do not accept arbitrary pixels, recipes, shaders, or unrestricted source injection from clients.

Example causal chain:

1. Player A uses **Seed** to create a field knot near the first relay.
2. Player B uses **Tune** on that same region, changing its local channel relationship while preserving its magnitude.
3. Player C uses **Push** to carry the resulting current toward the gate.
4. A late or overpowered Push sends the structure past the gate or leaves it unable to recover from the next surge.

The players are not drawing over one another. They are modifying the shared state left by one another.

## 4. Game rules that prevent a generic fluid sandbox

### 4.1 Scarce influence

Each player receives a small number of operations per tide. The room also has a shared influence budget. Radius, strength, affected area, impulse, and cumulative field change are capped.

This makes the central question:

> When does the field need help, and what kind of help does it need?

It prevents the game from becoming “make the screen brighter and noisier.”

### 4.2 Fixed settling windows

The first game should use planning and settling windows rather than continuous freehand mutation. This makes the input legible, limits network complexity, and aligns with the current Workbench's explicit paused-operation semantics.

Continuous live painting is a later experiment, not a prerequisite for proving the game.

### 4.3 Readable consequences

After each tide, the game should show:

- the committed ghost glyphs;
- which regions were affected;
- intensity change;
- bounded-coherence change;
- disequilibrium change;
- flow/current change;
- objective progress;
- the operation order and player attribution.

The UI should never collapse these into one opaque “energy” or “balance” score.

### 4.4 Authored objectives

Every first-release scenario needs a concrete objective and fixed end state:

- carry a bloom through relay windows;
- preserve two distinct currents through a turn;
- hold a field region inside a recovery envelope;
- deliver a current through a gate before a surge closes it;
- survive a final disturbance with enough structure remaining.

The simulation can remain emergent inside those boundaries, but the player must know what success means.

## 5. Progression and retention

Progression should unlock:

- new authored field seeds;
- route and recovery challenges;
- visual materials;
- glyph shapes and replay treatments;
- soundscapes;
- new objective patterns after their mechanics are balanced.

Progression must not unlock stronger field influence for paying players.

Good retention loops include:

- daily deterministic seeds;
- weekly authored relay challenges;
- exact replay cards;
- branch comparison against an earlier team attempt;
- inviting a friend into the next relay;
- a short “what changed” contribution history.

Do not use streak pressure, opaque compatibility scores, variable-reward mechanics, or a permanent public canvas as a substitute for a fun round.

## 6. Secondary modes

### 6.1 Echo Fields—later asynchronous mode

One player makes a bounded intervention, saves the resulting state, and passes it to the next player. The next player receives one or two actions and leaves another branch.

This is attractive for mobile because it does not require simultaneous presence. It should wait until private synchronous rooms prove that players understand the causal interaction. It introduces public user-generated content, attribution, rollback, storage, and moderation requirements.

### 6.2 Competitive interference—later or optional

Two teams could attempt to stabilize their own relay while redirecting a shared current. This is mechanically possible but should not lead the product. It risks reducing the field to a projectile battler and encourages overpowering rather than cooperation.

### 6.3 Permanent shared world—not a first target

A permanent public Cassi canvas combines the highest costs with the weakest initial evidence:

- continuous authoritative simulation;
- persistent state and storage;
- vandalism and moderation;
- cold-start/network effects;
- public UGC obligations;
- 24-hour operational expectations.

The first product should use ephemeral, bounded rooms.

## 7. Technical architecture

### 7.1 Current evidence and limits

The current Workbench has verified bounded operations, checkpoints, branches, cursor placement, recipes, and deterministic replay in controlled inline/grid mode. It explicitly rejects exact branching for hidden state in decoupled, boxless/site-native, meshless, merging, black-hole, and tracking modes.

The current production scene is a large site-native simulation with worker-thread local RenderingDevice ownership and a 500,000-particle interactive preset. It is not the first multiplayer backend, and no mobile renderer, cross-device deterministic protocol, authentication, reconnect path, or multiplayer transport is currently verified.

### 7.2 Server authority

One room server owns:

- room seed and solver revision;
- fixed simulation clock and timestep;
- accepted operation order;
- field evolution;
- objective and score rules;
- replay log;
- state hashes;
- reconnect checkpoints.

Clients own touch sampling, local ghost strokes, camera, UI, audio, and interpolation. A client may render a low-resolution prediction for responsiveness, but that prediction is disposable and never determines gameplay.

Do not use peer-to-peer authority. Do not trust an open-source client with field state, score, particle positions, or arbitrary shader code.

### 7.3 First backend

The vertical slice should use a new reduced deterministic reference backend:

- 2D or 2.5D field;
- 16³ or 32³ bounded grid, or an equivalent measured 2D representation;
- fixed timestep;
- CPU/reference operation semantics first;
- 2–4 players;
- no meshless, boxless, black-hole, merge, tracking, or hidden production state;
- fixed authored seeds;
- deterministic accepted-operation log.

GPU/server promotion is a later performance gate, not an assumption.

### 7.4 Transport and message shape

A first mobile-compatible transport can be TLS WebSocket over port 443. Keep the schema transport-neutral so a later sequenced snapshot channel can be added without changing game semantics.

A client submits only bounded quantized intent, for example:

```text
room_id
client_id
client_sequence
base_tick
stroke_id
operation_kind
profile
center_q
radius_q
strength_q
heading_q
```

The server:

1. validates ranges, finite values, room membership, sequence numbers, and influence budgets;
2. resamples a capped polyline into deterministic brush dabs;
3. assigns an authoritative operation sequence and apply tick;
4. applies accepted operations in canonical order;
5. returns an acknowledgement, measured affected counts, apply tick, and state hash.

Start around 20 Hz simulation and 10 Hz snapshots, then measure. Send compressed low-resolution field views, objective state, ghost glyphs, and selected particles—not the complete production field or full particle buffer.

### 7.5 Replays and reconnects

A multiplayer replay needs more than the current paused Workbench scenario format. It must include:

- solver revision;
- room seed and configuration;
- accepted operation log;
- authoritative tick/order;
- periodic keyframes or hashes;
- objective transitions;
- reconnect-safe checkpoints.

A reconnect receives a recent keyframe and subsequent accepted operations. A replay must never silently substitute a client-side prediction for authoritative state.

## 8. Prototype sequence

### Phase 0: single-player mechanic

- one 2D field;
- one seed;
- Seed/Tune/Push operations;
- four tides;
- one relay objective;
- deterministic replay;
- no networking or accounts.

Acceptance: players can explain what each operation changes and can complete or fail a repeatable scenario.

### Phase 1: local two-client room

- local authoritative server;
- two desktop clients;
- bounded quantized strokes;
- operation acknowledgements;
- snapshot interpolation;
- reconnect and replay tests;
- simulated latency, loss, duplication, and reordering.

Acceptance: the same accepted operation log produces the same server result and the clients converge after correction.

### Phase 2: mobile rendering client

- Android first if the supported hardware path is clearer;
- low-resolution field presentation;
- ghost-stroke responsiveness;
- battery and thermal measurement;
- touch accessibility and color-independent cues;
- crash and reconnect handling.

Acceptance: target low/mid devices sustain the intended frame rate for a full session without removing the causal field behavior.

### Phase 3: private invite-only test

- 10–20 invited pairs or small groups;
- one authored scenario family;
- no public gallery;
- report/block/evidence capture from the beginning;
- real checkout or preorder test only after the interaction is legible.

Acceptance: players voluntarily replay, can describe why their action changed the outcome, and prefer the field interaction to a cosmetically matched generic fluid toy.

## 9. Monetization

The foundational solver, protocol, and reusable game backend should remain open source once licensing and provenance are settled. The official product can charge for:

- a polished signed mobile client;
- authored scenarios and seed families;
- offline practice;
- replay cards and high-resolution export;
- visual materials, glyph treatments, and soundscapes;
- private-room hosting after usage economics are measured.

Initial pricing hypotheses:

- complete official game: **$5.99–$7.99** one-time;
- cosmetic packs: **$1.99–$4.99**;
- authored scenario packs: **$2.99–$5.99**;
- replay/export pack: **$7.99–$14.99**;
- capped private hosting: only after measured cost and support limits.

Do not sell stronger strokes, larger influence radius, recovery, undo, protection, ranking boosts, or the ability to overwrite another player. That would make the shared field pay-to-win and undermine the game's premise.

## 10. Safety, moderation, and data

Even non-text drawing is user-generated content. The first release should be:

- invite-only;
- ephemeral by default;
- without public profiles, feeds, DMs, voice, or image uploads;
- without open chat;
- bounded to nonsemantic glyphs and capped strokes;
- equipped with report, block, replay evidence, takedown, and restore paths.

Collect only what is required for entitlement, room operation, replay, abuse evidence, and crash diagnosis. Do not request contacts, precise location, microphone, camera, health data, or biometrics. Make saved replay sharing opt-in and publish retention/deletion behavior.

Player-facing vocabulary should be neutral: “two currents,” “field mix,” “recovery,” “flow,” or “channel A/B.” If Yang/Yin appears, it is philosophical/artistic inspiration, not a mapping to gender, personality, morality, dominance, wellness, or identity.

Avoid claims that the game:

- balances or heals players;
- reveals compatibility, trauma, personality, consciousness, or intent;
- transmits a player's real energy;
- proves a theory of everything;
- naturally produces a persistent physical double helix;
- is a scientifically accurate universe;
- is anonymous, unhackable, or safe for children by default.

## 11. Pre-registered kill criteria

Do not escalate to a public mobile service unless these gates are met:

1. **Mechanism:** a mobile-sized field produces at least two repeatable strategic consequences from the bounded tools, and a label-blind comparison distinguishes the interaction from a generic fluid toy.
2. **Legibility:** in external paired tests, at least 70% of players can explain why an action changed the outcome and at least 60% voluntarily begin a second round.
3. **Mobile:** target devices sustain the agreed frame rate for a full session without severe thermal degradation or loss of causal behavior.
4. **Network:** the authoritative server reconnects safely, client views converge, and measured bandwidth/compute costs fit the intended price.
5. **Safety:** reporting, blocking, replay evidence, takedown, appeals, community rules, and human review are operational before any public room exists.
6. **Economics:** all-in variable cost—including compute, egress, storage, payments, fraud, support, and moderation—remains comfortably below net receipts at expected and high-use cohorts.
7. **Scope:** if private 2–4-player rooms do not retain players, do not add public persistence or concurrency to compensate.

## 12. Related documents

- [`product_ideas.md`](product_ideas.md)
- [`interactivity/interactivity_report.md`](interactivity/interactivity_report.md)
- [`interactivity/interactivity_design.md`](interactivity/interactivity_design.md)
- [`interactivity/next_frontier_report.md`](interactivity/next_frontier_report.md)
- [`interactivity/next_frontier_design.md`](interactivity/next_frontier_design.md)
