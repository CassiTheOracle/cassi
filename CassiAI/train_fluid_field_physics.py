#!/usr/bin/env python3
"""Train PhysicsFieldModel on physics simulation data.

Usage:
    python3 train_fluid_field_physics.py --d 32 --N 32 --epochs 100
    python3 train_fluid_field_physics.py --d 32 --N 32 --bs 128 --resume

After training, the PDE coefficients can be loaded into FluidCord for
byte-sequence prediction via the --physics-ckpt flag in train_fluid.py.
"""

import argparse
import os
import sys
import time

os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("HSA_ENABLE_SDMA", "0")

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from cassi.physics_field_model import PhysicsFieldModel


# ════════════════════════════════════════════════
#  GPU Selection
# ════════════════════════════════════════════════

def _select_gpu():
    if not torch.cuda.is_available():
        return "cpu"
    n = torch.cuda.device_count()
    if n == 1:
        return "cuda:0"
    for i in range(n):
        name = torch.cuda.get_device_name(i)
        props = torch.cuda.get_device_properties(i)
        total = props.total_memory / (1024 ** 3)
        if "7900" in name or total > 20:
            return f"cuda:{i}"
    return "cuda:0"


def _select_device():
    if not torch.cuda.is_available():
        return "cpu"
    return _select_gpu()


# ════════════════════════════════════════════════
#  Cache loading
# ════════════════════════════════════════════════

def load_cache(cache_path: str):
    """Load physics cache and return train/val splits.

    Returns:
        cache: full cache dict
        train_windows: [N_train, win_len, D]
        val_windows: [N_val, win_len, D]
    """
    cache = torch.load(cache_path, map_location="cpu", weights_only=True)
    windows = cache["windows"]  # [N_total, win_len, D]
    train_idx = cache["train_idx"]
    val_idx = cache["val_idx"]
    train_windows = windows[train_idx]
    val_windows = windows[val_idx]
    print(f"  Train windows: {len(train_windows):,}")
    print(f"  Val windows:   {len(val_windows):,}")
    print(f"  Families:      {cache['family_names']}")
    return cache, train_windows, val_windows


def sample_batch(windows: torch.Tensor, batch_size: int, device: str):
    """Sample a random batch from the cache.

    Returns:
        frames: [batch_size, win_len, D]
    """
    idx = torch.randint(0, len(windows), (batch_size,))
    return windows[idx].to(device)


