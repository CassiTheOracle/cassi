"""Train RecurrentDiffusionBrain on token-embedded text.

Usage:
    CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. python experiments/train_recurrent_brain.py --epochs 30 --bs 32
"""

import argparse, os, time, torch, numpy as np

DEV = 'cuda' if torch.cuda.is_available() else 'cpu'

from cassi.recurrent_diffusion_brain import RecurrentDiffusionBrain
from cassi.token_diffusion_cord import TokenDiffusionCord
from experiments.train_langevin_text import (
    build_text_loader, sample_train_batch, sample_val_batch
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=30)
    p.add_argument('--bs', type=int, default=32)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--emb-dim', type=int, default=4)
    p.add_argument('--steps-per-epoch', type=int, default=200)
    p.add_argument('--text-dir', default='datasets/active')
    p.add_argument('--save', default='checkpoints/recurrent_brain.pt')
    p.add_argument('--load', default=None)
    p.add_argument('--generate-only', action='store_true')
    p.add_argument('--gen-samples', type=int, default=4)
    p.add_argument('--timesteps', type=int, default=100)
    args = p.parse_args()

    print(f"Device: {DEV}")
    D = 1024 * args.emb_dim
    print(f"Field dim: {D} (emb_dim={args.emb_dim})")

    # Token embedding model for bytes→field
    token_model = TokenDiffusionCord(
        vocab_size=256, emb_dim=args.emb_dim, seq_len=1024,
        num_timesteps=args.timesteps
    ).to(DEV)

    # Recurrent diffusion brain operates on the token embedding field
    model = RecurrentDiffusionBrain(D=D, K=2).to(DEV)
    n_p = sum(p.numel() for p in model.parameters())
    n_t = sum(p.numel() for p in token_model.parameters())
    print(f"RecurrentBrain params: {n_p:,}")
    print(f"Token model params:    {n_t:,}")
    print(f"Total:                 {n_p + n_t:,}")

    start_epoch = 0
    if args.load and os.path.exists(args.load):
        ckpt = torch.load(args.load, map_location=DEV, weights_only=False)
        model.load_state_dict(ckpt['model'])
        if 'token_model' in ckpt:
            token_model.load_state_dict(ckpt['token_model'])
        start_epoch = ckpt.get('epoch', 0)
        print(f"Loaded from epoch {start_epoch}")

    if args.generate_only:
        print("\n" + "=" * 60)
        print("RecurrentDiffusionBrain Generation")
        print("=" * 60)
        model.eval()
        token_model.eval()
        # Simple DDIM generation loop with brainstem feedback
        steps = model.spine._subsample_steps(100)
        x_t = torch.randn(args.gen_samples, D, device=DEV)
        model.reset_state(args.gen_samples)

        for i, t_idx in enumerate(steps):
            t = torch.full((args.gen_samples,), t_idx, device=DEV, dtype=torch.long)
            t_prev = steps[i + 1] if i + 1 < len(steps) else -1
            x0 = model(x_t, t, step_idx=i)
            if t_prev >= 0:
                ac = model.spine.alphas_cumprod[t_idx]
                ap = model.spine.alphas_cumprod[t_prev]
                eps = (x_t - torch.sqrt(ac) * x0) / torch.sqrt(1.0 - ac + 1e-8)
                x_t = torch.sqrt(ap) * x0 + torch.sqrt(1.0 - ap + 1e-8) * eps
            else:
                x_t = x0

        bytes_tensor = token_model.field_to_bytes(x_t, temperature=0.8)
        for b in range(min(args.gen_samples, 4)):
            raw = bytes_tensor[b].cpu().numpy()
            text = bytes([x for x in raw if 32 <= x < 127]).decode('ascii', errors='replace')
            print(f"  {b+1}: {text[:150]!r}")
        return

    # ── Data ──
    sampler, total, n_train, n_val, val_off, tr_rng, val_rng = \
        build_text_loader(args.text_dir)
    print(f"Data: {total:,} bytes")

    opt = torch.optim.AdamW(
        list(model.parameters()) + list(token_model.parameters()),
        lr=args.lr, weight_decay=0.01
    )
    best_val = float('inf')

    for ep in range(start_epoch, start_epoch + args.epochs):
        t0 = time.time()
        model.train()
        token_model.train()
        model.reset_state(args.bs)
        total_loss = 0.0

        for step in range(args.steps_per_epoch):
            x_bytes, _ = sample_train_batch(sampler, args.bs, tr_rng)
            x_bytes = x_bytes.to(DEV)
            field = token_model.bytes_to_field(x_bytes)  # [B, D]

            opt.zero_grad()
            loss = model.training_loss(field)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(model.parameters()) + list(token_model.parameters()), 1.0
            )
            opt.step()
            total_loss += loss.item()

        avg_loss = total_loss / max(1, args.steps_per_epoch)
        dt = time.time() - t0
        print(f"Epoch {ep+1:3d}/{start_epoch+args.epochs}: loss={avg_loss:.4f} time={dt:.0f}s")

        if avg_loss < best_val:
            best_val = avg_loss
            torch.save({
                'model': model.state_dict(),
                'token_model': token_model.state_dict(),
                'loss': avg_loss,
                'epoch': ep + 1,
            }, args.save)
            print(f"  -> saved {args.save}")

    print(f"\nBest loss={best_val:.4f}")


if __name__ == '__main__':
    main()
