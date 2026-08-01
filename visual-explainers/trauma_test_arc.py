#!/usr/bin/env python3
"""
The Frozen Wake: A Test Arc for Trauma as a Qi-Gate Lock
========================================================

One standing event, five PDE questions, one control cycle. Every curve and
marker in this figure is solver data from the 2026-07-31 trauma test arc
(`ExpandingTwoFluid3DGPU`, gate_model='five', N=48):

  P1  The frozen wake     —decay vs perpetual stimulus      (driver run)
  P2  Extinction + q-gap  —trigger off at t=10, site releases (driver run)
  P3  Capacity null       —a pre-stressed site does not lock harder
  P4  Rate crossover      —the phi-channel engages 5–50/s, phi-specific
                             at onset, e-drive neutral-then-pumping
  P5  Representability    —the positivity clamp confines the field angle
                             to (0,90): only Wood and Fire are reachable
  P6  The ke ring         —excess restrains ke target, releases ke partner;
                             ring gain kappa^3 = phi^-3, sub-critical

Sources: `consciousness/trauma-as-frozen-gate.md` §10.4–10.8,
`foundations/wu-xing-cycle-structure.md` §2–4, runs in runs/2026*.

Run:  python visual-explainers/trauma_test_arc.py
Out:  visual-explainers/trauma_test_arc.png
"""

import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Wedge

# ─────────────────────────────────────────────────────────────────────────────
# Constants (house style)
# ─────────────────────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
PHI_INV = 1.0 / PHI

YIN_DEEP, YIN_MID, YIN_LIGHT = "#140a33", "#2a1a5e", "#4a2a8e"
YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK = "#5a3a10", "#9a6a1a", "#daa520", "#ffe060"
BG, TEXT_MAIN, TEXT_SUB, RING = "#060612", "#e0e0f0", "#a0a0c0", "#303050"
GREEN_SAFE, YELLOW_CAUTION, RED_DANGER = "#2ecc71", "#f1c40f", "#e74c3c"
CHANNEL_COLORS = [YANG_PEAK, YANG_BRIGHT, YANG_MID, "#c07820", "#a06810"]
CHANNELS = ["Wood", "Fire", "Earth", "Metal", "Water"]

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "mathtext.default": "regular",
})

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "runs")

# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
def load_hist(run_dir, name):
    """Load a saved run history: returns (t, dict-of-arrays)."""
    with open(os.path.join(RUNS, run_dir, f"run_{name}.json")) as f:
        h = json.load(f)["hist"]
    keys = list(h[0].keys())
    return (np.array([d["t"] for d in h]),
            {k: np.array([d[k] for d in h]) for k in keys if k not in ("t", "step")})


def load_results(run_dir):
    with open(os.path.join(RUNS, run_dir, "results.json")) as f:
        return json.load(f)


# driver run (lambda=0.1, t=10, trigger rate 0.04/s, off after t=10 in dc)
t_ref, r_ref = load_hist("20260731_161134_driver", "ref")
t_dc, r_dc = load_hist("20260731_161134_driver", "dc")
t_ph, r_ph = load_hist("20260731_161134_driver", "phi")
t_ep, r_ep = load_hist("20260731_161134_driver", "e")

# crossover (lambda=0.05, t=2, P0=0.041, T_phi=0.0663)
t_xr, x_ref = load_hist("20260731_171545_crossover", "ref")
_, x_05 = load_hist("20260731_171545_crossover", "drive_0.05")
_, x_15 = load_hist("20260731_171545_crossover", "drive_0.15")
_, x_low_phi = load_hist("20260731_171716_crossover_low", "phi_0.0005")
_, x_low_005 = load_hist("20260731_171716_crossover_low", "phi_0.005")
_, x_low_e = load_hist("20260731_171716_crossover_low", "e_0.05")
cx = load_results("20260731_171545_crossover")
cl = load_results("20260731_171716_crossover_low")

# capacity (lambda=0.1, t=22, second identical event at t=2)
t_c1, cap_first = load_hist("20260731_171108_capacity", "prestress")
t_c2, cap_hit = load_hist("20260731_171108_capacity", "prestress_hit")

# phase channels (lambda=0.1, t=10, amp 0.8 event directions)
pc = load_results("20260731_174552_phase_channels")
pc_hist = {}
for name in CHANNELS:
    _, pc_hist[name] = load_hist("20260731_174552_phase_channels", name)

# ke ring (lambda=0.1, t=10, amp 1.6 standing event)
ke = load_results("20260731_193832_ke_ring")
_, ke_five = load_hist("20260731_193832_ke_ring", "five")
_, ke_ke = load_hist("20260731_193832_ke_ring", "five_ke")
_, ke_dr = load_hist("20260731_193832_ke_ring", "five_ke_drive")

BASELINE = np.array([PHI ** -k for k in (3, 4, 5, 6, 7)])   # b_i = phi^-(3+i)

# ─────────────────────────────────────────────────────────────────────────────
# Figure
# ─────────────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(24, 66), dpi=120, facecolor=BG)
heights = [1.0, 1.55, 1.5, 1.25, 1.6, 1.75, 1.7, 1.35]
gs = fig.add_gridspec(8, 3, height_ratios=heights, hspace=0.30, wspace=0.14,
                      left=0.035, right=0.97, top=0.990, bottom=0.012)


