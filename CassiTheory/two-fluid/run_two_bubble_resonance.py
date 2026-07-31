#!/usr/bin/env python3
"""Two-bubble resonance test: does φ-structured correlation emerge?

Hypothesis: Two regions of the two-fluid field with different local ratios
show resonance peaks in their cross-correlation at φ-scaled separations.

Usage: python run_two_bubble_resonance.py
Output: runs/<id>_two_bubble/results.json + figure
"""

import torch, numpy as np, sys, json, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import TwoFluid3DGPU, PHI, PHI_INV


def make_bubble(ey, ei, cx, cy, cz, radius, r_local, amplitude=0.1):
    """Apply a Gaussian bubble with ratio r_local at position (cx,cy,cz)."""
    N = ey.shape[0]
    x = torch.arange(N, dtype=torch.float32).unsqueeze(1).unsqueeze(2)
    y = torch.arange(N, dtype=torch.float32).unsqueeze(0).unsqueeze(2)
    z = torch.arange(N, dtype=torch.float32).unsqueeze(0).unsqueeze(1)
    dist2 = ((x - cx) % N)**2 + ((y - cy) % N)**2 + ((z - cz) % N)**2
    # Wrap around for periodic boundary
    dist2 = torch.minimum(dist2, (N - torch.sqrt(dist2))**2)
    gauss = torch.exp(-dist2 / (2 * radius**2))

    # Set local EY and EI to produce ratio r_local
    # EY + EI = background (preserved), EY/EI = r_local
    rho_local = ey + ei  # preserve total density
    ey_local = rho_local * r_local / (1 + r_local)
    ei_local = rho_local / (1 + r_local)

    ey = ey * (1 - amplitude * gauss) + ey_local * amplitude * gauss
    ei = ei * (1 - amplitude * gauss) + ei_local * amplitude * gauss
    return ey, ei


