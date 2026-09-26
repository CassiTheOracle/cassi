#!/usr/bin/env python3
"""Measure spatial boost factor: does <(1-q)*eps> exceed (1-<q>)*<eps>?"""

import torch, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import TwoFluid3DGPU, PHI, PHI_INV

N = 32; lam = 0.02; dt = 0.0005; steps = 500
dev = torch.device('cpu')
solver = TwoFluid3DGPU(N=N, lam=lam, D=0.0001, nu=0.0005, chi=0.0, device='cpu')

ey = torch.ones(N,N,N, device=dev) * 0.5
ei = torch.ones(N,N,N, device=dev) * 1.0
torch.manual_seed(42)
ey += 0.05 * torch.randn(N,N,N, device=dev)
ei += 0.05 * torch.randn(N,N,N, device=dev)
ey = torch.clamp(ey, 0.01, None); ei = torch.clamp(ei, 0.01, None)

ey_hat = torch.fft.fftn(ey); ei_hat = torch.fft.fftn(ei)
u_hat = torch.zeros(3,N,N,N, dtype=torch.complex64, device=dev)

print(f"Measuring spatial boost at r0~0.5, N={N}, {steps} steps")
print(f"{'step':>6s} {'<r>':>8s} {'<q>':>8s} {'<(1-q)>':>10s} {'boost':>8s} {'<eps>':>10s}")

for step in range(steps):
    u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)
    
    if step % 50 == 0:
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        r = ey / (ei + 1e-12)
        eps = (ey - PHI * ei); rho = ey + ei
        eps_sq = (r - PHI)**2 * PHI**2 / ((1+r)**2 + 1e-30)
        q = rho**2 / (rho**2 + PHI_INV**2 + eps_sq + 1e-30)
        one_minus_q = 1 - q
        num = (one_minus_q * eps.abs()).mean()
        den = one_minus_q.mean() * eps.abs().mean() + 1e-30
        boost = (num/den).item()
        print(f"{step:6d} {r.mean().item():8.4f} {q.mean().item():8.4f} {one_minus_q.mean().item():10.4f} {boost:8.4f} {torch.sqrt((eps**2).mean()).item():10.4f}")

print(f"\nFinal boost = {boost:.4f}")
if boost > 1.01: print("SIGNIFICANT spatial boost!")
elif boost > 1.001: print("Marginal boost")
else: print("No significant spatial boost")
