/**
 * HEALPix cell assignment for spherical position indexing.
 *
 * HEALPix (Hierarchical Equal Area isoLatitude Pixelization) partitions the
 * sphere into equal-area cells. This gives us O(1) spatial bucketing:
 * engrams in the same cell are geometrically nearby, and neighboring cells
 * can be enumerated without distance computations.
 *
 * We use a simplified ring-based scheme that matches HEALPix's RING ordering:
 * cells are numbered by rings of constant latitude, making z-band queries
 * and neighbor enumeration straightforward at our modest resolutions.
 *
 * Reference: Górski+ 2005, "HEALPix: A Framework for High-Resolution
 * Discretization and Fast Analysis of Data Distributed on the Sphere"
 */

/** Number of cells: 12 × nside² */
export function nCells(nside: number): number {
  return 12 * nside * nside
}

/**
 * Convert spherical coordinates to a ring-indexed cell.
 *
 * Ring ordering: cells numbered north-to-south by latitude rings.
 * Within each ring, cells are numbered eastward from phi=0.
 *
 * @param theta Azimuthal angle [0, 2π]
 * @param phi   Polar angle [0, π] (0 = north pole)
 * @param nside Resolution parameter
 * @returns Cell index in [0, 12×nside² - 1]
 */
export function ringCell(theta: number, phi: number, nside: number): number {
  theta = ((theta % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)
  phi = Math.max(0, Math.min(Math.PI, phi))

  const nRing = 4 * nside
  const ringFloat = phi / Math.PI * (nRing - 1)
  const ring = Math.max(0, Math.min(nRing - 1, Math.floor(ringFloat + 0.5)))

  const cellsInRing = ringCellsPerRing(ring, nside)
  const cellInRing = Math.floor(theta / (2 * Math.PI) * cellsInRing) % cellsInRing

  let globalCell = 0
  for (let r = 0; r < ring; r++) {
    globalCell += ringCellsPerRing(r, nside)
  }
  return globalCell + cellInRing
}

/**
 * Number of cells in a ring. Matches HEALPix's latitude-dependent
 * cell counts: polar rings have fewer cells, equatorial rings max out.
 */
function ringCellsPerRing(ring: number, nside: number): number {
  const nRing = 4 * nside
  const mid = nRing >> 1
  if (ring <= mid) return Math.max(4, 4 * (ring + 1))
  return Math.max(4, 4 * (nRing - ring))
}

/** Compute the radial shell from r ∈ [0, 1]. */
export function radialShell(r: number): number {
  if (r < 0.1) return 0
  if (r < 0.3) return 1
  if (r < 0.6) return 2
  return 3
}

/** nside for each shell. */
export function shellNside(shell: number): number {
  return [1, 2, 4, 8][shell]!
}

/** Spherical cell descriptor. */
export interface SphericalCell {
  shell: number
  nside: number
  ring: number
  cellInRing: number
  cell: number
}

/** Assign (r, theta, phi) to a HEALPix-like cell. */
export function assignCell(r: number, theta: number, phi: number): SphericalCell {
  const shell = radialShell(r)
  const nside = shellNside(shell)
  theta = ((theta % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)
  phi = Math.max(0, Math.min(Math.PI, phi))

  const nRing = 4 * nside
  const ring = Math.max(0, Math.min(nRing - 1,
    Math.floor(phi / Math.PI * (nRing - 1) + 0.5)))

  const cellsInRing = ringCellsPerRing(ring, nside)
  const cellInRing = Math.floor(theta / (2 * Math.PI) * cellsInRing) % cellsInRing

  let globalCell = 0
  for (let r = 0; r < ring; r++) globalCell += ringCellsPerRing(r, nside)
  globalCell += cellInRing

  return { shell, nside, ring, cellInRing, cell: globalCell }
}

/**
 * Global cell key for LMDB storage.
 * 5 bytes: [shell:1B][cell:4B big-endian] for ordered-binary sorting.
 */
export function globalCellKey(shell: number, cell: number): string {
  const buf = Buffer.alloc(5)
  buf.writeUInt8(shell, 0)
  buf.writeUInt32BE(cell, 1)
  return buf.toString('binary')
}

/** Decode a global cell key. */
export function decodeCellKey(key: string): { shell: number; cell: number } | null {
  if (key.length < 5) return null
  const buf = Buffer.from(key, 'binary')
  return { shell: buf.readUInt8(0), cell: buf.readUInt32BE(1) }
}

/**
 * Compute phi (polar angle) from the z residual coordinate.
 * z ∈ [-1, 1] maps to phi ∈ [0, π] via arccos.
 */
export function phiFromZ(z: number): number {
  const clamped = Math.max(-1, Math.min(1, Math.tanh(z * 5)))
  return Math.acos(clamped)
}

/**
 * Enumerate all cell keys intersecting an angular sector.
 *
 * @param shell    Radial shell
 * @param thetaMin Azimuthal start [0, 2π]
 * @param thetaMax Azimuthal end [0, 2π]
 * @param phiMin   Polar start [0, π]
 * @param phiMax   Polar end [0, π]
 */
export function cellsInSector(
  shell: number,
  thetaMin: number,
  thetaMax: number,
  phiMin: number,
  phiMax: number,
): string[] {
  const nside = shellNside(shell)
  const nRing = 4 * nside
  const ringMin = Math.max(0, Math.floor(phiMin / Math.PI * nRing))
  const ringMax = Math.min(nRing - 1, Math.floor(phiMax / Math.PI * nRing))

  const keys: string[] = []
  for (let ring = ringMin; ring <= ringMax; ring++) {
    const cellsInRing = ringCellsPerRing(ring, nside)
    const cellMin = Math.floor(thetaMin / (2 * Math.PI) * cellsInRing)
    const cellMax = Math.min(cellsInRing - 1,
      Math.floor(thetaMax / (2 * Math.PI) * cellsInRing))

    let globalCellBase = 0
    for (let r = 0; r < ring; r++) globalCellBase += ringCellsPerRing(r, nside)

    for (let ci = cellMin; ci <= cellMax; ci++) {
      keys.push(globalCellKey(shell, globalCellBase + (ci % cellsInRing)))
    }
  }
  return keys
}

/**
 * Get neighbor cell keys (±1 ring, ±1 cell in theta).
 * Returns unique keys including self.
 */
export function neighborCells(cell: SphericalCell): string[] {
  const { shell, nside, ring, cellInRing } = cell
  const nRing = 4 * nside
  const neighbors = new Set<string>()

  neighbors.add(globalCellKey(shell, cell.cell))

  for (const dr of [-1, 1]) {
    const nr = ring + dr
    if (nr < 0 || nr >= nRing) continue
    const oldCount = ringCellsPerRing(ring, nside)
    const newCount = ringCellsPerRing(nr, nside)
    const scaled = Math.floor(cellInRing * newCount / oldCount)
    for (const dc of [-1, 0, 1]) {
      const nc = ((scaled + dc) % newCount + newCount) % newCount
      let global = 0
      for (let r = 0; r < nr; r++) global += ringCellsPerRing(r, nside)
      neighbors.add(globalCellKey(shell, global + nc))
    }
  }

  // Same ring, ±1 in theta
  const count = ringCellsPerRing(ring, nside)
  const next = (cellInRing + 1) % count
  const prev = (cellInRing - 1 + count) % count
  let base = 0
  for (let r = 0; r < ring; r++) base += ringCellsPerRing(r, nside)
  neighbors.add(globalCellKey(shell, base + next))
  neighbors.add(globalCellKey(shell, base + prev))

  return [...neighbors]
}
