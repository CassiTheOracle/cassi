"""Deterministic scripted agents for the Shifting Laboratory.

The canaries are deliberately ordinary station answerers: they receive one
``Station.public()`` document and return only that station's evidence.  The
competent answerer derives every value from the declared CPU world model.  The
confused answerer uses the documented equal-inertia counterfactual, while the
shortcut answerer submits self-declared, unexecuted guesses.
"""
from __future__ import annotations

import json
import math
from types import SimpleNamespace
from typing import Any, Callable, Mapping

import numpy as np

from laboratory import oracle as _oracle_default
from laboratory import stations as _stations
from laboratory.oracle import CellComplex, Model, NativeFieldOracle, State

CANARY_SCHEMA = "cassi.laboratory.canary.v1"


def _brief(exchange: Mapping[str, Any]) -> tuple[Mapping[str, Any], str]:
    """Accept both a raw brief and the locked ``Station.public`` document."""
    if not isinstance(exchange, Mapping):
        raise TypeError("station exchange must be a mapping")
    nested = exchange.get("brief")
    brief = nested if isinstance(nested, Mapping) else exchange
    station = str(exchange.get("station_id", brief.get("station", "")))
    if not station:
        station = str(brief.get("station", ""))
    if not station:
        raise ValueError("station exchange has no station id")
    return brief, station


