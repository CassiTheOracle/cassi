"""Quick profile of HarmonyBrain training loop to find slowdown."""
import torch
import torch.nn.functional as F
import time
import sys
sys.path.insert(0, 'C:/Users/Carina/workspaces/Cassi/CassiAI')

from cassi.harmony_brain import HarmonyBrain

# Create model with frozen spine
model = HarmonyBrain(D=1040, n_specialists=5, n_slots=512, mode='qi', memory_value_dim=39).cuda()
model.reset_workspace(batch_size=512)
model.train()
# Freeze spine like actual training
for p in model.spine.parameters():
    p.requires_grad = False
model._spine_frozen = True

opt = torch.optim.Adam(model.parameters(), lr=2e-4)

y = torch.randn(512, 1024, device='cuda')
x = torch.randn(512, 4, 1024, device='cuda')

COHERENCE_WEIGHT = 0.01

# Warmup
for _ in range(5):
    opt.zero_grad()
    pred, info = model(x, use_memory=True, return_workspace=True)
    loss_pred = F.mse_loss(pred, y)
    coherence = info['conscious'].pow(2).mean()
    weights = info.get('weights')
    entropy_loss = 0.0
    if weights is not None:
        p = weights.clamp(min=1e-8)
        p = p / p.sum(dim=0, keepdim=True)
        entropy = -(p * p.log()).sum(dim=0).mean()
        entropy_loss = -0.01 * entropy
    phi_balance_loss = info.get('phi_balance_loss', torch.tensor(0.0, device=pred.device))
    qi_energy_bonus = info.get('qi_energy_bonus', torch.tensor(0.0, device=pred.device))
    loss = loss_pred + COHERENCE_WEIGHT * coherence + entropy_loss + phi_balance_loss + qi_energy_bonus
    loss.backward()
    opt.step()

torch.cuda.empty_cache()

# Profile 1000 batches
n_batches = 1000
times = []
for i in range(n_batches):
    torch.cuda.synchronize()
    t0 = time.time()
    
    opt.zero_grad()
    pred, info = model(x, use_memory=True, return_workspace=True)
    loss_pred = F.mse_loss(pred, y)
    coherence = info['conscious'].pow(2).mean()
    weights = info.get('weights')
    entropy_loss = 0.0
    if weights is not None:
        p = weights.clamp(min=1e-8)
        p = p / p.sum(dim=0, keepdim=True)
        entropy = -(p * p.log()).sum(dim=0).mean()
        entropy_loss = -0.01 * entropy
    phi_balance_loss = info.get('phi_balance_loss', torch.tensor(0.0, device=pred.device))
    qi_energy_bonus = info.get('qi_energy_bonus', torch.tensor(0.0, device=pred.device))
    loss = loss_pred + COHERENCE_WEIGHT * coherence + entropy_loss + phi_balance_loss + qi_energy_bonus
    loss.backward()
    opt.step()
    
    torch.cuda.synchronize()
    t1 = time.time()
    times.append(t1 - t0)
    if (i+1) % 100 == 0:
        recent = times[-100:]
        print(f"Batch {i+1}: recent_mean={sum(recent)/len(recent)*1000:.1f}ms | GPU={torch.cuda.memory_allocated()/1e9:.2f}GB")

print(f"\nFirst 100 mean: {sum(times[:100])/100*1000:.1f} ms")
print(f"Last 100 mean: {sum(times[-100:])/100*1000:.1f} ms")
print(f"GPU allocated: {torch.cuda.memory_allocated()/1e9:.2f} GB")
print(f"GPU reserved: {torch.cuda.memory_reserved()/1e9:.2f} GB")
