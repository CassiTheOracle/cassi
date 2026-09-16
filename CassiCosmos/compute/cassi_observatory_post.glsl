#[compute]
// Observatory/Cinematic POST_TRANSPARENT resolve.
// Binding 0 is the renderer-owned resolved scene color and is intentionally
// read/write in place. Bindings 1/2 are borrowed optical volume/depth outputs;
// bindings 3/4 are previous volume-only history; bindings 5/6 are next history.
// Binding 7 is an owned std430 parameter record. No borrowed RID is released.
#version 450
layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;

const float EPS = 1e-6;
const float INV_TWO_PI = 0.15915494309189535;

layout(push_constant, std430) uniform CameraPC {
    vec3 camera_origin; float fov_y;
    vec3 camera_right; float out_width;
    vec3 camera_up; float out_height;
    vec3 camera_forward; float optical_near;
} pc;

// params[0] = exposure EV, bloom, temporal enable, field mode
// params[1] = background enable, history valid, reset, auto exposure
// params[2] = previous origin xyz, previous fov
// params[3] = previous right xyz, previous width
// params[4] = previous up xyz, previous height
// params[5] = previous forward xyz, source epoch
// params[6] = current source epoch, resize epoch, composition kind (0 layered,
//             1 prescribed replacement, 2 physical replacement), background scale
layout(set=0,binding=0,rgba16f) uniform readonly image2D scene_color;
layout(set=0,binding=1,rgba32f) uniform readonly image2D volume_color;
layout(set=0,binding=2,r32f) uniform readonly image2D volume_depth;
layout(set=0,binding=3,rgba32f) uniform readonly image2D history_color;
layout(set=0,binding=4,r32f) uniform readonly image2D history_depth;
layout(set=0,binding=5,rgba32f) uniform writeonly image2D next_history_color;
layout(set=0,binding=6,r32f) uniform writeonly image2D next_history_depth;
layout(set=0,binding=7,std430) readonly buffer PostParams { vec4 params[]; } pp;
layout(set=0,binding=8,std430) readonly buffer ExposureState { vec4 exposure; } exposure_state;
layout(set=0,binding=9,rgba16f) uniform writeonly image2D combined_color;
layout(set=0,binding=10,rgba16f) uniform writeonly image2D bright_color;
// Binding 11 carries the world background alone and is writeonly here, so it
// never enters this pass's meter. The bloom pass adds it after the exposure
// multiply, so exposure never scales the sky directly; the shared highlight
// curve still acts on the combined pixel.
layout(set=0,binding=11,rgba16f) uniform writeonly image2D background_color;
bool finite1(float x) { return !(isnan(x) || isinf(x)); }
bool finite3(vec3 x) { return finite1(x.x) && finite1(x.y) && finite1(x.z); }
vec3 safe3(vec3 x) { return finite3(x) ? x : vec3(0.0); }

vec3 ray_dir(vec2 ndc) {
    float w=max(pc.out_width,1.0), h=max(pc.out_height,1.0);
    float aspect=w/h;
    float tan_half=tan(0.5*max(pc.fov_y,0.001));
    return normalize(pc.camera_forward + pc.camera_right*(ndc.x*aspect*tan_half)
        + pc.camera_up*(ndc.y*tan_half));
}

ivec2 uv_pixel(vec2 uv, ivec2 dim) {
    vec2 p=clamp(uv,vec2(0.0),vec2(0.999999))*vec2(dim);
    return ivec2(clamp(p,vec2(0.0),vec2(dim-1)));
}

vec4 volume_load(ivec2 p) {
    ivec2 d=imageSize(volume_color);
    ivec2 q=clamp(p,ivec2(0),max(d-1,ivec2(0)));
    vec4 v=imageLoad(volume_color,q);
    if (!finite3(v.rgb) || !finite1(v.a)) return vec4(0.0);
    return max(v,vec4(0.0));
}

vec4 volume_at(vec2 uv) {
    ivec2 d=imageSize(volume_color);
    if (d.x<=0 || d.y<=0) return vec4(0.0);
    vec2 p=clamp(uv,vec2(0.0),vec2(1.0))*vec2(d)-vec2(0.5);
    ivec2 p0=ivec2(floor(p)), p1=p0+ivec2(1);
    vec2 f=fract(p);
    return mix(mix(volume_load(p0),volume_load(ivec2(p1.x,p0.y)),f.x),
        mix(volume_load(ivec2(p0.x,p1.y)),volume_load(p1),f.x),f.y);
}

