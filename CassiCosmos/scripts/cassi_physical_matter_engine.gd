class_name CassiPhysicalMatterEngine
extends RefCounted
## Default-off conservative hydrogen material/radiation engine coupled to the
## live Cassi particle mass, velocity, and acceleration buffers.  prepare() is
## CPU-only; initialize() and every dispatch run on the supplied RD's owner.

const MODEL_PATH_DEFAULT := "res://research/presentation/reference/cassi_physical_matter_model.json"
const INIT_SHADER_PATH := "res://compute/cassi_physical_matter_init.glsl"
const HYDRO_SHADER_PATH := "res://compute/cassi_physical_matter_hydro.glsl"
const ATOMIC_SHADER_PATH := "res://compute/cassi_physical_matter_atomic.glsl"
const TRANSPORT_SHADER_PATH := "res://compute/cassi_physical_matter_transport.glsl"
const TRACER_SHADER_PATH := "res://compute/cassi_physical_matter_tracer.glsl"
const C_LIGHT_M_S := 299792458.0
const CHECKPOINT_SCHEMA := "cassi-physical-matter-checkpoint-v1"
const NUMERICAL_IDENTITY := "cassi-hydrogen-hllc-lebedev26-radhydro-v2"
const WORKGROUP_PARTICLE := 256
const WORKGROUP_CELL := 64
const WORKGROUP_TRANSPORT := 256
const FIXED_SCALE_INITIAL := 2147483648.0
const FIXED_SCALE_GRAVITY := 2147483648.0
const GLOBAL_INITIALIZATION_PARTICLE_CHUNK := 32768
const GLOBAL_STEP_PARTICLE_CHUNK := 32768
const STEP_PHASE_IDLE := 0
const STEP_PHASE_PREPARE := 1
const STEP_PHASE_GRAVITY := 2
const STEP_PHASE_CELL_PREPARE := 3
const STEP_PHASE_HYDRO := 4
const STEP_PHASE_RADIATION := 5
const STEP_PHASE_TRACER := 6
const STEP_PHASE_FINAL_FENCE := 7
const STATUS_NONFATAL_MASK := 64 | 512
const STATUS_STEP_REJECTED := 131072
# Status vocabulary mirrored from the five compute shaders' status[0].x bits.
# A failure message names every set bit rather than printing one masked word,
# and status[3].w packs three independent reasons into disjoint byte fields
# (see _decode_status), which are decoded separately for the same reason.
const STATUS_FLAG_NAMES := {
	1: "nonfinite_input",
	2: "out_of_domain",
	4: "fixed_overflow",
	8: "invalid_cell",
	16: "hydro_nonfinite",
	32: "hydro_negative",
	64: "hydro_retry",
	128: "kinetics_failure",
	256: "source_nonfinite",
	512: "source_limited",
	1024: "moving_frame_domain",
	2048: "remap_nonfinite",
	4096: "transport_cfl",
	8192: "transport_nonfinite",
	16384: "transport_negative",
	32768: "tracer_nonfinite",
	65536: "tracer_domain",
	131072: "step_rejected",
}
const HYDRO_SUBSTEPS_PER_BASE_STEP := 8
const MAX_HYDRO_SUBSTEPS := 256
const MAX_RESOURCE_BYTES := 1536 * 1024 * 1024
const HYDROGEN_MASS_KG := 1.6735575e-27
const FLOAT32_EPSILON := 1.1920928955078125e-7
const FLOAT32_MAX := 3.4028234663852886e38

const RATE_SAMPLES := 96
const RATE_TEMPERATURE_MIN_K := 10.0
const RATE_TEMPERATURE_MAX_K := 1.0e8


var _prepared := false
var _ready := false
var _initialized := false
# `_last_error` latches only genuinely fatal failures (model/prepare/resource
# creation, fatal GPU status flags). Guard/ordering failures -- a step before
# the first commit, a short status readback, an over-cap substep request --
# land in `_last_reject_error` instead, so one rejected call cannot
# permanently disable stepping.
var _last_error := ""
var _last_reject_error := ""
var _last_checkpoint_error := ""
var _rd: RenderingDevice = null
var _rd_global := true
var _spirv: Dictionary = {}
var _model: Dictionary = {}
var _model_path := ""
var _model_file_sha256 := ""
var _model_sha256 := ""
var _frequency_grid_sha256 := ""
var _atomic_bundle_sha256 := ""
var _unit_map_sha256 := ""

var _grid := Vector3i(32, 32, 32)
var _extents := Vector3(728.0, 450.0, 278.0)
var _center := Vector3.ZERO
var _particle_count := 0
var _total_particle_mass := 0.0
var _initial_temperature_K := 8000.0
var _cadence_steps := 8
var _dt_sim := 0.05
var _length_m_per_sim := 1.0e12
var _time_s_per_sim := 1.0e8
var _mass_kg_per_sim := 1.98847e30
var _energy_J_per_sim := 0.0
var _density_kg_m3_per_sim := 0.0
var _energy_density_J_m3_per_sim := 0.0
var _velocity_m_s_per_sim := 0.0
var _gamma_gas := 5.0 / 3.0
var _temperature_min_K := 10.0
var _temperature_max_K := 1.0e8
var _c_reduced_sim := 299.792458
var _maximum_v_over_c := 0.05
var _transport_cfl := 0.42
var _density_floor := 1.0e-20
var _pressure_floor := 1.0e-24
var _tracer_blend := 1.0
var _group_count := 0
var _angle_count := 0
var _line_count := 0
var _cell_count := 0
var _radiation_count := 0
var _max_ordinate_l1 := 1.0
var _resource_bytes := 0

var _accepted_steps := 0
var _state_epoch := 1
var _reset_epoch := 1
var _physical_time_sim := 0.0
var _pending_steps := 0
var _pending_time_sim := 0.0
var _pending_heating_events := 0
var _pending_heating_delta_temperature_K := 0.0
var _accepted_heating_events := 0
var _total_heating_delta_temperature_K := 0.0
var _pending_initialization := false
var _pending_initialization_slice := false
var _initialization_particle_offset := 0
var _step_phase := STEP_PHASE_IDLE
var _step_particle_offset := 0
var _step_elapsed_dt_sim := 0.0
var _step_hydro_substep := 0
var _step_radiation_substep := 0
var _step_radiation_stage := 0
var _step_material_role_b := false
var _step_radiation_role_b := false
var _pending_step_slice := false
var _material_role_b := false
var _radiation_role_b := false
var _last_status: Dictionary = {}
# Fatal status bits decoded at the last commit fence; published so per-frame
# consumers do not re-derive them from status_values.
var _last_fatal_flags := 0
# Reused push-constant images. The invariant words are written once in
# prepare(); each recorder patches only its per-dispatch words, so a recorded
# step allocates no Packed*Array and no byte copy per dispatch.
var _pc_init := PackedByteArray()
var _pc_hydro := PackedByteArray()
var _pc_atomic := PackedByteArray()
var _pc_transport := PackedByteArray()
var _pc_tracer := PackedByteArray()
# Sourced from the SHA-pinned model's source_record rather than a code literal.
var _two_photon_rate_s_inv := 0.0
var _source_enabled := true
# publication() reports the cadence substep estimates; both are pure
# functions of prepare()-time state, so they are computed once there.
var _cadence_radiation_substeps := 1
var _cadence_hydro_substeps := 1
# Physical commands join the caller's already-open compute list. Godot does
# not permit timestamps inside an active dispatched list, so this component
# reports command-record time and the host-visible fence/readback boundary.
# The owning production frame brackets the complete list for GPU timing.
var _last_command_record_us := 0
var _last_commit_fence_readback_us := 0
# A rejected batch must not expose the opposite ping-pong role merely because
# guarded no-op dispatches were recorded after the GPU preflight. Keep the
# first role pair until the enclosing fence reports acceptance or rejection.
var _pending_role_snapshot_valid := false
var _pending_material_role_b := false
var _pending_radiation_role_b := false

var _pos := RID()
var _vel := RID()
var _acc := RID()
var _fixed := RID()
var _material0_a := RID()
var _material1_a := RID()
var _population0_a := RID()
var _population1_a := RID()
var _material0_b := RID()
var _material1_b := RID()
var _population0_b := RID()
var _population1_b := RID()
var _radiation_a := RID()
var _radiation_b := RID()
var _frequency := RID()
var _ordinate := RID()
var _line_a := RID()
var _line_b := RID()
var _level := RID()
var _rates := RID()
var _opacity := RID()
var _emission := RID()
var _gravity := RID()
var _ledger0 := RID()
var _ledger1 := RID()
var _ledger2 := RID()
var _status := RID()
var _hydro_debug := RID()

var _init_shader := RID()
var _hydro_shader := RID()
var _atomic_shader := RID()
var _transport_shader := RID()
var _tracer_shader := RID()
var _init_pipe := RID()
var _hydro_pipe := RID()
var _atomic_pipe := RID()
var _transport_pipe := RID()
var _tracer_pipe := RID()
var _us_init := RID()
var _us_hydro_ab := RID()
var _us_hydro_ba := RID()
# Four atomic uniform sets indexed by _atomic_role_index(matter_b, radiation_b):
# a flat RID array keeps the per-dispatch role lookup allocation-free.
var _us_atomic: Array = []
var _us_transport_ab := RID()
var _us_transport_ba := RID()
var _us_tracer_a := RID()
var _us_tracer_b := RID()

var _frequency_bytes := PackedByteArray()
var _ordinate_bytes := PackedByteArray()
var _line_a_bytes := PackedByteArray()
var _line_b_bytes := PackedByteArray()
var _level_bytes := PackedByteArray()
var _rate_bytes := PackedByteArray()


func prepare(config: Dictionary) -> bool:
	if _ready or _prepared:
		return _fail("physical matter engine is already prepared")
	_reset_prepared_state()
	_model_path = String(config.get("model_path", MODEL_PATH_DEFAULT))
	if not FileAccess.file_exists(_model_path):
		return _fail("physical matter model does not exist: " + _model_path)
	var bytes := FileAccess.get_file_as_bytes(_model_path)
	_model_file_sha256 = _sha256(bytes)
	var parsed: Variant = JSON.parse_string(bytes.get_string_from_utf8())
	if not parsed is Dictionary:
		return _fail("physical matter model is not a JSON object")
	_model = (parsed as Dictionary).duplicate(true)
	if String(_model.get("source_kind", "")) != "conditional_hydrogen_plasma":
		return _fail("physical matter model has unsupported source_kind")
	if String(_model.get("coupling", "")) != "live_cassi_mass_motion_gravity":
		return _fail("physical matter model has unsupported coupling")
	_model_sha256 = String(_model.get("model_sha256", ""))
	var expected_model_sha := String(config.get("model_sha256", ""))
	if expected_model_sha.is_empty() or expected_model_sha != _model_sha256:
		return _fail("physical matter model SHA-256 is missing or mismatched")
	var frequency_grid_value: Variant = _model.get("frequency_grid", {})
	var kinetics_value: Variant = _model.get("kinetics", {})
	var eos_value: Variant = _model.get("eos", {})
	var units_value: Variant = _model.get("unit_defaults", {})
	var source_value: Variant = _model.get("source_record", {})
	if not frequency_grid_value is Dictionary or not kinetics_value is Dictionary \
			or not eos_value is Dictionary or not units_value is Dictionary \
			or not source_value is Dictionary:
		return _fail("physical matter model is missing required dictionaries")
	var frequency_grid := frequency_grid_value as Dictionary
	var kinetics := kinetics_value as Dictionary
	var eos := eos_value as Dictionary
	var units := units_value as Dictionary
	var source := source_value as Dictionary
	_frequency_grid_sha256 = String(frequency_grid.get("frequency_grid_sha256", ""))
	_atomic_bundle_sha256 = String(source.get("source_record_sha256", ""))
	_unit_map_sha256 = String(units.get("unit_defaults_sha256", ""))
	if _frequency_grid_sha256.length() != 64 or _atomic_bundle_sha256.length() != 64 \
			or _unit_map_sha256.length() != 64:
		return _fail("physical matter identity bundle is incomplete")
	# The two-photon rate is a physics constant the hash-pinned source record
	# already carries; sourcing it here keeps the model SHA a real witness for
	# the value the GPU is given instead of trusting a code literal.
	_two_photon_rate_s_inv = float(source.get("two_photon_rate_s_inv", 0.0))
	if not is_finite(_two_photon_rate_s_inv) or _two_photon_rate_s_inv <= 0.0:
		return _fail("physical matter model is missing a valid two_photon_rate_s_inv")
	_grid = Vector3i(config.get("grid", Vector3i(32, 32, 32)))
	if _grid.x < 4 or _grid.y < 4 or _grid.z < 4 or _grid.x > 128 or _grid.y > 128 or _grid.z > 128:
		return _fail("physical matter grid must be within 4..128 cells per axis")
	_extents = Vector3(config.get("extents", _extents))
	_center = Vector3(config.get("center", Vector3.ZERO))
	if not _finite_vec3(_extents) or _extents.x <= 0.0 or _extents.y <= 0.0 or _extents.z <= 0.0:
		return _fail("physical matter extents must be finite and positive")
	_particle_count = int(config.get("particle_count", 0))
	_total_particle_mass = float(config.get("total_particle_mass", 0.0))
	if _particle_count <= 0 or not is_finite(_total_particle_mass) or _total_particle_mass <= 0.0:
		return _fail("physical matter particle count and total mass must be positive")
	_cadence_steps = maxi(int(config.get("cadence_steps", 8)), 1)
	_dt_sim = float(config.get("dt_sim", 0.05))
	_initial_temperature_K = float(config.get(
			"initial_temperature_K", units.get("initial_temperature_K", 8000.0)))
	_length_m_per_sim = float(config.get("length_m_per_sim", units.get("length_m_per_sim", 1.0e12)))
	_time_s_per_sim = float(config.get("time_s_per_sim", units.get("time_s_per_physics_sim", 1.0e8)))
	_mass_kg_per_sim = float(config.get(
			"mass_kg_per_sim", units.get("target_total_baryonic_mass_kg", 1.98847e30)))
	_gamma_gas = float(eos.get("gamma", 5.0 / 3.0))
	_temperature_min_K = float(eos.get("temperature_min_K", 10.0))
	_temperature_max_K = float(eos.get("temperature_max_K", 1.0e8))
	var reduced_light_fraction := float(config.get("reduced_light_fraction", -1.0))
	if reduced_light_fraction > 0.0 and reduced_light_fraction <= 1.0:
		_c_reduced_sim = C_LIGHT_M_S * reduced_light_fraction \
				* _time_s_per_sim / _length_m_per_sim
	else:
		_c_reduced_sim = float(units.get("c_gamma_sim", 299.792458))
	var transport_value: Variant = _model.get("transport", {})
	if not transport_value is Dictionary:
		return _fail("physical matter transport controls are missing")
	var transport := transport_value as Dictionary
	_maximum_v_over_c = float(transport.get("maximum_v_over_c_reduced", 0.05))
	_transport_cfl = float(transport.get("cfl", 0.42))
	_density_floor = float(config.get("density_floor", 1.0e-20))
	_pressure_floor = float(config.get("pressure_floor", 1.0e-24))
	_tracer_blend = clampf(float(config.get("tracer_blend", 1.0)), 0.0, 1.0)
	_source_enabled = bool(config.get("source_enabled", true))
	if not _finite_positive_controls():
		return _fail("physical matter units or numerical controls are invalid")
	_velocity_m_s_per_sim = _length_m_per_sim / _time_s_per_sim
	_energy_J_per_sim = _mass_kg_per_sim * _velocity_m_s_per_sim * _velocity_m_s_per_sim
	_density_kg_m3_per_sim = _mass_kg_per_sim / pow(_length_m_per_sim, 3.0)
	_energy_density_J_m3_per_sim = _energy_J_per_sim / pow(_length_m_per_sim, 3.0)
	if not _build_static_payloads(frequency_grid, kinetics):
		return false
	_cell_count = _grid.x * _grid.y * _grid.z
	_radiation_count = _cell_count * _group_count * _angle_count
	_build_push_constant_images()
	_cadence_hydro_substeps = _hydro_substeps(_dt_sim * float(_cadence_steps))
	_cadence_radiation_substeps = _radiation_substeps(_dt_sim * float(_cadence_steps))
	_resource_bytes = _estimate_resource_bytes()
	if _resource_bytes <= 0 or _resource_bytes > MAX_RESOURCE_BYTES:
		return _fail("physical matter GPU allocation exceeds the 1.5 GiB bound")
	_prepared = true
	_last_error = ""
	return true


