import { homedir } from 'node:os';
import path from 'node:path';

/**
 * CassiCore PathManager
 * Centralizes all path resolution to prevent architectural drift
 */
export class PathManager {
  static get home() {
    return process.env.HOME || homedir();
  }

  static get cassiRoot() {
    return process.env.CASSI_WORKSPACE_DIR || path.join(this.home, '.cassi');
  }

  static get coreRoot() {
    return process.env.CASSI_CORE_DIR || path.join(this.home, '.cassicore');
  }

  static get memory() {
    return path.join(this.cassiRoot, 'memory');
  }

  static get data() {
    return path.join(this.coreRoot, 'data');
  }

  static get autoMemory() {
    return path.join(this.data, 'memory', 'automatic');
  }

  static resolve(relativePath: string, root: 'cassi' | 'core' = 'core') {
    const base = root === 'cassi' ? this.cassiRoot : this.coreRoot;
    return path.join(base, relativePath);
  }
}
