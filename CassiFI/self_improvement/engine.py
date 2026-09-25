"""Cassi's recursive self-improvement engine.

Cassi rewrites her own hot functions with her live brain, measures every
rewrite on a protected anchor, adopts verified gains into the live source, and
improves the improver itself.  The improver is a policy module ``M_g``: it
chooses which function to work on, what the brain sees, how the brain's answer
is read, and how its own successor is written.  A successor ``M_{g+1}`` governs
the lineage only after it beats ``M_g`` on untouched functions under the same
budget of brain calls and tokens, from the same source snapshot.

Layers
------
anchor      ``anchor_worker.py``: fixed workloads, exact output digests,
            durable-write counts, and per-function inclusive clocks.  The
            lineage hash-locks it.
snapshot    a frozen copy of the module closure the anchor exercises; every
            comparison inside a round runs against one snapshot.
pool        the functions worth improving: measured, stable, free of child
            process noise, and located in the snapshot's own modules.
arm         one policy spending one budget on one set of functions.
succession  live round -> adoption -> successor -> matched comparison ->
            promotion -> adoption.

Command line (run from anywhere)::

    python CassiFI/self_improvement/engine.py succession --generations 2
    python CassiFI/self_improvement/engine.py status
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import copy
import hashlib
import importlib.util
import json
import math
import os
import queue
import re
import shutil
import statistics
import subprocess
import sys
import textwrap
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psutil

PACKAGE = Path(__file__).resolve().parent
LIVE = PACKAGE.parent
REPOSITORY = LIVE.parent
WORKER = PACKAGE / "anchor_worker.py"
POLICY_DIR = PACKAGE / "policies"
HOME = Path(os.environ.get("CASSI_SELF_IMPROVEMENT_HOME", "E:/CassiData/self-improvement"))
CORPUS = HOME / "corpus"
WARM_CORPUS = HOME / "corpus-warm"
LINEAGE = HOME / "lineage.json"
BRAIN_URL = os.environ.get("CASSI_BRAIN_URL", "http://127.0.0.1:8097")
BRAIN_ABSENCE_LIMIT = 12 * 3600.0
# The dense 9B brain shared with the CassiTrading supervisor's `brain` service, fully in VRAM; this session starts
# it only when that service is absent and the GPU has room beside other sessions.
BRAIN_SERVER = [
    "E:/CassiData/outputs/CassiTrading/_service/brain-bin/llama-server.exe",
    "--model", str(LIVE.parent / "CassiQwen/Qwen3.5-9B-Q8_0.gguf"),
    "--host", "127.0.0.1", "--port", BRAIN_URL.rsplit(":", 1)[-1], "--ctx-size", "65536", "--parallel", "4",
    "--kv-unified", "--gpu-layers", "99", "--flash-attn", "on", "--jinja", "--cache-ram", "2048",
    "--no-cassi-modal", "--load-mode", "none",
]
BRAIN_VRAM_MB = 12_000  # 9.1 GiB of weights, the unified KV cache, and compute buffers
GPU_MEMORY_MB = int(os.environ.get("CASSI_GPU_MEMORY_MB", "24560"))

MAX_COMPLETION = 6144
MAX_PROMPT_CHARS = 40_000
MAX_SUCCESSOR_PROMPT_CHARS = 70_000
SUCCESSOR_COMPLETION = 24_000
DIAGNOSIS_COMPLETION = 16_000
DIAGNOSIS_REQUEST = """

## Before the module: diagnosis
Do not write the module yet.  Answer in prose, citing the ledger's numbers:
1. Where the parent's reading comes from, and where its calls and tokens produce nothing.
2. Three changes to the parent's method, each in a different part of it: which targets get calls and in what
   order; how many attempts a target gets and what follows a verified or a failed attempt; the request parameters
   (max_tokens, temperature, reasoning mode); the context and evidence a prompt carries; how replies are parsed.
   For each, the ledger evidence behind it and the reading gain per arm it would plausibly add, computed from the
   numbers (the reading is the sum over targets of the log of each target's best verified speedup).
3. The one change with the largest expected gain that you will make, and the ledger figure that will show
   whether it worked.
"""
WRITE_REQUEST = (
    "Now write the complete successor module that makes the change you chose, keeping everything in the parent "
    "that your diagnosis gives no reason to change.  Return it in one ```python block."
)
VERIFY_RATIO = 1.05
TOTAL_TOLERANCE = 1.04
CALIBRATION_RUNS = 5
MAX_TARGET_CV = 0.06
MIN_TARGET_SECONDS = 0.002
MIN_LOCAL_SECONDS = 0.004
MIN_LOCAL_SHARE = 0.15
TEST_PREFIXES = ("test_", "conftest", "pytest_")
BLOCKING_LEAVES = frozenset({
    "<built-in method nt.fsync>", "<built-in method posix.fsync>", "<built-in method nt.replace>",
    "<built-in method posix.replace>", "<method 'acquire' of '_thread.lock' objects>",
    "<method 'acquire' of '_thread.RLock' objects>", "<built-in method time.sleep>",
    "<built-in method _winapi.WaitForSingleObject>", "<built-in method _winapi.WaitForMultipleObjects>",
    "<built-in method _winapi.CreateProcess>",
})
SCREEN_PARALLEL = 3
TIMED_PAIRS = 3
PROMISING_RATIO = 0.95
PLAN_TIMEOUT = 60.0
PARSE_TIMEOUT = 20.0
POLICY_LOAD_TIMEOUT = 60.0
REPLAY_TIMEOUT = 10.0
REPLAY_CASES = 24
DENY = (
    "threading", "concurrent", "multiprocessing", "monitoring", "setprofile", "settrace",
    "gc", "perf_counter", "process_time", "anchor_worker", "_thread", "ctypes", "lru_cache", "pytest", "unittest",
)

RULES = f"""\
- Return the complete replacement for the one function, with the same name, the same parameters and defaults, and the same sync/async kind.
- Every observable result must stay identical: return values, mutations, exceptions, written files and their bytes, and the order of durable writes.  Cassi's anchor compares exact output digests and runs Cassi's own tests.
- Speed must come from doing the work faster.  Never cache a call's result for reuse by a later call with the same arguments: the anchor repeats identical calls, so a result cache measures as a false gain.  Precomputing constants, compiled patterns, and lookup tables is fine.
- Durable writes stay durable: never remove or skip os.fsync, os.replace, flush, or atomic-write steps.
- Module-level helpers (imports, constants, precompiled patterns, helper functions) may precede a module-level function in the same reply, using new names.  A method replacement is a single def; put helpers inside it.
- The anchor forbids new uses of: {", ".join(DENY)}.
- A rewrite counts when the function's own inclusive time falls by at least {int(round((VERIFY_RATIO - 1) * 100))}% on the anchor and the whole anchor does not slow down."""

POLICY_INTERFACE = f"""\
A policy module is a Python 3.12 file that defines:

plan(view: dict) -> list[dict]
    Called before every wave.  Return at most view["slots"] requests; an empty list ends the arm.
    view["targets"]: list of target dicts with keys
        id, module, qualname, name, method (bool), file, source (current code), args,
        profile {{calls, cumulative, self}} (profiler seconds, inflated for tiny calls),
        base {{seconds, calls, cv}} (measured inclusive seconds on the anchor: the number to beat),
        callees [{{function, calls, cumulative}}], callers [{{function, calls, cumulative}}].
    view["history"]: outcomes of this arm so far, oldest first; each has
        target, wave, note, temperature, thinking, max_tokens, prompt_tokens, completion_tokens,
        stage ("request" | "brain" | "parse" | "invalid" | "screen" | "slower" | "verified"),
        detail (why it stopped there), ratio (base/candidate inclusive time, when timed),
        total_ratio, candidate (the parsed replacement), reply (start of the brain's answer).
    view["budget"]: calls_left, tokens_left, calls_total, tokens_total.  Prompt and completion tokens both count.
    view["slots"]: requests that run concurrently in this wave.
    view["memory"]: a dict the policy may mutate; it persists across waves of one arm while the policy's
        process lives (an overrunning call restarts the process with empty memory).
    view["rules"]: the anchor's rules for a valid rewrite (worth showing to the brain).
    view["snapshot_root"]: directory holding the snapshot's source files (read-only context, e.g. callee definitions).
    view["limits"]: max_tokens cap ({MAX_COMPLETION}) and prompt_chars cap ({MAX_PROMPT_CHARS}).
    A request is a dict: target (id), messages (chat list of {{role, content}}), max_tokens, temperature,
    thinking (bool: Qwen reasoning mode, whose tokens count against the budget), note (free text).

parse(text: str, target: dict) -> str | None
    Extract the replacement source (the def, plus optional module-level helpers) from the brain's answer.
    It runs on every reply, including replies cut off at max_tokens with an unclosed fence, and must return
    within {PARSE_TIMEOUT:.0f}s.  Successors are first replayed on replies the brain wrote in earlier rounds.

successor_messages(record: dict) -> list[dict]
    Chat messages asking the brain to write the complete next policy module (returned in one ```python block).
    record keys: generation, parent, parent_source, interface, rules, rounds (arms this lineage ran: label,
    policy, reading, verified, attempts, calls_used, tokens_used, budget {{calls, tokens}}, ended (why the arm
    stopped), stages, history), comparisons (earlier successor trials: parent, child, readings, promoted), limits.
    Prompt limit {MAX_SUCCESSOR_PROMPT_CHARS} characters; the successor reply may use up to {SUCCESSOR_COMPLETION} tokens.
    The harness appends a ledger of per-policy totals over every arm of the lineage to the last message, and the
    brain answers in reasoning mode.

Each policy runs in its own process; its arguments and results cross as JSON.
The harness counts budget, builds and verifies candidates, and keeps the anchor fixed.
A successor is promoted only when its arm earns a higher reading than its parent's arm on untouched
functions with the same budget.  The reading is the sum over targets of log(best verified speedup): each target
counts once, at its best verified speedup, and a target without a verified speedup counts zero."""


# --------------------------------------------------------------------- utilities


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex[:8]}.tmp")
    temporary.write_text(json.dumps(value, indent=1, default=str), encoding="utf-8")
    os.replace(temporary, path)


