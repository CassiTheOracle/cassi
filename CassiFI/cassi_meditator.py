#!/usr/bin/env python3
"""The tiny meditator: a field-owned mind practicing in a living Yang/Yin body.

Its mind is ``meditator/mind.py``, compiled into its own LearningComputer and
kept by a FieldIntelligenceOwner. What it has learned, its habits, the
practices it has refined and its journal are that program's module globals:
left in the field when a sit completes and handed to the next sit.

Its body is the CassiCosmos mind engine (line-JSON on 7599): a 32^3 two-fluid
field. A breath is one natural balance cycle of that field, 80 PDE steps
sensed at ten moments. Each sit begins with the day's mind arising (a
scattered field), and thoughts keep arising during the sit. Each breath the
host turns the field into a felt sense, hands it to the mind, and carries out
the practice the mind chooses at every moment of the next breath.

    python cassi_meditator.py sit --breaths 64 --face
    python cassi_meditator.py face
    python cassi_meditator.py status
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import random
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_field_owner import FieldIntelligenceOwner
from programs.python.kernel import REGIONAL_KERNEL_NAME
from programs.python.kernel import regional_state as python_regional_state
from programs.python.runtime import RUNTIME_SCHEMA, read_global

HERE = Path(__file__).resolve().parent
MIND_SOURCE = HERE / "meditator" / "mind.py"
FACE_PAGE = HERE / "meditator" / "face.html"
DEFAULT_HOME = HERE / ".cassi" / "meditator"
COMPUTER_ID = "meditator"
PROFILE = {"mode_count": 262_144, "max_native_work": 64, "max_steps": 1_000_000}
LIMITS = {"max_operations": 1_000_000, "max_events": 1_000_000, "max_heap_objects": 65_536}
QUANTA = 2048
ROUND = 12  # breaths per round: each round is one bounded task in the mind's field computer

PHI = (1.0 + math.sqrt(5.0)) / 2.0
GOLDEN = np.array([PHI, 1.0]) / math.sqrt(1.0 + PHI * PHI)  # the balanced direction EY = φ·EI
MOMENTS = 10  # moments felt per breath
MOMENT_STEPS = 8  # PDE steps per moment; one breath = one natural balance cycle
BRIGHT = 8  # cells a practice attends to
SPIRAL_MODES = tuple(m for m in range(-8, 9) if m != 0)
TRACE = 160
CONTEXTS = ("scattered", "settled", "stirring", "flowing")


# ── body ────────────────────────────────────────────────────────────────


class Body:
    """Line-JSON client for the mind engine that is the meditator's body."""

    def __init__(self, host: str, port: int, timeout: float = 60.0) -> None:
        self._socket = socket.create_connection((host, port), timeout=timeout)
        self._socket.settimeout(timeout)
        self._reader = self._socket.makefile("rb")

    def request(self, message: Mapping[str, Any]) -> dict[str, Any]:
        self._socket.sendall(json.dumps(message).encode("utf-8") + b"\n")
        line = self._reader.readline()
        if not line:
            raise ConnectionError("the mind engine closed the connection")
        reply = json.loads(line)
        if reply.get("ok") is not True:
            raise RuntimeError(f"the mind engine refused {message.get('cmd')}: {reply}")
        return reply

    def feel(self) -> tuple[np.ndarray, np.ndarray]:
        reply = self.request({"cmd": "readout"})
        return _floats(reply["ey_b64"]), _floats(reply["ei_b64"])

    def deposit(self, charges: Sequence[Mapping[str, float]]) -> None:
        for charge in charges:
            self.request({"cmd": "deposit", **charge})

    def step(self, count: int) -> None:
        self.request({"cmd": "step", "n": int(count)})

    def clear(self) -> None:
        self.request({"cmd": "clear"})

    def close(self) -> None:
        try:
            self._reader.close()
            self._socket.close()
        except OSError:
            pass


