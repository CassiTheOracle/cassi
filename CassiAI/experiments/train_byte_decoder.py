#!/usr/bin/env python3
"""Train a ByteDecoder for the frozen byte_encoder in the text spine."""

import torch
import torch.nn.functional as F
import numpy as np
import time
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.text_codec import ByteDecoder

DEV = 'cuda'


def load_text_bytes(path='datasets/TinyStories-Instruct-train.txt', max_gb=2):
    """Load text file as raw bytes, capped at max_gb."""
    max_bytes = int(max_gb * 1024**3)
    if not os.path.exists(path):
        # Fallback: find first large .txt in datasets/active/
        active = 'datasets/active'
        if os.path.exists(active):
            for f in sorted(os.listdir(active)):
                if f.endswith('.txt'):
                    path = os.path.join(active, f)
                    break
    with open(path, 'rb') as f:
        data = f.read(max_bytes)
    print(f"Loaded {len(data):,} bytes from {path}")
    return np.frombuffer(data, dtype=np.uint8)


def main():
    print("Loading spine checkpoint...")
    ck = torch.load('checkpoints/spine_text.pt', map_location=DEV, weights_only=False)
    state = ck['model'] if isinstance(ck, dict) and 'model' in ck else ck

    # Extract byte_encoder weights
    enc_state = {k.replace('spine.byte_encoder.', ''): v
                 for k, v in state.items() if k.startswith('spine.byte_encoder.')}

    # Reconstruct byte_encoder
    from cassi.text_codec import ByteEncoder
    window_bytes = 1024
    chunk = 256
    dim_field = 1024
    byte_enc = ByteEncoder(window_bytes=window_bytes, dim_field=dim_field, T=4).to(DEV)
    byte_enc.load_state_dict(enc_state, strict=True)
    byte_enc.eval()
    for p in byte_enc.parameters():
        p.requires_grad = False

    print(f"byte_encoder loaded: chunk={chunk}, dim_field={dim_field}")

    # Load real text data
    text_bytes = load_text_bytes()

    # Create larger decoder
    class LargeByteDecoder(torch.nn.Module):
        def __init__(self, dim_field=1024, chunk=256):
            super().__init__()
            self.chunk = chunk
            self.net = torch.nn.Sequential(
                torch.nn.Linear(dim_field, 1024),
                torch.nn.GELU(),
                torch.nn.Linear(1024, 1024),
                torch.nn.GELU(),
                torch.nn.Linear(1024, chunk * 256)
            )
        def forward(self, field):
            return self.net(field).view(-1, self.chunk, 256)

    decoder = LargeByteDecoder(dim_field=dim_field, chunk=chunk).to(DEV)
    opt = torch.optim.AdamW(decoder.parameters(), lr=2e-3, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=5000, eta_min=1e-4)

    batch_size = 8192
    steps = 5000
    t_start = time.perf_counter()

    for step in range(steps):
        # Sample random windows from real text
        starts = np.random.randint(0, len(text_bytes) - chunk, size=batch_size)
        idx = np.arange(chunk)
        raw_np = text_bytes[starts[:, None] + idx[None, :]]
        raw = torch.from_numpy(raw_np).to(DEV, dtype=torch.uint8)

        # Encode through frozen encoder
        with torch.no_grad():
            remapped = byte_enc.remap[raw.long()]
            field = byte_enc.proj(remapped)

        # Decode
        logits = decoder(field)
        loss = F.cross_entropy(logits.view(-1, 256), raw.long().view(-1))

        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(decoder.parameters(), 1.0)
        opt.step()
        scheduler.step()

        if (step + 1) % 500 == 0:
            elapsed = time.perf_counter() - t_start
            acc = (logits.argmax(dim=-1) == raw).float().mean().item()
            print(f"  step {step+1:5d}  loss={loss.item():.4f}  acc={acc:.4f}  lr={scheduler.get_last_lr()[0]:.2e}  [{elapsed:.1f}s]")

    # Final eval
    with torch.no_grad():
        starts = np.random.randint(0, len(text_bytes) - chunk, size=batch_size)
        idx = np.arange(chunk)
        raw_np = text_bytes[starts[:, None] + idx[None, :]]
        raw = torch.from_numpy(raw_np).to(DEV, dtype=torch.uint8)
        remapped = byte_enc.remap[raw.long()]
        field = byte_enc.proj(remapped)
        logits = decoder(field)
        acc = (logits.argmax(dim=-1) == raw).float().mean().item()
        print(f"\nFinal accuracy: {acc:.4f}")

    torch.save({'decoder': decoder.state_dict(), 'chunk': chunk, 'dim_field': dim_field,
                'accuracy': acc}, 'checkpoints/byte_decoder.pt')
    print("Saved checkpoints/byte_decoder.pt")


if __name__ == '__main__':
    main()
