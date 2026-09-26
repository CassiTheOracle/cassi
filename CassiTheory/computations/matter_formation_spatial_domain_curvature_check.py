import sys,json,hashlib
from pathlib import Path
import numpy as np
root=Path.cwd(); sys.path.insert(0,str(root/'computations'))
from matter_formation_radial import Grid,finite_volume_energy_gradient
run=root/'runs/20260906_matter_formation_spatial_domain'
receipt_bytes=(run/'results.json').read_bytes(); receipt=json.loads(receipt_bytes)
checks=[]
for row in receipt['rows']:
    with np.load(run/row['artifact']['path'],allow_pickle=False) as z:
        f=z['f']; c=z['c']; V=z['volumes']; grid=Grid.make(row['R'],row['n'])
        norm=float(np.dot(V,c*c)); omega=row['source']['omega']
        for parent in row['parents']:
            a=parent['a']; charge=norm*np.sqrt(1+4*a*omega)
            vector=z[f"radial_{parent['denominator']}_vectors"][:,0]
            df=vector[0::2]/np.sqrt(V); dc=vector[1::2]/np.sqrt(V)
            def energy(t):
                ff=f+t*df; cc=c+t*dc
                static=finite_volume_energy_gradient(ff,cc,grid)[0]
                population=float(np.dot(V,cc*cc))
                return static+(population-charge)**2/(4*a*population)
            e0=energy(0.)
            for eps in (0.01,0.005):
                curvature=(energy(eps)+energy(-eps)-2*e0)/eps**2
                discrepancy=abs(curvature-parent['minimum'])/max(1.,abs(parent['minimum']))
                checks.append({'id':row['id'],'a':a,'epsilon':eps,'curvature':curvature,'eigenvalue':parent['minimum'],'relative_discrepancy':discrepancy,'pass':bool(discrepancy<1e-4)})
result={'primary_sha256':hashlib.sha256(receipt_bytes).hexdigest(),'method':'Central finite differences of the full fixed-signed-charge nonlinear energy along retained normalized radial eigenvectors','checks':checks,'max_relative_discrepancy':max(x['relative_discrepancy'] for x in checks),'pass':all(x['pass'] for x in checks)}
print(json.dumps(result,allow_nan=False))
sys.exit(0 if result['pass'] else 1)
