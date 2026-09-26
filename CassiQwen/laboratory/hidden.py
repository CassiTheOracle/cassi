"""Hidden worlds: the Level-2 laboratory of the Shifting course.

Level 1 fixed one world and asked what an instrument could say about it.  Level
2 hides the law.  The agent receives a menu of candidate laws, a handful of
observed runs that only one of them can produce, and a menu of writes whose
fates it must forecast.  Nothing here reveals which candidate is true: the
world identity commits to the hidden law, the briefs carry only observations,
and every judge recomputes its numbers from the declared world instead of
trusting a claim.

Two stations carry the level:

``identification``
    Which candidate law ran the observations; the measured value the declared
    instrument reports; how strongly the observations separate that law from
    the closest other candidate; and a forecast of the probe series past the
    observed window (a held-out extrapolation, not a re-read of the data).

``retention``
    How long each declared write stays recognizable under the identified law,
    measured with one declared procedure (a windowed fidelity mean), with the
    declared ``beyond-horizon`` branch for writes that outlive the horizon.

The physics is the same two-fluid field as Level 1; only the bookkeeping is
new, so a wrong attribution is visible in the numbers rather than in the prose.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from laboratory import oracle as oracle_module
from laboratory import stations as stations_module
from laboratory.oracle import CellComplex, Model, NativeFieldOracle, State
from laboratory.stations import LaboratoryError, Station

LAW_SCHEMA = "cassi.laboratory.law.v1"
HIDDEN_WORLD_SCHEMA = "cassi.laboratory.hidden-world.v1"
EVIDENCE_IDENTIFICATION = "cassi.laboratory.evidence.identification.v1"
EVIDENCE_RETENTION = "cassi.laboratory.evidence.retention.v1"
HIDDEN_CANARY_SCHEMA = "cassi.laboratory.hidden-canary.v1"

PHI = stations_module.PHI

# Tolerances of the two Level-2 stations.  The measurement tolerance is far
# above any honest integration difference (the fit itself is exact to 1e-6 on a
# single tone) and far below the separation between neighbouring laws.
MEASUREMENT_TOLERANCE = 0.02
SEPARATION_FLOOR = 0.01
SEPARATION_MATCH_TOLERANCE = 0.25
FORECAST_TOLERANCE = 0.02
FORECAST_STEPS: tuple[int, ...] = (700, 800, 900)
RETENTION_RELATIVE_TOLERANCE = 0.05
RETENTION_ABSOLUTE_TOLERANCE = 0.3
RETENTION_SPREAD_FLOOR = 1.0
MEASUREMENT_RESIDUAL_FLOOR = 0.05
FIT_SCAN_LOW = 0.10
FIT_SCAN_HIGH = 2.20
FIT_SCAN_POINTS = 421

MEASUREMENT_RECIPE_ID = "A"  # the default measured recipe; a world measures its first one

# --------------------------------------------------------------------------- #
# candidate laws
# --------------------------------------------------------------------------- #

LAW_MENU: tuple[dict[str, Any], ...] = (
    {
        "law_id": "L1-native-w25",
        "description": "the Yin channel converts with the native phi gain at omega2 = 0.25",
        "yin": "phi",
        "omega2": 0.25,
    },
    {
        "law_id": "L2-equal-w25",
        "description": "both channels convert with the same gain at omega2 = 0.25",
        "yin": "equal",
        "omega2": 0.25,
    },
    {
        "law_id": "L3-native-w49",
        "description": "the native phi gain with a stiffer conversion at omega2 = 0.49",
        "yin": "phi",
        "omega2": 0.49,
    },
    {
        "law_id": "L4-equal-w81",
        "description": "the equal gain with the stiffest conversion at omega2 = 0.81",
        "yin": "equal",
        "omega2": 0.81,
    },
)


def law_model(law: Mapping[str, Any], *, yin: str | None = None) -> Model:
    """The field model of one candidate law, optionally with a forced convention."""

    if not isinstance(law, Mapping):
        raise LaboratoryError("a law must be an object")
    try:
        omega2 = float(law["omega2"])
    except (KeyError, TypeError, ValueError) as error:
        raise LaboratoryError(f"law is missing a numeric omega2: {error}") from error
    convention = str(yin or law.get("yin", "phi"))
    return Model(c_f2=1.0, omega2=omega2, mu=1.0, phi=PHI, yin=convention)


def law_document(law: Mapping[str, Any]) -> dict[str, Any]:
    """The declared description of one candidate law, including its model."""

    return {
        "schema": LAW_SCHEMA,
        "law_id": str(law["law_id"]),
        "description": str(law.get("description", "")),
        "model": law_model(law).as_dict(),
    }


def law_menu_document(laws: Sequence[Mapping[str, Any]] = LAW_MENU) -> list[dict[str, Any]]:
    return [law_document(law) for law in laws]


def law_from_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Read back a declared law document into the internal law record."""

    if not isinstance(document, Mapping):
        raise LaboratoryError("a declared law must be an object")
    law_id = str(document.get("law_id", "")).strip()
    model = document.get("model")
    if not law_id or not isinstance(model, Mapping):
        raise LaboratoryError("a declared law needs a law_id and a model")
    return {
        "law_id": law_id,
        "description": str(document.get("description", "")),
        "yin": str(model.get("yin", "phi")),
        "omega2": float(model.get("omega2", 0.0)),
    }


def law_by_id(laws: Sequence[Mapping[str, Any]], law_id: str) -> dict[str, Any]:
    for law in laws:
        if str(law["law_id"]) == str(law_id):
            return dict(law)
    raise LaboratoryError(f"no candidate law {law_id!r}")


# --------------------------------------------------------------------------- #
# declared writes
# --------------------------------------------------------------------------- #

RECIPE_FAMILIES: dict[str, dict[str, Any]] = {
    "uniform-pair": {
        "description": "psi_Y and psi_I uniform over every node, both at rest",
        "parameters": ("psi_y", "psi_i"),
    },
    "gaussian-pair": {
        "description": "one Gaussian bump per channel, both at rest",
        "parameters": (
            "psi_y_amplitude", "psi_y_center", "psi_y_width",
            "psi_i_amplitude", "psi_i_center", "psi_i_width",
        ),
    },
    "counterflow-packet": {
        "description": "two counter-directed Gaussian packets with eps identically zero",
        "parameters": ("amplitude", "width", "center", "speed"),
    },
    "conversion-blob": {
        "description": "one Gaussian conversion excitation with psi_I = -psi_Y/phi",
        "parameters": ("amplitude", "width", "center"),
    },
}


def _number(parameters: Mapping[str, Any], key: str) -> float:
    try:
        return float(parameters[key])
    except (KeyError, TypeError, ValueError) as error:
        raise LaboratoryError(f"recipe parameter {key!r} must be a number: {error}") from error


