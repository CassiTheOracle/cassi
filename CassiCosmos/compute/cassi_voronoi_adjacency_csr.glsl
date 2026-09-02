#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 8 floats (32 B); set 0: bindings 0-4
// Exact sampled-JFA adjacency compaction.
// mode 0: degree count; mode 1: ascending CSR fill; mode 2: single-workgroup
// exclusive scan into offsets including the sentinel and status publication.
#version 450
layout(local_size_x=64,local_size_y=1,local_size_z=1) in;
layout(push_constant,std430) uniform PC { float n_sites_f; float words_per_site_f; float mode; float capacity_f; float generation_f; float _pad0; float _pad1; float _pad2; } pc;
layout(set=0,binding=0,std430) readonly buffer AdjacencyBits { uint adj[]; };
layout(set=0,binding=1,std430) buffer Offsets { uint offsets[]; };
layout(set=0,binding=2,std430) buffer Degree { uint degree[]; };
layout(set=0,binding=3,std430) buffer Neighbors { uint neighbors[]; };
layout(set=0,binding=4,std430) buffer Status { uint status[]; };
void main(){
 uint gid=gl_GlobalInvocationID.x,lid=gl_LocalInvocationID.x;
 uint ns=uint(max(pc.n_sites_f,0.0)+0.5),words=uint(max(pc.words_per_site_f,0.0)+0.5),mode=uint(max(pc.mode,0.0)+0.5),cap=uint(max(pc.capacity_f,0.0)+0.5);
 if(mode==2u){if(lid==0u){uint total=0u;offsets[0]=0u;for(uint s=0u;s<ns;++s){total+=degree[s];offsets[s+1u]=total;}status[0]=uint(max(pc.generation_f,0.0)+0.5);status[1]=total;status[2]=(total>cap)?1u:0u;status[3]=ns;}return;}
 if(gid>=ns||words==0u)return;
 if(mode==0u){uint count=0u,base=gid*words;for(uint w=0u;w<words;++w)count+=uint(bitCount(adj[base+w]));degree[gid]=count;return;}
 if(mode==1u && (status[0] != uint(max(pc.generation_f,0.0)+0.5) || status[2] != 0u || status[3] != ns)) return;
 uint dst=offsets[gid],base=gid*words;for(uint w=0u;w<words;++w){uint bits=adj[base+w];while(bits!=0u){uint bit=uint(findLSB(bits));if(dst<cap)neighbors[dst]=w*32u+bit;dst++;bits&=bits-1u;}}
}
