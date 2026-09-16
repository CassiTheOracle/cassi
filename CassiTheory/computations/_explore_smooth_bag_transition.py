from __future__ import annotations
import importlib.util
from pathlib import Path
import numpy as np

source = Path(__file__).with_name("matter_formation_fermion_vacuum_bag.py")
spec = importlib.util.spec_from_file_location("bag", source)
assert spec is not None and spec.loader is not None
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def step_matrix(U, sigma, dr, coupling, dt):
    H = m.dense_hamiltonian(sigma, dr, coupling)
    def rhs(X): return -1j * (H @ X)
    k1 = rhs(U)
    k2 = rhs(U + 0.5 * dt * k1)
    k3 = rhs(U + 0.5 * dt * k2)
    k4 = rhs(U + dt * k3)
    return U + dt * (k1 + 2*k2 + 2*k3 + k4) / 6.0

for name,(n,dr,dt0) in m.GRIDS.items():
    dt = 0.002 if name == 'G0' else 0.001 if name == 'G1' else 0.0005
    r=(np.arange(n)+.5)*dr
    vacuum=m.dense_hamiltonian(np.ones(n),dr,m.G_YUKAWA)
    ev0,vec0=np.linalg.eigh(vacuum); neg0=vec0[:,ev0<0] / np.sqrt(dr)
    A=1.5; target=m.V-A*np.exp(-.5*(r/m.WIDTH)**2)
    htarget=m.dense_hamiltonian(target,dr,m.G_YUKAWA)
    evt,vect=np.linalg.eigh(htarget); pos=vect[:,evt>0]/np.sqrt(dr); neg=vect[:,evt<0]/np.sqrt(dr)
    # lowest positive bound state is the first positive eigenvalue
    bidx=int(np.argmin(evt[evt>0])); bound=pos[:,bidx:bidx+1]
    U=neg0.copy(); T=2.0; tf=12.0; steps=round(tf/dt)
    for j in range(steps):
        t=(j+0.5)*dt
        s=min(1.0,max(0.0,t/T))
        f=10*s**3-15*s**4+6*s**5 if 0<s<1 else (0.0 if s<=0 else 1.0)
        sigma=np.ones(n)+f*(target-np.ones(n))
        U=step_matrix(U,sigma,dr,m.G_YUKAWA,dt)
    c=dr*(pos.conj().T@U)
    nall=float(np.sum(np.abs(c)**2))
    cb=float(np.sum(np.abs(dr*(bound.conj().T@U))**2))
    hole=float(n-np.sum(np.abs(dr*(neg.conj().T@U))**2))
    print(name,'dt',dt,'nall',nall,'bound',cb,'hole',hole,'eval',evt[evt>0][:4])
