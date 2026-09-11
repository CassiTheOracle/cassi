#!/usr/bin/env python3
"""Frozen loop-carrying exterior (bowtie) Yang--Mills fibre protocol.

The graph, schedule, observables, thresholds, verdict vocabulary and stopping
rule below are copied from ``yang-mills-bowtie-fibre-prereg.md``.  All Haar
integrals are SU(2) Clebsch--Gordan contractions; no sampling or quadrature is
used.
"""
from __future__ import annotations
import hashlib, importlib.util, json, math, string, tempfile, time
from fractions import Fraction
from itertools import product as cartesian_product
from pathlib import Path

import numpy as np
from scipy.linalg import eigh

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-bowtie-fibre-prereg.md"
SOURCE = Path(__file__).resolve()
ALGEBRA = ROOT / "computations" / "yang_mills_conditional_algebra.py"
REFERENCE = ROOT / "computations" / "verify_yang_mills_exact_block_spectrum.py"
OUT = ROOT / "runs" / "yang_mills_bowtie_fibre" / "verification.json"

# Frozen literals: protocol §§2--7.
CUTOFFS = (1, 2, 3)
COUPLINGS = (Fraction(1, 4), Fraction(1), Fraction(4), Fraction(16))
BOUNDARY_ANGLES = tuple(Fraction(k, 8) for k in range(9))
ORBIT_THRESHOLD = 1.0e-8
UNIFORM_RATIO = 0.5
NONUNIFORM_RATIO = 0.25
COLLAPSE_THRESHOLD = 1.0e-3
FULL_RESIDUAL_MAX = 1.0e-2
BLOCK_LINKS = (0, 1, 2, 3)
EXTERIOR_LINKS = (4, 5, 6, 7)
ALL_LINKS = tuple(range(8))
LINK_TAILS = (0, 1, 3, 0, 0, 4, 6, 0)
LINK_HEADS = (1, 2, 2, 3, 4, 5, 5, 6)
PLAQUETTES = (
    ((0, +1), (1, +1), (2, -1), (3, -1)),
    ((4, +1), (5, +1), (6, -1), (7, -1)),
)

# Import the §27 exact representation engine without copying or modifying it.
spec = importlib.util.spec_from_file_location("ym_reference", REFERENCE)
assert spec and spec.loader
ym = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ym)


def four_intertwiner(a: int, b: int, q: int) -> np.ndarray:
    """Unit-norm invariant in V_a⊗V_a⊗V_b⊗V_b, paired through channel q."""
    if q < 0 or q > min(a, b):
        raise ValueError("invalid four-valent channel")
    ta = 2 * q
    ca, ja = ym.cg_fusion(a, a)
    cb, jb = ym.cg_fusion(b, b)
    pa = np.flatnonzero(ja == ta)
    pb = np.flatnonzero(jb == ta)
    if pa.size != ta + 1 or pb.size != ta + 1:
        raise ValueError("missing channel")
    ca = ca[:, :, pa]
    cb = cb[:, :, pb]
    # The CG channel has norm squared d_q; divide by sqrt(d_q) so each
    # four-valent intertwiner is orthonormal in the declared channel basis.
    g = ym.metric_tensor(ta)
    return np.einsum("ijm,kln,mn->ijkl", ca, cb, g, optimize=True) / math.sqrt(ta + 1)


