from __future__ import annotations

from pathlib import Path

import pytest

from cassi_equation_discovery import (
    EquationDiscoveryError,
    _candidate_id,
    _candidate_results,
    _field_tournament,
    _initial_speed,
    _metric_winner,
    _synthetic_statistics,
    calibration_controls,
)
from cassi_research_organism import ResearchOrganism


def test_known_world_calibrations_recover_the_registered_laws() -> None:
    controls = calibration_controls()
    assert controls["harmonic"]["status"] == "PASS"
    assert controls["harmonic"]["selected_support"] == [1.0]
    assert controls["inverse-square"]["status"] == "PASS"
    assert controls["inverse-square"]["selected_support"] == [-2.0]

def test_initial_speed_provenance_accepts_both_bound_receipt_shapes() -> None:
    assert _initial_speed({"geometry": {"initial_speed": 0.5}, "engine": {}}) == 0.5
    assert _initial_speed({"geometry": {}, "engine": {"initial_speed": 1.0}}) == 1.0
    with pytest.raises(EquationDiscoveryError, match="unavailable"):
        _initial_speed({"geometry": {}, "engine": {}})


def test_candidate_identity_is_content_addressed_and_field_contract_is_opaque() -> None:
    fit = [_synthetic_statistics(0.25, segment="fit")]
    validation = [_synthetic_statistics(0.25, segment="holdout")]
    candidates = _candidate_results(fit, validation)
    winner = _metric_winner(candidates)
    assert winner == _candidate_id((0.25,))
    assert candidates[winner]["validation_mean_nrmse"] <= 1e-10

    class ChoosingField:
        def __init__(self) -> None:
            self.calls: list[list[dict[str, object]]] = []

        def select_laboratory_candidate(self, **request: object) -> dict[str, object]:
            rows = request["candidates"]
            assert isinstance(rows, list)
            assert all("support" not in row and "coefficients" not in row for row in rows)
            self.calls.append(rows)
            selected = max(rows, key=lambda row: (float(row["development_score"]), str(row["candidate_id"])))
            return {
                "campaign_id": request["campaign_id"],
                "laboratory_id": request["laboratory_id"],
                "candidate_id": selected["candidate_id"],
                "selection_record_id": f"selection:{len(self.calls)}",
                "holdout_visible_during_selection": False,
            }

    field = ChoosingField()
    selected, selections = _field_tournament(
        field,
        campaign_id="calibration-campaign",
        candidates=candidates,
    )
    assert selected == winner
    assert len(selections) > 1
    assert max(len(call) for call in field.calls) <= 32


def test_equation_runtime_is_in_the_organism_source_closure(tmp_path: Path) -> None:
    workspace = Path(__file__).resolve().parents[1]
    organism = ResearchOrganism(tmp_path / "organism", workspace=workspace)
    source_paths = organism.initialize()["manifest"]["source_paths"]
    assert "CassiFI/cassi_equation_discovery.py" in source_paths
    assert "CassiFI/run_cassi_equation_discovery.py" in source_paths
    assert "CassiFI/verify_cassi_equation_discovery.py" in source_paths
