#[compute]
// Two-vec4/site compact payload. First vec4 = render-local site xyz (tile-E)
// and opacity. Second = EY, EI, coherence, gradient magnitude.
#version 450
layout(local_size_x=64,local_size_y=1,local_size_z=1) in;
layout(push_constant,std430) uniform PC { float n_sites_f; float extent_x; float extent_y; float extent_z; float opacity_scale; float _pad0; float _pad1; float _pad2; } pc;
layout(set=0,binding=0,std430) readonly buffer Sites { vec4 sites[]; };
layout(set=0,binding=1,std430) readonly buffer PsiY { float ey[]; };
layout(set=0,binding=2,std430) readonly buffer PsiI { float ei[]; };
layout(set=0,binding=3,std430) readonly buffer GradY { vec4 gy[]; };
layout(set=0,binding=4,std430) readonly buffer GradI { vec4 gi[]; };
layout(set=0,binding=5,std430) writeonly buffer Optical { vec4 optical[]; };
void main(){ uint s=gl_GlobalInvocationID.x,ns=uint(max(pc.n_sites_f,0.0)); if(s>=ns)return; float y=ey[s],i=ei[s],rho=max(y+i,0.0),eps=y-1.61803398875*i; float coh=(rho*rho)/(rho*rho+0.38196601125+eps*eps); float grad=length(gy[s].xyz)+length(gi[s].xyz); vec3 local=sites[s].xyz-vec3(pc.extent_x,pc.extent_y,pc.extent_z); optical[2u*s]=vec4(local,max(pc.opacity_scale,0.0)*rho/(1.0+grad)); optical[2u*s+1u]=vec4(y,i,coh,grad); }
