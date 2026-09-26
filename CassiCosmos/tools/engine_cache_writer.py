#!/usr/bin/env python3
"""engine_cache_writer.py — Phase 1: engine states into the training cache.

Connects to the Cassi Mind Engine TCP bridge (line-delimited JSON on
127.0.0.1:7599; scripts/cassi_mind_engine.gd), runs seeded deposit families,
samples midplane ey/ei frames at a stride cadence, and writes RAW per-family
[T, 32, 32] float32 .pt files plus a collection metadata JSON.

Windowing, per-family z-scoring, and train/val splits are deliberately NOT
done here: CassiAI/build_physics_cache.py is the format authority and
consumes these raw files (family name = first "_" token of the filename).
The final cache is therefore byte-compatible with the turbulence cache by
construction instead of by reimplementation.

Gates (per family):
  G1 charge-exact:  |sum(ey+ei) - sum(cy+ci)| / |sum(cy+ci)| <= 1e-3 on the
                    first post-IC frame (the TSC scatter pin + the shader's
                    conservative conversion term).
  G2 finite:        every decoded frame all-finite (NaN-loud-fail).
  G3 shape:         decoded readout length == grid_n^3.
  G4 liveness:      max_eps2 telemetry recorded (a fully dormant family is
                    flagged, not silently dropped).

Usage:
  python tools/engine_cache_writer.py --runs 4 --frames 640
  python tools/engine_cache_writer.py --self-test
"""

import argparse
import base64
import json
import random
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import torch

PHI = 1.618033988749895
DT = 0.005  # engine default (scenes/mind_engine_cache.tscn does not override)


def decode_b64(b64: str) -> np.ndarray:
    """Decode a base64 little-endian float32 payload (Marshalls.raw_to_base64)."""
    return np.frombuffer(base64.b64decode(b64), dtype="<f4")


