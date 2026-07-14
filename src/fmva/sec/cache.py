"""Small auditable disk cache for SEC JSON responses."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """Cached JSON payload and metadata."""

    payload: dict[str, Any]
    fetched_at: float
    url: str


class JsonDiskCache:
    """URL-keyed JSON cache with explicit time-to-live behavior."""

    def __init__(self, directory: Path, ttl_seconds: int) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds

    def _path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def get(self, url: str) -> CacheEntry | None:
        """Return a fresh cache entry, or None for missing/stale/malformed data."""

        path = self._path(url)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = float(raw["fetched_at"])
            if self.ttl_seconds and time.time() - fetched_at > self.ttl_seconds:
                return None
            payload = raw["payload"]
            if not isinstance(payload, dict):
                return None
            return CacheEntry(payload=payload, fetched_at=fetched_at, url=str(raw["url"]))
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def put(self, url: str, payload: dict[str, Any]) -> None:
        """Atomically write one response to cache."""

        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(url)
        temporary = path.with_suffix(".tmp")
        record = {"url": url, "fetched_at": time.time(), "payload": payload}
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