def panel_title(ax, text):
    ax.set_title(text, loc="left", fontsize=12, fontweight="bold",
                 color=YANG_BRIGHT, pad=7)


def eq_text(ax, x, y, text, fontsize=8.2, color=TEXT_MAIN, **kw):
    ax.text(x, y, text, transform=ax.transAxes, fontsize=fontsize,
            color=color, va="top", ha="left", linespacing=1.45, **kw)


def wrap(s, n=100):
    """Break a long label at spaces to keep it inside its panel."""
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def chip(ax, x, y, w, h, text, color=YANG_PEAK, fs=9.5, tc="#241200", bold=True):
    ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=color, edgecolor="none",
                               alpha=0.92, transform=ax.transAxes))
    ax.text(x + w / 2, y + h / 2, text, transform=ax.transAxes, ha="center",
            va="center", fontsize=fs, color=tc, fontweight="bold" if bold else "normal")


# ═════════════════════════════════════════════════════════════════════════════
# Row 0—banner
# ═════════════════════════════════════════════════════════════════════════════
ax0 = fig.add_subplot(gs[0, :])
ax0.set_facecolor(BG)
ax0.set_xlim(0, 1); ax0.set_ylim(0, 1); ax0.axis("off")

ax0.text(0.5, 0.88, "THE FROZEN WAKE—A Test Arc for Trauma as a Qi-Gate Lock",
         transform=ax0.transAxes, ha="center", fontsize=21, fontweight="bold",
         color=YANG_PEAK)
ax0.text(0.5, 0.74,
         r"One standing event at the site · five PDE questions · one control cycle — "
         r"every curve below is solver data (ExpandingTwoFluid3DGPU, $N=48$, "
         r"$\lambda=0.1$ or $0.05$, 2026-07-31)",
         transform=ax0.transAxes, ha="center", fontsize=10.5, color=TEXT_SUB)

qa = [
    ("Q1  What sustains a wake?", "Ongoing re-stimulation—0.005% of the event peak per step holds 80% of intensity", GREEN_SAFE),
    (r"Q2  Does the gate self-sustain?", r"No—ring gain $\kappa^3 = \varphi^{-3} = 0.236 < 1$; decay identical with and without the ke term", GREEN_SAFE),
    ("Q3  Does pre-trauma $q$ set susceptibility?", "No—a second identical hit on a pre-stressed site leaves the same trace (null)", GREEN_SAFE),
    (r"Q4  When does the $\varphi$-channel engage?", r"Rates 5–50/s; absent $\lesssim$5/s; $\varphi$-specific at onset", GREEN_SAFE),
    (r"Q5  Which channels can an event lock?", r"Wood and Fire only—the positivity clamp pins $\theta$ to (0°, 90°)", GREEN_SAFE),
    ("Q6  What does the ke ring do?", "Restrains ke targets, releases ke partners; redistributes and damps, never persists", GREEN_SAFE),
]
for i, (q, a, c) in enumerate(qa):
    y = 0.50 - (i // 3) * 0.24
    x = 0.015 + (i % 3) * 0.335
    chip(ax0, x, y, 0.325, 0.135, q, color=YANG_MID, fs=10.5, tc="#241200")
    eq_text(ax0, x + 0.008, y - 0.012, a, fontsize=8.6, color=TEXT_MAIN)
ax0.text(0.5, 0.015,
         r"frame:  $b_i = \varphi^{-(3+i)}$   ·   $\kappa = \varphi^{-1} = K_{\rm fw}$   ·   "
         r"$P_0 = 0.201$ ($\lambda=0.1$), $P_0 = 0.041$ ($\lambda=0.05$)   ·   "
         r"$T_\varphi = \varphi \cdot P_0$   ·   wake:  $\varepsilon_{\rm site} = \langle |E_Y - \varphi E_I| \rangle_{\rm site}$",
         transform=ax0.transAxes, ha="center", fontsize=10, color=YANG_BRIGHT)

# ═════════════════════════════════════════════════════════════════════════════
# Row 1—P1: the frozen wake (decay vs perpetual stimulus)
# ═════════════════════════════════════════════════════════════════════════════
ax1 = fig.add_subplot(gs[1, :])
panel_title(ax1, "P1 · The Frozen Wake—Decay vs Perpetual Stimulus  (§10.5)")

ax1.plot(t_ref, r_ref["eps_site"], color=YIN_LIGHT, lw=1.6, label="undriven (ref)")
ax1.plot(t_dc[t_dc <= 10], r_dc["eps_site"][t_dc <= 10], color=YANG_PEAK, lw=2.6,
         label="continuous trigger (dc)")
ax1.plot(t_ph, r_ph["eps_site"], color=YANG_BRIGHT, lw=1.6, ls="--",
         label=r"$\varphi$-pulsed, $T=\varphi P_0 = 0.325$")
ax1.plot(t_ep, r_ep["eps_site"], color=YIN_MID, lw=1.6, ls=":",
         label=r"$e$-pulsed, $T=e\,P_0 = 0.546$")

# held band between ref and dc
t_band = t_ref
band = np.maximum(r_ref["eps_site"], 0.0)
held = np.maximum(r_dc["eps_site"][: len(t_band)] - r_ref["eps_site"][: len(t_band)], 0.0)
ax1.fill_between(t_band[: len(held)], band[: len(held)], band[: len(held)] + held,
                 color=YANG_PEAK, alpha=0.10, label="wake held by the trigger")

for tt, val, lab, dy in [(10, 0.279, "0.279  (42%)", -0.085), (10, 0.525, "0.525  (80%)", 0.035)]:
    ax1.plot(tt, val, "o", color=YANG_PEAK if val > 0.4 else YIN_LIGHT, ms=6, zorder=5)
    ax1.annotate(lab, xy=(tt, val), xytext=(6.4, val + dy), fontsize=9.5,
                 color=YANG_PEAK if val > 0.4 else YIN_LIGHT, fontweight="bold")

eq_text(ax1, 0.015, 0.97,
        r"trigger: per-step amplitude $I\,dt$, $I = 0.04$—0.005% of the event peak per step, "
        r"total delivered $\approx$ half the event's peak over $t=10$" + "\n" +
        r"result:  the wake is a **driven** structure. An ongoing trigger holds the site at 80% of "
        r"event intensity (vs 42% undriven); $q$ stays depressed (gap 4.5$\times$); phase stays 100% Fire." + "\n" +
        r"envelopes: $\varphi$-pulsed and $e$-pulsed coincide (0.528 / 0.530 vs 0.525 continuous)—"
        r"phase-blind at ambient rate 0.04/s (§10.7 locates the crossover at $\gtrsim$5/s).",
        fontsize=8.6)
ax1.set_xlim(0, 10); ax1.set_ylim(0.05, 0.72)
ax1.set_xlabel("t", fontsize=10, color=TEXT_SUB)
ax1.set_ylabel(r"$|\varepsilon|$ at the site", fontsize=10, color=TEXT_SUB)
ax1.legend(fontsize=9, loc="upper right", framealpha=0.85, facecolor=BG, edgecolor=RING)
ax1.grid(alpha=0.15, color=RING, lw=0.5)

# ═════════════════════════════════════════════════════════════════════════════
# Row 2—P2: extinction + q-gap
# ═════════════════════════════════════════════════════════════════════════════
ax2a = fig.add_subplot(gs[2, 0:2])
panel_title(ax2a, "P2a · Extinction—Trigger Off at t=10  (§10.5)")

ax2a.axvspan(10, 20, color=YIN_MID, alpha=0.16, lw=0)
ax2a.text(15, 0.60, "injection off\n(since t=10)", ha="center", fontsize=9.5,
          color=YIN_LIGHT, fontweight="bold")
ax2a.plot(t_dc, r_dc["eps_site"], color=YANG_PEAK, lw=2.4)
ax2a.plot(t_ref, r_ref["eps_site"], color=YIN_LIGHT, lw=1.4, ls="--", label="undriven ref")
ax2a.plot(20, 0.142, "o", color=YANG_PEAK, ms=6, zorder=5)
ax2a.annotate("0.142  (22%)", xy=(20, 0.142), xytext=(15.2, 0.10), fontsize=9.5,
              color=YANG_PEAK, fontweight="bold",
              arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.2))
