# BTC Historical Event Replay

Read-only historical replay for BTC using actually available MarketDataCollector raw data. BTC is aligned to NQ by UTC. Candidate thresholds are derived from trailing past observations only and remain `RESEARCH_CANDIDATE_ONLY`.

The replay separates microstructure/M1/M5 timing from M30/H1 long-horizon regime context. Macro minute inputs and crypto-specific external flows remain `VERIFY_REQUIRED` when unavailable. Future prices are used only to label outcomes and compute MFE/MAE after an event; they are never passed into `shadow_replay`, preventing future leakage.

Operational outputs are written only under `04_CSV_기록/Research/BTCEventReplay` and are not committed to Git.