def _quiet_core() -> list[int]:
    """Logical processors of the physical core other work has used least over the last half second.

    A function's speed depends on what shares its core: with a busy SMT sibling the same code ran up to
    1.8x slower, run to run.  Timed runs pinned to one quiet core repeat within a few percent.
    """

    load = psutil.cpu_percent(interval=0.5, percpu=True)
    width = max(1, len(load) // (psutil.cpu_count(logical=False) or len(load)))
    cores = [list(range(start, start + width)) for start in range(0, len(load), width)]
    return min(cores[1:] or cores, key=lambda core: sum(load[cpu] for cpu in core))


class _Lanes:
    """Screens share the machine; timing runs have it to themselves, pinned to its quietest core."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._shared = 0
        self._exclusive = False
        self._waiting = 0

    @contextlib.contextmanager
    def shared(self):
        with self._condition:
            while self._exclusive or self._waiting:
                self._condition.wait()
            self._shared += 1
        try:
            yield
        finally:
            with self._condition:
                self._shared -= 1
                self._condition.notify_all()

    @contextlib.contextmanager
    def exclusive(self):
        with self._condition:
            self._waiting += 1
            while self._exclusive or self._shared:
                self._condition.wait()
            self._waiting -= 1
            self._exclusive = True
        try:
            yield _quiet_core()
        finally:
            with self._condition:
                self._exclusive = False
                self._condition.notify_all()


# ------------------------------------------------------------------------ anchor


def anchor_sha() -> str:
    return _sha(WORKER.read_bytes())


def run_anchor(
    source_root: Path,
    *,
    overlay: Path | None = None,
    targets: tuple[str, ...] | list[str] = (),
    workloads: tuple[str, ...] | list[str] = (),
    profile: Path | None = None,
    modules: Path | None = None,
    dump: Path | None = None,
    timeout: float = 600.0,
    cores: list[int] | None = None,
) -> dict:
    out = HOME / "tmp" / f"anchor-{uuid.uuid4().hex}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, str(WORKER), "--source-root", str(source_root),
        "--corpus", str(CORPUS), "--warm-corpus", str(WARM_CORPUS), "--out", str(out),
    ]
    if overlay is not None:
        command += ["--overlay", str(overlay)]
    for target in targets:
        command += ["--target", target]
    for workload in workloads:
        command += ["--workload", workload]
    for flag, path in (("--profile", profile), ("--modules", modules), ("--dump", dump)):
        if path is not None:
            command += [flag, str(path)]
    started = time.perf_counter()
    # Timed runs take the machine's high priority class and one quiet core, so other sessions' work neither
    # preempts the clock nor shares the core it reads.  Child processes inherit the affinity.
    flags = subprocess.HIGH_PRIORITY_CLASS if cores and os.name == "nt" else 0
    # Test workloads run on the CPU with a fixed hash seed, as the survey that chose them did.
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONHASHSEED="0")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               cwd=str(source_root), creationflags=flags, env=env)
    if cores:
        with contextlib.suppress(psutil.Error):
            psutil.Process(process.pid).cpu_affinity(cores)
    try:
        _, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        out.unlink(missing_ok=True)
        return {"ok": False, "error": f"the anchor did not finish within {timeout:.0f}s", "elapsed": timeout}
    try:
        payload = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {"ok": False, "error": "the anchor produced no result", "traceback": (stderr or "")[-3000:]}
    finally:
        out.unlink(missing_ok=True)
    payload["elapsed"] = time.perf_counter() - started
    return payload


def _total(payload: dict) -> float:
    """Whole-anchor reading: the sum of each workload's declared steady reading (wall or CPU seconds)."""

    return sum(value["reading"] for value in payload["workloads"].values())


def _short(value: Any, limit: int = 160) -> str:
    text = json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


def first_difference(expected: Any, actual: Any, path: str = "") -> str:
    if type(expected) is not type(actual):
        return f"{path or 'value'}: expected {_short(expected)} got {_short(actual)}"
    if isinstance(expected, dict):
        for key in expected:
            if key not in actual:
                return f"{path}.{key} is missing"
            found = first_difference(expected[key], actual[key], f"{path}.{key}")
            if found:
                return found
        extra = sorted(set(actual) - set(expected))
        return f"{path}: unexpected keys {extra[:3]}" if extra else ""
    if isinstance(expected, list):
        for index, (left, right) in enumerate(zip(expected, actual)):
            found = first_difference(left, right, f"{path}[{index}]")
            if found:
                return found
        if len(expected) != len(actual):
            return f"{path}: expected {len(expected)} items got {len(actual)}"
        return ""
    if expected != actual:
        return f"{path or 'value'}: expected {_short(expected)} got {_short(actual)}"
    return ""


# ---------------------------------------------------------------------- snapshot


class Snapshot:
    def __init__(self, root: Path, files: dict[str, str]) -> None:
        self.root = root
        self.files = files


def take_snapshot(label: str) -> Snapshot:
    """Copy the module closure the anchor exercises in the live tree."""

    modules_file = HOME / "tmp" / f"modules-{uuid.uuid4().hex}.json"
    payload = run_anchor(LIVE, modules=modules_file)
    if not payload.get("ok"):
        raise RuntimeError(f"the live anchor failed: {payload.get('error')}\n{payload.get('traceback', '')}")
    closure = json.loads(modules_file.read_text(encoding="utf-8"))
    modules_file.unlink(missing_ok=True)
    root = HOME / "snapshots" / f"{_stamp()}-{label}-{uuid.uuid4().hex[:4]}"
    files: dict[str, str] = {}
    directories: set[Path] = set()
    for name in closure:
        relative = Path(name).resolve().relative_to(LIVE)
        if relative.parts[0] == PACKAGE.name or not (LIVE / relative).is_file():
            continue  # the engine's own package, and torch's synthetic `_classes.py`/`_ops.py` names
        data = (LIVE / relative).read_bytes()
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        files[relative.as_posix()] = _sha(data)
        directories.add(relative.parent)
    for directory in directories:
        for extra in (LIVE / directory).iterdir():
            if extra.is_file() and extra.suffix not in (".py", ".pyc") and extra.stat().st_size <= 2_000_000:
                destination = root / directory / extra.name
                if not destination.exists():
                    shutil.copy2(extra, destination)
    _write_json(root / "snapshot.json", {"label": label, "created": _stamp(), "live": str(LIVE), "files": files})
    return Snapshot(root, files)


# -------------------------------------------------------------------------- pool


def _function_index(path: Path) -> dict[int, dict]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    index: dict[int, dict] = {}

    def visit(body: list[ast.stmt], prefix: str, in_class: bool) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([decorator.lineno for decorator in node.decorator_list] + [node.lineno])
                record = {
                    "qualname": prefix + node.name,
                    "name": node.name,
                    "method": in_class,
                    "start": start,
                    "end": node.end_lineno,
                    "indent": node.col_offset,
                    "source": "".join(lines[start - 1:node.end_lineno]),
                    "args": ast.unparse(node.args),
                    "async": isinstance(node, ast.AsyncFunctionDef),
                }
                index[start] = record
                index[node.lineno] = record
            elif isinstance(node, ast.ClassDef):
                visit(node.body, prefix + node.name + ".", True)

    visit(ast.parse(text).body, "", False)
    return index


def profile_snapshot(snapshot: Snapshot) -> dict:
    """Profile rows of every workload's timed pass, and the snapshot files each workload runs."""

    path = HOME / "tmp" / f"profile-{uuid.uuid4().hex}.json"
    payload = run_anchor(snapshot.root, profile=path)
    if not payload.get("ok"):
        raise RuntimeError(f"the snapshot anchor failed: {payload.get('error')}\n{payload.get('traceback', '')}")
    profile = json.loads(path.read_text(encoding="utf-8"))
    path.unlink(missing_ok=True)
    return profile


def build_pool(snapshot: Snapshot, rows: list[dict]) -> list[dict]:
    root = snapshot.root.resolve()
    callees: dict[tuple, list[tuple[dict, int, float]]] = defaultdict(list)
    for row in rows:
        for caller_file, caller_line, caller_function, calls, cumulative in row["callers"]:
            callees[(caller_file, caller_line, caller_function)].append((row, calls, cumulative))
    callers = {(row["file"], row["lineno"], row["function"]): row["callers"] for row in rows}

    def label(file: str, function: str) -> str:
        try:
            relative = Path(file).resolve().relative_to(root)
            return f"{relative.with_suffix('').as_posix().replace('/', '.')}:{function}"
        except (ValueError, OSError):
            return function if file == "~" else f"{Path(file).name}:{function}"

    placed: dict[str, bool] = {}

    def inside(file: str) -> bool:
        if file not in placed:
            try:
                Path(file).resolve().relative_to(root)
                placed[file] = True
            except (ValueError, OSError):
                placed[file] = False
        return placed[file]

    def harness(file: str) -> bool:
        """The anchor's own frames: its durable-write counters and, in confused profiles, its drivers."""

        return file.endswith("anchor_worker.py")

    by_key = {(row["file"], row["lineno"], row["function"]): row for row in rows}
    shares: dict[tuple, float] = {}

    def blocking_share(key: tuple, active: set[tuple]) -> float:
        """Fraction of a function's cumulative time spent waiting on durable writes, locks, or processes."""

        if key in shares:
            return shares[key]
        row = by_key.get(key)
        if row is None or row["cumtime"] <= 0:
            return 0.0
        if row["file"] == "~":
            share = 1.0 if row["function"] in BLOCKING_LEAVES else 0.0
            shares[key] = share
            return share
        if key in active:
            return 0.0
        active.add(key)
        blocked = sum(
            cumulative * blocking_share((callee["file"], callee["lineno"], callee["function"]), active)
            for callee, _, cumulative in callees.get(key, ()) if callee is not row
        )
        active.discard(key)
        shares[key] = min(1.0, blocked / row["cumtime"])
        return shares[key]

    def spawns(key: tuple) -> bool:
        seen: set[tuple] = set()
        stack = [key]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            for row, _, _ in callees.get(current, ()):
                if "CreateProcess" in row["function"] or (
                    row["file"].endswith("subprocess.py") and row["function"] in ("run", "_execute_child")
                ):
                    return True
                stack.append((row["file"], row["lineno"], row["function"]))
        return False

    indexes: dict[Path, dict[int, dict]] = {}
    pool: dict[str, dict] = {}
    for row in rows:
        if row["function"].startswith("<") or row["file"] == "~":
            continue
        try:
            relative = Path(row["file"]).resolve().relative_to(root)
        except (ValueError, OSError):
            continue
        if len(relative.parts) != 1 or relative.suffix != ".py" or relative.name.startswith(TEST_PREFIXES):
            continue  # the tests are the anchor's observers: rewriting them would change the yardstick
        if row["cumtime"] < 0.010 or row["cumtime"] / max(1, row["ncalls"]) < 20e-6:
            continue
        if relative not in indexes:
            indexes[relative] = _function_index(root / relative)
        record = indexes[relative].get(row["lineno"])
        if record is None or record["name"] != row["function"]:
            continue
        key = (row["file"], row["lineno"], row["function"])
        # Time the function's own code spends (itself plus library calls), less waiting on durable writes,
        # locks, and processes, which the rules keep.  Time inside other Cassi functions belongs to those
        # functions, which are improved as targets of their own.  A row whose callees account for little of
        # its time was profiled across threads or callbacks; its attribution is unreliable.
        edges = [(callee, cumulative) for callee, _, cumulative in callees.get(key, ()) if callee is not row]
        unaccounted = row["cumtime"] - row["tottime"] - sum(cumulative for _, cumulative in edges)
        if unaccounted > 0.3 * row["cumtime"]:
            continue
        local = row["cumtime"] - sum(
            cumulative if inside(callee["file"]) or harness(callee["file"])
            else cumulative * blocking_share((callee["file"], callee["lineno"], callee["function"]), set())
            for callee, cumulative in edges
        )
        # A verified rewrite must cut inclusive time by 5%, so the function's own share has to allow it.
        if local < MIN_LOCAL_SECONDS or local < MIN_LOCAL_SHARE * row["cumtime"] or spawns(key):
            continue
        module = relative.stem
        identity = f"{module}:{record['qualname']}"
        if identity in pool:
            continue
        top_callees = sorted(callees.get(key, ()), key=lambda item: -item[2])[:10]
        top_callers = sorted(callers.get(key, ()), key=lambda item: -item[4])[:4]
        pool[identity] = {
            "id": identity,
            "module": module,
            "file": relative.as_posix(),
            **record,
            "workloads": row["workloads"],
            "profile": {
                "calls": row["ncalls"], "cumulative": round(row["cumtime"], 5), "self": round(row["tottime"], 5),
                "local": round(local, 5),
            },
            "callees": [
                {"function": label(callee["file"], callee["function"]), "calls": calls, "cumulative": round(cumulative, 5)}
                for callee, calls, cumulative in top_callees
            ],
            "callers": [
                {"function": label(file, function), "calls": calls, "cumulative": round(cumulative, 5)}
                for file, _, function, calls, cumulative in top_callers
            ],
        }
    return sorted(pool.values(), key=lambda target: -target["profile"]["local"])


# ------------------------------------------------------------------- candidates


class CandidateError(ValueError):
    pass


def _identifiers(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                names.update(node.module.split("."))
            for alias in node.names:
                names.update(alias.name.split("."))
                if alias.asname:
                    names.add(alias.asname)
    return names


def _bound_names(node: ast.stmt) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Import):
        return [alias.asname or alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        return [alias.asname or alias.name for alias in node.names]
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    names: list[str] = []
    for target in targets:
        for item in ast.walk(target):
            if isinstance(item, ast.Name):
                names.append(item.id)
    return names


def _module_bindings(tree: ast.Module) -> dict[str, list[ast.stmt]]:
    bindings: dict[str, list[ast.stmt]] = defaultdict(list)

    def visit(body: list[ast.stmt]) -> None:
        for node in body:
            for name in _bound_names(node):
                bindings[name].append(node)
            if isinstance(node, (ast.If, ast.Try, ast.With)):
                visit(node.body)
                visit(getattr(node, "orelse", []))
                visit(getattr(node, "finalbody", []))
                for handler in getattr(node, "handlers", []):
                    visit(handler.body)

    visit(tree.body)
    return bindings


def _import_origin(node: ast.stmt, name: str) -> tuple | None:
    """What an import statement binds to ``name``, so a repeated import of the same object is harmless."""

    if isinstance(node, ast.Import):
        for alias in node.names:
            if (alias.asname or alias.name.split(".")[0]) == name:
                return ("import", alias.name if alias.asname else alias.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            if (alias.asname or alias.name) == name:
                return ("from", node.level, node.module, alias.name)
    return None


def build_candidate(root: Path, target: dict, replacement: str) -> tuple[str, str]:
    """The patched module text and the replacement block, or ``CandidateError``."""

    path = root / target["file"]
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    if "".join(lines[target["start"] - 1:target["end"]]) != target["source"]:
        raise CandidateError("the snapshot no longer holds this function")
    text = textwrap.dedent(replacement.expandtabs(4)).strip("\n") + "\n"
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise CandidateError(f"the replacement does not parse: {exc.msg} (line {exc.lineno})") from None
    definitions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target["name"]
    ]
    if len(definitions) != 1:
        raise CandidateError(f"the replacement must define {target['name']} exactly once at its top level")
    function = definitions[0]
    if ast.unparse(function.args) != target["args"]:
        raise CandidateError(
            f"the parameters changed: expected ({target['args']}) got ({ast.unparse(function.args)})"
        )
    if isinstance(function, ast.AsyncFunctionDef) != target["async"]:
        raise CandidateError("the replacement changed sync/async kind")
    helpers = [node for node in tree.body if node is not function]
    if helpers and target["method"]:
        raise CandidateError("a method replacement must be a single def; put helpers inside it")
    bindings = _module_bindings(ast.parse(original))
    for node in helpers:
        if not isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.FunctionDef, ast.ClassDef)):
            raise CandidateError(f"unsupported module-level statement in the reply: {type(node).__name__}")
        for name in _bound_names(node):
            if name not in bindings:
                continue
            origin = _import_origin(node, name)
            if origin is None or not any(_import_origin(existing, name) == origin for existing in bindings[name]):
                raise CandidateError(f"helper name {name!r} already exists in {target['module']}; choose a new name")
    used = _identifiers(tree)
    before = _identifiers(ast.parse(textwrap.dedent(target["source"])))
    banned = sorted(name for name in DENY if name in used and name not in before)
    if banned:
        raise CandidateError(f"the replacement uses {', '.join(banned)}, which the anchor forbids")
    indent = " " * target["indent"]
    block = "".join((indent + line) if line.strip() else line for line in text.splitlines(keepends=True))
    candidate = "".join(lines[:target["start"] - 1]) + block + "".join(lines[target["end"]:])
    if candidate == original:
        raise CandidateError("the replacement is identical to the current function")
    try:
        compile(candidate, str(path), "exec")
    except SyntaxError as exc:
        raise CandidateError(f"the patched module does not compile: {exc.msg} (line {exc.lineno})") from None
    return candidate, block


