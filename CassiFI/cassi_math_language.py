"""Bounded symbolic mathematics language for the CassiFI field.

The module deliberately separates three concerns:

* English and LaTeX are finite surface syntaxes;
* canonical typed terms are the shared semantic representation;
* exact arithmetic and linear solving are stateless, independently checkable
  kernels.

Adaptive language knowledge can be stored by CassiFI's existing language
construction records.  This module does not add a learned sidecar or execute
arbitrary TeX macros.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from fractions import Fraction
from typing import Any, Mapping, Sequence

from cassi_field_open_vocab import OpenVocabError, canonical_term

MATH_LANGUAGE_SCHEMA = "cassifi.math-language.v1"
MATH_SOLUTION_SCHEMA = "cassifi.math-solution.v1"

_CONSTRUCTORS = frozenset({
    "add",
    "div",
    "eq",
    "ge",
    "gt",
    "le",
    "lt",
    "mul",
    "pow",
    "sqrt",
})
_RELATIONS = {"eq": "=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
_GREEK_TO_LATEX = {
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "θ": "theta",
    "λ": "lambda",
    "μ": "mu",
    "π": "pi",
    "ρ": "rho",
    "σ": "sigma",
    "τ": "tau",
    "φ": "phi",
    "ω": "omega",
}
_LATEX_TO_GREEK = {value: key for key, value in _GREEK_TO_LATEX.items()}
_LATEX_COMMANDS = {
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "theta",
    "lambda",
    "mu",
    "pi",
    "rho",
    "sigma",
    "tau",
    "phi",
    "omega",
}
_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$|^[^\W\d_]+$", re.UNICODE)


class MathLanguageError(ValueError):
    """Typed refusal from the bounded math language or exact kernel."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise MathLanguageError(code, message)


def _json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value:
        _fail("invalid-term", "math variable name must be nonempty text")
    name = unicodedata.normalize("NFC", value)
    if not _IDENTIFIER_RE.fullmatch(name):
        _fail("invalid-term", f"unsupported math variable name: {value!r}")
    return name

def _integer(value: int) -> dict[str, Any]:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("invalid-term", "math integer must be an integer")
    return {"kind": "atom", "type": {"kind": "atom", "name": "integer"}, "value": value}


def _variable(name: str) -> dict[str, Any]:
    return {
        "kind": "variable",
        "name": _identifier(name),
        "scope": "free",
        "type": {"kind": "named", "name": "real"},
    }


def _node(name: str, *args: Mapping[str, Any]) -> dict[str, Any]:
    return {"kind": "constructor", "name": name, "args": [dict(arg) for arg in args]}


def _integer_value(term: Mapping[str, Any]) -> int | None:
    if (
        term.get("kind") == "atom"
        and term.get("type") == {"kind": "atom", "name": "integer"}
        and isinstance(term.get("value"), int)
        and not isinstance(term.get("value"), bool)
    ):
        return int(term["value"])
    return None


def _constant_fraction(term: Mapping[str, Any]) -> Fraction | None:
    integer = _integer_value(term)
    if integer is not None:
        return Fraction(integer)
    if term.get("kind") == "constructor" and term.get("name") == "div":
        args = term.get("args", [])
        if len(args) == 2:
            numerator = _integer_value(args[0])
            denominator = _integer_value(args[1])
            if numerator is not None and denominator not in (None, 0):
                return Fraction(numerator, denominator)
    return None


def _fraction_term(value: Fraction | int) -> dict[str, Any]:
    fraction = Fraction(value)
    if fraction.denominator == 1:
        return _integer(fraction.numerator)
    return _node("div", _integer(fraction.numerator), _integer(fraction.denominator))


def _sort_key(term: Mapping[str, Any]) -> str:
    return _json(term).decode("utf-8")


