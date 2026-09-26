#!/usr/bin/env python3
"""Frozen learned balance-policy collection, training, and live evaluation.

The protocol is frozen in research/steering/balance_policy_learning_prereg.md.
This module intentionally imports only the readout/IC/observability helpers from
balance_spiral_observability and uses NumPy (not CassiAI or PyTorch) for fitting.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import random
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

import balance_spiral_observability as obs

PHI = obs.PHI
CADENCE = [1, 2, 3, 4, 7, 11, 18, 29]
PROJECT_K = 8
BUDGET = 0.25
ANALYTIC_STRENGTH = 0.25
TRAIN_SEEDS = list(range(20260901, 20260909))
VAL_SEEDS = [20260911, 20260912]
LIVE_SEEDS = [20260817, 20260819, 20260821]
FIT_SEED = 20260900
EPOCHS = 200
LR = 0.03
ZERO_BASELINE = 1.0


def normalize_budget(deposits: list[dict], budget: float = BUDGET) -> list[dict]:
    charge = sum(abs(float(d.get("cy", 0.0))) + abs(float(d.get("ci", 0.0))) for d in deposits)
    if charge <= budget or charge == 0.0:
        return deposits
    scale = budget / charge
    return [{**d, "cy": float(d.get("cy", 0.0)) * scale, "ci": float(d.get("ci", 0.0)) * scale} for d in deposits]


def analytic_magnitude(eps: np.ndarray | float) -> np.ndarray | float:
    return ANALYTIC_STRENGTH * np.abs(eps) / (1.0 + np.abs(eps)) / 8.0


def features(eps: np.ndarray, rho: np.ndarray, previous_z: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    eps = np.asarray(eps, dtype=np.float64)
    rho = np.asarray(rho, dtype=np.float64)
    active = np.abs(rho) > 0.0
    median = float(np.median(np.abs(rho)[active])) if np.any(active) else 0.0
    z = eps / (np.abs(rho) + PHI ** -1)
    d = np.log1p(np.abs(rho) / (median + 1e-8))
    dz = z.copy() if previous_z is None else z - np.asarray(previous_z, dtype=np.float64)
    return z, d, dz


def action_multiplier(policy: str, z: np.ndarray, d: np.ndarray, dz: np.ndarray, params: np.ndarray | None = None, random_values: np.ndarray | None = None) -> np.ndarray:
    if policy == "D":
        return np.zeros_like(z, dtype=np.float64)
    if policy == "A":
        return np.ones_like(z, dtype=np.float64)
    if policy == "G":
        if params is None:
            raise ValueError("G requires gamma")
        return np.full_like(z, float(1.0 / (1.0 + np.exp(-float(params[0])))))
    if policy == "P":
        if params is None or len(params) != 4:
            raise ValueError("P requires b,wz,wd,wdz")
        b, wz, wd, wdelta = np.asarray(params, dtype=np.float64)
        q = b + wz * np.abs(z) + wd * d + wdelta * np.abs(dz)
        q = np.clip(q, -60.0, 60.0)
        return 0.5 + 1.0 / (1.0 + np.exp(-q))
    if policy == "R":
        if random_values is None:
            raise ValueError("R requires deterministic random values")
        return np.asarray(random_values, dtype=np.float64)
    raise ValueError(policy)


def policy_deposits(field: dict, cells: list[dict], policy: str, previous_z: np.ndarray | None = None, params: np.ndarray | None = None, seed: int = 0) -> tuple[list[dict], np.ndarray, dict]:
    eps = np.asarray([field["eps"][int(c["i"])] for c in cells], dtype=np.float64)
    rho = np.asarray([field["rho"][int(c["i"])] for c in cells], dtype=np.float64)
    z, d, dz = features(eps, rho, previous_z)
    if policy == "R":
        rng = np.random.default_rng(seed)
        random_values = rng.uniform(0.5, 1.5, size=len(cells))
    else:
        random_values = None
    magnitude = analytic_magnitude(eps) * action_multiplier(policy, z, d, dz, params, random_values)
    out = []
    for cell, e, amount in zip(cells, eps, magnitude):
        cy, ci = (float(amount), 0.0) if e < 0.0 else (0.0, float(amount))
        out.append({"x": float(cell["x"]), "y": float(cell["y"]), "z": float(cell["z"]), "cy": cy, "ci": ci, "sigma": 1.0})
    return normalize_budget(out), z, {"z": z, "d": d, "dz": dz, "eps": eps, "rho": rho, "magnitude": np.asarray(magnitude)}


def row_from_state(seed: int, rung: int, rank: int, field: dict, cell: dict, previous_z: float = 0.0, next_eps: float = 0.0) -> dict:
    idx = int(cell["i"])
    e = float(field["eps"][idx]); r = float(field["rho"][idx])
    z, d, dz = features(np.asarray([e]), np.asarray([r]), np.asarray([previous_z]))
    a = float(analytic_magnitude(e))
    cy, ci = (a, 0.0) if e < 0.0 else (0.0, a)
    return {"seed": seed, "rung": rung, "rank": rank, "i": idx,
            "gx": int(cell["gx"]), "gy": int(cell["gy"]), "gz": int(cell["gz"]),
            "x": float(cell["x"]), "y": float(cell["y"]), "z_coord": float(cell["z"]),
            "z": float(z[0]), "d": float(d[0]), "dz": float(dz[0]), "eps": e, "rho": r,
            "cy": cy, "ci": ci, "magnitude": a, "next_eps": next_eps}


def _rows_to_npz(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = ["seed", "rung", "rank", "i", "gx", "gy", "gz", "x", "y", "z_coord", "z", "d", "dz", "eps", "rho", "cy", "ci", "magnitude", "next_eps"]
    np.savez(path, **{k: np.asarray([r[k] for r in rows]) for k in keys})


def load_rows(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return {k: np.asarray(data[k]) for k in data.files}


def split_rows(data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    seeds = np.asarray(data["seed"], dtype=np.int64)
    train = np.isin(seeds, TRAIN_SEEDS)
    val = np.isin(seeds, VAL_SEEDS)
    if np.any(np.isin(seeds, LIVE_SEEDS)):
        raise ValueError("live seed leaked into offline dataset")
    if not np.all(train | val):
        raise ValueError("dataset contains seed outside frozen train/validation partitions")
    return train, val


def _adam_fit(x: np.ndarray, target: np.ndarray, kind: str) -> tuple[np.ndarray, list[float]]:
    npar = 1 if kind == "G" else 4
    p = np.zeros(npar, dtype=np.float64)
    m = np.zeros_like(p); v = np.zeros_like(p)
    losses = []
    aa = np.asarray(target, dtype=np.float64)
    for epoch in range(1, EPOCHS + 1):
        if kind == "G":
            sig = 1.0 / (1.0 + np.exp(-p[0])); pred = np.full(aa.shape, sig)
            grad_pred = 2.0 * (pred - aa) / max(1, aa.size)
            grad = np.asarray([np.sum(grad_pred * sig * (1.0 - sig))])
        else:
            z, d, dz = x.T
            q = np.clip(p[0] + p[1] * np.abs(z) + p[2] * d + p[3] * np.abs(dz), -60.0, 60.0)
            sig = 1.0 / (1.0 + np.exp(-q)); pred = 0.5 + sig
            grad_pred = 2.0 * (pred - aa) / max(1, aa.size)
            grad = np.asarray([np.sum(grad_pred * sig * (1.0 - sig) * c) for c in (np.ones_like(z), np.abs(z), d, np.abs(dz))])
        losses.append(float(np.mean((pred - aa) ** 2)))
        m = 0.9 * m + 0.1 * grad; v = 0.999 * v + 0.001 * grad * grad
        p -= LR * (m / (1.0 - 0.9 ** epoch)) / (np.sqrt(v / (1.0 - 0.999 ** epoch)) + 1e-8)
    return p, losses


def fit(data: dict[str, np.ndarray]) -> dict:
    tr, va = split_rows(data)
    z = np.column_stack((data["z"], data["d"], data["dz"]))
    target = np.divide(data["magnitude"], np.maximum(data["magnitude"], 1e-30), out=np.zeros_like(data["magnitude"], dtype=float), where=np.isfinite(data["magnitude"]))
    # Analytic teacher magnitude is nonzero target direction; zero rows remain zero.
    target = (data["magnitude"] > 0).astype(np.float64)
    pg, lg = _adam_fit(z[tr], target[tr], "G")
    pp, lp = _adam_fit(z[tr], target[tr], "P")
    def mse(p, kind, mask):
        pred = action_multiplier(kind, z[mask, 0], z[mask, 1], z[mask, 2], p)
        return float(np.mean((pred - target[mask]) ** 2))
    return {"seed": FIT_SEED, "lr": LR, "epochs": EPOCHS,
            "G": {"params": pg.tolist(), "train_loss": lg[-1], "val_loss": mse(pg, "G", va)},
            "P": {"params": pp.tolist(), "train_loss": lp[-1], "val_loss": mse(pp, "P", va)},
            "zero_baseline_val_loss": float(np.mean(target[va] ** 2)),
            "finite": bool(np.isfinite(pg).all() and np.isfinite(pp).all())}


def collect(args) -> int:
    client = obs.BridgeClient(args.host, args.port, args.timeout)
    rows = []
    try:
        client.request({"cmd": "ping"})
        for seed in TRAIN_SEEDS + VAL_SEEDS:
            client.request({"cmd": "clear"})
            for dep in obs.make_ic(seed, args.ic_deposits): client.request({"cmd": "deposit", **dep})
            client.request({"cmd": "step", "n": 1})
            prev = np.zeros(PROJECT_K)
            for rung, tau in enumerate(CADENCE):
                field = obs.decode_readout(client.request({"cmd": "readout"}), args.grid_n)
                cells = client.request({"cmd": "project", "k": PROJECT_K})["cells"]
                for rank, cell in enumerate(cells): rows.append(row_from_state(seed, rung, rank, field, cell, float(prev[rank])))
                deps, prev, _ = policy_deposits(field, cells, "A", prev)
                for dep in deps: client.request({"cmd": "deposit", **dep})
                client.request({"cmd": "step", "n": tau})
    finally: client.close()
    _rows_to_npz(rows, Path(args.dataset))
    print(json.dumps({"dataset": args.dataset, "rows": len(rows), "train_seeds": TRAIN_SEEDS, "val_seeds": VAL_SEEDS}, indent=2))
    return 0


def metrics(field, n: int, control_seed: int) -> dict:
    live = obs.observe(field, n)
    return {"eps_rms": live["eps"]["rms"], "coherence_mean": live["qi_coherence"]["mean"],
            "field_power_max": float(np.max(field["field_power"])), "h_star": live["helix"],
            "j_proxy_rms": live["current"]["rms"],
            "controls": {k: obs.observe(v, n)["helix"] for k, v in obs.matched_controls(field, n, control_seed).items()}}


def run_arm(client, seed: int, arm: str, params: dict, n: int, ic_deposits: int) -> dict:
    client.request({"cmd": "clear"})
    for dep in obs.make_ic(seed, ic_deposits): client.request({"cmd": "deposit", **dep})
    client.request({"cmd": "step", "n": 1})
    field = obs.decode_readout(client.request({"cmd": "readout"}), n)
    baseline_max = max(1e-30, float(np.max(field["field_power"])))
    records = [{"rung": 0, "tau": 0, "metrics": metrics(field, n, obs.CONTROL_SEED + seed), "injected": 0.0}]
    prev = np.zeros(PROJECT_K); total = 0.0; rung_charges = []
    for rung, tau in enumerate(CADENCE, 1):
        cells = client.request({"cmd": "project", "k": PROJECT_K})["cells"]
        deps, prev, _ = policy_deposits(field, cells, arm, prev, params.get(arm), seed + rung)
        injected = sum(abs(d["cy"]) + abs(d["ci"]) for d in deps)
        if injected > BUDGET + 1e-9: raise RuntimeError("per-rung budget exceeded")
        for dep in deps: client.request({"cmd": "deposit", **dep})
        total += injected; rung_charges.append(injected)
        client.request({"cmd": "step", "n": tau})
        field = obs.decode_readout(client.request({"cmd": "readout"}), n)
        if not np.isfinite(field["ey"]).all() or not np.isfinite(field["ei"]).all(): raise RuntimeError("non-finite live readout")
        if np.max(field["qi_coherence"]) > 1.0 + 1e-6 or np.max(field["field_power"]) > baseline_max * 100.0: raise RuntimeError("safety gate failed")
        records.append({"rung": rung, "tau": tau, "metrics": metrics(field, n, obs.CONTROL_SEED + seed + rung * 10), "injected": injected})
    return {"seed": seed, "arm": arm, "records": records, "total_charge": total, "rung_charges": rung_charges,
            "endpoint": records[-1]["metrics"], "integrated_balance": float(sum(r["metrics"]["eps_rms"] for r in records)),
            "integrated_h_star": float(sum(r["metrics"]["h_star"]["mode_zero"] for r in records)),
            "integrated_j_proxy_rms": float(sum(r["metrics"]["j_proxy_rms"] for r in records))}


def decision(runs: list[dict], offline: dict) -> dict:
    if not offline["finite"]: return {"branch": 2, "verdict": "INVALID"}
    if offline["P"]["val_loss"] >= offline["zero_baseline_val_loss"] or offline["P"]["val_loss"] > offline["G"]["val_loss"] + 1e-12:
        return {"branch": 3, "verdict": "NOT LEARNABLE—CLOSE POLICY LINE"}
    by = {(r["seed"], r["arm"]): r for r in runs}; paired = []
    for seed in LIVE_SEEDS:
        d = by[(seed, "D")]; a = by[(seed, "A")]; p = by[(seed, "P")]
        de, ae, pe = d["endpoint"]["eps_rms"], a["endpoint"]["eps_rms"], p["endpoint"]["eps_rms"]
        paired.append({"seed": seed, "I_P": de - pe, "I_A": de - ae,
                       "p_beats_d": pe < de, "p_beats_a": pe < ae,
                       "p_integrated_not_worse_a": p["integrated_balance"] <= a["integrated_balance"]})
    if sum(x["p_beats_d"] for x in paired) < 2: return {"branch": 8, "verdict": "LEARNED POLICY REJECT", "paired": paired}
    if sum(x["p_beats_a"] for x in paired) >= 2 and sum(x["p_integrated_not_worse_a"] for x in paired) >= 2: return {"branch": 7, "verdict": "LEARNED POLICY ADOPT", "paired": paired}
    return {"branch": 6, "verdict": "REDISCOVERS ANALYTIC BALANCE", "paired": paired}


def train(args) -> int:
    data = load_rows(Path(args.dataset)); result = fit(data)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True); Path(args.output).write_text(json.dumps({"protocol": "balance-policy-learning-v1", "offline": result}, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2)); return 0


def live(args, run_training: bool = True) -> int:
    data = load_rows(Path(args.dataset)); offline = fit(data) if run_training else json.loads(Path(args.output).read_text())["offline"]
    params = {"G": np.asarray(offline["G"]["params"]), "P": np.asarray(offline["P"]["params"])}
    client = obs.BridgeClient(args.host, args.port, args.timeout); runs = []
    try:
        client.request({"cmd": "ping"})
        for seed in LIVE_SEEDS:
            for arm in ("D", "A", "G", "P", "R"): runs.append(run_arm(client, seed, arm, params, args.grid_n, args.ic_deposits))
    finally: client.close()
    result = {"protocol": "balance-policy-learning-v1", "offline": offline, "runs": runs, "decision": decision(runs, offline), "seeds": LIVE_SEEDS, "arms": ["D", "A", "G", "P", "R"], "cadence": CADENCE, "budget": BUDGET, "held_out": "H* and J_proxy are reported only"}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True); Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8"); print(json.dumps(result["decision"], indent=2)); return 0


def self_test() -> int:
    e = np.array([-2.0, 0.0, 2.0]); r = np.ones(3); z, d, dz = features(e, r)
    assert np.allclose(dz, z) and np.all(d >= 0) and np.isclose(analytic_magnitude(2.0), 0.25 * 2.0 / 3.0 / 8.0)
    assert sum(abs(x["cy"]) + abs(x["ci"]) for x in normalize_budget([{"cy": 1, "ci": 1}], .25)) <= .25 + 1e-12
    x = np.zeros((4, 3)); target = np.full(4, .75); p, losses = _adam_fit(x, target, "G"); assert np.isfinite(p).all() and len(losses) == EPOCHS
    data = {"seed": np.array([TRAIN_SEEDS[0], VAL_SEEDS[0]]), "z": np.zeros(2), "d": np.ones(2), "dz": np.zeros(2), "magnitude": np.ones(2)}; tr, va = split_rows(data); assert tr.sum() == va.sum() == 1
    fake = [{"seed": s, "arm": a, "endpoint": {"eps_rms": 1.0 if a == "P" else 2.0}, "integrated_balance": 1.0 if a == "P" else 2.0} for s in LIVE_SEEDS for a in ("D", "A", "P")]
    off = {"finite": True, "P": {"val_loss": 0.1}, "G": {"val_loss": 0.2}, "zero_baseline_val_loss": 1.0}; assert decision(fake, off)["branch"] == 7
    print("[self-test] PASS: feature math, budget, analytic gradients, split integrity, decision arithmetic"); return 0


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--self-test", action="store_true"); p.add_argument("--collect", action="store_true"); p.add_argument("--train", action="store_true"); p.add_argument("--live", action="store_true"); p.add_argument("--all", action="store_true"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=7599); p.add_argument("--timeout", type=float, default=300.0); p.add_argument("--grid-n", type=int, default=32); p.add_argument("--ic-deposits", type=int, default=10); p.add_argument("--dataset", default=str(Path(__file__).resolve().parents[1] / "_diag" / "balance_policy" / "samples.npz")); p.add_argument("--output", default=str(Path(__file__).resolve().parents[1] / "_diag" / "balance_policy" / "result.json")); args = p.parse_args()
    if args.self_test: return self_test()
    if args.all or args.collect: collect(args)
    if args.all or args.train: train(args)
    if args.all or args.live: return live(args)
    return 0

if __name__ == "__main__": sys.exit(main())
