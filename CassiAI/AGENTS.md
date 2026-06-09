# AGENTS.md — Cassi Project Context

> This file is for AI coding agents. It assumes you know nothing about the project.
> All facts below were derived from the actual codebase. Do not generalize.

---

## 1. Project Overview

**Cassi** is a research codebase for a *universal dynamics engine* — a PyTorch neural architecture that learns to predict the evolution of any byte stream (physics fields, text, audio waveforms) through a modality-agnostic field representation.

The project is built around the **Cassi Principle**: the golden ratio φ ≈ 1.618 acts as a universal constant of scale separation in multi-scale coupled systems. Every architectural decision (damping ratios, spectral widths, frequency spacing, workspace mixing) is explicitly φ-scaled.

Key architectural motifs:
- **13 chakras** — φ-scaled spectral bands in the field representation.
- **Twin-Cord** — forward (Yang/expansive) and reverse (Yin/contractive) IIR filters.
- **Dual workspace** — `workspace_fwd` and `workspace_rev` whose difference forms conscious content.
- **Breath** — dual-heart oscillator with learnable Yang/Yin frequencies.
- **Berry Memory** — topological associative memory keyed by geometric Berry phases.
- **Qi-fluid** — resonant overlap between workspaces that modulates specialist attention.
- **HoneybeeBrain** — competitive sparse workspace (mushroom-body inspired) for larger-scale experiments.

This is a **single-researcher project** with no formal test suite, no CI/CD, and no package management files (no `pyproject.toml`, `setup.py`, or `requirements.txt`). Dependencies are imported directly.

---

## 2. Technology Stack

| Component | Version (observed) | Purpose |
|-----------|-------------------|---------|
| Python | 3.14.5 | Runtime |
| PyTorch | 2.12.0 | Deep learning framework |
| NumPy | 2.4.6 | Numerical arrays, RNG, sampling |
| matplotlib | (any) | Offline dashboard plotting |

**Device assumption:** Training scripts hardcode `DEV = 'cuda'` and expect a GPU. CPU-only training is not supported without editing the scripts.

**No package manager:** If you need to add a dependency, you must install it into the system/venv environment; there is no `requirements.txt` to update.

---

## 3. Project Structure

```
cassi/                        # Core Python package
    cord.py                   # CordPhysics — φ-damped IIR spine (13 chakras)
    phi_garden.py             # PhiGardenBrain — base brain with specialists, GWT, Berry memory
    harmony_brain.py          # HarmonyBrain — Qi-fluid, gating, sparse attention, Breath
    multimodal_brain.py       # MultimodalBrain — changepoint detector, soul vector, audio fusion
    honeybee_brain.py         # HoneybeeBrain — competitive sparse workspace (k-WTA)
    berry_brain.py            # BerryMemory — topological memory keyed by Berry phases
    breath.py                 # Breath — dual-heart Yin-Yang oscillator
    text_codec.py             # ByteEncoder, TextEncoder, TextDecoder, WaveByteEncoder
    audio_encoder.py          # AudioFieldEncoder — STFT→mel→field projection
    audio_utils.py            # Audio helper utilities
    multimodal_loader.py      # MultimodalDataLoader — curriculum-based sampling
    streaming_text_sampler.py # StreamingTextSampler — memory-mapped / ring-buffer text
    adaptive_trainer.py       # AdaptiveTrainer — curriculum + LR scheduling from model signals
    observability.py          # CassiMetrics — per-batch/epoch metrics collection
    dashboard.py              # Matplotlib dashboard from JSONL logs
    iir_optimizer.py          # ResonantIIR — φ-damped gradient filter optimizer

train.py                      # Unified trainer (physics / text / self-driven)
train_multimodal.py           # Multimodal trainer with curriculum phases 0–5
train_byte_decoder.py         # Byte decoder training script
fit_wave_encoder.py           # Wave encoder fitting script
profile_train.py              # Training profiler
debug_anomaly*.py             # Anomaly debug scripts (1–5)

experiments/
    experiment_harmony_gated.py
    experiment_sparse_extended.py
    generate_phi_garden_text.py

datasets/                     # Training data (not in git)
    active/                   # Text files ingested live
    physics_cache_v10.pt      # Pre-cached physics windows
    peoples_speech/           # Audio data
    tokens/                   # Tokenized text
    ...

checkpoints/                  # Saved model weights (.pt, .pt.best)
logs/                         # Training logs and metrics JSONL
    metrics/                  # Per-epoch JSONL metrics
    dashboard_epoch_*.png     # Generated dashboards
```