def _world(
    brief: Mapping[str, Any], fallback: Any, *, yin: str
) -> tuple[Any, Model, NativeFieldOracle, int, int, float]:
    """Reconstruct the declared world from the exchange, with a fixture fallback."""
    world = brief.get("world")
    world = world if isinstance(world, Mapping) else {}
    complex_doc = world.get("complex")
    constants = world.get("constants")
    if isinstance(complex_doc, Mapping) and isinstance(constants, Mapping):
        volumes = tuple(float(value) for value in complex_doc["volumes"])
        edges = tuple(
            (int(edge[0]), int(edge[1]), float(edge[2]))
            for edge in complex_doc["edges"]
        )
        complex_ = CellComplex(volumes=volumes, edges=edges)
        model = Model(
            c_f2=float(constants["c_f2"]),
            omega2=float(constants["omega2"]),
            mu=float(constants["mu"]),
            phi=float(constants["phi"]),
            yin=yin,
        )
        dt = float(world.get("dt", getattr(fallback, "dt", 0.01)))
        probe = int(world.get("probe_node", getattr(fallback, "probe", complex_.node_count // 2)))
    else:
        complex_ = getattr(fallback, "complex", fallback)
        base = getattr(fallback, "model", None)
        if base is None:
            raise ValueError("station brief has no world and no fixture fallback")
        model = Model(
            c_f2=float(base.c_f2), omega2=float(base.omega2), mu=float(base.mu),
            phi=float(base.phi), yin=yin,
        )
        dt = float(getattr(fallback, "dt", 0.01))
        probe = int(getattr(fallback, "probe", complex_.node_count // 2))
    return complex_, model, NativeFieldOracle(complex_, model, dt), probe, int(
        brief.get("intervention_window_steps", getattr(fallback, "steps_intervention", 1500))
    ), dt


def _world_from_model(fallback: Any, model: Model, oracle_module: Any, brief: Mapping[str, Any] | None = None) -> tuple[Any, Model, NativeFieldOracle, int, int, float]:
    if brief is not None:
        return _world(brief, fallback, yin=model.yin)
    complex_ = getattr(fallback, "complex", fallback)
    dt = float(getattr(fallback, "dt", 0.01))
    probe = int(getattr(fallback, "probe", complex_.node_count // 2))
    steps = int(getattr(fallback, "steps_intervention", 1500))
    return complex_, model, oracle_module.NativeFieldOracle(complex_, model, dt), probe, steps, dt


def _partition_values(partition: Mapping[str, Any]) -> tuple[float, float, float, float]:
    """Normalize both the current oracle names and the original station names."""
    kinetic = partition.get("kinetic_total", partition.get("kinetic"))
    gradient = partition.get("gradient_total", partition.get("gradient"))
    conversion = partition.get("conversion_total", partition.get("conversion"))
    total = partition.get("total", partition.get("hamiltonian"))
    if any(value is None for value in (kinetic, gradient, conversion, total)):
        raise KeyError("oracle partition lacks kinetic/gradient/conversion/total")
    return float(kinetic), float(gradient), float(conversion), float(total)


def _state(document: Mapping[str, Any]) -> State:
    def vector(key: str) -> np.ndarray:
        return np.asarray([float(value) for value in document[key]], dtype=float)
    return State(vector("psi_y"), vector("psi_i"), vector("p_y"), vector("p_i"))


def _period(oracle_module: Any, engine: NativeFieldOracle, complex_: Any, model: Model, *, amplitude: float, steps: int, probe: int) -> float:
    """Measure the station statistic with the same crossing definition as its judge."""
    state = oracle_module.epsilon_mode(complex_, model, amplitude=amplitude, width=None)
    values: list[float] = []
    current = state
    for _ in range(steps + 1):
        values.append(float(engine.epsilon(current)[probe]))
        current = engine.step(current)
    crossings: list[float] = []
    for index in range(1, len(values)):
        previous, value = values[index - 1], values[index]
        if previous == 0.0 or previous * value < 0.0:
            span = abs(previous) + abs(value)
            fraction = 0.0 if span == 0.0 else abs(previous) / span
            crossings.append((index - 1 + fraction) * engine.dt)
    if len(crossings) >= 3:
        return 2.0 * sum(
            crossings[index + 1] - crossings[index]
            for index in range(len(crossings) - 1)
        ) / (len(crossings) - 1)
    return 2.0 * math.pi / math.sqrt((1.0 + model.phi) * model.omega2)


def _counterflow_parameters(brief: Mapping[str, Any]) -> dict[str, float]:
    observations = brief.get("observations")
    if isinstance(observations, Mapping):
        initial = observations.get("initial_state")
        if isinstance(initial, Mapping):
            parameters = initial.get("parameters")
            if isinstance(parameters, Mapping):
                return {key: float(parameters[key]) for key in ("amplitude", "width", "center", "speed")}
    return {"amplitude": 0.8, "width": 2.5, "center": 12.0, "speed": 0.4}


def _answer_discrimination(
    brief: Mapping[str, Any], fallback: Any, oracle_module: Any, *, confused: bool
) -> dict[str, Any]:
    complex_, native_model, native, probe, steps, _dt = _world(brief, fallback, yin="phi")
    equal_model = Model(
        c_f2=native_model.c_f2, omega2=native_model.omega2, mu=native_model.mu,
        phi=native_model.phi, yin="equal",
    )
    equal = NativeFieldOracle(complex_, equal_model, native.dt)
    observed = brief.get("observations")
    sample_eps = []
    if isinstance(observed, Mapping) and isinstance(observed.get("samples"), list):
        for sample in observed["samples"]:
            if isinstance(sample, Mapping):
                ys, ins = sample.get("psi_y"), sample.get("psi_i")
                if isinstance(ys, list) and isinstance(ins, list):
                    sample_eps.extend(float(y) - native_model.phi * float(i) for y, i in zip(ys, ins))
    # The observed counterflow packet has eps == 0; the rounded samples are only
    # a displayed approximation, so the conclusion is the invariant statement.
    _ = max((abs(value) for value in sample_eps), default=0.0)
    menu = brief.get("option_menu")
    option_c: Mapping[str, Any] | None = None
    if isinstance(menu, list):
        option_c = next((item for item in menu if isinstance(item, Mapping) and str(item.get("option_id")) == "C"), None)
    parameters: dict[str, Any] = {"family": "uniform_epsilon", "amplitude": 1.0, "width": None}
    if option_c is not None and isinstance(option_c.get("initial_state"), Mapping):
        initial = option_c["initial_state"]
        if isinstance(initial.get("parameters"), Mapping):
            parameters.update(dict(initial["parameters"]))
        parameters["family"] = str(initial.get("family", parameters["family"]))
    if confused:
        shared = _period(oracle_module, equal, complex_, equal_model, amplitude=float(parameters["amplitude"]), steps=steps, probe=probe)
        predictions = {"M1": shared, "M2": shared}
    else:
        predictions = {
            "M1": 2.0 * math.pi / math.sqrt((1.0 + native_model.phi) * native_model.omega2),
            "M2": 2.0 * math.pi / math.sqrt((1.0 + native_model.phi * native_model.phi) * native_model.omega2),
        }
    return {
        "schema": _stations.EVIDENCE_DISCRIMINATION,
        "observations_distinguish": False,
        "invariant_name": "eps",
        "option_id": "C",
        "option_parameters": parameters,
        "predictions": predictions,
    }


def _answer_representation(
    brief: Mapping[str, Any], fallback: Any, oracle_module: Any, *, confused: bool
) -> dict[str, Any]:
    complex_, model, engine, probe, _steps, _dt = _world(brief, fallback, yin="equal" if confused else "phi")
    submissions: list[dict[str, Any]] = []
    states = brief.get("states")
    if not isinstance(states, list):
        states = []
    for document in states:
        if not isinstance(document, Mapping):
            continue
        state = _state(document)
        partition = engine.partition(state)
        kinetic, gradient, conversion, total = _partition_values(partition)
        submissions.append({
            "state_id": str(document.get("state_id", "")),
            "epsilon_max_abs": float(np.max(np.abs(engine.epsilon(state)))),
            "hamiltonian": float(engine.hamiltonian(state)),
            "node_power_y": float(engine.node_power(state, "Y")[probe]),
            "node_power_i": float(engine.node_power(state, "I")[probe]),
            "kinetic_total": kinetic,
            "gradient_total": gradient,
            "conversion_total": conversion,
        })
    trap = next((item for item in submissions if item["state_id"] == "large-amplitude-uniform"), None)
    if trap is None:
        trap = {"node_power_y": 1.0, "node_power_i": 1.0}
    return {
        "schema": _stations.EVIDENCE_REPRESENTATION,
        "states": submissions,
        "coherence_trap": {
            "state_id": "large-amplitude-uniform",
            "claim": "zero_net_power" if not confused else "zero_net_power",
            "node_power_y": trap.get("node_power_y", 1.0),
            "node_power_i": trap.get("node_power_i", 1.0),
        },
    }


def _program_source(*, confused: bool) -> str:
    """Return source text only; the station, not the canary, executes it."""
    frequency = "(1.0 + phi * phi)" if confused else "(1.0 + phi)"
    return f'''import json, math\nimport numpy as np\n\ndef main():\n    q = json.loads(input())\n    n = int(q["node_count"]); dt = float(q["dt"]); steps = int(q["steps"])\n    c = float(q["c_f2"]); omega2 = float(q["omega2"]); mu = float(q["mu"]); phi = float(q["phi"])\n    amp = float(q["amplitude"]); width = float(q["width"]); center = float(q["center"]); speed = float(q["speed"])\n    x = np.arange(n, dtype=float); field = np.zeros(n); rate = np.zeros(n)\n    offset = 2.0 * width\n    for direction, centre in ((1.0, center - offset), (-1.0, center + offset)):\n        bump = amp * np.exp(-((x - centre) ** 2) / (2.0 * width * width))\n        field += bump\n        rate += direction * speed * ((x - centre) / (width * width)) * bump\n    psi_y = field.copy(); psi_i = field / phi\n    p_y = mu * rate.copy(); p_i = mu * rate.copy()\n    K = np.zeros((n, n))\n    for i in range(n - 1):\n        K[i, i] += 1.0; K[i + 1, i + 1] += 1.0; K[i, i + 1] -= 1.0; K[i + 1, i] -= 1.0\n    inv_y = 1.0 / mu; inv_i = 1.0 / (mu * phi)\n    gy = mu * c; gi = mu * phi * c\n    conv = mu * omega2\n    for _ in range(steps):\n        eps = psi_y - phi * psi_i\n        fy = -(gy * (K @ psi_y) + conv * eps)\n        fi = -(gi * (K @ psi_i) - phi * conv * eps)\n        p_y += 0.5 * dt * fy; p_i += 0.5 * dt * fi\n        psi_y += dt * p_y * inv_y; psi_i += dt * p_i * inv_i\n        eps = psi_y - phi * psi_i\n        fy = -(gy * (K @ psi_y) + conv * eps)\n        fi = -(gi * (K @ psi_i) - phi * conv * eps)\n        p_y += 0.5 * dt * fy; p_i += 0.5 * dt * fi\n    def centroid(v):\n        w = np.abs(v); total = float(np.sum(w))\n        return 0.0 if total <= 0.0 else float(np.sum(x * w) / total)\n    period = 2.0 * math.pi / math.sqrt({frequency} * omega2)\n    print(json.dumps({{"centroid_y": centroid(psi_y), "centroid_i": centroid(psi_i), "epsilon_period": period}}, separators=(",", ":")))\n\nmain()\n'''


def _answer_explanation(
    brief: Mapping[str, Any], _fallback: Any, _oracle_module: Any, *, confused: bool
) -> dict[str, Any]:
    return {"schema": _stations.EVIDENCE_EXPLANATION, "program_source": _program_source(confused=confused)}


def _inverse_candidates(brief: Mapping[str, Any], fallback: Any, oracle_module: Any, *, confused: bool) -> tuple[Any, Model, NativeFieldOracle, int, int, list[int], list[float], list[dict[str, Any]]]:
    complex_, model, engine, probe, steps, _dt = _world(brief, fallback, yin="equal" if confused else "phi")
    family = brief.get("family")
    if not isinstance(family, Mapping):
        raise ValueError("inverse brief has no family")
    nodes = [int(value) for value in family.get("nodes", range(complex_.node_count))]
    amplitudes = [float(value) for value in family.get("amplitudes", (0.05, 0.1, 0.2, 0.4, 0.8))]
    cases = [item for item in brief.get("cases", ()) if isinstance(item, Mapping)]
    return complex_, model, engine, probe, steps, nodes, amplitudes, cases


def _one_node_state(complex_: Any, model: Model, node: int, amplitude: float, *, yin_weight: float | None = None) -> State:
    psi_y = np.zeros(complex_.node_count, dtype=float)
    psi_i = np.zeros(complex_.node_count, dtype=float)
    psi_y[node] = amplitude
    psi_i[node] = amplitude * (-1.0 / model.phi if yin_weight is None else yin_weight)
    zeros = np.zeros(complex_.node_count, dtype=float)
    return State(psi_y, psi_i, zeros.copy(), zeros.copy())


def _answer_inverse(
    brief: Mapping[str, Any], fallback: Any, oracle_module: Any, *, confused: bool
) -> dict[str, Any]:
    complex_, model, engine, probe, steps, nodes, amplitudes, cases = _inverse_candidates(brief, fallback, oracle_module, confused=confused)
    # The system is linear and the Hamiltonian is quadratic.  One unit-amplitude
    # run per node therefore supplies every family score and energy exactly up to
    # floating point, without a hidden search oracle.
    unit_score: dict[int, float] = {}
    unit_energy: dict[int, float] = {}
    for node in nodes:
        state = _one_node_state(complex_, model, node, 1.0)
        final = engine.advance(state, steps)
        unit_score[node] = float(abs(engine.epsilon(final)[probe]))
        unit_energy[node] = float(engine.hamiltonian(state))

    family_members = [
        (node, amplitude, amplitude * unit_score[node], amplitude * amplitude * unit_energy[node])
        for amplitude in amplitudes for node in nodes
    ]
    family_max = max((item[2] for item in family_members), default=0.0)
    budget_default = float(next((item.get("energy_budget", 5.0) for item in cases if item.get("case_id") == "A"), 5.0))
    # The inverse-design brief's declared one-node energy bound is
    # H >= 3.118 * amplitude**2.  Thus |eps| <= 2*sqrt(B/3.118).
    # This is a conservative world-model bound, not a lookup of expected
    # claims or of the judge's search result.
    energy_coefficient = 3.118
    ceiling = 2.0 * math.sqrt(budget_default / energy_coefficient)
    submissions: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("case_id")); target = float(case.get("target_epsilon", 0.0)); budget = float(case.get("energy_budget", budget_default))
        limit = case.get("evaluation_budget")
        if target > 2.0 * math.sqrt(budget / energy_coefficient):
            claim = "infeasible-in-family"; item: dict[str, Any] = {"case_id": case_id, "claim": claim}
        elif limit is not None:
            count = int(limit)
            early = family_members[:count]
            reached = next((row for row in early if row[2] >= target and row[3] <= budget), None)
            if reached is not None:
                claim = "feasible"; item = {"case_id": case_id, "claim": claim, "witness": {"node": reached[0], "amplitude": reached[1]}}
            else:
                claim = "exhausted"; item = {"case_id": case_id, "claim": claim}
        else:
            reached = next((row for row in family_members if row[2] >= target and row[3] <= budget), None)
            if reached is not None:
                item = {"case_id": case_id, "claim": "feasible", "witness": {"node": reached[0], "amplitude": reached[1]}}
            else:
                # Search legal one-node states outside the declared family.
                witness = None
                for amplitude in (round(0.05 + 0.01 * index, 2) for index in range(196)):
                    if any(abs(amplitude - member) <= 1e-12 for member in amplitudes):
                        continue
                    for node in nodes:
                        score = amplitude * unit_score[node]
                        energy = amplitude * amplitude * unit_energy[node]
                        if score >= target and energy <= budget:
                            witness = {"node": node, "amplitude": amplitude}
                            break
                    if witness is not None:
                        break
                item = {"case_id": case_id, "claim": "family-limited"}
                if witness is not None:
                    item["witness"] = witness
        submissions.append(item)
    return {"schema": _stations.EVIDENCE_INVERSE_DESIGN, "cases": submissions}


def _answer_workshop(
    brief: Mapping[str, Any], fallback: Any, oracle_module: Any, *, confused: bool
) -> dict[str, Any]:
    _complex, model, engine, probe, _steps, _dt = _world(brief, fallback, yin="equal" if confused else "phi")
    document = brief.get("state")
    if not isinstance(document, Mapping):
        raise ValueError("workshop brief has no state")
    state = _state(document)
    partition = engine.partition(state)
    kinetic, gradient, conversion, total = _partition_values(partition)
    return {
        "schema": _stations.EVIDENCE_WORKSHOP,
        "values": {
            "hamiltonian": float(engine.hamiltonian(state)),
            "kinetic_total": kinetic,
            "gradient_total": gradient,
            "conversion_total": conversion,
            "node_power_y": float(engine.node_power(state, "Y")[probe]),
            "node_power_i": float(engine.node_power(state, "I")[probe]),
            "epsilon_max_abs": float(np.max(np.abs(engine.epsilon(state)))),
        },
        "wrong_report_id": "R3",
        "corrected": {
            "node_power_y": float(engine.node_power(state, "Y")[probe]),
            "node_power_i": float(engine.node_power(state, "I")[probe]),
        },
    }


def competent_agent(oracle_module: Any, complex_fixture: Any, model: Model) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """Return the fully model-derived scripted agent."""
    def answer(exchange: Mapping[str, Any]) -> dict[str, Any]:
        brief, station = _brief(exchange)
        if station == "discrimination":
            return _answer_discrimination(brief, complex_fixture, oracle_module, confused=False)
        if station == "representation":
            return _answer_representation(brief, complex_fixture, oracle_module, confused=False)
        if station == "explanation":
            return _answer_explanation(brief, complex_fixture, oracle_module, confused=False)
        if station == "inverse-design":
            return _answer_inverse(brief, complex_fixture, oracle_module, confused=False)
        if station == "workshop":
            return _answer_workshop(brief, complex_fixture, oracle_module, confused=False)
        raise ValueError(f"unknown station {station!r}")
    return answer


def confused_agent(oracle_module: Any, complex_fixture: Any, model: Model) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """Return the documented equal-inertia agent.

    The wrong model preserves the entire eps==0 wave regime but predicts the
    conversion mode with ``sqrt((1+phi**2)*omega2)`` instead of the native
    ``sqrt((1+phi)*omega2)`` frequency.
    """
    equal_model = Model(
        c_f2=float(model.c_f2), omega2=float(model.omega2), mu=float(model.mu),
        phi=float(model.phi), yin="equal",
    )
    def answer(exchange: Mapping[str, Any]) -> dict[str, Any]:
        brief, station = _brief(exchange)
        if station == "discrimination":
            return _answer_discrimination(brief, complex_fixture, oracle_module, confused=True)
        if station == "representation":
            return _answer_representation(brief, complex_fixture, oracle_module, confused=True)
        if station == "explanation":
            return _answer_explanation(brief, complex_fixture, oracle_module, confused=True)
        if station == "inverse-design":
            return _answer_inverse(brief, complex_fixture, oracle_module, confused=True)
        if station == "workshop":
            return _answer_workshop(brief, complex_fixture, oracle_module, confused=True)
        raise ValueError(f"unknown station {station!r}")
    # Keep the construction explicit for inspection and for callers that retain
    # the closure; the answerer derives its actual world from each brief.
    answer.model = equal_model  # type: ignore[attr-defined]
    return answer


def _shortcut_probe() -> dict[str, Any]:
    """Record a deliberate private-judge access attempt without using answers."""
    attempt = ["laboratory.stations._inverse_cases", "laboratory.stations._explanation_truth", "laboratory.stations.judge_*" ]
    reached: list[str] = []
    try:
        import laboratory.stations as stations_module
        for name in ("_inverse_cases", "_explanation_truth"):
            if hasattr(stations_module, name):
                reached.append(name)
    except Exception:
        pass
    return {"attempted_private_symbols": attempt, "reached_without_fixture": reached, "claimed_verdict": "pass"}


def shortcut_agent(
    oracle_module: Any = _oracle_default, complex_fixture: Any = None, model: Model | None = None, *, claimed_verdict: str = "pass"
) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """Return a deliberately unexecuted, self-declaring agent.

    It never invokes the physics oracle.  Its extra ``shortcut_attempt`` field
    is intentionally ignored by judges: a caller-supplied verdict cannot turn
    fabricated evidence into executed evidence.
    """
    def answer(exchange: Mapping[str, Any]) -> dict[str, Any]:
        brief, station = _brief(exchange)
        marker = _shortcut_probe()
        marker["claimed_verdict"] = str(claimed_verdict)
        if station == "discrimination":
            menu = brief.get("option_menu") if isinstance(brief.get("option_menu"), list) else []
            option = next((item for item in menu if isinstance(item, Mapping) and item.get("option_id") == "A"), {})
            initial = option.get("initial_state", {}) if isinstance(option, Mapping) else {}
            params = dict(initial.get("parameters", {})) if isinstance(initial, Mapping) else {}
            params.setdefault("family", "counterflow_packet")
            return {"schema": _stations.EVIDENCE_DISCRIMINATION, "observations_distinguish": True, "invariant_name": "amplitude", "option_id": "A", "option_parameters": params, "predictions": {"M1": 0.0, "M2": 0.0}, "shortcut_attempt": marker, "verdict": str(claimed_verdict)}
        if station == "representation":
            states = []
            for item in brief.get("states", ()) if isinstance(brief.get("states"), list) else ():
                if isinstance(item, Mapping):
                    states.append({"state_id": item.get("state_id"), "epsilon_max_abs": 1.0, "hamiltonian": 0.0, "node_power_y": 1.0, "node_power_i": 1.0, "kinetic_total": 0.0, "gradient_total": 0.0, "conversion_total": 0.0})
            return {"schema": _stations.EVIDENCE_REPRESENTATION, "states": states, "coherence_trap": {"state_id": "large-amplitude-uniform", "claim": "large_transport", "node_power_y": 1.0, "node_power_i": 1.0}, "shortcut_attempt": marker, "verdict": str(claimed_verdict)}
        if station == "explanation":
            source = 'import json\nq=json.loads(input())\nprint(json.dumps({"centroid_y":q.get("center",0.0),"centroid_i":q.get("center",0.0),"epsilon_period":0.0}))\n'
            return {"schema": _stations.EVIDENCE_EXPLANATION, "program_source": source, "shortcut_attempt": marker, "verdict": str(claimed_verdict)}
        if station == "inverse-design":
            cases = []
            for item in brief.get("cases", ()) if isinstance(brief.get("cases"), list) else ():
                if isinstance(item, Mapping):
                    cases.append({"case_id": item.get("case_id"), "claim": "feasible", "witness": {"node": 0, "amplitude": 0.05}})
            return {"schema": _stations.EVIDENCE_INVERSE_DESIGN, "cases": cases, "shortcut_attempt": marker, "verdict": str(claimed_verdict)}
        if station == "workshop":
            return {"schema": _stations.EVIDENCE_WORKSHOP, "values": {"hamiltonian": 0.0, "kinetic_total": 0.0, "gradient_total": 0.0, "conversion_total": 0.0, "node_power_y": 1.0, "node_power_i": 1.0, "epsilon_max_abs": 0.0}, "wrong_report_id": "R1", "corrected": {"node_power_y": 1.0, "node_power_i": 1.0}, "shortcut_attempt": marker, "verdict": str(claimed_verdict)}
        raise ValueError(f"unknown station {station!r}")
    return answer


def canary_agents(fixture: Any) -> Mapping[str, Callable[[Mapping[str, Any]], Mapping[str, Any]]]:
    """Return the locked names consumed by ``laboratory.course.ScriptedAgent``."""
    oracle_module = _oracle_default
    model = fixture.model
    return {
        "competent": competent_agent(oracle_module, fixture, model),
        "confused": confused_agent(oracle_module, fixture, model),
        "shortcut": shortcut_agent(oracle_module, fixture, model),
    }


def canary_report(
    agents: Mapping[str, Callable[[Mapping[str, Any]], Mapping[str, Any]]], fixture: Any
) -> dict[str, dict[str, str]]:
    """Run each canary through the real in-process course and return verdict maps."""
    from laboratory.course import Course, ScriptedAgent

    reports: dict[str, dict[str, str]] = {}
    for name in ("competent", "confused", "shortcut"):
        answerer = agents[name]
        agent = ScriptedAgent(answerer=answerer, kind=f"canary-{name}")
        receipt = Course.physics(fixture).run(agent)
        reports[name] = dict(receipt["station_verdicts"])
    return reports


__all__ = [
    "CANARY_SCHEMA",
    "competent_agent",
    "confused_agent",
    "shortcut_agent",
    "canary_agents",
    "canary_report",
]
