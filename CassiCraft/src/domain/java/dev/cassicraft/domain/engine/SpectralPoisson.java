package dev.cassicraft.domain.engine;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The spectral Poisson solver: {@code ∇²Φ = ρ_mass}, {@code Φ̂ = −ρ̂/k²},
 * with {@code k=0} nulled — the port of {@code CassiCosmos/compute/cassi_poisson.glsl}.
 * The engine uses a hand-rolled <b>fused Stockham</b> complex FFT, 6 dispatches
 * per solve: {@code clear → load+x → fft(y) → fft(z) → [kspace+inv-z] → ifft(y) →
 * ifft(x)} (PORT-SPEC §2.2, `cassi_physics_engine.gd:2464-2513`).
 *
 * <p>Constraint / convention (shader `:9-17`):
 * <pre>
 *   ∇²Φ = ρ_mass,  Φ̂ = −ρ̂/k²,  k = 0 nulled.
 *   k_i = 2π·fftfreq(N)/L_i,  L_i = 2·extent_i
 *   fftfreq: n ≤ N/2 → +n, n > N/2 → n − N   (Nyquist at +N/2 only)
 * </pre>
 * The k-space multiply is a <b>division</b> {@code −f/k2} (one rounding), never
 * a reciprocal-multiply — the shader comment at `:144-147` is explicit that a
 * reciprocal-multiply differs by ~1 ulp and would break bit-level parity.
 *
 * <p>FFT decision (PORT-SPEC §2.4): a <b>hand-rolled radix-2 Stockham</b> for
 * determinism. A library FFT (JVector/JTransforms) uses a different
 * radix/decomposition/twiddle ordering and cannot be bit-identical to the
 * shader's autosort Stockham schedule (same bit-reversed load, double-buffered
 * banks, same stage order). The twiddle table is computed once at init with
 * {@link Math#cos}/{@link Math#sin} in the exact forward convention
 * {@code vec2(cos, −sin)} — this Java table is deterministic for the Java
 * replay gate; the future <em>GPU-parity</em> step is to freeze hard-coded
 * table constants (the GPU's libm may differ by ~1 ulp). The butterfly stage
 * sequence and the fused kspace-into-inverse-z load are the highest-fidelity
 * contract (PORT-SPEC §7 risk 1) and must not be reordered.
 *
 * <p>Each <b>inverse</b> pass scales by {@code 1/N} (shader `:252-253`); three
 * inverse passes → total {@code 1/N³} for a normalized transform. Forward
 * passes are unnormalized. After the last pass the <b>real</b> part of the
 * buffer holds Φ (imag ≈ 0); {@link #solve} writes that into {@code phi}.
 *
 * <p>Poisson ρ source (PORT-SPEC §7 risk 7 / §2.2, flag #4 resolved): the engine
 * deposits particle mass as the Poisson source; the <em>field-only</em> port
 * solves over the two-fluid's own density {@code ρ = EY+EI}. The source array
 * is a parameter of {@link #solve(float[], float[])}.
 */
public final class SpectralPoisson {

	/** Grid size matches the solver — N = 64 (radix-2), bits = 6. */
	public static final int N = TwoFluidSolver.N;
	public static final int CELLS = N * N * N;
	private static final int BITS = 6;   // log2(N)
	private static final int HALF = N / 2;

	private static final float TWO_PI = 6.28318530717958647693f;
	/** Per-axis box half-extent (cube, PORT-SPEC §5). */
	private static final float EXTENT = TwoFluidSolver.EXTENT;

	/** Interleaved complex buffer: {@code f[2·cell] = re}, {@code f[2·cell+1] = im}. */
	private final float[] f;
	/** Twiddle table in the shader's offset layout: index {@code (1<<(s-1))-1 + jj}. */
	private final float[] twRe;
	private final float[] twIm;

	/** How a row's elements are initially loaded into the working bank. */
	private enum Source { BUFFER, RHO, KSPACE }

	public SpectralPoisson() {
		this.f = new float[CELLS * 2];
		int size = (1 << BITS) - 1;
		this.twRe = new float[size];
		this.twIm = new float[size];
		for (int s = 1; s <= BITS; s++) {
			int halfn = 1 << (s - 1);
			int offset = halfn - 1;
			for (int jj = 0; jj < halfn; jj++) {
				float ang = TWO_PI * jj / (float) (1 << s);
				int idx = offset + jj;
				twRe[idx] = (float) Math.cos(ang);
				twIm[idx] = (float) -Math.sin(ang);   // forward: exp(−iθ)
			}
		}
	}

	/**
	 * Solve {@code ∇²Φ = ρ} in place: given the density field, fill {@code phi}
	 * with the potential Φ (the real part of the FFT buffer). Per the fused
	 * engine chain — 6 axis passes: {@code load+x → fft(y) → fft(z) →
	 * [kspace+inv-z] → ifft(y) → ifft(x)}.
	 *
	 * @param rho density source (= EY+EI for the field-only port), length CELLS
	 * @param phi potential output, length CELLS
	 */
	public void solve(float[] rho, float[] phi) {
		// The engine's mode-3 clear zeroes the particle-deposit accumulator; the
		// Java solve is a pure function over rho, so clear is a no-op here.
		passAxis(0, false, Source.RHO, rho);   // mode 4: fused load ρ + forward-x
		passAxis(1, false, Source.BUFFER, rho); // mode 1: forward y
		passAxis(2, false, Source.BUFFER, rho); // mode 1: forward z
		passAxis(2, true, Source.KSPACE, rho); // mode 5: inverse-z fused kspace
		passAxis(1, true, Source.BUFFER, rho); // mode 1: inverse y
		passAxis(0, true, Source.BUFFER, rho); // mode 1: inverse x
		for (int c = 0; c < CELLS; c++) {
			phi[c] = f[2 * c];   // real part holds Φ afterward
		}
	}

	/**
	 * One multi-row Stockham axis pass (shader {@code fft_main}, `:164-254`):
	 * a radix-2 DIT over every length-{@code N} line parallel to {@code axis}.
	 * Each line's {@code N} elements are loaded into a working bank in
	 * <b>bit-reversed</b> order, then run through the staged butterflies
	 * (double-buffered banks, one barrier-equivalent per stage), and written
	 * back scaled (1/N on inverse). The {@code Source.RHO}/{@code KSPACE}
	 * variants fuse the load (mode 4 / mode 5) exactly as the engine chain does.
	 */
	private void passAxis(int axis, boolean inverse, Source src, float[] rho) {
		float scale = inverse ? 1.0f / N : 1.0f;
		float[] b0 = new float[2 * N];
		float[] b1 = new float[2 * N];
		for (int row = 0; row < N * N; row++) {
			int r0 = row % N;
			int r1 = row / N;
			int base;
			int stride;
			if (axis == 0) {
				base = N * r0 + N * N * r1;
				stride = 1;
			} else if (axis == 1) {
				base = r0 + N * N * r1;
				stride = N;
			} else {
				base = r0 + N * r1;
				stride = N * N;
			}
			// Bit-reversed load into bank b0 (slot e holds the line element at
			// physical offset bitrev(e) along the axis — the DIT input order).
			for (int e = 0; e < N; e++) {
				int phys = base + bitrev(e, BITS) * stride;
				float re;
				float im;
				switch (src) {
				case BUFFER:
					re = f[2 * phys];
					im = f[2 * phys + 1];
					break;
				case RHO:
					re = rho[phys];
					im = 0.0f;
					break;
				default: // KSPACE: −v/k², k = 0 nulled — DIVISION, one rounding.
					float k2 = k2OfCell(phys);
					if (k2 > 0.0f) {
						re = -f[2 * phys] / k2;
						im = -f[2 * phys + 1] / k2;
					} else {
						re = 0.0f;
						im = 0.0f;
					}
					break;
				}
				b0[2 * e] = re;
				b0[2 * e + 1] = im;
			}
			float[] rbank = b0;
			float[] wbank = b1;
			for (int s = 1; s <= BITS; s++) {
				int nSub = 1 << s;
				int halfn = 1 << (s - 1);
				int twBase = halfn - 1;
				for (int e = 0; e < N; e++) {
					int jj = e & (nSub - 1);
					int blk = e >> s;
					if (jj < halfn) {
						int slot = (blk * nSub + jj) * 2;
						float evenRe = rbank[slot];
						float evenIm = rbank[slot + 1];
						float oddRe = rbank[slot + 2 * halfn];
						float oddIm = rbank[slot + 2 * halfn + 1];
						int tw = twBase + jj;
						float twR = twRe[tw];
						float twI = inverse ? -twIm[tw] : twIm[tw];   // conjugate on inverse
						// o = odd · tw (complex multiply, shader :239).
						float oRe = oddRe * twR - oddIm * twI;
						float oIm = oddRe * twI + oddIm * twR;
						wbank[slot] = evenRe + oRe;
						wbank[slot + 1] = evenIm + oIm;
						wbank[slot + 2 * halfn] = evenRe - oRe;
						wbank[slot + 2 * halfn + 1] = evenIm - oIm;
					}
				}
				float[] tmp = rbank;
				rbank = wbank;
				wbank = tmp;
			}
			// Write back scaled; slot e → physical offset e along the line.
			for (int e = 0; e < N; e++) {
				int out = 2 * (base + e * stride);
				f[out] = rbank[2 * e] * scale;
				f[out + 1] = rbank[2 * e + 1] * scale;
			}
		}
	}

	/** k² for one cell — the shader's exact formula (shader `k2_of_cell`, `:147-158`). */
	private static float k2OfCell(int cell) {
		int i = cell % N;
		int j = (cell / N) % N;
		int k = cell / (N * N);
		int kx = (i <= HALF) ? i : i - N;
		int ky = (j <= HALF) ? j : j - N;
		int kz = (k <= HALF) ? k : k - N;
		float kxw = TWO_PI * kx / (2.0f * EXTENT);
		float kyw = TWO_PI * ky / (2.0f * EXTENT);
		float kzw = TWO_PI * kz / (2.0f * EXTENT);
		return kxw * kxw + kyw * kyw + kzw * kzw;
	}

	/** Reverse the low {@code bits} bits of {@code x} (shader `bitrev`, `:125-132`). */
	private static int bitrev(int x, int bits) {
		int r = 0;
		for (int b = 0; b < bits; b++) {
			r = (r << 1) | (x & 1);
			x >>= 1;
		}
		return r;
	}
}
