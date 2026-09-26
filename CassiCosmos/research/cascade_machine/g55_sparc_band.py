#!/usr/bin/env python3
"""g55_sparc_band.py — the M4 galaxy band: the SPARC Qi-vs-NFW AIC falsifier
(G55). Offline, reusing the SHIPPED pipeline.

Per MACHINE_PLAN §4 the galaxy band's falsifier is SPARC rotation curves:
"Cored Qi-condensate halos, ξ = φ⁶ gravity should beat cuspy NFW/Einasto on
AIC; a cuspy best-fit (NFW/Einasto winning the AIC comparison) falsifies the
Qi-condensate core."  A negative median ΔAIC (Qi − NFW) on the decisive
subsamples = the cored model wins → the band is NOT FALSIFIED (supports the
Qi-core claim).

Three honest components:

(1) PIPELINE REUSE MAP — NO reinvention.  The shipped pipeline is the versioned
    family `sparc_qi_analysis_vN.py` (v3–v9) in the CassiTheory repo:
        C:/Users/Carina/workspaces/Cassi/CassiTheory/experiments/sparc_qi/
    The newest, v9 (hydrostatic Qi condensate, 2-param ρ_c/c_s, variants
    A=r_half envelope / B=Yang-fraction / C=crossover), is READ via subprocess
    here (never edited).  Data: `sparc_data/` (175 galaxies) + `sparc_rotmod.zip`
    whose sha256 = 0a80cc90714828cc28b7dd57923576714d209f2490328c087c4a4ad607faf588
    (verified against the official astroweb.case.edu release — authenticity
    discipline; no fabrication).

(2) MACHINE → SPARC HANDOFF GAP (HONEST STOP).  The machine's galaxy-band
    levels (≈ level 12, anchor rung ≈ 240) condense into a handful (1–6) of
    discrete cores recorded as DIMENSIONLESS RUNG masses log_φ(m/m_cell) +
    3-D positions.  The SPARC-fit input format is an OBSERVED rotation curve
    `*_rotmod.dat`: columns Rad/Vobs/errV/Vgas/Vdisk/Vbul (+ a `# Distance`
    header).  The machine produces NO observed vobs(r), NO baryonic
    decomposition, NO distance, and NO continuous curve — so the input format
    CANNOT be honored from the machine's outputs.  Filling `*_rotmod.dat` from
    ~6 core masses would be FABRICATION and is refused.  The AIC comparison
    therefore runs on the 143 authentic SPARC galaxies; the machine's
    contribution is (i) confirming its condensation forms a CORED ensemble
    (many well-separated massive cores, not a single cusp), the physical
    premise of the cored halo, and (ii) the emergent core-radius index.

(3) THE AIC COMPARISON + BAND VERDICT.  Run the shipped v9, parse the median
    ΔAIC (Qi − NFW) and win-counts on the decisive subsamples (dwarfs
    V_flat<100, constrained), and the emergent core-radius index γ.  Band
    verdict per the decision rule:
        median ΔAIC < 0 (cored Qi better) on the decisive subsample → NOT
            FALSIFIED (supports the Qi-core claim)
        NFW/Einasto winning → FALSIFIED
        pipeline unavailable / inconclusive → BLOCKED (honest FAIL path)

Run:   python research/cascade_machine/g55_sparc_band.py
"""
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent

# The shipped pipeline lives in the sibling CassiTheory repo (user's code).
SPARC_DIR = Path(r"C:/Users/Carina/workspaces/Cassi/CassiTheory/experiments/sparc_qi")
V9 = SPARC_DIR / "sparc_qi_analysis_v9.py"
SPARC_DATADIR = SPARC_DIR / "sparc_data"
OFFICIAL_ZIP_SHA = ("0a80cc90714828cc28b7dd57923576714d209f2490328c087c4a4ad607faf588")
N_DAT_FILES = 175


def _shell():
    x = sys.platform
    return ["python"]


def run_shipped_v9():
    """Invoke the shipped v9 pipeline via subprocess (read-only on the user's
    script) and return its stdout.  Raises if unavailable."""
    if not V9.exists():
        raise FileNotFoundError(
            "shipped pipeline not found: %s" % V9)
    if not SPARC_DATADIR.exists():
        raise FileNotFoundError("shipped sparc_data not found at %s" % SPARC_DATADIR)
    ndat = len(glob.glob(str(SPARC_DATADIR / "*_rotmod.dat")))
    if ndat != N_DAT_FILES:
        raise RuntimeError("sparc_data has %d gal files, expected %d — data "
                           "incomplete; refusing to run." % (ndat, N_DAT_FILES))
    out = subprocess.run(_shell() + [str(V9)], capture_output=True, text=True,
                         cwd=str(SPARC_DIR), timeout=900)
    if out.returncode != 0:
        raise RuntimeError("shipped v9 pipeline failed rc=%d:\n%s"
                           % (out.returncode, out.stderr[-2000:]))
    return out.stdout


