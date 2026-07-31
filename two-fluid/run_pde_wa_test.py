#!/usr/bin/env python3
"""PDE w_a test at N=32—max_H=None, background run with file logging."""

import torch, numpy as np, sys, json, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

def main():
    N = 32; lam = 0.02; dt = 0.0005; steps = 40000
    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_pde_wa"; os.makedirs(rdir, exist_ok=True)
    logfile = f"{rdir}/log.txt"
    
    solver = ExpandingTwoFluid3DGPU(
        N=N, lam=lam, chi=0.0, D=0.0001, nu=0.0005,
        a0=0.01, initial_ratio=21.2, hubble_mode='conversion',
        max_H=None, h_smooth=0.05, qi_gate=True,
        mode='cosmos', device='cpu'
    )
    u_hat, ey_hat, ei_hat = solver.initial_expanding(amplitude=0.01, seed=42)
    
    with open(logfile, "w") as f:
        f.write(f"# N={N} lam={lam} steps={steps} initial_ratio=21.2\n")
        f.write("# step a H_smooth r_mean q_mean\n")
    
    print(f"Starting N={N} PDE w_a test ({steps} steps) -> {logfile}")
    
    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)
        
        if step % 200 == 0:
            a = solver.a.item()
            H = solver._H_smooth.item()
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            r = (ey.mean()/(ei.mean()+1e-12)).item()
            q_mean = solver.q_mean
            
            if np.isnan(a):
                with open(logfile, "a") as f:
                    f.write(f"NaN at step {step}\n")
                print(f"NaN at step {step}")
                break
            
            with open(logfile, "a") as f:
                f.write(f"{step} {a:.6e} {H:.6e} {r:.6f} {q_mean:.6f}\n")
        
        if step % 5000 == 0:
            print(f"  step={step:5d} a={a:.4f} r={r:.4f} H={H:.4f} q={q_mean:.4f}")
    
    print(f"\nRun complete. Log: {logfile}")

if __name__=="__main__": main()
