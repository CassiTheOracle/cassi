/**
 * SpatialIndex — HEALPix-backed positional engram index.
 *
 * Maps engram positions to HEALPix cells for O(log cells) spatial queries.
 * Stored in LMDB under "spatial_index" — keyed by globalCellKey.
 *
 * Layers:
 *   Shell 0 (r < 0.1): Nside=1  →  12 cells
 *   Shell 1 (r < 0.3): Nside=2  →  48 cells
 *   Shell 2 (r < 0.6): Nside=4  → 192 cells
 *   Shell 3 (r ≥ 0.6): Nside=8  → 768 cells
 *   Total: 1,020 cells across 4 shells
 */

import { assignCell, globalCellKey, radialShell, shellNside, cellsInSector, neighborCells } from './healpix.js';

interface EngramPosition {
  engramId: string;
  r: number;
  theta: number;
  z: number;
  potentiation: number;
  nodeType: string;
  /** First 100 chars of content for display. */
  contentPreview: string;
}

interface CellEntry {
  engrams: EngramPosition[];
}

export class SpatialIndex {
  private db: any = null;
  private env: any = null;

  constructor(env?: any, dbName: string = 'spatial_index') {
    if (env) {
      this.env = env;
      this.db = env.openDB?.(dbName) ?? null;
    }
  }

  setEnv(env: any): void {
    this.env = env;
    this.db = env.openDB?.('spatial_index') ?? null;
  }

  get ready(): boolean {
    return this.db !== null && this.env !== null;
  }

  /** Index an engram at its position. */
  indexEngram(pos: EngramPosition): void {
    if (!this.db) return;
    const phi = phiFromZ(pos.z);
    const cell = assignCell(pos.r, pos.theta, phi);
    const key = globalCellKey(cell.shell, cell.cell);

    const entry = this.readCell(key);
    const existing = entry.engrams.findIndex(e => e.engramId === pos.engramId);
    if (existing >= 0) {
      entry.engrams[existing] = pos;
    } else {
      entry.engrams.push(pos);
    }
    this.writeCell(key, entry);
  }

  /** Remove an engram from the spatial index. */
  removeEngram(engramId: string, r: number, theta: number, z: number): void {
    if (!this.db) return;
    const phi = phiFromZ(z);
    const cell = assignCell(r, theta, phi);
    const key = globalCellKey(cell.shell, cell.cell);

    const entry = this.readCell(key);
    entry.engrams = entry.engrams.filter(e => e.engramId !== engramId);
    this.writeCell(key, entry);
  }

