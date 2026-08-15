extends RefCounted
## Cassi tree-gravity worker — the first threaded slice of the physics
## decoupling. Owns a dedicated Thread + the tree-arm LOCAL RenderingDevice
## (created ON the worker thread — verified: a worker-thread-created local
## RD executes compute, while a main-thread-created one rejects
## compute_list_begin off the render thread on this build) and runs the
## meshless-tree build+walk (fmm_design.md Q6) OFF the main thread. The sim
## stages the frame's meshless source state (sites/ψ/ρ/pos global-RD
## readbacks — main-thread-only reads) and submits a job; the worker
## computes the per-particle gradient asynchronously and publishes the
## newest completed result; the sim picks it up via submit()'s return /
## poll() and uploads it to the global _ml_tree_grad. The main thread never
## waits for the tree GPU work after the bootstrap frame — the local-RD
## submit+sync+readback that used to stall every frame now runs off the
## critical path.
##
## Concurrency contract:
## - start(S, N3, Np): MAIN thread. Loads the two tree shaders (SPIR-V is
##   passed to the worker — resource loading is not thread-safe) and spawns
##   the worker thread, which creates the local RenderingDevice and all
##   tree resources on itself. The first submitted job is SYNCHRONOUS
##   (submit blocks on setup + completion) so the first physics step reads
##   a fresh gradient.
## - submit(job): MAIN thread. Non-blocking after the bootstrap. Coalesces:
##   a new job replaces an unconsumed pending one (newest state wins, the
##   same freshness semantics as the cadence skip).
## - poll(): MAIN thread, non-blocking. Returns the freshest UNCONSUMED
##   result as {"grad": PackedFloat32Array, "nc": int}, or {}.
## - stop(): MAIN thread. Joins the worker (which frees its own local RD
##   resources before exiting).
## - The worker thread touches ONLY: its local RD, the staged job slot
##   (_job_mutex), and the publish slot (_res_mutex). It never touches the
##   sim's global RD (illegal off the main thread).

const ML_TREE_LEAF_CAP := 1
const ML_TREE_MAX_LEVELS := 14
const ML_TREE_NODE_MAX_MULT := 8
const ML_TREE_FIELD_FLOOR := 1e-6   # source-mass recipe field-density floor
const ML_TREE_THETA := 0.5
const PHI: float = 1.618033988749895
const PHI_6: float = 17.94427191

var _thread: Thread
var _thread_started := false
var _running := false
var _job_sem: Semaphore
var _done_sem: Semaphore
var _setup_sem: Semaphore
var _job_mutex: Mutex
var _res_mutex: Mutex

# Local RenderingDevice + tree build/walk resources (created ON the worker
# thread in _setup(); worker-thread use only).
var _tlrd: RenderingDevice
var _tl_bld_sh: RID; var _tl_bld_pipe: RID
var _tl_grv_sh: RID; var _tl_grv_pipe: RID
var _tl_us_b: RID; var _tl_us_g: RID
var _tl_src: RID; var _tl_srcw: RID; var _tl_key: RID; var _tl_order: RID
var _tl_cf: RID; var _tl_nw: RID; var _tl_nq: RID; var _tl_nr: RID; var _tl_ctr: RID
var _tl_sites: RID; var _tl_psy: RID; var _tl_psi: RID; var _tl_vol: RID; var _tl_rho: RID
var _tl_tgrad: RID; var _tl_tic: RID; var _tl_tpos: RID
var _ready := false
var _S := 0
var _N3 := 0
var _Np := 0

# Job slot (main thread writes, worker reads — both under _job_mutex).
var _job: Dictionary = {}
var _job_pending := false

# Publish slot (worker writes under _res_mutex; main reads under it).
var _res_result: Dictionary = {}
var _res_gen := 0
var _consumed_gen := 0
var _wait_next := false   # first job after start() blocks (fresh-bootstrap)


func is_ready() -> bool:
	return _ready


