#!/usr/bin/env python3
"""Fast two-bubble verification: N=48, 1000 steps, 3 seeds, key r-pairs.
Usage: python run_two_bubble_fast.py
Output: runs/<id>_two_bubble_fast/results.json + figure
"""

import torch, numpy as np, sys, json, os
from datetime import datetime

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import TwoFluid3DGPU, PHI, PHI_INV


def make_bubble(ey, ei, cx, cy, cz, radius, r_local, amplitude=0.1):
    N = ey.shape[0]
    device = ey.device
    x = torch.arange(N, dtype=torch.float64, device=device)
    dist2 = ((x.unsqueeze(1).unsqueeze(2) - cx) % N)**2 + \
            ((x.unsqueeze(0).unsqueeze(2) - cy) % N)**2 + \
            ((x.unsqueeze(0).unsqueeze(1) - cz) % N)**2
    dist2 = torch.minimum(dist2, (N - torch.sqrt(dist2))**2)
    gauss = torch.exp(-dist2 / (2 * radius**2))
    rho_local = ey + ei
    ey = ey * (1 - amplitude * gauss) + rho_local * r_local/(1+r_local) * amplitude * gauss
    ei = ei * (1 - amplitude * gauss) + rho_local/(1+r_local) * amplitude * gauss
    return ey, ei


def run_one(solver, r1, r2, d, radius, steps, dt, seed):
    N = solver.N
    device = solver.device
    torch.manual_seed(seed)
    ey = torch.ones(N, N, N, dtype=torch.float64, device=device) * 0.7
    ei = torch.ones(N, N, N, dtype=torch.float64, device=device) * 0.7
    cx1, cy1, cz1 = N//4, N//2, N//2
    cx2, cy2, cz2 = (N//4 + d) % N, N//2, N//2
    ey, ei = make_bubble(ey, ei, cx1, cy1, cz1, radius, r1, 0.3)
    ey, ei = make_bubble(ey, ei, cx2, cy2, cz2, radius, r2, 0.3)
    ey_hat = torch.fft.fftn(ey)
    ei_hat = torch.fft.fftn(ei)
    u_hat = torch.zeros(3, N, N, N, dtype=torch.complex128, device=device)

    x = torch.arange(N, dtype=torch.float64, device=device)
    corr_history = []
    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)
        if step % 50 == 0:
            ey_f = torch.fft.ifftn(ey_hat).real
            ei_f = torch.fft.ifftn(ei_hat).real
            eps = ey_f - PHI * ei_f
            dist1 = torch.sqrt(((x.unsqueeze(1).unsqueeze(2)-cx1)%N)**2 +
                               ((x.unsqueeze(0).unsqueeze(2)-cy1)%N)**2 +
                               ((x.unsqueeze(0).unsqueeze(1)-cz1)%N)**2)
            dist2 = torch.sqrt(((x.unsqueeze(1).unsqueeze(2)-cx2)%N)**2 +
                               ((x.unsqueeze(0).unsqueeze(2)-cy2)%N)**2 +
                               ((x.unsqueeze(0).unsqueeze(1)-cz2)%N)**2)
            w1 = torch.exp(-dist1**2/(2*(radius*2)**2))
            w2 = torch.exp(-dist2**2/(2*(radius*2)**2))
            eps1 = (eps*w1).sum()/(w1.sum()+1e-30)
            eps2 = (eps*w2).sum()/(w2.sum()+1e-30)
            eps1c = (eps*w1) - eps1*w1
            eps2c = (eps*w2) - eps2*w2
            cross = (eps1c*eps2c).sum()
            n1 = torch.sqrt((eps1c**2).sum()+1e-30)
            n2 = torch.sqrt((eps2c**2).sum()+1e-30)
            corr_history.append((cross/(n1*n2+1e-30)).item())
    fc = float(np.mean(corr_history[-10:])) if corr_history else 0.0
    pc = float(max(corr_history)) if corr_history else 0.0
    return fc, pc


