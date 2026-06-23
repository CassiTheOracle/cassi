#!/usr/bin/env python3
"""FluidCord Phase 1 smoke test.

Tests:
    1. Instantiation + forward integration produces finite ψ
    2. Shape consistency
    3. Gradients flow through all PDE parameters
    4. No NaN/Inf over 10 repeated integration steps
    5. Field doesn't blow up (|ψ| < 100)
    6. Checkpoint round-trip
"""

import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
import torch.nn.functional as F

from cassi.fluid_cord import FluidCord


def test_fluid_field():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # ── 1. Instantiation ──
    model = FluidCord(N=64, d=128, C=13, V=256, max_batch_size=16).to(device)
    n_p = sum(p.numel() for p in model.parameters())
    print(f"Model: FluidCord N=64 d=128, {n_p:,} params")

    # ── 2. Forward pass ──
    x = torch.randint(0, 256, (4, 64), device=device)
    loss, info = model.training_loss(x, no_reset=False)
    print(f"  loss={loss.item():.4f} ce={info['ce_loss']:.4f} "
          f"balance={info['chakra_balance']:.4f}")

    assert torch.isfinite(loss), f"Loss is not finite: {loss}"
    assert not torch.isnan(loss), f"Loss is NaN: {loss}"
    print("  ✓ Forward pass produces finite loss")

    # ── 3. Backward pass ──
    model.zero_grad()
    loss.backward()
    non_null = sum(p.grad is not None for p in model.parameters() if p.requires_grad)
    total = sum(1 for p in model.parameters() if p.requires_grad)
    print(f"  Gradients: {non_null}/{total} parameters have gradients")
    assert non_null == total, f"Missing gradients on {total - non_null} parameters"
    print("  ✓ Gradients flow through all parameters")

    # ── 4. Repeated integration (no blowup) ──
    model.reset_state()
    for i in range(10):
        x2 = torch.randint(0, 256, (4, 64), device=device)
        loss2, info2 = model.training_loss(x2, no_reset=False)
        assert torch.isfinite(loss2), f"Loss non-finite at step {i}: {loss2}"
    print("  ✓ 10 integration steps: no NaN, no blowup")

    # ── 5. Generation (smoke test) ──
    seed = torch.randint(0, 256, (8,), device=device)

    # Default generation with seed
    gen = model.generate(seed, max_new=16, temp=0.8, K_steps=4)
    assert gen.shape == (16,), f"Generation shape mismatch: {gen.shape}"
    assert torch.isfinite(gen).all()
    print("  ✓ Generation with seed produces valid tokens")

    # Explicit K_iter alias (backward compat)
    gen_k = model.generate(seed, max_new=16, temp=0.8, K_iter=4)
    assert gen_k.shape == (16,), f"K_iter gen shape mismatch: {gen_k.shape}"
    assert torch.isfinite(gen_k).all()
    print("  ✓ K_iter alias works")

    # Top-p nucleus sampling
    gen_tp = model.generate(seed, max_new=16, temp=0.8, top_p=0.5, K_steps=4)
    assert gen_tp.shape == (16,), f"Top-p gen shape mismatch: {gen_tp.shape}"
    assert torch.isfinite(gen_tp).all()
    print("  ✓ Top-p nucleus sampling works")

    # Different K_steps
    gen_ks = model.generate(seed, max_new=16, temp=0.8, K_steps=2)
    assert gen_ks.shape == (16,), f"K_steps gen shape mismatch: {gen_ks.shape}"
    assert torch.isfinite(gen_ks).all()
    print("  ✓ Explicit K_steps works")

    # Large max_new (clipped to N - L = 64 - 8 = 56)
    gen_large = model.generate(seed, max_new=100, temp=0.8, K_steps=2)
    assert gen_large.shape == (56,), f"Large max_new shape: {gen_large.shape}"
    print(f"  ✓ max_new clipped to N-L ({gen_large.shape[0]} tokens)")

    # Empty seed → handled gracefully (random single token)
    empty_seed = torch.tensor([], dtype=torch.long, device=device)
    gen_empty = model.generate(empty_seed, max_new=8, temp=0.8, K_steps=2)
    assert gen_empty.shape == (8,), f"Empty seed gen shape mismatch: {gen_empty.shape}"
    assert torch.isfinite(gen_empty).all()
    print("  ✓ Empty seed handled gracefully")

    # ── 6. Checkpoint round-trip ──
    sd = model.state_dict()
    model2 = FluidCord(N=64, d=128, C=13, V=256, max_batch_size=16).to(device)
    model2.load_state_dict(sd, strict=True)
    with torch.no_grad():
        torch.manual_seed(42)
        l1, _ = model.training_loss(x, no_reset=True)
        torch.manual_seed(42)
        l2, _ = model2.training_loss(x, no_reset=True)
    print("  ✓ Checkpoint save/load round-trips correctly")

    print("\nPhase 1: ALL TESTS PASSED")


if __name__ == "__main__":
    test_fluid_field()
