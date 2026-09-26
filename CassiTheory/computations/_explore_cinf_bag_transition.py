from __future__ import annotations
import importlib.util
from pathlib import Path
import numpy as np

source = Path(__file__).with_name("matter_formation_fermion_vacuum_bag.py")
spec = importlib.util.spec_from_file_location("bag", source)
assert spec is not None and spec.loader is not None
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def bump(s):
    if s <= 0.0: return 0.0
    if s >= 1.0: return 1.0
    a=np.exp(-1.0/s); b=np.exp(-1.0/(1.0-s)); return float(a/(a+b))

def step_matrix(U, sigma, dr, coupling, dt):
    H = m.dense_hamiltonian(sigma, dr, coupling)
    def rhs(X): return -1j * (H @ X)
    k1 = rhs(U); k2 = rhs(U + 0.5*dt*k1); k3 = rhs(U + 0.5*dt*k2); k4 = rhs(U + dt*k3)
    return U + dt*(k1+2*k2+2*k3+k4)/6
for name,(n,dr,dt0) in m.GRIDS.items():
    dt = {'G0':0.002,'G1':0.001,'G2':0.0005}[name]
    r=(np.arange(n)+.5)*dr
    h0=m.dense_hamiltonian(np.ones(n),dr,m.G_YUKAWA); e0,v0=np.linalg.eigh(h0); U=v0[:,e0<0]/np.sqrt(dr)
    target=m.V-1.5*np.exp(-.5*(r/m.WIDTH)**2); ht=m.dense_hamiltonian(target,dr,m.G_YUKAWA); et,vt=np.linalg.eigh(ht); pos=vt[:,et>0]/np.sqrt(dr); neg=vt[:,et<0]/np.sqrt(dr)
    bound=pos[:,:1]
    for j in range(round(12/dt)):
        t=(j+0.5)*dt; sig=np.ones(n)+bump(t/2.0)*(target-np.ones(n)); U=step_matrix(U,sig,dr,m.G_YUKAWA,dt)
    c=dr*(pos.conj().T@U); cb=dr*(bound.conj().T@U)
    print(name,float(np.sum(np.abs(c)**2)),float(np.sum(np.abs(cb)**2)),float(n-np.sum(np.abs(dr*(neg.conj().T@U))**2)))
