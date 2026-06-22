"""Train CordPhysics on text, then generate via CordLangevinSampler.

Usage:
    # Quick test (few epochs, small batches)
    CUDA_VISIBLE_DEVICES="" python experiments/train_langevin_text.py --epochs 3 --bs 4 --steps-per-epoch 20

    # Full training
    python experiments/train_langevin_text.py --epochs 20 --bs 32 --steps-per-epoch 500

    # Load existing checkpoint and just generate
    python experiments/train_langevin_text.py --load checkpoints/spine_text.pt --generate-only
"""

import argparse
import math
import os
import sys
import time
import torch
import torch.nn.functional as F
import numpy as np

# Force CPU if CUDA not available, and patch experiments/train.py's hardcoded DEV
_USE_CUDA = torch.cuda.is_available()
if not _USE_CUDA:
    os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')
DEV = 'cuda' if _USE_CUDA else 'cpu'

from cassi.cord import CordPhysics
from cassi.cord_langevin import CordLangevinSampler
from cassi.streaming_text_sampler import StreamingTextSampler


def build_text_loader(active_dir='datasets/active', val_frac=0.02):
    """Build a simple text data loader from active directory."""
    sampler = StreamingTextSampler(None, window_bytes=1024, stride=256, device=DEV)

    if active_dir and os.path.exists(active_dir):
        for fname in sorted(os.listdir(active_dir)):
            path = os.path.join(active_dir, fname)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(fname)[1].lower()
            try:
                if ext == '.txt':
                    with open(path, 'rb') as f:
                        while True:
                            chunk = f.read(1024 * 1024)
                            if not chunk:
                                break
                            sampler.append(chunk)
                elif ext == '.parquet':
                    _append_parquet(sampler, path)
                elif ext in ('.json', '.jsonl'):
                    _append_json(sampler, path)
            except Exception as e:
                print(f"  Warning: could not load {fname}: {e}")

    total_size = sampler.size
    n_val = int(total_size * val_frac)
    n_train = total_size - n_val
    val_offset = n_train

    train_rng = np.random.RandomState(42)
    val_rng = np.random.RandomState(43)

    return sampler, total_size, n_train, n_val, val_offset, train_rng, val_rng


def _append_parquet(sampler, path):
    try:
        import pyarrow.parquet as pq
        df = pq.read_table(path).to_pandas()
        for col in df.columns:
            if df[col].dtype == object:
                sample = df[col].dropna().iloc[:5].tolist()
                if any(isinstance(x, str) and len(x) > 20 for x in sample):
                    texts = df[col].dropna().astype(str).tolist()
                    sampler.append('\n\n'.join(texts).encode('utf-8'))
                    break
    except ImportError:
        pass


def _append_json(sampler, path):
    import json
    texts = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    try:
        obj = json.loads(content)
        if isinstance(obj, list):
            texts = [x for x in obj if isinstance(x, str)]
    except json.JSONDecodeError:
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    for key in ('text', 'content', 'instruction', 'response'):
                        if key in obj and isinstance(obj[key], str):
                            texts.append(obj[key])
                            break
            except json.JSONDecodeError:
                pass
    if texts:
        sampler.append('\n\n'.join(texts).encode('utf-8'))


def sample_train_batch(sampler, batch_size, train_rng):
    """Sample a training batch of byte windows."""
    max_start = sampler.size - sampler.window_bytes - sampler.stride
    if max_start <= 0:
        raise ValueError(f"Not enough data: {sampler.size} bytes")
    batch_size = min(batch_size, max_start)
    starts = train_rng.randint(0, max_start, size=batch_size)
    idx = np.arange(sampler.window_bytes)
    x_idx = starts[:, None] + idx[None, :]
    y_idx = (starts + sampler.stride)[:, None] + idx[None, :]
    # Index directly into ring buffer — skip intermediate view of full array
    x = torch.from_numpy(sampler._ring[x_idx]).to(DEV)
    y = torch.from_numpy(sampler._ring[y_idx]).to(DEV)
    return x, y


def sample_val_batch(sampler, batch_size, val_offset, val_rng):
    """Sample a validation batch."""
    max_start = sampler.size - val_offset - sampler.window_bytes - sampler.stride
    if max_start > 0:
        starts = val_rng.randint(val_offset, val_offset + max_start, size=batch_size)
    else:
        max_start = max(1, sampler.size - sampler.window_bytes - sampler.stride)
        starts = val_rng.randint(0, max_start, size=batch_size)
    idx = np.arange(sampler.window_bytes)
    x_idx = starts[:, None] + idx[None, :]
    y_idx = (starts + sampler.stride)[:, None] + idx[None, :]
    x = torch.from_numpy(sampler._ring[x_idx]).to(DEV)
    y = torch.from_numpy(sampler._ring[y_idx]).to(DEV)
    return x, y


