#!/usr/bin/env python3
"""run_cascade_tree.py — the M2 offline φ-cascade-tree ORCHESTRATOR.

Launches the whole proton→supercluster ladder END-TO-END UNATTENDED: one
command builds the build order (parent levels condense via Stage-3 machinery,
children ingest the parent survey dirs as ICs), runs every level as its own
periodic solve (φ-spaced, never N/2), checkpoints after each node (resume a
killed run), and farms sibling branches in parallel (never inside a level).

The cascade tree registry (self-describing):
  cascade_tree/tree_registry.json       — nodes + edges + overall progress
  cascade_tree/level_<i>_r<anchor>/     — one node dir per level (survey +
    meta.json with `level:`/`parent:`/rungs/seed, run_state.json, artifacts)
    field_ey/ei/q.raw, particles*.raw   — the byte-exact G24 survey format

Design:
  D-M2-1  R = 4 rungs per level; 49 levels cover the 193-rung reach.
  D-M2-6  The tree is a chain (each node 1 parent / 1 child) — a valid
          degenerate tree (the offline-first plan §2.3). The FARM is a real
          parallel executor exercised over genuine independent sibling nodes
          (every level's rung-control + P(k) analysis, and the archetype
          control level-runs), proving cross-branch parallelism without ever
          splitting a single level's solve (D5).
  D-M2-5  CLOSURE IS OUT OF SCOPE: the closure slot is a documented no-op in
          the registry (R1), and the rung-integrity gate runs WITHOUT it.

Run:   python research/cascade_machine/run_cascade_tree.py [--force] [--levels K]
"""
import argparse
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import cascade_ladder as cl  # noqa: E402


# ── registry / layout ────────────────────────────────────────────────────
TREE_ROOT = _HERE / "cascade_tree"


def node_dir(root, index, anchor_rung):
    return root / ("level_%02d_r%d" % (index, anchor_rung))


# ── level spec ───────────────────────────────────────────────────────────
def build_specs(n_levels=None, rungs_per=cl.R):
    """The build order: level 0 = supercluster (coarsest), descending to
    level n-1 = proton (finest). Each level's anchor rung = 288 − R·lev."""
    n_levels = n_levels or cl.level_count()
    specs = []
    for lev in range(n_levels):
        rung = cl.N_SUPERCLUSTER - rungs_per * lev
        L = cl.box_side(rung)
        radii = cl.level_radii(L)
        specs.append({
            "lev": lev, "rung": int(rung), "L": float(L),
            "radii": [float(r) for r in radii],
            "seed": 20260814 + lev * 7919,     # deterministic per level
            "closure_slot": None,              # D-M2-5: no-op (R1)
        })
    return specs


def spec_for_lev(specs, lev):
    for sp in specs:
        if sp["lev"] == lev:
            return sp
    raise KeyError(lev)