---

## 4. Key Architecture Concepts

### 4.1 CordPhysics (`cassi/cord.py`)
- Input: `[B, 4, 1024]` field history (4 timesteps).
- 13 chakras with widths scaled by `PHI^c` (normalized to sum `D=1040` or `D=16384`).
- Each chakra has a learned second-order IIR filter with damping `ρ = PHI_INV ≈ 0.618`.
- Frequencies initialized inversely φ-scaled: fast chakras → high freq, slow chakras → low freq.
- Output: prediction `[B, 1024]` or representation `[B, D]`.

### 4.2 PhiGardenBrain → HarmonyBrain → MultimodalBrain
Inheritance chain:
```
PhiGardenBrain (specialists + GWT + Berry memory)
    └── HarmonyBrain (+ Qi-fluid + gating + Breath + neuroplasticizer)
            └── MultimodalBrain (+ changepoint + soul + multimodal fusion)
```
- **Specialists:** 5 (or 13) slim copies of the Cord spine, each with frequency offsets.
- **GWT broadcast:** φ-temperature softmax competition decides which specialists enter the conscious workspace.
- **Berry Memory:** Fixed-size slot memory (`n_slots=4096` or `512`). Keys = 26-dim Berry phases. Retrieved via sparse top-k attention.
- **Qi-fluid:** Running overlap between `workspace_fwd` and `workspace_rev`. Modulates a harmony gate.
- **Breath:** Learnable dual oscillator (`omega_yang`, `omega_yin`). Phases persist across batches (buffer-based). Reset by neuroplasticizer pulse.
- **Neuroplasticizer:** Triggered when rigidity (low variance in harmony/Qi/surprise) exceeds 0.6. Resets breath phases, injects Yin shock, entropy surge.

### 4.3 HoneybeeBrain
- Separate branch, not a subclass of HarmonyBrain (subclasses `PhiGardenBrain` directly).
- Workspace is small (`W=256`) and sparse (`~10%` active via k-WTA).
- Each specialist projects into its own region of the workspace.
- Designed for larger `D` (up to 16384) with competitive sparse integration.

### 4.4 Data Flow
1. Raw bytes → modality-specific encoder → field `[B, 4, 1024]`.
2. Spine IIR → 13 chakra representations.
3. Specialists compete → GWT broadcast → conscious workspace.
4. Workspace + Berry memory + Qi → prediction `[B, 1024]`.
5. Loss = MSE(pred, target) + optional coherence + spectral-slope + φ-balance regularization.

---

## 5. Build and Training Commands

There is **no build step**. Run scripts directly with Python.

### 5.1 Physics-only training
```bash
python train.py --data physics --epochs 20
```

### 5.2 Text training
```bash
python train.py --data text --epochs 10 --steps-per-epoch 2000
```

### 5.3 Self-driven consistency training
```bash
python train.py --data physics --self-driven --consistency-weight 0.1
```

### 5.4 Adaptive LR + curriculum + mixed precision
```bash
python train.py --data text --adaptive --curriculum --mixed-precision
```

### 5.5 Multimodal curriculum training
```bash
# Phase 0: physics only
python train_multimodal.py --phase 0 --epochs 10

# Phase 3: speech + audio
python train_multimodal.py --phase 3 --epochs 10 --resume

# Full curriculum (phase 5)
python train_multimodal.py --phase 5 --epochs 20 --resume
```

