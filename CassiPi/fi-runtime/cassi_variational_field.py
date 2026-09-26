r"""A common finite-dimensional potential for field learning and inference.

This post-prototype operator does not modify or impersonate the paper runtime,
W3 dynamics, or their checkpoint formats. It consumes the same raw tensor shape
as QiFieldState.field, [S, 9*M, 1], with an explicitly different interpretation.
All adaptive memory AND provisional workspace live in that tensor. Geometry,
factor scopes and coordinate transforms are fixed. There is no learned codec,
external weight matrix, persistent factorization, or model fallback.

For factor f, P_f selects a fixed subset of workspace coordinates z. Its memory
is an SPD block Sigma_f. With lambda > 0 and k_f = len(scope_f), define

    F(Sigma,z) = 1/2 sum_f [log det(Sigma_f/lambda I)
                 + lambda tr(Sigma_f^-1) - k_f
                 + (P_f z)^T Sigma_f^-1 (P_f z)].

These are dimensionless model quantities, not physical energy or probabilities.

Learning: with an actual local observation x held fixed, Q=x x^T+lambda I.
Under g_S(U,V)=1/2 tr(S^-1 U S^-1 V), grad_g F=S-Q. Thus the exact
negative-gradient flow is S(t)=exp(-t)S(0)+(1-exp(-t))Q and

    dF/dt = -1/2 ||S^-1/2 (S-Q) S^-1/2||_F^2 <= 0.

If ||x||<=R and lambda I<=S(0)<=(lambda+R^2)I, those SPD bounds persist.
This is a covariance convex combination; F is not generally Euclidean convex
in S. Learning changes only the admitted factor. Fixed exposure gives explicit
exponential forgetting; it does not promise unlimited or interference-free
retention. Changing observed coordinates supplies boundary work before descent.

Inference: hold memories fixed and clamp observed coordinates. The same F has
H=sum_f P_f^T Sigma_f^-1 P_f. Complete scope coverage makes H positive definite.
For free coordinates U and observed O, implicit Euler is

    z_U' = (I+h H_UU)^-1 (z_U-h H_UO z_O), h>0.

At fixed clamps, with delta=z_U'-z_U,

    F(z)-F(z') = ||delta||^2/h + delta^T H_UU delta/2 >= 0.

The conditional minimum is -H_UU^-1 H_UO z_O. With incidence counts d_j,
d_min/(lambda+R^2) I <= H <= d_max/lambda I. A joint [u,v] factor gives
v*=Sigma_vu Sigma_uu^-1 u and the reverse conditional from the SAME memory;
several overlapping factors share one global inference objective.
With m_U=lambda_min(H_UU), the free gradient contracts by at most
(1+h*m_U)^-1 per step. A fixed number of steps need not settle weakly
constrained or contradictory observations; use the free-gradient residual
or its derived contraction bound as the numerical stopping criterion.

Robust linear readout: with frozen memory, conditioning is z*(b)=J b,
where J_O=I and J_U=-H_UU^-1 H_UO (columns use the observed-coordinate order).
For a FIXED linear readout A, winner i and competitor j have nominal gap
m_ij=(A_i-A_j)z* and observation sensitivity g_ij=(A_i-A_j)J. Cauchy-Schwarz
gives the exact real-arithmetic ball minimum

    min_{||delta_b||<=r} [m_ij+g_ij delta_b] = m_ij-r||g_ij||.

Every margin must be strictly positive for a unique robust winner. For g!=0,
the bound is attained by delta_b=-r*g/||g||. Ties are not certified. The
declared error ball must remain inside the admitted observation domain.
Float64 evaluation uses scaled scores and boundary guards; it is not a formal
interval-arithmetic proof. Uncertainty in Sigma, the readout, the observation
model or the external world's response is outside this conditional claim.

Storage: use the unnormalized common coordinate C=phi*Y+I for REAL memory,
and the IMAGINARY differential D=Y-phi*I for workspace. The inverse is
Y=(D+phi*C)/(1+phi^2), I=(C-phi*D)/(1+phi^2). Real memory and imaginary
workspace use disjoint raw lanes; inference preserves the memory bytes exactly.
The unused components are zero. No post-update clipping is applied to SPD data.
Phi is a coordinate choice; no golden-ratio performance advantage is claimed.

Limits: covariance structure and fixed scopes are not autonomous concept or
particle formation. The unique conditional minimum is an estimate, not proof of
truth, evidence availability, permission, or calibrated uncertainty. Contradictory
relations can average to an unsupported zero. Only admitted observations may call
observe(); provisional completion must use relax() or condition(), which freeze
memory. certify_linear_action() reports conditional input robustness only; it
does not authorize an action or establish truth.

Related source mechanisms (read-only): prototype/cassi-technical-paper.md
sections 2-7; prototype/cassi_mnemic_condensation.py; the ridge moment laws in
prototype/cassi_bilateral_counterflow.py. Unlike their separate update families,
this operator implements the two block flows of the potential written above.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor

from cassi_field_regions import KernelResult

STATE_SCHEMA = "cassifi.variational-field.v1"


@dataclass(frozen=True)
class VariationalField:
    """Fixed factor geometry; instances contain no adaptive state."""

    dimension: int
    scopes: tuple[tuple[int, ...], ...]
    ridge: float = 1e-4
    observation_norm_bound: float = 4.0
    phi: float = (1.0 + math.sqrt(5.0)) / 2.0

    def __post_init__(self) -> None:
        if isinstance(self.dimension, bool) or not isinstance(self.dimension, int) or self.dimension < 1:
            raise ValueError("dimension must be a positive integer")
        scopes = tuple(tuple(scope) for scope in self.scopes)
        if not scopes:
            raise ValueError("at least one factor is required")
        covered: set[int] = set()
        for scope in scopes:
            if not scope or len(scope) != len(set(scope)):
                raise ValueError("each scope must be nonempty with unique coordinates")
            if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < self.dimension for i in scope):
                raise ValueError("scope coordinate is outside the workspace")
            covered.update(scope)
        if covered != set(range(self.dimension)):
            raise ValueError("every workspace coordinate must belong to a factor")
        for name in ("ridge", "observation_norm_bound", "phi"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        object.__setattr__(self, "scopes", scopes)

    @property
    def modes(self) -> int:
        return max(self.dimension, max(len(scope) ** 2 for scope in self.scopes))

    @property
    def shape(self) -> tuple[int, int, int]:
        return len(self.scopes), 9 * self.modes, 1

    def _parts(self, field: Tensor) -> Tensor:
        if not isinstance(field, Tensor) or tuple(field.shape) != self.shape:
            raise ValueError(f"field must have shape {self.shape}")
        if field.dtype != torch.float64 or field.requires_grad or not bool(torch.isfinite(field).all()):
            raise ValueError("field must be finite float64 without autograd state")
        return field.reshape(len(self.scopes), 9, self.modes)

    def _covariance(self, parts: Tensor, factor: int) -> Tensor:
        size = len(self.scopes[factor])
        return (self.phi * parts[factor, 0, :size * size] + parts[factor, 2, :size * size]).reshape(size, size)

    def _put_covariance(self, parts: Tensor, factor: int, covariance: Tensor) -> None:
        values = covariance.reshape(-1) / (1.0 + self.phi * self.phi)
        parts[factor, 0, :values.numel()] = self.phi * values
        parts[factor, 2, :values.numel()] = values

    def _workspace(self, parts: Tensor) -> Tensor:
        return parts[0, 1, :self.dimension] - self.phi * parts[0, 3, :self.dimension]

    def _put_workspace(self, parts: Tensor, workspace: Tensor) -> None:
        values = workspace / (1.0 + self.phi * self.phi)
        parts[0, 1, :self.dimension] = values
        parts[0, 3, :self.dimension] = -self.phi * values

    def validate(self, field: Tensor) -> None:
        parts = self._parts(field)
        if bool(torch.count_nonzero(parts[:, 0, :] - self.phi * parts[:, 2, :])):
            raise ValueError("real memory must occupy the common coordinate only")
        if bool(torch.count_nonzero(self.phi * parts[:, 1, :] + parts[:, 3, :])):
            raise ValueError("imaginary workspace must occupy the differential coordinate only")
        if bool(torch.count_nonzero(parts[:, 4:, :])):
            raise ValueError("unused velocity/statistic lanes must be zero")
        for factor, scope in enumerate(self.scopes):
            size = len(scope)
            if bool(torch.count_nonzero(parts[factor, (0, 2), size * size:])):
                raise ValueError("memory padding must be zero")
            start = self.dimension if factor == 0 else 0
            if bool(torch.count_nonzero(parts[factor, (1, 3), start:])):
                raise ValueError("workspace padding must be zero")
            covariance = self._covariance(parts, factor)
            if not torch.equal(covariance, covariance.T):
                raise ValueError("memory covariance must be symmetric")
            eigenvalues = torch.linalg.eigvalsh(covariance)
            upper = self.ridge + self.observation_norm_bound ** 2
            tolerance = 128 * torch.finfo(field.dtype).eps * size * max(1.0, upper)
            if float(eigenvalues.min()) < self.ridge - tolerance or float(eigenvalues.max()) > upper + tolerance:
                raise ValueError("memory covariance leaves its declared spectral bounds")
            if int(torch.linalg.cholesky_ex(covariance).info) != 0:
                raise ValueError("memory covariance must be positive definite")

    def initial_state(self, *, device: str | torch.device = "cpu") -> Tensor:
        field = torch.zeros(self.shape, dtype=torch.float64, device=device)
        parts = self._parts(field)
        for factor, scope in enumerate(self.scopes):
            self._put_covariance(parts, factor, self.ridge * torch.eye(len(scope), dtype=field.dtype, device=field.device))
        return field

    def covariance(self, field: Tensor, factor: int) -> Tensor:
        self.validate(field)
        if isinstance(factor, bool) or not isinstance(factor, int) or not 0 <= factor < len(self.scopes):
            raise ValueError("unknown factor")
        return self._covariance(self._parts(field), factor)

    def workspace(self, field: Tensor) -> Tensor:
        self.validate(field)
        return self._workspace(self._parts(field))

    def _observation(self, field: Tensor, indices: Sequence[int], values: Any) -> tuple[Tensor, Tensor]:
        indices = tuple(indices)
        if len(indices) != len(set(indices)) or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < self.dimension for i in indices):
            raise ValueError("observed coordinates must be unique and inside the workspace")
        value = torch.as_tensor(values, dtype=field.dtype, device=field.device)
        if tuple(value.shape) != (len(indices),) or value.requires_grad or not bool(torch.isfinite(value).all()):
            raise ValueError("observation must be a finite vector matching its coordinates")
        if float(torch.linalg.vector_norm(value)) > self.observation_norm_bound:
            raise ValueError("observation exceeds the declared norm bound")
        return torch.tensor(indices, dtype=torch.long, device=field.device), value

    def clamp(self, field: Tensor, indices: Sequence[int], values: Any) -> Tensor:
        """Supply workspace boundary data without teaching it as experience."""
        self.validate(field)
        index, value = self._observation(field, indices, values)
        candidate = field.clone()
        parts = self._parts(candidate)
        workspace = self._workspace(parts)
        workspace[index] = value
        self._put_workspace(parts, workspace)
        return candidate

    def observe(self, field: Tensor, factor: int, values: Any, *, exposure: float) -> Tensor:
        """Admit one fully observed local relation; other memories are untouched."""
        covariance = self.covariance(field, factor)
        if isinstance(exposure, bool) or not math.isfinite(exposure) or exposure <= 0:
            raise ValueError("exposure must be finite and positive")
        candidate = self.clamp(field, self.scopes[factor], values)
        parts = self._parts(candidate)
        observation = self._workspace(parts)[list(self.scopes[factor])]
        target = torch.outer(observation, observation) + self.ridge * torch.eye(len(observation), dtype=field.dtype, device=field.device)
        gain = -math.expm1(-exposure)
        self._put_covariance(parts, factor, (1.0 - gain) * covariance + gain * target)
        self.validate(candidate)
        return candidate

    def precision(self, field: Tensor) -> Tensor:
        """Derive the inference Hessian from the field; retain no solve cache."""
        self.validate(field)
        parts = self._parts(field)
        precision = field.new_zeros((self.dimension, self.dimension))
        for factor, scope in enumerate(self.scopes):
            index = torch.tensor(scope, dtype=torch.long, device=field.device)
            covariance = self._covariance(parts, factor)
            inverse = torch.cholesky_inverse(torch.linalg.cholesky(covariance))
            precision[index[:, None], index[None, :]] += inverse
        return precision

    def energy(self, field: Tensor) -> float:
        self.validate(field)
        parts = self._parts(field)
        workspace = self._workspace(parts)
        energy = field.new_zeros(())
        for factor, scope in enumerate(self.scopes):
            covariance = self._covariance(parts, factor)
            chol = torch.linalg.cholesky(covariance)
            inverse = torch.cholesky_inverse(chol)
            local = workspace[list(scope)]
            logdet = 2.0 * torch.log(chol.diagonal()).sum() - len(scope) * math.log(self.ridge)
            energy += 0.5 * (logdet + self.ridge * torch.trace(inverse) - len(scope) + local @ inverse @ local)
        return float(energy)

    def relax(self, field: Tensor, indices: Sequence[int], values: Any, *, duration: float) -> Tensor:
        """Implicit-Euler inference at fixed memory and observed coordinates."""
        if isinstance(duration, bool) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("duration must be finite and positive")
        precision = self.precision(field)
        candidate = self.clamp(field, indices, values)
        parts = self._parts(candidate)
        workspace = self._workspace(parts)
        observed = set(indices)
        free = torch.tensor([i for i in range(self.dimension) if i not in observed], dtype=torch.long, device=field.device)
        if free.numel():
            hessian = precision[free[:, None], free[None, :]]
            boundary = workspace.clone()
            boundary[free] = 0
            rhs = workspace[free] - duration * (precision @ boundary)[free]
            system = torch.eye(free.numel(), dtype=field.dtype, device=field.device) + duration * hessian
            workspace[free] = torch.linalg.solve(system, rhs)
            self._put_workspace(parts, workspace)
        return candidate

    def condition(self, field: Tensor, indices: Sequence[int], values: Any) -> tuple[Tensor, Tensor]:
        """Return the conditional field and its linear response to observations.

        Response columns follow the caller's index order. The response is
        derived from the current frozen memory and is never cached.
        """
        precision = self.precision(field)
        indices = tuple(indices)
        observed, observation = self._observation(field, indices, values)
        response = field.new_zeros((self.dimension, len(indices)))
        response[observed] = torch.eye(len(indices), dtype=field.dtype, device=field.device)
        observed_set = set(indices)
        free = torch.tensor([i for i in range(self.dimension) if i not in observed_set], dtype=torch.long, device=field.device)
        if free.numel() and observed.numel():
            response[free] = torch.linalg.solve(
                precision[free[:, None], free[None, :]],
                -precision[free[:, None], observed[None, :]],
            )
        candidate = field.clone()
        self._put_workspace(self._parts(candidate), response @ observation)
        self.validate(candidate)
        return candidate, response

    def certify_linear_action(
        self, field: Tensor, indices: Sequence[int], values: Any,
        readout: Any, *, radius: float,
    ) -> tuple[Tensor, dict[str, Any]]:
        """Certify a unique linear-score winner under bounded observation error.

        The field and readout are frozen. For each competing action, the exact
        real-arithmetic worst margin is gap - radius*||score_sensitivity||_2.
        Scores are divided by one positive readout scale, which leaves winners
        and stability radii unchanged. Float64 boundary guards are conservative
        numerical checks, not interval-arithmetic certification.

        This is NOT confidence, evidence sufficiency, model-error robustness,
        action authorization, or a claim about the external world's outcome.
        """
        if isinstance(radius, bool) or not math.isfinite(radius) or radius < 0:
            raise ValueError("observation radius must be finite and nonnegative")
        indices = tuple(indices)
        candidate, response = self.condition(field, indices, values)
        _, observation = self._observation(field, indices, values)
        if indices and float(torch.linalg.vector_norm(observation)) + radius > self.observation_norm_bound:
            raise ValueError("observation uncertainty ball exceeds the declared norm bound")
        matrix = torch.as_tensor(readout, dtype=field.dtype, device=field.device)
        if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] != self.dimension:
            raise ValueError("readout must have at least two rows and one column per workspace coordinate")
        if matrix.requires_grad or not bool(torch.isfinite(matrix).all()):
            raise ValueError("readout must be fixed and finite")
        scale = float(matrix.abs().max()) or 1.0
        matrix = matrix / scale
        workspace = self._workspace(self._parts(candidate))
        scores = matrix @ workspace
        winner = int(scores.argmax())
        competitors = [i for i in range(len(scores)) if i != winner]
        differences = matrix[winner] - matrix[competitors]
        gaps = differences @ workspace
        sensitivities = differences @ response

        def row_norm(rows: Tensor) -> Tensor:
            sizes = rows.abs().amax(dim=1) if rows.shape[1] else rows.new_zeros(rows.shape[0])
            divisors = torch.where(sizes > 0, sizes, torch.ones_like(sizes))
            return sizes * torch.linalg.vector_norm(rows / divisors[:, None], dim=1)

        norms = row_norm(sensitivities)
        worst_margins = gaps - radius * norms
        evaluation_scale = differences.abs() @ workspace.abs() + radius * row_norm(differences.abs() @ response.abs())
        guards = 64 * torch.finfo(field.dtype).eps * evaluation_scale + torch.finfo(field.dtype).tiny
        if not all(bool(torch.isfinite(value).all()) for value in (scores, gaps, sensitivities, worst_margins, guards)):
            raise ValueError("linear readout exceeds the finite numerical range")
        certified = bool(torch.all(worst_margins > guards))
        limiting = int(worst_margins.argmin())
        if float(norms[limiting]) > 0:
            perturbation = -radius * sensitivities[limiting] / norms[limiting]
        else:
            perturbation = observation.new_zeros(observation.shape)
        # Zero sensitivity with a tied margin cannot support a unique winner.
        boundary_distances = [
            max(0.0, float(gap / norm)) if float(norm) > 0 else (0.0 if float(gap) <= 0 else math.inf)
            for gap, norm in zip(gaps, norms)
        ]
        stability_radius = min(boundary_distances)
        return candidate, {
            "scope": "fixed quadratic field and fixed linear readout; observation L2 error only",
            "nominal_action": winner,
            "certified_action": winner if certified else None,
            "observation_radius": float(radius),
            "readout_scale": scale,
            "normalized_scores": scores.tolist(),
            "competitors": competitors,
            "normalized_nominal_margins": gaps.tolist(),
            "normalized_sensitivity_norms": norms.tolist(),
            "normalized_worst_case_margins": worst_margins.tolist(),
            "numerical_margin_guards": guards.tolist(),
            "linear_stability_radius": stability_radius if math.isfinite(stability_radius) else None,
            "limiting_competitor": competitors[limiting],
            "worst_case_observation_delta": perturbation.tolist(),
        }

    def checkpoint(self, field: Tensor) -> dict[str, Any]:
        """Data-only payload; deliberately incompatible with v2/v3 checkpoints."""
        self.validate(field)
        return {"schema": STATE_SCHEMA, "geometry": asdict(self), "field": field.detach().cpu().clone()}

    def restore(self, payload: Mapping[str, Any], *, device: str | torch.device = "cpu") -> Tensor:
        if not isinstance(payload, Mapping) or set(payload) != {"schema", "geometry", "field"}:
            raise ValueError("invalid variational checkpoint envelope")
        if payload["schema"] != STATE_SCHEMA or payload["geometry"] != asdict(self):
            raise ValueError("checkpoint belongs to a different field interpretation")
        self.validate(payload["field"])
        return payload["field"].detach().to(device=device).clone()
 
REGIONAL_KERNEL_NAME = "numerical.variational"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.regional-variational-field-state.v1"
REGIONAL_RESULT_SCHEMA = "cassifi.regional-kernel-result.v1"

_REGIONAL_MAX_DIMENSION = 128
_REGIONAL_MAX_FACTORS = 64
_REGIONAL_MAX_SCOPE = 16
_REGIONAL_MAX_ITERATIONS = 4_096
_REGIONAL_WORD_MAX = 2**32 - 1
_REGIONAL_EPSILON = 2.220446049250313e-16


class VariationalRegionalError(ValueError):
    """A regional variational task or bounded transition is invalid."""


def _regional_integer(
    value: Any,
    name: str,
    *,
    minimum: int = 0,
    maximum: int = 2**31 - 1,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > maximum
    ):
        raise VariationalRegionalError(
            f"{name} must be an integer in [{minimum}, {maximum}]"
        )
    return int(value)


def _regional_number(
    value: Any,
    name: str,
    *,
    nonnegative: bool = False,
    positive: bool = False,
) -> float:
    if isinstance(value, bool):
        raise VariationalRegionalError(f"{name} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise VariationalRegionalError(f"{name} must be finite") from exc
    if (
        not math.isfinite(number)
        or (nonnegative and number < 0.0)
        or (positive and number <= 0.0)
    ):
        qualifier = (
            "finite and nonnegative"
            if nonnegative
            else "finite and positive"
            if positive
            else "finite"
        )
        raise VariationalRegionalError(f"{name} must be {qualifier}")
    return number


def _regional_json(value: Any, name: str = "regional state") -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise VariationalRegionalError(f"{name} is not canonical JSON") from exc


def _regional_float_words(value: Any, name: str) -> list[int]:
    number = _regional_number(value, name)
    raw = struct.pack("<d", number)
    return [
        int.from_bytes(raw[:4], "little"),
        int.from_bytes(raw[4:], "little"),
    ]


def _regional_decode_float_words(
    words: Any,
    name: str,
    *,
    count: int | None = None,
) -> list[float]:
    if not isinstance(words, list):
        raise VariationalRegionalError(f"{name} must be a word list")
    if len(words) % 2:
        raise VariationalRegionalError(f"{name} has an odd word count")
    if count is not None and len(words) != 2 * count:
        raise VariationalRegionalError(f"{name} has the wrong word count")
    decoded: list[float] = []
    for offset in range(0, len(words), 2):
        low = _regional_integer(
            words[offset], f"{name} word", maximum=_REGIONAL_WORD_MAX
        )
        high = _regional_integer(
            words[offset + 1], f"{name} word", maximum=_REGIONAL_WORD_MAX
        )
        number = struct.unpack(
            "<d", low.to_bytes(4, "little") + high.to_bytes(4, "little")
        )[0]
        if not math.isfinite(number):
            raise VariationalRegionalError(f"{name} contains a nonfinite number")
        decoded.append(number)
    return decoded


def _regional_vector_words(values: Sequence[Any], name: str) -> list[int]:
    words: list[int] = []
    for index, value in enumerate(values):
        words.extend(_regional_float_words(value, f"{name}[{index}]"))
    return words


def _regional_decode_matrix_words(
    words: Any,
    rows: int,
    columns: int,
    name: str,
) -> list[list[float]]:
    values = _regional_decode_float_words(
        words, name, count=rows * columns
    )
    return [
        values[row * columns : (row + 1) * columns]
        for row in range(rows)
    ]


def _regional_norm(values: Sequence[float], name: str) -> float:
    scale = max((abs(float(value)) for value in values), default=0.0)
    if not math.isfinite(scale):
        raise VariationalRegionalError(f"{name} is nonfinite")
    if scale == 0.0:
        return 0.0
    scaled = math.sqrt(
        sum((float(value) / scale) ** 2 for value in values)
    )
    result = scale * scaled
    if not math.isfinite(result):
        raise VariationalRegionalError(f"{name} exceeds the finite range")
    return result


def _regional_eigenvalues(matrix: Sequence[Sequence[float]]) -> list[float]:
    """Deterministically diagonalize a small symmetric matrix for guards."""
    size = len(matrix)
    working = [list(row) for row in matrix]
    if any(len(row) != size for row in working):
        raise VariationalRegionalError("regional covariance is not square")
    for row in working:
        if any(not math.isfinite(value) for value in row):
            raise VariationalRegionalError("regional covariance is nonfinite")
    if size <= 1:
        return [working[0][0]] if size else []
    limit = max(16, 16 * size * size)
    for _ in range(limit):
        p, q = 0, 1
        largest = 0.0
        for row in range(size):
            for column in range(row + 1, size):
                magnitude = abs(working[row][column])
                if magnitude > largest:
                    largest = magnitude
                    p, q = row, column
        diagonal_scale = max(
            1.0,
            max(abs(working[index][index]) for index in range(size)),
        )
        if largest <= 32.0 * _REGIONAL_EPSILON * diagonal_scale:
            break
        app, aqq, apq = working[p][p], working[q][q], working[p][q]
        angle = 0.5 * math.atan2(2.0 * apq, aqq - app)
        cosine, sine = math.cos(angle), math.sin(angle)
        for index in range(size):
            if index in (p, q):
                continue
            aip, aiq = working[index][p], working[index][q]
            working[index][p] = working[p][index] = (
                cosine * aip - sine * aiq
            )
            working[index][q] = working[q][index] = (
                sine * aip + cosine * aiq
            )
        working[p][p] = (
            cosine * cosine * app
            - 2.0 * sine * cosine * apq
            + sine * sine * aqq
        )
        working[q][q] = (
            sine * sine * app
            + 2.0 * sine * cosine * apq
            + cosine * cosine * aqq
        )
        working[p][q] = working[q][p] = 0.0
    values = [working[index][index] for index in range(size)]
    if any(not math.isfinite(value) for value in values):
        raise VariationalRegionalError("regional covariance spectrum is nonfinite")
    return values


def _regional_spd_inverse(
    matrix: Sequence[Sequence[float]],
    *,
    ridge: float,
    norm_bound: float,
    name: str,
) -> list[list[float]]:
    size = len(matrix)
    if size < 1 or size > _REGIONAL_MAX_SCOPE:
        raise VariationalRegionalError(f"{name} dimension is outside the bound")
    copied = [list(row) for row in matrix]
    if any(len(row) != size for row in copied):
        raise VariationalRegionalError(f"{name} must be square")
    for row in copied:
        if any(not math.isfinite(value) for value in row):
            raise VariationalRegionalError(f"{name} is nonfinite")
    for row in range(size):
        for column in range(row):
            if copied[row][column] != copied[column][row]:
                raise VariationalRegionalError(f"{name} must be symmetric")
    upper = ridge + norm_bound * norm_bound
    if not math.isfinite(upper):
        raise VariationalRegionalError(f"{name} spectral bound is nonfinite")
    spectrum = _regional_eigenvalues(copied)
    tolerance = (
        128.0 * _REGIONAL_EPSILON * size * max(1.0, upper)
    )
    if (
        min(spectrum) < ridge - tolerance
        or max(spectrum) > upper + tolerance
    ):
        raise VariationalRegionalError(
            f"{name} leaves its declared spectral bounds"
        )
    lower: list[list[float]] = [
        [0.0 for _ in range(size)] for _ in range(size)
    ]
    for row in range(size):
        for column in range(row + 1):
            value = copied[row][column] - sum(
                lower[row][index] * lower[column][index]
                for index in range(column)
            )
            if row == column:
                if not math.isfinite(value) or value <= 0.0:
                    raise VariationalRegionalError(
                        f"{name} must be positive definite"
                    )
                lower[row][column] = math.sqrt(value)
            else:
                divisor = lower[column][column]
                if divisor <= 0.0 or not math.isfinite(divisor):
                    raise VariationalRegionalError(
                        f"{name} must be positive definite"
                    )
                lower[row][column] = value / divisor
    inverse = [[0.0 for _ in range(size)] for _ in range(size)]
    for column in range(size):
        forward = [0.0 for _ in range(size)]
        for row in range(size):
            rhs = 1.0 if row == column else 0.0
            forward[row] = (
                rhs
                - sum(lower[row][index] * forward[index] for index in range(row))
            ) / lower[row][row]
        backward = [0.0 for _ in range(size)]
        for row in range(size - 1, -1, -1):
            backward[row] = (
                forward[row]
                - sum(
                    lower[index][row] * backward[index]
                    for index in range(row + 1, size)
                )
            ) / lower[row][row]
        for row in range(size):
            inverse[row][column] = backward[row]
    if any(
        not math.isfinite(value)
        for row in inverse
        for value in row
    ):
        raise VariationalRegionalError(f"{name} inverse is nonfinite")
    return inverse


def _regional_spd_solve(
    matrix: Sequence[Sequence[float]],
    vector: Sequence[float],
    *,
    name: str,
) -> list[float]:
    size = len(matrix)
    if len(vector) != size:
        raise VariationalRegionalError(f"{name} dimensions do not match")
    if not size:
        return []
    copied = [list(row) for row in matrix]
    if any(
        len(row) != size or any(not math.isfinite(value) for value in row)
        for row in copied
    ) or any(not math.isfinite(value) for value in vector):
        raise VariationalRegionalError(f"{name} is nonfinite")
    if any(
        copied[row][column] != copied[column][row]
        for row in range(size)
        for column in range(row)
    ):
        raise VariationalRegionalError(f"{name} must be symmetric")
    lower = [[0.0 for _ in range(size)] for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            value = copied[row][column] - sum(
                lower[row][index] * lower[column][index]
                for index in range(column)
            )
            if row == column:
                if not math.isfinite(value) or value <= 0.0:
                    raise VariationalRegionalError(
                        f"{name} must be positive definite"
                    )
                lower[row][column] = math.sqrt(value)
            else:
                lower[row][column] = value / lower[column][column]
    forward = [0.0 for _ in range(size)]
    for row in range(size):
        forward[row] = (
            vector[row]
            - sum(lower[row][index] * forward[index] for index in range(row))
        ) / lower[row][row]
    result = [0.0 for _ in range(size)]
    for row in range(size - 1, -1, -1):
        result[row] = (
            forward[row]
            - sum(
                lower[index][row] * result[index]
                for index in range(row + 1, size)
            )
        ) / lower[row][row]
    if any(not math.isfinite(value) for value in result):
        raise VariationalRegionalError(f"{name} solution is nonfinite")
    return result


def _regional_precision(
    geometry: Mapping[str, Any],
    covariance: Sequence[Sequence[Sequence[float]]],
) -> list[list[float]]:
    dimension = int(geometry["dimension"])
    ridge = _regional_decode_float_words(
        geometry["ridge_words"], "regional ridge", count=1
    )[0]
    norm_bound = _regional_decode_float_words(
        geometry["norm_bound_words"], "regional norm bound", count=1
    )[0]
    precision = [
        [0.0 for _ in range(dimension)] for _ in range(dimension)
    ]
    for factor, reference in enumerate(geometry["factor_refs"]):
        scope = [int(value) for value in reference["coordinates"]]
        inverse = _regional_spd_inverse(
            covariance[factor],
            ridge=ridge,
            norm_bound=norm_bound,
            name=f"regional covariance factor {factor}",
        )
        for local_row, global_row in enumerate(scope):
            for local_column, global_column in enumerate(scope):
                precision[global_row][global_column] += inverse[
                    local_row
                ][local_column]
    if any(
        not math.isfinite(value)
        for row in precision
        for value in row
    ):
        raise VariationalRegionalError("regional precision is nonfinite")
    return precision


def _regional_validate_state(state: Any) -> None:
    required = {
        "schema", "geometry", "task", "continuation", "work", "result"
    }
    if not isinstance(state, Mapping) or set(state) != required:
        raise VariationalRegionalError("regional variational state is invalid")
    if state["schema"] != REGIONAL_STATE_SCHEMA:
        raise VariationalRegionalError("regional variational state schema is invalid")
    geometry = state["geometry"]
    if (
        not isinstance(geometry, Mapping)
        or set(geometry)
        != {
            "dimension",
            "factor_refs",
            "ridge_words",
            "norm_bound_words",
            "phi_words",
        }
    ):
        raise VariationalRegionalError("regional variational geometry is invalid")
    dimension = _regional_integer(
        geometry["dimension"],
        "regional dimension",
        minimum=1,
        maximum=_REGIONAL_MAX_DIMENSION,
    )
    references = geometry["factor_refs"]
    if (
        not isinstance(references, list)
        or not references
        or len(references) > _REGIONAL_MAX_FACTORS
    ):
        raise VariationalRegionalError("regional factor references are invalid")
    covered: set[int] = set()
    for factor, reference in enumerate(references):
        if (
            not isinstance(reference, Mapping)
            or set(reference) != {"factor_id", "scope_ref", "coordinates"}
            or reference["factor_id"] != factor
            or reference["scope_ref"] != f"scope:{factor}"
        ):
            raise VariationalRegionalError("regional factor reference is invalid")
        coordinates = reference["coordinates"]
        if (
            not isinstance(coordinates, list)
            or not coordinates
            or len(coordinates) > _REGIONAL_MAX_SCOPE
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value < dimension
                for value in coordinates
            )
            or len(coordinates) != len(set(coordinates))
        ):
            raise VariationalRegionalError("regional factor scope is invalid")
        covered.update(coordinates)
    if covered != set(range(dimension)):
        raise VariationalRegionalError(
            "regional factor geometry does not cover the workspace"
        )
    ridge = _regional_decode_float_words(
        geometry["ridge_words"], "regional ridge", count=1
    )[0]
    norm_bound = _regional_decode_float_words(
        geometry["norm_bound_words"], "regional norm bound", count=1
    )[0]
    phi = _regional_decode_float_words(
        geometry["phi_words"], "regional phi", count=1
    )[0]
    if ridge <= 0.0 or norm_bound <= 0.0 or phi <= 0.0:
        raise VariationalRegionalError(
            "regional geometry parameters must be positive"
        )
    if not math.isfinite(ridge + norm_bound * norm_bound):
        raise VariationalRegionalError("regional spectral bound is nonfinite")

    task = state["task"]
    task_keys = {
        "covariance_words",
        "workspace_words",
        "rhs_words",
        "observed_indices",
        "observed_words",
        "duration_words",
        "uncertainty_words",
        "allowance_words",
        "readout",
        "panel_size",
        "max_iterations",
    }
    if not isinstance(task, Mapping) or set(task) != task_keys:
        raise VariationalRegionalError("regional variational task is invalid")
    covariance_words = task["covariance_words"]
    if (
        not isinstance(covariance_words, list)
        or len(covariance_words) != len(references)
    ):
        raise VariationalRegionalError("regional covariance words are invalid")
    for factor, reference in enumerate(references):
        size = len(reference["coordinates"])
        covariance_values = _regional_decode_float_words(
            covariance_words[factor],
            f"regional covariance factor {factor}",
            count=size * size,
        )
        covariance_matrix = [
            covariance_values[row * size : (row + 1) * size]
            for row in range(size)
        ]
        _regional_spd_inverse(
            covariance_matrix,
            ridge=ridge,
            norm_bound=norm_bound,
            name=f"regional covariance factor {factor}",
        )
    workspace = _regional_decode_float_words(
        task["workspace_words"],
        "regional workspace",
        count=dimension,
    )
    indices = task["observed_indices"]
    if (
        not isinstance(indices, list)
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value < dimension
            for value in indices
        )
        or len(indices) != len(set(indices))
    ):
        raise VariationalRegionalError("regional observed indices are invalid")
    observed = _regional_decode_float_words(
        task["observed_words"],
        "regional observations",
        count=len(indices),
    )
    duration = _regional_decode_float_words(
        task["duration_words"], "regional duration", count=1
    )[0]
    uncertainty = _regional_decode_float_words(
        task["uncertainty_words"], "regional uncertainty", count=1
    )[0]
    allowance = _regional_decode_float_words(
        task["allowance_words"], "regional allowance", count=1
    )[0]
    if duration <= 0.0 or uncertainty < 0.0 or allowance <= 0.0:
        raise VariationalRegionalError(
            "regional duration, uncertainty, or allowance is invalid"
        )
    if _regional_norm(observed, "regional observation") + uncertainty > norm_bound:
        raise VariationalRegionalError(
            "regional observation uncertainty exceeds the norm bound"
        )
    panel_size = _regional_integer(
        task["panel_size"],
        "regional panel size",
        minimum=1,
        maximum=dimension,
    )
    max_iterations = _regional_integer(
        task["max_iterations"],
        "regional maximum iterations",
        minimum=1,
        maximum=_REGIONAL_MAX_ITERATIONS,
    )
    readout = task["readout"]
    if readout is not None:
        if (
            not isinstance(readout, Mapping)
            or set(readout) != {"rows", "columns", "words"}
        ):
            raise VariationalRegionalError("regional readout is invalid")
        rows = _regional_integer(
            readout["rows"], "regional readout rows", minimum=2, maximum=256
        )
        columns = _regional_integer(
            readout["columns"],
            "regional readout columns",
            minimum=1,
            maximum=_REGIONAL_MAX_DIMENSION,
        )
        if columns != dimension:
            raise VariationalRegionalError(
                "regional readout dimension does not match geometry"
            )
        _regional_decode_float_words(
            readout["words"],
            "regional readout words",
            count=rows * columns,
        )

    continuation = state["continuation"]
    continuation_keys = {
        "phase", "panel_cursor", "iteration", "free_indices", "residual_norm"
    }
    if (
        not isinstance(continuation, Mapping)
        or set(continuation) != continuation_keys
        or continuation["phase"] not in {"running", "done", "fault"}
    ):
        raise VariationalRegionalError("regional continuation is invalid")
    free = [
        index for index in range(dimension) if index not in set(indices)
    ]
    if continuation["free_indices"] != free:
        raise VariationalRegionalError("regional free-coordinate cursor is invalid")
    _regional_decode_float_words(
        task["rhs_words"],
        "regional implicit right hand side",
        count=len(free),
    )
    panel_cursor = _regional_integer(
        continuation["panel_cursor"],
        "regional panel cursor",
        maximum=len(free),
    )
    iteration = _regional_integer(
        continuation["iteration"],
        "regional iteration cursor",
        maximum=max_iterations,
    )
    residual = continuation["residual_norm"]
    if residual is not None:
        _regional_number(residual, "regional residual norm", nonnegative=True)
    if not free and panel_cursor != 0:
        raise VariationalRegionalError("regional empty solve cursor is invalid")
    if panel_cursor == 0 and iteration == 0 and residual is not None:
        raise VariationalRegionalError("regional initial residual is invalid")
    work = state["work"]
    if (
        not isinstance(work, Mapping)
        or set(work) != {"panels", "iterations", "total"}
    ):
        raise VariationalRegionalError("regional work ledger is invalid")
    panels = _regional_integer(
        work["panels"], "regional panel work", maximum=2**53 - 1
    )
    iterations = _regional_integer(
        work["iterations"],
        "regional completed iterations",
        maximum=2**53 - 1,
    )
    total = _regional_integer(
        work["total"], "regional accumulated work", maximum=2**53 - 1
    )
    if panels != total or iterations != iteration:
        raise VariationalRegionalError("regional work ledger is inconsistent")
    result = state["result"]
    if continuation["phase"] == "running" and result is not None:
        raise VariationalRegionalError("running regional state has a result")
    if continuation["phase"] in {"done", "fault"} and not isinstance(
        result, Mapping
    ):
        raise VariationalRegionalError("terminal regional state has no result")
    _regional_json(state)
    del workspace, ridge, phi, panels, iterations, total


def regional_state(
    model: VariationalField,
    field: Tensor,
    indices: Sequence[int] = (),
    values: Any = (),
    *,
    duration: float = 1.0,
    panel_size: int = 1,
    max_iterations: int = 256,
    uncertainty: float = 0.0,
    allowance: float = 1e-12,
    readout: Any = None,
) -> dict[str, Any]:
    """Lower one fixed-memory relaxation into typed regional task data."""
    if not isinstance(model, VariationalField):
        raise VariationalRegionalError("regional variational model is invalid")
    try:
        model.validate(field)
    except (ValueError, TypeError, RuntimeError) as exc:
        raise VariationalRegionalError(str(exc)) from exc
    dimension = model.dimension
    try:
        observed_indices = list(indices)
    except TypeError as exc:
        raise VariationalRegionalError(
            "regional observed indices must be a sequence"
        ) from exc
    if (
        any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < dimension
            for index in observed_indices
        )
        or len(observed_indices) != len(set(observed_indices))
    ):
        raise VariationalRegionalError("regional observed indices are invalid")
    try:
        observed_values = list(values)
    except TypeError as exc:
        raise VariationalRegionalError(
            "regional observations must be a sequence"
        ) from exc
    if len(observed_values) != len(observed_indices):
        raise VariationalRegionalError(
            "regional observations do not match their coordinates"
        )
    observed = [
        _regional_number(value, f"regional observation[{index}]")
        for index, value in enumerate(observed_values)
    ]
    duration_value = _regional_number(
        duration, "regional duration", positive=True
    )
    uncertainty_value = _regional_number(
        uncertainty, "regional uncertainty", nonnegative=True
    )
    allowance_value = _regional_number(
        allowance, "regional allowance", positive=True
    )
    panel_value = _regional_integer(
        panel_size,
        "regional panel size",
        minimum=1,
        maximum=dimension,
    )
    iteration_value = _regional_integer(
        max_iterations,
        "regional maximum iterations",
        minimum=1,
        maximum=_REGIONAL_MAX_ITERATIONS,
    )
    if _regional_norm(observed, "regional observation") + uncertainty_value > model.observation_norm_bound:
        raise VariationalRegionalError(
            "regional observation uncertainty exceeds the norm bound"
        )
    if readout is not None:
        try:
            readout_tensor = torch.as_tensor(
                readout, dtype=torch.float64, device="cpu"
            )
        except (TypeError, ValueError, RuntimeError) as exc:
            raise VariationalRegionalError("regional readout is invalid") from exc
        if (
            readout_tensor.ndim != 2
            or readout_tensor.shape[0] < 2
            or readout_tensor.shape[1] != dimension
            or readout_tensor.requires_grad
            or not bool(torch.isfinite(readout_tensor).all())
        ):
            raise VariationalRegionalError("regional readout is invalid")
        readout_value: dict[str, Any] | None = {
            "rows": int(readout_tensor.shape[0]),
            "columns": int(readout_tensor.shape[1]),
            "words": _regional_vector_words(
                readout_tensor.reshape(-1).tolist(), "regional readout"
            ),
        }
    else:
        readout_value = None
    parts = model._parts(field)
    covariance_words: list[list[int]] = []
    factor_refs: list[dict[str, Any]] = []
    for factor, scope in enumerate(model.scopes):
        covariance = model._covariance(parts, factor)
        covariance_words.append(
            _regional_vector_words(
                covariance.reshape(-1).tolist(),
                f"regional covariance factor {factor}",
            )
        )
        factor_refs.append(
            {
                "factor_id": factor,
                "scope_ref": f"scope:{factor}",
                "coordinates": list(scope),
            }
        )
    workspace = model._workspace(parts).tolist()
    free = [
        index for index in range(dimension) if index not in set(observed_indices)
    ]
    state = {
        "schema": REGIONAL_STATE_SCHEMA,
        "geometry": {
            "dimension": dimension,
            "factor_refs": factor_refs,
            "ridge_words": _regional_float_words(model.ridge, "regional ridge"),
            "norm_bound_words": _regional_float_words(
                model.observation_norm_bound, "regional norm bound"
            ),
            "phi_words": _regional_float_words(model.phi, "regional phi"),
        },
        "task": {
            "covariance_words": covariance_words,
            "workspace_words": _regional_vector_words(
                workspace, "regional workspace"
            ),
            "rhs_words": [],
            "observed_indices": observed_indices,
            "observed_words": _regional_vector_words(
                observed, "regional observations"
            ),
            "duration_words": _regional_float_words(
                duration_value, "regional duration"
            ),
            "uncertainty_words": _regional_float_words(
                uncertainty_value, "regional uncertainty"
            ),
            "allowance_words": _regional_float_words(
                allowance_value, "regional allowance"
            ),
            "readout": readout_value,
            "panel_size": panel_value,
            "max_iterations": iteration_value,
        },
        "continuation": {
            "phase": "running",
            "panel_cursor": 0,
            "iteration": 0,
            "free_indices": free,
            "residual_norm": None,
        },
        "work": {"panels": 0, "iterations": 0, "total": 0},
        "result": None,
    }
    covariance_values, workspace_values, observed_keys, observed_values, duration_number, _, _ = (
        _regional_task_values(state)
    )
    regional_precision = _regional_precision(
        state["geometry"], covariance_values
    )
    fixed_rhs = [
        workspace_values[index]
        - duration_number
        * sum(
            regional_precision[row][observed_index] * observed_values[column]
            for column, observed_index in enumerate(observed_keys)
        )
        for row, index in enumerate(free)
    ]
    state["task"]["rhs_words"] = _regional_vector_words(
        fixed_rhs, "regional implicit right hand side"
    )
    _regional_validate_state(state)
    return state


def _regional_task_values(
    state: Mapping[str, Any],
) -> tuple[
    list[list[list[float]]],
    list[float],
    list[int],
    list[float],
    float,
    float,
    float,
]:
    geometry = state["geometry"]
    task = state["task"]
    covariance: list[list[list[float]]] = []
    for factor, reference in enumerate(geometry["factor_refs"]):
        size = len(reference["coordinates"])
        values = _regional_decode_float_words(
            task["covariance_words"][factor],
            f"regional covariance factor {factor}",
            count=size * size,
        )
        covariance.append(
            [
                values[row * size : (row + 1) * size]
                for row in range(size)
            ]
        )
    dimension = int(geometry["dimension"])
    workspace = _regional_decode_float_words(
        task["workspace_words"], "regional workspace", count=dimension
    )
    indices = [int(value) for value in task["observed_indices"]]
    observed = _regional_decode_float_words(
        task["observed_words"],
        "regional observations",
        count=len(indices),
    )
    duration = _regional_decode_float_words(
        task["duration_words"], "regional duration", count=1
    )[0]
    uncertainty = _regional_decode_float_words(
        task["uncertainty_words"], "regional uncertainty", count=1
    )[0]
    allowance = _regional_decode_float_words(
        task["allowance_words"], "regional allowance", count=1
    )[0]
    return (
        covariance,
        workspace,
        indices,
        observed,
        duration,
        uncertainty,
        allowance,
    )


def _regional_output(
    state: Mapping[str, Any],
    workspace: Sequence[float],
    precision: Sequence[Sequence[float]],
    residual_norm: float,
    *,
    status: str,
) -> dict[str, Any]:
    geometry = state["geometry"]
    task = state["task"]
    dimension = int(geometry["dimension"])
    indices = [int(value) for value in task["observed_indices"]]
    ridge = _regional_decode_float_words(
        geometry["ridge_words"], "regional ridge", count=1
    )[0]
    covariance, _, _, _, _, uncertainty, allowance = _regional_task_values(state)
    energy = 0.0
    for factor, reference in enumerate(geometry["factor_refs"]):
        scope = [int(value) for value in reference["coordinates"]]
        inverse = _regional_spd_inverse(
            covariance[factor],
            ridge=ridge,
            norm_bound=_regional_decode_float_words(
                geometry["norm_bound_words"], "regional norm bound", count=1
            )[0],
            name=f"regional covariance factor {factor}",
        )
        size = len(scope)
        local = [workspace[index] for index in scope]
        covariance_matrix = covariance[factor]
        lower: list[list[float]] = [
            [0.0 for _ in range(size)] for _ in range(size)
        ]
        for row in range(size):
            for column in range(row + 1):
                value = covariance_matrix[row][column] - sum(
                    lower[row][index] * lower[column][index]
                    for index in range(column)
                )
                if row == column:
                    lower[row][column] = math.sqrt(value)
                else:
                    lower[row][column] = value / lower[column][column]
        logdet = (
            2.0 * sum(math.log(lower[index][index]) for index in range(size))
            - size * math.log(ridge)
        )
        quadratic = sum(
            local[row] * inverse[row][column] * local[column]
            for row in range(size)
            for column in range(size)
        )
        trace = sum(inverse[index][index] for index in range(size))
        energy += 0.5 * (logdet + ridge * trace - size + quadratic)
    if not math.isfinite(energy):
        raise VariationalRegionalError("regional output energy is nonfinite")
    action: dict[str, Any] | None = None
    readout = task["readout"]
    if readout is not None:
        matrix = _regional_decode_matrix_words(
            readout["words"],
            int(readout["rows"]),
            int(readout["columns"]),
            "regional readout words",
        )
        scale = max(
            (abs(value) for row in matrix for value in row),
            default=0.0,
        ) or 1.0
        normalized = [[value / scale for value in row] for row in matrix]
        scores = [
            sum(row[index] * workspace[index] for index in range(dimension))
            for row in normalized
        ]
        if any(not math.isfinite(value) for value in scores):
            raise VariationalRegionalError("regional readout scores are nonfinite")
        winner = max(range(len(scores)), key=lambda index: scores[index])
        competitors = [
            index for index in range(len(scores)) if index != winner
        ]
        free = [
            index
            for index in range(dimension)
            if index not in set(indices)
        ]
        response = [
            [0.0 for _ in indices] for _ in range(dimension)
        ]
        for column, index in enumerate(indices):
            response[index][column] = 1.0
        if free and indices:
            cross = [
                [precision[row][index] for index in indices]
                for row in free
            ]
            hessian = [
                [precision[row][column] for column in free]
                for row in free
            ]
            for column in range(len(indices)):
                solved = _regional_spd_solve(
                    hessian,
                    [-cross[row][column] for row in range(len(free))],
                    name="regional readout response",
                )
                for row, index in enumerate(free):
                    response[index][column] = solved[row]
        gaps: list[float] = []
        norms: list[float] = []
        worst: list[float] = []
        for competitor in competitors:
            difference = [
                normalized[winner][index] - normalized[competitor][index]
                for index in range(dimension)
            ]
            gap = sum(difference[index] * workspace[index] for index in range(dimension))
            sensitivity = [
                sum(difference[index] * response[index][column] for index in range(dimension))
                for column in range(len(indices))
            ]
            norm = _regional_norm(sensitivity, "regional readout sensitivity")
            gaps.append(gap)
            norms.append(norm)
            worst.append(gap - uncertainty * norm)
        evaluation = [
            abs(gap) + uncertainty * abs(norm)
            for gap, norm in zip(gaps, norms)
        ]
        guards = [
            64.0 * _REGIONAL_EPSILON * max(1.0, value)
            for value in evaluation
        ]
        certified = bool(worst) and all(
            margin > guard for margin, guard in zip(worst, guards)
        )
        limiting = min(range(len(worst)), key=lambda index: worst[index]) if worst else 0
        limiting_norm = norms[limiting] if norms else 0.0
        perturbation = (
            [
                -uncertainty * value / limiting_norm
                for value in (
                    [
                        sum(
                            (
                                normalized[winner][index]
                                - normalized[competitors[limiting]][index]
                            )
                            * response[index][column]
                            for index in range(dimension)
                        )
                        for column in range(len(indices))
                    ]
                )
            ]
            if limiting_norm > 0.0
            else [0.0 for _ in indices]
        )
        distances = [
            max(0.0, gap / norm)
            if norm > 0.0
            else (0.0 if gap <= 0.0 else math.inf)
            for gap, norm in zip(gaps, norms)
        ]
        stability = min(distances) if distances else None
        action = {
            "nominal_action": winner,
            "certified_action": winner if certified else None,
            "readout_scale": scale,
            "normalized_scores": scores,
            "competitors": competitors,
            "normalized_nominal_margins": gaps,
            "normalized_sensitivity_norms": norms,
            "normalized_worst_case_margins": worst,
            "numerical_margin_guards": guards,
            "linear_stability_radius": (
                stability if stability is not None and math.isfinite(stability) else None
            ),
            "limiting_competitor": (
                competitors[limiting] if competitors else None
            ),
            "worst_case_observation_delta": perturbation,
        }
    return {
        "schema": REGIONAL_RESULT_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "status": status,
        "workspace_words": _regional_vector_words(
            workspace, "regional output workspace"
        ),
        "workspace": [float(value) for value in workspace],
        "iterations": int(state["work"]["iterations"]),
        "panels": int(state["work"]["panels"]),
        "work": int(state["work"]["total"]),
        "residual_norm": float(residual_norm),
        "uncertainty": uncertainty,
        "allowance": allowance,
        "energy": energy,
        "precision": [list(row) for row in precision],
        "action": action,
    }


def _regional_fault(state: dict[str, Any], message: str) -> dict[str, Any]:
    state["continuation"] = {
        **dict(state["continuation"]),
        "phase": "fault",
    }
    result = {
        "schema": REGIONAL_RESULT_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "status": "fault",
        "error_type": "VariationalRegionalError",
        "message": str(message),
    }
    state["result"] = result
    return result


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Perform bounded Gauss--Seidel panels over serialized variational data."""
    _regional_validate_state(state)
    if not isinstance(arguments, Mapping) or arguments:
        raise VariationalRegionalError(
            "regional variational kernel takes no arguments"
        )
    bound = _regional_integer(
        quantum,
        "regional variational quantum",
        minimum=1,
        maximum=REGIONAL_KERNEL_MAX_WORK,
    )
    current = json.loads(_regional_json(dict(state)))
    phase = current["continuation"]["phase"]
    if phase == "done":
        return KernelResult(
            state=current,
            status="done",
            work=0,
            output=current["result"],
        )
    if phase == "fault":
        return KernelResult(
            state=current,
            status="fault",
            work=0,
            output=current["result"],
        )
    geometry = current["geometry"]
    task = current["task"]
    covariance, workspace, indices, observed, duration, _, allowance = (
        _regional_task_values(current)
    )
    dimension = int(geometry["dimension"])
    precision = _regional_precision(geometry, covariance)
    for column, index in enumerate(indices):
        workspace[index] = observed[column]
    free = [int(value) for value in current["continuation"]["free_indices"]]
    if not free:
        current["task"]["workspace_words"] = _regional_vector_words(
            workspace, "regional workspace"
        )
        current["continuation"]["phase"] = "done"
        current["continuation"]["residual_norm"] = 0.0
        current["result"] = _regional_output(
            current, workspace, precision, 0.0, status="done"
        )
        return KernelResult(
            state=current, status="done", work=0, output=current["result"]
        )
    hessian = [
        [precision[row][column] for column in free] for row in free
    ]
    rhs = _regional_decode_float_words(
        task["rhs_words"],
        "regional implicit right hand side",
        count=len(free),
    )
    system = [
        [
            (1.0 if row == column else 0.0)
            + duration * hessian[row][column]
            for column in range(len(free))
        ]
        for row in range(len(free))
    ]
    if any(
        not math.isfinite(value)
        for value in rhs
    ) or any(
        not math.isfinite(value)
        for row in system
        for value in row
    ):
        raise VariationalRegionalError(
            "regional implicit system is nonfinite"
        )
    consumed = 0
    panel_size = int(task["panel_size"])
    max_iterations = int(task["max_iterations"])
    while consumed < bound and current["continuation"]["phase"] == "running":
        cursor = int(current["continuation"]["panel_cursor"])
        end = min(cursor + panel_size, len(free))
        for local in range(cursor, end):
            diagonal = system[local][local]
            value = (
                rhs[local]
                - sum(
                    system[local][other] * workspace[free[other]]
                    for other in range(len(free))
                    if other != local
                )
            ) / diagonal
            if not math.isfinite(value):
                raise VariationalRegionalError(
                    "regional continuation produced a nonfinite value"
                )
            workspace[free[local]] = value
        consumed += 1
        current["work"]["panels"] += 1
        current["work"]["total"] += 1
        current["continuation"]["panel_cursor"] = end
        current["task"]["workspace_words"] = _regional_vector_words(
            workspace, "regional workspace"
        )
        if end != len(free):
            continue
        iteration = int(current["continuation"]["iteration"]) + 1
        current["continuation"]["iteration"] = iteration
        current["work"]["iterations"] = iteration
        current["continuation"]["panel_cursor"] = 0
        residual_values = [
            sum(
                system[row][column] * workspace[free[column]]
                for column in range(len(free))
            )
            - rhs[row]
            for row in range(len(free))
        ]
        residual_norm = _regional_norm(
            residual_values, "regional continuation residual"
        )
        current["continuation"]["residual_norm"] = residual_norm
        guard = 64.0 * _REGIONAL_EPSILON * max(
            1.0, _regional_norm(rhs, "regional implicit right hand side")
        )
        if residual_norm <= allowance + guard:
            exact = _regional_spd_solve(
                system, rhs, name="regional implicit system"
            )
            for local, index in enumerate(free):
                workspace[index] = exact[local]
            final_residual = _regional_norm(
                [
                    sum(
                        system[row][column] * exact[column]
                        for column in range(len(free))
                    )
                    - rhs[row]
                    for row in range(len(free))
                ],
                "regional final residual",
            )
            current["continuation"]["residual_norm"] = final_residual
            current["task"]["workspace_words"] = _regional_vector_words(
                workspace, "regional workspace"
            )
            current["continuation"]["phase"] = "done"
            current["result"] = _regional_output(
                current, workspace, precision, final_residual, status="done"
            )
        elif iteration >= max_iterations:
            current["result"] = _regional_fault(
                current,
                "regional iteration allowance exhausted before convergence",
            )
    status = "yield"
    output = None
    if current["continuation"]["phase"] == "done":
        status, output = "done", current["result"]
    elif current["continuation"]["phase"] == "fault":
        status, output = "fault", current["result"]
    return KernelResult(
        state=current,
        status=status,
        work=consumed,
        output=output,
    )


__all__ = [
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_RESULT_SCHEMA",
    "REGIONAL_STATE_SCHEMA",
    "STATE_SCHEMA",
    "VariationalField",
    "VariationalRegionalError",
    "regional_kernel",
    "regional_state",
]