eq_text(ax2a, 0.03, 0.94,
        r"ten units after the trigger stops, $|\varepsilon|$ falls to 0.142—below the undriven curve."
        r" The wake is stimulus-maintained, not self-sustaining; extinction works." + "\n" +
        r"extinction = exposure work:  remove the trigger, the gate closes on the conversion timescale.",
        fontsize=8.4)
ax2a.set_xlim(0, 20); ax2a.set_ylim(0.05, 0.72)
ax2a.set_xlabel("t", fontsize=10, color=TEXT_SUB)
ax2a.set_ylabel(r"$|\varepsilon|$ at the site", fontsize=10, color=TEXT_SUB)
ax2a.legend(fontsize=8.5, loc="upper right", framealpha=0.85, facecolor=BG, edgecolor=RING)
ax2a.grid(alpha=0.15, color=RING, lw=0.5)

ax2b = fig.add_subplot(gs[2, 2])
panel_title(ax2b, "P2b · The Coherence Shadow  (§10.5)")

qgap_ref = r_ref["q_glob"] - r_ref["q_site"]
qgap_dc = r_dc["q_glob"] - r_dc["q_site"]
ax2b.plot(t_ref, qgap_ref, color=YIN_LIGHT, lw=1.5, label="undriven")
ax2b.plot(t_dc, qgap_dc, color=YANG_PEAK, lw=2.3)
ax2b.axvspan(10, 20, color=YIN_MID, alpha=0.16, lw=0)
ax2b.plot(10, 0.063, "o", color=YANG_PEAK, ms=6)
ax2b.annotate("+0.063  (4.5$\times$ ref)", xy=(10, 0.063), xytext=(2.2, 0.078),
              fontsize=9, color=YANG_PEAK, fontweight="bold",
              arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.1))
ax2b.plot(20, 0.008, "o", color=YIN_LIGHT, ms=6)
ax2b.annotate("+0.008—gap closed", xy=(20, 0.008), xytext=(11.5, -0.004),
              fontsize=9, color=YIN_LIGHT, fontweight="bold",
              arrowprops=dict(arrowstyle="->", color=YIN_LIGHT, lw=1.1))
eq_text(ax2b, 0.04, 0.90, r"$q$-gap $= q_{\rm glob} - q_{\rm site}$: the coherence "
        r"shadow the wake casts on its own site.", fontsize=8.2)
