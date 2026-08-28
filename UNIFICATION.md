# Cassi Unification—The Field as the Shared Substrate

## Status: Plan—August 2026 (second edition)

## Workspace

This Plan lives at the root of the unified Cassi workspace (`C:/Users/Carina/workspaces/Cassi`), which holds the four projects as sibling directories, each with its own git repo, plus a root repository for the shared Plan documents (`UNIFICATION.md`, `README.md`, `.gitignore`):

| Directory | Project | Substrate |
|---|---|---|
| `CassiAI/` | Cassi AI | Python/PyTorch neural field (QiField, FluidCord, Vulkan field cube) |
| `CassiCore/` | CassiCore | TypeScript npm-workspaces agent orchestration (33 packages under `@cassicore/*`) |
| `CassiTheory/` | Cassi Theory | the laws — markdown theory repo plus the spectral two-fluid solver and computation pipelines |
| `CassiCosmos/` | Cassi Cosmos | the Godot 4.7 GPU space-sim (extracted from the physics repo with full git history) |

The physics parent (`C:/Users/Carina/workspaces/physics`) **stays where it is** — it is not part of this workspace: it holds the two-fluid Python solvers' sibling work, `C:/Users/Carina/workspaces/physics/research/neural_closure/`, `C:/Users/Carina/workspaces/physics/data/fields/*.pt`, and `C:/Users/Carina/workspaces/physics/archive/`. Path references below use this topology: `CassiAI/`, `CassiCore/`, `CassiTheory/`, `CassiCosmos/` are relative to this workspace root; `C:/Users/Carina/workspaces/physics/...` is the explicit physics path.

The second edition also carries one external reference: the **Cassi Mind program** — the staged build-and-measure program that wired CassiCore to the field engine and measured what works — whose plan and verdict reports still live in the pre-migration CassiCore tree (`D:/carina/workspaces/cassicore/.opencode/plans/cassi-mind-plugin.md` §1–§34, `D:/carina/workspaces/cassicore/research/mind/*`). Its code artifacts are mid-port into the `@cassicore/*` layout (migration tables P2–P7). This edition incorporates its measured verdicts into the present-state map, the seams, and the phased program.

---

This is a **Plan** document (a genre, not an epistemic tier). Sections 1 and 2 describe what exists today and are grounded in files cited at each claim. Section 3 and the later phases of Section 4 are the **Speculative** vision: framework-consistent, mechanism sketched, no pinned prediction. Every claim in this document is either cited to a file that exists or explicitly labeled speculative.

## Abstract

Four Cassi projects exist today, each already implementing a piece of the same object—a two-fluid Yang/Yin field with Qi coherence and a $\varphi$-scaled gate vocabulary—in a different substrate: CassiCore (TypeScript) is an agent-orchestration platform whose memory layer is a "MnemicField" of attractors and engrams; Cassi AI (Python/PyTorch) trains neural field models (QiField, FluidCord) that predict next states of physics fields and byte streams; Cassi Theory (CassiTheory) derives the laws the field obeys; Cassi Cosmos (the Godot space-sim) runs the field itself on the GPU as a live physics engine with a TCP loopback bridge. The first edition mapped what each project is and found the seams where they already touch. The second edition adds what has changed since: the **Cassi Mind program** built the missing bridge and produced a ledger of honest verdicts—what the field can do for the brain (projection, curation), what it cannot yet do (plain prediction, $\varphi$-log-periodicity in text), and what it *is* (§28: the field-as-model architecture beats the vanilla baseline by 4.8×). The current vision, built on that ledger, is fourfold: **(1)** the field is the shared substrate—the engine's GPU buffers are a live, verified instantiation of the theory's field; **(2)** the AI is the field's *steering* dynamics, not its predictor—training must preserve Qi (irreducible self-surprise), not minimize it; **(3)** orchestration is field dynamics—tasks as deposits, scheduling as the $\varphi$-cadence operator, memory as attractors; **(4)** the field is the memory—kindling, dreams, and the engram galaxy as the living recall surface. Sections 3–4 lay out this vision with every measured constraint from the ledger attached.

## 1. The present-state map

Four projects, four substrates. The survey ground-truth corrects the working topology: Cassi AI is **not** inside CassiTheory (it is its own repo), and CassiCore is **not** a Python wrapper of CassiTheory ML code (it is a TypeScript agent platform extracted from a separate source repo). The map below is what the code actually is.

### 1.1 CassiCore—the orchestration platform (`CassiCore/`)

A TypeScript npm-workspaces monorepo of 33 packages under `@cassicore/*` (`CassiCore/packages/`; `package.json`). The P0–P8 modular migration is complete and all suites pass (`MIGRATION-STATUS.md`); a second migration wave (recon + the P2–P7 migration tables) is porting the Mind-program artifacts into the package layout. Three packages define what it is:

- **MnemicField** (`CassiCore/packages/mnemic-field/src/`): a memory system built in field vocabulary—`attractor.ts`, `engram-decomposer.ts`, `backpropagation.ts`, `consolidation.ts`, `cortex.ts`, `healpix.ts`, `umap.ts`, `vq-prototypes.ts`. Memory is stored and retrieved as a field of attractors over engrams, not as a key-value store. This is the closest CassiCore gets to a "field" today: a learned memory manifold, not a PDE.
- **Mind runtime** (`CassiCore/packages/mind-runtime/src/channel/server.ts`): an always-on process that owns MnemicField plus the retained intelligence layer and serves a loopback HTTP/1.1 JSON channel on `127.0.0.1:7273` with 10 endpoints: `/v1/tools/execute`, `/v1/session/mirror`, `/v1/events/push`, `/v1/snapshot`, `/v1/health`, `/v1/memory/status`, `/v1/memory/search`, `/v1/memory/save`, `/v1/shutdown`. This is the AI's orchestration surface: tools, sessions, and memory over one loopback channel.
- **Spine** (`CassiCore/packages/spine/`): the oh-my-pi extension that registers the retained mind tools (13 tool delegates: `collect_thoughts`, `graph_discover`, `list_sessions`, `universal_search`, `memory_search`, …) and a `MnemicMemoryBackend` that proxies `/v1/memory/*`.

**Mind-program artifacts (port in flight).** The bridge from CassiCore to the GPU field exists and is measured: the plugin and its client live in the pre-migration tree (`D:/carina/workspaces/cassicore/mind-plugin/`: `MindClient` with fail-fast and race-timeout discipline, `StandardMindFieldEncoder` seam); the package-layout port has already landed the field bridge (`CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-bridge/`), the field encoder (`.../field-encoder/`), the gate composite (`CassiCore/packages/thalamus/src/gate-composite.ts`), the inter-field bridge (`CassiCore/packages/mnemic-field/src/self-model/inter-field-bridge.ts`), and the host-wired test suite (`CassiCore/packages/mnemic-field/tests/host-wired/`). The verdict ledger that governs them is §1.6.

**What it provides the unification:** the AI-I/O and orchestration runtime—a live process with a memory field, a tool surface, a loopback protocol—and, since the Mind program, a measured field seam (encoder, bridge, projection, curation) ready for adoption review.

### 1.2 Cassi AI—the neural field (`CassiAI`)

A standalone PyTorch project (own `AGENTS.md`; no build system). The active trunk is **QiField** (`CassiAI/cassi/qi_field.py`, 1436 lines), a complex field model:

