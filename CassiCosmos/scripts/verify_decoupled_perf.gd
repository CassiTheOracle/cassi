extends Node
## ───────────────────────────────────────────────────────────────────────────
## verify_decoupled_perf — PERF PROBE for the direct local-RD physics engine
## (scripts/cassi_physics_engine.gd standalone runner).
##
## Reproduces and times the two reported symptoms with HARD NUMBERS:
##   (1) the DETACHED-physics bootstrap path — direct local-RD setup performs
##       synchronous shader/buffer/IC initialization, then the first run_steps
##       batch waits for completion. This probe reports setup and first-batch
##       timing rather than the obsolete threaded protocol.
##   (2) MATTER-CONDENSING STUTTER — the particle-merge pass (particle_merge,
##       the live main.tscn "dust -> object" coalesce). Every merge cycle does
##       a ~35 MB host prefix-sum readback (cc) + two ~35 MB buffer_update
##       uploads (cs/ch) + an 8.9M-iteration CPU prefix-sum, with submit+sync
##       per cycle; in the standalone local-RD path it stalls the physics
##       batch (Trap T2).
##
## The probe instantiates its OWN engine(s) with private local RDs — fully
## isolated from any live sim; it touches NO shared sim files. It prints a
## timing table and (reproducible) writes → res://_diag/
## decoupled_perf_report.json (gitignored), then quits itself (exit 0).
## All engines use the current direct local-RD setup (rd_global=false,
## owns_rd=true), with synchronous run_steps batches and explicit readbacks.
##
## LAUNCH (windowed — local RD needs a real GPU; NEVER --headless):
##   Godot_v4.7-stable_win64_console.exe --path <space-sim> \
##       res://scenes/verify_decoupled_perf.tscn
## ───────────────────────────────────────────────────────────────────────────

const ENGINE_SCRIPT := "res://scripts/cassi_physics_engine.gd"

# Baseline config mirroring the LIVE main.tscn geometry (so the merge spatial
# hash, which is geometry-driven, matches the ~8.9M cells the user's scene
# builds). default cluster_radius in engine = 50; main.tscn uses 120.
const LIVE_CLUSTER_RADIUS := 120.0
const LIVE_NUM_CLUSTERS := 10
const LIVE_GRID_N := 64

# ── probe sizes ──
# The hang is size-driven (2.5M particles → ~83 MB fp32 snapshot + a
# multi-second IC loop). We run the bootstrap at the FULL size to reproduce
# it; the per-step / merge cost quantification uses a smaller N so the probe
# stays bounded (the merge hash readback is particle-count INDEPENDENT).
const HANG_N_PARTICLES := 2500000
const PROFILE_N_PARTICLES := 300000

# Bounded step budgets so the probe is quick.
const HANG_BOOTSTRAP_STEPS := 4

var report: Dictionary = {}
var _engine = null
var _cfg := {}


