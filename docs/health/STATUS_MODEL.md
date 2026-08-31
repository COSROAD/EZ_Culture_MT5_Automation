# Status Model

Supported states:

- PASS
- WARN
- FAIL
- UNKNOWN
- MARKET_CLOSED
- PENDING_VALIDATION
- VERIFY_REQUIRED
- BASELINE_MISMATCH
- NOT_REQUESTED

Priority for fail-closed aggregation:

`FAIL > BASELINE_MISMATCH > WARN > UNKNOWN/VERIFY_REQUIRED/PENDING_VALIDATION > PASS`

Only literal `PASS` is considered a pass. `UNKNOWN`, `VERIFY_REQUIRED`, and
`PENDING_VALIDATION` must never be converted to PASS.

`MARKET_CLOSED` is a special market state and is not equivalent to healthy live tick flow.
