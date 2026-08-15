/**
 * @cassicore/host — empty-shell placeholder (P5).
 *
 * The standalone host surface (daemon.ts composition root, entry/, cli/, bridge/,
 * scripts/qwen, bin/ + the vendored retained brain) has been retired and/or folded
 * into `@cassicore/mind-runtime` (CASSICORE-FOCUS §5 #26 / §6 P5). The retained
 * mind composition now lives entirely in `@cassicore/mind-runtime`; nothing imports
 * `@cassicore/host` anymore (zero-import guard verified at P5). This package is a
 * minimal shell retained solely so the workspace graph stays coherent until its
 * deletion at P7. No standalone surface, no exports.
 */
export const HOST_RETIRED = true