  /** Query engrams within a cylindrical region. */
  queryRegion(
    r: number,
    theta: number,
    z: number,
    radius: number,
    options?: { maxResults?: number; minPotentiation?: number },
  ): EngramPosition[] {
    if (!this.db) return [];
    const phi = phiFromZ(z);
    const maxResults = options?.maxResults ?? 50;
    const minPot = options?.minPotentiation ?? 0;

    // Determine which shells to search based on r ± radius
    const rMin = Math.max(0, r - radius);
    const rMax = Math.min(1, r + radius);
    const shellMin = radialShell(rMin);
    const shellMax = radialShell(rMax);

    // Angular bounds
    const thetaWidth = radius / Math.max(r, 0.05); // arc length approx
    const thetaMin = ((theta - thetaWidth) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
    const thetaMax = ((theta + thetaWidth) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
    const phiMin = Math.max(0, phi - thetaWidth);
    const phiMax = Math.min(Math.PI, phi + thetaWidth);

    const results: Array<EngramPosition & { _dist: number }> = [];
    const seen = new Set<string>();

    for (let shell = shellMin; shell <= shellMax; shell++) {
      const keys = cellsInSector(shell, thetaMin, thetaMax, phiMin, phiMax);
      for (const key of keys) {
        const entry = this.readCell(key);
        for (const e of entry.engrams) {
          if (seen.has(e.engramId)) continue;
          if (e.potentiation < minPot) continue;
          const dist = cylindricalDistance(r, theta, z, e.r, e.theta, e.z);
          if (dist <= radius) {
            seen.add(e.engramId);
            results.push({ ...e, _dist: dist });
          }
        }
      }
    }

    results.sort((a, b) => a._dist - b._dist);

    return results.slice(0, maxResults).map(({ _dist, ...e }) => e);
  }

  /** List engrams in a specific HEALPix cell. */
  queryCell(shell: number, cell: number): EngramPosition[] {
    if (!this.db) return [];
    const key = globalCellKey(shell, cell);
    const entry = this.readCell(key);
    return entry.engrams.sort((a, b) => b.potentiation - a.potentiation);
  }

  /** List engrams in a cell and its neighbors. */
  queryCellNeighbors(shell: number, cell: number): EngramPosition[] {
    if (!this.db) return [];
    const dummy: any = { shell, nside: shellNside(shell), ring: 0, cellInRing: 0, cell };
    const keys = neighborCells(dummy);
    const results: EngramPosition[] = [];
    const seen = new Set<string>();
    for (const key of keys) {
      const entry = this.readCell(key);
      for (const e of entry.engrams) {
        if (!seen.has(e.engramId)) {
          seen.add(e.engramId);
          results.push(e);
        }
      }
    }
    return results.sort((a, b) => b.potentiation - a.potentiation);
  }

  /** Get stats about the spatial index. */
  stats(): { totalCells: number; totalEngrams: number; shells: Record<number, { cells: number; engrams: number }> } {
    const shells: Record<number, { cells: number; engrams: number }> = { 0: { cells: 0, engrams: 0 }, 1: { cells: 0, engrams: 0 }, 2: { cells: 0, engrams: 0 }, 3: { cells: 0, engrams: 0 } };
    let totalCells = 0, totalEngrams = 0;

    if (this.db) {
      for (let shell = 0; shell <= 3; shell++) {
        const nside = shellNside(shell);
        const nRing = 4 * nside;
        for (let ring = 0; ring < nRing; ring++) {
          const cellsInRing = ringCellsPerRing(ring, nside);
          let base = 0;
          for (let r = 0; r < ring; r++) base += ringCellsPerRing(r, nside);
          for (let ci = 0; ci < cellsInRing; ci++) {
            const key = globalCellKey(shell, base + ci);
            const entry = this.readCell(key);
            if (entry.engrams.length > 0) {
              shells[shell]!.cells++;
              shells[shell]!.engrams += entry.engrams.length;
            }
          }
        }
        totalCells += shells[shell]!.cells;
        totalEngrams += shells[shell]!.engrams;
      }
    }

    return { totalCells, totalEngrams, shells };
  }

  private readCell(key: string): CellEntry {
    if (!this.db) return { engrams: [] };
    try {
      const raw = (this.db as any).get?.(key) as Buffer | null;
      if (raw && raw.length > 0) {
        return JSON.parse(raw.toString('utf-8'));
      }
    } catch { /* ignore corrupt entry */ }
    return { engrams: [] };
  }

  private writeCell(key: string, entry: CellEntry): void {
    if (!this.db) return;
    try {
      (this.db as any).put?.(key, Buffer.from(JSON.stringify(entry), 'utf-8'));
    } catch { /* best-effort */ }
  }
}

// Re-export these so kindling.ts can use them
export { globalCellKey, assignCell, radialShell, shellNside, cellsInSector, neighborCells };

/** Compute phi (polar angle) from z coordinate. */
function phiFromZ(z: number): number {
  const clamped = Math.max(-1, Math.min(1, Math.tanh(z * 5)));
  return Math.acos(clamped);
}

function ringCellsPerRing(ring: number, nside: number): number {
  const nRing = 4 * nside;
  const mid = nRing >> 1;
  if (ring <= mid) return Math.max(4, 4 * (ring + 1));
  return Math.max(4, 4 * (nRing - ring));
}

/** Cylindrical distance in (r, theta, z). */
export function cylindricalDistance(
  r1: number, theta1: number, z1: number,
  r2: number, theta2: number, z2: number,
): number {
  const dr = r1 - r2;
  const dz = z1 - z2;
  const dt = Math.abs(theta1 - theta2);
  const dtheta = Math.min(dt, 2 * Math.PI - dt);
  const arcLength = ((r1 + r2) / 2) * dtheta;
  return Math.sqrt(dr * dr + dz * dz + arcLength * arcLength);
}

/** Maximum engrams scanned per spatial region query. */
export const MAX_SPATIAL_ENGRAMS = 500;
