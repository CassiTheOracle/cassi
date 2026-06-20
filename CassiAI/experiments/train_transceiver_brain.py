#!/usr/bin/env python3
"""Train TransceiverBrain on frozen CordPhysics spine.

Spine stays frozen; brain learns to use φ-damped interference for prediction.
Key metrics:
  - base_mae: spine alone
  - enh_mae: spine + transceiver brain
  - field_mean/std: whether field self-organizes to stable amplitude
  - freq_spread: whether neurons maintain frequency diversity
"""

import torch
import torch.nn.functional as F
import numpy as np, time, os
from collections import Counter, defaultdict

from cassi.cord import CordPhysics
from transceiver_brain import TransceiverBrain, PHI, PHI_INV

DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
CACHE_PATH = 'datasets/physics_cache_v10.pt'
SPINE_PATH = 'checkpoints/spine_physics.pt'
BRAIN_PATH = 'transceiver_brain.pt'
SAVE_EVERY = 50

phi = PHI
phi_inv = PHI_INV

LOG_PATH = 'cassi_physics.log'
RUN_ID = hex(int(time.time() * 1e6))[-6:]

LR = 1e-3
WD = 0.01
BS = 512
MAX_EPOCHS = 400


def log_print(msg):
    with open(LOG_PATH, 'a') as f:
        f.write(f"[{RUN_ID}] {msg}\n")
        f.flush()


def save_checkpoint(path, brain, val_mae, epoch):
    torch.save({
        'model': brain.state_dict(),
        'val_mae': val_mae,
        'epoch': epoch + 1,
    }, path)


# ── Setup ───────────────────────────────────────────────────────

log_print(f"Device: {DEV}  φ={phi:.4f}  φ⁻¹={phi_inv:.4f}")

# Load spine (frozen)
ck = torch.load(SPINE_PATH, map_location=DEV, weights_only=False)
state = ck.get('model', ck)
state = {k.replace('_orig_mod.', ''): v for k, v in state.items()}
spine.load_state_dict(state, strict=False)
spine.eval()
for p in spine.parameters():
    p.requires_grad = False
spine_val_mae = ck.get('val_mae', 'unknown')
log_print(f"Loaded spine: {SPINE_PATH}  val_mae={spine_val_mae}")

# Load data
cache = torch.load(CACHE_PATH, map_location='cpu', weights_only=False)
wins = torch.stack(cache['windows'])
labels = cache['labels']
rm = {v: k for k, v in cache['family_map'].items()}
log_print(f"Loaded cache: {len(wins)} windows, {len(rm)} families")

# Train/val split
n = len(wins)
rng = np.random.RandomState(42)
perm = rng.permutation(n)
split = int(n * 0.8)
ti, vi = perm[:split], perm[split:]
nt, nv = len(ti), len(vi)
log_print(f"Train: {nt}  Val: {nv}  BS: {BS}")

# Initialize brain (Phase 2: 128 neurons + homeostasis)
brain = TransceiverBrain(D=1040, n_neurons=128, use_homeostasis=True, homeo_gain=0.05).to(DEV)
n_params = sum(p.numel() for p in brain.parameters())
log_print(f"Brain params: {n_params:,}")
log_print(f"Neurons: {brain.n_neurons}")
log_print(f"Homeostasis: target={PHI**2:.3f}  gain=0.05")
log_print(f"φ-damping: ρ={PHI_INV:.4f}")
log_print(f"Optimizer: AdamW  lr={LR}  wd={WD}")

opt = torch.optim.AdamW(brain.parameters(), lr=LR, weight_decay=WD)

best_val = float('inf')
best_state = None
best_ep = 0
start_ep = 0

if os.path.exists(BRAIN_PATH):
    ck = torch.load(BRAIN_PATH, map_location=DEV, weights_only=False)
    brain.load_state_dict(ck['model'], strict=False)
    best_val = ck.get('val_mae', float('inf'))
    start_ep = ck.get('epoch', 0)
    log_print(f"Resumed from {BRAIN_PATH}  epoch={start_ep}  val_mae={best_val:.4f}")

rg = np.random.RandomState(42)
t_start = time.perf_counter()

# ── Training ────────────────────────────────────────────────────

