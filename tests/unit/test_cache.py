from pathlib import Path

from fmva.sec.cache import JsonDiskCache


def test_cache_round_trip(tmp_path: Path) -> None:
    cache = JsonDiskCache(tmp_path, ttl_seconds=60)
    cache.put("https://example.test/data", {"ok": True})
    entry = cache.get("https://example.test/data")
    assert entry is not None
    assert entry.payload == {"ok": True}


def test_zero_ttl_does_not_expire(tmp_path: Path) -> None:
    cache = JsonDiskCache(tmp_path, ttl_seconds=0)
    cache.put("https://example.test/data", {"ok": True})
    assert cache.get("https://example.test/data") is not None