func _finite_positive_controls() -> bool:
	for value in [_dt_sim, _initial_temperature_K, _length_m_per_sim, _time_s_per_sim,
			_mass_kg_per_sim, _gamma_gas, _temperature_min_K, _temperature_max_K,
			_c_reduced_sim, _maximum_v_over_c, _transport_cfl, _density_floor, _pressure_floor]:
		if not is_finite(float(value)) or float(value) <= 0.0:
			return false
	return _temperature_max_K > _temperature_min_K and _gamma_gas > 1.0


func _build_static_payloads(frequency_grid: Dictionary, kinetics: Dictionary) -> bool:
	var edges_value: Variant = frequency_grid.get("frequency_edges_Hz", [])
	var mids_value: Variant = frequency_grid.get("group_midpoint_Hz", [])
	var widths_value: Variant = frequency_grid.get("group_width_Hz", [])
	var ordinates_value: Variant = frequency_grid.get("ordinates", [])
	var weights_value: Variant = frequency_grid.get("ordinate_weights_sr", [])
	var levels_value: Variant = _model.get("levels", [])
	var lines_value: Variant = _model.get("transitions", [])
	if not edges_value is Array or not mids_value is Array or not widths_value is Array \
			or not ordinates_value is Array or not weights_value is Array \
			or not levels_value is Array or not lines_value is Array:
		return _fail("physical matter model arrays are malformed")
	var edges := edges_value as Array
	var mids := mids_value as Array
	var widths := widths_value as Array
	var ordinates := ordinates_value as Array
	var weights := weights_value as Array
	var levels := levels_value as Array
	var lines := lines_value as Array
	_group_count = mids.size()
	_angle_count = ordinates.size()
	_line_count = lines.size()
	if _group_count != 24 or edges.size() != _group_count + 1 or widths.size() != _group_count:
		return _fail("physical matter frequency layout must contain 24 groups")
	if _angle_count != 26 or weights.size() != _angle_count:
		return _fail("physical matter angular layout must be Lebedev-26")
	if levels.size() != 7 or _line_count != 15:
		return _fail("physical matter atomic layout must contain seven states and fifteen lines")
	var frequency_floats := PackedFloat32Array()
	frequency_floats.resize(_group_count * 4)
	for group in range(_group_count):
		frequency_floats[group * 4] = float(edges[group])
		frequency_floats[group * 4 + 1] = float(edges[group + 1])
		frequency_floats[group * 4 + 2] = float(mids[group])
		frequency_floats[group * 4 + 3] = float(widths[group])
	_frequency_bytes = frequency_floats.to_byte_array()
	var ordinate_floats := PackedFloat32Array()
	ordinate_floats.resize(_angle_count * 4)
	var weight_sum := 0.0
	_max_ordinate_l1 = 0.0
	for angle in range(_angle_count):
		var direction_value: Variant = ordinates[angle]
		if not direction_value is Array or (direction_value as Array).size() != 3:
			return _fail("physical matter ordinate is malformed")
		var direction_array := direction_value as Array
		var direction := Vector3(float(direction_array[0]), float(direction_array[1]), float(direction_array[2]))
		var weight := float(weights[angle])
		if not _finite_vec3(direction) or absf(direction.length() - 1.0) > 1.0e-5 or weight <= 0.0:
			return _fail("physical matter ordinate is not a positive-weight unit direction")
		ordinate_floats[angle * 4] = direction.x
		ordinate_floats[angle * 4 + 1] = direction.y
		ordinate_floats[angle * 4 + 2] = direction.z
		ordinate_floats[angle * 4 + 3] = weight
		weight_sum += weight
		_max_ordinate_l1 = maxf(_max_ordinate_l1, absf(direction.x) + absf(direction.y) + absf(direction.z))
	if absf(weight_sum - TAU * 2.0) > 1.0e-5:
		return _fail("physical matter ordinate weights do not sum to 4pi")
	_ordinate_bytes = ordinate_floats.to_byte_array()
	var thresholds_value: Variant = kinetics.get("photoionization_threshold_m2", [])
	if not thresholds_value is Array or (thresholds_value as Array).size() != 6:
		return _fail("physical matter photoionization thresholds are malformed")
	var thresholds := thresholds_value as Array
	var ionization_value: Variant = levels[6]
	if not ionization_value is Dictionary:
		return _fail("physical matter ionization level record is malformed")
	var ionization_record := ionization_value as Dictionary
	var ionization_energy := float(ionization_record.get("excitation_energy_J", 0.0))
	if not is_finite(ionization_energy) or ionization_energy <= 0.0:
		return _fail("physical matter ionization energy is malformed")
	var level_floats := PackedFloat32Array()
	level_floats.resize(7 * 4)
	var level_energies: Array = []
	var level_degeneracies: Array = []
	var previous_excitation := -1.0
	for level in range(7):
		var record_value: Variant = levels[level]
		if not record_value is Dictionary:
			return _fail("physical matter level record is malformed")
		var record := record_value as Dictionary
		var excitation := float(record.get("excitation_energy_J", 0.0))
		var degeneracy := float(record.get("degeneracy", 0.0))
		if not is_finite(excitation) or excitation < 0.0 \
				or (level > 0 and excitation <= previous_excitation):
			return _fail("physical matter level energies are not finite and increasing")
		if not is_finite(degeneracy) or degeneracy <= 0.0:
			return _fail("physical matter level degeneracy is not finite and positive")
		level_energies.append(excitation)
		level_degeneracies.append(degeneracy)
		previous_excitation = excitation
		level_floats[level * 4] = excitation
		level_floats[level * 4 + 1] = degeneracy
		if level < 6:
			var threshold_frequency := (ionization_energy - excitation) / 6.62607015e-34
			var threshold := float(thresholds[level])
			# z is the bound-free threshold frequency; w is the independent
			# threshold cross-section.  They intentionally have different units
			# and must not be compared numerically.
			if not is_finite(threshold) or threshold <= 0.0 \
					or not is_finite(threshold_frequency) or threshold_frequency <= 0.0:
				return _fail("physical matter photoionization threshold is malformed")
			level_floats[level * 4 + 2] = threshold_frequency
			level_floats[level * 4 + 3] = threshold
	_level_bytes = level_floats.to_byte_array()

	var line_a_floats := PackedFloat32Array()
	var line_b_floats := PackedFloat32Array()
	line_a_floats.resize(_line_count * 4)
	line_b_floats.resize(_line_count * 4)
	for line in range(_line_count):
		var line_value: Variant = lines[line]
		if not line_value is Dictionary:
			return _fail("physical matter line record is malformed")
		var record := line_value as Dictionary
		var lower_value: Variant = record.get("lower_state", -1)
		var upper_value: Variant = record.get("upper_state", -1)
		var group_value: Variant = record.get("group_index", -1)
		if not (lower_value is int or lower_value is float) \
				or not (upper_value is int or upper_value is float) \
				or not (group_value is int or group_value is float):
			return _fail("physical matter transition indices are not numeric")
		var lower_number := float(lower_value)
		var upper_number := float(upper_value)
		var group_number := float(group_value)
		if not is_finite(lower_number) or lower_number != floor(lower_number) \
				or lower_number < 0.0 or lower_number >= float(levels.size()) \
				or not is_finite(upper_number) or upper_number != floor(upper_number) \
				or upper_number <= 0.0 or upper_number >= float(levels.size()) \
				or not is_finite(group_number) or group_number != floor(group_number) \
				or group_number < 0.0 or group_number >= float(_group_count):
			return _fail("physical matter transition indices are out of range")
		var lower_state := int(lower_number)
		var upper_state := int(upper_number)
		var group_index := int(group_number)
		if lower_state < 0 or lower_state >= levels.size() \
				or upper_state <= lower_state or upper_state >= levels.size():
			return _fail("physical matter transition indices are out of range")
		var lower_energy := float(level_energies[lower_state])
		var upper_energy := float(level_energies[upper_state])
		var expected_frequency := (upper_energy - lower_energy) / 6.62607015e-34
		var frequency := float(record.get("frequency_Hz", 0.0))
		var einstein_a := float(record.get("A_s_inv", 0.0))
		var oscillator := float(record.get("oscillator_strength", 0.0))
		var lower_degeneracy := float(record.get("lower_degeneracy", 0.0))
		var upper_degeneracy := float(record.get("upper_degeneracy", 0.0))
		if not is_finite(expected_frequency) or expected_frequency <= 0.0 \
				or not is_finite(frequency) or frequency <= 0.0 \
				or absf(frequency - expected_frequency) > 2.0e-5 * maxf(expected_frequency, 1.0) \
				or not is_finite(einstein_a) or einstein_a < 0.0 \
				or not is_finite(oscillator) or oscillator <= 0.0 \
				or not is_finite(lower_degeneracy) or lower_degeneracy <= 0.0 \
				or not is_finite(upper_degeneracy) or upper_degeneracy <= 0.0 \
				or group_index < 0 or group_index >= _group_count \
				or absf(lower_degeneracy - float(level_degeneracies[lower_state])) \
						> 2.0e-5 * maxf(float(level_degeneracies[lower_state]), 1.0) \
				or absf(upper_degeneracy - float(level_degeneracies[upper_state])) \
						> 2.0e-5 * maxf(float(level_degeneracies[upper_state]), 1.0):
			return _fail("physical matter transition metadata is inconsistent")
		line_a_floats[line * 4] = float(lower_state)
		line_a_floats[line * 4 + 1] = float(upper_state)
		line_a_floats[line * 4 + 2] = frequency
		line_a_floats[line * 4 + 3] = einstein_a
		line_b_floats[line * 4] = oscillator
		line_b_floats[line * 4 + 1] = float(group_index)
		line_b_floats[line * 4 + 2] = lower_degeneracy
		line_b_floats[line * 4 + 3] = upper_degeneracy
	_line_a_bytes = line_a_floats.to_byte_array()
	_line_b_bytes = line_b_floats.to_byte_array()

	if not _build_rate_payload(kinetics):
		return false
	return true


