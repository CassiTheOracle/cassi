"""Test and demo script for DiffusionCord.

Generates synthetic field data (multi-scale sinusoids in D=1040 space),
trains a DiffusionCord denoiser, and evaluates the quality of generated fields.

Usage:
    python test_diffusion_cord.py              # Quick smoke test
    python test_diffusion_cord.py --train      # Full training run
    python test_diffusion_cord.py --train --epochs 50 --lr 1e-3
"""

import argparse
import math
import time
import torch
import torch.nn.functional as F

from cassi.diffusion_cord import DiffusionCord, FieldDenoiser
from cassi.cord import PHI, PHI_INV


def generate_field_batch(B, D, device='cpu'):
    """Generate synthetic field data: multi-scale φ-spaced sinusoids + noise.

    Simulates physics-like fields with structure at different frequency bands,
    mimicking the kind of data the Cord naturally processes.
    """
    x = torch.linspace(0, 4 * math.pi, D, device=device)  # [D]

    # φ-spaced frequencies: slow to fast
    freqs = [PHI ** (-c) * 2.0 for c in range(13)]
    # Random amplitudes and phases per batch element
    amps = torch.rand(B, 13, device=device) * 0.5 + 0.5  # [0.5, 1.0]
    phases = torch.rand(B, 13, device=device) * 2 * math.pi

    field = torch.zeros(B, D, device=device)
    for c in range(13):
        field += amps[:, c:c+1] * torch.sin(freqs[c] * x.unsqueeze(0) + phases[:, c:c+1])

    # Add mild noise to simulate real measurements
    field += torch.randn(B, D, device=device) * 0.05

    # Normalize to unit variance per sample
    std = field.std(dim=-1, keepdim=True).clamp_min(1e-6)
    field = field / std

    return field


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def train_epoch(model, optimizer, B, D, steps_per_epoch, device):
    """Single training epoch."""
    model.train()
    total_loss = 0.0
    for step in range(steps_per_epoch):
        x_0 = generate_field_batch(B, D, device=device)
        optimizer.zero_grad()
        loss = model.training_loss(x_0)
        loss.backward()
        # Gradient clipping for stability
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total_loss += loss.item()
    return total_loss / steps_per_epoch


def evaluate_samples(model, B, D, device, n_samples=4):
    """Draw samples and compute simple quality metrics.

    Returns:
        mean_norm: average L2 norm (should be ~1.0 for normalized data)
        mean_energy: average squared norm
        samples: [n_samples, D] tensor
    """
    model.eval()
    with torch.no_grad():
        samples = model.sample((n_samples, D), device=device, num_steps=100)
        norms = samples.norm(dim=-1)
        energies = (samples ** 2).mean(dim=-1)
    return norms.mean().item(), energies.mean().item(), samples


def compute_frequency_spectrum(field, n_bins=64):
    """Compute power spectrum to check if generated fields have structure."""
    # FFT along last dimension
    fft = torch.fft.rfft(field, dim=-1)
    power = torch.abs(fft) ** 2
    # Bin into log-spaced frequency bins
    n_freqs = power.shape[-1]
    bins = torch.logspace(0, math.log10(n_freqs), n_bins + 1, device=field.device).long()
    bins = bins.clamp(0, n_freqs - 1)
    spectrum = torch.zeros(field.shape[0], n_bins, device=field.device)
    for i in range(n_bins):
        if bins[i] < bins[i + 1]:
            spectrum[:, i] = power[:, bins[i]:bins[i+1]].mean(dim=-1)
    return spectrum


