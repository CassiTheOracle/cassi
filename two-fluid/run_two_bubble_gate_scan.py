#!/usr/bin/env python3
"""Two-bubble decisive gate-parameter scan.

Tests `consciousness/consciousness-from-phi.md` §3.4: the two-bubble
φ-resonance revival must shift with the Qi gate parameter. The 2026-07-19
verification (`run_two_bubble_fast.py`, N=48, 1000 steps, 3 seeds) found
weak-to-moderate φ-structured revival for below-pinch r-pairs (below_below
φ/ctl 3.83×, mixed 3.44×, above_above 2.97×; revival at d≥31 present only
below the pinch). §3.4 leaves the decisive test untested: "scanning the Qi
gate parameter α".

Gate parameter definition (this scan):
  The canonical single-gate openness from `cassi_two_fluid_3d_gpu.py` rhs()
  (and `run_rung_offset_probe.py` gate_openness):
        (1-q) = (φ⁻² + ε²) / (M + φ⁻² + ε²),   M = (EY+EI)²,  ε = EY − φ·EI
  applied to conversion with openness exponent α:
        conv = −λ · (1-q)^α · ε
  α = 0.0 → ungated conversion, exactly the 2026-07-19 baseline dynamics
  α = 0.5 → weak gate (mild openness suppression)
  α = 2.0 → strong gate (closer to gate-closed; (1-q)² ≤ (1-q))

Verdict rule (honest): SUPPORTED if the large-separation revival
(mean correlation at φ-separations d∈{31,34,37}) or its peak position
moves systematically (monotone in α, beyond seed-bootstrap noise) with the
gate. NULL/AMBIGUOUS if the revival structure is gate-independent.

Checkpoint/resume: every completed (α, pair, d, seed) cell is appended to
`runs/<id>_two_bubble_gate/cells.json`; `--resume DIR` continues a killed
run from its checkpoint.

Usage:
  python run_two_bubble_gate_scan.py [--steps 1000] [--seeds 3] [--N 48]
      [--gates 0.0,0.5,2.0] [--pairs below_below,mixed]
      [--resume DIR] [--tag NAME] [--quick]

Runs from the repo root (two-fluid/ layout):  python two-fluid/run_two_bubble_gate_scan.py
"""

import torch, numpy as np, sys, json, os, gc, argparse
from datetime import datetime

torch.backends.cudnn.benchmark = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import TwoFluid3DGPU, PHI, PHI_INV

PHI_INV2 = PHI_INV ** 2  # φ⁻² ≈ 0.382, the gate scale in the solver

R_PAIRS = [
    ("below_below", 0.3, 0.5, "Both below pinch (r < φ⁻¹ ≈ 0.618)"),
    ("mixed",       0.5, 1.2, "One below, one above pinch"),
    ("above_above", 1.2, 2.0, "Both above pinch (self-aware)"),
]


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