func _build_rate_payload(kinetics: Dictionary) -> bool:
	var temperatures_value: Variant = kinetics.get("temperature_grid_K", [])
	var ion_value: Variant = kinetics.get("collisional_ionization_m3_s", [])
	var recombination_value: Variant = kinetics.get("case_a_recombination_m3_s", [])
	var transition_value: Variant = kinetics.get("collisional_transition_rates", [])
	if not temperatures_value is Array or not ion_value is Array or not recombination_value is Array \
			or not transition_value is Array:
		return _fail("physical matter rate tables are malformed")
	var temperatures := temperatures_value as Array
	var ion := ion_value as Array
	var recombination := recombination_value as Array
	var transitions := transition_value as Array
	if temperatures.size() != RATE_SAMPLES or ion.size() != RATE_SAMPLES \
			or recombination.size() != RATE_SAMPLES or transitions.size() != _line_count:
		return _fail("physical matter rate tables have an unsupported shape")
	var log_step := log(RATE_TEMPERATURE_MAX_K / RATE_TEMPERATURE_MIN_K) / float(RATE_SAMPLES - 1)
	for sample in range(RATE_SAMPLES):
		var temperature := float(temperatures[sample])
		var expected_log_temperature := log(RATE_TEMPERATURE_MIN_K) + float(sample) * log_step
		if not is_finite(temperature) or temperature <= 0.0 \
				or absf(log(temperature) - expected_log_temperature) > 2.0e-5:
			return _fail("physical matter rate temperature grid is not canonical geomspace")
		if not is_finite(float(ion[sample])) or float(ion[sample]) < 0.0 \
				or float(ion[sample]) > FLOAT32_MAX \
				or not is_finite(float(recombination[sample])) or float(recombination[sample]) < 0.0 \
				or float(recombination[sample]) > FLOAT32_MAX:
			return _fail("physical matter ionization rates are not finite and float32-representable")
	var rates := PackedFloat32Array()
	rates.resize(RATE_SAMPLES * 32)
	for sample in range(RATE_SAMPLES):
		rates[sample * 32] = float(ion[sample])
		rates[sample * 32 + 1] = float(recombination[sample])
		for line in range(_line_count):
			var record_value: Variant = transitions[line]
			if not record_value is Dictionary:
				return _fail("physical matter transition-rate record is malformed")
			var record := record_value as Dictionary
			var excitation_value: Variant = record.get("excitation_m3_s", [])
			var deexcitation_value: Variant = record.get("deexcitation_m3_s", [])
			if not excitation_value is Array or not deexcitation_value is Array:
				return _fail("physical matter transition-rate arrays are malformed")
			var excitation := excitation_value as Array
			var deexcitation := deexcitation_value as Array
			if excitation.size() != RATE_SAMPLES or deexcitation.size() != RATE_SAMPLES:
				return _fail("physical matter transition-rate sample count is unsupported")
			var excitation_rate := float(excitation[sample])
			var deexcitation_rate := float(deexcitation[sample])
			if not is_finite(excitation_rate) or excitation_rate < 0.0 \
					or excitation_rate > FLOAT32_MAX \
					or not is_finite(deexcitation_rate) or deexcitation_rate < 0.0 \
					or deexcitation_rate > FLOAT32_MAX:
				return _fail("physical matter transition rates are not finite and float32-representable")
			rates[sample * 32 + 2 + line * 2] = excitation_rate
			rates[sample * 32 + 3 + line * 2] = deexcitation_rate
	_rate_bytes = rates.to_byte_array()
	return true


func initialize(rd: RenderingDevice, rd_global: bool, spirv: Dictionary,
		position_buffer: RID, velocity_buffer: RID, acceleration_buffer: RID) -> bool:
	if not _prepared or _ready:
		return _fail("physical matter initialize requires one prepared engine")
	if rd == null or not position_buffer.is_valid() or not velocity_buffer.is_valid() \
			or not acceleration_buffer.is_valid():
		return _fail("physical matter initialize received invalid live buffers")
	_rd = rd
	_rd_global = rd_global
	_spirv = spirv
	_pos = position_buffer
	_vel = velocity_buffer
	_acc = acceleration_buffer
	if not _create_resources() or not _create_pipelines() or not _create_uniform_sets():
		shutdown()
		return false
	_ready = true
	_initialization_particle_offset = 0
	if _rd_global:
		# The renderer owns submission for the global RD. Initialization is
		# recorded incrementally into its per-frame list by
		# record_initialization_progress(), never into an orphan component list.
		return true
	var compute_list := _rd.compute_list_begin()
	_record_initialization(compute_list)
	_rd.compute_list_end()
	_pending_initialization = true
	_rd.submit()
	_rd.sync()
	if not commit_recorded_steps():
		return false
	return true


func _create_resources() -> bool:
	_fixed = _rd.storage_buffer_create(_cell_count * 7 * 16)
	_material0_a = _rd.storage_buffer_create(_cell_count * 16)
	_material1_a = _rd.storage_buffer_create(_cell_count * 16)
	_population0_a = _rd.storage_buffer_create(_cell_count * 16)
	_population1_a = _rd.storage_buffer_create(_cell_count * 16)
	_material0_b = _rd.storage_buffer_create(_cell_count * 16)
	_material1_b = _rd.storage_buffer_create(_cell_count * 16)
	_population0_b = _rd.storage_buffer_create(_cell_count * 16)
	_population1_b = _rd.storage_buffer_create(_cell_count * 16)
	_radiation_a = _rd.storage_buffer_create(_radiation_count * 4)
	_radiation_b = _rd.storage_buffer_create(_radiation_count * 4)
	_frequency = _rd.storage_buffer_create(_frequency_bytes.size(), _frequency_bytes)
	_ordinate = _rd.storage_buffer_create(_ordinate_bytes.size(), _ordinate_bytes)
	_line_a = _rd.storage_buffer_create(_line_a_bytes.size(), _line_a_bytes)
	_line_b = _rd.storage_buffer_create(_line_b_bytes.size(), _line_b_bytes)
	_level = _rd.storage_buffer_create(_level_bytes.size(), _level_bytes)
	_rates = _rd.storage_buffer_create(_rate_bytes.size(), _rate_bytes)
	_opacity = _rd.storage_buffer_create(_cell_count * _group_count * 4)
	_emission = _rd.storage_buffer_create(_cell_count * _group_count * 4)
	_gravity = _rd.storage_buffer_create(_cell_count * 16)
	_ledger0 = _rd.storage_buffer_create(_cell_count * 16)
	_ledger1 = _rd.storage_buffer_create(_cell_count * 16)
	_ledger2 = _rd.storage_buffer_create(_cell_count * 16)
	_status = _rd.storage_buffer_create(64)
	_hydro_debug = _rd.storage_buffer_create(64)
	# Initialization clears status from inside the rejected-guard dispatch, so a
	# recycled allocation that already carries STATUS_STEP_REJECTED would
	# suppress its own clear and lock the whole batch. Zero the bootstrap first.
	if _status.is_valid():
		_clear_words(_status)
	if _hydro_debug.is_valid():
		_clear_words(_hydro_debug)
	for rid in _buffer_rids():
		if not (rid as RID).is_valid():
			return _fail("physical matter GPU buffer allocation failed")
	return true


func _create_pipelines() -> bool:
	_init_shader = _shader_create(INIT_SHADER_PATH)
	_hydro_shader = _shader_create(HYDRO_SHADER_PATH)
	_atomic_shader = _shader_create(ATOMIC_SHADER_PATH)
	_transport_shader = _shader_create(TRANSPORT_SHADER_PATH)
	_tracer_shader = _shader_create(TRACER_SHADER_PATH)
	if not _init_shader.is_valid() or not _hydro_shader.is_valid() or not _atomic_shader.is_valid() \
			or not _transport_shader.is_valid() or not _tracer_shader.is_valid():
		return false
	_init_pipe = _rd.compute_pipeline_create(_init_shader)
	_hydro_pipe = _rd.compute_pipeline_create(_hydro_shader)
	_atomic_pipe = _rd.compute_pipeline_create(_atomic_shader)
	_transport_pipe = _rd.compute_pipeline_create(_transport_shader)
	_tracer_pipe = _rd.compute_pipeline_create(_tracer_shader)
	if not _init_pipe.is_valid() or not _hydro_pipe.is_valid() or not _atomic_pipe.is_valid() \
			or not _transport_pipe.is_valid() or not _tracer_pipe.is_valid():
		return _fail("physical matter compute pipeline creation failed")
	return true


func _shader_create(path: String) -> RID:
	var shader_spirv: RDShaderSPIRV = null
	if _spirv.has(path):
		shader_spirv = _spirv[path] as RDShaderSPIRV
	if shader_spirv == null:
		var shader_file := load(path) as RDShaderFile
		if shader_file != null:
			shader_spirv = shader_file.get_spirv()
	if shader_spirv == null:
		_fail("physical matter shader SPIR-V is unavailable: " + path)
		return RID()
	var compile_error := shader_spirv.get_stage_compile_error(RenderingDevice.SHADER_STAGE_COMPUTE)
	if not compile_error.is_empty():
		_fail("physical matter shader compile error: %s — %s" % [path, compile_error])
		return RID()
	var shader := _rd.shader_create_from_spirv(shader_spirv)
	if not shader.is_valid():
		_fail("physical matter shader creation failed: " + path)
	return shader


func _create_uniform_sets() -> bool:
	_us_init = _rd.uniform_set_create([
		_uniform(0, _pos), _uniform(1, _vel), _uniform(2, _acc), _uniform(3, _fixed),
		_uniform(4, _material0_a), _uniform(5, _material1_a),
		_uniform(6, _population0_a), _uniform(7, _population1_a),
		_uniform(8, _material0_b), _uniform(9, _material1_b),
		_uniform(10, _population0_b), _uniform(11, _population1_b),
		_uniform(12, _gravity), _uniform(13, _ledger0), _uniform(14, _ledger1),
		_uniform(15, _ledger2), _uniform(16, _status), _uniform(17, _level),
	], _init_shader, 0)
	_us_hydro_ab = _hydro_set(false)
	_us_hydro_ba = _hydro_set(true)
	_us_atomic.resize(4)
	for matter_b in [false, true]:
		for radiation_b in [false, true]:
			_us_atomic[_atomic_role_index(matter_b, radiation_b)] = _atomic_set(matter_b, radiation_b)
	_us_transport_ab = _rd.uniform_set_create([
		_uniform(0, _radiation_a), _uniform(1, _radiation_b),
		_uniform(2, _ordinate), _uniform(3, _status),
	], _transport_shader, 0)
	_us_transport_ba = _rd.uniform_set_create([
		_uniform(0, _radiation_b), _uniform(1, _radiation_a),
		_uniform(2, _ordinate), _uniform(3, _status),
	], _transport_shader, 0)
	_us_tracer_a = _rd.uniform_set_create([
		_uniform(0, _pos), _uniform(1, _vel), _uniform(2, _material0_a), _uniform(3, _status),
	], _tracer_shader, 0)
	_us_tracer_b = _rd.uniform_set_create([
		_uniform(0, _pos), _uniform(1, _vel), _uniform(2, _material0_b), _uniform(3, _status),
	], _tracer_shader, 0)
	for rid in _uniform_rids():
		if not (rid as RID).is_valid():
			return _fail("physical matter uniform-set creation failed")
	return true


func _hydro_set(reverse: bool) -> RID:
	var m0_in := _material0_b if reverse else _material0_a
	var m1_in := _material1_b if reverse else _material1_a
	var p0_in := _population0_b if reverse else _population0_a
	var p1_in := _population1_b if reverse else _population1_a
	var m0_out := _material0_a if reverse else _material0_b
	var m1_out := _material1_a if reverse else _material1_b
	var p0_out := _population0_a if reverse else _population0_b
	var p1_out := _population1_a if reverse else _population1_b
	return _rd.uniform_set_create([
		_uniform(0, m0_in), _uniform(1, m1_in), _uniform(2, p0_in), _uniform(3, p1_in),
		_uniform(4, m0_out), _uniform(5, m1_out), _uniform(6, p0_out), _uniform(7, p1_out),
		_uniform(8, _gravity), _uniform(9, _ledger1), _uniform(10, _ledger2),
		_uniform(11, _status), _uniform(12, _level), _uniform(13, _hydro_debug),
	], _hydro_shader, 0)


func _atomic_set(matter_b: bool, radiation_b: bool) -> RID:
	var m0 := _material0_b if matter_b else _material0_a
	var m1 := _material1_b if matter_b else _material1_a
	var p0 := _population0_b if matter_b else _population0_a
	var p1 := _population1_b if matter_b else _population1_a
	var radiation := _radiation_b if radiation_b else _radiation_a
	var scratch := _radiation_a if radiation_b else _radiation_b
	return _rd.uniform_set_create([
		_uniform(0, m0), _uniform(1, m1), _uniform(2, p0), _uniform(3, p1),
		_uniform(4, radiation), _uniform(5, scratch), _uniform(6, _frequency),
		_uniform(7, _ordinate), _uniform(8, _line_a), _uniform(9, _line_b),
		_uniform(10, _level), _uniform(11, _rates), _uniform(12, _opacity),
		_uniform(13, _emission), _uniform(14, _ledger0), _uniform(15, _status),
	], _atomic_shader, 0)


func _uniform(binding: int, buffer: RID) -> RDUniform:
	var uniform := RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	uniform.binding = binding
	uniform.add_id(buffer)
	return uniform

## Zero one 64-byte telemetry word block (status or hydro-debug).
func _clear_words(buffer: RID) -> void:
	if _rd == null or not buffer.is_valid():
		return
	var zeros := PackedInt32Array()
	zeros.resize(16)
	_rd.buffer_update(buffer, 0, 64, zeros.to_byte_array())