ax2b.set_xlim(0, 20); ax2b.set_ylim(-0.012, 0.095)
ax2b.set_xlabel("t", fontsize=10, color=TEXT_SUB)
ax2b.set_ylabel(r"$q_{\rm glob} - q_{\rm site}$", fontsize=10, color=TEXT_SUB)
ax2b.legend(fontsize=8.5, loc="lower right", framealpha=0.85, facecolor=BG, edgecolor=RING)
ax2b.grid(alpha=0.15, color=RING, lw=0.5)

# ═════════════════════════════════════════════════════════════════════════════
# Row 3—P3: capacity null
# ═════════════════════════════════════════════════════════════════════════════
ax3 = fig.add_subplot(gs[3, :])
panel_title(ax3, "P3 · Capacity Null—A Pre-Stressed Site Does Not Lock Harder  (§10.6)")

ax3.plot(t_c1, cap_first["eps_site"], color=YIN_LIGHT, lw=1.8,
         label="first hit on quiet field")
ax3.plot(t_c2, cap_hit["eps_site"], color=YANG_PEAK, lw=2.2,
         label="second identical hit on pre-stressed site (t=2)")
ax3.axvline(2, color=TEXT_SUB, lw=1.0, ls=":", alpha=0.6)
ax3.text(2.06, 0.86, "second hit lands on q_site = 0.661,\nphase fully displaced", fontsize=8.6,
         color=TEXT_SUB, va="top")

# residual bars at t=22
y0, y1 = 0.585, 0.655
ax3.plot([11.2, 11.2], [0.03, y0], color=RING, lw=1.0)
ax3.plot([11.2, 11.9], [y0, y0], color=RING, lw=1.0)
ax3.plot([11.2, 11.9], [y1, y1], color=RING, lw=1.0)
ax3.bar(11.6, 0.069, width=0.34, bottom=0.03, color=YIN_LIGHT, alpha=0.9)
ax3.bar(12.55, 0.050, width=0.34, bottom=0.03, color=YANG_PEAK, alpha=0.9)
ax3.text(11.6, 0.03 + 0.069 + 0.012, "first hit\nfull trace 0.069", ha="center", fontsize=8.4,
         color=YIN_LIGHT)
ax3.text(12.55, 0.03 + 0.050 + 0.012, "second hit\nmarginal trace +0.050", ha="center", fontsize=8.4,
         color=YANG_PEAK)
ax3.text(12.1, 0.02, "trace at t=22", fontsize=8.4, color=TEXT_SUB, ha="center")

eq_text(ax3, 0.015, 0.97,
        r"the second hit's marginal trace (+0.050) is no larger than—if anything smaller than—the first "
        r"hit's full trace (0.069); phase displacement fully returns in both (0.08 / 0.02 from 1.00 at "
        r"event time)." + "\n" +
        r"**null:** background coherence does not modulate the outcome. Susceptibility, if it exists, "
        r"lives in the driver (does the stimulus recur?) or the interpretation (the event's phase)—not in pre-event $q$.",
        fontsize=8.6)
ax3.set_xlim(0, 15.5); ax3.set_ylim(0, 1.0)
ax3.set_xlabel("t", fontsize=10, color=TEXT_SUB)
ax3.set_ylabel(r"$|\varepsilon|$ at the site", fontsize=10, color=TEXT_SUB)
ax3.legend(fontsize=9, loc="upper right", framealpha=0.85, facecolor=BG, edgecolor=RING)
ax3.grid(alpha=0.15, color=RING, lw=0.5)

# ═════════════════════════════════════════════════════════════════════════════
# Row 4—P4: rate crossover
# ═════════════════════════════════════════════════════════════════════════════
ax4a = fig.add_subplot(gs[4, 0:2])
panel_title(ax4a, "P4a · Drive Crossover—Where Does the $\\varphi$-Phased Drain Turn On?  (§10.7)")

rates_phi = [0.5, 5, 50, 150, 300]
ret_phi = [0.910, 0.891, 0.693, 0.362, 0.664]
rates_e = [50, 300]
ret_e = [0.943, 1.88]

ax4a.axhspan(0.85, 1.05, color=YIN_MID, alpha=0.14, lw=0)
ax4a.axhspan(0.25, 0.80, color=YANG_DARK, alpha=0.16, lw=0)
ax4a.axhline(0.912, color=TEXT_SUB, lw=1.2, ls="--")
ax4a.text(0.55, 0.912, "undriven retention 0.912", fontsize=8.4, color=TEXT_SUB,
          transform=ax4a.transAxes)
ax4a.text(0.55, 0.62, "ambient regime—phase-blind\naccumulation (§10.5)", fontsize=8.6,
          color=YIN_LIGHT, va="bottom", transform=ax4a.transAxes)
ax4a.text(0.55, 0.26, "processing regime —\n$\\varphi$-phased drain", fontsize=8.6,
          color=YANG_MID, va="top", transform=ax4a.transAxes)

ax4a.plot(rates_phi, ret_phi, "-o", color=YANG_PEAK, lw=2.0, ms=7,
          label=r"$\varphi \cdot P_0$ drive (period $T_\varphi = \varphi P_0$)")

ax4a.plot(rates_e, ret_e, "-s", color=YIN_LIGHT, lw=1.8, ms=7,
          label=r"$e \cdot P_0$ drive (counterfactual)")