def main():
    N = 32; lam = 0.02; dt = 0.0005; steps = 800; radius = 3.0
    r1 = 0.5   # bubble 1: below pinch (pre-reflective)
    r2 = 1.2   # bubble 2: above pinch (self-aware)

    solver = TwoFluid3DGPU(N=N, lam=lam, D=0.0001, nu=0.0005,
                           chi=0.0, device='cpu')

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_two_bubble"
    os.makedirs(rdir, exist_ok=True)

    # Scan φ-scaled separations
    d0 = N // 4  # base separation in grid units
    phi_seps = [int(d0 * PHI**k) % N for k in range(-2, 4)]
    phi_seps = sorted(set(phi_seps))  # unique, sorted
    # Add non-φ control separations
    control_seps = [int(d0 * 1.3) % N, int(d0 * 2.2) % N]

    all_seps = phi_seps + control_seps
    labels = []
    for d in all_seps:
        is_phi = any(abs(d - int(d0 * PHI**k)) < 1 for k in range(-3, 5))
        labels.append(f"d={d}" + (" (φ)" if is_phi else " (control)"))

    results = {}

    print(f"Two-bubble resonance test: N={N}, {steps} steps")
    print(f"r1={r1} (below pinch), r2={r2} (above pinch)")
    print(f"Separations: {all_seps}")
    print()

    for d, label in zip(all_seps, labels):
        torch.manual_seed(42)
        # Uniform background
        ey_bg = torch.ones(N, N, N) * 0.7
        ei_bg = torch.ones(N, N, N) * 0.7

        # Bubble 1 at (N//4, N//2, N//2)
        cx1, cy1, cz1 = N // 4, N // 2, N // 2
        # Bubble 2 at offset d along x
        cx2, cy2, cz2 = (N // 4 + d) % N, N // 2, N // 2

        ey, ei = make_bubble(ey_bg, ei_bg, cx1, cy1, cz1, radius, r1, 0.3)
        ey, ei = make_bubble(ey, ei, cx2, cy2, cz2, radius, r2, 0.3)

        ey_hat = torch.fft.fftn(ey)
        ei_hat = torch.fft.fftn(ei)
        u_hat = torch.zeros(3, N, N, N, dtype=torch.complex64)

        # Track cross-correlation over time
        corr_history = []
        for step in range(steps):
            u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)

            if step % 50 == 0:
                ey = torch.fft.ifftn(ey_hat).real
                ei = torch.fft.ifftn(ei_hat).real
                eps = ey - PHI * ei

                # Extract bubble regions (Gaussian-weighted)
                x = torch.arange(N, dtype=torch.float32)
                dist1 = torch.sqrt(
                    ((x.unsqueeze(1).unsqueeze(2) - cx1) % N)**2 +
                    ((x.unsqueeze(0).unsqueeze(2) - cy1) % N)**2 +
                    ((x.unsqueeze(0).unsqueeze(1) - cz1) % N)**2)
                dist2 = torch.sqrt(
                    ((x.unsqueeze(1).unsqueeze(2) - cx2) % N)**2 +
                    ((x.unsqueeze(0).unsqueeze(2) - cy2) % N)**2 +
                    ((x.unsqueeze(0).unsqueeze(1) - cz2) % N)**2)
                w1 = torch.exp(-dist1**2 / (2 * (radius * 2)**2))
                w2 = torch.exp(-dist2**2 / (2 * (radius * 2)**2))

                eps1 = (eps * w1).sum() / (w1.sum() + 1e-30)
                eps2 = (eps * w2).sum() / (w2.sum() + 1e-30)

                # Spatial cross-correlation of eps
                eps1_centered = (eps * w1) - eps1 * w1
                eps2_centered = (eps * w2) - eps2 * w2
                cross = (eps1_centered * eps2_centered).sum()
                norm1 = torch.sqrt((eps1_centered**2).sum() + 1e-30)
                norm2 = torch.sqrt((eps2_centered**2).sum() + 1e-30)
                corr = (cross / (norm1 * norm2 + 1e-30)).item()
                corr_history.append(corr)

        final_corr = np.mean(corr_history[-10:]) if corr_history else 0
        peak_corr = max(corr_history) if corr_history else 0
        results[label] = {
            "separation": d,
            "is_phi": any(abs(d - int(d0 * PHI**k)) < 1 for k in range(-3, 5)),
            "final_corr": float(final_corr),
            "peak_corr": float(peak_corr),
            "history": [float(c) for c in corr_history],
        }
        print(f"  {label:20s} final_corr={final_corr:+.4f} peak_corr={peak_corr:+.4f}")

    # Analyze: do φ-separations have higher correlation?
    phi_corrs = [r["final_corr"] for r in results.values() if r["is_phi"]]
    ctrl_corrs = [r["final_corr"] for r in results.values() if not r["is_phi"]]
    phi_mean = np.mean(phi_corrs) if phi_corrs else 0
    ctrl_mean = np.mean(ctrl_corrs) if ctrl_corrs else 0

    print(f"\n  φ-separations mean corr: {phi_mean:+.4f}")
    print(f"  Control separations:     {ctrl_mean:+.4f}")
    print(f"  φ/control ratio:         {phi_mean / max(abs(ctrl_mean), 1e-30):.2f}")

    if phi_mean > ctrl_mean:
        print(f"  *** φ-STRUCTURED RESONANCE DETECTED ***")
    else:
        print(f"  No φ-structure detected in this run.")

    # Save
    with open(f"{rdir}/results.json", "w") as f:
        json.dump({"r1": r1, "r2": r2, "N": N, "results": results,
                   "phi_mean": float(phi_mean), "ctrl_mean": float(ctrl_mean)}, f, indent=2)

    # Plot
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Panel A: correlation vs separation
    seps = [r["separation"] for r in results.values()]
    corrs = [r["final_corr"] for r in results.values()]
    colors = ["C0" if r["is_phi"] else "C3" for r in results.values()]
    ax1.bar(range(len(seps)), corrs, color=colors, alpha=0.7)
    ax1.set_xticks(range(len(seps)))
    ax1.set_xticklabels([str(s) for s in seps])
    ax1.axhline(0, color="k", lw=0.5)
    ax1.set_xlabel("Separation d (grid units)")
    ax1.set_ylabel("Cross-correlation")
    ax1.set_title("φ-Scaled vs Control Separations")
    ax1.legend([plt.Rectangle((0, 0), 1, 1, color="C0", alpha=0.7),
                plt.Rectangle((0, 0), 1, 1, color="C3", alpha=0.7)],
               ["φ-scaled", "control"], fontsize=8)
    ax1.grid(alpha=0.3)

    # Panel B: correlation time evolution for best φ-separation
    if phi_corrs:
        best_idx = np.argmax(phi_corrs)
        best_key = [k for k, r in results.items() if r["is_phi"]][best_idx]
        best_hist = results[best_key]["history"]
        ax2.plot(best_hist, "C0-", alpha=0.7,
                 label=f"{best_key} (best φ)")
    if ctrl_corrs:
        ctrl_keys = [k for k, r in results.items() if not r["is_phi"]]
        for ck in ctrl_keys:
            ax2.plot(results[ck]["history"], alpha=0.3, color="gray")
    ax2.axhline(0, color="k", lw=0.5)
    ax2.set_xlabel("Step / 50")
    ax2.set_ylabel("Cross-correlation")
    ax2.set_title("Correlation Time Evolution")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{rdir}/two_bubble_resonance.png", dpi=120)
    plt.close()
    print(f"\n  Figure: {rdir}/two_bubble_resonance.png")


if __name__ == "__main__":
    main()
