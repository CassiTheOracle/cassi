import torch
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cassi.qi_field import QiField

# Per AGENTS.md: GPU 0 is the iGPU and must never be used for training.
# The 7900 XTX is cuda:1.
device = 'cuda:1' if torch.cuda.is_available() and torch.cuda.device_count() > 1 else 'cuda:0'
model = QiField(N=64, d=64, K_train=3, K_gen=3, self_aware=True).to(device)
x = torch.randint(0, 256, (4, 64), device=device)
model.reset_state()
loss, info = model.training_loss(x)
print('loss:', loss.item())
print('ce_loss:', info['ce_loss'])
print('Q_mean:', info['Q_mean'])
print('ctrl_aux:', info.get('ctrl_aux_loss', 0.0))
assert not torch.isnan(loss)
print('OK')
