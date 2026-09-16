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

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor

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
