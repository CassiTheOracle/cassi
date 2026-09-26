extends Node
## Production-scale acceptance arm for the conditional physical-matter path.
## The arm deliberately keeps the main-scene particle configuration intact,
## records the default-off solver digest before enabling physical matter, and
## only samples published telemetry or captured images after physical init.

const OUTPUT := "res://_diag/physical_matter"
const RECEIPT_PATH := OUTPUT + "/production_acceptance.json"
const PREREGISTRATION := "research/presentation/physical_matter_implementation_prereg.md"

# PM-G0 fixture. The digest is evidence only; parity is owned by the battery's
# existing default-chain arms and no pre-feature digest is invented here.
const FIXED_SEED := 736241
const G0_FIXED_STEPS := 8

# PM-G9 production fixture.
const PRODUCTION_PARTICLE_COUNT := 2_500_000
const REQUIRED_PHYSICAL_STEPS := 256

# PM-G10 constants are frozen in source before the first qualifying run. They
# are intentionally not changed in response to the measurements below.
const G10_MAX_GPU_UPDATE_P95_US := 100_000.0
const G10_MAX_RENDERER_FRAME_P95_MS := 100.0
const G10_MAX_PHYSICAL_ALLOCATION_BYTES := 1_536 * 1024 * 1024
const G10_MAX_RENDERER_ALLOCATION_BYTES := 512 * 1024 * 1024
const G10_EXPECTED_CADENCE_STEPS := 8
const G10_EXPECTED_GROUPS := 24
const G10_EXPECTED_ANGLES := 26
const G10_MIN_GPU_SAMPLES := 8
const G10_MIN_RENDERER_SAMPLES := 32
const G10_MIN_CADENCE_SAMPLES := 8
const G10_MAX_RUN_MS := 180_000

# Raw XYZ image decoding and the packed status-flag policy are shared with the
# engine arm through this helper so the two arms cannot drift (M7).
const ArmMetrics := preload("res://scripts/physical_matter_arm_metrics.gd")
const MODE_NAMES: Array[String] = ["Scientific", "Observatory", "Cinematic"]
const LEGACY_SOURCE_NAME := "simulation_unit_optics"
const LIVE_SOURCE_NAME := "live_physical_matter"


var sim: Node3D
var camera: Camera3D
var _world: Node
var _checks := 0
var _failures := 0
var _gate_counts: Dictionary = {}
var _gate_failures: Dictionary = {}
var _receipt: Dictionary = {"checks": []}
var _physical_init_started := false
# Every particle/field-state readback the arm makes goes through
# _read_particle_state(), which records it here and increments the counter only
# when it happens after physical initialization.
var _per_particle_readbacks_after_physical_init := 0
var _particle_readback_trace: Array[Dictionary] = []
var _raw_capture_count_after_physical_init := 0


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT))
	_receipt = {
		"schema": "cassi-physical-matter-production-acceptance-v1",
		"preregistration": PREREGISTRATION,
		"verdict_vocabulary": ["PASS", "FAIL", "NULL", "ADOPT", "REJECT"],
		"frozen_constants": _frozen_constants(),
		"frozen_before_qualifying_run": true,
		"device": {
			"video_adapter": RenderingServer.get_video_adapter_name(),
			"renderer": str(Engine.get_version_info().get("string", "")),
			"version": str(Engine.get_version_info()),
		},
		"model_identity": {
			"path": "not_observed",
			"expected_sha256": "not_observed",
			"observed_model_sha256": "not_observed",
			"observed_model_file_sha256": "not_observed",
			"observed_frequency_grid_sha256": "not_observed",
			"observed_atomic_bundle_sha256": "not_observed",
			"observed_unit_map_sha256": "not_observed",
		},
		"controls": {
			"fixed_seed": FIXED_SEED,
			"production_particle_count": PRODUCTION_PARTICLE_COUNT,
			"physical_matter_initialized": false,
			"per_particle_readbacks_after_physical_init": 0,
			"raw_capture_count_after_physical_init": 0,
		},
		"checks": [],
	}
	
	get_window().size = Vector2i(960, 540)
	_world = load("res://scenes/main.tscn").instantiate()
	if _world == null:
		_record_boot_failures("main scene could not be instantiated")
		_finish()
		return
	sim = _world.get_node_or_null("CassiSim") as Node3D
	camera = _world.get_node_or_null("Camera3D") as Camera3D
	if sim == null or camera == null:
		_record_boot_failures("main scene is missing CassiSim or Camera3D")
		_finish()
		return
	# These are pacing controls only. The production particle count and all
	# physical-matter exports remain the values supplied by main.tscn/script.
	sim.set("ic_seed", FIXED_SEED)
	sim.set("physical_matter_enabled", false)
	sim.set("observatory_style", 0)
	sim.set("max_steps_per_frame", 1)
	sim.set("sim_speed", 1.0)
	sim.set("physics_frame_budget", 0.0)
	sim.set("auto_frame_camera_on_start", false)
	camera.set_process(false)
	_world.tree_entered.connect(func() -> void: get_tree().current_scene = _world, CONNECT_ONE_SHOT)
	get_tree().root.add_child.call_deferred(_world)
	await _world.ready
	_receipt["model_identity"]["path"] = str(sim.get("physical_matter_model_path"))
	_receipt["model_identity"]["expected_sha256"] = str(sim.get("physical_matter_expected_sha256"))
	_receipt["controls"]["physical_exports"] = {
		"physical_matter_enabled_default": bool(sim.get("physical_matter_enabled")),
		"physical_matter_model_path": str(sim.get("physical_matter_model_path")),
		"physical_matter_expected_sha256": str(sim.get("physical_matter_expected_sha256")),
		"physical_matter_cadence_steps": int(sim.get("physical_matter_cadence_steps")),
		"physical_matter_grid": _vector3i_array(sim.get("physical_matter_grid")),
		"physical_matter_temperature_K": float(sim.get("physical_matter_temperature_K")),
		"physical_matter_reduced_light_fraction": float(sim.get("physical_matter_reduced_light_fraction")),
		"physical_matter_tracer_blend": float(sim.get("physical_matter_tracer_blend")),
	}
	_receipt["controls"]["scene_particle_count_before_boot"] = int(sim.get("N_particles"))
	
	var booted := await _wait_for_boot(45_000)
	_receipt["boot"] = {
		"ok": booted,
		"particle_count": int(sim.get("N_particles")),
		"shaders_ready": bool(sim.get("_shaders_ready")),
		"decoupled_active": bool(sim.get("_decoupled_active")),
		"gridless_failure": bool(sim.get("_gridless_failure")),
	}
	if not booted:
		_record_boot_failures("production scene did not complete its decoupled boot")
		_finish()
		return
	await _run_g0()
	await _run_production()
	_finish()


