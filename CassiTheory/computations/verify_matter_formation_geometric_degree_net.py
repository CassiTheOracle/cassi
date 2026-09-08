#!/usr/bin/env python3
"""Independent verifier for the net-degree chiral-lattice formation verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import verify_matter_formation_geometric_degree as independent

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PRIMARY = ROOT / "computations" / "matter_formation_geometric_degree_net.py"
PRIMARY_ENGINE = ROOT / "computations" / "matter_formation_geometric_degree.py"
PROTOCOL = ROOT / "computations" / "matter-formation-geometric-degree-net-prereg.md"
SCHEMA = "matter-formation-geometric-degree-net-verification-v1"
PRIMARY_SCHEMA = "matter-formation-geometric-degree-net-v1"


def protocol_sha256() -> str:
    text = PROTOCOL.read_text(encoding="utf-8")
    begin = "<!-- geometric-net-degree-protocol:start -->"
    end = "<!-- geometric-net-degree-protocol:end -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise independent.VerificationError(
            "net-degree protocol markers are missing or duplicated"
        )
    frozen = text.split(begin, 1)[1].split(end, 1)[0]
    return hashlib.sha256(frozen.encode("utf-8")).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def net_controls() -> dict[str, Any]:
    controls = independent.controls()
    common_sign: int | None = None
    for nsites in (32, 48, 64):
        row = controls["hedgehogs"][str(nsites)]
        result = row["result"]
        degrees = [int(target["net_degree"]) for target in result["targets"]]
        signs = {int(value) for value in degrees}
        passes = bool(
            result["admissible"]
            and not result["ambiguous"]
            and all(abs(value) == 1 for value in degrees)
            and len(signs) == 1
        )
        sign = degrees[0] if passes else None
        if passes:
            if common_sign is None:
                common_sign = sign
            passes = sign == common_sign
        row["passes"] = bool(passes)
        row["sign"] = sign if passes else None
        row["net_degrees"] = degrees
        row["preimage_multiplicities"] = [
            len(target["positive_hits"]) + len(target["negative_hits"])
            for target in result["targets"]
        ]
    controls["hedgehog_sign"] = common_sign
    controls["all_pass"] = bool(
        controls["vacuum"]["passes"]
        and all(row["passes"] for row in controls["hedgehogs"].values())
        and controls["pair"]["passes"]
        and controls["orientation_reversal"]["passes"]
        and controls["reproducibility"]["passes"]
    )
    return controls


def compare_runs(
    left: dict[str, Any],
    right: dict[str, Any],
    tolerance: float,
    nsites: int,
) -> dict[str, Any]:
    left_rows = {row["t"]: row for row in left["snapshots"]}
    right_rows = {row["t"]: row for row in right["snapshots"]}
    common = sorted(set(left_rows) & set(right_rows))
    rows: list[dict[str, Any]] = []
    passes = bool(common and common[-1] == 4.0)
    basis = independent.primitive_basis(nsites, independent.L_DEFAULT)
    for time in common:
        first, second = left_rows[time], right_rows[time]
        state_agrees = first["pair_pass"] == second["pair_pass"]
        separation_difference = None
        centre_differences = None
        metric_pass = True
        if first["pair_pass"] and second["pair_pass"]:
            separation_difference = abs(
                float(first["separation"]) - float(second["separation"])
            )
            centre_differences = {}
            for label in ("positive", "negative"):
                delta = np.asarray(first["cluster_centres"][label]) - np.asarray(
                    second["cluster_centres"][label]
                )
                primitive = np.linalg.solve(basis, delta)
                primitive -= nsites * np.round(primitive / nsites)
                centre_differences[label] = float(
                    np.linalg.norm(basis @ primitive)
                )
            metric_pass = bool(
                separation_difference <= tolerance
                and all(value <= tolerance for value in centre_differences.values())
            )
        row_pass = bool(state_agrees and metric_pass)
        rows.append(
            {
                "t": time,
                "state_agrees": state_agrees,
                "separation_difference": separation_difference,
                "centre_differences": centre_differences,
                "passes": row_pass,
            }
        )
        passes = passes and row_pass
    return {
        "tolerance": tolerance,
        "common_times": common,
        "rows": rows,
        "passes": bool(passes),
    }


def verify(primary_path: Path, output: Path) -> dict[str, Any]:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise independent.VerificationError("--output must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    primary = independent.load_json(primary_path)
    if primary.get("schema") != PRIMARY_SCHEMA:
        raise independent.VerificationError("primary schema mismatch")

    sources = primary.get("sources")
    expected_sources = {
        relative(PRIMARY): independent.sha256(PRIMARY),
        relative(PRIMARY_ENGINE): independent.sha256(PRIMARY_ENGINE),
        relative(PROTOCOL): independent.sha256(PROTOCOL),
        relative(independent.SOLVER): independent.sha256(independent.SOLVER),
    }
    if not isinstance(sources, Mapping) or dict(sources) != expected_sources:
        raise independent.VerificationError("primary source identities mismatch")
    if primary.get("protocol_sha256") != protocol_sha256():
        raise independent.VerificationError("protocol hash mismatch")

    parameters = primary.get("parameters")
    expected_parameters = {
        "mu": independent.MU,
        "coefficient_tolerance": independent.TAU_C,
        "determinant_tolerance": independent.TAU_D,
        "edge_angle_limit": independent.EDGE_LIMIT,
        "targets": independent.targets().tolist(),
        "tetrahedra": [
            [independent.CUBE_OFFSETS[index].astype(int).tolist() for index in tet]
            for tet in independent.TETS
        ],
        "trajectory_directories": {
            name: row["input_directory"]
            for name, row in primary.get("trajectories", {}).items()
        },
    }
    if not isinstance(parameters, Mapping) or not independent.equal(
        parameters, expected_parameters
    ):
        raise independent.VerificationError("frozen parameters mismatch")

    controls = net_controls()
    trajectories_list = independent.reconstruct_trajectories(primary, primary_path.parent)
    trajectories = {
        str(row["name"]): {key: value for key, value in row.items() if key != "name"}
        for row in trajectories_list
    }
    if set(trajectories) != {"impulse_N48", "impulse_N48_halfdt", "impulse_N64"}:
        raise independent.VerificationError("trajectory set mismatch")
    timestep = compare_runs(
        trajectories["impulse_N48"],
        trajectories["impulse_N48_halfdt"],
        0.25,
        48,
    )
    refinement = compare_runs(
        trajectories["impulse_N48"], trajectories["impulse_N64"], 0.50, 48
    )
    admissibility = all(
        snapshot["admissible"] and not snapshot["ambiguous"]
        for trajectory in trajectories.values()
        for snapshot in trajectory["snapshots"]
    )
    degree_conservation = all(
        trajectory["degree_conservation"] for trajectory in trajectories.values()
    )
    formation = bool(trajectories["impulse_N64"]["formation"])
    persistence = bool(trajectories["impulse_N64"]["persistence"])
    gates = {
        "controls": controls["all_pass"],
        "admissibility": admissibility,
        "degree_conservation": degree_conservation,
        "time_step_agreement": timestep,
        "spatial_refinement": refinement,
        "formation_N64": formation,
        "persistence_N64": persistence,
    }
    if (
        not controls["all_pass"]
        or not admissibility
        or not timestep["passes"]
        or not refinement["passes"]
        or not degree_conservation
    ):
        verdict = "INCONCLUSIVE"
    elif not formation or not persistence:
        verdict = "DOES NOT EMERGE"
    else:
        verdict = "EMERGES CONDITIONAL"

    failures: list[str] = []
    for label, observed, reconstructed in (
        ("controls", primary.get("controls"), controls),
        ("trajectories", primary.get("trajectories"), trajectories),
        ("gates", primary.get("gates"), gates),
        ("verdict", primary.get("verdict"), verdict),
    ):
        if not independent.equal(observed, reconstructed):
            failures.append(label)
    reconstruction = {
        "controls": controls,
        "trajectories": trajectories,
        "gates": gates,
        "verdict": verdict,
    }
    if not independent.finite(reconstruction):
        raise independent.VerificationError("reconstruction is nonfinite")

    receipt = {
        "schema": SCHEMA,
        "primary_sha256": independent.sha256(primary_path),
        "protocol_sha256": protocol_sha256(),
        "sources": {
            relative(SELF): independent.sha256(SELF),
            relative(independent.SELF): independent.sha256(independent.SELF),
            relative(PROTOCOL): independent.sha256(PROTOCOL),
        },
        **reconstruction,
        "all_pass": not failures,
        "failures": failures,
    }
    with (output / "verification.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(independent.canonical(receipt), stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runs" / "20260907_matter_formation_geometric_degree_net" / "verification",
    )
    args = parser.parse_args()
    try:
        receipt = verify(args.primary.resolve(), args.output.resolve())
        print(json.dumps({"all_pass": receipt["all_pass"], "verdict": receipt["verdict"]}, allow_nan=False))
        return 0 if receipt["all_pass"] else 1
    except Exception as exc:
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": SCHEMA,
            "primary_sha256": independent.sha256(args.primary.resolve()) if args.primary.resolve().is_file() else None,
            "all_pass": False,
            "failures": [str(exc)],
            "verdict": "INCONCLUSIVE",
        }
        path = output / "verification.json"
        if not path.exists():
            path.write_text(
                json.dumps(independent.canonical(receipt), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
                encoding="utf-8",
            )
        print(json.dumps({"all_pass": False, "verdict": "INCONCLUSIVE", "failures": receipt["failures"]}, allow_nan=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
