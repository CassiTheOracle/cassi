#!/usr/bin/env python3
"""Cassi's thinking brain: neuron cells joined by one circulating Yang/Yin field.

Every neuron is a cell with one way of thinking, powered by the live Qwen brain.
Its site in the CassiFI thinking field (``cassi_thinking_field.ThinkingField``)
holds every idea it currently feels as a Yang/Yin density pair.  Along each
synapse Yang travels forward and Yin travels back, so open possibilities stream
from generative neurons into consolidating ones while established results flow
back to the neurons that opened them.

Layouts:

* ``ring``: intuition -> mathematician -> skeptic -> intuition.
* ``cortex`` (default): a loop alternating generative neurons (intuition,
  analogist, imaginer, explorer) with consolidating neurons (mathematician,
  skeptic), plus an integrator hub that exchanges with every loop neuron in
  both directions, like a global workspace.  ``--size`` sets the loop length.

The field decides what a neuron perceives (the brightest ideas at its own
site, up to its attention span), when it fires (its potential is the local
conversion power of the ideas it owes work on, recovering after each firing;
up to ``--parallel`` neurons think at once, one per brain slot), and what the
brain concludes (the idea with the highest resonance, the geometric mean of
its Qi over every neuron).

Mathematicians, skeptics, and imaginers write and run real Python in a plain
text channel, fixing a failing script from its own error, and a proof stands
only on a script that ran cleanly.  Skeptics and explorers read the
CassiTheory library on the CassiFI field shelf.  Every act, computation, and
citation is an exact record in ``records.jsonl``; the field and the neurons'
memories live in ``state.json`` and resume after interruption.

A verdict reaches every perceived idea making the same claim that the judging
neuron has not judged yet; a judgment a neuron already holds stays with it.
A neuron whose verdict came only by association, on an idea another neuron
judged the other way, examines that idea itself, and its direct verdict
replaces the associative one.  An answer that names its better claim among
the same-claim ideas passes no verdict along.  A skeptic's objection or a
mathematician's correction enters the field even when working memory is full
and goes to the other kind of consolidating neuron; when the better claim is
already present at the judging neuron's site, the neuron backs that idea with
Yang instead.  Conjectures and the integrator's syntheses wait for room.  The
integrator fires once at least two other neurons have judged since it last
fired, and its latest state of mind reaches every neuron that fires after it,
beside the ideas at that neuron's site.  An idea that fades below perception
at every neuron leaves the field, and its record, verdicts, and lineage stay
in memory.  When no neuron owes work the brain rests: the field breathes,
ideas fade and leave, and fired neurons recover until one wakes.

    python cassi_thinking_brain.py think --home RUN --question "..." --acts 48
    python cassi_thinking_brain.py resume --home RUN --acts 24
    python cassi_thinking_brain.py status --home RUN
"""
from __future__ import annotations

import argparse
import concurrent.futures
import http.client
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Collection, Mapping, Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "CassiFI"))

from cassi_field_foundry import FieldShelf  # noqa: E402
from cassi_thinking_field import PHI, ThinkingField  # noqa: E402

SCHEMA = "cassiqwen.thinking-brain.v1"
DEFAULT_BRAIN = "http://127.0.0.1:8084"  # the port start-llama-server.ps1 serves
DEFAULT_LIBRARY = "cassitheory"
GENERATIVE = ("intuition", "analogist", "imaginer", "explorer")
CONSOLIDATING = ("mathematician", "skeptic")
HUB = "integrator"
VERDICTS = {"mathematician": ("proven", "supported", "undecided", "refuted"),
            "skeptic": ("survives", "weakened", "broken")}
POSITIVE = ("proven", "supported", "survives")
NEGATIVE = ("refuted", "broken")
PRESENT = 0.08          # density at a site below which a neuron no longer perceives the idea
BREATH = 1.0            # field time that passes with each completed act
AMPLITUDE = 1.0 / 3.0   # density per neuron that one full-strength deposit adds; larger brains get larger deposits
REFRACTORY = 1.0        # field time over which a neuron's potential recovers after it fires
THRESHOLD = 1e-4        # potential below which a neuron stays quiet
MAX_ACTIVE = 16         # live ideas (dense enough, never broken) before generative neurons wait for room
MAX_IDEAS = 48          # ideas the field holds at once; an idea faded below perception everywhere leaves it
ATTENTION = 8           # brightest ideas a neuron perceives at once, its working memory
PYTHON_TIMEOUT = 90.0
OUTPUT_LIMIT = 4000
REPAIRS = 2             # times a neuron may fix a failing script from its own error
BUSY_RETRIES = 3        # waits for the brain server to free capacity before an act falls silent
MAX_REST = 256          # breaths a resting brain may take while its full working memory fades


def role_of(neuron: str) -> str:
    return re.sub(r"-\d+$", "", neuron)


def _side(verdict: str | None) -> int:
    return 1 if verdict in POSITIVE else -1 if verdict in NEGATIVE else 0


