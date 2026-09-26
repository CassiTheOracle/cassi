#[compute]
// Open-tile site traversal over exact CSR derived from sampled-JFA adjacency.
#version 450
layout(local_size_x=64,local_size_y=1,local_size_z=1) in;
const int MAX_SEG=64; const float EPS_DEN=1e-7;
layout(push_constant,std430)uniform PC{
 float n_rays_f,n_sites_f,max_seg_f,pad0;
 float extent_x,extent_y,extent_z,pad1;
 float window_x,window_y,window_z,pad2;
}pc;
layout(set=0,binding=0,std430)readonly buffer Sites{vec4 sites[];};
layout(set=0,binding=1,std430)readonly buffer CsrOffsets{uint offsets[];};
layout(set=0,binding=2,std430)readonly buffer CsrNeighbors{uint neighbors[];};
layout(set=0,binding=3,std430)readonly buffer Rays{vec4 rays[];};
layout(set=0,binding=4,std430)readonly buffer StartSite{int start_site[];};
layout(set=0,binding=5,std430)writeonly buffer Sequence{int seq[];};
layout(set=0,binding=6,std430)writeonly buffer HitT{float hit_t[];};
layout(set=0,binding=7,std430)writeonly buffer Count{int counts[];};
vec3 site_world(int i){return sites[i].xyz-vec3(pc.extent_x,pc.extent_y,pc.extent_z)+vec3(pc.window_x,pc.window_y,pc.window_z);}
float exit_t(vec3 ro,vec3 rd){
 vec3 mn=vec3(pc.window_x,pc.window_y,pc.window_z)-vec3(pc.extent_x,pc.extent_y,pc.extent_z);
 vec3 mx=vec3(pc.window_x,pc.window_y,pc.window_z)+vec3(pc.extent_x,pc.extent_y,pc.extent_z);
 float tx=abs(rd.x)>1e-9?((rd.x>0.?mx.x:mn.x)-ro.x)/rd.x:3.402823466e38;
 float ty=abs(rd.y)>1e-9?((rd.y>0.?mx.y:mn.y)-ro.y)/rd.y:3.402823466e38;
 float tz=abs(rd.z)>1e-9?((rd.z>0.?mx.z:mn.z)-ro.z)/rd.z:3.402823466e38;
 return min(tx,min(ty,tz));
}
void main(){
 int q=int(gl_GlobalInvocationID.x),nr=int(pc.n_rays_f+0.5),ns=int(pc.n_sites_f+0.5),cap=min(int(pc.max_seg_f+0.5),MAX_SEG);if(q>=nr)return;
 vec3 ro=rays[q*2].xyz,rd=normalize(rays[q*2+1].xyz);float texit=exit_t(ro,rd);int cur=start_site[q];float tc=0.;int nout=0;
 for(int step=0;step<cap;++step){
  if(cur<0||cur>=ns||tc>=texit)break;seq[q*MAX_SEG+nout]=cur;hit_t[q*MAX_SEG+nout]=tc;nout++;
  vec3 si=site_world(cur),p=ro+rd*tc;float eps=max(1e-5,2e-6*max(1.,abs(tc))),best=3.402823466e38;int nxt=-1;
  uint begin=offsets[cur],end=offsets[cur+1];
  for(uint k=begin;k<end;++k){int j=int(neighbors[k]);if(j==cur||j<0||j>=ns)continue;vec3 r=site_world(j)-si;float den=dot(r,rd);if(den<=EPS_DEN)continue;float th=tc+(dot(r,r)-2.*dot(r,p-si))/(2.*den);if(!(th>tc+eps)||!(th<texit-eps))continue;if(th<best-eps||(abs(th-best)<=eps&&(nxt<0||j<nxt))){best=th;nxt=j;}}
  if(nxt<0)break;tc=best;cur=nxt;
 }
 counts[q]=nout;
}