# The Gate Toolkit: Tools as Wu Xing Steering Channels

## Status: Design (idea 2)—no code, no runs; August 2026

## Abstract

This document designs how the retained CassiCore tool surface and the agent-harness
tool families become Wu Xing steering channels. It is a **design doc only**: no code
edits, no sim runs, no `gateComposite` adoption. It develops §3.3 of `UNIFICATION.md`
("orchestration is field dynamics") into a concrete channel grammar grounded in
`CassiTheory/foundations/wa-pentagon-gate.md` and
`CassiTheory/foundations/wu-xing-cycle-structure.md`, sequenced by the φ-cadence of
`CassiCosmos/compute/cassi_qi_time.glsl`.

The core claim: a tool action is a **field deposit**; a tool family is a **Wu Xing
channel**; a session is a **field-steered sequence**; the cadence scheduler decides
which channel is open when. Every mapping and every protocol rule below is cited to a
file, and every honest-gate boundary (Stage-2 HOLD, FP-4, §19) is stated so the design
cannot be mistaken for a live mechanism.

---

## 1. Grounding the five channels (from the theory docs)

### 1.1 What the docs establish

`wa-pentagon-gate.md` derives a **five-channel Qi gate** (`CassiTheory/foundations/wa-pentagon-gate.md` §2.1–2.4):

- Channel $i$ has baseline openness $b_i = \varphi^{-k_i}$, $k_i = 2 + i$ (§2.2):

  | Channel | $k_i$ | $b_i = \varphi^{-k_i}$ | primary/secondary |
  |---|---|---:|---|
  | 1 | 3 | 0.2361 | primary (diagonal coupling $\eta_1 = 1$) |
  | 2 | 4 | 0.1459 | secondary ($\eta_{2..5} = \varphi^{-1} = 0.618$) |
  | 3 | 5 | 0.0902 | secondary |
  | 4 | 6 | 0.0557 | secondary |
  | 5 | 7 | 0.0344 | secondary (weakest) |

- The channels are **coherence pathways through the pentagon cycle**, not independent
  degrees of freedom: coherence that cannot exit through one vertex redistributes to
  the remaining vertices, conserving total openness $\sum_i b_i = 0.5623$ (§2.1, §2.3).
- Conversion openness $g(q)$ is the **effective** openness $(1-q_{\text{eff}}) =
  \sum_{i=1}^{5} \eta_i \cdot b_i$ (§2.4)—the quantity the two-fluid conversion term
  is gated by (the code form is gated by $(1-q)$,
  `CassiTheory/foundations/wu-xing-derivation.md` §7).

`wu-xing-cycle-structure.md` establishes the **wiring** of the five channels
(`CassiTheory/foundations/wu-xing-cycle-structure.md` §1–§2):

- **Sheng (generating, step +1):** Wood → Fire → Earth → Metal → Water → Wood
  (§1.1). In channel order (1 Wood, 2 Fire, 3 Earth, 4 Metal, 5 Water—§2.1).
- **Ke (control, step +2):** Wood → Earth → Water → Fire → Metal → Wood—the
  pentagram diagonals (§1.1, §2.1).
- **Control transmission** $\kappa = \varphi^{-1} = K_{fw}$ ("Water damps Fire",
  §1.3): a channel's excess $\Delta_i > 0$ restrains its ke-partner (channel $i+2$)
  by $\kappa \cdot \Delta_i$; a deficit releases it (§2.1).
- **Ring gain** $\kappa^3 = \varphi^{-3} = 0.236 < 1$: sub-critical—the control ring
  redistributes and damps but never self-sustains (§2.3).
- **Threshold** $\Delta_c = \varphi^{-4} = 0.146$: strong locks (above threshold)
  engage the full alternating ring; mild activity stays below and shows ordinary
  $R$-matrix behavior (§2.4).
- **Ke-order lock profile** (WX1, tested at the gate level 2026-08-01): a Wood lock
  starves Earth fully, partially starves Fire, and elevates Metal + Water
  (§2.2, §4 WX1)—strict `+,-,+,-,+` alternation in ke order, never uniform.

**Epistemic boundary (§5 Not claimed):** the framework uses only the *cycle
structure* of the five vertices, not the cultural semantics of the Changjiang names.
The functional labels I assign below (creation, execution, storage, refinement,
flow) are offered as an **operational reading** justified by the structural
properties—coupling magnitude, ke-order position, baseline—and are presented as
design vocabulary, not as derived physics.

