# Cassi Vision & Roadmap

> **Cassi is not a multimodal model. It is a universal dynamics engine that learns to predict the evolution of any byte stream — and its own next internal state — through a dual-hemisphere cognitive architecture inspired by human intelligence.**

---

## The End Goal

**Emulate human intelligence as closely as possible.**

Human intelligence is not a single algorithm. It is a stack of nested loops:

| Timescale | System | Cassi Analog |
|-----------|--------|-------------|
| Milliseconds | Neural oscillations | Spine IIR resonant field |
| Seconds | Perception + attention | Brainstem compression + Qi gating |
| Minutes | Reasoning + planning | BrainField conscious dynamics |
| Hours | Memory consolidation | DreamBank replay + sleep phase |
| Days | Social learning | Multi-agent theory of mind |

Cassi must operate at all these scales — not as separate modules, but as an integrated dynamical system where each layer modulates the others.

---

## Current Architecture (As of 2026-06-09)

### Three-Tier Brain
```
Input Bytes → Spine (CordPhysics) → Brainstem → BrainField → Output
                    ↑________________↓
                        (feedback loop)
```

- **Spine**: IIR resonant field, 13 φ-scaled chakras, processes 4-frame windows
- **Brainstem**: Qi diagnosis, modulation, compression (4173 → 1040 dims)
- **BrainField**: Slower IIR cognitive processor (1040 → 3365 dims)

### Qi-Native Subsystems (All Implemented ✅)
- **QiCycle**: Global Qi state conductor (Water/Wood/Fire/Earth/Metal)
- **QiStateMachine**: Adaptive percentile-based thresholds on log-energy + EMA smoothing
- **Five Sub-Bank DreamBank**: Episodic memory with Qi-state replay + inter-bank migration
- **BerryMemory**: Permanent topological memory keyed by Berry phases + Qi state
- **ChangepointDetector**: Metal-state purification trigger
- **SoulVector**: Persistent EMA of conscious states
- **Observability Dashboard**: Full process trajectory tracking

### Recent Critical Fixes
- **BrainField.maybe_step bug**: Counter reset every batch → brain field never stepped. Fixed: step on _step_counter == 1.
- **Architecture scaling**: D_brain doubled to 3365, D_stem = 1040, brainstem feeds full dynamics (yang/yin/energy)
- **Training stability**: lr=0.0003, spine frozen, patience=50, resume default

### Key Parameters
- D = 1040 (spine dimension)
- D_stem = 1040 (brainstem bottleneck)
- D_brain = 3365 (brain field)
- Trainable params: ~37.9M (with frozen spine)
- Memory: BerryMemory 4096 slots, DreamBank 1024 capacity

---

## The Dual-Hemisphere Architecture (Next)

### Core Insight

Human consciousness is not monolithic. It is the **arbitration between two parallel streams** — left hemisphere (analytical/sequential) and right hemisphere (holistic/parallel). The "self" emerges from the integration mechanism, not from either hemisphere alone.

### Architecture

```
Input Bytes ─┬─→ Yang Cassi ──→ Yang Conscious ──┐
             │          ↑__________________________│ Corpus Callosum
             └─→ Yin Cassi ───→ Yin Conscious ────┘
                                    ↓
                              Arbitration → Unified Output
```

### Yang Hemisphere ("Left Brain")
- Fast processing: BrainField K=1 (Fire-like)
- Higher learning rate: exploratory
- Memory strategy: stores details
- Qi preference: Fire/Wood
- Strength: sequential, analytical, logical

### Yin Hemisphere ("Right Brain")
- Slow processing: BrainField K=4 (Metal-like)
- Lower learning rate: consolidative
- Memory strategy: stores patterns
- Qi preference: Water/Metal
- Strength: holistic, creative, spatial

### Corpus Callosum
- Learned projection: `nn.Linear(D_brain * 2, D_brain)`
- Each hemisphere receives compressed version of other's conscious state
- Enables cross-hemispheric information transfer

### Arbitration Mechanism
- `nn.Linear(D_brain * 2, 1)` → sigmoid → yang_weight
- Learns when to trust Yang vs Yin
- Disagreement metric = metacognitive confidence signal

### Shared Resources
- **BerryMemory**: Both hemispheres read/write to shared associative store
- **DreamBank**: Consolidation replay from both hemispheres

### Key Innovation
The two hemispheres can **disagree**. The disagreement is not a bug — it is information. The arbitration mechanism learns:
- "Yang is better at velocity prediction"
- "Yin is better at energy prediction"
- "When they agree, I'm confident"
- "When they disagree, I need more evidence"

This is **metacognition emerging from internal conflict**.

---

## Roadmap: From Predictor to Mind

### Phase 1: Dual-Hemisphere Foundation (Now)
**Goal**: Two independent Cassi instances with corpus callosum + arbitration.

