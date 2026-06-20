"""Smoke test for DualCassi with all enhancements.

Runs a few training steps with:
  - multi-scale bytes
  - EMA
  - curiosity engine
  - imagination consistency loss
  - metacognitive signals
  - all regularization losses

Use before launching a long training run to catch integration issues.
"""

import torch
import torch.nn.functional as F
from cassi.dual_cassi import DualCassi
from cassi.curiosity import CuriosityEngine
from cassi.model_ema import ModelEMA


def main():
    device = 'cuda'
    model = DualCassi(
        D=1040, D_stem=1040, D_brain=int(1040 * 1.618 * 2),
        use_changepoint=True, use_soul=True, use_memory=True,
        byte_mode=True, multi_scale_bytes=True, horizons=(1, 4, 16),
    ).to(device)

    opt = torch.optim.AdamW(model.parameters(), lr=2e-4)
    ema = ModelEMA(model, decay=0.9999, device=device)
    curiosity = CuriosityEngine(['physics', 'text', 'audio'])

    print("Running smoke test...")
    for step in range(3):
        model.train()
        model.reset_state(2)
        x = torch.randint(0, 256, (2, 1024), dtype=torch.uint8, device=device)
        y = torch.randn(2, 3, 1024, device=device)

        pred, info = model(x, return_info=True, byte_mode=True)

        loss_pred = F.mse_loss(pred, y)
        loss = (loss_pred
                + info['phi_balance_loss']
                + info['sparsity_loss']
                - 0.05 * info['chakra_entropy']
                + info.get('imagination_consistency_loss', 0))

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        opt.zero_grad()
        ema.update(model)

        print(f"  step {step}: loss={loss.item():.4f} pred={loss_pred.item():.4f} "
              f"curiosity={info['curiosity']:.3f} confidence={info['metacognitive_confidence']:.3f}")

    # Validation with EMA
    ema.apply_shadow(model)
    model.eval()
    with torch.no_grad():
        val_pred, val_info = model(x, return_info=True, byte_mode=True)
    print(f"  EMA val_pred mean={val_pred.mean().item():.4f}")
    ema.restore(model)

    # Curiosity weights
    curiosity.update('physics', 0.44)
    curiosity.update('text', 0.85)
    weights = curiosity.compute_weights()
    print(f"  curiosity weights: {weights}")

    # EMA checkpoint roundtrip
    sd = ema.state_dict()
    ema2 = ModelEMA(model, decay=0.9999, device=device)
    ema2.load_state_dict(sd)
    print("  EMA state dict roundtrip OK")

    print("\nSmoke test PASSED")


if __name__ == '__main__':
    main()
