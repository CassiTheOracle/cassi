"""Native reciprocal-graph wave-energy currents for the Cassi site operator.

The implementation mirrors ``compute/cassi_site_physics.glsl`` with winding,
radial-source, and momentum-cap terms omitted as required by the frozen
counterflow analysis.  It deliberately exposes graph wave-energy quantities;
these are not material/species velocities.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components


__all__ = ["NativeCurrentGraph"]


_GRADIENT_REG = float(np.float32(1.0e-6))
_EPS_DISTANCE2 = float(np.float32(1.0e-16))
_SQRT_ONE_HALF = float(np.float32(math.sqrt(0.5)))


def _finite_float_array(value: Any, name: str) -> np.ndarray:
    """Convert an array-like value to float64 and reject non-finite entries."""
    try:
        result = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a numeric array") from exc
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _native_scalar(value: Any, name: str) -> float:
    """Return a scalar represented by the shader's float32 push constant."""
    raw = np.asarray(value)
    if raw.shape != ():
        raise ValueError(f"{name} must be a scalar")
    try:
        native = np.float32(raw.item())
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite scalar") from exc
    if not np.isfinite(native):
        raise ValueError(f"{name} must be a finite scalar")
    return float(native)


def _integer_array(value: Any, name: str) -> np.ndarray:
    """Convert an integer CSR array without accepting lossy float indices."""
    raw = np.asarray(value)
    if raw.ndim != 1 or not np.issubdtype(raw.dtype, np.integer):
        raise ValueError(f"{name} must be a one-dimensional integer array")
    return np.asarray(raw, dtype=np.int64)


def _minimum_image(delta: np.ndarray, extents: np.ndarray) -> np.ndarray:
    """Apply the shader's periodic minimum-image transform."""
    period = 2.0 * extents
    return delta - period * np.floor(delta / period + 0.5)


