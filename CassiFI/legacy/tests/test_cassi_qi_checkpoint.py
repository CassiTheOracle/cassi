from __future__ import annotations

import copy
import hashlib
import json
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import torch

import cassi_qi_field as cassi_qi_field_module
from cassi_qi_field import (
    QI_FLOW_STATE_V3_SCHEMA,
    QI_FLOW_STATE_V3_TENSOR_DOMAIN,
    QiFlowStateV3,
    dump_v3_state_bytes,
    load_v3_checkpoint,
    load_v3_state_bytes,
    save_v3_checkpoint,
)
from cassi_qi_profile import (
    PROFILE_MISMATCH,
    QiFlowProfile,
    canonical_hash,
    canonical_json_bytes,
    canonical_json_loads,
    derive_rectangular_profile_overrides,
    finite_bits,
)
_MAGIC = b"CASSI-QI-FLOW-STATE-V3\x00"
_HEADER_FIELDS = frozenset(
    {
        "schema",
        "layout_id",
        "profile_sha256",
        "contract_root_sha256",
        "state_contract_sha256",
        "execution_schedule_sha256",
        "topology_sha256",
        "source_identity_sha256",
        "backend",
        "dtype",
        "shape",
        "raw_byte_count",
        "source_raw_sha256",
        "state_sha256",
        "self_sha256",
    }
)


def _split_checkpoint(payload: bytes) -> tuple[dict[str, object], bytes]:
    prefix_size = len(_MAGIC) + 8
    assert payload.startswith(_MAGIC)
    header_size = struct.unpack(">Q", payload[len(_MAGIC):prefix_size])[0]
    header = canonical_json_loads(payload[prefix_size:prefix_size + header_size])
    assert isinstance(header, dict)
    return header, payload[prefix_size + header_size:]


def _join_checkpoint(header: dict[str, object], raw: bytes) -> bytes:
    encoded_header = canonical_json_bytes(header)
    return _MAGIC + struct.pack(">Q", len(encoded_header)) + encoded_header + raw


def _frame(value: bytes) -> bytes:
    return struct.pack(">Q", len(value)) + value


def _raw_state_sha256(header: dict[str, object], raw: bytes) -> str:
    shape = header["shape"]
    assert isinstance(shape, list) and len(shape) == 3
    dtype = header["dtype"]
    state_contract = header["state_contract_sha256"]
    assert isinstance(dtype, str)
    assert isinstance(state_contract, str)
    digest = hashlib.sha256()
    digest.update(_frame(QI_FLOW_STATE_V3_TENSOR_DOMAIN.encode("utf-8")))
    digest.update(_frame(state_contract.encode("ascii")))
    digest.update(_frame(dtype.encode("ascii")))
    digest.update(struct.pack(">I", len(shape)))
    for dimension in shape:
        assert isinstance(dimension, int)
        digest.update(struct.pack(">Q", dimension))
    digest.update(struct.pack(">Q", len(raw)))
    digest.update(raw)
    return digest.hexdigest()


def _reseal_header(
    header: dict[str, object],
    raw: bytes,
    *,
    rehash_raw_state: bool = False,
) -> dict[str, object]:
    sealed = copy.deepcopy(header)
    if rehash_raw_state:
        sealed["source_raw_sha256"] = hashlib.sha256(raw).hexdigest()
        sealed["state_sha256"] = _raw_state_sha256(sealed, raw)
    sealed.pop("self_sha256", None)
    sealed["self_sha256"] = canonical_hash(sealed, QI_FLOW_STATE_V3_SCHEMA)
    return sealed


def _raw_scalar_offset(
    header: dict[str, object],
    *,
    scale: int,
    component: int,
    mode: int,
    lane: int,
) -> int:
    shape = header["shape"]
    dtype = header["dtype"]
    assert isinstance(shape, list) and len(shape) == 3
    assert all(isinstance(dimension, int) for dimension in shape)
    assert isinstance(dtype, str)
    assert shape[1] % 9 == 0
    mode_count = shape[1] // 9
    scalar_bytes = 4 if dtype == "float32" else 8
    scalar_index = (
        (scale * 9 * mode_count + component * mode_count + mode) * shape[2] + lane
    )
    return scalar_index * scalar_bytes


