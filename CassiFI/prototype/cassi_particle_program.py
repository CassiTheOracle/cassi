"""Canonical, deterministic particle programs for the Cassi world adapter."""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any, Final

PARTICLE_PROGRAM_SCHEMA: Final = "cassi.particle-program.v1"
MAX_PROGRAM_BYTES: Final = 64 * 1024
MAX_MESSAGE_BYTES: Final = 16 * 1024
MAX_POINT_CLOUD_POINTS: Final = 8192
MAX_REQUEST_ID_BYTES: Final = 256

_SELECTION_TYPES: Final = frozenset({"all", "sphere", "box"})
_TARGET_TYPES: Final = frozenset(
    {
        "line",
        "ring",
        "sphere",
        "grid",
        "helix",
        "double_helix",
        "point_cloud",
        "translate",
        "scale",
        "rotate",
    }
)
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


class ParticleProgramError(ValueError):
    """The proposed program is malformed, ambiguous, or outside bounded policy."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ParticleProgramError(f"program is not canonical JSON: {error}") from error


def program_digest(program: Mapping[str, Any]) -> str:
    """Return the SHA-256 of the normalized canonical program."""

    return hashlib.sha256(_canonical(normalize_program(program))).hexdigest()


def _exact_mapping(
    value: Any,
    *,
    required: set[str],
    optional: set[str] | None = None,
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ParticleProgramError(f"{label} must be an object")
    keys = set(value)
    allowed = required if optional is None else required | optional
    if not required <= keys or not keys <= allowed:
        raise ParticleProgramError(f"{label} has unexpected or missing keys")
    return value


def _number(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ParticleProgramError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive finite" if positive else "finite"
        raise ParticleProgramError(f"{label} must be {qualifier}")
    return result


def _integer(value: Any, label: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ParticleProgramError(f"{label} must be an integer >= {minimum}")
    return value


def _vector(value: Any, label: str) -> list[float]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) != 3
    ):
        raise ParticleProgramError(f"{label} must contain exactly three numbers")
    return [_number(component, f"{label}[{index}]") for index, component in enumerate(value)]


def _unit_vector(value: Any, label: str) -> list[float]:
    vector = _vector(value, label)
    length = math.sqrt(sum(component * component for component in vector))
    if length <= 1e-12:
        raise ParticleProgramError(f"{label} must be nonzero")
    return [component / length for component in vector]


def _selection(value: Any) -> dict[str, Any]:
    selection = _exact_mapping(
        value,
        required={"type"},
        optional={"center", "radius", "half_extents"},
        label="selection",
    )
    kind = selection.get("type")
    if kind not in _SELECTION_TYPES:
        raise ParticleProgramError("selection.type is unsupported")
    if kind == "all":
        if set(selection) != {"type"}:
            raise ParticleProgramError("all selection accepts no geometry")
        return {"type": "all"}
    if kind == "sphere":
        if set(selection) != {"type", "center", "radius"}:
            raise ParticleProgramError("sphere selection requires center/radius")
        return {
            "type": "sphere",
            "center": _vector(selection["center"], "selection.center"),
            "radius": _number(selection["radius"], "selection.radius", positive=True),
        }
    if set(selection) != {"type", "center", "half_extents"}:
        raise ParticleProgramError("box selection requires center/half_extents")
    half_extents = _vector(selection["half_extents"], "selection.half_extents")
    if any(component <= 0.0 for component in half_extents):
        raise ParticleProgramError("selection.half_extents must be positive")
    return {
        "type": "box",
        "center": _vector(selection["center"], "selection.center"),
        "half_extents": half_extents,
    }


def _target(value: Any) -> dict[str, Any]:
    target = _exact_mapping(
        value,
        required={"type"},
        optional={
            "center",
            "direction",
            "length",
            "normal",
            "radius",
            "phase",
            "spacing",
            "axis",
            "pitch",
            "turns",
            "points",
            "offset",
            "factor",
            "angle_radians",
        },
        label="target",
    )
    kind = target.get("type")
    if kind not in _TARGET_TYPES:
        raise ParticleProgramError("target.type is unsupported")

    if kind == "line":
        expected = {"type", "center", "direction", "length"}
        normalized = {
            "type": kind,
            "center": _vector(target.get("center"), "target.center"),
            "direction": _unit_vector(target.get("direction"), "target.direction"),
            "length": _number(target.get("length"), "target.length", positive=True),
        }
    elif kind == "ring":
        expected = {"type", "center", "normal", "radius", "phase"}
        normalized = {
            "type": kind,
            "center": _vector(target.get("center"), "target.center"),
            "normal": _unit_vector(target.get("normal"), "target.normal"),
            "radius": _number(target.get("radius"), "target.radius", positive=True),
            "phase": _number(target.get("phase"), "target.phase"),
        }
    elif kind == "sphere":
        expected = {"type", "center", "radius"}
        normalized = {
            "type": kind,
            "center": _vector(target.get("center"), "target.center"),
            "radius": _number(target.get("radius"), "target.radius", positive=True),
        }
    elif kind == "grid":
        expected = {"type", "center", "spacing"}
        normalized = {
            "type": kind,
            "center": _vector(target.get("center"), "target.center"),
            "spacing": _number(target.get("spacing"), "target.spacing", positive=True),
        }
    elif kind in {"helix", "double_helix"}:
        expected = {"type", "center", "axis", "radius", "pitch", "turns", "phase"}
        normalized = {
            "type": kind,
            "center": _vector(target.get("center"), "target.center"),
            "axis": _unit_vector(target.get("axis"), "target.axis"),
            "radius": _number(target.get("radius"), "target.radius", positive=True),
            "pitch": _number(target.get("pitch"), "target.pitch", positive=True),
            "turns": _number(target.get("turns"), "target.turns", positive=True),
            "phase": _number(target.get("phase"), "target.phase"),
        }
    elif kind == "point_cloud":
        expected = {"type", "points"}
        points = target.get("points")
        if (
            not isinstance(points, Sequence)
            or isinstance(points, (str, bytes, bytearray))
            or not 1 <= len(points) <= MAX_POINT_CLOUD_POINTS
        ):
            raise ParticleProgramError(
                f"target.points must contain 1..{MAX_POINT_CLOUD_POINTS} points"
            )
        indexed = [(_vector(point, f"target.points[{index}]"), index) for index, point in enumerate(points)]
        indexed.sort(key=lambda item: (*item[0], item[1]))
        normalized = {"type": kind, "points": [point for point, _ in indexed]}
    elif kind == "translate":
        expected = {"type", "offset"}
        normalized = {
            "type": kind,
            "offset": _vector(target.get("offset"), "target.offset"),
        }
    elif kind == "scale":
        expected = {"type", "center", "factor"}
        normalized = {
            "type": kind,
            "center": _vector(target.get("center"), "target.center"),
            "factor": _number(target.get("factor"), "target.factor", positive=True),
        }
    else:
        expected = {"type", "center", "axis", "angle_radians"}
        normalized = {
            "type": kind,
            "center": _vector(target.get("center"), "target.center"),
            "axis": _unit_vector(target.get("axis"), "target.axis"),
            "angle_radians": _number(
                target.get("angle_radians"), "target.angle_radians"
            ),
        }
    if set(target) != expected:
        raise ParticleProgramError(f"{kind} target has an invalid key set")
    return normalized


def _motion(value: Any) -> dict[str, Any]:
    motion = _exact_mapping(
        value,
        required={"type"},
        optional={"velocity_policy", "speed"},
        label="motion",
    )
    kind = motion.get("type")
    if kind == "exact":
        if set(motion) != {"type", "velocity_policy"} or motion.get(
            "velocity_policy"
        ) not in {"preserve", "zero"}:
            raise ParticleProgramError(
                "exact motion requires velocity_policy preserve or zero"
            )
        return {"type": "exact", "velocity_policy": motion["velocity_policy"]}
    if kind == "steer":
        if set(motion) != {"type", "speed"}:
            raise ParticleProgramError("steer motion requires speed")
        return {
            "type": "steer",
            "speed": _number(motion["speed"], "motion.speed", positive=True),
        }
    raise ParticleProgramError("motion.type is unsupported")


def _constraints(value: Any) -> dict[str, Any]:
    constraints = _exact_mapping(
        value,
        required={"maximum_particles", "maximum_displacement", "maximum_speed"},
        label="constraints",
    )
    return {
        "maximum_particles": _integer(
            constraints["maximum_particles"], "constraints.maximum_particles"
        ),
        "maximum_displacement": _number(
            constraints["maximum_displacement"],
            "constraints.maximum_displacement",
            positive=True,
        ),
        "maximum_speed": _number(
            constraints["maximum_speed"], "constraints.maximum_speed", positive=True
        ),
    }


def _source(value: Any) -> dict[str, Any]:
    source = _exact_mapping(
        value,
        required={"kind"},
        optional={"text"},
        label="source",
    )
    kind = source.get("kind")
    if kind not in {"chat", "manual", "explicit"}:
        raise ParticleProgramError("source.kind is unsupported")
    text = source.get("text")
    if text is None:
        if set(source) != {"kind"}:
            raise ParticleProgramError("source.text must be text")
        return {"kind": kind}
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ParticleProgramError("source.text exceeds the bounded UTF-8 limit")
    return {"kind": kind, "text": text}


def normalize_program(program: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize one particle program without world mutation."""

    value = _exact_mapping(
        program,
        required={
            "schema",
            "operation",
            "selection",
            "target",
            "motion",
            "constraints",
            "source",
            "request_id",
        },
        label="program",
    )
    if value.get("schema") != PARTICLE_PROGRAM_SCHEMA:
        raise ParticleProgramError("program schema is unsupported")
    if value.get("operation") != "arrange":
        raise ParticleProgramError("program operation is unsupported")
    request_id = value.get("request_id")
    if (
        not isinstance(request_id, str)
        or len(request_id.encode("utf-8")) > MAX_REQUEST_ID_BYTES
        or _REQUEST_ID.fullmatch(request_id) is None
    ):
        raise ParticleProgramError("request_id is malformed")
    normalized = {
        "schema": PARTICLE_PROGRAM_SCHEMA,
        "operation": "arrange",
        "selection": _selection(value["selection"]),
        "target": _target(value["target"]),
        "motion": _motion(value["motion"]),
        "constraints": _constraints(value["constraints"]),
        "source": _source(value["source"]),
        "request_id": request_id,
    }
    if len(_canonical(normalized)) > MAX_PROGRAM_BYTES:
        raise ParticleProgramError("program exceeds the bounded encoded limit")
    return normalized

