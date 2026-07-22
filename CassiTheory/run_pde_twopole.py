#!/usr/bin/env python3
"""Two-pole gate PDE test: east (closing) + west (opening with φ× cascade offset).
Uses gate_model='two_pole' in the solver, so dynamics use the combined gate."""

import torch, sys, os
sys.path.insert(0, 'two-fluid')
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU
from datetime import datetime

rid = datetime.now().strftime('%Y%m%d_%H%M%S') + '_twopole'
rdir = f'runs/{rid}'; os.makedirs(rdir, exist_ok=True)
logfile = f'{rdir}/log.txt'

s = ExpandingTwoFluid3DGPU(N=32, lam=0.02, chi=0.0, D=0.0001, nu=0.0005,
    a0=0.01, initial_ratio=21.2, hubble_mode='conversion',
    max_H=0.2, h_smooth=0.05, qi_gate=True, mode='cosmos', device='cpu')
s.gate_model = 'two_pole'
u, ey, ei = s.initial_expanding(amplitude=0.01, seed=42)

with open(logfile, 'w') as f: f.write('# step a H r q\n')
print('[two_pole] Starting 15000 steps (gate=two_pole, max_H=0.2)')
for step in range(15001):
    u, ey, ei = s.rk2_step(u, ey, ei, 0.0005)
    if step % 200 == 0:
        a = s.a.item(); H = s._H_smooth.item()
        ey_r = torch.fft.ifftn(ey).real; ei_r = torch.fft.ifftn(ei).real
        r = (ey_r.mean()/(ei_r.mean()+1e-12)).item(); qm = s.q_mean
        with open(logfile, 'a') as f: f.write(f'{step} {a:.6e} {H:.6e} {r:.6f} {qm:.6f}\n')
    if step % 5000 == 0:
        print(f'  step={step} a={a:.4f} H={H:.4f} r={r:.4f} q={qm:.4f}', flush=True)
print(f'[two_pole] done -> {rid}')