- The field $\psi \in \mathbb{C}^{B\times N\times d}$ is stored as real/imag pairs; **Yang = Re(ψ), Yin = Im(ψ)**. Qi evolves by a continuity equation, $Q_{t+1} = \rho\cdot Q_t + \varphi^{-2}\cdot\tanh(\varepsilon^2/\varepsilon_0^2)\cdot\psi^2 - \gamma\cdot Q_t - \nabla\cdot(Q\cdot v_Q)$, where ε² is the self-prediction gap |ψ − P[ψ]|² (`qi_field.py` module docstring).
- **13 chakras** with Fibonacci/φ-scaled widths (`_chakra_utils.py`: two interleaved Fibonacci sequences [3, 8, 5, 13, 8, 21, 13, 34, 21, 55] + head; `CassiAI/cassi/cord.py` line 51: "13 φ-scaled chakra widths").
- **Breath** (`CassiAI/cassi/breath.py`): a dual-heart oscillator—Yang beats at ω = φ ≈ 1.618, Yin at ω = φ⁻¹ ≈ 0.618, "the frequency ratio φ:φ⁻¹ = φ²:1 is the fundamental breath ratio".
- **Prediction operator** P[ψ] from per-chakra transceiver interference (`PredictionOperator`); a **SelfAwarenessController** (α/γ/ρ/perturb/m_self, `CassiAI/cassi/self_awareness_controller.py`) modulates the field; **QiPatternMemory** grows/dissolves neurons keyed on the field's own state (neurogenesis, `field_step`).
- **continuous_mode** (`train_qi_field_physics.py`, `physics_field_model.py`): input `[B, N, 1024]` → Linear to d=512 → K_train IIR steps → Linear to `[B, 1024]`; the physics-cache trainer (`experiments/train_qi_field_physics.py`) is the current physics regression entry point.
- **The physics-to-byte transfer** (`CassiAI/cassi/physics_field_model.py` `load_physics_to_fluidcord`): PDE coefficients learned on physics frames (nu_logit, hbar_logit, mass_logit, g_logit, chi_logit, A_B_logit, advection_logit, alpha_logit) are copied into FluidCord's `fluid_field` by exact name—the architecture's proof that a learned PDE operator transfers between tasks.
- **The Vulkan field cube** (`shaders/`): a full two-fluid compute stack in GLSL—`condensate_field.comp`, `two_fluid_diag.comp`, `qi_transport.comp`, `wu_xing_modulate.comp`, `wake_propagate.comp`, `self_pred_feedback.comp`, `field_predict.comp`, `embed_field.comp`—with `qi_cube.py`/`pde_cube.py` runners. The same field vocabulary, compiled to the GPU, outside Godot.

**Training data** (`CassiAI/cassi/multimodal_loader.py`, `CassiAI/build_physics_cache.py`): a `physics_cache.pt` dict holding `windows` `[N_windows, win_len=8, D=1024]` float32, plus `input_frames=4`, `horizons=[1]`, `train_idx`/`val_idx`, `norm_stats` (per-family z-score). Sampling yields x = `[B, 4, 1024]`, y = `[B, 1, 1024]`. The source fields are flattened 2D grids (`[T, H, W] → [T, 1024]`, i.e. 32×32; `CassiAI/build_physics_cache.py` flatten step; the source files live in the physics parent at `C:/Users/Carina/workspaces/physics/data/fields/*.pt`—advect/bouss/burgers families; burgers/pfc/yang are skipped as NaN families).

**What it provides the unification:** the field-AI—a trained model whose input/output format (1024-dim frames, 4-in-1-out windows) and whose internal vocabulary (chakras, breath, gates, self-prediction) are already the theory's. Its architecture search has now been measured (§1.6, Stage 5b): the cord-style field architecture is the one to reuse; the vanilla predictor is rejected.

### 1.3 Cassi Theory—the laws (CassiTheory)

The physics: a two-fluid Yang/Yin field governed by a single PDE with φ the only parameter (`CassiTheory/foundations/cassi-first-principles.md`), a φ-cascade ladder of scales (`CassiTheory/foundations/dimensionful-cascade.md`), and a gate vocabulary: the conversion openness $g(q)$, the five-channel Wu Xing gate (`CassiTheory/foundations/wu-xing-derivation.md`, `CassiTheory/foundations/wu-xing-cycle-structure.md`), the Qi gate pinch at $r = \varphi^{-1}$ identified as self-awareness (`CassiTheory/consciousness/consciousness-from-phi.md`), 13 chakras as cascade bubbles (`CassiTheory/consciousness/chakras-as-cascade-bubbles.md`), emotions as gate configurations (`CassiTheory/consciousness/emotions-as-gate-configurations.md`), and the phase current $J = \rho\nabla\theta$ as Qi flow (`CassiTheory/foundations/qi-flow-double-helix.md`). The doctrine documents carry explicit epistemic tiers and a Fit-Status Ledger (`CassiTheory/EPISTEMIC-MAP.md`, `CassiTheory/audit.md`).

The code that supports the theory lives here: the spectral two-fluid solver `CassiTheory/two-fluid/cassi_two_fluid_3d_gpu.py` (which carries a `qi_gate` flag, line 310), the GPU N-body solver `CassiTheory/two-fluid/cassi_nbody.py`, and the computational pipelines in `CassiTheory/computations/`.

The Mind program's time program also lives here: the Qi-as-time clock (`CassiTheory/speculations/qi-as-time-clock.md`), the mass–time equivalence derivation (`CassiTheory/speculations/qi-time-ladder-derivation.md`) and its referee (`CassiTheory/speculations/referee_qi_time_ladder.py`) — the derivation that fixed the framework's time-ladder exponent at 2 (§1.6).

**What it provides the unification:** the laws—the PDE the field obeys, the gate vocabulary the AI implements as architecture and the sim implements as shaders, and the epistemic discipline (tiers, registries) that keeps claims from inflating. The discipline is load-bearing: every verdict in §1.6 travels with its pre-registration and its decision tree.

### 1.4 Cassi Cosmos—the field engine (`CassiCosmos/`)

The Godot 4.7 space-sim runs the field on the GPU. Three layers matter:

- **The standalone physics engine** (`CassiCosmos/scripts/cassi_physics_engine.gd`, 1000 lines): a self-contained, verbatim port of the sim's GPU physics chain (mass deposit → spectral Poisson FFT → two-fluid PDE → BH sector → cell-centered ∇(g·Φ) → Yin/Yang dual lattice → cached-acc KDK) that runs on any RenderingDevice, including a **local RD created on a worker thread** (`start_threaded`/`submit_steps`/`poll`). Its published state, `readback_snapshot(packed)` (line ~540), returns `{"pos": [N*3], "vel": [N*3], "field_q": [grid_N³], "pot": [grid_N³], "t", "packed"}` with grid_N = 64 default (262144 cells), plus `readback_telemetry` (q_mean/q_min/q_max, π saturation fractions, ρ guard hits, eps, hubble, scale factor). The field buffers are `_field_ey`, `_field_ei` over the 64³ grid, with the two-fluid wave operator `∂²EY/∂t² = c²∇²EY − ω₀²(EY − φEI)` / `∂²EI/∂t² = c²∇²EI + ω₀²(EY − φEI)` (`CassiCosmos/cassi_contract.py`).
- **The sim orchestration** (`CassiCosmos/scripts/cassi_sim.gd`, 5027 lines): `physics_decoupled` mode runs the physics on the engine's worker thread and turns the sim's global-RD buffers into **mirrors** fed by published snapshots (`mirror_publish_cadence`, fp16 packed pos/vel half-pairs). The recorder (`CassiCosmos/scripts/main_recorder.gd`) drives Movie Maker video runs; the verify battery (`CassiCosmos/verify/README.md`) runs 30 arms, including `verify_mind_engine` (a no-op gate on the mind engine).
- **The mind engine** (`CassiCosmos/scripts/cassi_mind_engine.gd`, 513 lines): a self-contained two-fluid sidecar that runs `CassiCosmos/compute/cassi_two_fluid.glsl` on a local RD and serves a **loopback TCP bridge on `127.0.0.1:7599`**, line-delimited JSON: `ping`, `clear`, `deposit {x,y,z,cy,ci,sigma}` (TSC scatter into EY/EI, charge-exact), `step n`, `state`, `project k` (top-k attractor readout, q = EY²+EI², sorted), `readout` (ey/ei/q/eps2 as base64 float32 arrays, grid_n³ each), `snapshot`. This is a live field I/O protocol: read = readout/project, write = deposit.

