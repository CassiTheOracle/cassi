#!/usr/bin/env python3
"""Train MindBrainField — bidirectional QiField (mind) + Spine3D (brain) loop.

Usage:
    python3 experiments/train_mind_brain.py --N 128 --d 128 --epochs 50 --patience 20
"""

import argparse
import os
import time
import math

# Suppress TensorFlow/oneDNN chatter before TensorBoard imports it
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import torch
from torch.utils.tensorboard import SummaryWriter

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Auto-select best GPU: prefer discrete 7900 XTX over APU
def _select_gpu():
    if not torch.cuda.is_available():
        return 'cpu'
    n = torch.cuda.device_count()
    if n == 1:
        return 'cuda:0'
    for i in range(n):
        name = torch.cuda.get_device_name(i)
        if '7900 XTX' in name or '7900XTX' in name:
            return f'cuda:{i}'
    for i in range(n):
        if 'Radeon RX' in torch.cuda.get_device_name(i):
            return f'cuda:{i}'
    return 'cuda:0'
from cassi.mind_brain_field import MindBrainField
from cassi.qi_fluid_optimizer import QiFluidOptimizer
from experiments.train_langevin_text import (
    build_text_loader, sample_train_batch, sample_val_batch,
)


DEV = _select_gpu()


def train():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=50)
    p.add_argument('--bs', type=int, default=64)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--steps-per-epoch', type=int, default=200)
    p.add_argument('--N', type=int, default=128, help='Spatial positions (sequence length)')
    p.add_argument('--d', type=int, default=128, help='Field dimension per position')
    p.add_argument('--K-train', type=int, default=10, help='Refinement steps during training')
    p.add_argument('--K-gen', type=int, default=50, help='Refinement steps during generation')
    p.add_argument('--seq-len', type=int, default=None, help='Deprecated: must equal --N')
    p.add_argument('--text-dir', default='datasets/active')
    p.add_argument('--save-dir', default='checkpoints')
    p.add_argument('--gen-every', type=int, default=1)
    p.add_argument('--gen-len', type=int, default=200)
    p.add_argument('--gen-temp', type=float, default=0.8)
    p.add_argument('--optimizer', default='qifluid', choices=['adamw', 'qifluid'])
    p.add_argument('--patience', type=int, default=20)
    p.add_argument('--logdir', default='logs/tensorboard')
    p.add_argument('--no-tb', action='store_true', help='Disable TensorBoard logging')
    p.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    # MindBrainField-specific args
    p.add_argument('--n-shells', type=int, default=7, help='Number of brain shells')
    p.add_argument('--D-spine', type=int, default=588, help='Total brain dimensions across shells')
    p.add_argument('--nw', type=int, default=96, help='Brain input dimension')
    p.add_argument('--lambda-recon', type=float, default=0.1, help='Reconstruction loss weight')
    p.add_argument('--lambda-balance', type=float, default=0.01,
                   help='Balance regularizer weight for controller actuators. Anchors '
                        'alpha/gamma/rho near 1.0 to prevent brain energy collapse. '
                        'Set 0 to disable. Default 0.01.')
    p.add_argument('--lambda-be', type=float, default=0.1,
                   help='Brain energy regularizer weight. Prevents the optimizer '
                        'from collapsing brain weights to zero when the gate is '
                        'mostly closed. Default 0.1.')
    p.add_argument('--target-be', type=float, default=0.05,
                   help='Target mean brain energy for the regularizer. Calibrated '
                        'to epoch-0 shell-0 energy. Default 0.05.')
    # Performance flags
    p.add_argument('--bf16', dest='bf16', action='store_true', default=True,
                   help='Use bf16 autocast on mind field steps (~1.5x speedup). Default: True.')
    p.add_argument('--no-bf16', dest='bf16', action='store_false',
                   help='Disable bf16 autocast (run in fp32).')
    p.add_argument('--compile', dest='compile', action='store_true', default=False,
                   help='torch.compile predict() and _field_step_transform. Opt-in (ROCm may crash).')
    p.add_argument('--k-train-fast', type=int, default=None,
                   help='Override K_train for speed (e.g., 3). Changes model behavior.')
    p.add_argument('--reset-state', dest='reset_state', action='store_true', default=False,
                   help='Reset persistent IIR/breath/controller state between steps and val samples. '
                        'Default OFF: state persists across batches (the model keeps what it learns).')
    args = p.parse_args()

    if args.seq_len is None:
        args.seq_len = args.N
    elif args.seq_len != args.N:
        raise ValueError(f"--seq-len ({args.seq_len}) must equal --N ({args.N}) for MindBrainField")

    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    # Checkpoint subdirectory for this configuration
    args.save_dir = os.path.join(args.save_dir, f'N{args.N}_d{args.d}_shells{args.n_shells}')
    os.makedirs(args.save_dir, exist_ok=True)

    model = MindBrainField(
        N=args.N, d=args.d, C=13, V=256,
        K_train=args.K_train, K_gen=args.K_gen,
        n_shells=args.n_shells, D_spine=args.D_spine, nw=args.nw,
        lambda_recon=args.lambda_recon, lambda_balance=args.lambda_balance,
        lambda_be=args.lambda_be, target_be=args.target_be,
        use_bf16=args.bf16,
    ).to(DEV)
    if args.k_train_fast is not None:
        model.mind.K_train = args.k_train_fast
        print(f"  Overrode K_train -> {args.k_train_fast}", flush=True)
    if args.compile:
        try:
            model.mind.predict = torch.compile(model.mind.predict, mode='reduce-overhead')
            model.mind._field_step_transform = torch.compile(
                model.mind._field_step_transform, mode='reduce-overhead')
            print("  torch.compile: reduce-overhead mode enabled", flush=True)
        except Exception as e:
            print(f"  torch.compile reduce-overhead failed ({type(e).__name__}: {e}), "
                  f"trying default mode", flush=True)
            try:
                model.mind.predict = torch.compile(model.mind.predict)
                model.mind._field_step_transform = torch.compile(
                    model.mind._field_step_transform)
                print("  torch.compile: default mode enabled", flush=True)
            except Exception as e2:
                print(f"  torch.compile default failed ({type(e2).__name__}: {e2}), "
                      f"continuing without compile", flush=True)
    ckpt_latest = os.path.join(args.save_dir, 'mind_brain_latest.pt')
    ckpt_best = os.path.join(args.save_dir, 'mind_brain_best.pt')

    if args.resume:
        if os.path.exists(ckpt_latest):
            print(f'Resuming from {ckpt_latest}', flush=True)
            ck = torch.load(ckpt_latest, map_location=DEV, weights_only=True)
            model.load_state_dict(ck['model'], strict=False)
            start_ep = ck.get('epoch', -1) + 1
            print(f'  epoch {start_ep}', flush=True)
        else:
            print(f'No checkpoint at {ckpt_latest}, starting fresh', flush=True)
            start_ep = 0
    else:
        start_ep = 0

    n_p = sum(p.numel() for p in model.parameters())
    print(f"Model: MindBrainField N={args.N} d={args.d} shells={args.n_shells} "
          f"D_spine={args.D_spine} nw={args.nw}, params: {n_p:,}", flush=True)

    sampler, total, n_train, n_val, val_off, tr_rng, val_rng = build_text_loader(args.text_dir)
    print(f"Data: {total:,} bytes ({total/1e9:.1f} GB)", flush=True)

    if args.optimizer == 'qifluid':
        opt = QiFluidOptimizer(model.parameters(), lr=args.lr, weight_decay=0.01)
    else:
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)

    # ── TensorBoard logging ──
    if not args.no_tb:
        os.makedirs(args.logdir, exist_ok=True)
        tb_writer = SummaryWriter(log_dir=args.logdir)
        hparams = {k: str(v) for k, v in vars(args).items()}
        hparams['n_params'] = n_p
    else:
        tb_writer = None

    print(f"Optimizer: {args.optimizer} lr={args.lr}, epochs={args.epochs}, "
          f"bs={args.bs}, steps/epoch={args.steps_per_epoch}, "
          f"K_train={args.K_train}, K_gen={args.K_gen}")

    qi_ema = 0.0
    current_lr = args.lr
    best_val_loss = float('inf')
    patience_counter = 0
    prev_val_loss = float('inf')

    for ep in range(start_ep, args.epochs):
        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_ce = 0.0
        val_sigma = 0.0
        ep_Q_mean = 0.0
        ep_Q_max = 0.0
        ep_brain_energy_mean = 0.0
        ep_gate_openness = 0.0
        ep_recon_loss = 0.0
        nan_steps = 0
        param_nan = False

        for step in range(args.steps_per_epoch):
            if args.reset_state:
                model.reset_state()
            x_bytes, _ = sample_train_batch(sampler, args.bs, tr_rng)
            ids = x_bytes[:, :args.N].to(DEV).long()
            opt.zero_grad()
            try:
                loss, info = model.training_loss(ids)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                args.bs = max(4, args.bs // 2)
                print(f"  OOM — reducing batch size to {args.bs} (resetting corrupted state)", flush=True)
                model.reset_state()  # OOM leaves state half-updated; reset to avoid propagation
                continue

            if torch.isnan(loss) or torch.isinf(loss):
                print(f"  !! NaN/inf loss at step {step} — skipping", flush=True)
                nan_steps += 1
                continue

            loss.backward()

            # NaN gradient guard (vectorized)
            grad_nan = False
            if any(torch.isnan(p.grad).any() or torch.isinf(p.grad).any()
                   for p in model.parameters() if p.grad is not None):
                grad_nan = True
            if grad_nan:
                opt.zero_grad()
                nan_steps += 1
                continue

            # Per-chakra transceiver LR scaling by Qi level
            qi_pc = info.get('qi_per_chakra')
            if qi_pc is not None:
                with torch.no_grad():
                    for c in range(model.C):
                        scale = 1.0 + float(qi_pc[c])
                        for p in model.transceivers[c].parameters():
                            if p.grad is not None:
                                p.grad.mul_(scale)
                        # Residual MLP removed per "no classical ML" rule.
                        # The cord replaces it; the loop below is deleted.

            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            opt.step()

            # NaN param guard (vectorized)
            param_nan = any(torch.isnan(p).any() or torch.isinf(p).any()
                           for p in model.parameters())

            if param_nan:
                if os.path.exists(ckpt_latest):
                    print(f"     Restoring from {ckpt_latest}", flush=True)
                    ck = torch.load(ckpt_latest, map_location=DEV, weights_only=True)
                    model.load_state_dict(ck['model'], strict=False)
                    if args.optimizer == 'qifluid':
                        opt = QiFluidOptimizer(model.parameters(), lr=args.lr, weight_decay=0.01)
                    else:
                        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
                    opt.load_state_dict(ck.get('opt_state', {}))
                nan_steps += 1
                break  # restart epoch

            # TensorBoard logging (every 10 steps for speed)
            if tb_writer is not None:
                global_step = ep * args.steps_per_epoch + step
                if ep == 0 or step % 10 == 0:
                    tb_writer.add_scalar('train/loss', info['loss'], global_step)
                    tb_writer.add_scalar('train/ce_loss', info.get('ce_loss', info['loss']), global_step)
                    tb_writer.add_scalar('train/recon_loss', info.get('recon_loss', 0.0), global_step)
                    tb_writer.add_scalar('train/qi_loss', info.get('qi_loss', 0.0), global_step)
                    tb_writer.add_scalar('train/Q_mean', info['Q_mean'], global_step)
                    tb_writer.add_scalar('train/Q_max', info['Q_max'], global_step)
                    tb_writer.add_scalar('train/brain_energy_mean', info.get('brain_energy_mean', 0.0), global_step)
                    tb_writer.add_scalar('train/gate_openness', info.get('gate_openness', 0.0), global_step)
                    tb_writer.add_scalar('train/lr', float(current_lr), global_step)

            ep_loss += info['loss']
            ep_ce += info.get('ce_loss', info['loss'])
            ep_Q_mean += info['Q_mean']
            ep_Q_max = max(ep_Q_max, info['Q_max'])
            ep_brain_energy_mean += info.get('brain_energy_mean', 0.0)
            ep_gate_openness += info.get('gate_openness', 0.0)
            ep_recon_loss += info.get('recon_loss', 0.0)

        # If NaN recovery triggered restart
        if param_nan:
            print(f"     Restarting epoch {ep}", flush=True)
            continue

        eff_steps = max(1, args.steps_per_epoch - nan_steps)
        ep_loss /= eff_steps
        ep_ce /= eff_steps
        ep_Q_mean /= eff_steps
        ep_brain_energy_mean /= eff_steps
        ep_gate_openness /= eff_steps
        ep_recon_loss /= eff_steps

        # Qi-driven learning rate
        if ep < 3 and ep_Q_mean < 0.01:
            lr_factor = 1.0
        else:
            qi_ema = 0.9 * qi_ema + 0.1 * ep_Q_mean
            qi_delta = ep_Q_mean - qi_ema
            lr_factor = max(0.1, min(2.0, 1.0 + 5.0 * qi_delta))
        current_lr = args.lr * lr_factor
        for pg in opt.param_groups:
            pg['lr'] = current_lr

        dt = time.time() - t0

        # Validation
        model.eval()
        model.K_gen = model.K_train  # use training K for fast validation
        val_loss = 0.0
        val_steps = min(20, args.steps_per_epoch // 5)
        with torch.no_grad():
            for _ in range(val_steps):
                if args.reset_state:
                    model.reset_state()
                xv, _ = sample_val_batch(sampler, args.bs, val_off, val_rng)
                ids = xv[:, :args.N].to(DEV).long()
                _, info = model.training_loss(ids)
                val_loss += info['loss']
        val_loss /= max(1, val_steps)
        model.K_gen = args.K_gen  # restore generation K

        # Logging
        nan_str = f" nan={nan_steps}" if nan_steps else ""
        line = (f"[{ep:4d}] loss={ep_loss:.4f} ce={ep_ce:.4f} "
                f"val={val_loss:.4f} Qm={ep_Q_mean:.4f} QM={ep_Q_max:.2f} "
                f"lr={current_lr:.2e} dt={dt:.1f}s{nan_str}")
        print(line, flush=True)

        # MindBrainField-specific diagnostics
        brain_energy_str = ' '.join(f'e{c}={v:.3f}' for c, v in enumerate(info['brain_energy']))
        print(f"        brain_energy: {brain_energy_str}", flush=True)
        print(f"        gate: {info.get('gate_openness', 0.0):.4f}  "
              f"brain_Q={info.get('brain_energy_mean', 0.0):.4f}  "
              f"recon={ep_recon_loss:.4f}", flush=True)
        print(f"        ctrl: alpha={info.get('ctrl_alpha', 1.0):.3f} "
              f"gamma={info.get('ctrl_gamma', 1.0):.3f} "
              f"rho={info.get('ctrl_rho', 1.0):.3f}", flush=True)

        if tb_writer is not None:
            tb_writer.add_scalar('epoch/val_loss', val_loss, ep)
            tb_writer.add_scalar('epoch/train_ce', ep_ce, ep)
            tb_writer.add_scalar('epoch/Q_mean', ep_Q_mean, ep)
            tb_writer.add_scalar('epoch/brain_energy_mean', ep_brain_energy_mean, ep)
            tb_writer.add_scalar('epoch/gate_openness', ep_gate_openness, ep)
            tb_writer.add_scalar('epoch/recon_loss', ep_recon_loss, ep)
            tb_writer.add_scalar('epoch/lr', float(current_lr), ep)
            # Per-shell brain energy
            for c in range(args.n_shells):
                tb_writer.add_scalar(f'brain/energy_{c:02d}', info['brain_energy'][c], ep)
            # Histograms every 5 epochs
            if ep % 5 == 0:
                total_norm = 0.0
                for p in model.parameters():
                    if p.grad is not None:
                        total_norm += p.grad.norm().item() ** 2
                tb_writer.add_scalar('grad/total_norm', total_norm ** 0.5, ep)
            if args.optimizer == 'qifluid':
                qo = opt.qi_stats()
                tb_writer.add_scalar('epoch/opt_Q', qo['Q_mean'], ep)
        if args.optimizer == 'qifluid':
            qo = opt.qi_stats()
            print(f"        opt_Q={qo['Q_mean']:.6f} max={qo['Q_max']:.6f}", flush=True)

        # Validation-based patience
        delta = prev_val_loss - val_loss
        prev_val_loss = val_loss
        if delta > 0.0005 or val_loss < best_val_loss - 0.001:
            patience_counter = 0
        else:
            patience_counter += 1

        # Best checkpoint
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save({
                'model': model.state_dict(),
                'opt_state': opt.state_dict(),
                'epoch': ep,
                'val_loss': val_loss,
            }, ckpt_best)

        # Rolling checkpoint for NaN recovery
        torch.save({
            'model': model.state_dict(),
            'opt_state': opt.state_dict(),
            'epoch': ep,
            'val_loss': val_loss,
        }, ckpt_latest)

        # Generate
        if ep % args.gen_every == 0:
            if args.reset_state:
                model.reset_state()
            with torch.no_grad():
                tokens = model.generate(seq_len=args.gen_len, temp=args.gen_temp)
            text = bytes([b for b in tokens if 32 <= b < 127]).decode('ascii', errors='replace')
            print(f"  gen: {text[:120]}", flush=True)
            if tb_writer is not None:
                tb_writer.add_text('generation', text[:500], ep)

        if patience_counter >= args.patience:
            print(f"Early stop at epoch {ep} (patience={patience_counter})", flush=True)
            break

    torch.autograd.set_detect_anomaly(False)
    if tb_writer is not None:
        tb_writer.add_hparams(
            {k: str(v) for k, v in vars(args).items()},
            {'hparam/best_val_loss': best_val_loss, 'hparam/final_epoch': ep},
        )
        tb_writer.close()
    print(f"\nDone! Best val loss={best_val_loss:.4f}", flush=True)


if __name__ == '__main__':
    train()
