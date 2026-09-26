"""Run one live research episode through the field-brain entity.

The entity's research director is exercised against a real llama.cpp server and
real CassiTheory sources: two programs are created, one is paused and resumed,
a cycle runs through a mid-flight brain outage and a fresh server on the same
port, a second cycle is cancelled while it runs, the entity is closed and
reopened, and the whole state must come back unchanged and the work must
continue. A program that reaches its own terminal state is succeeded by a fresh
one, so every exercise runs against live work.

Usage (from the repository root):

    python CassiQwen/verify_research_episode_live.py
    python CassiQwen/verify_research_episode_live.py --model <path.gguf> --server-dir <Release dir>

Exit code 0 only when every required observation holds; the JSON receipt
(default `CassiQwen/_diag/research-episode/latest.json`) lists each step, the
program views, and any failed requirement.
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "CassiQwen/Qwen3.5-0.8B-Q4_0.gguf"
DEFAULT_SERVER_DIR = "CassiQwen/native/llama.cpp/b8-stream/bin/Release"
DEFAULT_NATIVE_DIR = "CassiFI/native/field-runtime/build/Release"
MEMORY_QUESTION = "Which term in the two-fluid equations sets the memory time?"
SIDECAR_QUESTION = "Which solver files implement the damping update?"


class Episode:
    """One live episode: server lifecycle, entity state, observations, failures."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.workspace = Path(args.workspace).resolve()
        self.model = (self.workspace / args.model).resolve()
        self.server_dir = (self.workspace / args.server_dir).resolve()
        self.native_dir = (self.workspace / args.native_dir).resolve()
        self.scratch = Path(args.scratch).resolve() if args.scratch else Path(
            tempfile.mkdtemp(prefix="research-episode-", dir=self.workspace / "CassiQwen" / "_diag")
        )
        self.receipt_path = Path(args.receipt).resolve() if args.receipt else (
            self.scratch / "summary.json" if args.scratch else self.scratch.parent / "latest.json"
        )
        self.started = time.monotonic()
        self.steps: list[dict[str, Any]] = []
        self.failures: list[str] = []
        self.server: subprocess.Popen[bytes] | None = None
        self.entity: Any = None

    # -- observations ---------------------------------------------------------
    def note(self, step: str, **fields: Any) -> dict[str, Any]:
        row = {"step": step, "t": round(time.monotonic() - self.started, 1),
               **{key: value for key, value in fields.items() if value is not None}}
        self.steps.append(row)
        print(json.dumps(row, default=str)[:700], flush=True)
        return row

    def require(self, condition: Any, description: str, **detail: Any) -> bool:
        if condition:
            return True
        self.failures.append(f"{description} ({json.dumps(detail, default=str)[:300]})")
        return False

    # -- server ---------------------------------------------------------------
    @staticmethod
    def free_port() -> int:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def start_server(self, port: int) -> subprocess.Popen[bytes]:
        log = open(self.scratch / f"server-{port}.log", "a", encoding="utf-8")
        process = subprocess.Popen(
            [str(self.scratch / "server" / "llama-server.exe"),
             "--model", str(self.model), "--host", "127.0.0.1", "--port", str(port),
             "--ctx-size", "16384", "--parallel", "1", "--threads", "8",
             "--device", "none", "--gpu-layers", "0", "--no-cassi-modal"],
            stdout=log, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"llama-server exited {process.returncode}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                    if response.status == 200:
                        return process
            except OSError:
                pass
            time.sleep(0.25)
        process.kill()
        raise RuntimeError("llama-server did not become healthy")

    def stop_server(self) -> None:
        if self.server is not None and self.server.poll() is None:
            self.server.kill()
            self.server.wait(timeout=30)
        self.server = None

    # -- entity ---------------------------------------------------------------
    def open_entity(self, port: int) -> Any:
        from cassi_field_brain_entity import open_local_entity

        return open_local_entity(
            self.scratch / "home",
            model_url=f"http://127.0.0.1:{port}",
            model_path=self.model,
            brain_backend="external",
            capability_root=self.workspace / "CassiQwen",
            theory_root=self.workspace / "CassiTheory",
            research_home=self.scratch / "research",
            research_roots=(self.workspace / "CassiTheory" / "two-fluid",),
            research_resident_enabled=True,
            program_native_enabled=True,
            program_native_runtime_executable=self.scratch / "native" / "cassifi-field-runtime.exe",
            max_response_tokens=768,
        )

    # -- program helpers ------------------------------------------------------
    def program_view(self, director: Any, program_id: str) -> dict[str, Any]:
        program = director.store.program(program_id)
        return {
            "status": program.get("status"),
            "cycles_completed": program.get("cycles_completed"),
            "claims": len(program.get("claims") or ()),
            "methods": len(program.get("methods") or ()),
            "frontier": len(program.get("frontier") or ()),
            "last_error": program.get("last_error"),
        }

    def last_claim(self, director: Any, program_id: str) -> str | None:
        claims = director.store.program(program_id).get("claims") or ()
        return claims[-1].get("finding") if claims else None

    def create(self, director: Any, program_id: str, question: str, cycle_limit: int) -> None:
        director.create_program(
            request_id=f"create-{program_id}",
            program_id=program_id,
            project_id="two-fluid",
            title="Damping and memory in the two-fluid field",
            mission=(
                "Establish from the two-fluid theory documents and solvers how the damping "
                "terms control how long the field remembers past forcing."
            ),
            initial_question=question,
            observed_at="2026-09-25T00:00:00Z",
            cycle_limit=cycle_limit,
        )

    @staticmethod
    def attempt(fn: Any) -> Any:
        try:
            return fn()
        except BaseException as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {exc}"

    def active_line(self, director: Any, stem: str, question: str, cycle_limit: int,
                    avoid_blocked: bool = False) -> str:
        """The live program on this line, creating a successor if one settled.

        `avoid_blocked` treats a program the director blocked on an unresolved
        effect as settled too, so the episode continues on a fresh line instead
        of retrying a reference that has no artifact behind it.
        """
        settled = {"completed", "cancelled", "canceled", "failed"}
        if avoid_blocked:
            settled.add("blocked")
        live = [str(row.get("program_id")) for row in director.store.programs()
                if str(row.get("program_id") or "") == stem
                or str(row.get("program_id") or "").startswith(f"{stem}-")]
        for program_id in sorted(live, reverse=True):
            if director.store.program(program_id).get("status") not in settled:
                return program_id
        successor = f"{stem}-{len(live) + 1}"
        self.create(director, successor, question, cycle_limit)
        self.note("successor-created", program=successor, of=stem)
        return successor

    def activate(self, director: Any, program_id: str, tag: str) -> None:
        status = director.store.program(program_id).get("status")
        if status in {"blocked", "paused", "waiting"}:
            director.control_program(request_id=f"resume-{program_id}-{tag}", program_id=program_id,
                                     action="resume", observed_at="2026-09-25T00:30:00Z")
            self.note("reactivated", program=program_id, was=status,
                      now=director.store.program(program_id).get("status"))

    def run_cycle(self, director: Any, program_id: str, expect: str) -> dict[str, Any]:
        """Run one cycle in the foreground and return what happened."""
        outcome: dict[str, Any] = {}

        def worker() -> None:
            try:
                outcome["result"] = director.run_one(program_id=program_id)
            except BaseException as exc:  # noqa: BLE001
                outcome["error"] = f"{type(exc).__name__}: {exc}"

        thread = threading.Thread(target=worker)
        thread.start()
        if expect == "cancel":
            time.sleep(3.0)
            try:
                outcome["control"] = director.control_program(
                    request_id=f"cancel-{program_id}", program_id=program_id, action="cancel",
                    observed_at="2026-09-25T00:20:00Z").get("status")
            except BaseException as exc:  # noqa: BLE001
                outcome["control_error"] = f"{type(exc).__name__}: {exc}"
        thread.join(timeout=1800)
        outcome["still_running"] = thread.is_alive()
        return outcome

    # -- episode --------------------------------------------------------------
    def staging(self) -> None:
        self.scratch.mkdir(parents=True, exist_ok=True)
        for label, source in (("native", self.native_dir), ("server", self.server_dir)):
            target = self.scratch / label
            shutil.rmtree(target, ignore_errors=True)
            target.mkdir()
            for built in source.iterdir():
                if built.suffix.lower() in {".exe", ".dll"}:
                    shutil.copy2(built, target / built.name)

    def run(self) -> int:
        self.staging()
        port = self.free_port()
        self.server = self.start_server(port)
        self.note("server-ready", port=port)
        self.entity = self.open_entity(port)
        director = self.entity.researcher
        cursor = 0
        status_before: dict[str, Any] = {}
        try:
            self.create(director, "memory", MEMORY_QUESTION, 3)
            self.create(director, "sidecar", SIDECAR_QUESTION, 3)
            memory = "memory"
            sidecar = "sidecar"
            created = {"memory": self.program_view(director, memory),
                       "sidecar": self.program_view(director, sidecar)}
            self.note("created", **created)
            self.require(created["memory"]["status"] == "active"
                         and created["sidecar"]["status"] == "active",
                         "both programs are active after creation", views=created)

            paused = director.control_program(request_id="pause-memory", program_id=memory, action="pause",
                                              observed_at="2026-09-25T00:10:00Z")
            refused = self.attempt(lambda: director.run_one(program_id=memory))
            self.note("paused", status=paused.get("status"), run_while_paused=str(refused)[:160])
            self.require(paused.get("status") == "paused" and "paused" in str(refused),
                         "a paused program refuses to run", refused=str(refused)[:160])
            resumed = director.control_program(request_id="resume-memory", program_id=memory, action="resume",
                                               observed_at="2026-09-25T00:11:00Z")
            self.note("resumed", status=resumed.get("status"))
            self.require(resumed.get("status") == "active", "the paused program resumes",
                         status=resumed.get("status"))

            # Brain outage inside a running cycle, then a fresh server on the same port.
            outage: dict[str, Any] = {}

            def run_through_outage() -> None:
                try:
                    outage["result"] = director.run_one(program_id=memory)
                except BaseException as exc:  # noqa: BLE001
                    outage["error"] = f"{type(exc).__name__}: {exc}"

            self.activate(director, memory, "before-outage")
            worker = threading.Thread(target=run_through_outage)
            worker.start()
            time.sleep(3.0)
            self.stop_server()
            worker.join(timeout=1800)
            self.note("outage-cycle", error=outage.get("error"), finished=worker.is_alive() is False,
                      view=self.program_view(director, memory))
            self.require(outage.get("error"), "a dead brain surfaces an error rather than a silent result",
                         outcome=outage)
            self.require(worker.is_alive() is False, "the cycle terminates when the brain goes away")
            self.server = self.start_server(port)
            self.note("server-restarted")

            memory = self.active_line(director, "memory", MEMORY_QUESTION, 3)
            self.activate(director, memory, "after-outage")
            completed = self.run_cycle(director, memory, expect="complete")
            view = self.program_view(director, memory)
            claim = self.last_claim(director, memory)
            self.note("cycle-after-outage", program=memory, view=view, claim=claim,
                      result=str(completed.get("result"))[:200], error=completed.get("error"))
            self.require(completed.get("error") is None and (view.get("cycles_completed") or 0) >= 1,
                         "a cycle completes against the restarted brain", program=memory, view=view,
                         error=completed.get("error"))
            self.require(claim, "the completed cycle records a claim", program=memory)

            # Cancel a cycle that is actually running.
            sidecar = self.active_line(director, "sidecar", SIDECAR_QUESTION, 3)
            self.activate(director, sidecar, "before-cancel")
            cancelled = self.run_cycle(director, sidecar, expect="cancel")
            sidecar_view = self.program_view(director, sidecar)
            self.note("cancelled", program=sidecar, control=cancelled.get("control"),
                      error=cancelled.get("error"), control_error=cancelled.get("control_error"),
                      view=sidecar_view)
            self.require(sidecar_view.get("status") == "canceled",
                         "the cancelled program is cancelled", view=sidecar_view)

            events = director.store.events_after(cursor)
            cursor += len(events)
            kinds = sorted({str(event.get("kind") or event.get("event") or event.get("type"))
                            for event in events})
            self.note("events", count=len(events), kinds=kinds[:30])
            self.require(events, "the episode recorded operation events")
            status_before = {str(row.get("program_id")): self.program_view(director, str(row.get("program_id")))
                             for row in director.store.programs()}
            status = director.status()
            self.require(status.get("schema") == "cassi.entity.research-director-state.v1",
                         "the director status carries its schema", status=list(status))
            self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
            self.receipt_path.write_text(json.dumps({"status": "running", "steps": self.steps},
                                                    indent=1, default=str), encoding="utf-8")
        finally:
            self.entity.close()
            self.entity = None
        self.note("closed")

        self.entity = self.open_entity(port)
        director = self.entity.researcher
        try:
            director.recover()
            after_reopen = {str(row.get("program_id")): self.program_view(director, str(row.get("program_id")))
                            for row in director.store.programs()}
            self.note("reopened", same=after_reopen == status_before, before=status_before, after=after_reopen)
            self.require(after_reopen == status_before and bool(status_before),
                         "reopening the entity recovers every program unchanged",
                         before=status_before, after=after_reopen)
            memory = self.active_line(director, "memory", MEMORY_QUESTION, 3, avoid_blocked=True)
            self.note("restart-continuation", program=memory,
                      status=director.store.program(memory).get("status"),
                      last_error=director.store.program(memory).get("last_error"))
            self.activate(director, memory, "after-restart")
            final = self.run_cycle(director, memory, expect="complete")
            final_view = self.program_view(director, memory)
            final_claim = self.last_claim(director, memory)
            self.note("cycle-after-restart", program=memory, view=final_view, claim=final_claim,
                      result=str(final.get("result"))[:200], error=final.get("error"))
            self.require(final.get("error") is None and (final_view.get("cycles_completed") or 0) >= 1,
                         "research continues after the entity restart", program=memory,
                         view=final_view, error=final.get("error"))
            self.require(final_claim, "the continued cycle records a claim", program=memory)
        finally:
            self.entity.close()
            self.entity = None
            self.stop_server()
        return self.finish()

    def finish(self) -> int:
        status = "episode-complete" if not self.failures else "episode-incomplete"
        receipt = {
            "schema": "cassi.entity.research-episode-verification.v1",
            "status": status,
            "scratch": str(self.scratch),
            "failures": self.failures,
            "steps": self.steps,
        }
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(json.dumps(receipt, indent=1, default=str), encoding="utf-8")
        print(json.dumps({"status": status, "failures": self.failures,
                          "receipt": str(self.receipt_path)}, indent=1))
        return 0 if not self.failures else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE),
                        help="repository root that holds CassiQwen, CassiFI and CassiTheory")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="GGUF for the live brain")
    parser.add_argument("--server-dir", default=DEFAULT_SERVER_DIR,
                        help="directory holding llama-server.exe and llama.dll")
    parser.add_argument("--native-dir", default=DEFAULT_NATIVE_DIR,
                        help="directory holding cassifi-field-runtime.exe and its DLLs")
    parser.add_argument("--scratch", default=None,
                        help="scratch directory (default: a fresh directory under CassiQwen/_diag)")
    parser.add_argument("--receipt", default=None, help="path for the JSON receipt")
    args = parser.parse_args(argv)
    episode = Episode(args)
    try:
        return episode.run()
    except BaseException:
        episode.note("failure", trace=traceback.format_exc()[-2000:])
        episode.stop_server()
        if episode.entity is not None:
            episode.entity.close()
        episode.require(False, "the episode raised before its checks completed")
        return episode.finish()


if __name__ == "__main__":
    sys.path[:0] = [str(Path(__file__).resolve().parent)]
    raise SystemExit(main())
