#!/usr/bin/env python3
"""Test stress_energy hubble_mode—does H_struct change w_a?"""

import torch, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

N=32; lam=0.02; dt=0.0005; steps=30000
solver = ExpandingTwoFluid3DGPU(
    N=N, lam=lam, chi=0.0, D=0.0001, nu=0.0005,
    a0=0.01, initial_ratio=21.2, hubble_mode='stress_energy',
    max_H=None, h_smooth=0.05, qi_gate=True,
    mode='cosmos', device='cpu'
)
u_hat, ey_hat, ei_hat = solver.initial_expanding(amplitude=0.01, seed=42)

hist = []
print(f"N={N} stress_energy mode ({steps} steps)...")
for step in range(steps):
    u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)
    if step % 200 == 0:
        a = solver.a.item(); H = solver._H_smooth.item()
        ey = torch.fft.ifftn(ey_hat).real; ei = torch.fft.ifftn(ei_hat).real
        r = (ey.mean()/(ei.mean()+1e-12)).item()
        if np.isnan(a): print(f"NaN at {step}"); break
        hist.append({"a":a,"H":H,"r":r})
    if step % 5000 == 0 and hist:
        h=hist[-1]; print(f"step={step:5d} a={h['a']:.4f} r={h['r']:.4f} H={h['H']:.6f}")

a_arr=np.array([h["a"] for h in hist]); H_arr=np.array([h["H"] for h in hist])
lna=np.log(a_arr+1e-30); w=-1-(2/3)*np.gradient(np.log(H_arr+1e-30),lna)
desi=(a_arr>=0.3)&(a_arr<=1.0)
if sum(desi)<5: desi=(a_arr>=0.1)  # fallback
A=np.column_stack([np.ones(sum(desi)),1-a_arr[desi]])
w0,wa=np.linalg.lstsq(A,w[desi],rcond=None)[0]

print(f"\nstress_energy: w0={w0:.4f} wa={wa:+.4f} (a_max={a_arr[-1]:.4f})")
print(f"ODE conversion: w0=-0.856 wa=+0.457")
print(f"Internal calibration target (not DESI): w0=-0.838+-0.064 wa=-0.51+-0.38")
if wa < 0: print("*** w_a SIGN FLIPPED! ***")
elif wa < 0.2: print("w_a significantly reduced")
else: print("w_a unchanged from ODE")
