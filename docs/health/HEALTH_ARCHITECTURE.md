# Health Architecture

Phase-1 implements a read-only Python core. Windows/MT5 adapters may be added later,
but no adapter is allowed to modify MT5, charts, indicators, Scheduler, Drive, or runtime data.

The end-to-end lifecycle is:

`GENERATED -> LOCAL_SAVED -> AGGREGATED -> DRIVE_SYNCED -> CONTROL_READABLE -> CONTROL_REVIEWED -> USER_REPORTED`

A technical pipeline status and a human delivery-lifecycle status are kept separately.
An unverified stage must never be silently promoted to `PASS`.

Phase-1 modules implemented:

- status / fail-closed primitives
- approved runtime baseline validation and hash
- runtime snapshot comparison framework
- recovery report generation (candidate only, never authorization)
- GitHub read-only baseline health
- F-drive Core-6 read-only hash/stat health
- control-summary formatter

No runtime installation, scheduling, compile, or deployment is included.
