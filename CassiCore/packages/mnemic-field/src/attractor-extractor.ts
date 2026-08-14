/**
 * AttractorExtractor — V-Field V3.0 Production Implementation
 *
 * Runs fluid simulation on gateEmbed vectors from the mnemic field's
 * highest-potentiation engrams. Extracts attractors (stable concept basins)
 * and stores them as engrams for retrieval, welfare, and introspection.
 *
 * Uses the same algorithm validated in scripts/fluid-field/experiment-6b.mjs:
 *   - Cosine-similarity pairwise forces (per-neighborhood normalized)
 *   - Coriolis rotational force on precomputed semantic planes
 *   - Entropy-based adaptive viscosity
 *   - Navier-Stokes momentum integration
 */

import type { MnemicField } from './index.js';
import type { EngramCreate } from './types.js';

const STRUCTURAL_TYPES = new Set([
  'message', 'tool_invocation', 'tool', 'bridge',
  'session', 'file', 'file_version', 'file_read',
  'changeset', 'replay_segment', 'expert_summary', 'thought_command',
]);

interface Particle {
  concept: string;
  engramId: string;
  pos: Float32Array;
  vel: Float32Array;
  initPos: Float32Array;
  rotPlane: { e1: Float32Array; e2: Float32Array } | null;
  density: number;
  viscosity: number;
  re: number;
}

export interface Attractor {
  id: string;
  centroid: Float32Array;
  members: Array<{ concept: string; engramId: string }>;
  stabilityScore: number;
  meanRe: number;
  basinSize: number;
}

export interface ExtractionConfig {
  maxParticles: number;
  steps: number;
  dt: number;
  rotStrength: number;
  temperature: number;
  minPotentiation: number;
}

const DEFAULTS: ExtractionConfig = {
  maxParticles: 30,
  steps: 200,
  dt: 0.04,
  rotStrength: 0.8,
  temperature: 0.05,
  minPotentiation: 0.1,
};

function mag(v: Float32Array): number {
  let s = 0;
  for (let i = 0; i < v.length; i++) s += v[i] * v[i];
  return Math.sqrt(s);
}
function sub(a: Float32Array, b: Float32Array): Float32Array {
  const o = new Float32Array(a.length);
  for (let i = 0; i < a.length; i++) o[i] = a[i] - b[i];
  return o;
}
function dot(a: Float32Array, b: Float32Array): number {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i] * b[i];
  return s;
}
function cosine(a: Float32Array, b: Float32Array): number {
  const ma = mag(a), mb = mag(b);
  return ma < 1e-8 || mb < 1e-8 ? 0 : dot(a, b) / (ma * mb);
}
function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function precomputeRotationPlane(pos: Float32Array, neighborPos: Float32Array): { e1: Float32Array; e2: Float32Array } | null {
  const dim = pos.length;
  const e1 = new Float32Array(pos);
  const e2 = sub(neighborPos, pos);
  const m2 = mag(e2);
  if (m2 < 1e-8) return null;
  for (let i = 0; i < dim; i++) e2[i] /= m2;
  const dp = dot(e1, e2);
  for (let i = 0; i < dim; i++) e2[i] -= dp * e1[i];
  const m2n = mag(e2);
  if (m2n < 1e-8) return null;
  for (let i = 0; i < dim; i++) e2[i] /= m2n;
  return { e1, e2 };
}

function rotationalForce(gradForce: Float32Array, plane: { e1: Float32Array; e2: Float32Array }, strength: number): Float32Array {
  const d = gradForce.length;
  const p1 = dot(gradForce, plane.e1);
  const p2 = dot(gradForce, plane.e2);
  const f = new Float32Array(d);
  for (let i = 0; i < d; i++) f[i] = strength * (-p2 * plane.e1[i] + p1 * plane.e2[i]);
  return f;
}

function gaussianNoise(dim: number, std: number): Float32Array {
  const v = new Float32Array(dim);
  for (let i = 0; i < dim; i++) {
    const u1 = Math.random(), u2 = Math.random();
    v[i] = std * Math.sqrt(-2 * Math.log(u1 || 1e-8)) * Math.cos(2 * Math.PI * u2);
  }
  return v;
}

export class AttractorExtractor {
  private field: MnemicField;
  private config: ExtractionConfig;
  private particles: Map<string, Particle> = new Map();
  private lastExtractionMs: number = 0;

  constructor(field: MnemicField, config: Partial<ExtractionConfig> = {}) {
    this.field = field;
    this.config = { ...DEFAULTS, ...config };
  }

