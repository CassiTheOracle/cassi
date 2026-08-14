/**
 * P8-DEFERRED native module declaration — `cassi-larql` (LARQL vindex sidecar
 * native bindings). Not packaged; entry/vindex-loader.ts loads it dynamically
 * behind a try/catch ("cassi-larql native module not found"). This declaration
 * keeps vindex-loader typechecking until P8 packages the native module.
 */
declare module 'cassi-larql' {
  export function loadVindexOnly(path: string): unknown
  export function vindexGateKnn(handle: unknown, layer: unknown, tokenId: unknown, topK: number): unknown
}
