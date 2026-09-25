from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_applicability import (
    ProgramBinding,
    RegimeConditionedEvaluator,
    contexts_from_market_observations,
    program_from_contract_dict,
)
from cassi_market_contracts import Authority, digest_value
from cassi_policy import PortfolioController, PortfolioPolicyConfig, PortfolioState, ProgramSignal
from cassi_program_synthesizer import ProgramSynthesizer
from cassi_skill_bundle import build_skill_bundle, skill_contracts_from_bundle
from cassi_trading_foundry import generate_demo_bars
from cassi_world_model import MarketWorldModel


RUNNER_SCHEMA = "cassi.market-policy-run.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Cassi regime-conditioned portfolio policy")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-policy-v1.json"))
    parser.add_argument("--bars", type=int, default=64)
    parser.add_argument("--mode", choices=("research", "shadow", "authorized"), default="shadow")
    args = parser.parse_args()
    if args.bars < 32:
        raise SystemExit("--bars must be >= 32")

    events = tuple(
        bar.as_event(source_id="policy-runner", source_revision="demo-bars.v1")
        for bar in generate_demo_bars(args.bars)
    )
    world = MarketWorldModel()
    world_update = world.update(events)
    bundle = build_skill_bundle()
    skills = skill_contracts_from_bundle(bundle)
    synthesis = ProgramSynthesizer().synthesize(
        [skills[1]],
        task_id="portfolio-policy-program",
        evidence_roots=(f"world:{world.snapshot()['content_sha256']}",),
    )
    program = program_from_contract_dict(synthesis["selected"]["program"])
    contexts = contexts_from_market_observations(events, world.observations, config=world.config)
    allowed_regimes = tuple(sorted({context.regime_id for context in contexts if context.regime_id != "regime:warming"}))
    applicability = RegimeConditionedEvaluator().evaluate(
        program,
        ProgramBinding(
            binding_id="policy-trend-coordinate",
            allowed_regimes=allowed_regimes,
            parameter_map={"value": "trend"},
            constants={},
        ),
        contexts,
    )
    latest_context = contexts[-1]
    latest_row = applicability["rows"][-1]
    value = float(latest_row["value"]) if latest_row["status"] == "evaluated" else 0.0
    trend = float(latest_context.coordinates["trend"])
    signal = ProgramSignal(
        signal_id=f"signal:{latest_context.event_id}",
        program_id=program.program_id,
        instrument="DEMOUSD",
        regime_id=latest_context.regime_id,
        direction=0.0 if value == 0.0 else (1.0 if trend >= 0.0 else -1.0),
        expected_edge=abs(value),
        expected_risk=max(float(latest_context.coordinates["volatility"]), 1.0e-4),
        applicability_status=latest_row["status"] if latest_row["status"] in {"evaluated", "inapplicable", "error"} else "abstain",
        event_id=latest_context.event_id,
        observation_id=latest_context.observation_id,
        available_at=latest_context.available_at,
        support_roots=tuple(program.evidence_roots),
    )
    authority = Authority(
        mode=args.mode,
        objective_id="policy-runner-objective",
        permission_generation="policy-runner-permission-1",
        revocation_generation="policy-runner-revocation-1",
    )
    decision = PortfolioController(
        policy_id="demo-policy",
        config=PortfolioPolicyConfig(max_turnover=0.25),
        support_roots=(program.content_sha256, world.snapshot()["content_sha256"]),
    ).decide(
        PortfolioState(equity=1.0),
        (signal,),
        authority=authority,
        operation_id="policy-operation-1",
    )
    body = {
        "schema": RUNNER_SCHEMA,
        "source_event_count": len(events),
        "world_update": world_update,
        "world_snapshot": world.snapshot(),
        "selected_program": synthesis["selected"],
        "applicability": applicability,
        "signal": signal.as_dict(),
        "decision": decision,
        "event_root_sha256": digest_value([event.as_dict() for event in events]),
    }
    body["content_sha256"] = digest_value(body)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": body["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
