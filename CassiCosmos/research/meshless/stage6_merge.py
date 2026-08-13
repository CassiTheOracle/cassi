"""Stage 6 — particle agglomeration (Cassi merge), numpy reference + gates.

The particle-level complement of the meshless collapse (MESHLESS_PLAN.md
§3.3): two particles within a merge radius R_m coalesce (mass + momentum
conserved, survivor = mass-weighted centroid) ONLY where the local
coherence q_coh = rho^2/(rho^2 + phi^-2 + eps^2) is ABOVE the phi-anchored
threshold phi^-2 (structure forms in coherent regions; non-coherent regions
free-stream). Design: research/meshless/particle_merge_design.md.

This script is the EXACT float64 reference the GPU shader
(compute/cassi_particle_merge.glsl) must reproduce: a direct O(N^2) pair
scan with the SAME deterministic (hop, fold) rule and the SAME trilinear
q_coh sampling. It stays the "numpy reference" so the shader's spatial hash
is validated against it, never vice-versa.

Gates (run:  python stage6_merge.py):
  G25  random cloud + planted close pair: total mass AND total momentum
       conserved to ~1e-12 (float64) across the merge.
  G26  the q gate: identical pairs in LOW-q regions do NOT merge, the SAME
       pairs in HIGH-q regions DO (deterministic same-seed/same geometry).
  G27  small collapsing cluster (RealSim-style drag on): repeatedly merging
       reduces particle count(t) monotonically while mass stays constant;
       R_m sensitivity reported.
  G28  [GPU] the GPU merge (spatial hash + float atomics, identical planted
       input) merges the SAME pairs with the SAME masses <= 1e-3 relative.
  G29  [GPU] GPU momentum conservation <= 1e-3.
G28/G29 run only when _diag/merge_gpu.json exists (produced by
scripts/verify_merge.gd); otherwise the prototype gates alone are reported.

Planted field: piecewise-constant EY/EI on an N^3 grid. HIGH-q region
(EY=PHI, EI=1) -> q_coh = (1+phi)^2/((1+phi)^2+phi^-2) ~ 0.947; LOW-q region
(EY=EI=0.05) -> q_coh ~ 0.03. The threshold phi^-2 ~ 0.382 separates them
cleanly, so fp32 GPU sampling cannot flip any planted decision.
"""
import json
import os

import numpy as np

PHI = 1.618033988749895
PHI_INV2 = 0.3819660112501051  # phi^-2 — the decoherence (merge-gate) threshold
PHI_INV3 = 0.2360679774997898  # phi^-3 — RealSim drag reference rho_ref

# - config (MUST match scripts/verify_merge.gd for G28/G29) ---------------
N_GRID = 64
EXTENT = 37.5          # box half-extent (probe default; matches sim's bh[2].y)
H0 = 2.0 * EXTENT / N_GRID      # reference grid cell
RM_FRAC = 0.5          # R_m = RM_FRAC * H0
R_M = RM_FRAC * H0
Q_TH = PHI_INV2
HIGH_EY = PHI; HIGH_EI = 1.0   # q_coh ~ 0.947
LOW_EY = 0.05; LOW_EI = 0.05   # q_coh ~ 0.03
MERGE_RESULTS = {}     # populated by the probes; read by g27


# - field helpers (world->grid map + trilinear, exact nbody convention) ---
def make_field(high_region=True):
    """Piecewise-constant EY/EI, one value over the whole box.

    high_region=True -> the HIGH-q value (coherent; merges allowed).
    False -> the LOW-q value (decoherent; free-streaming).
    """
    ey = np.full((N_GRID,) * 3, HIGH_EY if high_region else LOW_EY, dtype=np.float64)
    ei = np.full((N_GRID,) * 3, HIGH_EI if high_region else LOW_EI, dtype=np.float64)
    return ey, ei


def make_field_from_grids(ey_list, ei_list):
    """Wrap GPU-shipped flat EY/EI arrays into the numpy (N,N,N) field.

    The GPU buffer is flat in idx3 order = x + N*(y + N*z) (x fastest), so
    numpy reshape((N,N,N)) yields [z][y][x]; the trilinear sampler reads
    [x][y][z], hence the transpose(2,1,0).
    """
    ey = np.array(ey_list, dtype=np.float64).reshape((N_GRID,) * 3).transpose(2, 1, 0)
    ei = np.array(ei_list, dtype=np.float64).reshape((N_GRID,) * 3).transpose(2, 1, 0)
    return ey, ei


