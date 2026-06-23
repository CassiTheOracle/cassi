"""Quick integration test for reviewed ModelEMA and MultiScaleByteEncoder."""

import os
import sys
import tempfile
import torch
import torch.nn as nn

# Avoid logging
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.model_ema import ModelEMA
from cassi.multi_scale_byte import MultiScaleByteEncoder


def test_model_ema_roundtrip():
    torch.manual_seed(0)
    m = nn.Linear(10, 1)
    ema = ModelEMA(m, decay=0.5)
    with torch.no_grad():
        for p in m.parameters():
            p.add_(torch.randn_like(p) * 0.1)
    ema.update(m)
    sd = ema.state_dict()
    ema2 = ModelEMA(m, decay=0.5)
    ema2.load_state_dict(sd)
    for k in ema.params:
        assert torch.allclose(ema.params[k], ema2.params[k]), f"EMA mismatch {k}"

    # apply/restore idempotency
    ema.apply_shadow(m)
    shadow = next(m.parameters()).detach().clone()
    ema.restore(m)
    restored = next(m.parameters()).detach().clone()
    assert not torch.equal(shadow, restored), "EMA restore did nothing"
    ema.apply_shadow(m)
    shadow2 = next(m.parameters()).detach().clone()
    assert torch.equal(shadow, shadow2), "EMA re-apply idempotency broken"
    print("ModelEMA roundtrip OK")


def test_multi_scale_byte_shapes_and_gate():
    enc = MultiScaleByteEncoder(dim_field=1024, T=4)
    x = torch.randint(0, 256, (2, 512), dtype=torch.uint8)
    out = enc.encode_sequence(x, T=4)
    assert out.shape == (2, 4, 1024), f"expected (2,4,1024), got {out.shape}"
    single = enc.encode(x)
    assert single.shape == (2, 1024), f"expected (2,1024), got {single.shape}"

    # Check gate values are probabilities
    enc.eval()
    with torch.no_grad():
        out = enc.encode_sequence(x, T=4)
    scale_stats = torch.cat([
        enc.fine_encoder.encode_sequence(x[:, :enc.fine_window], T=4).mean(dim=1),
        enc.medium_encoder.encode_sequence(x[:, :enc.medium_window], T=4).mean(dim=1),
        enc.coarse_encoder.encode_sequence(x, T=4).mean(dim=1),
    ], dim=-1)
    gate = enc.scale_gate(scale_stats)
    assert torch.allclose(gate.sum(dim=-1), torch.ones(2), atol=1e-5), "gate not softmax"
    print("MultiScaleByteEncoder shapes and gate OK")


def test_multi_scale_byte_training_step():
    enc = MultiScaleByteEncoder(dim_field=1024, T=4)
    opt = torch.optim.SGD(enc.parameters(), lr=0.1)
    target = torch.randn(2, 4, 1024)
    x = torch.randint(0, 256, (2, 512), dtype=torch.uint8)
    out = enc.encode_sequence(x, T=4)
    loss = ((out - target) ** 2).mean()
    loss_before = loss.item()
    opt.zero_grad()
    loss.backward()
    opt.step()
    out2 = enc.encode_sequence(x, T=4)
    loss_after = ((out2 - target) ** 2).mean().item()
    assert loss_after < loss_before, f"loss did not decrease: {loss_before} -> {loss_after}"
    print("MultiScaleByteEncoder training step OK")


if __name__ == '__main__':
    test_model_ema_roundtrip()
    test_multi_scale_byte_shapes_and_gate()
    test_multi_scale_byte_training_step()
    print("\nAll review feature tests PASSED")