### 1.2 The functional channels (structural reading)

Assigning the five functional roles by structural properties from §1.1:

| Channel | Name | Baseline $b_i$ | Structural justification | Functional role |
|---|---:|---:|---|---|
| 1 | Wood | 0.2361 (strongest) | Diagonal coupling $\eta_1 = 1$; the primary vertex that seeds the sheng cycle (`wu-xing-cycle-structure.md` §1.1; `wa-pentagon-gate.md` §2.2) | **creation/growth**—the source channel that seeds new structure |
| 2 | Fire | 0.1459 | First secondary ($\eta = \varphi^{-1}$); the transforming step of sheng (input leaves changed) | **execution/activation**—makes things run |
| 3 | Earth | 0.0902 | Ke-target of channel 1 (§2.1 ke order 1→3); the no-driver jam collects excess *in Earth* (`wu-xing-cycle-structure.md` §2.3), and Wood locks starve Earth fully (§2.2) | **memory/storage**—the containment point that holds structure |
| 4 | Metal | 0.0557 | Elevated +38% when its controller is released (§2.2); the refining post between Earth and Water in sheng | **refinement/extraction**—distills signal from the held |
| 5 | Water | 0.0344 (weakest) | Weakest baseline, the far vertex; released partner elevated +62% (most dynamic gain, §2.2); $\kappa = \varphi^{-1}$ "Water damps Fire" (§1.3) | **exploration/flow**—the permeable channel that surveys and flows |

The ke control cycle over the functional channels is therefore
**creation → storage → flow → execution → refinement → creation** (ke order
1→3→5→2→4→1):

- **Creation (Wood) controls Storage (Earth):** over-production starves memory.
- **Storage (Earth) controls Flow (Water):** unrefreshed storage damps exploration.
- **Flow (Water) controls Execution (Fire):** broad exploration restrains execution
  (the `gate-composite.ts` phase-coherence tradeoff is this pair).
- **Execution (Fire) controls Refinement (Metal):** uncurbed execution overrides
  refinement.
- **Refinement (Metal) controls Creation (Wood):** over-refinement damps new growth.

This control algebra is the *steering policy engine* for §3. When a session's
activity pushes one channel above its baseline (excess $\Delta > 0$), the ke algebra
predicts which channel is damped below baseline—the honest boundary condition for
"which tool family to trust next."

---

## 2. Tool-family → Wu Xing channel mapping

### 2.1 The retained CassiCore tool surface

The retained mind-runtime registers **13 mind tools** as thin spine delegates
(`CassiCore/MIGRATION-STATUS.md` §31): `collect_thoughts`, `graph_discover`,
`list_sessions`, `list_subagents`, `get_subagent_status`, `get_subagent_result`,
`system_health`, `debug_session`, `universal_search`, `cassandra_query_events`,
`cassandra_context_inspect`, `query_events`, and `mind_complete`, plus hidden
`[SPINE-TYPES]` seam tools. The retained package set is **22 packages**
(`CassiCore/MIGRATION-STATUS.md` §2)—the real tool surface includes mnemic-field
(attractors/engrams, kindling, consolidation), cognitive-feed, training-trust-ledger,
synapse, and the retained `@cassicore/tools` implementation files
(`CassiCore/packages/tools/src/implementations/`).

### 2.2 The agent-harness tool families

Independent of CassiCore, the agent harness exposes tool families for steering the
world and the field: file read/write/edit, bash/eval (execution), glob/grep
(refinement), browser (navigation), computer (desktop), web_search/web-fetch
(exploration), memory (retain/recall/reflect—MnemicField-compatible), hub (task
delegation + peer messaging), think, yield.

### 2.3 The mapping

Each tool family is a **coherence channel**—one of the five. The mapping is fixed by
the channel's functional role from §1.2, and each row cites the theory grounds.

