"""Focused tests for the bounded canonical L/LL parent-register map."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

import cassi_resonant_field as field
import run_fractal_parent_summary_nested_exploration as runner


@pytest.fixture(scope="module")
def receipt() -> dict:
    built = runner.build_receipt()
    assert built["verdict"] == "PASS_FIELD_OWNED_NESTED_PARENT_REGISTERS"
    assert runner.verify_receipt(built)["content_digest_matches"]
    return built


def test_atomic_relation_and_frozen_continuity(receipt: dict) -> None:
    assert receipt["write"]["paths"] == ["L", "LL"]
    assert receipt["effects"]["same_source_capture_group"]
    assert receipt["effects"]["path_prefix_proven"]
    assert receipt["effects"]["support_containment_proven"]
    assert receipt["effects"]["reproduced_frozen_live_L_drift"]
    assert receipt["effects"]["reproduced_frozen_noop_drift"]


def test_registers_survive_source_off_and_LL_only_correction(receipt: dict) -> None:
    assert receipt["source_off_advance"]["source_enabled"] is False
    assert receipt["effects"]["stored_L_equal_after_LL_correction"]
    assert receipt["effects"]["stored_LL_equal_after_LL_correction"]
    assert receipt["effects"]["LL_correction_changes_successor_state"]
    assert receipt["effects"]["checkpoint_direct_read_equal"]


def test_relation_and_source_mutation_controls_fire(receipt: dict) -> None:
    for name in ("relation_digest_mutation", "source_digest_mutation"):
        control = receipt["controls"][name]
        assert control["attempted"] and control["can_fail"] and not control["accepted"]
        assert control["error_type"] == "ResonantNumericalError"


def test_partial_and_duplicate_paths_fail_closed() -> None:
    workspace = field.initial_workspace()
    with pytest.raises(field.ResonantNumericalError):
        field.write_parent_registers(workspace, paths=("L", "L"))
    with pytest.raises(field.ResonantNumericalError):
        field.write_parent_registers(workspace, paths=("L",), ancestry_pairs=(("L", "LL"),))
    stored, _ = field.write_parent_registers(workspace, paths=("L",))
    with pytest.raises(field.ResonantNumericalError, match="already active"):
        field.write_parent_registers(stored, paths=("L",))


def test_direct_reads_are_page_owned_and_roundtrip() -> None:
    workspace = field.initial_workspace()
    stored, _ = field.write_parent_registers(workspace, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),))
    before = field.read_parent_registers(stored)
    checkpoint = field.ResonantWorkspace.from_dict(stored.as_dict())
    assert field.read_parent_registers(checkpoint) == before
    original = field.analyze_helical_packet
    field.analyze_helical_packet = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("live analyzer called"))
    try:
        assert field.read_parent_register(stored, "L")["values"] == before["slots"]["L"]["values"]
        assert field.read_parent_register(stored, "LL")["values"] == before["slots"]["LL"]["values"]
    finally:
        field.analyze_helical_packet = original



def test_marker_partial_and_unsupported_map_mutations_fail_closed() -> None:
    workspace = field.initial_workspace()
    stored, _ = field.write_parent_registers(
        workspace, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),)
    )
    payload = copy.deepcopy(stored.as_dict())
    raw = bytearray(__import__("base64").b64decode(payload["field_b64"]))
    page = np.frombuffer(raw, dtype="<f8").copy()
    page[8] = 0.0
    payload["field_b64"] = __import__("base64").b64encode(page.astype("<f8").tobytes()).decode("ascii")
    payload["field"] = page.reshape(stored.profile.page_shape).tolist()
    payload.pop("state_sha256", None)
    with pytest.raises(field.ResonantNumericalError):
        field.ResonantWorkspace.from_dict(payload)
    partial = copy.deepcopy(stored.as_dict())
    del partial["layout_transition"][field.PARENT_REGISTER_METADATA_KEY]["slots"]["LL"]
    partial.pop("state_sha256", None)
    with pytest.raises(field.ResonantNumericalError):
        field.ResonantWorkspace.from_dict(partial)
    with pytest.raises(field.ResonantNumericalError):
        field.write_parent_registers(workspace, paths=("R",))

def test_resolution_and_regional_paths_reject_active_map() -> None:
    workspace = field.initial_workspace()
    stored, _ = field.write_parent_registers(workspace, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),))
    with pytest.raises(field.ResonantNumericalError, match="regional serialization rejects"):
        field.regional_state(stored)
    with pytest.raises(field.ResonantNumericalError, match="resolution change rejects"):
        field.expand_resolution(stored, factor=2)


def test_receipt_is_persistable(tmp_path: Path, receipt: dict) -> None:
    path = tmp_path / "exploration.json"
    path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert runner.verify_receipt(loaded)["content_digest_matches"]
