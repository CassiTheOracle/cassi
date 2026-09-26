from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from run_cassi_hive_adversarial_campaign import run_campaign


def test_adversarial_campaign_exercises_collective_path() -> None:
    with TemporaryDirectory() as tmp:
        report = run_campaign(Path(tmp) / "campaign-hive")
    assert report["audit"]["clean"] is True
    assert report["identity"]["attested"] is True
    assert report["hypothesis"]["contradiction_count"] == 1
    assert report["live_adoption"]["member_count"] == 3
    assert report["live_adoption"]["adopted_count"] == 3
    assert report["live_adoption"]["adopted_program_ids"] == [
        "composed-program",
        "composed-program-v2",
    ]
    assert all(
        member["adoption_status"] == "accepted"
        for member in report["live_adoption"]["members"]
    )
    assert report["population_outcome"]["ledger_id"] == report["live_adoption"]["ledger_id"]
    assert report["population_outcome"]["round_count"] == 2
    assert report["population_outcome"]["round_ledger_id"] == report["population_rounds"]["object_id"]
    assert report["population_outcome"]["success"] is True
    assert report["population_outcome"]["coverage"] == 1.0
    assert report["population_rounds"]["status"] == "accepted"
    assert all(
        len(round_report["comparisons"]) == 3
        for round_report in report["population_rounds"]["rounds"]
    )
    assert report["memory"]["source_count"] == 2
    assert report["bridge"]["event_id"]