| Channel | CassiCore retained surface | Agent-harness families | Dominant field operation | Grounding |
|---|---|---|---|---|
| **1 Wood—creation/growth** | `collect_thoughts` (deposits new thoughts into MnemicField); `spawn_subagent` fan-out; `todo_write` (creates a plan artifact) | `edit`, `write` (creates new structure); `task` delegation (spawns work); `retain` (writes durable facts) | **deposit** (write new engram) | Strongest coupling $\eta_1 = 1$; primary diagonal; sheng source vertex (`wa-pentagon-gate.md` §2.2, §2.4); `field-bridge/index.ts` deposit `{x,y,z,cy,ci,sigma}` is the field write (`CassiCore/.../field-bridge/index.ts`) |
| **2 Fire—execution/activation** | `runtime.executeTool` (`MindChannelServer.executeTool`, server.ts); retained run/exec tool implementations (`run-background`, `run-tests`, `shell-exec`) | `bash`, `eval`, `run-tests`, `run-tests.ts` implementations | **step** (advance the state; make it run) | First secondary $\eta = \varphi^{-1}$; the transforming sheng step (input leaves changed) (`wa-pentagon-gate.md` §2.4) |
| **3 Earth—memory/storage** | mnemic-field (`attractor.ts`, `engram-decomposer.ts`, `consolidation.ts`); `MnemicMemoryBackend` (`memory/{status,search,save}`, server.ts); `retain`/`recall`/`reflect` | memory `retain`/`recall`/`reflect` (`memory_edit`, `recall`, `reflect` on the harness) | **hold / retrieve** | The ke-target of channel 1; the jam attractor collects excess in Earth; Wood locks starve it (`wu-xing-cycle-structure.md` §2.2–2.3) |
| **4 Metal—refinement/extraction** | `graph_discover`, `universal_search`, `debug_session`, `get_subagent_result` (extract the distilled output); `cassandra_context_inspect` | `grep`, `glob` (pattern extraction), `lsp` (symbol extraction), reviewer/scout subagents | **distill** (extract signal from the held) | Elevated when released (§2.2); the refining post between Earth and Water in sheng (§1.1) |
| **5 Water—exploration/flow** | `query_events`, `cassandra_query_events` (event-flow traversal), `system_health` (observing flow / field status), `list_sessions` / `get_subagent_status` (surveying) | `web_search`, `web-fetch`, `browser`, `read` (exploratory), `computer` (desktop), scout subagent | **survey / flow** | Weakest baseline $\varphi^{-7}$ (most fluid, most dynamic gain on release, +62%); $\kappa = \varphi^{-1}$ "Water damps Fire" (`wu-xing-cycle-structure.md` §1.3, §2.2) |

**The ke control ring over tool families** (from §1.2): over-writing (Wood excess)
starves memory (Earth) by $\kappa \Delta$; over-exploration (Water) dampens execution
(Fire)—the exact pair `gate-composite.ts` encodes as phase-coherence vs. novelty
(two of the six score axes); uncurbed execution suppresses refinement; and so on.
This is the **monitoring grammar**: the toolkit's `gate_status` readout reports the
$\Delta_i$ per channel, and the ke algebra predicts which tool family is over- or
under-trusted at that moment.

---

## 3. The steering protocol

### 3.1 Tool action = deposit / gate-configuration

A **tool action** is one of two field operations, both grounded in the running field
primitives:

- **Deposit** (Wood/source, or any channel's action feeding the field): a write that
  positions a perturbation—the field-bridge `deposit {x,y,z,cy,ci,sigma}` command
  to the 7599 loopback (`CassiCore/.../field-bridge/index.ts`; `cassi_mind_engine.gd`,
  port 7599). A tool that *creates* (Wood), *executes* (Fire), *stores* (Earth),
  *refines* (Metal), or *surveys* (Water) emits a deposit into the field at the
  channel's coherence phase.
- **Gate-configuration**: a change to which channel is *open*—i.e., setting channel
  openness $b_i$ or excess $\Delta_i$. This is the "what does this action do to the
  cascade" reading. `collect_thoughts`, for instance, is a Wood deposit that also
  raises Wood's local $q$, nudging its gate open.

The read side is a **field probe**: `readProjection(k)` → `ProjectionCell[]` gives the
top-$k$ attractor cells; `readout`/`project`/`state` (`field-bridge/index.ts`,
`server.ts` snapshot/health) give the field and its stats. Every deposit is preceded
by a probe; every probe informs the next deposit's gate decision. **Never a
per-step pointwise forcing**: the closed-loop stability warning G34 (per-step
pointwise injection degraded the integrated attractor ~10×) is a hard constraint—
steering must be cadence-gated and strength-ramped from 0
(`UNIFICATION.md` §3.6, §5.1, and Phase 3's risk row).

### 3.2 Session = a field-steered sequence

A **session** is a sequence of tool actions treated as a single field trajectory: a
run of deposits and gate-configurations whose channels follow the sheng/ke cycles.
The spine's lifecycle tools already mirror sessions into the runtime
(`session_start/switch/branch/compact/shutdown` → `/v1/session/mirror` +
`appendEntry('mind.runtime.state', …)`, `CassiCore/MIGRATION-STATUS.md` §31), and
`/v1/snapshot` reports the session mirrors (`server.ts`). The steering policy—"which
channel is worth pushing next"—is a **Wu Xing policy**: read the current per-channel
$\Delta_i$ from projections, apply the ke algebra (which channel is being damped by
whom), and steer the channel that is released and under-baseline. This is a decision
rule with no free constants; the field state, not a learned agent, drives the choice.

### 3.3 Qi-time cadence sequences which channel is open when

The scheduler is `CassiCosmos/compute/cassi_qi_time.glsl`:

- Cell rung $k = \text{clamp}(\lfloor \log_\varphi(1/\rho) \rfloor, 0, K)$; rung cadence
  $\tau_k = \text{round}(\varphi^k)$ global steps.
- Gate $G = \sigma(\varphi^4 \cdot (q - 1/\varphi))$, $\sigma = \tfrac12(1+\tanh)$:
  opens when $q > 1/\varphi$.
- Twist $m = G \cdot (EY - \varphi EI)/(1+\varphi)$; a **local, charge-conserving** EY↔EI
  exchange.
- OFF mode = bit-identical pure copy (the guarded no-op baseline); PROBE mode applies
  the operator in scratch buffers.

In the toolkit, the cadence is the **temporal policy**: each channel is assigned a
rung cadence $\tau_k$, and the global step $t$ gates whether a channel is on its
"step"—a tool in a channel is only emitted when that channel's $\tau_k$ divides $t$.
The gate $\sigma(\varphi^4(q-1/\varphi))$ is the **admission test**: a channel's tool
is only honored when the channel's coherence $q$ exceeds the $1/\varphi$
(≈ 0.618) threshold. This is the temporal regularization G34 demands—injections
are spaced by $\varphi^k$, not every step (`UNIFICATION.md` Phase 3: "φ-cadence
injection as the temporal regularization").

**Boundary (FP-4):** this cadence policy is a *design rule*, not a measured mechanism.
The base field at current twist strength is measured as a rung-independent **mixing
clock** (G4c FP-4, `UNIFICATION.md` §4 Phase 6). Until the Phase-8 weak-twist probe
finds a regime where rung structure emerges (or honestly closes it), the toolkit must
not claim that the $\tau_k$ schedule *meaningfully* separates channels—only that it
is the φ-consistent spacing rule to test. This is recorded in §5.

---

## 4. Integration points in CassiCore (design only)

### 4.1 Where the toolkit would attach (without editing existing packages)

| Integration point | Existing primitive | Toolkit role |
|---|---|---|
| `@cassicore/mind-runtime` channel (`server.ts`, 7273) | `POST /v1/tools/execute` routes `{tool, params, sessionId}`; `/v1/snapshot`; `/v1/memory/search\|save` | A **read-only `gate_status` endpoint/tool** (below) would observe per-channel openness via projections—not route or gate execution |
| field bridge (`src/vendor/core/intelligence/field-bridge/index.ts`) | `readProjection(k)` → `ProjectionCell[]` (never throws, `[]` on engine-down) | The read source for the channel computation ($q$ per channel → $\Delta_i$ per channel) |
| `gate-composite.ts` (`@cassicore/thalamus`) | The Stage-2 `GateCompositeScorer` applies a ke-ring notion to the six score axes (relevance weight `0.5 + pc`) | **NOT extended.** The live $(1-q)$ field-factor is Stage 4 and out of scope; the composite stays `{off, cascade}` with `off` as the production default (§5) |
| `@cassicore/tools` retained 13 mind tools (`mind-definitions.ts`) | Registered thin delegates | Channel classification is a *labeling* the toolkit reads from, not a change to registration |
| `@cassicore/spine` | lifecycle → `/v1/session/mirror` | A session's channel trajectory is read from the snapshot mirrors (no edit) |

### 4.2 Minimal first artifact (design-only proposal)

**`gate_status` readout**—a read-only mind tool or channel endpoint that:

1. Calls `readProjection(k)` (e.g. $k=8$) on the 7599 bridge (`field-bridge/index.ts`).
2. Derives per-channel coherence $q$ by assigning each projected cell to a channel by
   its positional phase (Wood/Fire/Earth/Metal/Water), then computes excess
   $\Delta_i = q_i - b_i$ against the baseline table (§1.1).
3. Emits a five-channel readout: `{ channels: { wood: {b, q, delta}, fire: {...}, ... },
   keOrder: [1,3,5,2,4], predictedDamping: {...} }`—where `predictedDamping` is the
   ke-algebra statement of which channel is restrained/released by whom
   (`wu-xing-cycle-structure.md` §2.1).

This is **observation only**: it reads the field and reports the channel state in the
Wu Xing vocabulary. It does not route, gate, or alter any tool's execution—the same
parity-by-construction pattern as the qi_time OFF/probe split and the field-bridge
shadow semantics.

**What MUST NOT change:**

- No edits to any existing CassiCore package, spinner, or retained tool.
- `gateComposite` stays `{off, cascade}`, `off` remains the production default; the
  cascade variant stays an A/B arm (Stage-2 HOLD, §5).
- The tool-channel mapping is a **labeling layer** (a read-only classification), never
  an enforcement layer that blocks tools.
- No per-step field injection; the simulator and its 30-arm verify battery stay
  untouched.

A **router stub** (actually routing tool dispatch through channels) is explicitly
**not** the first artifact: it would change execution semantics and pre-empt the
honest gates in §5. It is named here only to state why it is deferred.

---

## 5. Honest gates

### 5.1 Stage-2 HOLD—the gate composite

The `GateCompositeScorer` (`CassiCore/packages/thalamus/src/gate-composite.ts`) is a
Stage-2 scorer, **off by default**; it requires `intelligence.thalamus.gateComposite =
'cascade'` to be wired in, and the plan keeps `off` as the production default with the
cascade variant as an A/B arm (`gate-composite.ts` header "Not wired in by default").
The owner strategy records **Stage-2 HOLD: gate composite never adopted to production;
off-states remain A/B arms** (workspace directive). For the Gate Toolkit this means:

- The toolkit's channel grammar is a **read/observe** layer that does not depend on
  the composite being live.
- Any artifact that *enforces* channel routing must be gated on a future pre-registered
  A/B that the composite survives—it is not assumed.
- The live $(1-q)$ field-openness modulation of the composite is explicitly **Stage 4,
  out of scope** (`gate-composite.ts` header).

### 5.2 FP-4—cadence claims wait on the weak-twist probe

G4c FP-4 measured the base field as a **rung-independent mixing clock at current twist
strength** (`UNIFICATION.md` §4 Phase 6 risk; §4 Phase 3 "at current twist strength the
base field is a mixing clock"). Therefore **every cadence claim**—that the
$\tau_k = \text{round}(\varphi^k)$ schedule meaningfully sequences channels, or that
rung structure decides *which channel is open when*—**waits on the Phase-8 weak-twist
probe**: reduce the qi-time twist strength so two-fluid competition (not the operator)
sets the relaxation timescale $T_{\text{rel}}$, with the n=2 cell's $T_{\text{rel}} = 5$
as the target signal and a pre-stated decision tree (rung-structured $T_{\text{rel}}$
in the weak regime → the φ² ladder is measurable; mixing clock at all strengths →
honest HOLD and the ladder claim closes) (`UNIFICATION.md` §4 Phase 8).

The companion pre-registration exists at
`CassiCosmos/research/cadence/weak_twist_probe_prereg.md` (landed 2026-08-15 by the
parallel weak-twist workstream): it is the Phase-8 milestone-1 probe with the **one
pre-registered weak strength** `q_sharp = φ²` (exactly one φ-power below the full
`φ⁴` baseline), the n=2 cell's `T_rel = 5` as its target signal, a pre-stated
decision tree (rung-structured `T_rel` in the weak regime → φ² ladder measurable;
mixing clock persists → honest HOLD), and a fixed stopping rule. Its exact contents
**supersede this paragraph where they conflict**. Until the probe runs and passes,
the toolkit's cadence policy in §3.3 is a **φ-consistent spacing rule to test**, not
a measured channel-selection mechanism.

### 5.3 §19—field-as-memory gate

The claim that MnemicField attractors / retrieval structure **tracks** field structure
—that a session's "field-steered sequence" genuinely reads from and writes to the
field as memory—waits on **§19 (field-as-memory gate): curation adoption, i.e.,
field structure tracks retrieval structure at z > 2 in ≥ 2/3 sessions**
(`UNIFICATION.md` §4 Phase 9 risk; the workspace directive records §19 as a
field-as-memory gate). Until that gate passes, the Earth (memory/storage) channel's
role in §3 is **instrumentation**: the toolkit can show where content lands in the
field, but cannot claim the field *is* the memory.

### 5.4 Summary table

| Gate | Status | What it blocks for the Gate Toolkit |
|---|---|---|
| **Stage-2 HOLD** | live | Any channel-*enforcement* artifact; adoption of the cascade composite; any dependency on the composite being production |
| **FP-4** | live | Any claim that the φ-cadence *meaningfully sequences* channels; the cadence policy is a spacing rule to test, not a mechanism |
| **§19** | live | Any claim that field structure *is* retrieval structure; the Earth channel's memory role is instrumentation until adoption |
| **G34** | measured negative | No per-step pointwise injection; steering must be cadence-gated and strength-ramped from 0 |

---

## 6. What this document does not do

- It does not change any code in CassiCore, CassiCosmos, CassiTheory, or the harness.
- It does not run the sim or the weak-twist probe; it does not adopt the gate composite.
- It does not claim Wu Xing cultural semantics are physics—only that the *cycle
  structure* (`wu-xing-cycle-structure.md` §5) supplies a coherent channel grammar.
- It names the minimal first artifact (`gate_status` readout) as a design proposal
  whose adoption is itself subject to a pre-registered gate before any code lands.

---

## References

- `CassiTheory/foundations/wa-pentagon-gate.md`—the five-channel gate: baselines $b_i = \varphi^{-(2+i)}$, coupling $\eta$ (diagonal vs side), effective openness $(1-q_{\text{eff}})$, control-release dynamics
- `CassiTheory/foundations/wu-xing-cycle-structure.md`—the sheng/ke cycles, $\kappa = \varphi^{-1}$, ring gain $\kappa^3$, ke-order lock profile, threshold $\Delta_c = \varphi^{-4}$, epistemic boundary
- `CassiTheory/foundations/wu-xing-derivation.md`—$w = 5$ derivation, gap $g$, conversion rate $\lambda = 1/(2w)$, $(1-q)$-gated code form
- `CassiCosmos/compute/cassi_qi_time.glsl`—the φ-cadence scheduler: $\tau_k = \text{round}(\varphi^k)$, gate $G = \sigma(\varphi^4(q-1/\varphi))$, OFF/PROBE modes
- `CassiCore/packages/mind-runtime/src/channel/server.ts`—the 7273 loopback: tools/execute, session/mirror, events/push, snapshot, health, memory endpoints
- `CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-bridge/index.ts`—deposit `{x,y,z,cy,ci,sigma}` + `readProjection(k)` → `ProjectionCell[]` over port 7599
- `CassiCore/packages/thalamus/src/gate-composite.ts`—the Stage-2 composite scorer (`{off, cascade}`, live $(1-q)$ factor deferred to Stage 4)
- `CassiCore/MIGRATION-STATUS.md`—the 22 retained packages; the 13 retained mind tools (§31)
- `CassiCore/packages/tools/src/implementations/mind-definitions.ts`—retained tool definitions
- `UNIFICATION.md`—§3.3 (orchestration is field dynamics), §3.6 (steering, not prediction), §4 Phase 3 (G34/FP-4 bounds), §4 Phase 6 (orchestration as field dynamics), §4 Phase 8 (weak-twist probe), §4 Phase 9 (§19 memory gate), §5.1 (closed-loop stability), §5.2 (two ε conventions)
- Skills: `cassi-ke-ring-gate-test`, `cassi-ke-ring-gate-level-test` (gate-level verification discipline), `prediction-test-preregistration` (claim-grade gating)
