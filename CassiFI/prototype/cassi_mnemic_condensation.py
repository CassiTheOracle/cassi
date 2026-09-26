from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Sequence

import torch

from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldError, QiFieldState


MNEMIC_CONDENSATION_SCHEMA = "cassi.mnemic.condensation.v1"
MNEMIC_ADDRESS_SCHEMA = "cassicore.mnemic.condensation-address.v1"
_WORD = re.compile(r"[\w'-]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class MnemicCondensationConfig:
    cue_dimensions: int = 512
    address_bytes: int = 16
    scale_count: int = 4
    slow_retention: float = 0.9999
    maximum_mode_amplitude: float = 64.0
    minimum_recall_signal: float = 0.20
    minimum_recall_margin: float = 0.03
    minimum_recall_availability: float = 0.25

    def __post_init__(self) -> None:
        if self.cue_dimensions < 64 or self.cue_dimensions % 2 != 0:
            raise ValueError("cue_dimensions must be an even integer >= 64")
        if self.address_bytes < 8 or self.address_bytes > 32:
            raise ValueError("address_bytes must be in [8, 32]")
        if self.scale_count < 2:
            raise ValueError("scale_count must be >= 2")
        if not 0.0 < self.slow_retention <= 1.0:
            raise ValueError("slow_retention must be in (0, 1]")
        if self.maximum_mode_amplitude <= 0.0:
            raise ValueError("maximum_mode_amplitude must be positive")
        if self.minimum_recall_signal < 0.0 or self.minimum_recall_signal > 1.0:
            raise ValueError("minimum_recall_signal must be in [0, 1]")
        if self.minimum_recall_margin < 0.0 or self.minimum_recall_margin > 1.0:
            raise ValueError("minimum_recall_margin must be in [0, 1]")
        if self.minimum_recall_availability < 0.0:
            raise ValueError("minimum_recall_availability must be nonnegative")

    @property
    def address_bits(self) -> int:
        return self.address_bytes * 8

    @property
    def mode_count(self) -> int:
        return self.address_bits * self.cue_dimensions

    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "schema": MNEMIC_CONDENSATION_SCHEMA,
                "address_bytes": self.address_bytes,
                "cue_dimensions": self.cue_dimensions,
                "maximum_mode_amplitude": self.maximum_mode_amplitude,
                "minimum_recall_signal": self.minimum_recall_signal,
                "minimum_recall_margin": self.minimum_recall_margin,
                "minimum_recall_availability": self.minimum_recall_availability,
                "scale_count": self.scale_count,
                "slow_retention": self.slow_retention,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def mnemic_field_address(
    record_id: str,
    revision: str,
    start_byte: int,
    end_byte: int,
    semantic_kind: str,
    *,
    address_bytes: int = 16,
) -> bytes:
    if not isinstance(record_id, str) or not record_id:
        raise QiFieldError("record_id must be nonempty text")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision):
        raise QiFieldError("revision must be a lowercase SHA-256")
    if not isinstance(start_byte, int) or not isinstance(end_byte, int):
        raise QiFieldError("field address span must use integer byte offsets")
    if start_byte < 0 or end_byte < start_byte:
        raise QiFieldError("field address span must be ordered and nonnegative")
    if not isinstance(semantic_kind, str) or not semantic_kind:
        raise QiFieldError("semantic_kind must be nonempty text")
    if address_bytes < 8 or address_bytes > 32:
        raise QiFieldError("address_bytes must be in [8, 32]")
    canonical = json.dumps(
        [
            MNEMIC_ADDRESS_SCHEMA,
            record_id,
            revision,
            start_byte,
            end_byte,
            semantic_kind,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).digest()[:address_bytes]


@dataclass(frozen=True, slots=True)
class MnemicRecall:
    address: bytes | None
    signal: float
    availability: float
    selection_margin: float
    minimum_bit_margin: float
    mean_bit_margin: float
    state_sha256: str


@dataclass(frozen=True, slots=True)
class MnemicDepositReceipt:
    state_in_sha256: str
    state_deposit_sha256: str
    address_hex: str
    prediction_signal: float
    residual_rms: float


@dataclass(frozen=True, slots=True)
class MnemicCondensationReceipt:
    state_in_sha256: str
    state_out_sha256: str
    address_hex: str
    prediction_signal: float
    residual_rms: float
    slow_energy_before: float
    slow_energy_after: float


class MnemicCondensationController:
    """Field-owned cue-to-exact-address associative condensation.

    The only adaptive state is the supplied ``QiFieldState.field`` tensor. Text
    features and address bits are deterministic boundary codecs; no learned
    codebook, candidate index, or side cache participates in recall.
    """

    def __init__(self, config: MnemicCondensationConfig | None = None) -> None:
        self.config = config or MnemicCondensationConfig()
        self.qi_config = QiFieldConfig(
            scale_count=self.config.scale_count,
            mode_count=self.config.mode_count,
            alphabet_size=260,
            settle_steps=1,
        )
        self._state_codec = QiFieldController(self.qi_config)

    @property
    def config_fingerprint(self) -> str:
        return self.config.fingerprint()

    def initial_state(
        self,
        *,
        device: str | torch.device = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> QiFieldState:
        return self._state_codec.initial_state(1, device=device, dtype=dtype)

    def validate_state(self, state: QiFieldState) -> None:
        state.validate(self.qi_config)
        if not bool(torch.isfinite(state.field).all().item()):
            raise QiFieldError("mnemic condensation field contains non-finite values")
        maximum = float(state.field.abs().max().item())
        if maximum > self.config.maximum_mode_amplitude + 1.0e-6:
            raise QiFieldError("mnemic condensation field exceeds its amplitude bound")

    def state_sha256(self, state: QiFieldState) -> str:
        self.validate_state(state)
        owned = state.field.detach().cpu().contiguous()
        digest = hashlib.sha256(
            json.dumps(
                {
                    "schema": MNEMIC_CONDENSATION_SCHEMA,
                    "config_fingerprint": self.config_fingerprint,
                    "dtype": str(owned.dtype),
                    "shape": tuple(owned.shape),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        digest.update(b"\x00")
        digest.update(owned.numpy().tobytes(order="C"))
        return digest.hexdigest()

    def dump_state_bytes(self, state: QiFieldState) -> bytes:
        self.validate_state(state)
        return self._state_codec.dump_state_bytes(state)

    def load_state_bytes(
        self,
        payload: bytes,
        *,
        device: str | torch.device = "cpu",
    ) -> QiFieldState:
        state = self._state_codec.load_state_bytes(payload, device=device)
        self.validate_state(state)
        return state

    def cue_vector(self, text: str, *, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
        if not isinstance(text, str) or not text.strip():
            raise QiFieldError("mnemic cue must be nonempty text")
        normalized = unicodedata.normalize("NFKC", text).casefold()
        words = _WORD.findall(normalized)
        features: list[tuple[str, float]] = []
        features.extend((f"w:{word}", 1.0) for word in words)
        features.extend(
            (f"p:{words[index]}\0{words[index + 1]}", 1.5)
            for index in range(len(words) - 1)
        )
        compact = " ".join(words).encode("utf-8")
        for width, weight in ((2, 0.20), (3, 0.35), (4, 0.45)):
            features.extend(
                (f"b{width}:{compact[index:index + width].hex()}", weight)
                for index in range(max(0, len(compact) - width + 1))
            )
        if not features:
            features.append((f"raw:{normalized.encode('utf-8').hex()}", 1.0))

        vector = torch.zeros(self.config.cue_dimensions, device=device, dtype=dtype)
        for feature, weight in features:
            digest = hashlib.blake2b(
                feature.encode("utf-8"),
                digest_size=16,
                person=b"cassi-mnemic-v1",
            ).digest()
            index = int.from_bytes(digest[:8], "little") % self.config.cue_dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign * weight
        norm = vector.square().sum().sqrt()
        if float(norm.item()) <= 0.0:
            raise QiFieldError("mnemic cue encoded to zero work")
        return vector / norm

    def recall(
        self,
        state: QiFieldState,
        cue: str,
        *,
        candidate_addresses: Sequence[bytes],
    ) -> MnemicRecall:
        self.validate_state(state)
        state_hash = self.state_sha256(state)
        differential = self._differential(state)[-1]
        matrix = differential.reshape(self.config.address_bits, self.config.cue_dimensions)
        cue_vector = self.cue_vector(cue, device=matrix.device, dtype=matrix.dtype)
        logits = matrix @ cue_vector
        logit_norm = float(logits.norm().item())
        candidates = tuple(dict.fromkeys(candidate_addresses))
        for address in candidates:
            if len(address) != self.config.address_bytes:
                raise QiFieldError(
                    f"candidate address must contain {self.config.address_bytes} bytes"
                )
        if not candidates or logit_norm <= torch.finfo(logits.dtype).eps:
            return MnemicRecall(
                address=None,
                signal=0.0,
                selection_margin=0.0,
                availability=0.0,
                minimum_bit_margin=0.0,
                mean_bit_margin=0.0,
                state_sha256=state_hash,
            )

        codes = torch.stack([
            self._address_bits(address, device=matrix.device, dtype=matrix.dtype)
            for address in candidates
        ])
        scores = (codes @ logits) / (math.sqrt(self.config.address_bits) * logit_norm)
        order = torch.argsort(scores, descending=True)
        best_index = int(order[0].item())
        signal = float(scores[best_index].item())
        runner_up = float(scores[int(order[1].item())].item()) if len(candidates) > 1 else 0.0
        availability = logit_norm / math.sqrt(self.config.address_bits)
        margin = signal - runner_up
        best_code = codes[best_index]
        signed_margins = logits * best_code
        address = candidates[best_index] if (
            availability >= self.config.minimum_recall_availability
            and signal >= self.config.minimum_recall_signal
            and margin >= self.config.minimum_recall_margin
        ) else None
        return MnemicRecall(
            address=address,
            signal=signal,
            availability=availability,
            selection_margin=margin,
            minimum_bit_margin=float(signed_margins.min().item()),
            mean_bit_margin=float(signed_margins.mean().item()),
            state_sha256=state_hash,
        )

    def deposit(
        self,
        state: QiFieldState,
        *,
        cue: str,
        address: bytes,
        strength: float = 1.0,
    ) -> tuple[QiFieldState, MnemicDepositReceipt]:
        self.validate_state(state)
        if len(address) != self.config.address_bytes:
            raise QiFieldError(
                f"mnemic address must contain {self.config.address_bytes} bytes"
            )
        if not math.isfinite(strength) or strength <= 0.0 or strength > 8.0:
            raise QiFieldError("mnemic condensation strength must be in (0, 8]")

        state_in_sha256 = self.state_sha256(state)
        current = self._differential(state)[-1].reshape(
            self.config.address_bits,
            self.config.cue_dimensions,
        )
        cue_vector = self.cue_vector(cue, device=current.device, dtype=current.dtype)
        target = self._address_bits(address, device=current.device, dtype=current.dtype)
        predicted = current @ cue_vector
        residual = (target - predicted) * strength
        correction = residual[:, None] * cue_vector[None, :]

        deposited = state.clone()
        differential = self._differential(deposited)
        differential[0] = torch.clamp(
            differential[0] + correction.reshape(-1),
            min=-self.config.maximum_mode_amplitude,
            max=self.config.maximum_mode_amplitude,
        )
        self._write_differential(deposited, differential)
        self.validate_state(deposited)
        return deposited, MnemicDepositReceipt(
            state_in_sha256=state_in_sha256,
            state_deposit_sha256=self.state_sha256(deposited),
            address_hex=address.hex(),
            prediction_signal=float(predicted.abs().mean().item()),
            residual_rms=float(residual.square().mean().sqrt().item()),
        )


    def condense(
        self,
        state: QiFieldState,
        *,
        cue: str,
        address: bytes,
        strength: float = 1.0,
    ) -> tuple[QiFieldState, MnemicCondensationReceipt]:
        self.validate_state(state)
        state_in_sha256 = self.state_sha256(state)
        slow_before = self._slow_energy(state)
        deposited, deposit_receipt = self.deposit(
            state,
            cue=cue,
            address=address,
            strength=strength,
        )
        next_state = self.evolve(deposited, steps=self.config.scale_count - 1)
        slow_after = self._slow_energy(next_state)
        state_out_sha256 = self.state_sha256(next_state)
        return next_state, MnemicCondensationReceipt(
            state_in_sha256=state_in_sha256,
            state_out_sha256=state_out_sha256,
            address_hex=address.hex(),
            prediction_signal=deposit_receipt.prediction_signal,
            residual_rms=deposit_receipt.residual_rms,
            slow_energy_before=slow_before,
            slow_energy_after=slow_after,
        )

    def inhibit(
        self,
        state: QiFieldState,
        *,
        cue: str,
        address: bytes,
        strength: float = 1.0,
    ) -> QiFieldState:
        """Suppress one cue-to-address component without erasing other address outflow."""
        self.validate_state(state)
        if len(address) != self.config.address_bytes:
            raise QiFieldError(
                f"mnemic address must contain {self.config.address_bytes} bytes"
            )
        if not math.isfinite(strength) or strength <= 0.0 or strength > 1.0:
            raise QiFieldError("mnemic inhibition strength must be in (0, 1]")
        next_state = state.clone()
        differential = self._differential(next_state)
        slow = differential[-1].reshape(
            self.config.address_bits,
            self.config.cue_dimensions,
        )
        cue_vector = self.cue_vector(cue, device=slow.device, dtype=slow.dtype)
        target_code = self._address_bits(address, device=slow.device, dtype=slow.dtype)
        predicted = slow @ cue_vector
        target_signal = torch.clamp(
            (target_code @ predicted) / self.config.address_bits,
            min=0.0,
        )
        correction = (
            -strength
            * target_signal
            * target_code[:, None]
            * cue_vector[None, :]
        )
        differential[0] = torch.clamp(
            differential[0] + correction.reshape(-1),
            min=-self.config.maximum_mode_amplitude,
            max=self.config.maximum_mode_amplitude,
        )
        self._write_differential(next_state, differential)
        return self.evolve(next_state, steps=self.config.scale_count - 1)

    def evolve(self, state: QiFieldState, *, steps: int = 1) -> QiFieldState:
        self.validate_state(state)
        if not isinstance(steps, int) or steps < 0 or steps > 100_000:
            raise QiFieldError("mnemic evolution steps must be an integer in [0, 100000]")
        next_state = state.clone()
        differential = self._differential(next_state)
        for _ in range(steps):
            previous = differential.clone()
            differential.zero_()
            differential[1:] = previous[:-1]
            differential[-1] += previous[-1] * self.config.slow_retention
        differential.clamp_(
            min=-self.config.maximum_mode_amplitude,
            max=self.config.maximum_mode_amplitude,
        )
        self._write_differential(next_state, differential)
        self.validate_state(next_state)
        return next_state

    def lesion_slow_field(self, state: QiFieldState) -> QiFieldState:
        """Diagnostic field-only counterfactual; never used by the live runtime."""
        self.validate_state(state)
        next_state = state.clone()
        differential = self._differential(next_state)
        differential[-1].zero_()
        self._write_differential(next_state, differential)
        return next_state

    def diagnostics(self, state: QiFieldState) -> dict[str, Any]:
        self.validate_state(state)
        differential = self._differential(state)
        energies = differential.square().mean(dim=1)
        return {
            "schema": MNEMIC_CONDENSATION_SCHEMA,
            "config_fingerprint": self.config_fingerprint,
            "state_sha256": self.state_sha256(state),
            "scale_energy": [float(value) for value in energies.tolist()],
            "slow_energy": float(energies[-1].item()),
            "active_slow_modes": int((differential[-1].abs() > 1.0e-8).sum().item()),
        }

    def _address_bits(
        self,
        address: bytes,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        values = [
            1.0 if byte & (1 << (7 - bit)) else -1.0
            for byte in address
            for bit in range(8)
        ]
        return torch.tensor(values, device=device, dtype=dtype)

    def _differential(self, state: QiFieldState) -> torch.Tensor:
        packed = state.field.reshape(
            self.config.scale_count,
            9,
            self.config.mode_count,
            state.batch_size,
        )
        return packed[:, 0, :, 0] - self.qi_config.phi * packed[:, 2, :, 0]

    def _write_differential(self, state: QiFieldState, differential: torch.Tensor) -> None:
        packed = state.field.reshape(
            self.config.scale_count,
            9,
            self.config.mode_count,
            state.batch_size,
        )
        phi = self.qi_config.phi
        denominator = 1.0 + phi * phi
        packed[:, 0, :, 0] = differential / denominator
        packed[:, 2, :, 0] = -phi * differential / denominator
        packed[:, 1, :, 0].zero_()
        packed[:, 3, :, 0].zero_()
        packed[:, 4:8, :, 0].zero_()
        packed[:, 8, :, 0] = packed[:, 0, :, 0].square() + packed[:, 2, :, 0].square()

    def _slow_energy(self, state: QiFieldState) -> float:
        slow = self._differential(state)[-1]
        return float(slow.square().mean().item())