func _run_g0() -> void:
	var physics_owner: Object = sim.get("_physics_engine")
	var readiness: Dictionary = sim.call("get_physical_matter_readiness") as Dictionary
	var physical_engine_value: Variant = physics_owner.get("_physical_matter_engine") \
			if physics_owner != null else null
	var physical_resources: Dictionary = physics_owner.call("physical_matter_render_resources") \
			if physics_owner != null and physics_owner.has_method("physical_matter_render_resources") else {}
	var allocation_bytes := int(readiness.get("resource_bytes", 0))
	var no_allocations := not bool(readiness.get("enabled", true)) \
			and str(readiness.get("mode", "")) == "disabled" \
			and physical_engine_value == null \
			and physical_resources.is_empty() \
			and allocation_bytes == 0
	_receipt["g0_disabled_initialization"] = {
		"readiness": _publication_evidence(readiness),
		"physical_engine_present": physical_engine_value != null,
		"physical_resources_empty": physical_resources.is_empty(),
		"allocation_bytes": allocation_bytes,
	}
	_record_check("PM-G0", "initialization reports no physical-matter allocations", no_allocations,
			{"enabled": bool(readiness.get("enabled", true)), "mode": str(readiness.get("mode", "")),
			"engine_present": physical_engine_value != null, "resource_bytes": allocation_bytes},
			{"surface": "get_physical_matter_readiness + physical_matter_render_resources",
			"supported": true,
			"why_valid": "The disabled physics engine deliberately creates no physical-matter engine or borrowed RID set."})

	# Capture a fixed-seed, fixed-step digest while physical matter is still
	# disabled. This is the arm's only particle/field-state readback and it is
	# routed through _read_particle_state() so the PM-G9 post-init readback
	# counter observes the arm's real call trace.
	sim.set("playing", false)
	await _frames(2)
	var digest_start_step := int(sim.get("_step_count"))
	sim.set("playing", true)
	var digest_target := digest_start_step + G0_FIXED_STEPS
	var digest_deadline := Time.get_ticks_msec() + 30_000
	while Time.get_ticks_msec() < digest_deadline and int(sim.get("_step_count")) < digest_target:
		await get_tree().process_frame
	sim.set("playing", false)
	await RenderingServer.frame_post_draw
	var digest_value: Dictionary = _read_particle_state(&"field_state_digest_for_verify") as Dictionary
	var digest := str(digest_value.get("checksum", ""))
	if digest.is_empty():
		digest = "not_observed"
	var digest_steps := int(sim.get("_step_count")) - digest_start_step
	var digest_ok := bool(digest_value.get("ok", false)) and digest.length() == 64 \
			and digest_steps == G0_FIXED_STEPS
	_receipt["g0_solver_state"] = {
		"seed": FIXED_SEED,
		"start_step": digest_start_step,
		"end_step": int(sim.get("_step_count")),
		"steps_requested": G0_FIXED_STEPS,
		"steps_observed": digest_steps,
		"digest": digest,
		"digest_surface": "field_state_digest_for_verify",
		"parity_baseline": "battery_default_chain_only; no baseline constant invented",
	}
	_record_check("PM-G0", "fixed-seed solver-state digest is recorded for battery parity evidence (comparison remains battery-owned)", digest_ok,
			{"seed": FIXED_SEED, "start_step": digest_start_step, "end_step": int(sim.get("_step_count")),
			"steps_observed": digest_steps, "digest": digest},
			{"surface": "field_state_digest_for_verify", "supported": true,
			"why_valid": "The helper hashes the live particle position and velocity buffers in the decoupled production branch, and the complete inline field-plus-particle state in the legacy branch; the battery supplies the pre-feature parity comparison."})

	# Existing presentation modes are exercised with their unchanged source.
	sim.call("set_observatory_source", 0)
	var mode_records: Array[Dictionary] = []
	var modes_ok := true
	for style in range(3):
		sim.call("set_observatory_style", style)
		await _frames(8)
		var stats: Dictionary = sim.call("get_observatory_statistics") as Dictionary
		var active_expected := style > 0
		var mode_ok := int(stats.get("style", -1)) == style \
				and str(stats.get("source_name", "")) == LEGACY_SOURCE_NAME \
				and bool(stats.get("active", false)) == active_expected \
				and (not active_expected or bool(stats.get("source_ready", false)))
		modes_ok = modes_ok and mode_ok
		mode_records.append({
			"mode_name": MODE_NAMES[style],
			"style": style,
			"active": bool(stats.get("active", false)),
			"source_name": str(stats.get("source_name", "")),
			"source_ready": bool(stats.get("source_ready", false)),
			"publication": stats.get("publication", {}) if stats.get("publication", {}) is Dictionary else {},
			"volume": _volume_evidence(stats.get("volume", {})),
		})
	_receipt["g0_publications"] = mode_records
	_record_check("PM-G0", "Scientific, Observatory, and Cinematic publications retain mode names and source contracts", modes_ok,
			{"modes": mode_records, "expected_source": LEGACY_SOURCE_NAME},
			{"surface": "get_observatory_statistics", "supported": true,
			"why_valid": "The existing Observatory runtime publishes the mode/style and source name for all three presentation modes without enabling physical matter."})