class BowtieCopy:
    """One spin-network copy with a four-valent vertex at 0."""
    def __init__(self, net: Any, a_spins: Sequence[int], b_spins: Sequence[int],
                 channel: int | None, prefix: str) -> None:
        self.net, self.prefix, self.overrides = net, prefix, {}
        self.a_spins, self.b_spins = tuple(a_spins), tuple(b_spins)
        self.la_m = net.label(f"{prefix}am", a_spins); self.la_n = net.label(f"{prefix}an", a_spins)
        self.lb_m = {e: net.label(f"{prefix}bm{e}", a_spins) for e in (1,2,3)}
        self.lb_n = {e: net.label(f"{prefix}bn{e}", a_spins) for e in (1,2,3)}
        self.be_m = {e: net.label(f"{prefix}em{e}", b_spins) for e in (4,5,6)}
        self.be_n = {e: net.label(f"{prefix}en{e}", b_spins) for e in (4,5,6)}
        self.l7_m = net.label(f"{prefix}7m", b_spins); self.l7_n = net.label(f"{prefix}7n", b_spins)
        if channel is not None:
            if len(a_spins) != len(b_spins) or len(a_spins) != 1:
                raise ValueError("simple copy requires one block and exterior spin")
            tensor = four_intertwiner(a_spins[0], b_spins[0], channel)
            net.add(tensor, (self.la_m, self.lb_m[3], self.be_m[4], self.l7_m))
        else:
            # Filled by add_omega_vertex for direct sums.
            pass
        self.channel = channel

    def add_omega_vertex(self, coefficients: dict[tuple[int,int,int], complex]) -> None:
        spins_a = tuple(sorted({s[0] for s in coefficients}))
        spins_b = tuple(sorted({s[1] for s in coefficients}))
        # labels created by constructor have these direct-sum blocks.
        t0 = np.zeros((self.la_m.size, self.lb_m[3].size, self.be_m[4].size, self.l7_m.size), dtype=complex)
        offs_a = {s:o for s,o in zip(spins_a, self.la_m.offsets)}
        offs_b = {s:o for s,o in zip(spins_b, self.be_m[4].offsets)}
        for (a,b,q), coeff in coefficients.items():
            block = four_intertwiner(a,b,q)
            sa, sb = a+1, b+1
            sl = (slice(offs_a[a],offs_a[a]+sa), slice(offs_a[a],offs_a[a]+sa),
                  slice(offs_b[b],offs_b[b]+sb), slice(offs_b[b],offs_b[b]+sb))
            t0[sl] = coeff * block
        self.net.add(t0, (self.la_m, self.lb_m[3], self.be_m[4], self.l7_m))

    def add_chain_nodes(self, generator: int | None=None, generator_link: int | None=None, conjugated: bool=False) -> None:
        n = self.net
        t1=ym.block_diagonal(self.la_n, ym._identity_builder)
        if generator is not None and generator_link==1:
            t1=_transform_axis(t1,self.lb_m[1],generator,conjugated,1)
        n.add(t1, (self.la_n, self.lb_m[1]))
        n.add(ym.block_diagonal(self.lb_n[1], ym.metric_tensor), (self.lb_n[1], self.lb_n[2]))
        t3=ym.block_diagonal(self.lb_m[2], ym._identity_builder)
        if generator is not None and generator_link==2:
            t3=_transform_axis(t3,self.lb_m[2],generator,conjugated,0)
        n.add(t3, (self.lb_m[2], self.lb_n[3]))
        n.add(ym.block_diagonal(self.be_n[4], ym._identity_builder), (self.be_n[4], self.be_m[5]))
        n.add(ym.block_diagonal(self.be_n[5], ym.metric_tensor), (self.be_n[5], self.be_n[6]))
        n.add(ym.block_diagonal(self.be_m[6], ym._identity_builder), (self.be_m[6], self.l7_n))

    def add_generator(self, link: int, component: int, conjugated: bool=False) -> None:
        m, _ = self.factors()[link]
        table = np.zeros((m.size, m.size), dtype=complex)
        for spin, off in zip(m.spins, m.offsets):
            g = 1j * ym.generator_matrix(spin, component)
            table[off:off+spin+1, off:off+spin+1] = np.conj(g.T) if conjugated else g.T
        new = self.net.label(f"{self.prefix}g{link}", m.spins)
        self.net.add(table, (new, m)); self.overrides[link] = new

    def factors(self) -> dict[int, tuple[Any,Any]]:
        raw = {0:(self.la_m,self.la_n), 1:(self.lb_m[1],self.lb_n[1]), 2:(self.lb_m[2],self.lb_n[2]),
               3:(self.lb_m[3],self.lb_n[3]), 4:(self.be_m[4],self.be_n[4]), 5:(self.be_m[5],self.be_n[5]),
               6:(self.be_m[6],self.be_n[6]), 7:(self.l7_m,self.l7_n)}
        return {e:(self.overrides.get(e,p[0]),p[1]) for e,p in raw.items()}


class BatchCopy(BowtieCopy):
    """Direct-sum test copy with one open state-index axis."""
    def __init__(self, net: Any, test_states: Sequence[tuple[int,int,int]], prefix: str,
                 generator: int | None=None, generator_link: int | None=None, conjugated: bool=False):
        self.test_states=tuple(test_states)
        aa=tuple(sorted({s[0] for s in self.test_states})); bb=tuple(sorted({s[1] for s in self.test_states}))
        super().__init__(net,aa,bb,None,prefix)
        self.r_axis=net.label(f"{prefix}R",(len(self.test_states)-1,))
        t0=np.zeros((self.la_m.size,self.lb_m[3].size,self.be_m[4].size,self.l7_m.size,self.r_axis.size),complex)
        offa={s:o for s,o in zip(aa,self.la_m.offsets)}; offb={s:o for s,o in zip(bb,self.be_m[4].offsets)}
        for r,(a,b,q) in enumerate(self.test_states):
            block=four_intertwiner(a,b,q); sa,sb=a+1,b+1
            sl=(slice(offa[a],offa[a]+sa),slice(offa[a],offa[a]+sa),
                slice(offb[b],offb[b]+sb),slice(offb[b],offb[b]+sb),r)
            t0[sl]=block
        if generator is not None and generator_link in (0,3):
            t0=_transform_axis(t0,self.la_m if generator_link==0 else self.lb_m[3],generator,conjugated,
                               0 if generator_link==0 else 1)
        net.add(t0,(self.la_m,self.lb_m[3],self.be_m[4],self.l7_m,self.r_axis))
        self.add_chain_nodes(generator,generator_link,conjugated)


