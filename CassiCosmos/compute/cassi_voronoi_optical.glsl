#[compute]
// Site-native open-tile radiative transfer over precomputed ray segments.
// Each segment reconstructs EY/EI at its midpoint using AREPO gradients and
// applies front-to-back Beer-Lambert integration.
#version 450
layout(local_size_x=64,local_size_y=1,local_size_z=1) in;
const int MAX_SEG=64;
layout(push_constant,std430) uniform PC{
 float n_rays_f,s_abs,s_fog,s_em;
 float phi_inv2,max_rho,max_e,eps_t;
 float extent_x,extent_y,extent_z,pad0;
 float window_x,window_y,window_z,pad1;
}pc;
layout(set=0,binding=0,std430)readonly buffer Seq{int seq[];};
layout(set=0,binding=1,std430)readonly buffer HitT{float hit_t[];};
layout(set=0,binding=2,std430)readonly buffer Count{int counts[];};
layout(set=0,binding=3,std430)readonly buffer Sites{vec4 sites[];};
layout(set=0,binding=4,std430)readonly buffer PsiY{float ey[];};
layout(set=0,binding=5,std430)readonly buffer PsiI{float ei[];};
layout(set=0,binding=6,std430)readonly buffer GradY{vec4 gy[];};
layout(set=0,binding=7,std430)readonly buffer GradI{vec4 gi[];};
layout(set=0,binding=8,std430)readonly buffer Rays{vec4 rays[];};
layout(set=0,binding=9,std430)writeonly buffer Out{vec4 out_rgba[];};
vec3 palette(float y,float i){float a=atan(i,y)/6.28318530718;return clamp(vec3(.55+.45*cos(6.2831853*(a+vec3(0,.333,.667)))),0.,1.);}
void main(){
 int q=int(gl_GlobalInvocationID.x);if(q>=int(pc.n_rays_f))return;
 int n=counts[q];vec3 ro=rays[q*2].xyz,rd=normalize(rays[q*2+1].xyz);
 vec3 lum=vec3(0);float trans=1.;
 for(int k=0;k+1<n;++k){int s=seq[q*MAX_SEG+k];float t0=hit_t[q*MAX_SEG+k],t1=hit_t[q*MAX_SEG+k+1];float ds=t1-t0;if(ds<=pc.eps_t)continue;
  vec3 pm=ro+rd*(.5*(t0+t1));vec3 sw=sites[s].xyz-vec3(pc.extent_x,pc.extent_y,pc.extent_z)+vec3(pc.window_x,pc.window_y,pc.window_z);vec3 rel=pm-sw;
  float y=clamp(ey[s]+dot(gy[s].xyz,rel),0.,pc.max_e);float i=clamp(ei[s]+dot(gi[s].xyz,rel),0.,pc.max_e);
  float rho=clamp(y+i,0.,pc.max_rho);float qcoh=rho*rho/(rho*rho+pc.phi_inv2+(y-1.61803398875*i)*(y-1.61803398875*i));
  vec3 emit=palette(y,i)*qcoh*rho;float dtrans=exp(-(pc.s_abs*rho+pc.s_fog)*ds);
  lum+=trans*pc.s_em*emit*ds;trans*=dtrans;if(trans<1e-4)break;
 }
 out_rgba[q]=vec4(lum,1.-trans);
}
