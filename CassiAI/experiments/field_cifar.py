#!/usr/bin/env python
"""
field_cifar.py — Field-Native Generative Model for CIFAR-10

Treats the VkQiCube PDE as a physics-informed denoising/generative kernel.
No byte prediction, no autoregressive loop, no tokenization. The PDE IS
the model — only I/O adapts per modality.

Coordinate mapping: 32×32×3 image → 256 voxels (16×16 spatial grid),
each voxel holds a 2×2×3 pixel block in its first 12 field dims (real).

Phase 0: Fixed mapping, PDE-only denoising (no trainable parameters).
          Tests whether the PDE alone can self-organize structured fields.

Phase 1: Learnable per-pixel amplitude scaling (enc_scale, dec_scale).
          Trained via gradient descent on MSE, PDE treated as fixed physics.

Usage:
    python experiments/field_cifar.py --phase 0 --epochs 5
    python experiments/field_cifar.py --phase 1 --epochs 20 --lr 0.01 --generate 10
"""

import sys
import os
import math
import struct
import argparse
import numpy as np
from pathlib import Path

# Path hack: experiments/ sees vk_qi.py at the parent (repo root)
sys.path.insert(0, str(Path(__file__).parent.parent))
from vk_qi import VkQiCube, N_VOXELS, FIELD_DIM, PHI, PHI_INV

# ──────────────────────────────────────────────────────────────────────
#  Coordinate mapping: CIFAR-10 32×32×3  ⇄  voxel grid 16×16×1
# ──────────────────────────────────────────────────────────────────────

VX_W = 16   # voxel grid width (used)
VX_H = 16   # voxel grid height (used)
VX_D = 1    # voxel grid depth (all in plane 0)

# Image dimensions
IMG_H = 32
IMG_W = 32
IMG_C = 3

# Each 2×2 pixel block → 1 voxel.  Block coords (by, bx) = (y//2, x//2).
# Within a voxel: dim = ((y%2) * 2 + (x%2)) * 3 + c   → range 0–11.
# All values stored in real components; imaginary set to 0.

def voxel_index(h, w, d):
    """Linear index into psi for voxel (h, w, d)."""
    return h + w * VX_W + d * (VX_W * VX_H)

def psi_offset(voxel, dim):
    """Byte offset for the real component of field(voxel, dim)."""
    return (voxel * FIELD_DIM * 2 + dim * 2) * 4

def encode_image(img, psi_flat=None):
    """
    Encode a (32, 32, 3) float image into the flat psi byte array.

    Args:
        img: (32, 32, 3) numpy array, values in [0, 1] or [-1, 1].
        psi_flat: existing (N_VOXELS * FIELD_DIM * 2,) float array or None.

    Returns:
        psi: flat float array of shape (N_VOXELS * FIELD_DIM * 2,).
    """
    if psi_flat is None:
        psi_flat = np.zeros(N_VOXELS * FIELD_DIM * 2, dtype=np.float32)
    # Flatten loops via mesh for speed
    yx = np.mgrid[0:IMG_H, 0:IMG_W]
    yy, xx = yx[0].ravel(), yx[1].ravel()
    for c in range(IMG_C):
        hh = yy // 2
        ww = xx // 2
        dd = 0
        dims = ((yy % 2) * 2 + (xx % 2)) * IMG_C + c
        for i in range(len(yy)):
            v = voxel_index(hh[i], ww[i], dd)
            off = v * FIELD_DIM * 2 + dims[i] * 2
            psi_flat[off] = img[yy[i], xx[i], c]
    return psi_flat

def decode_image(psi_flat):
    """
    Decode a flat psi float array back to a (32, 32, 3) float image.

    Args:
        psi_flat: flat float array of shape (N_VOXELS * FIELD_DIM * 2,).

    Returns:
        img: (32, 32, 3) numpy array.
    """
    img = np.zeros((IMG_H, IMG_W, IMG_C), dtype=np.float32)
    yx = np.mgrid[0:IMG_H, 0:IMG_W]
    yy, xx = yx[0].ravel(), yx[1].ravel()
    for c in range(IMG_C):
        hh = yy // 2
        ww = xx // 2
        dd = 0
        dims = ((yy % 2) * 2 + (xx % 2)) * IMG_C + c
        for i in range(len(yy)):
            v = voxel_index(hh[i], ww[i], dd)
            off = v * FIELD_DIM * 2 + dims[i] * 2
            img[yy[i], xx[i], c] = psi_flat[off]
    return img

