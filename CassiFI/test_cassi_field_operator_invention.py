from __future__ import annotations

from pathlib import Path

from cassi_field_operator_invention import (
    _atom,
    _canonical_program,
    _mutations,
    _run_construction,
    _seed_scalars,
    _synthetic_arm,
    calibration_controls,
)
from cassi_research_organism import ResearchOrganism


def test_operator_calibrations_recover_four_known_worlds() -> None:
    controls = calibration_controls()
    assert {controls[name]["status"] for name in ("harmonic", "drag", "normal", "mixed")} == {"PASS"}
    assert controls["canonicalization"]["status"] == "PASS"
    assert controls["canonicalization"]["semantic_cosine"] >= 0.999999999999


def test_typed_seed_and_mutation_language_is_canonical_and_bounded() -> None:
    seeds = _seed_scalars()
    assert len(seeds) == 25
    assert _canonical_program(
        {"op": "multiply", "args": [_atom("one"), _atom("q")]}
    ) == _atom("q")
    mutations = _mutations(_atom("radial_speed"))
    assert 2 <= len(mutations) <= 32
    assert _atom("radial_speed") in mutations


def test_field_selection_controls_recursive_lineage_without_program_disclosure() -> None:
    class ChoosingField:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def select_laboratory_candidate(self, **request: object) -> dict[str, object]:
            candidates = request["candidates"]
            assert isinstance(candidates, list)
            assert 2 <= len(candidates) <= 32
            assert all("equation" not in candidate for candidate in candidates)
            selected = min(
                candidates,
                key=lambda candidate: (
                    -float(candidate["development_score"]),
                    str(candidate["candidate_id"]),
                ),
            )
            self.calls.append(request)
            return {
                "campaign_id": request["campaign_id"],
                "laboratory_id": request["laboratory_id"],
                "candidate_id": selected["candidate_id"],
                "selection_record_id": f"selection:{len(self.calls)}",
                "holdout_visible_during_selection": False,
            }

    field = ChoosingField()
    fit = [_synthetic_arm("mixed", arm_id="fit")]
    validation = [_synthetic_arm("mixed", arm_id="validation")]
    construction = _run_construction(
        field,
        campaign_id="typed-construction-control",
        fit_arms=fit,
        validation_arms=validation,
    )
    assert len(field.calls) == 9
    assert len(construction["selection_records"]) == 9
    for frame in ("radial", "flow", "transverse", "normal"):
        mutation = construction["mutation_phase"][frame]
        assert mutation["parent_candidate"] == construction["seed_phase"][frame]["selection"]["candidate_id"]
    selected = construction["synthesis_candidates"][construction["final_selection"]["candidate_id"]]
    assert selected["validation_mean_nrmse"] <= 0.05

def test_operator_runtime_is_in_organism_source_closure(tmp_path: Path) -> None:
    workspace = Path(__file__).resolve().parents[1]
    organism = ResearchOrganism(tmp_path / "organism", workspace=workspace)
    source_paths = organism.initialize()["manifest"]["source_paths"]
    assert "CassiFI/cassi_field_operator_invention.py" in source_paths
    assert "CassiFI/run_cassi_field_operator_invention.py" in source_paths
    assert "CassiFI/verify_cassi_field_operator_invention.py" in source_paths