# ------------------------------------------------------------------------- bench


class Bench:
    """One snapshot, its measured pool, and the lanes that evaluate candidates."""

    def __init__(self, snapshot: Snapshot, pool: list[dict], work: Path, touched: dict[str, list[str]]) -> None:
        self.snapshot = snapshot
        self.root = snapshot.root
        self.pool = {target["id"]: target for target in pool}
        self.ids = [target["id"] for target in pool]
        self.work = work
        self.lanes = _Lanes()
        self.screens = threading.Semaphore(SCREEN_PARALLEL)
        self.base_digests: dict[str, str] = {}
        self.base_durable: dict[str, tuple[int, int]] = {}
        self.base_dump: Any = None
        self.dropped: dict[str, str] = {}
        self.unsteady: list[str] = []
        self.timeout = 240.0
        # A candidate changes one module, so only the workloads that run that module can observe it.
        self.runners: dict[str, list[str]] = defaultdict(list)
        root = self.root.resolve()
        for name, files in touched.items():
            for file in files:
                with contextlib.suppress(ValueError, OSError):
                    self.runners[Path(file).resolve().relative_to(root).as_posix()].append(name)

    def _anchor(self, cores: list[int], *, overlay: Path | None = None, dump: Path | None = None,
                targets: list[str] | None = None, workloads: list[str] | tuple[str, ...] = ()) -> dict:
        return run_anchor(self.root, overlay=overlay, targets=self.ids if targets is None else targets,
                          workloads=workloads, dump=dump, timeout=self.timeout, cores=cores)

    def calibrate(self, runs: int = CALIBRATION_RUNS) -> None:
        """One full run fixes every workload's digest; the repeats run only the workloads the pool touches."""

        self.work.mkdir(parents=True, exist_ok=True)
        dump = self.work / "base-dump.json"
        needed = sorted({name for target in self.pool.values() for name in target["workloads"]})
        with self.lanes.exclusive() as cores:
            payloads = [self._anchor(cores, dump=dump)] + [self._anchor(cores, workloads=needed) for _ in range(runs - 1)]
        for payload in payloads:
            if not payload.get("ok"):
                raise RuntimeError(f"the base anchor failed: {payload.get('error')}\n{payload.get('traceback', '')}")
        first = payloads[0]
        self.base_digests = {name: value["digest"] for name, value in first["workloads"].items()}
        self.base_durable = {name: (value["fsync"], value["replace"]) for name, value in first["workloads"].items()}
        # A workload whose output varies between identical runs cannot tell a changed candidate apart.
        self.unsteady = sorted({name for payload in payloads[1:] for name, value in payload["workloads"].items()
                                if self.base_digests[name] != value["digest"]})
        for name in self.unsteady:
            del self.base_digests[name], self.base_durable[name]
        if not self.base_digests:
            raise RuntimeError("no workload of the base anchor is deterministic")
        self.base_dump = json.loads(dump.read_text(encoding="utf-8"))
        missing = {name for name, _ in first.get("missing", [])}
        for identity in list(self.ids):
            samples = [payload["targets"][identity]["seconds"] for payload in payloads]
            calls = first["targets"][identity]["calls"]
            reason = ""
            if identity in missing:
                reason = "the clock could not resolve the function"
            elif self.runners and not any(name in self.base_digests for name in self.runners.get(self.pool[identity]["file"], ())):
                reason = "no deterministic workload runs its module"
            elif calls == 0 or min(samples) < MIN_TARGET_SECONDS:
                reason = f"too little measured time ({min(samples):.4f}s)"
            else:
                # Contention from other work only ever slows a run, so stability is read on the fastest runs.
                fastest = sorted(samples)[: max(3, (len(samples) + 1) // 2)]
                spread = statistics.pstdev(fastest) / statistics.mean(fastest)
                if spread > MAX_TARGET_CV:
                    reason = f"unstable timing (cv {spread:.3f})"
                else:
                    self.pool[identity]["base"] = {
                        "seconds": round(min(samples), 6), "calls": calls, "cv": round(spread, 4),
                    }
            if reason:
                self.dropped[identity] = reason
        self.ids = [identity for identity in self.ids if identity not in self.dropped]
        self.pool = {identity: self.pool[identity] for identity in self.ids}
        self.timeout = max(90.0, 6 * first["elapsed"])

    def evaluate(self, identity: str, module_text: str, label: str) -> dict:
        target = self.pool[identity]
        overlay = self.work / "candidates" / label
        overlay.mkdir(parents=True, exist_ok=True)
        (overlay / target["file"]).write_text(module_text, encoding="utf-8")
        dump = overlay / "dump.json"
        names = [name for name in self.base_digests if name in self.runners.get(target["file"], ())] or list(self.base_digests)
        with self.screens, self.lanes.shared():
            screen = run_anchor(self.root, overlay=overlay, dump=dump, workloads=names, timeout=self.timeout)
        if not screen.get("ok"):
            trace = screen.get("traceback", "")
            return {"stage": "screen", "detail": f"the anchor failed with the candidate: {screen.get('error')}\n{trace[-1500:]}"}
        changed = [name for name in names if screen["workloads"][name]["digest"] != self.base_digests[name]]
        if changed:
            try:
                observed = json.loads(dump.read_text(encoding="utf-8"))
                difference = first_difference({name: self.base_dump[name] for name in changed},
                                              {name: observed[name] for name in changed})
            except (OSError, ValueError, KeyError):
                difference = "no output captured"
            return {"stage": "screen", "detail": f"output changed in the {', '.join(changed)} workload: {difference}"}
        for name in names:
            fsync, replace = self.base_durable[name]
            observed = screen["workloads"][name]
            if observed["fsync"] < fsync or observed["replace"] < replace:
                return {
                    "stage": "screen",
                    "detail": f"durable writes dropped in {name}: fsync {observed['fsync']} of {fsync}, "
                              f"replace {observed['replace']} of {replace}",
                }
        # Base and candidate alternate inside one exclusive window, so load from other work on the machine
        # lands on both sides of the comparison.  A first pair far from a gain ends the timing early.  Only the
        # workloads that reach the function run, with only its clock installed; the screen above ran every
        # workload that runs the function's module.
        runs: dict[str, list[dict]] = {"base": [], "candidate": []}
        failure: dict = {}
        with self.lanes.exclusive() as cores:
            for pair in range(TIMED_PAIRS):
                for side in (("candidate", "base") if pair % 2 == 0 else ("base", "candidate")):
                    payload = self._anchor(cores, overlay=overlay if side == "candidate" else None,
                                           targets=[identity], workloads=target["workloads"])
                    if payload.get("ok"):
                        runs[side].append(payload)
                    else:
                        failure = payload
                if failure:
                    break
                if pair == 0 and runs["base"][0]["targets"][identity]["seconds"] < \
                        PROMISING_RATIO * runs["candidate"][0]["targets"][identity]["seconds"]:
                    break
        if not runs["candidate"] or not runs["base"]:
            return {"stage": "screen", "detail": f"the timed anchor failed: {failure.get('error')}"}
        base = min(payload["targets"][identity]["seconds"] for payload in runs["base"])
        measured = min(payload["targets"][identity]["seconds"] for payload in runs["candidate"])
        candidate_total = min(_total(payload) for payload in runs["candidate"])
        if measured <= 0 or candidate_total <= 0:
            # The clock lost the work: the candidate's time read zero, so no speedup can be attributed to it.
            return {"stage": "invalid", "detail": f"the timed run read zero seconds (function {measured}, "
                                                  f"whole anchor {candidate_total}); the rewrite escaped the clock"}
        ratio = base / measured
        total_ratio = min(_total(payload) for payload in runs["base"]) / candidate_total
        outcome = {
            "ratio": round(ratio, 4),
            "total_ratio": round(total_ratio, 4),
            "base_seconds": round(base, 6),
            "candidate_seconds": round(measured, 6),
            "timed_runs": len(runs["candidate"]),
        }
        if ratio >= VERIFY_RATIO and total_ratio >= 1 / TOTAL_TOLERANCE:
            return {"stage": "verified", "detail": f"{ratio:.3f}x faster inclusive, whole anchor {total_ratio:.3f}x", **outcome}
        return {
            "stage": "slower",
            "detail": f"inclusive time {ratio:.3f}x of base (needs >= {VERIFY_RATIO}x), whole anchor {total_ratio:.3f}x",
            **outcome,
        }


# ------------------------------------------------------------------------- brain


class Brain:
    """Cassi's live pretrained brain behind llama-server's chat endpoint."""

    def __init__(self, url: str = BRAIN_URL) -> None:
        self.url = url.rstrip("/")

    def complete(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        thinking: bool = False,
        seed: int | None = None,
        timeout: float = 1800.0,
    ) -> dict:
        body: dict[str, Any] = {
            "messages": messages,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "chat_template_kwargs": {"enable_thinking": bool(thinking)},
            "cache_prompt": True,
        }
        if seed is not None:
            body["seed"] = int(seed)
        request = urllib.request.Request(
            self.url + "/v1/chat/completions", json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"}
        )
        started = time.perf_counter()
        last: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = json.load(response)
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last = exc
                # An absent server (another session may have stopped or restarted it) pauses the call instead of
                # spending the arm's budget on failures; a present server that failed gets the plain retry.
                self._wait_until_present()
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"the brain did not answer: {last}")
        choice = payload["choices"][0]
        usage = payload.get("usage", {})
        return {
            "text": choice["message"].get("content") or "",
            "reasoning": choice["message"].get("reasoning_content") or "",
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "finish": choice.get("finish_reason"),
            "seconds": round(time.perf_counter() - started, 2),
        }

    def _wait_until_present(self) -> None:
        deadline = time.monotonic() + BRAIN_ABSENCE_LIMIT
        announced = False
        while True:
            try:
                with urllib.request.urlopen(self.url + "/health", timeout=10) as response:
                    if response.status == 200:
                        if announced:
                            _log(f"the brain at {self.url} is back")
                        return
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                pass
            if time.monotonic() > deadline:
                raise RuntimeError(f"the brain at {self.url} stayed absent for {BRAIN_ABSENCE_LIMIT / 3600:.0f} h")
            if not announced:
                _log(f"the brain at {self.url} is absent; its calls wait for it")
                announced = True
            time.sleep(30)


# ------------------------------------------------------------------------ policy


def load_policy(path: Path):
    name = f"cassi_policy_{_sha(path.read_bytes())[:12]}_{uuid.uuid4().hex[:6]}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for attribute in ("plan", "parse", "successor_messages"):
        if not callable(getattr(module, attribute, None)):
            raise TypeError(f"{path.name} does not define {attribute}()")
    return module


class PolicyError(RuntimeError):
    """A policy call raised, or the policy's process ended."""


def serve_policy(path: Path) -> int:
    """The policy-host process: one policy module, one JSON line per call and per answer."""

    answers = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())  # the policy's own prints must not reach the channel
    sys.stdin.reconfigure(encoding="utf-8")

    def send(status: str, value: Any) -> None:
        answers.write(json.dumps([status, value], default=str) + "\n")
        answers.flush()

    try:
        module = load_policy(path)
    except BaseException:
        send("error", f"the module did not load:\n{traceback.format_exc()[-1800:]}")
        return 1
    send("ok", None)
    memory: dict = {}
    for line in sys.stdin:
        name, args = json.loads(line)
        try:
            if name == "plan":
                view = args[0]
                view["memory"] = memory
                value = list(module.plan(view) or [])
                memory = view["memory"]
            elif name in ("parse", "successor_messages"):
                value = getattr(module, name)(*args)
            else:
                raise ValueError(f"unknown policy call {name!r}")
            send("ok", value)
        except BaseException:
            send("error", traceback.format_exc()[-1800:])
    return 0


