extends RefCounted
## Renderer-owned, read-only Observatory optical cache.
##
## The backend records one ordered compute list on the shared global
## RenderingDevice. It never submits or synchronizes that device and never
## reads a frame-sized resource back to the CPU. Source buffers in `frame` are
## borrowed; only fixed-point accumulators, cache images, pipelines and
## uniform sets are released by shutdown().

const DENSITY_CLEAR_PATH := "res://compute/cassi_observatory_density_clear.glsl"
const DENSITY_DEPOSIT_PATH := "res://compute/cassi_observatory_density_deposit.glsl"
const DENSITY_INLINE_PATH := "res://compute/cassi_observatory_density_inline.glsl"
const DENSITY_RECON_PATH := "res://compute/cassi_observatory_density_reconstruct.glsl"
const LIGHT_PATH := "res://compute/cassi_observatory_light.glsl"
const VOLUME_PATH := "res://compute/cassi_observatory_volume.glsl"
const MOTION_PATH := "res://compute/cassi_observatory_motion.glsl"
const MAX_GRID := 128
const MIN_GRID := 48
const TAU_SLICES := 64
const MAX_RENDER_EDGE := 4096
const FIXED_SCALE := 100000000.0

var _rd: RenderingDevice = null
var _ready := false
var _density_clear_shader := RID()
var _density_deposit_shader := RID()
var _density_inline_shader := RID()
var _density_recon_shader := RID()
var _light_shader := RID()
var _volume_shader := RID()
var _motion_shader := RID()
var _density_clear_pipe := RID()
var _density_deposit_pipe := RID()
var _density_inline_pipe := RID()
var _density_recon_pipe := RID()
var _light_pipe := RID()
var _volume_pipe := RID()
var _motion_pipe := RID()
var _dummy_source := RID()
var _particle_acc := RID()
var _field_acc := RID()
var _density_tex := RID()
var _light_state_tex := RID()
var _light_accum_tex := RID()
var _radiance_tex := RID()
var _depth_tex := RID()
var _tau_tex := RID()
var _motion_tex := RID()
var _volume_params := RID()
var _us_clear := RID()
var _us_deposit := RID()
var _us_inline := RID()
var _us_recon := RID()
var _us_light := RID()
var _us_volume := RID()
var _us_motion := RID()
var _bound_positions := RID()
var _bound_velocities := RID()
var _bound_sites := RID()
var _bound_field_ey := RID()
var _bound_field_ei := RID()
var _bound_inline_grid := 0
var _bound_grid := 0
var _bound_width := 0
var _bound_height := 0
var _bound_motion_width := 0
var _bound_particle_count := -1
var _bound_site_count := -1
var _grid := 0
var _width := 0
var _height := 0
var _motion_width := 0
var _motion_height := 0
var _last_source_epoch := -1
var _last_density_key: Array = []
var _last_site_epoch := -1
var _dispatch_count := 0
var _allocation_count := 0
var _last_valid_source := false
var _last_field_mode := false
var _last_error := ""
var _stats: Dictionary = {}
var _last_gpu_render_us := -1
var _pending_gpu_marker := ""
var _gpu_marker_id := 0
var _radiance: Texture2DRD = null
var _depth: Texture2DRD = null
var _optical_depth: Texture3DRD = null
var _motion: Texture2DRD = null

var radiance: Texture2DRD:
 get: return _radiance
var depth: Texture2DRD:
 get: return _depth
var optical_depth: Texture3DRD:
 get: return _optical_depth
var motion: Texture2DRD:
 get: return _motion

## Capture-only readback of the compositor input. Source zero has no calibrated
## XYZ target, so this linear-radiance image is its shape-authoritative surface.
func capture_shape_radiance() -> Dictionary:
 if _rd == null or not _radiance_tex.is_valid() or _width <= 0 or _height <= 0:
  return {"ok": false, "error": "simulation-optics radiance target is unavailable"}
 var bytes: PackedByteArray = _rd.texture_get_data(_radiance_tex, 0)
 if bytes.size() != _width * _height * 16:
  return {"ok": false, "error": "simulation-optics radiance byte count mismatch"}
 return {
  "ok": true,
  "bytes": bytes,
  "size": Vector2i(_width, _height),
  "format": "RGBA32F",
  "channels": ["R", "G", "B", "opacity"],
  "units": "linear simulation-unit radiance",
 }

