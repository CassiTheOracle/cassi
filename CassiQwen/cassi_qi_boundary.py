"""Strict CassiFI W7 boundary packets, metric-adjoint ports, and ingress journal."""

from __future__ import annotations

from contextlib import contextmanager
import base64
import json
import math
import os
import struct
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Any, Iterable, Iterator, Mapping, Sequence

import torch

from cassi_field_language import CassiFieldTextCodec
from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes
from cassi_qi_clock import QiCausalClock, QiClockError, QiClockTime, QiSourceScope, QiWatermark


BOUNDARY_PACKET_SCHEMA = "cassi.qi-flow-boundary-packet.v1"
NO_SAMPLE_SCHEMA = "cassi.qi-flow-no-sample.v1"
LINEAR_PORT_SCHEMA = "cassi.qi-flow-linear-boundary-port.v1"
ANTIALIAS_RECEIPT_SCHEMA = "cassi.qi-flow-antialias-receipt.v1"
JOURNAL_FRAME_SCHEMA = "cassi.qi-flow-ingress-journal-frame.v1"
JOURNAL_HEAD_SCHEMA = "cassi.qi-flow-ingress-journal-head.v1"
BOUNDARY_COMMIT_A_SCHEMA = "cassi.qi-flow-boundary-commit-a.v1"
PASSIVE_EGRESS_SCHEMA = "cassi.qi-flow-passive-egress-receipt.v1"


class QiBoundaryError(ValueError):
    """Raised before a boundary packet or state transition becomes committable."""


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise QiBoundaryError(f"{name} must be a nonempty string")
    return value


