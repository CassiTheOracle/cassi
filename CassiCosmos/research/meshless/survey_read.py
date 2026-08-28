#!/usr/bin/env python3
"""Cassi space-sim survey reader — loads a survey snapshot directory into
numpy for the theory pipelines (P(k) log-periodic search, cascade analysis).

Usage:  python research/meshless/survey_read.py <survey_dir>
(where <survey_dir> is under the repo's _diag/, e.g. _diag/survey_20260813_043322)

A snapshot directory (written by scripts/cassi_survey.gd) contains:
  meta.json     — grid_N, extents, particle_count, step/time, arm mode
  field_ey.raw  — float32 little-endian, grid_N^3 values (EY field)
  field_ei.raw  — float32 little-endian, grid_N^3 values (EI field)
  field_q.raw   — float32 little-endian, grid_N^3 values (Qi coherence; optional)
  particles.raw — float32 little-endian, xyz per particle (positions only)

GATE G24 (exits non-zero on failure):
  1. ey/ei shapes match meta (grid_N^3 each) and are finite;
  2. the particle count in particles.raw matches meta.particle_count;
  3. dumped field_ey.raw equals _diag/survey_ref.raw EXACTLY (byte comparison),
     the direct reference read written by scripts/verify_survey.gd from the
     same frozen sim state.
"""
import json
import sys
from pathlib import Path

import numpy as np


def load_float32_raw(path: Path, shape):
    """Load a float32 LE raw file, raising if its size mismatches `shape`."""
    arr = np.fromfile(path, dtype="<f4")
    expect = int(np.prod(shape))
    if arr.size != expect:
        raise ValueError(
            f"{path.name}: expected {expect} floats (shape {shape}), got {arr.size}"
        )
    return arr.reshape(shape)


def main() -> int:
    if len(sys.argv) < 2:
        print("[survey_read] usage: survey_read.py <survey_dir>")
        return 2

    repo = Path(__file__).resolve().parents[2]  # research/meshless -> repo root
    arg = Path(sys.argv[1])
    survey = arg if arg.is_absolute() else (Path.cwd() / arg)
    if not survey.exists():
        # Fall back to repo/_diag/<arg> for the common invocation form.
        alt = repo / "_diag" / arg
        if alt.exists():
            survey = alt
        else:
            print(f"[survey_read] survey dir not found: {survey} (tried {alt})")
            return 1

    meta_path = survey / "meta.json"
    if not meta_path.exists():
        print(f"[G24] RESULT FAIL — meta.json not found at {survey}")
        return 1
    meta = json.loads(meta_path.read_text())

    N = int(meta["grid_N"])
    shape = (N, N, N)
    fail: list[str] = []

    # ── 1. ey / ei shapes + finiteness ───────────────────────────────────
    try:
        ey = load_float32_raw(survey / "field_ey.raw", shape)
        ei = load_float32_raw(survey / "field_ei.raw", shape)
    except ValueError as exc:
        fail.append(f"ey/ei shape mismatch: {exc}")
        ey = ei = None

    q = None
    if (survey / "field_q.raw").exists():
        try:
            q = load_float32_raw(survey / "field_q.raw", shape)
        except ValueError as exc:
            fail.append(f"field_q shape mismatch: {exc}")

    if ey is not None and not np.isfinite(ey).all():
        fail.append(f"ey has {int((~np.isfinite(ey)).sum())} non-finite values")
    if ei is not None and not np.isfinite(ei).all():
        fail.append(f"ei has {int((~np.isfinite(ei)).sum())} non-finite values")
    if q is not None and not np.isfinite(q).all():
        fail.append(f"field_q has {int((~np.isfinite(q)).sum())} non-finite values")

    # ── 2. particle count ────────────────────────────────────────────────
    np_count = int(meta.get("particle_count", 0))
    parts = None
    pr = survey / "particles.raw"
    if pr.exists():
        raw = np.fromfile(pr, dtype="<f4")
        if raw.size == np_count * 3:
            parts = raw.reshape(np_count, 3)
        else:
            fail.append(
                f"particles.raw has {raw.size} floats; expected {np_count * 3}"
            )
            parts = None
    elif np_count != 0:
        fail.append(f"particles.raw missing but meta.particle_count={np_count}")

    # ── 3. dumped ey == _diag/survey_ref.raw (byte-exact) ────────────────
    ref = repo / "_diag" / "survey_ref.raw"
    if not ref.exists():
        fail.append(f"_diag/survey_ref.raw not found at {ref}")
    else:
        ref_bytes = ref.read_bytes()
        ey_bytes = (survey / "field_ey.raw").read_bytes()
        if ref_bytes != ey_bytes:
            fail.append(
                f"field_ey.raw != _diag/survey_ref.raw "
                f"({len(ey_bytes)} vs {len(ref_bytes)} bytes)"
            )

    # ── Summary ──────────────────────────────────────────────────────────
    ext = meta.get("extents", {})
    print("=" * 60)
    print(f"[survey_read] snapshot: {survey}")
    print(f"  grid_N              : {N} (shape {shape})")
    print(f"  extents             : x={ext.get('x'):.5f} y={ext.get('y'):.5f} "
          f"z={ext.get('z'):.5f}")
    print(f"  particle_count      : {np_count}")
    print(f"  step / time         : {meta.get('step')} / {meta.get('time')}")
    print(f"  arm                 : mode={meta.get('gravity_mode')} "
          f"({meta.get('gravity_mode_name')})  meshless={meta.get('meshless_mode')}")
    if ey is not None:
        print(f"  ey  min/max/mean    : {ey.min():.6g} / {ey.max():.6g} / "
              f"{ey.mean():.6g}")
    if ei is not None:
        print(f"  ei  min/max/mean    : {ei.min():.6g} / {ei.max():.6g} / "
              f"{ei.mean():.6g}")
    if q is not None:
        print(f"  q   min/max/mean    : {q.min():.6g} / {q.max():.6g} / "
              f"{q.mean():.6g}")
    if parts is not None and parts.size:
        print(f"  particle xyz span   : x[{parts[:,0].min():.3g},{parts[:,0].max():.3g}] "
              f"y[{parts[:,1].min():.3g},{parts[:,1].max():.3g}] "
              f"z[{parts[:,2].min():.3g},{parts[:,2].max():.3g}]")

    # ── Gate verdict ─────────────────────────────────────────────────────
    if fail:
        for f in fail:
            print(f"[G24]   FAIL — {f}")
        print("[G24] RESULT FAIL")
        return 1
    print("=" * 60)
    print("[G24] RESULT PASS — ey/ei shapes + finiteness, particle count, "
          "and byte-exact reference all OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
