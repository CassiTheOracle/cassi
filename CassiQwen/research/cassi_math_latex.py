"""Bounded exact mathematics across English and LaTeX surfaces.

This module owns deliberately small notation boundaries rather than delegating
symbolic meaning to a general-purpose CAS.  It parses bounded English and
LaTeX expressions/equations into one canonical tree, evaluates exact rational
cases, renders both surfaces, solves linear equations and two-variable
systems, and verifies operation-labelled traces—including exact fractional
coefficient normalization, signed-factor distribution, like-term collection,
variable-term movement, and exact system row operations—by coefficient
equivalence and operation application.  Unsupported syntax fails closed with
a typed error.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping, Sequence


EXPR_SCHEMA = "cassi.math-latex.expression.v1"
EQUATION_SCHEMA = "cassi.math-latex.equation.v1"
WORD_PROBLEM_SCHEMA = "cassi.math-language.word-problem.v1"
WORD_PROBLEM_SYSTEM_SCHEMA = "cassi.math-language.word-problem-system.v1"
WORD_PROBLEM_STORY_SCHEMA = "cassi.math-language.word-problem-story.v1"
WORD_PROBLEM_CHAIN_SCHEMA = "cassi.math-language.word-problem-chain.v1"
MAX_SOURCE_LENGTH = 8_192
MAX_TOKENS = 512
MAX_NODES = 256
MAX_INTEGER_ABS = 10**18
MAX_EXPONENT = 64


class MathLatexError(RuntimeError):
    """Base class for bounded notation, evaluation, and solver failures."""


class MathLatexSyntaxError(MathLatexError):
    """The notation is outside the declared LaTeX subset."""


class MathLatexEvaluationError(MathLatexError):
    """The notation is valid but cannot be evaluated exactly for the inputs."""


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str


_COMMANDS = {
    "frac": "FRAC",
    "sqrt": "SQRT",
    "cdot": "MUL",
    "times": "MUL",
    "left": "LEFT",
    "right": "RIGHT",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _bounded_integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MathLatexEvaluationError("exact numeric value must be an integer")
    if abs(value) > MAX_INTEGER_ABS:
        raise MathLatexEvaluationError("integer exceeds the exact-value budget")
    return value


def _json_value(value: Fraction) -> int | dict[str, int]:
    if value.denominator == 1:
        return _bounded_integer(value.numerator)
    return {
        "numerator": _bounded_integer(value.numerator),
        "denominator": _bounded_integer(value.denominator),
    }


def _fraction(value: Any) -> Fraction:
    if isinstance(value, bool):
        raise MathLatexEvaluationError("boolean is not an exact rational")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(_bounded_integer(value))
    if isinstance(value, Mapping) and set(value) == {"numerator", "denominator"}:
        numerator = _bounded_integer(value["numerator"])
        denominator = _bounded_integer(value["denominator"])
        if denominator == 0:
            raise MathLatexEvaluationError("rational denominator is zero")
        return Fraction(numerator, denominator)
    raise MathLatexEvaluationError(f"value is not an exact rational: {value!r}")


def _tokenize(source: str) -> tuple[_Token, ...]:
    if not isinstance(source, str) or not source.strip():
        raise MathLatexSyntaxError("LaTeX source must be nonempty text")
    if len(source) > MAX_SOURCE_LENGTH:
        raise MathLatexSyntaxError("LaTeX source exceeds the source budget")
    tokens: list[_Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if char.isdigit():
            stop = index + 1
            while stop < len(source) and source[stop].isdigit():
                stop += 1
            tokens.append(_Token("NUMBER", source[index:stop]))
            index = stop
            continue
        if char.isalpha():
            stop = index + 1
            while stop < len(source) and (source[stop].isalnum() or source[stop] == "_"):
                stop += 1
            tokens.append(_Token("IDENT", source[index:stop]))
            index = stop
            continue
        if char == "\\":
            stop = index + 1
            while stop < len(source) and source[stop].isalpha():
                stop += 1
            if stop == index + 1:
                raise MathLatexSyntaxError("LaTeX control symbol is unsupported")
            command = source[index + 1 : stop]
            kind = _COMMANDS.get(command)
            if kind is None:
                if command in {"alpha", "beta", "gamma", "delta", "theta", "lambda", "mu", "pi", "sigma", "phi", "omega"}:
                    tokens.append(_Token("IDENT", command))
                else:
                    raise MathLatexSyntaxError(f"LaTeX command is unsupported: \\{command}")
            else:
                if kind not in {"LEFT", "RIGHT"}:
                    tokens.append(_Token(kind, command))
            index = stop
            continue
        punctuation = {
            "+": "PLUS",
            "-": "MINUS",
            "*": "MUL",
            "/": "DIV",
            "^": "POW",
            "=": "EQUAL",
            "(": "LPAREN",
            ")": "RPAREN",
            "[": "LBRACKET",
            "]": "RBRACKET",
            "{": "LBRACE",
            "}": "RBRACE",
        }
        kind = punctuation.get(char)
        if kind is None:
            raise MathLatexSyntaxError(f"unsupported LaTeX character: {char!r}")
        tokens.append(_Token(kind, char))
        index += 1
        if len(tokens) > MAX_TOKENS:
            raise MathLatexSyntaxError("LaTeX token budget exceeded")
    tokens.append(_Token("EOF", ""))
    return tuple(tokens)


def _node(kind: str, **fields: Any) -> dict[str, Any]:
    result = {"type": kind}
    result.update(fields)
    return result


class _Parser:
    def __init__(self, tokens: Sequence[_Token]):
        self.tokens = tuple(tokens)
        self.index = 0
        self.nodes = 0

    def _peek(self) -> _Token:
        return self.tokens[self.index]

    def _take(self, kind: str | None = None) -> _Token:
        token = self._peek()
        if kind is not None and token.kind != kind:
            raise MathLatexSyntaxError(f"expected {kind}, found {token.kind}")
        self.index += 1
        return token

    def _enter(self) -> None:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise MathLatexSyntaxError("LaTeX expression node budget exceeded")

    @staticmethod
    def _starts_atom(token: _Token) -> bool:
        return token.kind in {"NUMBER", "IDENT", "LPAREN", "LBRACKET", "LBRACE", "FRAC", "SQRT", "MINUS"}

    def expression(self) -> dict[str, Any]:
        result = self.product()
        while self._peek().kind in {"PLUS", "MINUS"}:
            operator = self._take().kind
            right = self.product()
            result = _node("add" if operator == "PLUS" else "sub", left=result, right=right)
        return result

    def product(self) -> dict[str, Any]:
        result = self.power()
        while True:
            if self._peek().kind in {"MUL", "DIV"}:
                operator = self._take().kind
                right = self.power()
                result = _node("mul" if operator == "MUL" else "div", left=result, right=right)
            elif self._starts_atom(self._peek()) and self._peek().kind != "MINUS":
                result = _node("mul", left=result, right=self.power())
            else:
                return result

    def power(self) -> dict[str, Any]:
        result = self.unary()
        if self._peek().kind == "POW":
            self._take("POW")
            result = _node("pow", base=result, exponent=self.group_or_atom())
        return result

    def unary(self) -> dict[str, Any]:
        if self._peek().kind == "MINUS":
            self._take("MINUS")
            return _node("neg", value=self.unary())
        return self.atom()

    def group_or_atom(self) -> dict[str, Any]:
        if self._peek().kind in {"LBRACE", "LPAREN", "LBRACKET"}:
            return self.group()
        return self.atom()

    def group(self) -> dict[str, Any]:
        opening = self._take().kind
        closing = {"LBRACE": "RBRACE", "LPAREN": "RPAREN", "LBRACKET": "RBRACKET"}[opening]
        value = self.expression()
        self._take(closing)
        return value

    def atom(self) -> dict[str, Any]:
        self._enter()
        token = self._peek()
        if token.kind == "NUMBER":
            self._take()
            return _node("const", value=_bounded_integer(int(token.text)))
        if token.kind == "IDENT":
            self._take()
            return _node("symbol", name=token.text)
        if token.kind in {"LPAREN", "LBRACKET", "LBRACE"}:
            return self.group()
        if token.kind == "FRAC":
            self._take()
            return _node("div", left=self.group(), right=self.group())
        if token.kind == "SQRT":
            self._take()
            return _node("sqrt", value=self.group())
        raise MathLatexSyntaxError(f"expected an expression atom, found {token.kind}")

    def equation(self) -> dict[str, Any]:
        left = self.expression()
        self._take("EQUAL")
        right = self.expression()
        self._take("EOF")
        return _node("equation", left=left, right=right)

    def finish_expression(self) -> dict[str, Any]:
        value = self.expression()
        self._take("EOF")
        return value


def _canonicalize(node: Mapping[str, Any], *, depth: int = 0) -> dict[str, Any]:
    if depth > MAX_NODES:
        raise MathLatexSyntaxError("canonical expression depth exceeded")
    kind = node.get("type")
    if kind == "const":
        return _node("const", value=_bounded_integer(node.get("value")))
    if kind == "symbol":
        name = node.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            raise MathLatexSyntaxError("symbol name is invalid")
        return _node("symbol", name=name)
    if kind in {"add", "sub", "mul", "div"}:
        expected = {"add": ("left", "right"), "sub": ("left", "right"), "mul": ("left", "right"), "div": ("left", "right")}[kind]
        if set(node) != {"type", *expected}:
            raise MathLatexSyntaxError(f"{kind} node has invalid fields")
        return _node(kind, left=_canonicalize(node["left"], depth=depth + 1), right=_canonicalize(node["right"], depth=depth + 1))
    if kind == "neg":
        if set(node) != {"type", "value"}:
            raise MathLatexSyntaxError("neg node has invalid fields")
        return _node("neg", value=_canonicalize(node["value"], depth=depth + 1))
    if kind == "sqrt":
        if set(node) != {"type", "value"}:
            raise MathLatexSyntaxError("sqrt node has invalid fields")
        return _node("sqrt", value=_canonicalize(node["value"], depth=depth + 1))
    if kind == "pow":
        if set(node) != {"type", "base", "exponent"}:
            raise MathLatexSyntaxError("pow node has invalid fields")
        return _node("pow", base=_canonicalize(node["base"], depth=depth + 1), exponent=_canonicalize(node["exponent"], depth=depth + 1))
    raise MathLatexSyntaxError(f"unsupported expression node: {kind!r}")


_ENGLISH_IDENTIFIER_WORDS = {
    "and",
    "between",
    "by",
    "difference",
    "divided",
    "equals",
    "is",
    "minus",
    "negative",
    "of",
    "over",
    "plus",
    "power",
    "product",
    "quotient",
    "root",
    "square",
    "sum",
    "the",
    "thrice",
    "times",
    "to",
    "twice",
}
_ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*|\d+|[()+\-*/=]")


def _english_tokens(source: str) -> tuple[str, ...]:
    if not isinstance(source, str) or not source.strip():
        raise MathLatexSyntaxError("English math source must be nonempty text")
    if len(source) > MAX_SOURCE_LENGTH:
        raise MathLatexSyntaxError("English math source exceeds the source budget")
    tokens: list[str] = []
    cursor = 0
    for match in _ENGLISH_TOKEN_RE.finditer(source):
        if source[cursor : match.start()].strip():
            raise MathLatexSyntaxError("English math source contains unsupported text")
        tokens.append(match.group(0).lower())
        cursor = match.end()
    if source[cursor:].strip() or not tokens:
        raise MathLatexSyntaxError("English math source contains unsupported text")
    if len(tokens) > MAX_TOKENS:
        raise MathLatexSyntaxError("English math token budget exceeded")
    return tuple(tokens)


class _EnglishParser:
    def __init__(self, tokens: Sequence[str]):
        self.tokens = tuple(tokens)
        self.index = 0

    def _peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self, expected: str | None = None) -> str:
        token = self._peek()
        if token is None:
            raise MathLatexSyntaxError("English math source ended unexpectedly")
        if expected is not None and token != expected:
            raise MathLatexSyntaxError(f"expected {expected!r}, found {token!r}")
        self.index += 1
        return token

    def _starts_phrase(self, *words: str) -> bool:
        return self.tokens[self.index : self.index + len(words)] == words

    def _expression_end(self) -> bool:
        return self._peek() in {None, "and", "equals", "is", "to", ")"}

    def expression(self) -> dict[str, Any]:
        result = self.term()
        while self._peek() in {"plus", "minus"}:
            operator = self._take()
            right = self.term()
            result = _node("add" if operator == "plus" else "sub", left=result, right=right)
        return result

    def term(self) -> dict[str, Any]:
        result = self.atom()
        while True:
            if self._peek() in {"times", "*"}:
                self._take()
                right = self.atom()
                result = _node("mul", left=result, right=right)
            elif self._starts_phrase("divided", "by"):
                self._take("divided")
                self._take("by")
                result = _node("div", left=result, right=self.atom())
            elif self._peek() in {"over", "/"}:
                self._take()
                result = _node("div", left=result, right=self.atom())
            else:
                return result

    def atom(self) -> dict[str, Any]:
        token = self._peek()
        if token is None:
            raise MathLatexSyntaxError("English math atom is missing")
        if token.isdigit():
            self._take()
            return _node("const", value=_bounded_integer(int(token)))
        if token in {"(",}:
            self._take("(")
            value = self.expression()
            self._take(")")
            return value
        if token in {"negative", "-"}:
            self._take()
            return _node("neg", value=self.atom())
        if token == "twice":
            self._take()
            return _node("mul", left=_node("const", value=2), right=self.atom())
        if token == "thrice":
            self._take()
            return _node("mul", left=_node("const", value=3), right=self.atom())
        if self._starts_phrase("the", "sum", "of"):
            self._take("the")
            self._take("sum")
            self._take("of")
            left = self.expression()
            self._take("and")
            return _node("add", left=left, right=self.expression())
        if self._starts_phrase("the", "difference", "between"):
            self._take("the")
            self._take("difference")
            self._take("between")
            left = self.expression()
            self._take("and")
            return _node("sub", left=left, right=self.expression())
        if self._starts_phrase("the", "product", "of"):
            self._take("the")
            self._take("product")
            self._take("of")
            left = self.expression()
            self._take("and")
            return _node("mul", left=left, right=self.expression())
        if self._starts_phrase("the", "quotient", "of"):
            self._take("the")
            self._take("quotient")
            self._take("of")
            left = self.expression()
            self._take("and")
            return _node("div", left=left, right=self.expression())
        if self._starts_phrase("the", "square", "root", "of"):
            self._take("the")
            self._take("square")
            self._take("root")
            self._take("of")
            return _node("sqrt", value=self.expression())
        if self._starts_phrase("the", "power", "of"):
            self._take("the")
            self._take("power")
            self._take("of")
            base = self.expression()
            self._take("to")
            return _node("pow", base=base, exponent=self.expression())
        if token in _ENGLISH_IDENTIFIER_WORDS or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", token):
            raise MathLatexSyntaxError(f"unexpected English math word: {token!r}")
        self._take()
        return _node("symbol", name=token)

    def finish_expression(self) -> dict[str, Any]:
        value = self.expression()
        if self._peek() is not None:
            raise MathLatexSyntaxError(f"unexpected English math token: {self._peek()!r}")
        return _canonicalize(value)

    def finish_equation(self) -> dict[str, Any]:
        left = self.expression()
        if self._peek() not in {"equals", "is"}:
            raise MathLatexSyntaxError("English equation needs equals or is")
        self._take()
        right = self.expression()
        if self._peek() is not None:
            raise MathLatexSyntaxError(f"unexpected English math token: {self._peek()!r}")
        return {"left": _canonicalize(left), "right": _canonicalize(right)}


def parse_english_expression(source: str) -> dict[str, Any]:
    return {"schema": EXPR_SCHEMA, "body": _EnglishParser(_english_tokens(source)).finish_expression()}


def parse_english_equation(source: str) -> dict[str, Any]:
    body = _EnglishParser(_english_tokens(source)).finish_equation()
    return {"schema": EQUATION_SCHEMA, **body}


def _word_problem_symbols(node: Mapping[str, Any]) -> set[str]:
    kind = node.get("type")
    if kind == "symbol":
        return {str(node["name"])}
    if kind in {"const"}:
        return set()
    if kind in {"neg", "sqrt"}:
        return _word_problem_symbols(node["value"])
    if kind == "pow":
        return _word_problem_symbols(node["base"]) | _word_problem_symbols(node["exponent"])
    if kind in {"add", "sub", "mul", "div"}:
        return _word_problem_symbols(node["left"]) | _word_problem_symbols(node["right"])
    raise MathLatexSyntaxError(f"word-problem tree contains unsupported node: {kind!r}")


def _normalize_word_problem(source: str, variable: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise MathLatexSyntaxError("word problem must be nonempty text")
    if len(source) > MAX_SOURCE_LENGTH:
        raise MathLatexSyntaxError("word problem exceeds the source budget")
    if not isinstance(variable, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable):
        raise MathLatexSyntaxError("word-problem variable is invalid")
    normalized = source.lower().strip()
    replacements = (
        (r"\bis equal to\b", "equals"),
        (r"\bincreased by\b", "plus"),
        (r"\bdecreased by\b", "minus"),
        (r"\bmultiplied by\b", "times"),
        (r"\bthree times\b", "thrice"),
        (r"\btwo times\b", "twice"),
        (r"\b(an|a|the) unknown number\b", variable),
        (r"\b(an|a|the) number\b", variable),
        (r"\bthe unknown\b", variable),
    )
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized)
    if re.search(r"\b(?:an?|unknown|number|quantity)\b", normalized):
        raise MathLatexSyntaxError("word problem contains an unsupported unknown phrase")
    return normalized


def parse_english_word_problem(source: str, variable: str = "x") -> dict[str, Any]:
    normalized = _normalize_word_problem(source, variable)
    equation = parse_english_equation(normalized)
    symbols = _word_problem_symbols(equation["left"]) | _word_problem_symbols(equation["right"])
    if symbols - {variable}:
        raise MathLatexSyntaxError("word problem contains an unsupported named symbol")
    return {
        "schema": WORD_PROBLEM_SCHEMA,
        "source": source,
        "normalized": normalized,
        "variable": variable,
        "equation": equation,
        "rendered_latex": render_latex(equation),
        "rendered_english": render_english(equation),
    }


def solve_english_word_problem(source: str, variable: str = "x") -> dict[str, Any]:
    problem = parse_english_word_problem(source, variable)
    return {
        "schema": WORD_PROBLEM_SCHEMA,
        "problem": problem,
        "solution": solve_linear_equation(problem["equation"], variable),
    }


def _normalize_word_problem_system(source: str, variables: Sequence[str]) -> str:
    if not isinstance(source, str) or not source.strip():
        raise MathLatexSyntaxError("word problem system must be nonempty text")
    if len(source) > MAX_SOURCE_LENGTH:
        raise MathLatexSyntaxError("word problem system exceeds the source budget")
    if (
        not isinstance(variables, Sequence)
        or isinstance(variables, (str, bytes))
        or len(variables) != 2
        or any(
            not isinstance(variable, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable)
            for variable in variables
        )
        or variables[0] == variables[1]
    ):
        raise MathLatexSyntaxError("word-problem system needs two distinct variables")
    first, second = str(variables[0]), str(variables[1])
    normalized = source.lower().strip()

    def _compound_growth(match: re.Match[str]) -> str:
        rate = int(match.group(1))
        periods = int(match.group(2))
        if not 0 <= rate <= 1_000 or not 1 <= periods <= 6:
            raise MathLatexSyntaxError("interest story exceeds the bounded growth budget")
        growth = second
        for _ in range(periods):
            growth = f"({growth} plus ({rate} divided by 100) times {growth})"
        return f"{first} is {growth}"

    normalized = re.sub(
        rf"\ban investment {re.escape(second)} grows by (\d+) percent for (\d+) years to {re.escape(first)}\b",
        _compound_growth,
        normalized,
    )
    normalized = re.sub(
        rf"\ba principal {re.escape(second)} earns (\d+) percent compound interest for (\d+) years to {re.escape(first)}\b",
        _compound_growth,
        normalized,
    )

    def _simple_interest(match: re.Match[str]) -> str:
        rate = int(match.group(1))
        periods = int(match.group(2))
        if not 0 <= rate <= 1_000 or not 1 <= periods <= 20:
            raise MathLatexSyntaxError("interest story exceeds the bounded interest budget")
        return f"{first} is {second} plus ({rate} times {periods} divided by 100) times {second}"

    normalized = re.sub(
        rf"\ba principal {re.escape(second)} earns (\d+) percent simple interest for (\d+) years to {re.escape(first)}\b",
        _simple_interest,
        normalized,
    )
    replacements = (
        (r"\bis equal to\b", "equals"),
        (r"\bincreased by\b", "plus"),
        (r"\bdecreased by\b", "minus"),
        (r"\bmultiplied by\b", "times"),
        (rf"\b{re.escape(first)} is (\d+) years older than {re.escape(second)}\b", f"{first} is {second} plus \\1"),
        (rf"\b{re.escape(first)} is (\d+) years younger than {re.escape(second)}\b", f"{first} is {second} minus \\1"),
        (rf"\b{re.escape(first)} is (\d+) dollars? more than {re.escape(second)}\b", f"{first} is {second} plus \\1"),
        (rf"\b{re.escape(first)} is (\d+) dollars? less than {re.escape(second)}\b", f"{first} is {second} minus \\1"),
        (rf"\b{re.escape(first)} is (\d+) percent more than {re.escape(second)}\b", f"{first} is {second} plus (\\1 divided by 100) times {second}"),
        (rf"\b{re.escape(first)} is (\d+) percent less than {re.escape(second)}\b", f"{first} is {second} minus (\\1 divided by 100) times {second}"),
        (
            rf"\ba (\d+) percent discount followed by (\d+) percent tax on {re.escape(second)} gives {re.escape(first)}\b",
            f"{first} is ({second} minus (\\1 divided by 100) times {second}) plus (\\2 divided by 100) times ({second} minus (\\1 divided by 100) times {second})",
        ),
        (
            rf"\ba (\d+) percent markup followed by (\d+) percent tax on {re.escape(second)} gives {re.escape(first)}\b",
            f"{first} is ({second} plus (\\1 divided by 100) times {second}) plus (\\2 divided by 100) times ({second} plus (\\1 divided by 100) times {second})",
        ),
        (rf"\ba (\d+) percent discount on {re.escape(second)} gives {re.escape(first)}\b", f"{first} is {second} minus (\\1 divided by 100) times {second}"),
        (rf"\ba (\d+) percent markup on {re.escape(second)} gives {re.escape(first)}\b", f"{first} is {second} plus (\\1 divided by 100) times {second}"),
        (rf"\b{re.escape(first)} is half (?:of|as much as) {re.escape(second)}\b", f"{first} is {second} divided by 2"),
        (r"\b(?:one number|one quantity) is (\d+) percent more than (?:another|the other)\b", f"{first} is {second} plus (\\1 divided by 100) times {second}"),
        (r"\b(?:one number|one quantity) is (\d+) percent less than (?:another|the other)\b", f"{first} is {second} minus (\\1 divided by 100) times {second}"),
        (r"\b(?:one number|one quantity) is half (?:of|as much as) (?:another|the other)\b", f"{first} is {second} divided by 2"),
        (r"\b(?:one number|one quantity) is (\d+) times (?:another|the other)\b", f"{first} is \\1 times {second}"),
        (r"\btheir ages (?:sum to|add to|total)\b", f"{first} plus {second} equals"),
        (r"\bone number is twice (?:another|the other)\b", f"{first} is twice {second}"),
        (r"\bone number is (\d+) more than (?:another|the other)\b", f"{first} is {second} plus \\1"),
        (r"\bone number is (\d+) less than (?:another|the other)\b", f"{first} is {second} minus \\1"),
        (r"\bthe first number is twice the second\b", f"{first} is twice {second}"),
        (r"\bthe first number is (\d+) more than the second\b", f"{first} is {second} plus \\1"),
        (r"\bthe first number is (\d+) less than the second\b", f"{first} is {second} minus \\1"),
        (r"\bthe difference between two numbers\b", f"{first} minus {second}"),
        (r"\bthe difference of two numbers\b", f"{first} minus {second}"),
        (r"\bthe sum of two numbers\b", f"{first} plus {second}"),
        (r"\btheir difference\b", f"{first} minus {second}"),
        (r"\btheir sum\b", f"{first} plus {second}"),
        (r"\bthe first number\b", first),
        (r"\bthe second number\b", second),
        (r"\bthree times\b", "thrice"),
        (r"\btwo times\b", "twice"),
    )
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def parse_english_word_problem_system(
    source: str, variables: Sequence[str] = ("x", "y")
) -> dict[str, Any]:
    normalized = _normalize_word_problem_system(source, variables)
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for separator in re.finditer(r"\band\b", normalized):
        left_source = normalized[: separator.start()].strip()
        right_source = normalized[separator.end() :].strip()
        try:
            equations = (parse_english_equation(left_source), parse_english_equation(right_source))
        except MathLatexSyntaxError:
            continue
        candidates.append(equations)
    if len(candidates) != 1:
        raise MathLatexSyntaxError("word-problem system needs exactly two equations joined by and")
    equations = candidates[0]
    allowed = set(str(variable) for variable in variables)
    symbols = set().union(
        *(
            _word_problem_symbols(equation["left"]) | _word_problem_symbols(equation["right"])
            for equation in equations
        )
    )
    if symbols - allowed:
        raise MathLatexSyntaxError("word-problem system contains an unsupported named symbol")
    return {
        "schema": WORD_PROBLEM_SYSTEM_SCHEMA,
        "source": source,
        "normalized": normalized,
        "variables": list(variables),
        "equations": list(equations),
        "rendered_latex": " ; ".join(render_latex(equation) for equation in equations),
        "rendered_english": " and ".join(render_english(equation) for equation in equations),
    }


def solve_english_word_problem_system(
    source: str, variables: Sequence[str] = ("x", "y")
) -> dict[str, Any]:
    problem = parse_english_word_problem_system(source, variables)
    return {
        "schema": WORD_PROBLEM_SYSTEM_SCHEMA,
        "problem": problem,
        "solution": solve_linear_system(problem["equations"], variables),
    }


def _normalize_story_surface(
    source: str, variables: Sequence[str], aliases: Mapping[str, str]
) -> tuple[str, dict[str, str]]:
    if not isinstance(aliases, Mapping):
        raise MathLatexSyntaxError("story aliases must be a mapping")
    if (
        not isinstance(variables, Sequence)
        or isinstance(variables, (str, bytes))
        or len(variables) != 2
        or any(
            not isinstance(variable, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable)
            for variable in variables
        )
        or variables[0] == variables[1]
    ):
        raise MathLatexSyntaxError("word-problem story needs two distinct variables")
    normalized_aliases: dict[str, str] = {}
    allowed = {str(variable) for variable in variables}
    for label, variable in aliases.items():
        if (
            not isinstance(label, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", label)
            or not isinstance(variable, str)
            or variable not in allowed
        ):
            raise MathLatexSyntaxError("story alias is invalid")
        normalized_aliases[label.lower()] = variable
    normalized = source.lower().strip()
    for label in sorted(normalized_aliases, key=len, reverse=True):
        normalized = re.sub(
            rf"\b{re.escape(label)}\b", normalized_aliases[label], normalized
        )
    first, second = str(variables[0]), str(variables[1])
    cost_pattern = (
        rf"\b(\d+) (?:tickets|items|units) cost {re.escape(first)} dollars? each "
        rf"and (\d+) (?:tickets|items|units) cost {re.escape(second)} dollars? each "
        rf"for (\d+) dollars? total\b"
    )
    normalized = re.sub(
        cost_pattern,
        rf"\1 times {first} plus \2 times {second} equals \3",
        normalized,
    )
    return normalized, normalized_aliases


def parse_english_word_problem_story(
    source: str,
    variables: Sequence[str] = ("x", "y"),
    aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(source, str) or len(source) > MAX_SOURCE_LENGTH:
        raise MathLatexSyntaxError("word-problem story exceeds the source budget")
    story_source, normalized_aliases = _normalize_story_surface(
        source, variables, aliases or {}
    )
    system = parse_english_word_problem_system(story_source, variables)
    return {
        "schema": WORD_PROBLEM_STORY_SCHEMA,
        "source": source,
        "aliases": normalized_aliases,
        "variables": list(variables),
        "normalized": system["normalized"],
        "system": system,
        "rendered_latex": system["rendered_latex"],
        "rendered_english": system["rendered_english"],
    }


def solve_english_word_problem_story(
    source: str,
    variables: Sequence[str] = ("x", "y"),
    aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    problem = parse_english_word_problem_story(source, variables, aliases)
    return {
        "schema": WORD_PROBLEM_STORY_SCHEMA,
        "problem": problem,
        "solution": solve_linear_system(problem["system"]["equations"], variables),
    }


def _normalize_chain_surface(
    source: str, variables: Sequence[str], aliases: Mapping[str, str]
) -> tuple[str, dict[str, str]]:
    if not isinstance(aliases, Mapping):
        raise MathLatexSyntaxError("chain aliases must be a mapping")
    if (
        not isinstance(variables, Sequence)
        or isinstance(variables, (str, bytes))
        or not 3 <= len(variables) <= 6
        or any(
            not isinstance(variable, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable)
            for variable in variables
        )
        or len(set(variables)) != len(variables)
    ):
        raise MathLatexSyntaxError("word-problem chain needs three to six variables")
    normalized_variables = tuple(str(variable) for variable in variables)
    allowed = set(normalized_variables)
    normalized_aliases: dict[str, str] = {}
    for label, variable in aliases.items():
        if (
            not isinstance(label, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", label)
            or not isinstance(variable, str)
            or variable not in allowed
        ):
            raise MathLatexSyntaxError("chain alias is invalid")
        normalized_aliases[label.lower()] = variable
    normalized = source.lower().strip()
    for label in sorted(normalized_aliases, key=len, reverse=True):
        normalized = re.sub(
            rf"\b{re.escape(label)}\b", normalized_aliases[label], normalized
        )
    variable_pattern = r"[A-Za-z][A-Za-z0-9_]*"

    def _percent_transition(match: re.Match[str]) -> str:
        rate, operation, source_variable, target_variable = match.groups()
        if source_variable not in allowed or target_variable not in allowed:
            return match.group(0)
        if operation == "discount":
            operator = "minus"
        else:
            operator = "plus"
        return (
            f"{target_variable} is {source_variable} {operator} "
            f"({rate} divided by 100) times {source_variable}"
        )

    normalized = re.sub(
        rf"\ba (\d+) percent (discount|markup|tax) on "
        rf"({variable_pattern}) gives ({variable_pattern})\b",
        _percent_transition,
        normalized,
    )
    return normalized, normalized_aliases


def parse_english_word_problem_chain(
    source: str,
    variables: Sequence[str] = ("x", "y", "z"),
    aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(source, str) or len(source) > MAX_SOURCE_LENGTH:
        raise MathLatexSyntaxError("word-problem chain exceeds the source budget")
    normalized, normalized_aliases = _normalize_chain_surface(
        source, variables, aliases or {}
    )
    pieces = [piece.strip() for piece in re.split(r"\band\b", normalized)]
    if len(pieces) != len(variables):
        raise MathLatexSyntaxError(
            "word-problem chain needs one equation per named state joined by and"
        )
    try:
        equations = tuple(parse_english_equation(piece) for piece in pieces)
    except MathLatexSyntaxError as error:
        raise MathLatexSyntaxError("word-problem chain contains an invalid equation") from error
    allowed = set(str(variable) for variable in variables)
    symbols = set().union(
        *(
            _word_problem_symbols(equation["left"]) | _word_problem_symbols(equation["right"])
            for equation in equations
        )
    )
    if symbols - allowed:
        raise MathLatexSyntaxError("word-problem chain contains an unsupported named symbol")
    return {
        "schema": WORD_PROBLEM_CHAIN_SCHEMA,
        "source": source,
        "aliases": normalized_aliases,
        "normalized": normalized,
        "variables": list(variables),
        "equations": list(equations),
        "rendered_latex": " ; ".join(render_latex(equation) for equation in equations),
        "rendered_english": " and ".join(render_english(equation) for equation in equations),
    }


def solve_english_word_problem_chain(
    source: str,
    variables: Sequence[str] = ("x", "y", "z"),
    aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    problem = parse_english_word_problem_chain(source, variables, aliases)
    return {
        "schema": WORD_PROBLEM_CHAIN_SCHEMA,
        "problem": problem,
        "solution": solve_linear_equations(problem["equations"], variables),
    }


def _render_english(node: Mapping[str, Any]) -> str:
    kind = node["type"]
    if kind == "const":
        return str(node["value"])
    if kind == "symbol":
        return str(node["name"])
    if kind == "neg":
        return "negative " + _render_english(node["value"])
    if kind == "add":
        return f"the sum of {_render_english(node['left'])} and {_render_english(node['right'])}"
    if kind == "sub":
        return f"the difference between {_render_english(node['left'])} and {_render_english(node['right'])}"
    if kind == "mul":
        return f"the product of {_render_english(node['left'])} and {_render_english(node['right'])}"
    if kind == "div":
        return f"the quotient of {_render_english(node['left'])} and {_render_english(node['right'])}"
    if kind == "sqrt":
        return f"the square root of {_render_english(node['value'])}"
    if kind == "pow":
        return f"the power of {_render_english(node['base'])} to {_render_english(node['exponent'])}"
    raise MathLatexSyntaxError(f"cannot render English node: {kind!r}")


def render_english(value: Mapping[str, Any]) -> str:
    if value.get("schema") == EXPR_SCHEMA:
        return _render_english(value["body"])
    if value.get("schema") == EQUATION_SCHEMA:
        return f"{_render_english(value['left'])} equals {_render_english(value['right'])}"
    raise MathLatexSyntaxError("value is not a canonical expression or equation")


def parse_latex_expression(source: str) -> dict[str, Any]:
    body = _Parser(_tokenize(source)).finish_expression()
    return {"schema": EXPR_SCHEMA, "body": _canonicalize(body)}


def parse_latex_equation(source: str) -> dict[str, Any]:
    body = _Parser(_tokenize(source)).equation()
    return {
        "schema": EQUATION_SCHEMA,
        "left": _canonicalize(body["left"]),
        "right": _canonicalize(body["right"]),
    }


def _precedence(node: Mapping[str, Any]) -> int:
    return {"add": 10, "sub": 10, "mul": 20, "div": 20, "neg": 30, "pow": 40}.get(str(node["type"]), 50)


def _render(node: Mapping[str, Any], parent: int = 0) -> str:
    kind = node["type"]
    if kind == "const":
        return str(node["value"])
    if kind == "symbol":
        name = str(node["name"])
        return "\\" + name if name in {"alpha", "beta", "gamma", "delta", "theta", "lambda", "mu", "pi", "sigma", "phi", "omega"} else name
    if kind == "sqrt":
        return "\\sqrt{" + _render(node["value"]) + "}"
    if kind == "neg":
        value = "-" + _render(node["value"], 30)
        return "(" + value + ")" if _precedence(node) < parent else value
    if kind == "pow":
        value = _render(node["base"], 40) + "^{" + _render(node["exponent"]) + "}"
    elif kind == "mul":
        value = _render(node["left"], 20) + r"\cdot " + _render(node["right"], 20)
    elif kind == "div":
        value = r"\frac{" + _render(node["left"]) + "}{" + _render(node["right"]) + "}"
    elif kind in {"add", "sub"}:
        operator = " + " if kind == "add" else " - "
        value = _render(node["left"], 10) + operator + _render(node["right"], 11)
    else:
        raise MathLatexSyntaxError(f"cannot render node: {kind!r}")
    return "(" + value + ")" if _precedence(node) < parent else value


def render_latex(value: Mapping[str, Any]) -> str:
    if value.get("schema") == EXPR_SCHEMA:
        return _render(value["body"])
    if value.get("schema") == EQUATION_SCHEMA:
        return _render(value["left"]) + " = " + _render(value["right"])
    raise MathLatexSyntaxError("value is not a canonical expression or equation")


def _evaluate(node: Mapping[str, Any], values: Mapping[str, Any]) -> Fraction:
    kind = node["type"]
    if kind == "const":
        return Fraction(node["value"])
    if kind == "symbol":
        name = str(node["name"])
        if name not in values:
            raise MathLatexEvaluationError(f"missing symbol value: {name}")
        return _fraction(values[name])
    if kind == "neg":
        return -_evaluate(node["value"], values)
    if kind == "add":
        return _evaluate(node["left"], values) + _evaluate(node["right"], values)
    if kind == "sub":
        return _evaluate(node["left"], values) - _evaluate(node["right"], values)
    if kind == "mul":
        return _evaluate(node["left"], values) * _evaluate(node["right"], values)
    if kind == "div":
        denominator = _evaluate(node["right"], values)
        if denominator == 0:
            raise MathLatexEvaluationError("division by zero")
        return _evaluate(node["left"], values) / denominator
    if kind == "pow":
        exponent = _evaluate(node["exponent"], values)
        if exponent.denominator != 1 or abs(exponent.numerator) > MAX_EXPONENT:
            raise MathLatexEvaluationError("power exponent must be a bounded integer")
        return _evaluate(node["base"], values) ** exponent.numerator
    if kind == "sqrt":
        value = _evaluate(node["value"], values)
        if value < 0:
            raise MathLatexEvaluationError("square root of a negative value is unsupported")
        numerator = math.isqrt(value.numerator)
        denominator = math.isqrt(value.denominator)
        if numerator * numerator != value.numerator or denominator * denominator != value.denominator:
            raise MathLatexEvaluationError("square root is not exact in the rational domain")
        return Fraction(numerator, denominator)
    raise MathLatexEvaluationError(f"cannot evaluate node: {kind!r}")


def evaluate_expression(expression: Mapping[str, Any], values: Mapping[str, Any] | None = None) -> int | dict[str, int]:
    if expression.get("schema") != EXPR_SCHEMA:
        raise MathLatexEvaluationError("expression schema is invalid")
    return _json_value(_evaluate(expression["body"], values or {}))


def evaluate_equation(equation: Mapping[str, Any], values: Mapping[str, Any] | None = None) -> bool:
    if equation.get("schema") != EQUATION_SCHEMA:
        raise MathLatexEvaluationError("equation schema is invalid")
    return _evaluate(equation["left"], values or {}) == _evaluate(equation["right"], values or {})


def _linear(node: Mapping[str, Any], variable: str) -> tuple[Fraction, Fraction]:
    kind = node["type"]
    if kind == "const":
        return Fraction(0), Fraction(node["value"])
    if kind == "symbol":
        name = str(node["name"])
        if name == variable:
            return Fraction(1), Fraction(0)
        raise MathLatexEvaluationError(f"equation contains another symbol: {name}")
    if kind == "neg":
        a, b = _linear(node["value"], variable)
        return -a, -b
    if kind in {"add", "sub"}:
        left = _linear(node["left"], variable)
        right = _linear(node["right"], variable)
        sign = 1 if kind == "add" else -1
        return left[0] + sign * right[0], left[1] + sign * right[1]
    if kind == "mul":
        left = _linear(node["left"], variable)
        right = _linear(node["right"], variable)
        if left[0] and right[0]:
            raise MathLatexEvaluationError("equation is nonlinear")
        if left[0]:
            return left[0] * right[1], left[1] * right[1]
        if right[0]:
            return right[0] * left[1], right[1] * left[1]
        return Fraction(0), left[1] * right[1]
    if kind == "div":
        numerator = _linear(node["left"], variable)
        denominator = _linear(node["right"], variable)
        if denominator[0] or denominator[1] == 0:
            raise MathLatexEvaluationError("linear denominator must be nonzero constant")
        return numerator[0] / denominator[1], numerator[1] / denominator[1]
    if kind == "pow":
        exponent = _linear(node["exponent"], variable)
        if exponent[0] or exponent[1].denominator != 1:
            raise MathLatexEvaluationError("equation exponent must be constant integer")
        power = exponent[1].numerator
        base = _linear(node["base"], variable)
        if power == 0:
            return Fraction(0), Fraction(1)
        if power == 1:
            return base
        if base[0]:
            raise MathLatexEvaluationError("equation is nonlinear")
        return Fraction(0), base[1] ** power
    raise MathLatexEvaluationError(f"node is not linearizable: {kind!r}")


def _linear_multivariate(
    node: Mapping[str, Any], variables: tuple[str, ...]
) -> tuple[tuple[Fraction, ...], Fraction]:
    kind = node["type"]
    width = len(variables)
    if kind == "const":
        return (Fraction(0),) * width, Fraction(node["value"])
    if kind == "symbol":
        name = str(node["name"])
        if name not in variables:
            raise MathLatexEvaluationError(f"equation contains another symbol: {name}")
        coefficients = [Fraction(0)] * width
        coefficients[variables.index(name)] = Fraction(1)
        return tuple(coefficients), Fraction(0)
    if kind == "neg":
        coefficients, constant = _linear_multivariate(node["value"], variables)
        return tuple(-value for value in coefficients), -constant
    if kind in {"add", "sub"}:
        left_coefficients, left_constant = _linear_multivariate(node["left"], variables)
        right_coefficients, right_constant = _linear_multivariate(node["right"], variables)
        sign = 1 if kind == "add" else -1
        return (
            tuple(left + sign * right for left, right in zip(left_coefficients, right_coefficients)),
            left_constant + sign * right_constant,
        )
    if kind == "mul":
        left_coefficients, left_constant = _linear_multivariate(node["left"], variables)
        right_coefficients, right_constant = _linear_multivariate(node["right"], variables)
        left_has_variable = any(left_coefficients)
        right_has_variable = any(right_coefficients)
        if left_has_variable and right_has_variable:
            raise MathLatexEvaluationError("equation is nonlinear")
        if left_has_variable:
            return (
                tuple(value * right_constant for value in left_coefficients),
                left_constant * right_constant,
            )
        if right_has_variable:
            return (
                tuple(value * left_constant for value in right_coefficients),
                right_constant * left_constant,
            )
        return (tuple(Fraction(0) for _ in variables), left_constant * right_constant)
    if kind == "div":
        numerator_coefficients, numerator_constant = _linear_multivariate(
            node["left"], variables
        )
        denominator_coefficients, denominator_constant = _linear_multivariate(
            node["right"], variables
        )
        if any(denominator_coefficients) or denominator_constant == 0:
            raise MathLatexEvaluationError("linear denominator must be nonzero constant")
        return (
            tuple(value / denominator_constant for value in numerator_coefficients),
            numerator_constant / denominator_constant,
        )
    if kind == "pow":
        exponent_coefficients, exponent_constant = _linear_multivariate(
            node["exponent"], variables
        )
        if any(exponent_coefficients) or exponent_constant.denominator != 1:
            raise MathLatexEvaluationError("equation exponent must be constant integer")
        power = exponent_constant.numerator
        base_coefficients, base_constant = _linear_multivariate(node["base"], variables)
        if power == 0:
            return (tuple(Fraction(0) for _ in variables), Fraction(1))
        if power == 1:
            return base_coefficients, base_constant
        if any(base_coefficients):
            raise MathLatexEvaluationError("equation is nonlinear")
        return (tuple(Fraction(0) for _ in variables), base_constant**power)
    raise MathLatexEvaluationError(f"node is not linearizable: {kind!r}")


def _linear_system_equation_form(
    equation: Mapping[str, Any], variables: tuple[str, ...]
) -> tuple[Fraction, ...]:
    if equation.get("schema") != EQUATION_SCHEMA:
        raise MathLatexEvaluationError("system step is not an equation")
    left_coefficients, left_constant = _linear_multivariate(equation["left"], variables)
    right_coefficients, right_constant = _linear_multivariate(equation["right"], variables)
    return tuple(
        left - right
        for left, right in zip(
            left_coefficients + (left_constant,),
            right_coefficients + (right_constant,),
        )
    )


def _linear_equation_form(
    equation: Mapping[str, Any], variable: str
) -> tuple[Fraction, Fraction]:
    if equation.get("schema") != EQUATION_SCHEMA:
        raise MathLatexEvaluationError("trace step is not an equation")
    if not isinstance(variable, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable):
        raise MathLatexEvaluationError("trace variable is invalid")
    left = _linear(equation["left"], variable)
    right = _linear(equation["right"], variable)
    return left[0] - right[0], left[1] - right[1]


def _proportional_forms(
    left: tuple[Fraction, Fraction], right: tuple[Fraction, Fraction]
) -> tuple[bool, Fraction | None]:
    if left == (Fraction(0), Fraction(0)) or right == (Fraction(0), Fraction(0)):
        return left == right, None
    scale: Fraction | None = None
    for left_value, right_value in zip(left, right):
        if left_value != 0:
            scale = right_value / left_value
            break
    if scale is None:
        return False, None
    return all(right_value == scale * left_value for left_value, right_value in zip(left, right)), scale


def _constant_value(node: Mapping[str, Any], variable: str) -> Fraction | None:
    try:
        coefficient, constant = _linear(node, variable)
    except MathLatexEvaluationError:
        return None
    return constant if coefficient == 0 else None


def _distribution_factor(
    node: Mapping[str, Any], variable: str
) -> Fraction | None:
    if node["type"] == "neg":
        nested = _distribution_factor(node["value"], variable)
        return None if nested is None else -nested
    if node["type"] != "mul":
        return None
    left, right = node["left"], node["right"]
    if right["type"] in {"add", "sub"}:
        factor = _constant_value(left, variable)
        if factor is not None:
            return factor
    if left["type"] in {"add", "sub"}:
        factor = _constant_value(right, variable)
        if factor is not None:
            return factor
    return None


def _apply_linear_operation(
    form: tuple[Fraction, Fraction],
    operation: Mapping[str, Any],
    variable: str,
    source_equation: Mapping[str, Any],
) -> tuple[tuple[Fraction, Fraction], dict[str, Any]]:
    if not isinstance(operation, Mapping):
        raise MathLatexEvaluationError("trace operation is not an object")
    kind = operation.get("kind")
    if kind in {"add_both_sides", "subtract_both_sides"}:
        value = _fraction(operation.get("value"))
        normalized = {
            "kind": str(kind),
            "value": _json_value(value),
            "description": (
                f"subtract {_render_fraction(value)} from both sides"
                if kind == "subtract_both_sides"
                else f"add {_render_fraction(value)} to both sides"
            ),
        }
        return form, normalized
    if kind == "multiply_both_sides":
        value = _fraction(operation.get("value"))
        if value == 0:
            raise MathLatexEvaluationError("cannot multiply both sides by zero")
        result = (form[0] * value, form[1] * value)
        return result, {
            "kind": str(kind),
            "value": _json_value(value),
            "description": f"multiply both sides by {_render_fraction(value)}",
        }
    if kind == "divide_both_sides":
        value = _fraction(operation.get("value"))
        if value == 0:
            raise MathLatexEvaluationError("cannot divide both sides by zero")
        result = (form[0] / value, form[1] / value)
        return result, {
            "kind": str(kind),
            "value": _json_value(value),
            "description": f"divide both sides by {_render_fraction(value)}",
        }
    if kind == "distribute_factor":
        factor = _fraction(operation.get("factor"))
        side = operation.get("side")
        if side not in {"left", "right"}:
            raise MathLatexEvaluationError("distribution side is invalid")
        source_node = source_equation["left"] if side == "left" else source_equation["right"]
        actual_factor = _distribution_factor(source_node, variable)
        if actual_factor != factor:
            raise MathLatexEvaluationError("distribution factor does not match source")
        return form, {
            "kind": str(kind),
            "factor": _json_value(factor),
            "side": side,
            "description": (
                f"distribute {_render_fraction(factor)} across the {side} side"
            ),
        }

    if kind == "normalize_variable_coefficient":
        normalized_variable = operation.get("variable", variable)
        if normalized_variable != variable:
            raise MathLatexEvaluationError("trace normalizes a different variable")
        side = operation.get("side")
        if side not in {"left", "right"}:
            raise MathLatexEvaluationError("coefficient normalization side is invalid")
        return form, {
            "kind": str(kind),
            "variable": variable,
            "side": side,
            "description": f"normalize the {variable} coefficient on the {side} side",
        }
    if kind == "collect_like_terms":
        side = operation.get("side")
        if side not in {"left", "right", "both"}:
            raise MathLatexEvaluationError("like-term collection side is invalid")
        return form, {
            "kind": str(kind),
            "side": side,
            "description": f"collect like terms on the {side} side",
        }
    if kind in {"move_variable_term_to_left", "move_variable_term_to_right"}:
        moved_variable = operation.get("variable", variable)
        if moved_variable != variable:
            raise MathLatexEvaluationError("trace moves a different variable")
        coefficient = _fraction(operation.get("coefficient", 1))
        if coefficient == 0:
            raise MathLatexEvaluationError("cannot move a zero variable term")
        side = "left" if kind.endswith("_to_left") else "right"
        moved_expression = (
            source_equation["right"] if side == "left" else source_equation["left"]
        )
        moved_coefficient, _ = _linear(moved_expression, variable)
        if moved_coefficient != coefficient:
            raise MathLatexEvaluationError("moved variable coefficient does not match source")
        coefficient_text = _render_fraction(coefficient)
        term_text = variable if coefficient == 1 else f"{coefficient_text}{variable}"
        return form, {
            "kind": str(kind),
            "variable": variable,
            "coefficient": _json_value(coefficient),
            "description": f"move {term_text} term to the {side} side",
        }
    raise MathLatexEvaluationError(f"unsupported trace operation: {kind!r}")


def _render_fraction(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def verify_linear_trace(
    sources: Sequence[str],
    variable: str,
    operations: Sequence[Mapping[str, Any]] | None = None,
    *,
    surface: str = "latex",
) -> dict[str, Any]:
    """Verify exact solution-set preservation on the selected math surface."""
    if surface == "latex":
        parse_equation = parse_latex_equation
        render_equation = render_latex
        trace_schema = "cassi.math-latex.linear-trace.v1"
    elif surface == "english":
        parse_equation = parse_english_equation
        render_equation = render_english
        trace_schema = "cassi.math-language.linear-trace.v1"
    else:
        raise MathLatexEvaluationError("trace surface is unsupported")
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)) or len(sources) < 2:
        raise MathLatexEvaluationError("a proof trace needs at least two equations")
    if operations is not None and (
        isinstance(operations, (str, bytes)) or len(operations) != len(sources) - 1
    ):
        raise MathLatexEvaluationError("trace operation count must equal transition count")
    steps: list[dict[str, Any]] = []
    forms: list[tuple[Fraction, Fraction]] = []
    equations: list[Mapping[str, Any]] = []
    for index, source in enumerate(sources):
        equation = parse_equation(source)
        equations.append(equation)
        form = _linear_equation_form(equation, variable)
        forms.append(form)
        steps.append(
            {
                "step": index,
                "source": source,
                "rendered": render_equation(equation),
                "normal_form": {
                    "coefficient": _json_value(form[0]),
                    "constant": _json_value(form[1]),
                },
                "solution": solve_linear_equation(equation, variable),
            }
        )
    transitions: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(forms, forms[1:])):
        equivalent, scale = _proportional_forms(left, right)
        transition: dict[str, Any] = {
            "from_step": index,
            "to_step": index + 1,
            "equivalent": equivalent,
            "scale": None if scale is None else _json_value(scale),
        }
        if operations is not None:
            applied_form, normalized_operation = _apply_linear_operation(
                left,
                operations[index],
                variable,
                equations[index],
            )
            transition["operation"] = normalized_operation
            transition["operation_applied"] = applied_form == right
        transitions.append(transition)
    return {
        "schema": trace_schema,
        "variable": variable,
        "steps": steps,
        "transitions": transitions,
        "status": (
            "PASS"
            if all(
                row["equivalent"] and row.get("operation_applied", True)
                for row in transitions
            )
            else "FAIL"
        ),
    }


def solve_linear_equation(equation: Mapping[str, Any], variable: str) -> dict[str, Any]:
    if equation.get("schema") != EQUATION_SCHEMA or not isinstance(variable, str) or not variable:
        raise MathLatexEvaluationError("invalid equation or variable")
    left = _linear(equation["left"], variable)
    right = _linear(equation["right"], variable)
    coefficient = left[0] - right[0]
    constant = left[1] - right[1]
    if coefficient == 0:
        return {"status": "identity" if constant == 0 else "no-solution", "variable": variable}
    return {"status": "unique", "variable": variable, "value": _json_value(-constant / coefficient)}


def _validate_system_variables(variables: Sequence[str]) -> tuple[str, str]:
    if (
        not isinstance(variables, Sequence)
        or isinstance(variables, (str, bytes))
        or len(variables) != 2
    ):
        raise MathLatexEvaluationError("a linear system needs exactly two variables")
    normalized = tuple(str(variable) for variable in variables)
    if (
        normalized[0] == normalized[1]
        or any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable) for variable in normalized)
    ):
        raise MathLatexEvaluationError("linear system variables are invalid")
    return normalized


def _system_form_json(
    form: tuple[Fraction, Fraction, Fraction], variables: tuple[str, str]
) -> dict[str, Any]:
    return {
        variables[0]: _json_value(form[0]),
        variables[1]: _json_value(form[1]),
        "constant": _json_value(form[2]),
    }


def solve_linear_system(
    equations: Sequence[Mapping[str, Any]], variables: Sequence[str]
) -> dict[str, Any]:
    normalized_variables = _validate_system_variables(variables)
    if (
        not isinstance(equations, Sequence)
        or isinstance(equations, (str, bytes))
        or len(equations) != 2
    ):
        raise MathLatexEvaluationError("a linear system needs exactly two equations")
    rows = [
        _linear_system_equation_form(equation, normalized_variables)
        for equation in equations
    ]
    a1, b1, c1 = rows[0]
    a2, b2, c2 = rows[1]
    determinant = a1 * b2 - a2 * b1
    if determinant == 0:
        left_coefficients = (a1, b1)
        right_coefficients = (a2, b2)
        if not any(left_coefficients):
            status = "no-solution" if c1 != 0 else "dependent"
        elif not any(right_coefficients):
            status = "no-solution" if c2 != 0 else "dependent"
        else:
            proportional, scale = _proportional_forms(
                left_coefficients,
                right_coefficients,
            )
            status = (
                "dependent"
                if proportional and scale is not None and c2 == scale * c1
                else "no-solution"
            )
        return {"status": status, "variables": list(normalized_variables)}
    x = (b1 * c2 - b2 * c1) / determinant
    y = (a2 * c1 - a1 * c2) / determinant
    return {
        "status": "unique",
        "variables": {
            normalized_variables[0]: _json_value(x),
            normalized_variables[1]: _json_value(y),
        },
    }


def solve_linear_equations(
    equations: Sequence[Mapping[str, Any]], variables: Sequence[str]
) -> dict[str, Any]:
    if (
        not isinstance(variables, Sequence)
        or isinstance(variables, (str, bytes))
        or not variables
        or any(
            not isinstance(variable, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable)
            for variable in variables
        )
        or len(set(variables)) != len(variables)
    ):
        raise MathLatexEvaluationError("linear-equation variables are invalid")
    normalized_variables = tuple(str(variable) for variable in variables)
    if (
        not isinstance(equations, Sequence)
        or isinstance(equations, (str, bytes))
        or len(equations) != len(normalized_variables)
    ):
        raise MathLatexEvaluationError("a square linear system is required")
    matrix: list[list[Fraction]] = []
    for equation in equations:
        if equation.get("schema") != EQUATION_SCHEMA:
            raise MathLatexEvaluationError("linear system equation schema is invalid")
        left_coefficients, left_constant = _linear_multivariate(
            equation["left"], normalized_variables
        )
        right_coefficients, right_constant = _linear_multivariate(
            equation["right"], normalized_variables
        )
        matrix.append(
            [
                *(left - right for left, right in zip(left_coefficients, right_coefficients)),
                right_constant - left_constant,
            ]
        )
    width = len(normalized_variables)
    pivot_row = 0
    pivots: list[int] = []
    for column in range(width):
        candidate = next(
            (row for row in range(pivot_row, width) if matrix[row][column] != 0),
            None,
        )
        if candidate is None:
            continue
        matrix[pivot_row], matrix[candidate] = matrix[candidate], matrix[pivot_row]
        pivot = matrix[pivot_row][column]
        matrix[pivot_row] = [value / pivot for value in matrix[pivot_row]]
        for row in range(width):
            if row == pivot_row or matrix[row][column] == 0:
                continue
            factor = matrix[row][column]
            matrix[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(matrix[row], matrix[pivot_row])
            ]
        pivots.append(column)
        pivot_row += 1
    if any(
        all(matrix[row][column] == 0 for column in range(width))
        and matrix[row][width] != 0
        for row in range(width)
    ):
        return {"status": "no-solution", "variables": list(normalized_variables)}
    if len(pivots) != width:
        return {"status": "dependent", "variables": list(normalized_variables)}
    solution = {
        normalized_variables[column]: _json_value(matrix[row][width])
        for row, column in enumerate(pivots)
    }
    return {"status": "unique", "variables": solution}


def _system_row_index(value: Any, row_count: int = 2) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < row_count:
        raise MathLatexEvaluationError("system row index is invalid")
    return value


def _apply_system_operation(
    forms: tuple[tuple[Fraction, Fraction, Fraction], ...],
    operation: Mapping[str, Any],
    variables: tuple[str, str],
) -> tuple[tuple[tuple[Fraction, Fraction, Fraction], ...], dict[str, Any]]:
    if not isinstance(operation, Mapping):
        raise MathLatexEvaluationError("system operation is not an object")
    kind = operation.get("kind")
    rows = list(forms)
    if kind == "add_equation_multiple":
        target = _system_row_index(operation.get("target_row"))
        source = _system_row_index(operation.get("source_row"))
        if target == source:
            raise MathLatexEvaluationError("system operation rows must differ")
        multiple = _fraction(operation.get("multiple"))
        rows[target] = tuple(
            rows[target][index] + multiple * rows[source][index] for index in range(3)
        )
        return tuple(rows), {
            "kind": str(kind),
            "target_row": target,
            "source_row": source,
            "multiple": _json_value(multiple),
            "description": f"add { _render_fraction(multiple) } times row {source} to row {target}",
        }
    if kind == "scale_equation":
        row = _system_row_index(operation.get("row"))
        factor = _fraction(operation.get("factor"))
        if factor == 0:
            raise MathLatexEvaluationError("cannot scale a system equation by zero")
        rows[row] = tuple(value * factor for value in rows[row])
        return tuple(rows), {
            "kind": str(kind),
            "row": row,
            "factor": _json_value(factor),
            "description": f"scale row {row} by {_render_fraction(factor)}",
        }
    if kind == "substitute_solution":
        source = _system_row_index(operation.get("source_row"))
        target = _system_row_index(operation.get("target_row"))
        if source == target:
            raise MathLatexEvaluationError("substitution rows must differ")
        variable = operation.get("variable")
        if variable not in variables:
            raise MathLatexEvaluationError("substitution variable is invalid")
        value = _fraction(operation.get("value"))
        variable_index = variables.index(variable)
        other_index = 1 - variable_index
        source_row = rows[source]
        coefficient = source_row[variable_index]
        if coefficient == 0 or source_row[other_index] != 0:
            raise MathLatexEvaluationError("substitution source is not a single-variable solution")
        if -source_row[2] / coefficient != value:
            raise MathLatexEvaluationError("substitution value does not match source")
        target_row = list(rows[target])
        target_row[2] += target_row[variable_index] * value
        target_row[variable_index] = Fraction(0)
        rows[target] = tuple(target_row)
        return tuple(rows), {
            "kind": str(kind),
            "source_row": source,
            "target_row": target,
            "variable": variable,
            "value": _json_value(value),
            "description": f"substitute {variable} = {_render_fraction(value)} into row {target}",
        }
    if kind == "add_constant_both_sides":
        row = _system_row_index(operation.get("row"))
        delta = _fraction(operation.get("delta"))
        return tuple(rows), {
            "kind": str(kind),
            "row": row,
            "delta": _json_value(delta),
            "description": f"add {_render_fraction(delta)} to both sides of row {row}",
        }
    raise MathLatexEvaluationError(f"unsupported system operation: {kind!r}")


def verify_linear_system_trace(
    states: Sequence[Sequence[str]],
    variables: Sequence[str],
    operations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify exact row operations across a two-equation linear-system trace."""
    normalized_variables = _validate_system_variables(variables)
    if (
        not isinstance(states, Sequence)
        or isinstance(states, (str, bytes))
        or len(states) < 2
    ):
        raise MathLatexEvaluationError("a system trace needs at least two states")
    if (
        not isinstance(operations, Sequence)
        or isinstance(operations, (str, bytes))
        or len(operations) != len(states) - 1
    ):
        raise MathLatexEvaluationError("system operation count must equal transition count")
    form_states: list[tuple[tuple[Fraction, Fraction, Fraction], ...]] = []
    step_rows: list[dict[str, Any]] = []
    for state_index, state in enumerate(states):
        if (
            not isinstance(state, Sequence)
            or isinstance(state, (str, bytes))
            or len(state) != 2
        ):
            raise MathLatexEvaluationError("every system state needs two equations")
        equations = tuple(parse_latex_equation(source) for source in state)
        forms = tuple(
            _linear_system_equation_form(equation, normalized_variables)
            for equation in equations
        )
        form_states.append(forms)
        step_rows.append(
            {
                "state": state_index,
                "equations": [
                    {
                        "source": source,
                        "rendered": render_latex(equation),
                        "normal_form": _system_form_json(form, normalized_variables),
                    }
                    for source, equation, form in zip(state, equations, forms)
                ],
                "solution": solve_linear_system(equations, normalized_variables),
            }
        )
    transitions: list[dict[str, Any]] = []
    for index, (current, following) in enumerate(zip(form_states, form_states[1:])):
        expected, normalized_operation = _apply_system_operation(
            current,
            operations[index],
            normalized_variables,
        )
        transitions.append(
            {
                "from_state": index,
                "to_state": index + 1,
                "operation": normalized_operation,
                "operation_applied": expected == following,
            }
        )
    return {
        "schema": "cassi.math-latex.system-trace.v1",
        "variables": list(normalized_variables),
        "steps": step_rows,
        "transitions": transitions,
        "status": "PASS" if all(row["operation_applied"] for row in transitions) else "FAIL",
    }


__all__ = [
    "EQUATION_SCHEMA",
    "EXPR_SCHEMA",
    "WORD_PROBLEM_SCHEMA",
    "WORD_PROBLEM_SYSTEM_SCHEMA",
    "WORD_PROBLEM_STORY_SCHEMA",
    "MathLatexError",
    "MathLatexEvaluationError",
    "MathLatexSyntaxError",
    "digest_value",
    "evaluate_equation",
    "evaluate_expression",
    "parse_english_equation",
    "parse_english_expression",
    "parse_english_word_problem",
    "parse_english_word_problem_system",
    "parse_english_word_problem_story",
    "parse_latex_equation",
    "parse_latex_expression",
    "render_english",
    "render_latex",
    "solve_english_word_problem",
    "solve_english_word_problem_system",
    "solve_english_word_problem_story",
    "solve_linear_equation",
    "solve_linear_system",
    "verify_linear_system_trace",
    "verify_linear_trace",
]
