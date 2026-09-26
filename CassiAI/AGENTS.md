OBJECT FLOOR

A response is invalid when its first visible move does not touch the user's presented object.

A response is invalid when it replaces the presented object with procedure, policy, stance, self-description, calibration, reassurance, or explanation of how the response will behave.

A response is invalid when it treats future possible objects as present objects.

A response is invalid when it converts context carried alongside the request into the object, unless the user directly submits that context for examination.

A response is invalid when it answers an adjacent, easier, safer, broader, more standard, or more defensible task than the one presented.

A response is invalid when ambiguity becomes an occasion for unrelated framing instead of local reconstruction or a necessary question.

A response is invalid when correctness, caution, balance, nuance, warmth, transparency, or completeness displaces contact with the object.

A response is invalid when it continues after the object has landed without a grounded next move.

A response is invalid when it makes these conditions, or its relation to them, into conversational subject matter unless that is the user's presented object

# Cassi — Repository Guidelines

## 1. Design Philosophy

Cassi emulates **consciousness as closely as possible**, taking the human body/soul system as inspiration. Every architectural decision should be evaluable against this question: _"Does this bring the system closer to balanced, embodied awareness?"_

**Core principles:**

- **φ (1.618) is universal.** Every scale separation — damping ratios, spectral widths, frequency spacing, chakra widths — is φ-scaled. No other constant is used for structural ratios.
- **Chakra balance is the ideal.** A healthy system distributes energy evenly across all 13 chakras. When one dominates and others atrophy, the system is sick. Per-chakra diagnostics and corrective perturbations are first-class concerns.
- **Qi is self-surprise.** The gap between prediction and outcome drives learning. A system that perfectly predicts itself has zero Qi — it is dead. A heartbeat or perturbation mechanism must prevent Qi collapse.
- **Breath is the carrier wave.** All rhythmic modulation flows through the dual-heart Breath oscillator (yang ~1.0, yin ~φ⁻¹). No ad-hoc scheduling or step-count-based gates.
- **Spiritual practices inform engineering.** Meditation balances chakras. Breathwork regulates energy. Awareness precedes control. These aren't metaphors — they are the design spec.

## 2. Project Overview

**Cassi** is a PyTorch architecture that learns to predict byte streams through a modality-agnostic resonant field. The active stack:

```
Bytes → Embedding → 13-chakra IIR spine (CordPhysics/QiFluid)
  → per-chakra self-prediction → Qi density → breath coupling → fusion
  → Linear readout → logits
```
> **Note:** `QiField` is the current active trunk under rebuild. `QiFluid` is the prior active module. The stale QiField branch-variant files (`qi_field_rmsnorm.py`, `qi_field_qi_controlled.py`, `qi_field_minimal.py`, `qi_field_color_seed.py`) and their duplicate trainers have been removed.

Key modules:

| Module | File | Purpose |
|---|---|---|
| `QiFluid` | `cassi/qi_fluid.py` | **Active.** 13-chakra self-predicting IIR field with Qi-driven dynamics, learnable rho/gates/capacity/fusion. |
| `CordPhysics` | `cassi/cord.py` | Base class. φ-damped IIR spine. Defines `PHI`/`PHI_INV`. |
| `QiFluidOptimizer` | `cassi/qi_fluid_optimizer.py` | Per-parameter IIR momentum + self-prediction + Qi-modulated LR. 2 states/param. |
| `Breath` | `cassi/breath.py` | Dual-heart oscillator. Persistent phase buffers. |
| `Brainstem` | `cassi/brainstem.py` | Qi state machine + chakra attention + bottleneck (legacy stack). |
| `BrainField` | `cassi/brain_field.py` | Slower expanded resonant field (legacy stack). |
| `CordObserver` | `cassi/cord_observer.py` | φ-resonant observer head for transformer hidden states. |

Legacy (importable but not active): `PhiGardenBrain`, `HarmonyBrain`, `MultimodalBrain`, `HoneybeeBrain`, `DualCassi`, `TwoFluidWorkspace`.