func initialize(device: RenderingDevice) -> bool:
 if _ready: return true
 _rd = device
 if _rd == null:
  _last_error = "missing_rendering_device"
  return false
 _density_clear_shader = _load_shader(DENSITY_CLEAR_PATH)
 _density_deposit_shader = _load_shader(DENSITY_DEPOSIT_PATH)
 _density_inline_shader = _load_shader(DENSITY_INLINE_PATH)
 _density_recon_shader = _load_shader(DENSITY_RECON_PATH)
 _light_shader = _load_shader(LIGHT_PATH)
 _volume_shader = _load_shader(VOLUME_PATH)
 _motion_shader = _load_shader(MOTION_PATH)
 if not _density_clear_shader.is_valid() or not _density_deposit_shader.is_valid() \
   or not _density_inline_shader.is_valid() or not _density_recon_shader.is_valid() \
   or not _light_shader.is_valid() or not _volume_shader.is_valid() or not _motion_shader.is_valid():
  _last_error = "shader_load_failed"
  return false
 _density_clear_pipe = _rd.compute_pipeline_create(_density_clear_shader)
 _density_deposit_pipe = _rd.compute_pipeline_create(_density_deposit_shader)
 _density_inline_pipe = _rd.compute_pipeline_create(_density_inline_shader)
 _density_recon_pipe = _rd.compute_pipeline_create(_density_recon_shader)
 _light_pipe = _rd.compute_pipeline_create(_light_shader)
 _volume_pipe = _rd.compute_pipeline_create(_volume_shader)
 _motion_pipe = _rd.compute_pipeline_create(_motion_shader)
 if not _density_clear_pipe.is_valid() or not _density_deposit_pipe.is_valid() \
   or not _density_inline_pipe.is_valid() or not _density_recon_pipe.is_valid() \
   or not _light_pipe.is_valid() or not _volume_pipe.is_valid() or not _motion_pipe.is_valid():
  _last_error = "pipeline_create_failed"
  return false
 _dummy_source = _rd.storage_buffer_create(64)
 _volume_params = _rd.storage_buffer_create(32)
 _allocation_count += 2
 _ready = true
 _stats = {"initialized": true, "valid": false}
 return true