def _context_vector(
    context: Mapping[str, Any], key: str, default: list[float]
) -> list[float]:
    value = context.get(key, default)
    return _vector(value, f"context.{key}")


def _named_number(
    text: str,
    names: Sequence[str],
    default: float,
    *,
    positive: bool = True,
) -> float:
    alternatives = "|".join(re.escape(name) for name in names)
    patterns = (
        rf"\b(?:{alternatives})\s*(?:=|of|to|by)?\s*({_NUMBER})\b",
        rf"\b({_NUMBER})\s*(?:unit|units)?\s*(?:{alternatives})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match is not None:
            return _number(float(match.group(1)), names[0], positive=positive)
    return _number(default, names[0], positive=positive)


def _named_vector(text: str, names: Sequence[str]) -> list[float] | None:
    alternatives = "|".join(re.escape(name) for name in names)
    match = re.search(
        rf"\b(?:{alternatives})\s*(?:=|to|by|at)?\s*[\[(]?\s*({_NUMBER})\s*,\s*({_NUMBER})\s*,\s*({_NUMBER})\s*[\])]?",
        text,
    )
    if match is None:
        return None
    return [float(match.group(index)) for index in (1, 2, 3)]


def _limits(context: Mapping[str, Any]) -> dict[str, Any]:
    raw = context.get("constraints", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ParticleProgramError("context.constraints must be an object")
    particle_count = context.get("particle_count", 2_500_000)
    maximum_particles = raw.get("maximum_particles", particle_count)
    if isinstance(maximum_particles, int) and not isinstance(maximum_particles, bool):
        maximum_particles = max(1, min(maximum_particles, 2_500_000))
    return _constraints(
        {
            "maximum_particles": maximum_particles,
            "maximum_displacement": raw.get("maximum_displacement", 1000.0),
            "maximum_speed": raw.get("maximum_speed", 1000.0),
        }
    )


def _context_selection(context: Mapping[str, Any]) -> dict[str, Any]:
    value = context.get("selection")
    if value is None:
        return {"type": "all"}
    return _selection(value)


def _point_cloud_from_text(text: str) -> list[list[float]]:
    marker = re.search(r"\bpoints?\s*(?:=|:)\s*", text, re.IGNORECASE)
    if marker is None:
        raise ParticleProgramError("point_cloud requires a JSON points array")
    try:
        value = json.JSONDecoder().raw_decode(text[marker.end() :].lstrip())[0]
    except (json.JSONDecodeError, ValueError) as error:
        raise ParticleProgramError("point_cloud points are not valid JSON") from error
    normalized = _target({"type": "point_cloud", "points": value})
    return normalized["points"]


def deterministic_particle_program(
    message: str,
    context: Any,
    *,
    request_id: str,
) -> dict[str, Any]:
    """Compile the bounded registered natural-language surface into one program."""

    if not isinstance(message, str) or not message.strip():
        raise ParticleProgramError("message must be nonempty text")
    if len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ParticleProgramError("message exceeds the bounded UTF-8 limit")
    if not isinstance(context, Mapping):
        raise ParticleProgramError("context must be an object")

    text = message.casefold()
    cursor = _context_vector(context, "cursor", [0.0, 0.0, 0.0])
    center = _named_vector(text, ("center", "around", "at")) or cursor
    axis = _named_vector(text, ("axis",)) or [0.0, 1.0, 0.0]
    normal = _named_vector(text, ("normal",)) or axis
    radius = _named_number(
        text,
        ("radius",),
        _number(context.get("default_radius", 5.0), "context.default_radius", positive=True),
    )
    phase = (
        math.radians(_named_number(text, ("phase",), 0.0, positive=False))
        if "phase" in text
        else 0.0
    )

    if "double helix" in text or "double-helix" in text:
        target: dict[str, Any] = {
            "type": "double_helix",
            "center": center,
            "axis": axis,
            "radius": radius,
            "pitch": _named_number(text, ("pitch",), radius),
            "turns": _named_number(text, ("turns", "turn"), 3.0),
            "phase": phase,
        }
    elif "helix" in text or "spiral" in text:
        target = {
            "type": "helix",
            "center": center,
            "axis": axis,
            "radius": radius,
            "pitch": _named_number(text, ("pitch",), radius),
            "turns": _named_number(text, ("turns", "turn"), 3.0),
            "phase": phase,
        }
    elif "point cloud" in text or "point-cloud" in text:
        target = {"type": "point_cloud", "points": _point_cloud_from_text(message)}
    elif "ring" in text or "circle" in text or "loop" in text:
        target = {
            "type": "ring",
            "center": center,
            "normal": normal,
            "radius": radius,
            "phase": phase,
        }
    elif "sphere" in text or "shell" in text:
        target = {"type": "sphere", "center": center, "radius": radius}
    elif "grid" in text or "lattice" in text:
        target = {
            "type": "grid",
            "center": center,
            "spacing": _named_number(text, ("spacing",), max(radius * 0.25, 1e-6)),
        }
    elif "line" in text:
        target = {
            "type": "line",
            "center": center,
            "direction": _named_vector(text, ("direction",)) or [1.0, 0.0, 0.0],
            "length": _named_number(text, ("length",), 2.0 * radius),
        }
    elif "translate" in text or re.search(r"\bmove\b", text):
        offset = _named_vector(text, ("offset", "by", "translate", "move"))
        if offset is None:
            raise ParticleProgramError("translate requires an offset vector")
        target = {"type": "translate", "offset": offset}
    elif "scale" in text or "resize" in text:
        target = {
            "type": "scale",
            "center": center,
            "factor": _named_number(text, ("factor", "scale"), 1.0),
        }
    elif "rotate" in text or "rotation" in text:
        angle = _named_number(
            text, ("degrees", "degree", "angle"), 90.0, positive=False
        )
        target = {
            "type": "rotate",
            "center": center,
            "axis": axis,
            "angle_radians": math.radians(angle),
        }
    else:
        raise ParticleProgramError(
            "name one target: line, ring, sphere, grid, helix, double helix, point cloud, translate, scale, or rotate"
        )

    if "steer" in text or "gradually" in text:
        motion: dict[str, Any] = {
            "type": "steer",
            "speed": _named_number(text, ("speed",), 1.0),
        }
    else:
        motion = {
            "type": "exact",
            "velocity_policy": "preserve" if "preserve velocity" in text else "zero",
        }

    return normalize_program(
        {
            "schema": PARTICLE_PROGRAM_SCHEMA,
            "operation": "arrange",
            "selection": _context_selection(context),
            "target": target,
            "motion": motion,
            "constraints": _limits(context),
            "source": {"kind": "chat", "text": message},
            "request_id": request_id,
        }
    )


def _qwen_candidate(
    url: str,
    message: str,
    context: Mapping[str, Any],
    *,
    request_id: str,
    token: str | None,
    timeout: float,
) -> dict[str, Any]:
    prompt = (
        "Return only one JSON object using schema cassi.particle-program.v1. "
        "Allowed selectors: all, sphere, box. Allowed targets: line, ring, sphere, "
        "grid, helix, double_helix, point_cloud, translate, scale, rotate. "
        "Allowed motion: exact or steer. Do not add keys. Request: "
        + message
        + "\nContext: "
        + _canonical(context).decode("utf-8")
        + "\nrequest_id: "
        + request_id
    )
    body = _canonical(
        {
            "model": "qwen",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
        }
    )
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        decoded = json.loads(response.read())
    candidate: Any = decoded
    if isinstance(decoded, Mapping) and "choices" in decoded:
        candidate = json.loads(decoded["choices"][0]["message"]["content"])
    if not isinstance(candidate, Mapping):
        raise ParticleProgramError("Qwen planner returned no program object")
    value = dict(candidate)
    value["request_id"] = request_id
    value["source"] = {"kind": "chat", "text": message}
    return normalize_program(value)


def compile_particle_program(
    message: str,
    context: Mapping[str, Any],
    *,
    request_id: str,
    qwen_url: str | None = None,
    qwen_token: str | None = None,
    qwen_timeout: float = 10.0,
) -> tuple[dict[str, Any], str]:
    """Use optional stateless Qwen planning, then the deterministic fallback."""

    if qwen_url:
        try:
            return (
                _qwen_candidate(
                    qwen_url,
                    message,
                    context,
                    request_id=request_id,
                    token=qwen_token,
                    timeout=qwen_timeout,
                ),
                "qwen",
            )
        except Exception:
            pass
    return (
        deterministic_particle_program(message, context, request_id=request_id),
        "deterministic",
    )
