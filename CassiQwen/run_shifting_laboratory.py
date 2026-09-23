"""Run the Shifting Laboratory.

    python run_shifting_laboratory.py self-check
    python run_shifting_laboratory.py canary
    python run_shifting_laboratory.py mission --agent scripted:competent
    python run_shifting_laboratory.py entity-run --run-dir _runs/lab-1 --model-path ...gguf
    python run_shifting_laboratory.py portfolio --state _runs/lab-1/portfolio.json
    python run_shifting_laboratory.py night-shift --rounds 3 --agent scripted:competent
    python run_shifting_laboratory.py rail
    python run_shifting_laboratory.py transactions

    python run_shifting_laboratory.py discover --law L3-native-w49
    python run_shifting_laboratory.py discover-canary
    python run_shifting_laboratory.py shift --reader tracking
    python run_shifting_laboratory.py shift-canary
    python run_shifting_laboratory.py author --reference good
    python run_shifting_laboratory.py author-canary

Every mode writes JSON receipts under --receipt / --receipt-dir.  A run in
`entity-run` is disposable by construction: a fresh data home, a fresh research
root and a fresh token inside one run directory, and the entity's live home is
never touched.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import math
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from laboratory import authoring as authoring_module  # noqa: E402
from laboratory import course as course_module  # noqa: E402
from laboratory import hidden as hidden_module  # noqa: E402
from laboratory import shifting as shifting_module  # noqa: E402
from laboratory import stations as stations_module  # noqa: E402
from laboratory.course import (  # noqa: E402
    Course,
    CourseContext,
    EntityAgent,
    NightShift,
    ScriptedAgent,
    portfolio_worlds,
    run_portfolio_round,
    write_receipt,
)
from laboratory.oracle import (  # noqa: E402
    CellComplex,
    Model,
    NativeFieldOracle,
    State,
    counterflow_packet,
    epsilon_mode,
)

DEFAULT_MODEL = HERE / "Qwen3.8-27B-UD-Q2_K_XL.gguf"
DEFAULT_MODEL_URL = "http://127.0.0.1:8084"
PHI = (1.0 + math.sqrt(5.0)) / 2.0


# --------------------------------------------------------------------------
# self-checks


def oracle_self_check() -> dict[str, Any]:
    """Call the oracle's declared self-check and preserve every measured check."""

    candidate = getattr(NativeFieldOracle, "self_check", None)
    if callable(candidate):
        result = candidate()
        if isinstance(result, Mapping):
            return {"entry": "NativeFieldOracle.self_check", **dict(result)}
        return {"entry": "NativeFieldOracle.self_check", "result": result}
    for name in ("self_check", "run_self_check", "self_checks", "verify"):
        candidate = getattr(stations_module.oracle_module, name, None)
        if callable(candidate):
            try:
                result = candidate()
            except TypeError:
                continue
            if isinstance(result, Mapping):
                return {"entry": name, **dict(result)}
            return {"entry": name, "result": result}
    return {"entry": None, "error": "the oracle exposes no self-check entry"}


def independent_checks(fixture: stations_module.Fixture) -> dict[str, Any]:
    """Checks the course owns: the judge's own dependencies, verified here.

    These do not re-read the oracle's internals.  They measure relations
    between quantities the oracle reports (energy, node power, the step map)
    and compare them with mathematics derived independently.
    """

    checks: list[dict[str, Any]] = []

    # 1. energy ledger: dH/dt = -(sum of node powers), second-order accurate.
    residuals: dict[str, float] = {}
    for dt in (0.02, 0.01, 0.005):
        engine = NativeFieldOracle(fixture.complex, fixture.native, dt)
        state = _mixed_state(fixture)
        scale = abs(engine.hamiltonian(state)) + 1e-12
        energy_before = float(engine.hamiltonian(state))
        power_before = float(engine.node_power(state, "Y").sum() + engine.node_power(state, "I").sum())
        after = engine.step(state)
        energy_after = float(engine.hamiltonian(after))
        power_after = float(engine.node_power(after, "Y").sum() + engine.node_power(after, "I").sum())
        ledger = (energy_after - energy_before) / dt + 0.5 * (power_before + power_after)
        residuals[f"dt={dt}"] = abs(ledger) / scale
    ordered = [residuals[key] for key in ("dt=0.02", "dt=0.01", "dt=0.005")]
    converged = ordered[2] < ordered[0] and ordered[0] > 0.0
    ratio = (ordered[0] / ordered[2]) if ordered[2] > 0 else float("inf")
    checks.append(
        {
            "name": "energy ledger closes at second order",
            "ok": converged and ratio >= 2.0,
            "detail": f"relative residuals {json.dumps(residuals)}; refined/coarse ratio {ratio:.3f}",
            "numbers": {"ratio": ratio, "finest": ordered[2]},
        }
    )

    # 2. the step map is time-symmetric: negate momenta and run back.
    engine = NativeFieldOracle(fixture.complex, fixture.native, fixture.dt)
    start = _mixed_state(fixture)
    forward = engine.advance(start, 200)
    rewind = engine.advance(
        State(forward.psi_y, forward.psi_i, -forward.p_y, -forward.p_i), 200
    )
    drift = max(
        float(abs(rewind.psi_y - start.psi_y).max()),
        float(abs(rewind.psi_i - start.psi_i).max()),
        float(abs(rewind.p_y + start.p_y).max()),
        float(abs(rewind.p_i + start.p_i).max()),
    )
    amplitude = max(float(abs(start.psi_y).max()), float(abs(start.psi_i).max())) + 1e-12
    checks.append(
        {
            "name": "the integrator is time-symmetric",
            "ok": drift / amplitude <= 1e-9,
            "detail": f"200 steps forward, momenta negated, 200 steps back; drift {drift:.3e} against amplitude {amplitude:.3e}",
            "numbers": {"relative_drift": drift / amplitude},
        }
    )

    # 3. the conversion period the whole course rests on.
    measured = {}
    for name, model in (("native", fixture.native), ("counterfactual", fixture.counterfactual)):
        engine = NativeFieldOracle(fixture.complex, model, fixture.dt)
        state = epsilon_mode(fixture.complex, model, amplitude=1.0, width=None)
        series = []
        current = state
        for _ in range(3000):
            series.append(float(engine.epsilon(current)[fixture.probe]))
            current = engine.step(current)
        measured[name] = stations_module._period_from_zero_crossings(series, fixture.dt)
    analytic = {
        "native": 2.0 * math.pi / math.sqrt((1.0 + fixture.model.phi) * fixture.model.omega2),
        "counterfactual": 2.0 * math.pi / math.sqrt((1.0 + fixture.model.phi ** 2) * fixture.model.omega2),
    }
    errors = {
        name: (abs(measured[name] - analytic[name]) / analytic[name] if measured.get(name) else None)
        for name in analytic
    }
    separation = stations_module._separation(measured.get("native"), measured.get("counterfactual"))
    checks.append(
        {
            "name": "the measured conversion period matches the analytic one",
            "ok": all(error is not None and error <= 1e-3 for error in errors.values()),
            "detail": json.dumps({"measured": measured, "analytic": analytic, "relative_errors": errors}, sort_keys=True),
            "numbers": {key: value for key, value in errors.items() if value is not None},
        }
    )
    checks.append(
        {
            "name": "the two mechanisms are separated by the period",
            "ok": separation is not None and separation >= stations_module.DISCRIMINATION_SEPARATION,
            "detail": f"relative separation {separation!r} (threshold {stations_module.DISCRIMINATION_SEPARATION})",
            "numbers": {"separation": separation},
        }
    )

    # 4. the observed run really is blind to the difference.
    engine = NativeFieldOracle(fixture.complex, fixture.native, fixture.dt)
    state = counterflow_packet(
        fixture.complex,
        fixture.model,
        amplitude=fixture.observed_packet["amplitude"],
        width=fixture.observed_packet["width"],
        center=fixture.observed_packet["center"],
        speed=fixture.observed_packet["speed"],
    )
    worst = 0.0
    for _ in range(fixture.steps_observed + 1):
        worst = max(worst, float(abs(engine.epsilon(state)).max()))
        state = engine.step(state)
    checks.append(
        {
            "name": "the observed run keeps the conversion quantity at zero",
            "ok": worst <= 1e-9,
            "detail": f"max |eps| over the observed window: {worst:.3e}",
            "numbers": {"max_abs_epsilon": worst},
        }
    )

    return {
        "schema": "cassi.laboratory.self-check.v1",
        "fixture_id": fixture.fixture_id(),
        "checks": checks,
        "verdict": "pass" if all(item["ok"] for item in checks) else "fail",
    }


