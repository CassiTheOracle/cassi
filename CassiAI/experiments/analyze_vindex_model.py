#!/usr/bin/env python3
"""Analyze what a trained QiField-on-vindex model has learned."""

import argparse
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.qi_field import QiField
from cassi.vindex_weight_dataset import VindexWeightDataset


def _select_device():
    if not torch.cuda.is_available():
        return 'cpu'
    n = torch.cuda.device_count()
    if n == 1:
        return 'cuda:0'
    for i in range(n):
        name = torch.cuda.get_device_name(i)
        props = torch.cuda.get_device_properties(i)
        total = props.total_memory / (1024 ** 3)
        if '7900' in name or total > 20:
            return f'cuda:{i}'
    return 'cuda:0'


def file_for_position(pos, scales):
    """Return filename for a byte position in the concatenated stream."""
    offset = 0
    for name, _, _, count in scales:
        if pos < offset + count:
            return name
        offset += count
    return 'past_end'


def build_model_from_args(a, dev):
    """Construct QiField using the hyperparameters stored in the trainer args dict."""
    kwargs = dict(
        N=a['N'], d=a['d'], C=13, V=256,
        K_train=a.get('K_train', 10),
        K_gen=a.get('K_gen', 50),
        self_aware=a.get('self_aware', True),
        ctrl_hidden_dim=a.get('ctrl_hidden_dim', 64),
        ctrl_loss_weight=a.get('ctrl_loss_weight', 0.01),
        max_neurons=a.get('max_neurons', 512),
        span_len=a.get('span_len', 16),
        lambda_pattern_div=a.get('lambda_pattern_div', 0.001),
        lambda_pattern_commit=a.get('lambda_pattern_commit', 0.001),
        lambda_pattern_util=a.get('lambda_pattern_util', 0.01),
        multi_scale_bytes=a.get('multi_scale_bytes', False),
    )
    if kwargs['self_aware']:
        kwargs.update(
            lambda_homeo=a.get('lambda_homeo', 0.1),
            lambda_breath_gating=a.get('lambda_breath_gating', 0.01),
            lambda_smooth=a.get('lambda_smooth', 0.01),
            lambda_balance=a.get('lambda_balance', 0.01),
            lambda_center=a.get('lambda_center', 1e-4),
        )
    return QiField(**kwargs).to(dev)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--vindex-dir', default=None,
                        help='Override vindex dir from checkpoint')
    parser.add_argument('--include-files', default=None,
                        help='Comma-separated list of .bin files to evaluate on')
    parser.add_argument('--bs', type=int, default=32)
    parser.add_argument('--n-batches', type=int, default=50,
                        help='Number of batches to evaluate')
    parser.add_argument('--seed', type=int, default=123)
    args = parser.parse_args()

    DEV = _select_device()
    print(f'Device: {DEV}')

    ckpt = torch.load(args.checkpoint, map_location=DEV, weights_only=True)
    a = ckpt.get('args', {})
    print(f"Checkpoint epoch {ckpt.get('epoch')}, best_val_loss {ckpt.get('best_val_loss')}")

    model = build_model_from_args(a, DEV)
    state = ckpt.get('model', ckpt)
    # Drop transient buffers that are lazily resized during forward.
    for key in list(state.keys()):
        if 'pattern_memory.qi_ema' in key or 'Q_bar_pos' in key:
            del state[key]
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        print('Missing keys:', missing)
    if unexpected:
        print('Unexpected keys:', unexpected)
    model.eval()

    vdir = args.vindex_dir if args.vindex_dir else a.get('vindex_dir')
    include_files = None
    if args.include_files:
        include_files = [f.strip() for f in args.include_files.split(',')]
    sampler = VindexWeightDataset(vdir, window_bytes=a['N'], include_files=include_files)
    rng = np.random.RandomState(args.seed)

    all_ce = []
    all_acc = []
    all_top5_acc = []
    file_ce = {}
    file_counts = {}
    pos_ce = np.zeros(a['N'])
    pos_counts = np.zeros(a['N'])

    span_len = a.get('span_len', 16)
    context_len = max(1, a['N'] - span_len)
    if span_len >= a['N']:
        context_len = a['N'] // 2

    with torch.no_grad():
        for _ in range(args.n_batches):
            x, _, starts = sampler.sample_batch(args.bs, rng=rng)
            x = x[:, :a['N']].to(DEV).long()
            loss, info = model.training_loss(x)
            # Recompute logits manually to get per-token metrics.
            model.reset_state()
            for t in model.transceivers:
                t.reset_state(args.bs, DEV)
            context = x[:, :context_len]
            if context.shape[1] < a['N']:
                pad = torch.zeros(args.bs, a['N'] - context_len, dtype=torch.long, device=DEV)
                context = torch.cat([context, pad], dim=1)
            psi_real, psi_imag = model.embed(context)
            Q_field = model.Q_field.expand(args.bs, -1, -1).clone()
            for _ in range(model.K_train):
                breath = model.breath.step()
                psi_real, psi_imag, Q_field, _ = model.field_step(
                    psi_real, psi_imag, Q_field, breath)
            logits = model.readout_positions(psi_real, psi_imag)[:, context_len:, :]
            target = x[:, context_len:]
            ce = F.cross_entropy(logits.reshape(-1, 256), target.reshape(-1), reduction='none')
            ce = ce.view(args.bs, a['N'] - context_len).cpu().numpy()
            preds = logits.argmax(dim=-1).cpu().numpy()
            target_np = target.cpu().numpy()

            for b in range(args.bs):
                start = int(starts[b])
                for t in range(a['N'] - context_len):
                    pos = start + context_len + t
                    name = file_for_position(pos, sampler._scales)
                    err = ce[b, t]
                    all_ce.append(err)
                    file_ce[name] = file_ce.get(name, 0.0) + err
                    file_counts[name] = file_counts.get(name, 0) + 1
                    pos_ce[context_len + t] += err
                    pos_counts[context_len + t] += 1
                    pred = preds[b, t]
                    true = target_np[b, t]
                    all_acc.append(float(pred == true))
                    top5 = torch.topk(logits[b, t], k=5).indices
                    all_top5_acc.append(float((top5 == true).any()))

    all_ce = np.array(all_ce)
    all_acc = np.array(all_acc)
    all_top5_acc = np.array(all_top5_acc)

    print('\n=== Overall ===')
    print(f'Mean CE: {all_ce.mean():.4f}')
    print(f'Mean accuracy: {all_acc.mean():.4f}')
    print(f'Mean top-5 accuracy: {all_top5_acc.mean():.4f}')
    print(f'Random-guess CE: {np.log(256):.4f}')

    print('\n=== Per-file CE ===')
    for name in sorted(file_counts.keys()):
        mean_ce = file_ce[name] / file_counts[name]
        print(f'{name}: {mean_ce:.4f} ({file_counts[name]:,} tokens)')

    print('\n=== Per-target-position CE ===')
    pos_ce_mean = pos_ce / np.maximum(pos_counts, 1)
    for t in range(context_len, a['N']):
        if pos_counts[t] > 0:
            print(f'  pos {t:3d}: {pos_ce_mean[t]:.4f}')

    print('\n=== Prediction vs target byte distribution ===')
    x, _, _ = sampler.sample_batch(args.bs, rng=rng)
    x = x[:, :a['N']].to(DEV).long()
    model.reset_state()
    with torch.no_grad():
        loss, info = model.training_loss(x)
        model.reset_state()
        for t in model.transceivers:
            t.reset_state(args.bs, DEV)
        context = x[:, :context_len]
        if context.shape[1] < a['N']:
            pad = torch.zeros(args.bs, a['N'] - context_len, dtype=torch.long, device=DEV)
            context = torch.cat([context, pad], dim=1)
        psi_real, psi_imag = model.embed(context)
        Q_field = model.Q_field.expand(args.bs, -1, -1).clone()
        for _ in range(model.K_train):
            breath = model.breath.step()
            psi_real, psi_imag, Q_field, _ = model.field_step(
                psi_real, psi_imag, Q_field, breath)
        logits = model.readout_positions(psi_real, psi_imag)[:, context_len:, :]
    pred_dist = logits.argmax(dim=-1).cpu().numpy().flatten()
    true_dist = x[:, context_len:].cpu().numpy().flatten()
    print(f'Pred mean/std: {pred_dist.mean():.2f} / {pred_dist.std():.2f}')
    print(f'True mean/std: {true_dist.mean():.2f} / {true_dist.std():.2f}')
    print(f'Pred byte range: [{pred_dist.min()}, {pred_dist.max()}]')
    print(f'True byte range: [{true_dist.min()}, {true_dist.max()}]')

    with torch.no_grad():
        probs = F.softmax(logits, dim=-1)
        entropy = -(probs * torch.log(probs + 1e-10)).sum(dim=-1)
    print(f'\nMean prediction entropy: {entropy.mean().item():.4f}')
    print(f'Prediction entropy std: {entropy.std().item():.4f}')


if __name__ == '__main__':
    main()
