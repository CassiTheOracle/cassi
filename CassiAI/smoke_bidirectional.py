import torch
from cassi.qi_field import QiField

model = QiField(N=64, d=64, K_train=3, K_gen=3, self_aware=True).to('cuda:0')
x = torch.randint(0, 256, (4, 64), device='cuda:0')
model.reset_state()
loss, info = model.training_loss(x)
print('loss:', loss.item())
print('ce_loss:', info['ce_loss'])
print('Q_mean:', info['Q_mean'])
print('ctrl_aux:', info.get('ctrl_aux_loss', 0.0))
assert not torch.isnan(loss)
print('OK')