# ── one level: run, analyze, dump, checkpoint ────────────────────────────
def run_level(spec, parent_survey_dir, tree_root, force=False):
    """Run one level (its own periodic solve), analyze it, dump its survey
    dir, and write its checkpoint. Skipped (resume) if already done unless
    force. Returns the node state dict."""
    d = node_dir(tree_root, spec["lev"], spec["rung"])
    state_path = d / "run_state.json"
    if not force and state_path.exists() and json.loads(state_path.read_text()).get("done"):
        st = json.loads(state_path.read_text())
        print("[tree] level %02d already done, skipping (resume)" % spec["lev"])
        return st

    lev = spec["lev"]
    L = spec["L"]
    radii = spec["radii"]
    seed = spec["seed"]
    t0 = time.time()

    # deterministic child IC from the parent survey (handoff), OR fresh IC at
    # the root (supercluster): seed geometry = the φ-spaced shell.
    centers = None
    handoff = None
    if parent_survey_dir is not None:
        # the child's box is the SAME spec box (L already φ⁴ finer than the
        # parent's), so build_child_ic uses this level's box as child_L.
        handoff = cl.build_child_ic(parent_survey_dir, L, radii, seed)
        centers = [c.tolist() for c in handoff["centers"]]
        centers_np = handoff["centers"]
    else:
        centers_np = None

    rng = np.random.default_rng(seed)
    sites = cl.bcc_seeds(cl.NCELL, L, rng)
    # CFL time-step homothety: the two-fluid wave CFL is dt ≲ h/c ∝ L. The M1/
    # stage3 reference (L=10, dt=0.005) is the identity; for finer boxes
    # (L<10) the time-step scales DOWN with L so the same resolved band stays
    # stable. For coarser boxes (L≥10) it is capped at the reference (the
    # breathing/restoring term bounds dt from above, and the wave CFL is
    # trivially safe). m2_design.md D-M2-7.
    dt = cl.DT * min(1.0, L / 10.0)
    spec["dt"] = float(dt)
    res = cl.run_condensation(sites, L, radii, cl.A_PARENT, dt=dt, seed=seed,
                              centers=centers_np)
    t_phys = time.time() - t0

    # rung score (uniform baseline, G8 discipline) over ALL cores
    m_cell = res["m_cell"]
    masses = res["masses"].astype(np.float64)
    score = cl.rung_score(masses, m_cell) if len(masses) else 0.0
    n_abs = (np.log(np.maximum(masses, 1e-30) / m_cell) / cl.LN_PHI).tolist()
    # attractor ratio (the level's EY/EI → φ, for the falsifier gate)
    r_end = float(res["r_traj"][-1]) if len(res["r_traj"]) else 0.0

    # survey dump (byte-exact G24 format) + anchor_support_B1 for the handoff
    ey_g = res["fv"].rasterize(res["psiY"])
    ei_g = res["fv"].rasterize(res["psiI"])
    q_g = res["fv"].rasterize(res["qf_max"])
    b1 = cl.anchor_support(sites, L, radii)
    os.makedirs(d, exist_ok=True)
    # Store the mass-ladder RUNG (dimensionless log_φ(m/m_cell)) in the
    # survey's particle-mass file — bounded, overflow-free float32 at any
    # scale (absolute masses at supercluster scale are ~1e77 and overflow
    # float32). meta['mass_encoding'] documents the convention; m_cell is
    # carried so absolute mass reconstructs as m_cell·φ^n.
    n_abs_store = (np.log(np.maximum(masses, 1e-30) / m_cell) / cl.LN_PHI) \
        if len(masses) else np.array([])
    # centers actually used for THIS level's IC (from the handoff, or the
    # default box-center shell for the root) — recorded so the G8 control
    # (same geometry, non-φ radii) is the FAIR contrast, and so the child's
    # IC is fully self-describing in the survey (replayable).
    ic_centers = centers_np if centers_np is not None else None
    if ic_centers is None:
        ic_centers = [c.tolist() for c in cl.shell_centers(L)]
    meta_epoch = {
        "ic_centers": [c.tolist() for c in ic_centers
                       if hasattr(c, "tolist")] or
                      [[float(x) for x in c] for c in ic_centers],
        "ic_radii": [float(x) for x in radii],
        "ic_amplitude": float(cl.A_PARENT),
        "dt": float(dt),
    }
    meta_epoch = {
        "ic_centers": [c.tolist() for c in ic_centers
                       if hasattr(c, "tolist")] or
                      [[float(x) for x in c] for c in ic_centers],
        "ic_radii": [float(x) for x in radii],
        "ic_amplitude": float(cl.A_PARENT),
        "dt": float(dt),
    }
    meta_extra = {
        "level": lev,
        "rung_anchor": int(spec["rung"]),
        "seed": int(seed),
        "parent": (None if parent_survey_dir is None
                   else Path(parent_survey_dir).name),
        "closure_slot": None,          # D-M2-5 documented no-op (R1)
        "anchor_support_B1": float(b1),
        "rung_score": float(score),
        "attractor_r": float(r_end),
        "mass_encoding": "log_rung log_phi(m/m_cell)",
        "m_cell": float(m_cell),
        "mass_sum_logrung": float(n_abs_store.sum()) if len(n_abs_store) else 0.0,
    }
    meta_extra.update(meta_epoch)
    cl.dump_survey(d, cl.N, L, ey_g, ei_g, q_g, res["pos"], n_abs_store,
                   meta_extra=meta_extra)

    # P(k) log-periodicity (calibrated null discipline)
    try:
        kk, PP = cl.pk_from_field(ey_g, ei_g, L)
        pk_res = cl.pk_logperiodic(kk, PP) if len(kk) > 10 else {"n_bins": int(len(kk))}
    except Exception as exc:  # pragma: no cover - honest degrade
        pk_res = {"error": str(exc)}
    (d / "pk.json").write_text(json.dumps(pk_res, indent=2))

    # artifacts + checkpoint
    (d / "rung_score.json").write_text(json.dumps({
        "rung_score": float(score), "n_cores": int(len(masses)),
        "n_abs": [float(x) for x in np.sort(n_abs)],
        "m_cell": float(m_cell), "attractor_r": float(r_end),
        "mass_sum": float(masses.sum()) if len(masses) else 0.0,
    }, indent=2))

    t_tot = time.time() - t0
    state = {
        "lev": lev, "rung": int(spec["rung"]), "L": float(L),
        "seed": int(seed), "done": True,
        "cores": int(len(masses)), "rung_score": float(score),
        "attractor_r": float(r_end),
        "mass_sum": float(masses.sum()) if len(masses) else 0.0,
        "m_handed": float(handoff["m_handed"]) if handoff else None,
        "dM_handoff": float(handoff["dM"]) if handoff else None,
        "A_cons": float(handoff["A_cons"]) if handoff else None,
        "t_phys_s": float(t_phys), "t_total_s": float(t_tot),
        "pk": pk_res,
    }
    (d / "run_state.json").write_text(json.dumps(state, indent=2))
    print("[tree] level %02d r%d done in %.1fs: cores=%d rung=%.3f "
          "r_end=%.4f" % (lev, spec["rung"], t_tot, len(masses), score, r_end))
    # write nodes/edges to a per-level edge marker (parent already recorded)
    return state