def world_to_grid(wp, N=N_GRID, ext=EXTENT):
    hn = float(N) * 0.5
    return (wp / ext) * hn + hn


def trilinear(field, wp, N=N_GRID, ext=EXTENT):
    """Trilinear sample of a per-cell scalar field at world point wp."""
    gc = world_to_grid(wp, N, ext)
    i0 = int(np.floor(gc[0])); j0 = int(np.floor(gc[1])); k0 = int(np.floor(gc[2]))
    fx, fy, fz = gc[0] - i0, gc[1] - j0, gc[2] - k0
    i0 %= N; j0 %= N; k0 %= N
    i1, j1, k1 = (i0 + 1) % N, (j0 + 1) % N, (k0 + 1) % N
    c000 = field[i0, j0, k0]; c100 = field[i1, j0, k0]
    c010 = field[i0, j1, k0]; c110 = field[i1, j1, k0]
    c001 = field[i0, j0, k1]; c101 = field[i1, j0, k1]
    c011 = field[i0, j1, k1]; c111 = field[i1, j1, k1]
    q0 = (c000 * (1 - fx) + c100 * fx) * (1 - fy) + (c010 * (1 - fx) + c110 * fx) * fy
    q1 = (c001 * (1 - fx) + c101 * fx) * (1 - fy) + (c011 * (1 - fx) + c111 * fx) * fy
    return q0 * (1 - fz) + q1 * fz


def qcoh_at(ey, ei, wp):
    """q_coh = rho^2/(rho^2+phi^-2+eps^2) at wp, rho=EY+EI, eps=EY-phi*EI."""
    eyv = trilinear(ey, wp)
    eiv = trilinear(ei, wp)
    rho = eyv + eiv
    eps = eyv - PHI * eiv
    return (rho * rho) / (rho * rho + PHI_INV2 + eps * eps)


def min_image(p, q, ext=EXTENT):
    d = np.asarray(p, dtype=np.float64) - np.asarray(q, dtype=np.float64)
    d -= np.round(d / (2.0 * ext)) * (2.0 * ext)
    return d


def _collapse_loop(n, alive, m, mom, cent, p, v, ey, ei, max_cycles=64):
    """Shared (fold, best, sink, hop) coalescing loop.

    mirrors the GPU shader's cycle exactly:
      fold  : survivors take their accumulated centroid/momentum (mom/cent
              carry the cross-cycle running accumulation; identity on cycle 1)
      best  : best[i] = min index over alive qualified neighbors, else i
      sink  : sink[i] = (best[i] == i)  — i has no lower qualified neighbor
      hop   : i merges into best[i] ONLY IF best[i] != i AND sink[best[i]]
              (never into a particle that might itself forward this cycle, so
               a receiver is never also a forwarder -> no stranded momentum)
    Momentum/mass are EXACTLY conserved: every transfer moves the source's
    full canonical state to a sink that survives the cycle; a sink that
    later becomes non-sink forwards its whole (accumulated) state.
    """
    merges_total = 0
    for _ in range(max_cycles):
        # fold accumulated gains into canonical positions/velocities
        for i in range(n):
            if alive[i] and m[i] > 0.0:
                v[i] = mom[i] / m[i]
                p[i] = cent[i] / m[i]
        # best + sink over the folded canonical positions
        best = np.arange(n, dtype=np.int64)
        for i in range(n):
            if not alive[i]:
                continue
            for j in range(n):
                if j == i or not alive[j]:
                    continue
                if np.linalg.norm(min_image(p[i], p[j])) > R_M:
                    continue
                if qcoh_at(ey, ei, (p[i] + p[j]) * 0.5) <= Q_TH:
                    continue
                if j < best[i]:
                    best[i] = j
        sink = best == np.arange(n, dtype=np.int64)
        # hop: transfer canonical state to surviving sinks
        cycle_merges = 0
        for i in range(n):
            if not alive[i]:
                continue
            b = int(best[i])
            if b < i and sink[b] and alive[b]:
                m[b] += m[i]
                mom[b] += mom[i]
                cent[b] += cent[i]
                alive[i] = 0
                cycle_merges += 1
        merges_total += cycle_merges
        if cycle_merges == 0:
            break
        if int(alive.sum()) <= 1:
            break
    return alive, m, mom, cent, p, v, merges_total


