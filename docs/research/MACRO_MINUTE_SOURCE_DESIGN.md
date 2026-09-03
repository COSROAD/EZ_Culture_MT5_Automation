# Macro Minute / Near-Minute Historical Source Design

Required: DXY, US 2Y, US 10Y, US 30Y, Real Yield.

Options:
1. Institutional vendor feed (Bloomberg/LSEG/ICE-class): tick/sub-minute where entitled, deep history, commercial licensing/redistribution constraints.
2. Licensed DXY/index-owner source: authoritative DXY intraday access subject to license/vendor terms.
3. Broker/platform proxy feed: near-real-time possible, but source identity must be retained and a proxy must not be mislabeled as canonical cash yield.
4. Public official sources (Treasury/FRED-class): strong authoritative daily/reference history, generally insufficient alone for complete minute reconstruction.

Local design: source-separated raw storage, UTC canonical timestamps, source/vendor/instrument identity on every row, derived normalized minute tables written separately, no silent proxy substitution. Missing/stale => VERIFY_REQUIRED/NOT_AVAILABLE. No automatic paid subscription.

Recommendation: use licensed intraday source when funded; until then preserve minute macro fields as VERIFY_REQUIRED.