func update(frame: Dictionary, settings: Dictionary) -> bool:
 if not _ready or _rd == null: return false
 var field_mode := bool(frame.get("field_mode", false))
 var particle_count := maxi(0, int(frame.get("particle_count", 0)))
 var site_count := maxi(0, int(frame.get("site_count", 0)))
 var positions: RID = frame.get("positions", RID())
 var velocities: RID = frame.get("velocities", RID())
 var sites: RID = frame.get("optical_sites", RID())
 var field_ey: RID = frame.get("field_ey", RID())
 var field_ei: RID = frame.get("field_ei", RID())
 var field_grid := maxi(1, int(frame.get("field_grid_size", 1)))
 var inline_mode := field_mode and site_count <= 0 and field_ey.is_valid() and field_ei.is_valid()
 var site_mode := field_mode and not inline_mode
 var source_ok := (field_ey.is_valid() and field_ei.is_valid() and field_grid > 1) if inline_mode else ((sites.is_valid() and site_count > 0) if site_mode else (positions.is_valid() and particle_count > 0))
 var grid := _choose_grid(frame, settings)
 var out_size := _choose_render_size(frame, settings)
 if not _ensure_resources(grid, out_size.x, out_size.y, particle_count): return false
 var effective_positions := positions if positions.is_valid() else _dummy_source
 var effective_velocities := velocities if velocities.is_valid() else _dummy_source
 var effective_sites := sites if sites.is_valid() else _dummy_source
 var effective_particles := particle_count if positions.is_valid() else 0
 var effective_sites_count := site_count if sites.is_valid() else 0
 if not _ensure_uniform_sets(effective_positions, effective_velocities, effective_sites, effective_particles, effective_sites_count, field_ey if field_ey.is_valid() else _dummy_source, field_ei if field_ei.is_valid() else _dummy_source, field_grid, inline_mode): return false
 var bounds: AABB = frame.get("bounds", AABB(Vector3(-1.0, -1.0, -1.0), Vector3(2.0, 2.0, 2.0)))
 var bmin := bounds.position
 var bmax := bounds.position + bounds.size
 var span := bmax - bmin
 if span.x <= 0.0 or span.y <= 0.0 or span.z <= 0.0: return false
 var ref_mass := maxf(float(frame.get("reference_mass", 1.0)), 1.0e-9)
 var reference_radius := maxf(float(frame.get("reference_radius", 1.0)), 1.0e-6)
 var mass_scale := clampf(FIXED_SCALE / ref_mass, 1.0, 1.0e9)
 var cell_volume := maxf(span.x * span.y * span.z / float(grid * grid * grid), 1.0e-9)
 var field_scale := 1.0e6 / cell_volume
 var site_offset: Vector3 = frame.get("site_origin_offset", frame.get("field_origin_offset", Vector3.ZERO))
 var source_mode := 2.0 if inline_mode else (1.0 if field_mode else 0.0)
 var optical_thickness := maxf(float(settings.get("optical_thickness", 1.0)), 0.0)
 var scattering := clampf(float(settings.get("scattering", 0.35)), 0.0, 1.0)
 var emission := maxf(float(settings.get("emission", 1.0)), 0.0)
 var point_fraction := 0.0 if field_mode else clampf(float(settings.get("point_fraction", 0.65)), 0.0, 1.0)
 var density_key := [positions, sites, field_ey, field_ei, int(frame.get("source_epoch", 0)), int(frame.get("site_epoch", 0)), grid, field_grid, field_mode, inline_mode, bmin, bmax, site_offset, ref_mass, optical_thickness, emission, point_fraction, reference_radius, frame.get("field_extents", Vector3.ONE), frame.get("field_origin_offset", Vector3.ZERO)]
 var density_dirty := density_key != _last_density_key or bool(frame.get("playing", true))
 var volume_params := PackedFloat32Array([float(frame.get("reference_radius", 1.0)), float(frame.get("delta", 0.0)), source_mode, maxf(float(settings.get("shutter_seconds", 0.0)), 0.0), float(frame.get("source_epoch", 0)), float(frame.get("site_epoch", 0)), 1.0 if bool(frame.get("reset_history", false)) else 0.0, float(TAU_SLICES)])
 _rd.buffer_update(_volume_params, 0, 32, volume_params.to_byte_array())
 _resolve_gpu_render_timestamp()
 var gpu_marker := "observatory_volume_%d" % _gpu_marker_id
 var measure_gpu := _pending_gpu_marker.is_empty()
 if measure_gpu: _rd.capture_timestamp(gpu_marker + "/start")
 var cl := _rd.compute_list_begin()
 if density_dirty:
  _rd.compute_list_bind_compute_pipeline(cl, _density_clear_pipe)
  _rd.compute_list_bind_uniform_set(cl, _us_clear, 0)
  _rd.compute_list_set_push_constant(cl, _pc_grid(grid), 16)
  _rd.compute_list_dispatch(cl, ceili(float(grid) / 8.0), ceili(float(grid) / 8.0), ceili(float(grid) / 8.0))
  _rd.compute_list_add_barrier(cl)
  var deposit_pc := _pc_density(bmin, bmax, grid, mass_scale, effective_particles, effective_sites_count, source_mode, site_offset, field_scale, cell_volume)
  if inline_mode:
   _rd.compute_list_bind_compute_pipeline(cl, _density_inline_pipe)
   _rd.compute_list_bind_uniform_set(cl, _us_inline, 0)
   var inline_pc := _pc_inline(bmin, bmax, grid, field_grid, frame.get("field_extents", Vector3.ONE), frame.get("field_origin_offset", site_offset), field_scale, cell_volume)
   _rd.compute_list_set_push_constant(cl, inline_pc, inline_pc.size())
   _rd.compute_list_dispatch(cl, ceili(float(field_grid * field_grid * field_grid) / 256.0), 1, 1)
  else:
   _rd.compute_list_bind_compute_pipeline(cl, _density_deposit_pipe)
   _rd.compute_list_bind_uniform_set(cl, _us_deposit, 0)
   _rd.compute_list_set_push_constant(cl, deposit_pc, deposit_pc.size())
   var source_work := effective_sites_count if field_mode else effective_particles
   if source_work > 0: _rd.compute_list_dispatch(cl, ceili(float(source_work) / 256.0), 1, 1)
  _rd.compute_list_add_barrier(cl)
  _rd.compute_list_bind_compute_pipeline(cl, _density_recon_pipe)
  _rd.compute_list_bind_uniform_set(cl, _us_recon, 0)
  _rd.compute_list_set_push_constant(cl, deposit_pc, deposit_pc.size())
  _rd.compute_list_dispatch(cl, ceili(float(grid) / 8.0), ceili(float(grid) / 8.0), ceili(float(grid) / 8.0))
  _rd.compute_list_add_barrier(cl)
  var light_pc := PackedByteArray(); light_pc.resize(48)
  light_pc.encode_float(8, float(grid)); light_pc.encode_float(12, optical_thickness)
  light_pc.encode_float(20, ref_mass / maxf(reference_radius * reference_radius, 1.0e-6))
  light_pc.encode_float(24, emission); light_pc.encode_float(28, source_mode)
  light_pc.encode_float(32, point_fraction); light_pc.encode_float(36, reference_radius)
  _rd.compute_list_bind_compute_pipeline(cl, _light_pipe)
  _rd.compute_list_bind_uniform_set(cl, _us_light, 0)
  for direction in range(6):
   var cell_length: float = span[direction >> 1] / float(grid)
   light_pc.encode_float(0, float(direction)); light_pc.encode_float(16, cell_length)
   var positive := direction == 0 or direction == 2 or direction == 4
   var first := grid - 1 if positive else 0
   var last := -1 if positive else grid
   var step := -1 if positive else 1
   for layer in range(first, last, step):
    light_pc.encode_float(4, float(layer))
    _rd.compute_list_set_push_constant(cl, light_pc, 48)
    _rd.compute_list_dispatch(cl, ceili(float(grid) / 8.0), ceili(float(grid) / 8.0), 1)
    _rd.compute_list_add_barrier(cl)
 var cam: Transform3D = frame.get("camera_transform", Transform3D.IDENTITY)
 var viewport := Vector2i(out_size.x, out_size.y)
 var fov := deg_to_rad(maxf(float(frame.get("fov", 60.0)), 1.0))
 var steps := _quality_steps(int(settings.get("quality", 1)), grid)
 var volume_point_fraction := 0.0 if field_mode else clampf(float(settings.get("point_fraction", 0.65)), 0.0, 1.0)
 _rd.compute_list_bind_compute_pipeline(cl, _volume_pipe)
 _rd.compute_list_bind_uniform_set(cl, _us_volume, 0)
 var volume_pc := _pc_volume(cam, bmin, bmax, fov, viewport, float(frame.get("near", 0.01)), float(frame.get("far", 10000.0)), grid, steps, optical_thickness, maxf(float(settings.get("emission", 1.0)), 0.0), scattering, volume_point_fraction, ref_mass)
 _rd.compute_list_set_push_constant(cl, volume_pc, volume_pc.size())
 _rd.compute_list_dispatch(cl, ceili(float(out_size.x) / 8.0), ceili(float(out_size.y) / 8.0), 1)
 _rd.compute_list_add_barrier(cl)
 var motion_pc := PackedByteArray(); motion_pc.resize(16); motion_pc.encode_float(0, float(particle_count)); motion_pc.encode_float(4, float(_motion_width)); motion_pc.encode_float(8, float(_motion_height)); motion_pc.encode_float(12, 0.0)
 if bool(frame.get("playing", true)) or density_dirty:
  _rd.compute_list_bind_compute_pipeline(cl, _motion_pipe)
  _rd.compute_list_bind_uniform_set(cl, _us_motion, 0)
  _rd.compute_list_set_push_constant(cl, motion_pc, 16)
  if particle_count > 0: _rd.compute_list_dispatch(cl, ceili(float(particle_count) / 256.0), 1, 1)
 _rd.compute_list_end()
 if measure_gpu:
  _rd.capture_timestamp(gpu_marker + "/end")
  _pending_gpu_marker = gpu_marker
  _gpu_marker_id += 1
 _dispatch_count += 1
 _last_source_epoch = int(frame.get("source_epoch", 0)); _last_site_epoch = int(frame.get("site_epoch", 0)); _last_valid_source = source_ok; _last_field_mode = field_mode
 _last_density_key = density_key
 _stats = {"initialized": true, "valid": true, "valid_source": source_ok, "field_mode": field_mode, "source_kind": ("inline_field" if inline_mode else ("site_field" if field_mode else "particles")), "grid": grid, "grid_dimensions": Vector3i(grid, grid, grid), "render_size": Vector2i(out_size.x, out_size.y), "radiance_dimensions": Vector2i(_width, _height), "depth_dimensions": Vector2i(_width, _height), "optical_depth_dimensions": Vector3i(_width, _height, TAU_SLICES), "motion_dimensions": Vector2i(_motion_width, _motion_height), "tau_slices": TAU_SLICES, "dispatch_count": _dispatch_count, "allocation_count": _allocation_count, "particle_count": particle_count, "site_count": site_count, "field_grid_size": field_grid, "source_epoch": _last_source_epoch, "site_epoch": _last_site_epoch, "resources_valid": _resources_valid(), "resource_validity": {"particle_acc": _particle_acc.is_valid(), "field_acc": _field_acc.is_valid(), "density": _density_tex.is_valid(), "light": _light_accum_tex.is_valid(), "radiance": _radiance_tex.is_valid(), "depth": _depth_tex.is_valid(), "optical_depth": _tau_tex.is_valid(), "motion": _motion_tex.is_valid()}, "last_error": _last_error}
 _stats["last_gpu_render_us"] = _last_gpu_render_us
 return true