def collapse(pos, vel, mass, ey, ei):
    """Deterministic lowest-index collapse to fixpoint (the GPU shader's
    (fold,best,sink,hop) iteration in exact float64).

    Returns (survivor_pos, survivor_vel, survivor_mass) — COMPACT arrays of
    the surviving particles only (merged ones are dropped). The survivor set
    is the minimum-index member of each connected qualified cluster; mass and
    momentum are exactly conserved.
    """
    n = len(pos)
    alive = np.ones(n, dtype=bool)
    m = mass.astype(np.float64).copy()
    mom = (vel * mass[:, None]).astype(np.float64)
    cent = (pos * mass[:, None]).astype(np.float64)
    p = pos.astype(np.float64).copy()
    v = vel.astype(np.float64).copy()
    alive, m, mom, cent, p, v, _ = _collapse_loop(n, alive, m, mom, cent, p, v, ey, ei)
    idx = np.where(alive)[0]
    return p[idx], v[idx], m[idx]


def collapse_indexed(pos, vel, mass, ey, ei):
    """Like `collapse` but returns (alive_bool[N], mass_accum[N]) over the
    FULL index space — for G28's index-matched GPU/numpy survivor compare.
    Dead particles carry mass 0 (and zero velocity/position), so full-array
    sums are correct."""
    n = len(pos)
    alive = np.ones(n, dtype=bool)
    m = mass.astype(np.float64).copy()
    mom = (vel * mass[:, None]).astype(np.float64)
    cent = (pos * mass[:, None]).astype(np.float64)
    p = pos.astype(np.float64).copy()
    v = vel.astype(np.float64).copy()
    alive, m, mom, cent, p, v, _ = _collapse_loop(n, alive, m, mom, cent, p, v, ey, ei)
    m_full = np.where(alive, m, 0.0)
    v_full = np.where(alive[:, None], v, 0.0)
    p_full = np.where(alive[:, None], p, 0.0)
    return alive, m_full, v_full, p_full


def total_momentum(vel, mass):
    return (vel * mass[:, None]).sum(axis=0)


# - gates ------------------------------------------------------------------
def g25():
    """Random cloud + planted close pair; mass & momentum conserved ~1e-12."""
    rng = np.random.default_rng(20260813)
    n = 100
    # sparse cloud: grid-spaced (>> 2*R_M) + jitter so NO two cloud particles
    # are within R_M — the only merge is the planted close pair, isolating the
    # conservation gate to a single deterministic coalescence.
    side = int(round(n ** (1.0 / 3.0)))           # 5^3 = 125 >= n
    pos = np.zeros((side ** 3, 3))
    k = 0
    for a in range(side):
        for b in range(side):
            for c in range(side):
                pos[k] = np.array([20.0, 0.0, 0.0]) + np.array([a, b, c]) * 3.0 \
                    + rng.uniform(-0.2, 0.2, 3)
                k += 1
    pos = pos[:n]
    vel = rng.uniform(-0.5, 0.5, (n, 3))
    mass = rng.uniform(0.3, 30.0, n)
    # planted close pair at indices 0,1 far from the cloud (>= 12) -> isolated
    pos[0] = np.array([5.0, 0.0, 0.0])
    pos[1] = pos[0] + np.array([0.35, 0.0, 0.0])   # d = 0.35 <= R_M
    vel[0] = np.array([0.1, 0.2, -0.1])
    vel[1] = np.array([-0.2, 0.05, 0.3])
    ey, ei = make_field(high_region=True)
    m0 = mass.sum()
    p0 = total_momentum(vel, mass)
    p_s, v_s, m_s = collapse(pos, vel, mass, ey, ei)
    n_surv = len(m_s)
    dm = abs(m_s.sum() - m0)
    dp = np.linalg.norm(total_momentum(v_s, m_s) - p0)
    g = dm <= 1e-12 and dp <= 1e-12 and n_surv == n - 1
    print("[G25] random cloud + planted pair: survivors=%d (merged 1)  "
          "mass err=%.3e  momentum err=%.3e (<=1e-12)  %s"
          % (n_surv, dm, dp, "PASS" if g else "FAIL"))
    global MERGE_RESULTS
    MERGE_RESULTS = {"n0": n, "n1": n_surv, "dm": dm, "dp": dp}
    return g


