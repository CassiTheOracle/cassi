#!/usr/bin/env python3
"""PDE w_a test: 5-channel gate vs single-channel at N=32."""
import torch, numpy as np, sys, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

def run_test(gate_model, label, steps=15000):
    N = 32; lam = 0.02; dt = 0.0005; log_interval = 200
    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_wa_{gate_model}"; os.makedirs(rdir, exist_ok=True)
    logfile = f"{rdir}/log.txt"

    solver = ExpandingTwoFluid3DGPU(
        N=N, lam=lam, chi=0.0, D=0.0001, nu=0.0005,
        a0=0.01, initial_ratio=21.2, hubble_mode='conversion',
        max_H=None, h_smooth=0.05, qi_gate=True,
        mode='cosmos', device='cpu'
    )
    solver.gate_model = gate_model

    u_hat, ey_hat, ei_hat = solver.initial_expanding(amplitude=0.01, seed=42)

    with open(logfile, "w") as f:
        f.write(f"# N={N} lam={lam} gate={gate_model} steps={steps}\n")
        f.write(f"# step a H_smooth r_mean q_mean\n")

    print(f"[{label}] Starting N={N} gate={gate_model} ({steps} steps) -> {logfile}")

    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)
        if step % log_interval == 0:
            a = solver.a.item()
            H = solver._H_smooth.item()
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            r = (ey.mean()/(ei.mean()+1e-12)).item()
            qm = solver.q_mean
            if np.isnan(a):
                with open(logfile, "a") as f:
                    f.write(f"NaN at step {step}\n")
                print(f"  [{label}] NaN at step {step}")
                break
            with open(logfile, "a") as f:
                f.write(f"{step} {a:.6e} {H:.6e} {r:.6f} {qm:.6f}\n")
        if step % 5000 == 0:
            print(f"  [{label}] step={step:5d} a={a:.4f} r={r:.4f} H={H:.4f} q={qm:.4f}")

    print(f"[{label}] Complete ({step+1} steps). Log: {logfile}")
    return logfile

if __name__ == "__main__":
    print("═══ 5-Channel Gate PDE Test ═══\n")
    log_single = run_test('single', '1-ch', steps=15000)
    print()
    log_five = run_test('five', '5-ch', steps=15000)

    print("\n═══ COMPARISON ═══")
    print(f"  1-ch: {log_single}")
    print(f"  5-ch: {log_five}")
    print("  Run `python vs wa extractor` to compare H(a) and w_a.")