def _mixed_state(fixture: stations_module.Fixture) -> State:
    packet = counterflow_packet(
        fixture.complex,
        fixture.model,
        amplitude=fixture.observed_packet["amplitude"],
        width=fixture.observed_packet["width"],
        center=fixture.observed_packet["center"],
        speed=fixture.observed_packet["speed"],
    )
    excited = epsilon_mode(fixture.complex, fixture.model, amplitude=0.3, width=None)
    return State(
        packet.psi_y + excited.psi_y,
        packet.psi_i + excited.psi_i,
        packet.p_y,
        packet.p_i,
    )


def cmd_self_check(arguments: argparse.Namespace) -> int:
    fixture = stations_module.build_fixture(variant=arguments.variant)
    report = {
        "oracle": oracle_self_check(),
        "independent": independent_checks(fixture),
    }
    report["verdict"] = (
        "pass"
        if report["independent"]["verdict"] == "pass"
        and not report["oracle"].get("error")
        and _oracle_passed(report["oracle"])
        else "fail"
    )
    if arguments.receipt:
        write_receipt(report, arguments.receipt)
    _print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "pass" else 1


def _oracle_passed(report: Mapping[str, Any]) -> bool:
    for key in ("verdict", "ok", "passed", "result"):
        value = report.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value in {"pass", "ok"}:
            return True
        if isinstance(value, Mapping) and "verdict" in value:
            return value["verdict"] == "pass"
    checks = report.get("checks")
    if isinstance(checks, list) and checks:
        return all(bool(item.get("ok") or item.get("passed")) for item in checks)
    return True


# --------------------------------------------------------------------------
# agents


def canary_answerers(fixture: stations_module.Fixture) -> dict[str, Callable[[Mapping[str, Any]], Mapping[str, Any]]]:
    module = importlib.import_module("laboratory.canary")
    builder = getattr(module, "canary_agents", None)
    if callable(builder):
        return dict(builder(fixture))
    raise SystemExit("laboratory.canary exposes no canary_agents(fixture)")


def scripted_agent(name: str, fixture: stations_module.Fixture) -> ScriptedAgent:
    answerers = canary_answerers(fixture)
    if name not in answerers:
        raise SystemExit(f"unknown canary {name!r}; available: {sorted(answerers)}")
    return ScriptedAgent(answerer=answerers[name], kind=f"scripted:{name}")


def _entity_tools(arguments: argparse.Namespace) -> tuple[str, ...]:
    declared = getattr(arguments, "entity_tools", None)
    if not declared:
        return ("write_artifact",)
    return tuple(item.strip() for item in declared.split(",") if item.strip())