def g26():
    """Identical pairs in LOW-q do NOT merge; the SAME pairs in HIGH-q DO."""
    pair_pos = np.array([[3.0, 3.0, 0.0], [3.0 + 0.3, 3.0, 0.0]])  # d=0.3<=R_M
    pair_vel = np.zeros((2, 3))
    pair_mass = np.array([7.0, 7.0])
    ey_high, ei_high = make_field(high_region=True)
    ey_low, ei_low = make_field(high_region=False)
    _, _, m_h = collapse(pair_pos.copy(), pair_vel.copy(), pair_mass.copy(), ey_high, ei_high)
    _, _, m_l = collapse(pair_pos.copy(), pair_vel.copy(), pair_mass.copy(), ey_low, ei_low)
    n_high = len(m_h); n_low = len(m_l)
    g = n_high == 1 and n_low == 2
    print("[G26] HIGH-q pair: survivors=%d (merged)  LOW-q pair: survivors=%d (free-streams)\n"
          "      identical geometry/seed  %s"
          % (n_high, n_low, "PASS" if g else "FAIL"))
    return g


def g27():
    """Small collapsing cluster w/ RealSim drag: count(t) monotonic, mass const."""
    dt = 0.02
    n_steps = 80
    gamma = 0.5                 # RealSim drag (viscous motion through the medium)
    n = 40
    rng = np.random.default_rng(271828)
    pos = np.clip(rng.normal(0.0, 0.6, (n, 3)), -10.0, 10.0)
    vel = -0.8 * pos / (np.linalg.norm(pos, axis=1)[:, None] + 1e-6)  # inward
    mass = rng.uniform(0.5, 5.0, n)
    ey, ei = make_field(high_region=True)   # the cluster collapses in coherence
    m0 = mass.sum()
    counts = [n]
    for _ in range(n_steps):
        # velocity-Verlet with RealSim drag a = -gamma*v (mode-4 doctrine:
        # motion through the coherent medium dissipates kinetic energy)
        v_half = vel + (-gamma * vel) * (dt * 0.5)
        pos = np.clip(pos + v_half * dt, -30.0, 30.0)   # keep inside the box
        vel = v_half + (-gamma * v_half) * (dt * 0.5)
        pos, vel, mass = collapse(pos, vel, mass, ey, ei)
        counts.append(len(mass))
        if len(mass) <= 1:
            break
    mono = all(counts[i + 1] <= counts[i] for i in range(len(counts) - 1))
    dm = abs(mass.sum() - m0)
    g = mono and dm <= 1e-9 and counts[-1] <= counts[0]

    print("[G27] collapse cluster: count(t) = %s" % counts)
    print("[G27] monotonic count(t)=%s  mass err=%.3e (<=1e-9)  final=%d<=%d  %s"
          % (mono, dm, counts[-1], counts[0], "PASS" if g else "FAIL"))

    # R_m sensitivity: same collapsing cluster, several R_m -> survivors + time
    print("[G27] R_m sensitivity (frac x H0 -> survivors, steps-to-single):")
    sens_ref = None
    for frac in [0.25, 0.5, 1.0, 2.0]:
        rng2 = np.random.default_rng(271828)
        pp = np.clip(rng2.normal(0.0, 0.6, (n, 3)), -10.0, 10.0)
        vv = -0.8 * pp / (np.linalg.norm(pp, axis=1)[:, None] + 1e-6)
        mm = rng2.uniform(0.5, 5.0, n)
        rm = frac * H0
        steps = 0
        for s in range(n_steps):
            vh = vv + (-gamma * vv) * (dt * 0.5)
            pp = np.clip(pp + vh * dt, -30.0, 30.0)
            vv = vh + (-gamma * vh) * (dt * 0.5)
            pp, vv, mm = _collapse_rm(pp, vv, mm, ey, ei, rm)
            steps = s + 1
            if len(mm) <= 1:
                break
        na = len(mm)
        print("      R_m=%.2f H0 -> %d survivors, %d steps" % (frac, na, steps))
    return g


