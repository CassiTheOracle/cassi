"""Train TokenDiffusionCord on text.

Usage:
    CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. python experiments/train_token_diffusion.py --epochs 20 --bs 32
"""

import argparse, os, time, torch, numpy as np

DEV = 'cuda' if torch.cuda.is_available() else 'cpu'

from cassi.token_diffusion_cord import TokenDiffusionCord, train_token_diffusion
from experiments.train_langevin_text import (
    build_text_loader, sample_train_batch, sample_val_batch
)


def validate(model, sampler, val_offset, val_rng, args):
    model.eval()
    loss = 0.0
    with torch.no_grad():
        for _ in range(10):
            x, y = sample_val_batch(sampler, args.bs, val_offset, val_rng)
            loss += model.training_loss(x.to(DEV)).item()
    return loss / 10


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--bs', type=int, default=32)
    p.add_argument('--lr', type=float, default=1e-3)
    p.add_argument('--emb-dim', type=int, default=4, help='Embedding dim per position')
    p.add_argument('--steps-per-epoch', type=int, default=200)
    p.add_argument('--text-dir', default='datasets/active')
    p.add_argument('--save', default='checkpoints/token_diffusion.pt')
    p.add_argument('--load', default=None)
    p.add_argument('--generate-only', action='store_true')
    p.add_argument('--gen-samples', type=int, default=4)
    p.add_argument('--timesteps', type=int, default=100)
    args = p.parse_args()

    print(f"Device: {DEV}")
    print(f"Embedding dim: {args.emb_dim}, Field dim: {1024 * args.emb_dim}")

    model = TokenDiffusionCord(vocab_size=256, emb_dim=args.emb_dim, seq_len=1024,
                               num_timesteps=args.timesteps).to(DEV)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")

    start_epoch = 0
    if args.load and os.path.exists(args.load):
        ckpt = torch.load(args.load, map_location=DEV, weights_only=False)
        model.load_state_dict(ckpt['model'])
        start_epoch = ckpt.get('epoch', 0)
        print(f"Loaded from epoch {start_epoch}")

    if args.generate_only:
        print("\n" + "=" * 60)
        print("TokenDiffusionCord Generation")
        print("=" * 60)
        model.eval()
        texts = model.generate_text(B=args.gen_samples, num_steps=100,
                                    temperature=0.8, method='ddim', device=DEV)
        for i, t in enumerate(texts):
            print(f"  {i+1}: {t[:150]!r}")
        return

    sampler, total, n_train, n_val, val_off, tr_rng, val_rng = build_text_loader(args.text_dir)
    print(f"Data: {total:,} bytes")

    class Loader:
        def sample_train_batch(self, bs):
            return sample_train_batch(sampler, bs, tr_rng)
    loader = Loader()
    loader.bs = args.bs

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    best = float('inf')

    for ep in range(start_epoch, start_epoch + args.epochs):
        t0 = time.time()
        tl = train_token_diffusion(model, loader, opt, args, ep)
        vl = validate(model, sampler, val_off, val_rng, args)
        dt = time.time() - t0
        print(f"\nEpoch {ep+1}/{start_epoch+args.epochs}: train={tl:.4f} val={vl:.4f} time={dt:.0f}s")
        if vl < best:
            best = vl
            torch.save({'model': model.state_dict(), 'val_loss': vl, 'epoch': ep+1}, args.save)
            print(f"  -> saved {args.save}")

    print(f"\nBest val_loss={best:.4f}")
    model.eval()
    texts = model.generate_text(B=4, num_steps=100, temperature=0.8, method='ddim', device=DEV)
    print("\nFinal samples:")
    for i, t in enumerate(texts):
        print(f"  {i+1}: {t[:150]!r}")


if __name__ == '__main__':
    main()
