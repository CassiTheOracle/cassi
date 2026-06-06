"""Cassi Observability — metrics and diagnostics for the φ-brain.

Tracks Yin-Yang dynamics, specialist ecology, memory topology, and
consciousness statistics so architectural decisions are data-driven.

Design principles:
  - Zero training overhead: metrics are computed from tensors already in memory.
  - Persistent logs: JSONL per epoch for post-hoc analysis.
  - Real-time dashboard: matplotlib plots updated every N batches.
"""

import torch
import torch.nn.functional as F
import json
import os
import time
from collections import deque
from typing import Dict, List, Optional
import numpy as np


class CassiMetrics:
    """Collects per-batch and per-epoch metrics without gradient interference.

    Usage:
        metrics = CassiMetrics(log_dir='logs/metrics')
        for batch in loader:
            pred, info = model(x)
            metrics.record_batch(info, loss, pred, target)
        metrics.flush_epoch(epoch=1)
        metrics.plot_dashboard(save_path='logs/dashboard_epoch_1.png')
    """

    def __init__(self, log_dir: str = 'logs/metrics', window_size: int = 100):
        os.makedirs(log_dir, exist_ok=True)
        self.log_dir = log_dir
        self.window_size = window_size

        # Per-batch ring buffers (fast access for dashboard)
        self.batch_buffer = {
            'yang_yin_ratio': deque(maxlen=window_size),
            'conscious_yang_ratio': deque(maxlen=window_size),
            'conscious_norm': deque(maxlen=window_size),
            'conscious_sparsity': deque(maxlen=window_size),
            'surprise': deque(maxlen=window_size),
            'harmony_mean': deque(maxlen=window_size),
            'specialist_entropy': deque(maxlen=window_size),
            'qi_yang_yin_ratio': deque(maxlen=window_size),
            'meta_cord_norm': deque(maxlen=window_size),
            'pred_error': deque(maxlen=window_size),
            'spectral_slope': deque(maxlen=window_size),
            'berry_hit_rate': deque(maxlen=window_size),
            'changepoint_triggered': deque(maxlen=window_size),
            'soul_injection_strength': deque(maxlen=window_size),
        }

        # Per-epoch aggregates (written to disk)
        self.epoch_records: List[Dict] = []
        self.current_epoch_batches: List[Dict] = []

    def record_batch(
        self,
        info: Dict,
        loss: Optional[float] = None,
        pred: Optional[torch.Tensor] = None,
        target: Optional[torch.Tensor] = None,
        model=None,
    ):
        """Record a single batch's worth of metrics.

        info: dict returned by HarmonyBrain/MultimodalBrain forward.
        model: the brain instance (for accessing buffers/parameters).
        """
        record = {}

        # --- YIN-YANG DYNAMICS ---
        workspace_fwd = info.get('workspace_fwd')
        workspace_rev = info.get('workspace_rev')
        if workspace_fwd is not None and workspace_rev is not None:
            with torch.no_grad():
                yang = workspace_fwd.norm(dim=-1).mean().item()
                yin = workspace_rev.norm(dim=-1).mean().item()
                record['yang_yin_ratio'] = yang / (yin + 1e-8)

        # --- CONSCIOUSNESS DECOMPOSITION ---
        conscious = info.get('conscious')
        if conscious is not None and workspace_fwd is not None and workspace_rev is not None:
            with torch.no_grad():
                from cassi.cord import PHI, PHI_INV
                yang_comp = (PHI_INV * workspace_fwd).norm(dim=-1)
                yin_comp = (PHI_INV ** 2 * workspace_rev).norm(dim=-1)
                record['conscious_yang_ratio'] = (yang_comp / (yin_comp + 1e-8)).mean().item()
                record['conscious_norm'] = conscious.norm(dim=-1).mean().item()
                record['conscious_sparsity'] = (conscious.abs() < 1e-3).float().mean().item()

        # --- SURPRISE & HARMONY ---
        record['surprise'] = info.get('surprise', 0.0)
        harmony = info.get('harmony')
        if harmony is not None:
            with torch.no_grad():
                record['harmony_mean'] = harmony.mean().item()

        # --- SPECIALIST ECOLOGY ---
        weights = info.get('weights')
        energy = info.get('energy')
        harmony_matrix = info.get('harmony_matrix')
        if weights is not None:
            with torch.no_grad():
                # Entropy of specialist weights per sample, averaged over batch
                p = weights.clamp(min=1e-8)
                p = p / p.sum(dim=0, keepdim=True)
                entropy = -(p * p.log()).sum(dim=0)
                record['specialist_entropy'] = entropy.mean().item()

                # Dominance: fraction of mass held by top-1 specialist
                top1_mass = p.max(dim=0).values.mean().item()
                record['specialist_top1_mass'] = top1_mass

        if energy is not None:
            with torch.no_grad():
                record['energy_mean'] = energy.mean().item()
                record['energy_std'] = energy.std().item()

        if harmony_matrix is not None:
            with torch.no_grad():
                # Eigenvalues of harmony matrix reveal specialist factions
                hm = harmony_matrix
                if hm.dim() == 3:
                    # [N, N, B] — average over batch
                    hm = hm.mean(dim=-1)
                # hm should now be [N, N]
                if hm.dim() == 2 and hm.shape[0] == hm.shape[1]:
                    eigvals = torch.linalg.eigvalsh(hm)
                    record['harmony_eig_max'] = eigvals[-1].item()
                    record['harmony_eig_min'] = eigvals[0].item()
                    record['harmony_effective_rank'] = (eigvals.abs() > 1e-3).sum().item()

        # --- QI-FLUID ---
        if model is not None and hasattr(model, 'qi_yang') and hasattr(model, 'qi_yin'):
            with torch.no_grad():
                qy = model.qi_yang.norm(dim=-1).mean().item()
                qi = model.qi_yin.norm(dim=-1).mean().item()
                record['qi_yang_yin_ratio'] = qy / (qi + 1e-8)

        # --- META-CORD ---
        if model is not None and hasattr(model, 'meta_history'):
            with torch.no_grad():
                record['meta_cord_norm'] = model.meta_history.norm(dim=-1).mean().item()

        # --- PREDICTION ERROR ---
        if pred is not None and target is not None:
            with torch.no_grad():
                err = F.mse_loss(pred, target, reduction='none').mean(dim=-1)
                record['pred_error_mean'] = err.mean().item()
                record['pred_error_std'] = err.std().item()

        # --- BERRY MEMORY ---
        memory_attn = info.get('memory_attn')
        if memory_attn is not None:
            with torch.no_grad():
                # Hit rate: fraction of attention mass on filled slots
                if hasattr(model, 'berry_memory'):
                    mask = model.berry_memory.mask.float()
                    filled_mass = (memory_attn * mask.unsqueeze(0)).sum(dim=-1).mean().item()
                    record['berry_hit_rate'] = filled_mass
                    record['berry_n_filled'] = model.berry_memory.n_filled.item()

        # --- CHANGepoint ---
        record['changepoint_triggered'] = 1.0 if info.get('changepoint') else 0.0

        # --- SOUL ---
        if model is not None and hasattr(model, 'soul') and model.soul is not None:
            with torch.no_grad():
                record['soul_norm'] = model.soul.vector.norm().item()
                record['soul_count'] = model.soul.count.item()

        # --- SPECTRAL (physics only) ---
        if pred is not None and pred.shape[-1] == 1024:
            with torch.no_grad():
                # Rough spectral slope estimate via FFT
                spec = torch.fft.rfft(pred, dim=-1).abs()
                freqs = torch.arange(1, spec.shape[-1] // 4 + 1, device=spec.device)
                spec_slice = spec[:, 1:spec.shape[-1] // 4 + 1].mean(dim=0)
                # Log-log linear regression for slope
                log_f = torch.log(freqs.float())
                log_s = torch.log(spec_slice + 1e-8)
                slope = ((log_f - log_f.mean()) * (log_s - log_s.mean())).sum() / ((log_f - log_f.mean()) ** 2).sum()
                record['spectral_slope'] = slope.item()

        # Update ring buffers
        for key, val in record.items():
            if key in self.batch_buffer:
                self.batch_buffer[key].append(val)

        self.current_epoch_batches.append(record)
        return record

    def flush_epoch(self, epoch: int, val_metrics: Optional[Dict] = None):
        """Aggregate batch records and write epoch summary to disk."""
        if not self.current_epoch_batches:
            return

        agg = {}
        keys = self.current_epoch_batches[0].keys()
        for key in keys:
            vals = [b[key] for b in self.current_epoch_batches if key in b]
            if vals:
                agg[f'{key}_mean'] = float(np.mean(vals))
                agg[f'{key}_std'] = float(np.std(vals))
                agg[f'{key}_min'] = float(np.min(vals))
                agg[f'{key}_max'] = float(np.max(vals))

        agg['epoch'] = epoch
        agg['n_batches'] = len(self.current_epoch_batches)
        agg['timestamp'] = time.time()

        if val_metrics is not None:
            agg['val'] = val_metrics

        self.epoch_records.append(agg)

        # Write JSONL
        path = os.path.join(self.log_dir, 'epoch_metrics.jsonl')
        with open(path, 'a') as f:
            f.write(json.dumps(agg) + '\n')

        # Clear batch buffer
        self.current_epoch_batches = []

    def get_latest(self, key: str, n: int = 10):
        """Get the last N values of a metric from the ring buffer."""
        buf = self.batch_buffer.get(key, deque())
        return list(buf)[-n:]

    def plot_dashboard(self, save_path: Optional[str] = None):
        """Generate a multi-panel dashboard of current metrics."""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            return

        fig, axes = plt.subplots(3, 3, figsize=(15, 12))
        fig.suptitle('Cassi φ-Dashboard', fontsize=14)

        panels = [
            ('yang_yin_ratio', 'Yang/Yin Ratio', 'tab:red'),
            ('conscious_yang_ratio', 'Conscious Yang/Yin', 'tab:purple'),
            ('conscious_norm', 'Conscious Norm', 'tab:blue'),
            ('conscious_sparsity', 'Conscious Sparsity', 'tab:green'),
            ('surprise', 'Surprise', 'tab:orange'),
            ('specialist_entropy', 'Specialist Entropy', 'tab:cyan'),
            ('qi_yang_yin_ratio', 'Qi Yang/Yin', 'tab:pink'),
            ('pred_error', 'Pred Error', 'tab:brown'),
            ('berry_hit_rate', 'Berry Hit Rate', 'tab:olive'),
        ]

        for ax, (key, title, color) in zip(axes.flat, panels):
            vals = self.get_latest(key, n=self.window_size)
            if vals:
                ax.plot(vals, color=color, linewidth=1.2)
                ax.axhline(1.618, color='gray', linestyle='--', alpha=0.5, label='φ')
                ax.set_title(title, fontsize=10)
                ax.set_xlabel('Batch')
                ax.grid(True, alpha=0.3)
            else:
                ax.set_title(f'{title} (no data)')
                ax.set_xticks([])
                ax.set_yticks([])

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150)
        plt.close()

    def summary_table(self, epoch: Optional[int] = None):
        """Print a text summary of key metrics."""
        if epoch is not None and epoch < len(self.epoch_records):
            rec = self.epoch_records[epoch]
        elif self.epoch_records:
            rec = self.epoch_records[-1]
        else:
            return "No records."

        lines = [
            f"Epoch {rec.get('epoch', '?')}",
            "-" * 40,
            f"Yang/Yin ratio:       {rec.get('yang_yin_ratio_mean', 0):.3f} ± {rec.get('yang_yin_ratio_std', 0):.3f}",
            f"Conscious Yang/Yin:   {rec.get('conscious_yang_ratio_mean', 0):.3f} ± {rec.get('conscious_yang_ratio_std', 0):.3f}",
            f"Conscious norm:       {rec.get('conscious_norm_mean', 0):.3f}",
            f"Conscious sparsity:   {rec.get('conscious_sparsity_mean', 0):.3f}",
            f"Surprise:             {rec.get('surprise_mean', 0):.3f}",
            f"Specialist entropy:   {rec.get('specialist_entropy_mean', 0):.3f}",
            f"Spec entropy std:     {rec.get('specialist_entropy_std', 0):.3f}",
            f"Harmony eff. rank:    {rec.get('harmony_effective_rank_mean', 0):.1f}",
            f"Qi Yang/Yin:          {rec.get('qi_yang_yin_ratio_mean', 0):.3f}" if 'qi_yang_yin_ratio_mean' in rec else "Qi Yang/Yin:          N/A",
            f"Berry hit rate:       {rec.get('berry_hit_rate_mean', 0):.3f}",
            f"Spectral slope:       {rec.get('spectral_slope_mean', 0):.3f}",
            f"Changepoint freq:     {rec.get('changepoint_triggered_mean', 0):.3f}",
            "-" * 40,
        ]
        return '\n'.join(lines)