float depth_load(ivec2 p) {
    ivec2 d=imageSize(volume_depth);
    ivec2 q=clamp(p,ivec2(0),max(d-1,ivec2(0)));
    float v=imageLoad(volume_depth,q).r;
    return finite1(v) && v>0.0 ? v : 0.0;
}

float depth_at(vec2 uv) {
    ivec2 d=imageSize(volume_depth);
    if (d.x<=0 || d.y<=0) return 0.0;
    vec2 p=clamp(uv,vec2(0.0),vec2(1.0))*vec2(d)-vec2(0.5);
    ivec2 p0=ivec2(floor(p)), p1=p0+ivec2(1);
    vec2 f=fract(p);
    return mix(mix(depth_load(p0),depth_load(ivec2(p1.x,p0.y)),f.x),
        mix(depth_load(ivec2(p0.x,p1.y)),depth_load(p1),f.x),f.y);
}


// Fixed angular cells define actual persistent star centers. Analytic pixel
// filtering avoids the sparkling produced by hashing continuous camera rays.
float star_hash(vec2 cell) {
    return fract(sin(dot(cell,vec2(127.1,311.7)))*43758.5453);
}
vec3 background_radiance(vec3 direction) {
    // A continuous deep-sky floor keeps free-flight orientation legible when
    // every camera ray misses the finite simulation window. The previous
    // star-only result was exactly zero across almost every pixel, so leaving
    // the window and turning away from the origin looked like a renderer
    // failure. These values mirror the main scene's procedural sky, attenuated
    // here by the requested background gain, and remain subordinate to both
    // matter radiance and the explicit background toggle, which ships off. The
    // depth floor carries the visible level, so it drops about 3 EV; the star
    // field drops less so it stays a legible cue against the darker floor.
    const float BACKGROUND_FLOOR_GAIN=0.12;
    const float BACKGROUND_STAR_GAIN=0.4;
    float altitude=clamp(direction.y*0.5+0.5,0.0,1.0);
    vec3 zenith=mix(vec3(0.003,0.007,0.020),vec3(0.006,0.012,0.035),altitude)
        *BACKGROUND_FLOOR_GAIN;
    float horizon=exp(-7.0*abs(direction.y));
    vec3 radiance=mix(zenith,vec3(0.025,0.050,0.110)*BACKGROUND_FLOOR_GAIN,
        0.32*horizon);

    // Fixed angular cells define actual persistent star centers. Analytic
    // pixel filtering avoids sparkle when the camera turns.
    const vec2 grid=vec2(512.0,256.0);
    const float pi=3.141592653589793;
    vec2 angular=vec2(atan(direction.z,direction.x)/(2.0*pi)+0.5,
        acos(clamp(direction.y,-1.0,1.0))/pi)*grid;
    vec2 base=floor(angular);
    float footprint=pc.fov_y*grid.y/(pi*max(pc.out_height,1.0));
    float variance=0.0036+footprint*footprint/12.0;
    for(int y=-1;y<=1;++y) for(int x=-1;x<=1;++x) {
        vec2 cell=base+vec2(x,y), wrapped=vec2(mod(cell.x,grid.x),cell.y);
        if(cell.y<0.0 || cell.y>=grid.y || star_hash(wrapped)>0.012) continue;
        float warm=star_hash(wrapped+17.3);
        vec2 center=cell+vec2(0.2)+0.6*vec2(warm,star_hash(wrapped+41.7));
        vec2 delta=angular-center;
        vec3 spectrum=mix(vec3(0.45,0.58,0.8),vec3(1.0,0.78,0.56),warm);
        radiance+=spectrum*0.018*0.0036/variance*exp(-0.5*dot(delta,delta)/variance)
            *BACKGROUND_STAR_GAIN;
    }
    return radiance;
}