def smoke_test():
    """Minimal smoke test: create model, run one forward/backward pass."""
    print("=" * 60)
    print("Smoke Test: DiffusionCord")
    print("=" * 60)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    D = 1040
    B = 8

    print(f"Device: {device}")
    print(f"Creating DiffusionCord(D={D})...")
    model = DiffusionCord(D=D, num_timesteps=100).to(device)
    n_params = count_parameters(model)
    print(f"Parameters: {n_params:,}")

    # Generate synthetic data
    x_0 = generate_field_batch(B, D, device=device)

    # Training loss
    loss = model.training_loss(x_0)
    print(f"Initial loss: {loss.item():.6f}")

    # Gradient check
    loss.backward()
    grad_norms = []
    for name, p in model.named_parameters():
        if p.grad is not None:
            grad_norms.append(p.grad.norm().item())
    max_grad = max(grad_norms) if grad_norms else 0.0
    print(f"Max gradient norm: {max_grad:.6f}")

    # Sampling
    print("\nSampling (DDPM, 50 steps)...")
    t0 = time.time()
    samples = model.sample((4, D), num_steps=50, device=device)
    dt = time.time() - t0
    sample_norms = samples.norm(dim=-1).mean().item()
    sample_energy = (samples ** 2).mean(dim=-1).mean().item()
    print(f"  Time: {dt:.2f}s")
    print(f"  Mean norm: {sample_norms:.4f}")
    print(f"  Mean energy: {sample_energy:.4f}")

    # DDIM sampling
    print("\nSampling (DDIM, 20 steps, deterministic)...")
    t0 = time.time()
    samples_ddim = model.sample_ddim((4, D), num_steps=20, eta=0.0, device=device)
    dt = time.time() - t0
    ddim_norms = samples_ddim.norm(dim=-1).mean().item()
    print(f"  Time: {dt:.2f}s")
    print(f"  Mean norm: {ddim_norms:.4f}")

    # NaN check
    assert not torch.isnan(loss).any(), "Loss is NaN!"
    assert not torch.isnan(samples).any(), "DDPM samples contain NaN!"
    assert not torch.isnan(samples_ddim).any(), "DDIM samples contain NaN!"

    print("\n✓ All smoke tests passed!")
    return True