def main():
    N, lam, dt, steps, radius, n_seeds = 48, 0.02, 0.0005, 1000, 4.0, 3

    r_pairs = [
        ("below_below", 0.3, 0.5, "Both below pinch"),
        ("mixed",       0.5, 1.2, "One below, one above"),
        ("above_above", 1.2, 2.0, "Both above pinch"),
    ]

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={N}  steps={steps}  seeds={n_seeds}")
    solver = TwoFluid3DGPU(N=N, lam=lam, D=0.0001, nu=0.0005, chi=0.0, device=device)

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_two_bubble_fast"
    os.makedirs(rdir, exist_ok=True)

    d0 = N // 4
    phi_seps = sorted(set(int(d0*PHI**k)%N for k in range(-3, 6) if int(d0*PHI**k)%N >= 2))
    ctl_seps = sorted(set(int(d0*m)%N for m in [1.3, 1.7, 2.2, 2.8] if int(d0*m)%N >= 2 and int(d0*m)%N not in phi_seps))
    all_seps = phi_seps + ctl_seps

    print(f"φ-seps: {phi_seps}  ctl: {ctl_seps}  r-pairs: {[p[0] for p in r_pairs]}\n")

    all_results = {}
    for pair_label, r1, r2, desc in r_pairs:
        print(f"=== {pair_label} (r1={r1}, r2={r2}): {desc} ===")
        pair_results = {}
        for d in all_seps:
            finals = []
            for seed in range(42, 42+n_seeds):
                fc, _ = run_one(solver, r1, r2, d, radius, steps, dt, seed)
                finals.append(fc)
            mu, sd = float(np.mean(finals)), float(np.std(finals))
            is_phi = d in phi_seps
            pair_results[f"d={d}"+(" φ" if is_phi else " ctl")] = {
                "separation": d, "is_phi": is_phi, "mean": mu, "std": sd
            }
            print(f"  d={d:2d}: {mu:+.4f}±{sd:.4f}  {'[φ]' if is_phi else '[ctl]'}")

        phi_mu = np.mean([r["mean"] for r in pair_results.values() if r["is_phi"]])
        ctl_mu = np.mean([r["mean"] for r in pair_results.values() if not r["is_phi"]])
        ratio = phi_mu / max(abs(ctl_mu), 1e-30)
        print(f"  φ-mu={phi_mu:+.4f}  ctl-mu={ctl_mu:+.4f}  φ/ctl={ratio:.2f}×")
        if ratio > 1.2:
            print(f"  *** φ-STRUCTURED RESONANCE (ratio {ratio:.1f}×) ***")
        all_results[pair_label] = {"r1": r1, "r2": r2, "phi_mean": phi_mu,
                                    "ctl_mean": ctl_mu, "ratio": ratio,
                                    "separations": pair_results}
        print()

    # Save
    output = {"N": N, "steps": steps, "n_seeds": n_seeds, "results": all_results}
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(output, f, indent=2)

    # Summary
    print("=== SUMMARY ===")
    print(f"{'r-pair':<16} {'φ_mean':>8} {'ctl_mean':>8} {'φ/ctl':>7} {'Signal'}")
    print("-" * 56)
    for pl, d in all_results.items():
        s = "*** DETECTED ***" if d["ratio"] > 1.2 else "none"
        print(f"{pl:<16} {d['phi_mean']:>+8.4f} {d['ctl_mean']:>+8.4f} {d['ratio']:>7.2f}× {s}")

    # Plot
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(len(r_pairs), 1, figsize=(12, 3*len(r_pairs)))
        if len(r_pairs) == 1: axes = [axes]
        for idx, (pl, d) in enumerate(all_results.items()):
            ax = axes[idx]
            sd = d["separations"]
            labels = list(sd.keys())
            corrs = [sd[l]["mean"] for l in labels]
            stds = [sd[l]["std"] for l in labels]
            colors = ["C0" if sd[l]["is_phi"] else "C3" for l in labels]
            ax.bar(range(len(labels)), corrs, yerr=stds, color=colors, alpha=0.7, capsize=3)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
            ax.axhline(0, color="k", lw=0.5)
            ax.set_ylabel("Cross-correlation")
            ax.set_title(f"{pl}: r1={d['r1']}, r2={d['r2']}  φ/ctl={d['ratio']:.2f}×")
            ax.legend([plt.Rectangle((0,0),1,1,color="C0",alpha=0.7),
                       plt.Rectangle((0,0),1,1,color="C3",alpha=0.7)],
                      ["φ-scaled","control"], fontsize=7)
            ax.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{rdir}/two_bubble_fast.png", dpi=120)
        plt.close()
        print(f"\nFigure: {rdir}/two_bubble_fast.png")
    except Exception as e:
        print(f"\nPlot: {e}")

    print(f"Results: {rdir}/results.json")

if __name__ == "__main__":
    main()