vec4 history_resolve(vec2 uv, vec4 current, float depth, ivec2 out_dim) {
    float temporal=clamp(pp.params[0].z,0.0,1.0);
    bool enabled=temporal>0.5 && pp.params[1].y>0.5 && pp.params[1].z<0.5;
    if (!enabled || depth<=0.0) return current;
    vec4 po=pp.params[2], pr=pp.params[3], pu=pp.params[4], pf=pp.params[5];
    float prev_fov=po.w, prev_w=pr.w, prev_h=pu.w;
    if (prev_fov<=0.0 || prev_w<=1.0 || prev_h<=1.0) return current;
    // Screen UV is top-left; convert to pinhole NDC before ray generation.
    vec2 ndc=vec2(uv.x*2.0-1.0,1.0-uv.y*2.0);
    vec3 p=pc.camera_origin+ray_dir(ndc)*depth;
    vec3 delta=p-po.xyz;
    float prev_forward=dot(delta,pf.xyz);
    if (!(prev_forward>EPS) || !finite1(prev_forward)) return current;
    float tan_half=tan(0.5*prev_fov), aspect=prev_w/max(prev_h,1.0);
    vec2 prev_ndc=vec2(dot(delta,pr.xyz)/max(prev_forward*tan_half*aspect,EPS),
        dot(delta,pu.xyz)/max(prev_forward*tan_half,EPS));
    vec2 prev_uv=vec2(prev_ndc.x*0.5+0.5,0.5-prev_ndc.y*0.5);
    if (any(lessThan(prev_uv,vec2(0.0))) || any(greaterThanEqual(prev_uv,vec2(1.0)))) return current;
    ivec2 hp=uv_pixel(prev_uv,imageSize(history_color));
    vec4 old=imageLoad(history_color,hp);
    float old_depth=imageLoad(history_depth,hp).r;
    float old_distance=length(delta);
    float tol=0.06*max(max(old_distance,old_depth),1e-3);
    if (!(old_depth>0.0) || !finite1(old_depth) || abs(old_distance-old_depth)>tol) return current;

    // Clamp history against a 3x3 neighborhood in optical-image texels.
    vec4 lo=current, hi=current;
    ivec2 vd=imageSize(volume_color);
    vec2 texel=1.0/vec2(max(vd,ivec2(1)));
    for (int oy=-1;oy<=1;++oy) for (int ox=-1;ox<=1;++ox) {
        vec4 n=volume_at(uv+vec2(ox,oy)*texel);
        lo=min(lo,n); hi=max(hi,n);
    }
    vec4 clamped=clamp(old,lo,hi);
    return mix(current,clamped,clamp(temporal,0.0,0.92));
}

void main() {
    ivec2 pix=ivec2(gl_GlobalInvocationID.xy);
    ivec2 dim=imageSize(scene_color);
    if (pix.x>=dim.x || pix.y>=dim.y || dim.x<=0 || dim.y<=0) return;
    vec2 uv=(vec2(pix)+vec2(0.5))/vec2(dim);
    vec4 scene=imageLoad(scene_color,pix);
    if (!finite3(scene.rgb) || !finite1(scene.a)) scene=vec4(0.0);
    vec4 current_volume=volume_at(uv);
    float depth=depth_at(uv);
    vec4 resolved_volume=current_volume;
    // Particle scene radiance is already attenuated by the point material.
    // It is added once and is never included in history.
    if (pp.params[0].w>0.5 || pp.params[6].z>0.5) scene=vec4(0.0);
    resolved_volume=history_resolve(uv,current_volume,depth,dim);

    // The medium radiates only where it is the subject: field and cosmology
    // compositions. In the particle composition the matter is the point cloud,
    // and a radiating medium reads as a coarse voxel wash laid over it, so the
    // medium keeps transmittance only: it still darkens the background behind
    // dense matter and still carries optical depth, and adds no light.
    float composition_kind=pp.params[6].z;
    vec3 medium_radiance=composition_kind<0.5?vec3(0.0):resolved_volume.rgb;
    vec3 total=scene.rgb+medium_radiance;
    float residual=clamp(1.0-resolved_volume.a,0.0,1.0);
    bool background_allowed=composition_kind<0.5 || composition_kind>1.5;
    vec3 background=vec3(0.0);
    if (pp.params[1].x>0.5 && background_allowed) background=background_radiance(
        ray_dir(vec2(uv.x*2.0-1.0,1.0-uv.y*2.0)))
        *residual*clamp(pp.params[6].w,0.0,1.0);

    // Prepare pass writes linear combined HDR and thresholded bright output.
    // Bloom filtering/tone mapping is a separate pass, so neighboring pixels
    // never race with writes to the renderer-owned scene image.
    vec3 combined_safe=clamp(safe3(total),vec3(0.0),vec3(65504.0));
    vec3 bright=clamp(combined_safe-vec3(1.0),vec3(0.0),vec3(65504.0));
    imageStore(combined_color,pix,vec4(combined_safe,1.0));
    imageStore(bright_color,pix,vec4(bright,1.0));
    imageStore(background_color,pix,vec4(
        clamp(safe3(background),vec3(0.0),vec3(65504.0)),1.0));
    imageStore(next_history_color,pix,resolved_volume);
    imageStore(next_history_depth,pix,vec4(depth,0.0,0.0,0.0));
}