def _normalize(term: Mapping[str, Any], *, allow_roles: bool = False) -> dict[str, Any]:
    kind = term.get("kind")
    if kind == "atom":
        if _integer_value(term) is None:
            _fail("unsupported-term", "only exact integer atoms are supported")
        return _integer(int(term["value"]))
    if kind == "variable":
        scope = term.get("scope")
        if scope == "role":
            if not allow_roles:
                _fail("unsupported-term", "math variables must use free scope")
            name = _identifier(str(term.get("name")))
            type_value = term.get("type")
            if type_value not in (
                {"kind": "atom", "name": "integer"},
                {"kind": "named", "name": "variable"},
                {"kind": "named", "name": "term"},
            ):
                _fail("unsupported-term", "math role type is unsupported")
            return {
                "kind": "variable",
                "name": name,
                "scope": "role",
                "type": dict(type_value),
            }
        if scope != "free":
            _fail("unsupported-term", "math variables must use free scope")
        return _variable(str(term.get("name")))
    if kind != "constructor":
        _fail("unsupported-term", "math terms must be integers, variables, or constructors")
    name = term.get("name")
    args = term.get("args")
    if name not in _CONSTRUCTORS or not isinstance(args, list):
        _fail("unsupported-term", f"unsupported math constructor: {name!r}")
    children = [_normalize(arg, allow_roles=allow_roles) for arg in args]
    if name in _RELATIONS:
        if len(children) != 2:
            _fail("invalid-term", f"relation {name!r} needs two arguments")
        return _node(name, *children)
    if name == "add":
        flat: list[dict[str, Any]] = []
        for child in children:
            if child.get("kind") == "constructor" and child.get("name") == "add":
                flat.extend(child["args"])
            else:
                flat.append(child)
        constant = Fraction(0)
        rest: list[dict[str, Any]] = []
        for child in flat:
            value = _constant_fraction(child)
            if value is None:
                rest.append(child)
            else:
                constant += value
        if constant:
            rest.append(_fraction_term(constant))
        if not rest:
            return _integer(0)
        rest.sort(key=_sort_key)
        return rest[0] if len(rest) == 1 else _node("add", *rest)
    if name == "mul":
        flat = []
        for child in children:
            if child.get("kind") == "constructor" and child.get("name") == "mul":
                flat.extend(child["args"])
            else:
                flat.append(child)
        constant = Fraction(1)
        rest = []
        for child in flat:
            value = _constant_fraction(child)
            if value is None:
                rest.append(child)
            else:
                constant *= value
        if constant == 0:
            return _integer(0)
        rest.sort(key=_sort_key)
        if constant != 1 or not rest:
            rest.insert(0, _fraction_term(constant))
        return rest[0] if len(rest) == 1 else _node("mul", *rest)
    if name == "div":
        if len(children) != 2:
            _fail("invalid-term", "division needs two arguments")
        denominator = _constant_fraction(children[1])
        if denominator == 0:
            _fail("undefined", "division by zero is undefined")
        numerator = _constant_fraction(children[0])
        if numerator is not None and denominator is not None:
            return _fraction_term(numerator / denominator)
        if _integer_value(children[0]) == 0:
            return _integer(0)
        if denominator == 1:
            return children[0]
        return _node("div", *children)
    if name == "pow":
        if len(children) != 2:
            _fail("invalid-term", "power needs two arguments")
        exponent = _integer_value(children[1])
        if exponent is None:
            _fail("unsupported-term", "power exponents must be exact integers")
        if exponent == 0:
            return _integer(1)
        if exponent == 1:
            return children[0]
        return _node("pow", *children)
    if name == "sqrt":
        if len(children) != 1:
            _fail("invalid-term", "square root needs one argument")
        return _node("sqrt", children[0])
    _fail("unsupported-term", f"unsupported math constructor: {name!r}")