def _transform_axis(tensor: np.ndarray, label: Any, component: int, conjugated: bool, axis: int) -> np.ndarray:
    mat=np.zeros((label.size,label.size),complex)
    for spin,off in zip(label.spins,label.offsets):
        g=1j*ym.generator_matrix(spin,component)
        mat[off:off+spin+1,off:off+spin+1]=np.conj(g.T) if conjugated else g.T
    out=np.tensordot(mat,tensor,axes=(1,axis))
    return np.moveaxis(out,0,axis)

def add_bowtie_copy(net: Any, state: tuple[int,int,int], prefix: str) -> BowtieCopy:
    a,b,q = state
    c = BowtieCopy(net, (a,), (b,), q, prefix)
    c.add_chain_nodes(); return c


def add_bowtie_omega(net: Any, coefficients: dict[tuple[int,int,int],float], prefix: str) -> BowtieCopy:
    aa = tuple(sorted({s[0] for s in coefficients})); bb = tuple(sorted({s[1] for s in coefficients}))
    c = BowtieCopy(net, aa, bb, None, prefix); c.add_omega_vertex(coefficients); c.add_chain_nodes(); return c
def add_batch_copy(net: Any, test_states: Sequence[tuple[int,int,int]], prefix: str, generator: int | None=None, generator_link: int | None=None, conjugated: bool=False) -> BatchCopy:
    return BatchCopy(net,test_states,prefix,generator,generator_link,conjugated)

def loop_factors(net: Any, plaquette: int, tag: str, dagger: bool=False) -> dict[int,tuple[Any,Any,bool]]:
    labs = [net.label(f"{tag}l{k}",(1,)) for k in range(4)]
    out = {}
    for k,(e,ori) in enumerate(PLAQUETTES[plaquette]):
        x,y = labs[k], labs[(k+1)%4]
        if ori > 0: out[e]=(x,y,False != dagger)
        else: out[e]=(y,x,True != dagger)
    return out


def fixed_tables(matrices: dict[int,np.ndarray]) -> dict[int,tuple[Callable[[int],np.ndarray],Callable[[int],np.ndarray]]]:
    # Matrices are defining-representation SU(2) elements; build every
    # higher-spin block with the exact representation map.
    return {e: (lambda s, m=m: ym.rep_matrix(s,m), lambda s: np.zeros((s+1,s+1),complex)) for e,m in matrices.items()}


def z_boundary(theta: float) -> dict[int,tuple[Callable[[int],np.ndarray],Callable[[int],np.ndarray]]]:
    I = np.eye(2, dtype=complex)
    return fixed_tables({4:I,5:I,6:I,7:ym.z_rotation_matrix(1,theta)})


def assemble(coefficients: dict[tuple[int,int,int],complex], specs: Sequence[tuple[str,Any,bool,int|None,Sequence[int]]],
             integrated: Sequence[int], fixed: dict[int,tuple[Callable[[int],np.ndarray],Callable[[int],np.ndarray]]] | None,
             loops: Sequence[Any]=(), label: str="I", open_axes: bool=False) -> Any:
    net = ym.Network(); copies=[]; opened=[]
    for k,(kind,state,conj,gen,genlinks) in enumerate(specs):
        if kind=="omega": c=add_bowtie_omega(net,coefficients,f"{label}C{k}")
        elif kind=="combo": c=add_bowtie_omega(net,state,f"{label}C{k}")
        elif kind=="batch":
            link=genlinks[0] if gen is not None and genlinks else None
            c=add_batch_copy(net,state,f"{label}C{k}",gen,link,conj); opened.append(c.r_axis); gen=None
        else: c=add_bowtie_copy(net,state,f"{label}C{k}")
        if gen is not None:
            for e in genlinks: c.add_generator(e,gen,conj)
        copies.append((conj,c))
    lf={}
    for p in loops:
        if isinstance(p,(tuple,list)): pi,d=p
        else: pi,d=p,False
        for e,f in loop_factors(net,int(pi),f"{label}P{pi}{e if False else ''}",bool(d)).items(): lf.setdefault(e,[]).append(f)
    ints=set(integrated)
    for e in ALL_LINKS:
        factors=[]
        for conj,c in copies:
            m,n=c.factors()[e]; factors.append((m,n,conj))
        factors.extend(lf.get(e,()))
        if e in ints:
            ym.link_integral(net,factors,f"{label}L{e}")
        else:
            if fixed is None: raise ValueError("fixed matrices required")
            val,der=fixed[e]
            for conj,c in copies:
                m,n=c.factors()[e]; b=val
                if conj: b=lambda s,base=b: np.conj(base(s))
                net.add(ym.block_diagonal(m,b),(m,n))
            for m,n,conj in lf.get(e,()):
                b=val
                if conj: b=lambda s,base=b: np.conj(base(s))
                net.add(ym.block_diagonal(m,b),(m,n))
    return net.contract(tuple(opened)) if open_axes else complex(net.contract())


def states(cutoff:int) -> list[tuple[int,int,int]]:
    return [(a,b,q) for a in range(cutoff+1) for b in range(cutoff+1) for q in range(min(a,b)+1)]


