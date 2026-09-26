"""Demonstration: MnemosyneCord as a standalone associative memory.

Trains the chord to memorise a set of random patterns, then tests recall
from noisy / partial cues.  This validates the "ultimate compression" idea:
the chord stores patterns in its resonant attractor landscape and retrieves
them via energy minimisation.
"""

import torch
import torch.nn.functional as F

from cassi.mnemosyne_cord import MnemosyneCord, HybridCord


def demo_standalone_memory():
    print("=" * 60)
    print("MnemosyneCord: Standalone Associative Memory Demo")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    D = 512
    input_dim = 256
    n_patterns = 128
    n_slots = 256

    # Small chord for fast training
    cord = MnemosyneCord(
        D=D,
        input_dim=input_dim,
        n_slots=n_slots,
        attractor_steps=4,
        working_memory_decay=0.9,
    ).to(device)

    opt = torch.optim.Adam(cord.parameters(), lr=1e-3)

    # Generate a fixed set of random patterns to memorise
    torch.manual_seed(42)
    patterns = torch.randn(n_patterns, input_dim, device=device)

    print(f"\nMemorising {n_patterns} random {input_dim}-dim patterns...")
    print(f"Chord capacity: {n_slots} slots | Internal dim: {D}")

    # Training: autoencode with noise
    for epoch in range(30):
        total_loss = 0.0
        total_recon = 0.0
        total_sep = 0.0

        # Shuffle patterns each epoch
        perm = torch.randperm(n_patterns)
        batch_size = 16

        for i in range(0, n_patterns, batch_size):
            idx = perm[i : i + batch_size]
            batch = patterns[idx]

            # Store (no grad) then recall from noisy cue (with grad)
            cord.reset_working_memory(batch_size)
            with torch.no_grad():
                cord.store(batch)

            # Training recall: cue = pattern + noise
            noise_scale = 0.2 + 0.1 * torch.randn(1).item()
            cue = batch + noise_scale * torch.randn_like(batch)
            recalled = cord.recall(cue, steps=4, temperature=0.5)

            # Losses
            loss_recon = F.mse_loss(recalled, batch)

            # Separation: distinct patterns should have distinct signatures
            sig_clean, _, _ = cord.encode(batch)
            sig_clean = F.normalize(sig_clean, dim=-1)
            sim_matrix = sig_clean @ sig_clean.T
            eye_mask = ~torch.eye(batch_size, dtype=torch.bool, device=device)
            loss_sep = -sim_matrix[eye_mask].mean() + 1.0  # push away from 1.0

            loss = loss_recon + 0.1 * loss_sep

            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(cord.parameters(), 1.0)
            opt.step()

            total_loss += loss.item()
            total_recon += loss_recon.item()
            total_sep += loss_sep.item()

        if (epoch + 1) % 5 == 0:
            stats = cord.memory_stats()
            print(
                f"  Epoch {epoch+1:2d} | "
                f"loss={total_loss:.4f} recon={total_recon:.4f} sep={total_sep:.4f} | "
                f"mem={stats['filled']}/{stats['capacity']}"
            )

    # --- Test recall quality ---
    print("\n--- Recall Quality Test ---")
    cord.reset_working_memory()
    with torch.no_grad():
        cord.store(patterns)  # store all clean patterns

    # Test 1: recall from noise
    noise_levels = [0.0, 0.1, 0.2, 0.3, 0.5, 1.0]
    print("\nNoise robustness:")
    for noise in noise_levels:
        noisy = patterns + noise * torch.randn_like(patterns)
        recalled = cord.recall(noisy, steps=4, temperature=0.5)
        mse = F.mse_loss(recalled, patterns).item()
        print(f"  noise={noise:.1f} → MSE={mse:.6f}")

    # Test 2: recall from partial (zero out random 50% of dims)
    print("\nPartial cue robustness (50% masked):")
    mask = torch.rand_like(patterns) > 0.5
    partial = patterns * mask.float()
    recalled = cord.recall(partial, steps=4, temperature=0.5)
    mse = F.mse_loss(recalled, patterns).item()
    print(f"  50% masked → MSE={mse:.6f}")

    # Test 3: attractor trajectory
    print("\nAttractor convergence (single pattern, noise=0.3):")
    test_pat = patterns[0:1]
    noisy = test_pat + 0.3 * torch.randn_like(test_pat)
    _, trajectory = cord.recall(noisy, steps=8, temperature=0.5, return_trajectory=True)
    for step, traj in enumerate(trajectory):
        mse = F.mse_loss(traj, test_pat).item()
        print(f"  step {step+1}: MSE={mse:.6f}")

    stats = cord.memory_stats()
    print(f"\nFinal memory stats: {stats}")
    print("\nDemo complete!")


