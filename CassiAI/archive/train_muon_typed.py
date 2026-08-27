#!/usr/bin/env python3
"""Train MuonCord on typed byte dataset (arbitrary files).

Usage:
    python3 experiments/train_muon_typed.py --root-dir datasets/mixed --epochs 10
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

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from muon_cord import MuonCord
from cassi.qi_fluid_optimizer import QiFluidOptimizer
from cassi.typed_byte_dataset import TypedByteDataset, prepare_typed_dataset


def _select_gpu():
    if not torch.cuda.is_available():
        return 'cpu'
    n = torch.cuda.device_count()
    if n >= 2:
        return 'cuda:1'
    return 'cuda:0'


def _select_device():
    if not torch.cuda.is_available():
        return 'cpu'
    return _select_gpu()
def sample_typed_batch(dataset, batch_size, rng):
    """Sample a batch from typed dataset."""
    indices = torch.randint(0, len(dataset), (batch_size,), generator=rng)
    contexts = []
    for idx in indices.tolist():
        context, _ = dataset[idx]
        contexts.append(context)
    return torch.stack(contexts)


def main():
    parser = argparse.ArgumentParser(description='Train MuonCord on typed byte dataset')
    parser.add_argument('--root-dir', type=str, default='datasets/mixed',
                        help='Root directory containing files to train on')
    parser.add_argument('--N', type=int, default=128, help='Field size (N)')
    parser.add_argument('--d', type=int, default=128, help='Field dimension (d)')
    parser.add_argument('--epochs', type=int, default=10, help='Number of epochs')
    parser.add_argument('--bs', type=int, default=32, help='Batch size')
    parser.add_argument('--lr', type=float, default=3e-4, help='Learning rate')
    parser.add_argument('--steps-per-epoch', type=int, default=100,
                        help='Training steps per epoch')
    parser.add_argument('--gen-every', type=int, default=5,
                        help='Generate text every N epochs (0=never)')
    parser.add_argument('--max-files', type=int, default=1000,
                        help='Maximum number of files to load')
    parser.add_argument('--no-tb', action='store_true', help='Disable TensorBoard')
    args = parser.parse_args()

    device = _select_device()
    print(f'GPU: {device}')

    # Prepare dataset
    print(f'Scanning {args.root_dir} for files...')
    file_paths = prepare_typed_dataset(args.root_dir, max_files=args.max_files)
    print(f'Found {len(file_paths)} files')
    
    if len(file_paths) == 0:
        print('No files found. Please populate the dataset directory.')
        return

    # Create dataset
    dataset = TypedByteDataset(
        file_paths=file_paths,
        seq_len=args.N,
        overlap=args.N // 4,
        max_file_size=10 * 1024 * 1024,  # 10MB
    )
    print(f'Dataset: {len(dataset)} chunks')

    # Build model
    model = MuonCord(N=args.N, d=args.d, K_train=3, K_gen=3).to(device)
    print(f'Model: MuonCord N={args.N} d={args.d}')
    print(f'Params: {sum(p.numel() for p in model.parameters()):,} total')

    # Build optimizer
    opt = QiFluidOptimizer(model.parameters(), lr=args.lr)

    # Training loop
    rng = torch.Generator().manual_seed(42)
    best_val = float('inf')

    print(f'\nStarting training for {args.epochs} epochs...')
    for epoch in range(args.epochs):
        model.train()
        epoch_loss = 0.0
        t0 = time.time()

        for step in range(args.steps_per_epoch):
            # Sample batch
            x = sample_typed_batch(dataset, args.bs, rng).to(device)

            # Forward
            loss, info = model.training_loss(x)

            # Backward
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

            epoch_loss += loss.item()

            if (step + 1) % 20 == 0:
                print(f'  step {step+1}/{args.steps_per_epoch} loss={loss.item():.4f}')

        # Epoch stats
        dt = time.time() - t0
        avg_loss = epoch_loss / args.steps_per_epoch
        Q = info.get('Q_mean', 0.0)
        if isinstance(Q, torch.Tensor):
            Q = Q.item()
        yang = info.get('yang', 0.0)
        if isinstance(yang, torch.Tensor):
            yang = yang.item()
        yin = info.get('yin', 0.0)
        if isinstance(yin, torch.Tensor):
            yin = yin.item()
        pm_active = info.get('pm_active', 0)

        print(f'ep={epoch} train={avg_loss:.4f} Q={Q:.3f} '
              f'yang={yang:.3f} yin={yin:.3f} pm_active={pm_active:.1f} dt={dt:.1f}s')

        # Validation (simple: use last batch)
        model.eval()
        with torch.no_grad():
            x_val = sample_typed_batch(dataset, args.bs, rng).to(device)
            val_loss, _ = model.training_loss(x_val)
        
        if val_loss.item() < best_val:
            best_val = val_loss.item()
            print(f'  ✓ new best: {best_val:.4f}')

        # Generation
        if args.gen_every > 0 and (epoch + 1) % args.gen_every == 0:
            print(f'--- generation @ epoch {epoch} ---')
            model.eval()
            with torch.no_grad():
                # Generate with type marker for text
                seed = torch.tensor([0xFF, 0x01], dtype=torch.long, device=device)  # txt type
                gen = model.generate_parallel(seed, max_len=64, temp=0.8)
                # Decode bytes
                text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in gen.tolist())
                print(text[:100])

    print('Done.')


if __name__ == '__main__':
    main()
