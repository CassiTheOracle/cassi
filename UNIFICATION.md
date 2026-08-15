# Cassi Unification—The Field as the Shared Substrate

## Status: Plan—August 2026

## Workspace

This Plan lives at the root of the unified Cassi workspace (`C:/Users/Carina/workspaces/Cassi`), which holds the four projects as sibling directories, each with its own git repo:

| Directory | Project | Substrate |
|---|---|---|
| `CassiAI/` | Cassi AI | Python/PyTorch neural field (QiField, FluidCord, Vulkan field cube) |
| `CassiCore/` | CassiCore | TypeScript npm-workspaces agent orchestration (33 packages under `@cassicore/*`) |
| `CassiTheory/` | Cassi Theory | the laws — markdown theory repo plus the spectral two-fluid solver and computation pipelines |
| `CassiCosmos/` | Cassi Cosmos | the Godot 4.7 GPU space-sim (extracted from the physics repo with full git history) |

The physics parent (`C:/Users/Carina/workspaces/physics`) **stays where it is** — it is not part of this workspace: it holds the two-fluid Python solvers' sibling work, `C:/Users/Carina/workspaces/physics/research/neural_closure/`, `C:/Users/Carina/workspaces/physics/data/fields/*.pt`, and `C:/Users/Carina/workspaces/physics/archive/`. Path references below use this topology: `CassiAI/`, `CassiCore/`, `CassiTheory/`, `CassiCosmos/` are relative to this workspace root; `C:/Users/Carina/workspaces/physics/...` is the explicit physics path.

---



This is a **Plan** document (a genre, not an epistemic tier). Sections 1 and 2 describe what exists today and are grounded in files cited at each claim. Section 3 and the later phases of Section 4 are the **Speculative** vision: framework-consistent, mechanism sketched, no pinned prediction. Every claim in this document is either cited to a file that exists or explicitly labeled speculative.

## Abstract