func _record_initialization(compute_list: int) -> void:
	_rd.compute_list_bind_compute_pipeline(compute_list, _init_pipe)
	_rd.compute_list_bind_uniform_set(compute_list, _us_init, 0)
	_dispatch_init(compute_list, 0, _cell_count * 7, FIXED_SCALE_INITIAL, 0)
	_rd.compute_list_add_barrier(compute_list)
	_dispatch_init(compute_list, 1, _particle_count, FIXED_SCALE_INITIAL, 0)
	_rd.compute_list_add_barrier(compute_list)
	_dispatch_init(compute_list, 2, _cell_count, FIXED_SCALE_INITIAL, 0)
	_rd.compute_list_add_barrier(compute_list)
	_record_atomic(compute_list, 3, _dt_sim)
	_rd.compute_list_add_barrier(compute_list)
	_record_atomic(compute_list, 4, _dt_sim)
	_rd.compute_list_add_barrier(compute_list)


## Record at most one bounded initialization slice into the renderer-owned
## global-RD list. Particle rendering continues from the live site buffers
## while the material deposit advances; normal physics remains paused until
## the final slice has crossed the renderer's frame fence and committed.
func record_initialization_progress(compute_list: int) -> bool:
	if not _rd_global or _initialized or _pending_initialization \
			or _pending_initialization_slice:
		return false
	if not _ready or compute_list < 0:
		return false
	_rd.compute_list_bind_compute_pipeline(compute_list, _init_pipe)
	_rd.compute_list_bind_uniform_set(compute_list, _us_init, 0)
	if _initialization_particle_offset == 0:
		_dispatch_init(compute_list, 0, _cell_count * 7, FIXED_SCALE_INITIAL, 0)
		_rd.compute_list_add_barrier(compute_list)
	var remaining := _particle_count - _initialization_particle_offset
	var slice_count := mini(remaining, GLOBAL_INITIALIZATION_PARTICLE_CHUNK)
	if slice_count > 0:
		_dispatch_init(compute_list, 1, slice_count, FIXED_SCALE_INITIAL,
				_initialization_particle_offset)
		_initialization_particle_offset += slice_count
		_rd.compute_list_add_barrier(compute_list)
	if _initialization_particle_offset >= _particle_count:
		_dispatch_init(compute_list, 2, _cell_count, FIXED_SCALE_INITIAL, 0)
		_rd.compute_list_add_barrier(compute_list)
		_record_atomic(compute_list, 3, _dt_sim)
		_rd.compute_list_add_barrier(compute_list)
		_record_atomic(compute_list, 4, _dt_sim)
		_rd.compute_list_add_barrier(compute_list)
		_pending_initialization = true
	_pending_initialization_slice = true
	return true


func initialization_recording_needed() -> bool:
	return _rd_global and _ready and not _initialized \
			and not _pending_initialization and not _pending_initialization_slice


func initialization_incomplete() -> bool:
	return _ready and not _initialized


func record_step(compute_list: int, elapsed_dt_sim: float) -> bool:
	# Rejections here are retryable ordering/argument faults: no GPU buffer was
	# touched, so they must not latch the fatal error that disables stepping.
	if not is_operational() or compute_list < 0 or not is_finite(elapsed_dt_sim) \
			or elapsed_dt_sim <= 0.0:
		return _reject("physical matter step requires initialized resources and positive dt")
	var hydro_substeps := _hydro_substeps(elapsed_dt_sim)
	if hydro_substeps > MAX_HYDRO_SUBSTEPS:
		return _reject("physical matter hydro update requires %d substeps; maximum is %d"
				% [hydro_substeps, MAX_HYDRO_SUBSTEPS])
	if _rd_global:
		if _step_phase != STEP_PHASE_IDLE or _pending_step_slice:
			return _reject("physical matter step already has staged GPU work")
		_pending_role_snapshot_valid = true
		_pending_material_role_b = _material_role_b
		_pending_radiation_role_b = _radiation_role_b
		_step_material_role_b = _material_role_b
		_step_radiation_role_b = _radiation_role_b
		_step_elapsed_dt_sim = elapsed_dt_sim
		_step_particle_offset = 0
		_step_hydro_substep = 0
		_step_radiation_substep = 0
		_step_radiation_stage = 0
		_step_phase = STEP_PHASE_PREPARE
		return record_step_progress(compute_list)
	return _record_step_monolithic(compute_list, elapsed_dt_sim, hydro_substeps)


func step_recording_incomplete() -> bool:
	return _step_phase != STEP_PHASE_IDLE


func step_recording_needed() -> bool:
	return _rd_global and _step_phase > STEP_PHASE_IDLE \
			and _step_phase < STEP_PHASE_FINAL_FENCE and not _pending_step_slice


## Record one bounded global-RD slice. The published ping-pong roles stay on
## the last accepted state until the final fence; `_step_*_role_b` carries the
## private working roles across renderer frames.
func record_step_progress(compute_list: int) -> bool:
	if not step_recording_needed() or compute_list < 0:
		return false
	var record_started_us := Time.get_ticks_usec()
	match _step_phase:
		STEP_PHASE_PREPARE:
			_record_atomic(compute_list, 5, 0.0)
			_rd.compute_list_add_barrier(compute_list)
			_rd.compute_list_bind_compute_pipeline(compute_list, _init_pipe)
			_rd.compute_list_bind_uniform_set(compute_list, _us_init, 0)
			_dispatch_init(compute_list, 3, _cell_count * 7, FIXED_SCALE_GRAVITY, 0)
			_rd.compute_list_add_barrier(compute_list)
			_step_phase = STEP_PHASE_GRAVITY
		STEP_PHASE_GRAVITY:
			var remaining := _particle_count - _step_particle_offset
			var slice_count := mini(remaining, GLOBAL_STEP_PARTICLE_CHUNK)
			_rd.compute_list_bind_compute_pipeline(compute_list, _init_pipe)
			_rd.compute_list_bind_uniform_set(compute_list, _us_init, 0)
			_dispatch_init(compute_list, 4, slice_count, FIXED_SCALE_GRAVITY,
					_step_particle_offset)
			_step_particle_offset += slice_count
			_rd.compute_list_add_barrier(compute_list)
			if _step_particle_offset >= _particle_count:
				_step_particle_offset = 0
				_step_phase = STEP_PHASE_CELL_PREPARE
		STEP_PHASE_CELL_PREPARE:
			_rd.compute_list_bind_compute_pipeline(compute_list, _init_pipe)
			_rd.compute_list_bind_uniform_set(compute_list, _us_init, 0)
			_dispatch_init(compute_list, 5, _cell_count, FIXED_SCALE_GRAVITY, 0)
			_rd.compute_list_add_barrier(compute_list)
			_step_phase = STEP_PHASE_HYDRO
		STEP_PHASE_HYDRO:
			_material_role_b = _step_material_role_b
			_radiation_role_b = _step_radiation_role_b
			var hydro_substeps := _hydro_substeps(_step_elapsed_dt_sim)
			var hydro_dt := _step_elapsed_dt_sim / float(hydro_substeps)
			for axis in range(3):
				_record_hydro(compute_list, axis, hydro_dt)
				_material_role_b = not _material_role_b
				_rd.compute_list_add_barrier(compute_list)
			_step_material_role_b = _material_role_b
			_step_radiation_role_b = _radiation_role_b
			_step_hydro_substep += 1
			if _step_hydro_substep >= hydro_substeps:
				_step_phase = STEP_PHASE_RADIATION
		STEP_PHASE_RADIATION:
			_material_role_b = _step_material_role_b
			_radiation_role_b = _step_radiation_role_b
			var radiation_substeps := _radiation_substeps(_step_elapsed_dt_sim)
			var radiation_dt := _step_elapsed_dt_sim / float(radiation_substeps)
			match _step_radiation_stage:
				0:
					_record_transport_pass(compute_list, radiation_dt, true)
					_rd.compute_list_add_barrier(compute_list)
					_step_radiation_stage = 1
				1:
					_record_atomic(compute_list, 2, radiation_dt)
					_rd.compute_list_add_barrier(compute_list)
					_step_radiation_stage = 2
				2:
					_record_transport_pass(compute_list, radiation_dt, false)
					_radiation_role_b = not _radiation_role_b
					_rd.compute_list_add_barrier(compute_list)
					_step_radiation_substep += 1
					_step_radiation_stage = 0
					if _step_radiation_substep >= radiation_substeps:
						_record_atomic(compute_list, 1, _step_elapsed_dt_sim)
						_radiation_role_b = not _radiation_role_b
						_rd.compute_list_add_barrier(compute_list)
						_step_phase = STEP_PHASE_TRACER
			_step_material_role_b = _material_role_b
			_step_radiation_role_b = _radiation_role_b
		STEP_PHASE_TRACER:
			var remaining := _particle_count - _step_particle_offset
			var slice_count := mini(remaining, GLOBAL_STEP_PARTICLE_CHUNK)
			_record_tracer(compute_list, _step_material_role_b,
					_step_particle_offset, slice_count)
			_step_particle_offset += slice_count
			_rd.compute_list_add_barrier(compute_list)
			if _step_particle_offset >= _particle_count:
				_pending_steps = 1
				_pending_time_sim = _step_elapsed_dt_sim
				_step_phase = STEP_PHASE_FINAL_FENCE
		_:
			return false
	# Never expose an intermediate ping-pong role to the physical observer.
	_material_role_b = _pending_material_role_b
	_radiation_role_b = _pending_radiation_role_b
	_pending_step_slice = true
	_last_command_record_us = Time.get_ticks_usec() - record_started_us
	_last_reject_error = ""
	return true


func _record_step_monolithic(compute_list: int, elapsed_dt_sim: float,
		hydro_substeps: int) -> bool:
	_pending_role_snapshot_valid = true
	_pending_material_role_b = _material_role_b
	_pending_radiation_role_b = _radiation_role_b
	var record_started_us := Time.get_ticks_usec()
	_record_atomic(compute_list, 5, 0.0)
	_rd.compute_list_add_barrier(compute_list)
	_rd.compute_list_bind_compute_pipeline(compute_list, _init_pipe)
	_rd.compute_list_bind_uniform_set(compute_list, _us_init, 0)
	_dispatch_init(compute_list, 3, _cell_count * 7, FIXED_SCALE_GRAVITY, 0)
	_rd.compute_list_add_barrier(compute_list)
	_dispatch_init(compute_list, 4, _particle_count, FIXED_SCALE_GRAVITY, 0)
	_rd.compute_list_add_barrier(compute_list)
	_dispatch_init(compute_list, 5, _cell_count, FIXED_SCALE_GRAVITY, 0)
	_rd.compute_list_add_barrier(compute_list)
	_record_step_cells(compute_list, elapsed_dt_sim, hydro_substeps)
	_record_tracer(compute_list, _material_role_b, 0, _particle_count)
	_rd.compute_list_add_barrier(compute_list)
	_last_command_record_us = Time.get_ticks_usec() - record_started_us
	_pending_steps += 1
	_pending_time_sim += elapsed_dt_sim
	_last_reject_error = ""
	return true


func _record_step_cells(compute_list: int, elapsed_dt_sim: float,
		hydro_substeps: int = -1) -> void:
	if hydro_substeps < 0:
		hydro_substeps = _hydro_substeps(elapsed_dt_sim)
	var hydro_dt := elapsed_dt_sim / float(hydro_substeps)
	for _substep in range(hydro_substeps):
		for axis in range(3):
			_record_hydro(compute_list, axis, hydro_dt)
			_material_role_b = not _material_role_b
			_rd.compute_list_add_barrier(compute_list)
	_record_atomic(compute_list, 0, elapsed_dt_sim)
	_rd.compute_list_add_barrier(compute_list)
	var radiation_substeps := _radiation_substeps(elapsed_dt_sim)
	var radiation_dt := elapsed_dt_sim / float(radiation_substeps)
	for _substep in range(radiation_substeps):
		_record_transport_pass(compute_list, radiation_dt, true)
		_rd.compute_list_add_barrier(compute_list)
		_record_atomic(compute_list, 2, radiation_dt)
		_rd.compute_list_add_barrier(compute_list)
		_record_transport_pass(compute_list, radiation_dt, false)
		_radiation_role_b = not _radiation_role_b
		_rd.compute_list_add_barrier(compute_list)
	_record_atomic(compute_list, 1, elapsed_dt_sim)
	_radiation_role_b = not _radiation_role_b
	_rd.compute_list_add_barrier(compute_list)
## Record one live external thermal event into the caller's open global-RD
## list.  It is intentionally separate from accepted physical time: density,
## momentum, populations, and ping-pong roles stay unchanged while the EOS
## energy/temperature and published coefficients are refreshed at the fence.
func record_heating_event(compute_list: int, delta_temperature_K: float) -> bool:
	if not is_operational() or compute_list < 0 \
			or not is_finite(delta_temperature_K) \
			or delta_temperature_K <= 0.0 \
			or delta_temperature_K > _temperature_max_K:
		return _reject("physical matter heating event requires a finite positive temperature delta within the model range")
	if _pending_initialization or _pending_steps > 0 or _pending_heating_events > 0:
		return _reject("physical matter heating event requires a committed publication")
	var record_started_us := Time.get_ticks_usec()
	_record_atomic(compute_list, 7, 0.0, delta_temperature_K)
	_rd.compute_list_add_barrier(compute_list)
	# The event changes the thermodynamic state but not the kinetics populations;
	# rebuild the live group coefficients before Observatory consumes them.
	_record_atomic(compute_list, 4, 0.0)
	_rd.compute_list_add_barrier(compute_list)
	_last_command_record_us = Time.get_ticks_usec() - record_started_us
	_pending_heating_events = 1
	_pending_heating_delta_temperature_K = delta_temperature_K
	_last_reject_error = ""
	return true




