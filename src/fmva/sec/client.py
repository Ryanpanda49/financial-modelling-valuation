"""Compliant SEC JSON client with retries, rate limiting, and local cache."""

from __future__ import annotations

import gzip
import json
import logging
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable
from typing import Any

from fmva.config.models import SecConfig
from fmva.exceptions import SecRequestError
from fmva.sec.cache import JsonDiskCache, TextDiskCache
from fmva.sec.rate_limit import RateLimiter

LOGGER = logging.getLogger(__name__)
JsonTransport = Callable[[str, dict[str, str], float], dict[str, Any]]
TextTransport = Callable[[str, dict[str, str], float], str]


def _urllib_json_transport(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset("utf-8")
        content_encoding = response.headers.get("Content-Encoding", "")
        payload = json.loads(
            _decode_response_body(response.read(), content_encoding).decode(charset)
        )
    if not isinstance(payload, dict):
        raise ValueError("SEC response root must be a JSON object.")
    return payload


def _urllib_text_transport(url: str, headers: dict[str, str], timeout: float) -> str:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset("utf-8")
        content_encoding = response.headers.get("Content-Encoding", "")
        return _decode_response_body(response.read(), content_encoding).decode(charset)


def _decode_response_body(body: bytes, content_encoding: str) -> bytes:
    """Decode HTTP content encodings explicitly requested from SEC."""

    encoding = content_encoding.strip().lower()
    if encoding == "gzip":
        return gzip.decompress(body)
    if encoding == "deflate":
        try:
            return zlib.decompress(body)
        except zlib.error:
            return zlib.decompress(body, -zlib.MAX_WBITS)
    return body


class SecClient:
    """Retrieve SEC JSON endpoints according to a conservative access policy."""

    DATA_BASE = "https://data.sec.gov"
    WWW_BASE = "https://www.sec.gov"

    def __init__(
        self,
        config: SecConfig,
        *,
        transport: JsonTransport | None = None,
        text_transport: TextTransport | None = None,
        cache: JsonDiskCache | None = None,
        text_cache: TextDiskCache | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        config.validate_for_live_requests()
        self.config = config
        self.transport = transport or _urllib_json_transport
        self.text_transport = text_transport or _urllib_text_transport
        self.cache = cache or JsonDiskCache(config.cache_directory, config.cache_ttl_seconds)
        self.text_cache = text_cache or TextDiskCache(
            config.cache_directory, config.cache_ttl_seconds
        )
        self.rate_limiter = RateLimiter(config.requests_per_second, sleeper=sleeper)
        self.sleeper = sleeper
        self.headers = {
            "User-Agent": config.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

    def get_json(self, url: str, *, use_cache: bool = True) -> dict[str, Any]:
        """Get one JSON object, retrying transient failures with exponential backoff."""

        if self.config.cache_enabled and use_cache:
            cached = self.cache.get(url)
            if cached is not None:
                LOGGER.debug("SEC cache hit: %s", url)
                return cached.payload

        attempts = self.config.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            self.rate_limiter.wait()
            try:
                payload = self.transport(url, self.headers, self.config.timeout_seconds)
                if self.config.cache_enabled:
                    self.cache.put(url, payload)
                return payload
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
            if attempt < attempts - 1:
                delay = min(2**attempt, 8)
                LOGGER.warning("SEC request failed; retrying in %ss: %s", delay, url)
                self.sleeper(delay)
        raise SecRequestError(
            f"SEC request failed after {attempts} attempt(s): {url}. "
            f"Cause: {last_error!s}"
        ) from last_error

    def get_text(self, url: str, *, use_cache: bool = True) -> str:
        """Get one SEC text/XML document with the same retry and cache policy."""

        if self.config.cache_enabled and use_cache:
            cached = self.text_cache.get(url)
            if cached is not None:
                LOGGER.debug("SEC text cache hit: %s", url)
                return cached.payload

        attempts = self.config.max_retries + 1
        last_error: Exception | None = None
        headers = {**self.headers, "Accept": "application/xml,text/xml,text/plain,*/*"}
        for attempt in range(attempts):
            self.rate_limiter.wait()
            try:
                payload = self.text_transport(url, headers, self.config.timeout_seconds)
                if self.config.cache_enabled:
                    self.text_cache.put(url, payload)
                return payload
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
                last_error = exc
            if attempt < attempts - 1:
                delay = min(2**attempt, 8)
                LOGGER.warning("SEC text request failed; retrying in %ss: %s", delay, url)
                self.sleeper(delay)
        raise SecRequestError(
            f"SEC text request failed after {attempts} attempt(s): {url}. "
            f"Cause: {last_error!s}"
        ) from last_error

    def company_tickers(self) -> dict[str, Any]:
        """Return the SEC company ticker registry."""

        return self.get_json(f"{self.WWW_BASE}/files/company_tickers.json")

    def submissions(self, cik: str) -> dict[str, Any]:
        """Return submissions metadata for a zero-padded CIK."""

        return self.get_json(f"{self.DATA_BASE}/submissions/CIK{int(cik):010d}.json")

    def company_facts(self, cik: str) -> dict[str, Any]:
        """Return Company Facts for a zero-padded CIK."""

        return self.get_json(f"{self.DATA_BASE}/api/xbrl/companyfacts/CIK{int(cik):010d}.json")

    def filing_directory(self, cik: str, accession_number: str) -> dict[str, Any]:
        """Return the SEC Archives directory index for one filing accession."""

        accession = accession_number.replace("-", "").strip()
        if not accession.isdigit():
            raise ValueError("Accession number must contain only digits and hyphens.")
        return self.get_json(
            f"{self.WWW_BASE}/Archives/edgar/data/{int(cik)}/{accession}/index.json"
        )