def _integer(value: int, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise QiBoundaryError(f"{name} must be an integer >= {minimum}")
    return value


def _finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise QiBoundaryError(f"{name} must be finite")
    return result


def _hash_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _sha256_identity(value: str, name: str) -> str:
    digest = _text(value, name)
    if len(digest) != 64 or digest.lower() != digest or any(ch not in "0123456789abcdef" for ch in digest):
        raise QiBoundaryError(f"{name} must be a lowercase SHA-256 digest")
    return digest


def _matrix_sha256(rows: Sequence[Sequence[complex]]) -> str:
    digest = sha256()
    digest.update(struct.pack("<II", len(rows), len(rows[0])))
    for row in rows:
        for value in row:
            digest.update(struct.pack("<dd", value.real, value.imag))
    return digest.hexdigest()


def _complex_rows(rows: Sequence[Sequence[complex]], name: str) -> tuple[tuple[complex, ...], ...]:
    converted = tuple(tuple(complex(value) for value in row) for row in rows)
    if not converted or not converted[0]:
        raise QiBoundaryError(f"{name} must be a nonempty matrix")
    width = len(converted[0])
    if any(len(row) != width for row in converted):
        raise QiBoundaryError(f"{name} must be rectangular")
    if any(not math.isfinite(value.real) or not math.isfinite(value.imag) for row in converted for value in row):
        raise QiBoundaryError(f"{name} contains a non-finite coefficient")
    return converted


def _matrix_payload(rows: Sequence[Sequence[complex]]) -> list[list[list[float]]]:
    return [[[value.real, value.imag] for value in row] for row in rows]


def _real_vector(values: Sequence[float], name: str, *, positive: bool = False) -> tuple[float, ...]:
    converted = tuple(_finite(value, name) for value in values)
    if not converted or (positive and any(value <= 0.0 for value in converted)):
        raise QiBoundaryError(f"{name} is empty or outside its domain")
    return converted


@dataclass(frozen=True, slots=True)
class QiLinearBoundaryPort:
    """A fixed observation operator B and its metric adjoint A=g G^-1 B* W."""

    name: str
    observation_rows: tuple[tuple[complex, ...], ...]
    source_metric: tuple[float, ...]
    field_metric: tuple[float, ...]
    gain: float
    port_indices: tuple[int, ...]
    descriptor_sha256: str

    @classmethod
    def create(
        cls,
        *,
        name: str,
        observation_rows: Sequence[Sequence[complex]],
        source_metric: Sequence[float],
        field_metric: Sequence[float],
        gain: float,
        port_indices: Sequence[int],
    ) -> "QiLinearBoundaryPort":
        port_name = _text(name, "port name")
        rows = _complex_rows(observation_rows, "observation_rows")
        source = _real_vector(source_metric, "source_metric", positive=True)
        field = _real_vector(field_metric, "field_metric", positive=True)
        scalar_gain = _finite(gain, "gain")
        if scalar_gain < 0.0:
            raise QiBoundaryError("gain must be nonnegative")
        ports = tuple(_integer(value, "port index") for value in port_indices)
        if len(rows) != len(source):
            raise QiBoundaryError("source metric length must equal observation row count")
        if len(rows[0]) != len(field):
            raise QiBoundaryError("field metric length must equal observation column count")
        if len(set(ports)) != len(ports) or any(value >= len(field) for value in ports):
            raise QiBoundaryError("port indices must be unique registered field coordinates")
        if any(any(value != 0j for index, value in enumerate(row) if index not in ports) for row in rows):
            raise QiBoundaryError("observation operator writes outside its registered field port")
        body = {
            "schema": LINEAR_PORT_SCHEMA,
            "name": port_name,
            "observation_shape": [len(rows), len(rows[0])],
            "observation_matrix_sha256": _matrix_sha256(rows),
            "source_metric": list(source),
            "field_metric": list(field),
            "gain": scalar_gain,
            "port_indices": list(ports),
        }
        return cls(port_name, rows, source, field, scalar_gain, ports, canonical_hash(body, LINEAR_PORT_SCHEMA))

    @property
    def source_dimension(self) -> int:
        return len(self.observation_rows)

    @property
    def field_dimension(self) -> int:
        return len(self.observation_rows[0])

    def _metric_identity_indices(self) -> tuple[int, ...] | None:
        if self.gain != 1.0:
            return None
        indices: list[int] = []
        for row_index, row in enumerate(self.observation_rows):
            nonzero = [column for column, value in enumerate(row) if value != 0j]
            if len(nonzero) != 1:
                return None
            column = nonzero[0]
            if row[column] != 1.0 + 0.0j or self.source_metric[row_index] != self.field_metric[column]:
                return None
            indices.append(column)
        return tuple(indices)

    def _matrix(self, *, device: torch.device | str = "cpu") -> torch.Tensor:
        return torch.tensor(self.observation_rows, dtype=torch.complex128, device=device)

    def observe(self, field: torch.Tensor) -> torch.Tensor:
        value = torch.as_tensor(field, dtype=torch.complex128)
        if tuple(value.shape) != (self.field_dimension,):
            raise QiBoundaryError("field vector shape disagrees with boundary port")
        indices = self._metric_identity_indices()
        if indices is not None:
            return value[list(indices)].contiguous()
        return (self._matrix(device=value.device) @ value).contiguous()

    def inject(self, source: torch.Tensor) -> torch.Tensor:
        value = torch.as_tensor(source, dtype=torch.complex128)
        if tuple(value.shape) != (self.source_dimension,):
            raise QiBoundaryError("source vector shape disagrees with boundary port")
        indices = self._metric_identity_indices()
        if indices is not None:
            result = torch.zeros(self.field_dimension, dtype=torch.complex128, device=value.device)
            result[list(indices)] = value
            return result
        matrix = self._matrix(device=value.device)
        source_metric = torch.tensor(self.source_metric, dtype=torch.float64, device=value.device)
        field_metric = torch.tensor(self.field_metric, dtype=torch.float64, device=value.device)
        adjoint = (matrix.conj().T * source_metric.unsqueeze(0)) / field_metric.unsqueeze(1)
        return (self.gain * (adjoint @ value)).contiguous()

    def adjoint_residual(self, field: torch.Tensor, source: torch.Tensor) -> float:
        x = torch.as_tensor(field, dtype=torch.complex128)
        y = torch.as_tensor(source, dtype=torch.complex128)
        if tuple(x.shape) != (self.field_dimension,) or tuple(y.shape) != (self.source_dimension,):
            raise QiBoundaryError("adjoint probe shape mismatch")
        bx = self.observe(x)
        ay = self.inject(y)
        source_metric = torch.tensor(self.source_metric, dtype=torch.float64, device=x.device)
        field_metric = torch.tensor(self.field_metric, dtype=torch.float64, device=x.device)
        left = torch.sum(bx.conj() * source_metric * y)
        right = torch.sum(x.conj() * field_metric * ay) / self.gain if self.gain != 0.0 else torch.zeros((), dtype=torch.complex128, device=x.device)
        return float(torch.abs(left - right).detach().cpu().item())


def assert_disjoint_ports(ports: Sequence[QiLinearBoundaryPort]) -> None:
    seen: dict[int, str] = {}
    for port in ports:
        if not isinstance(port, QiLinearBoundaryPort):
            raise QiBoundaryError("port registry contains an invalid descriptor")
        for index in port.port_indices:
            if index in seen:
                raise QiBoundaryError(f"boundary port collision between {seen[index]} and {port.name} at {index}")
            seen[index] = port.name


@dataclass(frozen=True, slots=True)
class QiOpticalDescriptor:
    descriptor_id: str
    sensor_shape_hwc: tuple[int, int, int]
    retinal_shape_yx: tuple[int, int]
    active_sensor_indices: tuple[int, ...]
    retinal_to_active_index: tuple[int, ...]
    luminance_coefficients: tuple[float, ...]
    raw_min: float
    raw_max: float
    midpoint: float
    port: QiLinearBoundaryPort
    descriptor_sha256: str

    @classmethod
    def create(
        cls,
        *,
        descriptor_id: str,
        sensor_shape_hwc: Sequence[int],
        retinal_shape_yx: Sequence[int],
        active_sensor_indices: Sequence[int],
        retinal_to_active_index: Sequence[int],
        luminance_coefficients: Sequence[float],
        raw_min: float,
        raw_max: float,
        midpoint: float,
        port: QiLinearBoundaryPort,
    ) -> "QiOpticalDescriptor":
        sensor = tuple(_integer(value, "sensor dimension", minimum=1) for value in sensor_shape_hwc)
        retinal = tuple(_integer(value, "retinal dimension", minimum=1) for value in retinal_shape_yx)
        if len(sensor) != 3 or len(retinal) != 2 or sensor[2] not in {1, 3}:
            raise QiBoundaryError("optical shape must be HxWx1 or HxWx3 and a 2-D retinal grid")
        active = tuple(_integer(value, "active sensor index") for value in active_sensor_indices)
        if not active or len(set(active)) != len(active) or any(value >= sensor[0] * sensor[1] for value in active):
            raise QiBoundaryError("active optical crop indices are invalid")
        remap = tuple(_integer(value, "retinal remap index") for value in retinal_to_active_index)
        if len(remap) != retinal[0] * retinal[1] or any(value >= len(active) for value in remap):
            raise QiBoundaryError("retinal resample map is incomplete")
        coefficients = _real_vector(luminance_coefficients, "luminance coefficient")
        if len(coefficients) != sensor[2]:
            raise QiBoundaryError("luminance coefficient count disagrees with sensor channels")
        low, high, center = _finite(raw_min, "raw_min"), _finite(raw_max, "raw_max"), _finite(midpoint, "midpoint")
        if not low < high or not low <= center <= high:
            raise QiBoundaryError("optical calibration range is invalid")
        if port.source_dimension != 2 * retinal[0] * retinal[1]:
            raise QiBoundaryError("optical port source dimension must hold Yang/Yin retinal channels")
        body = {
            "descriptor_id": descriptor_id,
            "sensor_shape_hwc": list(sensor),
            "retinal_shape_yx": list(retinal),
            "active_sensor_indices": list(active),
            "retinal_to_active_index": list(remap),
            "luminance_coefficients": list(coefficients),
            "raw_range": [low, high],
            "midpoint": center,
            "port_sha256": port.descriptor_sha256,
        }
        return cls(_text(descriptor_id, "descriptor_id"), sensor, retinal, active, remap, coefficients, low, high, center, port, canonical_hash(body, "cassi.qi-flow-optical-descriptor.v1"))

    def source_vector(self, frame: Sequence[float]) -> torch.Tensor:
        expected = math.prod(self.sensor_shape_hwc)
        values = tuple(_finite(value, "optical sample") for value in frame)
        if len(values) != expected or any(value < self.raw_min or value > self.raw_max for value in values):
            raise QiBoundaryError("optical frame shape or calibrated range is invalid")
        channels = self.sensor_shape_hwc[2]
        luminance = []
        for pixel in range(self.sensor_shape_hwc[0] * self.sensor_shape_hwc[1]):
            offset = pixel * channels
            luminance.append(sum(self.luminance_coefficients[channel] * values[offset + channel] for channel in range(channels)))
        active = [luminance[index] for index in self.active_sensor_indices]
        retinal = torch.tensor([active[index] - self.midpoint for index in self.retinal_to_active_index], dtype=torch.float64)
        return torch.cat((torch.clamp_min(retinal, 0.0), torch.clamp_min(-retinal, 0.0))).to(torch.complex128)


@dataclass(frozen=True, slots=True)
class QiAudioDescriptor:
    descriptor_id: str
    sample_rate_hz: int
    window: tuple[float, ...]
    hop_samples: int
    retained_bins: tuple[int, ...]
    port: QiLinearBoundaryPort
    descriptor_sha256: str

    @classmethod
    def create(
        cls,
        *,
        descriptor_id: str,
        sample_rate_hz: int,
        window: Sequence[float],
        hop_samples: int,
        retained_bins: Sequence[int],
        port: QiLinearBoundaryPort,
    ) -> "QiAudioDescriptor":
        rate = _integer(sample_rate_hz, "sample_rate_hz", minimum=1)
        weights = _real_vector(window, "window")
        if len(weights) < 2 or any(value == 0.0 for value in weights):
            raise QiBoundaryError("audio window must be nonsingular and contain at least two samples")
        hop = _integer(hop_samples, "hop_samples", minimum=1)
        if hop > len(weights):
            raise QiBoundaryError("audio hop exceeds the registered window")
        bins = tuple(_integer(value, "retained bin") for value in retained_bins)
        if not bins or len(set(bins)) != len(bins) or any(value > len(weights) // 2 for value in bins):
            raise QiBoundaryError("audio retained-bin registry is invalid")
        if port.source_dimension != len(bins):
            raise QiBoundaryError("audio port dimension disagrees with retained bins")
        body = {
            "descriptor_id": descriptor_id,
            "sample_rate_hz": rate,
            "window": list(weights),
            "hop_samples": hop,
            "retained_bins": list(bins),
            "normalization": "torch-rfft-norm-ortho.v1",
            "port_sha256": port.descriptor_sha256,
        }
        return cls(
            _text(descriptor_id, "descriptor_id"),
            rate,
            weights,
            hop,
            bins,
            port,
            canonical_hash(body, "cassi.qi-flow-audio-descriptor.v1"),
        )

    def source_vector(self, samples: Sequence[float]) -> torch.Tensor:
        values = torch.tensor(tuple(_finite(value, "audio sample") for value in samples), dtype=torch.float64)
        if values.numel() != len(self.window):
            raise QiBoundaryError("audio frame length disagrees with its descriptor")
        spectrum = torch.fft.rfft(values * torch.tensor(self.window, dtype=torch.float64), norm="ortho")
        return spectrum[torch.tensor(self.retained_bins, dtype=torch.long)].to(torch.complex128).contiguous()

    def reconstruct_window(self, retained: torch.Tensor) -> torch.Tensor:
        values = torch.as_tensor(retained, dtype=torch.complex128)
        if tuple(values.shape) != (len(self.retained_bins),):
            raise QiBoundaryError("audio retained spectrum shape mismatch")
        spectrum = torch.zeros(len(self.window) // 2 + 1, dtype=torch.complex128, device=values.device)
        spectrum[torch.tensor(self.retained_bins, dtype=torch.long, device=values.device)] = values
        return torch.fft.irfft(spectrum, n=len(self.window), norm="ortho").contiguous()


@dataclass(frozen=True, slots=True)
class QiProprioceptiveDescriptor:
    descriptor_id: str
    channel_names: tuple[str, ...]
    units: tuple[str, ...]
    minimums: tuple[float, ...]
    maximums: tuple[float, ...]
    basis_rows: tuple[tuple[complex, ...], ...]
    pseudoinverse_rows: tuple[tuple[complex, ...], ...]
    port: QiLinearBoundaryPort
    descriptor_sha256: str

    @classmethod
    def create(
        cls,
        *,
        descriptor_id: str,
        channel_names: Sequence[str],
        units: Sequence[str],
        minimums: Sequence[float],
        maximums: Sequence[float],
        basis_rows: Sequence[Sequence[complex]],
        port: QiLinearBoundaryPort,
        rank_tolerance: float,
    ) -> "QiProprioceptiveDescriptor":
        names = tuple(_text(value, "proprioceptive channel") for value in channel_names)
        unit_rows = tuple(_text(value, "proprioceptive unit") for value in units)
        low = _real_vector(minimums, "proprioceptive minimum")
        high = _real_vector(maximums, "proprioceptive maximum")
        if not names or len(set(names)) != len(names) or not (len(names) == len(unit_rows) == len(low) == len(high)) or any(a >= b for a, b in zip(low, high, strict=True)):
            raise QiBoundaryError("proprioceptive channel registry or ranges are invalid")
        basis = _complex_rows(basis_rows, "proprioceptive basis")
        if len(basis[0]) != len(names):
            raise QiBoundaryError("proprioceptive basis input dimension is invalid")
        matrix = torch.tensor(basis, dtype=torch.complex128)
        tolerance = _finite(rank_tolerance, "rank_tolerance")
        if tolerance <= 0.0 or int(torch.linalg.matrix_rank(matrix, tol=tolerance).item()) != len(names):
            raise QiBoundaryError("proprioceptive basis is not injective")
        inverse = torch.linalg.pinv(matrix, rtol=tolerance, atol=tolerance)
        pinv = tuple(tuple(complex(value.item()) for value in row) for row in inverse)
        if port.source_dimension != len(basis):
            raise QiBoundaryError("proprioceptive port source dimension disagrees with basis")
        body = {
            "descriptor_id": descriptor_id,
            "channel_names": list(names),
            "units": list(unit_rows),
            "minimums": list(low),
            "maximums": list(high),
            "basis_rows": _matrix_payload(basis),
            "pseudoinverse_rows": _matrix_payload(pinv),
            "rank_tolerance": tolerance,
            "port_sha256": port.descriptor_sha256,
        }
        return cls(_text(descriptor_id, "descriptor_id"), names, unit_rows, low, high, basis, pinv, port, canonical_hash(body, "cassi.qi-flow-proprioceptive-descriptor.v1"))

    def source_vector(self, values: Sequence[float]) -> torch.Tensor:
        raw = tuple(_finite(value, "proprioceptive sample") for value in values)
        if len(raw) != len(self.channel_names) or any(value < low or value > high for value, low, high in zip(raw, self.minimums, self.maximums, strict=True)):
            raise QiBoundaryError("proprioceptive sample shape or range is invalid")
        normalized = torch.tensor(
            [2.0 * (value - low) / (high - low) - 1.0 for value, low, high in zip(raw, self.minimums, self.maximums, strict=True)],
            dtype=torch.complex128,
        )
        return (torch.tensor(self.basis_rows, dtype=torch.complex128) @ normalized).contiguous()

    def reconstruct_channels(self, source: torch.Tensor) -> tuple[float, ...]:
        value = torch.as_tensor(source, dtype=torch.complex128)
        if tuple(value.shape) != (len(self.basis_rows),):
            raise QiBoundaryError("proprioceptive source shape mismatch")
        normalized = torch.tensor(self.pseudoinverse_rows, dtype=torch.complex128, device=value.device) @ value
        if float(torch.max(torch.abs(normalized.imag)).detach().cpu().item()) > 1.0e-10:
            raise QiBoundaryError("proprioceptive inverse left the registered real channel space")
        return tuple(
            low + 0.5 * (float(item.real.detach().cpu().item()) + 1.0) * (high - low)
            for item, low, high in zip(normalized, self.minimums, self.maximums, strict=True)
        )


@dataclass(frozen=True, slots=True)
class QiTextDescriptor:
    descriptor_id: str
    codec: CassiFieldTextCodec
    port: QiLinearBoundaryPort
    descriptor_sha256: str

    @classmethod
    def create(cls, *, descriptor_id: str, port: QiLinearBoundaryPort) -> "QiTextDescriptor":
        codec = CassiFieldTextCodec()
        if port.source_dimension != codec.alphabet_size:
            raise QiBoundaryError("text port must expose the frozen 260-symbol alphabet")
        body = {
            "descriptor_id": descriptor_id,
            "codec_sha256": codec.fingerprint,
            "alphabet_size": codec.alphabet_size,
            "port_sha256": port.descriptor_sha256,
        }
        return cls(
            _text(descriptor_id, "descriptor_id"),
            codec,
            port,
            canonical_hash(body, "cassi.qi-flow-text-descriptor.v1"),
        )

    def encode_message(self, message: str) -> tuple[torch.Tensor, ...]:
        symbols = self.codec.encode_messages(({"role": "user", "content": message},))[1:-1]
        rows = []
        for symbol in symbols:
            row = torch.zeros(self.codec.alphabet_size, dtype=torch.float64)
            row[symbol] = 1.0
            rows.append(row)
        return tuple(rows)

    def decode_symbols(self, symbols: Iterable[int]) -> str:
        values = tuple(_integer(symbol, "text symbol") for symbol in symbols)
        if any(symbol >= 256 for symbol in values):
            raise QiBoundaryError("text boundary output must contain UTF-8 byte symbols")
        return bytes(values).decode("utf-8", "strict")


@dataclass(frozen=True, slots=True)
class QiActuatorDescriptor:
    descriptor_id: str
    channel_names: tuple[str, ...]
    minimums: tuple[float, ...]
    maximums: tuple[float, ...]
    zero_points: tuple[float, ...]
    slew_per_tick: tuple[float, ...]
    quantization_step: tuple[float, ...]
    port: QiLinearBoundaryPort
    descriptor_sha256: str

    @classmethod
    def create(
        cls,
        *,
        descriptor_id: str,
        channel_names: Sequence[str],
        minimums: Sequence[float],
        maximums: Sequence[float],
        zero_points: Sequence[float],
        slew_per_tick: Sequence[float],
        quantization_step: Sequence[float],
        port: QiLinearBoundaryPort,
    ) -> "QiActuatorDescriptor":
        names = tuple(_text(value, "actuator channel") for value in channel_names)
        low = _real_vector(minimums, "actuator minimum")
        high = _real_vector(maximums, "actuator maximum")
        zero = _real_vector(zero_points, "actuator zero point")
        slew = _real_vector(slew_per_tick, "actuator slew", positive=True)
        quant = _real_vector(quantization_step, "actuator quantization", positive=True)
        if not names or len(set(names)) != len(names) or len({len(names), len(low), len(high), len(zero), len(slew), len(quant)}) != 1:
            raise QiBoundaryError("actuator channel vectors are incomplete")
        if any(not a < z < b for a, z, b in zip(low, zero, high, strict=True)):
            raise QiBoundaryError("actuator zero points must lie strictly inside channel ranges")
        if port.source_dimension != len(names):
            raise QiBoundaryError("actuator observation dimension disagrees with channels")
        body = {
            "descriptor_id": descriptor_id,
            "channel_names": list(names),
            "minimums": list(low),
            "maximums": list(high),
            "zero_points": list(zero),
            "slew_per_tick": list(slew),
            "quantization_step": list(quant),
            "port_sha256": port.descriptor_sha256,
        }
        return cls(_text(descriptor_id, "descriptor_id"), names, low, high, zero, slew, quant, port, canonical_hash(body, "cassi.qi-flow-actuator-descriptor.v1"))

    def quantize(self, requested: Sequence[float], previous: Sequence[float]) -> tuple[float, ...]:
        demand = tuple(_finite(value, "requested actuator value") for value in requested)
        prior = tuple(_finite(value, "previous actuator value") for value in previous)
        if len(demand) != len(self.channel_names) or len(prior) != len(self.channel_names):
            raise QiBoundaryError("actuator vector shape mismatch")
        result = []
        for value, old, low, high, slew, step in zip(demand, prior, self.minimums, self.maximums, self.slew_per_tick, self.quantization_step, strict=True):
            if value < low or value > high or old < low or old > high or abs(value - old) > slew:
                raise QiBoundaryError("actuator request violates range or slew contract")
            quantized = low + round((value - low) / step) * step
            if quantized < low or quantized > high:
                raise QiBoundaryError("actuator quantization left the registered range")
            result.append(quantized)
        return tuple(result)


@dataclass(frozen=True, slots=True)
class QiBoundaryPacket:
    schema: str
    profile_sha256: str
    clock_sha256: str
    descriptor_sha256: str
    source_epoch: str
    source_stream_id: str
    source_sequence: int
    capture_start: QiClockTime
    capture_end: QiClockTime
    logical_time: QiClockTime
    watermark_sha256: str
    ingress_journal_sha256: str
    payload_shape: tuple[int, ...]
    payload_dtype: str
    payload: bytes
    payload_sha256: str
    valid: bool
    event_id: str
    failure_reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        clock: QiCausalClock,
        scope: QiSourceScope,
        profile_sha256: str,
        watermark_sha256: str,
        ingress_journal_sha256: str,
        source_sequence: int,
        cycle_frontier: QiClockTime,
        payload_shape: Sequence[int],
        payload_dtype: str,
        payload: bytes,
        valid: bool = True,
        failure_reason: str | None = None,
    ) -> "QiBoundaryPacket":
        if not isinstance(clock, QiCausalClock) or not isinstance(scope, QiSourceScope):
            raise QiBoundaryError("packet requires a registered exact clock and source scope")
        profile = _sha256_identity(profile_sha256, "profile_sha256")
        clock_sha = _sha256_identity(clock.schedule_sha256, "clock_sha256")
        watermark = _sha256_identity(watermark_sha256, "watermark_sha256")
        journal = _sha256_identity(ingress_journal_sha256, "ingress_journal_sha256")
        sequence = _integer(source_sequence, "source_sequence")
        try:
            start, end = clock.expected_capture(scope, sequence)
            clock.validate_capture(
                scope=scope,
                source_sequence=sequence,
                capture_start=start,
                capture_end=end,
                cycle_frontier=cycle_frontier,
            )
        except QiClockError as exc:
            raise QiBoundaryError(str(exc)) from exc
        shape = tuple(_integer(value, "payload dimension") for value in payload_shape)
        dtype = _text(payload_dtype, "payload_dtype")
        if not isinstance(payload, bytes):
            raise QiBoundaryError("packet payload must be detached immutable bytes")
        if valid:
            if not payload or not shape or any(value == 0 for value in shape):
                raise QiBoundaryError("valid packet payload cannot be empty")
            if failure_reason is not None:
                raise QiBoundaryError("valid packet cannot carry a failure reason")
            reason = None
            schema = BOUNDARY_PACKET_SCHEMA
        else:
            if shape != (0,) or dtype != "none" or payload or failure_reason is None:
                raise QiBoundaryError("no-sample packet must carry shape [0], dtype none, empty payload, and a reason")
            reason = _text(failure_reason, "no_sample reason")
            schema = NO_SAMPLE_SCHEMA
        payload_hash = _hash_bytes(payload)
        header = {
            "schema": schema,
            "profile_sha256": profile,
            "clock_sha256": clock_sha,
            "descriptor_sha256": scope.descriptor_sha256,
            "source_epoch": scope.source_epoch,
            "source_stream_id": scope.source_stream_id,
            "source_sequence": sequence,
            "capture_start": start.payload(),
            "capture_end": end.payload(),
            "logical_time": cycle_frontier.payload(),
            "watermark_sha256": watermark,
            "ingress_journal_sha256": journal,
            "payload_shape": list(shape),
            "payload_dtype": dtype,
            "payload_sha256": payload_hash,
            "valid": valid,
            "failure_reason": reason,
        }
        event_id = canonical_hash(header, "cassi.qi-flow-boundary-event.v1")
        return cls(
            schema=schema,
            profile_sha256=profile,
            clock_sha256=clock_sha,
            descriptor_sha256=scope.descriptor_sha256,
            source_epoch=scope.source_epoch,
            source_stream_id=scope.source_stream_id,
            source_sequence=sequence,
            capture_start=start,
            capture_end=end,
            logical_time=cycle_frontier,
            watermark_sha256=watermark,
            ingress_journal_sha256=journal,
            payload_shape=shape,
            payload_dtype=dtype,
            payload=payload,
            payload_sha256=payload_hash,
            valid=valid,
            event_id=event_id,
            failure_reason=reason,
        )

    @classmethod
    def no_sample(
        cls,
        *,
        clock: QiCausalClock,
        scope: QiSourceScope,
        profile_sha256: str,
        watermark_sha256: str,
        ingress_journal_sha256: str,
        source_sequence: int,
        cycle_frontier: QiClockTime,
        reason: str,
    ) -> "QiBoundaryPacket":
        return cls.create(
            clock=clock,
            scope=scope,
            profile_sha256=profile_sha256,
            watermark_sha256=watermark_sha256,
            ingress_journal_sha256=ingress_journal_sha256,
            source_sequence=source_sequence,
            cycle_frontier=cycle_frontier,
            payload_shape=(0,),
            payload_dtype="none",
            payload=b"",
            valid=False,
            failure_reason=_text(reason, "no_sample reason"),
        )

    @property
    def scope(self) -> QiSourceScope:
        return QiSourceScope(
            source_epoch=self.source_epoch,
            source_stream_id=self.source_stream_id,
            descriptor_sha256=self.descriptor_sha256,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "event_id": self.event_id,
            "profile_sha256": self.profile_sha256,
            "clock_sha256": self.clock_sha256,
            "descriptor_sha256": self.descriptor_sha256,
            "source_epoch": self.source_epoch,
            "source_stream_id": self.source_stream_id,
            "source_sequence": self.source_sequence,
            "capture_start": self.capture_start.payload(),
            "capture_end": self.capture_end.payload(),
            "logical_time": self.logical_time.payload(),
            "watermark_sha256": self.watermark_sha256,
            "ingress_journal_sha256": self.ingress_journal_sha256,
            "payload_shape": list(self.payload_shape),
            "payload_dtype": self.payload_dtype,
            "payload_sha256": self.payload_sha256,
            "payload_base64": base64.b64encode(self.payload).decode("ascii"),
            "valid": self.valid,
            "failure_reason": self.failure_reason,
        }


@dataclass(frozen=True, slots=True)
class QiAntialiasReceipt:
    profile_sha256: str
    source_shape: tuple[int, ...]
    output_shape: tuple[int, ...]
    input_sha256: str
    output_sha256: str
    coefficient_sha256: str
    mode: str

    def payload(self) -> dict[str, Any]:
        body = {
            "schema": ANTIALIAS_RECEIPT_SCHEMA,
            "profile_sha256": self.profile_sha256,
            "source_shape": list(self.source_shape),
            "output_shape": list(self.output_shape),
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "coefficient_sha256": self.coefficient_sha256,
            "mode": self.mode,
        }
        return {**body, "self_sha256": canonical_hash(body, ANTIALIAS_RECEIPT_SCHEMA)}


def apply_antialias(samples: torch.Tensor, coefficients: Sequence[float], *, profile_sha256: str) -> tuple[torch.Tensor, QiAntialiasReceipt]:
    values = torch.as_tensor(samples, dtype=torch.float64)
    if values.ndim != 1 or values.numel() == 0:
        raise QiBoundaryError("antialias input must be one nonempty real channel")
    taps = torch.tensor(_real_vector(coefficients, "antialias coefficient"), dtype=torch.float64, device=values.device)
    if taps.numel() % 2 != 1 or taps.numel() > values.numel():
        raise QiBoundaryError("antialias FIR must have odd length no larger than the frame")
    kernel_sum = float(taps.sum().detach().cpu().item())
    if not math.isclose(kernel_sum, 1.0, rel_tol=0.0, abs_tol=1.0e-12):
        raise QiBoundaryError("antialias FIR must preserve DC exactly within registered tolerance")
    pad = taps.numel() // 2
    padded = torch.nn.functional.pad(values.reshape(1, 1, -1), (pad, pad), mode="reflect")
    output = torch.nn.functional.conv1d(padded, taps.flip(0).reshape(1, 1, -1)).reshape(-1).contiguous()
    input_bytes = struct.pack(f">{values.numel()}d", *[float(value) for value in values.detach().cpu()])
    output_bytes = struct.pack(f">{output.numel()}d", *[float(value) for value in output.detach().cpu()])
    coefficient_bytes = struct.pack(f">{taps.numel()}d", *[float(value) for value in taps.detach().cpu()])
    receipt = QiAntialiasReceipt(_text(profile_sha256, "profile_sha256"), tuple(values.shape), tuple(output.shape), _hash_bytes(input_bytes), _hash_bytes(output_bytes), _hash_bytes(coefficient_bytes), "fixed-fir-reflect-v1")
    return output, receipt


@dataclass(frozen=True, slots=True)
class QiJournalEntry:
    frame_sha256: str
    head_sha256: str
    previous_head_sha256: str | None
    cumulative_bytes: int


class QiIngressJournal:
    """Small content-addressed journal; HEAD advances only after durable objects."""

    def __init__(self, root: str | Path, *, max_bytes: int) -> None:
        self.root = Path(root)
        self.max_bytes = _integer(max_bytes, "max_bytes", minimum=1)
        self.objects = self.root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.root / "APPEND.lock"
        self._thread_lock = RLock()
        try:
            with self.lock_path.open("ab") as handle:
                if handle.tell() == 0:
                    handle.write(b"\x00")
                    handle.flush()
        except OSError as exc:
            raise QiBoundaryError("ingress journal lock is unavailable") from exc

    @contextmanager
    def _append_lock(self) -> Iterator[None]:
        with self._thread_lock:
            try:
                handle = self.lock_path.open("r+b")
            except OSError as exc:
                raise QiBoundaryError("ingress journal lock is unavailable") from exc
            with handle:
                try:
                    if os.name == "nt":
                        import msvcrt

                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                except OSError as exc:
                    raise QiBoundaryError("ingress journal lock cannot be acquired") from exc
                try:
                    yield
                finally:
                    if os.name == "nt":
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @property
    def head_path(self) -> Path:
        return self.root / "HEAD"

    def _read_head_sha256(self) -> str | None:
        if not self.head_path.exists():
            return None
        try:
            value = self.head_path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError) as exc:
            raise QiBoundaryError("ingress journal HEAD is unreadable") from exc
        return _sha256_identity(value, "ingress journal HEAD")

    def _read_object(self, digest: str) -> Mapping[str, Any]:
        digest = _sha256_identity(digest, "journal object")
        path = self.objects / f"{digest}.json"
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise QiBoundaryError(f"journal object {digest} is unreadable") from exc
        if _hash_bytes(raw) != digest or not isinstance(value, Mapping):
            raise QiBoundaryError("journal object hash mismatch")
        return value

    def _store(self, payload: Mapping[str, Any]) -> tuple[str, int]:
        raw = canonical_json_bytes(dict(payload))
        digest = _hash_bytes(raw)
        path = self.objects / f"{digest}.json"
        try:
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            try:
                if path.read_bytes() != raw:
                    raise QiBoundaryError("content-addressed journal collision")
            except OSError as exc:
                raise QiBoundaryError(f"journal object {digest} is unreadable") from exc
        except OSError as exc:
            raise QiBoundaryError(f"journal object {digest} is not durable") from exc
        return digest, len(raw)
    def _read_head(self, digest: str) -> Mapping[str, Any]:
        head = self._read_object(digest)
        if set(head) != {
            "schema",
            "previous_head_sha256",
            "frame_sha256",
            "event_id",
            "source_scope",
            "source_sequence",
            "cumulative_bytes",
        } or head.get("schema") != JOURNAL_HEAD_SCHEMA:
            raise QiBoundaryError("journal head schema is invalid")
        previous = head.get("previous_head_sha256")
        if previous is not None:
            _sha256_identity(previous, "journal predecessor")
        _sha256_identity(head.get("frame_sha256"), "journal frame")
        _text(head.get("event_id"), "journal event_id")
        source_scope = head.get("source_scope")
        if not isinstance(source_scope, Mapping) or set(source_scope) != {
            "source_epoch",
            "source_stream_id",
            "descriptor_sha256",
        }:
            raise QiBoundaryError("journal source scope is invalid")
        _text(source_scope.get("source_epoch"), "source_epoch")
        _text(source_scope.get("source_stream_id"), "source_stream_id")
        _sha256_identity(source_scope.get("descriptor_sha256"), "descriptor_sha256")
        _integer(head.get("source_sequence"), "source_sequence")
        _integer(head.get("cumulative_bytes"), "cumulative_bytes")
        return head

    def _read_frame(self, digest: str) -> Mapping[str, Any]:
        frame = self._read_object(digest)
        if set(frame) != {"schema", "packet"} or frame.get("schema") != JOURNAL_FRAME_SCHEMA:
            raise QiBoundaryError("journal frame schema is invalid")
        packet = frame.get("packet")
        if not isinstance(packet, Mapping):
            raise QiBoundaryError("journal frame packet is invalid")
        if set(packet) != {
            "schema",
            "event_id",
            "profile_sha256",
            "clock_sha256",
            "descriptor_sha256",
            "source_epoch",
            "source_stream_id",
            "source_sequence",
            "capture_start",
            "capture_end",
            "logical_time",
            "watermark_sha256",
            "ingress_journal_sha256",
            "payload_shape",
            "payload_dtype",
            "payload_sha256",
            "payload_base64",
            "valid",
            "failure_reason",
        }:
            raise QiBoundaryError("journal packet schema is invalid")
        if packet.get("schema") not in {BOUNDARY_PACKET_SCHEMA, NO_SAMPLE_SCHEMA}:
            raise QiBoundaryError("journal packet schema is invalid")
        event_id = _text(packet.get("event_id"), "packet event_id")
        _sha256_identity(packet.get("profile_sha256"), "profile_sha256")
        _sha256_identity(packet.get("clock_sha256"), "clock_sha256")
        _sha256_identity(packet.get("descriptor_sha256"), "descriptor_sha256")
        _text(packet.get("source_epoch"), "source_epoch")
        _text(packet.get("source_stream_id"), "source_stream_id")
        _integer(packet.get("source_sequence"), "source_sequence")
        try:
            capture_start = QiClockTime.from_payload(packet.get("capture_start"))
            capture_end = QiClockTime.from_payload(packet.get("capture_end"))
            logical_time = QiClockTime.from_payload(packet.get("logical_time"))
        except (QiClockError, TypeError, KeyError) as exc:
            raise QiBoundaryError("journal packet clock payload is invalid") from exc
        if not capture_start < capture_end or capture_end > logical_time:
            raise QiBoundaryError("journal packet clock interval is invalid")
        _sha256_identity(packet.get("watermark_sha256"), "watermark_sha256")
        _sha256_identity(packet.get("ingress_journal_sha256"), "ingress_journal_sha256")
        shape = packet.get("payload_shape")
        if not isinstance(shape, list) or not shape:
            raise QiBoundaryError("journal packet shape is invalid")
        for value in shape:
            _integer(value, "payload dimension")
        dtype = _text(packet.get("payload_dtype"), "payload_dtype")
        _sha256_identity(packet.get("payload_sha256"), "payload_sha256")
        encoded = packet.get("payload_base64")
        if not isinstance(encoded, str):
            raise QiBoundaryError("journal packet payload encoding is invalid")
        try:
            payload = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise QiBoundaryError("journal packet payload encoding is invalid") from exc
        if base64.b64encode(payload).decode("ascii") != encoded:
            raise QiBoundaryError("journal packet payload encoding is not canonical")
        valid = packet.get("valid")
        reason = packet.get("failure_reason")
        if not isinstance(valid, bool):
            raise QiBoundaryError("journal packet validity flag is invalid")
        if valid:
            if any(value == 0 for value in shape) or not payload or reason is not None or dtype == "none":
                raise QiBoundaryError("journal valid packet payload is invalid")
        elif shape != [0] or dtype != "none" or payload or not isinstance(reason, str) or not reason:
            raise QiBoundaryError("journal no-sample packet payload is invalid")
        if _hash_bytes(payload) != packet["payload_sha256"]:
            raise QiBoundaryError("journal packet payload hash mismatch")
        header = {
            "schema": packet["schema"],
            "profile_sha256": packet["profile_sha256"],
            "clock_sha256": packet["clock_sha256"],
            "descriptor_sha256": packet["descriptor_sha256"],
            "source_epoch": packet["source_epoch"],
            "source_stream_id": packet["source_stream_id"],
            "source_sequence": packet["source_sequence"],
            "capture_start": packet["capture_start"],
            "capture_end": packet["capture_end"],
            "logical_time": packet["logical_time"],
            "watermark_sha256": packet["watermark_sha256"],
            "ingress_journal_sha256": packet["ingress_journal_sha256"],
            "payload_shape": packet["payload_shape"],
            "payload_dtype": packet["payload_dtype"],
            "payload_sha256": packet["payload_sha256"],
            "valid": packet["valid"],
            "failure_reason": packet["failure_reason"],
        }
        try:
            expected_event = canonical_hash(header, "cassi.qi-flow-boundary-event.v1")
        except Exception as exc:
            raise QiBoundaryError("journal packet event identity is invalid") from exc
        if event_id != expected_event:
            raise QiBoundaryError("journal packet event identity is invalid")
        return frame


    def _replace_pointer(self, path: Path, digest: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("wb") as handle:
            handle.write((digest + "\n").encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def _head_contains_frame(self, head_sha256: str, frame_sha256: str) -> bool:
        cursor: str | None = _sha256_identity(head_sha256, "journal head")
        frame_sha256 = _sha256_identity(frame_sha256, "journal frame")
        seen: set[str] = set()
        while cursor is not None:
            if cursor in seen:
                raise QiBoundaryError("ingress journal head chain contains a cycle")
            seen.add(cursor)
            head = self._read_head(cursor)
            if head["frame_sha256"] == frame_sha256:
                return True
            cursor = head["previous_head_sha256"]
        return False

    def append(self, packet: QiBoundaryPacket) -> QiJournalEntry:
        if not isinstance(packet, QiBoundaryPacket):
            raise QiBoundaryError("journal append requires a strict boundary packet")
        with self._append_lock():
            frame = {"schema": JOURNAL_FRAME_SCHEMA, "packet": packet.canonical_payload()}
            frame_sha, frame_bytes = self._store(frame)
            self._read_frame(frame_sha)
            previous = self._read_head_sha256()
            if previous is not None and self._head_contains_frame(previous, frame_sha):
                head = self._read_head(previous)
                return QiJournalEntry(
                    frame_sha,
                    previous,
                    head["previous_head_sha256"],
                    head["cumulative_bytes"],
                )
            previous_bytes = 0
            if previous is not None:
                previous_bytes = self._read_head(previous)["cumulative_bytes"]
            cumulative = previous_bytes + frame_bytes
            if cumulative > self.max_bytes:
                raise QiBoundaryError("ingress journal capacity would be exceeded")
            head_body = {
                "schema": JOURNAL_HEAD_SCHEMA,
                "previous_head_sha256": previous,
                "frame_sha256": frame_sha,
                "event_id": packet.event_id,
                "source_scope": packet.scope.payload(),
                "source_sequence": packet.source_sequence,
                "cumulative_bytes": cumulative,
            }
            head_sha, _ = self._store(head_body)
            if self._read_head_sha256() != previous:
                raise QiBoundaryError("ingress journal advanced concurrently")
            self._replace_pointer(self.head_path, head_sha)
            return QiJournalEntry(frame_sha, head_sha, previous, cumulative)

    def replay(self) -> tuple[Mapping[str, Any], ...]:
        cursor = self._read_head_sha256()
        rows: list[Mapping[str, Any]] = []
        chain: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
        seen_heads: set[str] = set()
        seen_frames: set[str] = set()
        while cursor is not None:
            if cursor in seen_heads:
                raise QiBoundaryError("ingress journal head chain contains a cycle")
            seen_heads.add(cursor)
            head = self._read_head(cursor)
            frame_sha = head["frame_sha256"]
            if frame_sha in seen_frames:
                raise QiBoundaryError("ingress journal contains a duplicate frame")
            seen_frames.add(frame_sha)
            frame = self._read_frame(frame_sha)
            packet = frame["packet"]
            if (
                packet["event_id"] != head["event_id"]
                or packet["source_epoch"] != head["source_scope"].get("source_epoch")
                or packet["source_stream_id"] != head["source_scope"].get("source_stream_id")
                or packet["descriptor_sha256"] != head["source_scope"].get("descriptor_sha256")
                or packet["source_sequence"] != head["source_sequence"]
            ):
                raise QiBoundaryError("journal head and frame identities disagree")
            chain.append((head, frame))
            cursor = head["previous_head_sha256"]
        running = 0
        for head, frame in reversed(chain):
            try:
                running += len(canonical_json_bytes(dict(frame)))
            except Exception as exc:
                raise QiBoundaryError("journal frame is not canonically encoded") from exc
            if head["cumulative_bytes"] != running:
                raise QiBoundaryError("journal cumulative byte accounting is invalid")
            rows.append(frame)
        return tuple(rows)


@dataclass(frozen=True, slots=True)
class QiBoundaryCommitAReceipt:
    commit_sha256: str
    journal_head_sha256: str
    event_id: str
    predecessor_head_sha256: str
    candidate_state_sha256: str
    candidate_state_object_sha256: str
    watermark_payload: Mapping[str, Any]


class QiBoundaryCommitAStore:
    """Atomic boundary-local Commit A envelope and post-commit acknowledgement."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.head_path = self.root / "COMMITTED"

    def _replace_pointer(self, path: Path, digest: str) -> None:
        digest = _sha256_identity(digest, "committed object")
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            with temporary.open("wb") as handle:
                handle.write((digest + "\n").encode("ascii"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            raise QiBoundaryError("committed pointer is not durable") from exc

    def commit(
        self,
        *,
        journal: QiIngressJournal,
        entry: QiJournalEntry,
        packet: QiBoundaryPacket,
        watermark: QiWatermark,
        predecessor_head_sha256: str,
        candidate_state_sha256: str,
        candidate_state_object_sha256: str,
    ) -> tuple[QiWatermark, QiBoundaryCommitAReceipt]:
        if not isinstance(journal, QiIngressJournal):
            raise QiBoundaryError("Commit A requires an ingress journal")
        if not isinstance(entry, QiJournalEntry):
            raise QiBoundaryError("Commit A requires a journal entry")
        if not isinstance(packet, QiBoundaryPacket):
            raise QiBoundaryError("Commit A requires a strict boundary packet")
        if not isinstance(watermark, QiWatermark):
            raise QiBoundaryError("Commit A requires a strict watermark")
        entry_head = _sha256_identity(entry.head_sha256, "journal_head_sha256")
        entry_frame = _sha256_identity(entry.frame_sha256, "frame_sha256")
        entry_previous = (
            None
            if entry.previous_head_sha256 is None
            else _sha256_identity(entry.previous_head_sha256, "previous_head_sha256")
        )
        entry_cumulative = _integer(entry.cumulative_bytes, "cumulative_bytes")
        predecessor = _sha256_identity(predecessor_head_sha256, "predecessor_head_sha256")
        candidate = _sha256_identity(candidate_state_sha256, "candidate_state_sha256")
        candidate_object = _sha256_identity(candidate_state_object_sha256, "candidate_state_object_sha256")
        if journal._read_head_sha256() != entry_head:
            raise QiBoundaryError("Commit A journal head is not authoritative")
        head = journal._read_head(entry_head)
        if (
            head["frame_sha256"] != entry_frame
            or head["previous_head_sha256"] != entry_previous
            or head["cumulative_bytes"] != entry_cumulative
        ):
            raise QiBoundaryError("Commit A journal entry is not authoritative")
        frame = journal._read_frame(entry_frame)
        if frame["packet"] != packet.canonical_payload():
            raise QiBoundaryError("Commit A packet does not match its journal frame")
        try:
            advanced = watermark.advance(
                scope=packet.scope,
                capture_start=packet.capture_start,
                capture_end=packet.capture_end,
                source_sequence=packet.source_sequence,
                frame_sha256=entry_frame,
                first_sequence=packet.source_sequence,
                first_capture_start=packet.capture_start,
                cycle_frontier=packet.logical_time,
                indexed_in_commit_a=True,
            )
            if isinstance(advanced, tuple):
                next_watermark, status = advanced
            else:
                next_watermark, status = advanced, "accepted"
        except QiClockError as exc:
            raise QiBoundaryError(str(exc)) from exc
        body = {
            "schema": BOUNDARY_COMMIT_A_SCHEMA,
            "journal_head_sha256": entry_head,
            "frame_sha256": entry_frame,
            "event_id": packet.event_id,
            "predecessor_head_sha256": predecessor,
            "candidate_state_sha256": candidate,
            "candidate_state_object_sha256": candidate_object,
            "watermark": next_watermark.payload(),
            "watermark_status": status,
        }
        raw = canonical_json_bytes(body)
        digest = _hash_bytes(raw)
        path = self.objects / f"{digest}.json"
        try:
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            try:
                if path.read_bytes() != raw:
                    raise QiBoundaryError("Commit A hash collision")
            except OSError as exc:
                raise QiBoundaryError("committed boundary envelope is unreadable") from exc
        except OSError as exc:
            raise QiBoundaryError("committed boundary envelope is not durable") from exc
        if journal._read_head_sha256() != entry_head:
            raise QiBoundaryError("Commit A journal advanced concurrently")
        self._replace_pointer(self.head_path, digest)
        receipt = QiBoundaryCommitAReceipt(
            digest,
            entry_head,
            packet.event_id,
            predecessor,
            candidate,
            candidate_object,
            MappingProxyType(next_watermark.payload()),
        )
        return next_watermark, receipt

    def acknowledge(self, event_id: str) -> str:
        event_id = _text(event_id, "event_id")
        if not self.head_path.exists():
            raise QiBoundaryError("packet cannot be acknowledged before Commit A")
        try:
            digest = _sha256_identity(self.head_path.read_text(encoding="ascii").strip(), "committed object")
            path = self.objects / f"{digest}.json"
            raw = path.read_bytes()
            body = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise QiBoundaryError("committed boundary envelope is unreadable") from exc
        if _hash_bytes(raw) != digest or not isinstance(body, Mapping):
            raise QiBoundaryError("committed boundary envelope hash mismatch")
        if set(body) != {
            "schema",
            "journal_head_sha256",
            "frame_sha256",
            "event_id",
            "predecessor_head_sha256",
            "candidate_state_sha256",
            "candidate_state_object_sha256",
            "watermark",
            "watermark_status",
        } or body.get("schema") != BOUNDARY_COMMIT_A_SCHEMA:
            raise QiBoundaryError("committed boundary envelope schema is invalid")
        if body.get("event_id") != event_id:
            raise QiBoundaryError("acknowledgement event does not match committed envelope")
        _sha256_identity(body.get("journal_head_sha256"), "journal_head_sha256")
        _sha256_identity(body.get("frame_sha256"), "frame_sha256")
        _sha256_identity(body.get("predecessor_head_sha256"), "predecessor_head_sha256")
        _sha256_identity(body.get("candidate_state_sha256"), "candidate_state_sha256")
        _sha256_identity(body.get("candidate_state_object_sha256"), "candidate_state_object_sha256")
        if not isinstance(body.get("watermark"), Mapping):
            raise QiBoundaryError("committed watermark is invalid")
        return canonical_hash({"commit_sha256": digest, "event_id": event_id}, "cassi.qi-flow-boundary-ack.v1")


@dataclass(frozen=True, slots=True)
class QiPassiveEgressReceipt:
    committed: bool
    event_id: str | None
    energy_before: float
    energy_after: float
    injected_work: float
    uncertainty: float
    residual: float
    rejection_reason: str | None

    def payload(self) -> dict[str, Any]:
        body = {
            "schema": PASSIVE_EGRESS_SCHEMA,
            "committed": self.committed,
            "event_id": self.event_id,
            "energy_before": self.energy_before,
            "energy_after": self.energy_after,
            "injected_work": self.injected_work,
            "uncertainty": self.uncertainty,
            "residual": self.residual,
            "rejection_reason": self.rejection_reason,
            "no_time_advancement": True,
        }
        return {**body, "self_sha256": canonical_hash(body, PASSIVE_EGRESS_SCHEMA)}


def passive_egress_receipt(
    *,
    event_id: str,
    energy_before: float,
    energy_after: float,
    injected_work: float,
    uncertainty: float,
    tolerance: float,
    guard_valid: bool,
) -> QiPassiveEgressReceipt:
    before = _finite(energy_before, "energy_before")
    after = _finite(energy_after, "energy_after")
    work = _finite(injected_work, "injected_work")
    bound = _finite(uncertainty, "uncertainty")
    threshold = _finite(tolerance, "tolerance")
    if bound < 0.0 or threshold < 0.0:
        raise QiBoundaryError("passive egress uncertainty and tolerance must be nonnegative")
    residual = after - before - work
    valid = bool(guard_valid) and abs(residual) <= bound + threshold
    return QiPassiveEgressReceipt(
        valid,
        _text(event_id, "event_id") if valid else None,
        before,
        after,
        work,
        bound,
        residual,
        None if valid else ("guard-rejected" if not guard_valid else "energy-ledger-rejected"),
    )


__all__ = [
    "ANTIALIAS_RECEIPT_SCHEMA",
    "BOUNDARY_COMMIT_A_SCHEMA",
    "BOUNDARY_PACKET_SCHEMA",
    "NO_SAMPLE_SCHEMA",
    "QiActuatorDescriptor",
    "QiAntialiasReceipt",
    "QiAudioDescriptor",
    "QiBoundaryCommitAReceipt",
    "QiBoundaryCommitAStore",
    "QiBoundaryError",
    "QiBoundaryPacket",
    "QiIngressJournal",
    "QiJournalEntry",
    "QiLinearBoundaryPort",
    "QiOpticalDescriptor",
    "QiPassiveEgressReceipt",
    "QiProprioceptiveDescriptor",
    "QiTextDescriptor",
    "apply_antialias",
    "assert_disjoint_ports",
    "passive_egress_receipt",
]
