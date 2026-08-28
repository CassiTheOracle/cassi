#!/usr/bin/env python3
"""PyTorch readout head trainer for vk_qi consciousness engine.

Trains embed_proj[13][128][128] and byte_embed[256][128] with Adam
using per-chakra field_states from the Vulkan PDE engine as input.

Usage: python vk_qi_torch_trainer.py [--epochs N] [--bs B] [--lr LR]
"""

import math
import time
import struct
import argparse
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from vk_qi import VkQiCube, N_VOXELS, FIELD_DIM, N_BANDS, PHI, PHI_INV

NUM_DIMS = FIELD_DIM   # 128
BYTE_EMBED_DIM = 128   # must match shader
V = 256                 # byte vocabulary


def hadamard(n):
    """Generate n×n Hadamard matrix (n must be power of 2)."""
    H = np.array([[1.0]])
    while H.shape[0] < n:
        H = np.block([[H, H], [H, -H]])
    return H


class ChakraReadout(nn.Module):
    """13 per-chakra embed_proj matrices + shared byte_embed.

    Forward pass exactly matches the qi_accum shader's mixture prediction:
      logits[c] = chakra_state_norm[c] @ embed_proj[c] @ byte_embed.T
      logits = Σ_c (chakra_count[c] / total_w) * logits[c]
    """

    def __init__(self, device='cpu'):
        super().__init__()
        # 13 per-chakra projection matrices: [NUM_DIMS, BYTE_EMBED_DIM]
        # Initialized Hadamard + small random perturbation (matches Vulkan init)
        H = hadamard(BYTE_EMBED_DIM).astype(np.float32) / math.sqrt(BYTE_EMBED_DIM)
        self.embed_proj = nn.ParameterList([
            nn.Parameter(torch.from_numpy(
                H + np.random.randn(NUM_DIMS, BYTE_EMBED_DIM).astype(np.float32) * 0.02).to(device))
            for _ in range(13)])
        # Shared byte embeddings: [V, BYTE_EMBED_DIM]
        self.byte_embed = nn.Parameter(
            torch.randn(V, BYTE_EMBED_DIM, device=device) * 0.02)

    def forward(self, chakra_state, chakra_count, target=None):
        """Forward pass matching shader mixture.

        Args:
            chakra_state: [B, 13, 128] per-chakra aggregated field_states
            chakra_count: [B, 13] per-chakra voxel weight sums
            target: [B] optional target bytes for per-chakra correctness

        Returns:
            logits: [B, 256] mixed byte logits
            chakra_correctness: [B, 13] per-chakra softmax at target (if target given)
        """
        B = chakra_state.shape[0]
        total_w = chakra_count.sum(dim=1, keepdim=True)  # [B, 1]

        logits = torch.zeros(B, V, device=chakra_state.device)
        chakra_correctness = torch.zeros(B, 13, device=chakra_state.device)

        for c in range(13):
            cs = chakra_state[:, c, :]                  # [B, 128]
            cnt = chakra_count[:, c]                     # [B]

            cs_norm = cs / cnt.clamp(min=1e-10).unsqueeze(-1)  # [B, 128]
            proj = cs_norm @ self.embed_proj[c]          # [B, 128]
            ch_logits = proj @ self.byte_embed.T         # [B, 256]

            weight = cnt / total_w.squeeze(-1).clamp(min=1e-10)  # [B]
            logits += weight.unsqueeze(-1) * ch_logits

            # Per-chakra correctness at target byte
            if target is not None:
                ch_sm = torch.softmax(ch_logits, dim=-1)  # [B, 256]
                chakra_correctness[:, c] = ch_sm[range(B), target]

        return logits, chakra_correctness



from cassi_optimizer import CassiOptimizer