func shutdown() -> void:
 if _rd == null: return
 _ready = false
 _free_uniform_sets()
 for rid in [_particle_acc, _field_acc, _density_tex, _light_state_tex, _light_accum_tex, _radiance_tex, _depth_tex, _tau_tex, _motion_tex, _volume_params, _dummy_source]:
  if rid.is_valid() and _rd != null: _rd.free_rid(rid)
 _particle_acc = RID(); _field_acc = RID(); _density_tex = RID(); _light_state_tex = RID(); _light_accum_tex = RID(); _radiance_tex = RID(); _depth_tex = RID(); _tau_tex = RID(); _motion_tex = RID(); _volume_params = RID(); _dummy_source = RID()
 _radiance = null; _depth = null; _optical_depth = null; _motion = null
 for rid in [_density_clear_pipe, _density_deposit_pipe, _density_inline_pipe, _density_recon_pipe, _light_pipe, _volume_pipe, _motion_pipe, _density_clear_shader, _density_deposit_shader, _density_inline_shader, _density_recon_shader, _light_shader, _volume_shader, _motion_shader]:
  if rid.is_valid() and _rd != null: _rd.free_rid(rid)
 _ready = false; _rd = null; _stats = {"initialized": false, "valid": false, "resources_valid": false}
 _grid = 0; _width = 0; _height = 0; _bound_particle_count = -1
 _last_density_key = []

