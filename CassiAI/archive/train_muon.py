#!/usr/bin/env python3
"""MuonCord trainer — resonant field architecture.

Usage:
    python3 experiments/train_muon.py --N 128 --d 128 --epochs 50
    python3 experiments/train_muon.py --bidirectional --lambda-backward 0.5
"""

import argparse
import os
import sys
import time

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
os.environ.setdefault('ABSL_MIN_LOG_LEVEL', '2')
import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from muon_cord import MuonCord
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
    if max_width is None:
        try:
            max_width = os.get_terminal_size().columns
        except OSError:
            max_width = 120
    chars = [chr(t) if 32 <= t <= 126 else '.' for t in tokens]
    s = ''.join(chars)
    if len(s) > max_width:
        s = s[:max(max_width - 3, 0)] + '...'
    return s


def main():
    parser = argparse.ArgumentParser(
        description='Train MuonCord resonant field architecture on text.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    # Core model
    parser.add_argument('--N', type=int, default=128, help='sequence length')
    parser.add_argument('--d', type=int, default=128, help='field dimension per position')
    parser.add_argument('--epochs', type=int, default=50, help='training epochs')
    parser.add_argument('--patience', type=int, default=50, help='early stop patience')
    parser.add_argument('--bs', type=int, default=32, help='batch size')
    parser.add_argument('--steps-per-epoch', type=int, default=200, help='batches per epoch')
    parser.add_argument('--lr', type=float, default=3e-4, help='learning rate')
    parser.add_argument('--optimizer', type=str, default='qifluid',
                        choices=['qifluid', 'adamw'], help='optimizer type')
    parser.add_argument('--K-train', type=int, default=3, help='field unroll steps')
    parser.add_argument('--K-gen', type=int, default=50, help='generation unroll steps')
    # Brain
    parser.add_argument('--brain-shells', type=int, default=7, help='brain Tuner shells')
    parser.add_argument('--brain-D', type=int, default=588, help='brain Tuner dimension')
    # Constraint forces
    parser.add_argument('--stiffness-Q', type=float, default=1.0, help='Qi constraint force')
    parser.add_argument('--stiffness-E', type=float, default=1.0, help='energy constraint force')
    parser.add_argument('--stiffness-B', type=float, default=0.1, help='breath constraint force')
    parser.add_argument('--noise-scale', type=float, default=0.01, help='low-Q arousal noise')
    # Bidirectional
    parser.add_argument('--bidirectional', action='store_true',
                        help='bidirectional training (forward+backward)')
    parser.add_argument('--lambda-backward', type=float, default=0.5,
                        help='backward loss weight')
    parser.add_argument('--lambda-consistency', type=float, default=0.1,
                        help='fwd/bwd consistency loss weight')
    # Pattern memory
    parser.add_argument('--max-neurons', type=int, default=512, help='pattern memory cap')
    parser.add_argument('--span-len', type=int, default=16, help='pattern memory span')
    parser.add_argument('--lambda-pattern-div', type=float, default=0.001,
                        help='pattern diversity loss')
    parser.add_argument('--lambda-pattern-commit', type=float, default=0.001,
                        help='pattern commit loss')
    parser.add_argument('--lambda-pattern-util', type=float, default=0.01,
                        help='pattern utilization loss')
    # Word formation
    parser.add_argument('--word-loss-scale', type=float, default=0.0,
                        help='weight for word-formation auxiliary losses (0=disabled)')
    # Masked prediction
    parser.add_argument('--mask-ratio', type=float, default=0.35,
                        help='span mask ratio for masked prediction (0=disabled)')
    parser.add_argument('--mask-prob', type=float, default=0.5,
                        help='probability of any given step using masked prediction')
    # Generation
    parser.add_argument('--gen-every', type=int, default=1,
                        help='generate every N epochs (0 disables)')
    parser.add_argument('--gen-len', type=int, default=128, help='generation length')
    parser.add_argument('--gen-temp', type=float, default=0.8, help='generation temperature')
    parser.add_argument('--gen-seeds', type=int, default=2, help='seeds per gen run')
    parser.add_argument('--repetition-penalty', type=float, default=1.2,
                        help='repetition penalty factor')
    parser.add_argument('--gen-top-k', type=int, default=0,
                        help='top-k sampling (0=disabled)')
    parser.add_argument('--gen-ngram-block', type=int, default=0,
                        help='ngram blocking (0=disabled)')
    # I/O
    parser.add_argument('--no-tb', action='store_true', help='disable TensorBoard')
    parser.add_argument('--logdir', type=str, default=None, help='TensorBoard log dir')
    parser.add_argument('--save-dir', type=str, default=None, help='checkpoint save dir')
    parser.add_argument('--no-reset', action='store_true', help='carry state across batches (stateful RNN mode)')
    parser.add_argument('--checkpoint', type=str, default=None, help='resume from path')
    parser.add_argument('--strict-ckpt', action='store_true',
                        help='error on incompatible checkpoints (default: partial load)')
    parser.add_argument('--multi-scale-bytes', action='store_true',
                        help='use multi-scale byte embedding')
    args = parser.parse_args()

    if args.save_dir is None:
        args.save_dir = f'checkpoints/N{args.N}_d{args.d}_muon'
    if args.logdir is None:
        args.logdir = 'logs/tensorboard_muon'
    os.makedirs(args.save_dir, exist_ok=True)

    DEV = _select_device()
    if DEV == 'cpu':
        print('GPU: CPU-only')
    else:
        print(f'GPU: {DEV} ({torch.cuda.get_device_name(DEV)})')
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    model = MuonCord(
        N=args.N, d=args.d, C=13, V=256,
        K_train=args.K_train, K_gen=args.K_gen,
        brain_shells=args.brain_shells, brain_D=args.brain_D,
        stiffness_Q=args.stiffness_Q, stiffness_E=args.stiffness_E,
        stiffness_B=args.stiffness_B, noise_scale=args.noise_scale,
        bidirectional=args.bidirectional,
        lambda_backward=args.lambda_backward,
        lambda_consistency=args.lambda_consistency,
        max_neurons=args.max_neurons, span_len=args.span_len,
        lambda_pattern_div=args.lambda_pattern_div,
        lambda_pattern_commit=args.lambda_pattern_commit,
        lambda_pattern_util=args.lambda_pattern_util,
        lambda_word=args.word_loss_scale,
        max_batch_size=args.bs,
    ).to(DEV)

    n_p = sum(p.numel() for p in model.parameters())
    print(f'Model: MuonCord N={args.N} d={args.d} ({model.C} chakras, '
          f'{args.brain_shells} brain shells)')
    print(f'Params: {n_p:,} total')
    print(f'Chakra dims: {model.chakra_widths} (sum={sum(model.chakra_widths)})')

    if args.optimizer == 'qifluid':
        opt = QiFluidOptimizer(model.parameters(), lr=args.lr)
    else:
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr)

    ckpt_latest = os.path.join(args.save_dir, 'muon_latest.pt')
    ckpt_best = os.path.join(args.save_dir, 'muon_best.pt')
    start_ep = 0
    best_val_loss = float('inf')
    patience_counter = 0

    ckpt_path = args.checkpoint or ckpt_latest
    loaded_ok = False
    if os.path.exists(ckpt_path):
        ckpt = torch.load(ckpt_path, map_location=DEV, weights_only=True)
        ckpt_model = ckpt.get('model', ckpt)
        if args.strict_ckpt:
            # No partial load allowed — any missing/unexpected is a hard error
            model.load_state_dict(ckpt_model, strict=True)
            print(f'Loaded checkpoint from {ckpt_path} (strict mode)')
            loaded_ok = True
        else:
            missing, unexpected = model.load_state_dict(ckpt_model, strict=False)
            loaded_keys = len(ckpt_model) - len(missing) - len(unexpected)
            total_keys = len(dict(model.state_dict()))
            print(f'Loaded checkpoint from {ckpt_path}: '
                  f'{loaded_keys}/{total_keys} tensors restored')
            if missing:
                print(f'  {len(missing)} tensors reinitialized from defaults')
            if unexpected:
                print(f'  {len(unexpected)} tensors dropped (not in current model)')
            loaded_ok = loaded_keys > 0
        if loaded_ok and 'optimizer' in ckpt:
            try:
                opt.load_state_dict(ckpt['optimizer'])
                print('Loaded optimizer state')
            except (RuntimeError, ValueError):
                print('Using fresh optimizer (incompatible state)')
        if loaded_ok and 'epoch' in ckpt:
            start_ep = ckpt.get('epoch', 0) + 1
            best_val_loss = ckpt.get('best_val_loss', float('inf'))
            # Always reset patience counter — patience counts from THIS run
            patience_counter = 0
    else:
        print(f'No checkpoint found at {ckpt_path}, training from scratch')
    tb_writer = None
    run_id = time.strftime('%Y%m%d-%H%M%S')
    if not args.no_tb:
        tb_writer = SummaryWriter(log_dir=f'{args.logdir}/{run_id}')

    sampler, total_size, n_train, n_val, val_offset, train_rng, val_rng = \
        build_text_loader('datasets/active')
    print(f'Data: {total_size:,} bytes')

    for ep in range(start_ep, start_ep + args.epochs):
        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_ce = 0.0
        ep_Q_mean = 0.0
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

        for step in range(args.steps_per_epoch):
            x, _ = sample_train_batch(sampler, args.bs, train_rng)
            x = x[:, :args.N].to(DEV).long()
            mask_ratio = args.mask_ratio if torch.rand(1).item() < args.mask_prob else 0.0
            opt.zero_grad()
            loss, info = model.training_loss(x, no_reset=args.no_reset,
                                            mask_ratio=mask_ratio)
            # Ensure all scalars in info are Python floats
            for k in list(info.keys()):
                if isinstance(info[k], torch.Tensor) and info[k].numel() == 1:
                    info[k] = info[k].item()
            if torch.isnan(loss) or torch.isinf(loss):
                print(f'  !! NaN at step {step} — skipping')
                continue
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            opt.step()
            ep_loss += info.get('loss', 0.0)
            ep_ce += info.get('ce_loss', 0.0)
            ep_Q_mean += info.get('Q_mean', 0.0)
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

        n = args.steps_per_epoch
        ep_loss /= n
        ep_ce /= n
        ep_Q_mean /= n
        ep_lambda_Q /= n
        ep_lambda_E /= n
        ep_lambda_B /= n
        ep_breath_yang /= n
        ep_breath_yin /= n
        ep_breath_beat /= n
        ep_pm_active /= n
        ep_pm_born_ratio /= n
        ep_pm_new_neurons /= n
        ep_pm_dissolved /= n

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for _ in range(20):
                x, _ = sample_val_batch(sampler, args.bs,
                                        val_offset, val_rng)
                x = x[:, :args.N].to(DEV).long()
                model.reset_iir_state()
                loss_v, _ = model.training_loss(x, no_reset=False)
                val_loss += loss_v.item()
        val_loss /= 20

        # Generation — guarded: ROCm HSA crash on 7900 XTX
        if args.gen_every > 0 and ep % args.gen_every == 0:
            model.eval()
            model.reset_iir_state()
            try:
                print(f'--- generation @ epoch {ep} ---', flush=True)
                for seed_idx in range(args.gen_seeds):
                    torch.manual_seed(42 + ep * 1000 + seed_idx)
                    x_bytes, _ = sample_val_batch(sampler, 1, val_offset, val_rng)
                    seed = x_bytes[0, :8].to(DEV).long()
                    sample = model.generate_parallel(
                        seed, max_len=args.gen_len, temp=args.gen_temp,
                        top_k=args.gen_top_k if args.gen_top_k > 0 else None)
                    print(_display_tokens(sample.cpu().tolist()), flush=True)
            except Exception as e:
                print(f'  !! generation failed (skipping): {e}')
            model.train()

        dt = time.time() - t0
        constraint_str = (f'λ_Q={ep_lambda_Q:.3f} λ_E={ep_lambda_E:.3f} '
                          f'λ_B={ep_lambda_B:.3f}')
        print(f'ep={ep} train={ep_loss:.4f} ce={ep_ce:.4f} val={val_loss:.4f} '
              f'Q={ep_Q_mean:.4f} {constraint_str} '
              f'yang={ep_breath_yang:.3f} yin={ep_breath_yin:.3f} '
              f'pm_active={ep_pm_active:.1f} dt={dt:.1f}s')

        if tb_writer is not None:
            tb_writer.add_scalar('epoch/val_loss', val_loss, ep)
            tb_writer.add_scalar('epoch/train_loss', ep_loss, ep)
            tb_writer.add_scalar('epoch/train_ce', ep_ce, ep)
            tb_writer.add_scalar('epoch/Q_mean', ep_Q_mean, ep)
            tb_writer.add_scalar('epoch/lambda_Q', ep_lambda_Q, ep)

        # Save
        ckpt = {
            'epoch': ep,
            'model': model.state_dict(),
            'optimizer': opt.state_dict(),
            'best_val_loss': best_val_loss,
            'patience_counter': patience_counter,
        }
        torch.save(ckpt, ckpt_latest)
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(ckpt, ckpt_best)
            patience_counter = 0
            print(f'  ✓ new best: {best_val_loss:.4f}')
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f'Early stop after {ep} epochs (best={best_val_loss:.4f})')
                break

    if tb_writer is not None:
        tb_writer.close()
    print('Done.')


if __name__ == '__main__':
    main()