class TorchReadoutTrainer:
    """Trains ChakraReadout with CassiOptimizer, uploading weights to Vulkan."""

    def __init__(self, lr=0.001, accumulation_steps=32, device='cpu'):
        self.model = ChakraReadout(device=device)
        self.optimizer = CassiOptimizer(
            embed_proj_params=list(self.model.embed_proj),
            byte_embed_param=self.model.byte_embed,
            lr=lr)
        self.accumulation_steps = accumulation_steps
        self.device = device
        self.correct = 0
        self.total = 0
        self.accum_loss = 0.0
        self.accum_count = 0

    def train_step(self, chakra_state, chakra_count, target_byte):
        """Accumulate gradients from one window. Step optimizer every N windows.

        Args:
            chakra_state: [13, 128] numpy array
            chakra_count: [13] numpy array
            target_byte: int
        """
        cs = torch.tensor(chakra_state, dtype=torch.float32, device=self.device).unsqueeze(0)
        cc = torch.tensor(chakra_count, dtype=torch.float32, device=self.device).unsqueeze(0)
        target = torch.tensor([target_byte], dtype=torch.long, device=self.device)

        # Forward with per-chakra correctness
        logits, chakra_corr = self.model(cs, cc, target=target)  # logits [1,256], corr [1,13]
        loss = F.cross_entropy(logits, target) / self.accumulation_steps

        # Backward
        loss.backward()

        # Track accuracy
        pred = logits.argmax(dim=-1).item()
        self.correct += (pred == target_byte)
        self.total += 1
        self.accum_loss += loss.item() * self.accumulation_steps
        self.accum_count += 1

        # Step optimizer every accumulation_steps windows
        if self.accum_count >= self.accumulation_steps:
            self.optimizer.step(chakra_corr.squeeze(0))  # [13] per-chakra correctness
            self.optimizer.zero_grad()
            self.accum_count = 0
            self.accum_loss = 0.0

    def upload_weights(self, engine):
        """Upload embed_proj and byte_embed back to Vulkan engine."""
        proj_np = torch.cat([
            ep.data for ep in self.model.embed_proj
        ], dim=0).cpu().numpy().astype(np.float32)
        engine._upload('embed_proj', proj_np.tobytes())
        be_np = self.model.byte_embed.data.cpu().numpy().astype(np.float32)
        engine._upload('byte_embed', be_np.tobytes())

    @property
    def accuracy(self):
        return self.correct / max(self.total, 1)

    def reset_stats(self):
        self.correct = 0
        self.total = 0