def demo_hybrid_compression():
    print("\n" + "=" * 60)
    print("HybridCord: Shared Encoding for Prediction + Memory")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    D = 512
    input_dim = 256

    cord = HybridCord(D=D, input_dim=input_dim, n_slots=256).to(device)
    opt = torch.optim.Adam(cord.parameters(), lr=1e-3)

    # Generate sequences: each sequence is a smooth interpolation between two patterns
    torch.manual_seed(42)
    n_seq = 64
    seq_len = 8
    anchors = torch.randn(n_seq, 2, input_dim, device=device)
    sequences = []
    for i in range(n_seq):
        t = torch.linspace(0, 1, seq_len + 1, device=device).unsqueeze(-1)  # (seq_len+1, 1)
        seq = (1 - t) * anchors[i, 0] + t * anchors[i, 1]  # (seq_len+1, input_dim)
        sequences.append(seq)
    sequences = torch.stack(sequences)  # (n_seq, seq_len+1, input_dim)

    print(f"\nTraining on {n_seq} smooth sequences (length {seq_len}+1)...")
    print("Loss = prediction_error + 0.1 * memory_reconstruction_error")

    for epoch in range(20):
        total_pred = 0.0
        total_mem = 0.0
        perm = torch.randperm(n_seq)

        for i in perm:
            seq = sequences[i]  # (seq_len+1, input_dim)
            # Windows of 4 frames → predict 5th
            x = seq[:-1].unsqueeze(0)  # (1, seq_len, input_dim) — need 4-frame windows
            # Simple sliding window
            for t in range(seq_len - 3):
                window = seq[t : t + 4].unsqueeze(0)  # (1, 4, input_dim)
                target = seq[t + 3].unsqueeze(0)  # (1, input_dim) — predict next

                out = cord(window, mode="both")
                loss_pred = F.mse_loss(out["pred"], target)
                loss_mem = F.mse_loss(out["recalled"], window[:, -1, :])
                loss = loss_pred + 0.1 * loss_mem

                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(cord.parameters(), 1.0)
                opt.step()

                total_pred += loss_pred.item()
                total_mem += loss_mem.item()

        if (epoch + 1) % 5 == 0:
            print(
                f"  Epoch {epoch+1:2d} | "
                f"pred_loss={total_pred:.4f} mem_loss={total_mem:.4f}"
            )

    # Test: predict next frame on held-out sequence
    print("\n--- Generalisation Test ---")
    with torch.no_grad():
        test_seq = sequences[0]
        pred_errors = []
        for t in range(seq_len - 3):
            window = test_seq[t : t + 4].unsqueeze(0)
            target = test_seq[t + 3].unsqueeze(0)
            pred = cord(window, mode="predict")
            pred_errors.append(F.mse_loss(pred, target).item())
        print(f"  Mean prediction MSE: {sum(pred_errors)/len(pred_errors):.6f}")

    print("\nHybrid demo complete!")


if __name__ == "__main__":
    demo_standalone_memory()
    demo_hybrid_compression()
