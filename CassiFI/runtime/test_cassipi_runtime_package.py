from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_cassipi_runtime import RuntimePackageError, build_runtime, verify_runtime


def test_runtime_package_is_exact_and_imports_without_optional_surfaces(tmp_path: Path) -> None:
    output = tmp_path / "runtime"
    manifest = build_runtime(output)
    verified = verify_runtime(output)
    assert set(manifest["dependencies"]) == {"numpy", "scipy", "torch"}

    assert manifest == verified["manifest"]
    assert "cassi_field_program" in verified["loaded_modules"]
    assert {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    } == {"runtime-manifest.json", *(row["path"] for row in manifest["files"])}
    assert not any(
        name.startswith(
            (
                "cassi_canonical_runtime",
                "cassi_field_language",
                "cassi_qi",
                "cassi_text_codec",
                "cassi_universal_data",
            )
        )
        for name in verified["loaded_modules"]
    )


def test_runtime_package_rejects_a_tampered_input(tmp_path: Path) -> None:
    output = tmp_path / "runtime"
    build_runtime(output)
    target = output / "cassi_field_owner.py"
    target.write_bytes(target.read_bytes() + b"tampered")

    with pytest.raises(RuntimePackageError):
        verify_runtime(output)


def test_resonant_snapshot_preserves_measured_pool_power_without_advancing(tmp_path: Path) -> None:
    from cassi_cassipi_v2 import CanonicalOwnerAdapter
    from cassi_resonant_view import snapshot

    runtime = tmp_path / "runtime"
    build_runtime(runtime)
    adapter = CanonicalOwnerAdapter(runtime, data_home=tmp_path / "owner")
    try:
        adapter.advance(operation_id="measured-pool-pulse", ticks=4)
        before = adapter.owner.state.state_sha256
        measured = snapshot(adapter)
        assert adapter.owner.state.state_sha256 == before
        samples = [
            row
            for strand in measured["strands"].values()
            for row in strand["samples"]
        ]
        assert sum(row["power"] for row in samples) > 0
        for pool, row in enumerate(measured["pools"]):
            expected_power = sum(sample["power"] for sample in samples if sample["pool"] == pool)
            assert row["available"]
            assert row["power"] == pytest.approx(expected_power, rel=1e-12, abs=0)
            assert row["amplitude"] ** 2 == pytest.approx(expected_power, rel=1e-12, abs=0)
    finally:
        adapter.close()
