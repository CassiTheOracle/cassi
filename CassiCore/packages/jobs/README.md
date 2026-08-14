# @cassicore/jobs

Background job manager (fork-based) and `Job` types extracted from CassiCore's
`core/jobs/`. History-preserved import splice. Simplest package in the phase —
depends on `@cassicore/foundation` (`IEventBus`/`ILogger` as types) and Node
builtins only (`node:child_process/fs/path/os`). `RingBuffer` is defined in
`types.ts`.

## Surface

- `JobManager` (`job-manager.ts`)
- `Job`, `JobConfig`, `JobResult`, `JobStatus`, `RingBuffer` (`types.ts`)
