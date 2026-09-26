extends RefCounted
## Meshless render-topology worker.
## The renderer owns a global RenderingDevice whose meshless rebuild dispatch
## chain is a measured raster-blackout trigger on the RX 7900 XTX. This worker
## keeps that chain off the renderer: it creates a LOCAL RenderingDevice on its
## own thread, builds the finite open-tile Voronoi labels and adjacency/CSR,
## then publishes one coherent geometry result for the main thread.
##
## Only render topology is staged here. The global engine remains authoritative
## for the live two-fluid cell state and particle physics; the worker never
## writes the global device and never runs on a global command list.


const TOPOLOGY_SHADER_PATH := "res://compute/cassi_voronoi_render_topology.glsl"
const ADJ_SHADER_PATH := "res://compute/cassi_voronoi_render_adjacency.glsl"
const CSR_SHADER_PATH := "res://compute/cassi_voronoi_adjacency_csr.glsl"


var _thread: Thread = null
var _thread_started := false
var _running := false
var _setup_sem: Semaphore
var _job_sem: Semaphore
var _done_sem: Semaphore
var _setup_mutex: Mutex
var _job_mutex: Mutex
var _res_mutex: Mutex
var _setup_complete := false
var _ready := false
var _wait_next := true

var _job: Dictionary = {}
var _job_pending := false
var _res_result: Dictionary = {}
var _res_generation := 0
var _consumed_generation := 0

var _grid_n := 64
var _site_count := 0
var _neighbor_capacity := 1
var _words_per_site := 1
var _extents := Vector3.ONE

var _rd: RenderingDevice = null
var _topology_shader: RID
var _topology_pipe: RID
var _adj_shader: RID
var _adj_pipe: RID
var _csr_shader: RID
var _csr_pipe: RID

var _sites: RID
var _labels_a: RID
var _labels_b: RID
var _open_labels: RID
var _adjacency: RID
var _degree: RID
var _offsets: RID
var _neighbors: RID
var _status: RID

var _us_topology: RID
var _us_adjacency: RID
var _us_csr: RID


func is_ready() -> bool:
	if _setup_mutex == null:
		return false
	_setup_mutex.lock()
	var ready := _setup_complete and _ready
	_setup_mutex.unlock()
	return ready


## MAIN thread. Shader resources are loaded here because RDShaderFile loading
## is not thread-safe. The local device and all worker resources are created
## by _thread_main on the worker thread.
func start(grid_n: int, site_count: int, neighbor_capacity: int, extents: Vector3) -> bool:
	stop()
	_grid_n = maxi(grid_n, 1)
	_site_count = maxi(site_count, 1)
	_neighbor_capacity = maxi(neighbor_capacity, 1)
	_words_per_site = maxi(int(ceil(float(_site_count) / 32.0)), 1)
	_extents = extents
	var spirv := {}
	for path in [TOPOLOGY_SHADER_PATH, ADJ_SHADER_PATH, CSR_SHADER_PATH]:
		var sf := load(path) as RDShaderFile
		if sf == null or sf.get_spirv() == null:
			push_error("[MeshlessTopologyWorker] shader load failed: " + path)
			return false
		spirv[path] = sf.get_spirv()
	_setup_sem = Semaphore.new()
	_job_sem = Semaphore.new()
	_done_sem = Semaphore.new()
	_setup_mutex = Mutex.new()
	_job_mutex = Mutex.new()
	_res_mutex = Mutex.new()
	_setup_complete = false
	_ready = false
	_wait_next = true
	_job = {}
	_job_pending = false
	_res_result = {}
	_res_generation = 0
	_consumed_generation = 0
	_running = true
	_thread = Thread.new()
	_thread_started = _thread.start(_thread_main.bind(spirv)) == OK
	if not _thread_started:
		_running = false
		push_warning("[MeshlessTopologyWorker] thread spawn failed")
		return false
	return true


## MAIN thread. Submit is deliberately non-blocking: topology is a render
## payload, not a prerequisite for particle physics. A job may be queued while
## the worker builds its local RD resources; the worker cannot consume the
## semaphore until setup has completed. This prevents a fast render loop from
## repeatedly readback-staging a job that an almost-ready worker would reject.
func submit(job: Dictionary) -> bool:
	if not _thread_started or _setup_mutex == null:
		return false
	_setup_mutex.lock()
	var setup_failed := _setup_complete and not _ready
	_setup_mutex.unlock()
	if setup_failed:
		return false
	_wait_next = false
	_enqueue(job)
	return true

func poll() -> Dictionary:
	return _consume_latest()


func stop() -> void:
	if _thread != null and _thread_started:
		_running = false
		_job_sem.post()
		_thread.wait_to_finish()
	_thread_started = false
	_thread = null
	_ready = false
	_setup_complete = false
	_job_pending = false
	_rd = null


