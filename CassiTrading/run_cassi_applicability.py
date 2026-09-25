from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_applicability import (
    RegimeConditionedEvaluator,
    ProgramBinding,
    contexts_from_market_observations,
    program_from_contract_dict,
)
from cassi_market_contracts import digest_value
from cassi_program_synthesizer import ProgramSynthesizer
from cassi_skill_bundle import build_skill_bundle, skill_contracts_from_bundle
from cassi_trading_foundry import generate_demo_bars
from cassi_world_model import MarketWorldModel


RUNNER_SCHEMA = "cassi.market-regime-applicability-run.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run regime-conditioned Cassi program applicability")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-applicability-v1.json"))
    parser.add_argument("--bars", type=int, default=64)
    args = parser.parse_args()
    if args.bars < 32:
        raise SystemExit("--bars must be >= 32")

    events = tuple(
        bar.as_event(source_id="applicability-runner", source_revision="demo-bars.v1")
        for bar in generate_demo_bars(args.bars)
    )
    world = MarketWorldModel()
    world_update = world.update(events)
    bundle = build_skill_bundle()
    skills = skill_contracts_from_bundle(bundle)
    synthesis = ProgramSynthesizer().synthesize(
        [skills[1]],
        task_id="regime-conditioned-program",
        evidence_roots=(f"world:{world.snapshot()['content_sha256']}",),
    )
    program = program_from_contract_dict(synthesis["selected"]["program"])
    contexts = contexts_from_market_observations(events, world.observations, config=world.config)
    allowed_regimes = tuple(sorted({context.regime_id for context in contexts if context.regime_id != "regime:warming"}))
    applicability = RegimeConditionedEvaluator().evaluate(
        program,
        ProgramBinding(
            binding_id="p1-trend-coordinate",
            allowed_regimes=allowed_regimes,
            parameter_map={"value": "trend"},
            constants={},
        ),
        contexts,
    )
    body = {
        "schema": RUNNER_SCHEMA,
        "source_event_count": len(events),
        "world_update": world_update,
        "world_snapshot": world.snapshot(),
        "selected_program": synthesis["selected"],
        "applicability": applicability,
        "event_root_sha256": digest_value([event.as_dict() for event in events]),
    }
    body["content_sha256"] = digest_value(body)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": body["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