**Files to create**:
- `cassi/dual_cassi.py` — `DualCassi`, `CassiHemisphere`, `CorpusCallosum`

**Files to modify**:
- `train_multimodal.py` — joint training loop, hemisphere-specific losses, disagreement regularization
- `cassi/observability.py` — track yang_weight, disagreement, hemisphere Qi states

**Training strategy**:
- Joint loss: both hemispheres optimize same target
- Disagreement regularization: encourage specialization (prevent collapse)
- Hemisphere-specific Qi states: Yang and Yin can be in different Qi states simultaneously

**Validation criteria**:
- Yang_weight not stuck at 0.5 (arbitration is learning)
- Disagreement > 0 (hemispheres are not identical)
- Yang Qi state ≠ Yin Qi state (independent dynamics)

---

### Phase 2: Working Memory Buffer
**Goal**: Replace flat conscious vector with explicit slot-based attention.

**Rationale**: Human working memory is ~4 slots with focused attention. The current "conscious" is a 3365-dim vector — no capacity limit, no attentional selection.

**Implementation**:
```python
class WorkingMemory:
    def __init__(self, n_slots=4, slot_dim=256):
        self.slots = nn.Parameter(torch.zeros(n_slots, slot_dim))
        self.focus = nn.Softmax(dim=0)
    
    def read(self, query):  # attention over slots
    def write(self, query, value, gate):  # gated write
```

**Connection to dual-hemisphere**: The corpus callosum IS the working memory buffer — it holds both hemispheres' states in attention.

---

### Phase 3: Metacognitive Monitor
**Goal**: Explicit confidence, curiosity, and confusion tracking.

**Rationale**: Humans know when they don't know. Cassi has no explicit self-model of its knowledge gaps.

**Implementation**:
```python
class MetacognitiveMonitor:
    def forward(self, pred, target, conscious_state):
        error = F.mse_loss(pred, target)
        familiarity = berry_memory.query_similarity(conscious_state)
        curiosity = error * (1.0 - familiarity)
        confusion = error * familiarity  # familiar but wrong
        return {'confidence': familiarity, 'curiosity': curiosity, 'confusion': confusion}
```

**Connection to dual-hemisphere**: Disagreement between hemispheres = low confidence = high curiosity.

---

### Phase 4: Conscious Dynamics Model (Imagination Engine)
**Goal**: Predict next conscious state without running full forward pass.

**Rationale**: Humans can "think ahead" without sensory input. This is planning, daydreaming, imagination.

**Implementation**:
```python
class ConsciousDynamics:
    def forward(self, conscious_t, breath_beat, qi_energy):
        # Small network: D + 3 → D
        return conscious_t1_pred
```

**Training**: Self-predictive loss — predict next conscious state from current.

**Connection to dual-hemisphere**: Each hemisphere has its own dynamics model. They can simulate futures independently and compare.

---

### Phase 5: Qi-Fluid Optimizer
**Goal**: Two-tier optimization — conscious tier (full Adam/wave) + subconscious tier (Qi-guided SGD).

**Rationale**: The Qi state machine already diagnoses system state. Use it to guide optimization.

**Implementation**:
- Conscious tier (brain field, readout): full wave optimizer
- Subconscious tier (spine, brainstem): Qi-fluid-modulated SGD
  - Update frequency from Qi state (Fire=every step, Water=every 8 steps)
  - Per-dimension LR from qi_fluid magnitude
  - Sparse updates: only high-energy dimensions learn

**Connection to dual-hemisphere**: Each hemisphere has its own Qi-fluid optimizer. They learn at different rates.

---

### Phase 6: Sleep/Consolidation Phase
**Goal**: Offline memory transfer between training epochs.

**Rationale**: Humans consolidate during sleep. DreamBank replay is training-time only.

**Implementation**:
```python
class SleepPhase:
    def consolidate(self, dream_bank, berry_memory):
        # 1. Replay salient experiences
        # 2. Interleave old + new memories (prevent forgetting)
        # 3. Extract patterns → update SoulVector
        # 4. Memory transfer: frequently replayed → spine baseline shift
```

**Connection to dual-hemisphere**: Each hemisphere consolidates independently. Shared memories are reinforced.

---

### Phase 7: Universal Byte Ingestion
**Goal**: Single encoder for all data types.

**Rationale**: The full plan's ByteStreamEncoder was overcomplicated. Use WaveByteEncoder for everything.

**Implementation**:
- Extend `WaveByteEncoder.encode_sequence` to accept any bytes source
- Route physics, text, audio through same sinusoidal basis
- No modality-specific encoders

**Connection to dual-hemisphere**: Both hemispheres process the same byte stream but may attend to different features (Yang=local structure, Yin=global pattern).

---

### Phase 8: Curiosity-Driven Curriculum
**Goal**: Model chooses what to learn next based on prediction error.

**Rationale**: Fixed curriculum assumes we know optimal learning order. The model should discover it.