func _enqueue(job: Dictionary) -> void:
	_job_mutex.lock()
	var was_pending := _job_pending
	_job = job
	_job_pending = true
	_job_mutex.unlock()
	if not was_pending:
		_job_sem.post()


func _consume_latest() -> Dictionary:
	_res_mutex.lock()
	var generation := _res_generation
	var result := _res_result
	_res_mutex.unlock()
	if generation > _consumed_generation and not result.is_empty():
		_consumed_generation = generation
		return result
	return {}


func _thread_main(spirv: Dictionary) -> void:
	_setup(spirv)
	_setup_sem.post()
	while true:
		_job_sem.wait()
		if not _running:
			break
		_job_mutex.lock()
		var job := _job
		_job_pending = false
		_job_mutex.unlock()
		_run_job(job)
		_done_sem.post()
	_free_resources()


func _setup(spirv: Dictionary) -> void:
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		push_error("[MeshlessTopologyWorker] local RenderingDevice creation failed")
		return
	var cells := _grid_n * _grid_n * _grid_n
	_sites = _rd.storage_buffer_create(_site_count * 16)
	_labels_a = _rd.storage_buffer_create(cells * 4)
	_labels_b = _rd.storage_buffer_create(cells * 4)
	_open_labels = _rd.storage_buffer_create(cells * 4)
	_adjacency = _rd.storage_buffer_create(_site_count * _words_per_site * 4)
	_degree = _rd.storage_buffer_create(_site_count * 4)
	_offsets = _rd.storage_buffer_create((_site_count + 1) * 4)
	_neighbors = _rd.storage_buffer_create(_neighbor_capacity * 4)
	_status = _rd.storage_buffer_create(16)

	_topology_shader = _shader_create(TOPOLOGY_SHADER_PATH, spirv)
	_adj_shader = _shader_create(ADJ_SHADER_PATH, spirv)
	_csr_shader = _shader_create(CSR_SHADER_PATH, spirv)
	if _topology_shader.is_valid(): _topology_pipe = _rd.compute_pipeline_create(_topology_shader)
	if _adj_shader.is_valid(): _adj_pipe = _rd.compute_pipeline_create(_adj_shader)
	if _csr_shader.is_valid(): _csr_pipe = _rd.compute_pipeline_create(_csr_shader)

	if _topology_shader.is_valid():
		_us_topology = _rd.uniform_set_create([
			_storage(0, _sites), _storage(1, _labels_a), _storage(2, _labels_b),
			_storage(3, _open_labels),
		], _topology_shader, 0)
	if _adj_shader.is_valid():
		_us_adjacency = _rd.uniform_set_create([
			_storage(0, _open_labels), _storage(1, _adjacency),
		], _adj_shader, 0)
	if _csr_shader.is_valid():
		_us_csr = _rd.uniform_set_create([
			_storage(0, _adjacency), _storage(1, _offsets), _storage(2, _degree),
			_storage(3, _neighbors), _storage(4, _status),
		], _csr_shader, 0)
	var setup_ready := _topology_pipe.is_valid() and _adj_pipe.is_valid() \
			and _csr_pipe.is_valid() and _us_topology.is_valid() \
			and _us_adjacency.is_valid() and _us_csr.is_valid()
	_setup_mutex.lock()
	_ready = setup_ready
	_setup_complete = true
	_setup_mutex.unlock()
	if setup_ready:
		print("[MeshlessTopologyWorker] ready: grid=%d^3 sites=%d neighbors=%d" % [_grid_n, _site_count, _neighbor_capacity])
	else:
		push_error("[MeshlessTopologyWorker] setup failed: local RD pipeline or uniform set is invalid")


func _shader_create(path: String, spirv: Dictionary) -> RID:
	var sp := spirv.get(path, null) as RDShaderSPIRV
	if sp == null:
		return RID()
	return _rd.shader_create_from_spirv(sp)


func _storage(binding: int, buffer: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buffer)
	return u