func _run_production() -> void:
	var configured_count := int(sim.get("N_particles"))
	var count_ok := configured_count == PRODUCTION_PARTICLE_COUNT
	_receipt["controls"]["particle_count_asserted"] = configured_count
	_record_check("PM-G9", "configured production particle count is exactly 2,500,000", count_ok,
			{"observed_particle_count": configured_count, "required_particle_count": PRODUCTION_PARTICLE_COUNT},
			{"surface": "live CassiSim.N_particles export", "supported": true,
			"why_valid": "The arm reads the live node after main-scene boot and does not replace the scene's particle configuration."})
	if not count_ok:
		_record_production_unavailable("live production particle count differs from the preregistered setup")
		return

	# Enable only through the scene's exported physical-matter switch and the
	# normal reinit path. Keep the renderer paused while the second 2.5M
	# decoupled engine replaces the default engine; this lets worker setup and
	# resource destruction settle without accumulating render/compute lists.
	sim.call("set_observatory_style", 0)
	sim.call("set_observatory_source", 0)
	sim.set("physical_matter_enabled", true)
	_physical_init_started = true
	sim.set("playing", false)
	sim.call("reinit")
	var physical_ready := await _wait_for_physical_ready(75_000)
	sim.set("playing", true)
	_receipt["controls"]["physical_matter_initialized"] = physical_ready
	var initial_readiness: Dictionary = sim.call("get_physical_matter_readiness") as Dictionary
	_update_model_identity(initial_readiness)
	if physical_ready:
		sim.call("set_observatory_source", 2)
		sim.call("set_observatory_style", 1)
	var initial_stats: Dictionary = sim.call("get_observatory_statistics") as Dictionary
	var source_active := false
	var source_deadline := Time.get_ticks_msec() + 15_000
	while physical_ready and Time.get_ticks_msec() < source_deadline:
		source_active = bool(initial_stats.get("active", false)) \
				and str(initial_stats.get("source_name", "")) == LIVE_SOURCE_NAME \
				and bool(initial_stats.get("source_ready", false))
		if source_active:
			break
		await _frames(2)
		initial_stats = sim.call("get_observatory_statistics") as Dictionary
	source_active = physical_ready and bool(initial_stats.get("active", false)) \
			and str(initial_stats.get("source_name", "")) == LIVE_SOURCE_NAME \
			and bool(initial_stats.get("source_ready", false))
	_receipt["physical_boot"] = {
		"ready": physical_ready,
		"readiness": _publication_evidence(initial_readiness),
		"source_active": source_active,
		"statistics": {
			"source_name": str(initial_stats.get("source_name", "")),
			"source_ready": bool(initial_stats.get("source_ready", false)),
			"volume": _volume_evidence(initial_stats.get("volume", {})),
		},
	}
	if not physical_ready or not source_active:
		_record_production_unavailable("physical matter or its live observation source did not initialize")
		return

	# Pacing is frozen before the qualifying measurement window. One requested
	# parent step per frame avoids building a long global-RD command list at the
	# 2.5M production scale while preserving the physical cadence contract
	# (one accepted update per 8 parent steps).
	sim.set("max_steps_per_frame", 1)
	sim.set("sim_speed", 1.0)
	sim.call("set_observatory_setting", "adaptive_quality", false)
	sim.call("set_observatory_setting", "quality", 0)
	_receipt["controls"]["qualifying_pacing"] = {
		"max_steps_per_frame": int(sim.get("max_steps_per_frame")),
		"sim_speed": float(sim.get("sim_speed")),
		"physics_frame_budget": float(sim.get("physics_frame_budget")),
		"observatory_quality": 0,
		"adaptive_quality": false,
	}
	await _frames(16)
	var measurement := await _measure_production_window()
	_receipt["g10_measurement"] = measurement.get("receipt", {})
	var last_readiness: Dictionary = measurement.get("last_readiness", {}) as Dictionary
	var last_stats: Dictionary = measurement.get("last_stats", {}) as Dictionary
	_update_model_identity(last_readiness)

	# Capture the live source while paused so the observation test is not mixed
	# with a physical update. The raw texture readback is explicitly permitted
	# by PM-G9 and is not a per-particle readback.
	sim.set("playing", false)
	_apply_orbit(0, 360, measurement.get("orbit_target", Vector3.ZERO), float(measurement.get("orbit_radius", 10.0)))
	await _frames(4)
	var event_pose := camera.global_transform
	var observation_before := _capture_xyz()
	var pause_probe := await _pause_independence_probe(measurement)
	var observation_event := await _controlled_heating_observation(observation_before, event_pose)
	_receipt["observation"] = observation_event.get("receipt", {})
	_receipt["controls"]["per_particle_readbacks_after_physical_init"] = _per_particle_readbacks_after_physical_init
	_receipt["controls"]["raw_capture_count_after_physical_init"] = _raw_capture_count_after_physical_init

	var health: Dictionary = measurement.get("health", {}) as Dictionary
	var accepted_delta := int(measurement.get("accepted_delta", 0))
	var g9_steps_ok := accepted_delta >= REQUIRED_PHYSICAL_STEPS \
			and int(health.get("fatal_status_samples", 1)) == 0 \
			and int(health.get("runtime_health_failures", 1)) == 0 \
			and int(health.get("nonfinite_or_positivity_samples", 1)) == 0
	_record_check("PM-G9", "at least 256 physical substeps complete without runtime, shader, device-loss, nonfinite-state, or positivity errors", g9_steps_ok,
			{"accepted_steps_start": int(measurement.get("accepted_start", 0)),
			"accepted_steps_end": int(measurement.get("accepted_end", 0)),
			"accepted_steps_completed": accepted_delta,
			"fatal_status_samples": int(health.get("fatal_status_samples", 0)),
			"nonfinite_or_positivity_samples": int(health.get("nonfinite_or_positivity_samples", 0)),
			"runtime_health_failures": int(health.get("runtime_health_failures", 0)),
			"last_error": str(last_readiness.get("error", ""))},
			{"surface": "published status_values + readiness + fail-closed decoupled/RD/shader state", "supported": true,
			"runtime_error_buffer": "not exposed to this GDScript arm",
			"alternative": "fatal status flags, readiness errors, _gridless_failure, _shaders_ready, _decoupled_active, and RenderingDevice validity are sampled every post-fence frame; this is fail-closed for the production path.",
			"why_valid": "The physical engine rejects nonfinite/negative states transactionally and the renderer stops on shader/device failure; no successful accepted sample can hide those flags."})

	var fence_ok := int(measurement.get("fence_violations", 1)) == 0 \
			and int(measurement.get("fence_samples", 0)) >= G10_MIN_CADENCE_SAMPLES \
			and accepted_delta >= REQUIRED_PHYSICAL_STEPS
	_record_check("PM-G9", "physical time and accepted-step counters advance only after the renderer fence", fence_ok,
			{"fence_samples": int(measurement.get("fence_samples", 0)),
			"fence_violations": int(measurement.get("fence_violations", 0)),
			"accepted_delta": accepted_delta,
			"cadence_samples": measurement.get("cadence_samples", []),
			"accepted_time_samples": measurement.get("physical_time_samples", [])},
			{"surface": "post-RenderingServer.frame_post_draw publication samples + has_pending_publication", "supported": true,
			"pre_fence_hook": "not exposed to this arm",
			"alternative": "Every counter sample is taken only after frame_post_draw and must have no pending publication, state_epoch=accepted_steps+1, and physical_time_sim=accepted_steps*dt*cadence.",
			"why_valid": "The production integration commits physical matter only after RenderingServer.frame_post_draw, then publishes the accepted counters and state."})

	var publication_ok := _publication_acceptance_ok(last_readiness)
	_record_check("PM-G9", "source publication reports identities, conservation ledgers, state epochs, and measured update/readback times", publication_ok,
			{"publication": _publication_evidence(last_readiness), "last_stats": _volume_evidence(last_stats.get("volume", {}))},
			{"surface": "get_physical_matter_readiness / physical_matter_publication", "supported": true,
			"why_valid": "The source publication exposes immutable identities, ledger RIDs, epochs, status telemetry, and command/fence/GPU timings without copying particle state."})

	var before_metrics: Dictionary = observation_before.get("metrics", {}) as Dictionary
	var event_receipt: Dictionary = observation_event.get("receipt", {}) as Dictionary
	var after_metrics: Dictionary = event_receipt.get("after", {}) as Dictionary
	var event_changed := bool(observation_event.get("changed", false))
	var event_control_supported := bool(event_receipt.get("control", {}).get("supported", false)) \
			and bool(event_receipt.get("control", {}).get("accepted", false))
	var observation_metrics_ok := bool(before_metrics.get("ok", false)) \
			and int(before_metrics.get("finite_pixels", 0)) > 0 \
			and int(before_metrics.get("nonblack_pixels", 0)) > 0 \
			and float(before_metrics.get("unit_scale_J_m3_per_sim", 0.0)) > 0.0 \
			and bool(after_metrics.get("ok", false)) \
			and int(after_metrics.get("finite_pixels", 0)) > 0 \
			and int(after_metrics.get("nonblack_pixels", 0)) > 0 \
			and float(after_metrics.get("unit_scale_J_m3_per_sim", 0.0)) > 0.0 \
			and event_changed
	var observation_ok := observation_metrics_ok and event_control_supported
	_record_check("PM-G9", "physical observation produces finite nonblack XYZ pixels from live state and changes after the selected controlled heating event", observation_ok,
			{"before": before_metrics, "after": after_metrics, "byte_changed": event_changed,
			"observation_metrics_ok": observation_metrics_ok,
			"event_control_supported": event_control_supported,
			"event_control": event_receipt.get("control", {})},
			{"surface": "capture_observation_raw_xyz + request_physical_matter_heating + fenced completion",
			"qualification_choice": "heating_alternative",
			"alternative": "controlled compression is permitted by PM-G9 but not selected for this qualifying run",
			"supported": true,
			"why_valid": "The preregistered PM-G9 rule accepts either a controlled compression or heating event; this run selects the implemented live GPU thermal impulse, waits for the shared-render-list publication fence, and captures the same camera pose before and after the accepted event. No reinitialization or init-time temperature mutation is used."})

	var telemetry_bound := bool(measurement.get("telemetry_bounded", false))
	var readback_ok := _physical_init_started \
			and _per_particle_readbacks_after_physical_init == 0 \
			and telemetry_bound
	_record_check("PM-G9", "no CPU per-particle readback occurs after initialization; recurring readback is bounded to telemetry, checkpoints on request, and captured images", readback_ok,
			{"per_particle_readbacks_after_physical_init": _per_particle_readbacks_after_physical_init,
			"particle_readback_trace": _particle_readback_trace,
			"telemetry_publication_counter": int(measurement.get("telemetry_publication_counter", 0)),
			"telemetry_last_readback_counter": int(measurement.get("telemetry_last_readback_counter", 0)),
			"telemetry_cadence": int(measurement.get("telemetry_cadence", 0)),
			"raw_captures": _raw_capture_count_after_physical_init,
			"checkpoints_requested": 0},
			{"surface": "arm call trace + bounded CassiSim publication counters", "supported": true,
			"alternative": "Every particle/field-state read is routed through _read_particle_state(); the arm's only such read is the pre-init PM-G0 digest, and no field_state_digest_for_verify, solver buffer readback, checkpoint, or per-particle accessor is called after physical initialization. Only status telemetry and raw image textures are sampled.",
			"why_valid": "The global-RD production publication carries telemetry only, while captured XYZ textures are explicitly allowed by the preregistration."})

	var independence_ok := bool(pause_probe.get("ok", false))
	_record_check("PM-G9", "particle motion, camera motion, display cadence, and capture cadence cannot advance the physical solver independently", independence_ok,
			pause_probe.get("metrics", {}) as Dictionary,
			{"surface": "paused live sim with camera orbit, rendered frames, and raw XYZ capture", "supported": true,
			"why_valid": "The accepted-step, parent-step, and physical-time counters remain fixed while the renderer and capture surfaces continue to operate."})

	var g10_ok := _g10_acceptance_ok(measurement, last_readiness, last_stats)
	_record_check("PM-G10", "production-scale performance and degradation remain within the frozen interactive criterion", g10_ok,
			measurement.get("g10_metrics", {}) as Dictionary,
			{"surface": "post-fence GPU timestamp, frame interval, publication allocation bytes, cadence, and source identity", "supported": true,
			"gpu_timing_scope": "complete_decoupled_compute_list (the supported timestamp boundary; includes physical work and renderer list)",
			"renderer_timing_scope": "wall interval from SceneTree.process_frame through RenderingServer.frame_post_draw",
			"allocation_scope": "physical publication resource_bytes + physical-volume estimated_total_bytes",
			"physical_term_surface": "published radiation_substeps and hydro_substeps (>0 on every accepted update)",
			"physical_term_limitation": "No per-pipeline dispatch counter is exposed; zero substeps are fail-closed, while positive published substeps are the supported production term schedule.",
			"why_valid": "The available boundaries measure the actual production work conservatively; thresholds were frozen before the qualifying window and are not adapted afterward."})