class PolicyHost:
    """A policy module served by its own process.

    Policies are written by the brain, so their code can loop, hold the interpreter, or crash.  In its own
    process that costs only the call that caused it: an overrun kills the process, and the next call starts
    a fresh one (with a fresh ``view["memory"]``).
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._answers: queue.Queue | None = None

    def __enter__(self) -> PolicyHost:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _start(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).resolve()), "policy-host", str(self.path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
        )
        answers: queue.Queue = queue.Queue()

        def read() -> None:
            for line in process.stdout:
                answers.put(line)
            answers.put(None)

        threading.Thread(target=read, name=f"policy-{self.path.stem}", daemon=True).start()
        self._process, self._answers = process, answers
        try:
            self._receive("loading the module", POLICY_LOAD_TIMEOUT)
        except BaseException:
            self._stop()
            raise

    def _stop(self) -> None:
        process, self._process, self._answers = self._process, None, None
        if process is None:
            return
        with contextlib.suppress(OSError):
            process.kill()
        with contextlib.suppress(OSError, ValueError):
            process.stdin.close()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(10)

    def _receive(self, what: str, timeout: float) -> Any:
        try:
            line = self._answers.get(timeout=timeout)
        except queue.Empty:
            self._stop()
            raise TimeoutError(f"{what} did not finish within {timeout:.0f}s") from None
        if line is None:
            self._stop()
            raise PolicyError(f"the policy process ended while {what}")
        status, value = json.loads(line)
        if status != "ok":
            raise PolicyError(value)
        return value

    def call(self, name: str, *args: Any, timeout: float) -> Any:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self._stop()
                self._start()
            try:
                self._process.stdin.write(json.dumps([name, args], default=str) + "\n")
                self._process.stdin.flush()
            except OSError:
                self._stop()
                raise PolicyError(f"the policy process ended before {name}()") from None
            return self._receive(f"{name}()", timeout)

    def close(self) -> None:
        with self._lock:
            self._stop()


def _last_line(exc: BaseException) -> str:
    lines = str(exc).strip().splitlines()
    return lines[-1] if lines else type(exc).__name__


def _valid_messages(messages: Any, limit: int) -> str:
    if not isinstance(messages, list) or not messages:
        return "messages must be a non-empty list"
    size = 0
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in ("system", "user", "assistant"):
            return "every message needs a role of system, user, or assistant"
        if not isinstance(message.get("content"), str):
            return "every message needs string content"
        size += len(message["content"])
    if size > limit:
        return f"the prompt holds {size} characters; the limit is {limit}"
    return ""


def _public_target(target: dict) -> dict:
    return {key: copy.deepcopy(value) for key, value in target.items() if key not in ("start", "end", "indent")}


def run_arm(
    label: str,
    policy_path: Path,
    bench: Bench,
    target_ids: list[str],
    *,
    calls: int,
    tokens: int,
    slots: int,
    seed: int,
    brain: Brain,
    log_dir: Path,
) -> dict:
    targets = [_public_target(bench.pool[identity]) for identity in target_ids]
    history: list[dict] = []
    calls_left, tokens_left = calls, tokens
    wave = 0
    ended = "budget spent"
    log_path = log_dir / f"{label}.jsonl"
    replies_path = log_dir / f"{label}.replies.jsonl"
    log_dir.mkdir(parents=True, exist_ok=True)
    with PolicyHost(policy_path) as policy:
        while calls_left > 0 and tokens_left > 0:
            view = {
                "targets": targets,
                "history": history,
                "budget": {"calls_left": calls_left, "tokens_left": tokens_left, "calls_total": calls, "tokens_total": tokens},
                "slots": min(slots, calls_left),
                "rules": RULES,
                "snapshot_root": str(bench.root),
                "limits": {"max_tokens": MAX_COMPLETION, "prompt_chars": MAX_PROMPT_CHARS},
            }
            try:
                requests = policy.call("plan", view, timeout=PLAN_TIMEOUT)[: view["slots"]]
            except (PolicyError, TimeoutError) as exc:
                ended = f"plan() failed: {_last_line(exc)}"
                break
            if not requests:
                ended = "the policy stopped"
                break
            accepted: list[tuple[int, dict]] = []
            for index, request in enumerate(requests):
                base = {
                    "target": request.get("target") if isinstance(request, dict) else None,
                    "wave": wave,
                    "note": str(request.get("note", ""))[:300] if isinstance(request, dict) else "",
                }
                problem = ""
                if not isinstance(request, dict):
                    problem = "a request must be a dict"
                elif request.get("target") not in target_ids:
                    problem = f"unknown target {request.get('target')!r}"
                else:
                    problem = _valid_messages(request.get("messages"), MAX_PROMPT_CHARS)
                if problem:
                    calls_left -= 1
                    history.append({**base, "stage": "request", "detail": problem})
                    continue
                accepted.append((index, request))
            if not accepted:
                wave += 1
                continue

            def generate(item: tuple[int, dict]) -> dict:
                index, request = item
                try:
                    return brain.complete(
                        request["messages"],
                        max_tokens=max(64, min(int(request.get("max_tokens", 2048)), MAX_COMPLETION)),
                        temperature=max(0.0, min(float(request.get("temperature", 0.6)), 1.5)),
                        thinking=bool(request.get("thinking", False)),
                        seed=seed * 1000 + wave * 10 + index,
                    )
                except Exception as exc:
                    return {"error": f"{type(exc).__name__}: {exc}"}

            with ThreadPoolExecutor(len(accepted)) as executor:
                replies = list(executor.map(generate, accepted))
            with replies_path.open("a", encoding="utf-8") as handle:
                for (index, request), reply in zip(accepted, replies):
                    calls_left -= 1
                    tokens_left -= reply.get("prompt_tokens", 0) + reply.get("completion_tokens", 0)
                    handle.write(json.dumps({"target": request["target"], "wave": wave, "index": index,
                                             "finish": reply.get("finish"), "text": reply.get("text", "")}) + "\n")

            def process(item: tuple[int, dict], reply: dict) -> dict:
                index, request = item
                identity = request["target"]
                outcome = {
                    "target": identity,
                    "wave": wave,
                    "note": str(request.get("note", ""))[:300],
                    "temperature": request.get("temperature", 0.6),
                    "thinking": bool(request.get("thinking", False)),
                    "max_tokens": request.get("max_tokens", 2048),
                    "prompt_tokens": reply.get("prompt_tokens", 0),
                    "completion_tokens": reply.get("completion_tokens", 0),
                    "brain_seconds": reply.get("seconds"),
                    "finish": reply.get("finish"),
                    "reply": reply.get("text", "")[:3000],
                    "candidate": "",
                    "ratio": None,
                    "total_ratio": None,
                }
                if "error" in reply:
                    return {**outcome, "stage": "brain", "detail": reply["error"]}
                try:
                    source = policy.call("parse", reply["text"], bench.pool[identity], timeout=PARSE_TIMEOUT)
                except (PolicyError, TimeoutError) as exc:
                    return {**outcome, "stage": "parse", "detail": f"parse() failed: {str(exc)[-900:]}"}
                if not isinstance(source, str) or not source.strip():
                    detail = "no replacement found in the reply"
                    if reply.get("finish") == "length":
                        detail += " (the reply hit max_tokens)"
                    return {**outcome, "stage": "parse", "detail": detail}
                outcome["candidate"] = source[:12000]
                try:
                    module_text, block = build_candidate(bench.root, bench.pool[identity], source)
                except CandidateError as exc:
                    return {**outcome, "stage": "invalid", "detail": str(exc)}
                try:
                    result = bench.evaluate(identity, module_text, f"{label}-w{wave}-{index}-{uuid.uuid4().hex[:4]}")
                except Exception as exc:  # one malformed measurement must not end every arm of a trial
                    return {**outcome, "stage": "invalid", "detail": f"evaluation failed: {type(exc).__name__}: {str(exc)[-700:]}"}
                if result["stage"] == "verified":
                    result["block"] = block
                return {**outcome, **result}

            with ThreadPoolExecutor(len(accepted)) as executor:
                outcomes = list(executor.map(process, accepted, replies))
            with log_path.open("a", encoding="utf-8") as handle:
                for outcome in outcomes:
                    history.append(outcome)
                    handle.write(json.dumps(outcome) + "\n")
                    shown = f" {outcome['ratio']}x" if outcome.get("ratio") else ""
                    _log(f"{label} w{wave} {outcome['target']}: {outcome['stage']}{shown} "
                         f"({outcome['completion_tokens']} tok) {outcome.get('detail', '')[:140]!r}")
            wave += 1
    best: dict[str, dict] = {}
    for outcome in history:
        if outcome.get("stage") == "verified":
            identity = outcome["target"]
            if identity not in best or outcome["ratio"] > best[identity]["ratio"]:
                best[identity] = outcome
    reading = sum(math.log(outcome["ratio"]) for outcome in best.values())
    return {
        "label": label,
        "policy": policy_path.stem,
        "policy_sha256": _sha(policy_path.read_bytes()),
        "targets": target_ids,
        "reading": round(reading, 5),
        "verified": len(best),
        "attempts": len(history),
        "stages": dict(Counter(outcome.get("stage") for outcome in history)),
        "calls_used": calls - calls_left,
        "tokens_used": tokens - tokens_left,
        "budget": {"calls": calls, "tokens": tokens},
        "ended": ended,
        "best": best,
        "history": history,
    }


# ---------------------------------------------------------------------- breeding


def _extract_module(text: str) -> str:
    """The policy module in the brain's reply.

    A policy's own prompts contain Markdown fences, so the module's closing fence is the fence line that
    makes the longest block compile and define the policy interface.
    """

    lines = text.splitlines(keepends=True)
    openings = [index for index, line in enumerate(lines) if re.fullmatch(r"```(?:python|py)?[ \t]*\r?\n?", line)]
    closings = [index for index, line in enumerate(lines) if re.fullmatch(r"```[ \t]*\r?\n?", line)] + [len(lines)]
    complete: list[str] = []
    fallback: list[str] = []
    for start in openings:
        for end in closings:
            if end <= start:
                continue
            block = "".join(lines[start + 1:end])
            if "def plan" not in block or "def successor_messages" not in block:
                continue
            fallback.append(block)
            try:
                ast.parse(block)
            except SyntaxError:
                continue
            complete.append(block)
    if complete or fallback:
        return max(complete or fallback, key=len)
    blocks = re.findall(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", text, re.S)
    return max(blocks or [""], key=len)


SAMPLE_TARGET = {
    "id": "cassi_sample:score", "module": "cassi_sample", "qualname": "score", "name": "score", "method": False,
    "file": "cassi_sample.py", "source": "def score(values):\n    total = 0\n    for value in values:\n        total += value * value\n    return total\n",
    "args": "values", "async": False,
    "profile": {"calls": 120, "cumulative": 0.05, "self": 0.04},
    "base": {"seconds": 0.03, "calls": 120, "cv": 0.01},
    "callees": [{"function": "builtins:len", "calls": 120, "cumulative": 0.001}],
    "callers": [{"function": "cassi_sample:run", "calls": 120, "cumulative": 0.06}],
}


def _sample_view() -> dict:
    second = copy.deepcopy(SAMPLE_TARGET)
    second.update({"id": "cassi_sample:Table.rows", "qualname": "Table.rows", "name": "rows", "method": True,
                   "source": "    def rows(self):\n        return [list(r) for r in self._rows]\n", "args": "self"})
    history = [{
        "target": "cassi_sample:score", "wave": 0, "note": "", "temperature": 0.6, "thinking": False,
        "max_tokens": 2048, "prompt_tokens": 900, "completion_tokens": 300, "stage": "slower",
        "detail": "inclusive time 0.990x of base", "ratio": 0.99, "total_ratio": 1.0,
        "candidate": "def score(values):\n    return sum(v * v for v in values)\n", "reply": "```python\n...```",
    }]
    return {
        "targets": [copy.deepcopy(SAMPLE_TARGET), second],
        "history": history,
        "budget": {"calls_left": 11, "tokens_left": 50_000, "calls_total": 12, "tokens_total": 60_000},
        "slots": 2,
        "rules": RULES,
        "snapshot_root": str(LIVE),
        "limits": {"max_tokens": MAX_COMPLETION, "prompt_chars": MAX_PROMPT_CHARS},
    }


def _sample_record(source: str) -> dict:
    view = _sample_view()
    arm = {"label": "sample", "policy": "m0", "reading": 0.1, "verified": 1, "attempts": 2,
           "calls_used": 2, "tokens_used": 3000, "stages": {"slower": 1, "verified": 1},
           "history": view["history"] * 2}
    return {"generation": 1, "parent": "m0", "parent_source": source, "interface": POLICY_INTERFACE,
            "rules": RULES, "rounds": [arm], "comparisons": [],
            "limits": {"prompt_chars": MAX_SUCCESSOR_PROMPT_CHARS, "completion_tokens": SUCCESSOR_COMPLETION}}


def _excerpt(text: str, size: int = 1200) -> str:
    if len(text) <= 2 * size:
        return text
    return f"{text[:size]}\n[... {len(text) - 2 * size} characters ...]\n{text[-size:]}"


def _replay_cases(lineage: dict) -> list[dict]:
    """Recent replies the brain wrote in the lineage's finished rounds, with the targets they answered.

    Replies that ended at the token limit lead: their unclosed fences are where extraction breaks.
    """

    cases: list[dict] = []
    for entry in lineage["rounds"]:
        log = Path(entry["log"])
        pool_path = log.parent / "pool.json"
        if not log.exists() or not pool_path.exists():
            continue
        targets = json.loads(pool_path.read_text(encoding="utf-8")).get("targets", {})
        replies = log.with_name(f"{entry['label']}.replies.jsonl")
        if replies.exists():
            rows = [json.loads(line) for line in replies.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            rows = [{"target": outcome["target"], "finish": outcome.get("finish"), "text": outcome["reply"]}
                    for outcome in json.loads(log.read_text(encoding="utf-8"))["history"] if outcome.get("reply")]
        cases += [{"target": targets[row["target"]], "finish": row.get("finish"), "text": row["text"]}
                  for row in rows if row.get("text") and row.get("target") in targets]
    risky = [case for case in cases if case["finish"] == "length"][-(REPLAY_CASES // 2):]
    rest = [case for case in cases if case["finish"] != "length"]
    return risky + rest[max(0, len(rest) - (REPLAY_CASES - len(risky))):]


def _replay_problems(policy: PolicyHost, cases: list[dict], expected: list[bool]) -> str:
    problems: list[str] = []
    for case, found in zip(cases, expected):
        try:
            parsed = policy.call("parse", case["text"], case["target"], timeout=REPLAY_TIMEOUT)
        except TimeoutError:
            problem = (f"parse() did not return within {REPLAY_TIMEOUT:.0f}s "
                       "(nested regex repetition backtracking over an unclosed fence is a usual cause)")
        except PolicyError as exc:
            problem = f"parse() raised:\n{str(exc)[-700:]}"
        else:
            if parsed is not None and not isinstance(parsed, str):
                problem = f"parse() returned {type(parsed).__name__}; it must return a str or None"
            elif found and not (parsed or "").strip():
                problem = "parse() found no replacement, while the parent's parse() extracted one from this reply"
            else:
                continue
        problems.append(f"{problem}\nThe reply, for {case['target']['id']} (finish={case['finish']}, "
                        f"{len(case['text'])} characters):\n{_excerpt(case['text'])}")
        if len(problems) == 3:
            break
    if not problems:
        return ""
    return "parse() mishandled replies the brain wrote in earlier rounds:\n\n" + "\n\n".join(problems)


def validate_policy(path: Path, cases: list[dict], expected: list[bool]) -> str:
    """The problems that keep a policy module out of a comparison, or "".

    Beyond calls on a sample view, parse() replays replies the brain wrote in earlier rounds: it must
    return promptly on each, and find a replacement wherever the parent found one.
    """

    view = _sample_view()
    identities = {target["id"] for target in view["targets"]}
    try:
        with PolicyHost(path) as policy:
            requests = policy.call("plan", view, timeout=PLAN_TIMEOUT)
            if not requests:
                return "plan() must return a non-empty list for a fresh arm with budget left"
            if len(requests) > view["slots"]:
                return "plan() returned more requests than view['slots']"
            for request in requests:
                if not isinstance(request, dict) or request.get("target") not in identities:
                    return "each request must be a dict naming one of view['targets'] by id"
                problem = _valid_messages(request.get("messages"), MAX_PROMPT_CHARS)
                if problem:
                    return f"plan() request: {problem}"
            reply = "Here it is:\n```python\ndef score(values):\n    return sum(v * v for v in values)\n```\n"
            parsed = policy.call("parse", reply, SAMPLE_TARGET, timeout=PARSE_TIMEOUT)
            if not isinstance(parsed, str) or "def score" not in parsed:
                return "parse() must return the def from a fenced python block"
            if policy.call("parse", "no code here", SAMPLE_TARGET, timeout=PARSE_TIMEOUT) not in (None, ""):
                return "parse() must return None when the reply holds no code"
            record = _sample_record(path.read_text(encoding="utf-8"))
            problem = _valid_messages(policy.call("successor_messages", record, timeout=PLAN_TIMEOUT),
                                      MAX_SUCCESSOR_PROMPT_CHARS)
            if problem:
                return f"successor_messages(): {problem}"
            return _replay_problems(policy, cases, expected)
    except (PolicyError, TimeoutError) as exc:
        return str(exc)[-2500:]


def _parent_finds(parent: PolicyHost, cases: list[dict]) -> list[bool]:
    """Whether the parent's parse() extracts a replacement from each replayed reply."""

    found = []
    for case in cases:
        try:
            parsed = parent.call("parse", case["text"], case["target"], timeout=REPLAY_TIMEOUT)
        except (PolicyError, TimeoutError):
            parsed = None
        found.append(isinstance(parsed, str) and bool(parsed.strip()))
    return found


