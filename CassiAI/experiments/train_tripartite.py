#!/usr/bin/env python3
"""TripartiteCord trainer — unified Cord↔Brain↔Mind architecture.

Usage:
    python3 experiments/train_tripartite.py --N 128 --d 128 --epochs 50
"""

import argparse
import os
import sys
import time

# Suppress TensorFlow/absl/oneDNN noise from torch.utils.tensorboard
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')       # 0=all 1=info 2=warn 3=error
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')      # deterministic path
os.environ.setdefault('ABSL_MIN_LOG_LEVEL', '2')         # supress absl "log before init"
import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.tripartite_cord import TripartiteCord
from cassi.qi_fluid_optimizer import QiFluidOptimizer
from experiments.train_langevin_text import (
    build_text_loader, sample_train_batch, sample_val_batch,
)


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
    parser.add_argument('--N', type=int, default=128)
    parser.add_argument('--d', type=int, default=128)
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--patience', type=int, default=50)
    parser.add_argument('--bs', type=int, default=32)
    parser.add_argument('--steps-per-epoch', type=int, default=200)
    parser.add_argument('--lr', type=float, default=3e-4)
    parser.add_argument('--optimizer', type=str, default='qifluid',
                        choices=['qifluid', 'adamw'])
    parser.add_argument('--K-train', type=int, default=10)
    parser.add_argument('--K-gen', type=int, default=50)
    # Brain parameters
    parser.add_argument('--brain-shells', type=int, default=7,
                        help='Number of spherical shells in BrainStep')
    parser.add_argument('--brain-D', type=int, default=588,
                        help='Total brain dimensions across shells')
    parser.add_argument('--brain-scale', type=float, default=0.1,
                        help='BrainStep coupling strength')
    # Constraint force stiffnesses
    parser.add_argument('--stiffness-Q', type=float, default=1.0,
                        help='Qi constraint stiffness')
    parser.add_argument('--stiffness-E', type=float, default=1.0,
                        help='Energy constraint stiffness')
    parser.add_argument('--stiffness-B', type=float, default=0.1,
                        help='Balance constraint stiffness')
    parser.add_argument('--noise-scale', type=float, default=0.01,
                        help='Heartbeat perturbation scale')
    # General
    parser.add_argument('--no-tb', action='store_true')
    parser.add_argument('--logdir', type=str, default=None)
    parser.add_argument('--save-dir', type=str, default=None)
    parser.add_argument('--gen-every', type=int, default=10,
                        help='Generate samples every N epochs; 0 disables')
    parser.add_argument('--gen-len', type=int, default=128,
                        help='Length of generated sequence in tokens')
    parser.add_argument('--gen-temp', type=float, default=0.8,
                        help='Sampling temperature for generation')
    parser.add_argument('--gen-seeds', type=int, default=2,
                        help='Number of independent samples to generate')
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
                        help='Top-k filtering during generation (0=off)')
    parser.add_argument('--gen-ngram-block', type=int, default=0,
                        help='N-gram block size during generation (0=off)')
    parser.add_argument('--reset', action='store_true',
                        help='Reset field state every batch (default: accumulate)')
    parser.add_argument('--checkpoint', type=str, default=None,
                        help='Resume from specific checkpoint path')
    args = parser.parse_args()

    if args.save_dir is None:
        args.save_dir = f'checkpoints/N{args.N}_d{args.d}_tripartite_v1'
    if args.logdir is None:
        args.logdir = f'logs/tensorboard_tripartite'
    os.makedirs(args.save_dir, exist_ok=True)

    DEV = _select_device()
    if DEV == 'cpu':
        print(f'GPU: CPU-only mode')
    else:
        print(f'GPU: device {DEV} ({torch.cuda.get_device_name(DEV)})')
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    model = TripartiteCord(
        N=args.N, d=args.d, C=13, V=256,
        K_train=args.K_train, K_gen=args.K_gen,
        brain_shells=args.brain_shells,
        brain_D=args.brain_D,
        brain_scale=args.brain_scale,
        stiffness_Q=args.stiffness_Q,
        stiffness_E=args.stiffness_E,
        stiffness_B=args.stiffness_B,
        noise_scale=args.noise_scale,
        max_neurons=args.max_neurons,
        span_len=args.span_len,
        lambda_pattern_div=args.lambda_pattern_div,
        lambda_pattern_commit=args.lambda_pattern_commit,
        lambda_pattern_util=args.lambda_pattern_util,
        multi_scale_bytes=args.multi_scale_bytes,
    ).to(DEV)

    n_p = sum(p.numel() for p in model.parameters())
    brain_p = sum(p.numel() for p in model.brain.parameters())
    print(f'Model: TripartiteCord N={args.N} d={args.d} ({model.C} chakras, '
          f'{args.brain_shells} brain shells)')
    print(f'Params: {n_p:,} total ({brain_p:,} brain)')

    if args.optimizer == 'qifluid':
        opt = QiFluidOptimizer(model.parameters(), lr=args.lr)
    elif args.optimizer == 'adamw':
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    else:
        raise ValueError(f'Unsupported optimizer: {args.optimizer}')

    ckpt_latest = os.path.join(args.save_dir, 'tripartite_latest.pt')
    ckpt_best = os.path.join(args.save_dir, 'tripartite_best.pt')
    start_ep = 0
    best_val_loss = float('inf')
    patience_counter = 0

    ckpt_path = args.checkpoint or ckpt_latest
    if os.path.exists(ckpt_path):
        ckpt = torch.load(ckpt_path, map_location=DEV, weights_only=True)
        ckpt_model = ckpt.get('model', ckpt)
        try:
            missing, unexpected = model.load_state_dict(ckpt_model)
            print(f'Loaded checkpoint from {ckpt_path}')
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

    sampler, total_size, n_train, n_val, val_offset, train_rng, val_rng = build_text_loader('datasets/active')
    print(f'Data: {total_size:,} bytes')

    prev_val_loss = float('inf')
    for ep in range(start_ep, args.epochs):
        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_ce = 0.0
        ep_Q_mean = 0.0
        ep_psi2_mean = 0.0
        ep_self_reg = 0.0
        ep_lambda_Q = 0.0
        ep_lambda_E = 0.0
        ep_lambda_B = 0.0
        ep_breath_yang = 0.0
        ep_breath_yin = 0.0
        ep_breath_beat = 0.0
        ep_pm_active = 0.0
        ep_pm_born_ratio = 0.0
        ep_pm_new_neurons = 0.0
        ep_pm_dissolved = 0.0
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
            opt.step()

            ep_loss += info['loss']
            ep_ce += info['ce_loss']
            ep_Q_mean += info['Q_mean']
            ep_psi2_mean += info.get('psi2_mean', 0.0)
            ep_self_reg += info.get('self_reg', 0.0)
            ep_lambda_Q += info.get('lambda_Q', 0.0)
            ep_lambda_E += info.get('lambda_E', 0.0)
            ep_lambda_B += info.get('lambda_B', 0.0)
            ep_breath_yang += info.get('breath_yang', 0.0)
            ep_breath_yin += info.get('breath_yin', 0.0)
            ep_breath_beat += info.get('breath_beat', 0.0)
            ep_pm_active += info.get('pm_active', 0.0)
            ep_pm_born_ratio += info.get('pm_born_ratio', 0.0)
            ep_pm_new_neurons += info.get('pm_new_neurons', 0.0)
            ep_pm_dissolved += info.get('pm_dissolved', 0.0)

        eff_steps = max(1, args.steps_per_epoch - nan_steps)
        ep_loss /= eff_steps
        ep_ce /= eff_steps
        ep_Q_mean /= eff_steps
        ep_psi2_mean /= eff_steps
        ep_self_reg /= eff_steps
        ep_lambda_Q /= eff_steps
        ep_lambda_E /= eff_steps
        ep_lambda_B /= eff_steps
        ep_breath_yang /= eff_steps
        ep_breath_yin /= eff_steps
        ep_breath_beat /= eff_steps
        ep_pm_active /= eff_steps
        ep_pm_born_ratio /= eff_steps

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
            for seed_idx in range(args.gen_seeds):
                torch.manual_seed(42 + ep * 1000 + seed_idx)
                x_bytes, _ = sample_val_batch(sampler, 1, val_offset, val_rng)
                seed = x_bytes[0, :8].to(DEV).long()
                sample = model.generate_autoregressive(
                    seed, max_new=args.gen_len, temp=args.gen_temp,
                    repetition_penalty=args.repetition_penalty,
                    top_k=args.gen_top_k if args.gen_top_k > 0 else None,
                    ngram_block_size=args.gen_ngram_block)
                print(_display_tokens(sample.cpu().tolist()), flush=True)
            model.train()

        dt = time.time() - t0
        constraint_str = (f'λ_Q={ep_lambda_Q:.3f} λ_E={ep_lambda_E:.3f} '
                          f'λ_B={ep_lambda_B:.3f}')
        breath_str = f'yang={ep_breath_yang:.3f} yin={ep_breath_yin:.3f} beat={ep_breath_beat:.3f}'
        print(f'ep={ep} train={ep_loss:.4f} ce={ep_ce:.4f} val={val_loss:.4f} '
              f'Q={ep_Q_mean:.4f} ψ²={ep_psi2_mean:.3f} sr={ep_self_reg:.3f} '
              f'{constraint_str} {breath_str} '
              f'pm_active={ep_pm_active:.1f} pm_born={ep_pm_born_ratio:.3f} '
              f'pm_new={ep_pm_new_neurons:.1f} pm_diss={ep_pm_dissolved:.1f} '
              f'lr={opt.param_groups[0]["lr"]:.6f} dt={dt:.1f}s')

        if tb_writer is not None:
            tb_writer.add_scalar('epoch/val_loss', val_loss, ep)
            tb_writer.add_scalar('epoch/train_ce', ep_ce, ep)
            tb_writer.add_scalar('epoch/train_loss', ep_loss, ep)
            tb_writer.add_scalar('epoch/Q_mean', ep_Q_mean, ep)
            tb_writer.add_scalar('epoch/psi2_mean', ep_psi2_mean, ep)
            tb_writer.add_scalar('epoch/self_reg', ep_self_reg, ep)
            tb_writer.add_scalar('epoch/lambda_Q', ep_lambda_Q, ep)
            tb_writer.add_scalar('epoch/lambda_E', ep_lambda_E, ep)
            tb_writer.add_scalar('epoch/lambda_B', ep_lambda_B, ep)
            tb_writer.add_scalar('epoch/breath_yang', ep_breath_yang, ep)
            tb_writer.add_scalar('epoch/breath_yin', ep_breath_yin, ep)
            tb_writer.add_scalar('epoch/breath_beat', ep_breath_beat, ep)
            tb_writer.add_scalar('epoch/pm_active', ep_pm_active, ep)
            tb_writer.add_scalar('epoch/pm_born_ratio', ep_pm_born_ratio, ep)
            tb_writer.add_scalar('epoch/pm_new_neurons', ep_pm_new_neurons, ep)
            tb_writer.add_scalar('epoch/pm_dissolved', ep_pm_dissolved, ep)
            tb_writer.add_scalar('epoch/lr', opt.param_groups[0]['lr'], ep)

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

    # Mitigate ROCm/PyTorch shutdown segfaults
    if torch.cuda.is_available():
        try:
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
        except Exception:
            pass


if __name__ == '__main__':
    main()