class BridgeClient:
    """Minimal line-delimited JSON client for the mind engine bridge."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7599,
                 timeout: float = 120.0):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)
        self._rf = self._sock.makefile("rb")

    def request(self, obj: dict) -> dict:
        self._sock.sendall(json.dumps(obj).encode() + b"\n")
        resp = self._rf.readline()
        if not resp:
            raise ConnectionError("engine closed the connection")
        return json.loads(resp.decode())

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


def midplane(flat: np.ndarray, n: int) -> np.ndarray:
    """Midplane slice (z = n//2) of an x-major flat grid; returns [n, n].

    Engine flat index: i = gx*N*N + gy*N + gz (cassi_mind_engine.gd), so
    axis 0 = x, axis 1 = y, axis 2 = z; grid[:, :, n//2] is the z-midplane.
    """
    grid = flat.reshape(n, n, n)
    return np.ascontiguousarray(grid[:, :, n // 2])


def make_deposits(rng: random.Random, k: int = 10) -> list[dict]:
    """Seeded IC: 1/3 attractor-ratio (cy=phi*ci), 2/3 off-ratio, mixed sigma."""
    deps = []
    for _ in range(k):
        x, y, z = (rng.uniform(-0.8, 0.8) for _ in range(3))
        sigma = rng.choice([0.5, 1.0, 1.5, 2.0])
        if rng.random() < 1.0 / 3.0:
            ci = rng.uniform(0.3, 1.0)
            cy = PHI * ci  # attractor-ratio (dormant control deposits)
        else:
            cy = rng.uniform(-1.0, 1.0)
            ci = rng.uniform(-1.0, 1.0)
        deps.append({"x": x, "y": y, "z": z, "cy": cy, "ci": ci, "sigma": sigma})
    return deps


def run_family(client: BridgeClient, tag: str, deps: list[dict], grid_n: int,
               frames: int, stride: int, tele: dict) -> tuple[np.ndarray, np.ndarray]:
    """clear -> deposits -> step 1 (flush+step) -> sample `frames` readouts.

    Returns (ey_stack, ei_stack), each [frames, grid_n, grid_n] float32.
    Raises RuntimeError on any gate failure (NaN-loud-fail convention).
    """
    n3 = grid_n ** 3
    client.request({"cmd": "clear"})
    for d in deps:
        client.request({"cmd": "deposit", **d})
    charge_in = sum(d["cy"] + d["ci"] for d in deps)
    client.request({"cmd": "step", "n": 1})  # flushes deposits + 1 PDE step

    ey_frames: list[np.ndarray] = []
    ei_frames: list[np.ndarray] = []
    max_eps2 = 0.0
    for f in range(frames):
        if f > 0:
            client.request({"cmd": "step", "n": stride})
        ro = client.request({"cmd": "readout"})
        ey = decode_b64(ro["ey_b64"])
        ei = decode_b64(ro["ei_b64"])
        if ey.size != n3 or ei.size != n3:  # G3
            raise RuntimeError(f"[{tag}] readout length mismatch: {ey.size} != {n3}")
        if not (np.isfinite(ey).all() and np.isfinite(ei).all()):  # G2
            raise RuntimeError(f"[{tag}] non-finite field at frame {f}")
        if f == 0:  # G1 charge-exact
            charge_out = float(np.sum(ey) + np.sum(ei))
            rel = abs(charge_out - charge_in) / max(abs(charge_in), 1e-12)
            tele["charge_in"] = charge_in
            tele["charge_out"] = charge_out
            tele["charge_rel_err"] = rel
            if rel > 1e-3:
                raise RuntimeError(f"[{tag}] charge-exact gate FAILED: rel err {rel:.3e}")
        eps = ey - PHI * ei
        max_eps2 = max(max_eps2, float(np.max(eps * eps)))
        ey_frames.append(midplane(ey, grid_n))
        ei_frames.append(midplane(ei, grid_n))

    st = client.request({"cmd": "state"})
    tele["mean_ey"] = st["mean_ey"]
    tele["mean_ei"] = st["mean_ei"]
    tele["max_eps2"] = max_eps2
    tele["final_step"] = st["step"]
    tele["final_t"] = st["t"]
    tele["dormant"] = max_eps2 < 1e-12  # G4 flag
    return np.stack(ey_frames), np.stack(ei_frames)


def self_test(grid_n: int) -> int:
    """Offline round-trip: decode + midplane indexing on synthetic data."""
    n3 = grid_n ** 3
    ey = np.arange(n3, dtype="<f4")
    b64 = base64.b64encode(ey.tobytes()).decode()
    back = decode_b64(b64)
    assert back.size == n3, back.size
    assert np.array_equal(back, ey), "decode round-trip mismatch"
    m = midplane(back, grid_n)
    assert m.shape == (grid_n, grid_n), m.shape
    grid = back.reshape(grid_n, grid_n, grid_n)
    assert np.array_equal(m, grid[:, :, grid_n // 2]), "midplane indexing mismatch"
    print(f"[self-test] PASS: decode+midplane round-trip (n={grid_n}, plane {m.shape})")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Collect mind-engine field frames into raw family .pt files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=7599)
    p.add_argument("--runs", type=int, default=4, help="seeded IC runs (2 families each: ey, ei)")
    p.add_argument("--frames", type=int, default=640, help="frames per family (>= 8)")
    p.add_argument("--stride", type=int, default=1, help="steps between sampled frames")
    p.add_argument("--grid-n", type=int, default=32)
    p.add_argument("--deposits", type=int, default=10)
    p.add_argument("--seed", type=int, default=20260815)
    p.add_argument("--fields-dir", default=None,
                   help="raw-fields output dir (default: %TEMP%/cassi_engine_fields)")
    p.add_argument("--self-test", action="store_true",
                   help="offline decode/slice round-trip, no connection")
    args = p.parse_args()

    if args.self_test:
        return self_test(args.grid_n)
    if args.frames < 8:
        print("[writer] ERROR: --frames must be >= 8 (builder win_len)")
        return 2

    fields_dir = Path(args.fields_dir or (Path(tempfile.gettempdir()) / "cassi_engine_fields"))
    if fields_dir.exists():
        shutil.rmtree(fields_dir, ignore_errors=True)
    fields_dir.mkdir(parents=True, exist_ok=True)

    client = BridgeClient(args.host, args.port)
    meta = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "grid_n": args.grid_n, "dt": DT, "stride": args.stride,
        "frames": args.frames, "runs": args.runs, "seed": args.seed,
        "runs": [],
    }
    runs_ok = 0
    try:
        pong = client.request({"cmd": "ping"})
        if not pong.get("ok"):
            print(f"[writer] ERROR: ping failed: {pong}")
            return 1
        print(f"[writer] connected: engine step={pong.get('step')} t={pong.get('t')}")

        for i in range(args.runs):
            tag = f"r{i}"
            seed = args.seed + i * 1009
            rng = random.Random(seed)
            deps = make_deposits(rng, args.deposits)
            tele = {"family_seed": seed, "deposits": deps}
            t0 = time.time()
            try:
                eyf, eif = run_family(client, tag, deps, args.grid_n,
                                      args.frames, args.stride, tele)
            except RuntimeError as e:
                print(f"[writer] run {tag} FAILED: {e}")
                meta["runs"].append({"tag": tag, "status": "failed",
                                     "error": str(e), "family_seed": seed,
                                     "deposits": deps})
                continue
            torch.save(torch.from_numpy(eyf), fields_dir / f"{tag}ey.pt")
            torch.save(torch.from_numpy(eif), fields_dir / f"{tag}ei.pt")
            meta["runs"].append({"tag": tag, "status": "ok",
                                 "telemetry": {k: tele[k] for k in tele if k != "deposits"},
                                 "family_seed": seed, "deposits": deps})
            runs_ok += 1
            dt_run = time.time() - t0
            print(f"[writer] run {tag}: ok in {dt_run:.1f}s — charge rel {tele['charge_rel_err']:.2e}, "
                  f"max_eps2 {tele['max_eps2']:.4g}, dormant={tele['dormant']}, "
                  f"final step {tele['final_step']}")
    finally:
        client.close()

    if runs_ok < 2:
        print("[writer] ERROR: fewer than 2 usable runs — aborting (see meta)")
        return 1

    builder_cmd = (
        "python CassiAI/build_physics_cache.py "
        f"--fields-dir {fields_dir} "
        "--output CassiAI/datasets/physics_cache_engine.pt "
        "--d 1024 --win-len 8 --max-per-file 625 --val-frac 0.1 --seed 42"
    )
    meta["runs_ok"] = runs_ok
    meta["fields_dir"] = str(fields_dir)
    meta["builder_cmd"] = builder_cmd
    meta_path = fields_dir / "collection_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"[writer] done: {2 * runs_ok} family files -> {fields_dir}")
    print(f"[writer] meta: {meta_path}")
    print(f"[writer] next: {builder_cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
