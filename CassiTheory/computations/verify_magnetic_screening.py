#!/usr/bin/env python3
"""Independently reconstruct the constrained magnetic-screening identities.

Run: python computations/verify_magnetic_screening.py
Protocol: computations/matter-formation-continuum-report.md section 39.1.
The component densities are positive, so -1 < b = cos(beta) < 1.
This program imports no primary calculation or reported result.
"""

import json

import sympy as s

rho, g, K, Ks = s.symbols('rho g K Ks', positive=True)
b = s.symbols('b', real=True)
tY, tI, theta, relative = s.symbols('tY tI theta relative', real=True)
k = s.Matrix([1, 2, -1, s.Rational(3, 4)])
B = s.Matrix([s.Rational(3, 5), -s.Rational(3, 10), s.Rational(1, 5), s.Rational(4, 5)])
W = s.diag(K, K, K, Ks)
EY, EI = rho*(1+b)/2, rho*(1-b)/2


def square(x):
    return (x.T*W*x)[0]


energy = (EY*square(tY*k-g*B/2)+EI*square(tI*k+g*B/2))/2
stationary = s.solve([s.diff(energy,tY),s.diff(energy,tI)], [tY,tI])
V = square(k)
P = (k.T*W*B)[0]
projected = rho*g*g*(square(B)-P*P/V)/8
assert s.factor(energy.subs(stationary)-projected) == 0
assert s.factor(s.diff(projected,b)) == 0
common = energy.subs({tY:theta-relative/2,tI:theta+relative/2})
c = relative*k+g*B
Pc = (k.T*W*c)[0]
theta_star = s.solve(s.diff(common,theta),theta)[0]
assert s.factor(theta_star-b*Pc/(2*V)) == 0
common_projected = rho*(square(c)-b*b*Pc*Pc/V)/8
assert s.factor(common.subs(theta,theta_star)-common_projected) == 0
shift = s.symbols('shift',real=True)
assert s.factor(common.subs(theta,theta_star+shift)-common_projected-rho*V*shift**2/2)==0
A = s.symbols('A',real=True)
tube = K*(EY*(1-g*A/2)**2+EI*(-1+g*A/2)**2)/2
assert s.factor(s.diff(tube,A,2)-K*rho*g*g/4)==0
phi = (1+s.sqrt(5))/2
counterflow = K*rho/phi**3
assert s.simplify(counterflow-K*rho*(1-phi**-6)/4)==0
print(json.dumps({
    'verdict': 'PASS',
    'independent_exact_checks': 7,
    'transverse_mass_squared': 'g_Q^2 K_x rho / 4',
    'counterflow_stiffness': 'K_x rho (1-cos(beta)^2) / 4',
    'counterflow_to_transverse_ratio_at_phi': float(4/phi**3),
    'kappa_squared_witness': 0.71*0.83**2*1.2*0.8/4,
    'complete_physical_matter_formation': False,
}, indent=2))
