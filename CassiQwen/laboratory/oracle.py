"""Independent CPU physics judge for the Shifting Laboratory course.

This module is the course's ground truth. It implements, in double precision and
with the standard library plus ``numpy`` only, the qualified site-native
two-channel field core of ``CassiCosmos/ENGINE.md`` sections 2 and 5: a fixed
cell complex, the Yang/Yin conversion equations, the canonical momenta, the
conservative Hamiltonian ``H_F``, the directed edge power, a time-centred
kick-drift-kick (KDK) step, and the deterministic scenarios the stations use.

Nothing here talks to the network, the entity server, Godot or the GPU. Nothing
here reads a clock, a random number generator or an environment variable: every
number this module produces is a pure function of its declared inputs.

Physics (frozen)
----------------

Cell complex:  nodes ``i = 0 .. N-1`` with positive volumes ``V_i``; internal
edges ``(i, j, w)`` with ``i < j`` and positive conductance ``w``.  Oriented
incidence ``B`` is ``(E, N)`` with ``B[e, i] = +1``, ``B[e, j] = -1``,
``W = diag(w)``, stiffness ``K = Bᵀ W B`` (symmetric positive semidefinite,
``K @ 1 = 0`` on the closed operator), and the operator ``L = -M⁻¹ K`` with
``M = diag(V)``.  Registration convention: ``w = A / d``, so the regular chain
built by :meth:`CellComplex.chain` reproduces the ``1/h²`` second-difference
response.

Model (native, ``yin="phi"``)::

    psi_ddot_Y = c_f2 * L psi_Y - omega2 * eps
    psi_ddot_I = c_f2 * L psi_I + omega2 * eps
    eps        = psi_Y - phi * psi_I                    (per node)
    P_Y        = mu   * M psi_dot_Y
    P_I        = mu phi * M psi_dot_I

    H_F = (1/2) P_Yᵀ (mu M)⁻¹ P_Y + (1/2) P_Iᵀ (mu phi M)⁻¹ P_I
        + (mu c_f2 / 2)(psi_Yᵀ K psi_Y + phi psi_Iᵀ K psi_I)
        + (mu omega2 / 2) sum_i V_i (psi_Y,i - phi psi_I,i)²

    P_{i->j,s} = -(b_s w_ij / 2)(psi_s,j - psi_s,i)(psi_dot_s,i + psi_dot_s,j)
    P_{j->i,s} = -P_{i->j,s}          with b_Y = mu c_f2, b_I = mu phi c_f2

Counterfactual (``yin="equal"``, the documented wrong-inertia control): equal
channel inertia ``mu`` and equal gradient coefficients ``mu c_f2`` with the
*same* conversion potential, so the Yin conversion term gains a factor ``phi``::

    P_I        = mu * M psi_dot_I
    psi_ddot_I = c_f2 * L psi_I + phi * omega2 * eps

Both models are written generically as
``H_F = 1/2 Pᵀ(inertia M)⁻¹P + (b_s/2) psi_sᵀ K psi_s + (mu omega2/2) sum V eps²``
with ``inertia = Model.inertia()`` and ``b = Model.gradient()``, and each is
integrated with its own Hamiltonian consistently.  Their uniform conversion
frequencies differ: ``sqrt((1 + phi) omega2)`` (native) against
``sqrt((1 + phi²) omega2)`` (equal) -- the station-1 discriminator.

One step is time-centred kick-drift-kick with canonical momenta defined at
accepted integer times: a half kick with the force ``-dH_F/dpsi`` at the current
positions, a drift with ``dpsi/ds = dH/dP`` (exact, because the kinetic term is
quadratic in ``P``), and a second half kick with the force at the drifted
positions.

Scenario profiles (exact; node coordinate = node index)
--------------------------------------------------------

The frozen complex carries volumes and edges but no coordinate frame, so a
profile is written in *index* units ``x_i = i``.  For a chain built by
:meth:`CellComplex.chain` with spacing ``h`` this is the affine image of the
engine's physical coordinate (``x_phys = h * (x_index + 0.5)``).

``counterflow_packet(complex, model, *, amplitude, width, center, speed)``
    Two Gaussian bumps on the index axis, centred at ``center - 2*width``
    (direction ``+1``) and ``center + 2*width`` (direction ``-1``)::

        g_b(x) = amplitude * exp(-(x - c_b)^2 / (2 width^2)),  c_b = center -/+ 2 width
        psi_Y(x)  = g_+(x) + g_-(x)
        psi_I(x)  = psi_Y(x) / phi
        psi_dot_Y(x) = speed * sum_b  d_b * (x - c_b) / width^2 * g_b(x)     (exact derivative)
        psi_dot_I(x) = psi_dot_Y(x) / phi
        P_s = inertia_s * V * psi_dot_s                                      (declared rates)

    This is the engine's verified ``counterflow`` initializer: travelling-pulse
    profiles over axial centres with one direction per centre, fields and
    canonical rates adding linearly, so the net momentum cancels while both
    transport directions fire.  Because ``psi_Y = phi psi_I`` *and*
    ``psi_dot_Y = phi psi_dot_I`` hold pointwise, ``eps ≡ 0`` and
    ``eps_dot ≡ 0``; since ``eps_ddot = c_f2 L eps - (1 + phi) omega2 eps``
    (native) or ``c_f2 L eps - (1 + phi²) omega2 eps`` (equal), ``eps`` stays
    identically zero under both candidate models: this fixture cannot
    discriminate them, and both owe the same observations.  Defaults:
    ``amplitude = 1.0``, ``width = 2.0``, ``center = (N-1)/2``,
    ``speed = sqrt(c_f2)`` (the channel wave speed).

``epsilon_mode(complex, model, *, amplitude, width, center)``
    An excitation carrying ``eps != 0``, prepared at rest (``P = 0``)::

        f(x)     = amplitude * exp(-(x - center)^2 / (2 width^2))
        psi_Y(x) = +f(x)
        psi_I(x) = -f(x) / phi
        eps(x)   = 2 f(x)                     (pointwise)
        P_Y = P_I = 0                          (zero for both models)

    ``width=None`` gives the uniform profile ``f ≡ amplitude``, for which the
    conversion oscillation is the single uniform normal mode with frequency
    ``sqrt((1 + phi) omega2)`` (native) or ``sqrt((1 + phi²) omega2)`` (equal).
    A finite width localizes the excitation; its ``eps`` band then mixes spatial
    modes, and only the uniform preparation has a single clean frequency.

``resting(complex)``
    All four state arrays zero.

Self-check fixture (fixed, reported in the report's ``fixture`` field)
---------------------------------------------------------------------

* algebraic complex: volumes ``(0.7, 1.3, 0.9, 1.8)``, edges
  ``(0,1,0.8) (1,2,1.7) (2,3,0.5) (0,3,1.2) (0,2,0.4)`` (the engine's recorded
  fixture writes the wrap edge as ``(3, 0, 1.2)``; it is reoriented here to the
  frozen ``i < j`` convention, which leaves ``K = BᵀWB`` unchanged), and the
  engine's recorded field and momentum values;
* model: ``c_f2 = 0.8``, ``omega2 = 0.4``, ``mu = 1.25``, ``phi`` golden;
* KDK refinement: 16-node chain, spacing 1, horizon 0.4, dt levels
  0.02 / 0.01 / 0.005 / 0.0025;
* conversion frequency: the same algebraic complex, uniform ``epsilon_mode``
  with ``amplitude = 1``, ``dt = 0.004``, 5000 steps.

``NativeFieldOracle.self_check()`` is callable both on an instance and on the
class (``NativeFieldOracle.self_check()``); it always evaluates the fixed
fixture above, so the numbers are identical either way.  It never raises on a
failed check: every check is reported with its measured numbers.
"""

from __future__ import annotations

import json
import math
import platform
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

MODEL_ID = "cassi.laboratory.native-field.v1"
SELF_CHECK_SCHEMA = "cassi.laboratory.oracle-self-check.v1"
MODEL_SCHEMA = "cassi.laboratory.native-model.v1"
COMPLEX_SCHEMA = "cassi.laboratory.cell-complex.v1"

PHI = (1.0 + math.sqrt(5.0)) / 2.0

_YIN_MODES = ("phi", "equal")
_CHANNEL_ALIASES = {
    "yang": "yang",
    "yin": "yin",
    "y": "yang",
    "i": "yin",
}

# --------------------------------------------------------------------------- #
# Fixed self-check fixture
# --------------------------------------------------------------------------- #

