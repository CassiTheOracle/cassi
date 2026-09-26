# QiField Physics Training — Design Contract

## Goal
Prepare QiField to train on `datasets/physics_cache_multihz_v1.pt` (and optionally `physics_cache_v10.pt`), which contain continuous 1024-D field-vector windows. The physics task is **regression**: given 4 input frames, predict target frame(s).

## Design

### 1. QiField continuous mode
Add a continuous-field regression path to `cassi/qi_field.py` while keeping byte-mode behavior unchanged.

New constructor arguments (after existing args, before `multi_scale_bytes`):
```python
input_dim: int = 256,
output_dim: int = 256,
continuous_mode: bool = False,
```

Behavior:
- When `continuous_mode=False` (default): exact current byte-mode behavior.
- When `continuous_mode=True`:
  - Input `x` to `embed()` is a float tensor `[B, N, input_dim]`.
  - Use `self.input_proj = nn.Linear(input_dim, d)` instead of `token_embed`/`imag_proj`.
  - Position encodings are still added.
  - Readout produces `output_dim`-dimensional continuous vectors via `self.output_proj = nn.Linear(d, output_dim)` instead of `readout_y`/`readout_z` logits.
  - `training_loss(self, x, y=None)`:
    - If `y` is provided (continuous mode target), `y` has shape `[B, output_dim]`.
    - Embed `x`, run `K_train` field steps.
    - Pool the final field state across positions (e.g., mean of last position or mean over all positions) and project to `[B, output_dim]`.
    - Loss is `F.mse_loss(pred, y)`; no CE, no pattern-memory text losses.
    - Return `(loss, diagnostics)` with diagnostics containing `loss`, `mse_loss`, `Q_mean`, etc.
  - `generate_autoregressive(seed, max_new=1, ...)` for continuous mode:
    - `seed` is `[B, N_seed, input_dim]`.
    - Autoregressively predict one frame at a time by feeding the last predicted frame back as input.
    - Return `[B, max_new, output_dim]`.
  - `step(input_ids)` should be generalized: if `continuous_mode`, `input_ids` is float `[B, L, input_dim]` and returns continuous prediction for the next position.

Implementation notes:
- Do not remove or rename existing parameters/buffers unless necessary.
- Keep `V=256` default for byte mode; in continuous mode `V` is still passed but unused for embedding/readout.
- Keep multi-scale byte embedder only for byte mode (disable or ignore in continuous mode).
- Keep all Qi dynamics (IIR, transceivers, controller, pattern memory, glial, breath) unchanged — they operate on the complex field `psi`.

### 2. Physics trainer
Create `experiments/train_qi_field_physics.py` analogous to `experiments/train_qi_field.py` but for physics regression.

Key differences from text trainer:
- Data source: `datasets/physics_cache_multihz_v1.pt` (default; `--cache` flag).
- Use `MultimodalDataLoader(physics_cache=..., phase=0)` or a minimal dedicated loader to get train/val splits and batches.
- Model constructed with `continuous_mode=True, input_dim=1024, output_dim=1024`.
- Default hyperparameters tuned for physics: `--N 4` or `--N 5`, `--d 512` or `--d 1024`, `--bs 64`, `--lr 1e-3`.
- Loss is MSE; log `mse_loss` and `mae`.
- Validation samples `x, y` and computes MSE/MAE.
- Generation/rollout: every `--gen-every` epochs, sample a val window, feed first 4 frames, rollout `--gen-horizon` frames, compare to ground-truth target(s), print MAE.
- Resume logic mirrors text trainer.
- Save checkpoints to `checkpoints/N{N}_d{d}_qifield_physics_v1/`.

### 3. Smoke test
Create or run a short script that:
- Builds `QiField(N=4, d=128, continuous_mode=True, input_dim=1024, output_dim=1024)`.
- Loads one physics batch `[B, 4, 1024]` and target `[B, 1024]`.
- Runs `training_loss(x, y)`, checks finite loss and finite gradients after `backward()`.
- Optionally runs a 1-step rollout.

## Acceptance criteria
- `python3 experiments/train_qi_field_physics.py --epochs 1 --bs 4 --steps-per-epoch 2 --N 4 --d 128` runs without NaN/inf on CUDA:1 (7900 XTX).
- Byte-mode trainer `experiments/train_qi_field.py` still runs a single epoch on text data unchanged.
- All new code follows repo conventions (separator comments, shape annotations, `weights_only=True` for non-physics-cache loads).