def casimir(n2:int)->float:
    j=n2/2; return j*(j+1)


def norm_expected(s): return 1.0/((s[0]+1)*(s[1]+1))


def overlap(left,right,loops=()):
    return assemble({},[("state",left,True,None,BLOCK_LINKS),("state",right,False,None,BLOCK_LINKS)],ALL_LINKS,None,loops,"O")


class Space:
    def __init__(self,J:int):
        self.cutoff=J; self.states=states(J); self.index={s:i for i,s in enumerate(self.states)}; n=len(self.states)
        self.overlap=np.diag([norm_expected(s) for s in self.states]); self.kinetic=np.array([4*casimir(s[0])+4*casimir(s[1]) for s in self.states])
        self.plaquette=np.zeros((n,n))
        for i,s in enumerate(self.states):
            for j,t in enumerate(self.states):
                if s[1]==t[1] and abs(s[0]-t[0])==1:
                    self.plaquette[i,j]+=float(np.real(overlap(s,t,loops=(0,))))
                if s[0]==t[0] and abs(s[1]-t[1])==1:
                    self.plaquette[i,j]+=float(np.real(overlap(s,t,loops=(1,))))
        self.hermiticity_residual=float(np.max(np.abs(self.plaquette-self.plaquette.T)))
    def hamiltonian(self,x): return np.diag((self.kinetic+4*float(x))*np.diag(self.overlap))-float(x)*self.plaquette


def ritz(space:Space,x,extended:Space):
    H=space.hamiltonian(x); S=space.overlap; vals,vec=eigh(H,S); v=np.array(vec[:,0]);
    if v[np.flatnonzero(abs(v)>1e-14)[0]]<0:v=-v
    v/=math.sqrt(float(v@S@v)); E=float(vals[0]); rp=float(np.linalg.norm((H-E*S)@v/np.sqrt(np.diag(S))))
    emb=np.zeros(len(extended.states));
    for i,s in enumerate(space.states): emb[extended.index[s]]=v[i]
    rr=(extended.hamiltonian(x)-E*extended.overlap)@emb
    return {"energy_ground":E,"energy_first_excited":float(vals[1]),"projected_residual":rp,"full_residual":float(np.linalg.norm(rr/np.sqrt(np.diag(extended.overlap)))),"vector":v.tolist(),"basis_dimension":len(space.states)}


_RESTRICTION_CACHE: dict[tuple[tuple[tuple[int,int,int],...], str], np.ndarray] = {}


def restriction_gram(theta: float, tests: Sequence[tuple[int,int,int]]) -> np.ndarray:
    key = (tuple(tests), f"{theta:.17g}")
    if key in _RESTRICTION_CACHE:
        return _RESTRICTION_CACHE[key].copy()
    fixed = z_boundary(theta); n = len(tests); H = np.zeros((n,n), complex)
    for i,a in enumerate(tests):
        for j,b in enumerate(tests):
            H[i,j] = assemble({}, [("state",a,True,None,BLOCK_LINKS),("state",b,False,None,BLOCK_LINKS)],
                               BLOCK_LINKS, fixed, label="R")
    _RESTRICTION_CACHE[key] = H.copy()
    return H


def restriction_frame(H: np.ndarray, tests: Sequence[tuple[int,int,int]]) -> tuple[np.ndarray,np.ndarray,np.ndarray,int,int]:
    w,V=eigh(H); keep=w>1e-10*max(float(np.max(abs(w))),1.0); rank=int(np.sum(keep))
    M=V[:,keep]/np.sqrt(w[keep]); k=tests.index((0,0,0))
    c=(np.sqrt(w[keep])*np.conj(V[k,keep])).astype(complex); cn=float(np.linalg.norm(c))
    if cn: c/=cn
    P=np.eye(rank)-np.outer(c,c.conj()) if cn else np.eye(rank)
    U,s,_=np.linalg.svd(P,full_matrices=False); B=U[:,s>1e-8]
    return M@B,w,B,rank,(1 if cn else 0)


def restricted_coefficient(state: tuple[int,int,int], theta: float) -> np.ndarray:
    a,b,q=state; I=four_intertwiner(a,b,q); g=ym.metric_tensor(b)
    z=np.diag(ym.z_rotation_matrix(b,theta))
    R=np.einsum("ijkl,kl,l->ij",I,g,z,optimize=True)
    eye=np.eye(a+1); ga=ym.metric_tensor(a)
    return np.einsum("ab,cd,ef,gh->abcdefgh",R,eye,ga,eye,optimize=True)


def conjugate_coefficient(C: np.ndarray, spin: int) -> np.ndarray:
    K=ym.block_conjugation(ym.Label("K",(spin,)))
    out=C
    for e in range(4):
        out=np.tensordot(K,out,axes=([2,3],[2*e,2*e+1]))
        out=np.moveaxis(out,(0,1),(2*e,2*e+1))
    return out


