uniform float uPointScale;
uniform float uHoveredIndex;

attribute float a_potentiation;
attribute float a_typeIndex;
attribute float a_kindleCharge;

varying float v_potentiation;
varying float v_typeIndex;
varying float v_kindleCharge;
varying float v_isHovered;

void main() {
  v_potentiation = a_potentiation;
  v_typeIndex = a_typeIndex;
  v_kindleCharge = a_kindleCharge;
  v_isHovered = abs(float(gl_VertexID) - uHoveredIndex) < 0.5 ? 1.0 : 0.0;

  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);

  float baseSize = 0.8 + a_potentiation * 3.0;
  float kindleBoost = 1.0 + a_kindleCharge * 3.0;
  float hoverBoost = 1.0 + v_isHovered * 5.0;
  float attenuation = 120.0 / -mvPosition.z;

  gl_PointSize = baseSize * kindleBoost * hoverBoost * attenuation * uPointScale;
  gl_Position = projectionMatrix * mvPosition;
}
