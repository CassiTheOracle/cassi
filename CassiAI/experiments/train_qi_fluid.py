#!/usr/bin/env python3
"""Train QiField — spatially-extended byte-level field via diffusion.

Usage:
    python3 experiments/train_qi_fluid.py --N 128 --d 128 --epochs 50 --patience 20
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
from cassi.qi_field import QiField
from cassi.qi_fluid_optimizer import QiFluidOptimizer
from experiments.train_langevin_text import (
    build_text_loader, sample_train_batch, sample_val_batch,
)


DEV = _select_gpu()


def train():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=50)
    p.add_argument('--bs', type=int, default=32)
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
    args = p.parse_args()

    if args.seq_len is None:
        args.seq_len = args.N
    elif args.seq_len != args.N:
        raise ValueError(f"--seq-len ({args.seq_len}) must equal --N ({args.N}) for QiField")

    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    args.save_dir = os.path.join(args.save_dir, f'N{args.N}_d{args.d}')
    os.makedirs(args.save_dir, exist_ok=True)

    dev_idx = int(DEV.split(':')[1]) if DEV != 'cpu' and ':' in DEV else 0
    print(f"GPU: device {dev_idx} ({torch.cuda.get_device_name(dev_idx)}, "
          f"{torch.cuda.get_device_properties(dev_idx).total_memory/1e9:.1f}GB)")

    model = QiField(
        N=args.N, d=args.d, C=13, V=256,
        K_train=args.K_train, K_gen=args.K_gen,
    ).to(DEV)
    ckpt_latest = os.path.join(args.save_dir, 'qi_field_latest.pt')
    ckpt_best = os.path.join(args.save_dir, 'qi_field_best.pt')

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
    print(f"Model: QiField N={args.N} d={args.d} (13 chakras), params: {n_p:,}", flush=True)

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

    # Anomaly detection for first 3 epochs (catches NaN early)
    # Anomaly detection disabled to save memory (K-step unrolled graph is large)
    # torch.autograd.set_detect_anomaly(True)
    pass

    for ep in range(start_ep, args.epochs):
        # if start_ep == 0 and ep == 3:
        #     torch.autograd.set_detect_anomaly(False)
        pass

        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_ce = 0.0
        val_sigma = 0.0
        ep_Q_mean = 0.0
        ep_Q_max = 0.0
        ep_sigma = 0.0
        ep_psi_sat = 0.0
        ep_Q_clip = 0.0
        ep_Qt_clip = 0.0
        ep_Q_max_raw = 0.0
        nan_steps = 0
        param_nan = False

        for step in range(args.steps_per_epoch):
            model.reset_state()
            x_bytes, _ = sample_train_batch(sampler, args.bs, tr_rng)
            ids = x_bytes[:, :args.N].to(DEV).long()
            opt.zero_grad()
            loss, info = model.training_loss(ids)

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

            # Per-chakra predictor LR scaling by Qi level
            qi_pc = info.get('qi_per_chakra')
            if qi_pc is not None:
                with torch.no_grad():
                    for c in range(model.C):
                        scale = 1.0 + float(qi_pc[c])
                        for p in model.predictors[c].parameters():
                            if p.grad is not None:
                                p.grad.mul_(scale)

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
                    tb_writer.add_scalar('train/qi_loss', info.get('qi_loss', 0.0), global_step)
                    tb_writer.add_scalar('train/Q_mean', info['Q_mean'], global_step)
                    tb_writer.add_scalar('train/Q_max', info['Q_max'], global_step)
                    tb_writer.add_scalar('train/lr', float(current_lr), global_step)
                    tb_writer.add_scalar('clamp/psi_saturated', info.get('psi_saturated', 0.0), global_step)
                    tb_writer.add_scalar('clamp/Q_clipped', info.get('Q_clipped', 0.0), global_step)
                    tb_writer.add_scalar('clamp/Q_transport_clipped', info.get('Q_transport_clipped', 0.0), global_step)
                    tb_writer.add_scalar('clamp/Q_max_raw', info.get('Q_max_raw', info['Q_max']), global_step)

            ep_loss += info['loss']
            ep_ce += info.get('ce_loss', info['loss'])
            ep_Q_mean += info['Q_mean']
            ep_Q_max = max(ep_Q_max, info['Q_max'])
            ep_sigma += info.get('sigma', 0.0)
            ep_psi_sat = max(ep_psi_sat, info.get('psi_saturated', 0.0))
            ep_Q_clip = max(ep_Q_clip, info.get('Q_clipped', 0.0))
            ep_Qt_clip = max(ep_Qt_clip, info.get('Q_transport_clipped', 0.0))
            ep_Q_max_raw = max(ep_Q_max_raw, info.get('Q_max_raw', 0.0))
        # If NaN recovery triggered restart
        if param_nan:
            print(f"     Restarting epoch {ep}", flush=True)
            continue

        eff_steps = max(1, args.steps_per_epoch - nan_steps)
        ep_loss /= eff_steps
        ep_ce /= eff_steps
        ep_Q_mean /= eff_steps

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
                model.reset_state()
                xv, _ = sample_val_batch(sampler, args.bs, val_off, val_rng)
                ids = xv[:, :args.N].to(DEV).long()
                _, info = model.training_loss(ids)
                val_loss += info['loss']
                val_sigma += info.get('sigma', 0.0)
        val_loss /= max(1, val_steps)
        model.K_gen = args.K_gen  # restore generation K

        # Logging
        nan_str = f" nan={nan_steps}" if nan_steps else ""
        line = (f"[{ep:4d}] loss={ep_loss:.4f} ce={ep_ce:.4f} "
                f"val={val_loss:.4f} Qm={ep_Q_mean:.4f} QM={ep_Q_max:.2f} "
                f"lr={current_lr:.2e} dt={dt:.1f}s{nan_str}")
        print(line, flush=True)
        train_sigma_avg = ep_sigma / eff_steps if ep_sigma else 0.0
        val_sigma_avg = val_sigma / val_steps if val_sigma else 0.0
        print(f"  sigma_avg: train={train_sigma_avg:.3f} val={val_sigma_avg:.3f}", flush=True)

        harmony_str = ' '.join(f'h{c}={v:.3f}' for c, v in enumerate(info['harmony']))
        print(f"        harmony: {harmony_str}", flush=True)
        qi_state = model.qi_state(info['qi_per_chakra'])
        print(f"        qi_state: {qi_state}", flush=True)
        clamp_sat = (ep_psi_sat > 0) or (ep_Q_clip > 0) or (ep_Qt_clip > 0) or (ep_Q_max_raw > ep_Q_max)
        if clamp_sat:
            print(f"        clamp: psi_saturated={ep_psi_sat:.4f} Q_clipped={ep_Q_clip:.4f} "
                  f"Q_transport_clipped={ep_Qt_clip:.4f} Q_max_raw={ep_Q_max_raw:.2f}", flush=True)
        if tb_writer is not None:
            tb_writer.add_scalar('epoch/val_loss', val_loss, ep)
            tb_writer.add_scalar('epoch/train_ce', ep_ce, ep)
            tb_writer.add_scalar('epoch/Q_mean', ep_Q_mean, ep)
            tb_writer.add_scalar('epoch/lr', float(current_lr), ep)
            # Per-chakra harmony
            for c in range(model.C):
                tb_writer.add_scalar(f'chakra/harmony_{c:02d}', info['harmony'][c], ep)
            # Histograms every 5 epochs
            if ep % 5 == 0:
                tb_writer.add_histogram('params/harmony', torch.tensor(info['harmony']), ep)
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