def product_coefficient(C1: np.ndarray, a: int, C2: np.ndarray, c: int) -> dict[tuple[int,int,int,int],np.ndarray]:
    out={}
    letters=string.ascii_letters
    for rs in cartesian_product(*[tuple(range(abs(a-c),a+c+1,2))]*4):
        operands=[C1,C2]; subs1=letters[:8]; subs2=letters[8:16]; outs=[]
        pieces=[]
        for e,r in enumerate(rs):
            cg,jb=ym.cg_fusion(a,c); pos=np.flatnonzero(jb==r)
            cr=cg[:,:,pos]
            rr,cc=letters[16+2*e:18+2*e]
            operands.extend([cr,cr])
            pieces.extend([subs1[2*e]+subs2[2*e]+rr,subs1[2*e+1]+subs2[2*e+1]+cc])
            outs.extend([rr,cc])
        spec=",".join([subs1,subs2,*pieces])+"->"+"".join(outs)
        out[rs]=np.einsum(spec,*operands,optimize=True)
    return out


def coefficient_inner(left: dict, right: dict) -> complex:
    value=0j
    for key,A in left.items():
        B=right.get(key)
        if B is not None:
            value += np.vdot(A,B)/float(np.prod([r+1 for r in key]))
    return value


def derivative_coefficient(C: np.ndarray, spin: int, component: int, link: int, conjugated: bool=False) -> np.ndarray:
    g=1j*ym.generator_matrix(spin,component)
    mat=np.conj(g.T) if conjugated else g.T
    out=np.tensordot(mat,C,axes=(1,2*link)); return np.moveaxis(out,0,2*link)
def mode_matrix(state,theta):
    a,b,q=state; I=four_intertwiner(a,b,q); ga=ym.metric_tensor(a); gb=ym.metric_tensor(b)
    out=np.zeros((a+1,a+1),complex); vals=ym.magnetic_values(b)
    for k in vals:
        ie=(-int(k)+b)//2; il=(int(k)+b)//2
        K=I[:,:,ie,il]*gb[ie,il]
        out += np.exp(0.5j*float(k)*theta) * (ga @ K.T)
    return out.T