func start(S: int, N3: int, Np: int) -> bool:
	stop()
	_S = S
	_N3 = N3
	_Np = Np
	# Load the shaders HERE (main thread): resource loading is not
	# thread-safe; the worker receives the extracted SPIR-V.
	var bsf := load("res://compute/cassi_tree_build.glsl") as RDShaderFile
	var gsf := load("res://compute/cassi_tree_gravity.glsl") as RDShaderFile
	if bsf == null or gsf == null or bsf.get_spirv() == null or gsf.get_spirv() == null:
		push_error("[TreeWorker] tree shaders failed to load (import race — retry next frame)")
		return false
	var bspirv: RDShaderSPIRV = bsf.get_spirv()
	var gspirv: RDShaderSPIRV = gsf.get_spirv()
	_job_sem = Semaphore.new()
	_done_sem = Semaphore.new()
	_setup_sem = Semaphore.new()
	_job_mutex = Mutex.new()
	_res_mutex = Mutex.new()
	_res_result = {}
	_res_gen = 0
	_consumed_gen = 0
	_job_pending = false
	_wait_next = true
	_ready = false
	_running = true
	_thread = Thread.new()
	_thread_started = _thread.start(_thread_main.bind(bspirv, gspirv)) == OK
	if not _thread_started:
		push_warning("[TreeWorker] thread spawn failed — tree arm stays offline")
		_running = false
		return false
	return true


## Stage a job and (after the bootstrap) fire-and-forget. Returns the fresh
## result only on the synchronous bootstrap frame; otherwise {}.
func submit(job: Dictionary) -> Dictionary:
	if not _thread_started:
		return {}
	if _wait_next:
		# Bootstrap: block until the worker finished setup AND this job.
		_wait_next = false
		_setup_sem.wait()
		if not _ready:
			return {}
		_job_mutex.lock()
		_job = job
		_job_pending = true
		_job_mutex.unlock()
		_job_sem.post()
		_done_sem.wait()
		return _consume_latest()
	if not _ready:
		return {}
	_job_mutex.lock()
	_job = job
	_job_pending = true
	_job_mutex.unlock()
	_job_sem.post()
	return {}


## Non-blocking: the freshest UNCONSUMED completed result.
func poll() -> Dictionary:
	return _consume_latest()


func stop() -> void:
	if _thread != null and _thread_started:
		_running = false
		_job_sem.post()   # wake the worker so it observes _running == false
		_thread.wait_to_finish()
	_thread_started = false
	_thread = null
	_ready = false
	_tlrd = null


func _consume_latest() -> Dictionary:
	_res_mutex.lock()
	var gen := _res_gen
	var res := _res_result
	_res_mutex.unlock()
	if gen > _consumed_gen and not res.is_empty():
		_consumed_gen = gen
		return res
	return {}


func _thread_main(bspirv: RDShaderSPIRV, gspirv: RDShaderSPIRV) -> void:
	_setup(bspirv, gspirv)
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


## Create the local RenderingDevice + all tree resources ON this (worker)
## thread — the verified recipe, mirroring the old in-sim _tree_local_setup.
func _setup(bspirv: RDShaderSPIRV, gspirv: RDShaderSPIRV) -> void:
	_tlrd = RenderingServer.create_local_rendering_device()
	if _tlrd == null:
		push_error("[TreeWorker] local-RD create failed (worker thread)")
		return
	var S := _S
	var N3 := _N3
	var Np := _Np
	var tnm: int = ML_TREE_NODE_MAX_MULT * S + 64
	_tl_src = _tlrd.storage_buffer_create(2 * S * 16)
	_tl_srcw = _tlrd.storage_buffer_create(S * 4)
	_tl_key = _tlrd.storage_buffer_create(S * 4)
	_tl_order = _tlrd.storage_buffer_create(S * 4)
	_tl_cf = _tlrd.storage_buffer_create(tnm * 16)
	_tl_nw = _tlrd.storage_buffer_create(tnm * 16)
	_tl_nq = _tlrd.storage_buffer_create(2 * tnm * 16)
	_tl_nr = _tlrd.storage_buffer_create(tnm * 16)
	_tl_ctr = _tlrd.storage_buffer_create(8 * 4)
	_tl_sites = _tlrd.storage_buffer_create(S * 16)
	_tl_psy = _tlrd.storage_buffer_create(S * 4)
	_tl_psi = _tlrd.storage_buffer_create(S * 4)
	_tl_vol = _tlrd.storage_buffer_create(S * 4)
	_tl_rho = _tlrd.storage_buffer_create(N3 * 4)
	_tl_tgrad = _tlrd.storage_buffer_create(maxi(Np, 1) * 16)
	_tl_tic = _tlrd.storage_buffer_create(maxi(Np, 1) * 4)
	_tl_tpos = _tlrd.storage_buffer_create(maxi(Np, 1) * 16)
	_tl_bld_sh = _tlrd.shader_create_from_spirv(bspirv)
	_tl_bld_pipe = _tlrd.compute_pipeline_create(_tl_bld_sh)
	_tl_grv_sh = _tlrd.shader_create_from_spirv(gspirv)
	_tl_grv_pipe = _tlrd.compute_pipeline_create(_tl_grv_sh)
	_tl_us_b = _tlrd.uniform_set_create([
		_stor_tl(0, _tl_src), _stor_tl(1, _tl_srcw), _stor_tl(2, _tl_key), _stor_tl(3, _tl_order),
		_stor_tl(4, _tl_cf), _stor_tl(5, _tl_nw), _stor_tl(6, _tl_nq), _stor_tl(7, _tl_nr), _stor_tl(8, _tl_ctr),
		_stor_tl(9, _tl_sites), _stor_tl(10, _tl_psy), _stor_tl(11, _tl_psi), _stor_tl(12, _tl_vol), _stor_tl(13, _tl_rho),
	], _tl_bld_sh, 0)
	_tl_us_g = _tlrd.uniform_set_create([
		_stor_tl(0, _tl_src), _stor_tl(3, _tl_order), _stor_tl(4, _tl_cf), _stor_tl(5, _tl_nw),
		_stor_tl(6, _tl_nq), _stor_tl(7, _tl_nr), _stor_tl(8, _tl_ctr), _stor_tl(9, _tl_tgrad),
		_stor_tl(10, _tl_tic), _stor_tl(11, _tl_tpos),
	], _tl_grv_sh, 0)
	_ready = _tl_bld_pipe.is_valid() and _tl_grv_pipe.is_valid() \
		and _tl_us_b.is_valid() and _tl_us_g.is_valid()
	print("[TreeWorker] ready: S=%d N3=%d Np=%d" % [_S, _N3, _Np])


