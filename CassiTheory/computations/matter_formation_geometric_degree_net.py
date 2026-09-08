#!/usr/bin/env python3
"""Primary net-degree adjudication of retained chiral-lattice formation fields."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matter_formation_geometric_degree as base

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "matter-formation-geometric-degree-net-prereg.md"
SCHEMA = "matter-formation-geometric-degree-net-v1"


def protocol_sha256() -> str:
    text = PROTOCOL.read_text(encoding="utf-8")
    begin = "<!-- geometric-net-degree-protocol:start -->"
    end = "<!-- geometric-net-degree-protocol:end -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError("net-degree protocol markers are missing or duplicated")
    frozen = text.split(begin, 1)[1].split(end, 1)[0]
    return hashlib.sha256(frozen.encode("utf-8")).hexdigest()


def net_control_suite(target_values: Any, radial: Any) -> dict[str, Any]:
    controls = base.control_suite(target_values, radial)
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
    )
    return controls


def run(output: Path) -> dict[str, Any]:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"--output must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    target_values = base.targets()
    radial = base.radial_profile()
    controls = net_control_suite(target_values, radial)
    repeated = net_control_suite(target_values, radial)
    reproducible = base.canonical(controls) == base.canonical(repeated)
    controls["reproducibility"] = {"passes": reproducible}
    controls["all_pass"] = bool(controls["all_pass"] and reproducible)

    trajectories = {
        name: base.load_trajectory(name, directory, target_values)
        for name, directory in base.TRAJECTORY_DIRS.items()
    }
    timestep = base.compare_trajectories(
        trajectories["impulse_N48"],
        trajectories["impulse_N48_halfdt"],
        tolerance=0.25,
        nsites=48,
        basis=base.basis_matrix(48, 18.0),
    )
    refinement = base.compare_trajectories(
        trajectories["impulse_N48"],
        trajectories["impulse_N64"],
        tolerance=0.50,
        nsites=48,
        basis=base.basis_matrix(48, 18.0),
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

    source_paths = (SELF, PROTOCOL, base.SOLVER, Path(base.__file__).resolve())
    payload = {
        "schema": SCHEMA,
        "sources": {base.relative(path): base.sha256(path) for path in source_paths},
        "protocol_file": base.relative(PROTOCOL),
        "protocol_sha256": protocol_sha256(),
        "parameters": {
            "mu": base.MU,
            "coefficient_tolerance": base.TAU_COEFFICIENT,
            "determinant_tolerance": base.TAU_DETERMINANT,
            "edge_angle_limit": base.EDGE_LIMIT,
            "targets": target_values.tolist(),
            "tetrahedra": base.TETRAHEDRA,
            "trajectory_directories": {
                name: base.relative(path) for name, path in base.TRAJECTORY_DIRS.items()
            },
        },
        "controls": controls,
        "trajectories": trajectories,
        "gates": gates,
        "verdict": verdict,
        "scientific_scope": (
            "This net-degree qualification concerns the retained classical impulse in the "
            "supplied massive chiral action. It does not select a canonical Cassi action, "
            "quantum state, renormalization, statistics or particle identity."
        ),
    }
    with (output / "results.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runs" / "20260907_matter_formation_geometric_degree_net" / "primary",
    )
    args = parser.parse_args()
    payload = run(args.output.resolve())
    print(json.dumps({"verdict": payload["verdict"], "gates": payload["gates"]}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