def extract_spine_state(checkpoint):
    """Extract spine.* weights from a full-brain or spine checkpoint."""
    state = checkpoint.get('model', checkpoint)
    spine_state = {}
    for k, v in state.items():
        if k.startswith('spine.'):
            spine_state[k[6:]] = v
        elif any(k.startswith(p) for p in ('byte_encoder.', 'in_proj.', 'fusion.',
                                             'decoder.', 'chakra_', 'fwd_', 'rev_')):
            spine_state[k] = v
    if not spine_state:
        for k, v in state.items():
            if not any(k.startswith(p) for p in ('harmony_', 'workspace_', 'field_history',
                                                  'specialist_', 'qi_fluid', 'yang', 'yin')):
                spine_state[k] = v
    return spine_state


def train_spine_denoising(model, sampler, train_rng, optimizer, args, epoch):
    """Train CordPhysics as a denoising autoencoder on text.

    Adds Gaussian noise to input bytes, trains the Cord to recover clean bytes.
    This creates a proper denoising energy landscape that the Langevin sampler
    can use for generation.
    """
    model.train()
    total_loss = 0.0

    for step in range(args.steps_per_epoch):
        x, y = sample_train_batch(sampler, args.bs, train_rng)
        # x, y are [B, 1024] uint8 byte windows
        # Add noise to input (the Cord should learn to denoise)
        noise_level = args.noise_level * (0.5 + 0.5 * np.random.random())
        noise = torch.randn_like(x.float()) * noise_level
        x_noisy = (x.float() + noise).clamp(0, 255)

        optimizer.zero_grad()
        pred = model(x_noisy.to(torch.uint8), byte_mode=True)
        loss = F.mse_loss(pred, x.float())

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item()

        if step % 50 == 0:
            elapsed = time.time() - args.t0
            print(f"  [{epoch+1}/{args.epochs}] step {step:4d}/{args.steps_per_epoch}  "
                  f"loss={loss.item():.4f}  noise={noise_level:.1f}  elapsed={elapsed:.0f}s")

    return total_loss / max(1, args.steps_per_epoch)


train_spine = train_spine_denoising  # alias for main loop


def validate_spine(model, sampler, val_offset, val_rng, args):
    """Validate CordPhysics on held-out text data (with denoising)."""
    model.eval()
    total_loss = 0.0
    n_val = 10

    with torch.no_grad():
        for _ in range(n_val):
            x, y = sample_val_batch(sampler, args.bs, val_offset, val_rng)
            noise = torch.randn_like(x.float()) * args.noise_level
            x_noisy = (x.float() + noise).clamp(0, 255)
            pred = model(x_noisy.to(torch.uint8), byte_mode=True)
            loss = F.mse_loss(pred, x.float())
            total_loss += loss.item()

    return total_loss / n_val


def try_langevin_generation(model, args):
    print("\n" + "=" * 60)
    print("Langevin Text Generation")
    print("=" * 60)
    sampler = CordLangevinSampler(model)

    # Test with different Langevin noise regimes
    configs = [
        ("low noise", 0.05, 0.02),
        ("med noise", 0.15, 0.05),
        ("high noise", 0.3, 0.1),
    ]

    for label, ripple_scale, noise_scale in configs:
        print(f"\n  [{label}] ripple={ripple_scale}, noise={noise_scale}")
        for i in range(min(args.gen_samples, 2)):
            with torch.no_grad():
                field_D = sampler.sample(
                    1, num_steps=args.gen_steps,
                    ripple_scale=ripple_scale, noise_scale=noise_scale,
                    device=DEV, temperature=args.temperature
                )
                # Decode D → 1024 field space
                field_1024 = model.decoder(field_D)  # [1, 1024]

            # Use ByteEncoder's built-in decode_field (pseudo-inverse based)
            byte_ids = model.byte_encoder.decode_field(field_1024[0])  # [256]
            text_bytes = bytes([b for b in byte_ids.cpu().numpy() if 32 <= b < 127])
            text = text_bytes.decode('ascii', errors='replace')

            field_np = field_1024[0].cpu().numpy()
            autocorr = np.corrcoef(field_np[:-1], field_np[1:])[0, 1]

            print(f"    Sample {i+1}: field mean={field_np.mean():.2f} std={field_np.std():.3f} "
                  f"autocorr={autocorr:.4f}")
            print(f"    Decoded (256 bytes): {text[:120]!r}")

    print()

