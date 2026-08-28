#[compute]
// Dedicated clamped/open JFA. mode 0 clears A/B; mode 1 seeds A;
// mode 2 floods selected input with bounded neighbors; mode 3 copies output.
#version 450
layout(local_size_x=64,local_size_y=1,local_size_z=1) in;
layout(push_constant,std430) uniform PC { float grid_n_f; float n_sites_f; float mode; float read_a; float jump; float extent_x; float extent_y; float extent_z; } pc;
layout(set=0,binding=0,std430) readonly buffer Sites { vec4 site_pos[]; };
layout(set=0,binding=1,std430) buffer LabelsA { uint labels_a[]; };
layout(set=0,binding=2,std430) buffer LabelsB { uint labels_b[]; };
layout(set=0,binding=3,std430) buffer Output { uint labels_out[]; };
const uint INVALID=0xffffffffu;
int idx3(int x,int y,int z,int n){return x*n*n+y*n+z;}
vec3 cell_pos(int id,int n){int x=id/(n*n),r=id-x*n*n,y=r/n,z=r-y*n;return (vec3(x,y,z)+vec3(.5))*vec3(2.0*pc.extent_x,2.0*pc.extent_y,2.0*pc.extent_z)/float(n);}
void main(){uint gid=gl_GlobalInvocationID.x;int n=int(pc.grid_n_f+.5),ns=int(pc.n_sites_f+.5),cells=n*n*n;uint mode=uint(pc.mode+.5);if(mode==0u){if(gid<uint(cells)){labels_a[gid]=INVALID;labels_b[gid]=INVALID;}return;}if(mode==1u){if(gid<uint(ns)){vec3 p=site_pos[gid].xyz;ivec3 q=clamp(ivec3(floor(vec3(p.x/(2.0*pc.extent_x),p.y/(2.0*pc.extent_y),p.z/(2.0*pc.extent_z))*float(n))),ivec3(0),ivec3(n-1));atomicMin(labels_a[idx3(q.x,q.y,q.z,n)],gid);}return;}if(gid>=uint(cells)||n<=0||ns<=0)return;if(mode==3u){labels_out[gid]=(pc.read_a>.5)?labels_a[gid]:labels_b[gid];return;}int id=int(gid),x=id/(n*n),r=id-x*n*n,y=r/n,z=r-y*n;bool read_a=pc.read_a>.5;uint best=read_a?labels_a[id]:labels_b[id];float bd=3.402823466e+38;if(best<uint(ns)){vec3 d=site_pos[best].xyz-cell_pos(id,n);bd=dot(d,d);}int jmp=max(int(pc.jump+.5),1);for(int dz=-1;dz<=1;dz++)for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++){int xx=x+dx*jmp,yy=y+dy*jmp,zz=z+dz*jmp;if(xx<0||yy<0||zz<0||xx>=n||yy>=n||zz>=n)continue;uint j=read_a?labels_a[idx3(xx,yy,zz,n)]:labels_b[idx3(xx,yy,zz,n)];if(j>=uint(ns))continue;vec3 d=site_pos[j].xyz-cell_pos(id,n);float dd=dot(d,d);if(dd<bd||(dd==bd&&j<best)){bd=dd;best=j;}}if(read_a)labels_b[id]=best;else labels_a[id]=best;}
