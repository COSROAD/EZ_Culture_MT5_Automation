
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

UTC = timezone.utc

@dataclass(frozen=True)
class AlignedTime:
    utc: str
    kst: str
    source_time: str
    source_timezone: str
    broker: Optional[str] = None
    server: Optional[str] = None

def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def align_time(value: str, source_timezone: timezone, broker: str | None = None, server: str | None = None) -> AlignedTime:
    dt = parse_iso(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=source_timezone)
    utc_dt = dt.astimezone(UTC)
    kst_dt = utc_dt.astimezone(timezone.utc).replace(tzinfo=None)  # temporary arithmetic basis
    from datetime import timedelta
    kst_dt = (utc_dt + timedelta(hours=9)).replace(tzinfo=timezone(timedelta(hours=9)))
    return AlignedTime(
        utc=utc_dt.isoformat(),
        kst=kst_dt.isoformat(),
        source_time=dt.isoformat(),
        source_timezone=str(source_timezone),
        broker=broker,
        server=server,
    )