func _measure_production_window() -> Dictionary:
	var start_readiness: Dictionary = sim.call("get_physical_matter_readiness") as Dictionary
	var accepted_start := int(start_readiness.get("accepted_steps", 0))
	var target := accepted_start + REQUIRED_PHYSICAL_STEPS
	var accepted_last := accepted_start
	var last_parent_step := int(sim.get("_step_count"))
	var last_physical_time := float(start_readiness.get("physical_time_sim", 0.0))
	var dropped_steps_start := int(sim.get("_dropped_steps"))
	var frame_ms_samples: Array = []
	var observatory_frame_ms_samples: Array = []
	var gpu_samples: Array = []
	var physical_alloc_samples: Array = []
	var renderer_alloc_samples: Array = []
	var cadence_samples: Array = []
	var physical_time_samples: Array = []
	var status_flags_samples: Array = []
	var fence_samples := 0
	var fence_violations := 0
	var physical_term_violations := 0
	var identity_violations := 0
	var fatal_status_samples := 0
	var nonfinite_or_positivity_samples := 0
	var runtime_health_failures := 0
	var gpu_missing_samples := 0
	var orbit_target: Vector3 = sim.call("get_presentation_camera_target")
	var extents: Vector3 = sim.call("_extents")
	var orbit_radius := maxf(extents.length() * 1.25, 10.0)
	var orbit_displacement := 0.0
	var first_camera_position := camera.global_position
	var previous_usec := Time.get_ticks_usec()
	var started_usec := previous_usec
	var frame_index := 0
	var deadline := Time.get_ticks_msec() + G10_MAX_RUN_MS
	var last_readiness := start_readiness
	var last_stats: Dictionary = sim.call("get_observatory_statistics") as Dictionary
	while (accepted_last < target or frame_index < G10_MIN_RENDERER_SAMPLES) \
			and Time.get_ticks_msec() < deadline:
		_apply_orbit(frame_index, 360, orbit_target, orbit_radius)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var now_usec := Time.get_ticks_usec()
		var frame_ms := float(now_usec - previous_usec) / 1000.0
		previous_usec = now_usec
		if is_finite(frame_ms) and frame_ms > 0.0:
			frame_ms_samples.append(frame_ms)
		last_readiness = sim.call("get_physical_matter_readiness") as Dictionary
		last_stats = sim.call("get_observatory_statistics") as Dictionary
		var observatory_frame_ms := float(last_stats.get("frame_ms_ema", -1.0))
		if is_finite(observatory_frame_ms) and observatory_frame_ms > 0.0:
			observatory_frame_ms_samples.append(observatory_frame_ms)
		var accepted_now := int(last_readiness.get("accepted_steps", -1))
		if accepted_now > accepted_last:
			var accepted_increment := accepted_now - accepted_last
			var parent_step := int(sim.get("_step_count"))
			var parent_gap := parent_step - last_parent_step
			if accepted_increment == 1:
				cadence_samples.append(parent_gap)
				physical_time_samples.append(float(last_readiness.get("physical_time_sim", 0.0)) - last_physical_time)
			else:
				for _sample in range(accepted_increment):
					cadence_samples.append(float(parent_gap) / float(accepted_increment))
					physical_time_samples.append((float(last_readiness.get("physical_time_sim", 0.0)) - last_physical_time) / float(accepted_increment))
			var gpu_us := float(last_readiness.get("production_compute_gpu_us", -1.0))
			if is_finite(gpu_us) and gpu_us >= 0.0:
				gpu_samples.append(gpu_us)
			else:
				gpu_missing_samples += accepted_increment
			var physical_bytes := int(last_readiness.get("resource_bytes", 0))
			if physical_bytes >= 0:
				physical_alloc_samples.append(physical_bytes)
			var volume: Dictionary = last_stats.get("volume", {}) as Dictionary
			var renderer_bytes := int(volume.get("estimated_total_bytes", 0))
			if renderer_bytes >= 0:
				renderer_alloc_samples.append(renderer_bytes)
			var status: Dictionary = last_readiness.get("status_values", {}) as Dictionary
			var flags := int(status.get("flags", 0))
			status_flags_samples.append(flags)
			if not ArmMetrics.status_keys_present(status):
				fatal_status_samples += accepted_increment
			if ArmMetrics.status_is_fatal(flags):
				fatal_status_samples += accepted_increment
			if int(status.get("nonfinite_inputs", 0)) > 0 \
					or int(status.get("initial_out_of_domain", 0)) > 0 \
					or int(status.get("kinetics_failures", 0)) > 0 \
					or int(status.get("moving_frame_rejections", 0)) > 0 \
					or int(status.get("transport_nonfinite", 0)) > 0 \
					or int(status.get("transport_negative", 0)) > 0 \
					or flags & 16 != 0 or flags & 32 != 0:
				nonfinite_or_positivity_samples += accepted_increment
			var pending := _physical_publication_pending()
			var expected_epoch := accepted_now + 1
			var physical_time := float(last_readiness.get("physical_time_sim", -1.0))
			var expected_time := float(accepted_now) * float(sim.get("dt")) * float(sim.get("physical_matter_cadence_steps"))
			var epoch_ok := int(last_readiness.get("state_epoch", -1)) == expected_epoch
			var time_ok := is_equal_approx(physical_time, expected_time)
			fence_samples += accepted_increment
			if pending or not epoch_ok or not time_ok:
				fence_violations += accepted_increment
			var identity_ok := int(last_readiness.get("groups", 0)) == G10_EXPECTED_GROUPS \
					and int(last_readiness.get("angles", 0)) == G10_EXPECTED_ANGLES \
					and str(last_readiness.get("source_kind", "")) == "conditional_hydrogen_plasma" \
					and str(volume.get("source_kind", "")) == "live_conditional_hydrogen_plasma" \
					and str(last_stats.get("source_name", "")) == LIVE_SOURCE_NAME
			var physical_terms_ok := int(last_readiness.get("radiation_substeps", 0)) > 0 \
					and int(last_readiness.get("hydro_substeps", 0)) > 0
			if not physical_terms_ok:
				physical_term_violations += accepted_increment
			if not identity_ok:
				identity_violations += accepted_increment
			accepted_last = accepted_now
			last_parent_step = parent_step
			last_physical_time = physical_time
		var runtime_ok := not bool(sim.get("_gridless_failure")) \
				and bool(sim.get("_shaders_ready")) \
				and bool(sim.get("_decoupled_active")) \
				and sim.get("_rd") != null \
				and bool(last_readiness.get("ready", false)) \
				and str(last_readiness.get("error", "")).is_empty()
		if not runtime_ok:
			runtime_health_failures += 1
		orbit_displacement = maxf(orbit_displacement, camera.global_position.distance_to(first_camera_position))
		frame_index += 1
	var elapsed_ms := float(Time.get_ticks_usec() - started_usec) / 1000.0
	var accepted_delta := accepted_last - accepted_start
	var dropped_steps := maxi(int(sim.get("_dropped_steps")) - dropped_steps_start, 0)
	var pub_counter := int(sim.get("_pub_counter"))
	var last_readback_counter := int(sim.get("_last_readback_pub_counter"))
	var telemetry_cadence := maxi(int(sim.get("mirror_publish_cadence")), 1)
	var telemetry_bounded := pub_counter >= 0 and last_readback_counter >= 0 \
			and last_readback_counter <= pub_counter \
			and (last_readback_counter == 0 or last_readback_counter == 1 \
			or last_readback_counter % telemetry_cadence == 0)
	var g10_metrics := {
		"window": {
			"accepted_steps_start": accepted_start,
			"accepted_steps_end": accepted_last,
			"accepted_steps_completed": accepted_delta,
			"frames": frame_index,
			"elapsed_ms": elapsed_ms,
			"deadline_ms": G10_MAX_RUN_MS,
			"camera_orbit_target": _vector3_array(orbit_target),
			"camera_orbit_radius": orbit_radius,
			"camera_orbit_displacement": orbit_displacement,
			"camera_orbit_observed": orbit_displacement > 0.1,
		},
		"gpu_physical_update_us": _distribution(gpu_samples),
		"renderer_frame_ms": _distribution(frame_ms_samples),
		"observatory_frame_ms_ema": _distribution(observatory_frame_ms_samples),
		"physical_allocation_bytes": _distribution(physical_alloc_samples),
		"renderer_allocation_bytes": _distribution(renderer_alloc_samples),
		"physical_cadence_steps": _distribution(cadence_samples),
		"physical_time_per_update_sim": _distribution(physical_time_samples),
		"gpu_missing_samples": gpu_missing_samples,
		"status_flags": _distribution(status_flags_samples),
		"status_fatal_samples": fatal_status_samples,
		"fence_samples": fence_samples,
		"fence_violations": fence_violations,
		"physical_term_violations": physical_term_violations,
		"identity_violations": identity_violations,
		"dropped_steps": dropped_steps,
		"runtime_health_failures": runtime_health_failures,
	}
	return {
		"accepted_start": accepted_start,
		"accepted_end": accepted_last,
		"accepted_delta": accepted_delta,
		"last_readiness": last_readiness,
		"last_stats": last_stats,
		"orbit_target": orbit_target,
		"orbit_radius": orbit_radius,
		"cadence_samples": cadence_samples,
		"physical_time_samples": physical_time_samples,
		"fence_samples": fence_samples,
		"fence_violations": fence_violations,
		"health": {
			"fatal_status_samples": fatal_status_samples,
			"nonfinite_or_positivity_samples": nonfinite_or_positivity_samples,
			"runtime_health_failures": runtime_health_failures,
		},
		"telemetry_publication_counter": pub_counter,
		"telemetry_last_readback_counter": last_readback_counter,
		"telemetry_cadence": telemetry_cadence,
		"telemetry_bounded": telemetry_bounded,
		"g10_metrics": g10_metrics,
		"receipt": {
			"accepted_start": accepted_start,
			"accepted_end": accepted_last,
			"accepted_delta": accepted_delta,
			"frames": frame_index,
			"elapsed_ms": elapsed_ms,
			"camera_orbit": g10_metrics.window,
			"gpu_physical_update_us": g10_metrics.gpu_physical_update_us,
			"renderer_frame_ms": g10_metrics.renderer_frame_ms,
			"observatory_frame_ms_ema": g10_metrics.observatory_frame_ms_ema,
			"physical_allocation_bytes": g10_metrics.physical_allocation_bytes,
			"renderer_allocation_bytes": g10_metrics.renderer_allocation_bytes,
			"physical_cadence_steps": g10_metrics.physical_cadence_steps,
			"physical_time_per_update_sim": g10_metrics.physical_time_per_update_sim,
			"gpu_missing_samples": gpu_missing_samples,
			"status_fatal_samples": fatal_status_samples,
			"fence_samples": fence_samples,
			"fence_violations": fence_violations,
			"physical_term_violations": physical_term_violations,
			"identity_violations": identity_violations,
			"dropped_steps": dropped_steps,
			"runtime_health_failures": runtime_health_failures,
			"telemetry_bounded": telemetry_bounded,
		},
	}