## Free the worker's local-RD resources (ON the worker thread, before exit).
func _free_resources() -> void:
	if _tlrd == null:
		return
	for rid in [_tl_src, _tl_srcw, _tl_key, _tl_order, _tl_cf, _tl_nw, _tl_nq,
			_tl_nr, _tl_ctr, _tl_sites, _tl_psy, _tl_psi, _tl_vol, _tl_rho,
			_tl_tgrad, _tl_tic, _tl_tpos,
			_tl_bld_pipe, _tl_bld_sh, _tl_grv_pipe, _tl_grv_sh]:
		if rid.is_valid():
			_tlrd.free_rid(rid)
	# NOTE (Godot 4.7): free_rid() on the two uniform SETS fails with
	# "Attempted to free invalid ID" from a worker thread (the set's
	# bookkeeping is main-thread-owned). The device free below tears them
	# down with the device — no leak.
	_tlrd.free()
	_tlrd = null
	_ready = false


## The full tree build+walk on the worker's local RD (verbatim from the
## verify_meshless_gravity-proven recipe) + gradient readback + publish.
func _run_job(job: Dictionary) -> void:
	if not _ready:
		return
	var S := int(job.get("S", 0))
	var Np := int(job.get("Np", 0))
	if S != _S or job.get("N3", 0) != _N3 or Np != _Np:
		push_error("[TreeWorker] job size mismatch — restart the worker after reinit")
		return
	var ext: Vector3 = job.get("ext", Vector3.ONE)
	var half: float = job.get("half", 1.0)
	# ADAPTIVE TREE ROOT (perf-decomp 2026-08-15, overhaul migration): the
	# root cube's min corner comes from the tracked structure's bounding box
	# (job.bmin); absent (verify scenes driving the worker with their own
	# job dicts) → the legacy box cube centered at the origin — bit-identical.
	var bmin: Vector3 = job.get("bmin", -Vector3.ONE * half)
	var eps2: float = job.get("eps2", 0.0025)
	var tnm: int = int(job.get("tnm", 0))
	_tlrd.buffer_update(_tl_sites, 0, (job["sites"] as PackedFloat32Array).size() * 4, (job["sites"] as PackedFloat32Array).to_byte_array())
	_tlrd.buffer_update(_tl_psy, 0, (job["psy"] as PackedFloat32Array).size() * 4, (job["psy"] as PackedFloat32Array).to_byte_array())
	_tlrd.buffer_update(_tl_psi, 0, (job["psi"] as PackedFloat32Array).size() * 4, (job["psi"] as PackedFloat32Array).to_byte_array())
	_tlrd.buffer_update(_tl_vol, 0, (job["vol"] as PackedFloat32Array).size() * 4, (job["vol"] as PackedFloat32Array).to_byte_array())
	_tlrd.buffer_update(_tl_rho, 0, (job["rho"] as PackedFloat32Array).size() * 4, (job["rho"] as PackedFloat32Array).to_byte_array())
	_tlrd.buffer_update(_tl_tpos, 0, (job["pos"] as PackedFloat32Array).size() * 4, (job["pos"] as PackedFloat32Array).to_byte_array())
	# seed the self-contained counters + root (host seed is fine on the
	# local RD — no global-RD cross-list race here). The root nodeCF is
	# authoritative from mode-10 ROOT_SEED (bmin+bhalf); the _tl_cf seed
	# mirrors the same root center (bmin + half) for consistency.
	_tlrd.buffer_update(_tl_ctr, 0, 32, PackedInt32Array([1, 0, 1, 0, 0, 0, 0, 0]).to_byte_array())
	_tlrd.buffer_update(_tl_cf, 0, 16, PackedFloat32Array([bmin.x + half, bmin.y + half, bmin.z + half, half]).to_byte_array())
	_tlrd.buffer_update(_tl_nr, 0, 16, PackedInt32Array([0, S, -1, 0]).to_byte_array())
	var bpc := PackedFloat32Array()
	bpc.resize(19)
	bpc[0] = float(S)
	bpc[1] = bmin.x
	bpc[2] = bmin.y
	bpc[3] = bmin.z
	bpc[4] = half
	bpc[5] = eps2
	bpc[6] = PHI
	bpc[7] = PHI_6
	bpc[8] = float(ML_TREE_LEAF_CAP)
	bpc[9] = float(ML_TREE_MAX_LEVELS)
	bpc[14] = float(int(job.get("grid_N", 0)))
	bpc[15] = ext.x
	bpc[16] = ext.y
	bpc[17] = ext.z
	bpc[18] = ML_TREE_FIELD_FLOOR
	var gpc := PackedFloat32Array()
	gpc.resize(5)
	gpc[0] = float(Np)
	gpc[1] = ML_TREE_THETA
	gpc[2] = eps2
	gpc[3] = 1.0
	gpc[4] = float(tnm)
	var pg := int(ceil(float(S) / 64.0))
	var pall := int(ceil(float(tnm) / 64.0))
	var cl := _tlrd.compute_list_begin()
	_tlrd.compute_list_bind_compute_pipeline(cl, _tl_bld_pipe)
	_tlrd.compute_list_bind_uniform_set(cl, _tl_us_b, 0)
	# gather (mode 7) + bitonic (1/13) + BFS split (5/8) + moments (6)
	bpc[10] = 7.0
	_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
	_tlrd.compute_list_dispatch(cl, pg, 1, 1)
	_tlrd.compute_list_add_barrier(cl)
	var k := 2
	while k <= S:
		var j := k >> 1
		while j >= 1:
			bpc[10] = 1.0
			bpc[11] = float(k)
			bpc[12] = float(j)
			bpc[13] = 1.0
			_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
			_tlrd.compute_list_dispatch(cl, pg, 1, 1)
			_tlrd.compute_list_add_barrier(cl)
			j = j >> 1
		k = k << 1
	_tlrd.compute_list_add_barrier(cl)
	for _d in range(ML_TREE_MAX_LEVELS):
		bpc[10] = 5.0
		_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
		_tlrd.compute_list_dispatch(cl, pall, 1, 1)
		_tlrd.compute_list_add_barrier(cl)
		bpc[10] = 8.0
		_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
		_tlrd.compute_list_dispatch(cl, 1, 1, 1)
		_tlrd.compute_list_add_barrier(cl)
	bpc[10] = 6.0
	_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
	_tlrd.compute_list_dispatch(cl, pall, 1, 1)
	_tlrd.compute_list_add_barrier(cl)
	# walk — one thread per PARTICLE (_tl_tpos targets), writes _tl_tgrad
	_tlrd.compute_list_bind_compute_pipeline(cl, _tl_grv_pipe)
	_tlrd.compute_list_bind_uniform_set(cl, _tl_us_g, 0)
	_tlrd.compute_list_set_push_constant(cl, gpc.to_byte_array(), gpc.size() * 4)
	_tlrd.compute_list_dispatch(cl, int(ceil(float(Np) / 64.0)), 1, 1)
	_tlrd.compute_list_end()
	_tlrd.submit()
	_tlrd.sync()
	# publish: per-particle gradient + node count
	var grad := _tlrd.buffer_get_data(_tl_tgrad, 0, Np * 16).to_float32_array()
	var nc := _tlrd.buffer_get_data(_tl_ctr, 0, 4).to_int32_array()
	_res_mutex.lock()
	_res_result = {"grad": grad, "nc": nc[0] if nc.size() else 0}
	_res_gen += 1
	_res_mutex.unlock()


# LOCAL-RD uniform-storage helper (RDUniform for a storage buffer).
func _stor_tl(bind: int, r: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = bind
	u.add_id(r)
	return u
