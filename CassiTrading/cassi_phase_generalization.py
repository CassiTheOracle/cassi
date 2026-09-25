"""Run the prospective field-phase predictor on multiple source regimes."""

from __future__ import annotations

from typing import Any

from cassi_market_contracts import digest_value
from cassi_market_scenarios import SCENARIO_PROFILES, build_scenario_manifest, generate_scenario_bars
from cassi_source_order_match import run_source_order_match
from cassi_trading_foundry import RefinementField

PHASE_GENERALIZATION_SCHEMA = "cassi.native-phase-generalization.v1"


def _replay_readout(outcomes: tuple[str, ...]) -> dict[str, Any]:
    field = RefinementField()
    for outcome in outcomes:
        field.learn_program("edge", "synthesized-transfer-program", outcome, repeats=1)
    return {
        "readout": field.predict_program("edge", "synthesized-transfer-program"),
        "field_sha256": field.fingerprint(),
    }

def run_phase_generalization(*, bar_count: int = 352) -> dict[str, Any]:
    cases = {
        "positive_jump": {
            "source_instrument": "JUMP",
            "source_profile": "positive_jump",
            "target_instruments": ("TREND", "REVERSAL", "VOLATILE"),
            "target_profiles": {
                "TREND": "trend",
                "REVERSAL": "reversal",
                "VOLATILE": "volatile",
            },
        },
        "reversal": {
            "source_instrument": "REVERSAL",
            "source_profile": "reversal",
            "target_instruments": ("TREND", "MEAN", "VOLATILE"),
            "target_profiles": {
                "TREND": "trend",
                "MEAN": "mean_revert",
                "VOLATILE": "volatile",
            },
        },
        "volatile": {
            "source_instrument": "VOLATILE",
            "source_profile": "volatile",
            "target_instruments": ("TREND", "REVERSAL", "MEAN"),
            "target_profiles": {
                "TREND": "trend",
                "REVERSAL": "reversal",
                "MEAN": "mean_revert",
            },
        },
    }
    results: dict[str, Any] = {}
    for name, case in cases.items():
        assignments = {
            case["source_instrument"]: SCENARIO_PROFILES[case["source_profile"]],
            **{
                instrument: SCENARIO_PROFILES[profile]
                for instrument, profile in case["target_profiles"].items()
            },
        }
        bars = {
            instrument: generate_scenario_bars(bar_count, symbol=instrument, profile=profile)
            for instrument, profile in assignments.items()
        }
        results[name] = {
            "source_manifest": build_scenario_manifest(assignments, bar_count=bar_count),
            "phase_receipt": run_source_order_match(
                bars,
                source_instrument=case["source_instrument"],
                target_instruments=case["target_instruments"],
            ),
        }
    original = tuple(results["positive_jump"]["phase_receipt"]["matches"][4]["source_lesson_outcomes"])
    mutated = ("reject",) + original[1:]
    original_replay = _replay_readout(original)
    mutated_replay = _replay_readout(mutated)
    body: dict[str, Any] = {
        "schema": PHASE_GENERALIZATION_SCHEMA,
        "bar_count": bar_count,
        "cases": results,
        "mutation_control": {
            "original_outcomes": list(original),
            "mutated_outcomes": list(mutated),
            "original_replay": original_replay,
            "mutated_replay": mutated_replay,
            "predicted_authority_changed": (
                original_replay["readout"].get("status") == "supported"
                and original_replay["readout"].get("outcome") == "promote"
                and not (
                    mutated_replay["readout"].get("status") == "supported"
                    and mutated_replay["readout"].get("outcome") == "promote"
                )
            ),
        },
        "controls": {
            "source_window_counts": list(range(1, 9)),
            "prospective_readout_precedes_target_arms": True,
            "exact_replay_required": True,
            "mutation_control_must_fire": True,
        },
    }
    body["content_sha256"] = digest_value(body)
    return body


__all__ = ["PHASE_GENERALIZATION_SCHEMA", "run_phase_generalization"]