func _ready() -> void:
	# House rule: never run while the live sim process shares this GPU in a
	# way that distorts timings — the probe is its own process by design.
	print("[perf] decoupled-perf probe — baseline hang/condensation timing")
	report["machine"] = {
		"godot": "4.7 win64 console (windowed, local RD)",
		"note": "AMD RX 7900 XTX; timings include PCIe transfer + CPU loops",
	}

	var table := []
	# ── Symptom 1: the DETACHED bootstrap timing (full 2.5M) ─────────────
	table.append(_probe_bootstrap())
	# ── Synchronous snapshot/readback economics ──────────────────────────
	table.append(_probe_readback())
	# ── Symptom 2: merge pass cost (per-batch readback + prefix-sum) ─────
	table.append(_probe_merge())
	# ── Condensation / BH-accretion per-step chain cost (toggle) ────────
	table.append(_probe_condensation())
	# ── Local-RD float-atomic accumulation (FIX D pre-check) ────────────
	table.append(_probe_worker_atomicaults())

	report["timings"] = table
	print("\n══════ decoupled-perf probe — timing table ══════")
	for row in table:
		print("  %-46s %10s" % [row.label, row.value])
	print("════════════════════════════════════════════════")
	var out_dir := "res://_diag"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	var f := FileAccess.open(out_dir + "/decoupled_perf_report.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(report, "\t"))
		f.close()
		print("[perf] report → res://_diag/decoupled_perf_report.json")
	get_tree().quit(0)


func _base_cfg(n_particles: int, extras: Dictionary) -> Dictionary:
	var c = {
		"grid_N": LIVE_GRID_N,
		"N_particles": n_particles,
		"dt": 0.002,
		"cluster_radius": LIVE_CLUSTER_RADIUS,
		"num_clusters": LIVE_NUM_CLUSTERS,
		"cluster_separation": 120.0,
		"gravity_mode": 0,          # river (the per-step chain stays deterministic)
		"meshless_mode": false,     # grid path (deterministic, no tree worker)
		"meshless_gravity": false,
		"dual_grid": true,
		"black_holes_enabled": false,
		"particle_merge": false,
		"bh_accretion": false,
		"seed": 7,                  # fixed ICs (reproducible; engine key is "seed")
	}
	for k in extras:
		c[k] = extras[k]
	return c


func _new_engine(cfg: Dictionary):
	var rd: RenderingDevice = RenderingServer.create_local_rendering_device()
	if rd == null:
		return null
	var e = load(ENGINE_SCRIPT).new()
	var local_cfg: Dictionary = cfg.duplicate()
	local_cfg["rd"] = rd
	local_cfg["rd_global"] = false
	local_cfg["owns_rd"] = true
	if not e.setup(local_cfg):
		e.shutdown()
		return null
	return e


func _ms() -> int:
	return Time.get_ticks_msec()


func _row(label: String, value: String) -> Dictionary:
	return {"label": label, "value": value}


## ── Probe 1: the detached bootstrap path ─────────────────────────────────
## The current standalone path is synchronous: setup() builds the local-RD
## engine, then run_steps(..., true) records, submits, and waits for a batch.
## Measure those phases directly, followed by the actual fp32 readback.
func _probe_bootstrap() -> Dictionary:
	print("\n── [perf] Probe 1: detached ENGINE BOOTSTRAP (synchronous local RD) ──")
	var rd: RenderingDevice = RenderingServer.create_local_rendering_device()
	if rd == null:
		return _row("PROBE1 bootstrap local RD", "FAILED (local RD)")
	var e = load(ENGINE_SCRIPT).new()
	_engine = e
	var cfg: Dictionary = _base_cfg(HANG_N_PARTICLES, {"black_holes_enabled": false})
	cfg["rd"] = rd
	cfg["rd_global"] = false
	cfg["owns_rd"] = true
	var t_setup := _ms()
	var ok: bool = e.setup(cfg)
	var setup_ms := _ms() - t_setup
	if not ok:
		_stop_engine()
		return _row("PROBE1 bootstrap setup", "FAILED (local RD)")
	var t_batch := _ms()
	e.run_steps(HANG_BOOTSTRAP_STEPS, true)
	var first_batch_ms := _ms() - t_batch
	var t_readback := _ms()
	var snap: Dictionary = e.readback_snapshot()
	var pos: PackedFloat32Array = snap.get("pos", PackedFloat32Array())
	var vel: PackedFloat32Array = snap.get("vel", PackedFloat32Array())
	var fq: PackedFloat32Array = snap.get("field_q", PackedFloat32Array())
	var pot: PackedFloat32Array = snap.get("pot", PackedFloat32Array())
	var telemetry: Dictionary = e.readback_telemetry(fq)
	var readback_ms := _ms() - t_readback
	var exec := int(e._executed)
	var mb := (pos.size() + vel.size() + fq.size() + pot.size()) * 4 / (1024.0 * 1024.0)
	print("  [perf] setup (local RD, synchronous):                %d ms" % setup_ms)
	print("  [perf] first run_steps(%d,true) batch:              %d ms" % [HANG_BOOTSTRAP_STEPS, first_batch_ms])
	print("  [perf] first fp32 snapshot + telemetry readback:   %d ms  -> executed=%d, snapshot=%.1f MB" % [readback_ms, exec, mb])
	print("  [perf] first telemetry q_mean=%.6f" % float(telemetry.get("q_mean", 0.0)))
	var row := _row("PROBE1 bootstrap setup + first batch", "%d ms + %d ms" % [setup_ms, first_batch_ms])
	row["_detail"] = {
		"setup_ms": setup_ms, "first_batch_ms": first_batch_ms,
		"first_readback_ms": readback_ms, "executed": exec,
		"snapshot_mb": mb, "steps": HANG_BOOTSTRAP_STEPS,
	}
	# Keep the useful warm batch timing, now through the synchronous local-RD API.
	print("\n── [perf] Probe 1b: synchronous local-RD batch latency ──")
	var t_tot := 0
	for _i in range(4):
		var tn := _ms()
		e.run_steps(HANG_BOOTSTRAP_STEPS, true)
		t_tot += _ms() - tn
	print("  [perf] local-RD batch (%d steps + wait): avg %d ms (%.2f ms/step)" % [HANG_BOOTSTRAP_STEPS, t_tot / 4, float(t_tot) / 4.0 / float(HANG_BOOTSTRAP_STEPS)])
	row["_detail"]["per_batch_ms"] = t_tot / 4
	_stop_engine()
	return row

# ── Probe 2: synchronous snapshot/readback economics ─────────────────────
func _probe_readback() -> Dictionary:
	print("\n── [perf] Probe 2: synchronous fp32 snapshot/readback economics ──")
	_engine = null
	_engine = _new_engine(_base_cfg(HANG_N_PARTICLES, {}))
	if _engine == null:
		return _row("PROBE2 snapshot readback fp32", "FAILED")
	# Warm the chain, then time only the readbacks that the current API exposes.
	_engine.run_steps(2, true)
	var t0 := _ms()
	var snap: Dictionary = _engine.readback_snapshot()
	var fq: PackedFloat32Array = snap.get("field_q", PackedFloat32Array())
	var telemetry: Dictionary = _engine.readback_telemetry(fq)
	var t_readback := _ms() - t0
	var pos: PackedFloat32Array = snap.get("pos", PackedFloat32Array())
	var vel: PackedFloat32Array = snap.get("vel", PackedFloat32Array())
	var pot: PackedFloat32Array = snap.get("pot", PackedFloat32Array())
	var mb := (pos.size() + vel.size() + fq.size() + pot.size()) * 4 / (1024.0 * 1024.0)
	print("  [perf] synchronous fp32 snapshot + telemetry readback: %d ms (%.1f MB)" % [t_readback, mb])
	print("  [perf] telemetry q_mean=%.6f" % float(telemetry.get("q_mean", 0.0)))
	var row := _row("PROBE2 snapshot readback fp32", "%d ms (%.1f MB)" % [t_readback, mb])
	row["_detail"] = {
		"fp32_ms": t_readback, "snapshot_mb": mb,
		"q_mean": float(telemetry.get("q_mean", 0.0)),
		"N": HANG_N_PARTICLES,
	}
	_stop_engine()
	return row


# ── Probe 3: merge pass cost ──────────────────────────────────────────────
func _probe_merge() -> Dictionary:
	print("\n── [perf] Probe 3: MATTER-CONDENSING (particle merge) cost ──")
	var c3 := _base_cfg(PROFILE_N_PARTICLES, {"particle_merge": true})
	print("      [debug] cfg.particle_merge=%s (probe intends true)" % c3.particle_merge)
	# engine A: particle_merge ON → measures the merge pass per batch
	var em = _new_engine(c3)
	if em == null:
		return _row("PROBE3 merge pass", "FAILED (merge buffers)")
	var em2 = _new_engine(_base_cfg(PROFILE_N_PARTICLES, {"particle_merge": false}))
	if em2 == null:
		em.shutdown()
		return _row("PROBE3 merge twin", "FAILED")
	# Setup is synchronous; warm both local-RD engines before the timed batch.
	em.run_steps(2, true)
	em2.run_steps(2, true)
	print("      [debug] em.particle_merge=%s hash=(%d,%d,%d) total=%d  em2.particle_merge=%s" % [
		em.particle_merge, em._merge_hash_nx, em._merge_hash_ny, em._merge_hash_nz,
		em._merge_hash_total, em2.particle_merge])
	var hash_total: int = em._merge_hash_total
	var hash_mb: float = hash_total * 4.0 / (1024.0 * 1024.0)
	# A fresh equal batch on each warm engine — the delta is the merge cost.
	var margin_steps := 8
	var t_m_0 := _ms()
	em.run_steps(margin_steps, true)
	var t_m := _ms() - t_m_0
	var t_nm_0 := _ms()
	em2.run_steps(margin_steps, true)
	var t_nm := _ms() - t_nm_0
	var merge_overhead_ms: float = float(t_m - t_nm)
	print("      merge hash cells = %d  (%.1f MB read / %.1f MB upload per cycle)" % [hash_total, hash_mb, hash_mb])
	print("  [perf] %d-step batch WITHOUT merge: %d ms (%.2f ms/step)" % [margin_steps, t_nm, float(t_nm) / margin_steps])
	print("  [perf] %d-step batch WITH    merge: %d ms (%.2f ms/step)  -> merge overhead ≈ %+d ms/batch" % [margin_steps, t_m, float(t_m) / margin_steps, int(merge_overhead_ms)])
	print("  [perf] merge cycles run (engine lifetime): %d" % em._merge_cycles_run)
	var row := _row("PROBE3 merge overhead per batch", "%+d ms (%d hash cells)" % [int(merge_overhead_ms), hash_total])
	row["_detail"] = {
		"hash_total": hash_total, "hash_readback_mb": hash_mb,
		"batch_no_merge_ms": t_nm, "batch_with_merge_ms": t_m,
		"merge_overhead_ms": int(merge_overhead_ms),
		"merge_cycles_lifetime": em._merge_cycles_run,
	}
	em.shutdown()
	em2.shutdown()
	_engine = null
	return row


# ── Probe 4: condensation / BH-integrate chain cost ───────────────────────
func _probe_condensation() -> Dictionary:
	print("\n── [perf] Probe 4: BH chain (condensation scan every 100 steps, BH-integrate every step) ──")
	var eA = _new_engine(_base_cfg(PROFILE_N_PARTICLES, {"black_holes_enabled": false}))
	var eB = _new_engine(_base_cfg(PROFILE_N_PARTICLES, {"black_holes_enabled": true, "bh_accretion": false}))
	if eA == null or eB == null:
		if eA != null:
			eA.shutdown()
		if eB != null:
			eB.shutdown()
		return _row("PROBE4 BH chain", "FAILED")
	# Setup is synchronous; warm both before timing a batch that crosses the
	# condensation cadence.
	eA.run_steps(2, true)
	eB.run_steps(2, true)
	var steps := 102
	var ta_0 := _ms()
	eA.run_steps(steps, true)
	var ta := _ms() - ta_0
	var tb_0 := _ms()
	eB.run_steps(steps, true)
	var tb := _ms() - tb_0
	print("  [perf] BH OFF: %d steps, %d ms  -> %.2f ms/step" % [steps, ta, float(ta) / steps])
	print("  [perf] BH  ON: %d steps, %d ms  -> %.2f ms/step  (condensation every 100, BH-integrate every step)" % [steps, tb, float(tb) / steps])
	var row := _row("PROBE4 BH-chain ms/step (off→on)", "%.2f → %.2f ms/step" % [float(ta) / steps, float(tb) / steps])
	row["_detail"] = {"off_ms": ta, "on_ms": tb, "steps": steps}
	eA.shutdown()
	eB.shutdown()
	_engine = null
	return row


func _stop_engine() -> void:
	if _engine != null:
		_engine.shutdown()
		_engine = null


# ── Probe 5: local-RD FLOAT-ATOMIC accumulation check ─────────────────────
# Settles FIX D empirically: does the BH-accretion float atomicAdd
# (OpAtomicFAddEXT) actually accumulate on the local RenderingDevice? We plant
# a BH record via the engine's own _bh_init_bytes member, set bh_accretion ON
# with particle_merge OFF (so any pos.w=0 deaths are from ACCRETION alone, not
# from a merge zeroing), and count deaths in the fp32 snapshot readback.
func _probe_worker_atomicaults() -> Dictionary:
	print("\n── [perf] Probe 5: BH-ACCRETION float atomic on the local RD ──")
	var cfg := _base_cfg(100000, {
		"black_holes_enabled": true, "bh_accretion": true,
		"particle_merge": false,
		"bh_accretion_radius": 100.0, "cluster_radius": 40.0,
		"num_clusters": 1, "cluster_separation": 0.0,
		"source_strength": 0.0, "bh_acc_rate": 0.0,
	})
	var e = _new_engine(cfg)
	if e == null:
		return _row("PROBE5 local accretion atomic", "FAILED (setup)")
	_engine = e
	# setup() is synchronous, so _apply_gravity_calibration is complete and
	# _bh_init_bytes is final before planting the BH header.
	var b: PackedByteArray = e._bh_init_bytes.duplicate()
	if b.size() < 96:
		_stop_engine()
		return _row("PROBE5 local accretion atomic", "FAILED (header)")
	b.encode_float(64, 0.0); b.encode_float(68, 0.0); b.encode_float(72, 0.0)
	b.encode_float(76, 5.0)   # planted BH mass 5.0 at origin
	b.encode_float(80, 0.0); b.encode_float(84, 0.0); b.encode_float(88, 0.0)
	b.encode_float(92, 0.0)
	e._bh_init_bytes = b
	# R_acc=100 covers the whole Plummer ball -> if the atomic fires, the bulk
	# of the ~100k particles die (pos.w=0). bh_acc_rate=0 kills integrate
	# growth so accretion is the only death source (no merge in this config).
	var t0 := _ms()
	e.run_steps(6, true)
	var batch_ms := _ms() - t0
	var snap: Dictionary = e.readback_snapshot()
	var pos: PackedFloat32Array = snap.get("pos", PackedFloat32Array())
	var dead := 0
	var total := pos.size() / 4
	for i in range(pos.size() / 4):
		if pos[i * 4 + 3] <= 0.0:
			dead += 1
	print("      [perf] local BH-accretion: %d/%d particles dead (pos.w=0) after 6 steps, batch=%d ms (R_acc=100, planted BH mass 5)" % [dead, total, batch_ms])
	var worked := dead > 0
	print("      [perf] => float-atomic accretion on local RD: %s" % ("ACCUMULATES (works)" if worked else "NO DEATHS (atomic did not fire)"))
	var row := _row("PROBE5 local accretion float-atomic", "WORKS (%d dead)" % dead if worked else "NO-OP (%d dead)" % dead)
	row["_detail"] = {"dead": dead, "total": total, "batch_ms": batch_ms, "atomic_worked": worked}
	_stop_engine()
	return row
