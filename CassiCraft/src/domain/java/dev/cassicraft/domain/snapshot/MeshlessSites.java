package dev.cassicraft.domain.snapshot;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The sparse meshless-site record: 8192 moving-Voronoi sites (2·16³ at N=64,
 * {@code ML_N1 = 16}) that mark "where the field is most organized" and double as
 * the chunk-activity / LOD scheduler (chunk-field-quantization.md §5). Each site
 * carries a position + per-site coherence; the server projects sites onto chunk
 * space to mark active chunks for re-quantization.
 *
 * <p>Phase 1 may start with a simpler radial-hotness fallback and add the sites
 * once the seam is steady (BUILD-PLAN.md §3.2 item 5). STUB: bounded array shape
 * pinned; the JFA/Lloyd rebuild body is later work.
 */
public final class MeshlessSites {

	/** Hard constant from the engine: {@code ML_N1 = 16} → 2·16³ = 8192 sites. */
	public static final int SITE_COUNT = 2 * 16 * 16 * 16;

	private final float[] x;
	private final float[] y;
	private final float[] z;
	private final float[] coherence;

	private int count;

	public MeshlessSites() {
		this.x = new float[SITE_COUNT];
		this.y = new float[SITE_COUNT];
		this.z = new float[SITE_COUNT];
		this.coherence = new float[SITE_COUNT];
		this.count = 0;
	}

	/** Reset the buffer for a fresh rebuild (every {@code ML_REBUILD = 25} steps). */
	public void reset() {
		this.count = 0;
	}

	public void addSite(float x, float y, float z, float coherence) {
		if (count >= SITE_COUNT) {
			throw new IllegalStateException("MeshlessSites capacity exceeded");
		}
		this.x[count] = x;
		this.y[count] = y;
		this.z[count] = z;
		this.coherence[count] = coherence;
		this.count++;
	}

	public int count() {
		return count;
	}

	public float[] x() {
		return x;
	}

	public float[] y() {
		return y;
	}

	public float[] z() {
		return z;
	}

	public float[] coherence() {
		return coherence;
	}
}
