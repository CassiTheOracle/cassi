"""Train ByteDiffusionCord on text and generate samples.

Usage:
    CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. python experiments/train_byte_diffusion.py --epochs 20 --bs 32
    PYTHONPATH=. python experiments/train_byte_diffusion.py --load checkpoints/byte_diffusion.pt --generate-only
"""

import argparse, os, time, torch, numpy as np

_USE_CUDA = torch.cuda.is_available()
DEV = 'cuda' if _USE_CUDA else 'cpu'

from cassi.cord import CordPhysics
from cassi.byte_diffusion_cord import ByteDiffusionCord, train_byte_diffusion
from cassi.streaming_text_sampler import StreamingTextSampler
from experiments.train_langevin_text import (
    build_text_loader, sample_train_batch, sample_val_batch
)


def extract_byte_encoder(path):
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


def validate(model, sampler, val_offset, val_rng, args):
    model.eval()
    loss = 0.0
    with torch.no_grad():
        for _ in range(10):
            x, y = sample_val_batch(sampler, args.bs, val_offset, val_rng)
            loss += model.training_loss(x.to(DEV)).item()
    return loss / 10


def generate(model, args):
    print("\n" + "=" * 60)
    print("Generation — DDIM vs Langevin")
    print("=" * 60)
    model.eval()

    methods = [
        ("DDIM 50 steps",       50, 'ddim'),
        ("DDIM 100 steps",     100, 'ddim'),
        ("Langevin 100 steps", 100, 'langevin'),
        ("Langevin 200 steps", 200, 'langevin'),
    ]
    for label, steps, method in methods:
        print(f"\n  [{label}]")
        texts = model.generate_text(B=min(args.gen_samples, 2), num_steps=steps,
                                    temperature=0.8, method=method, device=DEV)
        for i, t in enumerate(texts):
            print(f"    {i+1}: {t[:150]!r}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--bs', type=int, default=32)
    p.add_argument('--lr', type=float, default=1e-3)
    p.add_argument('--steps-per-epoch', type=int, default=200)
    p.add_argument('--text-dir', default='datasets/active')
    p.add_argument('--save', default='checkpoints/byte_diffusion.pt')
    p.add_argument('--load', default=None)
    p.add_argument('--generate-only', action='store_true')
    p.add_argument('--gen-samples', type=int, default=3)
    p.add_argument('--spine-ckpt', default='checkpoints/spine_text.pt')
    p.add_argument('--timesteps', type=int, default=1000)
    args = p.parse_args()

    print(f"Device: {DEV}")

    byte_encoder = extract_byte_encoder(args.spine_ckpt).to(DEV)
    model = ByteDiffusionCord(byte_encoder, num_timesteps=args.timesteps,
                              train_remap=True).to(DEV)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")

    start_epoch = 0
    if args.load and os.path.exists(args.load):
        ckpt = torch.load(args.load, map_location=DEV, weights_only=False)
        ms, cs = model.state_dict(), ckpt['model']
        for k in list(cs.keys()):
            if k in ms and cs[k].shape == ms[k].shape:
                ms[k] = cs[k]
        model.load_state_dict(ms)
        start_epoch = ckpt.get('epoch', 0)
        print(f"Loaded from epoch {start_epoch}")

    if args.generate_only:
        generate(model, args)
        return

    sampler, total, n_train, n_val, val_off, tr_rng, val_rng = build_text_loader(args.text_dir)
    print(f"Data: {total:,} bytes")

    class Loader:
        def sample_train_batch(self, bs):
            return sample_train_batch(sampler, bs, tr_rng)
    loader = Loader()
    loader.bs = args.bs
    loader.device = DEV

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    best = float('inf')

    for ep in range(start_epoch, start_epoch + args.epochs):
        t0 = time.time()
        tl = train_byte_diffusion(model, loader, opt, args, ep)
        vl = validate(model, sampler, val_off, val_rng, args)
        dt = time.time() - t0
        print(f"\nEpoch {ep+1}/{start_epoch+args.epochs}: train={tl:.4f} val={vl:.4f} time={dt:.0f}s")
        if vl < best:
            best = vl
            torch.save({'model': model.state_dict(), 'val_loss': vl, 'epoch': ep+1}, args.save)
            print(f"  -> saved {args.save}")

    print(f"\nBest val_loss={best:.4f}")
    generate(model, args)


if __name__ == '__main__':
    main()