## Build the one reusable push-constant image per recorder. Layouts mirror the
## GLSL std430 structures exactly (init 24, hydro 20, atomic 32, transport 12,
## tracer 16 floats); words that vary per dispatch start at a placeholder and
## are patched with encode_float() before each bind. encode_float() writes the
## same 32-bit words PackedFloat32Array.to_byte_array() did.
func _build_push_constant_images() -> void:
	_pc_init = PackedFloat32Array([
		0.0, float(_particle_count), float(_grid.x), float(_grid.y), float(_grid.z),
		_extents.x, _extents.y, _extents.z, _center.x, _center.y, _center.z,
		_total_particle_mass, 0.0, _gamma_gas, _initial_temperature_K,
		_length_m_per_sim, _time_s_per_sim, _mass_kg_per_sim, _energy_J_per_sim,
		_density_kg_m3_per_sim, _energy_density_J_m3_per_sim, _velocity_m_s_per_sim,
		_dt_sim, 0.0,
	]).to_byte_array()
	_pc_hydro = PackedFloat32Array([
		0.0, float(_grid.x), float(_grid.y), float(_grid.z),
		_extents.x, _extents.y, _extents.z, 0.0, _gamma_gas,
		_velocity_m_s_per_sim, _density_floor, _pressure_floor,
		_temperature_min_K, _temperature_max_K, _length_m_per_sim, _time_s_per_sim,
		0.0, 0.0, 0.0, 0.0,
	]).to_byte_array()
	_pc_atomic = PackedFloat32Array([
		0.0, float(_grid.x), float(_grid.y), float(_grid.z),
		float(_group_count), float(_angle_count), 0.0, _c_reduced_sim,
		_length_m_per_sim, _time_s_per_sim, _density_kg_m3_per_sim,
		_energy_density_J_m3_per_sim, _velocity_m_s_per_sim, _gamma_gas,
		_density_floor, _pressure_floor, _temperature_min_K, _temperature_max_K,
		_maximum_v_over_c, 1.0 if _source_enabled else 0.0, _extents.x, _extents.y,
		_extents.z, _two_photon_rate_s_inv,
		0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
	]).to_byte_array()
	_pc_transport = PackedFloat32Array([
		float(_grid.x), float(_grid.y), float(_grid.z), float(_group_count),
		float(_angle_count), _extents.x, _extents.y, _extents.z,
		0.0, _c_reduced_sim, _transport_cfl, 0.0,
	]).to_byte_array()
	# The tracer push constants are invariant for the whole prepared lifetime.
	_pc_tracer = PackedFloat32Array([
		float(_particle_count), float(_grid.x), float(_grid.y), float(_grid.z),
		_extents.x, _extents.y, _extents.z, _center.x, _center.y, _center.z,
		_density_floor, _tracer_blend, _c_reduced_sim, _maximum_v_over_c, 0.0, 0.0,
	]).to_byte_array()


## Toggles the atomic source exchange by patching only the source-enabled word
## of the built atomic push constant: it touches no state, roles, or other
## numeric control.  Used by checkpoint restore and by fixture/gate harnesses;
## the default remains enabled.
func set_source_enabled(enabled: bool) -> void:
	_source_enabled = enabled
	if _pc_atomic.size() >= 80:
		_pc_atomic.encode_float(76, 1.0 if enabled else 0.0)


func _dispatch_init(compute_list: int, mode: int, count: int, fixed_scale: float,
		particle_offset: int = 0) -> void:
	_pc_init.encode_float(0, float(mode))
	_pc_init.encode_float(48, fixed_scale)
	_pc_init.encode_float(92, float(particle_offset))
	_rd.compute_list_set_push_constant(compute_list, _pc_init, _pc_init.size())
	_rd.compute_list_dispatch(compute_list, _groups_for(count, WORKGROUP_PARTICLE), 1, 1)


func _record_hydro(compute_list: int, axis: int, elapsed_dt: float) -> void:
	_rd.compute_list_bind_compute_pipeline(compute_list, _hydro_pipe)
	_rd.compute_list_bind_uniform_set(compute_list,
			_us_hydro_ba if _material_role_b else _us_hydro_ab, 0)
	_pc_hydro.encode_float(0, float(axis))
	_pc_hydro.encode_float(28, elapsed_dt)
	_rd.compute_list_set_push_constant(compute_list, _pc_hydro, _pc_hydro.size())
	_rd.compute_list_dispatch(compute_list, _groups_for(_cell_count, WORKGROUP_PARTICLE), 1, 1)


func _record_atomic(compute_list: int, mode: int, elapsed_dt: float,
		event_delta_temperature_K: float = 0.0) -> void:
	_rd.compute_list_bind_compute_pipeline(compute_list, _atomic_pipe)
	_rd.compute_list_bind_uniform_set(compute_list,
			_us_atomic[_atomic_role_index(_material_role_b, _radiation_role_b)] as RID, 0)
	_pc_atomic.encode_float(0, float(mode))
	_pc_atomic.encode_float(24, elapsed_dt)
	_pc_atomic.encode_float(96, event_delta_temperature_K)
	_rd.compute_list_set_push_constant(compute_list, _pc_atomic, _pc_atomic.size())
	_rd.compute_list_dispatch(compute_list, _groups_for(_cell_count, WORKGROUP_CELL), 1, 1)


func _record_transport(compute_list: int, elapsed_dt: float) -> void:
	# Validate the complete transport update before its first output write.
	# This keeps a fatal CFL/nonfinite/negative result transactional: the
	# guarded write pass sees STATUS_STEP_REJECTED and leaves the inactive
	# ping-pong buffer byte-identical.
	_record_transport_pass(compute_list, elapsed_dt, true)
	_rd.compute_list_add_barrier(compute_list)
	_record_transport_pass(compute_list, elapsed_dt, false)


func _record_transport_pass(compute_list: int, elapsed_dt: float,
		validate_only: bool) -> void:
	_rd.compute_list_bind_compute_pipeline(compute_list, _transport_pipe)
	_rd.compute_list_bind_uniform_set(compute_list,
			_us_transport_ba if _radiation_role_b else _us_transport_ab, 0)
	_pc_transport.encode_float(32, elapsed_dt)
	_pc_transport.encode_float(44, 1.0 if validate_only else 0.0)
	_rd.compute_list_set_push_constant(compute_list, _pc_transport, _pc_transport.size())
	_rd.compute_list_dispatch(compute_list,
			_groups_for(_radiation_count, WORKGROUP_TRANSPORT), 1, 1)


func _record_tracer(compute_list: int, material_role_b: bool,
		particle_offset: int, particle_count: int) -> void:
	_rd.compute_list_bind_compute_pipeline(compute_list, _tracer_pipe)
	_rd.compute_list_bind_uniform_set(compute_list,
			_us_tracer_b if material_role_b else _us_tracer_a, 0)
	_pc_tracer.encode_float(56, float(particle_offset))
	_rd.compute_list_set_push_constant(compute_list, _pc_tracer, _pc_tracer.size())
	_rd.compute_list_dispatch(compute_list, _groups_for(particle_count, WORKGROUP_PARTICLE), 1, 1)


func _hydro_substeps(elapsed_dt: float) -> int:
	# A cadence-delayed publication carries several parent physics steps.
	# Preserve that elapsed physical time while resolving each parent step
	# into a fixed face-consistent sequence; every cell uses the same flux dt.
	var target_dt := maxf(_dt_sim / float(HYDRO_SUBSTEPS_PER_BASE_STEP), 1.0e-12)
	return maxi(1, int(ceil(elapsed_dt / target_dt - 1.0e-6)))


func _radiation_substeps(elapsed_dt: float) -> int:
	var cell_size := 2.0 * _extents / Vector3(_grid)
	var minimum_spacing := minf(cell_size.x, minf(cell_size.y, cell_size.z))
	var courant := _c_reduced_sim * elapsed_dt * _max_ordinate_l1 / minimum_spacing
	return maxi(1, int(ceil(courant / _transport_cfl)))


func commit_recorded_steps() -> bool:
	if not _ready or _rd == null:
		return _reject("physical matter commit requires initialized GPU resources")
	var readback_started_us := Time.get_ticks_usec()
	var status_bytes := _rd.buffer_get_data(_status)
	_last_commit_fence_readback_us = Time.get_ticks_usec() - readback_started_us
	if status_bytes.size() < 64:
		# A short readback reports no usable status; the batch is not accepted
		# but nothing is corrupted, so this is a retryable rejection.
		return _reject("physical matter status readback is truncated")
	_last_status = _decode_status(status_bytes)
	var flags := int(_last_status.get("flags", 0))
	var fatal_flags := flags & ~STATUS_NONFATAL_MASK
	_last_fatal_flags = fatal_flags
	if fatal_flags != 0:
		_last_status["state_diagnostics"] = _diagnose_current_state()
		var hydro_debug := _rd.buffer_get_data(_hydro_debug)
		if hydro_debug.size() >= 64:
			var debug_words := hydro_debug.to_int32_array()
			var debug_floats := hydro_debug.to_float32_array()
			_last_status["hydro_failure_diagnostic"] = {
				"cell": (int(debug_words[0]) & 0xffffffff) - 1,
				"axis": int(debug_words[1]) & 0xffffffff,
				"candidate_reason": int(debug_words[2]) & 0xffffffff,
				"source_reason": int(debug_words[3]) & 0xffffffff,
				"candidate_density": float(debug_floats[4]),
				"candidate_total_energy": float(debug_floats[5]),
				"candidate_kinetic_energy": float(debug_floats[6]),
				"candidate_chemical_energy": float(debug_floats[7]),
				"candidate_thermal_energy": float(debug_floats[8]),
				"source_density": float(debug_floats[9]),
				"source_total_energy": float(debug_floats[10]),
				"source_kinetic_energy": float(debug_floats[11]),
				"source_thermal_energy": float(debug_floats[12]),
				"candidate_cached_pressure": float(debug_floats[14]),
				"source_cached_pressure": float(debug_floats[15]),
			}
		# A moving-frame preflight rejection only changed the status telemetry;
		# guarded dispatches left the physical buffers untouched. Restore the
		# role pair so publication remains the preflight state as well.
		if (flags & STATUS_STEP_REJECTED) != 0 and _pending_role_snapshot_valid:
			_material_role_b = _pending_material_role_b
			_radiation_role_b = _pending_radiation_role_b
		_pending_steps = 0
		_pending_time_sim = 0.0
		_pending_heating_events = 0
		_pending_heating_delta_temperature_K = 0.0
		_pending_initialization = false
		_pending_initialization_slice = false
		_pending_step_slice = false
		_step_phase = STEP_PHASE_IDLE
		_step_particle_offset = 0
		_step_elapsed_dt_sim = 0.0
		_step_hydro_substep = 0
		_step_radiation_substep = 0
		_step_radiation_stage = 0
		_step_material_role_b = _material_role_b
		_step_radiation_role_b = _radiation_role_b
		_pending_role_snapshot_valid = false
		# The reason names every set bit; status[3].w's packed dry/wet reasons
		# stay separate fields inside _last_status and status_values.
		return _fail("physical matter GPU status rejected publication: %s flags=%d status=%s"
				% [_describe_status_flags(fatal_flags), fatal_flags, JSON.stringify(_last_status)])
	if _pending_initialization:
		_pending_initialization = false
		_initialized = true
	_pending_initialization_slice = false
	if _pending_step_slice:
		_pending_step_slice = false
		if _step_phase != STEP_PHASE_FINAL_FENCE:
			_last_reject_error = ""
			return true
		_material_role_b = _step_material_role_b
		_radiation_role_b = _step_radiation_role_b
		_step_phase = STEP_PHASE_IDLE
		_step_particle_offset = 0
		_step_elapsed_dt_sim = 0.0
		_step_hydro_substep = 0
		_step_radiation_substep = 0
		_step_radiation_stage = 0
	_accepted_steps += _pending_steps
	_state_epoch += _pending_steps + _pending_heating_events
	_physical_time_sim += _pending_time_sim
	_accepted_heating_events += _pending_heating_events
	_total_heating_delta_temperature_K += _pending_heating_delta_temperature_K
	_pending_steps = 0
	_pending_time_sim = 0.0
	_pending_heating_events = 0
	_pending_heating_delta_temperature_K = 0.0
	_pending_role_snapshot_valid = false
	_last_reject_error = ""
	_clear_words(_hydro_debug)
	return true




func _decode_status(bytes: PackedByteArray) -> Dictionary:
	var words := bytes.to_int32_array()
	var floats := bytes.to_float32_array()
	return {
		"flags": int(words[0]) & 0xffffffff,
		"initial_out_of_domain": int(words[1]) & 0xffffffff,
		"nonfinite_inputs": int(words[2]) & 0xffffffff,
		"initialized_cells": int(words[3]) & 0xffffffff,
		"hydro_retries": int(words[4]) & 0xffffffff,
		"hydro_rejections": int(words[5]) & 0xffffffff,
		"kinetics_failures": int(words[6]) & 0xffffffff,
		"moving_frame_rejections": int(words[7]) & 0xffffffff,
		"transport_cfl_rejections": int(words[8]) & 0xffffffff,
		"transport_nonfinite": int(words[9]) & 0xffffffff,
		"transport_negative": int(words[10]) & 0xffffffff,
		"maximum_pre_source_v_over_c": float(floats[11]),
		"hydro_rejections_axis_x": int(words[12]) & 0xffffffff,
		"hydro_rejections_axis_y": int(words[13]) & 0xffffffff,
		"hydro_rejections_axis_z": int(words[14]) & 0xffffffff,
		"hydro_rejection_reasons": int(words[15]) & 0xff,
		"hydro_source_rejection_reasons": (int(words[15]) >> 8) & 0xff,
		"hydro_retry_reasons": (int(words[15]) >> 16) & 0xffff,
	}



