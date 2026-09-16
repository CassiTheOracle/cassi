#[compute]
// Bloom/filter/tone pass. It reads owned staging images only and writes the
// renderer scene color one pixel at a time, avoiding cross-pixel in-place races.
// The world background arrives premultiplied by its residual/scale in binding 4
// and is resolved AFTER exposure, so matter is metered while the background
// stays a fixed reference.
#version 450
// Must match AUTO_EXPOSURE_EV_LIMIT in cassi_observatory_post_luma.glsl, which
// stores the bounded correction this pass applies.
const float AUTO_EXPOSURE_EV_LIMIT = 8.0;
layout(local_size_x=8,local_size_y=8,local_size_z=1) in;
layout(push_constant,std430) uniform PC { float exposure_ev; float bloom; float auto_exposure; float reserved; } pc;
layout(set=0,binding=0,rgba16f) uniform writeonly image2D scene_color;
layout(set=0,binding=1,rgba16f) uniform readonly image2D combined_color;
layout(set=0,binding=2,rgba16f) uniform readonly image2D bright_color;
layout(set=0,binding=3,std430) readonly buffer ExposureState { vec4 exposure; } exposure_state;
layout(set=0,binding=4,rgba16f) uniform readonly image2D background_color;

vec3 filmic(vec3 x) {
    x=max(x,vec3(0.0));
    return clamp((x*(2.51*x+0.03))/(x*(2.43*x+0.59)+0.14),vec3(0.0),vec3(1.0));
}
ivec2 clamp_px(ivec2 p,ivec2 d) { return clamp(p,ivec2(0),max(d-1,ivec2(0))); }
void main() {
    ivec2 p=ivec2(gl_GlobalInvocationID.xy), d=imageSize(scene_color);
    if (p.x>=d.x || p.y>=d.y || d.x<=0 || d.y<=0) return;
    ivec2 q=clamp_px(p,d);
    vec3 total=imageLoad(combined_color,q).rgb;
    // A normalized Gaussian kernel in display-angular units. Thresholding
    // happened in linear HDR before this pass; faint matter is not bloomed.
    vec3 bright=vec3(0.0);
    const float weights[5]=float[5](1.0,4.0,6.0,4.0,1.0);
    int stride=max(1,int(round(float(d.y)/240.0)));
    if (pc.bloom>0.0) {
        for (int y=-2;y<=2;++y) for (int x=-2;x<=2;++x)
            bright+=imageLoad(bright_color,clamp_px(q+ivec2(x,y)*stride,d)).rgb
                *weights[x+2]*weights[y+2]/256.0;
    }
    total+=bright*clamp(pc.bloom,0.0,1.0);
    float exposure=exp2(clamp(pc.exposure_ev,-12.0,12.0));
    if (pc.auto_exposure>0.5) exposure*=exp2(clamp(
        exposure_state.exposure.x,-AUTO_EXPOSURE_EV_LIMIT,AUTO_EXPOSURE_EV_LIMIT));
    // Exposure governs matter only: the world background is added after the
    // exposure multiply, so it is never directly exposure-scaled and never
    // metered. It does join the sum before the shared highlight transform, so
    // that transform still compresses it where matter shares the pixel.
    vec3 background=max(imageLoad(background_color,q).rgb,vec3(0.0));
    imageStore(scene_color,p,vec4(filmic(total*exposure+background),1.0));
}