# ──────────────────────────────────────────────────────────────────────
#  Dummy data (no torch dependency)
# ──────────────────────────────────────────────────────────────────────

def make_dummy_images(n=100, h=32, w=32, c=3):
    """Generate synthetic 'images' (random noise + structure) for testing."""
    imgs = []
    for i in range(n):
        # A blob that moves with i
        xc = int(w * 0.3 + (i / n) * w * 0.4)
        yc = int(h * 0.4)
        canvas = np.random.randn(h, w, c).astype(np.float32) * 0.1
        rr = 6
        for dy in range(-rr, rr + 1):
            for dx in range(-rr, rr + 1):
                ny, nx = yc + dy, xc + dx
                if 0 <= ny < h and 0 <= nx < w and dy*dy + dx*dx <= rr*rr:
                    canvas[ny, nx, :] += 0.5
        # Clip to reasonable range
        canvas = np.clip(canvas, -1.0, 1.0)
        imgs.append(canvas)
    return imgs

def load_cifar10_subset(n=5000):
    """Load CIFAR-10 training images using torchvision if available."""
    try:
        from torchvision import datasets, transforms
        import torch
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        ])
        dataset = datasets.CIFAR10(root='./data', train=True, download=True,
                                   transform=transform)
        imgs = []
        for i in range(min(n, len(dataset))):
            img_tensor, _ = dataset[i]
            # Convert (3,32,32) to (32,32,3), [-1,1] range
            img = img_tensor.permute(1, 2, 0).numpy().astype(np.float32)
            imgs.append(img)
        print(f'Loaded {len(imgs)} CIFAR-10 images')
        return imgs
    except ImportError:
        print('torchvision not available — using synthetic images')
        return make_dummy_images(n, 32, 32, 3)

# ──────────────────────────────────────────────────────────────────────
#  Training  (Phase 0: PDE-only, Phase 1: learnable scaling)
# ──────────────────────────────────────────────────────────────────────

def train_phase0(engine, images, epochs=5, sigma_max=0.5, k_steps=5):
    """Phase 0: Fixed mapping, PDE-only denoising. No trainable params."""
    print(f'Phase 0: {len(images)} images, {epochs} epochs, sigma_max={sigma_max}')
    psi_buf = np.zeros(N_VOXELS * FIELD_DIM * 2, dtype=np.float32)
    for epoch in range(epochs):
        total_mse = 0.0
        for i, img in enumerate(images):
            # 1. Encode
            encode_image(img, psi_buf)
            engine._upload('psi', psi_buf.tobytes())

            # 2. PDE with noise
            sigma = np.random.uniform(0, sigma_max) if sigma_max > 0 else 0.0
            engine.run_pde(k_steps=k_steps, sigma=sigma)

            # 3. Decode
            psi_out = np.array(engine._read_result('psi', 0,
                N_VOXELS * FIELD_DIM * 2 * 4, 'f'), dtype=np.float32)
            img_out = decode_image(psi_out)

            # 4. MSE
            mse = np.mean((img_out - img) ** 2)
            total_mse += mse
            if i % 50 == 0:
                print(f'  epoch {epoch} img {i:4d}: MSE={mse:.6f} sigma={sigma:.2f}')
        avg_mse = total_mse / len(images)
        print(f'Epoch {epoch} done: avg MSE={avg_mse:.6f}')
    return avg_mse