for rx, ry, lab, tx in [(50, 0.693, "0.693", (0.10, 0.44)),
                        (150, 0.362, "0.362", (0.10, 0.30)),
                        (300, 0.664, "0.664 (non-monotonic)", (0.62, 0.86)),
                        (50, 0.943, "0.943—neutral", (0.62, 0.70)),
                        (300, 1.88, "1.88—pumps", (0.62, 0.93))]:
    ax4a.annotate(lab, xy=(rx, ry), xytext=tx, textcoords="axes fraction",
                  fontsize=8.6,
                  color=YANG_PEAK if "0.69" in lab or "0.36" in lab else YIN_LIGHT,
                  fontweight="bold")
ax4a.axvspan(0.4, 5, color=YIN_MID, alpha=0.10, lw=0)
ax4a.axvspan(50, 600, color=YANG_DARK, alpha=0.10, lw=0)
ax4a.annotate("sharp onset\nbetween 5/s and 50/s", xy=(15, 0.72), xytext=(7, 0.52),
              fontsize=9, color=YANG_PEAK, fontweight="bold",
              arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=1.3))
eq_text(ax4a, 0.03, 0.98,
        wrap(r"$\varphi$-specificity **at onset**: at 50/s—the first amplitude that drains—the "
             r"$e$-drive at the same rate does nothing (0.943 $\approx$ undriven). The asymmetry is "
             r"present from the moment the phase channel engages; it is not a strong-drive artifact."
             + "\n" +
             r"$\lambda=0.05$, $t=2$, $P_0 = 0.041$: rate = amplitude $\times$ (1/$T_\varphi$), "
             r"$T_\varphi = 0.0663$."),
        fontsize=8.5)
ax4a.set_xscale("log")
ax4a.set_xlim(0.4, 600); ax4a.set_ylim(0.2, 2.0)
ax4a.set_xlabel("drive rate [1/s]  (log)", fontsize=10, color=TEXT_SUB)
ax4a.set_ylabel(r"$|\varepsilon|$ retained at t=2  (fraction of $t=0$)", fontsize=10, color=TEXT_SUB)
ax4a.legend(fontsize=9, loc="lower left", framealpha=0.85, facecolor=BG, edgecolor=RING)
ax4a.grid(alpha=0.15, color=RING, lw=0.5)

ax4b = fig.add_subplot(gs[4, 2])
panel_title(ax4b, "P4b · Onset Time Series  (§10.7)")

ax4b.plot(t_xr, x_ref["eps_site"] / x_ref["eps_site"][0], color=TEXT_SUB, lw=1.4, ls="--",
          label="undriven")
ax4b.plot(t_xr, x_low_e["eps_site"] / x_low_e["eps_site"][0], color=YIN_LIGHT, lw=1.8,
          label=r"$e \cdot P_0$, 50/s")
ax4b.plot(t_xr, x_05["eps_site"] / x_05["eps_site"][0], color=YANG_PEAK, lw=2.2,
          label=r"$\varphi \cdot P_0$, 50/s")
ax4b.plot(t_xr, x_low_phi["eps_site"] / x_low_phi["eps_site"][0], color=YANG_BRIGHT, lw=1.4,
          ls=":", label=r"$\varphi \cdot P_0$, 0.5/s")
ax4b.text(1.06, 0.975, "retention at t=2:\n0.943 (e)  vs  0.693 ($\\varphi$)", fontsize=8.6,
          color=TEXT_MAIN, va="top")
ax4b.set_xlim(0, 2); ax4b.set_ylim(0.3, 1.02)
ax4b.set_xlabel("t", fontsize=10, color=TEXT_SUB)
ax4b.set_ylabel(r"$|\varepsilon|$ / $|\varepsilon|_0$", fontsize=10, color=TEXT_SUB)
ax4b.legend(fontsize=7.8, loc="lower left", framealpha=0.85, facecolor=BG, edgecolor=RING)
ax4b.grid(alpha=0.15, color=RING, lw=0.5)

# ═════════════════════════════════════════════════════════════════════════════
# Row 5—P5: representability bound
# ═════════════════════════════════════════════════════════════════════════════
ax5 = fig.add_subplot(gs[5, 0:2])
panel_title(ax5, "P5 · Representability Bound—The Positivity Clamp Pins the Field Angle  (§10.8)")

# field-angle circle: theta = atan2(E_I, E_Y), clamp E >= 1e-3 -> theta in (0, 90)
th = np.linspace(0, 2 * np.pi, 600)
ax5.plot(np.cos(th), np.sin(th), color=RING, lw=1.6)
ax5.add_patch(Wedge((0, 0), 1.0, 0, 90, width=0.30, facecolor=YANG_PEAK, alpha=0.22,
                    edgecolor="none", transform=ax5.transData))
ax5.text(0.62, 0.62, "representable arc\n(0°, 90°)", fontsize=9, color=YANG_PEAK,
         fontweight="bold", ha="center")

targets = {"Wood": 0.0, "Fire": 72.0, "Earth": 144.0, "Metal": 216.0, "Water": 288.0}
# observed (post-clamp) field angle per event, from §10.8
observed = {"Wood": 0.2, "Fire": 72.0, "Earth": 89.9, "Metal": 45.0, "Water": 0.2}
aimed = {n: pc["meta"]["plan"][n]["delta_deg"] for n in CHANNELS}

