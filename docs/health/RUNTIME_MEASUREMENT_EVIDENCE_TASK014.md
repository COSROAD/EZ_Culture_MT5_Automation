# TASK-GITHUB-FOUNDATION-014 Runtime Measurement Evidence

**Classification:** `RUNTIME_MEASUREMENT_EVIDENCE`

> **THIS IS NOT APPROVED_RUNTIME_BASELINE**

This document preserves the read-only Culture Capital runtime-configuration measurements completed under TASK-GITHUB-FOUNDATION-014. It is confirmation evidence only. It does not change or promote `APPROVED_RUNTIME_BASELINE`.

## Measurement scope

- Culture Broker: `CultureCapital` — **MEASURED**
- Culture Server: `CultureCapital-Server` — **MEASURED**
- Discovery method: MT5 `.chr` profile deep parse + Culture config/profile-reference search + running-terminal read-only evidence + MarketData metadata
- Active runtime profile: Profile 3 signature match candidate — **VERIFY_REQUIRED**
- Direct proof that the currently running Culture terminal explicitly loaded Profile 3: **NOT AVAILABLE**

## Measured chart evidence

| Symbol | Period | Ichimoku | MA | Legacy V2.2 | GeneratedTime | MACD |
|---|---:|---:|---:|---:|---:|---:|
| US100 | M30 | 1 | 2 | 1 | 1 | 1 |
| XAUUSD | M30 | 1 | 2 | 0 | 1 | 1 |
| XAGUSD | M30 | 1 | 2 | 0 | 1 | 1 |
| WTI | M30 | 1 | 2 | 0 | 1 | 1 |
| BTCUSD | M30 | 1 | 2 | 0 | 1 | 1 |

GeneratedTime was measured exactly once on each of the five target charts.

## Parameter evidence

### Moving Average

- MA1 period: `30` — **MEASURED**
- MA2 period: `60` — **MEASURED**
- Method raw: `0` — **MEASURED_RAW**
- Reference semantic candidate: `MODE_SMA / Simple` — **REFERENCE_ONLY**
- Applied-price semantic promotion: **NOT APPROVED**

### MACD

- Fast: `12` — **MEASURED**
- Slow: `26` — **MEASURED**
- Signal: `9` — **MEASURED**

### Ichimoku

- Tenkan: `9` — **MEASURED**
- Kijun: `26` — **MEASURED**
- Senkou Span B: `52` — **MEASURED**

## Parser RCA

The MT5 `.chr` `Main` pane block is chart-pane metadata, not an attached indicator. The Phase-2 parser excludes `Main` from indicator inventory. This correction removed the false `UNAPPROVED_INDICATOR: Main` mismatch without suppressing real indicator mismatches.

## Remaining verification

- `ACTIVE_RUNTIME_PROFILE_DIRECT_REFERENCE` — **VERIFY_REQUIRED**

This remaining item is intentionally preserved. No chart click, profile switch, timeframe switch, indicator attach/delete, MT5 restart, or runtime mutation was used to force confirmation.

## Baseline policy

Measured values are **confirmation evidence only**. Baseline promotion requires CONTROL review and USER approval.
