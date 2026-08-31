from pathlib import Path
import hashlib
from datetime import datetime, timezone


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def file_stat(path):
    p = Path(path)
    if not p.exists():
        return {"exists": False, "path": str(p)}
    stat = p.stat()
    return {
        "exists": True,
        "path": str(p),
        "size_bytes": stat.st_size,
        "modified_time_utc": datetime.fromtimestamp(
            stat.st_mtime, timezone.utc
        ).isoformat(),
        "sha256": sha256_file(p),
    }


def check_core6(items):
    results = []
    for item in items:
        data = file_stat(item["path"])
        data["source_id"] = item["source_id"]
        data["expected_sha256"] = item["sha256"]
        data["sha_match"] = (
            data.get("exists")
            and data.get("sha256") == item["sha256"].upper()
        )
        results.append(data)

    all_ok = all(r.get("exists") and r.get("sha_match") for r in results)
    return {
        "status": "PASS" if all_ok else "FAIL",
        "items": results,
        "matched": sum(1 for r in results if r.get("sha_match")),
        "expected": len(results),
    }
