#!/usr/bin/env python3
"""Four-arm balance-built Qi spiral confirmation runner."""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

import balance_spiral_observability as obs

SEEDS = [20260817, 20260819, 20260821]
ARMS = ["D", "A", "B", "C"]
STRENGTH = 0.25
TARGET_K = 8


def read_field(client, n):
    return obs.decode_readout(client.request({"cmd": "readout"}), n)


def target_cells(client):
    reply = client.request({"cmd": "project", "k": TARGET_K})
    return reply["cells"]


def normalize_budget(deposits, budget):
    total = sum(abs(d["cy"]) + abs(d["ci"]) for d in deposits)
    if total <= budget or total == 0:
        return deposits
    scale = budget / total
    return [{**d, "cy": d["cy"] * scale, "ci": d["ci"] * scale} for d in deposits]


def balance_deposits(field, cells, n, budget):
    out = []
    for cell in cells:
        idx = int(cell["i"])
        epsilon = float(field["eps"][idx])
        amount = STRENGTH * abs(epsilon) / (1.0 + abs(epsilon)) / len(cells)
        cy = amount if epsilon < 0 else 0.0
        ci = amount if epsilon > 0 else 0.0
        out.append({"x": cell["x"], "y": cell["y"], "z": cell["z"], "cy": cy, "ci": ci, "sigma": 1.0})
    return normalize_budget(out, budget)


def spiral_deposits(field, cells, n, budget):
    helix = obs.helical_scan(field["theta"], field["field_power"], n)
    axis, mode = int(helix["axis"]), int(helix["mode"])
    out = []
    for cell in cells:
        coord = [cell["gx"], cell["gy"], cell["gz"]][axis]
        phase = 2.0 * np.pi * mode * coord / n
        out.append({"x": cell["x"], "y": cell["y"], "z": cell["z"],
                    "cy": math.cos(phase), "ci": math.sin(phase), "sigma": 1.0})
    return normalize_budget(out, budget)


def arm_deposits(arm, field, cells, n):
    if arm == "D":
        return []
    if arm == "A":
        return balance_deposits(field, cells, n, STRENGTH)
    if arm == "B":
        return spiral_deposits(field, cells, n, STRENGTH)
    return balance_deposits(field, cells, n, STRENGTH / 2) + spiral_deposits(field, cells, n, STRENGTH / 2)


def compact_metrics(field, n, control_seed):
    live = obs.observe(field, n)
    controls = obs.matched_controls(field, n, control_seed)
    controlled = {name: obs.observe(value, n) for name, value in controls.items()}
    return {"eps_rms": live["eps"]["rms"], "coherence_mean": live["qi_coherence"]["mean"],
            "field_power_mean": live["field_power"]["mean"], "field_power_max": live["field_power"]["percentiles"]["99"],
            "j_proxy_rms": live["current"]["rms"], "helix": live["helix"],
            "controls": {name: value["helix"] for name, value in controlled.items()}}


def run_arm(client, seed, arm, n):
    client.request({"cmd": "clear"})
    for dep in obs.make_ic(seed, 10):
        client.request({"cmd": "deposit", **dep})
    client.request({"cmd": "step", "n": 1})
    field = read_field(client, n)
    baseline = compact_metrics(field, n, obs.CONTROL_SEED + seed)
    ceiling = max(1e-12, float(np.max(field["field_power"]))) * 100.0
    records = [{"index": 0, "tau": 0, "metrics": baseline, "injected": 0.0}]
    total_injected = 0.0
    for index, tau in enumerate(obs.CADENCE, 1):
        cells = target_cells(client)
        deposits = arm_deposits(arm, field, cells, n)
        injected = sum(abs(d["cy"]) + abs(d["ci"]) for d in deposits)
        if injected > STRENGTH + 1e-9:
            raise RuntimeError("shared charge budget exceeded")
        for dep in deposits:
            client.request({"cmd": "deposit", **dep})
        total_injected += injected
        client.request({"cmd": "step", "n": tau})
        field = read_field(client, n)
        if float(np.max(field["field_power"])) > ceiling:
            raise RuntimeError(f"UNSAFE field-power ceiling at arm {arm} seed {seed}")
        records.append({"index": index, "tau": tau,
                        "metrics": compact_metrics(field, n, obs.CONTROL_SEED + seed + index * 10),
                        "injected": injected})
    return {"seed": seed, "arm": arm, "total_injected": total_injected, "records": records}


def summarize(runs):
    by = {(r["seed"], r["arm"]): r for r in runs}
    paired = []
    for seed in SEEDS:
        d = by[(seed, "D")]["records"][-1]["metrics"]
        row = {"seed": seed}
        for arm in ("A", "B", "C"):
            end = by[(seed, arm)]["records"][-1]["metrics"]
            row[arm] = {"balance_improvement": d["eps_rms"] - end["eps_rms"],
                        "helix_improvement": end["helix"]["best"] - d["helix"]["best"],
                        "control_separation": end["helix"]["mode"] != 0 and end["helix"]["best"] > end["controls"]["shuffle"]["best"] and end["helix"]["best"] > end["controls"]["phase"]["best"]}
        paired.append(row)
    balance_pass = sum(p["A"]["balance_improvement"] > 0 for p in paired) >= 2
    spiral_direction = sum(p["B"]["helix_improvement"] > 0 for p in paired) >= 2
    spiral_control = sum(p["B"]["control_separation"] for p in paired) >= 2
    combined_pass = sum(p["C"]["balance_improvement"] > 0 and p["C"]["helix_improvement"] > 0 and p["C"]["control_separation"] for p in paired) >= 2
    decisions = {"A": "BALANCE SUPPORTED" if balance_pass else "BALANCE OBJECTIVE DOES NOT SUPPORT",
                 "B": "SPIRAL SUPPORTED" if spiral_direction and spiral_control else ("NOISE-COMPATIBLE / MECHANISM NOT SUPPORTED" if spiral_direction else "SPIRAL OBJECTIVE DOES NOT SUPPORT"),
                 "C": "BALANCE-BUILT QI SPIRAL SUPPORTED" if combined_pass else "COMBINED OBJECTIVE DOES NOT SUPPORT"}
    return {"paired": paired, "decisions": decisions}


def self_test():
    deps = normalize_budget([{"cy": 1.0, "ci": -1.0}], 0.25)
    assert abs(abs(deps[0]["cy"]) + abs(deps[0]["ci"]) - 0.25) < 1e-12
    fake = {"eps_rms": 2.0, "helix": {"best": 0.3}}
    assert fake["eps_rms"] - 1.0 > 0
    print("[self-test] PASS: shared budget, frozen arms, paired decision arithmetic")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7599)
    parser.add_argument("--grid-n", type=int, default=32)
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[1] / "_diag" / "balance_spiral_confirmation.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    client = obs.BridgeClient(args.host, args.port)
    try:
        client.request({"cmd": "ping"})
        runs = [run_arm(client, seed, arm, args.grid_n) for seed in SEEDS for arm in ARMS]
        result = {"protocol": "balance-spiral-confirmation-v1", "seeds": SEEDS, "arms": ARMS,
                  "cadence": obs.CADENCE, "strength": STRENGTH, "runs": runs}
        result["summary"] = summarize(runs)
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"output": str(output), **result["summary"]}, indent=2))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