func _diagnose_current_state() -> Dictionary:
	var material0_rid := _material0_b if _material_role_b else _material0_a
	var material1_rid := _material1_b if _material_role_b else _material1_a
	var population0_rid := _population0_b if _material_role_b else _population0_a
	var population1_rid := _population1_b if _material_role_b else _population1_a
	var material0 := _rd.buffer_get_data(material0_rid).to_float32_array()
	var material1 := _rd.buffer_get_data(material1_rid).to_float32_array()
	var population0 := _rd.buffer_get_data(population0_rid).to_float32_array()
	var population1 := _rd.buffer_get_data(population1_rid).to_float32_array()
	var active_cells := 0
	var nonfinite_cells := 0
	var zero_population_cells := 0
	var first_zero_population_cells: Array[int] = []
	var maximum_v_over_c := 0.0
	var maximum_velocity_cell := -1
	var maximum_velocity := Vector3.ZERO
	var minimum_density := INF
	var minimum_pressure := INF
	var minimum_pressure_cell := -1
	var maximum_population_relative_error := 0.0
	var level_data := _level_bytes.to_float32_array()
	var minimum_recovered_pressure := INF
	var minimum_recovered_pressure_cell := -1
	var minimum_recovered_pressure_state: Dictionary = {}
	var velocity_unit2 := _velocity_m_s_per_sim * _velocity_m_s_per_sim
	for cell in range(_cell_count):
		var offset := cell * 4
		var rho := material0[offset]
		if not is_finite(rho):
			nonfinite_cells += 1
			continue
		if rho <= _density_floor:
			continue
		active_cells += 1
		minimum_density = minf(minimum_density, rho)
		var momentum := Vector3(
				material0[offset + 1], material0[offset + 2], material0[offset + 3])
		var pressure := material1[offset + 2]
		var population_sum := (
				population0[offset] + population0[offset + 1]
				+ population0[offset + 2] + population0[offset + 3]
				+ population1[offset] + population1[offset + 1]
				+ population1[offset + 2])
		if not momentum.is_finite() or not is_finite(pressure) or not is_finite(population_sum):
			nonfinite_cells += 1
			continue
		if population_sum <= 0.0:
			zero_population_cells += 1
			if first_zero_population_cells.size() < 8:
				first_zero_population_cells.append(cell)
		var population_error := absf(population_sum - rho) / maxf(rho, _density_floor)
		maximum_population_relative_error = maxf(
				maximum_population_relative_error, population_error)
		if pressure < minimum_pressure:
			minimum_pressure = pressure
			minimum_pressure_cell = cell
		var chemical := 0.0
		for level in range(7):
			var population := 0.0
			if level < 4:
				population = population0[offset + level]
			else:
				population = population1[offset + level - 4]
			chemical += float(population) * level_data[level * 4] \
					/ (HYDROGEN_MASS_KG * velocity_unit2)
		var kinetic := 0.5 * momentum.length_squared() / rho
		var thermal := material1[offset] - kinetic - chemical
		var recovered_pressure := (_gamma_gas - 1.0) * thermal
		if recovered_pressure < minimum_recovered_pressure:
			minimum_recovered_pressure = recovered_pressure
			minimum_recovered_pressure_cell = cell
			var energy_scale := maxf(absf(material1[offset]), absf(kinetic) + absf(chemical))
			minimum_recovered_pressure_state = {
				"rho": rho,
				"total_energy": material1[offset],
				"kinetic_energy": kinetic,
				"chemical_energy": chemical,
				"thermal_energy": thermal,
				"cached_pressure": pressure,
				"thermal_roundoff_tolerance": 32.0 * FLOAT32_EPSILON * energy_scale,
				"physical_thermal_floor": _pressure_floor / (_gamma_gas - 1.0),
			}
		var velocity := momentum / rho
		var v_over_c := velocity.length() / maxf(_c_reduced_sim, 1.0e-20)
		if v_over_c > maximum_v_over_c:
			maximum_v_over_c = v_over_c
			maximum_velocity_cell = cell
			maximum_velocity = velocity
	return {
		"active_cells": active_cells,
		"nonfinite_cells": nonfinite_cells,
		"zero_population_cells": zero_population_cells,
		"first_zero_population_cells": first_zero_population_cells,
		"maximum_population_relative_error": maximum_population_relative_error,
		"maximum_v_over_c": maximum_v_over_c,
		"maximum_velocity_cell": maximum_velocity_cell,
		"maximum_velocity": str(maximum_velocity),
		"minimum_density": minimum_density if active_cells > 0 else 0.0,
		"minimum_pressure": minimum_pressure if active_cells > 0 else 0.0,
		"minimum_pressure_cell": minimum_pressure_cell,
		"minimum_recovered_pressure": minimum_recovered_pressure if active_cells > 0 else 0.0,
		"minimum_recovered_pressure_cell": minimum_recovered_pressure_cell,
		"minimum_recovered_pressure_state": minimum_recovered_pressure_state,
	}

func should_step(cassi_step: int) -> bool:
	return is_operational() and cassi_step > 0 and cassi_step % _cadence_steps == 0


func is_prepared() -> bool:
	return _prepared


func is_ready() -> bool:
	# Lives on the fatal latch only: a rejected guard, short readback, or
	# uncommitted-batch request must not leave the engine permanently not-ready.
	return _ready and _last_error.is_empty()


func is_operational() -> bool:
	return is_ready() and _initialized


func has_pending_publication() -> bool:
	return _pending_initialization or _pending_initialization_slice \
			or _pending_step_slice or _pending_steps > 0 \
			or _pending_heating_events > 0

## Most recent reason the engine is degraded: the latched fatal failure if any,
## else the last retryable rejection, else the last checkpoint rejection.
func last_error() -> String:
	if not _last_error.is_empty():
		return _last_error
	if not _last_reject_error.is_empty():
		return _last_reject_error
	return _last_checkpoint_error


func last_fatal_error() -> String:
	return _last_error


func last_reject_error() -> String:
	return _last_reject_error


func last_checkpoint_error() -> String:
	return _last_checkpoint_error


func has_fatal_error() -> bool:
	return not _last_error.is_empty()


## A non-empty reason whenever the engine is not operational, and an empty one
## whenever it is: consumers (sim UI, observatory, production probe) print this
## string, and a generic reason beats an empty one. Transient rejection and
## checkpoint reasons are only surfaced while they actually block readiness.
func _publication_error() -> String:
	if not _last_error.is_empty():
		return _last_error
	if _prepared and _ready and _initialized:
		return ""
	if not _last_reject_error.is_empty():
		return _last_reject_error
	if not _last_checkpoint_error.is_empty():
		return _last_checkpoint_error
	if not _prepared:
		return "physical matter engine is not prepared"
	if not _ready:
		return "physical matter GPU resources are not ready"
	return "physical matter state is not initialized"


func accepted_steps() -> int:
	return _accepted_steps


func physical_time_sim() -> float:
	return _physical_time_sim


func cadence_steps() -> int:
	return _cadence_steps


func publication() -> Dictionary:
	return {
		"ready": is_operational(),
		"error": _publication_error(),
		"initialized": _initialized,
		"fatal_flags": _last_fatal_flags,
		"last_error": _last_error,
		"last_reject_error": _last_reject_error,
		"last_checkpoint_error": _last_checkpoint_error,
		"pending_initialization": _pending_initialization or _pending_initialization_slice,
		"source_kind": "conditional_hydrogen_plasma",
		"numerical_identity": NUMERICAL_IDENTITY,
		"model_sha256": _model_sha256,
		"model_file_sha256": _model_file_sha256,
		"frequency_grid_sha256": _frequency_grid_sha256,
		"atomic_bundle_sha256": _atomic_bundle_sha256,
		"unit_map_sha256": _unit_map_sha256,
		"grid": _grid,
		"extents": _extents,
		"center": _center,
		"groups": _group_count,
		"angles": _angle_count,
		"length_m_per_sim": _length_m_per_sim,
		"time_s_per_sim": _time_s_per_sim,
		"c_reduced_sim": _c_reduced_sim,
		"density_kg_m3_per_sim": _density_kg_m3_per_sim,
		"energy_density_J_m3_per_sim": _energy_density_J_m3_per_sim,
		"accepted_steps": _accepted_steps,
		"state_epoch": _state_epoch,
		"reset_epoch": _reset_epoch,
		"physical_time_sim": _physical_time_sim,
		"heating_events": {
			"accepted": _accepted_heating_events,
			"total_delta_temperature_K": _total_heating_delta_temperature_K,
			"pending": _pending_heating_events,
			"pending_delta_temperature_K": _pending_heating_delta_temperature_K,
		},
		"resource_bytes": _resource_bytes,
		"radiation_substeps": _cadence_radiation_substeps,
		"hydro_substeps": _cadence_hydro_substeps,
		"last_command_record_us": _last_command_record_us,
		"last_commit_fence_readback_us": _last_commit_fence_readback_us,
		"source_enabled": _source_enabled,
		"tracer_blend": _tracer_blend,
		# The tracer writes the borrowed host velocity buffer, so a checkpoint
		# that restores the engine's own buffers is byte-exact only when the
		# caller also restores that coupled buffer. Enforced by carrying it in
		# every checkpoint payload set; declared here for consumers.
		"coupling_writes_host_velocity": _tracer_blend > 0.0,
		"coupled_velocity": _vel,
		"material_role_b": _material_role_b,
		"radiation_role_b": _radiation_role_b,
		"material0": _material0_b if _material_role_b else _material0_a,
		"material1": _material1_b if _material_role_b else _material1_a,
		"population0": _population0_b if _material_role_b else _population0_a,
		"population1": _population1_b if _material_role_b else _population1_a,
		"radiation": _radiation_b if _radiation_role_b else _radiation_a,
		"frequency": _frequency,
		"ordinates": _ordinate,
		"opacity": _opacity,
		"emission": _emission,
		"ledger0": _ledger0,
		"ledger1": _ledger1,
		"ledger2": _ledger2,
		"status": _status,
		"status_values": _last_status.duplicate(true),
	}

## Borrowed live RIDs for read-only render/diagnostic consumers. Ownership
## remains here; consumers must release uniform sets before shutdown.
func render_resources() -> Dictionary:
	if not is_operational():
		return {}
	return publication()

## A fence-bound, in-memory checkpoint used by the production wrapper and
## workbench.  It carries both ping-pong roles plus the borrowed host velocity
## buffer the tracer writes, so a coupled restore is byte-exact; all validation
## happens before the first GPU buffer update.
func checkpoint() -> Dictionary:
	_last_checkpoint_error = ""
	if not is_operational():
		return _checkpoint_dict("physical matter checkpoint requires operational state")
	if has_pending_publication():
		return _checkpoint_dict("physical matter checkpoint has an uncommitted batch")
	var buffers := _checkpoint_buffer_rids()
	var expected_sizes := _checkpoint_expected_sizes()
	var encoded: Dictionary = {}
	var hashes: Dictionary = {}
	for name_value in buffers:
		var name := String(name_value)
		var rid := buffers[name] as RID
		if not rid.is_valid():
			return _checkpoint_dict("physical matter checkpoint buffer is unavailable: " + name)
		var payload := _rd.buffer_get_data(rid)
		if payload.size() != int(expected_sizes[name]):
			return _checkpoint_dict("physical matter checkpoint buffer size mismatch: " + name)
		encoded[name] = Marshalls.raw_to_base64(payload)
		hashes[name] = _sha256(payload)
	return {
		"ok": true,
		"schema_version": CHECKPOINT_SCHEMA,
		"numerical_identity": NUMERICAL_IDENTITY,
		"source_kind": "conditional_hydrogen_plasma",
		"model_sha256": _model_sha256,
		"model_file_sha256": _model_file_sha256,
		"frequency_grid_sha256": _frequency_grid_sha256,
		"atomic_bundle_sha256": _atomic_bundle_sha256,
		"unit_map_sha256": _unit_map_sha256,
		"grid": [_grid.x, _grid.y, _grid.z],
		"extents": [_extents.x, _extents.y, _extents.z],
		"center": [_center.x, _center.y, _center.z],
		"particle_count": _particle_count,
		"cell_count": _cell_count,
		"group_count": _group_count,
		"angle_count": _angle_count,
		"accepted_steps": _accepted_steps,
		"state_epoch": _state_epoch,
		"reset_epoch": _reset_epoch,
		"physical_time_sim": _physical_time_sim,
		"material_role_b": _material_role_b,
		"radiation_role_b": _radiation_role_b,
		"pending_steps": 0,
		"pending_time_sim": 0.0,
		"pending_initialization": false,
		"tracer_blend": _tracer_blend,
		"coupling_writes_host_velocity": _tracer_blend > 0.0,
		"source_enabled": _source_enabled,
		"buffers": encoded,
		"buffer_sha256": hashes,
	}


func restore_checkpoint(value: Variant) -> bool:
	_last_checkpoint_error = ""
	if value is String:
		return _restore_file_checkpoint(String(value))
	if not value is Dictionary:
		return _checkpoint_reject("physical matter checkpoint must be a Dictionary or directory path")
	if not _ready:
		return _checkpoint_reject("physical matter restore requires initialized resources")
	if has_pending_publication():
		return _checkpoint_reject("physical matter restore requires a committed publication")
	var validated := _validate_memory_checkpoint(value as Dictionary)
	if not bool(validated.get("ok", false)):
		return _checkpoint_reject(String(validated.get(
				"error", "invalid physical matter checkpoint")))
	_apply_checkpoint(validated["payloads"] as Dictionary, validated)
	return true


