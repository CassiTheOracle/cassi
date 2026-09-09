#!/usr/bin/env python3
"""Execute the fixed capillary/thermal schedule and preserve immutable evidence.

Run from CassiTheory. Existing outputs are refused; failures retain their input
snapshots and any completed trajectories. Verification supports only the selected
constitutive model, not microscopic viscosity or a physical-fluid replacement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
import sympy as sp
from scipy.integrate import solve_ivp

import cassi_fluid_thermodynamics as fluid
from verify_cassi_fluid_feasibility import Receipt

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/cassi-fluid-thermodynamics-prereg.md"


def algebra(book):
    x, y, z = xyz = sp.symbols("x y z", real=True)
    c = sp.Function("c")(*xyz)
    g = sp.Function("g")(c)
    a, cs, gamma, mass, hbar, n0 = sp.symbols("a cs gamma m hbar n0", positive=True)
    dc = sp.Matrix([sp.diff(c, coordinate) for coordinate in xyz])
    energy = a * (c-cs)**2/2 + g * dc.dot(dc)/2
    flux = g * dc
    mu = a*(c-cs) + sp.diff(g, c)*dc.dot(dc)/2 - sum(sp.diff(flux[j], xyz[j]) for j in range(3))
    stress = g * dc * dc.T
    for i in range(3):
        residual = mu*dc[i] - sp.diff(energy, xyz[i]) + sum(sp.diff(stress[i,j], xyz[j]) for j in range(3))
        book.exact(f"algebra.stress_{i}", sp.expand(residual))
    reaction = sp.Function("R")(*xyz)
    velocity = sp.Matrix([sp.Function(f"u{i}")(*xyz) for i in range(3)])
    ct = reaction - velocity.dot(dc)
    et = (a*(c-cs)+sp.diff(g,c)*dc.dot(dc)/2)*ct
    et += sum(flux[j]*sp.diff(ct,xyz[j]) for j in range(3))
    transport = et + sum(velocity[j]*sp.diff(energy,xyz[j]) for j in range(3))
    interstitial = sum(sp.diff(flux[j]*reaction,xyz[j]) for j in range(3))
    stress_work = sum(stress[i,j]*sp.diff(velocity[i],xyz[j]) for i in range(3) for j in range(3))
    book.exact("algebra.material_energy", sp.expand(transport-mu*reaction-interstitial+stress_work))
    fraction, grad = sp.symbols("fraction grad", positive=True)
    fisher = hbar**2/(2*mass) * (n0/(4*fraction)+n0/(4*(1-fraction))) * grad**2
    book.exact("algebra.fisher_coefficient", fisher - hbar**2*n0/(8*mass*fraction*(1-fraction))*grad**2)
    chi, gamma, alpha, beta = sp.symbols("chi gamma alpha beta", positive=True)
    fraction_chi = sp.sin(chi/(2*sp.sqrt(gamma)))**2
    metric_chi = gamma/(fraction_chi*(1-fraction_chi))
    book.exact("algebra.flat_gradient_coordinate",
               sp.trigsimp(metric_chi*sp.diff(fraction_chi,chi)**2-1))
    profile = alpha*sp.cos(x)+beta*sp.cos(x+y)
    overlap = sp.expand_trig(sp.diff(profile,x)*sp.diff(profile,y)*sp.cos(y))
    mean_work = sp.integrate(overlap,(x,0,2*sp.pi),(y,0,2*sp.pi))/(2*sp.pi)**2
    book.exact("algebra.nonzero_capillary_commutator",mean_work-alpha*beta/4)
    temperature, C, b, potential, hp, M, viscous, lapT, conduction, gradT2 = sp.symbols("T C b mu hp M H lapT k gradT2", real=True)
    affinity = potential + b*temperature*hp
    R = -M*affinity
    Tdot = (conduction*lapT+viscous-potential*R)/C
    entropy_rate = C*Tdot/temperature-b*hp*R
    entropy_flux_div = conduction*lapT/temperature-conduction*gradT2/temperature**2
    expected = (viscous+M*affinity**2)/temperature+conduction*gradT2/temperature**2
    book.exact("algebra.entropy_balance", entropy_rate-entropy_flux_div-expected)
    book.exact("algebra.total_energy_exchange", -viscous + potential*R + C*Tdot-conduction*lapT)
    delta, slope, gate, scale = sp.symbols("delta slope kappa scale", positive=True)
    mobility = scale*gate/(a+b*temperature*slope)
    book.exact("algebra.canonical_homogeneous", -mobility*(a*delta+b*temperature*slope*delta)+scale*gate*delta)
    book.exact("algebra.zero_temperature_heat", (-potential*R).subs(temperature,0)-M*potential**2)
    r = (sp.log(fraction/cs)-sp.log((1-fraction)/(1-cs)))/(fraction-cs)
    book.exact("algebra.continuous_secant", sp.limit(r,fraction,cs)-1/(cs*(1-cs)))

    p = fluid.Parameters()
    c0, t0, lap_c = 0.7, 1.0, 10.0
    delta0 = c0-fluid.C_STAR
    mu0 = p.a*delta0-p.gamma/(c0*(1-c0))*lap_c
    hp0 = np.log(c0*(1-fluid.C_STAR)/(fluid.C_STAR*(1-c0)))
    eps = p.rho_ref*(1+fluid.PHI)*delta0
    kappa = p.conversion*(fluid.PHI**-2+eps**2)/(p.rho_ref**2+fluid.PHI**-2+eps**2)
    Rlocal = -(1+fluid.PHI)*kappa*delta0
    A0 = mu0+p.mixing_entropy*t0*hp0
    mobility0 = (1+fluid.PHI)*kappa/(p.a+p.mixing_entropy*t0*hp0/delta0)
    book.check("control.local_reaction_entropy_violation", -A0*Rlocal/t0 < 0,
               dict(c=c0, laplacian=lap_c, mu=mu0, affinity=A0, local_entropy_production=-A0*Rlocal/t0))
    book.check("control.affinity_entropy_sign", mobility0*A0*A0/t0 > 0,
               dict(entropy_production=mobility0*A0*A0/t0))
    c0 = 0.8
    eps = p.rho_ref*(1+fluid.PHI)*(c0-fluid.C_STAR)
    local_reaction = -(1+fluid.PHI)*p.conversion*(fluid.PHI**-2+eps**2)/(p.rho_ref**2+fluid.PHI**-2+eps**2)*(c0-fluid.C_STAR)
    book.check("control.omitted_conversion_heat", p.a*(c0-fluid.C_STAR)*local_reaction < -1e-6,
               dict(total_energy_rate_without_heat=p.a*(c0-fluid.C_STAR)*local_reaction))
    book.check("control.omitted_shear_heat", -p.viscosity/2 < -1e-6,
               dict(total_energy_rate_without_heat=-p.viscosity/2))


class MatrixReference:
    """Independent trigonometric differentiation and direct spectral Poisson."""
    def __init__(self, n, parameters):
        self.n, self.p = n, parameters
        x = 2*np.pi*np.arange(n)/n
        modes = np.arange(-(n//2), n//2+1, dtype=np.float64)
        difference = x[:,None]-x[None,:]
        self.D = np.real(np.sum(1j*modes[:,None,None]*np.exp(1j*modes[:,None,None]*difference),axis=0)/n)
        self.F = np.exp(-1j*modes[:,None]*x[None,:])/np.sqrt(n)
        self.Finv = self.F.conj().T
        grid = np.meshgrid(modes,modes,modes,indexing="ij")
        k2 = sum(component**2 for component in grid)
        self.inverse_lap = np.zeros_like(k2)
        np.divide(-1.0,k2,out=self.inverse_lap,where=k2!=0)
        nodes, weights = np.polynomial.legendre.leggauss(16)
        self.nodes, self.weights = (nodes+1)/2, weights/2

    @staticmethod
    def along(value, matrix, axis):
        absolute_axis = value.ndim-3+axis
        moved = np.moveaxis(value,absolute_axis,-1)
        return np.moveaxis(moved@matrix.T,-1,absolute_axis)

    def d(self, value, axis):
        return self.along(value,self.D,axis)

    def lap(self, value):
        return sum(self.d(self.d(value,j),j) for j in range(3))

    def project(self, vector):
        pressure = sum(self.d(vector[j],j) for j in range(3)).astype(np.complex128)
        for j in range(3):
            pressure = self.along(pressure,self.F,j)
        pressure *= self.inverse_lap
        for j in range(3):
            pressure = self.along(pressure,self.Finv,j)
        return vector-np.asarray([self.d(pressure.real,j) for j in range(3)])

    def rhs(self, time, flat_state):
        state = flat_state.reshape(5,self.n,self.n,self.n)
        p, u, c, T = self.p, state[:3], state[3], state[4]
        if np.min(c)<=0 or np.max(c)>=1 or np.min(T)<=0:
            raise FloatingPointError("Independent reference left the physical state domain")
        derivatives = [[self.d(state[i],j) for j in range(3)] for i in range(5)]
        dc = derivatives[3]
        c2 = sum(d*d for d in dc)
        g = p.gamma/(c*(1-c))
        gp = p.gamma*(2*c-1)/(c*c*(1-c)**2)
        gradient_mu = 0.5*gp*c2-sum(self.d(g*dc[j],j) for j in range(3))
        mu = p.a*(c-fluid.C_STAR)+gradient_mu
        delta = c-fluid.C_STAR
        slope = np.zeros_like(c)
        for node, weight in zip(self.nodes,self.weights):
            intermediate = fluid.C_STAR+node*delta
            slope += weight/(intermediate*(1-intermediate))
        eps = p.rho_ref*((1+fluid.PHI)*c-fluid.PHI)
        kappa = p.conversion*(1-p.rho_ref**2/(p.rho_ref**2+fluid.PHI**-2+eps**2))
        mobility = (1+fluid.PHI)*kappa/(p.a+p.mixing_entropy*T*slope)
        reaction = -(1+fluid.PHI)*kappa*delta-mobility*gradient_mu
        viscous_heat = np.zeros_like(c)
        force = np.zeros_like(u)
        velocity_rhs = np.zeros_like(u)
        for i in range(3):
            for j in range(3):
                force[i] -= self.d(g*dc[i]*dc[j],j)
                velocity_rhs[i] -= 0.5*(u[j]*derivatives[i][j]+self.d(u[i]*u[j],j))
                viscous_heat += 0.5*p.viscosity*(derivatives[i][j]+derivatives[j][i])**2
        result = np.empty_like(state)
        result[:3] = self.project(velocity_rhs+force/p.inertia)+(p.viscosity/p.inertia)*self.lap(u)
        result[3] = reaction-sum(u[j]*dc[j] for j in range(3))
        result[4] = (p.conductivity*self.lap(T)+viscous_heat-mu*reaction)/p.heat_capacity
        result[4] -= sum(u[j]*derivatives[4][j] for j in range(3))
        return result.ravel()

    def observables(self, state):
        p, u, c, T = self.p, state[:3], state[3], state[4]
        gradient2 = sum(self.d(c,j)**2 for j in range(3))
        return dict(kinetic=float(p.inertia*np.mean(np.sum(u*u,axis=0))/2),
                    composition=float(np.mean(p.a*(c-fluid.C_STAR)**2/2+p.gamma*gradient2/(2*c*(1-c)))),
                    thermal=float(p.heat_capacity*np.mean(T)),
                    entropy=float(np.mean(p.heat_capacity*np.log(T)-p.mixing_entropy*(c*np.log(c/fluid.C_STAR)+(1-c)*np.log((1-c)/(1-fluid.C_STAR))))))


def run_case(book, key, model, initial, dt, c_bounds, expected=None):
    final, history, columns, integral = model.evolve(initial,0.2,dt)
    before, after = model.diagnostics(initial), model.diagnostics(final)
    table = {name: history[:,index] for index,name in enumerate(columns)}
    momentum = history[:,[columns.index(f"momentum_{axis}") for axis in "xyz"]]
    drift = float(np.max(np.abs(momentum-momentum[0])))
    book.check(key+".finite_domain", bool(np.isfinite(history).all() and np.min(table["c_min"])>0
               and np.max(table["c_max"])<1 and np.min(table["temperature_min"])>0),
               dict(c_min=float(np.min(table["c_min"])),c_max=float(np.max(table["c_max"])),temperature_min=float(np.min(table["temperature_min"]))))
    book.check(key+".composition_interval", np.min(table["c_min"])>=c_bounds[0]-1e-10
               and np.max(table["c_max"])<=c_bounds[1]+1e-10,dict(bounds=c_bounds))
    book.near(key+".momentum",drift,0,tolerance=1e-10)
    book.near(key+".divergence",np.max(table["divergence_max"]),0,tolerance=1e-10)
    row = dict(parameters=asdict(model.p),n=model.n,dt=dt,duration=0.2,initial=before,final=after,
               max_energy_drift=float(np.max(np.abs(table["total_energy"]-before["total_energy"]))),
               entropy_integral=integral,entropy_balance_error=after["entropy"]-before["entropy"]-integral,
               max_momentum_drift=drift)
    if expected is not None:
        row["endpoint_error"] = float(np.max(np.abs(final-expected))/max(1.0,float(np.max(np.abs(expected)))))
        book.near(key+".exact_endpoint",final,expected,tolerance=1e-8)
    book.result.setdefault("trajectories",{})[key]=row
    book.arrays[key+".initial"]=initial.copy()
    book.arrays[key+".final"]=final
    book.arrays[key+".history"]=history
    book.result["history_columns"]=columns
    return final, row


def exact_controls(book):
    for family in ("homogeneous", "shear", "conduction", "stationary", "homogeneous_low"):
        for n in ((9,) if family=="homogeneous_low" else (9,15)):
            model=fluid.SpectralFluid(n)
            p=model.p
            x,y,z=model.xyz
            initial=np.zeros((5,n,n,n))
            initial[3]=fluid.C_STAR
            initial[4]=1
            expected=initial.copy()
            bounds=(fluid.C_STAR,fluid.C_STAR)
            if family.startswith("homogeneous"):
                c0=0.3 if family=="homogeneous_low" else 0.8
                initial[3]=c0
                def canonical(time,value):
                    eps=p.rho_ref*((1+fluid.PHI)*value[0]-fluid.PHI)
                    return [-(1+fluid.PHI)*p.conversion*(1-p.rho_ref**2/(p.rho_ref**2+fluid.PHI**-2+eps**2))*(value[0]-fluid.C_STAR)]
                solution=solve_ivp(canonical,(0,0.2),[c0],method="DOP853",rtol=1e-13,atol=1e-14)
                if not solution.success:
                    raise RuntimeError(solution.message)
                expected[3]=solution.y[0,-1]
                expected[4]=1+p.a*((c0-fluid.C_STAR)**2-(solution.y[0,-1]-fluid.C_STAR)**2)/(2*p.heat_capacity)
                bounds=(min(c0,fluid.C_STAR),max(c0,fluid.C_STAR))
            elif family=="shear":
                nu=p.viscosity/p.inertia
                initial[0]=np.sin(y)
                expected[0]=np.exp(-nu*0.2)*np.sin(y)
                mean=p.inertia*(1-np.exp(-2*nu*0.2))/(4*p.heat_capacity)
                rate=4*p.conductivity/p.heat_capacity
                amplitude=p.viscosity/(2*p.heat_capacity)*(np.exp(-2*nu*0.2)-np.exp(-rate*0.2))/(rate-2*nu)
                expected[4]=1+mean+amplitude*np.cos(2*y)
            elif family=="conduction":
                profile=np.cos(x)*np.cos(y)*np.cos(z)
                initial[4]=1+0.1*profile
                expected[4]=1+0.1*np.exp(-3*p.conductivity*0.2/p.heat_capacity)*profile
            else:
                initial[:3]=np.array([0.3,-0.2,0.1])[:,None,None,None]
                expected=initial.copy()
            rows=[]
            for dt in (0.004,0.002):
                key=f"{family}.N{n}.dt{dt}"
                _,row=run_case(book,key,model,initial,dt,bounds,expected)
                rows.append(row)
            coarse,fine=(row["endpoint_error"] for row in rows)
            book.check(f"{family}.N{n}.refinement",coarse<=1e-11 or fine<=coarse/8,
                       dict(coarse=coarse,fine=fine,order_floor=1e-11))


def coupled_controls(book):
    finals={}
    bounds=(fluid.C_STAR-0.105,fluid.C_STAR+0.105)
    for n in (9,15,21):
        model=fluid.SpectralFluid(n)
        initial=fluid.coupled_initial(model)
        rhs=model.rhs(initial)
        fields=model.terms(initial)
        p=model.p
        analytic_E=float(np.mean(p.inertia*np.sum(initial[:3]*rhs[:3],axis=0)+fields["mu"]*rhs[3]+p.heat_capacity*rhs[4]))
        analytic_S=float(np.mean(p.heat_capacity*rhs[4]/initial[4]-p.mixing_entropy*fields["hp"]*rhs[3]))
        plus=model.diagnostics(initial+1e-6*rhs)
        minus=model.diagnostics(initial-1e-6*rhs)
        book.near(f"variation.N{n}.energy",(plus["total_energy"]-minus["total_energy"])/2e-6,analytic_E,tolerance=1e-7)
        book.near(f"variation.N{n}.entropy",(plus["entropy"]-minus["entropy"])/2e-6,analytic_S,tolerance=1e-7)
        book.result.setdefault("spatial_budget_residuals",{})[str(n)]=dict(energy_rate=analytic_E,
                              entropy_rate_defect=analytic_S-float(np.mean(fields["production"])))
        for dt in (0.004,0.002):
            final,row=run_case(book,f"coupled.N{n}.dt{dt}",model,initial,dt,bounds)
            finals[n,dt]=final
        book.near(f"coupled.N{n}.time_difference",finals[n,0.004],finals[n,0.002],tolerance=1e-7)
    fine=book.result["trajectories"]["coupled.N21.dt0.002"]
    book.near("coupled.fine.energy_budget",fine["max_energy_drift"],0,tolerance=1e-7)
    book.near("coupled.fine.entropy_budget",fine["entropy_balance_error"],0,tolerance=1e-7)
    book.check("coupled.fine.entropy_increase",fine["final"]["entropy"]-fine["initial"]["entropy"]>1e-7,
               dict(increase=fine["final"]["entropy"]-fine["initial"]["entropy"]))
    initial=book.arrays["coupled.N21.dt0.002.initial"]
    final=finals[21,0.002]
    book.check("coupled.fine.generated_vertical_flow",np.max(np.abs(final[2]))>1e-8,dict(max_vertical_velocity=float(np.max(np.abs(final[2])))))
    book.check("coupled.fine.composition_evolution",np.max(np.abs(final[3]-initial[3]))>1e-6,dict(max_change=float(np.max(np.abs(final[3]-initial[3])))))
    for name in ("kinetic","composition","thermal","entropy"):
        other=book.result["trajectories"]["coupled.N15.dt0.002"]["final"][name]
        book.near("coupled.spatial."+name,fine["final"][name],other,tolerance=1e-5)
    for n in (15,21):
        model=fluid.SpectralFluid(n,replace(fluid.Parameters(),viscosity=0,conductivity=0,conversion=0))
        initial=fluid.coupled_initial(model,at_rest=True)
        initial[4]=1
        final,row=run_case(book,f"capillary.N{n}",model,initial,0.002,bounds)
        book.check(f"capillary.N{n}.kinetic_release",row["final"]["kinetic"]>1e-10,dict(kinetic=row["final"]["kinetic"]))
        book.near(f"capillary.N{n}.temperature",final[4],1,tolerance=1e-12)
        if n==21:
            book.near("capillary.fine.energy_budget",row["max_energy_drift"],0,tolerance=1e-7)
            compensation=row["final"]["kinetic"]+row["final"]["composition"]-row["initial"]["composition"]
            threshold=1e-12+0.01*row["final"]["kinetic"]
            book.check("capillary.fine.resolved_exchange",abs(compensation)<=threshold,
                       dict(kinetic_gain=row["final"]["kinetic"],exchange_defect=compensation,tolerance=threshold))
    model=fluid.SpectralFluid(21)
    boost=np.array([0.3,-0.2,0.1])
    initial=fluid.coupled_initial(model)
    initial[:3]+=boost[:,None,None,None]
    final,_=run_case(book,"boost.N21",model,initial,0.002,bounds)
    shift=np.exp(-0.2j*np.sum(model.k*boost[:,None,None,None],axis=0))
    translated=model.ifft(model.fft(finals[21,0.002])*shift)
    translated[:3]+=boost[:,None,None,None]
    book.near("boost.Galilean_covariance",final,translated,tolerance=1e-6)


def independent_controls(book):
    model=fluid.SpectralFluid(9)
    initial=fluid.coupled_initial(model)
    reference=MatrixReference(9,model.p)
    independent_rhs=reference.rhs(0,initial.ravel()).reshape(initial.shape)
    book.near("reference.matrix_rhs",independent_rhs,model.rhs(initial),tolerance=1e-10)
    result=solve_ivp(reference.rhs,(0,0.2),initial.ravel(),method="DOP853",rtol=1e-11,atol=1e-11)
    book.check("reference.integration",result.success,dict(message=result.message,evaluations=result.nfev))
    if not result.success:
        raise RuntimeError(result.message)
    final=result.y[:,-1].reshape(initial.shape)
    book.arrays["reference.N9.final"]=final
    book.near("reference.matrix_endpoint",final,book.arrays["coupled.N9.dt0.002.final"],tolerance=1e-8)
    book.result["independent_reference"]=dict(n=9,method="direct differentiation matrices and DOP853",nfev=result.nfev)
    for key,row in book.result["trajectories"].items():
        reference=MatrixReference(row["n"],fluid.Parameters(**row["parameters"]))
        for endpoint in ("initial","final"):
            reconstructed=reference.observables(book.arrays[key+"."+endpoint])
            for name,value in reconstructed.items():
                book.near(f"raw.{key}.{endpoint}.{name}",value,row[endpoint][name],tolerance=1e-11)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"runs/cassi_fluid_thermodynamics/verification.json")
    args=parser.parse_args()
    output=args.output.resolve()
    manifest=output.with_suffix(".inputs.json")
    snapshots=output.with_suffix(".sources")
    archive=output.with_suffix(".trajectories.npz")
    if any(path.exists() for path in (output,manifest,snapshots,archive)):
        raise FileExistsError(f"Use a fresh evidence path: {output}")
    sources=dict(protocol=PROTOCOL,model=Path(fluid.__file__).resolve(),verifier=Path(__file__).resolve(),
                 receipt_helper=ROOT/"computations/verify_cassi_fluid_feasibility.py",
                 action=ROOT/"foundations/interscale-current-soliton.md",
                 canonical_density=ROOT/"foundations/cassi-theory-reference.md")
    payloads={name:path.read_bytes() for name,path in sources.items()}
    identities={name:dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(payloads[name]).hexdigest()) for name,path in sources.items()}
    output.parent.mkdir(parents=True,exist_ok=True)
    snapshots.mkdir()
    for name,path in sources.items():
        (snapshots/path.name).write_bytes(payloads[name])
    inputs=dict(created_utc=datetime.now(timezone.utc).isoformat(),inputs=identities,
                platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
    with manifest.open("x",encoding="utf-8") as stream:
        json.dump(inputs,stream,indent=2)
    result=dict(schema="cassi.fluid.thermodynamics.verification.v1",**inputs,
                scope="Selected constant-density constitutive model; smooth-solution identities and finite-grid controls",
                physical_replacement="UNESTABLISHED",microscopic_viscosity="UNESTABLISHED",global_regularity="UNESTABLISHED")
    book=Receipt(result)
    try:
        algebra(book)
        exact_controls(book)
        coupled_controls(book)
        independent_controls(book)
        if any(path.read_bytes()!=payloads[name] for name,path in sources.items()):
            raise RuntimeError("A frozen source changed during execution")
        result["status"]="PASS" if all(row["passed"] for row in book.checks.values()) else "FAIL"
    except Exception as exc:
        result.update(status="ERROR",error=f"{type(exc).__name__}: {exc}")
    finally:
        with archive.open("xb") as stream:
            np.savez_compressed(stream,**book.arrays)
        result["raw_arrays"]=dict(path=archive.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),keys=list(book.arrays))
        result["check_count"]=len(book.checks)
        result["failed_checks"]=[name for name,row in book.checks.items() if not row["passed"]]
        result["trajectory_count"]=len(result.get("trajectories",{}))
        result["closure_budget_classification"]="SUPPORTS" if result["status"]=="PASS" else "INCONCLUSIVE"
        with output.open("x",encoding="utf-8") as stream:
            json.dump(result,stream,indent=2,allow_nan=False)
    print(f"Receipt: {output}")
    print(json.dumps({key:result.get(key) for key in ("status","check_count","trajectory_count","failed_checks","error")},indent=2))
    if result["status"]=="PASS":
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__=="__main__":
    raise SystemExit(main())
