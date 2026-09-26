class_name CassiGpuTextureBridge
extends RefCounted
## Renderer seam for compute-produced global RenderingDevice textures.
## Texture2DRD is renderer-visible only when the RID comes from the shared
## device returned by RenderingServer.get_rendering_device().

static func wrap(texture_rd: RID) -> Texture2DRD:
	var texture := Texture2DRD.new()
	texture.texture_rd_rid = texture_rd
	return texture
