import torch
from cassi.qi_field import QiField

model = QiField(N=64, d=64, K_train=3, K_gen=3, self_aware=True).to('cuda:0')
x = torch.randint(0, 256, (2, 64), device='cuda:0')
model.reset_state()
loss, info = model.training_loss(x)
print('loss:', loss.item())
print('ce_loss:', info['ce_loss'])
print('ctrl_gamma:', info.get('ctrl_gamma'))
print('ctrl_alpha:', info.get('ctrl_alpha'))
print('Q_mean:', info['Q_mean'])
loss.backward()
print('controller grad norm:', sum(p.grad.norm().item() for p in model.controller.parameters() if p.grad is not None))
print('OK')
