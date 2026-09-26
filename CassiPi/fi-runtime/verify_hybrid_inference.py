#!/usr/bin/env python
"""Independently check CassiFI hybrid-inference proof receipts.

This standard-library verifier imports neither the field implementation nor the
scenario runner.  It reconstructs every clause, cutting-plane, GF(2), bridge,
extension, and resolution inference from the serialized proof.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

PROOF_SCHEMA = "cassifi.hybrid-inference-proof.v1"
RECEIPT_SCHEMA = "cassifi.hybrid-inference-probe.v1"
DEFAULT_RECEIPT = Path("_diag/p_vs_np_hybrid_inference.json")
SAFE_INTEGER = 2**53 - 1


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def exact_integer(value: Any, name: str, *, minimum: int | None = None) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{name}: not an integer")
    result = cast(int, value)
    require(abs(result) <= SAFE_INTEGER, f"{name}: outside exact range")
    if minimum is not None:
        require(result >= minimum, f"{name}: below minimum")
    return result


def literal_key(literal: int) -> tuple[int, bool]:
    return abs(literal), literal < 0


def clause_value(value: Any, variables: int, name: str) -> tuple[int, ...]:
    require(isinstance(value, list), f"{name}: clause is not a list")
    literals = tuple(exact_integer(item, f"{name} literal") for item in cast(list[Any], value))
    require(all(literal != 0 and abs(literal) <= variables for literal in literals), f"{name}: invalid literal")
    require(len(literals) == len(set(literals)), f"{name}: duplicate literal")
    require(not any(-literal in literals for literal in literals), f"{name}: tautological clause")
    require(literals == tuple(sorted(literals, key=literal_key)), f"{name}: noncanonical clause")
    return literals


def canonical_formula(formula: Sequence[Sequence[int]], variables: int) -> tuple[tuple[int, ...], ...]:
    rows = [
        clause_value(list(clause), variables, f"source clause {index}")
        for index, clause in enumerate(formula, 1)
    ]
    require(len(rows) == len(set(rows)), "source formula contains duplicate clauses")
    return tuple(sorted(rows, key=lambda clause: (len(clause), clause)))


@dataclass(frozen=True, slots=True)
class CheckedLine:
    kind: str
    values: tuple[tuple[int, int], ...]
    rhs: int
    rule: str
    left: int = 0
    right: int = 0
    aux: int = 0

    def coefficients(self) -> dict[int, int]:
        return dict(self.values)


def sparse(values: Mapping[int, int]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((variable, coefficient) for variable, coefficient in values.items() if coefficient))


def add_values(left: CheckedLine, right: CheckedLine) -> tuple[tuple[int, int], ...]:
    values = left.coefficients()
    for variable, coefficient in right.values:
        values[variable] = values.get(variable, 0) + coefficient
    return sparse(values)


def xor_values(left: CheckedLine, right: CheckedLine) -> tuple[tuple[int, int], ...]:
    values = set(left.coefficients()) ^ set(right.coefficients())
    return tuple((variable, 1) for variable in sorted(values))


def clause_line(clause: Sequence[int], rule: str, *, left: int = 0, right: int = 0, aux: int = 0) -> CheckedLine:
    return CheckedLine(
        "clause",
        tuple((abs(literal), 1 if literal > 0 else -1) for literal in clause),
        0,
        rule,
        left,
        right,
        aux,
    )


def clause_from(line: CheckedLine) -> tuple[int, ...]:
    require(line.kind == "clause", "clause premise has wrong kind")
    return tuple(variable if coefficient > 0 else -variable for variable, coefficient in line.values)


def clause_pb(line: CheckedLine, *, left: int) -> CheckedLine:
    clause = clause_from(line)
    values = {
        abs(literal): -1 if literal > 0 else 1
        for literal in clause
    }
    return CheckedLine("pb", sparse(values), sum(literal < 0 for literal in clause) - 1, "clause-pb", left)


def resolve(left: CheckedLine, right: CheckedLine, pivot: int) -> tuple[int, ...]:
    left_clause = clause_from(left)
    right_clause = clause_from(right)
    left_polarity = 1 if pivot in left_clause else -1 if -pivot in left_clause else 0
    right_polarity = 1 if pivot in right_clause else -1 if -pivot in right_clause else 0
    require(left_polarity != 0 and right_polarity == -left_polarity, "resolution premises lack complementary pivot")
    result: set[int] = set()
    for literal in (*left_clause, *right_clause):
        if abs(literal) == pivot:
            continue
        require(-literal not in result, "resolution produced tautology")
        result.add(literal)
    return tuple(sorted(result, key=literal_key))


def parse_terms(value: Any, variables: int, name: str) -> tuple[tuple[int, int], ...]:
    require(isinstance(value, list), f"{name}: terms are not a list")
    result: list[tuple[int, int]] = []
    for index, raw in enumerate(cast(list[Any], value), 1):
        require(isinstance(raw, list) and len(raw) == 2, f"{name}: term {index} malformed")
        variable = exact_integer(raw[0], f"{name} variable", minimum=1)
        coefficient = exact_integer(raw[1], f"{name} coefficient")
        require(variable <= variables and coefficient != 0, f"{name}: invalid term")
        result.append((variable, coefficient))
    require(result == sorted(result) and len({variable for variable, _ in result}) == len(result), f"{name}: terms not canonical")
    return tuple(result)


def parse_xor(value: Any, variables: int, name: str) -> tuple[tuple[int, int], ...]:
    require(isinstance(value, list), f"{name}: variables are not a list")
    parsed = [exact_integer(item, f"{name} variable", minimum=1) for item in cast(list[Any], value)]
    require(all(variable <= variables for variable in parsed), f"{name}: variable out of range")
    require(parsed == sorted(set(parsed)), f"{name}: variables not canonical")
    return tuple((variable, 1) for variable in parsed)


def line_common(row: Mapping[str, Any], line_id: int) -> tuple[str, str, int, int, int]:
    require(row.get("line_id") == line_id, f"line {line_id}: id mismatch")
    kind = row.get("kind")
    rule = row.get("rule")
    require(kind in {"clause", "pb", "xor", "extension"}, f"line {line_id}: invalid kind")
    require(
        rule
        in {
            "input",
            "clause-pb",
            "pb-add",
            "pb-scale",
            "pb-divide",
            "parity-import",
            "xor-add",
            "cardinality-parity",
            "extension-define",
            "extension-clause",
            "resolve",
        },
        f"line {line_id}: invalid rule",
    )
    left = exact_integer(row.get("left", 0), f"line {line_id} left")
    right = exact_integer(row.get("right", 0), f"line {line_id} right")
    aux = exact_integer(row.get("aux", 0), f"line {line_id} aux")
    require(left < line_id and right < line_id, f"line {line_id}: forward premise")
    return cast(str, kind), cast(str, rule), left, right, aux


def audit_proof(
    formula: Sequence[Sequence[int]],
    value: Any,
    *,
    variables: int,
) -> dict[str, Any]:
    require(isinstance(value, dict), "proof is not an object")
    proof = cast(dict[str, Any], value)
    require(proof.get("schema") == PROOF_SCHEMA, "proof schema mismatch")
    expected_system = "CNF resolution plus cutting planes, GF(2) elimination, cardinality-parity bridges, and acyclic extension definitions"
    require(proof.get("proof_system") == expected_system, "proof-system label mismatch")
    require(proof.get("original_variables") == variables, "original variable count mismatch")
    source = canonical_formula(formula, variables)
    require(proof.get("original_clauses") == len(source), "original clause count mismatch")
    lines_value = proof.get("lines")
    require(isinstance(lines_value, list) and all(isinstance(row, dict) for row in lines_value), "proof lines malformed")
    raw_lines = cast(list[dict[str, Any]], lines_value)
    checked: list[CheckedLine] = []
    active_variables = variables
    rule_counts: dict[str, int] = {}
    maximum_integer_magnitude = 0

    for line_id, row in enumerate(raw_lines, 1):
        kind, rule, left, right, aux = line_common(row, line_id)
        rule_counts[rule] = rule_counts.get(rule, 0) + 1
        if kind == "clause":
            clause = clause_value(row.get("literals"), active_variables, f"line {line_id}")
            actual = clause_line(clause, rule, left=left, right=right, aux=aux)
        elif kind == "pb":
            terms = parse_terms(row.get("terms"), active_variables, f"line {line_id}")
            rhs = exact_integer(row.get("rhs"), f"line {line_id} rhs")
            actual = CheckedLine(kind, terms, rhs, rule, left, right, aux)
        elif kind == "xor":
            values = parse_xor(row.get("variables"), active_variables, f"line {line_id}")
            rhs = exact_integer(row.get("rhs"), f"line {line_id} rhs")
            require(rhs in (0, 1), f"line {line_id}: invalid XOR rhs")
            actual = CheckedLine(kind, values, rhs, rule, left, right, aux)
        else:
            operands = clause_value(row.get("operands"), active_variables, f"line {line_id} operands")
            require(len(operands) == 2, f"line {line_id}: extension needs two operands")
            new_variable = exact_integer(row.get("new_variable"), f"line {line_id} new variable", minimum=1)
            actual = CheckedLine(kind, tuple((abs(literal), 1 if literal > 0 else -1) for literal in operands), 0, rule, left, right, new_variable)

        if rule == "input":
            require(line_id <= len(source) and kind == "clause", f"line {line_id}: invalid input line")
            expected = clause_line(source[line_id - 1], "input")
        else:
            require(line_id > len(source), f"line {line_id}: source line has derived rule")
            require(left == 0 or left <= len(checked), f"line {line_id}: missing left premise")
            require(right == 0 or right <= len(checked), f"line {line_id}: missing right premise")
            if rule == "clause-pb":
                require(left > 0 and not right and not aux, f"line {line_id}: malformed clause conversion")
                expected = clause_pb(checked[left - 1], left=left)
            elif rule == "pb-add":
                require(left > 0 and right > 0 and not aux, f"line {line_id}: malformed PB addition")
                a, b = checked[left - 1], checked[right - 1]
                require(a.kind == b.kind == "pb", f"line {line_id}: PB premise kind mismatch")
                expected = CheckedLine("pb", add_values(a, b), a.rhs + b.rhs, rule, left, right)
            elif rule == "pb-scale":
                require(left > 0 and not right and aux >= 0, f"line {line_id}: malformed PB scaling")
                source_line = checked[left - 1]
                require(source_line.kind == "pb", f"line {line_id}: scaling premise kind mismatch")
                expected = CheckedLine("pb", tuple((variable, coefficient * aux) for variable, coefficient in source_line.values if coefficient * aux), source_line.rhs * aux, rule, left, 0, aux)
            elif rule == "pb-divide":
                require(left > 0 and not right and aux > 0, f"line {line_id}: malformed PB division")
                source_line = checked[left - 1]
                require(source_line.kind == "pb" and all(coefficient % aux == 0 for _, coefficient in source_line.values), f"line {line_id}: invalid exact-coefficient division")
                expected = CheckedLine("pb", tuple((variable, coefficient // aux) for variable, coefficient in source_line.values if coefficient // aux), source_line.rhs // aux, rule, left, 0, aux)
            elif rule == "parity-import":
                require(kind == "xor" and left > 0 and not right and not aux, f"line {line_id}: malformed parity import")
                support = tuple(variable for variable, _ in actual.values)
                required_masks = {mask for mask in range(1 << len(support)) if mask.bit_count() & 1 == 1 - actual.rhs}
                source_masks = set()
                for clause in source:
                    if tuple(abs(literal) for literal in clause) != support:
                        continue
                    source_masks.add(sum(1 << position for position, literal in enumerate(clause) if literal < 0))
                require(bool(support) and required_masks.issubset(source_masks), f"line {line_id}: parity block incomplete")
                expected = actual
            elif rule == "xor-add":
                require(left > 0 and right > 0, f"line {line_id}: malformed XOR addition")
                a, b = checked[left - 1], checked[right - 1]
                require(a.kind == b.kind == "xor", f"line {line_id}: XOR premise kind mismatch")
                expected = CheckedLine("xor", xor_values(a, b), a.rhs ^ b.rhs, rule, left, right, aux)
            elif rule == "cardinality-parity":
                require(left > 0 and right > 0 and not aux, f"line {line_id}: malformed cardinality bridge")
                upper, lower = checked[left - 1], checked[right - 1]
                require(upper.kind == lower.kind == "pb", f"line {line_id}: bridge premise kind mismatch")
                upper_values = upper.coefficients()
                lower_values = lower.coefficients()
                require(all(value in (0, 1) for value in upper_values.values()), f"line {line_id}: upper row is not cardinality")
                require(upper_values == {variable: -value for variable, value in lower_values.items()} and upper.rhs == -lower.rhs, f"line {line_id}: rows do not prove exact cardinality")
                expected = CheckedLine("xor", tuple((variable, 1) for variable in sorted(upper_values)), upper.rhs & 1, rule, left, right)
            elif rule == "extension-define":
                require(kind == "extension" and not left and not right and not aux, f"line {line_id}: malformed extension definition")
                require(actual.aux == active_variables + 1, f"line {line_id}: extension is not fresh")
                require(len({variable for variable, _ in actual.values}) == 2, f"line {line_id}: repeated extension operand")
                expected = actual
                active_variables += 1
            elif rule == "extension-clause":
                require(kind == "clause" and left > 0 and not right and aux in (1, 2, 3), f"line {line_id}: malformed extension clause")
                definition = checked[left - 1]
                require(definition.kind == "extension", f"line {line_id}: extension premise kind mismatch")
                operands = clause_from(CheckedLine("clause", definition.values, 0, "input"))
                first, second = operands
                axioms = ((-definition.aux, first, second), (definition.aux, -first), (definition.aux, -second))
                expected = clause_line(tuple(sorted(axioms[aux - 1], key=literal_key)), rule, left=left, aux=aux)
            elif rule == "resolve":
                require(kind == "clause" and left > 0 and right > 0 and aux > 0, f"line {line_id}: malformed resolution")
                expected_clause = resolve(checked[left - 1], checked[right - 1], aux)
                expected = clause_line(expected_clause, rule, left=left, right=right, aux=aux)
            else:
                raise AssertionError(f"line {line_id}: unsupported rule")
        require(actual == expected, f"line {line_id}: false {rule} inference")
        maximum_integer_magnitude = max(
            maximum_integer_magnitude,
            abs(actual.rhs),
            *(abs(coefficient) for _, coefficient in actual.values),
        )
        checked.append(actual)

    status = proof.get("status")
    require(status in {"unsat", "exhausted"}, "invalid proof status")
    roots = [
        index + 1
        for index, line in enumerate(checked)
        if (line.kind == "clause" and not line.values)
        or (line.kind == "pb" and not line.values and line.rhs < 0)
        or (line.kind == "xor" and not line.values and line.rhs == 1)
    ]
    root_line = proof.get("root_line")
    if status == "unsat":
        require(isinstance(root_line, int) and root_line in roots, "UNSAT proof lacks a contradiction")
    else:
        require(root_line is None and not roots, "exhausted proof carries a contradiction")
    digest_payload = dict(proof)
    proof_sha256 = digest_payload.pop("proof_sha256", None)
    require(
        isinstance(proof_sha256, str)
        and proof_sha256 == hashlib.sha256(canonical(digest_payload)).hexdigest(),
        "proof digest mismatch",
    )
    return {
        "status": status,
        "proof_lines": len(checked),
        "derived_lines": len(checked) - len(source),
        "root_line": root_line,
        "active_variables": active_variables,
        "rule_counts": dict(sorted(rule_counts.items())),
        "maximum_integer_magnitude": maximum_integer_magnitude,
    }


def formula_from(value: Any, variables: int, name: str) -> tuple[tuple[int, ...], ...]:
    require(isinstance(value, list), f"{name}: formula is not a list")
    return tuple(
        clause_value(row, variables, f"{name} clause {index}")
        for index, row in enumerate(cast(list[Any], value), 1)
    )

def satisfies(formula: Sequence[Sequence[int]], assignment: Sequence[int]) -> bool:
    return all(
        any(
            assignment[abs(literal) - 1] == (1 if literal > 0 else 0)
            for literal in clause
        )
        for clause in formula
    )


def has_model(formula: Sequence[Sequence[int]], variables: int) -> bool:
    return any(
        satisfies(formula, assignment)
        for assignment in itertools.product((0, 1), repeat=variables)
    )


def digest(value: Any, name: str) -> str:
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        f"{name}: invalid SHA-256",
    )
    return cast(str, value)

def recognize_connected_matched_exact_one(
    formula: Sequence[Sequence[int]],
    variables: int,
) -> dict[str, Any]:
    """Recognize the mixed class from CNF syntax alone.

    The recognizer identifies disjoint three-variable exact-one blocks and
    then requires the remaining clauses to be complete binary parity
    encodings whose supports form a cross-block perfect matching.  The
    matching quotient graph must be connected.
    """
    source = set(tuple(clause) for clause in formula)
    positive_blocks = sorted(
        (
            tuple(clause)
            for clause in formula
            if len(clause) == 3 and all(literal > 0 for literal in clause)
        ),
        key=lambda block: block,
    )
    require(
        len(positive_blocks) >= 4 and len(positive_blocks) % 2 == 0,
        "mixed class needs an even number of at least four blocks",
    )
    flattened = [variable for block in positive_blocks for variable in block]
    require(
        len(flattened) == variables
        and len(set(flattened)) == variables
        and set(flattened) == set(range(1, variables + 1)),
        "mixed exact-one blocks do not partition the variables",
    )
    block_for = {
        variable: block_index
        for block_index, block in enumerate(positive_blocks)
        for variable in block
    }
    exact_one_clauses: set[tuple[int, ...]] = set()
    for block in positive_blocks:
        exact_one_clauses.add(block)
        for left, right in itertools.combinations(block, 2):
            exact_one_clauses.add(
                tuple(sorted((-left, -right), key=literal_key))
            )
    require(
        exact_one_clauses.issubset(source),
        "mixed class is missing an exact-one clause",
    )
    remainder = source - exact_one_clauses
    groups: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for clause in remainder:
        require(len(clause) == 2, "mixed class has a non-binary remainder")
        support = tuple(sorted(abs(literal) for literal in clause))
        require(
            len(set(support)) == 2
            and block_for[support[0]] != block_for[support[1]],
            "mixed matching edge is repeated or internal to a block",
        )
        groups.setdefault(cast(tuple[int, int], support), []).append(clause)

    matching: list[dict[str, Any]] = []
    incidence: dict[int, int] = {}
    adjacency = {index: set() for index in range(len(positive_blocks))}
    label_xor = 0
    for support in sorted(groups):
        clauses = groups[support]
        require(len(clauses) == 2, "mixed parity support is incomplete")
        masks = {
            sum(
                1 << position
                for position, variable in enumerate(support)
                if next(
                    literal
                    for literal in clause
                    if abs(literal) == variable
                )
                < 0
            )
            for clause in clauses
        }
        if masks == {0, 3}:
            rhs = 1
        elif masks == {1, 2}:
            rhs = 0
        else:
            raise AssertionError("mixed binary clauses do not encode parity")
        for variable in support:
            incidence[variable] = incidence.get(variable, 0) + 1
        left_block, right_block = (
            block_for[support[0]],
            block_for[support[1]],
        )
        adjacency[left_block].add(right_block)
        adjacency[right_block].add(left_block)
        label_xor ^= rhs
        matching.append({"variables": list(support), "rhs": rhs})
    require(
        len(matching) * 2 == variables
        and all(incidence.get(variable) == 1 for variable in range(1, variables + 1)),
        "mixed parity supports are not a perfect matching",
    )
    reached = {0}
    frontier = [0]
    while frontier:
        current = frontier.pop()
        for neighbor in adjacency[current] - reached:
            reached.add(neighbor)
            frontier.append(neighbor)
    require(
        len(reached) == len(positive_blocks),
        "mixed matching quotient graph is disconnected",
    )
    global_rhs = (len(positive_blocks) & 1) ^ label_xor
    return {
        "blocks": len(positive_blocks),
        "variables": variables,
        "clauses": len(source),
        "exact_one_blocks": [list(block) for block in positive_blocks],
        "matching": matching,
        "quotient_connected": True,
        "global_rhs": global_rhs,
        "contradiction": global_rhs == 1,
    }


EXPECTED_CASES = (
    "counting_php_3_into_2",
    "counting_php_4_into_3",
    "counting_php_5_into_4",
    "counting_php_7_into_6",
    "counting_php_9_into_8",
    "counting_php_11_into_10",
    "counting_php_13_into_12",
    "parity_prism_3_odd",
    "parity_prism_4_odd",
    "parity_prism_5_odd",
    "parity_prism_8_odd",
    "parity_prism_12_odd",
    "parity_prism_16_odd",
    "mixed_connected_blocks_4_odd",
    "mixed_connected_blocks_6_odd",
    "mixed_connected_blocks_8_odd",
    "mixed_connected_blocks_12_odd",
    "mixed_connected_blocks_16_odd",
    "mixed_connected_blocks_24_odd",
    "mixed_labeled_blocks_4_max_odd",
    "mixed_labeled_blocks_6_max_odd",
    "mixed_labeled_blocks_8_max_odd",
    "mixed_labeled_blocks_12_max_odd",
    "mixed_exact_one_even_parity",
    "named_disjunction_unsat",
    "control_even_tseitin",
    "control_incomplete_parity",
    "control_missing_capacity_edge",
    "control_named_disjunction_sat",
    "control_transition_exhaustion",
    "control_mixed_connected_blocks_4_even",
)


def verify_receipt(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(
        isinstance(value, dict) and value.get("schema") == RECEIPT_SCHEMA,
        "receipt schema mismatch",
    )
    receipt = cast(dict[str, Any], value)
    contract = receipt.get("field_contract")
    require(isinstance(contract, dict), "field contract missing")
    contract = cast(dict[str, Any], contract)
    require(
        contract.get("persistent_adaptive_side_tables") == 0
        and contract.get("family_labels_used_by_controller") == 0
        and contract.get("host_proof_hints") == 0
        and contract.get("model_calls") == 0,
        "field-ownership contract mismatch",
    )
    cases_value = receipt.get("cases")
    require(
        isinstance(cases_value, list)
        and all(isinstance(row, dict) for row in cases_value),
        "receipt cases malformed",
    )
    cases = cast(list[dict[str, Any]], cases_value)
    require(
        tuple(row.get("name") for row in cases) == EXPECTED_CASES,
        "scenario corpus mismatch",
    )
    audited: list[dict[str, Any]] = []
    mixed_recognized: dict[str, dict[str, Any]] = {}
    for row in cases:
        name = cast(str, row["name"])
        variables = exact_integer(
            row.get("variables"),
            f"{name} variables",
            minimum=1,
        )
        formula = formula_from(row.get("formula"), variables, name)
        require(
            row.get("problem_sha256")
            == hashlib.sha256(canonical(formula)).hexdigest(),
            f"{name}: problem digest mismatch",
        )
        proof_value = row.get("proof")
        require(isinstance(proof_value, dict), f"{name}: proof missing")
        proof = cast(dict[str, Any], proof_value)
        audit = audit_proof(formula, proof, variables=variables)
        require(row.get("expected_status") == audit["status"], f"{name}: expected status mismatch")
        require(row.get("status") == audit["status"], f"{name}: status mismatch")
        require(row.get("audit") == audit, f"{name}: stored audit mismatch")
        expected_model = row.get("expected_model")
        require(
            expected_model is None or isinstance(expected_model, bool),
            f"{name}: invalid model control",
        )
        if isinstance(expected_model, bool):
            require(variables <= 20, f"{name}: truth-table control too large")
            require(
                has_model(formula, variables) == expected_model,
                f"{name}: truth-table control mismatch",
            )
        required_rules = row.get("required_rules")
        require(
            isinstance(required_rules, list)
            and all(isinstance(rule, str) for rule in required_rules)
            and set(required_rules).issubset(audit["rule_counts"]),
            f"{name}: required proof route missing",
        )
        profile_value = row.get("profile")
        require(isinstance(profile_value, dict), f"{name}: profile missing")
        profile = cast(dict[str, Any], profile_value)
        expected_profile_keys = {
            "max_variables",
            "max_original_clauses",
            "max_lines",
            "max_extensions",
            "max_parity_width",
            "max_resolution_inferences",
            "max_transitions",
        }
        require(set(profile) == expected_profile_keys, f"{name}: profile keys mismatch")
        parsed_profile = {
            key: exact_integer(profile[key], f"{name} {key}", minimum=0)
            for key in expected_profile_keys
        }
        require(
            parsed_profile["max_variables"] == variables
            and parsed_profile["max_original_clauses"] == len(formula)
            and parsed_profile["max_lines"] >= len(proof["lines"]),
            f"{name}: profile capacity mismatch",
        )
        expected_bytes = 72 * max(
            16,
            parsed_profile["max_lines"]
            * (parsed_profile["max_variables"] + parsed_profile["max_extensions"]),
        )
        require(row.get("field_bytes") == expected_bytes, f"{name}: field storage mismatch")
        digest(row.get("initial_state_sha256"), f"{name} initial state")
        digest(row.get("state_sha256"), f"{name} final state")
        require(
            row.get("checkpoint_roundtrip_exact") is True
            and row.get("deterministic_replay_exact") is True,
            f"{name}: persistence or determinism control failed",
        )
        proof_lines = cast(list[dict[str, Any]], proof["lines"])
        expected_ledger = {
            "transitions": (
                audit["derived_lines"]
                if audit["status"] == "unsat"
                else min(
                    parsed_profile["max_transitions"],
                    audit["derived_lines"] + 1,
                )
            ),
            "input_lines": sum(line["rule"] == "input" for line in proof_lines),
            "pb_lines": sum(line["kind"] == "pb" for line in proof_lines),
            "xor_lines": sum(line["kind"] == "xor" for line in proof_lines),
            "extension_definitions": sum(
                line["kind"] == "extension" for line in proof_lines
            ),
            "resolution_lines": sum(
                line["rule"] == "resolve" for line in proof_lines
            ),
            "maximum_integer_magnitude": audit["maximum_integer_magnitude"],
        }
        require(
            row.get("resource_ledger") == expected_ledger,
            f"{name}: resource ledger mismatch",
        )
        if row.get("family") == "connected-matched-exact-one":
            recognized = recognize_connected_matched_exact_one(formula, variables)
            mixed_recognized[name] = recognized
            blocks = exact_integer(
                recognized["blocks"],
                f"{name} recognized blocks",
                minimum=4,
            )
            require(
                recognized["contradiction"] is True
                and variables == 3 * blocks
                and len(formula) == 7 * blocks,
                f"{name}: restricted-class identity mismatch",
            )
            expected_rules = {
                "input": 7 * blocks,
                "clause-pb": 7 * blocks,
                "parity-import": 3 * blocks // 2,
                "pb-add": 4 * blocks - 1,
                "pb-divide": blocks,
                "cardinality-parity": 2 * blocks + 1,
                "xor-add": 5 * blocks // 2,
            }
            require(
                audit["rule_counts"] == expected_rules
                and audit["proof_lines"] == 25 * blocks
                and audit["derived_lines"] == 18 * blocks
                and expected_ledger["transitions"] == 18 * blocks
                and audit["maximum_integer_magnitude"] == blocks
                and parsed_profile["max_lines"] == 83 * blocks + 256
                and row["field_bytes"]
                == 17_928 * blocks * blocks + 55_296 * blocks,
                f"{name}: restricted-class proof formula mismatch",
            )
        elif row.get("family") == "connected-matched-exact-one-labeled":
            recognized = recognize_connected_matched_exact_one(formula, variables)
            mixed_recognized[name] = recognized
            blocks = exact_integer(
                recognized["blocks"],
                f"{name} recognized blocks",
                minimum=4,
            )
            line_limit = 40 * blocks * blocks + 32 * blocks + 256
            require(
                recognized["contradiction"] is True
                and variables == 3 * blocks
                and len(formula) == 7 * blocks
                and audit["status"] == "unsat"
                and audit["proof_lines"] <= line_limit
                and audit["maximum_integer_magnitude"] <= 3 * blocks
                and parsed_profile["max_lines"] == line_limit
                and expected_ledger["extension_definitions"] == 0
                and expected_ledger["resolution_lines"] == 0,
                f"{name}: labeled restricted-class bound mismatch",
            )
        elif name == "control_mixed_connected_blocks_4_even":
            recognized = recognize_connected_matched_exact_one(formula, variables)
            mixed_recognized[name] = recognized
            require(
                recognized["blocks"] == 4
                and recognized["global_rhs"] == 0
                and recognized["contradiction"] is False
                and expected_model is True
                and audit["status"] == "exhausted"
                and audit["root_line"] is None,
                f"{name}: consistent restricted-class control mismatch",
            )
        audited.append(audit)

    summary = receipt.get("summary")
    require(isinstance(summary, dict), "receipt summary missing")
    expected_summary = {
        "cases": len(cases),
        "unsat": sum(row["status"] == "unsat" for row in audited),
        "exhausted_controls": sum(row["status"] == "exhausted" for row in audited),
        "all_proofs_independently_verified": True,
        "total_proof_lines": sum(row["proof_lines"] for row in audited),
        "maximum_integer_magnitude": max(
            (row["maximum_integer_magnitude"] for row in audited),
            default=0,
        ),
    }
    require(summary == expected_summary, "receipt summary mismatch")

    expected_scaling: dict[str, list[dict[str, Any]]] = {}
    for family in (
        "cutting-plane-pigeonhole",
        "gf2-tseitin",
        "connected-matched-exact-one",
        "connected-matched-exact-one-labeled",
    ):
        expected_scaling[family] = []
        for row, audit in zip(cases, audited):
            if row.get("family") != family:
                continue
            expected_scaling[family].append(
                {
                    "variables": row["variables"],
                    "input_clauses": len(row["formula"]),
                    "proof_lines": audit["proof_lines"],
                    "derived_lines": audit["derived_lines"],
                    "transitions": row["resource_ledger"]["transitions"],
                    "field_bytes": row["field_bytes"],
                    "maximum_integer_magnitude": audit[
                        "maximum_integer_magnitude"
                    ],
                }
            )
    require(receipt.get("scaling") == expected_scaling, "scaling table mismatch")

    mixed_rows = [
        (row, audit)
        for row, audit in zip(cases, audited)
        if row.get("family") == "connected-matched-exact-one"
    ]
    mixed_labeled_rows = [
        (row, audit)
        for row, audit in zip(cases, audited)
        if row.get("family") == "connected-matched-exact-one-labeled"
    ]
    expected_restricted_class = {
        "schema": "cassifi.connected-matched-exact-one.v2",
        "syntax": {
            "block": "a positive three-literal clause plus all three negative pairs",
            "coupling": "complete binary parity CNFs form a cross-block perfect matching",
            "globality": "the quotient graph on exact-one blocks is connected",
            "contradiction": "block-count parity XOR matching-label parity equals one",
        },
        "semantic_identity": (
            "XORing every exact-one parity and matching equation cancels "
            "every variable exactly twice"
        ),
        "canonical_subfamily_bounds": {
            "blocks": "even b >= 4",
            "variables": "3b",
            "input_clauses": "7b",
            "derived_proof_lines": "18b",
            "total_proof_lines": "25b",
            "maximum_integer_magnitude": "b",
            "profile_max_lines": "83b + 256",
            "field_bytes": "17928b^2 + 55296b",
            "bulk_controller_work": "O(b^3) conservative loop bound",
            "stepwise_controller_work": "O(b^4) conservative loop bound",
            "temporary_space": "O(b^2)",
        },
        "labeled_subfamily_bounds": {
            "labels": "arbitrary with XOR_e ell_e = 1",
            "proof_lines": "<= 40b^2 + 32b + 256",
            "maximum_integer_magnitude": "<= 3b",
            "profile_max_lines": "40b^2 + 32b + 256",
            "field_bytes": "216b(40b^2 + 32b + 256)",
            "bulk_controller_work": "O(b^3) conservative loop bound",
            "stepwise_controller_work": "O(b^5) conservative loop bound",
            "temporary_space": "O(b^3)",
        },
        "measured": [
            {
                "blocks": mixed_recognized[cast(str, row["name"])]["blocks"],
                "variables": row["variables"],
                "input_clauses": len(row["formula"]),
                "proof_lines": audit["proof_lines"],
                "derived_lines": audit["derived_lines"],
                "transitions": row["resource_ledger"]["transitions"],
                "maximum_integer_magnitude": audit["maximum_integer_magnitude"],
                "field_bytes": row["field_bytes"],
                "problem_sha256": row["problem_sha256"],
                "proof_sha256": row["proof"]["proof_sha256"],
            }
            for row, audit in mixed_rows
        ],
        "measured_labeled": [
            {
                "blocks": mixed_recognized[cast(str, row["name"])]["blocks"],
                "odd_labels": sum(
                    edge["rhs"]
                    for edge in mixed_recognized[cast(str, row["name"])][
                        "matching"
                    ]
                ),
                "proof_lines": audit["proof_lines"],
                "derived_lines": audit["derived_lines"],
                "transitions": row["resource_ledger"]["transitions"],
                "maximum_integer_magnitude": audit["maximum_integer_magnitude"],
                "field_bytes": row["field_bytes"],
                "problem_sha256": row["problem_sha256"],
                "proof_sha256": row["proof"]["proof_sha256"],
            }
            for row, audit in mixed_labeled_rows
        ],
        "consistent_control": {
            "blocks": mixed_recognized[
                "control_mixed_connected_blocks_4_even"
            ]["blocks"],
            "global_rhs": mixed_recognized[
                "control_mixed_connected_blocks_4_even"
            ]["global_rhs"],
            "truth_table_model_exists": True,
            "status": "exhausted",
            "root_line": None,
        },
    }
    require(
        receipt.get("restricted_class") == expected_restricted_class,
        "restricted-class theorem receipt mismatch",
    )

    representation_value = receipt.get("representation")
    require(isinstance(representation_value, dict), "representation controls missing")
    representation = cast(dict[str, Any], representation_value)
    variants_value = representation.get("variants")
    require(
        isinstance(variants_value, list)
        and len(variants_value) == 3
        and all(isinstance(row, dict) for row in variants_value),
        "representation variants malformed",
    )
    variants = cast(list[dict[str, Any]], variants_value)
    require(
        [row.get("name") for row in variants] == ["base", "reordered", "renamed"],
        "representation variant names mismatch",
    )
    require(
        variants[0].get("state_sha256") == variants[1].get("state_sha256")
        and variants[0].get("proof_sha256") == variants[1].get("proof_sha256"),
        "reordering control mismatch",
    )
    require(
        variants[0].get("problem_sha256") != variants[2].get("problem_sha256")
        and len({row.get("status") for row in variants}) == 1,
        "renaming control mismatch",
    )
    require(
        representation.get("reorder_state_identical") is True
        and representation.get("reorder_proof_identical") is True
        and representation.get("renaming_status_invariant") is True
        and representation.get("renaming_problem_digest_changed") is True,
        "representation assessment mismatch",
    )

    assessment = receipt.get("assessment")
    require(isinstance(assessment, dict), "receipt assessment missing")
    assessment = cast(dict[str, Any], assessment)
    require(
        assessment.get("p_equals_np") == "not established"
        and assessment.get("universal_polynomial_proof_search")
        == "not established",
        "receipt overclaims P versus NP",
    )
    return expected_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", nargs="?", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    result = verify_receipt(args.receipt)
    print(json.dumps(result, sort_keys=True))
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