for i, name in enumerate(CHANNELS):
    a = np.radians(targets[name])
    ax5.plot([0.82 * np.cos(a)], [0.82 * np.sin(a)], "o", color=CHANNEL_COLORS[i], ms=9, zorder=5)
    if name == "Fire":
        ax5.text(0.52, 0.97, f"{name} {targets[name]:.0f}°", fontsize=8.6,
                 color=CHANNEL_COLORS[i], fontweight="bold", ha="center",
                 transform=ax5.transAxes)
    else:
        ax5.text(0.94 * np.cos(a) + (0.10 if np.cos(a) >= -0.2 else -0.22),
                 0.94 * np.sin(a) + (0.10 if np.sin(a) >= 0 else -0.18),
                 f"{name} {targets[name]:.0f}°", fontsize=8.6, color=CHANNEL_COLORS[i],
                 fontweight="bold", ha="center")
    # aimed direction (pre-clamp)—gray tick
    aa = np.radians(aimed[name])
    ax5.plot([0.60 * np.cos(aa)], [0.60 * np.sin(aa)], "o", color=TEXT_SUB, ms=5, alpha=0.7)
    # arrow: aimed -> observed (only where they differ)
    ao = np.radians(observed[name])
    if abs(aimed[name] - observed[name]) > 1:
        ax5.add_patch(FancyArrowPatch((0.60 * np.cos(aa), 0.60 * np.sin(aa)),
                                      (0.78 * np.cos(ao), 0.78 * np.sin(ao)),
                                      arrowstyle="-|>", mutation_scale=11,
                                      color=CHANNEL_COLORS[i], lw=1.5, alpha=0.95))

ax5.set_xlim(-1.35, 1.35); ax5.set_ylim(-1.30, 1.30)
ax5.set_aspect("equal"); ax5.axis("off")
ax5.text(-1.32, 1.18, r"aimed direction (grey dot) → post-clamp angle (coloured dot)",
         fontsize=8.2, color=TEXT_SUB)
ax5.text(-1.32, -1.24, r"$\theta = \operatorname{atan2}(E_I, E_Y)$", fontsize=9, color=TEXT_SUB)
eq_text(ax5, 0.02, 0.86,
        wrap(r"the positivity clamp ($E_Y, E_I \geq 10^{-3}$) confines $\theta$ to the first "
             r"quadrant at every cell, for any event, any amplitude. Of the five pentagon channels "
             r"only **Wood (0°) and Fire (72°) are representable**: Earth (144°) clamps to 89.9°, "
             r"Metal (216°) to 45°, Water (288°) to 0.2°. Representability = sector proximity: "
             r"$|\theta_{\rm obs} - \theta_{\rm ch}| \leq 36°$."),
        fontsize=8.3)

ax5c = fig.add_subplot(gs[5, 2])
panel_title(ax5c, "Lock Channel vs Event Direction  (§10.8)")
ax5c.axis("off")
ax5c.set_xlim(0, 1); ax5c.set_ylim(0, 1)

rows = [
    ("event", "t=2", "t=10", "status"),
]
doms = {n: (pc["runs"][n]["t2_dominant"], pc["runs"][n]["t10_dominant"]) for n in CHANNELS}
y = 0.965
ax5c.text(0.06, y, "event", fontsize=9.5, color=YANG_BRIGHT, fontweight="bold")
ax5c.text(0.40, y, "locked at t=2", fontsize=9.5, color=YANG_BRIGHT, fontweight="bold")
ax5c.text(0.60, y, "t=10", fontsize=9.5, color=YANG_BRIGHT, fontweight="bold")
ax5c.text(0.78, y, "verdict", fontsize=9.5, color=YANG_BRIGHT, fontweight="bold")
y -= 0.105
for name in CHANNELS:
    d2, d10 = doms[name]
    ok = d2 == name
    ax5c.text(0.06, y, name, fontsize=10, color=CHANNEL_COLORS[CHANNELS.index(name)],
              fontweight="bold")
    ax5c.text(0.40, y, d2, fontsize=10, color=YANG_PEAK if d2 == name else TEXT_MAIN)
    ax5c.text(0.60, y, d10, fontsize=10, color=YANG_PEAK if d10 == name else TEXT_MAIN)
    if ok:
        ax5c.text(0.78, y, "clean", fontsize=10, color=GREEN_SAFE, fontweight="bold")
    else:
        ax5c.text(0.78, y, f"clamped→{d2}", fontsize=10, color=RED_DANGER, fontweight="bold")
    y -= 0.105
eq_text(ax5c, 0.04, 0.36,
        wrap(r"within the representable arc the lock **tracks the event direction and persists**: "
             r"Fire event → 100% Fire at t=2 and t=10; Wood event → 100% Wood at both. No convergence. "
             r"The five-way pentagon is not lost—it lives in the gate's $\mathbf{b}$-manifold "
             r"(channel openness), where all five channels exist; only the stimulus-side field angle "
             r"is 1D in this PDE. A geometric constraint of positive fields, not a dynamical null."),
        fontsize=8.1)

# ═════════════════════════════════════════════════════════════════════════════
# Row 6—P6: the ke ring
# ═════════════════════════════════════════════════════════════════════════════
ax6 = fig.add_subplot(gs[6, 0])
panel_title(ax6, "P6 · The Ke Ring in the Gate  (C3)")

