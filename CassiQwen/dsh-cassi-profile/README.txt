Side-by-side DeepSeek Harness profile

Set DSH_HOME to a separate home, install/link this profile's dependencies, and launch the installed dsh binary with --profile cassi. The profile connects directly to the already-running loopback Cassi entity at 127.0.0.1:8090; no entity API key or token file is required.

To enable the bounded exact-source tool, configure host-only source roots before launching:

```powershell
$env:CASSI_SOURCE_ROOTS = 'C:\Users\Carina\workspaces\Cassi'
```

Separate multiple roots with the platform path delimiter (`;` on Windows). The plugin registers `cassi_read_source` only when this value is non-empty. A non-empty `sourceRoots` array in the Cordis patch takes precedence over the environment value; leaving both empty keeps source reads disabled. Paths are read relative to the configured roots, not as arbitrary absolute paths.

The profile patch enables the bounded `cassi_execute_work_order` broker for
`cassi_read_source` only. It dispatches through Harness's normal ToolRuntime
pipeline and persists outcomes to
`CassiQwen/_diag/field-brain-entity/work-orders.jsonl` by default; override
that path with `CASSI_WORK_ORDER_LEDGER`. Reads are pre-authorized by the
configured source-root boundary. Other effect classes require an active
Harness approval turn and an `allowed-once` answer; no generated-code or
arbitrary-shell executor is registered.