for ep in range(start_ep, MAX_EPOCHS):
    brain.train()
    rg.shuffle(ti)
    epoch_loss = 0.0
    n_batches = 0

    for bi in range(0, nt, BS):
        bi2 = ti[bi:bi + BS]
        x = wins[bi2][:, :4].to(DEV)
        y = wins[bi2][:, 4].to(DEV)

        # Spine prediction + representation (spine params frozen, but keep graph)
        spine_pred, trajs = spine(x, return_trajectories=True)
        spine_repr = trajs['repr']

        # Reset brain state per batch (independent windows)
        brain.reset()

        # Brain residual
        residual = brain(spine_repr, use_neurons=True)
        enhanced = spine_pred + residual

        # Loss
        loss = F.mse_loss(enhanced, y)

        if not torch.isfinite(loss):
            log_print(f"  NaN loss at epoch {ep+1} — stopping")
            break

        opt.zero_grad()
        loss.backward()
        opt.step()

        epoch_loss += loss.item() * len(bi2)
        n_batches += 1

    # ── Validation ──────────────────────────────────────────────
    brain.eval()
    val_mae_base = 0.0
    val_mae_enh = 0.0
    val_mse_base = 0.0
    val_mse_enh = 0.0
    field_means = []
    field_stds = []
    field_energies = []
    freq_spreads = []

    with torch.no_grad():
        for bi in range(0, nv, BS):
            bi2 = vi[bi:bi + BS]
            x = wins[bi2][:, :4].to(DEV)
            y = wins[bi2][:, 4].to(DEV)

            spine_pred, trajs = spine(x, return_trajectories=True)
            spine_repr = trajs['repr']

            brain.reset()
            residual = brain(spine_repr, use_neurons=True)
            enhanced = spine_pred + residual

            val_mae_base += F.l1_loss(spine_pred, y).item() * len(bi2)
            val_mae_enh += F.l1_loss(enhanced, y).item() * len(bi2)
            val_mse_base += F.mse_loss(spine_pred, y).item() * len(bi2)
            val_mse_enh += F.mse_loss(enhanced, y).item() * len(bi2)

            stats = brain.get_field_stats()
            field_means.append(stats['mean'])
            field_stds.append(stats['std'])
            field_energies.append(stats.get('energy', 0.0))

            freqs = brain.get_neuron_freqs()
            freq_spreads.append(np.std(freqs))

    val_mae_base /= nv
    val_mae_enh /= nv
    val_mse_base /= nv
    val_mse_enh /= nv

    if not np.isfinite(val_mae_enh):
        log_print(f"  NaN detected at epoch {ep+1} — stopping")
        break

    improved = val_mae_enh < best_val * 0.999
    if val_mae_enh < best_val:
        best_val = val_mae_enh
        best_state = {k: v.clone().cpu() for k, v in brain.state_dict().items()}
        best_ep = ep

    if (ep + 1) % 10 == 0 or ep == start_ep:
        elapsed = time.perf_counter() - t_start
        delta = val_mae_base - val_mae_enh
        fmean = np.mean(field_means)
        fstd = np.mean(field_stds)
        fenergy = np.mean(field_energies)
        fspread = np.mean(freq_spreads)
        log_print(f"  epoch {ep+1:4d}  base={val_mae_base:.4f}  "
                  f"enh={val_mae_enh:.4f}  best={best_val:.4f}  "
                  f"Δ={delta:+.4f}  field={fmean:.3f}±{fstd:.3f}  "
                  f"energy={fenergy:.3f}  freq_spread={fspread:.3f}  "
                  f"[{int(elapsed//60)}m{int(elapsed%60):02d}s]")

    if (ep + 1) % SAVE_EVERY == 0 or (improved and ep > 0):
        save_checkpoint(BRAIN_PATH.replace('.pt', '_latest.pt'), brain, val_mae_enh, ep)

# ── Final eval ──────────────────────────────────────────────────

if best_state is not None:
    brain.load_state_dict(best_state)
brain.eval()
elapsed = time.perf_counter() - t_start
log_print(f"\n  Best: epoch {best_ep+1}  val_mae={best_val:.4f}  "
          f"[{int(elapsed//60)}m{int(elapsed%60):02d}s]")

# Per-family eval
vi_list = [int(x) for x in vi]
fc = Counter([rm[labels[i]] for i in vi_list])
fm = defaultdict(lambda: {'base_mae': [], 'enh_mae': []})

with torch.no_grad():
    for bi in range(0, nv, BS):
        bi2 = vi_list[bi:min(bi + BS, nv)]
        x = wins[bi2][:, :4].to(DEV)
        y = wins[bi2][:, 4].to(DEV)
        spine_pred, trajs = spine(x, return_trajectories=True)
        spine_repr = trajs['repr']
        brain.reset()
        residual = brain(spine_repr, use_neurons=True)
        enhanced = spine_pred + residual
        for j in range(len(bi2)):
            fam = rm[labels[bi2[j]]]
            fm[fam]['base_mae'].append(F.l1_loss(spine_pred[j:j+1], y[j:j+1]).item())
            fm[fam]['enh_mae'].append(F.l1_loss(enhanced[j:j+1], y[j:j+1]).item())

fnl = sorted(fm.keys(), key=lambda f: fc.get(f, 0), reverse=True)
log_print(f"\n  Family                   n    base     enh     Δ")
for fam in fnl:
    bm = np.mean(fm[fam]['base_mae'])
    em = np.mean(fm[fam]['enh_mae'])
    log_print(f"  {fam:<20s} {fc[fam]:>4d}  {bm:.4f}  {em:.4f}  {em-bm:+.4f}")

torch.save({
    'model': best_state,
    'val_mae': best_val,
    'epoch': best_ep + 1,
}, BRAIN_PATH)
log_print(f"\nSaved {BRAIN_PATH}  val_mae={best_val:.4f}")