_FIXTURE_VOLUMES = (0.7, 1.3, 0.9, 1.8)
# The engine's recorded four-node fixture writes the wrap edge as (3, 0, 1.2); it is
# reoriented here to the frozen i < j edge convention (K = BᵀWB is orientation-invariant).
_FIXTURE_EDGES = ((0, 1, 0.8), (1, 2, 1.7), (2, 3, 0.5), (0, 3, 1.2), (0, 2, 0.4))
_FIXTURE_C_F2 = 0.8
_FIXTURE_OMEGA2 = 0.4
_FIXTURE_MU = 1.25
_FIXTURE_DT = 0.01
# The engine's recorded four-node algebra fixture (ENGINE.md section 11).
_FIXTURE_PSI_Y = (0.25, -0.7, 1.1, 0.3)
_FIXTURE_PSI_I = (-0.2, 0.5, 0.8, -0.9)
_FIXTURE_P_Y = (0.4, -0.3, 0.8, 0.1)
_FIXTURE_P_I = (-0.5, 0.7, 0.2, -0.4)

_KDK_CHAIN_NODES = 16
_KDK_CHAIN_SPACING = 1.0
_KDK_HORIZON = 0.4
_KDK_DT_LEVELS = (0.02, 0.01, 0.005, 0.0025)

_EPS_MODE_AMPLITUDE = 1.0
_EPS_MODE_DT = 0.004
_EPS_MODE_STEPS = 5000

_TOL_STIFFNESS_NULL = 1e-12
_TOL_POWER_IDENTITY = 1e-12
_TOL_GRADIENT_MATCH = 1e-8
_CONTROL_MIN_MISMATCH = 1e-4
_TOL_FREQUENCY = 1e-3
_MIN_FREQUENCY_SEPARATION = 1e-2
_ORDER_TARGET = 2.0
_ORDER_TOLERANCE = 0.2
_PER_STEP_DRIFT_BOUND = 1e-4
_MAX_FIT_RESIDUAL = 1e-5
_TOL_EPS2_RATIO = 1e-3


class OracleError(RuntimeError):
    """Raised for an invalid complex, model, oracle configuration or state."""


# --------------------------------------------------------------------------- #
# small numeric helpers
# --------------------------------------------------------------------------- #