def _collapse_rm(pos, vel, mass, ey, ei, R_m):
    """Same deterministic collapse as `collapse`, but with R_m an argument."""
    global R_M
    saved = R_M
    R_M = R_m
    try:
        p, v, m = collapse(pos, vel, mass, ey, ei)
    finally:
        R_M = saved
    return p, v, m


# - GPU gates (G28/G29) run from the verify_merge.gd JSON dump --------------
def g28_gpu(gpu):
    """GPU merge == numpy reference on the identical planted input, <=1e-3."""
    ey, ei = make_field_from_grids(gpu["ey"], gpu["ei"])
    n = int(gpu["N"])
    pos = np.array(gpu["pos"], dtype=np.float64).reshape(n, 3)
    vel = np.array(gpu["vel"], dtype=np.float64).reshape(n, 3)
    mass = np.array(gpu["mass"], dtype=np.float64)
    alive_gpu = np.array(gpu["alive"], dtype=bool)
    merge_gpu = int(gpu["merge_count"])

    alive_ref, m_ref, _, _ = collapse_indexed(pos, vel, mass, ey, ei)
    merge_ref = int((~alive_ref).sum())

    surv_gpu = set(np.where(alive_gpu)[0].tolist())
    surv_ref = set(np.where(alive_ref)[0].tolist())
    if surv_gpu != surv_ref:
        print("[G28] survivor-index mismatch: GPU=%s numpy=%s"
              % (sorted(surv_gpu), sorted(surv_ref)))
        return False
    if merge_gpu != merge_ref:
        print("[G28] merge-count mismatch: GPU=%d numpy=%d" % (merge_gpu, merge_ref))
        return False
    worst = 0.0
    for i in surv_ref:
        g_m = float(gpu["mass_final"][i])
        r_m = float(m_ref[i])
        worst = max(worst, abs(g_m - r_m) / max(abs(r_m), 1e-30))
    g = worst <= 1e-3
    print("[G28] GPU==numpy: %d merges (both)  %d matching survivors  "
          "worst rel mass err=%.2e (<=1e-3)  %s"
          % (merge_ref, len(surv_ref), worst, "PASS" if g else "FAIL"))
    return g


def g29_gpu(gpu):
    """GPU momentum before vs after the merge, <= 1e-3."""
    n = int(gpu["N"])
    vel0 = np.array(gpu["vel"], dtype=np.float64).reshape(n, 3)
    mass0 = np.array(gpu["mass"], dtype=np.float64)
    vel1 = np.array(gpu["vel_final"], dtype=np.float64).reshape(n, 3)
    mass1 = np.array(gpu["mass_final"], dtype=np.float64)
    p_before = (vel0 * mass0[:, None]).sum(axis=0)
    p_after = (vel1 * mass1[:, None]).sum(axis=0)
    rel = np.linalg.norm(p_after - p_before) / max(np.linalg.norm(p_before), 1e-30)
    g = rel <= 1e-3
    print("[G29] GPU momentum conservation: |P_a - P_b|/|P_b| = %.3e (<=1e-3)  %s"
          % (rel, "PASS" if g else "FAIL"))
    return g


# - main -------------------------------------------------------------------
def main():
    print("Stage 6 particle merge reference:  PHI=%.6f  phi^-2=%.6f  "
          "R_m=%.3f (%.2f x H0=%.3f)  Q_th=phi^-2"
          % (PHI, PHI_INV2, R_M, RM_FRAC, H0))
    ok = [("G25 mass/momentum conservation (1e-12)", g25()),
          ("G26 q-gate (high merges / low free-streams)", g26()),
          ("G27 monotonic collapse + R_m sensitivity", g27())]
    gpu_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "_diag", "merge_gpu.json"))
    if os.path.exists(gpu_path):
        with open(gpu_path) as f:
            gpu = json.load(f)
        ok.append(("G28 GPU == numpy merge (1e-3)", g28_gpu(gpu)))
        ok.append(("G29 GPU momentum conservation (1e-3)", g29_gpu(gpu)))
    else:
        print("[merge] _diag/merge_gpu.json not found — G28/G29 deferred to the GPU run.")
    print("---- gates ----")
    all_pass = True
    for name, passed in ok:
        all_pass = all_pass and passed
        print("[%s] %s" % ("PASS" if passed else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if all_pass else "FAILURES PRESENT"))


if __name__ == "__main__":
    main()
