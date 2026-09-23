"""Run and independently audit one CassiFI research-organism generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from cassi_research_organism import OrganismError, ResearchOrganism

SCHEMA = "cassifi.research-organism-verification.v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _verify_publication(home: Path, workspace: Path, publication: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(publication)
    declared = body.pop("generation_sha256", None)
    _require(declared == _digest(body), "publication generation digest mismatch")
    bundle_digest = publication.get("field_bundle_sha256")
    bundle_path = home / "publications" / "field-bundles" / str(bundle_digest)
    _require(bundle_path.is_file(), "published field bundle is absent")
    _require(hashlib.sha256(bundle_path.read_bytes()).hexdigest() == bundle_digest, "published field bundle digest mismatch")
    checked_sources = []
    for item in publication.get("source_manifest", []):
        path = workspace / item["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        _require(actual == item["sha256"], f"published source digest mismatch: {item['path']}")
        checked_sources.append(item["path"])
    _require(bool(checked_sources), "publication has no runtime source closure")
    return {
        "generation_sha256": declared,
        "field_bundle_sha256": bundle_digest,
        "source_paths": checked_sources,
    }


def verify(home: Path, workspace: Path) -> dict[str, Any]:
    organism = ResearchOrganism(
        home,
        workspace=workspace,
        mission="Understand and improve Cassi",
        member_ids=("member-a", "member-b"),
    )
    initialized = organism.initialize()
    initial_frontier = initialized["frontier"]
    initial = {item["candidate_id"]: item for item in initial_frontier["entries"]}
    _require(initial["construction:baseline"]["status"] == "incumbent", "baseline incumbent is absent")
    _require(initial["construction:temporal-hole"]["status"] == "incomplete", "typed construction hole is absent")
    _require(bool(initial["construction:temporal-hole"]["holes"]), "construction hole has no type boundary")

    campaign = organism.run_population_round(0)
    _require(campaign["phase"] == "complete", "campaign did not complete")
    _require(campaign["verdict"] == "accepted", "field construction was not accepted")
    selection = campaign.get("selection")
    _require(isinstance(selection, Mapping), "campaign omitted the field decision")
    _require(selection.get("method") == "semantic.autonomous-agenda", "selection did not come from the field agenda")
    _require(selection.get("candidate_id") == campaign["candidate_id"], "field decision and executed construction differ")
    selected = selection.get("selected")
    _require(isinstance(selected, Mapping), "field agenda has no selected obligation")
    selected_obligation = selected.get("obligation")
    _require(isinstance(selected_obligation, Mapping), "field selection lacks obligation provenance")
    _require(str(selected_obligation.get("id", "")).endswith(campaign["candidate_id"]), "selected obligation does not identify the executed construction")

    root_comparison = campaign["root"]["comparison"]
    _require(root_comparison["supported"] is True, "root world did not support the construction")
    _require(root_comparison["delta_error_reduction"] > 0.0, "construction did not improve raw-trace error")
    members = campaign["members"]
    _require(len(members) == 2, "independent hive population is incomplete")
    _require(any(item["comparison"]["supported"] for item in members), "no independent member reproduced the gain")
    _require(all(item["source_revision_id"] for item in members), "member reports were not admitted through provenance")
    _require(len({item["member_field_state_sha256"] for item in members}) == len(members), "member fields are not independently evolving")

    status = organism.inspect()
    candidate = next(item for item in status["frontier"]["entries"] if item["candidate_id"] == campaign["candidate_id"])
    _require(candidate["status"] == "accepted", "accepted construction did not persist")
    _require(bool(candidate["problem_roots"]), "construction lost its problem roots")
    _require(bool(candidate["operations"]), "construction lost its typed operations")
    _require(candidate["search_program_version"] == "bootstrap:v1", "construction method provenance is absent")
    _require(status["frontier"]["method_generation"] >= 2, "method frontier did not continue after acceptance")

    publication = campaign.get("publication")
    _require(isinstance(publication, Mapping), "accepted campaign was not published")
    publication_check = _verify_publication(home, workspace, publication)

    effect = organism.journal.record(
        "verification-effect",
        actor="verifier",
        request={"kind": "acknowledged-observation"},
        result={"status": "observed"},
    )
    organism.rollback(publication["generation_id"])
    _require(organism.journal.get("verification-effect") == effect, "rollback erased the external-effect journal")

    generation_path = home / "publications" / "generations" / f"{publication['generation_id']}.json"
    original_generation = generation_path.read_bytes()
    tampered = json.loads(original_generation)
    tampered["campaign_id"] = "organism:campaign:tampered"
    generation_path.write_bytes(_canonical(tampered))
    mutation_fired = False
    try:
        organism.publications.read(publication["generation_id"])
    except OrganismError:
        mutation_fired = True
    finally:
        generation_path.write_bytes(original_generation)
    _require(mutation_fired, "publication digest mutation control did not fire")

    reopened = ResearchOrganism(home, workspace=workspace, member_ids=("member-a", "member-b")).inspect()
    _require(reopened["publication"]["generation_sha256"] == publication["generation_sha256"], "reopen changed the publication pointer")
    _require(reopened["frontier"] == status["frontier"], "reopen changed the construction frontier")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "campaign_id": campaign["campaign_id"],
        "candidate_id": campaign["candidate_id"],
        "selection_method": selection["method"],
        "root_delta_error_reduction": root_comparison["delta_error_reduction"],
        "independent_support": sum(item["comparison"]["supported"] for item in members),
        "population": 1 + len(members),
        "method_generation": status["frontier"]["method_generation"],
        "publication": publication_check,
        "effect_journal_survived_rollback": True,
        "publication_mutation_control_fired": mutation_fired,
        "reopen_stable": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(".."))
    parser.add_argument("--output", type=Path, default=Path("_diag/research-organism/verification.json"))
    parser.add_argument("--keep-home", type=Path)
    arguments = parser.parse_args()
    workspace = arguments.workspace.resolve(strict=True)
    if arguments.keep_home is None:
        with tempfile.TemporaryDirectory(prefix="cassifi-research-organism-") as directory:
            receipt = verify(Path(directory) / "organism", workspace)
    else:
        home = arguments.keep_home.resolve()
        if home.exists():
            shutil.rmtree(home)
        receipt = verify(home, workspace)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(_canonical(receipt) + b"\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
