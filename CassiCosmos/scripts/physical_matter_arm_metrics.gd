extends RefCounted
class_name PhysicalMatterArmMetrics
## Shared decode/policy helpers for the physical-matter acceptance arms.
##
## scripts/verify_physical_matter_engine.gd and
## scripts/verify_physical_matter_production.gd both read the same raw
## [X, Y, Z, valid] float32 observation image and the same packed status words
## published by CassiPhysicalMatterEngine.  Keeping the image layout, the
## finite/nonnegative pixel policy, the fatal-flag mask, and the raw status word
## indices here once means the two arms cannot silently drift apart.

# Status word 0 flags. compute/cassi_physical_matter_hydro.glsl:54
# STATUS_HYDRO_RETRY (64) marks a retried hydro step and
# compute/cassi_physical_matter_init.glsl:99 STATUS_SOURCE_LIMITED (512) marks a
# bounded (not divergent) source term; both are recoverable, so the engine
# treats them as nonfatal.  Every other status flag is fatal.
const NONFATAL_STATUS_MASK: int = 64 | 512

# Raw status-buffer word indices (the engine's `_status` RID).
const STATUS_WORD_FLAGS: int = 0
const STATUS_WORD_HYDRO_RETRIES: int = 4
const STATUS_WORD_HYDRO_REJECTIONS: int = 5
const STATUS_WORD_KINETICS_FAILURES: int = 6
const STATUS_WORD_TRANSPORT_CFL: int = 8
const STATUS_FLOAT_MAX_V_OVER_C: int = 11

# Raw observation image layout: [X, Y, Z, valid] float32 per pixel.
const RAW_XYZ_STRIDE: int = 4

# Status keys every published `status_values` dictionary must carry so a shape
# change can never be mistaken for an empty-but-healthy status.
const REQUIRED_STATUS_KEYS := [
	"flags",
	"initial_out_of_domain",
	"nonfinite_inputs",
	"hydro_rejections",
	"kinetics_failures",
	"moving_frame_rejections",
	"transport_nonfinite",
	"transport_negative",
]


static func status_flags(words: PackedInt32Array) -> int:
	if words.size() <= STATUS_WORD_FLAGS:
		return 0
	return int(words[STATUS_WORD_FLAGS]) & 0xffffffff


static func fatal_status_bits(flags: int) -> int:
	return flags & ~NONFATAL_STATUS_MASK


static func status_is_fatal(flags: int) -> bool:
	return fatal_status_bits(flags) != 0


static func status_keys_present(status: Dictionary) -> bool:
	for key in REQUIRED_STATUS_KEYS:
		if not status.has(key):
			return false
	return true


# Interleaved [X, Y, Z, valid] finiteness/nonnegativity, matching the engine
# arm's observation validity policy.
static func finite_nonnegative(values: PackedFloat32Array) -> bool:
	if values.is_empty() or values.size() % RAW_XYZ_STRIDE != 0:
		return false
	for value in values:
		if not is_finite(value) or value < 0.0:
			return false
	return true


# Per-pixel finite/nonblack tally over an interleaved [X, Y, Z, valid] image.
# `nonblack` requires both a positive valid channel and a positive XYZ peak, so
# it cannot be satisfied by a purely black image.
static func pixel_metrics(values: PackedFloat32Array, size: Vector2i) -> Dictionary:
	var expected_pixels := maxi(size.x * size.y, 0)
	var finite_pixels := 0
	var nonblack_pixels := 0
	var max_xyz := 0.0
	for pixel in range(mini(expected_pixels, values.size() / RAW_XYZ_STRIDE)):
		var base := pixel * RAW_XYZ_STRIDE
		var x := float(values[base])
		var y := float(values[base + 1])
		var z := float(values[base + 2])
		var valid := float(values[base + 3])
		if not is_finite(x) or not is_finite(y) or not is_finite(z) or not is_finite(valid):
			continue
		finite_pixels += 1
		var peak := maxf(x, maxf(y, z))
		max_xyz = maxf(max_xyz, peak)
		if valid > 0.0 and peak > 0.0:
			nonblack_pixels += 1
	return {
		"width": size.x,
		"height": size.y,
		"bytes": values.size() * RAW_XYZ_STRIDE,
		"finite_pixels": finite_pixels,
		"nonblack_pixels": nonblack_pixels,
		"expected_pixels": expected_pixels,
		"max_xyz": max_xyz,
		"ok": values.size() == expected_pixels * RAW_XYZ_STRIDE,
	}


# Raw byte decoder for the production arm's capture_observation_raw_xyz surface.
static func raw_xyz_metrics(bytes: PackedByteArray, size: Vector2i) -> Dictionary:
	var metrics := pixel_metrics(bytes.to_float32_array(), size)
	metrics["bytes"] = bytes.size()
	metrics["digest"] = sha256(bytes) if not bytes.is_empty() else "not_observed"
	metrics["ok"] = bytes.size() == maxi(size.x * size.y, 0) * RAW_XYZ_STRIDE * 4
	return metrics


static func sha256(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	if context.start(HashingContext.HASH_SHA256) != OK:
		return ""
	if context.update(bytes) != OK:
		return ""
	return context.finish().hex_encode()
