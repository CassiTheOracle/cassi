package dev.cassicraft.domain.engine;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The backend adapter seam (async-field-domain.md §6). The CPU solver is
 * Phase 1; a future OpenCL backend implements the same publish contract so the
 * sampler and world-writer never know the difference. This interface is the
 * factory-selected {@code implements} boundary that keeps the swap a
 * construction-site change, not a contract change.
 */
public interface EngineBackend {

	/** Submit a bounded run of steps (cumulative target, newest-wins per the corpus loop). */
	int submitSteps(int target, boolean block);

	/** The latest executed step count. */
	int executed();

	/** Poll the freshest job meta. */
	EngineJob poll();

	/** Close the backend explicitly — never a finalizer/GC hook (BUILD-PLAN.md §3.3). */
	void close();
}