def _floats(payload: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(payload), dtype="<f4").astype(np.float64)


def side(size: int) -> int:
    n = round(size ** (1.0 / 3.0))
    if n ** 3 != size:
        raise ValueError(f"field of {size} cells is not a cube")
    return n


def place(cell: int, n: int) -> tuple[float, float, float]:
    """Physical centre of a flat cell index (the engine's x-major layout)."""

    gx, rest = divmod(int(cell), n * n)
    gy, gz = divmod(rest, n)
    return 2.0 * gx / n - 1.0, 2.0 * gy / n - 1.0, 2.0 * gz / n - 1.0


def scattered_charge(rng: random.Random) -> dict[str, float]:
    """One arising: a Yang/Yin charge at a random place, the size of the day's thoughts."""

    magnitude = rng.uniform(0.3, 1.0)
    angle = rng.uniform(0.0, 2.0 * math.pi)
    return {
        "x": rng.uniform(-0.8, 0.8),
        "y": rng.uniform(-0.8, 0.8),
        "z": rng.uniform(-0.8, 0.8),
        "cy": magnitude * math.cos(angle),
        "ci": magnitude * math.sin(angle),
        "sigma": rng.choice((0.5, 1.0, 1.5, 2.0)),
    }


def days_mind(rng: random.Random) -> list[dict[str, float]]:
    return [scattered_charge(rng) for _ in range(10)]


def thought(rng: random.Random) -> list[dict[str, float]]:
    return [scattered_charge(rng) for _ in range(rng.randint(1, 3))]


# ── senses ──────────────────────────────────────────────────────────────


def balance(ey: np.ndarray, ei: np.ndarray) -> float:
    """1 when every cell sits on EY = φ·EI, 0.5 when Yang and Yin are unrelated."""

    scale = float(np.sum(ey * ey + PHI * PHI * ei * ei))
    if scale <= 1e-30:
        return 0.5
    eps = ey - PHI * ei
    return 1.0 - 0.5 * float(np.sum(eps * eps)) / scale


def helix_order(ey: np.ndarray, ei: np.ndarray, n: int) -> float:
    """Strongest nonzero helical order of the phase, weighted by power, on any axis."""

    z = ey + 1j * ei
    power = float(np.sum(ey * ey + ei * ei))
    if power <= 1e-30:
        return 0.0
    field = (np.abs(z) * z).reshape((n, n, n))
    best = 0.0
    for axis in range(3):
        profile = field.sum(axis=tuple(a for a in range(3) if a != axis))
        spectrum = np.abs(np.fft.fft(profile))
        best = max(best, max(float(spectrum[m % n]) for m in SPIRAL_MODES))
    return best / power


class SpiralSense:
    """Helical order and its margin over spatially shuffled and phase-scrambled copies."""

    def __init__(self, n: int, seed: int) -> None:
        self.n = n
        shape = (n, n, n)
        self.permutation = np.random.default_rng(seed).permutation(n ** 3)
        self.phases = [
            np.exp(1j * np.angle(np.fft.rfftn(np.random.default_rng(seed + k).normal(size=shape))))
            for k in (1, 2)
        ]

    def __call__(self, ey: np.ndarray, ei: np.ndarray) -> tuple[float, float]:
        live = helix_order(ey, ei, self.n)
        shuffled = helix_order(ey[self.permutation], ei[self.permutation], self.n)
        scrambled = helix_order(self._scramble(ey, 0), self._scramble(ei, 1), self.n)
        return live, live - max(shuffled, scrambled)

    def _scramble(self, values: np.ndarray, which: int) -> np.ndarray:
        cube = values.reshape((self.n,) * 3)
        rebuilt = np.fft.irfftn(np.abs(np.fft.rfftn(cube)) * self.phases[which], s=cube.shape, axes=(0, 1, 2)).real
        spread = float(np.std(rebuilt))
        mean = float(np.mean(cube))
        if spread <= 0.0:
            return np.full(values.size, mean)
        return ((rebuilt - rebuilt.mean()) * (float(np.std(cube)) / spread) + mean).ravel()


