"""Quick forward test of DualCassi with multi-scale bytes."""
import torch
from cassi.dual_cassi import DualCassi

m = DualCassi(D=1040, multi_scale_bytes=True)
m.eval()
m.reset_state(batch_size=2)

# Text bytes
x = torch.randint(0, 256, (2, 64), dtype=torch.uint8)
# Audio: dummy [B, T, C] normalized
audio = torch.randn(2, 1, 256)

with torch.no_grad():
    out, info = m(x=x, audio=audio, text_labels=torch.randint(0, 256, (2,)),
                  phase_name='text_audio', return_info=True)
print("out type:", type(out))
if isinstance(out, dict):
    print("out keys:", sorted(out.keys()))
else:
    print("out shape:", out.shape)
print("info keys:", sorted(info.keys()))
print("Forward OK")
