#!/usr/bin/env python3
"""
Coherence Transmission: cascade-span analysis of sustained multi-rung injection
==============================================================================

When a φ-spaced device injects coherent perturbations spanning K cascade rungs,
how much coherence survives as we descend through the normal cascade, across the
Planck barrier, and into the microcascade?

This script applies the cascade-suppression formula (Derived) and the
microcascade q_n ansatz (Speculative — see microcascade-mirror.md §3.2) to
compute the per-rung transmission landscape and answer: is coherence easier to
sustain at sub-Planckian scales?

Run:  python visual-explainers/coherence_transmission.py
Out:  visual-explainers/coherence_transmission.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
DELTA = 3                     # σ = ℓ_Pl / φ³
N_CASCADE = 292               # total cascade rungs
N_MICRO = 292                 # symmetric extension into microcascade

# House palette
YIN_DEEP, YIN_MID, YIN_LIGHT = "#140a33", "#2a1a5e", "#4a2a8e"
YANG_DARK, YANG_MID, YANG_BRIGHT, YANG_PEAK = "#5a3a10", "#9a6a1a", "#daa520", "#ffe060"
BG, TEXT_MAIN, TEXT_SUB, RING = "#060612", "#e0e0f0", "#a0a0c0", "#303050"
GREEN_SAFE, YELLOW_CAUTION, RED_DANGER = "#2ecc71", "#f1c40f", "#e74c3c"
PLANCK_LINE = "#ff6b6b"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT_MAIN, "axes.edgecolor": RING,
    "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
    "font.family": "DejaVu Sans", "mathtext.default": "regular",
})

# ─────────────────────────────────────────────────────────────────────────────
# Cascade rung arrays
# ─────────────────────────────────────────────────────────────────────────────
n_pos = np.arange(0, N_CASCADE + 1)          # 0..292
n_neg = np.arange(-N_MICRO, 0)               # -292..-1
n_full = np.arange(-N_MICRO, N_CASCADE + 1)   # -292..292

# ─────────────────────────────────────────────────────────────────────────────
# Qi profile q_n
# ─────────────────────────────────────────────────────────────────────────────
# Derived for n ≥ 0
q_pos = 1.0 - PHI ** (-n_pos.astype(float) - DELTA)
q_pos = np.clip(q_pos, 0.0, 1.0)

# Ansatz for n < 0 (microcascade-mirror.md §3.2 — SPECULATIVE)
abs_n_neg = np.abs(n_neg).astype(float)
q_neg_ansatz = PHI ** (-abs_n_neg - DELTA) / (1.0 + PHI ** (-abs_n_neg - DELTA))

# Stitch full profile
q_full = np.concatenate([q_neg_ansatz, q_pos])
gate_full = 1.0 - q_full   # (1 - q_n) = per-rung coherence openness

# ─────────────────────────────────────────────────────────────────────────────
# Per-rung transmission: two regimes (cascade-suppression-formula.md §1–2)
# ─────────────────────────────────────────────────────────────────────────────
# Signal regime: d_i^(signal) ≈ φ^{-1} for i ≥ 1 (uniform per-rung damping)
# For i = 0: d_0^(signal) = φ^{-0-δ} + φ^{-1} = φ^{-3} + φ^{-1}
d_signal_pos = np.full_like(n_pos, 1.0 / PHI, dtype=float)
d_signal_pos[0] = PHI ** (-DELTA) + 1.0 / PHI   # Planck rung exact

# For n < 0: same φ^{-1} ansatz (signal passes through microcascade similarly)
d_signal_neg = np.full_like(n_neg, 1.0 / PHI, dtype=float)
# But: microcascade has (1-q_n) → 1, meaning the medium is more transparent.
# A proper treatment would use the microcascade PDE — not available.
# We show BOTH assumptions (uniform φ^{-1} vs improved by 1-q_n) on the plot.

# Coherence regime: d_i^(coherence) = (1 - q_i)  (position-dependent)
d_coherence_pos = gate_full[N_MICRO:]   # n ≥ 0
d_coherence_neg = gate_full[:N_MICRO]   # n < 0

# Cumulative transmission: product of per-rung factors from injection rung down
# to target rung. For signal regime, cumulative from rung k to Planck (n=0):
#   T_signal(k→0) = ∏_{i=0}^{k} d_i^(signal) ≈ φ^{-k} (for k ≥ 1)
# For coherence regime, cumulative from Planck to rung k:
#   T_coherence(0→k) = ∏_{i=0}^{k} (1-q_i) = φ^{-k(k+1)/2 - δ(k+1)}

# Compute cumulative transmission: from a given starting rung down through Planck
# into microcascade. We go DOWNWARD (decreasing n).
# Path: injection rung → Planck (n=0) → microcascade target

# For signal regime: per-rung = φ^{-1}, cumulative across N rungs = φ^{-N}
# For each injection rung n_inj ≥ 0, the path to Planck has n_inj rungs
cum_signal_pos_to_planck = np.ones(N_CASCADE + 1)
for k in range(1, N_CASCADE + 1):
    cum_signal_pos_to_planck[k] = cum_signal_pos_to_planck[k - 1] / PHI

# For the microcascade path: from Planck (n=0) down to n < 0
# Signal regime: φ^{-|n|} per step. Microcascade nodes have an effective
# per-rung factor. With microcascade ansatz, (1-q_n) → 1, so d_n → 1
# (no attenuation). But signal damping φ^{-1} applies if medium is same.
# We plot BOTH assumptions.
cum_signal_micro_uniform = np.ones(N_MICRO)
for d in range(1, N_MICRO):
    cum_signal_micro_uniform[d] = cum_signal_micro_uniform[d - 1] / PHI

cum_signal_micro_improved = np.ones(N_MICRO)
for d in range(1, N_MICRO):
    # per-rung factor = max(1-q_n, φ^{-1}) — microcascade enforces φ^{-1} floor
    improved_d = max(gate_full[N_MICRO - 1 - d], 1.0 / PHI)
    cum_signal_micro_improved[d] = cum_signal_micro_improved[d - 1] * improved_d

# Planck barrier: the single-step transmission at n=0
planck_barrier = gate_full[N_MICRO]  # (1-q_0) = φ^{-3} ≈ 0.236

# ─────────────────────────────────────────────────────────────────────────────
# Key cascade rungs for annotation
# ─────────────────────────────────────────────────────────────────────────────
LANDMARKS = {
    0:   ("Planck", PLANCK_LINE, -0.5),
    80:  ("Electroweak", YANG_MID, -0.5),
    95:  ("QCD", YANG_MID, -0.5),
    117: ("Atomic (Bohr)", YANG_DARK, -0.5),
    285: ("Wu Xing bubble", YANG_BRIGHT, 0.5),
    292: ("Hubble", YANG_PEAK, 0.5),
}

MICRO_LANDMARKS = {
    -1:  ("φ⁻¹ ℓ_Pl", YIN_LIGHT, 0.5),
    -5:  ("φ⁻⁵ ℓ_Pl", YIN_LIGHT, -0.5),
    -10: ("φ⁻¹⁰ ℓ_Pl", YIN_MID, 0.5),
}

# ─────────────────────────────────────────────────────────────────────────────
# Figure
# ─────────────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 11), dpi=160, facecolor=BG)

# ── Panel A: Qi profile q(n) ────────────────────────────────────────────────
axA = fig.add_axes([0.06, 0.58, 0.40, 0.36])
axA.set_facecolor(BG)

# Shade regimes
axA.axvspan(-N_MICRO, -1, alpha=0.08, color=YIN_MID, zorder=0)
axA.axvspan(0, N_CASCADE, alpha=0.05, color=YANG_MID, zorder=0)
axA.axvspan(N_CASCADE - 7, N_CASCADE, alpha=0.08, color=YANG_PEAK, zorder=0)

# Plot q(n)
axA.plot(n_neg, q_neg_ansatz, color=YIN_LIGHT, lw=1.5, ls="--",
         label=r"$q_n$ (microcascade ansatz — Speculative)")
axA.plot(n_pos, q_pos, color=YANG_BRIGHT, lw=2.0,
         label=r"$q_n = 1 - \varphi^{-n-3}$ (Derived)")

# Planck barrier
axA.axvline(x=0, color=PLANCK_LINE, lw=1.5, ls=":", alpha=0.8)
axA.text(0.5, 0.92, "Planck\nbarrier", transform=axA.transAxes,
         fontsize=8, color=PLANCK_LINE, ha="center", va="top")

# Landmarks
q_full_idx = n_full.tolist()
for n_val, (label, color, yoff) in LANDMARKS.items():
    idx = q_full_idx.index(n_val)
    qv = q_full[idx]
    axA.axvline(x=n_val, color=color, lw=0.7, ls=":", alpha=0.5)
    axA.annotate(label, xy=(n_val, qv), xytext=(n_val + yoff * 30, qv + 0.08),
                 fontsize=7, color=color, ha="center",
                 arrowprops=dict(arrowstyle="->", color=color, lw=0.7))

for n_val, (label, color, yoff) in MICRO_LANDMARKS.items():
    idx = n_full.tolist().index(n_val)
    qv = q_full[idx]
    axA.annotate(label, xy=(n_val, qv), xytext=(n_val + yoff * 25, qv - 0.1),
                 fontsize=7, color=color, ha="center",
                 arrowprops=dict(arrowstyle="->", color=color, lw=0.7))

axA.set_xlabel("cascade rung $n$", fontsize=10, color=TEXT_SUB)
axA.set_ylabel("Qi coherence $q_n$", fontsize=10, color=TEXT_SUB)
axA.set_xlim(-N_MICRO, N_CASCADE)
axA.set_ylim(-0.02, 1.08)
axA.legend(fontsize=7.5, loc="lower right", framealpha=0.85,
           facecolor=BG, edgecolor=RING)
axA.set_title("A. Qi Coherence Across the Full Cascade ($-$292 to +292)",
              fontsize=12, color=YANG_PEAK, fontweight="bold", pad=10)
# Regime labels
axA.text(-200, 1.02, "MICROCASCADE\n($n<0$, Speculative)", fontsize=8,
         color=YIN_LIGHT, ha="center", fontstyle="italic")
axA.text(100, 1.02, "CASCADE ($0$–$292$, Derived)", fontsize=8,
         color=YANG_BRIGHT, ha="center", fontstyle="italic")
axA.text(285, 1.02, "MEGA", fontsize=7,
         color=YANG_PEAK, ha="center", fontstyle="italic")

# ── Panel B: Per-rung transmission (1 − q_n) ────────────────────────────────
axB = fig.add_axes([0.06, 0.10, 0.40, 0.36])
axB.set_facecolor(BG)

# Threshold zones
axB.axhspan(0.5, 1.0, alpha=0.08, color=GREEN_SAFE, zorder=0)
axB.axhspan(0.1, 0.5, alpha=0.06, color=YELLOW_CAUTION, zorder=0)
axB.axhspan(0.0, 0.1, alpha=0.05, color=RED_DANGER, zorder=0)

axB.text(0.99, 0.92, "EASY: $(1-q_n) > 0.5$\nhigh transmission", transform=axB.transAxes,
         fontsize=7, color=GREEN_SAFE, ha="right", va="top")
axB.text(0.99, 0.65, "MODERATE: $0.1 < (1-q_n) < 0.5$", transform=axB.transAxes,
         fontsize=7, color=YELLOW_CAUTION, ha="right", va="top")
axB.text(0.99, 0.35, "HARD: $(1-q_n) < 0.1$\nPlanck barrier floor", transform=axB.transAxes,
         fontsize=7, color=RED_DANGER, ha="right", va="top")

# Plot (1-q_n)
axB.plot(n_neg, gate_full[:N_MICRO], color=YIN_LIGHT, lw=1.8, ls="--",
         label=r"$(1-q_n)$ — microcascade ansatz (Speculative)")
axB.plot(n_pos, gate_full[N_MICRO:], color=YANG_BRIGHT, lw=2.0,
         label=r"$(1-q_n) = \varphi^{-n-\delta}$ — cascade (Derived)")

# Signal-propagation line for comparison
axB.axhline(y=1.0/PHI, color=TEXT_SUB, lw=1.0, ls=":", alpha=0.6)
axB.text(0.01, 1.0/PHI + 0.01, r"$\varphi^{-1} \approx 0.618$ (signal regime floor)",
         transform=axB.get_yaxis_transform(), fontsize=7, color=TEXT_SUB, va="bottom")

# Planck barrier
axB.axvline(x=0, color=PLANCK_LINE, lw=1.5, ls=":", alpha=0.8)
axB.plot([0], [gate_full[N_MICRO]], "o", color=PLANCK_LINE, ms=8, zorder=5)
planck_val = gate_full[N_MICRO]
axB.annotate(f"Planck barrier\n$(1-q_0) = \\varphi^{{-3}}$\n$= {planck_val:.3f}$",
             xy=(0, planck_val), xytext=(-60, 0.45),
             fontsize=7.5, color=PLANCK_LINE, ha="center",
             arrowprops=dict(arrowstyle="->", color=PLANCK_LINE, lw=1.2))

# Arrow showing microcascade → 1
axB.annotate(r"$(1-q_n) \to 1$ as $n \to -\infty$" + "\n(perfect transmission at depth)",
             xy=(-250, gate_full[42]), xytext=(-150, 0.82),
             fontsize=8, color=GREEN_SAFE, ha="center", fontweight="bold",
             arrowprops=dict(arrowstyle="->", color=GREEN_SAFE, lw=1.5))

# Arrow showing cascade decay
axB.annotate(r"$(1-q_n) \to 0$ as $n \to \infty$" + "\n(Qi saturation closes gate)",
             xy=(200, gate_full[N_MICRO + 200]), xytext=(150, 0.30),
             fontsize=8, color=RED_DANGER, ha="center",
             arrowprops=dict(arrowstyle="->", color=RED_DANGER, lw=1.5))

axB.set_xlabel("cascade rung $n$", fontsize=10, color=TEXT_SUB)
axB.set_ylabel(r"per-rung transmission $(1-q_n)$", fontsize=10, color=TEXT_SUB)
axB.set_xlim(-N_MICRO, N_CASCADE)
axB.set_ylim(-0.02, 1.08)
axB.legend(fontsize=7.5, loc="upper left", framealpha=0.85,
           facecolor=BG, edgecolor=RING)
axB.set_title("B. Per-Rung Coherence Transmission $(1-q_n)$",
              fontsize=12, color=YANG_PEAK, fontweight="bold", pad=10)

# ── Panel C: Cumulative transmission ────────────────────────────────────────
axC = fig.add_axes([0.52, 0.10, 0.44, 0.36])
axC.set_facecolor(BG)

# X-axis: cascade rung n from -60 to selected device rungs
# Y-axis: cumulative transmission T(n) = product of per-rung factors down to n
# Starting from different injection rungs.

# Path: device injects at n_inj, we compute cumulative transmission
# down through cascade to Planck, across Planck barrier, into microcascade.
# For the signal regime (device to Planck): φ^{-(n_inj - n)}
# For n < 0 in microcascade: multiply by microcascade ansatz factors

injection_rungs = [5, 20, 80, 117, 285]
colors_inj = [YIN_LIGHT, YIN_MID, YANG_MID, YANG_BRIGHT, YANG_PEAK]
labels_inj = ["n=5 (GUT-ish)", "n=20 (seesaw)", "n=80 (EW)",
              "n=117 (atomic)", "n=285 (bubble)"]

n_display = np.arange(-60, 293)

for n_inj, color, label in zip(injection_rungs, colors_inj, labels_inj):
    T = np.zeros(len(n_display))
    # From injection rung downward
    for j, n_targ in enumerate(n_display):
        if n_targ > n_inj:
            T[j] = np.nan   # can't transmit upward
        elif n_targ >= 0:
            # Signal regime from n_inj to n_targ within normal cascade
            span = n_inj - n_targ
            T[j] = PHI ** (-span) if span >= 0 else np.nan
        else:
            # n_targ < 0: go to Planck first, then into microcascade
            span_to_planck = n_inj  # from n_inj to 0
            T_planck = PHI ** (-span_to_planck) * planck_barrier
            # microcascade path: from 0 down to n_targ (negative)
            mc_depth = abs(n_targ)
            if mc_depth < N_MICRO:
                T_micro = cum_signal_micro_improved[mc_depth]
            else:
                T_micro = 0.0
            T[j] = T_planck * T_micro

    # Mask NaNs for plotting
    mask = ~np.isnan(T)
    axC.semilogy(n_display[mask], T[mask], color=color, lw=1.8,
                 alpha=0.85, label=f"inject at {label}")

# Planck barrier
axC.axvline(x=0, color=PLANCK_LINE, lw=1.5, ls=":", alpha=0.8)

# Horizontal line: 10^{-3} (practical detectability floor)
axC.axhline(y=1e-3, color=TEXT_SUB, lw=0.8, ls="--", alpha=0.4)
axC.text(0.98, 0.08, r"$10^{-3}$ (arbitrary\ndetectability floor)",
         transform=axC.transAxes, fontsize=7, color=TEXT_SUB, ha="right", va="bottom")

# Shade regimes
axC.axvspan(-60, -1, alpha=0.08, color=YIN_MID, zorder=0)
axC.axvspan(0, 292, alpha=0.04, color=YANG_MID, zorder=0)

axC.set_xlabel("target cascade rung $n_{\\rm target}$", fontsize=10, color=TEXT_SUB)
axC.set_ylabel("cumulative coherence transmission $T$", fontsize=10, color=TEXT_SUB)
axC.set_xlim(-60, 292)
axC.set_ylim(1e-60, 2)
axC.legend(fontsize=7, loc="lower left", framealpha=0.85, facecolor=BG, edgecolor=RING)
axC.set_title("C. Cumulative Transmission: Injection Rung → Microcascade Depth",
              fontsize=12, color=YANG_PEAK, fontweight="bold", pad=10)
axC.text(0.5, 0.94, "signal-propagation regime: $d_i \\approx \\varphi^{-1}$ per rung" +
         "  ·  Planck barrier $\\varphi^{-3}$  ·  microcascade path: $(1-q_n)$ ansatz",
         transform=axC.transAxes, fontsize=8, color=TEXT_SUB, ha="center")

# ── Panel D: Key findings table ─────────────────────────────────────────────
axD = fig.add_axes([0.52, 0.58, 0.44, 0.36])
axD.set_facecolor(BG)
axD.set_xlim(0, 1); axD.set_ylim(0, 1)
axD.axis("off")

findings_text = [
    ("KEY FINDINGS", YANG_PEAK, 14, "bold"),
    ("", TEXT_SUB, 8, "normal"),
    (r"CASCADE ($n \geq 0$) — Derived from cascade-suppression formula", YANG_BRIGHT, 10, "bold"),
    (r"  $(1-q_n) = \varphi^{-n-3}$ decays as $n$ grows", TEXT_MAIN, 9, "normal"),
    (r"  Qi saturates ($q \to 1$) at large scales → coherence gate closes", TEXT_MAIN, 9, "normal"),
    (r"  Single-rung signal from EW ($n{=}80$) to Planck: $\varphi^{-80} \approx 10^{-17}$", YELLOW_CAUTION, 9, "normal"),
    (r"  Full coherence from Planck to EW: $\varphi^{-80\cdot81/2} \approx 10^{-675}$ — impossible", RED_DANGER, 9, "normal"),
    ("", TEXT_SUB, 8, "normal"),
    (r"MICROCASCADE ($n < 0$) — Ansatz (Speculative, microcascade-mirror.md §3.2)", YIN_LIGHT, 10, "bold"),
    (r"  $(1-q_n) \to 1$ as $n \to -\infty$ — per-rung transmission approaches 100%", GREEN_SAFE, 9, "normal"),
    (r"  Deep microcascade is the EASIEST regime for coherence transport", GREEN_SAFE, 9, "normal"),
    (r"  Planck barrier $(1-q_0) = \varphi^{-3} \approx 0.236$ — 24% step loss", PLANCK_LINE, 9, "normal"),
    (r"  Microcascade energy sum diverges ($E_{\rm micro} \to \infty$ formally)", YIN_LIGHT, 9, "normal"),
    ("", TEXT_SUB, 8, "normal"),
    (r"MULTI-RUNG INJECTION — Hypothesized mechanism", YANG_BRIGHT, 10, "bold"),
    (r"  Phase-coherent φ-spaced injection across $K$ rungs sums amplitudes", TEXT_MAIN, 9, "normal"),
    (r"  Net: $T \approx K \cdot \varphi^{-n_{\rm device}} \cdot \varphi^{-3}$ (Planck) $\cdot$ (microcascade)", TEXT_MAIN, 9, "normal"),
    (r"  Signal regime (not coherence regime) applies between injection rungs", TEXT_MAIN, 9, "normal"),
    (r"  Each injected rung independently couples to the rung below it", TEXT_MAIN, 9, "normal"),
    ("", TEXT_SUB, 8, "normal"),
    (r"IMPLICATION: The microcascade's infinite depth provides an unbounded", YANG_PEAK, 9.5, "bold"),
    (r"coherent reservoir, but coupling to it requires crossing the cascade", YANG_PEAK, 9.5, "bold"),
    (r"medium + Planck barrier. Deeper injection = exponentially harder.", YANG_PEAK, 9.5, "bold"),
    ("", TEXT_SUB, 8, "normal"),
    (r"Epistemic: Qi profile n≥0 = Derived; n<0 q_n = Speculative ansatz", TEXT_SUB, 7.5, "normal", "italic"),
    (r"Multi-rung injection mechanism = Hypothesized (not PDE-simulated)", TEXT_SUB, 7.5, "normal", "italic"),
]

y_pos = 0.96
for entry in findings_text:
    text, color, size, weight = entry[:4]
    style = entry[4] if len(entry) > 4 else "normal"
    axD.text(0.02, y_pos, text, transform=axD.transAxes,
             fontsize=size, color=color, fontweight=weight,
             fontstyle=style, va="top")

# ── Title ────────────────────────────────────────────────────────────────────
fig.suptitle("COHERENCE TRANSMISSION THROUGH THE FULL CASCADE",
             fontsize=18, fontweight="bold", color=YANG_PEAK, y=0.985)
fig.text(0.5, 0.975,
         r"$q_n = 1 - \varphi^{-n-\delta}$ (Derived, $n\geq 0$)   ·   "
         r"$q_n = \varphi^{-|n|-\delta} / (1 + \varphi^{-|n|-\delta})$ (Speculative ansatz, $n<0$)   ·   "
         r"$\delta=3$, $\sigma=\ell_{\rm Pl}/\varphi^3$",
         ha="center", fontsize=9, color=TEXT_SUB)

OUT = "visual-explainers/coherence_transmission.png"
fig.savefig(OUT, dpi=160, facecolor=BG)
print(f"wrote {OUT}")

# ─────────────────────────────────────────────────────────────────────────────
# Console verification
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Coherence Transmission Analysis ──")
print(f"  PHI                = {PHI:.12f}")
print(f"  DELTA              = {DELTA}")
print(f"  Planck q_0         = {q_pos[0]:.6f}  (Derived: 1 - φ^{-3})")
print(f"  Planck (1-q_0)     = {gate_full[N_MICRO]:.6f}  (barrier)")
print(f"  Signal per-rung    ≈ {1/PHI:.6f}  (φ^{-1})")
print(f"")

print("  ── Per-rung (1-q_n) at key rungs ──")
for n_val in [0, 1, 5, 10, 20, 50, 80, 95, 117, 200, 292]:
    idx = n_full.tolist().index(n_val)
    gv = gate_full[idx]
    regime = "Derived" if n_val >= 0 else "Speculative"
    print(f"  n = {n_val:>4d}:  (1-q_n) = {gv:.6f}  [{regime}]")

print(f"")
print("  ── Microcascade (Speculative ansatz) ──")
for n_val in [-1, -5, -10, -20, -50, -100, -200, -292]:
    idx = n_full.tolist().index(n_val)
    gv = gate_full[idx]
    print(f"  n = {n_val:>4d}:  (1-q_n) = {gv:.8f}  q_n = {q_full[idx]:.8f}")

print(f"")
print("  ── Cumulative transmission: injection → Planck → microcascade ──")
for n_inj in [5, 20, 80, 117]:
    for mc_depth in [0, 5, 20, 50]:
        T_planck = PHI ** (-n_inj) * planck_barrier
        T_micro = cum_signal_micro_improved[min(mc_depth, N_MICRO - 1)]
        T_total = T_planck * T_micro
        print(f"  inject n={n_inj:>3d}, to Planck, to mc depth {mc_depth:>3d}: "
              f"T_planck = {T_planck:.2e}, T_micro = {T_micro:.6f}, "
              f"T_total = {T_total:.2e}")

print(f"\n  ── Microcascade energy sum check (formal divergence) ──")
# Sum of (1-q_n) over n = -1 to -292
mc_energy_factors = gate_full[:N_MICRO]
mc_sum = np.sum(mc_energy_factors)
print(f"  Σ (1-q_n) for n=-1..-292 = {mc_sum:.2f}  (→ diverges as N→∞)")
print(f"  (1-q_n) → {gate_full[0]:.6f} at n=-292 (→ 1.0 as n→-∞)")