class GatedTwoFluid3DGPU(TwoFluid3DGPU):
    """TwoFluid3DGPU with Qi-gated conversion: conv = −λ·(1−q)^α·ε.

    (1−q) is the canonical single-gate openness (q = M/(M + φ⁻² + ε²),
    M = (EY+EI)², ε = EY − φ·EI) used by `ExpandingTwoFluid3DGPU` and
    `run_rung_offset_probe.py`. α = 0 reproduces the ungated base solver
    exactly—the 2026-07-19 two-bubble baseline dynamics.
    """

    def __init__(self, gate_alpha=0.0, phi_inv2=PHI_INV2, **kw):
        super().__init__(**kw)
        self.gate_alpha = float(gate_alpha)
        self.phi_inv2 = float(phi_inv2)

    def rhs(self, u_hat, ey_hat, ei_hat):
        # Mirrors TwoFluid3DGPU.rhs() (cassi_two_fluid_3d_gpu.py, lines 134-200)
        # with only the conversion block changed to the gated form.
        u = [torch.fft.ifftn(u_hat[d]).real for d in range(3)]
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        rho = ey + ei
        pi = ey - ei

        rho_hat = torch.fft.fftn(rho)
        if self.rho_ext_hat is not None:
            rho_hat = rho_hat + self.rho_ext_hat
        phi_hat = self._poisson(rho_hat)
        phi = torch.fft.ifftn(phi_hat).real

        adv_u = [torch.zeros_like(u[0]) for _ in range(3)]
        for i in range(3):
            grad_ui = self._grad(u_hat[i])
            for j in range(3):
                adv_u[i] = adv_u[i] + u[j] * grad_ui[j]

        grad_phi = self._grad(phi_hat)
        force = [pi * grad_phi[d] for d in range(3)]

        rhs_u_hat = [
            -torch.fft.fftn(adv_u[d]) + torch.fft.fftn(force[d]) - self.nu * self.k2 * u_hat[d]
            for d in range(3)
        ]
        for d in range(3):
            rhs_u_hat[d] = rhs_u_hat[d] * self.dealias
        rhs_u_hat = self._project(rhs_u_hat)

        grad_ey = self._grad(ey_hat)
        grad_ei = self._grad(ei_hat)
        adv_ey = sum(u[d] * grad_ey[d] for d in range(3))
        adv_ei = sum(u[d] * grad_ei[d] for d in range(3))

        # --- Qi-gated conversion (the only change vs the base solver) ---
        if self.lam != 0.0:
            eps = ey - PHI * ei
            M_qi = (ey + ei) ** 2
            one_minus_q = (self.phi_inv2 + eps ** 2) / (M_qi + self.phi_inv2 + eps ** 2 + 1e-30)
            conv = -self.lam * (one_minus_q ** self.gate_alpha) * eps
        else:
            conv = torch.zeros_like(ey)

        rhs_ey_hat = (-torch.fft.fftn(adv_ey) - self.D * self.k2 * ey_hat +
                      torch.fft.fftn(conv))
        rhs_ei_hat = (-torch.fft.fftn(adv_ei) - self.D * self.k2 * ei_hat -
                      torch.fft.fftn(conv))

        if self.chi != 0.0:
            chi_y = self.chi_yang
            chi_i = self.chi
            flux_y = [chi_y * ey * grad_phi[d] for d in range(3)]
            flux_i = [-chi_i * ei * grad_phi[d] for d in range(3)]
            rhs_ey_hat = rhs_ey_hat - self._divergence_of_flux(flux_y)
            rhs_ei_hat = rhs_ei_hat - self._divergence_of_flux(flux_i)

        rhs_ey_hat = rhs_ey_hat * self.dealias
        rhs_ei_hat = rhs_ei_hat * self.dealias

        return rhs_u_hat, rhs_ey_hat, rhs_ei_hat


def run_one_config(solver, r1, r2, d, radius, steps, dt, seed):
    """Run one bubble-pair configuration; return final_corr, peak_corr, history.

    Seed threading: the 2026-07-19 harness called torch.manual_seed(seed) but
    its initialization contained no random draws, so the "ensemble" was a
    single deterministic trajectory. Here the seed drives a small Gaussian
    background-density perturbation (amplitude 0.02, device generator, same
    pattern as TwoFluid3DGPU.initial_cosmos) so the ensemble measures real
    run-to-run variance. The bubble structure itself stays deterministic.
    """
    N = solver.N
    device = solver.device
    gen = torch.Generator(device=device)
    gen.manual_seed(seed)

    noise = 0.02 * torch.randn(N, N, N, generator=gen,
                               device=device, dtype=torch.float64)
    ey_bg = torch.clamp(torch.ones(N, N, N, dtype=torch.float64,
                                   device=device) * 0.7 + noise, min=0.1)
    ei_bg = torch.clamp(torch.ones(N, N, N, dtype=torch.float64,
                                   device=device) * 0.7 + noise, min=0.1)

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


def separation_sets(N):
    """φ-scaled and control separations, same recipe as run_two_bubble_fast.py."""
    d0 = N // 4
    phi_seps = sorted(set(int(d0 * PHI**k) % N for k in range(-3, 6)
                          if int(d0 * PHI**k) % N >= 2))
    ctl_seps = sorted(set(int(d0 * m) % N for m in [1.3, 1.7, 2.2, 2.8]
                          if int(d0 * m) % N >= 2 and int(d0 * m) % N not in phi_seps))
    return phi_seps, ctl_seps


def save_cells(rdir, cells):
    with open(f"{rdir}/cells.json", "w") as f:
        json.dump(cells, f, indent=1)


def load_cells(rdir):
    p = f"{rdir}/cells.json"
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}


