// 13 engram type colors — luminous on dark void
const vec3 TYPE_COLORS[13] = vec3[13](
  vec3(0.31, 0.76, 0.97),  // fact - #4FC3F7
  vec3(0.67, 0.28, 0.74),  // episode - #AB47BC
  vec3(1.00, 0.44, 0.26),  // decision - #FF7043
  vec3(0.40, 0.73, 0.42),  // pattern - #66BB6A
  vec3(1.00, 0.79, 0.16),  // abstraction - #FFCA28
  vec3(0.94, 0.33, 0.31),  // goal - #EF5350
  vec3(0.47, 0.56, 0.61),  // file - #78909C
  vec3(0.15, 0.78, 0.85),  // tool - #26C6DA
  vec3(0.49, 0.34, 0.76),  // session - #7E57C2
  vec3(1.00, 0.65, 0.15),  // outcome - #FFA726
  vec3(0.55, 0.43, 0.39),  // source_file - #8D6E63
  vec3(0.93, 0.25, 0.48),  // changeset - #EC407A
  vec3(0.15, 0.65, 0.60)   // artifact - #26A69A
);

varying float v_potentiation;
varying float v_typeIndex;
varying float v_kindleCharge;
varying float v_isHovered;

void main() {
  // radial glow: bright center, soft falloff
  vec2 uv = gl_PointCoord * 2.0 - 1.0;
  float dist = dot(uv, uv);
  if (dist > 1.0) discard;

  float glow = exp(-dist * 3.0);

  // color from engram type
  int idx = clamp(int(v_typeIndex), 0, 12);
  vec3 baseColor = TYPE_COLORS[idx];

  // kindle charge adds white-hot brightness
  vec3 kindleColor = mix(baseColor, vec3(1.0, 0.95, 0.85), v_kindleCharge * 0.7);

  // hover brightens significantly
  vec3 finalColor = mix(kindleColor, vec3(1.0), v_isHovered * 0.7);

  // intensity from potentiation + kindle — base brightness visible for all points
  float alpha = glow * (0.15 + v_potentiation * 0.45 + v_kindleCharge * 0.8 + v_isHovered * 0.6);
  alpha = clamp(alpha, 0.0, 1.0);

  gl_FragColor = vec4(finalColor * glow, alpha);
}
