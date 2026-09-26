/**
 * @cassicore/spine — json-schema → omptype/Zod builder shared by tool wrappers.
 *
 * The retained mind-tool definitions from `@cassicore/tools` describe parameters as a
 * JSON-Schema subset (`ToolParamSchema`: `type: 'object'`, `properties`, `required`).
 * ohmypi's `registerTool` wants a Zod/omptype schema (`pi.zod.object({...})`). This
 * module converts the retained JSON-Schema form to the Zod shapes the spine registers,
 * preserving exact names/requiredness/defaults so the registered tool schemas stay
 * faithful to the retained definitions.
 *
 * The zod builder is captured structurally (only the subset of the omptype/zod API the
 * converter needs) so this module stays independent of the exact omptype type surface.
 */

import type { ToolParamSchema, ToolParamProperty } from '@cassicore/tools'

/** Minimal structural view of the ohmypi zod builder this converter needs. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface ZodBuilder {
  object(shape: Record<string, any>): any
  string(): any
  number(): any
  boolean(): any
  array(item: any): any
  enum(values: readonly [string, ...string[]]): any
  any(): any
}

/**
 * Build a Zod object schema from a retained JSON-Schema `ToolParamSchema` using the
 * ohmypi-injected `zod` builder. Returns the builder's object schema.
 */
export function zodFromParamSchema(zod: ZodBuilder, schema: ToolParamSchema): ReturnType<ZodBuilder['object']> {
  const shape: Record<string, any> = {}
  for (const [key, prop] of Object.entries(schema.properties ?? {})) {
    const z = zodFromProp(zod, prop)
    shape[key] = schema.required?.includes(key) ? z : z.optional()
  }
  return zod.object(shape)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function zodFromProp(zod: ZodBuilder, prop: ToolParamProperty): any {
  switch (prop.type) {
    case 'string':
      if (prop.enum && prop.enum.length > 0) return zod.enum(prop.enum as [string, ...string[]])
      return zod.string()
    case 'number':
      return prop.enum && prop.enum.length > 0
        ? zod.enum(prop.enum.map(String) as [string, ...string[]])
        : zod.number()
    case 'boolean':
      return zod.boolean()
    case 'array':
      return zod.array(zodFromProp(zod, prop.items ?? { type: 'string' }))
    case 'object':
      return zod.object(toShape(zod, prop)).passthrough()
    default:
      return zod.any()
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toShape(zod: ZodBuilder, prop: ToolParamProperty): Record<string, any> {
  const shape: Record<string, any> = {}
  const meta = prop as { required?: string[]; properties?: Record<string, ToolParamProperty> }
  for (const [k, v] of Object.entries(meta.properties ?? {})) {
    const nested = v as ToolParamProperty
    shape[k] = meta.required?.includes(k) ? zodFromProp(zod, nested) : zodFromProp(zod, nested).optional()
  }
  return shape
}