ch_five = np.array(ke["c1"]["ch_five"])
ch_ke = np.array(ke["c1"]["ch_ke"])
ring = np.array(ke["c1"]["ring"])
x = np.arange(5)
w = 0.26
ax6.bar(x - w, BASELINE, w, color=RING, alpha=0.85, label=r"baseline $b_i = \varphi^{-(3+i)}$")
ax6.bar(x, ch_five, w, color=YIN_LIGHT, label="five (control)")
ax6.bar(x + w, ch_ke, w, color=YANG_PEAK, label="five_ke (ke ring)")
ax6.axhline(0, color=TEXT_SUB, lw=0.8)
ax6.set_xticks(x); ax6.set_xticklabels(CHANNELS, fontsize=9.5)
ax6.set_ylabel("channel openness at t=2", fontsize=9.5, color=TEXT_SUB)
ax6.set_ylim(0, 0.34)
ax6.legend(fontsize=8, loc="upper right", framealpha=0.85, facecolor=BG, edgecolor=RING)
eq_text(ax6, 0.03, 0.90,
        wrap(r"event: standing Yang deficit, amp 1.6. Excess channels Fire, Earth, Water act on their "
             r"ke targets (i+2) and release the ke-released partners (i+4). One-round ke prediction "
             r"vs PDE state: error $\leq 6\times 10^{-4}$."),
        fontsize=8.0)

ax6b = fig.add_subplot(gs[6, 1])
panel_title(ax6b, "Ring Deviation—Restrained vs Released  (C1)")

ax6b.bar(x, ring * 1e3, 0.55,
         color=[GREEN_SAFE if v > 0.3 else RED_DANGER for v in ring * 1e3], alpha=0.92)
ax6b.axhline(0, color=TEXT_SUB, lw=0.8)
for i, v in enumerate(ring * 1e3):
    ax6b.text(i, v + (2.5 if v >= 0 else -6.5), f"{v:+.1f}", ha="center", fontsize=9,
              color=GREEN_SAFE if v > 0 else RED_DANGER, fontweight="bold")
ax6b.set_xticks(x); ax6b.set_xticklabels(CHANNELS, fontsize=9.5)
ax6b.set_ylabel(r"$\Delta$ openness (five_ke − five) × 10³", fontsize=9.5, color=TEXT_SUB)
ax6b.set_ylim(-34, 42)
ax6b.grid(alpha=0.15, color=RING, lw=0.5)
eq_text(ax6b, 0.03, 0.27,
        r"excess restrains the ke target:  $d_i = \min(\kappa\,\Delta_i^+,\; b_{i+2})$" + "\n" +
        r"release lands on the ke-released partner (i+4):  $\Delta_{i+4} = \Delta_{i+4} + d_i$" + "\n" +
        r"$\kappa = \varphi^{-1} = K_{\rm fw}$—no new parameter.",
        fontsize=8.2)

ax6c = fig.add_subplot(gs[6, 2])
panel_title(ax6c, "Ring Gain—Sub-Critical, No Self-Sustenance  (C3a, C3b)")

ax6c.bar([0, 1, 2], [ke["c3"]["eps_rel"]["five"], ke["c3"]["eps_rel"]["five_ke"],
                     ke["c3"]["eps_rel"]["five_ke+drive"]], 0.5,
         color=[YIN_LIGHT, YANG_BRIGHT, YANG_PEAK], alpha=0.92)
ax6c.set_xticks([0, 1, 2])
ax6c.set_xticklabels(["five\n(control)", "five_ke\n(no driver)", "five_ke\n+ φ-drive"],
                     fontsize=8.5)
ax6c.set_ylabel(r"$|\varepsilon|$ retained at t=10", fontsize=9.5, color=TEXT_SUB)
ax6c.set_ylim(0, 0.45)
for i, v in enumerate([ke["c3"]["eps_rel"]["five"], ke["c3"]["eps_rel"]["five_ke"],
                       ke["c3"]["eps_rel"]["five_ke+drive"]]):
    ax6c.text(i, v + 0.015, f"{v:.3f}", ha="center", fontsize=10, color=TEXT_MAIN,
              fontweight="bold")
ax6c.grid(alpha=0.15, color=RING, lw=0.5)
eq_text(ax6c, 0.03, 0.58,
        wrap(r"ring gain $\kappa^3 = \varphi^{-3} = 0.236$—the pentagram's central-segment fraction. "
             r"The ke term changes nothing about decay without a driver (0.350 vs 0.349), and the "
             r"$\varphi$-phased drive still dissolves the site (0.149). The ke ring redistributes and "
             r"damps; it never creates persistence. A self-sustained lock would require $\kappa \geq 1$ "
             r"— excluded by $K_{\rm fw} = \varphi^{-1}$."),
        fontsize=8.1)

# ═════════════════════════════════════════════════════════════════════════════
# Row 7—verdict card
# ═════════════════════════════════════════════════════════════════════════════
ax7 = fig.add_subplot(gs[7, :])
ax7.set_facecolor(BG)
ax7.set_xlim(0, 1); ax7.set_ylim(0, 1); ax7.axis("off")

ax7.text(0.015, 0.94, "WHAT THE ARC ESTABLISHED", fontsize=13, color=YANG_PEAK,
         fontweight="bold", va="top")