def _write_raw_scalar(
    header: dict[str, object],
    raw: bytearray,
    *,
    scale: int,
    component: int,
    mode: int,
    lane: int,
    value: float,
) -> None:
    dtype = header["dtype"]
    assert isinstance(dtype, str)
    scalar_format = "<f" if dtype == "float32" else "<d"
    struct.pack_into(
        scalar_format,
        raw,
        _raw_scalar_offset(
            header,
            scale=scale,
            component=component,
            mode=mode,
            lane=lane,
        ),
        value,
    )


class QiFlowV3CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = QiFlowProfile.from_defaults()

    def _state(
        self,
        profile: QiFlowProfile | None = None,
        *,
        lanes: int = 2,
    ) -> QiFlowStateV3:
        selected = self.profile if profile is None else profile
        state = QiFlowStateV3.create(selected, batch_lanes=lanes)
        field_contract = selected.payload["field"]
        assert isinstance(field_contract, dict)
        mode_count = int(field_contract["mode_count"])
        active_site_counts = field_contract["active_site_counts"]
        assert isinstance(active_site_counts, list)
        with torch.no_grad():
            for scale, active_sites in enumerate(active_site_counts):
                assert isinstance(active_sites, int)
                for component in range(9):
                    start = component * mode_count
                    state.field[scale, start:start + active_sites, :].fill_(
                        (component + 1) / 100.0
                    )
        return state

    def _payload(
        self,
        profile: QiFlowProfile | None = None,
        *,
        lanes: int = 1,
    ) -> bytes:
        selected = self.profile if profile is None else profile
        return dump_v3_state_bytes(self._state(selected, lanes=lanes), selected)

    def _mutated_raw_payload(
        self,
        profile: QiFlowProfile,
        mutate: object,
    ) -> bytes:
        payload = self._payload(profile)
        header, raw = _split_checkpoint(payload)
        self.assertEqual(_raw_state_sha256(header, raw), header["state_sha256"])
        changed = bytearray(raw)
        assert callable(mutate)
        mutate(header, changed)
        changed_raw = bytes(changed)
        return _join_checkpoint(
            _reseal_header(header, changed_raw, rehash_raw_state=True),
            changed_raw,
        )

    def _header_mutation_payload(self, mutate: object) -> bytes:
        payload = self._payload()
        header, raw = _split_checkpoint(payload)
        assert callable(mutate)
        mutate(header)
        return _join_checkpoint(_reseal_header(header, raw), raw)

    def _assert_rejected_without_swap(
        self,
        payload: bytes,
        profile: QiFlowProfile | None = None,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        selected = self.profile if profile is None else profile
        predecessor = self._state(selected, lanes=1)
        before_bits = predecessor.field.view(torch.uint8).clone()
        before_hash = predecessor.state_sha256(selected)
        current = predecessor
        with self.assertRaises(PROFILE_MISMATCH):
            current = load_v3_state_bytes(payload, selected, device=device, dtype=dtype)
        self.assertIs(current, predecessor)
        self.assertTrue(torch.equal(predecessor.field.view(torch.uint8), before_bits))
        self.assertEqual(predecessor.state_sha256(selected), before_hash)

    def _profile_with_bounds(
        self,
        *,
        component_cap: str,
        amplitude_cap: str,
        density_cap: str,
        epsilon_cap: str,
    ) -> QiFlowProfile:
        field = copy.deepcopy(dict(self.profile.payload["field"]))
        existing_bounds = field["state_bounds"]
        assert isinstance(existing_bounds, dict)
        field["state_bounds"] = {
            "component_abs_max": [component_cap] * 9,
            "complex_amplitude_max": [amplitude_cap] * 4,
            "density_max": density_cap,
            "epsilon2_ema_max": epsilon_cap,
            "inactive_tail_value": existing_bounds["inactive_tail_value"],
        }
        return QiFlowProfile.from_defaults(overrides={"field": field})

    def _tail_profile(self) -> QiFlowProfile:
        field_contract = self.profile.payload["field"]
        assert isinstance(field_contract, dict)
        scale_count = int(field_contract["scale_count"])
        overrides = derive_rectangular_profile_overrides(
            self.profile,
            [[3, 8]] * scale_count,
        )
        return QiFlowProfile.from_defaults(overrides=overrides)

    def test_one_state_has_only_the_declared_finite_s9mb_tensor(self) -> None:
        state = self._state()
        tensors = [value for value in vars(state).values() if torch.is_tensor(value)]
        self.assertEqual(len(tensors), 1)
        self.assertIs(tensors[0], state.field)
        field_contract = self.profile.payload["field"]
        backend_contract = self.profile.payload["backend_contract"]
        assert isinstance(field_contract, dict)
        assert isinstance(backend_contract, dict)
        self.assertEqual(
            tuple(state.field.shape),
            (
                field_contract["scale_count"],
                9 * field_contract["mode_count"],
                2,
            ),
        )
        self.assertEqual(
            state.field.dtype,
            {"float32": torch.float32, "float64": torch.float64}[
                field_contract["dtype"]
            ],
        )
        self.assertEqual(state.field.device.type, backend_contract["device"])
        self.assertTrue(bool(torch.isfinite(state.field).all()))
        self.assertFalse(state.field.requires_grad)
        packed = state.field.reshape(
            int(field_contract["scale_count"]),
            9,
            int(field_contract["mode_count"]),
            2,
        )
        for scale, active_sites in enumerate(field_contract["active_site_counts"]):
            self.assertTrue(bool(torch.all(packed[scale, :, active_sites:, :] == 0.0)))
        state.validate(self.profile)

    def test_exact_v3_round_trip_preserves_raw_bits_hash_and_header_contract(self) -> None:
        state = self._state()
        expected_bits = state.field.view(torch.uint8).clone()
        expected_hash = state.state_sha256(self.profile)
        payload = dump_v3_state_bytes(state, self.profile)
        header, raw = _split_checkpoint(payload)
        self.assertEqual(set(header), _HEADER_FIELDS)
        self.assertNotIn("endianness", header)
        self.assertEqual(header["schema"], QI_FLOW_STATE_V3_SCHEMA)
        self.assertEqual(_raw_state_sha256(header, raw), header["state_sha256"])
        restored = load_v3_state_bytes(payload, self.profile, device="cpu")
        self.assertTrue(torch.equal(restored.field.view(torch.uint8), expected_bits))
        self.assertEqual(restored.state_sha256(self.profile), expected_hash)
        self.assertEqual(
            restored.identity_metadata(self.profile)["profile_sha256"],
            self.profile.profile_sha256,
        )

    def test_raw_state_hash_is_parented_only_by_state_contract(self) -> None:
        receipts = copy.deepcopy(dict(self.profile.payload["receipts"]))
        receipts["max_parents"] = int(receipts["max_parents"]) - 1
        evidence_only_profile = QiFlowProfile.from_defaults(
            overrides={"receipts": receipts}
        )
        self.assertNotEqual(evidence_only_profile.profile_sha256, self.profile.profile_sha256)
        self.assertEqual(
            evidence_only_profile.state_contract_sha256,
            self.profile.state_contract_sha256,
        )
        baseline = self._state(self.profile, lanes=1)
        evidence_only = self._state(evidence_only_profile, lanes=1)
        self.assertTrue(
            torch.equal(
                baseline.field.view(torch.uint8),
                evidence_only.field.view(torch.uint8),
            )
        )
        self.assertEqual(
            baseline.state_sha256(self.profile),
            evidence_only.state_sha256(evidence_only_profile),
        )

        state_contract_profile = self._profile_with_bounds(
            component_cap=finite_bits(0.25),
            amplitude_cap=finite_bits(0.25),
            density_cap=finite_bits(0.25),
            epsilon_cap=finite_bits(0.25),
        )
        self.assertNotEqual(
            state_contract_profile.state_contract_sha256,
            self.profile.state_contract_sha256,
        )
        changed_state_contract = self._state(state_contract_profile, lanes=1)
        self.assertTrue(
            torch.equal(
                baseline.field.view(torch.uint8),
                changed_state_contract.field.view(torch.uint8),
            )
        )
        self.assertNotEqual(
            baseline.state_sha256(self.profile),
            changed_state_contract.state_sha256(state_contract_profile),
        )

    def test_same_backend_file_restart_preserves_exact_raw_bits_and_hash(self) -> None:
        state = self._state()
        expected_bits = state.field.view(torch.uint8).clone()
        expected_hash = state.state_sha256(self.profile)
        with TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "state.qiflow"
            self.assertEqual(
                save_v3_checkpoint(checkpoint, state, self.profile),
                expected_hash,
            )
            restored = load_v3_checkpoint(checkpoint, self.profile, device="cpu")
        self.assertTrue(torch.equal(restored.field.view(torch.uint8), expected_bits))
        self.assertEqual(restored.state_sha256(self.profile), expected_hash)

    def test_rejected_in_memory_candidate_is_never_repaired_or_mutated(self) -> None:
        field_contract = self.profile.payload["field"]
        assert isinstance(field_contract, dict)
        mode_count = int(field_contract["mode_count"])
        for value in (-0.125, -0.0):
            with self.subTest(epsilon2_ema=value):
                candidate = self._state(lanes=1)
                candidate.field[0, 8 * mode_count, 0] = value
                before_bits = candidate.field.view(torch.uint8).clone()
                with self.assertRaises(PROFILE_MISMATCH):
                    candidate.validate(self.profile)
                self.assertTrue(torch.equal(candidate.field.view(torch.uint8), before_bits))
                with self.assertRaises(PROFILE_MISMATCH):
                    QiFlowStateV3.from_field(self.profile, candidate.field)
                self.assertTrue(torch.equal(candidate.field.view(torch.uint8), before_bits))
                with self.assertRaises(PROFILE_MISMATCH):
                    dump_v3_state_bytes(candidate, self.profile)
                self.assertTrue(torch.equal(candidate.field.view(torch.uint8), before_bits))

    def test_v1_v2_and_malformed_payloads_are_rejected_without_predecessor_swap(self) -> None:
        for payload in (
            b"CASSI-QI-FLOW-STATE-V1\x00legacy",
            b"CASSI-QI-FLOW-STATE-V2\x00legacy",
            b"PK\x03\x04legacy-torch-payload",
            b'{"schema":"cassi.qi.field-state.v2"}',
            b'{"schema":"cassi.qi-flow-session.v2"}',
        ):
            with self.subTest(payload=payload[:32]):
                self._assert_rejected_without_swap(payload)

    def test_header_schema_and_every_authenticated_identity_mismatch_rejects(self) -> None:
        mutations: tuple[tuple[str, object], ...] = (
            ("schema", "cassi.qi-flow-state.v2"),
            ("layout_id", "wrong-layout"),
            ("profile_sha256", "0" * 64),
            ("contract_root_sha256", "0" * 64),
            ("state_contract_sha256", "0" * 64),
            ("execution_schedule_sha256", "0" * 64),
            ("topology_sha256", "0" * 64),
            ("source_identity_sha256", "0" * 64),
            ("backend", "cuda"),
            ("dtype", "float32"),
            ("source_raw_sha256", "0" * 64),
            ("state_sha256", "0" * 64),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                self._assert_rejected_without_swap(
                    self._header_mutation_payload(
                        lambda header, key=key, value=value: header.__setitem__(key, value)
                    )
                )

        payload = self._payload()
        header, raw = _split_checkpoint(payload)
        wrong_self = copy.deepcopy(header)
        wrong_self["self_sha256"] = "0" * 64
        self._assert_rejected_without_swap(_join_checkpoint(wrong_self, raw))

        alternate_profile = QiFlowProfile.from_defaults(profile_id="different-profile")
        self._assert_rejected_without_swap(payload, alternate_profile)

    def test_header_shape_batch_dtype_and_raw_size_mismatches_reject_before_restore(self) -> None:
        payload = self._payload()
        header, raw = _split_checkpoint(payload)
        shape = header["shape"]
        assert isinstance(shape, list) and len(shape) == 3

        def with_shape(new_shape: object) -> bytes:
            candidate = copy.deepcopy(header)
            candidate["shape"] = new_shape
            return _join_checkpoint(_reseal_header(candidate, raw), raw)

        field_contract = self.profile.payload["field"]
        assert isinstance(field_contract, dict)
        shape_mutations = (
            [shape[0] + 1, shape[1], shape[2]],
            [shape[0], shape[1] + 1, shape[2]],
            [shape[0], shape[1], field_contract["batch_limit"] + 1],
            [shape[0], shape[1], True],
            [shape[0], shape[1]],
        )
        for new_shape in shape_mutations:
            with self.subTest(shape=new_shape):
                self._assert_rejected_without_swap(with_shape(new_shape))

        wrong_count = copy.deepcopy(header)
        wrong_count["raw_byte_count"] = int(header["raw_byte_count"]) + 1
        self._assert_rejected_without_swap(
            _join_checkpoint(_reseal_header(wrong_count, raw), raw)
        )
        self._assert_rejected_without_swap(payload[:-1])
        self._assert_rejected_without_swap(payload + b"\x00")

        extra = copy.deepcopy(header)
        extra["extra_tensor"] = {"forbidden": 1}
        self._assert_rejected_without_swap(_join_checkpoint(_reseal_header(extra, raw), raw))
        adaptive = copy.deepcopy(header)
        adaptive["adaptive_map"] = {"forbidden": 1}
        self._assert_rejected_without_swap(
            _join_checkpoint(_reseal_header(adaptive, raw), raw)
        )

        self._assert_rejected_without_swap(payload, dtype=torch.float32)
        self._assert_rejected_without_swap(payload, device="cuda")
        field_contract = self.profile.payload["field"]
        assert isinstance(field_contract, dict)
        with self.assertRaises(PROFILE_MISMATCH):
            QiFlowStateV3.create(
                self.profile,
                batch_lanes=int(field_contract["batch_limit"]) + 1,
            )

    def test_fixed_little_endian_schema_rejects_unsupported_host_before_allocation(self) -> None:
        payload = self._payload()
        predecessor = self._state(lanes=1)
        before_bits = predecessor.field.view(torch.uint8).clone()
        with patch.object(cassi_qi_field_module.sys, "byteorder", "big"):
            with self.assertRaises(PROFILE_MISMATCH):
                load_v3_state_bytes(payload, self.profile)
        self.assertTrue(torch.equal(predecessor.field.view(torch.uint8), before_bits))

    def test_resealed_nonfinite_raw_scalars_reject_without_predecessor_swap(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self._assert_rejected_without_swap(
                    self._mutated_raw_payload(
                        self.profile,
                        lambda header, raw, value=value: _write_raw_scalar(
                            header,
                            raw,
                            scale=0,
                            component=0,
                            mode=0,
                            lane=0,
                            value=value,
                        ),
                    )
                )

    def test_profile_rejects_non_little_endian_storage_before_tensor_materialization(self) -> None:
        field_contract = copy.deepcopy(dict(self.profile.payload["field"]))
        field_contract["byte_order"] = "big"
        with patch.object(
            cassi_qi_field_module.torch,
            "frombuffer",
            side_effect=AssertionError("wrong endian reached raw tensor materialization"),
        ) as frombuffer:
            with self.assertRaises(PROFILE_MISMATCH):
                QiFlowProfile.from_defaults(overrides={"field": field_contract})
        frombuffer.assert_not_called()

    def test_invalid_raw_rejects_before_tensor_materialization(self) -> None:
        payload = self._mutated_raw_payload(
            self.profile,
            lambda header, raw: _write_raw_scalar(
                header,
                raw,
                scale=0,
                component=8,
                mode=0,
                lane=0,
                value=-0.125,
            ),
        )
        with patch.object(
            cassi_qi_field_module.torch,
            "frombuffer",
            side_effect=AssertionError("raw admission allocated a tensor"),
        ):
            self._assert_rejected_without_swap(payload)

    def test_resealed_negative_ema_and_each_declared_bound_reject_without_swap(self) -> None:
        for value in (-0.125, -0.0):
            with self.subTest(epsilon2_ema=value):
                self._assert_rejected_without_swap(
                    self._mutated_raw_payload(
                        self.profile,
                        lambda header, raw, value=value: _write_raw_scalar(
                            header,
                            raw,
                            scale=0,
                            component=8,
                            mode=0,
                            lane=0,
                            value=value,
                        ),
                    )
                )

        half = finite_bits(0.5)
        quarter = finite_bits(0.25)
        one = finite_bits(1.0)
        component_profile = self._profile_with_bounds(
            component_cap=quarter,
            amplitude_cap=half,
            density_cap=one,
            epsilon_cap=half,
        )
        self._assert_rejected_without_swap(
            self._mutated_raw_payload(
                component_profile,
                lambda header, raw: _write_raw_scalar(
                    header,
                    raw,
                    scale=0,
                    component=0,
                    mode=0,
                    lane=0,
                    value=0.3,
                ),
            ),
            component_profile,
        )

        amplitude_profile = self._profile_with_bounds(
            component_cap=half,
            amplitude_cap=quarter,
            density_cap=one,
            epsilon_cap=half,
        )

        def violate_amplitude(header: dict[str, object], raw: bytearray) -> None:
            _write_raw_scalar(
                header,
                raw,
                scale=0,
                component=0,
                mode=0,
                lane=0,
                value=0.2,
            )
            _write_raw_scalar(
                header,
                raw,
                scale=0,
                component=1,
                mode=0,
                lane=0,
                value=0.2,
            )

        self._assert_rejected_without_swap(
            self._mutated_raw_payload(amplitude_profile, violate_amplitude),
            amplitude_profile,
        )

        density_profile = self._profile_with_bounds(
            component_cap=half,
            amplitude_cap=half,
            density_cap=quarter,
            epsilon_cap=half,
        )

        def violate_density(header: dict[str, object], raw: bytearray) -> None:
            for component in (0, 2, 4, 6):
                _write_raw_scalar(
                    header,
                    raw,
                    scale=0,
                    component=component,
                    mode=0,
                    lane=0,
                    value=0.3,
                )

        self._assert_rejected_without_swap(
            self._mutated_raw_payload(density_profile, violate_density),
            density_profile,
        )

        ema_profile = self._profile_with_bounds(
            component_cap=half,
            amplitude_cap=half,
            density_cap=one,
            epsilon_cap=quarter,
        )
        self._assert_rejected_without_swap(
            self._mutated_raw_payload(
                ema_profile,
                lambda header, raw: _write_raw_scalar(
                    header,
                    raw,
                    scale=0,
                    component=8,
                    mode=0,
                    lane=0,
                    value=0.3,
                ),
            ),
            ema_profile,
        )

    def test_per_scale_active_tail_requires_exact_positive_zero(self) -> None:
        tail_profile = self._tail_profile()
        self.assertEqual(tail_profile.contract_root_sha256, self.profile.contract_root_sha256)
        self.assertEqual(tail_profile.payload["schema"], self.profile.payload["schema"])
        field_contract = tail_profile.payload["field"]
        assert isinstance(field_contract, dict)
        active_counts = field_contract["active_site_counts"]
        assert isinstance(active_counts, list)
        self.assertEqual(active_counts, [24] * 4)
        capacity = tail_profile.payload["scale_geometry"]["capacity"]
        assert isinstance(capacity, dict)
        self.assertEqual(capacity["active_state_bytes_at_batch_limit"], 27648)
        self.assertEqual(capacity["padded_state_bytes_at_batch_limit"], 9216)

        valid = self._state(tail_profile, lanes=1)
        valid_payload = dump_v3_state_bytes(valid, tail_profile)
        restored = load_v3_state_bytes(valid_payload, tail_profile)
        self.assertTrue(
            torch.equal(restored.field.view(torch.uint8), valid.field.view(torch.uint8))
        )

        for tail_value in (0.125, -0.0):
            with self.subTest(tail_value=tail_value):
                self._assert_rejected_without_swap(
                    self._mutated_raw_payload(
                        tail_profile,
                        lambda header, raw, tail_value=tail_value: _write_raw_scalar(
                            header,
                            raw,
                            scale=0,
                            component=0,
                            mode=24,
                            lane=0,
                            value=tail_value,
                        ),
                    ),
                    tail_profile,
                )

    def test_header_is_strict_canonical_json_and_raw_values_are_fixed_little_endian(self) -> None:
        state = self._state(lanes=1)
        state.field[0, 0, 0] = 0.125
        payload = dump_v3_state_bytes(state, self.profile)
        header, raw = _split_checkpoint(payload)
        scalar_format = "<f" if header["dtype"] == "float32" else "<d"
        self.assertEqual(raw[: struct.calcsize(scalar_format)], struct.pack(scalar_format, 0.125))

        noncanonical_header = json.dumps(
            header,
            ensure_ascii=False,
            sort_keys=False,
            separators=(", ", ": "),
        ).encode("utf-8")
        malformed = (
            _MAGIC
            + struct.pack(">Q", len(noncanonical_header))
            + noncanonical_header
            + raw
        )
        self._assert_rejected_without_swap(malformed)

    def test_float32_profile_layout_round_trips_without_conversion(self) -> None:
        float32_field = copy.deepcopy(dict(self.profile.payload["field"]))
        float32_field["dtype"] = "float32"
        float32_profile = QiFlowProfile.from_defaults(
            overrides={"field": float32_field}
        )
        state = self._state(float32_profile, lanes=1)
        state.field[0, 0, 0] = 0.125
        restored = load_v3_state_bytes(
            dump_v3_state_bytes(state, float32_profile),
            float32_profile,
        )
        self.assertEqual(restored.field.dtype, torch.float32)
        self.assertTrue(
            torch.equal(restored.field.view(torch.uint8), state.field.view(torch.uint8))
        )

if __name__ == "__main__":
    unittest.main()