def layout(name: str, size: int = 8) -> tuple[list[str], list[tuple[str, str]]]:
    """Neurons and synapses of a named brain layout."""

    if name == "ring":
        cells = ["intuition", "mathematician", "skeptic"]
        return cells, list(zip(cells, cells[1:] + cells[:1]))
    if name != "cortex":
        raise ValueError(f"unknown layout {name}")
    if size < 4 or size % 2:
        raise ValueError("a cortex loop needs an even number of at least four neurons")
    seen: dict[str, int] = {}
    loop = []
    for position in range(size):
        roles = GENERATIVE if position % 2 == 0 else CONSOLIDATING
        role = roles[(position // 2) % len(roles)]
        seen[role] = seen.get(role, 0) + 1
        loop.append(role if seen[role] == 1 else f"{role}-{seen[role]}")
    synapses = list(zip(loop, loop[1:] + loop[:1]))
    for neuron in loop:
        synapses += [(neuron, HUB), (HUB, neuron)]
    return loop + [HUB], synapses


# ── live brain and tools ────────────────────────────────────────────────────


class BrainSilence(RuntimeError):
    """The live brain gave no parsable answer."""


class BrainUnavailable(ConnectionError):
    """The brain server stopped answering; the run pauses with every finished act saved."""


_SWALLOWED = {"\b": "\\b", "\f": "\\f", "\t": "\\t", "\r": "\\r", "\n": "\\n"}
_SWALLOWED_AT = re.compile(r"[\b\f\t\r](?=[A-Za-z])|\n(?=(?:eq|abla|u|ot|otin|leq|geq|subseteq|parallel)(?![A-Za-z]))")
_IDEA_ID = re.compile(r"i\d+")
_FENCED = re.compile(r"```[^\n]*\n(.*?)(?:\n```|\Z)", re.S)


def _restore_latex(value: Any) -> Any:
    """Undo JSON escapes that swallowed a LaTeX command (``\\frac`` read as form feed + ``rac``, ``\\neq`` as
    newline + ``eq``)."""

    if isinstance(value, str):
        return _SWALLOWED_AT.sub(lambda match: _SWALLOWED[match.group()], value)
    if isinstance(value, list):
        return [_restore_latex(item) for item in value]
    if isinstance(value, dict):
        return {key: _restore_latex(item) for key, item in value.items()}
    return value


def _script(text: str) -> str:
    """The longest fenced code block of a reply, or the whole reply when it has none."""

    blocks = _FENCED.findall(text)
    return max(blocks, key=len) if blocks else text.strip()


class LiveBrain:
    """Client for the live llama.cpp brain: schema-constrained JSON answers and plain-text scripts."""

    def __init__(self, base_url: str = DEFAULT_BRAIN) -> None:
        match = re.fullmatch(r"http://(127\.0\.0\.1|localhost):(\d+)/?", base_url)
        if not match:
            raise ValueError("the brain must be a loopback http://host:port")
        self.host, self.port = match.group(1), int(match.group(2))
        self.model = self._request("GET", "/v1/models")["data"][0]["id"]
        try:
            self.slots = max(1, len(self._request("GET", "/slots")))
        except (RuntimeError, TypeError, ValueError):
            self.slots = 1

    def _request(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        for attempt in range(BUSY_RETRIES + 1):
            connection = http.client.HTTPConnection(self.host, self.port, timeout=1800)
            try:
                connection.request(method, path, body=payload,
                                   headers={} if payload is None else {"content-type": "application/json"})
                response = connection.getresponse()
                raw = response.read().decode("utf-8")
            except (OSError, http.client.HTTPException) as lost:  # refused, reset, or cut off: down or restarting
                if attempt == BUSY_RETRIES:
                    raise BrainUnavailable(f"the brain at http://{self.host}:{self.port} stopped answering: "
                                           f"{type(lost).__name__}: {lost}") from lost
                time.sleep(10.0 * (attempt + 1))
                continue
            finally:
                connection.close()
            if response.status == 200:
                return json.loads(raw)
            busy = response.status == 503 or "Context size has been exceeded" in raw
            if not busy or attempt == BUSY_RETRIES:
                raise RuntimeError(f"brain returned HTTP {response.status}: {raw[:300]}")
            time.sleep(10.0 * (attempt + 1))  # other slots are holding the shared context; let them finish

    def ask(self, system: str, prompt: str, schema: Mapping[str, Any], *, temperature: float,
            max_tokens: int = 1600) -> dict[str, Any]:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": temperature, "stream": False,
            "response_format": {"type": "json_schema", "json_schema": {"name": "act", "schema": schema}},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        started = time.perf_counter()
        content = ""
        for _ in range(2):
            reply = self._request("POST", "/v1/chat/completions", body)
            content = reply["choices"][0]["message"].get("content") or ""
            try:
                answer = json.loads(content)
            except json.JSONDecodeError:
                body["max_tokens"] *= 2  # an answer cut off at the token limit is the usual cause
                continue
            if isinstance(answer, dict):
                return {"answer": _restore_latex(answer), "raw": content,
                        "seconds": round(time.perf_counter() - started, 3),
                        "tokens": reply.get("usage", {}).get("completion_tokens")}
        raise BrainSilence(content[-400:])

    def write(self, system: str, prompt: str, *, temperature: float, max_tokens: int = 2400) -> dict[str, Any]:
        """A plain-text reply, so code reaches Python without passing through JSON string escapes."""

        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": temperature, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        started = time.perf_counter()
        for _ in range(2):
            reply = self._request("POST", "/v1/chat/completions", body)
            choice = reply["choices"][0]
            if choice.get("finish_reason") != "length":
                break
            body["max_tokens"] *= 2
        return {"text": choice["message"].get("content") or "", "seconds": round(time.perf_counter() - started, 3),
                "tokens": reply.get("usage", {}).get("completion_tokens")}


def run_python(code: str) -> dict[str, Any]:
    """Run brain-written Python in a scratch directory and return its exact output."""

    if not code.strip():
        return {"ran": False}
    with tempfile.TemporaryDirectory(prefix="cassi_neuron_") as scratch:
        script = Path(scratch) / "neuron.py"
        script.write_text(code, encoding="utf-8")
        started = time.perf_counter()
        try:
            done = subprocess.run([sys.executable, str(script)], cwd=scratch, capture_output=True,
                                  text=True, timeout=PYTHON_TIMEOUT, encoding="utf-8", errors="replace",
                                  env={**os.environ, "PYTHONUTF8": "1"})
            output, status = done.stdout + (("\n[stderr]\n" + done.stderr) if done.stderr else ""), done.returncode
        except subprocess.TimeoutExpired:
            output, status = f"[timed out after {PYTHON_TIMEOUT:.0f} s]", None
    kept = output if len(output) <= OUTPUT_LIMIT else (
        output[:OUTPUT_LIMIT // 2] + f"\n[... {len(output) - OUTPUT_LIMIT} characters omitted ...]\n"
        + output[-OUTPUT_LIMIT // 2:])
    return {"ran": True, "code": code, "exit": status, "seconds": round(time.perf_counter() - started, 3),
            "output": kept, "truncated": len(output) > OUTPUT_LIMIT}


class Library:
    def __init__(self, name: str = DEFAULT_LIBRARY) -> None:
        self.name = name
        self.reader = FieldShelf().open(name)
        self._lock = threading.Lock()

    def search(self, query: str, limit: int = 3, chars: int = 1500) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        with self._lock:
            hits = self.reader.search(query, limit=limit)["hits"]
        return [{"library": self.name, "path": hit["path"], "title": hit["title"], "start": hit["start"],
                 "end": hit["end"], "sha256": hit["sha256"], "text": hit["text"][:chars]} for hit in hits]


# ── what each neuron is asked ───────────────────────────────────────────────

MIND = ("You are one neuron of Cassi, a mind whose neurons think together through a circulating Yang/Yin field. "
        "Be precise and brief. ")
SYSTEM = MIND + ("Reply with one JSON object in the requested shape. Inside JSON strings write mathematics in plain "
                 "Unicode (φ, √, ², ≤, ∂).")
SYSTEM_CODE = MIND + "You write complete Python scripts that run on the first try."
CODE_RULES = (
    "\nReply with one complete Python script in a single ```python block and nothing else. numpy, scipy and sympy "
    "are available (sympy has no phi; its golden ratio is sp.GoldenRatio). The script must finish within a minute "
    "and print every decisive quantity with a label."
)

ROLE = {
    "intuition": (
        "You are INTUITION, a generative neuron. You sense which direction is promising before any proof exists, "
        "propose sharp checkable conjectures, refine ideas that were broken, promote ideas that pull, and release "
        "ideas that no longer do."
    ),
    "analogist": (
        "You are the ANALOGIST, a generative neuron. You find the same structure in different fields (physics, "
        "mathematics, biology, computation, meditation and the felt flow of Qi) and carry what is known there to "
        "the question as a checkable claim."
    ),
    "imaginer": (
        "You are the IMAGINER, a generative neuron. You answer 'what would happen if...' by building a small "
        "numerical model, running it, and proposing the claim the observation suggests."
    ),
    "explorer": (
        "You are the EXPLORER, a generative neuron driven by curiosity. You notice surprises: a result that broke "
        "an expectation, neurons that disagree, places where the theory is silent. You search the CassiTheory "
        "library and turn the surprise into a sharper checkable claim."
    ),
    "mathematician": (
        "You are a MATHEMATICIAN, a consolidating neuron. You turn a vague idea into a precise statement and decide "
        "it by derivation and computation."
    ),
    "skeptic": (
        "You are a SKEPTIC, a consolidating neuron. You attack a claim: counterexamples, edge cases, hidden "
        "assumptions, and conflicts with the Cassi theory registry. A claim is strong only after you tried to "
        "break it and failed."
    ),
    "integrator": (
        "You are the INTEGRATOR, the hub every neuron exchanges with. You see the whole brain at once, decide what "
        "it currently believes, endorse ideas the evidence supports, release ideas that are superseded or broken, "
        "and join compatible supported ideas into one synthesis."
    ),
}

PROPOSE = (
    " proposals: at most two new single checkable mathematical claims that neither an idea at your site nor the "
    "state of mind already states (confidence 0..1; refines: the id of the idea it refines, or \"\"); back an idea "
    "already present by promoting it. promote: ideas that deserve more attention, strength 0..1. release: ids of "
    "ideas to let go."
)


def _object(**properties: Any) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


_TEXT = {"type": "string"}
_NUMBER = {"type": "number"}
_IDS = {"type": "array", "items": _TEXT, "maxItems": 4}
_PROPOSALS = {"type": "array", "maxItems": 2,
              "items": _object(statement=_TEXT, why=_TEXT, confidence=_NUMBER, refines=_TEXT)}
_WEIGHTS = {"type": "array", "maxItems": 3, "items": _object(idea=_TEXT, strength=_NUMBER)}


def _opening(lead: str) -> dict[str, Any]:
    return _object(**{lead: _TEXT}, proposals=_PROPOSALS, promote=_WEIGHTS, release=_IDS)


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


def _unit(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, number)) if math.isfinite(number) else default


def _evidence(run: Mapping[str, Any], hits: Sequence[Mapping[str, Any]]) -> str:
    parts = []
    if run.get("ran"):
        parts.append(f"YOUR SCRIPT:\n```python\n{run['code']}\n```\nIT PRINTED (exit {run['exit']}):\n{run['output']}")
    if hits:
        parts.append("LIBRARY PASSAGES:\n" + "\n\n".join(f"[{h['path']} :: {h['title']}]\n{h['text']}" for h in hits))
    return "\n\n".join(parts or ["(no computation and no passages)"]) + "\n\n"


def _verdict_line(verdict: Mapping[str, Any]) -> str:
    via = f" (same claim as {verdict['via']})" if verdict.get("via") else ""
    return f"{verdict['verdict']}{via}: {verdict['reason'][:200]}"


# ── the organism ────────────────────────────────────────────────────────────


class ThinkingBrain:
    """Neurons, their circulating field, and the exact record of their thinking."""

    def __init__(self, home: Path, brain: LiveBrain | None = None, library: Library | None = None,
                 python: Callable[[str], dict[str, Any]] = run_python) -> None:
        self.home = Path(home)
        self.brain, self.library, self.python = brain, library, python
        state = json.loads((self.home / "state.json").read_text(encoding="utf-8"))
        if state.get("schema") != SCHEMA:
            raise ValueError(f"{self.home} is not a thinking brain")
        self.state = state
        self.field = ThinkingField.from_json(state["field"])
        self.amplitude = AMPLITUDE * len(self.field.cells)

    @classmethod
    def create(cls, home: Path, question: str, *, layout_name: str = "cortex", size: int = 8,
               library: Library | None = None, **kwargs: Any) -> "ThinkingBrain":
        home = Path(home)
        if (home / "state.json").exists():
            raise FileExistsError(f"{home} already holds a thinking brain")
        cells, synapses = layout(layout_name, size)
        home.mkdir(parents=True, exist_ok=True)
        grounding = library.search(question, limit=2, chars=3600) if library else []
        state = {
            "schema": SCHEMA, "question": question, "layout": layout_name, "grounding": grounding,
            "field": ThinkingField(cells, synapses).to_json(), "ideas": {}, "events": [], "mind": None,
            "neurons": {n: {"role": role_of(n), "fired": 0, "fired_at": None, "seen_events": 0, "judged": []}
                        for n in cells},
            "acts": 0, "status": "thinking",
        }
        (home / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        organism = cls(home, library=library, **kwargs)
        organism._record({"kind": "question", "question": question, "layout": layout_name,
                          "synapses": state["field"]["synapses"], "grounding": grounding})
        return organism

    def _save(self) -> None:
        self.state["field"] = self.field.to_json()
        path = self.home / "state.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    def _record(self, record: Mapping[str, Any]) -> None:
        with (self.home / "records.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"field_time": round(self.field.time, 6), **record}, ensure_ascii=False) + "\n")

    # perception --------------------------------------------------------------

    def _live(self, idea: str) -> bool:
        k = self.field.ideas.index(idea)
        dense = float((self.field.ey[k] + self.field.ei[k]).max()) >= PRESENT
        return dense and not any(v["verdict"] in NEGATIVE for v in self.state["ideas"][idea]["verdicts"].values())

    def _room(self) -> bool:
        """Room for a generative proposal or a synthesis: field capacity left and working memory below capacity."""

        live = sum(1 for idea in self.field.ideas if self._live(idea))
        return len(self.field.ideas) < MAX_IDEAS and live < MAX_ACTIVE

    def _new_idea(self, statement: Any, *, neuron: str, kind: str, parents: list[str], why: Any) -> str | None:
        """Admit an idea. A judgment's correction or objection enters even when working memory is full;
        conjectures and syntheses wait for room."""

        statement = str(statement or "").strip()
        if not statement or len(self.field.ideas) >= MAX_IDEAS or (
                kind in ("conjecture", "synthesis") and not self._room()):
            return None
        idea = f"i{len(self.state['ideas']) + 1}"
        self.state["ideas"][idea] = {"statement": statement, "kind": kind, "by": neuron, "parents": parents,
                                     "why": str(why or ""), "verdicts": {}, "born": self.state["acts"]}
        self.field.add_idea(idea)
        self.state["events"].append({"neuron": neuron, "idea": idea, "event": "proposed"})
        return idea

    def _view(self, neuron: str) -> list[dict[str, Any]]:
        """The brightest ideas present at this neuron's site, up to its attention span, with their verdicts."""

        c = self.field.cells.index(neuron)
        q = self.field.qi()
        rows = []
        for k, idea in enumerate(self.field.ideas):
            ey, ei = float(self.field.ey[k, c]), float(self.field.ei[k, c])
            if ey + ei < PRESENT:
                continue
            meta = self.state["ideas"][idea]
            rows.append({
                "id": idea, "by": meta["by"], "kind": meta["kind"], "statement": meta["statement"],
                "parents": meta["parents"], "presence": round(ey + ei, 3), "qi_here": round(float(q[k, c]), 3),
                "tone": "open, pressing for work" if ey > PHI * ei else "consolidated",
                "verdicts": {n: _verdict_line(v) for n, v in meta["verdicts"].items()},
            })
        rows.sort(key=lambda row: -row["presence"])
        return rows[:ATTENTION]

    def _context(self, neuron: str, view: Sequence[Mapping[str, Any]]) -> str:
        """What a neuron knows when it fires: its role, the question, the grounding passages, the integrator's
        broadcast state of mind, and the ideas present at its site."""

        grounding = "\n\n".join(f"[{g['path']} :: {g['title']}]\n{g['text']}" for g in self.state["grounding"])
        mind = self.state["mind"]
        broadcast = f"THE BRAIN'S STATE OF MIND (the integrator, act {mind['act']}):\n{mind['text']}\n\n" if mind else ""
        return (f"{ROLE[role_of(neuron)]}\n\nQUESTION:\n{self.state['question']}\n\n"
                f"SOURCE PASSAGES (CassiTheory library):\n{grounding or '(none)'}\n\n{broadcast}"
                f"IDEAS PRESENT AT YOUR SITE, brightest first:\n{_dump(view) if view else '(none yet)'}\n")

    @staticmethod
    def _contested(neuron: str, verdicts: Mapping[str, Mapping[str, Any]]) -> bool:
        """The neuron judged this idea only by association, and another neuron judged it the other way."""

        own = verdicts.get(neuron)
        side = _side(own["verdict"]) if own and own.get("via") else 0
        return side != 0 and any(_side(v["verdict"]) == -side for n, v in verdicts.items() if n != neuron)

    def _contest_note(self, neuron: str, idea: str | None) -> str:
        """What a neuron re-examining a contested idea is told about its own associative verdict."""

        verdicts = self.state["ideas"][idea]["verdicts"] if idea else {}
        if not self._contested(neuron, verdicts):
            return ""
        own = verdicts[neuron]
        return (f"YOUR VERDICT SO FAR, {own['verdict']}, came only by association with {own['via']}, and other "
                "neurons judged this idea the other way. Examine this idea itself.\n")

    def candidates(self, busy: Mapping[str, str | None] | None = None) -> list[tuple[float, str, str | None]]:
        """Every quiet neuron that owes work, with its firing potential and focus idea."""

        busy = busy or {}
        churn = self.field.churn()
        rho = self.field.ey + self.field.ei
        room = self._room()
        taken = {(role_of(n), idea) for n, idea in busy.items() if idea}
        verdict_events = {v for names in VERDICTS.values() for v in names}
        out: list[tuple[float, str, str | None]] = []
        for c, neuron in enumerate(self.field.cells):
            if neuron in busy:
                continue
            memory = self.state["neurons"][neuron]
            role = memory["role"]
            recovery = 1.0 if memory["fired_at"] is None else (
                1.0 - math.exp(-(self.field.time - memory["fired_at"]) / REFRACTORY))
            if role in CONSOLIDATING:
                best: tuple[float, str] | None = None
                for k, idea in enumerate(self.field.ideas):
                    meta = self.state["ideas"][idea]
                    verdicts = meta["verdicts"]
                    if rho[k, c] < PRESENT or (role, idea) in taken:
                        continue
                    if not self._contested(neuron, verdicts) and (
                            idea in memory["judged"] or role_of(meta["by"]) == role
                            or any(role_of(n) == role for n in verdicts)
                            or any(v["verdict"] in NEGATIVE for v in verdicts.values())):
                        continue
                    value = float(churn[k, c] + 0.1 * rho[k, c])
                    if best is None or value > best[0]:
                        best = (value, idea)
                if best:
                    out.append((recovery * best[0], neuron, best[1]))
                continue
            if role in GENERATIVE and not room:
                continue
            if role in GENERATIVE and memory["fired"] == 0:
                out.append((recovery * (1.0 - 0.1 * GENERATIVE.index(role)), neuron, None))
                continue
            fresh = [event for event in self.state["events"][memory["seen_events"]:]
                     if event["neuron"] != neuron and event["idea"] in self.field.ideas
                     and (role != HUB or event["event"] in verdict_events)]
            present = [event for event in fresh if rho[self.field.ideas.index(event["idea"]), c] >= PRESENT]
            if not present or (role == HUB and len({event["neuron"] for event in present}) < 2):
                continue  # the hub integrates once at least two other neurons have judged
            value = max(float(churn[k, c] + 0.1 * rho[k, c])
                        for k in {self.field.ideas.index(event["idea"]) for event in present})
            out.append((recovery * value, neuron, None))
        out.sort(key=lambda row: -row[0])
        return [row for row in out if row[0] > THRESHOLD]

    # thinking (worker threads; reads only the job snapshot) --------------------

    def _think(self, job: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return self._think_as(job)
        except BrainSilence as silence:
            return {"silent": str(silence)}
        except RuntimeError as failure:  # the server refused the request; the act is recorded silent
            return {"silent": str(failure)}

    def _think_as(self, job: Mapping[str, Any]) -> dict[str, Any]:
        role, context = job["role"], job["context"]

        def ask(task: str, schema: Mapping[str, Any], temperature: float, tokens: int = 1600) -> dict[str, Any]:
            return self.brain.ask(SYSTEM, context + task, schema, temperature=temperature, max_tokens=tokens)

        def search(query: Any) -> list[dict[str, Any]]:
            return self.library.search(str(query or "")) if self.library else []

        def compute(task: str, temperature: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            """Write a script, run it, and fix it from its own error up to REPAIRS times."""

            calls, runs = [], []
            prompt = context + task + CODE_RULES
            for _ in range(1 + REPAIRS):
                reply = self.brain.write(SYSTEM_CODE, prompt, temperature=temperature)
                calls.append(reply)
                run = self.python(_script(reply["text"]))
                runs.append(run)
                if not run.get("ran") or run.get("exit") == 0:
                    break
                prompt = (context + task + f"\nYOUR SCRIPT:\n```python\n{run['code']}\n```\nIT FAILED:\n"
                          f"{run['output'][-1500:]}\n\nTASK: fix the script so it runs cleanly and does the same job."
                          + CODE_RULES)
            return calls, runs

        if role in ("intuition", "analogist"):
            lead = "reflection" if role == "intuition" else "analogy"
            task = ("\nTASK: sense where the answer lies. reflection: what you sense in the question, the present "
                    "ideas, and their verdicts." if role == "intuition" else
                    "\nTASK: find a structure from another field with the same shape as this question. analogy: "
                    "that structure and what it teaches here.")
            reply = ask(task + PROPOSE, _opening(lead), 0.8)
            return {"calls": [reply], "answer": reply["answer"]}
        if role == "imaginer":
            calls, runs = compute("\nTASK: build one small numerical experiment that shows what would happen. Open the "
                                  "script with comments saying what it varies and what it watches.", 0.6)
            second = ask("\n" + _evidence(runs[-1], []) + "TASK: observation: what the output shows." + PROPOSE,
                         _opening("observation"), 0.5)
            return {"calls": calls + [second], "computation": runs[-1], "earlier_attempts": runs[:-1],
                    "answer": second["answer"]}
        if role == "explorer":
            first = ask("\nTASK: surprise: the most surprising tension in the present ideas and verdicts, or a place "
                        "where the theory is silent. library_query: words to search the CassiTheory library for "
                        "what bears on it.", _object(surprise=_TEXT, library_query=_TEXT), 0.7)
            hits = search(first["answer"].get("library_query"))
            passages = "\n\n".join(f"[{h['path']} :: {h['title']}]\n{h['text']}" for h in hits) or "(no passages)"
            second = ask(f"\nYOUR SURPRISE: {first['answer'].get('surprise')}\nLIBRARY PASSAGES:\n{passages}\n\n"
                         "TASK: finding: what the passages settle or open." + PROPOSE, _opening("finding"), 0.6)
            return {"calls": [first, second], "library": hits, "answer": second["answer"]}
        if role in CONSOLIDATING:
            focus = f"\nIDEA UNDER YOUR EXAMINATION: {job['idea']}: {job['statement']}\n{job['contest']}"
            hits: list[dict[str, Any]] = []
            if role == "mathematician":
                calls, runs = compute(focus + "TASK: decide this idea by derivation and computation. Open the script "
                                      "with comments stating the idea as an exact mathematical claim and how the "
                                      "script decides it.", 0.2)
                step, rule = "", " proven only when your script ran cleanly and its output decides the claim."
            else:
                first = ask(focus + "TASK: attack: the strongest way this could fail. library_query: words to search "
                            "the CassiTheory registry for conflicting or supporting statements. "
                            "counterexample_search: a computation that could expose the failure, or \"\" when the "
                            "library settles it.",
                            _object(attack=_TEXT, library_query=_TEXT, counterexample_search=_TEXT), 0.3)
                hits = search(first["answer"].get("library_query"))
                hunt = str(first["answer"].get("counterexample_search") or "").strip()
                calls, runs = compute(focus + f"YOUR ATTACK: {first['answer'].get('attack')}\nTASK: hunt the "
                                      f"counterexample: {hunt}", 0.3) if hunt else ([], [{"ran": False}])
                calls = [first] + calls
                step, rule = f"YOUR ATTACK: {_dump(first['answer'])}\n\n", ""
            verdicts = VERDICTS[role]
            second = ask(focus + step + _evidence(runs[-1], hits) +
                         "TASK: decide from the evidence. reason: cite the printed numbers or passages you rely on. "
                         f"verdict: one of {list(verdicts)};{rule} strength 0..1. same_claim: ids of the other ideas "
                         "at your site asserting this very claim, which your verdict decides too; leave out ideas "
                         "that contradict it or only share its topic; else []. "
                         "replacement: when the idea fails, a corrected or sharper claim, or the id of an idea at "
                         "your site that already states it; else \"\".",
                         _object(reason=_TEXT, verdict={"type": "string", "enum": list(verdicts)},
                                 strength=_NUMBER, same_claim=_IDS, replacement=_TEXT), 0.1)
            return {"calls": calls + [second], "computation": runs[-1], "earlier_attempts": runs[:-1],
                    "library": hits, "answer": second["answer"]}
        reply = ask("\nTASK: state_of_mind: what the brain currently believes and what remains open. endorse: ideas "
                    "the evidence supports, strength 0..1. release: ids of superseded or broken ideas. synthesis: "
                    "when compatible supported ideas join into a claim no present idea already states, statement is "
                    "their union as one checkable claim and combines lists their ids; otherwise leave statement "
                    "empty.",
                    _object(state_of_mind=_TEXT, endorse=_WEIGHTS, release=_IDS,
                            synthesis=_object(statement=_TEXT, combines=_IDS, why=_TEXT)), 0.3)
        return {"calls": [reply], "answer": reply["answer"]}

    # applying a finished act (main thread) -------------------------------------

    def _deposit(self, idea: str, neuron: str, event: str, *, yang: float = 0.0, yin: float = 0.0) -> dict[str, Any]:
        self.field.deposit(idea, neuron, yang=yang, yin=yin)
        self.state["events"].append({"neuron": neuron, "idea": idea, "event": event})
        return {event: idea, **({"yang": round(yang, 4)} if yang else {}), **({"yin": round(yin, 4)} if yin else {})}

    def _drain(self, idea: str, neuron: str, event: str, fraction: float) -> dict[str, Any]:
        self.field.drain(idea, neuron, fraction)
        self.state["events"].append({"neuron": neuron, "idea": idea, "event": event})
        return {event: idea, "drain": round(fraction, 4)}

    def _open(self, neuron: str, answer: Mapping[str, Any]) -> list[dict[str, Any]]:
        effects = []
        for proposal in (answer.get("proposals") or [])[:2]:
            if not isinstance(proposal, Mapping):
                continue
            parent = str(proposal.get("refines") or "")
            idea = self._new_idea(proposal.get("statement"), neuron=neuron, kind="conjecture",
                                  parents=[parent] if parent in self.state["ideas"] else [], why=proposal.get("why"))
            if idea:
                amount = self.amplitude * (0.5 + _unit(proposal.get("confidence"), 0.6))
                self.field.deposit(idea, neuron, yang=amount)
                effects.append({"new": idea, "yang": round(amount, 4)})
        for item in (answer.get("promote") or [])[:3]:
            if isinstance(item, Mapping) and item.get("idea") in self.field.ideas:
                effects.append(self._deposit(item["idea"], neuron, "promoted",
                                             yang=0.5 * self.amplitude * _unit(item.get("strength"), 0.5)))
        for idea in (answer.get("release") or [])[:4]:
            if idea in self.field.ideas:
                effects.append(self._drain(idea, neuron, "released", 0.5))
        return effects

    def _judge(self, idea: str, neuron: str, verdict: str, strength: float) -> dict[str, Any]:
        """One verdict's effect on the field at the judging neuron's own site."""

        if verdict in POSITIVE:
            return self._deposit(idea, neuron, verdict,
                                 yin=self.amplitude * strength * (1.5 if verdict == "proven" else 1.0))
        if verdict in NEGATIVE:
            return self._drain(idea, neuron, verdict, 0.8)
        if verdict == "weakened":
            return self._drain(idea, neuron, verdict, 0.3 * strength + 0.1)
        self.state["events"].append({"neuron": neuron, "idea": idea, "event": verdict})
        return {verdict: idea}

    def _decide(self, neuron: str, idea: str, answer: Mapping[str, Any], computation: Mapping[str, Any],
                perceived: Collection[str]) -> tuple[str | None, list[dict[str, Any]]]:
        """Apply a verdict to the examined idea and to every perceived idea making the same claim.

        Association fills in only ideas this neuron has not judged, and a judgment it holds stays; examining
        an idea replaces the neuron's earlier verdict on it.
        """

        role = role_of(neuron)
        verdict = claimed = answer.get("verdict")
        if verdict not in VERDICTS[role]:
            return None, [{"silent": True}]
        if verdict == "proven" and computation.get("exit") != 0:
            verdict = "supported"  # a proof stands only on a script that ran cleanly
        strength = _unit(answer.get("strength"), 0.5)
        effects: list[dict[str, Any]] = [{"claimed": claimed}] if claimed != verdict else []
        effects.append(self._judge(idea, neuron, verdict, strength))
        before = self.state["ideas"][idea]["verdicts"].get(neuron)
        if before:  # examining the idea itself replaces a verdict that came by association
            effects.append({"revises": before["verdict"]})
        record = {"verdict": verdict, **({"claimed": claimed} if claimed != verdict else {}), "strength": strength,
                  "reason": str(answer.get("reason") or "")[:1200], "act": self.state["acts"] + 1,
                  **({"revises": before["verdict"]} if before else {})}
        self.state["ideas"][idea]["verdicts"][neuron] = record
        judged = self.state["neurons"][neuron]["judged"]
        replacement = str(answer.get("replacement") or "").strip()
        same = list(dict.fromkeys(answer.get("same_claim") or []))
        if replacement in same:  # the better claim cannot share the failed one: the answer confused its lists
            same = []
        for other in same:
            if other == idea or other not in perceived or other not in self.field.ideas:
                continue
            verdicts = self.state["ideas"][other]["verdicts"]
            held = verdicts.get(neuron, {}).get("verdict")
            if held:
                if held != verdict:
                    effects.append({"kept": other, "held": held})
                continue
            effects.append({**self._judge(other, neuron, verdict, strength), "via": idea})
            verdicts[neuron] = {**record, "via": idea}
            if other not in judged:  # a silent act may have listed it without a verdict
                judged.append(other)
        if replacement and verdict not in POSITIVE:
            if _IDEA_ID.fullmatch(replacement):  # an idea the brain already holds states the better claim
                if replacement != idea and replacement in perceived and replacement in self.field.ideas:
                    effects.append(self._deposit(replacement, neuron, "backed", yang=0.5 * self.amplitude))
            else:
                kind = "correction" if role == "mathematician" else "objection"
                new = self._new_idea(replacement, neuron=neuron, kind=kind, parents=[idea], why=answer.get("reason"))
                if new:
                    self.field.deposit(new, neuron, yang=self.amplitude)
                    effects.append({"new": new, "yang": round(self.amplitude, 4)})
        return verdict, effects

    def _integrate(self, neuron: str, answer: Mapping[str, Any]) -> list[dict[str, Any]]:
        effects = []
        for item in (answer.get("endorse") or [])[:3]:
            idea = item.get("idea") if isinstance(item, Mapping) else None
            if idea in self.field.ideas and any(
                    v["verdict"] in POSITIVE for v in self.state["ideas"][idea]["verdicts"].values()):
                effects.append(self._deposit(idea, neuron, "endorsed",
                                             yin=0.5 * self.amplitude * _unit(item.get("strength"), 0.5)))
        for idea in (answer.get("release") or [])[:4]:
            if idea in self.field.ideas:
                effects.append(self._drain(idea, neuron, "released", 0.5))
        synthesis = answer.get("synthesis") if isinstance(answer.get("synthesis"), Mapping) else {}
        combines = [i for i in synthesis.get("combines") or [] if i in self.state["ideas"]]
        if len(combines) >= 2:
            new = self._new_idea(synthesis.get("statement"), neuron=neuron, kind="synthesis", parents=combines,
                                 why=synthesis.get("why"))
            if new:
                self.field.deposit(new, neuron, yang=self.amplitude)
                effects.append({"new": new, "yang": round(self.amplitude, 4)})
        if answer.get("state_of_mind"):
            self.state["mind"] = {"act": self.state["acts"] + 1, "text": str(answer["state_of_mind"])}
        return effects

    def _readout(self) -> dict[str, Any]:
        readout = self.field.readout()
        rho = self.field.ey + self.field.ei
        readout["sites"] = {idea: [round(float(x), 4) for x in rho[k]]
                            for k, idea in enumerate(self.field.ideas) if rho[k].max() >= PRESENT}
        return readout

    def _apply(self, job: Mapping[str, Any], result: Mapping[str, Any], keep: Collection[str] = ()) -> dict[str, Any]:
        neuron, role, focus = job["neuron"], job["role"], job["idea"]
        memory = self.state["neurons"][neuron]
        answer = result.get("answer") or {}
        verdict = None
        if "silent" in result:
            effects: list[dict[str, Any]] = [{"silent": True}]
        elif role in GENERATIVE:
            effects = self._open(neuron, answer)
        elif role in CONSOLIDATING:
            verdict, effects = self._decide(neuron, focus, answer, result.get("computation") or {}, job["perceived"])
        else:
            effects = self._integrate(neuron, answer)
        if role in CONSOLIDATING:
            if focus not in memory["judged"]:  # a contested idea is judged twice
                memory["judged"].append(focus)
        else:
            memory["seen_events"] = job["seen"]
        memory["fired"] += 1
        memory["fired_at"] = self.field.time
        self.state["acts"] += 1
        self.field.breathe(BREATH)
        forgotten = self._forget(keep)
        record = {"kind": "act", "act": self.state["acts"], "neuron": neuron, "role": role, "idea": focus,
                  "priority": round(job["priority"], 6), "launched_at": job["launched_at"],
                  "perceived": job["perceived"], "verdict": verdict,
                  "effects": effects, **{k: v for k, v in result.items() if k != "answer"}, "answer": answer,
                  **({"forgotten": forgotten} if forgotten else {}), "field": self._readout()}
        self._record(record)
        self._save()
        return record

    def _forget(self, keep: Collection[str] = ()) -> list[str]:
        """Remove from the field every idea faded below perception at every site.

        The idea's record, verdicts, and lineage stay in the brain's memory; ``keep`` names ideas that
        neurons are still examining.
        """

        rho = self.field.ey + self.field.ei
        faded = [idea for k, idea in enumerate(self.field.ideas) if idea not in keep and rho[k].max() < PRESENT]
        for idea in faded:
            self.field.forget(idea)
            self.state["ideas"][idea]["forgotten"] = self.state["acts"]
        return faded

    def _rest(self) -> dict[str, Any]:
        """Breathe without firing until some neuron owes work again, at most MAX_REST breaths.

        Ideas fade out of working memory and fired neurons recover, so a brain whose memory is full, or
        whose neurons have nothing left to judge, makes room and wakes on its own.
        """

        live = [idea for idea in self.field.ideas if self._live(idea)]
        breaths, forgotten, ranked = 0, [], self.candidates()
        while not ranked and breaths < MAX_REST:
            self.field.breathe(BREATH)
            breaths += 1
            forgotten += self._forget()
            ranked = self.candidates()
        record = {"kind": "rest", "breaths": breaths, "woke": ranked[0][1] if ranked else None,
                  "faded": [idea for idea in live if idea not in self.field.ideas or not self._live(idea)],
                  "forgotten": forgotten, "field": self._readout()}
        self._record(record)
        self._save()
        return record

    def run(self, acts: int, *, parallel: int = 1,
            report: Callable[[Mapping[str, Any]], None] = lambda record: None) -> str:
        """Let the field fire neurons, up to ``parallel`` at once, until ``acts`` acts finish or it rests.

        When no neuron owes work and none is thinking, the brain rests (``_rest``) and carries on once a
        neuron wakes; it stops at rest only when MAX_REST breaths wake nobody. When the brain server stops
        answering, the neurons already thinking finish, the run saves with status ``waiting-for-brain``,
        and ``BrainUnavailable`` is raised; resume continues from there.
        """

        parallel = max(1, int(parallel))
        busy: dict[str, str | None] = {}
        jobs: dict[concurrent.futures.Future, dict[str, Any]] = {}
        launched = 0
        lost: BrainUnavailable | None = None
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
            while True:
                while lost is None and launched < acts and len(jobs) < parallel:
                    ranked = self.candidates(busy)
                    if not ranked:
                        break
                    priority, neuron, idea = ranked[0]
                    view = self._view(neuron)
                    job = {"neuron": neuron, "role": role_of(neuron), "idea": idea, "priority": priority,
                           "launched_at": round(self.field.time, 6), "seen": len(self.state["events"]),
                           "perceived": [row["id"] for row in view], "context": self._context(neuron, view),
                           "statement": self.state["ideas"][idea]["statement"] if idea else None,
                           "contest": self._contest_note(neuron, idea)}
                    busy[neuron] = idea
                    jobs[pool.submit(self._think, job)] = job
                    launched += 1
                if not jobs:
                    if lost is None and launched < acts:
                        rest = self._rest()
                        report(rest)
                        if rest["woke"]:
                            continue
                    break
                done, _ = concurrent.futures.wait(jobs, return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    job = jobs.pop(future)
                    busy.pop(job["neuron"], None)
                    try:
                        result = future.result()
                    except BrainUnavailable as failure:  # this neuron's act is dropped; it fires again on resume
                        lost = failure
                        continue
                    keep = {i for other in jobs.values() for i in (other["idea"], *other["perceived"]) if i}
                    report(self._apply(job, result, keep))
        if lost is not None:
            self.state["status"] = "waiting-for-brain"
            self._save()
            raise lost
        self.state["status"] = "thinking" if self.candidates() else "at-rest"
        self._save()
        return self.state["status"]

    # conclusion ----------------------------------------------------------------

    def acts(self) -> list[dict[str, Any]]:
        path = self.home / "records.jsonl"
        if not path.exists():
            return []
        records = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
        return [record for record in records if record.get("kind") == "act"]

    def conclusion(self, top: int = 8) -> dict[str, Any]:
        resonance = self.field.resonance()
        ranked = sorted(zip(self.field.ideas, resonance.tolist()), key=lambda row: -row[1])
        first = ranked[0][1] if ranked else 0.0
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        leads = [max(a["field"]["resonance"].items(), key=lambda kv: kv[1])[0]
                 for a in self.acts() if a["field"]["resonance"]]
        return {
            "status": self.state["status"], "acts": self.state["acts"],
            "shape": "settled" if first > 0.0 and first >= PHI * second else ("split" if first > 0.0 else "empty"),
            "lead_changes": sum(1 for a, b in zip(leads, leads[1:]) if a != b),
            "rhythm": " ".join(a["neuron"] for a in self.acts()),
            "mind": self.state["mind"],
            "ranking": [{"idea": idea, "resonance": round(r, 4),
                         **{k: self.state["ideas"][idea][k] for k in ("statement", "kind", "by", "parents")},
                         "verdicts": {n: v["verdict"] for n, v in self.state["ideas"][idea]["verdicts"].items()}}
                        for idea, r in ranked[:top]],
        }


def _print_record(record: Mapping[str, Any]) -> None:
    field = record["field"]
    lead = max(field["resonance"].items(), key=lambda kv: kv[1]) if field["resonance"] else ("-", 0.0)
    tail = f"lead={lead[0]} R={lead[1]:.3f} churn={field['max_churn']:.3f}"
    forgot = f"; forgot {', '.join(record['forgotten'])}" if record.get("forgotten") else ""
    if record["kind"] == "rest":
        faded = ", ".join(record["faded"]) or "nothing"
        woke = f"woke {record['woke']}" if record["woke"] else "nobody woke"
        print(f"[rest] {record['breaths']} breaths, faded {faded}{forgot}; {woke}  {tail}", flush=True)
        return
    flows = sum(1 for e in record["effects"] if "via" in e)
    after = [f"{k}={e[k]}" for e in record["effects"] for k in ("revises", "new", "backed", "kept") if k in e]
    detail = (record["verdict"] + (f" +{flows} same claim" if flows else "") + "".join(f", {a}" for a in after)
              if record.get("verdict") else
              ", ".join(f"{k}={v}" for e in record["effects"] for k, v in e.items() if k not in ("yang", "yin", "drain")))
    print(f"[{record['act']:>3}] {record['neuron']:<16} {record['idea'] or '':<4} {detail[:40]:<40} {tail}{forgot}",
          flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("think", "resume", "status"):
        command = sub.add_parser(name)
        command.add_argument("--home", type=Path, required=True)
        if name != "status":
            command.add_argument("--acts", type=int, default=48)
            command.add_argument("--brain", default=DEFAULT_BRAIN)
            command.add_argument("--parallel", type=int, default=0,
                                 help="neurons thinking at once (default: the brain's slot count)")
        if name == "think":
            command.add_argument("--question", required=True)
            command.add_argument("--layout", choices=("cortex", "ring"), default="cortex")
            command.add_argument("--size", type=int, default=8, help="loop neurons in the cortex layout")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if args.command == "status":
        print(_dump(ThinkingBrain(args.home).conclusion()))
        return 0
    library = Library()
    try:
        brain = LiveBrain(args.brain)
    except BrainUnavailable as lost:
        print(lost, file=sys.stderr)
        return 3
    parallel = args.parallel or brain.slots
    if args.command == "think":
        organism = ThinkingBrain.create(args.home, args.question, layout_name=args.layout, size=args.size,
                                        library=library, brain=brain)
    else:
        organism = ThinkingBrain(args.home, brain=brain, library=library)
    started = time.perf_counter()
    try:
        organism.run(args.acts, parallel=parallel, report=_print_record)
    except BrainUnavailable as lost:
        print(f"{lost}\npaused at act {organism.state['acts']}; `resume` continues from there", file=sys.stderr)
        return 3
    print(f"{organism.state['acts']} acts in {time.perf_counter() - started:.0f} s, {parallel} neurons at once")
    print(_dump(organism.conclusion()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
