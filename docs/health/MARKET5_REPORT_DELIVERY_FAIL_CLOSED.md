# MARKET5 Report Delivery / Freshness Fail-Closed Architecture

Task: `TASK-REPORT-DELIVERY-HEALTH-001`

## Safety boundary

This implementation is a GitHub task-branch framework only. It does **not** replace the live reporting pipeline and it does not write to Google Drive. Live deployment requires explicit user approval.

## Success chain

`REPORT_GENERATED → HISTORY_SAVED → HISTORY_REOPEN_VERIFIED → LATEST_UPDATED → LATEST_REOPEN_VERIFIED → REPORT_ID_MATCH → CONTENT_HASH_MATCH → CONTROL_READABLE → DATA_FRESHNESS_CHECKED → CONTROL_RECEIVED`

Any unverified stage is not PASS.

## Atomic delivery order

1. Generate report with unique `REPORT_ID`.
2. Save timestamped history report.
3. Re-open history report and verify REPORT_ID + content hash.
4. Update `MARKET5_LATEST_REPORT`.
5. Re-open Latest and verify REPORT_ID + content hash.
6. Verify Latest REPORT_ID equals the latest completed scheduled-run REPORT_ID.
7. Only then mark delivery PASS.

A Drive write API success response alone is never sufficient.

## Fail-closed CONTROL rule

If Latest is stale, its REPORT_ID differs from the latest completed run, or reopen verification fails:

- emit `[CURRENT_REPORT_DELIVERY_FAILURE]`;
- set current report to unavailable;
- preserve the last valid report only as `REFERENCE_ONLY`;
- never silently reuse an older report as CURRENT.

## Freshness dimensions

The following are independent:

- REPORT_FRESHNESS
- SIGNAL_DATA_FRESHNESS
- MARKET_DATA_FRESHNESS
- WEB_MARKET_FRESHNESS

Signal fresh + Market stale is not an overall market-data PASS. Conversely, no new signal is not itself a failure when the signal stream explicitly allows no-new-signal.

## User-facing header

Every current-market response must surface, before directional analysis:

1. CURRENT REPORT TIME
2. CURRENT DELIVERY STATUS
3. DATA FRESHNESS

Stale-data warnings must not be buried below the market analysis.

## Delivery failure alert

If a scheduled run executes but Latest is not updated and reopened successfully, return `[DRIVE_DELIVERY_FAILURE]` with scheduled run time, last valid report time, failure stage, market-data freshness and signal-data freshness.

## Runtime deployment

`LIVE_DEPLOYMENT = NO` for this task branch.
