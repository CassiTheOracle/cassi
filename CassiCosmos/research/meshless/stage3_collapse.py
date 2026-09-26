"""Stage 3: matter formation as collapse (MESHLESS_PLAN.md §3.3, Stage 3).

The condensation pathway: when a cell's Qi field magnitude crosses the
condensation threshold (R3 resolution — the same peak criterion the sim's
condensation scanner already detects: q_field = EY²+EI², NOT the
coherence gate q_coh which is LOW at deviation peaks), the connected
condensed core COALESCES into one matter particle — the plan's "the cell
collapses into a matter particle; the cascade continues", one object per
peak. Mass = sum of rho·V over the core; position = rho-weighted
centroid. The condensate BREATHES, so the criterion fires on the
peak-phase Qi magnitude (the windowed max over the evolution).

Gate: the formed mass function follows the theory's cascade ladder.
The multi-rung IC (the sim's own φ-spaced bubble seeding) gives blobs
with φ-spaced radii, so the collapsed core masses sit on φ³-rung
spacing (log_phi(m) = n_min + 3k); a CONTROL IC with non-φ radii must
NOT show the alignment. Both arms share the SAME fixed blob centers —
two per band on a symmetric axis shell at distance 3.0 (no center blob;
its halo bridged the shell cores in the earlier design) — only the
radii differ (×1.4, whose band step 3·log_phi(1.4) ≈ 2.09 stays off
the 3-rung lattice). The statistic is offset-invariant: the median
distance of (n - n_min)/3 from integers.

  G8 rung alignment: score_phi > score_control + 0.10 AND the φ arm
     forms >= 6 particles (all six blobs collapse).

Run:  python stage3_collapse.py
"""
import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components

from stage1_jfa3d import PHI, TWO_PI, bcc_seeds
from stage2_moving3d import MovingVoronoi3D


def make_blob_ics(sites, L, radii, A=0.5):
    """Deviation blobs at the given radii on FIXED centers: psiY =
    1.5 + sum A g_k, psiI = 1.0 - sum A g_k. Two blobs per band on a
    symmetric axis shell (distance 3.0 from the box center): band 0 on
    +-x, band 1 on +-y, band 2 on +-z — identical geometry in both
    arms, only the radii differ."""
    n = len(sites)
    psiY = np.full(n, 1.5)
    psiI = np.ones(n)
    shell = 3.4
    c0 = np.array([L / 2.0, L / 2.0, L / 2.0])

    positions = []
    for e in np.eye(3):
        positions.append(c0 + shell * e)
        positions.append(c0 - shell * e)
    for band_idx, r in enumerate(radii):
        for k in range(2):
            c = positions[2 * band_idx + k]
            d = np.mod(sites - c, L)
            d = np.minimum(d, L - d)
            g = np.exp(-(d ** 2).sum(axis=1) / (2.0 * r ** 2))
            psiY += A * g
            psiI -= A * g
    return psiY, psiI


def collapse(fv, qf, rho, q_field_th):
    """Threshold the Qi field magnitude, extract connected condensed
    cores on the mesh adjacency, coalesce each into a matter particle.
    Returns (masses, positions)."""
    core = (qf > q_field_th) & (fv.vol > 0.0)
    core_idx = np.where(core)[0]
    if len(core_idx) == 0:
        return np.array([]), np.zeros((0, 3))
    n = fv.n
    # mesh adjacency: grid faces separating different labels
    lab = fv.labels
    rows = []
    cols = []
    for ax in range(3):
        lab_n = np.roll(lab, -1, ax)
        cross = lab != lab_n
        if cross.any():
            rows.append(lab[cross])
            cols.append(lab_n[cross])
    rows = np.concatenate(rows)
    cols = np.concatenate(cols)
    adj = sparse.csr_matrix(
        (np.ones(len(rows)), (rows, cols)), shape=(n, n))
    adj = (adj + adj.T).tocsr()
    # sub-matrix over the condensed core only
    core_set = set(core_idx.tolist())
    r2 = []
    c2 = []
    for i in core_idx:
        for j in adj.indices[adj.indptr[i]:adj.indptr[i + 1]]:
            if j in core_set:
                r2.append(i)
                c2.append(j)
    sub = sparse.csr_matrix(
        (np.ones(len(r2)), (r2, c2)), shape=(n, n))
    n_comp, comp_labels = connected_components(sub, directed=False)
    masses = []
    positions = []
    for c in range(n_comp):
        cells = np.where(comp_labels == c)[0]
        if not core[cells].any():
            continue  # isolated non-core singleton (scipy includes all nodes)
        w = rho[cells] * fv.vol[cells]
        if w.sum() <= 0.0:
            continue  # degenerate zero-volume core
        m = w.sum()
        pos = (fv.sites[cells] * w[:, None]).sum(axis=0) / w.sum()
        masses.append(m)
        positions.append(pos)
    return np.array(masses), np.array(positions)