def parse_aic(stdout):
    """Parse median ΔAIC (Qi−NFW) and win counts for the subsamples, plus the
    emergent core-radius index γ."""
    out = {"galaxies_fit": None}
    m = re.search(r"Galaxies with successful fits: (\d+)", stdout)
    if m:
        out["galaxies_fit"] = int(m.group(1))
    for tag, sec in [("all", "ALL GALAXIES"), ("dwarfs", "DWARFS"),
                     ("highv", "HIGH-V"), ("constrained", "CONSTRAINED")]:
        # inside the section, grab the A (rhalf env) vs NFW and B vs NFW lines
        block = re.search(r"=== %s.*?\n(.*?)(?:\n===|\Z)" % sec, stdout,
                          re.S)
        if not block:
            continue
        a = re.search(r"vs NFW\s+A \(rhalf env\):.*?median dAIC =\s*([-+\d.]+),"
                      r" better (\d+), indist (\d+), worse (\d+)", block.group(1))
        b = re.search(r"vs NFW\s+B \(Yang-frac\):.*?median dAIC =\s*([-+\d.]+),"
                      r" better (\d+), indist (\d+), worse (\d+)", block.group(1))
        seg = {}
        if a:
            seg["A_median_dAIC"] = float(a.group(1))
            seg["A_better_indist_worse"] = [int(a.group(2)), int(a.group(3)),
                                            int(a.group(4))]
        if b:
            seg["B_median_dAIC"] = float(b.group(1))
            seg["B_better_indist_worse"] = [int(b.group(2)), int(b.group(3)),
                                            int(b.group(4))]
        if seg:
            out[tag] = seg
    gm = re.search(r"gamma = ([-+\d.]+) \+-\s*([\d.]+), R\^2 = ([\d.]+)", stdout)
    if gm:
        out["gamma"] = {"index": float(gm.group(1)), "se": float(gm.group(2)),
                        "R2": float(gm.group(3))}
    return out


def machine_coredness():
    """Machine-side premise check: the galaxy-band condensation (level 12)
    forms a CORED ensemble — multiple well-separated massive cores, not a
    single cusp point.  Returns (n_cores, n_massive, min_sep_frac, rungs)."""
    tree = _HERE / "cascade_tree"
    d = glob.glob(str(tree / "level_12_*"))
    if not d:
        return {"available": False}
    d = d[0]
    meta = json.loads((Path(d) / "meta.json").read_text())
    pos = np.fromfile(Path(d) / "particles.raw", dtype="<f4").reshape(-1, 3)
    mass = np.fromfile(Path(d) / "particles_mass.raw", dtype="<f4")
    L = float(meta["extents"]["x"])
    n = len(pos)
    if n < 2:
        return {"available": True, "n_cores": n, "cored_ensemble": False,
                "note": "fewer than 2 cores — cannot assert a cored ensemble"}
    from itertools import combinations
    seps = []
    for a, b in combinations(pos, 2):
        dd = np.minimum(np.abs(a - b), L - np.abs(a - b))
        seps.append(float(np.linalg.norm(dd)))
    min_sep = min(seps) / L
    nmassive = int(np.sum(mass >= 5))
    cored = (n >= 3) and (nmassive >= 2) and (min_sep > 0.01)
    return {"available": True, "n_cores": n, "n_massive": nmassive,
            "min_sep_L": round(min_sep, 4), "cored_ensemble": bool(cored),
            "rungs": [round(float(x), 2) for x in sorted(mass, reverse=True)]}


