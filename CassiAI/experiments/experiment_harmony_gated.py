#!/usr/bin/env python3
"""Experiment: Harmony-Gated Attention vs Baseline vs Qi-Fluid.

Compares three architectures on synthetic regression:
  1. Baseline PhiGardenBrain (no harmony)
  2. HarmonyBrain (Qi-fluid rate modulation)
  3. HarmonyBrain mode=gated (direct specialist gating)
"""

import torch
import torch.nn.functional as F
import numpy as np
import time

from cassi.phi_garden import PhiGardenBrain
from cassi.harmony_brain import HarmonyBrain
from cassi.cord import PHI

DEV = 'cuda'
D = 1040
N_SPEC = 5


def make_synthetic_data(n=5000, D_data=1024, T=4):
    """Piecewise smooth + abrupt regime changes.
    Returns x:[B,T,D_data], y:[B,D_data] — x is history, y is target.
    D_data must be 1024 to match CordPhysics in_proj.
    """
    # Generate temporal sequence data
    seq = torch.randn(n, T + 1, D_data, device=DEV)
    regime = torch.rand(n, 1, device=DEV)

    t = torch.linspace(0, 4 * np.pi, D_data, device=DEV)
    for b in range(n):
        r = regime[b].item()
        if r < 0.4:
            for tt in range(T + 1):
                seq[b, tt] = torch.sin(t * (1.5 + tt * 0.1)) * 0.5 + torch.randn(D_data, device=DEV) * 0.1
        elif r < 0.7:
            for tt in range(T + 1):
                seq[b, tt] = torch.cos(t * (2.0 + tt * 0.1)) * 0.3 + torch.randn(D_data, device=DEV) * 0.2
        else:
            for tt in range(T + 1):
                seq[b, tt] = torch.randn(D_data, device=DEV) * 0.5
            idx = torch.randint(0, D_data, (3,), device=DEV)
            seq[b, -1, idx] += torch.randn(3, device=DEV) * 2.0

    x = seq[:, :T, :]  # [B, T, D_data] — history
    y = seq[:, -1, :]  # [B, D_data] — target
    return x, y


def train_epoch(model, x_train, y_train, opt, bs=256):
    model.train()
    n = len(x_train)
    idx = torch.randperm(n, device=DEV)
    total_loss = 0.0
    total_mae = 0.0
    n_batches = 0

    for i in range(0, n, bs):
        b_idx = idx[i:i+bs]
        x = x_train[b_idx]
        y = y_train[b_idx]

        model.reset_workspace(len(x))
        pred = model(x, use_memory=True, return_workspace=False)

        loss = F.mse_loss(pred, y)
        if not torch.isfinite(loss):
            continue

        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

        total_loss += loss.item() * len(x)
        total_mae += F.l1_loss(pred, y).item() * len(x)
        n_batches += 1

    return total_loss / n, total_mae / n


def eval_model(model, x_val, y_val, bs=256):
    model.eval()
    n = len(x_val)
    total_mae = 0.0
    total_mse = 0.0
    harmony_scores = []
    gate_scores = []

    with torch.no_grad():
        for i in range(0, n, bs):
            x = x_val[i:i+bs]
            y = y_val[i:i+bs]

            model.reset_workspace(len(x))
            pred, info = model(x, use_memory=True, return_workspace=True)

            total_mae += F.l1_loss(pred, y).item() * len(x)
            total_mse += F.mse_loss(pred, y).item() * len(x)

            if 'harmony' in info and hasattr(info['harmony'], 'cpu'):
                h = info['harmony'].mean(dim=0).cpu().numpy()
                if h.ndim == 0:
                    harmony_scores.append(float(h))
                else:
                    harmony_scores.extend(h.tolist())
            if 'harmony_gate' in info and hasattr(info['harmony_gate'], 'cpu'):
                g = info['harmony_gate'].mean(dim=0).cpu().numpy()
                if g.ndim == 0:
                    gate_scores.append(float(g))
                else:
                    gate_scores.extend(g.tolist())

    return total_mae / n, total_mse / n, harmony_scores, gate_scores