def _as_float(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OracleError(f"{label} must be a real number, got {value!r}") from exc
    if not math.isfinite(number):
        raise OracleError(f"{label} must be finite, got {value!r}")
    return number


def _as_index(value: Any, label: str) -> int:
    number = _as_float(value, label)
    if number != math.floor(number):
        raise OracleError(f"{label} must be an integer index, got {value!r}")
    return int(number)


def _relative_max(difference_max: float, scale: float) -> float:
    """``max|difference| / scale`` with a nonzero denominator for the report."""
    return float(difference_max) / max(float(scale), 1e-300)


def _checked_channel(channel: Any) -> str:
    if not isinstance(channel, str):
        raise OracleError(f"channel must be a string, got {type(channel).__name__}")
    key = channel.strip().lower()
    if key not in _CHANNEL_ALIASES:
        raise OracleError(f"unknown channel {channel!r}; expected 'yang' or 'yin'")
    return _CHANNEL_ALIASES[key]


def _summary(differences: np.ndarray, reference: np.ndarray) -> dict:
    """max|difference| and its relative size against the reference's own scale."""
    difference_max = float(np.max(np.abs(differences))) if differences.size else 0.0
    scale = float(np.max(np.abs(reference))) if reference.size else 0.0
    return {
        "max_abs": difference_max,
        "scale": scale,
        "relative": _relative_max(difference_max, scale),
        "attempted": int(differences.size),
    }


def _momentum_from_rates(
    volumes: np.ndarray, inertia: tuple[float, float], rate_y: np.ndarray, rate_i: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Canonical momenta from declared field rates: ``P_s = inertia_s * M psi_dot_s``."""
    return inertia[0] * volumes * rate_y, inertia[1] * volumes * rate_i


def _index_coordinates(complex_: CellComplex) -> np.ndarray:
    return np.arange(complex_.node_count, dtype=float)


def _gaussian(x: np.ndarray, center: float, width: float) -> np.ndarray:
    return np.exp(-((x - center) ** 2) / (2.0 * width * width))


def _fit_frequency(
    times: np.ndarray,
    values: np.ndarray,
    guess: float,
    *,
    span: float = 0.12,
    points: int = 97,
    rounds: int = 3,
) -> dict:
    """Least-squares fit of ``values(t) ~ A cos(w t) + B sin(w t) + C``.

    The bracket is refined ``rounds`` times about the best candidate; the fit is
    free to choose the frequency, amplitude, phase and offset.
    """
    times = np.asarray(times, dtype=float)
    values = np.asarray(values, dtype=float)
    low = float(guess) * (1.0 - span)
    high = float(guess) * (1.0 + span)
    best_omega = float(guess)
    best_coefficients = np.zeros(3)
    best_cost = math.inf
    for _ in range(rounds):
        grid = np.linspace(low, high, points)
        for omega in grid:
            basis = np.empty((times.size, 3))
            basis[:, 0] = np.cos(omega * times)
            basis[:, 1] = np.sin(omega * times)
            basis[:, 2] = 1.0
            coefficients, *_ = np.linalg.lstsq(basis, values, rcond=None)
            residual = values - basis @ coefficients
            cost = float(residual @ residual)
            if cost < best_cost:
                best_cost = cost
                best_omega = float(omega)
                best_coefficients = coefficients
        half_width = (high - low) / (points - 1)
        low = best_omega - half_width
        high = best_omega + half_width
    basis = np.empty((times.size, 3))
    basis[:, 0] = np.cos(best_omega * times)
    basis[:, 1] = np.sin(best_omega * times)
    basis[:, 2] = 1.0
    residual = values - basis @ best_coefficients
    amplitude = float(math.hypot(best_coefficients[0], best_coefficients[1]))
    residual_max = float(np.max(np.abs(residual)))
    return {
        "omega": best_omega,
        "amplitude": amplitude,
        "offset": float(best_coefficients[2]),
        "residual_max": residual_max,
        "residual_relative": _relative_max(residual_max, amplitude),
        "samples": int(times.size),
    }


def _first_zero_crossing(times: np.ndarray, values: np.ndarray) -> float | None:
    """Linearly interpolated first positive-to-negative crossing, or ``None``."""
    signs = np.sign(np.asarray(values, dtype=float))
    crossings = np.nonzero(np.diff(signs) < 0)[0]
    if crossings.size == 0:
        return None
    index = int(crossings[0])
    t0, t1 = float(times[index]), float(times[index + 1])
    v0, v1 = float(values[index]), float(values[index + 1])
    if v0 == v1:
        return t0
    return t0 + (t1 - t0) * (0.0 - v0) / (v1 - v0)


def _max_rate_eigenvalue(complex_: CellComplex) -> float:
    """Largest eigenvalue of ``M⁻¹ K`` (a symmetric similarity transform)."""
    volumes = np.asarray(complex_.volumes, dtype=float)
    root = 1.0 / np.sqrt(volumes)
    scaled = root[:, None] * complex_.stiffness() * root[None, :]
    eigenvalues = np.linalg.eigvalsh(0.5 * (scaled + scaled.T))
    return float(np.max(eigenvalues))


# --------------------------------------------------------------------------- #
# fixed interface
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CellComplex:
    """Fixed cell complex: positive node volumes and internal edges ``(i, j, w)``."""

    volumes: tuple[float, ...]
    edges: tuple[tuple[int, int, float], ...]

    def __post_init__(self) -> None:
        volumes = tuple(self.volumes)
        for index, volume in enumerate(volumes):
            number = _as_float(volume, f"volumes[{index}]")
            if number <= 0.0:
                raise OracleError(f"volumes[{index}] must be positive, got {number!r}")
            volumes = volumes[:index] + (number,) + volumes[index + 1 :]
        if not volumes:
            raise OracleError("CellComplex requires at least one node")

        edges: list[tuple[int, int, float]] = []
        seen: set[tuple[int, int]] = set()
        for index, edge in enumerate(tuple(self.edges)):
            try:
                tail, head, conductance = edge
            except (TypeError, ValueError) as exc:
                raise OracleError(
                    f"edges[{index}] must be a (tail, head, conductance) triple, got {edge!r}"
                ) from exc
            tail = _as_index(tail, f"edges[{index}].tail")
            head = _as_index(head, f"edges[{index}].head")
            weight = _as_float(conductance, f"edges[{index}].conductance")
            if not 0 <= tail < head < len(volumes):
                raise OracleError(
                    f"edges[{index}] = ({tail}, {head}) must satisfy 0 <= tail < head < {len(volumes)}"
                )
            if weight <= 0.0:
                raise OracleError(f"edges[{index}] conductance must be positive, got {weight!r}")
            if (tail, head) in seen:
                raise OracleError(f"edges[{index}] duplicates edge ({tail}, {head})")
            seen.add((tail, head))
            edges.append((tail, head, weight))

        object.__setattr__(self, "volumes", volumes)
        object.__setattr__(self, "edges", tuple(edges))

    @property
    def node_count(self) -> int:
        return len(self.volumes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def incidence(self) -> np.ndarray:
        """Oriented incidence ``B`` with shape ``(E, N)``, ``B[e, i] = +1``, ``B[e, j] = -1``."""
        incidence = np.zeros((self.edge_count, self.node_count), dtype=float)
        for index, (tail, head, _weight) in enumerate(self.edges):
            incidence[index, tail] = 1.0
            incidence[index, head] = -1.0
        return incidence

    def stiffness(self) -> np.ndarray:
        """``K = Bᵀ W B``, exactly symmetric, with ``K @ 1 = 0``."""
        incidence = self.incidence()
        weights = np.array([edge[2] for edge in self.edges], dtype=float)
        stiffness = incidence.T @ (weights[:, None] * incidence)
        return 0.5 * (stiffness + stiffness.T)

    def operator(self) -> np.ndarray:
        """``L = -M⁻¹ K`` with ``M = diag(volumes)``."""
        volumes = np.asarray(self.volumes, dtype=float)[:, None]
        return -(self.stiffness() / volumes)

    @staticmethod
    def chain(node_count: int, *, spacing: float = 1.0, conductance: float | None = None) -> "CellComplex":
        """Regular 1-D chain: fixed ends, ``node_count`` nodes, no periodic edge.

        Node volumes are the spacing ``h`` and edge conductances default to
        ``A / d = 1 / h``, so ``L`` is the second difference with the declared
        ``1/h²`` response.
        """
        count = _as_index(node_count, "node_count")
        if count < 1:
            raise OracleError(f"node_count must be at least 1, got {count}")
        h = _as_float(spacing, "spacing")
        if h <= 0.0:
            raise OracleError(f"spacing must be positive, got {h!r}")
        weight = 1.0 / h if conductance is None else _as_float(conductance, "conductance")
        if weight <= 0.0:
            raise OracleError(f"conductance must be positive, got {weight!r}")
        volumes = tuple([h] * count)
        edges = tuple((index, index + 1, weight) for index in range(count - 1))
        return CellComplex(volumes=volumes, edges=edges)

    def as_dict(self) -> dict:
        return {
            "schema": COMPLEX_SCHEMA,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "volumes": [float(volume) for volume in self.volumes],
            "edges": [[int(tail), int(head), float(weight)] for tail, head, weight in self.edges],
        }


@dataclass(frozen=True, slots=True)
class Model:
    """Native field constants and Yin channel convention."""

    c_f2: float
    omega2: float
    mu: float
    phi: float = PHI
    yin: str = "phi"

    def __post_init__(self) -> None:
        c_f2 = _as_float(self.c_f2, "c_f2")
        omega2 = _as_float(self.omega2, "omega2")
        mu = _as_float(self.mu, "mu")
        phi = _as_float(self.phi, "phi")
        if c_f2 < 0.0:
            raise OracleError(f"c_f2 must be non-negative, got {c_f2!r}")
        if omega2 < 0.0:
            raise OracleError(f"omega2 must be non-negative, got {omega2!r}")
        if mu <= 0.0:
            raise OracleError(f"mu must be positive, got {mu!r}")
        if phi <= 0.0:
            raise OracleError(f"phi must be positive, got {phi!r}")
        if self.yin not in _YIN_MODES:
            raise OracleError(f"yin must be one of {_YIN_MODES}, got {self.yin!r}")
        object.__setattr__(self, "c_f2", c_f2)
        object.__setattr__(self, "omega2", omega2)
        object.__setattr__(self, "mu", mu)
        object.__setattr__(self, "phi", phi)

    def inertia(self) -> tuple[float, float]:
        """Channel inertia ``(Yang, Yin)`` in ``P_s = inertia_s M psi_dot_s``."""
        if self.yin == "phi":
            return (self.mu, self.mu * self.phi)
        return (self.mu, self.mu)

    def gradient(self) -> tuple[float, float]:
        """Channel gradient coefficients ``(b_Y, b_I)`` of ``(b_s/2) psi_sᵀ K psi_s``."""
        if self.yin == "phi":
            return (self.mu * self.c_f2, self.mu * self.phi * self.c_f2)
        return (self.mu * self.c_f2, self.mu * self.c_f2)

    def as_dict(self) -> dict:
        inertia = self.inertia()
        gradient = self.gradient()
        return {
            "schema": MODEL_SCHEMA,
            "id": MODEL_ID,
            "c_f2": float(self.c_f2),
            "omega2": float(self.omega2),
            "mu": float(self.mu),
            "phi": float(self.phi),
            "yin": str(self.yin),
            "inertia": [float(inertia[0]), float(inertia[1])],
            "gradient": [float(gradient[0]), float(gradient[1])],
        }


@dataclass(frozen=True, slots=True)
class State:
    """Field values and canonical momenta at one accepted time."""

    psi_y: np.ndarray
    psi_i: np.ndarray
    p_y: np.ndarray
    p_i: np.ndarray


class NativeFieldOracle:
    """CPU reference integrator and measurement surface for one complex, model and dt."""

    def __init__(self, complex: CellComplex, model: Model, dt: float) -> None:
        if not isinstance(complex, CellComplex):
            raise OracleError(f"complex must be a CellComplex, got {type(complex).__name__}")
        if not isinstance(model, Model):
            raise OracleError(f"model must be a Model, got {type(model).__name__}")
        step = _as_float(dt, "dt")
        if step <= 0.0:
            raise OracleError(f"dt must be positive, got {step!r}")

        self._complex = complex
        self._model = model
        self._dt = step
        self._volumes = np.asarray(complex.volumes, dtype=float)
        self._stiffness = complex.stiffness()
        self._operator = complex.operator()
        self._inertia = model.inertia()
        self._gradient = model.gradient()
        self._c_f2 = float(model.c_f2)
        self._omega2 = float(model.omega2)
        self._phi = float(model.phi)
        # Native Yin conversion gain is 1; the wrong-inertia control carries phi.
        self._yin_gain = 1.0 if model.yin == "phi" else float(model.phi)
        self._inv_inertia_volume_y = 1.0 / (self._inertia[0] * self._volumes)
        self._inv_inertia_volume_i = 1.0 / (self._inertia[1] * self._volumes)
        # mu * omega2 * V, the conversion force scale in -dH/dpsi.
        self._conversion_force = float(model.mu) * float(model.omega2) * self._volumes
        self._edge_weights = np.array([edge[2] for edge in complex.edges], dtype=float)
        self._edge_tails = np.array([edge[0] for edge in complex.edges], dtype=int)
        self._edge_heads = np.array([edge[1] for edge in complex.edges], dtype=int)

    @property
    def complex(self) -> CellComplex:
        return self._complex

    @property
    def model(self) -> Model:
        return self._model

    @property
    def dt(self) -> float:
        return self._dt

    # -- internals ---------------------------------------------------------- #

    def _components(self, state: State) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if not isinstance(state, State):
            raise OracleError(f"state must be a State, got {type(state).__name__}")
        node_count = self._complex.node_count
        out: list[np.ndarray] = []
        for name in ("psi_y", "psi_i", "p_y", "p_i"):
            value = np.asarray(getattr(state, name), dtype=float)
            if value.shape != (node_count,):
                raise OracleError(
                    f"State.{name} has shape {value.shape}, expected ({node_count},)"
                )
            if not bool(np.all(np.isfinite(value))):
                raise OracleError(f"State.{name} contains a non-finite value")
            out.append(value)
        return out[0], out[1], out[2], out[3]

    def _reaction_forces(self, psi_y: np.ndarray, psi_i: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """``-dH_F/dpsi`` for both channels: the declared kick force at fixed positions."""
        epsilon = psi_y - self._phi * psi_i
        force_y = -(self._gradient[0] * (self._stiffness @ psi_y) + self._conversion_force * epsilon)
        force_i = -(
            self._gradient[1] * (self._stiffness @ psi_i)
            - self._phi * self._conversion_force * epsilon
        )
        return force_y, force_i

    def _channel(self, state: State, channel: Any) -> tuple[str, np.ndarray, np.ndarray]:
        key = _checked_channel(channel)
        psi_y, psi_i, p_y, p_i = self._components(state)
        if key == "yang":
            return key, psi_y, p_y * self._inv_inertia_volume_y
        return key, psi_i, p_i * self._inv_inertia_volume_i

    def _channel_parameters(self, key: str) -> tuple[float, float]:
        if key == "yang":
            return self._gradient[0], self._inertia[0]
        return self._gradient[1], self._inertia[1]

    # -- declared dynamics -------------------------------------------------- #

    def rates(self, state: State) -> tuple[np.ndarray, np.ndarray]:
        """Field time rates ``dpsi_s/ds = dH/dP_s``."""
        _psi_y, _psi_i, p_y, p_i = self._components(state)
        return p_y * self._inv_inertia_volume_y, p_i * self._inv_inertia_volume_i

    def accelerations(self, state: State) -> tuple[np.ndarray, np.ndarray]:
        """Declared equations of motion for both channels."""
        psi_y, psi_i, _p_y, _p_i = self._components(state)
        epsilon = psi_y - self._phi * psi_i
        return (
            self._c_f2 * (self._operator @ psi_y) - self._omega2 * epsilon,
            self._c_f2 * (self._operator @ psi_i) + self._yin_gain * self._omega2 * epsilon,
        )

    def epsilon(self, state: State) -> np.ndarray:
        """Per-node conversion variable ``eps = psi_Y - phi psi_I``."""
        psi_y, psi_i, _p_y, _p_i = self._components(state)
        return psi_y - self._phi * psi_i

    def hamiltonian(self, state: State) -> float:
        return float(self.partition(state)["total"])

    def partition(self, state: State) -> dict:
        """Kinetic / gradient / conversion energy per channel and in total."""
        psi_y, psi_i, p_y, p_i = self._components(state)
        epsilon = psi_y - self._phi * psi_i
        kinetic_yang = 0.5 * float(np.sum(p_y * p_y * self._inv_inertia_volume_y))
        kinetic_yin = 0.5 * float(np.sum(p_i * p_i * self._inv_inertia_volume_i))
        gradient_yang = 0.5 * self._gradient[0] * float(psi_y @ (self._stiffness @ psi_y))
        gradient_yin = 0.5 * self._gradient[1] * float(psi_i @ (self._stiffness @ psi_i))
        conversion = (
            0.5
            * float(self._model.mu)
            * float(self._model.omega2)
            * float(np.sum(self._volumes * epsilon * epsilon))
        )
        channels = {
            "yang": {"kinetic": kinetic_yang, "gradient": gradient_yang},
            "yin": {"kinetic": kinetic_yin, "gradient": gradient_yin},
        }
        return {
            "kinetic_yang": kinetic_yang,
            "kinetic_yin": kinetic_yin,
            "kinetic": kinetic_yang + kinetic_yin,
            "gradient_yang": gradient_yang,
            "gradient_yin": gradient_yin,
            "gradient": gradient_yang + gradient_yin,
            "conversion": conversion,
            "total": kinetic_yang + kinetic_yin + gradient_yang + gradient_yin + conversion,
            "channels": channels,
        }

    def edge_power(self, state: State, channel: Any) -> np.ndarray:
        """Directed edge power ``P_{i->j,s}`` per edge, with its sign."""
        key, values, rates = self._channel(state, channel)
        b_s, _inertia = self._channel_parameters(key)
        difference = values[self._edge_heads] - values[self._edge_tails]
        rate_sum = rates[self._edge_tails] + rates[self._edge_heads]
        return -(b_s * self._edge_weights / 2.0) * difference * rate_sum

    def node_power(self, state: State, channel: Any) -> np.ndarray:
        """Net power into each node: ``-(Bᵀ P_edge)``, summed over incident edges."""
        power = self.edge_power(state, channel)
        node_count = self._complex.node_count
        gained = np.bincount(self._edge_heads, weights=power, minlength=node_count)
        lost = np.bincount(self._edge_tails, weights=power, minlength=node_count)
        return gained - lost

    # -- integration -------------------------------------------------------- #

    def step(self, state: State) -> State:
        """One time-centred kick-drift-kick step."""
        psi_y, psi_i, p_y, p_i = self._components(state)
        half = 0.5 * self._dt

        force_y, force_i = self._reaction_forces(psi_y, psi_i)
        p_y = p_y + half * force_y
        p_i = p_i + half * force_i

        psi_y = psi_y + self._dt * (p_y * self._inv_inertia_volume_y)
        psi_i = psi_i + self._dt * (p_i * self._inv_inertia_volume_i)

        force_y, force_i = self._reaction_forces(psi_y, psi_i)
        p_y = p_y + half * force_y
        p_i = p_i + half * force_i

        return State(psi_y=psi_y, psi_i=psi_i, p_y=p_y, p_i=p_i)

    def advance(self, state: State, steps: int) -> State:
        """``step`` applied ``steps`` times."""
        count = _as_index(steps, "steps")
        if count < 0:
            raise OracleError(f"steps must be non-negative, got {steps!r}")
        current = state
        for _ in range(count):
            current = self.step(current)
        return current

    def observe(
        self, state: State, *, time: float, sites: Sequence[int] | None = None
    ) -> dict:
        """JSON-safe field slice at declared sites (all nodes when ``sites`` is None)."""
        psi_y, psi_i, _p_y, _p_i = self._components(state)
        when = _as_float(time, "time")
        if sites is None:
            indices = list(range(self._complex.node_count))
        else:
            if isinstance(sites, (str, bytes)):
                raise OracleError("sites must be a sequence of node indices")
            try:
                candidates = list(sites)
            except TypeError as exc:
                raise OracleError("sites must be a sequence of node indices") from exc
            indices = []
            for position, site in enumerate(candidates):
                index = _as_index(site, f"sites[{position}]")
                if not 0 <= index < self._complex.node_count:
                    raise OracleError(
                        f"sites[{position}] = {index} is outside 0..{self._complex.node_count - 1}"
                    )
                indices.append(index)
        return {
            "time": when,
            "sites": [int(index) for index in indices],
            "psi_y": [float(psi_y[index]) for index in indices],
            "psi_i": [float(psi_i[index]) for index in indices],
        }

    # -- self-check --------------------------------------------------------- #

    def self_check(self=None) -> dict:
        """Run the five fixed-fixture checks and report every measured number.

        Callable on the class (``NativeFieldOracle.self_check()``) or on an
        instance.  The fixture is fixed and independent of the instance's own
        complex, model and dt, so the report is identical either way.  A failed
        check is reported, never raised.
        """
        checks = [
            _check_stiffness_nullspace_and_node_power(),
            _check_reversed_momentum(),
            _check_hamiltonian_gradient_specialization(),
            _check_kdk_energy_convergence(),
            _check_epsilon_mode_frequency(),
        ]
        return {
            "schema": SELF_CHECK_SCHEMA,
            "checks": checks,
            "ok": bool(all(check["ok"] for check in checks)),
            "fixture": _fixture_description(),
        }


# --------------------------------------------------------------------------- #
# scenarios (deterministic, no RNG)
# --------------------------------------------------------------------------- #


def resting(complex: CellComplex) -> State:
    """All-zero state on ``complex``."""
    if not isinstance(complex, CellComplex):
        raise OracleError(f"complex must be a CellComplex, got {type(complex).__name__}")
    empty = np.zeros(complex.node_count, dtype=float)
    return State(psi_y=empty.copy(), psi_i=empty.copy(), p_y=empty.copy(), p_i=empty.copy())


def counterflow_packet(
    complex: CellComplex,
    model: Model,
    *,
    amplitude: float = 1.0,
    width: float = 2.0,
    center: float | None = None,
    speed: float | None = None,
) -> State:
    """Two counter-directed Gaussian packets with ``eps ≡ 0`` identically.

    Exact profile (index axis ``x_i = i``, bump centres ``center -/+ 2*width``
    with directions ``+1`` and ``-1``)::

        g_b(x) = amplitude * exp(-(x - c_b)^2 / (2 width^2))
        psi_Y  = g_plus + g_minus
        psi_I  = psi_Y / phi
        rate_Y = speed * sum_b d_b * (x - c_b) / width^2 * g_b(x)
        rate_I = rate_Y / phi
        P_s    = inertia_s * V * rate_s

    Fields and canonical rates add over the two centres, so the net momentum
    cancels while both transport directions fire.  ``psi_Y = phi psi_I`` and
    ``psi_dot_Y = phi psi_dot_I`` hold pointwise, hence ``eps ≡ 0`` and
    ``eps_dot ≡ 0`` are preserved by both candidate models: this fixture cannot
    discriminate them.
    """
    if not isinstance(complex, CellComplex):
        raise OracleError(f"complex must be a CellComplex, got {type(complex).__name__}")
    if not isinstance(model, Model):
        raise OracleError(f"model must be a Model, got {type(model).__name__}")
    amp = _as_float(amplitude, "amplitude")
    width_value = _as_float(width, "width")
    if width_value <= 0.0:
        raise OracleError(f"width must be positive, got {width_value!r}")
    center_value = (complex.node_count - 1) / 2.0 if center is None else _as_float(center, "center")
    speed_value = math.sqrt(float(model.c_f2)) if speed is None else _as_float(speed, "speed")

    x = _index_coordinates(complex)
    phi = float(model.phi)
    offset = 2.0 * width_value
    field = np.zeros(complex.node_count, dtype=float)
    rate = np.zeros(complex.node_count, dtype=float)
    for direction, centre in ((1.0, center_value - offset), (-1.0, center_value + offset)):
        bump = amp * _gaussian(x, centre, width_value)
        field += bump
        rate += direction * speed_value * ((x - centre) / (width_value * width_value)) * bump
    inertia = model.inertia()
    volumes = np.asarray(complex.volumes, dtype=float)
    p_y, p_i = _momentum_from_rates(volumes, inertia, rate, rate / phi)
    return State(psi_y=field, psi_i=field / phi, p_y=p_y, p_i=p_i)


def epsilon_mode(
    complex: CellComplex,
    model: Model,
    *,
    amplitude: float = 1.0,
    width: float | None = None,
    center: float | None = None,
) -> State:
    """A rest-prepared excitation carrying ``eps != 0``.

    Exact profile (index axis ``x_i = i``)::

        f(x)   = amplitude * exp(-(x - center)^2 / (2 width^2))     (uniform when width is None)
        psi_Y  = +f
        psi_I  = -f / phi
        eps    = 2 f                                                 (pointwise)
        P_Y = P_I = 0

    ``width=None`` gives ``f ≡ amplitude``: the uniform single-mode conversion
    excitation whose frequency the two candidate models predict differently
    (``sqrt((1 + phi) omega2)`` against ``sqrt((1 + phi²) omega2)``).
    """
    if not isinstance(complex, CellComplex):
        raise OracleError(f"complex must be a CellComplex, got {type(complex).__name__}")
    if not isinstance(model, Model):
        raise OracleError(f"model must be a Model, got {type(model).__name__}")
    amp = _as_float(amplitude, "amplitude")
    phi = float(model.phi)
    x = _index_coordinates(complex)
    if width is None:
        profile = np.full(complex.node_count, amp, dtype=float)
    else:
        width_value = _as_float(width, "width")
        if width_value <= 0.0:
            raise OracleError(f"width must be positive, got {width_value!r}")
        center_value = (
            (complex.node_count - 1) / 2.0 if center is None else _as_float(center, "center")
        )
        profile = amp * _gaussian(x, center_value, width_value)
    zeros = np.zeros(complex.node_count, dtype=float)
    return State(psi_y=profile, psi_i=-profile / phi, p_y=zeros.copy(), p_i=zeros.copy())


# --------------------------------------------------------------------------- #
# self-check fixture and checks
# --------------------------------------------------------------------------- #


def _fixture_complex() -> CellComplex:
    return CellComplex(volumes=_FIXTURE_VOLUMES, edges=_FIXTURE_EDGES)


def _fixture_model(*, yin: str = "phi") -> Model:
    return Model(c_f2=_FIXTURE_C_F2, omega2=_FIXTURE_OMEGA2, mu=_FIXTURE_MU, phi=PHI, yin=yin)


def _fixture_state() -> State:
    return State(
        psi_y=np.array(_FIXTURE_PSI_Y, dtype=float),
        psi_i=np.array(_FIXTURE_PSI_I, dtype=float),
        p_y=np.array(_FIXTURE_P_Y, dtype=float),
        p_i=np.array(_FIXTURE_P_I, dtype=float),
    )


def _fixture_description() -> dict:
    complex_ = _fixture_complex()
    native = _fixture_model()
    equal = _fixture_model(yin="equal")
    return {
        "model_id": MODEL_ID,
        "complex": complex_.as_dict(),
        "model": native.as_dict(),
        "control_model": equal.as_dict(),
        "dt": _FIXTURE_DT,
        "state": {
            "psi_y": [float(value) for value in _FIXTURE_PSI_Y],
            "psi_i": [float(value) for value in _FIXTURE_PSI_I],
            "p_y": [float(value) for value in _FIXTURE_P_Y],
            "p_i": [float(value) for value in _FIXTURE_P_I],
        },
        "kdk_refinement": {
            "node_count": _KDK_CHAIN_NODES,
            "spacing": _KDK_CHAIN_SPACING,
            "horizon": _KDK_HORIZON,
            "dt_levels": [float(dt) for dt in _KDK_DT_LEVELS],
        },
        "epsilon_mode": {
            "amplitude": _EPS_MODE_AMPLITUDE,
            "width": None,
            "dt": _EPS_MODE_DT,
            "steps": _EPS_MODE_STEPS,
            "horizon": _EPS_MODE_DT * _EPS_MODE_STEPS,
        },
        "node_coordinate": "node index x_i = i (affine image of the engine's (i + 0.5) * spacing)",
        "numpy_version": np.__version__,
        "python_version": platform.python_version(),
    }


def _check_stiffness_nullspace_and_node_power() -> dict:
    """K @ 1 = 0, and node powers cancel while edge powers need not be zero."""
    complex_ = _fixture_complex()
    model = _fixture_model()
    oracle = NativeFieldOracle(complex_, model, _FIXTURE_DT)
    node_count = complex_.node_count
    volumes = np.asarray(complex_.volumes, dtype=float)
    inertia = model.inertia()

    stiffness = complex_.stiffness()
    residual = stiffness @ np.ones(node_count)
    row_scale = float(np.max(np.sum(np.abs(stiffness), axis=1)))
    null_max_abs = float(np.max(np.abs(residual)))
    null_relative = _relative_max(null_max_abs, row_scale)

    # Uniform oscillation: both the field and the rate are uniform per channel.
    x = _index_coordinates(complex_)
    uniform_psi_y = np.full(node_count, 0.3)
    uniform_psi_i = np.full(node_count, -0.2)
    uniform_rate_y = np.full(node_count, 0.17)
    uniform_rate_i = np.full(node_count, -0.09)
    p_y, p_i = _momentum_from_rates(volumes, inertia, uniform_rate_y, uniform_rate_i)
    uniform = State(psi_y=uniform_psi_y, psi_i=uniform_psi_i, p_y=p_y, p_i=p_i)
    uniform_edge = np.concatenate(
        [oracle.edge_power(uniform, "yang"), oracle.edge_power(uniform, "yin")]
    )
    uniform_node = np.concatenate(
        [oracle.node_power(uniform, "yang"), oracle.node_power(uniform, "yin")]
    )

    # In-phase rate field on a non-uniform state: edge powers are nonzero and
    # node powers still cancel exactly.
    base = _fixture_state()
    in_phase_rate_y = np.full(node_count, 0.23)
    in_phase_rate_i = np.full(node_count, -0.14)
    p_y, p_i = _momentum_from_rates(volumes, inertia, in_phase_rate_y, in_phase_rate_i)
    in_phase = State(psi_y=base.psi_y, psi_i=base.psi_i, p_y=p_y, p_i=p_i)
    in_phase_edge_y = oracle.edge_power(in_phase, "yang")
    in_phase_edge_i = oracle.edge_power(in_phase, "yin")
    in_phase_node_y = oracle.node_power(in_phase, "yang")
    in_phase_node_i = oracle.node_power(in_phase, "yin")
    edge_scale = float(
        max(np.max(np.abs(in_phase_edge_y)), np.max(np.abs(in_phase_edge_i)))
    )
    sum_abs = float(abs(in_phase_node_y.sum()) + abs(in_phase_node_i.sum()))
    sum_relative = _relative_max(sum_abs, edge_scale)

    # Firing control: with a non-uniform rate field the node powers are nonzero,
    # so the zero above is a property of the state and not a dead code path.
    firing = _fixture_state()
    firing_node = np.concatenate(
        [oracle.node_power(firing, "yang"), oracle.node_power(firing, "yin")]
    )
    firing_max = float(np.max(np.abs(firing_node)))

    numbers = {
        "node_count": node_count,
        "edge_count": complex_.edge_count,
        "stiffness_null_max_abs": null_max_abs,
        "stiffness_row_abs_sum_max": row_scale,
        "stiffness_null_relative": null_relative,
        "uniform_edge_power_max_abs": float(np.max(np.abs(uniform_edge))),
        "uniform_edge_power_nonzero_entries": int(np.count_nonzero(uniform_edge)),
        "uniform_edge_power_attempted": int(uniform_edge.size),
        "uniform_node_power_max_abs": float(np.max(np.abs(uniform_node))),
        "uniform_node_power_attempted": int(uniform_node.size),
        "uniform_node_power_relative": _relative_max(
            float(np.max(np.abs(uniform_node))), max(edge_scale, 1e-300)
        ),
        "in_phase_rate_edge_power_max_abs": edge_scale,
        "in_phase_rate_edge_power_nonzero_entries": int(
            np.count_nonzero(np.concatenate([in_phase_edge_y, in_phase_edge_i]))
        ),
        "in_phase_rate_edge_power_attempted": int(in_phase_edge_y.size + in_phase_edge_i.size),
        "in_phase_rate_node_power_sum_abs": sum_abs,
        "in_phase_rate_node_power_sum_relative": sum_relative,
        "in_phase_rate_node_power_sum_attempted": int(in_phase_node_y.size + in_phase_node_i.size),
        "in_phase_rate_max_node_power_abs": float(
            max(np.max(np.abs(in_phase_node_y)), np.max(np.abs(in_phase_node_i)))
        ),
        "firing_node_power_max_abs": firing_max,
        "firing_node_power_attempted": int(firing_node.size),
        "tolerance_relative": _TOL_STIFFNESS_NULL,
    }
    ok = bool(
        null_relative <= _TOL_STIFFNESS_NULL
        and float(np.max(np.abs(uniform_edge))) == 0.0
        and float(np.max(np.abs(uniform_node))) == 0.0
        and sum_relative <= _TOL_POWER_IDENTITY
        and edge_scale > 0.0
        and firing_max > 0.0
    )
    detail = (
        "K @ 1 = 0 to {rel:.3e} relative; a uniform oscillation carries exactly zero edge and "
        "node power ({attempted} node and {edge_attempted} edge comparisons); an in-phase rate "
        "field carries nonzero edge power that cancels exactly at the nodes "
        "(sum relative {sum_rel:.3e}); a fully non-uniform state fires with max node power "
        "{fire:.6e}, so the zeros are not a dead path."
    ).format(
        rel=null_relative,
        attempted=numbers["uniform_node_power_attempted"],
        edge_attempted=numbers["uniform_edge_power_attempted"],
        sum_rel=sum_relative,
        fire=firing_max,
    )
    return {"name": "stiffness_nullspace_and_node_power_cancellation", "ok": ok, "detail": detail, "numbers": numbers}


def _check_reversed_momentum() -> dict:
    """Reversed canonical momenta preserve H and negate every edge power."""
    complex_ = _fixture_complex()
    model = _fixture_model()
    oracle = NativeFieldOracle(complex_, model, _FIXTURE_DT)
    state = _fixture_state()
    reversed_state = State(
        psi_y=state.psi_y.copy(),
        psi_i=state.psi_i.copy(),
        p_y=-state.p_y,
        p_i=-state.p_i,
    )

    energy = oracle.hamiltonian(state)
    reversed_energy = oracle.hamiltonian(reversed_state)
    energy_difference = abs(reversed_energy - energy)

    edge_y = oracle.edge_power(state, "yang")
    edge_i = oracle.edge_power(state, "yin")
    reversed_edge_y = oracle.edge_power(reversed_state, "yang")
    reversed_edge_i = oracle.edge_power(reversed_state, "yin")
    power_scale = float(max(np.max(np.abs(edge_y)), np.max(np.abs(edge_i))))
    edge_difference = float(
        max(np.max(np.abs(reversed_edge_y + edge_y)), np.max(np.abs(reversed_edge_i + edge_i)))
    )

    node_y = oracle.node_power(state, "yang")
    node_i = oracle.node_power(state, "yin")
    reversed_node_y = oracle.node_power(reversed_state, "yang")
    reversed_node_i = oracle.node_power(reversed_state, "yin")
    node_difference = float(
        max(np.max(np.abs(reversed_node_y + node_y)), np.max(np.abs(reversed_node_i + node_i)))
    )

    numbers = {
        "energy": energy,
        "energy_reversed": reversed_energy,
        "energy_max_abs_change": energy_difference,
        "energy_relative_change": _relative_max(energy_difference, abs(energy)),
        "energy_attempted": 1,
        "edge_power_scale": power_scale,
        "edge_power_nonzero_entries": int(np.count_nonzero(edge_y) + np.count_nonzero(edge_i)),
        "edge_power_negation_max_abs": edge_difference,
        "edge_power_negation_relative": _relative_max(edge_difference, power_scale),
        "edge_power_attempted": int(edge_y.size + edge_i.size),
        "node_power_negation_max_abs": node_difference,
        "node_power_negation_relative": _relative_max(
            node_difference, max(float(max(np.max(np.abs(node_y)), np.max(np.abs(node_i)))), 1e-300)
        ),
        "node_power_attempted": int(node_y.size + node_i.size),
        "tolerance_relative": _TOL_POWER_IDENTITY,
    }
    ok = bool(
        numbers["energy_relative_change"] <= _TOL_POWER_IDENTITY
        and numbers["edge_power_negation_relative"] <= _TOL_POWER_IDENTITY
        and power_scale > 0.0
        and numbers["edge_power_nonzero_entries"] > 0
    )
    detail = (
        "H is unchanged to {e:.3e} relative ({attempted} energy comparison); all {edges} edge "
        "powers over both channels are negated to {p:.3e} relative with {nonzero} of them "
        "nonzero, so the identity is exercised on a live power field."
    ).format(
        e=numbers["energy_relative_change"],
        attempted=numbers["energy_attempted"],
        edges=numbers["edge_power_attempted"],
        p=numbers["edge_power_negation_relative"],
        nonzero=numbers["edge_power_nonzero_entries"],
    )
    return {"name": "reversed_momentum_energy_and_edge_power", "ok": ok, "detail": detail, "numbers": numbers}


def _finite_difference_gradient(oracle: NativeFieldOracle, state: State) -> tuple[np.ndarray, np.ndarray]:
    """``dH/dpsi`` per channel by central differences on the oracle's own H_F."""
    node_count = oracle.complex.node_count
    psi_y, psi_i, p_y, p_i = oracle._components(state)
    gradients = [np.empty(node_count), np.empty(node_count)]
    for channel, values in enumerate((psi_y, psi_i)):
        step = 1e-5 * max(1.0, float(np.max(np.abs(values))))
        for node in range(node_count):
            plus = values.copy()
            minus = values.copy()
            plus[node] += step
            minus[node] -= step
            if channel == 0:
                high = State(psi_y=plus, psi_i=psi_i, p_y=p_y, p_i=p_i)
                low = State(psi_y=minus, psi_i=psi_i, p_y=p_y, p_i=p_i)
            else:
                high = State(psi_y=psi_y, psi_i=plus, p_y=p_y, p_i=p_i)
                low = State(psi_y=psi_y, psi_i=minus, p_y=p_y, p_i=p_i)
            gradients[channel][node] = (oracle.hamiltonian(high) - oracle.hamiltonian(low)) / (
                2.0 * step
            )
    return gradients[0], gradients[1]


def _finite_difference_momentum_gradient(
    oracle: NativeFieldOracle, state: State
) -> tuple[np.ndarray, np.ndarray]:
    """``dH/dP`` per channel by central differences on the oracle's own H_F."""
    node_count = oracle.complex.node_count
    psi_y, psi_i, p_y, p_i = oracle._components(state)
    gradients = [np.empty(node_count), np.empty(node_count)]
    for channel, values in enumerate((p_y, p_i)):
        step = 1e-5 * max(1.0, float(np.max(np.abs(values))))
        for node in range(node_count):
            plus = values.copy()
            minus = values.copy()
            plus[node] += step
            minus[node] -= step
            if channel == 0:
                high = State(psi_y=psi_y, psi_i=psi_i, p_y=plus, p_i=p_i)
                low = State(psi_y=psi_y, psi_i=psi_i, p_y=minus, p_i=p_i)
            else:
                high = State(psi_y=psi_y, psi_i=psi_i, p_y=p_y, p_i=plus)
                low = State(psi_y=psi_y, psi_i=psi_i, p_y=p_y, p_i=minus)
            gradients[channel][node] = (oracle.hamiltonian(high) - oracle.hamiltonian(low)) / (
                2.0 * step
            )
    return gradients[0], gradients[1]


def _check_hamiltonian_gradient_specialization() -> dict:
    """The native H_F specializes to the declared equations; the equal model cannot."""
    complex_ = _fixture_complex()
    native = NativeFieldOracle(complex_, _fixture_model(), _FIXTURE_DT)
    equal_model = _fixture_model(yin="equal")
    equal = NativeFieldOracle(complex_, equal_model, _FIXTURE_DT)
    state = _fixture_state()
    volumes = np.asarray(complex_.volumes, dtype=float)

    gradient_y, gradient_i = _finite_difference_gradient(native, state)
    momentum_gradient_y, momentum_gradient_i = _finite_difference_momentum_gradient(native, state)

    native_inertia = native.model.inertia()
    equal_inertia = equal_model.inertia()
    declared_rates_y, declared_rates_i = native.rates(state)
    declared_accel_y, declared_accel_i = native.accelerations(state)
    equal_rates_y, equal_rates_i = equal.rates(state)
    equal_accel_y, equal_accel_i = equal.accelerations(state)

    # Native specialization: -dH/dpsi / (inertia M) reproduces the declared accelerations,
    # and dH/dP reproduces the declared rates.
    native_accel_y = -gradient_y / (native_inertia[0] * volumes)
    native_accel_i = -gradient_i / (native_inertia[1] * volumes)
    native_rates = _summary(
        np.concatenate(
            [
                np.concatenate([native_accel_y - declared_accel_y, native_accel_i - declared_accel_i]),
                np.concatenate(
                    [momentum_gradient_y - declared_rates_y, momentum_gradient_i - declared_rates_i]
                ),
            ]
        ),
        np.concatenate(
            [
                np.concatenate([declared_accel_y, declared_accel_i]),
                np.concatenate([declared_rates_y, declared_rates_i]),
            ]
        ),
    )

    # Control that must fail: the same specialization applied to the equal model
    # (its own inertia and its own rate map) against the native H_F.
    control_accel_y = -gradient_y / (equal_inertia[0] * volumes)
    control_accel_i = -gradient_i / (equal_inertia[1] * volumes)
    equal_acceleration_map = _summary(
        np.concatenate(
            [control_accel_y - equal_accel_y, control_accel_i - equal_accel_i]
        ),
        np.concatenate([equal_accel_y, equal_accel_i]),
    )
    equal_rate_map = _summary(
        np.concatenate([momentum_gradient_y - equal_rates_y, momentum_gradient_i - equal_rates_i]),
        np.concatenate([equal_rates_y, equal_rates_i]),
    )

    numbers = {
        "native_rates_and_accelerations": native_rates,
        "native_acceleration_relative": native_rates["relative"],
        "native_attempted": native_rates["attempted"],
        "equal_model_acceleration_mismatch": equal_acceleration_map,
        "equal_model_acceleration_mismatch_relative": equal_acceleration_map["relative"],
        "equal_model_rates_mismatch": equal_rate_map,
        "equal_model_rates_mismatch_relative": equal_rate_map["relative"],
        "equal_model_attempted": equal_acceleration_map["attempted"],
        "control_accel_y_abs_max": float(np.max(np.abs(control_accel_y))),
        "control_accel_i_abs_max": float(np.max(np.abs(control_accel_i))),
        "declared_equal_accel_y_abs_max": float(np.max(np.abs(equal_accel_y))),
        "declared_equal_accel_i_abs_max": float(np.max(np.abs(equal_accel_i))),
        "declared_native_accel_y_abs_max": float(np.max(np.abs(native_accel_y))),
        "declared_native_accel_i_abs_max": float(np.max(np.abs(native_accel_i))),
        "control_yin_mismatch_over_native_yin": float(
            float(np.max(np.abs(control_accel_i - equal_accel_i)))
            / max(float(np.max(np.abs(equal_accel_i))), 1e-300)
        ),
        "tolerance_match_relative": _TOL_GRADIENT_MATCH,
        "control_min_mismatch_relative": _CONTROL_MIN_MISMATCH,
    }
    ok = bool(
        native_rates["relative"] <= _TOL_GRADIENT_MATCH
        and equal_acceleration_map["relative"] > _CONTROL_MIN_MISMATCH
    )
    detail = (
        "Finite-difference gradients of the native H_F reproduce the declared rates and "
        "accelerations to {native:.3e} relative over {attempted} components; the yin='equal' "
        "control against the same H_F mismatches by {control:.3e} (must exceed {floor:.0e}), "
        "localized in the Yin channel where the conversion gain carries an extra phi."
    ).format(
        native=native_rates["relative"],
        attempted=native_rates["attempted"],
        control=equal_acceleration_map["relative"],
        floor=_CONTROL_MIN_MISMATCH,
    )
    return {"name": "hamiltonian_gradient_specialization", "ok": ok, "detail": detail, "numbers": numbers}


def _check_kdk_energy_convergence() -> dict:
    """KDK energy drift shrinks with the fitted order 2 over the dt refinements."""
    complex_ = CellComplex.chain(_KDK_CHAIN_NODES, spacing=_KDK_CHAIN_SPACING)
    model = _fixture_model()
    node_count = complex_.node_count
    x = np.arange(node_count, dtype=float)
    psi_y = 0.4 * np.cos(math.pi * x / node_count) + 0.25 * np.sin(2.0 * math.pi * x / node_count)
    psi_i = (0.4 / PHI) * np.cos(math.pi * x / node_count) - 0.2 * np.sin(
        3.0 * math.pi * x / node_count
    )
    initial = State(psi_y=psi_y, psi_i=psi_i, p_y=np.zeros(node_count), p_i=np.zeros(node_count))

    levels = []
    for dt in _KDK_DT_LEVELS:
        steps = int(round(_KDK_HORIZON / dt))
        oracle = NativeFieldOracle(complex_, model, dt)
        energy_0 = oracle.hamiltonian(initial)
        current = initial
        worst = 0.0
        for _ in range(steps):
            current = oracle.step(current)
            worst = max(worst, abs(oracle.hamiltonian(current) - energy_0) / abs(energy_0))
        levels.append(
            {
                "dt": float(dt),
                "steps": int(steps),
                "max_energy_error_relative": worst,
                "best_energy_error_relative": float(abs(oracle.hamiltonian(current) - energy_0) / abs(energy_0)),
            }
        )

    errors = [level["max_energy_error_relative"] for level in levels]
    dts = [level["dt"] for level in levels]
    refinement_orders = [
        math.log2(errors[index] / errors[index + 1]) for index in range(len(errors) - 1)
    ]
    log_dt = np.log(np.asarray(dts, dtype=float))
    log_error = np.log(np.asarray(errors, dtype=float))
    centered_dt = log_dt - float(np.mean(log_dt))
    centered_error = log_error - float(np.mean(log_error))
    denominator = float(centered_dt @ centered_dt)
    fitted_order = float((centered_dt @ centered_error) / denominator) if denominator > 0.0 else 0.0

    per_step_drift = max(
        level["max_energy_error_relative"] / level["steps"] for level in levels
    )
    omega_estimate = math.sqrt(
        float(model.c_f2) * _max_rate_eigenvalue(complex_) + (1.0 + PHI) * float(model.omega2)
    )

    numbers = {
        "horizon": _KDK_HORIZON,
        "dt_levels": dts,
        "steps": [level["steps"] for level in levels],
        "max_energy_error_relative": errors,
        "best_step_energy_error_relative": [level["best_energy_error_relative"] for level in levels],
        "refinement_orders": refinement_orders,
        "refinements_attempted": len(refinement_orders),
        "fitted_order_least_squares": fitted_order,
        "fitted_order_mean_ratio": float(np.mean(refinement_orders)) if refinement_orders else 0.0,
        "order_target": _ORDER_TARGET,
        "order_tolerance": _ORDER_TOLERANCE,
        "energy_error_floor_relative": float(min(errors)) if errors else 0.0,
        "measurement_above_roundoff": bool(min(errors) > 1e-13) if errors else False,
        "per_step_drift_max": per_step_drift,
        "per_step_drift_bound": _PER_STEP_DRIFT_BOUND,
        "coarsest_omega_dt": omega_estimate * float(_KDK_DT_LEVELS[0]),
        "max_rate_estimate": omega_estimate,
        "fitted_order_attempted": len(refinement_orders),
    }
    measurable = bool(errors) and min(errors) > 0.0
    ok = bool(
        measurable
        and abs(fitted_order - _ORDER_TARGET) <= _ORDER_TOLERANCE
        and per_step_drift <= _PER_STEP_DRIFT_BOUND
    )
    if not measurable:
        detail = (
            "Refinement could not be measured: at least one level reports an exactly zero energy "
            "error (round-off floor), so no order is claimed."
        )
    else:
        detail = (
            "Over {attempted} refinements of dt ({levels}) the maximum relative energy error "
            "{errors} gives a least-squares fitted order {order:.4f} (mean ratio order {mean:.4f}) "
            "against the declared target 2; per-step drift stays at {drift:.3e} with the coarsest "
            "resolution omega*dt = {res:.4f}."
        ).format(
            attempted=len(refinement_orders),
            levels=", ".join(f"{dt:g}" for dt in dts),
            errors=", ".join(f"{error:.3e}" for error in errors),
            order=fitted_order,
            mean=numbers["fitted_order_mean_ratio"],
            drift=per_step_drift,
            res=numbers["coarsest_omega_dt"],
        )
    return {"name": "kdk_energy_convergence_order", "ok": ok, "detail": detail, "numbers": numbers}


def _check_epsilon_mode_frequency() -> dict:
    """Uniform conversion frequency against the closed forms, and their separation."""
    complex_ = _fixture_complex()
    volumes = np.asarray(complex_.volumes, dtype=float)
    results: dict[str, dict] = {}
    for label, yin in (("native", "phi"), ("equal", "equal")):
        model = _fixture_model(yin=yin)
        oracle = NativeFieldOracle(complex_, model, _EPS_MODE_DT)
        state = epsilon_mode(complex_, model, amplitude=_EPS_MODE_AMPLITUDE, width=None)
        times = np.empty(_EPS_MODE_STEPS + 1)
        epsilon_series = np.empty(_EPS_MODE_STEPS + 1)
        energy_series = np.empty(_EPS_MODE_STEPS + 1)
        uniformity = 0.0
        current = state
        time = 0.0
        for index in range(_EPS_MODE_STEPS + 1):
            epsilon = oracle.epsilon(current)
            times[index] = time
            epsilon_series[index] = float(epsilon[0])
            energy_series[index] = float(np.sum(volumes * epsilon * epsilon))
            uniformity = max(uniformity, float(np.max(np.abs(epsilon - epsilon[0]))))
            if index == _EPS_MODE_STEPS:
                break
            current = oracle.step(current)
            time += _EPS_MODE_DT

        closed_form = math.sqrt((1.0 + float(model.phi)) * float(model.omega2)) if yin == "phi" else math.sqrt(
            (1.0 + float(model.phi) ** 2) * float(model.omega2)
        )
        crossing = _first_zero_crossing(times, epsilon_series)
        if crossing is None or crossing <= 0.0:
            results[label] = {
                "closed_form_omega": closed_form,
                "zero_crossing_found": False,
            }
            continue
        bracket_guess = math.pi / (2.0 * crossing)
        fit = _fit_frequency(times, epsilon_series, bracket_guess)
        doubled_fit = _fit_frequency(times, energy_series, 2.0 * fit["omega"])
        results[label] = {
            "closed_form_omega": closed_form,
            "zero_crossing_time": float(crossing),
            "zero_crossing_omega_guess": float(bracket_guess),
            "zero_crossing_found": True,
            "omega_fitted": float(fit["omega"]),
            "omega_relative_error": _relative_max(abs(fit["omega"] - closed_form), closed_form),
            "fit_residual_relative": float(fit["residual_relative"]),
            "fit_amplitude": float(fit["amplitude"]),
            "fit_offset": float(fit["offset"]),
            "samples": int(fit["samples"]),
            "epsilon_energy_frequency": float(doubled_fit["omega"]),
            "epsilon_energy_frequency_ratio": float(doubled_fit["omega"]) / float(fit["omega"]),
            "epsilon_energy_fit_residual_relative": float(doubled_fit["residual_relative"]),
            "initial_epsilon_amplitude": float(epsilon_series[0]),
            "uniformity_max_deviation": uniformity,
        }

    native = results.get("native", {})
    equal = results.get("equal", {})
    complete = bool(native.get("zero_crossing_found") and equal.get("zero_crossing_found"))
    if complete:
        separation = abs(native["omega_fitted"] - equal["omega_fitted"]) / native["omega_fitted"]
        prediction_ratio = equal["closed_form_omega"] / native["closed_form_omega"]
        measurement_ratio = equal["omega_fitted"] / native["omega_fitted"]
    else:
        separation = 0.0
        prediction_ratio = 0.0
        measurement_ratio = 0.0

    numbers = {
        "native": native,
        "equal": equal,
        "closed_form_prediction_ratio": prediction_ratio,
        "measured_frequency_ratio": measurement_ratio,
        "separation_relative": separation,
        "separation_min": _MIN_FREQUENCY_SEPARATION,
        "frequency_tolerance_relative": _TOL_FREQUENCY,
        "samples_per_model": _EPS_MODE_STEPS + 1,
        "dt": _EPS_MODE_DT,
        "amplitude": _EPS_MODE_AMPLITUDE,
    }
    ok = bool(
        complete
        and native["omega_relative_error"] <= _TOL_FREQUENCY
        and equal["omega_relative_error"] <= _TOL_FREQUENCY
        and native["fit_residual_relative"] <= _MAX_FIT_RESIDUAL
        and equal["fit_residual_relative"] <= _MAX_FIT_RESIDUAL
        and abs(native["epsilon_energy_frequency_ratio"] - 2.0) <= _TOL_EPS2_RATIO
        and abs(equal["epsilon_energy_frequency_ratio"] - 2.0) <= _TOL_EPS2_RATIO
        and separation > _MIN_FREQUENCY_SEPARATION
    )
    if not complete:
        detail = (
            "The uniform conversion oscillation did not complete: no positive-to-negative zero "
            "crossing of eps was found for both models, so no frequency is claimed."
        )
    else:
        detail = (
            "Uniform eps mode: native omega {native_measured:.9f} against the closed form "
            "{native_closed:.9f} ({native_error:.3e} relative), yin='equal' omega "
            "{equal_measured:.9f} against {equal_closed:.9f} ({equal_error:.3e} relative); the two "
            "closed forms separate by {separation:.4f} relative (must exceed {floor:g}). Each fit "
            "is a single-frequency cosine fit with relative residual {res:.2e} over {samples} "
            "samples; the sum V eps^2 series oscillates at exactly twice the eps frequency "
            "(measured ratios {ratio_native:.6f} native, {ratio_equal:.6f} equal), so the "
            "eps^2 spectrum must be halved before it is compared with the closed form."
        ).format(
            native_measured=native["omega_fitted"],
            native_closed=native["closed_form_omega"],
            native_error=native["omega_relative_error"],
            equal_measured=equal["omega_fitted"],
            equal_closed=equal["closed_form_omega"],
            equal_error=equal["omega_relative_error"],
            separation=separation,
            floor=_MIN_FREQUENCY_SEPARATION,
            res=max(native["fit_residual_relative"], equal["fit_residual_relative"]),
            samples=numbers["samples_per_model"],
            ratio_native=native["epsilon_energy_frequency_ratio"],
            ratio_equal=equal["epsilon_energy_frequency_ratio"],
        )
    return {"name": "epsilon_mode_conversion_frequency", "ok": ok, "detail": detail, "numbers": numbers}


if __name__ == "__main__":
    _report = NativeFieldOracle.self_check()
    print(json.dumps(_report, indent=2))
    raise SystemExit(0 if _report["ok"] else 1)