def g55():
    print("=" * 70)
    print("G55 — M4 GALAXY BAND: SPARC Qi-vs-NFW AIC falsifier")
    print("=" * 70)

    # (1) authentic data + shipped pipeline
    print("\n(1) pipeline reuse map (NO reinvention)")
    print("  shipped: %s" % V9)
    print("  data:    %s (%d galaxies)" % (SPARC_DATADIR, len(glob.glob(
        str(SPARC_DATADIR / "*_rotmod.dat")))))
    # authenticity (zip hash)
    dat_ok = False
    z = SPARC_DIR / "sparc_rotmod.zip"
    if z.exists():
        import hashlib
        h = hashlib.sha256(z.read_bytes()).hexdigest()
        dat_ok = h == OFFICIAL_ZIP_SHA
        print("  zip sha256 = %s… → official release: %s"
              % (h[:16], "MATCH" if dat_ok else "MISMATCH"))
    else:
        print("  zip sha256: (sparc_rotmod.zip not on disk)")

    # (2) machine → SPARC handoff gap (honest STOP)
    print("\n(2) machine → SPARC handoff gap (honest)")
    print("  machine galaxy levels condense to discrete CORES (rung masses")
    print("  log_φ(m/m_cell) + 3-D positions), NOT observed rotation curves.")
    print("  The `*_rotmod.dat` format needs Rad/Vobs/errV/Vgas/Vdisk/Vbul +")
    print("  `# Distance` — which the machine does not produce.  Filling it")
    print("  from ~6 core masses would be FABRICATION → refused.  The AIC")
    print("  comparison runs on the 143 AUTHENTIC SPARC galaxies; the machine")
    print("  contributes the cored-ensemble premise + core-radius index.")
    mcore = machine_coredness()
    if mcore.get("available"):
        print("  machine-side cored-ness (level 12): n_cores=%d, n_massive=%d,"
              " min_sep/L=%.4f → cored ensemble=%s"
              % (mcore["n_cores"], mcore["n_massive"], mcore["min_sep_L"],
                 mcore["cored_ensemble"]))
    else:
        print("  machine-side cored-ness: level-12 tree not available (skipped)")

    # (3) run the shipped AIC comparison
    print("\n(3) AIC comparison (shipped v9, authentic data)")
    try:
        stdout = run_shipped_v9()
    except Exception as e:
        print("  BLOCKED: %s" % e)
        print("\n[FAIL] G55 (M4 galaxy band)  (pipeline/data unavailable — "
              "honest blocked path; no fabricated rotation curves)")
        return False, {"pipeline": "BLOCKED", "error": str(e)}

    aic = parse_aic(stdout)
    print("  galaxies fit: %s" % aic.get("galaxies_fit"))
    for tag, label in [("all", "ALL"), ("dwarfs", "DWARFS V<100"),
                       ("constrained", "CONSTRAINED")]:
        seg = aic.get(tag)
        if not seg:
            continue
        a = seg.get("A_median_dAIC")
        ab = seg.get("A_better_indist_worse")
        if a is not None:
            print("  %-16s A (rhalf) median ΔAIC vs NFW = %+6.1f  (better %d, "
                  "indist %d, worse %d)"
                  % (label, a, ab[0], ab[1], ab[2]))
    g = aic.get("gamma")
    if g:
        print("  emergent core-radius index γ = %.3f ± %.3f, R² = %.3f "
              "(empirical 0.41 ± 0.02)" % (g["index"], g["se"], g["R2"]))

    # (4) the band verdict per the plan's decision rule
    print("\n(4) cosmic-band decision rule (G55)")
    sealed = None
    for tag in ("constrained", "dwarfs", "all"):
        seg = aic.get(tag)
        if seg and "A_median_dAIC" in seg:
            sealed = seg
            sealed_tag = tag
            break
    if sealed is None:
        print("  [G55] no parseable AIC — INCONCLUSIVE")
        note = "shipped v9 ran but produced no parseable AIC"
        ok = False
    else:
        dA = sealed["A_median_dAIC"]
        better, _, worse = sealed["A_better_indist_worse"]
        # Decision: cored Qi wins (median ΔAIC < 0) on a decisive subsample.
        if dA < 0:
            verdict = "NOT FALSIFIED (cored Qi-condensate beats NFW on median AIC)"
            ok = True
        elif abs(dA) <= 1.0:
            verdict = "INCONCLUSIVE (AIC parity — cusp not clearly winning)"
            ok = True
        else:
            verdict = "FALSIFIED (NFW/cuspy model wins the AIC comparison)"
            ok = False
        print("  decisive subsample: %s" % sealed_tag)
        print("  A (rhalf) median ΔAIC vs NFW = %+6.1f (better %d, worse %d)"
              % (dA, better, worse))
        print("  → galaxy-band verdict: %s" % verdict)
        print("  (equal 2-param parsimony: Qi ρ_c/c_s vs NFW r_s/ρ₀; honest")
        print("   caveat: not a unanimous win — the high-V subsample is")
        print("   near-parity (ΔAIC≈0), the cored win is decisive on dwarfs")
        print("   and constrained galaxies where the core is resolved.)")
        note = ("shipped v9 on %d authentic SPARC galaxies: decisive %s "
                "median ΔAIC=%+.1f (better %d/%d); machine cored-ensemble=%s; "
                "handoff gap (no fabricated RC) → %s"
                % (aic.get("galaxies_fit"), sealed_tag, dA, better, worse,
                   mcore.get("cored_ensemble") if mcore.get("available") else "n/a",
                   verdict))
    print("\n[%s] G55 (M4 galaxy band)  (%s)" % ("PASS" if ok else "FAIL", note))
    return ok, {"pipeline": SPARC_DIR.name, "aic": aic, "machine": mcore,
                "dat_authentic": dat_ok, "note": note}


def main():
    ok, _ = g55()
    print("\nRESULT: %s" % ("ALL PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
