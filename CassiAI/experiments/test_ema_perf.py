"""Stress-test ModelEMA apply/restore performance."""
import torch
import torch.nn as nn
import time
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cassi.model_ema import ModelEMA

m = nn.Sequential(*[nn.Linear(1024, 1024) for _ in range(10)])
if torch.cuda.is_available():
    m = m.cuda()
ema = ModelEMA(m, decay=0.9999, device='cuda' if torch.cuda.is_available() else None)

# Perturb model weights so shadow differs
with torch.no_grad():
    for p in m.parameters():
        p.add_(torch.randn_like(p) * 0.1)
ema.update(m)

# Warm up
for _ in range(3):
    ema.apply_shadow(m)
    ema.restore(m)

# Time 100 apply/restore cycles
t0 = time.perf_counter()
for _ in range(100):
    ema.apply_shadow(m)
    ema.restore(m)
elapsed = time.perf_counter() - t0
print(f"100 apply/restore cycles: {elapsed:.3f}s ({elapsed/100*1000:.1f} ms/cycle)")

# Verify weights match after restore
ema.apply_shadow(m)
shadow_w = m[0].weight.data.clone()
ema.restore(m)
restored_w = m[0].weight.data.clone()
assert not torch.equal(shadow_w, restored_w), "restore did nothing"
ema.apply_shadow(m)
shadow_w2 = m[0].weight.data.clone()
assert torch.equal(shadow_w, shadow_w2), "apply idempotency broken"
ema.restore(m)
print("ModelEMA performance test PASSED")
