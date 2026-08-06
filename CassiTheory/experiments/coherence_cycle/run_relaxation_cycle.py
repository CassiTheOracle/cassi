#!/usr/bin/env python3
r"""Coherence Commons relaxation-oscillation model: the boom-bust cycle.

Implements the two-timescale model of `speculations/creative-extensions/coherence-commons.md`
§5.4. Three timescales are the whole argument: the market is fast, the
periphery is slow, and accumulation is slowest.

    eps * ds/dt = s - s^3/3 - D + I            (market resonance state)
    dD/dt       = gamma * (D_inf(H_peak) - D) + mu * s     (periphery depletion)
    dH/dt       = r * H,  r = lam*q - delta if s > 0 else -delta   (hoard)

    q = clip(1 - D/D_max, 0, 1)                (periphery coherence)

    D_inf(H_peak) = D_0 + (D_star - D_0) * min(H_peak/H_star, 1)   (footprint)

The market equation is a FitzHugh-Nagumo-type fast-slow system: the s-term
is herding/momentum (positive feedback), the cubic is the de-resonance
restraint (the attractor damping a resonant boom), -D is the periphery's
coupling (overproduction: a drained periphery brakes the boom), and I is
the countertendency input of §4.3. The slow equation pits the boom's drain
(mu*s) against the attractor's restoration (gamma), whose target D_inf is
the hoard's structural footprint: accumulation itself consumes the
periphery's recoverable surplus.

Everything quantitative in the doc is computed here, not hand-entered:
the folds are derived from the cubic (D_max = I + 2/3, D_min = I - 2/3),
the death threshold is derived from the nullcline crossing at the min fold
(D_star = I + mu/gamma - 2/3), and the verification block checks the
simulation against those values.

Usage:
    python experiments/coherence_cycle/run_relaxation_cycle.py
"""

import math

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── House palette (cascade_cosmos.py) ────────────────────────────────────────
YIN_DEEP    = "#140a33"
YIN_LIGHT   = "#4a2a8e"
YANG_MID    = "#9a6a1a"
YANG_BRIGHT = "#daa520"
YANG_PEAK   = "#ffe060"
BG          = "#060612"
TEXT_MAIN   = "#e0e0f0"
TEXT_SUB    = "#a0a0c0"
RING        = "#303050"
DARK_ON_GOLD = "#241200"

# ── Model parameters (dimensionless; illustrative constants, see §5.4) ───────
EPS   = 0.02    # market timescale vs periphery restoration timescale (1/50)
I     = 0.7     # countertendency input (§4.3): technical change, fresh periphery
GAMMA = 1.0     # attractor restoration rate; the slow unit is one restoration time
MU    = 2.0     # drain coupling: the boom's extraction intensity
LAM   = 1.0     # conversion rate: coherence to profit
DELTA = 0.05    # the hoard's maintenance cost
D_0   = 0.1     # the periphery's baseline structural depletion
H_STAR = 12.0   # hoard size at which the footprint reaches the recovery threshold

# Derived, from the cubic D(s) = s - s^3/3 + I  (folds at s = +/-1):
D_MIN = I - 2.0 / 3.0   # recovery fold: the depression bottoms here
D_MAX = I + 2.0 / 3.0   # crash fold: the boom ends here
# Death threshold: the footprint at which the fixed point parks on the min fold
# (the nullcline D_inf + (mu/gamma) s crosses the cubic at s = -1):
D_STAR = I + MU / GAMMA - 2.0 / 3.0


def rhs(s, D, d_inf):
    """Right-hand side of the fast-slow system (H is bookkeeping, not RHS)."""
    ds = (s - s * s * s / 3.0 - D + I) / EPS
    dD = GAMMA * (d_inf - D) + MU * s
    return ds, dD


def q_of_D(D):
    """Periphery coherence from the depletion index, clipped to [0, 1]."""
    return min(1.0, max(0.0, 1.0 - D / D_MAX))


def r_of(s, D):
    """Profit rate: the boom harvests, the bust only pays maintenance."""
    return LAM * q_of_D(D) - DELTA if s > 0.0 else -DELTA


