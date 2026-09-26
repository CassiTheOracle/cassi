#!/usr/bin/env python3
"""Train QiField on transformer weights from a LARQL vindex.

Usage:
    python3 experiments/train_qi_field_on_vindex.py \
        --vindex-dir ~/.cassicore/models/gemma4-26b-a4b-full.vindex \
        --N 128 --d 128 --bs 32 --steps-per-epoch 200 --epochs 50
"""

import argparse
import os
import sys
import time

import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.qi_field import QiField
from cassi.qi_fluid_optimizer import QiFluidOptimizer
from cassi.vindex_weight_dataset import (
    build_vindex_loader, sample_train_batch, sample_val_batch,
)


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


def _display_tokens(tokens, max_width=None):
    """Convert byte token IDs to a printable string for terminal display."""
    if max_width is None:
        try:
            max_width = os.get_terminal_size().columns
        except OSError:
            max_width = 120
    chars = []
    for t in tokens:
        if 32 <= t <= 126:
            chars.append(chr(t))
        else:
            chars.append('.')
    s = ''.join(chars)
    if len(s) > max_width:
        s = s[:max(max_width - 3, 0)] + '...'
    return s


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vindex-dir', type=str, required=True,
                        help='Path to a LARQL .vindex directory')
    parser.add_argument('--val-frac', type=float, default=0.02,
                        help='Fraction of the quantized weight stream held out for validation')
    parser.add_argument('--include-files', type=str, default=None,
                        help='Comma-separated list of .bin files to ingest (default: all)')
    parser.add_argument('--reset', action='store_true',
                        help='Reset field state every batch (default: accumulate)')
    parser.add_argument('--model', type=str, default='qifield', choices=list(MODELS.keys()))
    parser.add_argument('--N', type=int, default=128)
    parser.add_argument('--d', type=int, default=128)
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--patience', type=int, default=50)
    parser.add_argument('--bs', type=int, default=32)
    parser.add_argument('--steps-per-epoch', type=int, default=200)
    parser.add_argument('--lr', type=float, default=3e-4)
    parser.add_argument('--optimizer', type=str, default='qifluid', choices=['qifluid', 'adamw'])
    parser.add_argument('--K-train', type=int, default=10)
    parser.add_argument('--K-gen', type=int, default=50)
    parser.add_argument('--no-self-aware', action='store_true',
                        help='Disable self-awareness controller (default: enabled)')
    parser.add_argument('--ctrl-hidden-dim', type=int, default=64,
                        help='Controller hidden dimension')
    parser.add_argument('--ctrl-loss-weight', type=float, default=0.01,
                        help='Global weight for controller auxiliary losses')
    parser.add_argument('--ctrl-lr-scale', type=float, default=0.1,
                        help='LR scale for controller parameters')
    parser.add_argument('--lambda-homeo', type=float, default=0.1,
                        help='Homeostasis loss weight')
    parser.add_argument('--lambda-breath-gating', type=float, default=0.01,
                        help='Breath-gating loss weight')
    parser.add_argument('--lambda-smooth', type=float, default=0.01,
                        help='Controller smoothness loss weight')
    parser.add_argument('--lambda-balance', type=float, default=0.01,
                        help='Chakra balance loss weight')
    parser.add_argument('--lambda-center', type=float, default=1e-4,
                        help='Controller center prior weight')
    parser.add_argument('--no-tb', action='store_true')
    parser.add_argument('--logdir', type=str, default=None)
    parser.add_argument('--save-dir', type=str, default=None)
    parser.add_argument('--gen-every', type=int, default=10,
                        help='Generate samples every N epochs; 0 disables generation')
    parser.add_argument('--gen-len', type=int, default=128,
                        help='Length of generated sequence in tokens')
    parser.add_argument('--gen-temp', type=float, default=0.8,
                        help='Sampling temperature for generation')
    parser.add_argument('--gen-seeds', type=int, default=2,
                        help='Number of independent samples to generate per epoch')
    parser.add_argument('--max-neurons', type=int, default=512,
                        help='Maximum pattern-neuron slots')
    parser.add_argument('--span-len', type=int, default=16,
                        help='Suffix continuation length during training')
    parser.add_argument('--lambda-pattern-div', type=float, default=0.001,
                        help='Pattern diversity loss weight')
    parser.add_argument('--lambda-pattern-commit', type=float, default=0.001,
                        help='Pattern commitment loss weight')
    parser.add_argument('--lambda-pattern-util', type=float, default=0.01,
                        help='Pattern utilization loss weight')
    parser.add_argument('--repetition-penalty', type=float, default=1.2,
                        help='Repetition penalty for generation')
    parser.add_argument('--multi-scale-bytes', action='store_true',
                        help='Enable multi-scale byte embedder')
    parser.add_argument('--gen-top-k', type=int, default=0,
                        help='Top-k filtering during generation (0 = off)')
    parser.add_argument('--gen-ngram-block', type=int, default=0,
                        help='N-gram block size during generation (0 = off)')
    args = parser.parse_args()
    args.self_aware = not args.no_self_aware

    if args.save_dir is None:
        model_name = os.path.basename(os.path.normpath(args.vindex_dir)).replace('.vindex', '')
        args.save_dir = f'checkpoints/vindex-{model_name}/N{args.N}_d{args.d}_{args.model}_v1'
    if args.logdir is None:
        args.logdir = f'logs/tensorboard_vindex'
    os.makedirs(args.save_dir, exist_ok=True)

    DEV = _select_device()
    if DEV == 'cpu':
        print(f'GPU: CPU-only mode')
    else:
        print(f'GPU: device {DEV.split(":")[-1]} ({torch.cuda.get_device_name(int(DEV.split(":")[-1]))})')
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    ModelCls = MODELS[args.model]
    model_kwargs = dict(N=args.N, d=args.d, C=13, V=256,
                        K_train=args.K_train, K_gen=args.K_gen,
                        self_aware=args.self_aware,
                        ctrl_hidden_dim=args.ctrl_hidden_dim,
                        ctrl_loss_weight=args.ctrl_loss_weight,
                        max_neurons=args.max_neurons,
                        span_len=args.span_len,
                        lambda_pattern_div=args.lambda_pattern_div,
                        lambda_pattern_commit=args.lambda_pattern_commit,
                        lambda_pattern_util=args.lambda_pattern_util,
                        multi_scale_bytes=args.multi_scale_bytes)
    if args.self_aware:
        model_kwargs.update(
            lambda_homeo=args.lambda_homeo,
            lambda_breath_gating=args.lambda_breath_gating,
            lambda_smooth=args.lambda_smooth,
            lambda_balance=args.lambda_balance,
            lambda_center=args.lambda_center,
        )
    model = ModelCls(**model_kwargs).to(DEV)

    n_p = sum(p.numel() for p in model.parameters())
    print(f'Model: {ModelCls.__name__} N={args.N} d={args.d} ({model.C} chakras), params: {n_p:,}')

    if args.optimizer == 'qifluid':
        opt = QiFluidOptimizer(model.parameters(), lr=args.lr)
    elif args.optimizer == 'adamw':
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    else:
        raise ValueError(f'Unsupported optimizer: {args.optimizer}')
    ckpt_latest = os.path.join(args.save_dir, f'{args.model}_latest.pt')
    ckpt_best = os.path.join(args.save_dir, f'{args.model}_best.pt')
    start_ep = 0
    best_val_loss = float('inf')
    patience_counter = 0

    if os.path.exists(ckpt_latest):
        ckpt = torch.load(ckpt_latest, map_location=DEV, weights_only=True)
        ckpt_model = ckpt.get('model', ckpt)
        try:
            missing, unexpected = model.load_state_dict(ckpt_model)
            print(f'Loaded checkpoint from {ckpt_latest}')
        except RuntimeError as e:
            print(f'Checkpoint conversion failed: {e}')
            print('Starting training from scratch.')
            start_ep = 0
            best_val_loss = float('inf')
            patience_counter = 0

        if 'optimizer' in ckpt:
            try:
                opt.load_state_dict(ckpt['optimizer'])
                print('Loaded optimizer state.')
            except (RuntimeError, ValueError) as e:
                print(f'Optimizer state incompatible: {e}')
                print('Using freshly initialized optimizer.')

        if 'epoch' in ckpt and start_ep == 0:
            start_ep = ckpt.get('epoch', 0) + 1
            best_val_loss = ckpt.get('best_val_loss', float('inf'))
            patience_counter = ckpt.get('patience_counter', 0)
    tb_writer = None
    run_id = time.strftime('%Y%m%d-%H%M%S')
    if not args.no_tb:
        tb_writer = SummaryWriter(log_dir=f'{args.logdir}/{run_id}')

    include_files = None
    if args.include_files:
        include_files = [f.strip() for f in args.include_files.split(',')]
    sampler, total_size, n_train, n_val, val_offset, train_rng, val_rng = build_vindex_loader(
        args.vindex_dir, val_frac=args.val_frac, window_bytes=args.N, stride=args.N // 2,
        include_files=include_files)
    print(f'Data: {total_size:,} bytes ({n_train:,} train, {n_val:,} val)')

    prev_val_loss = float('inf')
    for ep in range(start_ep, args.epochs):
        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_ce = 0.0
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
            x_bytes, _ = sample_train_batch(sampler, args.bs, train_rng)
            x = x_bytes[:, :args.N].to(DEV).long()
            opt.zero_grad()
            loss, info = model.training_loss(x, no_reset=not args.reset)

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

            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)

            # Scale controller gradients independently
            if args.self_aware and model.controller is not None:
                for p in model.controller.parameters():
                    if p.grad is not None:
                        p.grad.mul_(args.ctrl_lr_scale)

            opt.step()

            ep_loss += info['loss']
            ep_ce += info['ce_loss']
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
        ep_ce /= eff_steps
        ep_Q_mean /= eff_steps
        ep_pm_active /= eff_steps
        ep_pm_born_ratio /= eff_steps
        if args.self_aware:
            ep_ctrl_aux /= eff_steps
            ep_ctrl_alpha /= eff_steps
            ep_ctrl_beta /= eff_steps
            ep_ctrl_delta /= eff_steps
        model.eval()
        model.reset_state()
        val_loss = 0.0
        with torch.no_grad():
            for _ in range(20):
                x_bytes, _ = sample_val_batch(sampler, args.bs, val_offset, val_rng)
                x = x_bytes[:, :args.N].to(DEV).long()
                loss, info = model.training_loss(x)
                val_loss += loss.item()
        val_loss /= 20

        # Periodic generation sampling
        if args.gen_every > 0 and ep % args.gen_every == 0:
            model.eval()
            model.reset_state()
            print(f'--- generation @ epoch {ep} ---', flush=True)
            gen_texts = []
            for seed_idx in range(args.gen_seeds):
                torch.manual_seed(42 + ep * 1000 + seed_idx)
                x_bytes, _ = sample_val_batch(sampler, 1, val_offset, val_rng)
                seed = x_bytes[0, :8].to(DEV).long()
                sample = model.generate_autoregressive(
                    seed, max_new=args.gen_len, temp=args.gen_temp,
                    repetition_penalty=args.repetition_penalty,
                    top_k=args.gen_top_k if args.gen_top_k > 0 else None,
                    ngram_block_size=args.gen_ngram_block)
                gen_texts.append(_display_tokens(sample.cpu().tolist()))
            for txt in gen_texts:
                print(txt, flush=True)
            model.train()
        extra = ''
        if args.self_aware:
            extra = (f' ctrl_aux={ep_ctrl_aux:.4f} alpha={ep_ctrl_alpha:.3f} '
                     f'beta={ep_ctrl_beta:.3f} delta={ep_ctrl_delta:.3f}')
        dt = time.time() - t0
        print(f'ep={ep} train={ep_loss:.4f} ce={ep_ce:.4f} val={val_loss:.4f} '
              f'Q={ep_Q_mean:.4f} pm_active={ep_pm_active:.1f} '
              f'pm_born_ratio={ep_pm_born_ratio:.3f} '
              f'pm_new={ep_pm_new_neurons:.1f} pm_dissolved={ep_pm_dissolved:.1f}{extra} '
              f'lr={opt.param_groups[0]["lr"]:.6f} dt={dt:.1f}s')
        if tb_writer is not None:
            tb_writer.add_scalar('epoch/val_loss', val_loss, ep)
            tb_writer.add_scalar('epoch/train_ce', ep_ce, ep)
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

    # Mitigate ROCm/PyTorch shutdown segfaults by synchronizing the device
    # and releasing cached allocations before Python finalization.
    if torch.cuda.is_available():
        try:
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
        except Exception:
            pass


if __name__ == '__main__':
    main()