func _pause_independence_probe(measurement: Dictionary) -> Dictionary:
	var accepted_before := int(sim.call("get_physical_matter_readiness").get("accepted_steps", -1))
	var step_before := int(sim.get("_step_count"))
	var time_before := float(sim.call("get_physical_matter_readiness").get("physical_time_sim", -1.0))
	var stats_before: Dictionary = sim.call("get_observatory_statistics") as Dictionary
	var dispatch_before := int((stats_before.get("volume", {}) as Dictionary).get("dispatch_count", 0))
	var start_pose := camera.global_transform
	for index in range(12):
		_apply_orbit(index + 61, 360, measurement.get("orbit_target", Vector3.ZERO), float(measurement.get("orbit_radius", 10.0)))
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
	var stats_after: Dictionary = sim.call("get_observatory_statistics") as Dictionary
	var accepted_after_readiness: Dictionary = sim.call("get_physical_matter_readiness") as Dictionary
	var accepted_after := int(accepted_after_readiness.get("accepted_steps", -1))
	var step_after := int(sim.get("_step_count"))
	var time_after := float(accepted_after_readiness.get("physical_time_sim", -1.0))
	var dispatch_after := int((stats_after.get("volume", {}) as Dictionary).get("dispatch_count", 0))
	var capture := _capture_xyz()
	var accepted_after_capture := int((sim.call("get_physical_matter_readiness") as Dictionary).get("accepted_steps", -1))
	var camera_moved := camera.global_transform.origin.distance_to(start_pose.origin) > 0.1
	var display_advanced := dispatch_after > dispatch_before
	var capture_ok := bool((capture.get("metrics", {}) as Dictionary).get("ok", false))
	var ok := not bool(sim.get("playing")) \
			and camera_moved \
			and display_advanced \
			and capture_ok \
			and accepted_after == accepted_before \
			and accepted_after_capture == accepted_before \
			and step_after == step_before \
			and is_equal_approx(time_after, time_before)
	return {
		"ok": ok,
		"metrics": {
			"playing": bool(sim.get("playing")),
			"accepted_before": accepted_before,
			"accepted_after_camera_display": accepted_after,
			"accepted_after_capture": accepted_after_capture,
			"step_before": step_before,
			"step_after": step_after,
			"physical_time_before": time_before,
			"physical_time_after": time_after,
			"camera_moved": camera_moved,
			"display_dispatch_before": dispatch_before,
			"display_dispatch_after": dispatch_after,
			"display_advanced": display_advanced,
			"capture": capture.get("metrics", {}),
		},
	}