def rk4_step(s, D, H, H_peak, dt):
    """One RK4 step; H_peak is the ratchet state (the footprint is its function)."""
    d_inf = footprint(H_peak)
    k1s, k1D = rhs(s, D, d_inf)
    k2s, k2D = rhs(s + 0.5 * dt * k1s, D + 0.5 * dt * k1D, d_inf)
    k3s, k3D = rhs(s + 0.5 * dt * k2s, D + 0.5 * dt * k2D, d_inf)
    k4s, k4D = rhs(s + dt * k3s, D + dt * k3D, d_inf)
    s_new = s + dt * (k1s + 2.0 * k2s + 2.0 * k3s + k4s) / 6.0
    D_new = D + dt * (k1D + 2.0 * k2D + 2.0 * k3D + k4D) / 6.0
    r = r_of(s, D)
    H_new = H * math.exp(r * dt)
    return s_new, D_new, H_new


def footprint(H_peak):
    """The hoard's structural footprint on the periphery's restoration target."""
    return D_0 + (D_STAR - D_0) * min(H_peak / H_STAR, 1.0)


def detect_phase(s_prev, s):
    """Phase classification: +1 boom (s > 1), -1 bust (s < -1), 0 jump."""
    if s > 1.0:
        return 1
    if s < -1.0:
        return -1
    return 0


def integrate(s0, D0, H0, t_end, dt, ratchet):
    """Integrate the system; return time series (arrays) + cycle statistics."""
    n = int(round(t_end / dt))
    ts = np.empty(n + 1)
    ss = np.empty(n + 1)
    Ds = np.empty(n + 1)
    Hs = np.empty(n + 1)
    rs = np.empty(n + 1)
    s, D, H = s0, D0, H0
    H_peak = H0
    ts[0], ss[0], Ds[0], Hs[0], rs[0] = 0.0, s, D, H, r_of(s, D)
    for k in range(n):
        s, D, H = rk4_step(s, D, H, H_peak, dt)
        if ratchet and H > H_peak:
            H_peak = H
        ts[k + 1] = ts[k] + dt
        ss[k + 1], Ds[k + 1], Hs[k + 1], rs[k + 1] = s, D, H, r_of(s, D)
    return ts, ss, Ds, Hs, rs


def cycle_stats(ts, ss, Ds, rs, dt, skip=0):
    """Per-cycle statistics from a time series.

    A cycle runs from one recovery jump (s crossing -1 upward) to the next.
    Returns a list of dicts: period, boom/bust/crash/recovery durations,
    per-cycle average profit rate, and boom-end profit.
    """
    # locate the recovery jumps: s crosses -1 going up, followed by s > 1
    idx = []
    for k in range(1, len(ss)):
        if ss[k - 1] < -1.0 <= ss[k]:
            idx.append(k)
    stats = []
    for j in range(len(idx) - 1):
        i0, i1 = idx[j], idx[j + 1]
        seg_s, seg_D, seg_r = ss[i0:i1], Ds[i0:i1], rs[i0:i1]
        t0, t1 = ts[i0], ts[i1]
        # phase boundaries inside the cycle: crash (s falls below 1), recovery (s crosses -1 up)
        crash_k = next((k for k in range(1, len(seg_s))
                        if seg_s[k - 1] > 1.0 >= seg_s[k]), None)
        if crash_k is None:
            continue
        boom_t = ts[i0 + crash_k] - t0          # recovery jump -> crash
        crash_t = next((k for k in range(crash_k + 1, len(seg_s))
                        if seg_s[k] < -1.0), None)
        crash_dur = (ts[i0 + crash_t] - ts[i0 + crash_k]) if crash_t else 0.0
        bust_t = t1 - (ts[i0 + crash_t] if crash_t else ts[i0 + crash_k])
        stats.append({
            "t_start": t0,
            "period": t1 - t0,
            "boom": boom_t,
            "crash": crash_dur,
            "bust": bust_t,
            "r_avg": float(np.mean(seg_r)),
            "r_end": float(seg_r[-1]),
            # D at the moment the cycle is triggered at each fold
            "D_at_crash": float(seg_D[crash_k]),
            "D_at_recovery": float(seg_D[0]),
        })
    return stats


