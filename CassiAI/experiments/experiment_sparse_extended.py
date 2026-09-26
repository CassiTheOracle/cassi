#!/usr/bin/env python3
"""Extended experiment: Sparse brain for more epochs + more specialists.

Compares:
  - Sparse-5 (5 specialists, 20 epochs)
  - Sparse-7 (7 specialists, 20 epochs)
  - Sparse-10 (10 specialists, 20 epochs)
  - Baseline-5 (reference, 10 epochs)
"""

import torch
import torch.nn.functional as F
import numpy as np
import time

from cassi.phi_garden import PhiGardenBrain
from cassi.cord import PHI

DEV = 'cuda'
D = 1040


def make_synthetic_data(n=5000, D_data=1024, T=4):
    """Piecewise smooth + abrupt regime changes."""
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
    x = seq[:, :T, :]
    y = seq[:, -1, :]
    return x, y


def train_epoch(model, x_train, y_train, opt, bs=256):
    model.train()
    n = len(x_train)
    idx = torch.randperm(n, device=DEV)
    epoch_loss = 0.0
    epoch_mae = 0.0
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
        epoch_loss += loss.item() * len(x)
        epoch_mae += F.l1_loss(pred, y).item() * len(x)
        n_batches += 1
    return epoch_loss / n, epoch_mae / n


def eval_model(model, x_val, y_val, bs=256):
    model.eval()
    n = len(x_val)
    total_mae = 0.0
    total_mse = 0.0
    harmony_scores = []
    k_values = []
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
            if 'k_eff' in info and hasattr(info['k_eff'], 'cpu'):
                k_values.extend(info['k_eff'].cpu().numpy().tolist())
    return total_mae / n, total_mse / n, harmony_scores, k_values


def run():
    print("=" * 70)
    print("Sparse Extended: More Epochs + More Specialists")
    print("=" * 70)

    x_train, y_train = make_synthetic_data(8000)
    x_val, y_val = make_synthetic_data(2000)

    configs = [
        ('Baseline-5', PhiGardenBrain, {'n_specialists': 5}, 10),
        ('Sparse-5', HarmonyBrain, {'n_specialists': 5, 'min_k': 1, 'mode': 'sparse'}, 20),
        ('Sparse-7', HarmonyBrain, {'n_specialists': 7, 'min_k': 1, 'mode': 'sparse'}, 20),
        ('Sparse-10', HarmonyBrain, {'n_specialists': 10, 'min_k': 2, 'mode': 'sparse'}, 20),
    ]

    models = {}
    opts = {}
    for name, cls, kwargs, epochs in configs:
        model = cls(D=D, n_slots=512, memory_value_dim=26,
                    readout_hidden=520, byte_mode=False, **kwargs).to(DEV)
        n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())
        print(f"{name:15s} params: {n_params:,} / {total:,}  epochs: {epochs}")
        models[name] = (model, epochs)
        opts[name] = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=0.01)

    print()
    results = {name: {'val_mae': [], 'val_mse': []} for name in models}

    t0 = time.perf_counter()
    max_epochs = max(epochs for _, _, _, epochs in configs)

    for ep in range(max_epochs):
        for name, (model, max_ep) in models.items():
            if ep >= max_ep:
                continue
            train_loss, train_mae = train_epoch(model, x_train, y_train, opts[name])
            val_mae, val_mse, h_scores, k_vals = eval_model(model, x_val, y_val)
            results[name]['val_mae'].append(val_mae)
            results[name]['val_mse'].append(val_mse)

        if (ep + 1) % 2 == 0 or ep == 0:
            elapsed = time.perf_counter() - t0
            parts = [f"ep {ep+1:2d} [{elapsed:5.1f}s]"]
            for name in models:
                if len(results[name]['val_mae']) > 0:
                    parts.append(f"{name}={results[name]['val_mae'][-1]:.4f}")
            print("  ".join(parts))

    # Final summary
    print("\n" + "=" * 70)
    print("Final Results")
    print("=" * 70)
    for name in models:
        final_mae = results[name]['val_mae'][-1]
        best_mae = min(results[name]['val_mae'])
        print(f"{name:15s} final MAE={final_mae:.4f}  best MAE={best_mae:.4f}")

    # Analyze sparse variants
    for name in ['Sparse-5', 'Sparse-7', 'Sparse-10']:
        model, _ = models[name]
        _, _, h_scores, k_vals = eval_model(model, x_val, y_val)
        if h_scores and k_vals:
            h_arr = np.array(h_scores)
            k_arr = np.array(k_vals)
            corr = np.corrcoef(h_arr, k_arr)[0, 1] if len(h_arr) > 1 else 0
            print(f"\n--- {name} ---")
            print(f"  Mean harmony: {h_arr.mean():.2f}  k: {k_arr.mean():.2f}")
            print(f"  Harmony-k correlation: {corr:.3f}")

            # Error vs harmony
            all_errors = []
            all_harmony = []
            all_k = []
            with torch.no_grad():
                for i in range(0, len(x_val), 256):
                    x = x_val[i:i+256]
                    y = y_val[i:i+256]
                    model.reset_workspace(len(x))
                    pred, info = model(x, use_memory=True, return_workspace=True)
                    error = (pred - y).abs().mean(dim=-1).cpu().numpy()
                    harmony = info['harmony'].mean(dim=0).cpu().numpy()
                    k_eff = info['k_eff'].cpu().numpy()
                    if error.ndim == 0:
                        all_errors.append(float(error))
                        all_harmony.append(float(harmony))
                        all_k.append(float(k_eff))
                    else:
                        all_errors.extend(error.tolist())
                        all_harmony.extend(harmony.tolist())
                        all_k.extend(k_eff.tolist())

            if len(all_errors) > 10:
                err_arr = np.array(all_errors)
                harm_arr = np.array(all_harmony)
                low_mask = harm_arr < np.percentile(harm_arr, 25)
                high_mask = harm_arr > np.percentile(harm_arr, 75)
                print(f"  Low harmony:  error={err_arr[low_mask].mean():.4f}  k={np.array(all_k)[low_mask].mean():.2f}")
                print(f"  High harmony: error={err_arr[high_mask].mean():.4f}  k={np.array(all_k)[high_mask].mean():.2f}")
                print(f"  Error-harmony r: {np.corrcoef(err_arr, harm_arr)[0,1]:.3f}")


if __name__ == '__main__':
    run()
