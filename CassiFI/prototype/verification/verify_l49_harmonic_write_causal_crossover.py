"""Source-independent verifier for the frozen L49 causal crossover board."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
ROOT=Path(__file__).resolve().parents[1]
L40_INPUTS = (
    (
        ROOT / "_diag/l40-rolling-ordered-relational-recall/l40-rolling-board.json",
        "44a0baff773c85405c35e0d92da405e8157e3617b811da75f6d2f00e88811530",
    ),
    (
        ROOT / "_diag/l40-rolling-ordered-relational-recall/l40-rolling-traces.npz",
        "21549f5bd65fd6e10247295bf59b48d6b35ed1b4d1b1a0a857fffafce32f045a",
    ),
    (
        ROOT / "artifacts/l40-rolling-ordered-relational-recall/l40-rolling-verification.json",
        "b5fd0f085e876eebd589dc7cf8a6353d20b93e1616c014f13d77c11a8aca8ca7",
    ),
)
PREFIX_FIELD_HASHES = np.asarray(
    (
        "e8370b2ebbe4d3afb155cf2a5fd3d866462f8d7b7481806536ef103c30c8a15c",
        "493a231a6606a7530b959880646b34e9142c9bdf577057e940211b33974ae1f2",
    )
)
BOARD_SCHEMA="cassi.l49.harmonic-write-causal-crossover-board.v1"; TRACE_SCHEMA="cassi.l49.harmonic-write-causal-crossover-traces.v1"; VERIFICATION_SCHEMA="cassi.l49.harmonic-write-causal-crossover-verification.v1"
LAYOUT_PROFILE="cassi.qi-cyclic-chromatic-coordinate-native.v1"; ORDERED_PROFILE="cassi.qi-ordered-relational-chromatic-recall.v1"; HARMONIC_PROFILE="cassi.qi-harmonic-age-ladder.v1"; PROJECTION_PROFILE="cassi.qi-cyclic-chromatic-projection.v1"
PREREGISTRATION=ROOT/"designs/L49-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md"; DEFAULT_BOARD=ROOT/"_diag/l49-harmonic-write-causal-crossover/l49-board.json"; DEFAULT_OUTPUT=ROOT/"artifacts/l49-harmonic-write-causal-crossover"; DEFAULT_REPORT=DEFAULT_OUTPUT/"L49-HARMONIC-WRITE-CAUSAL-CROSSOVER-REPORT.md"; DEFAULT_JSON=DEFAULT_OUTPUT/"l49-verification.json"
CHANNELS,MODE_COUNT,WIDTH,ALPHABET,BATCH=7,2048,1024,260,8; FLOOR=1e-8; ATOL_NATIVE=RTOL_NATIVE=3e-6; ATOL_SCORE=3e-5; RTOL_SCORE=2e-4
AGE_HARMONICS=np.asarray((1,2,3,4,5,6,0),dtype=np.int64); S0=np.asarray((0,37,74,111,148,185,222,259),dtype=np.int64); S1=(S0+97)%ALPHABET; S2=(S0+181)%ALPHABET; S3=S1; STAGES=np.stack((S0,S1,S2,S3)); BRANCH_NAMES=np.asarray(("I","U","W","UW")); BRANCH_CHECKPOINTS=np.asarray(("immediate","tick-8","tick-16","tick-128")); SEQUENCE_CHECKPOINTS=np.asarray(("s1-deposit","s1-horizon","s2-deposit","s2-horizon","s3-reversal-deposit","s3-reversal-horizon"))
EXPECTED_SOURCES: dict[str, str | None]
EXPECTED_SOURCES={"cassi_qi_profile.py":"d6eda20a1cf45032191d8f52ece3c4cffca3dfafa83b0052dd1bd89b8f738238","cassi_qi_field.py":"31ca9a9c878b5397f96cffc6aaa7245b2d0cc70847b8d8c04e5a6881c3393b9b","cassi_prismatic_field.py":"dc3fc1143c762ee0b9e024f3f8e2a7d8a4353c60c55403b344ff01785ec41b29","cassi_white_chromatic_field.py":"3ca4f7d9eb28f0e8450338f88498e03e02551d65d7146ea0607b9490fe283674","cassi_cyclic_chromatic_field.py":"643310f91d468771daf1a0a162999b473f9775246798b32b4411b58be47caf6b","cassi_relational_chromatic_field.py":"87fefae8a9d73c2ba420a547bc5bf48207567e8f0495237e04736a599304b978","cassi_ordered_relational_field.py":"c02260a0f0e778ad811a3fdc04b0c6493775d808fcef3458d88391928f978380","cassi_harmonic_age_field.py":"b4f053f2d441bf612842a88ed13a02d2554bc31c5711a460a9c72bfef417aa61","verification/run_l30_white_chromatic_field.py":"0b38a76aeb476f4d20c3dbd81e39fe1c6abe105f735574cf5c9b6a1bc08976dc","verification/verify_l30_white_chromatic_field.py":"48bddc4b97b77a174de3885ec42886b78e623c19f74c0acab32cf6e607b24405","verification/run_l40_rolling_ordered_relational_recall.py":"490322bb0b11bbf3e3c8f95badd254bf6737b4831abc9cea2d3eac7fe58c1e09","verification/verify_l40_rolling_ordered_relational_recall.py":"756e02f5b33ad88b3d8cf11eb7412ae3003f125d1780a288c573e10288b80202","designs/L46-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md":"1177ad06111a7c99037595d288d6fc80b6437c6c3167cf15c4e96c7df2add18e","designs/L48-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md":"0a7c98a3637ef79796e09b913e2c619f592810904453ce30125a71bc1cc7b58f"}
EXPECTED_SOURCES.update({"designs/L49-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md":"eb81b088fca5b16744a0c7a9188b5cbb0f5d1d947af3af79738524382befa312","tests/test_l49_harmonic_write_causal_crossover.py":None,"verification/run_l49_harmonic_write_causal_crossover.py":None,"verification/verify_l49_harmonic_write_causal_crossover.py":None})
class L49VerificationError(RuntimeError): pass
def _need(ok:bool,msg:str)->None:
    if not ok: raise L49VerificationError(msg)
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _finite_tree(value: Any, label: str = "JSON") -> None:
    if value is None or isinstance(value, (bool, str, int)):
        return
    if isinstance(value, float):
        _need(math.isfinite(value), f"{label} is nonfinite")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _finite_tree(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _need(isinstance(key, str), f"{label} has a non-string key")
            _finite_tree(item, f"{label}.{key}")
        return
    raise L49VerificationError(
        f"{label} has unsupported JSON value {type(value).__name__}"
    )


def load_json(path: Path) -> Mapping[str, Any]:
    raw = path.read_bytes()
    value = json.loads(
        raw.decode("utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(
            ValueError(item)
        ),
    )
    _need(isinstance(value, Mapping), "board must be an object")
    _finite_tree(value)
    _need(raw == canonical_bytes(value), "board JSON is not canonical")
    return value


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    _need(isinstance(value, Mapping), f"{label} must be an object")
    return value


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
def _sha_array(a:np.ndarray)->str:return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def _close(a:np.ndarray,b:np.ndarray,label:str,score=False)->None:_need(np.allclose(a,b,atol=ATOL_SCORE if score else ATOL_NATIVE,rtol=RTOL_SCORE if score else RTOL_NATIVE),f"{label} reconstruction mismatch")
def semantic_compare(recorded_scores,recorded_symbols,recorded_available,expected_scores,expected_symbols,expected_available,label):
    if not np.allclose(recorded_scores,expected_scores,atol=ATOL_SCORE,rtol=RTOL_SCORE): raise L49VerificationError(f"{label} score reconstruction mismatch")
    if not np.array_equal(recorded_available,expected_available): raise L49VerificationError(f"{label} availability reconstruction mismatch")
    both=np.asarray(recorded_available,bool)&np.asarray(expected_available,bool); am=both&(recorded_symbols!=expected_symbols); um=(~both)&(recorded_symbols!=expected_symbols)
    if bool(am.any()): raise L49VerificationError(f"{label} available winner reconstruction mismatch")
    return {"available_winner_mismatches":int(am.sum()),"ignored_unavailable_winner_mismatches":int(um.sum())}
def _field_dimensions(field) -> tuple[int, int]:
    _need(
        field.ndim == 3
        and field.shape[0] == CHANNELS
        and field.shape[1] % 18 == 0,
        "native field layout mismatch",
    )
    mode_count = field.shape[1] // 9
    return mode_count, mode_count // 2


def native_coordinates(field):
    mode_count, width = _field_dimensions(field)
    packed = field.reshape(
        CHANNELS, 9, mode_count, field.shape[-1]
    )
    return tuple(
        packed[:, index, :width]
        + 1j * packed[:, index + 1, :width]
        for index in (0, 2, 4, 6)
    )
def _pack(field, coords):
    mode_count, width = _field_dimensions(field)
    out = np.array(field, copy=True)
    packed = out.reshape(
        CHANNELS, 9, mode_count, field.shape[-1]
    )
    for index, value in zip((0, 2, 4, 6), coords):
        packed[:, index, :width] = value.real
        packed[:, index + 1, :width] = value.imag
        packed[:, index : index + 2, width:] = 0.0
    packed[:, 8, width:] = 0.0
    return out
def lift_field(field):
    c,d,vc,vd=native_coordinates(field); phase=np.exp(2j*np.pi*np.arange(CHANNELS)/CHANNELS)[:,None,None]; return _pack(field,(c,phase*d,vc,phase*vd))
def _dynamic_energy(field):
    mode_count, width = _field_dimensions(field)
    packed = field.reshape(
        CHANNELS, 9, mode_count, field.shape[-1]
    )
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    return (
        (packed[:, :8, :width].astype(np.float64) ** 2)
        .sum(axis=1)
        .mean(axis=1)
        / (1.0 + phi * phi)
    )
def bare_write_field(field, codebook, symbols):
    mode_count, width = _field_dimensions(field)
    _need(
        codebook.shape[1] == width,
        "codebook width does not match field layout",
    )
    c, d, vc, vd = native_coordinates(field)
    selected = codebook[symbols, :, 0] + 1j * codebook[symbols, :, 1]
    phase = np.exp(2j * np.pi * np.arange(CHANNELS) / CHANNELS)
    white = np.full(CHANNELS, 1.0 / math.sqrt(CHANNELS))
    direction = (
        phase[:, None, None]
        * selected.T[None, :, :]
        / math.sqrt(CHANNELS)
    )
    carrier = np.sum(white[:, None, None] * c, axis=0)
    chromatic = np.sum(np.conjugate(direction) * d, axis=0)
    carrier_velocity = np.sum(white[:, None, None] * vc, axis=0)
    chromatic_velocity = np.sum(np.conjugate(direction) * vd, axis=0)
    alpha = np.asarray(0.5 * np.pi, dtype=field.dtype)
    cosine, sine = np.cos(alpha), np.sin(alpha)
    new_chromatic = cosine * chromatic + sine * carrier
    new_carrier = cosine * carrier - sine * chromatic
    new_chromatic_velocity = (
        cosine * chromatic_velocity + sine * carrier_velocity
    )
    new_carrier_velocity = (
        cosine * carrier_velocity - sine * chromatic_velocity
    )
    c = c + white[:, None, None] * (new_carrier - carrier)[None]
    d = d + direction * (new_chromatic - chromatic)[None]
    vc = vc + white[:, None, None] * (
        new_carrier_velocity - carrier_velocity
    )[None]
    vd = vd + direction * (
        new_chromatic_velocity - chromatic_velocity
    )[None]
    result = _pack(field, (c, d, vc, vd))
    packed = result.reshape(
        CHANNELS, 9, mode_count, field.shape[-1]
    )
    active = packed[:, :8, :width]
    clamped = np.clip(active, -8.0, 8.0)
    clamps = int(np.count_nonzero(active != clamped))
    packed[:, :8, :width] = clamped
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    energy = (
        (clamped.astype(np.float64) ** 2).sum(axis=1).mean(axis=1)
        / (1.0 + phi * phi)
    )
    excessive = energy > 4.0
    factors = np.where(
        excessive,
        np.sqrt(4.0 / np.maximum(energy, 1.0e-30)),
        1.0,
    )
    packed[:, :8, :width] *= factors[:, None, None, :]
    clamps += int(excessive.sum())
    epsilon = packed[:, 8, :width]
    bounded_epsilon = np.clip(epsilon, 0.0, 4096.0)
    clamps += int(np.count_nonzero(epsilon != bounded_epsilon))
    packed[:, 8, :width] = bounded_epsilon
    packed[:, :, width:] = 0.0
    before = _dynamic_energy(field).mean(axis=0)
    after = _dynamic_energy(result).mean(axis=0)
    drift = np.where(
        (before == 0.0) & (after == 0.0),
        0.0,
        (after - before)
        / np.maximum(np.abs(before), np.finfo(np.float64).eps),
    )
    return result, drift.astype(field.dtype, copy=False), clamps
def reconstruct_readouts(field, codebook):
    width = codebook.shape[1]
    _need(
        _field_dimensions(field)[1] == width,
        "readout codebook width does not match field layout",
    )
    common, differential, _, differential_velocity = (
        native_coordinates(field)
    )
    code = codebook[..., 0] + 1j * codebook[..., 1]
    channel_phase = np.exp(
        2j * np.pi * np.arange(CHANNELS) / CHANNELS
    )

    channel_coefficients = np.einsum(
        "sw,jwb->jbs",
        np.conjugate(code),
        differential,
        optimize=True,
    ) / width
    aligned = (
        np.conjugate(channel_phase)[:, None, None]
        * channel_coefficients
    )
    current_scores = (
        np.abs(aligned.sum(axis=0) / math.sqrt(CHANNELS)) ** 2
    )
    current_symbols = np.argmax(current_scores, axis=1).astype(np.int64)
    rms = np.sqrt(np.mean(np.abs(differential) ** 2, axis=1))
    current_available = (
        np.mean(np.abs(differential) ** 2, axis=(0, 1)) >= FLOOR
    ) & ((rms >= FLOOR).sum(axis=0) >= 2)

    common_carrier = common.sum(axis=0) / math.sqrt(CHANNELS)
    differential_carrier = (
        np.conjugate(channel_phase)[:, None, None] * differential
    ).sum(axis=0) / math.sqrt(CHANNELS)
    relational_trace = -(common_carrier * differential_carrier)
    relational_coefficients = np.einsum(
        "sw,wb->bs",
        np.conjugate(code),
        relational_trace,
        optimize=True,
    ) / width
    relational_scores = np.abs(relational_coefficients) ** 2
    relational_symbols = np.argmax(
        relational_scores, axis=1
    ).astype(np.int64)
    relational_available = current_available & (
        np.max(relational_scores, axis=1) >= FLOOR
    )

    current_scale = np.maximum(
        np.max(current_scores, axis=1, keepdims=True), FLOOR
    )
    relational_scale = np.maximum(
        np.max(relational_scores, axis=1, keepdims=True), FLOOR
    )
    ordered_scores = np.maximum(
        current_scores / current_scale,
        relational_scores / relational_scale,
    )
    for row in range(field.shape[-1]):
        if not current_available[row]:
            ordered_scores[row] = current_scores[row]
            continue
        if (
            relational_available[row]
            and relational_symbols[row] != current_symbols[row]
        ):
            ordered_scores[row, relational_symbols[row]] = 2.0
        ordered_scores[row, current_symbols[row]] = 3.0

    basis = (
        np.conjugate(channel_phase)[None, :]
        ** np.arange(CHANNELS)[:, None]
    )
    physical_d = np.einsum(
        "kj,jmb->kmb", basis, differential, optimize=True
    ) / math.sqrt(CHANNELS)
    physical_vd = np.einsum(
        "kj,jmb->kmb", basis, differential_velocity, optimize=True
    ) / math.sqrt(CHANNELS)
    age_d = physical_d[AGE_HARMONICS]
    age_vd = physical_vd[AGE_HARMONICS]
    coefficients = np.einsum(
        "sw,kwb->bks",
        np.conjugate(code),
        age_d,
        optimize=True,
    ) / width
    age_scores = np.abs(coefficients) ** 2
    age_symbols = np.argmax(age_scores, axis=2).astype(np.int64)
    age_available = current_available[:, None] & (
        np.max(age_scores, axis=2) >= FLOOR
    )
    current_predecessor = np.stack(
        (age_symbols[:, 0], age_symbols[:, 1]), axis=1
    )
    current_predecessor = current_predecessor.astype(np.int64, copy=False)
    current_predecessor[~age_available[:, 0], 0] = -1
    current_predecessor[~age_available[:, 1], 1] = -1

    return {
        "physical_d": physical_d,
        "physical_vd": physical_vd,
        "age_d": age_d,
        "age_vd": age_vd,
        "coefficients": coefficients,
        "age_scores": age_scores.astype(np.float32),
        "age_energies": np.mean(np.abs(age_d) ** 2, axis=1)
        .T.astype(np.float32),
        "age_symbols": age_symbols,
        "age_available": age_available,
        "current_scores": current_scores.astype(np.float32),
        "current_symbols": current_symbols,
        "current_available": current_available,
        "relational_scores": relational_scores.astype(np.float32),
        "relational_symbols": relational_symbols,
        "relational_available": relational_available,
        "ordered_scores": ordered_scores.astype(np.float32),
        "ordered_current_symbols": current_symbols,
        "ordered_relational_symbols": relational_symbols,
        "ordered_current_available": current_available,
        "ordered_relational_available": relational_available,
        "current_predecessor": current_predecessor,
    }
def _check_arrays(a):
    shapes={"schema_id":(),"branch_names":(4,),"branch_checkpoint_names":(4,),"sequence_checkpoint_names":(6,),"stage_symbols":(4,8),"codebook":(260,1024,2),"channel_phase":(7,2),"prefix_field_sha256":(2,),"fork_field_sha256":(4,),"s1_symbol_sha256":(),"prefix_checkpoint_fields":(2,7,18432,8),"prefix_post_readout_fields":(2,7,18432,8),"prefix_emitted_symbols":(2,8),"prefix_current_symbols":(2,8),"prefix_relational_symbols":(2,8),"prefix_current_available":(2,8),"prefix_relational_available":(2,8),"prefix_current_scores":(2,8,260),"prefix_relational_scores":(2,8,260),"prefix_ordered_scores":(2,8,260),"prefix_clamp_counts":(18,),"prefix_input_energy_drift":(17,8),"branch_pre_fields":(4,7,18432,8),"branch_checkpoint_fields":(4,4,7,18432,8),"branch_post_readout_fields":(4,4,7,18432,8),"branch_harmonic_d":(4,4,7,1024,8),"branch_harmonic_vd":(4,4,7,1024,8),"branch_codebook_coefficients":(4,4,8,7,260),"branch_age_scores":(4,4,8,7,260),"branch_age_energies":(4,4,8,7),"branch_age_symbols":(4,4,8,7),"branch_age_available":(4,4,8,7),"branch_current_predecessor":(4,4,8,2),"branch_ordered_current_symbols":(4,4,8),"branch_ordered_relational_symbols":(4,4,8),"branch_ordered_current_available":(4,4,8),"branch_ordered_relational_available":(4,4,8),"branch_ordered_scores":(4,4,8,260),"branch_clamp_counts":(4,129),"branch_input_energy_drift":(4,129,8),"branch_dynamic_energy":(4,4,7,8),"branch_maximum_absolute_field":(4,4),"sequence_fields":(6,7,18432,8),"sequence_post_readout_fields":(6,7,18432,8),"sequence_harmonic_d":(6,7,1024,8),"sequence_harmonic_vd":(6,7,1024,8),"sequence_codebook_coefficients":(6,8,7,260),"sequence_age_scores":(6,8,7,260),"sequence_age_energies":(6,8,7),"sequence_age_symbols":(6,8,7),"sequence_age_available":(6,8,7),"sequence_current_predecessor":(6,8,2),"sequence_ordered_current_symbols":(6,8),"sequence_ordered_relational_symbols":(6,8),"sequence_ordered_current_available":(6,8),"sequence_ordered_relational_available":(6,8),"sequence_ordered_scores":(6,8,260),"sequence_clamp_counts":(51,),"sequence_input_energy_drift":(51,8),"resume_uninterrupted_sha256":(34,),"resume_reloaded_sha256":(34,)}
    _need(set(a)==set(shapes),"trace array set mismatch")
    for n,s in shapes.items(): _need(a[n].shape==s,f"{n} shape mismatch")
    for n in ("schema_id","branch_names","branch_checkpoint_names","sequence_checkpoint_names","prefix_field_sha256","fork_field_sha256","s1_symbol_sha256","resume_uninterrupted_sha256","resume_reloaded_sha256"): _need(a[n].dtype.kind=="U",f"{n} dtype mismatch")
    for n,x in a.items():
        if x.dtype.kind in "fc": _need(bool(np.isfinite(x).all()),f"{n} contains nonfinite values")
    for n in ("stage_symbols","prefix_emitted_symbols","prefix_current_symbols","prefix_relational_symbols","prefix_clamp_counts","branch_age_symbols","branch_current_predecessor","branch_ordered_current_symbols","branch_ordered_relational_symbols","branch_clamp_counts","sequence_age_symbols","sequence_current_predecessor","sequence_ordered_current_symbols","sequence_ordered_relational_symbols","sequence_clamp_counts"): _need(a[n].dtype==np.int64,f"{n} dtype mismatch")
    for n in ("prefix_current_available","prefix_relational_available","branch_age_available","branch_ordered_current_available","branch_ordered_relational_available","sequence_age_available","sequence_ordered_current_available","sequence_ordered_relational_available"): _need(a[n].dtype==np.bool_,f"{n} dtype mismatch")
    for n in ("codebook","channel_phase","prefix_checkpoint_fields","prefix_post_readout_fields","prefix_current_scores","prefix_relational_scores","prefix_ordered_scores","prefix_input_energy_drift","branch_pre_fields","branch_checkpoint_fields","branch_post_readout_fields","branch_age_scores","branch_age_energies","branch_ordered_scores","branch_input_energy_drift","branch_dynamic_energy","branch_maximum_absolute_field","sequence_fields","sequence_post_readout_fields","sequence_age_scores","sequence_age_energies","sequence_ordered_scores","sequence_input_energy_drift"): _need(a[n].dtype==np.float32,f"{n} dtype mismatch")
    for n in ("branch_harmonic_d","branch_harmonic_vd","branch_codebook_coefficients","sequence_harmonic_d","sequence_harmonic_vd","sequence_codebook_coefficients"): _need(a[n].dtype==np.complex64,f"{n} dtype mismatch")
def _source_gate(board):
    source=mapping(board.get("source_sha256"),"source_sha256"); _need(set(source)==set(EXPECTED_SOURCES),"source hash path set mismatch")
    for rel,frozen in EXPECTED_SOURCES.items():
        p=ROOT/rel; _need(p.is_file(),f"source path missing: {rel}"); actual=sha256_file(p); _need(source[rel]==actual,f"source hash mismatch: {rel}"); _need(frozen is None or actual==frozen,f"frozen source hash mismatch: {rel}")
    _need(board.get("preregistration_sha256")==EXPECTED_SOURCES["designs/L49-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md"],"preregistration hash mismatch")
def _artifact(bp,v,name,label):
    item=mapping(v,label); _need(item.get("path")==name,f"{label} sibling name mismatch"); p=bp.parent/name; _need(p.is_file(),f"{label} artifact missing"); _need(item.get("sha256")==sha256_file(p),f"{label} hash mismatch"); return p
def _check_l40_inputs() -> None:
    for path, expected in L40_INPUTS:
        _need(path.is_file(), f"L40 input missing: {path}")
        _need(
            sha256_file(path) == expected,
            f"L40 input hash mismatch: {path}",
        )


def check_identity_receipts(arrays) -> None:
    prefix_fields = arrays["prefix_checkpoint_fields"]
    _need(
        np.array_equal(arrays["prefix_field_sha256"], PREFIX_FIELD_HASHES),
        "prefix field hash receipt mismatch",
    )
    for index, expected in enumerate(PREFIX_FIELD_HASHES):
        _need(
            _sha_array(prefix_fields[index]) == expected,
            f"prefix field {index} hash mismatch",
        )
    branch_pre = arrays["branch_pre_fields"]
    for branch in range(4):
        _need(
            np.array_equal(branch_pre[branch], prefix_fields[1]),
            f"fork clone {branch} differs from prefix horizon",
        )
        _need(
            arrays["fork_field_sha256"][branch]
            == _sha_array(branch_pre[branch]),
            f"fork clone {branch} hash mismatch",
        )
    _need(
        arrays["s1_symbol_sha256"].item()
        == _sha_array(S1.astype(np.int64)),
        "S1 symbol hash mismatch",
    )
    _need(
        np.array_equal(
            arrays["resume_uninterrupted_sha256"],
            arrays["resume_reloaded_sha256"],
        ),
        "save/reload continuation mismatch",
    )


def _check_zero_clamps(values, label: str) -> None:
    _need(bool((np.asarray(values) == 0).all()), f"{label} clamps occurred")


def _check_field_bounds(fields, label: str) -> float:
    flat = np.asarray(fields).reshape(
        -1, CHANNELS, 9, MODE_COUNT, BATCH
    )
    maximum = 0.0
    for index, packed in enumerate(flat):
        active = packed[:, :8, :WIDTH]
        epsilon = packed[:, 8, :WIDTH]
        _need(
            bool((packed[:, :, WIDTH:] == 0).all()),
            f"{label} {index} inactive field modes are nonzero",
        )
        _need(
            bool(((epsilon >= 0.0) & (epsilon <= 4096.0)).all()),
            f"{label} {index} epsilon bound exceeded",
        )
        item_maximum = float(np.abs(active).max())
        _need(
            item_maximum <= 8.0,
            f"{label} {index} active field amplitude exceeds bound",
        )
        energy = _dynamic_energy(
            packed.reshape(CHANNELS, 9 * MODE_COUNT, BATCH)
        )
        _need(
            float(energy.max()) <= 4.0 + ATOL_NATIVE,
            f"{label} {index} dynamic energy exceeds bound",
        )
        maximum = max(maximum, item_maximum)
    return maximum


def _semantic_symbols(
    recorded_symbols,
    recorded_available,
    expected_scores,
    expected_symbols,
    expected_available,
    label: str,
) -> dict[str, int]:
    return semantic_compare(
        expected_scores,
        recorded_symbols,
        recorded_available,
        expected_scores,
        expected_symbols,
        expected_available,
        label,
    )


def verify_board(board_path: Path, *, allow_smoke_device=False):
    board = load_json(board_path)
    _need(
        board.get("schema_id") == BOARD_SCHEMA,
        "board schema identity mismatch",
    )
    _need(board.get("status") == "COMPLETE", "board is not complete")
    _need(
        board.get("protocol_id")
        == "cassi.l49.harmonic-write-causal-crossover-protocol.v1",
        "protocol identity mismatch",
    )
    _need(
        board.get("execution") == {"canonical": True, "smoke": False},
        "canonical execution identity mismatch",
    )
    expected_profiles = {
        "layout_profile_id": LAYOUT_PROFILE,
        "operator_profile_id": ORDERED_PROFILE,
        "harmonic_layout_profile_id": LAYOUT_PROFILE,
        "harmonic_operator_profile_id": HARMONIC_PROFILE,
        "harmonic_projection_profile_id": PROJECTION_PROFILE,
        "projection_profile_id": PROJECTION_PROFILE,
        "trace_schema_id": TRACE_SCHEMA,
    }
    for key, value in expected_profiles.items():
        _need(board.get(key) == value, f"{key} identity mismatch")
    _source_gate(board)
    _check_l40_inputs()

    prefix_identity = mapping(board.get("prefix"), "prefix")
    _need(
        set(prefix_identity)
        == {
            "l40_board_sha256",
            "l40_trace_sha256",
            "l40_verification_sha256",
            "field_sha256",
        },
        "prefix identity key set mismatch",
    )
    _need(
        prefix_identity["l40_board_sha256"] == L40_INPUTS[0][1]
        and prefix_identity["l40_trace_sha256"] == L40_INPUTS[1][1]
        and prefix_identity["l40_verification_sha256"]
        == L40_INPUTS[2][1],
        "board L40 input identity mismatch",
    )
    _need(
        prefix_identity["field_sha256"] == PREFIX_FIELD_HASHES.tolist(),
        "board prefix field identity mismatch",
    )

    constants = mapping(board.get("constants"), "constants")
    expected_constants = {
        "channels": 7,
        "mode_count": 2048,
        "active_modes": 1024,
        "alphabet_size": 260,
        "batch_size": 8,
        "evolution_steps": 8,
        "blank_ticks": 128,
        "readout_energy_floor": FLOOR,
        "maximum_input_energy_drift": 2.0e-6,
        "max_mode_amplitude": 8.0,
        "max_epsilon": 4096.0,
        "age_harmonics": AGE_HARMONICS.tolist(),
        "branch_checkpoints": BRANCH_CHECKPOINTS.tolist(),
        "sequence_checkpoints": SEQUENCE_CHECKPOINTS.tolist(),
        "stage_symbols": STAGES.tolist(),
    }
    _need(
        set(constants) == set(expected_constants),
        "constant key set mismatch",
    )
    for key, value in expected_constants.items():
        _need(constants[key] == value, f"constant {key} mismatch")

    device = mapping(board.get("device"), "device")
    _need(device.get("dtype") == "float32", "canonical dtype mismatch")
    _need(
        isinstance(device.get("torch_version"), str)
        and bool(device["torch_version"]),
        "PyTorch version missing",
    )
    _need(
        isinstance(device.get("hip_version"), str)
        and bool(device["hip_version"]),
        "HIP version missing",
    )
    if not allow_smoke_device:
        _need(
            device.get("requested") == "cuda"
            and device.get("type") == "cuda"
            and device.get("name") == "AMD Radeon RX 7900 XTX",
            "canonical device mismatch",
        )

    trace_metadata = mapping(board.get("trace"), "trace")
    trace_path = _artifact(
        board_path, trace_metadata, "l49-traces.npz", "trace"
    )
    with np.load(trace_path, allow_pickle=False) as archive:
        arrays = {
            name: np.asarray(archive[name]) for name in archive.files
        }
    _check_arrays(arrays)
    _need(
        trace_metadata.get("array_count") == len(arrays),
        "trace array count mismatch",
    )
    _need(
        arrays["schema_id"].item() == TRACE_SCHEMA,
        "trace schema identity mismatch",
    )
    _need(
        np.array_equal(arrays["branch_names"], BRANCH_NAMES),
        "branch names mismatch",
    )
    _need(
        np.array_equal(
            arrays["branch_checkpoint_names"], BRANCH_CHECKPOINTS
        ),
        "branch checkpoint names mismatch",
    )
    _need(
        np.array_equal(
            arrays["sequence_checkpoint_names"], SEQUENCE_CHECKPOINTS
        ),
        "sequence checkpoint names mismatch",
    )
    _need(
        np.array_equal(arrays["stage_symbols"], STAGES),
        "stage symbols mismatch",
    )
    expected_phase = np.stack(
        (
            np.cos(2 * np.pi * np.arange(CHANNELS) / CHANNELS),
            np.sin(2 * np.pi * np.arange(CHANNELS) / CHANNELS),
        ),
        axis=1,
    ).astype(np.float32)
    _close(arrays["channel_phase"], expected_phase, "channel phase")

    check_identity_receipts(arrays)
    ignored_unavailable = 0
    prefix_fields = arrays["prefix_checkpoint_fields"]
    _need(
        np.array_equal(
            prefix_fields, arrays["prefix_post_readout_fields"]
        ),
        "prefix readout mutated field",
    )
    expected_relational_availability = (
        np.zeros(BATCH, dtype=np.bool_),
        np.ones(BATCH, dtype=np.bool_),
    )
    for checkpoint in range(2):
        reconstructed = reconstruct_readouts(
            prefix_fields[checkpoint], arrays["codebook"]
        )
        current_counts = semantic_compare(
            arrays["prefix_current_scores"][checkpoint],
            arrays["prefix_current_symbols"][checkpoint],
            arrays["prefix_current_available"][checkpoint],
            reconstructed["current_scores"],
            reconstructed["current_symbols"],
            reconstructed["current_available"],
            f"prefix current {checkpoint}",
        )
        relational_counts = semantic_compare(
            arrays["prefix_relational_scores"][checkpoint],
            arrays["prefix_relational_symbols"][checkpoint],
            arrays["prefix_relational_available"][checkpoint],
            reconstructed["relational_scores"],
            reconstructed["relational_symbols"],
            reconstructed["relational_available"],
            f"prefix relational {checkpoint}",
        )
        ignored_unavailable += (
            current_counts["ignored_unavailable_winner_mismatches"]
            + relational_counts["ignored_unavailable_winner_mismatches"]
        )
        _close(
            arrays["prefix_ordered_scores"][checkpoint],
            reconstructed["ordered_scores"],
            f"prefix ordered {checkpoint}",
            True,
        )
        _need(
            np.array_equal(
                arrays["prefix_emitted_symbols"][checkpoint], S0
            )
            and np.array_equal(
                arrays["prefix_current_symbols"][checkpoint], S0
            ),
            f"prefix S0 current {checkpoint} mismatch",
        )
        _need(
            bool(arrays["prefix_current_available"][checkpoint].all()),
            f"prefix current {checkpoint} unavailable",
        )
        _need(
            np.array_equal(
                arrays["prefix_relational_available"][checkpoint],
                expected_relational_availability[checkpoint],
            ),
            f"prefix relational availability {checkpoint} mismatch",
        )
    _need(
        np.array_equal(arrays["prefix_relational_symbols"][1], S0),
        "contaminated horizon relational symbol mismatch",
    )
    _check_zero_clamps(arrays["prefix_clamp_counts"], "prefix")
    prefix_drift = float(
        np.abs(arrays["prefix_input_energy_drift"]).max()
    )
    _need(prefix_drift <= 2.0e-6, "prefix energy drift exceeds bound")

    codebook = arrays["codebook"]
    branch_fields = arrays["branch_checkpoint_fields"]
    for branch in range(4):
        for checkpoint in range(4):
            field = branch_fields[branch, checkpoint]
            _need(
                np.array_equal(
                    field,
                    arrays["branch_post_readout_fields"][
                        branch, checkpoint
                    ],
                ),
                f"branch {branch}/{checkpoint} readout mutated field",
            )
            reconstructed = reconstruct_readouts(field, codebook)
            _close(
                arrays["branch_harmonic_d"][branch, checkpoint],
                reconstructed["physical_d"],
                f"branch {branch}/{checkpoint} harmonic D",
            )
            _close(
                arrays["branch_harmonic_vd"][branch, checkpoint],
                reconstructed["physical_vd"],
                f"branch {branch}/{checkpoint} harmonic VD",
            )
            _close(
                arrays["branch_codebook_coefficients"][
                    branch, checkpoint
                ],
                reconstructed["coefficients"],
                f"branch {branch}/{checkpoint} coefficients",
            )
            age_counts = semantic_compare(
                arrays["branch_age_scores"][branch, checkpoint],
                arrays["branch_age_symbols"][branch, checkpoint],
                arrays["branch_age_available"][branch, checkpoint],
                reconstructed["age_scores"],
                reconstructed["age_symbols"],
                reconstructed["age_available"],
                f"branch {branch}/{checkpoint} age",
            )
            ignored_unavailable += age_counts[
                "ignored_unavailable_winner_mismatches"
            ]
            _close(
                arrays["branch_age_energies"][branch, checkpoint],
                reconstructed["age_energies"],
                f"branch {branch}/{checkpoint} age energies",
                True,
            )
            _need(
                np.array_equal(
                    arrays["branch_current_predecessor"][
                        branch, checkpoint
                    ],
                    reconstructed["current_predecessor"],
                ),
                f"branch {branch}/{checkpoint} tuple mismatch",
            )
            ordered_counts = semantic_compare(
                arrays["branch_ordered_scores"][branch, checkpoint],
                arrays["branch_ordered_current_symbols"][
                    branch, checkpoint
                ],
                arrays["branch_ordered_current_available"][
                    branch, checkpoint
                ],
                reconstructed["ordered_scores"],
                reconstructed["ordered_current_symbols"],
                reconstructed["ordered_current_available"],
                f"branch {branch}/{checkpoint} ordered current",
            )
            relational_counts = _semantic_symbols(
                arrays["branch_ordered_relational_symbols"][
                    branch, checkpoint
                ],
                arrays["branch_ordered_relational_available"][
                    branch, checkpoint
                ],
                reconstructed["relational_scores"],
                reconstructed["ordered_relational_symbols"],
                reconstructed["ordered_relational_available"],
                f"branch {branch}/{checkpoint} ordered relational",
            )
            ignored_unavailable += (
                ordered_counts["ignored_unavailable_winner_mismatches"]
                + relational_counts[
                    "ignored_unavailable_winner_mismatches"
                ]
            )
            _close(
                arrays["branch_dynamic_energy"][branch, checkpoint],
                _dynamic_energy(field),
                f"branch {branch}/{checkpoint} dynamic energy",
            )
            packed = field.reshape(
                CHANNELS, 9, MODE_COUNT, BATCH
            )
            active_maximum = np.asarray(
                np.abs(packed[:, :8, :WIDTH]).max(),
                dtype=np.float32,
            )
            _close(
                arrays["branch_maximum_absolute_field"][
                    branch, checkpoint
                ],
                active_maximum,
                f"branch {branch}/{checkpoint} maximum field",
                True,
            )
        _check_zero_clamps(
            arrays["branch_clamp_counts"][branch],
            f"branch {branch}",
        )
        _need(
            float(
                np.abs(
                    arrays["branch_input_energy_drift"][branch]
                ).max()
            )
            <= 2.0e-6,
            f"branch {branch} energy drift exceeds bound",
        )

    branch_pre = arrays["branch_pre_fields"]
    identity = branch_fields[0, 0]
    lifted = lift_field(branch_pre[0])
    written, write_drift, write_clamps = bare_write_field(
        branch_pre[0], codebook, S1
    )
    lifted_written, lifted_write_drift, lifted_write_clamps = (
        bare_write_field(lifted, codebook, S1)
    )
    _need(
        np.array_equal(identity, branch_pre[0]),
        "identity branch changed before readout",
    )
    _need(
        not np.array_equal(written, lifted_written),
        "W and UW are byte-identical",
    )
    _close(
        arrays["branch_input_energy_drift"][0, 0],
        np.zeros(BATCH, dtype=np.float32),
        "I write receipt",
    )
    _close(
        arrays["branch_input_energy_drift"][1, 0],
        np.zeros(BATCH, dtype=np.float32),
        "U write receipt",
    )
    _close(
        arrays["branch_input_energy_drift"][2, 0],
        write_drift,
        "W write receipt",
    )
    _close(
        arrays["branch_input_energy_drift"][3, 0],
        lifted_write_drift,
        "UW write receipt",
    )
    _need(
        arrays["branch_clamp_counts"][0, 0] == 0
        and arrays["branch_clamp_counts"][1, 0] == 0
        and arrays["branch_clamp_counts"][2, 0] == write_clamps
        and arrays["branch_clamp_counts"][3, 0]
        == lifted_write_clamps,
        "immediate operation clamp receipt mismatch",
    )

    pre_packed = branch_pre[0].reshape(
        CHANNELS, 9, MODE_COUNT, BATCH
    )
    lifted_packed = branch_fields[1, 0].reshape(
        CHANNELS, 9, MODE_COUNT, BATCH
    )
    untouched_ok = all(
        np.array_equal(pre_packed[:, index], lifted_packed[:, index])
        for index in (0, 1, 4, 5, 8)
    )
    pre_readout = reconstruct_readouts(branch_pre[0], codebook)
    lifted_readout = reconstruct_readouts(branch_fields[1, 0], codebook)
    relocated = (
        np.allclose(
            lifted_readout["physical_d"],
            np.roll(pre_readout["physical_d"], 1, axis=0),
            atol=ATOL_NATIVE,
            rtol=RTOL_NATIVE,
        )
        and np.allclose(
            lifted_readout["physical_vd"],
            np.roll(pre_readout["physical_vd"], 1, axis=0),
            atol=ATOL_NATIVE,
            rtol=RTOL_NATIVE,
        )
    )
    conserved = (
        np.allclose(
            np.linalg.norm(
                lifted_readout["physical_d"], axis=(0, 1)
            ),
            np.linalg.norm(pre_readout["physical_d"], axis=(0, 1)),
            atol=ATOL_NATIVE,
            rtol=RTOL_NATIVE,
        )
        and np.allclose(
            np.linalg.norm(
                lifted_readout["physical_vd"], axis=(0, 1)
            ),
            np.linalg.norm(pre_readout["physical_vd"], axis=(0, 1)),
            atol=ATOL_NATIVE,
            rtol=RTOL_NATIVE,
        )
    )
    age_rotation_ok = (
        np.allclose(
            branch_fields[1, 0],
            lifted,
            atol=ATOL_NATIVE,
            rtol=RTOL_NATIVE,
        )
        and untouched_ok
        and relocated
        and conserved
    )
    write_geometry_ok = np.allclose(
        branch_fields[2, 0],
        written,
        atol=ATOL_NATIVE,
        rtol=RTOL_NATIVE,
    )
    deposit_interaction_ok = np.allclose(
        branch_fields[3, 0],
        lifted_written,
        atol=ATOL_NATIVE,
        rtol=RTOL_NATIVE,
    )

    sequence_fields = arrays["sequence_fields"]
    _need(
        np.array_equal(sequence_fields[0], branch_fields[3, 0]),
        "sequence does not begin at immediate UW",
    )
    _need(
        arrays["sequence_clamp_counts"][0]
        == arrays["branch_clamp_counts"][3, 0],
        "sequence initial clamp receipt mismatch",
    )
    _close(
        arrays["sequence_input_energy_drift"][0],
        arrays["branch_input_energy_drift"][3, 0],
        "sequence initial write receipt",
    )
    expected_sequence = (
        np.stack((S1, S0), axis=1),
        np.stack((S1, S0), axis=1),
        np.stack((S2, S1), axis=1),
        np.stack((S2, S1), axis=1),
        np.stack((S1, S2), axis=1),
        np.stack((S1, S2), axis=1),
    )
    reconstructed_sequence = []
    for checkpoint in range(6):
        field = sequence_fields[checkpoint]
        _need(
            np.array_equal(
                field,
                arrays["sequence_post_readout_fields"][checkpoint],
            ),
            f"sequence {checkpoint} readout mutated field",
        )
        reconstructed = reconstruct_readouts(field, codebook)
        reconstructed_sequence.append(reconstructed)
        _close(
            arrays["sequence_harmonic_d"][checkpoint],
            reconstructed["physical_d"],
            f"sequence {checkpoint} harmonic D",
        )
        _close(
            arrays["sequence_harmonic_vd"][checkpoint],
            reconstructed["physical_vd"],
            f"sequence {checkpoint} harmonic VD",
        )
        _close(
            arrays["sequence_codebook_coefficients"][checkpoint],
            reconstructed["coefficients"],
            f"sequence {checkpoint} coefficients",
        )
        age_counts = semantic_compare(
            arrays["sequence_age_scores"][checkpoint],
            arrays["sequence_age_symbols"][checkpoint],
            arrays["sequence_age_available"][checkpoint],
            reconstructed["age_scores"],
            reconstructed["age_symbols"],
            reconstructed["age_available"],
            f"sequence {checkpoint} age",
        )
        ignored_unavailable += age_counts[
            "ignored_unavailable_winner_mismatches"
        ]
        _close(
            arrays["sequence_age_energies"][checkpoint],
            reconstructed["age_energies"],
            f"sequence {checkpoint} age energies",
            True,
        )
        _need(
            np.array_equal(
                arrays["sequence_current_predecessor"][checkpoint],
                reconstructed["current_predecessor"],
            ),
            f"sequence {checkpoint} tuple reconstruction mismatch",
        )
        ordered_counts = semantic_compare(
            arrays["sequence_ordered_scores"][checkpoint],
            arrays["sequence_ordered_current_symbols"][checkpoint],
            arrays["sequence_ordered_current_available"][checkpoint],
            reconstructed["ordered_scores"],
            reconstructed["ordered_current_symbols"],
            reconstructed["ordered_current_available"],
            f"sequence {checkpoint} ordered current",
        )
        relational_counts = _semantic_symbols(
            arrays["sequence_ordered_relational_symbols"][checkpoint],
            arrays["sequence_ordered_relational_available"][checkpoint],
            reconstructed["relational_scores"],
            reconstructed["ordered_relational_symbols"],
            reconstructed["ordered_relational_available"],
            f"sequence {checkpoint} ordered relational",
        )
        ignored_unavailable += (
            ordered_counts["ignored_unavailable_winner_mismatches"]
            + relational_counts[
                "ignored_unavailable_winner_mismatches"
            ]
        )
    _check_zero_clamps(
        arrays["sequence_clamp_counts"], "sequence"
    )
    sequence_drift = float(
        np.abs(arrays["sequence_input_energy_drift"]).max()
    )
    _need(
        sequence_drift <= 2.0e-6,
        "sequence energy drift exceeds bound",
    )

    maximum = max(
        _check_field_bounds(prefix_fields, "prefix"),
        _check_field_bounds(branch_pre, "fork"),
        _check_field_bounds(branch_fields, "branch"),
        _check_field_bounds(sequence_fields, "sequence"),
    )
    branch_drift = float(
        np.abs(arrays["branch_input_energy_drift"]).max()
    )
    maximum_drift = max(prefix_drift, branch_drift, sequence_drift)

    arms = mapping(board.get("arms"), "arms")
    _need(set(arms) == {"canonical"}, "canonical arm key mismatch")
    canonical_metrics = mapping(arms["canonical"], "canonical arm")
    expected_metric_keys = {
        "mode_count",
        "canonical",
        "prefix_clamp_count",
        "branch_clamp_count",
        "sequence_clamp_count",
        "maximum_input_energy_drift",
        "maximum_absolute_field",
        "resume_event_count",
    }
    _need(
        set(canonical_metrics) == expected_metric_keys,
        "canonical metric key set mismatch",
    )
    _need(
        canonical_metrics["mode_count"] == MODE_COUNT
        and canonical_metrics["canonical"] is True
        and canonical_metrics["prefix_clamp_count"] == 0
        and canonical_metrics["branch_clamp_count"] == 0
        and canonical_metrics["sequence_clamp_count"] == 0
        and canonical_metrics["resume_event_count"] == 34,
        "canonical discrete metric mismatch",
    )
    _close(
        np.asarray(canonical_metrics["maximum_input_energy_drift"]),
        np.asarray(maximum_drift),
        "board maximum input-energy drift",
    )
    _close(
        np.asarray(canonical_metrics["maximum_absolute_field"]),
        np.asarray(
            arrays["branch_maximum_absolute_field"].max()
        ),
        "board branch maximum field",
        True,
    )
    resources = mapping(board.get("resources"), "resources")
    wall_seconds = resources.get("wall_seconds")
    peak_allocated = resources.get("peak_allocated_bytes")
    _need(
        isinstance(wall_seconds, (int, float))
        and np.isfinite(float(wall_seconds))
        and wall_seconds >= 0.0
        and isinstance(peak_allocated, int)
        and peak_allocated >= 0,
        "resource receipt mismatch",
    )

    immediate_target = np.stack((S1, S0), axis=1)
    causal_classification = "SUPPORTED"
    if not age_rotation_ok:
        causal_classification = "AGE_ROTATION_FAILURE"
    elif not write_geometry_ok:
        causal_classification = "WRITE_GEOMETRY_FAILURE"
    elif not deposit_interaction_ok:
        causal_classification = "DEPOSIT_INTERACTION_FAILURE"
    elif not np.array_equal(
        reconstruct_readouts(
            branch_fields[3, 0], codebook
        )["current_predecessor"],
        immediate_target,
    ):
        causal_classification = "READOUT_FAILURE"
    elif any(
        not np.array_equal(
            reconstruct_readouts(
                branch_fields[3, checkpoint], codebook
            )["current_predecessor"],
            immediate_target,
        )
        for checkpoint in (1, 2, 3)
    ):
        causal_classification = "EVOLUTION_FAILURE"
    elif any(
        not np.array_equal(
            reconstructed_sequence[index]["current_predecessor"],
            expected,
        )
        or not np.array_equal(
            arrays["sequence_current_predecessor"][index],
            expected,
        )
        for index, expected in enumerate(expected_sequence)
    ):
        causal_classification = "ROLLING_SEQUENCE_FAILURE"

    failures = (
        []
        if causal_classification == "SUPPORTED"
        else [causal_classification]
    )
    verdict = "SUPPORTS" if not failures else "CONTRADICTS"
    return verdict, {
        "schema_id": VERIFICATION_SCHEMA,
        "verdict": verdict,
        "causal_classification": causal_classification,
        "mechanical_gates": {
            "source_and_artifact_integrity": True,
            "schema_shape_dtype_finiteness": True,
            "canonical_execution_identity": True,
            "prefix_reproduction": True,
            "fork_and_symbol_identity": True,
            "independent_native_reconstruction": True,
            "availability_qualified_readouts": True,
            "readout_immutability": True,
            "write_receipts": True,
            "bounds_energy_clamps": True,
            "persistence": True,
        },
        "metrics": {
            "maximum_absolute_field": maximum,
            "maximum_input_energy_drift": maximum_drift,
            "ignored_unavailable_winner_mismatches": ignored_unavailable,
            "functional_failures": failures,
        },
        "failures": failures,
        "trace_path": str(trace_path),
        "trace_sha256": sha256_file(trace_path),
    }
def report_text(verdict,payload):
    lines=["# L49 Harmonic Write Causal Crossover — Verification","",f"**Verdict: `{verdict}`**",""]; fs=payload.get("failures",[]); lines.extend(["## Failures",*[f"- {x}" for x in fs],""] if fs else []); return "\n".join(lines)
def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--board",type=Path,default=DEFAULT_BOARD); p.add_argument("--report",type=Path,default=DEFAULT_REPORT); p.add_argument("--json",type=Path,default=DEFAULT_JSON); p.add_argument("--allow-smoke-device",action="store_true"); a=p.parse_args(); bp=a.board.resolve()
    if not bp.is_file(): v,payload="INCOMPLETE",{"schema_id":VERIFICATION_SCHEMA,"verdict":"INCOMPLETE","mechanical_gates":{},"metrics":{},"failures":["board artifact is unavailable"]}
    else:
        try:v,payload=verify_board(bp,allow_smoke_device=a.allow_smoke_device)
        except Exception as e:v,payload="FAIL",{"schema_id":VERIFICATION_SCHEMA,"verdict":"FAIL","mechanical_gates":{},"metrics":{},"failures":[f"{type(e).__name__}: {e}"]}
    payload=dict(payload); payload.update({"board_path":str(bp),"board_sha256":sha256_file(bp) if bp.is_file() else None}); atomic_write(a.json.resolve(),canonical_bytes(payload)); atomic_write(a.report.resolve(),report_text(v,payload).encode()); print(v); print(a.report.resolve()); print(a.json.resolve()); return 1 if v in {"FAIL","INCOMPLETE"} else 0
if __name__=="__main__": raise SystemExit(main())
