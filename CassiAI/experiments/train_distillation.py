#!/usr/bin/env python3
"""QiField trainer for function-space distillation of pre-captured layer residuals.

Usage:
    python3 experiments/train_distillation.py --data-dir /path/to/activations --N 10 --d 512 --bs 32
    python3 experiments/train_distillation.py --data-dir /path/to/activations --self-aware
"""

import argparse
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.qi_field import QiField
from cassi.qi_fluid_optimizer import QiFluidOptimizer
from cassi.activation_dataset import ActivationDataset, sample_train_batch, sample_val_batch


MODELS = {
    'qifield': QiField,
}


def _select_gpu():
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


def _select_device():
    if not torch.cuda.is_available():
        return 'cpu'
    return _select_gpu()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=str, required=True,
                        help='Path to activation data directory')
    parser.add_argument('--N', type=int, default=10, help='Context layers (seq_layers)')
    parser.add_argument('--d', type=int, default=512, help='Field dimension')
    parser.add_argument('--bs', type=int, default=32, help='Batch size')
    parser.add_argument('--lr', type=float, default=3e-4, help='Learning rate')
    parser.add_argument('--optimizer', type=str, default='qifluid', choices=['qifluid', 'adamw'])
    parser.add_argument('--K-train', type=int, default=10, help='IIR field steps')
    parser.add_argument('--span-len', type=int, default=4, help='Target prediction span')
    parser.add_argument('--epochs', type=int, default=200)
    parser.add_argument('--steps-per-epoch', type=int, default=200)
    parser.add_argument('--patience', type=int, default=30)
    parser.add_argument('--no-tb', action='store_true')
    parser.add_argument('--reset', action='store_true',
                        help='Reset field state every batch (default: accumulate)')
    parser.add_argument('--gen-every', type=int, default=0,
                        help='Generate rollout every N epochs (disabled for continuous mode)')
    parser.add_argument('--save-dir', type=str, default=None)
    parser.add_argument('--logdir', type=str, default=None)
    parser.add_argument('--self-aware', action='store_true',
                        help='Enable self-awareness controller')
    parser.add_argument('--ctrl-hidden-dim', type=int, default=64)
    parser.add_argument('--ctrl-loss-weight', type=float, default=0.01)
    parser.add_argument('--ctrl-lr-scale', type=float, default=0.1)
    parser.add_argument('--lambda-homeo', type=float, default=0.1)
    parser.add_argument('--lambda-breath-gating', type=float, default=0.01)
    parser.add_argument('--lambda-smooth', type=float, default=0.01)
    parser.add_argument('--lambda-balance', type=float, default=0.01)
    parser.add_argument('--lambda-center', type=float, default=1e-4)
    parser.add_argument('--max-neurons', type=int, default=512)
    parser.add_argument('--lambda-pattern-div', type=float, default=0.001)
    parser.add_argument('--lambda-pattern-commit', type=float, default=0.001)
    parser.add_argument('--lambda-pattern-util', type=float, default=0.01)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()

    if args.save_dir is None:
        args.save_dir = 'checkpoints/distillation-e2b'
    if args.logdir is None:
        args.logdir = 'logs/tensorboard_distillation'
    os.makedirs(args.save_dir, exist_ok=True)

    DEV = _select_device()
    if DEV == 'cpu':
        print('GPU: CPU-only mode')
    else:
        dev_idx = int(DEV.split(':')[-1])
        print(f'GPU: device {dev_idx} ({torch.cuda.get_device_name(dev_idx)})')
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    # ── Data ──
    dataset = ActivationDataset(args.data_dir, seq_layers=args.N)
    hidden_size = dataset.hidden_size
    n_layers = dataset.n_layers
    print(f'Data: {dataset.total_tokens:,} tokens, {n_layers} layers, hidden={hidden_size}')
    train_rng = np.random.RandomState(42)
    val_rng = np.random.RandomState(999)

    # ── Model ──
    model_kwargs = dict(
        N=args.N, d=args.d, C=13, V=256,
        K_train=args.K_train,
        self_aware=args.self_aware,
        ctrl_hidden_dim=args.ctrl_hidden_dim,
        ctrl_loss_weight=args.ctrl_loss_weight,
        max_neurons=args.max_neurons,
        span_len=args.span_len,
        lambda_pattern_div=args.lambda_pattern_div,
        lambda_pattern_commit=args.lambda_pattern_commit,
        lambda_pattern_util=args.lambda_pattern_util,
        input_dim=hidden_size,
        output_dim=hidden_size,
        continuous_mode=True,
        max_batch_size=args.bs,
    )
    if args.self_aware:
        model_kwargs.update(
            lambda_homeo=args.lambda_homeo,
            lambda_breath_gating=args.lambda_breath_gating,
            lambda_smooth=args.lambda_smooth,
            lambda_balance=args.lambda_balance,
            lambda_center=args.lambda_center,
        )
    model = QiField(**model_kwargs).to(DEV)

    n_p = sum(p.numel() for p in model.parameters())
    print(f'Model: QiField N={args.N} d={args.d} ({model.C} chakras), params: {n_p:,}')

    if args.optimizer == 'qifluid':
        opt = QiFluidOptimizer(model.parameters(), lr=args.lr)
    elif args.optimizer == 'adamw':
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    else:
        raise ValueError(f'Unsupported optimizer: {args.optimizer}')

    ckpt_latest = os.path.join(args.save_dir, 'qifield_latest.pt')
    ckpt_best = os.path.join(args.save_dir, 'qifield_best.pt')
    start_ep = 0
    best_val_loss = float('inf')
    patience_counter = 0

    loaded_model = False
    if args.resume and os.path.exists(ckpt_latest):
        ckpt = torch.load(ckpt_latest, map_location=DEV, weights_only=True)
        ckpt_model = ckpt.get('model', ckpt)
        try:
            missing, unexpected = model.load_state_dict(ckpt_model)
            print(f'Loaded checkpoint from {ckpt_latest}')
            loaded_model = True
        except RuntimeError as e:
            print(f'Checkpoint conversion failed: {e}')
            print('Starting training from scratch.')
            start_ep = 0
            best_val_loss = float('inf')
            patience_counter = 0

        if loaded_model:
            if 'optimizer' in ckpt:
                try:
                    opt.load_state_dict(ckpt['optimizer'])
                    print('Loaded optimizer state.')
                except (RuntimeError, ValueError) as e:
                    print(f'Optimizer state incompatible: {e}')
                    print('Using freshly initialized optimizer.')

            if 'epoch' in ckpt:
                start_ep = ckpt.get('epoch', 0) + 1
                best_val_loss = ckpt.get('best_val_loss', float('inf'))
                patience_counter = ckpt.get('patience_counter', 0)
                print(f'Resuming from epoch {start_ep}')

    tb_writer = None
    run_id = time.strftime('%Y%m%d-%H%M%S')
    if not args.no_tb:
        tb_writer = SummaryWriter(log_dir=f'{args.logdir}/{run_id}')

    prev_val_loss = float('inf')
    end_epoch = args.epochs + (start_ep if args.resume else 0)
    for ep in range(start_ep, end_epoch):
        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_mse = 0.0
        ep_mae = 0.0
        ep_Q_mean = 0.0
        ep_pm_active = 0.0
        ep_pm_born_ratio = 0.0
        ep_pm_new_neurons = 0.0
        ep_pm_dissolved = 0.0
        ep_ctrl_aux = 0.0
        ep_ctrl_alpha = 0.0
        ep_ctrl_beta = 0.0
        ep_ctrl_delta = 0.0
        nan_steps = 0

        for step in range(args.steps_per_epoch):
            x, y = sample_train_batch(dataset, args.bs, train_rng)
            x, y = x.to(DEV), y.to(DEV)

            opt.zero_grad()
            loss, info = model.training_loss(x, y, no_reset=not args.reset)

            if torch.isnan(loss) or torch.isinf(loss):
                print(f'  !! NaN/inf loss at step {step} — skipping', flush=True)
                nan_steps += 1
                continue

            loss.backward()

            grad_nan = any(
                torch.isnan(p.grad).any() or torch.isinf(p.grad).any()
                for p in model.parameters() if p.grad is not None
            )
            if grad_nan:
                opt.zero_grad()
                nan_steps += 1
                continue

            if args.self_aware and model.controller is not None:
                for p in model.controller.parameters():
                    if p.grad is not None:
                        p.grad.mul_(args.ctrl_lr_scale)

            opt.step()

            ep_loss += info['loss']
            ep_mse += info['mse_loss']
            ep_mae += info['mae_loss']
            ep_Q_mean += info['Q_mean']
            ep_pm_active += info.get('pm_active', 0.0)
            ep_pm_born_ratio += info.get('pm_born_ratio', 0.0)
            ep_pm_new_neurons += info.get('pm_new_neurons', 0.0)
            ep_pm_dissolved += info.get('pm_dissolved', 0.0)
            if args.self_aware:
                ep_ctrl_aux += info.get('ctrl_aux_loss', 0.0)
                ep_ctrl_alpha += info.get('ctrl_alpha', 0.0)
                ep_ctrl_beta += info.get('ctrl_beta', 0.0)
                ep_ctrl_delta += info.get('ctrl_delta', 0.0)

        eff_steps = max(1, args.steps_per_epoch - nan_steps)
        ep_loss /= eff_steps
        ep_mse /= eff_steps
        ep_mae /= eff_steps
        ep_Q_mean /= eff_steps
        ep_pm_active /= eff_steps
        ep_pm_born_ratio /= eff_steps
        ep_pm_new_neurons /= eff_steps
        ep_pm_dissolved /= eff_steps
        if args.self_aware:
            ep_ctrl_aux /= eff_steps
            ep_ctrl_alpha /= eff_steps
            ep_ctrl_beta /= eff_steps
            ep_ctrl_delta /= eff_steps

        # ── Validation ──
        model.eval()
        val_loss = 0.0
        val_mae = 0.0
        with torch.no_grad():
            for _ in range(20):
                x, y = sample_val_batch(dataset, args.bs, val_rng)
                x, y = x.to(DEV), y.to(DEV)
                loss, info = model.training_loss(x, y)
                val_loss += loss.item()
                val_mae += info['mae_loss']
        val_loss /= 20
        val_mae /= 20

        extra = ''
        if args.self_aware:
            extra = (f' ctrl_aux={ep_ctrl_aux:.4f} alpha={ep_ctrl_alpha:.3f} '
                     f'beta={ep_ctrl_beta:.3f} delta={ep_ctrl_delta:.3f}')
        dt = time.time() - t0
        print(f'ep={ep} train={ep_loss:.4f} mse={ep_mse:.4f} mae={ep_mae:.4f} '
              f'val={val_loss:.4f} val_mae={val_mae:.4f} Q={ep_Q_mean:.4f} '
              f'pm_active={ep_pm_active:.1f} pm_born_ratio={ep_pm_born_ratio:.3f} '
              f'pm_new={ep_pm_new_neurons:.1f} pm_dissolved={ep_pm_dissolved:.1f}{extra} '
              f'lr={opt.param_groups[0]["lr"]:.6f} dt={dt:.1f}s', flush=True)

        if tb_writer is not None:
            tb_writer.add_scalar('epoch/val_loss', val_loss, ep)
            tb_writer.add_scalar('epoch/val_mae', val_mae, ep)
            tb_writer.add_scalar('epoch/train_mse', ep_mse, ep)
            tb_writer.add_scalar('epoch/train_mae', ep_mae, ep)
            tb_writer.add_scalar('epoch/train_loss', ep_loss, ep)
            tb_writer.add_scalar('epoch/Q_mean', ep_Q_mean, ep)
            tb_writer.add_scalar('epoch/pm_active', ep_pm_active, ep)
            tb_writer.add_scalar('epoch/pm_born_ratio', ep_pm_born_ratio, ep)
            tb_writer.add_scalar('epoch/pm_new_neurons', ep_pm_new_neurons, ep)
            tb_writer.add_scalar('epoch/pm_dissolved', ep_pm_dissolved, ep)
            tb_writer.add_scalar('epoch/lr', opt.param_groups[0]['lr'], ep)
            if args.self_aware:
                tb_writer.add_scalar('epoch/ctrl_aux', ep_ctrl_aux, ep)
                tb_writer.add_scalar('epoch/ctrl_alpha', ep_ctrl_alpha, ep)
                tb_writer.add_scalar('epoch/ctrl_beta', ep_ctrl_beta, ep)
                tb_writer.add_scalar('epoch/ctrl_delta', ep_ctrl_delta, ep)

        ckpt = {
            'epoch': ep,
            'model': model.state_dict(),
            'optimizer': opt.state_dict(),
            'best_val_loss': best_val_loss,
            'patience_counter': patience_counter,
            'args': vars(args),
        }
        torch.save(ckpt, ckpt_latest)

        delta = prev_val_loss - val_loss
        prev_val_loss = val_loss
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(ckpt, ckpt_best)
        else:
            patience_counter += 1

        if patience_counter >= args.patience:
            print(f'Early stop at epoch {ep}')
            break

    if tb_writer is not None:
        tb_writer.close()
    print('Done!')

    if torch.cuda.is_available():
        try:
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
        except Exception:
            pass


if __name__ == '__main__':
    main()