def run_experiment():
    print("=" * 70)
    print("Harmony-Gated Attention Experiment")
    print("=" * 70)

    # Data
    x_train, y_train = make_synthetic_data(8000)
    x_val, y_val = make_synthetic_data(2000)

    # Models
    baseline = PhiGardenBrain(D=D, n_specialists=N_SPEC, n_slots=512,
                              memory_value_dim=26, readout_hidden=520).to(DEV)

    qi_brain = HarmonyBrain(D=D, n_specialists=N_SPEC, n_slots=512,
                            memory_value_dim=26, readout_hidden=520).to(DEV)

    gated_brain = HarmonyBrain(mode="gated", D=D, n_specialists=N_SPEC, n_slots=512,
                                    memory_value_dim=26, readout_hidden=520).to(DEV)

    combined_brain = HarmonyBrain(mode="combined", D=D, n_specialists=N_SPEC, n_slots=512,
                                          memory_value_dim=26, readout_hidden=520).to(DEV)

    sparse_brain = HarmonyBrain(mode='sparse', D=D, n_specialists=N_SPEC, n_slots=512,
                                memory_value_dim=26, readout_hidden=520,
                                min_k=1).to(DEV)

    models = {
        'Baseline': baseline,
        'Qi-Fluid': qi_brain,
        'Harmony-Gated': gated_brain,
        'Combined': combined_brain,
        'Sparse': sparse_brain,
    }

    for name, model in models.items():
        n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())
        print(f"{name:15s} params: {n_params:,} / {total:,}")

    print()

    # Optimizers
    opts = {
        name: torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=0.01)
        for name, model in models.items()
    }

    # Train
    n_epochs = 10
    results = {name: {'train_mae': [], 'val_mae': [], 'val_mse': []} for name in models}

    t0 = time.perf_counter()
    for ep in range(n_epochs):
        for name, model in models.items():
            train_loss, train_mae = train_epoch(model, x_train, y_train, opts[name])
            val_mae, val_mse, h_scores, g_scores = eval_model(model, x_val, y_val)

            results[name]['train_mae'].append(train_mae)
            results[name]['val_mae'].append(val_mae)
            results[name]['val_mse'].append(val_mse)

        if (ep + 1) % 2 == 0 or ep == 0:
            elapsed = time.perf_counter() - t0
            print(f"ep {ep+1:2d} [{elapsed:5.1f}s]  "
                  f"Base={results['Baseline']['val_mae'][-1]:.4f}  "
                  f"Qi={results['Qi-Fluid']['val_mae'][-1]:.4f}  "
                  f"Gated={results['Harmony-Gated']['val_mae'][-1]:.4f}  "
                  f"Combo={results['Combined']['val_mae'][-1]:.4f}")

    # Final summary
    print("\n" + "=" * 70)
    print("Final Results")
    print("=" * 70)
    for name in models:
        final_mae = results[name]['val_mae'][-1]
        best_mae = min(results[name]['val_mae'])
        print(f"{name:15s} final MAE={final_mae:.4f}  best MAE={best_mae:.4f}")

    # Harmony analysis for sparse brain
    print("\n--- Sparse Brain Analysis ---")
    _, _, h_scores, g_scores = eval_model(sparse_brain, x_val, y_val)
    if h_scores:
        h_arr = np.array(h_scores)
        print(f"Mean harmony: {h_arr.mean():.3f}  std: {h_arr.std():.3f}")
    if g_scores:
        g_arr = np.array(g_scores)
        print(f"Mean gate:    {g_arr.mean():.3f}  std: {g_arr.std():.3f}")

    # Error vs harmony correlation for sparse
    print("\n--- Error-Harmony Correlation (Sparse) ---")
    sparse_brain.eval()
    all_errors = []
    all_harmony = []
    all_k = []
    with torch.no_grad():
        for i in range(0, len(x_val), 256):
            x = x_val[i:i+256]
            y = y_val[i:i+256]
            sparse_brain.reset_workspace(len(x))
            pred, info = sparse_brain(x, use_memory=True, return_workspace=True)
            error = (pred - y).abs().mean(dim=-1).cpu().numpy()
            harmony = info['harmony'].mean(dim=0).cpu().numpy()
            if error.ndim == 0:
                all_errors.append(float(error))
                all_harmony.append(float(harmony))
            else:
                all_errors.extend(error.tolist())
                all_harmony.extend(harmony.tolist())
            all_k.extend(info['k_eff'].cpu().numpy().tolist())

    if len(all_errors) > 10:
        corr = np.corrcoef(all_errors, all_harmony)[0, 1]
        print(f"Pearson r (error vs harmony): {corr:.3f}")

        err_arr = np.array(all_errors)
        harm_arr = np.array(all_harmony)
        k_arr = np.array(all_k)
        low_mask = harm_arr < np.percentile(harm_arr, 25)
        high_mask = harm_arr > np.percentile(harm_arr, 75)
        print(f"Low harmony  (bottom 25%): error={err_arr[low_mask].mean():.4f}  k={k_arr[low_mask].mean():.2f}")
        print(f"High harmony (top 25%):    error={err_arr[high_mask].mean():.4f}  k={k_arr[high_mask].mean():.2f}")

    return results


if __name__ == '__main__':
    run_experiment()