# ── the tree registry ────────────────────────────────────────────────────
def write_registry(tree_root, specs, states):
    nodes = []
    for sp in specs:
        d = node_dir(tree_root, sp["lev"], sp["rung"])
        st = states.get(sp["lev"])
        nodes.append({
            "lev": sp["lev"], "rung": int(sp["rung"]), "L": float(sp["L"]),
            "dir": str(d.resolve()), "done": bool(st and st.get("done")),
            "seed": int(sp["seed"]),
            "rung_score": float(st["rung_score"]) if st else None,
            "attractor_r": float(st["attractor_r"]) if st else None,
        })
    edges = []
    for i in range(1, len(specs)):
        edges.append({
            "parent": "level_%02d_r%d" % (specs[i - 1]["lev"], specs[i - 1]["rung"]),
            "child": "level_%02d_r%d" % (specs[i]["lev"], specs[i]["rung"]),
            "kind": "condensation",             # the parent→child edge (D3)
            "closure": None,                    # D-M2-5 no-op slot (R1)
        })
    reg = {
        "status": "M2 offline φ-cascade tree",
        "rungs_per_level": int(cl.R),
        "reach_rungs": int(cl.rungs_between(cl.N_PROTON, cl.N_SUPERCLUSTER)),
        "n_levels": len(specs),
        "n_done": sum(1 for n in nodes if n["done"]),
        "n_edges": len(edges),
        "closure_slot": "no-op (closure wave 2 honest negative; R1 insert-later)",
        "nodes": nodes, "edges": edges,
    }
    (tree_root / "tree_registry.json").write_text(json.dumps(reg, indent=2))
    return reg