class NativeCurrentGraph:
    """Reconstruct native graph operators and wave-energy current diagnostics.

    ``sites`` contains tile coordinates (three coordinates plus optional GLSL
    padding).  ``offsets`` and ``neighbors`` are the authoritative CSR graph.
    The constructor requires that graph to be a connected, reciprocal,
    duplicate-free, self-edge-free graph; it never fills in missing reverse
    edges.  Volumes use the executed shader guard ``max(abs(V), floor)``.

    ``evaluate`` is vectorized over sites and edges.  The sparse operators and
    geometry-dependent gradient inverses are built once in the constructor so
    repeated frame evaluation does not walk Python neighbor lists.
    """

    def __init__(
        self,
        sites: Any,
        volumes: Any,
        offsets: Any,
        neighbors: Any,
        extents: Any,
        c2: Any,
        phi: Any,
        volume_floor: Any = 0.005,
    ) -> None:
        site_array = _finite_float_array(sites, "sites")
        if site_array.ndim != 2 or site_array.shape[1] not in (3, 4):
            raise ValueError("sites must have shape (N, 3) or (N, 4)")
        site_count = int(site_array.shape[0])
        if site_count <= 0:
            raise ValueError("sites must contain at least one site")

        volume_array = _finite_float_array(volumes, "volumes")
        if volume_array.shape != (site_count,):
            raise ValueError(f"volumes must have shape ({site_count},)")

        extent_array = _finite_float_array(extents, "extents")
        if extent_array.shape != (3,):
            raise ValueError("extents must have shape (3,)")
        if np.any(extent_array <= 0.0):
            raise ValueError("extents must be strictly positive")

        floor = _finite_float_array(volume_floor, "volume_floor")
        if floor.shape != () or float(floor) <= 0.0:
            raise ValueError("volume_floor must be a positive scalar")
        floor_value = float(floor)

        self.sites = site_array[:, :3].copy()
        self.extents = extent_array.copy()
        self.world_sites = self.sites - self.extents
        self.volume_floor = floor_value
        # This is exactly site_volume() in the executed shader.
        self.volumes = np.maximum(np.abs(volume_array), floor_value)
        self.node_mass = np.power(self.volumes, 1.0 / 3.0)
        self._face_area = np.power(self.volumes, 2.0 / 3.0)

        self.c2 = _native_scalar(c2, "c2")
        self.phi = _native_scalar(phi, "phi")
        if self.c2 < 0.0:
            raise ValueError("c2 must be nonnegative for positive graph energy")
        if self.phi <= 0.0:
            raise ValueError("phi must be positive for positive graph energy")

        self.offsets = _integer_array(offsets, "offsets")
        self.neighbors = _integer_array(neighbors, "neighbors")
        if self.offsets.shape != (site_count + 1,):
            raise ValueError(f"offsets must have shape ({site_count + 1},)")
        if self.offsets[0] != 0:
            raise ValueError("offsets[0] must be zero")
        if np.any(np.diff(self.offsets) < 0):
            raise ValueError("offsets must be nondecreasing")
        if self.offsets[-1] != self.neighbors.size:
            raise ValueError("offsets[-1] must equal neighbors.size")

        row_degree = np.diff(self.offsets)
        rows = np.repeat(np.arange(site_count, dtype=np.int64), row_degree)
        cols = self.neighbors.copy()
        if np.any(cols < 0) or np.any(cols >= site_count):
            raise ValueError("neighbors contains an out-of-range site index")
        if np.any(rows == cols):
            raise ValueError("CSR graph contains a self edge")

        directed_pairs = np.column_stack((rows, cols))
        _, directed_counts = np.unique(directed_pairs, axis=0, return_counts=True)
        if directed_counts.size != cols.size or np.any(directed_counts != 1):
            raise ValueError("CSR graph contains duplicate directed edges")
        undirected_pairs = np.sort(directed_pairs, axis=1)
        _, reciprocal_counts = np.unique(undirected_pairs, axis=0, return_counts=True)
        if reciprocal_counts.size * 2 != cols.size or np.any(reciprocal_counts != 2):
            raise ValueError("CSR graph must contain exactly one reciprocal edge per pair")

        canonical = rows < cols
        self.edge_i = rows[canonical].copy()
        self.edge_j = cols[canonical].copy()
        edge_count = int(self.edge_i.size)
        if edge_count * 2 != cols.size:
            raise ValueError("CSR graph reciprocal edge count is inconsistent")

        adjacency = sparse.coo_matrix(
            (
                np.ones(cols.size, dtype=np.float64),
                (rows, cols),
            ),
            shape=(site_count, site_count),
        ).tocsr()
        component_count = int(connected_components(adjacency, directed=False, return_labels=False))
        if component_count != 1:
            raise ValueError(f"CSR graph must be connected; found {component_count} components")

        # Every directed CSR row uses its own shader minimum-image displacement.
        # In particular, this preserves the shader's deterministic half-period
        # tie behavior rather than assuming reverse displacement is bitwise -d.
        directed_delta = _minimum_image(
            self.world_sites[cols] - self.world_sites[rows], self.extents
        )
        directed_distance2 = np.einsum("ij,ij->i", directed_delta, directed_delta)
        if np.any(~(directed_distance2 > _EPS_DISTANCE2)):
            raise ValueError("CSR graph contains coincident or zero-distance sites")
        directed_distance = np.sqrt(directed_distance2)
        directed_direction = directed_delta / directed_distance[:, None]

        # Canonical edge geometry is the i -> j row, with i < j.
        self.displacement = directed_delta[canonical].copy()
        self.distance = directed_distance[canonical].copy()
        self._directed_rows = rows
        self._directed_cols = cols
        self._directed_distance = directed_distance
        self._directed_direction = directed_direction
        # Recover each canonical edge's reverse CSR row.  Current vectors use
        # the directed minimum-image displacement at each endpoint; this is
        # significant at an exact half-period tie, where the shader's
        # floor-based transform need not produce d_ji == -d_ij.
        directed_keys = rows * site_count + cols
        key_order = np.argsort(directed_keys)
        sorted_keys = directed_keys[key_order]
        reverse_keys = self.edge_j * site_count + self.edge_i
        reverse_positions = np.searchsorted(sorted_keys, reverse_keys)
        if np.any(reverse_positions >= sorted_keys.size):
            raise ValueError("CSR graph reciprocal lookup failed")
        if np.any(sorted_keys[reverse_positions] != reverse_keys):
            raise ValueError("CSR graph reciprocal lookup failed")
        self._reverse_displacement = directed_delta[
            key_order[reverse_positions]
        ].copy()

        self._lap_operator = self._build_laplacian(
            site_count, rows, cols, directed_distance
        )
        self._gradient_operators = tuple(
            self._build_gradient_operator(
                site_count, rows, cols, directed_distance, directed_direction[:, axis]
            )
            for axis in range(3)
        )

        normal = np.broadcast_to(
            _GRADIENT_REG * np.eye(3, dtype=np.float64),
            (site_count, 3, 3),
        ).copy()
        if cols.size:
            outer = directed_direction[:, :, None] * directed_direction[:, None, :]
            np.add.at(normal, rows, outer)
        determinant = np.linalg.det(normal)
        self._gradient_valid = np.abs(determinant) > 1.0e-12
        self._gradient_inverse = np.zeros_like(normal)
        if np.any(self._gradient_valid):
            self._gradient_inverse[self._gradient_valid] = np.linalg.inv(
                normal[self._gradient_valid]
            )

        edge_numbers = np.arange(edge_count, dtype=np.int64)
        self._endpoint_incidence = sparse.coo_matrix(
            (
                np.ones(2 * edge_count, dtype=np.float64),
                (
                    np.concatenate((self.edge_i, self.edge_j)),
                    np.concatenate((edge_numbers, edge_numbers)),
                ),
            ),
            shape=(site_count, edge_count),
        ).tocsr()
        self._signed_incidence = sparse.coo_matrix(
            (
                np.concatenate(
                    (
                        np.ones(edge_count, dtype=np.float64),
                        -np.ones(edge_count, dtype=np.float64),
                    )
                ),
                (
                    np.concatenate((self.edge_i, self.edge_j)),
                    np.concatenate((edge_numbers, edge_numbers)),
                ),
            ),
            shape=(site_count, edge_count),
        ).tocsr()
        self._current_operators = tuple(
            sparse.coo_matrix(
                (
                    np.concatenate(
                        (self.displacement[:, axis], -self._reverse_displacement[:, axis])
                    ),
                    (
                        np.concatenate((self.edge_i, self.edge_j)),
                        np.concatenate((edge_numbers, edge_numbers)),
                    ),
                ),
                shape=(site_count, edge_count),
            ).tocsr()
            for axis in range(3)
        )

        degree = np.diff(self.offsets)
        self.topology_summary = {
            "site_count": site_count,
            "neighbor_count": int(cols.size),
            "directed_edge_count": int(cols.size),
            "undirected_edge_count": edge_count,
            "connected_components": component_count,
            "connected": True,
            "reciprocal": True,
            "duplicate_free": True,
            "self_edge_count": 0,
            "min_degree": int(degree.min()) if degree.size else 0,
            "max_degree": int(degree.max()) if degree.size else 0,
        }


    def _build_laplacian(
        self,
        site_count: int,
        rows: np.ndarray,
        cols: np.ndarray,
        distance: np.ndarray,
    ) -> sparse.csr_matrix:
        weights = self._face_area[rows] / distance
        off_diagonal = sparse.coo_matrix(
            (weights, (rows, cols)), shape=(site_count, site_count)
        ).tocsr()
        row_sum = np.bincount(rows, weights=weights, minlength=site_count)
        return (off_diagonal - sparse.diags(row_sum, offsets=0, format="csr")).tocsr()

    @staticmethod
    def _build_gradient_operator(
        site_count: int,
        rows: np.ndarray,
        cols: np.ndarray,
        distance: np.ndarray,
        direction_component: np.ndarray,
    ) -> sparse.csr_matrix:
        # rhs = sum_j ((psi_j - psi_i) / d_ij) * direction_ij.
        coefficients = direction_component / distance
        off_diagonal = sparse.coo_matrix(
            (coefficients, (rows, cols)), shape=(site_count, site_count)
        ).tocsr()
        row_sum = np.bincount(rows, weights=coefficients, minlength=site_count)
        return (off_diagonal - sparse.diags(row_sum, offsets=0, format="csr")).tocsr()

    @staticmethod
    def _state_array(value: Any, name: str, site_count: int) -> np.ndarray:
        result = _finite_float_array(value, name)
        if result.shape != (site_count,):
            raise ValueError(f"{name} must have shape ({site_count},)")
        return result

    def _gradients(self, values: np.ndarray) -> np.ndarray:
        rhs = np.empty((values.size, 3), dtype=np.float64)
        rhs[:, 0] = self._gradient_operators[0].dot(values)
        rhs[:, 1] = self._gradient_operators[1].dot(values)
        rhs[:, 2] = self._gradient_operators[2].dot(values)
        # The shader returns zero when the explicit determinant threshold is
        # reached; using a precomputed inverse keeps this frame path vectorized.
        return np.einsum("nij,nj->ni", self._gradient_inverse, rhs)

    def evaluate(
        self,
        y: Any,
        i: Any,
        py: Any,
        pi: Any,
        omega2: Any,
        mass_scale: Any,
        site_mass: Any,
    ) -> dict[str, np.ndarray]:
        """Evaluate native operators, powers, currents, and local energy balance.

        ``omega2`` and ``mass_scale`` are scalar values corresponding to the
        float32 push constants for the observed frame.  ``site_mass`` is the
        deposited site mass used by the native source ``S = mass_scale *
        site_mass / V``.  The returned ``balance_residual`` is independently
        formed as ``energy_derivative + divergence - source_power``; it is not
        assigned from a conservation identity.
        """
        site_count = self.world_sites.shape[0]
        y_array = self._state_array(y, "y", site_count)
        i_array = self._state_array(i, "i", site_count)
        py_array = self._state_array(py, "py", site_count)
        pi_array = self._state_array(pi, "pi", site_count)
        site_mass_array = self._state_array(site_mass, "site_mass", site_count)
        if np.any(site_mass_array < 0.0):
            raise ValueError("site_mass must be nonnegative deposited mass")
        omega2_value = _native_scalar(omega2, "omega2")
        mass_scale_value = _native_scalar(mass_scale, "mass_scale")
        if omega2_value < 0.0:
            raise ValueError("omega2 must be nonnegative for positive graph energy")

        lap_y = np.asarray(self._lap_operator.dot(y_array), dtype=np.float64).reshape(-1)
        lap_i = np.asarray(self._lap_operator.dot(i_array), dtype=np.float64).reshape(-1)
        grad_y = self._gradients(y_array)
        grad_i = self._gradients(i_array)

        edge_dy = y_array[self.edge_j] - y_array[self.edge_i]
        edge_di = i_array[self.edge_j] - i_array[self.edge_i]
        edge_power_y = -self.c2 * edge_dy * (
            py_array[self.edge_i] + py_array[self.edge_j]
        ) / (2.0 * self.distance)
        edge_power_i = -self.phi * self.c2 * edge_di * (
            pi_array[self.edge_i] + pi_array[self.edge_j]
        ) / (2.0 * self.distance)

        current_y = np.empty((site_count, 3), dtype=np.float64)
        current_y[:, 0] = self._current_operators[0].dot(edge_power_y)
        current_y[:, 1] = self._current_operators[1].dot(edge_power_y)
        current_y[:, 2] = self._current_operators[2].dot(edge_power_y)
        current_y /= 2.0 * self.volumes[:, None]
        current_i = np.empty((site_count, 3), dtype=np.float64)
        current_i[:, 0] = self._current_operators[0].dot(edge_power_i)
        current_i[:, 1] = self._current_operators[1].dot(edge_power_i)
        current_i[:, 2] = self._current_operators[2].dot(edge_power_i)
        current_i /= 2.0 * self.volumes[:, None]

        continuum_current_y = -self.c2 * py_array[:, None] * grad_y
        continuum_current_i = -self.phi * self.c2 * pi_array[:, None] * grad_i

        defect = y_array - self.phi * i_array
        kinetic = 0.5 * self.node_mass * (
            py_array * py_array + self.phi * pi_array * pi_array
        )
        coupling = 0.5 * omega2_value * self.node_mass * defect * defect
        edge_spring_energy = (
            edge_dy * edge_dy + self.phi * edge_di * edge_di
        ) / self.distance
        spring_by_site = 0.25 * self.c2 * np.asarray(
            self._endpoint_incidence.dot(edge_spring_energy), dtype=np.float64
        )
        energy_by_site = kinetic + coupling + spring_by_site

        # The source work is kept separate from the chain-rule derivative.
        source = mass_scale_value * (site_mass_array / self.volumes)
        source_power_by_site = self.node_mass * source * (
            py_array + self.phi * pi_array * _SQRT_ONE_HALF
        )

        # Native semidiscrete RHS (winding=0, radial_source=0, no momentum cap).
        rhs_y = self.c2 * lap_y / self.volumes - omega2_value * defect + source
        rhs_i = (
            self.c2 * lap_i / self.volumes
            + omega2_value * defect
            + source * _SQRT_ONE_HALF
        )

        # Differentiate the split site energy directly.  The edge spring part
        # uses d(psi_j-psi_i)/dt = pi_j-pi_i, independently of bond powers.
        spring_chain = 0.5 * self.c2 * np.asarray(
            self._endpoint_incidence.dot(
                (
                    edge_dy * (py_array[self.edge_j] - py_array[self.edge_i])
                    + self.phi
                    * edge_di
                    * (pi_array[self.edge_j] - pi_array[self.edge_i])
                )
                / self.distance
            ),
            dtype=np.float64,
        )
        energy_derivative_by_site = self.node_mass * (
            py_array * rhs_y
            + self.phi * pi_array * rhs_i
            + omega2_value * defect * (py_array - self.phi * pi_array)
        ) + spring_chain

        divergence_by_site = np.asarray(
            self._signed_incidence.dot(edge_power_y + edge_power_i),
            dtype=np.float64,
        ).reshape(-1)
        balance_residual = (
            energy_derivative_by_site + divergence_by_site - source_power_by_site
        )
        balance_scale = np.maximum.reduce(
            (
                np.abs(energy_derivative_by_site),
                np.abs(divergence_by_site),
                np.abs(source_power_by_site),
            )
        )
        balance_scale = np.maximum(balance_scale, 1.0e-30)

        return {
            "grad_y": grad_y,
            "grad_i": grad_i,
            "lap_y": lap_y,
            "lap_i": lap_i,
            "edge_power_y": edge_power_y,
            "edge_power_i": edge_power_i,
            "current_y": current_y,
            "current_i": current_i,
            "continuum_current_y": continuum_current_y,
            "continuum_current_i": continuum_current_i,
            "energy_by_site": energy_by_site,
            "source_power_by_site": source_power_by_site,
            "energy_derivative_by_site": energy_derivative_by_site,
            "divergence_by_site": divergence_by_site,
            "balance_residual": balance_residual,
            "balance_scale": balance_scale,
            "rhs_y": rhs_y,
            "rhs_i": rhs_i,
        }
