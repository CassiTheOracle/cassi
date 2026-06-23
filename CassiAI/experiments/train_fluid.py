#!/usr/bin/env python3
"""Train FluidCord (PDE-based neural field) on byte-sequence prediction.

Usage:
    python3 experiments/train_fluid.py --d 128 --epochs 50 --bs 16

Simplified trainer for Phase 1: single-window, no streaming, AdamW.
"""

import argparse
import os
import sys
import time

os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("HSA_ENABLE_SDMA", "0")
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
os.environ.setdefault('ABSL_MIN_LOG_LEVEL', '2')

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cassi.fluid_cord import FluidCord
from cassi.fluid_optimizer import FluidLRScheduler
from experiments.train_langevin_text import (
    build_text_loader,
    sample_train_batch,
    sample_val_batch,
)


# ════════════════════════════════════════════════
#  GPU Selection
# ════════════════════════════════════════════════

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
        return "cpu"
    return _select_gpu()


# ════════════════════════════════════════════════
#  Main
# ════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Train FluidCord (PDE-based neural field) on text.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--N", type=int, default=128, help="window size")
    parser.add_argument("--d", type=int, default=128, help="field dimension")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--bs", type=int, default=16, help="batch size")
    parser.add_argument("--lr", type=float, default=None,
                        help="fixed LR override (default: Qi-driven scheduler)")
    parser.add_argument("--steps-per-epoch", type=int, default=200)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--T", type=float, default=1.0, help="PDE integration time")
    parser.add_argument("--dt", type=float, default=0.2, help="PDE time step")
    parser.add_argument("--gen-every", type=int, default=1,
                        help="generate every N epochs (0=disabled)")
    parser.add_argument("--gen-len", type=int, default=64)
    parser.add_argument("--gen-temp", type=float, default=0.8)
    parser.add_argument("--gen-k-iter", type=int, default=None,
                        help="self-consistency iterations (default: max_new//4)")
    parser.add_argument("--gen-top-p", type=float, default=0.9,
                        help="nucleus sampling threshold for final output (1.0=disabled)")
    parser.add_argument("--no-tb", action="store_true")
    parser.add_argument("--logdir", type=str, default="logs/tensorboard_fluid")
    parser.add_argument("--save-dir", type=str, default=None)
    parser.add_argument("--resume", action="store_true",
                        help="resume from latest checkpoint")
    parser.add_argument("--no-multi-scale-bytes", action="store_true",
                        help="disable multi-scale byte embedding")
    parser.add_argument("--no-phi-qp", action="store_true",
                        help="use standard |ψ|^{1/2} instead of φ-modified QP")
    parser.add_argument("--use-attention", action="store_true",
                        help="add self-attention on ψ.real after PDE integration")
    parser.add_argument("--use-spectral-memory", action="store_true",
                        help="use SpectralMemory (Galerkin projection)")
    parser.add_argument("--lookahead", type=int, default=4,
                        help="multi-token lookahead (K positions predicted per step)")
    args = parser.parse_args()

    if args.save_dir is None:
        args.save_dir = f"checkpoints/N{args.N}_d{args.d}_fluid"
    os.makedirs(args.save_dir, exist_ok=True)

    DEV = _select_device()
    if DEV == "cpu":
        print("GPU: CPU-only")
    else:
        print(f"GPU: {DEV} ({torch.cuda.get_device_name(DEV)})")
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)
    model = FluidCord(
        N=args.N, d=args.d, C=13, V=256, max_batch_size=args.bs,
        scales=(1, 2, 3, 5, 8, 13) if not args.no_multi_scale_bytes else (1,),
        use_phi_qp=not args.no_phi_qp,
        lookahead=args.lookahead,
        use_attention=args.use_attention,
        use_spectral_memory=args.use_spectral_memory,
    ).to(DEV)

    n_p = sum(p.numel() for p in model.parameters())
    print(f"Model: FluidCord N={args.N} d={args.d} ({model.C} chakras)")
    print(f"Params: {n_p:,} total")
    # ── Optimizer ──
    use_scheduler = args.lr is None
    if use_scheduler:
        opt = torch.optim.AdamW(model.parameters())
        scheduler = FluidLRScheduler(opt)
        print("Optimizer: AdamW + FluidLRScheduler (Qi-driven LR)")
    else:
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
        scheduler = None
        print(f"Optimizer: AdamW (fixed lr={args.lr})")

    # ── Checkpoint ──
    ckpt_latest = os.path.join(args.save_dir, "fluid_latest.pt")
    ckpt_best = os.path.join(args.save_dir, "fluid_best.pt")
    start_ep = 0
    best_val_loss = float("inf")
    patience_counter = 0

    if args.resume and os.path.exists(ckpt_latest):
        ckpt = torch.load(ckpt_latest, map_location=DEV, weights_only=True)
        ckpt_model = ckpt.get("model", ckpt)
        missing, unexpected = model.load_state_dict(ckpt_model, strict=False)
        loaded_keys = len(ckpt_model) - len(missing) - len(unexpected)
        total_keys = len(dict(model.state_dict()))
        print(f"Loaded checkpoint: {loaded_keys}/{total_keys} tensors restored")
        if "optimizer" in ckpt:
            try:
                opt.load_state_dict(ckpt["optimizer"])
                print("Loaded optimizer state")
            except (RuntimeError, ValueError):
                print("Using fresh optimizer (incompatible state)")
        if "epoch" in ckpt:
            start_ep = ckpt.get("epoch", 0) + 1
            best_val_loss = ckpt.get("best_val_loss", float("inf"))
        if scheduler is not None and "scheduler" in ckpt:
            scheduler.load_state_dict(ckpt["scheduler"])
            print("Loaded scheduler state")
        patience_counter = 0
    else:
        print("Training from scratch")

    # ── TensorBoard ──
    tb_writer = None
    run_id = time.strftime("%Y%m%d-%H%M%S")
    if not args.no_tb:
        try:
            from torch.utils.tensorboard import SummaryWriter
            tb_writer = SummaryWriter(log_dir=f"{args.logdir}/{run_id}")
        except ImportError:
            print("TensorBoard not available, skipping")

    # ── Data ──
    sampler, total_size, n_train, n_val, val_offset, train_rng, val_rng = \
        build_text_loader("datasets/active", val_frac=0.02)
    print(f"Data: {total_size:,} bytes")

    # ════════════════════════════════════════════════
    #  Training Loop
    # ════════════════════════════════════════════════

    for ep in range(start_ep, start_ep + args.epochs):
        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_ce = 0.0
        ep_grouping = 0.0
        ep_balance = 0.0
        for step in range(args.steps_per_epoch):
            x, _ = sample_train_batch(sampler, args.bs, train_rng)
            x = x[:, :args.N].to(DEV).long()

            opt.zero_grad()
            loss, info = model.training_loss(x, no_reset=False,
                                              T=args.T, dt=args.dt)

            # NaN guard: skip step if loss is NaN/Inf (prevents GPU crashes)
            if torch.isfinite(loss):
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
                if scheduler is not None:
                    scheduler.step()
                opt.step()
            else:
                print(f"  ⚠ NaN loss at step {step}, skipping")

            ep_loss += info["loss"]
            ep_ce += info["ce_loss"]
            ep_grouping += info["grouping_loss"]
            ep_balance += info["chakra_balance"]
        n_steps = args.steps_per_epoch
        ep_loss /= n_steps
        ep_ce /= n_steps
        ep_grouping /= n_steps
        ep_balance /= n_steps
        # ── Validation ──
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for _ in range(20):
                x, _ = sample_val_batch(sampler, args.bs, val_offset, val_rng)
                x = x[:, :args.N].to(DEV).long()
                loss_v, _ = model.training_loss(x, no_reset=False,
                                                 T=args.T, dt=args.dt)
                val_loss += loss_v.item()
        val_loss /= 20

        # ── Generation ──
        if args.gen_every > 0 and ep % args.gen_every == 0:
            model.eval()
            torch.manual_seed(42 + ep * 1000)
            x_bytes, _ = sample_val_batch(sampler, 1, val_offset, val_rng)
            seed = x_bytes[0, :8].to(DEV).long()
            gen = model.generate(seed, max_new=args.gen_len, temp=args.gen_temp,
                                 K_steps=args.gen_k_iter if args.gen_k_iter is not None else 32,
                                 top_p=args.gen_top_p)
            text = "".join(chr(b) if 32 <= b < 127 else "." for b in gen.tolist())
            print(f"--- gen @ epoch {ep}: {text[:64]}", flush=True)
            model.train()

        dt = time.time() - t0
        print(f"ep={ep} train={ep_loss:.4f} ce={ep_ce:.4f} grp={ep_grouping:.5f} "
              f"val={val_loss:.4f} balance={ep_balance:.4f} dt={dt:.1f}s")

        if tb_writer is not None:
            tb_writer.add_scalar("epoch/val_loss", val_loss, ep)
            tb_writer.add_scalar("epoch/train_loss", ep_loss, ep)
            tb_writer.add_scalar("epoch/train_ce", ep_ce, ep)

        # ── Save ──
        ckpt = {
            "epoch": ep,
            "model": model.state_dict(),
            "optimizer": opt.state_dict(),
            "best_val_loss": best_val_loss,
            "patience_counter": patience_counter,
        }
        if scheduler is not None:
            ckpt["scheduler"] = scheduler.state_dict()
        torch.save(ckpt, ckpt_latest)
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(ckpt, ckpt_best)
            patience_counter = 0
            print(f"  ✓ new best: {best_val_loss:.4f}")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f"Early stop after {ep} epochs (best={best_val_loss:.4f})")
                break

    if tb_writer is not None:
        tb_writer.close()
    print("Done.")


if __name__ == "__main__":
    main()
