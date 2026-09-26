#[compute]
// Direct inline Field source ABI: live EY/EI float grids, never stale cached fields.
// Each voxel deposits to eight clamped CIC cells. PC uses half extents and a
// center origin: p = origin - extents + (coord+0.5)/N * 2*extents.
#version 450
layout(local_size_x=256,local_size_y=1,local_size_z=1) in;
layout(push_constant,std430) uniform PC {
 vec3 bounds_min; float grid_size;
 vec3 bounds_max; float field_grid;
 vec3 field_extents; float field_origin_x;
 float field_origin_y; float field_origin_z; float field_scale; float cell_volume;
} pc;
layout(set=0,binding=0,std430) readonly buffer FieldEY { float ey[]; } fy;
layout(set=0,binding=1,std430) readonly buffer FieldEI { float ei[]; } fi;
layout(set=0,binding=2,std430) buffer FieldAccum { uvec2 field_acc[]; } fa;
bool good(float x){return !(isnan(x)||isinf(x));}
void add_field(uint index,uint amount){uint old=atomicAdd(fa.field_acc[index].x,amount);if(old>0xffffffffu-amount)atomicAdd(fa.field_acc[index].y,1u);}
uint ci(ivec3 c,uint n){return uint(c.x)*n*n+uint(c.y)*n+uint(c.z);}
void main(){
 uint id=gl_GlobalInvocationID.x,fn=max(1u,uint(pc.field_grid+0.5)),total=fn*fn*fn;
 if(id>=total)return;
 float y=fy.ey[id],i=fi.ei[id];if(!good(y)||!good(i))return;
 float op=length(vec2(y,i));if(!(op>1e-12))return;
 uint n=max(1u,uint(pc.grid_size+0.5));uint z=id%fn;uint t=id/fn;uint yy=t%fn;uint xx=t/fn;
 vec3 half_ext=max(pc.field_extents,vec3(1e-6));
 vec3 qpos=vec3(pc.field_origin_x,pc.field_origin_y,pc.field_origin_z)-half_ext+((vec3(float(xx),float(yy),float(z))+vec3(0.5))/float(fn))*(2.0*half_ext);
 vec3 span=max(pc.bounds_max-pc.bounds_min,vec3(1e-6));vec3 q=clamp((qpos-pc.bounds_min)/span*float(n)-vec3(0.5),vec3(0.0),vec3(float(n)-1.0001));
 ivec3 i0=ivec3(floor(q));vec3 f=clamp(q-vec3(i0),vec3(0.0),vec3(1.0));
 float source_volume=8.0*half_ext.x*half_ext.y*half_ext.z/float(total);
 float vals[4]=float[4](op,op*y,op*i,op*clamp(op,0.0,1.0));
 for(int dx=0;dx<2;++dx)for(int dy=0;dy<2;++dy)for(int dz=0;dz<2;++dz){
  ivec3 c=clamp(i0+ivec3(dx,dy,dz),ivec3(0),ivec3(int(n)-1));float w=(dx==0?1.0-f.x:f.x)*(dy==0?1.0-f.y:f.y)*(dz==0?1.0-f.z:f.z);uint cell=ci(c,n);
  for(uint k=0u;k<4u;++k){float value=vals[k]*w*source_volume*max(pc.field_scale,1.0);uint amount=uint(clamp(round(abs(value)),0.0,4294967040.0));if(amount>0u)add_field(8u*cell+2u*k+(value<0.0?1u:0u),amount);}
 }
}