Four Cassi projects exist today, each already implementing a piece of the same object—a two-fluid Yang/Yin field with Qi coherence and a $\varphi$-scaled gate vocabulary—in a different substrate: CassiCore (TypeScript) is an agent-orchestration platform whose memory layer is a "MnemicField" of attractors and engrams; Cassi AI (Python/PyTorch) trains neural field models (QiField, FluidCord) that predict next states of physics fields and byte streams; Cassi Theory (CassiTheory) derives the laws the field obeys; Cassi Cosmos (the Godot space-sim) runs the field itself on the GPU as a live physics engine with a TCP loopback bridge. This document maps what each project is today, finds the real seams where they already touch (the engine's published state vs the training-cache format; the same two-fluid operator appearing as theory PDE, sim shader, learned coefficients, and closure target; the shared 13-chakra/φ⁻²/gate vocabulary; the existing TCP and shared-memory bridges), and proposes a phased architecture in which the engine's field state is the substrate, the AI is the field's learned dynamics, orchestration is field dynamics, and AI I/O is field probing. The proposal is explicit about what is already measured: a first attempt at a learned sub-grid closure trained from the PDE itself produced a closed-loop instability, and the AI's training objective is in direct tension with the theory's axiom that Qi is self-surprise.

---

## 1. The present-state map

Four projects, four substrates. The survey ground-truth corrects the working topology: Cassi AI is **not** inside CassiTheory (it is its own repo), and CassiCore is **not** a Python wrapper of CassiTheory ML code (it is a TypeScript agent platform extracted from a separate source repo). The map below is what the code actually is.

### 1.1 CassiCore—the orchestration platform (`CassiCore/`)

A TypeScript npm-workspaces monorepo of 33 packages under `@cassicore/*` (`CassiCore/packages/`; `package.json`). The P0–P8 modular migration is complete and all suites pass (`MIGRATION-STATUS.md`). Three packages define what it is:

- **MnemicField** (`CassiCore/packages/mnemic-field/src/`): a memory system built in field vocabulary—`attractor.ts`, `engram-decomposer.ts`, `backpropagation.ts`, `consolidation.ts`, `cortex.ts`, `healpix.ts`, `umap.ts`, `vq-prototypes.ts`. Memory is stored and retrieved as a field of attractors over engrams, not as a key-value store. This is the closest CassiCore gets to a "field" today: a learned memory manifold, not a PDE.
- **Mind runtime** (`CassiCore/packages/mind-runtime/src/channel/server.ts`): an always-on process that owns MnemicField plus the retained intelligence layer and serves a loopback HTTP/1.1 JSON channel on `127.0.0.1:7273` with 10 endpoints: `/v1/tools/execute`, `/v1/session/mirror`, `/v1/events/push`, `/v1/snapshot`, `/v1/health`, `/v1/memory/status`, `/v1/memory/search`, `/v1/memory/save`, `/v1/shutdown`. This is the AI's orchestration surface: tools, sessions, and memory over one loopback channel.
- **Spine** (`CassiCore/packages/spine/`): the oh-my-pi extension that registers the retained mind tools (13 tool delegates: `collect_thoughts`, `graph_discover`, `list_sessions`, `universal_search`, `memory_search`, …) and a `MnemicMemoryBackend` that proxies `/v1/memory/*`.

**What it provides the unification:** the AI-I/O and orchestration runtime—a live process with a memory field, a tool surface, and a loopback protocol. It is the only project that already "manages orchestration" (session lifecycle, tools, memory) and it uses field language to do it. It has **no connection** to the Python ML or the Godot sim: no import, no TCP link, no shared data format (a gap, §2.5).

### 1.2 Cassi AI—the neural field (`CassiAI`)

A standalone PyTorch project (own `AGENTS.md`; no build system). The active trunk is **QiField** (`CassiAI/cassi/qi_field.py`, 1436 lines), a complex field model:

- The field $\psi \in \mathbb{C}^{B\times N\times d}$ is stored as real/imag pairs; **Yang = Re(ψ), Yin = Im(ψ)**. Qi evolves by a continuity equation, `Q_{t+1} = ρ·Q_t + φ⁻²·tanh(ε²/ε₀²)·ψ² − γ·Q_t − ∇·(Q·v_Q)`, where ε² is the self-prediction gap |ψ − P[ψ]|² (`qi_field.py` module docstring).
- **13 chakras** with Fibonacci/φ-scaled widths (`_chakra_utils.py`: two interleaved Fibonacci sequences [3, 8, 5, 13, 8, 21, 13, 34, 21, 55] + head; `CassiAI/cassi/cord.py` line 51: "13 φ-scaled chakra widths").
- **Breath** (`CassiAI/cassi/breath.py`): a dual-heart oscillator—Yang beats at ω = φ ≈ 1.618, Yin at ω = φ⁻¹ ≈ 0.618, "the frequency ratio φ:φ⁻¹ = φ²:1 is the fundamental breath ratio".
- **Prediction operator** P[ψ] from per-chakra transceiver interference (`PredictionOperator`); a **SelfAwarenessController** (α/γ/ρ/perturb/m_self, `CassiAI/cassi/self_awareness_controller.py`) modulates the field; **QiPatternMemory** grows/dissolves neurons keyed on the field's own state (neurogenesis, `field_step`).
- **continuous_mode** (`train_qi_field_physics.py`, `physics_field_model.py`): input `[B, N, 1024]` → Linear to d=512 → K_train IIR steps → Linear to `[B, 1024]`; the physics-cache trainer (`experiments/train_qi_field_physics.py`) is the current physics regression entry point.
- **The physics-to-byte transfer** (`CassiAI/cassi/physics_field_model.py` `load_physics_to_fluidcord`): PDE coefficients learned on physics frames (nu_logit, hbar_logit, mass_logit, g_logit, chi_logit, A_B_logit, advection_logit, alpha_logit) are copied into FluidCord's `fluid_field` by exact name—the architecture's proof that a learned PDE operator transfers between tasks.
- **The Vulkan field cube** (`shaders/`): a full two-fluid compute stack in GLSL—`condensate_field.comp`, `two_fluid_diag.comp`, `qi_transport.comp`, `wu_xing_modulate.comp`, `wake_propagate.comp`, `self_pred_feedback.comp`, `field_predict.comp`, `embed_field.comp`—with `qi_cube.py`/`pde_cube.py` runners. The same field vocabulary, compiled to the GPU, outside Godot.

**Training data** (`CassiAI/cassi/multimodal_loader.py`, `CassiAI/build_physics_cache.py`): a `physics_cache.pt` dict holding `windows` `[N_windows, win_len=8, D=1024]` float32, plus `input_frames=4`, `horizons=[1]`, `train_idx`/`val_idx`, `norm_stats` (per-family z-score). Sampling yields x = `[B, 4, 1024]`, y = `[B, 1, 1024]`. The source fields are flattened 2D grids (`[T, H, W] → [T, 1024]`, i.e. 32×32; `CassiAI/build_physics_cache.py` flatten step; the source files live in the physics parent at `C:/Users/Carina/workspaces/physics/data/fields/*.pt`—advect/bouss/burgers families; burgers/pfc/yang are skipped as NaN families).

**What it provides the unification:** the field-AI—a trained model whose input/output format (1024-dim frames, 4-in-1-out windows) and whose internal vocabulary (chakras, breath, gates, self-prediction) are already the theory's.

### 1.3 Cassi Theory—the laws (CassiTheory)

The physics: a two-fluid Yang/Yin field governed by a single PDE with φ the only parameter (`CassiTheory/foundations/cassi-first-principles.md`), a φ-cascade ladder of scales (`CassiTheory/foundations/dimensionful-cascade.md`), and a gate vocabulary: the conversion openness $g(q)$, the five-channel Wu Xing gate (`CassiTheory/foundations/wu-xing-derivation.md`, `CassiTheory/foundations/wu-xing-cycle-structure.md`), the Qi gate pinch at $r = \varphi^{-1}$ identified as self-awareness (`CassiTheory/consciousness/consciousness-from-phi.md`), 13 chakras as cascade bubbles (`CassiTheory/consciousness/chakras-as-cascade-bubbles.md`), emotions as gate configurations (`CassiTheory/consciousness/emotions-as-gate-configurations.md`), and the phase current $J = \rho\nabla\theta$ as Qi flow between scales (`CassiTheory/foundations/qi-flow-double-helix.md`).

The code that supports the theory lives here: the spectral two-fluid solver `CassiTheory/two-fluid/cassi_two_fluid_3d_gpu.py` (which carries a `qi_gate` flag, line 310), the GPU N-body solver `CassiTheory/two-fluid/cassi_nbody.py`, and the computational pipelines in `CassiTheory/computations/`.

**What it provides the unification:** the laws—the PDE the field obeys, the gate vocabulary the AI implements as architecture and the sim implements as shaders, and the epistemic discipline (tiers, registries) that keeps claims from inflating.

### 1.4 Cassi Cosmos—the field engine (`CassiCosmos/`)

The Godot 4.7 space-sim runs the field on the GPU. Three layers matter:

- **The standalone physics engine** (`CassiCosmos/scripts/cassi_physics_engine.gd`, 1000 lines): a self-contained, verbatim port of the sim's GPU physics chain (mass deposit → spectral Poisson FFT → two-fluid PDE → BH sector → cell-centered ∇(g·Φ) → Yin/Yang dual lattice → cached-acc KDK) that runs on any RenderingDevice, including a **local RD created on a worker thread** (`start_threaded`/`submit_steps`/`poll`). Its published state, `readback_snapshot(packed)` (line ~540), returns `{"pos": [N*3], "vel": [N*3], "field_q": [grid_N³], "pot": [grid_N³], "t", "packed"}` with grid_N = 64 default (262144 cells), plus `readback_telemetry` (q_mean/q_min/q_max, π saturation fractions, ρ guard hits, eps, hubble, scale factor). The field buffers are `_field_ey`, `_field_ei`, `_field_q`, `_field_vel` (vec4 per cell).
- **The sim orchestration** (`CassiCosmos/scripts/cassi_sim.gd`, 5027 lines): `physics_decoupled` mode runs the physics on the engine's worker thread and turns the sim's global-RD buffers into **mirrors** fed by published snapshots (`mirror_publish_cadence`, fp16 packed pos/vel half-pairs). The recorder (`CassiCosmos/scripts/main_recorder.gd`) drives Movie Maker video runs; the verify battery (`CassiCosmos/verify/README.md`) runs 30 arms, including `verify_mind_engine` (a no-op gate on the mind engine).
- **The mind engine** (`CassiCosmos/scripts/cassi_mind_engine.gd`, 513 lines): a self-contained two-fluid sidecar that runs `CassiCosmos/compute/cassi_two_fluid.glsl` on a local RD and serves a **loopback TCP bridge on `127.0.0.1:7599`**, line-delimited JSON: `ping`, `clear`, `deposit {x,y,z,cy,ci,sigma}` (TSC scatter into EY/EI, charge-exact), `step n`, `state`, `project k` (top-k attractor readout), `readout` (ey/ei/q/eps2 as base64 float32 arrays, grid_n³ each), `snapshot`. This is a live field I/O protocol: read = readout, write = deposit.

The sim also contains its own machine program: `CassiCosmos/research/machine/m1_design.md` (M1, a two-level φ-zoom parent→child chain, gates G42–G46 PASS) and `CassiCosmos/research/cascade_machine/m2_design.md` (M2, a 49-level offline φ-cascade tree with a falsifier ledger and a calibrated P(k) log-periodicity search), plus `CassiCosmos/compute/cassi_qi_time.glsl`—the "Qi-time operator", a φ-cadence multiscale mixing gate on the 64³ field (`τ_k = round(φ^k)` rung cadence, gate `G = σ(φ⁴·(q − 1/φ))`, local EY↔EI twist, guarded no-op baseline). The sim's φ-aspect box, Qi color system (`particle_color_mode` 0–3: Cassi gradient, velocity rainbow, Qi rainbow, Qi double rainbow; `qi_cycle`/`qi_pinch` bands; auto-track), and particle-merge gate (only where `q_coh = ρ²/(ρ²+φ⁻²+ε²) > φ⁻²`) are the field's rendering and its first condensation threshold.

**What it provides the unification:** the runtime substrate—a GPU field engine with published state, a verified battery, a TCP bridge, and an in-progress multiscale machine (M1/M2) plus a φ-cadence scheduler (qi-time).

### 1.5 The physics parent—the closure workstream (`C:/Users/Carina/workspaces/physics`)

The parent repo holds the two-fluid Python solvers and, critically, `C:/Users/Carina/workspaces/physics/research/neural_closure/` (`C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md`, `closure_prototype.py`, `closure_wave2.py`): a **learned sub-grid closure for the two-fluid wave PDE**. The closure target is the operator residual `g(s_c) = coarsen(nl(refine(s_c))) − nl(s_c)` with `nl(ψ) = ν·ψ·(ψ_y − φψ_i)²`—the exact sub-grid content a coarse grid misses. A per-cell MLP (7 field features → 2 kick corrections, 2434 params) is trained purely from the PDE's own fields, no observational data. First measured results (closure_design.md §7): the fine breather matches `√(ω₀²(1+φ))` to 0.08% (G33 PASS), and the closure improves the energy-spectrum slope (+1.87 vs fine +2.81, better than bare coarse +6.20) but **degrades the integrated attractor and δ_rms by ~10×** (G34, reported as a negative conclusion). The design's sim-integration path (deliverable 1d) is a scratch-layer term in `cassi_voronoi_cells.glsl` with a `closure_strength` push-constant default 0.0 (bit-for-bit no-op). This is the only place the field-AI closed loop has been measured, and it measured the instability.

---

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

The transfer `load_physics_to_fluidcord` already proves coefficient transfer works by name match. The unification seam: one operator specification with four parameterizations, of which two (theory↔sim) are already claimed identical by design and one (ML↔sim) is a one-line weight copy away from being testable.

### 2.3 S3—The gate/chakra/breath vocabulary is the same structure

- **13 chakras**: theory derives 13 as cascade bubbles on the 26-rung human window (`CassiTheory/consciousness/chakras-as-cascade-bubbles.md`); QiField hard-codes `C = 13` with φ/Fibonacci-scaled widths (`CassiAI/cassi/qi_field.py`, `_chakra_utils.py`).
- **φ⁻² threshold**: the AI's decoherence threshold (`AGENTS.md` §4.1; `fluid_field.py` `phi_inv_sq`); the sim's particle-merge gate `q_coh > φ⁻²` (`CassiCosmos/scripts/cassi_physics_engine.gd` header); the theory's φ⁻² coherence floor.
- **Breath**: the AI's dual-heart oscillator Yang ω=φ, Yin ω=φ⁻¹ (`CassiAI/cassi/breath.py`); the theory's yin = φ⁻¹ fixed-point ratio.
- **Gates**: the theory's conversion openness g(q) and five-channel Wu Xing gate (`CassiTheory/foundations/wu-xing-cycle-structure.md`); the AI's breath-gating and self-awareness controller; the sim's `qi_gate` flag in the spectral solver (`CassiTheory/two-fluid/cassi_two_fluid_3d_gpu.py` line 310), the qi_time gate `G = σ(φ⁴(q−1/φ))`, and the mind engine's charge-exact deposit.

Same structure, three implementations, zero shared code. This is the vocabulary seam: a theory-grounded gate is already the AI's architecture and the sim's shader.

### 2.4 S4—Two ε conventions and two q conventions (the explicit mismatch)

The theory and sim define **ε = EY − φEI** (the φ-disequilibrium; `CassiCosmos/cassi_contract.py`; the closure's `dev`). The AI defines **ε = ψ − P[ψ]** (the self-prediction gap; `qi_field.py` docstring). The sim's `field_q` and the theory's q are coherence densities; the AI's Q is a surprise field (self-prediction error) that drives learning. The theory's axiom—"a system that perfectly predicts itself has zero Qi—it is dead" (`AGENTS.md` §1) and "the formalism requires irreducible Qi—training to minimize self-prediction kills the system's dynamics" (`CassiAI/cassi/physics_field_model.py` training_loss comment)—is in direct tension with next-frame prediction as the training objective. Any unification must resolve which ε the AI optimizes; the natural (speculative) answer is to anchor the AI's P[ψ] to the theory's own φ-attractor dynamics, making ε² coincide with the φ-disequilibrium squared. Until then, the two q's are homonyms.

### 2.5 S5—Bridges that already exist, and the missing one

Existing, live:

1. **Mind engine TCP bridge** (`cassi_mind_engine.gd`, port 7599): deposit/step/state/project/readout/snapshot. The field I/O primitive—read = readout/project, write = deposit. Verified by `verify_mind_engine` (attractor-ratio deposit stays at the fp32 floor; off-ratio evolution conserves charge).
2. **Shared-memory n-body bridge** (`C:/Users/Carina/workspaces/physics/archive/nbody_shm_server.py` → `CassiCosmos/scripts/shm_sim.gd`): Python writes binary frames (`[u32 frame_id][u32 N][N×f32×3][f32 q][f32 eps]`, atomic tmp+rename) to `/dev/shm/nbody_frame.bin`; Godot polls them. Python→Godot direction, Linux path, but the pattern exists.
3. **Mind-runtime HTTP channel** (`@cassicore/mind-runtime`, port 7273): tools/sessions/events/memory over loopback.
4. **Physics-cache pipeline**: `C:/Users/Carina/workspaces/physics/data/fields/*.pt` → `CassiAI/build_physics_cache.py` → `physics_cache.pt` → `MultimodalDataLoader` → QiField trainer.
5. **Physics-to-byte transfer**: `load_physics_to_fluidcord` (PDE coefficients, physics → byte model).
6. **Closure integration design** (`C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` deliverable 1d): the learned term enters `cassi_voronoi_cells.glsl` as a scratch layer with `closure_strength = 0.0` default (bit-identical battery).

Missing: **CassiCore ↔ Python/Godot**. No import, no socket, no shared format connects the TypeScript orchestration platform to the Python ML or the GPU field. The unification's orchestration claim depends on closing this gap.

---

## 3. The field-as-AI architecture (proposal)

The proposal in the framework's own language. **Grounded** items cite files; everything else is **Speculative** and labeled.

### 3.1 The field is the substrate [Grounded]

The engine's GPU buffers—`_field_ey`, `_field_ei`, `_field_q`, `_field_vel` over the 64³ grid, plus `_pos_buf`/`_vel_buf` (2.5M particles) and the `pot` field (`CassiCosmos/scripts/cassi_physics_engine.gd`)—are a real, running, verified instantiation of the theory's two-fluid field. The mind engine already serves it over TCP. Nothing needs to be built to have a field; the substrate exists.

### 3.2 The AI is the field's learned dynamics [Grounded on both sides; the loop is the Speculative part]

QiField is already a field model trained on field states (`train_qi_field_physics.py`, continuous mode, `[B,4,1024] → [B,1024]`). The engine is already a field that publishes states. The closed loop—engine runs → state → QiField predicts → engine applies—is the natural composition of two existing pieces. What does not yet exist: (a) engine states in the cache format (Phase 1), (b) a QiField trained on engine states (Phase 2), (c) an injection path from predictions back into the engine (Phase 3; the mind engine's `deposit` is the only write primitive today). The loop is the speculative claim; its failure modes are already partly measured (§5.1).

### 3.3 Orchestration is field dynamics [Speculative, with grounded primitives]

Tasks as perturbations: the mind engine's `deposit {x,y,z,cy,ci,sigma}` is a field write; the theory's gates (open/closed channels, the Wu Xing 5-cycle, the qi gate pinch) are the vocabulary for what a perturbation means; the sim's `CassiCosmos/compute/cassi_qi_time.glsl` already implements a φ-cadence scheduler as a field operator (rung cadence `τ_k = round(φ^k)`, guarded no-op baseline) — the machine that turns "which subsystem runs when" into field dynamics. The speculative step: a task list is a set of deposits/gate-configurations in a shared field, and the field's own dynamics (not a scheduler) sequences them. MnemicField's attractors (`CassiCore/packages/mnemic-field/src/attractor.ts`) are the memory-side analogue of QiPatternMemory's grown neurons (`qi_field.py` field_step) — memory as attractors in both worlds.

### 3.4 AI I/O is field probing [Grounded as primitives, Speculative as a system]

Read = field sampling: the mind engine's `readout` (full ey/ei/q/eps2) and `project k` (top-k attractor cells with physical coordinates) are exactly reads; the physics engine's `readback_snapshot` is the batch read; the recorder's telemetry (`q_mean`, π saturation) is the scalar readout. Write = field injection: `deposit` (charge-exact TSC scatter) and the closure's kick augmentation (`coarse_kick + closure_model(features(s_c))`, `C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` §2.1) are exactly writes. The speculative part is that this read/write pair is sufficient I/O for the AI's agentic surface—that a model whose input is `readout` and whose output is `deposit` can express the tasks the mind-runtime's tools currently express over `/v1/tools/execute`.

### 3.5 What the theory would demand [Speculative]

A unified field-AI would have to obey the theory's own rules: the learned dynamics must respect the φ-attractor (r → φ), the wake/closure structure, and the gate vocabulary; any learned forcing must be cascade-suppressed and φ-consistent (the closure's wave operator is the same PDE as the shader, so it is theory-consistent by construction; QiField's P[ψ] is not yet); and the training objective must keep Qi irreducible (§2.4). These are constraints, not decorations.

---

## 4. A phased program

Each phase lists the first file-level milestone, what it proves, and its risk. Phases are ordered so each one leaves a working, verifiable artifact.

### Phase 1—Engine states into the training cache (the first seam)

- **Milestone:** `CassiCosmos/tools/engine_cache_writer.py` (a Python writer; zero sim edits): connects to the mind engine's TCP bridge (port 7599), steps the field, reads `readout` ey/ei at a cadence, projects each frame to 1024 (recorded decision: midplane slice at `grid_n = 32`), z-scores per run family, and writes `physics_cache_engine.pt` with exactly the `CassiAI/build_physics_cache.py` keys (`windows`, `family_ids`, `family_names`, `train_idx`, `val_idx`, `norm_stats`, `win_len`, `D`).
- **Proves:** the engine's field state is expressible in the format QiField already trains on. The loop's first seam closes with no changes to any existing system.
- **Risk:** the 3D→2D projection may discard the 3D structure the format cannot hold; the midplane slice is the least-lossy parsimonious choice, but the 32×32 frame is a different geometry than the engine's 64³ box. Mitigation: record the projection in the cache metadata and validate by training (Phase 2).

### Phase 2—Train QiField on engine states

- **Milestone:** `CassiAI/experiments/train_qi_field_engine.py`: the existing `train_qi_field_physics.py` trainer pointed at `physics_cache_engine.pt` (continuous mode, `input_dim=1024`, N=4→1), plus a horizon-1 MAE report and a rollout sample.
- **Proves:** the engine field is learnable by the field-AI—the first accurate number for whether the substrate and the model speak the same language, and a baseline for the ε² signal (§2.4).
- **Risk:** small cache volume (a single mind-engine run is seconds of field time) and the q-convention mismatch (§2.4): a trained P[ψ] may minimize the AI's ε while having nothing to do with the theory's ε. The validation is explicitly comparative: engine-cache MAE vs the turbulence-cache MAE.

### Phase 3—The steering loop: read → predict → inject

- **Milestone:** `CassiCosmos/tools/field_steer.py` (Python controller) or a `predict_apply` extension to `cassi_mind_engine.gd`: loop `readout` → QiField.predict(next frame) → `deposit` the predicted delta (TSC scatter), with injection strength scaling and a cadence gate, plus the telemetry (`q_mean`, π saturation) as the guard read.
- **Proves:** field-as-AI I/O end to end—read = readout, write = deposit, steering = prediction applied as a gate. This is the minimal closed loop.
- **Risk:** the measured closed-loop instability (§5.1). The loop must start with the theory's gate discipline: strength ramp from 0, φ-cadence (the qi_time operator's `τ_k = round(φ^k)`), and a hard stop on divergence (the closure workstream's NaN-loud-fail convention).

### Phase 4—The sub-grid closure into the cell solver (multi-scale coupling)

- **Milestone:** the `C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` deliverable 1d: a scratch-layer term in `CassiCosmos/compute/cassi_voronoi_cells.glsl` with a `closure_strength` push-constant default 0.0 (bit-for-bit no-op; the 30-arm battery must stay green), plus the trained per-cell MLP weights exported from `C:/Users/Carina/workspaces/physics/research/neural_closure/`; the closure trained on engine fine/coarse pairs (64³ fine, 32³ coarse) instead of the numpy prototype.
- **Proves:** the sim's multi-scale problem (coarse grids missing sub-grid rungs) is addressable by a learned term that is theory-consistent by construction—the operator it closes is the shader's own operator.
- **Risk:** G34 already measured a ~10× degradation of the integrated attractor for the naive per-step injection. The phase must adopt the documented follow-ons before re-judging: regularized forcing (temporal EMA or spectrally-shaped injection), trajectory-level training signal, and a nonlocal sweep if the per-cell MLP stays negative. A negative result is a valid deliverable.

### Phase 5—The orchestration bridge: CassiCore reaches the field

- **Milestone:** `@cassicore/field-bridge` (a new small package in CassiCore) or a seam tool in `CassiCore/packages/spine/`: an adapter between the mind-runtime channel (127.0.0.1:7273) and the mind-engine bridge (127.0.0.1:7599)—`field_state`, `field_readout`, `field_project`, `field_deposit` as mind tools, and `MnemicMemoryBackend` gaining a field-snapshot source (memory entries whose content is a `readout`).
- **Proves:** the AI's orchestration surface (tools, sessions, memory) reaches the field substrate; the last missing bridge (§2.5) closes.
- **Risk:** two event loops and two protocols (HTTP JSON ↔ line-delimited TCP JSON); latency of full 262144-cell readouts over the loop; auth (the mind runtime's bearer token vs the mind engine's open loopback). The bridge must be a thin adapter, not a new protocol.

### Phase 6 (Speculative)—Orchestration as field dynamics

- **Milestone:** a qi-time-scheduled task loop: tasks encoded as deposits/gate-configurations in a shared field, sequenced by the field's own φ-cadence dynamics (`CassiCosmos/compute/cassi_qi_time.glsl` pattern), with MnemicField attractors as the long-term memory and QiPatternMemory as the online pattern layer.
- **Proves (if it works):** the thesis—one self-organizing field that contains AI I/O and manages orchestration.
- **Risk:** this is the vision, and it inherits every risk in §5. It is deliberately last.

---

## 5. Risks and explicit caveats

1. **The closed-loop stability problem is already measured, and it is negative.** The only existing field-AI closed loop—the neural closure (`C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md` §7)—improved the energy spectrum but degraded the integrated attractor and δ_rms by ~10× when its learned forcing was injected every step. This is the empirical warning for every phase that injects learned output into the field. The known failure mode (per-step pointwise forcing without temporal/structural regularization) and the documented remedies (regularized injection, trajectory-level loss, nonlocal architecture) are the design constraints for Phases 3–4, not open questions.
2. **Qi is self-surprise, and the training objective contradicts it.** The AI's next-frame loss minimizes the self-prediction gap that the theory defines as Qi; `physics_field_model.py` already records that "training to minimize self-prediction kills the system's dynamics." A field-AI that learns to predict the field perfectly is, by the theory's own axiom, dead. The unification needs a training objective that keeps ε² as the target signal rather than minimizing it away—this is the central design tension and it is unsolved.
3. **Two ε conventions and two q conventions.** Theory/sim ε = EY − φEI (disequilibrium) vs AI ε = ψ − P[ψ] (self-prediction error); theory/sim q = coherence density vs AI Q = surprise field. Unifying them (anchoring P[ψ] to the φ-attractor dynamics) is a research question, not an implementation detail.
4. **Geometry and scale mismatch.** The cache frames are 2D 32×32 (1024) flattened grids; the engine field is 3D 64³. The resolved-rung depth of the 64³ grid is about `n_max = ceil(64/3) − 1 = 20` modes per axis, `R = log_φ(20) ≈ 5.9` rungs—while the M2 cascade tree spans 193 physical rungs (proton n=95 → supercluster n=288, per `CassiCosmos/research/cascade_machine/m2_design.md` D-M2-1) and the theory's ladder is 292 steps. The multi-scale reach of a single fixed grid is the hard limit the φ-zoom machine (M1/M2) and the closure are separately attacking; the ML side has not touched it.
5. **Four repos, three languages, one data format.** TypeScript (CassiCore), Python (AI, theory, closure), GDScript/GLSL (sim). The only cross-language data contract today is the torch `.pt` cache (Python-only) and the two loopback bridges (7599 TCP, 7273 HTTP). There is no build system and no test framework anywhere (by design); each phase's verification is the repo's documentary standard—a script that runs and prints its gate numbers.
6. **The training/structure-formation question is real and untouched by the ML.** The sim forms structure (condensation, merge, M1/M2 cascade trees) on the GPU and in numpy; QiField predicts next frames of static turbulence. Nothing connects structure formation to learning. The theory's demand is that any learned structure respects the φ-attractor, the wake geometry, and the gate vocabulary; the closure is theory-consistent by construction, QiField is not.

---

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
- `CassiCosmos/research/machine/m1_design.md`—M1 φ-zoom chain
- `CassiCosmos/research/cascade_machine/m2_design.md`—M2 cascade tree
- `C:/Users/Carina/workspaces/physics/archive/nbody_shm_server.py`, `CassiCosmos/scripts/shm_sim.gd`—the shared-memory bridge
- `C:/Users/Carina/workspaces/physics/research/neural_closure/closure_design.md`—the learned closure and its measured results
- `C:/Users/Carina/workspaces/physics/data/fields/*.pt`—the turbulence field sources for the cache