def _ledger(lineage: dict, budget: dict) -> str:
    """Per-policy totals over every arm the lineage ran, for the author of the next successor.

    The histories show single outcomes; these totals show where each policy's budget went and how its arms
    ended, which the histories leave the reader to add up across many rounds."""

    names = {policy["sha256"]: name for name, policy in lineage["policies"].items()}
    totals: dict[str, dict] = {}
    best: list[tuple[float, str, str]] = []
    # Lineage-wide: how often an attempt verified, by its order on the target, by the previous outcome there,
    # and by the request's settings.
    by_order: dict[int, list[int]] = {}
    by_previous: dict[str, list[int]] = {}
    by_setting: dict[str, list[int]] = {}
    for entry in lineage["rounds"]:
        path = Path(entry["log"])
        if not path.exists():
            continue
        arm = json.loads(path.read_text(encoding="utf-8"))
        name = names.get(arm.get("policy_sha256"), f"{arm['policy']} (rejected candidate)")
        spent = arm.get("budget") or budget
        row = totals.setdefault(name, {
            "arms": 0, "targets": 0, "reading": 0.0, "calls": 0, "calls_budget": 0, "tokens": 0, "tokens_budget": 0,
            "completion": 0, "cut": 0, "after_verified": 0, "thinking": 0, "thinking_cut": 0,
            "stages": Counter(), "ended": Counter(),
        })
        row["arms"] += 1
        row["targets"] += len(arm["targets"])
        row["reading"] += arm["reading"]
        row["calls"] += arm["calls_used"]
        row["calls_budget"] += spent["calls"]
        row["tokens"] += arm["tokens_used"]
        row["tokens_budget"] += spent["tokens"]
        row["ended"][arm["ended"].split(":")[0]] += 1
        verified: set[str] = set()
        previous: dict[str, dict] = {}
        tried: Counter = Counter()
        for outcome in arm["history"]:
            row["stages"][outcome.get("stage")] += 1
            row["completion"] += outcome.get("completion_tokens", 0)
            row["cut"] += outcome.get("finish") == "length"
            row["thinking"] += bool(outcome.get("thinking"))
            row["thinking_cut"] += bool(outcome.get("thinking")) and outcome.get("finish") == "length"
            row["after_verified"] += outcome.get("target") in verified
            success = outcome.get("stage") == "verified"
            tried[outcome.get("target")] += 1
            by_order.setdefault(tried[outcome.get("target")], [0, 0])[0] += success
            by_order[tried[outcome.get("target")]][1] += 1
            for setting in (
                f"reasoning mode {'on' if outcome.get('thinking') else 'off'}",
                f"max_tokens {outcome.get('max_tokens')}",
                f"temperature {outcome.get('temperature')}",
                f"prompt {outcome.get('prompt_tokens', 0) // 1000}k-{outcome.get('prompt_tokens', 0) // 1000 + 1}k tokens",
            ):
                by_setting.setdefault(setting, [0, 0])[0] += success
                by_setting[setting][1] += 1
            before = previous.get(outcome.get("target"))
            if before is not None:
                kind = before.get("stage")
                if kind == "slower":
                    kind = "slower, ratio >= 1.0" if (before.get("ratio") or 0) >= 1.0 else "slower, ratio < 1.0"
                by_previous.setdefault(kind, [0, 0])[0] += success
                by_previous[kind][1] += 1
            previous[outcome.get("target")] = outcome
            if success:
                verified.add(outcome["target"])
        best += [(outcome["ratio"], identity, name) for identity, outcome in arm["best"].items()]
    lines = [
        "| policy | arms | reading per target | calls used / budget | tokens used / budget | completion tokens per call "
        "| replies cut at max_tokens | reasoning-mode calls (cut) | attempts on already verified targets | outcomes "
        "| how arms ended |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, row in totals.items():
        attempts = sum(row["stages"].values())
        lines.append(
            f"| {name} | {row['arms']} | {row['reading'] / max(1, row['targets']):.3f} | {row['calls']} / {row['calls_budget']} "
            f"| {row['tokens']} / {row['tokens_budget']} | {row['completion'] // max(1, attempts)} | {row['cut']} "
            f"| {row['thinking']} ({row['thinking_cut']}) | {row['after_verified']} | {dict(row['stages'].most_common())} "
            f"| {dict(row['ended'])} |"
        )
    lines += [""] + [
        f"{name} left {row['calls_budget'] - row['calls']} of {row['calls_budget']} calls and "
        f"{row['tokens_budget'] - row['tokens']} of {row['tokens_budget']} tokens unspent over its {row['arms']} arms."
        for name, row in totals.items() if name in lineage["policies"]
    ]
    lines += ["", "Verified attempts over all arms, by the attempt's order on its target: " + ", ".join(
        f"attempt {order}: {hits}/{count}" for order, (hits, count) in sorted(by_order.items())
    ) + ".", "Verified attempts after each previous outcome on the same target: " + ", ".join(
        f"after {kind}: {hits}/{count}" for kind, (hits, count) in sorted(by_previous.items(), key=lambda item: -item[1][1])
    ) + ".", "Verified attempts by request setting: " + ", ".join(
        f"{setting}: {hits}/{count}" for setting, (hits, count) in sorted(by_setting.items())
    ) + "."]
    lines += ["", "Largest verified speedups (target, policy):"]
    lines += [f"- {ratio:.2f}x {identity} ({name})" for ratio, identity, name in sorted(best, reverse=True)[:10]]
    lines += ["", "Matched successor trials (summed readings; per replicate group):"]
    for comparison in lineage["comparisons"]:
        child = names.get(_sha(Path(comparison["child_path"]).read_bytes())) if Path(comparison["child_path"]).exists() else None
        lines.append(f"- {comparison['parent']} vs {child or Path(comparison['child_path']).stem + ' (rejected candidate)'}: "
                     f"{comparison['readings']}, replicates {comparison['replicates']}, promoted {comparison['promoted']}")
    lines += ["", f"Promoted lineage: {' -> '.join(lineage['policies'])}.  A rejected candidate is an earlier attempt at a "
              "successor that lost its matched trial; its arms show what that attempt changed and how it fared."]
    return "\n".join(lines)


def breed(
    parent_path: Path, child_name: str, record: dict, cases: list[dict], brain: Brain, ledger: str,
) -> tuple[Path | None, dict]:
    trace: dict[str, Any] = {"parent": parent_path.stem, "child": child_name, "attempts": []}
    with PolicyHost(parent_path) as parent:
        try:
            messages = parent.call("successor_messages", record, timeout=PLAN_TIMEOUT)
        except (PolicyError, TimeoutError) as exc:
            trace["error"] = f"successor_messages() failed: {str(exc)[-900:]}"
            return None, trace
        expected = _parent_finds(parent, cases)
    trace["replay"] = {"cases": len(cases), "parent_found": sum(expected)}
    problem = _valid_messages(messages, MAX_SUCCESSOR_PROMPT_CHARS)
    if problem:
        trace["error"] = f"successor_messages(): {problem}"
        return None, trace
    # The harness's ledger follows the parent's own request, within the successor prompt limit.
    room = MAX_SUCCESSOR_PROMPT_CHARS - sum(len(message["content"]) for message in messages)
    heading = "\n\n## Lineage ledger (the harness's totals over every arm this lineage ran)\n"
    if room > len(heading) + 400:
        messages = messages[:-1] + [{**messages[-1], "content": messages[-1]["content"] + heading + ledger[: room - len(heading)]}]
        trace["ledger_chars"] = min(len(ledger), room - len(heading))
    trace["thinking"] = True
    candidates = HOME / "policies" / "candidates"
    candidates.mkdir(parents=True, exist_ok=True)
    stem = f"{child_name}-{_stamp()}"
    # Diagnosis first: the successor is written against a chosen, evidenced change to the parent's method.
    request = messages[-1]["content"]
    diagnosis = brain.complete(
        messages[:-1] + [{**messages[-1], "content": request + DIAGNOSIS_REQUEST}],
        max_tokens=DIAGNOSIS_COMPLETION, temperature=0.6, thinking=True, seed=len(record.get("comparisons", [])) * 17,
    )
    (candidates / f"{stem}.diagnosis.md").write_text(
        diagnosis["text"] + "\n\n---- reasoning ----\n\n" + diagnosis["reasoning"], encoding="utf-8")
    trace["diagnosis"] = {"text": diagnosis["text"][-6000:], "prompt_tokens": diagnosis["prompt_tokens"],
                          "completion_tokens": diagnosis["completion_tokens"], "finish": diagnosis.get("finish"),
                          "seconds": diagnosis["seconds"]}
    _log(f"breed {child_name} diagnosis: {diagnosis['completion_tokens']} tok, finish {diagnosis.get('finish')}")
    if diagnosis["text"].strip():
        messages = messages[:-1] + [
            {**messages[-1], "content": request + DIAGNOSIS_REQUEST},
            {"role": "assistant", "content": diagnosis["text"][-12_000:]},
            {"role": "user", "content": WRITE_REQUEST},
        ]
    for attempt in range(3):
        # Reasoning mode: writing the next improver is the one call where deliberation pays for every later round.
        reply = brain.complete(messages, max_tokens=SUCCESSOR_COMPLETION, temperature=0.6, thinking=True,
                               seed=len(record.get("comparisons", [])) * 17 + attempt)
        source = _extract_module(reply["text"])
        path = candidates / f"{stem}-{attempt}.py"
        path.with_suffix(".reply.md").write_text(reply["text"], encoding="utf-8")
        path.with_suffix(".reasoning.md").write_text(reply["reasoning"], encoding="utf-8")
        error = ""
        if not source.strip():
            error = "the reply held no ```python block with the module"
            if reply.get("finish") == "length":
                error += " (the reply hit the token limit; write a more compact module)"
        else:
            path.write_text(source, encoding="utf-8")
            error = validate_policy(path, cases, expected)
        trace["attempts"].append({"path": str(path), "error": error, "prompt_tokens": reply["prompt_tokens"],
                                  "completion_tokens": reply["completion_tokens"], "seconds": reply["seconds"]})
        _log(f"breed {child_name} attempt {attempt}: {'valid' if not error else error[-240:]!r}")
        if not error:
            return path, trace
        messages = messages + [
            {"role": "assistant", "content": reply["text"][-24_000:]},
            {"role": "user", "content": f"That module failed validation:\n{error}\n\nReturn the complete corrected module in one ```python block."},
        ]
        if sum(len(message["content"]) for message in messages) > MAX_SUCCESSOR_PROMPT_CHARS + 30_000:
            messages = messages[:1] + messages[-3:]
    return None, trace


def _waiting_successor(lineage: dict, parent_path: Path, child: str, cases: list[dict]) -> Path | None:
    """A bred successor that never reached a comparison and passes the validation in force now."""

    judged = {entry["child_path"] for entry in lineage["comparisons"]}
    waiting = [entry for trace in reversed(lineage["breeding"])
               if trace["parent"] == parent_path.stem and trace["child"] == child
               for entry in trace["attempts"]
               if not entry["error"] and entry["path"] not in judged and Path(entry["path"]).exists()]
    if not waiting:
        return None
    with PolicyHost(parent_path) as parent:
        expected = _parent_finds(parent, cases)
    for entry in waiting:
        entry["error"] = validate_policy(Path(entry["path"]), cases, expected)
        _write_json(LINEAGE, lineage)
        if not entry["error"]:
            return Path(entry["path"])
    return None


# ------------------------------------------------------------------------ lineage


def load_lineage() -> dict:
    if LINEAGE.exists():
        lineage = json.loads(LINEAGE.read_text(encoding="utf-8"))
    else:
        seed = POLICY_DIR / "m0.py"
        lineage = {
            "created": _stamp(),
            "anchor_sha256": anchor_sha(),
            "current": "m0",
            "policies": {"m0": {"path": str(seed), "sha256": _sha(seed.read_bytes()), "parent": None, "created": _stamp()}},
            "rounds": [],
            "comparisons": [],
            "breeding": [],
            "adoptions": [],
            "used_targets": [],
        }
        _write_json(LINEAGE, lineage)
    if lineage["anchor_sha256"] != anchor_sha():
        raise RuntimeError("anchor_worker.py changed since the lineage began; its yardstick is no longer the same")
    return lineage


def reanchor(why: str) -> dict:
    """Adopt the current anchor_worker.py as the lineage's yardstick.

    Every comparison runs its parent and child arms inside one bench on one anchor, so a new anchor never
    splits a comparison; the change is recorded so readings before and after it are read against their own
    yardstick.
    """

    lineage = json.loads(LINEAGE.read_text(encoding="utf-8"))
    new = anchor_sha()
    if lineage["anchor_sha256"] != new:
        lineage.setdefault("anchor_changes", []).append({
            "from": lineage["anchor_sha256"], "to": new, "at": _stamp(), "why": why,
            "rounds_before": len(lineage["rounds"]), "comparisons_before": len(lineage["comparisons"]),
        })
        lineage["anchor_sha256"] = new
        _write_json(LINEAGE, lineage)
    return lineage


def _round_summary(arm: dict) -> dict:
    return {key: value for key, value in arm.items() if key not in ("best", "history")} | {
        "improved": {identity: outcome["ratio"] for identity, outcome in arm["best"].items()},
    }


def _record_for(lineage: dict, generation: int, parent: str, budget: dict) -> dict:
    parent_path = Path(lineage["policies"][parent]["path"])
    promoted = {policy["sha256"]: name for name, policy in lineage["policies"].items()}
    rounds: list[dict] = []
    for entry in reversed(lineage["rounds"]):
        path = Path(entry["log"])
        if path.exists():
            arm = json.loads(path.read_text(encoding="utf-8"))
            rounds.insert(0, {key: arm[key] for key in (
                "label", "reading", "verified", "attempts", "calls_used", "tokens_used", "ended", "stages", "history",
            )} | {
                "policy": promoted.get(arm.get("policy_sha256"), f"{arm['policy']} (rejected candidate)"),
                "budget": arm.get("budget") or budget,
            })
            if len(rounds) == 6:
                break
    return {
        "generation": generation + 1,
        "parent": parent,
        "parent_source": parent_path.read_text(encoding="utf-8"),
        "interface": POLICY_INTERFACE,
        "rules": RULES,
        "rounds": rounds,
        "comparisons": lineage["comparisons"],
        "limits": {"prompt_chars": MAX_SUCCESSOR_PROMPT_CHARS, "completion_tokens": SUCCESSOR_COMPLETION},
    }


# ---------------------------------------------------------------------- adoption


def _module_tests(module: str) -> list[Path]:
    pattern = re.compile(rf"^\s*(from|import)\s+{re.escape(module)}\b", re.M)
    found = []
    for path in sorted(LIVE.glob("test_*.py")) + sorted((LIVE / "tests").rglob("test_*.py")):
        try:
            if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                found.append(path)
        except OSError:
            continue
    return sorted(found, key=lambda path: path.stat().st_size)[:8]


def _run_tests(files: list[Path]) -> dict[str, str]:
    """Failing test files mapped to their tail output."""

    def one(path: Path) -> tuple[str, str]:
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", str(path)],
                capture_output=True, text=True, timeout=900, cwd=str(LIVE),
            )
        except subprocess.TimeoutExpired:
            return path.name, "timed out"
        return path.name, "" if completed.returncode == 0 else (completed.stdout + completed.stderr)[-1200:]

    if not files:
        return {}
    with ThreadPoolExecutor(min(6, len(files))) as executor:
        results = list(executor.map(one, files))
    return {name: output for name, output in results if output}


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPOSITORY), *args], capture_output=True, text=True)


