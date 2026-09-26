package dev.cassicraft.domain.thread;

import dev.cassicraft.domain.engine.SpectralPoisson;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>Kernel/resource loading on the <b>main thread</b> (BUILD-PLAN.md §3.3;
 * async-field-domain.md §6): resource loading is not thread-safe, so the worker
 * never opens sources itself. The main thread builds the kernels here and hands
 * the ready context into the worker's start config.
 *
 * <p>CPU-first Phase 1 means "kernels" are the plain-Java solvers already
 * constructed on the main thread; the future OpenCL backend compiles real
 * program/kernel objects here and passes them the same way.
 */
public final class KernelLoader {

	/** Ready-to-use backend context handed to the worker in its start config. */
	public record KernelContext(SpectralPoisson poisson) {
	}

	/**
	 * Build the backend context on the calling (main) thread. Cheap for CPU Phase 1.
	 */
	public KernelContext load() {
		// CPU backend: the Poisson solver is the only "kernel" object the worker needs.
		return new KernelContext(new SpectralPoisson());
	}
}