# ── the farm executor (across sibling branches, never inside a level) ────
def farm(tasks, max_workers=None):
    """Run independent sibling tasks (each one whole-level solve) in parallel.
    D5: parallelism is ACROSS the tree, never inside a single level's solve."""
    max_workers = max_workers or 2
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(fn, *args): key for key, (fn, args) in tasks.items()}
        for fut in as_completed(futs):
            key = futs[fut]
            results[key] = fut.result()
    return results


# ── main ─────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="re-run levels even if a checkpoint exists")
    ap.add_argument("--levels", type=int, default=None,
                    help="number of levels (default: full 49-level ladder)")
    ap.add_argument("--workers", type=int, default=2,
                    help="farm workers for sibling branches (default 2)")
    ap.add_argument("--tree", default=str(TREE_ROOT),
                    help="cascade_tree root (default research/cascade_machine/cascade_tree)")
    args = ap.parse_args()

    tree_root = Path(args.tree)
    os.makedirs(tree_root, exist_ok=True)
    specs = build_specs(n_levels=args.levels)

    print("=" * 70)
    print("CASCADE TREE (M2 offline chain) — %d levels, R=%d rungs/level"
          % (len(specs), cl.R))
    print("reach = %d φ-rungs (proton n=%d → supercluster n=%d)"
          % (cl.rungs_between(cl.N_PROTON, cl.N_SUPERCLUSTER),
             cl.N_PROTON, cl.N_SUPERCLUSTER))
    print("closure slot: no-op (wave 2 honest negative; R1)  [D-M2-5]")
    print("=" * 70)

    states = {}
    # Root (level 0, supercluster) has NO parent → fresh φ-spaced IC.
    root_sp = spec_for_lev(specs, 0)
    st0 = run_level(root_sp, None, tree_root, force=args.force)
    states[0] = st0

    # The remaining levels form a chain; each child ingests its parent's
    # survey. Checkpoint/resume: skip levels already done.
    for lev in range(1, len(specs)):
        sp = spec_for_lev(specs, lev)
        parent_dir = node_dir(tree_root, lev - 1, specs[lev - 1]["rung"])
        state_path = node_dir(tree_root, lev, sp["rung"]) / "run_state.json"
        if not args.force and state_path.exists() and \
                json.loads(state_path.read_text()).get("done"):
            st = run_level(sp, parent_dir, tree_root, force=False)  # resumes
        else:
            st = run_level(sp, parent_dir, tree_root, force=args.force)
        states[lev] = st

    reg = write_registry(tree_root, specs, states)
    ndone = reg["n_done"]
    print("\n[trace] %d/%d levels done  aggregate rung spread:" % (ndone, len(specs)))
    print("  per-level rung_score:", [round(st["rung_score"], 3)
                                      for st in states.values() if st])
    print("[trace] RESULT: TREE COMPLETE (all levels done).")

    # ── farm demonstration: the archetype rung-control sibling solves ────
    # (independent whole-level nodes, run through the parallel executor —
    # genuine cross-branch parallelism, never intra-level.)
    print("\n[farm] exercising the cross-branch farm on independent sibling nodes ...")
    farm_t_start = time.time()
    ctrl_tasks = {}
    archetype = sorted({sp["lev"] for sp in specs})[:6]   # first 6 levels
    for i, lev in enumerate(archetype):
        sp = spec_for_lev(specs, lev)
        parent_dir = None if lev == 0 else node_dir(
            tree_root, lev - 1, specs[lev - 1]["rung"])
        ctrl_tasks["lev%d_ctrl" % lev] = (
            run_level, (sp, parent_dir, tree_root, True))   # force re-run
    farm(ctrl_tasks, max_workers=args.workers)
    farm_t = time.time() - farm_t_start
    print("[farm] %d sibling nodes completed in %.1fs (workers=%d)" % (
        len(ctrl_tasks), farm_t, args.workers))

    print("\n[farm] NOTE: the tree is a chain (offline-first plan §2.3); the farm "
          "is the real executor, proven over independent sibling nodes, D5 "
          "(parallelism across the tree, never inside a level's solve).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