def mode_conjugate(A,spin):
    vals=ym.magnetic_values(spin); out=np.zeros_like(A,dtype=complex)
    for i,m in enumerate(vals):
      for j,n in enumerate(vals):
        out[( -int(m)+spin)//2,(-int(n)+spin)//2] += ((-1.0)**((int(m)-int(n))//2))*np.conj(A[i,j])
    return out


def mode_product(A,a,B,c):
    out={}
    cg,jb=ym.cg_fusion(a,c)
    for J in sorted(set(int(x) for x in jb)):
        pos=np.flatnonzero(jb==J); cr=cg[:,:,pos]
        out[J]=np.einsum("mn,uv,muM,nvN->MN",A,B,cr,cr,optimize=True)
    return out


def mode_inner(left,right):
    return sum(np.vdot(A,right[J])/(J+1) for J,A in left.items() if J in right)


def cond_data(coeff,theta,tests):
    n=len(tests); modes={s:mode_matrix(s,theta) for s in tests}
    H=np.zeros((n,n),complex)
    for i,s in enumerate(tests):
      for j,t in enumerate(tests):
        if s[0]==t[0]: H[i,j]=np.vdot(modes[s],modes[t])/(s[0]+1)
    Q,w,B,rank,removed=restriction_frame(H,tests)
    omega={}
    for s,v in coeff.items(): omega[s[0]]=omega.get(s[0],0)+float(v)*modes[s]
    Z=float(np.real(mode_inner(omega,omega)))
    G=np.zeros((n,n),complex); D=np.zeros((n,n),complex); mean=np.zeros(n,complex)
    for i,s in enumerate(tests):
      prod_i={}
      deriv_i=[{} for _ in range(6)]
      for u,v in coeff.items():
        for J,A in mode_product(modes[u],u[0],modes[s],s[0]).items():
          prod_i[J]=prod_i.get(J,0)+float(v)*A
        for typ in (0,1):
          for Acomp in range(3):
            Gm=1j*ym.generator_matrix(s[0],Acomp)
            dm=Gm.T@modes[s] if typ==0 else -modes[s]@Gm.T
            idx=typ*3+Acomp
            for J,A in mode_product(modes[u],u[0],dm,s[0]).items():
              deriv_i[idx][J]=deriv_i[idx].get(J,0)+float(v)*A
      mean[i]=mode_inner(omega,prod_i)/Z
      for j,t in enumerate(tests):
        prod_j={}; deriv_j=[{} for _ in range(6)]
        for u,v in coeff.items():
          for J,A in mode_product(modes[u],u[0],modes[t],t[0]).items():
            prod_j[J]=prod_j.get(J,0)+float(v)*A
          for typ in (0,1):
            for Acomp in range(3):
              Gm=1j*ym.generator_matrix(t[0],Acomp)
              dm=Gm.T@modes[t] if typ==0 else -modes[t]@Gm.T
              idx=typ*3+Acomp
              for J,A in mode_product(modes[u],u[0],dm,t[0]).items():
                deriv_j[idx][J]=deriv_j[idx].get(J,0)+float(v)*A
        G[i,j]=mode_inner(prod_i,prod_j)/Z
        for idx in range(6): D[i,j]+=2*mode_inner(deriv_i[idx],deriv_j[idx])/Z
    C=G-np.outer(np.conj(mean),mean)
    return {"partition":Z,"restriction_gram":H,"gram":G,"covariance":C,"dirichlet":D,
            "gram_eigenvalues":w,"restriction_rank":rank,"retained_dimension":int(Q.shape[1]),
            "removed_constant_dimension":removed,"frame_M":Q}



def retained(data,tests):
    H=data["restriction_gram"]; w,V=eigh(H); keep=w>1e-10*max(float(np.max(abs(w))),1.0); rank=int(np.sum(keep))
    G0=data["gram"]; C0=data["covariance"]; D0=data["dirichlet"]
    M=V[:,keep]/np.sqrt(w[keep]); k=tests.index((0,0,0)); c=np.sqrt(w[keep])*np.conj(V[k,keep]); cn=float(np.linalg.norm(c))
    if cn: c/=cn
    P=np.eye(rank)-np.outer(c,c.conj()) if cn else np.eye(rank); U,s,_=np.linalg.svd(P,full_matrices=False); B=U[:,s>1e-8]
    C=B.conj().T@M.conj().T@C0@M@B; D=B.conj().T@M.conj().T@D0@M@B
    if C.shape[0]: vals,vec=eigh(D,C); rate=float(vals[0]); res=float(np.linalg.norm(D@vec[:,0]-rate*C@vec[:,0]))
    else: rate=0.0; res=0.0
    return {"rate":rate,"rate_residual":res,"restriction_rank":rank,"retained_dimension":int(B.shape[1]),
            "removed_constant_dimension":1 if cn else 0,"gram_eigenvalues":w.tolist(),"gram":G0,
            "restriction_gram":H,"covariance":C0,"dirichlet":D0}


def arr_hash(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def matrix_record(a):
    a=np.asarray(a); r={"shape":list(a.shape),"dtype":str(a.dtype),"sha256":arr_hash(a)}
    r.update({"real":a.real.tolist(),"imag":a.imag.tolist()} if np.iscomplexobj(a) else {"values":a.tolist()}); return r


def gauge_control(space,coeff):
    from scipy.linalg import expm
    g=expm(1j*0.371*sum(ym.rep_matrices(1)[a]*([0.3,0.4,0.5][a]) for a in range(3)))
    base={4:np.eye(2),5:np.eye(2),6:np.eye(2),7:ym.z_rotation_matrix(1,0.0)}
    trans=dict(base); trans[4]=g@base[4]; trans[7]=g@base[7]
    def run(fixed):
      Z=assemble(coeff,[("omega",None,False,None,BLOCK_LINKS),("omega",None,True,None,BLOCK_LINKS)],BLOCK_LINKS,fixed,label="GCZ").real
      n=len(space.states); G=np.zeros((n,n),complex); D=np.zeros_like(G); H=np.zeros_like(G); mean=np.zeros(n,complex)
      for i,a in enumerate(space.states):
       mean[i]=assemble(coeff,[("omega",None,False,None,BLOCK_LINKS),("omega",None,True,None,BLOCK_LINKS),("state",a,False,None,BLOCK_LINKS)],BLOCK_LINKS,fixed,label="GCM")/Z
       for j,b in enumerate(space.states):
        H[i,j]=assemble({},[("state",a,True,None,BLOCK_LINKS),("state",b,False,None,BLOCK_LINKS)],BLOCK_LINKS,fixed,label="GCH")
        G[i,j]=assemble(coeff,[("omega",None,False,None,BLOCK_LINKS),("omega",None,True,None,BLOCK_LINKS),("state",a,True,None,BLOCK_LINKS),("state",b,False,None,BLOCK_LINKS)],BLOCK_LINKS,fixed,label="GCG")/Z
        for A in range(3):
         for e in BLOCK_LINKS:
          D[i,j]+=assemble(coeff,[("omega",None,False,None,BLOCK_LINKS),("omega",None,True,None,BLOCK_LINKS),("state",a,True,A,(e,)),("state",b,False,A,(e,))],BLOCK_LINKS,fixed,label="GCD")/Z
      return Z,H,G,G-np.outer(np.conj(mean),mean),D
    z0,h0,g0,c0,d0=run(fixed_tables(base)); z1,h1,g1,c1,d1=run(fixed_tables(trans))
    return max(abs(z1-z0),float(np.max(abs(h1-h0))),float(np.max(abs(g1-g0))),float(np.max(abs(c1-c0))),float(np.max(abs(d1-d0))))


def main():
    # The final receipt is never opened until all computations and controls pass.
    if OUT.exists(): raise SystemExit(f"refusing to overwrite existing receipt: {OUT}")
    start=time.perf_counter()
    raw={p:p.read_bytes() for p in (PROTOCOL,SOURCE,ALGEBRA,REFERENCE)}
    spaces={J:Space(J) for J in (1,2,3,4)}
    spectrum={}; conditional={}
    for J in CUTOFFS:
      spc,ext=spaces[J],spaces[J+1]
      for x in COUPLINGS:
        key=f"J{J}_x{x}"
        rr=ritz(spc,x,ext); coeff=dict(zip(spc.states,rr["vector"]))
        spectrum[key]={**rr,"hamiltonian":matrix_record(spc.hamiltonian(x))}
        angles=[]
        for af in BOUNDARY_ANGLES:
          d=cond_data(coeff,float(af)*math.pi,spc.states); f=retained(d,spc.states)
          rec={"theta_pi":str(af),"partition":d["partition"],"log_partition":math.log(d["partition"]),
               "rate":f["rate"],"restriction_rank":f["restriction_rank"],
               "retained_dimension":f["retained_dimension"],
               "removed_constant_dimension":f["removed_constant_dimension"],
               "rate_residual":f["rate_residual"],
               "gram_hermiticity":float(np.max(abs(d["gram"]-d["gram"].conj().T))),
               "dirichlet_hermiticity":float(np.max(abs(d["dirichlet"]-d["dirichlet"].conj().T))),
               "gram_min_eigenvalue":float(np.min(f["gram_eigenvalues"])),
               "restriction_gram":matrix_record(f["restriction_gram"]),
               "_R":f["restriction_gram"],
               "matrices":{"gram":matrix_record(d["gram"]),"covariance":matrix_record(d["covariance"]),
                           "dirichlet":matrix_record(d["dirichlet"])}}
          angles.append(rec)
          print(f"J={J} x={x} theta={af} E={rr['energy_ground']:.8g} Z={d['partition']:.8g} rate={f['rate']:.8g}",flush=True)
        conditional[key]=angles

    rows=[]; verdicts=[]; qualification_failures=0
    for J in CUTOFFS:
      for x in COUPLINGS:
        key=f"J{J}_x{x}"; arr=conditional[key]
        sens=max(abs(r["log_partition"]) for r in arr)
        rates=[r["rate"] for r in arr]; ratio=min(rates)/max(rates) if max(rates)>0 else 0.0
        if sens<=ORBIT_THRESHOLD: verdicts.append("NULL_ORBIT_COLLAPSE")
        else: verdicts.append("SUPPORTS_BOUNDARY_SENSITIVITY")
        if J==CUTOFFS[-1] and ratio>=UNIFORM_RATIO: verdicts.append("SUPPORTS_UNIFORM_RETAINED_FIBRE")
        if J==CUTOFFS[-1] and ratio<NONUNIFORM_RATIO: verdicts.append("INCONSISTENT_RETAINED_FIBRE")
        prev=conditional.get(f"J{J-1}_x{x}") if J> CUTOFFS[0] else None
        rr=spectrum[key]["full_residual"]
        for i,r in enumerate(arr):
          failures=[]
          nested=0.0; rank_change=False
          if rr>FULL_RESIDUAL_MAX: failures.append("full_space_residual")
          if prev is not None:
            rank_change=r["restriction_rank"] != prev[i]["restriction_rank"]
            if rank_change: failures.append("restriction_rank_change")
            lowR=prev[i]["_R"]; highR=r["_R"]
            nested=float(np.max(abs(highR[:len(lowR),:len(lowR)]-lowR)))
            r["nested_inclusion_residual"]=nested
          else: r["nested_inclusion_residual"]=0.0
          r["rank_change"]=rank_change
          qualified=not failures
          if not qualified: cls="INCONCLUSIVE"; qualification_failures+=1
          elif r["rate"]<COLLAPSE_THRESHOLD: cls="CONDITIONAL_COLLAPSE_WITNESS"
          elif sens>ORBIT_THRESHOLD: cls="SUPPORTS_BOUNDARY_SENSITIVITY"
          else: cls="NULL_ORBIT_COLLAPSE"
          r["qualification_failures"]=failures; r["rate_qualified"]=qualified; r["classification"]=cls
          rows.append({"cutoff":J,"coupling":str(x),"full_residual":rr,**{k:v for k,v in r.items() if k!="_R"}})

    j1=spaces[1]
    dim_ok=len(j1.states)==5 and sum(1 for s in j1.states if s[:2]==(1,1))==2
    kinetic_ok=all(abs(j1.kinetic[i]-(4*casimir(s[0])+4*casimir(s[1])))<1e-14 for i,s in enumerate(j1.states))
    norm_err=max(abs(float(np.real(overlap(s,s)))-norm_expected(s)) for s in j1.states)
    herm=max(max(r["gram_hermiticity"],r["dirichlet_hermiticity"]) for r in rows)
    gram_min=min(r["gram_min_eigenvalue"] for r in rows); zmin=min(r["partition"] for r in rows)
    gauge_err=gauge_control(j1,dict(zip(j1.states,ritz(j1,Fraction(1),spaces[2])["vector"])))
    with tempfile.TemporaryDirectory() as td:
      sentinel=Path(td)/"sentinel"; sentinel.write_text("sealed",encoding="utf-8")
      try:
        with sentinel.open("x",encoding="utf-8"): pass
        overwrite_refused=False
      except FileExistsError: overwrite_refused=True
    controls={"state_space_dimension_check":{"passed":dim_ok,"measured":len(j1.states),"expected":5,"states":[list(s) for s in j1.states]},
      "kinetic_quantum_numbers":{"passed":kinetic_ok,"values":j1.kinetic.tolist()},
      "normalization_control":{"passed":norm_err<=1e-10,"max_error":norm_err},
      "gauge_orbit_invariance":{"passed":gauge_err<=1e-10,"max_abs_moment_difference":gauge_err},
      "hermiticity":{"passed":herm<=1e-10,"max_residual":herm},
      "positivity":{"passed":zmin>0 and gram_min>-1e-10,"partition_min":zmin,"gram_eigenvalue_min":gram_min},
      "refusal_to_overwrite":{"passed":overwrite_refused,"mode":"exclusive_create","preexisting_receipt":True}}
    if qualification_failures: classification="INCONCLUSIVE"
    elif any(r["classification"]=="CONDITIONAL_COLLAPSE_WITNESS" for r in rows): classification="CONDITIONAL_COLLAPSE_WITNESS"
    elif "INCONSISTENT_RETAINED_FIBRE" in verdicts: classification="INCONSISTENT_RETAINED_FIBRE"
    elif "SUPPORTS_BOUNDARY_SENSITIVITY" in verdicts: classification="SUPPORTS_BOUNDARY_SENSITIVITY"
    elif "SUPPORTS_UNIFORM_RETAINED_FIBRE" in verdicts: classification="SUPPORTS_UNIFORM_RETAINED_FIBRE"
    else: classification="NULL_ORBIT_COLLAPSE"
    for arr in conditional.values():
      for r in arr: r.pop("_R",None)
    graph={"links":[{"index":e,"tail":LINK_TAILS[e],"head":LINK_HEADS[e]} for e in ALL_LINKS],
      "plaquettes":[[{"link":e,"orientation":o} for e,o in p] for p in PLAQUETTES],
      "block":list(BLOCK_LINKS),"exterior":list(EXTERIOR_LINKS)}
    schedule={"cutoffs_doubled":list(CUTOFFS),"couplings":[str(x) for x in COUPLINGS],
      "boundary_angles_pi":[str(a) for a in BOUNDARY_ANGLES],"orbit_threshold":ORBIT_THRESHOLD,
      "uniform_ratio":UNIFORM_RATIO,"nonuniform_ratio":NONUNIFORM_RATIO,"collapse_threshold":COLLAPSE_THRESHOLD}
    notes=["The protocol says 'same retained test space as the seven-link study'; literal reading implemented as the full restriction image of all (A,B,q) spin-network states, with the constant direction removed.",
      "The state labels are (A,B,q): A and B are doubled link spins; q=0,...,min(A,B) is a channel ordinal whose physical intermediate doubled spin is 2q, giving min(A,B)+1 intertwiners.",
      "The exterior-loop orientation is literal: U4 U5 U6^{-1} U7^{-1}; fixed boundary values are U4=U5=U6=I and U7=exp(i theta sigma3/2).",
      "The protocol requests a retained fibre rate but does not define a separate transport score; no transport approximation was substituted."]
    record={"schema":"cassi.yang-mills.bowtie-fibre.v1","execution":"PASS","classification":classification,
      "source_sha256":hashlib.sha256(raw[SOURCE]).hexdigest(),"protocol_sha256":hashlib.sha256(raw[PROTOCOL]).hexdigest(),
      "inputs":{p.relative_to(ROOT).as_posix():hashlib.sha256(b).hexdigest() for p,b in raw.items()},
      "graph":graph,"schedule":schedule,
      "graph_sha256":hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest(),
      "schedule_sha256":hashlib.sha256(json.dumps(schedule,sort_keys=True).encode()).hexdigest(),
      "spaces":{str(J):{"dimension":len(sp.states),"states":[list(s) for s in sp.states],
        "overlap":matrix_record(sp.overlap),"kinetic":matrix_record(sp.kinetic),
        "plaquette":matrix_record(sp.plaquette),"hermiticity_residual":sp.hermiticity_residual} for J,sp in spaces.items()},
      "spectrum":spectrum,"conditional":conditional,"rows":rows,"controls":controls,
      "implementation_notes":notes,
      "open_obligations":["exact-vacuum fibre rate","transport score","cutoff removal","uniform interacting recovery","thermodynamic limit","continuum construction"],
      "wall_seconds":time.perf_counter()-start}
    if any(p.read_bytes()!=b for p,b in raw.items()): raise RuntimeError("input bytes changed during run")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("x",encoding="utf-8") as f: f.write(json.dumps(record,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print(f"wrote {OUT}: execution PASS; scientific classification {classification}")
    print(f"source_sha256={record['source_sha256']} receipt_sha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}")

if __name__=="__main__": main()
