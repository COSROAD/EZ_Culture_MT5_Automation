# Fail-Closed Policy

The following conditions must never yield false PASS:

- missing protected file
- protected SHA mismatch
- approved runtime baseline mismatch
- missing or duplicate expected indicator
- unapproved indicator/chart
- period mismatch
- known parameter mismatch
- output stale
- broker mixing
- historical rewrite
- new critical duplicate
- requested compile result unknown
- Drive delivery unconfirmed
- local/remote protected baseline mismatch
- secret detection
- expected runtime no-data

Unimplemented modules report `UNKNOWN`, `NOT_REQUESTED`, or `PENDING_VALIDATION` as appropriate.

The agent is read-only. It may DETECT and REPORT only.
Automatic recovery, rollback, commit, push, compile, deploy, MT5 restart, or chart modification are prohibited.