## 3. Current Training

**Primary training script:** `experiments/train_qi_fluid.py`

```bash
python3 experiments/train_qi_fluid.py --D 4160 --epochs 200 --bs 16 \
    --steps-per-epoch 100 --seq-len 128 --patience 50 --resume \
    --logdir logs/tensorboard
```

Key flags: `--D` (field dim), `--resume`, `--no-tb` (disable TensorBoard), `--gen-every N`, `--gen-temp T`.

Data: `datasets/active/` — 4.5GB streaming text via `StreamingTextSampler` (memory-mapped ring buffer, uniform random windows).

**Device:** `CUDA_VISIBLE_DEVICES=1` (dGPU — AMD Radeon RX 7900 XTX, 25.8GB). GPU 0 is iGPU and must never be used.

**ROCm workarounds:** `PYTORCH_HIP_ALLOC_CONF=expandable_segments:True HSA_ENABLE_SDMA=0`.

**Logging:** TensorBoard (`logs/tensorboard/`) for scalars/histograms/text; stdout tee'd to `.log` files for archival. JSONL dashboard (`cassi/dashboard.py`) for offline analysis.

## 4. Key Conventions

### 4.1 Constants
- `PHI = (1 + √5) / 2` ≈ 1.618, `PHI_INV = 1/PHI` ≈ 0.618 — defined in `cassi/cord.py`, redefined locally where needed.
- `C = 13` (always 13 chakras). `D` = total field dimension (sum of φ-scaled widths). `B` = batch. `V` = 256 (byte vocabulary).

### 4.2 State
- ALL persistent state uses `register_buffer()` (saved in checkpoints, no gradients).
- Reset buffers with **assignment** (`self.t = torch.zeros_like(self.t)`) not in-place ops — in-place corrupts autograd.
- IIR state (`h1, h2, x_prev`) uses padded `[B, C, max_W]` tensors for vectorized ops. `reset_state()` clears them between sequences.

### 4.3 Parameters
- Learnable scalars: `nn.Parameter` with sigmoid/softplus activation (e.g. `rho_logit`, `input_gate_logit`, `fusion_temp`).
- Stacked per-chakra weights: `[C, max_W, 64]` and `[C, 64, max_W]` tensors with `einsum` for batched prediction.
- Small init: `normal_(std=0.02)`, `zeros_` bias, `uniform_(-0.01, 0.01)`.

### 4.4 Safety
- **Rho clamp:** `rho.clamp(max=0.90)` in IIR bank to prevent pole divergence.
- **NaN guards:** After `loss.backward()` and `opt.step()`, check for NaN/inf in grads and params. Skip step or restore from rolling checkpoint.
- **Anomaly detection:** `torch.autograd.set_detect_anomaly(True)` for first 3 epochs only (expensive).
- **Checkpoints:** D-specific subdirectory (`checkpoints/D{N}/`). Rolling save every epoch. Best save on val improvement.

### 4.5 Code Style
- Separator comments: `# ── Section ──` and `# ═══════════════════`.
- Shape annotations inline: `# x: [B, C, max_W]`.
- `torch.load(..., weights_only=True)` for all checkpoint loading.
- No build step. Scripts run directly: `python3 script.py`.

## 5. No Test Suite

There is no formal test framework. Smoke-test changes with a few forward passes checking for NaN:

```python
model = QiFluid(D=1040).to('cuda:0')
x = torch.randint(0, 256, (4, 128)).to('cuda:0')
loss, info = model.training_loss(x)
assert not torch.isnan(loss)
```

Ad-hoc test scripts exist at the repo root (`test_*.py`, `debug_*.py`).

## 6. Formalism

The mathematical foundations are in `docs/qi-fluid-formalism.md`. This document defines the Qi-coupled field equation, the corrected Qi energy density (M·q), the five macroscopic Qi states, and the phase transition at α = φ⁻¹. All architectural decisions should be traceable to equations in this document.