def bootstrap_analysis(all_results, gates, pairs, n_seeds, B=2000, rng_seed=1234):
    """Seed-bootstrap over the ensemble: revival R(α), ΔR, monotonicity."""
    if len(gates) < 2:
        return {}
    rng = np.random.default_rng(rng_seed)
    # per (gate, pair, d): array of per-seed finals (keyed by int separation)
    cells = {}
    for g in gates:
        for pl in pairs:
            cells[(g, pl)] = {}
            for slab, rec in all_results[g][pl]["separations"].items():
                cells[(g, pl)][int(rec["separation"])] = np.array(rec["ensemble"])

    out = {}
    for pl in pairs:
        # large-d φ revival window and control window (same as harness)
        phi_large = [d for d in cells[(gates[0], pl)] if d in (31, 34, 37)]
        phi_all = (2, 4, 7, 12, 19, 31, 34, 37)
        ctls = [d for d in cells[(gates[0], pl)] if d not in phi_all]
        R = {g: np.zeros(B) for g in gates}
        R_agg = {g: np.zeros(B) for g in gates}
        C = {g: np.zeros(B) for g in gates}
        for b in range(B):
            for g in gates:
                idx = rng.integers(0, n_seeds, size=n_seeds)
                dmeans = {d: cells[(g, pl)][d][idx].mean() for d in cells[(g, pl)]}
                R[g][b] = np.mean([dmeans[d] for d in phi_large])
                R_agg[g][b] = np.mean([dmeans[d] for d in phi_all if d in cells[(g, pl)]])
                C[g][b] = np.mean([dmeans[d] for d in ctls]) if ctls else 0.0
        g0, g1, g2 = gates
        dR_strong = R[g2] - R[g0]
        dR_weak = R[g1] - R[g0]
        # monotone order across the three gate values
        mono_up = (R[g0] <= R[g1]) & (R[g1] <= R[g2])
        mono_dn = (R[g0] >= R[g1]) & (R[g1] >= R[g2])
        out[pl] = {
            "gates": gates,
            "revival_window_d": phi_large,
            "ctl_window_d": ctls,
            "R_mean": {str(g): float(R[g].mean()) for g in gates},
            "R_ci95": {str(g): [float(np.percentile(R[g], 2.5)), float(np.percentile(R[g], 97.5))] for g in gates},
            "R_agg_mean": {str(g): float(R_agg[g].mean()) for g in gates},
            "C_mean": {str(g): float(C[g].mean()) for g in gates},
            "dR_strong_vs_baseline": {
                "mean": float(dR_strong.mean()),
                "ci95": [float(np.percentile(dR_strong, 2.5)), float(np.percentile(dR_strong, 97.5))],
                "p_positive": float((dR_strong > 0).mean()),
            },
            "dR_weak_vs_baseline": {
                "mean": float(dR_weak.mean()),
                "ci95": [float(np.percentile(dR_weak, 2.5)), float(np.percentile(dR_weak, 97.5))],
                "p_positive": float((dR_weak > 0).mean()),
            },
            "monotone_up_frac": float(mono_up.mean()),
            "monotone_down_frac": float(mono_dn.mean()),
            "flat_frac": float((~mono_up & ~mono_dn).mean()),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=48)
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--gates", type=str, default="0.0,0.5,2.0")
    ap.add_argument("--pairs", type=str, default="below_below,mixed")
    ap.add_argument("--resume", type=str, default=None)
    ap.add_argument("--tag", type=str, default=None)
    ap.add_argument("--quick", action="store_true",
                    help="smoke test: gates=0.0, below_below, seps {19,34}, 1 seed")
    args = ap.parse_args()

    N, lam, dt, steps, radius, n_seeds = args.N, 0.02, 0.0005, args.steps, max(4.0, args.N / 12.0), args.seeds

    if args.quick:
        gates = [0.0]
        pairs = [p for p in R_PAIRS if p[0] == "below_below"]
        quick_seps = [19, 34]
        n_seeds = 1
    else:
        gates = [float(g) for g in args.gates.split(",")]
        pair_lbls = args.pairs.split(",")
        pairs = [p for p in R_PAIRS if p[0] in pair_lbls]

    phi_seps, ctl_seps = separation_sets(N)
    all_seps = phi_seps + ctl_seps
    if args.quick:
        all_seps = quick_seps

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={N}  steps={steps}  seeds={n_seeds}", flush=True)
    print(f"Gates α: {gates}   r-pairs: {[p[0] for p in pairs]}", flush=True)
    print(f"φ-seps: {phi_seps}  ctl: {ctl_seps}", flush=True)
    print(f"Gate: conv = −λ·(1−q)^α·ε,  (1−q) = (φ⁻²+ε²)/(M+φ⁻²+ε²),  α=0 ≡ 2026-07-19 ungated baseline", flush=True)

    solvers = {g: GatedTwoFluid3DGPU(N=N, lam=lam, D=0.0001, nu=0.0005,
                                     chi=0.0, gate_alpha=g, device=device)
               for g in gates}

    rid = args.tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = args.resume if args.resume else f"runs/{rid}_two_bubble_gate"
    os.makedirs(rdir, exist_ok=True)
    cells = load_cells(rdir)
    print(f"Run dir: {rdir}  (cells cached: {len(cells)})", flush=True)

    n_done = 0
    for alpha in gates:
        for pair_label, r1, r2, desc in pairs:
            for d in all_seps:
                for seed in range(42, 42 + n_seeds):
                    key = f"{alpha}|{pair_label}|{d}|{seed}"
                    if key in cells:
                        continue
                    fc, pc, hist = run_one_config(solvers[alpha], r1, r2, d,
                                                  radius, steps, dt, seed)
                    cells[key] = {"alpha": alpha, "pair": pair_label, "d": d,
                                  "seed": seed, "final": fc, "peak": pc,
                                  "history": hist}
                    n_done += 1
                    if n_done % 12 == 0:
                        save_cells(rdir, cells)
                        print(f"  [{n_done} cells] α={alpha} {pair_label} d={d} "
                              f"seed={seed} final={fc:+.4f} peak={pc:+.4f}", flush=True)
    save_cells(rdir, cells)

    # Build per-gate/pair result structure
    all_results = {}
    for alpha in gates:
        all_results[alpha] = {}
        for pair_label, r1, r2, desc in pairs:
            pair_results = {}
            for d in all_seps:
                ens = [cells[f"{alpha}|{pair_label}|{d}|{s}"]["final"]
                       for s in range(42, 42 + n_seeds)]
                is_phi = d in phi_seps
                pair_results[f"d={d}" + (" φ" if is_phi else " ctl")] = {
                    "separation": d, "is_phi": is_phi,
                    "mean": float(np.mean(ens)), "std": float(np.std(ens)),
                    "ensemble": ens,
                }
            phi_mu = np.mean([r["mean"] for r in pair_results.values() if r["is_phi"]])
            ctl_recs = [r for r in pair_results.values() if not r["is_phi"]]
            ctl_mu = float(np.mean([r["mean"] for r in ctl_recs])) if ctl_recs else 0.0
            ratio = float(phi_mu / max(abs(ctl_mu), 1e-30)) if ctl_recs else None
            all_results[alpha][pair_label] = {
                "r1": r1, "r2": r2, "phi_mean": float(phi_mu),
                "ctl_mean": ctl_mu,
                "ratio": ratio,
                "separations": pair_results,
            }

    # Print per-gate tables
    print("\n\n=== PER-GATE RESULTS ===")
    for alpha in gates:
        print(f"\n--- gate α = {alpha} ---")
        for pair_label, r1, r2, desc in pairs:
            data = all_results[alpha][pair_label]
            print(f"{pair_label:<14} φ-mu={data['phi_mean']:+.4f} "
                  f"ctl-mu={data['ctl_mean']:+.4f} "
                  f"φ/ctl={data['ratio']:.2f}×" if data["ratio"] is not None else
                  f"{pair_label:<14} φ-mu={data['phi_mean']:+.4f} "
                  f"ctl-mu={data['ctl_mean']:+.4f} φ/ctl=n/a")
            for slab, rec in data["separations"].items():
                print(f"    {slab:12s} {rec['mean']:+.4f}±{rec['std']:.4f}")

    # Bootstrap significance
    boot = bootstrap_analysis(all_results, gates, [p[0] for p in pairs], n_seeds)
    print("\n\n=== BOOTSTRAP (2000 draws over seeds) ===")
    for pl in boot:
        b = boot[pl]
        print(f"\n{pl}: revival window d={b['revival_window_d']} vs ctl d={b['ctl_window_d']}")
        for g in gates:
            print(f"  α={g}: R={b['R_mean'][str(g)]:+.4f}  "
                  f"95% CI [{b['R_ci95'][str(g)][0]:+.4f}, {b['R_ci95'][str(g)][1]:+.4f}]  "
                  f"R_agg={b['R_agg_mean'][str(g)]:+.4f}")
        dR = b["dR_strong_vs_baseline"]
        print(f"  ΔR(strong−baseline): {dR['mean']:+.4f}  "
              f"95% CI [{dR['ci95'][0]:+.4f}, {dR['ci95'][1]:+.4f}]  P(Δ>0)={dR['p_positive']:.3f}")
        dW = b["dR_weak_vs_baseline"]
        print(f"  ΔR(weak−baseline):   {dW['mean']:+.4f}  "
              f"95% CI [{dW['ci95'][0]:+.4f}, {dW['ci95'][1]:+.4f}]  P(Δ>0)={dW['p_positive']:.3f}")
        print(f"  monotone up: {b['monotone_up_frac']:.3f}  "
              f"monotone down: {b['monotone_down_frac']:.3f}  flat: {b['flat_frac']:.3f}")

    # Peak-position shift in the large-d window
    print("\n=== LARGE-d PEAK POSITION (argmax over d∈{31,33,34,37}) ===")
    peak_shift = {}
    for alpha in gates:
        for pair_label, r1, r2, desc in pairs:
            data = all_results[alpha][pair_label]["separations"]
            win = {rec["separation"]: rec["mean"] for rec in data.values()
                   if rec["separation"] in (31, 33, 34, 37)}
            if len(win) < 2:
                continue
            best = max(win, key=win.get)
            peak_shift.setdefault(pair_label, {})[alpha] = {"argmax_d": best,
                                                            "value": win[best]}
            print(f"  α={alpha} {pair_label}: argmax d={best} (corr {win[best]:+.4f})")

    # Save final results
    output = {
        "N": N, "steps": steps, "n_seeds": n_seeds, "dt": dt, "lam": lam,
        "radius": radius, "gates": gates, "phi_separations": phi_seps,
        "control_separations": ctl_seps,
        "gate_definition": "conv = -lam*(1-q)^alpha*eps; (1-q) = (phi^-2+eps^2)/(M+phi^-2+eps^2); alpha=0 is the ungated 2026-07-19 baseline",
        "results": {str(alpha): all_results[alpha] for alpha in gates},
        "bootstrap": boot,
        "peak_shift": peak_shift,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to {rdir}/results.json", flush=True)

    # Plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(len(pairs), 1, figsize=(12, 3.5 * len(pairs)))
        if len(pairs) == 1:
            axes = [axes]
        for idx, (pair_label, r1, r2, desc) in enumerate(pairs):
            ax = axes[idx]
            x = np.arange(len(all_seps))
            width = 0.27
            colors = ["C0" if d in phi_seps else "C3" for d in all_seps]
            for j, alpha in enumerate(gates):
                means = [all_results[alpha][pair_label]["separations"][
                    f"d={d}" + (" φ" if d in phi_seps else " ctl")]["mean"] for d in all_seps]
                ax.bar(x + (j - 1) * width, means, width, alpha=0.75,
                       label=f"α={alpha}", color=colors if j == 0 else None)
            ax.axhline(0, color="k", lw=0.5)
            ax.set_xticks(x)
            ax.set_xticklabels([f"d={d}" + ("φ" if d in phi_seps else "") for d in all_seps],
                               rotation=45, ha="right", fontsize=8)
            ax.set_ylabel("Cross-correlation (final)")
            ax.set_title(f"{pair_label} (r1={r1}, r2={r2}): gate scan")
            ax.legend(fontsize=8)
            ax.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{rdir}/two_bubble_gate_scan.png", dpi=120)
        plt.close()
        print(f"Figure: {rdir}/two_bubble_gate_scan.png", flush=True)
    except Exception as e:
        print(f"Plot skipped: {e}", flush=True)

    # Clean GPU teardown (ROCm hangs at interpreter exit otherwise)
    del solvers, cells
    gc.collect()
    torch.cuda.synchronize()


if __name__ == "__main__":
    try:
        main()
    finally:
        # ROCm 7.2.1 hangs at interpreter teardown unless GPU objects are
        # released and synchronized first; also applies after exceptions.
        import gc as _gc
        _gc.collect()
        torch.cuda.synchronize()