The sim also contains its own machine program: `CassiCosmos/research/machine/m1_design.md` (M1, a two-level φ-zoom parent→child chain, gates G42–G46 PASS) and `CassiCosmos/research/cascade_machine/m2_design.md` (M2, a 49-level offline φ-cascade tree with a falsifier ledger and a calibrated P(k) log-periodicity search), plus the Mind program's time machinery: `CassiCosmos/compute/cassi_qi_time.glsl`—the "Qi-time operator", a φ-cadence multiscale mixing gate on the 64³ field (`τ_k = round(φ^k)` rung cadence, gate `G = σ(φ⁴·(q − 1/φ))`, local EY↔EI twist, guarded no-op baseline)—and its telescope companion `CassiCosmos/compute/cassi_qi_time_exp.glsl` with the `verify_telescoping` battery (`CassiCosmos/scripts/verify_telescoping.gd`). The sim's φ-aspect box, Qi color system (`particle_color_mode` 0–3: Cassi gradient, velocity rainbow, Qi rainbow, Qi double rainbow; `qi_cycle`/`qi_pinch` bands; auto-track), and particle-merge gate (only where `q_coh > φ⁻²`) are the visual and structural vocabulary the engram-galaxy phase (§4, Phase 9) builds on.

**What it provides the unification:** the runtime substrate—a GPU field engine with published state, a verified battery, a TCP bridge, an in-progress multiscale machine (M1/M2), and a φ-cadence scheduler (qi-time) with its measured verdict (§1.6).

### 1.5 The physics parent—the closure workstream (`C:/Users/Carina/workspaces/physics`)

The parent repo holds the two-fluid Python solvers and, critically, `C:/Users/Carina/workspaces/physics/research/neural_closure/` (`C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md`, `closure_prototype.py`, `closure_wave2.py`): a **learned sub-grid closure for the two-fluid wave PDE**. The closure target is the operator residual `g(s_c) = coarsen(nl(refine(s_c))) − nl(s_c)` with `nl(ψ) = ν·ψ·(ψ_y − φψ_i)²`—the exact sub-grid content a coarse grid misses. A per-cell MLP (7 field features → 2 kick corrections, 2434 params) is trained purely from the PDE's own fields, no observational data. First measured results (closure_design.md §7): the fine breather matches `√(ω₀²(1+φ))` to 0.08% (G33 PASS), and the closure improves the energy spectrum—but per-step injection of the learned forcing degrades the integrated attractor by ~10× (G34). The remedies (regularized injection, trajectory-level loss, nonlocal architecture) are the design constraints for every phase that injects learned output into the field (§5.1).

### 1.6 The Cassi Mind program—what has been built and measured

The program that wired CassiCore to the mind engine, stage by stage, each with a pre-registered gate and an honest verdict. Plan and reports: `D:/carina/workspaces/cassicore/.opencode/plans/cassi-mind-plugin.md` §1–§34, `D:/carina/workspaces/cassicore/research/mind/*` (pre-migration paths; the port is in flight). The ledger, in stage order:

- **Stage 0–1 — engine, bridge, deposit.** Mind engine + charge-exact TSC deposit + TCP bridge (7599, line-JSON) + σ partition-of-unity contract (σ=1 bit-identical; σ≠1 per-axis renormalization). 21/21 gates; live-verified. **PASS (foundation).**
- **Stage 2 — gate composite.** φ-cascade composite of gate signals (`gate-composite.ts`; config `intelligence.thalamus.gateComposite` ∈ {off, cascade}; §14 A/B pre-registered). **HOLD** — never adopted to production; default 'cascade' only during the overhaul period (§29).
- **Stage 3 — ln-φ text objective.** Prose log-periodicity test over 32 CassiTheory documents: mean_z = +0.39, only 3% with z > 2. **Honest NULL** — no φ-log-periodicity in text structure (`research/mind/lnphi_text_objective.py`, `CassiCosmos/research/mind/lnphi_text_objective.py`). The companion structural measurement (361,045 engrams; `stage3_structural_report.md`): cascade-rung, winding, and coherence-budget hypotheses H1–H3 **UNSUPPORTED** (z_phase −0.90, −0.11; ΔAIC +19.2 favors the plain power law); H4 was **NOT MEASURABLE** at the time (no merge journal existed — the journal is now wired and recording).
- **Stage 4 — field-read projection.** `project k` top-attractor readout; 23/23 battery; live smoke exact (a deposit at (0.25, −0.4, 0.6, 1.4562, 0.9) puts the top cell exactly at the anchor, q = 0.4187). Plugin action + context hook; three hang bugs fixed (fail-fast client, race timeout, offline resolve). The §19 positional-agreement harness now collects by default: mean 3D distance from retrieved engram to nearest attractor cell vs 1000 uniform draws on the quantized 64³ lattice, z = (null_mean − obs)/null_sd; adoption threshold z > 2 in ≥2/3 sessions.
- **Stage 5 — mind-native training.** Small 3D conv trained on 150 live field snapshots: final 1.2374 vs predict-unchanged floor 0.5571. **REJECT (honest branch 3)** — the vanilla predictor loses to doing nothing (`stage5_report.md`).
- **Stage 5b — field-as-model.** Cord architecture (φ/cord two-fluid features) vs matched vanilla GRU on physics boards. Five successive INVALID gates, each diagnosing the next confound (amplitude-metric inflation → increment metric → Euler ejection → Verlet → 10.9× radius → true-circular v_circ = 0.75232). **ADOPT**: increment-loss field arm 0.140207 vs GRU 0.669795 (**4.78×**), final-5 monotone (`stage5b_terminal_report.md`). The first terminal adopt of the program — "the field IS the model" is grounded. This is the architecture license for the field-AI loop (§4, Phase 2).
- **Stage 3-wiring — tiered consolidation.** Cascade-rung/winding/coherence-budget proxies over the real consolidation path; merge journal records every consolidation (pure function; decision untouched). 23/23 tests (`stage3_wiring_report.md`).
- **Overhaul defaults (§29, owner directive).** All new mechanisms default-ON during the overhaul period — encoder, bridge, merge journal, tiered 'cascade', retrieval positions, projection, attractor boost — so every daemon session measures them; off-states remain as A/B baseline arms; prior verdicts (Stage-2 HOLD, etc.) still govern production adoption. Tests: mnemic-field 25/25, field-bridge 11/11, thalamus 39 + 1 deliberate HOLD assertion.
- **Qi-time engine + theory.** Operator (`cassi_qi_time.glsl`): G1–G3 PASS (5.7e-8); G4 NULL (z = −0.959) → **HOLD branch 2** (`qi_time_engine_report.md`). Theory (`qi-as-time-clock.md`, `qi-time-ladder-derivation.md` + referee): mass–time equivalence **exponent(τ) = (3−m)/2**; the framework's Compton ladder (m = −1, wake geometry) → **exponent 2**; m = +1 trivializes to constant speed (spiral-dynamics c independence). The φ¹ ladder is excluded by a structured honest negative: the φ-locked eigenvalue lattice fails at density ×17, ΔAIC +4.00; Routes 1/3 are blocked by derivation. **FP-1..3 recorded.**
- **Scale-telescoping Wave-2.** `cassi_qi_time_exp.glsl` + `verify_telescoping` (e=1 bit-identical to the frozen §32 values). G1–G3 PASS; G4a replicates the null; **G4c FP-4 = branch "1": mixing clock** — T_rel is rung-independent (≈1 step) at current twist strength; the n=2 cell (T_rel = 5) is the hint that a weaker twist would let two-fluid competition set the timescale. **HOLD** (`telescoping_battery_report.md`, `scale_telescoping_design.md`). The weak-twist probe is the named next pre-registration.
- **Projection-as-curation.** Direct wiring: `readProjection(8)` → HEALPix spatial index (the same lookup kindling uses) → content-term overlap → bounded salience bonus min(0.10, 0.05·q_norm·overlap); config `intelligence.thalamus.attractorBoost` ∈ {off, 'field'}, default 'field'. 27/27 tests; §34 adoption gate: §19 z > 2 in ≥2/3 sessions.
- **Survey + synthesis.** `overhaul_candidates_core.md`: **DreamEngine is dead-wired** (no production caller; the dream phase no-ops every consolidation cycle) + spark-gate/sector-vq/tier-schedule/rung-lr candidates; `overhaul_candidates_packages.md`: AGENTS stale paths (fixed by the current migration wave) and the trellis vindex `has_model_weights:false` vs the 1.5 GB `down_weights.bin` on disk. `space_sim_recon_2026_08_14.md`: single kernel, lockstep; `physics_decoupled` producer + GPU-direct FieldQ — zero per-frame readbacks at 2.5M particles.

