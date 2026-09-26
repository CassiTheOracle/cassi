"""Stage 2a: moving + Qi-adaptive 3D mesh + sponge absorbing layer
(MESHLESS_PLAN.md Stage 2, numpy prototype).

Ports the Stage 0b recipes to the 3D jump-flooding mesh:

  - Steering (AREPO-class): sites ride the field momentum (quasi-
    Lagrangian, super-Lagrangian lam) + a Lloyd-style relaxation toward
    the cell centroid (kappa fraction per rebuild) — cells stay round.
  - ALE remap (D1 resolution, ported from Stage 0b): rebuild the mesh on
    the drifted seeds and give each new cell the state of the OLD cell
    containing its seed (nearest-old-seed = old Voronoi membership).
    Mass-conservative to the remap order — the continuous geometric
    source terms stay deferred (documented in the plan).
  - Qi-driven re-seeding (G6): n_base BCC sites + n_extra sampled from
    the INCOMPLETE-coherence distribution prob ∝ (1-q)^p · V — "the mesh
    follows Qi": resolution where coherence is still forming.
  - Sponge layer (D2 prototype): a wall-proximity mask damping pi near
    the box walls — the absorbing-boundary stand-in; the gate measures
    wave-energy absorption vs the periodic wrap-around control.

Gates:
  G5 moving mesh: L2 vs the exact reference <= 1.5x the static-mesh L2
     (the same ICs/seeds), breather within 2% of sqrt(om2 (1+phi))
  G6 Qi-adaptivity: adapted (2048+2048) beats uniform (4096) in the
     blob-core region at equal budget
  G7 sponge: total wave energy with the sponge < 1/3 of the
     no-sponge (periodic wrap) control

Run:  python stage2_moving3d.py   (~3-5 min)
"""
import numpy as np
from scipy.spatial import cKDTree

from stage1_jfa3d import (PHI, C2, OM2, OMEGA, TWO_PI, Spectral3D, _breath_freq,
                          JfaVoronoi3D, bcc_seeds, jfa_full, make_ics3d,
                          _bilinear3d)


class MovingVoronoi3D(JfaVoronoi3D):
    """JfaVoronoi3D + mesh motion: steering, periodic ALE remap, sponge."""

    def __init__(self, sites, N, L):
        self.N = N
        self.L = L
        self.h = L / N
        self.cc = (np.mgrid[0:N, 0:N, 0:N].astype(np.float64) + 0.5) * self.h
        self.build(sites)

    def build(self, sites):
        self.sites = sites
        self.n = len(sites)
        self.labels = jfa_full(sites, self.N, self.L)
        self.vol = np.bincount(self.labels.ravel(), minlength=self.n) * self.h ** 3
        self.kdt = cKDTree(sites)

    # ── the mesh-follows-Qi observables ─────────────────────────────────
    def q_coh(self, psiY, psiI):
        rho = psiY + psiI
        eps = psiY - PHI * psiI
        return (rho * rho) / (rho * rho + 1.0 / (PHI * PHI) + eps * eps)

    def centroids(self):
        """Wrapped per-cell centroids from the JFA labels (periodic grid)."""
        cnt = np.bincount(self.labels.ravel(), minlength=self.n)
        c = np.stack([
            np.bincount(self.labels.ravel(), weights=self.cc[a].ravel(),
                        minlength=self.n) for a in range(3)], axis=1)
        return c / np.maximum(cnt, 1)[:, None]

    def wall_weight(self, W):
        """Per-site wall proximity (quadratic ramp, 1.0 at the walls)."""
        d = self.L / 2.0 - np.abs(self.sites - self.L / 2.0)
        w = np.clip((W - d) / W, 0.0, 1.0) ** 2
        return w.sum(axis=1)

    # ── step with optional sponge damping ───────────────────────────────
    def step(self, psiY, psiI, piY, piI, dt, gamma=0.0, wall_w=None):
        dev = psiY - PHI * psiI
        piY = piY + dt * (C2 * self.lap(psiY) - OM2 * dev)
        piI = piI + dt * (C2 * self.lap(psiI) + OM2 * dev)
        if gamma > 0.0 and wall_w is not None:
            damp = 1.0 / (1.0 + dt * gamma * wall_w)
            piY = piY * damp
            piI = piI * damp
        psiY = psiY + dt * piY
        psiI = psiI + dt * piI
        return psiY, psiI, piY, piI

    # ── steering + ALE remap (the Stage 0b recipe, in 3D) ──────────────
    def steer_and_remap(self, psiY, psiI, piY, piI, T_steer, kappa, lam):
        rho = psiY + psiI + 1e-12
        v = lam * ((piY + piI) / rho)[:, None]
        cen = self.centroids()
        new_sites = (1.0 - kappa) * (self.sites + v * T_steer) + kappa * cen
        new_sites = np.mod(new_sites, self.L)
        old_kdt = self.kdt
        idx = old_kdt.query(new_sites)[1]
        self.build(new_sites)
        return psiY[idx], psiI[idx], piY[idx], piI[idx]

    def solve_moving(self, ey_fn, ei_fn, dt, n_steps, rebuild=25,
                     kappa=0.5, lam=8.0, gamma=0.0, W=None):
        pts = self.sites
        psiY = ey_fn(pts[:, 0], pts[:, 1], pts[:, 2]).copy()
        psiI = ei_fn(pts[:, 0], pts[:, 1], pts[:, 2]).copy()
        piY = np.zeros(self.n)
        piI = np.zeros(self.n)
        wall_w = self.wall_weight(W) if gamma > 0.0 else None
        r = np.empty(n_steps + 1)
        d = np.empty(n_steps + 1)
        r[0] = (psiY * self.vol).sum() / (psiI * self.vol).sum()
        d[0] = ((psiY - PHI * psiI) * self.vol).sum() / self.vol.sum()
        for s in range(n_steps):
            psiY, psiI, piY, piI = self.step(psiY, psiI, piY, piI, dt,
                                             gamma, wall_w)
            if (s + 1) % rebuild == 0:
                psiY, psiI, piY, piI = self.steer_and_remap(
                    psiY, psiI, piY, piI, dt * rebuild, kappa, lam)
                wall_w = self.wall_weight(W) if gamma > 0.0 else None
            r[s + 1] = (psiY * self.vol).sum() / (psiI * self.vol).sum()
            d[s + 1] = ((psiY - PHI * psiI) * self.vol).sum() / self.vol.sum()
        return r, d, psiY, psiI

    # ── deviation-mode energy — the breather oscillator's TRUE conserved
    #    functional. NOTE: the two-fluid coupling is NON-GRADIENT (the EY
    #    push on EI is -om2·dev, the EI push on EY is +phi·om2·dev — no
    #    symmetric potential exists), so no total-energy functional is
    #    conserved; the diagonal deviation mode (mass 1, spring
    #    om2(1+phi)) IS a harmonic oscillator, and its energy is the
    #    right absorption metric: the sponge damps pi, so E_dev decays.
    def wave_energy(self, psiY, psiI, piY, piI):

        cd = (psiY - PHI * psiI) / (1.0 + PHI)
        pd = (piY - PHI * piI) / (1.0 + PHI)
        e = 0.5 * (pd ** 2 + C2 * cd * (-self.lap(cd))
                   + OM2 * (1.0 + PHI) * cd ** 2) * self.vol
        return float(e.sum())



