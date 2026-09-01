# US Open 10-Minute Monitor — Scheduler Plan

## Plan only — LIVE_ACTIVATED = NO

Recommended production scheduler: dedicated Windows Scheduled Task/local-agent trigger every 10 minutes.

The runner:
1. derives 09:30 ET cash open using the current DST regime,
2. converts to KST,
3. exits `NO_ACTION` outside the first-three-hours window,
4. performs one early-warning check inside the window,
5. writes only the `US_OPEN_10M_*` namespace,
6. never writes `MARKET5_LATEST_REPORT`,
7. alerts only on material change.

Hourly collision protection is storage/authority separation: the hourly layer owns the full report and Latest; the 10-minute layer is `EARLY_WARNING_ONLY`.

Rollback path: disable the dedicated 10-minute task. The hourly automation does not require rollback.

Activation requires a separate CONTROL review and user approval.