func _controlled_heating_observation(before: Dictionary, event_pose: Transform3D) -> Dictionary:
	var old_temperature := float(sim.get("physical_matter_temperature_K"))
	var delta_temperature_K := maxf(old_temperature * 0.25, 1000.0)
	var request: Dictionary = sim.call(
			"request_physical_matter_heating", delta_temperature_K) as Dictionary
	var control := {
		"kind": "heating",
		"qualification_choice": "heating_alternative",
		"alternative": "controlled compression permitted by PM-G9 but not selected",
		"supported": bool(request.get("ok", false)),
		"accepted": false,
		"attempted": true,
		"parameter": "delta_temperature_K",
		"before_temperature_K": old_temperature,
		"delta_temperature_K": delta_temperature_K,
		"request": request,
		"mechanism": "live GPU thermal-energy impulse followed by shared-list publication fence",
	}
	var completion: Dictionary = {}
	if bool(request.get("ok", false)):
		var event_id := int(request.get("event_id", -1))
		completion = await _wait_for_control_event(event_id, 30_000)
		control["accepted"] = bool(completion.get("ok", false)) \
				and str(completion.get("status", "")) == "accepted"
		control["completion"] = completion
	var after := {"metrics": {"ok": false, "finite_pixels": 0, "nonblack_pixels": 0,
		"width": 0, "height": 0, "bytes": 0, "max_xyz": 0.0, "digest": ""}}
	if bool(control.get("accepted", false)):
		sim.call("set_observatory_source", 2)
		sim.call("set_observatory_style", 1)
		camera.global_transform = event_pose
		await _frames(12)
		after = _capture_xyz()
	var before_bytes_hash := str((before.get("metrics", {}) as Dictionary).get("digest", ""))
	var after_bytes_hash := str((after.get("metrics", {}) as Dictionary).get("digest", ""))
	var changed := bool((before.get("metrics", {}) as Dictionary).get("ok", false)) \
			and bool((after.get("metrics", {}) as Dictionary).get("ok", false)) \
			and before_bytes_hash != after_bytes_hash
	return {
		"changed": changed,
		"receipt": {
			"control": control,
			"before": before.get("metrics", {}),
			"after": after.get("metrics", {}),
			"byte_changed": changed,
		},
	}


func _capture_xyz() -> Dictionary:
	var raw: Dictionary = sim.call("capture_observation_raw_xyz") as Dictionary
	var bytes_value: Variant = raw.get("bytes", PackedByteArray())
	var bytes := PackedByteArray()
	if bytes_value is PackedByteArray:
		bytes = bytes_value
	var size := Vector2i(raw.get("size", Vector2i.ZERO))
	var metrics := ArmMetrics.raw_xyz_metrics(bytes, size)
	metrics["ok"] = bool(raw.get("ok", false)) and metrics.bytes == size.x * size.y * 16
	metrics["unit_scale_J_m3_per_sim"] = float(raw.get("unit_scale_J_m3_per_sim", 0.0))
	metrics["error"] = str(raw.get("error", ""))
	if _physical_init_started:
		_raw_capture_count_after_physical_init += 1
	return {"metrics": metrics, "bytes": bytes}


func _read_particle_state(surface: StringName) -> Variant:
	var reading: Variant = sim.call(surface)
	var after_physical_init := _physical_init_started
	_particle_readback_trace.append({
		"surface": String(surface),
		"after_physical_init": after_physical_init,
	})
	if after_physical_init:
		_per_particle_readbacks_after_physical_init += 1
	return reading


func _publication_acceptance_ok(readiness: Dictionary) -> bool:
	var required_sha_keys := ["model_sha256", "model_file_sha256", "frequency_grid_sha256", "atomic_bundle_sha256", "unit_map_sha256"]
	var identities_ok := str(readiness.get("source_kind", "")) == "conditional_hydrogen_plasma" \
			and not str(readiness.get("numerical_identity", "")).is_empty() \
			and str(readiness.get("model_sha256", "")) == str(sim.get("physical_matter_expected_sha256"))
	for key in required_sha_keys:
		identities_ok = identities_ok and str(readiness.get(key, "")).length() == 64
	var grid_value: Variant = readiness.get("grid", Vector3i.ZERO)
	var grid_ok := grid_value is Vector3i and (grid_value as Vector3i).x > 0 \
			and (grid_value as Vector3i).y > 0 and (grid_value as Vector3i).z > 0
	var status: Dictionary = readiness.get("status_values", {}) as Dictionary
	var resource_ids_ok := _rid_valid(readiness.get("material0", RID())) \
			and _rid_valid(readiness.get("material1", RID())) \
			and _rid_valid(readiness.get("population0", RID())) \
			and _rid_valid(readiness.get("population1", RID())) \
			and _rid_valid(readiness.get("radiation", RID())) \
			and _rid_valid(readiness.get("frequency", RID())) \
			and _rid_valid(readiness.get("ordinates", RID())) \
			and _rid_valid(readiness.get("opacity", RID())) \
			and _rid_valid(readiness.get("emission", RID()))
	var statuses_ok := ArmMetrics.status_keys_present(status) \
			and not ArmMetrics.status_is_fatal(int(status.get("flags", 0)))
	return bool(readiness.get("ready", false)) \
			and not bool(readiness.get("pending_initialization", true)) \
			and identities_ok \
			and grid_ok \
			and int(readiness.get("groups", 0)) == G10_EXPECTED_GROUPS \
			and int(readiness.get("angles", 0)) == G10_EXPECTED_ANGLES \
			and int(readiness.get("accepted_steps", 0)) >= REQUIRED_PHYSICAL_STEPS \
			and int(readiness.get("state_epoch", 0)) > 0 \
			and int(readiness.get("reset_epoch", 0)) > 0 \
			and is_finite(float(readiness.get("physical_time_sim", -1.0))) \
			and int(readiness.get("resource_bytes", 0)) > 0 \
			and int(readiness.get("last_command_record_us", -1)) >= 0 \
			and int(readiness.get("last_commit_fence_readback_us", -1)) >= 0 \
			and float(readiness.get("production_compute_gpu_us", -1.0)) >= 0.0 \
			and _rid_valid(readiness.get("ledger0", RID())) \
			and _rid_valid(readiness.get("ledger1", RID())) \
			and _rid_valid(readiness.get("ledger2", RID())) \
			and _rid_valid(readiness.get("status", RID())) \
			and resource_ids_ok \
			and statuses_ok


func _g10_acceptance_ok(measurement: Dictionary, readiness: Dictionary, stats: Dictionary) -> bool:
	var metrics: Dictionary = measurement.get("g10_metrics", {}) as Dictionary
	var gpu: Dictionary = metrics.get("gpu_physical_update_us", {}) as Dictionary
	var renderer: Dictionary = metrics.get("renderer_frame_ms", {}) as Dictionary
	var physical_alloc: Dictionary = metrics.get("physical_allocation_bytes", {}) as Dictionary
	var renderer_alloc: Dictionary = metrics.get("renderer_allocation_bytes", {}) as Dictionary
	var cadence: Dictionary = metrics.get("physical_cadence_steps", {}) as Dictionary
	var camera_orbit := bool(metrics.get("window", {}).get("camera_orbit_observed", false))
	var cadence_values: Array = measurement.get("cadence_samples", []) as Array
	var cadence_ok := cadence_values.size() >= G10_MIN_CADENCE_SAMPLES
	for value in cadence_values:
		cadence_ok = cadence_ok and is_equal_approx(float(value), float(G10_EXPECTED_CADENCE_STEPS))
	var source_ok := str(stats.get("source_name", "")) == LIVE_SOURCE_NAME \
			and str((stats.get("volume", {}) as Dictionary).get("source_kind", "")) == "live_conditional_hydrogen_plasma"
	var identity_stable := str(readiness.get("source_kind", "")) == "conditional_hydrogen_plasma"
	return camera_orbit \
			and int(metrics.get("identity_violations", 1)) == 0 \
			and int(metrics.get("dropped_steps", 1)) == 0 \
			and int(metrics.get("physical_term_violations", 1)) == 0 \
			and int(measurement.get("accepted_delta", 0)) >= REQUIRED_PHYSICAL_STEPS \
			and int(gpu.get("count", 0)) >= G10_MIN_GPU_SAMPLES \
			and float(gpu.get("p95", -1.0)) <= G10_MAX_GPU_UPDATE_P95_US \
			and int(renderer.get("count", 0)) >= G10_MIN_RENDERER_SAMPLES \
			and float(renderer.get("p95", -1.0)) <= G10_MAX_RENDERER_FRAME_P95_MS \
			and int(physical_alloc.get("count", 0)) >= G10_MIN_CADENCE_SAMPLES \
			and float(physical_alloc.get("p95", -1.0)) > 0.0 \
			and float(physical_alloc.get("p95", -1.0)) <= G10_MAX_PHYSICAL_ALLOCATION_BYTES \
			and int(renderer_alloc.get("count", 0)) >= G10_MIN_CADENCE_SAMPLES \
			and float(renderer_alloc.get("p95", -1.0)) > 0.0 \
			and float(renderer_alloc.get("p95", -1.0)) <= G10_MAX_RENDERER_ALLOCATION_BYTES \
			and cadence_ok \
			and float(cadence.get("p95", -1.0)) == float(G10_EXPECTED_CADENCE_STEPS) \
			and int(metrics.get("gpu_missing_samples", 1)) == 0 \
			and int(metrics.get("status_fatal_samples", 1)) == 0 \
			and int(metrics.get("fence_violations", 1)) == 0 \
			and int(metrics.get("runtime_health_failures", 1)) == 0 \
			and source_ok \
			and identity_stable