## Canonical checkpoint payload names.  The memory Dictionary and the on-disk
## manifest both key their payload set by these names, so one validator and one
## applier serve both paths.
func _checkpoint_buffer_rids() -> Dictionary:
	return {
		"material0_a": _material0_a, "material1_a": _material1_a,
		"population0_a": _population0_a, "population1_a": _population1_a,
		"material0_b": _material0_b, "material1_b": _material1_b,
		"population0_b": _population0_b, "population1_b": _population1_b,
		"radiation_a": _radiation_a, "radiation_b": _radiation_b,
		"opacity": _opacity, "emission": _emission,
		"ledger0": _ledger0, "ledger1": _ledger1, "ledger2": _ledger2,
		"status": _status,
		# Borrowed host buffer, written by the tracer; carried so a restore
		# reproduces the coupled state rather than only the engine's own
		# ping-pong buffers.
		"velocity": _vel,
	}


func _checkpoint_expected_sizes() -> Dictionary:
	return {
		"material0_a": _cell_count * 16, "material1_a": _cell_count * 16,
		"population0_a": _cell_count * 16, "population1_a": _cell_count * 16,
		"material0_b": _cell_count * 16, "material1_b": _cell_count * 16,
		"population0_b": _cell_count * 16, "population1_b": _cell_count * 16,
		"radiation_a": _radiation_count * 4, "radiation_b": _radiation_count * 4,
		"opacity": _cell_count * _group_count * 4,
		"emission": _cell_count * _group_count * 4,
		"ledger0": _cell_count * 16, "ledger1": _cell_count * 16,
		"ledger2": _cell_count * 16, "status": 64,
		"velocity": _particle_count * 16,
	}


## Write a fully validated payload set into the GPU buffers.  Only reachable
## after every check has passed, so a rejected checkpoint never mutates state.
func _apply_checkpoint(payloads: Dictionary, fields: Dictionary) -> void:
	var targets := _checkpoint_buffer_rids()
	for name_value in targets:
		var name := String(name_value)
		var payload := payloads[name] as PackedByteArray
		_rd.buffer_update(targets[name] as RID, 0, payload.size(), payload)
	_material_role_b = bool(fields["material_role_b"])
	_radiation_role_b = bool(fields["radiation_role_b"])
	_accepted_steps = int(fields["accepted_steps"])
	_state_epoch = int(fields["state_epoch"])
	_reset_epoch = int(fields["reset_epoch"])
	_physical_time_sim = float(fields["physical_time_sim"])
	_pending_steps = 0
	_pending_time_sim = 0.0
	_pending_initialization = false
	_pending_role_snapshot_valid = false
	_initialized = true
	# Continuation controls: the restored state only evolves identically if the
	# source switch and tracer blend match the ones that produced it. Both live
	# in already-built push-constant images, so patch them in place rather than
	# rebuilding (atomic word19/byte 76 via set_source_enabled, tracer word11/
	# byte 44 here).
	_tracer_blend = float(fields["tracer_blend"])
	if _pc_tracer.size() >= 48:
		_pc_tracer.encode_float(44, _tracer_blend)
	set_source_enabled(bool(fields["source_enabled"]))
	_last_status = _decode_status(payloads["status"] as PackedByteArray)
	_last_fatal_flags = 0
	_last_reject_error = ""
	_last_checkpoint_error = ""


## Identity, shape, counter, role, and pending-batch checks shared by the memory
## checkpoint and the on-disk manifest.  Returns the validated metadata fields.
func _validate_checkpoint_fields(value: Dictionary) -> Dictionary:
	for pair: Array in [
		["schema_version", CHECKPOINT_SCHEMA],
		["numerical_identity", NUMERICAL_IDENTITY],
		["source_kind", "conditional_hydrogen_plasma"],
		["model_sha256", _model_sha256],
		["model_file_sha256", _model_file_sha256],
		["frequency_grid_sha256", _frequency_grid_sha256],
		["atomic_bundle_sha256", _atomic_bundle_sha256],
		["unit_map_sha256", _unit_map_sha256],
	]:
		if String(value.get(String(pair[0]), "")) != String(pair[1]):
			return {"ok": false, "error": "checkpoint identity mismatch: " + String(pair[0])}
	for pair: Array in [
		["particle_count", _particle_count],
		["cell_count", _cell_count],
		["group_count", _group_count],
		["angle_count", _angle_count],
	]:
		var count_value: Variant = value.get(String(pair[0]), null)
		if not _is_checkpoint_int(count_value) or int(count_value) != int(pair[1]):
			return {"ok": false, "error": "checkpoint shape identity mismatch"}
	var grid_value: Variant = value.get("grid", null)
	if not grid_value is Array or (grid_value as Array).size() != 3:
		return {"ok": false, "error": "checkpoint grid identity is malformed"}
	var grid_values := grid_value as Array
	for index in range(3):
		if not _is_checkpoint_int(grid_values[index]) \
				or int(grid_values[index]) != _grid[index]:
			return {"ok": false, "error": "checkpoint grid identity mismatch"}
	if not _checkpoint_vector_matches(value.get("extents", null), _extents) \
			or not _checkpoint_vector_matches(value.get("center", null), _center):
		return {"ok": false, "error": "checkpoint spatial identity mismatch"}
	for key in ["accepted_steps", "state_epoch", "reset_epoch"]:
		if not value.has(key) or not _is_checkpoint_int(value[key]) \
				or int(value[key]) < 0:
			return {"ok": false, "error": "invalid checkpoint counter: " + key}
	if not value.has("physical_time_sim") \
			or not (value.physical_time_sim is int or value.physical_time_sim is float) \
			or not is_finite(float(value.physical_time_sim)) \
			or float(value.physical_time_sim) < 0.0:
		return {"ok": false, "error": "invalid checkpoint counter: physical_time_sim"}
	if not value.has("material_role_b") or not value.material_role_b is bool \
			or not value.has("radiation_role_b") or not value.radiation_role_b is bool:
		return {"ok": false, "error": "checkpoint ping-pong roles are malformed"}
	# The atomic source switch and the tracer blend change how the state
	# evolves, so a checkpoint carries them as continuation controls rather
	# than as decorative metadata: _apply_checkpoint restores both, and a
	# caller that wants a different control must set it explicitly.
	if not value.has("tracer_blend") \
			or not (value.tracer_blend is int or value.tracer_blend is float) \
			or not is_finite(float(value.tracer_blend)) \
			or float(value.tracer_blend) < 0.0 or float(value.tracer_blend) > 1.0:
		return {"ok": false, "error": "invalid checkpoint control: tracer_blend"}
	if not value.has("source_enabled") or not value.source_enabled is bool:
		return {"ok": false, "error": "invalid checkpoint control: source_enabled"}
	# Derived integrity field, not a control: it must agree with the restored
	# tracer blend so a hand-edited manifest cannot claim the coupled host
	# velocity is untouched while the tracer writes it (or vice versa).
	if not value.has("coupling_writes_host_velocity") \
			or not value.coupling_writes_host_velocity is bool \
			or bool(value.coupling_writes_host_velocity) != (float(value.tracer_blend) > 0.0):
		return {"ok": false, "error": "invalid checkpoint control: coupling_writes_host_velocity"}
	if value.has("pending_steps") and (not _is_checkpoint_int(value.pending_steps) \
			or int(value.pending_steps) != 0):
		return {"ok": false, "error": "checkpoint contains an uncommitted batch"}
	if value.has("pending_time_sim") \
			and (not (value.pending_time_sim is int or value.pending_time_sim is float) \
			or not is_finite(float(value.pending_time_sim)) \
			or not is_zero_approx(float(value.pending_time_sim))):
		return {"ok": false, "error": "checkpoint contains an uncommitted batch"}
	if value.has("pending_initialization") \
			and (not value.pending_initialization is bool or value.pending_initialization):
		return {"ok": false, "error": "checkpoint contains an uncommitted batch"}
	return {
		"ok": true,
		"accepted_steps": int(value.accepted_steps),
		"state_epoch": int(value.state_epoch),
		"reset_epoch": int(value.reset_epoch),
		"physical_time_sim": float(value.physical_time_sim),
		"material_role_b": bool(value.material_role_b),
		"radiation_role_b": bool(value.radiation_role_b),
		"tracer_blend": float(value.tracer_blend),
		"source_enabled": bool(value.source_enabled),
	}


## Checkpoint numbers arrive either as GDScript ints (in-memory Dictionary) or
## as JSON numbers (on-disk manifest), so an integral float is accepted while
## strings, bools, null, and fractional or non-finite floats are rejected.
func _is_checkpoint_int(value: Variant) -> bool:
	if value is int:
		return true
	if value is float:
		return is_finite(value) and value == floor(value)
	return false


func _validate_memory_checkpoint(value: Dictionary) -> Dictionary:
	var fields := _validate_checkpoint_fields(value)
	if not bool(fields.get("ok", false)):
		return fields
	var buffers_value: Variant = value.get("buffers", null)
	if not buffers_value is Dictionary:
		return {"ok": false, "error": "checkpoint buffer table is malformed"}
	var buffers := buffers_value as Dictionary
	var hashes_value: Variant = value.get("buffer_sha256", null)
	if not hashes_value is Dictionary:
		return {"ok": false, "error": "checkpoint buffer hash table is malformed"}
	var hashes := hashes_value as Dictionary
	var expected_sizes := _checkpoint_expected_sizes()
	var payloads: Dictionary = {}
	for name_value in expected_sizes:
		var name := String(name_value)
		var encoded := String(buffers.get(name, ""))
		if encoded.is_empty():
			return {"ok": false, "error": "checkpoint buffer is missing: " + name}
		var payload := Marshalls.base64_to_raw(encoded)
		if payload.size() != int(expected_sizes[name]):
			return {"ok": false, "error": "checkpoint byte length mismatch: " + name}
		if String(hashes.get(name, "")) != _sha256(payload):
			return {"ok": false, "error": "checkpoint buffer hash mismatch: " + name}
		payloads[name] = payload
	var validation_error := _validate_checkpoint_payloads(payloads)
	if not validation_error.is_empty():
		return {"ok": false, "error": validation_error}
	fields["payloads"] = payloads
	return fields


func _checkpoint_vector_matches(value: Variant, expected: Vector3) -> bool:
	if not value is Array or (value as Array).size() != 3:
		return false
	var values := value as Array
	for component in range(3):
		if not (values[component] is int or values[component] is float) \
				or not is_finite(float(values[component])):
			return false
	return is_equal_approx(float(values[0]), expected.x) \
			and is_equal_approx(float(values[1]), expected.y) \
			and is_equal_approx(float(values[2]), expected.z)


func _validate_checkpoint_payloads(payloads: Dictionary) -> String:
	# The borrowed host velocity is part of the coupled state and must be
	# finite, but unlike material/radiation it is signed: no non-negativity
	# or positivity rule applies to it.
	for name in ["material0_a", "material1_a", "population0_a", "population1_a",
			"material0_b", "material1_b", "population0_b", "population1_b",
			"radiation_a", "radiation_b", "opacity", "emission",
			"ledger0", "ledger1", "ledger2", "velocity"]:
		var finite_values := (payloads[name] as PackedByteArray).to_float32_array()
		for item in finite_values:
			if not is_finite(item):
				return "checkpoint contains a nonfinite value: " + String(name)
	for name in ["material0_a", "material0_b"]:
		var material0 := (payloads[name] as PackedByteArray).to_float32_array()
		var material1_name := "material1_a" if name.ends_with("_a") else "material1_b"
		var population0_name := "population0_a" if name.ends_with("_a") else "population0_b"
		var population1_name := "population1_a" if name.ends_with("_a") else "population1_b"
		var material1 := (payloads[material1_name] as PackedByteArray).to_float32_array()
		var population0 := (payloads[population0_name] as PackedByteArray).to_float32_array()
		var population1 := (payloads[population1_name] as PackedByteArray).to_float32_array()
		for cell in range(_cell_count):
			var base := cell * 4
			# material1 is (energy, temperature, pressure, divergence): lanes 0-2
			# are non-negative by construction, while lane 3 carries the signed
			# hydro divergence diagnostic (cassi_physical_matter_hydro.glsl:412
			# `state.q1.w = divergence`) and must not be range-checked.  Every
			# lane is already covered by the finite pass above.
			if material0[base] < 0.0 or material1[base] < 0.0 \
					or material1[base + 1] < 0.0 or material1[base + 2] < 0.0:
				return "checkpoint material positivity violation"
			if population0[base] < 0.0 or population0[base + 1] < 0.0 \
					or population0[base + 2] < 0.0 or population0[base + 3] < 0.0 \
					or population1[base] < 0.0 or population1[base + 1] < 0.0 \
					or population1[base + 2] < 0.0 or population1[base + 3] < 0.0:
				return "checkpoint population positivity violation"
			var rho := material0[base]
			var population_sum := population0[base] + population0[base + 1] \
					+ population0[base + 2] + population0[base + 3] \
					+ population1[base] + population1[base + 1] + population1[base + 2]
			if rho > _density_floor and (population_sum <= 0.0 \
					or absf(population_sum - rho) > maxf(2.0e-4 * rho, 1.0e-20)):
				return "checkpoint population closure violation"
	for name in ["radiation_a", "radiation_b", "opacity", "emission"]:
		var nonnegative_values := (payloads[name] as PackedByteArray).to_float32_array()
		for item in nonnegative_values:
			if item < 0.0:
				return "checkpoint nonnegative-channel violation: " + String(name)
	for name in ["ledger0", "ledger1"]:
		var ledger_values := (payloads[name] as PackedByteArray).to_float32_array()
		for cell in range(_cell_count):
			var base := cell * 4
			if ledger_values[base] < 0.0 or ledger_values[base + 1] < 0.0 \
					or (name == "ledger1" and ledger_values[base + 3] < 0.0) \
					or (name == "ledger0" and ledger_values[base + 2] < 0.0):
				return "checkpoint ledger positivity violation"
	var status := (payloads["status"] as PackedByteArray).to_int32_array()
	var flags := int(status[0]) & 0xffffffff
	if (flags & ~STATUS_NONFATAL_MASK) != 0:
		return "checkpoint status contains fatal flags"
	return ""


