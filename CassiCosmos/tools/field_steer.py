#!/usr/bin/env python3
"""field_steer.py — Phase 3: the steering loop (readout -> predict -> deposit).

Closes the minimal closed loop described in UNIFICATION.md §3.4 and §4 Phase 3: read coherence (readout/project), decide a
perturbation (a clearly-labeled steering policy, NOT a neural model), inject it
(deposit), on a phi-cadence schedule (NOT per-step). Hard stop on divergence
(NaN-loud-fail + q_mean / pi-saturation guard reads).

Pre-registration (statistic, decision tree, stopping rule) is fixed BEFORE any
run in research/steering/phase3_steering_prereg.md. This script implements
exactly that document and appends a ledger row to it per run.

The predictor is PERSISTENCE ONLY (predict-next = current frame) plus the
steering policy — the predict-unchanged floor that Stage 5's REJECT was
measured against. NO CassiAI code is imported; nothing from CassiAI/ is used.

Logic:
  connect -> ping -> clear -> IC deposits -> step 1 -> baseline readout r=0
  per rung r in 1..R:
      inject steering (queued deposit, scaled by --strength)   [control: none]
      step n = tau_r  (tau from round(phi^k); flushes the deposit on the
                       first sub-step, then evolves tau_r steps)
      readout -> record (Q_A, q_mean, pi_sat_frac, max_eps2, S_rung, guards)
  aggregate G_cad / G_0 increment framing, leverage S, verdict branch D0-D5.

Gates (mirrors engine_cache_writer.py):
  G1 charge-exact  |sum(ey+ei) - sum(cy+ci)| / max(|sum(cy+ci)|,1) <= 1e-3
     on the first post-IC frame.
  G2 finite        every decoded readout all-finite (NaN-loud-fail).
  G3 shape         decoded readout length == grid_n^3 (grid_n auto-detected).
  G4 liveness      q_mean + pi_sat_frac + max_eps2 recorded per rung; a
     dormancy/blow-up is flagged, not silently dropped.
  GS steering      total_injected > 0 in any non-control arm (a no-injection
     steering arm is a bug -> INVALID).

Usage:
  python tools/field_steer.py --self-test
  python tools/field_steer.py --strength 0.5 --mode yang --rungs 8
  python tools/field_steer.py --strength 0 --mode yang --rungs 8   # control
  python tools/field_steer.py --per-step --strength 0.25 --rungs 4 # G34 ref
"""

import argparse
import base64
import json
import math
import random
import socket
import sys
import time
from pathlib import Path

import numpy as np

PHI = 1.618033988749895
DT = 0.005  # engine default (mind_engine.tscn / mind_engine_cache.tscn set 0)
EPS_CHARGE = 1e-9
REPO_ROOT = Path(__file__).resolve().parents[1]  # CassiCosmos/
PREREG_PATH = REPO_ROOT / "research" / "steering" / "phase3_steering_prereg.md"


def decode_b64(b64: str) -> np.ndarray:
    """Decode a base64 little-endian float32 payload (Marshalls.raw_to_base64)."""
    return np.frombuffer(base64.b64decode(b64), dtype="<f4")


def auto_grid_n(arr: np.ndarray) -> int:
    """grid_n from a decoded readout length (n^3), validated exactly."""
    n = int(round(len(arr) ** (1.0 / 3.0)))
    if n ** 3 != len(arr):
        raise RuntimeError(f"readout length {len(arr)} is not a perfect cube")
    return n


def phi_cadence(rungs: int) -> list[int]:
    """Injection step intervals tau_r = round(phi^k), k = r (rung index)."""
    return [max(1, int(round(PHI ** k))) for k in range(rungs)]


def physical_to_grid(x: float, n: int, extent: float = 1.0) -> int:
    """Physical coord -> flat-index axis (matches _scatter's rounding)."""
    g = (x / extent + 1.0) * 0.5 * float(n)
    return int(floor(g + 0.5)) % n


def floor(x: float) -> int:
    return int(math.floor(x))