def train_phase1(engine, images, epochs=20, lr=0.01, sigma_max=0.5, k_steps=5):
    """Phase 1: Learnable per-pixel encoder/decoder amplitude scales."""
    print(f'Phase 1: {len(images)} images, {epochs} epochs, lr={lr}, sigma_max={sigma_max}')
    # Initialize learnable scales
    enc_scale = np.ones((IMG_H, IMG_W, IMG_C), dtype=np.float32)
    dec_scale = np.ones((IMG_H, IMG_W, IMG_C), dtype=np.float32)

    psi_buf = np.zeros(N_VOXELS * FIELD_DIM * 2, dtype=np.float32)
    for epoch in range(epochs):
        total_mse = 0.0
        for i, img in enumerate(images):
            # 1. Encode with scale
            psi_buf.fill(0)
            scaled = img * enc_scale
            encode_image(scaled, psi_buf)
            engine._upload('psi', psi_buf.tobytes())

            # 2. PDE with noise
            sigma = np.random.uniform(0, sigma_max) if sigma_max > 0 else 0.0
            engine.run_pde(k_steps=k_steps, sigma=sigma)

            # 3. Decode
            psi_out = np.array(engine._read_result('psi', 0,
                N_VOXELS * FIELD_DIM * 2 * 4, 'f'), dtype=np.float32)
            img_raw = decode_image(psi_out)
            img_out = img_raw * dec_scale

            # 4. MSE + gradients
            error = img_out - img  # (32, 32, 3)
            mse = np.mean(error ** 2)
            total_mse += mse

            # Gradient for dec_scale (exact: dL/d(dec) = 2*error*img_raw / N)
            grad_dec = 2.0 * error * img_raw / (IMG_H * IMG_W * IMG_C)
            dec_scale -= lr * grad_dec
            dec_scale = np.clip(dec_scale, 0.01, 10.0)

            # Gradient for enc_scale (approximate via finite-difference heuristic)
            # Since we can't backprop through the PDE, use a score-function
            # heuristic: scale that increases reconstruction error gets reduced.
            grad_enc_sign = np.sign(error * (img_raw - img))  # + if amplifies error
            enc_scale -= lr * 0.1 * grad_enc_sign * enc_scale
            enc_scale = np.clip(enc_scale, 0.01, 10.0)

            if i % 50 == 0:
                print(f'  epoch {epoch} img {i:4d}: MSE={mse:.6f} sigma={sigma:.2f} '
                      f'enc=[{enc_scale.min():.2f},{enc_scale.max():.2f}] '
                      f'dec=[{dec_scale.min():.2f},{dec_scale.max():.2f}]')
        avg_mse = total_mse / len(images)
        print(f'Epoch {epoch} done: avg MSE={avg_mse:.6f}')
    return avg_mse, enc_scale, dec_scale

# ──────────────────────────────────────────────────────────────────────
#  Generation  (purely in field-space)
# ──────────────────────────────────────────────────────────────────────

def generate_image(engine, enc_scale=None, dec_scale=None,
                   steps=50, sigma_start=1.5, save_path=None):
    """
    Generate a 32×32 image from random field noise via ancestral PDE sampling.

    No autoregressive loop, no byte sampling — the field self-organizes through
    repeated PDE application with decaying noise, then we decode.

    Args:
        engine: VkQiCube instance.
        enc_scale, dec_scale: optional per-pixel scale arrays from Phase 1.
        steps: number of PDE denoising steps.
        sigma_start: initial noise amplitude.
        save_path: if set, save the raw float array as .npy.
    Returns:
        img: (32, 32, 3) float numpy array.
    """
    # Start from random noise
    np.random.seed(int(np.random.randint(0, 2**31 - 1)))
    psi = np.random.randn(N_VOXELS * FIELD_DIM * 2).astype(np.float32) * sigma_start
    engine._upload('psi', psi.tobytes())

    for t in range(steps):
        sigma = sigma_start * (1.0 - t / max(steps - 1, 1))
        engine.run_pde(k_steps=1, sigma=sigma)
        if t % 10 == 0:
            # Sanity: check psi isn't NaN
            psi_chk = np.array(engine._read_result('psi', 0, 128*4, 'f'), dtype=np.float32)
            if np.any(np.isnan(psi_chk)):
                print(f'  WARNING: NaN in psi at step {t}')
                break

    # Final decode
    psi_out = np.array(engine._read_result('psi', 0,
        N_VOXELS * FIELD_DIM * 2 * 4, 'f'), dtype=np.float32)
    img = decode_image(psi_out)
    if dec_scale is not None:
        img = img * dec_scale
    if enc_scale is not None:
        img = img * enc_scale  # propagate encoder scale through

    img = np.clip(img, -2.0, 2.0)

    if save_path:
        np.save(save_path, img)
        print(f'Saved generated image to {save_path}')

    return img