func _run_job(job: Dictionary) -> void:
	if not _ready:
		return
	var sites_value: Variant = job.get("sites", PackedFloat32Array())
	var ext_value: Variant = job.get("ext", _extents)
	if not sites_value is PackedFloat32Array or not ext_value is Vector3:
		push_error("[MeshlessTopologyWorker] job payload types invalid")
		return
	var sites: PackedFloat32Array = sites_value
	var ext: Vector3 = ext_value
	if sites.size() != _site_count * 4 or not ext.is_finite() \
			or ext.x <= 0.0 or ext.y <= 0.0 or ext.z <= 0.0:
		push_error("[MeshlessTopologyWorker] job payload size or extents invalid")
		return
	for value in sites:
		if not is_finite(value):
			push_error("[MeshlessTopologyWorker] job sites contain non-finite values")
			return
	_rd.buffer_update(_sites, 0, sites.size() * 4, sites.to_byte_array())

	var cells := _grid_n * _grid_n * _grid_n
	var cell_groups := maxi(int(ceil(float(cells) / 64.0)), 1)
	var site_groups := maxi(int(ceil(float(_site_count) / 64.0)), 1)
	var gen := int(job.get("generation", 1))
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _topology_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_topology, 0)
	var pc := PackedFloat32Array([
		float(_grid_n), float(_site_count), 0.0, 1.0, 0.0,
		ext.x, ext.y, ext.z,
	])
	_rd.compute_list_set_push_constant(cl, pc.to_byte_array(), pc.size() * 4)
	_rd.compute_list_dispatch(cl, cell_groups, 1, 1)
	_rd.compute_list_add_barrier(cl)
	pc[2] = 1.0
	_rd.compute_list_set_push_constant(cl, pc.to_byte_array(), pc.size() * 4)
	_rd.compute_list_dispatch(cl, site_groups, 1, 1)
	_rd.compute_list_add_barrier(cl)
	var read_a := 1.0
	var jump := 1
	while jump < _grid_n:
		jump *= 2
	jump /= 2
	while jump >= 1:
		pc[2] = 2.0
		pc[3] = read_a
		pc[4] = float(jump)
		_rd.compute_list_set_push_constant(cl, pc.to_byte_array(), pc.size() * 4)
		_rd.compute_list_dispatch(cl, cell_groups, 1, 1)
		_rd.compute_list_add_barrier(cl)
		read_a = 1.0 - read_a
		jump /= 2
	pc[2] = 3.0
	pc[3] = read_a
	pc[4] = 0.0
	_rd.compute_list_set_push_constant(cl, pc.to_byte_array(), pc.size() * 4)
	_rd.compute_list_dispatch(cl, cell_groups, 1, 1)
	_rd.compute_list_add_barrier(cl)

	_rd.compute_list_bind_compute_pipeline(cl, _adj_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_adjacency, 0)
	var adj_pc := PackedFloat32Array([float(_grid_n), float(_site_count), float(_words_per_site), 0.0])
	_rd.compute_list_set_push_constant(cl, adj_pc.to_byte_array(), adj_pc.size() * 4)
	_rd.compute_list_dispatch(cl, maxi(int(ceil(float(_site_count * _words_per_site) / 64.0)), 1), 1, 1)
	_rd.compute_list_add_barrier(cl)
	adj_pc[3] = 1.0
	_rd.compute_list_set_push_constant(cl, adj_pc.to_byte_array(), adj_pc.size() * 4)
	_rd.compute_list_dispatch(cl, cell_groups, 1, 1)
	_rd.compute_list_add_barrier(cl)

	_rd.compute_list_bind_compute_pipeline(cl, _csr_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_csr, 0)
	var csr_pc := PackedFloat32Array([
		float(_site_count), float(_words_per_site), 0.0, float(_neighbor_capacity),
		float(gen), 0.0, 0.0, 0.0,
	])
	_rd.compute_list_set_push_constant(cl, csr_pc.to_byte_array(), csr_pc.size() * 4)
	_rd.compute_list_dispatch(cl, site_groups, 1, 1)
	_rd.compute_list_add_barrier(cl)
	csr_pc[2] = 2.0
	_rd.compute_list_set_push_constant(cl, csr_pc.to_byte_array(), csr_pc.size() * 4)
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	csr_pc[2] = 1.0
	_rd.compute_list_set_push_constant(cl, csr_pc.to_byte_array(), csr_pc.size() * 4)
	_rd.compute_list_dispatch(cl, site_groups, 1, 1)
	_rd.compute_list_add_barrier(cl)
	_rd.compute_list_end()

	_rd.submit()
	_rd.sync()

	var status := _rd.buffer_get_data(_status, 0, 16)
	var result := {
		"generation": gen,
		"query_generation": int(job.get("query_generation", -1)),
		"status": status,
		"open_labels": _rd.buffer_get_data(_open_labels, 0, cells * 4),
		"adjacency": _rd.buffer_get_data(_adjacency, 0, _site_count * _words_per_site * 4),
		"degree": _rd.buffer_get_data(_degree, 0, _site_count * 4),
		"offsets": _rd.buffer_get_data(_offsets, 0, (_site_count + 1) * 4),
		"neighbors": _rd.buffer_get_data(_neighbors, 0, _neighbor_capacity * 4),
	}
	_res_mutex.lock()
	_res_result = result
	_res_generation += 1
	_res_mutex.unlock()


func _free_resources() -> void:
	if _rd == null:
		return
	# Uniform sets are intentionally left to device teardown: Godot 4.7's
	# worker-thread free_rid path rejects their main-thread bookkeeping.
	for rid in [
			_sites, _labels_a, _labels_b, _open_labels, _adjacency, _degree,
			_offsets, _neighbors, _status, _topology_pipe, _topology_shader,
			_adj_pipe, _adj_shader, _csr_pipe, _csr_shader]:
		if rid.is_valid():
			_rd.free_rid(rid)
	_rd.free()
	_rd = null
	_ready = false