def view(ey: np.ndarray, ei: np.ndarray, n: int) -> dict[str, Any]:
    """The field seen from above: at each (x, y) the brightest cell along z, with an eye's compression."""

    q = (ey * ey + ei * ei).reshape((n, n, n))
    deepest = np.argmax(q, axis=2)[..., None]
    top_y = np.take_along_axis(ey.reshape((n, n, n)), deepest, axis=2)[..., 0]
    top_i = np.take_along_axis(ei.reshape((n, n, n)), deepest, axis=2)[..., 0]
    scale = float(np.sqrt(q.max())) or 1.0

    def seen(values: np.ndarray) -> list[float]:
        values = values / scale
        return [round(float(v), 3) for v in (np.sign(values) * np.abs(values) ** 0.4).ravel()]

    return {"n": n, "ey": seen(top_y), "ei": seen(top_i)}


# ── practices (the body's motor codec) ─────────────────────────────────


def practice_charges(
    practice: str, strength: float, ey: np.ndarray, ei: np.ndarray, n: int, motor: dict[str, float]
) -> tuple[list[dict[str, float]], float]:
    """Charges one moment of a practice deposits, and the effort in units of the field's brightness."""

    if practice == "still" or strength <= 0.0:
        return [], 0.0
    q = ey * ey + ei * ei
    bright = np.argpartition(q, -BRIGHT)[-BRIGHT:]
    bright = bright[np.argsort(-q[bright])]
    unit = math.sqrt(float(q[bright].mean()))
    if unit <= 1e-12:
        return [], 0.0
    charges: list[dict[str, float]] = []
    if practice == "balance":
        # let go of imbalance: move the brightest cells toward EY = φ·EI
        for cell in bright:
            eps = float(ey[cell] - PHI * ei[cell])
            x, y, z = place(cell, n)
            charges.append({"x": x, "y": y, "z": z, "cy": -strength * eps / (1 + PHI * PHI),
                            "ci": strength * PHI * eps / (1 + PHI * PHI), "sigma": 1.0})
    elif practice == "golden":
        # transform imbalance: turn the brightest cells onto the golden line, keeping their intensity
        for cell in bright:
            current = np.array([ey[cell], ei[cell]])
            along = float(current @ GOLDEN)
            target = math.copysign(float(np.hypot(*current)), along if along else 1.0) * GOLDEN
            push = strength * (target - current)
            x, y, z = place(cell, n)
            charges.append({"x": x, "y": y, "z": z, "cy": float(push[0]), "ci": float(push[1]), "sigma": 1.0})
    elif practice == "circulate":
        # a spiral rising through the central channel of the brightest cell
        x0, y0, _ = place(bright[0], n)
        turn = motor.get("circulate", 0.0)
        for j in range(8):
            angle = 2.0 * math.pi * j / 8.0 + turn
            charges.append({"x": x0, "y": y0, "z": -0.875 + 0.25 * j,
                            "cy": 0.25 * strength * unit * math.cos(angle),
                            "ci": 0.25 * strength * unit * math.sin(angle), "sigma": 1.0})
        motor["circulate"] = (turn + 2.0 * math.pi / (PHI * MOMENTS)) % (2.0 * math.pi)
    elif practice == "center":
        # gather at the heart of the field, on the golden ratio
        heart = (n // 2) * n * n + (n // 2) * n + n // 2
        along = float(ey[heart] * GOLDEN[0] + ei[heart] * GOLDEN[1])
        amount = math.copysign(0.5 * strength * unit, along if along else 1.0)
        charges.append({"x": 0.0, "y": 0.0, "z": 0.0, "cy": amount * GOLDEN[0], "ci": amount * GOLDEN[1],
                        "sigma": 2.0})
    elif practice == "listen":
        # follow the strongest current one cell downstream and join it, on the golden ratio
        yang = ey.reshape((n, n, n))
        yin = ei.reshape((n, n, n))
        flow = [
            yang * (np.roll(yin, -1, a) - np.roll(yin, 1, a)) * 0.5
            - yin * (np.roll(yang, -1, a) - np.roll(yang, 1, a)) * 0.5
            for a in range(3)
        ]
        strongest = int(np.argmax(flow[0] ** 2 + flow[1] ** 2 + flow[2] ** 2))
        direction = np.array([f.flat[strongest] for f in flow])
        direction = np.rint(direction / (np.linalg.norm(direction) + 1e-30)).astype(int)
        gx, rest = divmod(strongest, n * n)
        gy, gz = divmod(rest, n)
        cell = ((gx + direction[0]) % n) * n * n + ((gy + direction[1]) % n) * n + (gz + direction[2]) % n
        along = float(ey[cell] * GOLDEN[0] + ei[cell] * GOLDEN[1])
        amount = math.copysign(0.5 * strength * unit, along if along else 1.0)
        x, y, z = place(cell, n)
        charges.append({"x": x, "y": y, "z": z, "cy": amount * GOLDEN[0], "ci": amount * GOLDEN[1], "sigma": 1.0})
    else:
        raise ValueError(f"unknown practice {practice!r}")
    effort = sum(abs(c["cy"]) + abs(c["ci"]) for c in charges) / unit
    return charges, effort


class Living:
    """One sit's body: the field, the thoughts that arise in it, and the practice being done."""

    def __init__(self, body: Body, rng: random.Random, seed: int, thoughts: float) -> None:
        self.body = body
        self.rng = rng
        self.thoughts = thoughts
        self.motor: dict[str, float] = {}
        body.clear()
        body.deposit(days_mind(rng))
        body.step(1)
        self.ey, self.ei = body.feel()
        self.n = side(self.ey.size)
        self.spiral = SpiralSense(self.n, seed)

    def breathe(self, practice: str, strength: float, *, quiet: bool = False) -> dict[str, Any]:
        arose = not quiet and self.rng.random() < self.thoughts
        if arose:
            self.body.deposit(thought(self.rng))
        effort = 0.0
        balances: list[float] = []
        orders: list[float] = []
        margins: list[float] = []
        for _ in range(MOMENTS):
            charges, spent = practice_charges(practice, strength, self.ey, self.ei, self.n, self.motor)
            self.body.deposit(charges)
            effort += spent
            self.body.step(MOMENT_STEPS)
            self.ey, self.ei = self.body.feel()
            balances.append(balance(self.ey, self.ei))
            order, margin = self.spiral(self.ey, self.ei)
            orders.append(order)
            margins.append(margin)
        felt = {
            "balance": round(float(np.mean(balances)), 6),
            "steadiness": round(1.0 - (max(balances) - min(balances)), 6),
            "spiral": round(float(np.mean(orders)), 6),
            "spiral_margin": round(float(np.mean(margins)), 6),
            "effort": round(effort, 6),
        }
        power = float(np.mean(self.ey * self.ey + self.ei * self.ei))
        return {"felt": felt, "thought": arose, "power": power, "view": view(self.ey, self.ei, self.n)}


# ── mind (the meditator's field computer) ──────────────────────────────


class MindError(RuntimeError):
    pass


class Mind:
    """Drives the meditator's program in its own field computer, one breath at a time."""

    def __init__(self, owner: FieldIntelligenceOwner) -> None:
        self.owner = owner
        self.session = f"{time.time_ns():x}"
        self.count = 0
        if self._computer() is None:
            self.owner.operate_computer(
                "meditator:configure", computer_id=COMPUTER_ID, action="configure", arguments={"profile": PROFILE}
            )

    def _computer(self) -> Any:
        return next((row for row in self.owner.state.computers if row.computer_id == COMPUTER_ID), None)

    def _operation(self, kind: str) -> str:
        self.count += 1
        return f"meditator:{self.session}:{self.count}:{kind}"

    def task(self) -> Mapping[str, Any] | None:
        row = self._computer()
        if row is None:
            return None
        try:
            task = row.named_value("task")
        except Exception:
            return None
        if not isinstance(task, Mapping) or task.get("schema") != RUNTIME_SCHEMA:
            return None
        return task

    def memory(self) -> Any:
        task = self.task()
        if task is None or task.get("phase") != "completed":
            return None
        try:
            return read_global(task, "memory")
        except RuntimeError:
            return None

    def instructions(self) -> int:
        task = self.task()
        return int(task["ledger"]["instructions"]) if task else 0

    def interrupted(self) -> bool:
        task = self.task()
        return task is not None and task.get("phase") not in ("completed", "faulted", "cancelled")

    def request(self) -> tuple[str, str, Any] | None:
        """Run the program until it asks the body for something; None once the sit is complete."""

        for _ in range(4096):
            task = self.task()
            if task is None:
                return None
            phase = task.get("phase")
            if phase == "completed":
                return None
            if phase in ("faulted", "cancelled"):
                result = task.get("result") or {}
                raise MindError(f"the meditator's program {phase}: {result.get('exception')}")
            call = task["tasks"][task["active_task"]].get("pending_call")
            if call:
                operation = task["operations"][call["operation_id"]]
                name, payload = operation["inputs"][0], operation["inputs"][1]
                return call["operation_id"], name, json.loads(payload)
            advanced = self.owner.operate_computer(
                self._operation("advance"), computer_id=COMPUTER_ID, action="advance", arguments={"steps": QUANTA}
            )
            if advanced["receipt"].get("status") == "faulted":
                raise MindError(f"the meditator's field computer faulted: {advanced['receipt'].get('reason')}")
        raise MindError("the meditator's program did not reach its next breath")

    def answer(self, operation_id: str, value: Any) -> None:
        self.owner.operate_computer(
            self._operation("breath"),
            computer_id=COMPUTER_ID,
            action="invoke",
            arguments={
                "arguments": {"operation": "resume", "operation_id": operation_id, "value": value},
                "steps": QUANTA,
            },
        )

    def rest(self) -> None:
        """Let an unfinished sit end: every pending request is answered with the end of the sit."""

        while (pending := self.request()) is not None:
            self.answer(pending[0], None)

    def begin(self, memory: Any, closing: bool) -> tuple[str, str, Any]:
        source = MIND_SOURCE.read_text(encoding="utf-8")
        state = python_regional_state(
            source,
            mode="exec",
            filename="mind.py",
            inputs={"memory": memory, "closing": closing},
            capabilities=["effect-proposal"],
            limits=LIMITS,
        )
        self.owner.operate_computer(
            self._operation("sit"),
            computer_id=COMPUTER_ID,
            action="submit",
            arguments={"kernel": REGIONAL_KERNEL_NAME, "state": state, "arguments": {}, "steps": QUANTA},
        )
        pending = self.request()
        if pending is None or pending[1] != "arrive":
            raise MindError("the meditator did not arrive")
        return pending


# ── what it has learned, for people ────────────────────────────────────


def variant_label(variant: Mapping[str, Any]) -> str:
    names = {"still": "stillness", "balance": "balancing", "golden": "golden breath",
             "circulate": "circulation", "center": "centering", "listen": "listening"}
    name = names.get(variant["practice"], variant["practice"])
    if variant["practice"] == "still":
        return name
    return f"{name} {round(variant['strength'], 3)}"


def understanding(memory: Any) -> list[dict[str, Any]]:
    """For each felt state: the practice its experience favours and by how much over stillness."""

    if not isinstance(memory, Mapping):
        return []
    variants = memory.get("variants", [])
    rows = []
    for context in CONTEXTS:
        table = memory.get("table", {}).get(context, [])
        if not table:
            continue
        best = 0
        for index, row in enumerate(table):
            if row[0] >= 2 and row[1] > table[best][1]:
                best = index
        habit = memory.get("habits", {}).get(context)
        rows.append({
            "context": context,
            "best": variant_label(variants[best]),
            "practice": variants[best]["practice"],
            "gain": round(table[best][1] - table[0][1], 5),
            "samples": int(sum(row[0] for row in table)),
            "habit": variant_label(variants[habit]) if habit is not None else None,
        })
    return rows


# ── face ────────────────────────────────────────────────────────────────


class Face:
    """The face.json the page reads: written whole, replaced atomically."""

    def __init__(self, home: Path) -> None:
        self.path = home / "face.json"
        self.state: dict[str, Any] = {}

    def show(self, **values: Any) -> None:
        self.state.update(values)
        data = json.dumps(self.state, ensure_ascii=False, allow_nan=False).encode("utf-8")
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_bytes(data)
        for attempt in range(20):
            try:
                os.replace(temporary, self.path)
                return
            except PermissionError:
                time.sleep(0.02)
        raise PermissionError(f"could not update {self.path}")


def serve_face(home: Path, port: int) -> ThreadingHTTPServer:
    face_json = home / "face.json"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            route = self.path.split("?", 1)[0]
            if route in ("/", "/index.html"):
                body, kind = FACE_PAGE.read_bytes(), "text/html; charset=utf-8"
            elif route == "/face.json":
                try:
                    body, kind = face_json.read_bytes(), "application/json"
                except OSError:
                    body, kind = b"{}", "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, name="meditator-face", daemon=True).start()
    return server


# ── commands ────────────────────────────────────────────────────────────


def sit(args: argparse.Namespace) -> int:
    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    face = Face(home)
    server = serve_face(home, args.face_port) if args.face else None
    if server is not None:
        print(f"face: http://127.0.0.1:{args.face_port}/", flush=True)
    with FieldIntelligenceOwner(home / "mind") as owner:
        mind = Mind(owner)
        if mind.interrupted():
            mind.rest()
            print("an interrupted sit was brought to rest", flush=True)
        memory = mind.memory()
        number = 1 + (memory["sits"] if isinstance(memory, Mapping) else 0)
        journal = list(memory["journal"]) if isinstance(memory, Mapping) else []
        lifetime = memory["breaths"] if isinstance(memory, Mapping) else 0
        face.show(sit=number, breath=0, of=args.breaths, state="arriving", journal=journal[-14:],
                  learned=understanding(memory), trace=[], life={"sits": number - 1, "breaths": lifetime})
        rng = random.Random(f"{args.seed}:{number}")
        body = Body(args.host, args.port)
        try:
            living = Living(body, rng, args.seed, args.thoughts)
            breath = living.breathe("still", 0.0, quiet=True)
            trace: list[dict[str, Any]] = []
            started = time.perf_counter()
            for index in range(1, args.breaths + 1):
                if (index - 1) % ROUND == 0:
                    operation_id, _, _ = mind.begin(memory, closing=index + ROUND > args.breaths)
                before = mind.instructions()
                mind.answer(operation_id, {**breath["felt"], "fresh": True} if index == 1 else breath["felt"])
                pending = mind.request()
                if pending is None:
                    raise MindError("the meditator left before the sit ended")
                operation_id, _, decision = pending
                work = mind.instructions() - before
                journal.extend(decision.get("notes", []))
                trace.append({"e": round(decision["equanimity"], 4), "b": breath["felt"]["balance"],
                              "p": decision["practice"], "h": decision["habit"], "t": breath["thought"]})
                face.show(breath=index, state="sitting", felt=breath["felt"], thought=breath["thought"],
                          practice=decision, work=work, journal=journal[-14:], trace=trace[-TRACE:],
                          field=breath["view"], power=breath["power"],
                          life={"sits": number - 1, "breaths": lifetime + index})
                if args.verbose:
                    felt = breath["felt"]
                    print(f"{index:4d} {decision['context']:9s} β={felt['balance']:.3f} steady={felt['steadiness']:.3f} "
                          f"spiral={felt['spiral_margin']:+.3f} E={decision['equanimity']:.3f} "
                          f"→ {decision['label']:<22s}{' (habit)' if decision['habit'] else ''} work={work}"
                          f"{' ☁' if breath['thought'] else ''}", flush=True)
                breath = living.breathe(decision["practice"], float(decision["strength"]))
                if index % ROUND == 0 or index == args.breaths:
                    mind.answer(operation_id, None)
                    mind.rest()
                    memory = mind.memory()
            elapsed = time.perf_counter() - started
        finally:
            body.close()
    if not isinstance(memory, Mapping):
        raise MindError("the sit ended without leaving its memory in the field")
    face.show(state="resting", journal=memory["journal"][-14:], learned=understanding(memory),
              life={"sits": memory["sits"], "breaths": memory["breaths"]})
    print(f"sit {number}: {args.breaths} breaths in {elapsed:.0f} s", flush=True)
    for line in memory["journal"][-6:]:
        print("  " + line, flush=True)
    if server is not None and args.linger > 0:
        time.sleep(args.linger)
    if server is not None:
        server.shutdown()
    return 0


def status(args: argparse.Namespace) -> int:
    with FieldIntelligenceOwner(Path(args.home) / "mind") as owner:
        mind = Mind(owner)
        if mind.interrupted():  # the owner lock is exclusive, so no other process is sitting
            mind.rest()
            print("an interrupted sit was brought to rest; it continues at the next sit")
        memory = mind.memory()
    if not isinstance(memory, Mapping):
        print("the meditator has not sat yet")
        return 0
    print(f"{memory['sits']} sits, {memory['breaths']} breaths")
    for row in understanding(memory):
        habit = f"  habit: {row['habit']}" if row["habit"] else ""
        print(f"  when {row['context']:<9s} → {row['best']:<22s} {row['gain']:+.4f} over stillness "
              f"({row['samples']} breaths){habit}")
    print("journal:")
    for line in memory["journal"][-12:]:
        print("  " + line)
    return 0


def face_only(args: argparse.Namespace) -> int:
    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    server = serve_face(home, args.face_port)
    print(f"face: http://127.0.0.1:{args.face_port}/", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", default=str(DEFAULT_HOME), help="where the meditator's field and face live")
    commands = parser.add_subparsers(dest="command", required=True)

    sitting = commands.add_parser("sit", help="sit for a number of breaths")
    sitting.add_argument("--breaths", type=int, default=64)
    sitting.add_argument("--host", default="127.0.0.1")
    sitting.add_argument("--port", type=int, default=7599, help="the mind engine that is the meditator's body")
    sitting.add_argument("--thoughts", type=float, default=0.15, help="chance a thought arises in a breath")
    sitting.add_argument("--seed", type=int, default=20260925)
    sitting.add_argument("--face", action="store_true", help="serve the face while sitting")
    sitting.add_argument("--face-port", type=int, default=7612)
    sitting.add_argument("--linger", type=float, default=0.0, help="seconds to keep the face up after the sit")
    sitting.add_argument("--verbose", action="store_true", help="print every breath")
    sitting.set_defaults(run=sit)

    showing = commands.add_parser("face", help="serve the face of a meditator sitting elsewhere")
    showing.add_argument("--face-port", type=int, default=7612)
    showing.set_defaults(run=face_only)

    telling = commands.add_parser("status", help="what the meditator has learned")
    telling.set_defaults(run=status)

    args = parser.parse_args(argv)
    return int(args.run(args))


if __name__ == "__main__":
    sys.exit(main())
