"""Bounded, read-only SQLite oracle for the Cassi apprenticeship boundary.

This module is intentionally independent of CassiFI cognition and adaptive state.
It accepts a tiny canonical nullable table, places it in a fresh in-memory SQLite
connection, and observes only a deliberately small SELECT language.  The SQLite
runtime is the oracle; this adapter does not reimplement SQL semantics.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


TABLE_SCHEMA = "cassifi.nullable-table.v1"
RECEIPT_SCHEMA = "cassi.sqlite-apprenticeship-receipt.v1"
SOURCE_ID = "readings"
_DEFAULT_OPERATION_ID = "sqlite-oracle"
_MAX_INPUT_ROWS = 8
_MAX_COLUMNS = 8
_MAX_INTEGER = 32
_MAX_SQL_BYTES = 16 * 1024
_MAX_AST_DEPTH = 8
_MAX_AST_NODES = 96


class SQLiteOracleError(ValueError):
    """Raised by canonical table construction for malformed boundary values."""


# Public digest helpers.  JSON digests use exactly the same canonical encoding as
# receipts, making an independently reconstructed receipt straightforward.
def canonical_json(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for a JSON-compatible value."""

    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SQLiteOracleError(f"value is not canonical JSON: {exc}") from exc


def sha256_digest(value: bytes | bytearray | memoryview | str) -> str:
    """Return a lowercase SHA-256 digest of bytes (or UTF-8 text)."""

    if isinstance(value, str):
        value = value.encode("utf-8")
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError("sha256_digest expects bytes or str")
    return hashlib.sha256(bytes(value)).hexdigest()


def digest_json(value: Any) -> str:
    """Digest a JSON value after canonical encoding."""

    return sha256_digest(canonical_json(value))


def canonical_digest(value: Any) -> str:
    """Alias for :func:`digest_json` used by receipt consumers."""

    return digest_json(value)


def table_digest(table: Mapping[str, Any]) -> str:
    """Digest a canonical nullable table."""

    return digest_json(canonical_table(table))

def _require_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise SQLiteOracleError(f"{label} must be a nonempty bounded string")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise SQLiteOracleError(f"{label} must be an unquoted SQL identifier")
    return value


def _canonical_column(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 128
        or any(ord(character) < 32 for character in value)
    ):
        raise SQLiteOracleError(f"{label} must be a bounded nonempty string")
    return value


def _cell(value: Any, label: str = "cell") -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SQLiteOracleError(f"{label} must be a typed cell object")
    kind = value.get("kind")
    if kind == "null":
        if set(value) != {"kind"}:
            raise SQLiteOracleError(f"{label} null cell has unexpected fields")
        return {"kind": "null"}
    if kind == "integer":
        if set(value) != {"kind", "value"}:
            raise SQLiteOracleError(f"{label} integer cell has unexpected fields")
        integer = value.get("value")
        if isinstance(integer, bool) or not isinstance(integer, int):
            raise SQLiteOracleError(f"{label} integer value must be an int")
        if not -_MAX_INTEGER <= integer <= _MAX_INTEGER:
            raise SQLiteOracleError(
                f"{label} integer value must be in [-{_MAX_INTEGER}, {_MAX_INTEGER}]"
            )
        return {"kind": "integer", "value": int(integer)}
    raise SQLiteOracleError(f"{label} kind must be 'integer' or 'null'")


