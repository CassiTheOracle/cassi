# @cassicore/plugins

Host-side plugin system extracted from CassiCore `core/plugins/*` +
`core/plugin-host.ts`. History-preserved import splice. The overhaul session's
mind-plugin consumes this surface — export names/shapes preserved verbatim.

## Surface

- `PluginAPI` (`plugin-api.ts`) + `PluginAPIDeps`/`PluginAPIResult` — the
  injected host facade.
- `PluginRegistry` (`plugin-registry.ts`).
- `CassiCoreClient` (`client-sdk.ts`) — client SDK (Node `http` to the daemon
  admin API).
- `PluginHost` (`plugin-host.ts`) — fork-based worker manager (`implements
  IPluginHost`), wires `bus` from `@cassicore/events`.
- `external-clients/{curator,types}` — `ExternalClientCurator` +
  `CurationConfig`/`CurationMeta` (types from `@cassicore/thalamus`).

Protocol interfaces (`IPluginHost`, `PluginManifest`, `PluginStatus`,
`PluginRegistration`, `PluginToCore`, `PluginCapability`, …) come from
`@cassicore/foundation` `types/plugin.ts` + `types/interfaces.ts` — NOT
re-vendored.

Depends on `@cassicore/events`, `@cassicore/foundation`, `@cassicore/thalamus`.