Curriculum phases:
- `0`: physics_only
- `1`: physics_equations
- `2`: physics_descriptions
- `3`: speech_audio
- `4`: text_images (future)
- `5`: all_modalities

### 5.6 Generate dashboard from logs
```bash
python -m cassi.dashboard --log logs/metrics/epoch_metrics.jsonl --out dashboard.png
```

### 5.7 Common CLI flags
Both `train.py` and `train_multimodal.py` accept:
- `--bs BATCH_SIZE` (default varies)
- `--lr LR` (default ~2e-4)
- `--wd WEIGHT_DECAY` (default 0.01)
- `--epochs N`
- `--steps-per-epoch N`
- `--resume` (load from `SAVE_PATH`)
- `--mixed-precision`
- `--adaptive` (enable AdaptiveTrainer)
- `--curriculum` (prioritize high-surprise samples)

---

## 6. Data Organization

| Path | Content |
|------|---------|
| `datasets/active/` | Text files (`.txt`, `.json`, `.jsonl`, `.parquet`) loaded dynamically by `StreamingTextSampler` and `MultimodalDataLoader`. |
| `datasets/physics_cache_v10.pt` | Pre-cached physics windows tensor. Loaded by `PhysicsDataLoader`. |
| `datasets/peoples_speech/` | Audio data (MLCommons People's Speech). |
| `checkpoints/spine_physics.pt` | Pre-trained physics spine checkpoint. |
| `checkpoints/spine_text.pt` | Pre-trained text spine checkpoint. |
| `cassi_latest.pt` / `cassi_multimodal.pt` | Current best model checkpoint. |
| `logs/metrics/epoch_metrics.jsonl` | Per-epoch aggregated metrics. |
| `logs/test_metrics/` | Test-set metrics (when generated). |

**Data loading conventions:**
- Text is loaded as raw `bytes`, memory-mapped or ring-buffered.
- Physics is loaded from `.pt` cache (PyTorch tensors).
- Audio is loaded from Parquet or on-the-fly via `AudioFieldEncoder`.
- `StreamingTextSampler` supports **online learning**: call `.append(data_bytes)` while training.

---

## 7. Code Style & Conventions

### 7.1 Naming
- `PHI` = `(1 + 5**0.5) / 2` ≈ 1.618; `PHI_INV` = `1 / PHI` ≈ 0.618. Defined in `cassi/cord.py`.
- `D` = full field dimension (typically 1040 or 16384).
- `W` = workspace dimension (HoneybeeBrain only, typically 256).
- `B` = batch size in tensor shape comments.
- `N` or `n_specialists` = number of specialists.
- `C` = number of chakras (typically 13).
- Module-level constants are `UPPER_SNAKE_CASE`.

### 7.2 Tensor shape comments
Shape annotations are common in docstrings and inline comments:
```python
# x: [B, 4, 1024] — field history
# conscious: [B, D] — conscious workspace
```

### 7.3 State persistence
Models use `register_buffer(...)` extensively for state that must be saved in checkpoints but does not receive gradients:
- Breath phases (`t_yang`, `t_yin`)
- Qi fluid (`qi_fluid`)
- Harmony state (`harmony_state`)
- Meta-history (`meta_history`)
- Berry memory banks (`keys`, `values`, `counts`, `ages`)

**Critical rule:** When resetting buffers during a forward pass (e.g., neuroplasticizer pulse), use **assignment** (`self.t_yang = torch.zeros_like(self.t_yang)`) not **in-place ops** (`self.t_yang.zero_()`), to avoid corrupting the autograd graph.

### 7.4 Checkpointing pattern
All training scripts use atomic saves:
```python
tmp = path + '.tmp'
torch.save(ckpt, tmp)
os.replace(tmp, path)
```
Best checkpoints are saved as `*.pt.best`.

### 7.5 Logging
All training scripts define a `log_print(msg)` that writes to both stdout and a `.log` file. Log lines are prefixed with a run ID: `[{RUN_ID}] {msg}`.

---

## 8. Testing & Validation

**There is no formal test suite.** No `pytest`, no `unittest`, no `test_*.py` files.

Validation is performed inside training scripts:
- `val_mae` — mean absolute error on a held-out validation set.
- `spectral_slope_loss` — deviation from Kolmogorov `-5/3` spectrum (physics).
- `coherence_loss` — self-consistency between forward and reverse predictions.
- `phi_balance_loss` — regularization encouraging Yang/Yin frequency ratio toward φ.

**How to validate a model:**
```python
# In train.py or train_multimodal.py:
model.eval()
with torch.no_grad():
    val_mae = validate(model, val_loader, args)
```

**Debug scripts:** `debug_anomaly*.py` are standalone reproduction scripts for specific training anomalies. They instantiate the model, run a few forward passes, and print diagnostic tensors. Use them when training crashes or produces NaNs.

---

## 9. Observability & Debugging

### 9.1 Metrics (`cassi/observability.py`)
`CassiMetrics` records per-batch and per-epoch statistics:
- Yin-Yang dynamics: `yang_yin_ratio`, `conscious_yang_ratio`
- Specialist ecology: `specialist_entropy`, `harmony_effective_rank`
- Qi & Breath: `qi_energy`, `breath_yang`, `breath_yin`, `beat`, `phase_diff`, `freq_ratio`
- Training: `pred_error_mean`, `pred_error_std`, `spectral_slope`
- Memory: `berry_hit_rate`, `changepoint_triggered`, `soul_injection_strength`

Metrics are flushed to `logs/metrics/epoch_metrics.jsonl` after each epoch.

### 9.2 Dashboard (`cassi/dashboard.py`)
Generates a 4×3 grid of epoch-level plots. Run offline after training or point at live logs.

### 9.3 Typical debugging workflow
1. Check `logs/*.log` for the last error message.
2. Run the matching `debug_anomaly*.py` script to reproduce.
3. Inspect tensor shapes and NaN locations with `torch.isnan()`.
4. Check `CassiMetrics` JSONL for divergence patterns (e.g., `freq_ratio` drifting far from φ).
5. Use `profile_train.py` if training is unexpectedly slow.

---

## 10. Security Considerations

- **No secrets in code:** No API keys, tokens, or passwords are stored in the repository.
- **No network I/O:** The codebase does not make HTTP requests or open sockets.
- **File I/O:** Scripts read from `datasets/`, `checkpoints/`, and `logs/` relative to the working directory. They write checkpoints and logs to the same paths. Do not run with elevated privileges.
- **Pickle / torch.load:** `torch.load(..., weights_only=False)` is used throughout to load checkpoints and physics caches. Only load checkpoints you created.
- **Subprocess:** `cassi/audio_utils.py` may call `subprocess` for audio conversion. Verify inputs if exposing this to untrusted data.

---

## 11. GitNexus — Code Intelligence

This project is indexed by GitNexus as **cassi** (1616 symbols, 2205 relationships, 30 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

### Always Do
- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

### Never Do
- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

### Resources
| Resource | Use for |
|----------|---------|
| `gitnexus://repo/cassi/context` | Codebase overview, check index freshness |
| `gitnexus://repo/cassi/clusters` | All functional areas |
| `gitnexus://repo/cassi/processes` | All execution flows |
| `gitnexus://repo/cassi/process/{name}` | Step-by-step execution trace |

### CLI
| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

---

## 12. Design vs Implementation Protocol

> Direct user instruction, added 2026-06-08.

- **Only design when the user explicitly says "design".** Do not implement features during a design phase.
- **Designs need iterations.** Present design proposals as text/sketches/pseudocode first and wait for user feedback before writing production code.
- When the user says "implement" or approves a design, then write the code.

This rule overrides any implicit pressure to "just build it."
