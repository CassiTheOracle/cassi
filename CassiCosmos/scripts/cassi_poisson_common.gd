extends RefCounted
class_name CassiPoissonCommon
## Shared setup helpers for the persistent FFT twiddle table used by
## compute/cassi_poisson.glsl. The table is allocated and initialized once
## per Poisson resource; no per-solve or per-step allocation is required.

const TWIDDLE_ENTRIES := 255
const TWIDDLE_BYTES := TWIDDLE_ENTRIES * 8
const TWIDDLE_BINDING := 4
const TWIDDLE_INIT_MODE := 6.0

## Allocate the zeroed vec2[255] table. Mode 6 fills the entries with the
## shader's fp32 sin/cos expressions for the requested radix-2 N.
static func create_twiddle_buffer(rd: RenderingDevice) -> RID:
	var zero := PackedByteArray()
	zero.resize(TWIDDLE_BYTES)
	return rd.storage_buffer_create(TWIDDLE_BYTES, zero)

## Return the binding-4 storage uniform required by cassi_poisson.glsl.
static func twiddle_uniform(table: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = TWIDDLE_BINDING
	u.add_id(table)
	return u

## Set an existing seven-float Poisson PC to the one-time table-init mode.
## Call before recording mode 6; the caller restores its normal mode after the
## dispatch. This mutates the caller-owned preallocated byte array in place.
static func configure_twiddle_init(pc_bytes: PackedByteArray, n: int) -> void:
	pc_bytes.encode_float(0, float(n))
	pc_bytes.encode_float(12, TWIDDLE_INIT_MODE)

## Record the one-time GPU table generation. The caller supplies the pipeline
## and uniform set containing twiddle_uniform(); this helper binds both.
## The explicit barrier makes the table visible to the first FFT pass in the
## same compute list and is safe for both global and local RenderingDevices.
static func record_twiddle_init(
		rd: RenderingDevice,
		cl: int,
		pipe: RID,
		uniform_set: RID,
		pc_bytes: PackedByteArray,
		n: int) -> void:
	configure_twiddle_init(pc_bytes, n)
	rd.compute_list_bind_compute_pipeline(cl, pipe)
	rd.compute_list_bind_uniform_set(cl, uniform_set, 0)
	rd.compute_list_set_push_constant(cl, pc_bytes, pc_bytes.size())
	rd.compute_list_dispatch(cl, 1, 1, 1)
	rd.compute_list_add_barrier(cl)