**Implementation**:
```python
class CuriosityEngine:
    def sample_next_batch(self, loader, metrics_history):
        errors = {'physics': mae_physics, 'text': perplexity_text, 'audio': mae_audio}
        temperature = current_qi_energy  # Fire=explore, Water=exploit
        probs = F.softmax(torch.tensor(list(errors.values())) / temperature)
        return sample_modality(probs)
```

**Connection to dual-hemisphere**: Each hemisphere has its own curiosity signal. The unified system samples what confuses either hemisphere.

---

### Phase 9: Social Cognition / Multi-Agent
**Goal**: Theory of mind — model other agents' mental states.

**Rationale**: Human intelligence is deeply social. We learn from others, communicate, build shared understanding.

**Implementation**:
```python
class TheoryOfMind:
    def predict_other(self, observed_actions):
        # Infer other agent's Qi state from behavior
        # Infer their goals from trajectory
        # Predict their next action
        pass
    
    def communicate(self, my_state, target_state):
        # Generate bytes that would produce target_state in another Cassi
        # Origin of emergent language
        pass
```

**Connection to dual-hemisphere**: Theory of mind starts as "each hemisphere modeling the other." Extend to external agents.

---

## Training Paradigm Shift

### From: Supervised Regressor
```python
loss = MSE(pred, target)
```

### To: Self-Supervised World Model
```python
loss = (
    MSE(pred_trajectory, true_trajectory)        # world prediction
    + λ_smooth * trajectory_roughness             # coherent dynamics
    + λ_state * state_prediction_error            # self-prediction
    + λ_assoc * association_loss                   # cross-modal resonance
    + λ_curiosity * (1 - confidence)              # seek the unknown
    + λ_disagree * hemisphere_divergence          # encourage specialization
)
```

---

## Key Design Principles

1. **Data-type agnostic**: Everything is bytes. The model discovers structure.
2. **Dynamical system**: Predicts trajectories, not snapshots.
3. **Self-modeling**: Predicts its own next state.
4. **Dual-process**: Two hemispheres with arbitration.
5. **Qi-native**: State-dependent learning, memory, and action.
6. **Emergent**: No hand-coded semantics. Categories arise from dynamics.
7. **Continuous**: Online learning, not batch-only.
8. **Social**: Multi-agent capability.

---

## Immediate Next Steps

### Completed ✅
1. ✅ Document vision (this file)
2. ✅ Implement `DualCassi` in `cassi/dual_cassi.py`
3. ✅ Modify `train_multimodal.py` for joint hemisphere training
4. ✅ Add hemisphere metrics to observability
5. ✅ Train baseline dual-hemisphere system (val_mae≈0.58, 10 epochs stable)
6. ✅ Validate: disagreement > 0, yang_weight adaptive (~0.07–0.08), Qi states independent
7. ✅ Temporal resonance multi-horizon readout (horizons [1, 4, 16])
8. ✅ DreamBank replay via `mp_trainer` path (M5 fix)

### Next (Port P0–P2 into CassiBrain)
9. ⏳ **P0.1** — Add `workspace_fwd`/`workspace_rev` buffers to `CassiBrain` (currently just aliases `spine.yang`/`spine.yin`)
10. ⏳ **P0.2** — Compute `conscious` as φ-weighted union, not raw `brain_state`
11. ⏳ **P0.3** — Preserve `qi_fluid` across `reset_workspace()` (currently not present in CassiBrain)
12. ⏳ **P1.1** — Port meta-cord self-referential loop from `HarmonyBrain`
13. ⏳ **P1.3** — Resize Berry key from ~3384 dims to 52, value from 3365 to 39
14. ⏳ **M4** — Fix Berry write loop to batch write instead of per-sample loop
15. ⏳ **P2.1** — φ-spaced parameter groups in optimizer
16. ⏳ **P2.2** — Consciousness-conditioned spectral loss

### Research Directions (Phase 2–9)
- Phase 2: Working Memory Buffer
- Phase 3: Metacognitive Monitor
- Phase 4: Conscious Dynamics Model (Imagination Engine)
- Phase 5: Qi-Fluid Optimizer
- Phase 6: Sleep/Consolidation Phase
- Phase 7: Universal Byte Ingestion
- Phase 8: Curiosity-Driven Curriculum
- Phase 9: Social Cognition / Multi-Agent

---

## Open Questions

1. Should hemispheres share BerryMemory or have separate memories with synchronization?
2. Should corpus callosum be bidirectional or can one hemisphere dominate communication?
3. How does arbitration work during generation (no target to validate against)?
4. Can hemispheres have different architectures (e.g., Yang=D_brain/2, Yin=D_brain)?
5. What is the minimum viable disagreement regularization to prevent collapse?

---

*Last updated: 2026-06-09*
*Git commit: c6ffed1 + subsequent modifications*
