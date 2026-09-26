from __future__ import annotations

from pathlib import Path
import run_cubic_lift_realization_probe as source
import run_cubic_order10_exact_target_probe as runner
import verify_cubic_order10_exact_target_probe as verifier


def _factorization() -> dict[str, object]:
    return {
        "cycle_partition": [9],
        "identity_matching": list(range(1, 10)),
        "second_matching": [2, 3, 4, 5, 6, 7, 8, 9, 1],
        "third_matching": [3, 4, 5, 6, 7, 8, 9, 1, 2],
    }


def test_runner_and_verifier_agree_on_exact_target_control() -> None:
    formula = source.NULLITY_THREE_CONTROL
    formula_sha256 = source.formula_digest(formula)
    factorization = _factorization()
    modular_rank = source.rank_mod_prime(formula)

    production_row = runner.analyze_target(
        formula_sha256,
        formula,
        factorization,
        modular_rank,
    )
    independent_row = verifier.analyze_target(
        formula_sha256,
        formula,
        factorization,
        modular_rank,
    )

    assert production_row == independent_row
    assert production_row["status"] == "exact_target_connected"
    assert production_row["rank"] == 6
    assert production_row["nullity"] == 3
    assert production_row["basis_census"]["exact"] is True
    assert production_row["pair_profile"]["counts"]["pair_cases_checked"] == 36


def test_runner_and_verifier_agree_on_modular_false_positive_control() -> None:
    formula = (
        (1, 2, 3),
        (1, 2, 4),
        (1, 3, 4),
        (2, 3, 4),
    )
    formula_sha256 = source.formula_digest(formula)
    factorization = {
        "cycle_partition": [4],
        "identity_matching": [1, 2, 3, 4],
        "second_matching": [2, 3, 4, 1],
        "third_matching": [3, 4, 1, 2],
    }
    modular_rank = source.rank_mod_prime(formula)

    production_row = runner.analyze_target(
        formula_sha256,
        formula,
        factorization,
        modular_rank,
    )
    independent_row = verifier.analyze_target(
        formula_sha256,
        formula,
        factorization,
        modular_rank,
    )

    assert production_row == independent_row
    assert production_row["status"] == "modular_false_positive"
    assert production_row["rank"] == 4
    assert production_row["nullity"] == 0
    assert production_row["pair_profile"] is None


def test_exact_target_contract_constants_match() -> None:
    assert runner.SCHEMA == verifier.SCHEMA
    assert runner.FEASIBILITY_SCHEMA == verifier.FEASIBILITY_SCHEMA
    assert runner.ORDER == verifier.ORDER == 10
    assert runner.TARGET_NULLITY == verifier.TARGET_NULLITY == 3
    assert runner.PAIR_KEYS == verifier.PAIR_KEYS


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
    try:
        verifier.verify_receipt_object(tampered, expected, source_path)
    except verifier.VerificationError as error:
        assert str(error) == "exact-target deterministic digest mismatch"
    else:
        raise AssertionError("tampered exact-target receipt was accepted")

    wrong_source = dict(expected)
    wrong_source["source"] = {"generator_file_sha256": "0" * 64}
    wrong_actual = dict(wrong_source)
    wrong_actual["measurement"] = actual["measurement"]
    wrong_actual["deterministic_receipt_sha256"] = verifier.json_digest(wrong_source)
    try:
        verifier.verify_receipt_object(wrong_actual, wrong_source, source_path)
    except verifier.VerificationError as error:
        assert str(error) == "exact-target source generator digest mismatch"
    else:
        raise AssertionError("wrong source binding was accepted")