func _wait_for_boot(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
		if not bool(sim.get("_decoupled_boot_wait")) \
				and bool(sim.get("_shaders_ready")) \
				and bool(sim.get("_decoupled_active")) \
				and int(sim.get("_step_count")) >= 2:
			return true
	return false


func _wait_for_physical_ready(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
		var readiness: Dictionary = sim.call("get_physical_matter_readiness") as Dictionary
		if bool(readiness.get("ready", false)) \
				and bool(readiness.get("enabled", false)) \
				and bool(sim.get("_shaders_ready")) \
				and bool(sim.get("_decoupled_active")) \
				and not bool(sim.get("_gridless_failure")):
			return true
	return false


func _physical_publication_pending() -> bool:
	var owner: Object = sim.get("_physics_engine")
	if owner == null:
		return true
	var engine_value: Variant = owner.get("_physical_matter_engine")
	if engine_value == null or not (engine_value is RefCounted):
		return true
	return bool((engine_value as RefCounted).call("has_pending_publication"))


func _wait_for_control_event(event_id: int, timeout_ms: int) -> Dictionary:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
		var result: Dictionary = sim.call(
				"get_physical_matter_control_event", event_id) as Dictionary
		var status := str(result.get("status", ""))
		if status == "accepted" or status == "failed" or status == "cancelled" \
				or status == "rejected" or status == "unknown":
			return result
	return {"ok": false, "status": "timeout", "event_id": event_id,
		"error": "timed out waiting for physical matter heating publication"}


func _apply_orbit(index: int, total: int, target: Variant, radius: float) -> void:
	var center := Vector3(target)
	var theta := TAU * float(index % maxi(total, 1)) / float(maxi(total, 1))
	var elevation := 0.22 + 0.10 * sin(theta * 0.5)
	camera.global_position = center + Vector3(cos(theta) * radius, elevation * radius, sin(theta) * radius)
	camera.look_at(center, Vector3.UP)


func _frames(count: int = 3) -> void:
	for _index in count:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw


func _record_production_unavailable(reason: String) -> void:
	_receipt["production_unavailable"] = {"reason": reason}
	var metrics := {"reason": reason, "accepted_steps": 0}
	for label in [
			"at least 256 physical substeps complete without runtime, shader, device-loss, nonfinite-state, or positivity errors",
			"physical time and accepted-step counters advance only after the renderer fence",
			"source publication reports identities, conservation ledgers, state epochs, and measured update/readback times",
			"physical observation produces finite nonblack XYZ pixels from live state and changes after a controlled compression or heating event",
			"no CPU per-particle readback occurs after initialization; recurring readback is bounded to telemetry, checkpoints on request, and captured images",
			"particle motion, camera motion, display cadence, and capture cadence cannot advance the physical solver independently",
	]:
		_record_check("PM-G9", label, false, metrics, {"surface": "production boot", "supported": false, "reason": reason})
	_record_check("PM-G10", "production-scale performance and degradation remain within the frozen interactive criterion", false, metrics,
			{"surface": "production boot", "supported": false, "reason": reason})


func _record_boot_failures(reason: String) -> void:
	for label in [
			"initialization reports no physical-matter allocations",
			"fixed-seed solver-state digest is recorded for battery parity evidence (comparison remains battery-owned)",
			"Scientific, Observatory, and Cinematic publications retain mode names and source contracts",
	]:
		_record_check("PM-G0", label, false, {"reason": reason}, {"surface": "main scene boot", "supported": false, "reason": reason})
	_record_production_unavailable(reason)


func _record_check(gate: String, label: String, passed: bool, metrics: Dictionary, control: Dictionary) -> void:
	_checks += 1
	_gate_counts[gate] = int(_gate_counts.get(gate, 0)) + 1
	if not passed:
		_failures += 1
		_gate_failures[gate] = int(_gate_failures.get(gate, 0)) + 1
	var row := {
		"gate": gate,
		"name": label,
		"passed": passed,
		"metrics": metrics.duplicate(true),
		"control": control.duplicate(true),
	}
	(_receipt["checks"] as Array).append(row)
	print("[%s] %s: %s" % ["PASS" if passed else "FAIL", gate, label])


func _finish() -> void:
	_receipt["checks_total"] = _checks
	_receipt["checks_failed"] = _failures
	_receipt["gate_counts"] = _gate_counts.duplicate(true)
	_receipt["gate_failures"] = _gate_failures.duplicate(true)
	_receipt["controls"]["per_particle_readbacks_after_physical_init"] = _per_particle_readbacks_after_physical_init
	_receipt["controls"]["raw_capture_count_after_physical_init"] = _raw_capture_count_after_physical_init
	var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
	if file == null:
		_receipt["receipt_write_error"] = "could not open " + RECEIPT_PATH
		_failures += 1
	else:
		_receipt["verdict"] = "PASS" if _failures == 0 else "FAIL"
		_receipt["checks_failed"] = _failures
		file.store_string(JSON.stringify(_receipt, "\t") + "\n")
		file.close()
	for gate in ["PM-G0", "PM-G9", "PM-G10"]:
		print("%s RESULT: %d/%d checks passed" % [gate,
			int(_gate_counts.get(gate, 0)) - int(_gate_failures.get(gate, 0)),
			int(_gate_counts.get(gate, 0))])
	var verdict := "PASS" if _failures == 0 else "FAIL"
	_receipt["verdict"] = verdict
	print("PHYSICAL MATTER PRODUCTION RESULT: %s (%d/%d checks passed)" % [
		verdict, _checks - _failures, _checks])
	if sim != null:
		sim.set("playing", false)
	get_tree().quit(0 if _failures == 0 else 1)


func _frozen_constants() -> Dictionary:
	return {
		"production_particle_count": PRODUCTION_PARTICLE_COUNT,
		"required_physical_steps": REQUIRED_PHYSICAL_STEPS,
		"g0_fixed_steps": G0_FIXED_STEPS,
		"max_gpu_update_p95_us": G10_MAX_GPU_UPDATE_P95_US,
		"max_renderer_frame_p95_ms": G10_MAX_RENDERER_FRAME_P95_MS,
		"max_physical_allocation_bytes": G10_MAX_PHYSICAL_ALLOCATION_BYTES,
		"max_renderer_allocation_bytes": G10_MAX_RENDERER_ALLOCATION_BYTES,
		"expected_physical_cadence_steps": G10_EXPECTED_CADENCE_STEPS,
		"expected_frequency_groups": G10_EXPECTED_GROUPS,
		"expected_ordinate_angles": G10_EXPECTED_ANGLES,
		"minimum_gpu_samples": G10_MIN_GPU_SAMPLES,
		"minimum_renderer_samples": G10_MIN_RENDERER_SAMPLES,
		"minimum_cadence_samples": G10_MIN_CADENCE_SAMPLES,
		"maximum_run_ms": G10_MAX_RUN_MS,
		"justification": {
			"max_gpu_update_p95_us": "100 ms is the frozen conservative upper bound for the supported complete decoupled compute-list GPU boundary; it does not understate physical work.",
			"max_renderer_frame_p95_ms": "100 ms is a frozen 10 Hz interactive-camera ceiling measured at the real rendered-frame fence.",
			"max_physical_allocation_bytes": "Matches the physical engine's hard 1.5 GiB MAX_RESOURCE_BYTES bound.",
			"max_renderer_allocation_bytes": "512 MiB bounds the observer's independently accounted textures and source/observer resources while leaving headroom below the engine limit.",
			"expected_physical_cadence_steps": "The main physical-matter export and engine cadence contract are 8 parent steps per accepted physical update; every measured gap must remain exact.",
			"required_physical_steps": "The PM-G9 preregistration minimum and the G10 qualifying measurement window are both 256 accepted physical steps.",
		},
	}


func _update_model_identity(publication: Dictionary) -> void:
	var identity: Dictionary = _receipt["model_identity"] as Dictionary
	for pair in [
		["observed_model_sha256", "model_sha256"],
		["observed_model_file_sha256", "model_file_sha256"],
		["observed_frequency_grid_sha256", "frequency_grid_sha256"],
		["observed_atomic_bundle_sha256", "atomic_bundle_sha256"],
		["observed_unit_map_sha256", "unit_map_sha256"],
	]:
		var observed := str(publication.get(pair[1], ""))
		if not observed.is_empty():
			identity[pair[0]] = observed


func _publication_evidence(publication: Dictionary) -> Dictionary:
	var grid_value: Variant = publication.get("grid", Vector3i.ZERO)
	var grid := _vector3i_array(grid_value)
	var status_value: Variant = publication.get("status_values", {})
	var status: Dictionary = status_value.duplicate(true) if status_value is Dictionary else {}
	return {
		"ready": bool(publication.get("ready", false)),
		"pending_initialization": bool(publication.get("pending_initialization", false)),
		"enabled": bool(publication.get("enabled", false)),
		"mode": str(publication.get("mode", "")),
		"source_kind": str(publication.get("source_kind", "")),
		"numerical_identity": str(publication.get("numerical_identity", "")),
		"model_sha256": str(publication.get("model_sha256", "")),
		"model_file_sha256": str(publication.get("model_file_sha256", "")),
		"frequency_grid_sha256": str(publication.get("frequency_grid_sha256", "")),
		"atomic_bundle_sha256": str(publication.get("atomic_bundle_sha256", "")),
		"unit_map_sha256": str(publication.get("unit_map_sha256", "")),
		"grid": grid,
		"groups": int(publication.get("groups", 0)),
		"angles": int(publication.get("angles", 0)),
		"accepted_steps": int(publication.get("accepted_steps", 0)),
		"state_epoch": int(publication.get("state_epoch", 0)),
		"reset_epoch": int(publication.get("reset_epoch", 0)),
		"physical_time_sim": float(publication.get("physical_time_sim", 0.0)),
		"resource_bytes": int(publication.get("resource_bytes", 0)),
		"radiation_substeps": int(publication.get("radiation_substeps", 0)),
		"hydro_substeps": int(publication.get("hydro_substeps", 0)),
		"last_command_record_us": int(publication.get("last_command_record_us", -1)),
		"last_commit_fence_readback_us": int(publication.get("last_commit_fence_readback_us", -1)),
		"production_compute_gpu_us": float(publication.get("production_compute_gpu_us", -1.0)),
		"last_error": str(publication.get("error", "")),
		"production_compute_scope": str(publication.get("production_compute_scope", "")),
		"ledger0_valid": _rid_valid(publication.get("ledger0", RID())),
		"ledger1_valid": _rid_valid(publication.get("ledger1", RID())),
		"ledger2_valid": _rid_valid(publication.get("ledger2", RID())),
		"status_valid": _rid_valid(publication.get("status", RID())),
		"material0_valid": _rid_valid(publication.get("material0", RID())),
		"material1_valid": _rid_valid(publication.get("material1", RID())),
		"population0_valid": _rid_valid(publication.get("population0", RID())),
		"population1_valid": _rid_valid(publication.get("population1", RID())),
		"radiation_valid": _rid_valid(publication.get("radiation", RID())),
		"status_values": status,
	}


func _volume_evidence(value: Variant) -> Dictionary:
	if not value is Dictionary:
		return {"initialized": false, "valid": false, "source_kind": "", "estimated_total_bytes": 0,
			"dispatch_count": 0, "raw_capture_count": 0, "last_command_record_us": -1,
			"last_gpu_render_us": -1, "render_size": [0, 0]}
	var volume := value as Dictionary
	var render_size: Array = [0, 0]
	var size_value: Variant = volume.get("render_size", Vector2i.ZERO)
	if size_value is Vector2i:
		render_size = _vector2i_array(size_value)
	return {
		"initialized": bool(volume.get("initialized", false)),
		"valid": bool(volume.get("valid", false)),
		"source_kind": str(volume.get("source_kind", "")),
		"coupling": str(volume.get("coupling", "")),
		"composition_kind": str(volume.get("composition_kind", "")),
		"model_sha256": str(volume.get("model_sha256", "")),
		"frequency_grid_sha256": str(volume.get("frequency_grid_sha256", "")),
		"dispatch_count": int(volume.get("dispatch_count", 0)),
		"scattering_source_dispatch_count": int(volume.get("scattering_source_dispatch_count", 0)),
		"raw_capture_count": int(volume.get("raw_capture_count", 0)),
		"allocation_count": int(volume.get("allocation_count", 0)),
		"observer_bytes": int(volume.get("observer_bytes", 0)),
		"source_bytes": int(volume.get("source_bytes", 0)),
		"image_bytes": int(volume.get("image_bytes", 0)),
		"estimated_total_bytes": int(volume.get("estimated_total_bytes", 0)),
		"last_command_record_us": int(volume.get("last_command_record_us", -1)),
		"last_gpu_render_us": int(volume.get("last_gpu_render_us", -1)),
		"render_size": render_size,
		"visible_groups": int(volume.get("visible_groups", 0)),
	}


func _distribution(values: Array) -> Dictionary:
	var sorted: Array[float] = []
	for value in values:
		var number := float(value)
		if is_finite(number):
			sorted.append(number)
	sorted.sort()
	if sorted.is_empty():
		return {"count": 0, "median": -1.0, "p95": -1.0, "min": -1.0, "max": -1.0}
	var median: float
	if sorted.size() % 2 == 0:
		median = (sorted[sorted.size() / 2 - 1] + sorted[sorted.size() / 2]) * 0.5
	else:
		median = sorted[sorted.size() / 2]
	var p95_index := clampi(int(ceil(float(sorted.size()) * 0.95)) - 1, 0, sorted.size() - 1)
	return {"count": sorted.size(), "median": median, "p95": sorted[p95_index],
		"min": sorted[0], "max": sorted[sorted.size() - 1]}


func _rid_valid(value: Variant) -> bool:
	return value is RID and (value as RID).is_valid()


func _vector3_array(value: Variant) -> Array:
	if value is Vector3:
		var vector := value as Vector3
		return [vector.x, vector.y, vector.z]
	return [0.0, 0.0, 0.0]


func _vector3i_array(value: Variant) -> Array:
	if value is Vector3i:
		var vector := value as Vector3i
		return [vector.x, vector.y, vector.z]
	return [0, 0, 0]


func _vector2i_array(value: Variant) -> Array:
	if value is Vector2i:
		var vector := value as Vector2i
		return [vector.x, vector.y]
	return [0, 0]


func _exit_tree() -> void:
	if sim != null:
		sim.set("playing", false)