def canonical_math_term(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize one exact symbolic math term."""

    if not isinstance(value, Mapping):
        _fail("invalid-term", "math term must be an object")
    try:
        raw = canonical_term(value)
    except (OpenVocabError, TypeError, ValueError) as exc:
        raise MathLanguageError("invalid-term", str(exc)) from exc
    return _normalize(raw)


def integer_term(value: int) -> dict[str, Any]:
    return _integer(value)


def variable_term(name: str) -> dict[str, Any]:
    return _variable(name)


class _Token:
    __slots__ = ("kind", "value", "position")

    def __init__(self, kind: str, value: str, position: int):
        self.kind = kind
        self.value = value
        self.position = position

    def __repr__(self) -> str:
        return f"_Token({self.kind!r}, {self.value!r}, {self.position})"


def _tokenize_surface(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if character.isdigit() or character == ".":
            end = index + 1
            dots = int(character == ".")
            while end < len(text) and (text[end].isdigit() or text[end] == "."):
                dots += int(text[end] == ".")
                if dots > 1:
                    _fail("parse-error", f"invalid number near position {index}")
                end += 1
            value = text[index:end]
            if value == ".":
                _fail("parse-error", f"invalid number near position {index}")
            tokens.append(_Token("NUMBER", value, index))
            index = end
            continue
        if character.isalpha() or character == "_":
            end = index + 1
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            tokens.append(_Token("IDENT", text[index:end], index))
            index = end
            continue
        symbols = {
            "+": "PLUS",
            "-": "MINUS",
            "*": "MUL",
            "/": "DIV",
            "^": "POW",
            "=": "EQ",
            "<": "LT",
            ">": "GT",
            "(": "LPAREN",
            ")": "RPAREN",
            "{": "LBRACE",
            "}": "RBRACE",
        }
        kind = symbols.get(character)
        if kind is None:
            _fail("parse-error", f"unsupported symbol {character!r} at position {index}")
        if character in "<>":
            if index + 1 < len(text) and text[index + 1] == "=":
                kind = "LE" if character == "<" else "GE"
                tokens.append(_Token(kind, character + "=", index))
                index += 2
                continue
        tokens.append(_Token(kind, character, index))
        index += 1
    tokens.append(_Token("END", "", len(text)))
    return tokens


def _tokenize_latex(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if character == "\\":
            end = index + 1
            while end < len(text) and text[end].isalpha():
                end += 1
            command = text[index + 1 : end]
            if command in {"left", "right"}:
                index = end
                continue
            if command == "frac":
                tokens.append(_Token("FRAC", command, index))
            elif command == "sqrt":
                tokens.append(_Token("SQRT", command, index))
            elif command in {"cdot", "times"}:
                tokens.append(_Token("MUL", command, index))
            elif command in {"le", "leq"}:
                tokens.append(_Token("LE", command, index))
            elif command in {"ge", "geq"}:
                tokens.append(_Token("GE", command, index))
            elif command in {"neq", "ne"}:
                _fail("unsupported-syntax", "not-equal is outside the first math slice")
            elif command in _LATEX_COMMANDS:
                tokens.append(_Token("IDENT", _LATEX_TO_GREEK[command], index))
            else:
                _fail("unsupported-syntax", f"unsupported LaTeX command \\{command}")
            index = end
            continue
        if character in "≤≥":
            tokens.append(_Token("LE" if character == "≤" else "GE", character, index))
            index += 1
            continue
        if character == "×" or character == "·":
            tokens.append(_Token("MUL", character, index))
            index += 1
            continue
        if character == "−":
            tokens.append(_Token("MINUS", character, index))
            index += 1
            continue
        if character == "π" or character.isalpha() or character == "_":
            end = index + 1
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            tokens.append(_Token("IDENT", text[index:end], index))
            index = end
            continue
        if character.isdigit() or character == ".":
            end = index + 1
            dots = int(character == ".")
            while end < len(text) and (text[end].isdigit() or text[end] == "."):
                dots += int(text[end] == ".")
                if dots > 1:
                    _fail("parse-error", f"invalid number near position {index}")
                end += 1
            tokens.append(_Token("NUMBER", text[index:end], index))
            index = end
            continue
        symbols = {
            "+": "PLUS",
            "-": "MINUS",
            "*": "MUL",
            "/": "DIV",
            "^": "POW",
            "=": "EQ",
            "<": "LT",
            ">": "GT",
            "(": "LPAREN",
            ")": "RPAREN",
            "{": "LBRACE",
            "}": "RBRACE",
        }
        kind = symbols.get(character)
        if kind is None:
            _fail("parse-error", f"unsupported LaTeX character {character!r} at position {index}")
        if character in "<>":
            if index + 1 < len(text) and text[index + 1] == "=":
                kind = "LE" if character == "<" else "GE"
                tokens.append(_Token(kind, character + "=", index))
                index += 2
                continue
        tokens.append(_Token(kind, character, index))
        index += 1
    tokens.append(_Token("END", "", len(text)))
    return tokens


class _Parser:
    def __init__(self, tokens: Sequence[_Token]):
        self.tokens = list(tokens)
        self.index = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def take(self, kind: str | None = None) -> _Token:
        token = self.current
        if kind is not None and token.kind != kind:
            _fail("parse-error", f"expected {kind}, got {token.kind} at position {token.position}")
        self.index += 1
        return token

    def parse(self) -> dict[str, Any]:
        result = self.relation()
        if self.current.kind != "END":
            _fail("parse-error", f"unexpected token {self.current.value!r} at position {self.current.position}")
        return canonical_math_term(result)

    def relation(self) -> dict[str, Any]:
        left = self.addition()
        if self.current.kind in {"EQ", "LT", "LE", "GT", "GE"}:
            token = self.take()
            right = self.addition()
            if self.current.kind in {"EQ", "LT", "LE", "GT", "GE"}:
                _fail("parse-error", "a relation may contain only one comparison")
            return _node({"EQ": "eq", "LT": "lt", "LE": "le", "GT": "gt", "GE": "ge"}[token.kind], left, right)
        return left

    def addition(self) -> dict[str, Any]:
        result = self.multiplication()
        while self.current.kind in {"PLUS", "MINUS"}:
            operator = self.take().kind
            right = self.multiplication()
            if operator == "PLUS":
                result = _node("add", result, right)
            else:
                result = _node("add", result, _node("mul", _integer(-1), right))
        return result

    def multiplication(self) -> dict[str, Any]:
        result = self.power()
        while True:
            if self.current.kind in {"MUL", "DIV"}:
                operator = self.take().kind
                right = self.power()
                result = _node("mul" if operator == "MUL" else "div", result, right)
                continue
            if self.current.kind in {"NUMBER", "IDENT", "LPAREN", "LBRACE", "FRAC", "SQRT"}:
                result = _node("mul", result, self.power())
                continue
            return result

    def power(self) -> dict[str, Any]:
        result = self.prefix()
        if self.current.kind == "POW":
            self.take()
            result = _node("pow", result, self.power())
        return result

    def prefix(self) -> dict[str, Any]:
        if self.current.kind == "PLUS":
            self.take()
            return self.prefix()
        if self.current.kind == "MINUS":
            self.take()
            return _node("mul", _integer(-1), self.prefix())
        return self.primary()

    def primary(self) -> dict[str, Any]:
        token = self.current
        if token.kind == "NUMBER":
            self.take()
            try:
                value = Fraction(token.value)
            except (ValueError, ZeroDivisionError) as exc:
                raise MathLanguageError("parse-error", f"invalid number {token.value!r}") from exc
            return _fraction_term(value)
        if token.kind == "IDENT":
            self.take()
            return _variable(token.value)
        if token.kind in {"LPAREN", "LBRACE"}:
            opening = self.take().kind
            closing = "RPAREN" if opening == "LPAREN" else "RBRACE"
            result = self.relation()
            self.take(closing)
            return result
        if token.kind == "FRAC":
            self.take()
            numerator = self.group()
            denominator = self.group()
            return _node("div", numerator, denominator)
        if token.kind == "SQRT":
            self.take()
            return _node("sqrt", self.group())
        _fail("parse-error", f"expected expression at position {token.position}")

    def group(self) -> dict[str, Any]:
        if self.current.kind in {"LPAREN", "LBRACE"}:
            return self.primary()
        return self.power()


def parse_latex(text: str) -> dict[str, Any]:
    """Parse the bounded LaTeX/math-symbol surface into a canonical term."""

    if not isinstance(text, str) or not text.strip():
        _fail("parse-error", "LaTeX expression must be nonempty text")
    return _Parser(_tokenize_latex(text)).parse()


def _english_surface(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        _fail("parse-error", "English expression must be nonempty text")
    value = unicodedata.normalize("NFC", text.lower().strip())
    value = re.sub(r"[?!,.;:]", " ", value)
    value = re.sub(r"\bis equal to\b|\bequal to\b|\bequals\b|\bis\b", " = ", value)
    replacements = (
        (r"\bthe\s+sum\s+of\s+([\wα-ω]+)\s+and\s+([\wα-ω]+)\b", r"\1 + \2"),
        (r"\bthe\s+difference\s+between\s+([\wα-ω]+)\s+and\s+([\wα-ω]+)\b", r"\1 - \2"),
        (r"\bthe\s+product\s+of\s+([\wα-ω]+)\s+and\s+([\wα-ω]+)\b", r"\1 * \2"),
        (r"\bthe\s+quotient\s+of\s+([\wα-ω]+)\s+and\s+([\wα-ω]+)\b", r"\1 / \2"),
        (r"\bthe\s+square\s+of\s+([\wα-ω]+)\b", r"\1 ^ 2"),
        (r"\b([\wα-ω]+)\s+more\s+than\s+([\wα-ω]+)\b", r"\2 + \1"),
        (r"\b([\wα-ω]+)\s+less\s+than\s+([\wα-ω]+)\b", r"\2 - \1"),
        (r"\btwice\s+([\wα-ω]+)\b", r"2 * \1"),
        (r"\bdouble\s+([\wα-ω]+)\b", r"2 * \1"),
        (r"\b([\wα-ω]+)\s+squared\b", r"\1 ^ 2"),
        (r"\b([\wα-ω]+)\s+to\s+the\s+power\s+of\s+([\wα-ω]+)\b", r"\1 ^ \2"),
        (r"\b([\wα-ω]+)\s+divided\s+by\s+([\wα-ω]+)\b", r"\1 / \2"),
        (r"\b([\wα-ω]+)\s+multiplied\s+by\s+([\wα-ω]+)\b", r"\1 * \2"),
        (r"\b([\wα-ω]+)\s+times\s+([\wα-ω]+)\b", r"\1 * \2"),
    )
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value)
    word_replacements = (
        (r"\bplus\b|\badded\s+to\b|\badd\b", " + "),
        (r"\bminus\b|\bsubtracted\s+from\b|\bsubtract\b", " - "),
        (r"\bdivided\s+by\b|\bover\b", " / "),
        (r"\bmultiplied\s+by\b|\btimes\b", " * "),
        (r"\bto\s+the\s+power\s+of\b", " ^ "),
    )
    for pattern, replacement in word_replacements:
        value = re.sub(pattern, replacement, value)
    for word, number in _NUMBER_WORDS.items():
        value = re.sub(rf"\b{word}\b", str(number), value)
    value = re.sub(r"\bthe\b|\ba\b|\ban\b", " ", value)
    value = re.sub(r"\band\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_english(text: str) -> dict[str, Any]:
    """Parse the bounded teaching-language surface into a canonical term."""

    return _Parser(_tokenize_surface(_english_surface(text))).parse()


def _precedence(term: Mapping[str, Any]) -> int:
    if term.get("kind") != "constructor":
        return 5
    return 1 if term.get("name") in _RELATIONS else 2 if term.get("name") == "add" else 3 if term.get("name") in {"mul", "div"} else 4


def _negative_parts(term: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    integer = _integer_value(term)
    if integer is not None and integer < 0:
        return True, _integer(-integer)
    if term.get("kind") == "constructor" and term.get("name") == "mul":
        args = term.get("args", [])
        if args and _constant_fraction(args[0]) is not None and _constant_fraction(args[0]) < 0:
            magnitude = _constant_fraction(args[0]) * -1
            rest = list(args[1:])
            positive = _fraction_term(magnitude)
            if rest:
                return True, _normalize(_node("mul", positive, *rest))
            return True, positive
    return False, dict(term)


def _latex(term: Mapping[str, Any], parent: int = 0) -> str:
    kind = term.get("kind")
    if kind == "atom":
        return str(term["value"])
    if kind == "variable":
        name = str(term["name"])
        if name in _GREEK_TO_LATEX:
            return "\\" + _GREEK_TO_LATEX[name]
        return name
    name = term["name"]
    args = term["args"]
    if name in _RELATIONS:
        text = f"{_latex(args[0], 1)} {_RELATIONS[name]} {_latex(args[1], 1)}"
    elif name == "add":
        pieces: list[str] = []
        for index, arg in enumerate(args):
            negative, magnitude = _negative_parts(arg)
            rendered = _latex(magnitude if negative else arg, 2)
            if index == 0:
                pieces.append(("-" if negative else "") + rendered)
            else:
                pieces.append((" - " if negative else " + ") + rendered)
        text = "".join(pieces)
    elif name == "mul":
        if len(args) == 2 and _integer_value(args[0]) not in (None, 0, 1, -1) and args[1].get("kind") in {"variable", "constructor"}:
            text = f"{_latex(args[0], 3)}{_latex(args[1], 3)}"
        elif len(args) == 2 and _integer_value(args[0]) == -1:
            text = "-" + _latex(args[1], 3)
        else:
            text = r" \cdot ".join(_latex(arg, 3) for arg in args)
    elif name == "div":
        text = rf"\frac{{{_latex(args[0])}}}{{{_latex(args[1])}}}"
    elif name == "pow":
        text = rf"{_latex(args[0], 4)}^{{{_latex(args[1])}}}"
    elif name == "sqrt":
        text = rf"\sqrt{{{_latex(args[0])}}}"
    else:
        _fail("unsupported-term", f"cannot render constructor {name!r}")
    if _precedence(term) < parent:
        return rf"\left({text}\right)"
    return text


def render_latex(term: Mapping[str, Any], *, boxed: bool = False) -> str:
    """Render one canonical term into the supported LaTeX subset."""

    text = _latex(canonical_math_term(term))
    return rf"\boxed{{{text}}}" if boxed else text


def _english(term: Mapping[str, Any], parent: int = 0) -> str:
    kind = term.get("kind")
    if kind == "atom":
        return str(term["value"])
    if kind == "variable":
        return str(term["name"])
    name = term["name"]
    args = term["args"]
    if name in _RELATIONS:
        text = f"{_english(args[0], 1)} {'equals' if name == 'eq' else _RELATIONS[name]} {_english(args[1], 1)}"
    elif name == "add":
        pieces = []
        for index, arg in enumerate(args):
            negative, magnitude = _negative_parts(arg)
            rendered = _english(magnitude if negative else arg, 2)
            if index == 0:
                pieces.append(("minus " if negative else "") + rendered)
            else:
                pieces.append((" minus " if negative else " plus ") + rendered)
        text = "".join(pieces)
    elif name == "mul":
        text = " times ".join(_english(arg, 3) for arg in args)
    elif name == "div":
        text = f"{_english(args[0], 3)} divided by {_english(args[1], 3)}"
    elif name == "pow":
        exponent = _integer_value(args[1])
        text = (
            f"{_english(args[0], 4)} squared"
            if exponent == 2
            else f"{_english(args[0], 4)} to the power of {_english(args[1])}"
        )
    elif name == "sqrt":
        text = f"the square root of {_english(args[0])}"
    else:
        _fail("unsupported-term", f"cannot render constructor {name!r}")
    if _precedence(term) < parent:
        return f"( {text} )"
    return text


def render_english(term: Mapping[str, Any]) -> str:
    """Render one canonical term into an unambiguous teaching phrase."""

    return _english(canonical_math_term(term))


def _fraction_value(value: Any, label: str) -> Fraction:
    if isinstance(value, bool):
        _fail("invalid-value", f"{label} cannot be boolean")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise MathLanguageError("invalid-value", f"{label} is not an exact number") from exc
    _fail("invalid-value", f"{label} must be an integer, rational, or numeric string")


def evaluate(term: Mapping[str, Any], bindings: Mapping[str, Any] | None = None) -> Fraction | bool:
    """Evaluate a ground arithmetic or relation term using exact rationals."""

    row = canonical_math_term(term)
    supplied = dict(bindings or {})

    def visit(node: Mapping[str, Any]) -> Fraction | bool:
        if node["kind"] == "atom":
            return Fraction(int(node["value"]))
        if node["kind"] == "variable":
            name = node["name"]
            if name not in supplied:
                _fail("unbound-variable", f"no value supplied for {name!r}")
            return _fraction_value(supplied[name], f"binding {name!r}")
        name = node["name"]
        args = node["args"]
        if name == "add":
            return sum((visit(arg) for arg in args), Fraction(0))
        if name == "mul":
            result = Fraction(1)
            for arg in args:
                result *= visit(arg)
            return result
        if name == "div":
            numerator, denominator = visit(args[0]), visit(args[1])
            if denominator == 0:
                _fail("undefined", "division by zero is undefined")
            return numerator / denominator
        if name == "pow":
            base, exponent = visit(args[0]), visit(args[1])
            if exponent.denominator != 1:
                _fail("unsupported-value", "exact evaluation needs an integer exponent")
            return base ** exponent.numerator
        if name == "sqrt":
            value = visit(args[0])
            if value < 0:
                _fail("undefined", "square root of a negative value is not real")
            numerator_root = math.isqrt(value.numerator)
            denominator_root = math.isqrt(value.denominator)
            if numerator_root**2 != value.numerator or denominator_root**2 != value.denominator:
                _fail("unsupported-value", "square root is not an exact rational")
            return Fraction(numerator_root, denominator_root)
        left, right = visit(args[0]), visit(args[1])
        if not isinstance(left, Fraction) or not isinstance(right, Fraction):
            _fail("invalid-value", "relation operands must be numeric")
        return {
            "eq": left == right,
            "lt": left < right,
            "le": left <= right,
            "gt": left > right,
            "ge": left >= right,
        }[name]

    return visit(row)


def _linear_form(term: Mapping[str, Any], variable: str) -> tuple[Fraction, Fraction]:
    """Return ``(coefficient, constant)`` for one-variable linear terms."""

    node = canonical_math_term(term)
    if node["kind"] == "atom":
        return Fraction(0), Fraction(int(node["value"]))
    if node["kind"] == "variable":
        if node["name"] != variable:
            _fail("nonlinear", f"equation contains another variable {node['name']!r}")
        return Fraction(1), Fraction(0)
    name = node["name"]
    args = node["args"]
    if name == "add":
        coefficients = [_linear_form(arg, variable) for arg in args]
        return sum((row[0] for row in coefficients), Fraction(0)), sum((row[1] for row in coefficients), Fraction(0))
    if name == "mul":
        nonconstant: list[tuple[Fraction, Fraction]] = []
        constant = Fraction(1)
        for arg in args:
            value = _constant_fraction(arg)
            if value is None:
                nonconstant.append(_linear_form(arg, variable))
            else:
                constant *= value
        if len(nonconstant) > 1:
            _fail("nonlinear", "multiplication contains more than one variable-dependent factor")
        if not nonconstant:
            return Fraction(0), constant
        coefficient, offset = nonconstant[0]
        return constant * coefficient, constant * offset
    if name == "div":
        denominator = _constant_fraction(args[1])
        if denominator is None or denominator == 0:
            _fail("nonlinear", "linear division requires a nonzero constant denominator")
        coefficient, offset = _linear_form(args[0], variable)
        return coefficient / denominator, offset / denominator
    if name == "pow":
        exponent = _integer_value(args[1])
        if exponent == 0:
            return Fraction(0), Fraction(1)
        if exponent == 1:
            return _linear_form(args[0], variable)
        _fail("nonlinear", "powers above one are outside the linear solver")
    _fail("nonlinear", f"constructor {name!r} is outside the linear solver")


def solve_linear_inequality(
    term: Mapping[str, Any], variable: str | None = None
) -> dict[str, Any]:
    """Solve a bounded one-variable exact inequality with an interval certificate."""

    inequality = canonical_math_term(term)
    if (
        inequality.get("kind") != "constructor"
        or inequality.get("name") not in {"lt", "le", "gt", "ge"}
    ):
        _fail(
            "invalid-inequality",
            "linear inequality solving requires one strict or non-strict comparison",
        )
    variables = sorted(_variables(inequality))
    if variable is None:
        if len(variables) != 1:
            _fail("ambiguous-variable", "inequality solving needs exactly one variable")
        variable = variables[0]
    variable = _identifier(variable)
    if variables and variable not in variables:
        _fail("unknown-variable", f"inequality does not contain {variable!r}")
    left_coefficient, left_constant = _linear_form(
        inequality["args"][0], variable
    )
    right_coefficient, right_constant = _linear_form(
        inequality["args"][1], variable
    )
    coefficient = left_coefficient - right_coefficient
    constant = left_constant - right_constant
    variable_node = _variable(variable)
    relation = str(inequality["name"])
    if coefficient == 0:
        satisfied = evaluate(inequality, {variable: 0}) is True
        return {
            "schema": MATH_SOLUTION_SCHEMA,
            "status": "identity" if satisfied else "no-solution",
            "variable": variable,
            "solution": None,
            "steps": [],
            "verified": True,
            "certificate": {
                "kind": "constant-relation",
                "satisfied": satisfied,
            },
        }

    bound = -constant / coefficient
    reversed_relation = coefficient < 0
    final_relation = (
        {
            "lt": "gt",
            "le": "ge",
            "gt": "lt",
            "ge": "le",
        }[relation]
        if reversed_relation
        else relation
    )
    if final_relation in {"lt", "le"}:
        interval = {
            "kind": "interval",
            "variable": variable,
            "lower": None,
            "lower_inclusive": False,
            "upper": _fraction_term(bound),
            "upper_inclusive": final_relation == "le",
        }
        inside = bound - 1
        outside = bound + 1
    else:
        interval = {
            "kind": "interval",
            "variable": variable,
            "lower": _fraction_term(bound),
            "lower_inclusive": final_relation == "ge",
            "upper": None,
            "upper_inclusive": False,
        }
        inside = bound + 1
        outside = bound - 1

    collected = _node(
        relation,
        _node(
            "add",
            _node("mul", _fraction_term(coefficient), variable_node),
            _fraction_term(constant),
        ),
        _integer(0),
    )
    isolated = _node(
        relation,
        _node("mul", _fraction_term(coefficient), variable_node),
        _fraction_term(-constant),
    )
    solved = _node(final_relation, variable_node, _fraction_term(bound))
    boundary_expected = final_relation in {"le", "ge"}
    checks = {
        "boundary": evaluate(inequality, {variable: bound}) is boundary_expected,
        "inside": evaluate(inequality, {variable: inside}) is True,
        "outside": evaluate(inequality, {variable: outside}) is False,
        "final_relation": evaluate(solved, {variable: inside}) is True
        and evaluate(solved, {variable: outside}) is False,
    }
    if boundary_expected:
        checks["final_boundary"] = evaluate(solved, {variable: bound}) is True
    else:
        checks["final_boundary"] = evaluate(solved, {variable: bound}) is False
    if not all(checks.values()):
        _fail(
            "verification-failed",
            "exact linear inequality solution did not replay against its relation",
        )
    return {
        "schema": MATH_SOLUTION_SCHEMA,
        "status": "supported",
        "variable": variable,
        "solution": interval,
        "steps": [
            {"rule": "collect-variable", "equation": canonical_math_term(collected)},
            {"rule": "isolate-variable", "equation": canonical_math_term(isolated)},
            {
                "rule": (
                    "divide-coefficient-reverses-relation"
                    if reversed_relation
                    else "divide-coefficient"
                ),
                "equation": canonical_math_term(solved),
            },
        ],
        "verified": True,
        "certificate": {
            "coefficient": _fraction_term(coefficient),
            "constant": _fraction_term(constant),
            "normal_form": canonical_math_term(collected),
            "isolated_form": canonical_math_term(isolated),
            "final_form": canonical_math_term(solved),
            "checks": checks,
        },
    }


def solve_linear_equation(term: Mapping[str, Any], variable: str | None = None) -> dict[str, Any]:
    """Solve a bounded one-variable exact equation and return a checked trace."""

    equation = canonical_math_term(term)
    if equation.get("kind") != "constructor" or equation.get("name") != "eq":
        _fail("invalid-equation", "linear solving requires an equality")
    variables = sorted(_variables(equation))
    if variable is None:
        if len(variables) != 1:
            _fail("ambiguous-variable", "linear solving needs exactly one variable")
        variable = variables[0]
    variable = _identifier(variable)
    if variables and variable not in variables:
        _fail("unknown-variable", f"equation does not contain {variable!r}")
    left_coefficient, left_constant = _linear_form(equation["args"][0], variable)
    right_coefficient, right_constant = _linear_form(equation["args"][1], variable)
    coefficient = left_coefficient - right_coefficient
    constant = left_constant - right_constant
    variable_node = _variable(variable)
    if coefficient == 0:
        status = "identity" if constant == 0 else "no-solution"
        return {
            "schema": MATH_SOLUTION_SCHEMA,
            "status": status,
            "variable": variable,
            "solution": None,
            "steps": [],
            "verified": True,
        }
    solution_value = -constant / coefficient
    solution = _fraction_term(solution_value)
    collected = _node("eq", _node("add", _node("mul", _fraction_term(coefficient), variable_node), _fraction_term(constant)), _integer(0))
    isolated = _node("eq", _node("mul", _fraction_term(coefficient), variable_node), _fraction_term(-constant))
    solved = _node("eq", variable_node, solution)
    verified = evaluate(equation, {variable: solution_value}) is True

    if not verified:
        _fail("verification-failed", "exact linear solution did not replay against its equation")
    return {
        "schema": MATH_SOLUTION_SCHEMA,
        "status": "supported",
        "variable": variable,
        "solution": solution,
        "steps": [
            {"rule": "collect-variable", "equation": canonical_math_term(collected)},
            {"rule": "isolate-variable", "equation": canonical_math_term(isolated)},
            {"rule": "divide-coefficient", "equation": canonical_math_term(solved)},
        ],
        "verified": True,
    }
def canonical_math_template(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a math term template containing typed role variables."""

    if not isinstance(value, Mapping):
        _fail("invalid-template", "math template must be an object")
    try:
        raw = canonical_term(value)
    except (OpenVocabError, TypeError, ValueError) as exc:
        raise MathLanguageError("invalid-template", str(exc)) from exc
    return _normalize(raw, allow_roles=True)


def _template_roles(term: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    node = canonical_math_template(term)
    roles: dict[str, dict[str, Any]] = {}

    def visit(current: Mapping[str, Any]) -> None:
        if current["kind"] == "variable":
            if current["scope"] == "role":
                previous = roles.get(current["name"])
                if previous is not None and previous != current["type"]:
                    _fail("invalid-template", "role has inconsistent types")
                roles[current["name"]] = dict(current["type"])
            return
        if current["kind"] == "constructor":
            for child in current["args"]:
                visit(child)

    visit(node)
    return roles


def _parse_integer_binding(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        try:
            evaluated = evaluate(value)
        except MathLanguageError as exc:
            _fail("invalid-binding", str(exc))
        if isinstance(evaluated, Fraction) and evaluated.denominator == 1:
            return _integer(evaluated.numerator)
        _fail("invalid-binding", "integer role binding must evaluate to an integer")
    if isinstance(value, bool):
        _fail("invalid-binding", "integer role bindings cannot be boolean")
    if isinstance(value, int):
        return _integer(value)
    if isinstance(value, float) and value.is_integer():
        return _integer(int(value))
    if not isinstance(value, str) or not value.strip():
        _fail("invalid-binding", "integer role bindings must be numeric text")
    lowered = value.strip().lower()
    if lowered in {"twice", "double"}:
        return _integer(2)
    try:
        fraction = Fraction(value.strip())
    except (ValueError, ZeroDivisionError):
        try:
            parsed = parse_english(value)
        except MathLanguageError as exc:
            _fail("invalid-binding", str(exc))
        constant = _constant_fraction(parsed)
        if constant is None or constant.denominator != 1:
            _fail("invalid-binding", "integer role binding is not exact")
        return _integer(constant.numerator)
    if fraction.denominator != 1:
        _fail("invalid-binding", "integer role binding must be integral")
    return _integer(fraction.numerator)


def _binding_term(value: Any, type_name: str) -> dict[str, Any]:
    if type_name == "integer":
        return _parse_integer_binding(value)
    if isinstance(value, Mapping):
        candidate = canonical_math_term(value)
    elif isinstance(value, str) and value.strip():
        try:
            candidate = parse_latex(value)
        except MathLanguageError:
            candidate = parse_english(value)
    else:
        _fail("invalid-binding", "term role binding must be text or a term")
    if type_name == "variable":
        if candidate["kind"] != "variable":
            _fail("invalid-binding", "variable role binding is not a variable")
        return candidate
    return candidate


def instantiate_math_template(
    template: Mapping[str, Any],
    bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """Instantiate a typed math template into a closed canonical term."""

    node = canonical_math_template(template)
    roles = _template_roles(node)
    supplied = {str(name): value for name, value in dict(bindings).items()}
    if set(supplied) != set(roles):
        _fail("invalid-binding", "math role bindings do not match the template")

    def visit(current: Mapping[str, Any]) -> dict[str, Any]:
        if current["kind"] == "variable" and current["scope"] == "role":
            typ = current["type"]
            if typ["kind"] == "atom" and typ["name"] == "integer":
                return _binding_term(supplied[current["name"]], "integer")
            if typ["kind"] == "named" and typ["name"] == "variable":
                return _binding_term(supplied[current["name"]], "variable")
            if typ["kind"] == "named" and typ["name"] == "term":
                return _binding_term(supplied[current["name"]], "term")
            _fail("invalid-template", "math role type is unsupported")
        if current["kind"] == "variable":
            return _variable(current["name"])
        if current["kind"] == "atom":
            return _integer(int(current["value"]))
        return _node(current["name"], *(visit(child) for child in current["args"]))

    return canonical_math_term(visit(node))


def match_math_template(
    template: Mapping[str, Any],
    term: Mapping[str, Any],
) -> dict[str, str] | None:
    """Match a closed term against a typed template and return surface bindings."""

    pattern = canonical_math_template(template)
    target = canonical_math_term(term)
    bindings: dict[str, dict[str, Any]] = {}

    def visit(current: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
        if current["kind"] == "variable" and current["scope"] == "role":
            typ = current["type"]
            if typ["kind"] == "atom" and typ["name"] == "integer":
                if _integer_value(candidate) is None:
                    return False
            elif typ["kind"] == "named" and typ["name"] == "variable":
                if candidate["kind"] != "variable":
                    return False
            elif typ["kind"] == "named" and typ["name"] == "term":
                pass
            else:
                return False
            previous = bindings.get(current["name"])
            if previous is not None:
                return canonical_math_term(previous) == canonical_math_term(candidate)
            bindings[current["name"]] = dict(candidate)
            return True
        if current["kind"] != candidate["kind"]:
            return False
        if current["kind"] == "atom":
            return current == candidate
        if current["kind"] == "variable":
            return current == candidate
        return (
            current["name"] == candidate.get("name")
            and len(current["args"]) == len(candidate.get("args", []))
            and all(visit(left, right) for left, right in zip(current["args"], candidate["args"]))
        )

    if not visit(pattern, target):
        return None
    result: dict[str, str] = {}
    for name, bound in bindings.items():
        if bound["kind"] == "variable":
            result[name] = bound["name"]
        else:
            result[name] = render_latex(bound)
    return result


def validate_math_lessons(
    *,
    template: Mapping[str, Any],
    examples: Sequence[Mapping[str, Any]],
    holdout: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Check paired English/LaTeX lessons against one exact term template."""

    canonical_template = canonical_math_template(template)
    roles = _template_roles(canonical_template)

    def validate(rows: Sequence[Mapping[str, Any]], label: str) -> list[dict[str, Any]]:
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
            _fail("invalid-lesson", f"{label} must be a nonempty list")
        normalized: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping) or set(row) != {"english", "latex", "bindings"}:
                _fail("invalid-lesson", f"{label}[{index}] has invalid keys")
            english = row["english"]
            latex = row["latex"]
            bindings = row["bindings"]
            if (
                not isinstance(english, str)
                or not english.strip()
                or not isinstance(latex, str)
                or not latex.strip()
                or not isinstance(bindings, Mapping)
            ):
                _fail("invalid-lesson", f"{label}[{index}] is malformed")
            supplied = {str(name): value for name, value in bindings.items()}
            if set(supplied) != set(roles):
                _fail("invalid-lesson", f"{label}[{index}] has wrong role coverage")
            parsed_english = parse_english(english)
            parsed_latex = parse_latex(latex)
            if parsed_english != parsed_latex:
                _fail("invalid-lesson", f"{label}[{index}] surfaces disagree")
            instantiated = instantiate_math_template(canonical_template, supplied)
            if instantiated != parsed_latex:
                _fail("invalid-lesson", f"{label}[{index}] violates its template")
            normalized.append(
                {
                    "english": " ".join(english.split()),
                    "latex": latex.strip(),
                    "bindings": {
                        name: str(supplied[name]) for name in sorted(supplied)
                    },
                }
            )
        return normalized

    return {
        "schema": MATH_LANGUAGE_SCHEMA,
        "term_template": canonical_template,
        "examples": validate(examples, "examples"),
        "holdout": validate(holdout, "holdout") if holdout else [],
    }


def _variables(term: Mapping[str, Any]) -> set[str]:
    node = canonical_math_term(term)
    if node["kind"] == "variable":
        return {str(node["name"])}
    if node["kind"] == "constructor":
        result: set[str] = set()
        for child in node["args"]:
            result.update(_variables(child))
        return result
    return set()


__all__ = [
    "MATH_LANGUAGE_SCHEMA",
    "MATH_SOLUTION_SCHEMA",
    "MathLanguageError",
    "canonical_math_term",
    "canonical_math_template",
    "instantiate_math_template",
    "match_math_template",
    "validate_math_lessons",
    "integer_term",
    "variable_term",
    "parse_latex",
    "parse_english",
    "render_latex",
    "render_english",
    "evaluate",
    "solve_linear_equation",
    "solve_linear_inequality",
]
