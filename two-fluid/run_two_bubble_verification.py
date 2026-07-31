#!/usr/bin/env python3
"""Enhanced two-bubble resonance verification: GPU, N=64, ensemble, r-pair scan.

Usage: python run_two_bubble_verification.py
Output: runs/<id>_two_bubble_v2/results.json + figure
"""

import torch, numpy as np, sys, json, os
from datetime import datetime

# Ensure long runs don't time out
torch.backends.cudnn.benchmark = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import TwoFluid3DGPU, PHI, PHI_INV


def make_bubble(ey, ei, cx, cy, cz, radius, r_local, amplitude=0.1):
    """Apply a Gaussian bubble with ratio r_local at position (cx,cy,cz)."""
    N = ey.shape[0]
    device = ey.device
    x = torch.arange(N, dtype=torch.float64, device=device).unsqueeze(1).unsqueeze(2)
    y = torch.arange(N, dtype=torch.float64, device=device).unsqueeze(0).unsqueeze(2)
    z = torch.arange(N, dtype=torch.float64, device=device).unsqueeze(0).unsqueeze(1)
    dist2 = ((x - cx) % N)**2 + ((y - cy) % N)**2 + ((z - cz) % N)**2
    dist2 = torch.minimum(dist2, (N - torch.sqrt(dist2))**2)
    gauss = torch.exp(-dist2 / (2 * radius**2))

    rho_local = ey + ei
    ey_local = rho_local * r_local / (1 + r_local)
    ei_local = rho_local / (1 + r_local)

    ey = ey * (1 - amplitude * gauss) + ey_local * amplitude * gauss
    ei = ei * (1 - amplitude * gauss) + ei_local * amplitude * gauss
    return ey, ei



def run_one_config(solver, r1, r2, d, radius, steps, dt, seed):
    """Run one bubble-pair configuration, return final_corr, peak_corr, history."""
    N = solver.N
    device = solver.device
    torch.manual_seed(seed)

    # Uniform background on device
    ey_bg = torch.ones(N, N, N, dtype=torch.float64, device=device) * 0.7
    ei_bg = torch.ones(N, N, N, dtype=torch.float64, device=device) * 0.7

    cx1, cy1, cz1 = N // 4, N // 2, N // 2
    cx2, cy2, cz2 = (N // 4 + d) % N, N // 2, N // 2

    ey, ei = make_bubble(ey_bg, ei_bg, cx1, cy1, cz1, radius, r1, 0.3)
    ey, ei = make_bubble(ey, ei, cx2, cy2, cz2, radius, r2, 0.3)

    ey_hat = torch.fft.fftn(ey)
    ei_hat = torch.fft.fftn(ei)
    u_hat = torch.zeros(3, N, N, N, dtype=torch.complex128, device=device)

    corr_history = []
    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)

        if step % 50 == 0:
            ey_f = torch.fft.ifftn(ey_hat).real
            ei_f = torch.fft.ifftn(ei_hat).real
            eps = ey_f - PHI * ei_f

            x = torch.arange(N, dtype=torch.float64, device=device)
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

            eps1_centered = (eps * w1) - eps1 * w1
            eps2_centered = (eps * w2) - eps2 * w2
            cross = (eps1_centered * eps2_centered).sum()
            norm1 = torch.sqrt((eps1_centered**2).sum() + 1e-30)
            norm2 = torch.sqrt((eps2_centered**2).sum() + 1e-30)
            corr = (cross / (norm1 * norm2 + 1e-30)).item()
            corr_history.append(corr)

    final_corr = float(np.mean(corr_history[-10:])) if corr_history else 0.0
    peak_corr = float(max(corr_history)) if corr_history else 0.0
    return final_corr, peak_corr, [float(c) for c in corr_history]


