#[compute]
// Verification-only copy: renderer-owned color lacks CAN_COPY_FROM usage.
// Read the actual pre-tonemap image into a readback-capable SSBO instead.
#version 450
layout(local_size_x=8,local_size_y=8,local_size_z=1) in;
layout(set=0,binding=0,rgba16f) uniform readonly image2D source_color;
layout(set=0,binding=1,std430) writeonly buffer Pixels { vec4 color[]; } output_pixels;
void main() {
    ivec2 pixel=ivec2(gl_GlobalInvocationID.xy);
    ivec2 dimensions=imageSize(source_color);
    if(any(greaterThanEqual(pixel,dimensions))) return;
    output_pixels.color[pixel.y*dimensions.x+pixel.x]=imageLoad(source_color,pixel);
}