def main():
    parser = argparse.ArgumentParser(description='Train CordPhysics on text + Langevin generation')
    parser.add_argument('--epochs', type=int, default=5)
    parser.add_argument('--bs', type=int, default=8)
    parser.add_argument('--lr', type=float, default=2e-4)
    parser.add_argument('--lr-spine', type=float, default=5e-6)
    parser.add_argument('--steps-per-epoch', type=int, default=200)
    parser.add_argument('--D', type=int, default=1040)
    parser.add_argument('--text-dir', default='datasets/active')
    parser.add_argument('--save', default='checkpoints/spine_langevin.pt')
    parser.add_argument('--load', default=None, help='Load existing checkpoint')
    parser.add_argument('--generate-only', action='store_true')
    parser.add_argument('--gen-steps', type=int, default=200, help='Langevin steps')
    parser.add_argument('--gen-samples', type=int, default=3, help='Samples to generate')
    parser.add_argument('--ripple-scale', type=float, default=0.05)
    parser.add_argument('--noise-scale', type=float, default=0.02)
    parser.add_argument('--temperature', type=float, default=1.0)
    parser.add_argument('--noise-level', type=float, default=30.0,
                        help='Std of Gaussian noise added to input bytes for denoising training')
    args = parser.parse_args()
    args.t0 = time.time()


    print(f"Device: {DEV}")
    print(f"Field dim D: {args.D}")

    # ── Build model ──
    model = CordPhysics(D=args.D, byte_mode=True, multi_scale_bytes=False).to(DEV)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {n_params:,}")

    # ── Load checkpoint if provided ──
    start_epoch = 0
    if args.load and os.path.exists(args.load):
        print(f"Loading checkpoint: {args.load}")
        ckpt = torch.load(args.load, map_location=DEV, weights_only=False)
        spine_state = extract_spine_state(ckpt)
        for k in list(spine_state.keys()):
            if any(buf in k for buf in ('qi_fluid', 'h1', 'h2', 'x1', 'yang', 'yin',
                                         'field_state', 'field_energy', '_frame_buffer')):
                if spine_state[k].dim() >= 2 and spine_state[k].shape[0] > 1:
                    spine_state[k] = spine_state[k][:1]
        model.load_state_dict(spine_state, strict=False)
        if 'epoch' in ckpt:
            start_epoch = ckpt['epoch']
        print(f"  Loaded from epoch {start_epoch}")

    if args.generate_only:
        try_langevin_generation(model, args)
        return

    # ── Data loader ──
    print(f"Loading text data from: {args.text_dir}")
    sampler, total_size, n_train, n_val, val_offset, train_rng, val_rng = \
        build_text_loader(args.text_dir)
    print(f"  Total bytes: {total_size:,}")
    print(f"  Train bytes: {n_train:,}")
    print(f"  Val bytes:   {n_val:,}")

    # ── Optimizer ──
    optimizer = torch.optim.AdamW([
        {'params': [p for n, p in model.named_parameters() if 'byte_encoder' in n], 'lr': args.lr},
        {'params': [p for n, p in model.named_parameters() if 'byte_encoder' not in n], 'lr': args.lr_spine},
    ], weight_decay=0.01)

    # ── Training loop ──
    best_val = float('inf')
    for epoch in range(start_epoch, start_epoch + args.epochs):
        t0 = time.time()

        train_loss = train_spine(model, sampler, train_rng, optimizer, args, epoch)
        val_loss = validate_spine(model, sampler, val_offset, val_rng, args)

        dt = time.time() - t0
        print(f"\nEpoch {epoch+1}/{start_epoch + args.epochs}: "
              f"train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  time={dt:.0f}s")

        if val_loss < best_val:
            best_val = val_loss
            torch.save({
                'model': model.state_dict(),
                'val_loss': val_loss,
                'epoch': epoch + 1,
            }, args.save)
            print(f"  → Saved best checkpoint to {args.save}")

    # ── Final generation ──
    print(f"\nTraining complete. Best val_loss={best_val:.4f}")
    try_langevin_generation(model, args)


if __name__ == '__main__':
    main()