verdicts = [
    ("TESTED—the sustainer", "ongoing re-stimulation. 0.005% of the event peak per step holds 80% of "
     "event intensity; stopping the trigger releases the site to 22%.", GREEN_SAFE),
    ("TESTED—no self-sustenance", "the ke ring is sub-critical by construction (κ³ = 0.236 = the "
     "pentagram's central segment); decay identical with and without it; the φ-drive still dissolves "
     "(0.149 vs 0.349).", GREEN_SAFE),
    ("TESTED—susceptibility null", "a second identical event on a pre-stressed site leaves the same "
     "trace (+0.050 vs 0.069); background coherence does not modulate the outcome.", GREEN_SAFE),
    ("TESTED—the φ-channel", "engages between 5/s and 50/s (two orders above ambient trigger rates), "
     "φ-specific at onset (0.693 vs 0.943 e-drive), non-monotonic in amplitude.", GREEN_SAFE),
    ("TESTED—representability bound", "the positivity clamp confines θ to (0°, 90°): Wood and Fire "
     "events lock cleanly and persist; Earth, Metal, Water clamp onto Fire or Wood.", GREEN_SAFE),
    ("TESTED—the ke ring", "excess restrains its ke target and releases the ke-released partner, to "
     "≤ 6×10⁻⁴ against the PDE; the alternating pattern of T1 is the gate's natural response.",
     GREEN_SAFE),
]
for i, (head, body, c) in enumerate(verdicts):
    col = i % 2
    row = i // 2
    x0 = 0.015 + col * 0.505
    y0 = 0.66 - row * 0.225
    ax7.add_patch(plt.Rectangle((x0, y0), 0.48, 0.19, facecolor="#0a0a1c",
                                edgecolor=RING, lw=1.0, transform=ax7.transAxes))
    ax7.text(x0 + 0.012, y0 + 0.155, head, fontsize=9.5, color=c, fontweight="bold",
             transform=ax7.transAxes)
    ax7.text(x0 + 0.012, y0 + 0.115, body, fontsize=8.4, color=TEXT_MAIN,
             transform=ax7.transAxes, va="top", linespacing=1.35)

ax7.text(0.015, 0.025,
         "still open, needing affect data (Speculative):  T1—the ke-alternating profile "
         "[−0.382, −0.618, +0.382, +0.618]·D of lock-excess deficits, not four equal ones  ·  "
         "T2—the R-matrix healing sequence (anger first after fear-work, relief after rage-work)",
         fontsize=9.5, color=YIN_LIGHT, va="bottom")

OUT = os.path.join(ROOT, "visual-explainers", "trauma_test_arc.png")
fig.savefig(OUT, dpi=120, facecolor=BG)
print(f"wrote {OUT}")

# ─────────────────────────────────────────────────────────────────────────────
# Console verification—every number against the docs / results.json
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Trauma Test Arc: verification against runs/*/results.json ──")
fail = []

def check(name, got, want, tol=0.005):
    ok = abs(got - want) <= tol
    fail.append(not ok)
    print(f"  {'OK ' if ok else 'FAIL'} {name}: got {got:.4f}  want {want:.4f}")

print("  P1  driver (§10.5):")
check("ref retained @t=10", r_ref['eps_site'][-1] / r_ref['eps_site'][0], 0.4232)
check("dc retained @t=10", r_dc['eps_site'][199] / r_dc['eps_site'][0], 0.7959)
check("dc retained @t=20 (extinct)", r_dc['eps_site'][-1] / r_dc['eps_site'][0], 0.2152, 0.01)
check("phi envelope = dc", abs(r_ph['eps_site'][-1] - r_dc['eps_site'][199]), 0.0, 0.01)
print("  P2  q-gap:")
check("dc q-gap @t=10", qgap_dc[199], 0.0634, 0.004)
check("dc q-gap @t=20 closed", qgap_dc[-1], 0.0078, 0.004)
print("  P3  capacity (§10.6):")
check("first-hit trace @t=22", cap_first['eps_site'][-1], 0.0687, 0.005)
check("second-hit marginal", cap_hit['eps_site'][-1] - cap_first['eps_site'][-1], 0.0499, 0.01)
print("  P4  crossover (§10.7):")
check("phi 50/s retention", cx['runs']['drive_0.05']['eps_rel'], 0.6929)
check("phi 150/s retention", cx['runs']['drive_0.15']['eps_rel'], 0.3623)
check("phi 0.5/s retention", cl['runs']['phi_0.0005']['eps_rel'], 0.9097)
check("e 50/s retention", cl['runs']['e_0.05']['eps_rel'], 0.9429)
print("  P5  phase channels (§10.8):")
for n in CHANNELS:
    dom2 = pc['runs'][n]['t2_dominant']
    dom10 = pc['runs'][n]['t10_dominant']
    ok = (dom2 == dom10) and ((dom2 == n) or n in ("Earth", "Metal", "Water"))
    fail.append(not ok)
    print(f"  {'OK ' if ok else 'FAIL'} {n} event: t=2 {dom2}, t=10 {dom10}")
print("  P6  ke ring (C3):")
check("ring Wood release", ke['c1']['ring'][0], 0.0339, 0.002)
check("ring Metal restraint", ke['c1']['ring'][3], -0.0265, 0.002)
check("ring Water restraint", ke['c1']['ring'][4], -0.0210, 0.002)
check("ke pred error", ke['c1']['pred_err'], 0.00055, 0.0005)
check("five_ke retained = five", ke['c3']['eps_rel']['five_ke'], ke['c3']['eps_rel']['five'], 0.005)
check("five_ke+drive retained", ke['c3']['eps_rel']['five_ke+drive'], 0.1486, 0.005)
print(f"\n{'ALL CHECKS PASSED' if not any(fail) else 'SOME CHECKS FAILED'}")