func statistics() -> Dictionary:
 _resolve_gpu_render_timestamp()
 _stats["last_gpu_render_us"] = _last_gpu_render_us
 return _stats.duplicate(true)

func _resolve_gpu_render_timestamp() -> void:
 if _pending_gpu_marker.is_empty() or _rd == null: return
 var start_ns := -1
 var end_ns := -1
 for index in range(_rd.get_captured_timestamps_count()):
  var name := _rd.get_captured_timestamp_name(index)
  if name == _pending_gpu_marker + "/start":
   start_ns = _rd.get_captured_timestamp_gpu_time(index)
  elif name == _pending_gpu_marker + "/end":
   end_ns = _rd.get_captured_timestamp_gpu_time(index)
 if start_ns >= 0 and end_ns >= start_ns:
  _last_gpu_render_us = int(end_ns - start_ns) / 1000
  _pending_gpu_marker = ""

func _load_shader(path: String) -> RID:
 var sf: RDShaderFile = load(path) as RDShaderFile
 if sf == null: return RID()
 var spirv: RDShaderSPIRV = sf.get_spirv()
 return _rd.shader_create_from_spirv(spirv)

func _choose_grid(frame: Dictionary, settings: Dictionary) -> int:
 var q := int(frame.get("grid_size", 0))
 if q <= 0: q = [48, 64, 96, 128][clampi(int(settings.get("quality", 1)), 0, 3)]
 var best := MIN_GRID
 for candidate in [48, 64, 96, 128]:
  if abs(candidate - q) < abs(best - q): best = candidate
 return clampi(best, MIN_GRID, MAX_GRID)