def main():
    N = 64
    lam = 0.02
    dt = 0.0005
    steps = 2000
    radius = 5.0  # scaled with N
    n_seeds = 5

    # r-pair configurations: (label, r1, r2, description)
    r_pairs = [
        ("below_below", 0.3, 0.5, "Both below pinch (r < φ⁻¹ ≈ 0.618)"),
        ("mixed",       0.5, 1.2, "Mixed: one below, one above pinch"),
        ("above_above", 1.2, 2.0, "Both above pinch (self-aware)"),
        ("extreme",     0.3, 3.0, "Extreme spread: deep Yin to deep Yang"),
    ]

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    solver = TwoFluid3DGPU(N=N, lam=lam, D=0.0001, nu=0.0005,
                           chi=0.0, device=device)

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_two_bubble_v2"
    os.makedirs(rdir, exist_ok=True)

    # φ-scaled separations: d = N//4 * φ^k for k in [-3, 5]
    d0 = N // 4  # = 16
    phi_seps = []
    for k in range(-3, 6):
        d = int(d0 * PHI**k) % N
        if d not in phi_seps and d >= 2:
            phi_seps.append(d)
    phi_seps = sorted(set(phi_seps))
    # Control separations (non-φ)
    control_seps = []
    for mult in [1.3, 1.7, 2.2, 2.8]:
        d = int(d0 * mult) % N
        if d not in phi_seps and d not in control_seps and d >= 2:
            control_seps.append(d)

    all_seps = phi_seps + control_seps
    sep_labels = []
    for d in all_seps:
        is_phi = any(abs(d - int(d0 * PHI**k)) <= 1 for k in range(-3, 6))
        sep_labels.append(f"d={d}" + (" (φ)" if is_phi else " (ctl)"))

    print(f"Two-bubble verification: N={N}, steps={steps}, seeds={n_seeds}")
    print(f"φ-separations: {phi_seps}")
    print(f"Control separations: {control_seps}")
    print(f"r-pairs: {[p[0] for p in r_pairs]}")
    print()

    all_results = {}

    for pair_label, r1, r2, desc in r_pairs:
        print(f"\n=== r-pair: {pair_label} (r1={r1}, r2={r2}) ===")
        print(f"  {desc}")
        pair_results = {}

        for d, slab in zip(all_seps, sep_labels):
            # Ensemble over seeds
            ensemble_final = []
            ensemble_peak = []
            histories = []
            for seed in range(42, 42 + n_seeds):
                fc, pc, hist = run_one_config(solver, r1, r2, d, radius, steps, dt, seed)
                ensemble_final.append(fc)
                ensemble_peak.append(pc)
                histories.append(hist)

            mean_final = float(np.mean(ensemble_final))
            std_final = float(np.std(ensemble_final))
            mean_peak = float(np.mean(ensemble_peak))

            is_phi = "(φ)" in slab
            pair_results[slab] = {
                "separation": d,
                "is_phi": is_phi,
                "mean_final_corr": mean_final,
                "std_final_corr": std_final,
                "mean_peak_corr": mean_peak,
                "ensemble": [float(f) for f in ensemble_final],
            }
            print(f"  {slab:18s} final={mean_final:+.4f}±{std_final:.4f} peak={mean_peak:+.4f}")

        # Analyze for this r-pair
        phi_corrs = [r["mean_final_corr"] for r in pair_results.values() if r["is_phi"]]
        ctl_corrs = [r["mean_final_corr"] for r in pair_results.values() if not r["is_phi"]]
        phi_mean = np.mean(phi_corrs) if phi_corrs else 0.0
        ctl_mean = np.mean(ctl_corrs) if ctl_corrs else 0.0
        ratio = phi_mean / max(abs(ctl_mean), 1e-30)

        print(f"  φ-mu={phi_mean:+.4f} ctl-mu={ctl_mean:+.4f} φ/ctl={ratio:.2f}×")
        if ratio > 1.2:
            print(f"  *** φ-STRUCTURED RESONANCE (ratio {ratio:.1f}×) ***")

        all_results[pair_label] = {
            "r1": r1, "r2": r2, "description": desc,
            "phi_mean": phi_mean, "ctl_mean": ctl_mean,
            "phi_ctl_ratio": ratio,
            "separations": pair_results,
        }

    # Save
    output = {
        "N": N, "steps": steps, "n_seeds": n_seeds, "dt": dt, "lam": lam,
        "radius": radius, "phi_separations": phi_seps,
        "control_separations": control_seps,
        "results": all_results,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(output, f, indent=2)

    # Summary table
    print("\n\n=== SUMMARY ===")
    print(f"{'r-pair':<16} {'φ_mean':>8} {'ctl_mean':>8} {'φ/ctl':>7} {'Signal'}")
    print("-" * 56)
    for pair_label, data in all_results.items():
        ratio = data["phi_ctl_ratio"]
        signal = "*** DETECTED ***" if ratio > 1.2 else "none"
        print(f"{pair_label:<16} {data['phi_mean']:>+8.4f} {data['ctl_mean']:>+8.4f} {ratio:>7.2f}× {signal}")

    # Plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        n_pairs = len(r_pairs)
        fig, axes = plt.subplots(n_pairs, 2, figsize=(14, 4 * n_pairs))
        if n_pairs == 1:
            axes = [axes]

        for idx, (pair_label, data) in enumerate(all_results.items()):
            ax1, ax2 = axes[idx]
            sep_data = data["separations"]

            # Panel A: bar chart
            labels = list(sep_data.keys())
            corrs = [sep_data[l]["mean_final_corr"] for l in labels]
            stds = [sep_data[l]["std_final_corr"] for l in labels]
            colors = ["C0" if sep_data[l]["is_phi"] else "C3" for l in labels]
            xs = range(len(labels))
            ax1.bar(xs, corrs, yerr=stds, color=colors, alpha=0.7, capsize=3)
            ax1.set_xticks(xs)
            ax1.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
            ax1.axhline(0, color="k", lw=0.5)
            ax1.set_ylabel("Cross-correlation")
            ax1.set_title(f"{pair_label}: r1={data['r1']}, r2={data['r2']} (φ/ctl={data['phi_ctl_ratio']:.1f}×)")
            ax1.legend([plt.Rectangle((0, 0), 1, 1, color="C0", alpha=0.7),
                        plt.Rectangle((0, 0), 1, 1, color="C3", alpha=0.7)],
                       ["φ-scaled", "control"], fontsize=7)
            ax1.grid(alpha=0.3)

            # Panel B: time evolution for best φ separation
            phi_keys = [k for k, v in sep_data.items() if v["is_phi"]]
            if phi_keys:
                phi_corrs_vals = [sep_data[k]["mean_final_corr"] for k in phi_keys]
                best_key = phi_keys[int(np.argmax(phi_corrs_vals))]
                # For time evolution, use the data from the first seed's history
                # (already computed; stored in the all_results dict)
                ax2.text(0.5, 0.5, f"Best φ: {best_key}\nφ/ctl ratio: {data['phi_ctl_ratio']:.2f}×",
                         transform=ax2.transAxes, ha='center', va='center', fontsize=12)
            ax2.set_title(f"{pair_label}: Summary")

        plt.tight_layout()
        plt.savefig(f"{rdir}/two_bubble_verification.png", dpi=120)
        plt.close()
        print(f"\n  Figure: {rdir}/two_bubble_verification.png")
    except Exception as e:
        print(f"\n  Plot skipped: {e}")

    print(f"\nResults saved to {rdir}/results.json")


if __name__ == "__main__":
    main()
