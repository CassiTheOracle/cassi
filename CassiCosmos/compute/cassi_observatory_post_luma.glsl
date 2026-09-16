#[compute]
#version 450
// Two-stage luminance estimator over the lit field. Mode 0 writes at most 4096
// samples; mode 1 averages the lit ones and updates one persistent EV scalar.
// Empty samples carry a sentinel so empty sky cannot dominate the mean: with
// the whole frame averaged, sparse views drove the correction into its clamp
// and washed the matter out instead of tracking it.
// The correction is bounded to a wide EV band and approaches its target over a
// couple of seconds, so it follows the field rather than pumping the frame.
// AUTO_EXPOSURE_EV_LIMIT must match the clamp in
// cassi_observatory_post_bloom.glsl, which applies the stored correction.
layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;
const float AUTO_EXPOSURE_EV_LIMIT = 8.0;
const float AUTO_EXPOSURE_SECONDS = 2.0;
// Below this scene radiance a sample counts as empty space, not as matter.
const float LUMA_EMPTY_FLOOR = 1.0e-6;
// Written for empty samples; any real log-luminance is far above this.
const float SAMPLE_EMPTY = -1000.0;
// Accepted range for the metered target, which arrives in the push constant.
const float LUMA_TARGET_MIN = 0.01;
const float LUMA_TARGET_MAX = 1.0;
layout(push_constant, std430) uniform PC { float mode; float delta; float field_mode; float target_luma; } pc;
layout(set=0,binding=0,rgba16f) uniform readonly image2D scene_color;
layout(set=0,binding=1,rgba32f) uniform readonly image2D volume_color;
layout(set=0,binding=2,std430) buffer ExposureState { vec4 state; } exposure;
layout(set=0,binding=3,std430) buffer LumaSamples { float samples[]; } luma;

float safe_luma(vec3 c) {
    if (isnan(c.x)||isinf(c.x)||isnan(c.y)||isinf(c.y)||isnan(c.z)||isinf(c.z)) return 0.0;
    return dot(max(c,vec3(0.0)),vec3(0.2126,0.7152,0.0722));
}

void main() {
    if (pc.mode < 0.5) {
        uvec2 gid=gl_GlobalInvocationID.xy;
        if (gid.x>=64u || gid.y>=64u) return;
        vec3 matter=vec3(0.0);
        if (pc.field_mode > 0.5) {
            // Field and cosmology compositions render the medium alone.
            ivec2 vd=imageSize(volume_color);
            if (vd.x>0 && vd.y>0) {
                ivec2 vp=clamp(ivec2((vec2(gid)+vec2(0.5))/vec2(64.0)*vec2(vd)),ivec2(0),vd-ivec2(1));
                matter=imageLoad(volume_color,vp).rgb;
            }
        } else {
            // Particle composition renders the point layer alone; the medium
            // contributes transmittance only and must not enter the meter.
            ivec2 dim=imageSize(scene_color);
            if (dim.x>0 && dim.y>0) {
                ivec2 p=clamp(ivec2((vec2(gid)+vec2(0.5))/vec2(64.0)*vec2(dim)),ivec2(0),dim-ivec2(1));
                matter=imageLoad(scene_color,p).rgb;
            }
        }
        float lit=safe_luma(matter);
        luma.samples[gid.y*64u+gid.x]=lit>LUMA_EMPTY_FLOOR ? log(lit) : SAMPLE_EMPTY;
        return;
    }
    if (gl_GlobalInvocationID.x!=0u || gl_GlobalInvocationID.y!=0u) return;
    float sum_log=0.0;
    uint lit_count=0u;
    for (uint i=0u;i<4096u;++i) {
        float sample_value=luma.samples[i];
        if (sample_value>SAMPLE_EMPTY*0.5) { sum_log+=sample_value; lit_count+=1u; }
    }
    // Nothing lit: leave the state untouched. The correction is held instead of
    // being driven toward the positive clamp by a frame with no matter in it,
    // and no empty frame is ever recorded as a measurement.
    if (lit_count==0u) return;
    float mean_log=sum_log/float(lit_count);
    float target=clamp(pc.target_luma,LUMA_TARGET_MIN,LUMA_TARGET_MAX);
    float target_ev=clamp(log2(target)-mean_log/log(2.0),
        -AUTO_EXPOSURE_EV_LIMIT,AUTO_EXPOSURE_EV_LIMIT);
    float blend=1.0-exp(-max(pc.delta,0.0)/AUTO_EXPOSURE_SECONDS);
    exposure.state.x=mix(clamp(exposure.state.x,-AUTO_EXPOSURE_EV_LIMIT,
        AUTO_EXPOSURE_EV_LIMIT),target_ev,blend);
    exposure.state.y=mean_log;
}
