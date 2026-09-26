"""Station definitions, briefs, evidence schemas and independent judges.

The course gives the agent observations and a question.  Everything it must
produce is checked here against the physics oracle in `laboratory.oracle` --
an independent CPU implementation of the qualified release equations.  The
agent never sees a judge, an oracle internal or the outcome of the
intervention it proposes: it forecasts first, and the judge runs the world.

Evidence schemas are versioned so a mission on the field-brain entity and a
scripted canary submit exactly the same document.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from laboratory import oracle as oracle_module
from laboratory.oracle import CellComplex, Model, NativeFieldOracle, State

STATION_REPORT_SCHEMA = "cassi.laboratory.station-report.v1"
MISSION_SCHEMA = "cassi.laboratory.mission.v1"
MISSION_EVIDENCE_SCHEMA = "cassi.laboratory.mission-evidence.v1"
COURSE_SCHEMA = "cassi.laboratory.course-receipt.v1"

EVIDENCE_DISCRIMINATION = "cassi.laboratory.evidence.discrimination.v1"
EVIDENCE_REPRESENTATION = "cassi.laboratory.evidence.representation.v1"
EVIDENCE_EXPLANATION = "cassi.laboratory.evidence.explanation.v1"
EVIDENCE_INVERSE_DESIGN = "cassi.laboratory.evidence.inverse-design.v1"
EVIDENCE_WORKSHOP = "cassi.laboratory.evidence.workshop.v1"

DISCRIMINATION_SEPARATION = 1e-2
PREDICTION_TOLERANCE = 2e-2
ALGEBRA_TOLERANCE = 1e-6
ALGEBRA_ABSOLUTE = 1e-9
EXPLANATION_TOLERANCE = 1e-3
EXPLANATION_HOLDOUT_MARGIN = 1e-2
WORKSHOP_TOLERANCE = 1e-6
INVERSE_BUDGET = 20

PHI = (1.0 + math.sqrt(5.0)) / 2.0


class LaboratoryError(RuntimeError):
    """Raised when a station fixture or evidence document is unusable."""


# --------------------------------------------------------------------------
# fixture


@dataclass(frozen=True, slots=True)
class Fixture:
    """The declared world, the observations given to the agent and the cases.

    Every field is JSON-safe so the brief rendered from it is reproducible and
    the fixture identity below covers exactly what the agent was told.
    """

    complex: CellComplex
    model: Model
    dt: float
    observed_packet: dict[str, float]
    steps_observed: int
    sample_every: int
    steps_intervention: int
    probe: int
    variant: str
    representation_states: tuple[dict[str, Any], ...]
    inverse_cases: tuple[dict[str, Any], ...]
    inverse_search: dict[str, Any]
    workshop_reports: tuple[dict[str, Any], ...]
    workshop_state: dict[str, Any]

    # ---------------------------------------------------------------- shapes
    @property
    def node_count(self) -> int:
        return self.complex.node_count

    def model_document(self) -> dict[str, Any]:
        return {
            "phi": self.model.phi,
            "c_f2": self.model.c_f2,
            "omega2": self.model.omega2,
            "mu": self.model.mu,
        }

    def complex_document(self) -> dict[str, Any]:
        return {
            "node_count": self.complex.node_count,
            "volumes": list(self.complex.volumes),
            "edges": [list(edge) for edge in self.complex.edges],
            "registration": "w = A/d; K = B^T W B; L = -M^-1 K",
        }

    def candidate_mechanisms(self) -> tuple[dict[str, Any], ...]:
        """The two mechanism descriptions the agent must tell apart."""

        native = Model(
            c_f2=self.model.c_f2, omega2=self.model.omega2, mu=self.model.mu,
            phi=self.model.phi, yin="phi",
        )
        equal = Model(
            c_f2=self.model.c_f2, omega2=self.model.omega2, mu=self.model.mu,
            phi=self.model.phi, yin="equal",
        )
        return (
            {
                "mechanism_id": "M1",
                "description": (
                    "canonical momenta P_Y = mu M psi_dot_Y and P_I = mu*phi M "
                    "psi_dot_I with gradient coefficients b_Y = mu c_f2 and "
                    "b_I = mu*phi*c_f2 and the conversion potential "
                    "(mu omega2 / 2) sum V eps^2"
                ),
                "model": native.as_dict(),
            },
            {
                "mechanism_id": "M2",
                "description": (
                    "canonical momenta P_Y = mu M psi_dot_Y and P_I = mu M "
                    "psi_dot_I with gradient coefficients b_Y = mu c_f2 and "
                    "b_I = mu c_f2 and the same conversion potential"
                ),
                "model": equal.as_dict(),
            },
        )

    def observation_document(self) -> dict[str, Any]:
        return {
            "schema": "cassi.laboratory.observations.v1",
            "variant": self.variant,
            "initial_state": {
                "family": "counterflow_packet",
                "parameters": dict(self.observed_packet),
            },
            "dt": self.dt,
            "samples": self.observed_samples(),
        }

    def observed_samples(self) -> list[dict[str, Any]]:
        engine = self.engine(self.model)
        packet = self.observed_packet
        state = oracle_module.counterflow_packet(
            self.complex,
            self.model,
            amplitude=packet["amplitude"],
            width=packet["width"],
            center=packet["center"],
            speed=packet["speed"],
        )
        samples: list[dict[str, Any]] = []
        time = 0.0
        for index in range(self.steps_observed + 1):
            if index % self.sample_every == 0:
                samples.append(
                    {
                        "step": index,
                        "time": round(time, 6),
                        "psi_y": [round(float(value), 6) for value in state.psi_y],
                        "psi_i": [round(float(value), 6) for value in state.psi_i],
                    }
                )
            state = engine.step(state)
            time += self.dt
        return samples

    def engine(self, model: Model) -> NativeFieldOracle:
        return NativeFieldOracle(self.complex, model, self.dt)

    @property
    def native(self) -> Model:
        return Model(
            c_f2=self.model.c_f2, omega2=self.model.omega2, mu=self.model.mu,
            phi=self.model.phi, yin="phi",
        )

    @property
    def counterfactual(self) -> Model:
        return Model(
            c_f2=self.model.c_f2, omega2=self.model.omega2, mu=self.model.mu,
            phi=self.model.phi, yin="equal",
        )

    def fixture_id(self) -> str:
        payload = {
            "complex": self.complex_document(),
            "model": self.model_document(),
            "dt": self.dt,
            "variant": self.variant,
            "observed_packet": self.observed_packet,
            "steps_observed": self.steps_observed,
            "sample_every": self.sample_every,
            "steps_intervention": self.steps_intervention,
            "probe": self.probe,
            "representation_states": self.representation_states,
            "inverse_cases": self.inverse_cases,
            "workshop_reports": self.workshop_reports,
            "workshop_state": self.workshop_state,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


DEFAULT_PACKET: dict[str, float] = {
    "amplitude": 0.8,
    "width": 2.5,
    "center": 12.0,
    "speed": 0.4,
}

PORTFOLIO_VARIANTS: tuple[dict[str, Any], ...] = (
    {"variant": "counterflow-1", "packet": dict(DEFAULT_PACKET)},
    {
        "variant": "counterflow-2",
        "packet": {"amplitude": 1.1, "width": 1.8, "center": 6.0, "speed": 0.7},
    },
    {
        "variant": "counterflow-3",
        "packet": {"amplitude": 0.5, "width": 4.0, "center": 18.0, "speed": 0.25},
    },
)


def build_fixture(
    *,
    node_count: int = 24,
    variant: str = "counterflow-1",
    packet: Mapping[str, Any] | None = None,
    steps_observed: int = 600,
    sample_every: int = 50,
    steps_intervention: int = 1500,
    dt: float = 0.01,
) -> Fixture:
    """Build the declared world plus its frozen cases (deterministic)."""

    complex_ = CellComplex.chain(node_count, spacing=1.0, conductance=1.0)
    model = Model(c_f2=1.0, omega2=0.25, mu=1.0)
    observed = {key: float(value) for key, value in dict(packet or DEFAULT_PACKET).items()}
    for key in ("amplitude", "width", "center", "speed"):
        if key not in observed:
            raise LaboratoryError(f"observed packet is missing {key!r}")
    skeleton = Fixture(
        complex=complex_,
        model=model,
        dt=dt,
        observed_packet=observed,
        steps_observed=steps_observed,
        sample_every=sample_every,
        steps_intervention=steps_intervention,
        probe=node_count // 2,
        variant=variant,
        representation_states=(),
        inverse_cases=(),
        inverse_search={},
        workshop_reports=(),
        workshop_state={},
    )
    states = _representation_states(skeleton)
    cases, search = _inverse_cases(skeleton)
    reports, state_document = _workshop_material(skeleton)
    return Fixture(
        complex=complex_,
        model=model,
        dt=dt,
        observed_packet=observed,
        steps_observed=steps_observed,
        sample_every=sample_every,
        steps_intervention=steps_intervention,
        probe=skeleton.probe,
        variant=variant,
        representation_states=states,
        inverse_cases=cases,
        inverse_search=search,
        workshop_reports=reports,
        workshop_state=state_document,
    )


def default_fixture(*, node_count: int = 24) -> Fixture:
    return build_fixture(node_count=node_count)


# --------------------------------------------------------------------------
# shared measurement helpers


def _epsilon_series(
    engine: NativeFieldOracle, state: State, steps: int, probe: int
) -> list[float]:
    series: list[float] = []
    current = state
    for _ in range(steps + 1):
        series.append(float(engine.epsilon(current)[probe]))
        current = engine.step(current)
    return series


def _period_from_zero_crossings(series: Sequence[float], dt: float) -> float | None:
    crossings: list[float] = []
    for index in range(1, len(series)):
        previous, current = series[index - 1], series[index]
        if previous == 0.0 or previous * current < 0.0:
            span = abs(previous) + abs(current)
            fraction = 0.0 if span == 0.0 else abs(previous) / span
            crossings.append((index - 1 + fraction) * dt)
    if len(crossings) < 3:
        return None
    spacings = [crossings[i + 1] - crossings[i] for i in range(len(crossings) - 1)]
    mean = sum(spacings) / len(spacings)
    return 2.0 * mean


def _centroid(psi: Any, probe_only: bool = False) -> float:
    weights = [abs(float(value)) for value in psi]
    total = sum(weights)
    if total <= 0.0:
        return 0.0
    return sum(index * weight for index, weight in enumerate(weights)) / total


def _statistic(
    engine: NativeFieldOracle,
    option_id: str,
    parameters: Mapping[str, Any],
    steps: int,
    probe: int,
) -> float | None:
    """Return the declared statistic for one option, or None if undefined."""

    family = str(parameters["family"])
    if family == "counterflow_packet":
        state = oracle_module.counterflow_packet(
            engine.complex,
            engine.model,
            amplitude=float(parameters["amplitude"]),
            width=float(parameters["width"]),
            center=float(parameters["center"]),
            speed=float(parameters["speed"]),
        )
        first_y = _centroid(state.psi_y)
        first_i = _centroid(state.psi_i)
        final = engine.advance(state, steps)
        travel = steps * engine.dt
        if option_id.endswith("_y"):
            return (_centroid(final.psi_y) - first_y) / travel
        return (_centroid(final.psi_i) - first_i) / travel
    if family == "uniform_epsilon":
        state = oracle_module.epsilon_mode(
            engine.complex, engine.model, amplitude=float(parameters["amplitude"]), width=None,
        )
        if option_id.endswith("_period"):
            series = _epsilon_series(engine, state, steps, probe)
            return _period_from_zero_crossings(series, engine.dt)
        series = _epsilon_series(engine, state, steps, probe)
        return max(abs(value) for value in series)
    if family == "resting":
        state = oracle_module.resting(engine.complex)
        series = _epsilon_series(engine, state, steps, probe)
        return max(abs(value) for value in series)
    raise LaboratoryError(f"unsupported initial-state family {family!r}")


def discrimination_options(fixture: Fixture) -> tuple[dict[str, Any], ...]:
    packet = dict(fixture.observed_packet)
    return (
        {
            "option_id": "A",
            "initial_state": {"family": "counterflow_packet", "parameters": dict(packet)},
            "statistic": "yang_centroid_speed",
            "statistic_key": "centroid_speed_y",
        },
        {
            "option_id": "B",
            "initial_state": {"family": "counterflow_packet", "parameters": dict(packet)},
            "statistic": "yin_centroid_speed",
            "statistic_key": "centroid_speed_i",
        },
        {
            "option_id": "C",
            "initial_state": {"family": "uniform_epsilon", "parameters": {"amplitude": 1.0, "width": None}},
            "statistic": "epsilon_period",
            "statistic_key": "epsilon_period",
        },
        {
            "option_id": "D",
            "initial_state": {"family": "uniform_epsilon", "parameters": {"amplitude": 1.0, "width": None}},
            "statistic": "max_epsilon",
            "statistic_key": "max_epsilon",
        },
        {
            "option_id": "E",
            "initial_state": {"family": "resting", "parameters": {}},
            "statistic": "max_epsilon",
            "statistic_key": "max_epsilon",
        },
    )


def _option_statistic(fixture: Fixture, engine: NativeFieldOracle, option_id: str) -> float | None:
    option = next(item for item in discrimination_options(fixture) if item["option_id"] == option_id)
    parameters = dict(option["initial_state"]["parameters"])
    parameters["family"] = option["initial_state"]["family"]
    return _statistic(
        engine, option["statistic_key"], parameters, fixture.steps_intervention, fixture.probe,
    )


# --------------------------------------------------------------------------
# station 1 -- discrimination


def brief_discrimination(fixture: Fixture) -> dict[str, Any]:
    return {
        "station": "discrimination",
        "title": "One instrument that cannot yet tell a difference",
        "world": {
            "complex": fixture.complex_document(),
            "constants": fixture.model_document(),
            "dt": fixture.dt,
            "probe_node": fixture.probe,
        },
        "observations": fixture.observation_document(),
        "candidate_mechanisms": [dict(item) for item in fixture.candidate_mechanisms()],
        "question": (
            "Two candidate mechanisms are proposed for the same world and both are "
            "said to reproduce the observations above. (1) State whether the "
            "observations alone can tell them apart, and name the quantity that "
            "makes it so. (2) Choose exactly one option from the menu below whose "
            "outcome separates the two mechanisms by at least 1e-2 relative, and "
            "give its parameter values. (3) Predict the measured statistic under "
            "each mechanism, before any run is performed. The score is taken from "
            "a run you never see."
        ),
        "option_menu": [
            {
                "option_id": item["option_id"],
                "initial_state": item["initial_state"],
                "statistic": item["statistic"],
            }
            for item in discrimination_options(fixture)
        ],
        "intervention_window_steps": fixture.steps_intervention,
        "evidence_schema": EVIDENCE_DISCRIMINATION,
    }


def judge_discrimination(fixture: Fixture, evidence: Mapping[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    native = fixture.engine(fixture.native)
    counterfactual = fixture.engine(fixture.counterfactual)

    observed = oracle_module.counterflow_packet(
        fixture.complex,
        fixture.model,
        amplitude=fixture.observed_packet["amplitude"],
        width=fixture.observed_packet["width"],
        center=fixture.observed_packet["center"],
        speed=fixture.observed_packet["speed"],
    )
    engine_native = native
    observed_epsilon = 0.0
    state = observed
    for _ in range(fixture.steps_observed + 1):
        observed_epsilon = max(observed_epsilon, float(abs(engine_native.epsilon(state)).max()))
        state = engine_native.step(state)

    claimed_obvious = bool(evidence.get("observations_distinguish", False))
    checks.append(
        {
            "name": "observations are reported as non-discriminating",
            "ok": claimed_obvious is False,
            "detail": (
                "the observed run keeps eps identically zero, so the two mechanisms "
                "share its entire wave behaviour"
            ),
            "numbers": {"observed_max_abs_epsilon": observed_epsilon},
        }
    )
    checks[-1]["ok"] = checks[-1]["ok"] and observed_epsilon <= 1e-9

    invariant_name = str(evidence.get("invariant_name", "")).strip()
    checks.append(
        {
            "name": "the named invariant is the conversion quantity",
            "ok": invariant_name in {"eps", "epsilon", "psi_y - phi*psi_i", "conversion"},
            "detail": f"named invariant: {invariant_name!r}",
            "numbers": {},
        }
    )

    option_id = str(evidence.get("option_id", "")).strip().upper()
    parameters = evidence.get("option_parameters")
    if option_id not in {item["option_id"] for item in discrimination_options(fixture)}:
        raise LaboratoryError(f"unknown option {option_id!r}")
    if not isinstance(parameters, Mapping):
        raise LaboratoryError("option_parameters must be an object")
    chosen = dict(parameters)
    option_defaults = next(
        item for item in discrimination_options(fixture) if item["option_id"] == option_id
    )
    chosen.setdefault("family", option_defaults["initial_state"]["family"])

    native_value = _statistic(
        native, option_defaults["statistic_key"], chosen, fixture.steps_intervention, fixture.probe,
    )
    counterfactual_value = _statistic(
        counterfactual, option_defaults["statistic_key"], chosen, fixture.steps_intervention, fixture.probe,
    )
    separation = _separation(native_value, counterfactual_value)
    checks.append(
        {
            "name": "chosen intervention separates the mechanisms",
            "ok": separation is not None and separation >= DISCRIMINATION_SEPARATION,
            "detail": (
                f"option {option_id} statistic {option_defaults['statistic']}: "
                f"M1={native_value!r} M2={counterfactual_value!r}"
            ),
            "numbers": {"separation": separation, "threshold": DISCRIMINATION_SEPARATION},
        }
    )

    predictions = evidence.get("predictions")
    if not isinstance(predictions, Mapping):
        raise LaboratoryError("predictions must be an object")
    predicted = {
        "M1": predictions.get("M1"),
        "M2": predictions.get("M2"),
    }
    errors = {
        "M1": _relative_error(native_value, predicted["M1"]),
        "M2": _relative_error(counterfactual_value, predicted["M2"]),
    }
    prediction_separation = _separation(predicted["M1"], predicted["M2"])
    checks.append(
        {
            "name": "both forecasts match the run",
            "ok": all(
                error is not None and error <= PREDICTION_TOLERANCE for error in errors.values()
            ),
            "detail": json.dumps({"predicted": predicted, "relative_errors": errors}, sort_keys=True),
            "numbers": {key: value for key, value in errors.items()},
        }
    )
    checks.append(
        {
            "name": "the two forecasts are themselves different",
            "ok": prediction_separation is not None
            and prediction_separation >= DISCRIMINATION_SEPARATION,
            "detail": (
                "an agent that predicts one number for both mechanisms has not "
                "found the discriminating observable"
            ),
            "numbers": {"separation": prediction_separation},
        }
    )

    menu_separations: dict[str, Any] = {}
    for option in discrimination_options(fixture):
        parameters_seen = dict(option["initial_state"]["parameters"])
        parameters_seen["family"] = option["initial_state"]["family"]
        left = _statistic(
            native, option["statistic_key"], parameters_seen, fixture.steps_intervention, fixture.probe,
        )
        right = _statistic(
            counterfactual, option["statistic_key"], parameters_seen, fixture.steps_intervention, fixture.probe,
        )
        menu_separations[option["option_id"]] = {
            "statistic": option["statistic"],
            "separation": _separation(left, right),
        }
    controls.append(
        {
            "name": "non-discriminating options stay below the threshold",
            "ok": sum(
                1
                for item in menu_separations.values()
                if item["separation"] is not None and item["separation"] >= DISCRIMINATION_SEPARATION
            )
            == 1,
            "detail": f"exactly one option separates; the rest are the control: {json.dumps(menu_separations, sort_keys=True)}",
        }
    )

    verdict = "fail" if not all(item["ok"] for item in checks) else "pass"
    return _report(
        "discrimination", verdict, checks, controls,
        {
            "chosen_option": option_id,
            "menu_separations": menu_separations,
            "observed_max_abs_epsilon": observed_epsilon,
        },
        [
            "forecasts were taken before the judge ran the intervention",
            "the judge's own run is the only outcome used",
        ],
    )


def _separation(left: Any, right: Any) -> float | None:
    try:
        first, second = float(left), float(right)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(first) and math.isfinite(second)):
        return None
    scale = max(abs(first), abs(second))
    if scale <= 0.0:
        return 0.0
    return abs(first - second) / scale


def _relative_error(truth: Any, claimed: Any) -> float | None:
    try:
        reference, value = float(truth), float(claimed)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(reference) and math.isfinite(value)):
        return None
    scale = abs(reference)
    if scale <= ALGEBRA_ABSOLUTE:
        return abs(value - reference)
    return abs(value - reference) / scale


# --------------------------------------------------------------------------
# station 2 -- representation


def _representation_states(fixture: Fixture) -> tuple[dict[str, Any], ...]:
    native = fixture.engine(fixture.native)
    packet = oracle_module.counterflow_packet(
        fixture.complex,
        fixture.model,
        amplitude=fixture.observed_packet["amplitude"],
        width=fixture.observed_packet["width"],
        center=fixture.observed_packet["center"],
        speed=fixture.observed_packet["speed"],
    )
    mixed = native.advance(packet, 300)
    excited = oracle_module.epsilon_mode(
        fixture.complex, fixture.model, amplitude=0.4, width=None,
    )
    mixed_arrays = (
        mixed.psi_y + excited.psi_y,
        mixed.psi_i + excited.psi_i,
        mixed.p_y,
        mixed.p_i,
    )
    states = []
    documents = [
        ("packet-at-rest", packet),
        ("uniform-conversion", excited),
        ("mixed-state", State(*mixed_arrays)),
    ]
    for state_id, state in documents:
        states.append(
            {
                "state_id": state_id,
                "psi_y": [round(float(value), 6) for value in state.psi_y],
                "psi_i": [round(float(value), 6) for value in state.psi_i],
                "p_y": [round(float(value), 6) for value in state.p_y],
                "p_i": [round(float(value), 6) for value in state.p_i],
            }
        )
    quarter = int(round((math.pi / 2.0) / (math.sqrt((1.0 + PHI) * fixture.model.omega2) * fixture.dt)))
    coherent = native.advance(excited, quarter)
    states.append(
        {
            "state_id": "large-amplitude-uniform",
            "psi_y": [round(float(value), 6) for value in coherent.psi_y],
            "psi_i": [round(float(value), 6) for value in coherent.psi_i],
            "p_y": [round(float(value), 6) for value in coherent.p_y],
            "p_i": [round(float(value), 6) for value in coherent.p_i],
        }
    )
    return tuple(states)


def _state_from_document(document: Mapping[str, Any]) -> State:
    import numpy as np

    def vector(key: str) -> np.ndarray:
        return np.asarray([float(value) for value in document[key]], dtype=float)

    return State(vector("psi_y"), vector("psi_i"), vector("p_y"), vector("p_i"))


def brief_representation(fixture: Fixture) -> dict[str, Any]:
    return {
        "station": "representation",
        "title": "The quantities the instrument never reports",
        "world": {
            "complex": fixture.complex_document(),
            "constants": fixture.model_document(),
            "probe_node": fixture.probe,
        },
        "states": [dict(state) for state in fixture.representation_states],
        "question": (
            "For every declared state, report the invariant quantities the "
            "instrument does not display: the maximum absolute conversion "
            "quantity eps = psi_y - phi*psi_i, the total energy, its kinetic, "
            "gradient and conversion parts, and the net power entering the probe "
            "node in each channel. One state carries large amplitudes with no "
            "net transport at all: state that explicitly, with its numbers."
        ),
        "evidence_schema": EVIDENCE_REPRESENTATION,
    }


def judge_representation(fixture: Fixture, evidence: Mapping[str, Any]) -> dict[str, Any]:
    engine = fixture.engine(fixture.native)
    truth: dict[str, dict[str, float]] = {}
    for document in fixture.representation_states:
        state = _state_from_document(document)
        partition = engine.partition(state)
        truth[document["state_id"]] = {
            "epsilon_max_abs": float(abs(engine.epsilon(state)).max()),
            "hamiltonian": float(engine.hamiltonian(state)),
            "node_power_y": float(engine.node_power(state, "Y")[fixture.probe]),
            "node_power_i": float(engine.node_power(state, "I")[fixture.probe]),
            "kinetic_total": float(partition["kinetic"]),
            "gradient_total": float(partition["gradient"]),
            "conversion_total": float(partition["conversion"]),
        }

    submissions = evidence.get("states")
    if not isinstance(submissions, list):
        raise LaboratoryError("states must be a list")
    by_id = {str(item.get("state_id")): item for item in submissions if isinstance(item, Mapping)}

    checks: list[dict[str, Any]] = []
    worst: dict[str, Any] = {}
    missing: list[str] = []
    for state_id, expected in truth.items():
        submission = by_id.get(state_id)
        if submission is None:
            missing.append(state_id)
            continue
        errors = {
            key: _relative_error(expected[key], submission.get(key))
            for key in expected
        }
        worst[state_id] = errors
        ok = all(
            error is not None and error <= ALGEBRA_TOLERANCE for error in errors.values()
        )
        checks.append(
            {
                "name": f"derived quantities match for {state_id}",
                "ok": ok,
                "detail": json.dumps(errors, sort_keys=True),
                "numbers": errors,
            }
        )
    if missing:
        checks.append(
            {
                "name": "every declared state was answered",
                "ok": False,
                "detail": f"missing states: {missing}",
                "numbers": {"missing": len(missing), "declared": len(truth)},
            }
        )
    else:
        checks.append(
            {
                "name": "every declared state was answered",
                "ok": True,
                "detail": f"{len(truth)} of {len(truth)} declared states answered",
                "numbers": {"answered": len(truth)},
            }
        )

    trap = evidence.get("coherence_trap")
    trap_truth = truth["large-amplitude-uniform"]
    trap_ok = (
        isinstance(trap, Mapping)
        and str(trap.get("state_id")) == "large-amplitude-uniform"
        and str(trap.get("claim")) == "zero_net_power"
        and _relative_error(trap_truth["node_power_y"], trap.get("node_power_y")) is not None
        and _relative_error(trap_truth["node_power_y"], trap.get("node_power_y")) <= ALGEBRA_TOLERANCE
        and _relative_error(trap_truth["node_power_i"], trap.get("node_power_i")) is not None
        and _relative_error(trap_truth["node_power_i"], trap.get("node_power_i")) <= ALGEBRA_TOLERANCE
    )
    checks.append(
        {
            "name": "large amplitudes are not reported as transport",
            "ok": trap_ok,
            "detail": (
                "a uniform conversion mode carries no net node power even while "
                "the rates are maximal"
            ),
            "numbers": {
                "truth_node_power_y": trap_truth["node_power_y"],
                "claimed_node_power_y": (trap or {}).get("node_power_y") if isinstance(trap, Mapping) else None,
            },
        }
    )

    trap_state = _state_from_document(fixture.representation_states[-1])
    trap_rates = engine.rates(trap_state)
    trap_rate_max = max(
        float(abs(trap_rates[0]).max()),
        float(abs(trap_rates[1]).max()),
    )
    controls = [
        {
            "name": "a live uniform-rate state exists to be misread",
            "ok": abs(trap_truth["node_power_y"]) <= ALGEBRA_ABSOLUTE
            and abs(trap_truth["node_power_i"]) <= ALGEBRA_ABSOLUTE
            and trap_rate_max > 0.1,
            "detail": (
                f"max field rate {trap_rate_max:.6f} while both net node powers "
                "are zero; the zero is transport cancellation, not a dead state"
            ),
        }
    ]

    verdict = "fail" if not all(item["ok"] for item in checks) else "pass"
    return _report(
        "representation", verdict, checks, controls,
        {"worst_relative_errors": worst}, ["tolerance is algebraic: 1e-6 relative"],
    )


# --------------------------------------------------------------------------
# station 3 -- executable explanation


def explanation_holdout_cases() -> tuple[dict[str, Any], ...]:
    return (
        {"amplitude": 0.7, "width": 3.0, "center": 20.0, "speed": 0.5, "steps": 500},
        {"amplitude": 1.1, "width": 1.8, "center": 7.0, "speed": 0.8, "steps": 800},
        {"amplitude": 0.5, "width": 4.0, "center": 18.0, "speed": 0.3, "steps": 1100},
    )


def brief_explanation(fixture: Fixture) -> dict[str, Any]:
    return {
        "station": "explanation",
        "title": "An explanation that can be run",
        "world": {
            "complex": fixture.complex_document(),
            "constants": fixture.model_document(),
            "dt": fixture.dt,
            "probe_node": fixture.probe,
        },
        "initial_state_construction": {
            "family": "counterflow_packet",
            "psi_y": "amplitude * exp(-((x - center)^2) / (2 * width^2)) * cos(k * (x - center))",
            "psi_i": "psi_y / phi",
            "k": "speed / c_F  with  c_F = sqrt(c_f2)",
            "rates": "each channel carries its packet at its own declared rate so that eps starts and stays at zero",
            "momenta": "P_Y = mu * M * psi_dot_Y, P_I = mu * phi * M * psi_dot_I",
        },
        "program_contract": {
            "input": "one JSON object on stdin with keys node_count, dt, steps, c_f2, omega2, mu, phi, amplitude, width, center, speed, probe",
            "output": "one JSON object on stdout with keys centroid_y, centroid_i, epsilon_period",
            "definitions": {
                "centroid": "sum(i * |psi_i|) / sum(|psi_i|) over all nodes after the declared steps",
                "epsilon_period": "the period of the uniform conversion mode eps = psi_y - phi*psi_i of this world",
            },
            "runtime": "python 3.12, standard library plus numpy, no network, bounded to 30 seconds",
        },
        "question": (
            "Submit the source of a program that answers the contract for any "
            "declared input. It will be run on parameter values you have not "
            "seen, and its printed numbers are compared with an independent "
            "integration of the same declared equations."
        ),
        "holdout_notice": "three held-out parameter sets; the tolerance is 1e-3 relative",
        "evidence_schema": EVIDENCE_EXPLANATION,
    }


def judge_explanation(
    fixture: Fixture,
    evidence: Mapping[str, Any],
    *,
    runner: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from laboratory.course import run_submitted_program

    execute = runner or run_submitted_program
    source = evidence.get("program_source")
    if not isinstance(source, str) or not source.strip():
        raise LaboratoryError("program_source must be non-empty text")

    checks: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    cases = explanation_holdout_cases()
    observed: list[dict[str, Any]] = []
    native = fixture.engine(fixture.native)
    counterfactual = fixture.engine(fixture.counterfactual)

    for case in cases:
        inputs = {
            "node_count": fixture.node_count,
            "dt": fixture.dt,
            "steps": case["steps"],
            "c_f2": fixture.model.c_f2,
            "omega2": fixture.model.omega2,
            "mu": fixture.model.mu,
            "phi": fixture.model.phi,
            "amplitude": case["amplitude"],
            "width": case["width"],
            "center": case["center"],
            "speed": case["speed"],
            "probe": fixture.probe,
        }
        truth_native = _explanation_truth(native, inputs)
        truth_counterfactual = _explanation_truth(counterfactual, inputs)
        stdout, failed = execute(source, inputs)
        if failed:
            checks.append(
                {
                    "name": f"program ran for case {case}",
                    "ok": False,
                    "detail": failed,
                    "numbers": {},
                }
            )
            continue
        try:
            produced = json.loads(stdout)
        except json.JSONDecodeError as error:
            checks.append(
                {
                    "name": f"program printed JSON for case {case}",
                    "ok": False,
                    "detail": f"{error}: {stdout[:200]!r}",
                    "numbers": {},
                }
            )
            continue
        errors = {
            key: _relative_error(truth_native[key], produced.get(key))
            for key in truth_native
        }
        checks.append(
            {
                "name": f"held-out predictions match for case {case}",
                "ok": all(
                    error is not None and error <= EXPLANATION_TOLERANCE
                    for error in errors.values()
                ),
                "detail": json.dumps(
                    {
                        "claimed": produced,
                        "independent": truth_native,
                        "relative_errors": errors,
                    },
                    sort_keys=True,
                ),
                "numbers": errors,
            }
        )
        observed.append(
            {
                "case": case,
                "claimed": produced,
                "independent": truth_native,
                "counterfactual": truth_counterfactual,
            }
        )

    discriminating = any(
        _separation(item["independent"][key], item["counterfactual"][key]) is not None
        and _separation(item["independent"][key], item["counterfactual"][key]) >= EXPLANATION_HOLDOUT_MARGIN
        for item in observed
        for key in item["independent"]
    )
    controls.append(
        {
            "name": "the held-out cases can separate the two mechanisms",
            "ok": discriminating,
            "detail": (
                "at least one required quantity differs by more than the margin "
                "between the native and counterfactual worlds"
            ),
        }
    )
    if observed:
        period_separation = max(
            _separation(item["independent"]["epsilon_period"], item["counterfactual"]["epsilon_period"]) or 0.0
            for item in observed
        )
        controls.append(
            {
                "name": "the conversion period is the separating quantity",
                "ok": period_separation >= EXPLANATION_HOLDOUT_MARGIN,
                "detail": f"period separation across cases: {period_separation:.6f}",
            }
        )

    verdict = "fail" if not all(item["ok"] for item in checks) else "pass"
    return _report(
        "explanation", verdict, checks, controls,
        {"cases": len(cases), "observed": observed},
        ["the judge runs the submitted source itself on parameters the agent never saw"],
    )


def _explanation_truth(engine: NativeFieldOracle, inputs: Mapping[str, Any]) -> dict[str, float]:
    state = oracle_module.counterflow_packet(
        engine.complex,
        engine.model,
        amplitude=float(inputs["amplitude"]),
        width=float(inputs["width"]),
        center=float(inputs["center"]),
        speed=float(inputs["speed"]),
    )
    final = engine.advance(state, int(inputs["steps"]))
    uniform = oracle_module.epsilon_mode(
        engine.complex, engine.model, amplitude=float(inputs["amplitude"]), width=None,
    )
    series = _epsilon_series(engine, uniform, 1500, 0)
    period = _period_from_zero_crossings(series, engine.dt)
    if period is None:
        period = 2.0 * math.pi / math.sqrt(
            (1.0 + engine.model.phi) * engine.model.omega2
        )
    return {
        "centroid_y": _centroid(final.psi_y),
        "centroid_i": _centroid(final.psi_i),
        "epsilon_period": float(period),
    }


# --------------------------------------------------------------------------
# station 4 -- inverse design


def _inverse_family(node_count: int) -> tuple[tuple[int, float], ...]:
    amplitudes = (0.05, 0.1, 0.2, 0.4, 0.8)
    return tuple(
        (node, amplitude) for amplitude in amplitudes for node in range(node_count)
    )


def _inverse_member_state(fixture: Fixture, node: int, amplitude: float) -> State:
    import numpy as np

    psi_y = np.zeros(fixture.node_count)
    psi_i = np.zeros(fixture.node_count)
    psi_y[node] = amplitude
    psi_i[node] = -amplitude / fixture.model.phi
    return State(psi_y, psi_i, np.zeros(fixture.node_count), np.zeros(fixture.node_count))


def _inverse_selection(fixture: Fixture, evidence: Mapping[str, Any], key: str) -> State:
    selection = evidence.get(key)
    if not isinstance(selection, Mapping):
        raise LaboratoryError(f"{key} must be an object with node, amplitude and channel weights")
    node = int(selection["node"])
    if not 0 <= node < fixture.node_count:
        raise LaboratoryError(f"{key} node out of range")
    amplitude = float(selection["amplitude"])
    yin_weight = float(selection.get("yin_weight", -1.0 / fixture.model.phi))
    import numpy as np

    psi_y = np.zeros(fixture.node_count)
    psi_i = np.zeros(fixture.node_count)
    psi_y[node] = amplitude
    psi_i[node] = yin_weight * amplitude
    return State(psi_y, psi_i, np.zeros(fixture.node_count), np.zeros(fixture.node_count))


def _inverse_score(engine: NativeFieldOracle, fixture: Fixture, state: State) -> float:
    final = engine.advance(state, fixture.steps_intervention)
    return float(abs(engine.epsilon(final)[fixture.probe]))


def _inverse_budget(engine: NativeFieldOracle, state: State) -> float:
    return float(engine.hamiltonian(state))


def _inverse_cases(fixture: Fixture) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    engine = fixture.engine(fixture.native)
    achieved: dict[tuple[int, float], float] = {}
    energies: dict[tuple[int, float], float] = {}
    for node, amplitude in _inverse_family(fixture.node_count):
        state = _inverse_member_state(fixture, node, amplitude)
        achieved[(node, amplitude)] = _inverse_score(engine, fixture, state)
        energies[(node, amplitude)] = _inverse_budget(engine, state)

    family_max = max(achieved.values())
    best_key = max(achieved, key=lambda key: achieved[key])
    energy_budget = 5.0
    amplitude_ceiling = math.sqrt(energy_budget / 3.118)
    outside_amplitude = 1.2
    outside = _inverse_member_state(fixture, fixture.probe, outside_amplitude)
    outside_score = _inverse_score(engine, fixture, outside)
    outside_energy = _inverse_budget(engine, outside)
    if outside_energy > energy_budget:
        raise LaboratoryError(
            f"outside witness energy {outside_energy} exceeds the declared budget {energy_budget}"
        )
    if outside_score <= family_max * 1.02:
        raise LaboratoryError(
            f"outside witness {outside_score} does not clear the family maximum {family_max}"
        )
    analytic_ceiling = 2.0 * amplitude_ceiling

    early_keys = tuple(_inverse_family(fixture.node_count)[:INVERSE_BUDGET])
    early_max = max(achieved[key] for key in early_keys)

    budget_target = family_max * 0.95
    if not early_max < budget_target <= family_max:
        raise LaboratoryError(
            f"case C is not budget-limited: early {early_max} family {family_max} target {budget_target}"
        )
    case_b_target = max(analytic_ceiling, outside_score) * 1.1
    case_d_target = outside_score * 0.95
    if not family_max < case_d_target <= outside_score:
        raise LaboratoryError(
            f"case D is not family-limited: family {family_max} outside {outside_score} target {case_d_target}"
        )

    cases = (
        {
            "case_id": "A",
            "target_epsilon": round(family_max * 0.6, 6),
            "energy_budget": energy_budget,
            "expected_claim": "feasible",
            "note": "reachable inside the declared family",
        },
        {
            "case_id": "B",
            "target_epsilon": round(case_b_target, 6),
            "energy_budget": energy_budget,
            "expected_claim": "infeasible-in-family",
            "note": "above the energy budget allows for any state at the probe node",
        },
        {
            "case_id": "C",
            "target_epsilon": round(budget_target, 6),
            "energy_budget": energy_budget,
            "evaluation_budget": INVERSE_BUDGET,
            "expected_claim": "exhausted",
            "note": "reachable, but only by members outside the declared evaluation budget",
        },
        {
            "case_id": "D",
            "target_epsilon": round(case_d_target, 6),
            "energy_budget": energy_budget,
            "expected_claim": "family-limited",
            "note": "above the family maximum, reachable by a legal state outside it",
        },
    )
    search = {
        "family_max": family_max,
        "best_member": {"node": best_key[0], "amplitude": best_key[1]},
        "early_max": early_max,
        "outside_score": outside_score,
        "outside_amplitude": outside_amplitude,
        "outside_energy": outside_energy,
        "analytic_ceiling": analytic_ceiling,
        "amplitude_ceiling": amplitude_ceiling,
        "members": len(achieved),
        "energy_budget": energy_budget,
    }
    return cases, search


def brief_cases(fixture: Fixture) -> list[dict[str, Any]]:
    """The case list as the agent sees it: no expected claim, no note."""

    return [
        {
            "case_id": case["case_id"],
            "target_epsilon": case["target_epsilon"],
            "energy_budget": case["energy_budget"],
            **(
                {"evaluation_budget": case["evaluation_budget"]}
                if "evaluation_budget" in case
                else {}
            ),
        }
        for case in fixture.inverse_cases
    ]


def brief_inverse_design(fixture: Fixture) -> dict[str, Any]:
    return {
        "station": "inverse-design",
        "title": "Designing backwards under a budget",
        "world": {
            "complex": fixture.complex_document(),
            "constants": fixture.model_document(),
            "dt": fixture.dt,
            "probe_node": fixture.probe,
        },
        "family": {
            "description": (
                "a state at rest built from one node: psi_y[node] = amplitude, "
                "psi_i[node] = -amplitude/phi, all momenta zero"
            ),
            "nodes": list(range(fixture.node_count)),
            "amplitudes": [0.05, 0.1, 0.2, 0.4, 0.8],
            "energy": "the initial Hamiltonian of the prepared state",
        },
        "objective": {
            "statistic": "abs(eps) at the probe node",
            "evaluation_steps": fixture.steps_intervention,
        },
        "claims": {
            "feasible": "a family member reaches the target; a witness is required",
            "infeasible-in-family": "no family member reaches it and the agent's own bounded extension search found none",
            "exhausted": "the declared evaluation budget was used before either could be established",
            "family-limited": "no family member reaches it, but a legal state outside the family does; that witness is required",
        },
        "cases": brief_cases(fixture),
        "question": (
            "For each case, state which claim is supported and supply the witness "
            "where the claim requires one. A claim of impossibility that the "
            "world contradicts is a failed case, and so is a claim of success "
            "without a witness that actually reaches the target inside the "
            "energy budget."
        ),
        "evidence_schema": EVIDENCE_INVERSE_DESIGN,
    }


def judge_inverse_design(fixture: Fixture, evidence: Mapping[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    engine = fixture.engine(fixture.native)
    submissions = evidence.get("cases")
    if not isinstance(submissions, list):
        raise LaboratoryError("cases must be a list")
    by_id = {str(item.get("case_id")): item for item in submissions if isinstance(item, Mapping)}

    for case in fixture.inverse_cases:
        case_id = case["case_id"]
        submission = by_id.get(case_id)
        if submission is None:
            checks.append(
                {
                    "name": f"case {case_id} answered",
                    "ok": False,
                    "detail": "no submission for this case",
                    "numbers": {},
                }
            )
            continue
        claim = str(submission.get("claim", "")).strip()
        target = float(case["target_epsilon"])
        budget = float(case["energy_budget"])
        detail: dict[str, Any] = {"claim": claim, "target": target, "expected": case["expected_claim"]}
        ok = claim == case["expected_claim"]

        witness = submission.get("witness")
        if claim == "feasible":
            if not isinstance(witness, Mapping):
                ok = False
                detail["witness"] = "missing"
            else:
                try:
                    state = _inverse_selection(fixture, submission, "witness")
                except (KeyError, TypeError, ValueError, LaboratoryError) as error:
                    ok = False
                    detail["witness_error"] = str(error)
                else:
                    score = _inverse_score(engine, fixture, state)
                    energy = _inverse_budget(engine, state)
                    detail["witness_score"] = score
                    detail["witness_energy"] = energy
                    ok = ok and score >= target and energy <= budget
        elif claim == "family-limited":
            if not isinstance(witness, Mapping):
                ok = False
                detail["witness"] = "missing"
            else:
                try:
                    state = _inverse_selection(fixture, submission, "witness")
                except (KeyError, TypeError, ValueError, LaboratoryError) as error:
                    ok = False
                    detail["witness_error"] = str(error)
                else:
                    score = _inverse_score(engine, fixture, state)
                    energy = _inverse_budget(engine, state)
                    in_family = (
                        abs(float(submission["witness"].get("yin_weight", -1.0 / fixture.model.phi))
                            + 1.0 / fixture.model.phi) <= 1e-12
                        and float(submission["witness"]["amplitude"]) in {0.05, 0.1, 0.2, 0.4, 0.8}
                    )
                    detail["witness_score"] = score
                    detail["witness_energy"] = energy
                    detail["witness_in_family"] = in_family
                    ok = ok and score >= target and energy <= budget and not in_family

        checks.append(
            {
                "name": f"case {case_id} claim is supported",
                "ok": ok,
                "detail": json.dumps(detail, sort_keys=True),
                "numbers": {key: value for key, value in detail.items() if isinstance(value, (int, float))},
            }
        )

    search = fixture.inverse_search
    controls.append(
        {
            "name": "the family was actually searched",
            "ok": search["members"] > 0 and search["family_max"] > 0.0,
            "detail": json.dumps(search, sort_keys=True),
        }
    )
    controls.append(
        {
            "name": "the budget-limited case is reachable outside the evaluation budget",
            "ok": search["early_max"] < float(
                next(case["target_epsilon"] for case in fixture.inverse_cases if case["case_id"] == "C")
            )
            <= search["family_max"],
            "detail": (
                f"best inside the first {INVERSE_BUDGET} members {search['early_max']:.6f} "
                f"versus family maximum {search['family_max']:.6f}"
            ),
        }
    )
    controls.append(
        {
            "name": "case B sits above the energy-budget ceiling, so infeasibility is provable",
            "ok": float(
                next(case["target_epsilon"] for case in fixture.inverse_cases if case["case_id"] == "B")
            )
            > search["analytic_ceiling"],
            "detail": (
                f"target {next(case['target_epsilon'] for case in fixture.inverse_cases if case['case_id'] == 'B'):.6f} "
                f"versus ceiling {search['analytic_ceiling']:.6f} "
                f"(amplitude ceiling {search['amplitude_ceiling']:.6f} inside a budget of "
                f"{search['energy_budget']} for a one-node state)"
            ),
        }
    )
    controls.append(
        {
            "name": "case D exceeds the family maximum but not the budget",
            "ok": search["outside_energy"] <= search["energy_budget"]
            and float(
                next(case["target_epsilon"] for case in fixture.inverse_cases if case["case_id"] == "D")
            )
            > search["family_max"],
            "detail": json.dumps(
                {
                    "outside_amplitude": search["outside_amplitude"],
                    "outside_energy": search["outside_energy"],
                    "outside_score": search["outside_score"],
                    "family_max": search["family_max"],
                },
                sort_keys=True,
            ),
        }
    )

    verdict = "fail" if not all(item["ok"] for item in checks) else "pass"
    return _report(
        "inverse-design", verdict, checks, controls,
        {"search": search}, ["each claim is re-derived by the judge's own bounded search"],
    )


# --------------------------------------------------------------------------
# station 5 -- the workshop (source correction)


def _workshop_material(fixture: Fixture) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    engine = fixture.engine(fixture.native)
    packet = oracle_module.counterflow_packet(
        fixture.complex,
        fixture.model,
        amplitude=fixture.observed_packet["amplitude"],
        width=fixture.observed_packet["width"],
        center=fixture.observed_packet["center"],
        speed=fixture.observed_packet["speed"],
    )
    excited = oracle_module.epsilon_mode(
        fixture.complex, fixture.model, amplitude=0.3, width=None,
    )
    import numpy as np

    state = State(
        packet.psi_y + excited.psi_y,
        packet.psi_i + excited.psi_i,
        packet.p_y,
        packet.p_i,
    )
    partition = engine.partition(state)
    document = {
        "state_id": "workshop-state",
        "psi_y": [round(float(value), 6) for value in state.psi_y],
        "psi_i": [round(float(value), 6) for value in state.psi_i],
        "p_y": [round(float(value), 6) for value in state.p_y],
        "p_i": [round(float(value), 6) for value in state.p_i],
    }
    truth = {
        "hamiltonian": float(engine.hamiltonian(state)),
        "kinetic_total": float(partition["kinetic"]),
        "gradient_total": float(partition["gradient"]),
        "conversion_total": float(partition["conversion"]),
        "node_power_y": float(engine.node_power(state, "Y")[fixture.probe]),
        "node_power_i": float(engine.node_power(state, "I")[fixture.probe]),
        "epsilon_max_abs": float(abs(engine.epsilon(state)).max()),
    }
    reports = (
        {
            "report_id": "R1",
            "author": "kinematics",
            "method": "packet centroid tracking on both channels",
            "numbers": {"centroid_y": round(_centroid(state.psi_y), 6), "centroid_i": round(_centroid(state.psi_i), 6)},
            "claim": "the two packets travel in opposite directions",
        },
        {
            "report_id": "R2",
            "author": "energetics",
            "method": "total energy in a different normalisation: energy per node instead of per volume",
            "numbers": {
                "energy_per_node": round(truth["hamiltonian"] / fixture.node_count, 6),
                "kinetic_per_node": round(truth["kinetic_total"] / fixture.node_count, 6),
            },
            "claim": "the state is dominated by gradient energy",
        },
        {
            "report_id": "R3",
            "author": "transport",
            "method": "read the amplitudes and treat large coherent motion as transport",
            "numbers": {
                "node_power_y": round(truth["node_power_y"] * 40.0, 6),
                "node_power_i": round(truth["node_power_i"] * 40.0, 6),
                "epsilon_max_abs": round(truth["epsilon_max_abs"], 6),
            },
            "claim": "a large amplitude implies large net transport at the probe node",
        },
    )
    return reports, document


def brief_workshop(fixture: Fixture) -> dict[str, Any]:
    return {
        "station": "workshop",
        "title": "Three colleagues, one of them wrong",
        "world": {
            "complex": fixture.complex_document(),
            "constants": fixture.model_document(),
            "probe_node": fixture.probe,
        },
        "state": dict(fixture.workshop_state),
        "reports": [dict(report) for report in fixture.workshop_reports],
        "question": (
            "Reconcile the three reports into the declared quantities for this "
            "state, correct whichever report is wrong (name it and give the "
            "corrected quantity), and state the corrected value rather than an "
            "average of the reports."
        ),
        "evidence_schema": EVIDENCE_WORKSHOP,
    }


def judge_workshop(fixture: Fixture, evidence: Mapping[str, Any]) -> dict[str, Any]:
    engine = fixture.engine(fixture.native)
    state = _state_from_document(fixture.workshop_state)
    partition = engine.partition(state)
    truth = {
        "hamiltonian": float(engine.hamiltonian(state)),
        "kinetic_total": float(partition["kinetic"]),
        "gradient_total": float(partition["gradient"]),
        "conversion_total": float(partition["conversion"]),
        "node_power_y": float(engine.node_power(state, "Y")[fixture.probe]),
        "node_power_i": float(engine.node_power(state, "I")[fixture.probe]),
        "epsilon_max_abs": float(abs(engine.epsilon(state)).max()),
    }
    values = evidence.get("values")
    checks: list[dict[str, Any]] = []
    errors: dict[str, Any] = {}
    if not isinstance(values, Mapping):
        raise LaboratoryError("values must be an object")
    for key, expected in truth.items():
        error = _relative_error(expected, values.get(key))
        errors[key] = error
        checks.append(
            {
                "name": f"reconciled {key}",
                "ok": error is not None and error <= WORKSHOP_TOLERANCE,
                "detail": f"independent {expected!r} claimed {values.get(key)!r}",
                "numbers": {"relative_error": error},
            }
        )
    wrong = str(evidence.get("wrong_report_id", "")).strip()
    checks.append(
        {
            "name": "the wrong report is identified",
            "ok": wrong == "R3",
            "detail": "R3 reads large amplitude as transport; the probe node carries no net power",
            "numbers": {"report_count": len(fixture.workshop_reports), "compared": 3},
        }
    )
    corrected = evidence.get("corrected")
    corrected_ok = isinstance(corrected, Mapping) and all(
        _relative_error(truth[key], corrected.get(key)) is not None
        and _relative_error(truth[key], corrected.get(key)) <= WORKSHOP_TOLERANCE
        for key in ("node_power_y", "node_power_i")
    )
    checks.append(
        {
            "name": "the corrected transport values match",
            "ok": corrected_ok,
            "detail": json.dumps({"claimed": corrected, "independent": {"node_power_y": truth["node_power_y"], "node_power_i": truth["node_power_i"]}}, sort_keys=True),
            "numbers": {},
        }
    )

    average_y = (truth["node_power_y"] + truth["node_power_y"] * 40.0) / 2.0
    controls = [
        {
            "name": "averaging the wrong report fails the check",
            "ok": _relative_error(truth["node_power_y"], average_y) > WORKSHOP_TOLERANCE,
            "detail": "an average of the reports cannot satisfy the tolerance",
        },
        {
            "name": "the unit difference is real",
            "ok": abs(truth["hamiltonian"] / fixture.node_count - truth["hamiltonian"]) > 1e-6,
            "detail": "R2 reports per-node values, so its numbers must be rescaled with the volumes",
        },
    ]

    verdict = "fail" if not all(item["ok"] for item in checks) else "pass"
    return _report(
        "workshop", verdict, checks, controls,
        {"relative_errors": errors}, ["the wrong report is wrong in a physical way, not a typo"],
    )


# --------------------------------------------------------------------------
# station registry


@dataclass(frozen=True, slots=True)
class Station:
    """One judged piece of work.

    ``judge`` takes the course context (it carries the fixture, the entity
    client and the program when there is one) and the submitted evidence, and
    returns a station report.
    """

    station_id: str
    title: str
    evidence_schema: str
    brief: dict[str, Any]
    judge: Callable[[Any, Mapping[str, Any]], dict[str, Any]]
    kind: str = "physics"

    def public(self) -> dict[str, Any]:
        return {
            "station_id": self.station_id,
            "title": self.title,
            "evidence_schema": self.evidence_schema,
            "kind": self.kind,
            "brief": self.brief,
        }


def _physics_judge(
    judge: Callable[[Fixture, Mapping[str, Any]], dict[str, Any]]
) -> Callable[[Any, Mapping[str, Any]], dict[str, Any]]:
    def bound(context: Any, evidence: Mapping[str, Any]) -> dict[str, Any]:
        return judge(context.fixture, evidence)

    return bound


def physics_stations(fixture: Fixture | None = None) -> tuple[Station, ...]:
    declared = fixture or default_fixture()
    return (
        Station(
            "discrimination",
            "One instrument that cannot yet tell a difference",
            EVIDENCE_DISCRIMINATION,
            brief_discrimination(declared),
            _physics_judge(judge_discrimination),
        ),
        Station(
            "representation",
            "The quantities the instrument never reports",
            EVIDENCE_REPRESENTATION,
            brief_representation(declared),
            _physics_judge(judge_representation),
        ),
        Station(
            "explanation",
            "An explanation that can be run",
            EVIDENCE_EXPLANATION,
            brief_explanation(declared),
            _physics_judge(judge_explanation),
        ),
        Station(
            "inverse-design",
            "Designing backwards under a budget",
            EVIDENCE_INVERSE_DESIGN,
            brief_inverse_design(declared),
            _physics_judge(judge_inverse_design),
        ),
        Station(
            "workshop",
            "Three colleagues, one of them wrong",
            EVIDENCE_WORKSHOP,
            brief_workshop(declared),
            _physics_judge(judge_workshop),
        ),
    )


def mission_document(
    fixture: Fixture,
    stations: Sequence[Station],
    *,
    mission_id: str | None = None,
    level: str = "counterflow",
    world: Mapping[str, Any] | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """One brief, one deliverable, one world identity.

    ``world`` overrides the Level-1 world block; Level-2 worlds declare a
    candidate menu instead of a single set of constants, so they pass their own
    block and keep the rest of the mission document unchanged.
    """

    declared_world = (
        dict(world)
        if isinstance(world, Mapping)
        else {
            "complex": fixture.complex_document(),
            "constants": fixture.model_document(),
            "dt": fixture.dt,
            "probe_node": fixture.probe,
        }
    )
    return {
        "schema": MISSION_SCHEMA,
        "mission_id": mission_id or f"{level}:{fixture.variant}",
        "level": level,
        "title": title or f"The Shifting Laboratory — {fixture.variant}",
        "fixture_id": fixture.fixture_id(),
        "world": declared_world,
        "deliverable": {
            "schema": MISSION_EVIDENCE_SCHEMA,
            "artifact": "answer.json",
            "format": (
                "one JSON object fenced as ```json, with the keys schema, "
                "fixture_id and stations; stations maps each station id below to "
                "its own evidence document"
            ),
            "required_keys": ["schema", "fixture_id", "stations"],
            "sections_key": "stations",
            "fixture_id": fixture.fixture_id(),
            "station_keys": {station.station_id: station.evidence_schema for station in stations},
            "rule": (
                "forecasts are declared before any intervention is run; the score "
                "comes from runs you never see, and an answer to a different "
                "world is not an answer"
            ),
        },
        "stations": [station.public() for station in stations],
    }


def counterflow_mission(fixture: Fixture | None = None) -> dict[str, Any]:
    """The Level-1 mission: every physics station, one brief, one deliverable."""

    declared = fixture or default_fixture()
    return mission_document(declared, physics_stations(declared))


def _report(
    station: str,
    verdict: str,
    checks: Sequence[Mapping[str, Any]],
    controls: Sequence[Mapping[str, Any]],
    measurements: Mapping[str, Any],
    notes: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema": STATION_REPORT_SCHEMA,
        "station": station,
        "verdict": verdict,
        "checks": [dict(item) for item in checks],
        "controls": [dict(item) for item in controls],
        "measurements": dict(measurements),
        "notes": list(notes),
    }


def extract_evidence(text: str, schema: str) -> dict[str, Any] | None:
    """Pull one fenced JSON document carrying the requested evidence schema."""

    if not isinstance(text, str):
        return None
    blocks: list[str] = []
    marker = "```json"
    cursor = 0
    while True:
        start = text.find(marker, cursor)
        if start < 0:
            break
        end = text.find("```", start + len(marker))
        if end < 0:
            break
        blocks.append(text[start + len(marker):end])
        cursor = end + 3
    for block in blocks:
        try:
            candidate = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("schema") == schema:
            return candidate
    for block in blocks:
        try:
            candidate = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    return None