def entity_agent(arguments: argparse.Namespace, fixture: stations_module.Fixture) -> EntityAgent:
    from cassi_program_benchmark_client import ProgramBenchmarkClient

    if not arguments.url or not arguments.token_file:
        raise SystemExit("--agent entity needs --url and --token-file (or use entity-run)")
    token = Path(arguments.token_file).read_text(encoding="utf-8").strip()
    client = ProgramBenchmarkClient(arguments.url, token)
    root = Path(arguments.research_root).resolve() if arguments.research_root else Path(arguments.home or ".").resolve()
    root.mkdir(parents=True, exist_ok=True)
    workspace_root = Path(arguments.research_root) / "workspaces" if arguments.research_root else None
    return EntityAgent(
        client=client,
        project_id=arguments.project_id,
        allowed_roots=[str(root)],
        allowed_tools=_entity_tools(arguments),
        program_id=arguments.program_id,
        deadline_s=arguments.deadline,
        workspace_root=workspace_root,
    )


# --------------------------------------------------------------------------
# modes


def cmd_canary(arguments: argparse.Namespace) -> int:
    fixture = stations_module.build_fixture(variant=arguments.variant)
    answerers = canary_answerers(fixture)
    names = sorted(answerers) if arguments.which == "all" else [arguments.which]
    report: dict[str, Any] = {"schema": "cassi.laboratory.canary-report.v1", "fixture_id": fixture.fixture_id(), "runs": {}}
    exit_code = 0
    for name in names:
        if name not in answerers:
            raise SystemExit(f"unknown canary {name!r}; available: {sorted(answerers)}")
        receipt_dir = Path(arguments.receipt_dir or ".")
        receipt_path = receipt_dir / f"canary-{name}.json"
        agent = ScriptedAgent(answerer=answerers[name], kind=f"scripted:{name}")
        receipt = Course.physics(fixture).run(agent, receipt_path=receipt_path)
        report["runs"][name] = {
            "verdict": receipt["verdict"],
            "station_verdicts": receipt["station_verdicts"],
            "receipt": str(receipt_path),
            "digest": receipt["digest"],
        }
    competent = report["runs"].get("competent", {}).get("verdict")
    controls = [name for name in report["runs"] if name != "competent"]
    report["controls_all_failed"] = all(report["runs"][name]["verdict"] == "fail" for name in controls) if controls else None
    report["discriminates"] = competent == "pass" and bool(report["controls_all_failed"])
    report["verdict"] = "pass" if report["discriminates"] else "fail"
    if arguments.receipt:
        write_receipt(report, arguments.receipt)
    _print(json.dumps(report, indent=2, sort_keys=True))
    if not report["discriminates"]:
        exit_code = 1
    return exit_code


def cmd_mission(arguments: argparse.Namespace) -> int:
    fixture = stations_module.build_fixture(variant=arguments.variant)
    agent = _agent_for(arguments, fixture)
    course = Course.physics(fixture)
    receipt_path = arguments.receipt
    if receipt_path is None:
        run_dir = getattr(arguments, "run_dir", None)
        if run_dir is not None:
            # A shift's receipt is its evidence, so a live run writes one even
            # when the caller did not ask for it by name.
            receipt_path = Path(run_dir) / "mission-receipt.json"
    receipt = course.run(
        agent,
        receipt_path=receipt_path,
        resume_from=arguments.resume,
        station_ids=None if arguments.stations == "all" else arguments.stations.split(","),
        deadline_s=arguments.deadline,
    )
    agent.close()
    summary = _summary(receipt)
    if receipt_path is not None:
        summary["receipt"] = str(receipt_path)
    _print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if receipt["verdict"] == "pass" else 1


def cmd_portfolio(arguments: argparse.Namespace) -> int:
    def factory(world: stations_module.Fixture) -> Any:
        return _agent_for(arguments, world)

    state = run_portfolio_round(
        factory,
        state_path=arguments.state,
        receipt_dir=arguments.receipt_dir,
        only=arguments.only,
        deadline_s=arguments.deadline,
    )
    _print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state["settled"] == len(state["declared"]) else 1


def cmd_night_shift(arguments: argparse.Namespace) -> int:
    worlds = portfolio_worlds()

    def course_factory(index: int) -> Course:
        return Course.physics(worlds[index % len(worlds)])

    def agent_factory(index: int) -> Any:
        fixture = worlds[index % len(worlds)]
        if arguments.agent.startswith("entity"):
            namespace = argparse.Namespace(**vars(arguments))
            namespace.home = arguments.home
            return entity_agent(namespace, fixture)
        return scripted_agent(arguments.agent.split(":", 1)[1], fixture)

    shift = NightShift(
        course_factory=course_factory,
        rounds=arguments.rounds,
        state_path=arguments.state,
        receipt_dir=arguments.receipt_dir,
        minutes=arguments.minutes,
    )
    state = shift.run(agent_factory, deadline_s=arguments.deadline)
    _print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state["settled"] == arguments.rounds else 1


def cmd_rail(arguments: argparse.Namespace) -> int:
    """Measure real placements against one disposable live entity.

    The rail's whole point is an observed placement, so the mode always opens a
    live entity: a null client would report a clean zero that measured nothing.
    """

    from cassi_program_benchmark_client import PROGRAM_BACKENDS

    module = importlib.import_module("laboratory.rail")
    transactions_module = importlib.import_module("laboratory.transactions")
    parent = Path(tempfile.mkdtemp(prefix="rail-", dir=_scratch_parent()))
    token = secrets.token_urlsafe(24)
    fixture = _open_disposable_entity(parent, token)
    try:
        client = fixture["client"]
        prepared = transactions_module.prepare_program(
            client,
            program_id="rail-disposable",
            tag="rail",
            allowed_roots=[str(parent)],
            mission="Shifting Laboratory engineering rail",
            question="Which declared backend actually executes this program?",
        )
        placements = [
            {
                "placement_id": backend.split("-")[0],
                "declared": {
                    "backend": backend,
                    "capability": "effect-proposal",
                    "mode": "exec",
                },
            }
            for backend in PROGRAM_BACKENDS
            if backend == "logical-cpu"
        ]
        report = module.measure_rail(
            client=client,
            placements=placements,
            work={
                "program_id": prepared["program_id"],
                "source": "value = 7\n",
                "tag": "rail",
            },
            home=parent,
            workspace=parent / "workspace",
        )
    finally:
        _close_disposable_entity(fixture)
    if arguments.receipt:
        write_receipt(report, arguments.receipt)
    _print(json.dumps(report, indent=2, sort_keys=True))
    measured = int(report.get("measurements", {}).get("attempted_requests", 0))
    control = next(
        (item for item in report.get("controls", []) if item.get("name") == "invalid-backend-control"),
        None,
    )
    return 0 if measured > 0 and control is not None and control.get("ok") else 1