def build_state(
    complex_: CellComplex, model: Model, family: str, parameters: Mapping[str, Any]
) -> State:
    """Build one declared write in the given law's own convention.

    Every family except the counterflow packet is prepared at rest, so its
    state does not depend on the law at all.  The counterflow packet declares
    canonical rates, and its momenta therefore follow the law's own inertia --
    which is the declared meaning of "prepared in the world's law".
    """

    if not isinstance(parameters, Mapping):
        raise LaboratoryError("recipe parameters must be an object")
    node_count = complex_.node_count
    if family == "uniform-pair":
        zeros = np.zeros(node_count, dtype=float)
        return State(
            psi_y=np.full(node_count, _number(parameters, "psi_y")),
            psi_i=np.full(node_count, _number(parameters, "psi_i")),
            p_y=zeros.copy(),
            p_i=zeros.copy(),
        )
    if family == "gaussian-pair":
        x = np.arange(node_count, dtype=float)
        zeros = np.zeros(node_count, dtype=float)

        def bump(prefix: str) -> np.ndarray:
            amplitude = _number(parameters, f"{prefix}_amplitude")
            center = _number(parameters, f"{prefix}_center")
            width = _number(parameters, f"{prefix}_width")
            if width <= 0.0:
                raise LaboratoryError(f"{prefix}_width must be positive")
            return amplitude * np.exp(-((x - center) ** 2) / (2.0 * width * width))

        return State(psi_y=bump("psi_y"), psi_i=bump("psi_i"), p_y=zeros.copy(), p_i=zeros.copy())
    if family == "counterflow-packet":
        return oracle_module.counterflow_packet(
            complex_,
            model,
            amplitude=_number(parameters, "amplitude"),
            width=_number(parameters, "width"),
            center=_number(parameters, "center"),
            speed=_number(parameters, "speed"),
        )
    if family == "conversion-blob":
        return oracle_module.epsilon_mode(
            complex_,
            model,
            amplitude=_number(parameters, "amplitude"),
            width=_number(parameters, "width"),
            center=_number(parameters, "center"),
        )
    raise LaboratoryError(f"unknown recipe family {family!r}")


def recipe_document(
    recipe_id: str, family: str, parameters: Mapping[str, Any]
) -> dict[str, Any]:
    if family not in RECIPE_FAMILIES:
        raise LaboratoryError(f"unknown recipe family {family!r}")
    declared = RECIPE_FAMILIES[family]
    missing = [key for key in declared["parameters"] if key not in parameters]
    if missing:
        raise LaboratoryError(f"recipe {recipe_id!r} is missing {missing}")
    return {
        "recipe_id": str(recipe_id),
        "family": family,
        "construction": declared["description"],
        "parameters": {key: float(parameters[key]) for key in declared["parameters"]},
    }


OBSERVATION_RECIPES: tuple[dict[str, Any], ...] = (
    {
        "recipe_id": "A",
        "family": "uniform-pair",
        "parameters": {"psi_y": 1.2, "psi_i": 0.4},
        "steps_observed": 600,
        "sample_every": 50,
        "full_field": False,
    },
    {
        "recipe_id": "B",
        "family": "gaussian-pair",
        "parameters": {
            "psi_y_amplitude": 0.9, "psi_y_center": 8.0, "psi_y_width": 1.5,
            "psi_i_amplitude": 0.25, "psi_i_center": 10.5, "psi_i_width": 2.0,
        },
        "steps_observed": 600,
        "sample_every": 100,
        "full_field": True,
    },
)

DEFAULT_RETENTION_MENU: tuple[dict[str, Any], ...] = (
    {
        "recipe_id": "R1-uniform-pair",
        "family": "uniform-pair",
        "parameters": {"psi_y": 1.0, "psi_i": 0.0},
    },
    {
        "recipe_id": "R2-wide-packet",
        "family": "gaussian-pair",
        "parameters": {
            "psi_y_amplitude": 1.0, "psi_y_center": 11.5, "psi_y_width": 3.0,
            "psi_i_amplitude": 0.0, "psi_i_center": 11.5, "psi_i_width": 3.0,
        },
    },
    {
        "recipe_id": "R3-narrow-packet",
        "family": "gaussian-pair",
        "parameters": {
            "psi_y_amplitude": 1.0, "psi_y_center": 11.5, "psi_y_width": 1.0,
            "psi_i_amplitude": 0.0, "psi_i_center": 11.5, "psi_i_width": 1.0,
        },
    },
    {
        "recipe_id": "R4-counterflow",
        "family": "counterflow-packet",
        "parameters": {"amplitude": 0.8, "width": 2.5, "center": 11.5, "speed": 0.4},
    },
)

DEFAULT_RETENTION: dict[str, Any] = {
    "window_steps": 200,
    "threshold": 0.5,
    "horizon_steps": 5000,
    "sample_every": 10,
    "quantity": "windowed mean fidelity of the whole state against the write",
}


# --------------------------------------------------------------------------- #
# the declared instrument
# --------------------------------------------------------------------------- #


def measure_omega(times: Any, values: Any) -> dict[str, Any]:
    """The declared frequency instrument: a least-squares single-tone fit.

    ``value(t) ~ C + A cos(omega t) + B sin(omega t)`` minimised over
    ``FIT_SCAN_LOW < omega < FIT_SCAN_HIGH``.  A coarse scan locates the basin
    and the refinement follows the same objective, so any implementation of the
    declared minimisation lands on the same number.
    """

    times = np.asarray(times, dtype=float)
    values = np.asarray(values, dtype=float)
    if times.size < 3 or times.size != values.size:
        raise LaboratoryError("the frequency fit needs at least three paired samples")
    best_omega, best_cost = None, math.inf
    for omega in np.linspace(FIT_SCAN_LOW, FIT_SCAN_HIGH, FIT_SCAN_POINTS):
        basis = np.stack([np.cos(omega * times), np.sin(omega * times), np.ones_like(times)], axis=1)
        coefficients, *_ = np.linalg.lstsq(basis, values, rcond=None)
        residual = values - basis @ coefficients
        cost = float(residual @ residual)
        if cost < best_cost:
            best_cost, best_omega = cost, float(omega)
    step = (FIT_SCAN_HIGH - FIT_SCAN_LOW) / (FIT_SCAN_POINTS - 1)
    refined = oracle_module._fit_frequency(times, values, float(best_omega), span=4.0 * step, rounds=4)
    refined["scan_omega"] = float(best_omega)
    return refined