func _checkpoint_reject(message: String) -> bool:
	_last_checkpoint_error = message
	return false


## Rejection for the checkpoint entry points that return a Dictionary.
func _checkpoint_dict(message: String) -> Dictionary:
	_last_checkpoint_error = message
	return {"ok": false, "error": message}


## Directory checkpoint: the same canonical payload set, field validator, and
## payload validator as the in-memory path, with payloads stored one file per
## buffer.  Rejects an uncommitted batch rather than snapshotting a torn state.
func write_checkpoint(directory: String) -> Dictionary:
	_last_checkpoint_error = ""
	if not is_operational():
		return _checkpoint_dict("physical matter checkpoint requires operational state")
	if has_pending_publication():
		return _checkpoint_dict("physical matter checkpoint has an uncommitted batch")
	var absolute := ProjectSettings.globalize_path(directory)
	var mkdir_error := DirAccess.make_dir_recursive_absolute(absolute)
	if mkdir_error != OK:
		return _checkpoint_dict("cannot create physical matter checkpoint directory")
	var buffers := _checkpoint_buffer_rids()
	var expected_sizes := _checkpoint_expected_sizes()
	var files: Dictionary = {}
	for name_value in buffers:
		var name := String(name_value)
		var rid := buffers[name] as RID
		if not rid.is_valid():
			return _checkpoint_dict("physical matter checkpoint buffer is unavailable: " + name)
		var payload := _rd.buffer_get_data(rid)
		if payload.size() != int(expected_sizes[name]):
			return _checkpoint_dict("physical matter checkpoint buffer size mismatch: " + name)
		var filename := name + ".bin"
		var file := FileAccess.open(directory.path_join(filename), FileAccess.WRITE)
		if file == null:
			return _checkpoint_dict("cannot write checkpoint payload " + filename)
		file.store_buffer(payload)
		file.close()
		files[name] = {"bytes": payload.size(), "sha256": _sha256(payload)}
	var manifest := {
		"schema_version": CHECKPOINT_SCHEMA,
		"numerical_identity": NUMERICAL_IDENTITY,
		"source_kind": "conditional_hydrogen_plasma",
		"model_sha256": _model_sha256,
		"model_file_sha256": _model_file_sha256,
		"frequency_grid_sha256": _frequency_grid_sha256,
		"atomic_bundle_sha256": _atomic_bundle_sha256,
		"unit_map_sha256": _unit_map_sha256,
		"grid": [_grid.x, _grid.y, _grid.z],
		"extents": [_extents.x, _extents.y, _extents.z],
		"center": [_center.x, _center.y, _center.z],
		"particle_count": _particle_count,
		"cell_count": _cell_count,
		"group_count": _group_count,
		"angle_count": _angle_count,
		"accepted_steps": _accepted_steps,
		"state_epoch": _state_epoch,
		"reset_epoch": _reset_epoch,
		"physical_time_sim": _physical_time_sim,
		"material_role_b": _material_role_b,
		"radiation_role_b": _radiation_role_b,
		"pending_steps": 0,
		"pending_time_sim": 0.0,
		"pending_initialization": false,
		"tracer_blend": _tracer_blend,
		"coupling_writes_host_velocity": _tracer_blend > 0.0,
		"source_enabled": _source_enabled,
		"files": files,
	}
	var manifest_text := JSON.stringify(manifest, "  ") + "\n"
	var manifest_file := FileAccess.open(directory.path_join("manifest.json"), FileAccess.WRITE)
	if manifest_file == null:
		return _checkpoint_dict("cannot write physical matter checkpoint manifest")
	manifest_file.store_string(manifest_text)
	manifest_file.close()
	return {"ok": true, "directory": directory, "manifest": manifest}


func _restore_file_checkpoint(directory: String) -> bool:
	if not _ready:
		return _checkpoint_reject("physical matter restore requires initialized resources")
	if has_pending_publication():
		return _checkpoint_reject("physical matter restore requires a committed publication")
	var manifest_path := directory.path_join("manifest.json")
	if not FileAccess.file_exists(manifest_path):
		return _checkpoint_reject("physical matter checkpoint manifest is missing")
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
	if not parsed is Dictionary:
		return _checkpoint_reject("physical matter checkpoint manifest is malformed")
	var manifest := parsed as Dictionary
	# Same metadata validator the in-memory path runs: identity hashes (including
	# the model file hash), shape, grid/extents/center, counters with range
	# checks, ping-pong roles, and the uncommitted-batch fields.
	var fields := _validate_checkpoint_fields(manifest)
	if not bool(fields.get("ok", false)):
		return _checkpoint_reject(String(fields.get(
				"error", "invalid physical matter checkpoint")))
	var files_value: Variant = manifest.get("files", {})
	if not files_value is Dictionary:
		return _checkpoint_reject("physical matter checkpoint file table is malformed")
	var files := files_value as Dictionary
	var expected_sizes := _checkpoint_expected_sizes()
	var payloads: Dictionary = {}
	for name_value in expected_sizes:
		var name := String(name_value)
		var record_value: Variant = files.get(name, {})
		if not record_value is Dictionary:
			return _checkpoint_reject("physical matter checkpoint record is missing: " + name)
		var record := record_value as Dictionary
		var payload := FileAccess.get_file_as_bytes(directory.path_join(name + ".bin"))
		if payload.size() != int(expected_sizes[name]) \
				or payload.size() != int(record.get("bytes", -1)) \
				or _sha256(payload) != String(record.get("sha256", "")):
			return _checkpoint_reject("physical matter checkpoint payload mismatch: " + name)
		payloads[name] = payload
	var validation_error := _validate_checkpoint_payloads(payloads)
	if not validation_error.is_empty():
		return _checkpoint_reject(validation_error)
	_apply_checkpoint(payloads, fields)
	return true


func shutdown() -> void:
	if _rd != null:
		var seen: Dictionary = {}
		for rid_value in _uniform_rids() + _pipeline_rids() + _shader_rids() + _buffer_rids():
			var rid := rid_value as RID
			if rid.is_valid() and not seen.has(rid):
				seen[rid] = true
				_rd.free_rid(rid)
	_clear_gpu_handles()
	_reset_prepared_state()


func _buffer_rids() -> Array:
	return [_fixed, _material0_a, _material1_a, _population0_a, _population1_a,
		_material0_b, _material1_b, _population0_b, _population1_b,
		_radiation_a, _radiation_b, _frequency, _ordinate, _line_a, _line_b,
		_level, _rates, _opacity, _emission, _gravity, _ledger0, _ledger1,
		_ledger2, _status, _hydro_debug]


func _uniform_rids() -> Array:
	var result: Array = [_us_init, _us_hydro_ab, _us_hydro_ba,
		_us_transport_ab, _us_transport_ba, _us_tracer_a, _us_tracer_b]
	for value in _us_atomic:
		result.append(value)
	return result


func _pipeline_rids() -> Array:
	return [_init_pipe, _hydro_pipe, _atomic_pipe, _transport_pipe, _tracer_pipe]


func _shader_rids() -> Array:
	return [_init_shader, _hydro_shader, _atomic_shader, _transport_shader, _tracer_shader]


func _clear_gpu_handles() -> void:
	_rd = null
	_ready = false
	_initialized = false
	_pending_initialization = false
	_pending_initialization_slice = false
	_initialization_particle_offset = 0
	_step_phase = STEP_PHASE_IDLE
	_step_particle_offset = 0
	_step_elapsed_dt_sim = 0.0
	_step_hydro_substep = 0
	_step_radiation_substep = 0
	_step_radiation_stage = 0
	_pending_step_slice = false
	_pos = RID(); _vel = RID(); _acc = RID()
	_fixed = RID(); _material0_a = RID(); _material1_a = RID()
	_population0_a = RID(); _population1_a = RID()
	_material0_b = RID(); _material1_b = RID()
	_population0_b = RID(); _population1_b = RID()
	_radiation_a = RID(); _radiation_b = RID(); _frequency = RID(); _ordinate = RID()
	_line_a = RID(); _line_b = RID(); _level = RID(); _rates = RID()
	_opacity = RID(); _emission = RID(); _gravity = RID()
	_ledger0 = RID(); _ledger1 = RID(); _ledger2 = RID(); _status = RID()
	_hydro_debug = RID()
	_init_shader = RID(); _hydro_shader = RID(); _atomic_shader = RID()
	_transport_shader = RID(); _tracer_shader = RID()
	_init_pipe = RID(); _hydro_pipe = RID(); _atomic_pipe = RID()
	_transport_pipe = RID(); _tracer_pipe = RID()
	_us_init = RID(); _us_hydro_ab = RID(); _us_hydro_ba = RID()
	_us_atomic.clear()
	_us_transport_ab = RID(); _us_transport_ba = RID()
	_us_tracer_a = RID(); _us_tracer_b = RID()

func _reset_prepared_state() -> void:
	_prepared = false
	_model = {}
	_model_path = ""
	_model_file_sha256 = ""
	_model_sha256 = ""
	_frequency_grid_sha256 = ""
	_atomic_bundle_sha256 = ""
	_unit_map_sha256 = ""
	_frequency_bytes = PackedByteArray()
	_ordinate_bytes = PackedByteArray()
	_line_a_bytes = PackedByteArray()
	_line_b_bytes = PackedByteArray()
	_level_bytes = PackedByteArray()
	_rate_bytes = PackedByteArray()
	_accepted_steps = 0
	_state_epoch = 1
	_reset_epoch = 1
	_physical_time_sim = 0.0
	_pending_steps = 0
	_pending_time_sim = 0.0
	_pending_heating_events = 0
	_pending_heating_delta_temperature_K = 0.0
	_accepted_heating_events = 0
	_total_heating_delta_temperature_K = 0.0
	_pending_initialization = false
	_pending_initialization_slice = false
	_initialization_particle_offset = 0
	_step_phase = STEP_PHASE_IDLE
	_step_particle_offset = 0
	_step_elapsed_dt_sim = 0.0
	_step_hydro_substep = 0
	_step_radiation_substep = 0
	_step_radiation_stage = 0
	_step_material_role_b = false
	_step_radiation_role_b = false
	_pending_step_slice = false
	_material_role_b = false
	_radiation_role_b = false
	_pending_role_snapshot_valid = false
	_pending_material_role_b = false
	_pending_radiation_role_b = false
	_last_error = ""
	_last_reject_error = ""
	_last_checkpoint_error = ""
	_last_fatal_flags = 0
	_pc_init = PackedByteArray()
	_pc_hydro = PackedByteArray()
	_pc_atomic = PackedByteArray()
	_pc_transport = PackedByteArray()
	_pc_tracer = PackedByteArray()
	_two_photon_rate_s_inv = 0.0
	_source_enabled = true
	_cadence_radiation_substeps = 1
	_cadence_hydro_substeps = 1
	_last_command_record_us = 0
	_last_commit_fence_readback_us = 0


func _estimate_resource_bytes() -> int:
	var cell_vec4_buffers := 8 + 1 + 3
	var bytes := _cell_count * 16 * cell_vec4_buffers
	bytes += _cell_count * 7 * 16
	bytes += _radiation_count * 4 * 2
	bytes += _cell_count * _group_count * 4 * 2
	bytes += _frequency_bytes.size() + _ordinate_bytes.size() + _line_a_bytes.size()
	bytes += _line_b_bytes.size() + _level_bytes.size() + _rate_bytes.size() + 64 + 64
	return bytes


## Index of the atomic uniform set for a ping-pong role pair, matching the
## iteration order used to create them.
func _atomic_role_index(matter_b: bool, radiation_b: bool) -> int:
	return (2 if matter_b else 0) + (1 if radiation_b else 0)


func _groups_for(count: int, local_size: int) -> int:
	return maxi(1, int(ceil(float(count) / float(local_size))))


func _finite_vec3(value: Vector3) -> bool:
	return is_finite(value.x) and is_finite(value.y) and is_finite(value.z)


func _sha256(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(bytes)
	return context.finish().hex_encode()


## Names every set bit of a fatal status word so a failure message never
## collapses two different faults into one masked number.
func _describe_status_flags(flags: int) -> String:
	var names := PackedStringArray()
	for bit in STATUS_FLAG_NAMES:
		if (flags & int(bit)) != 0:
			names.append(String(STATUS_FLAG_NAMES[bit]))
	return "none" if names.is_empty() else ", ".join(names)


## Latch a genuinely fatal failure: resource/model/prepare faults and fatal GPU
## status flags.  Only these make the engine permanently not-ready.
func _fail(message: String) -> bool:
	_last_error = message
	push_error(message)
	return false


## Record a retryable rejection (ordering, argument, or readback fault).  The
## engine stays ready: no GPU state was touched and the caller can retry.
func _reject(message: String) -> bool:
	_last_reject_error = message
	push_error(message)
	return false