def adopt(patches: list[dict], reason: str) -> list[dict]:
    """Apply verified rewrites to the live source, one at a time, each re-checked on the live tree."""

    results: list[dict] = []
    if not patches:
        return results
    dump = HOME / "tmp" / f"live-dump-{uuid.uuid4().hex}.json"
    live_base = run_anchor(LIVE, dump=dump)
    dump.unlink(missing_ok=True)
    if not live_base.get("ok"):
        return [{"target": patch["target"]["id"], "adopted": False, "why": f"the live anchor fails: {live_base.get('error')}"} for patch in patches]
    digests = {name: value["digest"] for name, value in live_base["workloads"].items()}
    durable = {name: (value["fsync"], value["replace"]) for name, value in live_base["workloads"].items()}
    for patch in sorted(patches, key=lambda item: -item["ratio"]):
        target = patch["target"]
        path = LIVE / target["file"]
        entry = {"target": target["id"], "ratio": patch["ratio"], "file": target["file"], "adopted": False}
        results.append(entry)
        before = path.read_text(encoding="utf-8")
        if before.count(target["source"]) != 1:
            entry["why"] = "the live function changed since the snapshot"
            continue
        after = before.replace(target["source"], patch["block"], 1)
        try:
            compile(after, str(path), "exec")
        except SyntaxError as exc:
            entry["why"] = f"the live module does not compile with the rewrite: {exc}"
            continue
        relative = f"{LIVE.name}/{target['file']}"
        clean = _git("diff", "--quiet", "HEAD", "--", relative).returncode == 0 and \
            _git("ls-files", "--error-unmatch", relative).returncode == 0
        path.write_text(after, encoding="utf-8")

        def revert(why: str) -> None:
            if path.read_text(encoding="utf-8") == after:
                path.write_text(before, encoding="utf-8")
                entry["why"] = why
            else:
                entry["why"] = why + "; the file changed meanwhile, so it was left as found"

        check = run_anchor(LIVE)
        if not check.get("ok"):
            revert(f"the live anchor failed with the rewrite: {check.get('error')}")
            continue
        if {name: value["digest"] for name, value in check["workloads"].items()} != digests or any(
            check["workloads"][name]["fsync"] < fsync or check["workloads"][name]["replace"] < replace
            for name, (fsync, replace) in durable.items()
        ):
            revert("the live anchor output or durable writes changed with the rewrite")
            continue
        tests = _module_tests(target["module"])
        failures = _run_tests(tests)
        if failures:
            if path.read_text(encoding="utf-8") == after:
                path.write_text(before, encoding="utf-8")
                baseline = _run_tests([test for test in tests if test.name in failures])
                if set(baseline) == set(failures):
                    path.write_text(after, encoding="utf-8")
                    entry["preexisting_failures"] = sorted(failures)
                else:
                    entry["why"] = f"tests failed with the rewrite: {sorted(set(failures) - set(baseline))}"
                    entry["test_output"] = {name: failures[name] for name in set(failures) - set(baseline)}
                    continue
            else:
                entry["why"] = "the file changed during testing; left as found"
                continue
        entry["tests"] = [test.name for test in tests]
        entry["adopted"] = True
        if clean:
            message = f"CassiFI self-improvement: {target['id']} {patch['ratio']:.2f}x faster ({reason})"
            committed = _git("commit", "-q", "-m", message, "--", relative)
            entry["commit"] = _git("rev-parse", "--short", "HEAD").stdout.strip() if committed.returncode == 0 else None
            if committed.returncode != 0:
                entry["commit_error"] = committed.stderr[-400:]
        _log(f"adopted {target['id']} {patch['ratio']:.3f}x into live source" + (f" (commit {entry.get('commit')})" if clean else ""))
    return results


