#!/bin/bash
set -euo pipefail
mkdir -p shaders
echo "Compiling QiCube GLSL compute shaders..."
for f in shaders/*.comp; do
    spv="${f%.comp}.spv"
    echo "  $f -> $spv"
    glslangValidator -V "$f" -o "$spv"
done
echo "Done. $(ls shaders/*.spv 2>/dev/null | wc -l) shaders compiled."
ls -la shaders/*.spv