func _choose_render_size(frame: Dictionary, settings: Dictionary) -> Vector2i:
 var v: Vector2i = frame.get("render_size", Vector2i.ZERO)
 if v.x <= 0 or v.y <= 0: v = frame.get("viewport_size", Vector2i(1, 1))
 return Vector2i(clampi(v.x, 1, MAX_RENDER_EDGE), clampi(v.y, 1, MAX_RENDER_EDGE))

func _quality_steps(quality: int, grid: int) -> int:
 return [maxi(48, grid), maxi(72, grid), maxi(96, grid * 2), maxi(128, grid * 2)][clampi(quality, 0, 3)]

func _ensure_resources(grid: int, width: int, height: int, particle_count: int) -> bool:
 var changed := grid != _grid or width != _width or height != _height or particle_count != _bound_particle_count
 if not changed and _resources_valid(): return true
 _free_uniform_sets()
 _last_density_key = []
 if grid != _grid:
  for rid in [_particle_acc, _field_acc, _density_tex, _light_state_tex, _light_accum_tex]: _free_rid(rid)
  _particle_acc = _rd.storage_buffer_create(grid * grid * grid * 8)
  _field_acc = _rd.storage_buffer_create(grid * grid * grid * 64)
  _density_tex = _make_texture_3d(grid, grid, grid, RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
  _light_state_tex = _make_texture_3d(grid, grid, grid, RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
  _light_accum_tex = _make_texture_3d(grid, grid, grid, RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
  _allocation_count += 5
 if width != _width or height != _height:
  for rid in [_radiance_tex, _depth_tex, _tau_tex]: _free_rid(rid)
  _radiance_tex = _make_texture_2d(width, height, RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
  _depth_tex = _make_texture_2d(width, height, RenderingDevice.DATA_FORMAT_R32_SFLOAT)
  _tau_tex = _make_texture_3d(width, height, TAU_SLICES, RenderingDevice.DATA_FORMAT_R32_SFLOAT)
  _allocation_count += 3
  _radiance = _wrap_2d(_radiance_tex); _depth = _wrap_2d(_depth_tex); _optical_depth = _wrap_3d(_tau_tex)
 _motion_width = mini(4096, maxi(1, particle_count))
 _motion_height = maxi(1, ceili(float(maxi(1, particle_count)) / float(_motion_width)))
 if particle_count != _bound_particle_count:
  _free_rid(_motion_tex)
  _motion_tex = _make_texture_2d(_motion_width, _motion_height, RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
  _allocation_count += 1
  _motion = _wrap_2d(_motion_tex)
 _grid = grid; _width = width; _height = height; _bound_particle_count = particle_count
 return _resources_valid()

func _ensure_uniform_sets(positions: RID, velocities: RID, sites: RID, _particle_count: int, site_count: int, field_ey: RID, field_ei: RID, field_grid: int, _inline_mode: bool) -> bool:
 if _us_clear.is_valid() and positions == _bound_positions and velocities == _bound_velocities and sites == _bound_sites and field_ey == _bound_field_ey and field_ei == _bound_field_ei and field_grid == _bound_inline_grid and _bound_grid == _grid and _bound_width == _width and _bound_height == _height and _bound_motion_width == _motion_width and _bound_site_count == site_count: return true
 _free_uniform_sets()
 _us_clear = _rd.uniform_set_create([_storage(0, _particle_acc), _storage(1, _field_acc), _image(2, _density_tex), _image(3, _light_state_tex), _image(4, _light_accum_tex)], _density_clear_shader, 0)
 _us_deposit = _rd.uniform_set_create([_storage(0, positions), _storage(1, sites), _storage(2, _particle_acc), _storage(3, _field_acc)], _density_deposit_shader, 0)
 _us_inline = _rd.uniform_set_create([_storage(0, field_ey), _storage(1, field_ei), _storage(2, _field_acc)], _density_inline_shader, 0)
 _us_recon = _rd.uniform_set_create([_storage(0, _particle_acc), _storage(1, _field_acc), _image(2, _density_tex)], _density_recon_shader, 0)
 _us_light = _rd.uniform_set_create([_image(0, _density_tex), _image(1, _light_state_tex), _image(2, _light_accum_tex)], _light_shader, 0)
 _us_volume = _rd.uniform_set_create([_image(0, _density_tex), _image(1, _light_accum_tex), _image(2, _radiance_tex), _image(3, _depth_tex), _image(4, _tau_tex), _storage(5, _volume_params)], _volume_shader, 0)
 _us_motion = _rd.uniform_set_create([_storage(0, velocities), _storage(1, positions), _image(2, _motion_tex)], _motion_shader, 0)
 _bound_positions = positions; _bound_velocities = velocities; _bound_sites = sites; _bound_field_ey = field_ey; _bound_field_ei = field_ei; _bound_inline_grid = field_grid; _bound_grid = _grid; _bound_width = _width; _bound_height = _height; _bound_motion_width = _motion_width; _bound_site_count = site_count
 return _uniform_sets_valid()

func _free_uniform_sets() -> void:
 for rid in [_us_clear, _us_deposit, _us_inline, _us_recon, _us_light, _us_volume, _us_motion]: _free_rid(rid)
 _us_clear = RID(); _us_deposit = RID(); _us_inline = RID(); _us_recon = RID(); _us_light = RID(); _us_volume = RID(); _us_motion = RID()

func _free_rid(rid: RID) -> void:
 if rid.is_valid() and _rd != null: _rd.free_rid(rid)

func _resources_valid() -> bool:
 return _particle_acc.is_valid() and _field_acc.is_valid() and _density_tex.is_valid() and _radiance_tex.is_valid() and _depth_tex.is_valid() and _tau_tex.is_valid() and _motion_tex.is_valid()
func _uniform_sets_valid() -> bool:
 return _us_clear.is_valid() and _us_deposit.is_valid() and _us_inline.is_valid() and _us_recon.is_valid() and _us_light.is_valid() and _us_volume.is_valid() and _us_motion.is_valid()

func _storage(binding: int, rid: RID) -> RDUniform:
 var u := RDUniform.new(); u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER; u.binding = binding; u.add_id(rid); return u
func _image(binding: int, rid: RID) -> RDUniform:
 var u := RDUniform.new(); u.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE; u.binding = binding; u.add_id(rid); return u
func _make_texture_2d(width: int, height: int, format: RenderingDevice.DataFormat) -> RID:
 var f := RDTextureFormat.new(); f.width = width; f.height = height; f.format = format; f.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT | RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT | RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT; return _rd.texture_create(f, RDTextureView.new(), [])
func _make_texture_3d(width: int, height: int, depth: int, format: RenderingDevice.DataFormat) -> RID:
 var f := RDTextureFormat.new(); f.texture_type = RenderingDevice.TEXTURE_TYPE_3D; f.width = width; f.height = height; f.depth = depth; f.format = format; f.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT | RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT | RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT; return _rd.texture_create(f, RDTextureView.new(), [])
func _wrap_2d(rid: RID) -> Texture2DRD:
 var t := Texture2DRD.new(); t.texture_rd_rid = rid; return t
func _wrap_3d(rid: RID) -> Texture3DRD:
 var t := Texture3DRD.new(); t.texture_rd_rid = rid; return t

func _pc_grid(grid: int) -> PackedByteArray:
 var p := PackedByteArray(); p.resize(16); p.encode_float(0, float(grid)); return p
func _pc_density(bmin: Vector3, bmax: Vector3, grid: int, mass_scale: float, particle_count: int, site_count: int, source_mode: float, offset: Vector3, field_scale: float, cell_volume: float) -> PackedByteArray:
 var p := PackedByteArray(); p.resize(64); p.encode_float(0,bmin.x); p.encode_float(4,bmin.y); p.encode_float(8,bmin.z); p.encode_float(12,float(grid)); p.encode_float(16,bmax.x); p.encode_float(20,bmax.y); p.encode_float(24,bmax.z); p.encode_float(28,mass_scale); p.encode_float(32,float(particle_count)); p.encode_float(36,float(site_count)); p.encode_float(40,source_mode); p.encode_float(44,offset.x); p.encode_float(48,offset.y); p.encode_float(52,offset.z); p.encode_float(56,field_scale); p.encode_float(60,cell_volume); return p
func _pc_inline(bmin: Vector3, bmax: Vector3, grid: int, field_grid: int, extents: Vector3, origin: Vector3, field_scale: float, cell_volume: float) -> PackedByteArray:
 var p := PackedByteArray(); p.resize(64); p.encode_float(0,bmin.x); p.encode_float(4,bmin.y); p.encode_float(8,bmin.z); p.encode_float(12,float(grid)); p.encode_float(16,bmax.x); p.encode_float(20,bmax.y); p.encode_float(24,bmax.z); p.encode_float(28,float(field_grid)); p.encode_float(32,extents.x); p.encode_float(36,extents.y); p.encode_float(40,extents.z); p.encode_float(44,origin.x); p.encode_float(48,origin.y); p.encode_float(52,origin.z); p.encode_float(56,field_scale); p.encode_float(60,cell_volume); return p
func _pc_volume(cam: Transform3D, bmin: Vector3, bmax: Vector3, fov: float, size: Vector2i, near_clip: float, far_clip: float, grid: int, steps: int, thickness: float, emission: float, scattering: float, point_fraction: float, ref_mass: float) -> PackedByteArray:
 var p := PackedByteArray(); p.resize(128); var forward := -cam.basis.z.normalized(); var right := cam.basis.x.normalized(); var up := cam.basis.y.normalized(); var values := [cam.origin.x,cam.origin.y,cam.origin.z,fov,right.x,right.y,right.z,float(size.x),up.x,up.y,up.z,float(size.y),forward.x,forward.y,forward.z,near_clip,bmin.x,bmin.y,bmin.z,far_clip,bmax.x,bmax.y,bmax.z,float(grid),float(size.x),float(size.y),float(steps),thickness,emission,scattering,point_fraction,ref_mass]
 for i in values.size(): p.encode_float(i*4,float(values[i]))
 return p
