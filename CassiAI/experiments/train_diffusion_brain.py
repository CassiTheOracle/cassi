"""Train HierarchicalDiffusionBrain on text and generate samples.

Usage:
    CUDA_VISIBLE_DEVICES=1 PYTORCH_HIP_ALLOC_CONF=expandable_segments:True HSA_ENABLE_SDMA=0 \
        PYTHONPATH=. python experiments/train_diffusion_brain.py --epochs 20 --bs 32
"""

import argparse, os, time, torch, numpy as np
import torch.nn.functional as F

DEV = 'cuda' if torch.cuda.is_available() else 'cpu'

from cassi.cord import CordPhysics
from cassi.diffusion_brain import HierarchicalDiffusionBrain
from experiments.train_langevin_text import (
    build_text_loader, sample_train_batch, sample_val_batch
)


def load_byte_encoder(path='checkpoints/spine_text.pt'):
    """Load pre-trained ByteEncoder from a checkpoint."""
    ckpt = torch.load(path, map_location='cpu', weights_only=False)
    state = ckpt.get('model', ckpt)
    cord = CordPhysics(D=1040, byte_mode=True, multi_scale_bytes=False)
    spine_state = {}
    for k, v in state.items():
        if k.startswith('spine.byte_encoder.') or k.startswith('byte_encoder.'):
            spine_state[k[6:] if k.startswith('spine.') else k] = v
    if spine_state:
        cord.load_state_dict(spine_state, strict=False)
        print(f"Loaded ByteEncoder ({len(spine_state)} keys)")
    return cord.byte_encoder


def train_epoch(model, byte_encoder, sampler, train_rng, opt, args, epoch):
    """Train HierarchicalDiffusionBrain for one epoch."""
    model.train()
    total_loss = 0.0

    for step in range(args.steps_per_epoch):
        x_bytes, _ = sample_train_batch(sampler, args.bs, train_rng)
        x_bytes = x_bytes.to(DEV)

        # Encode bytes to field [B, 1024] using ByteEncoder's last frame
        with torch.no_grad():
            field_4d = byte_encoder.encode_sequence(x_bytes, T=4)  # [B, 4, 1024]
            field = field_4d[:, -1, :]  # take last frame [B, 1024]

        # Pad to D=1040
        if field.shape[-1] < model.D:
            field = F.pad(field, (0, model.D - field.shape[-1]))

        opt.zero_grad()
        loss = model.training_loss(field)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

        total_loss += loss.item()

        if step % 50 == 0:
            print(f"  [{epoch+1}/{args.epochs}] step {step:4d}/{args.steps_per_epoch}  "
                  f"loss={loss.item():.4f}")

    return total_loss / max(1, args.steps_per_epoch)


def validate(model, byte_encoder, sampler, val_offset, val_rng, args):
    """Validate HierarchicalDiffusionBrain."""
    model.eval()
    total_loss = 0.0
    n_val = 10

    with torch.no_grad():
        for _ in range(n_val):
            x_bytes, _ = sample_val_batch(sampler, args.bs, val_offset, val_rng)
            x_bytes = x_bytes.to(DEV)
            field_4d = byte_encoder.encode_sequence(x_bytes, T=4)
            field = field_4d[:, -1, :]
            if field.shape[-1] < model.D:
                field = F.pad(field, (0, model.D - field.shape[-1]))
            loss = model.training_loss(field)
            total_loss += loss.item()

    return total_loss / n_val


@torch.no_grad()
def generate(model, byte_encoder, args):
    """Generate text via DDIM sampling with hierarchical guidance."""
    print("\n" + "=" * 60)
    print("HierarchicalDiffusionBrain Generation")
    print("=" * 60)
    model.eval()

    # Use the spine's DDIM sampler, but with brainstem/brainfield guidance
    # enabled at the appropriate step intervals
    D = model.D

    for num_steps in [50, 100]:
        print(f"\n  [DDIM {num_steps} steps with hierarchical guidance]")

        # Manual DDIM loop with hierarchical forward
        step_indices = model.spine._subsample_steps(num_steps)
        x_t = torch.randn(args.gen_samples, D, device=DEV)

        for i, t_idx in enumerate(step_indices):
            t = torch.full((args.gen_samples,), t_idx, device=DEV, dtype=torch.long)
            t_prev = step_indices[i + 1] if i + 1 < len(step_indices) else -1

            # Hierarchical forward with guidance at step_idx
            x0_pred = model(x_t, t, step_idx=i)

            if t_prev >= 0:
                alpha_cumprod = model.spine.alphas_cumprod[t_idx]
                alpha_cumprod_prev = model.spine.alphas_cumprod[t_prev]
                sigma_t = 0.0
                eps_pred = (x_t - torch.sqrt(alpha_cumprod) * x0_pred) / \
                           torch.sqrt(1.0 - alpha_cumprod + 1e-8)
                pred_dir = torch.sqrt(1.0 - alpha_cumprod_prev + 1e-8) * eps_pred
                x_t = torch.sqrt(alpha_cumprod_prev) * x0_pred + pred_dir
            else:
                x_t = x0_pred

        # Decode back to bytes via ByteEncoder pseudo-inverse
        field_1024 = x_t[:, :1024]  # strip padding
        for b in range(min(args.gen_samples, 3)):
            byte_ids = byte_encoder.decode_field(field_1024[b])
            text = bytes([x for x in byte_ids.cpu().numpy() if 32 <= x < 127])
            print(f"    {b+1}: {text.decode('ascii', errors='replace')[:150]!r}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--bs', type=int, default=32)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--steps-per-epoch', type=int, default=200)
    p.add_argument('--text-dir', default='datasets/active')
    p.add_argument('--save', default='checkpoints/diffusion_brain.pt')
    p.add_argument('--load', default=None)
    p.add_argument('--generate-only', action='store_true')
    p.add_argument('--gen-samples', type=int, default=3)
    p.add_argument('--spine-ckpt', default='checkpoints/spine_text.pt')
    args = p.parse_args()

    print(f"Device: {DEV}")

    byte_encoder = load_byte_encoder(args.spine_ckpt).to(DEV)
    model = HierarchicalDiffusionBrain(D=1040, K=2, M=2).to(DEV)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")

    start_epoch = 0
    if args.load and os.path.exists(args.load):
        ckpt = torch.load(args.load, map_location=DEV, weights_only=False)
        model.load_state_dict(ckpt['model'])
        start_epoch = ckpt.get('epoch', 0)
        print(f"Loaded from epoch {start_epoch}")

    if args.generate_only:
        generate(model, byte_encoder, args)
        return

    sampler, total_size, n_train, n_val, val_off, tr_rng, val_rng = \
        build_text_loader(args.text_dir)
    print(f"Data: {total_size:,} bytes")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    best_val = float('inf')

    for epoch in range(start_epoch, start_epoch + args.epochs):
        t0 = time.time()
        tl = train_epoch(model, byte_encoder, sampler, tr_rng, opt, args, epoch)
        vl = validate(model, byte_encoder, sampler, val_off, val_rng, args)
        dt = time.time() - t0
        print(f"\nEpoch {epoch+1}/{start_epoch+args.epochs}: "
              f"train={tl:.4f} val={vl:.4f} time={dt:.0f}s")
        if vl < best_val:
            best_val = vl
            torch.save({'model': model.state_dict(), 'val_loss': vl, 'epoch': epoch+1}, args.save)
            print(f"  -> saved {args.save}")

    print(f"\nBest val_loss={best_val:.4f}")
    generate(model, byte_encoder, args)


if __name__ == '__main__':
    main()
