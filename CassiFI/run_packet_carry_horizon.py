"""Measure how long a bounded packet deposit stays readable in the field.

The temporal leg of the packet program needs one number that exists nowhere
today: at the declared clock, how many ticks a deposited cue survives above the
read gate. This runner deposits one bounded impulse into one scale mode, then
relaxes the field unforced and reads the packet after every tick.

It declares no temporal interface and makes no scheduling claim. It reports the
measured carry series, the tick at which each relative gate is crossed, and the
fitted relaxation rate, so a delay set can be chosen from measured behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from cassi_resonant_field import (
    ResonantProfile,
    advance_workspace,
    analyze_helical_packet,
    apply_helical_packet_impulse,
    helical_packet_channels,
    initial_workspace,
)

SCHEMA = "cassifi.packet-carry-horizon.v1"
GATES = (("e", 1.0 / math.e), ("0.1", 0.1), ("0.01", 0.01))
TICKS_OF_INTEREST = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)
# A local fit over a short window describes that window only; below this many
# ticks the probe reports no fitted rate rather than extrapolating one.
FIT_MIN_TICKS = 64
SCALE_PATH = "L"


def amplitude(workspace) -> tuple[float, float]:
    """Return the packet mode norm and the reconstructed channel norm."""

    packet = analyze_helical_packet(workspace, path=SCALE_PATH)
    coefficients = np.asarray(packet["coefficients"], dtype=np.float64)
    channels = helical_packet_channels(packet)
    return float(np.linalg.norm(coefficients)), float(np.linalg.norm(channels))


def run(ticks: int, budget: float, deposit: bool, profile: ResonantProfile):
    workspace = initial_workspace(profile)
    before_tick = workspace.evidence_tick
    receipt = None
    if deposit:
        workspace, receipt = apply_helical_packet_impulse(
            workspace,
            path=SCALE_PATH,
            component="scale",
            flow_signal=(1.0, 0.0),
            work_budget=budget,
            evidence_tick=before_tick,
            event_kind="reasoning-work",
        )
    mode_now, channel_now = amplitude(workspace)
    deposited_state_sha256 = workspace.state_sha256
    baseline = mode_now
    readable = baseline > 0.0
    series = [
        {
            "tick": 0,
            "mode_norm": mode_now,
            "channel_norm": channel_now,
            "relative": 1.0 if readable else None,
        }
    ]
    for tick in range(1, ticks + 1):
        workspace, step_receipt = advance_workspace(
            workspace, ticks=1, source_enabled=False
        )
        mode_now, channel_now = amplitude(workspace)
        series.append(
            {
                "tick": tick,
                "mode_norm": mode_now,
                "channel_norm": channel_now,
                # A silent arm has no relative amplitude: null, never 0, so it
                # cannot read as an arm that fell below every gate.
                "relative": mode_now / baseline if readable else None,
                "dissipated_work": float(step_receipt.get("dissipated_work", 0.0)),
            }
        )
    relative_all = [row["relative"] for row in series]
    crossings: dict[str, dict[str, Any]] = {}
    for name, gate in GATES:
        below = (
            [row["tick"] for row in series if row["relative"] <= gate]
            if readable
            else []
        )
        transitions_down = 0
        transitions_up = 0
        if readable:
            for earlier, later in zip(relative_all, relative_all[1:]):
                if earlier > gate >= later:
                    transitions_down += 1
                elif earlier <= gate < later:
                    transitions_up += 1
        crossings[name] = {
            "applicable": readable,
            "first_below": below[0] if below else None,
            "last_below": below[-1] if below else None,
            "below_samples": len(below),
            "transitions_down": transitions_down if readable else None,
            "transitions_up": transitions_up if readable else None,
        }
    relative = [value for value in relative_all if value is not None]
    monotonic = (
        all(
            earlier >= later - 1e-9
            for earlier, later in zip(relative, relative[1:])
        )
        if readable
        else None
    )
    retention = (
        {
            str(tick): series[tick]["relative"]
            for tick in TICKS_OF_INTEREST
            if tick < len(series)
        }
        if readable
        else None
    )
    finite = [
        row
        for row in series
        if row["tick"] > 0 and row["mode_norm"] > 0.0 and row["relative"] > 1e-12
    ]
    fitted_rate = None
    if len(finite) >= 2:
        ticks_axis = np.asarray([row["tick"] for row in finite], dtype=np.float64)
        log_axis = np.log(np.asarray([row["relative"] for row in finite]))
        slope = float(np.polyfit(ticks_axis, log_axis, 1)[0])
        fitted_rate = -slope
    return {
        "deposit": deposit,
        "work_budget": budget if deposit else 0.0,
        "deposit_receipt": receipt,
        "deposited_state_sha256": deposited_state_sha256,
        "final_state_sha256": workspace.state_sha256,
        "initial_mode_norm": series[0]["mode_norm"],
        "series": series,
        "gate_crossings": crossings,
        "retention": retention,
        "readable_signal": readable,
        "relative_series_is_monotonic": monotonic,
        "relative_min": min(relative) if readable else None,
        "relative_max": max(relative) if readable else None,
        "fitted_relaxation_rate_per_tick": fitted_rate
        if (monotonic and ticks >= FIT_MIN_TICKS)
        else None,
        "fitted_carry_ticks_to_1e": (1.0 / fitted_rate)
        if (monotonic and ticks >= FIT_MIN_TICKS and fitted_rate and fitted_rate > 0.0)
        else None,
        "fit_withheld_reason": (
            None
            if (monotonic and ticks >= FIT_MIN_TICKS)
            else (
                "short window"
                if ticks < FIT_MIN_TICKS
                else "relative series is not monotone"
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticks", type=int, default=64)
    parser.add_argument("--budget", type=float, default=0.25)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.ticks < 1:
        raise SystemExit("--ticks must be at least 1")
    if not 0.0 < arguments.budget <= 1.0:
        raise SystemExit("--budget must be in (0,1]")

    profile = ResonantProfile()
    deposited = run(arguments.ticks, arguments.budget, True, profile)
    control = run(arguments.ticks, arguments.budget, False, profile)
    payload = {
        "schema": SCHEMA,
        "profile": {
            "port_count": int(profile.port_count),
            "ports_per_pool": int(profile.ports_per_pool),
            "layout_identity": str(profile.layout_identity),
        },
        "path": SCALE_PATH,
        "component": "scale",
        "event_kind": "reasoning-work",
        "ticks": arguments.ticks,
        "source_enabled": False,
        "deposited": {
            key: value
            for key, value in deposited.items()
            if key != "series"
        },
        "control_no_deposit": {
            key: value for key, value in control.items() if key != "series"
        },
        "series": deposited["series"],
        "control_series": control["series"],
        "reading": {
            "deposited_readable": deposited["readable_signal"],
            "control_readable": control["readable_signal"],
            "retention_at": deposited["retention"],
            "gate_crossings": deposited["gate_crossings"],
            "relative_series_is_monotonic": deposited["relative_series_is_monotonic"],
            "relative_min": deposited["relative_min"],
            "relative_max": deposited["relative_max"],
            "fitted_carry_ticks_to_1e": deposited["fitted_carry_ticks_to_1e"],
            "fit_withheld_reason": deposited["fit_withheld_reason"],
            "control_amplitude": control["initial_mode_norm"],
            "deposited_amplitude": deposited["initial_mode_norm"],
            "control_is_silent": control["initial_mode_norm"] == 0.0,
            "oscillatory": not deposited["relative_series_is_monotonic"],
        },
    }
    if not deposited["readable_signal"]:
        raise RuntimeError(
            "the deposit produced no readable packet: the carry measurement is void"
        )
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    payload["receipt_sha256"] = hashlib.sha256(body).hexdigest()
    text = json.dumps(payload, indent=1, sort_keys=True)
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text, encoding="utf-8")
    print(json.dumps(payload["reading"], indent=1, sort_keys=True))
    if arguments.output is not None:
        print(f"receipt: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