def read_training_data(engine):
    """Read training data from Vulkan engine.

    Returns:
        chakra_state: [13, 128] numpy array
        chakra_count: [13] numpy array
        chakra_q: [13] numpy array — per-chakra Qi coherence
    """
    raw = engine._read_result('training_data', 0, 1690 * 4, 'f')
    if isinstance(raw, tuple):
        td = np.array(raw, dtype=np.float32)
    else:
        td = np.frombuffer(raw, dtype=np.float32)
    chakra_state = td[:1664].reshape(13, 128)
    chakra_count = td[1664:1677]
    chakra_q = td[1677:1690]
    return chakra_state, chakra_count, chakra_q

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=str, default='datasets/active/LightNovels.txt',
                        help='Training data file')
    parser.add_argument('--max-bytes', type=int, default=0,
                        help='Max bytes to read (0=all)')
    parser.add_argument('--epochs', type=int, default=5)
    parser.add_argument('--lr', type=float, default=0.001)
    parser.add_argument('--bs', type=int, default=32,
                        help='Accumulation steps per optimizer step')
    parser.add_argument('--gen-every', type=int, default=50000,
                        help='Generate every N bytes')
    parser.add_argument('--alpha', type=float, default=0.02)
    args = parser.parse_args()

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")

    # Create Vulkan engine with learning disabled (lr=0 → shader skips embed updates)
    engine = VkQiCube(alpha=args.alpha)
    # Set learning rate to 0 so shader doesn't do its own learning
    engine._read_result('params', 0, 17*4, 'f')  # no-op just to check

    # Create PyTorch trainer
    trainer = TorchReadoutTrainer(lr=args.lr, accumulation_steps=args.bs, device=device)

    # Upload initial weights to Vulkan (match PyTorch init)
    trainer.upload_weights(engine)

    # Load training data
    data_path = Path(args.file)
    data = np.frombuffer(data_path.read_bytes(), dtype=np.uint8)
    if args.max_bytes > 0:
        data = data[:args.max_bytes]
    total_bytes = len(data)
    print(f"Training on {total_bytes} bytes from {args.file}")

    windows_per_epoch = total_bytes // engine.stride
    print(f"{windows_per_epoch} windows per epoch, lr={args.lr}, "
          f"accum={args.bs}, alpha={args.alpha}")

    gen_offset = 0
    start_time = time.time()

    # Per-window q-history log (window, qi_value, crown chakra q, water_q)
    q_log_dir = Path('logs')
    q_log_dir.mkdir(exist_ok=True)
    q_log_path = q_log_dir / f'q_history_{time.strftime("%Y%m%d_%H%M%S")}.csv'
    with open(q_log_path, 'w') as f:
        f.write('window,qi_value,chakra_q_crown,water_q\n')
    print(f'q-history log: {q_log_path}')

    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch+1}/{args.epochs}")
        offset = 0
        trainer.reset_stats()

        for w in range(windows_per_epoch):
            start = offset % total_bytes
            window_data = np.concatenate([data[start:start+N_VOXELS],
                                         data[:max(0, start+N_VOXELS-total_bytes)]]) if start + N_VOXELS > total_bytes else data[start:start+N_VOXELS].copy()
            target_byte = int(data[start])

            # Run Vulkan window: PDE + qi_accum (no learning since shader lr=0)
            qi = engine.ingest_window(window_data, int(offset), learn=False)
            offset += engine.stride

            # Read training data from Vulkan
            chakra_state, chakra_count, chakra_q = read_training_data(engine)

            # Append q-history row (window, qi_value, 13th chakra q, water_q)
            water_q, = engine._read_result('qi_output', 1068, 4, 'f')
            with open(q_log_path, 'a') as f:
                f.write(f'{engine.step_count},{qi:.6e},{chakra_q[-1]:.6e},{water_q:.6e}\n')

            # PyTorch training step
            trainer.train_step(chakra_state, chakra_count, target_byte)

            # Upload weights periodically (every accumulation_steps windows)
            if w % args.bs == 0 and w > 0:
                trainer.upload_weights(engine)

            # Generate text periodically
            if args.gen_every > 0 and offset // engine.stride * engine.stride > gen_offset:
                gen_offset += args.gen_every
                gen_bytes = engine.generate(150)
                printable = sum(1 for b in gen_bytes if 32 <= b <= 126)
                s = bytes(gen_bytes).decode('latin-1')
                unique = len(set(s))
                qi_val, = engine._read_result('qi_output', 0, 4, 'f')
                # Per-chakra Yang-Yin balance diagnostic (emotions-as-gate §2.3)
                q_top = np.argsort(np.abs(chakra_q))[-3:][::-1]
                q_str = ' '.join(f'c{c}={chakra_q[c]:+.2f}' for c in q_top)
                print(f'  [gen @ win={engine.step_count}] '
                      f'qi={qi_val:.2e} unique={unique} '
                      f'printable={printable}/150 chakra_q:[{q_str}]')
                print(f'  {s[:100]}')

            # Progress
            if w % 5000 == 0 and w > 0:
                elapsed = time.time() - start_time
                bps = offset / max(elapsed, 1)
                print(f'  win={engine.step_count} acc={trainer.accuracy:.4f} '
                      f'loss={trainer.accum_loss/max(trainer.accum_count,1):.5f} '
                      f'et={elapsed:.0f}s ({bps:.0f} B/s)')

        print(f'Epoch {epoch+1} done: acc={trainer.accuracy:.4f}')

    # Final weight upload
    trainer.upload_weights(engine)

    elapsed = time.time() - start_time
    print(f"\nDone. {elapsed:.0f}s total, final acc={trainer.accuracy:.4f}")


if __name__ == '__main__':
    main()