def q_weighted_seeds3d(fv, psiY, psiI, n_base, n_extra, rng, L, p=4.0):
    """'The mesh follows Qi' in 3D: n_base BCC sites + n_extra sampled
    from the incomplete-coherence distribution prob ∝ (1-q)^p · V."""
    q = fv.q_coh(psiY, psiI)
    w = ((1.0 - q) ** p) * fv.vol
    w /= w.sum()
    cells = rng.choice(fv.n, size=n_extra, p=w)
    jit = rng.uniform(-0.5, 0.5, (n_extra, 3)) * (fv.vol[cells] ** (1.0 / 3.0))[:, None]
    extra = np.mod(fv.sites[cells] + jit, L)
    return np.concatenate([bcc_seeds(n_base, L, rng), extra])


def _packet_ics(sites, L, x0, A=0.1, sig=0.4):
    """Traveling deviation packet: ey/ei gaussian, momenta zero."""
    x, y, z = sites.T
    g = np.exp(-((x - x0) ** 2 + (y - L / 2.0) ** 2 + (z - L / 2.0) ** 2)
               / (2.0 * sig ** 2))
    return 1.5 + A * g, 1.0 - A * g, np.zeros(len(sites)), np.zeros(len(sites))


def main():
    rng = np.random.default_rng(20260813)
    N = 64
    L = TWO_PI
    DT = 0.005
    T = 1.5
    t_out = np.arange(0.0, T + DT, DT)
    ey0, ei0 = make_ics3d(N, L, rng)
    spec = Spectral3D(N, L)
    r_spec, d_spec, ey_spec, _ = spec.solve(ey0, ei0, t_out)

    def ey_fn(px, py, pz):
        return _bilinear3d(px, py, pz, ey0, ei0, L)[0]

    def ei_fn(px, py, pz):
        return _bilinear3d(px, py, pz, ey0, ei0, L)[1]

    # ── G5: moving mesh must match the static mesh + the reference ──────
    print("──── stage 2a: G5 moving mesh ────")
    seeds = bcc_seeds(4096, L, rng)
    fv_static = MovingVoronoi3D(seeds.copy(), N, L)
    _, _, ey_s, ei_s = fv_static.solve(ey_fn, ei_fn, DT, len(t_out) - 1)
    l2_static = float(np.linalg.norm(fv_static.rasterize(ey_s) - ey_spec)
                      / np.linalg.norm(ey_spec))

    fv_mv = MovingVoronoi3D(seeds.copy(), N, L)
    r_mv, d_mv, ey_m, ei_m = fv_mv.solve_moving(
        ey_fn, ei_fn, DT, len(t_out) - 1, rebuild=25, kappa=0.5, lam=8.0)
    l2_mv = float(np.linalg.norm(fv_mv.rasterize(ey_m) - ey_spec)
                  / np.linalg.norm(ey_spec))
    breath_mv = _breath_freq(d_mv, DT)
    r_err_mv = float(np.max(np.abs(r_mv - r_spec)) / np.abs(r_spec.mean()))
    print("[G5] static L2=%.4f  moving L2=%.4f  max|r err|=%.4f  breath=%.4f"
          % (l2_static, l2_mv, r_err_mv, breath_mv))
    g5 = (l2_mv < 1.5 * max(l2_static, 1e-6)
          and abs(breath_mv - OMEGA) / OMEGA < 0.02 and r_err_mv < 0.05)

    # ── G6: Qi-adaptivity beats uniform in the blob core ────────────────
    print("──── stage 2a: G6 Qi-adaptivity ────")
    ey0b, ei0b = make_ics3d(N, L, rng, blob=(0.3, 0.35))
    g = np.exp(-((np.arange(N)[:, None, None] - N * 0.5) ** 2
                 + (np.arange(N)[None, :, None] - N * 0.5) ** 2
                 + (np.arange(N)[None, None, :] - N * 0.5) ** 2)
               * (L / N) ** 2 / (2.0 * 0.35 ** 2))
    gmask = g > 0.5

    def _l2_region(grid, ref):
        return float(np.linalg.norm((grid - ref) * gmask)
                     / np.linalg.norm(ref * gmask))

    def ey_fn_b(px, py, pz):
        return _bilinear3d(px, py, pz, ey0b, ei0b, L)[0]

    def ei_fn_b(px, py, pz):
        return _bilinear3d(px, py, pz, ey0b, ei0b, L)[1]

    fv_u = MovingVoronoi3D(bcc_seeds(4096, L, rng), N, L)
    pts_u = fv_u.sites
    l2b_u = _l2_region(fv_u.rasterize(ey_fn_b(pts_u[:, 0], pts_u[:, 1],
                                              pts_u[:, 2])), ey0b)
    # adapted: q from a 2048-site mesh on the IC, extras follow (1-q)^p
    fv_q = MovingVoronoi3D(bcc_seeds(2048, L, rng), N, L)
    pts_q = fv_q.sites
    psi0y = ey_fn_b(pts_q[:, 0], pts_q[:, 1], pts_q[:, 2])
    psi0i = ei_fn_b(pts_q[:, 0], pts_q[:, 1], pts_q[:, 2])
    adapt_seeds = q_weighted_seeds3d(fv_q, psi0y, psi0i, 2048, 2048, rng, L)
    fv_a = MovingVoronoi3D(adapt_seeds, N, L)
    pts_a = fv_a.sites
    l2b_a = _l2_region(fv_a.rasterize(ey_fn_b(pts_a[:, 0], pts_a[:, 1],
                                               pts_a[:, 2])), ey0b)
    print("[G6] blob-core IC reconstruction L2: uniform=%.4f  adapted=%.4f"
          % (l2b_u, l2b_a))
    g6 = l2b_a < l2b_u

    # ── G7: sponge layer absorbs; the periodic wrap control conserves ───
    W = 2.0

    x0 = L - 1.5
    DT_S = 0.01
    n_steps = 400
    e_ratio = {}
    for name, gamma in [("no-sponge", 0.0), ("sponge", 20.0)]:
        fv_sp = MovingVoronoi3D(bcc_seeds(2048, L, rng), 48, L)
        pts = fv_sp.sites
        psiY, psiI, piY, piI = _packet_ics(pts, L, x0)
        e0 = fv_sp.wave_energy(psiY, psiI, piY, piI)
        wall_w = fv_sp.wall_weight(W) if gamma > 0.0 else None
        for _ in range(n_steps):
            psiY, psiI, piY, piI = fv_sp.step(psiY, psiI, piY, piI, DT_S,
                                              gamma, wall_w)
        e1 = fv_sp.wave_energy(psiY, psiI, piY, piI)
        e_ratio[name] = e1 / max(e0, 1e-30)
        print("[G7] %s: E_final/E_0 = %.3f" % (name, e_ratio[name]))
    g7 = e_ratio["sponge"] < e_ratio["no-sponge"] / 3.0

    print("---- gate ----")
    for name, ok in [("G5 moving mesh", g5),
                     ("G6 Qi-adaptivity", g6),
                     ("G7 sponge absorption", g7)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (g5 and g6 and g7)
                          else "FAILURES PRESENT"))


if __name__ == "__main__":
    main()
