"""Cassi Dashboard — offline metric visualization from JSONL logs.

Usage:
    python -m cassi.dashboard --log logs/metrics/epoch_metrics.jsonl --out dashboard.png
    python -m cassi.dashboard --live  # watch live metrics (if training is running)
"""

import json
import argparse
import os
from typing import List, Dict
import numpy as np


def load_epoch_records(path: str) -> List[Dict]:
    """Load epoch metrics from JSONL."""
    records = []
    if not os.path.exists(path):
        return records
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def plot_epoch_dashboard(records: List[Dict], save_path: str = 'dashboard.png'):
    """Generate a comprehensive epoch-level dashboard."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Run: pip install matplotlib")
        return

    if not records:
        print("No records to plot.")
        return

    epochs = [r['epoch'] for r in records]

    fig = plt.figure(figsize=(18, 14))
    fig.suptitle('Cassi φ-Dashboard (Epoch View)', fontsize=16, fontweight='bold')

    # Layout: 4 rows x 3 cols
    def subplot(idx, title, ylabel, keys, colors, hlines=None):
        ax = plt.subplot(4, 3, idx)
        for key, color in zip(keys, colors):
            vals = [r.get(key, np.nan) for r in records]
            ax.plot(epochs, vals, color=color, linewidth=1.5, label=key.replace('_mean', ''))
        if hlines:
            for h, lbl in hlines:
                ax.axhline(h, color='gray', linestyle='--', alpha=0.5, label=lbl)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel('Epoch')
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=7, loc='best')
        ax.grid(True, alpha=0.3)
        return ax

    # Row 1: Yin-Yang dynamics
    subplot(1, 'Yang/Yin Ratio', 'Ratio',
            ['yang_yin_ratio_mean'], ['tab:red'],
            hlines=[(1.618, 'φ'), (1.0, 'balance')])
    subplot(2, 'Conscious Yang/Yin', 'Ratio',
            ['conscious_yang_ratio_mean'], ['tab:purple'],
            hlines=[(1.618, 'φ'), (1.0, 'balance')])
    subplot(3, 'Conscious Norm & Sparsity', 'Value',
            ['conscious_norm_mean', 'conscious_sparsity_mean'],
            ['tab:blue', 'tab:green'])

    # Row 2: Specialist ecology
    subplot(4, 'Specialist Entropy', 'Entropy',
            ['specialist_entropy_mean'], ['tab:cyan'])
    subplot(5, 'Specialist Top-1 Mass', 'Fraction',
            ['specialist_top1_mass_mean'], ['tab:orange'])
    subplot(6, 'Harmony Effective Rank', 'Count',
            ['harmony_effective_rank_mean'], ['tab:pink'])

    # Row 3: Training & memory
    subplot(7, 'Surprise', 'Magnitude',
            ['surprise_mean'], ['tab:olive'])
    subplot(8, 'Prediction Error', 'MSE',
            ['pred_error_mean_mean'], ['tab:brown'])
    subplot(9, 'Berry Hit Rate', 'Fraction',
            ['berry_hit_rate_mean'], ['tab:gray'])

    # Row 4: Spectral & Qi
    subplot(10, 'Spectral Slope', 'Slope',
            ['spectral_slope_mean'], ['tab:cadetblue'],
            hlines=[(-1.667, '-5/3 target')])
    subplot(11, 'Qi Yang/Yin', 'Ratio',
            ['qi_yang_yin_ratio_mean'], ['tab:crimson'],
            hlines=[(1.618, 'φ'), (1.0, 'balance')])
    subplot(12, 'Changepoint Frequency', 'Rate',
            ['changepoint_triggered_mean'], ['tab:gold'])

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"Dashboard saved to {save_path}")


def plot_batch_window(log_dir: str = 'logs/metrics', save_path: str = 'dashboard_live.png', window: int = 100):
    """Plot the most recent batch-level metrics from ring buffers.
    Requires importing CassiMetrics with its buffer state (only useful in-process)."""
    print("Batch-level live plotting requires running inside the training process.")
    print("Use CassiMetrics.plot_dashboard() from train_multimodal.py instead.")


def print_summary_table(records: List[Dict], last_n: int = 5):
    """Print a text summary of the last N epochs."""
    if not records:
        print("No records.")
        return
    for rec in records[-last_n:]:
        ep = rec.get('epoch', '?')
        print(f"\n=== Epoch {ep} ===")
        keys = [
            'yang_yin_ratio_mean',
            'conscious_yang_ratio_mean',
            'conscious_norm_mean',
            'conscious_sparsity_mean',
            'surprise_mean',
            'specialist_entropy_mean',
            'harmony_effective_rank_mean',
            'qi_yang_yin_ratio_mean',
            'berry_hit_rate_mean',
            'spectral_slope_mean',
            'changepoint_triggered_mean',
        ]
        for k in keys:
            if k in rec:
                print(f"  {k:40s}: {rec[k]:.4f}")


def main():
    parser = argparse.ArgumentParser(description='Cassi Dashboard')
    parser.add_argument('--log', default='logs/metrics/epoch_metrics.jsonl',
                        help='Path to epoch metrics JSONL')
    parser.add_argument('--out', default='dashboard.png',
                        help='Output image path')
    parser.add_argument('--summary', action='store_true',
                        help='Print text summary instead of plotting')
    parser.add_argument('--last-n', type=int, default=5,
                        help='Number of epochs in summary')
    args = parser.parse_args()

    records = load_epoch_records(args.log)
    if args.summary:
        print_summary_table(records, last_n=args.last_n)
    else:
        plot_epoch_dashboard(records, save_path=args.out)


if __name__ == '__main__':
    main()
