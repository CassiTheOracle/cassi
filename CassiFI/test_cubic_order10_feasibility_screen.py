from __future__ import annotations

from pathlib import Path
import hashlib
import sqlite3

import pytest

import run_cubic_order10_feasibility_screen as runner
import verify_cubic_order10_feasibility_screen as verifier


def test_small_cycle_cover_and_factorization_controls_match() -> None:
    expected_partitions = ((2, 2), (4,))
    assert tuple(verifier.cycle_partitions(4)) == expected_partitions
    assert tuple(runner.source.cycle_partitions(4)) == expected_partitions

    second = verifier.canonical_cycle_permutation((4,))
    third = (2, 3, 0, 1)
    formula = verifier.formula_from_factorization(second, third)
    expected_formula = (
        (1, 2, 3),
        (1, 2, 4),
        (1, 3, 4),
        (2, 3, 4),
    )
    assert formula == expected_formula
    assert runner.source.formula_digest(formula) == verifier.formula_digest(formula)
    assert runner.source.rank_mod_prime(formula) == 4
    assert verifier.rank_mod_prime(formula) == 4


def test_hash_of_formula_keys_is_explicit_and_deterministic() -> None:
    expected = hashlib.sha256(b"a\nb\n").hexdigest()
    assert verifier.hash_stream_digest(["a", "b"]) == expected
    assert runner.hash_stream_digest(["a", "b"]) == expected

    formula_key = verifier.formula_digest(
        ((1, 2, 3), (1, 2, 4), (1, 3, 4), (2, 3, 4))
    )
    assert verifier.hash_stream_digest([formula_key]) == hashlib.sha256(
        (formula_key + "\n").encode("ascii")
    ).hexdigest()


def test_sorted_hash_digests_use_only_sqlite_keys() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE formulas ("
            "formula_sha256 TEXT PRIMARY KEY, "
            "modular_target INTEGER NOT NULL"
            ")"
        )
        connection.executemany(
            "INSERT INTO formulas VALUES (?, ?)",
            [("b", 0), ("a", 1)],
        )
        connection.commit()
        assert verifier.sorted_hash_digest(connection, target_only=False) == (
            verifier.hash_stream_digest(["a", "b"])
        )
        assert verifier.sorted_hash_digest(connection, target_only=True) == (
            verifier.hash_stream_digest(["a"])
        )
    finally:
        connection.close()


def test_invalid_formula_control_fires() -> None:
    with pytest.raises(verifier.VerificationError, match="duplicate variable"):
        verifier.canonical_formula(((1, 1, 2), (1, 2, 3), (1, 2, 3)))


def test_stable_contract_constants_match_without_reading_a_receipt() -> None:
    assert runner.SCHEMA == verifier.SCHEMA
    assert runner.source.MODULAR_PRIME == verifier.MODULAR_PRIME
    assert runner.source.SCHEMA == verifier.GENERATOR_SCHEMA
    assert runner.TARGET_NULLITY == verifier.TARGET_NULLITY


def _synthetic_receipt(source_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    expected: dict[str, object] = {
        "schema": verifier.SCHEMA,
        "source": {
            "generator_file_sha256": verifier.sha256_file(source_path),
        },
        "census": {"sentinel": 1},
        "assessment": {"result": "synthetic"},
    }
    actual = dict(expected)
    actual["measurement"] = {
        "elapsed_seconds": 1.0,
        "peak_working_set_bytes": 1,
        "temporary_storage_bytes": 1,
        "storage_deleted_after_receipt": True,
    }
    actual["deterministic_receipt_sha256"] = verifier.json_digest(expected)
    return actual, expected


def _temporary_source(tmp_path: Path) -> Path:
    source_path = tmp_path / "audited-generator.py"
    source_path.write_text("SOURCE = 'synthetic'\\n", encoding="utf-8")
    return source_path


def test_synthetic_receipt_verifies_without_full_census(tmp_path: Path) -> None:
    source_path = _temporary_source(tmp_path)
    actual, expected = _synthetic_receipt(source_path)
    result = verifier.verify_receipt_object(actual, expected, source_path)
    assert result["status"] == "verified"
    assert result["memory_measurement_status"] == "available"


def test_synthetic_receipt_tamper_and_source_binding_are_rejected(
    tmp_path: Path,
) -> None:
    source_path = _temporary_source(tmp_path)
    actual, expected = _synthetic_receipt(source_path)

    tampered = dict(actual)
    tampered["census"] = {"sentinel": 2}
    tampered["deterministic_receipt_sha256"] = verifier.json_digest(
        {
            key: value
            for key, value in tampered.items()
            if key not in {"measurement", "deterministic_receipt_sha256"}
        }
    )
    with pytest.raises(
        verifier.VerificationError,
        match="deterministic receipt digest mismatch",
    ):
        verifier.verify_receipt_object(tampered, expected, source_path)

    wrong_source = dict(expected)
    wrong_source["source"] = {"generator_file_sha256": "0" * 64}
    wrong_actual = dict(wrong_source)
    wrong_actual["measurement"] = actual["measurement"]
    wrong_actual["deterministic_receipt_sha256"] = verifier.json_digest(wrong_source)
    with pytest.raises(verifier.VerificationError, match="source generator digest"):
        verifier.verify_receipt_object(wrong_actual, wrong_source, source_path)
