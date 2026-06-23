#!/usr/bin/env python3
"""Fit WaveByteEncoder to match an existing ByteEncoder's field output.

This lets us swap encoders without retraining the entire model.
"""

import torch
import torch.nn.functional as F
import numpy as np
import time
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.text_codec import ByteEncoder, WaveByteEncoder

DEV = 'cuda'


def main():
    print("Loading old encoder from spine_text.pt...")
    ck = torch.load('checkpoints/spine_text.pt', map_location=DEV, weights_only=False)
    state = ck['model'] if isinstance(ck, dict) and 'model' in ck else ck

    # Extract old byte_encoder weights
    enc_state = {k.replace('spine.byte_encoder.', ''): v
                 for k, v in state.items() if k.startswith('spine.byte_encoder.')}

    old_enc = ByteEncoder(window_bytes=1024, dim_field=1024, T=4).to(DEV)
    old_enc.load_state_dict(enc_state, strict=True)
    old_enc.eval()
    for p in old_enc.parameters():
        p.requires_grad = False

    print("Old encoder loaded")

    # Create wave encoder
    wave_enc = WaveByteEncoder(window_bytes=1024, dim_field=1024, T=4).to(DEV)

    # Load text data for fitting
    print("Loading text data...")
    with open('datasets/TinyStories-Instruct-train.txt', 'rb') as f:
        data = np.frombuffer(f.read(200_000_000), dtype=np.uint8)

    chunk = 256
    opt = torch.optim.AdamW([wave_enc.gain], lr=1e-2, weight_decay=0.0)

    batch_size = 4096
    steps = 2000
    t_start = time.perf_counter()

    for step in range(steps):
        # Sample random byte windows
        starts = np.random.randint(0, len(data) - 1024, size=batch_size)
        idx = np.arange(1024)
        raw_np = data[starts[:, None] + idx[None, :]]
        raw = torch.from_numpy(raw_np).to(DEV, dtype=torch.uint8)

        # Encode with old encoder (T=4, full window)
        with torch.no_grad():
            old_field = old_enc.encode_sequence(raw, T=4)  # [B, 4, 1024]

        # Encode with wave encoder (T=4, full window)
        wave_field = wave_enc.encode_sequence(raw, T=4)  # [B, 4, 1024]

        # Match them
        loss = F.mse_loss(wave_field, old_field)

        opt.zero_grad()
        loss.backward()
        opt.step()

        if (step + 1) % 200 == 0:
            elapsed = time.perf_counter() - t_start
            print(f"  step {step+1:5d}  loss={loss.item():.6f}  [{elapsed:.1f}s]")

    # Final eval
    with torch.no_grad():
        starts = np.random.randint(0, len(data) - 1024, size=batch_size)
        raw_np = data[starts[:, None] + idx[None, :]]
        raw = torch.from_numpy(raw_np).to(DEV, dtype=torch.uint8)
        old_field = old_enc.encode_sequence(raw, T=4)
        wave_field = wave_enc.encode_sequence(raw, T=4)
        final_mse = F.mse_loss(wave_field, old_field).item()
        final_mae = F.l1_loss(wave_field, old_field).item()
        print(f"\nFinal MSE: {final_mse:.6f}")
        print(f"Final MAE: {final_mae:.6f}")

    # Save wave encoder
    torch.save({
        'wave_encoder': wave_enc.state_dict(),
        'mse': final_mse,
        'mae': final_mae,
    }, 'checkpoints/wave_encoder_fitted.pt')
    print("Saved checkpoints/wave_encoder_fitted.pt")

    # Test round-trip decode quality on exact old fields
    print("\nTesting decode quality on exact old fields...")
    with torch.no_grad():
        # Single chunk test
        raw_chunk = torch.randint(0, 256, (1000, 256), device=DEV, dtype=torch.uint8)
        old_field = old_enc.encode_sequence(raw_chunk, T=1).squeeze(1)  # [B, 1024]

        # Decode old field with old decoder
        old_decoded = old_enc.decode_field(old_field)
        old_acc = (old_decoded == raw_chunk[:, :256]).float().mean().item()

        # Decode old field with wave decoder (after wave encoding)
        wave_field = wave_enc.encode_sequence(raw_chunk, T=1).squeeze(1)
        wave_decoded = wave_enc.decode(wave_field)
        wave_acc = (wave_decoded == raw_chunk[:, :256]).float().mean().item()

        print(f"  Old decoder on old fields: {old_acc:.4f}")
        print(f"  Wave decoder on wave fields: {wave_acc:.4f}")


if __name__ == '__main__':
    main()