# ──────────────────────────────────────────────────────────────────────
#  Visualization helpers
# ──────────────────────────────────────────────────────────────────────

def img_to_text(img, width=32):
    """Render a small image as ASCII art."""
    # Normalize to [0,1]
    mn, mx = img.min(), img.max()
    if mx - mn > 1e-8:
        img_n = (img - mn) / (mx - mn)
    else:
        img_n = img * 0 + 0.5
    chars = ' .:-=+*#%@'
    lines = []
    for y in range(min(img.shape[0], width)):
        row = img_n[y, :min(img.shape[1], width), 0]  # channel 0 only
        line = ''.join(chars[min(int(v * (len(chars)-1)), len(chars)-1)] for v in row)
        lines.append(line)
    return '\n'.join(lines)

# ──────────────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Field-native CIFAR-10 generative model')
    parser.add_argument('--phase', type=int, default=0, choices=[0, 1],
                        help='0=PDE-only, 1=learnable scaling')
    parser.add_argument('--epochs', type=int, default=5)
    parser.add_argument('--lr', type=float, default=0.01)
    parser.add_argument('--sigma-max', type=float, default=0.5,
                        help='Max noise level for diffusion training')
    parser.add_argument('--pde-steps', type=int, default=5,
                        help='PDE Strang steps per image')
    parser.add_argument('--generate', type=int, default=0,
                        help='Number of images to generate after training')
    parser.add_argument('--gen-steps', type=int, default=30,
                        help='PDE steps during generation')
    parser.add_argument('--gen-sigma', type=float, default=1.5,
                        help='Starting noise level for generation')
    parser.add_argument('--n-images', type=int, default=200,
                        help='Number of images to train on')
    parser.add_argument('--real-data', action='store_true',
                        help='Use real CIFAR-10 data (requires torchvision)')
    args = parser.parse_args()

    # ── Load data ──
    if args.real_data:
        images = load_cifar10_subset(args.n_images)
    else:
        images = make_dummy_images(args.n_images)
        print(f'Using {len(images)} synthetic images (moving blob)')

    # Normalize images to zero-mean for the field
    images_flat = np.stack([img.ravel() for img in images])
    global_mean = images_flat.mean()
    global_std = images_flat.std() + 1e-8
    images = [(img - global_mean) / global_std for img in images]
    print(f'Normalized: mean={global_mean:.3f}, std={global_std:.3f}')

    # ── Create PDE engine ──
    print('Initializing VkQiCube engine...')
    engine = VkQiCube(lam=0.02, lr=0.0, dt=0.2, stride=256, alpha=0.1,
                      mem_blend=0.05, rho_eps=0.95, train_temp=0.1)
    print('Engine ready.')

    # ── Train ──
    if args.phase == 0:
        mse = train_phase0(engine, images, epochs=args.epochs,
                           sigma_max=args.sigma_max, k_steps=args.pde_steps)
        enc_scale = dec_scale = None
    else:
        mse, enc_scale, dec_scale = train_phase1(engine, images, epochs=args.epochs,
                                                  lr=args.lr, sigma_max=args.sigma_max,
                                                  k_steps=args.pde_steps)
        print(f'Final MSE: {mse:.6f}')
        print(f'enc_scale range: [{enc_scale.min():.3f}, {enc_scale.max():.3f}]')
        print(f'dec_scale range: [{dec_scale.min():.3f}, {dec_scale.max():.3f}]')

    # ── Generate ──
    if args.generate > 0:
        out_dir = Path('generated')
        out_dir.mkdir(exist_ok=True)
        for g in range(args.generate):
            img = generate_image(engine, enc_scale, dec_scale,
                                 steps=args.gen_steps, sigma_start=args.gen_sigma,
                                 save_path=out_dir / f'gen_{g:03d}.npy')
            print(f'--- Generated image {g} ---')
            print(img_to_text(img))
            print()

    print('Done.')

if __name__ == '__main__':
    main()
