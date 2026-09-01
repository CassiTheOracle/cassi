from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from enum import IntEnum
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

import torch

from cassi_field_language import CassiQiTextEngine
from cassi_persistent_provider import _load_phi_config
from cassi_phi_harmonic_language import (
    PhiHarmonicLanguageController,
    PhiHarmonicTextEngine,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldError, QiFieldState


ROOT = Path(__file__).resolve().parent
CORPUS_ARTIFACT = ROOT / "artifacts" / "cassi-qi-corpus-language"
PHI_ARTIFACT = ROOT / "artifacts" / "cassi-phi-harmonic-language"
REGIMES = ("natural", "ascii_upper", "suffix4", "reverse_words")
TOKEN_CAPACITY = 3
EVIDENCE_NAMES = (
    "support",
    "position_accuracy",
    "edit_similarity",
    "exact_rate",
    "outcome_error",
    "complexity",
    "activation",
    "score",
    "eligible",
)
ROW_WIDTH = 3 + TOKEN_CAPACITY + len(EVIDENCE_NAMES)
STATE_MAGIC = b"CASSI-TEXT-ABSTRACTION-1\0"


class TextToken(IntEnum):
    PROMPT = 1
    ASCII_UPPER = 2
    ASCII_LOWER = 3
    ASCII_SWAPCASE = 4
    REVERSE_BYTES = 5
    REVERSE_WORDS = 6
    SUFFIX_1 = 7
    SUFFIX_2 = 8
    SUFFIX_4 = 9
    SUFFIX_8 = 10
    FIT = 11
    REPEAT_TO_LENGTH = 12


_IDEMPOTENT = {TextToken.ASCII_UPPER, TextToken.ASCII_LOWER}
_INVOLUTIONS = {
    TextToken.ASCII_SWAPCASE,
    TextToken.REVERSE_BYTES,
    TextToken.REVERSE_WORDS,
}
_SUFFIX_WIDTH = {
    TextToken.SUFFIX_1: 1,
    TextToken.SUFFIX_2: 2,
    TextToken.SUFFIX_4: 4,
    TextToken.SUFFIX_8: 8,
}
_ASCII_UPPER = bytes.maketrans(
    bytes(range(256)),
    bytes(value - 32 if 97 <= value <= 122 else value for value in range(256)),
)
_ASCII_LOWER = bytes.maketrans(
    bytes(range(256)),
    bytes(value + 32 if 65 <= value <= 90 else value for value in range(256)),
)
_ASCII_SWAPCASE = bytes.maketrans(
    bytes(range(256)),
    bytes(
        value - 32
        if 97 <= value <= 122
        else value + 32
        if 65 <= value <= 90
        else value
        for value in range(256)
    ),
)


def _canonical_tokens(tokens: Sequence[TextToken]) -> tuple[TextToken, ...]:
    result: list[TextToken] = []
    for token in tokens:
        if token in _IDEMPOTENT and result and result[-1] == token:
            continue
        if token in _INVOLUTIONS and result and result[-1] == token:
            result.pop()
            continue
        result.append(token)
    return tuple(result)


@dataclass(frozen=True)
class TextProgram:
    tokens: tuple[TextToken, ...]

    def __post_init__(self) -> None:
        try:
            tokens = tuple(TextToken(int(token)) for token in self.tokens)
        except (TypeError, ValueError) as error:
            raise QiFieldError("text program contains an unsupported token") from error
        tokens = _canonical_tokens(tokens)
        if len(tokens) < 2 or len(tokens) > TOKEN_CAPACITY:
            raise QiFieldError("text program length is outside field capacity")
        if tokens[0] != TextToken.PROMPT:
            raise QiFieldError("text program must begin with PROMPT")
        if tokens[-1] not in {TextToken.FIT, TextToken.REPEAT_TO_LENGTH}:
            raise QiFieldError("text program must end in a span emitter")
        if any(
            token in {TextToken.PROMPT, TextToken.FIT, TextToken.REPEAT_TO_LENGTH}
            for token in tokens[1:-1]
        ):
            raise QiFieldError("text program has an invalid typed transform stack")
        object.__setattr__(self, "tokens", tokens)

    @property
    def decoded(self) -> tuple[str, ...]:
        return tuple(token.name for token in self.tokens)

    @property
    def sha256(self) -> str:
        payload = bytes(int(token) for token in self.tokens)
        return hashlib.sha256(payload).hexdigest()

    @property
    def complexity(self) -> float:
        return len(self.tokens) / TOKEN_CAPACITY


def generate_text_programs() -> tuple[TextProgram, ...]:
    candidates: list[tuple[TextToken, ...]] = [
        (TextToken.PROMPT, TextToken.FIT)
    ]
    candidates.extend(
        (TextToken.PROMPT, transform, TextToken.FIT)
        for transform in (
            TextToken.ASCII_UPPER,
            TextToken.ASCII_LOWER,
            TextToken.ASCII_SWAPCASE,
            TextToken.REVERSE_BYTES,
            TextToken.REVERSE_WORDS,
        )
    )
    candidates.extend(
        (TextToken.PROMPT, suffix, TextToken.REPEAT_TO_LENGTH)
        for suffix in _SUFFIX_WIDTH
    )
    unique: dict[str, TextProgram] = {}
    for tokens in candidates:
        program = TextProgram(tokens)
        unique.setdefault(program.sha256, program)
    return tuple(unique.values())


def _fit(span: bytes, length: int) -> bytes:
    if length <= 0 or not span:
        return b""
    if len(span) >= length:
        return span[-length:]
    return span + b" " * (length - len(span))


def _repeat(span: bytes, length: int) -> bytes:
    if length <= 0 or not span:
        return b""
    return (span * math.ceil(length / len(span)))[:length]


def evaluate_text_program(program: TextProgram, prompt: bytes, length: int) -> bytes:
    value = b""
    for token in program.tokens:
        if token == TextToken.PROMPT:
            value = prompt
        elif token == TextToken.ASCII_UPPER:
            value = value.translate(_ASCII_UPPER)
        elif token == TextToken.ASCII_LOWER:
            value = value.translate(_ASCII_LOWER)
        elif token == TextToken.ASCII_SWAPCASE:
            value = value.translate(_ASCII_SWAPCASE)
        elif token == TextToken.REVERSE_BYTES:
            value = value[::-1]
        elif token == TextToken.REVERSE_WORDS:
            value = b" ".join(reversed(value.split(b" ")))
        elif token in _SUFFIX_WIDTH:
            value = value[-_SUFFIX_WIDTH[token] :]
        elif token == TextToken.FIT:
            value = _fit(value, length)
        elif token == TextToken.REPEAT_TO_LENGTH:
            value = _repeat(value, length)
        else:
            raise QiFieldError("text program reached an unsupported token")
    if len(value) != length:
        raise QiFieldError("text program did not emit the requested span length")
    return value


@dataclass(frozen=True)
class TextEpisode:
    source_id: str
    prompt: bytes
    continuation: bytes
    payload_sha256: str


SYMBOLIC_REGIMES = (
    "natural",
    "entity_swap",
    "predicate_rebind",
    "discourse_reverse",
)
SYMBOLIC_STATE_MAGIC = b"CASSI-TEXT-ROLE-ABSTRACTION-1\0"
_SURFACE_SYMBOL_PATTERN = re.compile(r"\s+|\w+(?:[’']\w+)*|[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class SurfaceSymbol:
    kind: Literal["word", "space", "punctuation"]
    surface: str


def _surface_symbols(value: bytes) -> tuple[SurfaceSymbol, ...]:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise QiFieldError("symbol abstraction requires valid UTF-8") from error
    pieces = tuple(match.group(0) for match in _SURFACE_SYMBOL_PATTERN.finditer(text))
    if "".join(pieces) != text:
        raise QiFieldError("symbol abstraction tokenizer did not preserve the byte span")
    return tuple(
        SurfaceSymbol(
            "space"
            if piece.isspace()
            else "word"
            if piece[0].isalnum() or piece[0] == "_"
            else "punctuation",
            piece,
        )
        for piece in pieces
    )


class RoleToken(IntEnum):
    ENTITY_A = 1
    PREDICATE_A = 2
    ENTITY_B = 3
    ENTITY_C = 4
    PREDICATE_B = 5
    ENTITY_D = 6
    BECAUSE = 7
    THEN = 8
    PERIOD = 9


_ROLE_ENTITY_TOKENS = {
    RoleToken.ENTITY_A,
    RoleToken.ENTITY_B,
    RoleToken.ENTITY_C,
    RoleToken.ENTITY_D,
}
_ROLE_PREDICATE_TOKENS = {
    RoleToken.PREDICATE_A,
    RoleToken.PREDICATE_B,
}
_ROLE_CONNECTOR_TOKENS = {
    RoleToken.BECAUSE,
    RoleToken.THEN,
}
_ROLE_BINDING_ORDER = (
    RoleToken.ENTITY_A,
    RoleToken.PREDICATE_A,
    RoleToken.ENTITY_B,
    RoleToken.ENTITY_C,
    RoleToken.PREDICATE_B,
    RoleToken.ENTITY_D,
)


@dataclass(frozen=True)
class RoleProgram:
    tokens: tuple[RoleToken, ...]

    def __post_init__(self) -> None:
        try:
            tokens = tuple(RoleToken(int(token)) for token in self.tokens)
        except (TypeError, ValueError) as error:
            raise QiFieldError("role program contains an unsupported token") from error
        body = tokens[:-1]
        valid_clause = (
            len(body) == 3
            and body[0] in _ROLE_ENTITY_TOKENS
            and body[1] in _ROLE_PREDICATE_TOKENS
            and body[2] in _ROLE_ENTITY_TOKENS
        )
        valid_discourse = (
            len(body) == 7
            and body[0] in _ROLE_ENTITY_TOKENS
            and body[1] in _ROLE_PREDICATE_TOKENS
            and body[2] in _ROLE_ENTITY_TOKENS
            and body[3] in _ROLE_CONNECTOR_TOKENS
            and body[4] in _ROLE_ENTITY_TOKENS
            and body[5] in _ROLE_PREDICATE_TOKENS
            and body[6] in _ROLE_ENTITY_TOKENS
        )
        if (
            not tokens
            or tokens[-1] != RoleToken.PERIOD
            or not (valid_clause or valid_discourse)
        ):
            raise QiFieldError("role program violates the typed clause grammar")
        object.__setattr__(self, "tokens", tokens)

    @property
    def decoded(self) -> tuple[str, ...]:
        return tuple(token.name for token in self.tokens)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(bytes(int(token) for token in self.tokens)).hexdigest()

    @property
    def complexity(self) -> float:
        return len(self.tokens) / 8.0


def generate_role_programs() -> tuple[RoleProgram, ...]:
    clause_tokens = tuple(
        (*entities, RoleToken.PERIOD)
        for entities in (
            (RoleToken.ENTITY_A, RoleToken.PREDICATE_A, RoleToken.ENTITY_B),
            (RoleToken.ENTITY_B, RoleToken.PREDICATE_A, RoleToken.ENTITY_A),
            (RoleToken.ENTITY_A, RoleToken.PREDICATE_B, RoleToken.ENTITY_B),
            (RoleToken.ENTITY_B, RoleToken.PREDICATE_B, RoleToken.ENTITY_A),
            (RoleToken.ENTITY_C, RoleToken.PREDICATE_A, RoleToken.ENTITY_D),
            (RoleToken.ENTITY_D, RoleToken.PREDICATE_A, RoleToken.ENTITY_C),
            (RoleToken.ENTITY_C, RoleToken.PREDICATE_B, RoleToken.ENTITY_D),
            (RoleToken.ENTITY_D, RoleToken.PREDICATE_B, RoleToken.ENTITY_C),
        )
    )
    clause_a = (
        RoleToken.ENTITY_A,
        RoleToken.PREDICATE_A,
        RoleToken.ENTITY_B,
    )
    clause_b = (
        RoleToken.ENTITY_C,
        RoleToken.PREDICATE_B,
        RoleToken.ENTITY_D,
    )
    discourse_tokens = tuple(
        (*first, connector, *second, RoleToken.PERIOD)
        for first, second in ((clause_a, clause_b), (clause_b, clause_a))
        for connector in _ROLE_CONNECTOR_TOKENS
    )
    return tuple(RoleProgram(tokens) for tokens in (*clause_tokens, *discourse_tokens))


def _role_bindings(prompt: bytes) -> dict[RoleToken, str] | None:
    words = [
        symbol.surface
        for symbol in _surface_symbols(prompt)
        if symbol.kind == "word"
    ]
    if not words:
        return None
    selected = (
        words[-6:]
        if len(words) >= 6
        else [words[index % len(words)] for index in range(6)]
    )
    return dict(zip(_ROLE_BINDING_ORDER, selected, strict=True))


def evaluate_role_program(
    program: RoleProgram,
    prompt: bytes,
    _target_length: int,
) -> bytes:
    bindings = _role_bindings(prompt)
    if bindings is None:
        return b""
    surfaces = []
    for token in program.tokens[:-1]:
        if token in bindings:
            surfaces.append(bindings[token])
        elif token == RoleToken.BECAUSE:
            surfaces.append("because")
        elif token == RoleToken.THEN:
            surfaces.append("then")
        else:
            raise QiFieldError("role program reached an unsupported emitter")
    return (" ".join(surfaces) + ".").encode("utf-8")


_ROLE_CONTROL_TOKENS = {
    "entity_swap": (
        RoleToken.ENTITY_B,
        RoleToken.PREDICATE_A,
        RoleToken.ENTITY_A,
        RoleToken.PERIOD,
    ),
    "predicate_rebind": (
        RoleToken.ENTITY_A,
        RoleToken.PREDICATE_B,
        RoleToken.ENTITY_B,
        RoleToken.PERIOD,
    ),
    "discourse_reverse": (
        RoleToken.ENTITY_C,
        RoleToken.PREDICATE_B,
        RoleToken.ENTITY_D,
        RoleToken.BECAUSE,
        RoleToken.ENTITY_A,
        RoleToken.PREDICATE_A,
        RoleToken.ENTITY_B,
        RoleToken.PERIOD,
    ),
}


def _role_control_programs(
    programs: Sequence[RoleProgram],
) -> dict[str, RoleProgram]:
    by_tokens = {program.tokens: program for program in programs}
    return {
        regime: by_tokens[tokens]
        for regime, tokens in _ROLE_CONTROL_TOKENS.items()
    }


def _role_examples_by_regime(
    episodes: Sequence[TextEpisode],
    programs: Sequence[RoleProgram],
    *,
    rename_seed: str | None = None,
) -> dict[str, tuple[tuple[bytes, bytes], ...]]:
    controls = _role_control_programs(programs)
    prompts = tuple(
        episode.prompt
        if rename_seed is None
        else _rename_prompt_symbols(episode.prompt, f"{rename_seed}{index}")
        for index, episode in enumerate(episodes)
    )
    result = {
        "natural": tuple(
            (prompt, episode.continuation)
            for prompt, episode in zip(prompts, episodes, strict=True)
        )
    }
    for regime, program in controls.items():
        result[regime] = tuple(
            (prompt, evaluate_role_program(program, prompt, 0))
            for prompt in prompts
        )
    return result


def _rename_prompt_symbols(prompt: bytes, seed: str) -> bytes:
    symbols = _surface_symbols(prompt)
    replacements: dict[str, str] = {}
    renamed = []
    for symbol in symbols:
        if symbol.kind != "word":
            renamed.append(symbol.surface)
            continue
        replacement = replacements.setdefault(
            symbol.surface,
            f"{seed}x{len(replacements)}",
        )
        renamed.append(replacement)
    return "".join(renamed).encode("utf-8")


@dataclass(frozen=True)
class TextEvidence:
    support: int
    position_accuracy: float
    edit_similarity: float
    exact_rate: float
    outcome_error: float
    complexity: float
    activation: float
    score: float
    eligible: bool


@dataclass(frozen=True)
class TextProgramRecord:
    regime: str
    program_id: int
    program: Any
    evidence: TextEvidence


@dataclass(frozen=True)
class TextSelection:
    status: Literal["selected", "ambiguous", "exhausted"]
    regime: str
    program_id: int | None
    program_sha256: str | None
    tokens: tuple[str, ...]
    equivalent_program_ids: tuple[int, ...]
    score: float | None
    margin: float | None


class TextAbstractionController:
    def __init__(
        self,
        *,
        programs: Sequence[Any] | None = None,
        regimes: Sequence[str] = REGIMES,
        evaluator: Callable[[Any, bytes, int], bytes] = evaluate_text_program,
        state_magic: bytes = STATE_MAGIC,
        grammar_id: str = "byte-span-v1",
        breaths: int = 4,
        max_outcome_error: float = 0.05,
        selection_margin: float = 0.01,
    ) -> None:
        configured_programs = (
            generate_text_programs() if programs is None else tuple(programs)
        )
        configured_regimes = tuple(regimes)
        if (
            breaths < 1
            or not 0.0 <= max_outcome_error <= 1.0
            or not configured_programs
            or not configured_regimes
            or len(set(configured_regimes)) != len(configured_regimes)
            or not isinstance(state_magic, bytes)
            or not state_magic
        ):
            raise QiFieldError("text abstraction configuration is invalid")
        self.programs = configured_programs
        self.regimes = configured_regimes
        self.evaluate = evaluator
        self.state_magic = state_magic
        self.token_capacity = max(len(program.tokens) for program in self.programs)
        self.row_width = 3 + self.token_capacity + len(EVIDENCE_NAMES)
        self.breaths = breaths
        self.max_outcome_error = max_outcome_error
        self.selection_margin = selection_margin
        self.mode_count = math.ceil(
            len(self.regimes) * len(self.programs) * self.row_width / 9
        )
        self.shape = (1, 9 * self.mode_count, 1)
        grammar = {
            "grammar_id": grammar_id,
            "programs": [list(program.decoded) for program in self.programs],
            "regimes": list(self.regimes),
            "row_width": self.row_width,
        }
        self.grammar_sha256 = hashlib.sha256(
            json.dumps(grammar, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def new_state(self) -> QiFieldState:
        return QiFieldState(field=torch.zeros(self.shape, dtype=torch.float64))

    def _row_offset(self, regime_id: int, program_id: int) -> int:
        return (regime_id * len(self.programs) + program_id) * self.row_width

    def _row(
        self,
        state: QiFieldState,
        regime_id: int,
        program_id: int,
    ) -> torch.Tensor:
        offset = self._row_offset(regime_id, program_id)
        return state.field.reshape(-1)[offset : offset + self.row_width]

    def validate_state(self, state: QiFieldState) -> None:
        if (
            not isinstance(state, QiFieldState)
            or state.field.shape != self.shape
            or state.field.dtype != torch.float64
            or not bool(torch.isfinite(state.field).all().item())
        ):
            raise QiFieldError("text abstraction field is invalid")
        for regime_id in range(len(self.regimes)):
            for program_id, expected in enumerate(self.programs):
                row = self._row(state, regime_id, program_id)
                if not bool(torch.any(row != 0.0).item()):
                    continue
                if (
                    int(round(float(row[0].item()))) != program_id + 1
                    or int(round(float(row[1].item()))) != regime_id + 1
                ):
                    raise QiFieldError("text abstraction field row identity is invalid")
                token_count = int(round(float(row[2].item())))
                if not 1 <= token_count <= self.token_capacity:
                    raise QiFieldError("text abstraction field token count is invalid")
                tokens = tuple(
                    int(round(float(row[3 + index].item())))
                    for index in range(token_count)
                )
                if tokens != tuple(int(token) for token in expected.tokens):
                    raise QiFieldError("text abstraction field program tokens changed")
                metrics = row[3 + self.token_capacity :]
                if (
                    metrics[0].item() < 1.0
                    or any(
                        not 0.0 <= float(metrics[index].item()) <= 1.0
                        for index in (1, 2, 3, 4, 5, 6, 8)
                    )
                    or metrics[7].item() < 0.0
                ):
                    raise QiFieldError("text abstraction field evidence is invalid")
        used = len(self.regimes) * len(self.programs) * self.row_width
        if bool(torch.any(state.field.reshape(-1)[used:] != 0.0).item()):
            raise QiFieldError("text abstraction field padding changed")

    @staticmethod
    def state_sha256(state: QiFieldState) -> str:
        return hashlib.sha256(
            state.field.detach().cpu().contiguous().numpy().tobytes()
        ).hexdigest()

    @staticmethod
    def _position_accuracy(predicted: bytes, observed: bytes) -> float:
        if not observed:
            return float(not predicted)
        return sum(
            index < len(predicted) and predicted[index] == value
            for index, value in enumerate(observed)
        ) / len(observed)

    def _base_evidence(
        self,
        program: Any,
        examples: Sequence[tuple[bytes, bytes]],
    ) -> TextEvidence:
        predictions = [
            self.evaluate(program, prompt, len(target))
            for prompt, target in examples
        ]
        position_accuracy = sum(
            self._position_accuracy(predicted, target)
            for predicted, (_, target) in zip(predictions, examples, strict=True)
        ) / len(examples)
        edit_similarity = sum(
            SequenceMatcher(None, predicted, target, autojunk=False).ratio()
            for predicted, (_, target) in zip(predictions, examples, strict=True)
        ) / len(examples)
        exact_rate = sum(
            predicted == target
            for predicted, (_, target) in zip(predictions, examples, strict=True)
        ) / len(examples)
        outcome_error = 1.0 - exact_rate
        score = (
            (1.0 - position_accuracy)
            + (1.0 - edit_similarity)
            + 8.0 * outcome_error
            + 0.01 * program.complexity
        )
        return TextEvidence(
            support=len(examples),
            position_accuracy=position_accuracy,
            edit_similarity=edit_similarity,
            exact_rate=exact_rate,
            outcome_error=outcome_error,
            complexity=program.complexity,
            activation=0.0,
            score=score,
            eligible=outcome_error <= self.max_outcome_error,
        )

    def _refine(self, evidence: Sequence[TextEvidence]) -> tuple[TextEvidence, ...]:
        activation = torch.full(
            (len(evidence),),
            1.0 / len(evidence),
            dtype=torch.float64,
        )
        upward = torch.tensor(
            [item.position_accuracy + item.edit_similarity for item in evidence],
            dtype=torch.float64,
        )
        downward = torch.tensor(
            [8.0 * item.exact_rate - item.complexity for item in evidence],
            dtype=torch.float64,
        )
        for breath in range(self.breaths):
            evidence_logit = upward if breath % 2 == 0 else downward
            activation = torch.softmax(
                torch.log(activation.clamp_min(torch.finfo(torch.float64).tiny))
                + evidence_logit,
                dim=0,
            )
        return tuple(
            TextEvidence(
                **{
                    **asdict(item),
                    "activation": float(activation[index].item()),
                    "score": item.score,
                }
            )
            for index, item in enumerate(evidence)
        )

    def synthesize(
        self,
        examples_by_regime: Mapping[str, Sequence[tuple[bytes, bytes]]],
    ) -> QiFieldState:
        if set(examples_by_regime) != set(self.regimes):
            raise QiFieldError("text abstraction corpus regimes are incomplete")
        result = self.new_state()
        for regime_id, regime in enumerate(self.regimes):
            examples = tuple(examples_by_regime[regime])
            if not examples or any(not prompt or not target for prompt, target in examples):
                raise QiFieldError("text abstraction examples must contain byte spans")
            evidence = self._refine(
                [self._base_evidence(program, examples) for program in self.programs]
            )
            for program_id, (program, metrics) in enumerate(
                zip(self.programs, evidence, strict=True)
            ):
                row = torch.zeros(self.row_width, dtype=torch.float64)
                row[0] = program_id + 1
                row[1] = regime_id + 1
                row[2] = len(program.tokens)
                row[3 : 3 + len(program.tokens)] = torch.tensor(
                    [int(token) for token in program.tokens],
                    dtype=torch.float64,
                )
                row[3 + self.token_capacity :] = torch.tensor(
                    [
                        metrics.support,
                        metrics.position_accuracy,
                        metrics.edit_similarity,
                        metrics.exact_rate,
                        metrics.outcome_error,
                        metrics.complexity,
                        metrics.activation,
                        metrics.score,
                        float(metrics.eligible),
                    ],
                    dtype=torch.float64,
                )
                self._row(result, regime_id, program_id).copy_(row)
        self.validate_state(result)
        return result

    def records(self, state: QiFieldState, regime: str) -> tuple[TextProgramRecord, ...]:
        self.validate_state(state)
        if regime not in self.regimes:
            raise QiFieldError("text abstraction regime is unsupported")
        regime_id = self.regimes.index(regime)
        records = []
        for program_id in range(len(self.programs)):
            row = self._row(state, regime_id, program_id)
            if not bool(torch.any(row != 0.0).item()):
                continue
            token_count = int(round(float(row[2].item())))
            program = self.programs[program_id]
            tokens = tuple(
                int(round(float(row[3 + index].item())))
                for index in range(token_count)
            )
            if tokens != tuple(int(token) for token in program.tokens):
                raise QiFieldError("text abstraction field program tokens changed")
            values = [
                float(value.item()) for value in row[3 + self.token_capacity :]
            ]
            records.append(
                TextProgramRecord(
                    regime=regime,
                    program_id=program_id,
                    program=program,
                    evidence=TextEvidence(
                        support=int(round(values[0])),
                        position_accuracy=values[1],
                        edit_similarity=values[2],
                        exact_rate=values[3],
                        outcome_error=values[4],
                        complexity=values[5],
                        activation=values[6],
                        score=values[7],
                        eligible=bool(round(values[8])),
                    ),
                )
            )
        return tuple(records)

    def select(self, state: QiFieldState, regime: str) -> TextSelection:
        candidates = [
            record
            for record in self.records(state, regime)
            if record.evidence.eligible
            and record.evidence.outcome_error <= self.max_outcome_error
        ]
        if not candidates:
            return TextSelection("exhausted", regime, None, None, (), (), None, None)
        ranked = sorted(
            candidates,
            key=lambda record: (
                record.evidence.score,
                -record.evidence.activation,
                record.program.sha256,
            ),
        )
        best = ranked[0]
        equivalent = tuple(
            record.program_id
            for record in ranked
            if record.evidence.score - best.evidence.score <= self.selection_margin
        )
        margin = (
            None
            if len(ranked) == 1
            else ranked[1].evidence.score - best.evidence.score
        )
        if len(equivalent) > 1:
            return TextSelection(
                "ambiguous",
                regime,
                None,
                None,
                (),
                equivalent,
                best.evidence.score,
                margin,
            )
        return TextSelection(
            "selected",
            regime,
            best.program_id,
            best.program.sha256,
            best.program.decoded,
            equivalent,
            best.evidence.score,
            margin,
        )

    def selected_program(self, state: QiFieldState, regime: str) -> Any | None:
        selection = self.select(state, regime)
        if selection.program_id is None:
            return None
        return next(
            record.program
            for record in self.records(state, regime)
            if record.program_id == selection.program_id
        )

    def clear_program(
        self,
        state: QiFieldState,
        regime: str,
        program_id: int,
    ) -> QiFieldState:
        self.validate_state(state)
        if regime not in self.regimes or not 0 <= program_id < len(self.programs):
            raise QiFieldError("text abstraction ablation target is invalid")
        result = QiFieldState(field=state.field.clone())
        self._row(result, self.regimes.index(regime), program_id).zero_()
        self.validate_state(result)
        return result

    def dump_state_bytes(self, state: QiFieldState) -> bytes:
        self.validate_state(state)
        body = state.field.detach().cpu().contiguous().numpy().tobytes()
        return (
            self.state_magic
            + bytes.fromhex(self.grammar_sha256)
            + hashlib.sha256(body).digest()
            + body
        )

    def load_state_bytes(self, payload: bytes) -> QiFieldState:
        header = len(self.state_magic) + 64
        expected_body = math.prod(self.shape) * 8
        if (
            not isinstance(payload, bytes)
            or len(payload) != header + expected_body
            or not payload.startswith(self.state_magic)
            or payload[len(self.state_magic) : len(self.state_magic) + 32]
            != bytes.fromhex(self.grammar_sha256)
        ):
            raise QiFieldError("text abstraction state frame is incompatible")
        digest_start = len(self.state_magic) + 32
        body = payload[header:]
        if hashlib.sha256(body).digest() != payload[digest_start:header]:
            raise QiFieldError("text abstraction state checksum mismatch")
        field = torch.frombuffer(bytearray(body), dtype=torch.float64).clone().reshape(
            self.shape
        )
        result = QiFieldState(field=field)
        self.validate_state(result)
        return result


def _load_episode(
    descriptor: Mapping[str, Any],
    source_paths: Mapping[str, Path],
) -> TextEpisode:
    source_id = str(descriptor["source_id"])
    try:
        path = source_paths[source_id]
    except KeyError as error:
        raise QiFieldError(f"corpus source is unavailable: {source_id}") from error
    length = int(descriptor["length"])
    prompt_bytes = int(descriptor["prompt_bytes"])
    continuation_bytes = int(descriptor["continuation_bytes"])
    with path.open("rb") as handle:
        handle.seek(int(descriptor["offset"]))
        payload = handle.read(length)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != descriptor["payload_sha256"]:
        raise QiFieldError(f"corpus payload changed at {path}:{descriptor['offset']}")
    if (
        len(payload) != length
        or prompt_bytes + continuation_bytes != length
        or not 1 <= prompt_bytes < length
    ):
        raise QiFieldError("corpus episode byte counts changed")
    return TextEpisode(
        source_id=source_id,
        prompt=payload[:prompt_bytes],
        continuation=payload[prompt_bytes:],
        payload_sha256=digest,
    )


def _control_programs(programs: Sequence[TextProgram]) -> dict[str, TextProgram]:
    expected = {
        "ascii_upper": (TextToken.PROMPT, TextToken.ASCII_UPPER, TextToken.FIT),
        "suffix4": (TextToken.PROMPT, TextToken.SUFFIX_4, TextToken.REPEAT_TO_LENGTH),
        "reverse_words": (
            TextToken.PROMPT,
            TextToken.REVERSE_WORDS,
            TextToken.FIT,
        ),
    }
    by_tokens = {program.tokens: program for program in programs}
    return {name: by_tokens[tokens] for name, tokens in expected.items()}


def _examples_by_regime(
    episodes: Sequence[TextEpisode],
    programs: Sequence[TextProgram],
) -> dict[str, tuple[tuple[bytes, bytes], ...]]:
    controls = _control_programs(programs)
    result: dict[str, tuple[tuple[bytes, bytes], ...]] = {
        "natural": tuple(
            (episode.prompt, episode.continuation) for episode in episodes
        )
    }
    for regime, program in controls.items():
        result[regime] = tuple(
            (
                episode.prompt,
                evaluate_text_program(
                    program,
                    episode.prompt,
                    len(episode.continuation),
                ),
            )
            for episode in episodes
        )
    return result


def _span_metrics(
    episodes: Sequence[TextEpisode],
    outputs: Sequence[bytes],
    *,
    targets: Sequence[bytes] | None = None,
) -> dict[str, Any]:
    observed = (
        tuple(episode.continuation for episode in episodes)
        if targets is None
        else tuple(targets)
    )
    if len(outputs) != len(observed):
        raise QiFieldError("text comparison output count changed")
    total_bytes = sum(len(target) for target in observed)
    matched = sum(
        sum(
            index < len(output) and output[index] == value
            for index, value in enumerate(target)
        )
        for output, target in zip(outputs, observed, strict=True)
    )
    exact = sum(
        output == target
        for output, target in zip(outputs, observed, strict=True)
    )
    edit_similarity = sum(
        SequenceMatcher(None, output, target, autojunk=False).ratio()
        for output, target in zip(outputs, observed, strict=True)
    ) / len(observed)
    return {
        "episode_count": len(observed),
        "exact_continuations": exact,
        "exact_rate": exact / len(observed),
        "position_byte_accuracy": matched / total_bytes,
        "mean_edit_similarity": edit_similarity,
        "abstentions": sum(not output for output in outputs),
        "false_settlements": sum(
            bool(output) and output != target
            for output, target in zip(outputs, observed, strict=True)
        ),
        "mean_output_bytes": sum(len(output) for output in outputs) / len(outputs),
    }


def _baseline_outputs(
    episodes: Sequence[TextEpisode],
) -> tuple[list[bytes], dict[str, Any]]:
    config = QiFieldConfig.from_dict(
        json.loads((ROOT / "configs" / "cassi-qi-corpus-language.json").read_text())
    )
    controller = QiFieldController(config)
    engine = CassiQiTextEngine(
        controller,
        checkpoint_path=CORPUS_ARTIFACT / "field-state.pt",
        max_output_symbols=96,
    )
    state = engine.initial_state()
    memory_before = engine.law.memory_sha256(state)
    outputs = []
    stop_reasons: dict[str, int] = {}
    for episode in episodes:
        result = engine.generate(
            state,
            [{"role": "user", "content": episode.prompt.decode("utf-8")}],
            max_output_symbols=len(episode.continuation),
        )
        outputs.append(result.output_bytes)
        stop_reasons[result.stop_reason] = stop_reasons.get(result.stop_reason, 0) + 1
        if result.corpus_memory_sha256 != memory_before:
            raise QiFieldError("baseline generation changed trained corpus memory")
    return outputs, {
        "checkpoint_sha256": engine.checkpoint_sha256,
        "corpus_memory_sha256": memory_before,
        "stop_reasons": stop_reasons,
    }


def _phi_outputs(
    episodes: Sequence[TextEpisode],
) -> tuple[list[bytes], dict[str, Any]]:
    controller = PhiHarmonicLanguageController(
        _load_phi_config(ROOT / "configs" / "cassi-phi-harmonic-language.json")
    )
    state_bytes = (PHI_ARTIFACT / "field-state.pt").read_bytes()
    state = controller.load_state_bytes(state_bytes)
    tape_before = controller.tape_sha256(state)
    engine = PhiHarmonicTextEngine(controller, max_output_symbols=96)
    outputs = []
    stop_reasons: dict[str, int] = {}
    for episode in episodes:
        try:
            result = engine.generate(
                state,
                [{"role": "user", "content": episode.prompt.decode("utf-8")}],
                max_output_symbols=len(episode.continuation),
            )
        except QiFieldError as error:
            if str(error) != "live field has no learned trajectory continuation":
                raise
            outputs.append(b"")
            stop_reasons["field_abstained"] = (
                stop_reasons.get("field_abstained", 0) + 1
            )
            continue
        outputs.append(
            bytes(symbol for symbol in result.output_symbols if 0 <= symbol < 256)
        )
        stop_reasons[result.stop_reason] = stop_reasons.get(result.stop_reason, 0) + 1
        if result.tape_sha256 != tape_before:
            raise QiFieldError("Phi generation changed its learned trajectory tape")
    return outputs, {
        "checkpoint_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "tape_sha256": tape_before,
        "stop_reasons": stop_reasons,
    }


def _selection_dict(selection: TextSelection) -> dict[str, Any]:
    return {
        "status": selection.status,
        "program_id": selection.program_id,
        "program_sha256": selection.program_sha256,
        "tokens": list(selection.tokens),
        "equivalent_program_ids": list(selection.equivalent_program_ids),
        "score": selection.score,
        "margin": selection.margin,
    }


def _preview(value: bytes, limit: int = 72) -> str:
    text = value.decode("utf-8", errors="replace").replace("\n", "\\n")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _target_aware_oracle(
    controller: TextAbstractionController,
    episodes: Sequence[TextEpisode],
) -> tuple[list[bytes], dict[str, int]]:
    outputs = []
    program_counts: dict[str, int] = {}
    for episode in episodes:
        candidates = [
            (
                program,
                controller.evaluate(
                    program,
                    episode.prompt,
                    len(episode.continuation),
                ),
            )
            for program in controller.programs
        ]
        winner, output = min(
            candidates,
            key=lambda candidate: (
                -controller._position_accuracy(
                    candidate[1],
                    episode.continuation,
                ),
                -SequenceMatcher(
                    None,
                    candidate[1],
                    episode.continuation,
                    autojunk=False,
                ).ratio(),
                candidate[0].complexity,
                candidate[0].sha256,
            ),
        )
        label = " ".join(winner.decoded)
        program_counts[label] = program_counts.get(label, 0) + 1
        outputs.append(output)
    return outputs, program_counts


def run_text_abstraction_comparison() -> dict[str, Any]:
    training_receipt = json.loads(
        (CORPUS_ARTIFACT / "training-receipt.json").read_text(encoding="utf-8")
    )
    verification_receipt = json.loads(
        (CORPUS_ARTIFACT / "verification-receipt.json").read_text(encoding="utf-8")
    )
    phi_receipt = json.loads(
        (PHI_ARTIFACT / "training-receipt.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "configs" / "cassi-qi-corpus-first-wave.json").read_text(
            encoding="utf-8"
        )
    )
    source_paths = {
        str(source["id"]): Path(str(source["path"]))
        for source in manifest["sources"]
    }
    experience = training_receipt["experience"]
    training = tuple(
        _load_episode(descriptor, source_paths)
        for descriptor in experience["training_episodes"]
    )
    heldout = tuple(
        _load_episode(descriptor, source_paths)
        for descriptor in experience["heldout_episodes"]
    )
    if [episode.payload_sha256 for episode in training] != [
        descriptor["payload_sha256"]
        for descriptor in phi_receipt["training"]["episodes"]
    ]:
        raise QiFieldError("baseline and Phi checkpoints used different training episodes")

    controller = TextAbstractionController()
    training_examples = _examples_by_regime(training, controller.programs)
    heldout_examples = _examples_by_regime(heldout, controller.programs)
    state = controller.synthesize(training_examples)
    state_sha256 = controller.state_sha256(state)
    selections = {regime: controller.select(state, regime) for regime in REGIMES}

    natural_program = controller.selected_program(state, "natural")
    natural_outputs = [
        b""
        if natural_program is None
        else evaluate_text_program(
            natural_program,
            episode.prompt,
            len(episode.continuation),
        )
        for episode in heldout
    ]

    oracle_outputs, oracle_programs = _target_aware_oracle(controller, heldout)

    role_programs = generate_role_programs()
    role_controller = TextAbstractionController(
        programs=role_programs,
        regimes=SYMBOLIC_REGIMES,
        evaluator=evaluate_role_program,
        state_magic=SYMBOLIC_STATE_MAGIC,
        grammar_id="word-punctuation-role-v1",
    )
    role_training_examples = _role_examples_by_regime(
        training,
        role_programs,
    )
    role_heldout_examples = _role_examples_by_regime(
        heldout,
        role_programs,
    )
    role_state = role_controller.synthesize(role_training_examples)
    role_state_sha256 = role_controller.state_sha256(role_state)
    role_selections = {
        regime: role_controller.select(role_state, regime)
        for regime in SYMBOLIC_REGIMES
    }
    role_natural_program = role_controller.selected_program(role_state, "natural")
    role_natural_outputs = [
        b""
        if role_natural_program is None
        else evaluate_role_program(
            role_natural_program,
            episode.prompt,
            len(episode.continuation),
        )
        for episode in heldout
    ]
    role_oracle_outputs, role_oracle_programs = _target_aware_oracle(
        role_controller,
        heldout,
    )

    role_control_results = {}
    renamed_role_control_results = {}
    renamed_role_examples = _role_examples_by_regime(
        heldout,
        role_programs,
        rename_seed="heldout",
    )
    for regime in SYMBOLIC_REGIMES[1:]:
        selection = role_selections[regime]
        program = role_controller.selected_program(role_state, regime)
        pairs = role_heldout_examples[regime]
        targets = [target for _, target in pairs]
        outputs = [
            b""
            if program is None
            else evaluate_role_program(program, prompt, len(target))
            for prompt, target in pairs
        ]
        role_control_results[regime] = {
            "selection": _selection_dict(selection),
            "heldout": _span_metrics(heldout, outputs, targets=targets),
        }
        renamed_pairs = renamed_role_examples[regime]
        renamed_targets = [target for _, target in renamed_pairs]
        renamed_outputs = [
            b""
            if program is None
            else evaluate_role_program(program, prompt, len(target))
            for prompt, target in renamed_pairs
        ]
        renamed_role_control_results[regime] = _span_metrics(
            heldout,
            renamed_outputs,
            targets=renamed_targets,
        )

    entity_swap = role_selections["entity_swap"]
    if entity_swap.program_id is None:
        raise QiFieldError("positive role abstraction did not select a program")
    role_ablated = role_controller.clear_program(
        role_state,
        "entity_swap",
        entity_swap.program_id,
    )
    role_ablated_selection = role_controller.select(role_ablated, "entity_swap")
    role_shuffled_examples = dict(role_training_examples)
    entity_examples = list(role_training_examples["entity_swap"])
    entity_targets = [target for _, target in entity_examples]
    role_shuffled_examples["entity_swap"] = tuple(
        (prompt, entity_targets[(index + 1) % len(entity_targets)])
        for index, (prompt, _) in enumerate(entity_examples)
    )
    role_shuffled_state = role_controller.synthesize(role_shuffled_examples)
    role_shuffled_selection = role_controller.select(
        role_shuffled_state,
        "entity_swap",
    )

    role_frame = role_controller.dump_state_bytes(role_state)
    role_restarted = role_controller.load_state_bytes(role_frame)
    role_restart_exact = (
        role_frame == role_controller.dump_state_bytes(role_restarted)
    )
    role_inference_before = role_controller.state_sha256(role_restarted)
    role_replayed_selections = {
        regime: role_controller.select(role_restarted, regime)
        for regime in SYMBOLIC_REGIMES
    }
    role_inference_after = role_controller.state_sha256(role_restarted)
    role_natural_records = sorted(
        role_controller.records(role_state, "natural"),
        key=lambda record: record.evidence.score,
    )

    corpus_spans = tuple(
        span
        for episode in (*training, *heldout)
        for span in (episode.prompt, episode.continuation)
    )
    tokenized_spans = tuple(_surface_symbols(span) for span in corpus_spans)
    tokenizer_roundtrip_exact = all(
        "".join(symbol.surface for symbol in symbols).encode("utf-8") == span
        for symbols, span in zip(tokenized_spans, corpus_spans, strict=True)
    )
    symbol_counts = {
        kind: sum(
            symbol.kind == kind
            for symbols in tokenized_spans
            for symbol in symbols
        )
        for kind in ("word", "space", "punctuation")
    }

    baseline_outputs, baseline_state = _baseline_outputs(heldout)
    phi_outputs, phi_state = _phi_outputs(heldout)

    control_results = {}
    for regime in REGIMES[1:]:
        selection = selections[regime]
        program = controller.selected_program(state, regime)
        targets = [target for _, target in heldout_examples[regime]]
        outputs = [
            b""
            if program is None
            else evaluate_text_program(program, episode.prompt, len(target))
            for episode, target in zip(heldout, targets, strict=True)
        ]
        control_results[regime] = {
            "selection": _selection_dict(selection),
            "heldout": _span_metrics(heldout, outputs, targets=targets),
        }

    uppercase = selections["ascii_upper"]
    if uppercase.program_id is None:
        raise QiFieldError("positive text abstraction did not select a program")
    ablated = controller.clear_program(
        state,
        "ascii_upper",
        uppercase.program_id,
    )
    ablated_selection = controller.select(ablated, "ascii_upper")
    shuffled_examples = dict(training_examples)
    uppercase_examples = list(training_examples["ascii_upper"])
    shuffled_targets = [target for _, target in uppercase_examples]
    shuffled_examples["ascii_upper"] = tuple(
        (prompt, shuffled_targets[(index + 1) % len(shuffled_targets)])
        for index, (prompt, _) in enumerate(uppercase_examples)
    )
    shuffled_state = controller.synthesize(shuffled_examples)
    shuffled_selection = controller.select(shuffled_state, "ascii_upper")

    frame = controller.dump_state_bytes(state)
    restarted = controller.load_state_bytes(frame)
    restart_exact = frame == controller.dump_state_bytes(restarted)
    inference_before = controller.state_sha256(restarted)
    replayed_selections = {
        regime: controller.select(restarted, regime) for regime in REGIMES
    }
    inference_after = controller.state_sha256(restarted)

    natural_records = sorted(
        controller.records(state, "natural"),
        key=lambda record: record.evidence.score,
    )
    teacher_metrics = {
        "training_next_event_accuracy": verification_receipt["training"]["accuracy"],
        "heldout_next_event_accuracy": verification_receipt["heldout"]["accuracy"],
    }
    examples = []
    for index, episode in enumerate(heldout[:4]):
        examples.append(
            {
                "source_id": episode.source_id,
                "prompt": _preview(episode.prompt),
                "target": _preview(episode.continuation),
                "trajectory_output": _preview(baseline_outputs[index]),
                "phi_output": _preview(phi_outputs[index]),
                "abstraction_output": _preview(natural_outputs[index]),
                "grammar_oracle_output": _preview(oracle_outputs[index]),
                "role_abstraction_output": _preview(role_natural_outputs[index]),
                "role_grammar_oracle_output": _preview(role_oracle_outputs[index]),
            }
        )

    result = {
        "result": "TEXT_ABSTRACTION_COMPARISON_OK",
        "corpus": {
            "training_episodes": len(training),
            "heldout_episodes": len(heldout),
            "sources": sorted({episode.source_id for episode in training}),
            "max_episode_bytes": training_receipt["experience"]["max_episode_bytes"],
            "identical_training_split_for_phi": True,
        },
        "typed_program_abstraction": {
            "program_count": len(controller.programs),
            "breaths": controller.breaths,
            "grammar_sha256": controller.grammar_sha256,
            "adaptive_persistent_objects": ["QiFieldState.field"],
            "natural_selection": _selection_dict(selections["natural"]),
            "natural_heldout": _span_metrics(heldout, natural_outputs),
            "natural_top_programs": [
                {
                    "tokens": list(record.program.decoded),
                    **asdict(record.evidence),
                }
                for record in natural_records[:3]
            ],
            "grammar_oracle_heldout": _span_metrics(heldout, oracle_outputs),
            "grammar_oracle_programs": oracle_programs,
            "positive_controls": control_results,
            "field_sha256": state_sha256,
        },
        "role_symbol_abstraction": {
            "symbolizer": {
                "schema": "cassi.text-role-symbols.v1",
                "roundtrip_spans": len(corpus_spans),
                "roundtrip_exact": tokenizer_roundtrip_exact,
                "symbol_counts": symbol_counts,
                "role_binding": "last six word symbols as E_A/P_A/E_B/E_C/P_B/E_D",
                "semantic_parser": False,
            },
            "program_count": len(role_programs),
            "breaths": role_controller.breaths,
            "grammar_sha256": role_controller.grammar_sha256,
            "adaptive_persistent_objects": ["QiFieldState.field"],
            "natural_selection": _selection_dict(role_selections["natural"]),
            "natural_heldout": _span_metrics(heldout, role_natural_outputs),
            "natural_top_programs": [
                {
                    "tokens": list(record.program.decoded),
                    **asdict(record.evidence),
                }
                for record in role_natural_records[:3]
            ],
            "grammar_oracle_heldout": _span_metrics(
                heldout,
                role_oracle_outputs,
            ),
            "grammar_oracle_programs": role_oracle_programs,
            "positive_controls": role_control_results,
            "renamed_positive_controls": renamed_role_control_results,
            "field_sha256": role_state_sha256,
            "epistemic_boundary": (
                "entity, predicate, and discourse roles are deterministic "
                "surface-position hypotheses, not inferred semantics"
            ),
        },
        "next_symbol_trajectory_baseline": {
            "recorded_teacher_forced": {
                "training_next_event_accuracy": teacher_metrics["training_next_event_accuracy"],
                "heldout_next_event_accuracy": teacher_metrics["heldout_next_event_accuracy"],
            },
            "heldout_autoregressive": _span_metrics(heldout, baseline_outputs),
            "recorded_training_generation": {
                "example_count": len(verification_receipt["generation"]),
                "exact_continuations": sum(
                    item["actual"] == item["expected"]
                    for item in verification_receipt["generation"]
                ),
            },
            **baseline_state,
        },
        "phi_harmonic_baseline": {
            "heldout_autoregressive": _span_metrics(heldout, phi_outputs),
            "recorded_training_examples": len(
                phi_receipt["training"]["examples"]
            ),
            **phi_state,
        },
        "controls": {
            "program_ablation_status": ablated_selection.status,
            "shuffled_uppercase_status": shuffled_selection.status,
            "shuffled_field_changed": controller.state_sha256(shuffled_state)
            != state_sha256,
            "restart_bytes_exact": restart_exact,
            "restart_field_exact": controller.state_sha256(restarted) == state_sha256,
            "selection_replay_exact": replayed_selections == selections,
            "inference_frozen": inference_before == inference_after,
            "role_program_ablation_status": role_ablated_selection.status,
            "shuffled_role_status": role_shuffled_selection.status,
            "shuffled_role_field_changed": role_controller.state_sha256(
                role_shuffled_state
            )
            != role_state_sha256,
            "role_restart_bytes_exact": role_restart_exact,
            "role_restart_field_exact": role_controller.state_sha256(role_restarted)
            == role_state_sha256,
            "role_selection_replay_exact": role_replayed_selections
            == role_selections,
            "role_inference_frozen": role_inference_before == role_inference_after,
            "tokenizer_roundtrip_exact": tokenizer_roundtrip_exact,
            "teacher_or_model_calls": 0,
            "provider_route": False,
        },
        "examples": examples,
    }

    required = {
        "natural_abstention": selections["natural"].status == "exhausted"
        and result["typed_program_abstraction"]["natural_heldout"]["false_settlements"]
        == 0,
        "positive_transfer": all(
            value["selection"]["status"] == "selected"
            and value["heldout"]["exact_continuations"] == len(heldout)
            for value in control_results.values()
        ),
        "field_counterfactual": ablated_selection.status == "exhausted",
        "shuffled_control": shuffled_selection.status == "exhausted",
        "restart": restart_exact
        and controller.state_sha256(restarted) == state_sha256,
        "frozen": replayed_selections == selections
        and inference_before == inference_after,
        "role_natural_abstention": role_selections["natural"].status == "exhausted"
        and result["role_symbol_abstraction"]["natural_heldout"][
            "false_settlements"
        ]
        == 0,
        "role_positive_transfer": all(
            value["selection"]["status"] == "selected"
            and value["heldout"]["exact_continuations"] == len(heldout)
            for value in role_control_results.values()
        ),
        "role_renaming_transfer": all(
            value["exact_continuations"] == len(heldout)
            for value in renamed_role_control_results.values()
        ),
        "role_field_counterfactual": role_ablated_selection.status == "exhausted",
        "role_shuffled_control": role_shuffled_selection.status == "exhausted",
        "role_restart": role_restart_exact
        and role_controller.state_sha256(role_restarted) == role_state_sha256,
        "role_frozen": role_replayed_selections == role_selections
        and role_inference_before == role_inference_after,
        "tokenizer_roundtrip": tokenizer_roundtrip_exact,
        "no_fallback": result["controls"]["teacher_or_model_calls"] == 0
        and result["controls"]["provider_route"] is False,
    }
    failures = [name for name, passed in required.items() if not passed]
    if failures:
        raise RuntimeError("text abstraction comparison failed: " + ", ".join(failures))
    return result


def main() -> int:
    print(json.dumps(run_text_abstraction_comparison(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
