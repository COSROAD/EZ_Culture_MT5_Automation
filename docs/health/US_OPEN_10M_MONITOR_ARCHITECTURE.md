# US Market Open 10-Minute Intensive Monitor — Phase 1

Task: `TASK-US-OPEN-10MIN-MONITOR-001`

## Selected architecture: B

Use a dedicated 10-minute early-warning/change-detection layer. The existing hourly MARKET5 report remains authoritative.

### Reasons
- no overwrite of `MARKET5_LATEST_REPORT`
- lower delivery collision risk
- isolated DST/window logic
- simpler rollback: disable the dedicated task
- explicit `EARLY_WARNING_ONLY` authority

### Time source
The source of truth is US cash open at 09:30 Eastern. KST is derived automatically.
- DST open derives to 22:30 KST
- standard-time open derives to 23:30 KST
- active window is `[open, open + 3h)`

### Alert model
`10M CHECK → CHANGE DETECTION → RISK CLASSIFICATION → ALERT DECISION`

No meaningful change => `NO_MATERIAL_CHANGE`, no manufactured user alert.

### Protected hourly authority
The 10-minute layer must never overwrite `MARKET5_LATEST_REPORT`.

Candidate persistent namespace:
- `US_OPEN_10M_STATUS.json`
- `US_OPEN_10M_ALERT_<CHECK_ID>.json`

### Freshness
Keep WEB, SIGNAL and MARKET freshness independent. A stale MT5 stream never becomes current quantitative confirmation merely because web data is fresh.

### Corporate credit
US IG/HY issuance, IG/HY spreads, new issue concession when available, issuance calendar, Treasury supply/hedge pressure, 2Y/10Y/30Y and real yield are rate-pressure inputs. Missing values are `VERIFY_REQUIRED`/`N/A`, never fabricated.

### Phase-1 safety
No live scheduler activation. No MT5/chart/indicator/EX5/EA/order/position/lot/risk/schema change.