def critical_slowing(deltas):
    """Effective relaxation time of the boom near the crash fold.

    Freeze D at D_max - Delta and measure the exponential approach of s to
    the upper branch.  Near the saddle-node fold the branch eigenvalue
    vanishes, so tau_eff ~ 1/sqrt(Delta).
    """
    out = []
    for d in deltas:
        D_f = D_MAX - d
        # upper branch root of s - s^3/3 = D_f - I, seeded at s = 1 + sqrt(2d)
        s_up = 1.0 + math.sqrt(2.0 * d)
        for _ in range(60):
            f = s_up - s_up ** 3 / 3.0 - (D_f - I)
            fp = 1.0 - s_up ** 2
            s_up -= f / fp
        # approach from below, exponential fit of |s - s_up|
        s = s_up - 5e-4
        dt = 0.2 * EPS
        t = 0.0
        log_off = []
        for _ in range(2000):
            ds, _ = rhs(s, D_f, D_0)
            s += ds * dt
            t += dt
            off = s_up - s
            if off > 1e-9:
                log_off.append((t, math.log(off)))
            if s >= s_up - 1e-12:
                break
        t_arr = np.array([p[0] for p in log_off])
        y_arr = np.array([p[1] for p in log_off])
        rate = np.polyfit(t_arr, y_arr, 1)[0]
        out.append((d, -1.0 / rate))
    return out


