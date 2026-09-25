from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_market_contracts import digest_value
from cassi_program_synthesizer import ProgramSynthesizer, SynthesisBudget, SYNTHESIS_SCHEMA
from cassi_skill_bundle import build_skill_bundle, skill_contracts_from_bundle


RUNNER_SCHEMA = "cassi.market-program-synthesis-run.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded Cassi market program synthesizer")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-program-synthesis-v1.json"))
    parser.add_argument("--task-id", default="math-capability-frontier")
    parser.add_argument("--max-candidates", type=int, default=32)
    args = parser.parse_args()

    bundle = build_skill_bundle()
    skills = skill_contracts_from_bundle(bundle)
    contract_digest = digest_value([skill.as_dict() for skill in skills])
    synthesis = ProgramSynthesizer(
        budget=SynthesisBudget(max_candidates=args.max_candidates),
    ).synthesize(
        skills,
        task_id=args.task_id,
        evidence_roots=(f"capability-bundle:{bundle['content_sha256']}",),
    )
    body = {
        "schema": RUNNER_SCHEMA,
        "mode": "capability-closure-only",
        "synthesis_schema": SYNTHESIS_SCHEMA,
        "capability_bundle_sha256": bundle["content_sha256"],
        "skill_contract_sha256": contract_digest,
        "skill_count": len(skills),
        "synthesis": synthesis,
    }
    body["content_sha256"] = digest_value(body)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": body["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