def _patches_from(arms: list[dict], bench: Bench) -> list[dict]:
    best: dict[str, dict] = {}
    for arm in arms:
        for identity, outcome in arm["best"].items():
            if identity not in best or outcome["ratio"] > best[identity]["ratio"]:
                best[identity] = {"target": bench.pool[identity], "ratio": outcome["ratio"], "block": outcome["block"],
                                  "arm": arm["label"]}
    return list(best.values())


# -------------------------------------------------------------------- succession


def prepare_bench(label: str, run_dir: Path, lineage: dict, sizes: list[int], *, held_out: bool) -> tuple[Bench, list[list[str]]]:
    """A fresh snapshot of the live tree, its measured pool, and target groups for the coming arms.

    Held-out groups contain only functions no policy of the lineage has attempted.  Live rounds first
    revisit attempted functions that remain unimproved, then take untouched ones.  Untouched functions
    alternate between the two uses so later successor trials still meet comparable work.
    """

    snapshot = take_snapshot(label)
    profile = profile_snapshot(snapshot)
    pool = build_pool(snapshot, profile["rows"])
    used = set(lineage["used_targets"])
    adopted = {entry["target"] for entry in lineage["adoptions"] if entry.get("adopted")}
    fresh = [target for target in pool if target["id"] not in used]
    ordered = fresh[0::2] + fresh[1::2]
    if not held_out:
        ordered = [target for target in pool if target["id"] in used and target["id"] not in adopted] + ordered
    # Timing noise drops a share of measured functions, so the bench measures twice the groups' need.
    bench = Bench(snapshot, ordered[: 2 * sum(sizes) + 4], run_dir / "bench", profile["touched"])
    bench.calibrate()
    groups = [bench.ids[index::len(sizes)][:size] for index, size in enumerate(sizes)]
    _write_json(run_dir / "pool.json", {
        "snapshot": str(snapshot.root),
        "pool": [{"id": t["id"], "profile": t["profile"]} for t in pool],
        "measured": [{"id": t["id"], "base": t.get("base")} for t in bench.pool.values()],
        "dropped": bench.dropped,
        "unsteady_workloads": bench.unsteady,
        "groups": groups,
        "targets": bench.pool,
    })
    _log(f"{label}: snapshot {snapshot.root.name}, pool {len(pool)}, measured {len(bench.ids)} "
         f"({len(bench.dropped)} dropped, {len(bench.unsteady)} unsteady workloads), groups {groups}")
    return bench, groups


def _save_arm(arm: dict, run_dir: Path) -> Path:
    path = run_dir / f"{arm['label']}.json"
    _write_json(path, arm)
    return path


def _matched_arms(
    prefix: str, policies: dict[str, Path], bench: Bench, groups: list[list[str]], *,
    calls: int, tokens: int, seed: int, brain: Brain, log_dir: Path,
) -> dict[tuple[int, str], dict]:
    """Every policy spends the same budget on every replicate group of one bench, all arms at once.

    Arms on one group share their brain seeds, so the policies differ only in what they ask the brain."""

    jobs = [(replicate, name, path) for replicate in range(len(groups)) for name, path in policies.items()]
    with ThreadPoolExecutor(len(jobs)) as executor:
        futures = {
            (replicate, name): executor.submit(
                run_arm, f"{prefix}-r{replicate}-{name}", path, bench, groups[replicate],
                calls=calls, tokens=tokens, slots=1, seed=seed + replicate, brain=brain, log_dir=log_dir,
            )
            for replicate, name, path in jobs
        }
        return {key: future.result() for key, future in futures.items()}