# ════════════════════════════════════════════════
#  Main
# ════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Train PhysicsFieldModel on physics simulation data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--d", type=int, default=32,
                        help="Latent field dimension")
    parser.add_argument("--N", type=int, default=32,
                        help="Number of spatial positions (window frames)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--bs", type=int, default=64,
                        help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--steps-per-epoch", type=int, default=200,
                        help="Training batches per epoch")
    parser.add_argument("--val-steps", type=int, default=20,
                        help="Validation batches per epoch")
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--T", type=float, default=1.0,
                        help="PDE integration time")
    parser.add_argument("--dt", type=float, default=0.2,
                        help="PDE time step")
    parser.add_argument("--cache", type=str, default="datasets/physics_cache.pt",
                        help="Physics cache path")
    parser.add_argument("--save-dir", type=str, default=None)
    parser.add_argument("--resume", action="store_true",
                        help="Resume from latest checkpoint")
    parser.add_argument("--no-tb", action="store_true",
                        help="Disable TensorBoard")
    parser.add_argument("--logdir", type=str, default="logs/tensorboard_physics")
    parser.add_argument("--gen-every", type=int, default=10,
                        help="Run rollout eval every N epochs (0=disabled)")
    parser.add_argument("--gen-steps", type=int, default=20,
                        help="Rollout steps during eval")
    parser.add_argument("--mse-weight", type=float, default=1.0)
    parser.add_argument("--spectral-weight", type=float, default=0.1)
    args = parser.parse_args()

    if args.save_dir is None:
        args.save_dir = f"checkpoints/physics_d{args.d}_N{args.N}"
    os.makedirs(args.save_dir, exist_ok=True)

    # ── Device ──
    DEV = _select_device()
    if DEV == "cpu":
        print("GPU: CPU-only")
    else:
        print(f"GPU: {DEV} ({torch.cuda.get_device_name(DEV)})")
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    # ── Data ──
    print(f"Loading cache from {args.cache}...")
    cache, train_windows, val_windows = load_cache(args.cache)
    D = cache["D"]
    win_len = cache["win_len"]
    print(f"Data: {D}-dim physics, {win_len}-frame windows")

    # ── Model ──
    model = PhysicsFieldModel(
        field_d=D, d=args.d, N=args.N, C=13,
        max_batch_size=args.bs,
        use_phi_qp=True,
    ).to(DEV)

    n_p = sum(p.numel() for p in model.parameters())
    print(f"Model: PhysicsFieldModel d={args.d} N={args.N} "
          f"({model.C} chakras), params: {n_p:,}")

    # ── Optimizer ──
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    print(f"Optimizer: AdamW (lr={args.lr})")

    # ── Checkpoint state ──
    ckpt_latest = os.path.join(args.save_dir, "physics_latest.pt")
    ckpt_best = os.path.join(args.save_dir, "physics_best.pt")
    start_ep = 0
    best_val_loss = float("inf")
    patience_counter = 0

    if args.resume and os.path.exists(ckpt_latest):
        ckpt = torch.load(ckpt_latest, map_location=DEV, weights_only=True)
        ckpt_model = ckpt.get("model", ckpt)
        try:
            missing, unexpected = model.load_state_dict(ckpt_model, strict=False)
            # Log missing/unexpected but don't fail (buffers differ by N/d)
            loaded = len(ckpt_model) - len(missing) - len(unexpected)
            total = len(dict(model.state_dict()))
            print(f"Resumed checkpoint: {loaded}/{total} tensors restored")
            if "optimizer" in ckpt:
                opt.load_state_dict(ckpt["optimizer"])
            if "epoch" in ckpt:
                start_ep = ckpt["epoch"] + 1
                best_val_loss = ckpt.get("best_val_loss", float("inf"))
        except Exception as e:
            print(f"Checkpoint load failed: {e}, starting fresh")
    else:
        print("Training from scratch")

    # ── TensorBoard ──
    tb_writer = None
    if not args.no_tb:
        try:
            from torch.utils.tensorboard import SummaryWriter
            run_id = time.strftime("%Y%m%d-%H%M%S")
            tb_writer = SummaryWriter(log_dir=f"{args.logdir}/{run_id}")
        except ImportError:
            print("TensorBoard not available")

    # ════════════════════════════════════════════════
    #  Training Loop
    # ════════════════════════════════════════════════

    end_epoch = start_ep + args.epochs

    for ep in range(start_ep, end_epoch):
        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_mse = 0.0
        ep_spectral = 0.0
        ep_self_pred = 0.0
        nan_steps = 0

        for step in range(args.steps_per_epoch):
            frames = sample_batch(train_windows, args.bs, DEV)
            model.reset_state()

            loss, info = model.training_loss(
                frames, T=args.T, dt=args.dt,
                mse_weight=args.mse_weight,
                spectral_weight=args.spectral_weight,
            )

            if not torch.isfinite(loss):
                nan_steps += 1
                continue

            opt.zero_grad()
            loss.backward()

            # Gradient clipping (tight for PDE stability)
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            if torch.isnan(grad_norm) or torch.isinf(grad_norm):
                opt.zero_grad()
                nan_steps += 1
                continue

            opt.step()

            ep_loss += info["loss"]
            ep_mse += info["mse"]
            ep_spectral += info["spectral"]
            ep_self_pred += info["field_self_pred"]

        eff_steps = max(1, args.steps_per_epoch - nan_steps)
        ep_loss /= eff_steps
        ep_mse /= eff_steps
        ep_spectral /= eff_steps
        ep_self_pred /= eff_steps

        # ── Validation ──
        model.eval()
        val_loss = 0.0
        val_mse = 0.0
        with torch.no_grad():
            for _ in range(args.val_steps):
                model.reset_state()
                frames = sample_batch(val_windows, args.bs, DEV)
                v_loss, v_info = model.training_loss(
                    frames, T=args.T, dt=args.dt,
                    mse_weight=args.mse_weight,
                    spectral_weight=args.spectral_weight,
                )
                val_loss += v_loss.item()
                val_mse += v_info["mse"]
        val_loss /= args.val_steps
        val_mse /= args.val_steps

        # ── Rollout evaluation ──
        rollout_mae = None
        if args.gen_every > 0 and ep % args.gen_every == 0:
            model.eval()
            model.reset_state()
            with torch.no_grad():
                seed_batch = sample_batch(val_windows, 1, DEV)
                seed_frame = seed_batch[0, 0]
                gt_traj = seed_batch[0]
                rollout_traj = model.rollout(
                    seed_frame, n_steps=args.gen_steps,
                    T=args.T, dt=args.dt,
                )
                rollout_mae = F.l1_loss(
                    rollout_traj[:min(len(rollout_traj), len(gt_traj))],
                    gt_traj[:min(len(rollout_traj), len(gt_traj))]
                ).item()
            print(f"  rollout MAE (over {args.gen_steps} steps): {rollout_mae:.6f}")
            model.train()

        dt = time.time() - t0
        print(f"ep={ep} train={ep_loss:.6f} mse={ep_mse:.6f} "
              f"spec={ep_spectral:.6f} self_pred={ep_self_pred:.6f} "
              f"val={val_loss:.6f} val_mse={val_mse:.6f} "
              f"lr={opt.param_groups[0]['lr']:.6f} dt={dt:.1f}s")

        if tb_writer is not None:
            tb_writer.add_scalar("loss/train", ep_loss, ep)
            tb_writer.add_scalar("loss/val", val_loss, ep)
            tb_writer.add_scalar("loss/mse", ep_mse, ep)
            tb_writer.add_scalar("loss/spectral", ep_spectral, ep)
            tb_writer.add_scalar("loss/field_self_pred", ep_self_pred, ep)
            if rollout_mae is not None:
                tb_writer.add_scalar("eval/rollout_mae", rollout_mae, ep)

        # ── Save ──
        ckpt = {
            "epoch": ep,
            "model": model.state_dict(),
            "optimizer": opt.state_dict(),
            "best_val_loss": best_val_loss,
            "val_loss": val_loss,
        }
        torch.save(ckpt, ckpt_latest)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(ckpt, ckpt_best)
            print(f"  ✓ new best: {best_val_loss:.6f}")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f"Early stop at epoch {ep} (best={best_val_loss:.6f})")
                break

    if tb_writer is not None:
        tb_writer.close()
    print("Done!")


if __name__ == "__main__":
    main()
