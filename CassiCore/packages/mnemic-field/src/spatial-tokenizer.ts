/**
 * SpatialPositionTokenizer — maps 3D spatial positions to token IDs
 * using the TRELLIS.2 synthetic 32³ grid.
 *
 * The TRELLIS.2 vindex was extracted with a synthetic spatial tokenizer
 * that maps a 32³ voxel grid to token IDs: tokenId = x * 32² + y * 32 + z.
 * This tokenizer provides the bidirectional mapping and validation.
 *
 * Grid dimensions: 32 × 32 × 32 = 32,768 positions
 * Token ID range: [0, 32767]
 * Each position gets a unique sinusoidal encoding in the vindex's
 * 1536-dim residual space via the input_layer projection.
 */

const GRID_SIZE = 32
const GRID_SIZE_SQ = GRID_SIZE * GRID_SIZE  // 1024
const GRID_VOLUME = GRID_SIZE * GRID_SIZE * GRID_SIZE  // 32768

export interface SpatialPosition {
  x: number
  y: number
  z: number
}

export interface SpatialPositionWithToken extends SpatialPosition {
  tokenId: number
  /** Normalized coordinates in [-1, 1] for field positioning. */
  normalized: { x: number; y: number; z: number }
}

/**
 * Map a 3D position (integer grid coordinates) to a token ID.
 * Coordinates must be in [0, 31].
 */
export function positionToTokenId(x: number, y: number, z: number): number {
  if (x < 0 || x >= GRID_SIZE || y < 0 || y >= GRID_SIZE || z < 0 || z >= GRID_SIZE) {
    throw new Error(
      `Spatial position (${x},${y},${z}) out of range [0,${GRID_SIZE - 1}]`
    )
  }
  return x * GRID_SIZE_SQ + y * GRID_SIZE + z
}

/**
 * Map a token ID back to 3D grid coordinates.
 */
export function tokenIdToPosition(tokenId: number): SpatialPosition {
  if (tokenId < 0 || tokenId >= GRID_VOLUME) {
    throw new Error(`Token ID ${tokenId} out of range [0,${GRID_VOLUME - 1}]`)
  }
  const x = Math.floor(tokenId / GRID_SIZE_SQ)
  const remainder = tokenId % GRID_SIZE_SQ
  const y = Math.floor(remainder / GRID_SIZE)
  const z = remainder % GRID_SIZE
  return { x, y, z }
}

/**
 * Normalize grid coordinates to [-1, 1] for field (r, θ, z) positioning.
 * Maps [0, 31] → [-1, 1] linearly.
 */
export function normalizePosition(pos: SpatialPosition): { x: number; y: number; z: number } {
  const scale = (v: number) => (v / (GRID_SIZE - 1)) * 2 - 1
  return { x: scale(pos.x), y: scale(pos.y), z: scale(pos.z) }
}

/**
 * Convert normalized [-1,1] coordinates back to grid coordinates [0,31].
 */
export function denormalizePosition(normalized: { x: number; y: number; z: number }): SpatialPosition {
  const scale = (v: number) => Math.round(((v + 1) / 2) * (GRID_SIZE - 1))
  return {
    x: Math.max(0, Math.min(GRID_SIZE - 1, scale(normalized.x))),
    y: Math.max(0, Math.min(GRID_SIZE - 1, scale(normalized.y))),
    z: Math.max(0, Math.min(GRID_SIZE - 1, scale(normalized.z))),
  }
}

/**
 * Convert a 3D position to a full SpatialPositionWithToken including
 * normalized coordinates for field placement.
 */
export function tokenizePosition(x: number, y: number, z: number): SpatialPositionWithToken {
  const tokenId = positionToTokenId(x, y, z)
  const normalized = normalizePosition({ x, y, z })
  return { x, y, z, tokenId, normalized }
}

/**
 * Compute (r, θ, z) field coordinates from a spatial position.
 * Projects the 3D position onto the 2D polar field used by the mnemic field.
 *
 * r = distance from origin in XY plane (normalized to [0, 1])
 * θ = angle in XY plane (radians, [-π, π])
 * z = normalized z coordinate [-1, 1]
 */
export function positionToFieldCoords(
  pos: SpatialPosition,
): { r: number; theta: number; z: number } {
  const n = normalizePosition(pos)
  // Project XY plane to polar
  const r = Math.min(1, Math.sqrt(n.x * n.x + n.y * n.y))
  const theta = Math.atan2(n.y, n.x)
  return { r, theta, z: n.z }
}

/**
 * Generate a grid of spatial positions at the given density.
 * density=1 means every position, density=2 means every other, etc.
 * Returns positions within a unit sphere (r ≤ 1) to avoid sparse corners.
 */
export function generateSpatialGrid(density: number = 1): SpatialPositionWithToken[] {
  const step = Math.max(1, Math.floor(GRID_SIZE / (GRID_SIZE / density)))
  const positions: SpatialPositionWithToken[] = []

  for (let x = 0; x < GRID_SIZE; x += step) {
    for (let y = 0; y < GRID_SIZE; y += step) {
      for (let z = 0; z < GRID_SIZE; z += step) {
        const n = normalizePosition({ x, y, z })
        // Only include positions within the unit sphere
        const r = Math.sqrt(n.x * n.x + n.y * n.y + n.z * n.z)
        if (r <= 1.0) {
          positions.push(tokenizePosition(x, y, z))
        }
      }
    }
  }

  return positions
}

export { GRID_SIZE, GRID_SIZE_SQ, GRID_VOLUME }