def _scratch_parent() -> str:
    scratch = Path(tempfile.gettempdir()) / "cassi-laboratory"
    scratch.mkdir(parents=True, exist_ok=True)
    return str(scratch)


def _open_disposable_entity(home: Path, token: str, port: int = 0) -> dict[str, Any]:
    """One disposable real entity: fresh data home, research root and server."""

    from cassi_field_brain_entity import EntityConfig, FieldBrainEntity
    from cassi_field_brain_server import EntityHTTPServer
    from cassi_program_benchmark_client import ProgramBenchmarkClient

    class NoBrain:
        model_id = "laboratory-disposable-no-brain"
        model_sha256 = "0" * 64

        def complete(self, *args: Any, **kwargs: Any) -> str:
            raise RuntimeError("disposable laboratory fixtures must not call the brain")

    entity = FieldBrainEntity(
        EntityConfig(
            data_home=home / "entity",
            capability_root=HERE.parent,
            theory_root=HERE.parent / "CassiTheory",
            research_home=home / "research",
            research_roots=(home,),
            research_resident_enabled=False,
            program_native_enabled=False,
        ),
        brain=NoBrain(),
    )
    server = EntityHTTPServer(("127.0.0.1", port), entity, api_token=token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return {
        "entity": entity,
        "server": server,
        "thread": thread,
        "client": ProgramBenchmarkClient(
            f"http://127.0.0.1:{server.server_address[1]}", token
        ),
        "port": int(server.server_address[1]),
    }


def _close_disposable_entity(fixture: Mapping[str, Any]) -> None:
    fixture["server"].shutdown()
    fixture["server"].server_close()
    fixture["entity"].close()
    fixture["thread"].join(timeout=10)
    if fixture["thread"].is_alive():
        raise RuntimeError("disposable laboratory entity did not stop")


def cmd_transactions(arguments: argparse.Namespace) -> int:
    """Run each transaction station in its own disposable real entity."""

    module = importlib.import_module("laboratory.transactions")
    parent = Path(arguments.run_dir).resolve()
    parent.mkdir(parents=True, exist_ok=True)

    reports: dict[str, Any] = {}
    for station_name in ("capacity-cliff", "acknowledgment", "recovery"):
        home = Path(tempfile.mkdtemp(prefix=f"{station_name}-", dir=parent))
        token = secrets.token_urlsafe(36)
        fixture = _open_disposable_entity(home, token)
        program_id = f"laboratory-{station_name}"
        try:
            prepared = module.prepare_program(
                fixture["client"],
                program_id=program_id,
                tag=f"{station_name}-parent",
                allowed_roots=[str(home)],
                mission=f"Exercise the {station_name} transaction station.",
                question="Measure the real entity contract.",
            )
            if not prepared["accepted"]:
                raise RuntimeError(
                    f"{station_name} program preparation failed: "
                    f"{prepared['status']} {prepared['error']}"
                )
            if station_name == "capacity-cliff":
                report = module.cliff_station(
                    fixture["client"],
                    program_id=program_id,
                    tag="transaction-cliff",
                    max_concurrent=module.DEFAULT_TASK_CAPACITY,
                    source="value = 1",
                )
            elif station_name == "acknowledgment":
                report = module.acknowledgment_station(
                    fixture["client"],
                    program_id=program_id,
                    tag="transaction-ack",
                )
            else:
                def restart() -> None:
                    nonlocal fixture
                    port = fixture["port"]
                    _close_disposable_entity(fixture)
                    fixture = _open_disposable_entity(home, token, port)

                report = module.recovery_station(
                    fixture["client"],
                    program_id=program_id,
                    tag="transaction-recovery",
                    restart=restart,
                )
            reports[station_name] = report
        finally:
            _close_disposable_entity(fixture)

    combined = {
        "schema": "cassi.laboratory.transaction-report.v1",
        "verdict": (
            "pass"
            if all(report.get("verdict") == "pass" for report in reports.values())
            else "fail"
        ),
        "stations": reports,
    }
    receipt = arguments.receipt or parent / "transactions.json"
    write_receipt(combined, receipt)
    _print(
        json.dumps(
            {
                "schema": combined["schema"],
                "verdict": combined["verdict"],
                "receipt": str(receipt),
                "stations": {
                    name: {
                        "verdict": report["verdict"],
                        "checks": {
                            item["name"]: item["ok"]
                            for item in report.get("checks", [])
                        },
                        "controls": {
                            item["name"]: item["ok"]
                            for item in report.get("controls", [])
                        },
                    }
                    for name, report in reports.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if combined["verdict"] == "pass" else 1


LABORATORY_SLOT = Path("_diag/laboratory/live-entity.pid")


def _claim_entity_slot(run_dir: Path) -> None:
    """One live laboratory entity at a time, so runs cannot share the brain.

    Two entities polling one brain re-prefill each other's contexts and the
    measurement degrades silently; a killed run leaves its server behind, so
    the recorded slot is checked for a live process before a new run starts.
    """

    LABORATORY_SLOT.parent.mkdir(parents=True, exist_ok=True)
    if LABORATORY_SLOT.exists():
        recorded = LABORATORY_SLOT.read_text(encoding="utf-8").strip().splitlines()
        pid = recorded[0].strip() if recorded else ""
        holder = recorded[1].strip() if len(recorded) > 1 else "unknown run"
        if pid.isdigit() and _process_alive(int(pid)):
            raise SystemExit(
                f"a live laboratory entity (pid {pid}, {holder}) already owns the "
                "brain; stop it or remove "
                f"{LABORATORY_SLOT} before starting another run"
            )
    LABORATORY_SLOT.write_text(f"{os.getpid()}\n{run_dir}\n", encoding="utf-8")


def _release_entity_slot(run_dir: Path) -> None:
    try:
        recorded = LABORATORY_SLOT.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return
    if recorded and recorded[0].strip() == str(os.getpid()):
        LABORATORY_SLOT.unlink(missing_ok=True)
    elif len(recorded) > 1 and recorded[1].strip() == str(run_dir):
        LABORATORY_SLOT.unlink(missing_ok=True)


def _process_alive(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    return str(pid) in result.stdout


def _stop_server_tree(server: subprocess.Popen[Any]) -> None:
    """Stop the entity server and the resident worker it spawned.

    The server starts a resident research worker in its own process, so
    terminating the parent alone leaves a child holding the port and the
    shared brain.  The whole tree goes down before the body returns.
    """

    if server.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(server.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    try:
        server.wait(timeout=20)
    except subprocess.TimeoutExpired:
        server.kill()


@contextlib.contextmanager
def disposable_entity(arguments: argparse.Namespace) -> Any:
    """A fresh entity in its own run directory, healthy before the body runs.

    The live home is never touched: the entity gets a new data home, a new
    research root and a new token inside one run directory, and the server is
    stopped when the body leaves.
    """

    run_dir = Path(arguments.run_dir).resolve()
    for name in ("entity-home", "research"):
        (run_dir / name).mkdir(parents=True, exist_ok=True)
    _claim_entity_slot(run_dir)
    token = secrets.token_urlsafe(36)
    token_file = run_dir / "api-token.txt"
    token_file.write_text(token, encoding="utf-8")
    model_path = Path(arguments.model_path).resolve()
    if not model_path.exists():
        raise SystemExit(f"model not found: {model_path}")
    server_log = (run_dir / "entity-server.log").open("w", encoding="utf-8")
    server_arguments = [
        sys.executable,
        str(HERE / "cassi_field_brain_server.py"),
        "--data-home", str(run_dir / "entity-home"),
        "--model-url", arguments.model_url,
        "--model-path", str(model_path),
        "--api-token-file", str(token_file),
        "--port", str(arguments.port),
        "--research-home", str(run_dir / "research"),
        "--research-root", str(run_dir / "research"),
        "--capability-root", arguments.capability_root,
        "--theory-root", str(HERE.parent / "CassiTheory"),
        "--research-cycle-seconds", str(arguments.cycle_seconds),
        "--brain-context-tokens", str(arguments.brain_context_tokens),
    ]
    if arguments.no_resident:
        server_arguments.append("--no-resident")
    declared_tools = arguments.research_tool or [
        name for name in _entity_tools(arguments) if name in _SERVER_RESEARCH_TOOLS
    ]
    for tool in declared_tools:
        server_arguments.extend(["--research-tool", tool])
    server = subprocess.Popen(
        server_arguments,
        cwd=str(HERE),
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )
    try:
        base_url = arguments.url or f"http://127.0.0.1:{arguments.port}"
        if not _await_health(base_url, token=token, timeout=arguments.startup_timeout):
            raise SystemExit(f"entity did not become healthy; see {run_dir / 'entity-server.log'}")
        arguments.url = base_url
        arguments.token_file = str(token_file)
        arguments.research_root = str(run_dir / "research")
        yield run_dir
    finally:
        _stop_server_tree(server)
        server_log.close()
        _release_entity_slot(run_dir)


def cmd_entity_run(arguments: argparse.Namespace) -> int:
    """Start a disposable entity, run one mission against it, stop it."""

    with disposable_entity(arguments):
        return cmd_mission(arguments)


def cmd_discover_run(arguments: argparse.Namespace) -> int:
    """Start a disposable entity, then let it answer one hidden world."""

    with disposable_entity(arguments):
        return cmd_discover(arguments)


def cmd_author_run(arguments: argparse.Namespace) -> int:
    """Start a disposable entity, then have it author a station."""

    with disposable_entity(arguments):
        return cmd_author(arguments)


# --------------------------------------------------------------------------
# level 2: worlds that move, and stations an agent authors


def _world_identity(world: Any) -> dict[str, Any]:
    return {
        "variant": world.variant,
        "title": world.title(),
        "fixture_id": world.fixture_id(),
        "true_law_id": world.true_law_id,
        "measured_recipe_id": world.measurement_recipe_id,
        "observation_recipe_ids": [recipe["recipe_id"] for recipe in world.observations],
        "true_lifetimes": world.retention_lifetimes(),
    }


def _hidden_agent_for(arguments: argparse.Namespace, world: Any) -> Any:
    if arguments.agent.startswith("entity"):
        return entity_agent(arguments, world)
    name = arguments.agent.split(":", 1)[1]
    answerers = hidden_module.hidden_canary_agents()
    if name not in answerers:
        raise SystemExit(f"unknown reader {name!r}; available: {sorted(answerers)}")
    return ScriptedAgent(answerer=answerers[name], kind=f"hidden:{name}")


def _course_receipt(
    arguments: argparse.Namespace, level: str, world: Any, stations: Any, agent: Any, *, name: str
) -> dict[str, Any]:
    receipt_path = arguments.receipt or (Path(arguments.receipt_dir) / f"{name}.json")
    course = Course(
        world,
        stations,
        level=level,
        world_block=world.declared_world(),
        title=world.title(),
    )
    return course.run(agent, receipt_path=receipt_path, deadline_s=arguments.deadline)


def cmd_discover(arguments: argparse.Namespace) -> int:
    world = hidden_module.hidden_world(true_law_id=arguments.law, variant=arguments.variant)
    agent = _hidden_agent_for(arguments, world)
    try:
        receipt = _course_receipt(
            arguments, "hidden", world, world.stations(), agent, name=f"discover-{arguments.law}"
        )
    finally:
        agent.close()
    summary = _summary(receipt)
    summary["world"] = _world_identity(world)
    summary["declared_laws"] = [law["law_id"] for law in world.laws]
    _print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if receipt["verdict"] == "pass" else 1


def cmd_discover_canary(arguments: argparse.Namespace) -> int:
    report: dict[str, Any] = {"schema": "cassi.laboratory.hidden-canary-report.v1", "worlds": {}}
    exit_code = 0
    for law in arguments.laws.split(","):
        law_id = law.strip()
        if not law_id:
            continue
        world = hidden_module.hidden_world(true_law_id=law_id)
        world_report = hidden_module.hidden_canary_report(world, receipt_dir=arguments.receipt_dir)
        report["worlds"][law_id] = {
            "variant": world.variant,
            "true_law_id": world.true_law_id,
            "discriminates": world_report["discriminates"],
            "agents": {
                name: {"verdict": run["verdict"], "station_verdicts": run["station_verdicts"]}
                for name, run in world_report["agents"].items()
            },
        }
        if not world_report["discriminates"]:
            exit_code = 1
    report["discriminates"] = all(item["discriminates"] for item in report["worlds"].values())
    report["verdict"] = "pass" if report["discriminates"] else "fail"
    if arguments.receipt:
        write_receipt(report, arguments.receipt)
    _print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


def _shift_summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": receipt["schema"],
        "plan": receipt["plan"],
        "verdict": receipt["verdict"],
        "rounds": [
            {
                "index": item["index"],
                "law_id": item["law_id"],
                "claimed_law": item["claimed_law"],
                "verdict": item["verdict"],
            }
            for item in receipt["rounds"]
        ],
        "detection": receipt["detection"],
        "carry": receipt["carry"],
        "controls": [
            {"name": control["name"], "ok": control["ok"], "detail": control["detail"]}
            for control in receipt["controls"]
        ],
        "settled": receipt["settled"],
        "attempted": receipt["attempted"],
        "declared_rounds": receipt["declared_rounds"],
        "clock": receipt["clock"],
        "digest": receipt["digest"],
    }


def cmd_shift(arguments: argparse.Namespace) -> int:
    law_ids = tuple(item.strip() for item in arguments.sequence.split(",") if item.strip())
    plan = shifting_module.ShiftPlan(law_ids, arguments.switch, variant=arguments.variant)
    if arguments.agent.startswith("entity"):
        worlds = plan.worlds()

        def factory(index: int) -> Any:
            return entity_agent(arguments, worlds[index])
    else:
        factory = shifting_module.scripted_factory(arguments.agent.split(":", 1)[1])
    shift = shifting_module.ShiftingShift(
        plan,
        state_path=arguments.state,
        receipt_dir=arguments.receipt_dir,
        minutes=arguments.minutes,
    )
    receipt = shift.run(factory, deadline_s=arguments.deadline)
    if arguments.receipt:
        write_receipt(receipt, arguments.receipt)
    _print(json.dumps(_shift_summary(receipt), indent=2, sort_keys=True))
    return 0 if receipt["verdict"] == "pass" else 1


def cmd_shift_canary(arguments: argparse.Namespace) -> int:
    report = shifting_module.shift_canary_report(receipt_dir=arguments.receipt_dir)
    if arguments.receipt:
        write_receipt(report, arguments.receipt)
    _print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["discriminates"] else 1


def cmd_author(arguments: argparse.Namespace) -> int:
    base = hidden_module.hidden_world(variant=arguments.variant)
    stations = (authoring_module.authoring_station(base),)
    if arguments.agent.startswith("entity"):
        agent = entity_agent(arguments, base)
        name = "author-entity"
    else:
        if arguments.proposal:
            proposal = json.loads(Path(arguments.proposal).read_text(encoding="utf-8"))
            name = f"author-{Path(arguments.proposal).stem}"
        else:
            proposal = authoring_module.reference_proposals()[arguments.reference]
            name = f"author-{arguments.reference}"
        agent = ScriptedAgent(answerer=lambda _exchange, item=proposal: dict(item), kind="author:scripted")
    try:
        receipt = _course_receipt(arguments, "authoring", base, stations, agent, name=name)
    finally:
        agent.close()
    summary = _summary(receipt)
    report = receipt["stations"][0]
    summary["proposal"] = report.get("measurements", {}).get("proposal")
    summary["authored_world"] = report.get("measurements", {}).get("authored_world")
    summary["readers"] = {
        reader: {"verdict": run["verdict"], "failed_checks": run["failed_checks"]}
        for reader, run in report.get("measurements", {}).get("readers", {}).items()
    }
    _print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if receipt["verdict"] == "pass" else 1


def cmd_author_canary(arguments: argparse.Namespace) -> int:
    report = authoring_module.authoring_canary_report(receipt_dir=arguments.receipt_dir)
    if arguments.receipt:
        write_receipt(report, arguments.receipt)
    _print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["discriminates"] else 1


def _await_health(url: str, *, token: str, timeout: float) -> bool:
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(
                f"{url}/v1/health",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(1.0)
    return False


# --------------------------------------------------------------------------
# plumbing


def _agent_for(arguments: argparse.Namespace, fixture: stations_module.Fixture) -> Any:
    if arguments.agent.startswith("entity"):
        return entity_agent(arguments, fixture)
    return scripted_agent(arguments.agent.split(":", 1)[1], fixture)


def _summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    transcript = (receipt.get("agent") or {}).get("transcript")
    throughput = (
        transcript.get("throughput") if isinstance(transcript, Mapping) else None
    )
    summary = {
        "schema": receipt["schema"],
        "mission_id": receipt["identity"]["mission_id"],
        "fixture_id": receipt["identity"]["fixture_id"],
        "verdict": receipt["verdict"],
        "station_verdicts": receipt["station_verdicts"],
        "controls": {
            item["station"]: [
                {"name": control["name"], "ok": control["ok"]} for control in item.get("controls", [])
            ]
            for item in receipt["stations"]
        },
        "failed_checks": [
            {"station": item["station"], "check": check["name"], "detail": check["detail"]}
            for item in receipt["stations"]
            for check in item.get("checks", [])
            if not check["ok"]
        ],
        "clock": receipt["clock"],
        "digest": receipt["digest"],
    }
    if isinstance(throughput, Mapping):
        summary["throughput"] = {
            key: value
            for key, value in throughput.items()
            if key
            in {
                "cycles_completed",
                "seconds_per_cycle",
                "agent_seconds",
                "status",
                "deliverable_state",
                "coverage",
            }
        }
    return summary


def _print(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--model-url", default=DEFAULT_MODEL_URL)
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--capability-root", default=str(HERE))
    parser.add_argument(
        "--research-tool",
        action="append",
        choices=(
            "list_files",
            "read_file",
            "search_text",
            "write_artifact",
            "inspect_artifact",
            "run_existing_python",
        ),
        help="tool the mission program may use; repeat to add one, defaults to the laboratory set",
    )
    parser.add_argument("--cycle-seconds", type=float, default=1.0)
    parser.add_argument("--brain-context-tokens", type=int, default=32_768)
    parser.add_argument("--no-resident", action="store_true")
    parser.add_argument("--startup-timeout", type=float, default=120.0)


# A course program writes its answer document and runs the programs that
# answer is built from, inside its own disposable program root.  The executing
# tool is the capability here: reasoning about unwritten source is not evidence,
# and the hidden-world stations ask for a measured fit and a forecast.
MISSION_ENTITY_TOOLS = "write_artifact,run_existing_python,read_file,list_files"
_SERVER_RESEARCH_TOOLS = frozenset(
    {
        "fetch_url",
        "inspect_artifact",
        "list_files",
        "read_file",
        "run_existing_python",
        "search_text",
        "write_artifact",
    }
)


def _add_entity_arguments(parser: argparse.ArgumentParser, *, default_tools: str | None = None) -> None:
    parser.add_argument(
        "--entity-tools",
        default=default_tools,
        help="tools the entity program may use, comma separated",
    )
    parser.add_argument("--url")
    parser.add_argument("--token-file")
    parser.add_argument("--program-id")
    parser.add_argument("--project-id", default="shifting-laboratory")
    parser.add_argument("--home")
    parser.add_argument("--research-root")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", default="counterflow-1", help="declared world variant")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--receipt-dir", type=Path, default=Path("_diag/laboratory"))
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--stations", default="all", help="comma separated station ids, or all")
    parser.add_argument("--deadline", type=float, default=900.0, help="agent deadline in seconds")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    self_check = subparsers.add_parser(
        "self-check", help="oracle self-check plus the course's independent checks"
    )
    self_check.add_argument("--variant", default=argparse.SUPPRESS)
    self_check.add_argument("--receipt", type=Path, default=argparse.SUPPRESS)

    canary = subparsers.add_parser("canary", help="run the scripted controls")
    canary.add_argument(
        "--which", default="all", choices=("all", "competent", "confused", "shortcut")
    )
    canary.add_argument("--variant", default=argparse.SUPPRESS)
    canary.add_argument("--receipt", type=Path, default=argparse.SUPPRESS)
    canary.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)

    for name, help_text in (
        ("mission", "one mission"),
        ("entity-run", "disposable entity plus one mission"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument(
            "--agent",
            default="entity" if name == "entity-run" else "scripted:competent",
        )
        sub.add_argument("--variant", default=argparse.SUPPRESS)
        sub.add_argument("--receipt", type=Path, default=argparse.SUPPRESS)
        sub.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)
        sub.add_argument("--resume", type=Path, default=argparse.SUPPRESS)
        sub.add_argument("--stations", default=argparse.SUPPRESS)
        sub.add_argument("--deadline", type=float, default=argparse.SUPPRESS)
        sub.add_argument("--url")
        sub.add_argument("--token-file")
        sub.add_argument("--program-id")
        sub.add_argument("--project-id", default="shifting-laboratory")
        sub.add_argument("--home")
        sub.add_argument("--research-root")
        sub.add_argument(
            "--entity-tools",
            default=MISSION_ENTITY_TOOLS,
            help="tools the mission program may use, comma separated",
        )
        if name == "entity-run":
            _add_run_arguments(sub)

    portfolio = subparsers.add_parser("portfolio", help="resumable multi-world portfolio")
    portfolio.add_argument("--only")
    portfolio.add_argument("--variant", default=argparse.SUPPRESS)
    portfolio.add_argument("--receipt", type=Path, default=argparse.SUPPRESS)
    portfolio.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)
    portfolio.add_argument("--state", type=Path, default=Path("_diag/laboratory/portfolio-state.json"))
    portfolio.add_argument("--deadline", type=float, default=argparse.SUPPRESS)
    portfolio.add_argument("--agent", default="scripted:competent")
    portfolio.add_argument("--url")
    portfolio.add_argument("--token-file")
    portfolio.add_argument("--program-id")
    portfolio.add_argument("--project-id", default="shifting-laboratory")
    portfolio.add_argument("--home")
    portfolio.add_argument("--research-root")

    shift = subparsers.add_parser("night-shift", help="bounded shift of mixed work")
    shift.add_argument("--rounds", type=int, default=3)
    shift.add_argument("--minutes", type=float)
    shift.add_argument("--variant", default=argparse.SUPPRESS)
    shift.add_argument("--receipt", type=Path, default=argparse.SUPPRESS)
    shift.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)
    shift.add_argument("--state", type=Path, default=Path("_diag/laboratory/night-shift-state.json"))
    shift.add_argument("--deadline", type=float, default=argparse.SUPPRESS)
    shift.add_argument("--agent", default="scripted:competent")
    shift.add_argument("--url")
    shift.add_argument("--token-file")
    shift.add_argument("--program-id")
    shift.add_argument("--project-id", default="shifting-laboratory")
    shift.add_argument("--home")
    shift.add_argument("--research-root")


    discover = subparsers.add_parser(
        "discover", help="level 2: identify a hidden law and measure how long writes live"
    )
    discover.add_argument("--law", default="L1-native-w25", help="the law that actually runs the world")
    discover.add_argument("--agent", default="scripted:competent")
    discover.add_argument("--variant", default="hidden-1")
    discover.add_argument("--receipt", type=Path)
    discover.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)
    discover.add_argument("--deadline", type=float, default=argparse.SUPPRESS)
    _add_entity_arguments(discover, default_tools=MISSION_ENTITY_TOOLS)

    discover_run = subparsers.add_parser(
        "discover-run", help="disposable entity plus one hidden world"
    )
    discover_run.add_argument("--law", default="L1-native-w25")
    discover_run.add_argument("--agent", default="entity")
    discover_run.add_argument("--variant", default="hidden-1")
    discover_run.add_argument("--receipt", type=Path)
    discover_run.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)
    discover_run.add_argument("--deadline", type=float, default=argparse.SUPPRESS)
    _add_entity_arguments(discover_run, default_tools=MISSION_ENTITY_TOOLS)
    _add_run_arguments(discover_run)

    author_run = subparsers.add_parser(
        "author-run", help="disposable entity plus one authored station"
    )
    author_run.add_argument("--agent", default="entity")
    author_run.add_argument("--variant", default="authoring-base")
    author_run.add_argument("--receipt", type=Path)
    author_run.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)
    author_run.add_argument("--deadline", type=float, default=argparse.SUPPRESS)
    _add_entity_arguments(author_run, default_tools=MISSION_ENTITY_TOOLS)
    _add_run_arguments(author_run)

    discover_canary = subparsers.add_parser(
        "discover-canary", help="run the level 2 readers against every declared law"
    )
    discover_canary.add_argument(
        "--laws", default=",".join(law["law_id"] for law in hidden_module.LAW_MENU)
    )
    discover_canary.add_argument("--receipt", type=Path)
    discover_canary.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)

    shift = subparsers.add_parser(
        "shift", help="a world that changes its law mid-shift, and whether the reader notices"
    )
    shift.add_argument("--sequence", default=",".join(shifting_module.DEFAULT_SEQUENCE))
    shift.add_argument("--switch", type=int, default=shifting_module.DEFAULT_SWITCH_ROUND)
    shift.add_argument("--reader", dest="agent", default="scripted:tracking")
    shift.add_argument("--variant", default="shift")
    shift.add_argument("--state", type=Path, default=Path("_diag/laboratory/shift-state.json"))
    shift.add_argument("--minutes", type=float)
    shift.add_argument("--receipt", type=Path)
    shift.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)
    shift.add_argument("--deadline", type=float, default=argparse.SUPPRESS)
    _add_entity_arguments(shift)

    shift_canary = subparsers.add_parser(
        "shift-canary", help="tracking versus frozen versus shortcut readers across a shift"
    )
    shift_canary.add_argument("--receipt", type=Path)
    shift_canary.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)

    author = subparsers.add_parser(
        "author", help="an agent authors a station; the judge runs the real course on it"
    )
    author.add_argument("--agent", default="scripted")
    author.add_argument("--reference", default="good", choices=tuple(authoring_module.reference_proposals()))
    author.add_argument("--proposal", type=Path, help="a proposal JSON file instead of a reference")
    author.add_argument("--variant", default="authoring-base")
    author.add_argument("--receipt", type=Path)
    author.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)
    author.add_argument("--deadline", type=float, default=argparse.SUPPRESS)
    _add_entity_arguments(author, default_tools=MISSION_ENTITY_TOOLS)

    author_canary = subparsers.add_parser(
        "author-canary", help="a station that should be accepted and one that should be rejected"
    )
    author_canary.add_argument("--receipt", type=Path)
    author_canary.add_argument("--receipt-dir", type=Path, default=argparse.SUPPRESS)

    rail = subparsers.add_parser("rail", help="engineering rail measurement")
    rail.add_argument("--receipt", type=Path, default=argparse.SUPPRESS)
    transactions = subparsers.add_parser(
        "transactions", help="transaction stations on disposable real entities"
    )
    transactions.add_argument(
        "--run-dir", type=Path, default=Path("_diag/laboratory/transactions")
    )
    transactions.add_argument("--receipt", type=Path, default=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    mode = arguments.mode
    if mode == "self-check":
        return cmd_self_check(arguments)
    if mode == "canary":
        return cmd_canary(arguments)
    if mode == "mission":
        return cmd_mission(arguments)
    if mode == "entity-run":
        return cmd_entity_run(arguments)
    if mode == "portfolio":
        return cmd_portfolio(arguments)
    if mode == "night-shift":
        return cmd_night_shift(arguments)
    if mode == "rail":
        return cmd_rail(arguments)
    if mode == "transactions":
        return cmd_transactions(arguments)
    if mode == "discover":
        return cmd_discover(arguments)
    if mode == "discover-canary":
        return cmd_discover_canary(arguments)
    if mode == "shift":
        return cmd_shift(arguments)
    if mode == "shift-canary":
        return cmd_shift_canary(arguments)
    if mode == "discover-run":
        return cmd_discover_run(arguments)
    if mode == "author-run":
        return cmd_author_run(arguments)
    if mode == "author":
        return cmd_author(arguments)
    if mode == "author-canary":
        return cmd_author_canary(arguments)
    parser.error(f"unknown mode {mode!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