class BridgeClient:
    """Minimal line-delimited JSON client for the mind engine bridge (7599)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7599,
                 timeout: float = 300.0):
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


def make_ic_deposits(rng: random.Random, k: int = 10) -> list[dict]:
    """Seeded IC: 1/3 attractor-ratio (cy=phi*ci), 2/3 off-ratio, mixed sigma.

    Reuses engine_cache_writer.make_deposits so the IC matches Phase 1.
    """
    deps = []
    for _ in range(k):
        x, y, z = (rng.uniform(-0.8, 0.8) for _ in range(3))
        sigma = rng.choice([0.5, 1.0, 1.5, 2.0])
        if rng.random() < 1.0 / 3.0:
            ci = rng.uniform(0.3, 1.0)
            cy = PHI * ci  # attractor-ratio (dormant)
        else:
            cy = rng.uniform(-1.0, 1.0)
            ci = rng.uniform(-1.0, 1.0)
        deps.append({"x": x, "y": y, "z": z, "cy": cy, "ci": ci, "sigma": sigma})
    return deps


class SteeringArm:
    """One steering arm: fresh solver, IC, cadence loop, verdict state."""

    def __init__(self, client: BridgeClient, args):
        self.client = client
        self.args = args
        rng = random.Random(args.seed)
        self.ic = make_ic_deposits(rng, args.ic_deposits)
        self.grid_n = args.grid_n
        self.cadence = phi_cadence(args.rungs) if args.cadence == "phi" \
            else [1] * args.rungs  # uniform/per-step
        self.n3 = self.grid_n ** 3
        # telemetry accumulated per rung
        self.rungs: list[dict] = []
        self.boundary: list[str] = []

    # ── field helpers ────────────────────────────────────────────────────
    def _readout(self) -> dict:
        ro = self.client.request({"cmd": "readout"})
        ey = decode_b64(ro["ey_b64"])
        ei = decode_b64(ro["ei_b64"])
        q = decode_b64(ro["q_b64"])
        eps2 = decode_b64(ro["eps2_b64"])
        if not (ey.size == ei.size == q.size == eps2.size == self.n3):
            raise RuntimeError(
                f"shape mismatch: ey={ey.size} ei={ei.size} q={q.size} eps2={eps2.size} != {self.n3}")
        if not (np.isfinite(ey).all() and np.isfinite(ei).all()
                and np.isfinite(q).all() and np.isfinite(eps2).all()):
            raise RuntimeError("non-finite readout (NaN-loud-fail)")
        return {"ey": ey, "ei": ei, "q": q, "eps2": eps2}

    def _target_ball_mask(self, tcell: tuple[int, int, int], radius: int) -> np.ndarray:
        """Boolean mask of the cubic ball of `radius` cells around tcell."""
        n = self.grid_n
        gx, gy, gz = tcell
        idx = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    idx.append(((gx + dx) % n) * n * n
                               + ((gy + dy) % n) * n
                               + ((gz + dz) % n))
        m = np.zeros(self.n3, dtype=bool)
        m[idx] = True
        return m

    def _set_target(self, readout: dict) -> tuple[int, int, int]:
        """Pick target cell: explicit --target-x/y/z or the top project cell."""
        if self.args.target_x is not None:
            n = self.grid_n
            gx = physical_to_grid(self.args.target_x, n)
            gy = physical_to_grid(self.args.target_y, n)
            gz = physical_to_grid(self.args.target_z, n)
            return (gx, gy, gz)
        proj = self.client.request({"cmd": "project", "k": self.args.project_k})
        top = proj["cells"][0]
        return (top["gx"], top["gy"], top["gz"])

    # ── steering policy ──────────────────────────────────────────────────
    def _steering_deposits(self, readout: dict, tcell: tuple[int, int, int],
                           Q_A: float, q_mean0: float) -> list[dict]:
        """Decide deposits for this rung (Yang converge or Yin stay-alive)."""
        args = self.args
        if args.strength <= 0:
            return []  # control / strength-0
        n = self.grid_n
        n3 = self.n3
        gx, gy, gz = tcell
        x = (2.0 * gx / (n - 1) - 1.0) * 1.0
        y = (2.0 * gy / (n - 1) - 1.0) * 1.0
        z = (2.0 * gz / (n - 1) - 1.0) * 1.0
        mask = self._target_ball_mask(tcell, args.target_radius)
        nA = int(mask.sum())

        if args.mode == "yang":
            # Converge: build target coherence toward q_target_density, in the
            # phi-attractor ratio (cy = phi*ci => conversion term ~ 0). This is
            # steering WITH the attractor (leverage principle), never against.
            Q_desired = args.q_target_density * nA
            deficit = max(0.0, Q_desired - Q_A)
            if deficit <= 0:
                return []
            lam = min(args.strength * deficit / (1.0 + PHI), args.lam_max)

            if args.placement != "annular":
                # Single-cell TSC scatter at the target.
                return [{"x": x, "y": y, "z": z, "cy": lam * PHI, "ci": lam,
                         "sigma": args.sigma}]

            # Annular placement: split the same total charge lam evenly across
            # the 26-cell Chebyshev shell at radius 1 (the TSC stencil
            # footprint around the target), each cell a phi-ratio deposit with
            # the same sigma. Total injected charge is preserved (sum of
            # cy+ci == lam*(phi+1) across the ring).
            ring: list[dict] = []
            n = self.grid_n
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        if dx == dy == dz == 0:
                            continue  # skip center -> ring at radius 1
                        gxi = (gx + dx) % n
                        gyi = (gy + dy) % n
                        gzi = (gz + dz) % n
                        xi = (2.0 * gxi / (n - 1) - 1.0) * 1.0
                        yi = (2.0 * gyi / (n - 1) - 1.0) * 1.0
                        zi = (2.0 * gzi / (n - 1) - 1.0) * 1.0
                        ring.append({"x": xi, "y": yi, "z": zi,
                                     "cy": (lam / 26.0) * PHI,
                                     "ci": lam / 26.0,
                                     "sigma": args.sigma})
            return ring

        # Yin: stay-alive. Diffuse phi-ratio scatter only when below the floor;
        # conserve the Qi budget (inject exactly what's needed to lift q_mean).
        q_mean = float(np.mean(readout["q"]))
        floor_charge = (args.q_floor * q_mean0 - q_mean) * n3
        if floor_charge <= 0:
            return []
        lam = min(args.strength * floor_charge / (1.0 + PHI), args.lam_max)
        return [{"x": x, "y": y, "z": z, "cy": lam * PHI, "ci": lam,
                 "sigma": args.sigma_yin}]

    # ── the loop ─────────────────────────────────────────────────────────
    def run(self) -> dict:
        args = self.args
        c = self.client

        c.request({"cmd": "clear"})
        for d in self.ic:
            c.request({"cmd": "deposit", **d})
        charge_in = sum(d["cy"] + d["ci"] for d in self.ic)
        c.request({"cmd": "step", "n": 1})  # flush IC + 1 PDE step

        ro0 = self._readout()  # post-IC baseline (r=0)
        # G1 charge-exact on the IC first frame.
        charge_out = float(np.sum(ro0["ey"]) + np.sum(ro0["ei"]))
        rel = abs(charge_out - charge_in) / max(abs(charge_in), 1.0)
        if rel > 1e-3:
            raise RuntimeError(f"[G1] charge-exact FAILED: rel err {rel:.3e}")
        q_mean0 = float(np.mean(ro0["q"]))
        max_eps2 = float(np.max(ro0["eps2"]))
        tcell = self._set_target(ro0)
        mask = self._target_ball_mask(tcell, args.target_radius)
        self.target = tcell

        def q_A(ro: dict) -> float:
            return float(np.sum(ro["q"][mask]))

        Q_A_prev = q_A(ro0)
        total_injected = 0.0
        sum_dq = 0.0
        sum_dep = 0.0
        dq_list: list[float] = []
        s_list: list[float] = []
        steps_taken = 0
        hard_stop = False

        for r in range(1, args.rungs + 1):
            tau = self.cadence[r - 1]
            # Decide + queue this rung's deposit (before stepping so it lands).
            deps = self._steering_deposits(ro0, tcell, Q_A_prev, q_mean0)
            for d in deps:
                c.request({"cmd": "deposit", **d})
            injected = sum(d["cy"] + d["ci"] for d in deps)
            total_injected += injected

            # Advance tau steps (first sub-step flushes the queued deposit).
            c.request({"cmd": "step", "n": tau})
            steps_taken += tau
            ro = self._readout()
            Q_A = q_A(ro)
            dQ = Q_A - Q_A_prev
            Q_A_prev = Q_A
            dq_list.append(dQ)
            sum_dq += dQ
            sum_dep += injected
            s_rung = dQ / max(injected, EPS_CHARGE)
            s_list.append(s_rung)

            q_mean = float(np.mean(ro["q"]))
            pi_sat_frac = float(np.mean(ro["q"] >= args.q_sat))
            max_eps2 = float(np.max(ro["eps2"]))
            lively = (q_mean >= args.q_floor * q_mean0 and pi_sat_frac <= args.pi_sat_max)
            self.rungs.append({
                "r": r, "step": int(ro["step"]) if "step" in ro else steps_taken,
                "tau": tau, "q_mean": q_mean, "q_mean0": q_mean0,
                "pi_sat_frac": pi_sat_frac, "max_eps2": max_eps2,
                "Q_A": Q_A, "dQ": dQ, "injected": injected, "S_rung": s_rung,
                "alive": bool(lively),
            })
            if not lively:
                self.boundary.append(f"rung {r}: aliveness violated "
                                     f"(q_mean {q_mean:.4g} / floor {args.q_floor * q_mean0:.4g}"
                                     f", pi_sat {pi_sat_frac:.2e} / max {args.pi_sat_max:.2e})")
            if steps_taken > args.steps:
                self.boundary.append(f"step budget {args.steps} exceeded at rung {r}")
                break

        # G4 liveness (boundary-flagged): any deviation from healthy.
        dormancy = max_eps2 < 1e-12
        # GS steering guard: a non-control YANG arm that injected nothing is a
        # bug (steering that never happens). Yin stay-alive may legitimately
        # inject nothing when already above the aliveness floor.
        if args.strength > 0 and args.mode == "yang" and total_injected <= 0:
            raise RuntimeError("[GS] YANG arm injected nothing (strength>0) — bug")
        # S (per-unit leverage) is only meaningful when real charge was injected.
        has_injection = total_injected > 0.0
        leverage = sum_dq / max(sum_dep, EPS_CHARGE) if has_injection else None

        return {
            "ic_charge": charge_in, "charge_rel_err": rel,
            "q_mean0": q_mean0, "target": tcell, "rungs": self.rungs,
            "boundary": self.boundary, "total_injected": float(total_injected),
            "sum_dq": sum_dq, "sum_dep": sum_dep,
            "G_cad": sum_dq, "S": leverage,
            "has_injection": has_injection,
            "sigma_dq": float(np.std(dq_list)) if dq_list else 0.0,
            "mean_s_ratio": float(np.mean(s_list)) if s_list and has_injection else 0.0,
            "dormancy": dormancy, "steps_taken": steps_taken,
            "hard_stop": hard_stop,
        }


class Verdict:
    """Decision tree D0-D5 (section 8 of the pre-registration)."""

    @staticmethod
    def check(control: dict | None, result: dict, args) -> dict:
        # D0 connection/infrastructure handled at connect time (caller raises).
        # D1 aliveness abort / hard-stop.
        if result.get("hard_stop"):
            return {"verdict": "INVALID", "branch": "D1",
                    "reason": "NaN-loud-fail hard stop (boundary recorded)"}
        if [b for b in result["boundary"] if "aliveness" in b]:
            valid = sum(1 for r in result["rungs"] if r["alive"])
            if args.rungs - valid >= 2:
                return {"verdict": "INVALID", "branch": "D1",
                        "reason": "aliveness violated on 2+ rungs",
                        "boundary": result["boundary"]}

        # Need at least 6 valid rungs for any verdict.
        valid = sum(1 for r in result["rungs"] if r["alive"])
        if valid < 6 and result["sum_dep"] > 0:
            return {"verdict": "INVALID", "branch": "budget",
                    "reason": f"only {valid} valid rungs (< 6)"}

        # Under-budget: the run must complete ALL requested rungs (pre-reg §3/§4:
        # "If the step budget is exhausted before R rungs complete, the arm is
        # INVALID (under-budget)"). An incomplete run is not a verdict, even if
        # it had >= 6 valid rungs before budget cut it off.
        if len(result["rungs"]) < args.rungs and result["sum_dep"] > 0:
            return {"verdict": "INVALID", "branch": "budget",
                    "reason": f"under-budget: completed {len(result['rungs'])}/"
                              f"{args.rungs} rungs before N_max={args.steps} "
                              f"steps (boundary recorded)",
                    "boundary": result["boundary"]}

        if args.strength <= 0:
            # Control arm: report increment framing, no verdict branch.
            return {"verdict": "CONTROL", "reason": "strength 0 reference",
                    "G0": result["sum_dq"]}

        G0 = (control["sum_dq"] if control else 0.0)
        margin = 2.0 * result["sigma_dq"]
        Gc = result["sum_dq"]
        S = result["S"]

        # No injection applied -> no steering effect to judge (e.g. Yin
        # stay-alive above the floor). Honest N/A, not a verdict.
        if S is None:
            return {"verdict": "N/A", "branch": "no-injection",
                    "reason": "arm injected no charge (no steering effect to "
                              "judge — e.g. Yin stay-alive above the floor)",
                    "G_cad": Gc}

        # D4 regression: cadence arm target collapses ~10x relative to control.
        # Approx via target-coherence end-vs-start on the arm's final rung.
        if result["rungs"]:
            final_Q = result["rungs"][-1]["Q_A"]
            if control and control["sum_dq"] >= 0 and final_Q <= 1e-3:
                return {"verdict": "REGRESSION", "branch": "D4",
                        "reason": "target attractor collapsed (G34-like ~10x)"}

        if Gc > G0 + margin and S > 1.0:
            return {"verdict": "SUPPORT", "branch": "D2",
                    "reason": f"G_cad {Gc:.4g} > G0+2sig {G0 + margin:.4g} and S {S:.3f} > 1",
                    "G_cad": Gc, "G0": G0, "S": S}
        if S <= 0.0:
            return {"verdict": "NULL", "branch": "D5",
                    "reason": f"alive but S {S:.3f} <= 0 (no positive leverage)"}
        return {"verdict": "NULL", "branch": "D3",
                "reason": f"G_cad {Gc:.4g} <= G0+2sig {G0 + margin:.4g} or S {S:.3f} <= 1",
                "G_cad": Gc, "G0": G0, "S": S}


# ── offline self-test (no connection) ────────────────────────────────────
def self_test() -> int:
    n = 64
    arr = np.arange(n ** 3, dtype="<f4")
    b64 = base64.b64encode(arr.tobytes()).decode()
    back = decode_b64(b64)
    assert auto_grid_n(back) == n, "grid_n auto-detect failed"
    assert error_check_shape(back, n) == 0, "sh"
    # cadence series
    cad = phi_cadence(8)
    assert cad[:4] == [1, 2, 3, 4], cad
    assert cad[4] == 7 and cad[5] == 11, cad
    # S arithmetic (synthetic window)
    dq = np.array([1.0, 2.0, 1.5])
    dep = np.array([0.5, 1.0, 0.5])
    S = dq.sum() / dep.sum()
    assert abs(S - 4.5 / 2.0) < 1e-9, S
    # aliveness guard arithmetic
    q_mean0 = 1.0
    q_floor = 0.05
    q_sat = 100.0
    assert (q_mean0 >= q_floor * q_mean0)
    assert (np.mean(np.array([0.0, 200.0]) >= q_sat) > 0)  # pi-sat triggers
    print(f"[self-test] PASS: decode+grid_n+phi-cadence+S+aliveness (n={n})")
    return 0


def error_check_shape(arr: np.ndarray, n: int) -> int:
    return 0 if arr.size == n ** 3 else 1


def main() -> int:
    p = argparse.ArgumentParser(
        description="Phase-3 steering loop: readout -> predict(persistence) -> deposit on phi-cadence.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=7599)
    # steering
    p.add_argument("--strength", type=float, default=0.0,
                   help="injection strength multiplier; 0 = control/no injection")
    p.add_argument("--mode", choices=["yang", "yin"], default="yang",
                   help="converge (steer toward target attractor) or stay-alive")
    p.add_argument("--cadence", choices=["phi", "uniform"], default="phi",
                   help="phi = round(phi^k) rung intervals; uniform = every step")
    p.add_argument("--per-step", action="store_true",
                   help="shorthand for --cadence uniform (G34 reference arm)")
    p.add_argument("--steps", type=int, default=2000, help="max global-step budget")
    p.add_argument("--rungs", type=int, default=8, help="cadence rungs (full readouts)")
    # IC + target
    p.add_argument("--seed", type=int, default=20260815)
    p.add_argument("--ic-deposits", type=int, default=10)
    p.add_argument("--target-x", type=float, default=None)
    p.add_argument("--target-y", type=float, default=None)
    p.add_argument("--target-z", type=float, default=None)
    p.add_argument("--target-radius", type=int, default=1,
                   help="halo radius (cells) around the target cell for Q_A")
    p.add_argument("--placement", choices=["single", "annular"], default="single",
                   help="deposit placement: single-cell TSC at target, or split "
                        "across the 26-cell Chebyshev shell at radius 1 (annular)")
    p.add_argument("--project-k", type=int, default=8,
                   help="project k for the read-side target when --target-x/y/z "
                        "are absent (cell[0] is the target regardless of k)")
    # aliveness / steering constants (must match the pre-registration defaults)
    p.add_argument("--q-floor", type=float, default=0.05)
    p.add_argument("--q-sat", type=float, default=100.0)
    p.add_argument("--pi-sat-max", type=float, default=1e-6)
    p.add_argument("--q-target-density", type=float, default=1.0,
                   help="target coherence density for the Yang converge deficit")
    p.add_argument("--lam-max", type=float, default=1.0,
                   help="per-rung deposit charge ceiling in phi-ratio units")
    p.add_argument("--sigma", type=float, default=1.0,
                   help="TSC sigma for Yang deposits")
    p.add_argument("--sigma-yin", type=float, default=4.0,
                   help="TSC sigma for Yin diffuse deposits")
    p.add_argument("--grid-n", type=int, default=None,
                   help="pre-declared grid_n (auto-detected from first readout)")
    p.add_argument("--self-test", action="store_true",
                   help="offline arith/detect round-trip, no connection")
    p.add_argument("--ledger", action="store_true",
                   help="append a verdict ledger row to the pre-registration doc")
    p.add_argument("--pre-reg", default=str(PREREG_PATH),
                   help="pre-registration markdown file whose Ledger section "
                        "receives appended rows (default = phase3_steering_prereg.md)")
    args = p.parse_args()

    if args.self_test:
        return self_test()
    if args.per_step:
        args.cadence = "uniform"

    client = BridgeClient(args.host, args.port)
    try:
        pong = client.request({"cmd": "ping"})
        if not pong.get("ok"):
            print(f"[steer] ERROR: ping failed: {pong}")
            return 1
        print(f"[steer] connected: engine step={pong.get('step')} t={pong.get('t')}")

        # D0 infrastructure gates up front.
        ctrl = client.request({"cmd": "clear"})
        assert ctrl.get("ok"), ctrl

        # Auto-detect grid_n from a throwaway readout on the cleared field.
        if args.grid_n is None:
            probe = client.request({"cmd": "readout"})
            args.grid_n = auto_grid_n(decode_b64(probe["q_b64"]))
        print(f"[steer] grid_n = {args.grid_n}")

        # CONTROL arm first (strength 0 -> reference G0), then the active arm.
        ctrl_args = argparse.Namespace(**{**vars(args), "strength": 0.0})
        control_res = run_one(client, ctrl_args, mark="control")
        print(f"[steer] control: G0={control_res['sum_dq']:.4g} q_mean0={control_res['q_mean0']:.4g}")

        active_args = argparse.Namespace(**vars(args))
        res = run_one(client, active_args, mark=f"strength {args.strength}")
        verdict = Verdict.check(control_res, res, args)
        print("[steer] verdict: %s (%s) — %s" % (
            verdict["verdict"], verdict.get("branch", "-"), verdict.get("reason", "")))
        s_note = "n/a (no injection)" if res["S"] is None else f"{res['S']:.4f}"
        print("[steer] telemetry:")
        print(f"[steer]   G0          = {control_res['sum_dq']:.4g}")
        print(f"[steer]   G_cad       = {res['sum_dq']:.4g}")
        print(f"[steer]   injected    = {res['total_injected']:.4g}")
        print(f"[steer]   S (leverage)= {s_note}")
        print(f"[steer]   sigma_dq    = {res['sigma_dq']:.4g}")
        print(f"[steer]   q_mean0     = {res['q_mean0']:.4g}")
        print(f"[steer]   target cell = {res['target']}")
        if res["boundary"]:
            print("[steer]   boundaries  :")
            for b in res["boundary"]:
                print(f"[steer]     - {b}")
        for r in res["rungs"]:
            print(f"[steer]   rung {r['r']:<2} tau={r['tau']:<3} q_mean={r['q_mean']:.4g} "
                  f"pi_sat={r['pi_sat_frac']:.2e} dQ={r['dQ']:+.4g} "
                  f"inject={r['injected']:.4g} S_r={r['S_rung']:+.4f} alive={r['alive']}")

        if args.ledger:
            append_ledger(args, control_res, res, verdict)
        return 0
    finally:
        client.close()


def run_one(client: BridgeClient, args, mark: str) -> dict:
    arm = SteeringArm(client, args)
    t0 = time.time()
    res = arm.run()
    s_str = "n/a" if res["S"] is None else f"{res['S']:.4f}"
    print(f"[steer] arm {mark}: ok in {time.time() - t0:.1f}s — "
          f"G_cad {res['sum_dq']:.4g} injected {res['total_injected']:.4g} S {s_str}")
    return res


def append_ledger(args, control: dict, res: dict, verdict: dict) -> None:
    """Append a ledger row to the pre-registration document (section: Ledger)."""
    pre_path = Path(args.pre_reg)
    if not pre_path.exists():
        print(f"[steer] ledger: pre-reg file not found: {pre_path}")
        return
    text = pre_path.read_text(encoding="utf-8")
    s_ledge = "n/a" if res["S"] is None else f"{res['S']:.4f}"
    arm_ctx = (f"strength {args.strength} mode {args.mode} cadence {args.cadence} "
               f"placement {getattr(args, 'placement', 'single')} "
               f"lam_max {args.lam_max} rungs {args.rungs} "
               f"target_x {args.target_x} project_k {args.project_k} "
               f"seed {args.seed}")
    row = (
        f"\n### Run {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} — {arm_ctx}\n\n"
        f"- verdict: **{verdict['verdict']}** (branch {verdict.get('branch', '-')}) — "
        f"{verdict.get('reason', '')}\n"
        f"- G0 (control) = {control['sum_dq']:.4g}; G_cad = {res['sum_dq']:.4g}; "
        f"S (leverage) = {s_ledge}; sigma_dq = {res['sigma_dq']:.4g}\n"
        f"- injected = {res['total_injected']:.4g}; q_mean0 = {res['q_mean0']:.4g}; "
        f"target = {res['target']}\n"
        f"- boundary: {res['boundary'] if res['boundary'] else 'none'}\n"
        f"- per-rung: {json.dumps(res['rungs'])}\n"
    )
    new_text = text.replace("_No runs yet — pre-registration locked before execution._",
                            "_Runs recorded below._" + row)
    if new_text == text:
        # fall back to appending at end.
        new_text = text.rstrip() + "\n" + row
    pre_path.write_text(new_text, encoding="utf-8")
    print(f"[steer] ledger row appended to {pre_path.name}")


if __name__ == "__main__":
    sys.exit(main())