Every one of these verdicts is a boundary condition for §4: a new phase that ignores them re-pays the cost of discovering them.

## 2. The real integration seams

### 2.1 S1—Published engine state vs the training-cache format: a real mismatch, closeable

The engine publishes `readback_snapshot` = `{pos [N*3], vel [N*3], field_q [262144], pot [262144], t}` (`CassiCosmos/scripts/cassi_physics_engine.gd`). The training cache wants `windows [N, 8, 1024]` float32 frames (`CassiAI/build_physics_cache.py`), where each frame is a flattened 2D 32×32 grid. Three concrete mismatches:

1. **Dimensionality**: 262144-cell 3D field vs 1024-dim 2D frames. A projection is required. The clean options, in order of parsimony: (a) run the mind engine at `grid_n = 32` and take a midplane slice (32×32 = 1024 exactly, zero interpolation, format-identical to the existing 2D turbulence frames); (b) block-mean-pool the 64³ field 4×4×4 → 1024; (c) a 1024-mode spectral truncation. The choice is a design decision to record, not a blocker.
2. **Phase information**: `readback_snapshot` exposes `field_q` (coherence density) and `pot`, but not EY/EI. The training signal is the complex field (QiField's Yang=Re, Yin=Im). The mind engine's `readout` already returns ey/ei base64 (`cassi_mind_engine.gd`), so a writer should use the mind engine's readout, not the physics engine's snapshot.
3. **Normalization**: the cache is per-family z-scored with `norm_stats` saved; an engine-state family needs the same treatment (per-run or per-initial-condition family).

The seam is closeable with zero sim edits: the mind engine already serves everything a writer needs over TCP.

### 2.2 S2—The same two-fluid operator in four dialects

The operator the theory derives, the sim runs, and the ML learns is recognizably one operator:

- **Theory** (spectral, advective): `∂ₜψ₀ = −u·∇ψ₀ + ν∇²ψ₀ − λ(ψ₀² − φψ₁²)ψ₀ + S₀` (`CassiTheory/foundations/cassi-first-principles.md` §1.3, as quoted in `C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` §1.1), with the φ-attractor potential `V_attr = (λ/2)(ψ₀² − φψ₁²)²`.
- **Sim engine** (wave leapfrog, cell form): `∂²EY/∂t² = c²∇²EY − ω₀²(EY − φEI)`, `∂²EI/∂t² = c²∇²EI + ω₀²(EY − φEI)` (`CassiCosmos/cassi_contract.py` §KEY EQUATIONS; `CassiCosmos/compute/cassi_two_fluid.glsl`; `C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` §1.2: the wave system IS the scalar sector of the doctrine's field equations, realized as a leapfrog oscillator).
- **ML learned coefficients** (`CassiAI/cassi/physics_field_model.py`): nu, hbar, mass, g, chi, A_B, advection, alpha—the same diffusion/coupling/source terms, learned by regression on physics frames and transferred byte-for-byte into FluidCord (`load_physics_to_fluidcord`).
- **Closure target** (`C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md`): the sub-grid residual of exactly the wave operator, `nl(ψ) = ν·ψ·(ψ_y − φψ_i)²`—the derivative of the doctrine's V_attr.

The transfer `load_physics_to_fluidcord` already proves coefficient transfer works by name match. The unification seam: one operator specification with four parameterizations, of which two (theory↔sim) are already claimed identical by design and one (ML↔sim) is a one-line weight copy away from being testable. The Mind program adds the fifth dialect: the cord architecture that won §28 is the learned parameterization that actually generalizes (§1.6, Stage 5b).

### 2.3 S3—The gate/chakra/breath vocabulary is the same structure

- **13 chakras**: theory derives 13 as cascade bubbles on the 26-rung human window (`CassiTheory/consciousness/chakras-as-cascade-bubbles.md`); QiField hard-codes `C = 13` with φ/Fibonacci-scaled widths (`CassiAI/cassi/qi_field.py`, `_chakra_utils.py`).
- **φ⁻² threshold**: the AI's decoherence threshold (`AGENTS.md` §4.1; `fluid_field.py` `phi_inv_sq`); the sim's particle-merge gate `q_coh > φ⁻²` (`CassiCosmos/scripts/cassi_physics_engine.gd` header); the theory's φ⁻² coherence floor.
- **Breath**: the AI's dual-heart oscillator Yang ω=φ, Yin ω=φ⁻¹ (`CassiAI/cassi/breath.py`); the theory's yin = φ⁻¹ fixed-point ratio.
- **Gates**: the theory's conversion openness g(q) and five-channel Wu Xing gate (`CassiTheory/foundations/wu-xing-cycle-structure.md`); the AI's breath-gating and self-awareness controller; the sim's `qi_gate` flag in the spectral solver (`CassiTheory/two-fluid/cassi_two_fluid_3d_gpu.py` line 310), the qi_time gate `G = σ(φ⁴(q−1/φ))`, and the mind engine's charge-exact deposit.

Same structure, three implementations, zero shared code. This is the vocabulary seam: a theory-grounded gate is already the AI's architecture and the sim's shader.

### 2.4 S4—Two ε conventions and two q conventions (the explicit mismatch)

The theory and sim define **ε = EY − φEI** (the φ-disequilibrium; `CassiCosmos/cassi_contract.py`; the closure's `dev`). The AI defines **ε = ψ − P[ψ]** (the self-prediction gap; `qi_field.py` docstring). The sim's `field_q` and the theory's q are coherence densities; the AI's Q is a surprise field (self-prediction error) that drives learning. The theory's axiom—"a system that perfectly predicts itself has zero Qi—it is dead" (`AGENTS.md` §1) and "the formalism requires irreducible Qi—training to minimize self-prediction kills the system's dynamics" (`CassiAI/cassi/physics_field_model.py` training_loss comment)—is in direct tension with next-frame prediction as the training objective. Any unification must resolve which ε the AI optimizes. The second edition names the resolution: **the AI must not minimize ε; it must preserve it within bounds** (§3.6, Phase 7). The measured evidence agrees — the only predictor that beat a floor was the steering-style architecture, not the error-minimizer (§1.6, Stages 5/5b).

### 2.5 S5—Bridges that already exist, and the one that closed

Existing, live:

1. **Mind engine TCP bridge** (`cassi_mind_engine.gd`, port 7599): deposit/step/state/project/readout/snapshot. The field I/O primitive—read = readout/project, write = deposit. Verified by `verify_mind_engine` (attractor-ratio deposit stays at the fp32 floor; off-ratio evolution conserves charge) and by the projection battery (23/23).
2. **Shared-memory n-body bridge** (`C:/Users/Carina/workspaces/physics/archive/nbody_shm_server.py` → `CassiCosmos/scripts/shm_sim.gd`): Python writes binary frames (`[u32 frame_id][u32 N][N×f32×3][f32 q][f32 eps]`, atomic tmp+rename) to `/dev/shm/nbody_frame.bin`; Godot polls them. Python→Godot direction, Linux path, but the pattern exists.
3. **Mind-runtime HTTP channel** (`@cassicore/mind-runtime`, port 7273): tools/sessions/events/memory over loopback.
4. **Physics-cache pipeline**: `C:/Users/Carina/workspaces/physics/data/fields/*.pt` → `CassiAI/build_physics_cache.py` → `physics_cache.pt` → `MultimodalDataLoader` → QiField trainer.
5. **Physics-to-byte transfer**: `load_physics_to_fluidcord` (PDE coefficients, physics → byte model).
6. **Closure integration design** (`C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` deliverable 1d): the learned term enters `cassi_voronoi_cells.glsl` as a scratch layer with `closure_strength = 0.0` default (bit-identical battery).

**The missing one, as of the first edition, is now closed:** CassiCore ↔ the GPU field. The Mind program built the adapter (mind-plugin + `MindClient`, field encoder seam, field bridge, `readProjection(k)`), wired it into the daemon (encoder, bridge, merge journal, tiered cascade, retrieval positions, attractor boost — all default-ON under §29), and verified it end-to-end against the live engine (§1.6). What remains is mechanical: completing the port into the `@cassicore/*` layout (migration tables P2–P7) and re-running the suites there. The bridge exists; it is mid-move.

## 3. The field-as-AI architecture (proposal)

The proposal in the framework's own language. **Grounded** items cite files; everything else is **Speculative** and labeled.

### 3.1 The field is the substrate [Grounded]

The engine's GPU buffers—`_field_ey`, `_field_ei`, `_field_q`, `_field_vel` over the 64³ grid, plus `_pos_buf`/`_vel_buf` (2.5M particles) and the `pot` field (`CassiCosmos/scripts/cassi_physics_engine.gd`)—are a real, running, verified instantiation of the theory's two-fluid field. The mind engine already serves it over TCP. Nothing needs to be built to have a field; the substrate exists.

### 3.2 The AI is the field's learned dynamics [Grounded on both sides; the loop is the Speculative part]

QiField is already a field model trained on field states (`train_qi_field_physics.py`, continuous mode, `[B,4,1024] → [B,1024]`). The engine is already a field that publishes states. The closed loop—engine runs → state → model predicts → engine applies—is the natural composition of two existing pieces. What does not yet exist: (a) engine states in the cache format (Phase 1), (b) a model trained on engine states (Phase 2), (c) an injection path from predictions back into the engine (Phase 3; the mind engine's `deposit` is the only write primitive today). The loop is the speculative claim; its failure modes are partly measured (§5.1) — and, since the first edition, its *architecture* has been settled by measurement: the predictor to use is the cord architecture (Stage 5b ADOPT, 4.78×), not a vanilla conv (Stage 5 REJECT).

### 3.3 Orchestration is field dynamics [Speculative, with grounded primitives]

Tasks as perturbations: the mind engine's `deposit {x,y,z,cy,ci,sigma}` is a field write; the theory's gates (open/closed channels, the Wu Xing 5-cycle, the qi gate pinch) are the vocabulary for what a perturbation means; the sim's `CassiCosmos/compute/cassi_qi_time.glsl` already implements a φ-cadence scheduler as a field operator (rung cadence `τ_k = round(φ^k)`, guarded no-op baseline) — the machine that turns "which subsystem runs when" into field dynamics. The speculative step: a task list is a set of deposits/gate-configurations in a shared field, and the field's own dynamics (not a scheduler) sequences them. MnemicField's attractors (`CassiCore/packages/mnemic-field/src/attractor.ts`) are the memory-side analogue of QiPatternMemory's grown neurons (`qi_field.py`); the measured constraint is that the base field, at current twist strength, is a rung-independent mixing clock (Stage G4c FP-4) — the φ-cadence ladder is real machinery, but which clock the field actually keeps is an open measurement, not a settled claim.

### 3.4 AI I/O is field probing [Grounded as primitives, Speculative as a system]

Read = field sampling: the mind engine's `readout` (full ey/ei/q/eps2) and `project k` (top-k attractor cells with physical coordinates) are exactly reads; the physics engine's `readback_snapshot` is the batch read; the recorder's telemetry (`q_mean`, π saturation) is the scalar readout. Write = field injection: `deposit` (charge-exact TSC scatter) and the closure's kick augmentation (`coarse_kick + closure_model(features(s_c))`, `C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` §2.1) are exactly writes. The speculative part is that this read/write pair is sufficient I/O for the AI's agentic surface—that a model whose input is `readout` and whose output is `deposit` can express the tasks the mind-runtime's tools currently express. The first half of this claim is now grounded: field reads already drive memory curation (projection-as-curation, §1.6) and the §19 positional-agreement harness is measuring whether field structure tracks retrieval structure in live sessions.

### 3.5 What the theory would demand [Speculative]

A unified field-AI would have to obey the theory's own rules: the learned dynamics must respect the φ-attractor (r → φ), the wake/closure structure, and the gate vocabulary; any learned forcing must be cascade-suppressed and φ-consistent (the closure's wave operator is the same PDE as the shader, so it is theory-consistent by construction; QiField's P[ψ] is not yet); and the training objective must keep Qi irreducible (§2.4). These are constraints, not decorations.

### 3.6 Steering, not prediction—the aliveness principle [Grounded in the measured ledger, Speculative as an objective]

The first edition named the central tension: the AI's next-frame loss minimizes the self-prediction gap that the theory defines as Qi, and "training to minimize self-prediction kills the system's dynamics." The Mind program then measured both sides of it. Stage 5 REJECT: a vanilla predictor trained to minimize error on live field snapshots finished at 1.2374 — worse than the predict-unchanged floor (0.5571). Doing nothing beat the error-minimizer. Stage 5b ADOPT: the architecture that won was not the one that minimized error harder; it was the field-structured one whose loss is an *increment* metric, scored on how its steering compounds through integration.

The aliveness principle states the conclusion: **the field-AI is a steering operator, not a predictor.** Its objective is not min ε² but bounded ε² — keep Qi irreducible (the system alive) while staying stable and φ-consistent. Prediction is the probe; steering is the art; Qi is the resource the objective conserves rather than eliminates. The known failure modes (§5.1, G34's 10× degradation under naive per-step injection) are exactly what an aliveness objective must encode as constraints: regularized injection, cadence discipline, hard stops on divergence. Phase 7 is the program that tries to formulate it; its first deliverable may be an honest negative, which is a valid Plan outcome.

### 3.7 Multi-scale time—the qi-time ladder [Grounded, one open measurement]

The theory's cascade is a ladder of scales; the time program derived what a ladder of *clocks* must look like. The mass–time equivalence fixes the cadence exponent: **exponent(τ) = (3−m)/2**, so the framework's Compton ladder (m = −1) yields **τ ∝ φ²** per rung; m = +1 is the constant-speed trivialization. The φ¹ ladder — the naive "each rung one φ-slower" reading — is excluded by a structured honest negative (φ-locked eigenvalue lattice, density ×17, ΔAIC +4.00). The engine implements the operator (`cassi_qi_time.glsl`): τ_k = round(φ^k) cadence, twist gate G = σ(φ⁴(q−1/φ)); the telescope battery (`cassi_qi_time_exp.glsl`) made the cadence exponent a push-constant. The open measurement: at current twist strength the base field relaxes as a rung-independent mixing clock (G4c FP-4, branch "1"; the n=2 cell's T_rel = 5 is the only rung-structure hint). The weak-twist probe (§4, Phase 8) is the named next experiment; until it runs, "the field keeps φ² time" is a derived target, not a measured fact.

## 4. A phased program (second edition)

Each phase lists the first file-level milestone, what it proves, and its risk. Phases are ordered so each one leaves a working, verifiable artifact. Phases 1–6 are the first edition's program with their current status; Phases 7–9 are the current-vision additions built on the Mind program's ledger. Status tags: [planned], [in flight], [partially realized], [Speculative].

### Phase 1—Engine states into the training cache (the first seam) [planned]

- **Milestone:** `CassiCosmos/tools/engine_cache_writer.py` (a Python writer; zero sim edits): connects to the mind engine's TCP bridge (port 7599), steps the field, reads `readout` ey/ei at a cadence, projects each frame to 1024 (recorded decision: midplane slice at `grid_n = 32`), z-scores per run family, and writes `physics_cache_engine.pt` with exactly the `CassiAI/build_physics_cache.py` keys (`windows`, `family_ids`, `family_names`, `train_idx`, `val_idx`, `norm_stats`, `win_len`, `D`).
- **Proves:** the engine's field state is expressible in the format QiField already trains on. The loop's first seam closes with no changes to any existing system.
- **Risk:** the 3D→2D projection may discard the 3D structure the format cannot hold; the midplane slice is the least-lossy parsimonious choice, but the 32×32 frame is a different geometry than the engine's 64³ box. Mitigation: record the projection in the cache metadata and validate by training (Phase 2).

### Phase 2—Train the field-AI on engine states [planned; architecture settled by §28]

- **Milestone:** `CassiAI/experiments/train_qi_field_engine.py`: the existing `train_qi_field_physics.py` trainer pointed at `physics_cache_engine.pt` (continuous mode, `input_dim=1024`, N=4→1), plus a horizon-1 MAE report and a rollout sample.
- **Proves:** the engine field is learnable by the field-AI—the first accurate number for whether the substrate and the model speak the same language, and a baseline for the ε² signal (§2.4).
- **Risk and constraint:** small cache volume (a single mind-engine run is seconds of field time) and the q-convention mismatch (§2.4). **The architecture is no longer an open variable:** Stage 5 rejected the vanilla conv, Stage 5b adopted the cord architecture (4.78× on the increment metric). The engine trainer should start from the adopted architecture, not re-run the rejection. Validation is explicitly comparative: engine-cache MAE vs the turbulence-cache MAE, and the Stage-5b pre-registered board pattern (increment-relative metric, symplectic integrator, fresh pre-registration per refinement).

### Phase 3—The steering loop: read → predict → inject [planned; bounded by G34 and FP-4]

- **Milestone:** `CassiCosmos/tools/field_steer.py` (Python controller) or a `predict_apply` extension to `cassi_mind_engine.gd`: loop `readout` → model predicts the next frame → `deposit` the predicted delta (TSC scatter), with injection strength scaling and a cadence gate, plus the telemetry (`q_mean`, π saturation) as the guard read.
- **Proves:** field-as-AI I/O end to end—read = readout, write = deposit, steering = prediction applied as a gate. This is the minimal closed loop.
- **Risk:** the measured closed-loop instability (§5.1) is now twice-bounded. G34: per-step pointwise injection degrades the integrated attractor ~10×. G4c FP-4: at current twist strength the base field is a mixing clock — a steering loop that fires every step is injecting into noise. The loop must start with the theory's gate discipline: strength ramp from 0, **φ-cadence injection (the qi_time operator's τ_k = round(φ^k)) as the temporal regularization G34's remedies demand**, and a hard stop on divergence (the closure workstream's NaN-loud-fail convention). The closure × qi-time fusion (Phase 4) is the same discipline applied to the learned term.

### Phase 4—The sub-grid closure into the cell solver, under φ-cadence (multi-scale coupling) [planned]

- **Milestone:** the `C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` deliverable 1d: a scratch-layer term in `CassiCosmos/compute/cassi_voronoi_cells.glsl` with a `closure_strength` push-constant default 0.0 (bit-for-bit no-op; the 30-arm battery must stay green), plus the trained per-cell MLP weights exported from `C:/Users/Carina/workspaces/physics/research/neural_closure/`; the closure trained on engine fine/coarse pairs (64³ fine, 32³ coarse) instead of the numpy prototype — and, second edition, **injection gated by the qi-time cadence** instead of every step (the G34 remedy made concrete; the FP-4 mixing-clock finding is the null the cadence arm must beat).
- **Proves:** the sim's multi-scale problem (coarse grids missing sub-grid rungs) is addressable by a learned term that is theory-consistent by construction—the operator it closes is the shader's own operator—and that regularized injection is the difference between the 10× degradation and a real gain.
- **Risk:** G34's ~10× degradation is the honest baseline; the cadence arm is pre-registered against it. The documented follow-ons remain in force: regularized forcing (cadence or spectrally-shaped injection), trajectory-level training signal, and a nonlocal sweep if the per-cell MLP stays negative. A negative result is a valid deliverable.

### Phase 5—The orchestration bridge: CassiCore reaches the field [partially realized; port in flight]

- **Milestone (first edition):** `@cassicore/field-bridge` (a new small package in CassiCore) or a seam tool in `CassiCore/packages/spine/`: an adapter between the mind-runtime channel (127.0.0.1:7273) and the mind-engine bridge (127.0.0.1:7599)—`field_state`, `field_readout`, `field_project`, `field_deposit` as mind tools, and `MnemicMemoryBackend` gaining a field-snapshot source (memory entries whose content is a `readout`).
- **Status (second edition):** **built and verified, pre-migration.** The Mind program delivered this phase: the mind-plugin + `MindClient` (7599 line-JSON, fail-fast, race-timeout discipline), the `StandardMindFieldEncoder` seam (null default = no-op), the field bridge (`readProjection(k)` → `ProjectionCell[]`, never throws, empty on engine-down), the projection plugin action + context hook, and the curation wiring (projection → HEALPix spatial index → salience bonus; 27/27 tests). The remaining work is mechanical: complete the port into the `@cassicore/*` layout — the bridge and encoder are already vendored under `packages/mind-runtime/src/vendor/core/intelligence/`, the gate composite under `packages/thalamus/`, the inter-field bridge under `packages/mnemic-field/src/self-model/` — and re-run the suites there (`field-bridge` 11/11, `field-encoder` 4/4, host-wired tests).
- **Proves:** the AI's orchestration surface (tools, sessions, memory) reaches the field substrate; the last missing bridge (§2.5) closes.
- **Risk:** two event loops and two protocols (HTTP JSON ↔ line-delimited TCP JSON); latency of full 262144-cell readouts over the loop; auth (the mind runtime's bearer token vs the mind engine's open loopback). The bridge is a thin adapter, not a new protocol — this held in practice: engine-down degrades to empty surfaces with bounded warnings, never crashes.

### Phase 6—Orchestration as field dynamics [Speculative; primitives now exist]

- **Milestone:** a qi-time-scheduled task loop: tasks encoded as deposits/gate-configurations in a shared field, sequenced by the field's own φ-cadence dynamics (`CassiCosmos/compute/cassi_qi_time.glsl` pattern), with MnemicField attractors as the long-term memory and QiPatternMemory as the online pattern layer.
- **Proves (if it works):** the thesis—one self-organizing field that contains AI I/O and manages orchestration.
- **Risk:** this is the vision, and it inherits every risk in §5 — plus the new one from the ledger: G4c FP-4 measured the base field as a rung-independent mixing clock at current twist strength. Phase 6 cannot claim φ-cadence scheduling until Phase 8's weak-twist probe either finds the regime where rung structure emerges or honestly closes the claim. It is deliberately late, now for a measured reason, not just prudence.

### Phase 7—The aliveness objective: train for irreducible Qi [Speculative — the ε² inversion]

- **Milestone:** a training objective that bounds rather than minimizes ε² = |ψ − P[ψ]|² — candidate forms: a soft interval on ε² (floor + ceiling with a slack penalty outside the band), Qi-budget conservation across the horizon, or a two-term loss (stability + irreducibility) pre-registered as an A/B against the Stage-5b adopted objective on the physics boards. First artifact: the pre-registration document (statistic, decision tree, stopping rule) plus the objective implementation behind a config flag.
- **Proves:** whether the theory's central axiom is trainable — whether a field model can be *kept alive* (Qi bounded away from zero) while remaining stable and useful, and whether alive models steer better than dead ones on the Phase-3 loop.
- **Risk:** no known formulation exists; the first result may be an honest negative (Stage 5's REJECT is the precedent for how this program handles that). The failure modes are pre-identified: an ε² floor can reward noise (divergence), and the interval width is a new hyperparameter with its own look-elsewhere cost. Both go into the pre-registration. The theory's own words bound the ambition: "the formalism requires irreducible Qi" — Phase 7 is the attempt to turn that requirement from a comment into a loss.

### Phase 8—The φ-cascade telescope: M1/M2 × scale-telescoping [Speculative; one named experiment first]

- **Milestone (first):** the weak-twist probe — the pre-registration named by Wave-2: reduce the qi-time twist strength so that two-fluid competition (not the operator) sets T_rel, then re-run the telescoping FP-4 with the derived φ² arm. The n=2 cell's T_rel = 5 is the target signal. Decision tree pre-stated: rung-structured T_rel in the weak regime → the φ² ladder is measurable and M1/M2 temporal coupling proceeds; mixing clock persists at all strengths → honest HOLD, and the ladder claim is closed for this operator.
- **Milestone (second):** the telescope proper — M1's φ-zoom parent→child chain and M2's 49-level cascade tree coupled to `cassi_qi_time_exp.glsl` cadence per rung: out-of-band scales simulated on their own clocks, in-band scales on the camera's.
- **Proves:** whether one box can hold all 193 physical rungs — spatial zoom (M1/M2) for what's outside the window, temporal telescoping for what's outside the timestep.
- **Risk:** FP-4 already measured mixing-clock dominance at current strength; the weak regime may instead drown the gate signal (G4's null, z = −0.959, is the floor the probe must clear). Both branches are pre-registered outcomes, not failures.

### Phase 9—The field as memory: kindling and the dreaming galaxy [Speculative; gated on §19/§34]

- **Milestone:** the engram galaxy — CassiCore's MnemicField attractors rendered live in the sim: attractors as glowing clusters fed by the projection stream (readProjection(8) → HEALPix lookup), kindling as light-front propagation across the field, consolidation as star evolution, and the dead-wired DreamEngine re-energized as idle attractor drift (dream-phase `similar_to`/`cross_modal` synapse formation, the §31-3 design). Stretch artifact: Movie Maker recordings of idle relaxation — the dream archive — with the cascade-sonification mapping as the listening instrument.
- **Proves:** memory as a navigable universe; whether dream-phase relaxation discovers connections retrieval misses — the pre-registered dream-phase recall A/B.
- **Risk:** the value of the whole phase is downstream of the curation adoption gate (§34: §19 z > 2 in ≥2/3 sessions). Until the harness says field structure tracks retrieval structure, the galaxy is a visualization of an unproven mechanism, not of the field-as-memory claim. The build order respects this: the galaxy is cheap (existing instancer, existing streams); the dream A/B waits for the §19 data.

## 5. Risks and explicit caveats

1. **The closed-loop stability problem is already measured, and it is negative.** The only existing field-AI closed loop—the neural closure (`C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` §7)—improved the energy spectrum but degraded the integrated attractor and δ_rms by ~10× when its learned forcing was injected every step. This is the empirical warning for every phase that injects learned output into the field. The known failure mode (per-step pointwise forcing without temporal/structural regularization) and the documented remedies (regularized injection, trajectory-level loss, nonlocal architecture) are the design constraints for Phases 3–4, now concretized as cadence-gated injection (§4, Phase 4).
2. **Qi is self-surprise, and the training objective contradicts it.** The AI's next-frame loss minimizes the self-prediction gap that the theory defines as Qi; `physics_field_model.py` already records that "training to minimize self-prediction kills the system's dynamics." A field-AI that learns to predict the field perfectly is, by the theory's own axiom, dead. The unification needs a training objective that keeps ε² as the target signal rather than minimizing it away—this is the central design tension. The second edition adds the measurement that makes it actionable: Stage 5 REJECT (the error-minimizer lost to doing nothing) and Stage 5b ADOPT (the steering-style increment metric won). Phase 7 is the program's attempt at the objective itself.
3. **Two ε conventions and two q conventions.** Theory/sim ε = EY − φEI (disequilibrium) vs AI ε = ψ − P[ψ] (self-prediction error); theory/sim q = coherence density vs AI Q = surprise field. Unifying them (anchoring P[ψ] to the φ-attractor dynamics) is a research question, not an implementation detail.
4. **Geometry and scale mismatch.** The cache frames are 2D 32×32 (1024) flattened grids; the engine field is 3D 64³. The resolved-rung depth of the 64³ grid is about `n_max = ceil(64/3) − 1 = 20` modes per axis, `R = log_φ(20) ≈ 5.9` rungs—while the M2 cascade tree spans 193 physical rungs (proton n=95 → supercluster n=288, per `CassiCosmos/research/cascade_machine/m2_design.md` D-M2-1) and the theory's ladder is 292 steps. The multi-scale reach of a single fixed grid is the hard limit the φ-zoom machine (M1/M2), the closure, and the telescope (Phase 8) are separately attacking; the ML side has not touched it.
5. **Four repos, three languages, one data format.** TypeScript (CassiCore), Python (AI, theory, closure), GDScript/GLSL (sim). The only cross-language data contracts today are the torch `.pt` cache (Python-only) and the loopback bridges (7599 TCP, 7273 HTTP). There is no shared build system (by design); each phase's verification is the repo's documentary standard—a script that runs and prints its gate numbers.
6. **The training/structure-formation question is real and untouched by the ML.** The sim forms structure (condensation, merge, M1/M2 cascade trees) on the GPU and in numpy; QiField predicts next frames of static turbulence. Nothing connects structure formation to learning. The theory's demand is that any learned structure respects the φ-attractor, the wake geometry, and the gate vocabulary; the closure is theory-consistent by construction, QiField is not.
7. **The Mind program's artifacts are mid-migration, and its verdicts must travel with its code.** The bridge, encoder, gate composite, curation wiring, and the pre-registered harnesses exist and pass in the pre-migration tree (`D:/carina/workspaces/cassicore/`); the P2–P7 migration tables are porting them into the `@cassicore/*` layout. The risk is not loss—the verdicts are all on record in `research/mind/*`—but drift: a port that changes a constant (σ contract, bonus bounds, z thresholds) without re-running the suites silently invalidates the ledger. Port discipline: re-run the host-wired suites in the new layout before any new work builds on the ported code.
8. **The honest negatives are boundary conditions, not decorations.** Stage 3 NULL (no φ-log-periodicity in text), H1–H3 UNSUPPORTED (plain power law wins on the engram mass distribution), Stage 5 REJECT (vanilla predictor), G4 NULL (twist gate), G4c FP-4 branch "1" (mixing clock), Route-1/3 blocks and the φ¹ exclusion (time ladder). Each of these was a hypothesis someone wanted to be true; each failed pre-registered. New phases that re-hit them (a text objective, a vanilla predictor, a per-step injector, a φ¹ cadence) are re-paying measured costs. The second edition's program is built so each new phase is either orthogonal to a negative or pre-registered specifically to probe the one hint inside it (the n=2 cell, the weak-twist regime).

## References

- `CassiTheory/foundations/cassi-first-principles.md`—the two-fluid PDE and Qi definition
- `CassiTheory/foundations/dimensionful-cascade.md`—the φ-cascade ladder
- `CassiTheory/foundations/wu-xing-derivation.md`, `CassiTheory/foundations/wu-xing-cycle-structure.md`—the five-channel gate
- `CassiTheory/foundations/qi-flow-double-helix.md`—Qi as the phase current
- `CassiTheory/consciousness/consciousness-from-phi.md`—self-awareness as the Qi gate pinch
- `CassiTheory/consciousness/chakras-as-cascade-bubbles.md`—13 chakras as cascade bubbles
- `CassiTheory/consciousness/emotions-as-gate-configurations.md`—emotions as gate configurations
- `CassiTheory/two-fluid/cassi_two_fluid_3d_gpu.py`—the spectral two-fluid solver (`qi_gate` flag)
- `CassiTheory/EPISTEMIC-MAP.md`—the tier vocabulary this Plan sits under
- `CassiCore/package.json`—the 33-package workspace
- `CassiCore/MIGRATION-STATUS.md`—the P0–P8 migration record
- `CassiCore/packages/mind-runtime/src/channel/server.ts`—the 7273 loopback channel
- `CassiCore/packages/mnemic-field/src/`—the MnemicField memory system
- `CassiCore/packages/spine/`—the oh-my-pi extension
- `CassiAI/cassi/qi_field.py`—QiField
- `CassiAI/cassi/breath.py`—the dual-heart oscillator
- `CassiAI/cassi/physics_field_model.py`—PhysicsFieldModel + `load_physics_to_fluidcord`
- `CassiAI/cassi/multimodal_loader.py`—the cache loader
- `CassiAI/build_physics_cache.py`—the cache builder (format authority)
- `CassiAI/experiments/train_qi_field_physics.py`—the physics trainer
- `CassiAI/AGENTS.md`—the AI project's design philosophy
- `CassiCosmos/scripts/cassi_physics_engine.gd`—the standalone engine and its published state
- `CassiCosmos/scripts/cassi_sim.gd`—the sim orchestration (decoupled physics, mirrors)
- `CassiCosmos/scripts/cassi_mind_engine.gd`—the TCP loopback bridge (port 7599)
- `CassiCosmos/verify/README.md`—the 30-arm battery
- `CassiCosmos/cassi_contract.py`—the shared buffer/equation contract
- `CassiCosmos/compute/cassi_qi_time.glsl`—the φ-cadence multiscale gate
- `CassiCosmos/compute/cassi_qi_time_exp.glsl`—the telescope cadence-exponent operator
- `CassiCosmos/scripts/verify_qi_time.gd`, `CassiCosmos/scripts/verify_telescoping.gd`—the time-program batteries
- `CassiCosmos/research/machine/m1_design.md`—M1 φ-zoom chain
- `CassiCosmos/research/cascade_machine/m2_design.md`—M2 cascade tree
- `C:/Users/Carina/workspaces/physics/archive/nbody_shm_server.py`, `CassiCosmos/scripts/shm_sim.gd`—the shared-memory bridge
- `C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md`—the learned closure and its measured results
- `C:/Users/Carina/workspaces/physics/data/fields/*.pt`—the turbulence field sources for the cache

**Mind program (pre-migration paths; port in flight — migration tables P2–P7):**

- `D:/carina/workspaces/cassicore/.opencode/plans/cassi-mind-plugin.md`—the Mind program plan, §1–§34 (all pre-registrations, decision trees, and the verdict record)
- `D:/carina/workspaces/cassicore/mind-plugin/`—the plugin: `src/index.ts`, `src/mind-client.ts` (7599 client, fail-fast + race-timeout discipline)
- `D:/carina/workspaces/cassicore/research/mind/stage5b_terminal_report.md`—the field-as-model ADOPT record (4.78×, increment metric)
- `D:/carina/workspaces/cassicore/research/mind/stage5_report.md`—the Stage-5 REJECT record (predict-unchanged floor)
- `D:/carina/workspaces/cassicore/research/mind/stage3_structural_report.md`—the H1–H3 UNSUPPORTED measurement (361,045 engrams)
- `D:/carina/workspaces/cassicore/research/mind/stage3_wiring_report.md`—the tiered-consolidation wiring (23/23)
- `D:/carina/workspaces/cassicore/research/mind/qi_time_engine_report.md`—the qi-time G1–G4 battery (HOLD branch 2)
- `D:/carina/workspaces/cassicore/research/mind/scale_telescoping_design.md`—the telescope design and derivation-contract table
- `D:/carina/workspaces/cassicore/research/mind/telescoping_battery_report.md`—the Wave-2 FP-4 record (mixing clock, branch "1")
- `D:/carina/workspaces/cassicore/research/mind/overhaul_candidates_core.md`, `overhaul_candidates_packages.md`—the survey findings (dead-wired DreamEngine, trellis vindex)
- `D:/carina/workspaces/cassicore/research/mind/space_sim_recon_2026_08_14.md`—the sim recon (single kernel, lockstep, GPU-direct FieldQ)
- `CassiTheory/speculations/qi-as-time-clock.md`—the Qi-as-time clock (FP-1..3)
- `CassiTheory/speculations/qi-time-ladder-derivation.md`, `CassiTheory/speculations/referee_qi_time_ladder.py`—the mass–time equivalence derivation (exponent 2) and its referee
- `CassiCosmos/research/mind/stage0_verify.py`, `CassiCosmos/research/mind/lnphi_text_objective.py`—the sim-side Stage-0 and Stage-3 objective scripts
- `CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-bridge/`, `.../field-encoder/`—the ported field bridge and encoder
- `CassiCore/packages/thalamus/src/gate-composite.ts`—the ported gate composite
- `CassiCore/packages/mnemic-field/src/self-model/inter-field-bridge.ts`, `CassiCore/packages/mnemic-field/tests/host-wired/`—the ported inter-field bridge and its tests