def canonical_table(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a canonical nullable table owned by this boundary."""

    if not isinstance(value, Mapping) or set(value) != {"schema", "columns", "rows"}:
        raise SQLiteOracleError("table must have exactly schema, columns, and rows")
    if value.get("schema") != TABLE_SCHEMA:
        raise SQLiteOracleError(f"table schema must be {TABLE_SCHEMA!r}")
    columns_value = value["columns"]
    if (
        not isinstance(columns_value, list)
        or not columns_value
        or len(columns_value) > _MAX_COLUMNS
        or any(not isinstance(column, str) for column in columns_value)
    ):
        raise SQLiteOracleError("table columns must be a bounded nonempty list")
    columns = [_canonical_column(column, "column") for column in columns_value]
    if columns != sorted(set(columns)):
        raise SQLiteOracleError("table columns must be sorted and unique")
    rows_value = value["rows"]
    if not isinstance(rows_value, list) or len(rows_value) > _MAX_INPUT_ROWS:
        raise SQLiteOracleError(f"table rows must be a list of at most {_MAX_INPUT_ROWS}")
    rows: list[dict[str, dict[str, Any]]] = []
    expected = set(columns)
    for index, row in enumerate(rows_value):
        if not isinstance(row, Mapping) or set(row) != expected:
            raise SQLiteOracleError(
                f"row {index} must contain exactly the table columns (missing is invalid)"
            )
        rows.append({column: _cell(row[column], f"row {index}.{column}") for column in columns})
    return {"schema": TABLE_SCHEMA, "columns": list(columns), "rows": rows}


def table_from_rows(rows: Sequence[Any], columns: Sequence[str] = ("x",)) -> dict[str, Any]:
    """Construct a canonical table from plain integer/``None`` rows."""

    if not isinstance(rows, (list, tuple)):
        raise SQLiteOracleError("table rows must be a finite sequence")
    if not isinstance(columns, (list, tuple)) or not columns:
        raise SQLiteOracleError("table columns must be a nonempty sequence")
    names = [_canonical_column(name, "column") for name in columns]
    if names != sorted(set(names)) or len(names) > _MAX_COLUMNS:
        raise SQLiteOracleError("table columns must be sorted and unique")
    if len(rows) > _MAX_INPUT_ROWS:
        raise SQLiteOracleError(f"table rows must contain at most {_MAX_INPUT_ROWS} values")

    def as_cell(value: Any, label: str) -> dict[str, Any]:
        if value is None:
            return {"kind": "null"}
        if isinstance(value, Mapping):
            return _cell(value, label)
        if isinstance(value, bool) or not isinstance(value, int):
            raise SQLiteOracleError(f"{label} must be an integer in [-32, 32] or null")
        return _cell({"kind": "integer", "value": value}, label)

    canonical_rows: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        if isinstance(raw, Mapping):
            if set(raw) != set(names):
                raise SQLiteOracleError(f"table row {index} has invalid columns")
            values = [raw[name] for name in names]
        elif len(names) == 1:
            values = [raw]
        elif isinstance(raw, (list, tuple)) and len(raw) == len(names):
            values = list(raw)
        else:
            raise SQLiteOracleError(f"table row {index} has invalid shape")
        canonical_rows.append(
            {
                name: as_cell(values[column_index], f"table row {index} column {name!r}")
                for column_index, name in enumerate(names)
            }
        )
    return canonical_table({"schema": TABLE_SCHEMA, "columns": names, "rows": canonical_rows})




def _table_values(table: Mapping[str, Any]) -> list[tuple[Any]]:
    """Extract the one-column input profile as SQLite binding tuples."""

    if table["columns"] != ["x"]:
        raise SQLiteOracleError("SQLite oracle input must have exactly the x column")
    result: list[tuple[Any]] = []
    for row in table["rows"]:
        cell = row["x"]
        result.append((None if cell["kind"] == "null" else cell["value"],))
    return result


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    position: int


_RESERVED = {
    "SELECT",
    "DISTINCT",
    "FROM",
    "WHERE",
    "ORDER",
    "BY",
    "ASC",
    "DESC",
    "NULLS",
    "FIRST",
    "LAST",
    "LIMIT",
    "AS",
    "IS",
    "NOT",
    "NULL",
}


def _tokenize(sql: str) -> list[_Token]:
    if not isinstance(sql, str) or not sql.strip():
        raise SQLiteOracleError("sql must be a nonempty string")
    if len(sql.encode("utf-8")) > _MAX_SQL_BYTES:
        raise SQLiteOracleError("sql exceeds the bounded SQL size")
    tokens: list[_Token] = []
    index = 0
    while index < len(sql):
        character = sql[index]
        if character.isspace():
            index += 1
            continue
        if character in "(),.":
            tokens.append(_Token(character, character, index))
            index += 1
            continue
        if sql.startswith("--", index) or sql.startswith("/*", index):
            raise SQLiteOracleError("SQL comments are not permitted")
        if character in "'\"`[];":
            raise SQLiteOracleError("quoted identifiers, strings, and statements are not permitted")
        if character.isascii() and (character.isalpha() or character == "_"):
            start = index
            index += 1
            while index < len(sql) and sql[index].isascii() and (sql[index].isalnum() or sql[index] == "_"):
                index += 1
            tokens.append(_Token("ID", sql[start:index], start))
            continue
        if character.isdigit():
            start = index
            index += 1
            while index < len(sql) and sql[index].isdigit():
                index += 1
            # A dot/exponent immediately following an integer is always a float.
            if index < len(sql) and (sql[index] == "." or sql[index] in "eE"):
                raise SQLiteOracleError("floating-point literals are not permitted")
            tokens.append(_Token("INT", sql[start:index], start))
            continue
        if character == "-":
            tokens.append(_Token("-", character, index))
            index += 1
            continue
        matched = next((operator for operator in ("<>", "!=", "<=", ">=", "=", "<", ">") if sql.startswith(operator, index)), None)
        if matched is not None:
            tokens.append(_Token("OP", matched, index))
            index += len(matched)
            continue
        raise SQLiteOracleError(f"SQL character {character!r} is not permitted")
    return tokens


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.index = 0
        self.nodes = 0
        self.depth = 0

    def _node(self) -> None:
        self.nodes += 1
        if self.nodes > _MAX_AST_NODES:
            raise SQLiteOracleError("SQL expression is too large")

    def _peek(self, text: str | None = None) -> _Token | None:
        token = self.tokens[self.index] if self.index < len(self.tokens) else None
        if token is None or text is None:
            return token
        return token if token.text.upper() == text else None

    def _take(self, text: str | None = None) -> _Token:
        token = self._peek(text)
        if token is None:
            expected = text or "token"
            raise SQLiteOracleError(f"expected {expected}")
        self.index += 1
        return token

    def _optional(self, text: str) -> bool:
        if self._peek(text) is None:
            return False
        self.index += 1
        return True

    def parse(self) -> dict[str, Any]:
        tree = self.query()
        if self._peek() is not None:
            raise SQLiteOracleError("multiple statements or trailing SQL are not permitted")
        return tree

    def query(self) -> dict[str, Any]:
        self._node()
        self.depth += 1
        if self.depth > _MAX_AST_DEPTH:
            raise SQLiteOracleError("nested SQL scope is too deep")
        try:
            self._take("SELECT")
            distinct = self._optional("DISTINCT")
            select: list[dict[str, Any]] = []
            while True:
                expression = self.expression()
                alias: str | None = None
                if self._optional("AS"):
                    alias = _require_identifier(self._take().text, "alias")
                elif self._peek() is not None and self._peek().kind == "ID" and self._peek().text.upper() not in _RESERVED:
                    alias = _require_identifier(self._take().text, "alias")
                select.append({"expression": expression, "alias": alias})
                if not self._optional(","):
                    break
            self._take("FROM")
            if self._optional("("):
                source: dict[str, Any] = {"kind": "query", "query": self.query()}
                self._take(")")
                if self._optional("AS"):
                    source["alias"] = _require_identifier(self._take().text, "source alias")
                elif self._peek() is not None and self._peek().kind == "ID" and self._peek().text.upper() not in _RESERVED:
                    source["alias"] = _require_identifier(self._take().text, "source alias")
            else:
                table = _require_identifier(self._take().text, "table")
                if table.lower() != SOURCE_ID:
                    raise SQLiteOracleError("only the readings table is permitted")
                source = {"kind": "readings", "alias": None}
                if self._optional("AS"):
                    source["alias"] = _require_identifier(self._take().text, "source alias")
                elif self._peek() is not None and self._peek().kind == "ID" and self._peek().text.upper() not in _RESERVED:
                    source["alias"] = _require_identifier(self._take().text, "source alias")
            where = self.predicate() if self._optional("WHERE") else None
            order: dict[str, Any] | None = None
            if self._optional("ORDER"):
                self._take("BY")
                order_expression = self.expression()
                direction = "ASC"
                nulls = None
                if self._peek("ASC") or self._peek("DESC"):
                    direction = self._take().text.upper()
                if self._optional("NULLS"):
                    if self._peek("FIRST"):
                        nulls = "FIRST"
                    elif self._peek("LAST"):
                        nulls = "LAST"
                    else:
                        raise SQLiteOracleError("NULLS must be followed by FIRST or LAST")
                    self.index += 1
                order = {"expression": order_expression, "direction": direction, "nulls": nulls}
            limit: int | None = None
            if self._optional("LIMIT"):
                token = self._take()
                if token.kind != "INT":
                    raise SQLiteOracleError("LIMIT must be a bounded integer literal")
                limit = int(token.text)
                if limit > _MAX_INPUT_ROWS:
                    raise SQLiteOracleError(f"LIMIT must be at most {_MAX_INPUT_ROWS}")
            return {"select": select, "distinct": distinct, "source": source, "where": where, "order": order, "limit": limit}
        finally:
            self.depth -= 1

    def expression(self) -> dict[str, Any]:
        self._node()
        negative = self._optional("-")
        token = self._take()
        if token.kind == "INT":
            value = int(token.text)
            if negative:
                value = -value
            if not -_MAX_INTEGER <= value <= _MAX_INTEGER:
                raise SQLiteOracleError("integer literal is outside the bounded range")
            return {"kind": "literal", "value": value}
        if negative:
            raise SQLiteOracleError("only integer literals may be negative")
        if token.kind != "ID":
            raise SQLiteOracleError("expected a column, NULL, integer, or COALESCE expression")
        upper = token.text.upper()
        if upper == "NULL":
            return {"kind": "literal", "value": None}
        if upper == "COALESCE":
            self._take("(")
            first = self.expression()
            self._take(",")
            second = self.expression()
            self._take(")")
            return {"kind": "coalesce", "first": first, "second": second}
        if self._optional("."):
            qualified = self._take()
            if qualified.kind != "ID":
                raise SQLiteOracleError("qualified column must name an identifier")
            return {"kind": "column", "name": _require_identifier(qualified.text, "column")}
        return {"kind": "column", "name": _require_identifier(token.text, "column")}

    def predicate(self) -> dict[str, Any]:
        self._node()
        left = self.expression()
        if self._optional("IS"):
            negate = self._optional("NOT")
            self._take("NULL")
            return {"kind": "is_null", "expression": left, "negate": negate}
        operator = self._take()
        if operator.kind != "OP" or operator.text not in {"=", "!=", "<>", "<", ">", "<=", ">="}:
            raise SQLiteOracleError("predicate must use one comparison operator or IS NULL")
        return {"kind": "compare", "left": left, "operator": operator.text, "right": self.expression()}


def _validate_sql(sql: str) -> None:
    _Parser(_tokenize(sql)).parse()


def _runtime_identity(connection: sqlite3.Connection) -> dict[str, Any]:
    source_id = connection.execute("SELECT sqlite_source_id()").fetchone()[0]
    try:
        sqlite_module = importlib.import_module("_sqlite3")
        module_path = getattr(sqlite_module, "__file__", None)
    except ImportError:
        module_path = None
    return {
        "sqlite_version": str(sqlite3.sqlite_version),
        "sqlite_source_id": str(source_id),
        "sqlite_module": str(getattr(sqlite3, "__file__", "")),
        "sqlite_binding_module": str(module_path or ""),
        "sqlite_binding_version": str(getattr(sqlite3, "version", "")),
        "python_version": str(sys.version),
    }


def _base_receipt(operation_id: str, sql: Any, canonical_input: Any) -> dict[str, Any]:
    sql_text = sql if isinstance(sql, str) else ""
    operation_digest = sha256_digest(operation_id)
    binding_module = str(getattr(sqlite3, "__file__", ""))
    return {
        "schema": RECEIPT_SCHEMA,
        "operation": {
            "id": operation_id,
            "operation_id": operation_id,
            "operation_id_digest": operation_digest,
        },
        "operation_id": operation_id,
        "operation_id_digest": operation_digest,
        "input": canonical_input,
        "canonical_input": canonical_input,
        "input_digest": digest_json(canonical_input) if canonical_input is not None else None,
        "sql": sql_text,
        "sql_digest": sha256_digest(sql_text),
        "output": None,
        "canonical_output": None,
        "output_digest": None,
        "status": "rejected",
        "runtime": None,
        "sqlite_version": None,
        "sqlite_source_id": None,
        "binding": {"library": "sqlite3", "module": binding_module},
        "binding_identity": {"library": "sqlite3", "module": binding_module},
        "work": {
            "max_rows": None,
            "timeout_ms": None,
            "rows_bound": 0,
            "output_rows": 0,
            "progress_callbacks": 0,
            "elapsed_ms": 0,
            "capped": False,
        },
        "error": None,
    }


def _authorizer_factory() -> Any:
    def authorizer(action: int, arg1: Any, arg2: Any, database: Any, source: Any) -> int:
        if action == getattr(sqlite3, "SQLITE_SELECT", -1):
            return sqlite3.SQLITE_OK
        if action == getattr(sqlite3, "SQLITE_READ", -1):
            return (
                sqlite3.SQLITE_OK
                if str(arg1).lower() == SOURCE_ID and str(arg2).lower() == "x"
                else sqlite3.SQLITE_DENY
            )
        if action == getattr(sqlite3, "SQLITE_FUNCTION", -1):
            function = str(arg2 or arg1 or "").lower()
            return sqlite3.SQLITE_OK if function == "coalesce" else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_DENY

    return authorizer


def execute_sqlite_oracle(
    table: Mapping[str, Any],
    sql: str,
    operation_id: str = _DEFAULT_OPERATION_ID,
    max_rows: int = _MAX_INPUT_ROWS,
    timeout_ms: int = 1_000,
) -> dict[str, Any]:
    """Execute one bounded SELECT against a fresh in-memory SQLite database."""

    operation = operation_id if isinstance(operation_id, str) and operation_id else _DEFAULT_OPERATION_ID
    receipt = _base_receipt(operation, sql, None)
    started = time.monotonic()
    try:
        if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 128:
            raise SQLiteOracleError("operation_id must be a nonempty bounded string")
        if isinstance(max_rows, bool) or not isinstance(max_rows, int) or not 0 <= max_rows <= _MAX_INPUT_ROWS:
            raise SQLiteOracleError(f"max_rows must be an integer in [0, {_MAX_INPUT_ROWS}]")
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or not 1 <= timeout_ms <= 60_000:
            raise SQLiteOracleError("timeout_ms must be an integer in [1, 60000]")
        _validate_sql(sql)
        canonical_input = canonical_table(table)
        _table_values(canonical_input)
        receipt["input"] = canonical_input
        receipt["canonical_input"] = canonical_input
        receipt["input_digest"] = digest_json(canonical_input)
        receipt["work"]["max_rows"] = max_rows
        receipt["work"]["timeout_ms"] = timeout_ms
        receipt["work"]["rows_bound"] = len(canonical_input["rows"])
    except (SQLiteOracleError, TypeError, AttributeError) as exc:
        receipt["error"] = {"code": "invalid-request", "message": str(exc)[:512]}
        receipt["work"]["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        return receipt

    progress = {"callbacks": 0, "deadline": time.monotonic() + timeout_ms / 1000.0, "aborted": False}
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(":memory:")
        receipt["runtime"] = _runtime_identity(connection)
        receipt["sqlite_version"] = receipt["runtime"]["sqlite_version"]
        receipt["sqlite_source_id"] = receipt["runtime"]["sqlite_source_id"]
        connection.execute("CREATE TABLE readings (x INTEGER)")
        connection.executemany("INSERT INTO readings (x) VALUES (?)", _table_values(canonical_input))
        connection.execute("PRAGMA query_only = ON")
        connection.set_authorizer(_authorizer_factory())

        def progress_handler() -> int:
            progress["callbacks"] += 1
            if time.monotonic() >= progress["deadline"] or progress["callbacks"] > 100_000:
                progress["aborted"] = True
                return 1
            return 0

        connection.set_progress_handler(progress_handler, 100)
        cursor = connection.execute(sql)
        raw_rows = cursor.fetchmany(max_rows + 1)
        description = cursor.description or ()
        columns = [str(item[0]) for item in description]
        if not columns or len(set(columns)) != len(columns):
            raise SQLiteOracleError("query output must have unique named columns")
        output_rows: list[dict[str, Any]] = []
        for row_index, raw_row in enumerate(raw_rows[:max_rows]):
            cells: dict[str, Any] = {}
            for column, raw_value in zip(columns, raw_row):
                if raw_value is None:
                    cells[column] = {"kind": "null"}
                elif isinstance(raw_value, int) and not isinstance(raw_value, bool):
                    cells[column] = _cell({"kind": "integer", "value": raw_value}, f"output row {row_index}.{column}")
                else:
                    raise SQLiteOracleError("query output contains a non-integer/non-NULL value")
            output_rows.append(cells)
        output = canonical_table({"schema": TABLE_SCHEMA, "columns": sorted(columns), "rows": output_rows})
        receipt["output"] = output
        receipt["canonical_output"] = output
        receipt["output_digest"] = digest_json(output)
        receipt["status"] = "resource-exhausted" if len(raw_rows) > max_rows else "supported"
        receipt["work"]["capped"] = len(raw_rows) > max_rows
        if receipt["work"]["capped"]:
            receipt["error"] = {"code": "max-rows", "message": "query output exceeded max_rows"}
    except sqlite3.Error as exc:
        if progress["aborted"]:
            receipt["status"] = "resource-exhausted"
            receipt["error"] = {"code": "deadline", "message": "SQLite progress/deadline limit fired"}
        else:
            receipt["error"] = {"code": "sqlite-rejected", "message": str(exc)[:512]}
    except (SQLiteOracleError, TypeError, ValueError) as exc:
        receipt["status"] = "observation-unavailable"
        receipt["error"] = {"code": "output-normalization", "message": str(exc)[:512]}
    finally:
        receipt["work"]["progress_callbacks"] = progress["callbacks"]
        receipt["work"]["output_rows"] = len(receipt["output"]["rows"]) if isinstance(receipt["output"], Mapping) else 0
        receipt["work"]["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        if connection is not None:
            connection.close()
    return receipt


__all__ = [
    "TABLE_SCHEMA",
    "RECEIPT_SCHEMA",
    "SQLiteOracleError",
    "canonical_json",
    "sha256_digest",
    "digest_json",
    "canonical_digest",
    "table_digest",
    "canonical_table",
    "table_from_rows",
    "execute_sqlite_oracle",
]