def full_training(args):
    """Full training run on synthetic field data."""
    print("=" * 60)
    print("DiffusionCord Training")
    print("=" * 60)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    D = args.D
    B = args.bs

    print(f"Device: {device}")
    print(f"Field dim D: {D}")
    print(f"Batch size: {B}")
    print(f"Epochs: {args.epochs}")
    print(f"Learning rate: {args.lr}")
    print(f"Timesteps: {args.timesteps}")

    model = DiffusionCord(D=D, num_timesteps=args.timesteps).to(device)
    n_params = count_parameters(model)
    print(f"Parameters: {n_params:,}")

    # Filter info
    print("\nChakra configuration:")
    for info in model.filter_info():
        print(f"  Chakra {info['chakra']:2d}: width={info['width']:4d}, "
              f"freq={info['freq']:.4f}, period={info['period']:.1f}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    print(f"\n{'Epoch':>6s} {'Loss':>10s} {'SampleNorm':>12s} {'SampleEnergy':>14s} {'Time':>8s}")
    print("-" * 56)

    for epoch in range(args.epochs):
        t0 = time.time()
        avg_loss = train_epoch(model, optimizer, B, D, args.steps_per_epoch, device)
        scheduler.step()

        # Evaluate every few epochs
        if epoch % 5 == 0 or epoch == args.epochs - 1:
            mean_norm, mean_energy, samples = evaluate_samples(model, B, D, device, n_samples=4)
        else:
            mean_norm, mean_energy = float('nan'), float('nan')

        dt = time.time() - t0
        print(f"{epoch+1:6d} {avg_loss:10.6f} {mean_norm:12.4f} {mean_energy:14.4f} {dt:7.1f}s")

    # Final evaluation
    print("\n" + "=" * 60)
    print("Final Evaluation")
    print("=" * 60)

    # Sample quality
    model.eval()
    with torch.no_grad():
        n_eval = 64
        real = generate_field_batch(n_eval, D, device=device)
        gen = model.sample((n_eval, D), device=device, num_steps=100)

    # Compute statistics
    real_norm_mean = real.norm(dim=-1).mean().item()
    real_norm_std = real.norm(dim=-1).std().item()
    gen_norm_mean = gen.norm(dim=-1).mean().item()
    gen_norm_std = gen.norm(dim=-1).std().item()

    real_energy_mean = (real ** 2).mean().item()
    gen_energy_mean = (gen ** 2).mean().item()

    # Moment matching
    real_cov = torch.cov(real.T)
    gen_cov = torch.cov(gen.T)
    cov_diff = (real_cov - gen_cov).norm().item() / real_cov.norm().item()

    print(f"Real data:  norm={real_norm_mean:.4f}±{real_norm_std:.4f}, energy={real_energy_mean:.4f}")
    print(f"Generated:  norm={gen_norm_mean:.4f}±{gen_norm_std:.4f}, energy={gen_energy_mean:.4f}")
    print(f"Covariance relative difference: {cov_diff:.4f}")
    print(f"  (lower = better match)")

    # Frequency spectrum comparison
    real_spec = compute_frequency_spectrum(real).mean(dim=0)
    gen_spec = compute_frequency_spectrum(gen).mean(dim=0)
    spec_corr = F.cosine_similarity(real_spec.unsqueeze(0), gen_spec.unsqueeze(0)).item()
    print(f"Frequency spectrum cosine similarity: {spec_corr:.4f}")
    print(f"  (higher = better match)")

    # Check for mode collapse (all samples too similar)
    pairwise_dists = torch.cdist(gen[:16], gen[:16])
    mean_pairwise = pairwise_dists.mean().item()
    print(f"Mean pairwise distance (gen): {mean_pairwise:.4f}")
    real_pairwise = torch.cdist(real[:16], real[:16]).mean().item()
    print(f"Mean pairwise distance (real): {real_pairwise:.4f}")

    print("\n✓ Training complete!")


def field_denoiser_demo(args):
    """Demo the FieldDenoiser wrapper for 1024-dim fields."""
    print("=" * 60)
    print("FieldDenoiser Demo")
    print("=" * 60)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    D = args.D
    B = args.bs

    print(f"Device: {device}")
    print(f"Creating FieldDenoiser with D={D}...")

    model = FieldDenoiser(D=D, num_timesteps=args.timesteps).to(device)
    n_params = count_parameters(model)
    print(f"Parameters: {n_params:,}")

    # Generate 1024-dim fields
    print("\nGenerating synthetic 1024-dim fields...")
    x_1024 = torch.randn(B, 1024, device=device)
    x_1024 = x_1024 / x_1024.std(dim=-1, keepdim=True)

    # Encode → train → decode
    z_0 = model.encoder(x_1024)
    print(f"Encoded shape: {z_0.shape} (expected [{B}, {D}])")

    loss = model.training_loss(x_1024)
    print(f"Initial loss: {loss.item():.6f}")

    # Train a few steps
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    print(f"\nTraining {args.epochs} epochs...")
    for epoch in range(args.epochs):
        x_batch = torch.randn(B, 1024, device=device)
        x_batch = x_batch / x_batch.std(dim=-1, keepdim=True)
        optimizer.zero_grad()
        loss = model.training_loss(x_batch)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if epoch % 10 == 0 or epoch == args.epochs - 1:
            print(f"  Epoch {epoch+1:3d}: loss={loss.item():.6f}")

    # Sample
    print("\nSampling from FieldDenoiser...")
    with torch.no_grad():
        samples = model.sample(4, device=device)
    print(f"  Sample shape: {samples.shape}")
    print(f"  Sample norm: {samples.norm(dim=-1).mean().item():.4f}")

    print("\n✓ FieldDenoiser demo complete!")


def main():
    parser = argparse.ArgumentParser(description='DiffusionCord test and training')
    parser.add_argument('--train', action='store_true', help='Run full training')
    parser.add_argument('--field-denoise', action='store_true', help='Run FieldDenoiser demo')
    parser.add_argument('--epochs', type=int, default=30, help='Training epochs')
    parser.add_argument('--lr', type=float, default=1e-3, help='Learning rate')
    parser.add_argument('--bs', type=int, default=32, help='Batch size')
    parser.add_argument('--D', type=int, default=1040, help='Field dimension')
    parser.add_argument('--timesteps', type=int, default=100, help='Diffusion timesteps (use 100 for speed, 1000+ for quality)')
    parser.add_argument('--steps-per-epoch', type=int, default=50, help='Batches per epoch')
    args = parser.parse_args()

    # Always run smoke test first
    if not smoke_test():
        print("\n✗ Smoke test failed. Aborting.")
        return 1

    if args.field_denoise:
        field_denoiser_demo(args)

    if args.train:
        full_training(args)

    return 0


if __name__ == '__main__':
    exit(main())