  async extract(): Promise<Attractor[]> {
    const embedder = (this.field as any)._vindexEmbedder as ((text: string) => Float32Array) | undefined;
    if (!embedder) {
      throw new Error('AttractorExtractor: no vindex embedder wired');
    }

    const cortex = this.field.getCortex();
    const allEngrams = cortex.listEngrams(this.config.maxParticles * 3);
    const topEngrams: Array<{ concept: string; engramId: string }> = [];

    for (const e of allEngrams) {
      if (STRUCTURAL_TYPES.has(e.nodeType)) continue;
      if ((e.potentiation ?? 0) < this.config.minPotentiation) continue;
      if (!e.content) continue;
      const label = typeof e.content === 'string'
        ? e.content.slice(0, 50).replace(/\n/g, ' ')
        : JSON.stringify(e.content).slice(0, 50);
      if (label.length < 3) continue;
      topEngrams.push({ concept: label, engramId: e.id });
      if (topEngrams.length >= this.config.maxParticles) break;
    }

    if (topEngrams.length < 3) return [];

    const dim = 1536;
    const newParticles: Particle[] = [];

    for (const c of topEngrams) {
      let pos: Float32Array;
      try { pos = embedder(c.concept); } catch { continue; }
      if (!pos || pos.length === 0) continue;

      const existing = this.particles.get(c.engramId);
      newParticles.push({
        concept: c.concept,
        engramId: c.engramId,
        pos: new Float32Array(pos),
        vel: existing ? new Float32Array(existing.vel) : new Float32Array(dim),
        initPos: new Float32Array(pos),
        rotPlane: null,
        density: 1,
        viscosity: 0.5,
        re: 0,
      });
      this.particles.set(c.engramId, newParticles[newParticles.length - 1]);
    }

    if (newParticles.length < 3) return [];

    for (const p of newParticles) {
      let bestIdx = -1, bestSim = -1;
      for (let j = 0; j < newParticles.length; j++) {
        if (newParticles[j] === p) continue;
        const sim = cosine(p.pos, newParticles[j].pos);
        if (sim > bestSim) { bestSim = sim; bestIdx = j; }
      }
      if (bestIdx >= 0) p.rotPlane = precomputeRotationPlane(p.pos, newParticles[bestIdx].pos);
      if (!p.rotPlane) {
        const e1 = new Float32Array(p.pos);
        const e2 = new Float32Array(dim);
        for (let i = 0; i < dim; i++) e2[i] = (i % 2 === 0 ? 1 : -1) * p.pos[(i + dim / 2) % dim];
        const d = dot(e1, e2);
        for (let i = 0; i < dim; i++) e2[i] -= d * e1[i];
        const m = mag(e2);
        for (let i = 0; i < dim; i++) e2[i] /= m;
        p.rotPlane = { e1, e2 };
      }
    }

    const { steps, dt, rotStrength, temperature } = this.config;

    for (let step = 0; step < steps; step++) {
      const nPos: Float32Array[] = [];
      const nVel: Float32Array[] = [];

      for (let i = 0; i < newParticles.length; i++) {
        const p = newParticles[i];
        const cosI: number[] = [];
        for (let j = 0; j < newParticles.length; j++) {
          cosI[j] = i === j ? 1 : cosine(p.pos, newParticles[j].pos);
        }
        const other = cosI.filter((_, j) => j !== i);
        const mn = Math.min(...other);
        const mx = Math.max(...other);
        const rng = mx - mn || 1;

        const gf = new Float32Array(dim);
        let tw = 0;
        for (let j = 0; j < newParticles.length; j++) {
          if (i === j) continue;
          const ns = (cosI[j] - mn) / rng;
          const w = ns > 0.3 ? ns * ns : -0.5 * (1 - ns);
          const d = sub(newParticles[j].pos, p.pos);
          for (let k = 0; k < dim; k++) gf[k] += w * d[k];
          tw += Math.abs(w);
        }
        if (tw > 1e-8) for (let k = 0; k < dim; k++) gf[k] /= tw;

        const rf = p.rotPlane ? rotationalForce(gf, p.rotPlane, rotStrength) : new Float32Array(dim);
        const tf = new Float32Array(dim);
        for (let k = 0; k < dim; k++) tf[k] = gf[k] + rf[k];

        let density = 0;
        for (let j = 0; j < newParticles.length; j++) {
          if (i !== j && (cosI[j] - mn) / rng > 0.5) density++;
        }
        p.density = Math.max(1, density);

        const ns4e = other.map(s => (s - mn) / rng);
        const tns = ns4e.reduce((s, v) => s + v, 0) || 1;
        let entropy = 0;
        for (const ns of ns4e) {
          const prob = ns / tns;
          if (prob > 1e-8) entropy -= prob * Math.log(prob);
        }
        p.viscosity = clamp(0.3 + 1.5 * (entropy / Math.log(ns4e.length)), 0.1, 2.0);

        const damp = Math.max(0, 1 - p.viscosity * dt);
        const noise = gaussianNoise(dim, temperature * dt);
        const nv = new Float32Array(dim);
        for (let k = 0; k < dim; k++) {
          nv[k] = damp * p.vel[k] + (dt / p.density) * (tf[k] + noise[k]);
        }
        const np = new Float32Array(dim);
        for (let k = 0; k < dim; k++) np[k] = p.pos[k] + dt * nv[k];

        p.re = mag(tf) / (p.viscosity * mag(nv) + 1e-8);
        nPos[i] = np;
        nVel[i] = nv;
      }

      for (let i = 0; i < newParticles.length; i++) {
        newParticles[i].pos = nPos[i];
        newParticles[i].vel = nVel[i];
      }
    }

    const visited = new Set<number>();
    const attractors: Attractor[] = [];

    for (let i = 0; i < newParticles.length; i++) {
      if (visited.has(i)) continue;
      const members: Particle[] = [newParticles[i]];
      visited.add(i);
      for (let j = 0; j < newParticles.length; j++) {
        if (visited.has(j)) continue;
        if (cosine(newParticles[i].pos, newParticles[j].pos) > 0.7) {
          members.push(newParticles[j]);
          visited.add(j);
        }
      }
      if (members.length < 2) continue;

      const centroid = new Float32Array(dim);
      for (const m of members) {
        for (let k = 0; k < dim; k++) centroid[k] += m.pos[k] / members.length;
      }
      const stabilityScore = members.reduce((s, m) => s + (1 / (1 + mag(m.vel))), 0) / members.length;
      const meanRe = members.reduce((s, m) => s + m.re, 0) / members.length;

      attractors.push({
        id: `attr_${Date.now()}_${attractors.length}`,
        centroid,
        members: members.map(m => ({ concept: m.concept, engramId: m.engramId })),
        stabilityScore,
        meanRe,
        basinSize: members.length,
      });
    }

    attractors.sort((a, b) => b.basinSize - a.basinSize);

    for (const attr of attractors) {
      const content = JSON.stringify({
        basinSize: attr.basinSize,
        stabilityScore: attr.stabilityScore,
        meanRe: attr.meanRe,
        memberConcepts: attr.members.map(m => m.concept),
        memberEngramIds: attr.members.map(m => m.engramId),
      });

      try {
        this.field.store({
          nodeType: 'attractor',
          content,
          initialPotentiation: 0.5,
          metadata: {
            attractorId: attr.id,
            basinSize: attr.basinSize,
            stabilityScore: attr.stabilityScore,
            meanRe: attr.meanRe,
            extractedAt: new Date().toISOString(),
          },
        } as EngramCreate);
      } catch { /* best-effort */ }
    }

    this.lastExtractionMs = Date.now();
    return attractors;
  }

  getAttractors(): Attractor[] {
    const cortex = this.field.getCortex();
    const engrams = cortex.listEngrams(50, 'attractor');
    return engrams.map(e => {
      let meta: any = {};
      try { meta = typeof e.content === 'string' ? JSON.parse(e.content) : e.content || {}; } catch { /* ignore */ }
      return {
        id: meta.attractorId || e.id,
        centroid: new Float32Array(0),
        members: (meta.memberConcepts || []).map((c: string, i: number) => ({
          concept: c,
          engramId: (meta.memberEngramIds || [])[i] || '',
        })),
        stabilityScore: meta.stabilityScore || 0,
        meanRe: meta.meanRe || 0,
        basinSize: meta.basinSize || 0,
      };
    });
  }

  getAttractor(id: string): Attractor | null {
    return this.getAttractors().find(a => a.id === id) || null;
  }

  getBasinEngramIds(attractorId: string): string[] {
    const attr = this.getAttractor(attractorId);
    if (!attr) return [];
    return attr.members.map(m => m.engramId);
  }

  get timeSinceLastExtraction(): number {
    return this.lastExtractionMs === 0 ? Infinity : Date.now() - this.lastExtractionMs;
  }
}