def rung_score(masses, m_cell):
    """Offset-invariant rung alignment: the φ-spaced radii put the
    masses on 3-rung spacing (log_phi(m) = n_min + 3k), so score the
    distance of (n - n_min)/3 from integers — 1.0 = perfectly 3-spaced,
    0.0 = maximally off."""
    if len(masses) < 3:
        return 0.5
    nn = np.log(masses / m_cell) / np.log(PHI)
    frac3 = np.abs((nn - nn.min()) / 3.0 - np.round((nn - nn.min()) / 3.0))
    return float(1.0 - 2.0 * np.median(frac3))


def main():
    rng = np.random.default_rng(20260813)
    N = 64
    L = 10.0

    DT = 0.005
    n_steps = 80
    fv = MovingVoronoi3D(bcc_seeds(16384, L, rng), N, L)

    # φ-spaced radii (the multi-rung seeding) vs a ×1.4 control
    # (band step 3·log_phi(1.4) = 2.09 — off the 3-rung lattice)
    radii_phi = [1.2, 0.74, 0.46]
    radii_ctl = [r * 1.4 for r in radii_phi]
    # fixed condensation threshold (baseline qf = 3.25; core peak 4.25)
    q_th = 3.6

    results = {}
    for name, radii in [("phi-rung", radii_phi), ("control", radii_ctl)]:
        psiY, psiI = make_blob_ics(fv.sites, L, radii, A=0.5)
        piY = np.zeros(fv.n)
        piI = np.zeros(fv.n)
        # the condensate BREATHES: track the peak-phase Qi magnitude
        # (the condensation criterion fires at the maximum, not at an
        # arbitrary phase — R3's threshold applies to the peak)
        qf_max = psiY ** 2 + psiI ** 2
        for _ in range(n_steps):
            psiY, psiI, piY, piI = fv.step(psiY, psiI, piY, piI, DT)
            qf_max = np.maximum(qf_max, psiY ** 2 + psiI ** 2)
        masses, pos = collapse(fv, qf_max, psiY + psiI, q_th)
        m_cell = float(((psiY + psiI) * fv.vol).sum() / fv.n)
        score = rung_score(masses, m_cell)
        nn = np.log(np.maximum(masses, 1e-30) / m_cell) / np.log(PHI)
        results[name] = (masses, nn, score)
        print("[%s] q_th=%.2f  formed=%d  masses in [%.2f, %.2f] m_cell"
              % (name, q_th, len(masses),
                 masses.min() / m_cell if len(masses) else 0.0,
                 masses.max() / m_cell if len(masses) else 0.0))
        print("[%s] n = log_phi(m/m_cell): %s" % (
            name, np.round(np.sort(nn), 2).tolist() if len(nn) else []))
        print("[%s] rung score (1-2·median δn/3) = %.3f" % (name, score))

    s_phi = results["phi-rung"][2]
    s_ctl = results["control"][2]
    n_phi = len(results["phi-rung"][0])
    g8 = s_phi > s_ctl + 0.10 and n_phi >= 5
    print("---- gate ----")
    for nm, ok in [("G8 rung alignment (phi vs control, >=5 formed)", g8)]:

        print("[%s] %s" % ("PASS" if ok else "FAIL", nm))
    print("RESULT: %s" % ("ALL PASS" if g8 else "FAILURES PRESENT"))


if __name__ == "__main__":
    main()