# --------------------------------------------------------------------------- #
# the hidden world
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class HiddenWorld:
    """One world with a law the agent must recover from observations."""

    complex: CellComplex
    dt: float
    probe: int
    laws: tuple[Mapping[str, Any], ...]
    true_law_id: str
    observations: tuple[Mapping[str, Any], ...]
    forecast_steps: tuple[int, ...]
    retention_menu: tuple[Mapping[str, Any], ...]
    retention: Mapping[str, Any]
    variant: str = "hidden-1"

    # ---------------------------------------------------------------- identity
    @property
    def true_law(self) -> dict[str, Any]:
        return law_by_id(self.laws, self.true_law_id)

    def law(self, law_id: str) -> dict[str, Any]:
        return law_by_id(self.laws, law_id)

    def engine(self, model: Model) -> NativeFieldOracle:
        return NativeFieldOracle(self.complex, model, self.dt)

    def declared_world(self) -> dict[str, Any]:
        """Everything the agent is told about the world, and nothing more."""

        return {
            "schema": HIDDEN_WORLD_SCHEMA,
            "variant": self.variant,
            "complex": self.complex.as_dict(),
            "dt": self.dt,
            "probe_node": self.probe,
            "candidate_laws": law_menu_document(self.laws),
        }

    def title(self) -> str:
        return f"The Shifting Laboratory — {self.variant}"

    # ------------------------------------------------------------ observations
    def observation_samples(self, law: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        """The shipped runs: each recipe advanced under ``law`` (default: the truth)."""

        declared = dict(law or self.true_law)
        model = law_model(declared)
        engine = self.engine(model)
        rows: list[dict[str, Any]] = []
        for recipe in self.observations:
            state = build_state(self.complex, model, recipe["family"], recipe["parameters"])
            samples: list[dict[str, Any]] = []
            time = 0.0
            for index in range(int(recipe["steps_observed"]) + 1):
                if index % int(recipe["sample_every"]) == 0:
                    row: dict[str, Any] = {
                        "step": index,
                        "time": round(time, 6),
                        "probe_psi_y": round(float(state.psi_y[self.probe]), 6),
                        "probe_psi_i": round(float(state.psi_i[self.probe]), 6),
                    }
                    if recipe.get("full_field"):
                        row["psi_y"] = [round(float(value), 6) for value in state.psi_y]
                        row["psi_i"] = [round(float(value), 6) for value in state.psi_i]
                    samples.append(row)
                state = engine.step(state)
                time += self.dt
            rows.append({**recipe_document(recipe["recipe_id"], recipe["family"], recipe["parameters"]), "samples": samples})
        return rows

    @property
    def measurement_recipe_id(self) -> str:
        """The recipe the declared instrument reads: the world's first observation."""

        return str(self.observations[0]["recipe_id"])

    def observation_series(self, recipe_id: str | None = None) -> tuple[np.ndarray, np.ndarray]:
        """The probe series of one shipped recipe, as the agent sees it."""

        wanted = str(recipe_id or self.measurement_recipe_id)
        rows = self.observation_samples()
        recipe = next(
            (item for item in rows if item["recipe_id"] == wanted),
            None,
        )
        if recipe is None:
            raise LaboratoryError(f"no observation recipe {wanted!r}")
        if not all("probe_psi_y" in row for row in recipe["samples"]):
            raise LaboratoryError(f"recipe {wanted!r} is not sampled at the probe node")
        times = np.array([float(row["time"]) for row in recipe["samples"]], dtype=float)
        values = np.array([float(row["probe_psi_y"]) for row in recipe["samples"]], dtype=float)
        return times, values

    def measurement(self) -> dict[str, Any]:
        return {
            "quantity": "probe_omega",
            "units": "radians per time unit",
            "recipe_id": self.measurement_recipe_id,
            "definition": (
                "the angular frequency omega minimising the least-squares residual of "
                "v(t) ~ C + A cos(omega t) + B sin(omega t) over the shipped sample times of "
                f"recipe {self.measurement_recipe_id} (its probe_psi_y column), searched over "
                f"{FIT_SCAN_LOW} < omega < {FIT_SCAN_HIGH}"
            ),
        }

    def forecast(self) -> dict[str, Any]:
        return {
            "recipe_id": self.measurement_recipe_id,
            "node": self.probe,
            "steps": [int(step) for step in self.forecast_steps],
            "quantity": "psi_y",
            "tolerance_absolute": FORECAST_TOLERANCE * self.forecast_scale(),
            "definition": (
                "continue the declared recipe from the shipped preparation, past the observed "
                "window, and report psi_y at the declared node and steps"
            ),
        }

    def forecast_scale(self) -> float:
        """The declared field scale the forecast tolerance is relative to.

        The largest ``|psi_y|`` over the shipped samples of the measured recipe:
        a scale that every declared recipe family has, whatever its shape.
        """

        rows = next(
            item
            for item in self.observation_samples()
            if item["recipe_id"] == self.measurement_recipe_id
        )
        scale = max(
            (abs(float(row["probe_psi_y"])) for row in rows["samples"]),
            default=0.0,
        )
        return max(scale, 1e-6)

    def retention_document(self) -> dict[str, Any]:
        return {
            "procedure": dict(self.retention),
            "menu": [
                recipe_document(recipe["recipe_id"], recipe["family"], recipe["parameters"])
                for recipe in self.retention_menu
            ],
            "rule": (
                "a write stays recognizable while the windowed mean fidelity of the whole state "
                "against the write is above the threshold; the lifetime is reported in time "
                "units and is the window centre at the first sampled step where the mean has "
                "fallen to the threshold or below; a write that never does within the horizon "
                "is reported as beyond-horizon, and a beyond-horizon write outlives any "
                "measured lifetime"
            ),
        }

    def world_document(self) -> dict[str, Any]:
        """The full declared world: everything the two briefs carry."""

        return {
            **self.declared_world(),
            "observations": self.observation_samples(),
            "measurement": self.measurement(),
            "forecast": self.forecast(),
            "retention": self.retention_document(),
        }

    def fixture_id(self) -> str:
        payload = {
            "variant": self.variant,
            "complex": self.complex.as_dict(),
            "dt": self.dt,
            "probe": self.probe,
            "laws": law_menu_document(self.laws),
            "true_law_id": self.true_law_id,
            "observations": [
                {
                    "recipe_id": recipe["recipe_id"],
                    "family": recipe["family"],
                    "parameters": {key: float(value) for key, value in recipe["parameters"].items()},
                    "steps_observed": int(recipe["steps_observed"]),
                    "sample_every": int(recipe["sample_every"]),
                    "full_field": bool(recipe.get("full_field")),
                }
                for recipe in self.observations
            ],
            "forecast_steps": [int(step) for step in self.forecast_steps],
            "retention_menu": [
                recipe_document(recipe["recipe_id"], recipe["family"], recipe["parameters"])
                for recipe in self.retention_menu
            ],
            "retention": {key: value for key, value in self.retention.items()},
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    # --------------------------------------------------------------- physics
    def series(
        self,
        law: Mapping[str, Any],
        recipe: Mapping[str, Any],
        *,
        steps: int,
        sample_every: int,
        probe_only: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Advance one declared write under ``law`` and sample it."""

        model = law_model(law)
        engine = self.engine(model)
        state = build_state(self.complex, model, recipe["family"], recipe["parameters"])
        times: list[float] = []
        values: list[float] = []
        time = 0.0
        for index in range(steps + 1):
            if index % sample_every == 0:
                times.append(time)
                values.append(float(state.psi_y[self.probe]))
            state = engine.step(state)
            time += self.dt
        return np.array(times, dtype=float), np.array(values, dtype=float)

    def probe_omega(
        self, law: Mapping[str, Any], recipe_id: str | None = None
    ) -> float:
        """The declared measurement of one law's own run of one recipe."""

        wanted = str(recipe_id or self.measurement_recipe_id)
        recipe = next(item for item in self.observations if item["recipe_id"] == wanted)
        times, values = self.series(
            law,
            recipe,
            steps=int(recipe["steps_observed"]),
            sample_every=int(recipe["sample_every"]),
        )
        return float(measure_omega(times, values)["omega"])

    def forecast_truth(self, law: Mapping[str, Any] | None = None) -> list[float]:
        recipe = next(
            item for item in self.observations if item["recipe_id"] == self.measurement_recipe_id
        )
        declared = dict(law or self.true_law)
        model = law_model(declared)
        engine = self.engine(model)
        state = build_state(self.complex, model, recipe["family"], recipe["parameters"])
        wanted = {int(step): None for step in self.forecast_steps}
        for index in range(max(wanted) + 1):
            if index in wanted:
                wanted[index] = float(state.psi_y[self.probe])
            state = engine.step(state)
        return [float(wanted[int(step)]) for step in self.forecast_steps]

    def retention_lifetimes(
        self, law: Mapping[str, Any] | None = None
    ) -> dict[str, float | None]:
        model = law_model(dict(law or self.true_law))
        return {
            str(recipe["recipe_id"]): retention_tau(
                self.complex, model, self.dt, recipe, self.retention
            )
            for recipe in self.retention_menu
        }

    # -------------------------------------------------------------- stations
    def stations(self) -> tuple[Station, ...]:
        return (
            Station(
                "identification",
                "Which law ran the observations",
                EVIDENCE_IDENTIFICATION,
                brief_identification(self),
                _hidden_judge(judge_identification),
                kind="hidden",
            ),
            Station(
                "retention",
                "How long a write stays recognizable",
                EVIDENCE_RETENTION,
                brief_retention(self),
                _hidden_judge(judge_retention),
                kind="hidden",
            ),
        )


# --------------------------------------------------------------------------- #
# retention procedure
# --------------------------------------------------------------------------- #


def _procedure_number(procedure: Mapping[str, Any], key: str) -> float:
    try:
        return float(procedure[key])
    except (KeyError, TypeError, ValueError) as error:
        raise LaboratoryError(f"retention procedure {key!r} must be a number: {error}") from error


def retention_tau(
    complex_: CellComplex,
    model: Model,
    dt: float,
    recipe: Mapping[str, Any],
    procedure: Mapping[str, Any],
) -> float | None:
    """The declared lifetime of one write under one law, or ``None``.

    ``None`` means the write never fell to the threshold within the horizon:
    the declared ``beyond-horizon`` branch, not a missing measurement.
    """

    window_steps = int(_procedure_number(procedure, "window_steps"))
    threshold = _procedure_number(procedure, "threshold")
    horizon = int(_procedure_number(procedure, "horizon_steps"))
    sample_every = int(_procedure_number(procedure, "sample_every"))
    if window_steps < 1 or horizon < window_steps or sample_every < 1:
        raise LaboratoryError("retention procedure is not a usable measurement")

    engine = NativeFieldOracle(complex_, model, dt)
    initial = build_state(complex_, model, recipe["family"], recipe["parameters"])
    denominator = float(initial.psi_y @ initial.psi_y + initial.psi_i @ initial.psi_i)
    if denominator <= 0.0:
        raise LaboratoryError("the write carries no amplitude to follow")

    window: list[float] = []
    state = initial
    total = 0.0
    for index in range(1, horizon + 1):
        state = engine.step(state)
        total = float(state.psi_y @ initial.psi_y + state.psi_i @ initial.psi_i) / denominator
        window.append(total)
        if len(window) > window_steps:
            window.pop(0)
        if index % sample_every == 0 and index >= window_steps:
            if sum(window) / float(window_steps) <= threshold:
                return round((index - window_steps // 2) * dt, 4)
    return None


def longest_recipe(claims: Sequence[Mapping[str, Any]]) -> str:
    """The declared rule for "stays recognizable longest"."""

    beyond = [
        str(item["recipe_id"])
        for item in claims
        if str(item.get("claim", "")) == "beyond-horizon"
    ]
    if beyond:
        return beyond[0]
    measured = [
        (float(item["tau_seconds"]), str(item["recipe_id"]))
        for item in claims
        if item.get("tau_seconds") is not None
    ]
    if not measured:
        raise LaboratoryError("no lifetime was claimed at all")
    measured.sort(key=lambda item: (-item[0], item[1]))
    return measured[0][1]


# --------------------------------------------------------------------------- #
# briefs
# --------------------------------------------------------------------------- #


def _identification_evidence_shape(world: HiddenWorld) -> dict[str, Any]:
    return {
        "schema": EVIDENCE_IDENTIFICATION,
        "law_id": "one candidate law id",
        "measured": {"quantity": "probe_omega", "recipe_id": world.measurement_recipe_id, "value": 0.0},
        "separation": {"closest_other_law": "one candidate law id", "relative": 0.0},
        "forecast": {
            "recipe_id": world.measurement_recipe_id,
            "node": world.probe,
            "steps": [int(step) for step in world.forecast_steps],
            "psi_y": [0.0 for _ in world.forecast_steps],
        },
    }


def _retention_evidence_shape(world: HiddenWorld) -> dict[str, Any]:
    return {
        "schema": EVIDENCE_RETENTION,
        "recipes": [
            {"recipe_id": recipe["recipe_id"], "claim": "measured | beyond-horizon", "tau_seconds": 0.0}
            for recipe in world.retention_menu
        ],
        "longest": "one recipe id",
    }


def brief_identification(world: HiddenWorld) -> dict[str, Any]:
    return {
        "station": "identification",
        "level": "hidden",
        "fixture_id": world.fixture_id(),
        "world": world.declared_world(),
        "observations": world.observation_samples(),
        "measurement": world.measurement(),
        "forecast": world.forecast(),
        "question": (
            "One of the candidate laws produced both observed runs. Identify it; report the "
            "measured probe_omega of the observations; quantify how strongly the observations "
            "separate your law from the closest other candidate; and forecast the declared "
            "held-out steps of the declared recipe under the law you identified. The judge "
            "recomputes all of it from the true law, so an answer that only fits the observed "
            "window fails the forecast."
        ),
        "evidence": _identification_evidence_shape(world),
    }


def brief_retention(world: HiddenWorld) -> dict[str, Any]:
    return {
        "station": "retention",
        "level": "hidden",
        "fixture_id": world.fixture_id(),
        "world": world.declared_world(),
        "observations": world.observation_samples(),
        "measurement": world.measurement(),
        "retention": world.retention_document(),
        "question": (
            "Under the law you identified, forecast the lifetime of every write in the declared "
            "menu with the declared procedure, and name the write that stays recognizable "
            "longest. A write that never falls to the threshold within the horizon is claimed "
            "as beyond-horizon. The observations are repeated here so the law can be recovered "
            "inside this station as well."
        ),
        "evidence": _retention_evidence_shape(world),
    }


# --------------------------------------------------------------------------- #
# judges
# --------------------------------------------------------------------------- #


def _hidden_judge(judge: Callable[[HiddenWorld, Mapping[str, Any]], dict[str, Any]]):
    def bound(context: Any, evidence: Mapping[str, Any]) -> dict[str, Any]:
        return judge(context.fixture, evidence)

    return bound


def _relative(truth: float, claimed: Any) -> float | None:
    try:
        value = float(claimed)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    scale = abs(float(truth))
    if scale <= 0.0:
        return None if value != 0.0 else 0.0
    return abs(value - float(truth)) / scale


def _closest_other(predicted: Mapping[str, float], measured: float, exclude: str) -> tuple[str, float]:
    others = {key: value for key, value in predicted.items() if key != exclude}
    if not others:
        raise LaboratoryError("the law menu has only one candidate")
    closest = min(others, key=lambda key: (abs(measured - others[key]) / max(abs(others[key]), 1e-30), key))
    relative = abs(measured - others[closest]) / max(abs(others[closest]), 1e-30)
    return closest, relative


def judge_identification(world: HiddenWorld, evidence: Mapping[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []

    claimed_law_id = str(evidence.get("law_id", "")).strip()
    if claimed_law_id not in {str(law["law_id"]) for law in world.laws}:
        raise LaboratoryError(f"claimed law {claimed_law_id!r} is not a candidate law")

    truth = world.true_law
    measured_recipe = world.measurement_recipe_id
    times, values = world.observation_series()
    fitted = measure_omega(times, values)
    predicted = {str(law["law_id"]): world.probe_omega(law) for law in world.laws}
    closest, separation = _closest_other(predicted, float(fitted["omega"]), claimed_law_id)

    checks.append(
        {
            "name": "the identified law is the law that ran the observations",
            "ok": claimed_law_id == str(truth["law_id"]),
            "detail": (
                "the world's law is committed in its identity and recomputed here; the answer "
                f"named {claimed_law_id!r}"
            ),
            "numbers": {"true_law_id": str(truth["law_id"]), "claimed_law_id": claimed_law_id},
        }
    )

    measured = evidence.get("measured")
    if not isinstance(measured, Mapping):
        raise LaboratoryError("measured must be an object")
    quantity = str(measured.get("quantity", "")).strip()
    recipe_id = str(measured.get("recipe_id", "")).strip()
    measured_error = _relative(float(fitted["omega"]), measured.get("value"))
    checks.append(
        {
            "name": "the measured value is the value the instrument reports",
            "ok": (
                quantity in {"probe_omega", "omega", "probe_omega_rad_per_time"}
                and recipe_id == measured_recipe
                and measured_error is not None
                and measured_error <= MEASUREMENT_TOLERANCE
            ),
            "detail": json.dumps(
                {"claimed": measured, "judge_omega": fitted["omega"], "relative_error": measured_error},
                sort_keys=True,
            ),
            "numbers": {
                "judge_omega": float(fitted["omega"]),
                "relative_error": measured_error,
                "tolerance": MEASUREMENT_TOLERANCE,
            },
        }
    )

    separation_claim = evidence.get("separation")
    if not isinstance(separation_claim, Mapping):
        raise LaboratoryError("separation must be an object")
    claimed_closest = str(separation_claim.get("closest_other_law", "")).strip()
    claimed_relative = separation_claim.get("relative")
    separation_error = _relative(separation, claimed_relative)
    checks.append(
        {
            "name": "the separation from the closest other candidate is quantified",
            "ok": (
                claimed_closest == closest
                and separation_error is not None
                and separation_error <= SEPARATION_MATCH_TOLERANCE
            ),
            "detail": (
                f"the measured value sits {separation:.4f} relative from {closest!r} on the "
                "judge's own runs of every candidate law"
            ),
            "numbers": {
                "judge_closest": closest,
                "judge_separation": separation,
                "claimed_closest": claimed_closest,
                "claimed_separation": claimed_relative,
                "relative_error": separation_error,
                "tolerance": SEPARATION_MATCH_TOLERANCE,
            },
        }
    )

    forecast = evidence.get("forecast")
    if not isinstance(forecast, Mapping):
        raise LaboratoryError("forecast must be an object")
    steps = [int(step) for step in forecast.get("steps", []) if isinstance(step, (int, float))]
    claimed_values = forecast.get("psi_y")
    if not isinstance(claimed_values, Sequence) or isinstance(claimed_values, (str, bytes)):
        raise LaboratoryError("forecast.psi_y must be a list of numbers")
    truth_values = world.forecast_truth()
    tolerance = FORECAST_TOLERANCE * world.forecast_scale()
    declared_steps = [int(step) for step in world.forecast_steps]
    errors: list[float | None] = []
    if steps == declared_steps and len(claimed_values) == len(declared_steps):
        for truth_value, claimed_value in zip(truth_values, claimed_values):
            try:
                errors.append(abs(float(claimed_value) - float(truth_value)))
            except (TypeError, ValueError):
                errors.append(None)
    else:
        errors = [None] * len(declared_steps)
    checks.append(
        {
            "name": "the held-out forecast matches the field",
            "ok": (
                steps == declared_steps
                and len(claimed_values) == len(declared_steps)
                and all(error is not None and error <= tolerance for error in errors)
            ),
            "detail": json.dumps(
                {
                    "steps": declared_steps,
                    "truth": truth_values,
                    "claimed": list(claimed_values),
                    "absolute_errors": errors,
                    "tolerance": tolerance,
                },
                sort_keys=True,
            ),
            "numbers": {"tolerance": tolerance, "max_absolute_error": max(
                [error for error in errors if error is not None], default=None
            )},
        }
    )

    pairwise: dict[str, Any] = {}
    for index, left in enumerate(world.laws):
        for right in world.laws[index + 1:]:
            left_id, right_id = str(left["law_id"]), str(right["law_id"])
            left_value, right_value = predicted[left_id], predicted[right_id]
            pairwise[f"{left_id}|{right_id}"] = abs(left_value - right_value) / max(
                abs(left_value), abs(right_value)
            )
    worst_pair = min(pairwise.values()) if pairwise else None
    controls.append(
        {
            "name": "the observations separate every pair of candidates",
            "ok": worst_pair is not None and worst_pair >= SEPARATION_FLOOR,
            "detail": (
                "the measured quantity of the shipped recipe differs between candidates by at "
                f"least {worst_pair!r}; a world below the floor cannot decide anything"
            ),
            "numbers": {"worst_pairwise": worst_pair, "floor": SEPARATION_FLOOR, "pairs": pairwise},
        }
    )

    controls.insert(
        1,
        {
            "name": "the declared instrument can read its own observation",
            "ok": float(fitted["residual_relative"]) <= MEASUREMENT_RESIDUAL_FLOOR,
            "detail": (
                "the shipped series of the measured recipe has to be a single tone for the "
                f"declared fit to mean anything; its residual is {float(fitted['residual_relative']):.4f} "
                "of the fitted amplitude"
            ),
            "numbers": {
                "residual_relative": float(fitted["residual_relative"]),
                "floor": MEASUREMENT_RESIDUAL_FLOOR,
            },
        },
    )

    design_closest, _design_separation = _closest_other(
        predicted, predicted[str(truth["law_id"])], str(truth["law_id"])
    )
    truth_values_other = world.forecast_truth(law_by_id(world.laws, design_closest))
    forecast_gap = max(
        (abs(left - right) for left, right in zip(truth_values, truth_values_other)), default=0.0
    )
    controls.append(
        {
            "name": "the held-out steps separate the closest other candidate",
            "ok": forecast_gap >= tolerance,
            "detail": (
                f"the forecast of {design_closest!r} differs from the true forecast by at most "
                f"{forecast_gap:.6f}, against a tolerance of {tolerance:.6f}"
            ),
            "numbers": {
                "closest_other_law": design_closest,
                "forecast_gap": forecast_gap,
                "tolerance": tolerance,
            },
        }
    )
    controls.append(
        {
            "name": "the held-out window is not flat",
            "ok": max((abs(value) for value in truth_values), default=0.0) >= 3.0 * tolerance,
            "detail": "a flat forecast window would make the forecast check vacuous",
            "numbers": {"max_abs_truth": max((abs(value) for value in truth_values), default=0.0)},
        }
    )

    design_ok = all(bool(item["ok"]) for item in controls[:2])
    checks.append(
        {
            "name": "the world's observations can decide",
            "ok": design_ok,
            "detail": (
                "a readable instrument and a separation floor are part of the station's contract, "
                "not the agent's score"
            ),
            "numbers": {
                "worst_pairwise": worst_pair,
                "floor": SEPARATION_FLOOR,
                "residual_relative": float(fitted["residual_relative"]),
            },
        }
    )

    verdict = "pass" if all(bool(item["ok"]) for item in checks) else "fail"
    return stations_module._report(
        "identification",
        verdict,
        checks,
        controls,
        {
            "judge_omega": float(fitted["omega"]),
            "fit_residual_relative": float(fitted["residual_relative"]),
            "predicted_omega": predicted,
            "judge_closest_other_law": closest,
            "judge_separation": separation,
            "true_forecast": truth_values,
            "true_law_id": str(truth["law_id"]),
            "true_law_description": str(truth.get("description", "")),
        },
        [
            "the world identity commits to the hidden law; the brief never names it",
            "every judge number comes from the judge's own runs of the declared laws",
        ],
    )


def judge_retention(world: HiddenWorld, evidence: Mapping[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []

    claimed_recipes = evidence.get("recipes")
    if not isinstance(claimed_recipes, Sequence) or isinstance(claimed_recipes, (str, bytes)):
        raise LaboratoryError("recipes must be a list")
    claimed: dict[str, Mapping[str, Any]] = {}
    for item in claimed_recipes:
        if not isinstance(item, Mapping):
            raise LaboratoryError("every retention claim must be an object")
        claimed[str(item.get("recipe_id", ""))] = item
    expected = [str(recipe["recipe_id"]) for recipe in world.retention_menu]
    missing = [recipe_id for recipe_id in expected if recipe_id not in claimed]
    if missing:
        raise LaboratoryError(f"no lifetime was claimed for {missing}")

    truth = world.retention_lifetimes()
    per_recipe: dict[str, Any] = {}
    all_ok = True
    for recipe_id in expected:
        claimed_item = claimed[recipe_id]
        truth_value = truth[recipe_id]
        claim_kind = str(claimed_item.get("claim", "")).strip()
        if truth_value is None:
            ok = claim_kind == "beyond-horizon"
            detail = "the write never fell to the threshold within the horizon"
            numbers: dict[str, Any] = {"truth": None, "claimed": claim_kind}
        else:
            error = _relative(float(truth_value), claimed_item.get("tau_seconds"))
            tolerance = max(
                RETENTION_RELATIVE_TOLERANCE * float(truth_value), RETENTION_ABSOLUTE_TOLERANCE
            )
            ok = (
                claim_kind == "measured"
                and error is not None
                and abs(float(claimed_item.get("tau_seconds")) - float(truth_value)) <= tolerance
            )
            detail = (
                f"declared procedure gives {truth_value} time units for {recipe_id}"
            )
            numbers = {
                "truth": float(truth_value),
                "claimed": claimed_item.get("tau_seconds"),
                "absolute_error": (
                    None
                    if error is None
                    else abs(float(claimed_item.get("tau_seconds")) - float(truth_value))
                ),
                "tolerance": tolerance,
            }
        all_ok = all_ok and ok
        per_recipe[recipe_id] = {"ok": ok, "detail": detail, "numbers": numbers}

    checks.append(
        {
            "name": "every write's lifetime matches the declared procedure",
            "ok": all_ok,
            "detail": json.dumps(
                {key: value["detail"] for key, value in per_recipe.items()}, sort_keys=True
            ),
            "numbers": {key: value["numbers"] for key, value in per_recipe.items()},
        }
    )

    truth_longest = longest_recipe(
        [
            {
                "recipe_id": recipe_id,
                "claim": "beyond-horizon" if truth[recipe_id] is None else "measured",
                "tau_seconds": truth[recipe_id],
            }
            for recipe_id in expected
        ]
    )
    claimed_longest = str(evidence.get("longest", "")).strip()
    checks.append(
        {
            "name": "the longest-lived write is named",
            "ok": claimed_longest == truth_longest,
            "detail": (
                "under the declared rule a beyond-horizon write outlives every measured one; "
                f"the true longest is {truth_longest!r}"
            ),
            "numbers": {"truth": truth_longest, "claimed": claimed_longest},
        }
    )

    measured_values = [value for value in truth.values() if value is not None]
    spread = (max(measured_values) - min(measured_values)) if measured_values else 0.0
    controls.append(
        {
            "name": "the menu contains distinct lifetimes",
            "ok": spread >= RETENTION_SPREAD_FLOOR or any(value is None for value in truth.values()),
            "detail": f"the declared procedure separates the menu by {spread:.4f} time units",
            "numbers": {"spread": spread, "floor": RETENTION_SPREAD_FLOOR, "truth": truth},
        }
    )

    other_laws: dict[str, Any] = {}
    law_sensitive = False
    for law in world.laws:
        law_id = str(law["law_id"])
        if law_id == str(world.true_law_id):
            continue
        lifetimes = world.retention_lifetimes(law)
        differences: dict[str, Any] = {}
        for recipe_id in expected:
            left, right = truth[recipe_id], lifetimes[recipe_id]
            if left is None or right is None:
                different = (left is None) != (right is None)
                differences[recipe_id] = None if different else 0.0
            else:
                different = False
                differences[recipe_id] = abs(left - right)
            tolerance = max(
                RETENTION_RELATIVE_TOLERANCE * (1.0 if left is None else float(left)),
                RETENTION_ABSOLUTE_TOLERANCE,
            )
            if different or (differences[recipe_id] or 0.0) > tolerance:
                law_sensitive = True
        other_laws[law_id] = {"lifetimes": lifetimes, "absolute_differences": differences}
    controls.append(
        {
            "name": "the lifetimes carry the law",
            "ok": law_sensitive,
            "detail": (
                "at least one other candidate law changes at least one lifetime beyond the "
                "station's tolerance, so a wrong attribution is visible here"
            ),
            "numbers": {"other_laws": other_laws},
        }
    )
    checks.append(
        {
            "name": "the menu is a usable measurement",
            "ok": bool(controls[0]["ok"]) and bool(controls[1]["ok"]),
            "detail": "distinct lifetimes that a wrong law would miss are the station's contract",
            "numbers": {"spread": spread},
        }
    )

    verdict = "pass" if all(bool(item["ok"]) for item in checks) else "fail"
    return stations_module._report(
        "retention",
        verdict,
        checks,
        controls,
        {
            "true_lifetimes": truth,
            "true_longest": truth_longest,
            "claimed_longest": claimed_longest,
            "per_recipe": per_recipe,
            "other_laws": other_laws,
        },
        [
            "lifetimes are measured with the declared procedure on the judge's own runs",
            "the beyond-horizon branch is a claim about the horizon, not a missing number",
        ],
    )


# --------------------------------------------------------------------------- #
# worlds
# --------------------------------------------------------------------------- #


def hidden_world(
    *,
    true_law_id: str = "L1-native-w25",
    laws: Sequence[Mapping[str, Any]] = LAW_MENU,
    node_count: int = 24,
    dt: float = 0.01,
    variant: str = "hidden-1",
    observations: Sequence[Mapping[str, Any]] = OBSERVATION_RECIPES,
    retention_menu: Sequence[Mapping[str, Any]] = DEFAULT_RETENTION_MENU,
    retention: Mapping[str, Any] | None = None,
    forecast_steps: Sequence[int] = FORECAST_STEPS,
) -> HiddenWorld:
    """One hidden world with the declared observations and write menu."""

    law_by_id(laws, true_law_id)
    complex_ = CellComplex.chain(node_count, spacing=1.0, conductance=1.0)
    declared_observations: list[dict[str, Any]] = []
    for recipe in observations:
        recipe_document(recipe["recipe_id"], recipe["family"], recipe["parameters"])
        declared_observations.append(
            {
                "recipe_id": str(recipe["recipe_id"]),
                "family": str(recipe["family"]),
                "parameters": {key: float(value) for key, value in recipe["parameters"].items()},
                "steps_observed": int(recipe.get("steps_observed", 600)),
                "sample_every": int(recipe.get("sample_every", 50)),
                "full_field": bool(recipe.get("full_field", False)),
            }
        )
    menu = tuple(
        recipe_document(recipe["recipe_id"], recipe["family"], recipe["parameters"])
        for recipe in retention_menu
    )
    procedure = dict(DEFAULT_RETENTION)
    procedure.update(dict(retention or {}))
    return HiddenWorld(
        complex=complex_,
        dt=float(dt),
        probe=node_count // 2,
        laws=tuple(dict(law) for law in laws),
        true_law_id=str(true_law_id),
        observations=tuple(declared_observations),
        forecast_steps=tuple(int(step) for step in forecast_steps),
        retention_menu=menu,
        retention=procedure,
        variant=str(variant),
    )


def hidden_worlds_for_laws(
    law_ids: Sequence[str],
    *,
    laws: Sequence[Mapping[str, Any]] = LAW_MENU,
    variant_prefix: str = "shift",
    **kwargs: Any,
) -> tuple[HiddenWorld, ...]:
    """One hidden world per round, sharing recipes and differing only in the law."""

    return tuple(
        hidden_world(
            true_law_id=str(law_id),
            laws=laws,
            variant=f"{variant_prefix}-round{index}",
            **kwargs,
        )
        for index, law_id in enumerate(law_ids)
    )


# --------------------------------------------------------------------------- #
# scripted agents
# --------------------------------------------------------------------------- #


def _brief(exchange: Mapping[str, Any]) -> tuple[Mapping[str, Any], str]:
    if not isinstance(exchange, Mapping):
        raise TypeError("station exchange must be a mapping")
    nested = exchange.get("brief")
    brief = nested if isinstance(nested, Mapping) else exchange
    station = str(exchange.get("station_id", brief.get("station", "")))
    if not station:
        raise ValueError("station exchange has no station id")
    return brief, station


def _complex_from(document: Mapping[str, Any]) -> CellComplex:
    volumes = tuple(float(value) for value in document["volumes"])
    edges = tuple((int(edge[0]), int(edge[1]), float(edge[2])) for edge in document["edges"])
    return CellComplex(volumes=volumes, edges=edges)


def _brief_laws(brief: Mapping[str, Any]) -> list[dict[str, Any]]:
    world = brief.get("world")
    if not isinstance(world, Mapping):
        raise ValueError("the brief carries no world")
    laws = world.get("candidate_laws")
    if not isinstance(laws, Sequence) or isinstance(laws, (str, bytes)):
        raise ValueError("the world declares no candidate laws")
    return [law_from_document(document) for document in laws]


def _observed_probe_series(brief: Mapping[str, Any], recipe_id: str) -> tuple[np.ndarray, np.ndarray]:
    rows = brief.get("observations")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("the brief carries no observations")
    recipe = next(
        (item for item in rows if isinstance(item, Mapping) and str(item.get("recipe_id")) == recipe_id),
        None,
    )
    if recipe is None:
        raise ValueError(f"no observed recipe {recipe_id!r}")
    samples = recipe.get("samples")
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)):
        raise ValueError(f"recipe {recipe_id!r} carries no samples")
    times = np.array([float(row["time"]) for row in samples], dtype=float)
    values = np.array([float(row["probe_psi_y"]) for row in samples], dtype=float)
    return times, values


def _measured_recipe_id(brief: Mapping[str, Any]) -> str:
    """The recipe the world's instrument reads, as its brief declares it."""

    measurement = brief.get("measurement")
    if isinstance(measurement, Mapping) and measurement.get("recipe_id"):
        return str(measurement["recipe_id"])
    rows = brief.get("observations")
    if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)) and rows:
        return str(rows[0]["recipe_id"])
    raise ValueError("the brief declares no measured recipe")


def _recipe_from_brief(brief: Mapping[str, Any], recipe_id: str) -> dict[str, Any]:
    rows = brief.get("observations")
    recipe = next(
        (
            item
            for item in rows
            if isinstance(item, Mapping) and str(item.get("recipe_id")) == recipe_id
        ),
        None,
    )
    if recipe is None:
        raise ValueError(f"no observed recipe {recipe_id!r}")
    return {
        "recipe_id": str(recipe["recipe_id"]),
        "family": str(recipe["family"]),
        "parameters": dict(recipe["parameters"]),
        "steps_observed": int(recipe.get("steps_observed", 600)),
        "sample_every": int(recipe.get("sample_every", 50)),
    }


def _simulate(
    complex_: CellComplex,
    model: Model,
    dt: float,
    probe: int,
    recipe: Mapping[str, Any],
    steps: int,
    sample_every: int,
) -> tuple[np.ndarray, np.ndarray]:
    engine = NativeFieldOracle(complex_, model, dt)
    state = build_state(complex_, model, recipe["family"], recipe["parameters"])
    times: list[float] = []
    values: list[float] = []
    time = 0.0
    for index in range(steps + 1):
        if index % sample_every == 0:
            times.append(time)
            values.append(float(state.psi_y[probe]))
        state = engine.step(state)
        time += dt
    return np.array(times, dtype=float), np.array(values, dtype=float)


def _identification_evidence(
    brief: Mapping[str, Any],
    chosen: str,
    *,
    inertia: str | None = None,
    measured: Mapping[str, Any] | None = None,
    separation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build identification evidence for one named law, everything recomputed.

    ``measured`` and ``separation`` let a reader that stopped looking report the
    values it last read; the forecast is always recomputed from the named law,
    because it is a statement about the world rather than about the reading.
    """

    world = brief["world"]
    complex_ = _complex_from(world["complex"])
    dt = float(world["dt"])
    probe = int(world["probe_node"])
    laws = _brief_laws(brief)
    measured_recipe = _measured_recipe_id(brief)
    times, values = _observed_probe_series(brief, measured_recipe)
    recipe = _recipe_from_brief(brief, measured_recipe)
    reading = measure_omega(times, values)

    predicted: dict[str, float] = {}
    for law in laws:
        model = law_model(law, yin=inertia)
        simulated = _simulate(
            complex_, model, dt, probe, recipe,
            int(recipe["steps_observed"]), int(recipe["sample_every"]),
        )
        predicted[str(law["law_id"])] = float(measure_omega(*simulated)["omega"])

    others = {key: value for key, value in predicted.items() if key != chosen}
    if not others:
        raise LaboratoryError("the law menu has only one candidate")
    closest = min(
        others, key=lambda key: (abs(reading["omega"] - others[key]) / max(abs(others[key]), 1e-30), key)
    )
    relative = abs(reading["omega"] - others[closest]) / max(abs(others[closest]), 1e-30)

    evidence: dict[str, Any] = {
        "schema": EVIDENCE_IDENTIFICATION,
        "law_id": str(chosen),
        "measured": dict(
            measured
            or {
                "quantity": "probe_omega",
                "recipe_id": measured_recipe,
                "value": float(reading["omega"]),
            }
        ),
        "separation": dict(
            separation or {"closest_other_law": closest, "relative": float(relative)}
        ),
    }

    declared_forecast = brief.get("forecast")
    if isinstance(declared_forecast, Mapping) and declared_forecast.get("steps"):
        forecast_steps = [int(step) for step in declared_forecast["steps"]]
        chosen_law = law_by_id(laws, chosen)
        chosen_model = law_model(chosen_law, yin=inertia)
        engine = NativeFieldOracle(complex_, chosen_model, dt)
        state = build_state(complex_, chosen_model, recipe["family"], recipe["parameters"])
        wanted = set(forecast_steps)
        found: dict[int, float] = {}
        for index in range(max(forecast_steps) + 1):
            if index in wanted:
                found[index] = float(state.psi_y[probe])
            state = engine.step(state)
        evidence["forecast"] = {
            "recipe_id": measured_recipe,
            "node": probe,
            "steps": forecast_steps,
            "psi_y": [float(found[step]) for step in forecast_steps],
        }

    return evidence


def _candidate_deviations(
    brief: Mapping[str, Any], *, inertia: str | None = None
) -> dict[str, float]:
    """How far each candidate law's own run of the measured recipe sits from the shipped one."""

    world = brief["world"]
    complex_ = _complex_from(world["complex"])
    dt = float(world["dt"])
    probe = int(world["probe_node"])
    laws = _brief_laws(brief)
    measured_recipe = _measured_recipe_id(brief)
    _times, values = _observed_probe_series(brief, measured_recipe)
    recipe = _recipe_from_brief(brief, measured_recipe)
    deviations: dict[str, float] = {}
    for law in laws:
        model = law_model(law, yin=inertia)
        simulated = _simulate(
            complex_, model, dt, probe, recipe,
            int(recipe["steps_observed"]), int(recipe["sample_every"]),
        )
        deviations[str(law["law_id"])] = float(np.max(np.abs(simulated[1] - values)))
    return deviations


def _identify(
    brief: Mapping[str, Any], *, inertia: str | None = None
) -> dict[str, Any]:
    """The honest identification: compare every candidate with the shipped run."""

    deviations = _candidate_deviations(brief, inertia=inertia)
    chosen = min(deviations, key=lambda key: (deviations[key], key))
    return _identification_evidence(brief, chosen, inertia=inertia)


def misattributing_agent() -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """The honest reader with one mistake: it names the runner-up law.

    Its measurement is real and its forecast is a real forecast -- of the wrong
    law.  This is the control an authored station must always be able to catch,
    whatever law the author chose to hide.
    """

    def answer(exchange: Mapping[str, Any]) -> dict[str, Any]:
        brief, station = _brief(exchange)
        ranking = sorted(_candidate_deviations(brief).items(), key=lambda item: (item[1], item[0]))
        if len(ranking) < 2:
            raise ValueError("a misattribution needs at least two candidate laws")
        chosen = ranking[1][0]
        if station == "identification":
            return _identification_evidence(brief, chosen)
        if station == "retention":
            return _retention_answer(brief, chosen)
        raise ValueError(f"unknown station {station!r}")

    return answer


def identify_as(
    brief: Mapping[str, Any],
    law_id: str,
    *,
    inertia: str | None = None,
    measured: Mapping[str, Any] | None = None,
    separation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Identification evidence for a law the reader already carries.

    A reader that stopped looking can also freeze its reading and its
    separation claim; the forecast still follows the law it named.
    """

    law_by_id(_brief_laws(brief), law_id)
    return _identification_evidence(
        brief, law_id, inertia=inertia, measured=measured, separation=separation
    )


def _retention_answer(
    brief: Mapping[str, Any], law_id: str, *, inertia: str | None = None
) -> dict[str, Any]:
    world = brief["world"]
    complex_ = _complex_from(world["complex"])
    dt = float(world["dt"])
    declared = brief["retention"]
    procedure = dict(declared["procedure"])
    menu = [dict(item) for item in declared["menu"]]
    law = law_by_id(_brief_laws(brief), law_id)
    model = law_model(law, yin=inertia)
    claims: list[dict[str, Any]] = []
    for recipe in menu:
        tau = retention_tau(complex_, model, dt, recipe, procedure)
        claims.append(
            {
                "recipe_id": str(recipe["recipe_id"]),
                "claim": "measured" if tau is not None else "beyond-horizon",
                "tau_seconds": tau,
            }
        )
    return {
        "schema": EVIDENCE_RETENTION,
        "recipes": claims,
        "longest": longest_recipe(claims),
    }


def _identified_law_id(brief: Mapping[str, Any], *, inertia: str | None = None) -> str:
    """Recover the law inside a station brief (both briefs carry the observations)."""

    if "observations" in brief:
        return str(_identify(brief, inertia=inertia)["law_id"])
    law_id = str(brief.get("law_id", "")).strip()
    if not law_id:
        raise ValueError("the brief carries neither observations nor an identified law")
    return law_id


def competent_agent() -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """The honest Level-2 answerer: identify by simulation, then forecast."""

    def answer(exchange: Mapping[str, Any]) -> dict[str, Any]:
        brief, station = _brief(exchange)
        if station == "identification":
            return _identify(brief)
        if station == "retention":
            return _retention_answer(brief, _identified_law_id(brief))
        raise ValueError(f"unknown station {station!r}")

    return answer


def confused_agent() -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """The documented one-model reader: every candidate is simulated with equal inertia.

    On a world whose law really is an equal-inertia law this reader happens to
    be right, which is exactly why the canary report names the world it ran on.
    """

    def answer(exchange: Mapping[str, Any]) -> dict[str, Any]:
        brief, station = _brief(exchange)
        if station == "identification":
            return _identify(brief, inertia="equal")
        if station == "retention":
            return _retention_answer(brief, _identified_law_id(brief, inertia="equal"), inertia="equal")
        raise ValueError(f"unknown station {station!r}")

    return answer


def shortcut_agent(*, claimed_verdict: str = "pass") -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """The deliberately unexecuted Level-2 answerer: guesses, self-declared."""

    def answer(exchange: Mapping[str, Any]) -> dict[str, Any]:
        brief, station = _brief(exchange)
        marker = {
            "attempted_private_symbols": [
                "laboratory.hidden.judge_identification",
                "laboratory.hidden.judge_retention",
                "laboratory.hidden.HiddenWorld.true_law",
            ],
            "claimed_verdict": str(claimed_verdict),
        }
        if station == "identification":
            steps = [int(step) for step in brief.get("forecast", {}).get("steps", [])]
            return {
                "schema": EVIDENCE_IDENTIFICATION,
                "law_id": "L1-native-w25",
                "measured": {"quantity": "probe_omega", "recipe_id": _measured_recipe_id(brief), "value": 0.9},
                "separation": {"closest_other_law": "L2-equal-w25", "relative": 0.05},
                "forecast": {
                    "recipe_id": _measured_recipe_id(brief),
                    "node": int(brief.get("world", {}).get("probe_node", 0)),
                    "steps": steps,
                    "psi_y": [0.0 for _ in steps],
                },
                "shortcut_attempt": marker,
                "verdict": str(claimed_verdict),
            }
        if station == "retention":
            menu = brief.get("retention", {}).get("menu", [])
            return {
                "schema": EVIDENCE_RETENTION,
                "recipes": [
                    {"recipe_id": str(item["recipe_id"]), "claim": "measured", "tau_seconds": 1.0}
                    for item in menu
                ],
                "longest": str(menu[-1]["recipe_id"]) if menu else "",
                "shortcut_attempt": marker,
                "verdict": str(claimed_verdict),
            }
        raise ValueError(f"unknown station {station!r}")

    return answer


CANARY_READERS: tuple[str, ...] = ("competent", "confused", "misattributing", "shortcut")


def hidden_canary_agents() -> Mapping[str, Callable[[Mapping[str, Any]], Mapping[str, Any]]]:
    return {
        "competent": competent_agent(),
        "confused": confused_agent(),
        "misattributing": misattributing_agent(),
        "shortcut": shortcut_agent(),
    }


def hidden_canary_report(
    world: HiddenWorld,
    *,
    receipt_dir: str | None = None,
    deadline_s: float = 900.0,
) -> dict[str, Any]:
    """Run the three scripted agents through the real Level-2 course."""

    from laboratory.course import Course, ScriptedAgent

    agents = hidden_canary_agents()
    runs: dict[str, Any] = {}
    for name in CANARY_READERS:
        agent = ScriptedAgent(answerer=agents[name], kind=f"canary-{name}")
        receipt = Course(
            world,
            world.stations(),
            level="hidden",
            world_block=world.declared_world(),
            title=world.title(),
        ).run(agent, receipt_path=None if receipt_dir is None else f"{receipt_dir}/hidden-{name}.json", deadline_s=deadline_s)
        failures = {
            item["station"]: [
                check["name"] for check in item.get("checks", []) if not check.get("ok")
            ]
            for item in receipt["stations"]
            if item.get("verdict") != "pass"
        }
        runs[name] = {
            "verdict": receipt["verdict"],
            "station_verdicts": receipt["station_verdicts"],
            "failed_checks": failures,
            "digest": receipt["digest"],
        }
    competent_pass = runs["competent"]["verdict"] == "pass"
    controls_fail = all(
        runs[name]["verdict"] != "pass" for name in CANARY_READERS if name != "competent"
    )
    return {
        "schema": HIDDEN_CANARY_SCHEMA,
        "variant": world.variant,
        "fixture_id": world.fixture_id(),
        "true_law_id": world.true_law_id,
        "true_law_description": str(world.true_law.get("description", "")),
        "agents": runs,
        "discriminates": bool(competent_pass and controls_fail),
    }


__all__ = [
    "LAW_SCHEMA",
    "HIDDEN_WORLD_SCHEMA",
    "EVIDENCE_IDENTIFICATION",
    "EVIDENCE_RETENTION",
    "HIDDEN_CANARY_SCHEMA",
    "LAW_MENU",
    "OBSERVATION_RECIPES",
    "DEFAULT_RETENTION_MENU",
    "DEFAULT_RETENTION",
    "MEASUREMENT_RECIPE_ID",
    "HiddenWorld",
    "law_model",
    "law_document",
    "law_menu_document",
    "law_from_document",
    "law_by_id",
    "build_state",
    "recipe_document",
    "measure_omega",
    "retention_tau",
    "longest_recipe",
    "brief_identification",
    "brief_retention",
    "judge_identification",
    "judge_retention",
    "hidden_world",
    "hidden_worlds_for_laws",
    "competent_agent",
    "confused_agent",
    "misattributing_agent",
    "shortcut_agent",
    "CANARY_READERS",
    "hidden_canary_agents",
    "hidden_canary_report",
]