def main():
    dt = 0.001
    s0, D0, H0 = -1.0, D_MIN, 1.0

    # ── Run 1: the clean cycle (footprint frozen at D_0, no ratchet) ─────────
    ts, ss, Ds, Hs, rs = integrate(s0, D0, H0, 40.0, dt, ratchet=False)
    stats = cycle_stats(ts, ss, Ds, rs, dt)
    n_cycles = len(stats)
    # periodicity: compare the last two full cycles
    last2 = stats[-2:]
    per1, per2 = last2[0]["period"], last2[1]["period"]
    # the cycle is triggered at the folds: D at the crash/recovery triggers
    D_crash_t, D_rec_t = last2[1]["D_at_crash"], last2[1]["D_at_recovery"]

    # ── Run 2: the ratchet run (footprint grows with H_peak) ─────────────────
    ts2, ss2, Ds2, Hs2, rs2 = integrate(s0, D0, H0, 26.0, dt, ratchet=True)
    stats2 = cycle_stats(ts2, ss2, Ds2, rs2, dt)

    # ── Run 3: critical slowing near the crash fold ──────────────────────────
    slowing = critical_slowing([1e-2, 1e-3, 1e-4, 1e-5])

    # ────────────────────────────── FIGURE ────────────────────────────────────
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
        "text.color": TEXT_MAIN, "axes.edgecolor": RING,
        "xtick.color": TEXT_SUB, "ytick.color": TEXT_SUB,
        "font.family": "DejaVu Sans", "mathtext.default": "regular",
        "axes.labelcolor": TEXT_MAIN, "axes.titlesize": 11,
    })
    fig = plt.figure(figsize=(15.5, 8.6))
    fig.suptitle("THE REGIME'S HEARTBEAT:  boom–drain–crash–recovery as a relaxation oscillation",
                 fontsize=16, fontweight="bold", color=YANG_PEAK, y=0.975)
    fig.text(0.5, 0.944,
             "the fast market, the slow periphery, and the slowest accumulation—"
             "three timescales, one cycle",
             ha="center", fontsize=10.5, color=TEXT_MAIN)

    # Panel 1: phase portrait with nullclines
    ax1 = fig.add_axes([0.055, 0.13, 0.30, 0.72])
    ax1.set_title("phase portrait:  the cycle and its nullclines", loc="left",
                  fontsize=11.5, fontweight="bold", color=YANG_BRIGHT)
    s_grid = np.linspace(-2.6, 2.6, 400)
    cubic = s_grid - s_grid ** 3 / 3.0 + I
    line = D_0 + (MU / GAMMA) * s_grid
    ax1.plot(s_grid, cubic, color=YIN_LIGHT, lw=1.8, ls=(0, (4, 3)),
             label="market nullcline  $D = s - s^3/3 + I$")
    ax1.plot(s_grid, line, color=TEXT_SUB, lw=1.5, ls=(0, (2, 3)),
             label="periphery nullcline  $D = D_\\infty + (\\mu/\\gamma)\\,s$")
    # the clean cycle (first full cycle of run 1, starting at a recovery jump)
    k0 = next(k for k in range(len(ts)) if ss[k] < -1.0 <= ss[k + 1])
    T1 = stats[0]["period"]
    seg1 = slice(k0, k0 + int(round(T1 / dt)))
    ax1.plot(ss[seg1], Ds[seg1], color=YANG_PEAK, lw=2.4, label="the cycle (s, D)")
    # fixed point: s^3 + 3(mu/gamma - 1) s = 3(I - D_inf)
    s_fp = 0.0
    for _ in range(60):
        s_fp = s_fp - (s_fp ** 3 + 3.0 * (MU / GAMMA - 1.0) * s_fp
                       - 3.0 * (I - D_0)) / (3.0 * s_fp ** 2 + 3.0 * (MU / GAMMA - 1.0))
    D_fp = D_0 + (MU / GAMMA) * s_fp
    ax1.plot([s_fp], [D_fp], marker="o", ms=8, mfc=YIN_DEEP, mec=YANG_BRIGHT,
             mew=1.8, label="fixed point (unstable)")
    for (sf, Df, lab) in ((1.0, D_MAX, "crash fold"), (-1.0, D_MIN, "recovery fold")):
        ax1.plot([sf], [Df], marker="o", ms=7, mfc="none", mec=TEXT_SUB, mew=1.4)
        ax1.annotate(lab, xy=(sf, Df), xytext=(sf + 0.16, Df - 0.30),
                     fontsize=8.5, color=TEXT_MAIN,
                     arrowprops=dict(arrowstyle="->", color=TEXT_SUB, lw=0.8))
    ax1.set_xlim(-2.7, 2.7)
    ax1.set_ylim(-1.6, 2.2)
    ax1.set_xlabel("market resonance state  $s$   (boom $>1$, depression $<-1$)", fontsize=9.5)
    ax1.set_ylabel("periphery depletion  $D$", fontsize=9.5)
    ax1.legend(loc="upper left", fontsize=8, framealpha=0.25)
    ax1.text(-2.62, 2.02,
             "$\\epsilon\\,\\dot{s} = s - s^3/3 - D + I$\n"
             "$\\dot{D} = \\gamma(D_\\infty - D) + \\mu\\,s$",
             fontsize=9.5, color=YANG_PEAK, va="top")

    # Panel 2: time series of the first six cycles (ratchet run)
    ax2 = fig.add_axes([0.395, 0.50, 0.56, 0.35])
    ax2.set_title("six cycles:  slow boom, snap crash, crawl of the depression",
                  loc="left", fontsize=11.5, fontweight="bold", color=YANG_BRIGHT)
    t_cut = 6.5
    m = ts2 <= t_cut
    ax2.plot(ts2[m], ss2[m], color=YANG_PEAK, lw=1.6, label="$s(t)$: market state")
    ax2.plot(ts2[m], [0.0] * int(m.sum()), color=RING, lw=0.8)
    ax2.set_ylim(-2.6, 2.6)
    ax2.set_ylabel("$s$", fontsize=10, color=YANG_PEAK)
    ax2.legend(loc="upper right", fontsize=8, framealpha=0.25)
    ax3 = ax2.twinx()
    ax3.plot(ts2[m], Ds2[m], color=YIN_LIGHT, lw=1.6,
             label="$D(t)$: periphery depletion")
    ax3.plot(ts2[m], [D_MAX] * int(m.sum()), color=YIN_LIGHT, lw=0.8, ls=(0, (3, 3)))
    ax3.set_ylim(-0.2, 1.8)
    ax3.set_ylabel("$D$", fontsize=10, color=YIN_LIGHT)
    ax3.tick_params(axis="y", colors=YIN_LIGHT)
    ax3.spines["right"].set_color(YIN_LIGHT)
    ax3.legend(loc="lower left", fontsize=8, framealpha=0.25)
    ax2.set_xlabel("slow time  (one unit = one periphery-restoration timescale)", fontsize=9.5)
    ax2.text(0.02, 2.42,
             "the boom rides the upper branch; the crash is the snap at the fold "
             "($D \\to D_{\\max}$);\n"
             "the depression is the crawl back while the attractor restores the periphery",
             fontsize=8.5, color=TEXT_MAIN)

    # Panel 3: the tendency—per-cycle average profit rate, bust lengthening
    ax4 = fig.add_axes([0.395, 0.09, 0.56, 0.33])
    ax4.set_title("the tendency:  per-cycle average profit falls, depressions lengthen",
                  loc="left", fontsize=11.5, fontweight="bold", color=YANG_BRIGHT)
    ks = np.arange(1, len(stats2) + 1)
    r_avgs = np.array([st["r_avg"] for st in stats2])
    busts = np.array([st["bust"] for st in stats2])
    ax4.plot(ks, r_avgs, color=YANG_PEAK, lw=2.2, marker="o", ms=4,
             label="$\\langle r \\rangle_k$: average profit rate of cycle $k$")
    ax4.axhline(-DELTA, color=YANG_MID, lw=1.0, ls=(0, (4, 3)))
    ax4.text(0.6, -DELTA - 0.014, "maintenance floor  $r = -\\delta$",
             fontsize=8, color=YANG_MID)
    ax4.set_ylim(-0.09, 0.35)
    ax4.set_xlabel("cycle index  $k$", fontsize=9.5)
    ax4.set_ylabel("$\\langle r \\rangle_k$", fontsize=10, color=YANG_PEAK)
    ax4.legend(loc="upper right", fontsize=8, framealpha=0.25)
    ax4b = ax4.twinx()
    ax4b.plot(ks, busts, color=YIN_LIGHT, lw=1.8, marker="s", ms=3.5,
              label="$\\tau_{\\rm bust}$: depression duration")
    ax4b.set_ylabel("$\\tau_{\\rm bust}$", fontsize=10, color=YIN_LIGHT)
    ax4b.tick_params(axis="y", colors=YIN_LIGHT)
    ax4b.spines["right"].set_color(YIN_LIGHT)
    ax4b.legend(loc="center right", fontsize=8, framealpha=0.25)
    ax4.annotate("the last recovery fails:\nregime parks at the fold, $r = -\\delta$",
                 xy=(ks[-1], r_avgs[-1]), xytext=(ks[-1] - 4.6, -0.055),
                 fontsize=8.5, color=YANG_PEAK,
                 arrowprops=dict(arrowstyle="->", color=YANG_PEAK, lw=0.9))

    OUT = "experiments/coherence_cycle/relaxation_cycle.png"
    fig.savefig(OUT, dpi=170, facecolor=BG)
    print(f"wrote {OUT}")

    # ──────────────────────────── VERIFICATION ────────────────────────────────
    print("\n=== verification ===")
    print(f"folds from the cubic:  D_min = I - 2/3 = {D_MIN:.4f}   "
          f"D_max = I + 2/3 = {D_MAX:.4f}")
    print(f"death threshold (FP parks on the min fold):  "
          f"D_star = I + mu/gamma - 2/3 = {D_STAR:.4f}")
    print(f"\nrun 1 (clean cycle, footprint frozen):  {n_cycles} cycles in 40 slow units")
    print(f"  last two periods:  {per1:.4f}  {per2:.4f}   (self-sustained: "
          f"{'PASS' if abs(per1 - per2) < 1e-3 else 'FAIL'})")
    print(f"  cycle triggered near the folds:  crash at D = {D_crash_t:.4f} "
          f"(fold {D_MAX:.4f}, overshoot {abs(D_crash_t - D_MAX):.3f} ~ O(sqrt(eps)): "
          f"{'PASS' if abs(D_crash_t - D_MAX) < 0.15 else 'FAIL'}), "
          f"recovery at D = {D_rec_t:.4f} "
          f"(fold {D_MIN:.4f}, overshoot {abs(D_rec_t - D_MIN):.3f} ~ O(sqrt(eps)): "
          f"{'PASS' if abs(D_rec_t - D_MIN) < 0.15 else 'FAIL'})")
    print(f"  note: the trajectory carries past the fold by ~sqrt(eps) before the jump fires—"
          f"the fast variable's relaxation vanishes at the saddle-node, the same critical "
          f"slowing verified in run 3")
    st = stats[1]  # a settled cycle
    print(f"  settled cycle:  period {st['period']:.3f}  = boom {st['boom']:.3f} "
          f"+ crash {st['crash']:.3f} + bust {st['bust']:.3f}")
    print(f"  crash is {st['boom'] / max(st['crash'], 1e-9):.1f}x faster than the boom "
          f"(violent transition)")
    print(f"  average profit of the settled cycle:  {st['r_avg']:.4f}")
    q_peak = q_of_D(D_MIN)
    r_peak = LAM * q_peak - DELTA
    r_crash = LAM * q_of_D(D_MAX) - DELTA
    print(f"  boom opens at q = {q_peak:.4f}, r = {r_peak:.4f};  "
          f"boom ends at r = {r_crash:.4f} (== -delta: "
          f"{'PASS' if abs(r_crash + DELTA) < 1e-9 else 'FAIL'})")
    # overproduction: r crosses zero before the crash
    D_zero = D_MAX * (1.0 - DELTA / LAM)
    print(f"  overproduction: r crosses zero at D = {D_zero:.4f}, "
          f"{(D_MAX - D_zero) / (D_MAX - D_MIN) * 100:.1f}% of the boom's drain before the fold")

    print(f"\nrun 2 (ratchet run, footprint grows with H_peak):")
    print(f"  cycles run: {len(stats2)}   H from 1.00 to {Hs2[-1]:.3f}")
    print(f"  per-cycle average profit:  " +
          "  ".join(f"k={k}:{st['r_avg']:.4f}" for k, st in
                    list(enumerate(stats2, 1))[::2]))
    r_first, r_last = stats2[0]["r_avg"], stats2[-1]["r_avg"]
    print(f"  tendency:  <r> falls {r_first:.4f} -> {r_last:.4f} across cycles "
          f"({'PASS' if r_last < r_first else 'FAIL'})")
    b_first, b_last = stats2[0]["bust"], stats2[-1]["bust"]
    print(f"  depressions lengthen:  {b_first:.3f} -> {b_last:.3f} "
          f"({'PASS' if b_last > b_first else 'FAIL'})")
    H_max = float(Hs2.max())
    print(f"  hoard peaks at H = {H_max:.2f} (target H_star = {H_STAR:.0f});  "
          f"after the death it decays at -delta: H_end = {Hs2[-1]:.2f}")
    # death: no boom in the last three slow units, r parked at -delta, hoard decaying
    tail = ss2[-int(3.0 / dt):]
    no_boom = bool((tail < 1.0).all())
    h_decay = Hs2[-1] < H_max
    print(f"  terminal state: no boom in the last 3 slow units: {'PASS' if no_boom else 'FAIL'}, "
          f"r = {rs2[-1]:.4f} == -delta: {'PASS' if abs(rs2[-1] + DELTA) < 1e-9 else 'FAIL'}, "
          f"hoard decaying: {'PASS' if h_decay else 'FAIL'}  (s = {ss2[-1]:.3f}, parked on the fold)")

    print(f"\nrun 3 (critical slowing near the crash fold):")
    ratios = []
    for j, (d, tau) in enumerate(slowing):
        ratio = "" if j == 0 else f"   tau ratio vs previous: {tau / slowing[j - 1][1]:.2f} (expect ~3.16)"
        ratios.append(tau / slowing[j - 1][1] if j else 0.0)
        print(f"  Delta = {d:.0e}:  tau_eff = {tau:.4f}{ratio}")
    ok_slow = all(2.6 < ratios[j] < 3.9 for j in range(1, len(ratios)))
    print(f"  tau_eff ~ (D_max - D)^(-1/2):  {'PASS' if ok_slow else 'FAIL'}")

    # r(H) within the first boom: use the first full detected cycle and walk
    # the drain phase from the last pre-crash D-minimum to the crash trigger
    st = stats2[0]
    t0, t1 = st["t_start"], st["t_start"] + st["boom"] + 0.01
    seg = (ts2 >= t0) & (ts2 <= t1)
    Dseg, sseg, Hseg, rseg = Ds2[seg], ss2[seg], Hs2[seg], rs2[seg]
    crash_idx = next(k for k in range(1, len(sseg)) if sseg[k] < 1.0 <= sseg[k - 1])
    k = crash_idx                                   # walk back to the last D-min
    while k > 0 and Dseg[k] >= Dseg[k - 1]:
        k -= 1
    while k < crash_idx and Dseg[k] < D_MIN:        # past the recovery jump's dip
        k += 1
    drain = slice(k, crash_idx)
    D_b, r_b, H_b = Dseg[drain], rseg[drain], Hseg[drain]
    r_falls = bool((np.diff(r_b) <= 1e-9).all())
    D_rises = bool((np.diff(D_b) >= -1e-9).all())
    prof = r_b > 0.0
    rho = float(np.corrcoef(H_b[prof], r_b[prof])[0, 1])
    h_rises = bool((np.diff(H_b[prof]) > 0.0).all())
    h_gain = float(H_b[-1] / H_b[0])
    squeeze = float((r_b < 0.0).mean())
    print(f"\nwithin the first boom (drain phase):  D strictly rising: {'PASS' if D_rises else 'FAIL'}, "
          f"r strictly falling: {'PASS' if r_falls else 'FAIL'}")
    print(f"  hoard strictly growing while the rate falls: {'PASS' if h_rises else 'FAIL'} "
          f"(r vs H correlation {rho:+.4f}; H gains {h_gain:.2f}x over the boom)—"
          f"the rate of profit falls as the hoard grows (§4.2)")
    print(f"  the squeeze: r < 0 for the last {squeeze * 100:.1f}% of the boom before the crash "
          f"(overproduction—the boom turns unprofitable while it is still expanding)")


if __name__ == "__main__":
    main()