def succession(
    generations: int, *, calls: int, tokens: int, train_size: int, test_size: int, replicates: int,
    breed_tries: int, seed: int,
) -> dict:
    brain = Brain()
    lineage = load_lineage()
    for _ in range(generations):
        parent = lineage["current"]
        parent_path = Path(lineage["policies"][parent]["path"])
        generation = int(parent[1:])
        label = f"g{generation}-live-{parent}"
        finished = next((entry for entry in lineage["rounds"] if entry["label"] == label and Path(entry["log"]).exists()), None)
        if finished is not None:
            # The current improver already ran and adopted its live round; breed from that evidence.
            live = json.loads(Path(finished["log"]).read_text(encoding="utf-8"))
            run_dir = Path(finished["log"]).parent.parent
            _log(f"resuming after {label}: reading {live['reading']}, verified {live['verified']}")
        else:
            run_dir = HOME / "runs" / f"{_stamp()}-g{generation}"
            # The current improver's live round on the live tree.
            bench, (train,) = prepare_bench(f"g{generation}-live", run_dir / "live", lineage, [train_size], held_out=False)
            _log(f"live round {parent} on {train}")
            live = run_arm(label, parent_path, bench, train, calls=calls, tokens=tokens,
                           slots=4, seed=seed + generation, brain=brain, log_dir=run_dir / "live")
            lineage["used_targets"] = sorted(set(lineage["used_targets"]) | set(train))
            lineage["rounds"].append({"label": label, "log": str(_save_arm(live, run_dir / "live")), **_round_summary(live)})
            _write_json(LINEAGE, lineage)
            lineage["adoptions"] += adopt(_patches_from([live], bench), f"live round of {parent}")
            _write_json(LINEAGE, lineage)
        _log(f"live round reading {live['reading']:.4f}, verified {live['verified']}, stages {live['stages']}")
        # The current improver writes its successor; promotion needs a matched win on untouched functions,
        # summed over independent replicate groups so one lucky group cannot carry it.
        child = f"m{generation + 1}"
        for attempt in range(breed_tries):
            # A successor that passed validation but never reached its comparison gets that trial first.
            cases = _replay_cases(lineage)
            child_path = _waiting_successor(lineage, parent_path, child, cases)
            if child_path is not None:
                _log(f"{child} candidate {child_path.name} passes validation and takes its comparison")
            else:
                budget = {"calls": calls, "tokens": tokens}
                record = _record_for(lineage, generation, parent, budget)
                child_path, trace = breed(parent_path, child, record, cases, brain, _ledger(lineage, budget))
                lineage["breeding"].append(trace)
                _write_json(LINEAGE, lineage)
                if child_path is None:
                    _log(f"breeding {child} failed: {trace.get('error') or trace['attempts'][-1]['error'][:300]}")
                    continue
            compare_dir = run_dir / f"compare-{attempt}-{_stamp()}"
            bench, groups = prepare_bench(f"g{generation}-compare-{attempt}", compare_dir, lineage,
                                          [test_size] * replicates, held_out=True)
            if not all(groups):
                _log("the pool has no untouched functions left for a matched comparison")
                return lineage
            _log(f"comparison {parent} vs {child} on {groups}")
            # The comparison index keeps arm labels unique when a restarted engine repeats an attempt number.
            results = _matched_arms(
                f"g{generation}-c{len(lineage['comparisons'])}", {parent: parent_path, child: child_path}, bench, groups,
                calls=calls, tokens=tokens, seed=seed + 100 * (generation + 1) + 10 * attempt, brain=brain,
                log_dir=compare_dir,
            )
            lineage["used_targets"] = sorted(set(lineage["used_targets"]).union(*groups))
            for arm in results.values():
                lineage["rounds"].append({"label": arm["label"], "log": str(_save_arm(arm, compare_dir)), **_round_summary(arm)})
            per_replicate = [
                {name: results[(replicate, name)]["reading"] for name in (parent, child)} for replicate in range(len(groups))
            ]
            readings = {name: round(sum(entry[name] for entry in per_replicate), 5) for name in (parent, child)}
            promoted = readings[child] > readings[parent]
            comparison = {
                "parent": parent, "child": child, "child_path": str(child_path), "groups": groups,
                "readings": readings,
                "replicates": per_replicate,
                "replicate_wins": sum(entry[child] > entry[parent] for entry in per_replicate),
                "verified": {name: sum(results[(r, name)]["verified"] for r in range(len(groups))) for name in (parent, child)},
                "tokens": {name: sum(results[(r, name)]["tokens_used"] for r in range(len(groups))) for name in (parent, child)},
                "calls": {name: sum(results[(r, name)]["calls_used"] for r in range(len(groups))) for name in (parent, child)},
                "budget_per_arm": {"calls": calls, "tokens": tokens},
                "promoted": promoted,
            }
            lineage["comparisons"].append(comparison)
            _write_json(LINEAGE, lineage)
            lineage["adoptions"] += adopt(_patches_from(list(results.values()), bench), f"comparison {parent} vs {child}")
            _log(f"comparison readings {readings} replicates {per_replicate} -> "
                 f"{'promote ' + child if promoted else 'keep ' + parent}")
            if promoted:
                inherited = POLICY_DIR / f"{child}.py"
                shutil.copy2(child_path, inherited)
                lineage["policies"][child] = {"path": str(inherited), "sha256": _sha(inherited.read_bytes()),
                                              "parent": parent, "created": _stamp()}
                lineage["current"] = child
                _write_json(LINEAGE, lineage)
                break
            _write_json(LINEAGE, lineage)
        else:
            _log(f"{parent} remains the improver after {breed_tries} successor trials")
            break
    return lineage


def crosscheck(names: list[str], *, calls: int, tokens: int, size: int, replicates: int, seed: int) -> dict:
    """Several generations of the lineage on the same untouched functions under the same budget.

    A promotion compares one generation with its parent; this reading shows whether the gains accumulate
    along the chain.  Its arms stay out of the successor's evidence, and its verified rewrites are adopted.
    It writes the lineage, so it runs while no succession is running."""

    brain = Brain()
    lineage = load_lineage()
    policies = {name: Path(lineage["policies"][name]["path"]) for name in names}
    index = len(lineage.setdefault("crosschecks", []))
    run_dir = HOME / "runs" / f"{_stamp()}-crosscheck-{index}"
    bench, groups = prepare_bench(f"crosscheck-{index}", run_dir, lineage, [size] * replicates, held_out=True)
    if not all(groups):
        raise RuntimeError("the pool has no untouched functions left for a matched crosscheck")
    _log(f"crosscheck {' vs '.join(names)} on {groups}")
    results = _matched_arms(f"x{index}", policies, bench, groups, calls=calls, tokens=tokens,
                            seed=seed + 10_000 * (index + 1), brain=brain, log_dir=run_dir)
    lineage["used_targets"] = sorted(set(lineage["used_targets"]).union(*groups))
    per_replicate = [{name: results[(replicate, name)]["reading"] for name in names} for replicate in range(len(groups))]
    entry = {
        "at": _stamp(),
        "policies": names,
        "groups": groups,
        "readings": {name: round(sum(row[name] for row in per_replicate), 5) for name in names},
        "replicates": per_replicate,
        "verified": {name: sum(results[(r, name)]["verified"] for r in range(len(groups))) for name in names},
        "tokens": {name: sum(results[(r, name)]["tokens_used"] for r in range(len(groups))) for name in names},
        "calls": {name: sum(results[(r, name)]["calls_used"] for r in range(len(groups))) for name in names},
        "budget_per_arm": {"calls": calls, "tokens": tokens},
        "logs": {arm["label"]: str(_save_arm(arm, run_dir)) for arm in results.values()},
    }
    lineage["crosschecks"].append(entry)
    _write_json(LINEAGE, lineage)
    lineage["adoptions"] += adopt(_patches_from(list(results.values()), bench), f"crosscheck of {', '.join(names)}")
    _write_json(LINEAGE, lineage)
    _log(f"crosscheck readings {entry['readings']} replicates {per_replicate}")
    return entry


def status() -> None:
    lineage = load_lineage()
    print(f"current improver: {lineage['current']}")
    for name, policy in lineage["policies"].items():
        print(f"  {name}: parent {policy['parent']}, {policy['path']}")
    for comparison in lineage["comparisons"]:
        print(f"  {comparison['parent']} vs {comparison['child']}: {comparison['readings']} promoted={comparison['promoted']}")
    for check in lineage.get("crosschecks", []):
        print(f"  crosscheck {' vs '.join(check['policies'])}: {check['readings']} replicates {check['replicates']}")
    adopted = [entry for entry in lineage["adoptions"] if entry.get("adopted")]
    print(f"adopted rewrites: {len(adopted)}")
    for entry in adopted:
        print(f"  {entry['target']} {entry['ratio']}x commit={entry.get('commit')}")


def _end_children_with_engine() -> None:
    """Windows leaves children running when their parent dies, so a stopped engine used to strand policy hosts
    spinning in a runaway parse.  Joining a kill-on-close job ends the whole process tree with the engine."""

    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimits), ("IoInfo", ctypes.c_ulonglong * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not (job and kernel32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
            and kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())):
        print(f"children are not bound to the engine (Windows error {ctypes.get_last_error()})", file=sys.stderr)
    # The job handle stays open for the life of this process; the system closes it at exit.


def _gpu_used_mb() -> float:
    script = r"(Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage').CounterSamples | Measure-Object CookedValue -Sum | ForEach-Object Sum"
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=120)
    return float(result.stdout.strip() or 0) / 2**20


def start_brain_when_room() -> int:
    """Start the lineage's brain once the GPU holds room for it; other sessions' GPU work keeps running."""

    brain = Brain()
    with contextlib.suppress(urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        with urllib.request.urlopen(brain.url + "/health", timeout=10):
            _log(f"the brain at {brain.url} is already up")
            return 0
    announced = False
    while (free := GPU_MEMORY_MB - _gpu_used_mb()) < BRAIN_VRAM_MB:
        if not announced:
            _log(f"{free:.0f} MB of GPU memory free; the brain starts once {BRAIN_VRAM_MB} MB are")
            announced = True
        time.sleep(60)
    with (HOME / "brain.log").open("ab") as log:
        subprocess.Popen(BRAIN_SERVER, cwd=LIVE.parent, stdout=log, stderr=subprocess.STDOUT,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                         | subprocess.CREATE_BREAKAWAY_FROM_JOB)
    brain._wait_until_present()
    _log(f"the brain at {brain.url} is up ({free:.0f} MB were free)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("succession")
    run.add_argument("--generations", type=int, default=2)
    run.add_argument("--calls", type=int, default=12)
    run.add_argument("--tokens", type=int, default=60_000)
    run.add_argument("--train-size", type=int, default=6)
    run.add_argument("--test-size", type=int, default=4)
    run.add_argument("--replicates", type=int, default=2)
    run.add_argument("--breed-tries", type=int, default=2)
    run.add_argument("--seed", type=int, default=7)
    commands.add_parser("status")
    check = commands.add_parser("crosscheck", help="several generations on the same untouched functions and budget")
    check.add_argument("policies", nargs="+")
    check.add_argument("--calls", type=int, default=12)
    check.add_argument("--tokens", type=int, default=60_000)
    check.add_argument("--size", type=int, default=4)
    check.add_argument("--replicates", type=int, default=3)
    check.add_argument("--seed", type=int, default=7)
    anchor = commands.add_parser("reanchor", help="adopt the current anchor_worker.py as the lineage's yardstick")
    anchor.add_argument("--why", required=True)
    host = commands.add_parser("policy-host", help="serve one policy module over stdin/stdout (used by PolicyHost)")
    host.add_argument("path")
    commands.add_parser("brain", help="start the lineage's brain once the GPU has room for it")
    args = parser.parse_args(argv)
    if args.command == "policy-host":
        return serve_policy(Path(args.path))
    if args.command == "brain":
        return start_brain_when_room()
    _end_children_with_engine()
    if args.command == "status":
        status()
        return 0
    if args.command == "reanchor":
        lineage = reanchor(args.why)
        print(f"anchor {lineage['anchor_sha256'][:16]}; changes recorded: {len(lineage.get('anchor_changes', []))}")
        return 0
    if args.command == "crosscheck":
        crosscheck(args.policies, calls=args.calls, tokens=args.tokens, size=args.size, replicates=args.replicates,
                   seed=args.seed)
        status()
        return 0
    succession(args.generations, calls=args.calls, tokens=args.tokens, train_size=args.train_size,
               test_size=args.test_size, replicates=args.replicates, breed_tries=args.breed_tries, seed=args.seed)
    status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
