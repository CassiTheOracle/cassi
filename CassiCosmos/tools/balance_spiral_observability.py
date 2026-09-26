#!/usr/bin/env python3
"""Read-only Balance–Spiral Observability Gate for the Cassi mind engine.

Protocol and verdict are frozen in
research/steering/balance_spiral_observability_prereg.md.
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
DEFAULT_SEED = 20260817
CONTROL_SEED = 20260818
CADENCE = [max(1, int(round(PHI ** k))) for k in range(8)]
PERCENTILES = [1, 5, 25, 50, 75, 95, 99]


class BridgeClient:
    def __init__(self, host="127.0.0.1", port=7599, timeout=300.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.rf = self.sock.makefile("rb")

    def request(self, obj):
        self.sock.sendall(json.dumps(obj).encode("utf-8") + b"\n")
        raw = self.rf.readline()
        if not raw:
            raise ConnectionError("engine closed connection")
        reply = json.loads(raw.decode("utf-8"))
        if reply.get("ok") is not True:
            raise RuntimeError(f"engine rejected {obj.get('cmd')}: {reply}")
        return reply

    def close(self):
        try:
            self.rf.close()
            self.sock.close()
        except OSError:
            pass


def decode_f32(payload):
    raw = base64.b64decode(payload, validate=True)
    if len(raw) % 4:
        raise ValueError("float32 payload byte length is not divisible by four")
    return np.frombuffer(raw, dtype="<f4").copy()


def make_ic(seed=DEFAULT_SEED, count=10):
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        x, y, z = (rng.uniform(-0.8, 0.8) for _ in range(3))
        sigma = rng.choice([0.5, 1.0, 1.5, 2.0])
        if rng.random() < 1.0 / 3.0:
            ci = rng.uniform(0.3, 1.0)
            cy = PHI * ci
        else:
            cy = rng.uniform(-1.0, 1.0)
            ci = rng.uniform(-1.0, 1.0)
        out.append({"x": x, "y": y, "z": z, "cy": cy, "ci": ci, "sigma": sigma})
    return out


def summaries(values):
    a = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(a)), "std": float(np.std(a)),
        "rms": float(np.sqrt(np.mean(a * a))),
        "percentiles": {str(p): float(v) for p, v in zip(PERCENTILES, np.percentile(a, PERCENTILES))},
    }


def decode_readout(reply, expected_n):
    ey = decode_f32(reply["ey_b64"])
    ei = decode_f32(reply["ei_b64"])
    power_payload = decode_f32(reply["q_b64"])
    eps2_payload = decode_f32(reply["eps2_b64"])
    size = expected_n ** 3
    if not (ey.size == ei.size == power_payload.size == eps2_payload.size == size):
        raise ValueError(f"shape mismatch ey={ey.size} ei={ei.size} power={power_payload.size} eps2={eps2_payload.size} expected={size}")
    if not all(np.isfinite(x).all() for x in (ey, ei, power_payload, eps2_payload)):
        raise ValueError("non-finite engine readout")
    power = ey * ey + ei * ei
    eps = ey - PHI * ei
    eps2 = eps * eps
    power_error = float(np.max(np.abs(power_payload - power)))
    eps2_error = float(np.max(np.abs(eps2_payload - eps2)))
    if power_error > 1e-5 or eps2_error > 1e-5:
        raise ValueError(f"payload identity failed power={power_error:.3e} eps2={eps2_error:.3e}")
    rho = ey + ei
    qi = rho * rho / (rho * rho + PHI ** -2 + eps2)
    theta = np.arctan2(ei, ey)
    return {"ey": ey, "ei": ei, "field_power": power, "eps": eps, "rho": rho,
            "qi_coherence": qi, "theta": theta,
            "payload_errors": {"field_power": power_error, "eps2": eps2_error}}


def periodic_grad(a):
    return tuple((np.roll(a, -1, axis=ax) - np.roll(a, 1, axis=ax)) * 0.5 for ax in range(3))


def phase_current_proxy(ey, ei):
    gey = periodic_grad(ey)
    gei = periodic_grad(ei)
    return tuple(ey * gei[ax] - ei * gey[ax] for ax in range(3))


def helical_scan(theta, power, n, modes=range(-8, 9)):
    th = theta.reshape((n, n, n))
    pw = power.reshape((n, n, n)).astype(np.float64)
    denom = float(np.sum(pw))
    if denom <= 1e-30:
        return {"best": 0.0, "axis": 0, "mode": 0, "mode_zero": 0.0}
    phase = np.exp(1j * th)
    best = (-1.0, 0, 0)
    zero = 0.0
    coordinates = [np.arange(n).reshape((n, 1, 1)), np.arange(n).reshape((1, n, 1)), np.arange(n).reshape((1, 1, n))]
    for axis, coord in enumerate(coordinates):
        for mode in modes:
            carrier = np.exp(-1j * 2.0 * np.pi * mode * coord / n)
            order = float(abs(np.sum(pw * phase * carrier) / denom))
            if mode == 0:
                zero = max(zero, order)
            if order > best[0]:
                best = (order, axis, mode)
    return {"best": best[0], "axis": best[1], "mode": best[2], "mode_zero": zero}


def density_balance(rho, eps, bins=16):
    order = np.argsort(rho)
    chunks = np.array_split(order, bins)
    out = []
    for chunk in chunks:
        if chunk.size == 0:
            continue
        values = eps[chunk]
        med = float(np.median(values))
        out.append({"rho_median": float(np.median(rho[chunk])), "eps_median": med,
                    "eps_mad": float(np.median(np.abs(values - med))), "count": int(chunk.size)})
    return out


def spatial_shuffle(ey, ei, seed):
    rng = np.random.default_rng(seed)
    perm = rng.permutation(ey.size)
    return ey[perm], ei[perm]


def phase_scramble_component(a, seed):
    rng = np.random.default_rng(seed)
    shape = a.shape
    spectrum = np.fft.rfftn(a)
    random_field = rng.normal(size=shape)
    random_phase = np.angle(np.fft.rfftn(random_field))
    axes = tuple(range(len(shape)))
    rebuilt = np.fft.irfftn(np.abs(spectrum) * np.exp(1j * random_phase), s=shape, axes=axes).real
    std = float(np.std(rebuilt))
    target_std = float(np.std(a))
    if std > 0:
        rebuilt = (rebuilt - np.mean(rebuilt)) * (target_std / std) + np.mean(a)
    else:
        rebuilt.fill(float(np.mean(a)))
    return rebuilt


def matched_controls(field, n, seed):
    sey, sei = spatial_shuffle(field["ey"], field["ei"], seed)
    shape = (n, n, n)
    pey = phase_scramble_component(field["ey"].reshape(shape), seed + 1).ravel()
    pei = phase_scramble_component(field["ei"].reshape(shape), seed + 2).ravel()
    return {"shuffle": derive_arrays(sey, sei), "phase": derive_arrays(pey, pei)}


def derive_arrays(ey, ei):
    power = ey * ey + ei * ei
    eps = ey - PHI * ei
    rho = ey + ei
    qi = rho * rho / (rho * rho + PHI ** -2 + eps * eps)
    return {"ey": ey, "ei": ei, "field_power": power, "eps": eps, "rho": rho,
            "qi_coherence": qi, "theta": np.arctan2(ei, ey)}


def temporal_phase(previous, current):
    delta = np.angle(np.exp(1j * (current["theta"] - previous["theta"])))
    weight = np.sqrt(previous["field_power"] * current["field_power"]).astype(np.float64)
    total = float(np.sum(weight))
    if total <= 1e-30:
        return {"resultant": 0.0, "mean_abs_increment": 0.0}
    resultant = float(abs(np.sum(weight * np.exp(1j * delta)) / total))
    return {"resultant": resultant, "mean_abs_increment": float(np.sum(weight * np.abs(delta)) / total)}


def observe(field, n):
    shape = (n, n, n)
    currents = phase_current_proxy(field["ey"].reshape(shape), field["ei"].reshape(shape))
    j2 = sum(j * j for j in currents)
    total_j2 = float(np.mean(j2))
    return {
        "eps": summaries(field["eps"]), "abs_eps": summaries(np.abs(field["eps"])),
        "qi_coherence": summaries(field["qi_coherence"]), "field_power": summaries(field["field_power"]),
        "density_balance": density_balance(field["rho"], field["eps"]),
        "current": {"rms": float(math.sqrt(total_j2)),
                    "axis_rms": [float(np.sqrt(np.mean(j * j))) for j in currents],
                    "axial_fraction": float(np.mean(currents[2] ** 2) / total_j2) if total_j2 > 0 else 0.0},
        "helix": helical_scan(field["theta"], field["field_power"], n),
    }


def spearman(x, y):
    if len(x) != len(y) or len(x) < 2:
        return None
    rx = np.argsort(np.argsort(np.asarray(x, dtype=float)))
    ry = np.argsort(np.argsort(np.asarray(y, dtype=float)))
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def verdict(records):
    live = [r["live"] for r in records]
    if max(r["current"]["rms"] for r in live) <= 1e-14 and max(r["helix"]["best"] for r in live) <= 1e-14:
        return {"verdict": "NO OBSERVABLE PHASE CURRENT", "branch": 2}
    eligible = []
    unstable = False
    modes = []
    for r in records:
        lh = r["live"]["helix"]
        modes.append((lh["axis"], lh["mode"]))
        nonzero = lh["mode"] != 0
        separation = lh["best"] > r["controls"]["shuffle"]["helix"]["best"] and lh["best"] > r["controls"]["phase"]["helix"]["best"]
        eligible.append(nonzero and separation)
    if not any(eligible):
        return {"verdict": "NO EVIDENCE OF ORGANIZED SPIRAL", "branch": 3}
    winning = [modes[i] for i, ok in enumerate(eligible) if ok]
    if len(set(winning)) == len(winning) and len(winning) > 1:
        unstable = True
    if unstable or not eligible[-1]:
        return {"verdict": "INCONCLUSIVE—CALIBRATION UNSTABLE", "branch": 6}
    return {"verdict": "OBSERVABLE—ELIGIBLE FOR CONFIRMATION", "branch": 5}


def run_live(args):
    client = BridgeClient(args.host, args.port, args.timeout)
    try:
        client.request({"cmd": "ping"})
        client.request({"cmd": "clear"})
        for dep in make_ic(args.seed, args.ic_deposits):
            client.request({"cmd": "deposit", **dep})
        client.request({"cmd": "step", "n": 1})
        records = []
        previous = None
        for index, tau in enumerate([0] + CADENCE):
            if index > 0:
                client.request({"cmd": "step", "n": tau})
            reply = client.request({"cmd": "readout"})
            field = decode_readout(reply, args.grid_n)
            controls = matched_controls(field, args.grid_n, CONTROL_SEED + index * 10)
            record = {"index": index, "tau": tau, "step": reply.get("step"), "t": reply.get("t"),
                      "payload_errors": field["payload_errors"], "live": observe(field, args.grid_n),
                      "controls": {name: observe(ctrl, args.grid_n) for name, ctrl in controls.items()}}
            if previous is not None:
                record["temporal_phase"] = temporal_phase(previous, field)
            records.append(record)
            previous = field
        first_bins = records[0]["live"]["density_balance"]
        last_bins = records[-1]["live"]["density_balance"]
        calibration = {"balance_bin_spearman": spearman([b["eps_median"] for b in first_bins], [b["eps_median"] for b in last_bins])}
        result = {"protocol": "balance-spiral-observability-v1", "seed": args.seed, "control_seed": CONTROL_SEED,
                  "grid_n": args.grid_n, "cadence": CADENCE, "records": records,
                  "calibration": calibration, "decision": verdict(records)}
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"output": args.output, "decision": result["decision"], "calibration": calibration}, indent=2))
        return 0
    finally:
        client.close()


def self_test():
    n = 8
    coords = np.indices((n, n, n))
    theta = 2.0 * np.pi * coords[2] / n
    ey = np.cos(theta).ravel().astype("<f4")
    ei = np.sin(theta).ravel().astype("<f4")
    field = derive_arrays(ey, ei)
    obs = observe(field, n)
    assert obs["helix"]["axis"] == 2 and obs["helix"]["mode"] % n == 1
    assert obs["helix"]["best"] > 0.999
    s1 = spatial_shuffle(ey, ei, CONTROL_SEED)
    s2 = spatial_shuffle(ey, ei, CONTROL_SEED)
    assert np.array_equal(s1[0], s2[0]) and np.array_equal(s1[1], s2[1])
    p1 = phase_scramble_component(ey.reshape((n, n, n)), CONTROL_SEED)
    p2 = phase_scramble_component(ey.reshape((n, n, n)), CONTROL_SEED)
    assert np.array_equal(p1, p2)
    encoded = base64.b64encode(ey.tobytes()).decode("ascii")
    assert np.array_equal(decode_f32(encoded), ey)
    assert CADENCE == [1, 2, 3, 4, 7, 11, 18, 29]
    print("[self-test] PASS: strict decode, deterministic controls, periodic current, helix recovery, cadence")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7599)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--grid-n", type=int, default=32)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--ic-deposits", type=int, default=10)
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[1] / "_diag" / "balance_spiral_observability.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    return self_test() if args.self_test else run_live(args)


if __name__ == "__main__":
    sys.exit(main())
